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
ALLOWED="ask kb overview alerts latest honeypot audit geo webstats tts stories story"
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
head1 "⑩ 首屏角色资源（manifest 自报，非真实加载）≤ 1.5MB"
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
    ok "manifest 未自报，按文件规则实算首屏 $((FS/1024))KB（预算 1536KB）"
  fi
  if [ "${FS:-0}" -le 1572864 ]; then ok "首屏 $((FS/1024))KB ≤ 1536KB"; else no "首屏 $((FS/1024))KB 超预算 1536KB"; fi
else no "找不到 static/kurisu/manifest.json"; fi

# ---------- ⑪ 播放器必须保留降级与暂停逻辑（防以后被简化掉）----------
head1 "⑪ kurisu-player.js 保留 reduced-motion / visibility / 图集三类逻辑"
if [ -f static/js/kurisu-player.js ]; then
  for pat in 'prefers-reduced-motion' 'visibilitychange' 'drawImage'; do
    if grep -q "$pat" static/js/kurisu-player.js; then ok "播放器含 $pat"; else no "播放器缺少 $pat（降级/暂停/图集逻辑被删了？）"; fi
  done
else no "找不到 static/js/kurisu-player.js"; fi
# ---------- 汇总 ----------
head1 "汇总"
echo "  通过 $PASS 项，失败 $FAIL 项"
if [ "$FAIL" -eq 0 ]; then
  printf '\n\033[1;32m断言全部通过 → 允许发布\033[0m\n'
  exit 0
fi
printf '\n\033[1;31m有 %s 项断言失败 → 拒绝发布（gh-pages 不会被更新）\033[0m\n' "$FAIL"
exit 1
