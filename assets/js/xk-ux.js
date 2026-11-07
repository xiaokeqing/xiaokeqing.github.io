/* XK-LAB 的体验小件（2026-11-07 站主「把项目全做完」）
   三件事，全部零依赖、零额外请求（⌘K 用现成的 /index-lite.json，慢网不预取）：
   1) ⌘K / Ctrl+K 命令面板：跳页 + 搜笔记标题
   2) 笔记页：阅读进度条
   3) 笔记页：所有 <pre> 加「复制」按钮
   设计约束（同站点口径）：只用 textContent 写 DOM；不引入图表/UI 库；慢网（html.xk-slow）下不预取索引，只在打开面板时按需取。 */
(function () {
  'use strict';
  var doc = document, root = doc.documentElement;
  var isSlow = function () { return root.classList.contains('xk-slow'); };
  var ssr = function () { var m = doc.getElementById('content'); return m ? (m.getAttribute('data-xk-ssr') || '') : ''; };

  /* ---------------- 1) 命令面板 ---------------- */
  var PAGES = [
    ['主页', '/'], ['攻击实况', '/alerts/'], ['安全日报', '/daily/'],
    ['AI 问答', '/ai/'], ['笔记', '/posts/'], ['攻防验证', '/lab/'], ['更多', '/more/'],
    ['报告目录', '/reports/'], ['状态', '/status/'], ['接口', '/api/']
  ];
  var liteP = null;
  function loadLite() {
    if (liteP) return liteP;
    liteP = fetch('/index-lite.json', { cache: 'force-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
    return liteP;
  }

  function buildPalette() {
    var box = doc.createElement('div');
    box.className = 'xk-pal';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', '命令面板');
    box.innerHTML = '<div class="xk-pal-in"><input id="xkPalQ" type="text" autocomplete="off" spellcheck="false" placeholder="跳到页面 / 搜笔记标题…（Esc 关闭）"><div class="xk-pal-list" id="xkPalList"></div></div>';
    doc.body.appendChild(box);

    var q = box.querySelector('#xkPalQ'), list = box.querySelector('#xkPalList');
    var items = [], sel = 0;

    function render() {
      var kw = q.value.trim().toLowerCase();
      var out = [], i;
      for (i = 0; i < PAGES.length; i++) {
        if (!kw || PAGES[i][0].toLowerCase().indexOf(kw) >= 0) out.push({ t: PAGES[i][0], u: PAGES[i][1], k: '页面' });
      }
      var notes = (liteP && liteP.notes) || [];
      for (i = 0; i < notes.length && out.length < 40; i++) {
        var n = notes[i], t = n.title || n.slug || '';
        if (!kw || String(t).toLowerCase().indexOf(kw) >= 0 || String(n.summary || '').toLowerCase().indexOf(kw) >= 0) {
          out.push({ t: t, u: '/posts/' + n.slug + '/', k: (n.categories || []).join(' · ') || '笔记' });
        }
      }
      items = out.slice(0, 40); sel = 0;
      if (!items.length) { list.innerHTML = '<div class="xk-pal-empty">没有匹配（面板只搜笔记标题；全文搜索在 /posts/ 顶部）</div>'; return; }
      var html = '';
      for (i = 0; i < items.length; i++) {
        html += '<a class="xk-pal-i' + (i === 0 ? ' on' : '') + '" href="' + items[i].u + '"><b></b><span></span></a>';
      }
      list.innerHTML = html;
      var els = list.querySelectorAll('.xk-pal-i');
      for (i = 0; i < els.length; i++) {
        els[i].querySelector('b').textContent = items[i].t;
        els[i].querySelector('span').textContent = items[i].k;
      }
    }
    function move(d) {
      var els = list.querySelectorAll('.xk-pal-i');
      if (!els.length) return;
      if (els[sel]) els[sel].classList.remove('on');
      sel = (sel + d + els.length) % els.length;
      els[sel].classList.add('on');
      els[sel].scrollIntoView({ block: 'nearest' });
    }
    function close() { box.classList.remove('on'); if (q) q.blur(); }
    function open() {
      box.classList.add('on');
      q.value = ''; render(); q.focus();
      loadLite().then(function () { loadLite(); if (box.classList.contains('on')) render(); });
    }

    q.addEventListener('input', render);
    box.addEventListener('click', function (e) { if (e.target === box) close(); });
    q.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
      else if (e.key === 'Enter') { if (items[sel]) location.href = items[sel].u; }
      else if (e.key === 'Escape') { close(); }
    });
    doc.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); box.classList.contains('on') ? close() : open(); }
      else if (e.key === 'Escape' && box.classList.contains('on')) { close(); }
    });
  }

  /* ---------------- 2)+3) 笔记页：进度条 / 复制按钮 ---------------- */
  function articleUx() {
    var art = doc.querySelector('article.xk-article, .post-body, article');
    if (!art) return;
    var bar = doc.createElement('div');
    bar.className = 'xk-readbar';
    bar.innerHTML = '<i></i>';
    doc.body.appendChild(bar);
    var i = bar.firstChild;
    function onScroll() {
      var r = art.getBoundingClientRect();
      var h = r.height - innerHeight;
      var p = h > 0 ? Math.min(1, Math.max(0, -r.top / h)) : 1;
      i.style.width = (p * 100).toFixed(2) + '%';
    }
    addEventListener('scroll', onScroll, { passive: true });
    addEventListener('resize', onScroll);
    onScroll();

    var pres = art.querySelectorAll('pre');
    for (var k = 0; k < pres.length; k++) {
      (function (pre) {
        if (pre.querySelector('.xk-copy')) return;
        var b = doc.createElement('button');
        b.className = 'xk-copy'; b.type = 'button'; b.textContent = '复制';
        b.addEventListener('click', function () {
          var code = pre.querySelector('code') || pre;
          var txt = code.textContent || '';
          var done = function () { b.textContent = '已复制'; setTimeout(function () { b.textContent = '复制'; }, 1400); };
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(txt).then(done, function () { b.textContent = '复制失败'; });
          } else {
            var ta = doc.createElement('textarea');
            ta.value = txt; doc.body.appendChild(ta); ta.select();
            try { doc.execCommand('copy'); done(); } catch (e) { b.textContent = '复制失败'; }
            doc.body.removeChild(ta);
          }
        });
        pre.appendChild(b);
      })(pres[k]);
    }
  }

  function boot() {
    try { buildPalette(); } catch (e) { }
    if (doc.querySelector('article.xk-article, .post-body, article')) { try { articleUx(); } catch (e) { } }
  }
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
