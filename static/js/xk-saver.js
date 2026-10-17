/*! xk-saver.js — 极弱网省流模式（V3，2026-10-17）
 *
 * 触发条件（任一）：
 *   · navigator.connection.saveData === true
 *   · navigator.connection.effectiveType ∈ {slow-2g, 2g, 3g}
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
      : !!(c.saveData || /^(slow-2g|2g|3g)$/.test(c.effectiveType || ''));
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
    try {
      var st = document.createElement('style');
      st.id = 'xkSaverStyle';
      st.textContent =
        'html.xk-saver .plate{display:none!important}' +
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
