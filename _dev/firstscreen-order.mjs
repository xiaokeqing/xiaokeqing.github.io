/* 首屏关键资源加载顺序 + 首屏可交互时间 + 预取请求清单（P0-④ 的验收件）
   用法：node _dev/firstscreen-order.mjs [--page=home] [--ms=9000]
   输出：_shots/firstscreen-order.json（+ 控制台表格）
   数据来源：① CDP Network 事件时间戳（相对导航）② 页面自报 window.__xkFirstPaint.order
             ③ window.__xkId.prefetch（空闲预取清单）④ #dock 数据属性（导航栏入场=首屏可交互） */
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
const PAGE = argOf('page') || 'home';
const MS = Number(argOf('ms') || 9000);
const URL_OF = { home: '', alerts: 'alerts/', posts: 'posts/', ai: 'ai/', test: 'test/' }[PAGE] ?? '';

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p.endsWith('/')) { p += 'index.html'; }
  const f = path.join(PUB, p);
  if (!f.startsWith(PUB) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end('nf'); return; }
  res.writeHead(200, { 'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(PORT, '127.0.0.1', r));

const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-order-'));
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
const reqs = [];
let t0 = 0;
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waits.has(m.id)) { const w = waits.get(m.id); waits.delete(m.id); m.error ? w.rej(new Error(JSON.stringify(m.error))) : w.res(m.result); return; }
  if (m.method === 'Network.requestWillBeSent') {
    const u = m.params.request.url.replace(`http://127.0.0.1:${PORT}`, '');
    if (!t0) { t0 = m.params.timestamp * 1000; }   /* CDP 的 timestamp 是秒；以"第一个请求"为 0 点 */
    reqs.push({ url: u, kind: m.params.type || '', start: Math.round((m.params.timestamp * 1000) - t0), end: null, bytes: null, status: null, by: m.params.initiator ? m.params.initiator.type : null });
  }
  if (m.method === 'Network.responseReceived') {
    const u = m.params.response.url.replace(`http://127.0.0.1:${PORT}`, '');
    const r = reqs.filter((x) => x.url === u && x.end === null)[0]; if (r) { r.status = m.params.response.status; r.enc = Math.round((m.params.response.encodedDataLength || 0)); }
  }
  if (m.method === 'Network.loadingFinished') {
    const r = reqs.filter((x) => x.requestId === m.params.requestId)[0];
    const x = reqs.filter((y) => y.end === null && y.status != null)[0];
    void r; void x;
    for (let i = reqs.length - 1; i >= 0; i--) { if (reqs[i].end === null && reqs[i].status != null) { reqs[i].end = Math.round((m.params.timestamp * 1000) - t0); reqs[i].bytes = m.params.encodedDataLength; break; } }
  }
});
function rpc(method, params = {}) { const id = ++mid; return new Promise((res, rej) => { waits.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); }); }
await rpc('Page.enable'); await rpc('Runtime.enable'); await rpc('Network.enable');
const evalJs = async (e) => { const r = await rpc('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true }); return r && r.result ? r.result.value : null; };

t0 = 0;
await rpc('Page.navigate', { url: `http://127.0.0.1:${PORT}/${URL_OF}` });
await sleep(MS);

const page = await evalJs(`(function(){
  var nav = performance.getEntriesByType('navigation')[0] || {};
  var res = performance.getEntriesByType('resource').map(function(r){ return { url:r.name.replace(location.origin,''), start:Math.round(r.startTime), end:Math.round(r.responseEnd), bytes:r.encodedBodySize||0, initiator:r.initiatorType }; });
  var dk = document.getElementById('dock');
  var d = window.__xkId || {};
  return {
    path: location.pathname,
    nav: { domInteractive: Math.round(nav.domInteractive||0), domContentLoaded: Math.round(nav.domContentLoadedEventEnd||0), loadEvent: Math.round(nav.loadEventEnd||0), fcp: (function(){var p=performance.getEntriesByName('first-contentful-paint')[0];return p?Math.round(p.startTime):null;})() },
    dockIn: dk ? { at: dk.getAttribute('data-xk-dock-at'), why: dk.getAttribute('data-xk-dock-in') } : null,
    firstPaint: window.__xkFirstPaint || null,
    bootPhase: (window.__xkBoot && window.__xkBoot.phase) || null,
    prefetch: d.prefetch || [], prefetchNote: d.prefetchNote || null,
    sound: d.sound, emo: d.emo, loginHidden: (document.getElementById('xkLoginBtn')||{}).hidden,
    resources: res
  };
})()`);

const report = { page: PAGE, url: '/' + URL_OF, windowMs: MS, capturedAt: new Date().toISOString(), page, network: reqs };
fs.writeFileSync(path.join(OUT, 'firstscreen-order.json'), JSON.stringify(report, null, 1), 'utf8');

console.log('== 首屏关键资源加载顺序（' + PAGE + ' · 1280×900 · CDP 真实网络）==');
const KEY = ['desk.webp', 'lab.webp', 'opening', 'subtitle_frame_big.webp', 'manifest.json', 'video-manifest.json', 'bank.json'];
const rows = (page.network || reqs).filter((r) => KEY.some((k) => r.url.indexOf(k) >= 0));
console.log('  资源'.padEnd(46) + '开始(ms)  完成(ms)  状态  字节');
for (const r of rows) {
  console.log('  ' + r.url.padEnd(44) + String(r.start).padStart(7) + '  ' + String(r.end == null ? '-' : r.end).padStart(8) + '  ' + String(r.status ?? '-').padStart(5) + '  ' + String(r.bytes ?? r.enc ?? '-').padStart(7));
}
console.log('\n  页面自报 decode 顺序 window.__xkFirstPaint.order =', JSON.stringify(page.firstPaint && page.firstPaint.order));
console.log('  首屏可交互（导航栏入场 #dock[data-xk-dock-in]）=', JSON.stringify(page.dockIn));
console.log('  导航时间轴 =', JSON.stringify(page.nav));
console.log('  空闲预取清单 =', JSON.stringify(page.prefetch), page.prefetchNote || '');
console.log('\n报告 →', path.join(OUT, 'firstscreen-order.json'));
try { ws.close(); } catch { }
try { child.kill(); } catch { }
server.close();
process.exit(0);
