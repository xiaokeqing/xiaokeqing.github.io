
/* ★M1（2026-10-18）：手机上点头像或箭头展开/收起功能栏。
   为什么头像在手机上不再“换个情绪说一句”：那个动作在小屏上没有可见反馈（全身画布只在主页），
   反而会让人以为“点了没反应”。桌面行为不变。
   ★DESK-RAIL 2026-10-18：桌面（>980px）现在也走这条路 —— 功能钮收进卡片折叠，
   ▾ 是同一个按钮、.open 是同一个类；展开/收起后通知第二段脚本的 rail() 把导航挪到新位置
   （**不新写第二套展开逻辑**，只多这一行）。 */
(function(){
  var card = document.getElementById('xkIdCard');
  var fold = document.getElementById('xkIdFold');
  var av   = document.getElementById('xkIdAv');
  if(!card) return;
  function isNarrow(){ return window.innerWidth <= 980; }
  function setOpen(on){
    card.classList.toggle('open', !!on);
    if(fold) fold.setAttribute('aria-expanded', on ? 'true' : 'false');
    if(window.__xkRail) window.__xkRail();   /* 桌面：卡片下面那串（功能钮 / 导航）重新落位 */
  }
  if(fold) fold.addEventListener('click', function(e){ e.preventDefault(); e.stopPropagation(); setOpen(!card.classList.contains('open')); });
  if(av) av.addEventListener('click', function(e){
    if(!isNarrow()) return;                 /* 桌面：保留原有“点一下换情绪” */
    e.preventDefault(); e.stopPropagation();
    setOpen(!card.classList.contains('open'));
  }, true);
  /* 展开后点别处收起（不抓鼠标移出，手机上容易误触） */
  document.addEventListener('click', function(e){
    if(!card.classList.contains('open')) return;
    if(card.contains(e.target)) return;
    var col = document.getElementById('xkIdCol');
    if(col && col.contains(e.target)) return;
    setOpen(false);
  }, true);
  window.addEventListener('resize', function(){ if(!isNarrow()) setOpen(false); });
})();
/* ★2026-10-17（站主 m06282「位置太挤了…导航栏不行直接放到中间吧」）：宽屏把左栏三块竖排。
   ★DESK-RAIL 2026-10-18 站主口径改了：**不再垂直居中**，改成左边缘一条从上往下的轨 ——
     头像卡贴左上（CSS 里 left:8px;top:8px）→ 展开时的功能钮 → 导航，每段之间 8px。
   为什么不再居中：居中那套在 1920×1000（实测视口 1532×745）会把卡片推到屏幕中段（实测 y=198），
     三块加起来 605px 几乎顶满一屏，导航第一行还和卡片同列打架；收进折叠后左栏只剩「卡 + 导航」两块。
   这里只写 top/left：高度全部现读 offsetHeight（卡 88 / 钮 ~140 / 导航 ~357 都随系统字体和页面变），不写死。 */
(function(){
  var LEFT = 8, GAP = 8;
  function rail(){
    var card = document.querySelector('.xk-idcard'),
        dock = document.querySelector('.dock'),
        col  = document.querySelector('.xk-idcard-col');
    if (!card || !dock) return;
    /* ★守卫放进来、并且每次 resize 都清一次内联定位：
       否则宽屏渲染后被拉窄，三块会带着旧的 top/left 停在屏幕中间压住正文（窄屏实测）。 */
    if (window.innerWidth <= 980) {
      [card, dock, col].forEach(function(e){ if (!e) return;
        e.style.top = ''; e.style.left = ''; e.style.right = '';
        e.style.bottom = ''; e.style.transform = ''; });
      return;
    }
    [card, dock, col].forEach(function(e){ if (!e) return;
      e.style.left = LEFT + 'px'; e.style.right = 'auto';
      e.style.bottom = 'auto'; e.style.transform = 'none'; });
    /* 卡片自己的 top 交给 CSS（left:8px;top:8px），这里只从它下沿往下排 */
    var y = LEFT + card.offsetHeight + GAP;
    if (col) {
      col.style.top = y + 'px';
      /* 收起时 CSS 是 display:none（桌面不再常驻）⇒ offsetHeight=0 ⇒ 不占位，导航紧贴卡片 */
      if (col.offsetHeight) y += col.offsetHeight + GAP;
    }
    dock.style.top = y + 'px';
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', rail);
  else rail();
  window.addEventListener('resize', rail);
  window.addEventListener('load', rail);
  window.__xkRail = rail;
})();
