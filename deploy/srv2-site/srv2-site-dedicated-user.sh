#!/usr/bin/env bash
# ============================================================
# srv2-site-dedicated-user.sh —— 给站点服务一个**独立低权用户**（对齐 Dionaea 先例的口径）
# ------------------------------------------------------------
# 现状：secagent-static.service 以通用账号 www-data 运行（虽然已有 systemd 沙箱）。
# 目标：专用系统账号 `xksite`（no-login、无 home），并把这些只读它的东西交给它：
#   · /var/log/nginx、/var/lib/nginx（写日志/临时）
#   · /etc/ssl/secagent（读私钥：root:xksite 0640）
#   · /var/www/acme（ACME 挑战 webroot，保持 0755 可读）
# 保留：ReadOnlyPaths=/opt/secagent/static /opt/secagent/releases（内容仍只读）
#       CPUQuota=25% MemoryMax=128M TasksMax=64（资源上限不变）
# 纪律：备份 → 改 → 校验 → 重启后立刻自检；不对就整段回滚。
# 用法： sudo bash srv2-site-dedicated-user.sh
# ============================================================
set -uo pipefail

SVCUSER=xksite
UNIT=/etc/systemd/system/secagent-static.service
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/opt/secagent/backups/dedicated-user-$STAMP

log() { echo -e "\n\033[1;36m==> $*\033[0m"; }
ok()  { echo -e "  \033[1;32m[OK]\033[0m $*"; }
warn(){ echo -e "  \033[1;33m[!]\033[0m $*"; }
die() { echo -e "  \033[1;31m[X]\033[0m $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "需要 root"

log "1/6 备份单元 + 现有属主快照"
install -d -m 0700 "$BACKUP"
cp -a "$UNIT" "$BACKUP/secagent-static.service.before"
stat -c '%U:%G %a %n' /var/log/nginx /var/lib/nginx /etc/ssl/secagent /etc/ssl/secagent/* /var/www/acme 2>/dev/null | sed 's/^/  /' > "$BACKUP/owners.before"
cat "$BACKUP/owners.before"

log "2/6 建独立系统账号 $SVCUSER"
if id "$SVCUSER" >/dev/null 2>&1; then ok "已存在：$(id "$SVCUSER")"; else
  useradd --system --no-create-home --shell /usr/sbin/nologin "$SVCUSER"
  ok "已创建：$(id "$SVCUSER")"
fi

log "3/6 改单元 User/Group（保留沙箱与限额）"
sed -i "s|^User=.*$|User=$SVCUSER|; s|^Group=.*$|Group=$SVCUSER|" "$UNIT"
systemctl daemon-reload
grep -E '^User=|^Group=|^ReadOnlyPaths=|^CPUQuota=|^MemoryMax=|^AmbientCapabilities=' "$UNIT" | sed 's/^/  /'

log "4/6 移交属主（日志/临时/证书/ACME）"
chown -R "$SVCUSER:$SVCUSER" /var/log/nginx /var/lib/nginx
chown "root:$SVCUSER" /etc/ssl/secagent
chmod 0750 /etc/ssl/secagent
chown "root:$SVCUSER" /etc/ssl/secagent/site-fullchain.pem /etc/ssl/secagent/site-privkey.pem
chmod 0644 /etc/ssl/secagent/site-fullchain.pem
chmod 0640 /etc/ssl/secagent/site-privkey.pem
chown -R "$SVCUSER:$SVCUSER" /var/www/acme 2>/dev/null || true
stat -c '%U:%G %a %n' /var/log/nginx /var/lib/nginx /etc/ssl/secagent /etc/ssl/secagent/* /var/www/acme 2>/dev/null | sed 's/^/  /'

log "5/6 重启并自检"
rm -rf /run/nginx
systemctl restart secagent-static
sleep 2
printf '  is-active: %s\n' "$(systemctl is-active secagent-static)"
printf '  MainPID user: %s\n' "$(ps -o user= -p "$(systemctl show secagent-static -p MainPID --value)" 2>/dev/null)"
echo "  --- 三面自检 ---"
printf '  回环 site    xiaokeqing.cn        -> %s\n' "$(curl -s -o /dev/null -w '%{http_code} %{size_download}' -H 'Host: xiaokeqing.cn' http://127.0.0.1:18080/)"
printf '  回环 assets  static.xiaokeqing.cn -> %s\n' "$(curl -s -o /dev/null -w '%{http_code} %{size_download}' -H 'Host: static.xiaokeqing.cn' http://127.0.0.1:18080/)"
printf '  公网 443 (Host 头)                -> %s\n' "$(curl -sk -o /dev/null -w '%{http_code} %{size_download}' -H 'Host: xiaokeqing.cn' https://10.0.0.10/)"
printf '  公网 80 跳转                      -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: xiaokeqing.cn' http://10.0.0.10/)"
echo "  --- 隧道侧 ---"
printf '  cloudflared-static: %s\n' "$(systemctl is-active cloudflared-static)"

if [[ "$(systemctl is-active secagent-static)" != "active" ]]; then
  warn "服务没起来 → 回滚单元与属主"
  cp -a "$BACKUP/secagent-static.service.before" "$UNIT"
  chown -R www-data:www-data /var/log/nginx /var/lib/nginx 2>/dev/null || true
  chown root:www-data /etc/ssl/secagent /etc/ssl/secagent/*
  systemctl daemon-reload; systemctl restart secagent-static
  die "已回滚（服务应已恢复），请把 journalctl -u secagent-static 的输出给我"
fi

log "6/6 让并发会话的自检脚本也过一遍"
bash /opt/secagent/scripts/srv2-static-check.sh 2>&1 | tail -4 | sed 's/^/  /'
echo
sha256sum "$UNIT" | sed 's/^/  /'
ok "完成（备份：$BACKUP；用户：$SVCUSER）"
