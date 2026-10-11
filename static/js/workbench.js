/* ============================================================================
   知微安全实验室 · 工作台数据层
   ----------------------------------------------------------------------------
   职责：把 /api/public/* 的数据渲染进工作台页面，并处理三态：
     正常 / 降级（数据源不可达）/ 快照兜底（后端不通时显示"上次同步于 X 分钟前"）

   【三条硬规矩】
   1. 不写死任何数字。模板里只留占位（—），数字一律来自接口。
   2. 不用 innerHTML 拼数据。告警标题/规则名里可能带攻击者可控的字符串
      （用户名、URL、User-Agent…），拼 HTML 就是把 XSS 引到自己的展示页上。
      这里统一用 textContent / createElement。
   3. 接口不通就如实说。有快照就显示快照 + 明确标注时间，没有就显示错误，
      绝不拿假数据把版面填满 —— 工作台的价值就在于"看到的就是真的"。
   ========================================================================== */
(function () {
  'use strict';

  var root = document.querySelector('[data-wb-page]');
  if (!root) {
    return;
  }

  var page = root.getAttribute('data-wb-page');   // home | alerts

  /* ---------- 接口地址 ---------- */
  var meta = document.querySelector('meta[name="wb-api"]');
  var override = new URLSearchParams(location.search).get('wb_api');
  var API = (override || (meta && meta.content) || '').replace(/\/+$/, '');
  if (override) {
    // 只用于本地预览：把页面指向本机 SSH 转发的后端，避免线上域名在国内解析抖动。
    console.warn('[workbench] 接口地址被 URL 参数覆盖为 ' + API + '（仅本地预览用）');
  }

  var SNAP_PREFIX = 'wb:snap:v2:';
  var TIMEOUT_MS = 9000;

  /* ==================== 工具 ==================== */

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined && text !== null) { n.textContent = String(text); }
    return n;
  }

  function clear(node) {
    while (node && node.firstChild) { node.removeChild(node.firstChild); }
  }

  function $(sel) { return document.querySelector(sel); }

  /** "2026-10-11 21:28:13" → 今天显示 "21:28:13"，非今天显示 "10-11 21:28" */
  function fmtTime(s) {
    if (!s || typeof s !== 'string') { return '—'; }
    var m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/);
    if (!m) { return s; }
    var today = new Date();
    var isToday = (m[1] === String(today.getFullYear())
      && m[2] === pad(today.getMonth() + 1)
      && m[3] === pad(today.getDate()));
    return isToday ? (m[4] + ':' + m[5] + ':' + m[6]) : (m[2] + '-' + m[3] + ' ' + m[4] + ':' + m[5]);
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  function minutesAgo(ms) {
    var d = Math.max(0, Math.round((Date.now() - ms) / 60000));
    return d <= 0 ? '刚刚' : (d + ' 分钟前');
  }

  function sevClass(key) {
    switch (String(key || '').toUpperCase()) {
      case 'CRITICAL': return 'wb-badge--crit';
      case 'HIGH': return 'wb-badge--high';
      case 'MEDIUM': return 'wb-badge--med';
      case 'LOW': return 'wb-badge--low';
      default: return 'wb-badge--info';
    }
  }

  function srcClass(key) {
    return String(key || '').toUpperCase() === 'SURICATA' ? 'wb-badge--net' : 'wb-badge--host';
  }

  function srcShort(label, key) {
    if (String(key || '').toUpperCase() === 'SURICATA') { return '网络'; }
    if (String(key || '').toUpperCase() === 'WAZUH') { return '主机'; }
    return label || key || '—';
  }

  /* ==================== 取数 + 快照 ==================== */

  function api(path) {
    var ctrl = ('AbortController' in window) ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, TIMEOUT_MS) : null;

    return fetch(API + path, {
      method: 'GET',
      mode: 'cors',
      cache: 'no-store',
      signal: ctrl ? ctrl.signal : undefined,
      headers: { 'Accept': 'application/json' }
    }).then(function (res) {
      if (timer) { clearTimeout(timer); }
      if (!res.ok) { throw new Error('HTTP ' + res.status); }
      return res.json();
    }).then(function (body) {
      if (!body || body.code !== 200 || !body.data) {
        throw new Error((body && body.message) || '接口返回结构异常');
      }
      return body.data;
    }).catch(function (err) {
      if (timer) { clearTimeout(timer); }
      throw err;
    });
  }

  function saveSnap(path, data) {
    try { localStorage.setItem(SNAP_PREFIX + path, JSON.stringify({ at: Date.now(), data: data })); } catch (e) { /* 隐私模式下写不了，忽略 */ }
  }

  function readSnap(path) {
    try {
      var raw = localStorage.getItem(SNAP_PREFIX + path);
      if (!raw) { return null; }
      var obj = JSON.parse(raw);
      return (obj && obj.data) ? obj : null;
    } catch (e) { return null; }
  }

  /**
   * 取数并渲染；失败时退到快照，再失败就显示错误。
   * @param {string} path 接口路径
   * @param {function} render 渲染函数 (data, stale, snapAt)
   */
  function load(path, render) {
    api(path).then(function (data) {
      saveSnap(path, data);
      render(data, false, null);
    }).catch(function (err) {
      var snap = readSnap(path);
      if (snap) {
        render(snap.data, true, snap.at);
        notice('warn', '后端暂时不可达（' + err.message + '），下面是 '
          + minutesAgo(snap.at) + '抓取的快照，不是实时数据。');
      } else {
        notice('danger', '取不到数据：' + err.message
          + '。本页不展示任何估算或示例数据 —— 宁可空着，也不给假数字。');
        render(null, false, null);
      }
    });
  }

  function notice(kind, text) {
    var box = $('#wb-notice');
    if (!box) { return; }
    box.className = 'wb-notice wb-notice--' + (kind === 'danger' ? 'danger' : 'warn');
    box.textContent = text;
    box.hidden = false;
  }

  function clearNotice() {
    var box = $('#wb-notice');
    if (box) { box.hidden = true; box.textContent = ''; }
  }

  function setSynced(text) {
    var n = $('#wb-synced');
    if (n) { n.textContent = text || '—'; }
  }

  function setBadge(node, text, kind) {
    if (!node) { return; }
    node.textContent = text;
    node.className = 'wb-badge ' + (kind === 'ok' ? 'wb-badge--ok'
      : kind === 'danger' ? 'wb-badge--danger' : 'wb-badge--warn');
  }

  /* ==================== 首页状态条 ==================== */

  function renderHome(data) {
    clearNotice();
    if (!data) {
      setBadge($('#wb-live-badge'), '数据源不可达', 'warn');
      ['srv1', 'srv2'].forEach(function (id) {
        var box = document.querySelector('[data-wb-node="' + id + '"]');
        if (!box) { return; }
        var dot = box.querySelector('.wb-dot');
        var val = box.querySelector('[data-wb-node-val]');
        if (dot) { dot.className = 'wb-dot wb-dot--bad'; }
        if (val) { val.textContent = '未知'; }
      });
      var cnt = $('#wb-alert-count');
      if (cnt) { cnt.textContent = '—'; }
      return;
    }

    (data.nodes || []).forEach(function (node) {
      var box = document.querySelector('[data-wb-node="' + node.id + '"]');
      if (!box) { return; }
      var dot = box.querySelector('.wb-dot');
      var val = box.querySelector('[data-wb-node-val]');
      if (dot) { dot.className = 'wb-dot ' + (node.online ? 'wb-dot--ok' : 'wb-dot--bad'); }
      if (val) { val.textContent = node.online ? '在线' : '不可达'; }
      box.title = node.probe + (node.detail ? '（' + node.detail + '）' : '');
    });

    var a = data.alerts || {};
    var cnt = $('#wb-alert-count');
    if (cnt) {
      var today = (a.todayInWindow === undefined || a.todayInWindow === null) ? '—' : a.todayInWindow;
      cnt.textContent = today;
      cnt.title = a.windowDescription || '';
    }
    var note = $('#wb-alert-note');
    if (note) { note.textContent = a.windowDescription ? ('（' + a.windowDescription + '）') : ''; }

    var degraded = data.dataSource && data.dataSource.degraded;
    setBadge($('#wb-live-badge'), degraded ? '数据源不可达' : '实时', degraded ? 'warn' : 'ok');
    setSynced(fmtTime(data.generatedAt));
  }

  /* ==================== 告警看板 ==================== */

  function kpi(label, value, noteText, cls) {
    var box = el('div', 'wb-kpi');
    box.appendChild(el('span', 'wb-kpi__label', label));
    box.appendChild(el('span', 'wb-kpi__value' + (cls ? ' ' + cls : ''), value));
    if (noteText) { box.appendChild(el('span', 'wb-kpi__note', noteText)); }
    return box;
  }

  function renderKpis(data) {
    var host = $('#wb-kpis');
    if (!host) { return; }
    clear(host);
    host.setAttribute('aria-busy', 'false');

    if (!data) {
      host.appendChild(el('div', 'wb-kpi', '数据源不可达，本页不展示告警'));
      return;
    }

    var stats = data.stats || {};
    var bySev = {};
    (stats.bySeverity || []).forEach(function (b) { bySev[b.key] = b.count; });
    var bySrc = {};
    (stats.bySource || []).forEach(function (b) { bySrc[b.key] = b.count; });

    var rawTotal = data.rawTotal || 0;
    var aggTotal = data.total || 0;
    var crit = bySev.CRITICAL || 0;
    var high = bySev.HIGH || 0;

    host.appendChild(kpi('原始告警', rawTotal, data.windowSize ? ('最近 ' + data.windowSize + ' 条窗口') : ''));
    host.appendChild(kpi('聚合后', aggTotal, data.aggregated ? ('时间窗 ' + data.windowMinutes + ' 分钟') : '未启用聚合'));
    host.appendChild(kpi('严重', crit, '需人工处置', crit > 0 ? 'wb-kpi__value--crit' : ''));
    host.appendChild(kpi('高危', high, '优先关注', high > 0 ? 'wb-kpi__value--high' : ''));
    host.appendChild(kpi('网络告警', bySrc.SURICATA || 0, 'Suricata（经 Wazuh 聚合）'));
  }

  function renderDist(sel, buckets, toneFn) {
    var host = $(sel);
    if (!host) { return; }
    clear(host);
    if (!buckets || !buckets.length) {
      host.appendChild(el('div', 'wb-hint', '无数据'));
      return;
    }
    var max = buckets.reduce(function (m, b) { return Math.max(m, b.count || 0); }, 0) || 1;
    buckets.forEach(function (b) {
      var row = el('div', 'wb-dist__row');
      row.appendChild(el('span', 'wb-dist__label', b.label || b.key));
      var track = el('div', 'wb-dist__track');
      var bar = el('div', 'wb-dist__bar' + (toneFn ? ' ' + toneFn(b) : ''));
      bar.style.width = Math.max(2, Math.round((b.count || 0) / max * 100)) + '%';
      track.appendChild(bar);
      row.appendChild(track);
      row.appendChild(el('span', 'wb-dist__num', b.count || 0));
      row.title = (b.label || b.key) + '：' + (b.count || 0);
      host.appendChild(row);
    });
  }

  function renderTrend(data) {
    var host = $('#wb-trend');
    if (!host) { return; }
    clear(host);
    var trend = (data && data.stats && data.stats.trend) || [];
    if (!trend.length) {
      host.appendChild(el('div', 'wb-hint', '无数据'));
      return;
    }
    var max = trend.reduce(function (m, p) { return Math.max(m, p.count || 0); }, 0) || 1;
    trend.forEach(function (p, i) {
      var col = el('div', 'wb-trend__col');
      var bar = el('div', 'wb-trend__bar' + (p.count === max && max > 0 ? ' wb-trend__bar--peak' : ''));
      bar.style.height = Math.round((p.count || 0) / max * 100) + '%';
      col.appendChild(bar);
      // 每 4 小时标一个刻度，避免 24 个标签糊成一片
      col.appendChild(el('span', 'wb-trend__tick', (i % 4 === 0) ? p.time : ''));
      col.title = p.time + ' · ' + (p.count || 0) + ' 条';
      host.appendChild(col);
    });
  }

  function renderStream(data) {
    var host = $('#wb-stream');
    var note = $('#wb-stream-note');
    if (!host) { return; }
    clear(host);

    if (!data) {
      host.appendChild(el('div', 'wb-empty', '告警数据源不可达。这里不会显示示例数据。'));
      if (note) { note.textContent = ''; }
      return;
    }

    var list = data.list || [];
    if (note) {
      note.textContent = data.aggregated
        ? ('聚合口径：同源 IP + 同类型 + ' + data.windowMinutes + ' 分钟窗；点任意一条展开原始明细')
        : '未启用聚合，逐条展示';
    }
    if (!list.length) {
      host.appendChild(el('div', 'wb-empty', '当前取数窗口内没有告警 —— 这可能是真的安静，也可能是采集没生效。以自用界面的实时数据为准。'));
      return;
    }

    list.forEach(function (a) {
      var row = el('details', 'wb-row');
      row.setAttribute('data-agg', a.aggId || '');

      var sum = el('summary');
      sum.appendChild(el('span', 'wb-row__time', fmtTime(a.endTime || a.occurredAt)));
      sum.appendChild(el('span', 'wb-badge wb-row__sev ' + sevClass(a.severity), a.severityLabel || a.severity || '—'));
      sum.appendChild(el('span', 'wb-badge wb-row__src ' + srcClass(a.source), srcShort(a.sourceLabel, a.source)));
      sum.appendChild(el('span', 'wb-row__title', a.title || a.ruleName || '（无标题）'));
      sum.appendChild(el('span', 'wb-row__ip', a.srcIp || '—'));
      sum.appendChild(el('span', 'wb-row__count', (a.count > 1) ? (a.count + ' ×') : ''));
      row.appendChild(sum);

      var body = el('div', 'wb-row__body');
      body.appendChild(el('div', 'wb-hint', '展开以读取原始明细…'));
      row.appendChild(body);

      var loaded = false;
      row.addEventListener('toggle', function () {
        if (!row.open || loaded || !a.aggId) { return; }
        loaded = true;
        clear(body);
        body.appendChild(el('div', 'wb-hint', '读取中…'));
        api('/api/public/alerts/' + encodeURIComponent(a.aggId)).then(function (d) {
          clear(body);
          var members = (d && d.members) || [];
          if (!members.length) {
            body.appendChild(el('div', 'wb-hint', '该簇的原始明细已超出当前窗口'));
            return;
          }
          members.forEach(function (m) {
            var line = el('div', 'wb-member');
            line.appendChild(el('span', 'wb-row__time', fmtTime(m.occurredAt)));
            line.appendChild(el('span', 'wb-badge ' + sevClass(m.severity), m.severityLabel || m.severity || '—'));
            line.appendChild(el('span', 'wb-member__title', m.title || m.ruleName || ''));
            line.appendChild(el('span', 'wb-row__ip', (m.srcIp || '—') + (m.srcGeo ? ' · ' + m.srcGeo : '')));
            body.appendChild(line);
          });
          var foot = el('div', 'wb-hint', '共 ' + members.length + ' 条原始告警；原始 payload 与内网地址不在此接口返回');
          foot.style.marginTop = '8px';
          body.appendChild(foot);
        }).catch(function (e) {
          clear(body);
          body.appendChild(el('div', 'wb-hint', '下钻失败：' + e.message));
          loaded = false;   // 允许重试
        });
      });

      host.appendChild(row);
    });
  }

  function renderAlerts(data, stale, snapAt) {
    if (!stale) { clearNotice(); }

    // 数据源降级时，即使有数据也要说清楚
    if (data && data.dataSource && data.dataSource.degraded && !stale) {
      notice('danger', '告警数据源当前不可达（wazuhMode=' + data.dataSource.wazuhMode
        + '）。本页不展示内置样本，只显示为空。');
    }

    var badge = $('#wb-mode-badge');
    if (badge) {
      var degraded = !data || (data.dataSource && data.dataSource.degraded);
      badge.textContent = degraded ? '数据源不可达' : (stale ? '快照数据' : '实时');
      badge.className = 'wb-badge ' + (degraded ? 'wb-badge--danger' : stale ? 'wb-badge--warn' : 'wb-badge--ok');
    }

    setSynced(data ? fmtTime(data.generatedAt) : (snapAt ? minutesAgo(snapAt) : '—'));
    renderKpis(data);
    renderDist('#wb-by-severity', data && data.stats && data.stats.bySeverity, function (b) {
      switch (b.key) {
        case 'CRITICAL': return 'wb-dist__bar--crit';
        case 'HIGH': return 'wb-dist__bar--high';
        case 'MEDIUM': return 'wb-dist__bar--med';
        case 'LOW': return 'wb-dist__bar--low';
        default: return '';
      }
    });
    renderDist('#wb-by-source', data && data.stats && data.stats.bySource, function (b) {
      return b.key === 'SURICATA' ? 'wb-dist__bar--net' : '';
    });
    renderTrend(data);
    renderStream(data);
  }

  /* ==================== 启动 ==================== */

  var refresh = $('#wb-refresh');

  if (page === 'alerts') {
    load('/api/public/alerts', renderAlerts);
    if (refresh) {
      refresh.addEventListener('click', function () {
        load('/api/public/alerts', renderAlerts);
      });
    }
  } else if (page === 'home') {
    load('/api/public/overview', renderHome);
  }

  // 页面回到前台时刷新一次（数据有 15 秒缓存，不会造成压力）
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') {
      if (page === 'alerts') { load('/api/public/alerts', renderAlerts); }
      if (page === 'home') { load('/api/public/overview', renderHome); }
    }
  });
})();
