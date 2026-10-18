---
title: "163.5.210.194：一条零失败率的 SSH 爆破链（2026-10-15 ~ 10-18）"
date: 2026-10-18
type: post
categories: ["威胁分析"]
tags: ["attack-analysis", "honeypot", "suricata", "wazuh", "攻防复盘"]
summary: "一周内 6,956 次会话、6,931 次登录成功、6 次失败，0 条命令、0 条 Suricata 告警、0 次封禁。163.5.210.194 是一条「只打 2222、一枪就中、登进去就走」的机器人，它把失败次数型规则整条废掉了。"
description: "复刻一条真实攻击链：Suricata 首见 flow（midstream/timeout）、Cowrie 首见会话、单端口特征、每会话 0.997 次成功登录、command.input=0、audit.js 里 18 条封禁全是自测地址。含检测质量复盘：94.9% 告警是云 agent 心跳、规则 100110 命中 0、按会话速率（10/300s vs 20/300s）的实测窗口分布。"
ShowToc: true
---

先说结论：一个只打 2222 端口、一天近三千次会话、**99.6% 一枪命中**的源，7 天里没有产生任何一条 Suricata 告警，也没有被任何一次封禁。

## 为什么挑这一条

2026-10-17 全天 Cowrie 记到 11,847 个会话，这个源占 3,359 个（28.4%），当天第一；全周 6,956 次会话、6,931 次登录成功、**只有 6 次失败**（0.09%）。它把「失败次数」这个维度整条废掉了——机器人不失败，所以按失败次数写的规则永远不会响。

数据源与口径：Suricata `/opt/suricata/logs/eve.json`（1,475,091 行，2026-10-11 09:23 ~ 10-18 04:28 UTC，仍在增长，alert 共 294,112 条）；Cowrie `cowrie.json*`（同周期 136,463 次建连）；Wazuh `alerts.json` 加 10-11 起的轮转包（合计约 74 万条）；处置留痕取 `https://demo.xiaokeqing.cn/api/public/audit.js`（generatedAt `2026-10-18 12:25:47`）。全文时间均为 UTC，Cowrie 计数按 timestamp 的 UTC 日期聚合。

## 首见：先失败一次，19 分钟后才建成会话

Suricata 比蜜罐早看到它 19 分钟，而那次没握上手：

```json
{"timestamp":"2026-10-15T18:47:50.326891+0000","event_type":"flow",
 "src_ip":"163.5.210.194","src_port":49737,"dest_ip":"10.0.0.10","dest_port":2222,
 "flow":{"pkts_toserver":3,"pkts_toclient":1,"bytes_toserver":162,"bytes_toclient":58,
  "start":"2026-10-15T18:47:38.324750+0000","state":"closed","reason":"timeout","alerted":false,
  "exception_policy":[{"target":"stream_midstream","policy":"ignore"}]}}
```

`reason: timeout`、`alerted: false`、来回只有 3+1 个包。19:06:56 蜜罐才记到第一个完整会话（session `eb943b776b79`，源端口 60664），Suricata 对应的 ssh 事件是 19:07:07，同一源端口。

| 日期（UTC） | 会话数 | 登录成功 | 失败 |
|---|---|---|---|
| 10-15 | 614 | — | — |
| 10-16 | 2,288 | 2,285 | 3 |
| 10-17 | 3,359 | 3,346 | 1 |
| 10-18（至 04:28） | 695 | — | — |

## 扫描阶段：这一段是空的，而空掉的原因很重要

截至 10-18 04:25 快照，eve.json 里属于它的 13,904 行事件中 13,903 行 `dest_port=2222`，唯一例外是蜜罐主动回连的出向流（`10.0.0.10:2222 → 163.5.210.194:56144`，10-17 15:33:02），7 天没有任何多端口探测。原因有三个：云安全组对未放行端口直接丢包，SYN 到不了传感器；它本来就不是扫描器，是拿弱口令表直奔 SSH 的机器人；Suricata 侧 100% 的 ssh 事件里客户端 banner 只有一种——`"software_version":"OpenSSH"`（裸的，没有版本号，6,952 条）。

这件事直接废掉两条指纹规则：`1000101`（Go banner）和 `1000102`（libssh）在这条源上命中率必然为 0。不是没写对，是对方故意伪装成 OpenSSH。剩下的只有行为维度。

## 爆破：每会话 0.997 次登录，没有第二次尝试

10-17 零点第一个会话，三条事件就够了：

```json
{"session":"dd34eda1451c","src_ip":"163.5.210.194","dst_port":2222,"eventid":"cowrie.session.connect","timestamp":"2026-10-17T00:00:09.420918Z"}
{"session":"dd34eda1451c","src_ip":"163.5.210.194","username":"dell","password":"******","eventid":"cowrie.login.success","timestamp":"2026-10-17T00:00:10.435494Z"}
{"session":"dd34eda1451c","src_ip":"163.5.210.194","duration_ms":2264,"eventid":"cowrie.session.closed","timestamp":"2026-10-17T00:00:11.684858Z"}
```

1.0 秒完成登录，1.2 秒后连接就断了。会话时长（6,950 条 connect→closed）中位数 2.54 秒、p90 3.79 秒、最短 0.249 秒。

口令全是弱结构：第一名「6 位纯数字」占 2,260/6,931（32.6%），第二名「3 位纯数字」，第三名「6 位全 1」。用户维度 root 963 次（13.9%），其余是 dell / user / admin / test / ubuntu 这类设备默认账号。6,956 个会话发出 6,931 次成功登录 —— 平均每个会话 0.997 次，说明它口令牌第一发就中，从不重试。

## 停在登录层：command.input = 0

全周所有源合计 13.6 万个会话，`cowrie.command.input` 计数是 **0**；就这条源本身，6,956 个会话里也没有任何一条命令事件。没有 shell、没有 `wget`、没有 `chattr +i`，会话在 `session.closed` 就到头了。这类机器人要的不是这台机器，是「能登进去的机器清单」。

（保留一句反面可能：也可能是我在蜜罐里只给假 success、它发现拿不到 shell 就走了。但日志侧确实一条命令都没收到。）

## 处置：没被 ban，而且 18 条封禁全是自测

`audit.js` 的 summary：`blockTotal 18 / blockActive 0 / blockedByGuard 98 / executedActions 36`。18 条逐条看：

| IP | 条数 | 性质 |
|---|---|---|
| 1.2.3.4 | 8 | 自测（actor responder-agent） |
| 45.83.91.55 | 4 | 自测 / 演示 |
| 45.83.91.66 / .77 / .88 / .12 | 5 | 演示 |
| 198.18.0.9 | 1 | 保留地址 |

没有一条是真实攻击源，`163.5.210.194` 不在表里；18 条全部 `blockActive: 0`（60 分钟后自动解封，最长只挂了 60 分钟）。而 actions 里 30 多条是 `target=未知`、`reason=封禁目标 IP 为空`、`success=false`，另有 98 条被 guard 拦。处置链断在「拿不到可用 IP」，不是断在「没看见」。

「没看见」这条不成立：Wazuh 侧与这个 IP 相关的告警有 **22,963 条**（`100100` 7,661、`100104` 7,660、`100102` 7,642），全部停在告警列表里，没有任何一条进到处置链。

## 检测质量：94.9% 的告警是自家心跳

截至 10-18 04:25，294,112 条 alert 里 **279,099 条（94.9%）**是 `10.0.0.10 → 169.254.0.4:80 POST /ca_report.cgi`（签名 `2013031 ET INFO Python-urllib/ Suspicious User Agent`）。真实外部流量只占 5.1%。

```json
{"timestamp":"2026-10-11T09:23:07.131065+0000","event_type":"alert","src_ip":"10.0.0.10","dest_ip":"169.254.0.4","dest_port":80,
 "alert":{"signature_id":2013031,"signature":"ET INFO Python-urllib/ Suspicious User Agent","category":"Attempted Information Leak"},
 "http":{"hostname":"169.254.0.4","url":"/ca_report.cgi","http_method":"POST","http_user_agent":"Python-urllib/2.6"}}
```

已部署的 Wazuh 规则 `100110`（120 秒内 5 次登录失败）7 天命中 **0 次**（10-11 到 10-18 每个轮转文件逐个 grep，都是 0）——10-17 全天只有 17 条 `login.failed` 对 11,770 条 `login.success`。按失败次数报警在这套蜜罐上是空转。

正确的维度是**会话速率**。这条源的实测：614 个 5 分钟窗口，max 14、median 12、mean 11.33，其中 ≥10 的有 544 个。所以：

| 阈值 | 对 163.5.210.194 的效果 |
|---|---|
| Suricata `1000103`：10 次 / 300s | 544 个窗口命中 |
| Wazuh `100400`：20 次 / 300s | **一次都不中**（峰值只有 14） |

20/300s 是给 `195.178.110.218`（29 次/5min）、`45.148.10.161`（28 次/5min）那种脉冲源定的；10/300s 才覆盖这种「稳、慢、持久」的源。这不是阈值写错，是分层取舍——20 保精度，10 保覆盖，慢速源只能靠后者。

## 我为此补了什么

| 规则 | 对应的观测 |
|---|---|
| `1000103` 2222 端口 ≥10 次/300s | 直接对标这条源（544/614 窗口） |
| `1000101` Go banner / `1000102` libssh | 本源 banner 是裸 `OpenSSH`，两条都不中；留着抓偷懒的 Go/libssh 工具链 |
| `1000104` 多诱捕端口 ≥3/60s | 本源没有；给 `47.96.106.187`（一分钟 9 个端口）写的 |
| `1000105` `.env`/`.git` 探测、`1000107` DB 端口 | 与本源无关（它只打 2222），按另一批实测写的：262 次 `.env` 探测、1433 端口 6,760 条 flow |
| `1000108` 抑制 169.254.0.4:80 心跳 | 消掉那 94.9% 的自噪声 |
| Wazuh `100400` / `100401` / `100402` | 会话速率 ≥20/300s、跨端口 ≥3/60s、MSSQL 收到凭据 |

文件在 `detections/suricata/xk-lab.rules`（SID 1000101–1000108）和 `detections/wazuh/xk-lab_rules.xml`（100400/100401/100402）。两份都只做了语法验证，**没有部署**——这也是这条链能被完整记下来的原因：它在生产规则集里从未被拦下过。

复现：

```bash
grep '"src_ip":"163.5.210.194"' /opt/cowrie/logs/cowrie.json* \
  | python3 -c 'import sys,json,collections;c=collections.Counter(json.loads(l)["eventid"] for l in sys.stdin);print(c)'
```

一条 6,931 次成功登录的链路，7 天里既没告警，也没封禁。
