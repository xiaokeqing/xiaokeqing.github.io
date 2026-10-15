/* T31 开场六阶段 · 前 1.5s 逐帧取证（窗口 Q，2026-10-15）
   node _dev/probe-boot-phases.mjs
   做什么：CDP 连真浏览器打开主页，每 100ms 采一次 window.__xkBoot.phase / <html data-xk-boot> /
   .dock 是否可见 / #charCanvas 不透明像素，并在关键点截图。
   输出：_shots/boot-phases.json + _shots/boot-*.png
   口径：不许编数字 —— 下面每一行都是页面自己报的 phase 与当帧画布实测像素。
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
const PORT = 8841, CDP = 9363, VW = 1280, VH = 900;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8', '.woff2': 'font/woff2' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

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
  const udd = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-boot-'));
  const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
    '--no-default-browser-check', '--disable-extensions', '--mute-audio',
    `--remote-debugging-port=${CDP}`, `--user-data-dir=${udd}`, `--window-size=${VW},${VH}`, 'about:blank'], { stdio: 'ignore' });
  let target = null;
  for (let i = 0; i < 60 && !target; i++) {
    await sleep(400);
    try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); } catch { }
  }
  if (!target) throw new Error('连不上 Edge 调试端口');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  let events = [];
  ws.addEventListener('message', (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.method === 'Network.requestWillBeSent') events.push({ t: Date.now(), url: m.params.request.url });
  });
  await rpc(ws, 'Page.enable'); await rpc(ws, 'Runtime.enable'); await rpc(ws, 'Network.enable');
  await rpc(ws, 'Emulation.setDeviceMetricsOverride', { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
  const ev2 = async (expr) => { const r = await rpc(ws, 'Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: false }); return r.result?.value; };
  const shot = async (name) => { const r = await rpc(ws, 'Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    fs.writeFileSync(path.join(OUT, name + '.png'), Buffer.from(r.data, 'base64')); return name + '.png'; };

  const SAMPLE = `(function(){
    var b = window.__xkBoot || null;
    var dock = document.getElementById('dock');
    var cs = dock ? getComputedStyle(dock) : null;
    var c = document.getElementById('charCanvas');
    var opaque = -1;
    try { if(c && c.width){ var d=c.getContext('2d').getImageData(0,0,c.width,c.height).data,on=0;
      for(var i=3;i<d.length;i+=4){ if(d[i]>8) on++; } opaque = on; } } catch(e){ opaque = 'err'; }
    var cb = document.getElementById('crtBoot');
    return JSON.stringify({ phase:(b?b.phase:null), attr:document.documentElement.getAttribute('data-xk-boot'),
      log:(b&&b.log)?b.log.length:0, marks:(b&&b.marks)?b.marks:null,
      dockOpacity: cs?cs.opacity:null, dockWait: dock?dock.className:null, opaque:opaque,
      crtBoot: cb?getComputedStyle(cb).display:'absent' });
  })()`;

  const t0 = Date.now();
  await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/index.html` });
  const rows = [];
  for (let i = 0; i < 16; i++) {
    const at = Date.now() - t0;
    const s = await ev2(SAMPLE);
    let o = null; try { o = JSON.parse(s); } catch { o = { raw: s }; }
    rows.push({ atMs: at, ...o });
    if ([0, 2, 4, 6, 9, 12, 15].includes(i)) { await shot('boot-' + String(at).padStart(4, '0') + 'ms'); }
    await sleep(100);
  }
  const firstReqs = events.slice(0, 8).map((e) => ({ atMs: e.t - t0, url: e.url.replace(`http://127.0.0.1:${PORT}`, '') }));
  fs.writeFileSync(path.join(OUT, 'boot-phases.json'), JSON.stringify({ rows, firstReqs }, null, 1), 'utf8');
  console.log('== T31 开场六阶段 · 前 1.5s 采样（每 100ms）==');
  for (const r of rows) console.log(`  ${String(r.atMs).padStart(4)}ms  phase=${String(r.phase)}  data-xk-boot=${r.attr}  dock.opacity=${r.dockOpacity}  crtBoot=${r.crtBoot}  画布不透明像素=${r.opaque}  log=${r.log}`);
  console.log('\n前 8 个请求：');
  for (const q of firstReqs) console.log(`  +${String(q.atMs).padStart(4)}ms  ${q.url}`);
  console.log('\n-> _shots/boot-phases.json + _shots/boot-*.png');
  ws.close(); child.kill(); server.close();
  await sleep(300);
  try { fs.rmSync(udd, { recursive: true, force: true }); } catch { }
}
main().catch((e) => { console.error('FAILED: ' + e.message); process.exit(1); });
