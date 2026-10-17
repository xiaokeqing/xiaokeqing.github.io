/* ============================================================================
   XKPhoneEmote · 手机面板 E-mote 助手挂载器（可入库件：static/js/phone-emote.js）
   ----------------------------------------------------------------------------
   用途：把内容页右侧"手机面板"里的助手，从 Sprite 三段
        （/kurisu/full/{idle,speaking,thinking}.hi.webp）换成 **E-mote 实时渲染**；
        **电视那套 Sprite 状态机完全不碰**（各管各的画布：它用 #charCanvas，这里用手机面板的画布）。

   稳定 API（调用方只依赖这些）：
     const inst = XKPhoneEmote.mount(canvasEl, { model:'kurisu_c', mode:'idle', crop:0.52 });
       · 命中任一下线开关 / 环境不支持 ⇒ **返回 null**，且**绝不接管画布** ⇒ 调用方继续用 Sprite 三段
       · 否则返回实例（**同步**返回，加载是懒的、异步的）：
           inst.setMode('idle'|'thinking'|'speaking')   // 未就绪时先记下，就绪后生效
           inst.setModel('kurisu_c')                    // 只接受随包提供的模型；未知模型返回 false
           inst.dispose()                               // 释放（观测器/动画/引用）
           inst.status()                                // {state,ready,model,mode,loadMs,memMB,fps,error,reason,bytes}
           inst.onStatus(fn)                            // 状态变化回调（fn(status)，用于更新 UI 文案）
     XKPhoneEmote.models   // 随包模型登记表
     XKPhoneEmote.base     // 资源根（默认 '/kurisu/emote/'，可覆盖）

   懒加载（不抢首屏）：**先等**（首个 /api/public/** 响应落地 ｜ 首次手势 ｜ 最迟 6000ms，三选一）
                     **再等**画布进入可视区（IntersectionObserver）⇒ 两者都满足才拉运行时与模型。

   红线：**不引任何站外资源**（无 CDN）；运行时与模型都走本地相对路径。
   授权：E-mote 模型素材来自商业游戏（仅非商业技术学习/研究/演示）；
        运行时 FreeMote SDK 为 CC BY-NC-SA 4.0。整体可用 `?xk-no-kurisu=1` 一键关闭。
   ============================================================================ */
(function () {
  'use strict';

  var NS = (window.XKPhoneEmote = window.XKPhoneEmote || {});
  if (NS.mount) { return; }                     /* 重复引入时幂等 */
  NS.version = '1.0.0';

  var BASE = NS.base || '/kurisu/emote/';
  var LOADER_URL = BASE + 'loader/psb.js';
  var RUNTIME_URLS = [BASE + 'runtime/FreeMoteDriver.js', BASE + 'runtime/emoteplayer.js'];

  /* 随包模型登记表：dir 必须与 loader 侧目录名一致（psb.mjs 由 name 推导 <name>.psb.m.json） */
  var MODELS = {
    kurisu_c: { dir: 'kurisu_c', label: '常服', arm: null, crop: 0.52 },
  };
  NS.models = MODELS;

  var MAX_WAIT_MS = 6000;                        /* 与 B5 的"最迟 6s"一致 */
  var bootWaiter = null;                         /* 全局只等一次 */

  function qp(k) {
    try { var m = location.search.match(new RegExp('[?&]' + k + '=([^&]+)')); return m ? decodeURIComponent(m[1]) : null; } catch (e) { return null; }
  }
  function reduced() { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; } }

  /* ---- 下线开关（同步判定）：任一命中 ⇒ mount() 返回 null ---- */
  function gateReasons() {
    var r = [];
    if (window.__xkPhoneEmoteOff) { r.push('__xkPhoneEmoteOff'); }
    if (window.__xkNoKurisu === true) { r.push('__xkNoKurisu'); }
    if (qp('xk-no-kurisu') === '1' || qp('xk-kurisu') === 'off' || qp('xk-phone-emote') === 'off') { r.push('url-switch'); }
    if (reduced()) { r.push('prefers-reduced-motion'); }
    var ok = false;
    try { var c = document.createElement('canvas'); ok = !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (e) { ok = false; }
    if (!ok) { r.push('no-webgl'); }
    return r;
  }

  /* ---- 懒加载：等"首个 API 响应 / 首次手势 / 6s" ---- */
  function waitForBoot() {
    if (bootWaiter) { return bootWaiter; }
    bootWaiter = new Promise(function (resolve) {
      var done = false;
      function fire(why) { if (done) { return; } done = true; cleanup(); resolve(why); }
      function cleanup() {
        window.removeEventListener('pointerdown', onGesture, true);
        window.removeEventListener('keydown', onGesture, true);
        window.removeEventListener('scroll', onGesture, true);
        clearTimeout(timer);
        try { obs && obs.disconnect(); } catch (e) {}
      }
      function onGesture() { fire('gesture'); }
      var timer = setTimeout(function () { fire('timeout'); }, MAX_WAIT_MS);
      window.addEventListener('pointerdown', onGesture, true);
      window.addEventListener('keydown', onGesture, true);
      window.addEventListener('scroll', onGesture, { capture: true, passive: true });
      var obs = null;
      try {
        obs = new PerformanceObserver(function (list) {
          var es = list.getEntries();
          for (var i = 0; i < es.length; i++) {
            if (/\/api\/public\//.test(es[i].name)) { fire('first-api'); return; }
          }
        });
        obs.observe({ type: 'resource', buffered: true });
        /* buffered 里可能已经有过了 */
        var has = performance.getEntriesByType('resource').some(function (e) { return /\/api\/public\//.test(e.name); });
        if (has) { fire('first-api'); }
      } catch (e) { /* 老浏览器：退化为手势/超时 */ }
    });
    return bootWaiter;
  }
  function whenVisible(el) {
    return new Promise(function (resolve) {
      try {
        if (!('IntersectionObserver' in window)) { resolve('no-io'); return; }
        var io = new IntersectionObserver(function (ents) {
          for (var i = 0; i < ents.length; i++) {
            if (ents[i].isIntersecting && ents[i].intersectionRatio > 0) { io.disconnect(); resolve('visible'); return; }
          }
        }, { threshold: 0.01 });
        io.observe(el);
      } catch (e) { resolve('io-error'); }
    });
  }

  function injectScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = src; s.async = false; s.dataset.xkPhoneEmote = '1';
      s.onload = function () { resolve(src); };
      s.onerror = function () { reject(new Error('脚本加载失败: ' + src)); };
      (document.head || document.documentElement).appendChild(s);
    });
  }

  function memMB() {
    try { return performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null; } catch (e) { return null; }
  }

  /* EmotePlayer 由 Emscripten 的 WASM 异步初始化：脚本 onload 时它还可能没挂上 ⇒ 必须轮询等 */
  function waitForEmote(ms) {
    return new Promise(function (resolve, reject) {
      var t0 = Date.now();
      (function poll() {
        if (typeof EmotePlayer !== 'undefined' && window.EmoteDriver_Initialized) { resolve(true); return; }
        if (Date.now() - t0 > ms) { reject(new Error('E-mote 运行时初始化超时（WASM/WebGL）')); return; }
        setTimeout(poll, 100);
      })();
    });
  }

  NS.mount = function (canvas, opts) {
    opts = opts || {};
    var reasons = gateReasons();
    var st = {
      state: reasons.length ? 'off' : 'pending', ready: false, model: opts.model || 'kurisu_c',
      mode: opts.mode || 'idle', loadMs: null, memMB: null, fps: null, bytes: null,
      error: null, reason: reasons.length ? reasons.join('+') : null, bootWhy: null, visible: false,
    };
    if (reasons.length) { return null; }        /* ★ 返回 null：调用方继续用 Sprite 三段，画布不被接管 */

    if (!canvas) { return null; }
    var registry = MODELS[st.model] || null;
    if (!registry) { return null; }

    var player = null, metadata = null, applyMode = function () {}, updateParts = function () {}, speaking = false;
    /* ★V5（2026-10-17）：表情覆盖位 —— [EMO:xxx] 逐句继承时用它跳过 MODE_LABEL 的 idle/thinking 表 */
    var exprOverride = null, exprLabels = [];
    var disposed = false, fpsTimer = null;
    var cbs = [];
    function emit() { for (var i = 0; i < cbs.length; i++) { try { cbs[i](inst.status()); } catch (e) {} } }

    function setState(s, extra) {
      st.state = s;
      if (extra) { for (var k in extra) { st[k] = extra[k]; } }
      emit();
    }

    var inst = {
      setMode: function (mode) {
        if (disposed) { return false; }
        st.mode = (mode === 'thinking' || mode === 'speaking') ? mode : 'idle';
        if (st.ready) { applyMode(); } else { emit(); }
        return true;
      },
      /* ★V5：按 E-mote 的"表情_xxx"标签直接切表情（传 null/'' 复位成按 mode 自动）。
         未知标签返回 false（调用方自己回落），就绪前调用只记下来，就绪后生效。 */
      setExpression: function (label) {
        if (disposed) { return false; }
        if (label && exprLabels.length && exprLabels.indexOf(label) < 0) { return false; }
        exprOverride = label || null;
        if (st.ready) { applyMode(); } else { emit(); }
        return true;
      },
      expressionLabels: function () { return exprLabels.slice(); },
      setModel: function (id) {
        if (disposed || !MODELS[id]) { return false; }        /* 只接受随包模型（当前仅 kurisu_c） */
        if (id === st.model) { return true; }
        return false;                                          /* 换模型需重新 mount（运行时无热换 API） */
      },
      dispose: function () {
        disposed = true;
        try { if (fpsTimer) { clearInterval(fpsTimer); fpsTimer = null; } } catch (e) {}
        try { if (player) { player.onUpdate = null; } } catch (e) {}
        try { var ctx = canvas.getContext('2d'); if (ctx) { ctx.clearRect(0, 0, canvas.width, canvas.height); } } catch (e) {}
        player = null; metadata = null;
        setState('disposed', { ready: false });
      },
      status: function () {
        var s = {}; for (var k in st) { s[k] = st[k]; }
        s.memMB = memMB(); s.gpu = !!(typeof EmotePlayer !== 'undefined' && EmotePlayer.device && EmotePlayer.device.initialized);
        s.disposed = disposed;
        return s;
      },
      onStatus: function (fn) { if (typeof fn === 'function') { cbs.push(fn); fn(inst.status()); } return inst; },
    };

    /* ---- 懒加载链：先等 boot 时机，再等可见 ---- */
    waitForBoot().then(function (why) {
      st.bootWhy = why;
      return whenVisible(canvas);
    }).then(function (vis) {
      st.visible = vis === 'visible' || vis === 'no-io';
      if (disposed) { return; }
      setState('loading');
      return loadAll();
    }).catch(function (err) {
      setState('error', { error: String((err && err.message) || err) });
    });

    function loadAll() {
      var t0 = performance.now();
      /* 0) Emscripten 运行时需要先看到 Module 配置（页面上没有就由本脚本兜住） */
      if (!window.Module) { window.Module = { TOTAL_MEMORY: 512 * 1024 * 1024 }; }
      /* 1) 两个经典脚本（顺序注入，保证 driver 先于 player；已在页面上就跳过） */
      return RUNTIME_URLS.reduce(function (p, url) {
        return p.then(function () {
          if (url.indexOf('FreeMoteDriver') >= 0 && window.EmoteDriver_Initialized) { return null; }
          if (url.indexOf('emoteplayer') >= 0 && typeof EmotePlayer !== 'undefined') { return null; }
          return injectScript(url);
        });
      }, Promise.resolve()).then(function () {
        /* 2) 等 Emscripten 运行时真的就绪（异步），再进加载器 */
        return waitForEmote(20000);
      }).then(function () {
        /* 3) 加载器（ESM，动态 import；路径是站内相对路径，无 CDN） */
        return import(/* webpackIgnore: true */ LOADER_URL);
      }).then(function (loader) {
        if (disposed) { return; }
        if (typeof EmotePlayer === 'undefined') { throw new Error('EmotePlayer 未就绪（插件未注册）'); }
        var pr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
        var cssW = canvas.clientWidth || canvas.width, cssH = canvas.clientHeight || canvas.height;
        /* ★V2.2：画布内部尺寸必须跟 CSS 盒子一致（否则 Sprite 留下的 321×432 会被拉进 282×597 变形） */
    if (cssW > 0 && cssH > 0) { canvas.width = Math.round(cssW * pr); canvas.height = Math.round(cssH * pr); }
        EmotePlayer.createRenderCanvas(canvas.width, canvas.height);
        player = new EmotePlayer(canvas);
        if (!EmotePlayer.device.initialized) { throw new Error('WebGL 初始化失败'); }
        return loader.loadModel(registry.dir, function (msg) { setState('loading', { note: String(msg) }); })
          .then(function (res) {
            metadata = res.metadata;
            var bytes = res.bytes.length + res.bytes.byteLength || null;
            player.loadData(res.bytes);
            if (!player.playerId || !player.isCharaProfileAvailable) { throw new Error('模型无法识别'); }
            st.bytes = bytes;
            /* ★V2.3：引擎初始化会把画布改回它自己的尺寸 ⇒ 模型加载完再按 CSS 盒子重设一次，
               并在新尺寸上重排取景（finishSetup 里的 scale/coord 依赖 canvas.width/height） */
            var rr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
            if (canvas.clientWidth > 0 && canvas.clientHeight > 0) {
              canvas.width = Math.round(canvas.clientWidth * rr);
              canvas.height = Math.round(canvas.clientHeight * rr);
            }
            finishSetup(loader, registry, t0);
            return true;
          });
      });
    }

    function finishSetup(loader, registry, t0) {
      var bounds = player.charaBounds;
      var crop = typeof opts.crop === 'number' ? opts.crop : registry.crop;
      (function fit() {
        var bottom = bounds.top + (bounds.bottom - bounds.top) * crop;
        var scale = Math.min(canvas.width / (bounds.right - bounds.left), canvas.height / (bottom - bounds.top)) * 0.96;
        player.setScale(scale, 0);
        player.setCoord(-(bounds.left + bounds.right) / 2 * scale, -(bounds.top + bottom) / 2 * scale, 0);
      })();

      var selectors = metadata.customSelectorList.filter(function (c) { return c.enabled; });
      updateParts = function () {
        var values = {};
        for (var i = 0; i < selectors.length; i++) { values[selectors[i].label] = player.getVariable(selectors[i].label); }
        if (registry.arm !== null && registry.arm !== undefined) { values.arm_type = registry.arm; }
        var out = loader.partVariables(metadata, values);
        for (var label in out) { player.setVariable(label, out[label], 0); }
      };
      var expressions = player.mainTimelineLabels.filter(function (l) { return l.indexOf('表情_') === 0; });
      exprLabels = expressions.slice();               /* ★V5：把可选表情表暴露给 setExpression 调用方 */
      function pick(re) { for (var i = 0; i < expressions.length; i++) { if (re.test(expressions[i])) { return expressions[i]; } } return null; }
      /* 表情表是日文（实测 28 个），没有"思考"表情：thinking 用 呆然（退路 困る） */
      var MODE_LABEL = {
        idle: pick(/平常/) || expressions[0],
        thinking: pick(/呆然/) || pick(/困る/) || pick(/慌てる/) || expressions[0],
        speaking: pick(/平常/) || expressions[0],
      };
      var eyes = metadata.eyeControl.filter(function (c) { return c.enabled && c.varL && c.varR; });

      player.onUpdate = function () {
        if (disposed) { return; }
        updateParts();
        for (var i = 0; i < eyes.length; i++) {
          var v = player.getVariable(eyes[i].label);
          player.setVariable(eyes[i].varL, v); player.setVariable(eyes[i].varR, v);
        }
        if (speaking && !document.hidden) { player.setVariable('face_talk', (Math.sin(performance.now() / 120) + 1) * 2.5); }
      };
      applyMode = function () {
        var label = exprOverride || MODE_LABEL[st.mode];   /* ★V5：有情绪覆盖位就优先用表情标签 */
        if (label) { player.diffTimelineSlot1 = ''; player.mainTimelineLabel = label; }
        speaking = st.mode === 'speaking';
        if (!speaking) { player.setVariable('face_talk', 0, 120); }
        emit();
      };
      applyMode();

      /* 帧率实测（1 秒窗口，只采一次，供 status() 读）
         ★2026-10-17 修（V2b）：原实现在挂载瞬间就开测，窗口正好与模型初始化/纹理上传重叠，
           报出 2 是计数器口径问题（不是渲染器真的 2fps）。改为挂载后 1.5s 再测，避开初始化抖动。 */
      (function measureFps() {
        var n = 0, t0 = 0;
        function tick() {
          n++;
          if (performance.now() - t0 < 1000) { requestAnimationFrame(tick); }
          else { st.fps = Math.round(n * 1000 / (performance.now() - t0)); emit(); }
        }
        setTimeout(function(){ t0 = performance.now(); requestAnimationFrame(tick); }, 1500);
      })();

      setState('ready', { ready: true, loadMs: Math.round(performance.now() - t0), expressions: expressions.length, modeLabels: MODE_LABEL });
    }

    NS._last = inst;          /* 便于调试：控制台 XKPhoneEmote._last.status() */
    return inst;
  };
})();
