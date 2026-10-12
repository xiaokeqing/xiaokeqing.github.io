/* ============================================================================
   知微安全实验室 · 工作台数据层
   ----------------------------------------------------------------------------
   职责：把后台【公开只读】接口的数据渲染进页面。
     P1：/api/public/overview（首页状态行）、/api/public/alerts（告警看板）
     P2：/api/public/honeypot（蜜罐战报 · 攻防靶场）
         /api/public/audit   （处置审计 · 态势感知）
         /api/health         （系统状态：三个指纹 + 文档向量数，全局）
         以及 AI 研判 state 的措辞映射（当前端点不返回该字段，只做映射与样式）

   【四条硬规矩】
   1. 不写死任何数字。模板里只有占位（—），数字一律来自接口。
      接口没有的字段就标"未接入"（如服务器磁盘水位），绝不用别处的数字顶上。
   2. 不用 innerHTML 拼数据。告警标题/规则名里可能带攻击者可控的字符串
      （用户名、口令、URL、User-Agent），拼 HTML 就是把 XSS 引到自己的展示页上。
   3. 接口不通就如实说。有快照就显示快照 + 明确标注时间，没有就显示错误，
      绝不拿假数据把版面填满 —— 工作台的价值就在于"看到的就是真的"。
   4. 实时刷新只用【自适应轮询】：页面可见 2 秒一次、隐藏 20 秒一次。
      不用 SSE、不用 WebSocket、不保持长连接（匿名大屏不能占着服务端连接）。
   ========================================================================== */
(function () {
  'use strict';

  var root = document.querySelector('[data-wb-page]');    // 工作台页面（首页 / alerts）
  var sysCard = document.getElementById('wb-sys-card');    // 右栏系统状态卡
  var sysStrip = document.getElementById('wb-sys-strip');   // 其它页面的全局系统状态条
  if (!root && !sysCard && !sysStrip) {
    return;   // 这个页面既不取数也不显示系统状态，直接不产生任何请求
  }

  var page = root ? root.getAttribute('data-wb-page') : null;   // home | alerts

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
  var TIMELINE_LIMIT = 24;
  var ACTION_LIMIT = 20;

  /* ============================================================================
     AI 研判 state → 页面措辞（权威口径，前端只做映射，不改写、不美化）
     ----------------------------------------------------------------------------
     数据来源状态：公开只读端点【当前不返回】state / aiState 字段
     （2026-10-12 curl 实测 overview、alerts 的响应体里都没有该字段）。
     所以这里先把映射与样式做好：哪天端点带上该字段，告警流每行会自动多一枚
     状态标记，不需要改文案、也不需要改模板。
     未在表内的取值：原样显示 state 字符串 + "未识别状态"，绝不猜它的含义。
     ========================================================================== */
  var WB_STATE = {
    'model': { label: '模型研判', cls: 'model' },
    'input-insufficient': { label: '依据不足，不做定性', cls: 'input-insufficient' },
    'no-retrieval': { label: '未检索到依据，不给结论', cls: 'no-retrieval' },
    'retrieval-failed': { label: '检索不可用，未生成', cls: 'retrieval-failed' },
    'model-failed': { label: '模型不可用，未生成', cls: 'model-failed' },
    'rule-based': { label: '规则解析', cls: 'rule-based' }
  };

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

  /** 带 data-label 的单元格：窄屏时 CSS 用 ::before 显示列名，避免横向滚动 */
  function cell(label, text, cls) {
    var n = el('span', cls, text);
    n.setAttribute('data-label', label || '');
    return n;
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

  /** 387406 → "4 天 11 小时"；只用于 /api/health 的 uptimeMs */
  function fmtUptime(ms) {
    var n = Number(ms);
    if (!isFinite(n) || n < 0) { return '—'; }
    var min = Math.floor(n / 60000);
    var d = Math.floor(min / 1440);
    var h = Math.floor((min % 1440) / 60);
    var mi = min % 60;
    if (d > 0) { return d + ' 天 ' + h + ' 小时'; }
    if (h > 0) { return h + ' 小时 ' + mi + ' 分'; }
    return mi + ' 分钟';
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

  /** 把 [{key,count}] 变成 renderDist 需要的 [{label,key,count}] */
  function buckets(list) {
    return (list || []).map(function (b) {
      return { key: b.key, label: b.key, count: b.count };
    });
  }

  /* ---------- AI 研判 state 的渲染（口径见文件头的 WB_STATE） ---------- */

  function stateOf(rec) {
    if (!rec) { return ''; }
    var s = rec.state || rec.aiState;   // 字段名兼容两种写法，等端点定下来再收口
    return (s === undefined || s === null) ? '' : String(s).trim();
  }

  function stateBadge(raw) {
    var key = String(raw || '').trim();
    if (!key) { return null; }
    var m = WB_STATE[key];
    var node = el('span', 'wb-state wb-state--' + (m ? m.cls : 'unknown'), m ? m.label : (key + '（未识别状态）'));
    node.title = m
      ? ('state=' + key + ' → 页面措辞「' + m.label + '」')
      : ('state=' + key + '：不在权威口径表内，前端原样显示，不猜含义');
    return node;
  }

  /* ==================== 取数 + 快照 ==================== */

  function request(path) {
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
      if (!res.ok) {
        var e = new Error('HTTP ' + res.status);
        e.status = res.status;      // 429/5xx 要能被上层识别，用来退避
        throw e;
      }
      return res.json();
    }).catch(function (err) {
      if (timer) { clearTimeout(timer); }
      throw err;
    });
  }

  /** /api/public/*：带 {code,message,data} 信封 */
  function api(path) {
    return request(path).then(function (body) {
      if (!body || body.code !== 200 || !body.data) {
        throw new Error((body && body.message) || '接口返回结构异常');
      }
      return body.data;
    });
  }

  /** /api/health：扁平对象（没有 code/data 信封），所以单独一个取数函数 */
  function apiRaw(path) {
    return request(path).then(function (body) {
      if (!body || typeof body !== 'object') { throw new Error('接口返回结构异常'); }
      return body;
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

  /** 返回本次请求的 HTTP 状态（200 / 429 / …），供轮询层做退避；渲染错误已在内部处理 */
  function load(path, render, opts) {
    opts = opts || {};
    var noticeId = opts.noticeId || 'wb-notice';
    var fetcher = opts.raw ? apiRaw : api;

    return fetcher(path).then(function (data) {
      saveSnap(path, data);
      render(data, false, null);
      return 200;
    }).catch(function (err) {
      var snap = readSnap(path);
      var status = err.status || 0;
      if (snap) {
        render(snap.data, true, snap.at);
        noticeIn(noticeId, 'warn', status === 429
          ? '公开端点限流（HTTP 429）：已自动退避，稍后再试。框里是 ' + minutesAgo(snap.at) + '抓取的快照，不是实时数据。'
          : '后端暂时不可达（' + err.message + '），下面是 ' + minutesAgo(snap.at)
            + '抓取的快照，不是实时数据。');
      } else {
        noticeIn(noticeId, 'danger', status === 429
          ? '公开端点限流（HTTP 429），本次没取到数据；页面会自动退避重试。这里不会显示任何估算或示例数据。'
          : '取不到数据：' + err.message
            + '。本页不展示任何估算或示例数据 —— 宁可空着，也不给假数字。');
        render(null, false, null);
      }
      return status;
    });
  }

  function noticeIn(id, kind, text) {
    var box = document.getElementById(id);
    if (!box) { return; }
    box.className = 'wb-notice wb-notice--' + (kind === 'danger' ? 'danger' : 'warn');
    box.textContent = text;
    box.hidden = false;
  }

  function clearNoticeIn(id) {
    var box = document.getElementById(id);
    if (box) { box.hidden = true; box.textContent = ''; }
  }

  function notice(kind, text) { noticeIn('wb-notice', kind, text); }
  function clearNotice() { clearNoticeIn('wb-notice'); }

  function setSynced(text) {
    var n = $('#wb-synced');
    if (n) { n.textContent = text || '—'; }
  }

  function setText(id, text, title) {
    var n = document.getElementById(id);
    if (!n) { return; }
    n.textContent = (text === undefined || text === null) ? '—' : String(text);
    if (title !== undefined) { n.title = title; }
  }

  function setBadge(node, text, kind) {
    if (!node) { return; }
    node.textContent = text;
    node.className = 'wb-badge ' + (kind === 'ok' ? 'wb-badge--ok'
      : kind === 'danger' ? 'wb-badge--danger'
        : kind === 'warn' ? 'wb-badge--warn' : 'wb-badge--muted');
  }

  function setBadgeById(id, text, kind) { setBadge(document.getElementById(id), text, kind); }

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
      var cnt0 = $('#wb-alert-count');
      if (cnt0) { cnt0.textContent = '—'; }
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

    // 右栏"系统状态"卡里的告警窗口（口径与告警面板一致）。
    // 三个指纹与文档向量数来自 /api/health，见 renderSystemStatus()。
    var win = $('#wb-window');
    if (win) {
      if (a.windowSize) {
        win.textContent = '最近 ' + a.windowSize + (a.windowFull ? '+' : '') + ' 条';
        win.title = a.windowDescription || '';
      } else {
        win.textContent = '—';
      }
    }
  }

  /* ==================== 系统状态（/api/health） ====================
     字段（curl 实测）：buildSha / sourceSha / artifactMd5 / documentVectors /
     vectorStore / uptimeMs / status / application / buildTime / fingerprint。
     接口【没有】磁盘水位字段 → 固定显示"未接入"，不留空、不编造。 */

  function setSys(key, text, title) {
    var nodes = document.querySelectorAll('[data-wb-sys="' + key + '"]');
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].textContent = (text === undefined || text === null || text === '') ? '—' : String(text);
      if (title !== undefined) { nodes[i].title = title; }
    }
  }

  function renderSystemStatus(h, stale, snapAt) {
    if (sysStrip && !sysCard) { sysStrip.hidden = false; }

    if (!h) {
      setSys('build', '取数失败');
      setSys('source', '取数失败');
      setSys('md5', '取数失败');
      setSys('vectors', '取数失败');
      setSys('store', '取数失败');
      setSys('uptime', '取数失败');
      setSys('status', '不可达');
      setSys('disk', '未接入', '接口没有返回磁盘水位字段');
      setBadge(document.querySelector('[data-wb-sys="status"]'), '不可达', 'danger');
      return;
    }

    setSys('build', h.buildSha || '—', '声称版本（来自环境变量）');
    setSys('source', h.sourceSha || '—', '服务器源码版本');
    setSys('md5', h.artifactMd5 || '—', '镜像内 jar 的 MD5：三个指纹里最硬的一个');
    setSys('vectors', (h.documentVectors === undefined || h.documentVectors === null) ? '—' : h.documentVectors,
      '知识库文档向量条数，来自 ' + (h.vectorStore ? ('向量库 ' + h.vectorStore) : '/api/health'));
    setSys('store', h.vectorStore || '—');
    setSys('uptime', fmtUptime(h.uptimeMs), '进程已运行时长');
    setSys('disk', '未接入', '接口没有返回磁盘水位字段 —— 不编造');

    var statusNode = document.querySelector('[data-wb-sys="status"]');
    if (statusNode) {
      var s = String(h.status || '').toLowerCase();
      var label = s === 'ok' ? (stale ? '正常（快照）' : '正常')
        : s === 'degraded' ? '降级'
          : (h.status ? String(h.status) : '—');
      setBadge(statusNode, label, s === 'ok' ? (stale ? 'warn' : 'ok') : 'warn');
      statusNode.title = 'status=' + (h.status || '—') + (stale && snapAt ? '（快照：' + minutesAgo(snapAt) + '）' : '');
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

  function renderDist(sel, list, toneFn) {
    var host = $(sel);
    if (!host) { return; }
    clear(host);
    if (!list || !list.length) {
      host.appendChild(el('div', 'wb-hint', '无数据'));
      return;
    }
    var max = list.reduce(function (m, b) { return Math.max(m, b.count || 0); }, 0) || 1;
    list.forEach(function (b) {
      var row = el('div', 'wb-dist__row');
      var label = b.label || b.key || '—';
      var labelNode = el('span', 'wb-dist__label', label);
      labelNode.title = label;
      row.appendChild(labelNode);
      var track = el('div', 'wb-dist__track');
      var bar = el('div', 'wb-dist__bar' + (toneFn ? ' ' + toneFn(b) : ''));
      bar.style.width = Math.max(2, Math.round((b.count || 0) / max * 100)) + '%';
      track.appendChild(bar);
      row.appendChild(track);
      row.appendChild(el('span', 'wb-dist__num', b.count || 0));
      row.title = label + '：' + (b.count || 0);
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
      // AI 研判状态：端点目前不返回 state 字段 → 这里什么都不加；
      // 一旦带了该字段，就会按权威口径显示"模型研判 / 依据不足，不做定性 / …"
      var sb = stateBadge(stateOf(a));
      if (sb) { sum.appendChild(sb); }
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
            var msb = stateBadge(stateOf(m));
            if (msb) { line.appendChild(msb); }
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

  /* ==================== 处置审计（/api/public/audit） ==================== */

  var MODE_CLASS = { REAL: 'wb-badge--info', MOCK: 'wb-badge--muted', BLOCKED: 'wb-badge--warn' };

  function renderAudit(data, stale, snapAt) {
    var host = $('#wb-audit-kpis');
    if (!host) { return; }

    if (!stale) { clearNoticeIn('wb-audit-notice'); }

    var badge = document.getElementById('wb-audit-badge');
    if (badge) {
      setBadge(badge, (!data ? '数据源不可达' : (stale ? '快照数据' : '实时')) + (data && data.readOnly ? ' · 只读' : ''),
        !data ? 'danger' : (stale ? 'warn' : 'ok'));
    }
    setText('wb-audit-synced', data ? fmtTime(data.generatedAt, true) : (snapAt ? minutesAgo(snapAt) : '—'));

    clear(host);
    host.setAttribute('aria-busy', 'false');

    if (!data) {
      host.appendChild(el('div', 'wb-kpi', '数据源不可达'));
      setText('wb-audit-note', '');
      renderAuditBlocks(null);
      renderAuditActions(null);
      return;
    }

    var s = data.summary || {};
    var note = s.note || '';
    host.appendChild(kpi('封禁总数', (s.blockTotal === undefined ? '—' : s.blockTotal), '来自处置审计留痕文件'));
    host.appendChild(kpi('生效中', (s.blockActive === undefined ? '—' : s.blockActive), '当前仍在拦的封禁'));
    host.appendChild(kpi('被护栏拦下', (s.blockedByGuard === undefined ? '—' : s.blockedByGuard), '白名单/护栏拒绝执行'));
    host.appendChild(kpi('已执行动作', (s.executedActions === undefined ? '—' : s.executedActions), '审计流水条数'));
    setText('wb-audit-note', note ? ('口径：' + note) : '');

    renderAuditBlocks(data.blocks);
    renderAuditActions(data.actions);
  }

  function renderAuditBlocks(blocks) {
    var host = document.getElementById('wb-audit-blocks');
    if (!host) { return; }
    clear(host);

    if (!blocks) {
      host.appendChild(el('div', 'wb-empty', '审计数据源不可达 —— 不显示示例记录。'));
      setText('wb-audit-blocks-note', '');
      return;
    }
    if (!blocks.length) {
      host.appendChild(el('div', 'wb-empty', '审计留痕里还没有封禁记录。'));
      setText('wb-audit-blocks-note', '');
      return;
    }

    // 出现最多的掩码来源（从真实数据里数出来，不在代码里写死任何 IP）：
    // 这样"能否查到那次真实封禁"是可核对的事实，而不是我在页面上贴出来的样例。
    var tally = {};
    blocks.forEach(function (b) { tally[b.ip] = (tally[b.ip] || 0) + 1; });
    var topIp = '', topN = 0;
    Object.keys(tally).forEach(function (ip) {
      if (tally[ip] > topN) { topN = tally[ip]; topIp = ip; }
    });
    setText('wb-audit-blocks-note',
      blocks.length + ' 条 · 出现最多的掩码来源 ' + topIp + '（' + topN + ' 条）');

    var head = el('div', 'wb-rec__row wb-rec__row--head');
    ['创建时间', '来源 IP（后端掩码）', '时长', '来源', '操作者', '状态', '审计号'].forEach(function (t) {
      head.appendChild(el('span', null, t));
    });
    host.appendChild(head);

    blocks.forEach(function (b) {
      var row = el('div', 'wb-rec__row' + (b.ip === topIp ? ' is-hot' : ''));
      row.appendChild(cell('创建时间', fmtTime(b.createdAt, true), 'wb-row__time'));
      row.appendChild(cell('来源 IP', b.ip || '—', 'wb-rec__ip'));
      row.appendChild(cell('时长', (b.durationMinutes === undefined ? '—' : b.durationMinutes + ' 分钟')));
      row.appendChild(cell('来源', b.source || '—'));
      row.appendChild(cell('操作者', b.actor || '—'));
      var st = el('span');
      st.setAttribute('data-label', '状态');
      if (b.unblocked) {
        st.appendChild(el('span', 'wb-badge wb-badge--info2', '已解封'));
        st.title = '解封于 ' + (b.unblockedAt || '—') + '（unblockMode=' + (b.unblockMode || '—') + '）';
      } else {
        st.appendChild(el('span', 'wb-badge wb-badge--warn', '封禁中'));
        st.title = '到期时间 ' + (b.expiresAt || '—');
      }
      row.appendChild(st);
      row.appendChild(cell('审计号', b.auditId || b.id || '—', 'wb-rec__id'));
      row.title = (b.id || '') + ' · 到期 ' + (b.expiresAt || '—');
      host.appendChild(row);
    });
  }

  function renderAuditActions(actions) {
    var host = document.getElementById('wb-audit-actions');
    if (!host) { return; }
    clear(host);

    if (!actions) {
      host.appendChild(el('div', 'wb-empty', '审计流水不可达 —— 不显示示例记录。'));
      setText('wb-audit-actions-note', '');
      return;
    }
    if (!actions.length) {
      host.appendChild(el('div', 'wb-empty', '没有审计流水。'));
      setText('wb-audit-actions-note', '');
      return;
    }

    var shown = actions.slice(0, ACTION_LIMIT);
    setText('wb-audit-actions-note', actions.length > shown.length
      ? ('共 ' + actions.length + ' 条 · 按时间倒序显示最近 ' + shown.length + ' 条')
      : ('共 ' + actions.length + ' 条'));

    var head = el('div', 'wb-rec__row wb-rec__row--head');
    ['时间', '操作者', '动作', '目标（掩码）', '模式', '结果', '原因'].forEach(function (t) {
      head.appendChild(el('span', null, t));
    });
    host.appendChild(head);

    shown.forEach(function (a) {
      var row = el('div', 'wb-rec__row');
      row.appendChild(cell('时间', fmtTime(a.time, true), 'wb-row__time'));
      row.appendChild(cell('操作者', a.actor || '—'));
      row.appendChild(cell('动作', a.action || '—', 'wb-rec__act'));
      row.appendChild(cell('目标', a.target || '—', 'wb-rec__ip'));
      var mode = el('span', 'wb-badge ' + (MODE_CLASS[a.mode] || 'wb-badge--muted'), a.mode || '—');
      mode.setAttribute('data-label', '模式');
      row.appendChild(mode);
      var res = el('span', 'wb-badge ' + (a.success ? 'wb-badge--info2' : 'wb-badge--danger'),
        a.success ? '已执行' : '未执行');
      res.setAttribute('data-label', '结果');
      row.appendChild(res);
      var reason = cell('原因', a.reason || '—', 'wb-rec__reason');
      reason.title = a.reason || '';
      row.appendChild(reason);
      row.title = (a.id || '') + ' · riskLevel=' + (a.riskLevel || '—') + ' · ' + (a.reason || '');
      host.appendChild(row);
    });
  }

  /* ==================== 蜜罐战报（/api/public/honeypot） ==================== */

  var KIND_CLASS = { '登录成功': 'wb-badge--info', '新连接': 'wb-badge--info2', '客户端指纹': 'wb-badge--muted' };

  function renderHoneypot(data, stale, snapAt) {
    var host = $('#wb-hp-kpis');
    if (!host) { return; }

    if (!stale) { clearNoticeIn('wb-hp-notice'); }

    var badge = document.getElementById('wb-hp-badge');
    if (badge) {
      setBadge(badge, !data ? '数据源不可达'
        : (data.available === false ? '数据源标记不可用' : (stale ? '快照数据' : '实时')),
        !data ? 'danger' : (data.available === false ? 'warn' : (stale ? 'warn' : 'ok')));
    }
    setText('wb-hp-synced', data ? fmtTime(data.generatedAt, true) : (snapAt ? minutesAgo(snapAt) : '—'));

    if (!data) {
      renderHoneypotBody(null);
      return;
    }
    if (data.available === false && !stale) {
      noticeIn('wb-hp-notice', 'warn', '后端把蜜罐数据源标成 available=false：' + (data.note || '原因未说明')
        + '。下面的数字不刷新，不做估算。');
    }
    renderHoneypotBody(data);
  }

  function renderHoneypotBody(data) {
    var host = document.getElementById('wb-hp-kpis');
    if (host) {
      clear(host);
      host.setAttribute('aria-busy', 'false');
      if (!data) {
        host.appendChild(el('div', 'wb-kpi', '数据源不可达'));
      } else {
        host.appendChild(kpi('事件总量', (data.total === undefined ? '—' : data.total),
          '窗口内事件数（后端截断到 10000）'));
        host.appendChild(kpi('新连接', (data.connections === undefined ? '—' : data.connections), 'Cowrie SSH 连接'));
        host.appendChild(kpi('登录成功', (data.logins === undefined ? '—' : data.logins), '"成功"只说明蜜罐让它进来了'));
        host.appendChild(kpi('登录失败', (data.loginFails === undefined ? '—' : data.loginFails), '口令不匹配的次数'));
        host.appendChild(kpi('抽取样本', (data.sampled === undefined ? '—' : data.sampled), '参与分析的样本数'));
      }
    }

    if (!data) {
      renderDist('#wb-hp-cred', null);
      renderDist('#wb-hp-src', null);
      renderDist('#wb-hp-client', null);
      renderTimeline(null);
      renderCommands(null);
      return;
    }

    renderDist('#wb-hp-cred', buckets(data.topCredentials), function () { return 'wb-dist__bar--host'; });
    renderDist('#wb-hp-src', buckets(data.topSources), function () { return 'wb-dist__bar--high'; });
    renderDist('#wb-hp-client', buckets(data.topClients), function () { return 'wb-dist__bar--low'; });
    renderTimeline(data);
    renderCommands(data);
  }

  function renderTimeline(data) {
    var host = document.getElementById('wb-hp-timeline');
    if (!host) { return; }
    clear(host);

    if (!data) {
      host.appendChild(el('div', 'wb-empty', '蜜罐数据源不可达 —— 不显示示例事件。'));
      setText('wb-hp-tl-note', '');
      return;
    }
    var list = data.timeline || [];
    if (!list.length) {
      host.appendChild(el('div', 'wb-empty', '窗口内没有事件。'));
      setText('wb-hp-tl-note', '');
      return;
    }

    var shown = list.slice(0, TIMELINE_LIMIT);
    setText('wb-hp-tl-note', list.length > shown.length
      ? ('接口返回 ' + list.length + ' 条 · 显示最近 ' + shown.length + ' 条')
      : ('接口返回 ' + list.length + ' 条'));

    shown.forEach(function (e) {
      var row = el('div', 'wb-tl__row');
      row.appendChild(el('span', 'wb-row__time', fmtTime(e.time, true)));
      var kind = e.kind || '事件';
      row.appendChild(el('span', 'wb-badge ' + (KIND_CLASS[kind] || 'wb-badge--info2'), kind));
      row.appendChild(el('span', 'wb-tl__detail', e.detail || '（接口未给 detail）'));
      row.appendChild(el('span', 'wb-tl__ip', e.srcIp || '—'));
      host.appendChild(row);
    });
  }

  /**
   * 命令时间线。
   * 现在后端是 commandsAvailable=false 且没有 commands 字段 ——
   * 所以这里【必须】显示"数据源未接入"，把后端 note 原文贴出来。
   * 哪天后端接上了（commandsAvailable=true + commands 数组），这个分支会自动开始渲染。
   */
  function renderCommands(data) {
    var host = document.getElementById('wb-hp-cmd');
    var note = document.getElementById('wb-hp-cmd-note');
    if (!host) { return; }

    var hasCmds = !!(data && data.commandsAvailable && data.commands && data.commands.length);
    if (hasCmds) {
      clear(host);
      var list = el('div', 'wb-tl');
      data.commands.slice(0, TIMELINE_LIMIT).forEach(function (c) {
        var row = el('div', 'wb-tl__row');
        row.appendChild(el('span', 'wb-row__time', fmtTime(c.time, true)));
        row.appendChild(el('span', 'wb-badge wb-badge--host', c.srcIp || '—'));
        row.appendChild(el('span', 'wb-tl__detail', c.command || c.detail || '—'));
        list.appendChild(row);
      });
      host.appendChild(list);
      return;
    }

    // 没有数据源：如实说明，且把后端的原话带出来
    if (!host.querySelector('.wb-na-block__text')) {
      clear(host);
      var box = el('div', 'wb-na-block');
      box.appendChild(el('span', 'wb-badge wb-badge--muted', '数据源未接入'));
      box.appendChild(el('span', 'wb-na-block__text', ''));
      host.appendChild(box);
      note = box.querySelector('.wb-na-block__text');
    }
    if (note) {
      note.textContent = (data && data.note)
        ? ('后端说明：' + data.note)
        : 'Wazuh 侧没有命令执行规则，公开端点不返回 commands / commandsAvailable=true —— '
          + '所以这里没有命令时间线，不编造、也不用其他数据顶替。';
    }
  }

  /* ============================================================================
     自适应轮询
     ----------------------------------------------------------------------------
     规则（已定设计决策）：
       · 页面可见：实时看板 2.5 秒一次；页面隐藏：20 秒一次
       · 只轮询【当前栏目】需要的接口 + 全局接口（系统状态）
       · 不用 SSE / WebSocket / 长连接，就是短连接 GET

     【为什么还要退避】实测（2026-10-12）：公开端点有很紧的独立限流 ——
     连续请求到第 3 次就开始返回 HTTP 429。所以这里额外做三件事：
       ① 每个数据源单独计时，并错开首次请求，避免 4 个接口同时打上去；
       ② 收到 429/5xx 就指数退避（15s → 30s → 60s → 120s → 最长 300s），
         成功一次立刻恢复正常节奏；
       ③ 退避期间在面板上如实说明"限流中，显示的是快照"，不假装是实时。
     这不是"新起一套轮询"：仍然是同一个 tick 调度器、同一个 load() 取数链路。
     ========================================================================== */
  var POLL_VISIBLE_MS = 2500;
  var POLL_HIDDEN_MS = 20000;
  var TICK_MS = 1000;
  var HEALTH_VISIBLE_MS = 60000;    // 三个指纹只在部署时变，没必要跟着 2.5 秒轮询
  var HEALTH_HIDDEN_MS = 300000;
  var BACKOFF_START_MS = 15000;
  var BACKOFF_MAX_MS = 300000;
  var loaders = [];
  var currentView = page || 'home';

  function isVisible() { return document.visibilityState !== 'hidden'; }

  /** 某个 loader 当前该用的间隔（可见 / 隐藏；loader 可自定义） */
  function pollInterval(l) {
    return isVisible() ? (l.visibleMs || POLL_VISIBLE_MS) : (l.hiddenMs || POLL_HIDDEN_MS);
  }

  /** 找到宿主元素所在的栏目（#view-xxx）；不在任何栏目里（右栏/独立页）就返回 null = 常驻轮询 */
  function viewOf(node) {
    var v = (node && node.closest) ? node.closest('.wb-view') : null;
    return (v && v.id) ? v.id.replace(/^view-/, '') : null;
  }

  function register(host, fn, opts) {
    if (!host) { return null; }
    opts = opts || {};
    var l = {
      host: host, fn: fn, view: viewOf(host), busy: false, last: 0,
      visibleMs: opts.visibleMs, hiddenMs: opts.hiddenMs,
      backoff: 0,            // 当前退避时长，0 = 正常
      nextAt: 0              // 下一次允许执行的时间戳
    };
    loaders.push(l);
    return l;
  }

  function runLoader(l) {
    if (l.busy) { return; }
    l.busy = true;
    l.last = Date.now();
    Promise.resolve().then(l.fn).then(function (status) {
      if (status === 429 || status >= 500) {
        // 限流 / 后端故障：指数退避，别把访问者的 IP 打进限流黑名单
        l.backoff = l.backoff ? Math.min(l.backoff * 2, BACKOFF_MAX_MS) : BACKOFF_START_MS;
        l.nextAt = Date.now() + l.backoff;
      } else if (status === 200) {
        l.backoff = 0;
        l.nextAt = 0;
      }
    }).catch(function (e) {
      console.warn('[workbench] 轮询失败：' + (e && e.message));
    }).then(function () {
      l.busy = false;
    });
  }

  function tick(force) {
    var now = Date.now();
    loaders.forEach(function (l) {
      if (l.view && l.view !== currentView) { return; }      // 不在当前栏目 → 不取数
      if (l.nextAt && now < l.nextAt) { return; }            // 退避中
      if (!force && l.last && (now - l.last) < pollInterval(l)) { return; }
      runLoader(l);
    });
  }

  /* ==================== 启动 ==================== */

  var hasStatus = !!$('#wb-status');        // 首页 hero 右栏那一行状态
  var hasBoard = !!$('#wb-kpis');           // 告警面板（首页内联面板 / /alerts/ 页共用同一份标记）
  var hasAudit = !!$('#wb-audit-kpis');     // 处置审计块
  var hasHoneypot = !!$('#wb-hp-kpis');     // 蜜罐战报
  var hasSys = !!(sysCard || sysStrip);     // 系统状态（右栏卡片 / 全局细条）

  function loadStatus() { return load('/api/public/overview', renderHome); }
  function loadBoard() { return load('/api/public/alerts', renderAlerts); }
  function loadAudit() { return load('/api/public/audit', renderAudit, { noticeId: 'wb-audit-notice' }); }
  function loadHoneypot() { return load('/api/public/honeypot', renderHoneypot, { noticeId: 'wb-hp-notice' }); }
  function loadHealth() { return load('/api/health', renderSystemStatus, { raw: true }); }

  if (sysStrip && !sysCard) { sysStrip.hidden = false; }

  register($('#wb-status'), loadStatus);
  register(sysCard || sysStrip, loadHealth, { visibleMs: HEALTH_VISIBLE_MS, hiddenMs: HEALTH_HIDDEN_MS });
  register($('#wb-kpis'), loadBoard);
  register($('#wb-audit-kpis'), loadAudit);
  register($('#wb-hp-kpis'), loadHoneypot);

  var refresh = $('#wb-refresh');
  if (refresh) {
    refresh.addEventListener('click', function () {
      var l = loaders.filter(function (x) { return x.host && x.host.id === 'wb-kpis'; })[0];
      if (l) { l.nextAt = 0; l.backoff = 0; }   // 手动刷新：清掉退避，立刻取一次
      loadBoard();
    });
  }

  /* ---------- 栏目切换：顶栏每一项对应下面一块内容，只显示当前栏目 ----------
     六栏目口径：主页 / 笔记 / 态势感知 / AI 安全 / 攻防靶场（关于是独立页） */
  var VIEWS = {
    home: { id: 'view-home' },
    notes: { id: 'view-notes' },
    situ: { id: 'view-situ' },      // 态势感知 = 实时告警 + 处置审计
    ai: { id: 'view-ai' },          // AI 安全 = state 口径映射
    range: { id: 'view-range' }     // 攻防靶场 = 靶场三层 + 蜜罐战报
  };

  var layout = document.querySelector('.wb-layout');

  function showView(name, scroll) {
    if (!VIEWS[name]) { name = 'home'; }
    Object.keys(VIEWS).forEach(function (k) {
      var box = document.getElementById(VIEWS[k].id);
      if (box) { box.hidden = (k !== name); }
    });
    // 当前栏目写在容器上：CSS 据此决定"全幅 banner"还是"极淡页面底纹"
    if (root) { root.setAttribute('data-wb-view', name); }
    // tab 条高亮同步（顶栏与 tab 条是两个入口，状态必须一致）
    document.querySelectorAll('[data-wb-tab]').forEach(function (t) {
      t.classList.toggle('is-active', t.getAttribute('data-wb-tab') === name);
    });
    // 切栏目时立刻拉一次该栏目的数据（不必等下一个轮询周期）
    if (currentView !== name) {
      currentView = name;
      tick(true);
    }
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

  /* 首屏取数：错开启动（一个接口一个接口地发），别在同一个瞬间打 4 个请求 —— 
     公开端点限流很紧，同时发容易直接被 429。之后交给 1 秒粒度的调度器。 */
  loaders.forEach(function (l, i) {
    setTimeout(function () { if (!l.last) { runLoader(l); } }, i * 700);
  });
  setInterval(function () { tick(false); }, TICK_MS);

  /* 页面回到前台时立刻刷新一次（隐藏期间是 20 秒一次，回到前台马上补一次） */
  document.addEventListener('visibilitychange', function () {
    tick(true);
  });
})();
