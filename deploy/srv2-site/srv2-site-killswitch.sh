#!/usr/bin/env bash
# ============================================================
# srv2-site-killswitch.sh —— 公网直连入口的一键开关（off = 一步回到"只走隧道"）
# ------------------------------------------------------------
# off 做三件事（顺序有意为之：先断公网可达，再收掉监听）：
#   1) ufw 删掉 80/443 放行  → 外部立刻连不上（云安全组仍是站主那一层，若没放行则本来就不通）
#   2) nginx.conf 换成「隧道版」变体（只有回环 18080 的 static + site 两块）→ 公网监听消失
#   3) 重启服务 + 自检隧道侧仍然 200（写站点不能因为关直连而挂）
# on 反向恢复（含 ufw 放行）。
#
# 关键：off **不影响** Cloudflare 隧道路径（cloudflared-static.service 不动，
#       127.0.0.1:18080 仍在），所以关掉直连后站点继续可用。
#
# 用法（srv2，root）：
#   sudo bash srv2-site-killswitch.sh off      # 关闭公网直连
#   sudo bash srv2-site-killswitch.sh on       # 打开公网直连
#   sudo bash srv2-site-killswitch.sh status   # 只看状态，不改
# 变体文件：/opt/secagent/backups/site-nginx/nginx.{public,tunnel-only}.conf
# ============================================================
set -uo pipefail

VARIANTS=/opt/secagent/backups/site-nginx
CONF=/etc/nginx/nginx.conf
PUBLIC=$VARIANTS/nginx.public.conf
TUNNEL=$VARIANTS/nginx.tunnel-only.conf
UNIT=secagent-static.service

ok()   { echo "  [OK] $*"; }
warn() { echo "  [!] $*"; }
die()  { echo "  [X] $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "需要 root"

nginx_apply() { # $1 = 要落盘的变体
  local src=$1
  [[ -s $src ]] || die "变体不存在或为空：$src"
  nginx -t -c "$src" >/dev/null 2>&1 || { nginx -t -c "$src" 2>&1 | sed 's/^/    /'; die "变体 $src 语法不过，未落盘"; }
  cp -a "$CONF" "/tmp/nginx.conf.prev.$$"
  cp -a "$src" "$CONF"
  chmod 0644 "$CONF"; chown root:root "$CONF"
  # root 跑过 nginx -t 会把日志弄成 root:root，服务降权后打不开 → 立刻修回
  rm -f /var/log/nginx/secagent-static-access.log /var/log/nginx/secagent-static-traffic.log
  chown -R xksite:xksite /var/log/nginx /var/lib/nginx 2>/dev/null || true
  systemctl restart "$UNIT"
  sleep 2
}

check_tunnel() {
  local c
  c=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: xiaokeqing.cn' http://127.0.0.1:18080/ || echo 000)
  printf '  隧道侧（回环 18080，Host: xiaokeqing.cn）-> HTTP %s\n' "$c"
  [[ $c == "200" ]] && ok "隧道路径健康" || warn "隧道路径异常（HTTP $c）—— 立即人工介入"
  c=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: static.xiaokeqing.cn' http://127.0.0.1:18080/ || echo 000)
  printf '  素材站（回环 18080，Host: static.xiaokeqing.cn）-> HTTP %s\n' "$c"
}

show_status() {
  echo "== 当前 nginx.conf =="
  if grep -q '公网 443' "$CONF"; then echo "  公网版（含 80/443 监听）"; else echo "  隧道版（只有回环 18080）"; fi
  echo "== 监听 =="
  ss -tlnp 2>/dev/null | grep -E ':(80|443|18080) ' | sed 's/^/  /' || echo "  （无 80/443/18080）"
  echo "== ufw 里的 80/443 =="
  ufw status 2>/dev/null | grep -E '^(80|443)/tcp' | sed 's/^/  /' || echo "  （无放行）"
  echo "== 服务 =="
  printf '  %s: %s\n' "$UNIT" "$(systemctl is-active $UNIT)"
  printf '  cloudflared-static: %s\n' "$(systemctl is-active cloudflared-static)"
  echo "== 隧道连通性 =="
  check_tunnel
}

case "${1:-status}" in
  off)
    echo "==> 关闭公网直连（保留隧道路径）"
    ufw delete allow 80/tcp  >/dev/null 2>&1 || true
    ufw delete allow 443/tcp >/dev/null 2>&1 || true
    ok "ufw 已撤销 80/443 放行"
    nginx_apply "$TUNNEL"
    ok "已切到隧道版配置并重启"
    show_status
    ;;
  on)
    echo "==> 打开公网直连"
    nginx_apply "$PUBLIC"
    ok "已切到公网版配置并重启"
    ufw allow 80/tcp  comment 'blog http -> https redirect + ACME' >/dev/null
    ufw allow 443/tcp comment 'blog direct https (read-only static)' >/dev/null
    ok "ufw 已放行 80/443"
    show_status
    ;;
  status|*)
    show_status
    ;;
esac
