
/* ★M1（2026-10-18）：手机上点头像或箭头展开/收起功能栏。
   为什么头像在手机上不再“换个情绪说一句”：那个动作在小屏上没有可见反馈（全身画布只在主页），
   反而会让人以为“点了没反应”。桌面行为不变。 */
(function(){
  var card = document.getElementById('xkIdCard');
  var fold = document.getElementById('xkIdFold');
  var av   = document.getElementById('xkIdAv');
  if(!card) return;
  function isNarrow(){ return window.innerWidth <= 980; }
  function setOpen(on){
    card.classList.toggle('open', !!on);
    if(fold) fold.setAttribute('aria-expanded', on ? 'true' : 'false');
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
/* ★2026-10-17（站主 m06282「位置太挤了…导航栏不行直接放到中间吧」）：
   宽屏把「头像卡 / 导航 / 功能钮」三块竖排在左边缘并**垂直居中**——原来三块各自 fixed 定位，
   窗口一矮就互相压（他为这个截过图）。这里只做竖直排布，不改任何一块自身样式；
   窄屏（≤980）直接 return，走 CSS 里那套「头像左上 + 导航底部 + 功能钮底部横排」。 */
(function(){
  function rail(){
    var card = document.querySelector('.xk-idcard'),
        dock = document.querySelector('.dock'),
        col  = document.querySelector('.xk-idcard-col');
    var els = [card, dock, col].filter(Boolean);
    if (!els.length) return;
    /* ★守卫放进来、并且每次 resize 都清一次内联定位：
       否则宽屏渲染后被拉窄，三块会带着旧的 top/left 停在屏幕中间压住正文（窄屏实测）。 */
    if (window.innerWidth <= 980) {
      els.forEach(function(e){ e.style.top = ''; e.style.left = ''; e.style.right = '';
        e.style.bottom = ''; e.style.transform = ''; });
      return;
    }
    var gap = 10, total = 0, i;
    els.forEach(function(e){ e.style.left = '10px'; e.style.transform = 'none';
      e.style.right = 'auto'; e.style.bottom = 'auto'; e.style.top = '0px'; });
    els.forEach(function(e){ total += e.offsetHeight + gap; });
    total -= gap;
    var y = Math.max(12, Math.round((window.innerHeight - total) / 2));
    els.forEach(function(e){ e.style.top = y + 'px'; y += e.offsetHeight + gap; });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', rail);
  else rail();
  window.addEventListener('resize', rail);
  window.addEventListener('load', rail);
  window.__xkRail = rail;
})();
