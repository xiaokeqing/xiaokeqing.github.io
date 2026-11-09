# 服务器与托管配置 · 详细版（给外部 AI 评审）

> **范围**：两台云主机、七个容器、宿主机 nginx、证书、防火墙、隧道、DNS、发布链与回滚、流量与成本、
> 监控告警、单点风险与改进建议，最后是 **10 个开放问题**（评审重点）。
> **不含任何密钥/口令本身** ✓（只写"在哪台机器的哪个文件/哪个别名"）。
> **标注**：`[已实测]` 本会话有测量/命令输出支撑 ｜ `[契约]` 已定死不许改 ｜ `[待核对]` 我未逐项复核，请以机器实际为准 ｜ `[风险]`
> 姊妹文档：机制与前端接线见 `docs/角色动画与语音-实现全貌与服务器配置-给外部AI.md` §5（简版）与
> `docs/接线方案-动画与语音接入六页.md`；切换过程与回滚原文见 `docs/ops-博客托管切换与回滚.md`。

---

## 1. 拓扑总览

```
                      ┌─────────────────────────────┐
   访客 ── 443/80 ──▶ │ srv2（腾讯云）EIP {公网IP-腾讯云} │  ← **主站真身**（灰云直连）
                      │ 私网 10.0.0.10：nginx 只读静态  │
                      │ + 蜜罐 7 容器 + Wazuh 三件套   │
                      └─────────────────────────────┘
                                     ▲ 备份路径（橙云）
   访客 ── Cloudflare ── cloudflared(secagent-static) ── 127.0.0.1:18080
                      ┌─────────────────────────────┐
   访客 ── Cloudflare ── cloudflared(secagent) ──▶ │ srv1（阿里云）   │  ← 检测 + 公开只读 API
                      │ demo.xiaokeqing.cn（橙云）  │
                      └─────────────────────────────┘
   构建：GitHub Actions → gh-pages（历史/备份）  ✗ 不是线上 ✗
   发布：本机 hugo 构建 → tar.gz → srv2 原子切换（见 §7）
```

---

## 2. srv1（阿里云）— 检测与公开 API

| 项 | 值 |
|---|---|
| 系统 | Aliyun Linux 3 `[契约]` |
| 规格 | **2 vCPU ｜ 1870 MB** `[已实测]` |
| 计费 | **按流量 ¥0.800/GB** `[契约]`；实例费 `[待核对]` |
| 带宽 | 峰值 **3 Mbps** `[契约]` |
| 公网 | 直连（无 EIP 分离）；SSH 别名为 `secagent-srv1` |
| 职责 A | SecAgent 检测/分析栈（规则、告警聚合、故事线、地理富化、看板数据源）`[待核对]` 具体组件 |
| 职责 B | **公开只读 API** `/api/public/*`：`ask`（AI 问答）、`kb`（知识库/RAG 检索）、`overview`、`alerts`、`latest`、`honeypot`、`audit`、`geo`、`webstats`、`stories`、`tts`（**当前 503 关闭态**，等 Fish Audio Key） |
| 隧道 | cloudflared `secagent` → **demo.xiaokeqing.cn**（橙云 Proxied）—— 演示/备用 |
| 上行实测 | `[已实测]` srv1 → Cloudflare **2.9 MB/s**（服务器侧不是瓶颈） |
| 到 srv2 | `[已实测]` srv1 → srv2 单文件 550 KB/s；10MB 图集 35.4s ⇒ **295 KB/s** |

**要点**：srv1 是"数据与智能"侧；博客页面只读它的 `/api/public/*` ✓，因此 **srv1 挂掉只影响数字，不影响页面打开** ✓。

---

## 3. srv2（腾讯云）— 蜜罐检测 + 博客静态托管

### 3.1 规格与网络
```
系统：Ubuntu（VM-0-10-ubuntu）`[已实测]`
规格：**4 vCPU ｜ 3719 MB** ｜ 流量包 **300 GB/月（2026-11-11 重置）** `[已实测]`
公网：**EIP {公网IP-腾讯云}**，1:1 NAT 到私网 **10.0.0.10** `[契约]`
SSH：别名 `secagent-srv2`（密钥见 §9）
```

### 3.2 原有职责：7 个容器 + Wazuh
```
cowrie（SSH 蜜罐）· dionaea（多协议蜜罐）· secagent-decoy（诱饵）· suricata（IDS）
wazuh.dashboard · wazuh.indexer · wazuh.manager
蜜罐网段：cowrie_honeypot **172.19.0.0/16** `[契约]`
`[已实测]` 7 容器全部 Up；蜜罐网段对外 TCP 被 DROP（9 个端口 SYN=0，**对照组 SYN=3 证明测量有效**）
[风险] 站点与蜜罐/Wazuh 同一台机器 ⇒ 站点 443 暴露面与检测栈共享内核与磁盘 IO；
       已用"低权账号 + 只读路径 + 资源上限"隔离（见 3.4），但仍需评审是否够
```

### 3.3 宿主机 nginx（1.18.0）监听面
```
10.0.0.10:80    ← 公网面（只读静态，仅 GET/HEAD，限速 30 r/s burst 60，限连接 24/IP，无动态功能）
10.0.0.10:443   ← 公网面（同上；TLS 由 §5 的证书提供）
127.0.0.1:18080 ← **隧道回源口**（cloudflared `secagent-static` 打这里）
⚠️ `[已实测]` 127.0.0.1:443 被 **wazuh.dashboard 的 docker-proxy** 占用 ⇒ 站点**不能绑 0.0.0.0:443**
   （否则 EADDRINUSE）；绑 EIP 映射到的 10.0.0.10:443 才能拿到真 443 且不碰 Wazuh `[契约]`
```

### 3.4 站点服务（systemd，降权 + 限额）
```
单元：secagent-static.service
  User=xksite（**专用低权账号，uid 997，no-login、无 home**）`[已实测]`
  ReadOnlyPaths=/opt/secagent/static /opt/secagent/releases   ← 站点进程连自己目录都写不了 ✓
  CPUQuota=25% ｜ MemoryMax=128M ｜ TasksMax=64      `[已实测]` 常态内存约 11.6 MB
  AmbientCapabilities=CAP_NET_BIND_SERVICE           ← 非 root 绑 <1024 端口
  ExecReload=/usr/sbin/nginx -s reload               `[已实测]`
[风险] 跑 nginx -t 若以 root 执行会生成 root 属主日志 → 服务降权后无法启动 ✗（已列入陷阱表）
```

### 3.5 目录与发布布局
```
/opt/secagent/site → releases/site-<时间戳>   ← **主站真身**（符号链接；server_name = xiaokeqing.cn/www/direct）`[已实测]`
/opt/secagent/releases/site-<时间戳>/   ← 每次发布一个完整目录；**原子符号链接切换**，保留上一版
/opt/secagent/static/             ← `static.xiaokeqing.cn` 的**占位根**（248 B），**与主站无关** ✗ 别拿它当"主站备份"用
/opt/secagent/scripts/srv2-site-receive.sh   ← 接收/校验/切换/自检脚本（由发布脚本同步上去）
当前线上版本：`/opt/secagent/releases/site-20261015-112007` `[已实测 2026-10-15]`
```
**nginx 与 systemd 的关系**：`systemctl is-active nginx` 返回 **inactive 是设计如此** —— nginx 不是独立服务，它是 `secagent-static.service` 的主进程、以 `xksite` 身份跑 ✗ 别误判为故障（健康检查看 `secagent-static`，实测 active ✓）。3.4 的 `ReadOnlyPaths` 同时列 static/releases 是防御性的，与"主站真身是 /opt/secagent/site"不矛盾。

### 3.6 流量账（站点部分）
```
`[已实测]` 站点累计 used=125.2 MB ｜ 红线 **≤150 GB/月**（进日报，level=OK）
访客口径：典型访问（懒加载）≈ 3~8 MB；全量（含 9.54MB 视频）≈ 10 MB
⇒ 150GB ≈ **2~5 万次访问/月**；300GB 包 ≈ 4~10 万次 ⇒ 个人站余量充足 ✓
[风险] 视频上线 + 流量增长后，媒体宜迁对象存储 + CDN（见 §10 建议）
```

---

## 4. 防火墙与安全组

```
DOCKER-USER 链顺序 `[已实测]`：ESTABLISHED → 127.0.0.11(DNS) → **DROP** → 端口 ACCEPT
  ⇒ 蜜罐容器出网被拦；放行 80/443 前后逐行 diff 一致 ✓
ufw：放行 80/443 ✓ ｜ 腾讯云**安全组入站**：TCP 80/443 ✓（22 的暴露范围 `[待核对]`）
隔离回归 `[已实测]`：蜜罐网段对外 TCP 全 DROP（9 端口 SYN=0、对照 SYN=3）｜ 7 容器 Up
[风险] 443 与蜜罐同机；`[待核对]` 是否对 22 做了来源限制、是否有 fail2ban/SSH 速率限制
```

**⚠️ 硬前提：未备案 ⇒ 境内 80/443 被阻断（2026-10-15 实测铁证）**
```
curl -H 'Host: xiaokeqing.cn' http://{公网IP-腾讯云}/
  → 302 Location: https://dnspod.qcloud.com/static/webblock.html?d=xiaokeqing.cn
  （443 直接 reset，浏览器显示"连接被重置"）
```
⇒ **所有"连接被重置/超时"的真因就是这条**（曾经的"本地 SNI 过滤"判断是误判 ✗ 已纠正）。
⇒ **现行对外路径 = Cloudflare 隧道**（apex/www 的 DNS 已从 A 记录改为 Tunnel `secagent-static`，`direct.*` 保留 A 记录 DNS-only）。
⇒ **备案是唯一能回到直连速度的路**（站主机器实测直连 271~338 KB/s vs CF 免费链路 0~10.7 KB/s）；备案办下来后把 apex/www 切回 A {公网IP-腾讯云}（灰云）。
⇒ 顺带记录：srv1（阿里云）出站到 api.fish.audio 被 SNI 重置（同类阻断），TTS 代理的 Fish 上游暂不可达，见总账。

---

## 5. 证书（Let's Encrypt）

```
`[已实测]` CN=xiaokeqing.cn，签发者 CN=YR2（LE）
SAN 四名：**xiaokeqing.cn / www.xiaokeqing.cn / direct.xiaokeqing.cn / static.xiaokeqing.cn**
有效期：2026-10-14 → **2027-01-12**
自动续期：`certbot.timer` + deploy hook（同步证书并 reload nginx）✓
文件：/etc/letsencrypt/live/xk-site/{fullchain,privkey}.pem
      /etc/ssl/secagent/site-fullchain.pem、site-privkey.pem（属主 root:xksite，权限 640）`[已实测]`
[风险] 续期失败无独立告警 ✗ → 建议纳入 §8 的监控（见 §10）
```

---

## 6. DNS 与 Cloudflare（`xiaokeqing.cn` 区）

| 名称 | 类型 | 值 | 代理状态 | 说明 |
|---|---|---|---|---|
| `direct.xiaokeqing.cn` | A | {公网IP-腾讯云} | **DNS only（灰云）** | 直连入口，保留 |
| `xiaokeqing.cn`（apex） | A | {公网IP-腾讯云} | **DNS only（灰云）** | 2026-10-14 21:47 起从 CF 代理切到直连 |
| `www.xiaokeqing.cn` | A | {公网IP-腾讯云} | **DNS only（灰云）** | 同上 |
| `demo.xiaokeqing.cn` | Tunnel `secagent` | — | Proxied（橙云） | srv1 的演示/备用 |
| `static.xiaokeqing.cn` | Tunnel `secagent-static` | — | Proxied（橙云） | srv2 的**备份路径**（回源 127.0.0.1:18080） |
| Cache Rule | — | Hostname = `static.xiaokeqing.cn` **且** Path 以 `/kurisu/` 开头 → Eligible for cache | — | 只对备份路径生效 `[待核对]` 是否也要对主域生效 |

**回滚（原文在 `docs/ops-博客托管切换与回滚.md`）**：把 apex/www 恢复为
`CNAME xiaokeqing.github.io` + Proxied（橙云），全球生效 1~5 分钟 ✓

**为什么切直连** `[已实测]`：直连 srv2 271~338 KB/s；GitHub Pages 9.6~17 KB/s；CF 隧道 0~10.7 KB/s
（**即使 `cf-cache-status: HIT`、Age 168 也只有 10 KB/s**）⇒ 瓶颈是"访客链路 → CF 边缘"那一段 ✓

---

## 7. 发布链（★ 认知关键：**push ≠ 上线** ✗）

```
① 源码仓 GitHub（main）→ GitHub Actions：hugo 构建 + `scripts/assert-build.sh` → 发布 **gh-pages**
   ⇒ 这是**历史与备份**，**不是线上** ✗（域名已指向 srv2）
② 真正上线：本机执行 `scripts/publish-site-to-srv2.ps1`
     [1/6] 本机 hugo 构建（--gc --minify --cleanDestinationDir）
     [2/6] 汇总产物信息
     [3/6] 产物基本特征校验：index.html 存在且 **> 4 KB** `[已实测：今天把过时的 20KB 阈值改成 4KB，因为新主页=原型整份仅 9.5KB]`
                              文件数 > 0、产物中不出现 localhost
     [4/6] 打包 → %TEMP%\xk-site-<时间戳>.tar.gz（`[已实测]` 81.86 MB）
     [5/6] 上传到 `srv2:/tmp/`，并同步接收脚本到 /opt/secagent/scripts/
     [6/6] 远端 `sudo -n bash srv2-site-receive.sh`：
             verify_tree（基本特征 + 无越权文件；**MIN_INDEX_BYTES=4096**）→
             解包到 `/opt/secagent/releases/site-<stamp>` → **原子 rename 切换** →
             **回环自检**（`curl 127.0.0.1:18080` 期望 200 且字节数 == 刚解包 index.html）→
             失败则**丢弃暂存目录，线上不动** ✓ 并保留上一版
③ 三档回滚（秒 → 分钟）
     ① 秒级：把 `/opt/secagent/site` 指回上一版 release（目录都还在 ✓）
     ② 5 秒：killswitch off（站点退回只走隧道路径）
     ③ 2 分钟：DNS 把 apex/www 切回 Cloudflare + gh-pages（§6）
④ 纪律：推前必须看本地产物 + 截图；`git add` 只加自己的路径（禁入 public/、_shots/、大文件）✗
```

---

## 8. 监控与告警（现状）

```
已有：
  · 站点流量红线日报（≤150GB/月，level=OK）`[已实测]`
  · 外部心跳 + 磁盘告警 `[待核对]`（由"External heartbeat and disk alerting"那条线实现）具体项与阈值
  · 证书自动续期（certbot.timer）✓ 但**续期失败无独立告警** ✗
  · 蜜罐/检测侧：Wazuh 三件套 + Suricata 规则（另有独立的告警与案例管理待办）
缺口与建议（见 §10）：证书到期独立告警 · srv2 站点可用性外部探测 · 发布后自动核对线上版本号 · 备份恢复演练
```

---

## 9. 访问方式与凭据位置（**不含密钥本身** ✗）

```
SSH 别名：`secagent-srv1`（阿里云）｜ `secagent-srv2`（腾讯云）；配置在 %USERPROFILE%\.ssh\config
私钥：%USERPROFILE%\.ssh\secagent_ed25519（GitHub 推送也用同一把）
推送前必须：`$env:GIT_SSH_COMMAND = 'ssh -i "%USERPROFILE%\.ssh\secagent_ed25519" -o IdentitiesOnly=yes'`
           （否则 GitHub 报 publickey 拒绝 ✗）
凭据文件（均在仓库外）：E:\DeepSeek1\work\.cf-token（**当前无效** ✗，CF 返回 Invalid API Token）
                        E:\DeepSeek1\work\.fish-key（待建，用于动态 TTS）
[风险] 若任何密钥曾出现在聊天/文档里 → 到对应平台 **Revoke 重建** ✓
[风险] `[待核对]` 是否使用密码登录 sudo（发布脚本用 `sudo -n`，说明是免密 sudo ✓）
```

---

## 10. 单点风险与改进建议（评审请重点看这节）

```
[风险] ① **srv2 是整站单点**：站点、蜜罐、Wazuh 同机；重启/被滥用/磁盘满都会让站点不可用 ✗
       现状对策：gh-pages 已构建 ✓、CF 隧道备份路径 ✓、三档回滚 ✓
       建议：加**外部可用性探测**（第三方或 srv1 侧 curl 主域 + 关键素材，失败告警）✓
             可选：主站静态产物同步一份到 Cloudflare Pages / 对象存储，做**双源**（DNS 或 Nginx 层面降级）
[风险] ② 媒体膨胀：9.54MB 视频上线后，热门页单次访问 ~10MB；流量包按 300GB/月 计
       建议：媒体（`/kurisu/video/`、语音包）迁 **COS/OSS + CDN**（流量不进 CVM 包，还顺带解决海外访客）
[风险] ③ 静态服务与 Wazuh 共享 443 端口资源与内核
       建议：评审"低权账号 + 只读路径 + 资源上限"是否足够；如要更强隔离，可把静态站点挪到独立小机
[风险] ④ 证书续期失败无告警；DNS 记录与证书 SAN 需要人工保持同步（新增子域必须重签证书 ✗）
       建议：证书到期前 21 天/7 天/1 天三级告警 + 续期后自动访问一次 https 校验
[风险] ⑤ 发布链依赖本机（构建 + tar + 上传）⇒ 本机不可用时无法发布
       建议：把构建搬到 Actions，产物上传到对象存储，srv2 侧只做"拉取 + 切换"（解耦本机）
[风险] ⑥ 无 WAF/CC 防护（只有 nginx 限速 30r/s、24 连接/IP）
       建议：评审是否需要 CF 前置 + WAF（代价：回到今天遇到的 CF 慢链路 ✗ —— 需要权衡）
[风险] ⑦ 备份与恢复：releases 保留上一版 ✓，但**服务器配置、证书、nginx.conf、systemd 单元是否纳入备份** `[待核对]`
       建议：把 `/etc/nginx`、`/etc/systemd/system/secagent-static.service`、`/etc/letsencrypt`、
             `/opt/secagent/scripts` 纳入配置备份 + **做一次恢复演练**（记时间）
[风险] ⑧ 免密 sudo 的暴露面：发布脚本以 `sudo -n bash` 执行远端脚本
       建议：评审该脚本的可写路径与输入校验（只接受 /tmp 下的 tar 包 + 白名单成员路径 ✓ 已有）
```

---

## 11. 成本口径（给评审的估算框架）

```
srv1（阿里云）：实例费 `[待核对]` + 流量 **¥0.800/GB**（按量）
  · /api/public/* 响应很小（KB 级）；假设月出网 1~5 GB ⇒ 流量费 ≈ ¥0.8~4/月
srv2（腾讯云）：实例费 `[待核对]` + **300 GB/月流量包**（2026-11-11 重置）
  · 站点按 150GB 红线内运行；超出包量按 ¥/GB 计费 `[待核对]`
Cloudflare：免费档（橙云代理 + Cache Rule）✓
GitHub Actions：公开仓免费额度 ✓ `[待核对]` 分钟数
对象存储 + CDN（尚未启用）：按量计费，媒体迁移后 ≈ ¥0.2/GB 级 `[待核对]`
⇒ **结论框架**：当前"站点 + 检测"两机的固定成本未知（需你补实例价 ✓），
   与站点直接相关的边际成本主要是**流量**：直连 srv2 走 300GB 包内 ⇒ 边际成本 ≈ 0 ✓
```

---

## 12. 开放问题（请评审方逐条回答）

```
Q1  srv2 单点：你会怎么改？(a) 加外部探测 + 保留 CF 隧道做降级（最小改动）
    (b) 双源（srv2 + Cloudflare Pages/对象存储）(c) 把站点独立成第三台小机 (d) 维持现状
Q2  媒体迁 COS/OSS + CDN 的收益与风险？会不会违反"零第三方请求"的站点纪律（同域 CDN 是否可接受）？
Q3  静态服务与 Wazuh 同机的隔离强度是否足够？需要额外做 namespace/cgroup 或独立用户 + seccomp 吗？
Q4  证书与 DNS 的联动（新增子域必须重签）有没有更省事的方案（例如泛域名证书 + DNS-01 自动化）？
    注：本次因 CF API Token 无效而放弃 DNS-01，改用手动 HTTP-01
Q5  发布链是否该解耦本机（Actions 构建 + 对象存储中转 + srv2 拉取）？迁移成本与收益？
Q6  nginx 限速（30r/s、24 连接/IP）够不够？要不要 CC 防护/CF 前置？前置后性能代价如何权衡？
Q7  备份范围建议（nginx.conf / systemd 单元 / letsencrypt / scripts / releases 保留策略）与恢复演练步骤？
Q8  `[待核对]` 22 端口的暴露范围与 SSH 加固（密钥 only ✓？fail2ban？来源限制？）现状是否达标？
Q9  流量红线 ≤150GB/月 的设定合理吗？按"视频上线后单访 10MB"推演，是否需要下调/上调？
Q10 监控缺口优先级排序：证书告警 / 站点可用性探测 / 发布后版本核对 / 磁盘与 IO / 容器健康，先做哪个？
```

---

## 13. 事实与测量来源

```
本会话实测（可复核）：srv1 规格与上行 2.9MB/s；srv1→srv2 295~550KB/s；srv2 规格/容器/端口/单元限额/证书字段；
  发布链 6 步输出（含 81.86MB tar 与原子切换后的版本目录）；站点流量 125.2MB；隔离回归（9 端口 SYN=0 / 对照 3）；
  直连 271~338KB/s vs Pages 9.6~17KB/s vs CF 隧道 0~10.7KB/s；nginx -t 通过、证书 SAN 四名
未复核（标 [待核对]）：实例费与续费价、22 端口的暴露面、心跳/磁盘告警的具体项与阈值、
  真实 srv1 检测组件清单、备份是否覆盖配置、Security Group 明细
参考文档：docs/角色动画与语音-实现全貌与服务器配置-给外部AI.md（§5 简版）｜ docs/ops-博客托管切换与回滚.md（切换/回滚原文）
          ｜ docs/HANDOVER-接手手册-给下一个AI.md（§1 环境/§3 发布链/§7 陷阱/§12 最新进展）
          ｜ deploy/srv2-site/README.md（落地物说明）
```
