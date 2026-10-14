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
MIN_INDEX_BYTES=20480      # 产物基本特征：index.html 必须 > 20 KB
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

log "4/7 幂等检查（与线上同 hash 就跳过）"
CUR=$(current_target)
if [[ -n $CUR && -f $CUR/index.html ]]; then
  if [[ "$(sha256sum "$CUR/index.html" | cut -d' ' -f1)" == "$(sha256sum "$STAGING/index.html" | cut -d' ' -f1)" ]]; then
    warn "index.html 与线上完全一致 → 内容无变化，跳过切换（部署视为成功）"
    rm -rf -- "$STAGING"
    echo "RESULT=no-change"
    exit 0
  fi
fi

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
