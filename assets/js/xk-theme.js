/* 主题（第十一轮 A 项）+ 截图/软件渲染开关 + 固定浅色 data-theme 守卫。
     必须在样式表之前同步执行，否则会闪一下默认主题。
     注意：data-theme="light" 一直是浅色（站主 §0 硬约束：不允许深色模式偷偷生效）；
     这里新增的 data-xk-theme 是【两套玻璃配方】的开关：
       tech = 深色玻璃 + 霓虹描边（默认，站主第十一轮要求"界面要整体透明、有科技感"）
       read = 浅色玻璃（长文阅读更舒服，可由页面上的开关一键切回，并被记忆） */
  (function () {
    var d = document.documentElement;
    if (/[?&]wb_noblur=1/.test(location.search)) d.setAttribute('data-wb-noblur', '1');
    d.setAttribute('data-theme', 'light');
    var t = 'tech';
    try { var saved = localStorage.getItem('xk-theme'); if (saved === 'read' || saved === 'tech') t = saved; } catch (e) { /* 隐私模式忽略 */ }
    if (/[?&]theme=read/.test(location.search)) t = 'read';
    if (/[?&]theme=tech/.test(location.search)) t = 'tech';
    d.setAttribute('data-xk-theme', t);
    /* ★ 步骤 2：主页的 CRT 场景整屏铺在 bg.jpg 那一层之上，这个开关必须在这里打开
       （本脚本在样式表之前同步执行），否则 .xk-bg 的背景图（674KB）会在属性打开之前
       就被请求 —— 实测首屏白下 674KB，而且首帧会先闪一下 bg.jpg 再换成书桌照片。
       kurisu-player.js 之后仍按当前 hash 路由维护同一个属性（SPA 换页时由它开关）。
       2026-11-09：原来这里是 Hugo 的 {{ if and site.Params.kurisuEnabled .IsHome }} 条件，
       搬成静态资源后没有模板了，改成运行时判路径 —— 语义等价（kurisuEnabled 已在
       hugo.toml 里为 true，主页就是 / 或 /index.html）。 */
    var path = location.pathname;
    if (path === '/' || path === '/index.html') d.setAttribute('data-xk-crt-on', '1');
    try {
      localStorage.removeItem('pref-theme');
      localStorage.removeItem('pref-theme-default');
    } catch (e) { /* 隐私模式下 localStorage 可能抛错，忽略 */ }
  })();
