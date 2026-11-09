/* xk-kurisu.js —— 角色播放器的加载判定（2026-11-09 从 baseof.html 的内联里搬出来）
   规则：
     · 慢网（html.xk-slow）不装这个 71 KB 模块，也不取它要的 manifest（60 KB）；
       想在这种网络下看角色：URL 加 ?xk-kurisu=on。
     · 这一页没有"大 CRT 画布"时根本不装：分类页 / 笔记列表 / 笔记详情都是这种页面，
       它们的侧栏小面板由 xk-idcard.js 铺一张 19 KB 静态帧（/images/crt/panel-poster.webp），
       想看动画同样加 ?xk-kurisu=on。
   装的时候才动态插 <script defer>，不占首屏解析。 */
(function () {
  'use strict';
  try {
    var d = document.documentElement;
    if (d.classList.contains('xk-slow') && String(location.search).indexOf('xk-kurisu=on') < 0) { return; }
  } catch (e) { }
  try {
    if (String(location.search).indexOf('xk-kurisu=on') < 0) {
      var probe = document.querySelector('#charCanvas, #crt, .crt');
      if (!probe || probe.getBoundingClientRect().height < 300) {
        /* 告诉 CSS：这一页不走播放器 ⇒ 小舞台铺静态帧（见 extended/zz-kurisu.css 的 html.xk-noplayer 段） */
        document.documentElement.classList.add('xk-noplayer');
        return;
      }
    }
  } catch (e) { }
  var s = document.createElement('script');
  s.src = '/js/kurisu-player.js';
  s.defer = true;
  document.head.appendChild(s);
})();
