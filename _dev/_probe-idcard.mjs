/* 一次性排查：左上角头像卡到底画出来没有（不写产物） */
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const ROOT = 'F:\\7AAA\\AI\\blog', PUB = path.join(ROOT, 'public');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8817, CDP = 9367;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.m4a': 'audio/mp4', '.webm': 'audio/webm' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html';
  const f = path.join(PUB, p); if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' }); fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
const ud = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-probe-'));
const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--no-first-run', `--remote-debugging-port=${CDP}`, `--user-data-dir=${ud}`, '--window-size=1280,900', 'about:blank'], { stdio: 'ignore' });
let target = null;
for (let i = 0; i < 40 && !target; i++) { await sleep(300); try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); } catch { } }
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r, j) => { ws.addEventListener('open', r); ws.addEventListener('error', j); });
let mid = 0; const waits = new Map();
ws.addEventListener('message', (ev) => { const m = JSON.parse(ev.data); if (m.id && waits.has(m.id)) { const w = waits.get(m.id); waits.delete(m.id); m.error ? w.rej(new Error(JSON.stringify(m.error))) : w.res(m.result); } });
const rpc = (method, params = {}) => { const id = ++mid; return new Promise((res, rej) => { waits.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); }); };
await rpc('Page.enable'); await rpc('Runtime.enable');
const ev = async (e) => { const r = await rpc('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true }); return r && r.result ? r.result.value : r; };
await rpc('Page.navigate', { url: `http://127.0.0.1:${PORT}/` });
await sleep(4000);
console.log(JSON.stringify(await ev(`(function(){
  var cv=document.getElementById('xkIdAvCanvas');
  var out={ has:!!cv, w:cv&&cv.width, h:cv&&cv.height, cssW:cv&&cv.getBoundingClientRect().width, cssH:cv&&cv.getBoundingClientRect().height };
  try{ var g=cv.getContext('2d'); var d=g.getImageData(0,0,132,132).data; var nz=0, sample=[];
    for(var i=0;i<d.length;i+=4){ if(d[i+3]>0) nz++; }
    out.nonTransparent=nz; out.px0=[d[0],d[1],d[2],d[3]]; out.pxMid=[d[(66*132+66)*4],d[(66*132+66)*4+1],d[(66*132+66)*4+2],d[(66*132+66)*4+3]];
  }catch(e){ out.err=String(e); }
  var d2=window.__xkId||{}; out.emo=d2.emo; out.errs=(d2.errors||[]).slice(-5); out.sound=d2.sound;
  var img=document.querySelector('img[src*="normal.idle"]');
  out.img = null;
  try{ var probe=new Image(); probe.src='/kurisu/avatar/normal.idle.webp'; out.imgSrcComplete=probe.complete; }catch(e){}
  out.loginHidden=(document.getElementById('xkLoginBtn')||{}).hidden;
  out.loginDisplay=(function(){var l=document.getElementById('xkLoginBtn');return l?getComputedStyle(l).display:null;})();
  out.sndDisplay=(function(){var l=document.getElementById('xkSndBtn');return l?getComputedStyle(l).display:null;})();
  return out; })()`), null, 1));
try { ws.close(); } catch { } try { child.kill(); } catch { } server.close(); process.exit(0);
