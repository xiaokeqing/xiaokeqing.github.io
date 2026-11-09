/* 笔记正文的两件小事：右侧目录（只在大屏出现）+ 长表格折叠。
   为什么要它：/posts/network-basics-overview 这类整本讲义 56 张表、两万多字，
   从头滚到尾找不到段落；而把正文拆页会破坏"完整讲义"的定位。
   口径：目录由正文 h2/h3 现场生成（不预渲染、不加权重），窄屏直接不建；
   表格只在 >12 行时折叠，标题写清行数，默认收起但保留表头。
   2026-11-09 新增（§43 之后一轮）。 */
(function () {
  'use strict';
  var art = document.querySelector('.xk-article');
  if (!art) return;

  /* ---------- 1. 右侧目录 ---------- */
  function buildToc() {
    var nav = document.getElementById('xkToc');
    if (!nav) return;
    var heads = art.querySelectorAll('h2, h3');
    if (heads.length < 3) return;                 /* 标题太少，目录没意义 */
    var list = document.createElement('ol');
    list.className = 'xk-toc-list';
    var used = 0;
    Array.prototype.forEach.call(heads, function (h, i) {
      if (!h.id) h.id = 'h-' + i;
      var li = document.createElement('li');
      li.className = 'xk-toc-' + h.tagName.toLowerCase();
      var a = document.createElement('a');
      a.href = '#' + h.id;
      a.textContent = h.textContent.trim();
      a.addEventListener('click', function (e) {
        e.preventDefault();
        h.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', '#' + h.id);
      });
      li.appendChild(a);
      list.appendChild(li);
      used++;
    });
    if (!used) return;
    var head = document.createElement('div');
    head.className = 'xk-toc-hd';
    head.innerHTML = '<span>本页目录</span><button type="button" class="xk-toc-tg" aria-expanded="true">收起</button>';
    nav.appendChild(head);
    nav.appendChild(list);
    nav.hidden = false;
    document.documentElement.classList.add('xk-has-toc');

    head.querySelector('.xk-toc-tg').addEventListener('click', function () {
      var on = this.getAttribute('aria-expanded') === 'true';
      this.setAttribute('aria-expanded', String(!on));
      this.textContent = on ? '展开' : '收起';
      list.hidden = on;
    });

    /* 滚动高亮：只在高亮项变化时改 class，避免每帧写 DOM */
    var links = list.querySelectorAll('a');
    var current = null;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var id = en.target.id;
        for (var i = 0; i < links.length; i++) {
          var hit = links[i].getAttribute('href') === '#' + id;
          if (hit && current !== links[i]) {
            if (current) current.classList.remove('on');
            current = links[i];
            current.classList.add('on');
          }
        }
      });
    }, { rootMargin: '-72px 0px -70% 0px', threshold: 0 });
    Array.prototype.forEach.call(heads, function (h) { io.observe(h); });
  }

  /* ---------- 2. 长表格折叠 ---------- */
  function foldTables() {
    var tables = art.querySelectorAll('table');
    Array.prototype.forEach.call(tables, function (t) {
      if (t.closest('.xk-fold')) return;
      var rows = t.querySelectorAll('tbody tr').length || t.querySelectorAll('tr').length - 1;
      if (rows <= 12) return;
      var box = document.createElement('details');
      box.className = 'xk-fold';
      var sum = document.createElement('summary');
      sum.innerHTML = '展开这张表（共 ' + rows + ' 行）';
      t.parentNode.insertBefore(box, t);
      box.appendChild(sum);
      box.appendChild(t);
    });
  }

  function run() {
    try { foldTables(); } catch (e) {}
    try { buildToc(); } catch (e) {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
