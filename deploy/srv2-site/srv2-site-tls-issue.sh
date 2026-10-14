#!/usr/bin/env bash
# ============================================================
# srv2-site-tls-issue.sh —— 用 Let's Encrypt 签发/续期站点证书（HTTP-01）
# ------------------------------------------------------------
# 为什么 HTTP-01 能过（关键设计）：
#   LE 只能访问 80 端口上的 <域名>/.well-known/acme-challenge/<token>。
#   所以我们在【所有】server 块里都挂上同一个 ACME webroot（/var/www/acme）：
#     · 公网 80 块（10.0.0.10:80）  → 域名 A 记录直接指向 srv2 时走这条
#     · 回环 18080 块（隧道侧）      → 域名仍是 Cloudflare 橙云、经隧道回源到 srv2 时走这条
#   于是无论域名当前是"直连 srv2"还是"走 CF 隧道回源到 srv2"，HTTP-01 都能验证通过。
#   注意：域名若仍指向 GitHub Pages（橙云 + Pages 源站），验证必然失败 —— 那是正确行为。
#
# 产物：
#   /etc/letsencrypt/live/xk-site/                          （certbot 管）
#   /etc/ssl/secagent/site-fullchain.pem|site-privkey.pem   （nginx 读的稳定路径，root:xksite）
#   /etc/letsencrypt/renewal-hooks/deploy/xk-site-sync.sh   （续期后自动同步 + reload nginx）
# 用法（srv2，root）：
#   sudo bash srv2-site-tls-issue.sh                      # 默认只签 static.xiaokeqing.cn
#   sudo bash srv2-site-tls-issue.sh --dry                # 只做前置与 patch，不签发
#   sudo bash srv2-site-tls-issue.sh -d a.cn -d b.cn      # 指定域名（--expand 扩展同一张证书）
# ============================================================
set -uo pipefail

CONF=/etc/nginx/nginx.conf
LOCS=/etc/nginx/xk-site-locations.conf
ACME_ROOT=/var/www/acme
CERTDIR=/etc/ssl/secagent
CERT_NAME=xk-site
VARIANTS=/opt/secagent/backups/site-nginx
EMAIL=${LE_EMAIL:-ops@xiaokeqing.cn}
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/opt/secagent/backups/nginx-acme-$STAMP

log() { echo -e "\n\033[1;36m==> $*\033[0m"; }
ok()  { echo -e "  \033[1;32m[OK]\033[0m $*"; }
warn(){ echo -e "  \033[1;33m[!]\033[0m $*"; }
die() { echo -e "  \033[1;31m[X]\033[0m $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "需要 root"

DOMAINS=()
DRY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry) DRY=1; shift ;;
    -d) DOMAINS+=("$2"); shift 2 ;;
    *) die "未知参数：$1" ;;
  esac
done
[[ ${#DOMAINS[@]} -eq 0 ]] && DOMAINS=(static.xiaokeqing.cn)

log "1/7 前置：certbot + ACME webroot"
install -d -o xksite -g xksite -m 0755 "$ACME_ROOT"
install -d -o root -g xksite -m 0750 "$CERTDIR"
if ! command -v certbot >/dev/null 2>&1; then
  warn "没装 certbot，apt 安装中…"
  DEBIAN_FRONTEND=noninteractive timeout 300 apt-get install -y --no-install-recommends certbot 2>&1 | tail -3
fi
command -v certbot >/dev/null 2>&1 || die "certbot 装不上"
ok "$(certbot --version 2>&1)"

log "2/7 备份 nginx 配置"
install -d -m 0700 "$BACKUP"
cp -a "$CONF" "$BACKUP/nginx.conf.before"
[[ -f $LOCS ]] && cp -a "$LOCS" "$BACKUP/xk-site-locations.conf.before" || true
ok "$BACKUP"

log "3/7 给所有 server 块挂上 ACME webroot（幂等，带标记）"
python3 - "$CONF" "$LOCS" "$ACME_ROOT" <<'PY'
import re, sys

conf, locs, acme = sys.argv[1], sys.argv[2], sys.argv[3]
MARK = "# --- ACME HTTP-01 (managed by srv2-site-tls-issue.sh) ---"
BLOCK = (MARK + "\n"
         "        location ^~ /.well-known/acme-challenge/ {\n"
         f"            root {acme};\n"
         "            default_type text/plain;\n"
         "            try_files $uri =404;\n"
         "        }")

# 1) location 集（整站：隧道块 + 公网 443 块共用）
s = open(locs, encoding='utf-8').read()
if MARK in s:
    print("  location 集：已有 ACME 块（跳过）")
else:
    open(locs, 'w', encoding='utf-8').write(BLOCK + "\n" + s)
    print("  location 集：已插入 ACME 块")

# 2) nginx.conf 里每个 listen 127.0.0.1:18080 的 server 块（素材站 + 整站）
c = open(conf, encoding='utf-8').read()
if MARK in c:
    print("  nginx.conf：已有 ACME 块（跳过）")
else:
    lines = c.split('\n')
    out, i, added = [], 0, 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        if re.match(r'\s*server\s*\{', ln):
            depth, j, listen18080, first_loc = 1, i + 1, False, None
            while j < n:
                l2 = lines[j]
                if first_loc is None and re.match(r'\s*location\s', l2):
                    first_loc = j
                if 'listen 127.0.0.1:18080' in l2:
                    listen18080 = True
                depth += l2.count('{') - l2.count('}')
                j += 1
                if depth <= 0:
                    break
            if listen18080 and first_loc is not None:
                out.extend(lines[i:first_loc])
                out.append(BLOCK)
                out.extend(lines[first_loc:j])
                added += 1
            else:
                out.extend(lines[i:j])
            i = j
            continue
        out.append(ln)
        i += 1
    open(conf, 'w', encoding='utf-8').write('\n'.join(out))
    print(f"  nginx.conf：给 {added} 个回环 server 块插入了 ACME 块")
PY
echo "  --- acme-challenge 出现次数（conf / locations）---"
grep -c 'acme-challenge' "$CONF" | sed 's/^/   conf: /'
grep -c 'acme-challenge' "$LOCS" | sed 's/^/   locs: /'

log "4/7 nginx -t → 修日志属主 → 重启（再同步两个变体）"
nginx -t 2>&1 | sed 's/^/  /' || die "配置语法不过，备份在 $BACKUP"
rm -f /var/log/nginx/secagent-static-access.log /var/log/nginx/secagent-static-traffic.log
chown -R xksite:xksite /var/log/nginx /var/lib/nginx 2>/dev/null || true
systemctl restart secagent-static
sleep 2
systemctl is-active secagent-static | sed 's/^/  is-active: /'
if grep -q '公网 443' "$CONF"; then
  cp -a "$CONF" "$VARIANTS/nginx.public.conf"
  sed -e '/# ③ 公网 80/,$d' "$CONF" > "$VARIANTS/nginx.tunnel-only.conf"
  printf '}\n' >> "$VARIANTS/nginx.tunnel-only.conf"
  ok "两个变体已同步"
fi
echo "  --- ACME 路径自检（回环；应 404 而不是 403/405）---"
for h in static.xiaokeqing.cn xiaokeqing.cn; do
  printf '    %-24s -> %s\n' "$h" "$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $h" "http://127.0.0.1:18080/.well-known/acme-challenge/probe-$STAMP")"
done

log "5/7 续期后的同步钩子（copy 到 nginx 读的稳定路径 + reload）"
install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/xk-site-sync.sh <<'HOOK'
#!/usr/bin/env bash
# certbot 续期成功后：把证书同步到 nginx 读的稳定路径并 reload
set -euo pipefail
SRC=/etc/letsencrypt/live/xk-site
DST=/etc/ssl/secagent
[ -s "$SRC/fullchain.pem" ] || exit 0
install -m 0644 -o root -g xksite "$SRC/fullchain.pem" "$DST/site-fullchain.pem"
install -m 0640 -o root -g xksite "$SRC/privkey.pem"   "$DST/site-privkey.pem"
# reload 需要 pid 文件在位（踩过：删了 pid 再 reload 必失败）
systemctl reload secagent-static || systemctl restart secagent-static
HOOK
chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/xk-site-sync.sh
ok "钩子就位"

if [[ $DRY -eq 1 ]]; then
  warn "--dry：只做了前置与 patch，未签发"
  exit 0
fi

log "6/7 签发 Let's Encrypt（HTTP-01 webroot）"
ARGS=()
for d in "${DOMAINS[@]}"; do ARGS+=( -d "$d" ); done
certbot certonly --webroot -w "$ACME_ROOT" --cert-name "$CERT_NAME" --expand \
  --non-interactive --agree-tos --no-eff-email --email "$EMAIL" \
  --keep-until-expiring "${ARGS[@]}" 2>&1 | sed 's/^/  /'
RC=${PIPESTATUS[0]}
if [[ $RC -ne 0 ]]; then
  warn "certbot 退出码 $RC —— 常见原因：该域名的 A 记录还没指向本机，或仍是 CF 橙云 + Pages 源站"
  warn "srv2 上看到的解析："
  for d in "${DOMAINS[@]}"; do printf '    %s -> %s\n' "$d" "$(getent ahostsv4 "$d" | awk '{print $1}' | head -1)"; done
  exit $RC
fi

log "7/7 同步证书 + reload + 验证"
bash /etc/letsencrypt/renewal-hooks/deploy/xk-site-sync.sh
sleep 1
echo "  --- 证书信息（issuer 应不再是 xiaokeqing self-signed）---"
openssl x509 -in "$CERTDIR/site-fullchain.pem" -noout -subject -issuer -dates -ext subjectAltName | sed 's/^/  /'
echo "  --- 续期 timer ---"
systemctl list-timers --all --no-pager 2>/dev/null | grep -i certbot | sed 's/^/  /' || echo "  (没有 certbot.timer)"
sha256sum "$CERTDIR/site-fullchain.pem" "$CERTDIR/site-privkey.pem" "$CONF" "$LOCS" | sed 's/^/  /'
ok "完成"
