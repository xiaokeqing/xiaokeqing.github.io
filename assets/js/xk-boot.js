/* xk-boot.js —— 必须在样式表之前同步执行的那几段（2026-11-09 从 head-meta.html 的内联里搬出来）
   为什么单独一个文件：CSP 要去掉 'unsafe-inline'，内联脚本必须清零；
   而这几段确实必须早于 CSS/正文脚本执行，所以用"阻塞脚本 + 一年缓存"换掉每次内联的字节。

   ★顺序是有含义的：
   ⓪ wb-api 抄写 + 清空 —— **必须在任何正文脚本之前**。数据页（/alerts/ 等）的 xk-bind.js 是
      body 里的普通 <script>，在解析到它时立刻执行，比 head 里的 defer 脚本更早；如果清空动作
      放在 defer 里，xk-bind 会读到 demo 域名、去打那条 ~600 B/s 的隧道 → 整屏"读不到"。
      （2026-11-09 第一次外链化时踩过：实时看板一片空白，就是这一条顺序错了。）
   ① 按网速分档（★站主口径：按网速分档，不按设备）：给 <html> 挂 xk-slow，样式里所有
      "慢网省流"规则都挂在这个类上。只读不发请求。?xk-net=fast / ?xk-net=slow 可强制。
   ② /ai/ 的手机面板：E-mote ready 之前不要先画 Sprite/poster（否则进页面先闪一帧大白脸）。
      挂 xk-phone-emote-wait，由 xk-shell.js 在 ready/失败/超时时摘掉。
   注意：这里**不能用 return 提前退出**（IIFE 里 return 会把后面的段一并跳过）。 */
(function () {
  'use strict';
  var q = String(location.search || '');
  var d = document.documentElement;

  /* ⓪ wb-api：原值抄到 <html data-wb-api>，再把 meta 清空 ⇒ 数据页改读同源静态快照。
       /ai/ 问答与 SSE 需要真实接口时读 data-wb-api；?live=1 保留原值。 */
  try {
    var m = document.querySelector('meta[name="wb-api"]');
    if (m) {
      var v = m.getAttribute('content') || '';
      if (v) { d.setAttribute('data-wb-api', v); }
      if (q.indexOf('live=1') < 0) { m.setAttribute('content', ''); }
    }
  } catch (e) { }

  /* ① 慢网判定 */
  try {
    if (q.indexOf('xk-net=fast') < 0) {
      var c = navigator.connection || {}, et = String(c.effectiveType || '');
      var slow = !!c.saveData || et === 'slow-2g' || et === '2g' ||
        (typeof c.downlink === 'number' && c.downlink > 0 && c.downlink < 2);
      if (q.indexOf('xk-net=slow') >= 0) { slow = true; }
      if (slow) { d.classList.add('xk-slow'); }
    }
  } catch (e) { }

  /* ② /ai/ 手机面板：等 E-mote ready 再画 */
  try {
    var p = String(location.pathname || '');
    var eligible = p.indexOf('/ai/') === 0 &&
      q.indexOf('xk-phone-emote=off') < 0 && q.indexOf('xk-kurisu=off') < 0 &&
      q.indexOf('xk-no-kurisu=1') < 0 &&
      (window.innerWidth || 0) >= 1280 &&
      !(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
    if (eligible) {
      var mem = navigator.deviceMemory || 0, cores = navigator.hardwareConcurrency || 0;
      if ((!mem || mem >= 8) && (!cores || cores >= 4)) {
        d.classList.add('xk-phone-emote-wait');
        setTimeout(function () {
          if (!d.classList.contains('xk-emote-ready')) { d.classList.remove('xk-phone-emote-wait'); }
        }, 9000);
      }
    }
  } catch (e) { }
})();
