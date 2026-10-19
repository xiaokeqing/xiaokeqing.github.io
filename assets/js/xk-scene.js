
(()=>{

/* ================= 数据：全部来自 static/kurisu/manifest.json ================= */
const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
const CLIPS = {
  opening:  {src:'/kurisu/full/opening.hi.webp',  frames:84, interval:33.33, cols:8, cw:380, ch:290, fit:'screen',  next:'idle', bootSrc:'/kurisu/full/opening.boot.webp',  bootFrames:24, vid:'opening'},
  idle:     {src:'/kurisu/full/idle.hi.webp',     frames:60, interval:42,    cols:8, cw:476, ch:640, fit:'anchor', bootSrc:'/kurisu/full/idle.boot.webp',     bootFrames:24, vid:'idle'},
  speaking: {src:'/kurisu/full/speaking.hi.webp', frames:45, interval:68,    cols:8, cw:476, ch:640, fit:'anchor', bootSrc:'/kurisu/full/speaking.boot.webp', bootFrames:24, vid:'speaking_long'},
  thinking: {src:'/kurisu/full/thinking.hi.webp', frames:45, interval:68,    cols:8, cw:476, ch:640, fit:'anchor', bootSrc:'/kurisu/full/thinking.boot.webp', bootFrames:24, vid:'thinking_to_key_point'}
};
/* 角色落位（scene.character 源码公式）：scale=min(w*0.64/764,h*0.90/1028), x=0.52w, y=bottom-h*0.012, anchor=(0.5,1) */
const CHAR_BOX = {w:764, h:1028, maxW:0.64, maxH:0.90, xRatio:0.52, footRatio:0.012};

const stage = document.getElementById('stage');
const crt = document.getElementById('crt');
const canvas = document.getElementById('charCanvas');
const ctx = canvas.getContext('2d');
const cache = {};
function img(src){ if(!cache[src]){ const im=new Image(); im.src=src; cache[src]=im; } return cache[src]; }

let cur = null, acc = 0, fi = 0, lastT = 0, started = false;
let bounds = {w:0, h:0};

function resize(){
  const r = crt.getBoundingClientRect();
  const dpr = Math.min(devicePixelRatio || 1, 2);
  bounds = {w:r.width, h:r.height};
  canvas.width  = Math.round(r.width  * dpr);
  canvas.height = Math.round(r.height * dpr);
  /* 桌面实拍照常驻、CRT 完整可见的硬不变量：CRT 高度 <260px 触发降级 */
  const fb = document.getElementById('fallback');   /* ★第十二批：五个内容页没有 #fallback，
      demo 这里直接 .style 会抛 TypeError 让整个 IIFE 中止 —— 加存在性判断，行为不变 */
  /* ★2026-10-15 T1：桌面窄窗才降级；触屏（手机/平板）一律播动画，只是更小。视觉不变 */
  if(fb) fb.style.display = (r.height < 260 && !matchMedia('(pointer: coarse)').matches) ? 'grid' : 'none';
}


/* ================================================================================
   桐莉栖 · 视频渲染层（T7）—— 用 9.54MB 透明 WebM 替代 71MB PNG 图集
   --------------------------------------------------------------------------------
   它只做一件事：drawFrame() 想画角色时，先问它"这一帧你出得来吗"。
     出得来 → 它接手（画 <video> 的第 frameIndex 帧；缺帧先画 poster；两者都没有才让图集继续顶）；
     出不来 → 返回 false，页面照原样画图集(boot→hi)。
   ⇒ pixel 档 = 本模块整体不启用 = **逐像素等于接线前**；video 档失败也自动退回图集。

   硬纪律（每条都有实测/规格出处，别改）：
     · <video> 不进 DOM、muted、playsinline —— 避免任何样式/层叠/声音影响 ✗
     · 同时存活 ≤4 枚 video + LRU；同一个剪辑用 1 枚（逐帧 seek 用两枚交替会打乱帧序 ✗）
      偏离说明：接线方案 §4.2 写的是"两枚 video 交替"以避免 seek 白屏 —— 但本实现走的是
      **逐帧 seek 定位**（video 第 i 帧 == 图集第 i 帧），两枚交替没有意义（同剪辑两枚各自 seek，
      拿到的帧还会互相打架）。防白屏改用"poster 先顶位 + 解好的帧搬进离屏 canvas"，
      效果等价且帧序确定 —— 这条偏离记在 docs/状态-C-站点角色.md 里。
     · 逐帧对齐：video 第 i 帧 == 图集第 i 帧，单帧时长取 statemachine 的 frameIntervalMs
       （容器是 60fps 编的，**durationMs 不是帧间隔** ✗）—— 见 _shots/video-align.json
     · 首次手势前不预载视频 ✗（只按需取"当前该上屏的那一枚"）；手势后预载 manifest.preload
     · saveData / slow-2g / reduced-motion / 低端机 / 不支持 VP9 的 Safari ⇒ 不取视频（走图集）
     · 解码失败/404 ⇒ 该剪辑**永久降级**（不再重试 ✗）；连续 2 个剪辑解不出 alpha ⇒ 整站回 pixel
     · 零第三方请求：清单与素材都在本站 /kurisu/ 下
   诊断口径：window.__xkVid = V（验收脚本读 V.mode / V.drawn / V.failed / V.probe / V.errors）
   ================================================================================ */
var XKV2_BLOCK = (function(){
  var V = {
    mode:null, reason:null, auto:null, cfg:null,
    enabled:false, videoOK:false, disp:false, manifest:null, mfState:0, mfP:null,
    preload:'', gesture:false, cur:null,
    decoded:{}, failed:{}, errors:[], alive:0, clock:0, free:[],
    drawn:0, fallbackDrawn:0, released:0, alphaFail:0, probe:null,
    /* ★P0-①（2026-10-16）：alpha 采样从"整场只采第一枚"扩到"**每次切剪辑都采一次**" ——
       iOS 上"声明支持 VP9 但解不出 alpha"是半途才暴露的（批次 B §10.3 第 2 条），
       只采一次会漏掉后上场的剪辑。历史留在 probes[]，最近一次仍在 probe（老口径兼容）。 */
    probeClip:null, probes:[]
  };
  window.__xkVid = V;

  var Firefox = /Firefox\//.test(navigator.userAgent || '');
  var Chrome  = /Chrome\//.test(navigator.userAgent || '');
  var Safari  = !Chrome && /Safari\//.test(navigator.userAgent || '');

  function uaOf(){
    var u = navigator.userAgent || '';
    if(/iPhone|iPad|iPod/i.test(u) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) return 'ios';
    if(Firefox) return 'firefox';
    if(Chrome) return 'chromium';
    if(Safari) return 'safari';
    return 'unknown';
  }
  function core(){                       /* 总开关：?xk-kurisu-mode= > localStorage > <html data-...> */
    var m = null, s = location.search;
    var q = s.match(/[?&]xk-kurisu-mode=(video|pixel|off)/i);
    if(q) m = q[1].toLowerCase();
    if(!m){ try{ var ls = localStorage.getItem('xk-kurisu-mode'); if(ls) m = String(ls).toLowerCase(); }catch(e){} }
    if(!m){ var a = document.documentElement.getAttribute('data-xk-kurisu-mode'); if(a) m = String(a).toLowerCase(); }
    if(m === 'auto' || m === '1' || m === 'true') m = 'video';
    if(m !== 'video' && m !== 'pixel' && m !== 'off') m = 'video';
    return m;
  }
  V.cfg = {
    rm: !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches),
    saveData: !!(navigator.connection && navigator.connection.saveData),
    slowNet: !!(navigator.connection && /(^|-)2g$/.test(navigator.connection.effectiveType || '')),
    lowMem: (typeof navigator.deviceMemory === 'number' && navigator.deviceMemory <= 4),
    small: !!(window.matchMedia && matchMedia('(max-width: 979px)').matches),
    canPlay: !!(document.createElement('video').canPlayType('video/webm; codecs="vp9"')),
    mseVP9: !!(typeof MediaSource !== 'undefined' && MediaSource.isTypeSupported && MediaSource.isTypeSupported('video/webm; codecs="vp9"')),
    ua: uaOf()
  };
  var c = V.cfg;
  V.auto = (c.rm || c.saveData || c.slowNet || c.lowMem || (!c.canPlay && !c.mseVP9));
  V.mode = core();
  if(V.mode === 'off'){
    V.reason = '开关 off（角色层不加载）';
  }else if(V.mode === 'pixel'){
    V.reason = '开关 pixel（保持接线前的图集行为）';
  }else if(V.auto){
    V.mode = 'pixel';
    V.reason = 'auto 降级：' + [c.rm ? 'reduced-motion' : '', c.saveData ? 'saveData' : '',
      c.slowNet ? '2g' : '', c.lowMem ? 'deviceMemory<=4' : '',
      ((!c.canPlay && !c.mseVP9) ? ('无 VP9-alpha（' + c.ua + '）') : '')].filter(Boolean).join(' + ');
  }else{
    V.mode = 'poster';                   /* 先 poster 顶位，清单到位后升到 video（不留空框 ✗） */
    V.disp = true;
    V.reason = 'auto 通过（' + c.ua + '，VP9 声明可用）';
  }
  V.videoOK = (V.mode === 'poster' || V.mode === 'video');
  V.enabled = (V.mode !== 'off' && V.mode !== 'pixel');

  function clean(u){ return '/' + String(u).replace(/^\/+/, ''); }
  function posterUrl(n){ var m = V.manifest && V.manifest.clips && V.manifest.clips[n]; return m ? clean(m.poster) : ('/kurisu/video/' + n + '.poster.webp'); }
  function videoUrl(n){ var m = V.manifest && V.manifest.clips && V.manifest.clips[n]; return m ? clean(m.video) : ('/kurisu/video/' + n + '.webm'); }
  function clipOf(name, plan){
    /* 用图集侧那段配置反推剪辑名（/kurisu/full/opening.hi.webp → opening），
       这样"剪辑 ↔ 视频文件"永远与图集同源，不新增一处会漂的硬编码路径 ✓ */
    var v = null;
    if(plan && plan.vid) v = plan.vid;
    else if(plan && plan.src){ var mm = String(plan.src).match(/([A-Za-z0-9_]+)\.hi\.webp/); v = mm ? mm[1] : null; }
    if(v === 'speaking') v = 'speaking_long';          /* 原型 4 剪辑名 ↔ 状态机剪辑名 */
    if(v === 'thinking') v = 'thinking_to_key_point';
    return v;
  }
  function manifestLoad(){
    if(V.mfState === 2) return Promise.resolve(V.manifest);
    if(V.mfState === 1) return V.mfP;
    V.mfState = 1;
    V.mfP = fetch('/kurisu/video-manifest.json', {cache:'force-cache'}).then(function(r){
      if(!r.ok) throw new Error('manifest HTTP ' + r.status);
      return r.json();
    }).then(function(j){
      V.manifest = j; V.mfState = 2; V.preload = (j.preload || []).slice(0, 3).join(',');
      if(V.mode === 'poster') V.mode = 'video';        /* 清单到位 ⇒ 升到 video */
      return j;
    }).catch(function(e){
      V.mfState = 3; V.errors.push('manifest: ' + e);
      V.mode = 'pixel'; V.disp = false; V.videoOK = false; V.enabled = false;
      V.reason = '视频清单取不到（' + e.message + '）→ 回图集';
      return null;
    });
    return V.mfP;
  }
  /* ---- 逐帧 seek：video 第 i 帧 == 图集第 i 帧 ---- */
  function frameTime(c, i){
    var n = c.frames || 1, d = c.duration || 0;
    if(i < 0) i = 0;
    if(i > n - 1) i = n - 1;
    if(n <= 1 || !d) return 0;
    return Math.min(Math.max(0, i * d / n + d / (2 * n)), Math.max(0, d - 0.004));  /* 帧中心，避开边界抖 */
  }
  function seek(c, i){
    if(!c.ready) return;
    if(c.lastReq === i) return;
    c.lastReq = i;
    c.seq++;
    if(c.have === i || c.pending === i) return;        /* 已经是这一帧 / 正在等这一帧 */
    var t = frameTime(c, i), cur = c.vd.currentTime || 0;
    if(Math.abs(cur - t) < 0.0008){ c.pending = i; pump(c); return; }
    c.pending = i;
    try{ c.vd.currentTime = t; }
    catch(e){ c.err.push('seek: ' + e.message); fallback(c); return; }
    if(c.seekTimer) clearTimeout(c.seekTimer);
    c.seekTimer = setTimeout(function(){ c.err.push('seek timeout@' + i); fallback(c); }, 1500);
  }
  function pump(c){
    /* 把解好的那一帧搬进离屏 canvas（drawImage 每帧直接读 <video> 太贵 ⇒ 只搬一次） */
    if(!c.dcv || !c.vd || !c.vd.videoWidth) return;
    try{
      c.dcx.drawImage(c.vd, 0, 0, c.dcv.width, c.dcv.height);
      c.have = c.pending;
      c.pending = -1;
      if(c.seekTimer){ clearTimeout(c.seekTimer); c.seekTimer = 0; }
      /* ★P0-①：每次**切剪辑**都采一次（原来 !V.probe 只采整场第一枚 ⇒ 半途画错一帧查不到） */
      if(c.have >= 0 && V.probeClip !== c.name){ V.probeClip = c.name; probeAlpha(c); }
    }catch(e){ c.err.push('draw: ' + e.message); fallback(c); }
  }
  function fallback(c){
    c.bad = true;
    V.failed[c.name] = (c.err[c.err.length - 1] || 'unknown');
    release(c, true);
  }
  function release(c, hard){
    if(!c.act) return;
    c.act = false;
    V.released++;
    V.alive = Math.max(0, V.alive - 1);
    try{ c.vd.pause(); }catch(e){}
    if(hard){
      try{ c.vd.removeAttribute('src'); c.vd.load(); }catch(e){}
      if(c.bdcv){ c.bdcv.width = 1; c.bdcv.height = 1; }
    }
    V.free.push(c);
  }
  function lru(){
    if(V.alive < 4) return;
    var best = null, k;
    for(k in V.decoded){
      var c = V.decoded[k];
      if(!c.act || k === V.cur) continue;              /* 正在播的不动 */
      if(!best || c.used < best.used) best = c;
    }
    if(best) release(best, true);                      /* 腾不出就不腾，下一帧再判 */
  }
  function make(name){
    var vd = document.createElement('video');          /* ★绝不 appendChild：离屏、不进 DOM */
    vd.muted = true; vd.defaultMuted = true; vd.playsInline = true; vd.autoplay = false;
    vd.setAttribute('muted', ''); vd.setAttribute('playsinline', '');
    vd.preload = 'auto';
    var c = { name:name, vd:vd, act:false, ready:false, bad:false, seq:0, lastReq:-1, have:-1,
              pending:-1, used:0, frames:null, intervalMs:null, duration:0,
              pst:null, pdone:false, bdcv:null, dcx:null, dcv:null, seekTimer:0, err:[] };
    vd.addEventListener('loadedmetadata', function(){
      c.ready = true;
      c.duration = isFinite(vd.duration) ? vd.duration : 0;
      if(!c.bdcv){                                     /* 离屏缓冲：只搬一次，画的时候只做一次 drawImage */
        c.bdcv = document.createElement('canvas');
        c.bdcv.width = vd.videoWidth || 268;
        c.bdcv.height = vd.videoHeight || 360;
        c.dcx = c.bdcv.getContext('2d');
        c.dcv = c.bdcv;
      }
      c.lastReq = -1;
      pump(c);
    });
    vd.addEventListener('seeked', function(){ pump(c); });
    if(vd.requestVideoFrameCallback){
      try{ vd.requestVideoFrameCallback(function(){ pump(c); }); }catch(e){}
    }
    vd.addEventListener('error', function(){
      c.err.push('video error ' + (vd.error && vd.error.code));
      fallback(c);
    });
    var im = new Image(); im.decoding = 'async';
    im.addEventListener('load', function(){ c.pdone = true; });
    im.addEventListener('error', function(){ c.err.push('poster 404'); });
    im.src = posterUrl(name);
    c.pst = im;
    vd.src = videoUrl(name);
    return c;
  }
  function ensure(name){
    var c = V.decoded[name];
    if(c) return c;
    if(V.failed[name]) return null;                    /* 永久降级：不再重试 ✗ */
    lru();
    c = make(name);
    V.decoded[name] = c;
    c.act = true;
    c.used = ++V.clock;
    V.alive++;
    if(c.pst && c.pst.complete && c.pst.naturalWidth) c.pdone = true;
    return c;
  }
  function probeAlpha(c){
    /* 品红底法：透明像素画上去会留底色 ⇒ 读回来越接近纯品红 = alpha 越真。
       （同一方法素材自检时已用过，见总账 §2.3"浏览器实播…品红底 canvas"） */
    try{
      var t = document.createElement('canvas');
      t.width = 8; t.height = 8;
      var x = t.getContext('2d', { willReadFrequently: true });   /* ★C11：8×8 离屏回读 */
      x.fillStyle = 'rgb(255,0,255)';
      x.fillRect(0, 0, 8, 8);
      x.drawImage(c.bdcv, 0, 0, c.bdcv.width, c.bdcv.height, 0, 0, 8, 8);
      var d = x.getImageData(0, 0, 8, 8).data, n = 0, magenta = 0;
      for(var i = 0; i < d.length; i += 4){
        n++;
        if(d[i] > 235 && d[i + 1] < 55 && d[i + 2] > 235) magenta++;
      }
      var ratio = magenta / n;
      V.probe = { clip:c.name, magentaRatio:Math.round(ratio * 1000) / 1000, ok:ratio >= 0.06 };
      /* ★P0-①：历史（每次切剪辑一条）+ 真的"连续"两次才整站回 pixel（原来 alphaFail 不清零，
         采样本数一多就会把两次**不相邻**的失败也当成"连续"） */
      V.probes.push({ clip:c.name, magentaRatio:V.probe.magentaRatio, ok:V.probe.ok,
                      at:Math.round(performance.now()) });
      if(V.probes.length > 12){ V.probes.shift(); }
      if(!V.probe.ok){
        V.alphaFail++;
        c.err.push('alpha 采样不像透明（品红比 ' + V.probe.magentaRatio + '）');
        if(V.alphaFail >= 2){                          /* 连续两次 ⇒ 整站回 pixel（规格 §8） */
          V.mode = 'pixel'; V.disp = false; V.videoOK = false; V.enabled = false;
          V.reason = '连续 ' + V.alphaFail + ' 个剪辑解不出 alpha ⇒ 全站回图集';
          for(var k in V.decoded) release(V.decoded[k], true);
        }else{ fallback(c); }
      }else{ V.alphaFail = 0; }
    }catch(e){ V.probe = { clip:c.name, error:String(e), ok:false }; }
  }
  /* ---- 每帧入口：返回 true = 这一帧已经画好了，页面不要再画图集 ---- */
  /* 原型专属剪辑（不在视频白名单里：opening 只有 hi 图集，sad/smile 有素材但不在状态机）。
     写死在这里是为了**首次开门一个 404 都不发**，而不是每帧去试一次。 */
  var NOVID = {opening:1, sad:1, smile:1};
  function draw(name, fi, box){
    /* ★首次手势前：清单与视频一个都不取（规格 §6"首屏不载视频"、§5"无手势时视频不预载"）。
       所以这一段只返回 false，页面照原样画图集 —— 接线后首屏字节因此**零变化**。 */
    if(!V.gesture) return false;
    if(!V.enabled || !V.videoOK || !V.disp) return false;
    var plan = box.plan, ctx = box.ctx, W = box.w, H = box.h;
    var vname = clipOf(name, plan);
    if(!vname || NOVID[vname]){ V.fallbackDrawn++; return false; }   /* 交给图集 */
    if(V.failed[vname]){ V.fallbackDrawn++; return false; }
    V.cur = vname;
    var c = ensure(vname);
    if(!c){ V.fallbackDrawn++; return false; }
    c.used = ++V.clock;
    var meta = (V.manifest && V.manifest.clips && V.manifest.clips[vname]) || null;
    /* 清单还没到（手势刚发生、fetch 在路上）：这一帧仍走图集，别猜帧数 ✗ */
    if(!meta){ V.fallbackDrawn++; return false; }
    var n = c.frames || plan.frames || 1;
    var i = ((Math.round(fi) % n) + n) % n;
    /* ★倒放剪辑（key_point_to_thinking）：图集是倒放、视频是正放 ⇒ video[n-1-i] == atlas[i]。
       实测依据 _shots/video-align.json：不反转时首末帧剪影质心差 ±1.9px、中间帧吻合；
       反转后全帧吻合。缺了这步，入场/收尾会跳一下。 */
    var vi = meta.reverse ? (n - 1 - i) : i;
    if(c.ready && !c.bad) seek(c, vi);

    var src = null, sw = 0, sh = 0;
    if(c.ready && !c.bad && c.have >= 0){ src = c.bdcv; sw = c.bdcv.width; sh = c.bdcv.height; }
    else if(c.pdone){ src = c.pst; sw = c.pst.naturalWidth; sh = c.pst.naturalHeight; V.fallbackDrawn++; }
    else { V.fallbackDrawn++; return false; }           /* poster 也没到 → 图集继续顶（不留空框 ✗） */
    ctx.clearRect(0, 0, W, H);
    if(plan.fit === 'screen'){
      ctx.drawImage(src, 0, 0, sw, sh, 0, 0, W, H);
    }else{
      /* 落位公式与图集那一支逐字相同（同一处口径，不新增几何） */
      var s = Math.min(W * CHAR_BOX.maxW / CHAR_BOX.w, H * CHAR_BOX.maxH / CHAR_BOX.h);
      var dh = CHAR_BOX.h * s, dw = dh * (sw / sh);
      var x = W * CHAR_BOX.xRatio, y = H - Math.max(3, H * CHAR_BOX.footRatio);
      ctx.drawImage(src, 0, 0, sw, sh, x - dw / 2, y - dh, dw, dh);
    }
    V.drawn++;
    return true;
  }
  function unlock(){
    /* 只在**首次手势**里被调（pointerdown / keydown）：解锁后才会取清单、才知道预载集。
       绝不在 play() 里调它 —— 那会让"手势前不预载视频"这条规格作废（本轮真踩过：
       gate 报告里首屏多出 2 个 poster + 1 个 404）。 */
    if(V.gesture) return;
    V.gesture = true;
    if(!V.enabled || !V.videoOK) return;
    manifestLoad().then(function(j){
      if(!j || !j.preload) return;
      j.preload.slice(0, 3).forEach(function(nm){
        if(!V.decoded[nm] && !V.failed[nm] && !NOVID[nm]){
          var cc = ensure(nm);
          if(cc) cc.used = 0;                           /* 预载进来的排到 LRU 末尾，别挤掉在播的 */
        }
      });
    });
  }
  ['pointerdown', 'keydown'].forEach(function(ev){
    addEventListener(ev, function(){ unlock(); }, {once:true, passive:true});
  });
  document.addEventListener('visibilitychange', function(){
    /* 页面隐藏：暂停视频；可见后由 seek 归位（时间累加器的清零在 walker/loop 侧） */
    var k;
    if(document.hidden){ for(k in V.decoded){ try{ V.decoded[k].vd.pause(); }catch(e){} } }
  });
  return { draw:draw, unlock:unlock, ensure:ensure, state:V, clipOf:clipOf,
           manifest:manifestLoad,
           stats:function(){
             var bytes = 0, k, dc = 0;
             for(k in V.decoded){
               dc++;
               if(V.manifest && V.manifest.clips && V.manifest.clips[k]) bytes += V.manifest.clips[k].bytes.webm;
             }
             return { mode:V.mode, reason:V.reason, alive:V.alive, decoded:dc,
                      failed:Object.keys(V.failed).length, bytesFetchedHint:bytes, drawn:V.drawn,
                      fallbackDrawn:V.fallbackDrawn, released:V.released, preload:V.preload,
                      gesture:V.gesture, probe:V.probe, probes:V.probes, alphaFail:V.alphaFail,
                      errors:V.errors.slice(-4) };
           } };
})();

function drawFrame(){
  /* ★T7：视频层先出帧；它说"这一帧我出了"就不再画图集（false = 照原样画图集） */
  if(XKV2_BLOCK.draw(cur, fi, {plan:CLIPS[cur], ctx:ctx, w:canvas.width, h:canvas.height})) return;
  /* ★T8：状态机接管后，这一帧由它决定；它没画出来（图还没到）就照原样走下面的原型逻辑 */
  if(XK_SM_JS.state.tookOver){
    var _sm = XK_SM_JS.paintOps(XK_SM_JS.state.cur, XK_SM_JS.state.fi, canvas.width, canvas.height);
    if(_sm.mode){ XK_SM_JS.applyOps(ctx, _sm.ops); return; }
  }
  if(!cur) return;
  const _xk = xkClipIm(cur);
  const c = _xk.c, im = _xk.im;
  if(!im.complete || !im.naturalWidth) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const sx = (fi % c.cols) * c.cw, sy = Math.floor(fi / c.cols) * c.ch;
  if(c.fit === 'screen'){
    /* fit=crt_screen：整帧铺满屏幕（开场特写） */
    ctx.drawImage(im, sx, sy, c.cw, c.ch, 0, 0, canvas.width, canvas.height);
  }else{
    /* anchor：源码落位公式 */
    const w = bounds.w * (canvas.width / bounds.w), h = bounds.h * (canvas.height / bounds.h);
    const s = Math.min(w * CHAR_BOX.maxW / CHAR_BOX.w, h * CHAR_BOX.maxH / CHAR_BOX.h);
    const dw = CHAR_BOX.w * s, dh = CHAR_BOX.h * s;
    const x = w * CHAR_BOX.xRatio, y = h - Math.max(3, h * CHAR_BOX.footRatio);
    ctx.drawImage(im, sx, sy, c.cw, c.ch, x - dw/2, y - dh, dw, dh);
  }
}

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
/* ★T5.6 boot→hi：hi 已就绪就用 hi；否则 boot 小图集（前 24 帧，网格/瓦片同规格）先播，
   hi 由 play() 延迟触发（越过首屏窗口）；到位后按同一帧号无缝接力，画质不变。
   警告：hi 只能 peek 缓存、不能 img() 创建 —— img() 创建即发请求，会把 hi 拉回首屏；
   且必须先 peek hi 再兜底 boot —— 顺序反了会永远卡在 boot 档，开场永不落幕。
   ★P0-①：hi 的 peek 现在过一道 XK_TIER.hiAllowed() —— 手机上（或已降档的角色）连 peek 都不做，
   直接吃 boot 中档（34~53MB 的位图根本不会出现在内存里）。 */
function xkClipIm(name){
  const c = CLIPS[name];
  if(XK_TIER.hiAllowed(name)){
    const px = cache[c.src];
    if(px && px.complete && px.naturalWidth) return {im:px, c:c};
  }
  if(!XK_TIER.hiAllowed(name) && !c.bootSrc){
    XK_TIER.degrade(name, 'noHi 且该角色没有中档（boot）⇒ 直接静态帧');
    return {im:img(c.src), c:c};
  }
  if(c.bootSrc){
    const bt = img(c.bootSrc);
    if(bt.complete && bt.naturalWidth) return {im:bt, c:Object.assign({}, c, {frames:c.bootFrames})};
    return {im:bt, c:Object.assign({}, c, {frames:c.bootFrames})};
  }
  return {im:img(c.src), c:c};
}
/* ★2026-10-19（加载速度）：**舞台不可见就不取 hi 图集**。
   实测：/posts/ 这类内容页的角色 canvas 布局尺寸为 0（人物面板收起），
   但 boot 就绪 1.7 s 后 late() 仍把 idle.hi.webp（2.03 MB）拉了下来 ——
   一页白下 2 MB，而这一页上根本没有任何像素用到它。
   面板打开 / 切回首页会重新 play()，那时 stage 有了布局尺寸，自然会取 hi。 */
function xkStageVisible(){
  try{
    const cvs = document.querySelectorAll('[data-xk-kurisu-canvas],.xk-scene,.charcanvas');
    for(let i = 0; i < cvs.length; i++){
      const el = cvs[i];
      if(el.clientWidth > 0 && el.clientHeight > 0) return true;
    }
  }catch(e){}
  return false;
}
function play(name){
  const c = CLIPS[name];
  cur = name; fi = 0; acc = 0;
  /* ★T5.6：boot 先上（首屏只吃小图集）；hi 推迟到 boot 就绪 +1.7s 再取 ——
     越过首屏门禁的 1.5s 窗口，入户字节才真的降下来。boot 加载失败则立刻回退 hi。 */
  if(c.bootSrc){
    const bt = img(c.bootSrc);
    /* ★P0-①：手机/已降档的角色**不上 hi 档**（hi 单张解码 34~53MB，iOS 会把它丢掉）
       ★2026-10-19：舞台没有布局尺寸（内容页人物面板收起）时同样不取，省下整张 hi。 */
    const late = ()=>{ if(!XK_TIER.hiAllowed(name)) return; if(!xkStageVisible()) return; setTimeout(()=>{ img(c.src); }, 1700); };
    if(bt.complete && bt.naturalWidth){ late(); }
    else { bt.addEventListener('load', late, {once:true});
           bt.addEventListener('error', function(){ if(!XK_TIER.hiAllowed(name)){ XK_TIER.degrade(name, 'boot 中档取图失败（error）'); } else { img(c.src); } }, {once:true}); }
  } else { if(XK_TIER.hiAllowed(name)){ img(c.src); } else { XK_TIER.degrade(name, 'noHi 且该角色无中档 ⇒ 静态帧'); } }
  drawFrame();
}


/* ================================================================================
   桐莉栖 · 状态机游走 + 宿主触发（T8 第一批）
   --------------------------------------------------------------------------------
   它接管"她在播哪一段"：按 statemachine.json 的概率边游走，并接受四类宿主事件
   （语音/情绪/空闲/兜底）切进那些**prob=0 的入口节点**（那些入口天生就是给情绪驱动留的）。
   取帧有两条路：视频优先（复用 T7 的 XKV2_BLOCK），拿不到就画 medium 图集；两条路都不改几何公式。

   硬纪律：
     · statemachine.json 取不到/解析失败/结构不对 ⇒ V.on=false，**回到原型 4 剪辑循环**（不白屏 ✗）
     · 出边概率归一化后掷骰；prob=0 的边永不参与随机
     · once_then_hold 播完**停末帧**，等下一次跳转（不自己回绕 ✗）
     · 页面 hidden：暂停推进并**清零累加器**（切回不快进 ✗）
     · 取帧只用 medium.pages（first_frame/last_frame）+ frame_size；**不看 opaque_bbox**（实测已坏）
     · 单帧时长用 statemachine 的 frameIntervalMs，并保留 Math.max(16, ...) 夹取
   诊断口径：window.__xkSM（on/cur/fi/why/reasons/tl/fp/seed/replay/hiddenSkipped/errs）
   ================================================================================ */
var XK_SM_JS = (function(){
  /* ★2026-10-16（`07-v4定稿 §六#2` 合规要求 + 站主要"一键关"）：**全站关角色总开关**。
     触发（任一即可）：URL `?xk-no-kurisu=1` / `?xk-kurisu=off`；或页面在任何脚本之前设 `window.__xkNoKurisu = true`。
     行为（三件一起）：① 状态机不启用（V.on 保持 false）② `<html>` 加 `xk-no-kurisu` 并注入隐藏角色画布的 CSS
     ③ 置 `window.__xkNoKurisu = true`（播放器加载器据此不再拉 `/js/kurisu-player.js`）。
     为什么要有它：角色素材衍生于商业游戏资产（授权口径=非商业技术学习/研究/演示）⇒ 页面必须能"一键不含角色"。 */
  var NO_KURISU = (function(){
    try{
      if(window.__xkNoKurisu === true) return true;
      var q = location.search || '';
      if(/[?&]xk-no-kurisu=1/.test(q) || /[?&]xk-kurisu=off/.test(q)) return true;
    }catch(e){}
    return false;
  })();
  if(NO_KURISU){
    window.__xkNoKurisu = true;
    try{
      document.documentElement.className += ' xk-no-kurisu';
      var st = document.createElement('style');
      st.textContent = 'html.xk-no-kurisu #charCanvas,html.xk-no-kurisu #avCanvas,html.xk-no-kurisu #bubbleCanvas,html.xk-no-kurisu #xkIdAvCanvas,html.xk-no-kurisu #phoneCanvas,html.xk-no-kurisu #phone{display:none !important}';
      (document.head || document.documentElement).appendChild(st);
    }catch(e){}
  }
  /* ---- 四类宿主触发 → 入口剪辑（9 个 prob=0 入口的子集；运行时优先用 JSON 里的 host_triggered_entries）---- */
  var T0 = {
    voice:     ['speaking_trans','speaking_short','key_point_speaking'],
    emotion:   {angry:['angry_trans'], sad:['sad_trans'], shy:['shy_trans'], blush:['shy_trans'],
                surprised:['surprise_trans'], disappointed:['thinking_trans'], happy:['trans_smile'],
                sided_thinking:['thinking_trans'], normal:['trans_standby']},
    idle:      ['trans_standby','idle'],
    cadence:   ['closed_eye_trans','trans_smile','idle_mic_wind']
  };
  /* 语音 id → 情绪（沿用接手批那张表，收在这里；第二批做口型时会再读一次说话段）
     ★T27 收尾：nav_labs / nav_about 两句随靶场/关于两页删除作废（表里不再有这两个键）。 */
  var VOICE_EMO = {
    greet_welcome:'happy', greet_welcome_back:'happy',
    greet_first:'happy', greet_back:'happy', tab_return:'happy',
    nav_home:'normal', nav_monitor:'sided_thinking', nav_notes:'normal', nav_ai:'sided_thinking',
    fallback_no_data:'disappointed', fallback_offline:'disappointed', fallback_throttled:'sad'
  };
  var V = {
    on:false, err:null, errs:[], nodes:null, edges:null, byClip:{}, out:{}, entries:null, root:'idle',
    T:T0, RNG:null, seed:null, replay:null, replayIdx:0, tl:[], why:'—', reasonCounts:{}, fpSet:{}, fpList:[],
    cur:null, fi:0, acc:0, hold:false, lastT:0, hiddenSkipped:0, frames:0, atlasMode:null,
    lastHost:-1e9, lastAny:-1e9, lastIdleFired:-1e9, lastCadFired:-1e9, lastHostMs:-1e9, lastHostEvt:-1e9, hostCd:1800,
    idleMs:12000, cadenceMs:25000, idleCd:8000,
    atlas:{mf:null, full:null, mfErr:null, imgs:{}, pending:0, loaded:0, pages:0, budget:1.5},
    autoMaxMs:2200, startedAt:0
  };
  window.__xkSM = V;
  function assignObj(dest, src){
    /* 把 API 方法挂到状态对象上（两套诊断口径共用同一个对象）。
       ⚠ 这里直接覆盖、不做"跳过同名"的判断；正因如此**状态字段名绝不能与 API 方法名重叠**
         （本轮连踩两次：状态里的 reasons:{} 顶掉 reasons()、状态里的 host:[...] 顶掉 host()）。
         下面这段自检把冲突直接喊出来，免得再靠人眼盯。 */
    var clash = [];
    for(var k in src){ if(Object.prototype.hasOwnProperty.call(src, k)){ if(k in dest) clash.push(k); dest[k] = src[k]; } }
    if(clash.length) V.errs.push('API/状态字段命名冲突：' + clash.join(','));
    return dest;
  }

  /* ---------- 工具 ---------- */
  function qp(k){ var m = location.search.match(new RegExp('[?&]' + k + '=([^&]+)')); return m ? decodeURIComponent(m[1]) : null; }
  /* 固定步进模式（验收脚本专用）：用**虚拟时钟**代替 performance.now，
     这样 idle/cadence 那些基于时间的判定也随固定步长走 ⇒ 整条 timeline 可复现。 */
  var vclock = 0;
  function now(){ return vclock ? vclock : performance.now(); }
  function b64enc(s){ try{ return btoa(unescape(encodeURIComponent(s))); }catch(e){ return ''; } }
  function b64dec(s){ try{ return decodeURIComponent(escape(atob(s))); }catch(e){ return null; } }

  /* ---------- 种子化 RNG（?seed 可复现）---------- */
  function mkRng(seed){
    var a = (seed >>> 0) || 1;
    return function(){ a = (a * 1664525 + 1013904223) >>> 0; return a / 4294967296; };
  }
  /* ---------- 归一化后掷骰子（prob=0 的边永不参与）---------- */
  function pick(list){
    var i, sum = 0, pos = [];
    for(i = 0; i < list.length; i++){ if(list[i].prob > 0){ pos.push(list[i]); sum += list[i].prob; } }
    if(!pos.length || sum <= 0) return null;
    var r = V.RNG() * sum, acc = 0;
    for(i = 0; i < pos.length; i++){ acc += pos[i].prob; if(r <= acc) return pos[i]; }
    return pos[pos.length - 1];
  }

  /* ---------- 读图（状态机自己那一份，medium 档）---------- */
  function loadMf(){
    if(V.atlas.mf) return Promise.resolve(V.atlas.mf);
    if(V.atlas.mfP) return V.atlas.mfP;
    V.atlas.mfP = fetch('/kurisu/manifest.json', {cache:'default'}).then(function(r){
      if(!r.ok) throw new Error('manifest HTTP ' + r.status);
      return r.json();
    }).then(function(j){
      var cm = (j && j.clipsMedium && j.clipsMedium.clips) || null;
      if(!cm) throw new Error('manifest 里没有 clipsMedium.clips');
      V.atlas.full = j;                       /* ★Q2：整份清单留着 —— idle 要吃 clips[].atlas.hi */
      V.atlas.mf = cm;
      return cm;
    }).catch(function(e){ V.atlas.mfErr = String(e.message || e); return null; });
    return V.atlas.mfP;
  }
  function pageOf(clip, f0){                 /* f0 = 0-based 帧号（已含 reverse 处理）*/
    var c = V.atlas.mf && V.atlas.mf[clip];
    if(!c) return null;
    var f1 = f0 + 1, ps = c.atlas.medium.pages, i, p;
    for(i = 0; i < ps.length; i++){
      p = ps[i];
      if(f1 >= p.first_frame && f1 <= p.last_frame) return {c:c, p:p, local:f1 - p.first_frame};
    }
    return null;
  }
  /* ★Q（2026-10-15 接手批 · 窗口 Q）：medium 图集只在**那块画布真的被渲染**时才下载。
     实测取证 _shots/probe-firstscreen.json（CDP 抓 initiator）：五个内容页上 #charCanvas 在
     关着的 v-home 里、getBoundingClientRect 恒为 0×0，状态机却照样接管并按 root 剪辑预取，
     于是首屏白拉 759KB 的 medium/idle.atlas.webp —— ai 页自己还挂着手机面板的 1555KB 全身图，
     两项相加 2314KB，顶破 1650KB 预算（改前实测 ai = 2369400 B）。
     这里**只改加载时机**（站主第四批口径③允许的行为级懒加载）：画布不渲染就不发请求，
     先把没 src 的占位 Image 记在图里（complete=false ⇒ paintOps 不落笔、原型那一帧继续留着）；
     画布真露出来（SPA 切回主页）后下一次取帧就地补拉。取帧公式/几何/版式一字未动。
     canvasRendered 节流 250ms，避免每帧强制布局。 */
  var visAt = -1e9, visVal = false;
  function canvasRendered(){
    var t = now();
    if(t - visAt < 250) return visVal;
    var el = document.getElementById('charCanvas'), r = el ? el.getBoundingClientRect() : null;
    visVal = !!(r && r.width > 0 && r.height > 0);
    visAt = t;
    return visVal;
  }
  function img(url){
    var im = V.atlas.imgs[url];
    if(im){
      if(im.__xkDefer && canvasRendered()){          /* 画布露出来了：就地补拉（之前只是占位）*/
        im.__xkDefer = 0;
        V.atlas.pending++;
        im.src = '/' + String(url).replace(/^\/+/, '');
      }
      return im;
    }
    im = new Image();
    im.decoding = 'async';
    V.atlas.imgs[url] = im;
    im.addEventListener('load', function(){ V.atlas.pending--; V.atlas.loaded++; }, {once:true});
    im.addEventListener('error', function(){ V.atlas.pending--; V.atlas.errs.push('atlas 404 ' + url); }, {once:true});
    if(canvasRendered()){
      V.atlas.pending++;
      im.src = '/' + String(url).replace(/^\/+/, '');
    }else{
      im.__xkDefer = 1;                              /* 画布看不见 ⇒ 不设 src，首屏零请求 */
    }
    return im;
  }
  function prefetch(clip){
    var c = V.atlas.mf && V.atlas.mf[clip];
    if(!c) return;
    if(hiAtlas(clip)) return;                 /* ★Q2：这一档要吃 hi，就不要先白拉 medium 页 */
    var ps = c.atlas.medium.pages, i;
    for(i = 0; i < ps.length; i++){ if(i < V.atlas.budget) img(ps[i].url); }
  }
  /* ★Q2（2026-10-19 画质批）：首页 CRT 的角色本来走 medium 瓦片 **134×180**，
     而 CRT 的 CSS 尺寸是 673×509（DPR2 时画布后台 1346×1017）⇒ 放大 2.8× / 5.6×，
     这才是"人物糊"的真正原因（同一帧里 desk.webp 原生 1672×941 只放大 1.15×，所以背景看着清楚）。
     现成的 hi 图集 `kurisu/full/idle.hi.webp` 是 476×640 / 60 帧 / 2.03MB：DPR1 下是 0.8× 缩小，
     DPR2 也只放大 1.6× —— 观感提升明显，代价是首页多 1.3MB 且解码内存 ~78MB。
     只给 idle 用：它常驻；speaking/thinking 是交互时才出现的，继续走各自的老路径省内存。
     `XK_TIER.hiAllowed()` 已经覆盖了 ?xk-tier=... 与 noHi 两种降档旋钮，这里直接沿用。
     帧号映射：medium 120 帧 @21ms ↔ hi 60 帧 @42ms，同一段时间轴 ⇒ 按比例折算。 */
  /* ★Q2（2026-10-19 画质批）：首页 CRT 的角色本来走 medium 瓦片 **134×180**，
     而 CRT 的 CSS 尺寸是 673×509（DPR2 时画布后台 1346×1017）⇒ 放大 2.83× / 5.66×，
     这才是"人物糊"的真正原因（同一帧里 desk.webp 原生 1672×941 只放大 1.15×，所以背景看着清楚）。
     现成的高一档图集 kurisu/hi/<clip>.atlas.webp 是 **268×360 / 120 帧**（statemachine.json
     每个节点都带 hi 页，帧数与 medium 一一对应 ⇒ 不需要折算帧号）：放大降到 1.41× / 2.83×。
     只认单页的 hi（多页要跨页取帧，没实现）；没有 hi 的剪辑（如 idle2）继续走 medium。
     XK_TIER.hiAllowed() 已经覆盖 ?xk-tier=medium|poster 与 noHi 两种降档旋钮，这里沿用：
     想回到轻量档访问 /?xk-tier=medium 即可（整页不再取任何 hi 页）。 */
  var HI_MIN_H = 380;                 /* CRT 画布高度低于这个就继续用 medium：小窗/手机上不值得多付 4.5MB */
  function hiWanted(){
    var el = document.getElementById('charCanvas'), r = el ? el.getBoundingClientRect() : null;
    return !!(r && r.height >= HI_MIN_H);
  }
  function hiAtlas(clip){
    if(!hiWanted()) return null;
    try{ if(!XK_TIER.hiAllowed(clip)) return null; }catch(e){ return null; }
    var n = (V.byClip && V.byClip[clip]) || null;
    var hi = n && n.hi;
    var ps = hi && hi.pages;
    if(!ps || ps.length !== 1) return null;          /* 多页 hi 不在本批范围 */
    var p = ps[0];
    if(!p || !p.url || !p.tile_w) return null;
    return {p:p, frames:(n.frames || p.frames || 1), cols:(p.cols || 8)};
  }
  function paintHi(clip, fi, cw, ch){
    var h = hiAtlas(clip);
    if(!h) return null;
    var n = h.frames, i = ((Math.round(fi) % n) + n) % n;
    var tw = h.p.tile_w, th = h.p.tile_h;
    var im = img(h.p.url);
    if(!im.complete || !im.naturalWidth) return null;   /* hi 没就绪：这一帧先留着原型帧，不画 */
    return {mode:'atlas', ops:[
      ['clear', [0, 0, cw, ch]],
      ['img', [im, (i % h.cols) * tw, Math.floor(i / h.cols) * th, tw, th,
        Math.min(cw * CHAR_BOX.maxW / CHAR_BOX.w, ch * CHAR_BOX.maxH / CHAR_BOX.h),
        cw * CHAR_BOX.xRatio, ch - Math.max(3, ch * CHAR_BOX.footRatio)]]]};
  }
  /* 视频优先、拿不到画图集；两者都没就绪就**不画**（让原型那一帧继续留着，避免闪空）。
     关键：clearRect 滞后到"图真的就绪"那一步 —— 否则会把原型这一帧清成空白（会闪）✗ */
  function paintOps(clip, fi, cw, ch){
    var r = {mode:null, ops:[]};
    if(V.atlas.mf === undefined) return r;          /* 图集清单还没到：什么都不做 */
    var hr = paintHi(clip, fi, cw, ch);              /* ★Q2：idle 优先吃 hi（476×640） */
    if(hr) return hr;
    if(hiAtlas(clip)) return r;                      /* hi 还没就绪：别顺手把 medium 也拉了，留着原型帧 */
    var c = V.atlas.mf && V.atlas.mf[clip];
    if(!c) return r;
    var n = c.frames || 1, i = ((Math.round(fi) % n) + n) % n;
    var at = pageOf(clip, c.reverse ? (n - 1 - i) : i);
    if(!at) return r;
    var im = img(at.p.url);
    if(!im.complete || !im.naturalWidth) return r;    /* 没就绪：不 clear、不画 */
    var tw = at.p.tile_w, th = at.p.tile_h;
    r.ops.push(['clear', [0, 0, cw, ch]]);
    r.ops.push(['img', [im, (at.local % at.p.cols) * tw, Math.floor(at.local / at.p.cols) * th, tw, th,
      Math.min(cw * CHAR_BOX.maxW / CHAR_BOX.w, ch * CHAR_BOX.maxH / CHAR_BOX.h),
      cw * CHAR_BOX.xRatio, ch - Math.max(3, ch * CHAR_BOX.footRatio)]]);
    r.mode = 'atlas';
    return r;
  }
  function paint(ctx, cw, ch){
    if(window.__xkVid && window.__xkVid.__drawSm){
      if(window.__xkVid.__drawSm(V.cur, V.fi, {plan:{vid:V.cur}, ctx:ctx, w:cw, h:ch})) return 'video';
    }
    var r = paintOps(V.cur, V.fi, cw, ch);
    if(!r.mode) return null;
    applyOps(ctx, r.ops);
    return r.mode;
  }

  /* ---------- 图 ---------- */
  function setHost(edges, hostList){
    V.edges = edges;
    V.hostEntries = hostList && hostList.length ? hostList : null;
    if(V.hostEntries) V.T.voice = V.hostEntries;
  }
  function loadGraph(){
    V.errs.push('load start');
    /* ⚠ 用 cache:'default'（不是 force-cache）：状态机是**会随发布变的行为数据**，
       被强缓存住的话换一版 statemachine.json 页面还会跑老图（实测：多次导航后
       连"注入 404"都命中缓存拿回旧 200 ✗）。 */
    return fetch('/kurisu/statemachine.json', {cache:'default'}).then(function(r){
      if(!r.ok) throw new Error('statemachine HTTP ' + r.status);
      return r.json();
    }).then(function(g){
      if(!g || !g.root || !g.nodes || !g.nodes.length || !g.edges) throw new Error('结构不对（缺 root/nodes/edges）');
      V.nodes = g.nodes;
      V.root = g.root;
      var i, n, e;
      for(i = 0; i < g.nodes.length; i++){
        n = g.nodes[i];
        V.byClip[n.clip] = n;
        V.out[n.clip] = [];
      }
      for(i = 0; i < g.edges.length; i++){
        e = g.edges[i];
        if(!V.out[e.from]) V.out[e.from] = [];
        V.out[e.from].push(e);
      }
      setHost(g.edges, g.host_triggered_entries);
      V.on = true;
      /* ★2026-10-17 自愈：接管（takeOver → start）可能因页面时机丢失 —— 实测：线上/本地都会偶发
         （showHud 早于本模块加载时那句 takeOver 就丢了；主页还会等开场，慢链路下更晚）。
         模块内部兜底：每 1.2s 看一次，只要还没开演就补调 takeOver，直到开演或 30 次为止。 */
      if(!V._selfHeal){
        var _shN = 0;
        V._selfHeal = setInterval(function(){
          try{
            if(!V.on) return;
            if(V.cur){ clearInterval(V._selfHeal); V._selfHeal = null; return; }
            if(++_shN > 30){ clearInterval(V._selfHeal); V._selfHeal = null; return; }
            if(document.visibilityState !== 'hidden' && window.__xkSmTakeOver) window.__xkSmTakeOver();
          }catch(e){ try{ clearInterval(V._selfHeal); }catch(e2){} V._selfHeal = null; }
        }, 1200);
      }
      return true;
    }).catch(function(err){
      V.err = String((err && err.message) || err);
      V.on = false;
      V.errs.push('回落原型循环：' + V.err);
      return false;
    });
  }

  /* ---------- 跳转 ---------- */
  function log(from, to, why, t){
    V.tl.push({t:Math.round(t - V.startedAt), from:from, to:to, why:why});
    V.reasonCounts[why] = (V.reasonCounts[why] || 0) + 1;
  }
  function enter(clip, why){
    if(!V.byClip[clip]) return false;
    var t = now();
    log(V.cur || '(start)', clip, why, t);
    V.cur = clip; V.fi = 0; V.acc = 0; V.hold = false;
    V.why = why;
    V.lastAny = t;
    if(why.indexOf('host:') === 0) V.lastHost = t;
    if(why === 'host:idle') V.lastIdleFired = t;
    prefetch(clip);
    /* ★2026-10-16：**近期访问历史**（供 roll() 做"不回去"惩罚）。
       起因：修掉自环后线上暴露出"两点乒乓"（`speaking_closed_eye_1 ↔ _2` 各 10 次），仍是卡住。
       只留最近 4 步；`__xkSM.stats().recent` 可查。 */
    V.recent = V.recent || [];
    V.recent.push(clip);
    while(V.recent.length > 4) V.recent.shift();
    if(window.__xkSmVoice && V.voiceLineOf) { /* 宿主语音由页面侧调 host()，这里不重复播 */ }
    return true;
  }
  /* ★2026-10-17（站主 C 方案）：状态机轮换的质量闸 —— 返回某个**节点**所演剪辑的原生帧宽。
     为什么需要：38 条剪辑里 33 条是 134×180、idle_closed_eye 168×180，铺到 CRT 要放大 2.4~4.7 倍，
     是她"糊"的真正原因（画布尺寸不是主因）。轮换只走 ≥268px 的 5 条（idle / speaking_med /
     speaking_short / thinking_speaking2 / surprise_speaking）；情绪按钮（显式请求）不受限。 */
  function xkFw(nodeId){
    try {
      var n = V.byClip[nodeId];
      var m = n && XKM.clips && XKM.clips[n.clip];
      return (m && m.frameWidth) || 0;
    } catch(e){ return 0; }
  }
  function entryFor(kind, payload){
    var cand = null;
    if(kind === 'emotion'){
      var em = String((payload && payload.emotion) || payload || '');
      cand = (V.T.emotion && V.T.emotion[em]) || null;
    }else if(kind === 'idle' || kind === 'cadence' || kind === 'voice'){
      cand = V.T[kind] || null;
    }
    if(cand){
      /* ★2026-10-16 修（站主实测"动作没活起来"的根因之一）：
         原实现是"返回**第一个**可用的" ⇒ 每次 `host:voice` 都必然选到同一段
         （线上实测：66 条时间轴里 63 条是 `angry_speaking` 自环、每 ~3 秒一次）。
         现在：在"可用且不等于当前段"的候选里**随机**挑；一个都没有时才退回全集。 */
      var avail = [];
      for(var i = 0; i < cand.length; i++){
        var cl = cand[i];
        /* ★2026-10-17（站主 C 方案）：轮换只从 **原生 ≥268px 宽** 的剪辑里挑 ——
           38 条里有 33 条是 134×180、另有 idle_closed_eye 168×180，铺到 CRT 上要放大 2.4~4.7 倍
           ⇒ 那就是"她糊"的根因（不是画布尺寸问题）。情绪按钮走 kind==='emotion' 分支，不受此限。
           ⚠ 注意：V.byClip[x] 是**状态机节点**（带 .clip），帧宽要看 manifest：XKM.clips[n.clip].frameWidth。 */
        if(xkFw(cl) && xkFw(cl) < 268) continue;
        if(((V.hostEntries && V.hostEntries.indexOf(cl) >= 0) || V.byClip[cl]) && cl !== V.cur) avail.push(cl);
      }
      if(!avail.length){
        for(var j = 0; j < cand.length; j++){
          var cj = cand[j];
          if(xkFw(cj) && xkFw(cj) < 268) continue;
          if((V.hostEntries && V.hostEntries.indexOf(cj) >= 0) || V.byClip[cj]) avail.push(cj);
        }
      }
      if(avail.length) return avail[Math.floor(V.RNG() * avail.length)];
    }
    /* 兜底：把 current 的出边里、指向 host 入口的那条挑出来 */
    var es = V.out[V.cur] || [];
    for(var k = 0; k < es.length; k++){
      if(es[k].prob === 0) return es[k].to;
    }
    return V.root;
  }
  function roll(){
    /* ★2026-10-16 修（站主实测"动作没活起来"的**主根因**）：
       图里存在 `cur → cur` 的自环边且 `prob>0`，原实现直接按权重掷骰 ⇒ 实测线上
       `angry_speaking → angry_speaking` 连中 **63 次**（每 ~3 秒一次），她看起来"冻"在一个动作上。
       现在两条规则：
         ① **优先非自环边**（只有"没有别的正概率边"时才允许自环）；
         ② **反卡死**：连续 3 次落到同一段 ⇒ 强制回 `root`（idle），reason 记 `auto:anti-stall>` 供探针查。 */
    var out = V.out[V.cur] || [];
    var pos = [], self = [];
    for(var k = 0; k < out.length; k++){
      if(out[k].prob > 0){ (out[k].to === V.cur ? self : pos).push(out[k]); }
    }
    /* ★2026-10-16 三次修：**主动打断"N 点循环"**。
       背景：① 反自环修掉后线上露出"两点乒乓"（`speaking_closed_eye_1 ↔ _2`，各 12~13 次）；
             ② 只加"近期访问惩罚"**不够** —— 那两条边只有彼此，回到候选全被排除后退回全集，又回到乒乓。
       判据：最近 4 步里不同剪辑 ≤ 2 个 ⇒ 判定为循环，**强制回到 root（idle）**，
             reason 记 `auto:anti-cycle>idle`（探针可统计）。idle 的出边多，一跳出去就散开了。 */
    var r4 = (V.recent || []).slice(-4);
    if(r4.length >= 4){
      var u4 = [];
      for(var z = 0; z < r4.length; z++){ if(u4.indexOf(r4[z]) < 0) u4.push(r4[z]); }
      if(u4.length <= 2 && V.byClip[V.root] && V.cur !== V.root){
        return enter(V.root, 'auto:anti-cycle>' + V.root);
      }
    }
    var pool = pos.length ? pos : self;
    /* ★2026-10-17（站主 C 方案）：**选边也过质量闸** —— 只要有一条 ≥268px 的出边，就不走低清的边。
       兜底：全被过滤掉时仍用原 pool（宁可动，也不要冻住）。 */
    var poolHi = [], _hi;
    for(_hi = 0; _hi < pool.length; _hi++){
      if(!(xkFw(pool[_hi].to) && xkFw(pool[_hi].to) < 268)) poolHi.push(pool[_hi]);
    }
    if(poolHi.length) pool = poolHi;
    /* 近期访问惩罚：优先选"最近 4 步没到过"的边；全都到过才退回全集
       （此时上面的循环打断与下面的反自环/反卡死仍然生效）。 */
    var recent = V.recent || [];
    var cands = [];
    for(var q = 0; q < pool.length; q++){ if(recent.indexOf(pool[q].to) < 0) cands.push(pool[q]); }
    if(!cands.length) cands = pool;
    var e = pick(cands.length ? cands : (pos.length ? pos : self));
    if(!e) e = pick(out);
    if(!e) return false;
    if(e.to === V.cur){
      V.sameStuck = (V.sameStuck || 0) + 1;
      if(V.sameStuck >= 3 && V.byClip[V.root]){
        V.sameStuck = 0;
        return enter(V.root, 'auto:anti-stall>' + V.root);
      }
    }else{
      V.sameStuck = 0;
    }
    return enter(e.to, 'auto:' + e.from + '>' + e.to);
  }
  function host(kind, payload){
    if(!V.on) return false;
    if(V.fixed && !payload) return false;             /* 固定步进模式：只认带 payload 的显式注入 */
    var t = now();
    if(t - V.lastHostMs < V.hostCd) return false;      /* 冷却：防抖 */
    V.lastHostMs = t;
    V.lastHostEvt = t;                                 /* 只有真正的宿主动作才刷新 cadence 的判据 */
    var cl = entryFor(kind, payload);
    if(!cl) return false;
    if(V.cur === cl && (V.byClip[cl] && V.byClip[cl].loopMode === 'loop')) return false;  /* 已经在循环这一段 */
    return enter(cl, 'host:' + kind);
  }

  /* ---------- 推进 ---------- */
  /* ops 是"推迟落笔"的指令序列：图没就绪时**一条都不发**，页面那一帧就不动（避免闪空 ✗）。
     与 T7 视频层共用同一套落位公式（CHAR_BOX），两条路画出来的几何完全一致。 */
  function applyOps(c, ops){
    var i, o, im, s, dh, dw, x, y;
    for(i = 0; i < ops.length; i++){
      o = ops[i];
      if(o[0] === 'clear'){ c.clearRect(o[1][0], o[1][1], o[1][2], o[1][3]); continue; }
      if(o[0] !== 'img') continue;
      im = o[1][0];
      s = o[1][5]; dh = CHAR_BOX.h * s; dw = dh * (o[1][3] / o[1][4]);
      x = o[1][6]; y = o[1][7];
      c.drawImage(im, o[1][1], o[1][2], o[1][3], o[1][4], x - dw / 2, y - dh, dw, dh);
    }
  }
  function step(dt){
    var n = V.byClip[V.cur];
    if(!n) return;
    var iv = Math.max(16, n.frameIntervalMs || 33);     /* 硬约束：夹取保留 */
    if(V.hold) return;                                  /* once_then_hold 播完停末帧 */
    V.acc += dt;
    var adv = Math.floor(V.acc / iv);
    if(adv > 0){
      V.acc -= adv * iv;
      V.fi += adv;
      if(V.fi >= n.frames){
        if(n.loopMode === 'once_then_hold'){ V.fi = n.frames - 1; V.hold = true; }
        else { V.fi = V.fi % n.frames; }
      }
      V.frames++;
      var hh = hash();
      if(!V.fpSet[hh]){ V.fpSet[hh] = 1; V.fpList.push(hh); }
    }
  }
  function hash(){
    try{
      var d = ctx.getImageData(0, 0, canvas.width, canvas.height).data, h = 0;
      for(var i = 0; i < d.length; i += 601) h = (h * 31 + d[i] + (d[i + 1] << 3)) >>> 0;
      return h;
    }catch(e){ return 'err'; }
  }
  function due(){
    var t = now();
    /* idle / cadence 走**各自己的**冷却，不吃 hostCd（hostCd 是给 voice/emotion 的防抖）。
       注意 cadence 的判据是"**没有宿主事件**"（lastHostEvt），不是"没有触发"——
       否则 idle 每 8s 刷新一次就永远轮不到 cadence（它本来就是兜底，得能真的兜上）。 */
    if(t - V.lastHostEvt >= V.cadenceMs && t - V.lastCadFired >= V.cadenceMs){
      V.lastCadFired = t; V.lastHost = t; V.lastHostMs = t;
      enter(entryFor('cadence'), 'host:cadence');
      return;
    }
    if(t - V.lastHost >= V.idleMs && t - V.lastIdleFired >= V.idleCd){
      V.lastIdleFired = t; V.lastHost = t; V.lastHostMs = t;
      enter(entryFor('idle'), 'host:idle');
    }
  }
  function autoDue(){
    if(V.replay) return false;
    if(!V.autoAt) return false;
    return now() >= V.autoAt;
  }
  function arm(){
    var n = V.byClip[V.cur];
    var dur = (n ? n.frames * Math.max(16, n.frameIntervalMs) : 900);
    V.autoAt = now() + Math.min(V.autoMaxMs, Math.max(600, dur));
  }
  /* 自动跳转的节奏钳制：一段最多播 autoMaxMs 就换下一段（默认 2.2s）——
     素材里 idle_closed_eye 有 738 帧/12.5s、idle_side_butterfly 600 帧/10s，
     不钳制的话 30 秒只能看到 2~3 段，"她在动"反而看不出来。这条是**表现口径**，
     改 V.autoMaxMs 即回退到"整段播完再换"。 */
  function tick(dtForced){
    if(!V.on) return false;
    if(V.fixed && dtForced == null) return false;        /* 固定步进模式：只认 stepFixed，真实 rAF 不推进 */
    var t = now();
    var dt = (dtForced != null) ? (V.fixedMs || 33) : (t - (V.lastT || t));
    V.lastT = t;
    if(document.hidden){ V.hiddenSkipped++; V.acc = 0; return true; }   /* 隐藏：不推进、清零累加器 */
    if(dt > 200) dt = 200;                                               /* 硬约束：夹取保留 */
    /* replay：按时间线回放，保证"同一段画面"可复现 */
    if(V.replay){
      var ev = V.replay[V.replayIdx];
      if(ev && (t - V.startedAt) >= ev.t){ V.replayIdx++; enter(ev.to, ev.why + ':replay'); }
    }
    step(dt);
    var mode = paint(ctx, canvas.width, canvas.height);
    if(mode) V.atlasMode = mode;
    if(mode) V.drew = (V.drew || 0) + 1;
    /* ⚠ 固定步进模式下 due() 也必须由 stepFixed 驱动的 tick 来跑（否则真实 rAF 会把
       idle/cadence 从墙钟里额外打出来，timeline 就对不齐了 —— 本轮踩过）*/
    if(dtForced != null) due();
    if(V.replay){
      var ev2 = V.replay[V.replayIdx];
      if(ev2 && (t - V.startedAt) >= ev2.t){ V.replayIdx++; enter(ev2.to, ev2.why + ':replay'); }
    }else if(autoDue()){
      if(roll()) arm(); else V.autoAt = now() + 800;
    }
    return true;
  }
  function start(){
    if(!V.on || V.cur) return;
    V.startedAt = now();
    V.lastT = V.startedAt;
    V.lastHost = V.startedAt;
    V.lastHostEvt = V.startedAt;
    var first = (V.replay && V.replay[0]) ? V.replay[0].to : V.root;
    enter(first, V.replay ? (V.replay[0].why + ':replay') : 'auto:start');
    arm();
  }

  /* ---------- 页面钩子 ---------- */
  document.addEventListener('visibilitychange', function(){
    if(document.hidden){ V.acc = 0; V.hold = V.hold; }
    else { V.lastT = 0; V.acc = 0; }
  });
  /* status 行：**真实文本变化**才播（20s 防抖；不按定时器 ✗） */
  (function(){
    var seen = null, last = -1e9;
    setInterval(function(){
      if(!V.on || V.fixed) return;                     /* 固定步进（验收）模式下，宿主事件只由脚本注入 */
      var el = document.querySelector('.crt-status') || document.getElementById('crtStatus') || document.querySelector('[data-xk-kurisu-status]');
      var txt = el ? String(el.textContent || '').replace(/\s+/g, ' ').trim() : '';
      if(!txt || txt === seen) return;
      seen = txt;
      var t = now();
      if(t - last < 20000) return;                    /* 20s 防抖 */
      last = t;
      host('voice', {line:'status'});
    }, 2500);
  })();
  /* 每 1.25s 重新取一次种子序列（?seed 稳定；无 seed 用时间） */
  V.seed = qp('seed') != null ? (parseInt(qp('seed'), 10) >>> 0) : (Date.now() >>> 0);
  V.RNG = mkRng(V.seed);
  if(qp('xk-idle')) V.idleMs = Math.max(2000, parseInt(qp('xk-idle'), 10) || V.idleMs);
  if(qp('xk-host')) V.hostCd = Math.max(300, parseInt(qp('xk-host'), 10) || V.hostCd);
  if(qp('replay')){
    try{ V.replay = JSON.parse(b64dec(qp('replay')) || 'null'); }catch(e){ V.replay = null; }
    if(V.replay && V.replay.length){ V.seed = V.replay[0].seed || V.seed; V.RNG = mkRng(V.seed); }
  }
  function timeline(){ return V.tl.map(function(e){ return e.t + ':' + e.to + ':' + e.why; }).join('|'); }
  var API = {
    state:V,
    boot:function(){
      if(NO_KURISU){ V.errs.push('kurisu-off'); return Promise.resolve(false); }   /* ★全站关角色总开关（见该 IIFE 顶部注释）*/
      if(qp('xk-sm') === 'off'){ V.errs.push('xk-sm=off'); return Promise.resolve(false); }
      var rm = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
      if(rm){ V.errs.push('reduced-motion ⇒ 不启用状态机'); return Promise.resolve(false); }
      return loadMf().then(function(){ return loadGraph(); }).then(function(ok){
        if(!ok) return false;                       /* 回落：原型 4 剪辑循环继续跑（不白屏 ✗）*/
        window.__xkSmTakeOver = function(){
          if(V.tookOver) return;
          V.tookOver = true;
          try{ if(typeof XK_ACT !== 'undefined') XK_ACT = null; }catch(e){}
          start();                                  /* ⚠ 调函数名，不要调 V.start（V 是状态对象，不是 API）*/
        };
        /* 主页要等开场落定（showHud 里调 takeOver）；五页没有 opening，加载完就直接接 */
        if(!window.__xkSmIsHome) window.__xkSmTakeOver();
        return true;
      });
    },
    start:start, tick:tick, host:host, entryFor:entryFor, takeOver:function(){ if(window.__xkSmTakeOver) window.__xkSmTakeOver(); },
    /* 验收用：把时钟整体换成"虚拟时钟"（anchor 起算），必须在 takeOver 之前调 */
    useVirtualClock:function(anchor){ V.virtual = true; vclock = anchor || 1000; V.anchor = vclock; return vclock; },
    /* 固定步进推进（**只给验收脚本用**：这台机器 headless 的 rAF 会被节流，
       靠墙钟等不到确定性）。它按固定 dt 走一步，seed 相同 + 宿主事件序列相同 ⇒ timeline 逐字相同。 */
    stepFixed:function(dt, n){
      var k, d = dt || 33;
      if(document.hidden){ V.hiddenSkipped++; V.acc = 0; return 0; }
      V.fixed = true;                                   /* 固定步进模式：真实 rAF 不再推进 */
      if(!vclock) vclock = 1000;
      for(k = 0; k < (n || 1); k++){ vclock += d; tick(d); }
      return n || 1;
    },    paint:paint, paintOps:paintOps, applyOps:applyOps,
    currentClip:function(){ return V.cur; },   /* ⚠ 不要叫 cur：状态里已有 cur（当前剪辑名），会互相顶 ✗ */
    timeline:timeline,
    replayB64:function(){
      return b64enc(JSON.stringify(V.tl.map(function(e, i){ return {t:e.t, to:e.to, why:e.why, seed:i ? null : V.seed}; })));
    },
    reasons:function(){ return JSON.parse(JSON.stringify(V.reasonCounts || {})); },
    stats:function(){
      return { on:V.on, err:V.err, tookOver:!!V.tookOver, cur:V.cur, fi:V.fi, why:V.why, frames:V.frames, drew:V.drew || 0,
               atlasMode:V.atlasMode, fingerprints:V.fpList.length, fingerprintList:V.fpList.slice(0, 24),
               reasons:V.reasonCounts, timeline:V.tl.slice(-40), timelineN:V.tl.length, timelineRaw:V.tl, seed:V.seed,
               nodes:V.nodes ? V.nodes.length : 0, edges:V.edges ? V.edges.length : 0,
               entries:(V.hostEntries || []).length, hiddenSkipped:V.hiddenSkipped,
               atlas:{pages:V.atlas.pages, loaded:V.atlas.loaded, pending:V.atlas.pending, err:V.atlas.mfErr},
               replay:!!V.replay, idleMs:V.idleMs, cadenceMs:V.cadenceMs, hostCd:V.hostCd,
               recent:(V.recent || []).slice(), errors:V.errs.slice(-6) };
    }
  };
  /* ★既有门禁（gate-firstscreen 第 251 行）读的是 `window.__xkSM.reasons()` ——
     所以把 API 的方法也挂到 window.__xkSM 这个对象上，两套诊断口径同时可用（都指向同一份状态）。 */
  return assignObj(V, API);
})();

function loop(t){
  if(!started) return;
  /* ★T8：状态机接管后由它推进（含 hidden 清零/累加器夹取/指纹记账）*/
  if(XK_SM_JS.state.tookOver){ XK_SM_JS.tick(); lastT = t; requestAnimationFrame(loop); return; }
  if(cur){
    const _xk = xkClipIm(cur);
    const c = _xk.c, im = _xk.im;
    if((im.complete && im.naturalWidth) && !RM){
      acc += t - lastT;
      if(acc >= c.interval){
        acc = 0; fi++;
        if(fi >= c.frames){
          if(cur === 'opening'){ play('idle'); showHud(); }   /* 硬切（原版机制） */
          else fi = fi % c.frames;
        }
        drawFrame();
      }
    }
  }
  lastT = t;
  requestAnimationFrame(loop);
}

/* 屏内 HUD：开场结束后出现 */
let hudShown = false;
function showHud(){
  if(hudShown) return; hudShown = true;
  document.getElementById('crtStatus').hidden = false;
  typeSub('这里分三块：监测中心看实时攻击，AI 问答查概念，笔记写搭建过程。都不用登录。');
}
let typeTimer = null;
function typeSub(text){
  const el = document.getElementById('subText'), sub = document.getElementById('crtSub');
  sub.hidden = false; el.textContent = '';
  clearInterval(typeTimer);
  let i = 0;
  typeTimer = setInterval(()=>{
    el.textContent = text.slice(0, ++i);
    if(i >= text.length) clearInterval(typeTimer);
  }, 45);
}

/* 启动：reduced-motion 直接静帧 */
resize(); addEventListener('resize', ()=>{ resize(); drawFrame(); });
if(RM){
  cur = 'idle'; fi = 0;
  const im = img(CLIPS.idle.src);
  (im.complete ? Promise.resolve() : new Promise(r=>im.onload=r)).then(()=>{ drawFrame(); showHud(); });
  const bv = document.getElementById('bootveil');   /* ★第十二批：同上，五个内容页没有 #bootveil */
  if(bv){ bv.style.opacity = 0; setTimeout(()=>bv.remove(), 450); }
}else if(document.getElementById('v-home').classList.contains('on')){
  play('opening');
}
window.__xkSmIsHome = false;
function xkSmBoot(){ try{ XK_SM_JS.boot(); }catch(e){}
  /* ★2026-10-17 修时序竞态：接管原本只写在 showHud() 里，而 showHud 可能早于本模块加载
     （实测有时 __xkSM.cur 一直为 null、她永远是主页自己的 full/* 循环）⇒ 加兜底重试：
     开场落定（约 7s）后，只要状态机还没开始演，就每秒补调一次 takeOver()，最多 20 次。 */
  setTimeout(function(){
    var n = 0;
    var t = setInterval(function(){
      try {
        if(window.__xkSM && window.__xkSM.cur){ clearInterval(t); return; }
        if(window.XK_SM_JS && XK_SM_JS.takeOver) XK_SM_JS.takeOver();
        if(++n >= 20) clearInterval(t);
      } catch(e){ clearInterval(t); }
    }, 1000);
  }, 7000);
}
/* ★2026-10-17 站主定：**C 方案** —— 开场用立绘那套(full/*)，进站后由状态机演 38 条动作；
   但状态机的 idle/轮换只从 **≥268px** 的剪辑里挑（entryFor 里过滤），低清的 134/168 剪辑不参与轮换
   （情绪按钮仍可显式调用）。状态机在主页恢复启动。 */
if(!window.__xkSaver) setTimeout(xkSmBoot, 600);   /* ★V3：省流模式不起状态机（不取任何剪辑图集）*//* 与首屏门禁的 1.5s 窗口错开（懒加载，零首屏影响）*/
started = true; lastT = performance.now();
requestAnimationFrame(loop);
const veil = document.getElementById('bootveil');   /* ★第十二批：同上，加存在性判断 */
const desk = document.querySelector('.desk');
(desk && !desk.complete ? new Promise(r=>desk.onload=r) : Promise.resolve()).then(()=>{
  if(veil){ veil.style.opacity = 0; setTimeout(()=>veil.remove(), 450); }
});

/* 暴露给外壳切换 */
let introPlayed=false;
window.__enterHome=function(){
  resize(); drawFrame();
  const played=sessionStorage.getItem('xk-demo-intro');
  if(!RM && !played && document.getElementById('v-home').classList.contains('on')){ play('opening'); sessionStorage.setItem('xk-demo-intro','1'); }
  else if(!cur){ play('idle'); }
};
})();

