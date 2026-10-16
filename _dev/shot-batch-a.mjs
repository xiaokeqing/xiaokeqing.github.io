/* 批次 A 截图取证：桌面 1280×900 + 手机 375/390/414 各一张（五页），
   外加"访客视角 / 触发自用入口后"两张（主页）。
   用法：node _dev/shot-batch-a.mjs [--prefix=batchA]
   输出：_shots/<prefix>-<page>-<w>x<h>.png、_shots/<prefix>-home-admin.png、_shots/<prefix>-report.json
   口径：跟 _dev/gate-firstscreen.mjs 同一套（本机 http.server + Edge headless + CDP），
        给站主看观感的截图**不带** ?wb_noblur=1。 */
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = 'F:\\7AAA\\AI\\blog';
const PUB = path.join(ROOT, 'public');
const OUT = path.join(ROOT, '_shots');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8811, CDP = 9361;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.xml': 'application/xml', '.m4a': 'audio/mp4', '.webm': 'audio/webm' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const argOf = (k) => { const a = process.argv.find((x) => x.startsWith('--' + k + '=')); return a ? a.split('=')[1] : null; };
const PREFIX = argOf('prefix') || 'batchA';
fs.mkdirSync(OUT, { recursive: true });

const PAGES = [['home', ''], ['alerts', 'alerts/'], ['posts', 'posts/'], ['ai', 'ai/'], ['test', 'test/']];
const VIEWPORTS = [
  { name: 'desktop', w: 1280, h: 900, mobile: false },
  { name: 'phone375', w: 375, h: 812, mobile: true },
  { name: 'phone390', w: 390, h: 844, mobile: true },
  { name: 'phone414', w: 414, h: 896, mobile: true },
];

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
const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-shot-a-'));
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
let mid = 0; const waits = new Map(); const events = [];
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waits.has(m.id)) { const w = waits.get(m.id); waits.delete(m.id); m.error ? w.rej(new Error(JSON.stringify(m.error))) : w.res(m.result); }
  else if (m.method) { events.push(m); }
});
function rpc(method, params = {}) {
  const id = ++mid;
  return new Promise((res, rej) => { waits.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); });
}
await rpc('Page.enable'); await rpc('Runtime.enable'); await rpc('Network.enable');

async function evalJs(expr) {
  const r = await rpc('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  return r && r.result ? r.result.value : null;
}
async function shot(file) {
  const r = await rpc('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  fs.writeFileSync(path.join(OUT, file), Buffer.from(r.data, 'base64'));
  return fs.statSync(path.join(OUT, file)).size;
}

const report = { prefix: PREFIX, shots: [], checks: [] };
for (const vp of VIEWPORTS) {
  await rpc('Emulation.setDeviceMetricsOverride', { width: vp.w, height: vp.h, deviceScaleFactor: 1, mobile: vp.mobile });
  for (const [name, url] of PAGES) {
    await rpc('Page.navigate', { url: `http://127.0.0.1:${PORT}/${url}` });
    await sleep(2600);
    const file = `${PREFIX}-${name}-${vp.w}x${vp.h}.png`;
    const bytes = await shot(file);
    const probe = await evalJs(`(function(){
      var d=window.__xkId||{}, s=document.getElementById('xkSndBtn'), l=document.getElementById('xkLoginBtn');
      var r=s?s.getBoundingClientRect():null;
      return { path:location.pathname, sound:d.sound, emo:d.emo, admin:!!d.admin,
               kp:!!window.KurisuPlayer, sg:!!(window.KurisuPlayer&&window.KurisuPlayer.speakGroup),
               playerAt:d.playerAt||null, lg:Object.keys(window.__xkLineGroup||{}).length,
               sndText:s?s.textContent:null, sndTitle:s?s.title:null,
               loginHidden:l?l.hidden:null, loginText:l?l.textContent:null,
               cardLeft:r?Math.round(r.left):null, cardTop:r?Math.round(r.top):null,
               dockTop:(function(){var dk=document.getElementById('dock');return dk?Math.round(dk.getBoundingClientRect().top):null;})(),
               errs:(d.errors||[]).slice(-3) };})()`);
    report.shots.push({ page: name, viewport: vp.name, file, bytes, probe });
    console.log(`  ${vp.name.padEnd(8)} ${name.padEnd(7)} ${String(bytes).padStart(7)} B  sound=${probe && probe.sound} loginHidden=${probe && probe.loginHidden} dockTop=${probe && probe.dockTop} kp=${probe && probe.kp} sg=${probe && probe.sg} playerAt=${probe && probe.playerAt} lg=${probe && probe.lg} idErrs=${JSON.stringify((probe && probe.errs) || [])}`);
  }
}

/* 访客视角 / 触发自用入口后（主页，桌面） */
await rpc('Emulation.setDeviceMetricsOverride', { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
await rpc('Page.navigate', { url: `http://127.0.0.1:${PORT}/` });
await sleep(2600);
report.shots.push({ page: 'home', viewport: 'visitor', file: `${PREFIX}-home-visitor.png`, bytes: await shot(`${PREFIX}-home-visitor.png`) });
await rpc('Page.navigate', { url: `http://127.0.0.1:${PORT}/?admin=1` });
await sleep(2600);
const adminProbe = await evalJs(`(function(){var l=document.getElementById('xkLoginBtn'),d=window.__xkId||{};return {loginHidden:l?l.hidden:null,loginText:l?l.textContent:null,admin:!!d.admin,revealWhy:d.revealWhy};})()`);
report.shots.push({ page: 'home', viewport: 'admin', file: `${PREFIX}-home-admin.png`, bytes: await shot(`${PREFIX}-home-admin.png`), probe: adminProbe });
console.log('  admin    home   ', JSON.stringify(adminProbe));

/* 长按面板（主页，桌面）：直接用真实指针事件压 700ms */
await rpc('Page.navigate', { url: `http://127.0.0.1:${PORT}/` });
await sleep(2600);
await evalJs(`(function(){var av=document.getElementById('xkIdAv');var r=av.getBoundingClientRect();
  var opt={bubbles:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,pointerId:1,pointerType:'mouse'};
  av.dispatchEvent(new PointerEvent('pointerdown',opt));return true;})()`);
await sleep(800);
const panelOpen = await evalJs(`(function(){var p=document.getElementById('xkIdPanel');return p?p.classList.contains('open'):null;})()`);
await evalJs(`(function(){var av=document.getElementById('xkIdAv');var r=av.getBoundingClientRect();
  av.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,clientX:r.left+5,clientY:r.top+5,pointerId:1,pointerType:'mouse'}));return true;})()`);
await sleep(300);
report.shots.push({ page: 'home', viewport: 'panel', file: `${PREFIX}-home-panel.png`, bytes: await shot(`${PREFIX}-home-panel.png`), panelOpen });
console.log('  长按 500ms 后面板 open =', panelOpen);

fs.writeFileSync(path.join(OUT, PREFIX + '-shot-report.json'), JSON.stringify(report, null, 1), 'utf8');
try { ws.close(); } catch { }
try { child.kill(); } catch { }
server.close();
console.log('\n报告 →', path.join(OUT, PREFIX + '-shot-report.json'));
process.exit(0);
