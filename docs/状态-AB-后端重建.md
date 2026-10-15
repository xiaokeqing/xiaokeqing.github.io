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
