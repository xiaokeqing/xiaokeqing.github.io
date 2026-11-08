
/* ★2026-11-08 站主口径：左上角头像卡取消，头像并入顶栏右侧 .dock-tools
   （顺序 头像 → 声音 → 登录）。原来这套「桌面左栏 rail() + ▾ 折叠」的定位坐标
   （LEFT=8 / top=104 / top=56）全部退役 —— 卡片节点已 hidden，不再需要给 .dock 让位。
   这里保留 window.__xkRail 作为空操作：旧代码/诊断若调用它，不会再把顶栏挪走；
   只负责清掉历史上可能写进 .dock 的内联定位。 */
(function(){
  function rail(){
    var dock = document.querySelector('.dock');
    if (!dock) return;
    dock.style.top = ''; dock.style.left = ''; dock.style.right = '';
    dock.style.bottom = ''; dock.style.transform = '';
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', rail);
  else rail();
  window.addEventListener('resize', rail);
  window.addEventListener('load', rail);
  window.__xkRail = rail;
})();
