/* 主页 CRT 内部 "游离元素" 取证（窗口 Q）
   node _dev/probe-crt-strays.mjs
   列出 #crt 里所有可见文本元素（class/rect/文本）与所有 <img>（rect/natural），
   用来定位"屏内一串游离文字"到底是 DOM 文本还是素材图上烧进去的字。
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
const PORT = 8851, CDP = 9364, VW = 1280, VH = 900;
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
  const udd = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-stray-'));
  const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
    '--no-default-browser-check', '--disable-extensions', '--mute-audio',
    `--remote-debugging-port=${CDP}`, `--user-data-dir=${udd}`, `--window-size=${VW},${VH}`, 'about:blank'], { stdio: 'ignore' });
  let target = null;
  for (let i = 0; i < 60 && !target; i++) {
    await sleep(400);
    try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); } catch { }
  }
  if (!target) throw new Error('连不上调试端口');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  await rpc(ws, 'Page.enable'); await rpc(ws, 'Runtime.enable');
  const ev = async (expr) => { const r = await rpc(ws, 'Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }); return r.result?.value; };

  await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/index.html` });
  await sleep(12000);   /* 等开场与 T31 六阶段全部落定 */
  const dump = await ev(`(function(){
    var crt = document.getElementById('crt');
    if(!crt) return JSON.stringify({err:'no #crt'});
    function rectOf(e){ var r=e.getBoundingClientRect(); return {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}; }
    var texts = [];
    crt.querySelectorAll('*').forEach(function(e){
      var t = (e.childNodes.length===1 && e.firstChild && e.firstChild.nodeType===3) ? String(e.textContent||'').trim() : '';
      var own = Array.prototype.slice.call(e.childNodes).filter(function(n){return n.nodeType===3;}).map(function(n){return n.nodeValue;}).join('').trim();
      if(!own) return;
      var cs = getComputedStyle(e);
      if(cs.display==='none' || cs.visibility==='hidden' || Number(cs.opacity)===0) return;
      texts.push({tag:e.tagName, cls:e.className, id:e.id, own:own.slice(0,60), rect:rectOf(e), opacity:cs.opacity});
    });
    var imgs = [];
    crt.querySelectorAll('img').forEach(function(e){
      var cs = getComputedStyle(e);
      imgs.push({cls:e.className, src:(e.getAttribute('src')||'').split('/').pop(), rect:rectOf(e),
                 nat:e.naturalWidth+'x'+e.naturalHeight, disp:cs.display, op:cs.opacity, vis:cs.visibility});
    });
    var subs = [];
    ['crtSub','subText','crtBoot','crtStatus'].forEach(function(id){ var e=document.getElementById(id); if(e){ var cs=getComputedStyle(e);
      subs.push({id:id, hidden:e.hidden, disp:cs.display, rect:rectOf(e), text:String(e.textContent||'').trim().slice(0,80)}); } });
    return JSON.stringify({texts:texts, imgs:imgs, specials:subs,
      boot:(window.__xkBoot?{phase:window.__xkBoot.phase}:null)}, null, 1);
  })()`);
  console.log(dump);
  fs.writeFileSync(path.join(OUT, 'crt-strays.json'), dump || '', 'utf8');
  const r = await rpc(ws, 'Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  fs.writeFileSync(path.join(OUT, 'crt-strays.png'), Buffer.from(r.data, 'base64'));
  console.log('\n-> _shots/crt-strays.json + crt-strays.png');
  ws.close(); child.kill(); server.close();
  await sleep(300);
  try { fs.rmSync(udd, { recursive: true, force: true }); } catch { }
}
main().catch((e) => { console.error('FAILED: ' + e.message); process.exit(1); });
