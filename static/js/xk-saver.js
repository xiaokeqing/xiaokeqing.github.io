/*! xk-saver.js — 极弱网省流模式（V3，2026-10-17）
 *
 * 触发条件（任一）：
 *   · navigator.connection.saveData === true
 *   · navigator.connection.effectiveType ∈ {slow-2g, 2g}（3g 不触发，避免正常网速被误判）
 *   · 地址栏 ?xk-saver=1（强制开，便于验收/排查）；?xk-saver=0 强制关
 * 省流时做什么：
 *   · 只保留底图；**不启动状态机**（不发任何剪辑图集的请求，最大的一块在 1.3MB 量级）
 *   · **不取** CRT 垫板 subtitle_frame_big.webp（373KB）—— 垫板改成 data-src + 1×1 占位，
 *     由本文件在**非省流**时才补回 src（正常网络的请求时机与之前几乎一致）
 *   · 右上角一行"省流模式：只加载背景"提示；点它 ⇒ 以 ?xk-saver=0 重新加载（看完整效果）
 * 纪律：不伪造画面、不假装加载完成；关掉省流就是关掉，请求照常发。
 */
(function () {
  'use strict';
  try {
    var c = navigator.connection || navigator.mozConnection || {};
    var force = null;
    try {
      var qs = new URLSearchParams(location.search);
      if (qs.get('xk-saver') === '1') force = true;
      else if (qs.get('xk-saver') === '0') force = false;
    } catch (e) { /* 老浏览器没有 URLSearchParams，忽略 */ }

    var saver = (force !== null) ? force
      : !!(c.saveData || /^(slow-2g|2g)$/.test(c.effectiveType || ''));
    window.__xkSaver = saver;

    var root = document.documentElement;

    /* 非省流：补回垫板的真 src（垫板在标记里是 data-src + 透明占位） */
    if (!saver) {
      var setPlate = function () {
        var p = document.querySelector('img.plate[data-src]');
        if (p && !p.getAttribute('src')) p.setAttribute('src', p.getAttribute('data-src'));
      };
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setPlate, { once: true });
      else setPlate();
      return;
    }

    root.classList.add('xk-saver');
    /* ★真正的"只出底图"：本文件在 <head> 里同步执行，早于页面其它脚本 ⇒ 在这里直接拦图。
       省流模式下，凡是 /kurisu/** 的图（角色图集、场景混合图、头像、垫板）一律不发请求，
       换成 1×1 透明像素；只留 /images/crt/desk.webp 那张底图（它由 CSS/预载引用，不走这里）。
       两层都拦：img.src = "..."（属性 setter）与 setAttribute('src', ...) —— 防某处绕过。
       正常网络（非省流）完全不受影响（这段代码根本不会执行）。 */
    var PX = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    var BLOCK = /\/kurisu\//i;
    try {
      var proto = HTMLImageElement.prototype;
      var d = Object.getOwnPropertyDescriptor(proto, 'src');
      if (d && d.set && d.get) {
        Object.defineProperty(proto, 'src', {
          configurable: true,
          get: d.get,
          set: function (v) {
            try { if (typeof v === 'string' && BLOCK.test(v)) v = PX; } catch (e) { }
            d.set.call(this, v);
          }
        });
      }
      var sa = Element.prototype.setAttribute;
      Element.prototype.setAttribute = function (name, value) {
        try {
          if (String(name).toLowerCase() === 'src' && this instanceof HTMLImageElement &&
            typeof value === 'string' && BLOCK.test(value)) value = PX;
        } catch (e) { }
        return sa.call(this, name, value);
      };
      /* 次重资源：省流时不取统一播放器（156KB）与三份清单/语料 JSON（≈380KB）—— 它们是"完整模式"才需要的 */
      var BLOCK_JS = /\/js\/(?:kurisu-player|phone-emote)\.js$/i;
      var BLOCK_JSON = /\/kurisu\/(?:manifest|video-manifest|voice\/bank)\.json$/i;
      var sdp = HTMLScriptElement.prototype;
      var sd = Object.getOwnPropertyDescriptor(sdp, 'src');
      if (sd && sd.set && sd.get) {
        Object.defineProperty(sdp, 'src', {
          configurable: true,
          get: sd.get,
          set: function (v) {
            try { if (typeof v === 'string' && BLOCK_JS.test(v)) v = 'data:text/javascript,'; } catch (e) { }
            sd.set.call(this, v);
          }
        });
      }
      var RealFetch = window.fetch;
      if (RealFetch) {
        window.fetch = function (input, init) {
          try {
            var u = (typeof input === 'string') ? input : (input && input.url) || '';
            if (BLOCK_JSON.test(u)) return Promise.resolve(new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } }));
          } catch (e) { }
          if (BLOCK_JSON.test(u)) return Promise.resolve(new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } }));
          return RealFetch.call(this, input, init);
        };
      }
      var RealOpen = XMLHttpRequest.prototype.open;
      /* 空闲预取（2s 后 requestIdleCallback 里拉三份 JSON）在省流下一律不派发 */
      try { window.requestIdleCallback = function () { return 0; }; } catch (e) { }
      XMLHttpRequest.prototype.open = function (method, url) {
        if (typeof url === 'string' && BLOCK_JSON.test(url)) url = 'data:application/json,{}';
        return RealOpen.call(this, method, url);
      };
    } catch (e) { /* 拦截失败也不影响"垫板不取"这条主行为 */ }
    try {
      var st = document.createElement('style');
      st.id = 'xkSaverStyle';
      st.textContent =
        'html.xk-saver .plate{display:none!important}' +
        /* ★首屏 ≤130KB 口径：省流时 CRT 内景（场景混合图 44KB）与机箱背板（lab.webp 58.5KB）都不该取。
           用 !important 覆盖掉样式表里的 background-image ⇒ 浏览器按"最终生效值"取图，那两张就不会发请求。 */
        'html.xk-saver .xk-scene,html.xk-saver .backplate{display:none!important;background-image:none!important}' +
        'html.xk-saver .crt::before,html.xk-saver .crt::after{background-image:none!important}' +
        'html.xk-saver .xk-idcap{background:rgba(6,12,16,.78)!important;' +
        'box-shadow:inset 0 0 0 1px rgba(120,200,220,.18)!important}' +
        '.xk-saver-badge{position:fixed;top:8px;right:8px;z-index:9999;font:12px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;' +
        'color:#9fe6f2;background:rgba(6,14,18,.82);border:1px solid rgba(120,200,220,.35);border-radius:6px;' +
        'padding:4px 9px;cursor:pointer;max-width:80vw;text-align:left}' +
        '.xk-saver-badge:hover{background:rgba(10,22,28,.95)}';
      (document.head || root).appendChild(st);
    } catch (e) { /* 样式注入失败也不影响"不发请求"这条主行为 */ }

    var badge = function () {
      if (!document.body || document.getElementById('xkSaverBadge')) return;
      var b = document.createElement('button');
      b.id = 'xkSaverBadge';
      b.className = 'xk-saver-badge';
      b.type = 'button';
      b.textContent = '省流模式：只加载背景';
      b.title = '当前网络较低（或手动开启）。点这里以完整模式重新加载。';
      b.onclick = function () {
        try {
          var u = new URL(location.href);
          u.searchParams.set('xk-saver', '0');
          location.href = u.toString();
        } catch (e) { location.search = '?xk-saver=0'; }
      };
      document.body.appendChild(b);
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', badge, { once: true });
    else badge();
  } catch (e) {
    try { window.__xkSaver = false; } catch (e2) { }
  }
})();
