---
title: "我打的攻击，我的平台能看见吗 —— 一次可复现的紫队自测设计"
date: 2026-10-18
type: post
categories: ["紫队演练"]
tags: ["purple-team", "detection-engineering", "suricata", "wazuh", "自测"]
summary: "在自己靶场里主动打三下（SSH 爆破 / 端口扫描 / Web 探测），每一击都指定一条该命中的规则，再用 eve.json 和 alerts.json 的 grep 去对账。结论先摆好：规则还没部署，所以「实测命中」这一栏全部是未验证 —— grep 返回 0 证明的是没加载，不是没命中。"
description: "紫队自测设计：三条可测攻击对应 Suricata SID 1000101–1000108 与 Wazuh 100400–100402，给出发起命令、预期命中理由（含 detections/README.md 的真实窗口分布与计数）与 eve.json / alerts.json 的 grep 验证方法；未部署、未验证的部分如实标注。"
ShowToc: true
---

## 先说清楚这一篇要回答什么

问题只有一句：**我自己打出去的那一下，平台上有没有一条规则会响？**

这个问题不能靠"规则写得对"来回答。规则对不对是语法问题，`suricata -T` 与 `wazuh-analysisd -t` 已经回答过了（两份文件在 `detections/` 下，只做了语法验证，没进生产目录）。剩下的是另一件事：**把攻击真的打一遍，看日志里有没有那条告警**。

所以这篇不是战报，是一份**自测设计加一张待填的对账表**。我按"攻击动作 → 预期命中哪条 → 怎么验证"组织，最后如实写我验到了什么。

## 数字的出处（先立规矩）

- 规则本体：`.suricata` 七条生效 + 一条 opt-in 注释（SID `1000101–1000108`），Wazuh 三条（`100400–100402`）。
- 基线计数：srv2 `/opt/suricata/logs/eve.json`，**2026-10-11 09:23 ~ 2026-10-18 12:00 UTC 共 1,471,376 行**，其中 alert 293,482 / flow 612,516 / http 283,796 / ssh 142,926 / dns 132,086 / tls 6,801。
- 上面这两个来源是 `detections/README.md` 与其引用的原始日志。**本文所有阈值和计数都从这里来，没有一个是新编的。**

顺手交代一句：我按任务要求去翻了 `docs/Amadeus-项目总文档-20261017.md` 的 §19，那一节记的是 2026-10-18 的前端/后端/发布链改动（首屏聚合扩到五块、tar 包里"没有 index.html"的假失败、手机顶栏重做……），**里面没有任何 SID、也没有检测口径**。所以这一篇不引它，只引 `detections/README.md`。写在这里是为了下一个人不用再翻一遍。

## 一、SSH 爆破：往 :2222 打十次

**打法**。靶场的 SSH 面是蜜罐（Cowrie `:2222`），只走内网，所以要先 SSH 隧道进去或用内网机器发起。测"会话速率"这种规则，要点是**匀速**而不是并发拉满：

```bash
# 一条一条来，十次，中间歇几秒 —— 目标是"5 分钟内 ≥10 次建连"
for i in $(seq 1 10); do
  ssh -o PreferredAuthentications=password -o ConnectTimeout=3 \
      -p 2222 test@10.0.0.10 "true" 2>/dev/null
  sleep 25
done
```

**预期命中**：`1000103`（同源 300s 内 ≥10 次 SYN 到 :2222）。这条是给"慢而稳"的源定的，依据是原始数据的窗口分布：按 `src_ip × 300s` 聚合出 **1,448 个窗口，max 29 / p99 27 / mean 8.18**，其中 **≥20 的只有 42 个（2.9%）**，头部源 `195.178.110.218` 29 次/5min、`45.148.10.161` 28 次/5min。所以 10/300s 能覆盖大多数真实源，20/300s 只抓脉冲型。

另两条是同一批打进来的"附带指纹"，**不应当**因为我自己用 OpenSSH 就响：

- `1000101`：客户端 banner 以 `Go` 开头。真实 ssh 事件 142,926 条里 `software_version:"Go"` 有 75,390 条（52.7%），这是 Go SSH 库的机器人特征；我用 OpenSSH 打，这条不响才对，响了就是误报。
- `1000102`：banner 以 `libssh`/`libssh2` 开头（`libssh_0.9.3` 38,955 条）。

Wazuh 侧对应的是 `100400`（同源 300s ≥20 次 `cowrie.session.connect`）。这条对自测不友好：同一份窗口分布里 ≥20 只占 2.9%，我上面那十次打不到它 —— 想验 `100400` 得真的堆到 20+ 次/5min。

## 二、端口扫描：按顺序点三个以上诱捕端口

**打法**。判据是"同一源、60 秒内、打到 **≥3 个不同**诱捕端口"，所以关键是**端口要不同**，不是包要多：

```bash
# 诱捕端口组：21,22,23,1433,2222,3306,6379,9080,27017
nmap -sS -Pn -n -p 21,22,23,2222,3306 10.0.0.10
```

**预期命中**：`1000104`（60s 内 ≥3 个诱捕端口）。真实数据里这种 (源,分钟) 窗口有 **53 个、涉及 275 个外部源**，`47.96.106.187` 在 `2026-10-13T16:58` 一分钟打了 9 个端口。

打数据库口时再叠一条 `1000107`（外部源直连 `1433/3306/6379/9200/27017`；真实 1433 告警 1,628 条/136 源、3306 756 条/230 源）。**这里必须跑一次负样本对照**：只打单端口、打 2,752 次也不该触发 `1000104`/`100401` —— 真实对照就是 `179.63.84.194` 的 2,752 次全落在 1433 一个口上，规则设计上它不该被这两条报出来。我的自测里"该响的响了、不该响的没响"才算通过，只测前者是自欺。

## 三、Web 探测：五个路径 + 换一个 UA

**打法**：

```bash
for u in /.env /.git/config /config.json /web.config /phpmyadmin/scripts/setup.php; do
  curl -s -o /dev/null -w "%{http_code} $u\n" "http://10.0.0.10:8081$u"
done
curl -s -o /dev/null -A 'zgrab/0.x' "http://10.0.0.10:8081/"
```

**预期命中**：`1000105`（`.env` 家族 / `.git/config` / `.git/HEAD` / `web.config` / `config.json`）。真实计数：`.env` 家族 262 次、`/.git/config` 13 次、`/config.json` 7 次、`/web.config` 6 次、`/phpmyadmin/scripts/setup.php` 9 次 —— 数字这么小，说明这条规则**不是按"量大"定的，是按"打到了就是意图明确"定的**。

换 UA 打的那一发给 `1000106`（`Go Web Pentest Tool / l9explore / zgrab / CensysInspect / zmap / Infrawatch / Nmap NSE / AttackWatch-PoC-Scanner`，真实 155/96/72/26/6/23/16/10 次）。这条在规则里就写明**只打标、不作封禁依据**，因为 UA 可以随便改 —— 自测时它响了只证明解析链路通，不证明防护有效。

## 四、怎么验证：grep 两个文件

Suricata 看 `eve.json`（一行一个 JSON），按 `signature_id` 对账；Wazuh 看 `alerts.json`，按 `rule.id` 对账：

```bash
# 有没有这条规则的告警（-c 只数条数，先看是不是 0）
grep -c '"signature_id":1000103' /opt/suricata/logs/eve.json
grep '"signature_id":1000104' /opt/suricata/logs/eve.json | tail -n 5

# 只看我自己这台源的，别被别人的扫描混进来
grep '"signature_id":1000103' /opt/suricata/logs/eve.json | grep '"src_ip":"10.0.0.20"'

# flow 面：1000103 的输入证据（会话速率）
grep '"dest_port":2222' /opt/suricata/logs/eve.json | grep '"event_type":"flow"' | tail -n 50

# Wazuh
grep '"id":"100400"' /var/ossec/logs/alerts/alerts.json | tail -n 3
grep -c '"id":"100401"' /var/ossec/logs/alerts/alerts.json
```

**关键顺序**：先确认规则文件**在生产规则目录里、且被加载**，再 grep。否则 `grep -c` 返回 0，你无法区分"没命中"和"没加载"。这两种情况含义完全相反，混在一起写就是假战报。

## 五、我这次的实测结果

诚实版本：**本次没有部署**。两份规则文件仍在 `detections/` 旁路目录，没进 srv2 的 `/var/ossec/etc/rules/` 与 `/opt/suricata/rules/`，也没 reload 任何生产进程。语法验证用的是 `--rm` 一次性容器（`Suricata version 8.0.7`，`Configuration provided was successfully loaded`，exit 0；Wazuh `wazuh-analysisd -t` exit 0），生产影响为零 —— 这是 `detections/README.md` §3 的记录，我没有重跑。

所以：

| 规则 | 部署状态 | 本次实测命中 | 结论 |
|---|---|---|---|
| `1000101` `1000102`（指纹） | 未部署 | 未验证 | 不能报"命中"也不能报"没命中" |
| `1000103`（SSH ≥10/300s） | 未部署 | 未验证 | 同上 |
| `1000104` `1000107`（扫描/DB 口） | 未部署 | 未验证 | 同上 |
| `1000105` `1000106`（Web/UA） | 未部署 | 未验证 | 同上 |
| `1000108`（抑制自家心跳） | 默认注释、未启用 | 未验证 | opt-in，写错方向会连真实 C2 一起静音 |
| `100400` `100401` `100402`（Wazuh） | 未部署 | 未验证 | 同上 |

**"我打的攻击，我的平台能看见吗？"** 在部署之前，答案就是**看不见** —— 不是它没看见我，是我还没给它眼睛。这句话不好听，但它比一张全是"命中"的表可靠。

## 六、三个已经踩过的坑（自测前先记住）

1. **按失败次数写的规则在这套蜜罐上是空转的**。已部署的 `100110`（120 秒内 5 次登录失败）在 2026-10-17 全天 Cowrie 只有 **19 条 `login.failed` 对 14,061 条 `login.success`**，`alerts.json` 里 `"id":"100110"` 计数 **0**。机器人拿泄露口令表，一枪就中 —— 所以新的 `100400` 改成按会话建立速率判。我自测时如果只发错误口令，测的其实是这条空转规则。
2. **94.9% 的告警是自家的**（293,482 条里 278,405 条是 `10.0.0.10 → 169.254.0.4:80 POST /ca_report.cgi`）。自测前先想清楚：你 grep 出来的"命中"可能全是云主机心跳，`1000108` 就是为消掉它写的。
3. **Wazuh JSON 事件不能用 `<same_source_ip/>`**（内部 `srcip` 为空，规则永不触发），要用 `<same_field>src_ip</same_field>`；`<if_matched_group>` 不写尾随逗号；同一 rule 里 `<decoded_as>` 和 `<regex>` 不能共存，会让 analysisd 拒绝启动。这三条是写 XML 时真撞过的，别改回去。

## 下一步的顺序（别颠倒）

1. 部署：把两份文件放进生产规则目录，`suricata -T` / `wazuh-analysisd -t` 通过后 reload；
2. 自测：按上面三条打一遍，带上负样本对照；
3. 只有第 2 步能把 grep 从 0 变成非 0，"紫队闭环"才成立。

在完成第 1 步之前，这一页（和这篇）能提供的只有**设计与口径**，提供不了**命中证据**。
