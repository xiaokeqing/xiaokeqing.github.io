
/* 桐莉栖 · 头像卡（左上角）· 批次 A-①
   1) 声音开关：默认关；状态存 localStorage['xk-sound-on']；所有播放器统一读 window.__xkSound.on
   2) 登录：访客不渲染；隐蔽入口 ?admin=1 / #admin / 1.5s 内连点头像 5 次；绝不硬编码令牌
   3) 点头像 = 切下一个情绪 + 说一句；长按 >=500ms = 开面板（8 情绪 + 8 常用动作） */
(function () {
  'use strict';
  if (window.__xkId) { return; }
  var D = { sound: false, emo: 'normal', admin: false, loggedIn: false, panel: false, plays: 0, errors: [] };
  window.__xkId = D;
  function lg(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function ls(k, v) { try { localStorage.setItem(k, v); } catch (e) { } }
  function sg(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } }
  function ss(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { } }

  var EMOS8 = [
    ['normal', '普通', '/kurisu/avatar/normal.idle.webp'],
    ['happy', '开心', '/kurisu/avatar/happy.idle.webp'],
    ['sided_thinking', '思考', '/kurisu/avatar/sided_thinking.idle.webp'],
    ['sided_surprised', '惊讶', '/kurisu/avatar/sided_surprised.idle.webp'],
    ['sad', '难过', '/kurisu/avatar/sad.idle.webp'],
    ['blush', '害羞', '/kurisu/avatar/blush.idle.webp'],
    ['angry', '生气', '/kurisu/avatar/angry.idle.webp'],
    ['disappointed', '失望', '/kurisu/avatar/disappointed.idle.webp']
  ];
  /* 8 个常用动作 = static/kurisu/manifest.json 的 clipsMedium 里**真实存在**的剪辑名（不编名字 ✓） */
  var ACTS8 = [
    ['trans_standby', '待机待命'], ['trans_smile', '微笑'], ['thinking_trans', '思考入戏'],
    ['surprise_trans', '惊讶一下'], ['shy_trans', '害羞低头'], ['angry_trans', '生气'],
    ['sad_trans', '失落'], ['idle_closed_eye', '闭眼歇会儿']
  ];
  /* 固定台词表（口语版 · 入口 → 中文）。音轨文件与 lineId 一字不改；日语音轨仍是上一版录音，
     下一批重录时按这张表逐句重生成（见 docs/台词表-入口与固定台词-20261016.md）。 */
  var LINE_ZH = {
    /* ★2026-10-16 站主新口径：进站问候换成"欢迎使用 Amadeus 系统"那两句（音频为 GPT-SoVITS v3 新合成，见 bank.json）；
       旧的 greet_first / greet_back **保留**（新句子取不到时兜底，且它们的音轨仍是一字不改的老录音）。 */
    greet_welcome: '欢迎来到 XK-LAB。这个站分三块：监测中心看实时攻击和拦截记录，AI 问答查安全概念，笔记写这套系统怎么搭的。三个都不用登录。',
    greet_welcome_back: '欢迎回来。数据已经更新过了。',
    greet_first: '我是 Amadeus 助手。这个网站是干什么的，从上面四个入口看一圈就明白了。',
    greet_back: '又见面了。',
    nav_home: '这里是主页：左边四个入口，下面是最近更新的笔记。',
    nav_monitor: '监测中心：实时攻击流、威胁等级、攻击来源分布、蜜罐捕获的登录尝试，还有自动拦截记录。数字从后端直接读，取不到的地方会直接标出来。',
    nav_ai: 'AI 问答：可以问安全概念和防御做法，回答会附上出处。涉及站内事件数据的会直接拒答，这个面只解释公开知识。',
    nav_what: '介绍页：这是什么、能干什么，每个数字都标了来源。',
  nav_lab: '靶场在隔离网络里跑，口令进得去，别人打不开。',
  nav_notes: '笔记：这套系统怎么搭、怎么验证、哪里出过问题，都写在这里，每篇都带可核对的证据。',
    fallback_no_data: '这次没取到数据。不补数，读不到就是读不到。',
    fallback_offline: '请求没送达。我不编答案，等接口恢复再说。',
    fallback_throttled: '接口在限流，等一下再问。',
    tab_return: '你回来了。刚才我没说话，只是在这儿等着。'
  };
  window.__xkLineZh = LINE_ZH;
  var GROUP_OF = { greet_first: 'greeting', greet_back: 'greeting', tab_return: 'idle_banter',
    nav_home: 'page_intro', nav_monitor: 'page_intro', nav_ai: 'page_intro', nav_notes: 'page_intro',
    fallback_no_data: 'fallback', fallback_offline: 'fallback', fallback_throttled: 'fallback' };
  window.__xkLineGroup = GROUP_OF;   /* 统一播放器那边要用"这句属于哪个组"（与 bank 的 trigger 同源约定） */
  var EMO_LINE = { normal: 'nav_home', happy: 'greet_back', sided_thinking: 'nav_ai',
    sided_surprised: 'nav_monitor', sad: 'fallback_no_data', blush: 'greet_first',
    angry: 'fallback_throttled', disappointed: 'fallback_no_data' };

  var av = document.getElementById('xkIdAv'), cv = document.getElementById('xkIdAvCanvas');
  var cap = document.getElementById('xkIdCap'), panel = document.getElementById('xkIdPanel');
  var snd = document.getElementById('xkSndBtn'), login = document.getElementById('xkLoginBtn');
  if (!av || !cv || !cap || !panel || !snd || !login) { return; }

  /* ---------- 头像小播放器（132px 单元 · 8 列；只取用到的那个情绪的 idle 图） ----------
     ⚠ 帧数只取 **3**：manifest.json 里 emotions.*.idle 全是 {columns:8, frames:3, atlasW:1056}
     —— 图集是 8 列宽，但只有前 3 格有画面，后 5 格是空位；按"列数×行数"算会画到空位（实测：头像整块变白）。
     清单到位后（空闲预取那张）再用真值覆盖一次，防止以后素材改成 8 帧。 */
  var ctx = cv.getContext('2d'), CELL = 132, COLS = 8, framesOf = {}, imgs = {}, url = {}, last = 0, fi = 0;
  EMOS8.forEach(function (e) { url[e[0]] = e[2]; framesOf[e[0]] = 3; });
  function im(u) { if (!imgs[u]) { var i = new Image(); i.decoding = 'async'; i.src = u; imgs[u] = i; } return imgs[u]; }
  function paint() {
    var u = url[D.emo] || url.normal, g = im(u);
    if (!g.complete || !g.naturalWidth) { return; }
    var n = framesOf[D.emo] || 3;
    if (g.naturalWidth === CELL) { n = 1; }
    var k = n > 1 ? (fi % n) : 0;
    ctx.clearRect(0, 0, CELL, CELL);
    ctx.drawImage(g, (k % COLS) * CELL, Math.floor(k / COLS) * CELL, CELL, CELL, 0, 0, CELL, CELL);
  }
  (function tick(t) {
    requestAnimationFrame(tick);
    if (!last) { last = t; }
    if (t - last > 150) { last = t; fi++; paint(); }
  })(0);
  /* 头像图**立刻**开始取（首屏可见元素），并且不依赖 rAF 也一定能画上：
     实测 headless 下 rAF 有被节流的情况（截图里头像整块是底板色 #E8ECEF 的白方块）
     ⇒ 补一组"载入即画 + 几个时间点的兜底重画"。 */
  (function () {
    var g = im(url[D.emo]);
    if (g && g.addEventListener) { g.addEventListener('load', paint, { once: true }); }
    paint();
    [250, 700, 1500, 3000].forEach(function (ms) { setTimeout(paint, ms); });
  })();
  function setEmo(name) {
    if (!url[name]) { return false; }
    D.emo = name; fi = 0;
    var g = im(url[name]);
    if (g.complete && g.naturalWidth) { paint(); } else { g.addEventListener('load', paint, { once: true }); }
    markPanel();
    /* 主页：全身画布也一起切（那份状态机在主页内联脚本里；其它页没有 ⇒ 只动头像） */
    if (typeof window.xkmSetEmotion === 'function') { try { window.xkmSetEmotion(name); } catch (e) { D.errors.push('xkm: ' + e); } }
    return true;
  }

  /* ---------- 字幕条（只报真话：没出声就说没出声） ---------- */
  var capTimer = 0;
  function say(text) {
    cap.textContent = text;
    cap.classList.add('on');
    clearTimeout(capTimer);
    capTimer = setTimeout(function () { cap.classList.remove('on'); }, 7000);
  }
  /* 念一句：声音关着 ⇒ 只出字幕；开着 ⇒ 交给真正的语音层（统一播放器优先，其次是主页内联那份） */
  function speak(id, prefix, force) {
    var zh = LINE_ZH[id] || '';
    var head = prefix ? (prefix + ' —— ') : '';
    if (!D.sound && !force) { say(head + zh + '（声音默认关：点左下角「声音」才出声）'); return false; }
    var grp = GROUP_OF[id], ok = false;
    try {
      if (grp && window.KurisuPlayer && typeof window.KurisuPlayer.speakGroup === 'function') {
        var pr = window.KurisuPlayer.speakGroup(grp, { preferId: id });
        ok = true;
        if (pr && pr.then) {
          pr.then(function (r) {
            if (r && r.ok) { D.plays++; }
            else { D.errors.push('speak: ' + ((r && r.reason) || '?')); }
          });
        }
      } else if (typeof window.xkvPlay === 'function') { window.xkvPlay(id); ok = true; }
    } catch (e) { D.errors.push('speak: ' + e); }
    /* 没有任何语音层时只出字幕（**如实**记进 D.errors，不假装念过；音频在下一批接上） */
    if (!ok) { D.errors.push('no-voice-layer: ' + id); }
    say(head + zh);
    return ok;
  }

  /* ---------- 声音开关（默认关；访客可见） ---------- */
  function setSound(v, why) {
    D.sound = !!v;
    ls('xk-sound-on', D.sound ? '1' : '0');
    window.__xkSound = { on: D.sound, set: setSound, toggle: toggleSound };
    /* 开声 = 用户手势 ⇒ 这一刻必须保证统一播放器在位（按需加载那条） */
    if (D.sound) { loadPlayer(); }
    snd.textContent = D.sound ? '声音 开' : '声音 关';
    snd.setAttribute('aria-pressed', D.sound ? 'true' : 'false');
    snd.setAttribute('title', D.sound ? '声音：已打开（点一下关掉）' : '声音：已关闭（点一下打开）');
    try { window.dispatchEvent(new CustomEvent('xk-sound', { detail: { on: D.sound, why: why || 'btn' } })); } catch (e) { }
  }
  function toggleSound() { setSound(!D.sound, 'btn'); }
  snd.addEventListener('click', toggleSound);
  setSound(lg('xk-sound-on') === '1', 'restore');

  /* ---------- 场景光束开关（★2026-10-16 站主口径：光束保留，做成左上角头像旁的小功能）
     只切 `<html class="xk-lite">`；光束层样式与图在生成器的 BG_CSS（/kurisu/scene/bg/light_high.webp）；
     状态存 localStorage['xk-lite']；prefers-reduced-motion 下不淡入（BG_CSS 里已写）。 ---------- */
  var lite = document.getElementById('xkLiteBtn');
  function setLite(v, why) {
    D.lite = !!v;
    ls('xk-lite', D.lite ? '1' : '0');
    try { document.documentElement.classList.toggle('xk-lite', D.lite); } catch (e) { }
    if (lite) {
      lite.textContent = D.lite ? '光束 开' : '光束 关';
      lite.setAttribute('aria-pressed', D.lite ? 'true' : 'false');
      lite.setAttribute('title', D.lite ? '场景光束：已打开（点一下关掉）' : '场景光束：已关闭（点一下打开）');
    }
  }
  if (lite) { lite.addEventListener('click', function () { setLite(!D.lite, 'btn'); }); }
  setLite(lg('xk-lite') === '1', 'restore');

  /* ★批次 ③a（2026-10-16）· 自用令牌（判据、探针、降级、退出）—— 契约逐字见
     docs/落地上线-后端令牌登录与自用池-20261016.md §10。
     登录态**只认后端**：`GET {wb-api}/api/user/status` 返回 200 且 `data.loggedIn === true` 才算；
     localStorage 里有值只是"有一把待校验的令牌"，**不是**登录态。
     红线：① 令牌只进 `X-User-Token` 请求头，且只在目标是 wb-api 那个来源时才带；
           ② 不进 URL、不进 cookie、不打日志、不进任何产物；③ 本文件里没有任何令牌字面量 ✗。 */
  /* ★★ 2026-10-17 站主口径：登录改成「账号 + 密码」（只有站主能用；不开注册、不做多用户、不考虑别人）
     ---------------------------------------------------------------------------------------------
     入口：头像卡上那个 👤 按钮（默认可见 —— 站主原话"显示一下登录按键"）。
     契约（与后端 SecAgent 的 /api/auth 那一套对齐，实测 401/200 都通）：
       POST {apiBase}/api/auth/login   {username,password}
            → 200 {code:200,data:{token,expiresIn,username,role,roleLabel}}
            → 401 {code:401,message:"账号或密码错误"} ／ 429 限流
       GET  {apiBase}/api/auth/check   Authorization: Bearer <token>  → 200 才算登录态
       POST {apiBase}/api/auth/logout  Authorization: Bearer <token>
     纪律：① 密码只在这一次 POST 的请求体里出现，不落 localStorage、不进 URL、不打日志；
           ② 只把后端发的 token 存在 localStorage['xk-auth-token']；退出即删；
           ③ 令牌只发给 meta[name=wb-api] 那个来源（别的域一律不带）。
     登录后解锁（站主原话"让助手做所有动作和语音，主页的，自己选择"）：
       · 声音自动打开（只在这一刻自动开一次，之后仍可手动关）；
       · 情绪/动作面板、主页底部提问栏、以及所有台词与动作都放开（闸门仍是 __xkAdmin.allowed()）。
     --------------------------------------------------------------------------------------------- */
  var TOKEN_KEY = 'xk-user-token';    /* 旧「自用令牌」那套（/api/user/*）—— 保留，不动 */
  var AUTH_KEY = 'xk-auth-token';     /* 新的登录令牌（/api/auth/*） */
  var USER_KEY = 'xk-auth-user';
  var API_META = document.querySelector('meta[name="wb-api"]');
  function apiBase() { return ((API_META && API_META.getAttribute('content')) || '').replace(/\/+$/, ''); }
  /* 令牌的去向白名单：只有与 wb-api **同源**的 URL 才准带令牌 */
  function sameAsApi(u) {
    var b = apiBase(); if (!b) { return false; }
    try { return (new URL(u, location.href)).origin === (new URL(b, location.href)).origin; }
    catch (e) { return false; }
  }
  function userToken() { var t = lg(TOKEN_KEY); return (t && t.length) ? t : ''; }
  function authToken() { var t = lg(AUTH_KEY); return (t && t.length) ? t : ''; }
  function authUser() { return lg(USER_KEY) || ''; }
  var L10N = {
    title:    '站主登录',
    head:     '账号密码登录后才能用她的全部动作与语音（只有站主有账号）',
    userLb:   '账号',
    passLb:   '密码',
    wrong:    '账号或密码错误',
    throttled: '尝试过于频繁，请 N 秒后再试',
    offline:  '连不上服务，请稍后重试',
    ok:       '登录成功 —— 她的动作和语音都放开了。',
    bye:      '已退出登录：本机令牌已删除。'
  };
  var CID_KEY = 'xk-conversation-id';
  window.__xkL10N = L10N;
  window.__xkKeys = { token: TOKEN_KEY, auth: AUTH_KEY, cid: CID_KEY };
  var XL = window.__xkLogin = { state: 'anon', reason: 'notoken', status: 0, retryAfter: 0,
    checkedAt: 0, hasToken: false, role: '', username: '', errors: [], modal: false };
  function paintLogin() {
    var on = (XL.state === 'logged-in');
    D.loggedIn = on;
    login.setAttribute('aria-pressed', on ? 'true' : 'false');
    login.textContent = on ? '退出' : '登录';
    login.title = on ? ('已登录：' + (XL.username || '站主') + '（点一下退出）') : '登录（只有站主能登）';
  }
  /* ---------- 登录弹窗（动态建一次，之后复用） ---------- */
  var lbox = document.getElementById('xkLogin'), lbuilt = false;
  function buildLogin() {
    if (lbuilt || !lbox) { return; }
    lbuilt = true;
    lbox.innerHTML =
      '<form class="xk-login-card" id="xkLoginForm" autocomplete="on">' +
      '<h3>' + L10N.title + '</h3>' +
      '<p class="xk-login-hd">' + L10N.head + '</p>' +
      '<label for="xkLoginUser">' + L10N.userLb + '</label>' +
      '<input id="xkLoginUser" name="username" type="text" autocomplete="username" spellcheck="false" required>' +
      '<label for="xkLoginPass">' + L10N.passLb + '</label>' +
      '<input id="xkLoginPass" name="password" type="password" autocomplete="current-password" required>' +
      '<div class="xk-login-row"><button class="xk-login-sub" id="xkLoginSubmit" type="submit">登录</button>' +
      '<button class="xk-login-x" id="xkLoginCancel" type="button">取消</button></div>' +
      '<p class="xk-login-err" id="xkLoginErr" role="alert" aria-live="assertive"></p>' +
      '<p class="xk-login-who" id="xkLoginWho"></p>' +
      '</form>';
    var form = document.getElementById('xkLoginForm');
    var err = document.getElementById('xkLoginErr');
    document.getElementById('xkLoginCancel').addEventListener('click', closeLogin);
    lbox.addEventListener('click', function (ev) { if (ev.target === lbox) { closeLogin(); } });
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      submitLogin(err);
    });
  }
  function who() {
    var el = document.getElementById('xkLoginWho');
    if (!el) { return; }
    el.textContent = XL.state === 'logged-in'
      ? ('已登录：' + (XL.username || '站主') + (XL.role ? ('（' + XL.role + '）') : ''))
      : ('接口：' + (apiBase() || '未配置'));
  }
  function openLogin() {
    if (XL.state === 'logged-in') { logout(); return; }
    buildLogin();
    XL.modal = true;
    lbox.classList.add('open');
    who();
    var u = document.getElementById('xkLoginUser');
    if (u) { u.value = authUser(); setTimeout(function () { (u.value ? document.getElementById('xkLoginPass') : u).focus(); }, 30); }
    var e = document.getElementById('xkLoginErr'); if (e) { e.textContent = ''; }
  }
  function closeLogin() {
    XL.modal = false;
    if (lbox) { lbox.classList.remove('open'); }
    try { var p = document.getElementById('xkLoginPass'); if (p) { p.value = ''; } } catch (e) { }
  }
  function unlock() {
    /* ★2026-10-19 站主：「默认声音应该是关的」⇒ 登录**不再**替用户把声音打开。
       原来这里写着"站主的原话是让他们能做所有动作和语音"，于是登录一次就永久变成默认开声；
       现在只保留提示，声音开关完全由那颗按钮决定（状态仍存 localStorage['xk-sound-on']）。 */
    try { if (!D.sound) { say('已登录。声音仍是关的 —— 点「声音」才出声。'); } } catch (e) { }
    try { if (window.__xkAskBar && window.__xkAskBar.poke) { window.__xkAskBar.poke(); } } catch (e) { }
    try { openPanel(); } catch (e) { }
  }
  function submitLogin(errEl) {
    var u = (document.getElementById('xkLoginUser') || {}).value || '';
    var p = (document.getElementById('xkLoginPass') || {}).value || '';
    u = String(u).replace(/^\s+|\s+$/g, '');
    var base = apiBase();
    if (errEl) { errEl.textContent = ''; }
    if (!base) { if (errEl) { errEl.textContent = L10N.offline; } return; }
    if (!u || !p) { if (errEl) { errEl.textContent = '账号和密码都要填'; } return; }
    var btn = document.getElementById('xkLoginSubmit');
    if (btn) { btn.disabled = true; btn.textContent = '登录中…'; }
    XL.state = 'checking'; XL.checkedAt = Date.now();
    fetch(base + '/api/auth/login', {
      method: 'POST', cache: 'no-store', credentials: 'omit',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: u, password: p })
    }).then(function (r) {
      XL.status = r.status;
      var ra = parseInt(r.headers.get('Retry-After') || 0, 10) || 0;
      return r.json().catch(function () { return null; }).then(function (b) { return { s: r.status, b: b, ra: ra }; });
    }).then(function (x) {
      var b = x.b || {}, d = b.data || {};
      if (x.s === 200 && d.token) {
        try { localStorage.setItem(AUTH_KEY, String(d.token)); } catch (e) { }
        try { localStorage.setItem(USER_KEY, String(d.username || u)); } catch (e) { }
        XL.state = 'logged-in'; XL.reason = ''; XL.username = d.username || u; XL.role = d.roleLabel || d.role || '';
        paintLogin(); closeLogin(); unlock();
        say(L10N.ok); who();
        return;
      }
      if (x.s === 401) {
        XL.state = 'anon'; XL.reason = 'bad-credentials';
        if (errEl) { errEl.textContent = (b && b.message) || L10N.wrong; }
      } else if (x.s === 429) {
        XL.state = 'anon'; XL.reason = 'throttled'; XL.retryAfter = x.ra || 0;
        if (errEl) { errEl.textContent = L10N.throttled.replace('N', String(XL.retryAfter || 60)); }
      } else {
        XL.state = 'anon'; XL.reason = 'http-' + x.s;
        if (errEl) { errEl.textContent = '接口返回 HTTP ' + x.s + (b && b.message ? (' —— ' + b.message) : '') + '（没有登录成功）'; }
      }
      XL.errors.push(XL.reason);
      paintLogin();
    }).catch(function (e) {
      XL.state = 'anon'; XL.reason = String((e && e.message) || e);
      XL.errors.push(XL.reason);
      if (errEl) { errEl.textContent = L10N.offline; }
      paintLogin();
    }).then(function () {
      if (btn) { btn.disabled = false; btn.textContent = '登录'; }
    });
  }
  function probeAuth() {
    var base = apiBase(), t = authToken();
    XL.hasToken = !!t; XL.checkedAt = Date.now();
    if (!base || !t) { XL.state = 'anon'; XL.reason = t ? 'no-api-base' : 'notoken'; paintLogin(); return; }
    XL.username = authUser();
    fetch(base + '/api/auth/check', { headers: { 'Authorization': 'Bearer ' + t }, cache: 'no-store', credentials: 'omit' })
      .then(function (r) {
        XL.status = r.status;
        return r.json().catch(function () { return null; }).then(function (b) { return { s: r.status, b: b }; });
      })
      .then(function (x) {
        var d = (x.b && x.b.data) || {};
        if (x.s === 200) {
          XL.state = 'logged-in'; XL.reason = '';
          XL.username = d.username || XL.username; XL.role = d.roleLabel || d.role || XL.role;
        } else if (x.s === 401 || x.s === 403) {
          XL.state = 'anon'; XL.reason = 'token-invalid';
          try { localStorage.removeItem(AUTH_KEY); localStorage.removeItem(USER_KEY); } catch (e) { }
        } else {
          XL.state = 'anon'; XL.reason = 'HTTP ' + x.s;
        }
        paintLogin();
      })
      .catch(function (e) {
        XL.state = 'anon'; XL.reason = String((e && e.message) || e);
        XL.errors.push(XL.reason); paintLogin();
      });
  }
  function logout() {
    var t = authToken(), base = apiBase();
    if (t && base) {
      try {
        fetch(base + '/api/auth/logout', { method: 'POST', cache: 'no-store', credentials: 'omit',
          headers: { 'Authorization': 'Bearer ' + t } }).catch(function () { });
      } catch (e) { }
    }
    try { localStorage.removeItem(AUTH_KEY); localStorage.removeItem(USER_KEY); } catch (e) { }
    try { sessionStorage.removeItem(CID_KEY); } catch (e) { }
    XL.state = 'anon'; XL.reason = 'logout'; XL.status = 0; XL.role = ''; XL.username = '';
    paintLogin(); say(L10N.bye);
  }
  /* 隐深入口保留（?admin=1 / #admin / 连点头像 5 次）—— 现在按钮本来就可见，这里只是把状态位留着，
     免得旧链接/旧脚本引用 revealLogin 时炸掉。 */
  function revealLogin(why) { D.admin = true; D.revealWhy = why; }
  login.addEventListener('click', function () { openLogin(); });
  var emoBtn = document.getElementById('xkEmoBtn'), actBtn = document.getElementById('xkActBtn');
  if (emoBtn) { emoBtn.addEventListener('click', function () { openPanel(); markPanel(); }); }
  if (actBtn) { actBtn.addEventListener('click', function () { openPanel(); }); }
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && XL.modal) { closeLogin(); }
  });
  (function () {
    var q = /(^|[?&])admin=1(&|$)/.test(location.search);
    var hh = /#admin(\.|$|\/|\?)/.test(location.hash) || location.hash === '#admin';
    if (q || hh) { revealLogin(q ? 'url-query' : 'url-hash'); }
    if (authToken()) { revealLogin('stored-token'); }
  })();
  paintLogin();
  probeAuth();

  function withToken(h) {
    var o = h || {};
    var t = userToken();
    if (!t) { return o; }
    var out = {};
    for (var k in o) { if (Object.prototype.hasOwnProperty.call(o, k)) { out[k] = o[k]; } }
    out['X-User-Token'] = t;
    return out;
  }
  /* 登录后才有权限的东西：统一从这里走，未登录**不发请求**（站主追加②最后一条） */
  var admin = {
    userToken: userToken,
    allowed: function () { return !!(D.admin || D.loggedIn); },
    /* ⚠ 这里**不能**写 `this.allowed()`：调用方会把 fetch 拆出来当变量用
       （批次 ② 的输入栏就是 `var adminFetch = __xkAdmin.fetch`）⇒ this === undefined ⇒ TypeError（实测）。
       一律引用闭包里的 admin 对象。 */
    fetch: function (u, o) {
      if (!admin.allowed()) { return Promise.reject(new Error('ADMIN_ONLY')); }
      var opt = o || {};
      /* ★批次 ③a：令牌**只**发给 meta[name=wb-api] 那个来源（第三方域/CDN 一律不带）✗ */
      if (userToken() && sameAsApi(u)) { opt.headers = withToken(opt.headers); }
      return fetch(u, opt);
    },
    get: function (u) { return admin.fetch(u, { cache: 'no-store', credentials: 'omit' }); }
  };
  window.__xkAdmin = admin;

  /* ================= ★批次 ②：主页底部对话输入栏第 1 期 =================
     口径（照施工单，逐条）：
      1. 只在主页：SSR 标记在 body.is-home 上（其它四页没有）；这里再用路径判据兜一层；
      2. 显示条件 = __xkAdmin.allowed()；**未登录一个请求都不发**（整段在闸门后面）；
      3. 提交（Enter / 按钮同一条）→ POST {apiBase}/api/public/ask，body 只 {question}（≤600 字符）；
      4. 表情/动作只按响应里的 state / stateLabel（没有就 normal + 只字幕，绝不猜）；
      5. 🔊 默认关 ⇒ 只出字幕；开着才尝试统一播放器（闸门在 kurisu-player 的 playLine 那一处）；
      6. 失败/超时/额度照后端原话（HTTP 码 / Retry-After 倒计时 / quota.remaining），不补"像答案"的文字；
      7. 不做 SSE / WebSocket。
     ================= ★批次 ③b（2026-10-16）：登录后接**自用面** =================
     施工依据：docs/施工说明-前端自用面③b-20261016.md（主规格）+ 后端契约 §10（令牌面）。
       ① URL：`__xkLogin.state === 'logged-in'` ⇒ `POST /api/user/ask`；否则仍 `POST /api/public/ask`
          （**公开面行为一字不改**）。登录态**每次重取**（时序坑：__xkLogin 在另一个 IIFE 里赋值）。
       ② 多轮：`sessionStorage['xk-conversation-id']`（键名取自 `window.__xkKeys.cid`）；
          首句不带 id，拿到 `data.conversationId` 后存起来、后续请求带上；**退出登录一并清除**。
          body **只**允许 `{question, conversationId?}`（后端只认这两个键）。
       ③ 配额展示：`quota.remaining` 恒显示；自用面另显 `used/limit`；`softLimitReached=true` 时
          追加 §10.5-⑤ 文案且**输入框仍可用**（软上限只提醒、不硬停）。
       ④ 多轮进度：只报后端真值 `round / historyRounds / maxRounds`（公开面没有这些字段）。
       ⑤ 未生成：`state='model-failed'` 或 `generated=false` ⇒ 逐字显示「本次没有生成结论（模型或链路不可用）」
          —— **绝不把 answer 当结论渲染**。
       ⑥ 429 秒数三层兜底：响应头 `Retry-After` → 体 `retryAfter`/`data.retryAfter` → 默认 60（并如实披露）；
          `window.__xkAsk.retryLayer` 记录命中哪一层（探针断言用）。
       ⑦ 来源披露：自用面 `toolExecutionAllowed=true` 且后端 mock 默认开启 ⇒ 回答追加来源标注，
          不当真实值（主规格 §2 的安全提醒）。
       ⑧ 超时：自用面按后端 `limits.deadlineMs`（60000）+5s 取，不写死 20 秒（公开面仍 20s）。
       ⑨ 令牌纪律不变：一律经 `__xkAdmin.fetch`；只在 wb-api 同源时才带 `X-User-Token`。
     ⚠ 与 /ai/ 那个聊天框（#chatlog/#askInput，在 v-ai 那一屏里）**不是同一个东西**：本栏只挂主页，
        id 全部用 xkAsk* 前缀，靠这一点避免和 shell-script 的 xkPush/xkRenderAnswer 撞名。
     诊断：window.__xkAsk = {inited, allowed, state, status, ms, retryAfter, quota, errors, lastQuestionLen} */
  (function askBarSetup() {
    var bar = document.getElementById('xkAskBar');
    if (!bar) { return; }
    var D2 = window.__xkAsk = { inited: false, allowed: false, state: '', status: 0, ms: 0, retryAfter: 0,
      quota: null, errors: [], lastQuestionLen: 0,
      /* ★③b 新增诊断字段（探针用；不上屏）：self / url / sentCid / cid / round / historyRounds /
         toolExecutionAllowed / retryLayer / rateHits / timeoutMs */
      self: false, url: '', sentCid: '', cid: '', round: 0, historyRounds: 0,
      toolExecutionAllowed: false, retryLayer: '', rateHits: 0, timeoutMs: 0 };
    var onHome = false;
    try { onHome = document.body.classList.contains('is-home'); } catch (e) { }
    if (!onHome) {
      onHome = (location.pathname === '/' || /^\/index\.html?$/.test(location.pathname));
    }
    if (!onHome) { return; }                       /* 内容页：连驱动都不装（标记也在 CSS/条件里不显示） */
    /* ⚠ 两段式（实测踩过）：本 IIFE 跑在 `window.__xkAdmin` 赋值**之前**（它在偏件后面的"空闲预取"那一段）。
       所以：① 先按当前已存在的对象取一次并**建好** `adminApi`（fetch 允许被拆出来调用，内部不依赖 this）；
              ② 闸门判定放在下面，`poke()` 每次重取一次（隐蔽入口在本页加载后才打开时要用新对象）。 */
    var adminApi = (function () {
      var a = window.__xkAdmin;
      if (!a || typeof a.allowed !== 'function' || typeof a.fetch !== 'function') { return null; }
      return { allowed: a.allowed, fetch: a.fetch };
    })();
    var inp = document.getElementById('xkAskInput'), snd = document.getElementById('xkAskSend');
    var cnt = document.getElementById('xkAskCount');
    var wired = false;
    var META = document.querySelector('meta[name="wb-api"]');
    var API = ((META && META.getAttribute('content')) || '').replace(/\/+$/, '');
    var ASK_TIMEOUT = 20000, ASK_MAX = 600;
    /* ★③b：文案表**合并为一处**（§4 明确要求消除第二份会漂移的表）。
       与登录面共用 window.__xkL10N（③a 的五条契约文案）；此处只补**提问段独有**的四条。
       ⚠ 取不到共享表时（理论不会发生）保留兜底字面量，保证不出现 undefined 文案。 */
    var L = window.__xkL10N || {};
    var TXT = {
      notoken: L.notoken || '自用入口：请粘贴自用令牌（令牌只保存在本机浏览器，不会上传到别处）',
      invalid: L.invalid || '令牌无效或已轮换 —— 请向站主要一份新的自用令牌',
      disabled: L.disabled || '自用入口当前未启用（服务端未配置令牌）',
      throttled: L.throttled || '尝试过于频繁，请 N 秒后再试',
      soft: L.soft || '今日自用调用已达软上限 500 次，仍可继续使用（仅提醒，不限额）',
      offline: L.offline || '连不上服务，请稍后重试',
      /* ——— 以下为提问段独有 ——— */
      timeout: '等了 N 秒还没返回 —— 这次请求已放弃（不补推测答案）。',
      nofield: '这次后端没有给出 state / stateLabel —— 只出字幕，不猜她的表情。',
      /* ★③b §2：自用面 toolExecutionAllowed=true 且后端 mock 默认开启 ⇒ 展示来源时必须如实标注（不许当真实值） */
      nosrc: '（自用面：允许工具调用，指标或含模拟源 mock）',
      undisclosed: '（后端未给秒数，按限流窗口默认 60 秒）'
    };
    var ASK_EMO = { 'model': 'normal', 'rule-based': 'sided_thinking', 'input-insufficient': 'sided_thinking',
      'no-retrieval': 'sided_thinking', 'retrieval-failed': 'sided_thinking', 'model-failed': 'sided_thinking',
      'injection-blocked': 'sided_surprised' };
    /* ★唯一的闸门 —— 注意这里**不能 return**：挂钩 `window.__xkAskBar` 必须在任何情况下都存在，
       否则"本页加载之后才开隐蔽入口（5 次连点头像 / #admin）"这条路没有落点（浏览器实测踩过）。
       未登录 ⇒ 下面什么也不做：不摘 hidden、不绑监听、不发请求；由末尾的 poke() 统一执行判定。 */
    var shouldRun = !!(inp && snd && adminApi && adminApi.allowed());
    function labelOf(d) {
      if (d && d.stateLabel) { return String(d.stateLabel); }
      var st = (d && d.state) || '';
      var L = window.XK_STATE_LABEL;              /* 复用 shell-script 的那张表；没有就原样报 state */
      if (L && L[st] && L[st][0]) { return L[st][0]; }
      return st || '未识别状态';
    }
    function askSay(prefix, text) {
      clearInterval(D2._tick); D2._tick = 0;      /* 新字幕一来就停掉旧倒计时，避免两条消息互相盖（实测踩过） */
      say(prefix ? (prefix + ' —— ' + text) : text);
    }
    function shortAnswer(a) {
      var s = String(a == null ? '' : a).replace(/\s+/g, ' ').trim();
      if (!s) { return ''; }
      return s.length > 120 ? (s.slice(0, 120) + '…') : s;
    }
    function rem(d, self) {
      if (!(d && d.quota)) { return ''; }
      var q = d.quota, s = '';
      if (q.remaining != null) { s += ' 剩余 ' + q.remaining + ' 次'; }
      /* ★③b：自用池把 limit/used 一并报出（契约 §10.3 / §10.5-⑤ 的展示要求）；公开面口径不动 */
      if (self && q.limit != null && q.used != null) { s += '（本池 ' + q.used + '/' + q.limit + '）'; }
      if (self && q.softLimitReached) { s += ' · ' + TXT.soft; }   /* 软上限只提醒，不禁用输入框 */
      return s;
    }
    /* ★③b：多轮会话 id（只有自用面有）—— 键名复用共享出口，不重新定义字符串（§6） */
    function cidGet() {
      var K = (window.__xkKeys && window.__xkKeys.cid) || 'xk-conversation-id';
      try { return sessionStorage.getItem(K) || ''; } catch (e) { return ''; }
    }
    function cidSet(v) {
      var K = (window.__xkKeys && window.__xkKeys.cid) || 'xk-conversation-id';
      try { sessionStorage.setItem(K, String(v)); } catch (e) { }
    }
    /* ★③b：自用面的等待上限按后端 limits.deadlineMs（契约 60000）取，**不写死 20 秒**
       —— 公开面沿用 20s：自用池允许工具调用，20 秒会把合法答案掐掉。 */
    function selfTimeout() {
      var lim = null;
      try { lim = window.__xkLogin && window.__xkLogin.limits; } catch (e) { }
      var ms = Number((lim && lim.deadlineMs) || 60000);
      return Math.max(5000, ms + 5000);
    }
    function render(d, self) {
      var st = (d && d.state) || '';
      D2.state = st;
      D2.quota = (d && d.quota) || null;
      D2.self = !!self;
      D2.round = (d && d.round) || 0;
      D2.historyRounds = (d && d.historyRounds) || 0;
      D2.cid = (d && d.conversationId) || '';
      D2.toolExecutionAllowed = !!(d && d.toolExecutionAllowed === true);
      /* ★只按 state 驱动表情；状态→表现的真值表在服务端，这里只做"这一格该不该动"的映射 */
      var emo = ASK_EMO[st] || 'normal';
      setEmo(emo);
      var line = '', why = labelOf(d), tail = rem(d, self);
      /* ★③b：多轮进度（公开面没有 round/historyRounds 这些字段）—— 只报后端给的真值 */
      var turn = '';
      if (self && d && d.round != null) {
        turn = '（第 ' + d.round + ' 轮';
        if (d.maxRounds != null) { turn += ' / 上限 ' + d.maxRounds + ' 轮'; }
        if (d.historyRounds != null) { turn += '，已带上下文 ' + d.historyRounds + ' 轮'; }
        turn += '）';
      }
      /* ★③b §2：自用面 toolExecutionAllowed=true 且后端 mock 默认开启 ⇒ **如实标注来源**，不当真实值 */
      var src = (self && d && d.toolExecutionAllowed === true) ? (' ' + TXT.nosrc) : '';
      if (!d || !st) { line = TXT.nofield; }
      else if (d.generated === true && st === 'model') { line = '答完了' + turn + '（' + why + '）' + tail + '：' + shortAnswer(d.answer) + src; }
      else if (d.injection && d.injection.blocked) { line = '输入命中提示注入护栏（' + why + '）—— 我只把它当不可信数据，没执行它。'; }
      else if (st === 'rule-based') { line = '这条我不作答（' + why + '）—— 我不会为了"有回答"而编。'; }
      else if (st === 'input-insufficient' || st === 'no-retrieval') { line = '依据不足，我不给结论（' + why + '）。'; }
      else if (st === 'model-failed' || d.generated === false) {
        /* §5 补充（逐字）：本次没有生成结论 —— **不许**把 answer 当答案渲染 */
        line = '本次没有生成结论（模型或链路不可用）';
        if (d.failureReason) { line += ' —— 后端原话：' + shortAnswer(d.failureReason); }
        line += '。';
      }
      else { line = '这次没生成结论（' + why + '）。'; }
      /* ⚠ 顺序有讲究（实测踩过）：speak() 内部也会写字幕条 = 她的"台词"，
         所以必须**先 speak() 再 askSay()** —— 否则刚拿到的后端答案会被台词盖掉。 */
      speak(d.generated === true ? 'greet_back' : 'fallback_no_data', '', false);
      askSay('她的回答', line);
    }
    function fail(status, body, retryAfter) {
      D2.status = status;
      D2.retryAfter = parseInt(retryAfter || 0, 10) || 0;   /* 响应头是字符串（"7"）⇒ 诊断字段存整数 */
      var msg = (body && (body.message || (body.error && body.error.message))) || '';
      /* ★③b §5：N 的**三层兜底** —— ① `Retry-After` 响应头（跨域需后端 Expose 才读得到）
         ② 响应体 `retryAfter` / `data.retryAfter` ③ 默认 60（**并如实披露**"后端未给秒数"）
         注意：后端 `579cfe1` 之后头与体都给秒数；三层同时保留 ⇒ 幂等，且不会退化成"永远 60"。 */
      if (status === 429) {
        var hh = parseInt(retryAfter || 0, 10) || 0;
        var bb = parseInt((body && body.retryAfter) || 0, 10) || 0;
        var dd = parseInt((body && body.data && body.data.retryAfter) || 0, 10) || 0;
        var secs = hh || bb || dd || 0, disclosed = '';
        D2.retryLayer = hh ? 'header' : (bb ? 'body' : (dd ? 'data' : 'default'));
        if (!secs) { secs = 60; disclosed = ' ' + TXT.undisclosed; }
        D2.retryAfter = secs;
        D2.rateHits = (D2.rateHits || 0) + 1;
        var extra = (body && body.data && body.data.quota && body.data.quota.remaining != null)
          ? ('（剩余 ' + body.data.quota.remaining + ' 次）') : '';
        /* §6：把限流如实记到登录面（**不把 state 改成 throttled** —— 令牌仍然有效，
           若改了状态，下一次提问会静默切回公开池，与"自用面"口径冲突；这里只记原因与秒数） */
        try {
          var XLx = window.__xkLogin;
          if (XLx) { XLx.retryAfter = secs; XLx.lastAskState = 'throttled'; XLx.lastAskReason = (body && body.reason) || 'LOGIN_RATE_LIMITED'; }
        } catch (e) { }
        setEmo('normal');
        ticker(secs, (msg || '请求被限流。'), extra + disclosed);
        speak('fallback_throttled', '', false);
        return;
      }
      setEmo('normal');
      if (status === 401) {
        var reason = (body && (body.reason || (body.error && body.error.reason))) || '';
        D2.authReason = reason;
        try { var XL2 = window.__xkLogin; if (XL2) { XL2.lastAskState = 'bad-token'; XL2.lastAskReason = reason; } } catch (e) { }
        askSay('提问', (reason === 'USER_LOGIN_DISABLED') ? TXT.disabled : TXT.invalid);
      } else {
        try { var XL3 = window.__xkLogin; if (XL3) { XL3.lastAskState = 'offline'; } } catch (e) { }
        askSay('提问', '接口返回 HTTP ' + status + (msg ? (' —— ' + msg) : '') + '（不显示任何替代答案）。');
      }
      speak('fallback_no_data', '', false);
    }
    function ticker(secs, msg, extra) {
      var left = Math.max(1, Number(secs) || 0);
      clearInterval(D2._tick);
      function tick() {
        if (left <= 0) {
          clearInterval(D2._tick);
          askSay('提问', (msg || '请求被限流') + (extra || '') + ' —— 等待结束，可以重新提问了。');
          return;
        }
        askSay('提问', (msg || '请求被限流') + (extra || '') + ' —— 请稍后再试 ' + left + ' 秒。');
        left -= 1;
      }
      tick();
      D2._tick = setInterval(tick, 1000);
    }
    function ask() {
      var q = String(inp.value || '').trim();
      if (!q || D2.busy) { return; }
      if (q.length > ASK_MAX) { q = q.slice(0, ASK_MAX); }   /* 与后端 maxQuestionChars 同口径 */
      D2.lastQuestionLen = q.length;
      /* ★③b：登录态**每次重取**（时序坑：window.__xkLogin 在另一个 IIFE 里赋值，别在闭包外缓存）
         登录 ⇒ POST /api/user/ask（自用池 + 多轮）；未登录 ⇒ 原样 POST /api/public/ask（公开面口径不动） */
      var self = false;
      try { self = !!(window.__xkLogin && window.__xkLogin.state === 'logged-in'); } catch (e) { }
      var cid = cidGet();
      var url = API + (self ? '/api/user/ask' : '/api/public/ask');
      var payload = { question: q };
      if (self && cid) { payload.conversationId = cid; }     /* ★多轮：只有登录面有；body **只**这两个键 */
      var to = self ? selfTimeout() : ASK_TIMEOUT;
      D2.self = self; D2.sentCid = (self && cid) || ''; D2.url = url; D2.timeoutMs = to;
      D2.busy = true; snd.disabled = true;
      inp.value = ''; if (cnt) { cnt.textContent = '0/' + ASK_MAX; }
      setEmo('sided_thinking');
      askSay('提问', (self ? '正在走自用链路（自用池，可多轮追问）…' : '正在走公开检索链路…')
        + '（最多等 ' + Math.round(to / 1000) + ' 秒，不做流式）');
      var ctrl = (typeof AbortController === 'function') ? new AbortController() : null;
      var timer = setTimeout(function () { if (ctrl) { ctrl.abort(); } }, to);
      var t0 = Date.now();
      /* ★必须走 __xkAdmin.fetch：它负责"只在目标是 wb-api 同源时才带 X-User-Token"（③a 红线） */
      adminApi.fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        mode: 'cors', credentials: 'omit', cache: 'no-store',
        signal: ctrl ? ctrl.signal : undefined,
        body: JSON.stringify(payload)
      }).then(function (res) {
        clearTimeout(timer);
        var status = res.status, ra = res.headers.get('Retry-After');
        return res.json().catch(function () { return null; }).then(function (body) {
          D2.ms = Date.now() - t0; D2.status = status;
          if (!res.ok) { fail(status, body, ra); return; }
          var d = (body && body.data !== undefined) ? body.data : null;
          if (!d) { fail(status, body, ra); return; }
          /* ★③b：把后端回的 conversationId 存起来 ⇒ 下一句自动带上（多轮） */
          if (self && d.conversationId) { cidSet(d.conversationId); }
          render(d, self);
        });
      })['catch'](function (err) {
        clearTimeout(timer);
        D2.ms = Date.now() - t0;
        setEmo('normal');
        if (err && err.name === 'AbortError') { askSay('提问', TXT.timeout.replace('N', String(Math.round(to / 1000)))); }
        else { D2.errors.push('ask: ' + (err && err.message ? err.message : err)); askSay('提问', TXT.offline); }
        speak('fallback_offline', '', false);
      }).then(function () { D2.busy = false; snd.disabled = false; });
    }
    function wire() {
      if (wired) { return; }                        /* 幂等：poke 可能被反复调用 */
      wired = true;
      snd.addEventListener('click', ask);
      inp.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); ask(); }
      });
      inp.addEventListener('input', function () {
        if (cnt) { cnt.textContent = inp.value.length + '/' + ASK_MAX; }
      });
    }
    /* 挂钩**先于**闸门挂上：给 revealLogin()（5 次连点头像 / #admin）一个落点。
       本函数只做"判定 + 摘 hidden + 绑监听"，未登录时一律返回 false、什么都不动。 */
    function poke() {
      var a = window.__xkAdmin;                     /* 每次重取：__xkAdmin 在本偏件后面才赋值（实测踩过） */
      if (a && typeof a.allowed === 'function' && typeof a.fetch === 'function') {
        adminApi = { allowed: a.allowed, fetch: a.fetch };
      }
      var ok = !!(adminApi && adminApi.allowed() && inp && snd); D2.allowed = ok;
      if (!ok) { return false; }
      bar.hidden = false; D2.inited = true; wire();
      return true;
    }
    window.__xkAskBar = {
      ask: ask, el: bar, api: API, TXT: TXT, poke: poke,
      allowed: function () { return !!D2.allowed; }
    };
    poke();
  })();

  /* ---------- 面板：8 情绪 + 8 常用动作 ---------- */
  function labelOf(n) { for (var i = 0; i < EMOS8.length; i++) { if (EMOS8[i][0] === n) { return EMOS8[i][1]; } } return n; }
  function labelOfAct(n) { for (var i = 0; i < ACTS8.length; i++) { if (ACTS8[i][0] === n) { return ACTS8[i][1]; } } return n; }
  function markPanel() {
    Array.prototype.forEach.call(panel.querySelectorAll('[data-emo]'), function (b) {
      b.className = (b.getAttribute('data-emo') === D.emo) ? 'xk-chip on' : 'xk-chip';
    });
  }
  (function buildPanel() {
    var h = ['<h4>情绪（点一下，她演出来）</h4><div class="xk-row">'];
    EMOS8.forEach(function (e) { h.push('<button type="button" class="xk-chip" data-emo="' + e[0] + '">' + e[1] + '</button>'); });
    h.push('</div><h4>常用动作</h4><div class="xk-row">');
    ACTS8.forEach(function (a) { h.push('<button type="button" class="xk-chip" data-act="' + a[0] + '">' + a[1] + '</button>'); });
    h.push('</div><p class="xk-note">动作名取自 manifest.json 里真实存在的剪辑；全身画布只在主页有，别的页只出字幕，不假装在演。</p>');
    h.push('<p class="xk-note">换情绪/动作只改表演；台词只播真实录音，取不到就只出字幕。</p>');
    h.push('<button type="button" class="xk-close" id="xkIdClose" aria-label="关闭面板">✕</button>');
    panel.innerHTML = h.join('');
    panel.addEventListener('click', function (ev) {
      var t = ev.target;
      if (!t || !t.getAttribute) { return; }
      if (t.id === 'xkIdClose') { closePanel(); return; }
      var emo = t.getAttribute('data-emo');
      if (emo) { setEmo(emo); speak(EMO_LINE[emo] || 'nav_home', '情绪：' + labelOf(emo)); return; }
      var act = t.getAttribute('data-act');
      if (act) {
        var can = (typeof window.xkmPlayClip === 'function');
        if (can) { try { window.xkmPlayClip(act, null); window.XK_ACT = null; } catch (e) { D.errors.push('act: ' + e); } }
        say('动作：' + labelOfAct(act) + (can ? '' : '（全身画布只在主页可见，这一页只出字幕）'));
      }
    });
  })();
  function openPanel() { panel.classList.add('open'); D.panel = true; cap.classList.remove('on'); markPanel(); }
  function closePanel() { panel.classList.remove('open'); D.panel = false; }

  /* ---------- 点头像：切下一个情绪 + 念一句；长按 >=500ms：开面板 ---------- */
  var pressTimer = 0, longDone = false, taps = [];
  function tapCount() {
    var t = Date.now();
    taps.push(t);
    taps = taps.filter(function (x) { return t - x <= 1500; });
    if (taps.length >= 5) { taps = []; revealLogin('avatar-5tap'); say('自用入口已打开：登录按钮在头像右边。'); }
  }
  function nextEmo() {
    var i = 0, k;
    for (k = 0; k < EMOS8.length; k++) { if (EMOS8[k][0] === D.emo) { i = k; } }
    var e = EMOS8[(i + 1) % EMOS8.length];
    setEmo(e[0]);
    speak(EMO_LINE[e[0]] || 'nav_home', '情绪：' + e[1]);
  }
  av.addEventListener('pointerdown', function () {
    longDone = false;
    clearTimeout(pressTimer);
    pressTimer = setTimeout(function () { longDone = true; openPanel(); }, 500);
  });
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(function (ev) {
    av.addEventListener(ev, function () { clearTimeout(pressTimer); });
  });
  av.addEventListener('click', function () {
    if (longDone) { longDone = false; return; }     /* 长按已经开过面板 ⇒ 这一次不算"切情绪" */
    tapCount();
    nextEmo();
  });
  av.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); tapCount(); nextEmo(); }
  });
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && D.panel) { closePanel(); } });

  /* ---------- 进入栏目 ⇒ 固定一句介绍（同栏目 10 分钟内不重复念） ---------- */
  var ENTRY_LINE = { home: 'nav_home', monitor: 'nav_monitor', notes: 'nav_notes', ai: 'nav_ai' };
  (function entry() {
    var p = location.pathname, name = '';
    if (/^\/ai/.test(p)) { name = 'ai'; }
    else if (/^\/alerts/.test(p)) { name = 'monitor'; }
    else if (/^\/posts/.test(p)) { name = 'notes'; }
    else if (p === '/' || /^\/index\.html$/.test(p)) { name = 'home'; }
    var id = ENTRY_LINE[name];
    if (!id) { return; }                       /* /test/ 等页没有固定介绍句 ⇒ 什么都不播 ✓ */
    var KEY = 'xk-nav-voice-at', last = 0, lastSec = '';
    try { var raw = sg(KEY); if (raw) { var o = JSON.parse(raw); last = o.at || 0; lastSec = o.section || ''; } } catch (e) { }
    if (lastSec === name && (Date.now() - last) < 10 * 60 * 1000) { return; }
    ss(KEY, JSON.stringify({ section: name, at: Date.now() }));
    var tries = 0;
    (function wait() {
      var hasVoice = (window.KurisuPlayer && typeof window.KurisuPlayer.speakGroup === 'function') || typeof window.xkvPlay === 'function';
      if (!hasVoice && ++tries < 40) { setTimeout(wait, 100); return; }
      speak(id, '', true);                     /* 入口句是"固定一句"：即使声音关着也先把字幕显示出来（force） */
    })();
  })();

  /* ---------- 统一播放器：按需加载（P1 ⑥） ----------
     站主口径：宿主页要加载 `/js/kurisu-player.js`（选句/防复读/包络/口型一处实现）。
     实测：这个 138KB 的脚本**放进首屏 1.5s 窗口会顶爆首屏门禁**（/ai/ 1639KB → 1786KB > 1650KB 预算，
     且站主明确"预算不许抬"）⇒ 改成**按需注入**：1800ms 之后（越过窗口）或"点开声音"这个用户手势那一刻。
     它在本页找不到 [data-xk-kurisu] 节点（本页不挂站点舞台）⇒ 只提供 KurisuPlayer.speakGroup，不碰 DOM。 */
  function loadPlayer() {
    /* ★全站关角色总开关（v4 §六#2 合规）：开关打开时不拉播放器（也就不会有角色/语音） */
    if (window.__xkNoKurisu) { return; }
    if (window.KurisuPlayer || D.playerAsked) { return; }
    D.playerAsked = true;
    D.playerAt = Math.round(performance.now());
    try {
      var s = document.createElement('script');
      s.src = '/js/kurisu-player.js';
      s.defer = true;
      document.head.appendChild(s);
    } catch (e) { D.errors.push('loadPlayer: ' + e); }
  }
  D.loadPlayer = loadPlayer;
  /* ★慢网减量（2026-10-16）：原来固定 `setTimeout(loadPlayer, 1800)` —— 正好落在首屏数据到达前后，
     59KB 的播放器与 HTML/API **抢同一条窄带**（真机：链路 3~6KB/s，它实测 11.9s 才到）。
     改为"**三选一先到即加载**"，把带宽先让给数据，同时保证她**最终一定出现**：
       ① 首个 `/api/public/**` 响应落地（数据先出，她随后到）
       ② 首次用户手势（pointerdown/keydown/touchstart）
       ③ 最迟 6000ms 兜底
     ⚠️ 不改播放器本体行为；若三条都不触发（无 API 且无交互的极端情况）仍由 ③ 兜住。 */
  var __xkPlayerArmed = false;
  function armPlayerLoad(why) {
    if (__xkPlayerArmed) { return; }
    __xkPlayerArmed = true;
    D.playerWhy = why;
    setTimeout(loadPlayer, 0);
  }
  D.armPlayerLoad = armPlayerLoad;
  try {
    if (typeof PerformanceObserver === 'function') {
      var __xkPO = new PerformanceObserver(function (list) {
        var es = list.getEntries();
        for (var i = 0; i < es.length; i++) {
          if (String(es[i].name).indexOf('/api/public/') >= 0) { armPlayerLoad('first-api-data'); return; }
        }
      });
      __xkPO.observe({ type: 'resource', buffered: true });
    }
  } catch (e) { D.errors.push('armPlayerLoad/PO: ' + e); }
  ['pointerdown', 'keydown', 'touchstart'].forEach(function (ev) {
    addEventListener(ev, function () { armPlayerLoad('gesture:' + ev); }, { once: true, passive: true });
  });
  setTimeout(function () { armPlayerLoad('deadline-6s'); }, 6000);

  /* ---------- P0-④：首屏优先 + 其余空闲预取 ----------
     站主原话："一打开网页，首先把整体的图片加载出来，按时间顺序，要展示的先显示；
     但是显示的同时把其他地方加载一下，这样不就快多了吗"。
     口径：
       · 首屏四个关键图各自由主页脚本按"出现顺序"decode() 完再生效（壁纸→背板→她首帧→字幕框）；
         壁纸另外在 <head> 里 preload + fetchpriority=high（只这一张抢带宽）。
       · 其余（角色清单 manifest.json / 视频清单 video-manifest.json / 语音 bank.json / 面板数据）
         一律**空闲预取**：最早 2000ms 之后才开始，且只登记 <link rel=prefetch>，绝不阻塞首屏
         （首屏门禁的口径是"导航后 1.5s 内请求到的资产" ⇒ 预取必须晚于这个窗口）。
       · 移动端 / saveData / deviceMemory<=4 ⇒ **只取首屏 + 当前栏目**，其余点了才取（省流量）。
       · 登录后才该加载的东西一律走 __xkAdmin.fetch（未登录直接拒，**不发请求**）。
     验收：首屏关键资源加载顺序表 + 首屏可交互时间 + 预取请求清单 = _shots/firstscreen-order.json */
  D.pref = {}; D.prefetch = [];
  D.prefetchOff = (function () {
    try { var c = navigator.connection; if (c && (c.saveData || /(^|-)2g$/.test(c.effectiveType || ''))) { return 'saveData/2g'; } } catch (e) { }
    try { if (navigator.deviceMemory && navigator.deviceMemory <= 4) { return 'deviceMemory<=4'; } } catch (e) { }
    try { if (matchMedia('(max-width:980px)').matches) { return 'narrow'; } } catch (e) { }
    return '';
  })();
  function idle(fn, ms) {
    if (typeof window.requestIdleCallback === 'function') { window.requestIdleCallback(fn, { timeout: ms }); }
    else { setTimeout(fn, ms); }
  }
  function prefetch(u) {
    if (D.pref[u]) { return; }
    D.pref[u] = 1; D.prefetch.push({ url: u, at: Math.round(performance.now()) });
    try {
      var l = document.createElement('link');
      l.rel = 'prefetch'; l.href = u; l.as = 'fetch'; l.crossOrigin = 'anonymous';
      document.head.appendChild(l);
    } catch (e) { D.errors.push('prefetch: ' + e); }
  }
  /* ★`window.__xkAdmin`（含 X-User-Token 走头）**已上移到登录那一段（paintLogin/probeLogin 那段）之后**定义 ——
     因为 askBarSetup() 就在那一段里读它（批次 ② 实测：放在这里会让闸门永远读不到 ⇒ 输入栏不出现）。
     本处保留一行指路注释，避免下一个接手的人再挪回来。 */
  setTimeout(function () {
    if (D.prefetchOff) { D.prefetchNote = '跳过空闲预取（' + D.prefetchOff + '：只取首屏 + 当前栏目）'; return; }
    idle(function () {
      /* ★ 2026-10-30：只有页面上真有角色画布时才预取这两份清单。
       实测 /posts/pki/ 下没有任何角色画布却白拉 manifest 68KB + video-manifest 20KB。 */
if(document.querySelector('[data-xk-kurisu-canvas],#xk-kurisu__canvas,#charCanvas,.xk-scene')){
  ['/kurisu/manifest.json', '/kurisu/video-manifest.json'].forEach(prefetch);
}
      /* ★2026-10-22：语音库 bank.json 145 KB **默认不预取**。
         站主口径（§22）是"声音默认关"，关着就一个音频字节都不该取；而这条预取在每页都跑，
         等于把 145 KB 白花在从不发声的访客身上（实测每页 wire 清单里都有它）。
         真正开声时 kurisu-player / xk-shell 自己会取（走 HTTP 缓存），一次不多一次不少。 */
      if (window.__xkSound && window.__xkSound.on === true) { prefetch('/kurisu/voice/bank.json'); }
    }, 1500);
  }, 2000);
  /* 清单到位后用**真值**覆盖头像帧数（只读；清单本来就在上面的空闲预取清单里 ⇒ 走缓存，不额外发请求） */
  setTimeout(function () {
    fetch('/kurisu/manifest.json', { cache: 'force-cache' }).then(function (r) { return r.json(); }).then(function (j) {
      var em = (j && j.emotions) || {};
      EMOS8.forEach(function (e) {
        var f = em[e[0]] && em[e[0]].idle && em[e[0]].idle.frames;
        if (f) { framesOf[e[0]] = f; }
      });
      paint();
    }).catch(function () { });
  }, 3200);

  /* 首访/回访的问候由主页内联播放器负责（greet_first / greet_back，固定不随机）——
     这里只把"入口句"这一步记进诊断，便于验收核对。 */
  D.entry = { path: location.pathname, at: Date.now() };
})();
