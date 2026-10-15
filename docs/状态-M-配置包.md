# 状态-M：T25 配置改动包（解开 `max_tokens` 天花板）

- 本条线：**只准备，不部署、不重启、不动线上、不 push、不读密钥**
- 主交付：`docs/T25-配置改动包-20261015.md`（精确清单 / 补丁 / 构建部署 / 回滚 / 验证 / 成本）
- 产物目录：`E:\DeepSeek1\work\_t25\`
- 部署基线：`F:\7AAA\AI\SecAgent\sec-agent` @ `da9d1db`（= 线上 jar 内 `git.commit.id`）
- 补丁所在分支：`t25-unlock-max-tokens`（本地提交 `3080943`，**未 push**）

---

## 一、一句话结论

要修的不是"模型不行"，而是**"答案太长被当成模型不可用"**（截断 → JSON schema 校验失败 →
重试仍失败 → 如实报 `model-failed`）。
这一刀**必须整批下**，而且 L 的方案里**漏了一环**：真正建 OkHttpClient 的是
`spring.ai.dashscope.chat.options.{read,call}-timeout`（现落回 12s/15s），
**不显式补到 20s，`app.llm.timeout-ms=20s` 就是名义值** —— 故障只会从"截断"平移成"超时"。

---

## 二、改了什么（源仓库 5 个文件）

| 文件 | 关键改动 |
|---|---|
| `src/main/resources/application.yml` | `max-tokens` 800→**2000**；`app.llm.timeout-ms` 15000→**20000**；**新增** `spring.ai.dashscope.chat.options` 的 connect/read/call = 3000/**20000**/**20000**；`max-question-chars` 600→**1200**；`deadline-ms` 20000→**25000**；`public-daily-limit` 30→**60** |
| `docker-compose.yml` | `SPRING_APPLICATION_JSON` 与透传行的公开池默认值 30→**60**（★**线上真正生效的是这一处**，优先级高于 jar 内 yml） |
| `.env.example` | 公开池生产值 30→**60** |
| `RUNBOOK.md` §6.7 | 三本账表格 / 覆盖方式 / **发布前回收清单** 的 30→**60** |
| `scripts/preflight-release.sh` | 公开池"生产值"判据 30→**60**（★不改 ⇒ 改完额度后发布前体检**永久 [阻塞]**，把发布门禁卡死） |

**没动**：`requests-per-minute=6`、`max-body-chars=4000`、`app.outbound.*` 统一矩阵、
`max-inflight-per-dependency=2`、`rag.model`（它不控制公开问答 ✗）、任何 Java 文件。

---

## 三、自证（都可复现）

```
$ git -C F:\7AAA\AI\SecAgent\sec-agent status --porcelain     → 空（工作区停在 da9d1db）
$ git apply --check E:\DeepSeek1\work\_t25\t25-unlock-max-tokens.diff   → 退出码 0
$ mvn -o -B test        → Tests run: 588, Failures: 0, Errors: 0, Skipped: 4 / BUILD SUCCESS
$ Select-String target\classes\application.yml -Pattern 'max-tokens'   → max-tokens: 2000（证明构建用了补丁版配置）
```

- 补丁（人读）：`E:\DeepSeek1\work\_t25\t25-unlock-max-tokens.diff`
- 补丁（可 `git am`）：`E:\DeepSeek1\work\_t25\t25-unlock-max-tokens.patch`
- 备选方案（不重建镜像的线上热配置）：`E:\DeepSeek1\work\_t25\path-b-hot-config.md`
- 验证步骤与判据：`E:\DeepSeek1\work\_t25\verify-long-answer.md`

---

## 四、跨线依赖 / 待站主决定

| 项 | 内容 | 状态 |
|---|---|---|
| 执行人 | 重建镜像、合并 `main` 并 push、改 srv1 的 `.env`/compose、换容器 —— **全部由站主/运维本人做** | ⏳ 待派 |
| 额度 | 公开池 30→60 站主已批准 ✓；但**每 IP 小额度（T25-b）未落地前，60 会让"单 IP 刷爆全局"更快发生** | ⏳ 需取舍 |
| 验证通道 | 公开池 30/30 今日已耗尽 ⇒ 今天只能走评测池（`/api/chat` + `APP_EVAL_TOKEN`，余 31 次）；全量评测仍需先提 `APP_QUOTA_EVAL_DAILY_LIMIT` | ⏳ |
| T25-b | "每 IP 小额度与全局日额度分开"含 Java 改动（有界内存计数 + 经 `EvalIdentity` 的 InheritableThreadLocal 把来源 IP 送到模型出口）⇒ 属另一批 | ⏳ 待拍 |
| T25-c（新增建议） | ① 启动自检多打一行 `max_tokens`（现在只能靠行为验证）；② 补"长文本 + 注入诱导"负向用例 | ⏳ 待拍 |

---

## 五、风险与纪律自检

- **成本**：`max_tokens` 是上限不是用量 ⇒ 没被截断的回答费用不变；
  极端上界（公开池 60 次调用全顶格）≈ **0.15 元/日 ≈ 4.5 元/月**（非思考模式，美元单价换算 `[待核对]`；
  若按思考模式计费则 ≈0.59 元/日）。来源：官方 qwen-plus 价格页 + `[待核对]` 标注，不猜数。
- **超时/并发**：编排池固定 4 线程（`OrchestrationService.java:66-67`）；入口 20s→25s ⇒ 单请求最长占用 +25%；
  最坏路径 3×20s=60s ≫ 25s ⇒ 入口 deadline 一定先到（**"放宽单次超时"并不能让重试变得可用**）。
- 全程**只读**线上（未 ssh 进服务器执行任何变更）、**未发任何请求**、**未消耗额度**、
  **未打印任何 token/密钥**；数字均来自既有取证/源码行号/官方价格页，未核实的一律 `[待核对]`。
- 只 `git add` 了本条线的两个文档（`docs/T25-配置改动包-20261015.md`、`docs/状态-M-配置包.md`），
  并用 `Get-Item` + `git status --short` 自证存在。

> 附：建议追加进 `docs/项目总体规划-MasterPlan-20261015.md` §11 的那一行，见主文档 §10（**不由本包代写** —— 活文档归规划侧）。
