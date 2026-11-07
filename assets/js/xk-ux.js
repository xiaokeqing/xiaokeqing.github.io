/* XK-LAB 的体验小件（2026-11-07 站主「把项目全做完」；2026-11-07 晚 A8 补完）
   四件事，全部零依赖、零额外请求（⌘K 用现成的 /index-lite.json，慢网不预取）：
   1) ⌘K / Ctrl+K 命令面板：跳页 + 搜笔记标题与摘要（摘要同时参与匹配、并在结果项下方显示 40 字）
   2) 笔记页：阅读进度条
   3) 笔记页：所有 <pre> 加「复制」按钮
   4) 离线提示条：sw.js 回缓存兜底时会 postMessage({xk:'offline'})，这里插一行「当前离线，显示的是缓存版本」
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
  var liteP = null, liteD = null;   /* liteP = 在飞的 promise；liteD = 落地后的索引（render 读它） */
  function loadLite() {
    if (liteP) return liteP;
    liteP = fetch('/index-lite.json', { cache: 'force-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { liteD = j; return j; })
      .catch(function () { return null; });
    return liteP;
  }

  /* 首页（idcard 外壳）只加载 css/xk-idcard.css，不引 css/xk.css ⇒ 面板/离线条会退化成
     页面顶部的裸 DOM（实测 position:static、z-index:auto，被固定层压住 = 看起来没反应）。
     样式正式版在 css/xk.css 末尾；这里只做兜底：检测不到固定定位就注入同一套最小规则。 */
  var FALLBACK_CSS = '.xk-pal{position:fixed;inset:0;z-index:9000;display:none;background:rgba(4,8,10,.62);backdrop-filter:blur(6px)}' +
    '.xk-pal.on{display:flex;align-items:flex-start;justify-content:center;padding-top:12vh}' +
    '.xk-pal-in{width:min(640px,92vw);background:rgba(12,18,22,.96);border:1px solid rgba(127,212,216,.22);border-radius:14px;box-shadow:0 24px 60px rgba(0,0,0,.55);overflow:hidden}' +
    '.xk-pal-in input{width:100%;padding:14px 16px;background:transparent;border:0;border-bottom:1px solid rgba(127,212,216,.14);color:inherit;font:inherit;outline:none}' +
    '.xk-pal-list{max-height:52vh;overflow:auto;padding:6px}' +
    '.xk-pal-i{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:9px 12px;border-radius:9px;color:inherit;text-decoration:none}' +
    '.xk-pal-m{min-width:0;display:flex;flex-direction:column;gap:2px}' +
    '.xk-pal-i b{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
    '.xk-pal-i span{opacity:.55;font-size:12.5px;white-space:nowrap}' +
    '.xk-pal-i.on,.xk-pal-i:hover{background:rgba(127,212,216,.12)}' +
    '.xk-pal-s{font-style:normal;font-size:12px;line-height:1.35;opacity:.55;max-width:min(420px,56vw);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
    '.xk-pal-empty{padding:16px;opacity:.6;font-size:13px}' +
    '.xk-offline{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:8500;padding:7px 14px;border-radius:999px;font-size:12.5px;line-height:1.4;text-align:center;background:rgba(10,16,19,.94);color:#dfe9ec;border:1px solid rgba(127,212,216,.45);box-shadow:0 8px 24px rgba(0,0,0,.5);pointer-events:none}';
  function ensureCss() {
    var p = doc.querySelector('.xk-pal');
    if (!p || doc.getElementById('xk-ux-css')) return;
    if (getComputedStyle(p).position === 'fixed') return;   /* 正常页面：样式来自 css/xk.css */
    var st = doc.createElement('style');
    st.id = 'xk-ux-css';
    st.textContent = FALLBACK_CSS;
    (doc.head || doc.documentElement).appendChild(st);
  }

  function buildPalette() {
    var box = doc.createElement('div');
    box.className = 'xk-pal';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', '命令面板');
    box.innerHTML = '<div class="xk-pal-in"><input id="xkPalQ" type="text" autocomplete="off" spellcheck="false" placeholder="跳到页面 / 搜笔记标题或摘要…（Esc 关闭）"><div class="xk-pal-list" id="xkPalList"></div></div>';
    doc.body.appendChild(box);
    ensureCss();

    var q = box.querySelector('#xkPalQ'), list = box.querySelector('#xkPalList');
    var items = [], sel = 0;

    function render() {
      var kw = q.value.trim().toLowerCase();
      var out = [], i;
      for (i = 0; i < PAGES.length; i++) {
        if (!kw || PAGES[i][0].toLowerCase().indexOf(kw) >= 0) out.push({ t: PAGES[i][0], u: PAGES[i][1], k: '页面' });
      }
      var notes = (liteD && liteD.notes) || [];
      for (i = 0; i < notes.length && out.length < 40; i++) {
        var n = notes[i], t = n.title || n.slug || '';
        /* 摘要：压平成一行再参与匹配（整段都算，别只搜前 40 字）；展示的只留前 40 字 + 省略号 */
        var fs = String(n.summary || '').replace(/\s+/g, ' ').trim();
        if (!kw || String(t).toLowerCase().indexOf(kw) >= 0 || fs.toLowerCase().indexOf(kw) >= 0) {
          out.push({
            t: t, u: '/posts/' + n.slug + '/', k: (n.categories || []).join(' · ') || '笔记',
            s: fs.length > 40 ? fs.slice(0, 40) + '…' : fs
          });
        }
      }
      items = out.slice(0, 40); sel = 0;
      if (!items.length) { list.innerHTML = '<div class="xk-pal-empty">没有匹配（面板搜「页面名 / 笔记标题 / 笔记摘要」；全文搜索在 /posts/ 顶部）</div>'; return; }
      var html = '';
      for (i = 0; i < items.length; i++) {
        html += '<a class="xk-pal-i' + (i === 0 ? ' on' : '') + '" href="' + items[i].u + '"><div class="xk-pal-m"><b></b>' +
                (items[i].s ? '<i class="xk-pal-s"></i>' : '') + '</div><span></span></a>';
      }
      list.innerHTML = html;
      var els = list.querySelectorAll('.xk-pal-i');
      for (i = 0; i < els.length; i++) {
        els[i].querySelector('b').textContent = items[i].t;
        els[i].querySelector('span').textContent = items[i].k;
        var sEl = els[i].querySelector('.xk-pal-s');
        if (sEl) sEl.textContent = items[i].s;
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
      loadLite().then(function () { if (box.classList.contains('on')) render(); });
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

  /* ---------------- 4) 离线提示条 ---------------- */
  var offbar = null;
  function offlineBar() {
    if (offbar && offbar.parentNode) return;      /* 只插一行，重复消息不叠条 */
    offbar = doc.createElement('div');
    offbar.className = 'xk-offline';
    offbar.setAttribute('role', 'status');
    offbar.textContent = '当前离线，显示的是缓存版本';
    doc.body.appendChild(offbar);
  }
  function swUx() {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.addEventListener('message', function (e) {
      var d = e.data || {};
      if (d.xk !== 'offline') return;
      /* reason=state 是页面启动时主动问来的「历史兜底」：只有发生在本次导航里，才说明这一页
         确实是缓存版；否则 60 秒内重新联网、正常打开的页面会误挂一条「当前离线」。 */
      if (d.reason === 'state' && typeof d.at === 'number') {
        var dt = d.at - (performance.timeOrigin || (Date.now() - 1));
        if (dt < -200 || dt > 5000) return;
      }
      try { offlineBar(); } catch (x) { }
    });
    /* 断网首屏：SW 的广播常常早于本脚本执行，反过来问它一句「刚才兜底过吗」 */
    navigator.serviceWorker.ready.then(function (reg) {
      var a = reg.active;
      if (a && a.postMessage) { try { a.postMessage({ xk: 'state' }); } catch (x) { } }
    }).catch(function () { });
    /* 回网后自己收掉，不用刷新页面 */
    addEventListener('online', function () {
      if (offbar && offbar.parentNode) offbar.parentNode.removeChild(offbar);
    });
  }

  function boot() {
    try { buildPalette(); } catch (e) { }
    try { swUx(); } catch (e) { }
    if (doc.querySelector('article.xk-article, .post-body, article')) { try { articleUx(); } catch (e) { } }
  }
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
