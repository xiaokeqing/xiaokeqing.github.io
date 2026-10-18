#!/usr/bin/env bash
# ============================================================
# 博客构建产物断言（CI 发布前的最后一道闸）
# ------------------------------------------------------------
# 用法：bash scripts/assert-build.sh [构建产物目录]     默认 public
# 退出码：0 = 全部通过；1 = 有任一断言不通过（CI 里就意味着【不发布】）
#
# 为什么要在"构建成功"之后再断言一遍：
#   Hugo 构建成功 ≠ 发布出去的站点是对的。这个仓库真实发生过：
#   改了页面、本地看着没问题、但产物里带着 localhost 或漏了 CNAME
#   —— 这类问题在 CI 日志里完全看不出来（Hugo 只报 "built in 300ms"），
#   等发现时已经发布到线上、或者（更常见）根本没发布出去而没人察觉。
#   所以这里把"产物必须长什么样"变成硬断言，失败即拦截。
#
# 断言清单（每条都对应一种真实翻车方式）：
#   ① 产物非空                     —— 构建参数写错/输出目录搞错时，
#                                     Hugo 会"成功"地产出一个空目录
#   ② index.html 存在且非空         —— 首页模板缺失时其余页面照生成
#   ③ CNAME 内容 = xiaokeqing.cn    —— 漏了它 GitHub Pages 会解绑自定义域名
#   ④ sitemap.xml 存在且含 baseURL  —— 站点地图缺失/基址写错（比如写成本地）
#   ⑤ 全站不得出现 localhost        —— 最常见的是接口基址回退成开发机地址，
#                                    线上页面会去请求用户自己的 localhost
#   ⑥ 全站不得出现 /api/public/latest
#                                  —— 已下线的死端点。留着的引用会让页面
#                                    每次加载都对一个 404 发一次请求
#   （⑥ 的现状见交付说明：站点的「关于」页把它当作"未上线端点"在探测，
#     所以这条断言目前会红 —— 这是刻意不放开，具体取舍写在该说明里。）
# ============================================================
set -uo pipefail

PUB=${1:-public}
PASS=0
FAIL=0

ok()   { PASS=$((PASS + 1)); printf '  \033[1;32m[PASS]\033[0m %s\n' "$*"; }
no()   { FAIL=$((FAIL + 1)); printf '  \033[1;31m[FAIL]\033[0m %s\n' "$*"; }
warn() { printf "  \033[1;33m[WARN]\033[0m %s\n" "$*"; }
head1() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

# 只扫文本文件：-I 让 grep 跳过二进制（png/jpg/woff），
# 否则"在图片里搜到 localhost"会变成随机的假失败。
scan() { grep -rIl --exclude-dir=./.git -e "$1" "$PUB" 2>/dev/null; }

echo "构建产物断言：$PUB"
[ -d "$PUB" ] || { echo "错误：找不到目录 $PUB"; exit 1; }
echo "文件数：$(find "$PUB" -type f | wc -l | tr -d ' ')"

# ---------- ① 产物非空 ----------
head1 "① 产物非空（>= 20 个文件）"
NF=$(find "$PUB" -type f | wc -l | tr -d ' ')
if [ "$NF" -ge 20 ]; then
  ok "产物有 $NF 个文件"
else
  no "产物只有 $NF 个文件 —— 构建参数错误时 Hugo 会「成功」产出空目录"
fi

# ---------- ② index.html ----------
head1 "② index.html 存在且非空"
if [ -s "$PUB/index.html" ]; then
  ok "index.html 存在（$(stat -c %s "$PUB/index.html") 字节）"
else
  no "index.html 不存在或为空"
fi

# ---------- ③ CNAME ----------
head1 "③ CNAME 内容必须是 xiaokeqing.cn"
if [ -f "$PUB/CNAME" ]; then
  CN=$(tr -d '[:space:]' < "$PUB/CNAME")
  if [ "$CN" = "xiaokeqing.cn" ]; then
    ok "CNAME = $CN"
  else
    no "CNAME 内容不对：'$CN'（期望 xiaokeqing.cn）—— 错了会解绑自定义域名"
  fi
else
  no "缺 $PUB/CNAME —— static/CNAME 没被构建进产物"
fi

# ---------- ④ sitemap.xml ----------
head1 "④ sitemap.xml 存在、非空、且基址正确"
if [ -s "$PUB/sitemap.xml" ]; then
  if grep -q '<urlset' "$PUB/sitemap.xml"; then
    ok "sitemap.xml 存在且是合法 urlset"
  else
    no "sitemap.xml 缺少 <urlset（内容不像站点地图）"
  fi
  if grep -q 'https://xiaokeqing.cn/' "$PUB/sitemap.xml"; then
    ok "sitemap.xml 里的基址是 https://xiaokeqing.cn/"
  else
    no "sitemap.xml 里没有 https://xiaokeqing.cn/ —— baseURL 配错了（换域名/本地构建都会这样）"
  fi
else
  no "缺 $PUB/sitemap.xml（hugo.toml 的 sitemap 输出被关掉了？）"
fi

# ---------- ⑤ 不得出现 localhost ----------
head1 "⑤ 全站不得出现 localhost"
HITS=$(scan 'localhost' | head -20)
if [ -z "$HITS" ]; then
  ok "没有任何文件包含 localhost"
else
  no "有文件包含 localhost（线上会让用户去请求他自己的本机）："
  printf '%s\n' "$HITS" | sed 's/^/        /'
  printf '%s\n' "$HITS" | head -3 | while IFS= read -r f; do
    grep -n -m2 -e 'localhost' "$f" | sed "s|^|        $(printf '%s' "$f") :|"
  done
fi

# ---------- ⑥ 产物里出现的 /api/public/* 必须都在"已上线白名单"里 ----------
# 【2026-10-14 改】原来这条写死"不得出现 /api/public/latest"，前提是它当时已下线。
# 但该端点后来上线了（线上实测 200 + available=true），而「关于」页写的是**正确的文档**
# ——"③ /api/public/latest 已上线：返回窗口聚合"——于是断言把正确文档当成死端点拦下，
# 导致第十一轮整轮发布被拒（gh-pages 未更新）。教训：断言不要绑定"某个端点当前是死是活"
# 这种会过期的前提，而应断言"所有出现的端点都必须在白名单里"。
head1 "⑥ 产物里的公开端点必须全部属于已上线白名单"
# 白名单 = 线上实测能返回 200 的公开端点。**新增端点必须先在线上实测，再手动加进来。**
# 【2026-10-14 补】tts / stories / story 是**预登记**：L2 动态语音（/api/public/tts，没 Key 时是
# 设计关闭态 503）与故事线（/api/public/stories）都在公开面文档里写着，属于"会存在的端点"。
# 预登记不会让断言变松 —— 只有页面真的引用它时这条才起作用，而那时它确实是个存在的端点。
# 【2026-10-16 补】home / deploy / eval 是**新上线的公开端点**（线上实测 200，CORS=*、max-age=45/ETag 与别名同口径）：
#   · /api/public/home.js   = alerts+geo+honeypot 三合一聚合（首屏 3 请求 → 1）
#   · /api/public/deploy.js = 部署可追溯（当前 available:false + RELEASE_INFO_NOT_CONFIGURED —— 后端待配 release-info 文件）
#   · /api/public/eval.js   = AI 质量报告（当前 available:false + EVAL_REPORT_NOT_CONFIGURED —— 后端待配评测报告文件路径）
#   ★三者都遵守"取不到不编数"：available:false + reason，页面据此如实写"读不到"。
ALLOWED="ask kb overview alerts latest honeypot audit geo webstats tts stories story home deploy eval ip"
FOUND=$(grep -rhoE '/api/public/[a-zA-Z0-9_-]+' "$PUB" 2>/dev/null | sed 's|/api/public/||' | sort -u | tr '\n' ' ')
BAD=""
for e in $FOUND; do
  case " $ALLOWED " in *" $e "*) ;; *) BAD="$BAD $e" ;; esac
done
if [ -z "$BAD" ]; then
  ok "产物里出现的端点全部在白名单内（$(echo $FOUND | wc -w) 个：$(echo $FOUND | sed 's/ $//')）"
else
  no "产物里出现白名单外的 /api/public/* 端点（可能是死端点或拼写错误）：$BAD"
  for e in $BAD; do
    grep -rl -- "/api/public/$e" "$PUB" 2>/dev/null | head -3 | sed 's/^/        /'
  done
  echo "        → 该端点若确实已上线：线上实测 200 后，把它加进本脚本的 ALLOWED；"
  echo "          若已下线：删掉引用（否则每次加载都会打一个 404）。"
fi

# ---------- ⑦ 零第三方资源引用（只查"资源"，不查正文里的文字链接）----------
head1 "⑦ 产物里不得有第三方资源引用（src / link href / CSS url()）"
EXT=$(grep -rlE 'src="https?://|src='"'"'https?://|<link[^>]+href="https?://|url\(https?://' "$PUB" 2>/dev/null | grep -vE 'xiaokeqing' | head -5)
if [ -z "$EXT" ]; then ok "无第三方资源引用（正文里的文字链接不算）"; else
  no "发现第三方资源引用（违反零第三方红线）："; printf '%s\n' "$EXT" | sed 's/^/        /'
  printf '%s\n' "$EXT" | head -2 | while IFS= read -r f; do grep -oE '(src|href)="https?://[^"]+' "$f" | head -2 | sed "s|^|        $(printf '%s' "$f") :|"; done
fi

# ---------- ⑧ bg.jpg 一个字节都不许动 ----------
head1 "⑧ static/images/bg.jpg SHA256 未变"
BG_WANT="4b1e13ee54ef5df240543eef85de864f69823ccad25e023533a5e3f1e9a55660"
if [ -f "static/images/bg.jpg" ]; then
  BG_GOT=$(sha256sum static/images/bg.jpg | cut -d' ' -f1)
  [ "$BG_GOT" = "$BG_WANT" ] && ok "bg.jpg SHA256 与基线一致" || no "bg.jpg 被改动（红线②）：want=$BG_WANT got=$BG_GOT"
else no "找不到 static/images/bg.jpg"; fi

# ---------- ⑨ 角色资产完整性：不得有 0 字节 / 总体积封顶 / 分片各自封顶 ----------
# 【2026-10-14 改】上限 60MB → 96MiB：37 个剪辑的 medium 档（48.15MB）已入库，
# 主页最常用几段还要另发一档 hi（分辨率是 medium 的 2 倍，避免在 586px 宽的 CRT 屏里
# 把 134px 一帧的图放大 2.8 倍发虚）。首屏预算（第 ⑩ 条）不动，仍严 ≤1.5MB。
#   ★2026-10-16 口径标注（接手窗口）：**两个数不是一个数，别再混用** ——
#     · 本文件第 ⑩ 条 =「**资产自报口径**」：只读 static/kurisu/manifest.json 的自我申报，
#       判据 `≤ 1572864 B = 1536KB`（就是本条下方那句 `-le 1572864`，**判定逻辑一字未改**）；
#     · _dev/gate-firstscreen.mjs =「**整页真实加载口径**」：真浏览器 CDP 采集 + 硬拦截，
#       其默认 `BUDGET = 1689600 B = 1650KB`（该文件的用法行/注释此前写的 1572864、1600KB
#       都是陈旧值，已按实际值更正）。
#     · 文档里凡写"首屏预算 1536 / 1600 / 1650KB"，**必须指明是哪一个口径**。
# 【2026-10-16 改】96MiB → **160MiB**（站主口径）：原声库可发布集 46.2MB
# （dist 968 个 m4a/webm + envelope 484 个 + 3 个 bank 文件，见 docs/台词库扩容与合成交付-20261015.md）
# 要随发布一起上，96MiB 会被顶爆。同时**给每一路分片各自的上限**，防以后某一路失控靠总量兜着：
#   · 原声分片  static/kurisu/voice/orig*   ≤ 64MiB
#   · 合成分片  static/kurisu/voice/synth*  ≤ 32MiB
#   分片目录还不存在时 = 该路尚未入库 ⇒ 打印"尚未入库（跳过）"，**不判失败**。
#   算术交代（别把两个数当互相等价）：当前角色+场景 ≈88MB，原声入库后 ≈134MB，距 160MiB 还有 ≈26MB；
#   合成分片一旦超过 ≈26MB 会**先撞总量门禁**（这是有意的：总量是全局闸，分片上限是单路闸）。
#   到那天按站主口径再调总量，**不许顺手把分片上限抬上去**。
head1 "⑨ 角色资产：无 0 字节文件、总体积 ≤ 160MiB、分片各自封顶（原声 64MiB / 合成 32MiB）"
if [ -d static/kurisu ]; then
  EMPTY=$(find static/kurisu static/images/crt -type f -size 0 2>/dev/null | head -5)
  TOT=$(du -sk static/kurisu static/images/crt 2>/dev/null | awk '{s+=$1} END {print s+0}')
  [ -z "$EMPTY" ] && ok "无 0 字节资产" || { no "存在 0 字节资产（会解码失败）："; printf '%s\n' "$EMPTY" | sed 's/^/        /'; }
  if [ "$TOT" -le 163840 ]; then ok "角色+场景资产合计 $((TOT/1024))MB ≤ 160MiB"; else no "角色+场景资产合计 $((TOT/1024))MB > 160MiB"; fi
  # 分片各自封顶（$1=glob $2=上限KiB $3=中文名；目录不存在 = 跳过，不算失败）
  shard_cap() {
    local g=$1 cap=$2 name=$3 dirs s
    # shellcheck disable=SC2086
    dirs=$(ls -d $g 2>/dev/null || true)
    if [ -z "$dirs" ]; then ok "$name 分片尚未入库（跳过上限检查：$g）"; return; fi
    # shellcheck disable=SC2086
    s=$(du -sk $dirs 2>/dev/null | awk '{s+=$1} END {print s+0}')
    if [ "$s" -le "$cap" ]; then ok "$name 分片 $((s/1024))MB ≤ $((cap/1024))MiB（$(echo $dirs | tr '\n' ' ')）"
    else no "$name 分片 $((s/1024))MB > $((cap/1024))MiB（$(echo $dirs | tr '\n' ' ')）—— 这一路失控了，先查产物再发"; fi
  }
  shard_cap 'static/kurisu/voice/orig*' 65536 '原声'
  shard_cap 'static/kurisu/voice/synth*' 32768 '合成'
else no "找不到 static/kurisu（角色资产缺失）"; fi

# ---------- ⑩ 首屏档体积 ≤1.5MB（读 manifest 自报预算）----------
# ⚠️ 这一条**只读 manifest 的自我申报**（budgets.firstScreenBytes = 角色 boot/poster/头像静帧），
#    它**不测页面真实加载**。真实首屏（含 CSS/JS/bg/desk/图集）由 `_dev/gate-firstscreen.mjs`
#    用真浏览器 CDP 采集并**硬拦截**（超预算即退出码非 0）。两条口径不要混为一谈。
head1 "⑩ 首屏角色资源（资产自报口径：只读 manifest 自报，非真实加载）判据 ≤ 1536KB"
if [ -f static/kurisu/manifest.json ]; then
  # 【稳健写法】优先读 manifest 自报；字段名变了/没有就按"首屏档文件"名规则实算（boot/poster/static + 头像 idle）
  PYBIN=$(command -v python3 || command -v python || echo python); FS=$($PYBIN -c "
import json, os
p='static/kurisu/manifest.json'
try:
    d=json.load(open(p, encoding='utf-8'))
    b=d.get('budgets') or d.get('budget') or {}
    v=b.get('firstScreenBytes') or b.get('first_screen_bytes')
    if not v:
        files=(b.get('firstScreenFiles') or {}).keys()
        v=sum(os.path.getsize(os.path.join('static/kurisu', f)) for f in files if os.path.exists(os.path.join('static/kurisu', f)))
    print(int(v))
except Exception:
    print(-1)
" 2>/dev/null || echo -1)
  if [ "$FS" = "-1" ] || [ -z "$FS" ]; then
    # 兜底实算：首屏档 = *.boot.webp + *.poster.webp + avatar/*.static.webp + avatar/normal.idle.webp
    FS=$( { find static/kurisu -type f \( -name 'idle.boot.webp' -o -name 'idle.intro.webp' -o -name 'idle.poster.webp' -o -name 'normal.static.webp' -o -name 'normal.idle.webp' \) -printf '%s\n' 2>/dev/null | awk '{s+=$1} END {print s+0}'; } )
    ok "manifest 未自报，按文件规则实算首屏 $((FS/1024))KB（资产自报口径预算 1536KB）"
  fi
  if [ "${FS:-0}" -le 1572864 ]; then ok "首屏 $((FS/1024))KB ≤ 1536KB（资产自报口径）"; else no "首屏 $((FS/1024))KB 超预算 1536KB（资产自报口径）"; fi
else no "找不到 static/kurisu/manifest.json"; fi

# ---------- ⑪ 播放器必须保留降级与暂停逻辑（防以后被简化掉）----------
head1 "⑪ kurisu-player.js 保留 reduced-motion / visibility / 图集三类逻辑"
if [ -f static/js/kurisu-player.js ]; then
  for pat in 'prefers-reduced-motion' 'visibilitychange' 'drawImage'; do
    if grep -q "$pat" static/js/kurisu-player.js; then ok "播放器含 $pat"; else no "播放器缺少 $pat（降级/暂停/图集逻辑被删了？）"; fi
  done
else no "找不到 static/js/kurisu-player.js"; fi
# ---------- ⑫ 版式/比例硬约束（站主 2026-10-17："把尺寸比例拿捏好，别越做问题越多"）----------
# 这一组是把"已经修好的比例"钉成断言，防以后被顺手改回去（每条都对应一次真实翻车）。
# ★2026-10-18 外链化改口径：外壳 CSS/JS 不再内联在页面里，改成 /css/*.css 与 /js/*.js（带内容指纹）。
#   下面每条判据的语义、条数、报错文案一字不改，只把"检索面"从「ai/index.html 这一个文件」
#   换成「ai/index.html + 该页 <link>/<script> 真正引用的外链资产」——否则代码一搬进外链就假红，
#   而假红会逼人把内联写法加回去（这才是真的退化）。代码丢了照样红，判据没变松。
asset_corpus() {   # $1=页面产物 $2=语料输出文件；口径=HTML 全文 + 页面引用到的每个 /css/、/js/ 文件
  local page=$1 out=$2 ref
  if [ -f "$page" ]; then cat "$page" > "$out"; else : > "$out"; fi
  grep -oE '/(css|js)/[A-Za-z0-9._/-]+' "$page" 2>/dev/null | sort -u | while read -r ref; do
    [ -f "$PUB$ref" ] && cat "$PUB$ref" >> "$out"
  done
}
head1 "⑫ 版式/比例硬约束（手机面板、E-mote 画布、省流误判、字幕垫板）"
AICORPUS="${TMPDIR:-/tmp}/xk-ai-corpus.$$"
asset_corpus "$PUB/ai/index.html" "$AICORPUS"
if [ -s "$PUB/ai/index.html" ]; then
  AI="$AICORPUS"
  # 手机屏幕必须按比例（aspect-ratio 284/600），不能再写死 height:600px 与面板高度打架
  if grep -q 'aspect-ratio:284/600' "$AI"; then ok "手机屏幕 aspect-ratio:284/600 存在（比例随面板走）"; else no "手机屏幕缺 aspect-ratio:284/600（写死高度会导致面板裁切/变形）"; fi
  if grep -qE '\.phone-scr\{[^}]*width:284px;height:600px' "$AI"; then no "手机屏幕又写回固定 284x600（与面板高度冲突）"; else ok "手机屏幕没有写死 284x600"; fi
  # 面板宽度自适应，禁止再出现会压扁面板的 max-height 规则
  if grep -q 'min(300px,44vh)' "$AI"; then ok "手机面板宽度 min(300px,44vh)（按视口高度自适应）"; else no "手机面板缺 min(300px,44vh)"; fi
  if grep -q 'max-height:820px){.phone{top:84px' "$AI"; then no "旧的 max-height:820px 压扁规则回来了（面板会裁切）"; else ok "没有旧的 max-height:820px 压扁规则"; fi
  # E-mote 接管后必须停掉原始帧动画，并把画布内部尺寸对齐 CSS 盒子
  if grep -q '__xkPhoneAnim=!1\|__xkPhoneAnim=false' "$AI"; then ok "E-mote 接管后停掉原始帧动画"; else no "E-mote 接管后没停原始帧动画（手机里会两套画面打架）"; fi
  if [ -f "$PUB/js/phone-emote.js" ]; then
    if grep -q 'clientWidth' "$PUB/js/phone-emote.js" && grep -q 'devicePixelRatio' "$PUB/js/phone-emote.js"; then ok "E-mote 画布按 CSS 盒子×dpr 设定内部尺寸"; else no "E-mote 画布没按盒子尺寸设定（会被拉伸变形）"; fi
  else no "缺 $PUB/js/phone-emote.js"; fi
  # 静态立绘兜底（E-mote 不可用时手机不空屏）
  if grep -q 'idle.poster.webp' "$AI"; then ok "手机屏幕有静态立绘兜底"; else warn "手机屏幕没有静态立绘兜底"; fi
  # 但 E-mote 接管后必须撤掉这张静态立绘，否则两个人物叠在一起（线上真实出现过）；且必须在 ready 后才撤，避免加载期空屏
  if grep -q 'html\.xk-phone-emote\.xk-emote-ready \.phone-scr{background-image:none}' "$AI"; then ok "E-mote ready 后撤掉静态立绘垫底（不叠人、加载期不空屏）"; else no "E-mote ready 后没撤静态立绘（会和 E-mote 人物叠成两个 / 或加载期空屏）"; fi
  if grep -q "xk-emote-ready" "$AI"; then ok "页面有 xk-emote-ready 状态位（ready 才撤垫底）"; else no "页面缺 xk-emote-ready 状态位"; fi
else no "缺 $PUB/ai/index.html（手机面板页）"; fi

if [ -f "$PUB/js/xk-saver.js" ]; then
  SAVER="$PUB/js/xk-saver.js"
  if grep -q 'slow-2g|2g)' "$SAVER"; then ok "省流触发不含 3g（避免正常网速误判）"; else no "省流触发仍包含 3g（正常用户会被误判成弱网）"; fi
  for pat in 'HTMLImageElement.prototype' 'script' 'requestIdleCallback'; do
    if grep -q "$pat" "$SAVER"; then ok "省流脚本含 $pat 拦截"; else no "省流脚本缺少 $pat 拦截"; fi
  done
else warn "缺 $PUB/js/xk-saver.js（省流模式未上线）"; fi

# 字幕垫板走 data-src 惰性加载（省流时 373KB 不请求；非省流由 xk-saver 补回）
if grep -q 'data-src=/kurisu/scene/subtitle_frame_big.webp' "$PUB/index.html"; then ok "主页字幕垫板是 data-src 惰性加载"; else warn "主页字幕垫板不是 data-src（省流模式会白取 373KB）"; fi

# CRT 位置/尺寸必须由 --crt-w/--crt-h 变量驱动（禁写死像素，换视口就错位）
if grep -q -- '--crt-w' "$PUB/index.html" && grep -q 'width:var(--crt-w)' "$PUB/index.html"; then ok "CRT 尺寸由 --crt-w/--crt-h 驱动（随视口等比）"; else no "CRT 尺寸不是变量驱动（换视口会错位）"; fi

# ---------- ⑤ [EMO] 情绪标签协议（页面永不出现标签 + 逐句继承）----------
if [ -s "$PUB/ai/index.html" ]; then
  AI5="$AICORPUS"   # 同上：检索面 = HTML ∪ 外链资产
  if grep -q 'xkEmoClean' "$AI5"; then ok "V5: 答案渲染侧有标签剥离 helper（xkEmoClean）"; else no "V5: 缺 xkEmoClean（[EMO] 标签会直接显示给访客）"; fi
  if grep -q '__xkSetEmo' "$AI5"; then ok "V5: 有逐句情绪继承入口（__xkSetEmo）"; else no "V5: 缺 __xkSetEmo（标签解析了也不会换情绪）"; fi
  # 渲染路径必须调用 xkEmoClean（定义 + 至少一处调用 = ≥2 次；minify 后变量名会变，只数函数名）
  EMO_N=$(grep -o 'xkEmoClean' "$AI5" | wc -l)
  if [ "$EMO_N" -ge 2 ]; then ok "V5: 渲染路径调用 xkEmoClean（$EMO_N 处）"; else no "V5: 渲染路径没调用 xkEmoClean（只有定义没使用 = 标签仍会上屏）"; fi
  # 泄漏闸是运行时指标（xkEmoClean 内部的正则字面量本身含 [EMO:，不能用静态 grep 判定）；
  # 这里只保证页面暴露了自检入口 window.__xkEmoStat()，供 CDP/浏览器验收时量"可见文本里的标签数=0"
  if grep -q '__xkEmoStat' "$AI5"; then ok "V5: 页面暴露 __xkEmoStat() 自检入口（运行时量泄漏率）"; else no "V5: 缺 __xkEmoStat（无法在浏览器里验收泄漏率）"; fi
else warn "缺 $PUB/ai/index.html（跳过 V5 断言）"; fi

# ---------- ⑥ 全站共用书桌底图 + E-mote 署名（站主：比例/底图不许各页各写一套）----------
DESK_OK=0; DESK_N=0
for pg in index.html alerts/index.html posts/index.html ai/index.html test/index.html; do
  if [ -s "$PUB/$pg" ]; then
    DESK_N=$((DESK_N + 1))
    if grep -q 'class="\?desk' "$PUB/$pg"; then DESK_OK=$((DESK_OK + 1)); fi
  fi
done
if [ "$DESK_N" -gt 0 ] && [ "$DESK_OK" -eq "$DESK_N" ]; then ok "五页共用书桌底图（$DESK_OK/$DESK_N）"; else no "有页面缺书桌底图（$DESK_OK/$DESK_N）—— 站主要求所有页共用书桌"; fi
if [ -s "$PUB/ai/index.html" ] && grep -q 'CC BY-NC-SA' "$PUB/ai/index.html"; then ok "E-mote 素材署名在位（CC BY-NC-SA 4.0）"; else warn "缺 E-mote 署名（许可要求保留署名）"; fi

# ---------- ⑬ 新页产物契约：/what/ 介绍页 与 /lab/ 靶场页（2026-10-17 新增）----------
# 这两页是本轮新写的独立页面，失败方式与"漏构建"同性质，所以要在发布前硬拦截：
#   · 产物不存在     —— Hugo "构建成功"也可能没生成（layout 漏了 / draft / 输出路径错）
#   · 缺 data-xk-ssr —— SPA 换页靠 <main> 上的路由名，缺了夹层视图直接空白
#   · 只剩骨架       —— 模板没吃到内容（判据见下）
# ★2026-10-18 判据修订（原判据是"字节数 > 100000"）：
#   100000 这个数当初只是"真实产物约 15.5 万字节"的侧写，它成立的前提是外壳 CSS/JS
#   内联在每页里（光它们就 15 万字节以上）。外壳改外链后同一页只剩自身内容
#   （实测 what 14075 / lab 17296 / api 28447 / status 32280 / redteam 38926 字节），
#   旧阈值必然假红——而真红灯"模板没吃到内容"依旧要用体积抓，所以换成两个更准的判据：
#     · 骨架下限 8000 字节 —— 只剩骨架（head-meta + 空 <main> + 一堆外链标签）约 4–6KB，
#       真实内容页最小 14075 字节；取 8000 既能抓住"渲染成空壳"，又不会被正常删减误伤；
#     · 共享运行时确实外链 —— 页面里有 /css/xk*.css 与 /js/xk*.js 引用，说明 layout 链
#       (shell-style/shell-script/api-bind) 没退回到"整段内联"或干脆没渲染。
# 口径与 _dev/check-ssr-contract.py 的 PAGES 清单一致（那边 10 页全查，这里把五个新页
# 变成发布前硬拦截：它们是本轮新加的，还没经过多轮发布验证）。
# ★引号口径：产物被 minify 成 <main ... data-xk-ssr=what>（属性没引号），
#   所以判据用 ["']? 宽匹配，不写死带引号的字面量（写死会假红）。
# $1=路由名（=URL 段） $2=中文页名
new_page_gate() {
  local route=$1 name=$2 f="$PUB/$1/index.html" sz pat ext_css ext_js
  pat="data-xk-ssr=[\"']?${route}([^a-z-]|$)"
  if [ ! -f "$f" ]; then
    no "$route/index.html 不存在（$name 没被构建进产物）"
    return
  fi
  sz=$(stat -c %s "$f")
  ext_css=$(grep -coE '/css/xk[^"> ]*\.css' "$f")
  ext_js=$(grep -coE '/js/xk[^"> ]*\.js' "$f")
  if [ "$sz" -gt 8000 ] && grep -qE "$pat" "$f" && [ "${ext_css:-0}" -ge 2 ] && [ "${ext_js:-0}" -ge 2 ]; then
    ok "$route/index.html $sz 字节 > 8000（非骨架），data-xk-ssr=$route 在位，外链 $ext_css CSS / $ext_js JS（$name）"
  else
    no "$route/index.html 不合格：$sz 字节（需 >8000 非骨架）；data-xk-ssr=$route $(grep -qE "$pat" "$f" && echo 在位 || echo 缺失)；外链 $ext_css CSS / $ext_js JS（各需 ≥2）（$name）"
  fi
}
head1 "⑬ 新页产物契约（存在 + >8000 字节非骨架 + data-xk-ssr + 共享运行时外链）"
new_page_gate what 介绍页
new_page_gate lab 靶场说明页
new_page_gate api 公开端点清单页
new_page_gate status 状态页
new_page_gate redteam 红队评测页
new_page_gate ip IP情报页
new_page_gate purpleteam 紫队演练页
new_page_gate passwords 弱口令统计页

# ---------- ⑭ 外链共享运行时（2026-10-18：每页内联 136KB JS + 16KB CSS → 外链共享文件）----------
# 背景：改前 10 页每页都内联同一份外壳 CSS/JS，页均 158–253KB，二次访问一个字节都省不下来。
# 现在外壳/头像卡/绑定层统一走 /css/xk*.css 与 /js/xk-*.js，文件名带内容指纹
# （Hugo `fingerprint` = sha256 全 64 位 hex），页面只剩自身内容（14–62KB）。
# 这一组用来钉住"别又改回整段内联"，三个失败模式各一条：
#   · 内联回来了   —— HTML 体积上限 90000（改后最大 index 61606，留 ~28KB 余量给正文增长）
#   · 少了指纹     —— 外链名必须含 .min.<64 hex>.css|js；没指纹时改内容不改 URL，
#                     浏览器缓存的旧文件永远刷不掉（比内联更糟）
#   · 外链断了     —— resources.Get 路径写错时 Hugo 不报错、只吐空引用，这里按产物里的
#                     实际引用逐个 stat，缺文件直接红
# 手写静态文件（static/ 下的 xk-saver.js / xk-realtime.js / xk-app.js / phone-emote.js）不在
# 内容管道里，历史上也没指纹，明确列进白名单；其余一律要求带指纹。
# ★外壳内联 <script 数量判据：外壳（shell-script.html）必须仍然只产 2 个 <script 标签
#   （shell 运行时 + scene-js），2026-10-18 起两个都带 src（正文进 /js/xk-shell.js、
#   /js/xk-scene.js），id="scene-js" 保留（_dev/audit-shell.mjs 靠它定位）。见 ⑭ 末尾那条。
head1 "⑭ 外链共享运行时（HTML 体积上限 / 内容指纹 / 外链文件在位）"
for pg in index.html alerts/index.html posts/index.html ai/index.html test/index.html \
          what/index.html lab/index.html api/index.html status/index.html redteam/index.html; do
  f="$PUB/$pg"
  if [ ! -s "$f" ]; then no "$pg 不存在（外链化后每页仍必须有产物）"; continue; fi
  sz=$(stat -c %s "$f")
  if [ "$sz" -le 90000 ]; then
    ok "$pg HTML $sz 字节 ≤ 90000（外壳运行时已外链）"
  else
    no "$pg HTML $sz 字节 > 90000（内联运行时又回来了？）"
  fi
  REFS=$(grep -oE '/(css|js)/[A-Za-z0-9._/-]+' "$f" | sort -u)
  if [ -z "$REFS" ]; then no "$pg 没有任何 /css 或 /js 外链（模板可能退回整段内联）"; continue; fi
  BAD=""; N=0
  for ref in $REFS; do
    N=$((N + 1))
    if [ ! -f "$PUB$ref" ]; then BAD="$BAD 缺文件:$ref"; continue; fi
    case "$ref" in
      /js/xk-saver.js|/js/xk-realtime.js|/js/xk-app.js|/js/phone-emote.js|/js/kurisu-player.js) : ;;
      *) printf '%s' "$ref" | grep -qE '\.min\.[0-9a-f]{64}\.(css|js)$' || BAD="$BAD 无指纹:$ref" ;;
    esac
  done
  if [ -z "$BAD" ]; then
    ok "$pg 外链 $N 个：文件名带内容指纹且产物中在位"
  else
    no "$pg 外链不合格（$N 个）：$BAD"
  fi
done
# 外壳 <script 标签数 = 2（运行时 + scene-js），都必须是外链 src（正文不再内联）
for pg in alerts/index.html what/index.html redteam/index.html; do
  f="$PUB/$pg"
  [ -s "$f" ] || { no "$pg 不存在（外壳脚本数断言）"; continue; }
  SHELLN=$(grep -oE '<script[^>]*/(js/xk-shell|js/xk-scene)[^>]*>' "$f" | wc -l)
  SHELLSRC=$(grep -oE '<script[^>]*/(js/xk-shell|js/xk-scene)[^>]*>' "$f" | grep -c 'src=')
  if [ "$SHELLN" -eq 2 ] && [ "$SHELLSRC" -eq 2 ]; then
    ok "$pg 外壳 <script 恰好 2 处且都是外链 src（运行时 + scene-js）"
  else
    no "$pg 外壳 <script 数变了：$SHELLN 处（其中带 src $SHELLSRC 处），应为 2/2"
  fi
done

# ---------- 汇总 ----------
head1 "汇总"
echo "  通过 $PASS 项，失败 $FAIL 项"
if [ "$FAIL" -eq 0 ]; then
  printf '\n\033[1;32m断言全部通过 → 允许发布\033[0m\n'
  exit 0
fi
printf '\n\033[1;31m有 %s 项断言失败 → 拒绝发布（gh-pages 不会被更新）\033[0m\n' "$FAIL"
exit 1
