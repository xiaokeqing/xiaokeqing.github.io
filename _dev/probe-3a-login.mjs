/* ★批次 ③a 验收探针：自用令牌登录（前半）。
   用法：node _dev/probe-3a-login.mjs
   口径（逐条对应 docs/落地上线-后端令牌登录与自用池-20261016.md §10）：
     ① 访客：无令牌 ⇒ 不渲染 👤、**一个 /api/user/status 请求都不发**
     ② 粘贴框：?admin=1 → 点 👤 → window.prompt 收令牌 → localStorage['xk-user-token']，且请求头带 X-User-Token
     ③ 只有 200 且 data.loggedIn===true 才算登录态；401/429 一律不算
     ④ 五条降级文案逐字；坏令牌**不删** localStorage
     ⑤ 退出 = 本地删键
     ⑥ 令牌**只**发给 meta[name=wb-api]（demo.xiaokeqing.cn），别的来源一个字节都不带
     ⑦ 页面里不出现"已登录"字样（③b 之前）
   造响应：CDP Fetch 域拦 https://demo.xiaokeqing.cn/api/user/status（含 CORS 预检），离线也可确定性跑。
   输出：_shots/probe-3a-login.json + 控制台 PASS/FAIL */
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = 'F:\\7AAA\\AI\\blog';
const PUB = path.join(ROOT, 'public');
const OUT = path.join(ROOT, '_shots');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8841, CDP = 9391;
const API = 'https://demo.xiaokeqing.cn';
const PREFIX = '3a-';
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.webm': 'video/webm', '.woff2': 'font/woff2' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

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

const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-3a-'));
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
let CANNED = null;              /* { code, headers:{}, body:{} } */
let EXPOSE_RETRY = false;       /* 是否回 Access-Control-Expose-Headers: Retry-After（见 07 场景） */
let PROMPT_TEXT = '';           /* 下一次 prompt 里"粘贴"的内容 */
let CONFIRM_ACCEPT = true;
const dialogs = [];
const statusHits = [];          /* 每一次 /api/user/status 的请求头 */
const tokenSends = [];          /* 所有带 X-User-Token 的请求 */
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
    if (isStatus) statusHits.push({ method: req.method, url: req.url, headers: req.headers });
    const cors = [
      { name: 'access-control-allow-origin', value: BASE },
      { name: 'access-control-allow-methods', value: 'GET,POST,PUT,DELETE,OPTIONS' },
      { name: 'access-control-allow-headers', value: 'x-user-token,content-type' },
      { name: 'access-control-max-age', value: '0' }
    ];
    if (EXPOSE_RETRY) { cors.push({ name: 'access-control-expose-headers', value: 'Retry-After' }); }
    if (req.method === 'OPTIONS') {
      rpc('Fetch.fulfillRequest', { requestId: p.requestId, responseCode: 204, responseHeaders: cors, body: '' }).catch(() => { });
      return;
    }
    const c = CANNED || { code: 500, headers: {}, body: { code: 500 } };
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
  if (r && r.exceptionDetails) return { __err: (r.exceptionDetails.exception?.description || r.exceptionDetails.text || '').slice(0, 200) };
  return r && r.result ? r.result.value : null;
};
await rpc('Page.enable'); await rpc('Runtime.enable'); await rpc('Network.enable');
await rpc('Fetch.enable', { patterns: [{ urlPattern: '*demo.xiaokeqing.cn*', requestStage: 'Request' }] });

const SNAP = `(function(){
  var XL = window.__xkLogin || null, b = document.getElementById('xkLoginBtn');
  var r = b ? b.getBoundingClientRect() : null;
  var body = (document.body && document.body.innerText) || '';
  var html = document.documentElement.outerHTML || '';
  return {
    state: XL ? XL.state : null, reason: XL ? XL.reason : null, status: XL ? XL.status : null,
    retryAfter: XL ? XL.retryAfter : null, hasToken: XL ? XL.hasToken : null, softLimit: XL ? XL.softLimit : null,
    lsToken: (function(){ try { return localStorage.getItem('xk-user-token'); } catch(e){ return 'ERR'; } })(),
    btnHidden: b ? b.hidden : null, btnText: b ? b.textContent : null, btnTitle: b ? b.title : null,
    rect: r ? { x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2) } : null,
    cap: (document.getElementById('xkIdCap') || {}).textContent || '',
    hasLoginSuccessWord: html.indexOf('\\u5df2\\u767b\\u5f55') >= 0,
    askBarHidden: (function(){ var a = document.getElementById('xkAskBar'); return a ? !!a.hidden : null; })(),
    probe: body.length
  };
})()`;

async function scenario(name, opts) {
  const { token = null, url = '/', canned, click = false, promptText = '', confirmAccept = true, waitMs = 2600, exposeRetry = false } = opts;
  CANNED = canned;
  EXPOSE_RETRY = exposeRetry;
  statusHits.length = 0; tokenSends.length = 0; dialogs.length = 0; consoleMsgs.length = 0;
  PROMPT_TEXT = promptText; CONFIRM_ACCEPT = confirmAccept;
  await rpc('Page.navigate', { url: BASE + '/' });
  await sleep(320);
  await evalJs(`try{ localStorage.clear(); }catch(e){}${token ? `try{ localStorage.setItem('xk-user-token', ${JSON.stringify(token)}); }catch(e){}` : ''} 1`);
  await rpc('Page.navigate', { url: BASE + url });
  await sleep(1500);
  let clicked = null;
  if (click) {
    const s0 = await evalJs(SNAP);
    if (s0 && s0.rect) {
      await rpc('Input.dispatchMouseEvent', { type: 'mousePressed', x: s0.rect.x, y: s0.rect.y, button: 'left', clickCount: 1 });
      await rpc('Input.dispatchMouseEvent', { type: 'mouseReleased', x: s0.rect.x, y: s0.rect.y, button: 'left', clickCount: 1 });
      clicked = s0.rect;
    }
    await sleep(waitMs);
  } else {
    await sleep(waitMs - 1500 > 0 ? waitMs - 1500 : 0);
  }
  const s = await evalJs(SNAP);
  let shot = null;
  try {
    const png = await rpc('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    shot = PREFIX + name + '.png';
    fs.writeFileSync(path.join(OUT, shot), Buffer.from(png.data, 'base64'));
  } catch { }
  return { name, url, clicked, snap: s, shot, statusHits: statusHits.slice(), tokenSends: tokenSends.slice(), dialogs: dialogs.slice(), console: consoleMsgs.slice() };
}

const OK_BODY = { code: 200, message: 'success', data: { loggedIn: true, authenticated: true, pool: 'self', generatedAt: '2026-10-16 13:20:00',
  quota: { pool: 'self', softLimit: true, available: true, limit: 500, used: 37, remaining: 463, softLimitReached: false, storeFile: 'data/model-quota-self.json', note: '软上限' },
  conversation: { maxRounds: 5, ttlMinutes: 30 }, limits: { maxBodyChars: 4000, deadlineMs: 60000, maxTokens: 4000 }, note: '自用模式' } };

const runs = [];
runs.push(await scenario('01-visitor-no-token', { url: '/?xk-kurisu-mode=video', canned: { code: 200, body: OK_BODY } }));
runs.push(await scenario('02-admin-paste-bad-token', { url: '/?admin=1', click: true, promptText: 'wrong-token-wrong-token-wrong-token-xx',
  canned: { code: 401, body: { code: 401, message: '令牌无效', reason: 'TOKEN_INVALID' } } }));
runs.push(await scenario('03-401-user-login-disabled', { token: 't-abcdefghijklmnopqrstuvwxyz-0123',
  canned: { code: 401, body: { code: 401, message: '自用入口未启用（服务端未配置令牌）', reason: 'USER_LOGIN_DISABLED' } } }));
runs.push(await scenario('04-429-retry-after-header-exposed', { token: 't-abcdefghijklmnopqrstuvwxyz-0123', exposeRetry: true,
  canned: { code: 429, headers: { 'Retry-After': '7' }, body: { code: 429, message: '太频繁', reason: 'LOGIN_RATE_LIMITED' } } }));
runs.push(await scenario('04b-429-header-not-exposed-body-fallback', { token: 't-abcdefghijklmnopqrstuvwxyz-0123', exposeRetry: false,
  canned: { code: 429, headers: { 'Retry-After': '7' }, body: { code: 429, message: '太频繁', reason: 'LOGIN_RATE_LIMITED', retryAfter: 9 } } }));
runs.push(await scenario('05-200-loggedIn-true', { token: 't-abcdefghijklmnopqrstuvwxyz-0123', canned: { code: 200, body: OK_BODY } }));
const SOFT = JSON.parse(JSON.stringify(OK_BODY)); SOFT.data.quota.softLimitReached = true;
runs.push(await scenario('06-200-soft-limit', { token: 't-abcdefghijklmnopqrstuvwxyz-0123', canned: { code: 200, body: SOFT } }));
runs.push(await scenario('07-logout-deletes-key', { token: 't-abcdefghijklmnopqrstuvwxyz-0123', click: true, confirmAccept: true, canned: { code: 200, body: OK_BODY } }));

/* ---- 判定 ---- */
const checks = [];
const add = (name, ok, detail) => checks.push({ name, ok: !!ok, detail });
const r1 = runs[0], r2 = runs[1], r3 = runs[2], r4 = runs[3], r4b = runs[4], r5 = runs[5], r6 = runs[6], r7 = runs[7];
const getOf = (r) => (r.statusHits || []).find((h) => h.method === 'GET') || null;
add('① 访客：👤 不渲染（hidden=true）', r1.snap && r1.snap.btnHidden === true, JSON.stringify(r1.snap && r1.snap.btnHidden));
add('① 访客：一个 /api/user/status 都不发', r1.statusHits.length === 0, 'statusHits=' + r1.statusHits.length);
add('① 访客：一个带令牌的请求都没有', r1.tokenSends.length === 0, 'tokenSends=' + r1.tokenSends.length);
add('② 粘贴：点了 👤 出现 prompt', r2.dialogs.some((d) => d.type === 'prompt'), JSON.stringify(r2.dialogs.map((d) => d.type)));
add('② 粘贴：令牌进了 localStorage[xk-user-token]', r2.snap && r2.snap.lsToken === 'wrong-token-wrong-token-wrong-token-xx', String(r2.snap && r2.snap.lsToken));
const g2 = getOf(r2);
add('② 粘贴：GET 请求头带 X-User-Token（值=粘贴的原文）', !!g2 && Object.entries(g2.headers || {}).some(([k, v]) => k.toLowerCase() === 'x-user-token' && v === 'wrong-token-wrong-token-wrong-token-xx'), JSON.stringify(g2 && g2.headers));
add('② 预检：OPTIONS 声明了 x-user-token', (r2.statusHits.some((h) => h.method === 'OPTIONS' && String(h.headers['Access-Control-Request-Headers'] || '').toLowerCase().indexOf('x-user-token') >= 0)), JSON.stringify(r2.statusHits.map((h) => h.method)));
add('③ 401 ⇒ 不算登录态（state=bad-token）', r2.snap && r2.snap.state === 'bad-token', String(r2.snap && r2.snap.state));
add('④ 文案#2 逐字：令牌无效或已轮换', !!(r2.snap && r2.snap.cap.indexOf('令牌无效或已轮换 —— 请向站主要一份新的自用令牌') >= 0), JSON.stringify(r2.snap && r2.snap.cap));
add('④ 坏令牌**不删** localStorage', r2.snap && r2.snap.lsToken === 'wrong-token-wrong-token-wrong-token-xx', String(r2.snap && r2.snap.lsToken));
add('④ 文案#3 逐字：自用入口当前未启用（服务端未配置令牌）', !!(r3.snap && r3.snap.cap.indexOf('自用入口当前未启用（服务端未配置令牌）') >= 0), JSON.stringify(r3.snap && r3.snap.cap));
add('④ 文案#4 逐字 + N 取自响应头（后端 expose 了 Retry-After）', !!(r4.snap && r4.snap.cap.indexOf('尝试过于频繁，请 7 秒后再试') >= 0), JSON.stringify(r4.snap && { cap: r4.snap.cap, ra: r4.snap.retryAfter }));
add('④ 文案#4 逐字 + N 取自 body.retryAfter（后端**未** expose 头时的兜底）', !!(r4b.snap && r4b.snap.cap.indexOf('尝试过于频繁，请 9 秒后再试') >= 0), JSON.stringify(r4b.snap && { cap: r4b.snap.cap, ra: r4b.snap.retryAfter }));
add('③ 200+loggedIn:true ⇒ state=logged-in / 🔓', !!(r5.snap && r5.snap.state === 'logged-in' && r5.snap.btnText === '🔓'), JSON.stringify(r5.snap && { s: r5.snap.state, t: r5.snap.btnText }));
add('④ 文案#5 逐字：软上限仍可继续使用', !!(r6.snap && r6.snap.cap.indexOf('今日自用调用已达软上限 500 次，仍可继续使用（仅提醒，不限额）') >= 0), JSON.stringify(r6.snap && r6.snap.cap));
add('⑦ 页面里不出现"已登录"字样（探针跑到的每一页）', runs.every((r) => r.snap && r.snap.hasLoginSuccessWord === false), runs.map((r) => r.snap && r.snap.hasLoginSuccessWord).join(','));
add('⑤ 退出：本地删键', !!(r7.snap && !r7.snap.lsToken && r7.snap.state === 'anon'), JSON.stringify(r7.snap && { ls: r7.snap.lsToken, s: r7.snap.state }));
add('⑤ 退出：出现 confirm 且被接受', r7.dialogs.some((d) => d.type === 'confirm'), JSON.stringify(r7.dialogs.map((d) => d.type)));
const allTok = runs.flatMap((r) => r.tokenSends);
add('⑥ 令牌只发给 ' + API, allTok.length > 0 && allTok.every((t) => t.url.startsWith(API)), JSON.stringify([...new Set(allTok.map((t) => t.url))]));
add('⑥ 令牌没进任何别的来源', allTok.every((t) => t.url.indexOf(API) === 0), 'n=' + allTok.length);
add('console 0（阻断性）', runs.every((r) => r.console.filter((c) => c.startsWith('EXCEPTION') || c.startsWith('error')).length === 0), JSON.stringify(runs.map((r) => r.console.length)));

const pass = checks.filter((c) => c.ok).length;
const report = { at: new Date().toISOString(), api: API, base: BASE, checks, runs };
fs.writeFileSync(path.join(OUT, 'probe-3a-login.json'), JSON.stringify(report, null, 1), 'utf8');
for (const c of checks) { console.log((c.ok ? '  [PASS] ' : '  [FAIL] ') + c.name + (c.ok ? '' : '   << ' + c.detail)); }
console.log('\n③a 探针：' + pass + '/' + checks.length + ' PASS');
console.log('报告 →', path.join(OUT, 'probe-3a-login.json'));
try { ws.close(); } catch { }
try { child.kill(); } catch { }
server.close();
process.exit(pass === checks.length ? 0 : 1);
