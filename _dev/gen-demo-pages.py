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
'''

# 主页脚本里的路径也要改（CLIPS 表）
home_script = rewrite_assets(home_script)
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
    '<nav class="dock" id="dock" aria-label="站点导航（演示）">\n'
    '  <div class="brand">XK-LAB</div>\n'
    '  <a href="/" class="on">主页</a>\n'
    '  <a href="/alerts/">监测中心</a>\n'
    '  <a href="/ai/">AI 问答</a>\n'
    '  <a href="/posts/">笔记</a>\n'
    '  <a href="/labs/">靶场</a>\n'
    '  <a href="/about/">关于</a>\n'
    '</nav>')
NAVPILL_CSS = (
    '  /* 屏外：导航浮条 */\n'
    '  .navpill{position:fixed;top:16px;left:16px;z-index:60;display:flex;gap:2px;\n'
    '    background:rgba(11,17,24,.82);border:1px solid rgba(120,200,220,.35);border-radius:99px;\n'
    '    padding:4px;backdrop-filter:blur(8px)}\n'
    '  .navpill a{font:12.5px var(--sans);color:#8CA3B8;text-decoration:none;padding:5px 12px;border-radius:99px}\n'
    '  .navpill a.on{color:#39D0D8;background:rgba(57,208,216,.1)}\n')
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
    '\n'
    '  @media (max-width:980px){\n'
    '    .dock{left:8px;top:auto;bottom:10px;transform:none;flex-direction:row;max-width:calc(100vw - 16px);overflow-x:auto}\n'
    '    .dock .brand{display:none}\n'
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
    ('  phoneBody.set(BODY[mode === \'speaking\' ? \'speaking\' : (emo === \'sided_thinking\' ? \'thinking\' : \'idle\')]);',
     "  if(document.getElementById('v-ai').classList.contains('on')) phoneBody.set(BODY[mode === 'speaking' ? 'speaking' : (emo === 'sided_thinking' ? 'thinking' : 'idle')]);",
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

# ---- ② HOLO 面板那句话：先清掉假数字（api-bind 会重写这句话，仍是"原元素"）----
chrome = sub1(
    chrome,
    '过去 24 小时拦截了 <span class="qk">96 次</span> 暴力破解，蜜罐记录了 <span class="qk">37 条</span> 交互。都在「监测中心」的大屏里。',
    '公开只读端点汇总：护栏拦下 <span class="qk">—</span> 个动作，蜜罐累计事件 <span class="qk">—</span> 条。明细都在「监测中心」的大屏里。',
    'chrome: holo-say 假数字')

# ---- ⑤ demo 自身缺陷：五页的 scene-js 依赖不存在的 #fallback / #bootveil ----
# 【2026-10-14 第十二批 · 站主砍范围】这条**本轮不做**，原样保留 demo 的行为。
#   为什么不能顺手修：五个内容页的 scene-js 现在会在启动处抛 TypeError 提前中止，
#   于是「opening.hi.webp（1004KB）」根本没被请求；一旦补上存在性判断让 IIFE 跑完，
#   五页都会去载 opening.hi，/ai/ 的首屏从 1637KB 直接涨到 2640KB —— 首屏门禁（≤1650KB）立刻红。
#   所以它与首屏预算是**耦合**的，留给下一批连同 /ai/ 的图集一起处理。
#   （补丁文本保留在这里，下一批打开即可；本轮不应用。）
S_FALLBACK_OLD = "document.getElementById('fallback').style.display = r.height < 260 ? 'grid' : 'none';"
S_FALLBACK_NEW = ("const fb = document.getElementById('fallback');   /* ★第十二批：五个内容页没有 #fallback，\n"
                  "      demo 这里直接 .style 会抛 TypeError 让整个 IIFE 中止 —— 加存在性判断，行为不变 */\n"
                  "  if(fb) fb.style.display = r.height < 260 ? 'grid' : 'none';")
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
    "  monitor:'公开只读端点的实时汇总都在这一屏；取不到就写读不到，不补数。',",
    'shell: SAYS.monitor 假数字')
shell_scripts[0] = sc

# --------------------------------------------------------------------- 落盘
print('生成：')

# 1) 共享头
write(os.path.join(PART, 'head-meta.html'), HEAD_META)

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
     ③ 链接是站点真路由（/ · /alerts/ · /posts/ · /labs/ · /ai/ · /about/）
        （不是 demo 的 `<button data-v>`，也不走 `/#/…` hash：这一页不挂站点 SPA 的 app.js）
   不搬的：站点 SPA 外层（app.js / 侧栏 / 顶行 / 输入条 / 页脚 / 搜索层）、kurisu-player.js、
   状态机/语音/口型 —— 站主明确要求这些**不要**进这一页。
   保留的不可见契约：Hugo <head>（标题/描述/canonical/OG/favicon）+ <main id="content"
   data-xk-ssr="home">（SPA 契约断言读它）+ #xk-views 占位。
   重现方式：python _dev/gen-demo-pages.py
   ============================================================================ */ -}}
<!DOCTYPE html>
<html lang="{{ site.Language.Lang | default `zh-CN` }}">
<head>
{{ partial "xk-demo/head-meta.html" . }}
<style>%s
</style>
</head>
<body>
{{- /* ↓↓↓ 以下到 </main> 为止 = docs/demo-主页.html 的 body 逐字（仅素材路径与导航 href 如上） */}}
<main id="content" data-xk-ssr="home">
%s
</main>
<div id="xk-views" hidden aria-hidden="true"></div>
<script>
%s
</script>
{{ partial "xk-demo/api-bind.html" . }}
</body>
</html>
''' % (home_style, home_body, home_script))

# 3) 外壳共享片段
write(os.path.join(PART, 'shell-style.html'),
      u'{{- /* docs/demo-内容页外壳.html 的 <style> 逐字（第 7–398 行）+ 一条 <a> 伴随规则 */ -}}\n'
      u'<style>%s%s</style>\n' % (shell_style, DOCK_A_CSS))
write(os.path.join(PART, 'shell-chrome.html'),
      u'{{- /* 外壳常驻件（逐字）：底图两层 / demo 标识条 / 左侧 .dock / HOLO 面板 / 背景选择器。\n'
      u'      唯一改动：.dock 的 <button data-v> → <a href="站点真路由">（样式值逐字，见 shell-style）。 */ -}}\n'
      u'{{- $v := .v -}}\n%s\n' % chrome)
write(os.path.join(PART, 'shell-views.html'),
      u'{{- /* 六屏 <section class="view"> 逐字；只有哪一屏带 .on 由参数 v 决定 */ -}}\n'
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
    ('labs', 'range', '靶场'),
    ('about', 'about', '关于'),
    ('ai', 'ai', 'AI 问答'),
]
# content/about/_index.md 的 front matter 写着 layout: "single"（Hugo 只认 <type>/single.html），
# 所以这一页要多落一份同样的模板，否则会落回老的 _default/single.html（实测踩过）。
ALSO_SINGLE = {'about'}
for section, view, cname in PAGES:
    body_class = u'{{ if eq $v "home" }} class="is-home"{{ else if eq $v "ai" }} class="is-ai"{{ end }}'
    tpl = u'''{{- /* ============================================================================
   /%s/ = `docs/demo-内容页外壳.html` 的 `v-%s`（%s）那一屏**整份搬**（第四批口径）。
   ----------------------------------------------------------------------------
   搬过来的：外壳的 <style> 逐字、常驻件（底图/dock/HOLO/背景选择器）逐字、
   六屏标记逐字、两段内联 <script> 逐字；本页初始 .on 落在 v-%s。
   只改两处：① 素材路径 → static/ 真文件 ② dock 的 <button data-v> → <a href="真路由">
   不动：站点的 SPA 外层 / kurisu-player / 状态机 / 语音 / 口型。
   保留的不可见契约：Hugo <head> + <main id="content" data-xk-ssr="%s"> + #xk-views 占位。
   重现方式：python _dev/gen-demo-pages.py
   ============================================================================ */ -}}
{{- $v := "%s" -}}
<!DOCTYPE html>
<html lang="{{ site.Language.Lang | default `zh-CN` }}">
<head>
{{ partial "xk-demo/head-meta.html" . }}
{{ partial "xk-demo/shell-style.html" . }}
</head>
<body data-skin="warm"%s>
{{ partial "xk-demo/shell-chrome.html" (dict "v" $v) }}
<main class="main" id="content" data-xk-ssr="%s">
{{ partial "xk-demo/shell-views.html" (dict "v" $v) }}
</main>
<div id="xk-views" hidden aria-hidden="true"></div>
{{ partial "xk-demo/shell-script.html" . }}
{{ partial "xk-demo/api-bind.html" . }}
</body>
</html>
''' % (section, view, cname, view, view, view, body_class, view)
    write(os.path.join(ROOT, 'layouts', section, 'list.html'), tpl)
    if section in ALSO_SINGLE:
        write(os.path.join(ROOT, 'layouts', section, 'single.html'), tpl)

print('\n完成。')
