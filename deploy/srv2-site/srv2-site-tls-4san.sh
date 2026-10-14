#!/usr/bin/env bash
# ============================================================
# srv2-site-tls-4san.sh —— 主域名 DNS 一变就"一条命令补签 4-SAN"
# ------------------------------------------------------------
# 为什么单独写一个（而不是复用 srv2-site-tls-issue.sh）：
#   切换主域名后有一个"证书还没覆盖 xiaokeqing.cn/www"的窗口，
#   目标是把窗口压到 **40 秒内**。所以这里只做最短路径：
#     解析检查 → certbot（HTTP-01 webroot）→ hook 同步 → reload → 验证
#   不再重复做 ACME patch / 备份 / 说明（那些已经就位）。
#
# 用法（srv2，root）：
#   sudo bash srv2-site-tls-4san.sh                 # 默认四域名
#   sudo bash srv2-site-tls-4san.sh --wait=180      # 先等域名解析就位（最多 180s），再签
# 退出码：0 = 签发并生效；非 0 = 失败（脚本会打印 certbot 的失败原因）
# ============================================================
set -uo pipefail

DOMAINS=(xiaokeqing.cn www.xiaokeqing.cn direct.xiaokeqing.cn static.xiaokeqing.cn)
# 公网 80/443 绑在私网 IP 上（腾讯云 EIP 1:1 NAT）；本机自检必须用私网 IP
# —— 用公网 IP 从本机会 hairpin 失败（脚本早期版本就踩过：000）
PRIV_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -1)
PRIV_IP=${PRIV_IP:-10.0.0.10}
CERT_NAME=xk-site
ACME_ROOT=/var/www/acme
WAIT=0
case "${1:-}" in
  --wait=*) WAIT="${1#--wait=}" ;;
  "") ;;
  *) echo "用法: $0 [--wait=秒]"; exit 2 ;;
esac
[[ $EUID -eq 0 ]] || { echo "[X] 需要 root"; exit 1; }

t0=$(date +%s)
echo "== 0) 解析检查（必须全部指向本机 43.143.114.79）=="
ok_all=1
for d in "${DOMAINS[@]}"; do
  ips=$(getent ahostsv4 "$d" | awk '{print $1}' | sort -u | tr '\n' ' ')
  printf '  %-26s -> %s\n' "$d" "${ips:-（无解析）}"
  case " $ips " in *" 43.143.114.79 "*) ;; *) ok_all=0 ;; esac
done
if [[ $ok_all -eq 0 && $WAIT -gt 0 ]]; then
  echo "  [!] 还有域名没指到本机 → 最多等 ${WAIT}s（每 5s 复查）"
  deadline=$((t0 + WAIT))
  while [[ $(date +%s) -lt $deadline ]]; do
    sleep 5; ok_all=1
    for d in "${DOMAINS[@]}"; do
      case " $(getent ahostsv4 "$d" | awk '{print $1}' | sort -u | tr '\n' ' ') " in *" 43.143.114.79 "*) ;; *) ok_all=0 ;; esac
    done
    [[ $ok_all -eq 1 ]] && break
  done
fi
if [[ $ok_all -eq 0 ]]; then
  echo "  [X] 有域名还没指向本机 —— 现在签会失败。停手（DNS 就绪后重跑本脚本）"
  exit 3
fi
echo "  [OK] 四域名都指向本机"

echo
echo "== 1) 公网 80 上的 ACME 路径自检 =="
for d in "${DOMAINS[@]}"; do
  printf '  %-26s -> %s\n' "$d" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 -H "Host: $d" "http://$PRIV_IP/.well-known/acme-challenge/probe-$$" || echo 000)"
done
echo "（404 = 路径通了、只是这个 token 不存在；000/403/405 才是有问题）"

echo
echo "== 2) certbot 签发 4-SAN =="
ARGS=(); for d in "${DOMAINS[@]}"; do ARGS+=( -d "$d" ); done
certbot certonly --webroot -w "$ACME_ROOT" --cert-name "$CERT_NAME" --expand \
  --non-interactive --agree-tos --no-eff-email --email ops@xiaokeqing.cn "${ARGS[@]}" 2>&1 | tail -12
rc=${PIPESTATUS[0]}
if [[ $rc -ne 0 ]]; then echo "  [X] certbot 退出码 $rc —— 没签成，站点仍用旧证书（不会更糟）"; exit $rc; fi

echo
echo "== 3) 同步 + reload =="
bash /etc/letsencrypt/renewal-hooks/deploy/xk-site-sync.sh && echo "  sync+reload ok"
sleep 1

echo
echo "== 4) 生效验证 =="
openssl x509 -in /etc/ssl/secagent/site-fullchain.pem -noout -subject -issuer -dates -ext subjectAltName | sed 's/^/  /'
for d in "${DOMAINS[@]}"; do
  echo | timeout 10 openssl s_client -connect 10.0.0.10:443 -servername "$d" 2>/dev/null \
    | openssl x509 -noout -ext subjectAltName 2>/dev/null | tail -1 | sed "s/^/  SNI=$d → /"
done
echo
echo "  用时：$(( $(date +%s) - t0 )) 秒"
