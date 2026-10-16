/* ★B2+B3 验收探针：慢网容错 + 可缓存别名 + 429 限流状态
   用法：node _dev/probe-slownet.mjs [--pub=<目录>] [--label=after|before]
   造响应：CDP Fetch 域拦 https://demo.xiaokeqing.cn/api/public/**
     行为：ok（别名 200 + 新鲜度字段 + Age）/ degraded（200 但 available=false）/ fail（failRequest）
           / slow15（alerts 延迟 15s）/ slow-hp（honeypot 延迟 15s：验渐进渲染）/ rate-header（429 + Retry-After 头）/ rate-body（429 + body.retryAfter）
           / rate-none（429 且不给秒数）
   输出：_shots/probe-slownet-<label>.json + _shots/b2-<label>-NN-*.png + 控制台 PASS/FAIL */
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';

const ROOT = 'F:\\7AAA\\AI\\blog';
const argOf = (k, d) => { const a = process.argv.find((x) => x.startsWith('--' + k + '=')); return a ? a.split('=').slice(1).join('=') : d; };
const LABEL = argOf('label', 'after');
const PUB = path.resolve(argOf('pub', path.join(ROOT, 'public')));
const PREFIX = 'b2-' + LABEL + '-';
const OUT = path.join(ROOT, '_shots');
const REPORT = path.join(OUT, 'probe-slownet-' + LABEL + '.json');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8861, CDP = 9401;
const API = 'https://demo.xiaokeqing.cn';
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.webm': 'video/webm', '.woff2': 'font/woff2' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const SNAP_AT = '2026-10-16T19:38:12+08:00';       /* 固定快照时刻 ⇒ 可确定性断言"用的是 snapshotAt" */
const SNAP_HHMMSS = '19:38:12';
const CACHE_AGE = 7, EDGE_AGE = 5;                 /* 真实年龄应为 12s（契约 §4-2：cacheAgeSeconds + Age） */
const HEADER_WAIT = 7, BODY_WAIT = 9;
/* ★B4b：首页「0 请求 / 可见真值不受影响」的基线文件（由 --label=before 那次运行写出，这里默认读它做机械比对） */
const BASELINE_HOME = argOf('baseline-home', path.join(OUT, 'home-snap-before.json'));
const sha16 = (s) => crypto.createHash('sha256').update(String(s)).digest('hex').slice(0, 16);
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

/* ---------------- 造数据 ---------------- */
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
const JOBS = ['alerts', 'overview', 'honeypot', 'audit', 'geo', 'webstats', 'stories'];
const FIRST = 3;                                  /* ★B4：首屏（live）应恰好 = alerts + geo + honeypot */
const FIRST_SET = ['alerts', 'geo', 'honeypot'];
const nameOf = (u) => { const m = String(u).match(/\/api\/public\/([a-z]+)\.js/); return m ? m[1] : String(u); };
let MODE = 'ok';
let inFlight = 0;
const apiHits = [];            /* 本轮所有打到 /api/public/ 的 URL（含查询串） */
const apiLog = [];             /* 取证：{url, mode, code} —— 用来查"谁在什么时候成功写入了上次数据" */

const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-b3-'));
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
    if (req.url.indexOf('/api/public/') >= 0) apiHits.push(req.url);
    const name = JOBS.find((n) => req.url.indexOf('/api/public/' + n) >= 0) || '(other)';
    if (req.url.indexOf('/api/public/') >= 0) apiLog.push({ url: req.url.replace(API, ''), mode: MODE, code: (MODE === 'fail' ? 'FAILREQ' : (MODE.indexOf('rate-') === 0 ? 429 : (MODE === 'alias404' && /\.js(\?|$)/.test(req.url) ? 404 : 200))) });
    /* 契约 §3：别名路径放行 Age（+ Retry-After、限流头）并给 nosniff；Content-Type 仍是 application/json */
    const base = [
      { name: 'access-control-allow-origin', value: '*' },
      { name: 'access-control-allow-methods', value: 'GET,POST,OPTIONS' },
      { name: 'access-control-allow-headers', value: 'content-type' },
      { name: 'access-control-expose-headers', value: 'Age, Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining' },
      { name: 'access-control-max-age', value: '0' },
      { name: 'x-content-type-options', value: 'nosniff' },
      { name: 'cache-control', value: 'public, max-age=15' }
    ];
    if (req.method === 'OPTIONS') { rpc('Fetch.fulfillRequest', { requestId: id, responseCode: 204, responseHeaders: base, body: '' }).catch(() => { }); return; }
    const respond = () => {
      if (MODE === 'fail') { rpc('Fetch.failRequest', { requestId: id, errorReason: 'ConnectionFailed' }).catch(() => { }); inFlight--; return; }
      if (MODE.indexOf('rate-') === 0) {
        const headers = base.concat([{ name: 'content-type', value: 'application/json;charset=UTF-8' }]);
        let body = { code: 429, message: '请求过于频繁', reason: 'RATE_LIMITED' };
        if (MODE === 'rate-header') headers.push({ name: 'Retry-After', value: String(HEADER_WAIT) });
        if (MODE === 'rate-body') body = { code: 429, message: '请求过于频繁', reason: 'RATE_LIMITED', retryAfter: BODY_WAIT };
        rpc('Fetch.fulfillRequest', { requestId: id, responseCode: 429, responseHeaders: headers, body: Buffer.from(JSON.stringify(body), 'utf8').toString('base64') })
          .catch(() => { }).then(() => { inFlight--; });
        return;
      }
      if (MODE === 'alias404') {          /* 模拟"别名未部署 / CF 缓存了 404"：别名 404，旧路径 200（无 snapshotAt） */
        const isAlias = /\.js(\?|$)/.test(req.url);
        const headers = base.concat([{ name: 'content-type', value: 'application/json;charset=UTF-8' }]);
        const bodyObj = isAlias
          ? { code: 404, message: '接口或资源不存在' }
          : { code: 200, message: 'success', data: Object.assign({ generatedAt: SNAP_AT.slice(0, 19).replace('T', ' ') }, V[name] || {}) };
        rpc('Fetch.fulfillRequest', { requestId: id, responseCode: isAlias ? 404 : 200, responseHeaders: headers, body: Buffer.from(JSON.stringify(bodyObj), 'utf8').toString('base64') })
          .catch(() => { }).then(() => { inFlight--; });
        return;
      }
      const data = MODE === 'degraded' ? DEG[name] : V[name];
      const headers = base.concat([{ name: 'content-type', value: 'application/json;charset=UTF-8' }, { name: 'age', value: String(EDGE_AGE) }]);
      const env = { code: 200, message: 'success', data: data || {}, snapshotAt: SNAP_AT, cacheAgeSeconds: CACHE_AGE, snapshotTtlSeconds: 15, freshnessNote: '口径说明（探针造）' };
      rpc('Fetch.fulfillRequest', { requestId: id, responseCode: 200, responseHeaders: headers, body: Buffer.from(JSON.stringify(env), 'utf8').toString('base64') })
        .catch(() => { }).then(() => { inFlight--; });
    };
    inFlight++;
    const slowName = MODE === 'slow15' ? 'alerts' : (MODE === 'slow-hp' ? 'honeypot' : null);
    if (slowName && name === slowName) { setTimeout(respond, 15000); } else { respond(); }
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
    threatLevel: lv ? lv.textContent : null, hasDuBuDao: body.indexOf('读不到') >= 0,
    hasRateWord: body.indexOf('被限流') >= 0, hasUnreachWord: body.indexOf('不可达') >= 0,
    lastgoodKeys: n, staleDbg: window.__xkStale || null, bindErr: window.__xkBindErr || null };
})()`;
const clearLG = `(function(){ try { for (var i=sessionStorage.length-1;i>=0;i--){ var k=sessionStorage.key(i); if (String(k).indexOf('xk-lastgood-v1:')===0) sessionStorage.removeItem(k); } } catch(e){} return 1; })()`;

async function shot(name) {
  try { const png = await rpc('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); fs.writeFileSync(path.join(OUT, PREFIX + name + '.png'), Buffer.from(png.data, 'base64')); return PREFIX + name + '.png'; }
  catch { return null; }
}

const runs = [];
async function scenario(name, opts) {
  const { mode = 'ok', seedGood = false, sampleMs = 0, url = '/alerts/', cooldownProbe = false } = opts;
  consoleMsgs.length = 0;
  /* 落地页：非 seedGood 场景一律用 fail，保证"落地页不会偷偷写入上次数据"（否则清缓存后仍有在途响应落盘 ⇒ 竞态） */
  MODE = seedGood ? 'ok' : 'fail';
  await rpc('Page.navigate', { url: BASE + '/' });          /* 先落到同源（首页） */
  await sleep(900);
  let seedSnap = null;
  if (seedGood) {
    MODE = 'ok';
    await rpc('Page.navigate', { url: BASE + url });
    await sleep(2600);
    seedSnap = await evalJs(SNAP);                          /* 第一次成功 ⇒ 写入"上次成功数据" */
  } else {
    await evalJs(clearLG);                                  /* 清干净：本场景不允许有"上次数据" */
  }
  MODE = mode;
  apiHits.length = 0;
  if (!seedGood) { await evalJs(clearLG); }               /* 双清：压掉"落地页在途响应落盘"的竞态窗口 */
  const t0 = Date.now();
  const seq = [];
  if (sampleMs) {
    const p = rpc('Page.navigate', { url: BASE + url });
    const end = Date.now() + sampleMs;
    while (Date.now() < end) { await sleep(150); const s = await evalJs(SNAP); if (s && s.syncText) seq.push(s.syncText); }
    await p;
  } else {
    await rpc('Page.navigate', { url: BASE + url });
    await sleep(mode === 'slow15' ? 21000 : (mode.indexOf('rate-') === 0 ? 2600 : 3600));
  }
  const elapsedMs = Date.now() - t0;
  for (let i = 0; i < 60 && inFlight > 0; i++) { await sleep(100); }
  const snap = await evalJs(SNAP);
  const hits = apiHits.slice();
  let cool = null;
  if (cooldownProbe) {                                       /* ★B3：429 冷却期内不得再发请求 */
    const before = apiHits.length;
    await evalJs(`document.dispatchEvent(new Event('visibilitychange')); 1`);
    await sleep(1600);
    const after = await evalJs(SNAP);
    cool = { grew: apiHits.length - before, syncText: after && after.syncText };
  }
  const png = await shot(name);
  const run = { name, mode, url, elapsedMs, snap, seedSnap, syncSeq: seq, apiHits: hits, apiLog: apiLog.slice(-40), cooldown: cool, shot: png, console: consoleMsgs.slice() };
  runs.push(run);
  return run;
}

const r1 = await scenario('01-normal-alias', { mode: 'ok' });
const r2 = await scenario('02-slow15-alerts', { mode: 'slow15' });
const r3 = await scenario('03-fail-no-lastgood', { mode: 'fail' });
const r4 = await scenario('04-fail-with-lastgood', { mode: 'fail', seedGood: true });
const r5 = await scenario('05-retry-degraded', { mode: 'degraded', sampleMs: 6000 });
const r6 = await scenario('06-429-retry-after-header', { mode: 'rate-header', cooldownProbe: true });
const r7 = await scenario('07-429-body-retryAfter', { mode: 'rate-body' });
const r8 = await scenario('08-429-no-seconds', { mode: 'rate-none' });
const r9 = await scenario('09-429-with-lastgood', { mode: 'rate-none', seedGood: true });
const r10 = await scenario('10-alias404-fallback', { mode: 'alias404' });

/* ★B4：按 tab 懒加载 —— 首屏 3 个；切到 graph/matrix/stats 才补该 tab 独有的端点（取过的不重复取） */
const tabRun = async () => {
  consoleMsgs.length = 0;
  MODE = 'ok';
  await rpc('Page.navigate', { url: BASE + '/' });
  await sleep(900);
  await evalJs(clearLG);
  MODE = 'ok';
  apiHits.length = 0;
  await rpc('Page.navigate', { url: BASE + '/alerts/' });
  await sleep(3200);
  const first = apiHits.map(nameOf).sort();
  const holo1 = await evalJs(`(function(){var e=document.getElementById('holoSay');return e?e.textContent:null;})()`);
  const phases = [];
  for (const tab of ['graph', 'matrix', 'stats']) {
    const before = apiHits.length;
    await evalJs(`document.querySelector('#opsTabs button[data-tab=${tab}]').click(); 1`);
    await sleep(2600);
    phases.push({ tab, added: apiHits.slice(before).map(nameOf).sort() });
  }
  const snap = await evalJs(SNAP);
  const holo2 = await evalJs(`(function(){var e=document.getElementById('holoSay');return e?e.textContent:null;})()`);
  const storyTag = await evalJs(`(function(){var e=document.querySelector('[data-story-tag]');return e?e.textContent:null;})()`);
  const png = await shot('11-tab-lazy');
  const run = { name: '11-tab-lazy', mode: 'ok', first, holo1, holo2, storyTag, phases, snap, apiHits: apiHits.map(nameOf), shot: png, console: consoleMsgs.slice() };
  runs.push(run);
  return run;
};
const r11 = await tabRun();

/* ★B4b：首页 —— "首屏 0 请求" + "可见真值不受影响"（两档视口整屏截图 + 可见文本/元素快照，
   并与改前基线逐项机械比对：截图 sha、可见文本 sha、计数器文本、CRT 状态行、HOLO 文案、布局盒） */
const SNAP_HOME = `(function(){
  var body = (document.body && document.body.innerText) || '';
  function t(sel){ var e=document.querySelector(sel); return e ? String(e.textContent).replace(/\\s+/g,' ').trim() : null; }
  function box(sel){ var e=document.querySelector(sel); if(!e) return null; var r=e.getBoundingClientRect(), cs=getComputedStyle(e);
    return { w: Math.round(r.width), h: Math.round(r.height), display: cs.display, vis: cs.visibility }; }
  return {
    text: body,
    counters: Array.prototype.map.call(document.querySelectorAll('[data-count]'), function(e){return String(e.textContent).trim();}),
    holo: t('#holoSay'), crtStatus: t('#crtStatus'),
    nav: Array.prototype.map.call(document.querySelectorAll('.dock a, #dock a, nav a'), function(e){return String(e.textContent).trim();}).join('|'),
    screenBox: box('.screen'), statsBox: box('.stats'),
    hasDuBuDao: body.indexOf('读不到') >= 0, bodyLen: body.length
  };
})()`;
const homeRun = async (vp) => {
  consoleMsgs.length = 0;
  MODE = 'ok';
  await rpc('Emulation.setDeviceMetricsOverride', { width: vp.w, height: vp.h, deviceScaleFactor: 1, mobile: !!vp.mobile });
  apiHits.length = 0;
  await rpc('Page.navigate', { url: BASE + '/' });
  await sleep(3200);
  const hits = apiHits.map(nameOf).sort();
  const snap = await evalJs(SNAP_HOME);
  const png = await rpc('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  const file = PREFIX + 'home-' + vp.name + '.png';
  const buf = Buffer.from(png.data, 'base64');
  fs.writeFileSync(path.join(OUT, file), buf);
  await rpc('Emulation.clearDeviceMetricsOverride');
  const run = { name: 'home-' + vp.name, vp: vp.name, w: vp.w, h: vp.h, hits,
    textSha: sha16(snap.text), bodyLen: snap.bodyLen, counters: snap.counters, holo: snap.holo,
    crtStatus: snap.crtStatus, nav: snap.nav, hasDuBuDao: snap.hasDuBuDao, screenBox: snap.screenBox, statsBox: snap.statsBox,
    file, shotSha: sha16(buf), console: consoleMsgs.slice() };
  runs.push(run);
  return run;
};
const home1440 = await homeRun({ name: '1440x900', w: 1440, h: 900 });
const home390 = await homeRun({ name: '390x844', w: 390, h: 844, mobile: true });
fs.writeFileSync(path.join(OUT, 'home-snap-' + LABEL + '.json'),
  JSON.stringify({ at: new Date().toISOString(), label: LABEL, servedFrom: PUB, runs: [home1440, home390] }, null, 1), 'utf8');

/* ★B5：渐进渲染 —— ①慢端点拖 15s 时其它卡 <3s 出数；②未到的端点保持骨架、不写"读不到"；③降级不阻塞首屏 */
const SNAP_PROG = `(function(){
  function t(e){ return e ? String(e.textContent).replace(/\\s+/g,' ').trim() : null; }
  var mods = document.querySelectorAll('.ops-rail .mod');
  function firstK(i){ var m = mods[i]; if(!m) return null; var k = m.querySelector('.row .k'); return k ? t(k) : null; }
  function firstKsk(i){ var m = mods[i]; if(!m) return null; var k = m.querySelector('.row .k'); return k ? k.classList.contains('sk') : null; }
  var body = (document.body && document.body.innerText) || '';
  var sync = document.querySelector('.screen-hd .sync');
  return { threat: t(mods[0] && mods[0].querySelector('.lv')), geoFirst: firstK(1), honeyFirst: firstK(2),
    honeySkeleton: firstKsk(2), syncText: sync ? t(sync) : null, hasNA: body.indexOf('读不到') >= 0,
    naCtx: (function(){ var out=[], i=0; while((i=body.indexOf('读不到',i))>=0 && out.length<4){ out.push(body.slice(Math.max(0,i-34), i+20).replace(/\\s+/g,' ')); i+=3; } return out; })() };
})()`;
const isReal = (v) => !!v && v !== '—' && v.indexOf('读不到') < 0 && v.indexOf('取数中') < 0 && String(v).trim() !== '';
const progRun = async (tag, mode, budgetMs) => {
  consoleMsgs.length = 0;
  MODE = 'fail';
  await rpc('Page.navigate', { url: BASE + '/' });
  await sleep(900);
  await evalJs(clearLG);
  MODE = mode;
  apiHits.length = 0;
  const t0 = Date.now();
  await rpc('Page.navigate', { url: BASE + '/alerts/' });
  let firstData = null, firstTwo = null, allThree = null, firstRender = null, degShown = null, painted = null;
  let naBefore3s = false, skBefore3s = null, naFirst = null;
  while (Date.now() - t0 < budgetMs) {
    const s = await evalJs(SNAP_PROG);
    const ms = Date.now() - t0;
    const real = [s.threat, s.geoFirst, s.honeyFirst].filter(isReal).length;
    const two = [s.threat, s.geoFirst].filter(isReal).length;
    if (firstData === null && real > 0) firstData = ms;
    if (firstTwo === null && two === 2) firstTwo = ms;
    if (allThree === null && real === 3) allThree = ms;
    if (firstRender === null && s.syncText && s.syncText.indexOf('取数中') < 0) firstRender = ms;
    /* ★B5③ 严格判据：**卡片**离开 SSR 骨架（'—'）的时刻 —— 与同步行文案无关（"重试中"会立刻盖掉"降级值"） */
    if (painted === null && ((s.threat && s.threat !== '—') || (s.geoFirst && s.geoFirst !== '—'))) painted = ms;
    if (ms < 3000) {
      if (s.hasNA) { naBefore3s = true; if (!naFirst) naFirst = { ms: ms, ctx: s.naCtx, sync: s.syncText, honeySkel: s.honeySkeleton }; }
      if (s.honeySkeleton === true) skBefore3s = ms;
    }
    await sleep(120);
  }
  const snap = await evalJs(SNAP_PROG);
  const png = await shot('12-' + tag);
  const run = { name: '12-' + tag, mode, firstData, firstTwo, allThree, firstRender, degShown, painted, naBefore3s, naFirst,
    honeySkeletonAt3s: skBefore3s, snap, apiHits: apiHits.map(nameOf), shot: png, console: consoleMsgs.slice() };
  runs.push(run);
  return run;
};
const r12 = await progRun('progressive-slowhoneypot', 'slow-hp', 18000);
const r13 = await progRun('degraded-nonblocking', 'degraded', 6000);

/* ---------------- 判定 ---------------- */
const checks = [];
const add = (n, ok, d) => checks.push({ name: n, ok: !!ok, detail: d });
const STALE_RE = /上次数据·\d{2}:\d{2}:\d{2}/;
const aliasOk = (u) => /\/api\/public\/[a-z]+\.js(\?|$)/.test(u);
const noBuster = (u) => !/[?&](cb|t|_|r|ts|nocache)=/.test(u) && !/\d{13}/.test(u);

add('★B4 首屏懒加载：首屏只打 3 个端点（alerts+geo+honeypot），改前是 7 个',
  r1.apiHits.length === FIRST && r1.apiHits.every(aliasOk) &&
  FIRST_SET.every((n) => r1.apiHits.some((u) => nameOf(u) === n)),
  JSON.stringify(r1.apiHits));
add('★别名：没有任何随机 cache-buster', r1.apiHits.every(noBuster), JSON.stringify(r1.apiHits.filter((u) => !noBuster(u))));
const pageHtml = fs.readFileSync(path.join(PUB, 'alerts', 'index.html'), 'utf8');
add('★缓存语义：数据绑定层改成 `cache:"no-cache"`（可存 + 每次条件校验）',
  /cache:\s*"no-cache"/.test(pageHtml),
  JSON.stringify({ hasNoCache: /cache:\s*"no-cache"/.test(pageHtml), noStoreSites: (pageHtml.match(/cache:\s*"no-store"/g) || []).length, note: 'no-store 若仍有，属鉴权状态/POST/__xkAdmin 等其它调用点，非本层' }));
add('★新鲜度：同步行时间＝后端 snapshotAt（19:38:12），不是"收到时刻"',
  !!(r1.snap && r1.snap.syncText && r1.snap.syncText.indexOf(SNAP_HHMMSS) >= 0), JSON.stringify(r1.snap && r1.snap.syncText));
add('★新鲜度：边缘缓存龄＝cacheAgeSeconds(7)+Age(5)＝12s',
  !!(r1.snap && r1.snap.syncText && r1.snap.syncText.indexOf('12s') >= 0), JSON.stringify(r1.snap && r1.snap.syncText));
add('正常态：威胁等级=高 且无任何"上次数据"标注',
  !!(r1.snap && r1.snap.threatLevel === '高' && r1.snap.staleCount === 0), JSON.stringify({ lv: r1.snap && r1.snap.threatLevel, n: r1.snap && r1.snap.staleCount }));
add('B2 回归：慢响应 15s 不再被判"读不到"（上限 25s 生效）',
  !!(r2.snap && r2.snap.threatLevel === '高' && r2.elapsedMs >= 14000), JSON.stringify({ lv: r2.snap && r2.snap.threatLevel, ms: r2.elapsedMs }));
/* 场景 03 的**不变式**（不依赖"存储一定为空"的时序假设）：
   取不到 ⇒ 必须出现"读不到"；若用了任何旧值，必须**逐处标注**（卡角 + 同步行明说），不许冒充本次真值。 */
const r3inv = !!(r3.snap && r3.snap.hasDuBuDao && (
  r3.snap.staleCount === 0 ||
  (r3.snap.syncText && r3.snap.syncText.indexOf('上次数据') >= 0 && r3.snap.staleNotes.every((t) => STALE_RE.test(t)))));
add('B2 回归：取不到 ⇒ 显示"读不到"；若用了旧值必须逐处标注（不许冒充本次真值）', r3inv, JSON.stringify(r3.snap));
add('B2 回归：失败但有旧值 ⇒ 显示上次数据 + 卡角「上次数据·时间」',
  !!(r4.snap && r4.snap.threatLevel === '高' && r4.snap.staleCount >= 1 && r4.snap.staleNotes.every((t) => STALE_RE.test(t))),
  JSON.stringify({ lv: r4.snap && r4.snap.threatLevel, notes: r4.snap && r4.snap.staleNotes }));
add('B2 回归："重试中"与"读不到"可分辨', r5.syncSeq.some((t) => t.indexOf('重试中') >= 0), JSON.stringify(r5.syncSeq.slice(0, 4)));
add('★429 头路径：秒数取 `Retry-After: 7`',
  !!(r6.snap && r6.snap.syncText && r6.snap.syncText.indexOf('7 秒后可重试') >= 0), JSON.stringify(r6.snap && r6.snap.syncText));
add('★429 body 路径：秒数取 `body.retryAfter: 9`',
  !!(r7.snap && r7.snap.syncText && r7.snap.syncText.indexOf('9 秒后可重试') >= 0), JSON.stringify(r7.snap && r7.snap.syncText));
add('★429 无秒数：走默认 60 且**注明"后端未给秒数"**（不把默认当真值）',
  !!(r8.snap && r8.snap.syncText && r8.snap.syncText.indexOf('60 秒后可重试') >= 0 && r8.snap.syncText.indexOf('后端未给秒数') >= 0),
  JSON.stringify(r8.snap && r8.snap.syncText));
add('★429 文案与"不可达/读不到"可分辨（出现"被限流"，不当成"本次不可达"）',
  !!(r8.snap && r8.snap.syncText && r8.snap.syncText.indexOf('被限流') >= 0 && r8.snap.syncText.indexOf('本次不可达') < 0),
  JSON.stringify(r8.snap && r8.snap.syncText));
add('★429 不立刻重试：本轮请求数＝首屏 3 个（不做"降级补一次"）',
  r8.apiHits.length === FIRST, 'hits=' + r8.apiHits.length + ' ' + JSON.stringify(r8.apiHits));
add('★429 后冷却：同页触发 visibilitychange 也不再发请求，且同步行写明"冷却中"',
  !!(r6.cooldown && r6.cooldown.grew === 0 && r6.cooldown.syncText && r6.cooldown.syncText.indexOf('冷却中') >= 0),
  JSON.stringify(r6.cooldown));
add('★429 + 有旧值 ⇒ 优先显示上次数据（不是空白"读不到"）',
  !!(r9.snap && r9.snap.threatLevel === '高' && r9.snap.syncText && r9.snap.syncText.indexOf('上次数据') >= 0),
  JSON.stringify({ lv: r9.snap && r9.snap.threatLevel, sync: r9.snap && r9.snap.syncText }));
add('★429 卡角标注写的是"被限流"（不是"上次数据"）',
  !!(r9.snap && r9.snap.staleDbg && r9.snap.staleDbg.marked && r9.snap.staleDbg.marked.some((m) => String(m).indexOf(':rate') > 0)),
  JSON.stringify(r9.snap && r9.snap.staleDbg && r9.snap.staleDbg.marked));
add('★B4 首屏不取后续端点：切 tab 之前 webstats/overview/stories 一个请求都没有',
  r11.first.indexOf('webstats') < 0 && r11.first.indexOf('overview') < 0 && r11.first.indexOf('stories') < 0, JSON.stringify(r11.first));
add('★B4 切 tab 才取：点「攻击图谱」只补 audit（alerts/honeypot/geo 已在首屏）',
  JSON.stringify(r11.phases[0] && r11.phases[0].added) === JSON.stringify(['audit']), JSON.stringify(r11.phases));
add('★B4 切 tab 才取：点「威胁矩阵」补 0 个（矩阵只用 alerts，已在首屏）',
  !!(r11.phases[1] && r11.phases[1].added.length === 0), JSON.stringify(r11.phases[1]));
add('★B4 切 tab 才取：点「数据统计」补 overview/stories/webstats（audit 已在图谱取过 ⇒ 不重复请求）',
  JSON.stringify(r11.phases[2] && r11.phases[2].added) === JSON.stringify(['overview', 'stories', 'webstats']), JSON.stringify(r11.phases[2]));
add('★B4 懒加载后该 tab 的数据真的渲染了（故事线"候选来源"已出数）',
  !!(r11.storyTag && r11.storyTag.indexOf('候选来源') >= 0), JSON.stringify(r11.storyTag));
add('★B4 HOLO 汇总句：audit 未取时**不写"读不到"**且省略护栏分句；取到后补齐"护栏拦下"',
  !!(r11.holo1 && r11.holo1.indexOf('读不到') < 0 && r11.holo1.indexOf('蜜罐累计事件') >= 0 && r11.holo1.indexOf('护栏拦下') < 0 &&
     r11.holo2 && r11.holo2.indexOf('护栏拦下') >= 0), JSON.stringify({ before: r11.holo1, after: r11.holo2 }));
add('★B4b 首页 0 请求：`/` 首屏不打任何 /api/public/*（1440 与 390 两档都是 0）',
  home1440.hits.length === 0 && home390.hits.length === 0,
  JSON.stringify({ v1440: home1440.hits, v390: home390.hits }));
add('★B4b 首页 0 请求下可见文本非空且**不含"读不到"**（不制造假缺失）',
  home1440.bodyLen > 0 && !home1440.hasDuBuDao && !home390.hasDuBuDao,
  JSON.stringify({ len1440: home1440.bodyLen, du1440: home1440.hasDuBuDao, du390: home390.hasDuBuDao }));
/* 可见真值不受影响：与改前基线比**确定性可见真值子集**（首页是动画页 ⇒ 不用整屏 sha 当判据，
   逐像素差另由 PIL 单独算并写进报告；这里比的是"api-bind 在首页会写的/静态可见真值"） */
let baseDiff = null, baseOk = false, baseName = path.basename(BASELINE_HOME);
try {
  const base = JSON.parse(fs.readFileSync(BASELINE_HOME, 'utf8'));
  const cmp = [];
  const KEYS = ['counters', 'holo', 'crtStatus', 'nav', 'screenBox', 'statsBox'];
  base.runs.forEach(function (b) {
    const a = [home1440, home390].filter((x) => x.vp === b.vp)[0];
    if (!a) { cmp.push(b.vp + ': 本次缺该视口'); return; }
    KEYS.forEach(function (k) {
      if (JSON.stringify(a[k]) !== JSON.stringify(b[k])) cmp.push(b.vp + '.' + k + ': ' + JSON.stringify(b[k]) + ' → ' + JSON.stringify(a[k]));
    });
  });
  baseDiff = cmp; baseOk = cmp.length === 0;
} catch (e) { baseDiff = '基线不可读：' + String((e && e.message) || e); baseOk = false; }
add('★B4b 首页可见真值不受影响：与改前基线（' + baseName + '）的确定性可见真值子集逐项一致 —— 计数器／CRT 状态行／HOLO 文案／导航项／.screen 与 .stats 布局盒',
  baseOk, JSON.stringify(baseDiff));
add('无 JS 绑定异常（window.__xkBindErr 为空）', runs.every((r) => !r.snap || !r.snap.bindErr), JSON.stringify(runs.map((r) => r.snap && r.snap.bindErr)));
add('★B5 渐进渲染①：honeypot 被拖到 15s 时，alerts+geo 两张卡的真值 <3s 就出（改前＝等最慢那条＝15s）',
  r12.firstTwo !== null && r12.firstTwo < 3000,
  JSON.stringify({ firstData: r12.firstData, firstTwo: r12.firstTwo, allThree: r12.allThree }));
add('★B5 渐进渲染②：未到的 honeypot 卡 3s 内保持骨架（.sk 仍在），且 3s 内**不出现"读不到"**',
  r12.honeySkeletonAt3s !== null && r12.naBefore3s === false,
  JSON.stringify({ honeySkeletonAt3s: r12.honeySkeletonAt3s, naBefore3s: r12.naBefore3s, naFirst: r12.naFirst, snap: r12.snap }));
add('★B5 渐进渲染③：降级时不阻塞首屏 —— **卡片**离开骨架（— 占位）的时间 <1.2s；改前＝等 1.5s 定时器 + 补请求之后才渲染',
  r13.painted !== null && r13.painted < 1200,
  JSON.stringify({ painted: r13.painted, degShown: r13.degShown, firstRender: r13.firstRender, sync: r13.snap && r13.snap.syncText }));
add('★B5 对账：三张卡"全到齐"的时间仍应是慢端点到达之后（≥14s，不假装提前都有数据）',
  r12.allThree !== null && r12.allThree >= 14000, JSON.stringify({ allThree: r12.allThree, firstTwo: r12.firstTwo }));
add('★别名 404 回落：先打别名、再打旧路径（每端点各一次，只回落一次）',
  r10.apiHits.filter((u) => /\.js(\?|$)/.test(u)).length === FIRST && r10.apiHits.filter((u) => !/\.js(\?|$)/.test(u)).length === FIRST,
  JSON.stringify({ alias: r10.apiHits.filter((u) => /\.js(\?|$)/.test(u)).length, old: r10.apiHits.filter((u) => !/\.js(\?|$)/.test(u)).length }));
add('★别名 404 回落：页面仍渲染出真值（不是一片"读不到"）',
  !!(r10.snap && r10.snap.threatLevel === '高'), JSON.stringify(r10.snap && r10.snap.threatLevel));
add('★别名 404 回落：同步行如实说明"旧路径回落"＋时刻用 generatedAt 兜底（不冒充 snapshotAt）',
  !!(r10.snap && r10.snap.syncText && r10.snap.syncText.indexOf('旧路径回落') >= 0 &&
     r10.snap.syncText.indexOf('generatedAt') >= 0 && r10.snap.syncText.indexOf(SNAP_HHMMSS) >= 0),
  JSON.stringify(r10.snap && r10.snap.syncText));
add('console 0（阻断性）', runs.every((r) => r.console.filter((c) => c.startsWith('EXCEPTION') || c.startsWith('error')).length === 0),
  JSON.stringify(runs.map((r) => r.console.length)));

const pass = checks.filter((c) => c.ok).length;
const report = { at: new Date().toISOString(), label: LABEL, servedFrom: PUB, base: BASE, api: API, checks, summary: { pass, total: checks.length }, runs };
fs.writeFileSync(REPORT, JSON.stringify(report, null, 1), 'utf8');
for (const c of checks) console.log((c.ok ? '  [PASS] ' : '  [FAIL] ') + c.name + (c.ok ? '' : '   << ' + c.detail));
console.log('\nB2+B3 探针（' + LABEL + '，产物=' + PUB + '）：' + pass + '/' + checks.length + ' PASS');
console.log('报告 →', REPORT);
try { ws.close(); } catch { }
try { child.kill(); } catch { }
server.close();
process.exit(pass === checks.length ? 0 : 1);
