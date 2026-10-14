/* 逐页产物验收 + **首屏字节硬门禁**（_dev/ 本地工具，零第三方依赖）
   node _dev/gate-firstscreen.mjs [--budget=1572864] [--static] [--prefix=pages]

   做什么：
     ① 起本地 http 服务（只读 public/，不碰产物、不用 hugo server，避免 livereload 污染断言）
     ② CDP 连 Edge headless 1280×900，逐页导航：收 Network 响应 + 控制台报错
     ③ **门禁**：导航后 1.5s 内请求到的**全部资产**（图片/字体/样式/脚本）字节 ≤ budget（默认 1,572,864 B）
        任一页超标 → 打印超标文件清单 + **退出码 1**（这就是"真门禁"，不是报告）
     ④ 产物自查：正文长度 / 关键标记 / 站外资源引用 / 本地引用是否落到真实文件
     ⑤ hash 路由逐条切页，核对 app.js 的 data-xk-render 与正文长度
     ⑥ 主页额外取证：autoplay 门控（未交互时声音静默、有"点我开声"入口）+ 状态机诊断
   --static = 不跑浏览器，按 HTML 引用静态估算（输出里会明确标注"静态估算，未跑浏览器"）
   输出：_shots/<prefix>-*.png、_shots/<prefix>-report.json
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
const PORT = 8797, CDP = 9344, VW = 1280, VH = 900;
const argOf = (k) => { const a = process.argv.find((x) => x.startsWith('--' + k + '=')); return a ? a.split('=')[1] : null; };
const BUDGET = Number(argOf('budget') || 1572864);
const PREFIX = argOf('prefix') || 'pages';
const STATIC_ONLY = process.argv.includes('--static');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8', '.woff2': 'font/woff2', '.m4a': 'audio/mp4', '.wav': 'audio/wav', '.opus': 'audio/ogg' };
const ASSET_RE = /\.(webp|png|jpe?g|gif|svg|ico|css|js|woff2?|wav|opus|m4a)$/i;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

/* 页面清单：file = 产物里的文件，expect = app.js 对这条路由的 name（VIEW_TPL 的键） */
const PAGES = [
  { name: 'home', file: 'index.html', url: 'index.html', wait: 12000, expect: 'home', marker: '.xk-crt' },
  { name: 'monitor', file: 'alerts/index.html', url: 'alerts/', wait: 4000, expect: 'monitor', marker: '[data-xk-screen]' },
  { name: 'notes', file: 'posts/index.html', url: 'posts/', wait: 3000, expect: 'notes', marker: '.xk-page__title' },
  { name: 'labs', file: 'labs/index.html', url: 'labs/', wait: 3000, expect: 'range', marker: '[data-xk-pg-run]' },
  { name: 'about', file: 'about/index.html', url: 'about/', wait: 3000, expect: 'about', marker: '.xk-page__title' },
  { name: 'ai', file: 'ai/index.html', url: 'ai/', wait: 3000, expect: 'ai', marker: '#xk-ask-input' }
];

function byteOf(url) {
  const rel = url.split('?')[0].split('#')[0];
  const f = path.join(PUB, rel.replace(/^\//, '').replace(/\//g, path.sep));
  return (fs.existsSync(f) && fs.statSync(f).isFile()) ? fs.statSync(f).size : 0;
}

/* 产物自查（与门禁⑦同口径：只查资源引用，正文里的文字链接不算） */
function productCheck(htmlFile) {
  const html = fs.readFileSync(htmlFile, 'utf8');
  const ext = [], locals = [];
  let m;
  const re = /(?:src|href|srcset|poster)="([^"]+)"/g;
  while ((m = re.exec(html))) {
    const u = m[1].trim();
    if (!u || u.startsWith('#') || u.startsWith('data:') || u.startsWith('mailto:') || u.startsWith('javascript:')) continue;
    if (/^(https?:)?\/\//.test(u)) { if (!/xiaokeqing\.cn/.test(u)) ext.push(u); continue; }
    if (u.startsWith('/')) locals.push(u.split('?')[0].split('#')[0]);
  }
  const cssUrl = /url\((https?:\/\/[^)]+)\)/g;
  while ((m = cssUrl.exec(html))) { if (!/xiaokeqing\.cn/.test(m[1])) ext.push(m[1]); }
  const missing = [];
  for (const u of [...new Set(locals)]) {
    const f = u === '/' ? path.join(PUB, 'index.html') : path.join(PUB, u.replace(/\//g, path.sep));
    if (!fs.existsSync(f) && !fs.existsSync(f + path.sep + 'index.html') && !fs.existsSync(f + '.html')) missing.push(u);
  }
  const text = html.replace(/<script[\s\S]*?<\/script>/g, ' ').replace(/<style[\s\S]*?<\/style>/g, ' ')
    .replace(/<[^>]+>/g, ' ').replace(/&[a-z]+;/g, ' ').replace(/\s+/g, ' ').trim();
  return {
    bytes: fs.statSync(htmlFile).size, textChars: text.length,
    extRefs: [...new Set(ext)], missingLocal: missing,
    markers: {
      content: /id=["']?content["'\s>]/.test(html), ssr: /data-xk-ssr=/.test(html),
      views: /id=["']?xk-views["'\s>]/.test(html), crt: /xk-crt/.test(html),
      nav: /xk-nav|spa-nav|#\/home/.test(html), player: /kurisu-player\.js/.test(html),
      app: /\/js\/app\.js/.test(html), cname: fs.existsSync(path.join(PUB, 'CNAME'))
    }
  };
}

/* --static：不跑浏览器的降级口径（明确标注，不假装测过） */
function staticEstimate() {
  const rows = [];
  for (const p of PAGES) {
    const file = path.join(PUB, p.file);
    if (!fs.existsSync(file)) { rows.push({ page: p.name, bytes: 0, pass: false, note: '缺产物文件' }); continue; }
    const html = fs.readFileSync(file, 'utf8');
    const refs = new Set();
    let m;
    const re = /(?:src|href)="(\/[^"]+)"/g;
    while ((m = re.exec(html))) { if (ASSET_RE.test(m[1])) refs.add(m[1]); }
    // 样式表里引到的图片（保守：把 CSS 里出现的本站 url() 都算上）
    for (const f of fs.readdirSync(path.join(PUB, 'css'))) {
      if (!f.endsWith('.css')) continue;
      const css = fs.readFileSync(path.join(PUB, 'css', f), 'utf8');
      const u = /url\((\/[^)]+)\)/g;
      let mm;
      while ((mm = u.exec(css))) { if (ASSET_RE.test(mm[1])) refs.add(mm[1]); }
    }
    let total = 0;
    for (const r of refs) total += byteOf(r);
    rows.push({ page: p.name, bytes: total, pass: total <= BUDGET, files: [...refs] });
  }
  return rows;
}

let nextId = 0;
function rpc(ws, method, params = {}) {
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const on = (ev) => { let m; try { m = JSON.parse(ev.data); } catch { return; } if (m.id !== id) return; ws.removeEventListener('message', on); m.error ? reject(new Error(method + ': ' + JSON.stringify(m.error))) : resolve(m.result); };
    ws.addEventListener('message', on);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function main() {
  if (STATIC_ONLY) {
    const rows = staticEstimate();
    let bad = 0;
    console.log('== 首屏字节门禁（预算 %d B = %s KB）· **静态估算，未跑浏览器** ==',
      BUDGET, (BUDGET / 1024).toFixed(0));
    for (const r of rows) {
      console.log('  [%s] %-8s %8s KB  %s', r.pass ? 'PASS' : 'FAIL', r.page,
        (r.bytes / 1024).toFixed(0), r.pass ? '' : '（静态估算把整份 CSS 的 url() 都算进来了，偏保守）');
      if (!r.pass) bad++;
    }
    fs.writeFileSync(path.join(OUT, PREFIX + '-report.json'),
      JSON.stringify({ mode: 'static-estimate', note: '静态估算，未跑浏览器', budget: BUDGET, pages: rows }, null, 1), 'utf8');
    console.log(bad ? `\n静态估算：${bad} 页超预算 → 退出码 1` : '\n静态估算：全部在预算内');
    process.exitCode = bad ? 1 : 0;
    return;
  }

  const server = http.createServer((req, res) => {
    let p = decodeURIComponent(req.url.split('?')[0]);
    if (p.endsWith('/')) p += 'index.html';
    const f = path.join(PUB, p);
    if (!f.startsWith(PUB) || !fs.existsSync(f) || !fs.statSync(f).isFile()) { res.writeHead(404); res.end('404'); return; }
    res.writeHead(200, { 'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
  /* 新外壳样式表（assets/css/xk-app.css）现在**不在**站点总样式表里 —— 这是刻意的：
     它每条规则都带 `#xk-app` 前缀，而线上的 `spa-view-*.html` 里没有 `#xk-app` 根元素
     （那份 demo 的 markup 还带演示数字，不能原样搬进生产页）。所以判据是"一致性"：
       产物样式表里有 #xk-app 规则 ⇔ 页面上真有 #xk-app 根元素
     两种事故都能被这条抓住：白下 26KB 惰性 CSS / 以为接好了其实没接。 */
  const cssFiles = fs.readdirSync(path.join(PUB, 'css')).filter((f) => f.endsWith('.css'));
  let shellRules = 0;
  for (const f of cssFiles) {
    shellRules += (fs.readFileSync(path.join(PUB, 'css', f), 'utf8').match(/#xk-app/g) || []).length;
  }
  const shellRoots = {};
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-gate-'));
  const child = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--mute-audio', `--remote-debugging-port=${CDP}`, `--user-data-dir=${userDataDir}`, `--window-size=${VW},${VH}`, 'about:blank'], { stdio: 'ignore' });
  let target = null;
  for (let i = 0; i < 60 && !target; i++) {
    await sleep(400);
    try { const l = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); } catch { }
  }
  if (!target) throw new Error('连不上 Edge 调试端口');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });

  let responses = [], consoleMsgs = [];
  ws.addEventListener('message', (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.method === 'Network.responseReceived') { const r = m.params.response; responses.push({ status: r.status, url: r.url, type: m.params.type }); }
    if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type)) consoleMsgs.push(m.params.type + ': ' + (m.params.args || []).map((a) => a.value || a.description || '').join(' '));
    if (m.method === 'Runtime.exceptionThrown') consoleMsgs.push('EXCEPTION: ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
  });
  await rpc(ws, 'Page.enable'); await rpc(ws, 'Runtime.enable'); await rpc(ws, 'Network.enable');
  await rpc(ws, 'Emulation.setDeviceMetricsOverride', { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
  const evalJs = async (expression, awaitPromise = true) => {
    const r = await rpc(ws, 'Runtime.evaluate', { expression, returnByValue: true, awaitPromise });
    if (r.exceptionDetails) throw new Error('页面抛异常：' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result?.value;
  };
  const shot = async (name, clip) => {
    const r = await rpc(ws, 'Page.captureScreenshot', clip ? { format: 'png', clip: { ...clip, scale: 1 } } : { format: 'png', captureBeyondViewport: false });
    const file = path.join(OUT, name + '.png');
    fs.writeFileSync(file, Buffer.from(r.data, 'base64'));
    return { file: path.basename(file), bytes: fs.statSync(file).size };
  };

  const report = { mode: 'cdp', budget: BUDGET, pages: [], routes: [], gate: { pass: true, pages: [] } };
  let gateFail = 0;

  console.log('== 首屏字节门禁（预算 %d B = %s KB）· 真浏览器 1280×900 ==', BUDGET, (BUDGET / 1024).toFixed(0));
  for (const p of PAGES) {
    responses = []; consoleMsgs = [];
    await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/${p.url}` });
    await sleep(1500);
    /* ★ 首屏口径：导航后 1.5s 内请求到的**全部资产**（图片/字体/CSS/JS），按产物文件实算字节 */
    const firstScreen = [...new Set(responses.filter((r) => ASSET_RE.test(r.url.split('?')[0]))
      .map((r) => r.url.replace(`http://127.0.0.1:${PORT}`, '')))];
    const fsBytes = firstScreen.reduce((s, u) => s + byteOf(u), 0);
    const over = firstScreen.map((u) => ({ u, b: byteOf(u) })).filter((x) => x.b > 0).sort((a, b) => b.b - a.b);
    await sleep(Math.max(0, p.wait - 1500));
    const home = await shot(`${PREFIX}-${p.name}`);
    const nonOk = responses.filter((r) => r.status >= 400 || r.status === 0).map((r) => r.status + ' ' + r.url.replace(`http://127.0.0.1:${PORT}`, ''));
    const pass = fsBytes <= BUDGET;
    if (!pass) { gateFail++; report.gate.pass = false; }
    report.gate.pages.push({ page: p.name, bytes: fsBytes, pass, files: firstScreen });
    console.log('  [' + (pass ? 'PASS' : 'FAIL') + '] ' + p.name.padEnd(8) +
      ' 首屏 ' + (fsBytes / 1024).toFixed(0).padStart(5) + ' KB / 预算 ' + (BUDGET / 1024).toFixed(0) +
      ' KB' + (pass ? '' : '  ← 超标'));
    if (!pass) {
      console.log('        超标文件（按字节降序，前 8）：');
      for (const x of over.slice(0, 8)) console.log('          ' + (x.b / 1024).toFixed(0).padStart(6) + ' KB  ' + x.u);
    }
    const rec = {
      page: p.name, url: p.url, shot: home, expectRoute: p.expect,
      firstScreenAssetBytes: fsBytes, firstScreenFiles: firstScreen, gatePass: pass,
      allAssetBytes: [...new Set(responses.map((r) => r.url))].reduce((s, u) => s + byteOf(u.replace(`http://127.0.0.1:${PORT}`, '')), 0),
      nonOk, console: [...consoleMsgs], check: productCheck(path.join(PUB, p.file)),
      routeRender: await evalJs("document.documentElement.getAttribute('data-xk-render')"),
      markerPresent: await evalJs(`!!document.querySelector(${JSON.stringify(p.marker)})`),
      shellRoots: await evalJs("document.querySelectorAll('#xk-app').length"),
      mainTextChars: await evalJs("(function(){var m=document.querySelector('main#content');return m&&m.innerText?m.innerText.replace(/\\s+/g,' ').trim().length:0;})()")
    };
    shellRoots[p.name] = rec.shellRoots;
    if (p.name === 'home') {
      /* autoplay 门控取证：**任何交互之前**读一次（本脚本此时确实没点过任何东西） */
      rec.voiceBeforeGesture = await evalJs('JSON.stringify(window.KurisuPlayer ? KurisuPlayer.voiceDiag() : null)');
      rec.voiceLabelText = await evalJs("(function(){var b=document.querySelector('[data-xk-kurisu-voice]');return b?b.textContent.replace(/\\s+/g,' ').trim():null;})()");
      rec.voiceButtonShot = await shot(`${PREFIX}-voice-button`, { x: 268, y: 806, width: 240, height: 56, scale: 3 });
      rec.sm = await evalJs('JSON.stringify(window.__xkSm ? {steps:window.__xkSm.seq.length,nodeCount:window.__xkSm.nodeCount,edgeCount:window.__xkSm.edgeCount,hostSteps:(window.__xkSm.hostTimeline||[]).length} : null)');
      rec.stageSmOn = await evalJs('JSON.stringify((function(p){return p?{mode:p.mode,smOn:p.smOn,staticOnly:p.staticOnly,clip:(p.current&&(p.current.clipName||p.current.clip))||p.currentClipName}:null;})(window.KurisuPlayer&&KurisuPlayer.stage()))');
    }
    report.pages.push(rec);
    console.log('        nonOk=' + nonOk.length + ' console=' + consoleMsgs.length +
      ' 正文=' + rec.check.textChars + ' 站外=' + rec.check.extRefs.length +
      ' 缺本地=' + rec.check.missingLocal.length + ' data-xk-render=' + rec.routeRender +
      ' marker=' + rec.markerPresent + ' mainText=' + rec.mainTextChars);
    if (nonOk.length) console.log('        非200:', nonOk.slice(0, 6));
    if (consoleMsgs.length) console.log('        控制台:', consoleMsgs.slice(0, 4));
  }

  /* hash 路由逐条切页：核对 app.js 的 data-xk-render 与正文长度 */
  await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/index.html` });
  await sleep(3500);
  console.log('\n== hash 路由（app.js SPA 换页）==');
  let routeBad = 0;
  for (const [name, hash, want] of [['monitor', '#/monitor/alerts', 'monitor'], ['notes', '#/notes', 'notes'],
    ['labs', '#/labs', 'range'], ['about', '#/about', 'about'], ['ai', '#/ai', 'ai'], ['home', '#/home', 'home']]) {
    await evalJs(`location.hash=${JSON.stringify(hash)}; "ok"`, false);
    await sleep(1500);
    const got = await evalJs("document.documentElement.getAttribute('data-xk-render')");
    const textLen = await evalJs("(function(){var m=document.querySelector('main#content');return m&&m.innerText?m.innerText.replace(/\\s+/g,' ').trim().length:0;})()");
    const players = await evalJs('(window.KurisuPlayer&&KurisuPlayer.instances)?KurisuPlayer.instances().length:-1');
    const ok = got === want && textLen >= 150;
    if (!ok) routeBad++;
    await shot(`${PREFIX}-route-${name}`);
    report.routes.push({ route: name, hash, expect: want, got, ok, mainTextChars: textLen, playerInstances: players });
    console.log('  [' + (ok ? 'PASS' : 'FAIL') + '] ' + name.padEnd(8) + ' ' + hash.padEnd(20) +
      ' data-xk-render=' + String(got).padEnd(8) + ' (期望 ' + want + ') 正文=' + textLen + ' 播放器实例=' + players);
  }
  /* 手势后：autoplay 解锁取证（synthetic click 不算手势 → 用 CDP Input 派发真事件） */
  await evalJs('location.hash="#/home"; "ok"', false);
  await sleep(1500);
  await rpc(ws, 'Input.dispatchMouseEvent', { type: 'mousePressed', x: 340, y: 830, button: 'left', clickCount: 1 });
  await rpc(ws, 'Input.dispatchMouseEvent', { type: 'mouseReleased', x: 340, y: 830, button: 'left', clickCount: 1 });
  await sleep(2500);
  const voiceAfter = await evalJs('JSON.stringify(window.KurisuPlayer ? KurisuPlayer.voiceDiag() : null)');
  report.voiceAfterGesture = voiceAfter ? JSON.parse(voiceAfter) : null;
  console.log('\n== autoplay 门控 ==');
  console.log('  手势前：', report.pages[0] && report.pages[0].voiceBeforeGesture);
  console.log('  语音按钮文案：', report.pages[0] && report.pages[0].voiceLabelText);
  console.log('  手势后：', voiceAfter);

  report.gate.pass = gateFail === 0 && routeBad === 0;
  const anyRoot = Object.keys(shellRoots).some((k) => shellRoots[k] > 0);
  const shellConsistent = (shellRules > 0) === anyRoot;
  report.shellCss = { rulesInBundle: shellRules, rootsPerPage: shellRoots, anyRoot, consistent: shellConsistent,
    note: '#xk-app 规则数与页面上 #xk-app 根元素"要么都有、要么都没有"；现在两者都为 0 = 外壳还没接线（不是坏）' };
  fs.writeFileSync(path.join(OUT, PREFIX + '-report.json'), JSON.stringify(report, null, 1), 'utf8');
  console.log('\n== 结论 ==');
  console.log('  首屏门禁：%s（%d 页超标 / %d 页）', gateFail ? 'FAIL' : 'PASS', gateFail, PAGES.length);
  console.log('  hash 路由：%s（%d 条不符）', routeBad ? 'FAIL' : 'PASS', routeBad);
  console.log('  新外壳样式一致性：%s（产物样式表里 #xk-app 规则 %d 条；页面上 #xk-app 根元素 %s）',
    shellConsistent ? 'PASS' : 'FAIL', shellRules, anyRoot ? JSON.stringify(shellRoots) : '0 个（未接线）');
  console.log('  报告 →', path.join(OUT, PREFIX + '-report.json'));
  process.exitCode = report.gate.pass ? 0 : 1;
  ws.close(); child.kill(); server.close();
  await sleep(400);
  try { fs.rmSync(userDataDir, { recursive: true, force: true }); } catch { }
}
main().catch((e) => { console.error('FAILED: ' + e.message); process.exitCode = 1; });
