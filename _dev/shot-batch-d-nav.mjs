/* 批次 D 取证：手机端导航从底部移到**头部**（头像卡下方一行）。
   检查：① dock 在视口上半（top < 视口高/2）② 与左上角头像卡**不重叠** ③ 没有横向溢出
        ④ 触控目标 >=44px ⑤ 桌面（1280）仍是左侧竖排
   用法：node _dev/shot-batch-d-nav.mjs [--prefix=batchD]
   输出：_shots/<prefix>-<page>-<w>x<h>.png + _shots/<prefix>-nav-report.json */
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = 'F:\\7AAA\\AI\\blog';
const PUB = path.join(ROOT, 'public');
const OUT = path.join(ROOT, '_shots');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8825, CDP = 9375;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.webm': 'video/webm' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const argOf = (k) => { const a = process.argv.find((x) => x.startsWith('--' + k + '=')); return a ? a.slice(k.length + 3) : null; };
const PREFIX = argOf('prefix') || 'batchD';
fs.mkdirSync(OUT, { recursive: true });

const PAGES = [['home', ''], ['alerts', 'alerts/'], ['posts', 'posts/'], ['ai', 'ai/'], ['test', 'test/']];
const VPS = [
  { name: 'desktop', w: 1280, h: 900, mobile: false },
  { name: 'phone375', w: 375, h: 812, mobile: true },
  { name: 'phone390', w: 390, h: 844, mobile: true },
  { name: 'phone414', w: 414, h: 896, mobile: true }
];

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p.endsWith('/')) { p += 'index.html'; }
  const f = path.join(PUB, p);
  if (!f.startsWith(PUB) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end('nf'); return; }
  res.writeHead(200, { 'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(PORT, '127.0.0.1', r));

const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-navd-'));
const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  '--no-default-browser-check', '--disable-extensions', '--mute-audio', '--autoplay-policy=no-user-gesture-required',
  `--remote-debugging-port=${CDP}`, `--user-data-dir=${userDataDir}`, '--window-size=1280,900', 'about:blank'], { stdio: 'ignore' });
let target = null;
for (let i = 0; i < 40 && !target; i++) {
  await sleep(300);
  try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); } catch { }
}
if (!target) { console.error('cannot reach Edge CDP'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r, j) => { ws.addEventListener('open', r); ws.addEventListener('error', j); });
let mid = 0; const waits = new Map(); const consoleMsgs = [];
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waits.has(m.id)) { const w = waits.get(m.id); waits.delete(m.id); m.error ? w.rej(new Error(JSON.stringify(m.error))) : w.res(m.result); return; }
  const p = m.params || {};
  if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(p.type)) consoleMsgs.push(p.type + ': ' + (p.args || []).map((a) => a.value || a.description || '').join(' '));
  if (m.method === 'Runtime.exceptionThrown') consoleMsgs.push('EXCEPTION: ' + (p.exceptionDetails?.exception?.description || p.exceptionDetails?.text || ''));
});
const rpc = (method, params = {}) => { const id = ++mid; return new Promise((res, rej) => { waits.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); }); };
const evalJs = async (expr) => { const r = await rpc('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }); return r && r.result ? r.result.value : null; };
const shot = async (file) => { const r = await rpc('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); fs.writeFileSync(path.join(OUT, file), Buffer.from(r.data, 'base64')); return fs.statSync(path.join(OUT, file)).size; };
await rpc('Page.enable'); await rpc('Runtime.enable');

const report = { prefix: PREFIX, rows: [], checks: [] };
const push = (name, pass, detail) => { report.checks.push({ name, pass: !!pass, detail }); console.log('  [%s] %s %s', pass ? 'PASS' : 'FAIL', name, JSON.stringify(detail)); };

for (const vp of VPS) {
  await rpc('Emulation.setDeviceMetricsOverride', { width: vp.w, height: vp.h, deviceScaleFactor: 1, mobile: vp.mobile });
  for (const [name, url] of PAGES) {
    consoleMsgs.length = 0;
    await rpc('Page.navigate', { url: `http://127.0.0.1:${PORT}/${url}` });
    await sleep(2400);
    const geo = await evalJs(`(function(){
      var d = document.getElementById('dock'), c = document.getElementById('xkIdCard');
      var dr = d ? d.getBoundingClientRect() : null, cr = c ? c.getBoundingClientRect() : null;
      var a = d ? d.querySelector('a') : null, ar = a ? a.getBoundingClientRect() : null;
      var overlap = (dr && cr) ? (dr.left < cr.right && dr.right > cr.left && dr.top < cr.bottom && dr.bottom > cr.top) : null;
      return { vw: innerWidth, vh: innerHeight,
        dock: dr ? { l: Math.round(dr.left), r: Math.round(dr.right), t: Math.round(dr.top), b: Math.round(dr.bottom), w: Math.round(dr.width), h: Math.round(dr.height) } : null,
        card: cr ? { l: Math.round(cr.left), r: Math.round(cr.right), t: Math.round(cr.top), b: Math.round(cr.bottom) } : null,
        firstLink: ar ? { w: Math.round(ar.width), h: Math.round(ar.height) } : null,
        flexDir: d ? getComputedStyle(d).flexDirection : null,
        dockTopCss: d ? getComputedStyle(d).top : null,
        mq980: matchMedia('(max-width:980px)').matches,
        overlap: overlap,
        hOverflow: document.documentElement.scrollWidth > innerWidth + 1,
        scrollW: document.documentElement.scrollWidth };
    })()`);
    const file = `${PREFIX}-${name}-${vp.w}x${vp.h}.png`;
    const bytes = await shot(file);
    report.rows.push({ vp: vp.name, page: name, file, bytes, geo, console: consoleMsgs.slice(0, 3) });
    console.log('  %s %s dock(t=%s,b=%s,l=%s,vw=%s) card=%s overlap=%s hOverflow=%s link=%s console=%d',
      vp.name.padEnd(8), name.padEnd(7), geo.dock && geo.dock.t, geo.dock && geo.dock.b, geo.dock && geo.dock.l, geo.vw,
      JSON.stringify(geo.card), geo.overlap, geo.hOverflow, JSON.stringify(geo.firstLink), consoleMsgs.length);
  }
}

const mobile = report.rows.filter((r) => r.vp.startsWith('phone'));
const desktop = report.rows.filter((r) => r.vp === 'desktop');
push('mobile 3 viewports x 5 pages: dock in top half (top < vh/2)', mobile.every((r) => r.geo.dock && r.geo.dock.t < r.geo.vh / 2), mobile.map((r) => r.vp + '/' + r.page + ':t=' + (r.geo.dock && r.geo.dock.t)));
push('mobile: dock does not overlap the id card', mobile.every((r) => r.geo.overlap === false), mobile.filter((r) => r.geo.overlap).map((r) => r.vp + '/' + r.page));
push('mobile: no horizontal overflow', mobile.every((r) => r.geo.hOverflow === false), mobile.filter((r) => r.geo.hOverflow).map((r) => r.vp + '/' + r.page + ':sw=' + r.geo.scrollW));
push('mobile: touch target >=44px', mobile.every((r) => r.geo.firstLink && r.geo.firstLink.h >= 44 && r.geo.firstLink.w >= 44), mobile.map((r) => r.vp + ':' + JSON.stringify(r.geo.firstLink)));
push('desktop (1280): dock still the left column (left=0, taller than wide; top=88 is batch A giving way to the id card)',
  desktop.every((r) => r.geo.dock && r.geo.dock.l === 0 && (r.geo.dock.b - r.geo.dock.t) > 40 && (r.geo.dock.r - r.geo.dock.l) < 150),
  desktop.map((r) => r.page + ':l=' + (r.geo.dock && r.geo.dock.l) + ',t=' + (r.geo.dock && r.geo.dock.t) + ',h=' + (r.geo.dock && (r.geo.dock.b - r.geo.dock.t))));
push('console 0 everywhere', report.rows.every((r) => r.console.length === 0), report.rows.filter((r) => r.console.length).map((r) => r.vp + '/' + r.page + ':' + JSON.stringify(r.console)));

fs.writeFileSync(path.join(OUT, PREFIX + '-nav-report.json'), JSON.stringify(report, null, 1), 'utf8');
const failed = report.checks.filter((c) => !c.pass).length;
console.log('\n== summary ==\n  %d checks, %d failed -> %s', report.checks.length, failed, path.join(OUT, PREFIX + '-nav-report.json'));
try { ws.close(); } catch { }
try { child.kill(); } catch { }
server.close();
process.exit(failed ? 1 : 0);
