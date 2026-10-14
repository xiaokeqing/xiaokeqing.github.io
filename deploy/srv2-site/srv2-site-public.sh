#!/usr/bin/env bash
# ============================================================
# srv2-site-public.sh —— 给「博客整站」开公网直连入口（80/443，绕开 Cloudflare）
# ------------------------------------------------------------
# 站主 2026-10-14 批准：srv2 本来就有 21/23/445/1433/3306/6379/8080/8443/27017 对外，
# 多一个【只读静态】的 443 不改变机器定位。目标：
#   · 同一套宿主 nginx（不新起第二套 web 服务），公网仅 80 + 443
#   · 只读静态：只 GET/HEAD、autoindex off、无任何动态/上传/代理、无 Symlink 逃逸
#   · 限速与限连接：limit_req（30 r/s，burst 60）+ limit_conn（24/每 IP）+ 单连接速率上限
#   · 降权与加固：继续用 xksite + 现有 secagent-static.service 沙箱
#     （新增 AmbientCapabilities=CAP_NET_BIND_SERVICE —— 非 root 绑 <1024 端口必须要它）
#   · 日志：并入现有竖线流量口径（同一 access_log）
#   · 证书：先自签占位（SAN 覆盖四个域名），DNS 就绪后由 srv2-site-tls-issue.sh 换 Let's Encrypt
#
# 【关键约束 · 为什么是 listen 10.0.0.10:443 而不是 0.0.0.0:443】
#   srv2 上 127.0.0.1:443 已被 wazuh.dashboard 的 docker-proxy 占用
#   （docker ps: wazuh.dashboard | 127.0.0.1:443->5601/tcp）。
#   实测：0.0.0.0:443 即使带 SO_REUSEADDR 也绑不上（Address already in use），
#   但 10.0.0.10:443 可以绑（不同具体地址不冲突）。
#   腾讯云 EIP 是 1:1 NAT 到本机 eth0 的 10.0.0.10，所以公网 443 的流量正是落到这个地址。
#   ⇒ 这样既拿到真正的公网 443，又【完全不碰】Wazuh 的映射。
#
# 产物：
#   /etc/nginx/nginx.conf                          （可切换的“公网版”）
#   /etc/nginx/xk-site-locations.conf              （整站 location 集，隧道块与公网块共用）
#   /opt/secagent/backups/site-nginx/nginx.public.conf / nginx.tunnel-only.conf
#   /etc/ssl/secagent/site-fullchain.pem|site-privkey.pem
# 用法： sudo bash srv2-site-public.sh
# ============================================================
set -euo pipefail

CONF=/etc/nginx/nginx.conf
LOCS=/etc/nginx/xk-site-locations.conf
UNIT=/etc/systemd/system/secagent-static.service
VARIANTS=/opt/secagent/backups/site-nginx
CERTDIR=/etc/ssl/secagent
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/opt/secagent/backups/nginx-public-$STAMP
ACME_ROOT=/var/www/acme
PUB_IP_EXPECT=43.143.114.79

log() { echo -e "\n\033[1;36m==> $*\033[0m"; }
ok()  { echo -e "  \033[1;32m[OK]\033[0m $*"; }
warn(){ echo -e "  \033[1;33m[!]\033[0m $*"; }
die() { echo -e "  \033[1;31m[X]\033[0m $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "需要 root"
PRIV_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -1)
[[ -n $PRIV_IP ]] || die "拿不到本机私网 IP（用于 listen 绑定）"
ok "本机私网 IP：$PRIV_IP（公网 $PUB_IP_EXPECT 由云 NAT 1:1 映射到这里）"

# 绑不上就停手（避免写完配置后 nginx 起不来，把隧道那条路也弄挂）
python3 - "$PRIV_IP" <<'PY' || die "私有 IP:443 绑不上，停手"
import socket,sys
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
try:
    s.bind((sys.argv[1],443)); s.listen(1)
finally:
    s.close()
PY
ok "$PRIV_IP:443 可绑（127.0.0.1:443 仍留给 wazuh.dashboard，不冲突）"

log "1/8 备份（配置 + 单元 + iptables 全量）"
install -d -m 0700 "$BACKUP"
cp -a "$CONF" "$BACKUP/nginx.conf.before"
cp -a "$UNIT" "$BACKUP/secagent-static.service.before"
[[ -f $LOCS ]] && cp -a "$LOCS" "$BACKUP/xk-site-locations.conf.before" || true
iptables-save > "$BACKUP/iptables.before" 2>/dev/null || true
ip6tables-save > "$BACKUP/ip6tables.before" 2>/dev/null || true
ufw status verbose > "$BACKUP/ufw.before" 2>/dev/null || true
sha256sum "$CONF" "$UNIT" | sed 's/^/  /'
ok "备份目录：$BACKUP"

log "2/8 证书：自签占位（SAN 覆盖 xiaokeqing.cn / www / direct / static）"
install -d -o root -g xksite -m 0750 "$CERTDIR"
if [[ -f $CERTDIR/site-fullchain.pem && -f $CERTDIR/site-privkey.pem ]]; then
  ok "证书已存在（$(openssl x509 -in $CERTDIR/site-fullchain.pem -noout -enddate 2>/dev/null | cut -d= -f2)）——不覆盖"
else
  openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 90 \
    -keyout "$CERTDIR/site-privkey.pem" -out "$CERTDIR/site-fullchain.pem" \
    -subj "/CN=xiaokeqing.cn/O=xiaokeqing self-signed (pre-LE)" \
    -addext "subjectAltName=DNS:xiaokeqing.cn,DNS:www.xiaokeqing.cn,DNS:direct.xiaokeqing.cn,DNS:static.xiaokeqing.cn" \
    >/dev/null 2>&1
  chown root:xksite "$CERTDIR/site-privkey.pem" "$CERTDIR/site-fullchain.pem"
  chmod 0640 "$CERTDIR/site-privkey.pem"; chmod 0644 "$CERTDIR/site-fullchain.pem"
  ok "已生成自签证书（90 天）"
fi
openssl x509 -in "$CERTDIR/site-fullchain.pem" -noout -subject -enddate -ext subjectAltName 2>&1 | sed 's/^/  /'

log "3/8 写共用的 location 集 $LOCS（整站：隧道块与公网块共用，防两份配置漂移）"
cat > "$LOCS" <<'LOCS'
        # ============================================================
        # 博客整站 location 集（被「隧道 18080 块」与「公网 443 块」共用）
        #   · 只 GET/HEAD（server 级已 405 兜底，这里再 limit_except 一次）
        #   · 带扩展名的静态资源绝不回落到 index.html（缺图必须真 404）
        #   · /kurisu/** 与 /images/** 长缓存；css/js/json 短缓存；HTML no-cache
        # ============================================================
        location ~ ^/(kurisu|images)/ {
            limit_except GET { deny all; }
            try_files $uri =404;
            add_header Cache-Control "public, max-age=2592000" always;
            add_header X-Content-Type-Options nosniff always;
        }

        location ~* \.(?:woff2?|ttf|otf|eot|mp4|webm|mp3|ogg|avif|webp|png|jpe?g|gif|svg|ico)$ {
            limit_except GET { deny all; }
            try_files $uri =404;
            add_header Cache-Control "public, max-age=2592000" always;
            add_header X-Content-Type-Options nosniff always;
        }

        location ~* \.(?:css|js|mjs|json|xml|txt|map)$ {
            limit_except GET { deny all; }
            try_files $uri =404;
            add_header Cache-Control "public, max-age=300" always;
            add_header X-Content-Type-Options nosniff always;
        }

        # HTML / 目录 / SPA 兜底（hash 路由 SPA：/#/notes 这类都落在 /）
        location / {
            limit_except GET { deny all; }
            try_files $uri $uri/ /index.html;
            add_header Cache-Control "no-cache" always;
            add_header X-Content-Type-Options nosniff always;
        }

        # 隐藏文件/点文件一律拒绝
        location ~ /\. { deny all; }
LOCS
ok "已写入（$(wc -l < "$LOCS") 行）"

log "4/8 写公网版 nginx.conf（回环隧道块 + 公网 80/443）"
cat > /tmp/nginx.conf.public <<NGINXCONF
worker_processes 1;
pid /run/nginx/nginx.pid;
error_log stderr warn;

events { worker_connections 512; }

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # 两个口径的日志：
    #   access.log  = combined，给人看/排障
    #   traffic.log = 竖线分隔，给流量脚本算账（公网直连与隧道流量都在这里）
    log_format secagent_static '\$time_iso8601|\$request_method|\$uri|\$status|\$body_bytes_sent|\$remote_addr|\$http_user_agent';
    access_log /var/log/nginx/secagent-static-access.log combined;
    access_log /var/log/nginx/secagent-static-traffic.log secagent_static;
    log_not_found off;
    server_tokens off;
    sendfile on;
    tcp_nopush on;
    keepalive_timeout 65;
    etag on;

    # —— 公网入口的限速（只对公网块生效：隧道块不套这层，避免影响内部自检）——
    limit_req_zone  \$binary_remote_addr zone=xk_req:10m  rate=30r/s;
    limit_conn_zone \$binary_remote_addr zone=xk_conn:10m;
    limit_req_status  429;
    limit_conn_status 429;

    # —— TLS 基础（公网 443 生效；隧道那侧由 Cloudflare 终结）——
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:xkSSL:2m;
    ssl_session_timeout 1h;
    ssl_session_tickets off;

    # ============================================================
    # ① 素材站 static.xiaokeqing.cn -> /opt/secagent/static（隧道用，127.0.0.1:18080）
    #    仍是该回环端口的默认 server
    # ============================================================
    server {
        listen 127.0.0.1:18080;
        server_name static.xiaokeqing.cn _;

        root /opt/secagent/static;
        index index.html;

        autoindex off;
        disable_symlinks on;

        if (\$request_method !~ ^(GET|HEAD)\$) { return 405; }

        location / {
            limit_except GET { deny all; }
            try_files \$uri \$uri/ =404;
            add_header Cache-Control "public, max-age=86400" always;
            add_header X-Content-Type-Options nosniff always;
        }

        location ~ /\. { deny all; }
    }

    # ============================================================
    # ② 博客整站 xiaokeqing.cn / www / staging（隧道用，127.0.0.1:18080）
    # ============================================================
    server {
        listen 127.0.0.1:18080;
        server_name xiaokeqing.cn www.xiaokeqing.cn staging.xiaokeqing.cn;

        root /opt/secagent/site;
        index index.html;
        autoindex off;
        disable_symlinks if_not_owner;

        if (\$request_method !~ ^(GET|HEAD)\$) { return 405; }

        include /etc/nginx/xk-site-locations.conf;

        error_page 404 /404.html;
    }

    # ============================================================
    # ③ 公网 80：只做 ACME 挑战 + 301 跳 https（无任何内容）
    # ============================================================
    server {
        listen $PRIV_IP:80 default_server;
        server_name _;

        location ^~ /.well-known/acme-challenge/ {
            root $ACME_ROOT;
            default_type text/plain;
            try_files \$uri =404;
        }
        location / { return 301 https://\$host\$request_uri; }
    }

    # ============================================================
    # ④ 公网 443：博客整站（绕开 Cloudflare 的直连入口）
    #    listen 私网 IP（云 NAT 1:1）；公网 0.0.0.0:443 被 wazuh 的 127.0.0.1:443 挤占了
    # ============================================================
    server {
        listen $PRIV_IP:443 ssl http2 default_server;
        server_name xiaokeqing.cn www.xiaokeqing.cn direct.xiaokeqing.cn;

        ssl_certificate     $CERTDIR/site-fullchain.pem;
        ssl_certificate_key $CERTDIR/site-privkey.pem;
        add_header Strict-Transport-Security "max-age=86400" always;

        root /opt/secagent/site;
        index index.html;
        autoindex off;
        disable_symlinks if_not_owner;

        if (\$request_method !~ ^(GET|HEAD)\$) { return 405; }

        # 滥用面收窄：只读静态，不需要任何请求体、也不需要长连接慢慢磨
        client_max_body_size 1k;
        client_body_timeout 10s;
        client_header_timeout 10s;
        send_timeout 30s;
        large_client_header_buffers 4 8k;

        # 限速 / 限连接 / 单连接速率上限（前 4MB 不限速，保证正常下载与测速不被扭曲）
        limit_req  zone=xk_req burst=60 nodelay;
        limit_conn xk_conn 24;
        limit_rate_after 4m;
        limit_rate 6m;

        include /etc/nginx/xk-site-locations.conf;

        error_page 404 /404.html;
    }

    # ============================================================
    # ⑤ 公网 443：素材站（同一套 nginx；static 域名若直连过来也走这里）
    # ============================================================
    server {
        listen $PRIV_IP:443 ssl http2;
        server_name static.xiaokeqing.cn;

        ssl_certificate     $CERTDIR/site-fullchain.pem;
        ssl_certificate_key $CERTDIR/site-privkey.pem;
        add_header Strict-Transport-Security "max-age=86400" always;

        root /opt/secagent/static;
        index index.html;
        autoindex off;
        disable_symlinks on;

        if (\$request_method !~ ^(GET|HEAD)\$) { return 405; }

        client_max_body_size 1k;
        client_body_timeout 10s;
        client_header_timeout 10s;
        limit_req  zone=xk_req burst=60 nodelay;
        limit_conn xk_conn 24;
        limit_rate_after 4m;
        limit_rate 6m;

        location ~ ^/(kurisu|images)/ {
            limit_except GET { deny all; }
            try_files \$uri =404;
            add_header Cache-Control "public, max-age=2592000" always;
            add_header X-Content-Type-Options nosniff always;
        }
        location / {
            limit_except GET { deny all; }
            try_files \$uri \$uri/ =404;
            add_header Cache-Control "public, max-age=86400" always;
            add_header X-Content-Type-Options nosniff always;
        }
        location ~ /\. { deny all; }
    }
}
NGINXCONF

install -d -o xksite -g xksite -m 0755 "$ACME_ROOT"
install -d -o xksite -g xksite -m 0755 /run/nginx

log "5/8 nginx -t（root 跑完必须把日志属主修回 xksite，否则服务起不来）"
cp -a /tmp/nginx.conf.public "$CONF.new"
nginx -t -c "$CONF.new" 2>&1 | sed 's/^/  /' || { rm -f "$CONF.new"; die "公网版配置语法不过，未落盘"; }

log "6/8 落盘 + 保存两个变体 + 单元加 CAP_NET_BIND_SERVICE"
mv "$CONF.new" "$CONF"; chmod 0644 "$CONF"; chown root:root "$CONF"
install -d -m 0755 "$VARIANTS"
cp -a "$CONF" "$VARIANTS/nginx.public.conf"
# 隧道版 = 只有 ① ② 两个回环块（killswitch off 用）
sed -e '/# ③ 公网 80/,$d' "$CONF" > "$VARIANTS/nginx.tunnel-only.conf"
printf '}\n' >> "$VARIANTS/nginx.tunnel-only.conf"
if nginx -t -c "$VARIANTS/nginx.tunnel-only.conf" >/dev/null 2>&1; then
  ok "隧道版变体校验通过：$VARIANTS/nginx.tunnel-only.conf"
else
  warn "隧道版变体没通过语法检查（killswitch off 会用到它，先看看）"
  nginx -t -c "$VARIANTS/nginx.tunnel-only.conf" 2>&1 | sed 's/^/    /'
fi

if grep -q '^AmbientCapabilities=CAP_NET_BIND_SERVICE' "$UNIT"; then
  ok "单元已带 CAP_NET_BIND_SERVICE"
else
  sed -i 's|^CapabilityBoundingSet=$|CapabilityBoundingSet=CAP_NET_BIND_SERVICE|' "$UNIT"
  sed -i 's|^AmbientCapabilities=$|AmbientCapabilities=CAP_NET_BIND_SERVICE|' "$UNIT"
  ok "已加 CAP_NET_BIND_SERVICE（ip_unprivileged_port_start=1024，非 root 绑 80/443 必须要）"
fi
systemctl daemon-reload

log "7/8 修复日志/运行目录属主并重启"
rm -f /var/log/nginx/secagent-static-access.log /var/log/nginx/secagent-static-traffic.log
rm -rf /run/nginx
install -d -o xksite -g xksite -m 0755 /run/nginx
chown -R xksite:xksite /var/log/nginx /var/lib/nginx
chmod 0644 /var/log/nginx/*.log 2>/dev/null || true
systemctl restart secagent-static.service
sleep 2
printf '  is-active: %s\n' "$(systemctl is-active secagent-static.service)"
printf '  AmbientCapabilities: %s\n' "$(systemctl show secagent-static -p AmbientCapabilities --value)"
printf '  ReadOnlyPaths: %s\n' "$(systemctl show secagent-static -p ReadOnlyPaths --value)"
echo "  --- 监听（回环 18080 + 公网私网 IP 的 80/443）---"
ss -tlnp | grep -E ':(80|443|18080) ' | sed 's/^/  /'

log "8/8 ufw 放行 80/443（只加放行，不动 DOCKER-USER）"
ufw allow 80/tcp  comment 'blog http -> https redirect + ACME' >/dev/null
ufw allow 443/tcp comment 'blog direct https (read-only static)' >/dev/null
ok "已放行"
echo "  --- 放行前后 DOCKER-USER 对比（必须完全一致）---"
iptables-save > /tmp/iptables.after 2>/dev/null || true
for ch in DOCKER-USER FORWARD; do
  if diff <(grep -E "^-A $ch" "$BACKUP/iptables.before") <(grep -E "^-A $ch" /tmp/iptables.after) >/dev/null; then
    ok "$ch 链未变"
  else
    warn "$ch 链发生变化："
    diff <(grep -E "^-A $ch" "$BACKUP/iptables.before") <(grep -E "^-A $ch" /tmp/iptables.after) | sed 's/^/    /' || true
  fi
done

echo
echo "  --- 冒烟：回环（隧道侧）---"
for h in static.xiaokeqing.cn xiaokeqing.cn www.xiaokeqing.cn staging.xiaokeqing.cn; do
  printf '    %-24s -> %s\n' "$h" "$(curl -s -o /dev/null -w '%{http_code} %{size_download}' -H "Host: $h" http://127.0.0.1:18080/)"
done
echo "  --- 冒烟：公网 443（自签，-k）---"
curl -sk -o /dev/null -w "    https://$PUB_IP_EXPECT/            -> %{http_code} size=%{size_download}\n" --max-time 20 "https://$PUB_IP_EXPECT/" || true
curl -sk -o /dev/null -w "    Host: direct.xiaokeqing.cn  -> %{http_code} size=%{size_download}\n" --max-time 20 -H 'Host: direct.xiaokeqing.cn' "https://$PUB_IP_EXPECT/" || true
curl -skI --max-time 20 "https://$PUB_IP_EXPECT/" | head -6 | sed 's/^/    /' || true
echo "  --- 公网 80 跳转 ---"
curl -s -o /dev/null -w '    http://IP/ -> %{http_code} redirect=%{redirect_url}\n' --max-time 20 "http://$PUB_IP_EXPECT/" || true

echo
sha256sum "$CONF" "$LOCS" "$UNIT" "$VARIANTS/nginx.tunnel-only.conf" | sed 's/^/  /'
ok "完成（备份：$BACKUP）"
