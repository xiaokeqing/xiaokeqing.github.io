/* ★批次 ② 取证：主页底部对话输入栏第 1 期
   用途：一次跑出"改后"证据链（截图 + 机器可读断言），口径与 _dev/gate-firstscreen.mjs 同一套
        （本机 http 服务 + Edge headless + CDP，只读 public/，不碰产物）。
   用法：node _dev/shot-batch-b-askbar.mjs [--prefix=batchB]
   输出：_shots/batchB-home-visitor-1280x900.png 等 PNG
        + _shots/batchB-askbar-report.json（每张图的 hidden / 可见性 / 请求数 / 字幕 / 诊断）

   本脚本回答四个问题（对应施工单 ② 的验收条）：
     ① 未登录访客：主页 DOM 里输入栏在不在？可见吗？**有没有发出任何一个 /api/public/ask 请求？**
     ② 开了隐蔽入口（?admin=1）：栏出现；点「提问」是否真的 POST、body 是不是只有 {question}、超长是否截到 600；
     ③ 响应驱动：state=model 的答案 → 字幕用真答案；state=model-failed + failureReason → 字幕用后端原话；
        429 + Retry-After → 倒计时；超时（Fetch 挂起不响应）→ 只出字幕、不编答案；
     ④ 手机 375/390/414：栏不压 dock、不溢出视口。

   ⚠ 本机预览跑在 http://127.0.0.1:8790（源 = http://127.0.0.1:8790），后端 CORS 白名单里**没有**这个源
     （实测：Origin=http://127.0.0.1:8790 的 GET /api/public/overview 响应**不带** access-control-allow-origin）
     ⇒ 浏览器里真实跨域 POST 会被 CORS 拒掉（这是后端口径，不是前端 bug）。
     所以本脚本用 **CDP Fetch 拦截**伪造后端响应，只验证前端行为；"用真实响应体"这一点单独用
     `curl -X POST /api/public/ask`（服务器侧、无浏览器 CORS）证明，两条证据在报告里分开写。 */
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = 'F:\\7AAA\\AI\\blog';
const PUB = path.join(ROOT, 'public');
const OUT = path.join(ROOT, '_shots');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8813, CDP = 9363;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.xml': 'application/xml', '.m4a': 'audio/mp4', '.webm': 'audio/webm' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const argOf = (k) => { const a = process.argv.find((x) => x.startsWith('--' + k + '=')); return a ? a.split('=')[1] : null; };
const PREFIX = argOf('prefix') || 'batchB';
fs.mkdirSync(OUT, { recursive: true });

/* ---------- 假后端响应（字段名逐字照后端线设计件 §6 + 线上真实响应） ---------- */
const MOCK = {
  ok: {
    code: 200, message: 'success',
    data: {
      generatedAt: '2026-10-16 13:20:00', deadlineMs: 25000, maxQuestionChars: 1200, publicDemo: true,
      state: 'model', stateLabel: '模型研判', generated: true,
      answer: '## 结论\n\nXSS 的根因是**未做上下文相关的输出编码**：\n1. HTML 体用 `htmlspecialchars`\n2. 属性里加引号并转义\n3. 富文本走白名单净化（如 DOMPurify）\n\n> 公开演示只基于公开知识库回答。',
      citations: [{ title: '安全编码要点', snippet: '按上下文做 htmlspecialchars…', sourceType: 'community', sourceTypeLabel: '社区/内部整理（可信度中）', trustLevel: 'medium', trustLevelLabel: '可信度中', score: 0.82 }],
      quota: { available: true, pool: 'public-demo', limit: 30, used: 3, remaining: 27, note: '公开演示独立额度池' },
      clientIpMasked: '58.19.***.***',
      decision: { schemaVersion: 'xiaokeqing.kurisu.decision.v1', emotionFrom: 'normal', emotionTo: 'normal', action: 'idle', lineId: '', urgency: 0, reason: '', citations: [], fallbackUsed: false, rejectReason: '' }
    }
  },
  /* ★线上真实返回（2026-10-16 13:05 curl 实测，配额已用尽）—— 只取前端要用的字段，逐字保留 */
  quotaOut: {
    code: 200, message: 'success',
    data: {
      state: 'model-failed', stateLabel: '模型不可用，未生成', generated: false,
      failureReason: '今日公开演示模型额度已用完',
      answer: '## 本次没有生成结论\n\n> state=model-failed\n\n原因：**今日公开演示的模型额度已用完**。',
      citations: [], quota: { available: true, pool: 'public-demo', limit: 30, used: 116, remaining: 0, storeFile: 'data/model-quota-public.json', note: '这是【公开演示】独立额度池' },
      decision: { schemaVersion: 'xiaokeqing.kurisu.decision.v1', fallbackUsed: true, rejectReason: 'QUOTA_EXHAUSTED' }
    }
  },
  rate: { code: 429, message: '请求过于频繁', data: { quota: { pool: 'public-demo', limit: 30, used: 30, remaining: 0 } } }
};

/* ---------- 本机静态服务 ---------- */
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p.endsWith('/')) { p += 'index.html'; }
  const f = path.join(PUB, p);
  if (!f.startsWith(PUB) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end('nf'); return; }
  res.writeHead(200, { 'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(PORT, '127.0.0.1', r));

/* ---------- CDP ---------- */
const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-askbar-'));
const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  '--no-default-browser-check', '--disable-extensions', '--mute-audio',
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
let askRequests = [];     /* 本次导航里打到 /api/public/ask 的请求（含 body） */
let pausedLog = [];       /* CDP Fetch 里被拦下的每一个请求（诊断用） */
let consoleMsgs = [];
let mock = { mode: 'off' };   /* {mode:'ok'|'quotaOut'|'rate'|'hang'|'abort'|'off'} */
let intercepting = false;

ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waits.has(m.id)) { const w = waits.get(m.id); waits.delete(m.id); m.error ? w.rej(new Error(JSON.stringify(m.error))) : w.res(m.result); return; }
  if (!m.method) { return; }
  const p = m.params || {};
  if (m.method === 'Network.requestWillBeSent' && /\/api\/public\/ask/.test(p.request?.url || '')) {
    if (p.request.method === 'POST') {          /* 只记真提交；OPTIONS 预检单列（pausedLog 里有） */
      askRequests.push({ url: p.request.url, method: p.request.method, at: Math.round(Date.now()), postData: p.request.postData || null });
    }
  }
  if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(p.type)) {
    consoleMsgs.push(p.type + ': ' + (p.args || []).map((a) => a.value || a.description || '').join(' '));
  }
  if (m.method === 'Runtime.exceptionThrown') {
    consoleMsgs.push('EXCEPTION: ' + (p.exceptionDetails?.exception?.description || p.exceptionDetails?.text || ''));
  }
  /* ---- Fetch 拦截：只拦 /api/public/ask，其余照常走网络 ---- */
  if (m.method === 'Fetch.requestPaused') {
    const url = p.request?.url || '';
    const method = p.request?.method || '';
    pausedLog.push(method + ' ' + url);
    if (!/\/api\/public\/ask/.test(url) || mock.mode === 'off') { rpc('Fetch.continueRequest', { requestId: p.requestId }).catch(() => { }); return; }
    if (method === 'OPTIONS') {                    /* 预检：照实回一份允许的 CORS 头（否则浏览器直接判 POST 失败） */
      rpc('Fetch.fulfillRequest', {
        requestId: p.requestId, responseCode: 204,
        responseHeaders: [
          { name: 'Access-Control-Allow-Origin', value: 'http://127.0.0.1:' + PORT },
          { name: 'Access-Control-Allow-Methods', value: 'POST, GET, OPTIONS' },
          { name: 'Access-Control-Allow-Headers', value: 'Content-Type, X-User-Token' },
          { name: 'Access-Control-Max-Age', value: '600' }
        ]
      }).catch((e) => { consoleMsgs.push('fulfill-options: ' + e.message); });
      return;
    }
    if (mock.mode === 'hang') { return; }                                    /* 不响应 ⇒ 前端的 20s 超时分支（本脚本不跑满 20s） */
    if (mock.mode === 'abort') { rpc('Fetch.failRequest', { requestId: p.requestId, errorReason: 'Failed' }).catch(() => { }); return; }
    const body = mock.mode === 'rate' ? MOCK.rate : (mock.mode === 'quotaOut' ? MOCK.quotaOut : MOCK.ok);
    const headers = [
      { name: 'Content-Type', value: 'application/json' },
      { name: 'Access-Control-Allow-Origin', value: 'http://127.0.0.1:' + PORT },
      { name: 'Access-Control-Expose-Headers', value: 'Retry-After, ETag' }
    ];
    if (mock.mode === 'rate') { headers.push({ name: 'Retry-After', value: '7' }); }
    rpc('Fetch.fulfillRequest', {
      requestId: p.requestId, responseCode: body.code || 200,
      responseHeaders: headers, body: Buffer.from(JSON.stringify(body), 'utf8').toString('base64')
    }).catch((e) => { consoleMsgs.push('fulfill: ' + e.message); });
  }
});

function rpc(method, params = {}) {
  const id = ++mid;
  return new Promise((res, rej) => { waits.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); });
}
async function evalJs(expr) {
  const r = await rpc('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r && r.exceptionDetails) { throw new Error('页面抛异常：' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text)); }
  return r && r.result ? r.result.value : null;
}
async function shot(file) {
  const r = await rpc('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  fs.writeFileSync(path.join(OUT, file), Buffer.from(r.data, 'base64'));
  return fs.statSync(path.join(OUT, file)).size;
}
async function interceptOn() {
  if (intercepting) { return; }
  await rpc('Fetch.enable', { patterns: [{ urlPattern: '*api/public/ask*', requestStage: 'Request' }] });
  intercepting = true;
}
async function gotoHome(url, waitMs = 3000) {
  await rpc('Page.navigate', { url: url || `http://127.0.0.1:${PORT}/` });
  await sleep(waitMs);
}

await rpc('Page.enable'); await rpc('Runtime.enable'); await rpc('Network.enable');
await rpc('Emulation.setDeviceMetricsOverride', { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
await rpc('Network.clearBrowserCache');

const report = { prefix: PREFIX, note: '批次 ② 主页底部对话输入栏第 1 期 · 断言 + 截图', checks: [], shots: [], consoleMsgs: [] };
const push = (name, pass, detail) => {
  report.checks.push({ name, pass: !!pass, detail });
  console.log('  [%s] %s %s', pass ? 'PASS' : 'FAIL', (' ' + name).padEnd(48, ' '), typeof detail === 'string' ? detail : JSON.stringify(detail));
};

/* ================= 场景 1：访客（未登录）—— DOM + 零请求 ================= */
askRequests = []; consoleMsgs = []; mock = { mode: 'off' };
await gotoHome();
const visitor = await evalJs(`(function(){
  var bar=document.getElementById('xkAskBar'), inp=document.getElementById('xkAskInput');
  var cs=bar?getComputedStyle(bar):null, r=bar?bar.getBoundingClientRect():null;
  var d=window.__xkAsk||null;
  return { exists:!!bar, hidden:bar?bar.hidden:null, display:cs?cs.display:null,
           visible:bar?!!(bar.offsetWidth||bar.offsetHeight):null,
           inMain:!!(bar&&bar.closest('main#content')),
           role:bar?bar.getAttribute('role'):null, inputExists:!!inp,
           diagExists:!!d, diagInited:d?d.inited:null, diagAllowed:d?d.allowed:null,
           admin:(window.__xkId||{}).admin===true, token:(function(){try{return !!localStorage.getItem('xk-user-token');}catch(e){return null;}})() };})()`);
push('visitor: askbar 节点在 DOM 里（渲染契约）', visitor.exists === true, visitor);
push('visitor: 但带 hidden + 不可见 + 不在 <main> 内', visitor.hidden === true && visitor.visible === false && visitor.display === 'none' && visitor.inMain === false, { hidden: visitor.hidden, display: visitor.display, visible: visitor.visible, inMain: visitor.inMain });
push('visitor: 驱动没装（__xkAsk 未 init / 未放行）', visitor.diagInited === false && visitor.diagAllowed === false, { inited: visitor.diagInited, allowed: visitor.diagAllowed });
push('visitor: 一个 /api/public/ask 请求都没发', askRequests.length === 0, { askRequests: askRequests.length });
report.shots.push({ scene: 'visitor', viewport: '1280x900', file: `${PREFIX}-home-visitor-1280x900.png`, bytes: await shot(`${PREFIX}-home-visitor-1280x900.png`), probe: visitor });

/* 5 次连点（隐蔽入口 b）后：栏应出现 —— 同一页、不刷新 */
await evalJs(`(function(){var av=document.getElementById('xkIdAv');for(var i=0;i<5;i++){av.dispatchEvent(new MouseEvent('click',{bubbles:true}));}return true;})()`);
await sleep(400);
const after5tap = await evalJs(`(function(){var bar=document.getElementById('xkAskBar'),l=document.getElementById('xkLoginBtn');
  return {loginHidden:l?l.hidden:null, barHidden:bar?bar.hidden:null, barVisible:bar?!!(bar.offsetWidth||bar.offsetHeight):null,
          diag:(window.__xkAsk||{}).inited===true, poke:!!(window.__xkAskBar&&window.__xkAskBar.poke)};})()`);
push('5 次连点（本页加载后开入口）: 👤 与输入栏同时出现', after5tap.loginHidden === false && after5tap.barHidden === false && after5tap.barVisible === true && after5tap.diag === true, after5tap);
report.shots.push({ scene: '5tap', viewport: '1280x900', file: `${PREFIX}-home-5tap-1280x900.png`, bytes: await shot(`${PREFIX}-home-5tap-1280x900.png`), probe: after5tap });

/* ================= 场景 2：?admin=1 真提交（拦成 state=model 的假响应） ================= */
mock = { mode: 'ok' }; await interceptOn();
askRequests = [];
await gotoHome(`http://127.0.0.1:${PORT}/?admin=1`);
const adminOpen = await evalJs(`(function(){var bar=document.getElementById('xkAskBar'),l=document.getElementById('xkLoginBtn');
  return {loginHidden:l?l.hidden:null, barHidden:bar?bar.hidden:null, visible:bar?!!(bar.offsetWidth||bar.offsetHeight):null,
          rect:bar?(function(r){return {left:Math.round(r.left),top:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height),bottom:Math.round(r.bottom)};})(bar.getBoundingClientRect()):null,
          api:(window.__xkAskBar||{}).api||null};})()`);
push('admin: ?admin=1 ⇒ 栏可见', adminOpen.barHidden === false && adminOpen.visible === true, adminOpen);
report.shots.push({ scene: 'admin-open', viewport: '1280x900', file: `${PREFIX}-home-admin-open-1280x900.png`, bytes: await shot(`${PREFIX}-home-admin-open-1280x900.png`), probe: adminOpen });

/* 真·键盘路径：Input.insertText + Input.dispatchKeyEvent(Enter) */
await evalJs(`(function(){var i=document.getElementById('xkAskInput');i.focus();i.value='';return document.activeElement===i;})()`);
await rpc('Input.insertText', { text: '什么是 XSS？怎么防？' });
await sleep(150);
const typed = await evalJs(`(function(){return {v:document.getElementById('xkAskInput').value, c:document.getElementById('xkAskCount').textContent};})()`);
await rpc('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
await rpc('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
await sleep(2500);
const afterAsk = await evalJs(`(function(){var c=document.getElementById('xkIdCap'),d=window.__xkAsk||{};
  return {cap:c?c.textContent:null, capOn:c?c.classList.contains('on'):null, emo:(window.__xkId||{}).emo,
          state:d.state, ms:d.ms, status:d.status, quota:d.quota||null, busy:d.busy===true,
          inputValue:document.getElementById('xkAskInput').value, askBarHidden:document.getElementById('xkAskBar').hidden};})()`);
push('提交: 发出 1 个 POST，body 只有 {question}（≤600）', askRequests.length === 1 && (() => {
  try { const b = JSON.parse(askRequests[0].postData || '{}'); return Object.keys(b).length === 1 && typeof b.question === 'string' && b.question.length <= 600; } catch { return false; }
})(), { n: askRequests.length, postData: askRequests.map((r) => r.postData), typed, paused: pausedLog.slice(-6) });
push('响应 state=model ⇒ 表情 normal + 字幕用真答案', afterAsk.state === 'model' && afterAsk.emo === 'normal' && /答完了/.test(afterAsk.cap || '') && /XSS/.test(afterAsk.cap || ''), afterAsk);
push('答完输入框清空、栏仍在、busy 释放', afterAsk.inputValue === '' && afterAsk.askBarHidden === false && afterAsk.busy === false, { inputValue: afterAsk.inputValue, askBarHidden: afterAsk.askBarHidden, busy: afterAsk.busy });
report.shots.push({ scene: 'answered-model', viewport: '1280x900', file: `${PREFIX}-home-answered-model-1280x900.png`, bytes: await shot(`${PREFIX}-home-answered-model-1280x900.png`), probe: afterAsk });

/* ================= 场景 3：真实"额度用尽"响应（model-failed + failureReason） ================= */
mock = { mode: 'quotaOut' }; askRequests = [];
await evalJs(`(function(){var i=document.getElementById('xkAskInput');i.value='还有额度吗？';return true;})()`);
await evalJs(`(function(){document.getElementById('xkAskSend').click();return true;})()`);
await sleep(2000);
const afterQuota = await evalJs(`(function(){var c=document.getElementById('xkIdCap'),d=window.__xkAsk||{};
  return {cap:c?c.textContent:null, emo:(window.__xkId||{}).emo, state:d.state, quota:d.quota||null};})()`);
push('state=model-failed ⇒ 字幕带后端原话（额度已用完），不补答案', afterQuota.state === 'model-failed' && /模型不可用/.test(afterQuota.cap || '') && /额度已用完/.test(afterQuota.cap || ''), afterQuota);
report.shots.push({ scene: 'quota-out-real-response', viewport: '1280x900', file: `${PREFIX}-home-quota-out-1280x900.png`, bytes: await shot(`${PREFIX}-home-quota-out-1280x900.png`), probe: afterQuota });

/* ================= 场景 4：429 + Retry-After: 7 ================= */
mock = { mode: 'rate' }; askRequests = [];
await evalJs(`(function(){document.getElementById('xkAskInput').value='再问一次';document.getElementById('xkAskSend').click();return true;})()`);
await sleep(1200);
const after429 = await evalJs(`(function(){var c=document.getElementById('xkIdCap'),d=window.__xkAsk||{};
  return {cap:c?c.textContent:null, status:d.status, retryAfter:d.retryAfter, emo:(window.__xkId||{}).emo};})()`);
push('429 ⇒ 读 Retry-After 并倒计时（字幕里出现秒数）', after429.status === 429 && after429.retryAfter === 7 && /请稍后再试\s*[1-7]\s*秒/.test(after429.cap || ''), after429);
report.shots.push({ scene: 'rate-limited-429', viewport: '1280x900', file: `${PREFIX}-home-429-1280x900.png`, bytes: await shot(`${PREFIX}-home-429-1280x900.png`), probe: after429 });

/* ================= 场景 5：网络失败（Fetch.failRequest） ================= */
mock = { mode: 'abort' }; askRequests = [];
await evalJs(`(function(){document.getElementById('xkAskInput').value='断网时问一句';document.getElementById('xkAskSend').click();return true;})()`);
await sleep(1500);
const afterFail = await evalJs(`(function(){var c=document.getElementById('xkIdCap'),d=window.__xkAsk||{};
  return {cap:c?c.textContent:null, errors:(d.errors||[]).slice(-2), emo:(window.__xkId||{}).emo};})()`);
push('网络失败 ⇒ 只出字幕（不编答案、不刷屏）', /请求没?能?送达/.test(afterFail.cap || '') && /不编答案/.test(afterFail.cap || '') && afterFail.emo === 'normal' && !/EXCEPTION/.test(consoleMsgs.join(' ')), afterFail);
report.shots.push({ scene: 'network-fail', viewport: '1280x900', file: `${PREFIX}-home-netfail-1280x900.png`, bytes: await shot(`${PREFIX}-home-netfail-1280x900.png`), probe: afterFail });

/* ================= 场景 6：600 字符截断 ================= */
mock = { mode: 'ok' }; askRequests = [];
const longQ = 'x'.repeat(900);
await evalJs(`(function(){document.getElementById('xkAskInput').value=${JSON.stringify(longQ)};return true;})()`);
const countLong = await evalJs(`(function(){return document.getElementById('xkAskCount').textContent;})()`);
await evalJs(`(function(){document.getElementById('xkAskSend').click();return true;})()`);
await sleep(1500);
const trunc = askRequests.length ? JSON.parse(askRequests[0].postData).question.length : -1;
push('超长提问被截到 600 字符（与后端 maxQuestionChars 同口径）', trunc === 600, { sent: trunc, counterBeforeSend: countLong });

/* ================= 场景 7：手机 375 / 390 / 414（栏不溢出、不压 dock） ================= */
mock = { mode: 'off' };
await rpc('Fetch.disable'); intercepting = false;
for (const vp of [{ w: 375, h: 812 }, { w: 390, h: 844 }, { w: 414, h: 896 }]) {
  await rpc('Emulation.setDeviceMetricsOverride', { width: vp.w, height: vp.h, deviceScaleFactor: 1, mobile: true });
  await gotoHome(`http://127.0.0.1:${PORT}/?admin=1`);
  const geo = await evalJs(`(function(){var bar=document.getElementById('xkAskBar'),dk=document.getElementById('dock');
    var b=bar.getBoundingClientRect(), d=dk?dk.getBoundingClientRect():null;
    return {bar:{l:Math.round(b.left),r:Math.round(b.right),t:Math.round(b.top),b:Math.round(b.bottom),w:Math.round(b.width)},
            dock:d?{l:Math.round(d.left),r:Math.round(d.right),t:Math.round(d.top),b:Math.round(d.bottom)}:null,
            vw:innerWidth, vh:innerHeight,
            overlap:d?(b.left<d.right&&b.right>d.left&&b.top<d.bottom&&b.bottom>d.top):null,
            inputFont:getComputedStyle(document.getElementById('xkAskInput')).fontSize};})()`);
  const fit = geo.bar.l >= 0 && geo.bar.r <= geo.vw + 1 && geo.bar.b <= geo.vh + 1;
  push(`phone${vp.w}: 栏在视口内 + 与 dock 不重叠 + 输入字号 16px`, fit && geo.overlap === false && geo.inputFont === '16px', geo);
  const file = `${PREFIX}-home-phone${vp.w}-admin.png`;
  report.shots.push({ scene: 'phone-admin', viewport: `${vp.w}x${vp.h}`, file, bytes: await shot(file), probe: geo });
}

/* ================= 场景 8：内容页不得出现可见栏（只有主页渲染） ================= */
await rpc('Emulation.setDeviceMetricsOverride', { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
for (const [name, url] of [['ai', 'ai/?admin=1'], ['test', 'test/?admin=1']]) {
  await gotoHome(`http://127.0.0.1:${PORT}/${url}`, 2600);
  const p = await evalJs(`(function(){var bar=document.getElementById('xkAskBar');
    return {exists:!!bar, hidden:bar?bar.hidden:null, visible:bar?!!(bar.offsetWidth||bar.offsetHeight):null,
            diag:(window.__xkAsk||{}).inited===true, bodyClass:document.body.className};})()`);
  push(`${name}/ 即使 ?admin=1 也不显示栏（只有主页渲染）`, p.exists === true && p.visible === false && p.diag === false, p);
}

report.consoleMsgs = consoleMsgs;
push('全程 console 错误/警告 = 0', consoleMsgs.length === 0, consoleMsgs.slice(0, 5));
report.askRequestsTotal = askRequests.length;

fs.writeFileSync(path.join(OUT, PREFIX + '-askbar-report.json'), JSON.stringify(report, null, 1), 'utf8');
const failed = report.checks.filter((c) => !c.pass).length;
console.log('\n== 汇总 ==\n  %d 项断言，失败 %d 项', report.checks.length, failed);
console.log('  报告 →', path.join(OUT, PREFIX + '-askbar-report.json'));
try { ws.close(); } catch { }
try { child.kill(); } catch { }
server.close();
process.exit(failed ? 1 : 0);
