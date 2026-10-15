/* T7 视频接线 · 真浏览器验收（零第三方依赖，复用 sm-evidence.mjs 的 CDP 套路）
   node _dev/verify-video-wiring.mjs
   做六件事（每一项都落成 _shots/ 下的证据）：
     ① video 档真的在放视频：window.__xkVid.mode / drawn / alive / 品红 alpha 采样
     ② pixel 档 = 接线前行为：同一时刻整页截图（冻帧对拍用）
     ③ 故障注入 A：/kurisu/video/** 全 404 ⇒ 必须退图集、控制台 0 报错、画布仍然有角色
     ④ 故障注入 B：单个 idle.webm 损坏 ⇒ 该剪辑永久降级（只失败一次）、控制台 0 报错
     ⑤ 总开关：?xk-kurisu-mode=pixel / off 两档行为
     ⑥ 预载纪律：首次手势前不得出现 video-manifest.json / *.webm 请求；手势后允许
   输出：_shots/t7-video.json + _shots/t7-{video,pixel,fallback,corrupt,off}-home.png
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
const PORT = 8811, CDP = 9351, VW = 1280, VH = 900;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8', '.woff2': 'font/woff2', '.webm': 'video/webm', '.m4a': 'audio/mp4' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

/* 服务端：支持"注入故障"——404 全部视频 / 把某个 webm 回成损坏字节 */
const bad = { allVideo404: false, corruptWebm: null };
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p.endsWith('/')) p += 'index.html';
  if (bad.allVideo404 && p.startsWith('/kurisu/video/')) { res.writeHead(404); res.end('404'); return; }
  const f = path.join(PUB, p);
  if (!f.startsWith(PUB) || !fs.existsSync(f) || !fs.statSync(f).isFile()) { res.writeHead(404); res.end('404'); return; }
  if (bad.corruptWebm && p === bad.corruptWebm) {
    res.writeHead(200, { 'content-type': 'video/webm' });
    res.end(Buffer.from('not a real webm at all — 故意损坏的字节'));
    return;
  }
  res.writeHead(200, { 'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});

let nextId = 0;
function rpc(ws, method, params = {}) {
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const on = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.id !== id) return;
      ws.removeEventListener('message', on);
      m.error ? reject(new Error(method + ': ' + JSON.stringify(m.error))) : resolve(m.result);
    };
    ws.addEventListener('message', on);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

let consoleMsgs = [], responses = [], reqs = [];

async function main() {
  await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-vid-'));
  const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--mute-audio', '--autoplay-policy=no-user-gesture-required',
    `--remote-debugging-port=${CDP}`, `--user-data-dir=${userDataDir}`, `--window-size=${VW},${VH}`, 'about:blank'], { stdio: 'ignore' });
  let target = null;
  for (let i = 0; i < 60 && !target; i++) {
    await sleep(400);
    try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); } catch { }
  }
  if (!target) throw new Error('连不上 Edge 调试端口');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  ws.addEventListener('message', (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.method === 'Network.responseReceived') responses.push({ status: m.params.response.status, url: m.params.response.url });
    if (m.method === 'Network.requestWillBeSent') reqs.push(m.params.request.url);
    if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type))
      consoleMsgs.push(m.params.type + ': ' + (m.params.args || []).map((a) => a.value || a.description || '').join(' '));
    if (m.method === 'Runtime.exceptionThrown')
      consoleMsgs.push('EXCEPTION: ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
  });
  await rpc(ws, 'Page.enable'); await rpc(ws, 'Runtime.enable'); await rpc(ws, 'Network.enable');
  await rpc(ws, 'Emulation.setDeviceMetricsOverride', { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
  const evalJs = async (expression, awaitPromise = false) => {
    const r = await rpc(ws, 'Runtime.evaluate', { expression, returnByValue: true, awaitPromise });
    if (r.exceptionDetails) throw new Error('页面抛异常：' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result?.value;
  };
  const shot = async (name) => {
    /* 冻帧：页面自带一个 7s 的 .glow 呼吸动画（原型效果，不是接线引入的），
       它让"两次截图"的全局氛围光相位不同（实测只差 1/255，但会污染"0 像素差"判据）。
       这里在截图前把动画冻住 + 把 .glow 的透明度固定到同一个值 —— 对每张图一视同仁，
       不改产物、不改观感（固定值取动画中值 .5），只让对拍可复现。 */
    await evalJs(`(function(){var st=document.getElementById('xk-freeze');
      if(!st){st=document.createElement('style');st.id='xk-freeze';
        st.textContent='*,*::before,*::after{animation-play-state:paused !important} .glow{opacity:.5 !important}';
        document.head.appendChild(st);}return 1;})()`);
    await sleep(120);
    const r = await rpc(ws, 'Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    const file = path.join(OUT, name + '.png');
    fs.writeFileSync(file, Buffer.from(r.data, 'base64'));
    return path.basename(file);
  };
  const gesture = () => rpc(ws, 'Input.dispatchMouseEvent', { type: 'mousePressed', x: 640, y: 450, button: 'left', clickCount: 1 })
    .then(() => rpc(ws, 'Input.dispatchMouseEvent', { type: 'mouseReleased', x: 640, y: 450, button: 'left', clickCount: 1 }));
  /* 这台机器上 rAF 被节流（开场 84 帧要 ~11.5s），所以不能只按固定时间等 ——
     轮询到"视频帧真的画上屏"（drawn>0 且 probe 有值）或超时为止。 */
  const waitDrawn = async (ms) => {
    const t0 = Date.now();
    while (Date.now() - t0 < ms) {
      const s = await evalJs(`(function(){var V=window.__xkVid;return V?{d:V.drawn,p:!!V.probe,m:V.mode,f:Object.keys(V.failed)}:null;})()`);
      if (s && (s.d > 0 || s.p)) return { waitedMs: Date.now() - t0, at: s };
      await sleep(700);
    }
    return { waitedMs: ms, at: null };
  };
  const reset = () => { consoleMsgs = []; responses = []; reqs = []; };
  const state = () => evalJs(`(function(){var V=window.__xkVid;if(!V)return null;
      var vids=document.querySelectorAll('video');
      var inDom=0;for(var i=0;i<vids.length;i++){if(vids[i].isConnected)inDom++;}
      return {mode:V.mode,reason:V.reason,enabled:V.enabled,videoOK:V.videoOK,disp:V.disp,mfState:V.mfState,
        alive:V.alive,gesture:V.gesture,preload:V.preload,probe:V.probe,drawn:V.drawn,
        fallbackDrawn:V.fallbackDrawn,released:V.released,failed:Object.keys(V.failed),
        decoded:Object.keys(V.decoded),errs:V.errors.slice(-6),
        clipErrs:(function(){var o={};for(var k in V.decoded){if(V.decoded[k].err.length)o[k]=V.decoded[k].err;}return o;})(),
        vid:(function(){var o={};for(var k in V.decoded){var v=V.decoded[k].vd;o[k]={rs:v.readyState,ns:v.networkState,vw:v.videoWidth,vh:v.videoHeight,
          t:Math.round((v.currentTime||0)*1000)/1000,dur:Math.round((v.duration||0)*1000)/1000,ready:V.decoded[k].ready,have:V.decoded[k].have,
          pending:V.decoded[k].pending,lastReq:V.decoded[k].lastReq,act:V.decoded[k].act};}return o;})(),
        counters:{drawTrue:V.drawn,drawFalse:V.fallbackDrawn,probeDone:!!V.probe},
        videoEls:vids.length,videoInDom:inDom};})()`);
  const opaque = () => evalJs(`(function(){var c=document.getElementById('charCanvas');if(!c)return -1;
      var x=c.getContext('2d');if(!c.width)return -1;var d=x.getImageData(0,0,c.width,c.height).data,on=0;
      for(var i=3;i<d.length;i+=4){if(d[i]>8)on++;}return on;})()`);

  const report = { url: `http://127.0.0.1:${PORT}/`, cases: [] };

  /* ---------- ① video 档（默认）---------- */
  reset();
  await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/` });
  await sleep(1500);
  const preGesture = {
    state: await state(),
    manifestReqs: reqs.filter((u) => u.includes('video-manifest.json')).length,
    webmReqs: reqs.filter((u) => u.endsWith('.webm')).length,
    posterReqs: reqs.filter((u) => /\.poster\.webp$/.test(u)).length,
  };
  await gesture();                                      /* 用户第一次手势 → 解锁视频层 */
  await evalJs(`(function(){var B=window.__xkVid && XKV2_BLOCK; if(!B) return 'no-block';
      window.__xkVid.__origDraw = B.draw;                 /* 留一份原始 draw 给"直接驱动"用 */
      window.__xkProbe=[]; window.__xkProbeN=0; window.__xkProbeByClip={};
      var od=B.draw;
      B.draw=function(n,f,box){ var r,e=null; try{ r=od.apply(this,arguments); }catch(x){ e=String(x&&x.stack||x); }
        window.__xkProbeN++;
        var by=window.__xkProbeByClip; by[n]=by[n]||{n:0,t:0,f:0};
        by[n].n++; by[n].t+=r?1:0; by[n].f+=r?0:1;
        if(window.__xkProbe.length<60 && (!by[n].seen || by[n].seen<2)){ by[n].seen=(by[n].seen||0)+1;
          window.__xkProbe.push({n:n,f:f,mode:(window.__xkVid||{}).mode,mf:(window.__xkVid||{}).mfState,r:r,e:e,
            clips:((window.__xkVid||{}).manifest||{}).clips?Object.keys(window.__xkVid.manifest.clips).length:0}); }
        return r; };
      return 'hooked';})()`);
  /* ★直接驱动（绕开 headless 的 rAF 停摆）：等清单到位后，把 idle 的 0/30/60/90 帧
     逐帧喂给渲染器，看它是否真的"画上屏"（drawn 增加 + 画布哈希变化 + probe 有值）。
     这不是模拟用户路径，而是把"视频帧能不能出画"这件事单独测出来 —— 路径本身由 ① 的探针看。 */
  const drive = async () => {
    const t0 = Date.now();
    while (Date.now() - t0 < 20000) {
      const mf = await evalJs('(window.__xkVid||{}).mfState');
      if (mf === 2) break;
      await sleep(500);
    }
    /* 每帧之间必须**真的让出事件循环**（await sleep）—— seek 的完成是异步事件，
       用忙等会把回调饿死（本轮踩过：busy-wait 让 pump() 永远不执行，have 一直是 -1）。 */
    const hash = () => evalJs(`(function(){var c=document.getElementById('charCanvas');try{
      var d=c.getContext('2d').getImageData(0,0,c.width,c.height).data,h=0;
      for(var i=0;i<d.length;i+=397){h=(h*31+d[i])>>>0;}return h;}catch(e){return 'err';}})()`);
    const one = (f) => evalJs(`(function(){var V=window.__xkVid,d=V&&V.__origDraw;if(!d)return 'noDraw';
      var c=document.getElementById('charCanvas');
      var plan={src:'/kurisu/full/idle.hi.webp',frames:60,interval:42,cols:8,cw:321,ch:432,fit:'anchor'};
      return d('idle',${f},{plan:plan,ctx:c.getContext('2d'),w:c.width,h:c.height});})()`);
    const before = { drawn: await evalJs('(window.__xkVid||{}).drawn'), h: await hash() };
    const calls = [];
    for (const f of [0, 30, 60, 90]) {
      for (let rep = 0; rep < 12; rep++) {
        const r = await one(f);
        calls.push({ f, r });
        if (r === true) break;
        await sleep(150);
      }
    }
    const after = {
      drawn: await evalJs('(window.__xkVid||{}).drawn'),
      h: await hash(),
      probe: await evalJs('JSON.stringify((window.__xkVid||{}).probe)'),
      have: await evalJs('JSON.stringify((function(){var o={};for(var k in (window.__xkVid||{}).decoded)o[k]=window.__xkVid.decoded[k].have;return o;})())'),
    };
    return {
      before, calls, after,
      changed: before.h !== after.h,
      anyTrue: calls.filter((x) => x.r === true).length,
    };
  };
  const driven = await drive();
  const s1 = await state();
  const probe1 = await evalJs('JSON.stringify({samples:window.__xkProbe,total:window.__xkProbeN,byClip:window.__xkProbeByClip})');
  const op1 = await opaque();
  const shotVideo = await shot('t7-video-home');
  report.cases.push({ name: '①video档', preGesture, state: s1, probe: probe1 ? JSON.parse(probe1) : null,
    driven: driven || null, canvasOpaque: op1, shot: shotVideo,
    net: { webm: responses.filter((r) => /\.webm/.test(r.url)).map((r) => r.status + ' ' + r.url.split('/').pop()),
           manifest: responses.filter((r) => /video-manifest/.test(r.url)).map((r) => r.status) },
    console: [...consoleMsgs], expect: '手势前 0 个视频/poster/清单请求；手势后 mode=video／drawn>0／probe.ok=true／video 元素不进 DOM／无 console error' });

  /* ---------- ② pixel 档（冻帧对拍基线）---------- */
  reset();
  await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/?xk-kurisu-mode=pixel` });
  await gesture();
  await sleep(1500 + 13000);
  const s2 = await state();
  const shotPixel = await shot('t7-pixel-home');
  report.cases.push({ name: '②pixel档', state: s2, canvasOpaque: await opaque(), shot: shotPixel,
    net: { anyVideoRequests: reqs.filter((u) => /video-manifest|\.webm|\.poster\.webp/.test(u)).length },
    console: [...consoleMsgs], expect: 'mode=pixel／enabled=false／0 个视频请求／画布与接线前一致' });

  /* ---------- ③ 故障注入 A：/kurisu/video/** 全 404 ---------- */
  bad.allVideo404 = true;
  reset();
  await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/` });
  await sleep(1500);
  await gesture();
  const wait3 = await waitDrawn(30000);
  const s3 = await state();
  const op3 = await opaque();
  const shotFb = await shot('t7-fallback-home');
  bad.allVideo404 = false;
  report.cases.push({ name: '③故障A-视频全404', state: s3, canvasOpaque: op3, shot: shotFb, waitDrawn: wait3,
    nonOk: responses.filter((r) => r.status >= 400).length, console: [...consoleMsgs],
    expect: '退图集：canvasOpaque>10000（角色还在）／控制台 0 报错／failed 非空 or 仍 drawn>0' });

  /* ---------- ④ 故障注入 B：单个 idle.webm 损坏 ---------- */
  bad.corruptWebm = '/kurisu/video/idle.webm';
  reset();
  await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/` });
  await sleep(1500);
  await gesture();
  const wait4 = await waitDrawn(25000);
  await sleep(4000);                                    /* 再等一会：确认没有"每帧重试"式的报错增长 */
  const s4a = await state();
  await sleep(4000);
  const s4b = await state();
  const shotCorrupt = await shot('t7-corrupt-home');
  bad.corruptWebm = null;
  report.cases.push({ name: '④故障B-idle损坏', stateAfter9s: s4a, stateAfter13s: s4b, waitDrawn: wait4,
    canvasOpaque: await opaque(), shot: shotCorrupt,
    net: { idleRequests: reqs.filter((u) => u.endsWith('/idle.webm')).length,
           allWebm: reqs.filter((u) => u.endsWith('.webm')).map((u) => u.split('/').pop()) },
    console: [...consoleMsgs],
    expect: 'idle 永久降级（failed 含 idle）／不再重复请求 idle.webm／控制台 0 报错／画布仍有角色' });

  /* ---------- ⑤ 总开关 off ---------- */
  reset();
  await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/?xk-kurisu-mode=off` });
  await gesture();
  await sleep(1500 + 4000);
  const s5 = await state();
  report.cases.push({ name: '⑤off档', state: s5, shot: await shot('t7-off-home'),
    net: { anyVideoRequests: reqs.filter((u) => /video-manifest|\.webm|\.poster\.webp/.test(u)).length },
    console: [...consoleMsgs], expect: 'mode=off／不取清单与视频／角色层不加载' });

  fs.writeFileSync(path.join(OUT, 't7-video.json'), JSON.stringify(report, null, 1), 'utf8');
  console.log(JSON.stringify(report, null, 1));
  console.log('\n证据 → _shots/t7-video.json');
  ws.close(); child.kill(); server.close();
  await sleep(400);
  try { fs.rmSync(userDataDir, { recursive: true, force: true }); } catch { }
}
main().catch((e) => { console.error('FAILED: ' + e.message); server.close(); process.exit(1); });
