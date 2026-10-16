/* ★B2 验收探针：慢网容错（12s→25s / 保留上次成功数据 / 三态可分辨）
   用法：node _dev/probe-slownet.mjs [--pub=<目录>] [--label=after|before]
     --pub   要服务的产物目录（默认 public）
     --label 截图前缀 b2-after- / b2-before-
   造响应：CDP Fetch 域拦 https://demo.xiaokeqing.cn/api/public/*，离线确定性跑。四种行为：
     ok       —— 全部 200 + 真实形状
     degraded —— 全部 200 但 available=false / 数组为空（触发站点既有的"补一次请求"重试）
     fail     —— Fetch.failRequest（模拟不可达/超时）
     slow15   —— alerts 延迟 15s 再回（用来证明上限已从 12s 抬到 25s；12s 时代这里必被 abort）
   输出：_shots/probe-slownet.json + _shots/b2-{label}-NN-*.png + 控制台 PASS/FAIL */
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = 'F:\\7AAA\\AI\\blog';
const argOf = (k, d) => { const a = process.argv.find((x) => x.startsWith('--' + k + '=')); return a ? a.split('=').slice(1).join('=') : d; };
const LABEL = argOf('label', 'after');
const PUB = path.resolve(argOf('pub', path.join(ROOT, 'public')));
const PREFIX = 'b2-' + LABEL + '-';
const OUT = path.join(ROOT, '_shots');
const REPORT = path.join(OUT, 'probe-slownet-' + LABEL + '.json');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8853, CDP = 9397;
const API = 'https://demo.xiaokeqing.cn';
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.webm': 'video/webm', '.woff2': 'font/woff2' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });
if (!fs.existsSync(path.join(PUB, 'alerts', 'index.html'))) { console.error('--pub 里没有 alerts/index.html：' + PUB); process.exit(2); }

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

/* ---------------- 造数据（形状照真实端点，值随意但必须自洽） ---------------- */
const V = {
  alerts: { available: true, list: [{ aggId: 'a1', occurredAt: '2026-10-16T19:00:00', type: 'SSH', typeLabel: 'SSH 暴破', srcIp: '45.83.91.55', title: 'Failed password for root', count: 7 }],
    stats: { byType: [{ key: 'SSH', label: 'SSH 暴破', count: 12 }] },
    stats24h: { available: true, total: 42, bySeverity: { CRITICAL: 0, HIGH: 3, MEDIUM: 4, LOW: 5 }, trend: [1, 2, 3] } },
  geo: { available: true, byCountry: [{ country: 'CN', countryName: '中国', count: 10, sharePercent: 50 }], coverage: { sourceBuckets: 9 } },
  honeypot: { available: true, connections: 281, logins: 254, total: 10000, topCredentials: [{ username: 'root', passwordLength: 7, count: 45, weakPassword: true }], topClients: [{ key: '45.83.91.55', count: 9 }] },
  audit: { summary: { total: 5, active: 2, blockedByGuard: 26, executedActions: 3 }, blocks: [] },
  overview: { available: true, alerts: { bySource: [{ key: 'wazuh', label: 'Wazuh', count: 20 }] } },
  webstats: { available: true, heatmap: [{ hour: 13, count: 9 }] },
  stories: { available: true, sources: [{ key: 's1', title: '示例故事线', count: 2 }] }
};
const DEG = {
  alerts: { available: true, list: [], stats: { byType: [] }, stats24h: { available: false, total: 0, bySeverity: {}, trend: [] } },
  geo: { available: true, byCountry: [], coverage: { sourceBuckets: 0 } },
  honeypot: { available: true, connections: 0, logins: 0, total: 0, topCredentials: [], topClients: [] },
  audit: { available: true, summary: null, blocks: [] },
  overview: { available: true, alerts: null },
  webstats: { available: true, heatmap: [] },
  stories: { available: true, sources: [] }
};
const PATHS = ['alerts', 'overview', 'honeypot', 'audit', 'geo', 'webstats', 'stories'];
let MODE = 'ok';                       /* ok | degraded | fail | slow15 */
let inFlight = 0;

const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-b2-'));
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
const consoleMsgs = [];
const rpc = (method, params = {}) => { const id = ++mid; return new Promise((res, rej) => { waits.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); }); };

ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waits.has(m.id)) { const w = waits.get(m.id); waits.delete(m.id); m.error ? w.rej(new Error(JSON.stringify(m.error))) : w.res(m.result); return; }
  const p = m.params || {};
  if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(p.type)) consoleMsgs.push(p.type + ': ' + (p.args || []).map((a) => a.value || a.description || '').join(' '));
  if (m.method === 'Runtime.exceptionThrown') consoleMsgs.push('EXCEPTION: ' + (p.exceptionDetails?.exception?.description || p.exceptionDetails?.text || ''));
  if (m.method === 'Fetch.requestPaused') {
    const req = p.request, id = p.requestId;
    const name = PATHS.find((n) => req.url.indexOf('/api/public/' + n) >= 0) || '(other)';
    const cors = [
      { name: 'access-control-allow-origin', value: BASE },
      { name: 'access-control-allow-methods', value: 'GET,POST,OPTIONS' },
      { name: 'access-control-allow-headers', value: 'content-type,x-user-token' },
      { name: 'access-control-max-age', value: '0' }
    ];
    if (req.method === 'OPTIONS') { rpc('Fetch.fulfillRequest', { requestId: id, responseCode: 204, responseHeaders: cors, body: '' }).catch(() => { }); return; }
    const delay = (MODE === 'slow15' && name === 'alerts') ? 15000 : 0;
    const respond = () => {
      if (MODE === 'fail') { rpc('Fetch.failRequest', { requestId: id, errorReason: 'ConnectionFailed' }).catch(() => { }); inFlight--; return; }
      const body = MODE === 'degraded' ? DEG[name] : V[name];
      const headers = cors.concat([{ name: 'content-type', value: 'application/json;charset=UTF-8' }]);
      rpc('Fetch.fulfillRequest', { requestId: id, responseCode: 200, responseHeaders: headers, body: Buffer.from(JSON.stringify({ code: 200, data: body || {} }), 'utf8').toString('base64') })
        .catch(() => { }).then(() => { inFlight--; });
    };
    inFlight++;
    if (delay) { setTimeout(respond, delay); } else { respond(); }
  }
});

const evalJs = async (expr) => {
  const r = await rpc('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r && r.exceptionDetails) return { __err: (r.exceptionDetails.exception?.description || r.exceptionDetails.text || '').slice(0, 200) };
  return r && r.result ? r.result.value : null;
};
await rpc('Page.enable'); await rpc('Runtime.enable');
await rpc('Fetch.enable', { patterns: [{ urlPattern: '*demo.xiaokeqing.cn*', requestStage: 'Request' }] });

const SNAP = `(function(){
  var sync = document.querySelector('.screen-hd .sync');
  var notes = Array.prototype.slice.call(document.querySelectorAll('.xk-stale')).map(function(e){return e.textContent;});
  var lv = document.querySelector('.ops-rail .mod .lv');
  var body = (document.body && document.body.innerText) || '';
  var n = 0; try { for (var i=0;i<sessionStorage.length;i++){ if (String(sessionStorage.key(i)).indexOf('xk-lastgood-v1:')===0) n++; } } catch(e) { n = -1; }
  return { syncText: sync ? sync.textContent : null, staleNotes: notes, staleCount: notes.length,
    threatLevel: lv ? lv.textContent : null, hasDuBuDao: body.indexOf('读不到') >= 0, lastgoodKeys: n };
})()`;
const clearLG = `(function(){ try { for (var i=sessionStorage.length-1;i>=0;i--){ var k=sessionStorage.key(i); if (String(k).indexOf('xk-lastgood-v1:')===0) sessionStorage.removeItem(k); } } catch(e){} return 1; })()`;

async function shot(name) {
  try { const png = await rpc('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); fs.writeFileSync(path.join(OUT, PREFIX + name + '.png'), Buffer.from(png.data, 'base64')); return PREFIX + name + '.png'; }
  catch { return null; }
}

const runs = [];
async function scenario(name, opts) {
  const { mode = 'ok', seedGood = false, sampleMs = 0, url = '/alerts/' } = opts;
  consoleMsgs.length = 0;
  MODE = mode;
  await rpc('Page.navigate', { url: BASE + '/' });          /* 先落到同源，才能清 sessionStorage */
  await sleep(400);
  const t0 = Date.now();
  let seedSnap = null;
  if (seedGood) {
    MODE = 'ok';
    await rpc('Page.navigate', { url: BASE + url });
    await sleep(3000);
    seedSnap = await evalJs(SNAP);                          /* 第一次成功 ⇒ 写入"上次成功数据" */
    MODE = mode;
  } else {
    await evalJs(clearLG);                                  /* 清干净：本场景不允许有"上次数据" */
  }
  const seq = [];
  if (sampleMs) {
    const p = rpc('Page.navigate', { url: BASE + url });
    const end = Date.now() + sampleMs;
    while (Date.now() < end) { await sleep(150); const s = await evalJs(SNAP); if (s && s.syncText) seq.push(s.syncText); }
    await p;
  } else {
    await rpc('Page.navigate', { url: BASE + url });
    await sleep(mode === 'slow15' ? 21000 : 3600);
  }
  const elapsedMs = Date.now() - t0;
  for (let i = 0; i < 60 && inFlight > 0; i++) { await sleep(100); }
  const snap = await evalJs(SNAP);
  const png = await shot(name);
  const run = { name, mode, url, elapsedMs, snap, seedSnap, syncSeq: seq, shot: png, console: consoleMsgs.slice() };
  runs.push(run);
  return run;
}

const r1 = await scenario('01-normal', { mode: 'ok' });
const r2 = await scenario('02-slow15-alerts', { mode: 'slow15' });
const r3 = await scenario('03-fail-no-lastgood', { mode: 'fail' });
const r4 = await scenario('04-fail-with-lastgood', { mode: 'fail', seedGood: true });
const r5 = await scenario('05-retry-degraded', { mode: 'degraded', sampleMs: 6000 });

/* ---------------- 判定 ---------------- */
const checks = [];
const add = (n, ok, d) => checks.push({ name: n, ok: !!ok, detail: d });
const STALE_RE = /上次数据·\d{2}:\d{2}:\d{2}/;
add('① 慢响应 15s 不再被判"读不到"（证明上限 12s→25s 生效）',
  !!(r2.snap && r2.snap.threatLevel && r2.snap.threatLevel !== '读不到' && r2.elapsedMs >= 14000),
  JSON.stringify({ lv: r2.snap && r2.snap.threatLevel, ms: r2.elapsedMs }));
add('① 15s 场景里页面确实渲染了 alerts 真值（威胁等级=高）',
  !!(r2.snap && r2.snap.threatLevel === '高'), JSON.stringify(r2.snap && r2.snap.threatLevel));
add('② 首次失败 + 无上次数据 ⇒ 照旧"读不到"（不补样例）',
  !!(r3.snap && r3.snap.hasDuBuDao), JSON.stringify(r3.snap));
add('② 首次失败 + 无上次数据 ⇒ 不许出现任何"上次数据"标注',
  !!(r3.snap && r3.snap.staleCount === 0), JSON.stringify(r3.snap && r3.snap.staleNotes));
add('③ 失败但已有上次成功数据 ⇒ 页面显示的是上次数据（不是"读不到"）',
  !!(r4.snap && r4.snap.threatLevel && r4.snap.threatLevel !== '读不到' && r4.seedSnap && r4.snap.threatLevel === r4.seedSnap.threatLevel),
  JSON.stringify({ seed: r4.seedSnap && r4.seedSnap.threatLevel, now: r4.snap && r4.snap.threatLevel }));
add('③ 且卡角出现「上次数据 · 时间」小字（可机读）',
  !!(r4.snap && r4.snap.staleCount >= 1 && r4.snap.staleNotes.every((t) => STALE_RE.test(t))),
  JSON.stringify(r4.snap && r4.snap.staleNotes));
add('③ 同步行明说"几格显示的是上次数据"（不许写"刚刚同步"冒充本次真值）',
  !!(r4.snap && r4.snap.syncText && r4.snap.syncText.indexOf('上次数据') >= 0),
  JSON.stringify(r4.snap && r4.snap.syncText));
add('④ "重试中"与"读不到"可分辨（采样序列里出现"重试中"）',
  r5.syncSeq.some((t) => t.indexOf('重试中') >= 0), JSON.stringify(r5.syncSeq));
add('④ "重试中"不能同时出现在写"读不到"的那一态里',
  !r5.syncSeq.some((t) => t.indexOf('重试中') >= 0 && t.indexOf('读不到') >= 0), JSON.stringify(r5.syncSeq.slice(0, 6)));
add('④ 重试后仍降级 ⇒ 状态转成"降级值"说明（不再停在"重试中"，也不冒充"刚刚同步"）',
  !!(r5.snap && r5.snap.syncText && r5.snap.syncText.indexOf('重试中') < 0 && r5.snap.syncText.indexOf('降级值') >= 0),
  JSON.stringify(r5.snap && r5.snap.syncText));
add('⑤ 上次数据真的落进了 sessionStorage（键名带版本）',
  !!(r4.snap && r4.snap.lastgoodKeys > 0), JSON.stringify(r4.snap && r4.snap.lastgoodKeys));
add('console 0（阻断性）', runs.every((r) => r.console.filter((c) => c.startsWith('EXCEPTION') || c.startsWith('error')).length === 0),
  JSON.stringify(runs.map((r) => r.console.length)));

const pass = checks.filter((c) => c.ok).length;
const report = { at: new Date().toISOString(), label: LABEL, servedFrom: PUB, base: BASE, api: API, checks, summary: { pass, total: checks.length } };
fs.writeFileSync(REPORT, JSON.stringify(report, null, 1), 'utf8');
for (const c of checks) console.log((c.ok ? '  [PASS] ' : '  [FAIL] ') + c.name + (c.ok ? '' : '   << ' + c.detail));
console.log('\nB2 探针（' + LABEL + '，产物=' + PUB + '）：' + pass + '/' + checks.length + ' PASS');
console.log('报告 →', REPORT);
try { ws.close(); } catch { }
try { child.kill(); } catch { }
server.close();
process.exit(pass === checks.length ? 0 : 1);
