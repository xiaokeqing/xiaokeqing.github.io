/* ============================================================================
   知微安全实验室 · 工作台数据层
   ----------------------------------------------------------------------------
   职责：把 /api/public/* 的数据渲染进工作台页面（首页状态行 / 告警看板），
        并处理三态：正常 / 降级（数据源不可达）/ 快照兜底（注明"X 分钟前的快照"）

   【三条硬规矩】
   1. 不写死任何数字。模板里只有占位（—），数字一律来自接口。
   2. 不用 innerHTML 拼数据。告警标题/规则名里可能带攻击者可控的字符串
      （用户名、URL、User-Agent），拼 HTML 就是把 XSS 引到自己的展示页上。
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
  var params = new URLSearchParams(location.search);
  var override = params.get('wb_api');
  var API = (override || (meta && meta.content) || '').replace(/\/+$/, '');
  if (override) {
    console.warn('[workbench] 接口地址被 URL 参数覆盖为 ' + API + '（仅本地预览用）');
  }
  // 调试开关：无头浏览器软件渲染下 backdrop-filter 会卡死，截图时用 wb_noblur=1 关掉
  if (params.get('wb_noblur')) {
    document.documentElement.classList.add('wb-no-blur');
  }

  var SNAP_PREFIX = 'wb:snap:v3:';
  var TIMEOUT_MS = 9000;
  var SEV_RANK = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, INFO: 0 };
  var SEV_LABEL = { CRITICAL: '严重', HIGH: '高危', MEDIUM: '中危', LOW: '低危', INFO: '提示' };

  /* 告警看板的前端状态：一次取数，过滤/排序都在本地做（数据只有 200 条窗口，够快） */
  var state = { data: null, stale: false, snapAt: null, filter: 'ALL' };

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

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  /** "2026-10-11 22:28:13" → 今天显示 "22:28"，非今天显示 "10-11 22:28" */
  function fmtTime(s, withSeconds) {
    if (!s || typeof s !== 'string') { return '—'; }
    var m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/);
    if (!m) { return s; }
    var now = new Date();
    var isToday = (m[1] === String(now.getFullYear()) && m[2] === pad(now.getMonth() + 1) && m[3] === pad(now.getDate()));
    var t = m[4] + ':' + m[5] + (withSeconds ? ':' + m[6] : '');
    return isToday ? t : (m[2] + '-' + m[3] + ' ' + t);
  }

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
      default: return 'wb-badge--info2';
    }
  }

  function srcClass(key) {
    return String(key || '').toUpperCase() === 'SURICATA' ? 'wb-badge--net' : 'wb-badge--host';
  }

  function srcShort(key) {
    var k = String(key || '').toUpperCase();
    if (k === 'SURICATA') { return '网络'; }
    if (k === 'WAZUH') { return '主机'; }
    return key || '—';
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

  function load(path, render) {
    api(path).then(function (data) {
      saveSnap(path, data);
      render(data, false, null);
    }).catch(function (err) {
      var snap = readSnap(path);
      if (snap) {
        render(snap.data, true, snap.at);
        notice('warn', '后端暂时不可达（' + err.message + '），下面是 ' + minutesAgo(snap.at)
          + '抓取的快照，不是实时数据。');
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
      : kind === 'danger' ? 'wb-badge--danger'
        : kind === 'warn' ? 'wb-badge--warn' : 'wb-badge--muted');
  }

  /* ==================== 首页：一行状态 ==================== */

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
      var n = (a.windowCount === undefined || a.windowCount === null) ? '—' : a.windowCount;
      cnt.textContent = (a.windowFull ? n + '+' : n);
      cnt.title = a.windowDescription || '';
    }

    var degraded = data.dataSource && data.dataSource.degraded;
    setBadge($('#wb-live-badge'), degraded ? '数据源不可达' : '实时', degraded ? 'warn' : 'ok');

    // 右栏"系统状态"：后端版本从 nodes[0].detail 里取（形如 "build 9bfac33"）
    var build = $('#wb-build');
    if (build) {
      var n1 = (data.nodes || [])[0] || {};
      build.textContent = String(n1.detail || '').replace('build ', '') || '—';
    }
    var win = $('#wb-window');
    if (win) {
      // 右栏是窄表格式布局，这里只放短值；完整口径在"实时告警"栏目的 KPI 卡片里
      if (a.windowSize) {
        win.textContent = '最近 ' + a.windowSize + (a.windowFull ? '+' : '') + ' 条';
        win.title = a.windowDescription || '';
      } else {
        win.textContent = '—';
      }
    }
  }

  /* ==================== 告警看板 ==================== */

  function kpi(label, value, noteText, cls) {
    var box = el('div', 'wb-kpi');
    box.appendChild(el('span', 'wb-kpi__label', label));
    box.appendChild(el('span', 'wb-kpi__value' + (cls ? ' ' + cls : ''), value));
    if (noteText) { box.appendChild(el('span', 'wb-kpi__note', noteText)); }
    return box;
  }

  function sevBucketsFrom24(bySev) {
    return ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'].map(function (k) {
      return { key: k, label: SEV_LABEL[k], count: (bySev && bySev[k]) || 0 };
    });
  }

  function renderKpis(data) {
    var host = $('#wb-kpis');
    if (!host) { return; }
    clear(host);
    host.setAttribute('aria-busy', 'false');

    if (!data) {
      host.appendChild(el('div', 'wb-kpi', '数据源不可达'));
      return;
    }

    var s24 = data.stats24h || {};
    var has24 = !!s24.available;
    var sev = (has24 ? s24.bySeverity : null) || {};
    var winSev = {};
    ((data.stats || {}).bySeverity || []).forEach(function (b) { winSev[b.key] = b.count; });

    // 口径：能用 24 小时聚合就用它；拿不到就退回窗口口径，并把口径写在卡片上。
    // 关键是不能让"严重 0"同时意味着"没告警"和"没统计到"两种完全不同的意思。
    var note = has24 ? ('近 ' + (s24.windowHours || 24) + ' 小时') : '取数窗口内';
    var pick = function (k) { return has24 ? (sev[k] || 0) : (winSev[k] || 0); };

    // 总数用四档之和，不用后端返回的 total：
    // OpenSearch 的 hits.total 默认截断在 10000，直接显示会得到一个"看着精确其实偏小"的数字。
    // 四档之和是权威的（就是同一份聚合结果）。
    var total24 = 0;
    ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'].forEach(function (k) { total24 += (sev[k] || 0); });

    host.appendChild(kpi('近 24 小时', has24 ? total24 : (data.rawTotal || 0), has24 ? '全部告警' : '窗口口径'));
    host.appendChild(kpi('严重', pick('CRITICAL'), note, pick('CRITICAL') > 0 ? 'wb-kpi__value--crit' : ''));
    host.appendChild(kpi('高危', pick('HIGH'), note, pick('HIGH') > 0 ? 'wb-kpi__value--high' : ''));
    host.appendChild(kpi('中危', pick('MEDIUM'), note));
    host.appendChild(kpi('低危 / 提示', pick('LOW') + pick('INFO'), note));
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
    var axis = $('#wb-trend-axis');
    var totalEl = $('#wb-trend-total');
    var peakEl = $('#wb-trend-peak');
    if (!host) { return; }

    clear(host);
    if (axis) { clear(axis); }

    var trend = (data && data.stats24h && data.stats24h.available && data.stats24h.trend)
      || (data && data.stats && data.stats.trend)
      || [];
    if (!trend.length) {
      host.appendChild(el('div', 'wb-hint', '无数据'));
      if (totalEl) { totalEl.textContent = '—'; }
      if (peakEl) { peakEl.textContent = '—'; }
      return;
    }

    var counts = trend.map(function (p) { return p.count || 0; });
    var max = counts.reduce(function (m, c) { return Math.max(m, c); }, 0);
    var sum = counts.reduce(function (m, c) { return m + c; }, 0);
    var peakIdx = counts.indexOf(max);

    if (totalEl) { totalEl.textContent = sum; }
    if (peakEl) {
      peakEl.textContent = max > 0 ? (max + ' 条 · ' + trend[peakIdx].time) : '0';
    }

    trend.forEach(function (p) {
      var col = el('div', 'wb-trend__col');
      var bar = el('div', 'wb-trend__bar' + ((p.count || 0) === 0 ? ' wb-trend__bar--zero' : ''));
      // 有数据的柱子按比例给高度；0 值只留一点底纹，用来和"这段没数据"区分开
      bar.style.height = (p.count || 0) === 0 ? '4px' : Math.max(6, Math.round(p.count / max * 100)) + '%';
      col.appendChild(bar);
      col.title = p.time + ' · ' + (p.count || 0) + ' 条';
      host.appendChild(col);
    });

    // 时间轴横排：按【下标】每 4 个柱标一个。
    // 之前按"整点能被 4 整除"标，遇到 23:00 起的序列会连着标出 23:00 和 00:00 两个标签，挤成一团。
    if (axis) {
      trend.forEach(function (p, i) {
        axis.appendChild(el('span', 'wb-trend__tick', (i % 4 === 0) ? p.time : ''));
      });
    }
  }

  function severityRank(a) {
    return SEV_RANK[String(a.severity || '').toUpperCase()] || 0;
  }

  function renderFilters(data) {
    var host = $('#wb-filters');
    if (!host) { return; }
    clear(host);

    var list = (data && data.list) || [];
    var counts = { ALL: list.length };
    list.forEach(function (a) {
      var k = String(a.severity || '').toUpperCase();
      counts[k] = (counts[k] || 0) + 1;
    });

    var defs = [['ALL', '全部'], ['CRITICAL', '严重'], ['HIGH', '高危'], ['MEDIUM', '中危'], ['LOW', '低危']];
    defs.forEach(function (d) {
      var key = d[0];
      var n = counts[key] || 0;
      var chip = el('button', 'wb-chip' + (state.filter === key ? ' is-active' : ''), d[1] + ' ' + n);
      chip.type = 'button';
      chip.setAttribute('data-filter', key);
      chip.addEventListener('click', function () {
        state.filter = key;
        renderFilters(state.data);
        renderStream(state.data);
      });
      host.appendChild(chip);
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

    var all = (data.list || []).slice();
    // 高危置顶：先按级别降序，同级按时间降序 —— 让人一眼先看到要处理的
    all.sort(function (x, y) {
      var d = severityRank(y) - severityRank(x);
      if (d !== 0) { return d; }
      return String(y.endTime || y.occurredAt || '').localeCompare(String(x.endTime || x.occurredAt || ''));
    });

    var list = state.filter === 'ALL'
      ? all
      : all.filter(function (a) { return String(a.severity || '').toUpperCase() === state.filter; });

    if (note) {
      note.textContent = data.aggregated
        ? ('共 ' + all.length + ' 条聚合告警 · 高危置顶 · 点任意一条展开原始明细')
        : '未启用聚合，逐条展示';
    }

    if (!list.length) {
      host.appendChild(el('div', 'wb-empty', state.filter === 'ALL'
        ? '当前取数窗口内没有告警 —— 这可能是真的安静，也可能是采集没生效。以自用界面的实时数据为准。'
        : '该级别在当前窗口内没有告警。'));
      return;
    }

    list.forEach(function (a) {
      var row = el('details', 'wb-row');
      row.setAttribute('data-agg', a.aggId || '');

      var sum = el('summary');
      sum.appendChild(el('span', 'wb-row__time', fmtTime(a.endTime || a.occurredAt)));
      var sev = el('span', 'wb-badge wb-row__sev ' + sevClass(a.severity), a.severityLabel || SEV_LABEL[String(a.severity || '').toUpperCase()] || '—');
      sum.appendChild(sev);
      var src = el('span', 'wb-badge wb-row__src ' + srcClass(a.source), srcShort(a.source));
      sum.appendChild(src);
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
            line.appendChild(el('span', 'wb-row__time', fmtTime(m.occurredAt, true)));
            line.appendChild(el('span', 'wb-badge ' + sevClass(m.severity), m.severityLabel || '—'));
            line.appendChild(el('span', 'wb-member__title', m.title || m.ruleName || ''));
            line.appendChild(el('span', 'wb-row__ip', (m.srcIp || '—') + (m.srcGeo ? ' · ' + m.srcGeo : '')));
            body.appendChild(line);
          });
          var foot = el('div', 'wb-hint', '共 ' + members.length + ' 条原始告警 · 原始 payload 与内网地址不在此接口返回');
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
    state.data = data;
    state.stale = stale;
    state.snapAt = snapAt;

    if (!stale) { clearNotice(); }

    if (data && data.dataSource && data.dataSource.degraded && !stale) {
      notice('danger', '告警数据源当前不可达（wazuhMode=' + data.dataSource.wazuhMode
        + '）。本页不展示内置样本，只显示为空。');
    }

    var badge = $('#wb-mode-badge');
    if (badge) {
      var degraded = !data || (data.dataSource && data.dataSource.degraded);
      setBadge(badge, degraded ? '数据源不可达' : (stale ? '快照数据' : '实时'),
        degraded ? 'danger' : (stale ? 'warn' : 'ok'));
    }

    setSynced(data ? fmtTime(data.generatedAt, true) : (snapAt ? minutesAgo(snapAt) : '—'));
    renderKpis(data);

    var s24 = (data && data.stats24h) || null;
    var has24 = !!(s24 && s24.available);
    var sevTitle = $('#wb-sev-title');
    if (sevTitle) { sevTitle.textContent = '级别分布 · ' + (has24 ? '近 24 小时' : '取数窗口内'); }
    var srcTitle = $('#wb-src-title');
    if (srcTitle) { srcTitle.textContent = '来源分布 · 最近 ' + ((data && data.windowSize) || 200) + ' 条'; }

    renderDist('#wb-by-severity',
      has24 ? sevBucketsFrom24(s24.bySeverity) : (data && data.stats && data.stats.bySeverity),
      function (b) {
        switch (String(b.key).toUpperCase()) {
          case 'CRITICAL': return 'wb-dist__bar--crit';
          case 'HIGH': return 'wb-dist__bar--high';
          case 'MEDIUM': return 'wb-dist__bar--med';
          /* 低危 / 提示用蓝灰，刻意不用绿色：绿在本站只表示"在线"，
             否则"绿 = 好"会和"绿 = 低危"打架，图就开始骗人 */
          default: return 'wb-dist__bar--low';
        }
      });
    renderDist('#wb-by-source', data && data.stats && data.stats.bySource, function (b) {
      return String(b.key).toUpperCase() === 'SURICATA' ? 'wb-dist__bar--net' : 'wb-dist__bar--host';
    });
    renderTrend(data);
    renderFilters(data);
    renderStream(data);
  }

  /* ==================== 启动 ==================== */

  var hasStatus = !!$('#wb-status');    // 首页 hero 里那一行状态
  var hasBoard = !!$('#wb-kpis');       // 告警面板（首页内联面板 / /alerts/ 页共用同一份标记）

  function loadStatus() { if (hasStatus) { load('/api/public/overview', renderHome); } }
  function loadBoard() { if (hasBoard) { load('/api/public/alerts', renderAlerts); } }

  loadStatus();
  loadBoard();

  var refresh = $('#wb-refresh');
  if (refresh) {
    refresh.addEventListener('click', loadBoard);
  }

  /* ---------- 栏目切换：顶栏每一项对应下面一块内容，只显示当前栏目 ---------- */
  var VIEWS = {
    home: { id: 'view-home' },
    notes: { id: 'view-notes' },
    alerts: { id: 'view-alerts' },
    report: { id: 'view-report' },   // 蜜罐战报 + 红队评测合并成一个栏目
    kb: { id: 'view-kb' }
  };

  var layout = document.querySelector('.wb-layout');

  function showView(name, scroll) {
    if (!VIEWS[name]) { name = 'home'; }
    Object.keys(VIEWS).forEach(function (k) {
      var box = document.getElementById(VIEWS[k].id);
      if (box) { box.hidden = (k !== name); }
    });
    // 当前栏目写在容器上：CSS 据此决定"全幅 banner"还是"极淡页面底纹"
    root.setAttribute('data-wb-view', name);
    // tab 条高亮同步（顶栏与 tab 条是两个入口，状态必须一致）
    document.querySelectorAll('[data-wb-tab]').forEach(function (t) {
      t.classList.toggle('is-active', t.getAttribute('data-wb-tab') === name);
    });
    if (scroll !== false && layout && layout.scrollIntoView) {
      layout.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  if (layout) {
    function openView(name, e) {
      if (!VIEWS[name]) { return false; }
      if (e) { e.preventDefault(); }
      showView(name);
      if (history.replaceState) { history.replaceState(null, '', '#' + name); }
      return true;
    }

    // 顶栏里用 /#xxx 的项
    document.querySelectorAll('#menu a[href*="/#"]').forEach(function (a) {
      var name = (a.getAttribute('href') || '').split('#')[1];
      if (!VIEWS[name]) { return; }
      a.addEventListener('click', function (e) { openView(name, e); });
    });

    // 中栏 tab 条 + 主页"栏目说明"里的进入按钮
    document.querySelectorAll('[data-wb-tab], [data-wb-open]').forEach(function (el2) {
      var name = el2.getAttribute('data-wb-tab') || el2.getAttribute('data-wb-open');
      if (!VIEWS[name]) { return; }
      el2.addEventListener('click', function (e) { openView(name, e); });
    });

    // 直接带 hash 进来（分享链接 / 从别的页面点栏目）
    var initial = (location.hash || '').replace('#', '');
    showView(VIEWS[initial] ? initial : 'home', false);

    window.addEventListener('hashchange', function () {
      var name = (location.hash || '').replace('#', '');
      showView(VIEWS[name] ? name : 'home', false);
    });
  }

  // 页面回到前台时刷新一次（接口有 15 秒缓存，不会造成压力）
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') {
      loadStatus();
      loadBoard();
    }
  });
})();
