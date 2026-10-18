---
type: projects
title: 项目
summary: 五个可核实的项目记录：Amadeus 安全观测平台、可复现部署链、公开只读 API、内网靶场、AI 问答层。每项写明是什么、技术栈、地址与负责部分，核实不了的标待补。
description: 五个可核实的项目记录：Amadeus 安全观测平台、可复现部署链、公开只读 API、内网靶场、AI 问答层。每项写明是什么、技术栈、地址与负责部分，核实不了的标待补。
date: 2026-10-17
layout: "list"
note: 以上「是什么 / 技术栈 / 地址」都能在仓库里找到对应文档或脚本；标了「待补」的指仓库里没有证据的项（例如靶场的公网地址）。数字会随线上变化，本页不替代 `/api/public/*` 的实时返回。想看这些数字现在是否还活着 → [`/status/`](/status/)（8 个端点逐个体检：状态码、耗时、字节数、PASS/FAIL）；想看完整接口清单 → [`/api/`](/api/)（17 个端点 + 可直接复制的 curl + 脱敏口径）。
ShowToc: false
ShowReadingTime: false
ShowBreadCrumbs: false
hidemeta: true
comments: false
---

这一页列的是 xiaokeqing.cn 上实际在运行的东西，不是「规划中的项目」。每张卡的四行（是什么 / 技术栈 / 地址 / 我负责）都能在仓库文档或脚本里找到对应证据；仓库里找不到证据的，直接写「待补」。

## ① Amadeus 智能安全观测平台

- **是什么**：把主机层（Wazuh）、网络层（Suricata）与蜜罐（Cowrie / Dionaea）的告警汇到同一套页面和一套公开只读 API 的安全观测站。线上入口就是本站：监测中心看告警、蜜罐战报与处置审计，AI 安全页直接对着知识库提问。
- **技术栈**：前端 Hugo 静态站（SPA 导览外壳 + 服务端预渲染，零框架、零第三方脚本）；后端 Spring Boot `sec-agent`（单 JVM，公开端点 + 快照缓存 + 限流 + 脱敏）；采集侧 srv2 跑 Suricata、Wazuh、Cowrie 与 Dionaea，nginx 只对外提供 JSON。
- **地址**：[https://xiaokeqing.cn/](https://xiaokeqing.cn/) · 监测中心 [/alerts/](https://xiaokeqing.cn/alerts/) · AI 问答 [/ai/](https://xiaokeqing.cn/ai/)
- **我负责**：整站前端、公开 API 的缓存 / 限流 / 脱敏、检测链路接入与发布链。

## ② 可复现部署链（内容哈希 + tree 哈希 + 构建断言 + 原子切换 + 回滚）

- **是什么**：发布不是「scp 一把」。发送侧先在干净的 `git worktree` 里构建，产物先过 `scripts/assert-build.sh` 的硬断言，再算整树内容哈希（与线上接收侧逐字节同口径，SSH 远端用同一条 `LC_ALL=C` 字节序命令、排除带构建时刻的 `index.json`）；与线上相同就判 no-change 不上传，不同才上传。远端解包 → 校验 → 原子切换 → 自检，任一步失败自动回滚到上一版（`--rollback` 可手动回到上一版），服务器保留最近 4 个版本。切换后还会重算一次线上整树哈希与本地比对，作为最终核对。`-DryRun` 能在上传前就把整树哈希打印出来。
- **技术栈**：PowerShell（发送侧）+ bash（接收侧）+ ssh；`git worktree` 保证干净构建（顺带绕开中文文件名）。本次发布同时写 `release-info.json`（release / commit / files / totalBytes / indexSha256 / history，部署面板的真实数据源）。
- **地址**：仓库脚本 `scripts/publish-site-to-srv2.ps1`、`scripts/srv2-site-receive.sh`、门禁 `scripts/assert-build.sh`（不对外提供下载，见仓库文档）
- **我负责**：整条链的设计与实现，含断言清单与回滚路径。

## ③ 公开只读 API 与脱敏

- **是什么**：六个只读 GET 端点（`health` / `audit` / `honeypot` / `alerts` / `geo` / `stories`+`story?src=`），问答另有一个 `POST /api/public/ask`，全部零鉴权。服务端快照缓存（15–45s）并带 ETag；按 IP 限流（问答 6 次/分，超限 429 + `Retry-After`）；攻击者 IP 只出分段掩码，蜜罐凭据只保留结构与频次，自由文本统一过滤；「取不到 / 确实没有 / 未接入」三种措辞分开写，不补样例值。
- **技术栈**：Spring Boot Controller + 内存快照 + 令牌桶限流 + 后端脱敏过滤层；CORS 白名单只放 `x-user-token` 一个头（登录态才发，用于站主自己跳过限流）。
- **地址**：`https://demo.xiaokeqing.cn/api/public/*`（可直接 curl，只读）· 文章：[《公开接口防刷：限流、令牌与「我自己不限次」》](/posts/public-api-rate-limit-owner-token/)
- **我负责**：端点与脱敏层、限流与额度池的接线。

## ④ 内网靶场（Pikachu）

- **是什么**：把 Pikachu（PHP + MySQL 漏洞练习平台）容器化，放进 srv2 的内网网段 `labnet` 并**禁止出网**，主控前置一支口令门禁服务，入口页是本站 [/test/](https://xiaokeqing.cn/test/)。按仓库 2026-10-17 文档：DNS 未加、nginx 门禁未生效，**当前不对外开放** —— 所以这里不写「在线靶场」。
- **技术栈**：Docker（Pikachu 单镜像，常驻约 300–500 MB）/ 内网网段隔离 / 口令门禁（已写好，未上线）。
- **地址**：待补（无公网地址）
- **我负责**：容器化与内网隔离、门禁服务接线（上线前不宣称可用）。

## ⑤ AI 问答层（RAG）

- **是什么**：[/ai/](https://xiaokeqing.cn/ai/) 调 `POST /api/public/ask`。检索走 **BM25 稀疏 + 稠密向量双路召回 → RRF 融合（k=60）→ 轻量 IDF 重排**（纯 CPU，不引 Cross-Encoder，因为 2C2G 的小机装不下）；`top-k=3`、`min-score=0.30`、分块 `max-size=800 / overlap=100`。答案带 `citations` 可回源；检索不到走拒答并在正文写明没有依据；`PromptInjectionGuard` 命中会在应答里标注；公开面 `toolExecutionAllowed=false` 恒真，只解释、不取证。
- **技术栈**：Spring Boot + DashScope `text-embedding-v4`（1024 维）+ DeepSeek chat + 内存向量库；检索评测集 28 题，消融口径 28/28、MRR 0.9821（来源：`docs/后端问答能力升级方案-20261015.md` §2.4）。
- **地址**：[/ai/](https://xiaokeqing.cn/ai/) · 文章：[《为什么公开问答只解释、不取证：两层防御怎么做》](/posts/public-ask-explain-not-forensics/)
- **我负责**：检索链路、引用与拒答判定、注入护栏接线与评测。
