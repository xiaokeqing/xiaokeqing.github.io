

/* ============ 雪碧条播放器 ============ */
const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ============ OPS-ROOM 作战室 ============ */
const opsTabs = document.querySelectorAll('#opsTabs button');
const opsPanes = document.querySelectorAll('.ops-tab');
let opsTab = 'live';
opsTabs.forEach(b=>b.onclick = ()=>{
  opsTab = b.dataset.tab;
  opsTabs.forEach(x=>x.classList.toggle('on', x===b));
  opsPanes.forEach(p=>p.classList.toggle('on', p.dataset.pane===opsTab));
  if(opsTab==='graph'){ startGraph(); runCounters(); }   /* ★第十二批：这四个数字渲染在 graph 这一屏，
      原来只在点 stats 时滚动 → 它们永远停在 0（demo 的错位）。 */
  if(opsTab==='stats') drawSpark();
  if(opsTab==='live') drawSpark();
});

/* 实时攻击流 —— ★第十二批重写（站主：①不许假数字 ②修"行叠行"）
   数据：/api/public/alerts 的真实聚合告警，由 api-bind 写进 window.XK_FEED 后调 __xkRenderFeed。
   行数：按容器高度实算（原来是"最多 12 行 + 光标一行"= 13 个行盒塞进 12.89 行的容器，
        最后一行被 overflow 切掉 2.4px —— 实测 scrollHeight 316 > clientHeight 314）。
        现在行数 = floor((容器高 - 上下 padding) / 行高) - 1（减 1 给光标），行与行永不重叠、末行不被切。 */
const termFeed = document.getElementById('termFeed');
const xkEsc = s=>String(s==null?'':s).replace(/[&<>"']/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const tcursor = document.createElement('div');
tcursor.innerHTML = '<span class="tcursor"></span>';
let feedSeen = {};
function feedCap(){
  const lh = parseFloat(getComputedStyle(termFeed).lineHeight) || 22.8;
  return Math.max(2, Math.floor((termFeed.clientHeight - 20) / lh) - 1);
}
function feedRow(it){
  const el = document.createElement('div');
  el.className = 'tl lv-' + (it.cls || 'dns');   /* ★R2：行左 2px 级别色条（颜色映射在 CSS 里，复用既有类型色的变量，不新增色值） */
  el.innerHTML = `<span class="ts">${xkEsc(it.ts)}</span> <span class="tg ${it.cls}">${xkEsc(it.tag)}</span> ${xkEsc(it.text)}`;
  if (it.d) { el.__d = it.d; el.style.cursor = 'pointer'; el.title = '点一下看这条聚合告警的明细'; }
  termFeed.appendChild(el);
}

/* ★A3（2026-10-17）：点行看明细。只用 /alerts 已经返回的聚合字段，不额外发请求、不补字段。 */
let fdBox = null;
function feedDetailBox(){
  if (fdBox) return fdBox;
  const host = termFeed.closest('.mod') || termFeed.parentElement;
  if (host && getComputedStyle(host).position === 'static') host.style.position = 'relative';
  fdBox = document.createElement('div');
  fdBox.id = 'feedDetail';
  fdBox.hidden = true;
  fdBox.style.cssText = 'position:absolute;left:10px;right:12px;bottom:12px;z-index:40;max-height:48%;overflow:auto;'
    + 'background:rgba(6,10,14,.97);border:1px solid rgba(120,200,255,.38);border-radius:10px;'
    + 'padding:10px 12px;font:12px/1.7 ui-monospace,Consolas,monospace;color:#cfe9f5;'
    + 'box-shadow:0 14px 34px rgba(0,0,0,.55)';
  (host || termFeed).appendChild(fdBox);
  fdBox.addEventListener('click', function (e) {
    if (e.target && e.target.dataset && e.target.dataset.close === '1') fdBox.hidden = true;
    e.stopPropagation();
  });
  return fdBox;
}
function feedDetailShow(d){
  const box = feedDetailBox();
  const line = (k, v) => v ? `<div><span style="color:rgba(255,255,255,.42)">${k}</span> ${xkEsc(v)}</div>` : '';
  box.innerHTML = '<div style="display:flex;gap:8px;align-items:baseline;margin-bottom:6px">'
    + '<b style="color:#9fd8e6">聚合告警明细</b>'
    + '<span style="color:rgba(255,255,255,.4);font-size:11px">/api/public/alerts · 只读</span>'
    + '<span data-close="1" style="margin-left:auto;cursor:pointer;color:rgba(255,255,255,.5)">关闭 ✕</span></div>'
    + line('窗口', d.win) + line('命中', '×' + d.n + ' 次' + (d.hit && d.hit !== d.n ? '（hitCount ' + d.hit + '）' : ''))
    + line('来源', d.ip + (d.geo ? ' · ' + d.geo : ''))
    + line('严重度', d.sev) + line('类型', d.typ + (d.src2 ? ' · ' + d.src2 : ''))
    + line('规则', d.rule) + line('状态', d.st) + line('聚合号', d.agg);
  box.hidden = false;
}
termFeed.addEventListener('click', function (e) {
  const row = e.target && e.target.closest ? e.target.closest('.tl') : null;
  if (!row || !row.__d) return;
  feedDetailShow(row.__d);
});
function feedTrim(){
  const cap = feedCap();
  while(termFeed.querySelectorAll('.tl').length > cap) termFeed.removeChild(termFeed.querySelector('.tl'));
  termFeed.appendChild(tcursor);
}
function renderFeed(){
  const items = window.XK_FEED;
  if(!items){
    termFeed.innerHTML = '';
    /* ★2026-10-16（站主截图里那句原文）：**不再断言"不可达或被拦"** —— 那是未经证实的因果。
       前端现在已经能区分"被限流 / 失败但有旧值 / 真的读不到"，所以兜底文案按优先级取：
         ① `window.XK_FEED_NOTE`（字符串）⇒ 站点线在限流/降级场景写入的机读结论，**原样使用**；
         ② 否则用**中性且不诬告**的措辞：只说"本次未取到"，不猜原因。
       口径不变：不补样例值、不编造（零造假红线）。 */
    const note = (typeof window.XK_FEED_NOTE === 'string' && window.XK_FEED_NOTE)
      ? window.XK_FEED_NOTE
      : '/api/public/alerts 本次未取到 —— 不补样例值';
    feedRow({ts:'--:--:--', cls:'dns', tag:'[读不到]', text: note});
    feedTrim();
    return;
  }
  if(!items.length){
    termFeed.innerHTML = '';
    feedRow({ts:'--:--:--', cls:'dns', tag:'[空]', text:'/api/public/alerts 返回的聚合窗口里没有告警（不是取不到，是真的没有）'});
    feedTrim();
    return;
  }
  items.filter(it=>!feedSeen[it.key]).forEach(it=>{ feedSeen[it.key] = 1; feedRow(it); });
  feedTrim();
}
window.__xkRenderFeed = renderFeed;
addEventListener('resize', feedTrim);

/* ★A1/A2 英雄数字 + 今日战报：只读两个端点，取不到就写「未取到」，不补样例值 */
(function(){
  const el = id => document.getElementById(id);
  const hero = el('opsHero');
  const API = ((document.querySelector('meta[name="wb-api"]') || {}).content || '').replace(/\/+$/, '');
  if(!hero) return;
  const put = (id, v) => { const n = el(id); if(n) n.textContent = v; };
  const num = v => (typeof v === 'number' && isFinite(v)) ? v.toLocaleString('zh-CN') : '未取到';
  async function load(){
    /* ★速度：两个端点并行取，且一律走可被 CF 缓存的 `.js` 别名（不带 .js 的路径必然回源，实测 0.9~2.6s） */
    const grab = async p => { try { return (await (await fetch(API + '/api/public/' + p + '.js')).json()).data; } catch(_) { return null; } };
    const got = await Promise.all([grab('audit'), grab('honeypot')]);
    const audit = got[0], honey = got[1];
    const s = (audit && audit.summary) || {};
    put('ohBlocked', num(s.blockedByGuard));
    put('ohIps', num(s.blockTotal));
    /* ★C6（2026-10-18 外部巡检第 6 条）：`total` 是**统计上限哨兵**（恒 10000），不是真值。
       真值在同一响应的 `connections`（其次 `logins`）；只有拿到哨兵时写「≥10,000（上限）」，绝不把 10000 当累计。 */
    const hpN = honey && ((typeof honey.connections === 'number' && honey.connections > 0) ? honey.connections
      : ((typeof honey.logins === 'number' && honey.logins > 0) ? honey.logins : null));
    put('ohHoney', hpN ? num(hpN) : (honey && honey.total >= 10000 ? '≥10,000（上限）' : num(honey && honey.total)));
    const top = (honey && honey.topSources && honey.topSources[0]) || null;
    const at = (audit && audit.generatedAt) || (honey && honey.generatedAt) || '';
    const parts = [];
    if(top && top.key) parts.push('今天最凶的来源 ' + top.key + '，' + num(top.count) + ' 次登录尝试');
    if(s.blockActive != null) parts.push('当前生效封禁 ' + num(s.blockActive) + ' 个');
    if(at) parts.push('数据时间 ' + at);
    if(!parts.length) parts.push('两个端点本次都未取到 —— 不补样例值');
    put('ohLine', parts.join(' · '));
  }
  load();
  setInterval(load, 60000);
})();


/* 24 小时攻击时序 —— ★第十二批重写：数据改成 /api/public/alerts 的 stats24h.trend
   （25 个小时桶真实计数，由 api-bind 写进 window.XK24H）；取不到就清空画布 + 表头写"读不到"，
   不再用 Math.sin + 取模画一条看着像波形的假曲线（原实现就是这么画的）。
   ★R2（2026-10-16）：补横轴刻度（0/6/12/18/24h）+ 峰值点标记 + 当前小时（末桶）高亮点。
   色值全部是本样式表里已有值（acc/警示色/mut 的 warm 口径），不新增配色。 */
let sparkDone = false;
function drawSpark(){
  const c = document.getElementById('spark24'); if(!c) return;
  const h = 56, dpr = Math.min(devicePixelRatio||1, 2), w = c.clientWidth;
  if(!w) return;
  c.width = w*dpr; c.height = h*dpr;
  const x = c.getContext('2d'); x.setTransform(dpr,0,0,dpr,0,0); x.clearRect(0,0,w,h);
  const bins = window.XK24H || null;
  const mod = c.closest('.mod');
  const tag = mod ? mod.querySelector('.mod-hd .tag') : null;
  if(!bins || bins.length < 2){
    if(tag) tag.textContent = '读不到（/alerts · stats24h）';
    return;
  }
  if(tag) tag.textContent = '/alerts · stats24h（' + bins.length + ' 个小时桶）';
  const vals = bins.map(b=>Number(b.count)||0);
  const max = Math.max.apply(null, vals) || 1;
  const xOf = i => i/(vals.length-1)*w;
  const yOf = v => (h-14) - (h-24) * (v/max);          /* ★R2：底部留 10px 给刻度字，顶部留 8px 给峰值标记 */
  /* ★R2：刻度层（ baseline + 0/6/12/18/24h 刻度字，8px mono ） */
  const axes = ()=>{
    x.strokeStyle = 'rgba(210,203,189,.28)'; x.lineWidth = 1;
    x.beginPath(); x.moveTo(0,h-10.5); x.lineTo(w,h-10.5); x.stroke();
    x.fillStyle = 'rgba(210,203,189,.75)'; x.font = '8px ui-monospace,Menlo,Consolas,monospace';
    x.textAlign = 'center';
    const ticks = [0,6,12,18,24];
    ticks.forEach(t=>{
      const i = Math.round(t/24*(vals.length-1));
      const px = Math.min(Math.max(xOf(i), 8), w-10);
      x.fillText(t+'h', px, h-1);
      x.fillRect(xOf(i), h-13, 1, 3);
    });
  };
  const area = ()=>{
    x.beginPath(); x.moveTo(0,h-10);
    vals.forEach((v,i)=>x.lineTo(xOf(i), yOf(v)));
    x.lineTo(w,h-10); x.closePath();
    x.fillStyle = 'rgba(127,212,216,.10)'; x.fill();
  };
  const line = upto=>{
    x.beginPath();
    const n = Math.max(2, Math.ceil(vals.length*upto));
    for(let i=0;i<n;i++){ const px = xOf(i); i===0 ? x.moveTo(px,yOf(vals[i])) : x.lineTo(px,yOf(vals[i])); }
    x.strokeStyle = '#7FD4D8'; x.lineWidth = 1.6; x.stroke();
  };
  /* ★R2：峰值点（warn 色）+ 当前小时（末桶，acc 色描边点）；upto 没到就不画，跟着动画一起出现 */
  const marks = upto=>{
    const n = Math.max(2, Math.ceil(vals.length*upto));
    const pi = vals.indexOf(max);
    if(pi >= 0 && pi < n){                              /* 全零窗口 max 兜底成 1 ⇒ indexOf=-1，此时不画峰值点 */
      x.beginPath(); x.arc(xOf(pi), yOf(vals[pi]), 2.6, 0, 6.284);
      x.fillStyle = '#E8B45A'; x.fill();
    }
    const li = vals.length - 1;
    if(li < n){
      x.beginPath(); x.arc(xOf(li), yOf(vals[li]), 2.6, 0, 6.284);
      x.fillStyle = '#12100D'; x.fill();
      x.strokeStyle = '#7FD4D8'; x.lineWidth = 1.6; x.stroke();
    }
  };
  axes();
  if(RM || sparkDone){ area(); line(1); marks(1); return; }
  sparkDone = true;
  /* ★R2 收敛（2026-10-16 主窗口裁决）：去掉 1100ms 渐显 —— 直接画完成态。
     理由：渐显让 24h 图晚 1.1 秒才成型，属"只是更花"；站主核心诉求是"数据出得来、别慢"。
     画法与非动画分支（RM / 已画过）逐字一致：area(); line(1); marks(1); 行为零差异。 */
  area(); line(1); marks(1);
}
window.__xkSpark = drawSpark;
drawSpark();


/* 攻击图谱：攻击者 → 传感器，数据包流动动画 */
/* ★第十二批：攻击者与传感器不再是写死的样例 ——
   由 api-bind 从 /api/public/alerts（真实来源 IP）与 /api/public/honeypot（真实 SSH 客户端指纹）
   写进 window.XK_ATTACKERS / window.XK_SENSORS；取不到就只画一行「读不到」，不画假的攻击路径。 */
const SENSORS = [];
const ATTACKERS = [];
let graphStarted = false;
function startGraph(){
  const c = document.getElementById('atkGraph'); if(!c || graphStarted) return;
  graphStarted = true;
  const dpr = Math.min(devicePixelRatio||1, 2);
  const x = c.getContext('2d');
  let hits = null;
  let W = 0, H = 340;
  const resize = ()=>{ W = c.clientWidth; c.width = W*dpr; c.height = H*dpr; x.setTransform(dpr,0,0,dpr,0,0); };
  resize(); addEventListener('resize', resize);
  const A_NAMES = window.XK_ATTACKERS || [], S_NAMES = window.XK_SENSORS || [];
  if(!A_NAMES.length || !S_NAMES.length){   /* 读不到：把原因画在同一块画布上，不画假的路径 */
    graphStarted = false;   /* 不锁死：数据到了以后再点这一栏还能画 */
    const note = ()=>{ const w2 = c.clientWidth; if(!w2) return; x.clearRect(0,0,w2,H);
      x.fillStyle = 'rgba(210,203,189,.75)'; x.font = '12px ui-monospace,Consolas,monospace'; x.textAlign = 'center';
      x.fillText(window.XK_GRAPH_NOTE || '读不到：攻击路径的数据源没取到 —— 不画假的路径', w2/2, H/2); };
    note(); addEventListener('resize', note); return;
  }
  hits = S_NAMES.map(()=>0);
  const A = A_NAMES.map((n,i)=>({n, fx:.09, fy:(i+1)/(A_NAMES.length+1)}));
  const S = S_NAMES.map((s,i)=>({n:s[0], d:s[1], fx:.82, fy:(i+1)/(S_NAMES.length+1)}));
  let pk = [], last = 0;
  function frame(t){
    requestAnimationFrame(frame);
    if(opsTab!=='graph' || !document.getElementById('v-monitor').classList.contains('on') || !W) return;
    x.clearRect(0,0,W,H);
    x.font = '11px ui-monospace,Consolas,monospace';
    const pos = n=>({x:n.fx*W, y:26+n.fy*(H-60)});
    S.forEach(s=>{ const p = pos(s); x.textAlign='right'; x.fillStyle='rgba(210,203,189,.35)'; x.fillText(s.d, p.x-16, p.y+3); });
    if(!RM && t-last > 420 && pk.length < 22){ last = t; pk.push({a:(Math.random()*A.length)|0, s:(Math.random()*S.length)|0, k:0, sp:.006+Math.random()*.009}); }
    x.lineWidth = 1;
    pk.forEach(p=>{
      const pa = pos(A[p.a]), ps = pos(S[p.s]);
      x.strokeStyle = 'rgba(210,203,189,.05)';
      x.beginPath(); x.moveTo(pa.x,pa.y); x.lineTo(ps.x,ps.y); x.stroke();
    });
    pk = pk.filter(p=>{
      p.k += p.sp;
      const pa = pos(A[p.a]), ps = pos(S[p.s]);
      const px = pa.x+(ps.x-pa.x)*p.k, py = pa.y+(ps.y-pa.y)*p.k;
      for(let j=0;j<5;j++){
        const q = p.k - j*.02;
        if(q<0) break;
        x.fillStyle = `rgba(232,180,90,${.85-j*.16})`;
        x.beginPath(); x.arc(pa.x+(ps.x-pa.x)*q, pa.y+(ps.y-pa.y)*q, 2.6-j*.35, 0, 7); x.fill();
      }
      if(p.k>=1){ hits[p.s]++; return false; }
      return true;
    });
    A.forEach(a=>{
      const p = pos(a);
      x.fillStyle = '#E8837B'; x.beginPath(); x.arc(p.x,p.y,5,0,7); x.fill();
      x.fillStyle = 'rgba(210,203,189,.85)'; x.textAlign='left'; x.fillText(a.n, p.x+12, p.y+3);
    });
    S.forEach((s,i)=>{
      const p = pos(s);
      x.fillStyle = '#7FD4D8'; x.beginPath(); x.arc(p.x,p.y,6,0,7); x.fill();
      x.fillStyle = 'rgba(127,212,216,.25)'; x.beginPath(); x.arc(p.x,p.y,10+Math.sin(t/300+i)*2,0,7); x.fill();
      x.fillStyle = '#7FD4D8'; x.textAlign='left'; x.fillText(s.n, p.x+14, p.y-2);
      x.fillStyle = 'rgba(210,203,189,.8)'; x.fillText(String(hits[i]), p.x+14, p.y+11);
    });
  }
  requestAnimationFrame(frame);
}

/* 告警类型矩阵 —— ★第十二批重写（原来是写死的 TACTIC_HITS 样例值）。
   服务端没有 ATT&CK 战术字段，所以这里一格 = 服务端真实给的一个类型标签 + /alerts 的
   stats.byType 真实计数；映射关系由服务端给，前端不编。取不到就写"读不到"。
   ★R2（2026-10-16）：每格补 hover/聚焦摘要（占比 + 最近一条真实告警一句话，数据来自
   已在手的 XK_FEED，不发新请求）；格子可聚焦（tabindex）—— 摘要条 CSS 在 shell-style 的 R2 段。 */
const attkGrid = document.getElementById('attkGrid');
/* ATT&CK 技术编号释义：一处常量表，改这里（生成器 _dev/gen-demo-pages.py），不要散落到别处 */
const TECH_ZH = {
  'T1021': '远程服务登录 · 用 RDP/SSH/共享这类合法远程通道登进机器',
  'T1046': '网络服务扫描 · 扫端口和服务，先摸清下一步能打哪个口子',
  'T1071': '应用层协议通信 · 把回连与控制流量藏在 HTTP/DNS 这类正常协议里',
  'T1110': '暴力破解 · 反复试口令/撞库，直到撞出能用的密码',
  'T1190': '利用对外应用的公开漏洞 · 拿现成漏洞打 Web/中间件，不需要先拿到口令',
  'T1505': '服务端软件植入(WebShell) · 在被攻陷的服务器上留一个能随时回来的后门程序',
};
/* ★巡检：技术编号的 hover 说明 = "编号 技术名 · 一句人话"。编号与 label 都是**服务端**给的
   （api-bind 里的 it.attck），这里只补解释；表里没有的编号只用后端 name —— 不猜、不编。 */
function techTip(id, name){
  const t = TECH_ZH[id];
  if(t) return id + ' ' + t;
  return (String(id || '') + ' ' + String(name || '')).replace(/ +$/, '');
}
function attkTip(label){
  /* 从实时攻击流里找这个类型的最近一条（XK_FEED 新的在前），找不到就只给占比 */
  const items = window.XK_FEED || [];
  const plain = String(label || '').replace(/ *告警$/, '');
  const hit = items.find(it => String(it.tag || '').indexOf(plain) >= 0);
  return hit ? hit.ts + ' ' + hit.text : '';
}
function renderTypes(){
  if(!attkGrid) return;
  const rows = window.XK_TYPES;
  attkGrid.innerHTML = '';
  if(!rows || !rows.length){
    attkGrid.innerHTML = '<div class="cell"><b>读不到</b><span class="taid">/api/public/alerts</span><div class="num">—</div></div>';
    return;
  }
  const total = rows.reduce((s,r)=>s + (Number(r.count)||0), 0) || 1;
  const max = Math.max.apply(null, rows.map(r=>Number(r.count)||0)) || 1;
  /* ★R2 收敛（2026-10-16 站主批）：不再给每格挂浮层，改为把摘要写进图例那一行（#attkLgMsg）。
     数据来源不变（window.XK_TYPES + window.XK_FEED），仍然零新增请求；浮层撤掉后遮挡与窄屏溢出一起消失。 */
  const lgMsg = document.getElementById('attkLgMsg');
  const LG_DEFAULT = lgMsg ? lgMsg.textContent : '';
  function showTip(cell, share, hit, last){
    if(!lgMsg) return;
    const b = cell.querySelector('b');
    lgMsg.textContent = (b ? b.textContent : '') + ' · 占本窗口 ' + share + '%（' +
      hit.toLocaleString('en-US') + ' 次）' + (last ? ' · 最近：' + last : '');
  }
  function clearTip(){ if(lgMsg){ lgMsg.textContent = LG_DEFAULT; } }
  rows.forEach((r,i)=>{
    const hit = Number(r.count) || 0;
    const cell = document.createElement('div');
    cell.className = 'cell' + (hit/max >= .6 ? ' fire' : hit>0 ? ' hot' : '');
    cell.tabIndex = 0;                                  /* 键盘聚焦也能看摘要（写进图例行） */
    const share = Math.round(hit / total * 100);
    const last = attkTip(r.label || r.key);
    cell.innerHTML = `<b>${xkEsc(r.label || r.key || '—')}</b><span class="taid">${xkEsc(r.key || '')}</span>` +
      `<div class="num">${hit.toLocaleString('en-US')}</div>`;
    const fire = function(){ showTip(cell, share, hit, last); };
    cell.addEventListener('mouseenter', fire);
    cell.addEventListener('focus', fire);
    cell.addEventListener('mouseleave', clearTip);
    cell.addEventListener('blur', clearTip);
    attkGrid.appendChild(cell);
  });
  renderTech();
}
/* ★ATT&CK 行：把最近窗口里已经映射出技术编号的告警按 T1xxx 聚合。
   口径（写进图例，避免被读成"全站统计"）：窗口 = /api/public/alerts 的最近 200 条聚合；
   数字是该聚合条目自带的 count 之和，未归类的规则名**不塞 OTHER**，只如实说"未归类"。 */
function renderTech(){
  if(!attkGrid) return;
  let host = document.getElementById('attkTech');
  if(!host){
    host = document.createElement('div');
    host.id = 'attkTech'; host.className = 'attk-tech';
    attkGrid.parentNode.insertBefore(host, attkGrid.nextSibling);
  }
  const feed = window.XK_FEED || [];
  const agg = {}; const order = [];
  feed.forEach(function(it){
    const t = it && it.attck;
    if(!t || !t.id) return;
    if(!agg[t.id]){ agg[t.id] = { id:t.id, name:t.name, label:t.label, n:0 }; order.push(t.id); }
    agg[t.id].n += (it.d && Number(it.d.n)) || 1;
  });
  if(!order.length){
    host.innerHTML = '<span class="attk-note">ATT&CK：最近窗口里没有可映射的规则名（未归类，不猜编号）</span>';
    return;
  }
  order.sort(function(a,b){ return agg[b].n - agg[a].n; });
  let html = '<span class="attk-note">ATT&CK 技术编号 · 最近窗口聚合命中：</span>';
  order.forEach(function(id){
    const t = agg[id];
    html += '<span class="tech" title="' + xkEsc(techTip(t.id, t.name)) + '">' +
      '<b>' + xkEsc(t.id) + '</b>' + xkEsc(t.label || t.name || '') +
      '<i>×' + t.n.toLocaleString('en-US') + '</i></span>';
  });
  host.innerHTML = html;
}
window.__xkRenderTech = renderTech;
window.__xkRenderTypes = renderTypes;

/* 数据统计：数字滚动 */
let counted = false;
function runCounters(){
  counted = true;
  /* ★第十二批：data-count 为空 = 该数字这次没取到 → 写"读不到"，**不写 0 冒充**；
     真值由 api-bind 从真实端点写进 data-count 与文本。 */
  document.querySelectorAll('[data-count]').forEach(el=>{
    el.classList && el.classList.remove('sk');          /* ★R2：写实值的同时摘掉骨架条 */
    const raw = el.dataset.count, T = Number(raw);
    if(raw === '' || raw === undefined || !isFinite(T)){ el.textContent = '读不到'; return; }
    /* ★R2 收敛（2026-10-16 站主批）：去掉 count-up 数字滚动 —— 真值直接写。
       判据：更清楚=好，只是更花=删；数字从 0 滚上去不增加任何信息量。
       注意：RM（减少动效）之外的普通路径与 RM 现在同一条；"读不到"分支在上面原样保留。 */
    el.textContent = T.toLocaleString('en-US');
  });
}
const CELL = 132, COLS = 8;
const EMOS = {   /* ★2026-10-15 接手批：5 套 → 8 套（素材本来就有 8 套，见 static/kurisu/avatar/）；
                    sad / blush 由 static 单帧换成会动的 idle / speaking 图 */
  normal:         {idle:'/kurisu/avatar/normal.idle.webp',         speaking:'/kurisu/avatar/normal.speaking.webp'},
  happy:          {idle:'/kurisu/avatar/happy.idle.webp',          speaking:'/kurisu/avatar/happy.speaking.webp'},
  sided_thinking: {idle:'/kurisu/avatar/sided_thinking.idle.webp', speaking:'/kurisu/avatar/sided_thinking.speaking.webp'},
  sided_surprised:{idle:'/kurisu/avatar/sided_surprised.idle.webp',speaking:'/kurisu/avatar/sided_surprised.speaking.webp'},
  sad:            {idle:'/kurisu/avatar/sad.idle.webp',            speaking:'/kurisu/avatar/sad.speaking.webp'},
  blush:          {idle:'/kurisu/avatar/blush.idle.webp',          speaking:'/kurisu/avatar/blush.speaking.webp'},
  angry:          {idle:'/kurisu/avatar/angry.idle.webp',          speaking:'/kurisu/avatar/angry.speaking.webp'},
  disappointed:   {idle:'/kurisu/avatar/disappointed.idle.webp',   speaking:'/kurisu/avatar/disappointed.speaking.webp'}
};
function makePlayer(canvas){
  const ctx = canvas.getContext('2d');
  const cache = {};
  let cur = null, frames = 0, fi = 0, last = 0;
  function img(src){ if(!cache[src]){ const im = new Image(); im.src = src; cache[src] = im; } return cache[src]; }
  function set(src){
    if(cur === src) return;
    cur = src; fi = 0;
    const im = img(src);
    const ready = ()=>{ if(cur !== src) return;
      frames = (im.naturalWidth === CELL && im.naturalHeight === CELL)
        ? 1 : COLS * Math.floor(im.naturalHeight / CELL);
      draw(0); };
    (im.complete && im.naturalWidth) ? ready() : (im.onload = ready);
  }
  function draw(i){
    const im = img(cur);
    if(!im.complete || !im.naturalWidth) return;
    ctx.clearRect(0, 0, CELL, CELL);
    if(frames <= 1){ ctx.drawImage(im, 0, 0); return; }
    ctx.drawImage(im, (i % COLS) * CELL, Math.floor(i / COLS) * CELL, CELL, CELL, 0, 0, CELL, CELL);
  }
  function tick(t){
    if(cur && frames > 1 && !RM && t - last > 90){ fi = (fi + 1) % frames; draw(fi); last = t; }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  return { set };
}
const panelAv  = makePlayer(document.getElementById('avCanvas'));
const bubbleAv = makePlayer(document.getElementById('bubbleCanvas'));
/* 手机里的她：用人物包（full/）全身剪辑，与 CRT 同源 */
/* ================= ★P0-①（2026-10-16 站主 P0 修复半）：手机内存兜底 =================
   根因方向（批次 B §10.3 用排除法定到的）：iPhone Safari 连 video/webm;codecs=vp9 都不认
   ⇒ __xkVid 走 auto 降级进 pixel 档 ⇒ 画的是 /kurisu/full/*.hi.webp，
   而单张 hi 解码 = 34~53MB（manifest 的 decodedBytes 实测值：opening 38.8MB / idle 35.5MB /
   speaking·thinking 53.3MB）⇒ iOS 逐标签页内存上限把已解码位图丢掉 ⇒ 上屏就是**一整块灰**。
   本模块只做四件事（每条都留证据，验收脚本读 window.__xkTier）：
     ① 手机上**只到中档**：hi 一个请求都不发（noHi），走 medium 档 = /kurisu/full/*.boot.webp
        —— **同瓦片**（321×432 / 380×290）、24 帧、解码 10.6~13.3MB ⇒ 画质不变、内存降 3~4 倍；
     ② **位图被丢弃的检测**：抽检"她应该在那里"的画布区（非透明像素计数），连续 3 次全空 ⇒ 判定丢了；
     ③ **重试一次**（丢掉缓存里的 Image 重新取图 = 重新解码）；仍为空 ⇒ 降档 hi→medium→poster，
        写 degradeReason（宁可出静态帧，**不许静默留灰块** ✗）；
     ④ 诊断：window.__xkTier = {mobile,lowMem,noHi,initTier,tier,degraded,degradeReason,retries,checks,
        lastCheck,events,errors} ｜ 手机面板另记 bodyTier / bodyRetry。
   证据旋钮（只在 URL 上生效，默认行为逐字不变 —— 写在这里是为了"能本地确定性复现降档链"）：
     ?xk-tier=hi|medium|poster|auto  强制某一档（auto = 手机 medium / 桌面 hi）
     ?xk-tier-fail=<role>[,<role>]   把某几个角色当"位图已被丢弃"（复现 检测→重试→降档→静态帧）
     ?xk-tier-blank=1                抽检永远判空（同上，对全部角色）
   纪律：不改配色/背景/字体；**桌面 auto = hi，逐字等于改前**；不改首屏字节（手机上只会更小：hi 不在请求里）。
   ⚠ 这里的"medium 档"就是 full 系列的**中档 boot**（同瓦片、内存 1/4），不是 static/kurisu/medium/
     （134×180 瓦片 —— 那是"脸糊"的另一件事，属 ④ 的分析页；本模块只要"内存降下来、脸还在"）。 */
var XK_TIER = window.__xkTier || (function(){
  function q(k){ var m = new RegExp('[?&]' + k + '=([^&#]*)').exec(location.search || ''); return m ? decodeURIComponent(m[1]) : ''; }
  var ua = navigator.userAgent || '';
  var narrow = false;
  try { narrow = matchMedia('(max-width: 980px)').matches; } catch(e){}
  var mobile = /iPhone|iPad|iPod|Android|Mobile/i.test(ua) || narrow;
  var dm = (typeof navigator.deviceMemory === 'number') ? navigator.deviceMemory : 8;
  var forced = q('xk-tier');
  var T = { t0: performance.now(), mobile: mobile, lowMem: dm <= 4, narrow: narrow, dm: dm,
            forced: forced || 'auto', noHi: false, initTier: 'hi', tier: {}, degraded: {}, degradeReason: {},
            retries: {}, checks: 0, lastCheck: null, strike: 0, watchOn: false, phoneWatch: false,
            body: null, bodyTier: {}, bodyRetry: {}, bodyRole: null,
            fail: (q('xk-tier-fail') || '').split(',').filter(Boolean), blank: q('xk-tier-blank') === '1',
            events: [], history: [], errors: [] };
  T.noHi = (forced === 'medium' || forced === 'poster') ? true : (forced === 'hi' ? false : (mobile || T.lowMem));
  T.initTier = (forced === 'poster') ? 'poster' : (T.noHi ? 'medium' : 'hi');
  T.log = function(s){ try { var e = Math.round(performance.now() - T.t0) + 'ms ' + s; T.events.push(e); if(T.events.length > 30){ T.events.shift(); } T.history.push(e); if(T.history.length > 60){ T.history.shift(); } } catch(e){} };
  T.log('init mobile=' + mobile + ' lowMem=' + T.lowMem + ' noHi=' + T.noHi + ' tier=' + T.initTier + ' forced=' + T.forced);
  window.__xkTier = T;
  return T;
})();
XK_TIER.posterUrl = function(name){ return '/kurisu/full/' + name + '.poster.webp'; };
XK_TIER.role = function(name){ try { return (typeof CLIPS !== 'undefined' && CLIPS && CLIPS[name]) ? CLIPS[name] : null; } catch(e){ return null; } };
XK_TIER.tierOf = function(name){ return XK_TIER.tier[name] || XK_TIER.initTier; };
/* hi 只在"没被限档、也没降过档"时可用 —— 手机 noHi 与任何已降档的角色都在这里被挡住 */
XK_TIER.hiAllowed = function(name){ return !XK_TIER.noHi && !XK_TIER.tier[name]; };
XK_TIER.degrade = function(name, why){
  var c = XK_TIER.role(name); if(!c) return false;
  var cur = XK_TIER.tierOf(name);
  var next = (cur === 'hi' && c.bootSrc) ? 'medium' : 'poster';
  XK_TIER.tier[name] = next; XK_TIER.degraded[name] = next;
  XK_TIER.degradeReason[name] = why + ' @' + cur + '→' + next;
  XK_TIER.log('degrade ' + name + ' ' + XK_TIER.degradeReason[name]);
  if(next === 'poster'){ c.bootSrc = null; c.src = XK_TIER.posterUrl(name); c.frames = 1; }
  return next;
};
XK_TIER.retry = function(name){
  var c = XK_TIER.role(name); if(!c) return false;
  if(XK_TIER.retries[name]) return false;
  var cur = XK_TIER.tierOf(name);
  var url = (cur === 'hi') ? c.src : (cur === 'medium' ? c.bootSrc : c.src);
  if(!url) return false;
  XK_TIER.retries[name] = 1;
  try { if(cache){ delete cache[url]; } } catch(e){}
  try { img(url); } catch(e){ XK_TIER.errors.push('retry: ' + e); }
  XK_TIER.log('retry ' + name + ' @' + cur + '（同一个 URL 重新取图 = 重新解码）');
  return true;
};
/* 抽检"她应该在那里"的竖条：返回非透明像素计数（null = 读不到） */
XK_TIER.sample = function(cv){
  if(!cv || !cv.width || !cv.height) return null;
  var ctx = null; try { ctx = cv.getContext('2d', { willReadFrequently: true }); } catch(e){ return null; }   /* ★C11 */
  if(!ctx) return null;
  var W = cv.width, H = cv.height;
  var x0 = Math.floor(W * 0.20), x1 = Math.floor(W * 0.80);
  var y0 = Math.floor(H * 0.15), y1 = Math.floor(H * 0.95);
  var n = 0, nz = 0, rows = 24, step = Math.max(1, Math.floor((y1 - y0) / rows));
  for(var y = y0; y < y1; y += step){
    var d;
    try { d = ctx.getImageData(x0, y, Math.max(2, x1 - x0), 1).data; }
    catch(e){ XK_TIER.errors.push('getImageData: ' + e); return null; }
    for(var i = 3; i < d.length; i += 4){ n++; if(d[i] > 8){ nz++; } }
  }
  XK_TIER.checks++;
  XK_TIER.lastCheck = { w:W, h:H, samples:n, opaque:nz, at:Math.round(performance.now() - XK_TIER.t0) };
  return nz;
};
XK_TIER.applyForce = function(){
  try {
    if(typeof CLIPS === 'undefined' || !CLIPS) return;
    for(var k in CLIPS){ if(!Object.prototype.hasOwnProperty.call(CLIPS, k)) continue;
      if(XK_TIER.forced === 'poster'){ XK_TIER.tier[k] = 'medium'; XK_TIER.degrade(k, 'URL 旋钮 ?xk-tier=poster'); }
      else if(XK_TIER.noHi){ XK_TIER.tier[k] = 'medium'; }
    }
  } catch(e){ XK_TIER.errors.push('applyForce: ' + e); }
};
/* 主板画布（CRT）：cur = 当前 CLIPS 角色名 */
XK_TIER.watchCRT = function(){
  if(XK_TIER.watchOn) return false;
  var cv = document.getElementById('charCanvas');
  if(!cv || typeof CLIPS === 'undefined' || !CLIPS) return false;
  XK_TIER.watchOn = true;
  var fast = XK_TIER.blank || XK_TIER.fail.length > 0;
  if(XK_TIER.noHi || XK_TIER.forced !== 'auto' || fast){ XK_TIER.applyForce(); }
  var every = fast ? 500 : 1500, need = fast ? 1 : 3, gate = fast ? 1200 : 6000;
  XK_TIER.log('watchCRT on every=' + every + ' need=' + need + ' gate=' + gate);
  setInterval(function(){
    if(performance.now() - XK_TIER.t0 < gate) return;
    if(typeof XK_BOOT !== 'undefined' && XK_BOOT && XK_BOOT.phase < 4) return;
    var name = null;
    try { name = (typeof cur === 'string' && CLIPS[cur]) ? cur : null; } catch(e){}
    if(!name) return;
    var fastNow = XK_TIER.blank || XK_TIER.fail.indexOf(name) >= 0;
    if(XK_TIER.tierOf(name) === 'poster') return;   /* 已到底档，不再折腾（含旋钮复现） */
    var nz = XK_TIER.sample(cv);
    if(nz === null) return;
    if(fastNow) nz = 0;
    if(nz > 0){ XK_TIER.strike = 0; return; }
    XK_TIER.strike++;
    if(XK_TIER.strike < need) return;
    XK_TIER.strike = 0;
    if(!XK_TIER.retries[name]){ XK_TIER.retry(name); return; }
    XK_TIER.degrade(name, 'drawImage 后抽检 0 非透明像素（位图被系统丢弃）');
  }, every);
  return true;
};
/* 手机面板（外壳里的 phoneCanvas，用 full 全身剪辑） */
XK_TIER.bindBody = function(B){
  XK_TIER.body = B;
  try {
    for(var k in B){ if(!Object.prototype.hasOwnProperty.call(B, k)) continue;
      var b = B[k];
      if(XK_TIER.noHi && b && /\.hi\.webp$/.test(b.src)){
        b.src = b.src.replace(/\.hi\.webp$/, '.boot.webp'); b.frames = 24; XK_TIER.bodyTier[k] = 'medium';
      } else { XK_TIER.bodyTier[k] = XK_TIER.noHi ? 'medium' : 'hi'; }
    }
    XK_TIER.log('bindBody tier=' + JSON.stringify(XK_TIER.bodyTier));
  } catch(e){ XK_TIER.errors.push('bindBody: ' + e); }
};
XK_TIER.bodyOf = function(role){ XK_TIER.bodyRole = role; return (XK_TIER.body && XK_TIER.body[role]) ? XK_TIER.body[role] : null; };
XK_TIER.retryBody = function(role){
  if(XK_TIER.bodyRetry[role]) return false;
  var B = XK_TIER.body; if(!B || !B[role]) return false;
  XK_TIER.bodyRetry[role] = 1;
  var b = B[role]; b.src = b.src + (b.src.indexOf('?') < 0 ? '?' : '&') + 'xk_r=1';
  XK_TIER.log('retryBody ' + role + ' @' + (XK_TIER.bodyTier[role] || 'hi'));
  try { if(typeof render === 'function'){ render(); } } catch(e){}
  return true;
};
XK_TIER.degradeBody = function(role, why){
  var B = XK_TIER.body; if(!B || !B[role]) return false;
  var cur = XK_TIER.bodyTier[role] || 'hi';
  var next = (cur === 'hi') ? 'medium' : 'poster';
  XK_TIER.bodyTier[role] = next; XK_TIER.degraded['phone:' + role] = next;
  XK_TIER.degradeReason['phone:' + role] = why + ' @' + cur + '→' + next;
  XK_TIER.log('degradeBody ' + role + ' → ' + next);
  if(next === 'medium'){ var b = B[role]; b.src = b.src.replace(/\.hi\.webp$/, '.boot.webp'); b.frames = 24; }
  else { B[role] = { src: '/kurisu/full/' + role + '.poster.webp', frames: 1, interval: 42 }; }
  try { if(typeof render === 'function'){ render(); } } catch(e){}
  return next;
};
XK_TIER.watchPhone = function(){
  if(XK_TIER.phoneWatch) return false;
  var cv = document.getElementById('phoneCanvas');
  if(!cv || !XK_TIER.body) return false;
  XK_TIER.phoneWatch = true;
  var fast = XK_TIER.blank || XK_TIER.fail.length > 0;
  var every = fast ? 500 : 1500, need = fast ? 1 : 3, gate = fast ? 1200 : 6000;
  XK_TIER.log('watchPhone on every=' + every);
  setInterval(function(){
    if(performance.now() - XK_TIER.t0 < gate) return;
    try { if(typeof __xkPhoneDefer !== 'undefined' && __xkPhoneDefer) return; } catch(e){}
    var vAi = document.getElementById('v-ai');
    if(document.body.classList.contains('is-home')) return;
    var role = XK_TIER.bodyRole; if(!role) return;
    var fastNow = XK_TIER.blank || XK_TIER.fail.indexOf(role) >= 0;
    if(XK_TIER.bodyTier[role] === 'poster') return;   /* 已到底档，不再折腾 */
    var nz = XK_TIER.sample(cv);
    if(nz === null) return;
    if(fastNow) nz = 0;
    if(nz > 0){ XK_TIER.strike = 0; return; }
    XK_TIER.strike++;
    if(XK_TIER.strike < need) return;
    XK_TIER.strike = 0;
    if(!XK_TIER.bodyRetry[role] && XK_TIER.bodyTier[role] === 'medium'){ XK_TIER.retryBody(role); return; }
    XK_TIER.degradeBody(role, '手机面板抽检 0 非透明像素（位图被系统丢弃）');
  }, every);
  return true;
};
setTimeout(function(){ try { XK_TIER.watchCRT(); XK_TIER.watchPhone(); } catch(e){ XK_TIER.errors.push('watch: ' + e); } }, 1200);
const BODY = {
  idle:     {src:'/kurisu/full/idle.hi.webp',     frames:60, interval:42},
  speaking: {src:'/kurisu/full/speaking.hi.webp', frames:90, interval:34},
  thinking: {src:'/kurisu/full/thinking.hi.webp', frames:90, interval:34}
};
XK_TIER.bindBody(BODY);   /* ★P0-①：手机面板上限中档（boot），并挂降档链 */

/* ★V2 手机面板优先 E-mote（桌面大屏/够内存才加载；失败一行不改继续 Sprite 三段） */
(function(){
  /* 窄屏：手机面板退化为竖直静态立绘条，点一下放大/收起（不挂 E-mote，见下 w<1280 闸）*/
  (function(){
    var ph = document.querySelector('.phone');
    if(!ph || !window.matchMedia || !matchMedia('(max-width:980px)').matches) return;
    ph.style.cursor = 'pointer';
    ph.setAttribute('role','button');
    ph.addEventListener('click', function(e){
      if(e.target && e.target.closest && e.target.closest('.phone-btns')) return;
      document.documentElement.classList.toggle('xk-phone-open');
    });
    document.addEventListener('click', function(e){
      if(!document.documentElement.classList.contains('xk-phone-open')) return;
      if(ph.contains(e.target)) return;
      document.documentElement.classList.remove('xk-phone-open');
    }, true);
  })();
  var n = 0;
  function go(){
  var cv = document.getElementById('phoneCanvas');
  /* ★时序：phone-emote.js 是 defer 脚本、可能比本段后到 ⇒ 最多等 10s（40×250ms）再挂 */
  if(!cv || !window.XKPhoneEmote){ if(++n < 40) setTimeout(go, 250); return; }
  try { if(document.body && document.body.classList.contains('is-home')) return; } catch(e){}
  var w = window.innerWidth || 0, mem = navigator.deviceMemory || 0, cores = navigator.hardwareConcurrency || 0;
  if(w < 1280) return;
  if(mem && mem < 8) return;
  if(cores && cores < 4) return;
  if(window.__xkPhoneEmoteOff) return;
  var em = window.XKPhoneEmote.mount(cv, { model: 'kurisu_c', mode: 'idle', crop: 0.52 });
  if(!em) return;
  document.documentElement.classList.add('xk-phone-emote');
  window.__xkPhoneAnim = false;   /* ★V2.1：手机只放 E-mote，停掉原始帧动画 */
  XK_TIER.phoneEmote = em; window.__xkPhoneEmoteInst = em;
  em.onStatus(function(s){
    if(!s) return;
    /* ★ 加载中保留静态立绘垫底，只有 E-mote 真正 ready 才撤（否则加载期手机是空屏） */
    if(s.state === 'ready'){ document.documentElement.classList.add('xk-emote-ready'); }
    if(s.state === 'error' || s.state === 'off'){ document.documentElement.classList.remove('xk-phone-emote'); document.documentElement.classList.remove('xk-emote-ready'); XK_TIER.phoneEmote = null; }
    var el = document.getElementById('phoneState');
    if(el && s.state) el.textContent = String(s.state).toUpperCase();
  });
  /* ★兜底（2026-10-17 实测踩到）：模型从缓存命中时 mount 里就已经 ready，onStatus 只报「变化」，
     这一枪收不到 ⇒ 静态立绘和 E-mote 叠成两个人。这里补一个轮询，直到状态真为 ready 为止。 */
  var _rp = setInterval(function(){
    try{
      var s2 = (em.status && em.status()) || null;
      if(s2 && s2.state === 'ready'){ document.documentElement.classList.add('xk-emote-ready'); clearInterval(_rp); }
      else if(s2 && (s2.state === 'error' || s2.state === 'off')){ clearInterval(_rp); }
    }catch(e){ clearInterval(_rp); }
  }, 400);
  /* 模式跟随：读手机面板状态文字（IDLE/THINKING/SPEAKING），变化时通知 E-mote（不改原 setPhone） */
  var last = '';
  setInterval(function(){
    var el = document.getElementById('phoneState'); if(!el) return;
    var t = String(el.textContent || '').toUpperCase();
    if(t === last) return;
    last = t;
    var m = t.indexOf('SPEAK') >= 0 ? 'speaking' : (t.indexOf('THINK') >= 0 ? 'thinking' : 'idle');
    try { em.setMode(m); } catch(e){}
  }, 800);
  }
  go();
})();

function makeBodyPlayer(canvas){
  const ctx = canvas.getContext('2d');
  canvas.width = 321; canvas.height = 432;
  const CW = 321, CH = 432, COLS = 8;
  const cache = {};
  let cur = null, frames = 0, fi = 0, last = 0, iv = 42;
  function img(src){ if(!cache[src]){ const im = new Image(); im.src = src; cache[src] = im; } return cache[src]; }
  function set(clip){
    if(cur === clip.src) return;
    cur = clip.src; frames = clip.frames; iv = clip.interval; fi = 0;
    const im = img(cur);
    const ready = ()=>{ if(cur !== clip.src) return; draw(0); };
    (im.complete && im.naturalWidth) ? ready() : (im.onload = ready);
  }
  function draw(i){
    const im = img(cur);
    if(!im.complete || !im.naturalWidth) return;
    ctx.clearRect(0, 0, CW, CH);
    ctx.drawImage(im, (i % COLS) * CW, Math.floor(i / COLS) * CH, CW, CH, 0, 0, CW, CH);
  }
  function tick(t){
    if(cur && frames > 1 && !RM && window.__xkPhoneAnim !== false && t - last > iv){ fi = (fi + 1) % frames; draw(fi); last = t; }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  return { set };
}
const phoneBody = makeBodyPlayer(document.getElementById('phoneCanvas'));
const phoneAv  = null; // 手机用全身播放器，见 phoneBody
const phoneEl  = document.getElementById('phone');
const phoneLineEl = document.getElementById('phoneLine');
const phoneStateEl = document.getElementById('phoneState');
/* 手机时间（演示用真实时钟） */
function tickClock(){ const d=new Date();
  document.getElementById('phoneClock').textContent = String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0'); }
tickClock(); setInterval(tickClock, 20000);
/* ★P0（站主 2026-10-16）：手机里的助手 —— 功能按钮 */
(function(){
  var $=function(i){ return document.getElementById(i); };
  var snd=$('phSnd'), say=$('phSay'), mood=$('phMood'), anim=$('phAnim');
  var MOODS=['normal','sided_thinking'], mi=0;
  function soundOn(){ return !(window.__xkSound && window.__xkSound.on === false); }
  function syncSnd(){ if(!snd) return; snd.textContent = soundOn() ? '🔊' : '🔇'; snd.className = soundOn() ? '' : 'off'; }
  if(snd){ snd.onclick=function(){ var b=document.getElementById('xkSndBtn'); if(b){ b.click(); } setTimeout(syncSnd,60); }; syncSnd(); setInterval(syncSnd,1500); }
  if(say){ say.onclick=function(){
    var txt='嗯——我在。你想问什么？';
    try { if(typeof window.__xkSay === 'function') { window.__xkSay(); } } catch(e){}
    try { speak(txt); } catch(e){}
  }; }
  if(mood){ mood.onclick=function(){ mi=(mi+1)%MOODS.length; try { emo=MOODS[mi]; setPhone(); render(); } catch(e){} }; }
  if(anim){ anim.onclick=function(){ window.__xkPhoneAnim = (window.__xkPhoneAnim === false); anim.className = (window.__xkPhoneAnim === false) ? 'off' : ''; }; }
})();


/* ============ 面板状态 ============ */
var __xkPhoneDefer = document.body.classList.contains('is-ai');   /* /ai/：首帧不空取全身图集，1650ms 后允许 */
const holo = document.getElementById('holo');
const stateEl = document.getElementById('holoState');
const sayEl = document.getElementById('holoSay');
/* ★慢网减量（2026-10-16，主窗口量到的事实）：初始 `mode='speaking'` 会让首帧就去取
   `kurisu/avatar/<emo>.speaking.webp`（normal 那张 189KB），而**开页并没有任何音频在播**
   （语音要手势 + 声音开关），2.6 秒后又被 L1078 切回 idle ⇒ 这 189KB 纯属白取（真机实测 2.8s）。
   改成初始 idle：首帧只取 idle 那张（normal.idle.webp 84.7KB，本来就要用）；
   一旦有真台词（下方 `speak()`）或音频播放，`mode` 仍会被置 'speaking'、该图那时才取 —— 三态语义不变。 */
let emo = 'normal', mode = 'idle', speakTimer = null;
/* ★V5（2026-10-17）：[EMO:xxx] 情绪标签的唯一入口（渲染侧 xkEmoClean 先剥标签，页面永不出现方括号）。
   两条腿：① 原 Sprite/手机三态照旧（emo + render）；② 手机已换成 E-mote 时，按表情标签直接切脸。
   未知情绪回落 normal；异常不影响渲染。 */
var XK_EMO_EXPR = [
  [/happy/,            /嬉|笑|喜|楽/],
  [/sad/,              /悲|泣|哀|しょんぼり/],
  [/angry/,            /怒|怒り/],
  [/surprised/,        /驚|吃驚|びっくり/],
  [/blush/,            /照|恥|赤面/],
  [/disappointed/,     /困|呆|疲/],
  [/sided_thinking/,   /呆然|考え/],
  [/normal/,           /平常/]
];
function xkEmoToLabel(n){
  var em = window.__xkPhoneEmoteInst;
  if(!em || typeof em.expressionLabels !== 'function'){ return null; }
  var labels = em.expressionLabels();
  if(!labels || !labels.length){ return null; }
  var re = null;
  for(var i = 0; i < XK_EMO_EXPR.length; i++){ if(XK_EMO_EXPR[i][0].test(n)){ re = XK_EMO_EXPR[i][1]; break; } }
  if(!re){ re = /平常/; }
  for(var j = 0; j < labels.length; j++){ if(re.test(labels[j])){ return labels[j]; } }
  return null;
}
window.__xkSetEmo = function(n){
  if(!n) return;
  if(!EMOS[n]) n = 'normal';
  try{ emo = n; setPhone(); render(); }catch(e){}
  try{
    var em = window.__xkPhoneEmoteInst, lb = xkEmoToLabel(n);
    if(em && lb && typeof em.setExpression === 'function'){ em.setExpression(lb); }
  }catch(e2){}
};
function setPhone(){
  if(__xkPhoneDefer){ phoneStateEl.textContent = '连接中'; return; }
  /* ★P0-①：按 XK_TIER 当前的档取图（手机上 = boot 中档；降档后 = 静态 poster） */
  var _xkRole = (mode === 'speaking' ? 'speaking' : (emo === 'sided_thinking' ? 'thinking' : 'idle'));
  XK_TIER.bodyOf(_xkRole);
  phoneBody.set(XK_TIER.body[_xkRole] || BODY[_xkRole]);
}
function render(){
  const strip = EMOS[emo][mode === 'speaking' ? 'speaking' : 'idle'];
  if(!document.body.classList.contains('is-ai')) panelAv.set(strip);
  if(document.body.classList.contains('holo-min') && !document.body.classList.contains('is-ai')) bubbleAv.set(EMOS[emo].idle);
  if(!document.body.classList.contains('is-home')) setPhone();
  const label = mode === 'speaking' ? 'SPEAKING' : (emo === 'sided_thinking' ? 'THINKING' : 'IDLE');
  stateEl.textContent = label;
  phoneStateEl.textContent = __xkPhoneDefer ? '连接中' : label;
  holo.classList.toggle('live', mode === 'speaking' && !RM);
  phoneEl.classList.toggle('live', mode === 'speaking' && !RM);
}
function speak(html){
  sayEl.style.opacity = 0;
  phoneLineEl.style.opacity = 0;
  setTimeout(()=>{ sayEl.innerHTML = html; sayEl.style.opacity = 1;
    phoneLineEl.innerHTML = html; phoneLineEl.style.opacity = 1; }, 150);
  mode = 'speaking'; render();
  clearTimeout(speakTimer);
  speakTimer = setTimeout(()=>{ mode = 'idle'; render(); }, 2600);
}
render();
setTimeout(()=>{ mode = 'idle'; render(); }, 2600);
/* ★窗口 Q（2026-10-16）移动端硬伤 2（配对修复）：窄屏**默认收起**为头像泡 ——
   .holo 是 fixed 浮层，窄屏整幅（355/370/394 × 219）压住正文；收起后与 .main 零重叠。
   断点与 CSS 的 @media (max-width:980px) 同口径；越过断点回桌面语义（把 class 摘掉，
   否则"手机上收起了"这个状态会漂到桌面，桌面就看不到面板了）。≥981px 行为与改前逐字相同。 */
const mqNarrow = matchMedia('(max-width:980px)');
if (mqNarrow.matches) document.body.classList.add('holo-min');
mqNarrow.addEventListener('change', e=>{ if(!e.matches) document.body.classList.remove('holo-min'); });
document.getElementById('holoFold').onclick = ()=>{ document.body.classList.add('holo-min'); render(); };
document.getElementById('holoBubble').onclick = ()=>document.body.classList.remove('holo-min');

/* ★2026-10-16 ①：/ai/ 首帧 render() 里的手机全身图集延到 1650ms（越过首屏 1.5s 窗口；
   实测请求落在 ~1755ms，距窗口边界留 ~255ms）+ 状态标签在这段里如实写'连接中'。
   其余页照原样立刻 render()（首屏可见的东西不变慢），2600ms 那次 render() 也照原样立刻取。 */
if(__xkPhoneDefer){ setTimeout(function(){ __xkPhoneDefer = false; render(); }, 1650); }
/* ============ 页面切换 ============ */
const views = {home:'v-home', monitor:'v-monitor', ai:'v-ai', notes:'v-notes', range:'v-range', about:'v-about'};
const SAYS = {
  home:'回到主页了。我一直待在这台显示器里。',
  monitor:'这一屏是我们监测到的情况，数字都是真的；取不到我就写读不到。',
  ai:'有问题就问我，我照真检索到的东西答；答不了我就说答不了。',
  notes:'笔记都在这儿，新的排在最前面。',
  range:'想试试攻击输入？点上面的一键样本，判定全部来自后端检测组件。',
  about:'这个站点的一切口径都在这一页：数据从哪来、什么能说什么不能说。'
};
function switchView(v){
  document.querySelectorAll('.view').forEach(e=>e.classList.remove('on'));
  document.getElementById(views[v]).classList.add('on');
  document.querySelectorAll('#dock button').forEach(b=>b.classList.toggle('on', b.dataset.v === v));
  document.body.classList.toggle('is-home', v === 'home');
  document.body.classList.toggle('is-ai', v === 'ai');
  if(v === 'home'){ if(window.__enterHome) window.__enterHome(); return; }
  if(v === 'monitor'){ if(opsTab==='live') drawSpark(); if(opsTab==='graph') startGraph(); if(opsTab==='stats') runCounters(); }
  speak(SAYS[v]);
}
document.querySelectorAll('#dock button').forEach(b=>b.onclick = ()=>switchView(b.dataset.v));

/* ============ AI 问答（真实链路：POST /api/public/ask） ============ */
/* ★2026-10-15 接手批：原 demo 这里等 900ms 插一段写死的回答（0 网络请求）—— 改成真实调用。
   纪律：state / stateLabel / citations / failureReason / quota 全部按后端返回值如实展示；
        generated=false 就写服务端给的原因，绝不补"像答案"的文字；失败/超时/限流如实写，不给替代答案。
        不做 SSE/WebSocket（公开面只有一次性 POST），最多等 20 秒，429 按 Retry-After 倒计时。 */
const XK_ASK_API = ((document.querySelector('meta[name="wb-api"]')||{}).content||'').replace(/\/+$/,'');
const XK_ASK_TIMEOUT = 20000, XK_ASK_MAX = 600;
const XK_STATE_LABEL = {
  'model':['模型研判'], 'rule-based':['规则解析（拒答）'],
  'input-insufficient':['依据不足，不做定性'], 'no-retrieval':['未检索到依据，不给结论'],
  'retrieval-failed':['检索不可用，未生成'], 'model-failed':['模型不可用，未生成'],
  'injection-blocked':['命中提示注入护栏'],
  /* ★2026-10-16 状态语义分层（与 XK_STATE_CLS 一一对应，档位必须同源）：
     no-live-data = 这个数没有实时数据源（例如公开面本来就不取实时值）⇒ 写"没有实时数据源"；
     no-kb-basis  = 知识库里确实没有这条依据（检索成功但命中 0）⇒ 写"知识库无依据"；
     二者都**不等于**"取不到"（端点失败才写"读不到"）。 */
  'no-live-data':['没有实时数据源'], 'no-kb-basis':['知识库无依据']
};
function xkAskEsc(s){ return String(s==null?'':s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
/* ★V5（2026-10-17）：[EMO:xxx] 情绪标签协议（后端可选输出，前端必须完全消化）
   · xkEmoClean：从正文里剥掉所有标签 ⇒ 页面永不出现 "[EMO:" 字样（泄漏率=0 第一道闸）
   · xkEmoTags ：按出现顺序取 tag 列表 ⇒ 交给 __xkSetEmo 逐句继承
   · 只认 [EMO:小写字母/下划线]，其它形态原样保留（宁可不解析，也不吃掉正常文本） */
const XK_EMO_RE = /\[EMO:([a-z_]+)\]/gi;
function xkEmoClean(s){
  return String(s==null?'':s).replace(XK_EMO_RE,'').replace(/[ \t]{2,}/g,' ').replace(/\n{3,}/g,'\n\n').trim();
}
function xkEmoTags(s){
  const out = [];
  String(s==null?'':s).replace(XK_EMO_RE, function(_,n){ out.push(String(n).toLowerCase()); return ''; });
  return out;
}
function xkEmoPlay(seq){
  if(!seq || !seq.length) return;
  if(typeof window.__xkSetEmo !== 'function') return;
  let i = 0;
  (function step(){
    if(i >= seq.length) return;
    try{ window.__xkSetEmo(seq[i++]); }catch(e){ return; }
    if(i < seq.length) setTimeout(step, 900);
  })();
}
window.__xkEmoStat = function(){ return { helper: typeof xkEmoClean === 'function', leaks: (document.body.innerText.match(/\[EMO:/g)||[]).length }; };
function xkInline(s){
  return s.replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>')
          .replace(/`([^`]+)`/g,'<code>$1</code>')
          .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}
/* 极简 markdown：**先整段转义**再套标签 —— 后端正文里就算带 <script> 也只是文本 */
function xkMd(src){
  const t = xkAskEsc(src).trim();
  return t.split(/\n{2,}/).map(p=>p.trim()).filter(Boolean).map(p=>{
    const lines = p.split(/\n/);
    if(lines.every(l=>/^&gt;\s?/.test(l)))       /* 引用块（后端的编排说明大量用 >）
                                                    ⚠️ 整段已先过 xkAskEsc → ">" 已变成 "&gt;"，必须按转义后的写法匹配 */
      return '<blockquote style="border-left:2px solid var(--acc);padding-left:10px;margin:6px 0;color:var(--mut)">'+
             lines.map(l=>xkInline(l.replace(/^&gt;\s?/,''))).join('<br>')+'</blockquote>';
    if(lines.every(l=>/^[-*+]\s+/.test(l)))
      return '<ul>'+lines.map(l=>'<li>'+xkInline(l.replace(/^[-*+]\s+/,''))+'</li>').join('')+'</ul>';
    if(lines.every(l=>/^\d+[.)]\s+/.test(l)))
      return '<ol>'+lines.map(l=>'<li>'+xkInline(l.replace(/^\d+[.)]\s+/,''))+'</li>').join('')+'</ol>';
    const h = p.match(/^(#{1,4})\s+(.*)$/);
    if(h) return '<p style="font-weight:600;margin:8px 0 2px">'+xkInline(h[2])+'</p>';
    /* ★C8（2026-10-18 外部巡检第 8 条）：模型正文常在**每句末尾硬换行**（非 markdown 段落），
       以前`<br>` 渲染会把一句话拆成几行（实测：“暴力破解是反复试。”与“密码。”各占一行）。
       markdown 规范里单个换行 = 软换行（当空格），只有空行才分段；按规范走。 */
    return '<p>'+lines.map(xkInline).join(' ')+'</p>';
  }).join('');
}
let xkAsking = false;
/* 站主已登录 ⇒ 同一个公开端点，但带上 X-User-Token：后端认到有效令牌就**跳过「每 IP 6 次/分钟」限流**
   （响应结构完全不变，所以展示层不用分叉）。未登录/令牌失效 ⇒ 照旧限额。
   为什么不用 /api/user/ask：那条路的响应字段与公开面不同（answer/round/note…），展示层得再写一套，
   而这一层只需要「不限次」，不值得引入第二套契约。 */
function xkOwnerToken(){
  try {
    var t = localStorage.getItem('xk-auth-token');
    var L = window.__xkLogin;
    if (t && L && L.state === 'ok') return t;
  } catch(e){}
  return '';
}
function xkAskApi(question){
  const ctrl = (typeof AbortController === 'function') ? new AbortController() : null;
  const timer = setTimeout(()=>{ if(ctrl) ctrl.abort(); }, XK_ASK_TIMEOUT);
  const owner = xkOwnerToken();
  const headers = {'Content-Type':'application/json'};
  if (owner) headers['X-User-Token'] = owner;
  return fetch(XK_ASK_API + '/api/public/ask', {
    method:'POST', headers: headers,
    mode:'cors', credentials:'omit', cache:'no-store',
    signal: ctrl ? ctrl.signal : undefined,
    body: JSON.stringify({ question: String(question).slice(0, XK_ASK_MAX) })
  }).then(res=>{ clearTimeout(timer);
    /* 令牌过期/被撤销：清掉本地态，让 UI 回到「未登录」；本次请求仍按原样把结果交给展示层 */
    if (owner && (res.status === 401 || res.status === 403)) {
      try { localStorage.removeItem('xk-auth-token'); localStorage.removeItem('xk-auth-user'); } catch(e){}
      if (window.__xkLogin) { window.__xkLogin.state = 'anon'; window.__xkLogin.reason = 'token-expired'; }
    }
    return res.json().catch(()=>null).then(body=>({ status:res.status, ok:res.ok, body,
      retryAfter:res.headers.get('Retry-After') }));
  }).catch(err=>{ clearTimeout(timer);
    if(err && err.name === 'AbortError'){ const e = new Error('timeout'); e.timeout = true; throw e; }
    throw err; });
}
function xkPush(kind, html){
  const log = document.getElementById('chatlog');
  log.insertAdjacentHTML('beforeend', '<div class="msg '+(kind==='me'?'me':'ai')+'"></div>');
  const el = log.lastElementChild;
  el.innerHTML = html; el.scrollIntoView({block:'end'});
  return el;
}
function xkBadge(text){ const b = document.querySelector('.chat-hd .badge'); if(b) b.innerHTML = '<span class="dot"></span>' + xkAskEsc(text); }
function xkQuota(d){
  const q = document.querySelector('.chat-hd .quota'); if(!q) return;
  const owner = !!xkOwnerToken();
  if (owner) {
    const used = (d && d.quota && d.quota.used != null) ? d.quota.used : null;
    q.textContent = '站主登录：不限次（软限额每日只提醒不硬停）' +
      (used == null ? '' : ' · 今日已用 ' + used + ' 次');
    return;
  }
  q.textContent = (d && d.quota && d.quota.pool)
    ? '额度池 '+d.quota.pool+'：已用 '+(d.quota.used==null?'—':d.quota.used)+' / '+(d.quota.limit==null?'—':d.quota.limit)+' · 每 IP 6 次/分钟'
    : '额度：未返回 · 每 IP 6 次/分钟';
}
/* ★R2：引用卡升级成"引用卡组" —— 标题行给命中数，每条是原生 <details> 可展开核验（零 JS）。
   0 条引用时不渲染卡组，由状态徽标单独说明（generated=false 的拒答不该假装有引用）。 */
function xkCites(d){
  const cs = d.citations || []; if(!cs.length) return '';
  const items = cs.map((c,i)=>{
    const bits = [];
    if(c.sourceTypeLabel) bits.push(c.sourceTypeLabel);
    if(c.trustLevelLabel) bits.push(c.trustLevelLabel);
    if(c.score!=null && !isNaN(Number(c.score))) bits.push('相关度 ' + (Math.round(Number(c.score)*100)/100));
    return '<details class="cite"><summary>['+(i+1)+'] 《'+xkAskEsc(c.title||'（无标题）')+'》'+(bits.length?' · '+xkAskEsc(bits.join(' · ')):'')+'</summary>'+
      '<div class="snip">'+(c.snippet?xkAskEsc(c.snippet):'（后端未返回片段）')+'</div></details>';
  }).join('');
  return '<div class="citebox"><div class="citebox-hd">引用命中 '+cs.length+' 条 · 点任一条展开片段核验（全部来自公开白名单语料）</div>'+items+'</div>';
}
/* ★R2：状态徽标分档（颜色映射在 CSS，复用 ok/warn/bad 既有状态色，不新增色值） */
const XK_STATE_CLS = {
  'model':'st-ok', 'rule-based':'st-warn', 'input-insufficient':'st-warn', 'no-retrieval':'st-warn',
  'retrieval-failed':'st-bad', 'model-failed':'st-bad', 'injection-blocked':'st-bad',
  /* ★2026-10-16 状态语义分层：把"没有实时数据源"与"有数据但这题没依据"从"取不到"里分出来，
     否则页面上会出现"0 / 读不到 / 无数据"三种说法混用。同一状态在任何页面都必须同一档。 */
  'no-live-data':'st-warn', 'no-kb-basis':'st-warn'
};
function xkRenderAnswer(el, d){
  const st = d.state || '';
  const label = d.stateLabel || (XK_STATE_LABEL[st] ? XK_STATE_LABEL[st][0] : (st || '未识别状态'));
  let html = '<div class="who">AI 安全 · <span class="st '+(XK_STATE_CLS[st]||'')+'">'+xkAskEsc(label)+'</span></div>';
  if(d.injection && d.injection.blocked)
    html += '<p>输入命中提示注入护栏（'+xkAskEsc(d.injection.hitCount||0)+' 条规则）；下面是把它当"不可信数据"处理后的结果。</p>';
  if(d.failureReason) html += '<p><b>服务端说明：</b>'+xkAskEsc(d.failureReason)+'</p>';
  const _ans = d.answer;
  /* ★2026-10-17 去重：后端 2026-10-17 起在正文末尾附一行「依据：N 条 ›」，而本页下面还会渲染一张
     可展开的引用卡（同一 N）。两边都留 = 页面上出现两次"依据"。
     取舍：正文那行**剥掉**，改由引用卡的标题行显示（保留"可展开看片段"这个能力，且只有一处）。 */
  const _rawClean = xkEmoClean(_ans);
  const _citeLine = /(^|\n)\s*依据：\s*\d+\s*条\s*›?\s*$/;
  const _clean = _rawClean ? _rawClean.replace(_citeLine, '').replace(/\n+$/, '') : _rawClean;
  if(_clean) html += xkMd(_clean);
  else if(!d.failureReason) html += '<p>这次没有返回答案正文（state='+xkAskEsc(st||'—')+'）。</p>';
  html += xkCites(d);
  if(d.clientIpMasked || (d.quota && d.quota.pool))
    html += '<div class="cite">来源 IP（后端已掩码）：'+xkAskEsc(d.clientIpMasked||'—')+(d.quota&&d.quota.pool?' · 额度池 '+xkAskEsc(d.quota.pool):'')+'</div>';
  el.innerHTML = html;
  xkEmoPlay(xkEmoTags(_ans));               /* ★V5：逐句继承（900ms 一句，最后一句停住） */
  const log = document.getElementById('chatlog'); if(log) log.scrollTop = log.scrollHeight;
}
function xkCountdown(el, msg, secs){
  let left = Math.max(1, Number(secs)||0);
  clearInterval(el.__cd);
  function paint(){
    if(!document.body.contains(el)){ clearInterval(el.__cd); return; }
    const head = '<div class="who">AI 安全 · <span class="st">被限流</span></div>';
    if(left<=0){ el.innerHTML = head+'<p>'+xkAskEsc(msg)+'<br>等待结束，可以重新提问了。</p>'; clearInterval(el.__cd); return; }
    el.innerHTML = head+'<p>'+xkAskEsc(msg)+'<br>请稍后再试 <b>'+left+'</b> 秒。</p>';
    left -= 1;
  }
  paint(); el.__cd = setInterval(paint, 1000);
}
function askDemo(){
  const inp = document.getElementById('askInput');
  const q = inp.value.trim(); if(!q) return;
  if(xkAsking) return;                 /* 同一来源只允许 1 个在飞：前端也不重复发 */
  xkAsking = true;
  inp.value = '';
  xkPush('me', '').textContent = q;
  emo = 'sided_thinking'; mode = 'idle'; render();
  stateEl.textContent = 'THINKING';
  /* ★E2 思考垫音：开声时先放一句短垫音，填住「等 3–20 秒」的空档；不改字幕 */
  try {
    if (D.sound && window.KurisuPlayer && KurisuPlayer.speakGroup) {
      var _ls = ['lead_wait','lead_hmm','lead_check'];
      KurisuPlayer.speakGroup('lead_in', { preferId: _ls[Math.floor(Math.random()*_ls.length)] });
    }
  } catch (e) {}
  xkBadge('AI 安全 · 生成中…');
  const pending = xkPush('ai', '<div class="who">AI 安全 · <span class="st">生成中…</span></div><p>正在走检索增强链路（最多 20 秒）…</p>');
  const t0 = Date.now();
  xkAskApi(q).then(r=>{
    const body = r.body;
    if(r.status === 429){
      const wait = parseInt(r.retryAfter || (body&&body.retryAfter) || 0, 10) || 60;
      xkCountdown(pending, (body&&body.message)||'请求被限流。', wait);
      stateEl.textContent = 'RATE-LIMIT'; xkBadge('AI 安全 · 被限流'); emo = 'normal'; render(); return;
    }
    if(!r.ok || !body || body.data === undefined){
      pending.innerHTML = '<div class="who">AI 安全 · <span class="st">请求失败</span></div><p>接口返回 HTTP '+xkAskEsc(r.status)+'，没有可用数据。'+
        (body&&body.message?'后端说明：'+xkAskEsc(body.message):'')+' 这里不显示任何替代答案。</p>';
      stateEl.textContent = 'FAILED'; xkBadge('AI 安全 · 请求失败'); emo = 'normal'; render(); return;
    }
    const d = body.data || {};
    xkRenderAnswer(pending, d);
    xkQuota(d);
    const conf = XK_STATE_LABEL[d.state];
    xkBadge('AI 安全 · ' + (conf ? conf[0] : (d.state || '已返回')));
    stateEl.textContent = (d.state === 'model') ? 'ANSWERED' : (d.state || 'DONE');
    emo = (d.state === 'model') ? 'normal' : 'sided_thinking';
    render();
    speak(d.generated === true ? '回答生成了。引用与状态标注都在消息里，可展开核验。'
                              : '这次没有生成结论，原因如实写在消息里 —— 我不编答案。');
    window.__xkAskLast = { status:r.status, state:d.state, ms:Date.now()-t0, cites:(d.citations||[]).length };
  }).catch(err=>{
    if(err && err.timeout){
      pending.innerHTML = '<div class="who">AI 安全 · <span class="st">超时</span></div><p>等了 20 秒还没返回，这次请求已放弃。后端可能正在排队、或模型这一轮很慢 —— 这里不显示任何推测的答案，过一会儿可以重试。</p>';
      stateEl.textContent = 'TIMEOUT'; xkBadge('AI 安全 · 超时');
    }else{
      pending.innerHTML = '<div class="who">AI 安全 · <span class="st">请求失败</span></div><p>提问失败（网络不可达或跨域被拒）。没有拿到答案，也没有替代结论。</p>';
      stateEl.textContent = 'FAILED'; xkBadge('AI 安全 · 请求失败');
    }
    emo = 'normal'; render();
  }).then(()=>{ xkAsking = false; });
}
document.getElementById('askBtn').onclick = askDemo;
document.getElementById('askInput').addEventListener('keydown', e=>{ if(e.key === 'Enter') askDemo(); });


/* ================= 桐莉栖语音（L1 预渲染语音库）· 内容页 =================
   ★2026-10-15 接手批：与原 demo 的差别 —— 原来只 speak() 打字幕，一个音频都不播。
   资产：static/kurisu/voice/bank.json。手势前不播（只记 pending），取不到只显示字幕。 */
const XKV = { bank:null, unlocked:false, pending:null, lastId:null, audio:null, plays:0, errors:[] };
window.__xkVoice = XKV;
function xkvLine(id){ return (XKV.bank && XKV.bank.lines && XKV.bank.lines[id]) || null; }
function xkvLoad(){
  if(XKV.bank) return Promise.resolve(XKV.bank);
  /* ★慢网减量（2026-10-16）：`no-store` → `no-cache`（内容页同主页，理由见 HOME_VOICE 里那段注释）：
     既不做无谓的第二次 37KB 整份重下，又保留"每次都向源站再验证"的新鲜度保证。 */
  return fetch('/kurisu/voice/bank.json', {cache:'no-cache'}).then(r=>{
    if(!r.ok) throw new Error('bank HTTP '+r.status); return r.json();
  }).then(b=>{ XKV.bank = b; return b; }).catch(e=>{ XKV.errors.push('bank: '+e); return null; });
}
function xkvUnlock(){
  if(XKV.unlocked) return;
  XKV.unlocked = true;
  if(XKV.pending){ const id = XKV.pending; XKV.pending = null; xkvPlay(id); }
}
function xkvPageLine(){
  const on = document.querySelector('.view.on'); const id = on ? on.id : '';
  return ({ 'v-monitor':'nav_monitor', 'v-notes':'nav_notes', 'v-ai':'nav_ai', 'v-what':'nav_what', 'v-lab':'nav_lab' })[id] || 'nav_home';
}
function xkvPlay(id){
  const line = xkvLine(id);
  if(!line){ XKV.errors.push('no line: '+id); return; }
  if(!XKV.unlocked){ XKV.pending = id; return; }
  if(XKV.lastId === id && XKV.audio && !XKV.audio.paused) return;
  try{
    if(XKV.audio){ try{ XKV.audio.pause(); }catch(_){} }
    const a = new Audio('/' + String(line.audio).replace(/^\/+/, ''));
    a.preload = 'auto';
    XKV.audio = a; XKV.lastId = id;
    a.addEventListener('playing', ()=>{ XKV.plays++; });
    a.addEventListener('error', ()=>{ XKV.errors.push('audio: '+id); });
    const pr = a.play();
    if(pr && pr.catch){ pr.catch(err=>{ XKV.errors.push('play: '+(err && err.name)); }); }
    if(typeof speak === 'function') speak(line.text);   /* 字幕与语音同一句；同时把面板切到 speaking */
  }catch(e){ XKV.errors.push('audio ctor: '+e); }
}
addEventListener('pointerdown', xkvUnlock, {once:true});
addEventListener('keydown', xkvUnlock, {once:true});
setTimeout(()=>{ xkvLoad().then(()=>xkvPlay(xkvPageLine())); }, 1800);


/* ================= ★批次 R2（2026-10-16 前端优化批）：交互层 ================= */
/* ① 作战室 tab：hash 直达 + ←/→ 方向键（不拆页面，只让某个 tab 可分享/可直达） */
(function(){
  if(!document.querySelector('#v-monitor.on')) return;      /* 只有 /alerts/ 的作战室是亮的 */
  var nav = document.getElementById('opsTabs'); if(!nav) return;
  var tabs = Array.prototype.slice.call(nav.querySelectorAll('button'));
  if(!tabs.length) return;
  tabs.forEach(function(b){
    b.addEventListener('click', function(){
      try{ history.replaceState(null, '', '#' + b.dataset.tab); }catch(_){}
    });
  });
  var h = (location.hash || '').replace(/^#/, '');
  if(h){ tabs.forEach(function(b){ if(b.dataset.tab === h) b.click(); }); }
  nav.addEventListener('keydown', function(ev){
    if(ev.key !== 'ArrowLeft' && ev.key !== 'ArrowRight') return;
    var i = tabs.indexOf(document.activeElement);
    if(i < 0) return;
    ev.preventDefault();
    var n = tabs[(i + (ev.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    n.focus(); n.click();
  });
})();
/* ② 实时攻击流：暂停/继续（暂停期间新行进 backlog，恢复时补渲染；不丢数据、不多请求） */
(function(){
  var btn = document.getElementById('feedPause');
  if(!btn || typeof feedRow !== 'function') return;
  var paused = false, backlog = [], queued = {};
  btn.addEventListener('click', function(){
    paused = !paused;
    btn.classList.toggle('on', paused);
    btn.textContent = paused ? '继续' : '暂停';
    btn.setAttribute('aria-pressed', String(paused));
    if(!paused && backlog.length){
      backlog.forEach(function(it){ feedSeen[it.key] = 1; feedRow(it); });
      backlog = []; queued = {}; feedTrim();
    }
  });
  var orig = window.__xkRenderFeed;
  window.__xkRenderFeed = function(){
    var items = window.XK_FEED;
    if(paused && items && items.length){
      items.forEach(function(it){ if(!feedSeen[it.key] && !queued[it.key]){ queued[it.key] = 1; backlog.push(it); } });
      return;   /* 暂停中：只入队不上屏（「读不到/空」提示行不受暂停影响，仍走 orig） */
    }
    orig();
  };
})();
/* ③ AI 页：示例问题 chips（复用 anchor-row 胶囊样式；点了 = 填进输入框并发送） */
(function(){
  var row = document.getElementById('askEx'); if(!row) return;
  if(!document.querySelector('#v-ai.on')) return;
  var QS = ['什么是暴力破解？怎么防', '蜜罐是怎么抓到攻击者的', 'SQL 注入的原理与防御', '提示注入是什么'];
  row.innerHTML = QS.map(function(q){
    return '<a href="#" data-q="' + xkAskEsc(q) + '">' + xkAskEsc(q) + '</a>';
  }).join('');
  row.addEventListener('click', function(ev){
    var a = ev.target.closest ? ev.target.closest('[data-q]') : null; if(!a) return;
    ev.preventDefault();
    var inp = document.getElementById('askInput'); if(!inp) return;
    inp.value = a.getAttribute('data-q');
    if(typeof askDemo === 'function') askDemo();
  });
})();
/* ④ 笔记：分类 chips 过滤（纯前端，列表已在 SSR 里，零请求） */
(function(){
  var row = document.getElementById('catRow'); if(!row) return;
  row.addEventListener('click', function(ev){
    var a = ev.target.closest ? ev.target.closest('[data-cat]') : null; if(!a) return;
    ev.preventDefault();
    Array.prototype.forEach.call(row.querySelectorAll('a'), function(x){ x.classList.toggle('on', x === a); });
    var cat = a.getAttribute('data-cat');
    Array.prototype.forEach.call(document.querySelectorAll('#v-notes .note'), function(n){
      var cs = (n.getAttribute('data-cat') || '').split(',');
      n.style.display = (!cat || cs.indexOf(cat) >= 0) ? '' : 'none';
    });
  });
})();


  /* ★数据统计子分区（站主 2026-10-17「一屏装不下」）：
     运行期把这个面板的顶层卡片按 4 组搬进各自的 .sst-pane，只切显示、不动取数。
     分组不变式：顶层 7 个块 —— 7×24(0) / grid32 来源与故事(1) / 封禁榜(2) /
     来源分布(3) / 接口健康(4) / 部署(5) / 处置动作(6)。数量不对就整段跳过（宁可不拆，不许拆错）。 */
  (function(){
   function boot(){
    var pane = document.querySelector('.ops-tab[data-pane="stats"]'); if(!pane) return;
    if(pane.querySelector('.sst-nav')) return;                 /* 已经拆过 */
    var kids = [].slice.call(pane.children);
    if(kids.length !== 7) return;                              /* 结构变了：不硬拆 */
    var GROUPS = [['ov','概览',[0,3,1]],
                  ['act','处置留痕',[2,6]],['sys','部署与接口',[4,5]]];
    var nav = document.createElement('nav');
    nav.className='sst-nav'; nav.id='sstNav'; nav.setAttribute('role','tablist');
    nav.setAttribute('aria-label','数据统计分区');
    var panes = [], btns = [];
    GROUPS.forEach(function(g, n){
      var b=document.createElement('button');
      b.type='button'; b.setAttribute('data-sst', g[0]); b.setAttribute('role','tab');
      b.textContent=g[1]; if(n===0) b.className='on';
      b.setAttribute('aria-selected', n===0?'true':'false');
      nav.appendChild(b); btns.push(b);
      var p=document.createElement('div');
      p.className='sst-pane'+(n===0?' on':''); p.setAttribute('data-sst', g[0]);
      g[2].forEach(function(x){ if(kids[x]) p.appendChild(kids[x]); });
      panes.push(p);
    });
    /* 子导航搬到顶栏那一行（紧跟在「数据统计」右边）—— 站主口径：「放到上面那栏，正好空了挺多地方」。
       只在「数据统计」亮着时显示，所以别的 tab 下这一行还是原来那四个按钮。 */
    var host = document.getElementById('opsTabs');
    if(host && host.parentNode){ host.parentNode.insertBefore(nav, host.nextSibling); }
    else { pane.insertBefore(nav, pane.firstChild); }
    panes.forEach(function(p){ pane.appendChild(p); });
    function syncVis(){
      var on = pane.classList.contains('on');
      nav.style.display = on ? '' : 'none';
      /* 显示子导航时把 tabs 的 auto 外边距收掉：否则 auto 会把剩余空白全吃掉，
         子导航被挤到第二行（站主要的是"放到上面那栏"）。 */
      if(host){ host.style.marginLeft = on ? '0' : ''; host.style.marginRight = on ? '0' : ''; }
    }
    try{ new MutationObserver(syncVis).observe(pane, {attributes:true, attributeFilter:['class']}); }catch(e){}
    syncVis();
    function pick(name){
      var ok=false;
      btns.forEach(function(b){ var on=b.getAttribute('data-sst')===name;
        b.classList.toggle('on',on); b.setAttribute('aria-selected', on?'true':'false'); if(on) ok=true; });
      panes.forEach(function(p){ p.classList.toggle('on', p.getAttribute('data-sst')===name); });
      if(!ok && btns[0]) pick('ov');
    }
    nav.addEventListener('click', function(e){
      var b=e.target.closest('button'); if(!b) return; pick(b.getAttribute('data-sst'));
    });
    pick('ov');
   }
   if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  })();


