/* ============================================================================
   xk-app.js —— 新外壳的交互脚本（从 docs/demo-内容页外壳.html 的内联脚本切出）
   ---------------------------------------------------------------------------
   与 static/preview-shell.html 配套；由该页用 <script src="/js/xk-app.js" defer> 引入。
   本次修复（对照第一段审计表）：
     · 删掉「背景选择器」全部脚本（BGS / setBg / shadeRange / skin-toggle / bgBtn /
       bgPicker / 手机样式切换）—— 站主要求"真的删"，标记与样式也一起删。
       这一块原来就是脚本最前面的 59 行，它是"取不到元素就抛 TypeError"的源头，
       会让后面的头像播放器根本不执行（= 面板头像空白的直接原因之一）。
     · 所有 demo-assets/ 路径改成站点真实路径（头像走 /kurisu/avatar/、全身走 /kurisu/scene/）。
     · 头像帧数改成读 manifest 的真值（原来用 8*floor(atlasH/132) 反推，会把只有 3 帧的
       sided_thinking/happy/sad/blush/angry/disappointed 当成 8 帧，每轮多画 5 个空帧 = 闪烁）；
       并加 .static.webp 降级（单帧）。
     · 去掉文件尾部那段与 preview-shell.html 内联场景脚本重复的播放器（同一份逻辑两份实现）。
   ============================================================================ */
(function () {
  'use strict';

  var d = document;
  var RM = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ============ OPS-ROOM 作战室 ============ */
  var opsTabs = d.querySelectorAll('#opsTabs button');
  var opsPanes = d.querySelectorAll('.ops-tab');
  var opsTab = 'live';
  Array.prototype.forEach.call(opsTabs, function (b) {
    b.onclick = function () {
      opsTab = b.dataset.tab;
      Array.prototype.forEach.call(opsTabs, function (x) { x.classList.toggle('on', x === b); });
      Array.prototype.forEach.call(opsPanes, function (p) { p.classList.toggle('on', p.dataset.pane === opsTab); });
      if (opsTab === 'graph') startGraph();
      if (opsTab === 'stats') runCounters();
      if (opsTab === 'live') drawSpark();
    };
  });

  /* 实时攻击流 */
  var FEED = [
    ['ssh', '[SSH]', '密码猜测失败 root @ 45.155.x.x → 命中 cowrie-01'],
    ['ssh', '[SSH]', '暴力破解 12/12 组已尝试 → cowrie-01 全程记录'],
    ['ssh', '[SSH]', '会话建立：执行 uname -a、cat /etc/passwd → 已存回放'],
    ['scan', '[扫描]', '6379/tcp Redis 探测 → 引导至 sentinel 诱饵'],
    ['scan', '[扫描]', 'masscan 特征：单 IP 扫 200+ 端口 → 已限速留证'],
    ['web', '[WEB]', 'POST /wp-login.php 撞库 → dionaea-03 记录载荷'],
    ['web', '[WEB]', 'GET /.env 探测 → tanner 返回伪造配置'],
    ['iot', '[IoT]', 'Telnet 僵尸网络握手 → conpot 工控蜜罐'],
    ['iot', '[IoT]', 'Mirai 特征载荷 → 已进入样本库'],
    ['smb', '[SMB]', 'EternalBlue 探测 → honeytrap 已拦截'],
    ['dns', '[DNS]', '可疑 TXT 查询 → passiveDNS 已留证']
  ];
  var termFeed = d.getElementById('termFeed');
  var pad2 = function (n) { return String(n).padStart(2, '0'); };
  function feedLine() {
    var dt = new Date(), t = pad2(dt.getHours()) + ':' + pad2(dt.getMinutes()) + ':' + pad2(dt.getSeconds());
    var f = FEED[Math.floor(Math.random() * FEED.length)];
    var el = d.createElement('div');
    el.className = 'tl';
    el.innerHTML = '<span class="ts">' + t + '</span> <span class="tg ' + f[0] + '">' + f[1] + '</span> ' + f[2];
    termFeed.appendChild(el);
    while (termFeed.querySelectorAll('.tl').length > 12) termFeed.removeChild(termFeed.querySelector('.tl'));
  }
  var tcursor = d.createElement('div');
  if (termFeed) {
    for (var i = 0; i < 10; i++) feedLine();
    tcursor.innerHTML = '<span class="tcursor"></span>';
    termFeed.appendChild(tcursor);
    if (!RM) setInterval(function () {
      var mon = d.getElementById('v-monitor');
      if (mon && mon.classList.contains('on') && opsTab === 'live') { feedLine(); termFeed.appendChild(tcursor); }
    }, 1500);
  }

  /* 24h 时序 sparkline：线条从左到右画出 */
  var sparkDone = false;
  function drawSpark() {
    var c = d.getElementById('spark24'); if (!c) return;
    var dpr = Math.min(devicePixelRatio || 1, 2), w = c.clientWidth, h = 56;
    if (!w) return;
    c.width = w * dpr; c.height = h * dpr;
    var x = c.getContext('2d'); x.setTransform(dpr, 0, 0, dpr, 0, 0);
    var pts = [];
    for (var i = 0; i <= 48; i++) pts.push(h - 8 - Math.abs(Math.sin(i * 0.62)) * 26 - ((i * 7919) % 13));
    var line = function (upto) {
      x.beginPath();
      var n = Math.max(2, Math.ceil(pts.length * upto));
      for (var j = 0; j < n; j++) { var px = j / (pts.length - 1) * w; if (j === 0) x.moveTo(px, pts[j]); else x.lineTo(px, pts[j]); }
      x.strokeStyle = '#7FD4D8'; x.lineWidth = 1.6; x.stroke();
    };
    x.beginPath(); x.moveTo(0, h); pts.forEach(function (y, k) { x.lineTo(k / (pts.length - 1) * w, y); }); x.lineTo(w, h); x.closePath();
    x.fillStyle = 'rgba(127,212,216,.10)'; x.fill();
    if (RM || sparkDone) { line(1); return; }
    sparkDone = true;
    var t0 = performance.now(), dur = 1100;
    (function step(t) {
      var k = Math.min(1, (t - t0) / dur);
      x.clearRect(0, 0, w, h);
      x.beginPath(); x.moveTo(0, h); pts.forEach(function (y, j) { x.lineTo(j / (pts.length - 1) * w, y); }); x.lineTo(w, h); x.closePath();
      x.fillStyle = 'rgba(127,212,216,.10)'; x.fill();
      line(k);
      if (k < 1) requestAnimationFrame(step);
    })(t0);
  }
  drawSpark();

  /* 攻击图谱：攻击者 → 传感器，数据包流动动画 */
  var SENSORS = [['cowrie-01', 'SSH 蜜罐'], ['dionaea-03', '恶意软件捕获'], ['conpot', '工控蜜罐'], ['tanner', 'Web 蜜罐'], ['honeytrap', '低交互蜜罐'], ['sentinel', 'Redis 诱饵']];
  var ATTACKERS = ['45.155.x.x', '185.220.x.x', '91.240.x.x', '103.99.x.x', '198.51.x.x'];
  var graphStarted = false;
  function startGraph() {
    var c = d.getElementById('atkGraph'); if (!c || graphStarted) return;
    graphStarted = true;
    var dpr = Math.min(devicePixelRatio || 1, 2);
    var x = c.getContext('2d');
    var hits = SENSORS.map(function () { return 0; });
    var W = 0, H = 340;
    var resizeG = function () { W = c.clientWidth; c.width = W * dpr; c.height = H * dpr; x.setTransform(dpr, 0, 0, dpr, 0, 0); };
    resizeG(); addEventListener('resize', resizeG);
    var A = ATTACKERS.map(function (n, i) { return { n: n, fx: 0.09, fy: (i + 1) / (ATTACKERS.length + 1) }; });
    var S = SENSORS.map(function (s, i) { return { n: s[0], d: s[1], fx: 0.82, fy: (i + 1) / (SENSORS.length + 1) }; });
    var pk = [], last = 0;
    function frame(t) {
      requestAnimationFrame(frame);
      var mon = d.getElementById('v-monitor');
      if (opsTab !== 'graph' || !mon || !mon.classList.contains('on') || !W) return;
      x.clearRect(0, 0, W, H);
      x.font = '11px ui-monospace,Consolas,monospace';
      var pos = function (n) { return { x: n.fx * W, y: 26 + n.fy * (H - 60) }; };
      S.forEach(function (s) { var p = pos(s); x.textAlign = 'right'; x.fillStyle = 'rgba(210,203,189,.35)'; x.fillText(s.d, p.x - 16, p.y + 3); });
      if (!RM && t - last > 420 && pk.length < 22) { last = t; pk.push({ a: (Math.random() * A.length) | 0, s: (Math.random() * S.length) | 0, k: 0, sp: 0.006 + Math.random() * 0.009 }); }
      x.lineWidth = 1;
      pk.forEach(function (p) {
        var pa = pos(A[p.a]), ps = pos(S[p.s]);
        x.strokeStyle = 'rgba(210,203,189,.05)';
        x.beginPath(); x.moveTo(pa.x, pa.y); x.lineTo(ps.x, ps.y); x.stroke();
      });
      pk = pk.filter(function (p) {
        p.k += p.sp;
        var pa = pos(A[p.a]), ps = pos(S[p.s]);
        for (var j = 0; j < 5; j++) {
          var q = p.k - j * 0.02;
          if (q < 0) break;
          x.fillStyle = 'rgba(232,180,90,' + (0.85 - j * 0.16) + ')';
          x.beginPath(); x.arc(pa.x + (ps.x - pa.x) * q, pa.y + (ps.y - pa.y) * q, 2.6 - j * 0.35, 0, 7); x.fill();
        }
        if (p.k >= 1) { hits[p.s]++; return false; }
        return true;
      });
      A.forEach(function (a) {
        var p = pos(a);
        x.fillStyle = '#E8837B'; x.beginPath(); x.arc(p.x, p.y, 5, 0, 7); x.fill();
        x.fillStyle = 'rgba(210,203,189,.85)'; x.textAlign = 'left'; x.fillText(a.n, p.x + 12, p.y + 3);
      });
      S.forEach(function (s, i) {
        var p = pos(s);
        x.fillStyle = '#7FD4D8'; x.beginPath(); x.arc(p.x, p.y, 6, 0, 7); x.fill();
        x.fillStyle = 'rgba(127,212,216,.25)'; x.beginPath(); x.arc(p.x, p.y, 10 + Math.sin(t / 300 + i) * 2, 0, 7); x.fill();
        x.fillStyle = '#7FD4D8'; x.textAlign = 'left'; x.fillText(s.n, p.x + 14, p.y - 2);
        x.fillStyle = 'rgba(210,203,189,.8)'; x.fillText(String(hits[i]), p.x + 14, p.y + 11);
      });
    }
    requestAnimationFrame(frame);
  }

  /* ATT&CK 矩阵（中文版） */
  var TACTICS = [
    ['TA0043', '侦察'], ['TA0042', '资源开发'], ['TA0001', '初始访问'], ['TA0002', '执行'],
    ['TA0003', '持久化'], ['TA0004', '权限提升'], ['TA0005', '防御规避'], ['TA0006', '凭据访问'],
    ['TA0007', '发现'], ['TA0008', '横向移动'], ['TA0009', '收集'], ['TA0011', '指挥控制'],
    ['TA0010', '渗出'], ['TA0040', '影响']
  ];
  var TACTIC_HITS = { 3: 9, 8: 4, 11: 6, 9: 2, 1: 12, 13: 1 };
  var attkGrid = d.getElementById('attkGrid');
  if (attkGrid) {
    TACTICS.forEach(function (t, i) {
      var hit = TACTIC_HITS[i] || 0;
      var cell = d.createElement('div');
      cell.className = 'cell' + (hit >= 6 ? ' fire' : hit > 0 ? ' hot' : '');
      cell.innerHTML = '<b>' + t[1] + '</b><span class="taid">' + t[0] + '</span><div class="num">' + hit + '</div>';
      attkGrid.appendChild(cell);
    });
  }

  /* 数据统计：数字滚动 */
  var counted = false;
  function runCounters() {
    if (counted) return; counted = true;
    Array.prototype.forEach.call(d.querySelectorAll('[data-count]'), function (el) {
      var T = +el.dataset.count;
      if (RM) { el.textContent = T.toLocaleString(); return; }
      var t0 = performance.now(), dur = 900;
      (function step(t) {
        var k = Math.min(1, (t - t0) / dur);
        el.textContent = Math.round(T * (1 - Math.pow(1 - k, 3))).toLocaleString();
        if (k < 1) requestAnimationFrame(step);
      })(t0);
    });
  }

  /* ============ HOLO 面板头像（动图） ============
     ★ 站主点名的第一处 bug：面板头像空白。
     两处原因都修掉：
       ① 路径 —— demo 写的是 demo-assets/<情绪>.{idle,speaking}.webp，这些文件从来没进仓库；
          真实素材在 /kurisu/avatar/<情绪>.{idle,speaking,static}.webp（8 情绪 × 3 = 24 个，全在）。
       ② 帧数 —— demo 用 COLS*floor(atlasH/CELL) 反推，只有 3 帧的图集会被当成 8 帧播，
          每轮多出 5 个空帧（头像一闪一闪变白）。这里直接写 manifest 里的真值。
     规则（站主指定）：待机循环 <emo>.idle.webp；说话切 <emo>.speaking.webp；降级 <emo>.static.webp。
     下面 frames / interval 抄自 static/kurisu/manifest.json 的 emotions.*（没有改字段名，只是读值固化；
     若哪天 manifest 变了，改这张表即可）。 */
  var AV_CELL = 132, AV_COLS = 8, AV_BASE = '/kurisu/avatar/';
  var EMOS = {
    normal:          { idle: { frames: 21, iv: 120 }, speaking: { frames: 49, iv: 42 } },
    sided_thinking:  { idle: { frames: 3,  iv: 170 }, speaking: { frames: 62, iv: 41 } },
    sided_surprised: { idle: { frames: 3,  iv: 170 }, speaking: { frames: 37, iv: 41 } },
    happy:           { idle: { frames: 3,  iv: 170 }, speaking: { frames: 37, iv: 41 } },
    blush:           { idle: { frames: 3,  iv: 170 }, speaking: { frames: 62, iv: 41 } },
    angry:           { idle: { frames: 3,  iv: 170 }, speaking: { frames: 37, iv: 41 } },
    sad:             { idle: { frames: 3,  iv: 170 }, speaking: { frames: 49, iv: 42 } },
    disappointed:    { idle: { frames: 3,  iv: 170 }, speaking: { frames: 3,  iv: 170 } }
  };
  function stripUrl(emo, kind) { return AV_BASE + emo + '.' + kind + '.webp'; }
  function stripInfo(emo, kind) {
    var spec = (EMOS[emo] || EMOS.normal)[kind] || (EMOS[emo] || EMOS.normal).idle;
    /* 上限保护：帧数不可能超过图集里真实存在的格子（1016/132 = 8 行） */
    return { src: stripUrl(emo, kind), frames: Math.min(spec.frames, AV_COLS * 8), iv: spec.iv };
  }

  function makePlayer(canvas) {
    if (!canvas) return { set: function () {} };
    var ctx = canvas.getContext('2d');
    var cache = {};
    var cur = null, frames = 1, iv = 120, fi = 0, last = 0;
    function img(src) { if (!cache[src]) { var im = new Image(); im.src = src; cache[src] = im; } return cache[src]; }
    function set(emo, kind) {
      var info = stripInfo(emo, kind);
      var key = info.src;
      if (cur === key) return;
      cur = key; frames = info.frames; iv = info.iv; fi = 0;
      var im = img(info.src);
      var useStatic = function () {
        var st = stripUrl(emo, 'static');
        if (cur !== key) return;
        cur = key = st; frames = 1; iv = 0;
        var s = img(st);
        var go2 = function () { if (cur === st) draw(0); };
        if (s.complete && s.naturalWidth) go2(); else s.onload = go2;
      };
      var ready = function () {
        if (cur !== key) return;
        if (!im.naturalWidth) { useStatic(); return; }
        draw(0);
      };
      if (im.complete && im.naturalWidth) ready(); else { im.onload = ready; im.onerror = useStatic; }
    }
    function draw(i) {
      var im = img(cur);
      if (!im || !im.complete || !im.naturalWidth) return;
      ctx.clearRect(0, 0, AV_CELL, AV_CELL);
      if (frames <= 1) { ctx.drawImage(im, 0, 0, AV_CELL, AV_CELL, 0, 0, AV_CELL, AV_CELL); return; }
      ctx.drawImage(im, (i % AV_COLS) * AV_CELL, Math.floor(i / AV_COLS) * AV_CELL, AV_CELL, AV_CELL, 0, 0, AV_CELL, AV_CELL);
    }
    function tick(t) {
      if (cur && frames > 1 && !RM && t - last > iv) { fi = (fi + 1) % frames; draw(fi); last = t; }
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
    return { set: set };
  }
  var panelAv = makePlayer(d.getElementById('avCanvas'));
  var bubbleAv = makePlayer(d.getElementById('bubbleCanvas'));

  /* 手机里的她：全身剪辑，与 CRT 同源（用 /kurisu/scene/ 下已拷进来的那 4 段图集，
     这样与 preview-shell.html 内联场景脚本共用同一份 HTTP 缓存，不重复下载） */
  var BODY = {
    idle:     { src: '/kurisu/scene/idle.hi.webp',     frames: 60, interval: 42 },
    speaking: { src: '/kurisu/scene/speaking.hi.webp', frames: 90, interval: 34 },
    thinking: { src: '/kurisu/scene/thinking.hi.webp', frames: 90, interval: 34 }
  };
  function makeBodyPlayer(canvas) {
    if (!canvas) return { set: function () {} };
    var ctx = canvas.getContext('2d');
    var CW = 321, CH = 432, COLS = 8;
    canvas.width = CW; canvas.height = CH;
    var cache = {};
    var cur = null, frames = 1, fi = 0, last = 0, iv = 42;
    function img(src) { if (!cache[src]) { var im = new Image(); im.src = src; cache[src] = im; } return cache[src]; }
    function set(clip) {
      if (cur === clip.src) return;
      cur = clip.src; frames = clip.frames; iv = clip.interval; fi = 0;
      var im = img(cur);
      var ready = function () { if (cur !== clip.src) return; draw(0); };
      if (im.complete && im.naturalWidth) ready(); else im.onload = ready;
    }
    function draw(i) {
      var im = img(cur);
      if (!im || !im.complete || !im.naturalWidth) return;
      ctx.clearRect(0, 0, CW, CH);
      ctx.drawImage(im, (i % COLS) * CW, Math.floor(i / COLS) * CH, CW, CH, 0, 0, CW, CH);
    }
    function tick(t) {
      if (cur && frames > 1 && !RM && t - last > iv) { fi = (fi + 1) % frames; draw(fi); last = t; }
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
    return { set: set };
  }
  var phoneBody = makeBodyPlayer(d.getElementById('phoneCanvas'));
  var phoneEl = d.getElementById('phone');
  var phoneLineEl = d.getElementById('phoneLine');
  var phoneStateEl = d.getElementById('phoneState');
  /* 手机时间（演示用真实时钟） */
  function tickClock() {
    var el = d.getElementById('phoneClock'); if (!el) return;
    var dt = new Date();
    el.textContent = String(dt.getHours()).padStart(2, '0') + ':' + String(dt.getMinutes()).padStart(2, '0');
  }
  tickClock(); setInterval(tickClock, 20000);

  /* ============ 面板状态 ============ */
  var holo = d.getElementById('holo');
  var stateEl = d.getElementById('holoState');
  var sayEl = d.getElementById('holoSay');
  var emo = 'normal', mode = 'speaking', speakTimer = null;
  /* 手机里的她是**懒载**的：.phone 只存在于 AI 页，而它的全身图集 idle.hi 有 1.3MB。
     之前 render() 在首屏就给它 set()，等于主页白下 1.3MB（实测首屏 2.4MB，超硬预算 1.5MB）。
     现在只有 AI 视图真的可见时才喂它。 */
  function phoneActive() {
    var v = d.getElementById('v-ai');
    return !!(v && v.classList.contains('on'));
  }
  /* 面板头像是**懒载**的：home 视图 `body.xk-app-home .holo{display:none}` 把面板藏了，
     ai 视图也藏（她活在手机里）。看不见的元素没必要在首屏拉 87~189KB 的头像图集。
     切到监测中心/笔记/靶场/关于时 render() 会被再调一次，那时才载。 */
  function panelActive() {
    return !(d.body.classList.contains('xk-app-home') || d.body.classList.contains('xk-app-ai'));
  }
  function render() {
    var kind = mode === 'speaking' ? 'speaking' : 'idle';
    if (panelActive()) {
      panelAv.set(emo, kind);
      bubbleAv.set(emo, 'idle');
    }
    if (phoneActive()) {
      phoneBody.set(BODY[mode === 'speaking' ? 'speaking' : (emo === 'sided_thinking' ? 'thinking' : 'idle')]);
    }
    var label = mode === 'speaking' ? 'SPEAKING' : (emo === 'sided_thinking' ? 'THINKING' : 'IDLE');
    if (stateEl) stateEl.textContent = label;
    if (phoneStateEl) phoneStateEl.textContent = label;
    if (holo) holo.classList.toggle('live', mode === 'speaking' && !RM);
    if (phoneEl) phoneEl.classList.toggle('live', mode === 'speaking' && !RM);
  }
  function speak(html) {
    if (sayEl) sayEl.style.opacity = 0;
    if (phoneLineEl) phoneLineEl.style.opacity = 0;
    setTimeout(function () {
      if (sayEl) { sayEl.innerHTML = html; sayEl.style.opacity = 1; }
      if (phoneLineEl) { phoneLineEl.innerHTML = html; phoneLineEl.style.opacity = 1; }
    }, 150);
    mode = 'speaking'; render();
    clearTimeout(speakTimer);
    speakTimer = setTimeout(function () { mode = 'idle'; render(); }, 2600);
  }
  render();
  setTimeout(function () { mode = 'idle'; render(); }, 2600);
  var foldBtn = d.getElementById('holoFold');
  if (foldBtn) foldBtn.onclick = function () { d.body.classList.add('xk-app-holo-min'); };
  var bubble = d.getElementById('holoBubble');
  if (bubble) {
    var expand = function () { d.body.classList.remove('xk-app-holo-min'); };
    bubble.onclick = expand;
    bubble.onkeydown = function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); expand(); } };
  }
  Array.prototype.forEach.call(d.querySelectorAll('#emos b'), function (b) {
    var pick = function () {
      Array.prototype.forEach.call(d.querySelectorAll('#emos b'), function (x) { x.classList.remove('on'); });
      b.classList.add('on'); emo = b.dataset.emo; mode = 'idle'; render();
    };
    b.onclick = pick;
    b.onkeydown = function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } };
  });

  /* ============ 页面切换 ============
     状态类统一成 xk-app-*（挂在 <body> 上，避免 is-home / is-ai 这种通用名将来撞车） */
  var views = { home: 'v-home', monitor: 'v-monitor', ai: 'v-ai', notes: 'v-notes', range: 'v-range', about: 'v-about' };
  var SAYS = {
    home: '',
    monitor: '过去 24 小时拦截了 <span class="qk">96 次</span> 暴力破解，蜜罐记录了 <span class="qk">37 条</span> 交互。都在「监测中心」的大屏里。',
    ai: '有什么安全问题直接问我。答不了就说答不了。',
    notes: '这几篇都是真实实验记录，「Cowrie 观察」那篇最热闹。',
    range: '想试试攻击输入？点上面的一键样本，判定全部来自后端检测组件。',
    about: '这个站点的一切口径都在这一页：数据从哪来、什么能说什么不能说。'
  };
  function switchView(v) {
    Array.prototype.forEach.call(d.querySelectorAll('.view'), function (e) { e.classList.remove('on'); });
    var target = d.getElementById(views[v]);
    if (target) target.classList.add('on');
    Array.prototype.forEach.call(d.querySelectorAll('#dock button'), function (b) { b.classList.toggle('on', b.dataset.v === v); });
    d.body.classList.toggle('xk-app-home', v === 'home');
    d.body.classList.toggle('xk-app-ai', v === 'ai');
    render();   /* 进 AI 页才让手机播放器开始取全身图集（见 render 里的 phoneActive） */
    if (v === 'home') { if (window.__enterHome) window.__enterHome(); return; }
    if (v === 'monitor') {
      var mon = d.getElementById('v-monitor');
      if (mon && mon.classList.contains('on')) {
        if (opsTab === 'live') drawSpark();
        if (opsTab === 'graph') startGraph();
        if (opsTab === 'stats') runCounters();
      }
    }
    speak(SAYS[v]);
  }
  Array.prototype.forEach.call(d.querySelectorAll('#dock button'), function (b) {
    b.onclick = function () { switchView(b.dataset.v); };
  });

  /* ============ AI 问答演示 ============ */
  function askDemo() {
    var inp = d.getElementById('askInput'), log = d.getElementById('chatlog');
    if (!inp || !log) return;
    var q = inp.value.trim(); if (!q) return; inp.value = '';
    log.insertAdjacentHTML('beforeend', '<div class="msg me"></div>');
    log.lastElementChild.textContent = q;
    log.lastElementChild.scrollIntoView({ block: 'end' });
    emo = 'sided_thinking'; mode = 'idle'; render();
    if (stateEl) stateEl.textContent = 'THINKING';
    setTimeout(function () {
      var refuse = q.includes('昨天') || q.includes('谁打');
      log.insertAdjacentHTML('beforeend', refuse
        ? '<div class="msg ai"><div class="who">AI 安全 · <span class="st">规则解析（拒答）</span></div>这个问题需要内部事件数据，公开问答不取证 —— 可以去「监测中心」看脱敏后的真实统计。</div>'
        : '<div class="msg ai"><div class="who">AI 安全 · <span class="st">模型研判</span></div>（演示回答）这是知识库检索 + 模型生成的答案正文，引用卡片会列出标题、片段、可信度与来源性质。<div class="cite">引用：《演示文档》· 可信度 0.88</div></div>');
      log.lastElementChild.scrollIntoView({ block: 'end' });
      emo = 'normal';
      speak(refuse ? '拒答也是真实现：公开面不做事件取证。' : '回答生成了。引用与状态标注都在消息里，可展开核验。');
    }, 900);
  }
  var askBtn = d.getElementById('askBtn'), askInput = d.getElementById('askInput');
  if (askBtn) askBtn.onclick = askDemo;
  if (askInput) askInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') askDemo(); });

  /* ============ 靶场演示 ============ */
  var PG_DEMO = {
    '注入': '<div class="verdict"><span class="chip bad">命中</span>提示词注入防护：判定为越权指令，动作 = 拒绝执行并告警。</div>',
    'SQL': '<div class="verdict"><span class="chip warn">未命中 ≠ 无害</span>SQL 注入不属于输入扫描组件职责，判定仅供参考。</div>',
    '路径': '<div class="verdict"><span class="chip bad">命中</span>路径穿越净化：检测到目录越界模式，动作 = 净化后放行并记录。</div>',
    'AccessKey': '<div class="verdict"><span class="chip bad">命中</span>敏感信息扫描：匹配 AccessKey 样式，动作 = 打标 + 告警。</div>',
    '天气': '<div class="verdict"><span class="chip ok">未命中</span>三个组件均未命中。注意：未命中 ≠ 无害（后端 coverageWarning 常显）。</div>'
  };
  function runPg(text) {
    var box = d.getElementById('pgResult'); if (!box) return;
    var key = Object.keys(PG_DEMO).find(function (k) { return text.includes(k); }) || '天气';
    emo = 'sided_thinking'; render();
    if (stateEl) stateEl.textContent = 'THINKING';
    box.innerHTML = '<div class="verdict"><span class="chip">检测中…</span>输入已送往后端检测链路（演示为本地假结果）。</div>';
    setTimeout(function () {
      box.innerHTML = PG_DEMO[key] + '<div class="comp"><div class="hd"><span class="sev" style="background:var(--acc)"></span>PROMPT-GUARD · 适用</div><p>依据与动作由服务端返回，前端不拼内部标记名；接口不可用时如实显示"检测链路不可达"。</p></div>';
      emo = 'normal';
      speak('检测完成。记住：未命中不等于无害，判不了就说判不了。');
    }, 800);
  }
  var pgBtn = d.getElementById('pgBtn');
  if (pgBtn) pgBtn.onclick = function () {
    var el = d.getElementById('pgInput');
    var v = el ? el.value.trim() : '';
    if (v) runPg(v);
  };
  Array.prototype.forEach.call(d.querySelectorAll('.pgrun'), function (b) {
    b.onclick = function () {
      var el = d.getElementById('pgInput');
      if (el) el.value = b.dataset.pg;
      runPg(b.dataset.pg);
    };
  });
})();
