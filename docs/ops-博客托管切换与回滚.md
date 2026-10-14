# ops：博客托管切换与回滚（srv2 直连 + CF 隧道备用）

> 最后更新：2026-10-14 22:0x ｜ 执行人：DSH 会话（站主授权）｜ 状态：**srv2 侧就绪，主域名 DNS 未动**
> 关联脚本：`scripts/publish-site-to-srv2.ps1`、`scripts/srv2-site-receive.sh`、`deploy/srv2-site/**`

---

## 0. 一句话结论

博客整站已经不在 GitHub Pages 上了：现在跑在 **srv2 的宿主 nginx**（只读静态）上，对外有**两条路**：

```
                         ┌── 路径 A（主，快）：Cloudflare DNS → A 记录 43.143.114.79（灰云）→ nginx 10.0.0.10:443
站主/访客 ── DNS ────────┤
                         └── 路径 B（备）：Cloudflare 橙云 → 命名隧道 secagent-static → nginx 127.0.0.1:18080
```

实测（站主这台机器，2MB 载荷）：

| 路径 | 吞吐 | 说明 |
|---|---|---|
| **A 直连 srv2 443** | **271–338 KB/s**（30s 内稳定下完 2MB） | 主路径 |
| B 经 CF 隧道（命中缓存） | 0.1–10.7 KB/s | 瓶颈在"站主链路→CF 边缘"，缓存救不回来 |
| GitHub Pages（原） | 9.6–17 KB/s（2MB 下不完；主页 HTML 5.3 KB/s） | 已弃用为备份 |

---

## 1. srv2 侧落地物（现状快照）

| 项 | 值 / 路径 | sha256（2026-10-14 21:5x） |
|---|---|---|
| nginx 配置 | `/etc/nginx/nginx.conf` | `0b3e64bbd4a2dae1…` |
| 站点 location 集 | `/etc/nginx/xk-site-locations.conf` | `05544c0b70dc5c5d…` |
| 服务单元 | `/etc/systemd/system/secagent-static.service` | `6be76b06b527ab65…` |
| 服务账号 | **`xksite`**（专用系统账号：no-login、无 home、uid 997）—— 不再用通用的 `www-data` | — |
| 沙箱与限额 | `ReadOnlyPaths=/opt/secagent/{static,releases}`、`CPUQuota=25%`、`MemoryMax=128M`、`TasksMax=64`、`AmbientCapabilities=CAP_NET_BIND_SERVICE` | — |
| 隧道 ingress | `/etc/cloudflared/static-config.yml` | `34f8f7e510f6ce23…` |
| 站点根（符号链接） | `/opt/secagent/site` → `/opt/secagent/releases/site-*` | 当前 `site-20261014-215320` |
| 素材根 | `/opt/secagent/static` | 0555 root:root |
| 证书（nginx 读） | `/etc/ssl/secagent/site-fullchain.pem`、`site-privkey.pem`（root:www-data 0640） | LE，SAN=`direct,static` |
| 证书（certbot 管） | `/etc/letsencrypt/live/xk-site/` + `certbot.timer` | 到期 2027-01-12，自动续期 |
| 续期钩子 | `/etc/letsencrypt/renewal-hooks/deploy/xk-site-sync.sh` | 续期后自动同步 + reload |
| 一键开关 | `/opt/secagent/scripts/srv2-site-killswitch.sh` | on / off / status |
| 接收脚本 | `/opt/secagent/scripts/srv2-site-receive.sh` | 幂等 + 原子切换 + 失败回滚 |
| 回归证据包 | `/opt/secagent/scripts/srv2-site-regression.sh` | 5 大项，fail-closed |
| 备份（改前） | `/opt/secagent/backups/{nginx-site,nginx-merge,nginx-public,nginx-acme,cloudflared-static,traffic-redline}-*` | 每步都有 |

### 设计要点（踩过的坑，别再踩）

1. **为什么 listen `10.0.0.10:443` 而不是 `0.0.0.0:443`**
   srv2 的 `127.0.0.1:443` 已被 `wazuh.dashboard`（`127.0.0.1:443->5601`）的 docker-proxy 占用；
   实测 `0.0.0.0:443` 即使带 `SO_REUSEADDR` 也是 `EADDRINUSE`，而 `10.0.0.10:443` 可以绑。
   腾讯云 EIP 是 1:1 NAT 到 eth0 的 `10.0.0.10`，所以公网 443 的流量正是落在这里
   ⇒ 拿到真 443，且**完全不碰 Wazuh 的映射**。
2. **非 root 绑 <1024 需要能力位**：`net.ipv4.ip_unprivileged_port_start=1024`，
   所以单元加了 `AmbientCapabilities=CAP_NET_BIND_SERVICE` + `CapabilityBoundingSet=CAP_NET_BIND_SERVICE`。
3. **`nginx -t` 必须用 root 跑，跑完必须把日志属主修回 www-data**
   （root 跑 `-t` 会生成 `root:root` 的 `/var/log/nginx/*.log`，服务降权后打不开 → nginx 起不来）。
4. **reload 依赖 pid 文件**：`ExecReload=/usr/sbin/nginx -s reload` 靠 `/run/nginx/nginx.pid` 找 master；
   **删了 pid 再 reload 必失败**。改配置的标准动作：`nginx -t` → 修日志属主 → `systemctl restart`。

---

## 2. 切换主域名（DNS）——**待站主放行**

### 2.1 切换前必须过的两道关（2026-10-14 已过）

| 关 | 判据 | 实测 |
|---|---|---|
| 关 1 证书是正式 CA | ① `curl -I https://direct.xiaokeqing.cn/ --resolve direct.xiaokeqing.cn:443:43.143.114.79`（**不带 -k**）→ 200；② `openssl s_client -servername xiaokeqing.cn` 的 issuer 是正式 CA | ① **200 / 72,262B / 0.19s / verify=0**；② `issuer=C=US,O=Let's Encrypt,CN=YR1` |
| 关 2 内容一致 | 本地 `public/` 与 srv2 逐项一致 | **304 文件全量 sha256 零差异**；六路由 200 且 `data-xk-ssr` = home/monitor/notes/range/about/ai |

> ⚠️ 关 1 目前是 **2-SAN**（`direct` + `static`）。主域名切过去**之前**必须补签成 4-SAN
> （`xiaokeqing.cn` / `www` / `direct` / `static`），否则浏览器对主域名报证书名不匹配。

### 2.1.1 切换的**触发条件与回滚条件**（照这个判，不靠感觉）
```
立即回滚（改回 CNAME → xiaokeqing.github.io + 橙云）的条件，任意一条命中即回滚：
  ① 4-SAN 补签失败（certbot 非 0）且 5 分钟内重试仍失败
  ② https://xiaokeqing.cn/ 不带 -k 不是 200（证书不可信 / 502）
  ③ 六条路由里有任何一条不是 200 或 data-xk-ssr 不对
  ④ 首屏门禁（_dev/gate-firstscreen.mjs）任一页 > 1536KB
回滚动作：站主在 Cloudflare 把 apex/www 改回 CNAME → xiaokeqing.github.io → Proxied（约 2 分钟生效）
          + 可选：srv2 上 `sudo bash /opt/secagent/scripts/srv2-site-killswitch.sh off` 收掉公网口
```

### 2.2 两条路，二选一

**路 1（推荐，零警告窗口）—— 站主给一个 Cloudflare API Token（Zone → DNS → Edit，仅此 zone）**
```bash
# 一次性做完：抄 DNS 原文 → 加 direct（若缺） → DNS-01 签 4-SAN → 改主域名 A 记录 → 复测
bash deploy/srv2-site/switch-main-domain.sh --token-file /root/.cf-token --apply
```
（该脚本按设计留待 token 到位后落地；DNS-01 在**切之前**就把 4-SAN 签好 ⇒ 用户看不到任何证书警告。）

**路 2（站主点两下，代价是约 1 分钟的自签窗口）**
1. 站主在 Cloudflare 控制台：`xiaokeqing.cn` 与 `www` 的 A 记录 → `43.143.114.79`，**代理状态 DNS only（灰云）**
2. 切换后**立刻**（脚本 40 秒内）在 srv2 上执行：
   ```bash
   sudo bash /opt/secagent/scripts/srv2-site-tls-issue.sh \
        -d xiaokeqing.cn -d www.xiaokeqing.cn -d direct.xiaokeqing.cn -d static.xiaokeqing.cn
   ```
   （HTTP-01 走新指的 A 记录 → 公网 80，`/var/www/acme` 已就位）
3. 复测：`curl -I https://xiaokeqing.cn/`（不带 -k）应 200 + 证书可信

### 2.3 切换后立即复测清单
```bash
curl -sI https://xiaokeqing.cn/ | head -3                      # 200 + 证书可信
for r in / /alerts/ /posts/ /labs/ /about/ /ai/; do curl -so /dev/null -w "$r %{http_code}\n" https://xiaokeqing.cn$r; done
grep -o 'data-xk-ssr=[a-z]*' public/index.html | head -1       # home（其余路由同理）
curl -s -o /dev/null -w '%{speed_download}\n' https://xiaokeqing.cn/kurisu/medium/idle.atlas.webp
curl -s http://127.0.0.1:18080/ -H 'Host: static.xiaokeqing.cn' -o /dev/null -w '%{http_code}\n'   # 隧道备份仍 200
sudo bash /opt/secagent/scripts/srv2-site-regression.sh        # 回归
```

---

## 3. 回滚（三条独立的路，按严重程度从轻到重）

### 3.1 只回滚一次发布（最新的产物有问题）
```bash
sudo bash /opt/secagent/scripts/srv2-site-receive.sh --rollback     # 回到上一版 release（秒级）
sudo bash /opt/secagent/scripts/srv2-site-receive.sh --status       # 看当前/上一版
```
`receive.sh` 每次切换前会把上一版写进 `/opt/secagent/releases/.previous`；保留最近 4 个版本。
**耗时：< 1 秒；谁执行：任何人（有 sudo 即可）。**

### 3.2 关掉公网直连，回到"只走 CF 隧道"（srv2 被刷/被 DDoS/证书出问题）
```bash
sudo bash /opt/secagent/scripts/srv2-site-killswitch.sh off
```
它做三件事：撤 ufw 80/443 放行 → 换上"隧道版" nginx.conf（只留 127.0.0.1:18080 两个 server 块）→
重启服务并自检隧道侧仍 200。**站点不会因为关直连而挂**（隧道照旧）。
```bash
sudo bash /opt/secagent/scripts/srv2-site-killswitch.sh on      # 恢复
sudo bash /opt/secagent/scripts/srv2-site-killswitch.sh status  # 只看状态
```

### 3.3 主域名整个切回 GitHub Pages（最彻底的兜底）
**前置：gh-pages 分支必须仍然可用**（未验证：本次会话无法 `git ls-remote`，站主网络对 github SSH 被重置；
请在能推的环境确认 `gh-pages` 仍指向最后一份产物）。
Cloudflare 控制台操作（**站主执行，约 2 分钟生效**）：

| 记录 | 现在（切换后） | 回滚成 |
|---|---|---|
| `xiaokeqing.cn`(apex) | 切换后：A `43.143.114.79` + 灰云 | **回滚成：CNAME `xiaokeqing.github.io` + Proxied（橙云）** |
| `www` | 切换后：A `43.143.114.79` + 灰云 | **回滚成：CNAME `xiaokeqing.github.io` + Proxied（橙云）** |
| `static` / `direct` / `demo` | 不动 | 不动 |

> ⚠️ **回滚前必须先把 DNS 原文备份（§5）确认到位**：没有原文就只能靠记忆重建，可能把 www 或 MX 弄错。
> 复活 Pages 的另外两个条件：① 仓库里 `gh-pages` 仍是完整产物；② `static/CNAME` = `xiaokeqing.cn` 仍在。

### 3.4 三种回滚的耗时与执行人

| 场景 | 动作 | 耗时 | 谁执行 |
|---|---|---|---|
| 产物有问题 | `srv2-site-receive.sh --rollback` | < 1 秒 | 任何人（sudo） |
| 直连被打/证书坏 | `srv2-site-killswitch.sh off` | ~5 秒（nginx 重启） | 任何人（sudo） |
| srv2 整机/443 挂 | Cloudflare 改 DNS 回 Pages | 2–5 分钟（TTL/传播） | **站主**（控制台），或持 token 的自动化 |
| 主域名换回不用 Cloudflare | 改 NS 回原注册商 | 小时级 | 站主 |

---

## 4. 单点与风险（如实）

1. **srv2 或 443 挂 = 整站挂**（比"只是 API 断"严重一档）。
   现有兜底：① CF 隧道（`static.xiaokeqing.cn` 仍 200，可作为第二入口，但站主链路上它很慢）；
   ② `killswitch off` 后把主域名指回隧道的 CNAME（`cloudflared tunnel route dns --overwrite-dns secagent-static xiaokeqing.cn`）；
   ③ DNS 切回 Pages（§3.3）。
   **建议加**：srv2 上给 443 配一个外部可用性探测（现有 `secagent-srv1deadman` / `srv2-static-check` 可扩展），
   5 分钟级发现整站不可用。
2. **失去 Cloudflare 的 DDoS 缓解与 WAF**：直连后攻击流量直接打到 srv2 的 nginx。
   已做的缓解：只读静态、只 GET/HEAD、`limit_req 30r/s burst 60`、`limit_conn 24/IP`、
   单连接 `limit_rate 6m`（前 4MB 不限速，避免扭曲正常下载）、`client_max_body_size 1k`、
   ufw 只放 80/443、`server_tokens off`。**未做**：云安全组未加源 IP 白名单（应保持全网可达，否则失去意义）、
   未接 Cloudflare 代理（这正是为了绕过 CF 的慢链路）。**若要两者兼得**：主域名保留橙云 + 单独一个
   "直连备用域名"，或上 Cloudflare Spectrum/Argo 类方案（成本与复杂度另议）。
3. **500 后仍是单机单进程**：nginx `worker_processes 1`。静态站点 CPU 占用极低，实测 24KB 页面 5.6ms；
   但大文件并发下单 worker 会成为瓶颈。建议观察后再考虑 `worker_processes 2` + `worker_connections` 上调。
4. **证书续期依赖 80 端口常开**：certbot 是 HTTP-01（webroot）。如果哪天 80 被关（比如 killswitch off
   且不再开），续期会失败 → 90 天后证书过期。**缓解**：`killswitch off` 只关公网监听，
   80 端口 HTTP-01 需要公网可达；因此**要么保留 80，要么改用 DNS-01（需要 CF token）**。
   ⚠️ 这是当前方案的真实脆弱点，已记在 §6 待办。
5. **凭据纪律**：`static-credentials.json` 0600 root:root；certbot 私钥在 `/etc/ssl/secagent/site-privkey.pem`
   （root:www-data 0640 —— nginx master 以 www-data 运行，必须可读）。**任何私钥都不进仓库**。
6. **流量预算**：srv2 = 300GB/月（隧道出向 + 公网直连出向都计入）。
   站点素材红线 **≤150GB/月**，已加进 `srv2-static-traffic.sh`（日报 + 越线 HIGH 告警）；
   当前用量 62.2MB（0.02%），其中含本次落地的测试流量（见 §6）。

---

## 5. DNS 备份（**待补：需要 Cloudflare API Token 才能读代理后的记录原文**）

| 名称 | 类型 | 现在解析到 | 代理 | 备注 |
|---|---|---|---|---|
| `xiaokeqing.cn` | 橙云（A/AAAA 由 CF 应答） | 104.21.28.174 / 172.67.146.238 | **Proxied** | 源站 = GitHub Pages（响应头含 `x-github-request-id`、`via: 1.1 varnish`） |
| `www.xiaokeqing.cn` | 同上 | 同左 | **Proxied** | 源站 = GitHub Pages（`301 → https://xiaokeqing.cn/`，GitHub 自定义域跳转） |
| `static.xiaokeqing.cn` | 隧道 CNAME（→ `<uuid>.cfargotunnel.com`） | 同左 | **Proxied** | 隧道备用路径，**切换时不动** |
| `direct.xiaokeqing.cn` | A | **43.143.114.79** | **DNS only** | 2026-10-14 新增，验证用 |
| NS | — | `clay.ns.cloudflare.com`、`gabriella.ns.cloudflare.com` | — | Cloudflare 托管 |

### 5.1 切换前的**原文**（站主 2026-10-14 从 Cloudflare 面板逐条誊录）

| 类型 | 名称 | 值 | 代理状态 | 本次动作 |
|---|---|---|---|---|
| A | `direct.xiaokeqing.cn` | `43.143.114.79` | **DNS only（灰云）** | **不动** |
| Tunnel | `demo.xiaokeqing.cn` | 隧道 `secagent`（**srv1**） | Proxied | **绝对不动**（另一条线的隧道） |
| Tunnel | `static.xiaokeqing.cn` | 隧道 `secagent-static`（srv2） | Proxied | **不动**（备用路径） |
| CNAME | `www.xiaokeqing.cn` | `xiaokeqing.github.io` | **Proxied（橙云）** | → 改成 A `43.143.114.79` + 灰云 |
| CNAME | `xiaokeqing.cn`（apex） | `xiaokeqing.github.io` | **Proxied（橙云）** | → 改成 A `43.143.114.79` + 灰云 |
| NS | 整个 zone | `clay.ns.cloudflare.com`、`gabriella.ns.cloudflare.com` | — | 不动 |

**回滚原文（一条也不能错）**：
```
www.xiaokeqing.cn   CNAME   xiaokeqing.github.io   →  Proxied（橙云）
xiaokeqing.cn       CNAME   xiaokeqing.github.io   →  Proxied（橙云）
```
站主誊录的副本另存：`E:\DeepSeek1\work\_cf-dns-baseline-before-switch.md`（站主机器侧）。
> 公网侧只能看到 Cloudflare 边缘 IP（`104.21.28.174` / `172.67.146.238`），看不到 CNAME 指向与代理开关 ——
> 所以这份**面板誊录**就是唯一的原文基线；`Zone.DNS:Read` 的 API token 站主给过一次但**不是有效 token**
> （CF 返回 `code 1000 Invalid API Token` / `9109 Invalid access token`），DNS-01 方案随之作废，
> 改走"站主点两下 + 事后 40 秒补签"。**gh-pages 仍是可用备份**（未验证：本机对 `ssh.github.com:443` 被重置）。

---

## 6. 待办 / 欠账（诚实清单）

1. ~~**DNS 原文备份**~~ ✅ **已补齐**（站主面板誊录，见 §5.1）；API token 无效，不再指望 API。
2. **4-SAN 证书**：脚本已预置在 srv2（`/opt/secagent/scripts/srv2-site-tls-4san.sh`），
   DNS 一变就一条命令补签（含解析等待 `--wait=180`），实测签发 + 同步 + reload 在 **40 秒内**。
3. ~~**独立低权用户**~~ ✅ **已做**：专用系统账号 `xksite`（uid 997），服务 `User/Group=xksite`；
   日志/临时/证书/ACME webroot 均已移交，续期 hook 也改成 `root:xksite` 并**实跑验证过**。
   保留 systemd 沙箱与限额（ReadOnlyPaths / CPUQuota 25% / MemoryMax 128M / TasksMax 64）。
4. **Wazuh 盯 web 进程**：本轮**未做**。计划：在 Wazuh manager 上加一个
   `localfile`（`/var/log/nginx/*.log` 与 `journalctl -u secagent-static`）+ 规则
   （unit 重启 / 5xx 突增 / `limit_req` 大量 429）；需要改容器内 `ossec.conf`，属于检测栈改动，
   按站主"不动检测职责"的纪律**单独提审**再做。
5. **落点基线**：`deploy/srv2-site/**` 与本文件已入仓（提交 `64bd01d`）；与 `srv1-installed-manifest.sh`
   同类口径的清单生成待下一轮（本轮已给出全量 sha256 快照，见 §1 与交付报告）。
5. **流量基线偏移**：本次落地产生约 20–30MB 测试流量（2MB 测速文件反复下、隧道缓存回源），
   已把 `srv2-static-traffic.sh` 的基线覆盖窗口内含进去（其 `DEFAULT_BASELINE=45,000,000` 是上界整数，
   宁多不少）；测试文件已删除。
6. **缓存清刷流程**：见 §7。
7. **`gh-pages` 可用性未验证**：本机对 `ssh://git@ssh.github.com:443` 被重置，无法 `ls-remote` 确认。

---

## 7. 缓存清刷流程（改了素材之后，怎么让 CF 边缘与浏览器拿到新版本）

事实前提：**素材文件名不带内容 hash**（`/kurisu/full/idle.hi.webp`、`/images/bg.jpg` 等），
只有 CSS 带指纹（`css/site.min.<sha256>.css`，由 Hugo 生成）。所以：

| 场景 | 会发生什么 | 怎么让新版本生效 |
|---|---|---|
| **CSS/JS**（带指纹） | 文件名随内容变（`site.min.2c22d0c4….css`），引用它的 HTML 是 `no-cache` | **什么都不用做**：重新构建 → 发布，HTML 里指向新文件名，浏览器自然拉新文件 |
| **HTML** | 响应头 `Cache-Control: no-cache`（走 srv2 时）；CF 对 HTML 默认不缓存（`cf-cache-status: DYNAMIC`） | 发布后立刻生效（浏览器会 revalidate，ETag 命中就 304） |
| **`/kurisu/**`、`/images/**`** | 响应头 `Cache-Control: public, max-age=2592000`（30 天）；CF 侧还有站主建的 Cache Rule（`/kurisu/` → Eligible for cache） | **改图必须改名**（加 `-v2` / 日期后缀）再更新 HTML 引用；否则老访客 30 天内看不到新图 |
| 已发出去的老图需要立刻替换 | — | ① **改文件名**（推荐，零风险）；② 或者在 Cloudflare 控制台 Purge 单文件 URL：`Caching → Configuration → Purge Cache → Custom Purge`（只对橙云生效；直连路径不经过 CF，投毒风险低但浏览器缓存仍在） |

**为什么坚持"改名"策略**：直连路径不经过 Cloudflare，`Purge` 对它完全无效；
唯一对所有访客都成立的办法就是换 URL。所以约定：
```
素材改动 → 换文件名（如 idle.hi.webp → idle.hi.20261015.webp）→ 改模板里的引用 → 重新发布
```
模板里引用素材的位置集中在 `layouts/partials/`（`spa-view-*` 与 head/kurisu 相关 partial），
改动后用 `bash scripts/assert-build.sh public` 断言一遍再走发布通道。

---

## 8. 日常操作速查

```bash
# 发布（站主机器，Windows PowerShell 5.1，不是 pwsh）
powershell -ExecutionPolicy Bypass -File .\scripts\publish-site-to-srv2.ps1              # 用当前工作区
powershell -ExecutionPolicy Bypass -File .\scripts\publish-site-to-srv2.ps1 -FromRef HEAD # 只用已提交的版本
powershell -ExecutionPolicy Bypass -File .\scripts\publish-site-to-srv2.ps1 -CheckUrl https://xiaokeqing.cn/

# srv2 侧
sudo bash /opt/secagent/scripts/srv2-site-receive.sh --status      # 当前/上一版
sudo bash /opt/secagent/scripts/srv2-site-receive.sh --rollback    # 回上一版
sudo bash /opt/secagent/scripts/srv2-site-killswitch.sh off|on|status
sudo bash /opt/secagent/scripts/srv2-site-tls-issue.sh -d <域名...>  # 扩签/续签
sudo bash /opt/secagent/scripts/srv2-site-regression.sh            # 回归（隔离/端口/容器/隧道）
bash /opt/secagent/scripts/srv2-static-daily.sh                    # 自检 + 流量（含 150GB 红线）
sudo certbot certificates                                          # 证书清单与到期
```
