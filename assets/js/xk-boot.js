/* xk-boot.js —— 必须在样式表之前同步执行的那一小段（2026-11-09 从 head-meta.html 的内联里搬出来）
   为什么单独一个文件：CSP 要去掉 'unsafe-inline'，内联脚本必须清零；
   而这两段又确实必须早于 CSS 执行，所以用"阻塞脚本 + 一年缓存"换掉每次内联的 900 字节。

   ① 按网速分档（★2026-11-04 站主口径：按网速分档，不按设备）：
      给 <html> 挂 xk-slow，样式里所有"慢网省流"的规则都挂在这个类上。
      只读不发请求。?xk-net=fast / ?xk-net=slow 可强制。
   ② /ai/ 的手机面板：E-mote ready 之前不要先画 Sprite/poster（否则进页面先闪一帧大白脸）。
      挂 xk-phone-emote-wait，由 xk-shell.js 在 ready/失败/超时时摘掉。 */
(function () {
  'use strict';

  /* ① 慢网判定 */
  try {
    var c = navigator.connection || {}, et = String(c.effectiveType || ''), q = String(location.search);
    if (q.indexOf('xk-net=fast') >= 0) { return; }
    var slow = !!c.saveData || et === 'slow-2g' || et === '2g' ||
      (typeof c.downlink === 'number' && c.downlink > 0 && c.downlink < 2);
    if (q.indexOf('xk-net=slow') >= 0) { slow = true; }
    if (slow) { document.documentElement.classList.add('xk-slow'); }
  } catch (e) { }

  /* ② /ai/ 手机面板：等 E-mote ready 再画 */
  try {
    var p = String(location.pathname || '');
    if (p.indexOf('/ai/') !== 0) { return; }
    var q2 = String(location.search || '');
    if (q2.indexOf('xk-phone-emote=off') >= 0 || q2.indexOf('xk-kurisu=off') >= 0 ||
        q2.indexOf('xk-no-kurisu=1') >= 0) { return; }
    if ((window.innerWidth || 0) < 1280) { return; }
    if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) { return; }
    var mem = navigator.deviceMemory || 0, cores = navigator.hardwareConcurrency || 0;
    if (mem && mem < 8) { return; }
    if (cores && cores < 4) { return; }
    document.documentElement.classList.add('xk-phone-emote-wait');
    setTimeout(function () {
      if (!document.documentElement.classList.contains('xk-emote-ready')) {
        document.documentElement.classList.remove('xk-phone-emote-wait');
      }
    }, 9000);
  } catch (e) { }
})();
