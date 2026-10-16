/* 逐页产物验收 + **首屏字节硬门禁**（_dev/ 本地工具，零第三方依赖）
   node _dev/gate-firstscreen.mjs [--budget=1689600] [--static] [--prefix=pages] [--cold]
   node _dev/gate-firstscreen.mjs --cold --pages=ai      # 只量冷缓存 /ai/（专测，见下）

   ★★ 口径警告（2026-10-16 起，别拿错数字当结论）★★
   默认跑法是 **home→monitor→notes→ai→test 顺序、同一个浏览器实例 = warm 顺序跑**：
   前几页（尤其 home 的 avatar 以外的资源）会把共用资源带进浏览器缓存，后面的页因此偏小。
   实测后果：`/ai/` 的 warm 数字是 1639KB，但它自己的头像图（86KB）在 warm 跑里已被前四页
   带进缓存 ⇒ **冷缓存直接首访 /ai/ 的真实数字必须用 `--cold` 另测**（新 user-data-dir +
   清 localStorage + 每页一个全新浏览器实例 ⇒ 每个页面都是"首个页面"）。
   ⇒ warm 数字只用于"五页回归"，**冷缓存结论只认 `--cold` 的输出**。

   做什么：
     ① 起本地 http 服务（只读 public/，不碰产物、不用 hugo server，避免 livereload 污染断言）
     ② CDP 连 Edge headless 1280×900，逐页导航：收 Network 响应 + 控制台报错
     ③ **门禁**：导航后 1.5s 内请求到的**全部资产**（图片/字体/样式/脚本）字节 ≤ budget（**默认 1,689,600 B = 1650KB**，即代码里 BUDGET 的实际默认值；`--budget=` 可覆盖）
        任一页超标 → 打印超标文件清单 + **退出码 1**（这就是"真门禁"，不是报告）
     ④ 产物自查：正文长度 / 关键标记 / 站外资源引用 / 本地引用是否落到真实文件
     ⑤ **四页初始屏断言（2026-10-14 第四批口径 + 2026-10-15 T27 六页→四页）**：每页初始 `.on` 必须落在它自己那一屏
        （alerts→v-monitor、posts→v-notes、ai→v-ai），
        `main[data-xk-ssr]` 的取值要等于该页路由名，`#xk-views` 要在；
        主页（不是 .view 结构）改为断言 `.dock` 当前项 + `#charCanvas` 真的画出东西。
        ★ 主页导航本批已与内容页统一为左侧竖排 `.dock`（原顶部胶囊 `.navpill` 已删除），
          所以这里的取当前项选择器同步改成 `.dock a.on`（`#dock a.on` 同源）。
   ★ 旧口径的"hash 路由逐条切页（核对 app.js 的 data-xk-render）"那一段**已删除**：
     站主 2026-10-14 第四批口径明确"六个生产页 = demo 文件整份，不再套站点 SPA 外层、不挂 kurisu-player"，
     那段测的是已经不存在的机制。路由契约由 _dev/check-ssr-contract.py 继续负责。
     ⑥ 主页额外取证：autoplay 门控 + 状态机诊断 —— 同批口径后**不适用**（没有 kurisu-player 了），
        现在只报告页面上挂了几个播放器实例（预期 0）。
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
const BUDGET = Number(argOf('budget') || 1689600);
/* ↑ **本行是「整页真实加载口径」的唯一生效值：1,689,600 B = 1650KB**。
   ★2026-10-16 口径标注（接手窗口）：本注释此前写"→ 1600KB"、本文件用法行此前写 `--budget=1572864`，
   两处都与代码默认值**不符**，已按实际值更正；**常量本身一字未改**。
   历史：1536KB 是上一轮自己定的数（站主 2026-10-14 第四批裁定①改宽），主页实测 1569KB，
   构成全是 demo 自己的素材（opening.hi 1004 + 垫板原图 373 + desk/lab/ambient 179 + favicon 13）。
   ★ 与 `scripts/assert-build.sh` 第 ⑩ 条**不是同一个数**：那条是「资产自报口径」
     （只读 manifest.json 自报，判据 1,572,864 B = 1536KB）。任何文档写"预算 1536/1600/1650KB"
     都必须指明是哪一个口径。
   ★ 只改这个常量，**不动任何素材**。 */
const PREFIX = argOf('prefix') || 'pages';
const STATIC_ONLY = process.argv.includes('--static');
/* --cold：每页一个**全新浏览器实例**（新 user-data-dir）+ 清空 storage ⇒ 每个页面都是冷缓存首访。
   只用于冷缓存单独取证（尤其 /ai/）；五页回归仍用默认的 warm 顺序跑。 */
const COLD = process.argv.includes('--cold');
const COLD_ONLY = (argOf('pages') || '').split(',').map((s) => s.trim()).filter(Boolean);
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8', '.woff2': 'font/woff2', '.m4a': 'audio/mp4', '.wav': 'audio/wav', '.opus': 'audio/ogg' };
const ASSET_RE = /\.(webp|png|jpe?g|gif|svg|ico|css|js|woff2?|wav|opus|m4a)$/i;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

/* 页面清单：file = 产物里的文件，expect = app.js 对这条路由的 name（VIEW_TPL 的键）
   ★2026-10-16（窗口 Q）：新增第 5 页 /test/（测试模块页）—— 它的初始屏是实验区自己那一屏
     `<section class="view on lab" id="v-test">`，所以 expectView 直接写 'v-test'，复用现成断言。 */
const PAGES = [
  { name: 'home', file: 'index.html', url: 'index.html', wait: 14000, expect: 'home', view: null, marker: '.stage .charcanvas' },
  { name: 'monitor', file: 'alerts/index.html', url: 'alerts/', wait: 4000, expect: 'monitor', view: 'v-monitor', marker: '#termFeed' },
  { name: 'notes', file: 'posts/index.html', url: 'posts/', wait: 3000, expect: 'notes', view: 'v-notes', marker: '#v-notes .note' },
  { name: 'ai', file: 'ai/index.html', url: 'ai/', wait: 3000, expect: 'ai', view: 'v-ai', marker: '#askInput' },
  { name: 'test', file: 'test/index.html', url: 'test/', wait: 3000, expect: 'test', view: 'v-test', marker: '#v-test .lab-blk' }
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

/* --cold 用：起一个全新 Edge 实例（新 user-data-dir = 空磁盘缓存），返回其页面 target 的 ws 地址。
   独立端口/独立 profile，绝不与 warm 那个实例共用缓存。 */
const COLD_CDP = 9345;
let coldEdge = null, coldUserDir = null;
async function openEdge() {
  coldUserDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xk-gate-cold-'));
  coldEdge = spawn(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--mute-audio', `--remote-debugging-port=${COLD_CDP}`, `--user-data-dir=${coldUserDir}`, `--window-size=${VW},${VH}`, 'about:blank'], { stdio: 'ignore' });
  let t = null;
  for (let i = 0; i < 75 && !t; i++) {
    await sleep(400);
    try { const l = await (await fetch(`http://127.0.0.1:${COLD_CDP}/json/list`)).json(); t = l.find((x) => x.type === 'page' && x.webSocketDebuggerUrl); } catch { }
  }
  if (!t) throw new Error('冷缓存实例连不上 Edge 调试端口 ' + COLD_CDP);
  coldEdge.on('exit', () => {
    try { if (coldUserDir) fs.rmSync(coldUserDir, { recursive: true, force: true }); } catch { }
    coldUserDir = null; coldEdge = null;
  });
  return t.webSocketDebuggerUrl;
}
/* 关掉当前冷缓存实例（profile 目录在 exit 事件里删） */
async function closeEdge() {
  if (coldEdge) { try { coldEdge.kill(); } catch { } }
  for (let i = 0; i < 40 && coldEdge; i++) await sleep(100);
  coldEdge = null;
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
  /* 新外壳样式表（assets/css/xk-app.css）按页加载（head.html 的按页 <link>）——判据是"一致性"：
       **产物里（任何 .css）#xk-app 规则数 ⇔ 打开的页面里 #xk-app 根元素数**
     两种事故都能抓住：白下 26KB 惰性 CSS / 以为接好了其实没接。 */
  let shellRules = 0;
  const allCss = [];
  (function walkCss(dir) {
    for (const f of fs.readdirSync(dir)) {
      const p = path.join(dir, f);
      if (fs.statSync(p).isDirectory()) { walkCss(p); } else if (f.endsWith('.css')) { allCss.push(p); }
    }
  })(PUB);
  for (const f of allCss) { shellRules += (fs.readFileSync(f, 'utf8').match(/#xk-app/g) || []).length; }
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
  /* T5.2 已知无害控制台错误白名单：只收【实测出现过且确认无害】的条目，空启动。
   命中白名单的错误报 WARN-OK 不拦；未命中的一律算真错误。新增条目必须在提交信息里说明理由。 */
const CONSOLE_WHITELIST = [];
function consoleBlocking(msgs) {
  const bad = [];
  for (const m of msgs) {
    if (/^warning:/i.test(m)) continue;          /* warning 一律只报不拦（本门禁拦的是 error/EXCEPTION） */
    if (CONSOLE_WHITELIST.some((re) => re.test(m))) continue;
    bad.push(m);
  }
  return bad;
}

let gateFail = 0;

/* ======================= --cold：冷缓存专测（2026-10-16 ①） =======================
   为什么另跑：默认那个循环是 **warm 顺序**（前四页把共用资源带进缓存）⇒ 拿它的 /ai/ 数字
   当"冷缓存首访"结论是错的（施工单 §1 明确要求"必须专门造冷缓存"）。
   造冷：每个页面单独起一个 Edge 实例（新 user-data-dir = 空磁盘缓存）+ Network.clearBrowserCache
        + Storage.clearDataForOrigin（清 localStorage）+ 直接导航该页 ⇒ 该页就是"首个页面"。
   计量口径与 warm 完全一致：导航后 1.5s 内请求到的资产（产物文件实算字节）+ 控制台错误。
   用法：node _dev/gate-firstscreen.mjs --cold [--pages=ai] [--prefix=pages-cold] */
if (COLD) {
  const coldPages = COLD_ONLY.length ? PAGES.filter((p) => COLD_ONLY.includes(p.name)) : PAGES;
  const prefix = argOf('prefix') || 'pages-cold';
  const report = { mode: 'cdp-cold', note: '每页全新浏览器实例 + 清 storage ⇒ 冷缓存首访', budget: BUDGET, pages: [] };
  let coldFail = 0;
  console.log('== 冷缓存首屏字节门禁（预算 %d B = %s KB）· 每页独立全新实例 1280×900 ==', BUDGET, (BUDGET / 1024).toFixed(0));
  for (const p of coldPages) {
    const wsUrl = await openEdge();
    const ws = new WebSocket(wsUrl);
    await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
    const resp = [], msgs = [];
    ws.addEventListener('message', (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.method === 'Network.responseReceived') { const r = m.params.response; resp.push({ status: r.status, url: r.url, type: m.params.type }); }
      if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type)) msgs.push(m.params.type + ': ' + (m.params.args || []).map((a) => a.value || a.description || '').join(' '));
      if (m.method === 'Runtime.exceptionThrown') msgs.push('EXCEPTION: ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
    });
    await rpc(ws, 'Page.enable'); await rpc(ws, 'Runtime.enable'); await rpc(ws, 'Network.enable');
    await rpc(ws, 'Emulation.setDeviceMetricsOverride', { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
    await rpc(ws, 'Page.navigate', { url: 'about:blank' });
    await sleep(300);
    await rpc(ws, 'Network.clearBrowserCache');
    await rpc(ws, 'Storage.clearDataForOrigin', { origin: `http://127.0.0.1:${PORT}`, storageTypes: 'all' });
    console.log(`\n-- [${p.name}] 冷缓存首访 http://127.0.0.1:${PORT}/${p.url} --`);
    resp.length = 0;
    await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/${p.url}` });
    await sleep(1500);
    const files = [...new Set(resp.filter((r) => ASSET_RE.test(r.url.split('?')[0]))
      .map((r) => r.url.replace(`http://127.0.0.1:${PORT}`, '')))];
    const total = files.reduce((s, u) => s + byteOf(u), 0);
    const rows = files.map((u) => ({ u, b: byteOf(u) })).filter((x) => x.b > 0).sort((a, b) => b.b - a.b);
    const consoleBad = consoleBlocking(msgs);
    const pass = total <= BUDGET && consoleBad.length === 0;
    if (!pass) coldFail++;
    console.log('  [%s] %s 冷缓存首屏 %s KB / 预算 %s KB  (1.5s 窗口内资产 %d 个, %d 字节)',
      pass ? 'PASS' : 'FAIL', p.name.padEnd(8), (total / 1024).toFixed(0).padStart(5), (BUDGET / 1024).toFixed(0), files.length, total);
    for (const x of rows) console.log('        %s KB  %s', (x.b / 1024).toFixed(1).padStart(7), x.u);
    console.log('        console=%d（阻断性 %d）· nonOk=%d', msgs.length, consoleBad.length,
      resp.filter((r) => r.status >= 400 || r.status === 0).length);
    if (consoleBad.length) console.log('        阻断性控制台:', consoleBad.slice(0, 4));
    report.pages.push({ page: p.name, url: p.url, coldFirstScreenBytes: total, coldPass: pass,
      files: rows, fileCount: files.length, console: msgs, consoleBlocking: consoleBad });
    ws.close();
    await closeEdge();
  }
  fs.writeFileSync(path.join(OUT, prefix + '-report.json'), JSON.stringify(report, null, 1), 'utf8');
  console.log('\n== 冷缓存结论 ==');
  console.log('  %s（%d 页超标 / %d 页）· 报告 → %s', coldFail ? 'FAIL' : 'PASS', coldFail, coldPages.length,
    path.join(OUT, prefix + '-report.json'));
  process.exitCode = coldFail ? 1 : 0;
  process.exit(process.exitCode);   /* Edge 子进程/WS 句柄可能吊住事件循环 ⇒ 显式收尾 */
  return;
}

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
    const consoleBad = consoleBlocking(consoleMsgs);
    const pass = fsBytes <= BUDGET && consoleBad.length === 0;   /* T5.2：字节 + 控制台错误双闸 */
    if (!pass) { gateFail++; report.gate.pass = false; }
    report.gate.pages.push({ page: p.name, bytes: fsBytes, pass, files: firstScreen });
    console.log('  [' + (pass ? 'PASS' : 'FAIL') + '] ' + p.name.padEnd(8) +
      ' 首屏 ' + (fsBytes / 1024).toFixed(0).padStart(5) + ' KB / 预算 ' + (BUDGET / 1024).toFixed(0) +
      ' KB' + (pass ? '' : (fsBytes > BUDGET ? '  ← 超标' : '') + (consoleBad.length ? '  ← 控制台错误 ' + consoleBad.length + ' 条' : '')));
    if (!pass) {
      console.log('        超标文件（按字节降序，前 8）：');
      for (const x of over.slice(0, 8)) console.log('          ' + (x.b / 1024).toFixed(0).padStart(6) + ' KB  ' + x.u);
    }
    const rec = {
      page: p.name, url: p.url, shot: home, expectRoute: p.expect,
      firstScreenAssetBytes: fsBytes, firstScreenFiles: firstScreen, gatePass: pass,
      allAssetBytes: [...new Set(responses.map((r) => r.url))].reduce((s, u) => s + byteOf(u.replace(`http://127.0.0.1:${PORT}`, '')), 0),
      nonOk, console: [...consoleMsgs], consoleBlocking: consoleBad,
      smReasons: await evalJs('(window.__xkSM && window.__xkSM.reasons) ? window.__xkSM.reasons() : null'),
      check: productCheck(path.join(PUB, p.file)),
      ssrAttr: await evalJs("(function(){var m=document.querySelector('main[data-xk-ssr]');return m?m.getAttribute('data-xk-ssr'):null;})()"),
      viewOn: await evalJs("(function(){var v=document.querySelector('.view.on');return v?v.id:null;})()"),
      hasXkViews: await evalJs("!!document.getElementById('xk-views')"),
      markerPresent: await evalJs(`!!document.querySelector(${JSON.stringify(p.marker)})`),
      shellRoots: await evalJs("document.querySelectorAll('#xk-app').length"),
      mainTextChars: await evalJs("(function(){var m=document.querySelector('main#content');return m&&m.innerText?m.innerText.replace(/\\s+/g,' ').trim().length:0;})()")
    };
    shellRoots[p.name] = rec.shellRoots;
    if (p.name === 'home') {
      /* 同批新口径：主页不挂 kurisu-player（页面 = demo-主页.html 自己的那套逐帧代码），
         所以这里只报告"挂了几套播放器"，并另外取证 demo 自己的画布真的画出了东西。 */
      rec.playerInstances = await evalJs('(window.KurisuPlayer&&KurisuPlayer.instances)?KurisuPlayer.instances().length:-1');
      rec.demoCanvasOpaque = await evalJs("(function(){var c=document.getElementById('charCanvas');if(!c)return 'no-canvas';var x=c.getContext('2d');if(!c.width)return 'zero-size';var d=x.getImageData(0,0,c.width,c.height).data,on=0;for(var i=3;i<d.length;i+=4){if(d[i]>8)on++;}return on;})()");
      rec.demoClip = await evalJs("(typeof cur!=='undefined'?cur:null)");
      rec.dockOn = await evalJs("(function(){var a=document.querySelector('.dock a.on');return a?a.textContent.trim():null;})()");
    }
    report.pages.push(rec);
    console.log('        nonOk=' + nonOk.length + ' console=' + consoleMsgs.length +
      ' 正文=' + rec.check.textChars + ' 站外=' + rec.check.extRefs.length +
      ' 缺本地=' + rec.check.missingLocal.length + ' data-xk-ssr=' + rec.ssrAttr +
      ' .view.on=' + rec.viewOn + ' marker=' + rec.markerPresent + ' mainText=' + rec.mainTextChars);
    if (nonOk.length) console.log('        非200:', nonOk.slice(0, 6));
    if (consoleMsgs.length) console.log('        控制台:', consoleMsgs.slice(0, 4));
    if (consoleBad.length) console.log('        阻断性控制台错误:', consoleBad.slice(0, 4));
  }

  /* ★ 第四批新口径 + T27（六页→四页）：四页初始屏断言（旧 hash 路由段已删除，理由见文件头注释⑤） */
  console.log('\n== 四页初始屏（新口径：页面 = demo 对应那一屏，不再有 SPA hash 路由）==');
  let routeBad = 0;
  for (const p of PAGES) {
    await rpc(ws, 'Page.navigate', { url: `http://127.0.0.1:${PORT}/${p.url}` });
    await sleep(p.name === 'home' ? 9000 : 2500);   /* ★T5.6：boot→hi 后开场序列约 5.5s 落定（通电→boot循环→hi接力→推拉），检查点 6s→9s；判据仍是 >10000 不透明像素（抓黑屏不改）*/
    const ssr = await evalJs("(function(){var m=document.querySelector('main[data-xk-ssr]');return m?m.getAttribute('data-xk-ssr'):null;})()");
    const views = await evalJs("!!document.getElementById('xk-views')");
    const on = await evalJs("(function(){var v=document.querySelector('.view.on');return v?v.id:null;})()");
    const textLen = await evalJs("(function(){var v=document.querySelector('.view.on');var m=document.querySelector('main#content');var e=v||m;return e&&e.innerText?e.innerText.replace(/\\s+/g,' ').trim().length:0;})()");
    let extra = null, ok;
    if (p.view) {
      ok = ssr === p.expect && views && on === p.view && textLen >= 150;
      /* ★T27：原来的 about 特例（demo 的 v-about 是空屏）随 /about/ 页一起删除 */
    } else {
      const opaque = await evalJs("(function(){var c=document.getElementById('charCanvas');if(!c)return -1;var x=c.getContext('2d');if(!c.width)return -1;var d=x.getImageData(0,0,c.width,c.height).data,on=0;for(var i=3;i<d.length;i+=4){if(d[i]>8)on++;}return on;})()");
      const nav = await evalJs("(function(){var a=document.querySelector('.dock a.on');return a?a.textContent.trim():null;})()");
      ok = ssr === p.expect && views && opaque > 10000 && nav === '主页';
      extra = '画布不透明像素=' + opaque + ' · dock=' + nav;
    }
    if (!ok) routeBad++;
    await shot(`${PREFIX}-view-${p.name}`);
    report.routes.push({ page: p.name, expectSsr: p.expect, ssr, xkViews: views, viewOn: on, expectView: p.view, mainTextChars: textLen, ok, extra });
    console.log('  [' + (ok ? 'PASS' : 'FAIL') + '] ' + p.name.padEnd(8) + ' data-xk-ssr=' + String(ssr).padEnd(8) +
      ' .view.on=' + String(on).padEnd(10) + ' (期望 ' + String(p.view).padEnd(10) + ') #xk-views=' + views +
      ' 正文=' + textLen + (extra ? '  ' + extra : ''));
  }

  report.gate.pass = gateFail === 0 && routeBad === 0;
  const anyRoot = Object.keys(shellRoots).some((k) => shellRoots[k] > 0);
  const shellConsistent = (shellRules > 0) === anyRoot;
  report.shellCss = { rulesInBundle: shellRules, rootsPerPage: shellRoots, anyRoot, consistent: shellConsistent,
    note: '#xk-app 规则数与页面上 #xk-app 根元素"要么都有、要么都没有"；现在两者都为 0 = 外壳还没接线（不是坏）' };
  fs.writeFileSync(path.join(OUT, PREFIX + '-report.json'), JSON.stringify(report, null, 1), 'utf8');
  console.log('\n== 结论 ==');
  console.log('  首屏门禁：%s（%d 页超标 / %d 页）', gateFail ? 'FAIL' : 'PASS', gateFail, PAGES.length);
  console.log('  四页初始屏（新口径）：%s（%d 页不符）', routeBad ? 'FAIL' : 'PASS', routeBad);
  console.log('  路由契约（data-xk-ssr / #xk-views / 站外资源）：见 _dev/check-ssr-contract.py');
  console.log('  新外壳样式一致性：%s（产物样式表里 #xk-app 规则 %d 条；页面上 #xk-app 根元素 %s）',
    shellConsistent ? 'PASS' : 'FAIL', shellRules, anyRoot ? JSON.stringify(shellRoots) : '0 个（本批口径下不再挂站点外壳）');
  console.log('  报告 →', path.join(OUT, PREFIX + '-report.json'));
  process.exitCode = report.gate.pass ? 0 : 1;
  ws.close(); child.kill(); server.close();
  await sleep(400);
  try { fs.rmSync(userDataDir, { recursive: true, force: true }); } catch { }
}
main().catch((e) => { console.error('FAILED: ' + e.message); process.exitCode = 1; });
