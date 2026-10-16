/* T4-③ 口型同步探针（只读；**不改播放器**）
   用法：node _dev/probe-lipsync.mjs [--pub=<目录>] [--page=//]

   为什么这样设计：
   1) 我方口型是**按音频时钟取包络**驱动的（kurisu-player.js:1896-1914）：
        mouthValue = clamp(envelope.values[floor(audio.currentTime*1000/hopMs)]*3.75, 0, 1)
      ⇒ 能测的"逻辑对齐"由两件事界定：**rAF 栅格**（可见量化）+ **包络窗 hopMs=10ms**（查表粒度）。
   2) **可闻**的 A/V 偏移（扬声器出声 vs 屏幕变化）**不在 JS 可达范围**：需要回环采集（WASAPI loopback / ffmpeg），
      本机无 ffmpeg ⇒ 本探针**不产出**可闻偏移数字（宁缺不编 ✗），只给出 JS 侧上界与"要什么才能测"。
   3) 播放器没有暴露只读状态出口（只有状态机的 window.__xkSm）⇒ 本探针用**画布运动能量**间接观测口型，
      并在报告里把"需要播放器加一个只读出口"写成待办（本探针**不动**那个文件）。

   输出：_shots/probe-lipsync.json + 控制台 INFO/PASS 行
*/
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = 'F:\\7AAA\\AI\\blog';
const argOf = (k, d) => { const a = process.argv.find((x) => x.startsWith('--' + k + '=')); return a ? a.split('=').slice(1).join('=') : d; };
const PUB = path.resolve(argOf('pub', path.join(ROOT, '_dev', '_build-char')));
const PAGE = argOf('page', '/');
const OUT = path.join(ROOT, '_shots');
const REPORT = path.join(OUT, 'probe-lipsync.json');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 8873, CDP = 9413;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.webm': 'video/webm', '.m4a': 'audio/mp4', '.mp3': 'audio/mpeg', '.woff2': 'font/woff2' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });
if (!fs.existsSync(path.join(PUB, 'index.html'))) { console.error('--pub 里没有 index.html：' + PUB); process.exit(2); }

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p.endsWith('/')) p += 'index.html';
  const f = path.join(PUB, p);
  if (!f.startsWith(PUB) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end('nf'); return; }
  res.writeHead(200, { 'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${PORT}`;

const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-lipsync-'));
const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  '--autoplay-policy=no-user-gesture-required', '--mute-audio',
  `--remote-debugging-port=${CDP}`, `--user-data-dir=${userDataDir}`, '--window-size=1280,900', 'about:blank'], { stdio: 'ignore' });
let target = null;
for (let i = 0; i < 40 && !target; i++) {
  await sleep(250);
  try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); } catch { }
}
if (!target) { console.error('连不上 Edge CDP'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r, j) => { ws.addEventListener('open', r); ws.addEventListener('error', j); });
let mid = 0; const waits = new Map(); const consoleMsgs = [];
const rpc = (method, params = {}) => { const id = ++mid; return new Promise((res, rej) => { waits.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); }); };
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waits.has(m.id)) { const w = waits.get(m.id); waits.delete(m.id); m.error ? w.rej(new Error(JSON.stringify(m.error))) : w.res(m.result); return; }
  const p = m.params || {};
  if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(p.type)) consoleMsgs.push(p.type + ': ' + (p.args || []).map((a) => a.value || a.description || '').join(' '));
  if (m.method === 'Runtime.exceptionThrown') consoleMsgs.push('EXCEPTION: ' + (p.exceptionDetails?.exception?.description || p.exceptionDetails?.text || ''));
});
await rpc('Page.enable'); await rpc('Runtime.enable');

await rpc('Page.navigate', { url: BASE + PAGE + (PAGE.indexOf('?') >= 0 ? '&' : '?') + 'xk-voice-diag=1' });
await sleep(3500);

/* 页内测量（全部只读：读 rAF 栅格 / 音频时钟 / 画布像素） */
const expr = `(async () => {
  const out = { url: location.pathname, canvases: [], audios: [], kurisu: [], raf: null, clock: null, mouth: null, env: null, err: [] };
  try {
    document.querySelectorAll('canvas').forEach((c, i) => out.canvases.push({ i, w: c.width, h: c.height, id: c.id || '', cls: (c.className || '').toString().slice(0, 40) }));
    out.audios = [...document.querySelectorAll('audio')].map((a, i) => ({ i, src: (a.currentSrc || a.src || '').split('/').slice(-2).join('/'), paused: a.paused, dur: a.duration }));
    out.kurisu = [...document.querySelectorAll('[data-xk-kurisu-mode],[data-xk-boot],[data-xk-kurisu-sm]')].map((e) => ({ tag: e.tagName, id: e.id || '', mode: e.getAttribute('data-xk-kurisu-mode') || '', boot: e.getAttribute('data-xk-boot') || '' }));

    /* ① rAF 栅格：口型的"可见量化"上界（每帧才更新一次 mouthValue） */
    const ts = [];
    await new Promise((res) => { const f = (t) => { ts.push(t); if (ts.length >= 150) return res(); requestAnimationFrame(f); }; requestAnimationFrame(f); });
    const d = []; for (let i = 1; i < ts.length; i++) d.push(ts[i] - ts[i - 1]);
    d.sort((a, b) => a - b);
    const q = (p) => d[Math.min(d.length - 1, Math.floor(d.length * p))];
    out.raf = { frames: ts.length, p50: +q(0.5).toFixed(2), p95: +q(0.95).toFixed(2), max: +d[d.length - 1].toFixed(2) };

    /* ② 音频时钟：拿 bank 里一条真实语音播一遍，看 currentTime 与墙钟的关系（漂移/停顿） */
    const bank = await (await fetch('/kurisu/voice/bank.json')).json();
    const ids = Object.keys(bank.lines || {});
    const pick = ids.find((k) => (bank.lines[k].audio || '').indexOf('synth/') >= 0) || ids[0];
    const line = bank.lines[pick];
    out.env = { id: pick, hopMs: bank.hopMs || 10, durationMs: line.durationMs, envelopeValues: line.envelopeValues,
                coverageMs: (line.envelopeValues || 0) * (bank.hopMs || 10), offsetMs: (line.envelopeValues || 0) * (bank.hopMs || 10) - (line.durationMs || 0),
                formula: bank.envelopeFormula };
    const a = new Audio('/' + line.audio);
    a.preload = 'auto';
    const samples = [];
    const t0 = performance.now();
    try { await a.play(); } catch (e) { out.err.push('play: ' + e.message); }
    await new Promise((res) => {
      const f = () => {
        samples.push([+(performance.now() - t0).toFixed(1), +(a.currentTime * 1000).toFixed(1)]);
        if (a.ended || performance.now() - t0 > 4000) return res();
        requestAnimationFrame(f);
      };
      requestAnimationFrame(f);
    });
    a.pause();
    const last = samples[samples.length - 1] || [0, 0];
    out.clock = { id: pick, samples: samples.length, wallMs: last[0], audioMs: last[1], ratio: last[0] ? +(last[1] / last[0]).toFixed(4) : null,
                  stalls: samples.filter((s, i) => i > 0 && s[1] === samples[i - 1][1]).length };

    /* ③ 画布口型运动：最大画布的中下部区域逐帧均值差（只读像素；同源图不污染画布） */
    const cs = [...document.querySelectorAll('canvas')].sort((x, y) => y.width * y.height - x.width * x.height);
    if (cs.length) {
      const c = cs[0], ctx = c.getContext('2d');
      const rx = Math.floor(c.width * 0.30), ry = Math.floor(c.height * 0.55), rw = Math.floor(c.width * 0.40), rh = Math.floor(c.height * 0.35);
      const energ = [];
      for (let i = 0; i < 120; i++) {
        try {
          const px = ctx.getImageData(rx, ry, rw, rh).data;
          let s = 0; for (let j = 0; j < px.length; j += 16) s += px[j];
          energ.push(+(s / (px.length / 16)).toFixed(2));
        } catch (e) { out.err.push('getImageData: ' + e.message); break; }
        await new Promise((r) => requestAnimationFrame(r));
      }
      const dif = []; for (let i = 1; i < energ.length; i++) dif.push(Math.abs(energ[i] - energ[i - 1]));
      const mean = dif.reduce((x, y) => x + y, 0) / (dif.length || 1);
      out.mouth = { canvas: { w: c.width, h: c.height }, frames: energ.length, meanDelta: +mean.toFixed(3),
                    maxDelta: +Math.max(...dif, 0).toFixed(3), moving: dif.filter((x) => x > mean * 2).length };
    }

    /* ④ ★L7 端到端口型（2026-10-16 主窗口加的**只读**取证出口 __xkVoiceTick；本探针只读、不改播放器）
       必须走**播放器自己的说话路径**：否则 VOICE.speaking 不为真、出口不发布真值。
       出口契约：window.__xkVoiceTick = { t(音频秒), mouth, clip, hopMs, speaking, at(performance.now()) } */
    out.diag = { entry: 'n/a', hookType: typeof window.__xkVoiceTick, samples: [] };
    try {
      const K = window.KurisuPlayer;
      if (!K) { out.diag.entry = 'no KurisuPlayer'; }
      else if (typeof K.speakGroup === 'function') { await K.speakGroup('/', 'greeting'); out.diag.entry = 'speakGroup'; }
      else if (typeof K.speak === 'function') { await K.speak('greet_first'); out.diag.entry = 'speak'; }
      else if (typeof K.stage === 'function' && K.stage() && typeof K.stage().speak === 'function') { await K.stage().speak('greet_first'); out.diag.entry = 'stage.speak'; }
      else { out.diag.entry = 'no-usable-entry'; }
      await new Promise((r) => setTimeout(r, 250));
      const st = [];
      await new Promise((res) => {
        const t0 = performance.now();
        const f = () => {
          const v = window.__xkVoiceTick;
          if (v && v.speaking) st.push({ at: v.at, t: v.t, mouth: v.mouth, clip: v.clip, hopMs: v.hopMs });
          if (performance.now() - t0 > 3200) return res();
          requestAnimationFrame(f);
        };
        requestAnimationFrame(f);
      });
      out.diag.samples = st;
      out.diag.hookAfter = typeof window.__xkVoiceTick;
    } catch (e) { out.err.push('L7: ' + e.message); }
  } catch (e) { out.err.push('fatal: ' + e.message); }
  return JSON.stringify(out);
})()`;

const r = await rpc('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
const m = JSON.parse(r.result.value);

/* ---- L7 端到端（2026-10-16）：①契约公式逐样本核对 ②有效更新栅格 ③时钟关系 ④默认关闭 ---- */
let formula = { checked: 0, mismatches: 0, firstWindow: 0, worstAbs: 0, clip: null, hopMs: null };
if (m.diag && m.diag.samples && m.diag.samples.length) {
  try {
    const bank = await (await fetch(BASE + '/kurisu/voice/bank.json')).json();
    const withClip = m.diag.samples.filter((s) => s.clip && bank.lines && bank.lines[s.clip]);
    const clip = withClip.length ? withClip[0].clip : null;
    if (clip) {
      const line = bank.lines[clip];
      const env = await (await fetch(BASE + '/' + line.envelope)).json();
      const hop = env.hopMs || bank.hopMs || 10;
      const vals = env.values || [];
      formula.clip = clip; formula.hopMs = hop;
      for (const s of m.diag.samples) {
        if (typeof s.mouth !== 'number' || typeof s.t !== 'number') continue;
        let i = Math.floor((s.t * 1000) / hop);
        if (i < 0) i = 0;
        let v = vals[i]; if (typeof v !== 'number') v = 0;
        let exp = Math.min(1, Math.max(0, v * 3.75));
        /* 首窗保底（契约：speaking 且 i===0 且 contracted 更小时取 max(0.12, contracted)）——单独计数，算作合规 */
        if (i === 0) { formula.firstWindow++; exp = Math.max(0.12, exp); }
        formula.checked++;
        const dd = Math.abs(exp - s.mouth);
        if (dd > formula.worstAbs) formula.worstAbs = dd;
        if (dd > 1e-6) formula.mismatches++;
      }
    }
  } catch (e) { formula.err = String((e && e.message) || e); }
}
let grid = null;
if (m.diag && m.diag.samples && m.diag.samples.length > 1) {
  const d = [];
  for (let i = 1; i < m.diag.samples.length; i++) {
    if (m.diag.samples[i].mouth !== m.diag.samples[i - 1].mouth) d.push(m.diag.samples[i].at - m.diag.samples[i - 1].at);
  }
  d.sort((a, b) => a - b);
  const q = (p) => (d.length ? +d[Math.min(d.length - 1, Math.floor(d.length * p))].toFixed(2) : null);
  grid = { changes: d.length, p50: q(0.5), p95: q(0.95), max: d.length ? +d[d.length - 1].toFixed(2) : null };
}
let clockRel = null;
if (m.diag && m.diag.samples && m.diag.samples.length > 1) {
  const f0 = m.diag.samples[0], l0 = m.diag.samples[m.diag.samples.length - 1];
  const dAt = l0.at - f0.at, dT = (l0.t - f0.t) * 1000;
  clockRel = { dAtMs: +dAt.toFixed(1), dTms: +dT.toFixed(1), ratio: dAt ? +(dT / dAt).toFixed(4) : null,
               stalls: m.diag.samples.filter((s, i) => i > 0 && s.t === m.diag.samples[i - 1].t).length };
}
let defaultOff = { ok: false, msg: '未测' };
try {
  await rpc('Page.navigate', { url: BASE + PAGE });
  await sleep(2500);
  const rr = await rpc('Runtime.evaluate', { expression: 'typeof window.__xkVoiceTick', returnByValue: true });
  const ty = String(rr.result.value);
  defaultOff = { ok: ty === 'undefined', msg: '不带 ?xk-voice-diag=1 时 typeof window.__xkVoiceTick = ' + ty };
} catch (e) { defaultOff = { ok: false, msg: '默认关闭检查失败: ' + ((e && e.message) || e) }; }

const checks = [];
const rec = (id, ok, msg) => checks.push({ id, ok, msg });
rec('L1 rAF 栅格可测', !!m.raf, m.raf ? `p50=${m.raf.p50}ms p95=${m.raf.p95}ms max=${m.raf.max}ms` : '读不到');
rec('L2 包络窗 hopMs=10（查表粒度）', m.env && m.env.hopMs === 10, m.env ? `hopMs=${m.env.hopMs}` : '读不到');
rec('L3 包络覆盖 vs 音频时长（系统性偏移）', !!(m.env && Math.abs(m.env.offsetMs) <= 10 * 5),
  m.env ? `envCov=${m.env.coverageMs}ms / dur=${m.env.durationMs}ms ⇒ offset=${m.env.offsetMs}ms` : '读不到');
rec('L4 音频时钟可前进（含限流/静音环境）', !!(m.clock && m.clock.audioMs > 0), m.clock ? `wall=${m.clock.wallMs}ms audio=${m.clock.audioMs}ms ratio=${m.clock.ratio} 停顿帧=${m.clock.stalls}` : '读不到');
rec('L5 画布可读（像素级口型观测可行）', !!(m.mouth && m.mouth.frames > 0), m.mouth ? `canvas=${m.mouth.canvas.w}x${m.mouth.canvas.h} 帧=${m.mouth.frames} 运动帧=${m.mouth.moving} 均值差=${m.mouth.meanDelta}` : '读不到（可能跨源污染或页面无画布）');
rec('L6 控制台无 error/warning', consoleMsgs.length === 0, consoleMsgs.slice(0, 3).join(' | ') || '0 条');
rec('L7a 出口默认关闭（零开销；不带 ?xk-voice-diag=1）', defaultOff.ok, defaultOff.msg);
rec('L7b 端到端口型采样（走播放器自身说话路径）', !!(m.diag && m.diag.samples && m.diag.samples.length),
  m.diag ? `入口=${m.diag.entry} 采样=${m.diag.samples.length} 帧（hook 类型=${m.diag.hookType}）` : '读不到');
rec('L7c 发布值 == 契约公式 clamp(envelope[floor(t/hop)]*3.75,0,1)', formula.checked > 0 && formula.mismatches === 0,
  formula.checked ? `核对 ${formula.checked} 样本 / 不符 ${formula.mismatches} / 最大偏差 ${formula.worstAbs}（clip=${formula.clip} hopMs=${formula.hopMs}；首窗保底 0.12 命中 ${formula.firstWindow} 次，按契约计为合规）`
    : ('无样本' + (formula.err ? ' err=' + formula.err : '')));
rec('L7d 有效更新栅格与时钟关系', !!(grid && grid.changes > 0),
  (grid ? `mouth 变化 ${grid.changes} 次；Δat p50=${grid.p50}ms p95=${grid.p95}ms max=${grid.max}ms` : '无变化点')
  + (clockRel ? ` ｜ Δt/Δat=${clockRel.ratio}（停顿帧 ${clockRel.stalls}）` : ''));

const jsBound = m.raf ? +(m.raf.p95 + (m.env?.hopMs || 10)).toFixed(2) : null;
const report = {
  probe: 'probe-lipsync', at: new Date().toISOString(), pub: PUB, page: PAGE,
  principle: 'mouthValue = clamp(envelope.values[floor(audio.currentTime*1000/hopMs)]*3.75, 0, 1)  // kurisu-player.js:1896-1914',
  measured: m,
  derived: {
    jsSideUpperBoundMs: jsBound,
    jsSideUpperBoundNote: 'JS 侧可见量化上界 = rAF p95 + 包络窗 hopMs；**不含**扬声器可闻偏移',
    audibleOffset: null,
    audibleOffsetNote: '可闻 A/V 偏移**不是 JS 可测**：需回环采集（WASAPI loopback / ffmpeg 录屏+录声）后做互相关。本机无 ffmpeg ⇒ 本期不产出该数字（宁缺不编 ✗）',
    needsPlayerHook: '要端到端测"渲染出来的口型"，需播放器暴露只读出口（如 window.__xkVoiceTick={t,mouth,clip}）——本探针**未改动** static/js/kurisu-player.js，已列为待办',
  },
  checks,
  consoleMsgs,
};
fs.writeFileSync(REPORT, JSON.stringify(report, null, 1), 'utf8');

console.log('=== probe-lipsync ===');
for (const c of checks) console.log(`  ${c.ok ? 'PASS' : 'INFO'}  ${c.id} :: ${c.msg}`);
console.log(`  derived: JS 侧上界 = ${jsBound} ms（rAF p95 + hopMs）`);
console.log(`  report → ${REPORT}`);
const fails = checks.filter((c) => !c.ok).length;
console.log(`=== ${checks.length - fails}/${checks.length} PASS ===`);

try { ws.close(); } catch { }
child.kill();
server.close();
process.exit(0);
