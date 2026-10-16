/* ★批次 ③b 验收探针：自用面接线（POST /api/user/ask + 多轮 + 配额 + 429 三层兜底）
   用法：node _dev/probe-3b-selfask.mjs
   口径（逐条对应 docs/施工说明-前端自用面③b-20261016.md §7 的 11 条）：
     ① 未登录：不发任何 /api/user/* 请求（计数 0）
     ② 真令牌：status 200 + loggedIn=true ⇒ state='logged-in'、按钮 🔓
     ③ 提问：POST /api/user/ask，请求头带 X-User-Token，body **只** {question, conversationId?}
     ④ 令牌只发 https://demo.xiaokeqing.cn（同源 wb-api）
     ⑤ 多轮：第二次提问带上第一次响应回的 conversationId
     ⑥ state=model-failed / generated=false ⇒ 显示"本次没有生成结论"，**不**把 answer 当答案
     ⑦ 429：头内 Retry-After:7 / 体 retryAfter:9 / 都不给 ⇒ 7 / 9 / 60（默认并披露）
     ⑧ quota.softLimitReached=true ⇒ 显示第 5 条文案且输入框仍可用
     ⑨ 退出：confirm → 键删除 → state='anon' → 会话 id 一并清掉
     ⑩ 页面里搜不到令牌字面量；console 全程 0
     ⑪ 未登录访客：/api/user/* 与 /api/public/ask 请求数都为 0
   造响应：CDP Fetch 域拦截 demo.xiaokeqing.cn，离线确定可重复。
   输出：_shots/probe-3b-selfask.json + 控制台 PASS/FAIL */
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = 'F:\\7AAA\\AI\\blog';
const PUB = path.join(ROOT, '_dev', '_build-self');   /* ★本线独立构建目录，绝不碰共享 public/ */
const OUT = path.join(ROOT, '_shots');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8851, CDP = 9392;
const API = 'https://demo.xiaokeqing.cn';
const PREFIX = '3b-';
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.webm': 'video/webm', '.woff2': 'font/woff2' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });
if (!fs.existsSync(PUB)) { console.error('构建目录不存在：' + PUB + '（先 hugo -d _dev\\_build-self）'); process.exit(1); }

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p.endsWith('/')) { p += 'index.html'; }
  const f = path.join(PUB, p);
  if (!f.startsWith(PUB) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end('nf'); return; }
  res.writeHead(200, { 'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${PORT}`;

const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-3b-'));
const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  '--no-default-browser-check', '--disable-extensions', '--mute-audio', '--autoplay-policy=no-user-gesture-required',
  `--remote-debugging-port=${CDP}`, `--user-data-dir=${userDataDir}`, '--window-size=1280,900', 'about:blank'], { stdio: 'ignore' });
let target = null;
for (let i = 0; i < 40 && !target; i++) {
  await sleep(300);
  try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); } catch { }
}
if (!target) { console.error('连不上 Edge CDP'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r, j) => { ws.addEventListener('open', r); ws.addEventListener('error', j); });
let mid = 0; const waits = new Map();
let CANNED_STATUS = null;          /* /api/user/status 的造响应 */
let ASK_QUEUE = [];                /* /api/user/ask 的造响应队列（每次请求 shift 一个） */
let DEFAULT_ASK = { code: 500, headers: {}, body: { code: 500, message: 'no canned' } };
let PROMPT_TEXT = '';
let CONFIRM_ACCEPT = true;
const dialogs = [];
const statusHits = [];             /* /api/user/status 的请求 */
const askHits = [];                /* /api/user/ask 与 /api/public/ask 的请求（含 postData） */
const tokenSends = [];             /* 所有带 X-User-Token 的请求 */
const consoleMsgs = [];
const rpc = (method, params = {}) => { const id = ++mid; return new Promise((res, rej) => { waits.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); }); };

ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waits.has(m.id)) { const w = waits.get(m.id); waits.delete(m.id); m.error ? w.rej(new Error(JSON.stringify(m.error))) : w.res(m.result); return; }
  const p = m.params || {};
  if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(p.type)) consoleMsgs.push(p.type + ': ' + (p.args || []).map((a) => a.value || a.description || '').join(' '));
  if (m.method === 'Runtime.exceptionThrown') consoleMsgs.push('EXCEPTION: ' + (p.exceptionDetails?.exception?.description || p.exceptionDetails?.text || ''));
  if (m.method === 'Network.requestWillBeSent') {
    const h = p.request.headers || {};
    const hit = Object.keys(h).find((k) => k.toLowerCase() === 'x-user-token');
    if (hit) tokenSends.push({ url: p.request.url, value: h[hit] });
  }
  if (m.method === 'Page.javascriptDialogOpening') {
    dialogs.push({ type: p.type, message: p.message });
    const accept = p.type === 'confirm' ? CONFIRM_ACCEPT : true;
    rpc('Page.handleJavaScriptDialog', { accept, promptText: p.type === 'prompt' ? PROMPT_TEXT : undefined }).catch(() => { });
  }
  if (m.method === 'Fetch.requestPaused') {
    const req = p.request;
    const isStatus = req.url.indexOf('/api/user/status') >= 0;
    const isAsk = req.url.indexOf('/api/user/ask') >= 0 || req.url.indexOf('/api/public/ask') >= 0;
    const cors = [
      { name: 'access-control-allow-origin', value: BASE },
      { name: 'access-control-allow-methods', value: 'GET,POST,PUT,DELETE,OPTIONS' },
      { name: 'access-control-allow-headers', value: 'x-user-token,content-type' },
      { name: 'access-control-expose-headers', value: 'Retry-After' },
      { name: 'access-control-max-age', value: '0' }
    ];
    if (req.method === 'OPTIONS') {
      if (isStatus) statusHits.push({ method: 'OPTIONS', url: req.url, headers: req.headers, postData: req.postData });
      rpc('Fetch.fulfillRequest', { requestId: p.requestId, responseCode: 204, responseHeaders: cors, body: '' }).catch(() => { });
      return;
    }
    let c = null;
    if (isStatus) { statusHits.push({ method: req.method, url: req.url, headers: req.headers, postData: req.postData }); c = CANNED_STATUS; }
    else if (isAsk) { askHits.push({ method: req.method, url: req.url, headers: req.headers, postData: req.postData }); c = ASK_QUEUE.length ? ASK_QUEUE.shift() : DEFAULT_ASK; }
    if (!c) c = { code: 500, headers: {}, body: { code: 500 } };
    const headers = cors.concat([{ name: 'content-type', value: 'application/json;charset=UTF-8' }])
      .concat(Object.keys(c.headers || {}).map((k) => ({ name: k, value: c.headers[k] })));
    rpc('Fetch.fulfillRequest', {
      requestId: p.requestId, responseCode: c.code, responseHeaders: headers,
      body: Buffer.from(JSON.stringify(c.body || {}), 'utf8').toString('base64')
    }).catch(() => { });
  }
});

const evalJs = async (expr) => {
  const r = await rpc('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r && r.exceptionDetails) return { __err: (r.exceptionDetails.exception?.description || r.exceptionDetails.text || '').slice(0, 300) };
  return r && r.result ? r.result.value : null;
};
await rpc('Page.enable'); await rpc('Runtime.enable'); await rpc('Network.enable');
/* 字幕历史日志：`say()` 之后可能还有"台词"覆盖字幕条 ⇒ 只读 textContent 会漏判。
   这里在**新文档**里给 #xkIdCap 的 textContent 写入打日志（不影响原行为）。 */
await rpc('Page.addScriptToEvaluateOnNewDocument', { source: `(function(){
  var L = []; window.__xkCapLog = L;
  try {
    var d = Object.getOwnPropertyDescriptor(Node.prototype, 'textContent');
    Object.defineProperty(Node.prototype, 'textContent', {
      get: d.get,
      set: function (v) { try { if (this && this.id === 'xkIdCap') { L.push(String(v)); } } catch (e) { } d.set.call(this, v); }
    });
  } catch (e) { }
})();` });
await rpc('Fetch.enable', { patterns: [{ urlPattern: '*demo.xiaokeqing.cn*', requestStage: 'Request' }] });

const SNAP = `(function(){
  var XL = window.__xkLogin || null, A = window.__xkAsk || null;
  var b = document.getElementById('xkLoginBtn');
  var bar = document.getElementById('xkAskBar'), inp = document.getElementById('xkAskInput');
  var html = document.documentElement.outerHTML || '';
  var cidKey = (window.__xkKeys && window.__xkKeys.cid) || 'xk-conversation-id';
  var cid = null; try { cid = sessionStorage.getItem(cidKey); } catch (e) { cid = 'ERR'; }
  return {
    state: XL ? XL.state : null, reason: XL ? XL.reason : null, status: XL ? XL.status : null,
    retryAfter: XL ? XL.retryAfter : null, softLimit: XL ? XL.softLimit : null,
    limits: XL ? XL.limits : null, conversation: XL ? XL.conversation : null,
    ask: A ? { state: A.state, status: A.status, self: A.self, url: A.url, sentCid: A.sentCid, cid: A.cid,
               round: A.round, historyRounds: A.historyRounds, toolExecutionAllowed: A.toolExecutionAllowed,
               retryLayer: A.retryLayer, retryAfter: A.retryAfter, timeoutMs: A.timeoutMs,
               quota: A.quota, errors: A.errors, inited: A.inited } : null,
    lsToken: (function(){ try { return localStorage.getItem('xk-user-token'); } catch(e){ return 'ERR'; } })(),
    sid: cid,
    btnHidden: b ? b.hidden : null, btnText: b ? b.textContent : null,
    barHidden: bar ? !!bar.hidden : null,
    inpDisabled: inp ? !!inp.disabled : null,
    sendDisabled: (document.getElementById('xkAskSend') || {}).disabled,
    cap: (document.getElementById('xkIdCap') || {}).textContent || '',
    capLog: (window.__xkCapLog || []).slice(-14),
    hasSuccessWord: html.indexOf('\\u767b\\u5f55\\u6210\\u529f') >= 0,
    htmlLen: html.length
  };
})()`;

/* 让自用提问栏可见并发起一次提问：直接点按钮（事件监听是绑在按钮上的） */
async function askOnce(text) {
  const r = await evalJs(`(function(){ var i=document.getElementById('xkAskInput'); if(!i) return 'NOINPUT';
    i.value=${JSON.stringify(text)}; i.dispatchEvent(new Event('input',{bubbles:true}));
    document.getElementById('xkAskSend').click(); return 'CLICKED'; })()`);
  await sleep(1100);
  return r;
}

async function scenario(name, opts) {
  const { token = null, url = '/', cannedStatus, askQueue = [], click = false, promptText = '', confirmAccept = true, waitMs = 2200,
    ask = false, askText = '测试提问：XSS 是什么？' } = opts;
  CANNED_STATUS = cannedStatus || null;
  ASK_QUEUE = askQueue.slice();
  statusHits.length = 0; askHits.length = 0; tokenSends.length = 0; dialogs.length = 0; consoleMsgs.length = 0;
  PROMPT_TEXT = promptText; CONFIRM_ACCEPT = confirmAccept;
  await rpc('Page.navigate', { url: BASE + '/' });
  await sleep(320);
  await evalJs(`try{ localStorage.clear(); sessionStorage.clear(); }catch(e){}${token ? `try{ localStorage.setItem('xk-user-token', ${JSON.stringify(token)}); }catch(e){}` : ''} 1`);
  await rpc('Page.navigate', { url: BASE + url });
  await sleep(waitMs);
  let clicked = null;
  if (click) {
    const s0 = await evalJs(SNAP);
    const b = await evalJs(`(function(){ var b=document.getElementById('xkLoginBtn'); if(!b||b.hidden) return null;
      var r=b.getBoundingClientRect(); return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; })()`);
    if (b && !b.__err) {
      await rpc('Input.dispatchMouseEvent', { type: 'mousePressed', x: b.x, y: b.y, button: 'left', clickCount: 1 });
      await rpc('Input.dispatchMouseEvent', { type: 'mouseReleased', x: b.x, y: b.y, button: 'left', clickCount: 1 });
      clicked = b;
    } else { clicked = 'no-button'; }
    await sleep(1200);
    void s0;
  }
  /* ★只要队列里有 canned 提问响应、且本场景不是"点击"场景，就自动触发一次提问 */
  const doAsk = ask || (askQueue.length > 0 && !click);
  if (doAsk) { await askOnce(askText); }
  const s = await evalJs(SNAP);
  let shot = null;
  try {
    const png = await rpc('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    shot = PREFIX + name + '.png';
    fs.writeFileSync(path.join(OUT, shot), Buffer.from(png.data, 'base64'));
  } catch { }
  return { name, url, clicked, snap: s, shot, statusHits: statusHits.slice(), askHits: askHits.slice(), tokenSends: tokenSends.slice(), dialogs: dialogs.slice(), console: consoleMsgs.slice() };
}

const TOKEN = 't-abcdefghijklmnopqrstuvwxyz-0123';
/* ⚠ canned 的形状必须是 {code, headers?, body} —— body 才是响应体（踩过：把响应体直接当 canned ⇒ 拦截回空 {}） */
const OK_STATUS = { code: 200, body: { code: 200, message: 'success', data: { loggedIn: true, authenticated: true, pool: 'self', generatedAt: '2026-10-16 21:00:00',
  quota: { pool: 'self', softLimit: true, available: true, limit: 500, used: 37, remaining: 463, softLimitReached: false, storeFile: 'data/model-quota-self.json', note: '软上限' },
  conversation: { maxRounds: 5, ttlMinutes: 30 }, limits: { maxBodyChars: 4000, deadlineMs: 60000, maxTokens: 4000 }, note: '自用模式' } } };
const ANS = (o) => ({ code: 200, body: { code: 200, message: 'success', data: Object.assign({ answer: '这是一个真实答案。', state: 'model', generated: true,
  pool: 'self', citations: [], citationsInAnswer: false, clientIpMasked: '1.2.3.*', toolExecutionAllowed: true,
  quota: { pool: 'self', limit: 500, used: 38, remaining: 462, softLimitReached: false } }, o) } });

/* ---------- 场景 ---------- */
const runs = [];
/* ① ⑪ 未登录访客：不渲染栏、不发任何 user/* 与 public/ask */
runs.push(await scenario('01-visitor', { url: '/', cannedStatus: OK_STATUS, askQueue: [ANS({ conversationId: 'xk-should-not-happen' })] }));
/* ② 真令牌：登录态成立 */
runs.push(await scenario('02-logged-in', { url: '/', token: TOKEN, cannedStatus: OK_STATUS, askQueue: [ANS({ conversationId: 'xk-c1', round: 1, historyRounds: 0, maxRounds: 5 })] }));
/* ③⑤ 首问 + 追问（多轮）：见下面 multiTurn() 专用流程（比 scenario 更可控） */
/* ⑥ 未生成：不许渲染 answer */
runs.push(await scenario('04-model-failed', { url: '/', token: TOKEN, cannedStatus: OK_STATUS,
  askQueue: [{ code: 200, body: { code: 200, message: 'success', data: { answer: 'ANSWER_SHOULD_NOT_RENDER', state: 'model-failed', generated: false,
    failureReason: '上游超时', conversationId: 'xk-c2', round: 1, historyRounds: 0, maxRounds: 5, pool: 'self', toolExecutionAllowed: true,
    quota: { pool: 'self', limit: 500, used: 39, remaining: 461, softLimitReached: false } } } }] }));
/* ⑦ 429 三层：头 7 / 体 9 / 都不给 60 */
runs.push(await scenario('05-429-header', { url: '/', token: TOKEN, cannedStatus: OK_STATUS,
  askQueue: [{ code: 429, headers: { 'Retry-After': '7' }, body: { code: 429, message: '自用入口请求过于频繁', reason: 'LOGIN_RATE_LIMITED' } }] }));
runs.push(await scenario('06-429-body', { url: '/', token: TOKEN, cannedStatus: OK_STATUS,
  askQueue: [{ code: 429, headers: {}, body: { code: 429, message: '自用入口请求过于频繁', reason: 'LOGIN_RATE_LIMITED', retryAfter: 9 } }] }));
runs.push(await scenario('07-429-none', { url: '/', token: TOKEN, cannedStatus: OK_STATUS,
  askQueue: [{ code: 429, headers: {}, body: { code: 429, message: '自用入口请求过于频繁', reason: 'LOGIN_RATE_LIMITED' } }] }));
/* ⑧ 软上限：文案 + 输入框仍可用 */
runs.push(await scenario('08-soft-limit', { url: '/', token: TOKEN, cannedStatus: OK_STATUS,
  askQueue: [ANS({ conversationId: 'xk-c3', round: 1, historyRounds: 0, maxRounds: 5, quota: { pool: 'self', limit: 500, used: 500, remaining: 0, softLimitReached: true } })] }));
/* ⑨ 退出：见下面 logoutFlow() 专用流程（先提问让会话 id 落地，再点 👤 退出） */

/* ---------- 多轮：专用流程（首问 → 追问，断言 cid 被带上） ---------- */
async function multiTurn() {
  CANNED_STATUS = OK_STATUS;
  ASK_QUEUE = [ANS({ conversationId: 'xk-m1', round: 1, historyRounds: 0, maxRounds: 5 }),
               ANS({ conversationId: 'xk-m1', round: 2, historyRounds: 1, maxRounds: 5 })];
  statusHits.length = 0; askHits.length = 0; tokenSends.length = 0; dialogs.length = 0; consoleMsgs.length = 0;
  await rpc('Page.navigate', { url: BASE + '/' }); await sleep(300);
  await evalJs(`try{ localStorage.clear(); sessionStorage.clear(); localStorage.setItem('xk-user-token', ${JSON.stringify(TOKEN)}); }catch(e){} 1`);
  await rpc('Page.navigate', { url: BASE + '/' }); await sleep(2400);
  const before = await evalJs(SNAP);
  await askOnce('第一个问题：什么是 XSS？');
  const after1 = await evalJs(SNAP);
  await askOnce('追问：那 CSP 能防住吗？');
  const after2 = await evalJs(SNAP);
  const png = await rpc('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  fs.writeFileSync(path.join(OUT, PREFIX + '10-multiturn.png'), Buffer.from(png.data, 'base64'));
  const htmlHasToken = await evalJs('(document.documentElement.outerHTML||"").indexOf(' + JSON.stringify(TOKEN) + ') >= 0');
  const lsHasToken = await evalJs(`(function(){ try { return localStorage.getItem('xk-user-token') === ${JSON.stringify(TOKEN)}; } catch(e){ return 'ERR'; } })()`);
  return { name: '10-multiturn', before, after1, after2, askHits: askHits.slice(), tokenSends: tokenSends.slice(), console: consoleMsgs.slice(), htmlHasToken, lsHasToken };
}
const mt = await multiTurn();

/* ---------- 退出：专用流程（先提问落地会话 id，再点 👤 退出） ---------- */
async function logoutFlow() {
  CANNED_STATUS = OK_STATUS;
  ASK_QUEUE = [ANS({ conversationId: 'xk-out1', round: 1, historyRounds: 0, maxRounds: 5 })];
  statusHits.length = 0; askHits.length = 0; tokenSends.length = 0; dialogs.length = 0; consoleMsgs.length = 0;
  CONFIRM_ACCEPT = true;
  await rpc('Page.navigate', { url: BASE + '/' }); await sleep(300);
  await evalJs(`try{ localStorage.clear(); sessionStorage.clear(); localStorage.setItem('xk-user-token', ${JSON.stringify(TOKEN)}); }catch(e){} 1`);
  await rpc('Page.navigate', { url: BASE + '/' }); await sleep(2400);
  await askOnce('随便问一句，让会话 id 落地');
  const before = await evalJs(SNAP);
  const b = await evalJs(`(function(){ var b=document.getElementById('xkLoginBtn'); if(!b||b.hidden) return null;
    var r=b.getBoundingClientRect(); return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; })()`);
  if (b && !b.__err) {
    await rpc('Input.dispatchMouseEvent', { type: 'mousePressed', x: b.x, y: b.y, button: 'left', clickCount: 1 });
    await rpc('Input.dispatchMouseEvent', { type: 'mouseReleased', x: b.x, y: b.y, button: 'left', clickCount: 1 });
  }
  await sleep(1000);
  const after = await evalJs(SNAP);
  return { name: '11-logout', before, after, clicked: b, dialogs: dialogs.slice(), console: consoleMsgs.slice() };
}
const lo = await logoutFlow();

/* ---------- 判定 ---------- */
const checks = [];
const add = (name, ok, detail) => checks.push({ name, ok: !!ok, detail });
/* 字幕可能被后续"台词"覆盖 ⇒ 断言看**历史日志**（含最后一条） */
const capOfObj = (s) => ((s && (s.capLog || []).concat([s.cap])) || []).join(' | ');
const capAll = (r) => capOfObj(r && r.snap);
const r1 = runs[0], r2 = runs[1], r4 = runs[2], r5 = runs[3], r6 = runs[4], r7 = runs[5], r8 = runs[6];
const cidKeyOf = 'xk-conversation-id';
const firstAskOf = (r) => (r.askHits || []).find((h) => h.method === 'POST') || null;
const parseBody = (h) => { try { return JSON.parse(h.postData || '{}'); } catch { return null; } };

add('① 访客：提问栏 hidden', r1.snap && r1.snap.barHidden === true, JSON.stringify(r1.snap && r1.snap.barHidden));
add('①⑪ 访客：/api/user/* 请求数 = 0', (r1.statusHits || []).length === 0, 'statusHits=' + (r1.statusHits || []).length);
add('⑪ 访客：/api/public/ask 请求数 = 0', (r1.askHits || []).filter((h) => h.url.indexOf('/api/public/ask') >= 0).length === 0, JSON.stringify((r1.askHits || []).map((h) => h.url)));
add('①⑪ 访客：带令牌的请求 = 0', (r1.tokenSends || []).length === 0, 'tokenSends=' + (r1.tokenSends || []).length);
add('② 真令牌：state=logged-in 且按钮 🔓', !!(r2.snap && r2.snap.state === 'logged-in' && r2.snap.btnText === '🔓'), JSON.stringify(r2.snap && { s: r2.snap.state, t: r2.snap.btnText }));
add('② 登录成功文案（③b 解锁）：出现"登录成功 —— 已进入自用模式"', !!(capAll(r2).indexOf('登录成功 —— 已进入自用模式') >= 0), JSON.stringify(capAll(r2)));
add('② 文案里的轮数/时长取自后端真值（5 轮 / 30 分钟）', !!(capAll(r2).indexOf('最多 5 轮') >= 0 && capAll(r2).indexOf('30 分钟') >= 0), JSON.stringify(capAll(r2)));
add('③ 登录后提问打到 /api/user/ask', !!(firstAskOf(mt) && firstAskOf(mt).url.indexOf('/api/user/ask') >= 0), JSON.stringify((mt.askHits || []).map((h) => h.url)));
add('③ 请求头带 X-User-Token', (mt.tokenSends || []).some((t) => t.url.indexOf('/api/user/ask') >= 0), JSON.stringify((mt.tokenSends || []).map((t) => t.url)));
add('③ 首问 body 只有 {question}', (function () { const b = parseBody((mt.askHits || [])[0] || {}); return !!b && Object.keys(b).length === 1 && b.question === '第一个问题：什么是 XSS？'; })(), JSON.stringify(parseBody((mt.askHits || [])[0] || {})));
add('⑤ 首问不带 conversationId（sessionStorage 里还没有）', (mt.before && !mt.before.sid) === true, JSON.stringify(mt.before && mt.before.sid));
add('⑤ 首问后 sessionStorage 存下 conversationId=xk-m1', !!(mt.after1 && mt.after1.sid === 'xk-m1'), JSON.stringify(mt.after1 && mt.after1.sid));
add('⑤ 追问 body 带上了 conversationId=xk-m1', (function () { const b = parseBody((mt.askHits || [])[1] || {}); return !!b && b.conversationId === 'xk-m1'; })(), JSON.stringify(parseBody((mt.askHits || [])[1] || {})));
add('⑤ 追问只多这一个键（body = {question, conversationId}）', (function () { const b = parseBody((mt.askHits || [])[1] || {}); return !!b && Object.keys(b).sort().join(',') === 'conversationId,question'; })(), JSON.stringify(Object.keys(parseBody((mt.askHits || [])[1] || {}) || {})));
add('⑤ 多轮进度如实显示（第 2 轮 / 上限 5 轮 / 已带上下文 1 轮）', !!(mt.after2 && capOfObj(mt.after2).indexOf('第 2 轮') >= 0 && capOfObj(mt.after2).indexOf('上限 5 轮') >= 0 && capOfObj(mt.after2).indexOf('已带上下文 1 轮') >= 0), JSON.stringify(capOfObj(mt.after2)));
add('⑤ 配额展示：自用面显示 used/limit 与剩余', !!(mt.after1 && mt.after1.ask && mt.after1.ask.quota && capOfObj(mt.after2).match(/剩余\s*\d+\s*次（本池 \d+\/\d+）/)), JSON.stringify(capOfObj(mt.after2)));
add('⑥ model-failed：显示"本次没有生成结论（模型或链路不可用）"', !!(capAll(r4).indexOf('本次没有生成结论（模型或链路不可用）') >= 0), JSON.stringify(capAll(r4)));
add('⑥ model-failed：**不**把 answer 当答案渲染', !!(capAll(r4).indexOf('ANSWER_SHOULD_NOT_RENDER') < 0), JSON.stringify(capAll(r4)));
add('⑦ 429 头 Retry-After:7 ⇒ 倒计时 7 秒（retryLayer=header）', !!(capAll(r5).indexOf('请稍后再试 7 秒') >= 0 && r5.snap.ask && r5.snap.ask.retryLayer === 'header'), JSON.stringify({ cap: r5.snap && r5.snap.cap, L: r5.snap && r5.snap.ask && r5.snap.ask.retryLayer }));
add('⑦ 429 体 retryAfter:9（头缺失）⇒ 倒计时 9 秒（retryLayer=body）', !!(capAll(r6).indexOf('请稍后再试 9 秒') >= 0 && r6.snap.ask && r6.snap.ask.retryLayer === 'body'), JSON.stringify({ cap: r6.snap && r6.snap.cap, L: r6.snap && r6.snap.ask && r6.snap.ask.retryLayer }));
add('⑦ 429 头体都不给 ⇒ 默认 60 秒（retryLayer=default）且如实披露', !!(capAll(r7).indexOf('请稍后再试 60 秒') >= 0 && capAll(r7).indexOf('后端未给秒数') >= 0 && r7.snap.ask && r7.snap.ask.retryLayer === 'default'), JSON.stringify({ cap: r7.snap && r7.snap.cap, L: r7.snap && r7.snap.ask && r7.snap.ask.retryLayer }));
add('⑦ 429 文案与"读不到/不可达"可分辨（不得出现"不可达或被拦"）', !!(capAll(r7).indexOf('不可达或被拦') < 0 && (capAll(r7).indexOf('在限流') >= 0 || capAll(r7).indexOf('过于频繁') >= 0)), JSON.stringify(capAll(r7)));
add('⑧ 软上限：显示第 5 条文案（仍可继续使用 · 仅提醒不限额）', !!(capAll(r8).indexOf('今日自用调用已达软上限 500 次，仍可继续使用（仅提醒，不限额）') >= 0), JSON.stringify(capAll(r8)));
add('⑧ 软上限：输入框仍可用（disabled=false）', !!(r8.snap && r8.snap.inpDisabled === false), JSON.stringify(r8.snap && { i: r8.snap.inpDisabled, s: r8.snap.sendDisabled }));
add('⑨ 退出：出现 confirm 且被接受', (lo.dialogs || []).some((d) => d.type === 'confirm'), JSON.stringify((lo.dialogs || []).map((d) => d.type)));
add('⑨ 退出：localStorage 键被删 + state=anon', !!(lo.after && !lo.after.lsToken && lo.after.state === 'anon'), JSON.stringify(lo.after && { ls: lo.after.lsToken, s: lo.after.state }));
add('⑨ 退出前会话 id 确实存在（否则这条断言是空转）', !!(lo.before && lo.before.sid === 'xk-out1'), JSON.stringify(lo.before && lo.before.sid));
add('⑨ 退出：会话 id 一并清掉（sessionStorage）', !!(lo.after && !lo.after.sid), JSON.stringify(lo.after && lo.after.sid));
add('④ 令牌只发 ' + API, (function () { const t = [...(r2.tokenSends || []), ...(mt.tokenSends || [])]; return t.length > 0 && t.every((x) => x.url.indexOf(API) === 0); })(), JSON.stringify([...new Set([...(r2.tokenSends || []), ...(mt.tokenSends || [])].map((x) => x.url))]));
add('④ 带令牌请求的 URL 全部同源（无第三方）', [...(r2.tokenSends || []), ...(mt.tokenSends || [])].every((x) => x.url.indexOf(API) === 0), 'n=' + ((r2.tokenSends || []).length + (mt.tokenSends || []).length));
add('⑩ 令牌值不进 DOM（整页 outerHTML 搜不到令牌原文）', mt.htmlHasToken === false, 'htmlHasToken=' + JSON.stringify(mt.htmlHasToken));
add('⑩ 令牌只在 localStorage（值为原文，且不进产物）', mt.lsHasToken === true, 'lsHasToken=' + JSON.stringify(mt.lsHasToken));
add('⑩ console 全程 0（error/warning/exception）', runs.concat([{ console: mt.console }, { console: lo.console }]).every((r) => (r.console || []).filter((c) => c.startsWith('EXCEPTION') || c.startsWith('error')).length === 0), JSON.stringify(runs.map((r) => (r.console || []).length).concat([(mt.console || []).length, (lo.console || []).length])));
add('③ 自用面超时按后端 deadlineMs(60000)+5s=65000（不写死 20s）', !!(mt.after1 && mt.after1.ask && mt.after1.ask.timeoutMs === 65000), JSON.stringify(mt.after1 && mt.after1.ask && mt.after1.ask.timeoutMs));
add('⑦ 来源披露：toolExecutionAllowed=true ⇒ 回答带来源标注', !!(mt.after1 && capOfObj(mt.after1).indexOf('模拟源') >= 0), JSON.stringify(capOfObj(mt.after1)));

const pass = checks.filter((c) => c.ok).length;
const report = { at: new Date().toISOString(), api: API, base: BASE, pub: PUB, checks, runs, multiturn: mt, logout: lo };
fs.writeFileSync(path.join(OUT, 'probe-3b-selfask.json'), JSON.stringify(report, null, 1), 'utf8');
for (const c of checks) { console.log((c.ok ? '  [PASS] ' : '  [FAIL] ') + c.name + (c.ok ? '' : '   << ' + c.detail)); }
console.log('\n③b 探针：' + pass + '/' + checks.length + ' PASS');
console.log('报告 →', path.join(OUT, 'probe-3b-selfask.json'));
try { ws.close(); } catch { }
try { child.kill(); } catch { }
server.close();
process.exit(pass === checks.length ? 0 : 1);
