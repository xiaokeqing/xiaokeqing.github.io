# 状态-T：防复读（人格温度 / top_p / 历史层 / 台词库 / 复读率指标）——2026-10-15

- 本条线：**只出文档与改动包，不动代码 / 配置 / 容器** ✗
- 上游：`Code-Amadeus/Amadeus#227`（2026-10-15）—— 人格回复写死 `temperature=0.0` + 历史逐字全量回灌 ⇒ 口头禅自我强化成复读
  （硬证据：34 条消息的会话里用户只 2 次称"助手小姐"，角色却变体回敬 **8 次 / 17 轮 = 0.47**）
- 主交付（**4 份文档，全部追加式 / 新增，未改任何既有正文结论与数字**）：
  - ① `docs/T25-配置改动包-20261015.md` **§12 追加节**（人格/回答链路 `temperature` 与 `top_p` 可配 + 精确落点 + Java 改动 + 回滚 + 成本）
  - ② `docs/防复读实施件-20261015.md` **新增**（后端同类缺口只读体检：6 处缺口，逐条带文件 + 行号）
  - ③ `docs/台词库扩容-20261015.md` **新增**（前端台词库防复读：加权随机 + 短期不重复，含算法与参数）
  - ④ `docs/后端问答能力升级方案-20261015.md` **§10 追加节**（验收补一项"复读率"，三条指标 + 目标数字）
- 部署基线：`F:\7AAA\AI\SecAgent\sec-agent` @ **`da9d1dbaed054ad24c2b469cd09ca8695b6192d0`**（= 线上 jar 内 `git.commit.id`，工作区干净 ✓）

---

## 一、一句话结论

上游的三条结论，我们这边**只对上了一条**：

| 上游结论 | 我们的情况 |
|---|---|
| ① 人格温度要可配（0.7~0.9），planner/决策保持 0.0 | **做不到"只改 yml"** ✗：`temperature` 是**一个键管两条链**（PLANNER 与人格回答共用 `application.yml:129`）⇒ **必须改 Java + 重建镜像** |
| ② DeepSeek 已弃用 penalty ⇒ 可用旋钮只有 `temperature` 与 `top_p` | **惩罚类我们本来 0 命中**（不需要加 ✓）；但 `top_p` **线上根本没有**（DeepSeek 请求体不写这个字段，`DeepSeekLlmProvider.java:335-350`）⇒ 实际只剩一个旋钮 |
| ③ 历史层需防护（30 轮逐字窗口会长期主导输出） | **公开面是真空白历史** ✓（`PublicAskService.java:176` 传 `List.of()`）⇒ 上游那条**在我们公开面不成立**；内部 `/api/chat` 有 **6 对窗口**但**无摘要/无去重**（潜在缺口） |

**成本影响 ≈ 0**：`temperature` / `top_p` 都不是预算，不改 token 上限与调用次数 ✓（二阶效应只有"输出长度方差变大"）。

---

## 二、只读核到的新事实（含一处**对既有文档的更正**）

1. **线上现在是 DeepSeek，且回退关闭**（今天 21:54 起的自检行）：
   `provider=deepseek fallback=DISABLED`、`deepseek{model=deepseek-chat,key=SET,available=true}`、跨供应商回退**关闭**（fail-closed）。
2. **更正**：既有文档里"`topP=0.1`"是 **DashScope 实现**的硬编码（`DashScopeLlmProvider.java:163`）；
   线上走 DeepSeek ⇒ **公开问答当前不发 `top_p`**（等价于服务端默认 1.0）。⇒ 想用 `top_p` 当旋钮，**得先把它加进请求体**。
3. **线上没有任何采样参数覆盖**：compose 的 `SPRING_APPLICATION_JSON` 里没有 `app.llm.*`，`.env` 里没有 temperature/top_p 类键
   ⇒ 生效值全部来自 jar 内 yml。
4. **T25 尚未部署**（交叉验证）：线上 `APP_QUOTA_PUBLIC_DAILY_LIMIT=30`、出站 `read=12000ms / call=15000ms`（正文里要改成 60 / 20000）。
5. **"同一句重复"的现成审计不存在**：`response-audit.json`（46 条）与 `response-audit.eval.json`（7 条）只记**处置动作**，
   `access.jsonl`（2546 条）只记**请求元数据**；回答正文在**评测原始记录**里（`raw/qa-*.json` 的 `response.data.answer` + `ttsTextHash`）。

---

## 三、四条的落点（一句话各一条）

| 条 | 落点 | 一句话 |
|---|---|---|
| ① 参数可配 | `application.yml:129/130 附近`（新增 `app.llm.persona.temperature:0.8`、`persona.top-p:0.8`、`top-p:0.1`）＋ Java 5 处（`LlmProvider.java:46`、`DeepSeekLlmProvider.java:115-119/179/335-336/346-347`、`DashScopeLlmProvider.java:55-59/163`、`MultiAgentCoordinatorImpl.java:700` 只改这一处调用、`DeepSeekLlmProviderTest.java:105`） | **改 Java ⇒ 重建镜像**；planner 的 `:345` **一个字不动** |
| ② 后端缺口 | 6 处（G1 温度不分链 / G2 无 `top_p` / G3 DashScope topP 硬编码 / G4 其它链路硬编码 / G5 历史无摘要 / G6 无复读审计） | 最重是 **G1 + G2**；G5/G6 是"潜在 + 可绕过" |
| ③ 台词库防复读 | `static/js/kurisu-player.js`（`:1411 playLine` 之前加选择器、`:2318` 写死的 `tab_return`）＋ `layouts/index.html:1374/1410/1421` ＋ `shell-script.html:552/571`（**后两个文件工作区有未提交改动：-65/-4 行；行号=工作区口径，执行按锚点定位，对照表见《台词库扩容》§二**） | **"永远同一条"现在只发生在 greeting 与 idle_banter**；status/event/fallback 还没接线 ⇒ 规则必须**与接线同批**上 |
| ④ 复读率指标 | `后端问答能力升级方案` §10：`openerRepeatRate@3 ≤0.25 且降 ≥50%`、`verbatimRepeatRate ≤0.10`、`catchphraseTop1Share ≤0.15`；红线：要点命中率不得下降 | 载体是**已有**的评测原始记录；**硬前置是先补 3~5 条多轮题**（T13 现有 40 条没有多轮题 ✗） |

---

## 四、跨线依赖 / 待站主决定

| 项 | 内容 | 状态 |
|---|---|---|
| 执行人 | 合并 Java 改动、重建镜像、热调 `persona.*`、改 srv1 —— **全部由站主/运维本人做** | ⏳ 待派 |
| 取值拍板 | `persona.temperature` 默认 **0.8**（区间 0.7~0.9）与 `persona.top-p` 默认 **0.8** 是否照此定稿 | ⏳ 待拍 |
| 多轮题 | 复读率指标**必须先补 3~5 条多轮题**（现有 40 条没有多轮题），否则指标测不了 | ⏳ 待补 |
| 评测额度 | 改造前后各一次全量 = 两次额度；评测池 60/日，需分日或提额（同方案 §6.1） | ⏳ 待定 |
| 台词库扩库 | 60 句库已有 `ja`/`zh`，**TTS 合成**属另一条线；**入库前选择器必须先上** | ⏳ 待派 |
| `ChatService.java:81`（内部链路 0.7/0.9/2000）与 `ChatController.java:408-410`（ai_ops 0.3/0.9/8000） | 是否也一并做成可配（会牵动评测口径） | ⏳ 待拍（本批**刻意不动**） |

---

## 五、红线与纪律自检

- **未改线上任何配置**（`/opt/secagent/**` 一个字都没动）、**未重启/未重建容器**（只有 `docker ps / inspect / exec env / logs` 这类只读调用）。
- **未改源码仓库**：`F:\7AAA\AI\SecAgent\sec-agent` 仍停在 `da9d1db`，`git status --porcelain` 为空，**未 commit / 未 push / 未建分支**。
- **未消耗任何模型额度**：全程没有调用 `/api/public/ask` 或 `/api/chat`。
- **未打印任何密钥 / Token**：`.env` 只列**键名**、容器 env **过滤 key/token/secret/password** 后才显示、`data/` 只读字段名与条数。
- **文档纪律**：只**追加章节**（T25 §12、方案 §10）与**新增文档**（防复读实施件、台词库扩容、本状态）；
  别人正文的结论与数字**一个字未改** ✗；未核实的一律写 `[待核对]` / "待建立"，不猜数。
- **git**：只 `git add` 本条线的路径，**不 commit、不 push**；用 `Get-Item` + `git status --short` 自证（见 §六）。

---

## 六、交付自证（`Get-Item`）

```
PS> Get-Item -LiteralPath 'F:\7AAA\AI\blog\docs\T25-配置改动包-20261015.md',
      'F:\7AAA\AI\blog\docs\防复读实施件-20261015.md',
      'F:\7AAA\AI\blog\docs\台词库扩容-20261015.md',
      'F:\7AAA\AI\blog\docs\后端问答能力升级方案-20261015.md',
      'F:\7AAA\AI\blog\docs\状态-T-防复读.md' | Select-Object Length,LastWriteTime,FullName
（实测输出见本窗口回报；`git -c core.quotepath=false diff --cached --name-only` 只应列出这 5 个路径）
```

---

## 七、建议追加进活文档 §11 的一行

`docs/项目总体规划-MasterPlan-20261015.md` §11 是 append-only 变更日志。建议追加：

```
| 10-15 | T｜防复读 | 把上游 `Amadeus#227`（人格温度写死 0.0 + 历史逐字回灌 ⇒ 口头禅复读 8/17）落成可执行改动包（**只出文档，不部署**）：
① T25 追加 §12 定出"人格/回答链路 temperature+top_p 可配"的精确落点（`application.yml:129/130` 附近新增 `app.llm.persona.temperature:0.8` / `persona.top-p:0.8` / `top-p:0.1`，
**须改 Java 5 处 + 重建镜像**，planner 的 `MultiAgentCoordinatorImpl.java:345` 保持 0.0/低 topP 不许一起放开；**成本 ≈ 0**）；
② 只读体检出 6 处同类缺口（最重：G1 温度不分链、G2 线上 DeepSeek 请求体**没有 top_p**；G5 历史无摘要、G6 无复读审计；惩罚类旋钮本来 0 命中、不需要加）；
③ 台词库防复读：`greeting`/`idle_banter` 现在**写死单条**，落 `static/js/kurisu-player.js:1411`(+选择器)/`:2318` + `layouts/index.html:1374/1410/1421`，算法=**语义筛子集 → 排除最近 N=4 条 → 按 1/(1+近20次次数) 加权随机**；
④ 升级方案追加 §10 复读率指标（`openerRepeatRate@3 ≤0.25 且降≥50%`、`verbatim ≤0.10`、`口头禅占比 ≤0.15`，红线=要点命中率不降；**前置=先补 3~5 条多轮题**）｜
`docs/T25-配置改动包-20261015.md §12`、`docs/防复读实施件-20261015.md`、`docs/台词库扩容-20261015.md`、`docs/后端问答能力升级方案-20261015.md §10`、`docs/状态-T-防复读.md` | 后端/前端：**待站主拍板取值后执行**，本线零线上动作 |
```
