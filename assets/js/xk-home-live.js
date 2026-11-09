/* 首页顶部实时数据条（2026-11-09）
   目的：一进站就能看到真实数字（24h 拦截 / 严重 / 最新事件时间），而不是只有一张 CRT 照片。
   数据：同源快照 /api/public/alerts.js（data.stats24h.* 与 data.list[0].time）。
   口径：取不到就整条隐藏 —— 不显示 0，也不编样例。 */
(function () {
  var bar = document.getElementById('xkHbar');
  if (!bar) return;
  var elTotal = document.getElementById('xkHbarTotal');
  var elCrit = document.getElementById('xkHbarCrit');
  var elLast = document.getElementById('xkHbarLast');
  var elAge = document.getElementById('xkHbarAge');

  function fmt(n) {
    if (typeof n !== 'number' || !isFinite(n)) return null;
    return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  /* 数字滚动：从 0 涨到目标值，600ms 内完成；reduce-motion 时直接给终值 */
  function countUp(node, target) {
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || target < 1000) { node.textContent = fmt(target); return; }
    var t0 = 0, dur = 600;
    function step(ts) {
      if (!t0) t0 = ts;
      var k = Math.min(1, (ts - t0) / dur);
      var eased = 1 - Math.pow(1 - k, 3);
      node.textContent = fmt(target * eased);
      if (k < 1) requestAnimationFrame(step);
      else node.textContent = fmt(target);
    }
    requestAnimationFrame(step);
  }

  function ageText(iso) {
    if (!iso) return null;
    var t = Date.parse(String(iso).replace(' ', 'T'));
    if (isNaN(t)) return null;
    var s = Math.max(0, Math.round((Date.now() - t) / 1000));
    if (s < 90) return s + ' 秒前';
    if (s < 5400) return Math.round(s / 60) + ' 分钟前';
    return Math.round(s / 3600) + ' 小时前';
  }

  function show(json) {
    var d = json && json.data;
    if (!d || !d.stats24h || d.stats24h.available !== true) return;
    var total = d.stats24h.total;
    var crit = d.stats24h.bySeverity && d.stats24h.bySeverity.CRITICAL;
    if (typeof total !== 'number') return;
    countUp(elTotal, total);
    var c = fmt(crit);
    if (c) { elCrit.textContent = c; elCrit.parentNode.hidden = false; }
    var last = d.list && d.list[0] && d.list[0].time;
    if (last) { elLast.textContent = String(last).slice(11, 19) || last; elLast.parentNode.hidden = false; }
    var a = ageText(json.snapshotAt || d.generatedAt);
    if (a) elAge.textContent = '快照 ' + a;
    bar.hidden = false;
  }

  fetch('/api/public/alerts.js', { credentials: 'omit' })
    .then(function (r) { if (!r.ok) throw new Error('http ' + r.status); return r.text(); })
    .then(function (t) {
      var m = t.match(/window\.[A-Za-z0-9_$]+\s*=\s*([\s\S]*?)\s*;?\s*$/);
      show(JSON.parse(m ? m[1] : t));
    })
    .catch(function () { /* 取不到就保持隐藏，不显示 0 */ });
})();
