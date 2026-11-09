/* xk-after.js —— 可以推迟到页面加载完再做的事（2026-11-09 从 head-meta.html 内联里搬出来，配合 CSP 去 unsafe-inline）
   ① 注册 Service Worker（PWA 离线壳），只注册、不预缓存大资产；延迟 1.8 s，不跟首屏抢带宽。
   ② 无障碍兜底：nav.dock 的 aria-label / aria-current、#termFeed 的 aria-live、
      以及 .xk-skip 跳转链（xk-demo 页不引 site.css，样式表里那份收不到）。 */
(function () {
  'use strict';

  /* ① Service Worker */
  function regSW() {
    try {
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(function () { });
      }
    } catch (e) { }
  }
  if (document.readyState === 'complete') { setTimeout(regSW, 1800); }
  else { addEventListener('load', function () { setTimeout(regSW, 1800); }); }

  /* ② wb-api 抄写 + 清空 —— 2026-11-09 移到 xk-boot.js（阻塞脚本）：
        数据页的 xk-bind.js 是 body 里的普通脚本，会比这里（defer）更早执行，
        放在这里会导致它读到 demo 域名、去打 ~600 B/s 的隧道，整屏"读不到"。 */

  /* ③ 无障碍兜底 */
  function a11y() {
    var d = document, n = d.querySelector('nav.dock');
    if (n) {
      n.setAttribute('aria-label', '站内主导航');
      var a = n.querySelector('a.on');
      if (a) { a.setAttribute('aria-current', 'page'); }
    }
    var t = d.getElementById('termFeed');
    if (t) { t.setAttribute('aria-live', 'polite'); t.setAttribute('aria-atomic', 'false'); }
    if (!d.querySelector('.xk-skip')) {
      var s = d.createElement('a');
      s.className = 'xk-skip';
      s.href = '#content';
      s.textContent = '跳到主要内容';
      d.body.insertBefore(s, d.body.firstChild);
    }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', a11y); }
  else { a11y(); }
})();
