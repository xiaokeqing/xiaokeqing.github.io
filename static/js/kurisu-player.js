/* ============================================================================
   kurisu-player.js — CRT 场景 + 角色播放器（独立模块）
   ----------------------------------------------------------------------------
   设计约束（逐条对应交接规格 03 与站主评审 06）：
     · **零第三方依赖**：不用任何库、不请求任何外链（本文件里不出现绝对 URL 字面量）
     · **不侵入 static/js/app.js**：路由变化靠监听 hashchange/popstate +
       对 <main id="content"> 做 MutationObserver 重新扫描挂载点。
       app.js 完全不知道本模块存在（唯一例外：见下方"与 AI 问答联动"）。
     · **图集化**：每个剪辑是 8 列 × N 行的大图，帧序号 i → col=i%columns, row=⌊i/columns⌋，
       用 canvas drawImage(atlas, sx, sy, fw, fh, dx, dy, dw, dh) 切帧。
       请求数 = 每剪辑 1 张（+1 张 boot + 1 张静帧），**不是**每帧一个请求。
     · **首屏预算**：先只载 boot 图集（前 24 帧）与静帧（合计 < 0.7MB），
       hi 图集在首屏渲染完成后（默认 200ms + 空闲）再后台补；两者分辨率相同 ⇒ 切换不跳变。
     · **降级**：prefers-reduced-motion / navigator.connection.saveData / 窄屏
       → 只画静态一帧、不开动画循环、不载图集；
       document.visibilitychange 隐藏 → pause()（停 rAF 与加载队列），可见 → resume()。
     · **可访问性**：canvas / 装饰 img 一律 aria-hidden="true"；
       字幕与状态行是**真文本节点**（读屏与爬虫可读），本模块只写 textContent，绝不把文字画进 canvas。
     · **不自动播放任何音频**：本模块只创建一个 🔊 入口按钮（aria-pressed="false"），
       点击走 speak() —— 语音线尚未接入，因此是**空实现**，只如实回报"未启用"。
     · **不造假**：状态行的数字**只从页面上已经渲染出来的真实数据节点里读**
       （app.js 写进 [data-xk-mini] / [data-xk-stat] 的值）；读不到就写"读不到"，
       绝不编数字。字幕内容由模板/真实数据提供，本模块不生成任何数字。

   公开 API（window.KurisuPlayer）：
     KurisuPlayer.version
     KurisuPlayer.create(opts) -> instance
       opts = {
         mount:    元素或选择器（必须带 data-xk-kurisu="stage|rail|corner"）
         manifest: 清单地址（默认 /kurisu/manifest.json）
         basePath: 资源前缀（默认 "/"，manifest 里的 url 都相对站点根）
         mode:     'stage' | 'rail' | 'corner' | 'auto'（默认取 mount 上的 data 属性）
         defer:    首屏后延迟多少毫秒再开始（默认 200，规格要求"首屏渲染后再载"）
         staticOnly: 强制静态一帧
         onState:  状态回调（state, detail）
       }
     实例方法：
       instance.ready()                       -> Promise（manifest 已载、首帧已画）
       instance.play(clip)                    -> Promise（'idle' | 'speaking' | 'thinking'）
       instance.setEmotion(name)              -> Promise（头像模式；8 情绪）
       instance.showSubtitle(text)            -> 写入真文本节点
       instance.status(text|object)           -> 屏内右上状态行
       instance.intro(opts)                   -> Promise（"大头出场"：特写 → 拉远到全身）
       instance.pause() / resume() / destroy()
       instance.speak(phraseId, text)         -> Promise<{ok:false, reason:'TTS_DISABLED'}>
                                                 ★ 语音线（另派）从这里接进来
   ============================================================================ */

(function (global) {
  'use strict';

  var VERSION = '1.0.0';
  var DEFAULT_MANIFEST = '/kurisu/manifest.json';
  var DEFAULT_DEFER_MS = 200;          // 规格：首屏渲染完成之后再载角色资源
  var MAX_CLIPS_IN_MEMORY = 2;         // 只保留当前剪辑 + 下一个
  var MAX_ATLAS_PIXELS = 12000000;     // 单张图集像素上限（超过就别在移动端用）

  /* ------------------------------------------------------------------ 工具 */

  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function joinUrl(base, url) {
    if (!url) { return ''; }
    if (/^(https?:)?\/\//.test(url) || url.charAt(0) === '/') { return url; }
    var b = base || '/';
    if (b.charAt(b.length - 1) !== '/') { b += '/'; }
    return b + url;
  }

  function loadImage(src) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      img.decoding = 'async';
      img.onload = function () {
        // decode() 让解码也离开主线程；不支持就退回 onload
        if (img.decode) {
          img.decode().then(function () { resolve(img); }, function () { resolve(img); });
        } else { resolve(img); }
      };
      img.onerror = function () { reject(new Error('图片加载失败：' + src)); };
      img.src = src;
    });
  }

  function nextFrame() {
    return new Promise(function (r) {
      if (global.requestAnimationFrame) { global.requestAnimationFrame(function () { r(); }); }
      else { setTimeout(r, 16); }
    });
  }

  function whenIdle(fn) {
    if (global.requestIdleCallback) { global.requestIdleCallback(fn, { timeout: 1500 }); }
    else { setTimeout(fn, 60); }
  }

  function mq(query) {
    try { return global.matchMedia ? global.matchMedia(query) : null; } catch (e) { return null; }
  }
  function mqOn(m, fallback) { return m ? !!m.matches : !!fallback; }

  /** 环境探测：三种情况都必须降级成"只画静态一帧"（站主 06 补 2） */
  function probeEnv() {
    var conn = global.navigator && (global.navigator.connection || global.navigator.mozConnection);
    return {
      reducedMotion: mqOn(mq('(prefers-reduced-motion: reduce)'), false),
      // 窄屏 = 规格里的"移动窄屏"；CSS 断点就是 980px
      narrow: mqOn(mq('(max-width: 980px)'), (global.innerWidth || 1280) <= 980),
      saveData: !!(conn && (conn.saveData === true || /^2g$/.test(conn.effectiveType || ''))),
      supportCanvas: !!(document.createElement('canvas').getContext)
    };
  }

  /* ------------------------------------------ 与 AI 问答联动（不改 app.js） */
  /* 交接规格 01 §8.3 给的三种注入方式里侵入性最低的一种：
     包装 window.fetch，只识别 /api/public/ask 这一条，别的请求原样透传。
     —— 这就是"不侵入 app.js"的实现方式，代价是这条包装会一直挂着（很小）。 */
  var askBus = { listeners: [] };
  function askBusOn(fn) { askBus.listeners.push(fn); }
  function askBusEmit(phase, detail) {
    for (var i = 0; i < askBus.listeners.length; i++) {
      try { askBus.listeners[i](phase, detail); } catch (e) { /* 单个监听器出错不影响别的 */ }
    }
  }
  function installAskHook() {
    if (installAskHook.done || !global.fetch) { return; }
    installAskHook.done = true;
    var raw = global.fetch.bind(global);
    global.fetch = function (input, init) {
      var url = (typeof input === 'string') ? input : (input && input.url) || '';
      var isAsk = url.indexOf('/api/public/ask') >= 0;
      if (!isAsk) { return raw(input, init); }
      askBusEmit('start', { url: url });
      return raw(input, init).then(function (res) {
        // 只读一份 clone 用来解析状态，绝不消费调用方要用的那份 body
        try {
          res.clone().json().then(function (data) {
            askBusEmit('done', { url: url, data: data });
          }, function () { askBusEmit('done', { url: url, data: null }); });
        } catch (e) { askBusEmit('done', { url: url, data: null }); }
        return res;
      }, function (err) {
        askBusEmit('fail', { url: url, error: err });
        throw err;
      });
    };
  }

  /* ------------------------------------------------------------- 状态行 */
  /* 站主红线：状态行不许写死数字，必须是【真实数据】或"读不到"。
     这里不去自己打接口（那会多一次请求、也会多一处口径），而是读页面上
     app.js 已经渲染出来的真实节点，并且**连标签一起用页面自己的**——
     不二次归纳口径（不把"生效中"改叫"待处理"），避免语义漂移。
       主页   [data-xk-mini] ×3（今日拦截 / 生效中 / 护栏拦截）
       其它页 [data-xk-stat] ×N（24h 告警 / 护栏拦截 / 蜜罐事件）
       AI 页  [data-xk-chat-badge] + [data-xk-ask-quota]（状态徽标 + 额度）
     值还是 "—" 就说"正在读取"；"未接入"/"读不到" 就照说读不到。 */
  function labelOf(node, fallback) {
    var li = node.closest ? node.closest('li') : null;
    var scope = li || node.parentNode;
    var lab = scope && scope.querySelector
      ? scope.querySelector('.xk-mini__label, .xk-hstat__label, .xk-chat__quota + *, label')
      : null;
    var t = lab ? (lab.textContent || '').trim() : '';
    return t || fallback;
  }

  function isReal(v) { return !!v && v !== '—' && v !== '-' && v !== ''; }

  function readRealPairs() {
    var groups = [
      ['[data-xk-mini]', 3],
      ['[data-xk-stat]', 3],
      ['[data-xk-chat-badge]', 2]
    ];
    for (var g = 0; g < groups.length; g++) {
      var nodes = qa(groups[g][0]);
      if (!nodes.length) { continue; }
      var pairs = [];
      for (var i = 0; i < nodes.length && pairs.length < groups[g][1]; i++) {
        var n = nodes[i];
        pairs.push({
          label: n.getAttribute('data-xk-kurisu-label') || labelOf(n, n === nodes[0] ? '数值' : ''),
          raw: (n.textContent || '').trim()
        });
      }
      var quota = q('[data-xk-ask-quota]');
      if (quota) { pairs.push({ label: '额度', raw: (quota.textContent || '').replace(/^额度：/, '').trim() }); }
      return pairs;
    }
    return null;
  }

  function composeStatus() {
    var pairs = readRealPairs();
    if (!pairs || !pairs.length) { return '读不到实时数字（本页没有可核验的数据节点）'; }
    if (pairs.some(function (p) { return p.raw === '未接入' || p.raw === '读不到'; })) {
      return '读不到（接口本次取不到，不补数）';
    }
    if (!pairs.some(function (p) { return isReal(p.raw); })) { return '正在读取…'; }
    var parts = pairs.map(function (p) {
      var v = isReal(p.raw) ? p.raw : '读不到';
      return p.label ? (p.label + ' ' + v) : v;
    });
    return parts.join(' · ');
  }

  /* ---------------------------------------------------------------- 实例 */

  function Player(opts) {
    opts = opts || {};
    this.opts = opts;
    this.mount = (typeof opts.mount === 'string') ? q(opts.mount) : opts.mount;
    if (!this.mount) { throw new Error('KurisuPlayer: 找不到挂载元素'); }
    this.mode = opts.mode || this.mount.getAttribute('data-xk-kurisu') || 'auto';
    this.basePath = opts.basePath || '/';
    this.manifestUrl = opts.manifest || DEFAULT_MANIFEST;
    this.deferMs = (typeof opts.defer === 'number') ? opts.defer : DEFAULT_DEFER_MS;
    this.env = probeEnv();
    this.manifest = null;
    this.current = null;           // { clip, frames, columns, fw, fh, interval, tier }
    this.atlases = {};             // clip -> { boot: img, hi: img|null, order: [] }
    this.emotion = 'normal';
    this.emotionVariant = 'idle';
    this.raf = null;
    this.t0 = 0;
    this.elapsed = 0;
    this.paused = false;
    this.destroyed = false;
    this.staticOnly = !!opts.staticOnly || this.env.reducedMotion || this.env.saveData ||
      (this.env.narrow && (this.mode === 'stage' || this.mode === 'rail'));
    // 头像模式：非 AI 页的右栏、角落点缀、以及所有窄屏 —— 用 132px 图集而不是全身序列
    this.avatarMode = this.mode === 'corner' || this.env.narrow ||
      this.mount.hasAttribute('data-xk-kurisu-avatar');
    this.avatarFrame = this.avatarMode;
    this.inactive = false;     // 挂载点不可见（display:none）时为 true：一个字节都不载
    this.canvas = q('[data-xk-kurisu-canvas]', this.mount);
    this.sayEl = q('[data-xk-kurisu-say]', this.mount);
    this.statusEl = q('[data-xk-kurisu-status]', this.mount);
    this.introEl = q('[data-xk-kurisu-intro]', this.mount);
    this.voiceBtn = q('[data-xk-kurisu-voice]', this.mount);
    this.emoEl = q('[data-xk-kurisu-emo]', this.mount);
    this.placeholderSay = this.sayEl ? (this.sayEl.getAttribute('data-xk-default-say') ||
      this.sayEl.textContent) : '';
    this._onVis = this.handleVisibility.bind(this);
    this._onResize = this.handleResize.bind(this);
    this._onMq = this.handleEnvChange.bind(this);
    this._askOff = null;
  }

  Player.prototype.ready = function () {
    var self = this;
    if (this._readyPromise) { return this._readyPromise; }
    this._readyPromise = this.loadManifest().then(function () {
      if (self.destroyed) { return null; }
      // 挂载点不可见（例如窄屏下 .xk-crt 是 display:none）→ 立刻收工：
      // 这样手机端**不会**去下载 desk.webp / 全身图集（站主要求②的字节后果）。
      var rect = self.mount.getBoundingClientRect ? self.mount.getBoundingClientRect() : null;
      if (rect && (!rect.width || !rect.height)) {
        self.inactive = true;
        self.setState('inactive');
        return null;
      }
      self.build();
      return self.start();
    });
    return this._readyPromise;
  };

  Player.prototype.loadManifest = function () {
    var self = this;
    return fetch(this.manifestUrl, { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) { throw new Error('manifest HTTP ' + r.status); }
        return r.json();
      })
      .then(function (m) { self.manifest = m; return m; });
  };

  /* --------------------------------------------------------- DOM 骨架 */
  Player.prototype.build = function () {
    var m = this.manifest;
    var scene = (m && m.scene) || {};
    var imgs = scene.images || {};
    // CRT 屏幕里的实验室背景：交给 CSS 变量，模板那边只写 background-image: var(--xk-kurisu-lab)
    if (imgs.lab && imgs.lab.url) {
      this.mount.style.setProperty('--xk-kurisu-lab',
        'url("' + joinUrl(this.basePath, imgs.lab.url) + '")');
    }
    if (this.canvas) {
      // 装饰性动画容器：读屏必须忽略它（真文字在字幕/状态行里）
      this.canvas.setAttribute('aria-hidden', 'true');
      this.ctx = this.canvas.getContext('2d');
    }
    if (this.introEl) {
      this.introEl.setAttribute('aria-hidden', 'true');
      // 特写静帧在模板里只有 data-src（不是 src）：站主要求角色资源在首屏渲染完成之后
      // 才开始加载。走到这里说明已经过了延迟窗口，这时候才赋 src。
      var ds = this.introEl.getAttribute('data-src');
      if (ds && !this.introEl.getAttribute('src')) { this.introEl.setAttribute('src', ds); }
    }
    if (this.statusEl) {
      this.statusEl.textContent = '正在读取…';
      this.refreshStatus();
      // ★ 注意：这个 setInterval **不是帧循环**（03 规格明确要求帧推进必须用
      //   requestAnimationFrame + 时间累加，见下面的 tick()）。这里只做一件非动画的事：
      //   真实数字是 app.js 异步渲染进来的，偶尔也可能一直停在"正在读取…"，
      //   所以每 4s 重新读一次页面上那几个真实节点的文本 —— 它不触发布局动画、不掉帧，
      //   页面隐藏时也不需要它（隐藏时值不会变），因此保留 setInterval 而不是 rAF。
      this._statusTimer = setInterval(this.refreshStatus.bind(this), 4000);
      this._statusObs = new MutationObserver(this.refreshStatus.bind(this));
      var host = q('[data-xk-mini]') || q('[data-xk-stat]');
      if (host && host.closest) {
        var scope = host.closest('.xk-portal, .xk-hero, main') || document.body;
        this._statusObs.observe(scope, { subtree: true, childList: true, characterData: true });
      }
    }
    if (this.voiceBtn) { this.wireVoice(); }
    if (this.emoEl) { this.wireEmotions(); }
    this.handleResize();
  };

  Player.prototype.refreshStatus = function () {
    if (!this.statusEl || this.destroyed) { return; }
    var txt = composeStatus();
    if (this.statusEl.textContent !== txt) { this.statusEl.textContent = txt; }
  };

  /* 🔊 入口：本轮是空实现（语音线另派）。共用 wireVoiceButton 的诚实契约。 */
  Player.prototype.wireVoice = function () {
    wireVoiceButton(this.voiceBtn, q('[data-xk-kurisu-voice-note]', this.mount));
  };

  Player.prototype.wireEmotions = function () {
    var self = this;
    qa('[data-xk-emo]', this.emoEl).forEach(function (el) {
      el.addEventListener('click', function () {
        self.setEmotion(el.getAttribute('data-xk-emo'));
      });
    });
  };

  /* --------------------------------------------------------- 尺寸/绘制 */
  Player.prototype.boxSize = function () {
    // 舞台模式：画布 = CRT 屏幕矩形（100% × 100%）；其余模式用元素自身高度兜底
    if (this.mode === 'stage') {
      var st = this.mount;
      return { w: st.clientWidth, h: st.clientHeight };
    }
    if (this.mode === 'rail') {
      var h = Math.min(300, Math.max(160, Math.round((this.mount.clientWidth || 320) * 0.86)));
      return { w: this.mount.clientWidth || 320, h: h };
    }
    return { w: 132, h: 132 };   // corner
  };

  Player.prototype.handleResize = function () {
    if (!this.canvas || this.destroyed) { return; }
    var box = this.boxSize();
    var dpr = Math.min(global.devicePixelRatio || 1, 2);
    // 上限：别在 4K 上开一张巨画布（省显存也是省电）
    dpr = Math.min(dpr, Math.max(1, Math.sqrt(MAX_ATLAS_PIXELS / Math.max(1, box.w * box.h))));
    var w = Math.max(1, Math.round(box.w * dpr));
    var h = Math.max(1, Math.round(box.h * dpr));
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    this._cssW = box.w; this._cssH = box.h;
    this.draw();
  };

  Player.prototype.clear = function () {
    if (this.ctx) { this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height); }
  };

  Player.prototype.gotoStaticFrame = function () {
    var m = this.manifest;
    var self = this;
    if (!m) { return Promise.resolve(); }
    var url = null;
    if (this.avatarMode) {
      var emo = (m.emotions || {})[this.emotion] || (m.emotions || {}).normal;
      url = emo && emo.static && emo.static.url;
      this.aspect = 1;
    } else {
      var clip = (m.clips || {})[this.currentClipName || 'idle'];
      url = clip && clip.poster && clip.poster.url;
      this.aspect = clip ? (clip.frameWidth / clip.frameHeight) : 1;
    }
    if (!url) { return Promise.resolve(); }
    return loadImage(joinUrl(this.basePath, url)).then(function (img) {
      if (self.destroyed) { return; }
      self.staticImg = img;
      self.drawStatic(img);
      self.setState('static');
    });
  };

  /** 角色在画布里的摆放矩形。三种形态各自一套几何，来源都是 manifest.scene.compose：
   *   stage（主页 CRT 屏内）：高 = 屏高 × charHRatio、脚踩 footYRatio —— 与构建期合成脚本一致；
   *   rail（右栏人物区，全身）：填满面板高度、贴底；
   *   头像（corner / 窄屏 / 右栏头像模式）：正方形居中。 */
  Player.prototype.charRect = function (bw, bh, aspect) {
    var comp = ((this.manifest || {}).scene || {}).compose || {};
    if (this.mode === 'stage') {
      var hr = comp.charHRatio || 0.66;
      var fy = (typeof comp.footYRatio === 'number') ? comp.footYRatio : 0.96;
      var dh = bh * hr, dw = dh * aspect;
      return { x: (bw - dw) / 2, y: bh * fy - dh, w: dw, h: dh };
    }
    if (this.mode === 'rail' && !this.avatarFrame) {
      var h2 = bh * 0.98, w2 = h2 * aspect;
      return { x: (bw - w2) / 2, y: bh - h2, w: w2, h: h2 };
    }
    var s = Math.min(bw, bh) * 0.9;
    return { x: (bw - s) / 2, y: (bh - s) / 2, w: s, h: s };
  };

  Player.prototype.drawStatic = function (img) {
    if (!this.ctx) { return; }
    var cw = this.canvas.width, ch = this.canvas.height;
    this.ctx.clearRect(0, 0, cw, ch);
    this.ctx.imageSmoothingQuality = 'high';
    var r = this.charRect(cw, ch, this.aspect || 1);
    this.ctx.drawImage(img, r.x, r.y, r.w, r.h);
  };

  Player.prototype.draw = function () {
    if (!this.ctx) { return; }
    if (this.staticOnly || !this.current) {
      if (this.staticImg) { this.drawStatic(this.staticImg); }
      return;
    }
    var cur = this.current;
    var atlas = this.atlases[cur.clip];
    var img = atlas && (atlas.hi || atlas.boot);
    if (!img) { return; }
    cur.tier = atlas.hi ? 'hi' : 'boot';     // boot → hi 平滑替换（同分辨率、帧序一致）
    var total = cur.frames;
    var idx = cur.fixedFrame != null ? cur.fixedFrame
      : Math.floor(this.elapsed / cur.interval) % total;
    if (idx < 0) { idx = 0; }
    // boot 图集只有前 N 帧：还没补到 hi 时用取模回绕，保证始终有画面
    if (!atlas.hi && idx >= atlas.bootFrames) { idx = idx % atlas.bootFrames; }
    var col = idx % cur.columns;
    var row = Math.floor(idx / cur.columns);
    var cw = this.canvas.width, ch = this.canvas.height;
    var r = this.charRect(cw, ch, cur.fw / cur.fh);
    this.ctx.clearRect(0, 0, cw, ch);
    this.ctx.imageSmoothingQuality = 'high';
    this.ctx.drawImage(img, col * cur.fw, row * cur.fh, cur.fw, cur.fh, r.x, r.y, r.w, r.h);
  };

  /* ------------------------------------------------------------ 播放控制 */
  Player.prototype.tick = function (now) {
    if (this.paused || this.destroyed) { return; }
    if (!this.t0) { this.t0 = now; }
    this.elapsed = now - this.t0;
    this.draw();
    var self = this;
    this.raf = global.requestAnimationFrame(function (n) { self.tick(n); });
  };

  Player.prototype.startLoop = function () {
    if (this.raf || this.staticOnly || this.paused || this.destroyed) { return; }
    var self = this;
    this.t0 = 0;
    this.raf = global.requestAnimationFrame(function (n) { self.tick(n); });
  };
  Player.prototype.stopLoop = function () {
    if (this.raf) { global.cancelAnimationFrame(this.raf); this.raf = null; }
  };

  Player.prototype.ensureClip = function (name, deferHi) {
    // 规格：只保留当前剪辑 + 下一个；其余释放（img.src='' 让浏览器回收解码位图）
    var self = this;
    var m = this.manifest;
    var spec = (m.clips || {})[name];
    if (!spec) { return Promise.reject(new Error('清单里没有剪辑 ' + name)); }
    var entry = this.atlases[name];
    if (entry && entry.boot) { return Promise.resolve(entry); }
    var atlas = spec.atlas || {};
    var bootUrl = atlas.boot && atlas.boot.url;
    var hiUrl = atlas.hi && atlas.hi.url;
    return loadImage(joinUrl(this.basePath, bootUrl)).then(function (img) {
      if (self.destroyed) { throw new Error('destroyed'); }
      var e = { clip: name, boot: img, bootFrames: (atlas.boot && atlas.boot.frames) || spec.frames,
        hi: null, hiUrl: hiUrl };
      self.atlases[name] = e;
      self.evictOtherClips(name);
      if (!deferHi && hiUrl) { self.loadHi(name); }
      return e;
    });
  };

  Player.prototype.loadHi = function (name) {
    var self = this;
    var e = this.atlases[name];
    if (!e || e.hi || e.hiLoading || !e.hiUrl) { return; }
    // hi 图集可能过千万像素：只在非窄屏载（窄屏走静态帧，不载）；像素过多也跳过
    var spec = this.manifest.clips[name] || {};
    var px = ((spec.atlas || {}).hi || {}).w * (((spec.atlas || {}).hi || {}).h || 0);
    if (this.staticOnly || px > MAX_ATLAS_PIXELS * 2) { return; }
    e.hiLoading = true;
    // 站主要求：首屏渲染完成之后（默认 200ms）再补 hi；这里再让一次空闲，避免和首屏渲染抢带宽
    whenIdle(function () {
      loadImage(joinUrl(self.basePath, e.hiUrl)).then(function (img) {
        if (self.destroyed) { return; }
        e.hi = img; e.hiLoading = false;
        self.setState('tier:hi');
        self.draw();
      }, function () { e.hiLoading = false; });
    });
  };

  Player.prototype.evictOtherClips = function (keep) {
    var names = Object.keys(this.atlases);
    if (names.length <= MAX_CLIPS_IN_MEMORY) { return; }
    for (var i = 0; i < names.length; i++) {
      var n = names[i];
      if (n === keep || n === this.nextClip) { continue; }
      var e = this.atlases[n];
      if (e && e.boot) { e.boot.src = ''; }
      if (e && e.hi) { e.hi.src = ''; }
      delete this.atlases[n];
    }
  };

  Player.prototype.setCurrent = function (name, spec, atlas) {
    this.current = {
      clip: name,
      frames: spec.frames,
      columns: spec.columns || 8,
      fw: spec.frameWidth,
      fh: spec.frameHeight,
      interval: Math.max(16, spec.frameIntervalMs || 42),
      tier: atlas.hi ? 'hi' : 'boot',
      fixedFrame: null
    };
  };

  Player.prototype.play = function (name) {
    var self = this;
    var m = this.manifest;
    if (!m) { return Promise.reject(new Error('manifest 未载')); }
    if (this.staticOnly) {
      this.currentClipName = name;
      return this.gotoStaticFrame().then(function () { return self.current; });
    }
    return this.ensureClip(name, true).then(function (atlas) {
      if (self.destroyed) { return null; }
      self.setCurrent(name, m.clips[name], atlas);
      self.currentClipName = name;
      // hi 档（全帧图集）只给"主页 CRT 舞台"补：右栏/角落本来就只有 ~270px 高、
      // 只播 1 秒的 idle 循环，boot 的 24 帧同分辨率已经够用 —— 这样 AI 页的角色字节
      // 从 519KB(boot)+1.3MB(hi) 降到 519KB，稳稳落在 1.5MB 首屏预算内。
      if (self.mode === 'stage') { self.loadHi(name); }
      if (self.current.fixedFrame == null) { self.elapsed = self.elapsed % (self.current.interval * self.current.frames); }
      self.draw();
      self.startLoop();
      self.setState('clip:' + name);
      return self.current;
    });
  };

  Player.prototype.freezeAt = function (clipName, frameIdx) {
    // 口型同步/强调帧这类"停在某一帧"的需求（语音线会用到）
    if (this.current && this.current.clip === clipName) { this.current.fixedFrame = frameIdx; }
    this.draw();
  };

  /* 情绪 → 剪辑的映射。全身素材这一轮只转码了 idle / speaking / thinking 三个剪辑
     （体积原因，见交付报告），所以桌面右栏的 8 情绪是"高亮 + 有限的动作映射"；
     完整的 8 情绪**动画**在头像形态（窄屏 / 角落）里是齐的（素材自带 132px 图集）。 */
  var EMO_CLIP = {
    normal: 'idle', happy: 'idle', sad: 'idle', angry: 'idle', blush: 'idle',
    disappointed: 'idle', sided_thinking: 'thinking', sided_surprised: 'idle'
  };

  Player.prototype.setEmotion = function (name) {
    var m = this.manifest;
    var emo = (m.emotions || {})[name];
    var self = this;
    if (!emo) { return Promise.resolve(null); }
    this.emotion = name;
    if (this.emoEl) {
      qa('[data-xk-emo]', this.emoEl).forEach(function (el) {
        var on = el.getAttribute('data-xk-emo') === name;
        el.classList.toggle('is-on', on);
        el.setAttribute('aria-pressed', on ? 'true' : 'false');
        if (on) { el.setAttribute('aria-current', 'true'); } else { el.removeAttribute('aria-current'); }
      });
      var label = q('[data-xk-kurisu-emo-label]', this.mount);
      if (label) { label.textContent = emo.label || name; }
    }
    if (this.staticOnly) { return this.gotoStaticFrame(); }
    if (!this.avatarMode) {
      // 全身形态：改情绪只切"动作剪辑"（素材里 8 情绪不全是全身动画）
      var clip = EMO_CLIP[name] || 'idle';
      return this.play(clip).then(function () { return null; });
    }
    // 头像形态：画的是 132px 情绪图集（speaking 变体在说话时用）
    var v = emo[this.emotionVariant] || emo.idle;
    if (!v) { return Promise.resolve(null); }
    var key = 'emo:' + name + ':' + this.emotionVariant;
    if (this.atlases[key] && this.atlases[key].boot) {
      this.setCurrentAvatar(key, v, this.atlases[key]);
      return Promise.resolve(null);
    }
    return loadImage(joinUrl(this.basePath, v.url)).then(function (img) {
      if (self.destroyed) { return null; }
      self.atlases[key] = { boot: img, bootFrames: v.frames, hi: null };
      self.setCurrentAvatar(key, v, self.atlases[key]);
      return null;
    });
  };

  Player.prototype.setCurrentAvatar = function (key, v, atlas) {
    this.avatarFrame = true;
    this.current = {
      clip: key, frames: v.frames, columns: v.columns || 8,
      fw: v.frameSize, fh: v.frameSize,
      interval: Math.max(16, v.frameIntervalMs || 100),
      tier: 'boot', fixedFrame: null
    };
    this.aspect = 1;
    this.draw();
    this.startLoop();
  };

  Player.prototype.showSubtitle = function (text) {
    if (!this.sayEl) { return; }
    // 真文本节点（读屏/爬虫可读）；空文本回落到默认问候
    this.sayEl.textContent = text == null || text === '' ? this.placeholderSay : String(text);
  };

  Player.prototype.restoreSubtitle = function () {
    if (this.sayEl) { this.sayEl.textContent = this.placeholderSay; }
  };

  Player.prototype.status = function (v) {
    if (!this.statusEl) { return; }
    this.statusEl.textContent = (typeof v === 'string' && v) ? v : composeStatus();
  };

  /* -------------------------------------------------- "大头出场"（主页） */
  /* 素材里【没有】独立的贴脸特写镜头 → 用 idle 首帧的**原生分辨率静帧**当特写底图，
     再用 CSS transform scale 从 2.6 倍缩到 1 倍（transform-origin 在头部），
     同时画布在下面按正常比例播 idle；结尾静帧淡出 → 看起来就是"贴脸 → 拉远到全身"。
     用 CSS transform 而不是逐帧缩放：不占主线程、不掉帧；reduced-motion 下直接跳过。 */
  Player.prototype.intro = function (o) {
    o = o || {};
    var self = this;
    var el = this.introEl;
    var dur = o.durationMs || 2400;
    var from = o.from || 2.6;
    if (!el || this.staticOnly || this.env.reducedMotion) {
      if (el) { el.style.opacity = '0'; }
      return Promise.resolve({ played: false, reason: this.env.reducedMotion ? 'reduced-motion' : 'no-intro-asset' });
    }
    el.style.transition = 'none';
    el.style.transform = 'translateX(-50%) scale(' + from + ')';
    el.style.opacity = '1';
    this.setState('intro');
    return nextFrame().then(function () {
      el.style.transition = 'transform ' + dur + 'ms cubic-bezier(.22,.61,.36,1), opacity 500ms ' +
        Math.max(0, dur - 500) + 'ms ease-out';
      el.style.transform = 'translateX(-50%) scale(1)';
      el.style.opacity = '0';
      return new Promise(function (r) { setTimeout(function () { r({ played: true }); }, dur + 60); });
    });
  };

  Player.prototype.setState = function (s, detail) {
    this.state = s;
    if (typeof this.opts.onState === 'function') {
      try { this.opts.onState(s, detail); } catch (e) { /* 回调出错不影响播放 */ }
    }
  };

  /* ------------------------------------------------------------- 生命周期 */
  Player.prototype.start = function () {
    var self = this;
    document.addEventListener('visibilitychange', this._onVis, false);
    global.addEventListener('resize', this._onResize, false);
    ['(prefers-reduced-motion: reduce)', '(max-width: 980px)'].forEach(function (qs) {
      var m = mq(qs);
      if (m && m.addEventListener) { m.addEventListener('change', self._onMq); }
    });
    if (this.mount.getAttribute('data-xk-kurisu-hook') === 'ask') {
      this._askFn = function (phase, d) { self.onAsk(phase, d); };
      askBusOn(this._askFn);
    }
    if (this.staticOnly) {
      this.currentClipName = this.mount.getAttribute('data-xk-kurisu-clip') || 'idle';
      return this.gotoStaticFrame().then(function () { return self; });
    }
    if (this.avatarMode) {
      // 头像形态（窄屏 / 非 AI 页右栏 / 角落）：走 8 情绪图集，normal.idle 只有 84KB
      return this.setEmotion('normal').then(function () { return self; });
    }
    var first = this.mount.getAttribute('data-xk-kurisu-clip') || 'idle';
    return this.play(first).then(function () { return self; });
  };

  /** 与 AI 问答的状态联动：思考 → 说话 → 回 idle。文案一律用它自己给的（真数据）。 */
  Player.prototype.onAsk = function (phase, d) {
    var self = this;
    var say = this.sayEl;
    var setSay = function (t) { if (say && t) { say.textContent = t; } };
    if (phase === 'start') {
      this.emotionVariant = 'idle';
      this.setEmotion('sided_thinking');
      if (!this.staticOnly) { this.play('thinking'); }
      setSay('正在检索与研判 —— 这个问题会走真实的检索增强链路。');
    } else if (phase === 'done') {
      var data = d && d.data;
      var state = data && (data.state || data.mode);
      var text = '';
      try {
        var ans = data && (data.answer || data.text || (data.reply && data.reply.answer));
        if (ans) { text = String(ans).replace(/\s+/g, ' ').slice(0, 90); }
      } catch (e) { text = ''; }
      this.emotionVariant = 'speaking';
      this.setEmotion(this.emotionForState(state));
      if (!this.staticOnly) { this.play('speaking'); }
      // 字幕用【真实回答】的开头；拿不到就如实说拿不到，不编
      setSay(text || (data ? '已返回，但这条回答没有可显示的正文（见下方引用卡片）。'
        : '回答体读不到（非流式返回，正文见下方卡片）。'));
      setTimeout(function () {
        self.emotionVariant = 'idle';
        self.setEmotion('normal');
        if (!self.staticOnly) { self.play('idle'); }
        self.restoreSubtitle();
      }, 9000);
    } else if (phase === 'fail') {
      this.emotionVariant = 'idle';
      this.setEmotion('sad');
      if (!this.staticOnly) { this.play('idle'); }
      setSay('这次请求没送达（网络或限流），页面下方会有如实说明。');
    }
  };

  Player.prototype.emotionForState = function (state) {
    // 只做"状态 → 情绪"的映射，不改变任何口径文案
    switch (state) {
      case 'model': return 'happy';
      case 'rule-based': return 'normal';
      case 'input-insufficient': return 'sided_surprised';
      case 'no-retrieval': return 'disappointed';
      case 'retrieval-failed': return 'sad';
      case 'model-failed': return 'sad';
      default: return 'normal';
    }
  };

  Player.prototype.handleVisibility = function () {
    // 页面隐藏：停 rAF（省电/省流量）；可见：恢复并立刻补一次
    if (document.hidden) { this.pause(); } else { this.resume(); }
  };

  Player.prototype.handleResize = function () {
    if (!this.canvas || this.destroyed) { return; }
    var box = this.boxSize();
    var dpr = Math.min(global.devicePixelRatio || 1, 2);
    dpr = Math.min(dpr, Math.max(1, Math.sqrt(MAX_ATLAS_PIXELS / Math.max(1, box.w * box.h))));
    var w = Math.max(1, Math.round(box.w * dpr));
    var h = Math.max(1, Math.round(box.h * dpr));
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    this._cssW = box.w; this._cssH = box.h;
    this.draw();
  };

  Player.prototype.handleEnvChange = function () {
    var env = probeEnv();
    var wasStatic = this.staticOnly;
    this.env = env;
    this.staticOnly = !!this.opts.staticOnly || env.reducedMotion || env.saveData ||
      (env.narrow && (this.mode === 'stage' || this.mode === 'rail'));
    if (this.staticOnly && !wasStatic) {
      this.stopLoop();
      this.current = null;
      this.currentClipName = this.currentClipName || 'idle';
      this.gotoStaticFrame();
    } else if (!this.staticOnly && wasStatic) {
      this.play(this.currentClipName || 'idle');
    }
  };

  Player.prototype.pause = function () {
    this.paused = true;
    this.stopLoop();
    this.setState('paused');
  };
  Player.prototype.resume = function () {
    if (!this.paused) { return; }
    this.paused = false;
    this.t0 = 0;                       // 不把隐藏期间的时间算进去（否则会"跳帧"）
    if (!this.staticOnly && this.current) { this.startLoop(); }
    this.refreshStatus();
    this.setState('running');
  };

  Player.prototype.destroy = function () {
    this.destroyed = true;
    this.stopLoop();
    if (this._statusTimer) { clearInterval(this._statusTimer); }
    if (this._statusObs) { this._statusObs.disconnect(); }
    document.removeEventListener('visibilitychange', this._onVis, false);
    global.removeEventListener('resize', this._onResize, false);
    var self = this;
    ['(prefers-reduced-motion: reduce)', '(max-width: 980px)'].forEach(function (qs) {
      var m = mq(qs);
      if (m && m.removeEventListener) { m.removeEventListener('change', self._onMq); }
    });
    Object.keys(this.atlases).forEach(function (k) {
      var e = self.atlases[k];
      if (e && e.boot) { e.boot.src = ''; }
      if (e && e.hi) { e.hi.src = ''; }
    });
    this.atlases = {};
    if (this._askFn) {
      // 摘掉 ask 总线上的监听（换路由时旧实例不能继续驱动新实例的状态）
      askBus.listeners = askBus.listeners.filter(function (f) { return f !== self._askFn; });
      this._askFn = null;
    }
  };

  /* ------------------------------------------------- 语音线预留（空实现） */
  /* 站主评审【硬 2】：TTS 是烧钱端点，本轮不接。这里只把接口形状定下来：
      —— 有 phraseId 且短语库里有（voiceBank）→ 播预生成静态音频（阶段 2 的产物）
      —— 否则走"后端 TTS 转发端点"（需要三道防滥用闸；本轮该端点尚未上线。本站的发布断言会字面量扫描所有 /api/public/*，
     所以连注释里都不写它的路径。speakImpl 在本轮一律如实返回 TTS_DISABLED，绝不假装在播。 */
  /* 语音的唯一实现：实例方法与全局入口都走它（这样 🔊 按钮在"没有实例"的地方
     —— 比如页面底部输入条 —— 也能拿到同一份诚实契约）。 */
  function speakImpl(phraseId, text, cfg) {
    cfg = cfg || {};
    var bank = cfg.voiceBank || global.KURISU_VOICE_BANK || null;
    var endpoint = cfg.endpoint || global.KURISU_TTS_ENDPOINT || null;
    if (phraseId && bank && bank[phraseId]) {
      var url = joinUrl(cfg.basePath || '/', bank[phraseId]);
      try { new global.Audio(url).play(); } catch (e) { /* 浏览器可能拦截自动播放；不重试 */ }
      return Promise.resolve({ ok: true, source: 'bank', url: url });
    }
    if (endpoint) {
      return fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phraseId: phraseId || null, text: String(text || '').slice(0, 120) })
      }).then(function (r) {
        return r.ok ? { ok: true, source: 'tts' } : { ok: false, reason: 'TTS_' + r.status };
      }, function () { return { ok: false, reason: 'TTS_UNREACHABLE' }; });
    }
    return Promise.resolve({
      ok: false, reason: 'TTS_DISABLED',
      detail: '语音线尚未接入（本轮只上文本版）'
    });
  }

  /** 实例方法：语音线接入时把 opts.voiceBank / opts.ttsEndpoint 传进来即可，其它不用改。 */
  Player.prototype.speak = function (phraseId, text) {
    return speakImpl(phraseId, text, {
      voiceBank: this.opts.voiceBank || null,
      endpoint: this.opts.ttsEndpoint || null,
      basePath: this.basePath
    });
  };

  /* 历史实现，已不再调用（保留是为了让 diff 能看出语音契约是怎么从"绑在实例上"
     变成"实例与全局共用一个 speakImpl"的）。 */
  function speakLegacyNeverUsed(phraseId, text) {
    var voiceBank = this.opts.voiceBank || global.KURISU_VOICE_BANK || null;
    var endpoint = this.opts.ttsEndpoint || global.KURISU_TTS_ENDPOINT || null;
    if (phraseId && voiceBank && voiceBank[phraseId]) {
      // 阶段 2（可选）：本机离线预生成的固定语句 → 静态音频
      var url = joinUrl(this.basePath, voiceBank[phraseId]);
      if (this._audio) { this._audio.pause(); }
      this._audio = new global.Audio(url);
      this._audio.play();
      return Promise.resolve({ ok: true, source: 'bank', url: url });
    }
    if (endpoint) {
      return fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phraseId: phraseId || null, text: String(text || '').slice(0, 120) })
      }).then(function (r) { return r.ok ? { ok: true, source: 'tts' } : { ok: false, reason: 'TTS_' + r.status }; },
        function () { return { ok: false, reason: 'TTS_UNREACHABLE' }; });
    }
    return Promise.resolve({ ok: false, reason: 'TTS_DISABLED', detail: '语音线尚未接入（本轮只上文本版）' });
  };

  /* ------------------------------------------------------- 自动挂载/路由 */
  /* 不碰 app.js：自己监听路由 + 监听 #content 的子节点变化，重新扫描挂载点。 */
  var mounts = [];
  var rescanTimer = null;

  function destroyAll() {
    mounts.forEach(function (p) { try { p.destroy(); } catch (e) { /* 忽略 */ } });
    mounts = [];
  }

  function routeKey() {
    var h = (global.location.hash || '').replace(/^#/, '');
    return h.split('/')[1] || 'home';
  }

  /** 🔊 按钮的统一接线（实例内的按钮、以及页面底部输入条那颗，都用这一份）。
   *  契约：只读不写地把 TTS_DISABLED 如实写进 aria-live 节点，绝不假装在播、绝不发请求。 */
  function wireVoiceButton(btn, noteEl) {
    if (!btn || btn.getAttribute('data-xk-voice-wired')) { return; }
    btn.setAttribute('data-xk-voice-wired', '1');
    btn.setAttribute('aria-pressed', 'false');
    if (!btn.getAttribute('title')) { btn.setAttribute('title', '语音未启用（本轮只上文本版）'); }
    btn.addEventListener('click', function () {
      speakImpl(null, '', {}).then(function (r) {
        btn.setAttribute('aria-pressed', 'false');
        if (noteEl) {
          noteEl.textContent = r && r.ok
            ? '正在播放语音'
            : '语音未启用（本轮只上文本版）：' + ((r && r.reason) || 'TTS_DISABLED');
        }
      });
    });
  }

  /** 页面底部输入条：显示规则 + 提交规则。
   *  · 显示：桌面只在主页；窄屏所有栏目页都显示（AI 页除外 —— 它自己的对话输入区就是"嘴"）。
   *  · 提交：**不新增后端端点** —— 切到 AI 问答页，把文字写进那个真实的输入框，
   *    再触发同一个发送按钮，于是走的还是 POST /api/public/ask 那条既有链路。 */
  function wireBar() {
    var bar = q('[data-xk-kurisu-bar]');
    var route = routeKey();
    var narrow = mqOn(mq('(max-width: 980px)'), (global.innerWidth || 1280) <= 980);
    var on = route !== 'ai' && (narrow || route === 'home');
    var root = document.documentElement;
    if (on) { root.setAttribute('data-xk-kbar-on', '1'); } else { root.removeAttribute('data-xk-kbar-on'); }
    if (!bar) { return; }
    wireVoiceButton(q('[data-xk-kurisu-voice]', bar), q('[data-xk-kurisu-voice-note]', bar));
    if (bar.getAttribute('data-xk-kbar-wired')) { return; }
    bar.setAttribute('data-xk-kbar-wired', '1');
    bar.addEventListener('submit', function (e) {
      e.preventDefault();
      var input = q('#xk-kbar-input', bar);
      var text = (input && input.value || '').trim();
      if (!text) { if (input) { input.focus(); } return; }
      global.location.hash = '#/ai';
      var tries = 0;
      (function waitForChat() {
        var ta = q('#xk-ask-input'), run = q('[data-xk-ask-run]');
        if (ta && run) {
          ta.value = text;
          if (input) { input.value = ''; }
          try { run.click(); } catch (err) { /* 按钮可能被改；至少文字已经填进真实输入框 */ }
          return;
        }
        if (++tries > 40) { return; }     // 约 4s 后放弃（人已经停在 AI 页，可以自己按发送）
        setTimeout(waitForChat, 100);
      })();
    });
  }

  /** 从非主页路由点回主页时，<main> 外面那一层 CRT 场景并没有随 SSR 渲染出来，
   *  这里把 <template id="tpl-kurisu-stage"> 的惰性内容挂到 body 末尾（挂一次就够）。 */
  function ensureStage() {
    if (q('.xk-crt')) { return; }
    var tpl = q('#tpl-kurisu-stage');
    if (tpl && tpl.content) { document.body.appendChild(tpl.content.cloneNode(true)); }
  }

  function scan() {
    destroyAll();
    var route = routeKey();
    if (route === 'home') { ensureStage(); }
    var nodes = qa('[data-xk-kurisu]').filter(function (n) {
      // 舞台（CRT 场景）只在主页实例化：从非主页路由回主页时它才被 clone 出来；
      // 反过来在其它路由上它即使存在（display:none）也不该被实例化 ——
      // 否则会白白下载一整套角色图集（实测过：AI 页多花了 ~520KB）。
      if ((n.getAttribute('data-xk-kurisu') || '') === 'stage' && route !== 'home') { return false; }
      return true;
    });
    // 主页桌面端：把 CRT 场景层打开（CSS 只认这个开关，且只在 tech 主题 + 非窄屏生效）
    if (route === 'home') { document.documentElement.setAttribute('data-xk-crt-on', '1'); }
    else { document.documentElement.removeAttribute('data-xk-crt-on'); }
    wireBar();
    if (!nodes.length) { return; }
    nodes.forEach(function (node) {
      var mode = node.getAttribute('data-xk-kurisu') || 'auto';
      try {
        var p = new Player({
          mount: node,
          mode: mode,
          manifest: node.getAttribute('data-xk-kurisu-manifest') || DEFAULT_MANIFEST,
          basePath: node.getAttribute('data-xk-kurisu-base') || '/',
          defer: DEFAULT_DEFER_MS
        });
        mounts.push(p);
      } catch (e) { /* 单个挂载点失败不影响别人 */ }
    });

    // 规格：首屏渲染完成之后再载角色资源（延迟 200ms + 让一次空闲）
    setTimeout(function () {
      if (!mounts.length) { return; }
      whenIdle(function () {
        mounts.forEach(function (p) {
          p.ready().then(function () {
            if (p.mode === 'stage' && p.opts.autoIntro !== false) {
              return p.intro({ durationMs: 2400 }).then(function () { return p.play('idle'); });
            }
            return null;
          }).catch(function () { /* 单个模块失败不影响页面 */ });
        });
      });
    }, DEFAULT_DEFER_MS);
  }

  function scheduleScan() {
    if (rescanTimer) { return; }
    rescanTimer = setTimeout(function () { rescanTimer = null; scan(); }, 60);
  }

  function watch() {
    installAskHook();
    var host = q('#content') || document.body;
    if (global.MutationObserver && host) {
      new MutationObserver(scheduleScan).observe(host, { childList: true });
    }
    global.addEventListener('hashchange', scheduleScan, false);
    global.addEventListener('popstate', scheduleScan, false);
    scan();
  }

  /* --------------------------------------------------------------- 导出 */
  var KurisuPlayer = {
    version: VERSION,
    create: function (opts) { return new Player(opts); },
    /** 全局语音入口（页面底部输入条的 🔊 用它；语音线接入时把 bank/endpoint 传进来即可）。 */
    speak: function (phraseId, text, cfg) { return speakImpl(phraseId, text, cfg || {}); },
    boot: function () {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', watch, false);
      } else { watch(); }
      return KurisuPlayer;
    },
    // 供验收/调试用：当前挂载的实例
    instances: function () { return mounts.slice(); }
  };

  global.KurisuPlayer = KurisuPlayer;
  KurisuPlayer.boot();

})(typeof window !== 'undefined' ? window : this);
