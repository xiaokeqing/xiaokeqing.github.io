# -*- coding: utf-8 -*-
"""把两个 demo 文件"整份搬"成生产页模板（本轮口径，2026-10-14 第四批）。

口径（站主原话）：
  · 主页 = `docs/demo-主页.html` **整份**（它的 <style> / body 标记 / 内联 <script> 全搬）
  · 其余五页 = `docs/demo-内容页外壳.html` **整份**（同样的 style + 标记 + 两段内联 script），
    只改两处：① 素材路径 → static/ 下的真文件 ② 导航 <button data-v> → <a href="真路由">
  · 不再套站点 SPA 外层、不再挂 kurisu-player、不做像素差循环
  · 只保留"不可见契约"：Hugo 的 <head>/标题/canonical + <main id="content" data-xk-ssr> + #xk-views 占位

本脚本是**生成器**：所有 demo 文本都从 docs/ 下的原文件逐字抽取，避免手抄走样。
改口径 = 改这里再跑一次（输出在 layouts/ 下，那些才是要提交的源文件）。

用法：python _dev/gen-demo-pages.py
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_HOME = os.path.join(ROOT, 'docs', 'demo-主页.html')
DEMO_SHELL = os.path.join(ROOT, 'docs', 'demo-内容页外壳.html')
PART = os.path.join(ROOT, 'layouts', 'partials', 'xk-demo')


def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def write(p, s):
    d = os.path.dirname(p)
    if not os.path.isdir(d):
        os.makedirs(d)
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(s)
    print('  -> %s  (%d B)' % (os.path.relpath(p, ROOT), len(s.encode('utf-8'))))


# ---------------------------------------------------------------- 素材路径映射
# 目标都是仓库里**已经存在**的文件（逐字节与 demo-assets 同名副本一致，见交接文档核对表）
PATH_MAP = {
    'desk.webp': '/images/crt/desk.webp',
    'lab.webp': '/images/crt/lab.webp',
    'amadeus_ambient_high_blend.webp': '/kurisu/scene/amadeus_ambient_high_blend.webp',
    'subtitle_frame_big.webp': '/kurisu/scene/subtitle_frame_big.webp',
    'opening.hi.webp': '/kurisu/full/opening.hi.webp',      # demo-assets 里缺这个文件，我们有
    'idle.hi.webp': '/kurisu/full/idle.hi.webp',
    'speaking.hi.webp': '/kurisu/full/speaking.hi.webp',
    'thinking.hi.webp': '/kurisu/full/thinking.hi.webp',
    'normal.idle.webp': '/kurisu/avatar/normal.idle.webp',
    'normal.speaking.webp': '/kurisu/avatar/normal.speaking.webp',
    'happy.idle.webp': '/kurisu/avatar/happy.idle.webp',
    'happy.speaking.webp': '/kurisu/avatar/happy.speaking.webp',
    'sided_thinking.idle.webp': '/kurisu/avatar/sided_thinking.idle.webp',
    'sided_thinking.speaking.webp': '/kurisu/avatar/sided_thinking.speaking.webp',
    'sad.static.webp': '/kurisu/avatar/sad.static.webp',
    'blush.static.webp': '/kurisu/avatar/blush.static.webp',
}


def rewrite_assets(s):
    s = re.sub(r'demo-assets/bg/([\w.\-]+)', lambda m: '/kurisu/scene/bg/' + m.group(1), s)

    def rep(m):
        name = m.group(1)
        if name not in PATH_MAP:
            raise SystemExit('未映射的素材路径：demo-assets/%s（先决定它去 static/ 哪里）' % name)
        return PATH_MAP[name]

    return re.sub(r'demo-assets/([\w.\-]+)', rep, s)


# 五页导航：demo 是 <button data-v="monitor">监测中心</button>（它自己的 JS 切 view），
# 生产页要真链接（可新窗口打开、可被爬），所以换成 <a href="真路由">，外观值见下面的伴随规则。
DOCK_HREF = {
    'home': '/',
    'monitor': '/alerts/',
    'ai': '/ai/',
    'notes': '/posts/',
    'range': '/labs/',
    'about': '/about/',
}


def rewrite_dock(chrome):
    def rep(m):
        v, label = m.group(1), m.group(2)
        return ('<a href="%s" class="{{ if eq $v "%s" }}on{{ end }}">%s</a>'
                % (DOCK_HREF[v], v, label))
    out, n = re.subn(r'<button data-v="(\w+)"(?: class="on")?>([^<]*)</button>', rep, chrome)
    if n != len(DOCK_HREF):
        raise SystemExit('dock 按钮只换了 %d 个（期望 %d）' % (n, len(DOCK_HREF)))
    return out


# ------------------------------------------------------------------ 抽出 demo 片段
def block(s, pat, what):
    m = re.search(pat, s, re.S)
    if not m:
        raise SystemExit('抽不到 %s' % what)
    return m.group(1)


home_src = read(DEMO_HOME)
shell_src = read(DEMO_SHELL)

home_style = block(home_src, r'<style>(.*?)</style>', 'demo-主页 style')
home_body = block(home_src, r'<body>(.*?)<script>', 'demo-主页 body').strip('\n')
home_script = block(home_src, r'<script>(.*?)</script>', 'demo-主页 script')

shell_style = block(shell_src, r'<style>(.*?)</style>', 'demo-外壳 style')
shell_body = block(shell_src, r'<body[^>]*>(.*?)</body>', 'demo-外壳 body')
scripts = re.findall(r'<script[^>]*>.*?</script>', shell_body, re.S)
if len(scripts) != 2:
    raise SystemExit('外壳里的 <script> 数量变了：%d' % len(scripts))
shell_body_ns = re.sub(r'<script[^>]*>.*?</script>', '\n@@SCRIPT@@\n', shell_body, flags=re.S)
main_m = re.search(r'<main class="main">(.*?)</main>', shell_body_ns, re.S)
if not main_m:
    raise SystemExit('找不到外壳的 <main class="main">')
chrome = shell_body_ns[:main_m.start()].strip('\n')
views = main_m.group(1)

# 六个 view 切成六块（每块自带它原来的 class="view"/"view on"）
secs = list(re.finditer(r'<section class="view(?: on)?" id="v-([a-z]+)">', views))
if len(secs) != 6:
    raise SystemExit('view 数量不对：%d' % len(secs))
chunks = []
for i, m in enumerate(secs):
    end = secs[i + 1].start() if i + 1 < len(secs) else len(views)
    chunk = views[m.start():end]
    head = ('<section class="view{{ if eq $v "%s" }} on{{ end }}" id="v-%s">' % (m.group(1), m.group(1)))
    chunk = head + views[m.end():end]          # m.end() 是 views 里的绝对偏移，必须在 views 上切
    chunks.append(chunk.rstrip() + '\n')

# ------------------------------------------------------------------- 头/尾 拼装
HEAD_META = u'''{{- /* 不可见契约：Hugo 的 head（标题/描述/canonical/OG/favicon）。
       demo 文件自己的 <head> 只有 charset+viewport+title+<style>；这一份补上站点既有的 SEO 字段，
       其余一个字节都不加。 */ -}}
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{{- $desc := .Description | default site.Params.description -}}
{{- $ogTitle := cond .IsHome "xiaokeqing · 个人博客与安全运营工作台" .Title -}}
{{- $ogImgPath := "/images/bg.jpg" -}}
{{- with .Params.images }}{{ $ogImgPath = index . 0 }}{{ end -}}
{{- $ogImg := $ogImgPath | absURL -}}
<title>{{ if .IsHome }}xiaokeqing · 个人博客与安全运营工作台{{ else }}{{ .Title }} · xiaokeqing{{ end }}</title>
<meta name="description" content="{{ $desc }}">
<meta name="author" content="{{ site.Params.author }}">
<meta name="color-scheme" content="dark">
{{ hugo.Generator }}
<meta name="wb-api" content="{{ site.Params.wbApiBase | default "https://demo.xiaokeqing.cn" }}">
<link rel="icon" type="image/png" sizes="128x128" href="/favicon-128.png">
<link rel="apple-touch-icon" sizes="256x256" href="/favicon-256.png">
<link rel="canonical" href="{{ .Permalink }}">
<meta property="og:type" content="website">
<meta property="og:title" content="{{ $ogTitle }}">
<meta property="og:description" content="{{ $desc }}">
<meta property="og:url" content="{{ .Permalink }}">
<meta property="og:site_name" content="{{ site.Title }}">
<meta property="og:locale" content="zh_CN">
<meta property="og:image" content="{{ $ogImg }}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{ $ogTitle }}">
<meta name="twitter:description" content="{{ $desc }}">
<meta name="twitter:image" content="{{ $ogImg }}">
'''

VIEWS_TAIL = u'''</main>
{{- /* 不可见契约：SPA 视图表占位（_dev/check-ssr-contract.py 要每页都有 #xk-views）。
       本轮不挂 app.js（站主口径：不再套站点 SPA 外层），所以它只是一个空壳，不参与渲染。 */}}
<div id="xk-views" hidden aria-hidden="true"></div>
'''

# 伴随规则：<a> 需要和 <button> 一模一样的值（demo 的 .dock button 那三条的原值逐字复制）
DOCK_A_CSS = u'''
  /* ★ 生产站差异（唯一一处 CSS 新增，值逐字照抄上面的 .dock button 三条）：
     demo 的导航是 <button data-v=…>（它自己的 JS 切 view），生产页换成 <a href="真路由">，
     所以要给 .dock a 一组同样的外观值。demo 自己的元素渲染结果零变化。 */
  .dock a{display:flex;align-items:center;background:none;border:1px solid transparent;
    color:var(--mut);font:13px var(--sans);padding:7px 10px 7px 8px;border-radius:0 9px 9px 0;cursor:pointer;
    text-align:left;white-space:nowrap;text-decoration:none}
  .dock a.on{color:var(--acc);border-color:var(--line2);background:rgba(57,208,216,.1);font-weight:500}
  .dock a:hover{color:var(--txt)}
  /* ★窗口 Q（2026-10-16）移动端硬伤 3（配对修复）：demo 那份 980px 加高规则写在
     `.dock button` 上，生产页的元素是 <a> ⇒ 选择器不命中，必须给同一组值。
     值 = demo 的 `.dock button{min-height:44px;min-width:44px;justify-content:center;padding:13px 10px}`。 */
  @media (max-width:980px){
    .dock{gap:4px;padding:6px}
    .dock a{min-height:44px;min-width:44px;justify-content:center;padding:13px 10px}
  }
'''

# 主页脚本里的路径也要改（CLIPS 表）
home_script = rewrite_assets(home_script)

# ---- ⑮ 主页语音：把桐莉栖的 L1 预渲染语音**真接上**（真播放，不是"打字幕假装会说话"）----
# 【2026-10-15 接手批】资产早已就绪：static/kurisu/voice/ = bank.json + 12 条语音 + 逐条包络。
#   （T4：2026-10-15 已把这 12 条从 Windows SAPI 占位 wav 换成 GPT-SoVITS v3 日语 m4a/webm，
#    播放器读 bank.json 的 line.audio，契约不变 ⇒ 这里一行都不用改。）
#   但主页那段内联脚本只 typeSub() 打字幕，一个音频都不播 —— "她会说"这件事其实没实现。
#   这里在主页脚本**末尾**接一个自足的语音模块（不引新文件、不动任何版式/标记）：
#     · 手势前不播（浏览器 autoplay 限制）→ 只记 pending，首次 pointerdown/keydown 后补放最近一条；
#     · 首访/回访分流（localStorage）→ greet_first / greet_back；切回标签页 >60s → tab_return；
#     · 字幕与语音用**同一句**文案（line.text），语音取不到就只显示字幕，**绝不假装在播**；
#     · reduced-motion 不自动播；语音库在首屏窗口（1.5s 门禁口径）**之后**才取 → 不占首屏字节；
#     · 诊断挂 window.__xkVoice（plays / lastId / errors），便于验收与取证。
HOME_VOICE = r'''

/* ================= 桐莉栖语音（L1 预渲染语音库 · 真实播放） =================
   ★2026-10-15 接手批：这一段是**新接的**。原 demo 主页只会打字幕，从不播音频。
   资产：static/kurisu/voice/bank.json（12 条日语 m4a，逐条带 text / seconds / 包络）。
   纪律：手势前不播（只记 pending）；取不到就只显示字幕，绝不假装在播；RM 不自动播。 */
const XK_VOICE_BANK = '/kurisu/voice/bank.json';
const XK_DEFAULT_SAY = '你好，我是桐莉栖。这一屏的数字都是真的——看不清就走近一点。';
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
  return fetch(XK_VOICE_BANK, {cache:'no-store'}).then(r=>{
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
    KurisuPlayer.speakGroup('/', _grp, {preferId:id}).then(r=>{
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
      if(typeof play === 'function' && cur !== 'opening'){
        const sim = img(CLIPS.speaking.src);
        if(sim.complete && sim.naturalWidth){ play('speaking'); }
        else { sim.addEventListener('load', ()=>{ if(!XKV.audio || !XKV.audio.paused) play('speaking'); }, {once:true}); }
      }
    });
    a.addEventListener('error', ()=>{ XKV.errors.push('audio: '+id); });
    a.addEventListener('ended', ()=>{
      if(typeof play === 'function') play('idle');
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
  xkvLoad().then(()=>{
    let seen = false;
    try{ seen = !!localStorage.getItem('xk-visited'); localStorage.setItem('xk-visited','1'); }catch(_){}
    const id = seen ? 'greet_back' : 'greet_first';
    XKV.entryId = id;
    xkvPlay(id);
  });
}
/* ★批次A：声音开关打开的那一刻，把刚才因为"声音关着"压下来的那一句补播（同一句，不换文案）。 */
addEventListener('xk-sound', function(ev){
  if(ev && ev.detail && ev.detail.on && XKV.pending){ const id = XKV.pending; XKV.pending = null; xkvPlay(id); }
});
addEventListener('pointerdown', xkvUnlock, {once:true});
addEventListener('keydown', xkvUnlock, {once:true});
/* 语音库在首屏窗口（门禁口径 1.5s）**之后**才取 —— 语音资产不进首屏字节 */
setTimeout(xkvLoad, 1800);
if(!RM){ setTimeout(xkvGreet, 2600); }
let xkvHiddenAt = 0;
document.addEventListener('visibilitychange', ()=>{
  if(document.hidden){ xkvHiddenAt = Date.now(); }
  else if(xkvHiddenAt && (Date.now() - xkvHiddenAt) > 60000){ xkvHiddenAt = 0; xkvPlay('tab_return'); }
});
'''
home_script = home_script + HOME_VOICE
home_body = rewrite_assets(home_body)
# 导航统一（站主本批口径）：主页 demo 的**顶部胶囊 .navpill** → 内容页外壳那一份**左侧竖排 dock**。
#   标记逐字照 xk-demo/shell-chrome.html 的 <nav class="dock">（项目/顺序/aria 全同；主页高亮"主页"）；
#   样式值逐字照 xk-demo/shell-style.html 的 .dock / .dock .brand / .dock a（含 980px 那一条）与
#   .dock 用到的 :root 变量（warm 口径）。链接仍是站点真路由：这一页不挂 app.js，所以不是
#   data-xk-route / hash，而是普通 <a href="/…"> 服务器端渲染当前项。
NAVPILL_HTML = (
    '<nav class="navpill" aria-label="站点导航（演示）">\n'
    '  <a class="on" href="#">主页</a><a href="#">监测中心</a><a href="#">笔记</a>\n'
    '  <a href="#">靶场</a><a href="#">AI 问答</a><a href="#">关于</a>\n'
    '</nav>')
DOCK_HTML = (
    '<nav class="dock dock--wait" id="dock" aria-label="站点导航（演示）">\n'
    '  <div class="brand">XK-LAB</div>\n'
    '  <a href="/" class="on">主页</a>\n'
    '  <a href="/alerts/">监测中心</a>\n'
    '  <a href="/ai/">AI 问答</a>\n'
    '  <a href="/posts/">笔记</a>\n'

    '</nav>')
NAVPILL_CSS = (
    '  /* 屏外：导航浮条 */\n'
    '  .navpill{position:fixed;top:16px;left:16px;z-index:60;display:flex;gap:2px;\n'
    '    background:rgba(11,17,24,.82);border:1px solid rgba(120,200,220,.35);border-radius:99px;\n'
    '    padding:4px;backdrop-filter:blur(8px)}\n'
    '  .navpill a{font:12.5px var(--sans);color:#8CA3B8;text-decoration:none;padding:5px 12px;border-radius:99px}\n'
    '  .navpill a.on{color:#39D0D8;background:rgba(57,208,216,.1)}\n')
# ---- ★T31 第三拍：导航栏入场（站主 2026-10-15 口径）----------------------------------
#   主页 CSS/JS 与生成器同源：DOCK_CSS 里追加 T31_CSS，home_script 里注入 T31_JS，
#   并把"opening 播完 → 起推拉"抽成 xkTransStart()（自然路径行为逐字不变，跳过路径共用它）。
#   三拍时序：#1 通电闪烁（xkPowerOn）→ #2 助手大脸（opening 特写）→ #3 导航栏落入（本段）。
T31_CSS = '  /* ★T31 开场六阶段（站主 2026-10-15 精确规格）——\n     ① 首屏只有桌面壁纸（其余图由 JS 在 ①→② 之间才插入 ⇒ 首个请求只能是 desk.webp）\n     ② 底噪 + 一条极细扫描线 = 加载信号（不是转圈 ✗）\n     ③ CRT 黑屏闪烁 2~4 次（80~140ms，随机，不规律 ✗ 不做正弦）\n     ④ 大脸（opening 特写）以 2~3 次闪断出现（60~100ms 硬切 + 1~3px 行同步位移）\n     ⑤ 闪烁停止的那一帧：过冲白光 → 稳定，**同一帧**导航栏淡入上移（0.35s）\n     ⑥ 正式动画（opening → idle；沿用 L1 推拉，推拉起点 = 闪烁结束）\n     状态机在 <html data-xk-boot="0..5">，可查 window.__xkBoot = {phase,t0,marks,log} */\n  .crtboot{position:absolute;inset:0;z-index:6;background:#000;pointer-events:none}\n  .crtboot.noise{background-image:repeating-linear-gradient(0deg,rgba(255,255,255,.055) 0 1px,transparent 1px 3px)}\n  .crtboot.noise::after{content:"";position:absolute;left:0;right:0;top:46%;height:2px;\n    background:rgba(140,220,240,.20);animation:bootscan 1.1s linear infinite}\n  @keyframes bootscan{0%{top:12%}100%{top:88%}}\n  .crtboot.flash{background:#EAF7FF}\n  /* 第三拍：导航栏入场（闪烁期间必须不可见 ✗ —— 由标记上的 dock--wait 保证，不靠 JS 时序）*/\n  .dock.dock--wait{opacity:0;transform:translateX(-6px)}\n  .dock.dock--wait.dock--in{opacity:1;transform:none;animation:none;\n    transition:opacity .35s ease-out,transform .35s cubic-bezier(.2,.8,.3,1)}\n  .dock.dock--wait:not(.dock--in){animation:dockSafety .35s ease-out 1500ms forwards}\n  @keyframes dockSafety{to{opacity:1;transform:none}}\n  @media (prefers-reduced-motion:reduce){\n    .crtboot,.crtboot.noise::after{display:none;animation:none}\n    .dock.dock--wait{opacity:1;transform:none;animation:none}\n  }\n  /* ★批次1（2026-10-15 站主决定）：三张背景层 .glow/.backplate/.plate **留在标记里**（与 T7 完全一致），\n     "T=0 只见壁纸"改用**可见性门控**实现 —— 不再把这三张图从标记里删掉。\n     phase 0 三层不可见 · phase 1 露 glow · phase 4 起三层全部可见 ⇒ 终态与 T7 逐像素一致 ✓\n     （删层那条路已被站主否掉：实测后果就是"房间全黑 / 背景像没了" ✗）。*/\n  html[data-xk-boot="0"] .glow,\n  html[data-xk-boot="0"] .backplate,\n  html[data-xk-boot="0"] .plate{opacity:0 !important}\n  html[data-xk-boot="1"] .backplate,\n  html[data-xk-boot="1"] .plate,\n  html[data-xk-boot="2"] .backplate,\n  html[data-xk-boot="2"] .plate,\n  html[data-xk-boot="3"] .backplate,\n  html[data-xk-boot="3"] .plate{opacity:0 !important}\n'
T31_JS = '\n/* ================= ★T31 开场六阶段（站主 2026-10-15 逐帧规格） =================\n   phase 0 壁纸        ：veil 撤下；CRT 仍是黑屏、导航栏隐藏（全部由 CSS/标记保证，无 JS 也成立）\n   phase 1 预载        ：首帧之后才插入 glow/backplate/plate 等图；CRT 底噪 = 加载信号\n   phase 2 黑屏闪烁    ：2~4 次，间隔 80~140ms 随机（亮度/扫描线抖动，不是正弦）\n   phase 3 大脸闪断    ：**等 opening 图真的就绪**才开始；2~3 次 60~100ms 硬切 + 1~3px 位移\n   phase 4 稳定+导航   ：**由"闪烁结束"这一事件触发**（不是猜时间的 setTimeout）\n   phase 5 正式动画    ：opening 继续播 → L1 既有推拉 → idle（推拉起点对齐到闪烁结束）\n   跳过：任意 pointerdown/keydown/wheel/touchstart ⇒ 撤闪烁层 + 导航栏立刻出现 + 直接进推拉\n   RM  ：直接最终稳定态（壁纸 + 稳定画面 + 导航栏），②③④ 的闪烁一律不做\n   验收钩子：window.__xkBoot.{phase,marks,log} ｜ #dock[data-xk-dock-in|data-xk-dock-at] */\nconst XK_BOOT = { phase: 0, t0: performance.now(), rm: RM, marks: {}, log: [], timers: [],\n                  skipped: false, revealed: false };\nwindow.__xkBoot = XK_BOOT;\nconst XK_BOOT_ON = !RM;   /* 新开场生效 ⇒ 关掉旧的"通电四拍"，两种闪烁不叠加 */\nfunction xkBootSet(p, why){\n  if(p <= XK_BOOT.phase) return;\n  XK_BOOT.phase = p;\n  XK_BOOT.marks[p] = Math.round(performance.now() - XK_BOOT.t0);\n  document.documentElement.setAttribute(\'data-xk-boot\', String(p));\n  if(why) XK_BOOT.log.push(p + \':\' + why);\n}\nfunction xkBootTimer(ms, fn){\n  const id = setTimeout(function(){ if(!XK_BOOT.skipped) fn(); }, ms);\n  XK_BOOT.timers.push(id);\n  return id;\n}\nfunction xkBootRnd(a, b){ return a + Math.random() * (b - a); }\nfunction xkBootBlink(hide){\n  const boot = document.getElementById(\'crtBoot\');\n  if(boot) boot.style.display = hide ? \'none\' : \'block\';\n}\nfunction xkBootPreload(){\n  /* ①→② 之间才请回来（首屏只算壁纸那一张）——元素位置/类名与原来逐字一致，只改"什么时候插入" */\n  const stage = document.getElementById(\'stage\'), clip = document.getElementById(\'crtClip\');\n  const canvas = document.getElementById(\'charCanvas\');\n  function mk(cls, src, parent, before){\n    const el = document.createElement(\'img\');\n    el.className = cls; el.alt = \'\'; el.setAttribute(\'aria-hidden\', \'true\'); el.src = src;\n    if(parent) parent.insertBefore(el, before || null);\n    return el;\n  }\n  try{\n    if(stage) mk(\'glow\', \'/kurisu/scene/amadeus_ambient_high_blend.webp\', stage, null);\n    if(clip) mk(\'backplate\', \'/images/crt/lab.webp\', clip, canvas || clip.firstChild);\n    if(clip) mk(\'plate\', \'/kurisu/scene/subtitle_frame_big.webp\', clip, clip.querySelector(\'.scan\'));\n  }catch(e){ XK_BOOT.log.push(\'preload:\' + e.message); }\n}\nfunction xkBootBlackFlicker(){\n  const boot = document.getElementById(\'crtBoot\');\n  const n = 2 + Math.floor(Math.random() * 3);          /* 2~4 次 */\n  (function step(i){\n    if(i >= n){ xkBootWaitFace(); return; }\n    const black = i % 2 === 0;\n    if(boot){\n      boot.classList.toggle(\'noise\', black);\n      boot.style.background = black ? \'#000\' : \'#0A0E12\';   /* 亮度跳一下（不规律，不是正弦）*/\n    }\n    xkBootTimer(xkBootRnd(80, 140), function(){ step(i + 1); });\n  })(0);\n}\nfunction xkBootWaitFace(){\n  /* ③ → ④：\n     必须先有"大脸"那一帧可画，闪断才有东西可露 ⇒ 等图真的就绪（不靠猜时间 ✗）；\n     断网/慢网：停在壁纸 + 保留加载信号，并给人读的说明（导航栏照样给，别把人关在黑屏里）。 */\n  const t0 = performance.now();\n  (function wait(){\n    const im = cache[CLIPS.opening.src] || cache[CLIPS.opening.bootSrc];\n    const ready = !!(im && im.complete && im.naturalWidth);\n    if(!ready && (performance.now() - t0) < 3000){ xkBootTimer(60, wait); return; }\n    if(!ready){\n      const st = document.getElementById(\'crtStatus\');\n      if(st){ st.hidden = false; st.innerHTML = \'SEC-LAB · <span class="ok">● 画面读不到</span><br>网络或素材未到位 · 导航仍可用\'; }\n      xkBootReveal(\'no-face\');\n      return;\n    }\n    xkBootFaceFlicker();\n  })();\n}\nfunction xkBootFaceFlicker(){\n  xkBootSet(3, \'face\');\n  const clip = document.getElementById(\'crtClip\');\n  const n = 2 + Math.floor(Math.random() * 2);          /* 2~3 次闪断 */\n  (function step(i){\n    if(i >= n){ xkBootReveal(\'flicker-end\'); return; }   /* ★导航栏＝闪烁结束事件触发 */\n    xkBootBlink(i % 2 === 0);                           /* 硬切，不是淡入 ✗ */\n    if(clip) clip.style.transform = \'translateX(\' + (Math.random() * 6 - 3).toFixed(1) + \'px)\';\n    xkBootTimer(xkBootRnd(60, 100), function(){ step(i + 1); });\n  })(0);\n}\nfunction xkBootReveal(why){\n  if(XK_BOOT.revealed) return;\n  XK_BOOT.revealed = true;\n  const boot = document.getElementById(\'crtBoot\');\n  const clip = document.getElementById(\'crtClip\');\n  if(clip) clip.style.transform = \'\';\n  if(boot && !RM){                                       /* 过冲白光 → 稳定 */\n    boot.classList.remove(\'noise\');\n    boot.style.background = \'\';\n    boot.classList.add(\'flash\'); boot.style.display = \'block\';\n    xkBootTimer(120, function(){\n      boot.style.display = \'none\'; boot.classList.remove(\'flash\');\n    });\n  } else { xkBootBlink(true); }\n  xkDockIn(why);                                          /* ★同一帧：导航栏出现 */\n  xkBootSet(4, \'stable\');\n  xkBootSet(5, \'play\');\n}\nfunction xkBootStart(){\n  if(RM){ xkBootBlink(true); xkBootSet(4, \'rm\'); xkBootSet(5, \'rm\'); xkDockIn(\'rm\'); return; }\n  xkBootTimer(150, function(){ xkBootPreload(); xkBootSet(1, \'preload\'); xkBootSet(2, \'black\'); xkBootBlackFlicker(); });\n}\nfunction xkBootSkip(){\n  if(!started || XK_BOOT.revealed) return;\n  XK_BOOT.skipped = true;\n  XK_BOOT.timers.forEach(function(id){ clearTimeout(id); });\n  xkBootReveal(\'skip\');\n  xkTransStart();                       /* 跳过 = 直接进正式动画（推拉起点与"闪烁结束"同一语义）*/\n}\nconst XK_T31_EV = [\'pointerdown\', \'keydown\', \'wheel\', \'touchstart\'];\nfunction xkT31Off(){ XK_T31_EV.forEach(function(ev){ removeEventListener(ev, xkBootSkip); }); }\nXK_T31_EV.forEach(function(ev){ addEventListener(ev, function(){ xkT31Off(); xkBootSkip(); }, {passive:true}); });\nlet dockShown = false;\nfunction xkDockIn(why){\n  if(dockShown) return;\n  const d = document.getElementById(\'dock\');\n  if(!d) return;\n  dockShown = true;\n  d.classList.add(\'dock--in\');\n  d.setAttribute(\'data-xk-dock-in\', why || \'auto\');\n  d.setAttribute(\'data-xk-dock-at\', String(Math.round(performance.now() - XK_BOOT.t0)));\n}\nfunction xkTransStart(t){\n  /* ★T31：把"opening 播完 → 等 idle 图就绪 → 起推拉"抽成一处，供"自然播完"与"跳过"共用。\n     自然路径传 rAF 的 t，TRANS 取值与抽之前逐字等价（行为零变化）。 */\n  if(cur !== \'opening\' || TRANS) return;\n  fi = CLIPS.opening.frames - 1;\n  const idleIm = xkClipIm(\'idle\').im;\n  const btIdle = img(CLIPS.idle.bootSrc);\n  if(btIdle && !(btIdle.complete && btIdle.naturalWidth)) btIdle.addEventListener(\'load\', ()=>{ if(cur === \'opening\' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = performance.now(); } }, {once:true});\n  if(idleIm.complete && idleIm.naturalWidth){ TRANS = (t === undefined ? performance.now() : t); }\n  else {\n    idleIm.addEventListener(\'load\', ()=>{ if(cur === \'opening\' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = performance.now(); } }, {once:true});\n    idleIm.addEventListener(\'error\', ()=>{ if(cur === \'opening\' && !TRANS) TRANS = performance.now(); }, {once:true});\n  }\n}\n'
T31_JS_ANCHOR = "const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;\n"
T31_TRANS_OLD = "          else if(cur === 'opening'){   /* ★L1：播完不硬切——等 idle 图就绪后进场推拉 */\n            fi = c.frames - 1;\n            const idleR = xkClipIm('idle');\n            const idleIm = idleR.im;\n            const btIdle = img(CLIPS.idle.bootSrc);\n            if(btIdle && !(btIdle.complete && btIdle.naturalWidth)) btIdle.addEventListener('load', ()=>{ if(cur === 'opening' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = performance.now(); } }, {once:true});\n            if(idleIm.complete && idleIm.naturalWidth){ TRANS = t; }\n            else {\n              idleIm.addEventListener('load', ()=>{ if(cur === 'opening' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = performance.now(); } }, {once:true});\n              idleIm.addEventListener('error', ()=>{ if(cur === 'opening' && !TRANS) TRANS = performance.now(); }, {once:true});\n            }\n          }"
T31_TRANS_NEW = '          else if(cur === \'opening\'){ xkTransStart(t); }   /* ★T31：抽成函数（"自然播完"与"跳过"共用）；本路径行为逐字不变 */'
# ⚠ T8 接手批（2026-10-15）钉的口径：原锚点是
#     "}else{\n  play('opening');\n}\nstarted = true; lastT = performance.now();"
#   但 T8 在 `}` 与 `started = true;` 之间插入了三行（window.__xkSmIsHome / xkSmBoot / setTimeout），
#   于是这个锚点不再匹配（实测：跑生成器直接 SystemExit '出现 0 次'）。
#   改成只钉 `started = true; lastT = performance.now();` 这一行（demo 主页里唯一一处）——
#   xkBootStart() 仍然紧贴在启动之前执行；中间那三行是**声明 + 一个 setTimeout 注册**，
#   执行顺序语义与原来的"紧跟 } 之后"完全一致 ✓。
T31_START_OLD = "\nstarted = true; lastT = performance.now();"
T31_START_NEW = "\nxkBootStart();   /* ★T31 开场六阶段：RM 直接稳定态；非 RM 150ms 后进 ②③④⑤ */\nstarted = true; lastT = performance.now();"
T31_DRAW_OLD = "  const imO = xkClipIm('opening').im, imI = xkClipIm('idle').im;\n  const W = canvas.width, H = canvas.height;\n  ctx.clearRect(0, 0, W, H);\n  const lastF = cOpen.frames - 1;\n  const sx = (lastF % cOpen.cols) * cOpen.cw, sy = Math.floor(lastF / cOpen.cols) * cOpen.ch;"
T31_DRAW_NEW = '  const oR = xkClipIm(\'opening\'), imI = xkClipIm(\'idle\').im;\n  const imO = oR.im, cO = oR.c;   /* ★T31：与"当前上屏那一张"同源 —— hi 未到位就画 boot 末帧（跳过时不会越界取空帧）*/\n  const W = canvas.width, H = canvas.height;\n  ctx.clearRect(0, 0, W, H);\n  const lastF = Math.min(fi, cO.frames - 1);   /* 自然播完时 fi = hi 末帧，取值与旧写法逐字相同 */\n  const sx = (lastF % cO.cols) * cO.cw, sy = Math.floor(lastF / cO.cols) * cO.ch;'
T31_PWR_OLD = "    /* ★CRT 通电：opening 开头先亮线展开再出画面（约 0.55s） */\n    if(PWR && cur === 'opening'){"
T31_PWR_NEW = '    /* ★T31：新开场六阶段自带走电闪烁（.crtboot 覆盖层：黑屏/亮线/过冲白光）⇒\n       旧的"通电四拍"不再叠加（XK_BOOT_ON 时直接走正常绘制，画布内容随时可被闪断露出）。 */\n    if(PWR && cur === \'opening\' && !XK_BOOT_ON){'
T31_GLOW_OLD = '  <img class="glow" src="/kurisu/scene/amadeus_ambient_high_blend.webp" alt="" aria-hidden="true">\n'
T31_GLOW_NEW = '  {{/* ★T31：.glow / .backplate / .plate 由 xkBootPreload() 在首帧之后才插入 ⇒ 首屏只请求壁纸那一张 */}}\n'
T31_BACKPLATE_OLD = '      <img class="backplate" src="/images/crt/lab.webp" alt="" aria-hidden="true">\n'
T31_PLATE_OLD = '      <img class="plate" src="/kurisu/scene/subtitle_frame_big.webp" alt="" aria-hidden="true">\n'
T31_CRTBOOT_ANCHOR = '    <div class="crt-status" id="crtStatus" hidden>'
T31_CRTBOOT_NEW = '    <div class="crtboot noise" id="crtBoot" aria-hidden="true"></div>\n    <div class="crt-status" id="crtStatus" hidden>'
T31_HTML_OLD = '<html lang="{{ site.Language.Lang | default `zh-CN` }}" data-xk-kurisu-mode="video">'
T31_HTML_NEW = '<html lang="{{ site.Language.Lang | default `zh-CN` }}" data-xk-kurisu-mode="video" data-xk-boot="0">'
if 'dock--wait' not in DOCK_HTML:
    raise SystemExit('T31: DOCK_HTML 没带 dock--wait（导航入场 class 丢了）')

DOCK_CSS = (
    '  /* 屏外：左侧竖排导航 dock（值逐字照 xk-demo/shell-style.html 的 .dock / .dock .brand / .dock a） */\n'
    '  .dock{position:fixed;left:0;top:14px;z-index:60;\n'
    '    display:flex;flex-direction:column;gap:2px;\n'
    '    background:var(--solid);border:1px solid var(--line2);border-left:none;border-radius:0 14px 14px 0;\n'
    '    padding:6px 4px 6px 2px;backdrop-filter:blur(4px);box-shadow:0 10px 34px rgba(0,0,0,.45)}\n'
    '  .dock .brand{font:600 11px var(--mono);color:var(--acc);letter-spacing:.08em;text-align:center;\n'
    '    padding:3px 6px 6px;border-bottom:1px solid var(--line);margin-bottom:4px}\n'
    '  .dock a{display:flex;align-items:center;background:none;border:1px solid transparent;\n'
    '    color:var(--mut);font:13px var(--sans);padding:7px 10px 7px 8px;border-radius:0 9px 9px 0;cursor:pointer;\n'
    '    text-align:left;white-space:nowrap;text-decoration:none}\n'
    '  .dock a.on{color:var(--acc);border-color:var(--line2);background:rgba(57,208,216,.1);font-weight:500}\n'
    '  .dock a:hover{color:var(--txt)}\n'
    + T31_CSS + '\n'
    '  @media (max-width:980px){\n'
    '    .dock{left:8px;top:auto;bottom:10px;transform:none;flex-direction:row;max-width:calc(100vw - 16px);overflow-x:auto}\n'
    '    .dock .brand{display:none}\n'
    '    /* ★窗口 Q（2026-10-16）移动端硬伤 3（配对修复）：主页 dock 也是 <a>，值同 shell-style 的那一组 */\n'
    '    .dock{gap:4px;padding:6px}\n'
    '    .dock a{min-height:44px;min-width:44px;justify-content:center;padding:13px 10px}\n'
    '  }\n')
ROOT_ANCHOR = ('    --sans:"Segoe UI","Microsoft YaHei",system-ui,sans-serif;\n'
               '    /* —— 来自 static/kurisu/manifest.json scene.*（底图 1672×941） —— */\n')
DOCK_VARS = ('    /* —— 左侧 dock 用到的变量：值逐字取自 xk-demo/shell-style.html 的 :root（warm 口径） —— */\n'
             '    --line:rgba(255,246,235,.15);\n'
             '    --line2:rgba(255,246,235,.28);\n'
             '    --txt:#FAF7F0; --mut:#D2CBBD;\n'
             '    --acc:#7FD4D8;\n'
             '    --solid:rgba(48,45,41,.82);\n')
home_body = home_body.replace(NAVPILL_HTML, DOCK_HTML)
home_style = home_style.replace(NAVPILL_CSS, DOCK_CSS)
home_style = home_style.replace(ROOT_ANCHOR, ROOT_ANCHOR + DOCK_VARS, 1)
if 'navpill' in home_body or 'navpill' in home_style:
    raise SystemExit('主页还残留 .navpill（标记或 CSS）——demo 文件动过？')
if 'href="#">' in home_body:
    raise SystemExit('主页还有没换掉的 href="#"')

chrome = rewrite_dock(rewrite_assets(chrome))
shell_scripts = [rewrite_assets(s) for s in scripts]

# ---------------------------------------------------------- ③ 行为级懒加载（站主 2026-10-14 第四批口径）
# 站主裁定："允许'行为级'懒加载，但不许改版式；只改加载时机；首屏可见的东西必须照 demo 立刻载"。
# 下面每一条都是**只改加载时机**、渲染逻辑与数值逐字不动；每条都带硬断言，pattern 变了就报错，
# 不让补丁悄悄失效（否则字节会反弹而没人知道）。
LAZY_PATCHES = [
    # ① v-home 那一屏的 4 张图：五个内容页上 v-home 是 display:none（不进首屏），lazy 后不载。
    #    它们的 src 一个字节没改；点进主页走的是 / 那页自己的文件。
    ('<img class="desk" src=', '<img loading="lazy" class="desk" src=', 'views'),
    ('<img class="glow" src=', '<img loading="lazy" class="glow" src=', 'views'),
    ('<img class="backplate" src=', '<img loading="lazy" class="backplate" src=', 'views'),
    ('<img class="plate" src=', '<img loading="lazy" class="plate" src=', 'views'),
    # ② 背景选择器的 10 张缩略图：都在关着的弹层里（display:none）→ lazy；
    #    当前那张背景是 #bgEl 的 CSS background（setBg），照 demo 立刻载，不受影响。
    ('<img src="${b.file}" alt="${b.name}">', '<img loading="lazy" src="${b.file}" alt="${b.name}">', 'script0'),
    # ③ 头像泡（body.holo-min 才显示）的图：折叠时才载；折叠动作里补一次 render()，行为不变。
    ('bubbleAv.set(EMOS[emo].idle);',
     "if(document.body.classList.contains('holo-min')) bubbleAv.set(EMOS[emo].idle);", 'script0'),
    ("document.getElementById('holoFold').onclick = ()=>document.body.classList.add('holo-min');",
     "document.getElementById('holoFold').onclick = ()=>{ document.body.classList.add('holo-min'); render(); };", 'script0'),
    # ④ 面板头像在 body.is-ai（面板被 CSS 隐藏）时不载；手机全身图集在 v-ai 不显示时不载。
    #    可见的那一份仍然立刻载：非 ai 页载面板头像，ai 页载手机全身序列（speaking.hi）。
    ('  panelAv.set(strip);',
     "  if(!document.body.classList.contains('is-ai')) panelAv.set(strip);", 'script0'),
    # ③+④ 头像泡：折叠态才显示，且 /ai/ 页整块 holo 都被 CSS 隐藏 ⇒ 两张都别空取（只改加载时机）。
    ("  if(document.body.classList.contains('holo-min')) bubbleAv.set(EMOS[emo].idle);",
     "  if(document.body.classList.contains('holo-min') && !document.body.classList.contains('is-ai')) bubbleAv.set(EMOS[emo].idle);",
     'script0'),
    # ④b 手机全身序列：只有 v-ai 那一屏显示时才取（原表达式逐字搬进 setPhone()，取值一字未改）。
    ("  phoneBody.set(BODY[mode === 'speaking' ? 'speaking' : (emo === 'sided_thinking' ? 'thinking' : 'idle')]);",
     "  if(document.getElementById('v-ai').classList.contains('on')) setPhone();",
     'script0'),
    # ⑤ ★2026-10-16 ①（冷缓存首屏）：**只改加载时机，不改渲染逻辑/数值** ——
    #    /ai/ 页首帧那次 render() 不要空取全身图集（speaking.hi.webp 1554.7KB）：
    #      · 实测冷缓存直访 /ai/ = 1652KB > 1650KB 预算，超支项**就是**这一张（+ 84.7KB 头像 + favicon）；
    #      · 往后推 1800ms（越过门禁 1.5s 窗口，与"统一播放器按需加载"同一时刻）即可回到预算内；
    #      · 2600ms 那次 render()（mode→idle）与任何用户手势（提问/切情绪/折叠）都照原样立刻取 ⇒
    #        可见之后的行为逐字不变，只是"页面还没被操作的最初 1.65 秒"不抢这一张。
    #    判据：--cold 的 /ai/ ≤ 1650KB；--warm 五页回归不变；改前改后截图对拍。
    ('const holo = document.getElementById(\'holo\');',
     "var __xkPhoneDefer = document.body.classList.contains('is-ai');   /* /ai/：首帧不空取全身图集，1650ms 后允许 */\nconst holo = document.getElementById('holo');",
     'script0'),
    # 手机全身图集的"取哪一档"：抽成一个函数，两个分支**都是原表达式逐字**，
    # 只是在延后窗口里改成"先别取"，并把状态标签如实写成"连接中"（不谎报 SPEAKING）。
    ("function render(){\n  const strip = EMOS[emo][mode === 'speaking' ? 'speaking' : 'idle'];",
     "function setPhone(){\n  if(__xkPhoneDefer){ phoneStateEl.textContent = '连接中'; return; }\n  phoneBody.set(BODY[mode === 'speaking' ? 'speaking' : (emo === 'sided_thinking' ? 'thinking' : 'idle')]);\n}\nfunction render(){\n  const strip = EMOS[emo][mode === 'speaking' ? 'speaking' : 'idle'];",
     'script0'),
    ("  phoneStateEl.textContent = label;",
     "  phoneStateEl.textContent = __xkPhoneDefer ? '连接中' : label;",
     'script0'),
    ("/* ============ 页面切换 ============ */",
     "/* ★2026-10-16 ①：/ai/ 首帧 render() 里的手机全身图集延到 1650ms（越过首屏 1.5s 窗口；\n   实测请求落在 ~1755ms，距窗口边界留 ~255ms）+ 状态标签在这段里如实写'连接中'。\n   其余页照原样立刻 render()（首屏可见的东西不变慢），2600ms 那次 render() 也照原样立刻取。 */\nif(__xkPhoneDefer){ setTimeout(function(){ __xkPhoneDefer = false; render(); }, 1650); }\n/* ============ 页面切换 ============ */",
     'script0'),
]

views_out = '\n'.join(chunks)
for old, new, where in LAZY_PATCHES:
    if where == 'views':
        if views_out.count(old) != 1:
            raise SystemExit('懒加载补丁对不上（%s 出现 %d 次）：%s' % (where, views_out.count(old), old[:60]))
        views_out = views_out.replace(old, new)
    else:
        if shell_scripts[0].count(old) != 1:
            raise SystemExit('懒加载补丁对不上（%s 出现 %d 次）：%s' % (where, shell_scripts[0].count(old), old[:60]))
        shell_scripts[0] = shell_scripts[0].replace(old, new)

LAZY_NOTE = u'''
  /* ★ 生产站差异（站主第四批口径③"允许行为级懒加载，不许改版式"）：下面这几处**只改加载时机**，
     渲染逻辑/数值/结构逐字未动 —— 见 _dev/gen-demo-pages.py 的 LAZY_PATCHES。
       · v-home 的 4 张场景图加 loading="lazy"（五个内容页上 v-home 是 display:none，不进首屏）
       · 背景选择器 10 张缩略图加 loading="lazy"（在关着的弹层里）；当前背景仍立刻载
       · 头像泡（折叠后才显示）与"面板/手机各自不可见时"的图集不载；可见的那一份照 demo 立刻载
     判据：对拍像素差不变（_shots/demopage-*-side.png）+ 五页首屏回到 ≤1600KB。
  */
'''
views_out = rewrite_assets(views_out)

# =====================================================================================
# 第十二批（站主 2026-10-14 第二批口径）：**demo 只是原型，它自带的这些东西都不是作者意图**
#   口径原文："不是和 demo 文件一模一样，是要和作者想呈现的效果一模一样"
#   ① 删掉顶部"演示"横幅（`.demo-flag` 元素 + 它的 CSS）—— 六页同款一并处理
#   ② 演示数字 → 真实接口值：模板里的假数字全部清空，真值由 layouts/partials/xk-demo/api-bind.html
#      写进 **demo 原有元素**（取不到由它写"读不到"）
#   ③ 实时攻击流的"行叠行"：行数按容器高度实算 + 数据换成 /api/public/alerts 的真实告警
#   ④ CRT 顶部暗块：`.plate` 末尾那句 `inset:auto` 把它自己前面的 left/bottom 全抵消了，
#      垫板（subtitle_frame_big.webp）于是跑到 CRT 左上角 —— 删掉 inset:auto 即回到"底部垫板"
# 每条补丁都带硬断言：对不上就报错，不让补丁悄悄失效。
# =====================================================================================


def sub1(s, old, new, what):
    if s.count(old) != 1:
        raise SystemExit('第十二批补丁对不上（%s）：出现 %d 次 —— %s' % (what, s.count(old), old[:80]))
    return s.replace(old, new)


def subn(s, pat, new, n, what):
    out, got = re.subn(pat, new, s, flags=re.S)
    if got != n:
        raise SystemExit('第十二批补丁对不上（%s）：匹配 %d 次（期望 %d）' % (what, got, n))
    return out


def strip_demo_flag_body(s, what):
    return subn(s, r'\n?<div class="demo-flag">[^<]*</div>\n', '\n', 1, what)


def strip_demo_flag_css(s, what):
    return subn(s, r'\n  \.demo-flag\{[^}]*\}\n', '\n', 1, what)


def fix_plate(s, what):
    """④ CRT 顶部暗块：删掉 `.plate` 末尾那句把 left/bottom 抵消掉的 inset:auto。"""
    s, n = re.subn(r'(  \.plate\{[^}]*?);inset:auto\}', r'\1}', s, flags=re.S)
    if n != 1:
        raise SystemExit('第十二批补丁对不上（%s .plate）：匹配 %d 次' % (what, n))
    return sub1(s, '  .plate{', PLATE_NOTE + '  .plate{', what + ' .plate 注释')


# ---- ① 删横幅（元素 + 死 CSS）----
home_body = strip_demo_flag_body(home_body, '主页 demo-flag')
chrome = strip_demo_flag_body(chrome, '外壳 demo-flag')
home_style = strip_demo_flag_css(home_style, '主页 .demo-flag CSS')
shell_style = strip_demo_flag_css(shell_style, '外壳 .demo-flag CSS')

# ---- ④ 修 .plate（顶部暗块）：删掉那句把 left/bottom 抵消掉的 inset:auto ----
PLATE_NOTE = (u'  /* ★ 第十二批修正（站主：CRT 内景顶部有一块发暗的矩形）：demo 的 .plate 末尾写着\n'
              u'     `inset:auto`，它把同一条规则前面的 left/bottom 全部抵消 → 垫板被当成"四边 auto"的\n'
              u'     绝对定位元素，落在 CRT 左上角（就是那块暗色矩形）。删掉 inset:auto 即回到作者意图：\n'
              u'     垫板贴在屏幕底部、宽 72%（字幕条就压在它上面）。 */\n')
for _name in ('home_style', 'shell_style'):
    if _name == 'home_style':
        home_style = fix_plate(home_style, '主页')
    else:
        shell_style = fix_plate(shell_style, '外壳')

# ---- ③ 甜甜圈：模板里不留假的百分比（真值由 api-bind 写 inline conic-gradient）----
shell_style = sub1(
    shell_style,
    u'    background:conic-gradient(var(--acc) 0 46%,var(--warn) 46% 72%,var(--acc2) 72% 88%,var(--ok) 88% 100%)}',
    u'    background:rgba(140,160,180,.18)}   /* ★第十二批：真值由 api-bind 从 /api/public/overview 写 inline conic-gradient */',
    '外壳 .donut 假百分比')

shell_style = sub1(
    shell_style,
    u'  .threat .lv{font:700 22px var(--mono);color:var(--warn)}',
    u'  .threat .lv{font:700 22px var(--mono);color:var(--warn);white-space:nowrap}   /* ★第十二批：等级字不许被旁边的口径挤成两行 */',
    '外壳 .threat .lv nowrap')

# ---- ② 清掉外壳标记里的假数字（真值由 api-bind 写进这些"原元素"）----
VL = [
    # CRT 状态行（v-home，五个内容页上它是隐藏的，主页是可见的）
    ('24h 告警 1,284 · 拦截 96', '24h 告警 — · 拦截 —'),
    ('蜜罐交互 37 · sync 12s', '蜜罐交互 — · sync —'),
    # 作战室顶栏
    ('● SYNC 12s 前 · 全部来自 /api/public/* 只读端点',
     '● 取数中… · 全部来自 /api/public/* 只读端点'),
    ('<span class="term-path">tail -f /var/log/xk-lab/alerts.log</span>',
     '<span class="term-path">GET /api/public/alerts · 只读聚合（5 分钟窗口）</span>'),
    # 威胁等级
    ('<span class="lv">较高</span><span class="trend">▲ 较 24h 前 +12%</span>',
     '<span class="lv">—</span><span class="trend">取数中…</span>'),
    # TOP 攻击来源（4 行）
    ('<span class="k">45.155.x.x · 中国</span><span class="chip bad">412 次</span>',
     '<span class="k">—</span><span class="chip">—</span>'),
    ('<span class="k">185.220.x.x · 荷兰</span><span class="chip warn">238 次</span>',
     '<span class="k">—</span><span class="chip">—</span>'),
    ('<span class="k">91.240.x.x · 俄罗斯</span><span class="chip warn">197 次</span>',
     '<span class="k">—</span><span class="chip">—</span>'),
    ('<span class="k">103.99.x.x · 新加坡</span><span class="chip">121 次</span>',
     '<span class="k">—</span><span class="chip">—</span>'),
    # 蜜罐捕获凭据（4 行）
    ('<span class="k">root / admin···</span><span class="chip">×61 · 字母+数字</span>',
     '<span class="k">—</span><span class="chip">—</span>'),
    ('<span class="k">admin / passw···</span><span class="chip">×44 · 纯数字</span>',
     '<span class="k">—</span><span class="chip">—</span>'),
    ('<span class="k">oracle / 1234···</span><span class="chip">×38 · 含特殊字符</span>',
     '<span class="k">—</span><span class="chip">—</span>'),
    ('<span class="k">pi / raspbe···</span><span class="chip">×22 · 字典命中</span>',
     '<span class="k">—</span><span class="chip">—</span>'),
    # 24h 时序图的来源标签（真数据来自 /alerts 的 stats24h）
    ('24 小时攻击时序<span class="tag">/overview</span>',
     '24 小时攻击时序<span class="tag">/alerts · stats24h</span>'),
    # 攻击图谱：数据来自 /alerts（来源 IP）+ /honeypot（客户端指纹）
    ('<span class="tag">动画 · 数据 /alerts</span>', '<span class="tag">数据 /alerts + /honeypot</span>'),
    # 四个数字（data-count 清空；标签改成与真实字段一致，避免"名字对不上数"）
    ('<div class="n" data-count="1284">0</div>', '<div class="n" data-count="">—</div>'),
    ('<div class="n" data-count="96">0</div>', '<div class="n" data-count="">—</div>'),
    ('<div class="n" data-count="37">0</div>', '<div class="n" data-count="">—</div>'),
    ('<div class="n" data-count="22">0</div>', '<div class="n" data-count="">—</div>'),
    ('<div class="l">暴力破解拦截</div>', '<div class="l">护栏拦截（/audit）</div>'),
    ('<div class="l">活跃攻击源</div>', '<div class="l">来源网段 24h（/geo）</div>'),
    # 威胁矩阵：服务端没有 ATT&CK 战术字段 → 改成"服务端真实给的告警类型"，不编映射
    ('ATT&amp;CK 威胁矩阵 · 真实告警自动归类<span class="tag">MITRE ATT&amp;CK</span>',
     '告警类型矩阵 · 每格是服务端给的类型标签<span class="tag">/alerts · stats.byType</span>'),
    ('<p class="attk-note">每格是一种攻击战术，数字为本站真实命中次数（演示为样例值）；命中越多颜色越热，线上可点击下钻到对应告警。</p>',
     '<p class="attk-note">每格的数字是本站 <code class="k">/api/public/alerts</code> 的 '
     '<code class="k">stats.byType</code> 真实计数（类型标签由服务端给，前端不编 ATT&amp;CK 映射）；'
     '命中越多颜色越热。取不到就把整块标成读不到，不补样例值。</p>'),
    # 访问统计：来源标签换成真实端点
    ('7×24 访问统计<span class="tag">类别门槛 ≥5 · 零 IP</span>',
     '7×24 访问统计 · 按整点聚合<span class="tag">/webstats · 零 IP</span>'),
    # 告警来源分布（原"协议分布"）：真值来自 overview.alerts.bySource
    ('协议分布 · 按传感器类型<span class="tag">/overview</span>',
     '告警来源分布 · 按传感器类型<span class="tag">/overview · bySource</span>'),
    ('<div class="donut"><span class="donut-c">24h</span></div>',
     '<div class="donut"><span class="donut-c">—</span></div>'),
    ('<li><i class="lg teal"></i>SSH 暴力破解<b>46%</b></li>', '<li><i class="lg teal"></i>—<b>—</b></li>'),
    ('<li><i class="lg warn"></i>端口扫描<b>26%</b></li>', '<li><i class="lg warn"></i>—<b>—</b></li>'),
    ('<li><i class="lg purp"></i>Web 攻击<b>16%</b></li>', '<li><i class="lg purp"></i>—<b>—</b></li>'),
    ('<li><i class="lg ok"></i>IoT / 其他<b>12%</b></li>', '<li><i class="lg ok"></i>—<b>—</b></li>'),
    # 手机时钟（demo 写死 21:47；真值由页面自己的 tickClock 写）
    ('<span id="phoneClock">21:47</span>', '<span id="phoneClock">—</span>'),
]
for _old, _new in VL:
    views_out = sub1(views_out, _old, _new, 'views: ' + _old[:40])

# ---- ②b 主页自己的 CRT 状态行假数字（VL 只清五页 views_out 的副本；主页这份在 home_body）----
home_body = sub1(home_body,
                 u"      SEC-LAB · <span class=\"ok\">● LIVE</span><br>\n"
                 u"      24h 告警 1,284 · 拦截 96<br>\n"
                 u"      蜜罐交互 37 · sync 12s",
                 u"      SEC-LAB · <span class=\"ok\">● —</span><br>\n"
                 u"      24h 告警 — · 拦截 —<br>\n"
                 u"      蜜罐交互 — · sync —   /* ★T5.4：静态占位，真值由 api-bind 从 /api/public/* 写 */",
                 '主页 CRT 状态行假数字')

# ---- ②c T5.5：v-notes 的 4 条死笔记 → /posts/ 页渲染真实文章链接（Hugo range，同 class 不改视觉）----
views_out = sub1(views_out,
                 u'      <div class="note"><span class="dt">2026-10-12</span><div><div class="tt">用 Cowrie 观察一次真实的 SSH 扫密</div><div class="ds">凭据结构分析 · 蜜罐 · 12 min</div></div></div>\n'
                 u'      <div class="note"><span class="dt">2026-10-08</span><div><div class="tt">Suricata 规则调优：减少误报的五个开关</div><div class="ds">IDS · 调优 · 8 min</div></div></div>\n'
                 u'      <div class="note"><span class="dt">2026-09-30</span><div><div class="tt">Wazuh 最小权限接入实践</div><div class="ds">SIEM · 权限 · 10 min</div></div></div>\n'
                 u'      <div class="note"><span class="dt">2026-09-18</span><div><div class="tt">Dionaea 多协议蜜罐上线记录</div><div class="ds">蜜罐 · 部署 · 6 min</div></div></div>',
                 u'{{ if eq .page.Section "posts" }}{{ range .page.Pages }}<div class="note"><span class="dt">{{ .Date.Format "2006-01-02" }}</span>'
                 u'<div><a class="tt" href="{{ .RelPermalink }}" style="color:inherit;text-decoration:none">{{ .Title }}</a>'
                 u'<div class="ds">阅读约 {{ .ReadingTime }} min</div></div></div>{{ end }}{{ end }}',
                 'v-notes: 真文章链接')

# 7×24 的 28 根柱子：清掉写死的高度（真值由 api-bind 按 /webstats heatmap 写）
views_out = subn(views_out, r'<i style="height:\d+%;--i:(\d+)"></i>', r'<i style="--i:\1"></i>', 28, 'views: bars 28 根')
# 来源 TOP5 的 5 行
views_out = subn(views_out,
                 r'<li><span class="cc">[^<]*</span><span class="bar"><i style="width:\d+%"></i></span><span>[^<]*</span></li>',
                 '<li><span class="cc">—</span><span class="bar"><i style="width:0%"></i></span><span>—</span></li>',
                 5, 'views: geo TOP5')
# 故事线的 4 行
views_out = subn(views_out,
                 r'<span class="k">T\+\d+s</span><span>[^<]*</span><span class="chip[^"]*">[^<]*</span>',
                 '<span class="k">—</span><span>取数中…</span><span class="chip">—</span>',
                 4, 'views: 故事线 4 行')

# ---- ⑭ 聊天区：清掉 demo 写死的假问答（站主口径"演示数据一律清掉 / 绝不编答案"）----
#   demo 的 chatlog 预置了一问一答（"那我们昨天被谁打了？" + 一段写死的"拒答"）——
#   看着像真实交互，其实是死文本。删掉这两条，只留一句如实的开场说明。
#   （开场那句的 state 标注也从"模型研判"改成"公开只读"：还没提问就标"模型研判"是假的。）
views_out = subn(
    views_out,
    r'\n\s*<div class="msg me">那我们昨天被谁打了？</div>\s*\n\s*<div class="msg ai"><div class="who">AI 安全 · <span class="st">规则解析（拒答）</span></div>[^<]*</div>',
    '\n', 1, 'views: 清掉聊天区写死的假问答')
views_out = sub1(
    views_out,
    '<div class="who">AI 安全 · <span class="st">模型研判</span></div>你好，这里是公开只读的安全知识库问答。',
    '<div class="who">AI 安全 · <span class="st">公开只读</span></div>你好，这里是公开只读的安全知识库问答。',
    'views: 聊天区开场状态标注')

# ---- ② HOLO 面板那句话：先清掉假数字（api-bind 会重写这句话，仍是"原元素"）----
chrome = sub1(
    chrome,
    '过去 24 小时拦截了 <span class="qk">96 次</span> 暴力破解，蜜罐记录了 <span class="qk">37 条</span> 交互。都在「监测中心」的大屏里。',
    '公开只读端点汇总：护栏拦下 <span class="qk">—</span> 个动作，蜜罐累计事件 <span class="qk">—</span> 条。明细都在「监测中心」的大屏里。',
    'chrome: holo-say 假数字')

# ---- ⑤ demo 自身缺陷：五页的 scene-js 依赖不存在的 #fallback / #bootveil ----
# 【2026-10-15 T1 已修】判据收紧：原来是"CRT 高度 <260px 就降级"—— 手机横屏 CRT 实测 224px，
#   被整屏 fallback（position:fixed;inset:0;z-index:70）盖住 ⇒ 动画被静帧顶掉（站长投诉"动画不放"根因 ✓ CDP 实测）。
#   现在 = 只有"桌面细指针 + 高度不足"才降级；触屏（pointer:coarse = 手机/平板）一律播动画，只是更小。
#   桌面窄窗降级行为不变（视觉不变，只改判据 ✓）。
#   注：第十二批的存在性判断已应用 ✓；当时"与首屏预算耦合、暂不整体应用"的顾虑，
#   存在性判断部分照常应用，阈值部分由本条 T1 修订。
S_FALLBACK_OLD = "document.getElementById('fallback').style.display = r.height < 260 ? 'grid' : 'none';"
S_FALLBACK_NEW = ("const fb = document.getElementById('fallback');   /* ★第十二批：五个内容页没有 #fallback，\n"
                  "      demo 这里直接 .style 会抛 TypeError 让整个 IIFE 中止 —— 加存在性判断，行为不变 */\n"
                  "  /* ★2026-10-15 T1：桌面窄窗才降级；触屏（手机/平板）一律播动画，只是更小。视觉不变 */\n"
                  "  if(fb) fb.style.display = (r.height < 260 && !matchMedia('(pointer: coarse)').matches) ? 'grid' : 'none';")
S_BOOT_OLD = ("document.getElementById('bootveil').style.opacity = 0;\n"
              "  setTimeout(()=>document.getElementById('bootveil').remove(), 450);")
S_BOOT_NEW = ("const bv = document.getElementById('bootveil');   /* ★第十二批：同上，五个内容页没有 #bootveil */\n"
              "  if(bv){ bv.style.opacity = 0; setTimeout(()=>bv.remove(), 450); }")
S_VEIL_OLD = ("const veil = document.getElementById('bootveil');\n"
              "const desk = document.querySelector('.desk');\n"
              "(desk.complete ? Promise.resolve() : new Promise(r=>desk.onload=r)).then(()=>{\n"
              "  veil.style.opacity = 0; setTimeout(()=>veil.remove(), 450);\n"
              "});")
S_VEIL_NEW = ("const veil = document.getElementById('bootveil');   /* ★第十二批：同上，加存在性判断 */\n"
              "const desk = document.querySelector('.desk');\n"
              "(desk && !desk.complete ? new Promise(r=>desk.onload=r) : Promise.resolve()).then(()=>{\n"
              "  if(veil){ veil.style.opacity = 0; setTimeout(()=>veil.remove(), 450); }\n"
              "});")

# ---- ③/② 外壳脚本：真实攻击流 + 真 24h 时序 + 真图谱数据 + 真类型矩阵 + 真数字滚动 ----
S_FEED_NEW = u'''/* 实时攻击流 —— ★第十二批重写（站主：①不许假数字 ②修"行叠行"）
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
  el.className = 'tl';
  el.innerHTML = `<span class="ts">${xkEsc(it.ts)}</span> <span class="tg ${it.cls}">${xkEsc(it.tag)}</span> ${xkEsc(it.text)}`;
  termFeed.appendChild(el);
}
function feedTrim(){
  const cap = feedCap();
  while(termFeed.querySelectorAll('.tl').length > cap) termFeed.removeChild(termFeed.querySelector('.tl'));
  termFeed.appendChild(tcursor);
}
function renderFeed(){
  const items = window.XK_FEED;
  if(!items){
    termFeed.innerHTML = '';
    feedRow({ts:'--:--:--', cls:'dns', tag:'[读不到]', text:'/api/public/alerts 本次取不到（不可达或被拦）—— 不补样例值'});
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
'''

S_SPARK_NEW = u'''/* 24 小时攻击时序 —— ★第十二批重写：数据改成 /api/public/alerts 的 stats24h.trend
   （25 个小时桶真实计数，由 api-bind 写进 window.XK24H）；取不到就清空画布 + 表头写"读不到"，
   不再用 Math.sin + 取模画一条看着像波形的假曲线（原实现就是这么画的）。 */
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
  const yOf = v => (h-8) - (h-16) * (v/max);
  const area = ()=>{
    x.beginPath(); x.moveTo(0,h);
    vals.forEach((v,i)=>x.lineTo(i/(vals.length-1)*w, yOf(v)));
    x.lineTo(w,h); x.closePath();
    x.fillStyle = 'rgba(127,212,216,.10)'; x.fill();
  };
  const line = upto=>{
    x.beginPath();
    const n = Math.max(2, Math.ceil(vals.length*upto));
    for(let i=0;i<n;i++){ const px = i/(vals.length-1)*w; i===0 ? x.moveTo(px,yOf(vals[i])) : x.lineTo(px,yOf(vals[i])); }
    x.strokeStyle = '#7FD4D8'; x.lineWidth = 1.6; x.stroke();
  };
  area();
  if(RM || sparkDone){ line(1); return; }
  sparkDone = true;
  const t0 = performance.now(), dur = 1100;
  (function step(t){
    const k = Math.min(1,(t-t0)/dur);
    x.clearRect(0,0,w,h); area(); line(k);
    if(k<1) requestAnimationFrame(step);
  })(t0);
}
window.__xkSpark = drawSpark;
drawSpark();
'''

S_ATTK_NEW = u'''/* 告警类型矩阵 —— ★第十二批重写（原来是写死的 TACTIC_HITS 样例值）。
   服务端没有 ATT&CK 战术字段，所以这里一格 = 服务端真实给的一个类型标签 + /alerts 的
   stats.byType 真实计数；映射关系由服务端给，前端不编。取不到就写"读不到"。 */
const attkGrid = document.getElementById('attkGrid');
function renderTypes(){
  if(!attkGrid) return;
  const rows = window.XK_TYPES;
  attkGrid.innerHTML = '';
  if(!rows || !rows.length){
    attkGrid.innerHTML = '<div class="cell"><b>读不到</b><span class="taid">/api/public/alerts</span><div class="num">—</div></div>';
    return;
  }
  const max = Math.max.apply(null, rows.map(r=>Number(r.count)||0)) || 1;
  rows.forEach((r,i)=>{
    const hit = Number(r.count) || 0;
    const cell = document.createElement('div');
    cell.className = 'cell' + (hit/max >= .6 ? ' fire' : hit>0 ? ' hot' : '');
    cell.innerHTML = `<b>${xkEsc(r.label || r.key || '—')}</b><span class="taid">${xkEsc(r.key || '')}</span>` +
      `<div class="num">${hit.toLocaleString('en-US')}</div>`;
    attkGrid.appendChild(cell);
  });
}
window.__xkRenderTypes = renderTypes;
'''

S_COUNTERS_NEW = u'''let counted = false;
function runCounters(){
  counted = true;
  /* ★第十二批：data-count 为空 = 该数字这次没取到 → 写"读不到"，**不写 0 冒充**；
     真值由 api-bind 从真实端点写进 data-count 与文本。 */
  document.querySelectorAll('[data-count]').forEach(el=>{
    const raw = el.dataset.count, T = Number(raw);
    if(raw === '' || raw === undefined || !isFinite(T)){ el.textContent = '读不到'; return; }
    if(RM){ el.textContent = T.toLocaleString('en-US'); return; }
    const t0 = performance.now(), dur = 900;
    (function step(t){
      const k = Math.min(1,(t-t0)/dur);
      el.textContent = Math.round(T*(1-Math.pow(1-k,3))).toLocaleString('en-US');
      if(k<1) requestAnimationFrame(step);
    })(t0);
  });
}
'''

# （站主砍范围：上面 S_FALLBACK/S_BOOT/S_VEIL 三条补丁本轮**不应用** · 理由见那段注释）

sc = shell_scripts[0]
sc = subn(sc, r'/\* 实时攻击流 \*/.*?\}, 1500\);', lambda m: S_FEED_NEW, 1, 'shell: 攻击流整块')
sc = subn(sc, r'/\* 24h 时序 sparkline.*?\ndrawSpark\(\);', lambda m: S_SPARK_NEW, 1, 'shell: 24h 时序整块')
sc = subn(sc, r'/\* ATT&CK 矩阵（中文版） \*/.*?\n\}\);\n', lambda m: S_ATTK_NEW, 1, 'shell: 类型矩阵整块')
sc = subn(sc, r'let counted = false;\nfunction runCounters\(\)\{.*?\n\}\n', lambda m: S_COUNTERS_NEW, 1, 'shell: 数字滚动')

# ---- ⑬ AI 问答：把 demo 的"900ms 后插一段固定文本"换成**真实链路** POST /api/public/ask ----
# 【2026-10-15 接手批】原 demo 的 askDemo() 是个纯前端假实现：等 900ms 插一段写死的回答 +
#   假引用卡片，一个网络请求都不发（实测：/ai/ 页 0 个 /api/public/ask 请求）。
#   后端 /api/public/ask 早已上线（线上实测 200、多 Agent 编排、带引用与状态标注、跨域显式白名单已通），
#   所以这里按站点既有纪律把它接真：
#     · 真实 POST；state / stateLabel / citations / failureReason / quota / clientIpMasked 全部如实展示；
#     · generated=false 就写服务端给的原因，**不补一段"像答案"的文字**；
#     · 接口失败/超时/限流 → 如实写"请求失败 / 超时 / 被限流"，绝不返回替代答案；
#     · 不做 SSE/WebSocket（公开面只有一次性 POST），最多等 20 秒，429 按 Retry-After 倒计时。
#   接口基址只从 <meta name="wb-api"> 读（与 api-bind.html 同一处口径，JS 不写死域名）。
ASK_REAL = r'''/* ============ AI 问答（真实链路：POST /api/public/ask） ============ */
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
  'injection-blocked':['命中提示注入护栏']
};
function xkAskEsc(s){ return String(s==null?'':s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
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
    return '<p>'+lines.map(xkInline).join('<br>')+'</p>';
  }).join('');
}
let xkAsking = false;
function xkAskApi(question){
  const ctrl = (typeof AbortController === 'function') ? new AbortController() : null;
  const timer = setTimeout(()=>{ if(ctrl) ctrl.abort(); }, XK_ASK_TIMEOUT);
  return fetch(XK_ASK_API + '/api/public/ask', {
    method:'POST', headers:{'Content-Type':'application/json'},
    mode:'cors', credentials:'omit', cache:'no-store',
    signal: ctrl ? ctrl.signal : undefined,
    body: JSON.stringify({ question: String(question).slice(0, XK_ASK_MAX) })
  }).then(res=>{ clearTimeout(timer);
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
  q.textContent = (d && d.quota && d.quota.pool)
    ? '额度池 '+d.quota.pool+'：已用 '+(d.quota.used==null?'—':d.quota.used)+' / '+(d.quota.limit==null?'—':d.quota.limit)+' · 每 IP 6 次/分钟'
    : '额度：未返回 · 每 IP 6 次/分钟';
}
function xkCites(d){
  const cs = d.citations || []; if(!cs.length) return '';
  return cs.map((c,i)=>{
    const bits = [];
    if(c.sourceTypeLabel) bits.push(c.sourceTypeLabel);
    if(c.trustLevelLabel) bits.push(c.trustLevelLabel);
    if(c.score!=null && !isNaN(Number(c.score))) bits.push('相关度 ' + (Math.round(Number(c.score)*100)/100));
    return '<div class="cite">['+(i+1)+'] 《'+xkAskEsc(c.title||'（无标题）')+'》'+(bits.length?' · '+xkAskEsc(bits.join(' · ')):'')+
      (c.snippet?'<br><span style="opacity:.85">'+xkAskEsc(c.snippet)+'</span>':'')+'</div>';
  }).join('');
}
function xkRenderAnswer(el, d){
  const st = d.state || '';
  const label = d.stateLabel || (XK_STATE_LABEL[st] ? XK_STATE_LABEL[st][0] : (st || '未识别状态'));
  let html = '<div class="who">AI 安全 · <span class="st">'+xkAskEsc(label)+'</span></div>';
  if(d.injection && d.injection.blocked)
    html += '<p>输入命中提示注入护栏（'+xkAskEsc(d.injection.hitCount||0)+' 条规则）；下面是把它当"不可信数据"处理后的结果。</p>';
  if(d.failureReason) html += '<p><b>服务端说明：</b>'+xkAskEsc(d.failureReason)+'</p>';
  if(d.answer) html += xkMd(d.answer);
  else if(!d.failureReason) html += '<p>这次没有返回答案正文（state='+xkAskEsc(st||'—')+'）。</p>';
  html += xkCites(d);
  if(d.clientIpMasked || (d.quota && d.quota.pool))
    html += '<div class="cite">来源 IP（后端已掩码）：'+xkAskEsc(d.clientIpMasked||'—')+(d.quota&&d.quota.pool?' · 额度池 '+xkAskEsc(d.quota.pool):'')+'</div>';
  el.innerHTML = html;
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
document.getElementById('askInput').addEventListener('keydown', e=>{ if(e.key === 'Enter') askDemo(); });'''
sc = subn(sc, r'/\* =+ AI 问答演示 =+ \*/.*?askDemo\(\); \}\);', lambda m: ASK_REAL, 1, 'shell: AI 问答真实链路')

# ---- ⑯ 内容页语音：把 L1 预渲染语音接上（与主页同一套资产，独立成模块）----
# 【2026-10-15 接手批】五个内容页同样"只会打字幕、不播音频"。这里在**第一段**脚本（外壳逻辑）里
#   接一个语音模块 —— 刻意不放进第二段（scene-js），因为那一段当前会在 resize() 抛 TypeError 中止。
#   进页台词按当前 view 选：v-monitor→nav_monitor … v-ai→nav_ai（★T27：v-range/v-about 两屏已删，
#   对应的 nav_labs / nav_about 两句一起作废）。
#   纪律同主页：手势前只记 pending；取不到只显示字幕；语音与字幕同一句文案；诊断挂 window.__xkVoice。
CONTENT_VOICE = r'''
/* ================= 桐莉栖语音（L1 预渲染语音库）· 内容页 =================
   ★2026-10-15 接手批：与原 demo 的差别 —— 原来只 speak() 打字幕，一个音频都不播。
   资产：static/kurisu/voice/bank.json。手势前不播（只记 pending），取不到只显示字幕。 */
const XKV = { bank:null, unlocked:false, pending:null, lastId:null, audio:null, plays:0, errors:[] };
window.__xkVoice = XKV;
function xkvLine(id){ return (XKV.bank && XKV.bank.lines && XKV.bank.lines[id]) || null; }
function xkvLoad(){
  if(XKV.bank) return Promise.resolve(XKV.bank);
  return fetch('/kurisu/voice/bank.json', {cache:'no-store'}).then(r=>{
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
  return ({ 'v-monitor':'nav_monitor', 'v-notes':'nav_notes', 'v-ai':'nav_ai' })[id] || 'nav_home';
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
'''
# ⚠️ shell_scripts[0] 是**带 <script>/</script> 标签**的整段（见 scripts 的 findall 抽取），
#    所以必须插在闭合标签**之前** —— 直接 sc + X 会落到 <script> 外面变成正文（本轮踩过）。
if not sc.rstrip().endswith('</script>'):
    raise SystemExit('外壳第一段 <script> 的结构变了（结尾不是 </script>），内容页语音插入点失效')
sc = sc.rstrip()[:-len('</script>')] + CONTENT_VOICE + '\n</script>'

# ---- ⑰ 五页 TypeError：demo 的 scene-js 依赖不存在的 #fallback / #bootveil ----
# 【2026-10-15 接手批 · 打开原AI留的补丁】第十二批把这三条"砍范围"了，理由写在 L464-470：
#   一旦 IIFE 不再抛异常，五个内容页都会走到 play('opening') 去载 opening.hi（1004KB）→
#   /ai/ 首屏 1637KB → 2641KB，直接顶破 1650KB 门禁 —— 所以它和首屏预算是**耦合**的。
#   本批把"修异常"和"门控 opening"**一起**打开：异常没了，字节也不涨。
#   （主页不走这一页的脚本，所以对主页零影响；内容页上 v-home 永远不是 .on。）
s1 = shell_scripts[1]
s1 = sub1(s1, S_FALLBACK_OLD, S_FALLBACK_NEW, 'scene-js: #fallback 存在性判断')
s1 = sub1(s1, S_BOOT_OLD, S_BOOT_NEW, 'scene-js: #bootveil 存在性判断')
s1 = sub1(s1, S_VEIL_OLD, S_VEIL_NEW, 'scene-js: veil 存在性判断')
s1 = sub1(
    s1,
    "}else{\n  play('opening');\n}",
    "}else if(document.getElementById('v-home').classList.contains('on')){\n  play('opening');\n}",
    'scene-js: opening 只在主页可见时播')
s1 = sub1(
    s1,
    "  if(!RM && !played){ play('opening'); sessionStorage.setItem('xk-demo-intro','1'); }",
    "  if(!RM && !played && document.getElementById('v-home').classList.contains('on')){ play('opening'); sessionStorage.setItem('xk-demo-intro','1'); }",
    'scene-js: __enterHome 的 opening 门控')
shell_scripts[1] = s1

# ---- ★T20/T21/T22 的 DOM 片段（与 layouts/partials/xk-demo/shell-views.html 逐字同源）----
MOD_STORY_OLD = '            <div class="mod"><div class="mod-hd"><span class="led"></span>一次真实攻击的故事线<span class="tag">/stories</span></div>\n              <div class="mod-bd">\n                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n              </div>\n            </div>'
MOD_STORY_NEW = '            <div class="mod" data-xk-block="stories"><div class="mod-hd"><span class="led"></span>攻击故事线 · 候选来源<span class="tag" data-story-tag>/stories</span></div>\n              <div class="mod-bd">\n                <div data-story-list>\n                  <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                  <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                  <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                  <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                </div>\n                <div data-story-detail hidden>\n                  <div class="row"><span class="k" data-story-head>—</span><span data-story-meta>—</span><span class="chip" data-story-chip>—</span></div>\n                  <div data-story-tl></div>\n                </div>\n                <p class="attk-note" data-story-note>点上面任一条来源 → 载入它的四段时间线（点了才请求一次，不轮询）。</p>\n              </div>\n            </div>'
BAN_ANCHOR = '          <div class="mod"><div class="mod-hd"><span class="led"></span>告警来源分布'
MOD_BANS = '          <div class="mod" data-xk-block="bans"><div class="mod-hd"><span class="led"></span>处置成果 · 封禁榜<span class="tag">/audit · IP 已打码</span></div>\n            <div class="mod-bd">\n              <div class="stats">\n                <div class="stat"><div class="n" data-ban="total">—</div><div class="l">累计封禁 blockTotal</div></div>\n                <div class="stat"><div class="n" data-ban="active">—</div><div class="l">当前生效 blockActive</div></div>\n                <div class="stat"><div class="n" data-ban="guard">—</div><div class="l">护栏拦下动作 blockedByGuard</div></div>\n                <div class="stat"><div class="n" data-ban="actions">—</div><div class="l">已执行动作 executedActions</div></div>\n              </div>\n              <div data-ban-list>\n                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n              </div>\n              <p class="attk-note" data-ban-note>取数中…</p>\n            </div>\n          </div>\n'
KB_ANCHOR = '      <p class="chat-note">回答非流式传输（一次性返回 + 前端渐进显示）· 取不到就显示原因，绝不编答案</p>\n'
MOD_KB = '      <p class="chat-note">回答非流式传输（一次性返回 + 前端渐进显示）· 取不到就显示原因，绝不编答案</p>\n      <div class="card" data-xk-block="kb" style="margin-top:16px">\n        <div class="card-hd"><span class="led"></span>知识库检索 · 公开白名单<span style="margin-left:auto;font-size:11px;color:var(--acc)">GET /api/public/kb?q=</span></div>\n        <ul class="bl" style="padding-top:12px">\n          <li><b>检索范围是白名单</b>：只检索公开白名单目录下的文档（<code class="k">security-docs</code>、<code class="k">data/kb-approved</code>，来源类型 <code class="k">community</code>）——内部文档即使被语义命中也不会出现在这里。<span data-kb-rule></span></li>\n        </ul>\n        <div class="anchor-row" data-kb-topics style="padding:0 15px;margin:0"></div>\n        <div style="display:flex;gap:10px;padding:10px 15px 4px">\n          <input id="kbInput" placeholder="输入关键词…（只按 Enter / 点检索才请求，不边打字边请求）"\n            style="flex:1;background:rgba(255,255,255,.05);border:1px solid var(--line2);border-radius:99px;color:var(--txt);padding:9px 14px;font-size:13px;outline:none">\n          <button id="kbBtn" style="background:var(--acc);border:0;color:#04282b;font-weight:600;padding:0 18px;border-radius:99px;cursor:pointer">检索</button>\n        </div>\n        <div data-kb-out></div>\n        <p class="attk-note" data-kb-note style="padding:0 15px 12px">选一个话题词或自己输入关键词 —— 后端 top-k=3，前端不分页、不轮询。</p>\n      </div>\n'

# =====================================================================
# ★T27（2026-10-15 站主决议）：删 /labs/ 靶场页 + /about/ 关于页 ⇒ 六页 → 四页、导航六项 → 四项
#   · 原 T5.3 给 v-about 填的四张真实卡（站点性质/数据来源/她/纪律）按站主口径**改作知识库条目**，
#     草案见仓库外 E:\DeepSeek1\work\_ui-batch\data\kb-条目草案-T5.3迁移.md（本生成器不再注入 v-about）。
#   · v-range / v-about 两屏整段删除；dock 六项 → 四项（主页 DOCK_HTML 与外壳 chrome 同步）。
#   · 页数/链接/sitemap 的连带改动见 _dev/check-ssr-contract.py、_dev/gate-firstscreen.mjs、hugo.toml。
# =====================================================================
views_out = subn(views_out, r'\n  <!-- 靶场 -->.*?\n  </section>\n', '\n', 1, 'T27: 删 v-range 整屏')
views_out = subn(views_out, r'\n  <!-- 关于 -->.*?\n  </section>\n\s*$', '\n', 1, 'T27: 删 v-about 整屏')
# dock 六项 → 四项：demo 的 6 个 <button data-v> 先按原表（DOCK_HREF 保持 6 项）换成 <a>，
# 再按行删掉 range/about —— 这样 rewrite_dock 的硬断言（n != len(DOCK_HREF)）仍然是 6 == 6 ✓
for _line in ('<a href="/labs/" class="{{ if eq $v "range" }}on{{ end }}">靶场</a>\n',
              '<a href="/about/" class="{{ if eq $v "about" }}on{{ end }}">关于</a>\n'):
    chrome = sub1(chrome, _line, '', 'T27: chrome dock 删项')

# --------------------------------------------------------------------- ★T20/T21/T22（窗口 F 的字段映射）
#   T20 封禁榜 ← /audit（summary + blocks[]）；T21 故事线 ← /stories + 点击懒加载 /story?src=；
#   T22 知识库 ← /kb?q=（都在 /ai/ 页，只在用户操作时请求）。绑定实现在手写的 api-bind.html 里。
views_out = sub1(views_out, MOD_STORY_OLD, MOD_STORY_NEW, 'T21: 故事线卡 → 候选池 + 时间线容器')
views_out = sub1(views_out, BAN_ANCHOR, MOD_BANS + BAN_ANCHOR, 'T20: 封禁榜 mod')
views_out = sub1(views_out, KB_ANCHOR, MOD_KB, 'T22: /ai/ 知识库检索卡')

# =====================================================================
# T12（2026-10-15）：删右下角「背景/配色」面板 + 配套 CSS/JS/背景图
#   —— 站长原话"加载太卡"；内容页首屏 267KB → 约 190KB（不再载 room_empty 84KB）
#   保留：--shade 默认 .08（CSS 里有）、body 静态 data-skin="warm"、data-phone="v1"（模板补）
#   只动五页外壳（chrome / shell_style / sc）；主页没有这套东西。
# =====================================================================
chrome = subn(chrome,
              r'<!-- 背景选择器 -->.*?</div>\s*\Z',
              '', 1, 'T12: 删背景选择器标记')
chrome = sub1(chrome,
              '<div class="bg" id="bgEl" aria-hidden="true"></div>\n<div class="bgshade" aria-hidden="true"></div>\n',
              '', 'T12: 删背景 div')
shell_style = subn(shell_style,
                   r'\n  /\* 背景选择器 \*/\n  \.bgbtn\{.*?\.skin-toggle button\.on\{color:var\(--acc\);border-color:var\(--acc\)\}\n',
                   '\n', 1, 'T12: 删选择器 CSS')
shell_style = subn(shell_style,
                   r'  \.bg\{position:fixed;inset:0;z-index:-2;[^\n]*\n  \.bgshade\{position:fixed;inset:0;z-index:-1;\n    background:linear-gradient\(180deg,rgba\(8,10,14,var\(--shade\)\),rgba\(8,10,14,var\(--shade\)\)\)\}\n',
                   '', 1, 'T12: 删 .bg/.bgshade CSS')
shell_style = sub1(shell_style, '    .bggrid{grid-template-columns:repeat(3,1fr)}\n', '', 'T12: 删媒体查询 bggrid')
shell_style = sub1(shell_style, '  body.is-home .bg,body.is-home .bgshade{display:none}\n', '', 'T12: 删 is-home 背景规则')
shell_style = sub1(shell_style,
                   '  body.is-home .holo,body.is-home .holo-bubble,body.is-home .bgbtn,body.is-home .bgpicker{display:none}',
                   '  body.is-home .holo,body.is-home .holo-bubble{display:none}',
                   'T12: 收敛 is-home 规则')
sc = subn(sc,
          r'/\* ============ 背景选择器 ============ \*/.*?x\.dataset\.phone===savedPhone\)\);\n',
          '', 1, 'T12: 删背景 JS')

# =====================================================================
# T5.6（2026-10-15）：boot→hi 两段式 —— boot 小图集（前 24 帧，网格/瓦片与 hi
#   同规格）先播，hi 后台下载、到位后按同一帧号无缝接力。主页首屏 1569KB → 约 823KB。
#   落点：主页脚本（opening/idle）+ 壳 scene-js（speaking/thinking 在 /ai/ 播）。
# =====================================================================
CLIPS_BOOT_OLD = (
    "  opening:  {src:'/kurisu/full/opening.hi.webp',  frames:84, interval:33.33, cols:8, cw:380, ch:290, fit:'screen',  next:'idle'},\n"
    "  idle:     {src:'/kurisu/full/idle.hi.webp',     frames:60, interval:42,    cols:8, cw:321, ch:432, fit:'anchor'},\n"
    "  speaking: {src:'/kurisu/full/speaking.hi.webp', frames:90, interval:34,    cols:8, cw:321, ch:432, fit:'anchor'},\n"
    "  thinking: {src:'/kurisu/full/thinking.hi.webp', frames:90, interval:34,    cols:8, cw:321, ch:432, fit:'anchor'}")
CLIPS_BOOT_NEW = (
    "  opening:  {src:'/kurisu/full/opening.hi.webp',  frames:84, interval:33.33, cols:8, cw:380, ch:290, fit:'screen',  next:'idle', bootSrc:'/kurisu/full/opening.boot.webp',  bootFrames:24},\n"
    "  idle:     {src:'/kurisu/full/idle.hi.webp',     frames:60, interval:42,    cols:8, cw:321, ch:432, fit:'anchor', bootSrc:'/kurisu/full/idle.boot.webp',     bootFrames:24},\n"
    "  speaking: {src:'/kurisu/full/speaking.hi.webp', frames:90, interval:34,    cols:8, cw:321, ch:432, fit:'anchor', bootSrc:'/kurisu/full/speaking.boot.webp', bootFrames:24},\n"
    "  thinking: {src:'/kurisu/full/thinking.hi.webp', frames:90, interval:34,    cols:8, cw:321, ch:432, fit:'anchor', bootSrc:'/kurisu/full/thinking.boot.webp', bootFrames:24}")

XK_CLIPIM_JS = (
    "/* ★T5.6 boot→hi：hi 已就绪就用 hi；否则 boot 小图集（前 24 帧，网格/瓦片同规格）先播，\n"
    "   hi 由 play() 延迟触发（越过首屏窗口）；到位后按同一帧号无缝接力，画质不变。\n"
    "   警告：hi 只能 peek 缓存、不能 img() 创建 —— img() 创建即发请求，会把 hi 拉回首屏；\n"
    "   且必须先 peek hi 再兜底 boot —— 顺序反了会永远卡在 boot 档，开场永不落幕。 */\n"
    "function xkClipIm(name){\n"
    "  const c = CLIPS[name];\n"
    "  const px = cache[c.src];\n"
    "  if(px && px.complete && px.naturalWidth) return {im:px, c:c};\n"
    "  if(c.bootSrc){\n"
    "    const bt = img(c.bootSrc);\n"
    "    if(bt.complete && bt.naturalWidth) return {im:bt, c:Object.assign({}, c, {frames:c.bootFrames})};\n"
    "    return {im:bt, c:Object.assign({}, c, {frames:c.bootFrames})};\n"
    "  }\n"
    "  return {im:img(c.src), c:c};\n"
    "}\n")

def xk_boot_patches(script, is_home):
    s = script
    s = sub1(s, CLIPS_BOOT_OLD, CLIPS_BOOT_NEW, 'T5.6: CLIPS 加 boot 档')
    s = sub1(s,
             "function play(name){\n",
             XK_CLIPIM_JS + "function play(name){\n",
             'T5.6: xkClipIm helper')
    s = sub1(s,
             "  if(cur){\n    const c = CLIPS[cur];\n    const im = img(c.src);\n    if((im.complete && im.naturalWidth) && !RM){",
             "  if(cur){\n    const _xk = xkClipIm(cur);\n    const c = _xk.c, im = _xk.im;\n    if((im.complete && im.naturalWidth) && !RM){",
             'T5.6: loop 取图走 boot→hi')
    s = sub1(s,
             "  if(!cur) return;\n  const c = CLIPS[cur];\n  const im = img(c.src);\n  if(!im.complete || !im.naturalWidth) return;",
             "  if(!cur) return;\n  const _xk = xkClipIm(cur);\n  const c = _xk.c, im = _xk.im;\n  if(!im.complete || !im.naturalWidth) return;",
             'T5.6: drawFrame 取图走 boot→hi')
    s = sub1(s,
             "  cur = name; fi = 0; acc = 0;\n  img(c.src); drawFrame();",
             "  cur = name; fi = 0; acc = 0;\n"
             "  /* ★T5.6：boot 先上（首屏只吃小图集）；hi 推迟到 boot 就绪 +1.7s 再取 ——\n"
             "     越过首屏门禁的 1.5s 窗口，入户字节才真的降下来。boot 加载失败则立刻回退 hi。 */\n"
             "  if(c.bootSrc){\n"
             "    const bt = img(c.bootSrc);\n"
             "    const late = ()=>{ setTimeout(()=>{ img(c.src); }, 1700); };\n"
             "    if(bt.complete && bt.naturalWidth){ late(); }\n"
             "    else { bt.addEventListener('load', late, {once:true}); bt.addEventListener('error', ()=>{ img(c.src); }, {once:true}); }\n"
             "  } else { img(c.src); }\n"
             "  drawFrame();",
             'T5.6: play() boot 优先预载 + hi 延迟')
    return s

s1 = xk_boot_patches(s1, False)
shell_scripts[1] = s1
home_script = xk_boot_patches(home_script, True)
# 注：下面三条锚定 L1/CRT 生成代码的补丁必须放在 L1 段之后（见 L1 段末尾），
#   因为它们在 L1 补丁跑完之前目标文本还不存在。
# 图谱数据不再是写死的样例
sc = sub1(
    sc,
    "const SENSORS = [['cowrie-01','SSH 蜜罐'],['dionaea-03','恶意软件捕获'],['conpot','工控蜜罐'],['tanner','Web 蜜罐'],['honeytrap','低交互蜜罐'],['sentinel','Redis 诱饵']];\nconst ATTACKERS = ['45.155.x.x','185.220.x.x','91.240.x.x','103.99.x.x','198.51.x.x'];",
    "/* ★第十二批：攻击者与传感器不再是写死的样例 ——\n"
    "   由 api-bind 从 /api/public/alerts（真实来源 IP）与 /api/public/honeypot（真实 SSH 客户端指纹）\n"
    "   写进 window.XK_ATTACKERS / window.XK_SENSORS；取不到就只画一行「读不到」，不画假的攻击路径。 */\n"
    "const SENSORS = [];\nconst ATTACKERS = [];",
    'shell: 图谱写死样例')
sc = sub1(sc, '  const hits = SENSORS.map(()=>0);', '  let hits = null;', 'shell: hits 占位')
sc = sub1(
    sc,
    "  const A = ATTACKERS.map((n,i)=>({n, fx:.09, fy:(i+1)/(ATTACKERS.length+1)}));\n"
    "  const S = SENSORS.map((s,i)=>({n:s[0], d:s[1], fx:.82, fy:(i+1)/(SENSORS.length+1)}));",
    "  const A_NAMES = window.XK_ATTACKERS || [], S_NAMES = window.XK_SENSORS || [];\n"
    "  if(!A_NAMES.length || !S_NAMES.length){   /* 读不到：把原因画在同一块画布上，不画假的路径 */\n"
    "    graphStarted = false;   /* 不锁死：数据到了以后再点这一栏还能画 */\n"
    "    const note = ()=>{ const w2 = c.clientWidth; if(!w2) return; x.clearRect(0,0,w2,H);\n"
    "      x.fillStyle = 'rgba(210,203,189,.75)'; x.font = '12px ui-monospace,Consolas,monospace'; x.textAlign = 'center';\n"
    "      x.fillText(window.XK_GRAPH_NOTE || '读不到：攻击路径的数据源没取到 —— 不画假的路径', w2/2, H/2); };\n"
    "    note(); addEventListener('resize', note); return;\n"
    "  }\n"
    "  hits = S_NAMES.map(()=>0);\n"
    "  const A = A_NAMES.map((n,i)=>({n, fx:.09, fy:(i+1)/(A_NAMES.length+1)}));\n"
    "  const S = S_NAMES.map((s,i)=>({n:s[0], d:s[1], fx:.82, fy:(i+1)/(S_NAMES.length+1)}));",
    'shell: 图谱数据源')
# 四个数字原来挂在 stats 标签上，而它们渲染在 graph 那一屏 → 永远停在 0
sc = sub1(
    sc,
    "  if(opsTab==='graph') startGraph();\n  if(opsTab==='stats') runCounters();",
    "  if(opsTab==='graph'){ startGraph(); runCounters(); }   /* ★第十二批：这四个数字渲染在 graph 这一屏，\n"
    "      原来只在点 stats 时滚动 → 它们永远停在 0（demo 的错位）。 */\n"
    "  if(opsTab==='stats') drawSpark();",
    'shell: 数字滚动触发点')
# 兜底：死代码里的假数字（dock 是 <a>，switchView 已经到不了；留着也是假的，一起清掉）
sc = sub1(
    sc,
    "  monitor:'过去 24 小时拦截了 <span class=\"qk\">96 次</span> 暴力破解，蜜罐记录了 <span class=\"qk\">37 条</span> 交互。都在「监测中心」的大屏里。',",
    "  monitor:'这一屏是我们监测到的情况，数字都是真的；取不到我就写读不到。',",
    'shell: SAYS.monitor 假数字')

# ---- ⑱★批次 A（2026-10-16 站主追加①）：入口台词固定 + 口语化 ----
#   站主原话："进入主页是对话固定好一句打招呼的，你那个对话不知道在说啥"。
#   ⇒ ① 主页进入固定一句问候（首访 greet_first / 回访 greet_back，**不随机、不参与防复读轮换**）；
#      ② 每个栏目进入固定一句介绍（nav_home / nav_monitor / nav_ai / nav_notes，同一栏目 10 分钟内不重复念）；
#      ③ 文案一律改成"像人说话"，不写术语味（"公开只读端点的实时汇总" 这类一律不留在可见文案里）。
#   落点：demo 的 SAYS（内容页切屏时的字幕）、HOME_VOICE 的问候分流、台词表（见 IDCARD_PARTIAL 的 LINE_ZH）
#         与 kurisu-player.js 的选句器（nav_* 用 preferId 硬命定 ⇒ 固定不随机）。
#   台词表（入口 → 中日文对照）落纸：docs/台词表-入口与固定台词-20261016.md
SAYS_REWORD = [
    ("  home:'',\n",
     "  home:'回到主页了。我一直待在这台显示器里。',\n", 'SAYS.home'),
    ("  ai:'有什么安全问题直接问我。答不了就说答不了。',\n",
     "  ai:'有问题就问我，我照真检索到的东西答；答不了我就说答不了。',\n", 'SAYS.ai'),
    ("  notes:'这几篇都是真实实验记录，「Cowrie 观察」那篇最热闹。',\n",
     "  notes:'笔记都在这儿，新的排在最前面。',\n", 'SAYS.notes'),
]
for _old, _new, _what in SAYS_REWORD:
    sc = sub1(sc, _old, _new, 'batchA 台词口语化: ' + _what)

# ---- ⑯ 【2026-10-15 接手批】表情只挂了 5 套，素材其实有 8 套 ----
#   站主口径："这个人物的所有动画、表情等等都弄好"。
#   static/kurisu/avatar/ 里 8 套情绪（normal / happy / sided_thinking / sided_surprised /
#   sad / blush / angry / disappointed）的 idle + speaking 两态**都在**，manifest.emotions
#   也有逐套索引；但 demo 的 EMOS 表与 #emos 按钮只列了 5 个 → 剩下 3 套（惊讶 / 生气 / 失望）
#   永远点不到；而且 sad / blush 当初因为 demo-assets 里只有 static 单帧，被写死成**不会动**的静帧。
#   这里把表与按钮都补齐到 8 套，并把 sad / blush 换成真正会动的 idle / speaking 图。
EMOS_OLD = (
    "const EMOS = {\n"
    "  normal:         {idle:'/kurisu/avatar/normal.idle.webp',         speaking:'/kurisu/avatar/normal.speaking.webp'},\n"
    "  happy:          {idle:'/kurisu/avatar/happy.idle.webp',          speaking:'/kurisu/avatar/happy.speaking.webp'},\n"
    "  sided_thinking: {idle:'/kurisu/avatar/sided_thinking.idle.webp', speaking:'/kurisu/avatar/sided_thinking.speaking.webp'},\n"
    "  sad:            {idle:'/kurisu/avatar/sad.static.webp',          speaking:'/kurisu/avatar/sad.static.webp'},\n"
    "  blush:          {idle:'/kurisu/avatar/blush.static.webp',        speaking:'/kurisu/avatar/blush.static.webp'}\n"
    "};"
)
EMOS_NEW = (
    "const EMOS = {   /* ★2026-10-15 接手批：5 套 → 8 套（素材本来就有 8 套，见 static/kurisu/avatar/）；\n"
    "                    sad / blush 由 static 单帧换成会动的 idle / speaking 图 */\n"
    "  normal:         {idle:'/kurisu/avatar/normal.idle.webp',         speaking:'/kurisu/avatar/normal.speaking.webp'},\n"
    "  happy:          {idle:'/kurisu/avatar/happy.idle.webp',          speaking:'/kurisu/avatar/happy.speaking.webp'},\n"
    "  sided_thinking: {idle:'/kurisu/avatar/sided_thinking.idle.webp', speaking:'/kurisu/avatar/sided_thinking.speaking.webp'},\n"
    "  sided_surprised:{idle:'/kurisu/avatar/sided_surprised.idle.webp',speaking:'/kurisu/avatar/sided_surprised.speaking.webp'},\n"
    "  sad:            {idle:'/kurisu/avatar/sad.idle.webp',            speaking:'/kurisu/avatar/sad.speaking.webp'},\n"
    "  blush:          {idle:'/kurisu/avatar/blush.idle.webp',          speaking:'/kurisu/avatar/blush.speaking.webp'},\n"
    "  angry:          {idle:'/kurisu/avatar/angry.idle.webp',          speaking:'/kurisu/avatar/angry.speaking.webp'},\n"
    "  disappointed:   {idle:'/kurisu/avatar/disappointed.idle.webp',   speaking:'/kurisu/avatar/disappointed.speaking.webp'}\n"
    "};"
)
sc = sub1(sc, EMOS_OLD, EMOS_NEW, 'shell: EMOS 5 套 → 8 套')
chrome = sub1(
    chrome,
    '      <b data-emo="blush"          style="background:#f0997b" title="害羞"></b>\n',
    ('      <b data-emo="blush"          style="background:#f0997b" title="害羞"></b>\n'
     '      <b data-emo="sided_surprised" style="background:#e88fd0" title="惊讶"></b>\n'
     '      <b data-emo="angry"          style="background:#e8654e" title="生气"></b>\n'
     '      <b data-emo="disappointed"   style="background:#8a94a6" title="失望"></b>\n'),
    'chrome: 表情按钮 5 个 → 8 个')

shell_scripts[0] = sc

# ---- ⑰ 【2026-10-15 接手批】主页：把 38 段全身剪辑里的"表情段"接上（懒加载 · 零首屏影响）----
#   站主口径："这个人物的所有动画、表情等等都弄好"。
#   主页原来只有 4 段 hi 档剪辑（opening / idle / speaking / thinking），表情一个都没有；
#   而 static/kurisu/medium/ 里 38 段全身剪辑（smile_speaking / shy_speaking1 / angry_speaking /
#   sad_speaking / surprise_speaking / thinking_speaking1 / sad_trans …）与 manifest.clipsMedium
#   的**逐页**索引早已就绪。这里把主页同一块 #charCanvas 扩成"表情模式"：
#     · manifest 与图集都在首屏门禁 1.5s 窗口**之后**才取 → 首屏字节零变化（门禁①不受影响）；
#     · 多页图集（idle2 / speaking_long / thinking_speaking2 … 有 .p01/.p02）按页内偏移取帧；
#     · reverse（key_point_to_thinking 复用 thinking_to_key_point 图集倒放）照 manifest 处理；
#     · 落位沿用主页既有公式（CHAR_BOX），宽按素材自身比例算 —— 不与 hi 档打架；
#     · 取不到就退回 hi 档（play('idle')），**不假装有动画**；诊断挂 window.__xkEmo。
HOME_ANIM = r'''

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
  nav_home:'normal', nav_monitor:'sided_thinking', nav_notes:'normal', nav_ai:'sided_thinking',
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
function xkmMark(name){
  var bar = document.getElementById('xkEmoBar');
  if(!bar) return;
  var bs = bar.querySelectorAll('b'), i;
  for(i = 0; i < bs.length; i++){
    bs[i].className = (bs[i].getAttribute('data-emo') === name) ? 'on' : '';
  }
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
  XKM.emo = name; window.__xkEmo.emotion = name; xkmMark(name);
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
function xkmBuild(){
  var crtEl = document.getElementById('crt');
  if(!crtEl || document.getElementById('xkEmoBar')) return;
  var st = document.createElement('style');
  st.textContent =
    '.xk-emo-bar{position:absolute;top:5%;left:5%;display:flex;gap:6px;z-index:6;' +
    'opacity:0;transition:opacity .5s}' +
    '.xk-emo-bar.on{opacity:1}' +
    '.xk-emo-bar b{width:12px;height:12px;border-radius:50%;border:1px solid rgba(255,255,255,.45);' +
    'cursor:pointer;opacity:.45;transition:opacity .2s,box-shadow .2s}' +
    '.xk-emo-bar b:hover{opacity:.85}' +
    '.xk-emo-bar b.on{opacity:1;box-shadow:0 0 0 2px rgba(57,208,216,.55)}';
  document.head.appendChild(st);
  var bar = document.createElement('div');
  bar.className = 'xk-emo-bar'; bar.id = 'xkEmoBar';
  bar.setAttribute('role', 'group');
  bar.setAttribute('aria-label', '桐莉栖表情');
  bar.innerHTML = XK_EMO_LIST.map(function(e){
    return '<b data-emo="' + e[0] + '" style="background:' + e[2] + '" title="' + e[1] + '"></b>';
  }).join('');
  crtEl.appendChild(bar);
  bar.addEventListener('click', function(ev){
    var b = (ev.target && ev.target.closest) ? ev.target.closest('b[data-emo]') : null;
    if(!b) return;
    var nm = b.getAttribute('data-emo');
    XKM.manual = (nm !== 'normal');
    xkmSetEmotion(nm);
  });
  xkmMark(XKM.emo);
}
function xkmReveal(){
  var bar = document.getElementById('xkEmoBar');
  if(bar) bar.classList.add('on');
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
xkmBuild();
/* manifest 在首屏门禁 1.5s 窗口之后才取 —— 表情资产绝不进首屏字节 */
if(!RM){ setTimeout(xkmLoad, 2000); }
'''
home_script = sub1(home_script,
                   "function play(name){\n  const c = CLIPS[name];",
                   "function play(name){\n  XK_ACT = null;   /* ★2026-10-15：任何 hi 档播放都退出表情模式 */\n  const c = CLIPS[name];",
                   '主页 play(): 退出表情模式')
home_script = sub1(home_script,
                   "function drawFrame(){\n  if(!cur) return;",
                   "function drawFrame(){\n  if(XK_ACT){ xkmPaint(); return; }   /* ★表情模式：重画当前表情帧 */\n  if(!cur) return;",
                   '主页 drawFrame(): 表情模式分支')
home_script = sub1(home_script,
                   "function loop(t){\n  if(!started) return;\n  if(cur){",
                   "function loop(t){\n  if(!started) return;\n  if(XK_ACT){ xkmTick(t); lastT = t; requestAnimationFrame(loop); return; }   /* ★表情模式接管画布 */\n  if(cur){",
                   '主页 loop(): 表情模式分支')
home_script = sub1(home_script,
                   "  document.getElementById('crtStatus').hidden = false;\n"
                   "  typeSub('你好，我是桐莉栖。监测数据都是真的——看不清就走近一点。');",
                   "  document.getElementById('crtStatus').hidden = false;\n"
                   "  /* ★2026-10-15：语音正在说的时候字幕归语音那条，别被这句默认文案顶掉 */\n"
                   "  const _v = window.__xkVoice;\n"
                   "  if(!(_v && _v.audio && !_v.audio.paused)) typeSub('你好，我是桐莉栖。监测数据都是真的——看不清就走近一点。');\n"
                   "  if(typeof xkmReveal === 'function') xkmReveal();   /* ★2026-10-15：表情条随 HUD 一起出现 */",
                   '主页 showHud(): 显示表情条 + 不与语音抢字幕')
home_script = sub1(home_script,
                   "      if(typeof play === 'function' && cur !== 'opening'){\n        const sim = img(CLIPS.speaking.src);",
                   "      if(typeof xkVoiceAnim === 'function'){ xkVoiceAnim(id); return; }\n"
                   "      if(typeof play === 'function' && cur !== 'opening'){\n        const sim = img(CLIPS.speaking.src);",
                   '主页语音 playing: 交给表情层')
home_script = sub1(home_script,
                   "    a.addEventListener('ended', ()=>{\n      if(typeof play === 'function') play('idle');",
                   "    a.addEventListener('ended', ()=>{\n"
                   "      if(typeof xkVoiceEnd === 'function'){ xkVoiceEnd(); }\n"
                   "      else if(typeof play === 'function'){ play('idle'); }",
                   '主页语音 ended: 交给表情层')
home_script = sub1(home_script,
                   "  /* 桌面实拍照常驻、CRT 完整可见的硬不变量：CRT 高度 <260px 触发降级 */\n"
                   "  document.getElementById('fallback').style.display = r.height < 260 ? 'grid' : 'none';",
                   "  /* ★2026-10-15 T1：桌面窄窗才降级；触屏（手机/平板）一律播动画，只是更小。视觉不变 */\n"
                   "  document.getElementById('fallback').style.display = (r.height < 260 && !matchMedia('(pointer: coarse)').matches) ? 'grid' : 'none';",
                   '主页 fallback: 触屏不降级')
home_script = home_script + HOME_ANIM

# ---- L1 镜头推拉：opening→idle 不再硬切（2026-10-15）----
# 只改主页：opening 全屏特写只有主页会播（五页 v-home 从不 .on，scene-js 里 opening 永不触发），五页不接。
# 观感：开场特写缓慢后退+下摇到 CRT 区域，末 28% 与 idle 第 0 帧交叉融化（约 0.9s）。
# 零新素材；TRANS=0 且四处补丁全删即回到原版硬切（回滚路径 = 删本段）。
home_script = sub1(home_script,
                   "let cur = null, acc = 0, fi = 0, lastT = 0, started = false;",
                   "let cur = null, acc = 0, fi = 0, lastT = 0, started = false;\n"
                   "let TRANS = 0;   /* ★L1：opening→idle 镜头推拿起始时间戳（0=不在过渡） */\n"
                   "let PWR = 0;   /* ★CRT 通电：opening 首帧就绪时刻（0=不通电/已结束） */",
                   'L1: TRANS 状态位')

home_script = sub1(home_script,
                   "  if(XK_ACT){ xkmPaint(); return; }   /* ★表情模式：重画当前表情帧 */\n"
                   "  if(!cur) return;",
                   "  if(XK_ACT){ xkmPaint(); return; }   /* ★表情模式：重画当前表情帧 */\n"
                   "  if(TRANS){ xkDrawTrans(Math.min(1, (performance.now() - TRANS) / 900)); return; }   /* ★L1：推拉中以过渡渲染为准 */\n"
                   "  if(!cur) return;",
                   'L1: drawFrame TRANS 分支')

home_script = sub1(home_script,
                   "  if(c.fit === 'screen'){\n"
                   "    /* fit=crt_screen：整帧铺满屏幕（开场特写） */\n"
                   "    ctx.drawImage(im, sx, sy, c.cw, c.ch, 0, 0, canvas.width, canvas.height);",
                   "  if(c.fit === 'screen'){\n"
                   "    /* ★CRT 通电：opening 开头先亮线展开再出画面（约 0.55s） */\n"
                   "    if(PWR && cur === 'opening'){\n"
                   "      const pk = Math.min(1, (performance.now() - PWR) / 550);\n"
                   "      xkPowerOn(pk);\n"
                   "      if(pk >= 1) PWR = 0;\n"
                   "      return;\n"
                   "    }\n"
                   "    /* fit=crt_screen：整帧铺满屏幕（开场特写） */\n"
                   "    ctx.drawImage(im, sx, sy, c.cw, c.ch, 0, 0, canvas.width, canvas.height);",
                   'CRT: drawFrame 通电分支')

home_script = sub1(home_script,
                   "function play(name){\n"
                   "  XK_ACT = null;   /* ★2026-10-15：任何 hi 档播放都退出表情模式 */",
                   "/* ★CRT 通电（约 0.55s）：老显示器开机四拍——亮线 → 竖向展开（画面压进亮线里）→\n"
                   "   抖动闪烁 → 稳定（含一帧过冲白光）。替代黑场直出，正好露出她的脸。\n"
                   "   RM 用户不走 opening 所以永远看不到；删本函数 + PWR 引用即回退。 */\n"
                   "function xkPowerOn(k){\n"
                   "  const cOpen = CLIPS.opening;\n"
                   "  const im = img(cOpen.src);\n"
                   "  const W = canvas.width, H = canvas.height;\n"
                   "  ctx.clearRect(0, 0, W, H);\n"
                   "  if(!im.complete || !im.naturalWidth) return;\n"
                   "  const sx = (fi % cOpen.cols) * cOpen.cw, sy = Math.floor(fi / cOpen.cols) * cOpen.ch;\n"
                   "  const grow = k < 0.7 ? 1 - Math.pow(1 - k / 0.7, 3) : 1;   /* 展开段 easeOutCubic */\n"
                   "  const bandH = Math.max(2, H * grow);\n"
                   "  const bandY = (H - bandH) / 2;\n"
                   "  if(k > 0.12 && k < 0.8 && Math.random() < 0.22) return;   /* 起振不稳：随机黑帧 */\n"
                   "  ctx.save();\n"
                   "  ctx.beginPath(); ctx.rect(0, bandY, W, bandH); ctx.clip();\n"
                   "  if(k < 0.85) ctx.translate((Math.random() * 5 - 2.5) * (1 - k / 0.85), 0);   /* 水平抖动，越稳越少 */\n"
                   "  ctx.drawImage(im, sx, sy, cOpen.cw, cOpen.ch, 0, 0, W, H);\n"
                   "  if(k > 0.7 && k < 0.86){   /* 稳定瞬间的过冲白光 */\n"
                   "    ctx.fillStyle = 'rgba(235,250,255,' + (0.32 * (0.86 - k) / 0.16).toFixed(3) + ')';\n"
                   "    ctx.fillRect(0, bandY, W, bandH);\n"
                   "  }\n"
                   "  ctx.restore();\n"
                   "  if(bandH < H){   /* 亮线：展开中的两条扫描边 */\n"
                   "    const a = (0.35 + 0.4 * Math.random()).toFixed(3);\n"
                   "    ctx.fillStyle = 'rgba(170,240,255,' + a + ')';\n"
                   "    ctx.fillRect(0, bandY - 1, W, 2);\n"
                   "    ctx.fillRect(0, bandY + bandH - 1, W, 2);\n"
                   "  }\n"
                   "}\n"
                   "function play(name){\n"
                   "  XK_ACT = null;   /* ★2026-10-15：任何 hi 档播放都退出表情模式 */",
                   'L1: xkDrawTrans 函数')

home_script = sub1(home_script,
                   "function play(name){\n"
                   "  XK_ACT = null;   /* ★2026-10-15：任何 hi 档播放都退出表情模式 */",
                   "/* ★L1 镜头推拉（约 0.9s）：opening 末帧从全屏特写后退+下摇到 CRT 区域，\n"
                   "   末 28% 与 idle 第 0 帧交叉融化 —— 替代原版播完硬切（镜头跳变）。\n"
                   "   零新素材；TRANS=0 且本函数不被引用即回到硬切行为。 */\n"
                   "function xkDrawTrans(k){\n"
                   "  const cOpen = CLIPS.opening, cIdle = CLIPS.idle;\n"
                   "  const imO = img(cOpen.src), imI = img(cIdle.src);\n"
                   "  const W = canvas.width, H = canvas.height;\n"
                   "  ctx.clearRect(0, 0, W, H);\n"
                   "  const lastF = cOpen.frames - 1;\n"
                   "  const sx = (lastF % cOpen.cols) * cOpen.cw, sy = Math.floor(lastF / cOpen.cols) * cOpen.ch;\n"
                   "  const e = Math.min(1, k / 0.7), ease = 1 - Math.pow(1 - e, 3);   /* 推拉段 0→70%，easeOutCubic */\n"
                   "  const ow = W * (1 - 0.58 * ease), oh = H * (1 - 0.58 * ease);\n"
                   "  const ox = (W - ow) / 2, oy = H * 0.04 + (H * 0.5 - H * 0.04) * ease;   /* 下摇到 CRT 中部 */\n"
                   "  ctx.drawImage(imO, sx, sy, cOpen.cw, cOpen.ch, ox, oy, ow, oh);\n"
                   "  const f = k < 0.72 ? 0 : (k - 0.72) / 0.28;   /* 交叉融化段 */\n"
                   "  if(f > 0 && imI.complete && imI.naturalWidth){\n"
                   "    ctx.globalAlpha = Math.min(1, f);\n"
                   "    const s = Math.min(W * CHAR_BOX.maxW / CHAR_BOX.w, H * CHAR_BOX.maxH / CHAR_BOX.h);\n"
                   "    const dw = CHAR_BOX.w * s, dh = CHAR_BOX.h * s;\n"
                   "    const x = W * CHAR_BOX.xRatio, y = H - Math.max(3, H * CHAR_BOX.footRatio);\n"
                   "    ctx.drawImage(imI, 0, 0, cIdle.cw, cIdle.ch, x - dw / 2, y - dh, dw, dh);\n"
                   "    ctx.globalAlpha = 1;\n"
                   "  }\n"
                   "}\n"
                   "function play(name){\n"
                   "  XK_ACT = null;   /* ★2026-10-15：任何 hi 档播放都退出表情模式 */",
                   'L1: xkDrawTrans 函数（补回）')

home_script = sub1(home_script,
                   "        acc = 0; fi++;\n"
                   "        if(fi >= c.frames){\n"
                   "          if(cur === 'opening'){ play('idle'); showHud(); }   /* 硬切（原版机制） */\n"
                   "          else fi = fi % c.frames;\n"
                   "        }\n"
                   "        drawFrame();",
                   "        acc = 0;\n"
                   "        if(TRANS){   /* ★L1：推拉中——按墙上时间推进，不占帧步进 */\n"
                   "          const k = Math.min(1, (t - TRANS) / 900);\n"
                   "          if(k >= 1){ TRANS = 0; play('idle'); showHud(); }\n"
                   "          else { xkDrawTrans(k); lastT = t; requestAnimationFrame(loop); return; }\n"
                   "        }\n"
                   "        if(cur === 'opening' && !PWR && fi === 0) PWR = t;   /* ★CRT 通电：opening 首帧就绪那一刻起振（图片晚到也能吃上） */\n"
                   "        fi++;\n"
                   "        if(fi >= c.frames){\n"
                   "          if(cur === 'opening' && c.frames !== CLIPS.opening.frames){   /* ★T5.6：还在 boot 档——循环等 hi 到位接力，不当开场播完 */\n"
                   "            fi = fi % c.frames;\n"
                   "          }\n"
                   "          else if(cur === 'opening'){   /* ★L1：播完不硬切——等 idle 图就绪后进场推拉 */\n"
                   "            fi = c.frames - 1;\n"
                   "            const idleIm = img(CLIPS.idle.src);\n"
                   "            if(idleIm.complete && idleIm.naturalWidth){ TRANS = t; }\n"
                   "            else {\n"
                   "              idleIm.addEventListener('load', ()=>{ if(cur === 'opening' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = performance.now(); } }, {once:true});\n"
                   "              idleIm.addEventListener('error', ()=>{ if(cur === 'opening' && !TRANS) TRANS = performance.now(); }, {once:true});\n"
                   "            }\n"
                   "          }\n"
                   "          else fi = fi % c.frames;\n"
                   "        }\n"
                   "        drawFrame();",
                   'L1: loop 拦截硬切')

# ---- T5.6 收尾：通电/推拉两个函数也走 boot→hi（opening 开头 boot 已在播）----
home_script = sub1(home_script,
                   "  const cOpen = CLIPS.opening;\n  const im = img(cOpen.src);\n  const W = canvas.width, H = canvas.height;",
                   "  const cOpen = CLIPS.opening;\n  const im = xkClipIm('opening').im;\n  const W = canvas.width, H = canvas.height;",
                   'T5.6: 通电取图走 boot→hi')
home_script = sub1(home_script,
                   "  const imO = img(cOpen.src), imI = img(cIdle.src);",
                   "  const imO = xkClipIm('opening').im, imI = xkClipIm('idle').im;",
                   'T5.6: 推拉取图走 boot→hi')

# =====================================================================================
# T7 视频接线（2026-10-15 窗口 C）：canvas 从"画 PNG 图集"扩成"可画透明 <video>"
# -------------------------------------------------------------------------------------
# 口径（站主 2026-10-15 已批）：
#   · 六页不挂 kurisu-player、且由本生成器生成 ⇒ 模块做成**生成器补丁里的内联模块**
#     （一份补丁同管主页 + 五页 scene-js；回滚 = 一行 data-xk-kurisu-mode="pixel"）。
#   · 视觉不许变：pixel 档必须**逐像素等于接线前**；video 档只改角色区（非角色区像素差 = 0）。
#   · 首屏零新增字节：video-manifest.json 与 40 个 webm/poster 全部**懒加载**
#     （manifest 在首个剪辑真要上屏或首次手势后才取；预载集 = manifest.preload）。
#   · 降级链：video → 图集(boot/hi) → poster 静帧；单剪辑失败**永久降级**、不每帧重试；
#     全局判定"这个浏览器解不出 VP9-alpha"则整站回 pixel。
#   · 总开关：<html data-xk-kurisu-mode="video|pixel|off">；?xk-kurisu-mode= 与
#     localStorage['xk-kurisu-mode'] 可覆盖（现场排障用，见接线方案 §9 kill switch）。
# 素材事实（引用，不重测）：40 组 webm+poster = 9,543,169 B，268×360、pad 到 764×1028 画幅、
#   逐剪辑帧数与 statemachine.json **全等**（38/38，见 static/kurisu/video-manifest.json）。
# =====================================================================================

# ---- ① 四段原型剪辑补上"视频侧剪辑名"（不是硬编码路径：从图集 src 推导，与图集同源）----
CLIPS_VID_NEW = (
    "  opening:  {src:'/kurisu/full/opening.hi.webp',  frames:84, interval:33.33, cols:8, cw:380, ch:290, fit:'screen',  next:'idle', bootSrc:'/kurisu/full/opening.boot.webp',  bootFrames:24, vid:'opening'},\n"
    "  idle:     {src:'/kurisu/full/idle.hi.webp',     frames:60, interval:42,    cols:8, cw:321, ch:432, fit:'anchor', bootSrc:'/kurisu/full/idle.boot.webp',     bootFrames:24, vid:'idle'},\n"
    "  speaking: {src:'/kurisu/full/speaking.hi.webp', frames:90, interval:34,    cols:8, cw:321, ch:432, fit:'anchor', bootSrc:'/kurisu/full/speaking.boot.webp', bootFrames:24, vid:'speaking_long'},\n"
    "  thinking: {src:'/kurisu/full/thinking.hi.webp', frames:90, interval:34,    cols:8, cw:321, ch:432, fit:'anchor', bootSrc:'/kurisu/full/thinking.boot.webp', bootFrames:24, vid:'thinking_to_key_point'}")

# ---- ② 内联模块本体（零依赖、零第三方请求、<video> 不进 DOM）----
XK_VIDEO_JS = r'''
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
    drawn:0, fallbackDrawn:0, released:0, alphaFail:0, probe:null
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
      if(!V.probe && c.have >= 0) probeAlpha(c);
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
      var x = t.getContext('2d');
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
      if(!V.probe.ok){
        V.alphaFail++;
        c.err.push('alpha 采样不像透明（品红比 ' + V.probe.magentaRatio + '）');
        if(V.alphaFail >= 2){                          /* 连续两次 ⇒ 整站回 pixel（规格 §8） */
          V.mode = 'pixel'; V.disp = false; V.videoOK = false; V.enabled = false;
          V.reason = '连续 ' + V.alphaFail + ' 个剪辑解不出 alpha ⇒ 全站回图集';
          for(var k in V.decoded) release(V.decoded[k], true);
        }else{ fallback(c); }
      }
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
                      gesture:V.gesture, probe:V.probe, errors:V.errors.slice(-4) };
           } };
})();
'''

# =====================================================================================
# T8 第一批：状态机 + 宿主触发（2026-10-15 窗口 C）
# -------------------------------------------------------------------------------------
# 口径（站主 2026-10-15 已批）：
#   · 读 static/kurisu/statemachine.json（38 节点/88 边，root=idle）：出边概率**归一化后**掷骰子；
#     13 个 once_then_hold 播完停末帧；prob=0 的 9 条 = 宿主触发入口，永不被随机取。
#   · 宿主触发四类：voice / emotion / idle（可见且连续 12s 无宿主事件）/ cadence（>25s 无宿主事件兜底）。
#     每次切换记 reason = `auto:<edge>` 或 `host:<kind>`，验收按 reason 统计。
#   · 可复现：?seed=<n>（种子化 RNG）+ ?replay=<base64>（按 timeline 回放）。
#   · 回落：statemachine.json 404 / JSON 解析失败 / 结构不对 ⇒ 模块整体不启用，
#     页面回到原型那套 4 剪辑循环（**绝不白屏** ✗）。
#   · 取帧只用 medium.pages 分页索引 + frame_size —— **不用 opaque_bbox**（U8：该字段实测是坏的）。
#   · 验收旋钮（只在 URL 上生效，默认值不变）：?xk-host=<ms> 压缩宿主节奏、?xk-idle=<ms> 改 idle 阈值、
#     ?xk-sm=off 关掉状态机。报告里必须写明用的是哪个节奏 ✗。
# =====================================================================================
XK_SM_JS = r'''
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
    atlas:{mf:null, mfErr:null, imgs:{}, pending:0, loaded:0, pages:0, budget:1.5},
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
    var ps = c.atlas.medium.pages, i;
    for(i = 0; i < ps.length; i++){ if(i < V.atlas.budget) img(ps[i].url); }
  }
  /* 视频优先、拿不到画图集；两者都没就绪就**不画**（让原型那一帧继续留着，避免闪空）。
     关键：clearRect 滞后到"图真的就绪"那一步 —— 否则会把原型这一帧清成空白（会闪）✗ */
  function paintOps(clip, fi, cw, ch){
    var r = {mode:null, ops:[]};
    if(V.atlas.mf === undefined) return r;          /* 图集清单还没到：什么都不做 */
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
    if(window.__xkSmVoice && V.voiceLineOf) { /* 宿主语音由页面侧调 host()，这里不重复播 */ }
    return true;
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
      for(var i = 0; i < cand.length; i++){
        var cl = cand[i];
        if((V.hostEntries && V.hostEntries.indexOf(cl) >= 0) || V.byClip[cl]) return cl;
      }
    }
    /* 兜底：把 current 的出边里、指向 host 入口的那条挑出来 */
    var es = V.out[V.cur] || [];
    for(var k = 0; k < es.length; k++){
      if(es[k].prob === 0) return es[k].to;
    }
    return V.root;
  }
  function roll(){
    var out = V.out[V.cur] || [];
    var e = pick(out);
    if(!e) return false;
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
               errors:V.errs.slice(-6) };
    }
  };
  /* ★既有门禁（gate-firstscreen 第 251 行）读的是 `window.__xkSM.reasons()` ——
     所以把 API 的方法也挂到 window.__xkSM 这个对象上，两套诊断口径同时可用（都指向同一份状态）。 */
  return assignObj(V, API);
})();
'''

# ---- ③ 两处行为补丁 + 模块注入（主页脚本 / 五页 scene-js 共用同一函数）----
def xk_video_patches(script, is_home):
    """给"带 CLIPS/drawFrame 的那段脚本"接视频层；不带就原样返回（生成器必须可重跑）。

    幂等：CLIPS 行若已是 vid 版就跳过；drawFrame/play 补丁各有一个存在性门。
    ⚠ 顺序要紧：先做 narrow 的 drawFrame 补丁、再注入模块文本 —— 反过来的话
      "  if(!cur) return;" 这个锚点会被注入的模块顶开，补丁直接对不上（本轮踩过）。
    """
    s = script
    if 'const CLIPS' not in s:
        return s                                   # 不是带渲染器的那段（如外壳业务脚本）→ 不碰
    # ① CLIPS 挂视频剪辑名（逐行：已是新版跳过；老版替换；两者都没有（无 bootSrc 的裸 demo）也跳过）
    for old_line, new_line in zip(CLIPS_BOOT_NEW.split('\n'), CLIPS_VID_NEW.split('\n')):
        if s.count(new_line) == 1:
            continue
        if s.count(old_line) == 1:
            s = s.replace(old_line, new_line, 1)
    # ② drawFrame 第一件事：问视频层"这一帧你出得来吗"
    if 'XKV2_BLOCK.draw(cur' not in s:
        s = sub1(s, "  if(!cur) return;",
                 "  /* ★T7：视频层先出帧；它说\"这一帧我出了\"就不再画图集（false = 照原样画图集） */\n"
                 "  if(XKV2_BLOCK.draw(cur, fi, {plan:CLIPS[cur], ctx:ctx, w:canvas.width, h:canvas.height})) return;\n"
                 "  if(!cur) return;",
                 'T7: drawFrame 视频分支')
    # ③ 模块插在 drawFrame 之前（此时 CLIPS/canvas/ctx/CHAR_BOX/rm 都已就绪）
    if 'var XKV2_BLOCK' not in s:
        s = sub1(s, 'function drawFrame(){\n', XK_VIDEO_JS + '\nfunction drawFrame(){\n', 'T7: 注入视频渲染层')
    return s

home_script = xk_video_patches(home_script, True)
# ⚠ 变量对应关系（本轮踩过一次，写清楚免得再错）：
#   shell_scripts[0] = 外壳业务脚本（切 view / 作战室 / 聊天 / 语音）—— **没有** CLIPS/drawFrame；
#   shell_scripts[1] = scene-js（CLIPS / xkClipIm / drawFrame / play / loop）—— 才是要接视频的那段。
#   两个都过一遍 xk_video_patches：它自己按 'const CLIPS' 判断该不该动，不靠调用方猜。
sc = xk_video_patches(sc, False)
s1 = xk_video_patches(s1, False)
shell_scripts[0] = sc
shell_scripts[1] = s1

# =====================================================================================
# T8 第一批：把状态机模块接进两段脚本（主页脚本 / 五页 scene-js 共用同一函数）
# -------------------------------------------------------------------------------------
# 接线点（都在"看不见的逻辑"上，不改任何版式/几何）：
#   ① 模块插在 drawFrame 之前（此时 CLIPS/canvas/ctx/CHAR_BOX 都已就绪）
#   ② drawFrame：状态机就绪且它画得出来 ⇒ 直接 return（与 T7 视频分支同一处契约）
#   ③ loop：状态机接管后由它推进（它内部做 hidden 清零、累加器夹取、指纹记账）
#   ④ 主页 showHud()：开场落定后交出画布（takeOver）
#   ⑤ 语音/情绪：xkVoiceAnim / 表情条 → host('voice'|'emotion') —— 这两类宿主触发要能被看见
# =====================================================================================
def xk_sm_patches(script, is_home):
    """把状态机模块接进"带 CLIPS/drawFrame"的那段脚本；幂等、可重跑。

    ⚠ 顺序 / 锚点纪律（本轮踩过两次，写清楚）：
      · 模块注入用 `function loop(t){\n` 这个锚点（在 drawFrame 之后、T7 从没碰过它）——
        如果拿 drawFrame 当锚点，会和 T7 的注入互踩。
      · T7 的 xkVoiceAnim 补丁先跑（它的锚点是 `function xkVoiceAnim(id){\n`），
        本函数再在函数体开头插入一段 body 补丁：顺序反了 T7 就锚不住。
    """
    s = script
    if 'const CLIPS' not in s:
        return s
    # ① 模块注入（放在 loop 之前：此时 CLIPS/canvas/ctx/CHAR_BOX 都已在作用域里）
    if 'var XK_SM_JS' not in s:
        s = sub1(s, 'function loop(t){\n', XK_SM_JS + '\nfunction loop(t){\n', 'T8: 注入状态机模块')
    # ② drawFrame 分支（紧跟 T7 视频分支之后）
    if 'XK_SM_JS.paintOps' not in s:
        s = sub1(s,
                 "  if(XKV2_BLOCK.draw(cur, fi, {plan:CLIPS[cur], ctx:ctx, w:canvas.width, h:canvas.height})) return;\n",
                 "  if(XKV2_BLOCK.draw(cur, fi, {plan:CLIPS[cur], ctx:ctx, w:canvas.width, h:canvas.height})) return;\n"
                 "  /* ★T8：状态机接管后，这一帧由它决定；它没画出来（图还没到）就照原样走下面的原型逻辑 */\n"
                 "  if(XK_SM_JS.state.tookOver){\n"
                 "    var _sm = XK_SM_JS.paintOps(XK_SM_JS.state.cur, XK_SM_JS.state.fi, canvas.width, canvas.height);\n"
                 "    if(_sm.mode){ XK_SM_JS.applyOps(ctx, _sm.ops); return; }\n"
                 "  }\n",
                 'T8: drawFrame 状态机分支')
    # ③ loop 接管
    if 'XK_SM_JS.tick()' not in s:
        s = sub1(s,
                 "function loop(t){\n  if(!started) return;\n",
                 "function loop(t){\n  if(!started) return;\n"
                 "  /* ★T8：状态机接管后由它推进（含 hidden 清零/累加器夹取/指纹记账）*/\n"
                 "  if(XK_SM_JS.state.tookOver){ XK_SM_JS.tick(); lastT = t; requestAnimationFrame(loop); return; }\n",
                 'T8: loop 状态机接管')
    # ④ 主页：开场落定 → 交出画布（takeOver，只置位置 + start()）
    if is_home and 'XK_SM_JS.takeOver()' not in s:
        s = sub1(s,
                 "function showHud(){\n  if(hudShown) return; hudShown = true;\n",
                 "function showHud(){\n  if(hudShown) return; hudShown = true;\n"
                 "  if(typeof XK_SM_JS !== 'undefined') XK_SM_JS.takeOver();   /* ★T8：开场落定后交给状态机 */\n",
                 'T8: showHud 交出画布')
    # ⑤ 语音/情绪 → 宿主触发（这两条是**主页专属**：`xkVoiceAnim` / `xkVoiceEnd` 只在家页脚本里）
    if 'function xkVoiceAnim(id){\n' in s and 'host:voice' not in s:
        s = sub1(s,
                 "function xkVoiceAnim(id){\n",
                 "function xkVoiceAnim(id){\n"
                 "  /* ★T8：语音是四类宿主触发之一 —— 先按情绪切（更贴语义），再按语音规则进 talking 入口 */\n"
                 "  if(window.__xkSM && window.__xkSM.on){\n"
                 "    var _auto = (typeof XK_VOICE_EMO !== 'undefined' && XK_VOICE_EMO[id]) || null;\n"
                 "    if(_auto) XK_SM_JS.host('emotion', {emotion:_auto});\n"
                 "    XK_SM_JS.host('voice', {line:id}); return;\n"
                 "  }\n",
                 'T8: 语音 → 宿主触发')
    if 'xkmBuild();\n' in s and "host('emotion', {emotion:b.getAttribute" not in s:
        s = sub1(s,
                 "xkmBuild();\n",
                 "xkmBuild();\n"
                 "/* ★T8：点表情点 = 宿主触发 emotion（映射到 prob=0 的情绪入口剪辑）*/\n"
                 "document.addEventListener('click', function(ev){\n"
                 "  var b = ev.target && ev.target.closest ? ev.target.closest('[data-emo]') : null;\n"
                 "  if(!b) return;\n"
                 "  if(window.__xkSM && window.__xkSM.on && typeof XK_SM_JS !== 'undefined')\n"
                 "    XK_SM_JS.host('emotion', {emotion:b.getAttribute('data-emo')});\n"
                 "}, true);\n",
                 'T8: 表情点 → 宿主触发')
    # ⑥ 启动：错开首屏窗口再取 JSON（懒加载，零首屏影响）；主页由 showHud 交出画布
    if 'XK_SM_JS.boot()' not in s:
        s = sub1(s,
                 "started = true; lastT = performance.now();\n",
                 "window.__xkSmIsHome = %s;\n"
                 "function xkSmBoot(){ try{ XK_SM_JS.boot(); }catch(e){} }\n"
                 "setTimeout(xkSmBoot, 600);   /* 与首屏门禁的 1.5s 窗口错开（懒加载，零首屏影响）*/\n"
                 "started = true; lastT = performance.now();\n" % ('true' if is_home else 'false'),
                 'T8: 启动挂钩')
    return s

home_script = xk_sm_patches(home_script, True)
sc = xk_sm_patches(sc, False)
s1 = xk_sm_patches(s1, False)
shell_scripts[0] = sc
shell_scripts[1] = s1
# L1 等 idle → 改为等 boot（531KB）就绪即进场，hi 中途接力
home_script = sub1(home_script,
                   "            const idleIm = img(CLIPS.idle.src);\n"
                   "            if(idleIm.complete && idleIm.naturalWidth){ TRANS = t; }\n"
                   "            else {\n"
                   "              idleIm.addEventListener('load', ()=>{ if(cur === 'opening' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = performance.now(); } }, {once:true});\n"
                   "              idleIm.addEventListener('error', ()=>{ if(cur === 'opening' && !TRANS) TRANS = performance.now(); }, {once:true});\n"
                   "            }",
                   "            const idleR = xkClipIm('idle');\n"
                   "            const idleIm = idleR.im;\n"
                   "            const btIdle = img(CLIPS.idle.bootSrc);\n"
                   "            if(btIdle && !(btIdle.complete && btIdle.naturalWidth)) btIdle.addEventListener('load', ()=>{ if(cur === 'opening' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = performance.now(); } }, {once:true});\n"
                   "            if(idleIm.complete && idleIm.naturalWidth){ TRANS = t; }\n"
                   "            else {\n"
                   "              idleIm.addEventListener('load', ()=>{ if(cur === 'opening' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = performance.now(); } }, {once:true});\n"
                   "              idleIm.addEventListener('error', ()=>{ if(cur === 'opening' && !TRANS) TRANS = performance.now(); }, {once:true});\n"
                   "            }",
                   'T5.6: L1 等 idle boot 就绪即进场')

# ---- ★T31 开场六阶段（注入位置必须在 T5.6 之后，理由见 T31 段注释）----
home_script = sub1(home_script, T31_JS_ANCHOR, T31_JS_ANCHOR + T31_JS, 'T31: 注入六阶段状态机 JS')
home_script = sub1(home_script, T31_PWR_OLD, T31_PWR_NEW, 'T31: 旧通电四拍让位')
home_script = sub1(home_script, T31_TRANS_OLD, T31_TRANS_NEW, 'T31: opening 末帧 → xkTransStart()')
home_script = sub1(home_script, T31_START_OLD, T31_START_NEW, 'T31: 启动处起六阶段')
home_script = sub1(home_script, T31_DRAW_OLD, T31_DRAW_NEW, 'T31: xkDrawTrans 同源取帧')

# ★批次1（2026-10-15 站主决定）：三张非壁纸图 **不再从标记里拿掉** ✗
#   —— `.glow/.backplate/.plate` 就留在标记里（与 T7 逐字一致），"T=0 只见壁纸"由 T31_CSS 的
#      `html[data-xk-boot="…"]` 可见性门控实现。同时必须**禁掉 xkBootPreload 的插入**，
#      否则同一个 class 会在页面上出现两份（第一份静态、第二份 JS 插入）。
home_script, _n = re.subn(
    r"\nfunction xkBootPreload\(\)\{\n.*?\n\}\n",
    "\nfunction xkBootPreload(){\n"
    "  /* ★批次1（2026-10-15 站主）：三张背景层已经在标记里（与 T7 一致）⇒ 这里不再 createElement 插入，\n"
    "     只标记\"预载阶段已到\"；开场靠 CSS 的 data-xk-boot 可见性门控逐层显示。\n"
    "     ★P0-④（2026-10-16 站主追加②）：**按出现顺序串行优先 + 每张 decode() 完再生效** ——\n"
    "       壁纸(desk) 已在 phase 0 显示（head 里 preload + fetchpriority=high，唯一抢带宽的一张）；\n"
    "       这里按 光晕(glow) → 背板(backplate) → 字幕框(plate) 逐张 decode()，解完才置位 data-xk-boot-ready；\n"
    "       她的首帧(opening) 由 xkBootWaitFace() 等到 complete 才开始闪断 ⇒ 四张的先后是**事件驱动**的，不是猜时间。\n"
    "       顺序与耗时写进 window.__xkFirstPaint.order（验收脚本 _dev/firstscreen-order.mjs 读它）。*/\n"
    "  var FP = window.__xkFirstPaint = window.__xkFirstPaint || { t0: Math.round(performance.now()), order: [] };\n"
    "  function xkDec(el, name, next){\n"
    "    if(!el){ next(); return; }\n"
    "    var done = function(){ FP.order.push({ name: name, at: Math.round(performance.now() - FP.t0) }); next(); };\n"
    "    var go = function(){ if(el.decode){ el.decode().then(done, done); } else { done(); } };\n"
    "    if(el.complete && el.naturalWidth){ go(); return; }\n"
    "    el.addEventListener('load', go, {once:true});\n"
    "    el.addEventListener('error', done, {once:true});\n"
    "  }\n"
    "  xkDec(document.querySelector('.glow'), 'glow', function(){\n"
    "    xkDec(document.querySelector('.backplate'), 'backplate', function(){\n"
    "      xkDec(document.querySelector('.plate'), 'plate', function(){\n"
    "        document.documentElement.setAttribute('data-xk-boot-ready', '1');\n"
    "      });\n"
    "    });\n"
    "  });\n"
    "}\n",
    home_script, count=1, flags=re.S)
if _n != 1:
    raise SystemExit('批次1: xkBootPreload 匹配 %d 次（期望 1）' % _n)
for _cls in ('glow', 'backplate', 'plate'):
    if len(re.findall(r'class="%s"' % _cls, home_body)) != 1:
        raise SystemExit('批次1: 标记里的 .%s 不是恰好 1 个' % _cls)
home_body = sub1(home_body, T31_CRTBOOT_ANCHOR, T31_CRTBOOT_NEW, 'T31: 插入 .crtboot 覆盖层')

# =====================================================================================
# ★T27 收尾（2026-10-15 窗口 Q）：靶场页(v-range)删了，但 demo 自带的那段**靶场演示脚本**
#   还留在外壳的第一段 <script> 里 —— 它开头就是
#       document.getElementById('pgBtn').onclick = ...
#   而 pgBtn 随 v-range 一起消失 ⇒ 五个内容页每页抛一条
#       TypeError: Cannot set properties of null (setting 'onclick')
#   （实测：gate-firstscreen 报 monitor/notes/ai console=2）。这段本来就是站主点名的"本地假结果"
#   （PG_DEMO 里写死五条判定文案），所以整段删掉，而不是加个 if 守卫留尸体。
#   删完做残留断言：PG_DEMO / runPg / pgBtn / pgInput / .pgrun 一个都不许剩。
# =====================================================================================
_pg_re = re.compile(r"\n/\* ============ 靶场演示 ============ \*/.*?runPg\(b\.dataset\.pg\); \}\);\n", re.S)
shell_scripts[0], _pg_n = _pg_re.subn('\n', shell_scripts[0], count=1)
if _pg_n != 1:
    raise SystemExit('T27: 靶场演示脚本块匹配 %d 次（期望 1）—— demo 外壳的第一段 <script> 动过？' % _pg_n)
_pg_left = [k for k in ('PG_DEMO', 'runPg(', "'pgBtn'", "'pgInput'", "'.pgrun'", 'pgResult') if k in shell_scripts[0]]
if _pg_left:
    raise SystemExit('T27: 靶场演示脚本还残留 %s' % ','.join(_pg_left))

# =====================================================================================
# ★Q-2（2026-10-15 站主两条意见 · 规划侧转达 · 窗口 Q 落地）
#   ① "左上角 CRT 屏内一排彩色圆点（主题/配色切换器）"：
#      那是 **T8 给"手工宿主情绪触发"加的表情圆点条** `.xk-emo-bar`（xkmBuild 造点 + xkmReveal 显示
#      + document 上的 `[data-emo]` click 委托）。**情绪能力保留**（语音 → XK_VOICE_EMO →
#      XK_SM_JS.host('emotion') 那条路一字不动，T14 的 LLM 决策也从这条路进来），只删**控件**。
#   ② "屏内右侧 SEC-LAB · 读不到 数据卡"：demo 主页自带的 `#crtStatus`
#      （24h 告警 / 拦截 / 蜜罐交互 / sync）。**只从主页删**整块（含 CSS 与 showHud 里那一行），
#      /alerts/ 上的同类信息不动。
#   ③ 同时把五个内容页 HOLO 面板里 demo 自带的那排情绪点（`.emos` / `#emos`）也收掉：
#      它和①是**两个**东西（主页 demo 里根本没有 emos），但都是"一排彩色圆点外观控件"，
#      站主口径是"所有页面都不要这种控件"。删除的是控件本身（标记 + CSS + 点击绑定），
#      情绪状态机与语音联动不动（emotion 仍由语音/宿主驱动）。
#   删完逐个断言：这些 class/id 在主页产物里必须 0 命中。
# =====================================================================================
def _q2_drop(hay, pat, what, repl=''):
    global _Q2_N
    out, n = re.subn(pat, repl, hay, count=1, flags=re.S)
    if n != 1:
        raise SystemExit('Q-2: %s 匹配 %d 次（期望 1）' % (what, n))
    return out

# ① 主页表情圆点条（T8 加的控件）
home_script = _q2_drop(home_script, r"\nfunction xkmBuild\(\)\{.*?\n\}\nfunction xkmReveal\(\)\{.*?\n\}\n",
                       '主页 .xk-emo-bar 构造/显示函数', '\n')
home_script = _q2_drop(home_script, r"\nxkmBuild\(\);\n", '主页 xkmBuild() 调用', '\n')
home_script = _q2_drop(home_script,
                       r"\n/\* [^\n]*点表情点[^\n]*\*/\ndocument\.addEventListener\('click', function\(ev\)\{\n.*?\}, true\);\n",
                       '主页表情点 click 委托', '\n')
home_script = _q2_drop(home_script, r"\n[ \t]*if\(typeof xkmReveal === 'function'\) xkmReveal\(\);[^\n]*",
                       'showHud 里的 xkmReveal() 调用')
# 圆点条没了 ⇒ "高亮当前情绪那一个点"的 xkmMark 也成了纯死码，连函数带唯一调用点一起删
home_script = _q2_drop(home_script, r"\nfunction xkmMark\(name\)\{.*?\n\}\n", '主页 xkmMark() 定义', '\n')
home_script = _q2_drop(home_script, r"; xkmMark\(name\);", '主页 xkmSetEmotion 里的 xkmMark() 调用', ';')

# ② 主页 SEC-LAB 状态卡（demo 自带）—— CSS / 标记 / 三处脚本引用
home_style = _q2_drop(home_style, r"\n[ \t]*\.crt-status\{[^}]*\}\n[ \t]*\.crt-status \.ok\{[^}]*\}",
                      '主页 .crt-status CSS')
home_body = _q2_drop(home_body, r"\n[ \t]*<div class=\"crt-status\" id=\"crtStatus\" hidden>.*?\n[ \t]*</div>",
                     '主页 #crtStatus 标记')
home_script = _q2_drop(home_script, r"\n[ \t]*const st = document\.getElementById\('crtStatus'\);\n[ \t]*if\(st\)\{[^\n]*\}\n",
                       '主页降级分支里的 #crtStatus 写入', '\n')
home_script = _q2_drop(home_script, r"\n[ \t]*document\.getElementById\('crtStatus'\)\.hidden = false;",
                       '主页 showHud 里的 #crtStatus 显示')
home_script = _q2_drop(home_script,
                       r"document\.querySelector\('\.crt-status'\) \|\| document\.getElementById\('crtStatus'\) \|\| ",
                       '主页状态行观察器的 .crt-status 选择器')

# ③ 五个内容页 HOLO 面板里的 demo 表情点（控件）
chrome = _q2_drop(chrome, r"\n[ \t]*<div class=\"emos\" id=\"emos\"[^>]*>.*?\n[ \t]*</div>",
                  '内容页 .emos 标记')
for _rule in (r"\.holo-ft \.emos\{", r"\.holo-ft \.emos b\{", r"\.holo-ft \.emos b\.on\{"):
    shell_style = _q2_drop(shell_style, r"\n[ \t]*" + _rule + r"[^}]*\}", '内容页 CSS ' + _rule)
shell_scripts[0] = _q2_drop(shell_scripts[0],
                            r"\ndocument\.querySelectorAll\('#emos b'\)\.forEach\(b=>b\.onclick = \(\)=>\{\n.*?\n\}\);\n",
                            '内容页 #emos 点击绑定', '\n')

# 断言：主页产物里不许再出现这些 class/id（站主要求 grep 命中 = 0）
_home_all = home_style + home_body + home_script
_q2_left = [k for k in ('crt-status', 'crtStatus', 'SEC-LAB', 'xk-emo-bar', 'xkEmoBar', 'xkmBuild', 'xkmReveal')
            if k in _home_all]
if _q2_left:
    raise SystemExit('Q-2: 主页残留 %s' % ','.join(_q2_left))
_cont_all = chrome + shell_style + shell_scripts[0]
_q2_left2 = [k for k in ('class="emos"', "id=\"emos\"", '#emos', '.holo-ft .emos') if k in _cont_all]
if _q2_left2:
    raise SystemExit('Q-2: 内容页残留 %s' % ','.join(_q2_left2))

# =====================================================================
# ★外部审查 R3（2026-10-16）· 布局优化补丁（LAYOUT_PATCH）
#   原则：**每一条规则都写在 @media (max-width:980px) / (max-width:520px) 之内**，
#         桌面端（>980px）一个像素都不动 ⇒ 不影响既有首屏字节门禁与像素比对。
#   依据（R1 现场只读实测）：
#     ① 触控：只有 .dock 被抬到 44px；.ops-tabs button≈32px、.holo-fold=22px 仍不达标
#     ② 溢出：.attk 七列在 375px 视口下 ⇒ 每格约 53px（内含 19px 大数字）
#     ③ 遮挡：.holo 展开态 top:52px，与 .main padding-top:76px 仍重叠约 195px
#     ④ 留白：.main padding-right:310px 在 holo 收起后整条右侧空白
#     ⑤ 断点：外壳只有 980px 一档（extended 另有 1199/520）⇒ 320~980px 共用一套
# ---------------------------------------------------------------------
LAYOUT_PATCH = u'''
  /* ★R3 布局补丁（2026-10-16 外部审查）—— 以下全部只在 ≤980px 生效 */
  @media (max-width:980px){
    /* ① 交互件命中区补齐到 44px（只动命中区，配色/字号/边框色一个字节不改） */
    .ops-tabs button{min-height:44px;display:inline-flex;align-items:center;justify-content:center}
    .holo-fold{width:34px;height:34px;flex:none}
    .anchor-row a{min-height:38px;display:inline-flex;align-items:center}
    .chat-ft button{min-height:44px}
    .chat-ft input{min-height:44px}
    /* ② holo 收起（.holo-min）后主区不再白留 310px */
    body.holo-min .main{padding-right:12px}
    /* ③ 攻击矩阵七格 → 窄屏四格，避免每格被压到 50px 以下 */
    .attk{grid-template-columns:repeat(4,1fr)}
    .attk .cell{min-height:64px}
    /* ④ 展开态 holo 限高并给正文让位 */
    .holo{max-height:calc(100dvh - 210px);max-height:calc(100vh - 210px)}
  }
  @media (max-width:520px){
    /* ⑤ 极窄屏：统计卡单列；聊天区改动态高度，避开 667px 矮屏溢出 */
    .stats{grid-template-columns:1fr}
    .attk{grid-template-columns:repeat(3,1fr)}
    .chat{height:auto;max-height:calc(100vh - 150px);min-height:320px}
  }
'''

# =====================================================================
# ★批次 A-①（2026-10-16 站主 UI 指令）：左上角头像卡片 + 声音开关 + 登录（访客不可见）
#   站主原话：① 把她的头像放到**左上角**（圆角方形卡片头像，形状照原右上角那块卡片头，**不是小圆点**）；
#             ② 头像**右边**两个小按钮**竖排**（尺寸小、不抢导航）：
#                上 = 声音开关（🔊）**默认关闭**、点开才出声、状态存 localStorage、显示当前状态；
#                下 = 登录按钮（👤）—— ★追加：**访客不要显示**（这是他自己的功能），只留隐蔽入口；
#             ③ 其他新功能一律先放导航栏的「测试」栏目（= 现有 /test/ 实验台）。
#   实现：一整份 partial `layouts/partials/xk-demo/idcard.html`（自带 <style> + <script>，五页共用一份）；
#         五个宿主页各 include 一次；`<body class="xk-has-idcard">` 让既有 .dock 下移给它让位
#         （窄屏 dock 在底部，不受影响）。
#   纪律：不许硬编码任何令牌 ✗ —— 登录态只按 Cloudflare Access 的 Cookie **存在性**判定，
#         不读取、不存储、不打日志（见 docs/登录入口与自用模式-20261016.md）。
# =====================================================================
DOCK_ANCHOR_CONTENT = '<a href="/posts/" class="{{ if eq $v "notes" }}on{{ end }}">笔记</a>\n'
DOCK_ANCHOR_HOME = '<a href="/posts/">笔记</a>\n'
DOCK_TEST_CONTENT = '<a href="/test/" class="{{ if eq $v "test" }}on{{ end }}">测试</a>\n'
DOCK_TEST_HOME = '<a href="/test/">测试</a>\n'
chrome = sub1(chrome, DOCK_ANCHOR_CONTENT, DOCK_ANCHOR_CONTENT + '  ' + DOCK_TEST_CONTENT,
              'batchA: 外壳 dock 新增「测试」项')
home_body = sub1(home_body, DOCK_ANCHOR_HOME, DOCK_ANCHOR_HOME + '  ' + DOCK_TEST_HOME,
                 'batchA: 主页 dock 新增「测试」项')
# ★P0-④（站主 2026-10-16 追加②）：首屏**只给壁纸抢带宽** —— 它是"要展示的第一张"。
#   其余三张（背板 / 她首帧 / 字幕框）不抢，按出现顺序由 xkBootPreload() 逐张 decode() 完再生效。
home_body = sub1(home_body,
                 '<img class="desk" src="/images/crt/desk.webp"',
                 '<img class="desk" fetchpriority="high" src="/images/crt/desk.webp"',
                 'P0-④: 壁纸 fetchpriority=high')

IDCARD_PARTIAL = u'''{{- /* ★批次 A-①（2026-10-16 站主 UI 指令）· 左上角：她的头像卡片 + 两个小按钮
   ---------------------------------------------------------------------------
   站主口径（原话）：① 把她的头像放到左上角（圆角方形卡片头像，形状照原右上角那块卡片头，
     不是小圆点）；② 头像右边两个小按钮竖排、尺寸小不抢导航：
       上 = 声音开关（🔊）默认关闭 · 点开才出声 · 状态存 localStorage['xk-sound-on'] · 显示当前状态；
       下 = 登录按钮（👤）—— 访客**不可见**（站主追加：这是他自己的功能），只留隐蔽入口。
   隐蔽入口（两个都做了，任选其一）：
     a) URL 参数 `?admin=1` 或 hash `#admin`；b) 1.5 秒内连点头像 5 次。
     触发后本会话一直显示（sessionStorage['xk-admin-ui']=1）；已登录（Access Cookie 在）也一直显示。
   纪律：**绝不硬编码任何令牌** ✗ —— 登录态只按 Cloudflare Access 的 Cookie 存在性判定，不读取、不存储。
   素材：8 类情绪 = static/kurisu/avatar/<emo>.idle.webp（132px 单元 · 8 列，与 HOLO 面板同一套）；
         8 个常用动作 = static/kurisu/manifest.json clipsMedium 里**真实存在**的剪辑名（只在主页全身画布上演）。
   固定台词：LINE_ZH 是入口 → 中文口语台词（音轨文件与 lineId 不变；表见 docs/台词表-入口与固定台词-20261016.md），
            同时挂到 window.__xkLineZh，主页内联播放器(HOME_VOICE)读同一份文案 ⇒ 五页只有一份文案。
   诊断：window.__xkId = {sound, emo, admin, loggedIn, panel, plays, errors}
   ⚠ /ai/ 冷缓存首屏超预算的**真凶不在本偏件**（2026-10-16 实测，别照旧推论改错地方）：
     冷缓存直访 /ai/ = 1652KB > 1650KB，构成只有三个 ——
       /kurisu/full/speaking.hi.webp 1554.7KB（外壳手机的"说话"全身图集，shell-script.html 的 render() 首帧就取）
       /kurisu/avatar/normal.idle.webp 84.7KB（外壳 HOLO 头像，render() 里的 bubbleAv）
       /favicon-128.png 13.0KB
     ⇒ 已按施工单 §1"选项 1"的等价做法修在 **shell-script.html 那一侧**：/ai/ 页 `body.is-ai`
       下 `.holo`/`.holo-bubble` 本来就被 CSS `display:none`（shell-style.html），
       而手机面板是 `v-ai` 的常驻件 ⇒ 首帧不再空取这两张（延后到 1.8s / 2.6s 的用户可见时刻）。
       本偏件的头像图**保持立刻取**（它是真·首屏可见元素，且 84.7KB 不是那次的超支项）。
     验收：`_dev/gate-firstscreen.mjs --cold`（warm 与冷缓存两套口径，别混用）。
   ★改生成物要先改生成器：本文件由 _dev/gen-demo-pages.py 的 IDCARD_PARTIAL 写出。 */ -}}
<style>
  /* 左上角：她的头像卡片（圆角方形卡片头 + 两个小按钮竖排）
     值只新增这一组，不改任何既有配色/字体/背景（站主点名的"头像卡片"这一处新增） */
  .xk-idcard{position:fixed;left:0;top:14px;z-index:61;display:flex;align-items:center;gap:5px;
    padding:6px 4px;background:var(--solid,rgba(48,45,41,.82));border:1px solid var(--line2,rgba(255,246,235,.28));
    border-left:none;border-radius:0 14px 14px 0;box-shadow:0 10px 34px rgba(0,0,0,.45);backdrop-filter:blur(4px)}
  .xk-idcard-av{width:48px;height:48px;flex:none;padding:0;cursor:pointer;display:block;
    border:1px solid var(--line2,rgba(255,246,235,.28));border-radius:10px;overflow:hidden;
    background:#E8ECEF;line-height:0}
  .xk-idcard-av canvas{width:48px;height:48px;display:block}
  .xk-idcard-col{display:flex;flex-direction:column;gap:4px}
  .xk-idcard-btn{width:24px;height:24px;padding:0;cursor:pointer;font-size:12px;line-height:1;
    display:flex;align-items:center;justify-content:center;
    border:1px solid var(--line2,rgba(255,246,235,.28));border-radius:8px;
    background:rgba(0,0,0,.22);color:var(--txt,#FAF7F0)}
  /* ★必须留着这一条：上面的 display:flex 会盖掉浏览器对 [hidden] 的 display:none ⇒ 登录按钮会对访客露出来 */
  .xk-idcard-btn[hidden]{display:none}
  .xk-idcard-btn:hover{color:var(--acc,#7FD4D8);border-color:var(--acc,#7FD4D8)}
  .xk-idcard-btn[aria-pressed="true"]{color:var(--acc,#7FD4D8);border-color:var(--acc,#7FD4D8);
    background:rgba(57,208,216,.12)}
  .xk-idcard-btn:focus-visible,.xk-idcard-av:focus-visible{outline:2px solid var(--acc,#7FD4D8);outline-offset:2px}
  /* 给她让位：既有左侧 dock 下移（仅 >980px；窄屏 dock 在底部，规则在下面那条媒体查询里复位） */
  body.xk-has-idcard .dock{top:88px}
  .xk-idcap{position:fixed;left:6px;top:88px;z-index:62;max-width:250px;
    font:11.5px/1.5 var(--sans,sans-serif);color:var(--txt,#FAF7F0);
    background:var(--solid,rgba(48,45,41,.94));border:1px solid var(--line2,rgba(255,246,235,.28));
    border-radius:10px;padding:6px 9px;opacity:0;transition:opacity .2s;pointer-events:none}
  .xk-idcap.on{opacity:1}
  .xk-idpanel{position:fixed;left:96px;top:88px;z-index:63;width:252px;display:none;
    background:var(--solid,rgba(48,45,41,.96));border:1px solid var(--line2,rgba(255,246,235,.28));
    border-radius:12px;padding:10px 11px;box-shadow:0 14px 40px rgba(0,0,0,.5);backdrop-filter:blur(4px);
    font:11.5px/1.5 var(--sans,sans-serif);color:var(--txt,#FAF7F0)}
  .xk-idpanel.open{display:block}
  .xk-idpanel h4{font:600 12px/1.4 var(--sans,sans-serif);margin-bottom:6px}
  .xk-idpanel .xk-row{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:9px}
  .xk-idpanel .xk-chip{font:11px/1.4 var(--sans,sans-serif);padding:3px 8px;border-radius:99px;cursor:pointer;
    border:1px solid var(--line2,rgba(255,246,235,.28));background:rgba(0,0,0,.2);color:var(--mut,#D2CBBD)}
  .xk-idpanel .xk-chip:hover,.xk-idpanel .xk-chip.on{color:var(--acc,#7FD4D8);border-color:var(--acc,#7FD4D8)}
  .xk-idpanel .xk-note{font:10.5px/1.5 var(--mono,monospace);color:var(--mut,#D2CBBD);margin-top:2px}
  .xk-idpanel .xk-close{position:absolute;right:7px;top:5px;background:none;border:0;cursor:pointer;
    color:var(--mut,#D2CBBD);font-size:13px;line-height:1;padding:2px}
  @media (max-width:980px){
    body.xk-has-idcard .dock{top:auto}
    .xk-idcard-av{width:56px;height:56px}
    .xk-idcard-av canvas{width:56px;height:56px}
    .xk-idcard-btn{width:34px;height:34px;font-size:15px}
    .xk-idcap{top:104px}
    .xk-idpanel{left:6px;top:104px}
  }
</style>
<aside class="xk-idcard" id="xkIdCard" aria-label="桐莉栖 · 头像卡">
  <button class="xk-idcard-av" id="xkIdAv" type="button"
    title="点一下：换个情绪说一句 · 长按半秒：打开情绪与动作面板"
    aria-label="桐莉栖头像：点一下换个情绪并说一句，长按半秒打开情绪与动作面板">
    <canvas id="xkIdAvCanvas" width="132" height="132" aria-hidden="true"></canvas>
  </button>
  <span class="xk-idcard-col">
    <button class="xk-idcard-btn" id="xkSndBtn" type="button" aria-pressed="false"
      title="声音：默认关闭（点一下打开）">🔇</button>
    <button class="xk-idcard-btn" id="xkLoginBtn" type="button" title="登录（自用模式）" hidden>👤</button>
  </span>
</aside>
<div class="xk-idcap" id="xkIdCap" role="status" aria-live="polite"></div>
<div class="xk-idpanel" id="xkIdPanel" role="dialog" aria-label="桐莉栖 · 情绪与动作面板"></div>
<script>
/* 桐莉栖 · 头像卡（左上角）· 批次 A-①
   1) 声音开关：默认关；状态存 localStorage['xk-sound-on']；所有播放器统一读 window.__xkSound.on
   2) 登录：访客不渲染；隐蔽入口 ?admin=1 / #admin / 1.5s 内连点头像 5 次；绝不硬编码令牌
   3) 点头像 = 切下一个情绪 + 说一句；长按 >=500ms = 开面板（8 情绪 + 8 常用动作） */
(function () {
  'use strict';
  if (window.__xkId) { return; }
  var D = { sound: false, emo: 'normal', admin: false, loggedIn: false, panel: false, plays: 0, errors: [] };
  window.__xkId = D;
  function lg(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function ls(k, v) { try { localStorage.setItem(k, v); } catch (e) { } }
  function sg(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } }
  function ss(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { } }

  var EMOS8 = [
    ['normal', '普通', '/kurisu/avatar/normal.idle.webp'],
    ['happy', '开心', '/kurisu/avatar/happy.idle.webp'],
    ['sided_thinking', '思考', '/kurisu/avatar/sided_thinking.idle.webp'],
    ['sided_surprised', '惊讶', '/kurisu/avatar/sided_surprised.idle.webp'],
    ['sad', '难过', '/kurisu/avatar/sad.idle.webp'],
    ['blush', '害羞', '/kurisu/avatar/blush.idle.webp'],
    ['angry', '生气', '/kurisu/avatar/angry.idle.webp'],
    ['disappointed', '失望', '/kurisu/avatar/disappointed.idle.webp']
  ];
  /* 8 个常用动作 = static/kurisu/manifest.json 的 clipsMedium 里**真实存在**的剪辑名（不编名字 ✓） */
  var ACTS8 = [
    ['trans_standby', '待机待命'], ['trans_smile', '微笑'], ['thinking_trans', '思考入戏'],
    ['surprise_trans', '惊讶一下'], ['shy_trans', '害羞低头'], ['angry_trans', '生气'],
    ['sad_trans', '失落'], ['idle_closed_eye', '闭眼歇会儿']
  ];
  /* 固定台词表（口语版 · 入口 → 中文）。音轨文件与 lineId 一字不改；日语音轨仍是上一版录音，
     下一批重录时按这张表逐句重生成（见 docs/台词表-入口与固定台词-20261016.md）。 */
  var LINE_ZH = {
    greet_first: '你好，我是桐莉栖。这一屏的数字都是真的，看不清就凑近一点。',
    greet_back: '又见到你了。数据还是真的，我没换过口径。',
    nav_home: '回到主页了。我一直待在这台显示器里。',
    nav_monitor: '这一屏是我们监测到的情况，数字都是真的；取不到我就写读不到。',
    nav_ai: '有问题就问我，我照真检索到的东西答；答不了我就说答不了。',
    nav_notes: '笔记都在这儿，新的排在最前面。',
    fallback_no_data: '这次没读到数据。我不补数，读不到就是读不到。',
    fallback_offline: '请求没送达。我不编答案，等接口恢复再说。',
    fallback_throttled: '接口在限流，等一下再问。',
    tab_return: '你回来了。刚才我没说话，只是在这儿等着。'
  };
  window.__xkLineZh = LINE_ZH;
  var GROUP_OF = { greet_first: 'greeting', greet_back: 'greeting', tab_return: 'idle_banter',
    nav_home: 'page_intro', nav_monitor: 'page_intro', nav_ai: 'page_intro', nav_notes: 'page_intro',
    fallback_no_data: 'fallback', fallback_offline: 'fallback', fallback_throttled: 'fallback' };
  window.__xkLineGroup = GROUP_OF;   /* 统一播放器那边要用"这句属于哪个组"（与 bank 的 trigger 同源约定） */
  var EMO_LINE = { normal: 'nav_home', happy: 'greet_back', sided_thinking: 'nav_ai',
    sided_surprised: 'nav_monitor', sad: 'fallback_no_data', blush: 'greet_first',
    angry: 'fallback_throttled', disappointed: 'fallback_no_data' };

  var av = document.getElementById('xkIdAv'), cv = document.getElementById('xkIdAvCanvas');
  var cap = document.getElementById('xkIdCap'), panel = document.getElementById('xkIdPanel');
  var snd = document.getElementById('xkSndBtn'), login = document.getElementById('xkLoginBtn');
  if (!av || !cv || !cap || !panel || !snd || !login) { return; }

  /* ---------- 头像小播放器（132px 单元 · 8 列；只取用到的那个情绪的 idle 图） ----------
     ⚠ 帧数只取 **3**：manifest.json 里 emotions.*.idle 全是 {columns:8, frames:3, atlasW:1056}
     —— 图集是 8 列宽，但只有前 3 格有画面，后 5 格是空位；按"列数×行数"算会画到空位（实测：头像整块变白）。
     清单到位后（空闲预取那张）再用真值覆盖一次，防止以后素材改成 8 帧。 */
  var ctx = cv.getContext('2d'), CELL = 132, COLS = 8, framesOf = {}, imgs = {}, url = {}, last = 0, fi = 0;
  EMOS8.forEach(function (e) { url[e[0]] = e[2]; framesOf[e[0]] = 3; });
  function im(u) { if (!imgs[u]) { var i = new Image(); i.decoding = 'async'; i.src = u; imgs[u] = i; } return imgs[u]; }
  function paint() {
    var u = url[D.emo] || url.normal, g = im(u);
    if (!g.complete || !g.naturalWidth) { return; }
    var n = framesOf[D.emo] || 3;
    if (g.naturalWidth === CELL) { n = 1; }
    var k = n > 1 ? (fi % n) : 0;
    ctx.clearRect(0, 0, CELL, CELL);
    ctx.drawImage(g, (k % COLS) * CELL, Math.floor(k / COLS) * CELL, CELL, CELL, 0, 0, CELL, CELL);
  }
  (function tick(t) {
    requestAnimationFrame(tick);
    if (!last) { last = t; }
    if (t - last > 150) { last = t; fi++; paint(); }
  })(0);
  /* 头像图**立刻**开始取（首屏可见元素），并且不依赖 rAF 也一定能画上：
     实测 headless 下 rAF 有被节流的情况（截图里头像整块是底板色 #E8ECEF 的白方块）
     ⇒ 补一组"载入即画 + 几个时间点的兜底重画"。 */
  (function () {
    var g = im(url[D.emo]);
    if (g && g.addEventListener) { g.addEventListener('load', paint, { once: true }); }
    paint();
    [250, 700, 1500, 3000].forEach(function (ms) { setTimeout(paint, ms); });
  })();
  function setEmo(name) {
    if (!url[name]) { return false; }
    D.emo = name; fi = 0;
    var g = im(url[name]);
    if (g.complete && g.naturalWidth) { paint(); } else { g.addEventListener('load', paint, { once: true }); }
    markPanel();
    /* 主页：全身画布也一起切（那份状态机在主页内联脚本里；其它页没有 ⇒ 只动头像） */
    if (typeof window.xkmSetEmotion === 'function') { try { window.xkmSetEmotion(name); } catch (e) { D.errors.push('xkm: ' + e); } }
    return true;
  }

  /* ---------- 字幕条（只报真话：没出声就说没出声） ---------- */
  var capTimer = 0;
  function say(text) {
    cap.textContent = text;
    cap.classList.add('on');
    clearTimeout(capTimer);
    capTimer = setTimeout(function () { cap.classList.remove('on'); }, 7000);
  }
  /* 念一句：声音关着 ⇒ 只出字幕；开着 ⇒ 交给真正的语音层（统一播放器优先，其次是主页内联那份） */
  function speak(id, prefix, force) {
    var zh = LINE_ZH[id] || '';
    var head = prefix ? (prefix + ' —— ') : '';
    if (!D.sound && !force) { say(head + zh + '（声音默认关：点左上角 🔊 才出声）'); return false; }
    var grp = GROUP_OF[id], ok = false;
    try {
      if (grp && window.KurisuPlayer && typeof window.KurisuPlayer.speakGroup === 'function') {
        var pr = window.KurisuPlayer.speakGroup('/', grp, { preferId: id });
        ok = true;
        if (pr && pr.then) {
          pr.then(function (r) {
            if (r && r.ok) { D.plays++; }
            else { D.errors.push('speak: ' + ((r && r.reason) || '?')); }
          });
        }
      } else if (typeof window.xkvPlay === 'function') { window.xkvPlay(id); ok = true; }
    } catch (e) { D.errors.push('speak: ' + e); }
    /* 没有任何语音层时只出字幕（**如实**记进 D.errors，不假装念过；音频在下一批接上） */
    if (!ok) { D.errors.push('no-voice-layer: ' + id); }
    say(head + zh);
    return ok;
  }

  /* ---------- 声音开关（默认关；访客可见） ---------- */
  function setSound(v, why) {
    D.sound = !!v;
    ls('xk-sound-on', D.sound ? '1' : '0');
    window.__xkSound = { on: D.sound, set: setSound, toggle: toggleSound };
    /* 开声 = 用户手势 ⇒ 这一刻必须保证统一播放器在位（按需加载那条） */
    if (D.sound) { loadPlayer(); }
    snd.textContent = D.sound ? '🔊' : '🔇';
    snd.setAttribute('aria-pressed', D.sound ? 'true' : 'false');
    snd.setAttribute('title', D.sound ? '声音：已打开（点一下关掉）' : '声音：已关闭（点一下打开）');
    try { window.dispatchEvent(new CustomEvent('xk-sound', { detail: { on: D.sound, why: why || 'btn' } })); } catch (e) { }
  }
  function toggleSound() { setSound(!D.sound, 'btn'); }
  snd.addEventListener('click', toggleSound);
  setSound(lg('xk-sound-on') === '1', 'restore');

  /* ---------- 登录（站主自用；访客不渲染这个按钮） ---------- */
  function accessCookie() { try { return document.cookie.indexOf('CF_Authorization=') >= 0; } catch (e) { return false; } }
  function revealLogin(why) {
    if (!login.hidden) { return; }
    login.hidden = false;
    D.admin = true; D.revealWhy = why;
    ss('xk-admin-ui', '1');
  }
  function applyLogin() {
    D.loggedIn = accessCookie();
    if (D.loggedIn) { revealLogin('access-cookie'); }
    login.setAttribute('aria-pressed', D.loggedIn ? 'true' : 'false');
    login.textContent = D.loggedIn ? '🔓' : '👤';
    login.title = D.loggedIn ? '已登录 · 自用模式' : '登录（自用模式；通道待接入）';
  }
  login.addEventListener('click', function () {
    if (D.loggedIn) { say('已登录 · 自用模式（本会话本地状态；凭据不经前端）'); return; }
    say('登录通道待接入（需开 Cloudflare Access）—— 开了之后这里才会真的登录。');
  });
  (function () {
    var q = /(^|[?&])admin=1(&|$)/.test(location.search);
    var h = /#admin(\.|$|\/|\?)/.test(location.hash) || location.hash === '#admin';
    if (q || h) { revealLogin(q ? 'url-query' : 'url-hash'); }
    else if (sg('xk-admin-ui') === '1') { revealLogin('session'); }
  })();
  applyLogin();

  /* ---------- 面板：8 情绪 + 8 常用动作 ---------- */
  function labelOf(n) { for (var i = 0; i < EMOS8.length; i++) { if (EMOS8[i][0] === n) { return EMOS8[i][1]; } } return n; }
  function labelOfAct(n) { for (var i = 0; i < ACTS8.length; i++) { if (ACTS8[i][0] === n) { return ACTS8[i][1]; } } return n; }
  function markPanel() {
    Array.prototype.forEach.call(panel.querySelectorAll('[data-emo]'), function (b) {
      b.className = (b.getAttribute('data-emo') === D.emo) ? 'xk-chip on' : 'xk-chip';
    });
  }
  (function buildPanel() {
    var h = ['<h4>情绪（点一下，她演出来）</h4><div class="xk-row">'];
    EMOS8.forEach(function (e) { h.push('<button type="button" class="xk-chip" data-emo="' + e[0] + '">' + e[1] + '</button>'); });
    h.push('</div><h4>常用动作</h4><div class="xk-row">');
    ACTS8.forEach(function (a) { h.push('<button type="button" class="xk-chip" data-act="' + a[0] + '">' + a[1] + '</button>'); });
    h.push('</div><p class="xk-note">动作名取自 manifest.json 里真实存在的剪辑；全身画布只在主页有，别的页只出字幕，不假装在演。</p>');
    h.push('<p class="xk-note">换情绪/动作只改表演；台词只播真实录音，取不到就只出字幕。</p>');
    h.push('<button type="button" class="xk-close" id="xkIdClose" aria-label="关闭面板">✕</button>');
    panel.innerHTML = h.join('');
    panel.addEventListener('click', function (ev) {
      var t = ev.target;
      if (!t || !t.getAttribute) { return; }
      if (t.id === 'xkIdClose') { closePanel(); return; }
      var emo = t.getAttribute('data-emo');
      if (emo) { setEmo(emo); speak(EMO_LINE[emo] || 'nav_home', '情绪：' + labelOf(emo)); return; }
      var act = t.getAttribute('data-act');
      if (act) {
        var can = (typeof window.xkmPlayClip === 'function');
        if (can) { try { window.xkmPlayClip(act, null); window.XK_ACT = null; } catch (e) { D.errors.push('act: ' + e); } }
        say('动作：' + labelOfAct(act) + (can ? '' : '（全身画布只在主页可见，这一页只出字幕）'));
      }
    });
  })();
  function openPanel() { panel.classList.add('open'); D.panel = true; cap.classList.remove('on'); markPanel(); }
  function closePanel() { panel.classList.remove('open'); D.panel = false; }

  /* ---------- 点头像：切下一个情绪 + 念一句；长按 >=500ms：开面板 ---------- */
  var pressTimer = 0, longDone = false, taps = [];
  function tapCount() {
    var t = Date.now();
    taps.push(t);
    taps = taps.filter(function (x) { return t - x <= 1500; });
    if (taps.length >= 5) { taps = []; revealLogin('avatar-5tap'); say('自用入口已打开：登录按钮在头像右边。'); }
  }
  function nextEmo() {
    var i = 0, k;
    for (k = 0; k < EMOS8.length; k++) { if (EMOS8[k][0] === D.emo) { i = k; } }
    var e = EMOS8[(i + 1) % EMOS8.length];
    setEmo(e[0]);
    speak(EMO_LINE[e[0]] || 'nav_home', '情绪：' + e[1]);
  }
  av.addEventListener('pointerdown', function () {
    longDone = false;
    clearTimeout(pressTimer);
    pressTimer = setTimeout(function () { longDone = true; openPanel(); }, 500);
  });
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(function (ev) {
    av.addEventListener(ev, function () { clearTimeout(pressTimer); });
  });
  av.addEventListener('click', function () {
    if (longDone) { longDone = false; return; }     /* 长按已经开过面板 ⇒ 这一次不算"切情绪" */
    tapCount();
    nextEmo();
  });
  av.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); tapCount(); nextEmo(); }
  });
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && D.panel) { closePanel(); } });

  /* ---------- 进入栏目 ⇒ 固定一句介绍（同栏目 10 分钟内不重复念） ---------- */
  var ENTRY_LINE = { home: 'nav_home', monitor: 'nav_monitor', notes: 'nav_notes', ai: 'nav_ai' };
  (function entry() {
    var p = location.pathname, name = '';
    if (/^\/ai\b/.test(p)) { name = 'ai'; }
    else if (/^\/alerts\b/.test(p)) { name = 'monitor'; }
    else if (/^\/posts\b/.test(p)) { name = 'notes'; }
    else if (p === '/' || /^\/index\.html$/.test(p)) { name = 'home'; }
    var id = ENTRY_LINE[name];
    if (!id) { return; }                       /* /test/ 等页没有固定介绍句 ⇒ 什么都不播 ✓ */
    var KEY = 'xk-nav-voice-at', last = 0, lastSec = '';
    try { var raw = sg(KEY); if (raw) { var o = JSON.parse(raw); last = o.at || 0; lastSec = o.section || ''; } } catch (e) { }
    if (lastSec === name && (Date.now() - last) < 10 * 60 * 1000) { return; }
    ss(KEY, JSON.stringify({ section: name, at: Date.now() }));
    var tries = 0;
    (function wait() {
      var hasVoice = (window.KurisuPlayer && typeof window.KurisuPlayer.speakGroup === 'function') || typeof window.xkvPlay === 'function';
      if (!hasVoice && ++tries < 40) { setTimeout(wait, 100); return; }
      speak(id, '', true);                     /* 入口句是"固定一句"：即使声音关着也先把字幕显示出来（force） */
    })();
  })();

  /* ---------- 统一播放器：按需加载（P1 ⑥） ----------
     站主口径：宿主页要加载 `/js/kurisu-player.js`（选句/防复读/包络/口型一处实现）。
     实测：这个 138KB 的脚本**放进首屏 1.5s 窗口会顶爆首屏门禁**（/ai/ 1639KB → 1786KB > 1650KB 预算，
     且站主明确"预算不许抬"）⇒ 改成**按需注入**：1800ms 之后（越过窗口）或"点开声音"这个用户手势那一刻。
     它在本页找不到 [data-xk-kurisu] 节点（本页不挂站点舞台）⇒ 只提供 KurisuPlayer.speakGroup，不碰 DOM。 */
  function loadPlayer() {
    if (window.KurisuPlayer || D.playerAsked) { return; }
    D.playerAsked = true;
    D.playerAt = Math.round(performance.now());
    try {
      var s = document.createElement('script');
      s.src = '/js/kurisu-player.js';
      s.defer = true;
      document.head.appendChild(s);
    } catch (e) { D.errors.push('loadPlayer: ' + e); }
  }
  D.loadPlayer = loadPlayer;
  setTimeout(loadPlayer, 1800);

  /* ---------- P0-④：首屏优先 + 其余空闲预取 ----------
     站主原话："一打开网页，首先把整体的图片加载出来，按时间顺序，要展示的先显示；
     但是显示的同时把其他地方加载一下，这样不就快多了吗"。
     口径：
       · 首屏四个关键图各自由主页脚本按"出现顺序"decode() 完再生效（壁纸→背板→她首帧→字幕框）；
         壁纸另外在 <head> 里 preload + fetchpriority=high（只这一张抢带宽）。
       · 其余（角色清单 manifest.json / 视频清单 video-manifest.json / 语音 bank.json / 面板数据）
         一律**空闲预取**：最早 2000ms 之后才开始，且只登记 <link rel=prefetch>，绝不阻塞首屏
         （首屏门禁的口径是"导航后 1.5s 内请求到的资产" ⇒ 预取必须晚于这个窗口）。
       · 移动端 / saveData / deviceMemory<=4 ⇒ **只取首屏 + 当前栏目**，其余点了才取（省流量）。
       · 登录后才该加载的东西一律走 __xkAdmin.fetch（未登录直接拒，**不发请求**）。
     验收：首屏关键资源加载顺序表 + 首屏可交互时间 + 预取请求清单 = _shots/firstscreen-order.json */
  D.pref = {}; D.prefetch = [];
  D.prefetchOff = (function () {
    try { var c = navigator.connection; if (c && (c.saveData || /(^|-)2g$/.test(c.effectiveType || ''))) { return 'saveData/2g'; } } catch (e) { }
    try { if (navigator.deviceMemory && navigator.deviceMemory <= 4) { return 'deviceMemory<=4'; } } catch (e) { }
    try { if (matchMedia('(max-width:980px)').matches) { return 'narrow'; } } catch (e) { }
    return '';
  })();
  function idle(fn, ms) {
    if (typeof window.requestIdleCallback === 'function') { window.requestIdleCallback(fn, { timeout: ms }); }
    else { setTimeout(fn, ms); }
  }
  function prefetch(u) {
    if (D.pref[u]) { return; }
    D.pref[u] = 1; D.prefetch.push({ url: u, at: Math.round(performance.now()) });
    try {
      var l = document.createElement('link');
      l.rel = 'prefetch'; l.href = u; l.as = 'fetch'; l.crossOrigin = 'anonymous';
      document.head.appendChild(l);
    } catch (e) { D.errors.push('prefetch: ' + e); }
  }
  /* 登录后才有权限的东西：统一从这里走，未登录**不发请求**（站主追加②最后一条） */
  window.__xkAdmin = {
    allowed: function () { return !!(D.admin || D.loggedIn); },
    fetch: function (u, o) {
      if (!this.allowed()) { return Promise.reject(new Error('ADMIN_ONLY')); }
      return fetch(u, o);
    }
  };
  setTimeout(function () {
    if (D.prefetchOff) { D.prefetchNote = '跳过空闲预取（' + D.prefetchOff + '：只取首屏 + 当前栏目）'; return; }
    idle(function () {
      ['/kurisu/manifest.json', '/kurisu/video-manifest.json', '/kurisu/voice/bank.json'].forEach(prefetch);
    }, 1500);
  }, 2000);
  /* 清单到位后用**真值**覆盖头像帧数（只读；清单本来就在上面的空闲预取清单里 ⇒ 走缓存，不额外发请求） */
  setTimeout(function () {
    fetch('/kurisu/manifest.json', { cache: 'force-cache' }).then(function (r) { return r.json(); }).then(function (j) {
      var em = (j && j.emotions) || {};
      EMOS8.forEach(function (e) {
        var f = em[e[0]] && em[e[0]].idle && em[e[0]].idle.frames;
        if (f) { framesOf[e[0]] = f; }
      });
      paint();
    }).catch(function () { });
  }, 3200);

  /* 首访/回访的问候由主页内联播放器负责（greet_first / greet_back，固定不随机）——
     这里只把"入口句"这一步记进诊断，便于验收核对。 */
  D.entry = { path: location.pathname, at: Date.now() };
})();
</script>
'''
_n_brace_o = IDCARD_PARTIAL.count('{{')
_n_brace_c = IDCARD_PARTIAL.count('-}}')
if _n_brace_o != 1 or _n_brace_c != 1:
    raise SystemExit('batchA: idcard partial 里 {{ / -}} 不止注释那一处（%d / %d）—— JS/CSS 里混进了模板定界符'
                     % (_n_brace_o, _n_brace_c))

# --------------------------------------------------------------------- 落盘
print('生成：')
home_style = home_style + LAYOUT_PATCH

# 1) 共享头
write(os.path.join(PART, 'head-meta.html'), HEAD_META)

# 1b) ★批次 A-①：左上角头像卡（五页共用一份；自带 <style> + <script>）
write(os.path.join(PART, 'idcard.html'), IDCARD_PARTIAL)

# 2) 主页（整份）
write(os.path.join(ROOT, 'layouts', 'index.html'), u'''{{- /* ============================================================================
   生产主页 = `docs/demo-主页.html` **整份**（站主 2026-10-14 第四批口径）。
   ----------------------------------------------------------------------------
   搬过来的：它自己的 <style>（逐字）、<body> 全部标记（逐字）、那一段内联 <script>
   （4 剪辑逐帧 canvas / 开场播完硬切 idle / showHud 打字 / 原版落位公式，逐字）。
   只改三处：
     ① 素材 src → 我们 static/ 下的真文件（映射表见 _dev/gen-demo-pages.py）
     ② demo 的顶部胶囊 `.navpill` → 内容页外壳那一份**左侧竖排 dock**：标记逐字照
        `layouts/partials/xk-demo/shell-chrome.html` 的 <nav class="dock">，样式值逐字照
        `layouts/partials/xk-demo/shell-style.html` 的 `.dock` / `.dock .brand` / `.dock a`（+ 980px 那条）。
        项目顺序 XK-LAB ｜ 主页 · 监测中心 · AI 问答 · 笔记 · 靶场 · 关于；主页高亮"主页"。
     ③ 链接是站点真路由（/ · /alerts/ · /posts/ · /ai/）—— ★T27：/labs/ 与 /about/ 已删
        （不是 demo 的 `<button data-v>`，也不走 `/#/…` hash：这一页不挂站点 SPA 的 app.js）
   不搬的：站点 SPA 外层（app.js / 侧栏 / 顶行 / 输入条 / 页脚 / 搜索层）、kurisu-player.js、
   状态机/语音/口型 —— 站主明确要求这些**不要**进这一页。
   保留的不可见契约：Hugo <head>（标题/描述/canonical/OG/favicon）+ <main id="content"
   data-xk-ssr="home">（SPA 契约断言读它）+ #xk-views 占位。
   重现方式：python _dev/gen-demo-pages.py
   ============================================================================ */ -}}
<!DOCTYPE html>
<html lang="{{ site.Language.Lang | default `zh-CN` }}" data-xk-kurisu-mode="video" data-xk-boot="0">
<head>
{{ partial "xk-demo/head-meta.html" . }}
  {{- /* ★P0-④：首屏第一张（壁纸）preload + high —— 只这一张抢带宽，其余按顺序 decode */}}
  <link rel="preload" as="image" href="/images/crt/desk.webp" fetchpriority="high">
<style>%s
</style>
</head>
<body class="xk-has-idcard">
{{- /* ↓↓↓ 以下到 </main> 为止 = docs/demo-主页.html 的 body 逐字（仅素材路径与导航 href 如上） */}}
<main id="content" data-xk-ssr="home">
%s
</main>
<div id="xk-views" hidden aria-hidden="true"></div>
{{ partial "xk-demo/idcard.html" . }}
  {{- /* ★批次A-P1（站主 2026-10-16）：宿主页**按需加载**统一播放器 `/js/kurisu-player.js`
         （选句/防复读/包络/口型一处实现）。为什么不写死 <script src>：
         实测把 138KB 的播放器放进首屏窗口会顶爆首屏门禁（/ai/ 1639KB → 1786KB，预算 1650KB 不许抬 ✗）
         ⇒ 由头像卡在 **1800ms 之后**（或"点开声音"这个用户手势那一刻）注入，
         正好符合站主追加②"首屏优先、其余空闲预取"。 */}}
<script>
%s
</script>
{{ partial "xk-demo/api-bind.html" . }}
</body>
</html>
''' % (home_style, home_body, home_script))

shell_style = shell_style + LAYOUT_PATCH

# 3) 外壳共享片段
write(os.path.join(PART, 'shell-style.html'),
      u'{{- /* docs/demo-内容页外壳.html 的 <style> 逐字（第 7–398 行）+ 一条 <a> 伴随规则 */ -}}\n'
      u'<style>%s%s</style>\n' % (shell_style, DOCK_A_CSS))
write(os.path.join(PART, 'shell-chrome.html'),
      u'{{- /* 外壳常驻件（逐字）：底图两层 / demo 标识条 / 左侧 .dock / HOLO 面板 / 背景选择器。\n'
      u'      唯一改动：.dock 的 <button data-v> → <a href="站点真路由">（样式值逐字，见 shell-style）。\n'
      u'      ★T27（2026-10-15 站主）：/labs/ 与 /about/ 两页已删 ⇒ dock 六项 → 四项（主页 / 监测中心 / AI 问答 / 笔记）。 */ -}}\n'
      u'{{- $v := .v -}}\n%s\n' % chrome)
write(os.path.join(PART, 'shell-views.html'),
      u'{{- /* 四屏 <section class="view"> 逐字（★T27：靶场/关于两屏已删）；只有哪一屏带 .on 由参数 v 决定 */ -}}\n'
      u'{{- $v := .v -}}\n%s' % views_out)
_script_header = (u'{{- /* 外壳的两段内联 <script> 逐字（切 view / 作战室 / 聊天 / 靶场演示 / 雪碧条播放器 / CRT 场景）。\n'
                  u'      改动只有两类：① 素材路径 ② 站主第四批口径③允许的"行为级懒加载"（只改加载时机）。\n'
                  u'      ↓ 懒加载的逐条说明（Hugo 注释，不进产物；**别把它写成 JS 注释留在 <script> 外面** ——\n'
                  u'        那样会被当正文渲染出来，本轮踩过：像素差从 0.44% 弹到 3.59%）：'
                  + LAZY_NOTE.replace(u'*/', u'* /') + u' */ -}}\n')
write(os.path.join(PART, 'shell-script.html'),
      _script_header + shell_scripts[0] + u'\n' + shell_scripts[1] + u'\n')

# 4) 五个内容页 layout
PAGES = [
    ('alerts', 'monitor', '监测中心'),
    ('posts', 'notes', '笔记'),
    ('ai', 'ai', 'AI 问答'),
]
# ★T27：about 页已删 ⇒ 不再需要单落一份 single.html（原 about/single.html 由删除补丁一并清掉）。
ALSO_SINGLE = set()
for section, view, cname in PAGES:
    body_class = u' class="xk-has-idcard{{ if eq $v "ai" }} is-ai{{ end }}"'
    tpl = u'''{{- /* ============================================================================
   /%s/ = `docs/demo-内容页外壳.html` 的 `v-%s`（%s）那一屏**整份搬**（第四批口径）。
   ----------------------------------------------------------------------------
   搬过来的：外壳的 <style> 逐字、常驻件（底图/dock/HOLO/背景选择器）逐字、
   四屏标记逐字（★T27：靶场/关于两屏已删）、两段内联 <script> 逐字；本页初始 .on 落在 v-%s。
   只改两处：① 素材路径 → static/ 真文件 ② dock 的 <button data-v> → <a href="真路由">
   不动：站点的 SPA 外层 / kurisu-player / 状态机 / 语音 / 口型。
   保留的不可见契约：Hugo <head> + <main id="content" data-xk-ssr="%s"> + #xk-views 占位。
   重现方式：python _dev/gen-demo-pages.py
   ============================================================================ */ -}}
{{- $v := "%s" -}}
<!DOCTYPE html>
<html lang="{{ site.Language.Lang | default `zh-CN` }}" data-xk-kurisu-mode="video">
<head>
{{ partial "xk-demo/head-meta.html" . }}
{{ partial "xk-demo/shell-style.html" . }}
</head>
<body data-skin="warm" data-phone="v1"%s>
{{ partial "xk-demo/shell-chrome.html" (dict "v" $v) }}
<main class="main" id="content" data-xk-ssr="%s">
{{ partial "xk-demo/shell-views.html" (dict "v" $v "page" .) }}
</main>
<div id="xk-views" hidden aria-hidden="true"></div>
{{ partial "xk-demo/idcard.html" . }}
  {{- /* ★批次A-P1：统一播放器按需加载（同主页那条理由：138KB 放进首屏会顶爆 /ai/ 的门禁） */}}
{{ partial "xk-demo/shell-script.html" . }}
{{ partial "xk-demo/api-bind.html" . }}
</body>
</html>
''' % (section, view, cname, view, view, view, body_class, view)
    write(os.path.join(ROOT, 'layouts', section, 'list.html'), tpl)
    if section in ALSO_SINGLE:
        write(os.path.join(ROOT, 'layouts', section, 'single.html'), tpl)

print('\n完成。')
