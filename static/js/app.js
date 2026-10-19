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

  var SEV_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4 };
  var SEV_CLASS = { CRITICAL: 'critical', HIGH: 'high', MEDIUM: 'medium', LOW: 'low', INFO: 'info' };

  /* 备注：第十一轮把监测中心改成"一页大屏"后，原来的长列表分页常量（STREAM_LIMIT /
     HP_TL_LIMIT）连同用它们的加载器一起删掉了 —— 不留死代码。 */

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

  /* 端点预算（站主第九轮 ⑤「公开端点有 20 次/分钟限流，别把轮询调快」）：
     一个视图一次轮询读几个端点由调用方用 weight 告知，这里据此抬高轮询下限，
     让「端点个数 × 每分钟轮询次数」不超过 12 —— 只在需要时【放慢】，从不加快。
       1–2 个端点 → 仍是 10–15s（规格 §5 原值）
       4 个端点（主页）→ 下限 20s ≈ 12 次/分钟，给手动刷新和切栏目留 40% 余量 */
  var RPM_BUDGET = 12;
  function intervalFloor(weight) {
    var w = Math.max(1, Number(weight) || 1);
    return Math.max(POLL_MIN, Math.ceil(w * 60000 / RPM_BUDGET));
  }

  function startPolling(loadFn, weight) {
    stopPolling();
    var stopped = false, fails = 0, timer = null;
    var floor = intervalFloor(weight);

    function interval() {
      // 自适应：请求越慢，间隔越靠近上限；快请求落到下限。
      // 上限 15s 是规格硬约束 —— 服务端限流 20 次/分钟不放宽；
      // 端点多的视图下限由 intervalFloor 抬高（见上）。
      var lo = floor;
      var hi = Math.max(floor, POLL_MAX);
      return Math.max(lo, Math.min(hi, Math.round(LAST_RTT * 6)));
    }

    function clear() { if (timer) { clearTimeout(timer); timer = null; } }
    function schedule(ms) { clear(); if (!stopped) timer = setTimeout(tick, ms); }

    function tick() {
      if (stopped) return;
      timer = null;
      /* 站主第十轮 ④：页面不可见时【彻底停表】—— 不是"每 10s 醒来发现隐藏再睡回去"，
         而是根本不排下一个定时器；恢复可见时由 visibilitychange → resume() 立刻补一次。
         这样在后台标签页里一个请求都不会发（限流预算全部留给前台）。 */
      if (document.hidden) return;
      loadFn().then(function () {
        fails = 0;
      }).catch(function () {
        fails += 1;   // 失败次数由各视图自己写进同步文案
      }).then(function () {
        if (stopped || document.hidden) return;
        /* 失败退避：连续失败按 2^n 拉长间隔，封顶 BACKOFF_MAX(2 分钟)，只放慢不加快 */
        var delay = fails ? Math.min(interval() * Math.pow(2, fails), BACKOFF_MAX) : interval();
        schedule(delay);
      });
    }

    activePoller = {
      stop: function () { stopped = true; clear(); },
      /* 暂停：只停表，不改变 stopped（resume 后还能接着轮询） */
      pause: function () { clear(); },
      /* 恢复：清空失败计数并【立刻补一次】，不等下一个间隔 */
      resume: function () { if (stopped) return; fails = 0; clear(); tick(); },
      kick: function () { if (stopped) return; fails = 0; clear(); tick(); }
    };
    if (document.hidden) { /* 开局就不可见：不排任何定时器，等 visibilitychange */ }
    else { tick(); }
  }

  // 切到后台/标签隐藏即【暂停轮询】；回到前台立刻补一次（规格 §5 / 站主第十轮 ④）
  document.addEventListener('visibilitychange', function () {
    if (!activePoller) return;
    if (document.hidden) activePoller.pause();
    else activePoller.resume();
  });

  /* ==========================================================================
     5. 路由（hash 路由 + 深链兼容）
     ========================================================================== */
  var VIEW_TPL = {
    home: 'tpl-home', notes: 'tpl-notes', note: 'tpl-note',
    monitor: 'tpl-monitor', ai: 'tpl-ai',
    about: 'tpl-about', notfound: 'tpl-notfound'
  };
  var NAV_OF_ROUTE = { home: 'home', notes: 'notes', note: 'notes', monitor: 'monitor', ai: 'ai', about: 'about' };
  /* ★T27 收尾（2026-10-15 窗口 Q）：靶场页已删 ⇒ hash 别名表（labs→range）与
     tpl-range 一起作废。原来那段注释记录的 bug（hugo.toml 菜单 identifier="labs" 找不到
     VIEW_TPL['labs']）随菜单项一起消失：hugo.toml 里已经没有 range 这一项了。 */

  function parseHash(hash) {
    var m = String(hash || '').replace(/^#/, '').match(/^\/?([a-z-]+)(?:\/([^/?#]+))?/i);
    if (!m) return null;
    var name = m[1].toLowerCase(), arg = m[2] ? decodeURIComponent(m[2]) : null;
    if (HASH_ALIAS[name]) { name = HASH_ALIAS[name]; }
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
    /* ★T27 收尾：靶场页的路由匹配（labs → range）随页面删除一起摘掉（老地址由
       content/alerts 的 aliases 0 秒跳到监测中心，不再经过前端路由）。 */
    /* ★ 第十一轮修的一个真 bug：以前这里没有 /ai/ 分支 —— 所以直接打开 /ai/（服务端渲染正确）
       之后，app.js 会把路由判成 notfound 并把整页替换成 404。实测就是"无 JS 正常、有 JS 变 404"。
       现在补上，并把这个坑写进断言（见 _dev/verify-redesign.ps1 第 12 组）。 */
    if (/^\/ai\/?$/.test(p)) return { name: 'ai' };
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
    return /^\/(posts|about|projects|demo|alerts|categories|tags)/.test(href) || href === '/';
  }

  /** 站内跳转：URL 统一收敛成 /#/<route>，只替换 #content，绝不整页刷新 */
  function navigate(path) {
    var hash = path.charAt(0) === '#' ? path : '#' + path;
    history.pushState({ xk: 1 }, '', '/' + hash);
    render(parseHash(hash) || { name: 'notfound' });
  }

  /* 站点级小工具（第十一轮）：主题、阅读进度、引用、回到顶部、轻提示 */
  /* ========================================================================== */
  var THEME_KEY = 'xk-theme';
  var THEMES = ['tech', 'read'];
  function currentTheme() {
    var t = document.documentElement.getAttribute('data-xk-theme');
    return THEMES.indexOf(t) >= 0 ? t : 'tech';
  }
  function applyTheme(t, persist) {
    if (THEMES.indexOf(t) < 0) t = 'tech';
    document.documentElement.setAttribute('data-xk-theme', t);
    var btn = document.querySelector('[data-xk-theme-toggle]');
    if (btn) {
      var isRead = t === 'read';
      btn.setAttribute('aria-pressed', isRead ? 'true' : 'false');
      var lbl = btn.querySelector('[data-xk-theme-label]');
      if (lbl) lbl.textContent = isRead ? '阅读模式' : '科技模式';
    }
    if (persist) { try { localStorage.setItem(THEME_KEY, t); } catch (e) { /* 隐私模式忽略 */ } }
  }
  function toggleTheme() {
    applyTheme(currentTheme() === 'read' ? 'tech' : 'read', true);
  }

  /* 阅读进度：把 #content 的滚动量写成一个 CSS 变量，由 .xk-prog span 的宽度呈现 */
  function updateProgress() {
    var bar = $('[data-xk-prog]');
    if (!bar) return;
    var sc = contentEl.scrollHeight - contentEl.clientHeight;
    var p = sc > 8 ? (contentEl.scrollTop / sc) : 0;
    bar.style.setProperty('--xk-prog', (p * 100).toFixed(2) + '%');
    bar.classList.toggle('is-on', p > 0.004);
  }

  function toast(msg) {
    var host = $('#xk-toast');
    if (!host) {
      host = document.createElement('div');
      host.id = 'xk-toast';
      host.className = 'xk-toast';
      host.setAttribute('role', 'status');
      host.setAttribute('aria-live', 'polite');
      document.body.appendChild(host);
    }
    host.textContent = msg;
    host.classList.add('is-on');
    clearTimeout(host.__t);
    host.__t = setTimeout(function () { host.classList.remove('is-on'); }, 2400);
  }

  /** 引用文本：作者 · 标题 · 日期 · 链接（用于"复制引用"，不改动页面内容） */
  function citationText(title, date, url) {
    return (boot.siteName || 'xiaokeqing') + '｜' + (title || '') +
      (date ? '｜' + date : '') + (url ? '｜' + url : '');
  }

  /* ==========================================================================
     6. 视图渲染
     ========================================================================== */
  var contentEl = document.getElementById('content');

  /* ★ 第十一轮：把 <main> 里服务端渲染好的内容收进一个 .xk-ssr 容器。
     服务端在 main 上写了 data-xk-ssr="<路由>"（纯标记，不参与样式），
     这里据此判断"当前这一份就是这条路由的最终内容"，包一层容器后交给 render() 复用。
     不走这一步，render() 会把 main 当成空容器，点导航前就把服务端渲染的正文丢掉。 */
  var SSR_HOST = null;
  (function () {
    var name = contentEl.getAttribute('data-xk-ssr');
    if (!name || !contentEl.children.length) return;
    var host = document.createElement('div');
    host.className = 'xk-ssr';
    host.setAttribute('data-xk-ssr', name);
    while (contentEl.firstChild) host.appendChild(contentEl.firstChild);
    contentEl.appendChild(host);
    SSR_HOST = name;
  })();
  var INDEX = null;          // 笔记索引（/index.json）

  /** #content 里由构建期渲染好的那一份视图（data-xk-ssr 与路由同名时直接复用） */
  function ssrHostFor(route) {
    var first = contentEl.firstElementChild;
    if (!first || !first.classList.contains('xk-ssr')) return null;
    return first.getAttribute('data-xk-ssr') === route ? first : null;
  }

  /* 折叠件语义（站主第十轮 ④）：
     <details>/<summary> 本身就有原生展开语义，但很多辅助技术与自动化检查要求把状态写成
     aria-expanded + aria-controls。这里两者都给：
       · aria-controls 指向被折叠的那一块（没有 id 就自动补一个，保证指得着）；
       · aria-expanded 跟随 <details> 的 open 状态实时同步（toggle 事件）。
     所有折叠件（首页「数据口径」、靶场结果里的「动作与局限」）都走这一条通路。 */
  var XK_UID = 0;
  function syncDisclosures(root) {
    $$('details', root || document).forEach(function (d) {
      var s = d.querySelector('summary');
      if (!s) return;
      var body = d.querySelector('.xk-meta, .xk-check__kv, .xk-caliber__body, [data-xk-disclosure]') ||
                 d.lastElementChild;
      if (!body) return;
      if (body === s) body = null;
      if (body && !body.id) body.id = 'xk-disc-' + (++XK_UID);
      if (body && body.id) s.setAttribute('aria-controls', body.id);
      s.setAttribute('aria-expanded', d.open ? 'true' : 'false');
      if (!d.__xkAria) {
        d.__xkAria = true;
        d.addEventListener('toggle', function () {
          s.setAttribute('aria-expanded', d.open ? 'true' : 'false');
        });
      }
    });
  }

  function render(route) {
    stopPolling();
    /* 第十一轮 SSR（DEFECTS.md · B5）：本页在构建期已经把【当前这条路由】渲染进 <main> 了。
       开局时直接复用它，不再 cloneNode 覆盖 —— 否则首屏会出现一次内容替换（闪烁），
       而且会把服务端渲染好的正文白白丢掉。从别的路由切回来时，首屏那一份已经被换掉，
       这时才走正常的模板 clone 通路。 */
    /* 诊断面包屑（无副作用，属性 + 不参与任何逻辑）：路由名、首个子元素、模板是否存在。
       这条在排查"服务端渲染正确但页面显示 404"时是决定性的 —— 保留它没有成本。 */
    try {
      document.documentElement.setAttribute('data-xk-render', route.name);
      var __f = contentEl.firstElementChild;
      document.documentElement.setAttribute('data-xk-first', __f ? (String(__f.className) + '|' + (__f.getAttribute('data-xk-ssr') || '')) : 'none');
      document.documentElement.setAttribute('data-xk-tpl', String(!!document.getElementById(VIEW_TPL[route.name] || 'tpl-notfound')));
      var __kids = contentEl.children, __pairs = [];
      for (var __i = 0; __i < Math.min(__kids.length, 12); __i++) {
        __pairs.push(__kids[__i].tagName + '#' + (__kids[__i].id || '-') + '.' + String(__kids[__i].className || '-'));
      }
      document.documentElement.setAttribute('data-xk-kids', String(__kids.length) + ' :: ' + __pairs.join(' ~ '));
      document.documentElement.setAttribute('data-xk-contentid', String(contentEl && contentEl.id) + '/' + String(contentEl && contentEl.tagName));
      window.__xkDiag = { first: __f ? (String(__f.className) + '|' + (__f.getAttribute('data-xk-ssr') || '')) : 'none', n: contentEl.children.length };
    } catch (e) { }
    var ssr = ssrHostFor(route.name) || (route.name === 'note' ? ssrHostFor('note') : null);
    var ssrSlug = ssr ? ssr.getAttribute('data-xk-ssr-slug') : null;
    var canReuse = !!ssr && (!route.slug || !ssrSlug || ssrSlug === route.slug);
    if (canReuse) {
      var others = $$('.xk-ssr', contentEl).filter(function (n) { return n !== ssr; });
      others.forEach(function (n) { n.remove(); });
    } else {
      var tpl = document.getElementById(VIEW_TPL[route.name] || 'tpl-notfound');
      if (!tpl) tpl = document.getElementById('tpl-notfound');
      if (!tpl) {
        /* 理论上不会发生（每条路由都有模板）；但绝不让"模板缺失"把整页炸成空白 */
        contentEl.innerHTML = '<div class="xk-wrap xk-page"><p class="xk-notice xk-notice--bad">' +
          '这个视图的模板没有随页面下发（' + esc(String(route.name)) + '）。请刷新页面重试。</p></div>';
        return;
      }
      contentEl.replaceChildren(tpl.content.cloneNode(true));
    }
    window.scrollTo(0, 0);
    contentEl.scrollTop = 0;
    updateProgress();

    // 左侧栏导航高亮（导航本身不动，只换 class）+ aria-current（站主第十轮 ④）
    var active = NAV_OF_ROUTE[route.name];
    $$('.xk-side__link').forEach(function (a) {
      var on = a.getAttribute('data-xk-nav') === active;
      a.classList.toggle('is-on', on);
      if (on) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });

    // 折叠件（「数据口径」/「动作与局限」）把展开状态用 aria-expanded 显式暴露出来，
    // 并用 aria-controls 指向被展开的那块内容（站主第十轮 ④）
    syncDisclosures(contentEl);

    var head = contentEl.firstElementChild;
    if (route.name === 'home') { initHome(); initHeroPlay(); }
    else if (route.name === 'notes') initNotes();
    else if (route.name === 'note') { initNote(route.slug); initNoteExtras(); }
    else if (route.name === 'monitor') initMonitor(route.tab);
    /* ★T27 收尾：route.name === 'range' 的分支随靶场页删除一起摘掉（initRange 已无路由可进）*/
    else if (route.name === 'ai') initAi();
    else if (route.name === 'about') initAbout();
    else if (route.name === 'notfound') { /* 静态内容 */ }
    if (head) head.focus && head.setAttribute('tabindex', '-1');

    updateSearchButtonState();
  }

  /* ==========================================================================
     7. 主页（站主 2026-10-13 第九轮）：Hero 四数字 + 功能导览角标 + 右栏拦截动态
     --------------------------------------------------------------------------
     · Hero 四个核心数字：全部来自真实接口，页面上印着口径；取不到就写「未接入」。
        ① 24h 告警  ← /api/public/alerts · stats24h.total（24 小时【未去重】上报量）
                      注：/api/public/overview 只有「最近 200 条窗口」口径、没有 24h 总量字段，
                      所以这里用 alerts 的真字段；overview 只在 alerts 取不到时降级顶上，
                      且口径文案会改成「窗口数，不是 24h 总量」——不拿窗口数冒充满。
        ② 蜜罐事件  ← /api/public/honeypot · total
        ③ 护栏拦截  ← /api/public/audit · summary.blockedByGuard
        ④ 单元测试  ← 构建期常量（hugo.toml params.tests*，真值来自 SecAgent surefire 汇总）
     · 功能导览角标：监测中心 ← alerts.stats24h.total 压缩成「24h 21.3万条」；
       其余三个角标是构建期就能核对的真实事实（笔记篇数 / 靶场检测样例数 / 零第三方依赖）。
     · 右栏拦截动态：同类别 + 同来源 IP 聚合成 3–5 条中文可读条目；
       顶部三个小数字（今日拦截 / 生效中 / 护栏拦截）来自 audit summary + blocks；
       拿不到新鲜数据时标题写「最近同步 · 拦截动态」，不写「实时」。
     端点预算：主页一次轮询读 4 个公开端点 → startPolling 把下限抬到 20s（≈12 次/分钟）。
     ========================================================================== */
  var HOME_JOBS = [
    { name: 'overview', path: '/api/public/overview' },
    { name: 'audit', path: '/api/public/audit' },
    { name: 'honeypot', path: '/api/public/honeypot' },
    { name: 'alerts', path: '/api/public/alerts' }
  ];
  var FEED_ROWS_MAX = 5;      // 站主：右栏只留 3–5 条
  var LIVE_FRESH_MS = 90000;  // 90s 内有成功同步才算"实时"，否则标题写「最近同步」

  /** {code,message,data} 信封 → data；已经是裸对象就原样返回 */
  function envelope(res) {
    var b = res && res.data;
    return b && b.data ? b.data : b;
  }

  function partData(parts, name) {
    var p = parts.filter(function (x) { return x.name === name; })[0];
    return p && p.res ? envelope(p.res) : null;
  }

  function initHome() {
    $$('[data-xk-api-base]').forEach(function (n) { n.textContent = API.replace(/^https?:\/\//, ''); });

    function readHomePart(j) {
      return readApi(j.path).then(function (res) {
        return { name: j.name, path: j.path, res: res, err: null };
      }).catch(function (err) {
        // 失败时退回 localStorage 里的快照：数字照显，但同步文案会如实写「上次同步于 X 分钟前」
        return {
          name: j.name, path: j.path, err: err,
          res: err.snapshot ? { data: err.snapshot.data, syncedAt: err.snapshot.syncedAt } : null
        };
      });
    }

    var load = function () {
      return Promise.all(HOME_JOBS.map(readHomePart)).then(function (parts) {
        /* 服务端的 24h 统计会抖：冷缓存下 /api/public/alerts 常返回 stats24h.available=false，
           同一个 URL 过 15s（服务端缓存热了）再取就是真值 —— 实测记录见交付报告。
           所以这里【只在确实 available=false 时】补一次请求（多这一次，且不进快照）；
           补到真值就用，补不到就按降级口径显示（绝不拿窗口数冒充满 24h 总量）。 */
        var al = parts.filter(function (p) { return p.name === 'alerts'; })[0];
        var d = al && al.res ? envelope(al.res) : null;
        if (!d || !d.stats24h || d.stats24h.available !== false) return parts;
        return new Promise(function (r) { setTimeout(r, 1200); })
          .then(function () { return readApi('/api/public/alerts', { force: true }); })
          .then(function (res) {
            var d2 = envelope(res);
            if (d2 && d2.stats24h && d2.stats24h.available !== false) { al.res = res; al.err = null; al.retried = true; }
            return parts;
          })
          .catch(function () { return parts; });
      }).then(renderHome);
    };

    startPolling(load, HOME_JOBS.length);
  }

  function renderHome(parts) {
    var ov = partData(parts, 'overview');
    var au = partData(parts, 'audit');
    var hp = partData(parts, 'honeypot');
    var al = partData(parts, 'alerts');

    renderHeroStats(ov, au, hp, al);
    renderFeed(au, al, hp, parts);
    renderMinis(au);
    renderHoneypotMini(hp);
    setSync('feed', syncTextOf(parts));
    setSync('hp', syncTextOf(parts));
  }

  /** 压缩成中文数量口诀（只用于角标这种"小数据"，不改动真值本身） */
  function compactNum(n) {
    if (n === null || n === undefined || n === '' || isNaN(Number(n))) return null;
    var v = Number(n);
    if (v >= 100000000) return (v / 100000000).toFixed(1).replace(/\.0$/, '') + '亿';
    if (v >= 10000) return (v / 10000).toFixed(1).replace(/\.0$/, '') + '万';
    return String(v);
  }

  function setStat(key, value, caliber) {
    var n = document.querySelector('[data-xk-stat="' + key + '"]');
    if (n) n.textContent = (value === null || value === undefined || value === '') ? '未接入' : value;
    var c = document.querySelector('[data-xk-caliber="' + key + '"]');
    if (c && caliber) c.textContent = caliber;
  }

  function renderHeroStats(ov, au, hp, al) {
    /* ① 24h 告警（口径收进 <details>，标题只写"真值 + 本来就有的相对量"） */
    var s24 = al && al.stats24h;
    var v24 = (s24 && s24.available !== false && s24.total !== null && s24.total !== undefined) ? s24.total : null;
    if (v24 !== null) {
      setStat('alerts24h', num(v24), null);
      setTrend('alerts24h', trendLineOf(s24));
    } else if (ov && ov.alerts && ov.alerts.windowCount !== null && ov.alerts.windowCount !== undefined) {
      setStat('alerts24h', num(ov.alerts.windowCount), null);
      setTrend('alerts24h', '窗口口径（' + num(ov.alerts.windowSize) + ' 条，不是 24h 总量）');
    } else {
      setStat('alerts24h', null, null);
      setTrend('alerts24h', '本次取不到 → 未接入，不补数');
    }

    /* ② 蜜罐事件：相对量只用同一响应里本来就有的字段（连接 / 登录 / 登录失败） */
    var hpTotal = hp && hp.total !== undefined ? hp.total : null;
    setStat('honeypot', hpTotal === null ? null : num(hpTotal), null);
    if (hpTotal === null) {
      setTrend('honeypot', '本次取不到 → 未接入，不补数');
    } else {
      var parts = [];
      if (hp.connections !== undefined) parts.push('连接 ' + num(hp.connections));
      if (hp.logins !== undefined) parts.push('登录 ' + num(hp.logins));
      if (hp.loginFails !== undefined) parts.push('登录失败 ' + num(hp.loginFails));
      setTrend('honeypot', parts.length ? (parts.join(' · ') + '（同一响应内的字段）') : '服务端字段原样展示');
    }

    /* ③ 护栏拦截 + 封禁留痕（相对量 = 同一次 audit 响应里的其他计数） */
    var guard = au && au.summary && au.summary.blockedByGuard !== undefined ? au.summary.blockedByGuard : null;
    setStat('guard', guard === null ? null : num(guard), null);
    if (guard === null) {
      setTrend('guard', '本次取不到 → 未接入，不补数');
    } else {
      var sm = (au && au.summary) || {};
      var gp = [];
      if (sm.blockTotal !== undefined) gp.push('封禁留痕共 ' + num(sm.blockTotal) + ' 条');
      if (sm.blockActive !== undefined) gp.push('当前生效 ' + num(sm.blockActive));
      if (sm.executedActions !== undefined) gp.push('已执行动作 ' + num(sm.executedActions));
      setTrend('guard', gp.length ? gp.join(' · ') : '被护栏拦下的动作数');
    }

    /* ④ 单元测试：数值与口径都在模板里（构建期常量），这里不需要接口 */
  }

  /**
   * 24h 趋势（"本来就有的口径"，不编对比基准）：
   * stats24h.trend 是服务端给的 25 个小时桶，全部落在同一个 24h 窗口内 ——
   * 所以这里只做"窗口内最近 1 小时 vs 前 3 小时均值"的比较，并把两个原始数字都写出来，
   * 读的人可以自己核。取不到桶就如实写"未接入"。
   */
  function trendLineOf(s24) {
    if (!s24 || s24.available === false) return '本次取不到 24h 聚合 → 未接入';
    var t = s24.trend;
    if (!Array.isArray(t) || t.length < 5) return '服务端未返回逐小时桶 → 本次不给趋势';
    var arr = t.map(function (p) { return Number(p.count) || 0; });
    var cur = arr[arr.length - 1];
    var base = (arr[arr.length - 4] + arr[arr.length - 3] + arr[arr.length - 2]) / 3;
    var txt = '最近 1 小时 ' + num(cur) + ' · 前 3 小时均值 ' + num(Math.round(base));
    if (base > 0) {
      var d = Math.round((cur - base) / base * 100);
      var sign = d > 0 ? '+' : '';
      txt = (d > 0 ? '↑ ' : (d < 0 ? '↓ ' : '→ ')) + sign + d + '%　' + txt;
    }
    return txt + '（同一 24h 窗口内，现算）';
  }

  function setTrend(key, text) {
    var n = document.querySelector('[data-xk-trend="' + key + '"]');
    if (n) n.textContent = text || '—';
  }

  /* ---------- 右栏：三个小数字（今日拦截 / 生效中 / 护栏拦截） ---------- */
  function todayKey(d) {
    function p(n) { return (n < 10 ? '0' : '') + n; }
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
  }

  function setMini(key, value, warn) {
    var n = document.querySelector('[data-xk-mini="' + key + '"]');
    if (!n) return;
    n.textContent = (value === null || value === undefined || value === '') ? '未接入' : value;
    n.className = 'xk-mini__num' + (warn ? ' is-warn' : '');
  }

  function setMiniCtx(key, text) {
    var n = document.querySelector('[data-xk-mini-ctx="' + key + '"]');
    if (n) n.textContent = text || '—';
  }

  /**
   * 三个小数字 + 【每个 0 的上下文】（DEFECTS.md · A5）。
   * 站主要求不造假：0 就是 0，但必须让读的人知道这个 0 是什么意思 ——
   * 所以每个数字都补一行"最近一次是什么时候 / 当前是不是真的没有"。
   * 这一行全部由真实字段算出（blocks[].createdAt / unblockedAt / summary），没有估计值。
   */
  function renderMinis(au) {
    var s = (au && au.summary) || {};
    var blocks = (au && Array.isArray(au.blocks)) ? au.blocks : null;

    /* 今日拦截 */
    if (blocks) {
      var key = todayKey(new Date());
      var today = blocks.filter(function (b) { return String(b.createdAt || '').slice(0, 10) === key; });
      setMini('today', num(today.length), today.length > 0);
      if (today.length > 0) {
        setMiniCtx('today', '最近一次 ' + String(today[0].createdAt || '').slice(5, 16) + ' · ' + (today[0].ip || '—'));
      } else if (blocks.length) {
        setMiniCtx('today', '最近一次 ' + String(blocks[0].createdAt || '').slice(5, 16) + ' · ' + (blocks[0].ip || '—'));
      } else {
        setMiniCtx('today', '审计留痕里还没有封禁记录');
      }
    } else {
      setMini('today', null, false);
      setMiniCtx('today', '本次取不到处置审计 → 未接入');
    }

    /* 生效中 */
    var active = s.blockActive === undefined ? null : Number(s.blockActive);
    setMini('active', active === null ? null : num(active), active > 0);
    if (active === null) {
      setMiniCtx('active', '本次取不到 → 未接入');
    } else if (active > 0) {
      setMiniCtx('active', '仍在封禁期内的条数');
    } else if (blocks && blocks.length) {
      var un = blocks.filter(function (b) { return b.unblocked; })[0] || blocks[0];
      setMiniCtx('active', '最后一条已于 ' + String(un.unblockedAt || '').slice(5, 16) + ' 解除');
    } else {
      setMiniCtx('active', '没有仍在生效的封禁');
    }

    /* 护栏拦截 */
    var g = s.blockedByGuard === undefined ? null : Number(s.blockedByGuard);
    setMini('guard', g === null ? null : num(g), g > 0);
    setMiniCtx('guard', g === null ? '本次取不到 → 未接入'
      : (s.blockTotal !== undefined ? '封禁留痕共 ' + num(s.blockTotal) + ' 条' : '被护栏拦下的动作数'));

    renderHoneypotMini(CACHE['/api/public/honeypot'] ? envelope(CACHE['/api/public/honeypot'].data) : null);
  }

  /* ---------- 右栏入口卡：真实聚合（原「功能导览」的位置，DEFECTS.md · A3） ----------
     三块内容全部来自 /api/public/honeypot 的同一份响应：
       · 被攻击最多的来源（topSources，后端已把 IP 掩码到网段）
       · 尝试口令的结构（从 topCredentials 现场归纳：长度 / 是否与用户名相同 / 字符构成）
       · 攻击者用的客户端（topClients，客户端指纹）
     纪律：**完整口令不下发** —— 这里只输出结构分布与"掩码示例"（保留首末字符，中间打星）。 */
  function maskSecret(s) {
    var t = String(s || '');
    if (t.length <= 2) return '**';
    return t.charAt(0) + new Array(Math.max(1, t.length - 2) + 1).join('*') + t.charAt(t.length - 1);
  }

  function credStructure(creds) {
    var buckets = { '长度 ≤ 6': 0, '长度 7–9': 0, '长度 ≥ 10': 0 };
    var same = 0, total = 0, digits = 0, mixed = 0, samples = [];
    (creds || []).forEach(function (c) {
      var key = String(c.key || '');
      var i = key.indexOf(' / ');
      if (i < 0) return;
      var u = key.slice(0, i), p = key.slice(i + 3);
      if (!p) return;
      total++;
      if (p.length <= 6) buckets['长度 ≤ 6']++;
      else if (p.length <= 9) buckets['长度 7–9']++;
      else buckets['长度 ≥ 10']++;
      if (u && u === p) same++;
      if (/^\d+$/.test(p)) digits++;
      if (/[A-Za-z]/.test(p) && /\d/.test(p)) mixed++;
      if (samples.length < 3 && p.length >= 4) samples.push(u + ' / ' + maskSecret(p));
    });
    return { buckets: buckets, same: same, total: total, digits: digits, mixed: mixed, samples: samples };
  }

  function renderHoneypotMini(hp) {
    var hostS = document.querySelector('[data-xk-hp-sources-mini]');
    var hostC = document.querySelector('[data-xk-hp-creds-mini]');
    var hostK = document.querySelector('[data-xk-hp-clients-mini]');
    var noteC = document.querySelector('[data-xk-hp-creds-note]');
    if (!hostS && !hostC && !hostK) return;

    if (!hp) {
      [hostS, hostC, hostK].forEach(function (h) {
        if (h) h.innerHTML = '<p class="xk-hint">蜜罐接口本次取不到 → 未接入，不补数。</p>';
      });
      if (noteC) noteC.textContent = '';
      return;
    }

    if (hostS) hostS.innerHTML = distList((hp.topSources || []).slice(0, 3), true) || '<p class="xk-hint">没有来源数据。</p>';
    if (hostK) hostK.innerHTML = distList((hp.topClients || []).slice(0, 3), true) || '<p class="xk-hint">没有客户端指纹。</p>';

    if (hostC) {
      var st = credStructure(hp.topCredentials);
      if (!st.total) {
        hostC.innerHTML = '<p class="xk-hint">本次没有可归纳的尝试口令。</p>';
      } else {
        var rows = Object.keys(st.buckets).map(function (k) {
          return { label: k, count: st.buckets[k] };
        });
        rows.push({ label: '与用户名相同', count: st.same });
        rows.push({ label: '纯数字', count: st.digits });
        rows.push({ label: '字母 + 数字', count: st.mixed });
        hostC.innerHTML = distList(rows, false);
      }
      if (noteC) {
        noteC.textContent = st.total
          ? '按采样榜单（' + num(st.total) + ' 条）归纳；完整口令不下发，示例为掩码：' + (st.samples.join('、') || '—')
          : '';
      }
    }
  }

  /* ---------- 右栏：3–5 条中文可读的聚合条目 ----------
     为什么这样聚合：原来直接把 audit.actions 一条条摊开，结果是 8 条几乎一样的
     「block-ip → ***・18 小时前」（护栏连续拦下同一个动作），看着像假数据。
     现在按【类别 + 来源 IP / 动作】合并计数，并且同一类别最多占 2 行，
     保证 3–5 行里既有蜜罐、也有护栏与封禁留痕 —— 既真实也不单调。 */
  function feedGroups(au, al, hp) {
    var groups = {};   // key → { kind, level, label, ip, count, ms, source, goto }
    var reasons = {};  // key → { 原因: 次数 }（护栏拦下的原因，取最多的那个写进标签）

    var SEV_RANK = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4 };

    function put(key, g) {
      var cur = groups[key];
      if (!cur) { groups[key] = g; return; }
      cur.count += g.count;
      if (g.ms && (!cur.ms || g.ms > cur.ms)) cur.ms = g.ms;
      if (SEV_RANK[g.level] < SEV_RANK[cur.level]) cur.level = g.level;   // 取最严重的那条
    }

    /* (a) 蜜罐：topSources 是服务端给的"每个来源 IP 真实计数"，直接原样展示。
           只取最上面 1 条 —— 否则同一类条目会把 3–5 条的位置全占满，右栏又变单调。 */
    if (hp && Array.isArray(hp.topSources)) {
      var hpMs = parseTs(hp.generatedAt);
      hp.topSources.slice(0, 1).forEach(function (s) {
        put('hp|' + s.key, {
          kind: 'hp', level: 'HIGH', label: '蜜罐捕获 SSH 攻击来源', ip: s.key,
          count: Number(s.count) || 0, ms: hpMs, source: '/api/public/honeypot · topSources',
          goto: '#/monitor/honeypot'
        });
      });
    }

    /* (a2) 蜜罐时间线：接口返回窗口内的真实事件（新连接 / 登录尝试 / 客户端指纹），
           按"事件类型 + 来源 IP"计数。次数口径是"接口这次返回的窗口内条数"，标签里会写明来源。 */
    if (hp && Array.isArray(hp.timeline)) {
      hp.timeline.forEach(function (e) {
        var kind = String(e.kind || '');
        var label = /登录/.test(kind) ? '蜜罐捕获 SSH 登录尝试'
                  : /连接/.test(kind) ? '蜜罐新增 SSH 连接'
                  : /指纹/.test(kind) ? '蜜罐 SSH 客户端指纹'
                  : '蜜罐事件 · ' + kind;
        var ip = e.srcIp && e.srcIp !== '***' ? e.srcIp : '';
        put('hptl|' + label + '|' + ip, {
          kind: 'hptl', level: /登录/.test(kind) ? 'HIGH' : 'MEDIUM', label: label, ip: ip,
          count: 1, ms: parseTs(e.time),
          source: '/api/public/honeypot · timeline（接口返回窗口内）',
          goto: '#/monitor/honeypot'
        });
      });
    }

    /* (b) 高危 / 蜜罐相关的告警（alerts.list 已经是"同规则 + 同来源 IP"聚合，count 是出现次数） */
    if (al && Array.isArray(al.list)) {
      al.list.forEach(function (a) {
        var sev = a.severity || 'INFO';
        if (sev !== 'CRITICAL' && sev !== 'HIGH' && !/蜜罐|爆破|扫描|注入|injection|brute/i.test(String(a.title || ''))) return;
        var kind = alertKind(a.title, a.source);
        put('al|' + kind.label + '|' + (a.srcIp || '—'), {
          kind: 'al', level: sev === 'INFO' ? kind.level : sev,
          label: kind.label, ip: a.srcIp || '—',
          count: Number(a.count) || 1, ms: parseTs(a.occurredAt || a.endTime || a.startTime),
          source: '/api/public/alerts · ' + (a.sourceLabel || a.source || '告警'),
          goto: '#/monitor/alerts'
        });
      });
    }

    /* (c) 处置审计：封禁留痕按 IP 聚合（同一 IP 反复封禁只显示一条 + 次数） */
    if (au && Array.isArray(au.blocks)) {
      au.blocks.forEach(function (b) {
        var ip = b.ip || '—';
        put('blk|' + ip, {
          kind: 'blk', level: b.unblocked ? 'LOW' : 'HIGH',
          label: '封禁 IP' + (b.durationMinutes != null ? '（' + b.durationMinutes + ' 分钟）' : '') +
                 (b.unblocked ? '・已解封' : '・生效中'),
          ip: ip, count: 1, ms: parseTs(b.createdAt),
          source: '/api/public/audit · blocks', goto: '#/monitor/audit'
        });
      });
    }

    /* (d) 处置动作：护栏拦下的【按动作合并】（原因只取出现最多的那个），真的执行了的按 动作→目标 合并 */
    if (au && Array.isArray(au.actions)) {
      au.actions.forEach(function (a) {
        var blocked = a.mode === 'BLOCKED' || a.success === false;
        var action = a.action || '动作';
        var reason = String(a.reason || '').replace(/^封禁目标\s*/, '');
        var key, g;
        if (blocked) {
          key = 'gd|' + action;
          g = {
            kind: 'gd', level: 'MEDIUM', label: '护栏拦下 ' + action, ip: '', count: 1,
            ms: parseTs(a.time), source: '/api/public/audit · actions（mode=' + (a.mode || 'BLOCKED') + '）',
            goto: '#/monitor/audit'
          };
          if (reason) {
            reasons[key] = reasons[key] || {};
            reasons[key][reason] = (reasons[key][reason] || 0) + 1;
          }
        } else {
          var label = '处置 ' + action + ' → ' + (a.target || '—');
          key = 'act|' + label;
          g = {
            kind: 'act', level: a.riskLevel || 'LOW', label: label, ip: '', count: 1,
            ms: parseTs(a.time), source: '/api/public/audit · actions',
            goto: '#/monitor/audit'
          };
        }
        put(key, g);
      });
    }

    /* 护栏条目：把出现最多的原因补进标签，给人一个"为什么被拦"的落点 */
    Object.keys(reasons).forEach(function (k) {
      var tally = reasons[k], top = '', n = 0;
      Object.keys(tally).forEach(function (r) { if (tally[r] > n) { n = tally[r]; top = r; } });
      if (top && groups[k]) groups[k].label += '（' + top + '）';
    });

    /* 排序：先看"多新"（这是动态流），同一时间点再按严重程度 —— 不把一天前的高危顶在今天的事件前面 */
    var sorted = Object.keys(groups).map(function (k) { return groups[k]; })
      .sort(function (a, b) {
        var ta = a.ms || 0, tb = b.ms || 0;
        if (ta !== tb) return tb - ta;
        var sa = SEV_RANK[a.level] == null ? 9 : SEV_RANK[a.level];
        var sb = SEV_RANK[b.level] == null ? 9 : SEV_RANK[b.level];
        return sa - sb;
      });

    /* 同类最多 2 行：避免"护栏拦下 ×4"这种虽然聚合了、但看起来还是重复的版面 */
    var perKind = {}, out = [];
    sorted.forEach(function (g) {
      if (out.length >= FEED_ROWS_MAX) return;
      perKind[g.kind] = perKind[g.kind] || 0;
      if (perKind[g.kind] >= 2) return;
      perKind[g.kind] += 1;
      out.push(g);
    });
    return out;
  }

  /** 长规则名截断：优先在词边界断开（结果里不出现 "promisc" 这种断词） */
  function shortRule(t, max) {
    var s = String(t || '').trim();
    if (s.length <= max) return s;
    var cut = s.slice(0, max);
    var sp = cut.lastIndexOf(' ');
    if (sp > max * 0.6) cut = cut.slice(0, sp);
    return cut + '…';
  }

  /** 告警原始规则串 → 中文可读类别。口令 / 用户名这类细节一律不展示（前端也不还原任何被掩码字段）。 */
  function alertKind(title, source) {
    var t = String(title || '');
    if (/蜜罐/i.test(t)) return { label: /登录|login|SSH/i.test(t) ? '蜜罐拦截 SSH 登录尝试' : '蜜罐事件', level: 'HIGH' };
    if (/爆破|暴力|brute/i.test(t)) return { label: '暴力破解尝试', level: 'HIGH' };
    if (/SQL|XSS|注入|injection/i.test(t)) return { label: '注入类攻击尝试', level: 'HIGH' };
    if (/扫描|scan/i.test(t)) return { label: '端口 / 服务扫描', level: 'MEDIUM' };
    if (String(source) === 'SURICATA' || /Suricata/i.test(t)) return { label: '网络层可疑流量', level: 'LOW' };
    /* 认不出来的规则：不硬编一个中文解释，直接把规则名（截断）摆出来，口径在来源行里写明 */
    return { label: '主机告警 · ' + shortRule(t.replace(/^[\w\s.:\-]*?:\s*/, ''), 36), level: 'LOW' };
  }

  function renderFeed(au, al, hp, parts) {
    var host = $('[data-xk-feed]');
    if (!host) return;

    var rows = feedGroups(au, al, hp);

    if (!rows.length) {
      var reason = parts.filter(function (p) { return p.err; })[0];
      host.innerHTML = '<li class="xk-feed__row"><span class="xk-dot xk-dot--off"></span>' +
        '<span class="xk-feed__text">' + (reason
          ? '取不到数据（' + esc(reason.err.status ? 'HTTP ' + reason.err.status : '网络不可达') +
            '）——这里不显示占位事件，也不编造拦截记录。'
          : '接口没有返回可展示的拦截 / 处置记录。') +
        '</span><span class="xk-feed__time">—</span></li>';
    } else {
      host.innerHTML = rows.map(function (r) {
        var sevCls = SEV_CLASS[r.level];
        return '<li class="xk-feed__row" data-xk-goto="' + esc(r.goto) + '" role="link" tabindex="0">' +
          '<span class="xk-dot' + (sevCls ? ' xk-dot--' + sevCls : '') + '" title="级别：' + esc(sevLabel(r.level)) + '"></span>' +
          '<span class="xk-feed__text">' +
            '<b class="xk-feed__ok">' + esc(r.label) + '</b>' +
            (r.ip ? '・<b class="xk-feed__ip">' + esc(r.ip) + '</b>' : '') +
            (r.count > 1 ? '・<span class="xk-feed__cnt">聚合 ' + esc(num(r.count)) + ' 次</span>' : '') +
          '</span>' +
          '<span class="xk-feed__time">' + (r.ms ? esc(relTime(new Date(r.ms))) : '—') + '</span></li>';
      }).join('');
    }

    /* 标题诚实：只有【真的有新鲜同步】并且【没有端点失败】时才写「实时」 */
    var failed = parts.filter(function (p) { return p.err; }).length;
    var newest = 0;
    parts.forEach(function (p) { if (p.res && p.res.syncedAt > newest) newest = p.res.syncedAt; });
    var live = !failed && newest > 0 && (Date.now() - newest) < LIVE_FRESH_MS;
    var titleHost = $('[data-xk-live-title]');
    if (titleHost) {
      titleHost.innerHTML = live
        ? '<span class="xk-pulse" aria-hidden="true"></span>拦截动态 · 实时'
        : '拦截动态 · 最近同步';
    }
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
     9. 监测中心 —— 一页大屏（第十一轮重做）
     --------------------------------------------------------------------------
     站主原话："系统监控要做成很高级很科技感又很有用的大屏，有动态效果，而不是拆成一个个小模块"。
     数据来源（全部公开只读端点，5 个）：
       overview  节点在线 / 告警分布（窗口口径）
       alerts    聚合后的告警流 + stats24h（24h 总量 / 逐小时桶 / 严重度）
       honeypot  蜜罐：来源 Top / 尝试口令 / 客户端指纹 / 事件时间线
       audit     处置审计：封禁留痕、summary
       health    指纹与运行信息（扁平对象，无信封）
     图表全部自绘（SVG + CSS），零第三方图表库。
     纪律：拿不到就写「未接入」；**动画只用真数据**（新条目淡入是真的换了条目，
     绝不用假脉冲冒充"在跑"）。
     ========================================================================== */
  var SCREEN_JOBS = [
    { name: 'overview', path: '/api/public/overview' },
    { name: 'alerts', path: '/api/public/alerts' },
    { name: 'honeypot', path: '/api/public/honeypot' },
    { name: 'audit', path: '/api/public/audit' },
    { name: 'health', path: '/api/health' }
  ];

  function initMonitor() {
    var load = function () {
      return Promise.all(SCREEN_JOBS.map(function (j) {
        return readApi(j.path).then(function (res) { return { name: j.name, path: j.path, res: res, err: null }; })
          .catch(function (err) {
            return {
              name: j.name, path: j.path, err: err,
              res: err.snapshot ? { data: err.snapshot.data, syncedAt: err.snapshot.syncedAt } : null
            };
          });
      })).then(function (parts) {
        renderScreen(parts);
        setSync('monitor', syncTextOf(parts));
        setSync('feed', syncTextOf(parts));
      });
    };
    startPolling(load, SCREEN_JOBS.length);
  }

  function renderScreen(parts) {
    var ov = partData(parts, 'overview');
    var al = partData(parts, 'alerts');
    var hp = partData(parts, 'honeypot');
    var au = partData(parts, 'audit');
    var hh = partData(parts, 'health');

    /* ---- ① 指标带：与主页共用同一套"数字 + 本来就有的相对量"逻辑 ---- */
    renderHeroStats(ov, au, hp, al);
    var sm = (au && au.summary) || {};
    var activeN = sm.blockActive === undefined ? null : Number(sm.blockActive);
    screenSet('active', activeN === null ? '未接入' : num(activeN));
    screenSet('activeSub', activeN === null ? '本次取不到处置审计'
      : (activeN > 0 ? '仍在封禁期内' : (sm.blockTotal !== undefined ? '封禁留痕共 ' + num(sm.blockTotal) + ' 条，均已解除' : '当前没有生效中的封禁')));

    /* ---- ② 攻击来源网段 Top（自绘 SVG 条） ---- */
    var srcHost = $('[data-xk-screen-sources]', contentEl);
    if (srcHost) {
      var srcs = (hp && Array.isArray(hp.topSources)) ? hp.topSources.slice(0, 8) : null;
      if (!srcs) {
        srcHost.innerHTML = '<p class="xk-hint">蜜罐接口本次取不到 → 未接入，不补数。</p>';
      } else if (!srcs.length) {
        srcHost.innerHTML = '<p class="xk-hint">窗口内没有来源数据。</p>';
      } else {
        srcHost.innerHTML = svgBars(srcs.map(function (s) { return { label: String(s.key || '—'), value: Number(s.count) || 0 }; }));
      }
      var sn = $('[data-xk-screen-sources-note]', contentEl);
      if (sn) {
        sn.textContent = (hp && hp.total !== undefined)
          ? '蜜罐累计事件 ' + num(hp.total) + ' 条 · 采样 ' + num(hp.sampled) + ' 条；来源计数是采样窗口内的真实计数。'
          : '来源计数来自采样窗口。';
      }
    }

    /* ---- ③ 近 24 小时攻击节奏（自绘 SVG 折线 + 面积） ---- */
    var hHost = $('[data-xk-screen-hourly]', contentEl);
    var hNote = $('[data-xk-screen-trend-note]', contentEl);
    if (hHost) {
      var s24 = al && al.stats24h;
      if (!s24 || s24.available === false) {
        hHost.innerHTML = '<p class="xk-hint">24h 聚合本次取不到（stats24h.available=false）→ 未接入。</p>';
        if (hNote) hNote.textContent = '未接入';
      } else if (!Array.isArray(s24.trend) || !s24.trend.length) {
        hHost.innerHTML = '<p class="xk-hint">服务端没有返回逐小时桶 → 本次不画图。</p>';
        if (hNote) hNote.textContent = '无逐小时桶';
      } else {
        hHost.innerHTML = svgSpark(s24.trend.map(function (p) { return { label: p.time, value: Number(p.count) || 0 }; }));
        var arr = s24.trend.map(function (p) { return Number(p.count) || 0; });
        var peak = Math.max.apply(null, arr);
        var peakAt = s24.trend[arr.indexOf(peak)];
        if (hNote) hNote.textContent = '峰值 ' + num(peak) + ' 条 @ ' + (peakAt ? peakAt.time : '—') + ' · 共 ' + arr.length + ' 个桶';
      }
    }

    /* ---- ④ 攻击事件时间轴 ---- */
    var tl = $('[data-xk-screen-timeline]', contentEl);
    if (tl) {
      var evs = (hp && Array.isArray(hp.timeline)) ? hp.timeline.slice(0, 20) : null;
      if (!evs) {
        tl.innerHTML = '<li class="xk-hint">蜜罐接口本次取不到 → 未接入，不补数。</li>';
      } else if (!evs.length) {
        tl.innerHTML = '<li class="xk-hint">窗口内没有蜜罐事件。</li>';
      } else {
        tl.innerHTML = evs.map(function (e) {
          return '<li class="xk-tl__row">' +
            '<span class="xk-tl__time">' + esc(String(e.time || '').slice(5, 16)) + '</span>' +
            '<span class="xk-tl__kind">' + esc(e.kind || '事件') + '</span>' +
            '<span class="xk-tl__detail" title="' + esc(e.detail || '') + '">' + esc(e.srcIp || '—') + '</span></li>';
        }).join('');
      }
    }

    /* ---- ⑤ 规则命中 Top（alerts.list 的 ruleName 聚合是服务端给的，直接按条数排序展示） ---- */
    var rHost = $('[data-xk-screen-rules]', contentEl);
    if (rHost) {
      var list = (al && Array.isArray(al.list)) ? al.list : null;
      if (!list) {
        rHost.innerHTML = '<p class="xk-hint">告警接口本次取不到 → 未接入。</p>';
      } else {
        var byRule = {};
        list.forEach(function (a) {
          var k = shortRule(a.ruleName || a.title || '（无规则名）', 46);
          byRule[k] = (byRule[k] || 0) + (Number(a.count) || 1);
        });
        var rows = Object.keys(byRule).map(function (k) { return { label: k, count: byRule[k] }; })
          .sort(function (x, y) { return y.count - x.count; }).slice(0, 8);
        rHost.innerHTML = distList(rows, true);
      }
    }

    /* ---- ⑥ 严重度分布（24h 桶，服务端已给） ---- */
    var sevHost = $('[data-xk-screen-sev]', contentEl);
    if (sevHost) {
      var s24b = al && al.stats24h;
      var bucket = (s24b && s24b.available !== false && s24b.bySeverity) ? s24b.bySeverity
        : ((ov && ov.alerts && ov.alerts.bySeverity) ? ov.alerts.bySeverity.reduce(function (acc, x) { acc[x.key] = x.count; return acc; }, {}) : null);
      if (!bucket) {
        sevHost.innerHTML = '<p class="xk-hint">严重度分布本次取不到 → 未接入。</p>';
      } else {
        var order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
        var names = { CRITICAL: '严重', HIGH: '高危', MEDIUM: '中危', LOW: '低危', INFO: '提示' };
        var srows = order.map(function (k) { return { label: names[k], count: Number(bucket[k]) || 0, sev: k }; });
        sevHost.innerHTML = srows.map(function (r) {
          var max = Math.max.apply(null, srows.map(function (x) { return x.count; })) || 1;
          return '<div class="xk-dist__row">' +
            '<span class="xk-dist__label"><span class="xk-dot xk-dot--' + SEV_CLASS[r.sev] + '" aria-hidden="true"></span> ' + esc(r.label) + '</span>' +
            '<span class="xk-dist__track"><span class="xk-dist__fill" style="width:' + Math.round(r.count / max * 100) + '%"></span></span>' +
            '<span class="xk-dist__count">' + esc(num(r.count)) + '</span></div>';
        }).join('');
      }
    }

    /* ---- ⑦ 采集通道：三态灯（在线 / 降级 / 离线） ---- */
    var nodeHost = $('[data-xk-screen-nodes]', contentEl);
    if (nodeHost) {
      var nodes = (ov && Array.isArray(ov.nodes)) ? ov.nodes : null;
      if (!nodes) {
        nodeHost.innerHTML = '<li class="xk-hint">总览接口本次取不到 → 未接入。</li>';
      } else {
        nodeHost.innerHTML = nodes.map(function (n) {
          var on = n.online === true;
          return '<li><span class="xk-dot xk-dot--' + (on ? 'ok' : 'off') + '" aria-hidden="true"></span>' +
            '<span>' + esc(n.label || n.id || '节点') + '</span>' +
            '<b>' + (on ? '在线' : '离线 / 降级') + '</b>' +
            '<small class="xk-hint">' + esc(n.probe || '') + '</small></li>';
        }).join('');
      }
      var srcNote = $('[data-xk-screen-source-note]', contentEl);
      if (srcNote) {
        var ds = ov && ov.dataSource;
        srcNote.textContent = ds
          ? ('数据源：' + (ds.wazuhMode || '—') + ' · 降级=' + (ds.degraded === true ? '是' : '否') + (ds.note ? ' · ' + ds.note : ''))
          : '数据源状态本次取不到。';
        if (hh && hh.status) srcNote.textContent += ' · 服务状态=' + hh.status;
      }
    }

    /* ---- ⑧ 拦截动态：与主页复用同一套聚合 ---- */
    renderFeed(au, al, hp, parts);
  }

  function screenSet(key, text) {
    var n = document.querySelector('[data-xk-screen="' + key + '"]');
    if (n) n.textContent = text;
  }

  /** 自绘横向条形图（SVG）：来源网段 Top —— 不用任何图表库 */
  function svgBars(rows) {
    var max = Math.max.apply(null, rows.map(function (r) { return r.value; })) || 1;
    var W = 560, rowH = 26, gap = 6, padL = 6, padR = 78;
    var H = rows.length * (rowH + gap);
    var barMax = W - padL - padR;
    var svg = ['<svg class="xk-svg" viewBox="0 0 ' + W + ' ' + H + '" width="100%" height="' + H + '" role="img" aria-label="攻击来源网段 Top ' + rows.length + ' 条">'];
    rows.forEach(function (r, i) {
      var y = i * (rowH + gap);
      var w = Math.max(2, Math.round(r.value / max * barMax));
      svg.push('<rect x="0" y="' + y + '" width="' + W + '" height="' + rowH + '" rx="6" class="xk-svg__track"></rect>');
      svg.push('<rect x="' + padL + '" y="' + y + '" width="' + w + '" height="' + rowH + '" rx="6" class="xk-svg__bar" style="--xk-delay:' + (i * 70) + 'ms"></rect>');
      svg.push('<text x="' + (padL + 10) + '" y="' + (y + 17) + '" class="xk-svg__label">' + esc(r.label) + '</text>');
      svg.push('<text x="' + (W - 6) + '" y="' + (y + 17) + '" text-anchor="end" class="xk-svg__value">' + esc(num(r.value)) + '</text>');
    });
    svg.push('</svg>');
    return svg.join('');
  }

  /** 自绘折线 + 面积（SVG）：近 24h 攻击节奏 */
  function svgSpark(points) {
    var W = 560, H = 132, padB = 18, padT = 10;
    var vals = points.map(function (p) { return p.value; });
    var max = Math.max.apply(null, vals) || 1;
    var step = W / Math.max(1, points.length - 1);
    var yOf = function (v) { return padT + (H - padB - padT) * (1 - v / max); };
    var line = points.map(function (p, i) { return (i ? 'L' : 'M') + (i * step).toFixed(1) + ' ' + yOf(p.value).toFixed(1); }).join(' ');
    var area = line + ' L' + ((points.length - 1) * step).toFixed(1) + ' ' + (H - padB) + ' L0 ' + (H - padB) + ' Z';
    var svg = ['<svg class="xk-svg xk-svg--spark" viewBox="0 0 ' + W + ' ' + H + '" width="100%" height="' + H + '" role="img" aria-label="近 24 小时逐小时攻击计数折线">'];
    svg.push('<path d="' + area + '" class="xk-svg__area"></path>');
    svg.push('<path d="' + line + '" class="xk-svg__line"></path>');
    points.forEach(function (p, i) {
      if (i % 3 === 0) {
        svg.push('<text x="' + (i * step).toFixed(1) + '" y="' + (H - 4) + '" text-anchor="middle" class="xk-svg__x">' + esc(String(p.label || '').slice(0, 5)) + '</text>');
      }
      svg.push('<circle cx="' + (i * step).toFixed(1) + '" cy="' + yOf(p.value).toFixed(1) + '" r="2.5" class="xk-svg__dot"><title>' + esc((p.label || '') + '：' + num(p.value)) + '</title></circle>');
    });
    svg.push('</svg>');
    return svg.join('');
  }

  function distList(arr, wide) {
    if (!arr || !arr.length) return '<p class="xk-hint">无数据。</p>';
    var max = Math.max.apply(null, arr.map(function (x) { return x.count; }).concat([1]));
    return arr.slice(0, 10).map(function (x) { return distRow(x.key, x.count, max, ''); }).join('');
  }

  /* ==========================================================================
     10. 攻防靶场：两张卡都真的打到 /api/playground/check
     ★T27 收尾（2026-10-15）：靶场页已删 ⇒ 下面这段 initRange() 已**没有路由入口**
       （VIEW_TPL / routeFromPath / 渲染分发里的 range 分支都已摘掉）。函数体保留不删，
       是为了不在"删页面"这一批里顺手动 playground 取数逻辑；它随旧 SPA 一起下线。
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
        setStatus('链路不可达', 'xk-tag--off');
        var msg = '<p class="xk-notice xk-notice--bad">检测端点 <code>POST /api/playground/check</code> 当前不可用（' +
          esc(err.status ? 'HTTP ' + err.status : '网络不可达') + '）。按纪律这里不放任何模拟结论 —— 按钮已停用。</p>';
        $$('[data-xk-pg-result]', contentEl).forEach(function (r) { r.hidden = false; r.innerHTML = msg; });
        $$('[data-xk-pg-run], [data-xk-pg-preset]', contentEl).forEach(function (b) { b.disabled = true; });
      });
    }

    function run(text, resultEl) {
      if (available === false) return;
      resultEl.hidden = false;
      resultEl.innerHTML = '<p class="xk-hint"><span class="xk-pulse" aria-hidden="true"></span>正在请求后端检测链路…</p>';
      postPlayground(text).then(function (body) {
        renderCheckResult(resultEl, body, false);
      }).catch(function (err) {
        resultEl.innerHTML = '<p class="xk-notice xk-notice--bad">检测失败（' +
          esc(err.status ? 'HTTP ' + err.status : '网络不可达') + '）。这不代表输入安全，只代表这次没测成。</p>';
      });
    }

    var input = $('#xk-pg-input', contentEl);
    var pgResult = $('[data-xk-pg-result]', contentEl);
    if (!input || !pgResult) return;

    $$('[data-xk-pg-run]', contentEl).forEach(function (b) {
      b.addEventListener('click', function () { run(input.value, pgResult); });
    });
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') run(input.value, pgResult); });
    /* 一键样本（第十一轮 E 项）：点一下就把样本填进输入框并立刻真跑一次，
       不需要访客自己打字 —— 面试官"拿起来就能试"是这一栏唯一的目标。 */
    $$('[data-xk-pg-preset]', contentEl).forEach(function (b) {
      b.addEventListener('click', function () {
        input.value = b.getAttribute('data-xk-pg-preset');
        run(input.value, pgResult);
      });
    });

    availabilityProbe();
  }

  /* 站主第十轮 ⑤：结果展示重排（后端已保证只检测、不执行，也不再回传正则原文）
     ---------------------------------------------------------------------------
     读者要三眼看清三件事：① 有哪些组件、各自"适用 / 不适用"；② 命中还是未命中、severity 是几；
     ③ 未命中时为什么仍然不能说"安全"。
     所以结果区结构固定为：
       [总览条]  每个组件一格：severity 色点 + 组件名 + 适用/不适用 + 命中/未命中
       [未命中 ≠ 无害] 后端 coverageWarning / uncovered 原样展示（不缩写、不折叠）
       [逐组件卡] 结论（detail / 证据 / 命中规则）默认可见；action + limit 收进「动作与局限」折叠
     severity 色点：严重/高危=红、中危=橙、低危=灰蓝、未命中=绿、不适用=虚线空心。 */
  function sevDotClass(c) {
    if (c.applicable === false) return 'is-na';
    if (!c.hit) return 'is-miss';
    var s = c.severity;
    if (s === 'CRITICAL') return 'is-crit';
    if (s === 'HIGH') return 'is-high';
    if (s === 'MEDIUM') return 'is-med';
    return 'is-low';
  }
  function sevTagText(c) {
    if (c.applicable === false) return '不适用';
    if (!c.hit) return '未命中';
    return '命中 ' + (c.severity === 'NONE' ? '' : (c.severity || '')) ;
  }
  function sevTagClass(c) {
    if (c.applicable === false) return 'xk-sev is-info';
    if (!c.hit) return 'xk-sev is-low';
    return 'xk-sev ' + (c.severity === 'CRITICAL' || c.severity === 'HIGH' ? 'is-high' : 'is-medium');
  }
  function shortComp(name) {
    var s = String(name || '').replace(/Guard$|Scanner$|Util$/, '');
    return s || name;
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

    /* ---- 总览条：三组件各自结论一眼可见 ---- */
    html += '<ul class="xk-verdicts" data-xk-pg-summary>' + checks.map(function (c) {
      var hit = c.applicable !== false && c.hit;
      return '<li class="xk-verd' + (hit ? ' is-hit' : (c.applicable === false ? ' is-na' : '')) + '">' +
        '<span class="xk-verd__dot ' + sevDotClass(c) + '" aria-hidden="true"></span>' +
        '<span class="xk-verd__name" title="' + esc(c.name + ' · ' + (c.component || '')) + '">' + esc(shortComp(c.name)) + '</span>' +
        '<span class="xk-verd__st"><span class="' + sevTagClass(c) + '">' + esc(sevTagText(c)) + '</span></span>' +
        '</li>';
    }).join('') + '</ul>';

    /* ---- 「未命中 ≠ 无害」：后端原文照登，永远是可见段落（不折叠、不缩成小字） ---- */
    if (d.coverageWarning || d.uncovered) {
      html += '<div class="xk-noharm" data-xk-pg-noharm><span class="xk-noharm__ico" aria-hidden="true">!</span><div>' +
        '<b>未命中 ≠ 无害。</b> ' + (d.coverageWarning ? esc(d.coverageWarning) : '') +
        (d.uncovered ? '<p style="margin-top:6px"><b>' + esc(d.uncoveredTitle || '关于「未命中」的说明') + '</b>：' + esc(d.uncovered) + '</p>' : '') +
        '</div></div>';
    }

    /* ---- 逐组件：结论可见，动作与局限折叠 ---- */
    html += checks.map(function (c) {
      var mid = 'xk-more-' + String(c.id || c.component || 'c').replace(/[^\w-]/g, '');
      return '<div class="xk-check' + (c.applicable === false ? ' is-na' : '') + '">' +
        '<div class="xk-check__hd">' +
          '<span class="xk-verd__dot ' + sevDotClass(c) + '" aria-hidden="true"></span>' +
          '<span class="' + sevTagClass(c) + '">' + esc(sevTagText(c)) + '</span>' +
          '<span class="xk-check__name">' + esc(c.name) + '</span>' +
          '<span class="xk-check__where">' + esc(c.where || '') + ' · <code>' + esc(c.component || '') + '</code></span>' +
        '</div>' +
        '<div class="xk-check__body">' +
          '<p>' + esc(c.detail || '') + '</p>' +
          (c.evidence && c.evidence.length ? '<p class="xk-hint">证据：<code>' + esc(c.evidence.join(' / ')) + '</code></p>' : '') +
          (c.rules && c.rules.length ? '<p class="xk-hint">命中规则：<code>' + esc(rulesText(c.rules)) + '</code></p>' : '') +
          '<details class="xk-check__more" id="' + mid + '">' +
            '<summary>动作与局限</summary>' +
            '<ul class="xk-meta xk-check__kv">' +
              '<li><span>动作</span><b>' + esc(c.action || '—') + '</b></li>' +
              '<li><span>局限</span><b>' + esc(c.limit || '—') + '</b></li>' +
            '</ul>' +
          '</details>' +
        '</div></div>';
    }).join('');

    if (d.note) {
      html += '<p class="xk-note">' + esc(d.note) + '</p>';
    }
    host.innerHTML = html;
    /* 新插入的折叠件也要有 aria-expanded / aria-controls */
    syncDisclosures(host);
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

  /** 这一趟要不要顺便向服务端要一句日语语音（`speakJa`）。
   *  【为什么默认不要】多要一句日语改写 = 多一次公开池模型调用（额度 30/天）。
   *  静音的访客根本不会听，那一次调用就是纯浪费 —— 只有"声音真的开着"才要。
   *  声音状态由 kurisu-player.js 的 🔊 挂在 window.__xkSpeakJa 上（两支脚本互不依赖文件顺序）。 */
  function speakJaWanted() {
    try {
      /* ★2026-10-19 站主：默认关是硬口径 —— 没有开关/读不到状态（全站 88 个页面根本没加载头像卡）
         一律按"关"算，不再是 `on === false` 才拦。以前在那些页面上她会自己开口。 */
      if (!(window.__xkSound && window.__xkSound.on === true)) { return false; }
      return !!(window.__xkSpeakJa && window.__xkSpeakJa.on);
    } catch (e) { return false; }
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
      body: JSON.stringify({ question: String(question).slice(0, ASK_MAX_CHARS), speakJa: speakJaWanted() })
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

  /* ==========================================================================
     10b. AI 安全 —— 真·对话界面（第十一轮重写）
     --------------------------------------------------------------------------
     站主原话："AI 问答应该像豆包/对话界面"。所以这里不是"表单 + 结果块"，而是一条对话：
       · 用户气泡在右、AI 卡片在左；输入区在底部，Enter 发送 / Shift+Enter 换行；
       · AI 消息里渲染结论正文 + 引用卡片（<details> 展开看标题/片段/可信度/来源性质/相关度）；
       · 顶部状态徽标把 state 直接可视化（model / model-failed / input-insufficient / rule-based …）；
       · 预设问题 chips 一键发送（含一条演示"公开面为什么不取证"）。
     红线（站主 + 规格）：
       · **不许 SSE / WebSocket** —— 公开面只有一次性 POST /api/public/ask；
         正文用前端渐进揭示（打字机）呈现，并在界面上【如实标注"回答非流式传输"】，不假装真流式；
       · 模型没生成就写原因，不补"听起来像答案"的话；
       · 引用里出现的 web-01 / auth.log 是知识库文档里的教学示例，不当内部真实数据宣传。
     ========================================================================== */
  var CHAT_STATE_LABEL = {
    'model': ['模型研判', 'is-model', 'on'],
    'rule-based': ['规则解析', 'is-rule', 'warn'],
    'input-insufficient': ['依据不足，不做定性', 'is-warn', 'warn'],
    'no-retrieval': ['未检索到依据，不给结论', 'is-warn', 'warn'],
    'retrieval-failed': ['检索不可用，未生成', 'is-bad', 'bad'],
    'model-failed': ['模型不可用，未生成', 'is-bad', 'bad'],
    'injection-blocked': ['命中提示注入护栏', 'is-warn', 'warn']
  };

  var CHAT = { bound: false, asking: false, typeTimer: null };

  function chatLog() { return $('[data-xk-chat-log]', contentEl); }

  function chatScroll() {
    var log = chatLog();
    if (log) log.scrollTop = log.scrollHeight;
  }

  function chatPush(kind, html, metaOverride) {
    var log = chatLog();
    if (!log) return null;
    var li = document.createElement('li');
    li.className = 'xk-msg xk-msg--' + kind;
    li.innerHTML = '<div class="xk-msg__bubble">' + html + '</div>' +
      '<div class="xk-msg__meta"><span class="xk-msg__who">' +
      esc(metaOverride || (kind === 'user' ? '你' : 'AI 安全')) + '</span></div>';
    log.appendChild(li);
    chatScroll();
    return li;
  }

  function chatTypingPush() {
    return chatPush('ai', '<span class="xk-typing" aria-label="正在生成"><i></i><i></i><i></i></span>', 'AI 安全 · 生成中');
  }

  /** 状态徽标：把"到底是谁给的结论"直接摆在聊天窗口上方（项目最值钱的那部分） */
  function chatBadge(state, label) {
    var host = $('[data-xk-chat-badge]', contentEl);
    if (!host) return;
    var conf = CHAT_STATE_LABEL[state];
    var text = label || (conf ? conf[0] : (state ? state + '（未识别状态）' : '等待提问'));
    var dot = state === 'model' ? 'ok' : (conf && conf[2] === 'bad' ? 'off' : (conf ? 'medium' : 'off'));
    host.className = 'xk-chat__badge is-' + (conf ? conf[2] : 'off');
    host.innerHTML = '<span class="xk-dot xk-dot--' + dot + '" aria-hidden="true"></span>' + esc(text) +
      (state ? '<code>' + esc(state) + '</code>' : '');
  }

  /** 引用卡片：标题 + 来源性质 + 可信度 + 相关度，片段可展开（默认收起，避免淹没正文） */
  function chatCite(c, i) {
    var bits = [];
    if (c.sourceTypeLabel) bits.push(c.sourceTypeLabel);
    if (c.trustLevelLabel) bits.push(c.trustLevelLabel);
    if (c.score !== undefined && c.score !== null && !isNaN(Number(c.score))) {
      bits.push('相关度 ' + (Math.round(Number(c.score) * 100) / 100));
    }
    return '<li class="xk-cite">' +
      '<b class="xk-cite__title">[' + (i + 1) + '] ' + esc(c.title || '（无标题）') + '</b>' +
      (bits.length ? '<span class="xk-hint">' + esc(bits.join(' · ')) + '</span>' : '') +
      (c.snippet ? '<details class="xk-caliber xk-caliber--inline"><summary>看片段</summary>' +
        '<p class="xk-cite__snip">' + esc(c.snippet) + '</p></details>' : '') +
      '</li>';
  }

  /**
   * 渐进揭示：把【已经拿到的完整正文】逐字显示出来。
   * 诚实说明：这不是流式传输 —— 公开面只有一次性 POST（规格明确不许 SSE/WebSocket），
   * 页面上也如实标注了这一点。这里只是让"已经到手的完整答案"读起来不像一次硬刷新。
   * 做法：先按 mdLite 渲染成 HTML，再按"标签不可分割"的粒度渐进写入 ——
   * 展示的始终是真内容的子集（不是假动画），也不会因为截断标签而破坏 DOM。
   */
  function chatReveal(host, text) {
    var target = host.querySelector('[data-xk-reveal]');
    if (!target) return;
    var html = mdLite(text);
    var tokens = html.match(/<[^>]+>|[^<]/g) || [];
    var i = 0;
    target.innerHTML = '';
    if (prefersReducedMotion()) { target.innerHTML = html; chatScroll(); return; }
    var step = Math.max(1, Math.round(tokens.length / 120));
    clearInterval(CHAT.typeTimer);
    CHAT.typeTimer = setInterval(function () {
      if (!document.body.contains(target)) { clearInterval(CHAT.typeTimer); return; }
      var buf = '', n = 0;
      while (i < tokens.length && n < step) {
        buf += tokens[i];
        if (tokens[i].charAt(0) !== '<') n++;
        i++;
      }
      target.innerHTML += buf;
      chatScroll();
      if (i >= tokens.length) { clearInterval(CHAT.typeTimer); target.innerHTML = html; chatScroll(); }
    }, 16);
  }

  function chatRenderAnswer(li, d, elapsedMs) {
    var state = d.state || '';
    var conf = CHAT_STATE_LABEL[state];
    var head = '<div class="xk-msg__verdict">' +
      '<span class="xk-state ' + (conf ? conf[1] : 'is-warn') + '">' + esc(d.stateLabel || (conf ? conf[0] : (state || '未识别状态'))) + '</span>' +
      '<b>' + (d.generated === true ? '模型已生成结论' : '未生成结论（generated=false）') + '</b>' +
      '<span class="xk-hint">' + esc((Math.round(elapsedMs / 100) / 10)) + 's · 引用 ' +
      esc((d.citations || []).length) + ' 条</span></div>';

    var body = '';
    if (d.injection && d.injection.blocked) {
      body += '<p class="xk-notice xk-notice--warn">输入命中<b>提示注入护栏</b>（' +
        esc(d.injection.hitCount || 0) + ' 条规则）。下面是被当作"不可信数据"处理之后的结果。</p>';
    }
    if (d.failureReason) {
      body += '<p class="xk-notice xk-notice--warn"><b>服务端说明：</b>' + esc(d.failureReason) + '</p>';
    }
    if (d.answer) {
      body += '<div class="xk-md xk-answer"><span data-xk-reveal></span></div>';
    } else if (!d.failureReason) {
      body += '<p class="xk-hint">这次没有返回答案正文（<code>state=' + esc(state || '—') + '</code>）。</p>';
    }

    var cites = d.citations || [];
    body += cites.length
      ? '<details class="xk-caliber xk-caliber--cites"><summary>引用 ' + cites.length + ' 条（点开看片段）</summary>' +
        '<ul class="xk-cites">' + cites.map(chatCite).join('') + '</ul></details>'
      : '<p class="xk-hint">这次没有引用片段 —— 没有依据就直接说没有，不用"相关推荐"凑数。</p>';

    if (d.clientIpMasked || (d.quota && d.quota.pool)) {
      body += '<p class="xk-note">来源 IP（后端已掩码）：<code>' + esc(d.clientIpMasked || '—') + '</code>' +
        (d.quota && d.quota.pool ? ' · 额度池 <code>' + esc(d.quota.pool) + '</code>（已用 ' +
          esc(num(d.quota.used)) + '，上限 ' + esc(num(d.quota.limit)) + '）' : '') + '</p>';
    }

    li.querySelector('.xk-msg__bubble').innerHTML = head + body;
    if (d.answer) chatReveal(li, d.answer);
    chatScroll();
  }

  function initAi() {
    var log = chatLog();
    var askInput = $('#xk-ask-input', contentEl);
    var askBtn = $('[data-xk-ask-run]', contentEl);
    if (!log || !askInput) return;

    setSync('ai', '只读公开端点 · 无 SSE');

    /* 输入框自适应高度（最多 5 行），Enter 发送 / Shift+Enter 换行 */
    function autoGrow() {
      askInput.style.height = 'auto';
      askInput.style.height = Math.min(120, askInput.scrollHeight) + 'px';
    }
    askInput.addEventListener('input', autoGrow);
    askInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        runAsk();
      }
    });
    if (askBtn) askBtn.addEventListener('click', runAsk);
    $$('[data-xk-ask-preset]', contentEl).forEach(function (b) {
      b.addEventListener('click', function () {
        askInput.value = b.getAttribute('data-xk-ask-preset') || '';
        autoGrow();
        runAsk();
      });
    });

    function setAskState(text) {
      var n = $('[data-xk-ask-state]', contentEl);
      if (n) n.textContent = text;
    }

    function countdown429(li, msg, seconds) {
      var left = Math.max(1, Number(seconds) || 0);
      clearInterval(li.__cd);
      function paint() {
        if (!document.body.contains(li)) { clearInterval(li.__cd); return; }
        var b = li.querySelector('.xk-msg__bubble');
        if (left <= 0) {
          if (b) b.innerHTML = '<p class="xk-notice xk-notice--warn">' + esc(msg) + '<br>等待结束，可以重新提问了。</p>';
          clearInterval(li.__cd); return;
        }
        if (b) b.innerHTML = '<p class="xk-notice xk-notice--warn">' + esc(msg) + '<br>请稍后再试 <b>' + left + '</b> 秒。</p>';
        left -= 1;
      }
      paint();
      li.__cd = setInterval(paint, 1000);
    }

    function setQuota(d) {
      var q = $('[data-xk-ask-quota]', contentEl);
      if (!q) return;
      q.textContent = (d && d.quota) ? '本分钟额度：剩余 ' + num(d.quota.remaining) + '/' + num(d.quota.limit) : '额度：未返回';
      q.className = 'xk-tag ' + (d && d.quota && Number(d.quota.remaining) <= 0 ? 'xk-tag--bad' : '');
    }

    function runAsk() {
      var q = String(askInput.value || '').trim();
      if (!q) { toast('先写一个问题'); askInput.focus(); return; }
      if (CHAT.asking) return;              // 同一来源只允许 1 个在飞：前端也不重复发
      CHAT.asking = true;
      if (askBtn) askBtn.disabled = true;
      chatPush('user', '<p>' + esc(q) + '</p>', '你');
      askInput.value = '';
      autoGrow();
      var pending = chatTypingPush();
      setAskState('等待中（最多 20 秒）…');
      chatBadge('', '生成中…');
      var t0 = Date.now();
      askApi(q).then(function (r) {
        var body = r.body;
        if (r.status === 429) {
          var wait = parseInt(r.retryAfter || (body && body.retryAfter) || 0, 10) || 0;
          countdown429(pending, (body && body.message) || '请求被限流。', wait || 60);
          setAskState('被限流（HTTP 429）。');
          chatBadge('', '被限流');
          return;
        }
        if (!r.ok || !body || body.data === undefined) {
          pending.querySelector('.xk-msg__bubble').innerHTML =
            '<p class="xk-notice xk-notice--bad">接口返回 HTTP ' + esc(r.status) + '，没有可用数据。' +
            (body && body.message ? '后端说明：' + esc(body.message) : '') + ' 这里不显示任何替代答案。</p>';
          setAskState('失败（HTTP ' + r.status + '）。');
          chatBadge('', '请求失败');
          return;
        }
        var d = body.data || {};
        chatRenderAnswer(pending, d, Date.now() - t0);
        chatBadge(d.state || '', null);
        setQuota(d);
        setAskState('上次提问 ' + clockOf(Date.now()) + ' · HTTP ' + r.status +
          (r.rlLimit ? ' · 服务端余额 ' + (r.rlRemaining === null ? '—' : r.rlRemaining) + '/' + r.rlLimit : ''));
      }).catch(function (err) {
        if (err && err.timeout) {
          pending.querySelector('.xk-msg__bubble').innerHTML =
            '<p class="xk-notice xk-notice--warn">等了 20 秒还没返回，这次请求已放弃。后端可能正在排队、或模型这一轮很慢 ——' +
            ' 这里不显示任何推测的答案，过一会儿可以重试。</p>';
          setAskState('超时：等待 20 秒无响应。');
          chatBadge('', '超时');
        } else {
          pending.querySelector('.xk-msg__bubble').innerHTML =
            '<p class="xk-notice xk-notice--bad">提问失败（' + esc(err && err.status ? 'HTTP ' + err.status : '网络不可达或跨域被拒') +
            '）。没有拿到答案，也没有替代结论。</p>';
          setAskState('请求失败。');
          chatBadge('', '请求失败');
        }
      }).then(function () {
        CHAT.asking = false;
        if (askBtn) askBtn.disabled = false;
      });
    }
  }



  /* ==========================================================================
     11. 关于（正文由 Hugo 渲染）+ 站主第九轮 ⑤：
         主页不再出现技术免责 → 「数据来源 / 口径 / 免责」整块搬到这里，
         并把公开端点做一次【一次性探测】（不轮询、不缓存），如实标出可用/未上线。
     ========================================================================== */
  var ABOUT_ENDPOINTS = [
    ['/api/public/overview', '总览（节点 / 告警分布）'],
    ['/api/public/alerts', '实时告警（按规则 + IP 聚合）'],
    ['/api/public/honeypot', '蜜罐战报'],
    ['/api/public/audit', '处置审计'],
    ['/api/public/latest', '最新聚合（窗口口径，2026-10-13 上线）'],
    ['/api/public/kb', '公开知识库检索（白名单目录）'],
    ['/api/health', '系统指纹（扁平对象，无信封）']
  ];

  function initAbout() {
    $$('[data-xk-api-base]').forEach(function (n) { n.textContent = API.replace(/^https?:\/\//, ''); });

    var host = $('[data-xk-endpoints]', contentEl);
    if (!host) return;

    host.innerHTML = ABOUT_ENDPOINTS.map(function (e) {
      return '<li data-xk-ep="' + esc(e[0]) + '">' +
        '<span class="xk-ep__k"><span class="xk-mono">' + esc(e[0]) + '</span><small>' + esc(e[1]) + '</small></span>' +
        '<b class="xk-ep__st">探测中…</b></li>';
    }).join('');

    var done = 0, okCount = 0, bad = [];
    function settle(path, text, cls) {
      var li = $('[data-xk-ep="' + path + '"]', host);
      if (li) {
        var v = $('.xk-ep__st', li);
        if (v) { v.textContent = text; v.className = 'xk-ep__st ' + (cls || ''); }
      }
      done += 1;
      if (cls === 'is-ok') okCount += 1; else bad.push(path.replace('/api/public/', '').replace('/api/', ''));
      if (done === ABOUT_ENDPOINTS.length) {
        setSync('about', okCount + '/' + ABOUT_ENDPOINTS.length + ' 个端点可用' +
          (bad.length ? ' · 未上线 / 不可达：' + bad.join('、') : '') +
          ' · 探测于 ' + clockOf(Date.now()));
      }
    }

    /* 一次性探测：故意不带 If-None-Match、不写进 localStorage 快照 —— 这一页要的是"现在的状态"。
       并发度限死 2：服务端有公网并发闸（X-Public-Concurrency），6 个并发探测会被排队，
       界面上就会出现一直"探测中…"的假等待；小池子慢一点，但每一项都会落到真实结果。 */
    var queue = ABOUT_ENDPOINTS.slice(), running = 0, MAXC = 2;
    function pump() {
      while (running < MAXC && queue.length) {
        (function (e) {
          running += 1;
          fetch(API + e[0], { method: 'GET', mode: 'cors', credentials: 'omit', cache: 'no-store' })
            .then(function (r) { settle(e[0], 'HTTP ' + r.status + (r.ok ? ' · 可用' : ' · 未上线'), r.ok ? 'is-ok' : 'is-bad'); })
            .catch(function () { settle(e[0], '不可达 / 未接入', 'is-bad'); })
            .then(function () { running -= 1; setTimeout(pump, 150); });
        })(queue.shift());
      }
    }
    pump();
  }

  /* ==========================================================================
     12. 搜索（Ctrl+K，只搜笔记）
     ========================================================================== */
  var searchState = { open: false, items: [], cursor: 0 };
  /* 首屏可玩（英雄区「试着攻击我」）的运行态：用 document 级委托，视图换来换去也只绑一次 */
  var heroPlay = { running: false, bound: false };

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

  /**
   * 搜索结果渲染（第十一轮 ③）：命中高亮 + 分组 + 键盘上下选择。
   * 高亮做法：把 query 转成安全的正则（转义元字符），只对【已经 esc() 过的文本】做包裹，
   * 所以不存在把用户输入当 HTML 注入的路径（esc 在前，包 <mark> 在后）。
   */
  function hi(text, q) {
    var s = esc(text == null ? '' : String(text));
    if (!q) return s;
    var safe = String(q).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    try { return s.replace(new RegExp('(' + safe + ')', 'gi'), '<mark class="xk-mark">$1</mark>'); }
    catch (e) { return s; }
  }

  function searchBucket(n, q) {
    var qq = q.toLowerCase();
    if (String(n.title || '').toLowerCase().indexOf(qq) >= 0) return '标题命中';
    if (((n.categories || []).join(' ') + ' ' + (n.tags || []).join(' ')).toLowerCase().indexOf(qq) >= 0) return '分类 / 标签命中';
    return '正文命中';
  }

  function renderSearch(q) {
    var list = $('#xk-search-list');
    var query = String(q || '').trim();
    var lc = query.toLowerCase();
    var items = searchState.items;
    if (query) {
      items = items.filter(function (n) {
        var hay = [n.title, (n.categories || []).join(' '), (n.tags || []).join(' '), n.summary, n.text].join(' ').toLowerCase();
        return hay.indexOf(lc) >= 0;
      });
    }
    if (!items.length) {
      list.innerHTML = '<li class="xk-modal__empty">没有匹配的笔记。</li>';
      searchState.filtered = [];
      return;
    }
    searchState.filtered = items;
    searchState.cursor = 0;

    /* 分组：标题命中 → 分类/标签命中 → 正文命中（组内保持仓库里的时间倒序） */
    var groups = ['标题命中', '分类 / 标签命中', '正文命中'];
    var html = '', flat = 0;
    var shown = items.slice(0, 20);
    groups.forEach(function (g) {
      var inGroup = shown.filter(function (n) { return searchBucket(n, query || '') === g; });
      if (!inGroup.length) return;
      html += '<li class="xk-modal__group" aria-hidden="true">' + esc(g) + '</li>';
      inGroup.forEach(function (n) {
        var idx = flat++;
        html += '<li class="xk-modal__item' + (idx === 0 ? ' is-on' : '') + '" data-xk-idx="' + idx + '" data-xk-slug="' + esc(n.slug) + '" role="option">' +
          '<b>' + hi(n.title, query) + '</b>' +
          '<span>' + esc(n.date + ' · ' + (n.categories || []).join(' / ')) + ' · ' + hi(n.summary, query) + '</span></li>';
      });
    });
    list.innerHTML = html;
    // 分组后 Flat 顺序与 items 顺序一致，键盘移动仍然按 DOM 顺序走
    searchState.filtered = shown;
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
  //      站主第十轮 ④：把「看起来能点」的东西真正做成键盘可达 ——
  //      拦截动态条目（[data-xk-goto]，role=link）、告警流下钻行（.xk-stream__hd，role=button）
  //      都能用 Enter / 空格触发，和鼠标点击走同一条通路（直接派发 click，不复制一份逻辑）。
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      searchState.open ? closeSearch() : openSearch();
      return;
    }
    /* 第十一轮 ③："/" 也能聚焦搜索（很多技术读者习惯 vim/文档站的这个键位）。
       只在没有输入焦点、也没有打开浮层时接管，避免把正文里的斜杠吃掉。 */
    if (!searchState.open && e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
      var ae = document.activeElement;
      var typing = ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.isContentEditable);
      if (!typing) { e.preventDefault(); openSearch(); return; }
    }
    if (!searchState.open && (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar')) {
      var el = e.target;
      if (el && el.getAttribute) {
        var act = el.hasAttribute && el.hasAttribute('data-xk-goto') ? el
                : (el.classList && el.classList.contains('xk-stream__hd') ? el : null);
        if (act) { e.preventDefault(); act.click(); return; }
      }
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
     14. 首屏可玩：Hero 里的「试着攻击我」（第十一轮 ③）
     --------------------------------------------------------------------------
     站主原话："不是功能没做，是做得不够好不够出色"——最值钱的能力（真会被拦下来的检测链路）
     原来埋在"攻防靶场"二级页，首屏只给了一堆不能点的数字。现在 Hero 直接可玩：
     同一路径 POST /api/playground/check，结果用与靶场一致的 renderCheckResult 渲染
     （三组件判定 + severity 色点 + "未命中 ≠ 无害"常显）。
     红线：只做检测、不执行；前端不回显任何内部标记名或正则原文（后端已收口，这里也不自己拼）。
     ========================================================================== */
  function heroPlayRun(text) {
    var form = $('[data-xk-play="hero"]', contentEl);
    if (!form) return;
    var input = $('[data-xk-play-input]', form);
    var result = $('[data-xk-play-result]', form);
    if (!input || !result) return;
    var v = String(text == null ? input.value : text);
    if (!v.trim()) { toast('先输入一段内容再检测'); input.focus(); return; }
    if (heroPlay.running) return;
    heroPlay.running = true;
    result.hidden = false;
    result.innerHTML = '<p class="xk-hint"><span class="xk-pulse" aria-hidden="true"></span>正在请求后端检测链路…</p>';
    postPlayground(v).then(function (body) {
      renderCheckResult(result, body, false);
    }).catch(function (err) {
      result.innerHTML = '<p class="xk-notice xk-notice--bad">检测链路不可达（' +
        esc(err.status ? 'HTTP ' + err.status : '网络不可达') +
        '）。这不代表输入安全，只代表这次没测成 —— 完整能力见「攻防靶场」。</p>';
    }).then(function () { heroPlay.running = false; });
  }

  /**
   * 首屏可玩的绑定：用 document 级委托（submit + click），只绑一次。
   * 为什么不用元素级监听：视图会被 SPA 反复替换，元素级监听要么漏绑、要么重复绑；
   * 委托天然幂等，也不需要为"换回来"单独写一套恢复逻辑。
   */
  function initHeroPlay() {
    if (heroPlay.bound) return;
    heroPlay.bound = true;
    document.addEventListener('submit', function (e) {
      var form = e.target.closest ? e.target.closest('[data-xk-play="hero"]') : null;
      if (!form) return;
      e.preventDefault();
      heroPlayRun();
    });
    document.addEventListener('click', function (e) {
      if (!e.target.closest) return;
      var chip = e.target.closest('[data-xk-play-preset]');
      if (chip) {
        var form = chip.closest('[data-xk-play="hero"]');
        if (!form) return;
        var input = $('[data-xk-play-input]', form);
        if (input) input.value = chip.getAttribute('data-xk-play-preset');
        heroPlayRun(input ? input.value : '');
      }
    });
  }

  /* ==========================================================================
     15. 阅读页增强（第十一轮 ③）：进度、复制引用、回到顶部
     同样用 document 级委托，理由与上面一致。
     ========================================================================== */
  function copyText(txt, onOk, onFail) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(onOk, onFail);
      return;
    }
    var ta = document.createElement('textarea');
    ta.value = txt; ta.setAttribute('readonly', '');
    ta.style.position = 'fixed'; ta.style.left = '-9999px';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); onOk(); } catch (e) { onFail(); }
    document.body.removeChild(ta);
  }

  function initNoteExtras() {
    if (initNoteExtras.bound) return;
    initNoteExtras.bound = true;
    document.addEventListener('click', function (e) {
      if (!e.target.closest) return;
      var cite = e.target.closest('[data-xk-cite]');
      if (cite) {
        var txt = citationText(cite.getAttribute('data-cite-title'),
          cite.getAttribute('data-cite-date'), cite.getAttribute('data-cite-url'));
        var msg = $('[data-xk-cite-msg]', contentEl);
        copyText(txt,
          function () { if (msg) msg.textContent = '引用已复制'; toast('引用已复制'); },
          function () { if (msg) msg.textContent = '复制失败，请手动选择标题'; });
        return;
      }
      if (e.target.closest('[data-xk-top]')) {
        var reduce = prefersReducedMotion();
        contentEl.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
        window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
      }
    });
  }

  // 内容区滚动 → 更新阅读进度条（#content 在桌面是内部滚动容器，窄屏是文档流）
  contentEl.addEventListener('scroll', updateProgress, { passive: true });
  window.addEventListener('scroll', updateProgress, { passive: true });

  /* ==========================================================================
     16. 主题开关 + 全局委托（主题 / 引用的键盘可达）
     ========================================================================== */
  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-xk-theme-toggle]') : null;
    if (t) { toggleTheme(); return; }
  });

  /* ==========================================================================
     14. 启动
     ========================================================================== */
  applyTheme(currentTheme(), false);   // 读 <html data-xk-theme>（head 里的内联脚本已按存储值写好）
  initHeroPlay();
  initNoteExtras();
  render(currentRoute());
})();