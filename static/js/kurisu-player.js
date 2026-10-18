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
       instance.intro(opts)                   -> Promise（开场：原包现成帧序列 + 淡切到全身）
       instance.pause() / resume() / destroy()
       instance.speak(phraseId, text)         -> Promise<{ok:false, reason:'TTS_DISABLED'}>
                                                 ★ 有 text 时【同时】驱动“说话”帧动画 + 字幕（TTS 语音线另派，本轮仍是空实现）
   ============================================================================
   开场（“贴脸大头 → 拉远到全身站定”怎么做的）：
     · 帧序列**不是** transform: scale() 缩出来的 —— 全部来自原包现成序列：
       04 场景包 assets/scenarios/runtime/look_at_CRT/look_at_CRT_loop/loop/ 的 180 张 PNG
       （整段就是“贴脸靠近镜头”的成片），由 scripts/kurisu/build_intro_clip.py 打成
       full/opening.{boot,hi,poster}.webp；清单里是 clips.opening（role:"intro"、fit:"crt_screen"、
        stride=1、boot 24 帧 + hi 84 帧）。
     · 原包里【没有】“镜头拉远”的序列（39 个角色剪辑都是同一机位的全身动作：
       idle / trans_standby / speaking…）。所以开场结束后由本模块做一次 420ms 的
       淡入淡出切到 idle 全身 —— 交付报告里明说，不吹成“拉远动画”。
     · 状态行取真实数据：先从页面上真实渲染出来的节点读（其它路由 / AI 页），
       主页那些节点已经按站主要求删掉了，于是退回**自己请求** /api/public/overview
       （已上线白名单端点）；两条都取不到就如实写“读不到”，绝不编数字。
   ============================================================================ */

(function (global) {
  'use strict';

  var VERSION = '1.0.0';
  var DEFAULT_MANIFEST = '/kurisu/manifest.json';
  var DEFAULT_DEFER_MS = 200;          // 规格：首屏渲染完成之后再载角色资源
  var HI_DELAY_MS = 3000;              // hi 档最早什么时候开始补（首帧画出来起算；首屏门禁要它别抢首屏）
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

  /* ---------------------------------------------- 第二批动画的 URL 开关（T33/T34）
     口径：**不动 layouts/**（UI 批正在改）**，所有开关走查询串 + window.__xkConfig 覆盖：
       ?xk-mouth-idle=0|1            静音随机口型（默认 1）
       ?xk-blink=0|1                 眨眼（默认 1）
       ?xk-gaze=0|1                  视线跟随（默认 1）
       ?xk-blink-interval=500,3000   眨眼间隔 ms（默认 0.5~3s）
       ?xk-blink-phase=106,53,106    闭/持/开 ms（默认 E-mote「標準」档）
     reduced-motion 下：眨眼整段关闭 ✗、视线跟随只留 1/4 增益 ✓。 */
  var ANIM_FLAGS = (function () {
    var out = { mouthIdle: true, blink: true, gaze: true };
    try {
      var qs = (global.location && global.location.search) || '';
      var mm = /[?&]xk-mouth-idle=([01])/.exec(qs);
      var bb = /[?&]xk-blink=([01])/.exec(qs);
      var gg = /[?&]xk-gaze=([01])/.exec(qs);
      if (mm) { out.mouthIdle = mm[1] === '1'; }
      if (bb) { out.blink = bb[1] === '1'; }
      if (gg) { out.gaze = gg[1] === '1'; }
      var cfg = global.__xkConfig;
      if (cfg && typeof cfg === 'object') {
        if (cfg.mouthIdle != null) { out.mouthIdle = !!cfg.mouthIdle; }
        if (cfg.blink != null) { out.blink = !!cfg.blink; }
        if (cfg.gaze != null) { out.gaze = !!cfg.gaze; }
      }
    } catch (e) { /* 读不到就用默认 */ }
    return out;
  })();
  function animNum(name, dflt) {
    try {
      var m = new RegExp('[?&]' + name + '=([0-9,.]+)').exec((global.location && global.location.search) || '');
      if (!m) { return dflt; }
      var v = m[1].split(',').map(function (s) { return parseFloat(s); });
      var ok = v.length && v.every(function (x) { return isFinite(x) && x >= 0; });
      return ok ? v : dflt;
    } catch (e) { return dflt; }
  }

  /* ---------------------------------------------------- 状态机共用小工具 */
  /** 可复现的伪随机（LCG）：自动游走要"每次跑都给出同一条节点序列"才好取证。
   *  原版用的是真随机，这里的差别只在"可复现"，不影响加权掷骰子的分布。 */
  var smRngState = 20261014;
  function smSeed(s) { smRngState = (typeof s === 'number' && s) ? (s | 0) : 20261014; }
  function smRand() {
    smRngState = (smRngState * 1103515245 + 12345) & 0x7fffffff;
    return smRngState / 0x7fffffff;
  }
  /** medium 档多分页：全局帧号 → 页对象 */
  function smPageFor(pages, idx) {
    for (var i = 0; i < pages.length; i++) {
      var p = pages[i];
      if (idx >= p.first_frame - 1 && idx <= p.last_frame - 1) { return p; }
    }
    var last = pages[pages.length - 1];
    return (idx < 0) ? pages[0] : last;
  }

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

  /* ------------------------------------------- 屏内状态行的"真实数据"来源 */
  /* 主页把指标卡 / 统计节点全删了（站主：主页其它内容一个都不留），状态行不能再指望
     页面里已经有数字可读 —— 但也不许写死。这里自己请求已在白名单里的公开端点
     /api/public/overview（只读、无鉴权），把 nodes[].online 与告警窗口计数拼成人话；
     请求失败 / 超时 / 字段缺失一律退回"读不到"。60s 一次，失败也退避，不刷屏。 */
  var liveStatus = { data: null, at: 0, loading: false, failed: false };
  var LIVE_STATUS_TTL = 60000;

  function apiBaseUrl() {
    try {
      var el = document.getElementById('xk-boot');
      if (el) {
        var j = JSON.parse(el.textContent || '{}');
        if (j && j.apiBase) { return String(j.apiBase).replace(/\/+$/, ''); }
      }
    } catch (e) { /* 读不到就用相对路径 */ }
    return '';
  }

  function liveStatusTick() {
    var now = Date.now();
    if (liveStatus.loading) { return; }
    if (liveStatus.at && (now - liveStatus.at) < LIVE_STATUS_TTL) { return; }
    if (!global.fetch) { liveStatus.failed = true; liveStatus.at = now; return; }
    liveStatus.loading = true;
    fetch(apiBaseUrl() + '/api/public/overview', {
      method: 'GET', mode: 'cors', credentials: 'omit', cache: 'no-store'
    }).then(function (r) {
      if (!r.ok) { throw new Error('HTTP ' + r.status); }
      return r.json();
    }).then(function (b) {
      var d = (b && b.data) ? b.data : b;
      liveStatus.data = d || null;
      liveStatus.failed = !d;
      liveStatus.at = Date.now();
      liveStatus.loading = false;
      mounts.forEach(function (p) { try { p.refreshStatus(); } catch (e) { /* 忽略 */ } });
    }, function () {
      liveStatus.failed = true;
      liveStatus.at = Date.now();
      liveStatus.loading = false;
    });
  }

  function composeLiveStatus() {
    var d = liveStatus.data;
    if (!d) { return ''; }
    var parts = [];
    var nodes = d.nodes || [];
    nodes.slice(0, 2).forEach(function (n) {
      if (!n) { return; }
      var label = String(n.label || '节点').split('·')[0].replace(/\s+$/, '');
      parts.push(label + (n.online ? ' 在线' : ' 掉线'));
    });
    var al = d.alerts || {};
    if (al.windowCount !== null && al.windowCount !== undefined) {
      parts.push('告警窗口 ' + al.windowCount + ' 条');
    }
    if (al.high !== null && al.high !== undefined) { parts.push('高危 ' + al.high); }
    return parts.length ? parts.join(' · ') : '';
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
    if (!pairs || !pairs.length) {
      /* 主页的数据节点已经整块删掉了（站主要求）→ 退回自己请求的真实公开端点 */
      liveStatusTick();
      var live = composeLiveStatus();
      if (live) { return live; }
      if (liveStatus.loading || (!liveStatus.failed && !liveStatus.data)) { return '正在读取…'; }
      return '读不到实时数字（接口本次取不到，不补数）';
    }
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
    /* 降级：reduced-motion / saveData 只画静态一帧。
       ★ 窄屏（≤980px）**只有右栏面板**还降级（那是别的栏目页的既有行为，保持现状）；
         舞台（CRT 屏内）在窄屏上也播逐帧动画 —— 站主要"网页一进来就是这个大屏效果"。 */
    this.staticOnly = !!opts.staticOnly || this.env.reducedMotion || this.env.saveData ||
      (this.env.narrow && this.mode === 'rail');
    /* 头像形态（132px 图集）：只剩"角落点缀"、显式标了 data-xk-kurisu-avatar 的面板、
       以及窄屏右栏面板用；**舞台（CRT 屏内）永远是全身序列**，手机上也一样。 */
    this.avatarMode = this.mode === 'corner' || this.mount.hasAttribute('data-xk-kurisu-avatar') ||
      (this.env.narrow && this.mode === 'rail');
    this.avatarFrame = this.avatarMode;
    this.inactive = false;     // 挂载点不可见（display:none）时为 true：一个字节都不载
    this.canvas = q('[data-xk-kurisu-canvas]', this.mount);
    this.sayEl = q('[data-xk-kurisu-say]', this.mount);
    this.statusEl = q('[data-xk-kurisu-status]', this.mount);
    this.introEl = q('[data-xk-kurisu-intro]', this.mount);
    /* 开场序列画在**单独一层画布**上（整屏铺满），底下 idle 同时跑着：
       序列播完只要摘掉 data-xk-crt-intro，两层各做 420ms 的 opacity 过渡 = 淡切到全身。 */
    this.introCanvas = q('[data-xk-kurisu-canvas-intro]', this.mount);
    this.introCtx = null;
    this.introState = null;
    this.onceResolve = null;
    this.voiceBtn = q('[data-xk-kurisu-voice]', this.mount);
    this.emoEl = q('[data-xk-kurisu-emo]', this.mount);
    this.placeholderSay = this.sayEl ? (this.sayEl.getAttribute('data-xk-default-say') ||
      this.sayEl.textContent) : '';
    this._onVis = this.handleVisibility.bind(this);
    this._onResize = this.handleResize.bind(this);
    this._onMq = this.handleEnvChange.bind(this);
    this._askOff = null;
    /* 状态机（38 节点 / 92 边）的开关。
       ★2026-10-16（站主裁决）：**电视（rail）也要演原动画** —— 原实现硬要求 `mode==='stage'`，
       而现网 50 页挂载点全是 `rail` ⇒ 状态机永远不开，她只剩 idle 与开场（站主看到的"只有一进站的大头特效"）。
       现在：`rail` 与 `stage` 都允许，且 **rail 默认开**（电视就是她的舞台；phone 轨另算，见 §二十）。
       **一键关（三选一，任一即可）**：
         · URL 加 `?xk-sm=off`（由状态机自己的 boot 读，见该段注释）
         · `opts.stateMachine = false`
         · 构建期把 `manifest.stateMachine.auto = false`（`smOff` 会据此拦掉）
       保守边界：`prefers-reduced-motion` 时状态机自己不开（见其 boot）。 */
    var smMode = (opts.mode || this.mode);
    var smAttrOn = this.mount.getAttribute('data-xk-kurisu-sm') === 'on';
    this.smOn = (opts.stateMachine === true ||
      (opts.stateMachine !== false && (smAttrOn || smMode === 'rail'))) &&
      (smMode === 'stage' || smMode === 'rail');
    this.smTimer = null;
    this.smRunning = false;
    this.smDiag = null;
    this.graph = null;
    this._graphPromise = null;
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
    if (this.introCanvas) {
      // 开场那一层同样是装饰（真文字在字幕条里）
      this.introCanvas.setAttribute('aria-hidden', 'true');
      this.introCtx = this.introCanvas.getContext('2d');
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
    /* ★ 首屏预算与"垫板用原图"的冲突，用这一招两全：垫板 382,384 B 的原图在 markup 里只写
       data-src，首帧画出来之后（HI_DELAY_MS 同一节奏）再挂上真 src —— 首屏 1.5s 窗口里没有它，
       资产仍是作者原图、一字节没降质。 */
    var plate = q('[data-xk-plate]', this.mount);
    if (plate && plate.getAttribute('data-src')) {
      setTimeout(function () {
        if (self.destroyed || !plate.getAttribute('data-src')) { return; }
        plate.src = plate.getAttribute('data-src');
        plate.removeAttribute('data-src');
      }, HI_DELAY_MS);
    }
    this.handleResize();
  };

  Player.prototype.refreshStatus = function () {
    if (!this.statusEl || this.destroyed) { return; }
    // 舞台没有可读的真实节点（主页已删干净）→ 这里触发一次公开端点请求（TTL 内不会重复）
    if (this.mode === 'stage') { liveStatusTick(); }
    var txt = composeStatus();
    /* 事件驱动的宿主触发 · 第 3 类：**真实数据有变化**才换情绪（不编阈值、不猜严重度）。
       composeStatus() 的每个数字都来自页面上真实渲染出来的节点 / 白名单只读接口；
       文本变了 = 真实状态变了 → 推一次情绪入口。20 秒最短间隔防抖。 */
    if (this._lastStatusText && this._lastStatusText !== txt) {
      var now = Date.now();
      if (!this._lastEmotionAt || now - this._lastEmotionAt > 20000) {
        this._lastEmotionAt = now;
        this.smHostTrigger('emotion');
      }
    }
    this._lastStatusText = txt;
    if (this.statusEl.textContent !== txt) { this.statusEl.textContent = txt; }
  };

  /* 🔊 入口：本轮是空实现（语音线另派）。共用 wireVoiceButton 的诚实契约。 */
  Player.prototype.wireVoice = function () {
    wireVoiceButton(this.voiceBtn, q('[data-xk-kurisu-voice-note]', this.mount));
  };

  Player.prototype.wireEmotions = function () {
    this.wireGaze();          // T33-b：视线跟随的指针监听（挂在同一个装配点，不新开生命周期）

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

  /* 两张画布同一套尺寸（开场层 + 角色层），DRP 上限与显存上限共用一份逻辑 */
  Player.prototype.sizeCanvases = function () {
    if (!this.canvas || this.destroyed) { return null; }
    var box = this.boxSize();
    var dpr = Math.min(global.devicePixelRatio || 1, 2);
    dpr = Math.min(dpr, Math.max(1, Math.sqrt(MAX_ATLAS_PIXELS / Math.max(1, box.w * box.h))));
    var w = Math.max(1, Math.round(box.w * dpr));
    var h = Math.max(1, Math.round(box.h * dpr));
    [this.canvas, this.introCanvas].forEach(function (c) {
      if (!c) { return; }
      if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    });
    this._cssW = box.w; this._cssH = box.h;
    return { w: w, h: h };
  };

  Player.prototype.handleResize = function () {
    if (!this.canvas || this.destroyed) { return; }
    this.sizeCanvases();
    this.draw();
    this.drawIntro();
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
    if (this.mode === 'stage' && this.mount.getAttribute('data-xk-kurisu-fit') === 'source') {
      /* ★ 2026-10-14：按站主要求改用**原版源码落位公式**（docs/demo-主页.html 用的就是这一套，
         manifest.scene.character 也逐字记了它）：
           scale = min(w*0.64/764, h*0.90/1028)；x = 0.52w（再左移半个身位）；脚 = bottom − max(3, h*0.012)
         与下面 compose.charHRatio(0.66)/footYRatio(0.96) 的差别是**她在屏里更大更靠下**（0.90h vs 0.66h）
         —— 那正是 demo 的观感，所以主页舞台走这一支；其它挂载点完全不受影响。 */
      var ch = ((this.manifest || {}).scene || {}).character || {};
      var cv = ch.canvasSize || { w: 764, h: 1028 };
      var s = Math.min(bw * (ch.maxWidthRatio || 0.64) / cv.w,
                       bh * (ch.maxHeightRatio || 0.90) / cv.h);
      var dh = cv.h * s, dw = dh * aspect;
      var foot = Math.max(3, bh * (typeof ch.footRatio === 'number' ? ch.footRatio : 0.012));
      return { x: bw * (ch.xRatio || 0.52) - dw / 2, y: bh - foot - dh, w: dw, h: dh };
    }
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
    if (!atlas) { return; }
    var total = cur.frames;
    var idx;
    if (cur.fixedFrame != null) { idx = cur.fixedFrame; }
    else if (cur.once) { idx = Math.min(total - 1, Math.floor(this.elapsed / cur.interval)); }
    else { idx = Math.floor(this.elapsed / cur.interval) % total; }
    if (idx < 0) { idx = 0; }
    /* 倒放复用：只有 current.reverse 的节点（0.17.0α 的返回过渡）反向取帧。
       放在分页解析之前，多页图集也整体反序。fixedFrame 是取证/口型用的**绝对帧号**
       （smCoverage / mouthRender 直接指定），不参与反转，保持既有语义。 */
    if (cur.reverse && cur.fixedFrame == null) { idx = total - 1 - idx; }
    var img = null, cols = cur.columns, fw = cur.fw, fh = cur.fh, local = idx;
    if (atlas.pages && atlas.pages.length) {
      /* 状态机剪辑：medium 档是**多分页**图集（9 个新生成的剪辑 2~4 页）。
         全局帧号 idx → 落在哪一页 + 页内局部帧号。 */
      var pg = smPageFor(atlas.pages, idx);
      if (!pg || !pg.img) { return; }
      img = pg.img; cols = pg.cols; fw = pg.tile_w; fh = pg.tile_h;
      local = idx - (pg.first_frame - 1);
      if (local < 0) { local = 0; }
      if (local > pg.frames - 1) { local = pg.frames - 1; }
      cur.tier = 'medium';
      cur.page = pg.file || null;
    } else {
      img = atlas.hi || atlas.boot;
      if (!img) { return; }
      cur.tier = atlas.hi ? 'hi' : 'boot';   // boot → hi 平滑替换（同分辨率、帧序一致）
      // boot 图集只有前 N 帧：还没补到 hi 时用取模回绕，保证始终有画面
      if (!atlas.hi && atlas.bootFrames && idx >= atlas.bootFrames) { idx = idx % atlas.bootFrames; }
      local = idx;
      cur.page = null;
    }
    var col = local % cols;
    var row = Math.floor(local / cols);
    var cw = this.canvas.width, ch = this.canvas.height;
    // fit:"screen" / "crt_screen" = 整屏绘制（原包场景成片：房间 + 她 + 显示器边框都在帧里）
    var r = (cur.fit === 'screen' || cur.fit === 'crt_screen')
      ? { x: 0, y: 0, w: cw, h: ch } : this.charRect(cw, ch, fw / fh);
    this.ctx.clearRect(0, 0, cw, ch);
    this.ctx.imageSmoothingQuality = 'high';
    this.ctx.drawImage(img, col * fw, row * fh, fw, fh, r.x, r.y, r.w, r.h);
    if (!this._firstPaintAt) { this._firstPaintAt = Date.now(); }
    /* 叠闭嘴层：帧下标按"该剪辑自己的源帧序号"给（clips.speaking 是 stride=2 抽帧，
       所以源帧号 = 图集帧号 × 2；状态机的 medium/hi 是 stride=1，直接就是图集帧号）。 */
    var mouthClip = cur.clipName || cur.clip;
    var srcIdx = local * (MOUTH_STRIDE[cur.clip] || 1);
    this.drawMouth(r, srcIdx, mouthClip);
    /* T33-a/T33-b：眼皮补丁层 —— ★ 只叠加到输出 ✓，不写进 current/节点/边的任何字段 ✗。
       锚点按"该剪辑自己的源帧序号"给（与嘴部同一条 srcIdx 口径）。
       懒载：第一次画到支持它的剪辑时才请求一张 4KB 的小图（失败 = 永远不叠，不影响既有行为）。 */
    if (this.eyePatch && BLINK.alpha > 0) { this.drawBlink(r, mouthClip); }
    if (!this.eyePatch && !this._eyeLoading && this.current) { this.loadEye('idle1'); }
  };

  /* 开场序列：单独一条时间轴（不占 this.current，所以底下 idle 可以同时跑着）。
     绘制用 **cover**（等比放大到铺满，居中裁掉多余的边）—— 开场图集是"裁掉显示器边框后的
     屏幕内容"，它的宽高比（380×290 / 392×315）与屏幕矩形（608×500）不完全一致，
     拉伸会把人压扁，cover 只是裁掉一点边。 */
  Player.prototype.drawIntro = function () {
    if (!this.introCtx || !this.introState) { return; }
    var s = this.introState;
    var idx = Math.min(s.frames - 1, Math.floor(s.elapsed / s.interval));
    if (idx < 0) { idx = 0; }
    var col = idx % s.columns, row = Math.floor(idx / s.columns);
    var cw = this.introCanvas.width, ch = this.introCanvas.height;
    var k = Math.max(cw / s.fw, ch / s.fh);
    var dw = s.fw * k, dh = s.fh * k;
    this.introCtx.clearRect(0, 0, cw, ch);
    this.introCtx.imageSmoothingQuality = 'high';
    this.introCtx.drawImage(s.img, col * s.fw, row * s.fh, s.fw, s.fh,
      (cw - dw) / 2, (ch - dh) / 2, dw, dh);
  };

  /* ------------------------------------------------------------ 播放控制 */
  Player.prototype.tick = function (now) {
    if (this.paused || this.destroyed) { return; }
    if (!this.t0) { this.t0 = now; }
    this.elapsed = now - this.t0;
    voiceMouthTick();                      // 用真实音频播放时钟推进 mouthValue（全局一份）
    mouthIdleTick(now);                    // T34 静音随机口型（同一个 rAF）
    blinkTick(now);                       // T33-a 眨眼（只改叠加系数，不写继承状态）
    gazeApply();                           // T33-b 视线平滑（120ms 线性趋近）
    if (this.introState) { this.introState.elapsed = now - this.introState.t0; }
    this.draw();
    this.drawIntro();
    var cur = this.current;
    if (cur && cur.once && this.onceResolve && this.elapsed >= cur.interval * cur.frames) {
      var done = this.onceResolve;
      this.onceResolve = null;
      done(cur);
    }
    var s = this.introState;
    if (s && s.elapsed >= s.duration && s.onDone) {
      var f = s.onDone;
      s.onDone = null;
      f();
    }
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
    /* ★ 2026-10-14 改（首屏字节门禁）：hi 档**不许进首屏**。
       老实现是"首帧画完 + 一次空闲"就补（约 200~400ms），于是 idle.hi(1285KB) 落进 1.5s 窗口。
       现在：首帧画出来起算至少 HI_DELAY_MS(=3s)，或用户已经交互过 —— 两者先到先算。
       降级路径不变：这 3 秒里放的是 boot 24 帧（同分辨率、帧序一致）。 */
    var since = self._firstPaintAt ? (Date.now() - self._firstPaintAt) : 0;
    var wait = Math.max(0, HI_DELAY_MS - since);
    setTimeout(function () {
      if (self.destroyed) { return; }
      whenIdle(function () {
        loadImage(joinUrl(self.basePath, e.hiUrl)).then(function (img) {
          if (self.destroyed) { return; }
          e.hi = img; e.hiLoading = false;
          self.setState('tier:hi');
          self.draw();
        }, function () { e.hiLoading = false; });
      });
    }, wait);
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
      // fit:"screen" = 整屏铺满（原包场景成片）；默认 "char" = 按 charRect 站在屏幕里
      fit: spec.fit || 'char',
      // once_then_hold = 只播一遍并停在最后一帧（开场的贴脸序列就是这种）
      once: spec.loopMode === 'once_then_hold',
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
      // 换剪辑 = 时间轴从头开始（once 剪辑靠这个保证每次都从第一帧播）
      self.t0 = 0;
      self.elapsed = 0;
      self.onceResolve = null;
      self.draw();
      self.startLoop();
      self.setState('clip:' + name);
      return self.current;
    });
  };

  /** 播一个 once_then_hold 剪辑，播完（最后一帧也放完）resolve —— 开场用 */
  Player.prototype.playOnce = function (name) {
    var self = this;
    return this.play(name).then(function (cur) {
      if (!cur || !cur.once) { return cur; }
      return new Promise(function (resolve) { self.onceResolve = resolve; });
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

  /* --------------------------------------------------------- 开场（主页） */
  /* ★ 站主 2026-10-14 返工："开场贴脸→拉远→站定不要用 CSS 造假，原包里是做好的动画"。
     所以这段现在**只用原包现成的帧序列**：
       · clips.opening = 04 场景包 assets/scenarios/runtime/look_at_CRT/look_at_CRT_loop/loop/
         的 180 张 PNG（整段就是"贴脸靠近镜头"的成片），按原版 placementMode="crt_screen"
         的归一化裁剪框 [113/1398, 119/1125, 1182/1398, 902/1125] 切掉外圈玻璃，
         再拉伸进 CRT 多边形包围盒；逐帧 stride=1（第 38–43 帧那一次真眨眼因此不会被抽掉）。
         由 scripts/kurisu/build_intro_clip.py 打成 full/opening.{boot,hi,poster}.webp：
         boot 24 帧（首屏，0.28MB）+ hi 84 帧（≈2.8s，1.0MB，首帧之后后台补）。
       · 画在**单独一层画布**（.xk-kurisu__canvas--intro）上整屏铺满（cover 不拉伸）；
         底下 idle 全身同时在跑。序列播完 → 摘掉 [data-xk-crt-intro] → 两层各 420ms 互淡。
      ⚠️ 诚实声明：原包里**没有**"镜头拉远"的序列（39 个角色剪辑全是同一机位的全身动作），
         所以最后这一步是**淡入淡出**，不是 zoom。若映射表里找到真正的过渡序列，
         只要把 manifest 的 clips.<name>.role 改成 "intro"，这里一行都不用改。 */
  Player.prototype.intro = function (o) {
    o = o || {};
    var self = this;
    var m = this.manifest || {};
    var name = o.clip || introClipName(m);
    if (!name) { this.endIntro(); return Promise.resolve({ played: false, reason: 'no-intro-clip' }); }
    if (this.staticOnly || !this.introCanvas) {
      this.endIntro();
      return Promise.resolve({
        played: false,
        reason: this.staticOnly ? 'static-only(reduced-motion/saveData)' : 'no-intro-canvas'
      });
    }
    var spec = (m.clips || {})[name];
    if (!spec) { this.endIntro(); return Promise.resolve({ played: false, reason: 'no-intro-spec' }); }
    // 先挂属性（此时画布是空的、屏幕背景也收起来）—— 避免"全身先闪一下再贴脸"
    this.mount.setAttribute('data-xk-crt-intro', '1');
    this.setState('intro:loading');
    return this.ensureClip(name, true).then(function (atlas) {
      if (self.destroyed) { return { played: false, reason: 'destroyed' }; }
      if (!atlas || !atlas.boot) { self.endIntro(); return { played: false, reason: 'no-intro-atlas' }; }
      var interval = Math.max(16, spec.frameIntervalMs || 100);
      var hold = o.holdMs || 300;
      /* 开场时长：清单里可能给了 180 帧 @30fps（=6s）的完整序列，但"贴脸 → 站定"不该拖 6 秒。
         所以：先按 boot 图集能给的帧数播；hi 档到了再续上，但整体封顶 introMaxMs（默认 2800ms，
         清单可用 clips.<name>.introMaxMs 覆盖）。原包 look_at_CRT_loop 的前 ~84 帧（2.8s）就是
         "贴脸靠近"那一段，够用。 */
      var bootFrames = atlas.bootFrames || spec.frames;
      var capFrames = Math.max(1, Math.round((spec.introMaxMs || o.maxMs || 2800) / interval));
      var frames = Math.min(spec.frames, bootFrames, capFrames);
      self.introState = {
        clip: name,
        img: atlas.boot,
        frames: frames,
        maxFrames: Math.min(spec.frames, capFrames),
        columns: spec.columns || 8,
        fw: spec.frameWidth,
        fh: spec.frameHeight,
        interval: interval,
        duration: interval * frames + hold,
        hold: hold,
        hiLoading: false,
        t0: 0, elapsed: 0, onDone: null
      };
      self.setState('intro:' + name + '(' + frames + ')');
      self.startLoop();
      /* hi 档（全帧图集）后台补：到了就把开场无缝续到 maxFrames —— 不阻塞首屏，
         拿不到就播 boot 那几十帧（并如实把帧数写进 state 给取证用）。 */
      var hi = (spec.atlas || {}).hi;
      if (hi && hi.url && self.mode === 'stage' && !self.staticOnly) {
        self.introState.hiLoading = true;
        /* ★ 首屏门禁：开场 hi（1004KB）也不许落在导航后 1.5s 的窗口里。
           延迟 1.8s（1.5s 窗口 + 余量）；延迟期间播 boot 的 24 帧。 */
        setTimeout(function () {
          if (self.destroyed) { return; }
          loadImage(joinUrl(self.basePath, hi.url)).then(function (img) {
          var st = self.introState;
          if (self.destroyed || !st || st.clip !== name) { return; }
          st.img = img;
          st.frames = st.maxFrames;
          st.duration = interval * st.frames + hold;
          st.hiLoading = false;
          self.setState('intro:' + name + '(hi/' + st.frames + ')');
        }, function () {
          if (self.introState && self.introState.clip === name) { self.introState.hiLoading = false; }
        });
        }, 1800);
      }
      return new Promise(function (resolve) {
        self.introState.onDone = function () {
          var played = self.introState ? self.introState.frames : frames;
          self.endIntro();
          resolve({ played: true, clip: name, frames: played });
        };
      });
    });
  };

  /** 开场结束：摘属性 → CSS 让两层同时过渡（贴脸淡出 / 全身淡入） */
  Player.prototype.endIntro = function () {
    this.mount.removeAttribute('data-xk-crt-intro');
    this.introState = null;
    if (this.introCtx && this.introCanvas) {
      this.introCtx.clearRect(0, 0, this.introCanvas.width, this.introCanvas.height);
    }
    /* ★ demo 的 showHud()：屏内状态行与字幕条在 demo 里初始是 hidden，开场播完才出现。
       我们照这个行为（节点的初始 hidden 也照 demo 写在 partial 里）——
       状态行的**数字仍由 composeStatus() 从真实节点/白名单接口取**，取不到写"读不到"。 */
    if (this.statusEl) { this.statusEl.hidden = false; }
    var sayBox = this.sayEl && (this.sayEl.closest ? this.sayEl.closest('.crt-sub') : null);
    if (sayBox) { sayBox.hidden = false; }
    this.setState('intro:done');
  };

  /** 清单里哪个剪辑是开场：认 role:"intro"（没有就退化成"没有开场动画"，绝不用假动画顶替） */
  function introClipName(m) {
    var clips = (m && m.clips) || {};
    var names = Object.keys(clips);
    for (var i = 0; i < names.length; i++) {
      if (clips[names[i]] && clips[names[i]].role === 'intro') { return names[i]; }
    }
    return null;
  }

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
      /* ★T4：声音开 + 已有手势才念那一句日语；任何一环不满足就只留上面这行中文字幕。
         字幕（setSay）与回答正文、状态码都不受语音成败影响。 */
      var ja = (data && typeof data.speakJa === 'string') ? data.speakJa : '';
      if (ja) { speakJaSay(ja); }
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

  /* 注：尺寸计算已经统一到 sizeCanvases()（上面那份定义才是生效的实现）。 */
  Player.prototype.handleResize = function () {
    if (!this.canvas || this.destroyed) { return; }
    this.sizeCanvases();
    this.draw();
    this.drawIntro();
  };

  Player.prototype.handleEnvChange = function () {
    var env = probeEnv();
    var wasStatic = this.staticOnly;
    this.env = env;
    this.staticOnly = !!this.opts.staticOnly || env.reducedMotion || env.saveData ||
      (env.narrow && this.mode === 'rail');
    if (this.staticOnly && !wasStatic) {
      this.smStop();
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
    this.smStop();
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
    var base = cfg.basePath || '/';
    var endpoint = cfg.endpoint || global.KURISU_TTS_ENDPOINT || null;
    var viaEndpoint = function () {
      if (!endpoint) { return null; }
      return fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phraseId: phraseId || null, text: String(text || '').slice(0, 120) })
      }).then(function (r) {
        return r.ok ? { ok: true, source: 'tts' } : { ok: false, reason: 'TTS_' + r.status };
      }, function () { return { ok: false, reason: 'TTS_UNREACHABLE' }; });
    };
    /* L1：固定台词走离线静态音频（bank.json）。带 autoplay 门控。 */
    if (phraseId) {
      return playLine(base, phraseId, text).then(function (r) {
        if (r.ok || r.reason === 'AUTOPLAY_BLOCKED') { return r; }
        var ep = viaEndpoint();          // 这句没有预生成音频时，才退到后端 TTS
        if (ep) { return ep; }
        return { ok: false, reason: r.reason || 'NO_SUCH_LINE', id: phraseId,
                 detail: '该短语没有 L1 音频（本轮只上固定台词）' };
      });
    }
    var ep2 = viaEndpoint();
    if (ep2) { return ep2; }
    return Promise.resolve({
      ok: false, reason: 'TTS_DISABLED',
      detail: '这一路没有短语 id（L1 只覆盖固定台词；自由回答的语音线尚未接入）'
    });
  }

  /** 实例方法：语音线接入时把 opts.voiceBank / opts.ttsEndpoint 传进来即可，其它不用改。
   *  ★ 本轮扩展：有 text 时**同时**驱动"说话"帧动画 + 屏内字幕条（站主要求
   *  "说话时嘴在动且字幕同步"），播完自动回 idle 并在一会儿后还原默认字幕。
   *  TTS 本身仍是空实现（speakImpl 如实返回 TTS_DISABLED），两边不互相假装。 */
  Player.prototype.speak = function (phraseId, text) {
    var said = (text == null) ? '' : String(text);
    var self = this;
    var label = this.mouthLabelFor((this.current && (this.current.clipName || this.current.clip)) ||
      this.currentClipName || 'speaking');
    if (label) { this.loadMouth(label); }
    if (said) { this.animateSpeech(said); }
    /* ★ 事件驱动的宿主触发：有台词/有音频在播 → 推 speaking 入口（原版 prob=0 只能宿主走） */
    if (phraseId) { this.smHostTrigger('voice'); }
    return speakImpl(phraseId, said, {
      voiceBank: this.opts.voiceBank || null,
      endpoint: this.opts.ttsEndpoint || null,
      basePath: this.basePath
    }).then(function (r) {
      if (!said && r && r.text) { self.animateSpeech(r.text); }   // 用 L1 台词文本补字幕
      return r;
    });
  };

  /** 说话：切 speaking 帧序列（嘴在动）+ 字幕同步显示同一段文本。
   *  时长按字数估（每字 260ms，2.6s–12s），字幕跟着这条时间轴走。 */
  Player.prototype.animateSpeech = function (text, opts) {
    opts = opts || {};
    var self = this;
    var chars = String(text || '').length;
    var dur = opts.durationMs || Math.max(2600, Math.min(12000, chars * 260));
    this.showSubtitle(text);
    this.emotionVariant = 'speaking';
    if (!this.staticOnly) { this.play('speaking'); }
    if (this._speakTimer) { clearTimeout(this._speakTimer); }
    if (this._restoreTimer) { clearTimeout(this._restoreTimer); }
    this._speakTimer = setTimeout(function () {
      if (self.destroyed) { return; }
      self.emotionVariant = 'idle';
      if (!self.staticOnly) { self.play('idle'); }
      self._restoreTimer = setTimeout(function () {
        if (!self.destroyed) { self.restoreSubtitle(); }
      }, 6000);
    }, dur);
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

  /* ==================================================================== 语音 L1
     规格：docs/动画与语音实现规格-给外部AI.md §3.3（autoplay 门控）+ §4（口型两层）。
     机制逐条照抄：
       · 未交互态 = 动画与字幕照常、**声音静默**（绝不调 Audio.play()），并显式给"🔊 点我开声"
       · 首次 pointerdown / keydown / touchstart → 解锁；解锁后**补放**被拦下的那一句
       · mouthValue = clamp(RMS(10ms 窗) × 3.75, 0, 1)；首窗保底 0.12；停止发 0（离线算好存 JSON）
       · 静音（mouthValue ≤ 0.08）时叠"闭嘴层"；说话中用基础帧自带的嘴
     与本项目实际的一处**必要差异**（如实记录）：
       上游 `shouldClose = !speaking || mouthValue <= 0.08` 里的 speaking 是"她在说话这个状态"，
       因为上游没声音时不会停在说话剪辑上；我们这里**没有**语音也会自动游走到说话剪辑
       （37/87 状态机 + 还没接 L2），照抄会让她全程闭着嘴。
       所以本实现改成：**只有音频真的在播（VOICE.speaking）时才挂嘴罩**；没声音就退回
       "字幕 + 帧里自带的嘴"（= 规格 §3.1 的 L3 降级），这正是规格 §4 末行写的那种观感。 */
  var VOICE = {
    bank: null, bankLoading: null, unlocked: false,
    /* ★T3（语音接线，2026-10-16）：原声优先索引 `voice/bank-merged.origfirst.json`。
       **按需取**：只有"声音开关已开、且真的要播某一句"时才会 fetch（默认关声 ⇒ 一个字节都不取），
       一次会话只取一次。它是"id → 文件"的**唯一真值来源**。 */
    index: null, indexLoading: null,
    audio: null, line: null, envelope: null, speaking: false, mouthValue: 0,
    pending: null, last: null,
    variant: 'auto',        // 'auto' = 按每个 label 的 preferredVariant；'patch' / 'frame' = 强制
    diag: {
      unlockedBy: null, blockedPlays: 0, plays: 0, lastLine: null,
      mouthShown: 0, mouthHidden: 0, variant: 'patch', bankLines: 0, errors: [],
      /* ★T3 取证字段（探针/自证用，不上屏）：索引条数、本次取到的文件与来源、只见字幕的次数 */
      indexIds: 0, indexKind: null, indexUrl: null, subtitleOnly: 0
    }
  };

  function voiceBankUrl(basePath) {
    return joinUrl(basePath || '/', 'kurisu/voice/bank.json');
  }
  function loadVoiceBank(basePath) {
    if (VOICE.bank) { return Promise.resolve(VOICE.bank); }
    if (VOICE.bankLoading) { return VOICE.bankLoading; }
    VOICE.bankLoading = fetch(voiceBankUrl(basePath), { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) { throw new Error('voice bank HTTP ' + r.status); } return r.json(); })
      .then(function (b) {
        VOICE.bank = b;
        VOICE.diag.bankLines = Object.keys(b.lines || {}).length;
        return b;
      });
    return VOICE.bankLoading;
  }

  /* ====================================================== ★T3 · 原声优先接线（语音线，2026-10-16）
     口径**逐字**来自 `voice/bank-merged.origfirst.json` 的 note 字段：
       「前端唯一查找表：按 id 命中后，**优先用 orig（原声）**；没有 orig 再用 synth；两者都无 ⇒ 只出字幕。」
     设计取舍（如实记录，供复核）：
       · **分辨率**（id → 文件）以 merged 索引为唯一真值；**选择**（说哪一句 = pickLine）仍读 `bank.json`，
         因为 merged 的条目只有 {id, trigger, orig/synth{audio,envelope,text,webm}}，
         **没有 emotion / group / scene / tags / seconds / question** —— 选择层要用这些字段，
         改它就会改变"她说什么话"（不是本次授权的范围）✗
       · 取索引失败（404/网络抖动）⇒ **退回接线前的 bank.json 解析**（`playLineLegacy`），并如实记账；
         绝不因为索引拿不到就静音或报错刷屏 ✓
       · 索引里既无 orig 也无 synth ⇒ **只出字幕**（`NO_AUDIO_FOR_LINE`），不假装有声 ✓ */
  function voiceIndexUrl(basePath) {
    return joinUrl(basePath || '/', 'kurisu/voice/bank-merged.origfirst.json');
  }
  function loadVoiceIndex(basePath) {
    if (VOICE.index) { return Promise.resolve(VOICE.index); }
    if (VOICE.indexLoading) { return VOICE.indexLoading; }
    VOICE.indexLoading = fetch(voiceIndexUrl(basePath), { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) { throw new Error('voice index HTTP ' + r.status); } return r.json(); })
      .then(function (j) {
        VOICE.index = (j && j.lookup) || {};
        VOICE.diag.indexIds = Object.keys(VOICE.index).length;
        return VOICE.index;
      });
    return VOICE.indexLoading;
  }
  /** 按 id 命中后：orig（原声）优先 → 再 synth → 都没有返回 null（调用方只出字幕） */
  function resolveVoiceEntry(index, id) {
    var rec = index && index[id];
    if (!rec) { return null; }
    var sub = rec.orig || rec.synth || null;
    if (!sub || !sub.audio) { return null; }
    return { id: id, kind: rec.orig ? 'orig' : 'synth', trigger: rec.trigger || '',
             audio: sub.audio, envelope: sub.envelope || '', seconds: sub.seconds, text: sub.text || '' };
  }
  /** 见上：索引里 synth 条目不写 seconds；若 bank.json 已因选择层load过，就白捡它的值（不再多发请求） */
  function legacySeconds(id) {
    var rec = (VOICE.bank && VOICE.bank.lines) ? VOICE.bank.lines[id] : null;
    return rec ? rec.seconds : undefined;
  }
  function loadEnvelope(basePath, url) {
    return fetch(joinUrl(basePath || '/', url), { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) { throw new Error('envelope HTTP ' + r.status); } return r.json(); });
  }

  /* ============================================ ★T4 · 自由回答的日语语音线（2026-10-18）
     背景：后端 `/api/public/ask` 现在按需多给一个 `speakJa`（≤40 字的日语口语，中文字幕不变）。
     前端只负责"念出来"，并且**宁可不响，也不乱响**：
       · 声音开关默认关，且**只在访客自己点过 🔊 之后**才可能出第一声（VOICE.unlocked = 手势闸）；
       · 关声 / 没手势 / 响应里没有 speakJa ⇒ 纯字幕，连 `/tts/say` 都不请求（不花额度、不占带宽）；
       · 拿到了但 play() 被浏览器拦 ⇒ 静默降级，在字幕旁写「声音被浏览器拦截，点一下再试」，绝不假装在播；
       · 口型复用现成的 VOICE.speaking（playVoiceNow 播时置真、ended 复位），不新增一套状态。
     为什么挂 window.__xkSpeakJa：app.js 是另一支脚本，发问前要判断"这趟要不要 speakJa"，
     两支脚本之间只靠这个全局通信（不依赖加载顺序：两边都是用到时才读）。 */
  var SPEAK = { on: false };
  try { global.__xkSpeakJa = SPEAK; } catch (e) { /* 忽略 */ }

  function speakJaWanted() {
    try {
      if (global.__xkSound && global.__xkSound.on === false) { return false; }
      return !!SPEAK.on;
    } catch (e) { return false; }
  }
  /** 🔊 那颗按钮在"开声模式"下由这里独占写状态（aria-pressed = 声音开没开，而不是"解锁没解锁"） */
  function refreshSpeakButtons() {
    var btns = qa('[data-xk-kurisu-voice]');
    for (var i = 0; i < btns.length; i++) {
      var b = btns[i];
      if (!b.getAttribute('data-xk-speak-ja')) { continue; }
      b.setAttribute('aria-pressed', SPEAK.on ? 'true' : 'false');
      b.setAttribute('title', SPEAK.on
        ? '声音已开：点一下关声（只留中文字幕）'
        : '点我开声：之后每题念一句日语（中文字幕照旧）');
      /* 静态文案写的是"语音（未启用）"（当时确实没接）。现在接上了就必须如实翻面，
         否则界面在说谎 —— 只改这一个按钮的可见文字，字幕与回答正文一个字都不动。 */
      b.textContent = SPEAK.on ? '🔊 语音（已开·点我关）' : '🔊 语音（点我开声）';
    }
  }

  /** 念一句 speakJa。所有失败都在这里安静收口，返回 { ok, reason }，绝不抛。 */
  function speakJaSay(ja) {
    var text = String(ja == null ? '' : ja).replace(/^\s+|\s+$/g, '');
    if (!text) { return Promise.resolve({ ok: false, reason: 'NO_TEXT' }); }
    if (!speakJaWanted()) {
      VOICE.diag.blockedPlays++;
      return Promise.resolve({ ok: false, reason: 'SOUND_OFF' });
    }
    if (!VOICE.unlocked) {
      /* 没手势：只留字幕。把这句话记下来 —— 访客随后点 🔊 就能补上这一句 */
      VOICE.pendingSpeak = text;
      VOICE.diag.subtitleOnly++;
      voiceNote('声音要在你点一下之后才会出：点 🔊 再试（字幕已在上面）。');
      return Promise.resolve({ ok: false, reason: 'AUTOPLAY_BLOCKED' });
    }
    var ctrl = (typeof AbortController === 'function') ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) { ctrl.abort(); } }, 12000);
    return fetch(apiBaseUrl() + '/api/public/tts/say', {
      method: 'POST', mode: 'cors', credentials: 'omit', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      signal: ctrl ? ctrl.signal : undefined,
      body: JSON.stringify({ text: text })
    }).then(function (r) {
      clearTimeout(timer);
      if (!r.ok) { throw new Error('HTTP ' + r.status); }
      return r.blob();
    }).then(function (blob) {
      var url = URL.createObjectURL(blob);
      if (VOICE.speakJaUrl) { try { URL.revokeObjectURL(VOICE.speakJaUrl); } catch (e) { /* 忽略 */ } }
      VOICE.speakJaUrl = url;
      setTimeout(function () { try { URL.revokeObjectURL(url); } catch (e) { /* 忽略 */ } }, 30000);
      VOICE.diag.lastSpeakJa = text;
      var ok = playVoiceNow({ id: 'speak-ja', url: url, envelope: null },
        '声音被浏览器拦截，点一下再试。');
      return { ok: ok, reason: ok ? null : 'PLAY_FAILED', source: 'tts-say', text: text };
    }).catch(function (err) {
      clearTimeout(timer);
      VOICE.diag.errors.push('speak-ja: ' + (err && err.message));
      VOICE.diag.subtitleOnly++;
      return { ok: false, reason: 'TTS_FAILED' };
    });
  }

  function voiceNote(text) {
    VOICE.diag.lastNote = text;
    var els = qa('[data-xk-kurisu-voice-note]');
    for (var i = 0; i < els.length; i++) { els[i].textContent = text; }
  }
  /** 未交互态必须能从界面上看出来："🔊 点我开声"（站主要求的显式入口） */
  function refreshVoiceButtons() {
    var btns = qa('[data-xk-kurisu-voice]');
    for (var i = 0; i < btns.length; i++) {
      var b = btns[i];
      /* 开声模式的那颗（AI 页右栏 🔊）状态由 refreshSpeakButtons 独占写，这里不碰 */
      if (b.getAttribute('data-xk-speak-ja')) { continue; }
      b.setAttribute('aria-pressed', VOICE.unlocked ? 'true' : 'false');
      b.setAttribute('title', VOICE.unlocked ? '声音已开：点一下重播最近一句' : '浏览器会拦自动播放：点我开声');
      var lab = q('[data-xk-voice-label]', b);
      if (lab) { lab.textContent = VOICE.unlocked ? '已开声' : '点我开声'; }
    }
  }

  function unlockAudio(how) {
    if (VOICE.unlocked) { return; }
    VOICE.unlocked = true;
    VOICE.diag.unlockedBy = how || 'unknown';
    refreshVoiceButtons();
    voiceNote('声音已开（' + VOICE.diag.unlockedBy + '）。');
    var p = VOICE.pending;
    VOICE.pending = null;
    if (p) { playVoiceNow(p); }
  }
  function installAudioGate() {
    if (installAudioGate.done) { return; }
    installAudioGate.done = true;
    ['pointerdown', 'keydown', 'touchstart'].forEach(function (ev) {
      global.addEventListener(ev, function () { unlockAudio(ev); }, { passive: true });
    });
    refreshVoiceButtons();
    voiceNote('浏览器会拦自动播放：点 🔊 或按任意键开声（动画与字幕不受影响）。');
  }

  function playVoiceNow(line, blockedNote) {
    if (!line || !line.url) { return false; }
    try {
      if (VOICE.audio) { try { VOICE.audio.pause(); } catch (e) { /* 忽略 */ } }
      var a = new global.Audio(line.url);
      a.preload = 'auto';
      VOICE.audio = a;
      VOICE.line = line.id;
      VOICE.envelope = line.envelope || null;
      VOICE.speaking = true;
      VOICE.mouthValue = 0;
      VOICE.diag.plays++;
      VOICE.diag.lastLine = line.id;
      VOICE.diag.envelopeLen = VOICE.envelope && VOICE.envelope.values ? VOICE.envelope.values.length : 0;
      /* ⚠️ 只有"当前这一条"的事件才能改全局状态：换句子时旧 Audio 会以 AbortError 结束，
         不过滤的话旧的 catch 会把新句子的 speaking 直接打成 false（实测踩过）。 */
      var isCurrent = function () { return VOICE.audio === a; };
      /* 口型的 mouthValue 是在 tick() 里按音频播放时钟算的 —— 所以播语音时必须保证
         舞台的帧循环在跑（默认它就在跑；这里兜住"循环被别处停掉"的情况，不新开第二个循环）。 */
      for (var mi = 0; mi < mounts.length; mi++) {
        var mp = mounts[mi];
        if (mp.mode === 'stage' && !mp.staticOnly && !mp.paused && !mp.destroyed && !mp.raf) {
          mp.startLoop();
        }
      }
      a.addEventListener('ended', function () {
        if (!isCurrent()) { return; }
        VOICE.speaking = false; VOICE.mouthValue = 0;
        VOICE.diag.mouthHidden++;
      });
      var pr = a.play();
      if (pr && pr.catch) {
        pr.catch(function (err) {
          if (!isCurrent()) { return; }
          VOICE.speaking = false;
          VOICE.diag.errors.push('play: ' + (err && err.name));
          VOICE.diag.blockedPlays++;
          VOICE.pending = line;
          voiceNote(blockedNote || '浏览器拦下了播放：点 🔊 开声。');
        });
      }
      return true;
    } catch (e) {
      VOICE.diag.errors.push('audio: ' + e.message);
      return false;
    }
  }

  /* ============================================================ 选句器（防复读）· 2026-10-15 窗口 B 接线准备件
     问题：`playLine(basePath, id, text)` 只会"按 id 直取"。线上真正反复触发的入口（导航、状态、兜底）
     如果都写死同一个 id，访客听到的永远是**同一句** —— 台词库再大也没用 ✗。
     做法（与窗口 T 的 `docs/台词选句与防复读规则-20261015.md` 对齐）：
       ① 语义筛子集：ctx.emotion / ctx.tags 命中才留在候选里（**正确性压过多样性** ✓）
       ② 排除最近 N 条已播（N = min(4, 组内条数-1)），保证短时间内不复读
       ③ 剩余候选上按 w = 1/(1+近 20 次出现次数) 加权随机
       ④ 组里只有 1 条时不假装随机，如实记 noAlternative（窗口 T 规则 R4 ✓）
     降级链（任一步空集都往下退，绝不因为"想不重复"而卡住不出声 ✗）：
       排除最近 N → 空 ⇒ 只排除最近 1 → 仍空 ⇒ 用全组并记 diag。
     ⚠️ 只决定"选哪一条"，**不改 playLine 按 id 取音频的既有契约** ✗。 */
  var PICK = {
    key: 'xk-line-recent-v1',
    windowN: 4,
    weightWindow: 20,
    recent: null,
    counts: null,
    diag: { picks: 0, noAlternative: 0, byGroup: {}, fallbackLevel: {}, lastPick: null }
  };
  function pickLoadState() {
    if (PICK.recent) { return; }
    PICK.recent = {}; PICK.counts = {};
    try {
      var raw = global.localStorage && global.localStorage.getItem(PICK.key);
      if (raw) {
        var o = JSON.parse(raw);
        if (o && typeof o === 'object') {
          PICK.recent = (o.recent && typeof o.recent === 'object') ? o.recent : {};
          PICK.counts = (o.counts && typeof o.counts === 'object') ? o.counts : {};
        }
      }
    } catch (e) { /* 隐私模式/配额：退回内存态，不影响出声 */ }
  }
  function pickSaveState() {
    try {
      if (!global.localStorage) { return; }
      /* 只存 id（窗口 T 口径：不存文本/时间戳/用户标识 ⇒ 无隐私面 ✓） */
      global.localStorage.setItem(PICK.key, JSON.stringify({ recent: PICK.recent, counts: PICK.counts }));
    } catch (e) { /* 存不下不影响本次会话的选择 */ }
  }
  /* ★T3：**选择层**（说哪一句）仍读 `bank.json` —— 它带 emotion / group / scene / tags / seconds /
     question 这些选择要用的字段，而 merged 索引的条目只有 {id, trigger, orig/synth{audio,envelope,text,webm}}。
     分辨率（id → 文件）已改走 merged 索引（见 playLine）。若哪天要把选择层也换成 merged，
     必须先把上述字段补进 merged —— 那属于改数据/改"她说什么话"，不在本次授权范围 ✗ */
  function pickBankLines(basePath) {
    if (VOICE.bank) { return Promise.resolve(VOICE.bank.lines || {}); }
    return loadVoiceBank(basePath).then(function (b) { return (b && b.lines) || {}; });
  }
  /** 从组里挑一条。返回 {ok,id,group,level,candidates,subset}。
   *  group = trigger 组名；ctx.preferId 指定首选 id（导航页用），它必须属于该组 ✓。 */
  function pickLine(basePath, group, ctx) {
    ctx = ctx || {};
    return pickBankLines(basePath).then(function (lines) {
      if (!lines) { return { ok: false, reason: 'BANK_UNAVAILABLE', group: group }; }
      var all = [];
      for (var id in lines) {
        if (!Object.prototype.hasOwnProperty.call(lines, id)) { continue; }
        var rec = lines[id] || {};
        if ((rec.trigger || rec.group || '') !== group) { continue; }
        all.push(id);
      }
      if (!all.length) { return { ok: false, reason: 'NO_SUCH_GROUP', group: group }; }
      pickLoadState();
      /* ⓪ 指定优先 id（导航用）：规则是"点导航到某页 ⇒ 播该页 nav_*"，
         这是**语义要求**不是"随机里偏好"，所以硬返回它 ✓（但照样记账，权重窗口继续演进 ✓） */
      if (ctx.preferId && all.indexOf(ctx.preferId) >= 0) {
        var pre = PICK.recent[group] || [];
        pre.unshift(ctx.preferId);
        if (pre.length > PICK.weightWindow) { pre.length = PICK.weightWindow; }
        PICK.recent[group] = pre;
        var pc = PICK.counts[group] || {};
        pc[ctx.preferId] = (pc[ctx.preferId] || 0) + 1;
        PICK.counts[group] = pc;
        pickSaveState();
        PICK.diag.picks++;
        PICK.diag.byGroup[group] = (PICK.diag.byGroup[group] || 0) + 1;
        PICK.diag.fallbackLevel[0] = (PICK.diag.fallbackLevel[0] || 0) + 1;
        PICK.diag.lastPick = { group: group, id: ctx.preferId, level: 0, prefer: true };
        return { ok: true, id: ctx.preferId, group: group, level: 0, prefer: true };
      }
      /* ① 语义筛子集 */
      var subset = all.filter(function (id) {
        var rec = lines[id] || {};
        if (ctx.emotion) {
          var e = rec.emotion || '';
          if (e !== ctx.emotion && !(ctx.emotion === 'calm' && e === '')) { return false; }
        }
        if (ctx.tags && ctx.tags.length) {
          var tags = rec.tags || [];
          var hit = false;
          for (var i = 0; i < ctx.tags.length; i++) {
            if (tags.indexOf(ctx.tags[i]) >= 0) { hit = true; break; }
          }
          if (!hit) { return false; }
        }
        return true;
      });
      if (!subset.length) { subset = all; }   /* 语义筛空 ⇒ 宁用全组，也不出声失败 ✓ */
      /* ④ 单条组：不假装随机 */
      if (subset.length === 1) {
        PICK.diag.picks++; PICK.diag.noAlternative++;
        PICK.diag.byGroup[group] = (PICK.diag.byGroup[group] || 0) + 1;
        PICK.diag.lastPick = { group: group, id: subset[0], level: 3, noAlternative: true };
        return { ok: true, id: subset[0], group: group, level: 3, noAlternative: true };
      }
      var recent = (PICK.recent[group] || []);
      var nEff = Math.min(PICK.windowN, subset.length - 1);
      /* ② 排除最近 N（降级链） */
      var cand = subset.filter(function (id) { return recent.slice(0, nEff).indexOf(id) < 0; });
      var level = 1;
      if (!cand.length) {
        cand = subset.filter(function (id) { return recent.slice(0, 1).indexOf(id) < 0; });
        level = 2;
      }
      if (!cand.length) { cand = subset; level = 3; }
      /* ③ 加权随机 */
      var cnt = PICK.counts[group] || {};
      var weights = cand.map(function (id) { return 1 / (1 + (cnt[id] || 0)); });
      var total = weights.reduce(function (a, b) { return a + b; }, 0);
      var r = smRand() * total;
      var chosen = cand[cand.length - 1];
      for (var k = 0; k < cand.length; k++) {
        r -= weights[k];
        if (r <= 0) { chosen = cand[k]; break; }
      }
      recent.unshift(chosen);
      if (recent.length > PICK.weightWindow) { recent.length = PICK.weightWindow; }
      PICK.recent[group] = recent;
      cnt[chosen] = (cnt[chosen] || 0) + 1;
      var seenTotal = recent.reduce(function (a, x) { return a + (cnt[x] || 0); }, 0);
      if (seenTotal > PICK.weightWindow * 2) {
        for (var cid in cnt) { cnt[cid] = Math.floor(cnt[cid] / 2); }
      }
      PICK.counts[group] = cnt;
      pickSaveState();
      PICK.diag.picks++;
      PICK.diag.byGroup[group] = (PICK.diag.byGroup[group] || 0) + 1;
      PICK.diag.fallbackLevel[level] = (PICK.diag.fallbackLevel[level] || 0) + 1;
      PICK.diag.lastPick = { group: group, id: chosen, level: level,
                             candidates: cand.length, subset: subset.length };
      return { ok: true, id: chosen, group: group, level: level,
               candidates: cand.length, subset: subset.length };
    });
  }
  /** 按组播一句：先选句、再走既有 playLine（音频仍只取这一句 ✓） */
  function speakGroup(basePath, group, ctx) {
    return pickLine(basePath, group, ctx).then(function (pick) {
      if (!pick || !pick.ok) { return pick || { ok: false, reason: 'PICK_FAILED' }; }
      return playLine(basePath, pick.id, (ctx && ctx.text) || '').then(function (r) {
        return { ok: !!(r && (r.ok || r.reason === 'AUTOPLAY_BLOCKED')), reason: r && r.reason,
                 id: pick.id, group: group, level: pick.level, source: 'bank' };
      });
    });
  }

  /* ============================================================ 导航板块语音（四页 ⇒ nav_*）
     线上四个可导航板块：home / monitor / notes / ai（`xk-dock.html`、`xk-navpill.html` 的
     data-xk-nav，与 app.js 的 NAV_OF_ROUTE 一致）。nav_labs / nav_about **已随页面删除作废** ✗。
     触发：监听 hashchange（**不改 app.js** ✗ —— app.js 才是 SPA 外壳的写入者），
     把 #/monitor/... 映射成板块名，再走 speakGroup('page_intro', {preferId})。
     去抖：同一板块 10 分钟内不重复（sessionStorage 记，刷新不清零）。 */
  var NAV_VOICE = { map: { home: 'nav_home', monitor: 'nav_monitor', notes: 'nav_notes', ai: 'nav_ai', what: 'nav_what', lab: 'nav_lab' },
                    key: 'xk-nav-voice-at', dedupMs: 10 * 60 * 1000 };
  function navVoiceSection() {
    var h = (global.location && global.location.hash) || '';
    var p = (global.location && global.location.pathname) || '/';
    var m = /^#\/([a-z]+)/.exec(h);
    var name = m ? m[1] : '';
    if (!name) {
      if (/^\/ai\b/.test(p)) { name = 'ai'; }
      else if (/^\/alerts\b/.test(p)) { name = 'monitor'; }
      else if (/^\/posts\b/.test(p)) { name = 'notes'; }
      else if (p === '/' || /^\/index\.html$/.test(p)) { name = 'home'; }
    }
    var id = NAV_VOICE.map[name];
    return id ? { name: name, id: id } : null;
  }
  function navVoicePlay() {
    var sec = navVoiceSection();
    if (!sec) { return; }
    var now = Date.now(), last = 0, lastSec = '';
    try {
      var raw = global.sessionStorage && global.sessionStorage.getItem(NAV_VOICE.key);
      if (raw) { var o = JSON.parse(raw); last = o.at || 0; lastSec = o.section || ''; }
    } catch (e) { /* 忽略 */ }
    if (lastSec === sec.name && (now - last) < NAV_VOICE.dedupMs) { return; }
    try {
      if (global.sessionStorage) {
        global.sessionStorage.setItem(NAV_VOICE.key, JSON.stringify({ section: sec.name, at: now }));
      }
    } catch (e) { /* 忽略 */ }
    speakGroup('/', 'page_intro', { preferId: sec.id }).then(function (r) {
      VOICE.diag.lastNav = { section: sec.name, id: (r && r.id) || sec.id, ok: !!(r && r.ok) };
    });
  }
  global.addEventListener('hashchange', navVoicePlay);

  /** 播一句 L1 台词：走**原声优先索引**（`bank-merged.origfirst.json`）；索引拿不到就退回 bank.json；
      两者都没有这一句 ⇒ 只出字幕（L3 降级，绝不假装有声） */
  function playLine(basePath, id, text) {
    /* ★批次A（2026-10-16 站主）：全站**唯一的声音闸门**是左上角头像卡那颗 🔊, 默认关。
       关着的时候：一不出声、二**连 bank.json / 索引都不取**（既省首屏字节，也保证"没开声就不播"这条
       口径只有一个落点）。开关打开那一刻由头像卡派发 `xk-sound` 事件，各页自己把压下的那一句补播。 */
    if (global.__xkSound && !global.__xkSound.on) {
      VOICE.diag.blockedPlays = (VOICE.diag.blockedPlays || 0) + 1;
      return Promise.resolve({ ok: false, reason: 'SOUND_OFF', id: id,
                               detail: '声音开关默认关（左上角 🔊 打开）' });
    }
    /* ★T3：按 id 命中 → **优先 orig（原声）** → 再 synth → 都没有 ⇒ 只出字幕。 */
    return loadVoiceIndex(basePath).then(function (index) {
      var e = resolveVoiceEntry(index, id);
      if (!e) {
        VOICE.diag.subtitleOnly++;
        VOICE.diag.errors.push('no-audio: ' + id);
        voiceNote('这句没有可播的音频（原声与合成都没有）—— 只出字幕，不假装有声。');
        return { ok: false, reason: 'NO_AUDIO_FOR_LINE', subtitleOnly: true, id: id,
                 indexHit: !!(index && index[id]),
                 detail: '索引里这条既无 orig 也无 synth ⇒ 只出字幕' };
      }
      var seconds = (e.seconds != null) ? e.seconds : legacySeconds(id);
      var line = { id: id, url: joinUrl(basePath || '/', e.audio), text: text || e.text || '',
                   kind: e.kind, seconds: seconds };
      return loadEnvelope(basePath, e.envelope).then(function (env) {
        line.envelope = env;
        VOICE.last = line;
        VOICE.diag.indexKind = e.kind;
        VOICE.diag.indexUrl = line.url;
        if (!VOICE.unlocked) {
          VOICE.pending = line;
          VOICE.diag.blockedPlays++;
          voiceNote('动画与字幕照常；声音被浏览器的自动播放策略拦住了 —— 点 🔊 或按任意键开声。');
          return { ok: false, reason: 'AUTOPLAY_BLOCKED', needGesture: true, id: id,
                   url: line.url, kind: e.kind, envelopeValues: (env.values || []).length };
        }
        var ok = playVoiceNow(line);
        return { ok: ok, source: (e.kind === 'orig' ? 'bank-orig' : 'bank-synth'), id: id, url: line.url,
                 kind: e.kind, seconds: seconds, envelopeValues: (env.values || []).length };
      }, function (envErr) {
        /* ④ 降级：包络拿不到（404/网络抖动）也**只出字幕**，不报错刷屏、不假装在播 ✓
           （voiceMouthTick 对 null envelope 已有兜底：退回"帧里自带的嘴"） */
        VOICE.diag.errors.push('envelope: ' + id);
        VOICE.last = line;
        if (!VOICE.unlocked) { VOICE.pending = line; return { ok: false, reason: 'AUTOPLAY_BLOCKED', id: id }; }
        return { ok: !!playVoiceNow(line), source: 'bank-no-envelope', id: id, kind: e.kind,
                 seconds: seconds, envelopeValues: 0, envelopeMissing: true };
      });
    }, function (err) {
      /* 索引拿不到 ⇒ **退回接线前的 bank.json 解析**（行为与接线前一致），如实记账 */
      VOICE.diag.errors.push('index-fallback: ' + (err && err.message));
      return playLineLegacy(basePath, id, text);
    });
  }

  /** ★T3 之前的老解析路径（读 `bank.json`）。现在只在**索引取不到**时兜底，行为逐字保留。 */
  function playLineLegacy(basePath, id, text) {
    return loadVoiceBank(basePath).then(function (bank) {
      var rec = (bank.lines || {})[id];
      if (!rec) { return { ok: false, reason: 'NO_SUCH_LINE', id: id }; }
      var line = { id: id, url: joinUrl(basePath || '/', rec.audio), text: rec.text || text || '',
                   kind: 'legacy' };
      return loadEnvelope(basePath, rec.envelope).then(function (env) {
        line.envelope = env;
        VOICE.last = line;
        if (!VOICE.unlocked) {
          VOICE.pending = line;
          VOICE.diag.blockedPlays++;
          voiceNote('动画与字幕照常；声音被浏览器的自动播放策略拦住了 —— 点 🔊 或按任意键开声。');
          return { ok: false, reason: 'AUTOPLAY_BLOCKED', needGesture: true, id: id,
                   url: line.url, envelopeValues: (env.values || []).length };
        }
        var ok = playVoiceNow(line);
        return { ok: ok, source: 'bank', id: id, url: line.url,
                 seconds: rec.seconds, envelopeValues: (env.values || []).length };
      }, function (envErr) {
        VOICE.diag.errors.push('envelope: ' + id);
        VOICE.last = line;
        if (!VOICE.unlocked) { VOICE.pending = line; return { ok: false, reason: 'AUTOPLAY_BLOCKED', id: id }; }
        return { ok: !!playVoiceNow(line), source: 'bank-no-envelope', id: id,
                 seconds: rec.seconds, envelopeValues: 0, envelopeMissing: true };
      });
    }, function (err) {
      return { ok: false, reason: 'BANK_UNAVAILABLE', detail: String(err && err.message) };
    });
  }

  /* ------------------------------------------ T34 · 静音随机口型（输出叠加层）
     站主口径：idle 系列在**无语音**时叠小幅随机口型 —— 幅度 ≤0.25、间隔 0.4~1.5s 随机、
     `?xk-mouth-idle=0` 可关。三条规则：① 说话中不叠 ✗；② 闭嘴层只在 openness ≤0.08 时叠 ✓
     （沿用现有阈值）；③ 本层是**输出叠加**，不写进任何被继承的状态 ✗（没有任何节点/边字段读它）。
     随机用独立 LCG —— 不复用状态机的种子流，免得打乱既有取证序列。 */
  var MOUTH_IDLE = {
    on: true, speaking: false, value: 0, peak: 0, nextAt: 0, blinks: 0,
    rng: 20261015, minMs: 400, maxMs: 1500, maxOpen: 0.25, source: 'none'
  };
  function miRand() {
    MOUTH_IDLE.rng = (MOUTH_IDLE.rng * 1103515245 + 12345) & 0x7fffffff;
    return MOUTH_IDLE.rng / 0x7fffffff;
  }
  MOUTH_IDLE.on = !!ANIM_FLAGS.mouthIdle;
  /** 每帧调用：与 voiceMouthTick 共用同一个 rAF，不新开循环 */
  function mouthIdleTick(nowMs) {
    if (!MOUTH_IDLE.on) { MOUTH_IDLE.value = 0; MOUTH_IDLE.source = 'off'; return 0; }
    if (VOICE.speaking) {                       // ① 说话中不叠 ✗
      MOUTH_IDLE.speaking = true;
      MOUTH_IDLE.value = 0;
      MOUTH_IDLE.source = 'voice';
      return 0;
    }
    if (MOUTH_IDLE.speaking) {                  // 刚停：重置节拍，避免立刻弹一张嘴
      MOUTH_IDLE.speaking = false;
      MOUTH_IDLE.value = 0;
      MOUTH_IDLE.peak = 0;
      MOUTH_IDLE.nextAt = nowMs + 260;
      MOUTH_IDLE.source = 'idle';
      return 0;
    }
    if (!MOUTH_IDLE.nextAt) { MOUTH_IDLE.nextAt = nowMs + 400 + miRand() * 1100; }
    if (nowMs >= MOUTH_IDLE.nextAt) {
      MOUTH_IDLE.blinks++;
      MOUTH_IDLE.peak = 0.12 + miRand() * 0.13;                // ≈0.12~0.25 ≤ 0.25 ✓
      MOUTH_IDLE.value = MOUTH_IDLE.peak;
      if (MOUTH_IDLE.value <= 0.08) { MOUTH_IDLE.value = 0; }   // ② 阈值以下不叠 ✓
      MOUTH_IDLE.nextAt = nowMs + MOUTH_IDLE.minMs + miRand() * (MOUTH_IDLE.maxMs - MOUTH_IDLE.minMs);
    }
    MOUTH_IDLE.source = 'idle';
    return MOUTH_IDLE.value;
  }
  /** 闭嘴层实际用的值：说话中用语音包络、静音用随机口型 */
  function mouthEffective() {
    if (VOICE.speaking) { return VOICE.mouthValue; }
    return MOUTH_IDLE.on ? MOUTH_IDLE.value : 0;
  }

  /* ---------------------------------------- T33-a · 眨眼（眼皮补丁层，只叠加输出）
     ★ 硬纪律（`docs/素材与资料复查-20261015.md` §借 E-mote 笔记 规则 6）：
       眨眼/口型**只叠加到输出、不写进继承状态** ✗ —— 否则基线被顶到"闭眼档"，
       眼睛会递归自锁。本实现里眨眼唯一的跨帧状态是 BLINK.alpha（每帧现算、可归零），
       它**不参与**剪辑/节点/边的任何选择，也**没有任何字段被继承** ✓。
     参数 = E-mote blinkParameter「標準」档：闭 106ms / 保持 53ms / 开 106ms，
       间隔 0.5~3s 随机；?xk-blink-phase / ?xk-blink-interval 可调（六档预设见 eye json）。
     素材：static/kurisu/eye/<label>.json + eyes.closed.webp（与 mouth 补丁同构）。 */
  var BLINK = {
    on: true, state: 'idle', phase: 0, alpha: 0, nextAt: 0, count: 0,
    closeMs: 106, holdMs: 53, openMs: 106, minMs: 500, maxMs: 3000,
    clamps: 0
  };
  BLINK.on = !!ANIM_FLAGS.blink;
  (function () {
    var ph = animNum('xk-blink-phase', [106, 53, 106]);
    if (ph.length === 3) { BLINK.closeMs = ph[0]; BLINK.holdMs = ph[1]; BLINK.openMs = ph[2]; }
    var iv = animNum('xk-blink-interval', [500, 3000]);
    if (iv.length === 2) { BLINK.minMs = iv[0]; BLINK.maxMs = iv[1]; }
    try {
      var c = global.__xkConfig || {};
      if (c.blinkPhaseMs && c.blinkPhaseMs.length === 3) {
        BLINK.closeMs = c.blinkPhaseMs[0]; BLINK.holdMs = c.blinkPhaseMs[1]; BLINK.openMs = c.blinkPhaseMs[2];
      }
      if (c.blinkIntervalMs && c.blinkIntervalMs.length === 2) {
        BLINK.minMs = c.blinkIntervalMs[0]; BLINK.maxMs = c.blinkIntervalMs[1];
      }
    } catch (e) { /* 忽略 */ }
  })();
  function blinkInterval() { return BLINK.minMs + smRand() * Math.max(0, BLINK.maxMs - BLINK.minMs); }
  function blinkTick(nowMs) {
    if (!BLINK.on || (BLINK.closeMs + BLINK.holdMs + BLINK.openMs) <= 0) {
      BLINK.alpha = 0; BLINK.state = BLINK.on ? 'none' : 'off'; return 0;
    }
    if (!BLINK.nextAt) { BLINK.nextAt = nowMs + 800 + smRand() * 900; return 0; }
    if (BLINK.state === 'idle') {
      BLINK.alpha = 0;
      if (nowMs >= BLINK.nextAt) { BLINK.state = 'closing'; BLINK.phase = nowMs; }
      /* ★ 下一次眨眼**只在"开"结束后**才重摇间隔（不等就摇会在睁到一半时又闭，观感抽搐） */
      return 0;
    }
    var e = nowMs - BLINK.phase;
    if (BLINK.state === 'closing') {
      BLINK.alpha = BLINK.closeMs > 0 ? Math.min(1, e / BLINK.closeMs) : 1;
      if (e >= BLINK.closeMs) { BLINK.state = 'hold'; BLINK.phase = nowMs; BLINK.alpha = 1; }
      return BLINK.alpha;
    }
    if (BLINK.state === 'hold') {
      BLINK.alpha = 1;
      if (e >= BLINK.holdMs) { BLINK.state = 'opening'; BLINK.phase = nowMs; }
      return 1;
    }
    BLINK.alpha = BLINK.openMs > 0 ? Math.max(0, 1 - e / BLINK.openMs) : 0;
    if (e >= BLINK.openMs) {
      BLINK.state = 'idle'; BLINK.alpha = 0; BLINK.count++;
      BLINK.nextAt = nowMs + blinkInterval();
    }
    return BLINK.alpha;
  }
  /** 该剪辑戴不戴眼皮补丁（同机位同脸位白名单；侧脸族/闭眼族/默认 idle 不在内） */
  /* --------------------------------- T33-b · 视线跟随（鼠标 / 触摸）
     照抄 E-mote `demo/app.mjs` L111-125 的手感，只换"基准点"的来源：
       eyeX/eyeY = [(pointer / canvasRect) − 眼睛在画布上的归一化位置] × gain200 → clamp ±100
       再用 120ms 线性平滑（= 原版 setVariableDiff 的"独立差分通道"，与状态机完全解耦 ✓）
     基准点**不写死**：优先 manifest.scene.character.eyeAnchor；没有就按
       compose.charHRatio / footYRatio + 实测眼带纵向比例 0.35 现算 ⇒ 换视图/换取景不用改代码。
     实测依据：idle1 源坐标眼带 y=(102.6+250.9)/2=176.8，脚踩点 1028×0.96 ⇒ 0.35 档位吻合 ✓ */
  var GAZE = { on: true, x: 0, y: 0, tx: 0, ty: 0, gain: 200, clamp: 100, smoothMs: 120,
               level: 0, at: 0 };
  GAZE.on = !!ANIM_FLAGS.gaze;
  (function () {
    try {
      var c = global.__xkConfig || {};
      if (c.gazeGain != null) { GAZE.gain = c.gazeGain; }
      if (c.gazeClamp != null) { GAZE.clamp = c.gazeClamp; }
      if (c.gazeSmoothMs != null) { GAZE.smoothMs = c.gazeSmoothMs; }
    } catch (e) { /* 忽略 */ }
  })();
  function gazeReduced() {
    try { return mqOn(mq('(prefers-reduced-motion: reduce)'), false); } catch (e) { return false; }
  }
  /** 眼睛在画布上的归一化位置（不写死坐标；能从 manifest 取就从 manifest 取） */
  Player.prototype.eyePoint = function () {
    var cw = this.canvas ? this.canvas.width : 0;
    var ch = this.canvas ? this.canvas.height : 0;
    if (!cw || !ch) { return { x: 0.5, y: 0.35 }; }
    var e = (this.manifest && this.manifest.scene && this.manifest.scene.character
             && this.manifest.scene.character.eyeAnchor) || null;
    if (e && typeof e.x === 'number' && typeof e.y === 'number') { return { x: e.x, y: e.y }; }
    var r = this.charRect(cw, ch, this.aspect || 1);
    var comp = ((this.manifest || {}).scene || {}).compose || {};
    var hr = (typeof comp.charHRatio === 'number') ? comp.charHRatio : 0.66;
    var fy = (typeof comp.footYRatio === 'number') ? comp.footYRatio : 0.96;
    var eyeYRatio = 0.35;      // 实测：眼带中心 ≈ 脚踩点上方 0.35×角色高（见上方推导）
    return { x: (r.x + r.w / 2) / cw, y: (r.y + r.h * (fy - hr * eyeYRatio)) / ch };
  };
  Player.prototype.gazeSetFromPointer = function (clientX, clientY) {
    if (!GAZE.on || !this.canvas) { return null; }
    var rect = this.canvas.getBoundingClientRect ? this.canvas.getBoundingClientRect() : null;
    if (!rect || !rect.width || !rect.height) { return null; }
    var eye = this.eyePoint();
    var gain = GAZE.gain * (gazeReduced() ? 0.25 : 1);
    var cl = GAZE.clamp;
    GAZE.tx = Math.max(-cl, Math.min(cl, ((clientX - rect.left) / rect.width - eye.x) * gain));
    GAZE.ty = Math.max(-cl, Math.min(cl, ((clientY - rect.top) / rect.height - eye.y) * gain));
    GAZE.at = Date.now();
    return { x: GAZE.tx, y: GAZE.ty, eye: eye };
  };
  /** 每帧线性趋近（16.7ms/rAF ⇒ 120ms 到位，与 E-mote 的 120ms 平滑同量级） */
  function gazeApply() {
    if (!GAZE.on) { GAZE.x = 0; GAZE.y = 0; GAZE.level = 0; return 0; }
    var k = Math.min(1, 16.7 / Math.max(1, GAZE.smoothMs));
    GAZE.x += (GAZE.tx - GAZE.x) * k;
    GAZE.y += (GAZE.ty - GAZE.y) * k;
    GAZE.level = Math.min(1, Math.abs(GAZE.x) / Math.max(1, GAZE.clamp));
    return GAZE.level;
  }
  Player.prototype.wireGaze = function () {
    var self = this;
    if (!GAZE.on || !this.mount || this._gazeWired) { return; }
    this._gazeWired = true;
    this._onPointerMove = function (ev) { if (ev) { self.gazeSetFromPointer(ev.clientX, ev.clientY); } };
    this._onPointerLeave = function () { GAZE.tx = 0; GAZE.ty = 0; };
    this.mount.addEventListener('pointermove', this._onPointerMove, false);
    this.mount.addEventListener('pointerdown', this._onPointerMove, false);
    this.mount.addEventListener('pointerleave', this._onPointerLeave, false);
  };
  /* 视线 → 状态机的"转向偏置"：|x| > 60% 量程时，把**同一个侧脸族内部**的边连续加权
     （**不改 prob 的存储值**、不改字段语义 ✓；只是同一个数在掷骰子时乘一个 1.0~3.0 的系数）。
     只在用户真的把指针伸到边上时生效；没有指针事件时 level=0 ⇒ 系数恒 1
     ⇒ 行为与接线前**逐位一致** ✓ */
  var GAZE_STEER = {
    idle_side_wind: ['idle_side_soft_wind', 'idle_side_butterfly'],
    idle_side_soft_wind: ['idle_side_wind', 'idle_side_butterfly'],
    idle_side_butterfly: ['idle_side_wind', 'idle_side_soft_wind']
  };
  function gazeSteerMultiplier(from, to) {
    if (!GAZE.on || GAZE.level <= 0.6) { return 1; }
    var list = GAZE_STEER[from];
    if (!list || list.indexOf(to) < 0) { return 1; }
    return 1 + 2 * ((GAZE.level - 0.6) / 0.4);
  }

  function blinkAllowedOn(clipName, d) {
    if (!d) { return true; }
    var n = clipName || '';
    var allow = d.compatibleClips || null;
    if (allow && allow.length) { return allow.indexOf(n) >= 0; }
    var skip = d.skipPrefixes || [];
    for (var i = 0; i < skip.length; i++) { if (n.indexOf(skip[i]) === 0) { return false; } }
    return true;
  }
  Player.prototype.blinkAllowed = function (clipName) {
    return blinkAllowedOn(clipName, this.eyeData);
  };

  /** 用真实音频的播放时钟推进 mouthValue（包络是离线算好的 10ms 栅格，客户端零算力） */
  /* 口型取证出口的开关：**惰性判定一次，默认关**（与 window.__xkSm 同口径：只读、取证才开）。
     打开方式（二选一）：URL 加 `?xk-voice-diag=1`，或页面里先设 `window.__xkVoiceOn = true`。
     为什么要它：口型的"逻辑对齐"是构造性的（见下方契约），但**渲染出来的口型**只能
     用"音频时刻 ↔ 口型值 ↔ 当前句 id"三件套去端到端测（渲染栅格 / 动画帧对齐）。
     不打开时本函数不做任何额外工作（零开销）。
     ★命名教训（2026-10-16）：出口名**不能用 `__xkVoice`** —— 那个全局已被
     `layouts/partials/xk-demo/shell-script.html:827` 的 `window.__xkVoice = XKV`（语音子系统状态）占用。
     故本出口命名为 `__xkVoiceTick`。 */
  /* ★注意（2026-10-16 修）：**只记忆化 URL 判据，不记忆化 `__xkVoiceOn`**
     —— 否则页面启动时若先跑过一次 tick（此时 URL 无参数、`__xkVoiceOn` 还没被探针设上），
     就会把"关"缓存成永久 false，探针事后设 `__xkVoiceOn = true` 再也打不开
     （T5 报告里"先设 __xkVoiceOn=true 再 speak 仍 ABSENT"就是这个原因）。 */
  var forensicVoiceUrl = null;
  function forensicVoiceOn() {
    if (global.__xkVoiceOn) { return true; }
    if (forensicVoiceUrl === null) {
      forensicVoiceUrl = !!(global.location && /[?&]xk-voice-diag=1/.test(global.location.search || ''));
    }
    return forensicVoiceUrl;
  }
  function voiceMouthTick() {
    if (!VOICE.speaking || !VOICE.audio) {
      if (forensicVoiceOn()) { publishVoiceDiag(0, 0); }
      return VOICE.mouthValue;
    }
    var env = VOICE.envelope;
    if (env && env.values && env.values.length) {
      var hop = env.hopMs || 10;
      var i = Math.floor((VOICE.audio.currentTime || 0) * 1000 / hop);
      if (i < 0) { i = 0; }
      var v = env.values[i];
      if (typeof v !== 'number') { v = 0; }
      /* T8-b 契约（写死在这里，避免再漂）：mouthValue = clamp(envelope.values[floor((t−t0)/10ms)] × 3.75, 0, 1)
         首窗保底 0.12；包络值是 0~1 的 RMS，3.75 是把"正常说话"铺满 0~1 的实测增益。
         floor(t/10ms) 就是对 hopMs 栅格取整 —— 逐帧锚点定位，**不写死任何坐标** ✓ */
      var contracted = Math.min(1, Math.max(0, v * 3.75));
      VOICE.mouthValue = (VOICE.speaking && VOICE.mouthValue === 0 && i === 0)
        ? Math.max(0.12, contracted) : contracted;
    }
    if (VOICE.audio.ended || VOICE.audio.paused) { VOICE.speaking = false; VOICE.mouthValue = 0; }
    if (forensicVoiceOn()) {
      publishVoiceDiag((VOICE.audio && VOICE.audio.currentTime) || 0, VOICE.mouthValue);
    }
    return VOICE.mouthValue;
  }

  /* 复用同一个对象，避免逐帧新建造成 GC 抖动；字段含义：
     t = 音频播放时刻(秒) ｜ mouth = 本次算出的口型值 ｜ clip = 正在播的句 id ｜ hopMs = 包络栅格 ｜
     speaking = 是否在说话 ｜ at = 发布时刻(ms)，供探针对齐 rAF 时间戳
     ★对象**只在开关打开时才创建**（默认 `typeof window.__xkVoiceTick === 'undefined'`，与"默认关、零开销"口径一致） */
  function publishVoiceDiag(t, mouth) {
    var d = global.__xkVoiceTick || (global.__xkVoiceTick = { t: 0, mouth: 0, clip: null, hopMs: null, speaking: false, at: 0 });
    d.t = t;
    d.mouth = mouth;
    d.clip = (VOICE.line && (VOICE.line.id || VOICE.line.label)) || null;
    d.hopMs = (VOICE.envelope && VOICE.envelope.hopMs) || null;
    d.speaking = !!VOICE.speaking;
    d.at = (global.performance && global.performance.now) ? global.performance.now() : Date.now();
  }

  /* ============================================================ 状态机
     37 节点 / 87 边 —— 原版 graph_config.json 的机械提取，构建期落在
     static/kurisu/statemachine.json（docs/ 下的原始副本不进产物；manifest.stateMachine.url 指过去）。
     机制照抄原版（docs/amadeus-research/HOW-IT-WORKS.md）：
       · 出边按 prob 归一化后掷骰子。原图里 trans_standby 的正概率出边和 = 0.4、
         speaking_med = 1.2 —— 归一化正好抹平这个不一致；这是原版数据的现状，不改它。
       · prob = 0 的 9 条边 = 宿主触发入口（host_triggered_entries）：自动游走**不掷**它们，
         由宿主按事件触发。这里做成"每隔 hostTriggerEveryMs 插一次情绪入口"（原版的
         "宿主"就是页面/用户，本模块只是把宿主换成定时器，语义与原版一致）。
       · once_then_hold：播一遍并在最后一帧停住，然后按出边继续。
       · 帧推进仍然是 tick() 里那**同一个** rAF + 时间累加，不新开循环、不用 setInterval 做帧循环。
     资产：每个节点只发 medium 一档（48.15MB / 49 页），懒载 + 只留当前剪辑一个
     （idle_closed_eye 4 页 = 约 96MB 解码位图，多留一份就可能吃满内存）。
     诊断钩子（给验收脚本与站主演示用，不参与渲染）：
       window.__xkSm = { seed, seq:[{clip,tMs,holdMs,frames,pages}], edges:[], visited:{}, errors:[] }
     —— 测试/取证才显式开：挂载点属性 data-xk-kurisu-sm="on"（或 manifest.stateMachine.auto=true）。
     默认**不自动开**：37 段 medium 全量懒载约 48MB，按每节点 ~2.6s 的节奏，一次 60s 的访问
     会多拉 ~28MB —— 这是有代价的行为，必须由页面显式决定（见 docs/交接-P0第一阶段-20261014.md）。 */

  var SM_MIN_HOLD_MS = 900;
  var SM_MAX_HOLD_MS = 2600;      // 单节点驻留上限（否则 idle_closed_eye 12.5s 会卡住整段游走）
  var SM_DEFAULT_TRIGGER_MS = 7000;
  /* 带宽闸：一次访问里状态机最多拉多少字节的图集，超了就停在新节点上继续播（不回退、不报错）。
     36 段 medium 全量是 48MB —— 不设闸的话一次 2 分钟的访问能拉 50MB+，
     对 GitHub Pages 的流量额度和访客流量都不友好。默认 6MB ≈ 5 段左右。 */
  var SM_DEFAULT_MAX_BYTES = 6 * 1024 * 1024;
  /* 宿主触发的三类事件各自的入口剪辑（原版 `host_triggered_entries` 的 9 个按语义分组） */
  var HOST_ENTRIES_BY_REASON = {
    voice: ['speaking_trans', 'speaking_short'],
    emotion: ['angry_trans', 'sad_trans', 'surprise_trans', 'shy_trans', 'trans_smile'],
    idle: ['closed_eye_trans']
  };
  /* 自动巡演（兜底节拍）时轮着来，保证三类宿主事件都能被观测到 */
  var SM_CADENCE_REASONS = ['voice', 'emotion', 'idle'];

  Player.prototype.loadGraph = function () {
    var self = this;
    if (this._graphPromise) { return this._graphPromise; }
    var m = this.manifest || {};
    var url = (m.stateMachine && m.stateMachine.url) || 'kurisu/statemachine.json';
    this._graphPromise = fetch(joinUrl(this.basePath, url), { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) { throw new Error('statemachine HTTP ' + r.status); }
        return r.json();
      })
      .then(function (g) {
        if (!g || !g.nodes || !g.edges) { throw new Error('statemachine 结构不对'); }
        self.graph = g;
        self.graphByClip = {};
        for (var i = 0; i < g.nodes.length; i++) { self.graphByClip[g.nodes[i].clip] = g.nodes[i]; }
        self.smOut = {};
        self.smIn = {};
        for (var j = 0; j < g.edges.length; j++) {
          var e = g.edges[j];
          (self.smOut[e.from] = self.smOut[e.from] || []).push(e);
          (self.smIn[e.to] = self.smIn[e.to] || []).push(e);
        }
        return g;
      });
    return this._graphPromise;
  };

  /** 加权掷骰子：只在 prob > 0 的出边上归一化（prob=0 的宿主入口不参与） */
  Player.prototype.smPick = function (clip) {
    var out = (this.smOut && this.smOut[clip]) || [];
    var pos = [];
    var i, sum = 0;
    for (i = 0; i < out.length; i++) { if (out[i].prob > 0) { pos.push(out[i]); sum += out[i].prob; } }
    if (!pos.length) { return null; }
    var r = smRand() * sum;
    for (i = 0; i < pos.length; i++) {
      r -= pos[i].prob * gazeSteerMultiplier(clip, pos[i].to);
      if (r <= 0) { return pos[i]; }
    }
    return pos[pos.length - 1];
  };

  /** hi 档该不该用：hi 的 tile 是 medium 的 2 倍（268×360 vs 134×180），
   *  解码位图是 4 倍。只在画布背板 ≥480px（桌面档的 CRT 屏）时才值 ——
   *  窄屏屏宽 ~380px、角色 ~243px，medium 的 1.8× 放大还能接受，不必付 4 倍内存。 */
  Player.prototype.smUseHi = function (node) {
    if (!node || !node.hi || !node.hi.pages || !node.hi.pages.length) { return false; }
    if (this.staticOnly) { return false; }
    var w = (this.canvas && this.canvas.width) || 0;
    return w >= 480;
  };

  /** 载入一个状态机节点的图集（medium 或 hi，可能 2~4 页）。只保留当前这一个剪辑。
   *  别名节点（node.atlas_clip）与源剪辑共用同一个缓存键：同一张图只下载一次、只解码一次
   *  ——0.17.0α 的返回过渡 key_point_to_thinking 就是 thinking_to_key_point 的倒放，走这条路。 */
  Player.prototype.ensureMediumClip = function (node) {
    var self = this;
    var key = 'sm:' + (node.atlas_clip || node.clip);
    var have = this.atlases[key];
    if (have && have.pages) { return Promise.resolve(have); }
    var useHi = this.smUseHi(node);
    var pages = (useHi && node.hi && node.hi.pages) ? node.hi.pages : node.medium.pages;
    var tier = useHi ? 'hi' : 'medium';
    var chain = Promise.resolve([]);
    pages.forEach(function (p) {
      chain = chain.then(function (acc) {
        if (self.destroyed) { throw new Error('destroyed'); }
        return loadImage(joinUrl(self.basePath, p.url)).then(function (img) {
          acc.push({
            img: img, file: p.file, url: p.url, cols: p.cols, rows: p.rows, frames: p.frames,
            first_frame: p.first_frame, last_frame: p.last_frame,
            tile_w: p.tile_w, tile_h: p.tile_h, bytes: p.bytes
          });
          return acc;
        });
      });
    });
    return chain.then(function (imgs) {
      if (self.destroyed) { throw new Error('destroyed'); }
      var e = { clip: key, pages: imgs, tier: tier, bytes: node.medium.bytes,
        boot: null, hi: null, bootFrames: node.frames };
      self.atlases[key] = e;
      self.smEvict(key);
      return e;
    });
  };

  /** 状态机模式下的内存回收：只留 keep 这一个剪辑（clips.* 那几段也一起摘掉） */
  Player.prototype.smEvict = function (keep) {
    var self = this;
    Object.keys(this.atlases).forEach(function (k) {
      if (k === keep) { return; }
      var e = self.atlases[k];
      if (!e) { return; }
      if (e.pages) {
        e.pages.forEach(function (pg) { try { pg.img.src = ''; } catch (err) { /* 忽略 */ } });
      }
      if (e.boot) { try { e.boot.src = ''; } catch (err2) { /* 忽略 */ } }
      if (e.hi) { try { e.hi.src = ''; } catch (err3) { /* 忽略 */ } }
      delete self.atlases[k];
    });
  };

  /** 把一个状态机节点变成 current（几何全部来自节点里的 medium 分页元数据） */
  Player.prototype.smSetCurrent = function (node, atlas) {
    var p0 = atlas.pages[0];
    this.current = {
      clip: 'sm:' + (node.atlas_clip || node.clip),
      clipName: node.clip,
      frames: node.frames,
      columns: p0.cols,
      fw: p0.tile_w,
      fh: p0.tile_h,
      interval: Math.max(16, node.frameIntervalMs || 42),
      tier: 'medium',
      fit: 'char',
      once: node.loopMode === 'once_then_hold',
      /* 倒放复用（0.17.0α 新增的返回过渡 key_point_to_thinking）：
         图集是正向那张（atlas_clip），播放时把帧序反过来取 —— 不新增任何素材字节。
         其余节点没有这个字段，行为完全不变。 */
      reverse: !!node.reverse,
      fixedFrame: null,
      page: null,
      smNode: node
    };
    this.currentClipName = 'sm:' + node.clip;
    this.t0 = 0;
    this.elapsed = 0;
    this.onceResolve = null;
    this.draw();
    this.startLoop();
    this.setState('sm:' + node.clip);
  };

  /** 单节点驻留时长：loop 取一整圈但封顶 SM_MAX_HOLD_MS；once_then_hold 取整段 */
  function smHoldMs(node) {
    var full = node.frames * Math.max(16, node.frameIntervalMs || 42);
    if (node.loopMode === 'once_then_hold') { return Math.min(full, SM_MAX_HOLD_MS * 2); }
    return Math.max(SM_MIN_HOLD_MS, Math.min(full, SM_MAX_HOLD_MS));
  }

  /** 播一个状态机节点（载入 → 换 current → 记诊断） */
  Player.prototype.smPlayNode = function (clip) {
    var self = this;
    var node = this.graphByClip && this.graphByClip[clip];
    if (!node) { return Promise.reject(new Error('状态机里没有节点 ' + clip)); }
    return this.ensureMediumClip(node).then(function (atlas) {
      if (self.destroyed) { return null; }
      self.smSetCurrent(node, atlas);
      if (self.smDiag) {
        self.smDiag.seq.push({
          clip: clip, tMs: Date.now() - self.smDiag.startedAt, holdMs: smHoldMs(node),
          frames: node.frames, frameIntervalMs: node.frameIntervalMs,
          loopMode: node.loopMode, pages: atlas.pages.length, tier: atlas.tier,
          bytes: atlas.pages.reduce(function (s, p) { return s + p.bytes; }, 0)
        });
        self.smDiag.visited[clip] = (self.smDiag.visited[clip] || 0) + 1;
      }
      return node;
    });
  };

  /** 宿主触发入口（原版语义：prob=0 的边**只有宿主能走**，概率游走永远不选它们）。
   *  实测：只按正概率出边走，2000 步只覆盖 9/37 个节点，全困在 idle 变体簇里 ——
   *  她永远不说话、不换表情。所以"宿主"必须真的存在：
   *    voice   播一句台词 / 事件播报 → speaking 入口
   *    emotion 真实数据有变化（状态行文本变了）→ 情绪入口
   *    idle    长时间待机 → thinking_* / idle_closed_eye / closed_eye_trans
   *    cadence 自动巡演时的兜底节拍（保证取证时一定能看到宿主触发） */
  Player.prototype.smHostTrigger = function (reason, entries) {
    if (!this.smOn) { return false; }
    this.smPending = this.smPending || [];
    var entry = this.smHostEntryFor(reason, entries);
    if (!entry) { return false; }
    this.smPending.push({ reason: reason || 'host', entry: entry, tMs: Date.now() });
    return true;
  };

  /** 按"宿主事件类型"挑入口剪辑（都要真在状态机里，否则退回全部宿主入口） */
  Player.prototype.smHostEntryFor = function (reason, entries) {
    var self = this;
    var list = (entries && entries.length) ? entries
      : (HOST_ENTRIES_BY_REASON[reason] || ((this.graph && this.graph.host_triggered_entries) || []));
    var ok = [];
    for (var i = 0; i < list.length; i++) {
      if (!this.graphByClip || this.graphByClip[list[i]]) { ok.push(list[i]); }
    }
    if (!ok.length) { ok = (this.graph && this.graph.host_triggered_entries) || []; }
    if (!ok.length) { return null; }
    // 尽量不连着挑同一个入口（否则时间线看着像卡了）
    var pick = ok[Math.floor(smRand() * ok.length) % ok.length];
    if (ok.length > 1 && pick === self._lastHostEntry) {
      pick = ok[(ok.indexOf(pick) + 1) % ok.length];
    }
    self._lastHostEntry = pick;
    return pick;
  };

  /** 自动游走：按加权出边一段一段播下去。
   *  opts = { durationMs: 30000（0=不限）, hostTriggerEveryMs, seed, stopAfterNodes } */
  Player.prototype.smStart = function (opts) {
    opts = opts || {};
    var self = this;
    if (this.smTimer || this.smRunning) { return Promise.resolve(this.smDiag); }
    var duration = (typeof opts.durationMs === 'number') ? opts.durationMs : 30000;
    var triggerMs = (typeof opts.hostTriggerEveryMs === 'number') ? opts.hostTriggerEveryMs : SM_DEFAULT_TRIGGER_MS;
    var m2 = this.manifest || {};
    var maxBytes = (typeof opts.maxBytes === 'number') ? opts.maxBytes
      : ((m2.stateMachine && typeof m2.stateMachine.maxWalkBytes === 'number')
        ? m2.stateMachine.maxWalkBytes : SM_DEFAULT_MAX_BYTES);
    if (typeof opts.seed === 'number') { smSeed(opts.seed); }
    this.smRunning = true;
    this.smDiag = {
      seed: smRngState, durationMs: duration, hostTriggerEveryMs: triggerMs, maxBytes: maxBytes,
      startedAt: Date.now(), seq: [], edges: [], visited: {}, errors: [], bytes: 0,
      hostTimeline: [], nodeCount: 0, edgeCount: 0, stoppedBy: null
    };
    global.__xkSm = this.smDiag;
    var hostEntries = (this.graph && this.graph.host_triggered_entries) || [];
    var started = Date.now();
    var lastTrigger = started;
    var cadenceIdx = 0;

    return this.loadGraph().then(function (g) {
      self.smDiag.nodeCount = g.node_count;
      self.smDiag.edgeCount = g.edge_count;
      self.smDiag.root = g.root;
      var cur = g.root || 'idle';
      if (opts.startClip && self.graphByClip[opts.startClip]) { cur = opts.startClip; }
      return new Promise(function (resolve) {
        function finish(err, why) {
          if (err) { self.smDiag.errors.push(String(err.message || err)); }
          self.smRunning = false;
          self.smDiag.stoppedBy = why || (err ? 'error' : null);
          self.smDiag.finishedAt = Date.now();
          self.smDiag.wallMs = self.smDiag.finishedAt - self.smDiag.startedAt;
          resolve(self.smDiag);
        }
        function step() {
          if (self.destroyed || self.paused) { self.smTimer = setTimeout(step, 400); return; }
          if (duration > 0 && Date.now() - started >= duration) { finish(null, 'duration'); return; }
          if (opts.stopAfterNodes && self.smDiag.seq.length >= opts.stopAfterNodes) { finish(null, 'nodes'); return; }
          if (maxBytes > 0 && self.smDiag.bytes >= maxBytes) { finish(null, 'bytes'); return; }
          self.smPlayNode(cur).then(function (node) {
            if (!node) { finish(null, 'no-node'); return; }
            self.smDiag.bytes += node.medium.bytes;
            /* 空闲计时（真事件，不是定时器编的）：连续待在待机类剪辑上超过 12s → 推一次"闭眼休息"入口 */
            if (/^idle/.test(node.clip)) {
              self._idleAccumMs = (self._idleAccumMs || 0) + smHoldMs(node);
              if (self._idleAccumMs >= 12000) {
                self._idleAccumMs = 0;
                self.smHostTrigger('idle');
              }
            } else {
              self._idleAccumMs = 0;
            }
            var hold = smHoldMs(node);
            self.smTimer = setTimeout(function () {
              self.smTimer = null;
              if (self.destroyed) { finish(null); return; }
              var next = null, reason = null, now = Date.now();
              /* ① 宿主队列优先（voice / emotion / idle —— 原版语义：prob=0 只能宿主走） */
              if (self.smPending && self.smPending.length) {
                var pend = self.smPending.shift();
                next = pend.entry; reason = pend.reason;
              } else if (hostEntries.length && (now - lastTrigger) >= triggerMs) {
                /* ② 兜底节拍：轮着来，保证取证时三类宿主事件都能被观测到 */
                reason = SM_CADENCE_REASONS[cadenceIdx % SM_CADENCE_REASONS.length];
                cadenceIdx++;
                next = self.smHostEntryFor(reason);
                lastTrigger = now;
              }
              var tRel = now - self.smDiag.startedAt;
              if (next) {
                self.smDiag.edges.push({ from: cur, to: next, prob: 0, hostTriggered: true,
                                         reason: reason, tMs: tRel });
                self.smDiag.hostTimeline.push({ tMs: tRel, reason: reason, from: cur, entry: next });
              } else {
                var e = self.smPick(cur);
                if (e) {
                  next = e.to;
                  self.smDiag.edges.push({ from: e.from, to: e.to, prob: e.prob, tMs: tRel });
                }
              }
              if (!next) { next = self.graph.root || 'idle'; }
              cur = next;
              step();
            }, hold);
          }, function (err) { finish(err); });
        }
        step();
      });
    });
  };

  Player.prototype.smStop = function () {
    if (this.smTimer) { clearTimeout(this.smTimer); this.smTimer = null; }
    this.smRunning = false;
  };

  /** 覆盖取证：37 个节点逐一真载真画（帧 0 与中间帧），并逐条核对 87 条边的两端。
   *  返回一张"每个剪辑都能播"的表 —— 这是"37/87 真能跑满"的硬证据。 */
  Player.prototype.smCoverage = function () {
    var self = this;
    var out = { nodes: [], edges: [], nodeCount: 0, edgeCount: 0, ok: 0, failed: [] };
    if (!this.ctx) { out.failed.push('没有 canvas（staticOnly 或非舞台形态）'); return Promise.resolve(out); }
    return this.loadGraph().then(function (g) {
      out.nodeCount = g.node_count;
      out.edgeCount = g.edge_count;
      var chain = Promise.resolve();
      g.nodes.forEach(function (node) {
        chain = chain.then(function () {
          return self.ensureMediumClip(node).then(function (atlas) {
            self.smSetCurrent(node, atlas);
            var cur = self.current;
            var probes = [0, Math.floor(node.frames / 2), node.frames - 1];
            var rec = { clip: node.clip, frames: node.frames, pages: atlas.pages.length,
              tier: atlas.tier, frameIntervalMs: node.frameIntervalMs, loopMode: node.loopMode,
              bytes: atlas.pages.reduce(function (s, p) { return s + p.bytes; }, 0),
              probes: [] };
            probes.forEach(function (k) {
              cur.fixedFrame = k;
              self.draw();
              var d = self.ctx.getImageData(0, 0, self.canvas.width, self.canvas.height).data;
              var opaque = 0, hash = 0;
              for (var i = 3; i < d.length; i += 4) { if (d[i] > 8) { opaque++; } }
              for (var j = 0; j < d.length; j += 397) { hash = (hash * 31 + d[j]) >>> 0; }
              rec.probes.push({ frame: k, opaque: opaque, hash: hash });
            });
            cur.fixedFrame = null;
            var anyOpaque = rec.probes.some(function (p) { return p.opaque > 0; });
            rec.ok = !!anyOpaque;
            if (anyOpaque) { out.ok++; } else { out.failed.push(node.clip + ': 画布全透明'); }
            out.nodes.push(rec);
          }, function (err) {
            out.failed.push(node.clip + ': ' + (err && err.message));
            out.nodes.push({ clip: node.clip, ok: false, error: String(err && err.message) });
          });
        });
      });
      return chain.then(function () {
        g.edges.forEach(function (e) {
          var a = self.graphByClip[e.from], b = self.graphByClip[e.to];
          out.edges.push({
            from: e.from, to: e.to, prob: e.prob,
            ok: !!(a && b && a.medium && b.medium),
            hostTriggered: e.prob === 0
          });
        });
        return out;
      });
    });
  };

  /* ------------------------------------------------------- 口型两层（P0-④）
     数据：static/kurisu/mouth/<label>.json（逐帧锚点）+ <label>.patch.webp（嘴部小补丁）
           + <label>.closedRegion.webp（闭嘴源帧的 74×52 截块，给"原方案"用）
     只有上游 _MOUTH_SYNC_LABELS 那 16 个剪辑戴嘴罩（过渡剪辑与 smile/sad 不戴）。 */
  var MOUTH_LABELS = ['speaking_trans', 'speaking_loop1', 'speaking_loop2', 'speaking_short',
    'speaking_med', 'speaking_long', 'speaking_closed_eye_1', 'speaking_closed_eye_2',
    'thinking_speaking1', 'thinking_speaking2', 'key_point_speaking', 'smile_speaking',
    'sad_speaking', 'shy_speaking1', 'shy_speaking2', 'surprise_speaking', 'angry_speaking'];
  /* manifest 里的 4 段主推剪辑没有自己的口型 profile，借用上游的对应关系 */
  var MOUTH_ALIAS = { speaking: 'speaking_loop1', thinking: 'thinking_speaking1' };
  /* 图集帧号 → 源帧号的抽帧倍率（只有 manifest 的 clips.* 那 4 段是 stride 2） */
  var MOUTH_STRIDE = { speaking: 2, thinking: 2 };

  Player.prototype.mouthLabelFor = function (clipName) {
    if (!clipName) { return null; }
    var n = MOUTH_ALIAS[clipName] || clipName;
    return MOUTH_LABELS.indexOf(n) >= 0 ? n : null;
  };

  /** 载入眼皮补丁（与 loadMouth 同构；只请求一次）
   *  优先用内联 geometry（manifest.eye / window.__xkConfig.eye）⇒ 零额外请求；
   *  没有内联就退到 kurisu/eye/<label>.json。载不到 = 永远不叠眼皮，不影响任何既有行为 ✓ */
  Player.prototype.loadEye = function (label) {
    var self = this;
    var inline = null;
    try {
      inline = ((this.manifest || {}).eye) || ((global.__xkConfig || {}).eye) || null;
    } catch (e0) { inline = null; }
    if (this.eyeData || this._eyeLoading) { return this._eyeLoading || Promise.resolve(this.eyeData); }
    var getData = (inline && inline.box)
      ? Promise.resolve(inline)
      : fetch(joinUrl(this.basePath, 'kurisu/eye/' + (label || 'idle1') + '.json'),
              { credentials: 'same-origin' })
        .then(function (r) { if (!r.ok) { throw new Error('eye json HTTP ' + r.status); } return r.json(); });
    this._eyeLoading = getData
      .then(function (d) {
        return loadImage(joinUrl(self.basePath, d.patch)).then(function (img) {
          self.eyeData = d;
          self.eyePatch = { data: d, img: img };
          return d;
        });
      }, function (err) {
        self._eyeLoading = null;                    // 允许下次重试
        self.eyeError = String((err && err.message) || err);
        return null;
      });
    return this._eyeLoading;
  };

  /** 把眼皮补丁贴到眼睛上（alpha = BLINK.alpha）
   *  与嘴部补丁同构：补丁按 tile 原生像素存，画布矩形按 r 等比缩放（medium/hi 两档都成立）。 */
  Player.prototype.drawBlink = function (r, clipName) {
    var p = this.eyePatch;
    if (!p || !r || !(BLINK.alpha > 0)) { return false; }
    if (!this.blinkAllowed(clipName)) { BLINK.clamps++; return false; }
    var d = p.data;
    var box = d.box || [320, 130];
    var anchor = d.sourceAnchor || [71, 31];
    var unitK = (typeof d.k === 'number' && d.k > 0) ? d.k : 1;    // tile 世界 → 源帧世界的比例
    var up = d.upsample || 1;
    var sx = r.w / 764, sy = r.h / 1028;
    var cxs = anchor[0] * unitK, cys = anchor[1] * unitK;
    var bw = box[0] / up * unitK, bh = box[1] / up * unitK;
    var gx = (ANIM_FLAGS.gaze ? GAZE.x * 0.02 : 0);               // T33-b 的眼部微位移（源帧像素）
    var ctx = this.ctx;
    ctx.save();
    ctx.globalAlpha = Math.max(0, Math.min(1, BLINK.alpha));
    ctx.drawImage(p.img, r.x + (cxs - bw / 2 + gx) * sx, r.y + (cys - bh / 2) * sy, bw * sx, bh * sy);
    ctx.restore();
    return true;
  };

  Player.prototype.loadMouth = function (label) {
    var self = this;
    if (!label) { return Promise.resolve(null); }
    this.mouth = this.mouth || {};
    if (this.mouth[label]) { return Promise.resolve(this.mouth[label]); }
    this._mouthLoading = this._mouthLoading || {};
    if (this._mouthLoading[label]) { return this._mouthLoading[label]; }
    var url = joinUrl(this.basePath, 'kurisu/mouth/' + label + '.json');
    this._mouthLoading[label] = fetch(url, { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) { throw new Error('mouth json HTTP ' + r.status); } return r.json(); })
      .then(function (d) {
        return Promise.all([
          loadImage(joinUrl(self.basePath, d.patch)),
          loadImage(joinUrl(self.basePath, d.closedRegion))
        ]).then(function (imgs) {
          var m = { data: d, patch: imgs[0], region: imgs[1] };
          self.mouth[label] = m;
          return m;
        });
      });
    return this._mouthLoading[label];
  };

  /** 在**刚刚画完基础帧**之后叠闭嘴层。
   *  r = 基础帧在画布里的目标矩形；frameIdx = 该剪辑自己的帧下标（anchor_track 按它取）。
   *  源帧坐标（764×1028）→ 画布：sx = r.w/764、sy = r.h/1028（图集 tile 是源帧的等比缩小，所以这条对
   *  medium / hi 两档都成立，不需要按 tile 尺寸另算）。 */
  Player.prototype.drawMouth = function (r, frameIdx, clipName) {
    if (!this.ctx || !r) { return; }
    var label = this.mouthLabelFor(clipName);
    var m = label && this.mouth && this.mouth[label];
    var speaking = VOICE.speaking;
    var mv = mouthEffective();          // 说话中 = 语音包络；静音 = T34 随机口型（说话中不叠 ✗）
    var shouldClose = mv <= 0.08;       // 阈值沿用 0.08 ✓（闭嘴层只在这条线以下才叠）
    this.mouthDiag = { label: label, speaking: speaking, mouthValue: mv, shown: false,
                       mouthSource: speaking ? 'voice' : (MOUTH_IDLE.on ? 'idle' : 'off'),
                       blinkAlpha: BLINK.alpha, blinkState: BLINK.state,
                       variant: VOICE.variant, frame: frameIdx };
    if (!shouldClose || !m) { return; }
    var d = m.data;
    var track = d.anchorTrack || [];
    var a = track[frameIdx] || d.sourceAnchor;
    var bw = d.box[0], bh = d.box[1];
    var sx = r.w / 764, sy = r.h / 1028;
    var mx = 382 + a[0], my = 514 + a[1];
    var ew = bw / 2 * (d.ellipse ? d.ellipse[0] / bw : 1.8);
    var eh = bh / 2 * (d.ellipse ? d.ellipse[1] / bh : 2.125);
    var ctx = this.ctx;
    /* 变体：'auto' 时按 label 自己的偏好 —— 12 个"用自己的闭嘴帧"的剪辑走小补丁（等价、少一张图），
       4 个"借别的剪辑的闭嘴帧"的剪辑走原方案（截块 + 椭圆遮罩），因为借来的帧肤色略不同，
       补丁的矩形硬边看得出来（实测见 _shots/mouth-compare.json）。 */
    var variant = (VOICE.variant && VOICE.variant !== 'auto')
      ? VOICE.variant : (d.preferredVariant || 'patch');
    this.mouthDiag.variant = variant;
    ctx.save();
    if (variant === 'frame') {
      /* 原方案（上游算法）：闭嘴源帧的截块按"锚点差"整体平移，再用椭圆遮罩只露嘴。
         截块 74×52 完全包含椭圆 61×38 ⇒ 与"整帧 + 椭圆遮罩"在可视区域内逐像素等价
         （离线已证：见 _dev/mouth-verify.json 的 A_vs_Aregion）。 */
      var dx = a[0] - d.sourceAnchor[0], dy = a[1] - d.sourceAnchor[1];
      var rx = 382 + d.sourceAnchor[0] - 37 + dx;
      var ry = 514 + d.sourceAnchor[1] - 26 + dy;
      ctx.beginPath();
      ctx.ellipse(r.x + mx * sx, r.y + my * sy, ew * sx, eh * sy, 0, 0, Math.PI * 2);
      ctx.clip();
      ctx.drawImage(m.region, r.x + rx * sx, r.y + ry * sy, 74 * sx, 52 * sy);
    } else {
      /* 新方案（评审建议）：34×18 的嘴部小补丁按锚点直接贴，不裁不遮。
         补丁本身就是那个嘴框的内容，所以不需要椭圆。 */
      ctx.drawImage(m.patch, r.x + (mx - bw / 2) * sx, r.y + (my - bh / 2) * sy, bw * sx, bh * sy);
    }
    ctx.restore();
    this.mouthDiag.shown = true;
    VOICE.diag.mouthShown++;
  };

  /** 强制画出"某一变体的闭嘴层"（截图 / 现场演示用；不改动任何默认行为） */
  Player.prototype.mouthRender = function (opts) {
    var self = this;
    opts = opts || {};
    var label = opts.label || 'speaking_loop1';
    var frame = opts.frame || 0;
    return this.loadGraph().then(function (g) {
      var node = null;
      for (var i = 0; i < g.nodes.length; i++) { if (g.nodes[i].clip === label) { node = g.nodes[i]; break; } }
      if (!node) { return false; }
      return self.ensureMediumClip(node).then(function (atlas) {
        self.smSetCurrent(node, atlas);
        self.stopLoop();
        self.current.fixedFrame = frame;
        return self.loadMouth(label).then(function (m) {
          if (!m) { return false; }
          VOICE.variant = (opts.variant === 'frame') ? 'frame' : 'patch';
          VOICE.speaking = opts.speaking !== false;
          VOICE.mouthValue = (typeof opts.mouthValue === 'number') ? opts.mouthValue : 0;
          self.draw();
          return true;
        });
      });
    });
  };

  /** 同帧并排对照（验收用）：同一个基础帧 + 同一条锚点，两种闭嘴层各画一遍，
   *  在"嘴框"区域内量 NCC / 最大差 / 平均差。返回数字，不靠人眼看。 */
  Player.prototype.mouthCompare = function (opts) {
    opts = opts || {};
    var self = this;
    var label = opts.label || 'speaking_loop1';
    var frame = opts.frame || 0;
    var out = { label: label, frame: frame, variantA: 'frame', variantB: 'patch' };
    if (!this.ctx) { return Promise.resolve({ error: '没有 canvas' }); }
    return this.loadGraph().then(function (g) {
      var node = null;
      for (var i = 0; i < g.nodes.length; i++) {
        if (g.nodes[i].clip === label) { node = g.nodes[i]; break; }
      }
      if (!node) { return { error: 'label 不在状态机里：' + label }; }
      return self.ensureMediumClip(node).then(function (atlas) {
        self.smSetCurrent(node, atlas);
        self.current.fixedFrame = frame;
        self.stopLoop();
        return self.loadMouth(label).then(function (m) {
          if (!m) { return { error: '口型数据载不到' }; }
          var d = m.data;
          var track = d.anchorTrack || [];
          var a = track[frame] || d.sourceAnchor;
          var r = self.charRect(self.canvas.width, self.canvas.height, self.current.fw / self.current.fh);
          var sx = r.w / 764, sy = r.h / 1028;
          var bw = d.box[0], bh = d.box[1];
          var boxCanvas = {
            x: r.x + (382 + a[0] - bw / 2) * sx,
            y: r.y + (514 + a[1] - bh / 2) * sy,
            w: bw * sx, h: bh * sy
          };
          var grab = function (variant) {
            VOICE.variant = variant;
            VOICE.speaking = true;
            VOICE.mouthValue = 0;
            self.draw();
            var x = Math.max(0, Math.floor(boxCanvas.x)), y = Math.max(0, Math.floor(boxCanvas.y));
            var w = Math.max(1, Math.ceil(boxCanvas.w)), h = Math.max(1, Math.ceil(boxCanvas.h));
            return self.ctx.getImageData(x, y, w, h).data;
          };
          var A = grab('frame');
          var B = grab('patch');
          VOICE.speaking = false;
          VOICE.mouthValue = 0;
          VOICE.variant = 'patch';
          self.draw();
          var n = Math.min(A.length, B.length) / 4;
          var sa = 0, sb = 0, i, va, vb;
          for (i = 0; i < n; i++) {
            va = (A[i * 4] + A[i * 4 + 1] + A[i * 4 + 2]) / 3;
            vb = (B[i * 4] + B[i * 4 + 1] + B[i * 4 + 2]) / 3;
            sa += va; sb += vb;
          }
          sa /= n; sb /= n;
          var cov = 0, va2 = 0, vb2 = 0, maxd = 0, sumd = 0, over2 = 0;
          for (i = 0; i < n; i++) {
            va = (A[i * 4] + A[i * 4 + 1] + A[i * 4 + 2]) / 3;
            vb = (B[i * 4] + B[i * 4 + 1] + B[i * 4 + 2]) / 3;
            var da = va - sa, db = vb - sb, dd = Math.abs(va - vb);
            cov += da * db; va2 += da * da; vb2 += db * db;
            sumd += dd;
            if (dd > maxd) { maxd = dd; }
            if (dd > 2) { over2++; }
          }
          out.pixels = n;
          out.ncc = (va2 > 0 && vb2 > 0) ? (cov / Math.sqrt(va2 * vb2)) : 1;
          out.meanAbsDiff = sumd / n;
          out.maxAbsDiff = maxd;
          out.pixelsOver2 = over2;
          out.boxCanvas = boxCanvas;
          out.frameSize = { srcW: 764, srcH: 1028, scaleX: sx, scaleY: sy,
                            tile: [self.current.fw, self.current.fh] };
          out.anchor = { cx: a[0], cy: a[1], deltaFromSource: [a[0] - d.sourceAnchor[0], a[1] - d.sourceAnchor[1]] };
          out.ellipseSourcePx = d.ellipse;
          out.boxSourcePx = [bw, bh];
          self.current.fixedFrame = null;
          return out;
        });
      });
    });
  };

  /* ------------------------------------------------------- 自动挂载/路由 */
  /* 不碰 app.js：自己监听路由 + 监听 #content 的子节点变化，重新扫描挂载点。 */
  var mounts = [];
  var rescanTimer = null;

  function destroyAll() {
    mounts.forEach(function (p) { try { p.destroy(); } catch (e) { /* 忽略 */ } });
    mounts = [];
  }

  /* 语音/口型的诊断与手动入口（验收脚本与站主演示用；不参与渲染） */
  function voiceDiag() {
    var p = mounts.filter(function (x) { return x.mode === 'stage'; })[0] || mounts[0] || null;
    return {
      unlocked: VOICE.unlocked, unlockedBy: VOICE.diag.unlockedBy,
      blockedPlays: VOICE.diag.blockedPlays, plays: VOICE.diag.plays,
      lastLine: VOICE.diag.lastLine, bankLines: VOICE.diag.bankLines,
      mouthShown: VOICE.diag.mouthShown, mouthHidden: VOICE.diag.mouthHidden,
      variant: VOICE.variant,
      speaking: VOICE.speaking, mouthValue: VOICE.mouthValue,
      currentTime: VOICE.audio ? VOICE.audio.currentTime : null,
      paused: VOICE.audio ? VOICE.audio.paused : null,
      errors: VOICE.diag.errors.slice(-5),
      mouthDiag: p ? p.mouthDiag || null : null
    };
  }

  function routeKey() {
    /* ★ 2026-10-14 修（首屏字节）：老实现只认 hash。直接访问 `/alerts/`、`/posts/` 这类 URL 时
       hash 是空的 → 它把**每个直连页面都当成 home**，于是每个页面都 ensureStage() +
       实例化 CRT 舞台，白拉 idle.boot(519KB) + medium/idle.atlas(777KB) + idle.hi(1285KB)。
       现在：有 hash（= SPA 导航中）以 hash 为准；没有 hash（= 直连/SSR）以
       <main id="content" data-xk-ssr> 这个服务端标记为准。 */
    var h = (global.location.hash || '').replace(/^#/, '');
    var fromHash = h.split('/')[1] || '';
    if (fromHash) { return fromHash; }
    var host = document.getElementById('content');
    var ssr = host && host.getAttribute('data-xk-ssr');
    if (ssr && ssr !== 'notfound') { return ssr; }
    return 'home';
  }

  /** 🔊 按钮的统一接线（实例内的按钮、以及页面底部输入条那颗，都用这一份）。
   *  契约：只读不写地把 TTS_DISABLED 如实写进 aria-live 节点，绝不假装在播、绝不发请求。 */
  function wireVoiceButton(btn, noteEl) {
    if (!btn || btn.getAttribute('data-xk-voice-wired')) { return; }
    btn.setAttribute('data-xk-voice-wired', '1');
    btn.setAttribute('aria-pressed', 'false');
    /* ★T4：AI 页右栏（data-xk-kurisu-hook="ask"）那颗 🔊 就是**声音开关**：
       第一次点既解锁浏览器音频（手势闸），也打开"要不要念日语"；再点一次关声、只留中文字幕。
       其它地方那颗按钮保持原行为（只如实说"语音未启用"，一次请求都不发）—— 不动已经验收的路径。 */
    var askRail = null;
    try { askRail = (btn.closest ? btn.closest('[data-xk-kurisu-hook="ask"]') : null); } catch (e) { askRail = null; }
    if (askRail) {
      btn.setAttribute('data-xk-speak-ja', '1');
      refreshSpeakButtons();
      btn.addEventListener('click', function () {
        unlockAudio('🔊 按钮');
        SPEAK.on = !SPEAK.on;
        refreshSpeakButtons();
        voiceNote(SPEAK.on
          ? '声音已开：之后每题念一句日语（中文字幕照旧）。再点一次就关声。'
          : '声音已关：只留中文字幕（不请求任何语音）。');
        if (SPEAK.on && VOICE.pendingSpeak) {
          var p = VOICE.pendingSpeak;
          VOICE.pendingSpeak = null;
          speakJaSay(p);
        }
      });
      return;
    }
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

  /** 主页输入条 = "她的嘴"：直接打真实的 POST /api/public/ask（既有端点，不新增后端）。
   *  等待期间播 thinking 帧序列，拿到答案播 speaking 帧序列 + 把答案开头写进屏内字幕条；
   *  失败 / 限流 / 没有正文一律如实写进字幕，绝不编一句"像答案"的话。 */
  function askOnStage(p, question) {
    p.showSubtitle('正在检索与研判 —— 这个问题走真实的检索增强链路。');
    p.emotionVariant = 'idle';
    if (!p.staticOnly) { p.play('thinking'); }
    var ctrl = (typeof AbortController === 'function') ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) { ctrl.abort(); } }, 20000);
    fetch(apiBaseUrl() + '/api/public/ask', {
      method: 'POST', mode: 'cors', credentials: 'omit', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      signal: ctrl ? ctrl.signal : undefined,
      body: JSON.stringify({ question: String(question).slice(0, 600) })
    }).then(function (r) {
      return r.json().then(function (b) { return { ok: r.ok, status: r.status, body: b }; },
        function () { return { ok: r.ok, status: r.status, body: null }; });
    }).then(function (res) {
      clearTimeout(timer);
      if (p.destroyed) { return; }
      var d = (res.body && res.body.data) ? res.body.data : res.body;
      var ans = d && (d.answer || d.text || (d.reply && d.reply.answer));
      if (res.ok && ans) {
        p.speak(null, String(ans).replace(/\s+/g, ' ').slice(0, 120));
        return;
      }
      var why = res.ok ? '返回里没有可显示的答案正文' : ('HTTP ' + res.status);
      p.showSubtitle('这次没拿到答案（' + why + '）—— 完整问答请到 AI 问答页。');
      if (!p.staticOnly) { p.play('idle'); }
    }, function () {
      clearTimeout(timer);
      if (p.destroyed) { return; }
      p.showSubtitle('这次请求没送达（网络或超时）—— 不补话；完整问答请到 AI 问答页。');
      if (!p.staticOnly) { p.play('idle'); }
    });
  }

  /** 页面底部输入条：显示规则 + 提交规则。
   *  · 显示：桌面只在主页；窄屏所有栏目页都显示（AI 页除外 —— 它自己的对话输入区就是"嘴"）。
   *  · 提交（主页）：**就在大屏里**走 POST /api/public/ask —— 她说话、字幕同步（站主要的效果）。
   *    不新增任何后端端点；没有实例时（极端降级）才退回"切到 AI 页填进真实输入框"。 */
  function wireBar() {
    var bar = q('[data-xk-kurisu-bar]');
    var route = routeKey();
    var narrow = mqOn(mq('(max-width: 980px)'), (global.innerWidth || 1280) <= 980);
    var on = route !== 'ai' && (narrow || route === 'home');
    var root = document.documentElement;
    if (on) { root.setAttribute('data-xk-kbar-on', '1'); } else { root.removeAttribute('data-xk-kbar-on'); }
    if (!bar) { return; }
    // 占位文案跟路由走：主页是"在屏幕里回答"，其它路由仍是"切到 AI 问答页"
    var ph = (route === 'home')
      ? '问她一个安全相关的问题…（Enter 发送；她会在屏幕里回答，走真实接口）'
      : '问她一个安全相关的问题…（Enter 发送；会切到 AI 问答页，走真实链路）';
    var phEl = q('#xk-kbar-input', bar);
    if (phEl && phEl.getAttribute('placeholder') !== ph) { phEl.setAttribute('placeholder', ph); }
    wireVoiceButton(q('[data-xk-kurisu-voice]', bar), q('[data-xk-kurisu-voice-note]', bar));
    if (bar.getAttribute('data-xk-kbar-wired')) { return; }
    bar.setAttribute('data-xk-kbar-wired', '1');
    bar.addEventListener('submit', function (e) {
      e.preventDefault();
      var input = q('#xk-kbar-input', bar);
      var text = (input && input.value || '').trim();
      if (!text) { if (input) { input.focus(); } return; }
      if (input) { input.value = ''; }
      var stage = mounts.filter(function (p) { return p.mode === 'stage'; })[0];
      if (route === 'home' && stage) { askOnStage(stage, text); return; }
      global.location.hash = '#/ai';
      var tries = 0;
      (function waitForChat() {
        var ta = q('#xk-ask-input'), run = q('[data-xk-ask-run]');
        if (ta && run) {
          ta.value = text;
          try { run.click(); } catch (err) { /* 按钮可能被改；至少文字已经填进真实输入框 */ }
          return;
        }
        if (++tries > 40) { return; }     // 约 4s 后放弃（人已经停在 AI 页，可以自己按发送）
        setTimeout(waitForChat, 100);
      })();
    });
  }

  /* ------------------------------------------------ 开场只在该会话的第一次播 */
  var INTRO_KEY = 'xk-kurisu-intro-played';
  function shouldPlayIntro() {
    // 取证/调试用：?xk_intro=always 强制每次都播（默认每个浏览器会话只播一次）
    if (/(^|[?&])xk_intro=always(&|$)/.test(global.location.search)) { return true; }
    /* ★ 2026-10-18 站主反馈：一进来是半身贴脸图、然后硬切成全身站定，看着像“闪了一下”。
       开场序列直接关掉（保留 ?xk_intro=always 作为取证开关）：默认直接起 idle 全身。 */
    return false;
  }
  function markIntroPlayed() {
    try { global.sessionStorage.setItem(INTRO_KEY, '1'); } catch (e) { /* 隐私模式忽略 */ }
  }

  /** 从非主页路由点回主页时，<main> 外面那一层 CRT 场景并没有随 SSR 渲染出来，
   *  这里把 <template id="tpl-kurisu-stage"> 的惰性内容挂到 body 末尾（挂一次就够）。
   *  ★ 2026-10-14 修（真回归）：守卫原来查的是 `q('.xk-crt')`，而主页 stage 换成 demo 版式后
   *  根元素变成 `#xk-app .crt` —— `.xk-crt` 永远查不到，于是**每次 scan() 都往 body 再挂一份 stage**。
   *  后果：同一个页面出现 2 份 `[data-xk-kurisu="stage"]`，`scan()` 给两份都建了播放器，
   *  后挂的那份画布盖在上面；而 `KurisuPlayer.stage()` 返回的是**第一份**（它可能早已被
   *  destroyAll() 销毁 → `play()` 提前返回 → `current` 永远为空）。实测表现就是
   *  "角色画布空白、CRT 内部像素差从 11% 恶化到 81%"。守卫改成查**新的挂载点标记**。 */
  function ensureStage() {
    if (q('[data-xk-kurisu="stage"]') || q('.xk-crt')) { return; }
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
    // 主页：把 CRT 场景层打开（CSS 只认这个开关）
    if (route === 'home') { document.documentElement.setAttribute('data-xk-crt-on', '1'); }
    else { document.documentElement.removeAttribute('data-xk-crt-on'); }
    wireBar();
    /* 事件驱动的宿主触发 · 第 4 类：切页 → 切页解说（有台词就一定会推 speaking 入口） */
    navCommentary(route, mounts);
    if (!nodes.length) { return; }
    var playIntro = route === 'home' && shouldPlayIntro();
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
        // 开场要播：**先**把屏内两层切到"只有开场层"（属性在，画布还没画 = 空屏，
        // 不会先闪一下全身），再等清单/图集就绪。
        if (playIntro && mode === 'stage' && !p.staticOnly) {
          p.mount.setAttribute('data-xk-crt-intro', '1');
        }
      } catch (e) { /* 单个挂载点失败不影响别人 */ }
    });

    // 规格：首屏渲染完成之后再载角色资源（延迟 200ms + 让一次空闲）
    setTimeout(function () {
      if (!mounts.length) { return; }
      whenIdle(function () {
        mounts.forEach(function (p) {
          p.ready().then(function () {
            if (p.mode !== 'stage' || !playIntro) { return null; }
            markIntroPlayed();
            // ① 底层先把"全身 idle"跑起来（开场层淡出时立刻就是站定画面）
            // ② 开场：原包 look_at_CRT_loop 的真实帧序列（clips.opening，role:"intro"）
            // ③ 站定之后她开口说第一句 —— speaking 帧序列 + 字幕同步
            return p.play('idle').then(function () { return p.intro(); }).then(function (r) {
              if (!r || !r.played) { return null; }
              return new Promise(function (res) { setTimeout(res, 460); }).then(function () {
                /* 首访 / 回访分流（P1-⑧）：台词 id 不同，音色与链路完全一样；
                   音频受 autoplay 门控，未交互时只出字幕（动画照常）。 */
                p.speak(visitedBefore() ? 'greet_welcome_back' : 'greet_welcome', null);   /* greet_first/back 已于 rev7 下线 */
                markVisited();
                return r;
              });
            });
          }).then(function () {
            // ④ 开场走完（或本轮不播开场）→ 状态机 37 节点 / 87 边自动游走
            //    manifest.stateMachine.auto === false 是运行期总闸（改一个 JSON 就能全站关掉）
            var smOff = !!(p.manifest && p.manifest.stateMachine && p.manifest.stateMachine.auto === false);
            if (p.smOn && !smOff && !p.staticOnly && !p.destroyed) { return p.smStart({ durationMs: 0 }); }
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

  /* ------------------------------------------------ 首访/回访分流 + 切页解说 */
  var VISIT_KEY = 'xk-kurisu-visited';
  function visitedBefore() {
    try { return global.localStorage.getItem(VISIT_KEY) === '1'; } catch (e) { return false; }
  }
  function markVisited() {
    try { global.localStorage.setItem(VISIT_KEY, '1'); } catch (e) { /* 隐私模式忽略 */ }
  }
  /* ★T3（2026-10-16 语音线）：删掉 range / labs / about 三个键 —— 那两个页面已删（T27），
     对应的两条死语音 `nav_labs` / `nav_about` 也已从 `bank.json` 与 merged 索引里移除。
     留着这三个键就会变成"有键无文件"的**新断链**（正是本次要清掉的那种）。 */
  var NAV_LINE = { home: 'nav_home', notes: 'nav_notes', monitor: 'nav_monitor', ai: 'nav_ai', what: 'nav_what', lab: 'nav_lab' };
  var lastNavLine = null;

  /** 切页解说：一个路由只讲解一次（同一路由的重复 scan 不重复说话） */
  function navCommentary(route, mounts) {
    var id = NAV_LINE[route];
    if (!id || lastNavLine === route) { return; }
    lastNavLine = route;
    var p = mounts.length ? mounts[0] : null;
    if (p) { p.speak(id, null); } else { speakImpl(id, null, { basePath: '/' }); }
  }

  /* 切回标签页打招呼（隐藏 > 60s 才算"离开过"） */
  var hiddenAt = 0;
  function tabReturnWatch() {
    if (tabReturnWatch.done) { return; }
    tabReturnWatch.done = true;
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) { hiddenAt = Date.now(); return; }
      var away = hiddenAt ? (Date.now() - hiddenAt) : 0;
      hiddenAt = 0;
      if (away < 60000) { return; }
      var p = mounts.length ? mounts[0] : null;
      if (p) { p.speak('tab_return', null); } else { speakImpl('tab_return', null, { basePath: '/' }); }
    }, false);
  }

  function watch() {
    installAskHook();
    installAudioGate();
    tabReturnWatch();
    var host = q('#content') || document.body;
    if (global.MutationObserver && host) {
      new MutationObserver(scheduleScan).observe(host, { childList: true });
    }
    global.addEventListener('hashchange', scheduleScan, false);
    global.addEventListener('popstate', scheduleScan, false);
    scan();
  }

  function round2(v) { return Math.round(v * 100) / 100; }

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
    instances: function () { return mounts.slice(); },
    /* 状态机取证入口（给 _dev/shot-preview-1280.mjs 这类本地验收脚本用；
       不参与渲染，也不改变任何默认行为） */
    stage: function () {
      for (var i = 0; i < mounts.length; i++) { if (mounts[i].mode === 'stage') { return mounts[i]; } }
      return mounts[0] || null;
    },
    smDiag: function () { return global.__xkSm || null; },
    /** 跑一次覆盖取证：37 节点逐一真载真画 + 87 条边逐一核对（会真下载 48MB，只在本地取证时调） */
    smCoverage: function () {
      var p = KurisuPlayer.stage();
      if (!p) { return Promise.reject(new Error('页面上没有舞台实例')); }
      return p.smCoverage();
    },
    /** 跑一段限时自动游走并返回节点序列（取证用） */
    smWalk: function (opts) {
      var p = KurisuPlayer.stage();
      if (!p) { return Promise.reject(new Error('页面上没有舞台实例')); }
      return p.smStart(opts || { durationMs: 30000 });
    },
    smStop: function () {
      var p = KurisuPlayer.stage();
      if (p) { p.smStop(); }
    },
    /* T33/T34 的取证入口（纯只读快照，不改变任何行为） */
    animDiag: function () {
      var p = KurisuPlayer.stage();
      return {
        flags: { mouthIdle: ANIM_FLAGS.mouthIdle, blink: ANIM_FLAGS.blink, gaze: ANIM_FLAGS.gaze },
        mouthIdle: { on: MOUTH_IDLE.on, value: round2(MOUTH_IDLE.value), peak: MOUTH_IDLE.peak,
                     blinks: MOUTH_IDLE.blinks, source: MOUTH_IDLE.source, maxOpen: MOUTH_IDLE.maxOpen,
                     minMs: MOUTH_IDLE.minMs, maxMs: MOUTH_IDLE.maxMs },
        blink: { on: BLINK.on, state: BLINK.state, alpha: round2(BLINK.alpha), count: BLINK.count,
                 closeMs: BLINK.closeMs, holdMs: BLINK.holdMs, openMs: BLINK.openMs,
                 minMs: BLINK.minMs, maxMs: BLINK.maxMs, clamps: BLINK.clamps,
                 loaded: !!(p && p.eyeData), error: (p && p.eyeError) || null,
                 label: (p && p.eyeData && p.eyeData.label) || null },
        gaze: { on: GAZE.on, x: round2(GAZE.x), y: round2(GAZE.y), tx: round2(GAZE.tx), ty: round2(GAZE.ty),
                gain: GAZE.gain, clamp: GAZE.clamp, smoothMs: GAZE.smoothMs, level: round2(GAZE.level),
                eyePoint: p ? p.eyePoint() : null },
        mouthDiag: (p && p.mouthDiag) || null,
        mouthEffective: round2(mouthEffective())
      };
    },
    /* 眼皮补丁的叠加对拍（返回数字，不靠人眼看） */
    eyeRender: function (opts) {
      var p = KurisuPlayer.stage();
      if (!p) { return Promise.resolve(false); }
      opts = opts || {};
      var frame = (typeof opts.frame === 'number') ? opts.frame : 0;
      return p.loadEye('idle1').then(function (d) {
        if (!d) { return false; }
        var node = p.graphByClip && p.graphByClip[d.sourceClip || 'idle1'];
        if (!node) { return false; }
        return p.ensureMediumClip(node).then(function (atlas) {
          p.smSetCurrent(node, atlas);
          p.stopLoop();
          p.current.fixedFrame = frame;
          BLINK.alpha = (typeof opts.alpha === 'number') ? opts.alpha : 1;
          p.draw();
          var r = p.charRect(p.canvas.width, p.canvas.height, p.current.fw / p.current.fh);
          var k = (typeof d.k === 'number' && d.k > 0) ? d.k : 1;
          var up = d.upsample || 1;
          var bw = d.box[0] / up * k, bh = d.box[1] / up * k;
          var out = { label: d.sourceClip || 'idle1', frame: frame, alpha: BLINK.alpha,
                      shown: p.drawBlink(r, p.current.clipName || p.current.clip),
                      box: d.box, sourceAnchor: d.sourceAnchor,
                      drawn: { x: r.x + (d.sourceAnchor[0] * k - bw / 2) * (r.w / 764),
                               y: r.y + (d.sourceAnchor[1] * k - bh / 2) * (r.h / 1028),
                               w: bw * (r.w / 764), h: bh * (r.h / 1028) } };
          if (opts.reset !== false) { BLINK.alpha = 0; p.current.fixedFrame = null; p.draw(); }
          return out;
        });
      });
    },
    /* 语音/口型（P0-③④）的取证入口 */
    voiceDiag: voiceDiag,
    unlockAudio: function (how) { unlockAudio(how || 'api'); return VOICE.unlocked; },
    speakLine: function (id, text) {
      var p = mounts.length ? mounts[0] : null;
      return p ? p.speak(id, text) : speakImpl(id, text, { basePath: '/' });
    },
    /** 按组播一句（防复读选句器；验收入口 ✓） */
    speakGroup: function (group, ctx) { return speakGroup('/', group, ctx); },
    /** 选句器取证：抽了多少次 / 出现过几次"组内只有 1 条" / 每组候选规模 ✓ */
    linePickDiag: function () { return JSON.parse(JSON.stringify(PICK.diag)); },
    /** 导航语音取证（最近一次播了哪个板块的哪条 id） */
    navDiag: function () { return VOICE.diag.lastNav || null; },
    /** 宿主触发（事件驱动入口的手动版，演示/验收用）：reason = voice|emotion|idle */
    hostTrigger: function (reason) {
      var p = KurisuPlayer.stage();
      return p ? p.smHostTrigger(reason || 'voice') : false;
    },
    setMouthVariant: function (v) {
      VOICE.variant = (v === 'frame') ? 'frame' : 'patch';
      VOICE.diag.variant = VOICE.variant;
      return VOICE.variant;
    },
    /** 口型两层的同帧并排对照（返回数字，不靠人眼看） */
    mouthCompare: function (opts) {
      var p = KurisuPlayer.stage();
      if (!p) { return Promise.reject(new Error('页面上没有舞台实例')); }
      return p.mouthCompare(opts || {});
    },
    /** 画出指定变体的闭嘴层（截图/演示） */
    mouthRender: function (opts) {
      var p = KurisuPlayer.stage();
      if (!p) { return Promise.resolve(false); }
      return p.mouthRender(opts || {});
    }
  };

  global.KurisuPlayer = KurisuPlayer;
  KurisuPlayer.boot();

})(typeof window !== 'undefined' ? window : this);
