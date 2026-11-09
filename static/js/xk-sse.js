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
  /* 同源快照模式会清空 meta 的 content（只读数据页改读同源快照），但 SSE 没有快照可读，
     清空前原值抄在 <html data-wb-api>（见 layouts/partials/xk-demo/head-meta.html），这里回退到它。 */
  var API = ((meta && meta.getAttribute('content'))
    || document.documentElement.getAttribute('data-wb-api') || '').replace(/\/+$/, '');
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
  /* ★2026-11-08 跨境慢链路降级：
     - HELLO_MS：EventSource 的 open 事件不代表后端真的推了帧（跨境链路上 TCP 能连上、SSE 帧却
       迟迟不过河，页面就挂着一个"假活"的长连接）。3s 内没收到 hello 帧 ⇒ 判定这条连接没有价值，
       角标写"SSE 连接慢 · 已切轮询"并**主动 close()**，把连接还给轮询；
     - RETRY_COOLDOWN：关掉之后 30s 内不再重连（原逻辑只在 visibilitychange 里重开，但每次回到前台
       都重开一次、每次还得再等 3s，慢链路上等于反复拖页面）。 */
  var HELLO_MS = 3000, RETRY_COOLDOWN = 30000;
  var helloTimer = null, retryAt = 0;

  function stopEs() {
    if (helloTimer) { clearTimeout(helloTimer); helloTimer = null; }
    if (!es) { return; }
    try { es.close(); } catch (err) {}
    es = null;
  }

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
    /* 地图脉冲：只有后端给了 cc 才闪；没有就不画（不本地猜国家） */
    if (d.cc && window.__xkGeoPulse) { window.__xkGeoPulse(d.cc, d.sev); }
  }

  function open() {
    try { es = new EventSource(API + '/api/public/stream'); } catch (e) { setBadge('SSE 不可用 · 走轮询', true); return; }

    /* 3s 内必须见到 hello 帧；见不到就主动断开，不做"假活"的长连接 */
    if (helloTimer) { clearTimeout(helloTimer); }
    helloTimer = setTimeout(function () {
      helloTimer = null;
      if (ok || !es) { return; }
      setBadge('SSE 连接慢 · 已切轮询', true);
      retryAt = Date.now() + RETRY_COOLDOWN;
      stopEs();
    }, HELLO_MS);

    es.addEventListener('hello', function (e) {
      ok = true;
      retryAt = 0;
      if (helloTimer) { clearTimeout(helloTimer); helloTimer = null; }
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
       连续失败就把角标改成"走轮询"，不打扰页面（轮询本来就在跑）。
       关闭后 30s 内不再重试：慢链路上反复重连只会把页面拖慢，轮询已经能兜住。 */
    es.onerror = function () {
      if (!ok) { setBadge('SSE 未连上 · 走轮询', true); }
      else { setBadge('SSE 断开 · 走轮询', true); }
      retryAt = Date.now() + RETRY_COOLDOWN;
      stopEs();
      ok = false;
    };
  }

  /* 页面隐藏时不断连（轮询也在跑），但避免后台标签页里反复重连：只在前台且过了冷却期才重开 */
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && !es && Date.now() >= retryAt) { open(); }
  });

  open();
})();
