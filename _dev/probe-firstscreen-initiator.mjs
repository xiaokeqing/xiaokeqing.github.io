/* 诊断工装（窗口 Q，2026-10-15）：逐页量首屏资产，并抓每个请求的**发起处**（initiator stack）
   node _dev/probe-firstscreen-initiator.mjs [window_ms]
   输出：_shots/probe-firstscreen.json
   为什么需要它：gate-firstscreen.mjs 只量总字节，不告诉你"是谁拉的"。
   T8 之后 ai 页 2314KB > 1650KB 预算，必须用 initiator 证明是哪一段撑大的，不许猜。
*/
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = 'F:\\7AAA\\AI\\blog';
const PUB = path.join(ROOT, 'public');
const OUT = path.join(ROOT, '_shots');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8831, CDP = 9362, VW = 1280, VH = 900;
const WINDOW_MS = Number(process.argv[2] || 6000);
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8', '.woff2': 'font/woff2', '.m4a': 'audio/mp4' };
const ASSET_RE = /\.(webp|png|jpe?g|gif|svg|ico|css|js|woff2?|wav|opus|m4a)$/i;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

const PAGES = [
  { name: 'home', url: 'index.html' },
  { name: 'monitor', url: 'alerts/' },
  { name: 'notes', url: 'posts/' },
  { name: 'labs', url: 'labs/' },
  { name: 'about', url: 'about/' },
  { name: 'ai', url: 'ai/' },
];

function byteOf(url) {
  const rel = url.split('?')[0].split('#')[0];
  const f = path.join(PUB, rel.replace(/^\//, '').replace(/\//g, path.sep));
  return (fs.existsSync(f) && fs.statSync(f).isFile()) ? fs.statSync(f).size : 0;
}

let nid = 0;
const rpc = (ws, m, p = {}) => new Promise((resolve, reject) => {
  const id = ++nid;
  const on = (ev) => { let x; try { x = JSON.parse(ev.data); } catch { return; }
    if (x.id !== id) return; ws.removeEventListener('message', on);
    x.error ? reject(new Error(m + ': ' + JSON.stringify(x.error))) : resolve(x.result); };
  ws.addEventListener('message', on);
  ws.send(JSON.stringify({ id, method: m, params: p }));
});

async function main() {
  const server = http.createServer((req, res) => {
    let p = decodeURIComponent(req.url.split('?')[0]);
    if (p.endsWith('/')) p += 'index.html';
    const f = path.join(PUB, p);
    if (!f.startsWith(PUB) || !fs.existsSync(f) || !fs.statSync(f).isFile()) { res.writeHead(404); res.end('404'); return; }
    res.writeHead(200, { 'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
  const udd = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-probe-'));
  const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
    '--no-default-browser-check', '--disable-extensions', '--mute-audio',
    `--remote-debugging-port=${CDP}`, `--user-data-dir=${udd}`, `--window-size=${VW},${VH}`, 'about:blank'], { stdio: 'ignore' });
  let target = null;
  for (let i = 0; i < 60 && !target; i++) {
    await sleep(400);
    try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); } catch { }
  }
  if (!target) throw new Error('cannot reach Edge debug port');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });

  let events = [], consoleMsgs = [];
  ws.addEventListener('message', (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.method === 'Network.requestWillBeSent') events.push({ kind: 'req', t: Date.now(), url: m.params.request.url, initiator: m.params.initiator });
    if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type))
      consoleMsgs.push(m.params.type + ': ' + (m.params.args || []).map((a) => a.value || a.description || '').join(' '));
    if (m.method === 'Runtime.exceptionThrown')
      consoleMsgs.push('EXCEPTION: ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
  });
  await rpc(ws, 'Page.enable'); await rpc(ws, 'Runtime.enable'); await rpc(ws, 'Network.enable');
  await rpc(ws, 'Emulation.setDeviceMetricsOverride', { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
  const ev = async (expr, awaitPromise = true) => {
    const r = await rpc(ws, 'Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise });
    if (r.exceptionDetails) throw new Error('page threw: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result?.value;
  };

  const out = { windowMs: WINDOW_MS, pages: [] };
  for (const p of PAGES) {
    events = []; consoleMsgs = [];
    const t0 = Date.now();
    await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/${p.url}` });
    await sleep(WINDOW_MS);
    const vis = await ev(`(function(){
      function info(id){ var e=document.getElementById(id); if(!e) return 'absent';
        var r=e.getBoundingClientRect(); var cs=getComputedStyle(e);
        return { w:Math.round(r.width), h:Math.round(r.height), display:cs.display, visibility:cs.visibility }; }
      return JSON.stringify({ viewOn:(document.querySelector('.view.on')||{id:null}).id,
        charCanvas:info('charCanvas'), phoneCanvas:info('phoneCanvas'), avCanvas:info('avCanvas'),
        phoneEl:info('phone'), sm:(window.__xkSM?{on:window.__xkSM.on,tookOver:!!window.__xkSM.tookOver,cur:window.__xkSM.cur,
          atlas:{loaded:window.__xkSM.atlas?window.__xkSM.atlas.loaded:null,pending:window.__xkSM.atlas?window.__xkSM.atlas.pending:null},
          reasons:(window.__xkSM.reasons?window.__xkSM.reasons():null)}:null) }); })()`);
    const rows = [];
    for (const e of events) {
      if (!ASSET_RE.test(e.url.split('?')[0])) continue;
      const rel = e.url.replace(`http://127.0.0.1:${PORT}`, '').split('?')[0].split('#')[0];
      const st = e.initiator && e.initiator.stack && e.initiator.stack.callFrames && e.initiator.stack.callFrames[0];
      rows.push({ url: rel, bytes: byteOf(rel), atMs: e.t - t0, type: e.initiator?.type || null,
        from: st ? `${st.functionName || '(anon)'} @ ${(st.url || '').split('/').pop()}:${st.lineNumber + 1}` : (e.initiator?.url || null) });
    }
    const dedup = {}; for (const r of rows) { const k = r.url; if (!dedup[k] || dedup[k].atMs > r.atMs) dedup[k] = dedup[k] || r; }
    const uniq = Object.values(dedup).sort((a, b) => a.atMs - b.atMs);
    const in1500 = uniq.filter((r) => r.atMs <= 1500);
    const inWin = uniq.filter((r) => r.atMs <= WINDOW_MS);
    const sum = (a) => a.reduce((s, r) => s + r.bytes, 0);
    out.pages.push({ page: p.name, url: p.url, firstScreen1_5s_bytes: sum(in1500), windowBytes: sum(inWin), console: consoleMsgs, dom: JSON.parse(vis), assets: uniq });
    console.log(`== ${p.name} (${p.url})  1.5s=${(sum(in1500) / 1024).toFixed(0)}KB  ${WINDOW_MS}ms=${(sum(inWin) / 1024).toFixed(0)}KB  console=${consoleMsgs.length}`);
    for (const r of uniq) console.log(`   ${(r.bytes / 1024).toFixed(0).padStart(6)}KB  +${String(r.atMs).padStart(5)}ms  ${r.url}   <- ${r.type} ${r.from}`);
    const d = JSON.parse(vis);
    console.log(`   view.on=${d.viewOn} charCanvas=${JSON.stringify(d.charCanvas)} phoneCanvas=${JSON.stringify(d.phoneCanvas)} sm=${JSON.stringify(d.sm && d.sm.atlas)}`);
  }
  fs.writeFileSync(path.join(OUT, 'probe-firstscreen.json'), JSON.stringify(out, null, 1), 'utf8');
  console.log('\n-> _shots/probe-firstscreen.json');
  ws.close(); child.kill(); server.close();
  await sleep(300);
  try { fs.rmSync(udd, { recursive: true, force: true }); } catch { }
}
main().catch((e) => { console.error('FAILED: ' + e.message); process.exit(1); });
