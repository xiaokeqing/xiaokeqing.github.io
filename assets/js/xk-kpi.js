/* ============================================================================
   xk-kpi.js —— /alerts/ 顶部 KPI 卡的「24h 迷你趋势线 + 与上一份日报的环比」
   ----------------------------------------------------------------------------
   数据（同源、站内相对路径、页面加载后由浏览器请求）：
     · /api/public/alerts.js        → data.stats24h.{available,total,trend,windowHours,note}
     · /api/public/daily/index.json → days[0].{date,alertTotal}（最近一份已发布日报）
   纪律：
     · stats24h.available !== true / 请求失败 ⇒ sparkline、环比、窗口口径小字整块 hidden，
       不出现 0、不留空白框；
     · trend 的有效点 < 3 ⇒ 不画线、不渲染 SVG；
     · 上一份日报取不到 alertTotal ⇒ 环比写「— 无对比」，绝不猜；相等也写「— 无对比」；
     · 纯 DOM + SVG，无第三方库；只用 textContent / createElementNS（不拼 innerHTML）。
   ========================================================================== */
(function () {
  'use strict';

  var cell = document.getElementById('ohKpiCell');
  var win = document.getElementById('xkKpiWin');
  var delta = document.getElementById('xkKpiDelta');
  var spark = document.getElementById('xkKpiSpark');
  var sevC = document.getElementById('ohSevCritical');
  var sevH = document.getElementById('ohSevHigh');
  var guard = document.getElementById('ohGuardNote');
  if (!cell || !win || !delta || !spark) return;

  var NS = 'http://www.w3.org/2000/svg';
  var ALERTS_URL = '/api/public/alerts.js';
  var DAILY_URL = '/api/public/daily/index.json';

  function hideAll() {
    spark.hidden = true;
    spark.textContent = '';
    delta.hidden = true;
    delta.textContent = '';
    delta.removeAttribute('class');
    delta.removeAttribute('title');
    win.hidden = true;
    win.textContent = '';
    win.removeAttribute('title');
  }

  function getJSON(url) {
    try {
      return fetch(url, { credentials: 'same-origin' }).then(function (res) {
        if (!res || !res.ok) return null;
        return res.json().catch(function () { return null; });
      }).catch(function () { return null; });
    } catch (e) {
      return null;
    }
  }

  function svgNode(name, attrs) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, k)) n.setAttribute(k, attrs[k]);
    }
    return n;
  }

  /* 120×32 折线 + 面积渐变；有效点不足 3 个返回 false（调用方保持隐藏）。 */
  function drawSparkline(trend) {
    if (!Array.isArray(trend)) return false;
    var vals = [];
    for (var i = 0; i < trend.length; i++) {
      var v = trend[i] == null ? NaN : Number(trend[i].count);
      if (isFinite(v)) vals.push(v);
    }
    if (vals.length < 3) return false;

    var W = 120, H = 32, PX = 1.5, PT = 3.5, PB = 3.5;
    var lo = Math.min.apply(null, vals);
    var hi = Math.max.apply(null, vals);
    var range = hi - lo;
    var plotW = W - PX * 2;
    var plotH = H - PT - PB;
    var xOf = function (idx) { return PX + idx * plotW / (vals.length - 1); };
    var yOf = function (val) {
      if (range === 0) return PT + plotH / 2;
      return PT + plotH * (1 - (val - lo) / range);
    };

    var svg = svgNode('svg', {
      width: '120', height: '32', viewBox: '0 0 120 32',
      class: 'xk-kpi-sparkline', role: 'img',
      'aria-label': '最近 ' + vals.length + ' 小时拦截量趋势，最低 ' + lo + '，最高 ' + hi
    });

    var gid = 'xkKpiAreaGrad';
    var defs = svgNode('defs', {});
    var grad = svgNode('linearGradient', { id: gid, x1: '0', y1: '0', x2: '0', y2: '1' });
    grad.appendChild(svgNode('stop', { offset: '0%', 'stop-color': 'rgb(127,212,216)', 'stop-opacity': '0.12' }));
    grad.appendChild(svgNode('stop', { offset: '100%', 'stop-color': 'rgb(127,212,216)', 'stop-opacity': '0' }));
    defs.appendChild(grad);
    svg.appendChild(defs);

    var line = 'M' + xOf(0).toFixed(2) + ',' + yOf(vals[0]).toFixed(2);
    for (var j = 1; j < vals.length; j++) {
      line += 'L' + xOf(j).toFixed(2) + ',' + yOf(vals[j]).toFixed(2);
    }
    var base = (H - PB).toFixed(2);
    var area = line + 'L' + xOf(vals.length - 1).toFixed(2) + ',' + base +
      'L' + xOf(0).toFixed(2) + ',' + base + 'Z';

    svg.appendChild(svgNode('path', {
      d: area, class: 'xk-kpi-area', 'data-xk-kpi': 'area', fill: 'url(#' + gid + ')'
    }));
    svg.appendChild(svgNode('path', {
      d: line, class: 'xk-kpi-line', 'data-xk-kpi': 'line',
      fill: 'none', stroke: 'rgba(127,212,216,.9)', 'stroke-width': '1.6',
      'stroke-linecap': 'round', 'stroke-linejoin': 'round'
    }));

    spark.textContent = '';
    spark.appendChild(svg);
    spark.hidden = false;
    return true;
  }

  /* 最近一份日报 = days[] 里第一条 alertTotal 为正的（接口本来就倒序）。 */
  function pickPrevDay(json) {
    var days = json && json.days;
    if (!Array.isArray(days)) return null;
    for (var i = 0; i < days.length; i++) {
      var d = days[i];
      var n = d ? Number(d.alertTotal) : NaN;
      if (isFinite(n) && n > 0) return { total: n, date: d.date || '' };
    }
    return null;
  }

  function renderDelta(total, prev) {
    var text, cls;
    if (prev && prev.total > 0 && total > 0) {
      var pct = (total - prev.total) / prev.total * 100;
      var rounded = Math.round(pct * 10) / 10;
      if (!isFinite(rounded) || rounded === 0) {
        text = '— 无对比';
        cls = 'xk-kpi-flat';
      } else if (rounded > 0) {
        text = '较上一份日报 ▲ +' + rounded.toFixed(1) + '%';
        cls = 'xk-kpi-up';
      } else {
        text = '较上一份日报 ▼ ' + rounded.toFixed(1) + '%';
        cls = 'xk-kpi-down';
      }
      delta.title = '24h ' + total + ' 条 vs 日报 ' + (prev.date || '—') + ' ' + prev.total + ' 条';
    } else {
      text = '— 无对比';
      cls = 'xk-kpi-flat';
      delta.title = '上一份日报没有可用的 alertTotal —— 不猜';
    }
    delta.textContent = text;
    delta.className = 'xk-kpi-delta ' + cls;
    delta.hidden = false;
  }

  /* 两个快照并行取；任何一个失败都不抛到控制台。 */
  var alertsP = getJSON(ALERTS_URL);
  var dailyP = getJSON(DAILY_URL);

  Promise.all([alertsP, dailyP]).then(function (res) {
    var alerts = res[0];
    var daily = res[1];
    var data = alerts && (alerts.data || alerts);
    var s24 = data && data.stats24h;
    if (!s24 || s24.available !== true) {
      hideAll();
      return;
    }

    var hours = Number(s24.windowHours);
    if (isFinite(hours) && hours > 0) {
      win.textContent = hours + 'h';
      win.title = '窗口口径：滚动 ' + hours + ' 小时（stats24h.windowHours）';
      win.hidden = false;
    }

    if (!drawSparkline(s24.trend)) spark.hidden = true;

    var total = Number(s24.total);
    if (isFinite(total) && total > 0) {
      renderDelta(total, pickPrevDay(daily));
    } else {
      delta.hidden = true;
    }
  }).catch(hideAll);
})();


  /* ★2026-11-09 大屏改造：四个数同一份 alerts.js —— 严重 / 高危 / 护栏说明 */
  (function () {
    var f = function (n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); };
    fetch('/api/public/alerts.js', { credentials: 'same-origin' }).then(function (r) { return r && r.ok ? r.json() : null; }).then(function (d) {
      var s24 = d && d.data && d.data.stats24h;
      if (!s24 || s24.available !== true) return;
      var sev = s24.bySeverity || {};
      var big = document.getElementById('ohBlocked');
      if (big && s24.total != null) big.textContent = f(s24.total);
      var _c = document.getElementById('ohSevCritical');
      var _h = document.getElementById('ohSevHigh');
      var _g = document.getElementById('ohGuardNote');
      if (_c && sev.CRITICAL != null) _c.textContent = f(sev.CRITICAL);
      if (_h && sev.HIGH != null) _h.textContent = f(sev.HIGH);
      /* 严重度横条：自己画（不依赖 xk-viz 的初始化时序） */
      var box = document.querySelector('[data-vz-bars]');
      if (box) {
        var nt = document.querySelector('[data-vz-barsnote]');
        var DEF = [['CRITICAL','严重'],['HIGH','高危'],['MEDIUM','中危'],['LOW','低危']];
        var maxv = 0;
        DEF.forEach(function (d) { var v = Number(sev[d[0]] || 0); if (v > maxv) maxv = v; });
        box.textContent = '';
        DEF.forEach(function (d) {
          var v = Number(sev[d[0]] || 0);
          var row = document.createElement('div'); row.className = 'vb';
          var l = document.createElement('span'); l.className = 'vb-l'; l.textContent = d[1];
          var t = document.createElement('span'); t.className = 'vb-t';
          var i2 = document.createElement('i'); i2.className = 'vb-f vb-' + d[1];
          i2.style.width = (maxv ? Math.max(2, Math.round(100 * v / maxv)) : 0) + '%';
          t.appendChild(i2);
          var n = document.createElement('span'); n.className = 'vb-n';
          n.textContent = f(v) + (s24.total ? ' · ' + (100 * v / s24.total).toFixed(1) + '%' : '');
          row.appendChild(l); row.appendChild(t); row.appendChild(n);
          box.appendChild(row);
        });
        if (nt) nt.textContent = '共 ' + f(s24.total || 0) + ' 条（INFO 不计入分级）';
      }
      if (_g) {
        var blocked = (d.data && d.data.audit && d.data.audit.summary && d.data.audit.summary.blockedByGuard) || 0;
        if (blocked) _g.textContent = '处置策略未启用 · 护栏已拦 ' + f(blocked) + ' 次';
      }
    }).catch(function () { });
  })();
