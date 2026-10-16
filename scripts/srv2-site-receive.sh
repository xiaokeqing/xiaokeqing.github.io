#!/usr/bin/env bash
# ============================================================
# srv2-site-receive.sh —— 博客整站在 srv2 侧的接收/切换脚本（幂等、可回滚）
# ------------------------------------------------------------
# 调用方：站主机器上的 scripts/publish-site-to-srv2.ps1
#   sudo bash srv2-site-receive.sh <tarball.tar.gz>
#   sudo bash srv2-site-receive.sh --rollback      # 一键回到上一版
#   sudo bash srv2-site-receive.sh --status        # 看当前/上一版
#
# 目录布局与原子性：
#   /opt/secagent/releases/site-<stamp>/   每次发布一个完整目录（先解包、校验，再露面）
#   /opt/secagent/site -> releases/site-*  线上根（符号链接）
#   切换 = ln -sfn NEW /opt/secagent/site.tmp && mv -T site.tmp site
#          —— 单次 rename()，任何时刻对外都是一个完整版本，不存在半成品窗口。
#
# 失败即回滚：解包/校验/切换后自检（回环 HTTP 200 且字节数与本地 index.html 一致）
#   任何一步失败 → 恢复到上一版并 exit 非 0。
#
# 纪律：不动 nginx 配置、不开端口、不打印凭据；产物目录内容 root:root 只读（a+rX）。
# ============================================================
set -euo pipefail

SITE_LINK=/opt/secagent/site
RELEASES=/opt/secagent/releases
PREV_FILE=$RELEASES/.previous
KEEP=4                     # 保留最近 4 个版本（含当前）
MIN_INDEX_BYTES=4096      # 产物基本特征：index.html 必须 > 4 KB（新主页是 demo 整份，约 9.5KB）
HOST_FOR_CHECK=xiaokeqing.cn
CHECK_URL=http://127.0.0.1:18080/
LOG_TAG="site-receive"

log()  { echo "[$(date +%H:%M:%S)] $*"; }
ok()   { echo "  [OK] $*"; }
warn() { echo "  [!] $*"; }
die()  { echo "  [X] $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "需要 root（sudo bash $0 ...）"

current_target() { readlink -f "$SITE_LINK" 2>/dev/null || true; }

# 校验解包后的目录：基本特征 + 无越权文件
verify_tree() { # $1 = dir
  local d=$1
  [[ -d $d ]] || { echo "目录不存在：$d"; return 1; }
  [[ -f $d/index.html ]] || { echo "缺 index.html"; return 1; }
  local sz
  sz=$(stat -c%s "$d/index.html")
  [[ $sz -gt $MIN_INDEX_BYTES ]] || { echo "index.html 只有 $sz B（要求 > $MIN_INDEX_BYTES）"; return 1; }
  local n
  n=$(find "$d" -type f | wc -l)
  [[ $n -gt 0 ]] || { echo "产物是空的"; return 1; }
  # 安全检查：不得有 setuid/setgid 文件、不得有指向目录外的符号链接
  if find "$d" -type f -perm /6000 | head -1 | grep -q .; then echo "产物里出现 setuid/setgid 文件"; return 1; fi
  local badlink
  badlink=$(find "$d" -type l ! -lname "$d/*" -printf '%p -> %l\n' 2>/dev/null | head -3 || true)
  if [[ -n $badlink ]]; then echo "产物里有越出根目录的符号链接：$badlink"; return 1; fi
  echo "$sz" > /tmp/.site-receive-index-size
  return 0
}

# 回环自检：期望 200 且响应体字节数 == 刚解包出来的 index.html 大小
http_selfcheck() { # $1 = 期望字节数
  local expect=$1 code size
  read -r code size < <(curl -s -o /dev/null -w '%{http_code} %{size_download}' \
      -H "Host: $HOST_FOR_CHECK" "$CHECK_URL" || echo "000 0")
  echo "  回环自检：HTTP=$code bytes=$size（期望 200 / $expect）"
  [[ $code == "200" && $size == "$expect" ]]
}

switch_to() { # $1 = 目标 release 目录（绝对路径）
  local target=$1 cur
  cur=$(current_target)
  [[ "$cur" == "$target" ]] && { ok "线上已经就是这个版本，无需切换"; return 0; }
  [[ -d $target ]] || die "目标目录不存在：$target"
  printf '%s\n' "$cur" > "$PREV_FILE"   # 记下上一版，供 --rollback
  ln -sfn "$target" "$SITE_LINK.tmp"
  mv -T "$SITE_LINK.tmp" "$SITE_LINK"    # 原子替换
  ok "已切换：$SITE_LINK -> $(readlink "$SITE_LINK")（上一版：${cur:-无}）"
}

prune_old() {
  local cur keep_list
  cur=$(current_target)
  mapfile -t keep_list < <(ls -1dt "$RELEASES"/site-* 2>/dev/null | head -"$KEEP")
  local d
  while IFS= read -r d; do
    [[ -n $d ]] || continue
    [[ "$d" == "$cur" ]] && continue
    if printf '%s\n' "${keep_list[@]}" | grep -qx "$d"; then continue; fi
    warn "清理旧版本：$d"
    rm -rf -- "$d"
  done < <(ls -1dt "$RELEASES"/site-* 2>/dev/null || true)
}

# ---------------- 子命令 ----------------
case "${1:-}" in
  --status)
    echo "线上根：$SITE_LINK -> $(readlink "$SITE_LINK" 2>/dev/null || echo '(非符号链接)')"
    echo "上一版：$(cat "$PREV_FILE" 2>/dev/null || echo '(无记录)')"
    echo "现有版本："
    ls -1dt "$RELEASES"/site-* 2>/dev/null | sed 's/^/  /'
    curl -s -o /dev/null -w '  回环 GET / -> HTTP %{http_code} size=%{size_download}\n' -H "Host: $HOST_FOR_CHECK" "$CHECK_URL"
    exit 0
    ;;
  --rollback)
    prev=$(cat "$PREV_FILE" 2>/dev/null || true)
    [[ -n $prev ]] || die "没有可回滚的上一版记录（$PREV_FILE 为空）"
    [[ -d $prev ]] || die "上一版目录已经不存在：$prev"
    log "回滚到 $prev"
    # 用普通切换（会把当前版写进 .previous，形成来回可切）
    switch_to "$prev"
    sz=$(stat -c%s "$prev/index.html")
    http_selfcheck "$sz" || die "回滚后自检失败，请人工介入"
    ok "回滚完成"
    exit 0
    ;;
  --help|-h|"")
    sed -n '2,20p' "$0"
    exit 0
    ;;
esac

TARBALL=$1
[[ -f $TARBALL ]] || die "找不到 tar 包：$TARBALL"

STAMP=$(date +%Y%m%d-%H%M%S)
NEW=$RELEASES/site-$STAMP
STAGING=$RELEASES/.staging-$STAMP
INCOMING_SHA=$(sha256sum "$TARBALL" | cut -d' ' -f1)

log "0/7 输入：$TARBALL（$(stat -c%s "$TARBALL") B, sha256=${INCOMING_SHA:0:16}…）"

log "1/7 预检 tar 包（成员路径、是否含 index.html）"
MEMBERS=$(tar -tzf "$TARBALL")
[[ -n $MEMBERS ]] || die "tar 包是空的"
if printf '%s\n' "$MEMBERS" | grep -qE '^/|(^|/)\.\.(/|$)'; then
  die "tar 包含绝对路径或 .. 越界成员，拒绝解包"
fi
printf '%s\n' "$MEMBERS" | grep -qE '(^|/)index\.html$' || die "tar 包里没有 index.html"
ok "成员数 $(printf '%s\n' "$MEMBERS" | wc -l)"

log "2/7 解包到暂存目录（还不露面）→ $STAGING"
rm -rf -- "$STAGING"
install -d -o root -g root -m 0755 "$STAGING"
tar -xzf "$TARBALL" -C "$STAGING" --no-same-owner --no-same-permissions
# 有些 tar 会带一层 public/ 前缀，这里归一化
if [[ ! -f $STAGING/index.html && -f $STAGING/public/index.html ]]; then
  warn "tar 带 public/ 前缀，做归一化"
  shopt -s dotglob
  mv "$STAGING"/public/* "$STAGING"/ 2>/dev/null || true
  rmdir "$STAGING/public" 2>/dev/null || true
  shopt -u dotglob
fi
chown -R root:root "$STAGING"
chmod -R u=rwX,go=rX "$STAGING"

log "3/7 校验产物基本特征"
if ! verify_tree "$STAGING"; then
  rm -rf -- "$STAGING"
  die "产物校验不通过，已丢弃暂存目录（线上未动）"
fi
INDEX_SZ=$(cat /tmp/.site-receive-index-size)
ok "index.html=$INDEX_SZ B；文件数 $(find "$STAGING" -type f | wc -l)"

# ★窗口 Q 修（2026-10-16）：幂等检查原来**只比 index.html 的 sha256**。
#   后果：任何"只改资源（JS/CSS/图集）"的发布都会被判成"内容无变化"而**静默跳过切换**，
#   而且暂存目录被 rm -rf 掉，连手动切换的机会都没有（实测：动画二批只改了
#   static/js/kurisu-player.js + 新增 static/kurisu/eye/，index.html 逐字节未变 ⇒ RESULT=no-change，
#   新播放器根本没上线，但脚本退出码 0、上层视为发布成功）。
#   改成**整树内容哈希**：文件名（相对路径）+ 内容一起哈希。
#   ★2026-10-16（窗口 Q）：加 `LC_ALL=C` —— 默认 locale 是 en_US.UTF-8，GNU sort 会按 glibc
#   collation 排序（大小写/标点权重不按字节序），这样算出来的哈希**只有同一台机器、同一套 locale
#   才能复现**，Windows 发送侧永远算不出同一个值，发送侧就没法在上传前判"内容不同"。
#   钉到 LC_ALL=C（find/sort/xargs 全带）后 = 路径字节序 + 逐文件 sha256 + 对整段文本再 sha256，
#   跨平台可复现（发送侧 scripts/publish-site-to-srv2.ps1 的 Get-TreeHash 与这里逐字节同口径）。
#   行为不变：仍然只比"整树内容是否完全一致"，只是哈希取值本身变了（不对外，无兼容问题）。
#   ★2026-10-16（接手窗口）：**排除顶层 `./index.json`**。
#   为什么必须排除：发送侧 scripts/publish-site-to-srv2.ps1 早已把它列进 `$TreeNondet`
#   （"每次构建都会变"⇒ 逐文件比对时忽略，因为 layouts/index.json 模板里带 generatedAt），
#   但接收侧这里原来**把它算进整树哈希** ⇒ 两次构建的整树哈希**永不可能相等** ⇒
#   `RESULT=no-change` 分支**实际不可达**、每次发布都白切换一次（发送侧那句
#   "接收侧会跳过切换"因此是**误导**）。两边口径一致后，"无变化"才真正可达。
#   只排除**顶层** `./index.json`（Hugo 的分节/分页产物也可能叫 index.json，那些必须照算）。
tree_hash() { # $1 = 产物根目录
  ( cd "$1" 2>/dev/null && LC_ALL=C find . -type f ! -path './index.json' -print0 | LC_ALL=C sort -z | LC_ALL=C xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
}
# 供发送侧核对用：把两个哈希打成机器可读行（纯追加，不影响上面的人类可读日志）
emit_hashes() { # $1 = 线上树哈希  $2 = 待发布树哈希
  echo "TREE_HASH_ONLINE=${1:-}"
  echo "TREE_HASH_INCOMING=${2:-}"
}

log "4/7 幂等检查（与线上**整树内容**同 hash 才跳过）"
CUR=$(current_target)
NEW_HASH=$(tree_hash "$STAGING" || true)
CUR_HASH=""
if [[ -n $CUR && -f $CUR/index.html ]]; then
  CUR_HASH=$(tree_hash "$CUR" || true)
  if [[ -n $CUR_HASH && "$CUR_HASH" == "$NEW_HASH" ]]; then
    warn "整树内容与线上完全一致（${CUR_HASH:0:16}…）→ 跳过切换（部署视为成功）"
    emit_hashes "$CUR_HASH" "$NEW_HASH"
    rm -rf -- "$STAGING"
    echo "RESULT=no-change"
    exit 0
  fi
  ok "整树内容与线上不同（线上 ${CUR_HASH:0:16}… / 本次 ${NEW_HASH:0:16}…）⇒ 继续切换"
fi
emit_hashes "$CUR_HASH" "$NEW_HASH"

log "5/7 就位为新版本 $NEW + 原子切换"
mv "$STAGING" "$NEW"
switch_to "$NEW"

log "6/7 切换后自检（失败自动回滚）"
if ! http_selfcheck "$INDEX_SZ"; then
  warn "自检失败 → 自动回滚"
  PREV=$(cat "$PREV_FILE" 2>/dev/null || true)
  if [[ -n $PREV && -d $PREV ]]; then
    ln -sfn "$PREV" "$SITE_LINK.tmp"; mv -T "$SITE_LINK.tmp" "$SITE_LINK"
    warn "已回滚到 $PREV"
  else
    warn "没有可回滚的版本，保留当前（请人工检查）"
  fi
  die "本次发布失败并已回滚"
fi
ok "自检通过（HTTP 200 / $INDEX_SZ B）"

log "7/7 清理旧版本（保留最近 $KEEP 个）"
prune_old

# 记一份发布指纹，方便事后比对
printf '%s  %s  tar=%s index=%s\n' "$(date -Is)" "$(readlink "$SITE_LINK")" "${INCOMING_SHA:0:16}" "$INDEX_SZ" \
  >> /opt/secagent/logs/site-releases.log 2>/dev/null || true
# 该日志可能属主不对（logs 目录 root），失败不影响主流程
chown root:root /opt/secagent/logs/site-releases.log 2>/dev/null || true

echo
echo "RESULT=ok"
echo "RELEASE=$(readlink "$SITE_LINK")"
echo "INDEX_BYTES=$INDEX_SZ"
echo "TAR_SHA256=$INCOMING_SHA"
echo "FILES=$(find "$(readlink "$SITE_LINK")" -type f | wc -l)"
echo "TOTAL_BYTES=$(du -sb "$(readlink "$SITE_LINK")" | cut -f1)"
ok "发布完成"
