/* batch 4 evidence: measure the REAL magnification from source tile pixels to on-screen
   physical pixels by hooking CanvasRenderingContext2D.drawImage before page scripts run.
   usage: node _dev/probe-blur-factor.mjs [--only=iphone-375]
   output: _shots/probe-blur-factor.json + console summary */
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = 'F:\\7AAA\\AI\\blog';
const PUB = path.join(ROOT, 'public');
const OUT = path.join(ROOT, '_shots');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8851, CDP = 9401;
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

const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-blur-'));
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
let mid = 0; const waits = new Map();
const rpc = (method, params = {}) => { const id = ++mid; return new Promise((res, rej) => { waits.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); }); };
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waits.has(m.id)) { const w = waits.get(m.id); waits.delete(m.id); m.error ? w.rej(new Error(JSON.stringify(m.error))) : w.res(m.result); }
});
const evalJs = async (expr) => {
  const r = await rpc('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r && r.exceptionDetails) return { __err: (r.exceptionDetails.exception?.description || r.exceptionDetails.text || '').slice(0, 200) };
  return r && r.result ? r.result.value : null;
};
await rpc('Page.enable'); await rpc('Runtime.enable');

const HOOK = `(function(){
  if (window.__xkBlurHook) { return; }
  window.__xkBlurHook = true; window.__xkBlur = []; window.__xkBlurLayer = [];
  var P = CanvasRenderingContext2D.prototype, orig = P.drawImage;
  P.drawImage = function(img){
    var a = Array.prototype.slice.call(arguments, 1);
    var url = ''; try { url = img && (img.currentSrc || img.src || img.baseURI || ''); } catch(e){}
    var sw, sh, dx, dy, dw, dh;
    if (a.length === 8) { sw = a[2]; sh = a[3]; dx = a[4]; dy = a[5]; dw = a[6]; dh = a[7]; }
    else if (a.length === 4) { sw = img.naturalWidth || img.width; sh = img.naturalHeight || img.height; dx = a[0]; dy = a[1]; dw = a[2]; dh = a[3]; }
    else if (a.length === 2) { sw = img.naturalWidth || img.width; sh = img.naturalHeight || img.height; dx = a[0]; dy = a[1]; dw = sw; dh = sh; }
    else { return orig.apply(this, arguments); }
    var file = String(url).split('/').pop().split('?')[0];
    if (String(url).indexOf('/kurisu/') >= 0 && dw > 0 && sw > 0 && window.__xkBlur.length < 900) {
      var rec = { i: window.__xkBlur.length, cv: (this.canvas && this.canvas.id) || '', nw: img.naturalWidth || 0, nh: img.naturalHeight || 0,
        sw: Math.round(sw * 10) / 10, sh: Math.round(sh * 10) / 10, dw: Math.round(dw * 10) / 10, dh: Math.round(dh * 10) / 10,
        rx: Math.round(dw / sw * 1000) / 1000, ry: Math.round(dh / sh * 1000) / 1000,
        cw: this.canvas ? this.canvas.width : 0, ch: this.canvas ? this.canvas.height : 0, file: file,
        vidMode: (window.__xkVid && window.__xkVid.mode) || (window.__xkVid2 && window.__xkVid2.mode) || '' };
      window.__xkBlur.push(rec);
      if (window.__xkBlurLayer.length < 60) { window.__xkBlurLayer.push(rec.i + ':' + file + ':' + rec.vidMode); }
    }
    return orig.apply(this, arguments);
  };
  window.__xkBlurCanvas = function(){
    var o = {};
    ['charCanvas','phoneCanvas'].forEach(function(id){
      var c = document.getElementById(id); if (!c) return;
      var r = c.getBoundingClientRect();
      o[id] = { phys: [c.width, c.height], css: [Math.round(r.width), Math.round(r.height)], dpr: window.devicePixelRatio };
    });
    return o;
  };
})();`;

const ONLY = (process.argv.find((a) => a.startsWith('--only=')) || '').slice(7);
const PROFILES = [
  { name: 'iphone-375', w: 375, h: 812, ua: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1', mobile: true },
  { name: 'android-390', w: 390, h: 844, ua: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36', mobile: true },
  { name: 'desktop-1280', w: 1280, h: 900, ua: null, mobile: false }
].filter((p) => !ONLY || p.name === ONLY);
const MODES = ['', '?xk-kurisu-mode=video'];

const out = { at: new Date().toISOString(), profiles: [] };
for (const pf of PROFILES) {
  for (const mode of MODES) {
    await rpc('Page.addScriptToEvaluateOnNewDocument', { source: HOOK }).catch(() => { });
    await rpc('Emulation.setDeviceMetricsOverride', { width: pf.w, height: pf.h, deviceScaleFactor: 2, mobile: pf.mobile });
    await rpc('Emulation.setUserAgentOverride', { userAgent: pf.ua || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36' });
    await rpc('Page.navigate', { url: `${BASE}/${mode}` });
    await sleep(7000);
    const canvases = await evalJs('window.__xkBlurCanvas ? window.__xkBlurCanvas() : null');
    const draws = await evalJs('window.__xkBlur || []');
    const layer = await evalJs('window.__xkBlurLayer || []');
    const vidMode = await evalJs('(function(){ var v=window.__xkVid||window.__xkVid2; var t=window.__xkTier; return {mode:v?v.mode:null, reason:v?v.reason:null, drawn:v?v.drawn:null, enabled:v?v.enabled:null, videoOK:v?v.videoOK:null, noHi:t?t.noHi:null, tier:t?t.tier:null}; })()');
    const arr = Array.isArray(draws) ? draws : [];
    const byKey = {};
    for (const d of arr) { const k = d.cv + '|' + d.file; if (!byKey[k] || d.rx > byKey[k].rx) { byKey[k] = d; } }
    const list = Object.keys(byKey).map((k) => byKey[k]).sort((a, b) => b.rx - a.rx);
    out.profiles.push({ profile: pf.name, mode: mode || '(default)', vidMode, viewport: [pf.w, pf.h], dpr: 2, canvases, draws: arr.length, byFile: list, layerSeq: Array.isArray(layer) ? layer : [] });
    console.log(`\n== ${pf.name} (${pf.w}x${pf.h}) mode=${mode || '(default)'} vid=${JSON.stringify(vidMode)} canvases=${JSON.stringify(canvases)} draws=${arr.length}`);
    console.log('   layerSeq(first 30): ' + (Array.isArray(layer) ? layer.slice(0, 30).join(' | ') : ''));
    for (const d of list) {
      console.log(`   ${String(d.cv).padEnd(12)} ${String(d.file).padEnd(28)} src ${d.sw}x${d.sh} (img ${d.nw}x${d.nh}) -> dest ${d.dw}x${d.dh}  ratio ${d.rx}x`);
    }
  }
}
fs.writeFileSync(path.join(OUT, 'probe-blur-factor.json'), JSON.stringify(out, null, 1), 'utf8');
console.log('\nreport -> ' + path.join(OUT, 'probe-blur-factor.json'));
try { ws.close(); } catch { }
try { child.kill(); } catch { }
server.close();
process.exit(0);
