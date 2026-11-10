/* ============================================================================
   xk-stats.js —— /alerts/ 总览（数据统计）的四张统计卡
   ----------------------------------------------------------------------------
   站主口径：「只有四种为什么还要做个统计图」→「为什么不多加几条」⇔ 维度要更多。
   四卡 2×2：攻击类型 Top5 · 三源占比 · 攻击来源国家 Top5 · 目标端口 Top5。

   数据（同源只读快照；浏览器加载后请求，不走构建期）：
     · /api/public/alerts.js → data.stats.byType      [{key,label,count}]（5 分钟原始窗口）
                             → data.stats.bySource    [{key,label,count}]（5 分钟原始窗口）
                             → data.stats.topPorts     ← 这份快照**没有**这个字段；
                               列表项也没有任何端口字段 ⇒ 端口卡只写「未取到（原因）」
     · /api/public/geo.js    → data.byCountry           [{country,countryName,count,uniqueIps,sharePercent}]
                               data.coverage.totalAlerts / data.available / data.reason

   纪律（跟 xk-kpi.js / xk-bind.js 同一条红线）：
     · 拿不到 ⇒ 整卡只显示一行「未取到（原因）」，**不写 0、不补样例、不拿别的数据凑**；
     · 快照里真实为 0 的行（如 BUILTIN 0 条）不画成 0 宽条，只在卡内脚注说明，避免看起来像编数；
     · 只有一个来源时如实画 1 行（不硬凑三行）；
     · 纯 DOM，无第三方库；只用 createElement / textContent（不拼 innerHTML）；
     · 任何异常都在本文件内吃掉 ⇒ pageerror 为 0。
   ========================================================================== */
(function () {
  'use strict';

  var root = document.getElementById('xkStatGrid');
  if (!root) return;

  var ALERTS_URL = '/api/public/alerts.js';
  var GEO_URL = '/api/public/geo.js';

  function f(n) {
    var v = Number(n);
    if (!isFinite(v)) return '—';
    return String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function card(name) {
    return root.querySelector('[data-xk-stat="' + name + '"]');
  }

  function getJSON(url) {
    try {
      return fetch(url, { credentials: 'same-origin' }).then(function (res) {
        if (!res || !res.ok) return null;
        return res.json().catch(function () { return null; });
      }).catch(function () { return null; });
    } catch (e) {
      return Promise.resolve(null);
    }
  }

  /* 整卡空态：一行「未取到（原因）」，条与脚注都不显示；绝不写 0。 */
  function miss(name, why) {
    var c = card(name);
    if (!c) return 0;
    var bars = c.querySelector('[data-xk-stat-bars]');
    var note = c.querySelector('[data-xk-stat-note]');
    var empty = c.querySelector('[data-xk-stat-empty]');
    if (bars) { bars.textContent = ''; bars.hidden = true; }
    if (note) { note.textContent = ''; note.hidden = true; }
    if (empty) {
      empty.textContent = '未取到（' + why + '）';
      empty.hidden = false;
    }
    c.setAttribute('data-xk-stat-rows', '0');
    return 0;
  }

  /* rows: [{label, count, share:(数字|null), title:(可选)}]；max 定条宽，share 是已算好的百分比数字。 */
  function render(name, rows, noteText) {
    var c = card(name);
    if (!c) return 0;
    rows = (rows || []).filter(function (r) {
      return r && isFinite(Number(r.count)) && Number(r.count) > 0;
    });
    if (!rows.length) return miss(name, '这份快照里没有可画的计数');

    var bars = c.querySelector('[data-xk-stat-bars]');
    var note = c.querySelector('[data-xk-stat-note]');
    var empty = c.querySelector('[data-xk-stat-empty]');
    if (!bars) return 0;

    var max = 0;
    rows.forEach(function (r) { var v = Number(r.count); if (v > max) max = v; });

    bars.textContent = '';
    rows.forEach(function (r) {
      var v = Number(r.count);
      var row = document.createElement('div');
      row.className = 'vb';

      var l = document.createElement('span');
      l.className = 'vb-l';
      l.textContent = r.label;
      l.title = r.title || r.label;

      var t = document.createElement('span');
      t.className = 'vb-t';
      var i2 = document.createElement('i');
      i2.className = 'vb-f';
      i2.style.width = (max > 0 ? Math.max(2, Math.round(100 * v / max)) : 0) + '%';
      t.appendChild(i2);

      var n = document.createElement('span');
      n.className = 'vb-n';
      n.textContent = f(v) + (r.share == null ? '' : ' · ' + r.share + '%');

      row.appendChild(l);
      row.appendChild(t);
      row.appendChild(n);
      bars.appendChild(row);
    });

    bars.hidden = false;
    if (empty) { empty.hidden = true; empty.textContent = ''; }
    if (note) {
      note.textContent = noteText || '';
      note.hidden = !noteText;
    }
    c.setAttribute('data-xk-stat-rows', String(rows.length));
    return rows.length;
  }

  function arr(v) { return Object.prototype.toString.call(v) === '[object Array]' ? v : null; }

  function pct(part, total) {
    var p = Number(part), t = Number(total);
    if (!isFinite(p) || !isFinite(t) || t <= 0) return null;
    return (100 * p / t).toFixed(1);
  }

  /* 快照窗口（分钟）：alerts.js 的 data.windowMinutes，缺省 5 */
  function win(data) {
    var m = Number(data && data.windowMinutes);
    return (isFinite(m) && m > 0) ? Math.round(m) : 5;
  }

  /* 攻击类型 Top5 ← stats.byType（服务端标签优先，前端不编 ATT&CK 映射）
     百分比分母 = 整个 byType 列表的合计（不是 Top5 那几行），列表多于 5 类时脚注写明取前 5。 */
  function cardType(stats, data) {
    var full = arr(stats.byType);
    if (!full) return miss('type', '这份快照没有 stats.byType 字段');
    var total = 0;
    full.forEach(function (x) { total += Number(x && x.count) || 0; });
    var list = full.slice().sort(function (a, b) { return (Number(b && b.count) || 0) - (Number(a && a.count) || 0); }).slice(0, 5);
    var rows = list.map(function (x) {
      var label = String((x && (x.label || x.key)) || '—');
      return {
        label: label,
        count: Number(x && x.count) || 0,
        share: pct(x && x.count, total),
        title: label + ' · ' + ((x && x.key) || '—')
      };
    });
    if (!rows.length) return miss('type', 'stats.byType 为空');
    var note = '近 ' + win(data) + ' 分钟原始窗口 · 共 ' + f(total) + ' 条（stats.byType，类型标签由服务端给）';
    if (full.length > list.length) note += '；此处取前 5 类';
    return render('type', rows, note);
  }

  /* 三源占比 ← stats.bySource；真实 0 条的行不画条，只在脚注点名，不冒充第三源 */
  function cardSource(stats, data) {
    var list = arr(stats.bySource);
    if (!list) return miss('source', '这份快照没有 stats.bySource 字段');
    var total = 0, zero = [];
    list.forEach(function (x) {
      var n = Number(x && x.count) || 0;
      total += n;
      if (n <= 0) zero.push(String((x && (x.label || x.key)) || '—'));
    });
    var pos = list.filter(function (x) { return (Number(x && x.count) || 0) > 0; })
      .sort(function (a, b) { return (Number(b && b.count) || 0) - (Number(a && a.count) || 0); });
    var rows = pos.map(function (x) {
      var label = String((x && (x.label || x.key)) || '—');
      return {
        label: label,
        count: Number(x && x.count) || 0,
        share: pct(x && x.count, total),
        title: label + ' · ' + ((x && x.key) || '—')
      };
    });
    if (!rows.length) return miss('source', 'bysource 计数全为 0');
    var note = '近 ' + win(data) + ' 分钟 · 共 ' + f(total) + ' 条（stats.bySource）';
    if (zero.length) note += '；' + zero.join(' / ') + ' 0 条不画';
    note += '；蜜罐 Cowrie 事件经 Wazuh 采集，这份快照未单列';
    return render('source', rows, note);
  }

  /* 攻击来源国家 Top5 ← /geo byCountry（24h；分母用覆盖告警数，脚注照实写） */
  function cardCountry(geo) {
    if (!geo) return miss('country', '请求 /api/public/geo.js 失败或超时');
    if (geo.available !== true) {
      return miss('country', '/geo 快照不可用' + (geo.reason ? '（' + String(geo.reason) + '）' : '（available=false）'));
    }
    var list = arr(geo.byCountry);
    if (!list) return miss('country', '这份快照没有 byCountry 字段');
    list = list.slice().sort(function (a, b) { return (Number(b && b.count) || 0) - (Number(a && a.count) || 0); }).slice(0, 5);
    var rows = list.map(function (x) {
      var name = String((x && (x.countryName || x.country)) || '—');
      var code = String((x && x.country) || '—');
      var t = name;
      if (name !== code) t = name + ' · ' + code;
      if (x && x.uniqueIps != null) t += ' · IP ' + f(x.uniqueIps) + ' 个';
      return {
        label: name,
        count: Number(x && x.count) || 0,
        share: (x && x.sharePercent != null) ? Number(x.sharePercent) : null,
        title: t
      };
    });
    if (!rows.length) return miss('country', '24h 窗口没有可定位的国家');
    var cov = geo.coverage || {};
    var note = '24 小时窗口';
    if (cov.totalAlerts != null) note += ' · 覆盖 ' + f(cov.totalAlerts) + ' 条告警';
    if (geo.countryCount != null) note += ' · ' + f(geo.countryCount) + ' 个国家';
    return render('country', rows, note);
  }

  /* 目标端口 Top5 ← 只认 alerts.js 的 stats.topPorts；没有就整卡写原因，不拿别的数据凑 */
  function cardPort(data) {
    var stats = (data && data.stats) || {};
    var list = arr(stats.topPorts);
    if (!list) return miss('port', '这份快照没有端口字段 · stats.topPorts 与列表项都没有端口');
    var rows = list.slice().sort(function (a, b) { return (Number(b && b.count) || 0) - (Number(a && a.count) || 0); }).slice(0, 5).map(function (x) {
      var label = String((x && (x.label || x.port)) || '—');
      return { label: label, count: Number(x && x.count) || 0, share: null, title: label };
    });
    if (!rows.length) return miss('port', 'stats.topPorts 为空');
    return render('port', rows, '近 5 分钟 · stats.topPorts');
  }

  function done() {
    var n = {
      type: Number(card('type') && card('type').getAttribute('data-xk-stat-rows') || 0),
      source: Number(card('source') && card('source').getAttribute('data-xk-stat-rows') || 0),
      country: Number(card('country') && card('country').getAttribute('data-xk-stat-rows') || 0),
      port: Number(card('port') && card('port').getAttribute('data-xk-stat-rows') || 0)
    };
    root.setAttribute('data-xk-stats', 'type:' + n.type + ' source:' + n.source + ' country:' + n.country + ' port:' + n.port);
    window.__xkStats = n;
  }

  function safe(fn) {
    try { return fn(); } catch (e) { return 0; }
  }

  Promise.all([getJSON(ALERTS_URL), getJSON(GEO_URL)]).then(function (res) {
    var alerts = res[0];
    var geo = res[1];
    var data = alerts && (alerts.data || alerts);
    var stats = (data && data.stats) || null;

    if (!stats) {
      miss('type', '请求 /api/public/alerts.js 失败或超时');
      miss('source', '请求 /api/public/alerts.js 失败或超时');
      miss('port', '请求 /api/public/alerts.js 失败或超时');
    } else {
      safe(function () { cardType(stats, data); });
      safe(function () { cardSource(stats, data); });
      safe(function () { cardPort(data); });
    }
    safe(function () { cardCountry(geo && (geo.data || geo)); });
    done();
  }).catch(function () {
    safe(function () { miss('type', '统计脚本取数异常'); });
    safe(function () { miss('source', '统计脚本取数异常'); });
    safe(function () { miss('country', '统计脚本取数异常'); });
    safe(function () { miss('port', '统计脚本取数异常'); });
    safe(done);
  });
})();
