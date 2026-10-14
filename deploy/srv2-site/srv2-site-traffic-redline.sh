#!/usr/bin/env bash
# ============================================================
# srv2-site-traffic-redline.sh —— 给已有的流量脚本加"站点素材 ≤150GB/月"红线
# ------------------------------------------------------------
# 背景（父 agent 2026-10-14 定）：srv2 是 300GB/月 流量包，隧道出向与公网直连出向都计入。
#   站点素材体量大（37-clip medium tier 就 48MB），必须单独压一条红线：
#     · ≤150GB/月：站点素材的安全水位（留一半给检测/告警/备份等其它出网）
#     · 越过 150GB → 级别至少 HIGH，通知里明说"越过站点素材红线"
#   同时把这一项挂进现有日报/告警（srv2-static-daily.sh → srv2-static-traffic.sh 已经串好）。
# 做法：只【追加】逻辑与字段，不动既有阈值语义（100/200/270GB）与通知冷却机制。
# 用法： sudo bash srv2-site-traffic-redline.sh
# ============================================================
set -euo pipefail

T=/opt/secagent/scripts/srv2-static-traffic.sh
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/opt/secagent/backups/traffic-redline-$STAMP

log() { echo -e "\n\033[1;36m==> $*\033[0m"; }
ok()  { echo -e "  \033[1;32m[OK]\033[0m $*"; }
die() { echo -e "  \033[1;31m[X]\033[0m $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "需要 root"
[[ -s $T ]] || die "找不到 $T"

log "1/4 备份"
install -d -m 0700 "$BACKUP"
cp -a "$T" "$BACKUP/srv2-static-traffic.sh.before"
sha256sum "$T" | sed 's/^/  /'

log "2/4 打补丁（幂等：已打过就跳过）"
python3 - "$T" <<'PY'
import sys, io
p = sys.argv[1]
s = io.open(p, encoding='utf-8').read()

if 'SITE_REDLINE_BYTES' in s:
    print("  已含红线逻辑，跳过")
    raise SystemExit(0)

# 1) 常量
anchor = 'RESET_DATE="2026-11-11"'
assert anchor in s, "找不到 RESET_DATE 锚点"
const = anchor + '''

# —— 站点素材红线（2026-10-14 定）——
# 300GB/月 的包里，站点素材（Hugo 产物 + kurisu 素材 + 图片）单独压 ≤150GB/月：
#   留一半给检测/告警/备份等其它出网；越线就不再是"能跑就行"，必须处置。
# 口径提醒：nginx 的 $body_bytes_sent 把【隧道回源】与【公网 443 直连】都算进来了，
#   也包含本机自检那几百字节（可忽略，只会略微高估）。
SITE_REDLINE_BYTES=$((150 * 1000 * 1000 * 1000))'''
s = s.replace(anchor, const, 1)

# 2) 级别判定：越红线时把级别抬到至少 HIGH
anchor2 = '[ "$USED" -ge "$CRIT_BYTES" ] && LEVEL=CRITICAL'
assert anchor2 in s, "找不到 CRITICAL 锚点"
extra = anchor2 + '''

# 站点素材红线：越线即至少 HIGH（不降级，CRITICAL 保持）
REDLINE=0
if [ "$USED" -ge "$SITE_REDLINE_BYTES" ]; then
  REDLINE=1
  case "$LEVEL" in OK|LOW|MEDIUM) LEVEL=HIGH ;; esac
fi'''
s = s.replace(anchor2, extra, 1)

# 3) 报告行加字段
old_line = 'LINE="$(date \'+%F %T\')  used=$(human "$USED")  log=$(human "$LOG_BYTES")  baseline=$(human "$BASELINE")  pct=${pct_int}.${pct_dec}%  level=$LEVEL  距重置($RESET_DATE) ${days_left} 天${proj}"'
assert old_line in s, "找不到 LINE 锚点"
new_line = ('rl_pct=$((USED * 1000 / SITE_REDLINE_BYTES))\n'
            'LINE="$(date \'+%F %T\')  used=$(human "$USED")  log=$(human "$LOG_BYTES")  baseline=$(human "$BASELINE")  '
            'pct=${pct_int}.${pct_dec}%  site_redline=150GB($((rl_pct / 10)).$((rl_pct % 10))%)  level=$LEVEL  '
            '距重置($RESET_DATE) ${days_left} 天${proj}"')
s = s.replace(old_line, new_line, 1)

# 4) 通知正文加红线段
anchor3 = '流量包重置日：$RESET_DATE（还有 ${days_left} 天）${proj}'
assert anchor3 in s, "找不到 BODY 锚点"
body_extra = anchor3 + '''

站点素材红线：≤150GB/月 —— 当前 $(human "$USED")，占红线 $((USED * 100 / SITE_REDLINE_BYTES))%
$( [ "$REDLINE" = "1" ] && echo "【已越过 150GB/月 站点素材红线】先查是不是被刷/素材没走缓存，再决定限流或收窄 ingress" || true )'''
s = s.replace(anchor3, body_extra, 1)

io.open(p, 'w', encoding='utf-8').write(s)
print("  补丁已写入（常量 + 级别判定 + 报告字段 + 通知正文）")
PY

log "3/4 语法检查 + 干跑"
bash -n "$T" && ok "bash -n 通过"
bash "$T" --dry 2>&1 | sed 's/^/  /' || true

log "4/4 落地产物"
sha256sum "$T" | sed 's/^/  /'
echo "  --- 新增片段 ---"
grep -n 'SITE_REDLINE_BYTES\|REDLINE=\|site_redline' "$T" | sed 's/^/  /'
ok "完成（备份：$BACKUP）"
