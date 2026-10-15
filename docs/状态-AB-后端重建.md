# 状态 · AB 批（后端一次重建：T25 + T14 + U6）· 2026-10-16

> 一行一条，**结论 + 证据**。执行记录（长文、含四行自检原文与 V1~V4 原始数字）见
> `docs/后端重建执行记录-20261016.md`。改的是后端，**旧文档一个字没改** ✗（站主自己维护）。

---

## 0. 一页状态

| 项 | 状态 | 证据 |
|---|---|---|
| T25 A 组（max_tokens 2000 / timeout 20s / dashscope chat read+call 20s / 入口 1200 字·25s） | ✅ 已上线 | 提交 `29b136a`；`outbound` 自检 `dashscope-chat{read=20000ms,callTimeout=20000ms}` |
| T25 §12（人格采样 0.8/0.8 + top_p 进请求体 + 决策链路保持 0.0 且不发 top_p） | ✅ 已上线 | 单测 2 条（人格必须写 `top_p`、决策必须不写）；`app.llm.persona.*` / `app.llm.top-p` |
| T25 B 组（公开池 30→60） | ⛔ **本批不做**（规划侧拍板暂缓，等 T25-b） | 4 个文件与 `da9d1db` 净差为 0；线上公开池 **30** |
| T14（情绪决策 JSON 契约 + 白名单校验防幻觉） | ✅ 已上线 | `decision=whitelist{actions=38,hostEntries=9,emotions=8,lines=12,md5=99850845}`；V1 白名单内率见执行记录 |
| U6（persona 摘要注入公开面 system prompt） | ✅ 已上线 | `persona=loaded(bytes=3565,md5=679cab35)` |
| U5（`/api/health` 收口） | 🟡 **部分**：删掉 `embeddedGitCommitMessage`（提交标题，零消费端） | `HealthControllerTest` 2 条；其余指纹字段因部署/回滚门禁依赖而保留，完整收口属独立批次 |
| T25-c（自检补打 max_tokens / 长文本负向用例） | ⛔ 未做（不属本批） | — |
| 测试 | ✅ 605 run / 0 fail / 0 error / 4 skip | 基线 588/0/4；新增 17 条 |
| 发布指针 | `d3f1eee` → `29b136a`（镜像 digest 见执行记录） | `/api/health` 的 `embeddedGitCommit` + `artifactMd5` + `fingerprintMismatch=false` |
| 回滚 | 三档均可用（镜像级已 `--dry-run` 实测） | 执行记录 §8 |

---

## 1. 本批新增的三个"可核对点"（部署后一眼看）

```
① LLM-PROVIDER-SELFCHECK provider=deepseek … decision=whitelist{actions=38,hostEntries=9,emotions=8,lines=12,md5=99850845} persona=loaded(bytes=3565,md5=679cab35)
② OUTBOUND-TIMEOUTS-SELFCHECK dashscope-chat{connect=3000ms,read=20000ms,callTimeout=20000ms,…}
③ GET /api/public/ask 的响应体多一个 data.decision（schemaVersion=xiaokeqing.kurisu.decision.v1）
```

## 2. 本批**没有**解决、需要下一批的一件事（重要）

- 线上 `provider=deepseek`，而 T25 A 组放宽的是 **DashScope** 的 OkHttp 超时（`spring.ai.dashscope.chat.options.*`）。
  DeepSeek 那条链路的超时来自 `app.llm.deepseek.* → app.outbound.*`，并被 `DeepSeekConfig` **钳死**
  在 `read=12s / call=15s`（只许收紧、不许放大）⇒ **`max_tokens` 放开后，长答案仍可能在 12s 读超时处被掐断**
  （自检行原文：`deepseek-chat{connect=3000ms,read=12000ms,callTimeout=15000ms,…}`）。
  ⇒ 建议列入 **T25-c/后续批**：要么放宽 `app.outbound.read/call`（会一并放宽 Wazuh/SSH/通知），
  要么把 `DeepSeekConfig.MAX_READ_MS/MAX_CALL_MS` 与新预算（入口 25s）对齐。**本批按改动包执行，未擅自改。**
- `/api/health` 的**完整**收口（U5）必须与 srv1/srv2 脚本契约同批，理由见执行记录 §9。

---

## 3. IP 回显收口（2026-10-16 01:25~01:40）—— 只读核实：**上一条执行线已经修好并且已经上线**

> 起因：站主/母 agent 实测 `/api/public/ask` 响应里出现过 `"clientIp":"47.96.106.187"`（**调用者本人**原始地址）
> + `ipDisclosure.masked=false` + `removalContact` 指向 `/about/`。要求**先只读核实再动手**。
> 结论：**一个字段都不用改**，上一条线已落地并上线（只是没留收尾消息）。另外顺带 grep 出**一处同类泄漏**（见下）。

| 项 | 状态 | 证据 |
|---|---|---|
| `/api/public/ask` 不再回显调用者原始 IP | ✅ **已上线**（**不是本轮改的**） | 响应 `data` 顶层 22 键里匹配 `/ip/i` 的只有 `clientIpMasked` / `ipDisclosure`；`has clientIp = False`；**整份响应体 dotted-quads = 0** |
| 镜像 = 发布指针 = 仓库 HEAD | ✅ 四者同一 commit | 镜像 label `revision=3476f86c68ddeda1fbf12a467b059e4b49d4bd33`＝本机 `git log -1`＝`origin/main`；01:30:12 那轮 timer `[OK] 当前运行 digest 与发布指针相同 —— 无需变更，安静退出` |
| `ipDisclosure.masked` | ✅ `true` | 线上原文 `{"masked": true, "notice": "观测到的来源地址，未经验证，仅供参考", "removalContact": "https://xiaokeqing.cn/"}`（`callerDisclosure()` **恒 true**） |
| `removalContact` 目标页 | ✅ **200** | 线上值 `https://xiaokeqing.cn/`；`curl -L` ⇒ `HTTP=200 redirects=0`（01:33 实测 `/about/` 此刻也是 200，但线上**不依赖它**） |
| 掩码形态唯一 | ✅ | 全站统一 `47.96.***.***` / `77.90.***.***`，**没有** `47.96.106.x` 与 `***.***` 并存 |
| 正常问答仍 200 | 🟡 **HTTP 200，但今天是"额度用尽"的显式回退** | `code=200`；`state=model-failed`、`failureReason=今日公开演示模型额度已用完`、`decision.rejectReason=QUOTA_EXHAUSTED`；公开池 `limit=30 / used=116`（**全局额度，我接手前就用光了，不是本次改动造成**） |
| `decision=whitelist{…}` 自检仍在 | ✅ 在 | 启动行原文 `decision=whitelist{actions=38,hostEntries=9,emotions=8,lines=12,md5=99850845} persona=loaded(bytes=3565,md5=679cab35)` |
| 顺带 grep 同类问题 | ⚠️ **找到 1 处**：`/api/public/alerts` 的 `title`/`ruleName` 里内网来源地址明文出网（同一条记录的 `srcIp` 已是「内网/未知」） | 执行记录 §13.4；**已修 + `mvn -o -B test` 610/0/0/4 全绿，但【没能上线】** |
| 本轮是否动线上 | ⛔ **一个容器都没动、没改 `.env`、没换镜像** | 全程只读；timer 那一轮自己 no-op |

### ⛔ 未完成项（如实写，不许硬撑）：同类泄漏的修复**没能上线**

- 阻塞点：**本机没有可用的 GitHub 推送凭据** —— 无 GitHub SSH key（`Permission denied (publickey)`）；
  `gh auth status` = `The token in default is invalid`；HTTPS push = `could not read Username`。
- 发布链是 `GitHub Actions → ACR:stable → srv1 timer`，**没有第二条路**（srv1 只读 ACR、连不上 GitHub）。
- ⇒ 改动只到 **本地分支 `fix/public-freetext-ip-gate`（commit `2bb2b2d`，基于 `3476f86`）**，
  **未合并回 main、未 push**；`main` 仍停在 `3476f86`、工作区干净。
- 恢复凭据后的动作：`git push origin fix/public-freetext-ip-gate:main` → 等 CI 出镜像
  → 停 `secagent-redeploy.timer` → `srv1-redeploy.sh --force` → 起 timer
  → 复核 `/api/public/alerts` 的 `internal_leaks=none`。
- 回滚：因为本轮没上线，线上回滚面**没有变化**；若修复上线后要退回，
  目标 digest/commit/md5 = `sha256:3999c905…` / `3476f86…` / `2711340b…`（执行记录 §13.6 有整条命令）。
