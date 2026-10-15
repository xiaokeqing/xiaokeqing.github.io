/* 改前/改后 同分辨率对照（窗口 Q，2026-10-15）
   node _dev/shot-before-after.mjs
   用同一个 CDP 浏览器、同一视口 1280x900，逐页截图 + 算平均亮度：
     /index.html        现在的产物（T8 + UI 批 + 我的减法）
     /_old-home.html    发布前一版 site-20261015-210145 的主页（改前基准）
     /alerts/           现在的监测中心
     /_old-alerts.html  发布前一版的监测中心
   输出：_shots/ba-*.png + _shots/before-after.json（含平均亮度，用于"是否变暗"的量化对照）
   服务：复用 8790 端口（站主的本地预览地址），不再另起端口。
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
const PORT = 8790, CDP = 9365, VW = 1280, VH = 900;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8', '.woff2': 'font/woff2', '.m4a': 'audio/mp4', '.webm': 'video/webm' };
const PAGES = [
  { name: 'home-new', url: 'index.html', wait: 12000 },
  { name: 'home-old', url: '_old-home.html', wait: 12000 },
  { name: 'alerts-new', url: 'alerts/', wait: 7000 },
  { name: 'alerts-old', url: '_old-alerts.html', wait: 7000 },
];
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
  const udd = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-ba-'));
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
  await rpc(ws, 'Emulation.setDeviceMetricsOverride', { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
  const ev = async (expr) => { const r = await rpc(ws, 'Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }); return r.result?.value; };

  const rows = [];
  for (const p of PAGES) {
    await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/${p.url}` });
    await sleep(p.wait);
    /* ★稳定态对拍：把页面上所有 CSS 动画钉到**同一相位**再抓帧。
       否则 `.glow{animation:breathe 7s ...}` 的相位随"页面加载到抓帧"的几十毫秒抖动而变，
       会在整屏背景上产生 ±1 的亮度差，被误判成"版式/底图变了"。 */
    const frozen = await ev(`(function(){ var n = 0;
      try { document.getAnimations().forEach(function(a){ try { a.pause(); a.currentTime = 1200; n++; } catch(e){} }); } catch(e){}
      return n; })()`);
    await sleep(400);
    const r = await rpc(ws, 'Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    const file = path.join(OUT, 'ba-' + p.name + '.png');
    fs.writeFileSync(file, Buffer.from(r.data, 'base64'));
    /* 平均亮度：把截图交给页面自己算（canvas 读同源图即可） */
    const stat = await ev(`(function(){
      return new Promise(function(res){
        var src = ${JSON.stringify('data:image/png;base64,' + r.data)};
        var im = new Image();
        im.onload = function(){
          var c = document.createElement('canvas'); c.width = im.width; c.height = im.height;
          var x = c.getContext('2d'); x.drawImage(im, 0, 0);
          function mean(x0,y0,w,h){
            var d = x.getImageData(x0,y0,w,h).data, s = 0, n = 0;
            for(var i=0;i<d.length;i+=4){ s += 0.299*d[i] + 0.587*d[i+1] + 0.114*d[i+2]; n++; }
            return +(s/n).toFixed(1);
          }
          var crt = document.getElementById('crt'); var rc = crt ? crt.getBoundingClientRect() : null;
          res(JSON.stringify({ all: mean(0,0,c.width,c.height),
            top: mean(0,0,c.width,Math.round(c.height*0.25)),
            crt: rc && rc.width ? mean(Math.round(rc.x),Math.round(rc.y),Math.round(rc.width),Math.round(rc.height)) : null,
            size:[c.width,c.height], layers:(function(){
              var o = {};
              ['.desk','.glow','.backplate','.plate','#crtClip','.scan','.vig','#bootveil','#crtBoot'].forEach(function(s){
                var e = document.querySelector(s);
                o[s] = e ? (getComputedStyle(e).display + '/' + getComputedStyle(e).opacity) : 'absent';
              });
              return o; })() }));
        };
        im.src = src;
      });
    })()`);
    let o = {}; try { o = JSON.parse(stat); } catch { o = { raw: stat }; }
    rows.push({ page: p.name, url: p.url, shot: 'ba-' + p.name + '.png', frozenAnimations: frozen, ...o });
    console.log(`== ${p.name} (${p.url})  [冻结动画 ${frozen} 条 @t=1200ms]`);
    console.log('   mean(all)=' + o.all + '  mean(top25%)=' + o.top + '  mean(crt)=' + o.crt);
    console.log('   layers: ' + JSON.stringify(o.layers));
  }
  fs.writeFileSync(path.join(OUT, 'before-after.json'), JSON.stringify(rows, null, 1), 'utf8');
  console.log('\n-> _shots/ba-*.png + _shots/before-after.json');
  ws.close(); child.kill(); server.close();
  await sleep(300);
  try { fs.rmSync(udd, { recursive: true, force: true }); } catch { }
}
main().catch((e) => { console.error('FAILED: ' + e.message); process.exit(1); });
