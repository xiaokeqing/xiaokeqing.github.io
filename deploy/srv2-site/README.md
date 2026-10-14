# deploy/srv2-site —— 博客整站在 srv2 上的落地物（只读静态 + 公网直连 + 隧道备用）

> 这套东西把 `xiaokeqing.cn` 从 GitHub Pages 搬到 srv2 的**宿主 nginx**（不新起第二套 web 服务），
> 对外两条路：**公网 443 直连**（主，实测 271–338 KB/s）与 **Cloudflare 命名隧道**（备）。
> 运维手册：[`docs/ops-博客托管切换与回滚.md`](../../docs/ops-博客托管切换与回滚.md)

## 文件

| 文件 | 作用 | 什么时候跑 |
|---|---|---|
| `xk-site-locations.conf` | 整站 location 集（隧道块与公网块**共用**，防两份配置漂移）：`/kurisu/**`+`/images/**` 长缓存 30d、css/js/json 短缓存 300s、HTML `no-cache`、带扩展名的资源绝不回落 `index.html` | 由 `srv2-site-public.sh` 写入 `/etc/nginx/` |
| `srv2-site-nginx-merge.sh` | 把"整站 server 块"**增量合并**进当时的 nginx.conf（保留别条线加的 `log_format secagent_static` 流量口径），零中断 reload | 首次接入 / 别人改过 nginx.conf 之后 |
| `srv2-site-public.sh` | **主线**：自签占位证书 + 写公网版 nginx.conf（回环 18080 两块 + 公网 80/443）+ 单元加 `CAP_NET_BIND_SERVICE` + ufw 放行 80/443 + 生成 killswitch 用的两个变体 | 首次开公网 / 重建这台机器 |
| `srv2-site-tls-issue.sh` | 给**所有** server 块挂 ACME webroot（`/var/www/acme`），然后用 certbot HTTP-01 签发/扩签；写续期 deploy hook（同步证书 + reload） | 首次签证书 / 加域名 |
| `srv2-site-tls-4san.sh` | 主域名 DNS 一变就用的**最短路径**补签 4-SAN（解析自检 → certbot → hook → 验证，40s 内） | 切主域名之后立刻 |
| `srv2-site-killswitch.sh` | 一键开关公网直连：`off` 撤 ufw + 换"隧道版"配置 + 重启（**站点不挂**，隧道照旧）；`on` 反向 | 被刷 / 证书坏 / 要回到只走隧道 |
| `srv2-site-regression.sh` | 回归证据包（5 项）：DOCKER-USER 顺序、蜜罐隔离**实测**探针、诱饵端口三层、7 容器、监听面 + 隧道侧回归 | 动过防火墙/证书/nginx 之后 |
| `srv2-site-traffic-redline.sh` | 给 `srv2-static-traffic.sh` 加"**站点素材 ≤150GB/月**"红线（越线至少 HIGH，进日报与告警） | 一次（幂等） |

## 关键约束（踩过的坑）

1. **必须 `listen 10.0.0.10:443`，不能 `0.0.0.0:443`**
   srv2 的 `127.0.0.1:443` 被 `wazuh.dashboard`（`127.0.0.1:443->5601`）的 docker-proxy 占用；
   实测 `0.0.0.0:443`（即使带 `SO_REUSEADDR`）`EADDRINUSE`，`10.0.0.10:443` 可以绑。
   腾讯云 EIP 1:1 NAT 到 eth0 的 `10.0.0.10` ⇒ 公网 443 流量正好落这里，且**不碰 Wazuh 映射**。
2. **非 root 绑 <1024 要能力位**：`net.ipv4.ip_unprivileged_port_start=1024` ⇒ 单元必须
   `AmbientCapabilities=CAP_NET_BIND_SERVICE` + `CapabilityBoundingSet=CAP_NET_BIND_SERVICE`。
3. **`nginx -t` 跑完必须把日志属主修回 `www-data`**（root 跑 `-t` 会生成 `root:root` 的
   `/var/log/nginx/*.log`，服务降权后打不开 → nginx 起不来）。
4. **改配置不要先删 `/run/nginx/nginx.pid`**：`ExecReload=nginx -s reload` 靠它找 master，删了 reload 必失败。
   标准动作：`nginx -t` → 修日志属主 → `systemctl restart`。
5. **证书私钥可读性**：nginx master 以 `www-data` 运行 ⇒ 私钥必须 `root:www-data 0640`
   （`/etc/ssl/secagent/site-privkey.pem`），由续期 hook 负责同步。
6. **ACME 为什么挂在所有 server 块**：域名无论"直连 srv2"还是"经 CF 隧道回源"，
   HTTP-01 都能落到 `/var/www/acme`。域名仍指 GitHub Pages 时验证必然失败（正确行为）。

## 目标状态速查

```
/etc/nginx/nginx.conf                       公网版（可切隧道版）
/etc/nginx/xk-site-locations.conf           整站 location 集
/etc/ssl/secagent/site-{fullchain,privkey}.pem   nginx 读的稳定证书路径
/etc/letsencrypt/live/xk-site/              certbot 管的证书（certbot.timer 自动续期）
/etc/systemd/system/secagent-static.service  www-data + ReadOnlyPaths + CAP_NET_BIND_SERVICE
/opt/secagent/site -> releases/site-*       站点根（原子切换）
/opt/secagent/static                        素材根（0555，隧道用）
/opt/secagent/backups/site-nginx/nginx.{public,tunnel-only}.conf   killswitch 的两个变体
/opt/secagent/backups/nginx-*/              每步改前的备份
```
