/* xk-sse —— 作战室的实时推送（SSE），2026-11-07
 *
 * 口径（为什么这么写）：
 *  1. 长连接不放在站点域（Netlify 只出静态文件），而是连到我们自己的 API 域
 *     <meta name="wb-api">，跨域由后端 CORS 白名单放行（xiaokeqing.cn / www / 本地调试域）。
 *  2. **SSE 只是加速层，不是唯一通路**：连不上 / 中途断了 / 后端 mode=MOCK，都直接关掉，
 *     页面继续用原来的 15s 轮询 —— 最差情况不比以前差，这是设计前提。
 *  3. 慢网不连（html.xk-slow）：长连接在 3G 上占一条连接还吃心跳，不值得。
 *  4. 行内容全部走 textContent 拼装（feedRow 内部已 escape），不碰 innerHTML 注入。
 */
(function () {
  var main = document.getElementById('content');
  if (!main || main.getAttribute('data-xk-ssr') !== 'monitor') { return; }
  if (!window.EventSource || !window.__xkFeedPush) { return; }
  if (document.documentElement.classList.contains('xk-slow')) { return; }
  /* 用户手动 ?xk-sse=0 关掉，便于排障 */
  if (location.search.indexOf('xk-sse=0') >= 0) { return; }

  var meta = document.querySelector('meta[name="wb-api"]');
  var API = ((meta && meta.getAttribute('content')) || '').replace(/\/+$/, '');
  if (!API) { return; }

  var badge = document.createElement('span');
  badge.id = 'xkSseBadge';
  badge.style.cssText = 'margin-left:8px;font:11px/1.6 ui-monospace,Consolas,monospace;'
    + 'color:#7FD4D8;border:1px solid rgba(127,212,216,.45);border-radius:6px;padding:1px 6px;opacity:.9';
  badge.textContent = 'SSE 连接中…';
  var host = document.querySelector('.term-hd, .mod-hd, #termFeed');
  if (host && host.parentElement) { host.parentElement.appendChild(badge); }

  function setBadge(txt, dim) {
    badge.textContent = txt;
    badge.style.color = dim ? '#8a9ba5' : '#7FD4D8';
    badge.style.borderColor = dim ? 'rgba(138,155,165,.35)' : 'rgba(127,212,216,.45)';
  }

  var es = null, ok = false, seen = {};

  /* 级别 → 既有行样式（lv-* 前缀的类在 xk.css 里已有；不认识的落 dns） */
  var CLS = { ssh: 'ssh', http: 'http', dns: 'dns', tls: 'tls', flow: 'dns', scan: 'scan', alert: 'scan' };

  function pushEvent(d) {
    if (!d || !d.time) { return; }
    var key = d.time + '|' + d.src + '|' + d.rule;
    if (seen[key]) { return; }
    seen[key] = 1;
    var ts = String(d.time).slice(-8);
    var kind = String(d.kind || '').toLowerCase();
    var text = (d.rule || '告警') + ' ← ' + (d.src || '—') + (d.count > 1 ? ' ×' + d.count : '');
    window.__xkFeedPush({ ts: ts, cls: CLS[kind] || 'dns', tag: '[' + (d.sev || kind || '事件') + ']', text: text });
  }

  function open() {
    try { es = new EventSource(API + '/api/public/stream'); } catch (e) { setBadge('SSE 不可用 · 走轮询', true); return; }

    es.addEventListener('hello', function (e) {
      ok = true;
      var d = {};
      try { d = JSON.parse(e.data); } catch (err) {}
      var m = d.mode || '?';
      setBadge(m === 'REAL' ? 'LIVE · SSE' : 'SSE ' + m + ' · 轮询兜底', m !== 'REAL');
    });

    es.addEventListener('alert', function (e) {
      var arr = [];
      try { arr = JSON.parse(e.data); } catch (err) { return; }
      if (Array.isArray(arr)) { arr.forEach(pushEvent); } else { pushEvent(arr); }
    });

    /* 后端满员是 503，EventSource 会按 Retry-After 反复重连 —— 这里只让浏览器自己重试一次节奏，
       连续失败就把角标改成"走轮询"，不打扰页面（轮询本来就在跑）。 */
    es.onerror = function () {
      if (!ok) { setBadge('SSE 未连上 · 走轮询', true); }
      else { setBadge('SSE 断开 · 走轮询', true); }
      try { es.close(); } catch (err) {}
      es = null;
      ok = false;
    };
  }

  /* 页面隐藏时不断连（轮询也在跑），但避免后台标签页里反复重连：只在前台重开 */
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && !es) { open(); }
  });

  open();
})();
