/* xk-after.js —— 可以推迟到页面加载完再做的事（2026-11-09 从 head-meta.html 内联里搬出来，配合 CSP 去 unsafe-inline）
   ① 注册 Service Worker（PWA 离线壳），只注册、不预缓存大资产；延迟 1.8 s，不跟首屏抢带宽。
   ② 把 <meta name="wb-api"> 的原值抄到 <html data-wb-api> 再清空 meta：
      数据页因此改读同源静态快照（static/api/public/*），只有 /ai/ 问答与 SSE 回退用这份原值。
      ?live=1 时保留原值继续打实时接口。
   ③ 无障碍兜底：nav.dock 的 aria-label / aria-current、#termFeed 的 aria-live、
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

  /* ② wb-api 抄写 + 清空 */
  try {
    var m = document.querySelector('meta[name="wb-api"]');
    if (m) {
      var v = m.getAttribute('content') || '';
      if (v) { document.documentElement.setAttribute('data-wb-api', v); }
      if (location.search.indexOf('live=1') < 0) { m.setAttribute('content', ''); }
    }
  } catch (e) { }

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
