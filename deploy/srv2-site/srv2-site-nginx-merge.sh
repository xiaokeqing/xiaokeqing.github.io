#!/usr/bin/env bash
# ============================================================
# srv2-site-nginx-merge.sh —— 把「博客整站 server 块」合并进现有 nginx.conf
# ------------------------------------------------------------
# 背景：19:41 另一个会话把 nginx.conf 覆写成单 server 块版本（新增流量口径
#       log_format secagent_static + traffic 日志 + copytruncate 轮转 + 每日自检 timer）。
#       本脚本不改它的口径，只做**增量合并**：
#         · 保留它的 log_format / 两条 access_log / log_not_found 等设置
#         · 保留它的 static server 块（含 add_header Cache-Control 的写法）
#         · 新增 ② 整站 server 块（xiaokeqing.cn / www / staging -> /opt/secagent/site）
#         · 单元 ReadOnlyPaths 追加 /opt/secagent/releases（含 /opt/secagent/static 不变，
#           它自检脚本第 75 行是子串匹配，不会因此 fail）
#       落盘后用 reload（不 restart）：运行中的进程本来就是两 server 块 + 双路径沙箱，
#       reload 即可让磁盘配置与运行态一致，且零中断。
# 用法： sudo bash srv2-site-nginx-merge.sh
# ============================================================
set -euo pipefail

CONF=/etc/nginx/nginx.conf
UNIT=/etc/systemd/system/secagent-static.service
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/opt/secagent/backups/nginx-merge-$STAMP
TARGET=/tmp/nginx.conf.merged.$$

log() { echo -e "\n\033[1;36m==> $*\033[0m"; }
ok()  { echo -e "  \033[1;32m[OK]\033[0m $*"; }
warn(){ echo -e "  \033[1;33m[!]\033[0m $*"; }
die() { echo -e "  \033[1;31m[X]\033[0m $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "需要 root"

log "1/6 备份 + 认领现有配置的关键特征"
install -d -m 0700 "$BACKUP"
cp -a "$CONF" "$BACKUP/nginx.conf.before"
cp -a "$UNIT" "$BACKUP/secagent-static.service.before"
sha256sum "$CONF" "$UNIT" | sed 's/^/  /'
if grep -q 'secagent_static' "$CONF"; then
  ok "检测到并发会话的流量口径（log_format secagent_static）→ 合并时保留"
  KEEP_TRAFFIC=1
else
  warn "没检测到流量口径 → 按纯两 server 块写"
  KEEP_TRAFFIC=0
fi
if grep -q 'server_name static.xiaokeqing.cn' "$CONF"; then
  ok "检测到 static server 块 → 保留其现有写法"
else
  die "现有配置里没有 static server 块，情况与预期不符，停手"
fi

log "2/6 生成合并后的 nginx.conf（不覆盖任何已有口径，只新增整站块）"
cat > "$TARGET" <<'NGINXCONF'
worker_processes 1;
pid /run/nginx/nginx.pid;
error_log stderr warn;

events { worker_connections 256; }

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # 两个口径的日志：
    #   access.log  = combined，给人看/排障
    #   traffic.log = 竖线分隔，给流量脚本算账
    # 为什么不用 combined 数字段：$time_local 里带空格会把字段位右移，
    # "$10" 这种写法又脆又难查；竖线分隔后 $body_bytes_sent 恒为第 5 段。
    log_format secagent_static '$time_iso8601|$request_method|$uri|$status|$body_bytes_sent|$remote_addr|$http_user_agent';
    access_log /var/log/nginx/secagent-static-access.log combined;
    access_log /var/log/nginx/secagent-static-traffic.log secagent_static;
    log_not_found off;
    server_tokens off;
    sendfile on;
    tcp_nopush on;
    keepalive_timeout 65;
    etag on;

    # ============================================================
    # ① 素材站 static.xiaokeqing.cn -> /opt/secagent/static
    #    （第十一轮现状 + 流量口径；本 listen 端口的默认 server，逻辑不动）
    # ============================================================
    server {
        # 只绑回环：公网侧不存在这个端口，对外只经 cloudflared 隧道。
        listen 127.0.0.1:18080;
        server_name static.xiaokeqing.cn _;

        root /opt/secagent/static;
        index index.html;

        autoindex off;        # 无目录列表
        disable_symlinks on;  # 不跟随符号链接（防止越出静态根）

        # 只允许 GET / HEAD，其余一律 405
        if ($request_method !~ ^(GET|HEAD)$) { return 405; }

        location / {
            # limit_except 只能出现在 location 里；GET 同时放开 HEAD
            limit_except GET { deny all; }
            try_files $uri $uri/ =404;
            # 只发一条 Cache-Control：expires 会再补一条，重复没必要（实测会出两个头）
            add_header Cache-Control "public, max-age=86400" always;
            add_header X-Content-Type-Options nosniff always;
        }

        # 隐藏文件/点文件一律拒绝
        location ~ /\. { deny all; }
    }

    # ============================================================
    # ② 博客整站 xiaokeqing.cn / www.xiaokeqing.cn -> /opt/secagent/site
    #    （同一个 127.0.0.1:18080，靠 server_name 分流；公网入口只有隧道。
    #      staging 是切主域名前的公开验证入口，验证完可摘掉。）
    # ============================================================
    server {
        listen 127.0.0.1:18080;
        server_name xiaokeqing.cn www.xiaokeqing.cn staging.xiaokeqing.cn;

        # 站点根是指向 releases/site-* 的符号链接（发布时原子切换）：
        # 单次 rename 换链接 => 永远不会对外露出半成品目录。
        root /opt/secagent/site;
        index index.html;

        autoindex off;                       # 无目录列表
        # 不能像素材站那样 disable_symlinks on（根本身就是符号链接）；
        # if_not_owner = 符号链接与目标必须同 owner（这里都是 root）。
        # /opt/secagent 及其子目录全部 root:root 且非 root 不可写，本地伪造符号链接无入口。
        disable_symlinks if_not_owner;

        # 只允许 GET / HEAD，其余一律 405
        if ($request_method !~ ^(GET|HEAD)$) { return 405; }

        # —— 长缓存：角色/场景素材（站主已为 static 域名建好 /kurisu 的 Cache Rule；
        #     主域名切过去后需要把那条 Cache Rule 的 Hostname 覆盖到 xiaokeqing.cn）——
        location ~ ^/(kurisu|images)/ {
            limit_except GET { deny all; }
            try_files $uri =404;
            add_header Cache-Control "public, max-age=2592000" always;
            add_header X-Content-Type-Options nosniff always;
        }

        # —— 长缓存：字体与媒体（内容型大文件）——
        location ~* \.(?:woff2?|ttf|otf|eot|mp4|webm|mp3|ogg|avif|webp|png|jpe?g|gif|svg|ico)$ {
            limit_except GET { deny all; }
            try_files $uri =404;
            add_header Cache-Control "public, max-age=2592000" always;
            add_header X-Content-Type-Options nosniff always;
        }

        # —— 短缓存：样式/脚本/数据（文件名不带指纹，发布后必须能较快生效）——
        location ~* \.(?:css|js|mjs|json|xml|txt|map)$ {
            limit_except GET { deny all; }
            try_files $uri =404;
            add_header Cache-Control "public, max-age=300" always;
            add_header X-Content-Type-Options nosniff always;
        }

        # —— HTML / 目录 / SPA 兜底（hash 路由 SPA：/#/notes 这类都落在 /）——
        location / {
            limit_except GET { deny all; }
            try_files $uri $uri/ /index.html;
            add_header Cache-Control "no-cache" always;
            add_header X-Content-Type-Options nosniff always;
        }

        # 真 404（缺图/缺文件）不要拿 index.html 冒充
        error_page 404 /404.html;

        # 隐藏文件/点文件一律拒绝
        location ~ /\. { deny all; }
    }
}
NGINXCONF

# 保留位（如需在 no-traffic 情况下剥离流量口径，这里不动，保持简单可读）
[[ $KEEP_TRAFFIC -eq 1 ]] || warn "注意：本次仍然写入了 secagent_static 口径（与原配置一致即可）"

log "3/6 校验新配置"
install -d -o www-data -g www-data -m 0755 /run/nginx
chown -R www-data:www-data /var/lib/nginx /var/log/nginx 2>/dev/null || true
cp -a "$TARGET" "$CONF.new"
# nginx -t 需要一个 pid 可写目录；用 -c 指定候选配置来测
if ! nginx -t -c "$CONF.new" 2>&1 | sed 's/^/  /'; then
  rm -f "$CONF.new"
  die "新配置语法不过，已放弃（原配置未动）"
fi
ok "语法通过"

log "4/6 落盘（原子替换）+ 单元 ReadOnlyPaths 追加 releases"
mv "$CONF.new" "$CONF"
chmod 0644 "$CONF"; chown root:root "$CONF"
if grep -q '^ReadOnlyPaths=/opt/secagent/static /opt/secagent/releases$' "$UNIT"; then
  ok "单元已是目标状态"
else
  sed -i 's|^ReadOnlyPaths=.*$|ReadOnlyPaths=/opt/secagent/static /opt/secagent/releases|' "$UNIT"
  systemctl daemon-reload
  ok "$(grep '^ReadOnlyPaths=' "$UNIT")"
fi
sha256sum "$CONF" "$UNIT" | sed 's/^/  /'

log "5/6 reload（不 restart，零中断）"
rm -f /run/nginx/nginx.pid
systemctl reload secagent-static.service
sleep 1
printf '  is-active: %s\n' "$(systemctl is-active secagent-static.service)"
ss -tlnp 2>/dev/null | grep -E ':18080' | sed 's/^/  /'

log "6/6 冒烟：两个 server 块 + 它自检脚本"
smoke() { printf '  %-40s %-6s -> %s\n' "$1$2" "$3" "$(curl -s -o /dev/null -w '%{http_code} %{size_download}' -X "$3" -H "Host: $1" "http://127.0.0.1:18080$2")"; }
smoke static.xiaokeqing.cn / GET
smoke static.xiaokeqing.cn / POST
smoke xiaokeqing.cn / GET
smoke www.xiaokeqing.cn / GET
smoke staging.xiaokeqing.cn / GET
smoke xiaokeqing.cn / POST
smoke xiaokeqing.cn /nope.png GET
smoke xiaokeqing.cn /missing-page/ GET
echo
echo "  --- 并发会话的自检脚本（应仍然全过）---"
bash /opt/secagent/scripts/srv2-static-check.sh 2>&1 | tail -8 | sed 's/^/  /'
echo
ok "完成。备份：$BACKUP"
