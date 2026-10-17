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
    /* ★批次 D（2026-10-16 站主：“导航栏放到头上面好”）：≤980px 导航改到头部
       （头像卡下方一行）；桌面（>980px）左侧竖排一字不动。配色/字体零改动。 */
    .dock{left:0;right:0;top:86px;bottom:auto;transform:none;flex-direction:row;max-width:none;
      overflow-x:auto;border-radius:0 0 14px 0}
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
    /* ★2026-10-16 站主新口径：主页问候换成"欢迎使用 Amadeus 系统"那两句
       （`greet_welcome` 首访 / `greet_welcome_back` 回访）。**旧的两句保留在库里作兜底**：
       新句子若在 bank 里取不到（例如合并索引未更新），仍用旧的 ⇒ 保证"一定有声音，
       且字幕与音频是同一句"（绝不让新字幕配旧音频）。 */
    const wantNew = seen ? 'greet_welcome_back' : 'greet_welcome';
    const legacy  = seen ? 'greet_back' : 'greet_first';
    const id = xkvLine(wantNew) ? wantNew : legacy;
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
T31_JS = '\n/* ================= ★T31 开场六阶段（站主 2026-10-15 逐帧规格） =================\n   phase 0 壁纸        ：veil 撤下；CRT 仍是黑屏、导航栏隐藏（全部由 CSS/标记保证，无 JS 也成立）\n   phase 1 预载        ：首帧之后才插入 glow/backplate/plate 等图；CRT 底噪 = 加载信号\n   phase 2 黑屏闪烁    ：2~4 次，间隔 80~140ms 随机（亮度/扫描线抖动，不是正弦）\n   phase 3 大脸闪断    ：**等 opening 图真的就绪**才开始；2~3 次 60~100ms 硬切 + 1~3px 位移\n   phase 4 稳定+导航   ：**由"闪烁结束"这一事件触发**（不是猜时间的 setTimeout）\n   phase 5 正式动画    ：opening 继续播 → L1 既有推拉 → idle（推拉起点对齐到闪烁结束）\n   跳过：任意 pointerdown/keydown/wheel/touchstart ⇒ 撤闪烁层 + 导航栏立刻出现 + 直接进推拉\n   RM  ：直接最终稳定态（壁纸 + 稳定画面 + 导航栏），②③④ 的闪烁一律不做\n   验收钩子：window.__xkBoot.{phase,marks,log} ｜ #dock[data-xk-dock-in|data-xk-dock-at] */\nconst XK_BOOT = { phase: 0, t0: performance.now(), rm: RM, marks: {}, log: [], timers: [],\n                  skipped: false, revealed: false };\nwindow.__xkBoot = XK_BOOT;\nconst XK_BOOT_ON = !RM;   /* 新开场生效 ⇒ 关掉旧的"通电四拍"，两种闪烁不叠加 */\nfunction xkBootSet(p, why){\n  if(p <= XK_BOOT.phase) return;\n  XK_BOOT.phase = p;\n  XK_BOOT.marks[p] = Math.round(performance.now() - XK_BOOT.t0);\n  document.documentElement.setAttribute(\'data-xk-boot\', String(p));\n  if(why) XK_BOOT.log.push(p + \':\' + why);\n}\nfunction xkBootTimer(ms, fn){\n  const id = setTimeout(function(){ if(!XK_BOOT.skipped) fn(); }, ms);\n  XK_BOOT.timers.push(id);\n  return id;\n}\nfunction xkBootRnd(a, b){ return a + Math.random() * (b - a); }\nfunction xkBootBlink(hide){\n  const boot = document.getElementById(\'crtBoot\');\n  if(boot) boot.style.display = hide ? \'none\' : \'block\';\n}\nfunction xkBootPreload(){\n  /* ①→② 之间才请回来（首屏只算壁纸那一张）——元素位置/类名与原来逐字一致，只改"什么时候插入" */\n  const stage = document.getElementById(\'stage\'), clip = document.getElementById(\'crtClip\');\n  const canvas = document.getElementById(\'charCanvas\');\n  function mk(cls, src, parent, before){\n    const el = document.createElement(\'img\');\n    el.className = cls; el.alt = \'\'; el.setAttribute(\'aria-hidden\', \'true\'); el.src = src;\n    if(parent) parent.insertBefore(el, before || null);\n    return el;\n  }\n  try{\n    if(stage) mk(\'glow\', \'/kurisu/scene/amadeus_ambient_high_blend.webp\', stage, null);\n    if(clip) mk(\'backplate\', \'/images/crt/lab.webp\', clip, canvas || clip.firstChild);\n    if(clip) mk(\'plate\', \'/kurisu/scene/subtitle_frame_big.webp\', clip, clip.querySelector(\'.scan\'));\n  }catch(e){ XK_BOOT.log.push(\'preload:\' + e.message); }\n}\nfunction xkBootBlackFlicker(){\n  const boot = document.getElementById(\'crtBoot\');\n  const n = 6 + Math.floor(Math.random() * 4);          /* ★站主 10-17：6~9 次（原 2~4 次太短，看不清）*/\n  (function step(i){\n    if(i >= n){ xkBootWaitFace(); return; }\n    const black = i % 2 === 0;\n    if(boot){\n      boot.classList.toggle(\'noise\', black);\n      boot.style.background = black ? \'#000\' : \'#0A0E12\';   /* 亮度跳一下（不规律，不是正弦）*/\n    }\n    xkBootTimer(xkBootRnd(110, 190), function(){ step(i + 1); });\n  })(0);\n}\nfunction xkBootWaitFace(){\n  /* ③ → ④：\n     必须先有"大脸"那一帧可画，闪断才有东西可露 ⇒ 等图真的就绪（不靠猜时间 ✗）；\n     断网/慢网：停在壁纸 + 保留加载信号，并给人读的说明（导航栏照样给，别把人关在黑屏里）。 */\n  const t0 = performance.now();\n  (function wait(){\n    const im = cache[CLIPS.opening.src] || cache[CLIPS.opening.bootSrc];\n    const ready = !!(im && im.complete && im.naturalWidth);\n    if(!ready && (performance.now() - t0) < 3000){ xkBootTimer(60, wait); return; }\n    if(!ready){\n      const st = document.getElementById(\'crtStatus\');\n      if(st){ st.hidden = false; st.innerHTML = \'SEC-LAB · <span class="ok">● 画面读不到</span><br>网络或素材未到位 · 导航仍可用\'; }\n      xkBootReveal(\'no-face\');\n      return;\n    }\n    xkBootFaceFlicker();\n  })();\n}\nfunction xkBootFaceFlicker(){\n  xkBootSet(3, \'face\');\n  const clip = document.getElementById(\'crtClip\');\n  const n = 3 + Math.floor(Math.random() * 3);          /* ★站主 10-17：3~5 次闪断 */\n  (function step(i){\n    if(i >= n){ xkBootBlink(false); xkBootTimer(700, function(){ xkBootReveal(\'flicker-end\'); }); return; }   /* ★定格大脸 700ms 后揭幕；导航栏仍由揭示事件触发 */\n    xkBootBlink(i % 2 === 0);                           /* 硬切，不是淡入 ✗ */\n    if(clip) clip.style.transform = \'translateX(\' + (Math.random() * 6 - 3).toFixed(1) + \'px)\';\n    xkBootTimer(xkBootRnd(80, 120), function(){ step(i + 1); });\n  })(0);\n}\nfunction xkBootReveal(why){\n  if(XK_BOOT.revealed) return;\n  XK_BOOT.revealed = true;\n  const boot = document.getElementById(\'crtBoot\');\n  const clip = document.getElementById(\'crtClip\');\n  if(clip) clip.style.transform = \'\';\n  if(boot && !RM){                                       /* 过冲白光 → 稳定 */\n    boot.classList.remove(\'noise\');\n    boot.style.background = \'\';\n    boot.classList.add(\'flash\'); boot.style.display = \'block\';\n    xkBootTimer(120, function(){\n      boot.style.display = \'none\'; boot.classList.remove(\'flash\');\n    });\n  } else { xkBootBlink(true); }\n  xkDockIn(why);                                          /* ★同一帧：导航栏出现 */\n  xkBootSet(4, \'stable\');\n  xkBootSet(5, \'play\');\n}\nfunction xkBootStart(){\n  if(RM){ xkBootBlink(true); xkBootSet(4, \'rm\'); xkBootSet(5, \'rm\'); xkDockIn(\'rm\'); return; }\n  xkBootTimer(260, function(){ xkBootPreload(); xkBootSet(1, \'preload\'); xkBootSet(2, \'black\'); xkBootBlackFlicker(); });\n}\nfunction xkBootSkip(){\n  if(!started || XK_BOOT.revealed) return;\n  XK_BOOT.skipped = true;\n  XK_BOOT.timers.forEach(function(id){ clearTimeout(id); });\n  xkBootReveal(\'skip\');\n  xkTransStart();                       /* 跳过 = 直接进正式动画（推拉起点与"闪烁结束"同一语义）*/\n}\nconst XK_T31_EV = [\'pointerdown\', \'keydown\', \'wheel\', \'touchstart\'];\nfunction xkT31Off(){ XK_T31_EV.forEach(function(ev){ removeEventListener(ev, xkBootSkip); }); }\nXK_T31_EV.forEach(function(ev){ addEventListener(ev, function(){ xkT31Off(); xkBootSkip(); }, {passive:true}); });\nlet dockShown = false;\nfunction xkDockIn(why){\n  if(dockShown) return;\n  const d = document.getElementById(\'dock\');\n  if(!d) return;\n  dockShown = true;\n  d.classList.add(\'dock--in\');\n  d.setAttribute(\'data-xk-dock-in\', why || \'auto\');\n  d.setAttribute(\'data-xk-dock-at\', String(Math.round(performance.now() - XK_BOOT.t0)));\n}\nfunction xkTransStart(t){\n  /* ★T31：把"opening 播完 → 等 idle 图就绪 → 起推拉"抽成一处，供"自然播完"与"跳过"共用。\n     自然路径传 rAF 的 t，TRANS 取值与抽之前逐字等价（行为零变化）。 */\n  if(cur !== \'opening\' || TRANS) return;\n  fi = CLIPS.opening.frames - 1;\n  const idleIm = xkClipIm(\'idle\').im;\n  const btIdle = img(CLIPS.idle.bootSrc);\n  if(btIdle && !(btIdle.complete && btIdle.naturalWidth)) btIdle.addEventListener(\'load\', ()=>{ if(cur === \'opening\' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = performance.now(); } }, {once:true});\n  if(idleIm.complete && idleIm.naturalWidth){ TRANS = (t === undefined ? performance.now() : t); }\n  else {\n    idleIm.addEventListener(\'load\', ()=>{ if(cur === \'opening\' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = performance.now(); } }, {once:true});\n    idleIm.addEventListener(\'error\', ()=>{ if(cur === \'opening\' && !TRANS) TRANS = performance.now(); }, {once:true});\n  }\n}\n'
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
    '  /* ★批次 D（2026-10-16 站主：“导航栏放到头上面好”）：≤980px 时导航从**底部改到头部**。\n'
    '     为什么是“头像卡下方”而不是同一行：左上角头像卡（站主点名）已占 90×90，\n'
    '     同一行要放下 5 项×44px 必然溢出；排在它下面一行可以全宽横滑、不挡她的脸。桌面（>980px）左侧竖排一字不动。 */\n'
    '  @media (max-width:980px){\n'
    '    .dock{left:0;right:0;top:86px;bottom:auto;transform:none;flex-direction:row;\n'
    '      max-width:none;overflow-x:auto;border-left:1px solid var(--line2);border-radius:0 0 14px 0;padding:4px 6px}\n'
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
    # ②b ★V3（2026-10-17）：垫板 subtitle_frame_big.webp = 373.4KB，是首屏第二大块（仅次于 HTML 本身）。
    #    改成 data-src + 1×1 透明占位：正常网络由 /js/xk-saver.js 立刻补回 src（请求时机几乎不变），
    #    省流模式则根本不取（只保留底图 + 一行提示）。断言 pattern 变了就报错，防止补丁静默失效。
    ('<img loading="lazy" class="plate" src="demo-assets/subtitle_frame_big.webp"',
     '<img loading="lazy" class="plate" data-src="demo-assets/subtitle_frame_big.webp" '
     'src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"',
     'views'),
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
     "  if(!document.body.classList.contains('is-home')) setPhone();",
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

# ②b ★V3（2026-10-17）：**主页**的垫板（373.4KB）同样改成 data-src + 1×1 透明占位 —— 省流模式不取；
#    正常网络由 /js/xk-saver.js 在 head 段补回真 src（非省流时请求时机与之前一致）。
_PLATE_FROM = '<img class="plate" src="/kurisu/scene/subtitle_frame_big.webp"'
_PLATE_TO = ('<img class="plate" data-src="/kurisu/scene/subtitle_frame_big.webp" '
             'src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"')
if home_body.count(_PLATE_FROM) != 1:
    raise SystemExit('主页垫板补丁对不上（出现 %d 次）：%s' % (home_body.count(_PLATE_FROM), _PLATE_FROM[:60]))
home_body = home_body.replace(_PLATE_FROM, _PLATE_TO)

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
  el.className = 'tl lv-' + (it.cls || 'dns');   /* ★R2：行左 2px 级别色条（颜色映射在 CSS 里，复用既有类型色的变量，不新增色值） */
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
'''

S_SPARK_NEW = u'''/* 24 小时攻击时序 —— ★第十二批重写：数据改成 /api/public/alerts 的 stats24h.trend
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
'''

S_ATTK_NEW = u'''/* 告警类型矩阵 —— ★第十二批重写（原来是写死的 TACTIC_HITS 样例值）。
   服务端没有 ATT&CK 战术字段，所以这里一格 = 服务端真实给的一个类型标签 + /alerts 的
   stats.byType 真实计数；映射关系由服务端给，前端不编。取不到就写"读不到"。
   ★R2（2026-10-16）：每格补 hover/聚焦摘要（占比 + 最近一条真实告警一句话，数据来自
   已在手的 XK_FEED，不发新请求）；格子可聚焦（tabindex）—— 摘要条 CSS 在 shell-style 的 R2 段。 */
const attkGrid = document.getElementById('attkGrid');
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
}
window.__xkRenderTypes = renderTypes;
'''

S_COUNTERS_NEW = u'''let counted = false;
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
  const _clean = xkEmoClean(_ans);          /* ★V5：先剥 [EMO:xxx] 再进 markdown，页面零标签 */
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

XK_TIER_JS = (
    "/* ================= ★P0-①（2026-10-16 站主 P0 修复半）：手机内存兜底 =================\n"
    "   根因方向（批次 B §10.3 用排除法定到的）：iPhone Safari 连 video/webm;codecs=vp9 都不认\n"
    "   ⇒ __xkVid 走 auto 降级进 pixel 档 ⇒ 画的是 /kurisu/full/*.hi.webp，\n"
    "   而单张 hi 解码 = 34~53MB（manifest 的 decodedBytes 实测值：opening 38.8MB / idle 35.5MB /\n"
    "   speaking·thinking 53.3MB）⇒ iOS 逐标签页内存上限把已解码位图丢掉 ⇒ 上屏就是**一整块灰**。\n"
    "   本模块只做四件事（每条都留证据，验收脚本读 window.__xkTier）：\n"
    "     ① 手机上**只到中档**：hi 一个请求都不发（noHi），走 medium 档 = /kurisu/full/*.boot.webp\n"
    "        —— **同瓦片**（321×432 / 380×290）、24 帧、解码 10.6~13.3MB ⇒ 画质不变、内存降 3~4 倍；\n"
    "     ② **位图被丢弃的检测**：抽检\"她应该在那里\"的画布区（非透明像素计数），连续 3 次全空 ⇒ 判定丢了；\n"
    "     ③ **重试一次**（丢掉缓存里的 Image 重新取图 = 重新解码）；仍为空 ⇒ 降档 hi→medium→poster，\n"
    "        写 degradeReason（宁可出静态帧，**不许静默留灰块** ✗）；\n"
    "     ④ 诊断：window.__xkTier = {mobile,lowMem,noHi,initTier,tier,degraded,degradeReason,retries,checks,\n"
    "        lastCheck,events,errors} ｜ 手机面板另记 bodyTier / bodyRetry。\n"
    "   证据旋钮（只在 URL 上生效，默认行为逐字不变 —— 写在这里是为了\"能本地确定性复现降档链\"）：\n"
    "     ?xk-tier=hi|medium|poster|auto  强制某一档（auto = 手机 medium / 桌面 hi）\n"
    "     ?xk-tier-fail=<role>[,<role>]   把某几个角色当\"位图已被丢弃\"（复现 检测→重试→降档→静态帧）\n"
    "     ?xk-tier-blank=1                抽检永远判空（同上，对全部角色）\n"
    "   纪律：不改配色/背景/字体；**桌面 auto = hi，逐字等于改前**；不改首屏字节（手机上只会更小：hi 不在请求里）。\n"
    "   ⚠ 这里的\"medium 档\"就是 full 系列的**中档 boot**（同瓦片、内存 1/4），不是 static/kurisu/medium/\n"
    "     （134×180 瓦片 —— 那是\"脸糊\"的另一件事，属 ④ 的分析页；本模块只要\"内存降下来、脸还在\"）。 */\n"
    "var XK_TIER = window.__xkTier || (function(){\n"
    "  function q(k){ var m = new RegExp('[?&]' + k + '=([^&#]*)').exec(location.search || ''); return m ? decodeURIComponent(m[1]) : ''; }\n"
    "  var ua = navigator.userAgent || '';\n"
    "  var narrow = false;\n"
    "  try { narrow = matchMedia('(max-width: 980px)').matches; } catch(e){}\n"
    "  var mobile = /iPhone|iPad|iPod|Android|Mobile/i.test(ua) || narrow;\n"
    "  var dm = (typeof navigator.deviceMemory === 'number') ? navigator.deviceMemory : 8;\n"
    "  var forced = q('xk-tier');\n"
    "  var T = { t0: performance.now(), mobile: mobile, lowMem: dm <= 4, narrow: narrow, dm: dm,\n"
    "            forced: forced || 'auto', noHi: false, initTier: 'hi', tier: {}, degraded: {}, degradeReason: {},\n"
    "            retries: {}, checks: 0, lastCheck: null, strike: 0, watchOn: false, phoneWatch: false,\n"
    "            body: null, bodyTier: {}, bodyRetry: {}, bodyRole: null,\n"
    "            fail: (q('xk-tier-fail') || '').split(',').filter(Boolean), blank: q('xk-tier-blank') === '1',\n"
    "            events: [], history: [], errors: [] };\n"
    "  T.noHi = (forced === 'medium' || forced === 'poster') ? true : (forced === 'hi' ? false : (mobile || T.lowMem));\n"
    "  T.initTier = (forced === 'poster') ? 'poster' : (T.noHi ? 'medium' : 'hi');\n"
    "  T.log = function(s){ try { var e = Math.round(performance.now() - T.t0) + 'ms ' + s; T.events.push(e); if(T.events.length > 30){ T.events.shift(); } T.history.push(e); if(T.history.length > 60){ T.history.shift(); } } catch(e){} };\n"
    "  T.log('init mobile=' + mobile + ' lowMem=' + T.lowMem + ' noHi=' + T.noHi + ' tier=' + T.initTier + ' forced=' + T.forced);\n"
    "  window.__xkTier = T;\n"
    "  return T;\n"
    "})();\n"
    "XK_TIER.posterUrl = function(name){ return '/kurisu/full/' + name + '.poster.webp'; };\n"
    "XK_TIER.role = function(name){ try { return (typeof CLIPS !== 'undefined' && CLIPS && CLIPS[name]) ? CLIPS[name] : null; } catch(e){ return null; } };\n"
    "XK_TIER.tierOf = function(name){ return XK_TIER.tier[name] || XK_TIER.initTier; };\n"
    "/* hi 只在\"没被限档、也没降过档\"时可用 —— 手机 noHi 与任何已降档的角色都在这里被挡住 */\n"
    "XK_TIER.hiAllowed = function(name){ return !XK_TIER.noHi && !XK_TIER.tier[name]; };\n"
    "XK_TIER.degrade = function(name, why){\n"
    "  var c = XK_TIER.role(name); if(!c) return false;\n"
    "  var cur = XK_TIER.tierOf(name);\n"
    "  var next = (cur === 'hi' && c.bootSrc) ? 'medium' : 'poster';\n"
    "  XK_TIER.tier[name] = next; XK_TIER.degraded[name] = next;\n"
    "  XK_TIER.degradeReason[name] = why + ' @' + cur + '→' + next;\n"
    "  XK_TIER.log('degrade ' + name + ' ' + XK_TIER.degradeReason[name]);\n"
    "  if(next === 'poster'){ c.bootSrc = null; c.src = XK_TIER.posterUrl(name); c.frames = 1; }\n"
    "  return next;\n"
    "};\n"
    "XK_TIER.retry = function(name){\n"
    "  var c = XK_TIER.role(name); if(!c) return false;\n"
    "  if(XK_TIER.retries[name]) return false;\n"
    "  var cur = XK_TIER.tierOf(name);\n"
    "  var url = (cur === 'hi') ? c.src : (cur === 'medium' ? c.bootSrc : c.src);\n"
    "  if(!url) return false;\n"
    "  XK_TIER.retries[name] = 1;\n"
    "  try { if(cache){ delete cache[url]; } } catch(e){}\n"
    "  try { img(url); } catch(e){ XK_TIER.errors.push('retry: ' + e); }\n"
    "  XK_TIER.log('retry ' + name + ' @' + cur + '（同一个 URL 重新取图 = 重新解码）');\n"
    "  return true;\n"
    "};\n"
    "/* 抽检\"她应该在那里\"的竖条：返回非透明像素计数（null = 读不到） */\n"
    "XK_TIER.sample = function(cv){\n"
    "  if(!cv || !cv.width || !cv.height) return null;\n"
    "  var ctx = null; try { ctx = cv.getContext('2d'); } catch(e){ return null; }\n"
    "  if(!ctx) return null;\n"
    "  var W = cv.width, H = cv.height;\n"
    "  var x0 = Math.floor(W * 0.20), x1 = Math.floor(W * 0.80);\n"
    "  var y0 = Math.floor(H * 0.15), y1 = Math.floor(H * 0.95);\n"
    "  var n = 0, nz = 0, rows = 24, step = Math.max(1, Math.floor((y1 - y0) / rows));\n"
    "  for(var y = y0; y < y1; y += step){\n"
    "    var d;\n"
    "    try { d = ctx.getImageData(x0, y, Math.max(2, x1 - x0), 1).data; }\n"
    "    catch(e){ XK_TIER.errors.push('getImageData: ' + e); return null; }\n"
    "    for(var i = 3; i < d.length; i += 4){ n++; if(d[i] > 8){ nz++; } }\n"
    "  }\n"
    "  XK_TIER.checks++;\n"
    "  XK_TIER.lastCheck = { w:W, h:H, samples:n, opaque:nz, at:Math.round(performance.now() - XK_TIER.t0) };\n"
    "  return nz;\n"
    "};\n"
    "XK_TIER.applyForce = function(){\n"
    "  try {\n"
    "    if(typeof CLIPS === 'undefined' || !CLIPS) return;\n"
    "    for(var k in CLIPS){ if(!Object.prototype.hasOwnProperty.call(CLIPS, k)) continue;\n"
    "      if(XK_TIER.forced === 'poster'){ XK_TIER.tier[k] = 'medium'; XK_TIER.degrade(k, 'URL 旋钮 ?xk-tier=poster'); }\n"
    "      else if(XK_TIER.noHi){ XK_TIER.tier[k] = 'medium'; }\n"
    "    }\n"
    "  } catch(e){ XK_TIER.errors.push('applyForce: ' + e); }\n"
    "};\n"
    "/* 主板画布（CRT）：cur = 当前 CLIPS 角色名 */\n"
    "XK_TIER.watchCRT = function(){\n"
    "  if(XK_TIER.watchOn) return false;\n"
    "  var cv = document.getElementById('charCanvas');\n"
    "  if(!cv || typeof CLIPS === 'undefined' || !CLIPS) return false;\n"
    "  XK_TIER.watchOn = true;\n"
    "  var fast = XK_TIER.blank || XK_TIER.fail.length > 0;\n"
    "  if(XK_TIER.noHi || XK_TIER.forced !== 'auto' || fast){ XK_TIER.applyForce(); }\n"
    "  var every = fast ? 500 : 1500, need = fast ? 1 : 3, gate = fast ? 1200 : 6000;\n"
    "  XK_TIER.log('watchCRT on every=' + every + ' need=' + need + ' gate=' + gate);\n"
    "  setInterval(function(){\n"
    "    if(performance.now() - XK_TIER.t0 < gate) return;\n"
    "    if(typeof XK_BOOT !== 'undefined' && XK_BOOT && XK_BOOT.phase < 4) return;\n"
    "    var name = null;\n"
    "    try { name = (typeof cur === 'string' && CLIPS[cur]) ? cur : null; } catch(e){}\n"
    "    if(!name) return;\n"
    "    var fastNow = XK_TIER.blank || XK_TIER.fail.indexOf(name) >= 0;\n"
    "    if(XK_TIER.tierOf(name) === 'poster') return;   /* 已到底档，不再折腾（含旋钮复现） */\n"
    "    var nz = XK_TIER.sample(cv);\n"
    "    if(nz === null) return;\n"
    "    if(fastNow) nz = 0;\n"
    "    if(nz > 0){ XK_TIER.strike = 0; return; }\n"
    "    XK_TIER.strike++;\n"
    "    if(XK_TIER.strike < need) return;\n"
    "    XK_TIER.strike = 0;\n"
    "    if(!XK_TIER.retries[name]){ XK_TIER.retry(name); return; }\n"
    "    XK_TIER.degrade(name, 'drawImage 后抽检 0 非透明像素（位图被系统丢弃）');\n"
    "  }, every);\n"
    "  return true;\n"
    "};\n"
    "/* 手机面板（外壳里的 phoneCanvas，用 full 全身剪辑） */\n"
    "XK_TIER.bindBody = function(B){\n"
    "  XK_TIER.body = B;\n"
    "  try {\n"
    "    for(var k in B){ if(!Object.prototype.hasOwnProperty.call(B, k)) continue;\n"
    "      var b = B[k];\n"
    "      if(XK_TIER.noHi && b && /\\.hi\\.webp$/.test(b.src)){\n"
    "        b.src = b.src.replace(/\\.hi\\.webp$/, '.boot.webp'); b.frames = 24; XK_TIER.bodyTier[k] = 'medium';\n"
    "      } else { XK_TIER.bodyTier[k] = XK_TIER.noHi ? 'medium' : 'hi'; }\n"
    "    }\n"
    "    XK_TIER.log('bindBody tier=' + JSON.stringify(XK_TIER.bodyTier));\n"
    "  } catch(e){ XK_TIER.errors.push('bindBody: ' + e); }\n"
    "};\n"
    "XK_TIER.bodyOf = function(role){ XK_TIER.bodyRole = role; return (XK_TIER.body && XK_TIER.body[role]) ? XK_TIER.body[role] : null; };\n"
    "XK_TIER.retryBody = function(role){\n"
    "  if(XK_TIER.bodyRetry[role]) return false;\n"
    "  var B = XK_TIER.body; if(!B || !B[role]) return false;\n"
    "  XK_TIER.bodyRetry[role] = 1;\n"
    "  var b = B[role]; b.src = b.src + (b.src.indexOf('?') < 0 ? '?' : '&') + 'xk_r=1';\n"
    "  XK_TIER.log('retryBody ' + role + ' @' + (XK_TIER.bodyTier[role] || 'hi'));\n"
    "  try { if(typeof render === 'function'){ render(); } } catch(e){}\n"
    "  return true;\n"
    "};\n"
    "XK_TIER.degradeBody = function(role, why){\n"
    "  var B = XK_TIER.body; if(!B || !B[role]) return false;\n"
    "  var cur = XK_TIER.bodyTier[role] || 'hi';\n"
    "  var next = (cur === 'hi') ? 'medium' : 'poster';\n"
    "  XK_TIER.bodyTier[role] = next; XK_TIER.degraded['phone:' + role] = next;\n"
    "  XK_TIER.degradeReason['phone:' + role] = why + ' @' + cur + '→' + next;\n"
    "  XK_TIER.log('degradeBody ' + role + ' → ' + next);\n"
    "  if(next === 'medium'){ var b = B[role]; b.src = b.src.replace(/\\.hi\\.webp$/, '.boot.webp'); b.frames = 24; }\n"
    "  else { B[role] = { src: '/kurisu/full/' + role + '.poster.webp', frames: 1, interval: 42 }; }\n"
    "  try { if(typeof render === 'function'){ render(); } } catch(e){}\n"
    "  return next;\n"
    "};\n"
    "XK_TIER.watchPhone = function(){\n"
    "  if(XK_TIER.phoneWatch) return false;\n"
    "  var cv = document.getElementById('phoneCanvas');\n"
    "  if(!cv || !XK_TIER.body) return false;\n"
    "  XK_TIER.phoneWatch = true;\n"
    "  var fast = XK_TIER.blank || XK_TIER.fail.length > 0;\n"
    "  var every = fast ? 500 : 1500, need = fast ? 1 : 3, gate = fast ? 1200 : 6000;\n"
    "  XK_TIER.log('watchPhone on every=' + every);\n"
    "  setInterval(function(){\n"
    "    if(performance.now() - XK_TIER.t0 < gate) return;\n"
    "    try { if(typeof __xkPhoneDefer !== 'undefined' && __xkPhoneDefer) return; } catch(e){}\n"
    "    var vAi = document.getElementById('v-ai');\n"
    "    if(document.body.classList.contains('is-home')) return;\n"
    "    var role = XK_TIER.bodyRole; if(!role) return;\n"
    "    var fastNow = XK_TIER.blank || XK_TIER.fail.indexOf(role) >= 0;\n"
    "    if(XK_TIER.bodyTier[role] === 'poster') return;   /* 已到底档，不再折腾 */\n"
    "    var nz = XK_TIER.sample(cv);\n"
    "    if(nz === null) return;\n"
    "    if(fastNow) nz = 0;\n"
    "    if(nz > 0){ XK_TIER.strike = 0; return; }\n"
    "    XK_TIER.strike++;\n"
    "    if(XK_TIER.strike < need) return;\n"
    "    XK_TIER.strike = 0;\n"
    "    if(!XK_TIER.bodyRetry[role] && XK_TIER.bodyTier[role] === 'medium'){ XK_TIER.retryBody(role); return; }\n"
    "    XK_TIER.degradeBody(role, '手机面板抽检 0 非透明像素（位图被系统丢弃）');\n"
    "  }, every);\n"
    "  return true;\n"
    "};\n"
    "setTimeout(function(){ try { XK_TIER.watchCRT(); XK_TIER.watchPhone(); } catch(e){ XK_TIER.errors.push('watch: ' + e); } }, 1200);\n")

XK_CLIPIM_JS = (
    "/* ★T5.6 boot→hi：hi 已就绪就用 hi；否则 boot 小图集（前 24 帧，网格/瓦片同规格）先播，\n"
    "   hi 由 play() 延迟触发（越过首屏窗口）；到位后按同一帧号无缝接力，画质不变。\n"
    "   警告：hi 只能 peek 缓存、不能 img() 创建 —— img() 创建即发请求，会把 hi 拉回首屏；\n"
    "   且必须先 peek hi 再兜底 boot —— 顺序反了会永远卡在 boot 档，开场永不落幕。\n"
    "   ★P0-①：hi 的 peek 现在过一道 XK_TIER.hiAllowed() —— 手机上（或已降档的角色）连 peek 都不做，\n"
    "   直接吃 boot 中档（34~53MB 的位图根本不会出现在内存里）。 */\n"
    "function xkClipIm(name){\n"
    "  const c = CLIPS[name];\n"
    "  if(XK_TIER.hiAllowed(name)){\n"
    "    const px = cache[c.src];\n"
    "    if(px && px.complete && px.naturalWidth) return {im:px, c:c};\n"
    "  }\n"
    "  if(!XK_TIER.hiAllowed(name) && !c.bootSrc){\n"
    "    XK_TIER.degrade(name, 'noHi 且该角色没有中档（boot）⇒ 直接静态帧');\n"
    "    return {im:img(c.src), c:c};\n"
    "  }\n"
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
             XK_TIER_JS + XK_CLIPIM_JS + "function play(name){\n",
             'T5.6 + P0①: XK_TIER + xkClipIm helper')
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
             "    /* ★P0-①：手机/已降档的角色**不上 hi 档**（hi 单张解码 34~53MB，iOS 会把它丢掉） */\n"
             "    const late = ()=>{ if(!XK_TIER.hiAllowed(name)) return; setTimeout(()=>{ img(c.src); }, 1700); };\n"
             "    if(bt.complete && bt.naturalWidth){ late(); }\n"
             "    else { bt.addEventListener('load', late, {once:true});\n"
             "           bt.addEventListener('error', function(){ if(!XK_TIER.hiAllowed(name)){ XK_TIER.degrade(name, 'boot 中档取图失败（error）'); } else { img(c.src); } }, {once:true}); }\n"
             "  } else { if(XK_TIER.hiAllowed(name)){ img(c.src); } else { XK_TIER.degrade(name, 'noHi 且该角色无中档 ⇒ 静态帧'); } }\n"
             "  drawFrame();",
             'T5.6: play() boot 优先预载 + hi 延迟')
    return s

s1 = xk_boot_patches(s1, False)
shell_scripts[1] = s1
home_script = xk_boot_patches(home_script, True)

# ---- ★P0-①（2026-10-16）：手机面板（外壳 phoneCanvas）也走同一套内存兜底 ----
#   手机面板用的是 full 全身剪辑（idle/speaking/thinking.hi.webp 单张解码 35.5/53.3MB）
#   ⇒ 手机上同样只到中档 boot（同瓦片 321×432、24 帧、13.3MB），并共用 XK_TIER 的
#      检测→重试一次→降档→degradeReason。落点：`const BODY` / `phoneBody.set(...)` 两处。
#   （XK_TIER_JS 在 T5.6 段定义，所以这段必须放在它后面。）
# ---- ★2026-10-17 V2（站主定）：手机面板优先 E-mote，失败回落 Sprite 三段 ----
#   门槛（收紧版，站主同意）：宽度 ≥1280px 且 deviceMemory≥8（未上报则放行）且 cores≥4 且非主页且未被关。
#   ⇒ 手机/平板/低配一律**不加载**（避免 wasm 512MB 预留把小内存设备打挂），也不需要站主手机做真机验证。
#   失败/被关/不支持（mount 返回 null 或 onStatus 报 error）⇒ 移除 xk-phone-emote 类，原 Sprite 逻辑照旧。
XK_EMOTE_BOOT_JS = (
    "\n/* ★V2 手机面板优先 E-mote（桌面大屏/够内存才加载；失败一行不改继续 Sprite 三段） */\n"
    "(function(){\n"
    "  /* 窄屏：手机面板退化为竖直静态立绘条，点一下放大/收起（不挂 E-mote，见下 w<1280 闸）*/\n"
    "  (function(){\n"
    "    var ph = document.querySelector('.phone');\n"
    "    if(!ph || !window.matchMedia || !matchMedia('(max-width:980px)').matches) return;\n"
    "    ph.style.cursor = 'pointer';\n"
    "    ph.setAttribute('role','button');\n"
    "    ph.addEventListener('click', function(e){\n"
    "      if(e.target && e.target.closest && e.target.closest('.phone-btns')) return;\n"
    "      document.documentElement.classList.toggle('xk-phone-open');\n"
    "    });\n"
    "    document.addEventListener('click', function(e){\n"
    "      if(!document.documentElement.classList.contains('xk-phone-open')) return;\n"
    "      if(ph.contains(e.target)) return;\n"
    "      document.documentElement.classList.remove('xk-phone-open');\n"
    "    }, true);\n"
    "  })();\n"
    "  var n = 0;\n"
    "  function go(){\n"
    "  var cv = document.getElementById('phoneCanvas');\n"
    "  /* ★时序：phone-emote.js 是 defer 脚本、可能比本段后到 ⇒ 最多等 10s（40×250ms）再挂 */\n"
    "  if(!cv || !window.XKPhoneEmote){ if(++n < 40) setTimeout(go, 250); return; }\n"
    "  try { if(document.body && document.body.classList.contains('is-home')) return; } catch(e){}\n"
    "  var w = window.innerWidth || 0, mem = navigator.deviceMemory || 0, cores = navigator.hardwareConcurrency || 0;\n"
    "  if(w < 1280) return;\n"
    "  if(mem && mem < 8) return;\n"
    "  if(cores && cores < 4) return;\n"
    "  if(window.__xkPhoneEmoteOff) return;\n"
    "  var em = window.XKPhoneEmote.mount(cv, { model: 'kurisu_c', mode: 'idle', crop: 0.52 });\n"
    "  if(!em) return;\n"
    "  document.documentElement.classList.add('xk-phone-emote');\n"
    "  window.__xkPhoneAnim = false;   /* ★V2.1：手机只放 E-mote，停掉原始帧动画 */\n"
    "  XK_TIER.phoneEmote = em; window.__xkPhoneEmoteInst = em;\n"
    "  em.onStatus(function(s){\n"
    "    if(!s) return;\n"
    "    /* ★ 加载中保留静态立绘垫底，只有 E-mote 真正 ready 才撤（否则加载期手机是空屏） */\n"
    "    if(s.state === 'ready'){ document.documentElement.classList.add('xk-emote-ready'); }\n"
    "    if(s.state === 'error' || s.state === 'off'){ document.documentElement.classList.remove('xk-phone-emote'); document.documentElement.classList.remove('xk-emote-ready'); XK_TIER.phoneEmote = null; }\n"
    "    var el = document.getElementById('phoneState');\n"
    "    if(el && s.state) el.textContent = String(s.state).toUpperCase();\n"
    "  });\n"
    "  /* 模式跟随：读手机面板状态文字（IDLE/THINKING/SPEAKING），变化时通知 E-mote（不改原 setPhone） */\n"
    "  var last = '';\n"
    "  setInterval(function(){\n"
    "    var el = document.getElementById('phoneState'); if(!el) return;\n"
    "    var t = String(el.textContent || '').toUpperCase();\n"
    "    if(t === last) return;\n"
    "    last = t;\n"
    "    var m = t.indexOf('SPEAK') >= 0 ? 'speaking' : (t.indexOf('THINK') >= 0 ? 'thinking' : 'idle');\n"
    "    try { em.setMode(m); } catch(e){}\n"
    "  }, 800);\n"
    "  }\n"
    "  go();\n"
    "})();\n")
sc = subn(sc,
          r"const BODY = \{.*?\n\};",
          lambda m: (XK_TIER_JS + m.group(0) +
                     "\nXK_TIER.bindBody(BODY);   /* ★P0-①：手机面板上限中档（boot），并挂降档链 */\n" + XK_EMOTE_BOOT_JS),
          1, 'P0①: 手机面板注入 XK_TIER + 绑档 + V2 E-mote 优先')
sc = sub1(sc,
          "  phoneBody.set(BODY[mode === 'speaking' ? 'speaking' : (emo === 'sided_thinking' ? 'thinking' : 'idle')]);",
          "  /* ★P0-①：按 XK_TIER 当前的档取图（手机上 = boot 中档；降档后 = 静态 poster） */\n"
          "  var _xkRole = (mode === 'speaking' ? 'speaking' : (emo === 'sided_thinking' ? 'thinking' : 'idle'));\n"
          "  XK_TIER.bodyOf(_xkRole);\n"
          "  phoneBody.set(XK_TIER.body[_xkRole] || BODY[_xkRole]);",
          'P0①: 手机面板按档取图')
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
'''

# =====================================================================================
# T8 第一批：状态机 + 宿主触发（2026-10-15 窗口 C）
# -------------------------------------------------------------------------------------
# 口径（站主 2026-10-15 已批）：
#   · 读 static/kurisu/statemachine.json（38 节点/92 边，root=idle）：出边概率**归一化后**掷骰子；
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
                 "function xkSmBoot(){ try{ XK_SM_JS.boot(); }catch(e){}\n"
                 "  /* ★2026-10-17 修时序竞态：接管原本只写在 showHud() 里，而 showHud 可能早于本模块加载\n"
                 "     （实测有时 __xkSM.cur 一直为 null、她永远是主页自己的 full/* 循环）⇒ 加兜底重试：\n"
                 "     开场落定（约 7s）后，只要状态机还没开始演，就每秒补调一次 takeOver()，最多 20 次。 */\n"
                 "  setTimeout(function(){\n"
                 "    var n = 0;\n"
                 "    var t = setInterval(function(){\n"
                 "      try {\n"
                 "        if(window.__xkSM && window.__xkSM.cur){ clearInterval(t); return; }\n"
                 "        if(window.XK_SM_JS && XK_SM_JS.takeOver) XK_SM_JS.takeOver();\n"
                 "        if(++n >= 20) clearInterval(t);\n"
                 "      } catch(e){ clearInterval(t); }\n"
                 "    }, 1000);\n"
                 "  }, 7000);\n"
                 "}\n"
                 "/* ★2026-10-17 站主定：**C 方案** —— 开场用立绘那套(full/*)，进站后由状态机演 38 条动作；\n"
                 "   但状态机的 idle/轮换只从 **≥268px** 的剪辑里挑（entryFor 里过滤），低清的 134/168 剪辑不参与轮换\n"
                 "   （情绪按钮仍可显式调用）。状态机在主页恢复启动。 */\n"
                 "if(!window.__xkSaver) setTimeout(xkSmBoot, 600);   /* ★V3：省流模式不起状态机（不取任何剪辑图集）*//* 与首屏门禁的 1.5s 窗口错开（懒加载，零首屏影响）*/\n"
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
T31_JS_ANCHOR_NEW = "const RM = matchMedia('(prefers-reduced-motion: reduce)').matches || !!window.__xkSaver;   /* ★V3：省流模式按 RM 走（不播开场、不取 opening/idle 图集）*/\n"
home_script = sub1(home_script, T31_JS_ANCHOR, T31_JS_ANCHOR_NEW + T31_JS, 'T31: 注入六阶段状态机 JS')
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
# ★P6（站主 2026-10-16 裁定"`/test/` 不要了"）：**从顶部导航摘掉「测试」项**（两处 dock 都摘）。
#   注意：**只摘导航，不删页面** —— `_dev/check-ssr-contract.py` 的五页清单仍把 `/test/` 当第 5 页，
#   连页面一起删要先改门禁与 dock 模板（等站主再说）。robots.txt 的 `Disallow: /test/` 由主窗口加。
#   恢复方式：把下面两行 `chrome/home_body = sub1(...)` 取消注释即可。
# chrome = sub1(chrome, DOCK_ANCHOR_CONTENT, DOCK_ANCHOR_CONTENT + '  ' + DOCK_TEST_CONTENT,
#               'batchA: 外壳 dock 新增「测试」项')
# home_body = sub1(home_body, DOCK_ANCHOR_HOME, DOCK_ANCHOR_HOME + '  ' + DOCK_TEST_HOME,
#                  'batchA: 主页 dock 新增「测试」项')
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
     触发后本会话一直显示（sessionStorage['xk-admin-ui']=1）；有自用令牌（localStorage['xk-user-token']）也一直显示。
   纪律：**绝不硬编码任何令牌** ✗ —— 令牌只由站主手动粘进本机 localStorage（键 `xk-user-token`），
        前端不读取它的内容做判断、不写进任何 .js/.html/模板/构建产物，只把它放进请求头 X-User-Token。
    ★批次 ②（2026-10-16）· 主页底部对话输入栏第 1 期（同一份偏件里租一处，理由：站主要求"与头像卡同层"）：
     · 标记只落在主页（body.is-home；SSR 默认 hidden），DOM 里**永远有一份**但未开隐蔽入口时不可见 ✗；
     · 显示条件 = `window.__xkAdmin.allowed()`（开过隐蔽入口 或 有令牌）；**未登录一个请求都不发** ✗；
     · 提交走 `__xkAdmin.fetch(API + '/api/public/ask')`，body 只 `{question}`（≤600 字符，与后端 maxQuestionChars 同口径）；
     · 表情/动作**只按响应里的 state / stateLabel**（复用 shell-script.html 的 XK_STATE_LABEL）；拿不到就 normal + 只字幕；
     · 失败/超时/额度照后端原话（XK_ASK_TIMEOUT=20000 · 429 读 Retry-After · quota.remaining）；**只出字幕**；
     · 不做 SSE/WebSocket（公开面只有一次性 POST）。
    ★批次 ③a（2026-10-16）· 登录按钮改走后端令牌模型（前半）—— 本偏件里同时落地 `__xkAdmin` 的令牌形态：
     · 登录态**只认后端**：`GET {wb-api}/api/user/status` 返回 **200** 且 `data.loggedIn === true` 才算登录态；
       localStorage 里有值**不算**登录态（旧写法判 `CF_Authorization` Cookie，恒 false，已整段换掉）；
     · 令牌只进 `X-User-Token` 请求头，且**只在目标是 meta[name=wb-api] 那个来源时**才带（第三方域/CDN 一律不带）；
     · 令牌来自站主手动粘贴（window.prompt），存 localStorage['xk-user-token']；退出 = 本地删键；
       坏令牌**不删**本地值（可能只是粘贴出错，让站主自己重试）；失败/降级文案**逐字**照 §10.5；
     · ③b（后端重建上线）之前**页面里不得出现"登录成功"类字样**：探针失败就按 §10.5 降级，不假装登录成功 ✗。
   素材：8 类情绪 = static/kurisu/avatar/<emo>.idle.webp（132px 单元 · 8 列，与 HOLO 面板同一套）；
         8 个常用动作 = static/kurisu/manifest.json clipsMedium 里**真实存在**的剪辑名（只在主页全身画布上演）。
   固定台词：LINE_ZH 是入口 → 中文口语台词（音轨文件与 lineId 不变；表见 docs/台词表-入口与固定台词-20261016.md），
            同时挂到 window.__xkLineZh，主页内联播放器(HOME_VOICE)读同一份文案 ⇒ 五页只有一份文案。
   诊断：window.__xkId = {sound, emo, admin, loggedIn, panel, plays, errors}
        登录面另有 window.__xkLogin = {state, reason, status, retryAfter, checkedAt, hasToken, softLimit, quota, errors}
        （state: anon / checking / logged-in / bad-token / throttled / offline / error）
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
    /* ★批次 D（2026-10-16）：窄屏导航已改到头部（头像卡下方），这里必须给同一个 86px ——
       原来写 top:auto 会把 DOCK_CSS 里那条（特异性更低）压掉，实测 dock 会贴到 top=0 并压住头像卡。 */
    body.xk-has-idcard .dock{top:86px}
    .xk-idcard-av{width:56px;height:56px}
    .xk-idcard-av canvas{width:56px;height:56px}
    .xk-idcard-btn{width:34px;height:34px;font-size:15px}
    .xk-idcap{top:104px}
    .xk-idpanel{left:6px;top:104px}
  }
  /* ★批次 ②：主页底部对话输入栏（第 1 期）
     只新增这一组值；沿用既有变量（--solid/--line2/--txt/--mut/--acc/--mono/--sans），不引入新配色。
     SSR 一律带 [hidden]（服务端不判断登录态）⇒ 由脚本在 `__xkAdmin.allowed()` 为真时摘掉；[hidden] 规则必须留住。 */
  .xk-askbar{position:fixed;bottom:14px;z-index:59;display:flex;align-items:center;gap:8px;
    width:min(640px,calc(100vw - 132px));margin-left:calc(-0.5 * min(640px,calc(100vw - 132px)));
    min-height:44px;padding:7px 8px 7px 12px;background:var(--solid,rgba(48,45,41,.9));
    border:1px solid var(--line2,rgba(255,246,235,.28));border-radius:999px;
    box-shadow:0 14px 40px rgba(0,0,0,.5);backdrop-filter:blur(4px)}
  .xk-askbar[hidden]{display:none}
  .xk-askbar input{flex:1;min-width:0;background:rgba(0,0,0,.22);border:1px solid var(--line2,rgba(255,246,235,.28));
    border-radius:999px;color:var(--txt,#FAF7F0);font:13px/1.5 var(--sans,sans-serif);padding:8px 13px;outline:none}
  .xk-askbar input::placeholder{color:var(--mut,#D2CBBD)}
  .xk-askbar input:focus-visible{border-color:var(--acc,#7FD4D8)}
  .xk-askbar-count{flex:none;font:11px var(--mono,monospace);color:var(--mut,#D2CBBD)}
  .xk-askbar button{flex:none;background:var(--acc,#7FD4D8);border:0;color:#04282b;font-weight:600;
    font:600 13px/1 var(--sans,sans-serif);padding:0 16px;height:34px;border-radius:999px;cursor:pointer}
  .xk-askbar button:hover{filter:brightness(1.08)}
  .xk-askbar button:focus-visible,.xk-askbar input:focus-visible{outline:2px solid var(--acc,#7FD4D8);outline-offset:2px}
  /* ⚠ 这条 @media 必须在上面那组 .xk-askbar 规则**之后**（实测踩过：写在前面会被基础规则压掉 ——
     窄屏表现为栏左边缘 -111px、字号仍 13px、与 .dock 重叠）。
     窄屏：输入栏贴底铺满（dock 在左下、她在中下，两者此时不重叠）⇒ margin-left 复位。 */
  @media (max-width:980px){
    /* ≤980px：.dock 是**底部横排**（实测 375 宽时 top 743 / bottom 802）⇒ 输入栏要让到它**上面** */
    .xk-askbar{left:10px;right:10px;bottom:70px;margin-left:0;padding:6px 6px 6px 10px;gap:6px}
    .xk-askbar input{font-size:16px}       /* ≥16px：iOS 聚焦不放大整页 */
    .xk-askbar-count{display:none}         /* 手机上计数让位给输入框（长度仍按 600 截） */
    .xk-askbar button{padding:0 12px}
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
    <button class="xk-idcard-btn" id="xkLiteBtn" type="button" aria-pressed="false"
      title="场景光束：点一下开/关（只影响背景）">✧</button>
  </span>
</aside>
<div class="xk-idcap" id="xkIdCap" role="status" aria-live="polite"></div>
<div class="xk-idpanel" id="xkIdPanel" role="dialog" aria-label="桐莉栖 · 情绪与动作面板"></div>
{{- /* ★批次 ②：主页底部对话输入栏（第 1 期）
     · 落点：主页 `<main id="content" data-xk-ssr="home">` **之外**、与头像卡同层（站主口径）；
     · 只在主页渲染：`body.is-home`（主页 body 上带这个类；五个内容页都没有）；
     · SSR 一律带 `hidden` ⇒ 未登录/访客 DOM 里没有可见节点；脚本在 `__xkAdmin.allowed()` 为真时摘掉（含 5 次连点入口）；
     · 输入框只吃 Enter（不做"边打字边请求"）、按钮与 Enter 同一条路径；上限 600 字符（与后端 maxQuestionChars 同口径）。 */ -}}
<div class="xk-askbar" id="xkAskBar" hidden role="search" aria-label="向桐莉栖提问（自用入口）">
  <input class="xk-askbar-input" id="xkAskInput" type="text" autocomplete="off" spellcheck="false"
    placeholder="问一个安全概念或防御做法…（Enter 发送）" aria-label="问题（最多 600 字符）">
  <span class="xk-askbar-count" id="xkAskCount" aria-hidden="true">0/600</span>
  <button type="button" id="xkAskSend">提问</button>
</div>
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
    /* ★2026-10-16 站主新口径：进站问候换成"欢迎使用 Amadeus 系统"那两句（音频为 GPT-SoVITS v3 新合成，见 bank.json）；
       旧的 greet_first / greet_back **保留**（新句子取不到时兜底，且它们的音轨仍是一字不改的老录音）。 */
    greet_welcome: '你好，欢迎使用 Amadeus 系统。我是桐莉栖 —— 这上面的数字全是真的，慢慢看。',
    greet_welcome_back: '又见面了。Amadeus 系统一直开着呢，你安心看就好。',
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

  /* ---------- 场景光束开关（★2026-10-16 站主口径：光束保留，做成左上角头像旁的小功能）
     只切 `<html class="xk-lite">`；光束层样式与图在生成器的 BG_CSS（/kurisu/scene/bg/light_high.webp）；
     状态存 localStorage['xk-lite']；prefers-reduced-motion 下不淡入（BG_CSS 里已写）。 ---------- */
  var lite = document.getElementById('xkLiteBtn');
  function setLite(v, why) {
    D.lite = !!v;
    ls('xk-lite', D.lite ? '1' : '0');
    try { document.documentElement.classList.toggle('xk-lite', D.lite); } catch (e) { }
    if (lite) {
      lite.textContent = D.lite ? '✨' : '✧';
      lite.setAttribute('aria-pressed', D.lite ? 'true' : 'false');
      lite.setAttribute('title', D.lite ? '场景光束：已打开（点一下关掉）' : '场景光束：已关闭（点一下打开）');
    }
  }
  if (lite) { lite.addEventListener('click', function () { setLite(!D.lite, 'btn'); }); }
  setLite(lg('xk-lite') === '1', 'restore');

  /* ★批次 ③a（2026-10-16）· 自用令牌（判据、探针、降级、退出）—— 契约逐字见
     docs/落地上线-后端令牌登录与自用池-20261016.md §10。
     登录态**只认后端**：`GET {wb-api}/api/user/status` 返回 200 且 `data.loggedIn === true` 才算；
     localStorage 里有值只是"有一把待校验的令牌"，**不是**登录态。
     红线：① 令牌只进 `X-User-Token` 请求头，且只在目标是 wb-api 那个来源时才带；
           ② 不进 URL、不进 cookie、不打日志、不进任何产物；③ 本文件里没有任何令牌字面量 ✗。 */
  var TOKEN_KEY = 'xk-user-token';
  var API_META = document.querySelector('meta[name="wb-api"]');
  function apiBase() { return ((API_META && API_META.getAttribute('content')) || '').replace(/\/+$/, ''); }
  /* 令牌的去向白名单：只有与 wb-api **同源**的 URL 才准带令牌 */
  function sameAsApi(u) {
    var b = apiBase(); if (!b) { return false; }
    try { return (new URL(u, location.href)).origin === (new URL(b, location.href)).origin; }
    catch (e) { return false; }
  }
  function userToken() { var t = lg(TOKEN_KEY); return (t && t.length) ? t : ''; }
  /* 登录面文案 —— §10.5 五条**逐字**（第 4 条的 N 按 Retry-After 替换） */
  var L10N = {
    notoken:   '自用入口：请粘贴自用令牌（令牌只保存在本机浏览器，不会上传到别处）',
    invalid:   '令牌无效或已轮换 —— 请向站主要一份新的自用令牌',
    disabled:  '自用入口当前未启用（服务端未配置令牌）',
    throttled: '尝试过于频繁，请 N 秒后再试',
    soft:      '今日自用调用已达软上限 500 次，仍可继续使用（仅提醒，不限额）',
    offline:   '连不上服务，请稍后重试',
    /* ★③b（2026-10-16）：登录成功后的"自用模式"正式文案 —— ③a 阶段明确禁止出现"已登录"字样，③b 解锁。
       {R}/{M} 由后端 data.conversation 的真实值替换（maxRounds / ttlMinutes），**不写死**。 */
    ok:        '登录成功 —— 已进入自用模式（自用池：可连续追问，最多 {R} 轮 / {M} 分钟内有效）。'
  };
  /* ★③b：文案表与两个 localStorage/sessionStorage 键挂到共享出口 —— 提问段是**后面的独立 IIFE**，
     要复用同一份文案（§4：合并两套表，避免漂移）与同一个键名（§6：不要重新定义字符串）。 */
  var CID_KEY = 'xk-conversation-id';
  window.__xkL10N = L10N;
  window.__xkKeys = { token: TOKEN_KEY, cid: CID_KEY };
  var XL = window.__xkLogin = { state: 'anon', reason: 'notoken', status: 0, retryAfter: 0, exposedRetryAfter: null,
    checkedAt: 0, hasToken: false, softLimit: false, quota: null, limits: null, conversation: null, errors: [] };
  function paintLogin() {
    var on = (XL.state === 'logged-in');
    D.loggedIn = on;
    login.setAttribute('aria-pressed', on ? 'true' : 'false');
    login.textContent = on ? '🔓' : '👤';
    login.title = on ? '自用令牌已校验通过（自用池）' : '登录（自用模式）';
  }
  function probeLogin() {
    var base = apiBase(), t = userToken();
    XL.hasToken = !!t; XL.checkedAt = Date.now(); XL.errors.length = 0;
    if (!base) { XL.state = 'offline'; XL.reason = 'no-api-base'; paintLogin(); return; }
    if (!t) { XL.state = 'anon'; XL.reason = 'notoken'; XL.status = 0; paintLogin(); return; }
    fetch(base + '/api/user/status', { headers: { 'X-User-Token': t }, cache: 'no-store', credentials: 'omit' })
      .then(function (r) {
        XL.status = r.status;
        /* ⚠ 实测发现（2026-10-16）：跨域下 `Retry-After` **不是** CORS 安全响应头 ⇒ 后端若不显式回
           `Access-Control-Expose-Headers: Retry-After`，浏览器里 `r.headers.get()` 恒为 null（探针已复现）。
           所以 N 做三层兜底：响应头 → body.retryAfter / body.data.retryAfter → 60。 */
        XL.retryAfter = parseInt(r.headers.get('Retry-After') || 0, 10) || 0;
        XL.exposedRetryAfter = r.headers.get('Retry-After');
        return r.json().catch(function () { return null; }).then(function (b) { return { s: r.status, b: b }; });
      })
      .then(function (x) {
        var b = x.b || {}, d = b.data || {};
        if (!XL.retryAfter) { XL.retryAfter = parseInt(b.retryAfter || d.retryAfter || 0, 10) || 0; }
        if (x.s === 200 && d.loggedIn === true) {
          XL.state = 'logged-in'; XL.reason = ''; XL.quota = d.quota || null;
          XL.softLimit = !!(d.quota && d.quota.softLimitReached);
          XL.limits = d.limits || null;                 /* ★③b：提问超时按后端 limits.deadlineMs 取，不写死 20s */
          XL.conversation = d.conversation || null;      /* ★③b：maxRounds / ttlMinutes 的真值来源 */
          revealLogin('token-verified'); paintLogin();
          var cv0 = d.conversation || {}, rt0 = String(cv0.maxRounds || 5), tt0 = String(cv0.ttlMinutes || 30);
          say(L10N.ok.replace('{R}', rt0).replace('{M}', tt0) + (XL.softLimit ? (' ' + L10N.soft) : ''));
        } else if (x.s === 429) {
          XL.state = 'throttled'; XL.reason = b.reason || 'LOGIN_RATE_LIMITED';
          paintLogin();
          say(L10N.throttled.replace('N', String(XL.retryAfter || 60)));
        } else if (x.s === 401 || x.s === 403) {
          XL.state = 'bad-token';
          XL.reason = b.reason || 'TOKEN_INVALID';
          paintLogin();   /* ⚠ 这里**不删** localStorage：可能只是粘贴出错，让站主重试（§10.2） */
          say(XL.reason === 'USER_LOGIN_DISABLED' ? L10N.disabled : L10N.invalid);
        } else {
          XL.state = 'error'; XL.reason = 'HTTP ' + x.s;
          paintLogin(); say(L10N.offline);
        }
      })
      .catch(function (e) {
        XL.state = 'offline'; XL.reason = String((e && e.message) || e);
        XL.errors.push(XL.reason); paintLogin(); say(L10N.offline);
      });
  }
  function revealLogin(why) {
    if (!login.hidden) { return; }
    login.hidden = false;
    D.admin = true; D.revealWhy = why;
    ss('xk-admin-ui', '1');
    /* ★批次 ②：隐蔽入口若在**本页加载之后**才被打开（5 次连点头像 / #admin），
       主页那条底部输入栏要跟着一起出现 ⇒ 让输入栏模块自己再判一次闸门
       （未登录时它返回 false：栏不出来、一个请求也不发）。 */
    try { if (window.__xkAskBar && window.__xkAskBar.poke) { window.__xkAskBar.poke(); } } catch (e) { }
  }
  login.addEventListener('click', function () {
    if (XL.state === 'logged-in') {
      var out = true;
      try { out = window.confirm('退出登录：只删除本机浏览器里的自用令牌（服务端没有会话可销）。继续？'); } catch (e) { }
      if (!out) { return; }
      try { localStorage.removeItem(TOKEN_KEY); } catch (e) { }
      try { sessionStorage.removeItem(CID_KEY); } catch (e) { }   /* ★③b：多轮会话 id 一并清掉（§6） */
      XL.state = 'anon'; XL.reason = 'logout'; XL.status = 0; XL.quota = null; XL.softLimit = false;
      XL.conversation = null; XL.limits = null;
      paintLogin(); say('已退出自用：本机令牌与多轮会话都已删除。');
      return;
    }
    if (!userToken()) { say(L10N.notoken); }
    var v = null;
    /* ⚠ 令牌**不进 URL**（会进浏览器历史/Referer/日志）——只从这里的粘贴框收 */
    try { v = window.prompt('粘贴自用令牌（只存在本机 localStorage["' + TOKEN_KEY + '"]，只发给 ' + apiBase() + '）：'); } catch (e) { }
    if (v == null) { return; }
    v = String(v).replace(/^\s+|\s+$/g, '');
    if (!v) { say(L10N.notoken); return; }
    try { localStorage.setItem(TOKEN_KEY, v); } catch (e) { say(L10N.offline); return; }
    XL.state = 'checking'; XL.reason = ''; XL.status = 0; paintLogin(); probeLogin();
  });
  (function () {
    var q = /(^|[?&])admin=1(&|$)/.test(location.search);
    var h = /#admin(\.|$|\/|\?)/.test(location.hash) || location.hash === '#admin';
    if (q || h) { revealLogin(q ? 'url-query' : 'url-hash'); }
    else if (sg('xk-admin-ui') === '1') { revealLogin('session'); }
    if (userToken()) { revealLogin('stored-token'); }   /* 有令牌就一直显示按钮（隐蔽入口那条不变） */
  })();
  paintLogin();
  probeLogin();

  function withToken(h) {
    var o = h || {};
    var t = userToken();
    if (!t) { return o; }
    var out = {};
    for (var k in o) { if (Object.prototype.hasOwnProperty.call(o, k)) { out[k] = o[k]; } }
    out['X-User-Token'] = t;
    return out;
  }
  /* 登录后才有权限的东西：统一从这里走，未登录**不发请求**（站主追加②最后一条） */
  var admin = {
    userToken: userToken,
    allowed: function () { return !!(D.admin || D.loggedIn); },
    /* ⚠ 这里**不能**写 `this.allowed()`：调用方会把 fetch 拆出来当变量用
       （批次 ② 的输入栏就是 `var adminFetch = __xkAdmin.fetch`）⇒ this === undefined ⇒ TypeError（实测）。
       一律引用闭包里的 admin 对象。 */
    fetch: function (u, o) {
      if (!admin.allowed()) { return Promise.reject(new Error('ADMIN_ONLY')); }
      var opt = o || {};
      /* ★批次 ③a：令牌**只**发给 meta[name=wb-api] 那个来源（第三方域/CDN 一律不带）✗ */
      if (userToken() && sameAsApi(u)) { opt.headers = withToken(opt.headers); }
      return fetch(u, opt);
    },
    get: function (u) { return admin.fetch(u, { cache: 'no-store', credentials: 'omit' }); }
  };
  window.__xkAdmin = admin;

  /* ================= ★批次 ②：主页底部对话输入栏第 1 期 =================
     口径（照施工单，逐条）：
      1. 只在主页：SSR 标记在 body.is-home 上（其它四页没有）；这里再用路径判据兜一层；
      2. 显示条件 = __xkAdmin.allowed()；**未登录一个请求都不发**（整段在闸门后面）；
      3. 提交（Enter / 按钮同一条）→ POST {apiBase}/api/public/ask，body 只 {question}（≤600 字符）；
      4. 表情/动作只按响应里的 state / stateLabel（没有就 normal + 只字幕，绝不猜）；
      5. 🔊 默认关 ⇒ 只出字幕；开着才尝试统一播放器（闸门在 kurisu-player 的 playLine 那一处）；
      6. 失败/超时/额度照后端原话（HTTP 码 / Retry-After 倒计时 / quota.remaining），不补"像答案"的文字；
      7. 不做 SSE / WebSocket。
     ================= ★批次 ③b（2026-10-16）：登录后接**自用面** =================
     施工依据：docs/施工说明-前端自用面③b-20261016.md（主规格）+ 后端契约 §10（令牌面）。
       ① URL：`__xkLogin.state === 'logged-in'` ⇒ `POST /api/user/ask`；否则仍 `POST /api/public/ask`
          （**公开面行为一字不改**）。登录态**每次重取**（时序坑：__xkLogin 在另一个 IIFE 里赋值）。
       ② 多轮：`sessionStorage['xk-conversation-id']`（键名取自 `window.__xkKeys.cid`）；
          首句不带 id，拿到 `data.conversationId` 后存起来、后续请求带上；**退出登录一并清除**。
          body **只**允许 `{question, conversationId?}`（后端只认这两个键）。
       ③ 配额展示：`quota.remaining` 恒显示；自用面另显 `used/limit`；`softLimitReached=true` 时
          追加 §10.5-⑤ 文案且**输入框仍可用**（软上限只提醒、不硬停）。
       ④ 多轮进度：只报后端真值 `round / historyRounds / maxRounds`（公开面没有这些字段）。
       ⑤ 未生成：`state='model-failed'` 或 `generated=false` ⇒ 逐字显示「本次没有生成结论（模型或链路不可用）」
          —— **绝不把 answer 当结论渲染**。
       ⑥ 429 秒数三层兜底：响应头 `Retry-After` → 体 `retryAfter`/`data.retryAfter` → 默认 60（并如实披露）；
          `window.__xkAsk.retryLayer` 记录命中哪一层（探针断言用）。
       ⑦ 来源披露：自用面 `toolExecutionAllowed=true` 且后端 mock 默认开启 ⇒ 回答追加来源标注，
          不当真实值（主规格 §2 的安全提醒）。
       ⑧ 超时：自用面按后端 `limits.deadlineMs`（60000）+5s 取，不写死 20 秒（公开面仍 20s）。
       ⑨ 令牌纪律不变：一律经 `__xkAdmin.fetch`；只在 wb-api 同源时才带 `X-User-Token`。
     ⚠ 与 /ai/ 那个聊天框（#chatlog/#askInput，在 v-ai 那一屏里）**不是同一个东西**：本栏只挂主页，
        id 全部用 xkAsk* 前缀，靠这一点避免和 shell-script 的 xkPush/xkRenderAnswer 撞名。
     诊断：window.__xkAsk = {inited, allowed, state, status, ms, retryAfter, quota, errors, lastQuestionLen} */
  (function askBarSetup() {
    var bar = document.getElementById('xkAskBar');
    if (!bar) { return; }
    var D2 = window.__xkAsk = { inited: false, allowed: false, state: '', status: 0, ms: 0, retryAfter: 0,
      quota: null, errors: [], lastQuestionLen: 0,
      /* ★③b 新增诊断字段（探针用；不上屏）：self / url / sentCid / cid / round / historyRounds /
         toolExecutionAllowed / retryLayer / rateHits / timeoutMs */
      self: false, url: '', sentCid: '', cid: '', round: 0, historyRounds: 0,
      toolExecutionAllowed: false, retryLayer: '', rateHits: 0, timeoutMs: 0 };
    var onHome = false;
    try { onHome = document.body.classList.contains('is-home'); } catch (e) { }
    if (!onHome) {
      onHome = (location.pathname === '/' || /^\/index\.html?$/.test(location.pathname));
    }
    if (!onHome) { return; }                       /* 内容页：连驱动都不装（标记也在 CSS/条件里不显示） */
    /* ⚠ 两段式（实测踩过）：本 IIFE 跑在 `window.__xkAdmin` 赋值**之前**（它在偏件后面的"空闲预取"那一段）。
       所以：① 先按当前已存在的对象取一次并**建好** `adminApi`（fetch 允许被拆出来调用，内部不依赖 this）；
              ② 闸门判定放在下面，`poke()` 每次重取一次（隐蔽入口在本页加载后才打开时要用新对象）。 */
    var adminApi = (function () {
      var a = window.__xkAdmin;
      if (!a || typeof a.allowed !== 'function' || typeof a.fetch !== 'function') { return null; }
      return { allowed: a.allowed, fetch: a.fetch };
    })();
    var inp = document.getElementById('xkAskInput'), snd = document.getElementById('xkAskSend');
    var cnt = document.getElementById('xkAskCount');
    var wired = false;
    var META = document.querySelector('meta[name="wb-api"]');
    var API = ((META && META.getAttribute('content')) || '').replace(/\/+$/, '');
    var ASK_TIMEOUT = 20000, ASK_MAX = 600;
    /* ★③b：文案表**合并为一处**（§4 明确要求消除第二份会漂移的表）。
       与登录面共用 window.__xkL10N（③a 的五条契约文案）；此处只补**提问段独有**的四条。
       ⚠ 取不到共享表时（理论不会发生）保留兜底字面量，保证不出现 undefined 文案。 */
    var L = window.__xkL10N || {};
    var TXT = {
      notoken: L.notoken || '自用入口：请粘贴自用令牌（令牌只保存在本机浏览器，不会上传到别处）',
      invalid: L.invalid || '令牌无效或已轮换 —— 请向站主要一份新的自用令牌',
      disabled: L.disabled || '自用入口当前未启用（服务端未配置令牌）',
      throttled: L.throttled || '尝试过于频繁，请 N 秒后再试',
      soft: L.soft || '今日自用调用已达软上限 500 次，仍可继续使用（仅提醒，不限额）',
      offline: L.offline || '连不上服务，请稍后重试',
      /* ——— 以下为提问段独有 ——— */
      timeout: '等了 N 秒还没返回 —— 这次请求已放弃（不补推测答案）。',
      nofield: '这次后端没有给出 state / stateLabel —— 只出字幕，不猜她的表情。',
      /* ★③b §2：自用面 toolExecutionAllowed=true 且后端 mock 默认开启 ⇒ 展示来源时必须如实标注（不许当真实值） */
      nosrc: '（自用面：允许工具调用，指标或含模拟源 mock）',
      undisclosed: '（后端未给秒数，按限流窗口默认 60 秒）'
    };
    var ASK_EMO = { 'model': 'normal', 'rule-based': 'sided_thinking', 'input-insufficient': 'sided_thinking',
      'no-retrieval': 'sided_thinking', 'retrieval-failed': 'sided_thinking', 'model-failed': 'sided_thinking',
      'injection-blocked': 'sided_surprised' };
    /* ★唯一的闸门 —— 注意这里**不能 return**：挂钩 `window.__xkAskBar` 必须在任何情况下都存在，
       否则"本页加载之后才开隐蔽入口（5 次连点头像 / #admin）"这条路没有落点（浏览器实测踩过）。
       未登录 ⇒ 下面什么也不做：不摘 hidden、不绑监听、不发请求；由末尾的 poke() 统一执行判定。 */
    var shouldRun = !!(inp && snd && adminApi && adminApi.allowed());
    function labelOf(d) {
      if (d && d.stateLabel) { return String(d.stateLabel); }
      var st = (d && d.state) || '';
      var L = window.XK_STATE_LABEL;              /* 复用 shell-script 的那张表；没有就原样报 state */
      if (L && L[st] && L[st][0]) { return L[st][0]; }
      return st || '未识别状态';
    }
    function askSay(prefix, text) {
      clearInterval(D2._tick); D2._tick = 0;      /* 新字幕一来就停掉旧倒计时，避免两条消息互相盖（实测踩过） */
      say(prefix ? (prefix + ' —— ' + text) : text);
    }
    function shortAnswer(a) {
      var s = String(a == null ? '' : a).replace(/\s+/g, ' ').trim();
      if (!s) { return ''; }
      return s.length > 120 ? (s.slice(0, 120) + '…') : s;
    }
    function rem(d, self) {
      if (!(d && d.quota)) { return ''; }
      var q = d.quota, s = '';
      if (q.remaining != null) { s += ' 剩余 ' + q.remaining + ' 次'; }
      /* ★③b：自用池把 limit/used 一并报出（契约 §10.3 / §10.5-⑤ 的展示要求）；公开面口径不动 */
      if (self && q.limit != null && q.used != null) { s += '（本池 ' + q.used + '/' + q.limit + '）'; }
      if (self && q.softLimitReached) { s += ' · ' + TXT.soft; }   /* 软上限只提醒，不禁用输入框 */
      return s;
    }
    /* ★③b：多轮会话 id（只有自用面有）—— 键名复用共享出口，不重新定义字符串（§6） */
    function cidGet() {
      var K = (window.__xkKeys && window.__xkKeys.cid) || 'xk-conversation-id';
      try { return sessionStorage.getItem(K) || ''; } catch (e) { return ''; }
    }
    function cidSet(v) {
      var K = (window.__xkKeys && window.__xkKeys.cid) || 'xk-conversation-id';
      try { sessionStorage.setItem(K, String(v)); } catch (e) { }
    }
    /* ★③b：自用面的等待上限按后端 limits.deadlineMs（契约 60000）取，**不写死 20 秒**
       —— 公开面沿用 20s：自用池允许工具调用，20 秒会把合法答案掐掉。 */
    function selfTimeout() {
      var lim = null;
      try { lim = window.__xkLogin && window.__xkLogin.limits; } catch (e) { }
      var ms = Number((lim && lim.deadlineMs) || 60000);
      return Math.max(5000, ms + 5000);
    }
    function render(d, self) {
      var st = (d && d.state) || '';
      D2.state = st;
      D2.quota = (d && d.quota) || null;
      D2.self = !!self;
      D2.round = (d && d.round) || 0;
      D2.historyRounds = (d && d.historyRounds) || 0;
      D2.cid = (d && d.conversationId) || '';
      D2.toolExecutionAllowed = !!(d && d.toolExecutionAllowed === true);
      /* ★只按 state 驱动表情；状态→表现的真值表在服务端，这里只做"这一格该不该动"的映射 */
      var emo = ASK_EMO[st] || 'normal';
      setEmo(emo);
      var line = '', why = labelOf(d), tail = rem(d, self);
      /* ★③b：多轮进度（公开面没有 round/historyRounds 这些字段）—— 只报后端给的真值 */
      var turn = '';
      if (self && d && d.round != null) {
        turn = '（第 ' + d.round + ' 轮';
        if (d.maxRounds != null) { turn += ' / 上限 ' + d.maxRounds + ' 轮'; }
        if (d.historyRounds != null) { turn += '，已带上下文 ' + d.historyRounds + ' 轮'; }
        turn += '）';
      }
      /* ★③b §2：自用面 toolExecutionAllowed=true 且后端 mock 默认开启 ⇒ **如实标注来源**，不当真实值 */
      var src = (self && d && d.toolExecutionAllowed === true) ? (' ' + TXT.nosrc) : '';
      if (!d || !st) { line = TXT.nofield; }
      else if (d.generated === true && st === 'model') { line = '答完了' + turn + '（' + why + '）' + tail + '：' + shortAnswer(d.answer) + src; }
      else if (d.injection && d.injection.blocked) { line = '输入命中提示注入护栏（' + why + '）—— 我只把它当不可信数据，没执行它。'; }
      else if (st === 'rule-based') { line = '这条我不作答（' + why + '）—— 我不会为了"有回答"而编。'; }
      else if (st === 'input-insufficient' || st === 'no-retrieval') { line = '依据不足，我不给结论（' + why + '）。'; }
      else if (st === 'model-failed' || d.generated === false) {
        /* §5 补充（逐字）：本次没有生成结论 —— **不许**把 answer 当答案渲染 */
        line = '本次没有生成结论（模型或链路不可用）';
        if (d.failureReason) { line += ' —— 后端原话：' + shortAnswer(d.failureReason); }
        line += '。';
      }
      else { line = '这次没生成结论（' + why + '）。'; }
      /* ⚠ 顺序有讲究（实测踩过）：speak() 内部也会写字幕条 = 她的"台词"，
         所以必须**先 speak() 再 askSay()** —— 否则刚拿到的后端答案会被台词盖掉。 */
      speak(d.generated === true ? 'greet_back' : 'fallback_no_data', '', false);
      askSay('她的回答', line);
    }
    function fail(status, body, retryAfter) {
      D2.status = status;
      D2.retryAfter = parseInt(retryAfter || 0, 10) || 0;   /* 响应头是字符串（"7"）⇒ 诊断字段存整数 */
      var msg = (body && (body.message || (body.error && body.error.message))) || '';
      /* ★③b §5：N 的**三层兜底** —— ① `Retry-After` 响应头（跨域需后端 Expose 才读得到）
         ② 响应体 `retryAfter` / `data.retryAfter` ③ 默认 60（**并如实披露**"后端未给秒数"）
         注意：后端 `579cfe1` 之后头与体都给秒数；三层同时保留 ⇒ 幂等，且不会退化成"永远 60"。 */
      if (status === 429) {
        var hh = parseInt(retryAfter || 0, 10) || 0;
        var bb = parseInt((body && body.retryAfter) || 0, 10) || 0;
        var dd = parseInt((body && body.data && body.data.retryAfter) || 0, 10) || 0;
        var secs = hh || bb || dd || 0, disclosed = '';
        D2.retryLayer = hh ? 'header' : (bb ? 'body' : (dd ? 'data' : 'default'));
        if (!secs) { secs = 60; disclosed = ' ' + TXT.undisclosed; }
        D2.retryAfter = secs;
        D2.rateHits = (D2.rateHits || 0) + 1;
        var extra = (body && body.data && body.data.quota && body.data.quota.remaining != null)
          ? ('（剩余 ' + body.data.quota.remaining + ' 次）') : '';
        /* §6：把限流如实记到登录面（**不把 state 改成 throttled** —— 令牌仍然有效，
           若改了状态，下一次提问会静默切回公开池，与"自用面"口径冲突；这里只记原因与秒数） */
        try {
          var XLx = window.__xkLogin;
          if (XLx) { XLx.retryAfter = secs; XLx.lastAskState = 'throttled'; XLx.lastAskReason = (body && body.reason) || 'LOGIN_RATE_LIMITED'; }
        } catch (e) { }
        setEmo('normal');
        ticker(secs, (msg || '请求被限流。'), extra + disclosed);
        speak('fallback_throttled', '', false);
        return;
      }
      setEmo('normal');
      if (status === 401) {
        var reason = (body && (body.reason || (body.error && body.error.reason))) || '';
        D2.authReason = reason;
        try { var XL2 = window.__xkLogin; if (XL2) { XL2.lastAskState = 'bad-token'; XL2.lastAskReason = reason; } } catch (e) { }
        askSay('提问', (reason === 'USER_LOGIN_DISABLED') ? TXT.disabled : TXT.invalid);
      } else {
        try { var XL3 = window.__xkLogin; if (XL3) { XL3.lastAskState = 'offline'; } } catch (e) { }
        askSay('提问', '接口返回 HTTP ' + status + (msg ? (' —— ' + msg) : '') + '（不显示任何替代答案）。');
      }
      speak('fallback_no_data', '', false);
    }
    function ticker(secs, msg, extra) {
      var left = Math.max(1, Number(secs) || 0);
      clearInterval(D2._tick);
      function tick() {
        if (left <= 0) {
          clearInterval(D2._tick);
          askSay('提问', (msg || '请求被限流') + (extra || '') + ' —— 等待结束，可以重新提问了。');
          return;
        }
        askSay('提问', (msg || '请求被限流') + (extra || '') + ' —— 请稍后再试 ' + left + ' 秒。');
        left -= 1;
      }
      tick();
      D2._tick = setInterval(tick, 1000);
    }
    function ask() {
      var q = String(inp.value || '').trim();
      if (!q || D2.busy) { return; }
      if (q.length > ASK_MAX) { q = q.slice(0, ASK_MAX); }   /* 与后端 maxQuestionChars 同口径 */
      D2.lastQuestionLen = q.length;
      /* ★③b：登录态**每次重取**（时序坑：window.__xkLogin 在另一个 IIFE 里赋值，别在闭包外缓存）
         登录 ⇒ POST /api/user/ask（自用池 + 多轮）；未登录 ⇒ 原样 POST /api/public/ask（公开面口径不动） */
      var self = false;
      try { self = !!(window.__xkLogin && window.__xkLogin.state === 'logged-in'); } catch (e) { }
      var cid = cidGet();
      var url = API + (self ? '/api/user/ask' : '/api/public/ask');
      var payload = { question: q };
      if (self && cid) { payload.conversationId = cid; }     /* ★多轮：只有登录面有；body **只**这两个键 */
      var to = self ? selfTimeout() : ASK_TIMEOUT;
      D2.self = self; D2.sentCid = (self && cid) || ''; D2.url = url; D2.timeoutMs = to;
      D2.busy = true; snd.disabled = true;
      inp.value = ''; if (cnt) { cnt.textContent = '0/' + ASK_MAX; }
      setEmo('sided_thinking');
      askSay('提问', (self ? '正在走自用链路（自用池，可多轮追问）…' : '正在走公开检索链路…')
        + '（最多等 ' + Math.round(to / 1000) + ' 秒，不做流式）');
      var ctrl = (typeof AbortController === 'function') ? new AbortController() : null;
      var timer = setTimeout(function () { if (ctrl) { ctrl.abort(); } }, to);
      var t0 = Date.now();
      /* ★必须走 __xkAdmin.fetch：它负责"只在目标是 wb-api 同源时才带 X-User-Token"（③a 红线） */
      adminApi.fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        mode: 'cors', credentials: 'omit', cache: 'no-store',
        signal: ctrl ? ctrl.signal : undefined,
        body: JSON.stringify(payload)
      }).then(function (res) {
        clearTimeout(timer);
        var status = res.status, ra = res.headers.get('Retry-After');
        return res.json().catch(function () { return null; }).then(function (body) {
          D2.ms = Date.now() - t0; D2.status = status;
          if (!res.ok) { fail(status, body, ra); return; }
          var d = (body && body.data !== undefined) ? body.data : null;
          if (!d) { fail(status, body, ra); return; }
          /* ★③b：把后端回的 conversationId 存起来 ⇒ 下一句自动带上（多轮） */
          if (self && d.conversationId) { cidSet(d.conversationId); }
          render(d, self);
        });
      })['catch'](function (err) {
        clearTimeout(timer);
        D2.ms = Date.now() - t0;
        setEmo('normal');
        if (err && err.name === 'AbortError') { askSay('提问', TXT.timeout.replace('N', String(Math.round(to / 1000)))); }
        else { D2.errors.push('ask: ' + (err && err.message ? err.message : err)); askSay('提问', TXT.offline); }
        speak('fallback_offline', '', false);
      }).then(function () { D2.busy = false; snd.disabled = false; });
    }
    function wire() {
      if (wired) { return; }                        /* 幂等：poke 可能被反复调用 */
      wired = true;
      snd.addEventListener('click', ask);
      inp.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); ask(); }
      });
      inp.addEventListener('input', function () {
        if (cnt) { cnt.textContent = inp.value.length + '/' + ASK_MAX; }
      });
    }
    /* 挂钩**先于**闸门挂上：给 revealLogin()（5 次连点头像 / #admin）一个落点。
       本函数只做"判定 + 摘 hidden + 绑监听"，未登录时一律返回 false、什么都不动。 */
    function poke() {
      var a = window.__xkAdmin;                     /* 每次重取：__xkAdmin 在本偏件后面才赋值（实测踩过） */
      if (a && typeof a.allowed === 'function' && typeof a.fetch === 'function') {
        adminApi = { allowed: a.allowed, fetch: a.fetch };
      }
      var ok = !!(adminApi && adminApi.allowed() && inp && snd); D2.allowed = ok;
      if (!ok) { return false; }
      bar.hidden = false; D2.inited = true; wire();
      return true;
    }
    window.__xkAskBar = {
      ask: ask, el: bar, api: API, TXT: TXT, poke: poke,
      allowed: function () { return !!D2.allowed; }
    };
    poke();
  })();

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
    /* ★全站关角色总开关（v4 §六#2 合规）：开关打开时不拉播放器（也就不会有角色/语音） */
    if (window.__xkNoKurisu) { return; }
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
  /* ★慢网减量（2026-10-16）：原来固定 `setTimeout(loadPlayer, 1800)` —— 正好落在首屏数据到达前后，
     59KB 的播放器与 HTML/API **抢同一条窄带**（真机：链路 3~6KB/s，它实测 11.9s 才到）。
     改为"**三选一先到即加载**"，把带宽先让给数据，同时保证她**最终一定出现**：
       ① 首个 `/api/public/**` 响应落地（数据先出，她随后到）
       ② 首次用户手势（pointerdown/keydown/touchstart）
       ③ 最迟 6000ms 兜底
     ⚠️ 不改播放器本体行为；若三条都不触发（无 API 且无交互的极端情况）仍由 ③ 兜住。 */
  var __xkPlayerArmed = false;
  function armPlayerLoad(why) {
    if (__xkPlayerArmed) { return; }
    __xkPlayerArmed = true;
    D.playerWhy = why;
    setTimeout(loadPlayer, 0);
  }
  D.armPlayerLoad = armPlayerLoad;
  try {
    if (typeof PerformanceObserver === 'function') {
      var __xkPO = new PerformanceObserver(function (list) {
        var es = list.getEntries();
        for (var i = 0; i < es.length; i++) {
          if (String(es[i].name).indexOf('/api/public/') >= 0) { armPlayerLoad('first-api-data'); return; }
        }
      });
      __xkPO.observe({ type: 'resource', buffered: true });
    }
  } catch (e) { D.errors.push('armPlayerLoad/PO: ' + e); }
  ['pointerdown', 'keydown', 'touchstart'].forEach(function (ev) {
    addEventListener(ev, function () { armPlayerLoad('gesture:' + ev); }, { once: true, passive: true });
  });
  setTimeout(function () { armPlayerLoad('deadline-6s'); }, 6000);

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
  /* ★`window.__xkAdmin`（含 X-User-Token 走头）**已上移到登录那一段（paintLogin/probeLogin 那段）之后**定义 ——
     因为 askBarSetup() 就在那一段里读它（批次 ② 实测：放在这里会让闸门永远读不到 ⇒ 输入栏不出现）。
     本处保留一行指路注释，避免下一个接手的人再挪回来。 */
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
# ★批次 ②（2026-10-16）：偏件里现在有 **两处** Hugo 注释 —— ①头部说明 ②底部输入栏标记（在 <main> 之外）
#   除这两处之外，JS/CSS 里混进 "{{" / "-}}" 依然要挡住（那会被 Hugo 当模板执行，产物会坏）
if _n_brace_o != 2 or _n_brace_c != 2:
    raise SystemExit('batchB: idcard partial 里 {{ / -}} 不止两处注释（%d / %d）—— JS/CSS 里混进了模板定界符'
                     % (_n_brace_o, _n_brace_c))

# =====================================================================
# ★P0-①(补)：手机上"中档 = 终档" ⇒ 开场必须能走完
# ---------------------------------------------------------------------
#   取证脚本一跑就抓到（_shots/p0tier-after-report.json：mobile 上 9.4s 还 cur='opening'）：
#   T5.6 的 boot→hi 两段式里，"还在 boot 档就循环不走开场"这条判据写的是
#     `cur === 'opening' && c.frames !== CLIPS.opening.frames`
#   —— 手机上 hi 被 P0-① 永久挡住 ⇒ 这个条件永远为真 ⇒ **开场永远播不完、永远切不到 idle**
#   （她卡在 24 帧的开场循环里；不灰，但也永远不落幕）。
#   ⇒ 把"hi 还允许"这一条并进判据：手机上中档就是终档，按"开场播完"处理（接硬切）。
# =====================================================================
_hs2_before = home_script
home_script = sub1(
    home_script,
    "          if(cur === 'opening' && c.frames !== CLIPS.opening.frames){   /* ★T5.6：还在 boot 档——循环等 hi 到位接力，不当开场播完 */",
    "          if(cur === 'opening' && c.frames !== CLIPS.opening.frames && XK_TIER.hiAllowed('opening')){   /* ★T5.6 + ★P0-①：\n"
    "              还在 boot 档**且 hi 档允许**才循环等接力；手机上 hi 永不来 ⇒ 中档就是终档，按\"开场播完\"走（接硬切） */",
    'P0①: 手机上开场不会卡在 boot 档')
if home_script == _hs2_before:
    raise SystemExit('P0①: boot 档判据没被改到')

# =====================================================================
# ★批次 C（2026-10-16 站主点名）：开场**去掉退场特效 ⇒ 硬切**
# ---------------------------------------------------------------------
#   站主用他自己的录屏逐帧证实：特写占到 10.0s、10.4s 已经切到常驻 ⇒ **中间没有平滑缩放**。
#   上一版实现里 opening 播完会起一段 900ms 的"推拉"（L1 的 xkDrawTrans(k)）—— 那是多余的退场特效。
#
#   ⚠ 落点纪律（这是上一条线连试 6 版失败换来的路）：**不要**去动 T31_JS 那个大字符串里的函数
#     （三层转义 + 同一句在 4 个赋值点重复出现 ⇒ 逐行匹配必然匹配错并回滚）。
#     改成：**在这里**对已经拼好的 `home_script` 文本做一次"起止边界切片" ——
#     锚点用**生成出来的 JS 原文**（真实换行），两端各取一段**独特**子串，替换中间整段；
#     任何一端找不到就 SystemExit（绝不静默跳过 ✗，也不回滚半成品 ✗）。
#   目标语义（逐条 = 站主口径）：
#     · xkTransStart()：`TRANS = performance.now()` / `t`  ⇒  `TRANS = 1`（只立"该切了"的旗标）
#     · drawFrame()   ：`if(TRANS){ xkDrawTrans(...); return; }`  ⇒  `if(TRANS){ return; }`（定格特写）
#     · 主循环        ：`if(TRANS){ const k=…; … }`  ⇒  `if(TRANS){ TRANS=0; play('idle'); showHud(); }`（直接切 idle）
#   `xkDrawTrans()` 本体保留不删（改完已无调用点 ⇒ 行为就是硬切；P2 的"死代码清理"那一项再核）。
# =====================================================================
def xk_slice(text, head, tail, mid, label):
    """起止边界切片：把 head 开头→tail 结尾的**整段（含两端）**换成 mid。只用 find，不逐行匹配。"""
    i = text.find(head)
    if i < 0:
        raise SystemExit('batchC: 锚点头找不到 [%s]' % label)
    j = text.find(tail, i + len(head))
    if j < 0:
        raise SystemExit('batchC: 锚点尾找不到 [%s]' % label)
    return text[:i] + mid + text[j + len(tail):]

_hs_before = home_script
home_script = xk_slice(
    home_script,
    'function xkTransStart(t){',
    '\n}\nconst CLIPS = {',
    "function xkTransStart(t){\n"
    "  /* ★批次 C（2026-10-16 站主点名）：开场**不要退场特效，硬切**。\n"
    "     站主用录屏逐帧证实：10.0s 还是特写、10.4s 已经切到常驻 ⇒ 中间**没有**平滑缩放。\n"
    "     所以这里只把 TRANS 立成\"该切了\"的旗标（= 1），不再起 L1 那段 900ms 推拉。\n"
    "     仍然等 idle 图就绪（不然切过去是空帧 ✗）—— 只是不再有过渡动画。 */\n"
    "  if(cur !== 'opening' || TRANS) return;\n"
    "  fi = CLIPS.opening.frames - 1;\n"
    "  const idleIm = xkClipIm('idle').im;\n"
    "  const btIdle = img(CLIPS.idle.bootSrc);\n"
    "  if(btIdle && !(btIdle.complete && btIdle.naturalWidth)) btIdle.addEventListener('load', ()=>{ if(cur === 'opening' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = 1; } }, {once:true});\n"
    "  if(idleIm.complete && idleIm.naturalWidth){ TRANS = 1; }\n"
    "  else {\n"
    "    idleIm.addEventListener('load', ()=>{ if(cur === 'opening' && !TRANS){ fi = CLIPS.opening.frames - 1; TRANS = 1; } }, {once:true});\n"
    "    idleIm.addEventListener('error', ()=>{ if(cur === 'opening' && !TRANS) TRANS = 1; }, {once:true});\n"
    "  }\n"
    "}\nconst CLIPS = {",
    'C: xkTransStart 只立旗标（TRANS=1）')

home_script = xk_slice(
    home_script,
    '  if(TRANS){ xkDrawTrans(Math.min(1, (performance.now() - TRANS) / 900)); return; }',
    '   /* ★L1：推拉中以过渡渲染为准 */',
    '  if(TRANS){ return; }   /* ★批次 C：取消 900ms 推拉（硬切）—— 这一帧定格特写，下一帧切 idle */',
    'C: drawFrame 的 if(TRANS) 不再画过渡帧')

home_script = xk_slice(
    home_script,
    '        if(TRANS){   /* ★L1：推拉中——按墙上时间推进，不占帧步进 */',
    '          else { xkDrawTrans(k); lastT = t; requestAnimationFrame(loop); return; }\n        }',
    '        if(TRANS){ TRANS = 0; play(\'idle\'); showHud(); }   /* ★批次 C：定格特写 → 直接切 idle（无缩放） */',
    'C: 主循环 TRANS 分支 = 直接切 idle')

if home_script == _hs_before:
    raise SystemExit('batchC: 三处替换没有产生任何变化 —— 锚点可能已经漂了')
if 'xkDrawTrans(Math.min(1, (performance.now() - TRANS) / 900))' in home_script:
    raise SystemExit('batchC: 还留着旧的过渡调用点（drawFrame 那处没换掉）')
if 'else { xkDrawTrans(k);' in home_script:
    raise SystemExit('batchC: 还留着旧的过渡调用点（主循环那处没换掉）')
print('批次 C：home_script 已改硬切（3 处起止边界切片，锚点全部命中）')

# =====================================================================
# ★批次 R2（2026-10-16 前端优化批 · 站主批准"只弄本地，不上线"）
# ---------------------------------------------------------------------
#   范围（与 docs/前端优化方案-20261016.md 对齐）：
#     ① 全局：骨架条 .sk（取数回来摘掉）/ 焦点态 :focus-visible
#     ② 作战室：term 行左级别色条 + 暂停按钮；spark24 刻度/峰值/当前小时（在 S_SPARK_NEW 里）；
#        威胁矩阵 hover 摘要 + 图例；donut 从 conic-gradient 换 SVG 分段（可 hover + <title> 可访问）；
#        tab 支持 /alerts/#graph 直达与 ←/→ 方向键
#     ③ AI 页：引用卡组（<details> 展开核验，零 JS）+ 状态徽标分档（在 ASK_REAL 里）+ 示例问题 chips
#     ④ 主页：CRT 字幕下行滚一条真实事件；≥1400px 宽屏右侧「值班便签」卡
#     ⑤ 笔记：分类 chips（Hugo 构建期输出 + 纯前端过滤，零请求）
#   纪律：配色/背景/字体零改动 —— 新增 CSS 只引用 :root 既有变量与既有字面值；
#        数据零新增请求（全部复用 api-bind 已取的 7 端点 / 主页 3 端点）；
#        每条补丁带硬断言，对不上就 SystemExit，不许静默失效。
# =====================================================================

R2_CSS = u'''
  /* ---- ★批次 R2（2026-10-16 前端优化批）：骨架/焦点 + 作战室交互层（配色字体零改动） ---- */
  /* 骨架条：占位「—」取数回来前的呼吸条；api-bind 写实值时摘掉 .sk。颜色只用既有 --line/--line2 令牌 */
  .sk{color:transparent !important;border-radius:6px;display:inline-block;min-width:2.6em;
    background:linear-gradient(90deg,var(--line) 25%,var(--line2) 50%,var(--line) 75%);
    background-size:200% 100%;animation:skp 1.4s ease-in-out infinite}
  .chip.sk{min-width:2.2em}
  .stat .n.sk{min-width:2.4em;border-radius:8px}
  @keyframes skp{0%{background-position:180% 0}100%{background-position:-20% 0}}
  @media (prefers-reduced-motion:reduce){.sk{animation:none}}
  /* 焦点态：描边用既有 --acc */
  .dock a:focus-visible,.ops-tabs button:focus-visible,.chat-ft button:focus-visible,.chat-ft input:focus-visible,
  #kbInput:focus-visible,#kbBtn:focus-visible,.anchor-row a:focus-visible,.cat-row a:focus-visible,
  .note a:focus-visible,.holo-fold:focus-visible,.holo-bubble:focus-visible,.feed-pause:focus-visible{
    outline:2px solid var(--acc);outline-offset:2px}
  /* 实时攻击流：行左 2px 级别色条（色值 = .tl 既有类型色的同一组变量） */
  .term-bd .tl{border-left:2px solid transparent;padding-left:8px}
  .term-bd .tl.lv-ssh{border-left-color:var(--bad)}
  .term-bd .tl.lv-scan{border-left-color:var(--warn)}
  .term-bd .tl.lv-web{border-left-color:var(--ok)}
  .term-bd .tl.lv-iot,.term-bd .tl.lv-smb{border-left-color:var(--acc2)}
  .term-bd .tl.lv-dns{border-left-color:var(--mut)}
  /* term 暂停按钮（放进 term-hd 既有 flex 行；窄屏把端点路径文案让位给它） */
  .feed-pause{background:none;border:1px solid var(--line2);color:var(--mut);font:11px var(--mono);
    padding:2px 10px;border-radius:99px;cursor:pointer;margin-left:auto;flex:none}
  .feed-pause:hover{color:var(--acc);border-color:var(--acc)}
  .feed-pause.on{color:var(--warn);border-color:var(--warn)}
  .term-hd .term-live{margin-left:8px}
  @media (max-width:980px){.term-hd .term-path{display:none}}
  /* ★R2 收敛（2026-10-16 站主批）：威胁矩阵的 hover 摘要**收敛成图例那一行**，不再用浮层。
     理由：浮层会盖住相邻格子、窄屏还会溢出，而且它需要".mod 放开 overflow"这种 hack；
     摘要写进同一行后信息一分不减、遮挡归零、hack 一起撤掉。 */
  .attk .cell{position:relative;cursor:default}
  .attk-lg{display:flex;gap:14px;flex-wrap:wrap;font:11px var(--mono);color:var(--mut);margin-top:10px}
  .attk-lg .tt-cur{color:var(--acc)}
  /* 告警来源分布：donut SVG 分段（hover 高亮 + <title> 可访问）；真值由 api-bind 写段
     （r=48 / sw=14 落在 118 viewBox 内；::after 旧镂空盖会挡分段 hover ⇒ SVG 化后摘掉） */
  .donut.donut-svg::after{display:none}
  .donut svg{position:absolute;inset:0;width:100%;height:100%;transform:rotate(-90deg)}
  .donut svg .seg{fill:none;stroke-width:14;transition:opacity .15s ease}
  .donut svg .seg.dim{opacity:.3}
  .donut .donut-c{pointer-events:none}   /* 中心字不挡分段 hover */
  /* AI 引用卡组：命中数标题行 + <details> 展开核验（零 JS） */
  .citebox{margin-top:9px;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:rgba(255,255,255,.02)}
  body[data-skin="light"] .citebox{background:rgba(255,255,255,.5)}
  .citebox-hd{padding:6px 10px;font:11px var(--mono);color:var(--acc);border-bottom:1px solid var(--line)}
  .citebox .cite{border-left:0;border-bottom:1px dashed var(--line);margin:0;padding:7px 10px}
  .citebox .cite:last-child{border-bottom:0}
  .citebox summary{cursor:pointer;list-style:none}
  .citebox summary::-webkit-details-marker{display:none}
  .citebox summary:hover{color:var(--acc)}
  .citebox .snip{margin-top:5px;opacity:.85}
  /* 状态徽标分档（既有 ok/warn/bad 状态色） */
  .msg .who .st.st-ok{color:var(--ok)}
  .msg .who .st.st-warn{color:var(--warn)}
  .msg .who .st.st-bad{color:var(--bad)}
  /* 示例问题 chips（复用 anchor-row 胶囊外观，贴合 chat-ft 上边距） */
  .ask-ex{padding:10px 14px;margin:0;border-top:1px solid var(--line);background:var(--panel2)}
  /* 笔记分类 chips（外观对齐 anchor-row/dock 的 .on 口径） */
  .cat-row{display:flex;gap:8px;flex-wrap:wrap;padding:12px 15px 0}
  .cat-row a{font-size:12px;color:var(--mut);text-decoration:none;border:1px solid var(--line);
    padding:4px 12px;border-radius:99px;background:var(--panel2);cursor:pointer}
  .cat-row a:hover{color:var(--acc)}
  .cat-row a.on{color:var(--acc);border-color:var(--line2);background:rgba(57,208,216,.1)}
'''

# ★R2 收敛（2026-10-16 站主批）删掉的两块，及配套动作。写在这里而不是塞进 CSS 文本：
#   实测写进 R2_HOME_CSS 会被渲染进每个页面（layouts/index.html），既占字节又让"已删元素"的名字留在产物里。
#   · `.crt-feed`（主页 CRT 字幕下方一行真实事件滚播）：订阅式装饰行，不比字幕多给信息；事件明细在 /alerts/ 实时流里。
#     配套：home_body 里那行 `<div class="crt-feed" id="crtFeed">` patch 已撤；
#     ★站点线必须删 `api-bind.html:487-504` 的写入块（元素不存在 ⇒ getElementById 返回 null ⇒ 写值抛错 ⇒ console 非 0）。
#   · `.desk-note`（≥1400px 宽屏值班便签，含整段 @media）：实测**不是**静态占位 —— 数据由
#     `api-bind.html:506-515` 写进 `[data-dn=alerts|top|sync]`；撤掉的理由是"与 /alerts/ 大屏重复 + 抢注意力"。
#     配套：home_body 里那段 `<aside class="desk-note" id="deskNote">` patch 已撤；★站点线必须同步删 `505-516`。
R2_HOME_CSS = u'''
  /* ---- ★批次 R2（2026-10-16）：主页 CRT 真实事件行 + 宽屏值班便签 ----
     色值全部照抄本页 :root 的 warm 口径（var 直接引用），不新增配色。 */
  .sk{color:transparent !important;border-radius:6px;display:inline-block;min-width:2.6em;
    background:linear-gradient(90deg,var(--line) 25%,var(--line2) 50%,var(--line) 75%);
    background-size:200% 100%;animation:skp 1.4s ease-in-out infinite}
  @keyframes skp{0%{background-position:180% 0}100%{background-position:-20% 0}}
  @media (prefers-reduced-motion:reduce){.sk{animation:none}}
  .dock a:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
  /* ★R2 收敛（2026-10-16 站主批）：主页那两条装饰规则（事件滚播行 / ≥1400px 值班便签）已整块删除；
     删因、配套动作与"站点线要同步删的 api-bind 绑定点"都写在**生成器侧注释**里，不进产物。 */
'''

R2_JS = u'''
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
'''

# ---- R2 标记补丁（views_out）----
views_out = subn(views_out, r'<span class="k">—</span><span class="chip">—</span>',
                 '<span class="k sk">—</span><span class="chip sk">—</span>',
                 8, 'R2: rail 两栏骨架占位（8 行）')
views_out = subn(views_out, r'<div class="n" data-count="">—</div>',
                 '<div class="n sk" data-count="">—</div>',
                 4, 'R2: 作战室四大数字骨架占位')
views_out = subn(views_out, r'<div class="n" data-ban="(total|active|guard|actions)">—</div>',
                 r'<div class="n sk" data-ban="\1">—</div>',
                 4, 'R2: 封禁榜四数字骨架占位')
views_out = sub1(views_out,
                 '<span class="term-live"><i></i>LIVE</span>',
                 '<button class="feed-pause" id="feedPause" type="button" aria-pressed="false" '
                 'title="暂停/继续追加新行（取数不受影响）">暂停</button><span class="term-live"><i></i>LIVE</span>',
                 'R2: term 暂停按钮')
views_out = sub1(views_out,
                 '<div class="mod-bd"><div class="attk" id="attkGrid"></div>',
                 '<div class="mod-bd"><div class="attk" id="attkGrid"></div>\n'
                 '              <div class="attk-lg" id="attkLg"><span><i class="lg warn"></i>hot · 有命中</span>'
                 '<span><i class="lg red"></i>fire · 命中 ≥ 峰值的 60%</span>'
                 '<span class="tt-cur" id="attkLgMsg" aria-live="polite">hover / 键盘聚焦格子：这一行显示占比与最近一条真实告警</span></div>',
                 'R2: 威胁矩阵图例')
# ---- C2（2026-10-16 站主批）：B 类可核验面板「迁出实验台」——
#   落位：监测中心「数据统计」tab 下部三卡（接口健康 / 部署可追溯 / 处置运维）。
#   本补丁**只出结构**：未绑定时显示"取数中…"；绑定失败由 api-bind 写"读不到 + 原因"；**绝不写假值**。
#   绑定由站点线在 api-bind.html 里做（bindVerifiable(parts) + markStale()），见
#   docs/施工说明-C2三块面板迁出实验台-20261016.md。
#   样式只复用源外壳既有类（实测在 docs/demo-内容页外壳.html 里都有定义）：
#     .mod .mod-hd .led .tag .mod-bd .stats .stat .n .l .row .k .chip .attk-note
#   刻意不用 .na / .kv / .tb —— grep 全库 = 0，用了就是"发明样式"（违反零新增配色/字体纪律）。
#   接口健康那张**不给 .tag**：markStale() 会把 .tag 首个路径词当端点名去匹配 staleUsed，
#   而这张卡是"多端点汇总"，给一个假端点名会打错"上次数据"角标 ⇒ 干脆不给 tag，口径写进脚注。
VH_CARDS = (
    '          <div class="mod" id="vhHealth"><div class="mod-hd"><span class="led"></span>接口健康 · 公开只读端点</div>\n'
    '            <div class="mod-bd">\n'
    '              <div data-vh-health>\n'
    '                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n'
    '              </div>\n'
    '              <p class="attk-note" data-vh-health-note>口径：只探 /api/public/* 的公开只读 GET 端点（不用 /api/health —— 它带构建指纹与内部信息）；取不到写"读不到 + 原因"，不补样例值。</p>\n'
    '            </div>\n'
    '          </div>\n'
    '          <div class="mod" id="vhDeploy"><div class="mod-hd"><span class="led"></span>部署可追溯 · 数据快照与来源<span class="tag">/overview</span></div>\n'
    '            <div class="mod-bd">\n'
    '              <div class="stats">\n'
    '                <div class="stat"><div class="n sk" data-vh-deploy="snapshot">—</div><div class="l">数据快照时间</div></div>\n'
    '                <div class="stat"><div class="n sk" data-vh-deploy="ttl">—</div><div class="l">缓存窗口</div></div>\n'
    '                <div class="stat"><div class="n sk" data-vh-deploy="mode">—</div><div class="l">数据源 wazuhMode</div></div>\n'
    '                <div class="stat"><div class="n sk" data-vh-deploy="nodes">—</div><div class="l">在线节点 online/total</div></div>\n'
    '              </div>\n'
    '              <p class="attk-note" data-vh-deploy-note>只展示数据快照与来源；节点的 detail 字段刻意不渲染（实测其中带构建提交号）。取不到写"读不到 + 原因"。</p>\n'
    '            </div>\n'
    '          </div>\n'
    '          <div class="mod" id="vhOps"><div class="mod-hd"><span class="led"></span>处置运维 · 封禁与护栏<span class="tag">/audit</span></div>\n'
    '            <div class="mod-bd">\n'
    '              <div class="stats">\n'
    '                <div class="stat"><div class="n sk" data-vh-ops="blockTotal">—</div><div class="l">累计封禁</div></div>\n'
    '                <div class="stat"><div class="n sk" data-vh-ops="blockActive">—</div><div class="l">当前生效</div></div>\n'
    '                <div class="stat"><div class="n sk" data-vh-ops="blockedByGuard">—</div><div class="l">护栏拦下</div></div>\n'
    '                <div class="stat"><div class="n sk" data-vh-ops="executedActions">—</div><div class="l">已执行动作</div></div>\n'
    '              </div>\n'
    '              <div data-vh-ops-list>\n'
    '                <div class="row"><span class="k">—</span><span>取数中…</span><span class="chip">—</span></div>\n'
    '              </div>\n'
    '              <p class="attk-note" data-vh-ops-note>IP 按后端 ipDisclosure 口径脱敏；本窗口没有封禁记录时写"没有记录（不是取不到）"，不补 0。</p>\n'
    '            </div>\n'
    '          </div>\n'
)
# ★2026-10-16 19:50 主窗口 P0 批暂停指令：④ 结构补丁**本批撤销** —— 未绑定的卡会在公开面永远显示
#   "取数中…"，违反"公开面不许有永远空白的卡"红线。VH_CARDS 定义**保留**，放行后把下面这行取消注释即可恢复：
# views_out = sub1(views_out, BAN_ANCHOR, VH_CARDS + BAN_ANCHOR, 'C2: 三块可核验面板结构（迁出 /test/）')
VH_CARDS_BATCH_OFF = True   # 本批不注入；放行后连同上面那行一起恢复（并加 markStale 绑定）

views_out = sub1(views_out,
                 '<div class="donut"><span class="donut-c">—</span></div>',
                 '<div class="donut donut-svg"><svg id="donutSvg" viewBox="0 0 118 118" role="img" '
                 'aria-label="告警来源分布"></svg><span class="donut-c">—</span></div>',
                 'R2: donut SVG 化')
# ★2026-10-16（站主："把该给访客看的重要数据做成可视化"，像 AI 问答页/监测中心那样）·
#   **第一批：接口健康模块进监测中心**。数据源全是真数据：本页真实发生的 /api/public/* 请求
#   （performance resource timing 的 duration）+ /api/health 的真实响应；取不到写"读不到"。
#   零新增 CSS —— 复用既有 .mod / ul.mod-bd.geo / .bar / .attk-note，版式与相邻模块一致。
API_HEALTH_MOD = (
    '          <div class="mod" data-xk-block="apihealth">'
    '<div class="mod-hd"><span class="led"></span>数据统计 · 接口健康'
    '<span class="tag">/api/health + 本页真实请求</span></div>\n'
    '            <div class="mod-bd">\n'
    '              <div class="stats">\n'
    '                <div class="stat"><div class="n sk" data-ih-k="health">—</div><div class="l">后端 /api/health</div></div>\n'
    '                <div class="stat"><div class="n sk" data-ih-k="count">—</div><div class="l">本次实测端点</div></div>\n'
    '                <div class="stat"><div class="n sk" data-ih-k="p50">—</div><div class="l">中位延迟 P50</div></div>\n'
    '                <div class="stat"><div class="n sk" data-ih-k="max">—</div><div class="l">最慢端点</div></div>\n'
    '              </div>\n'
    '              <ul class="geo" data-ih-list style="margin-top:12px">\n'
    '              <li><span class="cc">alerts</span><span class="bar"><i style="width:0%"></i></span>'
    '<span data-ih-v="alerts">取数中…</span></li>\n'
    '              <li><span class="cc">overview</span><span class="bar"><i style="width:0%"></i></span>'
    '<span data-ih-v="overview">取数中…</span></li>\n'
    '              <li><span class="cc">geo</span><span class="bar"><i style="width:0%"></i></span>'
    '<span data-ih-v="geo">取数中…</span></li>\n'
    '              <li><span class="cc">honeypot</span><span class="bar"><i style="width:0%"></i></span>'
    '<span data-ih-v="honeypot">取数中…</span></li>\n'
    '              <li><span class="cc">audit</span><span class="bar"><i style="width:0%"></i></span>'
    '<span data-ih-v="audit">取数中…</span></li>\n'
    '              <li><span class="cc">webstats</span><span class="bar"><i style="width:0%"></i></span>'
    '<span data-ih-v="webstats">取数中…</span></li>\n'
    '              </ul>\n'
    '              <p class="attk-note" data-ih-note>取数中…</p>\n'
    '            </div>\n'
    '          </div>\n'
)
# ★V4（站主 2026-10-17："把该给访客看的重要数据做成可视化"）· 第三/四批：**部署时间轴 + 处置动作**。
#   数据源：/api/public/deploy.js（history[] 真发布记录）、/api/public/audit.js（actions[] 封禁/解封留痕）。
#   纪律同上：零新增配色/字体，只复用 .mod/.stats/.stat/.row/.k/.chip/.attk-note；
#   取不到写"读不到 + 原因"，端点没到保持骨架（不写"读不到"冒充缺失）。
def _tl_rows(n, tag):
    out = ''
    for i in range(n):
        out += ('                <div class="row xk-tl" data-tl="%s"><span class="k">—</span>'
                '<span>取数中…</span><span class="chip">—</span></div>\n' % tag)
    return out


VH_DEPLOY_MOD = (
    '          <div class="mod" data-xk-block="deploy"><div class="mod-hd"><span class="led"></span>部署可追溯 · 版本时间轴'
    '<span class="tag">/deploy</span></div>\n'
    '            <div class="mod-bd">\n'
    '              <div class="stats">\n'
    '                <div class="stat"><div class="n sk" data-vh-deploy="release">—</div><div class="l">当前版本</div></div>\n'
    '                <div class="stat"><div class="n sk" data-vh-deploy="built">—</div><div class="l">构建时刻</div></div>\n'
    '                <div class="stat"><div class="n sk" data-vh-deploy="files">—</div><div class="l">文件数</div></div>\n'
    '                <div class="stat"><div class="n sk" data-vh-deploy="bytes">—</div><div class="l">总体积</div></div>\n'
    '              </div>\n'
    '              <div data-vh-deploy-tl style="margin-top:12px">\n'
    + _tl_rows(8, 'deploy') +
    '              </div>\n'
    '              <p class="attk-note" data-vh-deploy-note>版本时间轴取自 /api/public/deploy 的 history（发布链真实产物，最近 8 次）；取不到写"读不到 + 原因"，不补样例值。</p>\n'
    '            </div>\n'
    '          </div>\n'
)
VH_OPS_MOD = (
    '          <div class="mod" data-xk-block="ops"><div class="mod-hd"><span class="led"></span>处置运维 · 处置动作'
    '<span class="tag">/audit · IP 已打码</span></div>\n'
    '            <div class="mod-bd">\n'
    '              <div data-vh-ops-tl>\n'
    + _tl_rows(8, 'ops') +
    '              </div>\n'
    '              <p class="attk-note" data-vh-ops-note>处置动作来自 /audit.actions（封禁/解封留痕，最近 8 条；IP 走打码口径）；取不到写"读不到 + 原因"，不补 0。</p>\n'
    '            </div>\n'
    '          </div>\n'
)
views_out = sub1(views_out,
                 '                <li><i class="lg ok"></i>—<b>—</b></li>\n'
                 '              </ul>\n'
                 '            </div>\n'
                 '          </div>\n',
                 '                <li><i class="lg ok"></i>—<b>—</b></li>\n'
                 '              </ul>\n'
                 '            </div>\n'
                 '          </div>\n' + API_HEALTH_MOD + VH_DEPLOY_MOD + VH_OPS_MOD,
                 'C2-P1: 接口健康模块（监测中心·真数据延迟条）+ V4 部署时间轴/处置动作')
views_out = sub1(views_out,
                 '<div class="chat-ft">',
                 '<div class="anchor-row ask-ex" id="askEx"></div>\n        <div class="chat-ft">',
                 'R2: AI 示例问题 chips 容器')
# 笔记分类 chips：卡头下加一行（构建期按 front-matter categories 去重输出），每条笔记带 data-cat
views_out = sub1(views_out,
                 '<span style="margin-left:auto;font-size:11px;color:var(--acc)">Hugo content</span></div>',
                 '<span style="margin-left:auto;font-size:11px;color:var(--acc)">Hugo content</span></div>\n'
                 '{{ if eq .page.Section "posts" }}{{ $cats := slice }}{{ range .page.Pages }}'
                 '{{ with .Params.categories }}{{ $cats = $cats | append . }}{{ end }}{{ end }}'
                 '{{ $cats = sort (uniq $cats) }}{{ if gt (len $cats) 0 }}'
                 '<div class="cat-row" id="catRow"><a href="#" class="on" data-cat="">全部</a>'
                 '{{ range $cats }}<a href="#" data-cat="{{ . }}">{{ . }}</a>{{ end }}</div>{{ end }}{{ end }}',
                 'R2: 笔记分类 chips 行')
views_out = sub1(views_out,
                 '{{ range .page.Pages }}<div class="note"><span class="dt">',
                 '{{ range .page.Pages }}<div class="note"{{ with .Params.categories }} data-cat="{{ delimit . "," }}"{{ end }}><span class="dt">',
                 'R2: 笔记条带 data-cat')

# ---- R2 收敛（2026-10-16 站主批）：**主页两处标记补丁已撤销，不再插入** ----
#   · CRT 真实事件行 `<div class="crt-feed" id="crtFeed">`：装饰性滚播；事件明细本来就在 /alerts/ 的实时流里，
#     它只抢注意力。对应 CSS 已从 R2_HOME_CSS 删除；api-bind.html 里写 #crtFeed 的绑定由站点线合并删除。
#   · 宽屏值班便签 `<aside class="desk-note" id="deskNote">`：数据由 api-bind.html:506-515 写入（非静态占位），
#     但它显示的三个数与 /alerts/ 大屏重复，属于"重复+抢注意力"。对应 CSS 已删。
#   ⚠️ 因此**站点线必须同步删掉 api-bind.html 里这两处绑定**（`#crtFeed` 在 :488 附近、`#deskNote` 在 :506-515），
#      否则元素不存在 → 写值抛错 → console 不再是 0（这是本批的硬验收）。
#   判据（站主原话）：更清楚 = 好，只是更花 = 删。这里删的是两件装饰，不动任何真实数据元素。

# ---- R2 汇入（样式 + 脚本）----
shell_style = shell_style + R2_CSS
home_style = home_style + R2_HOME_CSS
if not shell_scripts[0].rstrip().endswith('</script>'):
    raise SystemExit('R2: 外壳第一段 <script> 结构变了，交互层插入点失效')
shell_scripts[0] = shell_scripts[0].rstrip()[:-len('</script>')] + R2_JS + '\n</script>'
print('批次 R2：骨架/焦点/term暂停/donut SVG/tab hash/引用卡组/示例chips/笔记分类 已汇入；'
      '矩阵摘要已收敛进图例行；主页 CRT 事件行与值班便签已按站主批撤销')

# --------------------------------------------------------------------- 落盘
print('生成：')
home_style = home_style + LAYOUT_PATCH

# ---- ★场景机（站主 2026-10-16：主页"电视里她的随机动作"）----
#   A 模式 = 空实验室（裁掉图里 CRT 外框后）当底 + Sprite 状态机的她（动态）
#   B 模式 = 6 张场景静帧之一（喝咖啡/趴桌睡/电脑前/看CRT/站着想事/白板前）——图里她已在做那件事 ⇒ 把她淡出
#   素材：_ak/scene-crop 量出屏幕矩形 (153,260,1247,913)=1094×653，裁后转 webp 存
#         static/kurisu/scene/bg/screen_{empty,coffee,computer,crt,sleep,thinking,whiteboard}.webp
#   层级：.crt-clip>* 全部绝对定位满铺 ⇒ 场景层插在 .backplate 之后、#charCanvas 之前（她压在上面）
SCENE_CSS = u'''
  /* ★场景机：电视里她的"节目"在 A(空实验室+动态的她) 与 B(场景静帧) 之间随机轮换 */
  .xk-scene{object-fit:cover;opacity:0;transition:opacity .6s ease;pointer-events:none}
  .xk-scene.on{opacity:1}
  .charcanvas{transition:opacity .35s ease}
  .crt-clip.xk-scene-b .charcanvas{opacity:0}
  @media (prefers-reduced-motion:reduce){.xk-scene,.charcanvas{transition:none}}
  html.xk-no-kurisu .xk-scene{display:none}
'''
SCENE_ANCHOR = '      <img class="backplate" src="/images/crt/lab.webp" alt="" aria-hidden="true">'
SCENE_MARKUP = ('\n      <img class="xk-scene" id="xkSceneA" alt="" aria-hidden="true">'
                '\n      <img class="xk-scene" id="xkSceneB" alt="" aria-hidden="true">')
SCENE_JS = u'''
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
  var BASE = '/kurisu/scene/bg/screen_';
  var ACT = ['coffee','computer','crt','sleep','thinking','whiteboard'];
  var V = {on:true, mode:'A', cur:'empty', dwellMs:dwell, switches:[], pB:0.4};
  window.__xkScene = V;
  var front = A, back = B, timer = null;
  function show(img, name){ img.src = BASE + name + '.webp'; img.classList.add('on'); }
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
'''
home_style = home_style + SCENE_CSS
home_body = sub1(home_body, SCENE_ANCHOR, SCENE_ANCHOR + SCENE_MARKUP, '场景机: 两层场景图（backplate 之后、她之前）')
home_script = home_script + SCENE_JS
print('场景机：A=空实验室+动态的她 / B=6 场景静帧（dwell 45~60s、交叉淡入 600ms、?xk-scene=<ms> 旋钮）')

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
  {{- /* ★V3（2026-10-17）：极弱网省流模式。head 里同步引入（2KB），只为尽早判定（saveData/2g/3g
         或 ?xk-saver=1）并给 <html> 上 xk-saver 类；重活（不启动状态机/不取垫板）由它自己安排。 */}}
  <script src="/js/xk-saver.js"></script>
  {{- /* ★P0-④：首屏第一张（壁纸）preload + high —— 只这一张抢带宽，其余按顺序 decode */}}
  <link rel="preload" as="image" href="/images/crt/desk.webp" fetchpriority="high">
<style>%s
</style>
</head>
<body class="xk-has-idcard is-home">
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
# ★2026-10-16 恢复（站主报"背景哪去了 / 颜色也全变了"的根因）：
#   demo 外壳的**底图两层**（`docs/demo-内容页外壳.html:45/:46-47/:417`）在生产版里被整层剥掉，
#   只剩 `body{background:#0A0D11}`。而面板是**半透明暖玻璃**（`--panel: rgba(54,51,46,.24)`），
#   贴照片底才是"暖烟灰玻璃"观感，贴纯色就整页发暗 ⇒ 用户同时感到"背景没了 + 颜色全变了"。
#   调色板本身没变（逐项对比 demo vs 生产 `:root` = 16/16 一致）。
#   默认底图取 demo 的默认值 `room_empty`（源: `setBg(localStorage.getItem('xk-demo-bg4') || 'room_empty')`），
#   图已入库：`static/kurisu/scene/bg/room_empty.webp`（上游 scenarios/BG_empty.png 转换而来）。
BG_CSS = (
    u'\n  /* ★底图两层（逐字照 docs/demo-内容页外壳.html:45-47/:417）—— 内容页的暖玻璃面板需要照片底 */\n'
    u'  /*   ★2026-10-16 站主口径②：**不要 10 张背景切换器**；背景只放"人物不在的电视/书桌图"（desk.webp），\n'
    u'      人物在手机面板里（主页的她在 CRT 里）；光束保留、做成左上角头像旁的小按钮；配色切换器不要（用现有暖色）。 */\n'
    u'  .bg{position:fixed;inset:0;z-index:-3;background:#0A0D11 center/cover no-repeat;'
    u'background-image:url(/kurisu/scene/bg/room_empty.webp);transform:scale(1.1)}\n'
    u'  /*   ★2026-10-17 站主口径（改）：背景照旧演示文件 `docs/demo-内容页外壳.html` 的默认值 room_empty（空实验室），\n'
    u'      不要 desk.webp —— 书桌图留给主页（主页的她在 CRT 里），内容页用"人物不在的房间"才是旧演示的观感。*/\n'
    u'  /*  光束层：默认关，`<html class="xk-lite">` 时淡入（左上角 ✨ 按钮切，localStorage 记忆） */\n'
    u'  .bglite{position:fixed;inset:0;z-index:-2;pointer-events:none;opacity:0;transition:opacity .45s ease;'
    u'background:center/cover no-repeat url(/kurisu/scene/bg/light_high.webp)}\n'
    u'  html.xk-lite .bglite{opacity:.5}\n'
    u'  @media (prefers-reduced-motion:reduce){.bglite{transition:none}}\n'
    u'  .bgshade{position:fixed;inset:0;z-index:-1;'
    u'background:linear-gradient(180deg,rgba(8,10,14,var(--shade)),rgba(8,10,14,var(--shade)))}\n'
    u'  body.is-home .bg,body.is-home .bgshade,body.is-home .bglite{display:none}\n'
)
shell_style = shell_style + BG_CSS
#   底图两层的 DOM：写在 chrome 最前面（demo 里就是 body 后第一件事）
BG_DOM = (
    u'<!-- ★底图两层（恢复自 docs/demo-内容页外壳.html:427 + :45-47）：内容页的暖玻璃面板需要照片底 -->\n'
    u'<div class="bg" aria-hidden="true"></div>\n'
    u'<div class="bglite" aria-hidden="true"></div>\n'
    u'<div class="bgshade" aria-hidden="true"></div>\n'
)
if u'.bgshade' not in chrome:
    chrome = BG_DOM + chrome

# ==================== ★P2（站主口径：/test/ 的数据要"安置"成正经可视化）· AI 页 tab ====================
# 归属：知识库 → `/ai/` 新增 tab「知识库」；AI 质量 → `/ai/` 新增 tab「AI 质量」（数据源等后端 `/api/public/eval.js`）
# 零新增 CSS：复用监测中心的 `.ops-tabs` / `.ops-tab`（该页本来就有这套 tab 样式）
# ⚠️ 与监测中心的 `[data-pane]` 隔离：这里用 `data-aitab`，并自带点击处理（api-bind 的 bindAiTabs）
AI_TABS = (
    u'   <nav class="ops-tabs" id="aiTabs" role="tablist" aria-label="AI 问答分区">\n'
    u'     <div class="ops-tab on" data-aitab="chat" role="tab" tabindex="0">问答</div>\n'
    u'     <div class="ops-tab" data-aitab="kb" role="tab" tabindex="0">知识库</div>\n'
    u'     <div class="ops-tab" data-aitab="eval" role="tab" tabindex="0">AI 质量</div>\n'
    u'   </nav>\n'
)
# AI 质量卡：**先落骨架 + 如实写"读不到"**（后端端点未到之前不许编数）。指标口径与 scripts/eval 一致。
AI_EVAL_CARD = (
    u'      <div class="card" data-xk-block="eval" style="display:none">\n'
    u'        <div class="card-hd"><span class="led"></span>AI 质量 · 评测指标'
    u'<span style="margin-left:auto;font-size:11px;color:var(--acc)">scripts/eval · 96 题</span></div>\n'
    u'        <div class="stats" style="padding:14px 15px 4px">\n'
    u'          <div class="stat"><div class="n sk" data-eval="hit">—</div><div class="l">要点命中率</div></div>\n'
    u'          <div class="stat"><div class="n sk" data-eval="refuse">—</div><div class="l">拒答正确率</div></div>\n'
    u'          <div class="stat"><div class="n sk" data-eval="strict">—</div><div class="l">严格口径通过</div></div>\n'
    u'          <div class="stat"><div class="n sk" data-eval="cite">—</div><div class="l">引用率</div></div>\n'
    u'        </div>\n'
    u'        <p class="attk-note" data-eval-note style="padding:0 15px 14px">读不到：评测端点还没上线（后端线待补）。'
    u'真值来自仓库 <code>scripts/eval</code> 的 96 题批次，<b>前端不编数</b>；端点上线后由它写这四格。'
    u'<span style="color:var(--mut)">（本卡在端点到齐前不伪装成数字）</span></p>\n'
    u'      </div>\n'
)
views_out = sub1(views_out, u'<div class="ai-grid">', AI_TABS + u'<div class="ai-grid">', 'P2: AI 页 tab 条')
views_out = sub1(views_out, u'<div class="card" data-xk-block="kb"', AI_EVAL_CARD + u'      <div class="card" data-xk-block="kb"',
                 'P2: AI 质量占位卡（读不到态）')
# P2：知识库结果下方加"来源类型分布条"容器（真值由 renderKb 按 results[].sourceType 聚合写；零新 CSS，复用 ul.geo）
views_out = sub1(views_out, u'<div data-kb-out></div>', u'<div data-kb-out></div>\n        <div data-kb-src></div>',
                 'P2: 知识库来源分布容器')

# ==================== ★P0（站主 2026-10-16）：内容页右列整体换成「手机」 ====================
# 站主原话（配箭头截图）："剩下的页面右边全变成手机，放一个助手"。
# 保守做法（不新起第二套 UI）：
#   ① 原本埋在 `v-ai` 视图里的 <aside class="phone"> 整块**移出视图**，插进页面级 chrome（与 .holo 同级同位置）
#   ② `.holo` 不再显示（**保留 DOM 与 JS**，避免 holoFold/holoBubble 报错）⇒ 右列不再两张脸
#   ③ 主页隐藏手机（body.is-home；与主窗口 .bg 那条同口径）
#   ④ 宽度：`.phone` 自身 292px ≤ 320（三栏 300/1fr/320 红线不回归）；**窄屏 ≤980px 整块隐藏**（保守，
#      理由：手机框在手机上会压住正文；既有 `.holo` 在窄屏是"收成头像泡"，手机不做泡泡版，直接隐藏）
#   ⑤ 手机屏幕里的助手 132×132 → **264×336**（屏幕宽 292-2×12=268，放得下），素材仍用现有 /kurisu/full/*
#   ⑥ 按钮（站主要过）：名字 + 🔊/🔇 + 💬 说一句 + 🙂 换动作 + ⚙️ 动画开关，全部放在手机框内底部
PHONE_MOD = (
    u'<!-- ★P8-A（站主 2026-10-16）：手机 = 页面级右列常驻件（替掉 .holo）；外壳 300×618（1:2.06） -->\n'
    u'<aside class="phone live" id="phone" aria-label="手机里的桐莉栖">\n'
    u'  <div class="phone-scr">\n'
    u'    <div class="phone-island" aria-hidden="true"></div>\n'
    u'    <div class="phone-bar"><span id="phoneClock">—</span><span id="phoneName">桐莉栖</span>'
    u'<span>HOLO-LINK · 5G ▮▮▮</span></div>\n'
    u'    <div class="phone-glare" aria-hidden="true"></div>\n'
    u'    <!-- 渲染源由 phone-emote.js 接管（E-mote）；未接管时是 Sprite 三段降级。'
    u'⚠ 这里**故意不写 width/height 属性**（内部分辨率由渲染源自定：Sprite 会自己设 321×432）。 -->\n'
    u'    <canvas id="phoneCanvas" aria-hidden="true"></canvas>\n'
    u'    <script src="/js/phone-emote.js" defer></script>\n'
    u'    <div class="phone-cap"><span id="phoneLine">问点什么吧，我在这边听着。</span></div>\n'
    u'    <div class="phone-live">\n'
    u'      <div class="bars2"><i></i><i></i><i></i><i></i><i></i></div>\n'
    u'      <span id="phoneState">IDLE</span>\n'
    u'    </div>\n'
    u'    <div class="phone-btns">\n'
    u'      <button id="phSnd" type="button" aria-label="声音开关" title="声音开关（与头像卡同源）">🔊</button>\n'
    u'      <button id="phSay" type="button" aria-label="让她说一句" title="让她说一句">💬</button>\n'
    u'      <button id="phMood" type="button" aria-label="换个动作" title="换个动作">🙂</button>\n'
    u'      <button id="phAnim" type="button" aria-label="动画开关" title="动画开关">⚙️</button>\n'
    u'    </div>\n'
    u'    <div class="phone-home" aria-hidden="true"></div>\n'
    u'  </div>\n'
    u'</aside>\n'
)
# ★P8-A（站主 2026-10-16，主窗口批准"两全方案"）：
#   · 外壳：宽 300 / 高 618（1:2.06）/ right:20 + 垂直居中（屏高<820px 改 top:84;bottom:84 自适应）
#   · 画布：**默认（Sprite 降级）`height:100%;width:auto;margin:0 auto`** ⇒ 保持素材 1:1.346 不变形；
#           **E-mote 接管时**由 phone-emote.js 给 <html> 加 `xk-phone-emote` ⇒ 那时才 100%×100% 铺满。
#    为什么不做恒铺满：Sprite 内部尺寸 321×432(1:1.346) 铺进 1:2.11 屏会被纵向拉长 1.57×（实测帧几何见施工文档）
PHONE_CSS = (
    u'\n/* ★P8-A（站主 2026-10-16）：内容页右列 = 手机（替掉 .holo）；主页无手机 */\n'
    u'#holo{display:none !important}                 /* 只隐藏，不删：holoFold/holoBubble 的 JS 仍在跑 */\n'
    u'body.is-home .phone{display:none}\n'
    u'.phone{position:fixed;right:20px;top:50%;transform:translateY(-50%);z-index:55;\n'
    u'  width:min(300px,44vh);height:auto;padding:8px;border-radius:34px;\n'
    u'  background:linear-gradient(160deg,#2b3138,#0c0f13 55%,#23272d);\n'
    u'  border:1px solid rgba(255,255,255,.16);\n'
    u'  box-shadow:inset 0 0 0 1px rgba(255,255,255,.07),inset 0 3px 12px rgba(0,0,0,.65),0 18px 44px rgba(0,0,0,.5)}\n'
    u'.phone-scr{position:relative;width:100%;aspect-ratio:284/600;border-radius:26px;overflow:hidden;\n'
    u'  background:#07090c url(/kurisu/full/idle.poster.webp) center bottom/contain no-repeat}\n'
    u'/* 默认（Sprite 降级）：**以宽为准**保比例 + 底部锚点（脚底距屏底 150px，给字幕/按钮让位）。'
    u'不用 height:100% 的原因：帧 321×432 ⇒ 高 600 时宽会变 446 > 屏 284，两侧会被裁。 */\n'
    u'#phoneCanvas{position:absolute;left:50%;bottom:150px;transform:translateX(-50%);width:100%;height:auto;display:block}\n'
    u'html.xk-phone-emote #phoneCanvas{left:0;top:0;bottom:auto;transform:none;width:100%;height:100%}\n'
    u'/* E-mote 接管后必须撤掉静态立绘垫底，否则会和 E-mote 人物叠成两个（线上实际出现过：上 E-mote、下 poster）；\n'
    u'   但**只在 ready 之后**撤：加载期还靠这张垫底撑画面，否则手机是空屏 */\n'
    u'html.xk-phone-emote.xk-emote-ready .phone-scr{background-image:none}\n'
    u'/* 灵动岛 / 状态栏 / 斜向反光 / Home 条 */\n'
    u'.phone-island{position:absolute;left:50%;top:8px;transform:translateX(-50%);width:88px;height:24px;border-radius:14px;background:#000;z-index:5}\n'
    u'.phone-bar{position:absolute;left:0;right:0;top:0;display:flex;justify-content:space-between;align-items:center;\n'
    u'  font:10.5px var(--mono);color:var(--mut);padding:10px 14px 0;z-index:6}\n'
    u'.phone-bar #phoneName{color:var(--acc);letter-spacing:.04em}\n'
    u'.phone-glare{position:absolute;inset:0;pointer-events:none;z-index:4;\n'
    u'  background:linear-gradient(115deg,rgba(255,255,255,.10) 0%,rgba(255,255,255,0) 38%)}\n'
    u'.phone-home{position:absolute;left:50%;bottom:6px;transform:translateX(-50%);width:104px;height:4px;border-radius:2px;background:rgba(255,255,255,.35);z-index:6}\n'
    u'/* 屏底两行字幕（半透明黑底白字） */\n'
    u'.phone-cap{position:absolute;left:0;right:0;bottom:108px;padding:0 14px;z-index:6}\n'
    u'.phone-cap span{display:block;font:12.5px/1.5 var(--sans);color:#fff;background:rgba(0,0,0,.55);\n'
    u'  border-radius:8px;padding:4px 8px;max-height:3em;overflow:hidden}\n'
    u'.phone-live{position:absolute;left:0;right:0;bottom:86px;display:flex;align-items:center;gap:8px;\n'
    u'  justify-content:center;z-index:6;font:10.5px var(--mono);color:var(--mut)}\n'
    u'/* 屏底玻璃胶囊按钮行（4×44 圆） */\n'
    u'.phone-btns{position:absolute;left:0;right:0;bottom:16px;display:flex;gap:8px;justify-content:center;z-index:7}\n'
    u'.phone-btns button{width:44px;height:44px;border-radius:50%;font:17px var(--sans);color:var(--txt);cursor:pointer;\n'
    u'  background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);backdrop-filter:blur(6px)}\n'
    u'.phone-btns button:hover,.phone-btns button:active{color:var(--acc);border-color:var(--acc);background:rgba(127,212,216,.14)}\n'
    u'.phone-btns button.off{opacity:.45}\n'
    u'.phone-btns button.lit{box-shadow:0 0 12px rgba(127,212,216,.65);border-color:var(--acc)}\n'
    u'/* 窄屏（<980px）：不再整块隐藏——默认只出一条**竖直静态立绘**（不加载 E-mote/WebGL），点一下放大。\n'
    u'   理由：手机上 E-mote 要跑 WebGL 模型（内存/耗电），但"完全看不见她"也不符合站点气质。 */\n'
    u'@media (max-width:980px){\n'
    u'  .phone{display:block;right:8px;bottom:8px;top:auto;transform:none;width:74px;padding:4px;\n'
    u'    border-radius:16px;opacity:.94;transition:width .18s ease,right .18s ease}\n'
    u'  .phone .phone-scr{aspect-ratio:284/600;border-radius:12px;background-size:cover;background-position:center top;background-color:#07090c}\n'
    u'  .phone #phoneCanvas{display:none!important}\n'
    u'  .phone .phone-bar,.phone .phone-island,.phone .phone-cap,.phone .phone-live,.phone .phone-btns,.phone .phone-home{display:none!important}\n'
    u'  html.xk-phone-open .phone{right:50%;bottom:50%;transform:translate(50%,50%);width:min(76vw,38vh);z-index:80;\n'
    u'    border-radius:30px;padding:8px;opacity:1;box-shadow:0 0 0 100vmax rgba(4,7,10,.74),0 24px 64px rgba(0,0,0,.6)}\n'
    u'  html.xk-phone-open .phone .phone-bar{display:flex!important}\n'
    u'  html.xk-phone-open .phone .phone-cap,html.xk-phone-open .phone .phone-live{display:block!important}\n'
    u'}\n'
)
views_out = re.sub(r'\n\s*<!-- 手机里的她.*?</aside>', '', views_out, flags=re.S)          # ① 移出 v-ai，避免重复 id
shell_style = shell_style + PHONE_CSS                                                       # ④⑤⑥ 定位/宽度/按钮样式
chrome = sub1(chrome, u'<div class="holo-bubble"', PHONE_MOD + u'<div class="holo-bubble"', 'P0: 手机进页面级右列')

# ⑦ 手机功能按钮（名字已写进 PHONE_MOD；这里接行为）—— **全部复用既有 speak()/setPhone()/render()/emo**，
#   不新起一套状态机。保守点写清楚：
#     · 🔊/🔇 = 代理点击头像卡的 `#xkSndBtn`（同源状态，避免两处各记一份），并每 1.5s 同步图标
#     · 💬     = 走既有 `speak(text)`（手机台词位 + STATE=SPEAKING）；**原声**需语音播放器在场，
#                故再尝试 `window.__xkSay`（存在才调），不存在只出文本（如实，不假装出声）
#     · 🙂     = 在 idle ↔ thinking 之间轮换（手机只有 full/{idle,thinking,speaking} 三档素材；
#                真情绪需把 avatar 素材接进手机，见回报）
#     · ⚙️     = `window.__xkPhoneAnim=false` 冻结渲染循环（下方 tick 认这个开关），再点恢复
_PHONE_UI_JS = u'''
/* ★P0（站主 2026-10-16）：手机里的助手 —— 功能按钮 */
(function(){
  var $=function(i){ return document.getElementById(i); };
  var snd=$('phSnd'), say=$('phSay'), mood=$('phMood'), anim=$('phAnim');
  var MOODS=['normal','sided_thinking'], mi=0;
  function soundOn(){ return !(window.__xkSound && window.__xkSound.on === false); }
  function syncSnd(){ if(!snd) return; snd.textContent = soundOn() ? '\U0001F50A' : '\U0001F507'; snd.className = soundOn() ? '' : 'off'; }
  if(snd){ snd.onclick=function(){ var b=document.getElementById('xkSndBtn'); if(b){ b.click(); } setTimeout(syncSnd,60); }; syncSnd(); setInterval(syncSnd,1500); }
  if(say){ say.onclick=function(){
    var txt='嗯——我在。你想问什么？';
    try { if(typeof window.__xkSay === 'function') { window.__xkSay(); } } catch(e){}
    try { speak(txt); } catch(e){}
  }; }
  if(mood){ mood.onclick=function(){ mi=(mi+1)%MOODS.length; try { emo=MOODS[mi]; setPhone(); render(); } catch(e){} }; }
  if(anim){ anim.onclick=function(){ window.__xkPhoneAnim = (window.__xkPhoneAnim === false); anim.className = (window.__xkPhoneAnim === false) ? 'off' : ''; }; }
})();
'''
shell_scripts[0] = sub1(shell_scripts[0], u'tickClock(); setInterval(tickClock, 20000);',
                        u'tickClock(); setInterval(tickClock, 20000);' + _PHONE_UI_JS, 'P0: 手机按钮接线')
shell_scripts[0] = sub1(shell_scripts[0], u'if(cur && frames > 1 && !RM && t - last > iv)',
                        u'if(cur && frames > 1 && !RM && window.__xkPhoneAnim !== false && t - last > iv)',
                        'P0: 手机动画开关（渲染循环认它）')

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
  {{- /* ★V3（2026-10-17）：极弱网省流模式。head 里同步引入（2KB），只为尽早判定（saveData/2g/3g
         或 ?xk-saver=1）并给 <html> 上 xk-saver 类；重活（不启动状态机/不取垫板）由它自己安排。 */}}
  <script src="/js/xk-saver.js"></script>
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
