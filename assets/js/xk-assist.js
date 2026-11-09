/* ============================================================================
   xk-assist.js —— 全站右侧常驻助手「桐莉」（2026-11-09）
   ----------------------------------------------------------------------------
   面板标记在 layouts/partials/xk-demo/assistant.html 的 <template id="xk-assist-tpl"> 里
   （head-meta.html 是在 <head> 里被 include 的，直接把 aside 吐出来会把 <head> 提前关掉）。
   本脚本在 defer 阶段把模板 clone 到 body 末尾，然后接管：
     · 桌面（≥1180px）右侧常驻、主页介绍逐字打出（可点跳过）
     · 窄屏（<1180px）收成右下 44px 圆球，点开是 60vh 高的抽屉
     · 手动关闭写 localStorage['xk-assist-closed']（按路径记，本页以后不再自动展开）
     · localStorage['xk-assist-mode']='closed' 时全站默认收起，只留圆球
     · URL ?assist=0 本次收起（不写存储，刷新/点圆球即恢复）
   问答：站内已有的 POST /api/public/ask（同源，vercel.json 已反代）
     body  : {"q": "..."}          resp: {code,message,data:{answer,...}}
     答案只用 textContent 落 DOM（不拼 innerHTML）；剥掉 [EMO:x] 与「依据：N 条」行。
     失败分开说：429 限流 / 30s 超时 / 网络不可达 / 其它 HTTP 码。
   依赖：<template> + defer + fetch（无第三方库）。
   ========================================================================== */
(function () {
  'use strict';

  var tpl = document.getElementById('xk-assist-tpl');
  if (!tpl || !tpl.content || typeof document.body.appendChild !== 'function') return;
  document.body.appendChild(tpl.content.cloneNode(true));

  var root = document.getElementById('xk-assist');
  var fab = document.getElementById('xk-assist-fab');
  if (!root || !fab) return;

  var body = document.body;
  var path = root.getAttribute('data-path') || location.pathname;
  var intro = root.getAttribute('data-intro') || '';
  var say = root.querySelector('.xk-assist-say');
  var skip = root.querySelector('.xk-assist-skip');
  var form = root.querySelector('.xk-assist-form');
  var input = root.querySelector('.xk-assist-in');
  var go = root.querySelector('.xk-assist-go');
  var ans = root.querySelector('.xk-assist-ans');
  var bd = root.querySelector('.xk-assist-bd');
  var xBtn = root.querySelector('.xk-assist-x');
  if (!say || !form || !input || !go || !ans || !bd || !xBtn) return;

  var ASK_URL = '/api/public/ask';
  var ASK_TIMEOUT = 30000;                 /* 后端 deadlineMs≈25000，多给 5s */
  var ASK_MAX = 300;                       /* 输入框 maxlength 同口径 */
  var TICK = 42;                           /* 打字机速度：26 字约 1.1s */
  var reduce = false;
  try { reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  var narrow = false;
  try { narrow = window.matchMedia('(max-width:1179.98px)').matches; } catch (e) {}

  var chars = [], idx = 0, typeTimer = 0, typed = false;

  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  /* 本页是否被手动关过：新版存 {"<path>":1}；旧值 '1' 视为全站关过 */
  function closedHere() {
    var raw = lsGet('xk-assist-closed');
    if (!raw) return false;
    if (raw === '1') return true;
    try { return !!JSON.parse(raw)[path]; } catch (e) { return false; }
  }
  function markClosedHere() {
    var raw = lsGet('xk-assist-closed'), m = {};
    if (raw && raw !== '1') { try { m = JSON.parse(raw) || {}; } catch (e) { m = {}; } }
    m[path] = 1;
    lsSet('xk-assist-closed', JSON.stringify(m));
  }

  function setAria(on) { fab.setAttribute('aria-expanded', on ? 'true' : 'false'); }

  function finishTyping() {
    if (typeTimer) { clearTimeout(typeTimer); typeTimer = 0; }
    if (!chars.length) return;
    say.textContent = intro;
    say.classList.remove('is-typing');
    say.removeAttribute('title');
    skip.hidden = true;
    typed = true;
  }
  function step() {
    if (idx >= chars.length) { finishTyping(); return; }
    idx++;
    say.textContent = chars.slice(0, idx).join('');
    typeTimer = setTimeout(step, TICK);
  }
  function typeIntro() {
    if (typed || !intro) return;
    if (reduce) { finishTyping(); return; }
    chars = Array.from(intro);
    idx = 0;
    say.textContent = '';
    say.classList.add('is-typing');
    say.title = '点击跳过';
    skip.hidden = false;
    step();
  }

  function open(focusInput) {
    body.classList.remove('xk-assist-closed');
    body.classList.add('xk-assist-open');
    setAria(true);
    typeIntro();
    if (focusInput) setTimeout(function () { try { input.focus(); } catch (e) {} }, 60);
  }
  function close(mark) {
    body.classList.remove('xk-assist-open');
    body.classList.add('xk-assist-closed');
    setAria(false);
    finishTyping();
    if (mark) markClosedHere();
  }
  function isOpen() { return body.classList.contains('xk-assist-open'); }

  /* ---- 首屏状态 ------------------------------------------------------------
     · 桌面：默认展开；/ai/ 例外（那页右侧已有手机框，助手先收成圆球）
     · 窄屏：默认收起
     · ?assist=0 / mode=closed / 本页关过：收起 */
  var qs = '';
  try { qs = new URLSearchParams(location.search).get('assist') || ''; } catch (e) {}
  var offByUrl = qs === '0';
  var modeClosed = lsGet('xk-assist-mode') === 'closed';
  var isAi = body.classList.contains('is-ai');
  body.classList.add('xk-has-assist');

  if (!narrow && !offByUrl && !modeClosed && !closedHere() && !isAi) open(false);
  else close(false);

  /* ---- 交互 ------------------------------------------------------------- */
  fab.addEventListener('click', function () { open(true); });
  xBtn.addEventListener('click', function () { close(true); });
  say.addEventListener('click', function () { if (!typed) finishTyping(); });
  skip.addEventListener('click', finishTyping);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isOpen()) close(true);
  });

  /* ---- 问答 ------------------------------------------------------------- */
  function norm(s) { return String(s == null ? '' : s).replace(/[\s\u00a0]+/g, ' ').trim(); }
  function cleanAnswer(a) {
    var s = String(a == null ? '' : a);
    s = s.replace(/\[EMO:[a-z0-9_-]+\]/gi, '');
    s = s.replace(/(^|\n)[ \t]*依据：[ \t]*\d+[ \t]*条[ \t]*›?[ \t]*$/g, '');
    return s.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  }
  function fail(msg) {
    ans.hidden = false;
    ans.className = 'xk-assist-ans is-err';
    ans.textContent = msg;
    bd.scrollTop = bd.scrollHeight;
  }
  function reset() { go.disabled = false; input.disabled = false; }

  function ask() {
    var q = norm(input.value);
    if (!q) { try { input.focus(); } catch (e) {} return; }
    if (q.length > ASK_MAX) q = q.slice(0, ASK_MAX);
    go.disabled = true;
    input.disabled = true;
    ans.hidden = false;
    ans.className = 'xk-assist-ans';
    ans.textContent = '想一下…';

    var ctrl = (typeof AbortController === 'function') ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, ASK_TIMEOUT);
    var opts = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      cache: 'no-store',
      body: JSON.stringify({ q: q })
    };
    if (ctrl) opts.signal = ctrl.signal;

    fetch(ASK_URL, opts).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (b) {
        return { status: res.status, ok: res.ok, body: b };
      });
    }).then(function (r) {
      clearTimeout(timer);
      reset();
      if (r.status === 429) { fail('问得太快了，等一分钟再来。'); return; }
      if (!r.ok) { fail('接口回了 HTTP ' + r.status + '，这次没答上来。'); return; }
      if (!r.body) { fail('接口没有返回 JSON，这次没答上来。'); return; }
      var d = (r.body.data !== undefined && r.body.data !== null) ? r.body.data : r.body;
      var a = cleanAnswer(d && d.answer);
      if (!a) {
        var why = r.body.reason || r.body.message;
        fail('接口没给出正文' + (why ? '（' + norm(why).slice(0, 40) + '）' : '') + '。');
        return;
      }
      ans.className = 'xk-assist-ans';
      ans.textContent = a;
      bd.scrollTop = bd.scrollHeight;
    }, function (err) {
      clearTimeout(timer);
      reset();
      if (err && (err.name === 'AbortError' || err.timeout)) { fail('等了 30 秒还没回，待会儿再问。'); return; }
      fail('网络没接上，检查一下再问。');
    });
  }

  form.addEventListener('submit', function (e) { e.preventDefault(); ask(); });
})();
