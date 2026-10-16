#!/usr/bin/env node
/* 角色动作线 · 状态机可运行性探针 v2（只读；自建端口 8798/9345）
   v2 修正：① 显式 smStart（v1 漏了，导致 graph 从未加载）② 用真实挂载点标记（克隆 rail -> stage）
            ③ 注入用户手势（自动播放策略）④ 口型出口改名 __xkVoiceTick
   产物：_shots/probe-sm-walk.json（+ 截图） */
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = 'F:/7AAA/AI/blog';
const PUB = path.join(ROOT, '_dev/_build-sm');
const OUT = path.join(ROOT, '_shots');
const PORT = 8798, CDP = 9345, VW = 1440, VH = 900;
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PAGE = '/demo/';
const SM_MS = 24000, TRIGGER_MS = 3000;

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.css': 'text/css; charset=utf-8', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.avif': 'image/avif', '.m4a': 'audio/mp4', '.webm': 'video/webm', '.mp4': 'video/mp4', '.woff2': 'font/woff2', '.txt': 'text/plain; charset=utf-8', '.xml': 'application/xml' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function serve() {
  return http.createServer((req, res) => {
    let p = decodeURIComponent(req.url.split('?')[0]);
    if (p.endsWith('/')) p += 'index.html';
    const f = path.join(PUB, p);
    if (!f.startsWith(PUB) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end('nf'); return; }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
}

function cdpConnect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0; const pend = new Map();
  ws.addEventListener('message', (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
  });
  const ready = new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  function send(method, params = {}, timeoutMs = 30000) {
    return new Promise((res, rej) => {
      const myId = ++id; pend.set(myId, { res, rej });
      ws.send(JSON.stringify({ id: myId, method, params }));
      setTimeout(() => { if (pend.has(myId)) { pend.delete(myId); rej(new Error('cdp timeout: ' + method)); } }, timeoutMs);
    });
  }
  return { ws, ready, send };
}

async function evalJs(c, expr, awaitPromise = true, timeoutMs = 120000) {
  const r = await c.send('Runtime.evaluate', { expression: expr, awaitPromise, returnByValue: true, userGesture: true }, timeoutMs);
  if (r.exceptionDetails) throw new Error('page exception: ' + JSON.stringify(r.exceptionDetails.exception?.description || r.exceptionDetails.text));
  return r.result?.value;
}

const report = { at: new Date().toISOString(), page: PAGE, steps: {}, sm: null, matrix: [], control: [], errors: [], shots: [] };

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const server = serve();
  await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
  report.steps.server = `http://127.0.0.1:${PORT} -> ${PUB}`;

  const userDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sm-walk2-'));
  const edge = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--mute-audio', '--autoplay-policy=no-user-gesture-required', `--remote-debugging-port=${CDP}`, `--user-data-dir=${userDir}`, `--window-size=${VW},${VH}`, 'about:blank'], { stdio: 'ignore' });
  report.steps.edge = `pid=${edge.pid} cdp=${CDP}`;

  let target = null;
  for (let i = 0; i < 40 && !target; i++) { await sleep(300); try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); } catch { } }
  if (!target) throw new Error('拿不到 CDP target');

  const c = cdpConnect(target.webSocketDebuggerUrl);
  await c.ready;
  await c.send('Page.enable'); await c.send('Runtime.enable');
  await c.send('Page.navigate', { url: `http://127.0.0.1:${PORT}${PAGE}` }, 60000);
  for (let i = 0; i < 60; i++) { const s = await evalJs(c, 'document.readyState', false, 20000).catch(() => null); if (s === 'complete') break; await sleep(500); }

  // 真实用户手势（自动播放策略）
  await c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: 200, y: 200, button: 'left', clickCount: 1 }).catch(() => { });
  await c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: 200, y: 200, button: 'left', clickCount: 1 }).catch(() => { });
  report.steps.gesture = 'mousePressed+Released @200,200';

  report.steps.playerPresent = await evalJs(c, 'typeof window.KurisuPlayer === "object"', false);
  report.steps.mountsInPage = await evalJs(c, `(() => { const a = Array.from(document.querySelectorAll('[data-xk-kurisu]')); return { count: a.length, attrs: a.map(e => e.getAttribute('data-xk-kurisu')), hasSmOn: a.filter(e => e.getAttribute('data-xk-kurisu-sm') === 'on').length, keys: Array.from(document.documentElement.attributes).map(x => x.name).filter(n => n.indexOf('xk-') === 0) }; })()`, false);

  const boot = await evalJs(c, `(async () => {
    window.__xkVoiceOn = true;
    if (typeof window.KurisuPlayer !== 'object') {
      await new Promise((res, rej) => { const s = document.createElement('script'); s.src = '/js/kurisu-player.js'; s.onload = res; s.onerror = () => rej(new Error('player 加载失败')); document.head.appendChild(s); });
      await new Promise(r => setTimeout(r, 300));
    }
    const src = document.querySelector('[data-xk-kurisu]');
    const wrap = document.createElement('div');
    wrap.id = 'sm-probe-host';
    wrap.style.cssText = 'position:fixed;left:0;top:0;width:560px;height:420px;z-index:99999;background:#0b0b0b';
    if (src) { wrap.innerHTML = src.outerHTML; } else { wrap.innerHTML = '<div data-xk-kurisu-canvas></div>'; }
    const d = wrap.firstElementChild || wrap;
    d.setAttribute('data-xk-kurisu', 'stage');      /* SM 硬前提：mode === 'stage' */
    d.setAttribute('data-xk-kurisu-sm', 'on');
    d.removeAttribute('data-xk-kurisu-avatar');
    d.style.cssText = 'position:absolute;inset:0';
    document.body.appendChild(wrap);
    const p = window.KurisuPlayer.create({ mount: d, mode: 'stage', stateMachine: true, basePath: '/', manifest: '/kurisu/manifest.json' });
    window.__smP = p;
    await p.ready();
    const clips = Object.keys((p.manifest && p.manifest.clips) || {});
    const clipsMed = Object.keys((p.manifest && p.manifest.clipsMedium) || {});
    const played = await p.play('idle').catch(e => 'play-error:' + e.message);
    const started = await p.smStart({ durationMs: ${SM_MS}, hostTriggerEveryMs: ${TRIGGER_MS} }).then(r => (r === undefined ? '__undefined' : 'ok')).catch(e => 'smStart-error:' + e.message);
    return { smOn: !!p.smOn, mode: p.mode, hasCanvasEl: !!d.querySelector('[data-xk-kurisu-canvas]'), clipsCount: clips.length, clips: clips, clipsMediumCount: clipsMed.length, played: String(played && played.clip ? played.clip : played), smStart: String(started), graph: !!(p.graph), nodes: p.graph ? p.graph.nodes.length : 0, edges: p.graph ? p.graph.edges.length : 0, hostEntries: (p.graph && p.graph.host_triggered_entries) || null, maxWalkBytes: (p.graph && p.graph.max_walk_bytes) || null };
  })()`, true, 180000);
  report.steps.boot = boot;

  const samples = []; const t0 = Date.now();
  while (Date.now() - t0 < SM_MS + 4000) {
    await sleep(4000);
    const elapsed = Date.now() - t0;
    const s = await evalJs(c, `(() => { const d = window.__xkSm; const p = window.__smP; const cv = document.querySelector('#sm-probe-host canvas'); let nb = null; if (cv && cv.getContext) { try { const g = cv.getContext('2d'); const im = g.getImageData(0, 0, Math.min(48, cv.width), Math.min(48, cv.height)).data; let n = 0; for (let i = 0; i < im.length; i += 4) { if (im[i] || im[i+1] || im[i+2]) n++; } nb = n; } catch (e) { nb = 'err:' + e.message; } } return { t: ${elapsed}, seqLen: d ? d.seq.length : null, edgesLen: d ? d.edges.length : null, visited: d ? Object.keys(d.visited || {}).length : null, errs: d ? d.errors.length : null, cur: p ? (p.currentClipName || null) : null, smRunning: p ? !!p.smRunning : null, smBytes: p ? (p.smBytes || null) : null, canvasNonBlank: nb, canvasSize: cv ? (cv.width + 'x' + cv.height) : null, tick: window.__xkVoiceTick ? { t: window.__xkVoiceTick.t, mouth: window.__xkVoiceTick.mouth, clip: window.__xkVoiceTick.clip, speaking: window.__xkVoiceTick.speaking } : 'ABSENT' }; })()`, false, 60000);
    samples.push(s);
    if (s && s.errs) report.errors.push('sm.errors=' + s.errs + ' @' + s.t);
  }
  report.steps.samples = samples;

  report.sm = await evalJs(c, `(() => { const d = window.__xkSm || {}; const p = window.__smP || {}; const seq = (d.seq || []).map(x => x.clip); const visited = Object.keys(d.visited || {}); const edges = (d.edges || []).map(e => (e.from || '?') + '->' + (e.to || '?')); return { seed: d.seed, seqLen: seq.length, seqOrder: seq, distinctClips: Array.from(new Set(seq)), visitedCount: visited.length, visited: visited, edgesWalked: edges.length, edgesSample: edges.slice(0, 15), errors: (d.errors || []).map(e => String(e).slice(0, 160)), currentClip: p.currentClipName || null, smBytes: p.smBytes || null, canvasSize: (function () { const cv = document.querySelector('#sm-probe-host canvas'); return cv ? cv.width + 'x' + cv.height : null; })() }; })()`, false, 60000);

  // 逐个试探宿主控制面
  const controls = [
    ['play(idle)', 'window.__smP.play("idle")'],
    ['play(thinking)', 'window.__smP.play("thinking")'],
    ['play(thinking_trans)', 'window.__smP.play("thinking_trans")'],
    ['play(speaking_trans)', 'window.__smP.play("speaking_trans")'],
    ['play(speaking_short)', 'window.__smP.play("speaking_short")'],
    ['play(angry_trans)', 'window.__smP.play("angry_trans")'],
    ['play(sad_trans)', 'window.__smP.play("sad_trans")'],
    ['play(shy_trans)', 'window.__smP.play("shy_trans")'],
    ['play(surprise_trans)', 'window.__smP.play("surprise_trans")'],
    ['play(closed_eye_trans)', 'window.__smP.play("closed_eye_trans")'],
    ['play(trans_smile)', 'window.__smP.play("trans_smile")'],
    ['play(sad)', 'window.__smP.play("sad")'],
    ['play(smile)', 'window.__smP.play("smile")'],
    ['play(idle2)', 'window.__smP.play("idle2")'],
    ['play(idle_mic_wind)', 'window.__smP.play("idle_mic_wind")'],
    ['play(idle_side_butterfly)', 'window.__smP.play("idle_side_butterfly")'],
    ['play(idle_side_wind)', 'window.__smP.play("idle_side_wind")'],
    ['play(idle_str_wind)', 'window.__smP.play("idle_str_wind")'],
    ['play(idle_closed_eye)', 'window.__smP.play("idle_closed_eye")'],
    ['play(trans_standby)', 'window.__smP.play("trans_standby")'],
    ['setEmotion(angry)', 'window.__smP.setEmotion ? window.__smP.setEmotion("angry") : "NO_METHOD"'],
    ['smDiag()', 'window.KurisuPlayer.smDiag()'],
    ['instances()', 'window.KurisuPlayer.instances().length'],
    ['voiceTick', 'window.__xkVoiceTick || "ABSENT"'],
    ['xkVoice(旧名)', 'window.__xkVoice || "ABSENT"'],
  ];
  for (const [name, expr] of controls) {
    const t = Date.now(); let val = null, err = null;
    try { val = await evalJs(c, `(async () => { const r = await (${expr}); return (r === undefined) ? "__undefined" : (typeof r === "object" ? JSON.stringify(r).slice(0, 220) : String(r)); })()`, true, 60000); } catch (e) { err = String(e.message).slice(0, 200); }
    report.control.push({ name, ms: Date.now() - t, value: val, error: err });
  }

  // 说一句 + 采口型（已注入手势 + autoplay 放开）
  try {
    const sp = await evalJs(c, `(async () => { window.__xkVoiceOn = true; const r = await window.__smP.speak('greet_back', null).catch(e => ({ ok: false, error: String(e.message) })); await new Promise(r2 => setTimeout(r2, 1200)); return { speak: JSON.stringify(r).slice(0, 200), tick: window.__xkVoiceTick ? JSON.stringify(window.__xkVoiceTick) : 'ABSENT' }; })()`, true, 60000);
    report.steps.speakSample = sp;
  } catch (e) { report.errors.push('speak: ' + e.message); }

  try {
    const shot = await c.send('Page.captureScreenshot', { format: 'png' }, 60000);
    const fp = path.join(OUT, 'probe-sm-walk2-final.png');
    fs.writeFileSync(fp, Buffer.from(shot.data, 'base64'));
    report.shots.push(fp);
  } catch (e) { report.errors.push('screenshot: ' + e.message); }

  fs.writeFileSync(path.join(OUT, 'probe-sm-walk.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ boot: report.steps.boot, mounts: report.steps.mountsInPage, sm: report.sm, lastSamples: report.steps.samples.slice(-3), matrix: report.control.map(x => ({ n: x.name, ms: x.ms, v: (x.value || '').slice(0, 70), e: x.error ? 'ERR' : '' })), speak: report.steps.speakSample, errors: report.errors.slice(0, 6) }, null, 2));

  try { c.ws.close(); } catch { } try { edge.kill(); } catch { } server.close(); process.exit(0);
}

main().catch((e) => { console.error('PROBE FAILED: ' + (e && e.stack || e)); try { fs.writeFileSync(path.join(OUT, 'probe-sm-walk.json'), JSON.stringify({ ...report, fatal: String(e && e.message || e) }, null, 2)); } catch { } process.exit(1); });
