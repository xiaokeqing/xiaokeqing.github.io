/* 2026-11-10 打开一页时，让右侧手机（#phone）用气泡介绍这一页在干什么。
   文案来自 /api/page-intro.json（同源、1.2KB、缓存一年），不内联进 HTML。 */
(function () {
  'use strict';
  var KEY = 'xk-intro-v1';
  function cached() {
    try { var raw = sessionStorage.getItem(KEY); return raw ? JSON.parse(raw) : null; } catch (e) { return null; }
  }
  function norm(p) { return /\/$/.test(p) || /\.html?$/.test(p) ? p : p + '/'; }
  function pick(all) {
    if (!all) return null;
    var path = norm(location.pathname);
    if (all[path]) return all[path];
    if (path.indexOf('/posts/') === 0 && all['/posts/']) return all['/posts/'];
    if (path.indexOf('/tools/') === 0 && all['/tools/']) return all['/tools/'];
    return all['/'] || null;
  }
  function say(text) {
    var line = document.getElementById('phoneLine');
    if (!text || !line) return;
    if ((line.textContent || '').trim() === text.trim()) return;
    var i = 0, step = Math.max(12, Math.min(42, Math.round(1200 / Math.max(1, text.length))));
    line.textContent = '';
    var inst = window.XKPhoneEmote || window.__xkPhoneEmoteInst || null;
    var setMode = function (m) {
      try {
        if (inst && typeof inst.setMode === 'function') inst.setMode(m);
        else if (inst && inst.status && window.XKPhoneEmote && window.XKPhoneEmote.setMode) window.XKPhoneEmote.setMode(m);
      } catch (e) {}
    };
    setMode('speaking');
    (function tick() {
      if (i >= text.length) { setTimeout(function () { setMode('idle'); }, 900); return; }
      line.textContent += text.charAt(i++);
      setTimeout(tick, step);
    })();
  }
  function boot() {
    var all = cached();
    if (all) { setTimeout(function () { say(pick(all)); }, 1500); return; }
    try {
      fetch('/api/page-intro.json', { credentials: 'same-origin' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) {
          if (!j) return;
          try { sessionStorage.setItem(KEY, JSON.stringify(j)); } catch (e) {}
          setTimeout(function () { say(pick(j)); }, 1500);
        })
        .catch(function () {});
    } catch (e) {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
