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

# ---------- ⑥ 不得出现死端点 /api/public/latest ----------
head1 "⑥ 全站不得出现死端点 /api/public/latest"
HITS=$(scan '/api/public/latest' | head -20)
if [ -z "$HITS" ]; then
  ok "没有任何文件引用 /api/public/latest"
else
  no "有文件引用已下线的 /api/public/latest："
  printf '%s\n' "$HITS" | sed 's/^/        /'
  printf '%s\n' "$HITS" | head -3 | while IFS= read -r f; do
    grep -n -m2 -e '/api/public/latest' "$f" | sed "s|^|        $(printf '%s' "$f") :|"
  done
  echo "        → 处理方式二选一：① 从引用处删掉（推荐：它每次加载都会打一个 404）；"
  echo "                          ② 若确实要保留'未上线端点探测'的说明，就不要把它写进产物。"
fi

# ---------- 汇总 ----------
head1 "汇总"
echo "  通过 $PASS 项，失败 $FAIL 项"
if [ "$FAIL" -eq 0 ]; then
  printf '\n\033[1;32m断言全部通过 → 允许发布\033[0m\n'
  exit 0
fi
printf '\n\033[1;31m有 %s 项断言失败 → 拒绝发布（gh-pages 不会被更新）\033[0m\n' "$FAIL"
exit 1
