/* ============================================================================
   xiaokeqing 博客 · SPA 外壳 + 数据层（原生 JS，零依赖）
   ----------------------------------------------------------------------------
   对应《前端改版规格-xiaokeqing.md》：
     §2  hash 路由：点导航只替换 #content，背景层与胶囊导航始终不动；数据 fetch 异步加载。
     §4  三种版式：门户（主页）/ 笔记三栏阅读 / 监测中心四子 tab；AI 安全与未上线项标灰不可点。
     §5  数据纪律：
          · 只走 /api/public/*（只读、IP 掩码）与 /api/health（扁平对象，无信封）；
          · 轮询 10–15s 自适应，仅前台轮询，标签隐藏即暂停，失败指数退避；
          · 配合 ETag / If-None-Match（有则用）与服务端 15s 缓存（cacheSeconds）；
          · 服务端 20 次/分钟的限流保持不变 —— 前端不靠加频率换实时性，
            所以只轮询"当前视图"需要的端点（见 pollOnce 的 scope 说明）。
          · 取不到数据：显示"上次同步于 X 分钟前"的本地快照，或明确写"未接入"，绝不编造。
     §5  不做匿名常驻 SSE / WebSocket。
   ============================================================================ */
(function () {
  'use strict';

  /* ==========================================================================
     0. 启动参数与常量
     ========================================================================== */
  var boot = {};
  try { boot = JSON.parse(document.getElementById('xk-boot').textContent); } catch (e) { boot = {}; }
  var API = (boot.apiBase || document.querySelector('meta[name="wb-api"]').content || '').replace(/\/+$/, '');

  var POLL_MIN = 10000, POLL_MAX = 15000;   // §5：10–15 秒自适应
  var BACKOFF_MAX = 120000;                 // 连续失败最长退避 2 分钟
  var DEFAULT_CACHE_SECONDS = 15;           // 服务端 Cache-Control: max-age=15
  var SNAP_KEY = 'xk-snap-v1';
  var FEED_MAX = 8;                         // §4①：最近 5–8 条真实事件

  var SEV_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4 };
  var SEV_CLASS = { CRITICAL: 'critical', HIGH: 'high', MEDIUM: 'medium', LOW: 'low', INFO: 'info' };

  /* 长列表纪律（规格 §3：长列表分页或虚拟滚动）：
     告警流 / 蜜罐事件时间线先只渲染前 N 条，点"显示全部"再展开 —— 一次塞几百行
     既拖慢首屏，也让页面难以阅读。 */
  var STREAM_LIMIT = 30, HP_TL_LIMIT = 40;

  /* ==========================================================================
     1. 小工具
     ========================================================================== */
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /** 数字：null/NaN/undefined 一律显示「—」，不伪装成 0（0 本身是有效数据） */
  function num(n) {
    if (n === null || n === undefined || n === '' || isNaN(Number(n))) return '—';
    return Number(n).toLocaleString('zh-CN');
  }

  function pct(a, b) { return b > 0 ? Math.round(a / b * 100) : 0; }

  /** "2026-10-12 17:29:50" → Date（接口给的是无时区的本地时间串，按本地解析） */
  function parseTs(s) {
    if (!s) return null;
    var m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/);
    if (!m) return null;
    return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0));
  }

  function relTime(date) {
    if (!date) return '—';
    var diff = Math.max(0, Date.now() - date.getTime());
    var min = Math.floor(diff / 60000);
    if (min < 1) return '刚刚';
    if (min < 60) return min + ' 分钟前';
    var hr = Math.floor(min / 60);
    if (hr < 24) return hr + ' 小时前';
    return Math.floor(hr / 24) + ' 天前';
  }

  function clockOf(ts) {
    var d = new Date(ts);
    function p(n) { return (n < 10 ? '0' : '') + n; }
    return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
  }

  function durationText(ms) {
    if (ms === null || ms === undefined || isNaN(ms)) return '—';
    var s = Math.floor(ms / 1000), d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    if (d > 0) return d + ' 天 ' + h + ' 小时';
    if (h > 0) return h + ' 小时 ' + m + ' 分';
    return m + ' 分 ' + (s % 60) + ' 秒';
  }

  function sevLabel(s) {
    return { CRITICAL: '严重', HIGH: '高危', MEDIUM: '中危', LOW: '低危', INFO: '提示' }[s] || (s || '未知');
  }

  /** 尊重 prefers-reduced-motion：用户关掉动效时不做平滑滚动（规格 §3） */
  function prefersReducedMotion() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }
  function scrollToEl(el) {
    if (el) el.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
  }

  /* ==========================================================================
     2. 数据层：条件请求 + 15s 新鲜度 + 本地快照
     --------------------------------------------------------------------------
     · 有 ETag / Last-Modified 就带 If-None-Match / If-Modified-Since，命中 304 就不重新渲染；
     · 服务端给了 Cache-Control: max-age=15（接口体里也有 cacheSeconds=15），
       因此在 15s 内的重复读直接用本地副本，不发请求 —— 这是"配合服务端缓存"，
       也是把 20 次/分钟限流留给真正需要的时刻；
     · 成功后把载荷写进 localStorage：接口挂了还能显示"上次同步于 X 分钟前"的快照。
     ========================================================================== */
  var CACHE = {};       // path → { data, etag, lastModified, syncedAt, cacheSeconds, rtt }
  var LAST_RTT = 300;   // 最近一次请求耗时（用于 10–15s 自适应）

  try {
    var saved = JSON.parse(localStorage.getItem(SNAP_KEY) || '{}');
    Object.keys(saved).forEach(function (k) {
      if (saved[k] && saved[k].data !== undefined) CACHE[k] = saved[k];
    });
  } catch (e) { /* 快照坏了就当没有，不影响功能 */ }

  function persistSnapshots() {
    try {
      var out = {};
      Object.keys(CACHE).forEach(function (k) {
        if (CACHE[k].ok) out[k] = { data: CACHE[k].data, syncedAt: CACHE[k].syncedAt, cacheSeconds: CACHE[k].cacheSeconds };
      });
      localStorage.setItem(SNAP_KEY, JSON.stringify(out));
    } catch (e) { /* 配额满/隐私模式：忽略，内存里仍有数据 */ }
  }

  /**
   * 读取一个公开端点。
   * @param path 形如 /api/public/alerts
   * @param opts.force 忽略新鲜度，强制发请求
   * @returns { data, syncedAt, notModified, fromCache }
   * 抛出的错误带 .status（HTTP 状态码）或 .offline
   */
  function readApi(path, opts) {
    opts = opts || {};
    var hit = CACHE[path];
    var cacheSeconds = (hit && hit.cacheSeconds) || DEFAULT_CACHE_SECONDS;

    if (hit && hit.ok && !opts.force && (Date.now() - hit.syncedAt) < cacheSeconds * 1000) {
      return Promise.resolve({ data: hit.data, syncedAt: hit.syncedAt, fromCache: true, notModified: false });
    }

    var headers = {};
    if (hit && hit.etag) headers['If-None-Match'] = hit.etag;
    else if (hit && hit.lastModified) headers['If-Modified-Since'] = hit.lastModified;

    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();

    return fetch(API + path, {
      method: 'GET',
      headers: headers,
      mode: 'cors',
      credentials: 'omit',
      cache: 'no-store'      // 条件请求由我们自己发，避免浏览器缓存把 304 变成"看不见的 200"
    }).then(function (res) {
      var rtt = ((window.performance && performance.now) ? performance.now() : Date.now()) - t0;
      LAST_RTT = rtt;

      if (res.status === 304) {
        var h = CACHE[path] || {};
        h.syncedAt = Date.now(); h.ok = true; h.rtt = rtt;
        CACHE[path] = h;
        return { data: h.data, syncedAt: h.syncedAt, notModified: true, fromCache: true };
      }
      if (!res.ok) {
        var err = new Error('HTTP ' + res.status);
        err.status = res.status;
        throw err;
      }
      var etag = res.headers.get('ETag');
      var lastMod = res.headers.get('Last-Modified');

      return res.json().then(function (body) {
        var rec = {
          data: body, ok: true, syncedAt: Date.now(), rtt: rtt,
          etag: etag || null, lastModified: lastMod || null, cacheSeconds: null
        };
        // 服务端在信封里自述缓存秒数（15）；/api/health 没有信封，用默认值
        var cs = body && body.data && body.data.cacheSeconds;
        rec.cacheSeconds = cs || DEFAULT_CACHE_SECONDS;
        CACHE[path] = rec;
        persistSnapshots();
        return { data: body, syncedAt: rec.syncedAt, notModified: false, fromCache: false };
      });
    }).catch(function (e) {
      e.snapshot = CACHE[path] && CACHE[path].ok ? CACHE[path] : null;
      throw e;
    });
  }

  /** POST /api/playground/check（靶场唯一允许的互动端点） */
  function postPlayground(input) {
    return fetch(API + '/api/playground/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      mode: 'cors',
      credentials: 'omit',
      body: JSON.stringify({ input: String(input) })
    }).then(function (res) {
      if (!res.ok) { var e = new Error('HTTP ' + res.status); e.status = res.status; throw e; }
      return res.json();
    });
  }

  /* ==========================================================================
     3. 同步状态文案（"上次同步于 X 分钟前"，不白屏、不造假）
     ========================================================================== */
  function setSync(key, text, cls) {
    $$('[data-xk-sync="' + key + '"]').forEach(function (n) {
      n.textContent = text;
      n.className = 'xk-sync' + (cls ? ' ' + cls : '');
    });
  }

  function syncTextOf(parts) {
    // parts: [{name, res|null, err}] → 汇总成一句人话
    var okList = [], badList = [];
    parts.forEach(function (p) {
      if (p.err) badList.push(p.name + ' ' + (p.err.status ? 'HTTP ' + p.err.status : '不可达'));
      else okList.push(p.name);
    });
    var newest = 0;
    parts.forEach(function (p) { if (p.res && p.res.syncedAt > newest) newest = p.res.syncedAt; });
    var stamp = newest ? '刚刚同步 ' + clockOf(newest) : '尚无成功同步';
    if (badList.length === 0) return stamp + ' · ' + okList.join(' + ');
    return '上次同步于 ' + (newest ? relTime(new Date(newest)) + '（' + clockOf(newest) + '）' : '未知') +
           ' · 失败：' + badList.join('、');
  }

  /* ==========================================================================
     4. 轮询器：仅前台 / 只轮询当前视图 / 失败指数退避 / 10–15s 自适应
     ========================================================================== */
  var activePoller = null;

  function stopPolling() {
    if (activePoller) { activePoller.stop(); activePoller = null; }
  }

  function startPolling(loadFn) {
    stopPolling();
    var stopped = false, fails = 0, timer = null;

    function interval() {
      // 自适应：请求越慢，间隔越靠近上限；快请求落到下限 10s。
      // 上限 15s 是规格硬约束 —— 服务端限流 20 次/分钟不放宽。
      return Math.min(POLL_MAX, Math.max(POLL_MIN, Math.round(LAST_RTT * 6)));
    }

    function tick() {
      if (stopped) return;
      if (document.hidden) { timer = setTimeout(tick, POLL_MIN); return; }
      loadFn().then(function () {
        fails = 0;
      }).catch(function () {
        fails += 1;   // 失败次数由各视图自己写进同步文案
      }).then(function () {
        if (stopped) return;
        var delay = fails ? Math.min(interval() * Math.pow(2, fails), BACKOFF_MAX) : interval();
        timer = setTimeout(tick, delay);
      });
    }

    activePoller = {
      stop: function () { stopped = true; if (timer) clearTimeout(timer); },
      kick: function () { if (timer) clearTimeout(timer); fails = 0; tick(); }
    };
    tick();
  }

  // 切到后台/标签隐藏即暂停；回到前台立刻补一次（规格 §5）
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) return;
    if (activePoller) activePoller.kick();
  });

  /* ==========================================================================
     5. 路由（hash 路由 + 深链兼容）
     ========================================================================== */
  var VIEW_TPL = {
    home: 'tpl-home', notes: 'tpl-notes', note: 'tpl-note',
    monitor: 'tpl-monitor', ai: 'tpl-ai', range: 'tpl-range',
    about: 'tpl-about', notfound: 'tpl-notfound'
  };
  var NAV_OF_ROUTE = { home: 'home', notes: 'notes', note: 'notes', monitor: 'monitor', ai: 'ai', range: 'range', about: 'about' };

  function parseHash(hash) {
    var m = String(hash || '').replace(/^#/, '').match(/^\/?([a-z-]+)(?:\/([^/?#]+))?/i);
    if (!m) return null;
    var name = m[1].toLowerCase(), arg = m[2] ? decodeURIComponent(m[2]) : null;
    if (!VIEW_TPL[name]) return null;
    if (name === 'note' && arg) return { name: 'note', slug: arg };
    if (name === 'monitor') return { name: 'monitor', tab: arg || 'alerts' };
    if (name === 'notes' && arg) return { name: 'note', slug: arg };
    return { name: name };
  }

  function routeFromPath(path) {
    var p = path.replace(/index\.html$/, '');
    if (p === '/' || p === '') return { name: 'home' };
    var m = p.match(/^\/posts\/([^/]+)\/?$/);
    if (m) return { name: 'note', slug: m[1] };
    if (/^\/posts\/?$/.test(p) || /^\/categories/.test(p) || /^\/tags/.test(p)) return { name: 'notes' };
    if (/^\/alerts/.test(p)) return { name: 'monitor', tab: 'alerts' };
    if (/^\/labs/.test(p)) return { name: 'range' };
    if (/^\/(about|projects|demo)/.test(p)) return { name: 'about' };
    if (/^\/(404\.html)?$/.test(p)) return { name: 'notfound' };
    return { name: 'notfound' };
  }

  function currentRoute() {
    return parseHash(location.hash) || routeFromPath(location.pathname);
  }

  function isInternalRoute(href) {
    if (!href) return false;
    if (/^(https?:)?\/\//i.test(href) || /^(mailto|tel):/i.test(href)) return false;
    if (href.charAt(0) === '#') return href.indexOf('#/') === 0;
    return /^\/(posts|about|projects|demo|alerts|labs|categories|tags)/.test(href) || href === '/';
  }

  /** 站内跳转：URL 统一收敛成 /#/<route>，只替换 #content，绝不整页刷新 */
  function navigate(path) {
    var hash = path.charAt(0) === '#' ? path : '#' + path;
    history.pushState({ xk: 1 }, '', '/' + hash);
    render(parseHash(hash) || { name: 'notfound' });
  }

  /* ==========================================================================
     6. 视图渲染
     ========================================================================== */
  var contentEl = document.getElementById('content');
  var INDEX = null;          // 笔记索引（/index.json）

  function render(route) {
    stopPolling();
    var tpl = document.getElementById(VIEW_TPL[route.name] || 'tpl-notfound');
    contentEl.replaceChildren(tpl.content.cloneNode(true));
    window.scrollTo(0, 0);

    // 左侧栏导航高亮（导航本身不动，只换 class）
    var active = NAV_OF_ROUTE[route.name];
    $$('.xk-side__link').forEach(function (a) {
      a.classList.toggle('is-on', a.getAttribute('data-xk-nav') === active);
    });

    var host = contentEl.firstElementChild;
    if (route.name === 'home') initHome();
    else if (route.name === 'notes') initNotes();
    else if (route.name === 'note') initNote(route.slug);
    else if (route.name === 'monitor') initMonitor(route.tab);
    else if (route.name === 'range') initRange();
    else if (route.name === 'ai') initAi();
    else if (route.name === 'about') initAbout();
    else if (route.name === 'notfound') { /* 静态内容 */ }
    if (host) host.focus && host.setAttribute('tabindex', '-1');

    updateSearchButtonState();
  }

  /* ==========================================================================
     6.5 左侧栏左下角统计（站主第四轮 ④）
     --------------------------------------------------------------------------
     · 笔记篇数：/index.json 的 count（Hugo 渲染出来的真实索引）
     · 封禁留痕 / 处置动作：/api/public/audit 的 data.summary.blockTotal / executedActions
       —— 走和监测中心同一条 readApi（带 ETag/15s 缓存），不额外放大请求频率
     · 任一来源取不到：那一行写「未接入」，绝不填 0 或假数
     ========================================================================== */
  function setSideStat(key, text) {
    $$('[data-xk-stat="' + key + '"]').forEach(function (n) { n.textContent = text; });
  }

  function initSideStats() {
    if (!$('#xk-side-stats')) return;

    // 笔记篇数
    loadIndex().then(function (idx) {
      var n = idx && typeof idx.count === 'number' ? idx.count : (idx && idx.notes ? idx.notes.length : null);
      setSideStat('notes', n === null || n === undefined ? '未接入' : n + ' 篇');
    }).catch(function () {
      setSideStat('notes', '未接入');
    });

    // 处置审计（blockTotal = 封禁留痕条数；executedActions = 已执行处置动作数）
    readApi('/api/public/audit').then(function (r) {
      var s = (r && r.data && r.data.data && r.data.data.summary) || null;
      if (!s) { setSideStat('blocks', '未接入'); setSideStat('actions', '未接入'); return; }
      setSideStat('blocks', num(s.blockTotal) === '—' ? '未接入' : num(s.blockTotal) + ' 次');
      setSideStat('actions', num(s.executedActions) === '—' ? '未接入' : num(s.executedActions) + ' 次');
    }).catch(function (err) {
      var snap = err && err.snapshot && err.snapshot.data && err.snapshot.data.data;
      var s = snap && snap.summary;
      if (s) {
        // 接口挂了但有本地快照：照实标"上次同步"，不假装是刚拿到的
        setSideStat('blocks', num(s.blockTotal) + ' 次（上次同步）');
        setSideStat('actions', num(s.executedActions) + ' 次（上次同步）');
      } else {
        setSideStat('blocks', '未接入');
        setSideStat('actions', '未接入');
      }
    });
  }

  initSideStats();
  /* ==========================================================================
     7. 主页：实时拦截动态 + 数据来源
     ========================================================================== */
  /* /api/public/latest 规格里就写着"可能不存在"：实测 HTTP 500。
     它属于可选端点，失败后 10 分钟内不再重试 —— 不能因为一个不存在的端点
     把每个轮询周期都变成一次失败请求（那是在白白消耗 20 次/分钟的限流）。 */
  var OPTIONAL_RETRY_MS = 600000;
  var optionalDeadUntil = {};

  function initHome() {
    $$('[data-xk-api-base]').forEach(function (n) { n.textContent = API.replace(/^https?:\/\//, ''); });

    var load = function () {
      // 只读两个端点：audit（真实封禁/处置留痕）与 latest（规格说"可能不存在"）
      var jobs = [{ name: 'audit', path: '/api/public/audit', optional: false }];
      if (Date.now() > (optionalDeadUntil['/api/public/latest'] || 0)) {
        jobs.push({ name: 'latest', path: '/api/public/latest', optional: true });
      } else {
        jobs.push({ name: 'latest', path: '/api/public/latest', optional: true, dead: true });
      }

      return Promise.all(jobs.map(function (j) {
        if (j.dead) {
          return Promise.resolve({
            name: j.name, res: null, optional: true,
            err: { status: 500, cached: true }
          });
        }
        return readApi(j.path).then(function (res) {
          return { name: j.name, res: res, err: null, optional: !!j.optional };
        }).catch(function (err) {
          if (j.optional) optionalDeadUntil[j.path] = Date.now() + OPTIONAL_RETRY_MS;
          return {
            name: j.name, optional: !!j.optional, err: err,
            res: err.snapshot ? { data: err.snapshot.data, syncedAt: err.snapshot.syncedAt } : null
          };
        });
      })).then(function (parts) {
        var audit = (parts.filter(function (p) { return p.name === 'audit' && p.res; })[0] || {}).res;
        var latest = (parts.filter(function (p) { return p.name === 'latest' && p.res; })[0] || {}).res;
        renderFeed(audit, latest, parts);
      });
    };

    startPolling(load);
  }

  /** 实时动态：优先 /api/public/latest（未就绪就退回 audit，并如实写明） */
  function renderFeed(audit, latest, parts) {
    var rows = [], sourceNote = '';
    var latestPart = parts.filter(function (p) { return p.name === 'latest'; })[0];

    var latestItems = latest && latest.data ? pickArray(latest.data.data || latest.data) : null;
    if (latestItems && latestItems.length) {
      latestItems.slice(0, FEED_MAX).forEach(function (it) {
        rows.push({
          level: it.severity || it.level || 'INFO',
          text: it.title || it.message || it.ruleName || JSON.stringify(it).slice(0, 120),
          time: parseTs(it.occurredAt || it.time || it.createdAt),
          goto: '#/monitor/alerts'
        });
      });
      sourceNote = '数据来自 /api/public/latest（真实接口）。';
    } else if (audit && audit.data) {
      var d = (audit.data && audit.data.data) || {};   // {code,message,data} 信封
      (d.blocks || []).forEach(function (b) {
        rows.push({
          level: b.unblocked ? 'LOW' : 'HIGH',
          text: '封禁 ' + (b.ip || '—') + ' · ' + (b.durationMinutes != null ? b.durationMinutes + ' 分钟' : '时长未给') +
                '（来源：' + (b.source || '未标注') + '）' + (b.unblocked ? ' · 已解封' : ' · 生效中'),
          time: parseTs(b.createdAt),
          goto: '#/monitor/audit'
        });
      });
      (d.actions || []).forEach(function (a) {
        rows.push({
          level: a.success ? (a.riskLevel || 'LOW') : 'MEDIUM',
          text: '处置动作 ' + (a.action || '—') + ' → ' + (a.target || '—') +
                '（' + (a.mode || '—') + '）' + (a.reason ? ' · ' + a.reason : '') + (a.success ? '' : ' · 未执行'),
          time: parseTs(a.time),
          goto: '#/monitor/audit'
        });
      });
      sourceNote = '数据来自 /api/public/audit（真实封禁与处置留痕）。';
      if (latestPart && latestPart.err) {
        sourceNote += ' /api/public/latest 尚未就绪（' +
          (latestPart.err.status ? 'HTTP ' + latestPart.err.status : '不可达') + '），因此本卡用 audit 替代 —— 不编造 live 数据。';
      }
    }

    rows = rows.filter(function (r) { return r.time; })
               .sort(function (a, b) { return b.time - a.time; })
               .slice(0, FEED_MAX);

    var host = $('[data-xk-feed]');
    if (!host) return;

    if (!rows.length) {
      var reason = parts.filter(function (p) { return p.err && !p.optional; })[0];
      host.innerHTML = '<li class="xk-feed__row"><span class="xk-dot xk-dot--off"></span>' +
        '<span class="xk-feed__text">' + (reason
          ? '取不到数据（' + esc(reason.err.status ? 'HTTP ' + reason.err.status : '网络不可达') + '）——不显示占位假事件。'
          : '接口没有返回可展示的事件。') +
        '</span><span class="xk-feed__time">—</span></li>';
    } else {
      host.innerHTML = rows.map(function (r) {
        return '<li class="xk-feed__row" data-xk-goto="' + esc(r.goto) + '" role="link" tabindex="0">' +
          '<span class="xk-dot ' + (SEV_CLASS[r.level] ? 'xk-dot--' + SEV_CLASS[r.level] : '') + '"></span>' +
          '<span class="xk-feed__text" title="' + esc(r.text) + '">' + esc(r.text) + '</span>' +
          '<span class="xk-feed__time">' + esc(relTime(r.time)) + '</span></li>';
      }).join('');
    }

    var note = $('[data-xk-feed-note]');
    if (note) {
      note.textContent = sourceNote + ' IP 已由服务端掩码；这里是只读展示，不含任何处置入口。';
    }
    setSync('feed', syncTextOf(parts.filter(function (p) { return !p.optional || p.res; })));
  }

  /** 结果可能是数组，也可能包在 data/list/items 里 —— 不猜字段名，只在常见的三种里找 */
  function pickArray(body) {
    if (Array.isArray(body)) return body;
    if (!body) return null;
    ['data', 'list', 'items', 'events'].forEach(function (k) {
      if (Array.isArray(body[k])) body = body[k];
    });
    return Array.isArray(body) ? body : null;
  }

  /* ==========================================================================
     8. 笔记列表 + 阅读
     ========================================================================== */
  function loadIndex() {
    if (INDEX) return Promise.resolve(INDEX);
    return fetch('/index.json', { cache: 'no-cache' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (j) { INDEX = j; return INDEX; });
  }

  function initNotes() {
    var chips = $$('[data-xk-cats] .xk-chip', contentEl);
    var rows = $$('[data-xk-notes] .xk-notes__row', contentEl);
    var empty = $('[data-xk-notes-empty]', contentEl);

    function apply(cat) {
      var shown = 0;
      rows.forEach(function (r) {
        var cats = (r.getAttribute('data-note-cat') || '').split('|');
        var ok = cat === '__all' || cats.indexOf(cat) >= 0;
        r.hidden = !ok;
        if (ok) shown += 1;
      });
      if (empty) empty.hidden = shown > 0;
    }

    chips.forEach(function (c) {
      c.addEventListener('click', function () {
        chips.forEach(function (o) { o.classList.toggle('is-on', o === c); });
        apply(c.getAttribute('data-xk-cat'));
      });
    });
    apply('__all');
  }

  function initNote(slug) {
    var wrap = contentEl;
    loadIndex().then(function (idx) {
      var list = (idx && idx.notes) || [];
      var i = -1;
      list.forEach(function (n, k) { if (n.slug === slug) i = k; });
      if (i < 0) { render({ name: 'notfound' }); return; }
      var note = list[i];

      $('[data-xk-note-title]', wrap).textContent = note.title;
      $('[data-xk-note-crumb]', wrap).textContent = note.title;

      var meta = $('[data-xk-note-meta]', wrap);
      meta.innerHTML = [
        note.date ? esc(note.date) : '',
        note.categories && note.categories.length ? esc(note.categories.join(' / ')) : '',
        esc(note.readingTime + ' 分钟阅读'),
        esc(num(note.wordCount) + ' 字')
      ].filter(Boolean).map(function (s) { return '<span>' + s + '</span>'; }).join('<span aria-hidden="true">·</span>');

      var body = $('[data-xk-note-body]', wrap);
      body.innerHTML = note.content || '<p class="xk-hint">这篇没有正文。</p>';
      decorateCode(body);

      var stats = $('[data-xk-note-stats]', wrap);
      stats.innerHTML =
        '<li><span>字数</span><b>' + esc(num(note.wordCount)) + ' 字</b></li>' +
        '<li><span>阅读</span><b>' + esc(note.readingTime) + ' 分钟</b></li>' +
        '<li><span>发布</span><b>' + esc(note.date || '—') + '</b></li>' +
        '<li><span>小标题</span><b>' + esc($$('h2, h3', body).length) + ' 个</b></li>';

      var tags = $('[data-xk-note-tags]', wrap);
      var chips = [];
      (note.categories || []).forEach(function (c) { chips.push('<span class="xk-tag">' + esc(c) + '</span>'); });
      (note.tags || []).forEach(function (t) { chips.push('<span class="xk-tag xk-tag--ghost">' + esc(t) + '</span>'); });
      tags.innerHTML = chips.length ? chips.join('') : '<span class="xk-hint">未标注分类与标签。</span>';

      buildToc(body, $('[data-xk-toc]', wrap));

      var prev = list[i - 1], next = list[i + 1];
      $('[data-xk-note-nav]', wrap).innerHTML =
        (prev ? '<a class="xk-link" href="/#/notes/' + esc(prev.slug) + '" data-xk-note="' + esc(prev.slug) + '">← ' + esc(prev.title) + '</a>' : '<span class="xk-hint">已经是第一篇</span>') +
        (next ? '<a class="xk-link" href="/#/notes/' + esc(next.slug) + '" data-xk-note="' + esc(next.slug) + '">' + esc(next.title) + ' →</a>' : '<span class="xk-hint">已经是最后一篇</span>');
    }).catch(function () {
      $('[data-xk-note-body]', contentEl).innerHTML =
        '<p class="xk-notice xk-notice--bad">笔记索引 /index.json 读取失败。刷新页面重试；这不是"文章不存在"。</p>';
    });
  }

  /** 目录：从正文里真实存在的 h2/h3 生成（不写死 TOC） */
  function buildToc(body, host) {
    if (!host) return;
    var heads = $$('h2, h3', body).filter(function (h) { return h.id; });
    if (!heads.length) {
      host.innerHTML = '<li class="xk-hint">这篇没有小标题。</li>';
      return;
    }
    host.innerHTML = heads.map(function (h) {
      return '<li><a href="#' + esc(h.id) + '" data-xk-toc="' + esc(h.id) + '" class="' + (h.tagName === 'H3' ? 'is-l3' : '') + '">' + esc(h.textContent) + '</a></li>';
    }).join('');

    if (!('IntersectionObserver' in window)) return;
    var links = $$('a[data-xk-toc]', host);
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        links.forEach(function (a) { a.classList.toggle('is-on', a.getAttribute('data-xk-toc') === en.target.id); });
      });
    }, { rootMargin: '-88px 0px -70% 0px', threshold: 0 });
    heads.forEach(function (h) { obs.observe(h); });
  }

  /** 代码块：加一个复制按钮（只在正文里做，不引第三方高亮/复制库） */
  function decorateCode(scope) {
    $$('pre', scope).forEach(function (pre) {
      if (pre.parentElement && pre.parentElement.classList.contains('xk-code')) return;
      var holder = document.createElement('div');
      holder.className = 'xk-code';
      pre.parentNode.insertBefore(holder, pre);
      holder.appendChild(pre);
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'xk-copy';
      btn.textContent = '复制';
      btn.addEventListener('click', function () {
        var text = pre.innerText;
        var done = function () { btn.textContent = '已复制'; setTimeout(function () { btn.textContent = '复制'; }, 1600); };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () { btn.textContent = '复制失败'; });
        } else {
          var ta = document.createElement('textarea');
          ta.value = text; document.body.appendChild(ta); ta.select();
          try { document.execCommand('copy'); done(); } catch (e) { btn.textContent = '复制失败'; }
          document.body.removeChild(ta);
        }
      });
      holder.appendChild(btn);
    });
  }

  /* ==========================================================================
     9. 监测中心：四个子 tab
     ========================================================================== */
  function initMonitor(tab) {
    var tabs = $$('[data-xk-tab]', contentEl);
    var panes = $$('[data-xk-pane]', contentEl);
    var current = null;

    function activate(name, silent) {
      if (['alerts', 'honeypot', 'audit', 'system'].indexOf(name) < 0) name = 'alerts';
      current = name;
      tabs.forEach(function (t) {
        var on = t.getAttribute('data-xk-tab') === name;
        t.classList.toggle('is-on', on);
        t.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      panes.forEach(function (p) {
        var on = p.getAttribute('data-xk-pane') === name;
        p.classList.toggle('is-on', on);
        p.hidden = !on;
      });
      if (!silent) {
        // tab 也做成可深链的：#/monitor/honeypot
        history.replaceState({ xk: 1 }, '', '/#/monitor/' + name);
      }
      startPolling(loaders[name]);
    }

    var loaders = {
      alerts: loadAlerts,
      honeypot: loadHoneypot,
      audit: loadAudit,
      system: loadSystem
    };

    tabs.forEach(function (t) {
      t.addEventListener('click', function () { activate(t.getAttribute('data-xk-tab')); });
    });
    activate(tab || 'alerts', true);
  }

  /* ---------- 9.1 实时告警 ---------- */
  function loadAlerts() {
    var jobs = [
      { name: 'overview', path: '/api/public/overview' },
      { name: 'alerts', path: '/api/public/alerts' }
    ];
    return Promise.all(jobs.map(function (j) {
      return readApi(j.path).then(function (res) { return { name: j.name, res: res, err: null }; })
        .catch(function (err) {
          return { name: j.name, err: err, res: err.snapshot ? { data: err.snapshot.data, syncedAt: err.snapshot.syncedAt } : null };
        });
    })).then(function (parts) {
      var ov = (parts.filter(function (p) { return p.name === 'overview' && p.res; })[0] || {}).res;
      var al = (parts.filter(function (p) { return p.name === 'alerts' && p.res; })[0] || {}).res;
      renderAlerts(ov && ov.data && ov.data.data, al && al.data && al.data.data, parts);
    });
  }

  function renderAlerts(ov, al, parts) {
    function host(name) { return $('[data-xk-' + name + ']', contentEl); }

    /* --- KPI：一律用去重/聚合口径（规格 §4③ 明确要求，避免几万条"高危"） --- */
    var list = (al && al.list) || [];
    var bySev = {}, bySrc = {}, ips = {}, rules = {};
    list.forEach(function (a) {
      bySev[a.severity] = (bySev[a.severity] || 0) + 1;
      var src = a.sourceLabel || a.source || '未知';
      bySrc[src] = (bySrc[src] || 0) + 1;
      if (a.srcIp) ips[a.srcIp] = 1;
      if (a.ruleName) rules[a.ruleName] = 1;
    });
    var highDedup = (bySev.HIGH || 0) + (bySev.CRITICAL || 0);
    var aggTotal = al ? al.total : null;
    var kpiHtml = [
      kpi(num(aggTotal), '窗口内聚合告警（去重后条数）', ''),
      kpi(num(highDedup), '其中高危及以上（去重）', highDedup > 0 ? 'is-red' : ''),
      kpi(String(Object.keys(ips).length), '去重来源 IP', ''),
      kpi(String(Object.keys(rules).length), '去重规则', '')
    ].join('');
    host('alert-kpis').innerHTML = kpiHtml;

    var caliber = host('alert-caliber');
    if (caliber) {
      caliber.innerHTML = al
        ? '口径：观察窗口 <b>' + esc(al.windowMinutes != null ? al.windowMinutes + ' 分钟' : '未给') + '</b>、原始事件 <b>' + esc(num(al.rawTotal)) +
          '</b> 条，按规则/IP 去重聚合为 <b>' + esc(num(al.total)) + '</b> 条告警（<code>aggregated=' + esc(al.aggregated) + '</code>）。' +
          '响应体自述：窗口上限 ' + esc(num(al.windowSize)) + ' 条。'
        : '告警接口没有返回数据。';
    }

    var sevHost = host('alert-sev');
    var sevMax = Math.max(1, Math.max.apply(null, Object.keys(bySev).map(function (k) { return bySev[k]; }).concat([1])));
    var sevKeys = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
    sevHost.innerHTML = sevKeys.map(function (k) {
      var c = bySev[k] || 0;
      return distRow(sevLabel(k), c, sevMax, k);
    }).join('');

    var srcHost = host('alert-src');
    var srcMax = Math.max(1, Math.max.apply(null, Object.keys(bySrc).map(function (k) { return bySrc[k]; }).concat([1])));
    srcHost.innerHTML = Object.keys(bySrc).length
      ? Object.keys(bySrc).sort(function (a, b) { return bySrc[b] - bySrc[a]; }).map(function (k) { return distRow(k, bySrc[k], srcMax, ''); }).join('')
      : '<p class="xk-hint">无来源数据。</p>';

    /* --- 24h 趋势：原始计数（未去重）单独标注，并在下面写清为什么不用它做 KPI --- */
    var trend = (al && al.stats24h && al.stats24h.trend) || (al && al.stats && al.stats.trend) || [];
    var trendHost = host('alert-trend');
    if (trend.length) {
      var max = Math.max.apply(null, trend.map(function (t) { return t.count; }).concat([1]));
      trendHost.innerHTML =
        '<div class="xk-chart">' + trend.map(function (t) {
          var h = Math.max(2, Math.round(t.count / max * 118));
          return '<div class="xk-chart__col" title="' + esc(t.time + ' · ' + num(t.count) + ' 条原始事件') + '">' +
                 '<div class="xk-chart__bar' + (t.count ? '' : ' is-zero') + '" style="height:' + h + 'px"></div></div>';
        }).join('') + '</div>' +
        '<div class="xk-chart__x">' + trend.map(function (t, i) {
          return '<span class="xk-chart__xl">' + esc(i % 3 === 0 ? t.time : '') + '</span>';
        }).join('') + '</div>';
    } else {
      trendHost.innerHTML = '<p class="xk-hint">接口没有返回趋势数据。</p>';
    }
    var tnote = host('trend-note');
    if (tnote) {
      if (al && al.stats24h && al.stats24h.available) {
        tnote.innerHTML = '24 小时原始事件合计 <b>' + esc(num(al.stats24h.total)) + '</b> 条（<code>windowHours=' +
          esc(al.stats24h.windowHours) + '</code>）。这是<b>未去重</b>的上报量：单条高频规则一小时就能刷上万次，' +
          '直接当成"高危事件数"会严重误导，所以上方 KPI 用的是去重聚合口径，这张图只用来观察上报量的形状。';
      } else {
        tnote.textContent = '接口未提供 24 小时趋势（available=false）。';
      }
    }

    /* --- 告警流：高危置顶 + 级别过滤 + 点开下钻 --- */
    renderStream(al);

    /* --- 右栏：节点 / 数据源 --- */
    var nodesHost = host('nodes');
    var nodes = (ov && ov.nodes) || [];
    nodesHost.innerHTML = nodes.length ? nodes.map(function (n) {
      return '<li><span>' + esc(n.label || n.id) + '</span><b>' +
        '<span class="xk-dot ' + (n.online ? 'xk-dot--ok' : 'xk-dot--off') + '" style="display:inline-block;margin-right:6px"></span>' +
        esc(n.online ? '在线' : '离线') + '</b></li>' +
        '<li><span></span><b class="xk-meta__v" style="font-weight:400;color:var(--xk-muted);font-size:11.5px">' + esc(n.probe || '') + '</b></li>';
    }).join('') : '<li class="xk-hint">节点数据未返回。</li>';

    var srcPanel = host('source');
    var ds = ov && ov.dataSource;
    srcPanel.innerHTML = ds
      ? '<li><span>Wazuh</span><b>' + esc(ds.wazuhMode || '—') + '</b></li>' +
        '<li><span>降级</span><b>' + esc(ds.degraded ? '是' : '否') + '</b></li>'
      : '<li class="xk-hint">数据源信息未返回。</li>';
    var srcNote = host('source-note');
    if (srcNote && ds && ds.note) srcNote.textContent = ds.note;

    var drill = host('drill-note');
    if (drill) {
      drill.innerHTML = '展开用的是聚合记录自带的字段（无需额外请求）。' +
        '注意：明细下钻端点 <code>/api/public/alerts/{aggId}</code> 当前<b>尚未上线</b>（实测 HTTP 404），' +
        '所以这里不提供"原始事件列表"，也不会用别的接口拼一份出来。';
    }

    setSync('monitor', syncTextOf(parts));
  }

  function kpi(value, label, cls, sub) {
    return '<div class="xk-kpi"><span class="xk-kpi__num ' + (cls || '') + '">' + value + '</span>' +
      '<span class="xk-kpi__label">' + esc(label) + '</span>' +
      (sub ? '<span class="xk-kpi__sub">' + esc(sub) + '</span>' : '') + '</div>';
  }

  function distRow(label, count, max, sevKey) {
    // 计数为 0 就不画条：留 2% 的"零宽余量"会让 0 看起来像"有一点点"，那是误导
    var w = (max > 0 && count > 0) ? Math.max(3, Math.round(count / max * 100)) : 0;
    return '<div class="xk-dist__row"><span class="xk-dist__label" title="' + esc(label) + '">' + esc(label) + '</span>' +
      '<span class="xk-dist__track"><span class="xk-dist__fill' + (sevKey ? ' is-' + SEV_CLASS[sevKey] : '') + '" style="width:' + w + '%"></span></span>' +
      '<span class="xk-dist__count">' + esc(num(count)) + '</span></div>';
  }

  function renderStream(al) {
    var streamHost = $('[data-xk-alert-stream]', contentEl);
    var noteHost = $('[data-xk-stream-note]', contentEl);
    if (!streamHost) return;

    var list = ((al && al.list) || []).slice();
    var filter = streamHost.getAttribute('data-filter') || '__all';

    // 高危置顶：先按级别，再按时间倒序（规格 §4③）
    list.sort(function (a, b) {
      var sa = SEV_ORDER[a.severity] == null ? 9 : SEV_ORDER[a.severity];
      var sb = SEV_ORDER[b.severity] == null ? 9 : SEV_ORDER[b.severity];
      if (sa !== sb) return sa - sb;
      return String(b.occurredAt || '').localeCompare(String(a.occurredAt || ''));
    });
    if (filter !== '__all') list = list.filter(function (a) { return a.severity === filter; });

    if (!list.length) {
      streamHost.innerHTML = '<li class="xk-hint" style="padding:10px 0">该过滤条件下没有告警。</li>';
    } else {
      var shown = list.slice(0, STREAM_LIMIT);
      streamHost.innerHTML = shown.map(function (a) {
        var sev = SEV_CLASS[a.severity] || 'info';
        var t = parseTs(a.occurredAt);
        return '<li class="xk-stream__row" data-xk-agg="' + esc(a.aggId) + '">' +
          '<div class="xk-stream__hd" role="button" tabindex="0">' +
            '<span class="xk-sev is-' + sev + '">' + esc(a.severityLabel || sevLabel(a.severity)) + '</span>' +
            '<span class="xk-stream__title" title="' + esc(a.title) + '">' + esc(a.title) + '</span>' +
            '<span class="xk-stream__meta"><span>' + esc(a.srcIp || '—') + '</span>' +
            '<span>' + esc(a.sourceLabel || a.source || '—') + '</span>' +
            '<span>聚合 ' + esc(num(a.count)) + ' 次</span>' +
            '<span>' + esc(t ? relTime(t) : '—') + '</span></span>' +
          '</div>' +
          '<div class="xk-stream__detail" hidden>' + detailTable(a) + '</div>' +
        '</li>';
      }).join('') + (list.length > shown.length
        ? '<li class="xk-hint" style="padding:10px 0">只渲染了前 ' + shown.length + ' 条（共 ' + list.length +
          ' 条）<button class="xk-chip" type="button" data-xk-more="stream" style="margin-left:8px">显示全部</button></li>'
        : '');
    }

    if (noteHost) {
      noteHost.innerHTML = al
        ? '数据源口径：窗口 ' + esc(num(al.windowSize)) + ' 条原始事件 / ' + esc(num(al.rawTotal)) +
          ' 条已读取；接口返回 <code>aggregated=' + esc(al.aggregated) + '</code>，因此每一行是"同一规则 + 同一来源 IP"聚合后的一条记录，行内数字是它的出现次数。'
        : '';
    }
  }

  /** 下钻：展开聚合记录自带的全部字段（明文列出字段名，方便对照接口） */
  function detailTable(a) {
    var rows = [
      ['aggId', a.aggId], ['severity', a.severity + '（' + (a.severityLabel || '') + '）'],
      ['source', a.source + '（' + (a.sourceLabel || '') + '）'],
      ['type', a.type + '（' + (a.typeLabel || '') + '）'],
      ['srcIp（已掩码）', a.srcIp], ['count', a.count], ['status', a.status],
      ['occurredAt', a.occurredAt], ['startTime', a.startTime], ['endTime', a.endTime],
      ['ruleName', a.ruleName], ['srcGeo', a.srcGeo == null ? 'null（接口未提供）' : JSON.stringify(a.srcGeo)]
    ];
    return '<ul class="xk-meta xk-meta--kv">' + rows.map(function (r) {
      return '<li><span>' + esc(r[0]) + '</span><b>' + esc(r[1] === undefined ? '—' : r[1]) + '</b></li>';
    }).join('') + '</ul>';
  }

  /* ---------- 9.2 蜜罐战报 ---------- */
  function loadHoneypot() {
    return Promise.all([readApi('/api/public/honeypot').then(function (res) { return { res: res, err: null }; })
      .catch(function (err) { return { err: err, res: err.snapshot ? { data: err.snapshot.data, syncedAt: err.snapshot.syncedAt } : null }; })])
      .then(function (parts) {
        renderHoneypot(parts[0].res && parts[0].res.data && parts[0].res.data.data, parts);
      });
  }

  function renderHoneypot(d, parts) {
    function host(n) { return $('[data-xk-' + n + ']', contentEl); }
    if (!d) {
      host('hp-kpis').innerHTML = '<p class="xk-hint">蜜罐接口没有返回数据。</p>';
      setSync('monitor', syncTextOf(parts));
      return;
    }
    host('hp-kpis').innerHTML = [
      kpi(num(d.total), '事件总量（服务端字段 total）', ''),
      kpi(num(d.connections), 'SSH 连接数', ''),
      kpi(num(d.logins), '登录成功次数（攻击者拿到了"成功"）', d.logins > 0 ? 'is-orange' : ''),
      kpi(num(d.loginFails), '登录失败次数', '')
    ].join('');

    host('hp-note').innerHTML = (d.note ? esc(d.note) + ' ' : '') +
      '接口自述：<code>available=' + esc(d.available) + '</code>、<code>commandsAvailable=' + esc(d.commandsAvailable) + '</code>、' +
      '<code>total=' + esc(num(d.total)) + '</code>、<code>sampled=' + esc(num(d.sampled)) + '</code>。' +
      'total 与 sampled 的口径由服务端定义，这里按原字段展示，不做换算。';

    host('hp-creds').innerHTML = distList(d.topCredentials, true);
    host('hp-sources').innerHTML = distList(d.topSources, true);
    host('hp-clients').innerHTML = distList(d.topClients, true);

    var tl = host('hp-timeline');
    var rows = d.timeline || [];
    var tlShown = rows.slice(0, HP_TL_LIMIT);
    tl.innerHTML = rows.length ? tlShown.map(function (e) {
      return '<li class="xk-tl__row"><span class="xk-tl__time">' + esc(e.time) + '</span>' +
        '<span class="xk-tl__kind">' + esc(e.kind) + '</span>' +
        '<span class="xk-tl__detail" title="' + esc(e.detail) + '">' + esc(e.detail) + '</span></li>';
    }).join('') + (rows.length > tlShown.length
      ? '<li class="xk-hint" style="padding:10px 0">只渲染了最近 ' + tlShown.length + ' 条（接口共返回 ' + rows.length +
        ' 条）<button class="xk-chip" type="button" data-xk-more="hp" style="margin-left:8px">显示全部</button></li>'
      : '') : '<li class="xk-hint">接口没有返回事件时间线。</li>';

    var cmdNote = host('hp-cmd-note');
    if (cmdNote) {
      cmdNote.innerHTML = d.commandsAvailable === false
        ? '接口返回 <code>commandsAvailable=false</code>：蜜罐里敲过的命令暂时拿不到（Wazuh 侧没有命令执行规则）。' +
          '这一格保持「数据源未接入」，不编造命令内容。' + (d.note ? ' 接口原话：' + esc(d.note) : '')
        : '接口声称命令数据可用（<code>commandsAvailable=' + esc(d.commandsAvailable) + '</code>），但本次响应里没有 commands 字段，因此仍无可展示内容。';
    }
    host('hp-sampled').textContent = num(d.sampled);
    host('hp-total').textContent = num(d.total);
    setSync('monitor', syncTextOf(parts));
  }

  function distList(arr, wide) {
    if (!arr || !arr.length) return '<p class="xk-hint">无数据。</p>';
    var max = Math.max.apply(null, arr.map(function (x) { return x.count; }).concat([1]));
    return arr.slice(0, 10).map(function (x) { return distRow(x.key, x.count, max, ''); }).join('');
  }

  /* ---------- 9.3 处置审计 ---------- */
  function loadAudit() {
    return readApi('/api/public/audit').then(function (res) { return { res: res, err: null }; })
      .catch(function (err) { return { err: err, res: err.snapshot ? { data: err.snapshot.data, syncedAt: err.snapshot.syncedAt } : null }; })
      .then(function (part) { renderAudit(part.res && part.res.data && part.res.data.data, [part]); });
  }

  function renderAudit(d, parts) {
    function host(n) { return $('[data-xk-' + n + ']', contentEl); }
    if (!d) {
      host('audit-kpis').innerHTML = '<p class="xk-hint">审计接口没有返回数据。</p>';
      setSync('monitor', syncTextOf(parts));
      return;
    }
    var s = d.summary || {};
    host('audit-kpis').innerHTML = [
      kpi(num(s.blockTotal), '封禁留痕条数'),
      kpi(num(s.blockActive), '当前生效中的封禁', s.blockActive > 0 ? 'is-orange' : ''),
      kpi(num(s.blockedByGuard), '被护栏拦下的动作', s.blockedByGuard > 0 ? 'is-orange' : ''),
      kpi(num(s.executedActions), '已执行动作')
    ].join('');
    host('audit-note').innerHTML = (s.note ? esc(s.note) + ' ' : '') +
      '接口自述 <code>readOnly=' + esc(d.readOnly) + '</code>：这一栏没有任何写操作入口。';

    var blocks = d.blocks || [];
    host('audit-blocks').innerHTML =
      '<div class="xk-rec__row xk-rec__row--head"><span>审计号</span><span>IP（掩码）</span><span>时长</span><span>来源</span><span>创建 / 过期</span><span>解封</span><span>执行者与模式</span></div>' +
      (blocks.length ? blocks.map(function (b) {
        return '<div class="xk-rec__row">' +
          '<span class="xk-rec__id">' + esc(b.id) + '</span>' +
          '<span class="xk-rec__ip">' + esc(b.ip) + '</span>' +
          '<span>' + esc(b.durationMinutes != null ? b.durationMinutes + ' 分' : '—') + '</span>' +
          '<span>' + esc(b.source || '—') + '</span>' +
          '<span class="xk-hint">' + esc(b.createdAt) + '<br>' + esc(b.expiresAt) + '</span>' +
          '<span>' + (b.unblocked
            ? '<span class="xk-tag ' + (b.unblockMode === 'MOCK' ? 'xk-tag--warn' : 'xk-tag--on') + '">已解封 ' + esc(b.unblockMode || '') + '</span>'
            : '<span class="xk-tag xk-tag--bad">生效中</span>') + '</span>' +
          '<span>' + esc(b.actor || '—') + ' · <code>' + esc(b.auditId || '') + '</code></span>' +
        '</div>';
      }).join('') : '<p class="xk-hint">没有封禁留痕。</p>');

    var actions = d.actions || [];
    host('audit-actions').innerHTML =
      '<div class="xk-rec__row xk-rec__row--head"><span>审计号</span><span>时间</span><span>执行者</span><span>动作 → 目标</span><span>风险</span><span>模式</span><span>原因 / 结果</span></div>' +
      (actions.length ? actions.map(function (a) {
        var modeTag = a.mode === 'BLOCKED' ? 'xk-tag--bad' : (a.mode === 'MOCK' ? 'xk-tag--warn' : 'xk-tag--on');
        return '<div class="xk-rec__row">' +
          '<span class="xk-rec__id">' + esc(a.id) + '</span>' +
          '<span class="xk-hint">' + esc(a.time) + '</span>' +
          '<span>' + esc(a.actor) + '</span>' +
          '<span>' + esc(a.action) + ' → ' + esc(a.target) + '</span>' +
          '<span>' + esc(a.riskLevel) + '</span>' +
          '<span><span class="xk-tag ' + modeTag + '">' + esc(a.mode) + '</span></span>' +
          '<span class="xk-rec__reason">' + esc(a.reason || '') + (a.success ? '' : ' · <b>未执行</b>') + '</span>' +
        '</div>';
      }).join('') : '<p class="xk-hint">没有审计流水。</p>');

    setSync('monitor', syncTextOf(parts));
  }

  /* ---------- 9.4 系统状态 ---------- */
  function loadSystem() {
    // /api/health 是扁平对象，没有 {code,message,data} 信封
    return readApi('/api/health').then(function (res) { return { res: res, err: null }; })
      .catch(function (err) { return { err: err, res: err.snapshot ? { data: err.snapshot.data, syncedAt: err.snapshot.syncedAt } : null }; })
      .then(function (part) { renderSystem(part.res && part.res.data, [part]); });
  }

  function renderSystem(h, parts) {
    function host(n) { return $('[data-xk-' + n + ']', contentEl); }
    if (!h) {
      host('sys-fp').innerHTML = '<li class="xk-hint">/api/health 没有返回数据。</li>';
      host('sys-info').innerHTML = '<li class="xk-hint">—</li>';
      setSync('monitor', syncTextOf(parts));
      return;
    }

    var fp = [
      ['镜像指纹 artifactMd5', h.artifactMd5, '镜像内 jar 的 MD5（硬证据）'],
      ['源码指纹 embeddedGitCommit', h.embeddedGitCommit, (h.embeddedGitBranch || '—') + ' @ ' + (h.embeddedGitCommitTime || '—') + ' · ' + (h.embeddedGitCommitMessage || '')],
      ['服务器源码树 sourceSha', h.sourceSha, '服务器上的源码树 SHA'],
      ['环境变量自述 buildSha', h.buildSha, 'BUILD_SHA 自述，仅对照用，非证据'],
      ['期望发布 expectedReleaseCommit', h.expectedReleaseCommit, '发布流水线期望的 commit']
    ];
    host('sys-fp').innerHTML = fp.map(function (r) {
      var v = r[1] === undefined || r[1] === null || r[1] === '' ? '未接入' : r[1];
      return '<li class="xk-fp__row"><span class="xk-fp__k">' + esc(r[0]) + '</span>' +
        '<span class="xk-fp__v">' + esc(v) + (r[2] ? '<small>' + esc(r[2]) + '</small>' : '') + '</span></li>';
    }).join('');

    var statusTag = h.status === 'ok'
      ? '<span class="xk-tag xk-tag--on">ok</span>'
      : '<span class="xk-tag xk-tag--bad">' + esc(h.status || '未知') + '</span>';

    var kv = [
      ['应用 application', h.application],
      ['状态 status', null, statusTag],
      ['镜像包含 Git 属性 embeddedGitPropertiesPresent', h.embeddedGitPropertiesPresent === undefined ? '未接入' : String(h.embeddedGitPropertiesPresent)],
      ['工作区干净 embeddedGitDirty', h.embeddedGitDirty === undefined ? '未接入' : String(h.embeddedGitDirty)],
      ['指纹不一致 fingerprintMismatch', h.fingerprintMismatch === undefined ? '未接入' : String(h.fingerprintMismatch)],
      ['指纹问题 fingerprintIssues', Array.isArray(h.fingerprintIssues) && h.fingerprintIssues.length ? h.fingerprintIssues.join(' / ') : '无'],
      ['文档向量数 documentVectors', h.documentVectors],
      ['向量库 vectorStore', h.vectorStore],
      ['运行时长 uptimeMs', h.uptimeMs === undefined ? '未接入' : h.uptimeMs + ' ms（' + durationText(h.uptimeMs) + '）'],
      ['构建时间 buildTime', h.buildTime],
      ['jar 构建时间 embeddedGitBuildTime', h.embeddedGitBuildTime],
      ['构建说明 buildShaNote', h.buildShaNote]
    ];

    var html = kv.map(function (r) {
      var val = r[2] !== undefined && r[2] !== null ? r[2] : esc(r[1] === undefined || r[1] === null || r[1] === '' ? '未接入' : r[1]);
      return '<li><span>' + esc(r[0]) + '</span><b>' + val + '</b></li>';
    }).join('');

    // 样本开关：接口自己声明还开着 mock 数据源 —— 必须显示，不能藏起来
    var mocks = [];
    if (h.alertsMockEnabled) mocks.push('告警样本 alertsMockEnabled=true');
    if (h.logsMockEnabled) mocks.push('日志样本 logsMockEnabled=true');
    if (mocks.length) {
      html += '<li><span>样本开关</span><b><span class="xk-tag xk-tag--warn">' + esc(mocks.join(' / ')) + '</span></b></li>';
    } else {
      html += '<li><span>样本开关</span><b><span class="xk-tag xk-tag--on">均为 false</span></b></li>';
    }

    host('sys-info').innerHTML = html;

    var detail = kv.filter(function (r) { return r[1] !== undefined; });
    setSync('monitor', syncTextOf(parts));
    var sysSync = host('sys-sync');
    if (sysSync) sysSync.textContent = '字段名逐条对过 /api/health 的返回体';
    void detail;
  }

  /* ==========================================================================
     10. 攻防靶场：两张卡都真的打到 /api/playground/check
     ========================================================================== */
  function initRange() {
    var available = null;
    var statusEls = $$('[data-xk-pg-status], [data-xk-pi-status]', contentEl);

    function setStatus(text, cls) {
      statusEls.forEach(function (n) { n.textContent = text; n.className = 'xk-tag ' + (cls || ''); });
    }

    function availabilityProbe() {
      setStatus('正在探测检测链路…', '');
      postPlayground('xiaokeqing-frontend-probe').then(function () {
        available = true;
        setStatus('检测链路可用（真实后端）', 'xk-tag--on');
      }).catch(function (err) {
        available = false;
        setStatus('未上线・规划中', 'xk-tag--off');
        var msg = '<p class="xk-notice xk-notice--bad">检测端点 <code>POST /api/playground/check</code> 当前不可用（' +
          esc(err.status ? 'HTTP ' + err.status : '网络不可达') + '）。按纪律这里不放任何模拟结论 —— 按钮已停用。</p>';
        $$('[data-xk-pg-result], [data-xk-pi-result]', contentEl).forEach(function (r) { r.hidden = false; r.innerHTML = msg; });
        $$('[data-xk-pg-run], [data-xk-pg-preset], [data-xk-pi-preset]', contentEl).forEach(function (b) { b.disabled = true; });
      });
    }

    function run(input, resultEl, onlyPI) {
      if (available === false) return;
      resultEl.hidden = false;
      resultEl.innerHTML = '<p class="xk-hint">正在请求后端检测链路…</p>';
      postPlayground(input).then(function (body) {
        renderCheckResult(resultEl, body, onlyPI);
      }).catch(function (err) {
        resultEl.innerHTML = '<p class="xk-notice xk-notice--bad">检测失败（' +
          esc(err.status ? 'HTTP ' + err.status : '网络不可达') + '）。这不代表输入安全，只代表这次没测成。</p>';
      });
    }

    var input = $('#xk-pg-input', contentEl);
    var pgResult = $('[data-xk-pg-result]', contentEl);
    var piResult = $('[data-xk-pi-result]', contentEl);

    $$('[data-xk-pg-run]', contentEl).forEach(function (b) {
      b.addEventListener('click', function () { run(input.value, pgResult, false); });
    });
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') run(input.value, pgResult, false); });
    $$('[data-xk-pg-preset]', contentEl).forEach(function (b) {
      b.addEventListener('click', function () {
        input.value = b.getAttribute('data-xk-pg-preset');
        run(input.value, pgResult, false);
      });
    });
    $$('[data-xk-pi-preset]', contentEl).forEach(function (b) {
      b.addEventListener('click', function () { run(b.getAttribute('data-xk-pi-preset'), piResult, true); });
    });

    availabilityProbe();
  }

  function renderCheckResult(host, body, onlyPI) {
    var d = (body && body.data) || {};
    var checks = (d.checks || []).filter(function (c) { return !onlyPI || c.id === 'prompt-injection'; });
    var verdict = d.verdict || '—';
    var cls = verdict === 'CLEAN' ? 'xk-tag--on' : (verdict === 'BLOCKED' || verdict === 'HIT' ? 'xk-tag--bad' : 'xk-tag--warn');

    var html = '<div class="xk-result__verdict"><span class="xk-tag ' + cls + '">' + esc(verdict) + '</span>' +
      '<b>' + esc(d.verdictLabel || '') + '</b>' +
      '<span class="xk-hint">' + esc(d.summary || '') + ' · ' + esc(d.elapsedMs != null ? d.elapsedMs + ' ms' : '') +
      ' · ' + esc(d.treatedAsLabel || ('按「' + (d.treatedAs || '—') + '」检测')) + '</span></div>';

    html += checks.map(function (c) {
      var sevCls = c.hit ? (c.severity === 'HIGH' || c.severity === 'CRITICAL' ? 'is-high' : 'is-medium') : 'is-low';
      var stateTag = c.applicable === false
        ? '<span class="xk-sev is-info">不适用</span>'
        : (c.hit ? '<span class="xk-sev ' + sevCls + '">命中 ' + esc(c.severity || '') + '</span>' : '<span class="xk-sev is-low">未命中</span>');
      return '<div class="xk-check' + (c.applicable === false ? ' is-na' : '') + '">' +
        '<div class="xk-check__hd">' + stateTag +
          '<span class="xk-check__name">' + esc(c.name) + '</span>' +
          '<span class="xk-check__where">' + esc(c.where || '') + ' · <code>' + esc(c.component || '') + '</code></span>' +
        '</div>' +
        '<div class="xk-check__body">' +
          '<p>' + esc(c.detail || '') + '</p>' +
          (c.evidence && c.evidence.length ? '<p>证据：<code>' + esc(c.evidence.join(' / ')) + '</code></p>' : '') +
          (c.rules && c.rules.length ? '<p>命中规则：<code>' + esc(rulesText(c.rules)) + '</code></p>' : '') +
          '<p>动作：' + esc(c.action || '—') + '</p>' +
          '<p class="xk-note">边界：' + esc(c.limit || '—') + '</p>' +
        '</div></div>';
    }).join('');

    if (d.coverageWarning) {
      html += '<p class="xk-notice xk-notice--warn" style="margin-top:12px">' + esc(d.coverageWarning) + '</p>';
    }
    if (d.uncovered) {
      html += '<div class="xk-check"><div class="xk-check__hd"><span class="xk-check__name">' + esc(d.uncoveredTitle || '关于「未命中」的说明') + '</span></div>' +
        '<div class="xk-check__body"><p>' + esc(d.uncovered) + '</p></div></div>';
    }
    if (d.note) {
      html += '<p class="xk-note">' + esc(d.note) + '</p>';
    }
    host.innerHTML = html;
  }

  function rulesText(rules) {
    // 接口给的是对象数组（rule / severity / description），只展示规则名与说明，不整段 JSON 糊上去
    return rules.map(function (r) {
      if (typeof r === 'string') return r;
      var name = r.rule || r.name || r.id;
      return name ? (r.description ? name + '（' + r.description + '）' : name) : JSON.stringify(r);
    }).join(' / ');
  }

  /* ==========================================================================
     10.5 AI 安全：POST /api/public/ask + GET /api/public/kb（P4 后端已上线）
     --------------------------------------------------------------------------
     纪律：
       · 只调匿名公开端点，前端不加 Authorization；
       · answer 是 markdown —— 先整段转义再套极简 markdown（mdLite），不 innerHTML 直插后端原串；
       · state / stateLabel / failureReason / citations / quota / clientIpMasked 原样展示，
         generated=false 时明确写出服务端给的原因，不补一段"像答案"的文字；
       · 429 两种（每分钟 6 次的频率限制 / 同一来源 1 个在飞）按后端 body.message + Retry-After 显示，
         前端只做倒计时，不自己编话术；
       · 一次请求最多等 20 秒（服务端预算 20s），超时如实报超时。
     ========================================================================== */
  var ASK_TIMEOUT_MS = 20000;
  var ASK_MAX_CHARS = 600;

  /** 极简 markdown（先 esc 再套标签，因此后端正文里就算带 <script> 也只是文本） */
  function mdLite(src) {
    var text = esc(String(src === null || src === undefined ? '' : src));
    function inline(s) {
      return s
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
          '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    }
    var lines = text.split(/\r?\n/);
    var out = [], para = [], items = [], listType = '', bq = [];
    function closePara() { if (para.length) { out.push('<p>' + para.join('<br>') + '</p>'); para = []; } }
    function closeBq() { if (bq.length) { out.push('<blockquote><p>' + bq.join('<br>') + '</p></blockquote>'); bq = []; } }
    function closeList() {
      if (items.length) {
        out.push('<' + listType + '>' + items.map(function (i) { return '<li>' + i + '</li>'; }).join('') + '</' + listType + '>');
      }
      items = []; listType = '';
    }
    lines.forEach(function (raw) {
      var line = raw.replace(/\s+$/, '').trim();
      if (!line) { closePara(); closeList(); closeBq(); return; }
      /* 注意：整段已经过 esc()，所以引用块的 ">" 已经变成 "&gt;"，这里必须按转义后的写法匹配 */
      var q = line.match(/^&gt;\s?(.*)$/);
      if (q) { closePara(); closeList(); bq.push(inline(q[1])); return; }
      var h = line.match(/^(#{1,4})\s+(.*)$/);
      if (h) {
        closePara(); closeList(); closeBq();
        var lvl = Math.min(4, h[1].length + 1);   // # → h2，避免正文里再出现 h1
        out.push('<h' + lvl + '>' + inline(h[2]) + '</h' + lvl + '>');
        return;
      }
      var ul = line.match(/^[-*+]\s+(.*)$/);
      var ol = line.match(/^\d+[.)]\s+(.*)$/);
      if (ul || ol) {
        closePara(); closeBq();
        var t = ul ? 'ul' : 'ol';
        if (listType && listType !== t) closeList();
        listType = t;
        items.push(inline((ul || ol)[1]));
        return;
      }
      closeList(); closeBq();
      para.push(inline(line));
    });
    closePara(); closeList(); closeBq();
    return out.join('');
  }

  /** POST /api/public/ask —— 返回 {status, ok, body, retryAfter, rlRemaining, rlLimit}，超时抛 .timeout */
  function askApi(question) {
    var ctrl = (typeof AbortController === 'function') ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, ASK_TIMEOUT_MS);
    return fetch(API + '/api/public/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      mode: 'cors',
      credentials: 'omit',
      cache: 'no-store',
      signal: ctrl ? ctrl.signal : undefined,
      body: JSON.stringify({ question: String(question).slice(0, ASK_MAX_CHARS) })
    }).then(function (res) {
      clearTimeout(timer);
      return res.json().catch(function () { return null; }).then(function (body) {
        return {
          status: res.status, ok: res.ok, body: body,
          retryAfter: res.headers.get('Retry-After'),
          rlRemaining: res.headers.get('X-RateLimit-Remaining'),
          rlLimit: res.headers.get('X-RateLimit-Limit')
        };
      });
    }).catch(function (err) {
      clearTimeout(timer);
      if (err && err.name === 'AbortError') { var e = new Error('timeout'); e.timeout = true; throw e; }
      throw err;
    });
  }

  function initAi() {
    var askInput = $('#xk-ask-input', contentEl);
    var askBtn = $('[data-xk-ask-run]', contentEl);
    var askResult = $('[data-xk-ask-result]', contentEl);
    var askState = $('[data-xk-ask-state]', contentEl);
    var askQuota = $('[data-xk-ask-quota]', contentEl);
    var kbInput = $('#xk-kb-input', contentEl);
    var kbResult = $('[data-xk-kb-result]', contentEl);
    var kbStatus = $('[data-xk-kb-status]', contentEl);
    var kbNote = $('[data-xk-kb-note]', contentEl);
    var asking = false;

    if (!askInput || !kbInput) return;
    /* 顶栏副标题只放一句极简事实（端点与限额的完整清单在下面的卡片里，不再往页头堆字） */
    setSync('ai', '只读公开端点 · 无 SSE');

    function setAskState(text) { if (askState) askState.textContent = text; }

    /** 429 倒计时：话术用后端给的 message，只把剩余秒数显示出来 */
    function countdown429(host, msg, seconds) {
      if (host.__xkCd) clearInterval(host.__xkCd);
      var left = Math.max(1, Number(seconds) || 0);
      function paint() {
        if (!document.body.contains(host)) { clearInterval(host.__xkCd); host.__xkCd = null; return; }
        if (left <= 0) {
          host.innerHTML = '<p class="xk-notice xk-notice--warn">' + esc(msg) + '<br>等待结束，可以重新提交了。</p>';
          clearInterval(host.__xkCd); host.__xkCd = null; return;
        }
        host.innerHTML = '<p class="xk-notice xk-notice--warn">' + esc(msg) + '<br>请稍后再试 <b>' + left + '</b> 秒。</p>';
        left -= 1;
      }
      paint();
      host.__xkCd = setInterval(paint, 1000);
    }

    function citeItem(c) {
      var meta = [c.sourceTypeLabel, c.trustLevelLabel,
        (c.score === undefined || c.score === null || isNaN(Number(c.score)) ? '' : 'score ' + (Math.round(Number(c.score) * 100) / 100))]
        .filter(Boolean).map(esc).join(' · ');
      return '<li class="xk-cite">' +
        '<b class="xk-cite__title">' + esc(c.title || '（无标题）') + '</b>' +
        (meta ? '<span class="xk-hint">' + meta + '</span>' : '') +
        (c.snippet ? '<p class="xk-cite__snip">' + esc(c.snippet) + '</p>' : '') +
        '</li>';
    }

    function renderAsk(host, r, elapsedMs) {
      if (r.status === 429) {
        var wait = parseInt(r.retryAfter || (r.body && r.body.retryAfter) || 0, 10) || 0;
        countdown429(host, (r.body && r.body.message) || '请求被限流。', wait || 60);
        setAskState('被限流（HTTP 429）。');
        return;
      }
      var body = r.body;
      if (!r.ok || !body || body.data === undefined) {
        host.innerHTML = '<p class="xk-notice xk-notice--bad">接口返回 HTTP ' + esc(r.status) + '，没有可用数据。' +
          (body && body.message ? '后端说明：' + esc(body.message) : '') + ' 这里不显示任何替代答案。</p>';
        setAskState('失败（HTTP ' + r.status + '）。');
        return;
      }
      var d = body.data || {};
      var state = d.state || '';
      var cls = state === 'model' ? 'xk-tag--on'
        : (state === 'model-failed' || state === 'retrieval-failed' ? 'xk-tag--bad' : 'xk-tag--warn');
      var html = '<div class="xk-result__verdict">' +
        '<span class="xk-tag ' + cls + '">' + esc(d.stateLabel || state || '未识别状态') + '</span>' +
        /* generated 只有 state=model 时才为 true —— 不把"调用过模型"说成"给出了结论" */
        '<b>' + (d.generated === true ? '模型已生成结论' : '未生成结论（generated=false）') + '</b>' +
        '<span class="xk-hint">耗时 ' + esc((Math.round(elapsedMs / 100) / 10)) + 's' +
          ' · 引用 ' + esc((d.citations || []).length) + ' 条' +
          (d.quota ? ' · 本分钟剩余 ' + esc(num(d.quota.remaining)) + '/' + esc(num(d.quota.limit)) : '') +
        '</span></div>';
      if (d.failureReason) {
        html += '<p class="xk-notice xk-notice--warn"><b>服务端说明：</b>' + esc(d.failureReason) + '</p>';
      }
      if (d.injection && d.injection.blocked) {
        html += '<p class="xk-notice xk-notice--warn">输入命中提示注入护栏（' + esc(d.injection.hitCount || 0) +
          ' 条规则），下面是拦截之后的处理结果。</p>';
      }
      if (d.answer) {
        html += '<div class="xk-md xk-answer">' + mdLite(d.answer) + '</div>';
      } else if (!d.failureReason) {
        html += '<p class="xk-hint">这次没有返回答案正文（<code>state=' + esc(state || '—') + '</code>）。</p>';
      }
      var cites = d.citations || [];
      html += cites.length
        ? '<h3 class="xk-sub xk-answer-hd">引用（' + cites.length + ' 条）</h3><ul class="xk-cites">' + cites.map(citeItem).join('') + '</ul>'
        : '<p class="xk-hint">这次没有引用片段。</p>';
      if (d.clientIpMasked || (d.quota && d.quota.pool)) {
        html += '<p class="xk-note">来源 IP（后端已掩码）：<code>' + esc(d.clientIpMasked || '—') + '</code>' +
          (d.quota && d.quota.pool ? ' · 额度池 <code>' + esc(d.quota.pool) + '</code>' +
            '（已用 ' + esc(num(d.quota.used)) + '，上限 ' + esc(num(d.quota.limit)) + '）' : '') + '</p>';
      }
      host.innerHTML = html;
      if (askQuota) {
        askQuota.textContent = d.quota
          ? '本分钟额度：剩余 ' + num(d.quota.remaining) + '/' + num(d.quota.limit)
          : '额度：未返回';
        askQuota.className = 'xk-tag ' + (d.quota && Number(d.quota.remaining) <= 0 ? 'xk-tag--bad' : '');
      }
      setAskState('上次提问 ' + clockOf(Date.now()) + ' · HTTP ' + r.status +
        (r.rlLimit ? ' · 服务端余额 ' + (r.rlRemaining === null ? '—' : r.rlRemaining) + '/' + r.rlLimit : ''));
    }

    function runAsk() {
      var q = String(askInput.value || '').trim();
      if (!q) {
        askResult.hidden = false;
        askResult.innerHTML = '<p class="xk-notice xk-notice--warn">先写一个问题再提交。</p>';
        return;
      }
      if (asking) return;                       // 同一来源只允许 1 个在飞：前端也不重复发
      asking = true;
      if (askBtn) { askBtn.disabled = true; askBtn.textContent = '等待中…'; }
      askResult.hidden = false;
      askResult.innerHTML = '<p class="xk-hint"><span class="xk-pulse" aria-hidden="true"></span>已提交，正在检索并生成…这次最多等 20 秒。</p>';
      setAskState('等待中（最多 20 秒）…');
      var t0 = Date.now();
      askApi(q).then(function (r) {
        renderAsk(askResult, r, Date.now() - t0);
      }).catch(function (err) {
        if (err && err.timeout) {
          askResult.innerHTML = '<p class="xk-notice xk-notice--warn">等了 20 秒还没返回，这次请求已放弃。' +
            '后端可能正在排队、或模型这一轮很慢 —— 这里不显示任何推测的答案，过一会儿可以重试。</p>';
          setAskState('超时：等待 20 秒无响应。');
        } else {
          askResult.innerHTML = '<p class="xk-notice xk-notice--bad">提问失败（' +
            esc(err && err.status ? 'HTTP ' + err.status : '网络不可达或跨域被拒') +
            '）。没有拿到答案，也没有替代结论。</p>';
          setAskState('请求失败。');
        }
      }).then(function () {
        asking = false;
        if (askBtn) { askBtn.disabled = false; askBtn.textContent = '提交提问'; }
      });
    }

    function renderKb(host, d, q) {
      if (d.available === false) {
        if (kbStatus) { kbStatus.textContent = '检索不可用'; kbStatus.className = 'xk-tag xk-tag--bad'; }
        if (kbNote) kbNote.textContent = '后端自述检索不可用（available:false）。';
        host.innerHTML = '<p class="xk-notice xk-notice--warn"><b>检索不可用</b>（<code>available:false</code>）：' +
          esc(d.note || '后端没有给出更多说明。') + ' 这里不显示任何替代结果。</p>' + rulesHtml(d.rule);
        return;
      }
      var hits = d.results || [];
      if (kbStatus) {
        kbStatus.textContent = hits.length ? '命中 ' + hits.length + ' 条' : '无命中';
        kbStatus.className = 'xk-tag ' + (hits.length ? 'xk-tag--on' : 'xk-tag--off');
      }
      if (kbNote) {
        kbNote.textContent = '关键词「' + q + '」· hitCount=' +
          (d.hitCount === null || d.hitCount === undefined ? '—' : d.hitCount) + (d.note ? ' · ' + d.note : '');
      }
      host.innerHTML = (hits.length
        ? '<ul class="xk-cites">' + hits.map(citeItem).join('') + '</ul>'
        : '<p class="xk-hint">没有命中任何文档片段。换个关键词试试 —— 这里不用"相关推荐"凑数。</p>') + rulesHtml(d.rule);
    }

    /** d.rule{allowedRoots,...}：把后端自述的检索范围也如实列出来 */
    function rulesHtml(rule) {
      if (!rule || !rule.allowedRoots || !rule.allowedRoots.length) return '';
      return '<p class="xk-note">检索范围（后端自述 <code>rule.allowedRoots</code>）：<code>' +
        esc(rule.allowedRoots.join(' , ')) + '</code></p>';
    }

    function runKb() {
      var q = String(kbInput.value || '').trim();
      if (!q) {
        kbResult.hidden = false;
        kbResult.innerHTML = '<p class="xk-notice xk-notice--warn">先写一个关键词再检索。</p>';
        return;
      }
      kbResult.hidden = false;
      kbResult.innerHTML = '<p class="xk-hint">正在检索 <code>/api/public/kb</code> …</p>';
      if (kbStatus) { kbStatus.textContent = '检索中…'; kbStatus.className = 'xk-tag'; }
      fetch(API + '/api/public/kb?q=' + encodeURIComponent(q), {
        method: 'GET', mode: 'cors', credentials: 'omit', cache: 'no-store'
      }).then(function (res) {
        return res.json().catch(function () { return null; }).then(function (body) {
          if (res.status === 429) {
            var wait = parseInt(res.headers.get('Retry-After') || 0, 10) || 0;
            if (kbStatus) { kbStatus.textContent = '被限流'; kbStatus.className = 'xk-tag xk-tag--warn'; }
            countdown429(kbResult, (body && body.message) || '检索请求过于频繁。', wait || 60);
            return;
          }
          if (!res.ok || !body || body.data === undefined) {
            if (kbStatus) { kbStatus.textContent = '检索失败'; kbStatus.className = 'xk-tag xk-tag--bad'; }
            kbResult.innerHTML = '<p class="xk-notice xk-notice--bad">检索失败（HTTP ' + esc(res.status) + '）' +
              (body && body.message ? '：' + esc(body.message) : '') + '</p>';
            return;
          }
          renderKb(kbResult, body.data || {}, q);
        });
      }).catch(function () {
        if (kbStatus) { kbStatus.textContent = '网络不可达'; kbStatus.className = 'xk-tag xk-tag--bad'; }
        kbResult.innerHTML = '<p class="xk-notice xk-notice--bad">检索请求发不出去（网络不可达或跨域被拒）。' +
          '这里不显示本地缓存里编的结果。</p>';
      });
    }

    if (askBtn) askBtn.addEventListener('click', runAsk);
    askInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); runAsk(); } });
    $$('[data-xk-ask-preset]', contentEl).forEach(function (b) {
      b.addEventListener('click', function () {
        askInput.value = b.getAttribute('data-xk-ask-preset') || '';
        runAsk();
      });
    });
    var kbBtn = $('[data-xk-kb-run]', contentEl);
    if (kbBtn) kbBtn.addEventListener('click', runKb);
    kbInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); runKb(); } });
  }

  /* ==========================================================================
     11. 关于（内容由 Hugo 直接渲染，这里只处理小节锚点）
     ========================================================================== */
  function initAbout() { /* 无数据请求：正文是构建期渲染的 */ }

  /* ==========================================================================
     12. 搜索（Ctrl+K，只搜笔记）
     ========================================================================== */
  var searchState = { open: false, items: [], cursor: 0 };

  function updateSearchButtonState() { /* 预留：导航上的搜索按钮始终可用 */ }

  function openSearch() {
    var modal = $('#xk-search');
    modal.hidden = false;
    searchState.open = true;
    var input = $('#xk-search-input');
    input.value = '';
    input.focus();
    $('#xk-search-list').innerHTML = '<li class="xk-modal__empty">正在读取笔记索引 /index.json …</li>';
    loadIndex().then(function (idx) {
      searchState.items = (idx && idx.notes) || [];
      searchState.cursor = 0;
      renderSearch('');
    }).catch(function () {
      $('#xk-search-list').innerHTML = '<li class="xk-modal__empty">笔记索引读取失败。</li>';
    });
  }

  function closeSearch() {
    $('#xk-search').hidden = true;
    searchState.open = false;
  }

  function renderSearch(q) {
    var list = $('#xk-search-list');
    var query = String(q || '').trim().toLowerCase();
    var items = searchState.items;
    if (query) {
      items = items.filter(function (n) {
        var hay = [n.title, (n.categories || []).join(' '), (n.tags || []).join(' '), n.summary, n.text].join(' ').toLowerCase();
        return hay.indexOf(query) >= 0;
      });
    }
    if (!items.length) {
      list.innerHTML = '<li class="xk-modal__empty">没有匹配的笔记。</li>';
      return;
    }
    searchState.filtered = items;
    searchState.cursor = 0;
    list.innerHTML = items.slice(0, 20).map(function (n, i) {
      return '<li class="xk-modal__item' + (i === 0 ? ' is-on' : '') + '" data-xk-idx="' + i + '" data-xk-slug="' + esc(n.slug) + '">' +
        '<b>' + esc(n.title) + '</b><span>' + esc(n.date + ' · ' + (n.categories || []).join(' / ') + ' · ' + n.summary) + '</span></li>';
    }).join('');
  }

  function moveSearch(delta) {
    var items = searchState.filtered || [];
    if (!items.length) return;
    searchState.cursor = (searchState.cursor + delta + items.length) % items.length;
    $$('#xk-search-list .xk-modal__item').forEach(function (li, i) {
      li.classList.toggle('is-on', i === searchState.cursor);
      if (i === searchState.cursor) li.scrollIntoView({ block: 'nearest' });
    });
  }

  function submitSearch() {
    var items = searchState.filtered || [];
    var pick = items[searchState.cursor];
    if (!pick) return;
    closeSearch();
    navigate('#/notes/' + pick.slug);
  }

  /* ==========================================================================
     13. 全局事件绑定
     ========================================================================== */
  // 13.1 站内链接一律走 SPA（整页不刷新）
  document.addEventListener('click', function (e) {
    var toc = e.target.closest ? e.target.closest('a[data-xk-toc]') : null;
    if (toc) {                                  // 目录：手动滚动，不污染路由 hash
      e.preventDefault();
      scrollToEl(document.getElementById(toc.getAttribute('data-xk-toc')));
      return;
    }

    var anchor = e.target.closest ? e.target.closest('a[data-xk-anchor]') : null;
    if (anchor) {
      e.preventDefault();
      scrollToEl(document.getElementById(anchor.getAttribute('href').slice(1)));
      return;
    }

    var feed = e.target.closest ? e.target.closest('[data-xk-goto]') : null;
    if (feed) { navigate(feed.getAttribute('data-xk-goto')); return; }

    var noteLink = e.target.closest ? e.target.closest('a[data-xk-note]') : null;
    if (noteLink) { e.preventDefault(); navigate('#/notes/' + noteLink.getAttribute('data-xk-note')); return; }

    var row = e.target.closest ? e.target.closest('.xk-stream__hd') : null;
    if (row) {                                  // 告警下钻：展开聚合记录自带字段
      var item = row.parentElement;
      var detail = $('.xk-stream__detail', item);
      var open = !detail.hidden;
      detail.hidden = open;
      item.classList.toggle('is-open', !open);
      return;
    }

    var catChip = e.target.closest ? e.target.closest('[data-xk-sev-filter]') : null;
    if (catChip) {                              // 告警级别过滤
      var stream = $('[data-xk-alert-stream]', contentEl);
      $$('[data-xk-sev-filter]', contentEl).forEach(function (c) { c.classList.toggle('is-on', c === catChip); });
      stream.setAttribute('data-filter', catChip.getAttribute('data-xk-sev-filter'));
      var cached = CACHE['/api/public/alerts'];
      if (cached && cached.ok) {
        renderStream(Object.assign({}, cached.data && cached.data.data, { list: (cached.data && cached.data.data && cached.data.data.list) || [] }));
      }
      return;
    }

    var more = e.target.closest ? e.target.closest('[data-xk-more]') : null;
    if (more) {                                 // 长列表：按需展开剩余部分（数据已在内存里）
      if (more.getAttribute('data-xk-more') === 'stream') {
        STREAM_LIMIT = 100000;
        var ca = CACHE['/api/public/alerts'];
        if (ca && ca.ok) renderStream(ca.data && ca.data.data);
      } else {
        HP_TL_LIMIT = 100000;
        var ch = CACHE['/api/public/honeypot'];
        if (ch && ch.ok) renderHoneypot(ch.data && ch.data.data, [{ name: 'honeypot', res: { data: ch.data, syncedAt: ch.syncedAt }, err: null }]);
      }
      return;
    }

    var item2 = e.target.closest ? e.target.closest('#xk-search-list .xk-modal__item') : null;
    if (item2) {
      var slug = item2.getAttribute('data-xk-slug');
      closeSearch();
      navigate('#/notes/' + slug);
      return;
    }

    var hit = e.target.closest ? e.target.closest('[data-xk-search-open]') : null;
    if (hit) { openSearch(); return; }
    if (e.target.closest && (e.target.closest('[data-xk-search-close]'))) { closeSearch(); return; }

    var link = e.target.closest ? e.target.closest('a[href]') : null;
    if (!link) return;
    if (link.target === '_blank' || link.hasAttribute('download')) return;
    var href = link.getAttribute('href') || '';
    // "#/notes"、" /#/notes" 两种写法都要接住（导航里用的是后者）
    var hi = href.indexOf('#/');
    if (hi === 0 || (hi === 1 && href.charAt(0) === '/')) {
      e.preventDefault();
      navigate(href.slice(hi));
      return;
    }
    if (isInternalRoute(href)) {
      e.preventDefault();
      var mapped = routeFromPath(href.split('#')[0]);
      navigate('#/' + (mapped.name === 'note' ? 'notes/' + mapped.slug : mapped.name));
    }
  });

  // 13.2 键盘：Ctrl/Cmd+K 搜索、上下键选择、Esc 关闭
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      searchState.open ? closeSearch() : openSearch();
      return;
    }
    if (!searchState.open) return;
    if (e.key === 'Escape') { closeSearch(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); moveSearch(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); moveSearch(-1); }
    else if (e.key === 'Enter') { e.preventDefault(); submitSearch(); }
  });

  document.addEventListener('input', function (e) {
    if (e.target && e.target.id === 'xk-search-input') renderSearch(e.target.value);
  });

  // 13.3 前进/后退 + 手改 hash
  window.addEventListener('popstate', function () { render(currentRoute()); });
  window.addEventListener('hashchange', function () {
    var r = parseHash(location.hash);
    if (r) render(r);
  });

  // 13.4 笔记索引空闲预取：不占首屏带宽，但点笔记时已经在本地
  function prefetchIndex() {
    loadIndex().catch(function () { /* 失败就等用户真的点开再报错 */ });
  }
  if (window.requestIdleCallback) requestIdleCallback(prefetchIndex, { timeout: 4000 });
  else setTimeout(prefetchIndex, 2500);

  /* ==========================================================================
     14. 启动
     ========================================================================== */
  render(currentRoute());
})();
