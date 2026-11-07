/* ============================================================================
   xk-search-lazy.js · 搜索懒块（2026-11-07 拆包）
   ----------------------------------------------------------------------------
   站主口径：「分类页 383 KB 里 app.js 120 KB 要拆 —— 只在搜索/筛选时才用的
   模糊匹配、索引解析不该占首屏。」于是：
     · app.js 只剩**轻量绑定**：Ctrl+K / "/" 开合、Esc、上下键转发、输入框转发，
       以及 searchState（开合状态由它持有，键盘判定读得到）；
     · 本文件持有**只有打开搜索才跑**的那半边：
         loadLite()      /index-lite.json 的取与解（约 80 KB，无正文）
         hi()            命中高亮（查询串转安全正则，只在已 esc 的文本上包 <mark>）
         searchBucket()  标题 / 分类·标签 / 正文 三档分组
         renderSearch()  过滤 + 分组 + 列表 HTML
         moveSearch()    上下键移动（scrollIntoView 保持可见）
         submitSearch()  回车进笔记
         prefetchIndex() 快网空闲预取（html.xk-slow / saveData / 2g-3g / 下行<2Mbps 不预取）
     · 由 app.js 的 searchLazy() 在【用户真的打开搜索】或快网空闲时注入；
       用户从不搜索 ⇒ 这一个字节都不会下。
   入口：window.__xkSearch = { init, open, close, render, move, submit, prefetch, stats }
   指纹：layouts/baseof.html 里 resources.Get "js/xk-search-lazy.js" | minify | fingerprint，
         URL 写进 <meta name="xk-search-lazy">（app.js 在 static/ 下没有 Hugo 内容管道）。
   ========================================================================== */
(function () {
  'use strict';

  var Q = null, QA = null, ESC = null, GO = null, TXT = null;
  var state = null;           /* app.js 的 searchState（同一个对象，开合/条目/游标） */
  var LITE = null;            /* 轻索引缓存 */

  function init(deps) {
    Q = deps.$; QA = deps.$$; ESC = deps.esc; GO = deps.navigate; TXT = deps.toast;
    state = deps.state;
  }

  /* -------------------------------------------------------------------------
     8. 索引解析（原 static/js/app.js:1078-1083）
     ------------------------------------------------------------------------- */
  function loadLite() {
    if (LITE) return Promise.resolve(LITE);
    return fetch('/index-lite.json', { cache: 'no-cache' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (j) { LITE = j; return LITE; });
  }

  /* -------------------------------------------------------------------------
     12. 搜索：打开 → 取索引 → 渲染 → 键盘/提交
     ------------------------------------------------------------------------- */
  function open() {
    var input = Q('#xk-search-input');
    if (input) { input.value = ''; input.focus(); }
    var modal = Q('#xk-search');
    if (modal) modal.hidden = false;
    state.open = true;
    var list = Q('#xk-search-list');
    if (list) list.innerHTML = '<li class="xk-modal__empty">正在读取笔记索引…</li>';
    return loadLite().then(function (idx) {
      state.items = (idx && idx.notes) || [];
      state.cursor = 0;
      render('');
    }).catch(function () {
      var l = Q('#xk-search-list');
      if (l) l.innerHTML = '<li class="xk-modal__empty">笔记索引读取失败。</li>';
      return false;
    });
  }

  function close() {
    var modal = Q('#xk-search');
    if (modal) modal.hidden = true;
    state.open = false;
  }

  /**
   * 命中高亮：把 query 转成安全的正则（转义元字符），只对【已经 esc() 过的文本】
   * 做包裹，所以不存在把用户输入当 HTML 注入的路径（esc 在前，包 <mark> 在后）。
   */
  function hi(text, q) {
    var s = ESC(text == null ? '' : String(text));
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

  function render(q) {
    var list = Q('#xk-search-list');
    if (!list) return;
    var query = String(q || '').trim();
    var lc = query.toLowerCase();
    var items = state.items || [];
    if (query) {
      items = items.filter(function (n) {
        var hay = [n.title, (n.categories || []).join(' '), (n.tags || []).join(' '), n.summary, n.text].join(' ').toLowerCase();
        return hay.indexOf(lc) >= 0;
      });
    }
    if (!items.length) {
      list.innerHTML = '<li class="xk-modal__empty">没有匹配的笔记。</li>';
      state.filtered = [];
      return;
    }
    state.cursor = 0;

    /* 分组：标题命中 → 分类/标签命中 → 正文命中（组内保持仓库里的时间倒序） */
    var groups = ['标题命中', '分类 / 标签命中', '正文命中'];
    var html = '', flat = 0;
    var shown = items.slice(0, 20);
    groups.forEach(function (g) {
      var inGroup = shown.filter(function (n) { return searchBucket(n, query || '') === g; });
      if (!inGroup.length) return;
      html += '<li class="xk-modal__group" aria-hidden="true">' + ESC(g) + '</li>';
      inGroup.forEach(function (n) {
        var idx = flat++;
        html += '<li class="xk-modal__item' + (idx === 0 ? ' is-on' : '') + '" data-xk-idx="' + idx + '" data-xk-slug="' + ESC(n.slug) + '" role="option">' +
          '<b>' + hi(n.title, query) + '</b>' +
          '<span>' + ESC(n.date + ' · ' + (n.categories || []).join(' / ')) + ' · ' + hi(n.summary, query) + '</span></li>';
      });
    });
    list.innerHTML = html;
    // 分组后 Flat 顺序与 items 顺序一致，键盘移动仍然按 DOM 顺序走
    state.filtered = shown;
  }

  function move(delta) {
    var items = state.filtered || [];
    if (!items.length) return;
    state.cursor = (state.cursor + delta + items.length) % items.length;
    QA('#xk-search-list .xk-modal__item').forEach(function (li, i) {
      li.classList.toggle('is-on', i === state.cursor);
      if (i === state.cursor) li.scrollIntoView({ block: 'nearest' });
    });
  }

  function submit() {
    var items = state.filtered || [];
    var pick = items[state.cursor];
    if (!pick) return;
    close();
    GO('#/notes/' + pick.slug);
  }

  /* -------------------------------------------------------------------------
     13.4 轻索引空闲预取（原 static/js/app.js:2255-2282）
     -------------------------------------------------------------------------
     站主口径「每页先给最快的东西」：慢网（下行 < 2 Mbps / 省流量 / 2g-3g /
     html.xk-slow / ?xk-net=slow）**不预取**，等用户真的点开搜索再取。
     /index.json（1.2 MB，带正文）任何情况下都不预取。
     ------------------------------------------------------------------------- */
  function slowNetForIndex() {
    try {
      if (document.documentElement.classList.contains('xk-slow')) { return true; }
      var c = navigator.connection || {};
      if (c.saveData) { return true; }
      var et = String(c.effectiveType || '');
      if (et === 'slow-2g' || et === '2g' || et === '3g') { return true; }
      if (typeof c.downlink === 'number' && c.downlink > 0 && c.downlink < 2) { return true; }
    } catch (e) { }
    try {
      var q = String(location.search).match(/[?&]xk-net=([^&]+)/);
      if (q) {
        var v = decodeURIComponent(q[1]);
        if (v === 'slow') { return true; }
        if (v === 'fast') { return false; }
      }
    } catch (e) { }
    return false;
  }

  function prefetch() {
    if (slowNetForIndex()) { return Promise.resolve(false); }
    return loadLite().then(function () { return true; }).catch(function () { return false; });
  }

  window.__xkSearch = {
    init: init, open: open, close: close, render: render, move: move, submit: submit,
    prefetch: prefetch, load: loadLite, slowNet: slowNetForIndex,
    stats: function () { return { lite: !!LITE, items: state ? (state.items || []).length : 0, toast: !!TXT }; }
  };
})();
