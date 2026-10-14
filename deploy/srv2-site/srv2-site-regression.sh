#!/usr/bin/env bash
# ============================================================
# srv2-site-regression.sh —— 开公网 443 之后的回归证据包（只读，不改任何东西）
# ------------------------------------------------------------
# 覆盖父 agent 点名的三样 + 两样我自己加的：
#   1) DOCKER-USER 规则原文与顺序（ESTABLISHED → DNS → DROP → 端口 ACCEPT）
#   2) 蜜罐隔离【实测】探针（/usr/local/sbin/srv2-honeypot-egress-probe.sh，fail-closed）
#   3) 诱饵端口三层状态（srv2-decoy-ports.sh --plan）
#   4) 7 个容器是否仍 Up
#   5) 本机监听面：新增的只有 10.0.0.10:80/443，不得出现 0.0.0.0:80/443 或别的意外公网监听
# 用法（srv2，root）：bash srv2-site-regression.sh
#   退出码：0 = 全过；1 = 有过不去的；2 = 测量无效
# ============================================================
set -uo pipefail
FAIL=0; INVALID=0
ok()   { echo "  [OK] $*"; }
bad()  { echo "  [X]  $*"; FAIL=$((FAIL+1)); }
warn() { echo "  [!]  $*"; }
sec()  { echo; echo "===== $* ====="; }

sec "1) DOCKER-USER 顺序（隔离的兜底 DROP 必须排在端口放行之前）"
iptables -S DOCKER-USER | sed 's/^/  /'
DROP_LINE=$(iptables -S DOCKER-USER | grep -n -- '-s 172.19.0.0/16 -j DROP' | head -1 | cut -d: -f1)
PORT_LINE=$(iptables -S DOCKER-USER | grep -n -- '--dport' | head -1 | cut -d: -f1)
if [ -z "$DROP_LINE" ]; then bad "DOCKER-USER 里找不到 172.19.0.0/16 的 DROP"
elif [ -n "$PORT_LINE" ] && [ "$DROP_LINE" -gt "$PORT_LINE" ]; then bad "顺序错：端口放行(第 $PORT_LINE 行) 早于 DROP(第 $DROP_LINE 行)"
else ok "DROP 在第 $DROP_LINE 行，端口放行自第 ${PORT_LINE:-无} 行起 → 顺序正确"; fi
echo "  --- ESTABLISHED / DNS 两条是否仍在最前 ---"
head -3 <(iptables -S DOCKER-USER | grep -E 'RELATED,ESTABLISHED|127.0.0.11') | sed 's/^/    /'

sec "2) 蜜罐隔离【实测】探针（会起临时容器 + tcpdump 抓包，约 2 分钟）"
PROBE=/usr/local/sbin/srv2-honeypot-egress-probe.sh
if [ -x "$PROBE" ]; then
  timeout 300 bash "$PROBE"; RC=$?
  echo "  probe rc=$RC"
  case $RC in
    0) ok "隔离实测通过（蜜罐网段对外 SYN 全 0，且对照组证明测量有效）" ;;
    2) bad "测量无效（rc=2）—— 不许当通过"; INVALID=1 ;;
    *) bad "隔离有问题（rc=$RC）" ;;
  esac
else
  bad "探针不存在：$PROBE"
fi

sec "3) 诱饵端口三层状态"
timeout 120 bash /opt/secagent/scripts/srv2-decoy-ports.sh --plan 2>&1 | sed 's/^/  /' || warn "decoy --plan 退出码非 0"

sec "4) 容器（应为 7 个全部 Up）"
N=$(docker ps --format '{{.Names}}' | wc -l)
docker ps --format '  {{.Names}} | {{.Status}}' | sort
echo "  容器数：$N"
if [ "$N" -eq 7 ]; then ok "7 个容器都在跑"; else bad "容器数 $N ≠ 7"; fi
DOWN=$(docker ps -a --filter 'status=exited' --format '{{.Names}}' | wc -l)
[ "$DOWN" -eq 0 ] && ok "没有被 stop 的容器" || warn "有 $DOWN 个 exited 容器（可能是本来就停的，如 srv2-dionaea.service 的旧单元）"

sec "5) 监听面（新增只允许 10.0.0.10:80 与 10.0.0.10:443）"
ss -tlnp 2>/dev/null | awk 'NR==1 || $4 !~ /^127\./ {print "  "$0}'
for bad_port in ':0.0.0.0:80' ':0.0.0.0:443' '0.0.0.0:80 ' '0.0.0.0:443 '; do :; done
if ss -tln | awk '{print $4}' | grep -qxE '0\.0\.0\.0:443|\[::\]:443'; then bad "0.0.0.0:443 或 [::]:443 在监听（不符预期）"; else ok "没有 0.0.0.0:443（Wazuh 的 127.0.0.1:443 未受影响）"; fi
if ss -tln | awk '{print $4}' | grep -qxE '0\.0\.0\.0:80|\[::\]:80'; then bad "0.0.0.0:80 在监听（不符预期）"; else ok "没有 0.0.0.0:80"; fi
ss -tln | grep -q '10.0.0.10:80'  && ok "10.0.0.10:80 在监听"  || warn "10.0.0.10:80 没在监听（公网 HTTP 跳转不可用）"
ss -tln | grep -q '10.0.0.10:443' && ok "10.0.0.10:443 在监听" || warn "10.0.0.10:443 没在监听（公网 HTTPS 不可用）"
ss -tln | grep -q '127.0.0.1:443' && ok "127.0.0.1:443 仍是 Wazuh 的（docker-proxy）" || warn "127.0.0.1:443 不见了"

sec "6) 隧道侧回归（不能因为开直连把原路径弄坏）"
for h in static.xiaokeqing.cn xiaokeqing.cn www.xiaokeqing.cn staging.xiaokeqing.cn; do
  c=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $h" http://127.0.0.1:18080/ || echo 000)
  printf '  %-24s -> %s\n' "$h" "$c"
  [ "$c" = "200" ] || bad "$h 回环不是 200（$c）"
done
systemctl is-active secagent-static | sed 's/^/  secagent-static: /'
systemctl is-active cloudflared-static | sed 's/^/  cloudflared-static: /'

sec "结论"
if [ "$FAIL" -eq 0 ] && [ "$INVALID" -eq 0 ]; then echo "  [PASS] 回归全过"; exit 0; fi
if [ "$INVALID" -eq 1 ]; then echo "  [INVALID] 有测量无效项 + $FAIL 项不通过"; exit 2; fi
echo "  [FAIL] $FAIL 项不通过"; exit 1
