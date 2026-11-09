/* xk-home-fx.js -- 首页语音库 / 表情联动（XKM）/ 场景轮换（2026-11-09 从 layouts/index.html 内联脚本原样抽出，纯 JS 无模板变量）。 */
/* ================= 桐莉栖语音（L1 预渲染语音库 · 真实播放） =================
   ★2026-10-15 接手批：这一段是**新接的**。原 demo 主页只会打字幕，从不播音频。
   资产：static/kurisu/voice/bank.json（12 条日语 m4a，逐条带 text / seconds / 包络）。
   纪律：手势前不播（只记 pending）；取不到就只显示字幕，绝不假装在播；RM 不自动播。 */
const XK_VOICE_BANK = '/kurisu/voice/bank.json';
const XK_DEFAULT_SAY = '数字取不到就写读不到；点任意数字回到那条原始告警。';
const XKV = { bank:null, unlocked:false, pending:null, lastId:null, audio:null, plays:0, errors:[] };
window.__xkVoice = XKV;
/* ★批次A（2026-10-16 站主）：声音开关默认关 ⇒ 没开声就只记 pending + 只出字幕，开了再补播。
   开关本体在左上角头像卡（layouts/partials/xk-demo/idcard.html），状态存 localStorage['xk-sound-on']。 */
function xkSoundOn(){ try{ return !!(window.__xkSound && window.__xkSound.on); }catch(e){ return false; } }
/* 固定台词表（口语版）由头像卡那份 partial 提供（同一份文案，五页共用）：
   window.__xkLineZh = {lineId: '中文台词'}；没有就退回 bank.json 里的 text。 */
function xkvText(id, fallback){
  var m = window.__xkLineZh || {};
  return m[id] || fallback || '';
}
function xkvLine(id){ return (XKV.bank && XKV.bank.lines && XKV.bank.lines[id]) || null; }
function xkvLoad(){
  if(XKV.bank) return Promise.resolve(XKV.bank);
  /* ★慢网减量（2026-10-16）：原来这里是 `cache:'no-store'` —— 它会让 idcard 的 **prefetch 白费**
     并强制每次都整份重下 37KB（真机实测：bank.json 被下两次 = 11.8s + 10.8s，链路只有 3~6KB/s）。
     改 `no-cache`：仍然**每次都向源站再验证**（不会拿到过期的 bank），但命中就只回 304（几百字节），
     且能复用 prefetch 已经落到 HTTP 缓存的响应体 ⇒ 不再有第二次 37KB 下载。 */
  return fetch(XK_VOICE_BANK, {cache:'no-cache'}).then(r=>{
    if(!r.ok) throw new Error('bank HTTP '+r.status); return r.json();
  }).then(b=>{ XKV.bank = b; return b; }).catch(e=>{ XKV.errors.push('bank: '+e); return null; });
}
function xkvUnlock(){
  if(XKV.unlocked) return;
  XKV.unlocked = true;
  if(XKV.pending){ const id = XKV.pending; XKV.pending = null; xkvPlay(id); }
}
function xkvPlay(id){
  const line = xkvLine(id);
  if(!line){ XKV.errors.push('no line: '+id); return; }
  if(!xkSoundOn()){ XKV.pending = id; if(typeof typeSub === 'function') typeSub(xkvText(id, line.text)); return; }   /* ★批次A：声音关着 ⇒ 只出字幕 */
  if(!XKV.unlocked){ XKV.pending = id; if(typeof typeSub === 'function') typeSub(xkvText(id, line.text)); return; }        /* 手势前：只记 pending，不播 */
  /* ★批次A-P1（站主 2026-10-16）：**音频一律交给统一播放器** `KurisuPlayer.speakGroup`
     （选句 / 防复读 / 包络 / 口型只有那一处实现；这份简化的内联播放器不再自己 new Audio）。
     字幕与画布动画钩子仍由这一段负责（文案取共享的 xkvText）；统一播放器取不到才退回下面的本地实现。 */
  if(window.KurisuPlayer && typeof window.KurisuPlayer.speakGroup === 'function'){
    const _grp = (window.__xkLineGroup || {})[id] || 'greeting';
    if(typeof typeSub === 'function') typeSub(xkvText(id, line.text));
    if(typeof xkVoiceAnim === 'function'){ xkVoiceAnim(id); }
    XKV.lastId = id;
    KurisuPlayer.speakGroup(_grp, {preferId:id}).then(r=>{
      if(r && r.ok){ XKV.plays++; } else { XKV.errors.push('speakGroup: ' + ((r && r.reason) || '?')); }
      if(typeof xkVoiceEnd === 'function'){ xkVoiceEnd(); }
    }, e=>{ XKV.errors.push('speakGroup: ' + e); if(typeof xkVoiceEnd === 'function'){ xkVoiceEnd(); } });
    return;
  }
  if(XKV.lastId === id && XKV.audio && !XKV.audio.paused) return;
  try{
    if(XKV.audio){ try{ XKV.audio.pause(); }catch(_){} }
    const a = new Audio('/' + String(line.audio).replace(/^\/+/, ''));
    a.preload = 'auto';
    XKV.audio = a; XKV.lastId = id;
    a.addEventListener('playing', ()=>{
      XKV.plays++;
      /* 语音 → 动画联动（★2026-10-15 新接）：她在说话时切到 speaking 剪辑。
         图集没载完就先不切（drawFrame 对未载完的图直接 return，画布保留上一帧，不会闪白/卡死）。 */
      if(typeof xkVoiceAnim === 'function'){ xkVoiceAnim(id); return; }
      if(typeof play === 'function' && cur !== 'opening'){
        const sim = img(CLIPS.speaking.src);
        if(sim.complete && sim.naturalWidth){ play('speaking'); }
        else { sim.addEventListener('load', ()=>{ if(!XKV.audio || !XKV.audio.paused) play('speaking'); }, {once:true}); }
      }
    });
    a.addEventListener('error', ()=>{ XKV.errors.push('audio: '+id); });
    a.addEventListener('ended', ()=>{
      if(typeof xkVoiceEnd === 'function'){ xkVoiceEnd(); }
      else if(typeof play === 'function'){ play('idle'); }
      if(typeof typeSub === 'function') typeSub(XK_DEFAULT_SAY);
    });
    const pr = a.play();
    if(pr && pr.catch){ pr.catch(err=>{ XKV.errors.push('play: '+(err && err.name)); }); }
    if(typeof typeSub === 'function') typeSub(xkvText(id, line.text));
  }catch(e){ XKV.errors.push('audio ctor: '+e); }
}
/* ★批次A（站主追加①）：主页进入**固定一句问候** —— 首访 greet_first / 回访 greet_back；
   不随机、不参与"防复读"轮换（台账口径见 docs/台词表-入口与固定台词-20261016.md）。 */
function xkvGreet(){
  /* ★2026-10-22 省流量：声音默认关时**连语音库都不取**（原来无条件 xkvLoad()，
     首页每访客白拉 145 KB 的 voice/bank.json，而 xkvPlay 里面反正只会出字幕）。
     开关打开时由 xk-sound 监听走 xkvLoad() 补播（见下面那段）。 */
  if(!xkSoundOn()){ XKV.entryId = (function(){ try{ return localStorage.getItem('xk-visited') ? 'greet_welcome_back' : 'greet_welcome'; }catch(_){ return 'greet_welcome'; } })(); return; }
  xkvLoad().then(()=>{
    let seen = false;
    try{ seen = !!localStorage.getItem('xk-visited'); localStorage.setItem('xk-visited','1'); }catch(_){}
    /* ★2026-10-16 站主新口径：主页问候换成"欢迎使用 Amadeus 系统"那两句
       （`greet_welcome` 首访 / `greet_welcome_back` 回访）。**旧的两句保留在库里作兜底**：
       新句子若在 bank 里取不到（例如合并索引未更新），仍用旧的 ⇒ 保证"一定有声音，
       且字幕与音频是同一句"（绝不让新字幕配旧音频）。 */
    const wantNew = seen ? 'greet_welcome_back' : 'greet_welcome';
    const legacy  = seen ? 'greet_welcome_back' : 'greet_welcome';   /* greet_first/back 已于 rev7 下线 */
    const id = xkvLine(wantNew) ? wantNew : legacy;
    XKV.entryId = id;
    xkvPlay(id);
  });
}
/* ★批次A：声音开关打开的那一刻，把刚才因为"声音关着"压下来的那一句补播（同一句，不换文案）。
   ★2026-10-19 站主：关掉那一刻要**立刻静音**（含本页内联播放器自己的 Audio 兜底路径）并把 pending 丢掉。 */
addEventListener('xk-sound', function(ev){
  const on = !!(ev && ev.detail && ev.detail.on);
  if(on){ if(XKV.pending){ const id = XKV.pending; XKV.pending = null; xkvPlay(id); } return; }
  XKV.pending = null;
  if(XKV.audio){ try{ XKV.audio.pause(); }catch(_){} try{ XKV.audio.currentTime = 0; }catch(_){} }
});
addEventListener('pointerdown', xkvUnlock, {once:true});
addEventListener('keydown', xkvUnlock, {once:true});
/* 语音库在首屏窗口（门禁口径 1.5s）**之后**才取 —— 语音资产不进首屏字节 */
/* ★2026-10-22 省流量：原来是 `setTimeout(xkvLoad, 1800)` —— 声音默认关也照样把 145 KB 的
   voice/bank.json 拉下来（xkvPlay 里面反正只出字幕）。改成开声才取；
   开声那一刻由 xk-sound 监听走 xkvLoad() 补播（见下面 XKV 那段）。 */
setTimeout(function(){ if(xkSoundOn()) xkvLoad(); }, 1800);
if(!RM){ setTimeout(xkvGreet, 2600); }
let xkvHiddenAt = 0;
document.addEventListener('visibilitychange', ()=>{
  if(document.hidden){ xkvHiddenAt = Date.now(); }
  else if(xkvHiddenAt && (Date.now() - xkvHiddenAt) > 60000){ xkvHiddenAt = 0; xkvPlay('tab_return'); }
});


/* ================= 桐莉栖：全身表情 / 更多动画（L2 懒加载 · 零首屏影响） =================
   ★2026-10-15 接手批：把 medium 档 38 段全身剪辑里的"表情段"接到这块画布上。
   表情条的 8 个点与内容页外壳的 #emos 一一对应（同一套情绪命名，见 static/kurisu/manifest.json
   的 emotions 与 avatar/ 素材）。语音说话时若没有手选表情，会按语音场景自动切表情。 */
var XK_ACT = null;                     /* 非空 = 表情模式接管画布（loop / drawFrame 读它） */
var XK_EMO_LIST = [
  /* [情绪, 标签, 点色, 循环段, 进入过渡段] —— 过渡段就是状态机 host_triggered_entries 里的
     angry_trans / sad_trans / shy_trans / surprise_trans / trans_smile / thinking_trans，
     它们本来就是"进这个表情"的入场动画（0.48–0.96s，once_then_hold），播完自动接循环段
     —— 所以表情切换是"演出来"的，不是硬切。 */
  ['normal',          '普通', '#7cc4e8', 'idle',               ''],
  ['happy',           '开心', '#f2c14e', 'smile_speaking',     'trans_smile'],
  ['sided_thinking',  '思考', '#9a8cff', 'thinking_speaking1', 'thinking_trans'],
  ['sided_surprised', '惊讶', '#e88fd0', 'surprise_speaking',  'surprise_trans'],
  ['sad',             '难过', '#6b7f96', 'sad_speaking',       'sad_trans'],
  ['blush',           '害羞', '#f0997b', 'shy_speaking1',      'shy_trans'],
  ['angry',           '生气', '#e8654e', 'angry_speaking',     'angry_trans'],
  ['disappointed',    '失望', '#8a94a6', '',                   'thinking_to_serious']
];
/* 语音 id → 表情（只影响"没手选表情时"的自动切换；表里没有的 id 走默认 speaking） */
var XK_VOICE_EMO = {
  greet_first:'happy', greet_back:'happy', tab_return:'happy',
  nav_home:'normal', nav_monitor:'sided_thinking', nav_notes:'normal', nav_ai:'sided_thinking', nav_what:'normal', nav_lab:'sided_thinking', nav_what:'normal', nav_lab:'sided_thinking',
  fallback_no_data:'disappointed', fallback_offline:'disappointed', fallback_throttled:'sad'
};
var XKM = { clips:null, loading:null, imgs:{}, emo:'normal', clip:null,
            fi:0, acc:0, hold:0, last:0, done:false, next:null, manual:false, err:[] };
window.__xkEmo = { emotion:'normal', clip:null, frames:0, ok:false, errors:XKM.err };

function xkmImg(u){
  if(!XKM.imgs[u]){ var im = new Image(); im.decoding = 'async'; im.src = u; XKM.imgs[u] = im; }
  return XKM.imgs[u];
}
function xkmUrl(p){ return '/' + String(p.url).replace(/^\/+/, ''); }
function xkmLoad(){
  if(XKM.clips) return Promise.resolve(XKM.clips);
  if(XKM.loading) return XKM.loading;
  XKM.loading = fetch('/kurisu/manifest.json', {cache:'force-cache'}).then(function(r){
    if(!r.ok) throw new Error('manifest HTTP ' + r.status);
    return r.json();
  }).then(function(j){
    XKM.clips = (j && j.clipsMedium && j.clipsMedium.clips) || null;
    window.__xkEmo.ok = !!XKM.clips;
    return XKM.clips;
  }).catch(function(e){ XKM.err.push('manifest: ' + e); window.__xkEmo.ok = false; return null; });
  return XKM.loading;
}
function xkmFrameAt(clip, f){          /* f: 0-based（已含 reverse）；返回该帧落在哪一页 + 页内偏移 */
  var pages = clip.atlas.medium.pages, i, p, local;
  for(i = 0; i < pages.length; i++){
    p = pages[i];
    local = (f + 1) - p.first_frame;   /* manifest 的 first_frame 是 1-based */
    if(local >= 0 && local < p.frames) return {p:p, local:local};
  }
  return null;
}
function xkmPaint(){
  var clip = XKM.clip;
  if(!clip || !XK_ACT) return;
  var f = clip.reverse ? (clip.frames - 1 - XKM.fi) : XKM.fi;
  var at = xkmFrameAt(clip, f);
  if(!at) return;
  var im = xkmImg(xkmUrl(at.p));
  if(!im.complete || !im.naturalWidth) return;
  var tw = at.p.tile_w, th = at.p.tile_h;
  var sx = (at.local % at.p.cols) * tw, sy = Math.floor(at.local / at.p.cols) * th;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  var w = bounds.w * (canvas.width / bounds.w), h = bounds.h * (canvas.height / bounds.h);
  var s = Math.min(w * CHAR_BOX.maxW / CHAR_BOX.w, h * CHAR_BOX.maxH / CHAR_BOX.h);
  var dh = CHAR_BOX.h * s, dw = dh * (tw / th);   /* 宽按素材自身比例，避免不同 tile 被拉变形 */
  var x = w * CHAR_BOX.xRatio, y = h - Math.max(3, h * CHAR_BOX.footRatio);
  ctx.drawImage(im, sx, sy, tw, th, x - dw / 2, y - dh, dw, dh);
}
function xkmTick(t){
  if(!XK_ACT || !XKM.clip) return;
  if(!XKM.last){ XKM.last = t; return; }
  var dt = t - XKM.last; XKM.last = t;
  if(dt > 200) dt = 200;                 /* 切标签页回来别一次跳几百帧 */
  if(XKM.done){                          /* once_then_hold 播完：停住 2.8s 再回普通 */
    XKM.hold += dt;
    if(XKM.hold > 2800){ XKM.done = false; xkmSetEmotion('normal'); }
    return;
  }
  var clip = XKM.clip, iv = Math.max(4, clip.frameIntervalMs || 42);
  XKM.acc += dt;
  if(XKM.acc >= iv){
    /* ★必须按 manifest 的 frameIntervalMs 算"这一跳该走几帧"：
       medium 档过渡段是 5–8ms/帧（200fps 级别），一次 rAF 只走一帧的话
       会慢到 ~5 倍（trans_smile 从 0.60s 变成 2.88s，肉眼就是"卡住不动"）。 */
    var adv = Math.floor(XKM.acc / iv);
    XKM.acc -= adv * iv;
    XKM.fi += adv;
    if(XKM.fi >= clip.frames){
      if(clip.loopMode === 'loop'){ XKM.fi = XKM.fi % clip.frames; }
      else if(XKM.next){ var nx = XKM.next; XKM.next = null; xkmPlayClip(nx, null); return; }  /* 入场过渡播完 → 接循环段 */
      else { XKM.fi = clip.frames - 1; XKM.done = true; XKM.hold = 0; }
    }
  }
  xkmPaint();
}
function xkmPlayClip(name, next){        /* 真正上屏：取图集 → 接管画布；next = 这一段播完接哪一段 */
  xkmLoad().then(function(clips){
    if(!clips){ XKM.err.push('无 clipsMedium'); return; }
    var clip = clips[name];
    if(!clip){ XKM.err.push('缺剪辑: ' + name); return; }
    var pages = clip.atlas.medium.pages, k;
    for(k = 0; k < pages.length; k++){
      var im = xkmImg(xkmUrl(pages[k]));
      if(!im.complete){
        im.addEventListener('load', function(){ if(XK_ACT) xkmPaint(); }, {once:true});
      }
    }
    XKM.clip = clip; XKM.fi = 0; XKM.acc = 0; XKM.hold = 0; XKM.last = 0; XKM.done = false;
    XKM.next = next || null;
    XK_ACT = {name: name, emo: XKM.emo};
    window.__xkEmo.clip = name; window.__xkEmo.frames = clip.frames;
    xkmPaint();
  });
}
function xkmSetEmotion(name){
  var item = null, i;
  for(i = 0; i < XK_EMO_LIST.length; i++){ if(XK_EMO_LIST[i][0] === name){ item = XK_EMO_LIST[i]; } }
  if(!item) return false;
  XKM.emo = name; window.__xkEmo.emotion = name;
  /* ★2026-10-15：表情可能在开场还没播完时接管画布（语音自动切表情就会）——
     这时 loop() 不再走 opening 那一支，showHud() 就永远不会被调 → 状态行 / 字幕 / 表情条
     一个都不出现。所以这里补一次"开场被打断也要出 HUD"。 */
  if(cur === 'opening' && typeof showHud === 'function') showHud();
  if(name === 'normal'){                 /* "普通" = 交回 hi 档 idle */
    XK_ACT = null; XKM.clip = null; XKM.fi = 0; XKM.done = false; XKM.last = 0; XKM.next = null;
    window.__xkEmo.clip = null; window.__xkEmo.frames = 0;
    if(typeof play === 'function' && !document.hidden) play('idle');
    return true;
  }
  /* 先播入场过渡段（演出来），过渡播完自动接循环段；没有循环段就停在过渡末帧（如"失望"） */
  if(item[4]){ xkmPlayClip(item[4], item[3] || null); }
  else { xkmPlayClip(item[3], null); }
  return true;
}
/* 语音联动（HOME_VOICE 的两处 handler 会调这两个）：手选表情时不抢画布 */
function xkVoiceAnim(id){
  if(XK_ACT) return;
  var auto = XK_VOICE_EMO[id];
  if(auto && auto !== 'normal' && !XKM.manual){ xkmSetEmotion(auto); return; }
  if(typeof play !== 'function' || cur === 'opening') return;
  var sim = img(CLIPS.speaking.src);
  if(sim.complete && sim.naturalWidth){ play('speaking'); }
  else { sim.addEventListener('load', function(){ if(!XKV.audio || !XKV.audio.paused) play('speaking'); }, {once:true}); }
}
function xkVoiceEnd(){
  if(!XK_ACT && typeof play === 'function') play('idle');
}
/* manifest 在首屏门禁 1.5s 窗口之后才取 —— 表情资产绝不进首屏字节 */
if(!RM){ setTimeout(xkmLoad, 2000); }

/* ================= ★场景机（站主：主页电视里她的随机动作）=================
   她"住在电视里"：节目在两种画面间随机轮换 ——
     A 模式：空实验室 + Sprite 状态机的她（动态）；
     B 模式：6 张场景静帧之一（图里她已经在做那件事 ⇒ 把她淡出，避免两个她）。
   dwell 默认 45~60s 随机、交叉淡入 600ms；旋钮 ?xk-scene=<ms> 加速、?xk-scene=off 关闭；
   ?xk-sm=off / ?xk-no-kurisu=1 / prefers-reduced-motion / document.hidden 下不演（只留 A 或留 backplate）。
   诊断口径：window.__xkScene = {on, mode, cur, dwellMs, switches[{at,to,why}], pB, setMode()} */
(function(){
  var q = location.search || '';
  if(/[?&]xk-scene=off/.test(q) || /[?&]xk-sm=off/.test(q) || window.__xkNoKurisu === true) return;
  if(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var A = document.getElementById('xkSceneA'), B = document.getElementById('xkSceneB');
  var clip = document.getElementById('crtClip');
  if(!A || !B || !clip) return;
  var m = q.match(/[?&]xk-scene=(\d+)/);
  var dwell = m ? Math.max(1500, parseInt(m[1], 10)) : 45000 + Math.round(Math.random() * 15000);
  var BASE = '/kurisu/scene/bg/screen_', VQ = '?v=20261109a';   /* ★2026-11-09：/kurisu/* 是 30 天缓存，换内容必须换 URL */
  var ACT = ['coffee','computer','crt','sleep','thinking','whiteboard'];
  var V = {on:true, mode:'A', cur:'empty', dwellMs:dwell, switches:[], pB:0.4};
  window.__xkScene = V;
  var front = A, back = B, timer = null;
  function show(img, name){ img.src = BASE + name + '.webp' + VQ; img.classList.add('on'); }
  show(front, 'empty');
  function setMode(mode, name, why){
    if(mode === V.mode && name === V.cur) return;
    V.mode = mode; V.cur = name;
    show(back, name);
    setTimeout(function(){
      if(V.cur !== name) return;                 /* 期间又切了 ⇒ 作废这次换层 */
      front.classList.remove('on');
      var t = front; front = back; back = t;
      clip.classList.toggle('xk-scene-b', V.mode === 'B');
    }, 620);
    V.switches.push({ at: Math.round(performance.now()), to: name, why: why });
    if(V.switches.length > 20) V.switches.shift();
  }
  function pick(){
    if(V.mode === 'B' || Math.random() < V.pB){
      var n = ACT[Math.floor(Math.random() * ACT.length)];
      if(n === V.cur) n = ACT[(ACT.indexOf(n) + 1) % ACT.length];
      setMode('B', n, 'dwell');
    } else {
      setMode('A', 'empty', 'dwell');
    }
  }
  function arm(){ if(timer) clearTimeout(timer); timer = setTimeout(function(){ pick(); arm(); }, dwell); }
  document.addEventListener('visibilitychange', function(){
    if(document.hidden){ if(timer){ clearTimeout(timer); timer = null; } } else if(!timer){ arm(); }
  });
  /* ★2026-10-16 修（主窗口验收发现的真问题）：**开场期间不切场景**。
     根因：T31 开场六阶段用**内联 `style.opacity`** 控制 `#charCanvas`（优先级高于类级规则
     `.crt-clip.xk-scene-b .charcanvas{opacity:0}`）⇒ 开场期间进 B 模式"淡不出她"，
     且首切发生在 2.6s（开场还没走完）⇒ 观感是"大头特写里夹一张静帧"。
     判据（用既有钩子，不新造计时器）：生成器自己的口径是"主页要等**开场落定（showHud 里调 takeOver）**"
     ⇒ `__xkSM.stats().tookOver === true` 即开场结束；置位同时把开场写的内联 opacity 摘掉（交还给 CSS）。
     兜底：15s 内始终没落定（例如 statemachine.json 取不到、SM 未接管）也照常启动，避免永不轮换。 */
  var started = false;
  function openingDone(){
    try{ var s = window.__xkSM && window.__xkSM.stats && window.__xkSM.stats(); return !!(s && s.tookOver); }catch(e){ return false; }
  }
  function startWhenOpeningDone(){
    if(started) return;
    started = true;
    try{ var c = document.getElementById('charCanvas'); if(c) c.style.removeProperty('opacity'); }catch(e){}
    V.startedAt = Math.round(performance.now());
    arm();
  }
  if(openingDone()){ startWhenOpeningDone(); }
  else {
    var iv = setInterval(function(){ if(openingDone()){ clearInterval(iv); startWhenOpeningDone(); } }, 300);
    setTimeout(function(){ clearInterval(iv); startWhenOpeningDone(); }, 15000);
  }
  V.setMode = function(mode, name){ setMode(mode || 'A', name || 'empty', 'manual'); };
})();
