# 站点一致性 CI —— 部署说明

> 目标：用一个「不装任何东西」的 bash 脚本，每 15 分钟把**线上真实可见的东西**和对外的**自报数据**对一遍，
> 四类检查写一份 `latest.json`。它只做**观测**，不改站点、不发布、不重启任何服务。
>
> 本文件是**部署说明**，不包含本次改动之外的任何操作。仓库里对应三个文件：
> `scripts/consistency-check.sh`、`scripts/consistency-check.service`、`scripts/consistency-check.timer`。
>
> 本文档最后更新：2026-10-17（全部结论基于本机离线验证 + 线上只读探测，**srv2 上尚未安装**）。

---

## 0. 一页速览

| 项 | 值 |
|---|---|
| 检查对象 | 7 个公开页面、8 个公开端点、srv2 上最新 release 的 `index.html` 指纹、后端 `buildSha` |
| 运行位置 | srv2（`/opt/secagent/tools/consistency-check.sh`），root 运行 |
| 触发 | `consistency-check.timer`，`OnCalendar=*:0/15`，`Persistent=true`，单次上限 `TimeoutStartSec=300` |
| 结果文件 | `/opt/secagent/reports/ci/latest.json`（每次覆盖，原子写入） |
| 明细日志 | `journalctl -u consistency-check.service` |
| 退出码 | `0` 全通过 / `1` 有检查失败 / `2` 脚本自身环境问题（缺 `python3`、报告没落盘…） |
| 依赖 | `curl`、`coreutils`（`sha256sum`/`date`/`mktemp`/`head`/`ls`）、`python3` 标准库。Ubuntu 22.04 全自带的，**不装任何东西** |
| 副作用 | 每 15 分钟对 `https://xiaokeqing.cn` 与 `https://demo.xiaokeqing.cn` 发 15~16 个 GET（含 3 个 JSON API）。全是只读 GET |
| 公开风险 | 退出码非 0 时 systemd 会把这次 unit 标成 `failed`（刻意为之，见 §1 末尾） |

---

## 1. 它检查什么

四类，`checks` 字段是**实际参与判定**的项数：

| 类别 | 项数 | 通过条件 | 失败是否红 |
|---|---|---|---|
| **① 公开页面** | 7 | HTTP 200 且响应体 `> 100000` 字节 | 红 |
| **② 公开端点** | 8 | HTTP 200 且 body 能被 `json.loads` 解析 | 红 |
| **③ 站点完整性** | 0 或 1 | srv2 上最新 release 目录的 `index.html` sha256 == 清单里记录的 sha256 | **仅当清单存在时**红；清单找不到 → `skipped`，不红、不计入 `checks` |
| **④ 后端版本** | 0 | `/api/health` 的 `buildSha` 与 `/api/public/deploy` 的 `data.build.sha` 一致 | **永不判红**，只写 `backend_commit`: `match` / `mismatch` / `unverified` |

所以正常情况下 `checks = 15`（7+8+0）或 `16`（7+8+1）。

**页面清单（7 个）**：`/`、`/alerts/`、`/ai/`、`/posts/`、`/what/`、`/status/`、`/lab/`
（原始需求写「六个」但列了七个路径；以列出的路径为准，七个都查。）

**端点清单（8 个）**：`health`、`home`、`alerts`、`audit`、`honeypot`、`geo`、`webstats`、`deploy`

**为什么「退出码非 0 就 failed」是有意的**：`weekly-report.service` 也是这个取舍 —— 巡检不是要好看，是要能在
`systemctl --failed`、日报、监控里被看见。静默地把红压成绿，等于没有 CI。代价是 timer 不会自动重试，
失败证据只有退出码 + `latest.json`（`Persistent=true` 只管「错过的一次补跑」）。

---

## 2. 设计上踩过的三个坑（读代码前先看这段）

这套检查的**判定标准是我按线上真实情况定的**，与最初的文字需求有三处不同，都写在这里，避免以后有人"改回去"：

### 坑 1：端点裸路径根本不存在，真路径是 `/api/public/<name>`

线上实测（2026-10-17，只读 GET）：

| 裸路径 | 实况 | 真路径 | 实况 |
|---|---|---|---|
| `/alerts` | **404**（`{"code":404,"message":"接口或资源不存在"}`，49 B） | `/api/public/alerts` | 200 |
| `/audit` | **404** | `/api/public/audit` | 200 |
| `/geo` | **404** | `/api/public/geo` | **502**（16 B，服务端当前真故障） |
| `/honeypot`、`/webstats`、`/deploy` | 超时 / 404 | `/api/public/honeypot` 等 | 200 |

脚本的做法：每个端点先试 `/api/public/<name>`，**只有不是 200 才**退到裸路径 `<name>`；
`latest.json` 里 `endpoints[].path` 记的是**实际用上的那条**。这样既符合现状，又能感知"哪天开始裸路径也能用了"。

### 坑 2：srv2 的 release 目录里**没有** `release-info.json`

从发布链源码核实（`scripts/srv2-site-receive.sh`，srv2 侧接收脚本）：它只做「解包 → 校验 → `mv` 原子切换
`/opt/secagent/site` → 留 4 个 release」，**从不写任何清单文件**。带 `indexSha256` 的 `release-info.json` 是
`scripts/publish-site-to-srv2.ps1`（第 6.5 步）写到 **srv1** 的
`/opt/secagent/data/public-api/release-info.json`，再由后端通过 `/api/public/deploy` 暴露。

另外那个接收脚本的整树哈希特意 `! -path './index.json'` —— 说明 release 目录里的 `index.json` 是 **Hugo 的
`/index.json` 产物页**（带每次都变的 `generatedAt`），**不是**发布清单。所以脚本**绝不**把 `index.json` 当清单。

因此 `③` 按顺序探测候选清单，探到哪个就用哪个（`site_integrity_recorded_in`/`site_integrity_manifest` 记来源）：

1. `<最新 release 目录>/release-info.json`
2. `<最新 release 目录>/.release-info.json`
3. `/opt/secagent/releases/.release-info.json`
4. `/opt/secagent/data/public-api/release-info.json`
5. `$MANIFEST_EXTRA`（可留空；想在别处放清单就指过去）

**一个都探不到就如实写 `"site_integrity":"skipped"`，并把原因写在 `site_integrity_detail` 里，绝不臆造字段。**
在 srv2 上这条大概率就是 `skipped`（因为本地确实没有清单）—— 这是**如实记录**，不是缺陷。

字段名也是先探测再认：先按已核实的真名 `indexSha256`，再试 `index_sha256` / `indexSHA256`，
最后才做"值侧兜底"（清单里任何**值**是 64 位十六进制且等于 `index.html` 的 sha256 就算对上）。

### 坑 3：`/api/public/deploy` 里的 commit 是**站点仓库**的 commit，不是后端的

线上实测：

- `/api/health`：`{"status":"ok","buildSha":"8a8014676ef188b8babe4353681b4a4238b14523","embeddedGitCommit":"8a80146","expectedReleaseCommit":"8a8014676e…","fingerprintMismatch":false,…}`
- `/api/public/deploy`：`data.build.sha` = 同一个 `8a801467…`；`data.release.commit` = `e8d3c4364f2cdacf46876f4acab25b59bdf0492a`（来自 `publish-site-to-srv2.ps1` 的 `git rev-parse HEAD`，是**站点**仓库）

所以 `buildSha` 与 `release.commit` **本来就应该不同**，拿它们比会天天假红。脚本只做：

- `health.buildSha`（或 `embeddedGitCommit` 前缀）vs `deploy.data.build.sha` → 一致写 `match`，否则 `unverified`，**永不判红**；
- 顺手把 `deploy.release.commit` 记进 `site_release_commit` 供人看，**不参与任何判定**；
- 附赠 `live_vs_api_release`：`/opt/secagent/site` 解析出的目标目录 vs `deploy.data.release.release`，
  只记录（`match`/`mismatch`/`unknown`），**不判红**（deploy 文件在 srv1，可能滞后一档发布）。

---

## 3. 文件 → 目标路径

| 仓库内文件 | 装到 | owner | mode |
|---|---|---|---|
| `scripts/consistency-check.sh` | `/opt/secagent/tools/consistency-check.sh` | `root:root` | `0755` |
| `scripts/consistency-check.service` | `/etc/systemd/system/consistency-check.service` | `root:root` | `0644` |
| `scripts/consistency-check.timer` | `/etc/systemd/system/consistency-check.timer` | `root:root` | `0644` |
| （运行时自动创建） | `/opt/secagent/reports/ci/` | `root:root` | `0755` |
| （运行时生成） | `/opt/secagent/reports/ci/latest.json` | `root:root` | `0644` |

`/opt/secagent/tools` 是既有约定（`weekly-report.sh` 也在这里），理论上应该已经在。

---

## 4. 安装（在 srv2 上，root）

> ⚠️ 本节命令**未在 srv2 上执行过**（本次任务明确"不部署"）。执行前请按 §7 先看一眼现场。

```bash
# 4.1 目录（已存在则不动）
sudo install -d -o root -g root -m 0755 /opt/secagent/tools
sudo install -d -o root -g root -m 0755 /opt/secagent/reports/ci

# 4.2 脚本（从 srv1 上的仓库目录，或先 git pull 到 srv1 再发行 —— 走你们既有的发布通道，不要手改服务器）
sudo install -o root -g root -m 0755 scripts/consistency-check.sh /opt/secagent/tools/consistency-check.sh

# 4.3 systemd 单元
sudo install -o root -g root -m 0644 scripts/consistency-check.service /etc/systemd/system/consistency-check.service
sudo install -o root -g root -m 0644 scripts/consistency-check.timer   /etc/systemd/system/consistency-check.timer
sudo systemctl daemon-reload
```

**先手工跑一次再开 timer**（见 §5）。确认绿了/原因清楚了，再：

```bash
sudo systemctl enable --now consistency-check.timer
systemctl list-timers --all | grep consistency      # 确认 NEXT 是 15 分钟内
```

**权限说明**：unit 里**故意没写 `User=`**（跟随 systemd 默认 = root），理由：

1. 要读 `/opt/secagent/releases/*/index.html`、`/opt/secagent/site` 和不定期出现的清单文件，这些属主是 root；
2. 要写 `/opt/secagent/reports/ci/`；
3. 和 `weekly-report.service` 保持一致（它也没有 `User=`）。

如果你想降权，需要同时满足：`/opt/secagent/reports/ci` 可写、release 目录与 `site` 链接可读、
`/opt/secagent/data/public-api/release-info.json`（如果在 srv2 上放一份）可读。**不要只加 `User=` 就了事。**

**这个 unit 不启用任何 hardening**（`ProtectSystem`/`PrivateTmp`/`NoNewPrivileges` 都没加）：
脚本只需要网络 + 一个临时目录 + 一个输出目录，加 hardening 的收益不大，反而容易在下次改脚本时
把 `mktemp` 或 `/opt` 写入搞坏，得不偿失。如果以后要加，`ProtectSystem=full` 是安全的（`/opt` 仍可写）。

---

## 5. 手工跑一次

```bash
# 5.1 最直接：直接跑脚本（root）
sudo bash /opt/secagent/tools/consistency-check.sh; echo "rc=$?"
```

- **stdout**：恰好一行 JSON（就是写进 `latest.json` 的那一行）；
- **stderr**：每项一行 `[OK]` / `[!!]` 明细，最后一行是汇总；
- 退出码：`0` 全通过、`1` 有失败项、`2` 脚本环境问题。

```bash
# 5.2 只想要摘要，不想看 15 行明细
sudo bash /opt/secagent/tools/consistency-check.sh 2>/dev/null | python3 -m json.tool

# 5.3 走 systemd 跑一次（验证 unit 本身，最接近定时触发的环境）
sudo systemctl start consistency-check.service
systemctl status consistency-check.service --no-pager -l   # 有 failed 就在这里看
journalctl -u consistency-check.service -n 40 --no-pager
```

**注意**：手工跑和 timer 跑是同一份脚本、同一个输出文件，谁最后跑 `latest.json` 就是谁的结果。

---

## 6. 怎么看结果

### 6.1 `latest.json`（唯一的机器可读输出）

固定三字段在前：`ts`、`ok`、`failed[]`、`checks`，其余是明细（`ensure_ascii=False`，中文原样）。

| 字段 | 含义 |
|---|---|
| `ts` | 运行时间，带时区偏移（`2026-10-17T23:00:31+08:00`） |
| `ok` | `failed` 为空即 `true` |
| `failed` | 失败短语列表，**每项自带原因**，例如 `page /lab/ -> HTTP 500`、`endpoint geo (https://demo.xiaokeqing.cn/api/public/geo) -> HTTP 502` |
| `checks` | 参与判定的项数（15 或 16） |
| `site_integrity` | `pass` / `fail` / `skipped` |
| `site_integrity_detail` | 人读的原因；`skipped`/`fail` 时**一定**看这里 |
| `site_integrity_manifest` / `site_integrity_recorded_in` | 用的是哪个清单文件、其中哪个字段/路径被认为是记录值（`path@文件` 形式），空串表示没有 |
| `site_index_sha256` | 本机算出的 `index.html` sha256 |
| `release_dir` / `live_target` | 最新 release 目录 / `/opt/secagent/site` 解析出的真实目标 |
| `live_vs_api_release` / `api_release_path` | 上面的佐证对比（`match`/`mismatch`/`unknown`）与 deploy 记录的路径 |
| `backend_commit` | `match` / `mismatch` / `unverified`（**永远不影响 `ok`**） |
| `backend_build_sha` / `backend_deploy_build_sha` | 两边各自取到的 sha，对不上时用来定位是谁落后 |
| `site_release_commit` | deploy 里记的**站点** commit（仅供参考） |
| `pages[]` / `endpoints[]` | 逐项明细：`path`/`http`/`bytes`/`ok`（端点还有 `json`） |
| `min_bytes` | 页面字节阈值，默认 100000 |

一行看健康：

```bash
sudo python3 -c 'import json;d=json.load(open("/opt/secagent/reports/ci/latest.json"));print(d["ts"],"ok=",d["ok"],"checks=",d["checks"],"failed=",d["failed"])'
```

### 6.2 日志

```bash
journalctl -u consistency-check.service --since '1 hour ago' --no-pager | tail -40
journalctl -u consistency-check.timer --since today --no-pager | tail -20
systemctl list-timers consistency-check.timer --all
```

### 6.3 怎么接监控（可选，不在本次范围）

`latest.json` 是稳定 schema：`ok==true` 即全绿。最简单的接法是
「`/opt/secagent/reports/ci/latest.json` 的 mtime 超过 20 分钟 ⇒ 巡检没在跑」+「`ok==false` ⇒ 告警」两条。
（本次**没有**接进任何监控/日报，别以为它已经在报警。）

---

## 7. 排错

先分清三种红：

| `failed` 长什么样 | 判定 | 去哪查 |
|---|---|---|
| `page /x/ -> HTTP 000` | **请求没成功**（DNS/连接/超时），不等于站点坏 | 是否在网络受限的地方跑的？从 srv2 复跑 |
| `page /x/ -> HTTP 5xx` | 站点/反代 5xx | `journalctl -u nginx`、上游服务 |
| `page /x/ -> N B（要求 > 100000）` | 拿全了但太小（或只拿到部分） | 产物是否完整、是否被 CDN/WAF 截断 |
| `endpoint x (...) -> JSON 解析失败` | 200 但 body 不是 JSON（多半是反代返回 HTML 错误页） | `curl -i` 看真身 |
| `endpoint x (...) -> HTTP 502` | 上游服务坏了 | 后端进程/容器、`/api/health` 是否 200 |
| `site_integrity -> sha256 不一致` | release 内容与清单不符（发布未完成 / 清单旧 / 被手改） | 两边时间戳，见下行 |

常见现象与动作：

1. **`site_integrity: skipped`，detail 说"没有清单文件"** —— srv2 上本来就**没有**清单（见 §2 坑 2）。
   想让这一项真跑起来，二选一：
   - 在 srv2 上放一份：`sudo install -m 0644 <某个可信来源>/release-info.json /opt/secagent/data/public-api/release-info.json`
     （路径会被 `manifest_candidates` 第 4 顺位探到）；
   - 或者跑的时候指出来：`MANIFEST_EXTRA=/path/to/release-info.json sudo -E bash /opt/secagent/tools/consistency-check.sh`。
   **不要**把 release 目录里的 `index.json` 指过来 —— 那是 Hugo 产物页，sha 永远对不上。
2. **`site_integrity: fail`** —— 先看 `site_index_sha256` 与 `site_integrity_detail` 里清单记录值的差，
   再比两边 `stat` 时间：目录旧 / 清单旧 / 有人在服务器上手改了文件。
   注意 `release_dir` 取的是 **mtime 最新的 `site-*`**；`.staging-*` 不在 glob 里，天然排除。
3. **`live_vs_api_release: mismatch`** —— deploy 的 `release.release` 与 `/opt/secagent/site` 指向不一致。
   多半是 srv1 上的 `release-info.json` 滞后（它由发布脚本第 6.5 步写）。**不红**，但值得看一眼是不是发布只完成了一半。
4. **`backend_commit: unverified`** —— `/api/public/deploy` 取不到或没有 `data.build.sha`。**不红**。
   若想查：`curl -s https://demo.xiaokeqing.cn/api/public/deploy | python3 -m json.tool`。
5. **`exit 2` / `[X] 缺 python3`** —— 这台机器没有 `python3`（Ubuntu 22.04 默认有；精简镜像可能没有）。
   脚本不装东西，装 `python3-minimal` 是唯一选项；装不了就接受这套 CI 跑不了。
6. **`systemctl status` 显示 timeout** —— 超过 `TimeoutStartSec=300`。15 个 GET 并发 8，最坏 ≈ 135 s；
   真撞 300 s 基本等于站点整体不可达（比 15 个检查慢本身更严重的问题）。
   应急：`CURL_MAX=20 CURL_CONNECT=5 sudo -E bash /opt/secagent/tools/consistency-check.sh`。
7. **页面全是 000、但 srv2 上 `curl` 又是好的** —— 你在**站主家宽**上跑的。
   2026-10-17 实测：家宽拉 `/posts/` 150 s 才 148 KB（≈1 KB/s），7 个页并发全部撞 240 s 上限；
   同一时刻 srv2 上取同样 URL 3 s 拿全。**这套检查必须在 srv2 上跑**，别在本地跑完就下结论。
8. **`/api/public/geo` 502** —— 2026-10-17 起就是 502（16 B），是服务端当前状态，不是脚本误报。
   它会让 `ok=false` 一直红；要么修后端，要么临时把 `geo` 从 `ENDPOINTS` 里注释掉（**改代码要过 review**）。

可调环境变量（都不改文件，直接前缀）：

```
SITE_BASE API_BASE RELEASES_DIR SITE_LINK MANIFEST_EXTRA REPORT_DIR MIN_BYTES CURL_MAX CURL_CONNECT PARALLEL
```

例如只查端点、阈值放宽、只要 4 并发：
`MIN_BYTES=50000 PARALLEL=4 sudo -E bash /opt/secagent/tools/consistency-check.sh`

---

## 8. 回滚

脚本和 unit 都是**纯新增**，没有任何东西依赖它们，回滚 = 停掉 + 删文件，**不影响站点服务、不影响 nginx、
不影响 `weekly-report`**。

```bash
# 8.1 立刻止住（保留证据）
sudo systemctl disable --now consistency-check.timer
sudo systemctl stop consistency-check.service

# 8.2 确认它真的不再跑
systemctl list-timers --all | grep consistency || echo "no timer left"
systemctl --failed | grep consistency || echo "no failed unit left"

# 8.3 移除 unit 与脚本
sudo rm -f /etc/systemd/system/consistency-check.timer \
           /etc/systemd/system/consistency-check.service \
           /opt/secagent/tools/consistency-check.sh
sudo systemctl daemon-reload
sudo systemctl reset-failed consistency-check.service

# 8.4 报告目录（想留证据就只留，不想要就删）
sudo rm -rf /opt/secagent/reports/ci
```

**只停不删**（先观察一周再决定）：执行 8.1 即可，timer 停了就不会再触发。
想「暂停但保留启用」：`sudo systemctl mask --now consistency-check.timer`（重启后也不会起来）。

**回滚到本次之前的版本**：这三个文件是本次新建的，没有旧版本可回退；如果你装过一版临时脚本，
按 §4 重新 `install` 覆盖即可（`install` 会就地替换，不产生 `.bak`）。

---

## 9. 已验证 / 未验证（务必分开看）

### ✅ 已实际验证（2026-10-17，本机 Windows + Git bash 5.3.9）

1. **`bash -n` 语法检查通过**（`C:\Program Files\Git\bin\bash.exe -n scripts/consistency-check.sh` → exit 0）。
2. **离线端到端跑通 6 个场景**（用假 `curl` + 假 `releases/` 目录 + 真 `python3` 标准库，不联网）：
   - 全绿：`exit 0`、`ok=true`、`checks=16`（含完整性 1 项）、`site_integrity=pass`；
   - 4 项失败（页面 500 + 端点 502 + 非 JSON + 404）：`exit 1`、`failed` 4 条、逐条带原因；
   - 把清单里的 `indexSha256` 改成全 0：`site_integrity=fail`、`exit 1`、`failed` 里出现 sha 两边值；
   - 删掉清单：`site_integrity=skipped`、`exit 0`、`checks=15`（**skipped 不判红**）；
   - `RELEASES_DIR` 指向不存在的目录：`skipped` + detail「在 … 下没找到 site-* 发布目录」、`exit 0`；
   - `PATH` 里没有 `python3`：`exit 2` + `[X] 缺 python3（Ubuntu 22.04 自带 3.10）`；
   - `REPORT_DIR` 指向多级不存在的路径：自动 `mkdir -p` 后正常写 `latest.json`。
3. **真机字段名已核实**（读源码 + 线上 JSON）：
   - `release-info.json` 的指纹字段是 **`indexSha256`**（`scripts/publish-site-to-srv2.ps1:444` 写入 srv1 的 `/opt/secagent/data/public-api/release-info.json`）；
   - `/api/health` 有 `buildSha`、`embeddedGitCommit`、`expectedReleaseCommit`、`fingerprintMismatch`；
   - `/api/public/deploy` 有 `data.build.sha`、`data.release.release`、`data.release.commit`、`data.release.totalBytes`。
4. **线上真实响应已核对**（只读 GET，站主家宽）：7 个页面均 `200`；8 个端点里 7 个 200 且是 JSON，
   `/api/public/geo` 是 `502`；**裸路径 `/alerts`、`/audit`、`/geo` 均 404**（故脚本用 `/api/public/*` 为主路径）。
5. **页面字节数确实 > 100000**（阈值成立）：`/posts/` 150 s 收到 148803 B（未完）、`/lab/` 156101 B（未完）、
   `/what/` 158127 B、`/status/` 171875 B、`/ai/` 213012 B、`/` 139077 B、`/alerts/` 113641 B。
   （早先一次并发探测得到 `/posts/` 10924 B、`/lab/` 54985 B，是**家宽限速下的部分下载**，不代表真实大小。）
6. `date +%Y-%m-%dT%H:%M:%S%:z` 与 `sha256sum`、`mktemp -d`、`readlink -f`、`wait -n`（bash≥5.0）在 Git bash 下行为正确
   （Ubuntu 22.04 的 coreutils 与 bash 5.1 同样支持这些）。

### ❓ 未验证（本次明确不做 / 无法在本机做）

1. **srv2 上从未安装过、从未运行过**（`TimeoutStartSec`、root 权限、`/opt/secagent/releases` 的实际内容、
   `index.html` 是否存在、`/opt/secagent/site` 链接形态、`/opt/secagent/data/public-api/` 是否存在，全部未知）。
   本次任务明确「不部署、不碰 srv2」。
2. **unit 文件没有用 `systemd-analyze verify` 校验过**（本机是 Windows，没有 systemd）。
   语法是照 `weekly-report.service`/`.timer` 的结构写的，`OnCalendar=*:0/15` 的语义也未在真机 `systemd-analyze calendar` 上验证过。
3. **Ubuntu 上的 `python3` 是 3.10**：脚本只用标准库（`json`/`os`/`sys`/`hashlib`），没用到 3.11+ 特性，
   但**没有在 3.10 上实际执行过**（本机跑的是 3.13 系列的 Windows 构建）。唯一的兼容风险点是 f-string 之外的语法——当前脚本里没用到。
4. **`live_vs_api_release` 在 srv2 上是否 `match`**：离线夹具里因为 Windows 路径形态（`E:/…` vs `/e/…`）显示 `mismatch`，
   属测试夹具假象；真机上两边都是真路径，预期 `match`。该字段**不参与判定**。
5. **`site_integrity` 在 srv2 上最可能的结果是 `skipped`**（srv2 无清单）——这需要装完跑一次才能确认；
   如果你们另有把 `release-info.json` 落到 srv2 的流程，请把路径加到 `MANIFEST_EXTRA`（见 §7 第 1 条）。
6. **没有接入任何告警/日报**：`latest.json` 只落盘，没有人会因此被通知。
7. **没有跑 hugo、没有 `git add/commit/push`、没有 scp 上传、没有动 srv1/srv2** —— 按任务约束。

---

## 10. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-17 | 初版三件套：`scripts/consistency-check.sh`（四类检查、并发 8、退出码 0/1/2、JSON 摘要）、`consistency-check.service`（oneshot，300 s）、`consistency-check.timer`（`*:0/15`，`Persistent=true`）。本机离线 6 场景验证通过；**尚未在 srv2 安装**。 |
