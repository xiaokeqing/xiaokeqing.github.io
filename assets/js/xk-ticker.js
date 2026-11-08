/* ★2026-11-06 站主口径：顶栏中段放「实时攻击 ticker」——一进站就能看到"现在有人在打"。
   数据源复用已有只读端点 `{wb-api}/api/public/alerts?w=5`（和 /alerts/ 大屏同一个接口），
   不新增后端、不增加一次握手数：大屏本来就要拉它，这里只是拿同一份数据切出前几行。

   三条硬约束（都是踩过的坑）：
   1) 慢网不拉（html.xk-slow）：ticker 是"装饰"，不能跟首屏抢带宽；
   2) 失败静默隐藏，不留占位空洞（接口抖动时顶栏不能出现一条空槽）；
   3) 文案只做转义后的纯文本（来源 IP/手法来自日志，绝不用 innerHTML 拼）。 */
(function () {
  'use strict';
  var box = document.getElementById('dockTicker');
  if (!box) { return; }
  try {
    if (document.documentElement.classList.contains('xk-slow')) { return; }
  } catch (e) { }

  // 2026-11-08：head 的内联脚本会把接口原值抄到 <html data-wb-api> 后清空 meta（防爬），
  // 所以先读 data-wb-api，meta 只作为 JS 未执行时的兜底。
  var meta = document.querySelector('meta[name="wb-api"]');
  var api = document.documentElement.getAttribute('data-wb-api')
    || (meta && meta.getAttribute('content')) || '';
  if (!api) { return; }
  var items = [], idx = 0, timer = 0;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function paint() {
    if (!items.length) { return; }
    var it = items[idx % items.length];
    box.textContent = it.text;
    box.title = it.title;
    idx++;
  }
  function parse(data) {
    var list = (data && (data.list || data.data && data.data.list)) || [];
    var out = [];
    for (var i = 0; i < list.length && out.length < 8; i++) {
      var a = list[i] || {};
      var t = a.time || a.ts || a.timestamp || '';
      if (typeof t === 'string' && t.length >= 5) { t = t.slice(-8).replace('T', ' '); }
      var src = a.ip || a.src || a.srcIp || '';
      var act = a.ruleDesc || a.desc || a.actionDesc || a.method || a.rule || '';
      if (!src && !act) { continue; }
      out.push({
        text: (t ? t + ' · ' : '') + (src ? src + ' ' : '') + (act || '异常请求'),
        title: (a.raw || a.detail || act || '') + '（来自 /api/public/alerts，5 分钟窗口）'
      });
    }
    return out;
  }

  fetch(api + '/api/public/alerts?w=5', { credentials: 'omit' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (j) {
      if (!j) { return; }
      items = parse(j);
      if (!items.length) { return; }
      box.hidden = false;
      paint();
      timer = setInterval(paint, 6000);
    })
    .catch(function () { /* 静默：接口挂了就保持隐藏 */ });

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) { clearInterval(timer); }
    else if (items.length) { timer = setInterval(paint, 6000); }
  });
})();
