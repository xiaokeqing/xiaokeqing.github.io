/* xk-rail.js —— 数据页侧栏默认收起，用户的选择本地记住。
   为什么单独一个 1KB 文件：只在 monitor / daily / ip / noise / passwords / more
   这些"读数字的页面"上生效，与首页舞台、内容页 CRT 完全无关。 */
(function () {
  'use strict';
  var DATA_PAGES = ['monitor', 'daily', 'ip', 'noise', 'passwords', 'more', 'api'];
  var KEY = 'xk-rail';
  var main = document.getElementById('content');
  var page = main && main.getAttribute('data-xk-ssr');
  if (DATA_PAGES.indexOf(page) < 0) { return; }

  var root = document.documentElement;
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) { saved = null; }
  /* 默认收起；只有用户显式展开过（saved === 'open'）才保留面板 */
  var collapsed = saved !== 'open';

  function apply(state) {
    root.classList.toggle('xk-rail-collapsed', state);
    btn.setAttribute('aria-pressed', state ? 'true' : 'false');
    btn.setAttribute('aria-label', state ? '展开右侧面板' : '收起右侧面板');
    btn.textContent = state ? '展 开' : '收 起';
  }

  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'xk-rail-toggle';
  btn.addEventListener('click', function () {
    collapsed = !collapsed;
    try { localStorage.setItem(KEY, collapsed ? 'collapsed' : 'open'); } catch (e) {}
    apply(collapsed);
  });

  function mount() {
    if (!btn.parentNode) { document.body.appendChild(btn); }
    apply(collapsed);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
