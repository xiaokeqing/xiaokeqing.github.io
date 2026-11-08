/* /session/ 会话时间线：点开一行时把事件逐行亮起（打字机观感，不自动播放）。
   无 JS 时 SSR 输出就是全亮，可读性不依赖脚本；prefers-reduced-motion 直接整段显示。 */
(function () {
  var reduce = false;
  try {
    reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch (e) {}

  function play(box) {
    var lines = box.querySelectorAll('.ss-line');
    var i;
    if (box._ssTimers) {
      for (i = 0; i < box._ssTimers.length; i++) clearTimeout(box._ssTimers[i]);
    }
    box._ssTimers = [];
    for (i = 0; i < lines.length; i++) lines[i].classList.remove('on');
    if (reduce) {
      for (i = 0; i < lines.length; i++) lines[i].classList.add('on');
      return;
    }
    box.classList.add('is-playing');
    for (i = 0; i < lines.length; i++) {
      (function (ln, k) {
        box._ssTimers.push(setTimeout(function () { ln.classList.add('on'); }, 150 * k));
      })(lines[i], i);
    }
  }

  var rows = document.querySelectorAll('details.ss-sess');
  for (var i = 0; i < rows.length; i++) {
    rows[i].addEventListener('toggle', function () {
      if (!this.open) return;
      var box = this.querySelector('.ss-term');
      if (box) play(box);
      try {
        history.replaceState(null, '', '#' + this.id);
      } catch (e) {}
    });
  }

  // 带 #s-xxxx 进来时直接展开对应会话并播
  if (location.hash && location.hash.indexOf('#s-') === 0) {
    var hit = document.getElementById(location.hash.slice(1));
    if (hit && hit.tagName === 'DETAILS') {
      hit.open = true;
      var b = hit.querySelector('.ss-term');
      if (b) play(b);
    }
  }
})();
