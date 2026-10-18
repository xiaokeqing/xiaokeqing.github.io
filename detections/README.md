# detections —— 小柯实验室自写检测规则库

> 这个目录回答一个问题：**这些规则是谁写的、凭什么写。**
> 不是把 ET / Wazuh 现成规则搬过来，而是先在实验室真实日志里统计出"到底什么行为最多"，
> 再据此写匹配条件，并把每条的原始证据钉在这里。
>
> 状态（2026-10-18 更新）：**已部署到 srv2 并在生产生效** —— `xk-lab.rules` 经 `suricata.yaml: rule-files` 加载，
> `threshold.conf` 的 1 条精准抑制已启用，`cowrie_rules.xml` 的 100110 已改成 JSON 可触发的写法；两处 reload 都做过语法验证。
> 本目录仍未 git commit。变更与前后数字见文末 §5。

- Suricata 规则：`detections/suricata/xk-lab.rules`（7 条生效 + 1 条抑制型默认注释）
- Suricata 抑制：`detections/suricata/threshold.conf`（1 条生效 + 1 条注释态 opt-in）
- Wazuh 规则：`detections/wazuh/xk-lab_rules.xml`（3 条）+ `detections/wazuh/cowrie_rules.xml`（100100–100104、100110 的线上副本）
- 基线数据：srv2 `/opt/suricata/logs/eve.json`，2026-10-11 09:23 ~ 2026-10-18 12:00 UTC
  共 1,471,376 行：alert 293,482 / flow 612,516 / http 283,796 / ssh 142,926 / dns 132,086 / tls 6,801

---

## 0. 侦察结论：真实出现最多的 5 类行为（带计数）

| # | 行为 | 计数（7 天 / 单日） | 原文证据碎片 |
|---|------|--------------------|--------------|
| 1 | **蜜罐 SSH 会话海量涌入**（Cowrie :2222） | 2026-10-17 单日 14,147 会话；~590/小时，峰值 151/10min（19:20）；flow 侧 :2222 共 139,987 条 | `{"src_ip":"163.5.210.194","dst_port":2222,"eventid":"cowrie.session.connect","timestamp":"2026-10-17T00:00:09.420918Z"}` |
| 2 | **SSH 客户端指纹异常**（Go / libssh 库，机器人特征） | ssh 事件 142,926 中 `software_version:"Go"` 75,390、`libssh_0.9.3` 38,955；Cowrie 侧 `SSH-2.0-Go` 1,931、`libssh2_1.11.1` 3,275 | `"ssh":{"client":{"proto_version":"2.0","software_version":"Go"},"server":{...}}` + `"src_ip":"185.180.141.32","dest_port":2222` |
| 3 | **HTTP 密钥/配置探测**（`.env` 家族 / `.git/config`） | `.env` 家族 262 次；`/.git/config` 13；`/config.json` 7；`/web.config` 6；`/phpmyadmin/scripts/setup.php` 9。UA：`Go Web Pentest Tool` 155、`l9explore` 96、`zgrab` 72 | `{"src_ip":"130.12.180.117","http":{"hostname":"www.xiaokeqing.cn","url":"/.env","http_method":"GET","status":301}}` |
| 4 | **多端口顺序扫描 / 数据库端口直连** | 触及 ≥3 个诱捕端口的 (源,分钟) 窗口 53 个、涉及外部源 275；1433 告警 1,628（136 源）、3306 756（230 源）、6379 129 源、27017 67 源；Dionaea 侧 179.63.84.194 单源 2,752 次 1433 | `{"event_type":"flow","src_ip":"185.180.141.34","dest_port":2222,"flow":{"state":"closed","reason":"timeout"}}`；`{"signature":"ET SCAN Suspicious inbound to MSSQL port 1433","src_ip":"47.96.106.187","dest_port":1433}` |
| 5 | **「自家 agent」刷出的假警报**（最重要的一条，决定了噪声基线） | 293,482 条 alert 里 278,405 条 = 94.9% 是 `ET INFO Python-urllib/ Suspicious User Agent`，**100% 来自 10.0.0.10 → 169.254.0.4:80 的 POST /ca_report.cgi**（云主机元数据/心跳）；Wazuh 侧 18,228 条告警里 7,283 条是同一签名 | `{"src_ip":"10.0.0.10","dest_ip":"169.254.0.4","payload_printable":"POST /ca_report.cgi HTTP/1.1\r\n...User-Agent: Python-urllib/2.6"}` |

**顺带否掉的一个假设**：原本想写"僵尸网络 DNS 回连"规则，但 132,086 条 dns 事件里 rrname 前几名全是
正常基础设施（time1..5.tencentyun.com 各 ~23k、update2.agent.tencentyun.com 5,559、本站 demo.xiaokeqing.cn 9,628）。
**没有观测到可归因的 C2 域名 → 不写这条规则**（写了就是"看起来在监控"的死规则）。

另一个被数据否掉的假设：Wazuh 已部署的 `100110`（120s 内 5 次登录失败 → 爆破）。
2026-10-17 全天 Cowrie 只有 **19** 条 `login.failed`、**14,061** 条 `login.success`；
`alerts.json` 里 `grep '"id":"100110"'` 计数 **0**。因为机器人拿的是泄露口令表，第一发就"成功"。
→ 所以新规则改成按**会话建立速率**判（见 100400）。

---

## 1. Suricata 规则（`detections/suricata/xk-lab.rules`）

| 规则 id | 命中什么 | 依据的原始日志证据 | 建议动作 | 已知误报 |
|---|---|---|---|---|
| **1000101** | SSH 客户端 banner 以 `Go` 开头（Go SSH 库 = 爆破/僵尸网络工具链） | ssh 事件里 `software_version:"Go"` 75,390 条（占 52.7%）；样本 `2026-10-11T09:36:52` `185.180.141.32:20740 -> 10.0.0.10:2222` | 记入资产风险、按 `src_ip` 汇总排行；与 2222 命中联动提级 | 自研 Go 巡检脚本；云厂商/CI 的 Go 健康检查 |
| **1000102** | SSH 客户端 banner 以 `libssh`/`libssh2` 开头（自动化爆破框架默认库） | `libssh_0.9.3` 38,955 条；Cowrie `SSH-2.0-libssh2_1.11.1` 3,275 次（`143.198.159.21` 当日 2,587 会话） | 与 `1000103` 合流后按源封禁 | 自研备份/发布脚本；授权合规扫描器 |
| **1000103** | 同一源 60 分钟内 ≥120 次 SYN 到 :2222（≈2/min **持续**连接，2026-10-18 由 10/300s 调上来） | 按 `src_ip × 300s` 聚合：1,448 窗口 max=29 / p99=27 / mean=8.18，≥20 的窗口仅 42 个（2.9%）；top 源 `195.178.110.218` 29/5min、`45.148.10.161` 28/5min。**5 分钟窗的实测节奏**：`163.5.210.194` 24h 内 300s max=15 / median=12 / mean=12.06 ⇒ 阈值 ≤14 必然每 5 分钟一条（24h 677 条），≥15 又把它整个漏掉；改判 1 小时累计速率 | 自动加临时防火墙条目（1h）+ 记战报 | 实验室自查脚本（内部源已由 `$EXTERNAL_NET` 排除）；蜜罐重启补偿连接 |
| **1000104** | 同一源 60s 内 ≥3 次 SYN 落到诱捕端口组 `[21,22,23,1433,2222,3306,6379,9080,27017]` | 53 个 (源,分钟) 窗口触及 ≥3 端口；`47.96.106.187` 在 `2026-10-13T16:58` 一分钟打 9 个端口 | 判为横向探测器：拉黑 + 加进诱捕名单 | 背景测绘（Censys/Shadowserver 类），建议打标不封禁 |
| **1000105** | HTTP GET 目标为 `.env` 家族 / `.git/config` / `.git/HEAD` / `web.config` / `config.json` | `.env*` 262 次（`45.148.10.5` 单源 52 次、`80.94.95.211` 38、`213.209.159.154` 34）；`/.git/config` 13 次；样本见上表 #3 | 直接封源 + 检查站点是否真泄露（本站 Hugo 无 `.env`，301 即安全） | 站点 CI 拉 `.env` 做存在性校验；客户授权渗透 |
| **1000106** | UA 命中 `Go Web Pentest Tool / l9explore / zgrab / CensysInspect / zmap / Infrawatch / Nmap NSE / AttackWatch-PoC-Scanner` | 155 / 96 / 72 / 26 / 6 / 23 / 16 / 10 次；针对真实站点 `43.143.114.79` 的扫描 hostname 命中 171 次 | 只用于识别工具链与打标，**不作封禁依据**（UA 可伪造） | 安全团队自己的资产测绘；第三方合规监测探针 |
| **1000107** | 外部源 SYN 直连 DB 端口 `[1433,3306,6379,9200,27017]`（实验室对外不提供 DB） | 1433 告警 1,628 / 136 源；3306 756 / 230 源；6379 129 源；27017 67 源；Dionaea 单源 2,752 次 1433 | 直接封源（本实验室零合法外部 DB 连接） | 云厂商/监控平台端口探活（量极小，白名单排除） |
| **1000108**（默认注释，opt-in） | *抑制型*：`$HOME_NET -> 169.254.0.4:80 established` 走 `pass` | 278,405 条 / 94.9% 误报全部来自这一条出站 POST | 先在评估环境确认 `pass` 只静音自家 agent，再决定启用 | **写错方向会把真实 C2 一起静音**，故默认不启用；云厂商换 IP 后规则失效（失败模式=回到当前噪声，不会静默漏报） |

SID 段说明：`1000101–1000108` 属本地私有段，不占 ET 的 2,000,000–2,999,999，也不与 Suricata 内部 1/2/3 gid 冲突。

## 2. Wazuh 规则（`detections/wazuh/xk-lab_rules.xml`）

| 规则 id | 命中什么 | 依据的原始日志证据 | 建议动作 | 已知误报 |
|---|---|---|---|---|
| **100400** | 同一源 300s 内 ≥20 次 `cowrie.session.connect`（自动化爆破/刮削） | 2026-10-17 单日 14,147 会话；`src_ip × 300s` 窗口 max=29/p99=27/mean=8.18，≥20 仅 42 窗（2.9%）；top `195.178.110.218`(29)、`45.148.10.161`(28) | 提级到 10，进战报与封禁候选 | 实验室自查脚本；内部源 10.0.0.10 需白名单 |
| **100401** | 同一源 60s 内触及 **≥3 个不同**蜜罐端口（`same_field=src_ip` + `different_field=dst_port`） | flow 侧 53 个 (源,分钟) 窗口、275 个外部源；`47.96.106.187` 一分钟 9 端口；对照组 179.63.84.194 的 2,752 次全是单端口 1433（本条**不会**误报它） | 提级到 12，按横向探测处置 | 背景测绘；docker 网关 172.19.0.1（内部 lab 扫描） |
| **100402** | 蜜罐 MSSQL 收到**登录凭据**（已进认证阶段，`credentials` 键存在） | `credentials` 事件 2,753 条（mssqld 2,750 / mysqld 3），其中 2,750 条来自 `179.63.84.194`；原文 `"credentials": [{"password": "sa", "username": "sa"}]`；logtest 实测该字段被解码成字符串化数组 | 提级到 12，说明对方已过"探活"进到"猜口令" | 蜜罐连通性自测（带假凭据），需排除 |

与已部署规则的关系：不重复 `100100~100104`（单事件）、`100110`（失败次数聚合）、`100300~100302`（协议连上）、`100310`（同源 60s 内 6 次连接）。
本文件补的是这三个缺口：① 失败聚合在"几乎每次都成功"的蜜罐上失效 → 改用会话速率；② 100310 缺端口维度 → 100401 要求端口不同；③ 100301 不区分是否进到认证阶段 → 100402 单独提级。

三个实测踩过的写法（写在 XML 头注释里，别改回去）：
1. JSON 解码事件**不能用 `<same_source_ip/>`**（内部 `srcip` 字段为空，规则永不触发）→ 必须 `<same_field>src_ip</same_field>`；
2. `<if_matched_group>` 不写尾随逗号，`<group>` 要写；
3. 同一 rule 里 `<decoded_as>` 与 `<regex>` 不能共存（`Syntax error on tag 'regex'` 会让 analysisd 拒绝启动）。

---

## 3. 语法验证结果（实际执行，非声称）

| 检查项 | 命令 | 结果 |
|---|---|---|
| Suricata 规则语法 | `docker run --rm --network none --pull=never -v /tmp/xkrules:/rules:ro --entrypoint suricata jasonish/suricata:latest -T -S /rules/xk-lab.rules` | ✅ `Suricata version 8.0.7`，`Configuration provided was successfully loaded. Exiting.`，**exit 0**。另有 3 条 `W: detect: rule 1000103/1000104/1000107: SYN-only ... w/o direction specified, disabling for toclient direction` —— 只是提示"SYN 规则不会用于 toclient 方向"，属于预期内告警，不影响加载 |
| Wazuh 规则语法 | `docker run --rm --network none --pull=never -v /tmp/xkwazuh/etc:/var/ossec/etc --entrypoint /var/ossec/bin/wazuh-analysisd wazuh/wazuh-manager:4.9.2 -t`（`/tmp/xkwazuh/etc` = `docker cp wazuh.manager:/var/ossec/etc` 的快照 + 本文件） | ✅ **exit 0**，与"删掉本文件的对照实验"同样 exit 0 → 差异来自本文件且本文件无解析错误；`different_field` 被 4.9.2 接受 |
| 生产影响 | —— | **零**。两次验证都在一次性 `--rm` 容器内跑，没有 `docker exec` 进生产容器、没有改生产规则目录、没有 `reload`/`restart` suricata 或 wazuh。（2026-10-18 复核同样用一次性容器跑 `-T`；那次真 reload 是单独的部署步骤，见 §5） |

> 为什么不用 `suricata -T` 宿主机的：srv2 宿主机没装 suricata（`which suricata` → not found），
> 生产实例是 `jasonish/suricata:latest` 容器（`network_mode: host`，只被动抓包）。
> 用同一镜像起一次性容器做 `-T`，等价且更安全。

Wazuh `-t` 的踩坑记录（下次照抄）：一次性容器缺 `etc/ossec.conf` / `etc/internal_options.conf` /
`etc/shared/ar.conf`，前两次分别报 `ERROR: (1226): Error reading XML file 'etc/ossec.conf'` 和
`ERROR: (1103): Could not open file 'etc/internal_options.conf'`；只读挂载 `etc` 时分析器还要写
`etc/shared/ar.conf`（`(30)-(Read-only file system)`）。**正解**：`docker cp` 一份 `etc` 到 /tmp，可写挂载。

---

## 4. 边界（别误读）

- 本目录**没有**被任何自动化流程加载：hugo 站点只读 `content/ layouts/ static/` 等，`detections/` 是仓库根的旁路目录。
- 规则**已进** srv2：`detections/suricata/xk-lab.rules` → `/opt/suricata/rules/xk-lab.rules`（`suricata.yaml` 的 `rule-files` 里已列），
  `detections/suricata/threshold.conf` → `/opt/suricata/rules/threshold.conf`（`threshold-file` 指向它，改前 0 条生效、改后 1 条），
  `detections/wazuh/cowrie_rules.xml` → `/opt/wazuh/config/wazuh_cluster/rules/cowrie_rules.xml`。
  本仓库这几个文件与 srv2 上的同名文件 **md5 一致**（见 §5），改线上后要按同样方式回写，别只改一边。
- 阈值全部来自上表计数，改阈值前先重跑计数（`detections/` 里的数字都写清了窗口与分母，方便复核）。

---

## 5. 2026-10-18 生产变更记录（实测数字，可复核）

| # | 改了什么 | 改前 | 改后 | 验证 |
|---|---|---|---|---|
| 1 | Cowrie 下载留存：`/opt/cowrie/etc/cowrie.cfg` 加 `[honeypot] download_path=var/lib/cowrie/downloads` + `download_limit_size=10485760`，compose 加 `./dl:…/var/lib/cowrie/downloads` 绑定 | `file_download` 0 条、`/opt/cowrie/dl` 不存在（默认落在匿名 var 卷，宿主机看不到） | `/opt/cowrie/dl/` **4 个文件**（53/54/19/14 B，文件名=SHA-256）；`audit.log` 里有完整事件（`Downloaded URL (…) with SHA-256 … to var/lib/cowrie/downloads/<sha>`） | 走真实管线 `EventLog → EventDispatcher → jsonlog/audit` 调 `capture_download()` 落盘 + `docker exec cowrie python3`；**注意**：`logtype=rotating` 下由外部进程追加到 `cowrie.json` 的行会被活进程的写偏移覆盖（实测 5 秒内消失），JSON 事件要等真实会话内下载才会由活进程自己写进去 |
| 2 | 1000103：`threshold: type both, count 120, seconds 3600`（rev 2）；Wazuh 100110：`frequency=3 timeframe=300` + `<same_field>src_ip</same_field>` | 1000103 实测 30min 9 条 / 60min 20 条；24h 回放 677 条（15 源）。100110 真实命中 **0** | 1000103 改后 30min **0 条**（同期真实速率降到 2.5/min，属正常不触发）；60min 内 2 条：`11:29:08` `163.5.210.194`、`11:37:32` `45.148.10.155`（签名 `sustained burst (>=120/3600s)`）。100110 用 3 条同源 `login.failed` 回放第 3 条即 `Alert to be generated`（level 12） | `suricata -T`：42455 rules loaded / 0 failed / `threshold-config: 1 rule(s) found`；`wazuh-analysisd -t` exit 0；`suricata.log` 见同样三行，engine 重启成功 |
| 4 | 1000103 的离线 pcap 边界测试（一次性容器 `-r` 回放，`-k none`） | —— | 120 个 SYN / 600s → **恰好 1 条**（`pcap_cnt:120`）；119 个 / 600s → **0 条**；10 个 / 300s（旧阈值 10/300s 的触发量）→ **0 条** | `docker run --rm -v /tmp/tpcap:/pcap:ro … --entrypoint suricata jasonish/suricata:latest -r /pcap/burst120.pcap -c /etc/suricata/suricata.yaml -k none`；生成脚本 srv2 `/root/mkpcap.py` |
| 3 | `threshold.conf` 加 `suppress gen_id 1, sig_id 2013031, track by_src, ip 10.0.0.10`（另留整条注释态 opt-in） | 2013031 占全部告警 94.9%，实测 10min 301 条 | 重启后首个 10min 窗口 2013031 **0 条**，同期其它 sid 计数不变（1000102 18 / 1000104 16 / 2001219 2） | 同一份 `eve.json` 窗口切片对比；`suricata.log`：`Threshold config parsed: 1 rule(s) found` |

> 100110 早先"0 命中"有两个结构性原因，不是阈值太严：① JSON 解码事件内部 `srcip` 为空，`<same_source_ip/>` 永不相等；
> ② 机器人拿泄露口令表，第一发就 `login.success`（10-17 全天仅 17 条 `login.failed`/10 个源）。所以改成 `same_field` 后，
> 频率只需"300s 内 3 次失败"就能只抓真猜口令的源（10-12 `58.19.99.193` 单窗 12 次、10-13 4 次；`47.96.106.187` 4 次）。

> **风险点**：蜜罐网段被 `DOCKER-USER -s 172.19.0.0/16 -j DROP` 掐断出网 ⇒ 攻击者的 `wget`/`curl` 抓不到载荷，
> 留存链路虽已验证可用，真实样本仍要靠**放行出网**才会落盘（安全姿态变更，未擅自做）；
> 1000103 改成 `both` 语义后，单个源一小时最多 1 条（结构性上限，换来 −95.6% 噪音）；
> 2013031 的抑制只按 `by_src 10.0.0.10`，若该主机被攻陷，它对外的心跳类告警会一起不可见。
