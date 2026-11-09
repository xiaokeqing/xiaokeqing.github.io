# 状态 · K 模型取证（2026-10-15）

> 本文件是**进度/状态**文档；完整取证过程与原始命令输出见
> [后端问答模型取证-20261015.md](后端问答模型取证-20261015.md)。

## 一句话结论

`POST /api/public/ask` 的答案由**阿里云 DashScope（百炼）的 `qwen-plus`** 远端生成，
`temperature=0.0`、`topP=0.1`、`max_tokens=800`、单次调用硬超时 **15 s**；
**没有任何本地推理**，而且这台机器（1.87 GB 内存 / 2 vCPU / 无 GPU）**也跑不了**可用的本地模型。

## 状态看板

| 项 | 状态 | 说明 |
|---|---|---|
| 容器与 jar 定位 | ✅ 已查清 | 容器 `secagent`（`127.0.0.1:9900`），运行 `/app/app.jar`，md5 `ac7e643e…` |
| 部署提交 | ✅ 已钉死 | `git.commit.id=da9d1dba…`（`da9d1db`），与权威源码 `F:\7AAA\AI\SecAgent\sec-agent` 的 HEAD 一致 |
| yml 与源码一致性 | ✅ 已交叉验证 | jar 内 `application.yml` 去 CRLF 后 md5 `80dc548d…` == 仓库同文件 md5 |
| 供应商 / 模型 | ✅ 已查清 | `dashscope` / `qwen-plus`（启动自检 + yml + 代码常量链三重印证） |
| 生成参数 | ✅ 已查清 | temp 0.0 / topP 0.1 / max_tokens 800 / 硬超时 15 s / 冷却 60 s |
| 本地推理 | ✅ 已排除 | 无 ollama/vLLM/llama.cpp、无权重文件、无 GPU；内存也不够 |
| 备用供应商 | ✅ 已知 | DeepSeek 实现与配置齐全，但 `DEEPSEEK_API_KEY` 未配置；回退**默认关闭** |
| 多轮对话 | ✅ 已确认无 | 公开请求体只认 `question`/`q`，编排层收到 `List.of()` 空历史 |
| 工具调用 | ✅ 已确认禁止 | 响应恒为 `toolExecutionAllowed=false`；公开身份 RESPONDER 只解释、不调工具 |
| 出网延迟 | ✅ 已实测 | DashScope 首字节 ~89 ms、DeepSeek ~99 ms；`api.openai.com` 不可达 |
| `qwen-plus` 具体快照版本 | ⏳ `[待核对]` | 配置只写别名；需百炼控制台或响应体 `model` 字段才能确认 |
| `8899` 端口的 python3 用途 | ⏳ `[待核对]` | 非推理进程，与本次主题无关 |
| 公开问答当日可用性 | ⚠️ 额度已用尽 | 公开池 `30/30`（`data/model-quota-public.json`），此刻提问只会得到 `model-failed` |

## 关键参数（速查）

```
provider   = dashscope（阿里云百炼）          接入域名 https://dashscope.aliyuncs.com
model      = qwen-plus                        （rag.model 同值）
temperature= 0.0        topP = 0.1            max_tokens = 800
硬超时     = 15000 ms（应用层）                冷却 = 60000 ms
SDK 超时   = 180000 ms（被上层 15 s 压制）     SDK 重试 = 3 次（2 s 起、×2、上限 10 s）
编排重试   = ANALYST 结论最多 2 次
出站       = connect 3 s / read 12 s / call 15 s；单依赖在飞 ≤2
RAG        = top-k 3 / min-score 0.30 / BM25 on / RRF k=60 / rerank on
embedding  = DashScope text-embedding-v4（1024 维）  向量库 = memory（data/vector-store.json）
公开问答   = 6 次/分/IP、同 IP 并发 1、问题 ≤600 字符、body ≤4000、总预算 20 s、日额度 30
```

## 评价（"这个脑子够不够用 + 最大短板"）

**够用，但是"体面够用"，不是"能打"。**
`qwen-plus` + `temperature=0` 在"基于检索片段做归纳、复述、按 schema 输出 JSON"这类任务上是够的 ——
公开问答的定位就是"讲解公开知识库"，不是做真实研判，实测生产日志里 ANALYST 结论**首次尝试即成功**。

**最大短板有两个，按严重度排序：**

1. **`max_tokens=800` 是硬天花板**（比模型短，比 temperature 更影响观感）。
   一旦回答要展开（多条引用 + 结论 + 防护建议），800 token 会在半句话上**截断**，
   而上层拿到的是"截断的 JSON/正文"，表现为 schema 校验失败 → 重试一次 → 仍失败 → 如实标 `model-failed`。
   也就是**"答案太长"会被系统表现成"模型不可用"**，这是最容易被误诊的短板。
2. **能力天花板低 + 无本地兜底 + 备用链路是空的**。
   `qwen-plus` 在推理深度、长证据链关联上明显弱于 `qwen-max`/`deepseek-chat`；
   而 `fallback-provider` 为空、`DEEPSEEK_API_KEY` 未配置 ⇒ 一旦 DashScope 抖动/限流，
   公开问答就是**硬失败**（fail-closed，虽然诚实，但访客看到的是"不可用"）。

（第三个可提的：公开池日额度只有 30，被刷爆即整日不可用；今天已经 `used=30`。）

## 若要升级成更强模型：需要动什么

**结论：改配置 + 重建容器，不需要改代码；产线动作必须由站主本人做（我只做只读取证）。**

### 路线 A：留在 DashScope，把模型换强（**改动最小，推荐先试**）

- 改什么：公开问答的对话模型名来自代码常量 `DashScopeChatModel.DEFAULT_MODEL_NAME`
  （`ChatService.createChatModel()` 里硬编码），**yml 里没有任何键能覆盖它**：
  `rag.model` 只被 `RagService` 读，而 `/api/public/ask` **不经过** `RagService` 的生成
  （它走 `MultiAgentCoordinatorImpl.runAnalystPublic()` → `llmProvider.generate()`）。
  ⇒ 想换成 `qwen-max` 需要**改一行 Java 并重新构建镜像**（或者先做一次"把模型名提成配置项"的小改造）。
  - 若要顺带调参：`app.llm.max-tokens` / `app.llm.temperature` / `app.llm.timeout-ms`
    在 yml 里是**字面值**（没有 `${ENV:...}` 占位符）。改 yml 字面值最直接；
    注入 `APP_LLM_MAX_TOKENS` 之类的环境变量也能被 Spring 松散绑定识别，但本项目习惯是显式占位符，
    且 compose 的 `environment` 段需显式透传 —— 走这条路请以"启动自检打印的生效值"为准。
- 要不要重启：**要**。这些配置在启动时注入，改完必须重建/重启容器（`docker compose up -d --build`）。
- 谁来做：**站主/运维**（涉及产线容器重建；且 qwen-max 单价更高，属成本决策）。
- 备注：`app.llm.*` 目前**不在** `SPRING_APPLICATION_JSON` 覆盖段里，所以走 `.env` + compose 透传是有效的；
  但 compose 的 `environment` 段必须显式透传新键（该项目的既有坑，见 yml 注释）。

### 路线 B：切到 DeepSeek（**开关已就绪，只差一把 Key**）

- 改什么：`.env` 里 `APP_LLM_PROVIDER=deepseek` + `DEEPSEEK_API_KEY=<真实值>`；
  模型名可选 `APP_LLM_DEEPSEEK_MODEL`（默认 `deepseek-chat`）。
- 要不要重启：**要**（重建容器，然后看启动日志的 `LLM-PROVIDER-SELFCHECK` 行核对是否真的切过去了 ——
  项目明确要求"不要只看配置文件"）。
- 谁来做：**站主本人**（Key 只从环境变量注入，绝不入库；且这会把外部文本送到另一家）。
- **硬约束：`DASHSCOPE_API_KEY` 不能撤** —— DeepSeek 没有 embedding API，
  向量检索仍走 DashScope `text-embedding-v4`；撤了 Key 检索会整体失效（引用为空）。
- 成本提醒：DeepSeek 按 token 计价更低，但两家输出风格不同，公开页面的 `generatedBy` 会如实改写。

### 路线 C：本地推理（**当前机器不可行**）

- 需要：≥16 GB 内存或带 GPU 的机型（现机 1.87 GB / 无 GPU），自建 Ollama/vLLM 后把
  `base-url` 指过去（DeepSeek 实现是 OpenAI 兼容手写客户端，改指向本地端点即可）。
- 代价：新增一个必须 7×24 存活的推理服务、模型权重与显存运维；qwen-plus 级别的质量需要 7B+ 且量化后仍吃 5 GB 以上内存。
- 结论：**不建议在这台 1.87 GB 的机器上做**；若要做，等于**换机 + 新增运维面**。

### 无论走哪条路，都建议同时处理

1. `app.llm.max-tokens` 从 800 提到 2000+（否则升级模型也改不了"半句话截断"的表现）。
2. 视情况设置 `app.llm.fallback-provider`（开启后会真的换一家并如实署名，也会**多花一次钱**）。
3. 复核 `app.quota.public-daily-limit`（现为 30）与 `app.public-api.ask.requests-per-minute`（现为 6）。
4. 升级后必须核对启动日志 `LLM-PROVIDER-SELFCHECK`（供应商/模型/Key SET|MISSING/生效超时）这一行。

## 遗留与风险

- ⚠️ **取证过程自身失误（已在正文档披露）**：一次白名单 `grep` 误把 `APP_TTS_API_KEY` 的**值**打进了工具输出
  （Fish Audio TTS 凭据，与 LLM 无关）。未写入任何文件，但建议**轮换该 Key**。
- ⚠️ 公开池当日 `used=30/30`：此刻 `/api/public/ask` 只会返回额度用尽，**不能用它做"模型是否可用"的探测**。
- `[待核对]` `qwen-plus` 的底层快照版本、`spring.ai.dashscope.retry` 是否真被触发。
- 本次全程只读：未改配置、未重启、未发真实提问、未消耗任何额度；服务器上未留脚本/临时文件。
