/* T8 batch 1 - real-browser acceptance: state-machine walk + host triggers + fallbacks + reproducibility
   node _dev/verify-sm-walker.mjs [page]

   Checks (all required):
     A canvas frame fingerprints >= 8
     B reason counts: host:voice / host:emotion / host:idle both >= 1 (cadence also expected)
     C ?seed reproducible: two runs give an identical timeline
     C2 ?replay=<base64> replays the same segment
     D fallback injection 1: statemachine.json 404 -> prototype 4-clip loop, console 0 errors
     E fallback injection 2: statemachine.json bad JSON -> same
     F page hidden: pause and clear the accumulator (no fast-forward on return)

   Determinism note: this box throttles rAF in headless, so wall-clock waits are NOT reproducible
   (tried it: every run differed). Acceptance therefore drives the walker with a FIXED virtual clock
   (XK_SM_JS.useVirtualClock + stepFixed) and a fixed host-event script; same seed => identical timeline.

   Pacing note (must be quoted in the report): real defaults are idle=12s / cadence=25s / host cooldown 1.8s.
   Acceptance uses compressed knobs ?xk-idle=3000&xk-host=800 - it is NOT the real pacing.

   Output: _shots/t8-sm.json + _shots/t8-sm-*.png
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
const PORT = 8821, CDP = 9361, VW = 1280, VH = 900;
const PAGE = process.argv[2] || '';
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8', '.woff2': 'font/woff2', '.webm': 'video/webm', '.m4a': 'audio/mp4' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

const inj = { json404: false, jsonBad: false };
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p.endsWith('/')) p += 'index.html';
  if (p === '/kurisu/statemachine.json') {
    if (inj.json404) { res.writeHead(404); res.end('404'); return; }
    if (inj.jsonBad) { res.writeHead(200, { 'content-type': 'application/json' }); res.end('{ this is not json ,,, '); return; }
  }
  const f = path.join(PUB, p);
  if (!f.startsWith(PUB) || !fs.existsSync(f) || !fs.statSync(f).isFile()) { res.writeHead(404); res.end('404'); return; }
  res.writeHead(200, { 'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});

let nid = 0;
const rpc = (ws, m, p = {}) => new Promise((resolve, reject) => {
  const id = ++nid;
  const on = (ev) => {
    let x; try { x = JSON.parse(ev.data); } catch { return; }
    if (x.id !== id) return;
    ws.removeEventListener('message', on);
    x.error ? reject(new Error(m + ': ' + JSON.stringify(x.error))) : resolve(x.result);
  };
  ws.addEventListener('message', on);
  ws.send(JSON.stringify({ id, method: m, params: p }));
});

async function main() {
  await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
  const udd = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-sm-'));
  const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
    '--no-default-browser-check', '--disable-extensions', '--mute-audio', '--autoplay-policy=no-user-gesture-required',
    `--remote-debugging-port=${CDP}`, `--user-data-dir=${udd}`, `--window-size=${VW},${VH}`, 'about:blank'], { stdio: 'ignore' });
  let target = null;
  for (let i = 0; i < 60 && !target; i++) {
    await sleep(400);
    try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); } catch { }
  }
  if (!target) throw new Error('cannot reach Edge debug port');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });

  let consoleMsgs = [], responses = [];
  ws.addEventListener('message', (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.method === 'Network.responseReceived') responses.push({ s: m.params.response.status, u: m.params.response.url });
    if (m.method === 'Network.requestWillBeSent') reqs.push(m.params.request.url);
    if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type))
      consoleMsgs.push(m.params.type + ': ' + (m.params.args || []).map((a) => a.value || a.description || '').join(' '));
    if (m.method === 'Runtime.exceptionThrown')
      consoleMsgs.push('EXCEPTION: ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
  });
  await rpc(ws, 'Page.enable'); await rpc(ws, 'Runtime.enable'); await rpc(ws, 'Network.enable');
  await rpc(ws, 'Emulation.setDeviceMetricsOverride', { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
  const ev = async (expr, awaitPromise = false) => {
    const r = await rpc(ws, 'Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise });
    if (r.exceptionDetails) throw new Error('page threw: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result?.value;
  };
  const shot = async (name) => {
    await ev(`(function(){var st=document.getElementById('xk-freeze');if(!st){st=document.createElement('style');
      st.id='xk-freeze';st.textContent='*,*::before,*::after{animation-play-state:paused !important} .glow{opacity:.5 !important}';
      document.head.appendChild(st);}return 1;})()`);
    await sleep(120);
    const r = await rpc(ws, 'Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    fs.writeFileSync(path.join(OUT, name + '.png'), Buffer.from(r.data, 'base64'));
    return name + '.png';
  };
  const stats = () => ev('JSON.stringify(window.__xkSM ? XK_SM_JS.stats() : null)').then((s) => (s ? JSON.parse(s) : null));
  let reqs = [];
  const reset = () => { consoleMsgs = []; responses = []; reqs = []; };
  const nav = (query) => rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/${PAGE}${query || ''}` });
  const smResponses = () => responses.filter((r) => r.u.includes('statemachine.json')).map((r) => r.s);
  /* 注入用例必须绕过浏览器缓存：同一上下文里前一次导航已经把 200 缓存住了，
     不清缓存的话"注入 404"会被缓存吃掉（实测踩过：sm=[200]）。 */
  const clearCache = () => rpc(ws, 'Network.clearBrowserCache');
  const click = async () => {
    await rpc(ws, 'Input.dispatchMouseEvent', { type: 'mousePressed', x: 640, y: 450, button: 'left', clickCount: 1 });
    await rpc(ws, 'Input.dispatchMouseEvent', { type: 'mouseReleased', x: 640, y: 450, button: 'left', clickCount: 1 });
  };

  const report = {
    page: PAGE || 'home',
    acceptancePacing: { used: '?xk-idle=3000&xk-host=800 (compressed)', realDefaults: 'idle=12000ms, cadence=25000ms, host cooldown=1800ms' },
    determinism: 'fixed virtual clock (XK_SM_JS.useVirtualClock(1000) + stepFixed(33ms)) because headless throttles rAF',
    cases: [],
  };

  const STEPS = 3500, DT = 33;   /* ~115s virtual time: 1000 steps of injection, then silence long enough for cadence (>25s) */
  const runSeed = async (seed, label, inject, navExtra) => {
    reset();
    await nav(`?seed=${seed}&xk-idle=3000&xk-host=800${navExtra || ''}`);
    /* 等内联脚本求值完（模块是页面内联的，导航刚回来时可能还没定义）*/
    for (let i = 0; i < 50; i++) {
      if (await ev('typeof XK_SM_JS !== "undefined"')) break;
      await sleep(200);
    }
    await sleep(600);
    await ev('XK_SM_JS.useVirtualClock(1000)');
    await click();
    for (let i = 0; i < 40; i++) {
      if (await ev('!!(window.__xkSM && window.__xkSM.on && XK_SM_JS.state.tookOver)')) break;
      await sleep(400);
    }
    let k = 0;
    if (inject) {
      await ev(`XK_SM_JS.stepFixed(${DT}, 1)`); k += 1;
      while (k < 1000) {
        await ev(`XK_SM_JS.stepFixed(${DT}, 50)`); k += 50;
        await ev(`XK_SM_JS.host('emotion',{emotion:'angry'})`);
        await ev(`XK_SM_JS.stepFixed(${DT}, 5)`); k += 5;
        await ev(`XK_SM_JS.host('voice',{line:'nav_monitor'})`);
      }
    }
    while (k < STEPS) {
      const n = Math.min(100, STEPS - k);
      await ev(`XK_SM_JS.stepFixed(${DT}, ${n})`); k += n;
    }
    const s = await stats();
    const sht = await shot(label);
    return { label, seed, steps: STEPS, dt: DT, stats: s, shot: sht, console: [...consoleMsgs] };
  };

  const r1 = await runSeed(20261015, 't8-sm-run1', true);
  const r2 = await runSeed(20261015, 't8-sm-run2', true);
  const tls = (st) => (st?.timelineRaw || []).map((e) => e.t + ':' + e.to + ':' + e.why);
  const tl1 = tls(r1.stats).join('|'), tl2 = tls(r2.stats).join('|');
  report.cases.push({
    name: 'A/B/C seed reproducible + reason counts + fingerprints',
    run1: { seed: r1.seed, stats: r1.stats, shot: r1.shot, console: r1.console },
    run2: { seed: r2.seed, stats: r2.stats, shot: r2.shot, console: r2.console },
    timelineRun1: tl1, timelineRun2: tl2, timelineEqual: tl1 === tl2 && tl1.length > 0,
    expect: 'fingerprints>=8; host:voice / host:emotion / host:idle / host:cadence each >=1; two timelines identical',
  });

  /* C2: replay */
  const b64 = await ev('XK_SM_JS.replayB64()');
  const r3 = await runSeed(20261015, 't8-sm-replay', false, '&replay=' + encodeURIComponent(b64));
  const tl3 = tls(r3.stats).join('|');
  report.cases.push({
    name: 'C2 ?replay replays the same segment',
    replayB64Length: (b64 || '').length,
    replayParamHead: '&replay=' + (b64 || '').slice(0, 48),
    timelineReplay: tl3,
    replayHasReplayReasons: tl3.indexOf(':replay') >= 0,
    stats: r3.stats, console: r3.console,
    expect: 'replayed node sequence matches the recorded one (timeline whys carry the :replay suffix)',
  });

  /* D: statemachine.json 404 -> prototype loop */
  inj.json404 = true; inj.jsonBad = false; reset(); await clearCache();
  await nav('?seed=7');
  await sleep(1500); await click(); await sleep(9000);
  report.cases.push({
    name: 'D fallback injection: statemachine.json 404',
    smResponses: smResponses(),
    reqUrls: reqs.filter((u) => u.includes('statemachine')).map((u) => u.replace(`http://127.0.0.1:${PORT}`, '')),
    stats: await stats(),
    proto: await ev('JSON.stringify({cur:(typeof cur!=="undefined"?cur:null),fi:(typeof fi!=="undefined"?fi:null)})'),
    opaque: await ev(`(function(){var c=document.getElementById('charCanvas');if(!c||!c.width)return -1;
      var d=c.getContext('2d').getImageData(0,0,c.width,c.height).data,on=0;for(var i=3;i<d.length;i+=4){if(d[i]>8)on++;}return on;})()`),
    nonOk: responses.filter((r) => r.s >= 400).map((r) => r.s + ' ' + r.u.split('/').pop()),
    console: [...consoleMsgs], shot: await shot('t8-sm-fallback404'),
    expect: 'on=false + err mentions 404; prototype clip still advancing; console 0 errors',
  });
  inj.json404 = false;

  /* E: bad JSON -> prototype loop */
  inj.jsonBad = true; reset(); await clearCache();
  await nav('?seed=7');
  await sleep(1500); await click(); await sleep(9000);
  report.cases.push({
    name: 'E fallback injection: statemachine.json bad JSON',
    smResponses: smResponses(),
    stats: await stats(),
    proto: await ev('JSON.stringify({cur:(typeof cur!=="undefined"?cur:null),fi:(typeof fi!=="undefined"?fi:null)})'),
    opaque: await ev(`(function(){var c=document.getElementById('charCanvas');if(!c||!c.width)return -1;
      var d=c.getContext('2d').getImageData(0,0,c.width,c.height).data,on=0;for(var i=3;i<d.length;i+=4){if(d[i]>8)on++;}return on;})()`),
    console: [...consoleMsgs], shot: await shot('t8-sm-fallbackbadjson'),
    expect: 'on=false + err mentions parse failure; prototype clip still advancing; console 0 errors',
  });
  inj.jsonBad = false;

  /* F: hidden pause + accumulator reset */
  reset();
  await nav('?seed=20261015&xk-idle=3000&xk-host=800');
  await sleep(1500); await click(); await sleep(6000);
  const beforeHidden = await stats();
  await ev(`(function(){Object.defineProperty(document,'hidden',{get:function(){return true;},configurable:true});
    Object.defineProperty(document,'visibilityState',{get:function(){return 'hidden';},configurable:true});
    document.dispatchEvent(new Event('visibilitychange'));return 1;})()`);
  const fiAtHide = await ev('window.__xkSM.fi');
  await sleep(6000);
  const fiAfterHide = await ev('window.__xkSM.fi');
  const hiddenSkipped = await ev('window.__xkSM.hiddenSkipped');
  await ev(`(function(){Object.defineProperty(document,'hidden',{get:function(){return false;},configurable:true});
    Object.defineProperty(document,'visibilityState',{get:function(){return 'visible';},configurable:true});
    document.dispatchEvent(new Event('visibilitychange'));return 1;})()`);
  await sleep(2500);
  const afterShow = await stats();
  report.cases.push({
    name: 'F hidden: pause + clear accumulator',
    beforeHidden: { fi: beforeHidden.fi, cur: beforeHidden.cur },
    fiAtHide, fiAfterHide, hiddenSkipped,
    afterShow: { fi: afterShow.fi, cur: afterShow.cur, frames: afterShow.frames },
    console: [...consoleMsgs],
    expect: 'while hidden fi stays put and hiddenSkipped grows; after returning it continues (no fast-forward)',
  });

  fs.writeFileSync(path.join(OUT, 't8-sm.json'), JSON.stringify(report, null, 1), 'utf8');
  console.log(JSON.stringify(report, null, 1).slice(0, 14000));
  console.log('\nevidence -> _shots/t8-sm.json');
  ws.close(); child.kill(); server.close();
  await sleep(300);
  try { fs.rmSync(udd, { recursive: true, force: true }); } catch { }
}
main().catch((err) => { console.error('FAILED: ' + err.message); server.close(); process.exit(1); });
