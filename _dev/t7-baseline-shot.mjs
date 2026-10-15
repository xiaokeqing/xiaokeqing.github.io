/* T7 冻帧对拍 · 取基线：把**接线前的产物**（E:\...\_t7-baseline\public，由 HEAD 版模板构建）
   用与 verify-video-wiring.mjs 完全相同的 CDP 口径截一张 1280×900 的图。
   node _dev/t7-baseline-shot.mjs
   → _shots/t7-baseline-home.png
*/
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const BASE = 'E:\\DeepSeek1\\work\\_t7-baseline\\public';
const OUT = 'F:\\7AAA\\AI\\blog\\_shots';
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8814, CDP = 9354, VW = 1280, VH = 900;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8', '.woff2': 'font/woff2', '.webm': 'video/webm', '.m4a': 'audio/mp4' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });
if (!fs.existsSync(BASE)) { console.error('缺基线产物目录：' + BASE); process.exit(1); }

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p.endsWith('/')) p += 'index.html';
  const f = path.join(BASE, p);
  if (!f.startsWith(BASE) || !fs.existsSync(f) || !fs.statSync(f).isFile()) { res.writeHead(404); res.end('404'); return; }
  res.writeHead(200, { 'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});

let nextId = 0;
const rpc = (ws, method, params = {}) => new Promise((resolve, reject) => {
  const id = ++nextId;
  const on = (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.id !== id) return;
    ws.removeEventListener('message', on);
    m.error ? reject(new Error(method + ': ' + JSON.stringify(m.error))) : resolve(m.result);
  };
  ws.addEventListener('message', on);
  ws.send(JSON.stringify({ id, method, params }));
});

async function main() {
  await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
  const udd = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-base-'));
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
  await rpc(ws, 'Page.enable'); await rpc(ws, 'Runtime.enable'); await rpc(ws, 'Network.enable');
  await rpc(ws, 'Emulation.setDeviceMetricsOverride', { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
  await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/` });
  await sleep(11000);                                     /* 与 verify 脚本同款检查点（1.5s + 9.5s） */
  /* 与 verify-video-wiring.mjs 完全一致地"冻帧"：页面自带 7s 的 .glow 呼吸动画，
     不冻住的话两次截图的氛围光相位不同（只差 1/255，但会污染"0 像素差"判据）。 */
  await rpc(ws, 'Runtime.evaluate', {
    expression: `(function(){var st=document.getElementById('xk-freeze');
      if(!st){st=document.createElement('style');st.id='xk-freeze';
        st.textContent='*,*::before,*::after{animation-play-state:paused !important} .glow{opacity:.5 !important}';
        document.head.appendChild(st);}return 1;})()`,
    returnByValue: true,
  });
  await sleep(150);
  const r = await rpc(ws, 'Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  const f = path.join(OUT, 't7-baseline-home.png');
  fs.writeFileSync(f, Buffer.from(r.data, 'base64'));
  const info = await rpc(ws, 'Runtime.evaluate', {
    expression: `(function(){var V=window.__xkVid;var c=document.getElementById('charCanvas');
      var on=-1;if(c&&c.width){var d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;on=0;
      for(var i=3;i<d.length;i+=4){if(d[i]>8)on++;}}
      return {xkVid:!!V, clip:(typeof cur!=='undefined'?cur:null), opaque:on};})()`,
    returnByValue: true,
  });
  console.log('基线截图 → ' + f + '  页面状态=' + JSON.stringify(info.result.value));
  ws.close(); child.kill(); server.close();
  await sleep(400);
  try { fs.rmSync(udd, { recursive: true, force: true }); } catch { }
}
main().catch((e) => { console.error('FAILED: ' + e.message); server.close(); process.exit(1); });
