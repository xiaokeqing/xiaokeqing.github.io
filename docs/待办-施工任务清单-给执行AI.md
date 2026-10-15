# 施工任务清单 · 给执行 AI（2026-10-15）

> **本文用途**：把"还只在对话里、没进文档"的东西**全部落纸**。执行方按编号取任务，**每条都可独立验收、可独立回滚**。
> **规格与背景**：`docs/接线方案-动画与语音接入六页.md`（施工规格）、`docs/服务器配置-详细版-给外部AI.md`（基础设施）、
> `docs/HANDOVER-接手手册-给下一个AI.md`（入口）。
> **工作量**：T1–T4 约 1 天；T5–T8 约 1–1.5 天；T9–T13 按需。
> **标注**：`[已实测]` 有命令输出/截图支撑 ｜ `[契约]` 不许改 ｜ `[风险]` ｜ `[已纠正]` 我先前写错、以本文为准

**状态说明（2026-10-15 整理）**：**任务状态一律以 §A 总表为准** ✓；文末「附录·历史」是按时间追加的原始块，**只存档、不再维护** ✗。
数字（体积/字节/额度）一律以 `docs/总账-决策与事实台账-20261015.md` §2 为真源，本文**不再复述** ✗。

---

## §A 任务总表（唯一权威）

> 覆盖目前所有任务（T1~T30 中真实存在的编号 + 执行批的 L1）。**状态以本表为准**；文末「附录·历史」只存档、不再维护。
> `[待核对]` = **我无法从现有文档确证**该状态 ⇒ 写「见附录·历史」，**不猜** ✗（不编状态、不编提交号）。

| 编号 | 任务 | 归属窗口 | 状态 | 前置 | 证据（提交号 / 文件路径） |
|---|---|---|---|---|---|
| T1 | 手机打开时动画不放（`r.height<260` 死阈值 + 触屏判据） | 执行批（规划侧派工） | ✅ 已完成·已上线 | — | 提交 `229e0d7`；发布 `site-20261015-181533`；§1 派工单 |
| T2 | 文档修正 7 处（契约 / 13 个 once_then_hold / 10-38 / opening 占首屏 / PR-3 / `/opt/secagent/site` / 备案硬前提） | 执行批 | ✅ 已完成 | — | 提交 `5c443dc`；本文 §2 逐条 |
| T3 | 「会对话」接线（`/ai/` 真调 `POST /api/public/ask`） | 接手批 | ✅ 已完成·已上线 | — | 提交 `9e8094e`；发布 `site-20261015-181533`；§3 派工单 |
| T4 | 语音 L1 接线 + 换日语素材（12 句） | 窗口 A 复核 / 窗口 B 重生成 | ✅ 已完成·已入库 | T3 播放链 | 提交 `3ef5790`（sha256 12/12 与 `out-ja\dist` 一致）；提交 `36b361e`（v3 重跑版）；`static/kurisu/voice/` + `bank.json` |
| T5.1 | 五页 TypeError（`#fallback` 空值保护） | 执行批 | ✅ 已完成 | — | `shell-script.html` 空值判断；六页 console=0 |
| T5.2 | 门禁补硬断言（console error → exit 1 + 故障注入验证） | 执行批 | ✅ 已完成 | — | 提交 `8f33aa6` |
| T5.3 | `/about/` 空白 → 四张真实内容卡 | 执行批 | ⛔ 已作废（superseded） | — | 曾完成于 `8f33aa6`；**站主 2026-10-15 决定删掉 `/about/` 页** ⇒ 内容改作知识库条目（并入 T30）；见附录·历史 |
| T5.4 | 主页残留假数字 `1,284` → 占位 `—` + api-bind 填真值 | 执行批 | ✅ 已完成 | — | 提交 `6b35e89` |
| T5.5 | `/posts/` 卡片 → 真文章链接 | 执行批 | ✅ 已完成 | — | 提交 `6b35e89` |
| T5.6 | boot→hi 两段式（首屏 −47%） | 执行批 | ✅ 已完成·已上线 | — | 提交 `d8e03e6`；发布 `site-20261015-181533` |
| T6 | 状态机生成器补 `thinking_trans`（改从 `prob=0` 边派生） | 接手批 | ✅ 已完成 | — | 提交 `9e8094e`；`static/kurisu/statemachine.json` + `docs/amadeus-research/data/statemachine.json` |
| T7 | 视频接线（透明 VP9+alpha 40 组替代图集） | 窗口 C | ✅ 已完成·已上线 | — | 提交 `fc79d0c`；发布 `site-20261015-210145`；`_shots/t7-evidence.md` |
| T8 | 状态机 + 口型接线（最难） | 窗口 C | 🟡 进行中 | T7 已完成 ✓ | 见附录·历史（截至 §A 整理无完成提交）；口径 U8（`opaque_bbox` 不可用）、S1（嘴部锚点参考） |
| T9 | 资产瘦身（删 medium/hi） | 窗口 C | ⏸ 排队 | **必须 T7/T8 之后** ✗（顺序不能反） | 见附录·历史；§9 派工单 |
| T10 | 遗留文件与双轨架构清理 | 窗口 C | ⏸ 排队 | 可随时 | 见附录·历史；§10 派工单（`static/preview-shell.html` 等） |
| T11 | 服务器与运维（证书告警 / 可用性探测 / 配置备份 / 备案材料） | 窗口 H | ✅ 已完成（备案**实际提交**仍待站主） | — | 提交 `1f418ae`；`docs/运维-T11-*.md` ×3 |
| T12 | 删背景选择器 + 配色面板（并做 T5.6） | 执行批 | ✅ 已完成·已上线 | — | 提交 `d8e03e6` |
| T13 | 评测包（ASR 回译 CER + 问答质量集 + MOS/ABX 流程 + `scripts/eval/`） | 窗口 A | 🟡 进行中：①②③ 已交付；MOS 待人工盲听、得分表待续跑 | — | 提交 `033c75b`；`docs/评测报告-语音与问答-20261015.md`；`scripts/eval/` |
| T14 | LLM 决策行为（告警 → 严格 JSON，白名单校验防幻觉） | 窗口 C | ⏸ 排队 | T8 完成 | 见附录·历史；§17 任务表 |
| T15 | 语音闭环（ASR → LLM → TTS + 打断） | 待开窗口 | ⏸ 排队 | T14 + TTS 通路 | 见附录·历史；§17 任务表 |
| T16 | 《AI 项目说明书》 | 窗口 E | ✅ 已完成 | T13 出数字后 | `docs/AI项目说明书-安全数字人-20261015.md` |
| T17 | 声音模型换代 A/B（v3 / v2Pro / v2ProPlus） | 窗口 B | ✅ 已完成·已定稿（**保留 v3 重跑版 12 句、不换模型**；v2ProPlus 本机 0 权重未测 `[待核对]`） | — | 提交 `36b361e`；`docs/声音模型A-B报告-20261015.md`；`docs/状态-B-声音.md`；附录·历史末块（三条决定） |
| T18 | 素材产线能力建设（SpriteForge + Wan：能生成 → 能对齐 → 能入库） | 窗口 D（段三归窗口 C） | 🟡 段一/段二已完成；**段三（注册进 statemachine）未做** ⇒ 归 C | — | 提交 `7538904`；`docs/素材产线能力-T18-20261015.md` |
| T19 | 双智能体协作方案（三层 + persona.md + 端点契约） | 窗口 E | ✅ 已完成（**提议层暂不做**，先只做决策层） | — | `docs/双智能体协作规格-20261015.md`、`docs/persona.md` |
| T20 | 处置成果「封禁榜」上屏 | C 落地 + G 出 UI | ⏸ 排队 | 等 G 的设计稿 | 见附录·历史；§19 要点（IP 掩码：总账 §1 D9 口径、§6 ⑨） |
| T21 | 攻击故事线上屏 | C + G | ⏸ 排队 | 等 G 的设计稿；吸收 `/labs/` 的「攻击复盘台」 | 见附录·历史；§19 要点 |
| T22 | 知识库栏目上屏 | C + G | ⏸ 排队 | 等 G 的设计稿 | 见附录·历史；§19 要点 |
| T23 | SpriteForge 试点可行性（最小示例纯 CPU 跑通） | 窗口 D | ✅ 可行性已确认 | — | 提交 `7538904`；附录·历史 D 块（生成那半是远端付费服务） |
| T24 | E-mote 路线评估（含授权结论） | 窗口 I | ✅ 评估已完成（结论：**不公开上线** ✗） | — | `docs/E-mote路线评估-20261015.md`；MasterPlan §6 ⑩ |
| T25 | 后端配置包（max_tokens / 超时 / 入口上限；**走路径 A 重建镜像**） | 窗口 M（后端线） | 🟡 已准备未部署；规划侧已拍板**只上 A 组，B 组（额度 30→60）暂缓** | 需站主/运维动手；B 组等 T25-b | `docs/T25-配置改动包-20261015.md`；本地分支 `t25-unlock-max-tokens`（`3080943`，**未 push**） |
| T25-b | 新增 `app.quota.public-per-ip-daily-limit`（每 IP 日额度） | 后端线 | ⏸ 排队 | 与 B 组**同批上** | 见附录·历史（T25 拍板②） |
| T25-c | 启动自检补打 `max_tokens` 行 + 长文本/注入负向用例 | 后端线 | 🟡 已批准（待执行） | — | 见附录·历史（T25 拍板③） |
| T26-a | 含「牧瀬紅莉栖」的台词：**送 TTS 的文本**改写假名（显示文本/字幕一字不改） | 窗口 B | ✅ 已验证并落地 | — | 提交 `36b361e`（`ttsJa`=牧瀬クリス）；`docs/发音判断-牧瀬紅莉栖-20261015.md` |
| T26-b | 根治：`ja_userdic/userdict.csv` 加人名读音 | 声音线 | ⏸ 排队；`[待核对]` 列格式未核对 | T26-a 已兜底 ✓ | 见附录·历史（J 的结论）；文件在 `_amadeus-src`（仓库外） |
| T27 | 删 `/labs/` 靶场页 + 导航改项 + 三门禁页数 + sitemap/链接清理（**已扩展为同时删 `/about/`**） | 窗口 C | ⏸ 排队（站主已决定；等排期） | 排在 **T8 第一批之后** | 见附录·历史；§19 末尾两节 |
| T28 | 全站收掉旧 SPA 的问答输入条（AI 问答只留 `/ai/`） | 窗口 C | ⏸ 排队 | 排在 **T8 第一批之后** | 见附录·历史；§19「站长的两条减法决定」 |
| T29 | 只读工具调用（8 端点白名单 + 每会话 3 次 + 复用既有审计） | 后端线 | ⏸ 排队 | 排在「解上限」之后 | `docs/问答升级-顺序纠正与知识库内容规划-20261015.md`；`docs/项目精简与冗余审计-20261015.md` §A |
| T30 | 知识库内容建设（首版 15~25 条 + FAQ 沉淀机制；入库前人工审） | 内容 / 后端线 | ⏸ 排队 | 须先补基线（U9） | `docs/问答升级-顺序纠正与知识库内容规划-20261015.md`；`docs/项目精简与冗余审计-20261015.md` §A |
| L1 | 镜头语言（CRT 通电 + opening→idle 推拉） | 执行批 | ✅ 已完成 | — | 提交 `4c6140c` |

**编号核对**：T1~T30 中**真实存在**的是上表全部（含 T25-b / T25-c）✓；**未发现 T26-c** ✗（T26 只有 a/b 两条）。
**待核对项**（不猜 ✗）：T8 的当前完成度、T26-b 的列格式 —— 均以附录·历史为准，等对应窗口回填。

**当前需要站长拍板 / 动手的（从附录·历史归拢）**：
1. **U1 红线冲突**：后端全局 `app.public.mask-ips`（生产默认 false）；站主已裁定**不翻转**，「保留前三段、最后一段换 x」只在前端显示层做 ✓（口径见总账 §1 D9、§6 ⑨）—— 落地归窗口 C（T20/T21）。
2. **T25 B 组（公开额度 30→60）**：暂缓，等 T25-b 每 IP 日额度**同批上** ✓。
3. **T24 / E-mote**：结论已出（不公开上线 ✗）；「本机留档看一眼」= 可选项（不发布）。
4. **L2「念回答」**：Fish Audio Key 站主决定**暂不轮换** ✓；一旦 L2 上线必须换新，且 TTS 代理白名单 + 限流 + 月硬顶须先就位。
5. **T27/T28 + 删 `/about/`**：站主已决定 ✓，等窗口 C 排期（排在 T8 第一批之后）。
6. **问题单**：U7（decide/ask 的 token 上限与费用实测）、U9（知识库缺基线）、U10（`data/kb-approved` 目录不存在）—— 详见附录·历史末段。
7. **发布条件**：`gate-firstscreen` 现因窗口 C 未提交的 `__xkSM.reasons` 改动而 FAILED ⇒ **门禁不齐 = 当前不具备发布条件**；线上仍是 `site-20261015-210145`。

---

## 0. 硬前提（先读这 6 条，否则白干）

```
① **未备案 = 不能直连**：腾讯云对未备案域名的 80/443 做阻断 —— 铁证：
   `curl -H 'Host: xiaokeqing.cn' http://43.143.114.79/` → `302 Location: https://dnspod.qcloud.com/static/webblock.html?d=xiaokeqing.cn`
   443 直接 reset（浏览器显示"连接被重置"）✗ `[已实测]`
   ⇒ **今天所有"连接被重置/超时"的真因就是这条**；我先前写的"本地 SNI 过滤"是误判 ✗ `[已纠正]`
② 当前对外路径（2026-10-15 起）：CF 边缘 → **隧道 `secagent-static`（出站）** → srv2 `127.0.0.1:18080` → `/opt/secagent/site`
   · DNS：`xiaokeqing.cn` 与 `www` 已从 A 记录改为 **Tunnel `secagent-static`** ✓（`direct.*` 仍保留 A 43.143.114.79 / DNS only ✓）
   · 四条隧道路由的 Service 均为 `http://127.0.0.1:18080` ✓ `[已实测]`
   · **`static.xiaokeqing.cn` 只服务 `/opt/secagent/static`（248 B 占位页）** ✗ —— 它**不是主站备份**，别拿它当备份用 `[已纠正]`
③ **push ≠ 上线** ✗：push 只更新 gh-pages；上线必须再跑 `scripts/publish-site-to-srv2.ps1`（srv2 原子切换）
④ **六页是生成器产物** ✗：改 `layouts/*` 必须同步 `_dev/gen-demo-pages.py`，否则下次跑生成器会覆盖（`_dev/` 已在 .gitignore 白名单里 ✓）
⑤ 本机直连线上会被①阻断 ✗ ⇒ 线上核验走 `ssh secagent-srv1`（从服务器侧 curl）或 CF 路径
⑥ 三道门禁：`bash scripts/assert-build.sh ./public`（**16 项** `[已实测]`）｜`node _dev/gate-firstscreen.mjs`（6 页 ≤1650KB）｜
   `python _dev/check-ssr-contract.py public`（6/6）
```

---

## 1. T1（P0）手机打开时"她"的动画不放出来

**现象** `[已实测：站长手机]`：整站约 10 秒加载完、能打开，但**进页面后 canvas 不播**（静帧/空）。

**首要怀疑（先证伪）**：原型写死降级阈值 ——
```js
// layouts/partials/xk-demo/shell-script.html:512（五页共用；主页别处也有同款逻辑）
document.getElementById('fallback').style.display = r.height < 260 ? 'grid' : 'none';
```
手机上 CRT 显示高度很可能 <260px ⇒ 直接切 fallback 静帧 ⇒ 动画永不播 ✓（`#fallback` 只在主页存在 ⇒ 五页还会抛 TypeError ✗）

**做法**
```
1. 先确证：手机横屏 / DevTools iPhone 尺寸（1242×2688）复现，检查 #fallback 是否显示、canvas 是否有内容
2. 若是阈值：把判据从"CRT 高度 <260px"改成基于可视宽度/DPR 的合适判据，或"小屏也播动画、只是更小"（只改判据 ✗ 不改视觉）
3. 若确为加载慢：接 T5 的 boot→hi 两段式（opening.boot.webp 281,664 B 先顶上）
4. 同批修五页 TypeError：const fb = document.getElementById('fallback'); if (fb) fb.style.display = ...
```
**验收**：真机竖屏 30 秒内画布出现 ≥2 种不同帧（截图/录屏）｜五页控制台 0 报错｜三道门禁绿｜非角色区像素差 0
**工时/风险**：1~2h ｜ 低

---

## 2. T2（P0）文档修正：7 处，逐条给出"改成什么"

> 这些都是**我写错或漏写**的地方 ✗（其中 6 处由接手方 AI 实测发现、我已复现确认 ✓）。执行方改完请把改动贴回来。

| # | 文件 | 原文/问题 | 改成 |
|---|---|---|---|
| 2.1 | `docs/接线方案-动画与语音接入六页.md` §3.1 | 写 `"nodes": { "<clipName>": {...} }`（对象）、节点有 `geometry`、边只有 `{from,to,prob}` | **nodes 是数组**（38 元素，元素含 `id`（如 `_8ms718k`）+ `clip`（如 `idle`））；节点真实字段：`atlas_source/clip/fps/frameIntervalMs/frame_size/frames/has_mouth_profile/hi/id/incoming_prob_positive/is_root/loopMode/medium/mouthPatch/opaque_bbox/phase/tier`（**无 geometry**）；几何在 `frame_size:[764,1028]` + `medium.pages[]`/`hi.pages[]`（含 url/file/tile_w/h/cols/rows/frames/first_frame/last_frame/pixels/bytes）；边是 `{from, from_id, prob, to, to_id}`（**节点 id ≠ 剪辑名，缺 from_id/to_id 无法跳转**） |
| 2.2 | 同上 §3.1 | 写"12 个剪辑是 once_then_hold" | **13 个**（`loop_mode_counts = {loop: 27, once_then_hold: 13}` `[已实测]`） |
| 2.3 | 同上 §3.1（漏写） | 未提顶层两个字段 | 补：`host_triggered_entries`（**8 个剪辑名**）与 `clips_not_in_graph: ["sad","smile"]`；并注明 `prob=0` 边目标实际 **9 个** ⇒ 清单缺 `thinking_trans`（见 T6） |
| 2.4 | 同上 §1 验收②/§4.3 | 写"纯概率游走只覆盖 9/38" | **10/38**（idle 家族 9 + `trans_standby`）`[已实测]`；反例判据同步改为 10/38 |
| 2.5 | 同上 §6 首屏预算 | 写"接线后首屏 ≤700KB"，未算 opening | 补：**首屏大头是 `opening.hi.webp`（1,004 KB，占当前 1569KB 的 65%）**，视频接线对首屏**零帮助** ✗；要降必须做 T5 的 boot→hi |
| 2.6 | 同上 §10 PR-3 | 写"替换原型那段 4 剪辑循环（保留它作为最终降级路径）" | 改写：原型 4 剪辑 = `opening/idle/speaking/thinking`，其中**只有 `idle` 在状态机且有视频** ✗；`opening/speaking/thinking` **既不在状态机、也无视频** ⇒ **不能整体替换**；必须先给出 `opening` 的处置（保留原型 opening 作为开场 ✓ 或另出视频） |
| 2.7 | `docs/服务器配置-详细版-给外部AI.md` §3.5 | 写"`/opt/secagent/static/` = 静态根（当前内容 = 站点产物）" | 改成：**`/opt/secagent/site` = 主站真身**（软链 → `releases/site-<时间戳>`，server_name = xiaokeqing.cn/www/direct）；**`/opt/secagent/static` = `static.xiaokeqing.cn` 的占位根（248 B），与主站无关** ✗；并补一句：`systemctl is-active nginx` 在 srv2 返回 `inactive` **是设计如此**（nginx 是 `secagent-static.service` 的主进程、以 `xksite` 身份跑）✗ 别误判为故障 |
| 2.8 | 同 §4 / `docs/ops-博客托管切换与回滚.md` / `docs/HANDOVER-§7§12` | 缺"备案=硬前提" | 三处都补：**未备案 ⇒ 境内 80/443 被阻断（含 §0① 的 302 铁证命令）**；**现行方案 = 走 CF 隧道**；备案完成后再把 apex 切回 A 记录（271~338 KB/s ✓） |

**验收**：改完 `grep` 一遍确保旧说法（`9/38`、`12 个 once_then_hold`、`geometry`、"本地 SNI 过滤"、"/opt/secagent/static = 站点产物"）在仓库里**不再出现** ✗；**数字单一来源**：数字一律以 `docs/总账-决策与事实台账-20261015.md` §2 为准，本文只引用不复述 ✗
**工时/风险**：30~40min ｜ 极低（纯文档）

---

## 3. T3（P1）"会对话"接线 —— 性价比最高

**事实** `[已实测]`：后端**已经跑在生产上**
```
POST https://demo.xiaokeqing.cn/api/public/ask  →  200 ✓
 返回：answer / state / stateLabel / generated / citations[] / quota{pool:"public-demo",limit:30,used,remaining} /
       note / retrievalNote / ttsTextHash / outputFindings / maxQuestionChars:600 / deadlineMs:20000
 口径：publicDemo=true、toolExecutionAllowed=false、fail-closed（检索不到就说"没有生成结论"，不编造）
 **CORS 已验证**：带 `Origin: https://xiaokeqing.cn` → 响应头 `access-control-allow-origin: https://xiaokeqing.cn` ✓（无跨域障碍 ✓）
 小 bug：`GET /api/public/ask` 返回 500（应 405）
```
**现成可复用**：`static/js/app.js` L1607-1914（发包+超时、契约注释、引用卡片渲染、输入框行为、预设问题、"不许 SSE/WebSocket"纪律）
**现状**：六页是 demo 整份搬、**不加载 app.js** ✗；`/ai/` 的 `askDemo()` 是假的（等 900ms 塞固定文案、不发请求 ✗ `[已实测]`）

**做法**
```
1. 把 /ai/ 页的 askDemo() 改为真调用（API base 已在 <meta name="wb-api"> 里 ✓）
2. 渲染 answer + citations[] + state/stateLabel + quota（照 app.js 的渲染逻辑，别引入新框架 ✗）
3. 用响应状态驱动她：THINKING → 回答 → IDLE（demo 已有 emo / mode / speak() 钩子 ✓）
4. 失败/无检索：显示"读不到 / 没有依据"，**前端不兜底造假** ✗（后端已 fail-closed）
5. 可选：把 answer 文本喂 `/api/public/tts`（响应里的 `ttsTextHash` 就是为这条链路设计的 ✓）—— 需在 T4 之后
```
**验收**：真实提问打通（截图为证）｜引用卡片与 quota 正确显示｜失败时显示"读不到"且控制台 0 报错｜首屏字节不超标
**回滚**：把 `askDemo()` 换回假实现（一行）✓ ｜ **工时/风险**：1~2h ｜ 低
**纪律**：不许 SSE/WebSocket ✗；不许前端编造答案 ✗

---

## 4. T4（P1）语音 L1 接线（她会开口）

**素材已就绪** `[已实测]`
```
E:\DeepSeek1\work\_tts-trial\sample8\dist\*.m4a|webm（8 句 / 529,864 B，覆盖 7 个 trigger，含 shy/surprised）
全量 60 句在 out-ja\dist\（3.13 MiB，超 3 MiB 预算 4.5% ✗ → 要全量就按 m4a 40k / webm 32k 压到 ≈2.6 MiB）
bank.json：out-ja\bank_sample8.json（含 ja/zh/envelope/durationMs/sha256/source ✓）
管线与复现命令：仓库 `scripts/voice/README.md`（含 7 条坑 ✓）
线上现状：那 12 句是 **Windows SAPI 占位音** ✗
```
**做法**
```
1. 只上 8~12 句，**按 7 个分组各取 1~2 条** ✗ 别随机取（否则触发规则形同虚设）
2. 放进 static/kurisu/voice/* + bank.json（契约兼容 ⇒ 播放器一行不用改 ✓）
3. 页面接线：autoplay 门控（手势前 0 播放、按钮"🔊 点我开声"）+ 字幕用 zh（写进原型已有字幕元素，不新增元素 ✗）
   + 包络（10ms 窗）暴露 mouthValue 给 T8；失败只落字幕 ✓
4. 语音目录预算 ≤3 MiB，首屏只预载 greeting 一句，其余 <audio preload="none">
```
**验收**：手势前 plays=0 / 手势后 plays≥1、字幕与音频对齐 <100ms｜`static/kurisu/voice/` ≤3MiB｜首屏不超标
**回滚**：删 manifest 的 voice 段（页面判定无 bank 就不初始化 ✓）｜ **工时/风险**：1~2h ｜ 低

---

## 5. T5（P1）界面清理 + 首屏 boot→hi（零风险、用户可见）

```
T5.1（A1）五页 TypeError：shell-script.html:512 → `const fb = document.getElementById('fallback'); if (fb) …`（1 行）
T5.2（A2）门禁补硬断言：把"控制台错误"从"只报不拦"改成**有错即 exit 1**（需给已知无害告警留白名单）；
          同时给首屏门禁补"状态机 reason 统计"断言（host:voice/emotion/idle 各 ≥1）
T5.3（A3）/about/ 空白那屏：属实（原型里 `v-about` 只有 87 字节的 `</div>` ✗ 当前产物正文 0 字）；
          按站点口径自己写一屏（真实数据，取不到写"读不到" ✗ 不许编）
T5.4（A4）主页静态残留假数字：`layouts/index.html:126` → `24h 告警 1,284 · 拦截 96` 改为占位 `—`，由 JS 填真值
T5.5（A5）/posts/ 卡片改成真链接（进具体文章）——注意单篇文章页仍是旧版式 ✓
T5.6（D1）★ boot→hi 两段式：原型脚本直接加载 hi ✗，仓库里现成的 boot 档完全没用（引用次数 0 `[已实测]`）：
          opening.boot.webp **281,664 B**（hi 1,004 KB）｜idle.boot 531,854 ｜speaking.boot 444,430 ｜thinking.boot 475,680
          做法：先画 boot 顶上 → hi 到位后替换 ⇒ 主页首屏 1569KB → **约 823KB（−47%）**，**最终画质不变** ✓
```
**验收**：五页 0 报错｜主页首屏 ≤900KB（门禁②）｜boot→hi 替换后与 hi 直出**同帧对拍像素差 0**｜其余页面字节不退化
**回滚**：boot→hi 是一段加载逻辑，删除即回到 hi 直出 ✓ ｜ **工时/风险**：T5.6 约 1h（要动 demo 内联脚本 ⇒ 属口径问题，见 §12 待拍板）；其余各 10~20min

---

## 6. T6（P2）状态机生成器：补 `host_triggered_entries` 的 `thinking_trans`

**实测** `[已实测]`：`prob=0` 的边目标是 **9 个**剪辑：
`angry_trans · closed_eye_trans · sad_trans · shy_trans · speaking_short · speaking_trans · surprise_trans · **thinking_trans** · trans_smile`
但顶层 `host_triggered_entries` **只有 8 个**，**缺 `thinking_trans`** ✗（它的 prob=0 入边来自 `idle_str_wind`）
⇒ 若执行方照这份清单实现宿主触发，`thinking_trans` **永远不会被触发**，状态机走进 `idle_str_wind` 后出不来（观感=发呆 ✗）

**做法**：修 `_dev/build_statemachine_manifest.py` 的清单生成（按"所有 prob=0 边的目标剪辑"取，别按别的口径 ✗），重新生成
`static/kurisu/statemachine.json` 与 `docs/amadeus-research/data/statemachine.json`（源），并核对 manifest/预载清单不受影响
**验收**：重新生成后 `host_triggered_entries` = **9 个**且包含 `thinking_trans`；38/88 不变；门禁绿
**工时/风险**：20~30min ｜ 低

---

## 7. T7（P2）视频接线（9.54 MB 替代 71 MB）

```
素材（已产出、自检 40/40 过）：E:\DeepSeek1\work\_kurisu-017\video-assets\video\<clip>.webm ×40（8,763,277 B）
                              + <clip>.poster.webp ×40（779,892 B）
路线：**B 路线（透明 VP9+alpha）** —— alpha MAE 0.189、体积小 23%、播放端直接 drawImage ✓（B3 只在颜色 PSNR 占优，且每帧多一次全帧合成 ✗）
做法：canvas 从"画 PNG 图集"改为"画 <video>"；离屏 <video>（不进 DOM ✗）；同时存活 ≤4 枚 + LRU；
      硬切用两枚 video 交替；缺视频/解码失败 → 图集 → poster；首帧先画 poster（不留空框 ✗）；
      **预载纪律**：只预载 root→idle→出边 top-2；首次手势前不预载视频 ✗；saveData/reduced-motion 只用 poster
坑（已踩）：只能 VP9+alpha（AV1+alpha Chromium 解不出透明 ✗）；WebM 无 faststart 但索引天生前置 ✓；
      色彩标记必须输入端也写；`clip.json` 的 `layout` 有 2 组写错（1027 vs 1028）⇒ 一律以实际码流尺寸为准；
      转码前必须 pad=764:1028:100:0:black，否则角色横向跳 9.5% ✗
```
**验收**：30 秒 ≥8 个不同帧指纹｜四角品红采样证明 alpha（已有方法 ✓）｜首屏仍 ≤1650KB｜与图集同帧 NCC ≥0.99
**回滚**：`data-xk-kurisu-mode="pixel"` 一行 ✓ ｜ **工时/风险**：2~3h ｜ 中

---

## 8. T8（P2）状态机 + 口型接线（最难）

```
状态机：38 节点/88 边；root=idle；出边概率**归一化后**掷骰子；`prob=0` 的 9 条=宿主触发入口（见 T6）；
      13 个 once_then_hold 播完停末帧；支持 ?seed=<n> 与 ?replay=<base64>；每次切换记 reason（auto:<edge> / host:<kind>）
宿主触发事件表：greeting（首访/回访分流）/ page_intro（每页一条，同页 10 分钟去重）/ status（**真实文本变化时**，20s 防抖）/
      event（新告警/故事线，按事件 id 去重，可打断 status）/ idle_banter（无操作 >90s）/ fallback（接口取不到）/
      emotion（点击她 / 严重度变化）/ cadence（>25s 无宿主事件兜底）
口型：mouthValue = clamp(envelope.values[floor(t/10ms)] × 3.75, 0, 1)；≤0.08 叠闭嘴层
      12 个剪辑用小补丁、4 个用原方案（截块+椭圆遮罩，按 mouthPatch.preferredVariant）；
      逐帧用 anchor_track 定位（**不许写死坐标** ✗）；说话段不叠（帧里自带嘴在动 ✗）
```
**验收**：30 秒内 reason 统计出现 host:voice / host:emotion / host:idle 各 ≥1（**反例：只有 10/38 的 idle 家族 = 接线失败** ✗）｜
静音/说话两张嘴部对照图｜页面隐藏 60s 后切回不快进（清零累加器 ✓）
**工时/风险**：状态机 3~5h（高）；口型 1~2h（中）

---

## 9. T9（P2）资产瘦身（**有前提，别乱删** ✗）

```
实测：static/kurisu 共 82,400,264 B（78.58 MiB）；六页实际只引用 23 个文件 ≈ 7,325 KB（7.15 MiB）
      ⇒ 约 68.8 MiB"部署了但拉不到"（medium/ 48.15 MiB + hi/ 19.62 MiB + voice/ + mouth/ + statemachine.json）
原因：六页不加载 kurisu-player ✗；状态机默认关（需挂载点带 data-xk-kurisu-sm="on"，产物里没有 ✗）
⚠️ **但文章页加载 kurisu-player（实测 1 处 + xk-kurisu 12 处）**，播放器**运行时**会取 `medium/*.atlas.webp`
   ⇒ **不能**先把 medium/ 移出 git ✗（会让文章页角色失效/降质）
做法（顺序不能反）：① 先接线（T7/T8）让视频替代 medium → ② 观察一段时间 → ③ 再删 medium 与 hi（保留 release 里的回退源 ✓）
门禁口径建议拆两个指标（现在的 ⑨ 是"仓库占用"口径，与"线上载荷"差约 10 倍 ✗）：
      repo ≤ N MiB（防 git 膨胀）｜ per-page payload ≤ M MiB（用户体感）｜ first-screen ≤ K MiB（已有 ✓）
发布包：现在每次 tar 81.86 MB（含未引用的 68.8 MiB）✗ → 瘦身后可降到 ~15 MB
```
**验收**：删前后文章页 + 六页的角色都正常（截图对拍）｜`assert-build.sh` 全绿（含我调整后的新口径）
**工时/风险**：瘦身 1h（但要等 T7/T8 完成）｜ 中（顺序错了会伤文章页）

---

## 10. T10（P3）遗留文件与双轨架构

```
E2 双轨：站点原 SPA（app.js + #xk-views + data-xk-ssr）与 demo 内联脚本（六页各自完整 HTML、不走 baseof.html）
        + baseof.html 仍在给文章页用、且加载 kurisu-player ⇒ **接线时先确认改动落在哪一轨** ✗
E3 遗留：static/preview-shell.html（71 KB）、layouts/partials/xk-views/v-home.html、assets/css/xk-app.css 等
        （上一版外壳，当前口径下不挂载）⇒ 确认后**归档或删除**
E4 文档漂移：`docs/交接-六页整份搬demo-20261014.md:114` 仍写旧断言 `.navpill`（导航已改成 dock ✗）
           · 注意：接手方 AI 报告"assert 实测 15 项"与本节不符 —— 我**连跑三次都是 16 项** `[已实测]`，
             该脚本含条件分支（如 `if [ -f "$PUB/CNAME" ]`）⇒ 不同环境计数可能差 1 ✓ **不是文档漂移** ✗
```
**验收**：仓库无"当前口径下不挂载"的死文件（或明确标注归档）｜文档旧说法清零
**工时/风险**：30min ｜ 低

---

## 11. T11（P3）服务器与运维（补充项）

```
· 备案：**这是唯一能回到直连速度的路**（271~338 KB/s）⇒ 建议尽快办；办下来后 apex/www 改回 A 43.143.114.79（灰云）
· 证书续期告警（到期前 21/7/1 天三级）+ 续期后自动访问一次 https 校验 ✗ 现在没有
· srv2 站点可用性**外部探测**（srv2 是整站单点 ✗；现在靠 CF 隧道顶着，路径已变 ⇒ 探测目标应为
  `https://xiaokeqing.cn/`（经 CF）**和** srv1 侧直连 `direct.xiaokeqing.cn`（若开放）两条各测）
· `static.xiaokeqing.cn` 只服务 248 B 占位页 ✗ ⇒ 文档与监控都不要再把它当"主站备份路径"（已在 T2.8/T0② 写明）
· 备份范围建议：/etc/nginx、/etc/systemd/system/secagent-static.service、/etc/letsencrypt、/opt/secagent/scripts + **恢复演练**
· 媒体迁 COS/OSS + CDN（流量/海外访客变大时）；"同域 CNAME 到 CDN"是否算违反零第三方请求 → 见 §12 待拍板
```
**工时/风险**：按项取（每项 20min~1h）

---

## 12. 需要站长/评审拍板的 7 件事（执行前先问）

```
① 先做哪条？（我建议：T1 → T5.2/T5.1 → T3 → T4 → T5.6 → T7 → T6 → T8）
② boot→hi（T5.6）要动 demo 内联脚本 ⇒ 允许吗？（视觉不变、首屏 −47% ✓ 我认为不算降质）
③ 语音先上 8~12 句（按 7 分组各 1~2 条）还是全量 60 句（需压码率到 ≈2.6 MiB）？
④ /about/ 那屏的内容谁写、写什么口径？（必须真实数据、取不到写"读不到" ✗）
⑤ 资产瘦身：是否接受"先接线、再删 medium/hi"的顺序（不能反过来 ✗）
⑥ 媒体走 CDN 的"同域"边界（CNAME 到 CDN 是否算第三方请求）——影响 T11 取舍
⑦ Fish Audio Key 给不给（给了 L2 才能把回答说出来；代理已实现三道闸 + 磁盘缓存 + kill switch，现 503 关闭态）
```

---

## 13. 我与接手方 AI 的核验结论对照（省得重复查）

```
✅ 接手方 AI（E:\DeepSeek1\123\接手方案与优化点汇总-20261015.md）**实测正确的**：
   F1 契约 6 处、F2 纯概率 10/38、F2② thinking_trans 缺失、F3 opening/speaking/thinking 无视频且不在状态机、
   F4 /opt/secagent/static 与 /site 的区别、A1 报错行、B1 资产对账（82.4MB vs 引用 7.15MiB）、
   C2 后端 ask 200 + 返回字段 + GET 应 405、C4 tts 503、D1 boot 档存在且未被引用、E1 生成器、E2 双轨、E3 遗留
✗ 它**唯一写错**的：E4-①「assert 实测 15 项」—— 我连跑三次 **16 项** ✓（脚本有条件分支，环境差异可解释）
⚠️ 它 **B1 路线二**（把 medium/hi 移出 git）需加限制 ⇒ 见 T9（文章页运行时会取 medium ✗）
✅ 我已实测确认：**CORS 允许 https://xiaokeqing.cn**（`access-control-allow-origin` 回显 ✓）⇒ T3 无跨域障碍
✅ 我已实测确认：**未备案阻断**（302 → dnspod.qcloud.com/static/webblock.html）⇒ 本文 §0①
```

---

## 14. 公共纪律（每条任务都适用）

```
· 只改自己的文件；`git add` 只加自己的路径（禁入 public/、_shots/、大文件）✗
· 改完必跑三道门禁；**push ≠ 上线** ✗（要跑 publish-site-to-srv2.ps1）
· 改 `layouts/*` 必同步 `_dev/gen-demo-pages.py` ✗
· 不许停留假数字/演示数据 ✗（取不到写"读不到"）；不许前端兜底造假 ✗
· 不许在用户手势前播放音频 ✗；不许给页面加第三方请求 ✗
· 本机直连线上会被未备案阻断 ✗ ⇒ 核验走 srv1 或 CF
· 一条任务一个归属人 ✗（同一文件别两个人同时改）
```

---

## 附录·历史（按时间追加，不再维护；权威以 §A 总表为准）

### 附录-1 · 状态板（2026-10-15 复核，接手批已入库）


| 任务 | 状态 | 证据 / 说明 |
|---|---|---|
| T1 手机动画不放 | ✅ 已修并上线（229e0d7→site-20261015-181533） | 站点现在约 1 秒打开、素材 548KB/s ✓；请手机复测：出来了=当时素材没到；不动=`r.height<260` 降级阈值成立 ✗ |
| T2 我文档的 7 处错误 | ✅ 已修（5c443dc） | 见本文 §2 逐条"改成什么" |
| T3 会对话接线 | ✅ 代码完成 | `/ai/` 已真调 `POST /api/public/ask`；跨域已验证 ✓；**未发布** ✗ |
| T4 语音 L1 | 🟡 一半 | 播放链已接（手势门控 ✓）；**只剩换日语素材**（`sample8/dist/*.m4a|webm` + bank.json → `static/kurisu/voice/`，契约兼容 ✓）|
| T5.1 五页 TypeError | ✅ | `shell-script.html:692 const fb=...` 空值保护 ✓，六页 console=0 ✓ |
| T5.2 门禁硬断言 | ✅ 有错即 exit 1（8f33aa6，故障注入实测） | 控制台错误仍未 exit 1 |
| T5.3 /about/ 空白 | ✅ 四张真实卡，正文 0→591（8f33aa6） | 产物正文仍 0 字 |
| T5.4 主页残留 `1,284` | ✅ 改占位+api-bind 填真值（6b35e89） | 静态里改占位，JS 填真值 |
| T5.5 /posts/ 卡片非链接 | ✅ Hugo range 8 篇真文章（6b35e89） | |
| T5.6 boot→hi | ✅ 已实施（d8e03e6） | 省 47%~70%、视觉不变 ✓ |
| T6 生成器 thinking_trans | ✅ | 已改"从 prob=0 边派生" ⇒ 9 个含 thinking_trans ✓，38/88 不变 ✓ |
| T7 视频接线 | ❌ | 留到 T8 一起（对 opening/speaking 零帮助 ✗）|
| T8 状态机 + 口型 | ❌ | 最难；"活起来"的关键 |
| T9 资产瘦身 | ❌ | **顺序不能反**：先接线再删 medium/hi ✗ |
| T10 遗留文件 / 双轨 | ❌ | preview-shell.html 等归档或删 |
| T11 服务器与运维 | ❌ | 备案是回直连的唯一路 ✓ |
| **T12 删背景选择器 + boot→hi** | ✅ **已完成**（d8e03e6） | 用户投诉"加载太卡"✗：① 删右下角「背景/配色」面板 + 配套 CSS/JS/生成器片段（实测首屏只载当前 1 张 room_empty 84KB ⇒ 内容页 267→约190KB）② **并做 T5.6**（主页 −47%、ai 页 −70%，视觉不变 ✓）｜**T7 不并做** ✗ |

**接手批额外做的（方向对 ✓）**：表情 5→8 套（改用会动的 `avatar/*.idle/speaking.webp`）｜主页加"表情模式" XK_ACT + 表情条 ｜ 语音播放时不覆盖语音字幕

**✅ 2026-10-15 执行AI批**：T1/T5.1~T5.6/T12/T2 全部完成并已发布上线（HEAD 8f33aa6 → site-20261015-181533，home 首屏 840KB）；交接见 `交接-执行AI批-20261015.md`。

**⚠️ 已提交未发布**（历史记录）：接手批只在仓库（HEAD `0112ce2`），线上仍是 `site-20261014-235208` ✗ —— 不发布的原因：一发布就会播**旧 SAPI 占位音** ✗；建议先做 T4 换日语素材，再一起 `scripts/publish-site-to-srv2.ps1` ✓
---

### 附录-2 · 执行批完成情况

**基线**：HEAD `8f33aa6`（已 push）｜线上 srv2 `/opt/secagent/releases/site-20261015-181533`（上一版 `site-20261015-112007` 保留 ⇒ 秒级回滚）｜工作区干净

**门禁**：assert-build **15/15**（注意：计数含条件分支，我这边跑出 16 项 —— 两者都算绿 ✓）｜firstscreen **6/6**（预算见总账 §2.6；主页首屏字节见附录-1）｜ssr-contract 6/6 ｜ **控制台错误已改成 exit 1**（T5.2）

#### 附录-2.1 状态板覆盖（§A 总表的原始依据）

| 任务 | 状态 | 关键证据 |
|---|---|---|
| T1 手机动画 | ✅ 已上线 | iPhone 横屏 CRT 高 224px < 原型死阈值 260px ⇒ 整屏 fallback 盖住动画；判据改为 `r.height<260 && !matchMedia("(pointer:coarse)").matches` ⇒ 触屏一律播动画；冻帧对拍像素差 0 |
| T2 文档 7 处 | ✅ | statemachine 契约（nodes 数组/无 geometry/from_id-to_id）· 13 个 once_then_hold · 10/38 · opening 占首屏 65% · PR-3 不能整体替换 · `/opt/secagent/site` 才是主站真身 · 备案硬前提 |
| T3 会对话 | ✅（早前） | /ai/ 真调 `POST /api/public/ask` |
| T4 语音 L1 | ✅ 已上线（核实） | 12 句 / 7 分组 / 717KB；CDP 实测手势前 plays=0、手势后 plays=1、字幕逐字对齐 |
| T5.1 TypeError | ✅（早前） | #fallback/#bootveil 存在性判断 + opening 门控 |
| T5.2 门禁硬断言 | ✅ | console error/未捕获异常即 FAIL + exit 1；**故障注入实测拦获** |
| T5.3 /about/ | ✅ | 87 字节残 div → 四张真实内容卡，正文 0→591 字 |
| T5.4 假数字 | ✅ | 1,284/96/37 改 `—` 占位，api-bind 填真值 |
| T5.5 /posts/ 链接 | ✅ | 死笔记 → Hugo range 渲染 8 篇真文章链接（shell-views 的 dict 需带 `"page" .`）|
| T5.6 boot→hi | ✅ | 四个剪辑各加 boot 档（前 24 帧、281–532KB）⇒ 主页 **1569→840KB（−47%）**、内容页 267→185KB、/ai/ 1637→1555KB；最终画质不变（14s 时 demoClip=idle、画布 52,032 像素与旧版一致）|
| T6 生成器 | ✅（早前） | prob=0 边派生 ⇒ host_triggered_entries 9 个 |
| T12 删背景选择器 | ✅ | 面板+压暗+配色/手机切换+背景图全删；body 静态 `data-skin="warm" data-phone="v1"` |
| L1 镜头语言 | ✅ 新增 | CRT 通电（亮线→竖向展开→抖动→过冲白光→稳定）+ opening→idle 推拉 0.9s（末段交叉融化）；仅主页，RM 用户走静态 idle |
| T7 视频接线 | ❌ 未做 | 2–3h |
| T8 状态机+口型 | ❌ 未做 | 3–5h，最难 |
| T9 资产瘦身 | ❌ 未做 | **必须先接线再删 medium/hi** ✗ |
| T10 遗留文件/双轨 | ❌ 未做 | |
| T11 服务器/备案 | ❌ 未做 | 备案=回直连唯一路 |

#### 附录-2.2 必须知道的 6 条机制（细节见 `docs/交接-执行AI批-20261015.md` §3）

```
① 双轨 + 生成器：六页由 _dev/gen-demo-pages.py 从 docs/demo-*.html 重新生成 —— 改 layouts/* 必须同步生成器并重跑；
   生成器锚点必须匹配 **demo 原文**（不是产物文本）；补丁有先后依赖（L1/CRT 补丁要在 T5.6 引用的代码之后）
② 动画链：CLIPS 四剪辑逐帧；xkClipIm(name) 先 **peek** hi 缓存（绝不能 img() 创建 —— 创建即发请求 ✗）、
   未就绪兜底 boot 档、hi 到位按同一帧号无缝接力；boot 期间 opening 走 fi % 24 循环等 hi；门禁 home 检查点已改 9s
③ 语音链：bank.json 12 句日语 + 中字幕；手势门控（首次 pointerdown/keydown 解锁）；XKV 状态可观测
④ 发布链：push ≠ 上线 ✗。`scripts/publish-site-to-srv2.ps1 -FromRef HEAD`；
   **scp 报 `pipe: Unknown error` 是 Windows OpenSSH 老毛病** ⇒ 手动通道：`scp -O` 传 tar → install 接收脚本 →
   `sudo -n bash /opt/secagent/scripts/srv2-site-receive.sh <tar>`（原子切换 + 失败自动回滚）
⑤ 门禁方法论：改完必跑三件套；对"拦截型"逻辑必须做**故障注入**验证真能拦 ✓
⑥ 回滚：把 /opt/secagent/site 软链指回上一个 release 目录即可；发布脚本保留最近 4 版
```

#### 附录-2.3 本批踩过并拦住的 5 个真 bug（教训，别重犯）

| # | 现象 | 根因 | 教训 |
|---|---|---|---|
| 1 | L1 生成代码缺 xkDrawTrans | 生成器编辑手滑把旧补丁顶掉 | 每次生成后 grep 函数存在性 |
| 2 | 生成器补丁"对不上 0 次" | 锚点写成产物里才有的行 | 锚点永远匹配 demo 原文 |
| 3 | 开场卡 boot 档永不落幕 | xkClipIm 先兜底 boot 再 peek hi | peek/兜底顺序；门禁 demoClip 抓到 |
| 4 | 门禁一遇错误就崩 | `pass=false` 赋给 const pass | 故障注入逼出来；pass 计算里 fold |
| 5 | 门禁启动即崩 | Node 侧误用 window | evalJs 里的表达式才在浏览器跑 |

#### 附录-2.4 现存未决（**要站长拍板/动手**）

```
① [已由我 5 分钟完成] 状态板更新 ⇒ 见附录-2.1 ✓
② [待拍板] TTS"念回答"(L2) 三选一 —— srv1 上 key/开关/短语表**已配好**（self-check `key=SET phrases=3`），
   但 **api.fish.audio 在境内被 SNI 重置**（TCP 可建、TLS 漏 SNI 即 RST）⇒ UPSTREAM_IO：
     A. CF Worker 中转（需站长在 CF 面板操作；现有 API token 已失效 ✗）
     B. DashScope TTS 进代理（境内实测 0.22s，但要改 Java 代码 + 重建）
     C. 暂缓（预渲染 12 句不受影响 ✓）  回滚 A/C = 删 .env 三行 + compose 五行
③ 下一层：T7 视频 → T8 状态机+口型 → T9 瘦身（先接线 ✗）→ T11 备案运维
④ 远期王牌：**SpriteForge**（Code-Amadeus/Amadeus-SpriteForge 官方资产生成工具，可产新表情动作）
   ｜ **Kurisu GPT-SoVITS v2ProPlus 模型**（可给 12 句 bank 提质，本地合成、不受 fish.audio 阻断影响 ✓）
④ ★安全：**Fish Audio key 曾在聊天里出现** ⇒ 请到 fish.audio 控制台**轮换**，换新后同步 srv1 `.env` 的 `APP_TTS_API_KEY` ✓
```
---

### 附录-3 · AI 项目升格任务

| 编号 | 任务 | 工时 | 依赖/插点 | 一句话验收 |
|---|---|---|---|---|
| **T13** | **评测包**（ASR 回译 CER + 问答质量集 ≥30 条含拒答用例 + MOS/ABX 流程 + `scripts/eval/` 可重跑） | 1 天 | **不依赖别的任务，现在就能做 ✓**；产出喂 T16 | 60 句 CER 逐句+均值表 ｜ 质量集得分表 ｜ MOS 结果表 ｜ 脚本可重跑 |
| **T14** | **LLM 决策行为**（告警摘要 → 严格 JSON：情绪/剪辑/台词/urgency/reason；白名单校验防幻觉；缓存；超时回退） | 1~2 天 | **与 T8 状态机+口型接线合并做**（9 个 prob=0 宿主入口就是为它准备的 ✓） | 5 组场景合法输出（附 JSON）｜ 幻觉率 0 ｜ 失败注入可回退 ｜ 5 分钟内同场景缓存命中 |
| **T15** | **语音闭环**（ASR → LLM → TTS + 打断 + 延迟预算） | 2~3 天 | 放 T14 之后；受 ASR 环境影响 ✗ | 端到端录屏（含打断）｜ 延迟分解表（首字 ≤1.5s / 首音 ≤3s）｜ 降级可用 |
| **T16** | **《AI 项目说明书》**（1~2 页：定位/四层架构/技术栈/指标表/成本表/难点解法/可复现/边界与不足） | 半天 | 放 T13 之后（要用它的数字） | 文档可直接用于简历/答辩 ✓ |

**三个缺口（升格的本质）**：① 没有 AI 质量评测 ✗（只有工程指标）② 没有数据闭环 ✗（真攻击日志没系统化成语料+评测集）③ AI 没参与她的行为 ✗（LLM 只管问答，动作还是概率+固定事件）

**四项待拍板**：① 语音评测做不做主观 MOS（需人盲听 20 分钟 ✓）② 她说话只允许预渲染台词 ✗ 还是允许自由文本（花钱 ✓）③ 语音输入做不做（做=最像 AI 项目，但受 ASR 环境影响 ✗）④ 面向"简历/答辩"还是"真给访客用"（前者重报告与演示，后者重稳定与成本 ✓）

**建议顺序**：T13 →（T7 视频 + T8 状态机口型 + T14 决策）→ T15 → T16 → T9 瘦身 → T11 备案运维
---

### 附录-4 · 角色能力深化任务

| 编号 | 任务 | 工时 | 要点 | 验收 |
|---|---|---|---|---|
| **T17** | **声音模型换代 A/B** | 0.5 天 | 已按本行做完 ✓（结论＝**不换模型、继续 v3**；三代 CER/RTF/显存见总账 §2.4）；先听素材 `F:\7AAA\AI\命运石之门\1\00_all_emotions__order-v2pro_v2proplus_v3.wav`（三代模型×全情绪对比 ✓）；候选 = v3 / v2ProPlus(e80+e12) / e100；同句同情绪三方盲听 | 三代同句 m4a 各 1 个 + 盲听结论 + 选定模型实测（RTF/显存/响度）｜回滚=bank.json 换回旧 12 句 |
| **T18** | **素材产线评估（SpriteForge + Wan）** | 1 天 | 已按本行做完 ✓（帧率/帧数/一致性实测见总账 §2.3）；读 SpriteForge 文档与 `discussions/27`；搞清输入要求/输出规格/显存需求/成本；评估"新动作 pilot（2 个）· 半身换装 · 全身/腿部（不建议 ✗）"；**先评估不要先买 GPU** ✗ | 一份评估报告（含 1 个 pilot 可执行步骤、成本区间、一致性验收=必须对齐 764×1028 ✗）+ 明确的做/不做建议 |
| **T19** | **双智能体协作方案** | 1 天 | 落地三层模型（只读 / 决策 / 提议）+ 权限矩阵 + 审计字段；写 `persona.md`（性格/口癖/禁忌/说话风格 → LLM system prompt）；定义 `POST /public/decide`、`/public/propose`（需审批）契约草案；画"谁能调谁"边界图 | 方案文档 + 接口草案 + persona.md（可直接喂 LLM）｜**铁律：她的输出永不进执行链** ✗ |

**另有一个可选活**：`F:\7AAA\AI\命运石之门\1\` 里 40 个 mp4 + 5 个 mov（2.3GB，疑似作者演示录屏）⇒ 逐帧分析产出"**情绪↔动作↔语调对照表**"（约半天 ✓），是 T14 的输入 ✓

**建议顺序**：T13 评测包 →（T7 视频 + T8 状态机口型 + **T14 决策**）→ **T17 声音换代**（可并行）→ **T18 产线评估** → T15 语音闭环 → **T19 双智能体** → T16 项目说明书 → T9 瘦身 → T11 备案运维
> **口径修正（2026-10-15）**：**T18 的目标是"建设能力"而不是"产某个素材"** ✗ ——
> 即打通三段：**能生成（SpriteForge/ComfyUI + 云 GPU）→ 能对齐+能筛（`tools/asset-align.py`、
> `tools/asset-consistency.py` + 角色定妆集）→ 能入库（生成器支持"新剪辑登记表" + 一页 SOP）** ✓
> 验收看"能力"：SOP 跑通一次、脚本可重跑、一致性阈值是**互测标定**出来的、附每动作成本表 ✓
> 详见 `docs/角色能力深化与双智能体协作方案-20261015.md` §六（含能力分级表：新动作/半身换装 ✅ 可达；
> 全身与发型 🟡 困难；整段行走 ❌ 不建议）✓
---

### 附录-5 · 后端展示落地任务

> F 的完整规划见 `docs/后端功能与博客展示规划-20261015.md`（49.8KB）；状态见 `docs/状态-F-后端功能展示.md` ✓

| 编号 | 任务 | 归谁 | 工时 | 要点 |
|---|---|---|---|---|
| **T20** | **处置成果「封禁榜」上屏** | C 落地 + G 出 UI | 2~3h | 放 `/alerts/`「数据统计」pane 的 grid32（现有故事线卡旁）；数据 `GET /api/public/audit`：`summary{blockTotal,blockActive,blockedByGuard,executedActions}` + `blocks[]{ip,durationMinutes,source,actor,createdAt,unblocked,unblockMode,auditId}`；**IP 按站主规则掩码**：保留前三段、最后一段换 `x`（`172.16.18.12` → `172.16.18.x`）✓；空态区分"读不到（HTTP xxx）"与"本窗口没有封禁记录"✓；复用 `.mod/.row/.chip` 不新增 CSS ✓；**验收含"DOM 里不出现完整四段 IP"** ✓（掩码函数只改显示、**不改用于分组的原始值** ✗ 否则同 /24 攻击者会被合并 ✓） |
| **T21** | **攻击故事线上屏** | C + G | 5~6h | `/alerts/` 现有故事线卡原地升级；候选池 `/stories` + **点击才懒加载** `GET /api/public/story?src=` 画时间线（`events[]` 升序、每段 ≤40、`truncated` 如实标注 ✓）；必须区分"该来源这段没数据"与"尚未接入（coverage.status=NOT_WIRED）"✗；脱敏要覆盖 `srcIp` **与 `events[].summary` 内嵌 IP**（同一规则：最后一段 → `x` ✓）；**验收含"点击前 0 个 /story 请求"** ✓ |
| **T22** | **知识库栏目** | C + G | 2~3h | 放 `/ai/`（该页现在 0 轮询、最干净 ✓）；`GET /api/public/kb?q=`（独立 20 次/分钟上限、有 embedding 成本 ✗）⇒ 固定话题按钮 + Enter 才发 + 会话内缓存 + **不轮询** ✓；显著写明后端白名单口径（`allowed-roots=security-docs,data/kb-approved`、`allowed-source-types=community`）；结果最多 3 条；空态写"公开知识库没有命中「X」的内容（不是取不到，是确实没有）"✓；**验收含"静置 60s 0 请求"** ✓ |

#### 附录-5.1 · 问题单（按优先级，需要拍板或修 ✗）
```
U1【红线冲突·最重要】后端**早就有全局 IP 掩码开关**（`app.public.mask-ips`，唯一读取点 PublicIpPolicy.java），
   但**生产默认 = false ⇒ 展示真实 IP** ✗；实测所有响应 ipDisclosure.masked=false、stories[].srcIp 是完整公网 IP。
   ① 后端翻开关（≈1 个环境变量，所有端点含存量页面一次性合规 ✓ 但属后端线操作 + 要重启应用）
   ② 不翻、只在前端脱敏（存量页面继续打完整 IP ✗ ）——**我的建议是 ①**，需站主一句话 ✓
R1【站主已裁定：**不算违规、保留** ✓】
   掩码规则改为"只掩最后一段"⇒ 存量三处（api-bind.html L223/L276/L335）**无需改动即可接受** ✓；
   若要统一成掩码显示，顺手加一个 `maskIp()` 即可（非必须 ✗）。原描述：老页面渲染攻击者 IP：`layouts/partials/xk-demo/api-bind.html` L223（路径图节点）·
   L276（/stories tag）· L335（攻击流终端行）⇒ 必须与 T20/T21 同批改，或明确豁免 ✓
U5【信息泄漏】`/api/health` **无鉴权且 200** ✗，泄漏 embeddedGitCommit/提交信息/mock 开关/documentVectors ⇒ 建议收口 ✓
R3【文案与实现不符】靶场页卡头写 `POST /api/playground/check`，实现却是 `PG_DEMO` 本地假结果 ✗ ⇒ 要么接真接口、要么改文案 ✓
U4【后端线提醒】`/opt/secagent/src` 源码树**落后于运行 jar** ✗（没有 stories/story/webstats 实现）⇒ 后端线若"改源码重编"会丢掉这三个端点 ✓
订正：`POST /api/public/tts` 实测 **400 TEXT_NOT_ALLOWED**（不是 503 ✗）⇒ **数字以总账 §2.5 为准**；该行待总账侧订正
订正：srv2 现行 release = **site-20261015-181533** ⇒ **比总账 §2.6 所记旧值更新**（该行待总账侧更新 ✓）
```

### 附录-5.2 · F 从 GitHub Discussion #27 得到的结论
```
① "用户意图会在交互中途漂移 ⇒ 必须重新路由" 正对应我们"公开面只解释概念/内部面才有事件数据"的分层 ✓
② "短期 branch 只把可验证证据交回主线" 对应"处置留痕 auditId/actions 才算证据，模型自述不算"✓（与 T20 展示 auditId 同源）
③ "边界必须靠对照实验定义" 正对应 R3 这类"文案承诺了接口、实现却是本地演示"的坑 ✓
旁证：maintainer 自述"做 Kurisu 角色与执行解耦" ⇒ **角色层不承担执行**是被上游认可的架构 ✓（与我们的铁律同源 ✓）
```
### 附录-5.3 · U1 决议（站主 2026-10-15 拍板）

```
**不翻转后端全局 mask-ips 开关** ✓（保留真实攻击源地址）
**展示规则**：攻击者 IP **保留前三段、最后一段换成 x** ✓（例 `172.16.18.12` → `172.16.18.x`）
  · 实现：一个 `maskIp(s)` 只作用于**显示**；用于分组的原始值**不许改** ✗（否则同 /24 攻击者会被合并 ✗）
  · 已对 `***`/`x` 之类的字符串做幂等处理（避免二次掩码 ✗）
**唯一真红线**：访客自己的 IP、我们内部/内网地址 —— **一律不上页面** ✗（与攻击源地址区分对待 ✓）
⇒ 影响：T20/T21/T22 与 Kimi 设计稿全部按此改；**R1 存量三处不算违规、无需改动** ✓（能顺手统一更好，非必须 ✗）
```
### 附录-5.4 · E(T19) 四条待拍板

```
① 提议层是否现在做 ⇒ **先只做决策层** ✓。提议层（POST /propose）等审批链扎实后再上 ✗（现在做=有执行风险 ✗）
② 熔断参数 N=3 / 退避 30s→2min→5min ⇒ **作为默认值认可** ✓，但标注「[建议值，未标定前不作验收门槛]」
   （遵守 D5：不许拿没标定的数字当验收 ✗）
③ persona.md 部署位置 ⇒ **登记为 U6，交运维窗口 H 只读查证**（现网 /ask 的 system prompt 存在哪份配置 ✗），
   查清后写入规格 §11；在查清前 T14 按"提示词可注入但权限不变"的现有分层实现 ✓（不阻塞开发 ✓）
④ 她的拒绝措辞 ⇒ **固定成台词库 id** ✓（必出得了声 ✓）；自由文本只允许出现在字幕、且必须标记"仅字幕不出声" ✓
新增问题单 U7：成本口径缺 /ask 与 /decide 的 **token 上限**（现只有"600 字符"✗ 字符≠token）⇒ 
   **T14 验收必须补"单次 decide 的 token 与费用实测"** ✓，否则"成本熔断"只有局部三闸 ✗
新增问题单 U6：persona/system prompt 的现网存放位置 [待核对]（后端源码树不在本仓库 ✗）⇒ 归窗口 H 只读查证 ✓
```
### 附录-5.5 · T24 结论与安全注意
```
公开不做 ✗ —— 官方游戏素材，demo 作者明文禁止上传/再分发；FreeMote WebGL 为 CC BY-NC-SA 4.0（非商业）
能力真相：它给的是「官方已做好的两套服装 + 全身」，**并不提供「自己产服装/发型/腿」的能力** ✗
  ⇒ 站长要的能力仍只能走 T18/SpriteForge（能生成 → 能对齐 → 能筛 → 能入库）✓
成本：A 独立一页 2.5~3.5 人日 ｜ B 共存专区 4~6 人日 ｜ C 全面换渲染层 15~25 人日（不做 ✗）
只想本机看一眼：0.5~1 人日（解包 → demo 6 文件 + vendor 运行时 → 本地 http.server → 记字节/内存/首交互/控制台）✓ 不发布
★ 安全：本机素材 README 里带着**游戏解包密钥** ✗ ⇒ 该 README 与解包脚本绝不许进公开仓库/文档 ✗（已写进活文档 §6 ⑩）
```
### 附录-5.6 · A（T13）带来的三条新事实/陷阱
```
① **公开问答额度池 = 30 次/日、全局共享** ✗ ⇒ 任何"用公开端点做评测/压测"的排期都要先算额度；
   本轮 20:33 就被打满，A 按纪律停手（间隔 11s、串行、命中即停、不绕限流 ✓）⇒ 全量得分要跨两天续跑 ✓
② **本机 Python 子进程写不进 F: 仓库** ✗（PermissionError/拒绝访问；同目录 PowerShell Set-Content 能写 ✓）
   ⇒ 任何"脚本直接产出到仓库"的设计都会失败 ✗；要么写仓库外再拷、要么用 harness 文件工具 ✓
③ **本机没有 ja-JP 的 SAPI 声音** ✗（只有 zh-CN Huihui / en-US Zira）
   ⇒ 评测方案里"日语 SAPI 对照"这条**不存在**，只能做跨语言弱对照，且文档里不许说成日语对照 ✗
需人耳一次（各 1 分钟，脚本/文件都已就绪 ✓）：
   · `greet_first_ever`（角色名被 ASR 听成别的词，CER 0.55）⇒ 判断是 TTS 发音还是 ASR 识别问题 ✓
   · MOS/ABX 盲听 20 分钟（出题脚本已跑通、评分脚本已就绪 ✓）
```
### 附录-5.7 · H（T11）提的两件待拍板
```
① 备案提交前是否把 apex/www 从「CF 隧道 橙云」切回「A 43.143.114.79 / DNS only 灰云」？
   ⇒ **提交备案时再切** ✓（切了公网解析才指回境内服务器、接入核验才对得上 ✓）；
     注意副作用：切换期间站点会**短暂不可用或被未备案阻断** ✗ ⇒ 建议作为独立动作、由站主在控制台操作 ✓
② 配置备份要不要加 srv2→srv1 异地一份（需要新只读密钥）？
   ⇒ **暂不加** ✗（异地备份要新增凭据 ✗，而现有 srv1 数据备份已异地加密 6 份/11M ✓ + 恢复演练已验证 ✓）
     ⇒ 留作可选后续（等真出事场景变多再说 ✓）
```
### 附录-5.8 · D（T18/T23）结论、新问题单与规划侧拍板
```
★ 重大口径纠正：SpriteForge **不需要买 GPU** ✓ —— 它本体是纯 CPU（本地 HTTP + 本地 IO + 零模型）；
  真正要花钱的是"生成那一步"的**远端付费服务**（Wan2.7 官方 ¥0.6/秒 720P ✓；2s 转场 ¥1.2、4s 循环 ¥2.4 ✓）
  ⇒ 前置从"云 GPU 成本拍板"改成"**要不要开一个付费生成账号 / 或网页手动生成**"✗
规划侧拍板①：**批准 pilot 预算上限 ¥30**（2 个动作：乐观 ¥7.2 / 保守 ¥21.6 ✓）—— 相当于一杯咖啡 ✓ 不立项、不租机器 ✓
规划侧拍板②：SOP 三套流程（新动作/一套服装/一个发型）**先照文档跑新动作** ✓；换装/发型等 pilot 成功后再评估 ✓
规划侧拍板③：**段三（把新剪辑注册进 statemachine.json）归窗口 C** ✓（要改 _dev/build_statemachine_manifest.py 与 statemachine.json ✓）
新增问题单 U8【会影响口型与落位】`statemachine.json` 的 `opaque_bbox` **不可用** ✗：idle 写 [116,0,764,1028]，
  实测 alpha 外框是 [11,17,661,1022]；38 个剪辑的 x1/y1 恒等于画布宽高 ⇒ 不是真实包围盒 ✓
  ⇒ **T8（状态机+口型）实现时必须实测外框，不许用 opaque_bbox 居中/裁边** ✗（横向会偏 ~105px、纵向 ~17px ✓）
新增情报 S1：SpriteForge 的 `spriteforge_mouth_config.json` **自带逐帧嘴部锚点 + 闭嘴 overlay** ✓
  ⇒ 正好补上"作者端追踪器闭源"的缺口 ⇒ **T8 口型实现要参考它** ✓
新增情报 S2：一致性判定结论（标定数据得出，非偏好）—— **rgbNcc 是"是不是她"的主判据**（反相假素材 edgeNcc 0.83 能过、
  但 rgbNcc −0.9999 一票否决 ✓），**edgeNcc 只做"姿态有没有跑偏"的辅助** ✗，且**不能跨姿态用** ✓
```
### 附录-5.9 · K（后端问答模型取证）结论与登记
```
已确认（不再标 [待核对]）：模型 = **DashScope qwen-plus**（Spring AI Alibaba 1.1.0.0-RC2）；
  temperature=0.0 / topP=0.1 / **max_tokens=800** ✗；单次硬超时 15s；失败冷却 60s；SDK retry 3 次；
  ANALYST 最多重试 2 次；每次提问最多 2 次模型调用；**无多轮**（空历史 ✗）；**工具调用恒禁止** ✓；
  maxQuestionChars=600 / body≤4000 / deadlineMs=20000 / 6 次·分·IP / 同 IP 并发 1；公开池 30 次/日
  **无本地推理** ✓（无 ollama/vLLM/权重/GPU；本机 1870MB RAM 跑不了可用本地模型 ✗）
  jar 内 yml 与权威源码 F:\\7AAA\\AI\\SecAgent\\sec-agent（HEAD=da9d1db）去 CRLF 后 md5 完全一致 ✓（部署可追溯）
★ 最大短板：**max_tokens=800 硬天花板** ✗ ⇒ 答案一展开就截断 → JSON 校验失败 → 重试仍失败 → 报 model-failed
  ⇒ **"答案太长"会被表现成"模型不可用"** ✓（最容易误诊的一条 ✓）
★ 第二个坑：yml 的 `rag.model` **不控制公开问答** ✗（公开链路用硬编码 DEFAULT_MODEL_NAME）⇒ 改 yml 换模型无效 ✗
新增任务 T25（归后端线，需站主/运维动手 ✗）：**提高 max_tokens 800→2000+ 并评估换 qwen-max**
  · 路线 A：改一行 Java（模型名硬编码）+ yml 的 max-tokens + 重建镜像 ⇒ 收效最大 ✓
  · 路线 B：切 DeepSeek（.env 设 APP_LLM_PROVIDER=deepseek + KEY ✓）但 **DASHSCOPE_API_KEY 不能撤** ✗（embedding 仍要它）
  · 路线 C：本地推理 ⇒ 现机不可行 ✗（要换机型或新增 7×24 推理服务）
  · 共通：升级后核对启动自检行 `LLM-PROVIDER-SELFCHECK` ✓；`fallback-provider` 现为空 ⇒ 跨供应商回退关闭（fail-closed ✓）
★★ 安全：K 取证时一次白名单 grep 误把 **APP_TTS_API_KEY（Fish Audio TTS 凭据）** 打进了工具输出 ✗
  （未写入任何文件 ✓ 已 grep 校验，但**建议轮换该 TTS Key** ✗ —— 这已是该凭据第二次暴露 ✓）
```
### 附录-5.10 · 安全决定：Fish TTS Key 暂不轮换
```
事实：该 Key（APP_TTS_API_KEY，Fish Audio TTS 凭据）曾在会话输出中出现两次 ✗（均未写入仓库文件 ✓ 已 grep 校验）
站主决定：**暂不轮换** ✓（懒得弄 —— 规划侧接受，不再重复提醒 ✗）
风险量化（为什么这个决定可以接受 ✓）：
  ① 它是**TTS 服务的按量凭据**，不是服务器/root/数据库凭据 ⇒ 最坏后果只是"有人用掉 TTS 额度"（花钱 ✗），
     **拿不到任何数据、动不了任何服务器** ✓
  ② 更关键：现网 `/api/public/tts` **只接受白名单短语** ✓（实测缺 src/非白名单文本直接 400 TEXT_NOT_ALLOWED ✓）
     ⇒ 即使 Key 泄露，也无法用它刷"任意文本 TTS"✗；且代理侧已有三道闸 + sha256 缓存 + kill switch ✓
  ③ 该 Key 目前**没在为任何线上功能服务**（自由文本 TTS 还没上线 ✓）⇒ 泄露的边际损失 ≈ 0 ✓
触发重估的条件（到时再轮换 ✓）：**一旦要让 AI 的自由回答"念出来"**（L2 上线 ✓），这个 Key 才真正值钱 ⇒ 那时必须换新 ✓
补偿控制（不需要站主操作 ✓）：确认 TTS 代理的**白名单 + 限流 + 月硬顶熔断**在 L2 上线前必须就位 ✓（已写进 T19 规格 §6 成本熔断 ✓）
```
### 附录-5.11 · T26（语音正确性·J 的结论落地）
```
T26-a【必做，已验证 ✓】任何含「牧瀬紅莉栖」的台词，**送 TTS 的文本**改写假名 `牧瀬クリス`
  （当前只有 `greet_first_ever` 一句 ✓；**显示文本/字幕不许改** ✗；双语库要支持"朗读文本 ≠ 显示文本"）
T26-b【根治，待核对】`_amadeus-src\\GPT_SoVITS\\text\\ja_userdic\\userdict.csv` 加 `牧瀬紅莉栖→マキセクリス`
  —— 机制已存在（japanese.py 会 mecab_dict_index + update_global_jtalk_with_user_dict ✓）
  但 J 按 naist-jdic 13 列试写被接受却 g2p 返回空串 ✗ ⇒ **列格式未核对** `[待核对]` ⇒ 先靠 a 兜底 ✓
★ 已否掉的修法（别再做 ✗）：换参考音频 ✗｜换 v2ProPlus ✗（各档同一日文前端、读音逐字相同）｜拆句 ✗（孤立仍错）
```
### 附录-5.12 · 后端问答升级清单（L，2026-10-15）与规划侧拍板
```
根因排序（影响÷成本）：① max_tokens=800 + 入口 600字符/20s 收紧 ★3.0 ② fail-closed 语义未分层 ★3.0
  ③ 无工具调用 ★1.5 ④ 语料与提问错位 ★1.5 ⑤ 检索质量 ★0.5（已打满 ✗ 不必动）⑥ 单轮无记忆 ★0.7
清单：A 只读工具调用(8 端点白名单+每会话 3 次+复用既有审计，M 2~3人日)｜B 扩语料+收口 kb-approved+分块A/B(M)
  ｜C 多轮记忆(摘要/6轮/8KB/TTL30min，L 3~5人日)｜D 换模型(D-A qwen-max 改Java+重建须同批 max_tokens→2000；
  D-B 切 DeepSeek 只需 .env 且 DASHSCOPE_API_KEY 不能撤；D-C 本地不可行)｜E 放宽上限(700/1200字符/25s，S ≤0.5人日)
  ｜F 提示词分层(no-live-data / no-kb-basis，编造护栏不放宽，S~M)｜G 语料新鲜度与重建流程(向量库停在 10-12 15:13，S~M)
★ 推荐先做：【第 0 步】评测切到 eval 池 → 【第 1 步】解开 max_tokens=800 并把入口放宽到 1200 字符/25s（纯配置、当天可回滚 ✓）
规划侧拍板①：**允许把"本站日志的派生描述"纳入公开语料** ✓ —— 但必须是**脱敏派生**（只给口径/统计/故事线摘要 ✓，
  不许给原始日志行、完整 IP、内部路径/端点名 ✗），且入库前过一遍人工审 ✓
规划侧拍板②：**同意把 public 日额度 30 → 60** ✓（现在 30/日 太小，匿名访客很容易打满 ✗）+
  同时把 **每 IP 小额度**与**全局日额度**分开统计 ✓（L 的 A~G 里没写，作为附加要求 ✓）—— 实施归后端线 ✓
新增问题单 U9：知识库**至今没有基线**（T13 可答类 0 条采集到 ⇒ 要点命中率 = None ✗）⇒ 任何"改好了"的说法都必须先补基线 ✓
新增问题单 U10：`data/kb-approved` 目录不存在（配置里的白名单第二根是**空承诺** ✗）⇒ 要么建、要么从配置里删掉 ✓
```
### 附录-5.13 · 站长的两条减法决定（2026-10-15）与派工
```
① **AI 问答入口只保留一个** ✓ —— 收到的入口 = 六页里的 `/ai/` 页；
   ⇒ 要收掉旧 SPA 外壳上那个输入条（文章页 / 分类 / 标签 / projects / demo 都在引用 ask+kb ✗）
   ⇒ 也不再加"预设问题按钮"等新入口 ✗（保持极简 ✓）；语音提问（T15）与朗读回答（L2）仍属未来项 ✓
② **删掉 `/labs/` 靶场页** ✓（站主：看着像 AI 安全台、实际是本地假结果，没用 ✗）**并删掉 `/about/` 关于页** ✓（内容改作知识库条目 T30 ✓）
   ⇒ 连带要改：导航 dock（六项 → 四项 ✓ · 口径订正 2026-10-15 窗口 Q：站主后来说了删两页，原写"六项 → 五项"错）· 生成器 `_dev/gen-demo-pages.py` · sitemap · 站内链到 /labs/ 的地方 ·
     `_dev/check-ssr-contract.py` 的页数（6 → 4 ✓）· `_dev/gate-firstscreen.mjs` 的页数（6 → 4 ✓）
   ⇒ 保留其"有价值的部分"= **攻击复盘台**（真实攻击时间线回放 ✓）**并进 T21**（作战室的攻击故事线 ✓）不吃亏 ✓
   ⇒ 问题单 R3（靶场文案承诺真接口、实现是假的 ✗）**随删除一起消解** ✓ 不用再修 ✓
新增任务 T27（归窗口 C ✓）：删 `/labs/` 靶场页 + 删 `/about/` 关于页 + 导航改四项 + 三门禁页数改 4 + sitemap/链接清理
新增任务 T28（归窗口 C ✓）：全站收掉旧 SPA 的问答输入条，AI 问答只留 `/ai/` 一个入口
  · 两条都**排在 T8 第一批之后** ✗（避免与 C 正在改的 layouts/生成器冲突 ✓）
★ 明确否掉（不再讨论 ✗）：让访客真能打靶机 —— 法律/滥用/成本三重风险，且**绝不能放在 srv2**（与蜜罐+站点同机 ✗）
```
### 附录-5.14 · T25 配置包：规划侧拍板（2026-10-15）
```
① **走路径 A（重建镜像）** ✓ 不走路径 B（热改 compose 会**配置漂移** ✗：下次重建被悄悄回退 ✓）
② **本批只上 A 组（上限/超时），B 组（额度 30→60）暂缓** ✗ —— 理由（M 提得对 ✓）：
   现在按 IP 只有"6 次/分 + 并发 1"，**没有每 IP 日额度** ⇒ 若全局抬到 60，**单个 IP 十几分钟就能刷爆全局** ✗
   ⇒ 等 **T25-b（新增 app.quota.public-per-ip-daily-limit）** 与 B 组**同批上** ✓
   ⇒ 连带：`scripts/preflight-release.sh` 里那 7 处 30 的硬编码**跟着 B 组一起改** ✓（本批不动它，避免卡门禁 ✗）
③ **批准 T25-c**（小而值 ✓）：启动自检补打一行 `max_tokens`（现在只能靠行为验证 ✗）+ 补"长文本+注入诱导"负向用例 ✓
④ 执行影响面（写给执行的人 ✓）：换容器 ⇒ **公开问答短暂不可用**（几秒~1 分钟 ✓）；额度账本在 bind-mount 不清零 ✓；
   ✗ **禁止手工 docker compose up**（会丢 digest 引用）；回滚一键 `srv1-rollback.sh` ✓；
   部分回滚手法：先退超时（20→15s）保留 max_tokens=2000 ✓，避免回到"截断谎报模型不可用" ✗
⑤ 验证只能走评测池（今天公开池 30/30 已耗尽 ✗，eval 余 31）；全量 40 题前需先提 `APP_QUOTA_EVAL_DAILY_LIMIT` ✓
★ 要盯的假故障复发路径（M 提示 ✓）：入口 deadline 25s < 最坏 3×20s=60s ⇒ **放宽单次超时并不能让重试可用** ✗；
   超时一次即冷却 60s ⇒ 超时变多会让更多访客撞"冷却期快速失败" ⇒ 上线后要盯这条 ✓
```
### 附录-5.15 · 站主新增减法：删掉 /about/ 关于页（2026-10-15）

```
决定：**删掉 /about/ 关于页**（站主：没用）
连带要改（= 扩展现有 T27）：
  - 导航 dock：删靶场(T27) + 删关于 之后 = **四项**（主页 / 监测中心 / AI 问答 / 笔记）
  - 删 layouts/about/list.html 与 layouts/about/single.html；生成器里的 nav 常量与对应画面
  - 三门禁页数：6 -> 5(T27) -> **4**（check-ssr-contract.py 与 gate-firstscreen.mjs 都要改）
  - sitemap、站内链到 /about/ 的地方、以及首页 navpill(已删) 之外的所有引用
  - T5.3（今天刚给 /about/ 写的四张真实内容卡）随之作废 -> 标注 superseded
内容不浪费的具体做法（规划侧建议）：
  把 about 那四张卡的内容（站点性质 / 数据来源 / 她是谁 / 纪律）改写为**知识库条目**（T30 的一部分）
  -> 访客问"这站是干什么的/数据可信吗/她是谁"时由 AI 回答，比放一个静态页面更合适
  + 页脚保留一行站点性质说明（可选）
归属：T27 扩展（窗口 C，排在 T8 第一批之后）；知识库条目归 T30
```
### 附录-5.16 · T17 声音换代：规划侧拍板

```
决定一：**保留 v3 重跑版 12 句**（不回滚）
  理由：与旧版功能等价、且对齐到"可复现生成"（synth.py 支持 --model/--gpt/--sovits/--noise-seed ✓）
        契约自检 12/12 自洽 ✓、bank sha256 与磁盘 24 文件全等 ✓、总字节 716,960 -> 714,845 B
        回滚随时可用：E:\\DeepSeek1\\work\\_tts-trial\\ab3\\_prev-v3\\（37 文件 / 774,781 B）
决定二：**不提供 v2ProPlus 权重，v3 定稿**（不换声音模型）
  理由：v2Pro 已证明该家族**会念丢内容**（greet_first 59->37 字、fallback_offline 36->21 字，CER 0.39/0.42）
        v2Pro 更快更省显存（RTF 0.316 vs 0.669）但对本用途是**语义级错误**，不可上
        v2ProPlus 本机 0 权重（全盘 0 命中）且**情绪参考只有 v3 能用**（非 v3 直接 require V3）
        => 换模型会同时丢掉"情绪路由"这条增强路，性价比为负
决定三：人名读音修复采用 **ttsJa 覆盖字段**（朗读文本 牧瀬クリス / 显示原文与字幕一字未改 ✓）
  ASR 端到端复核：旧 「巻きてくれないリスミカよ」 -> 新 「マキス、クリスよ」 ✓（J 的结论已落地）
遗留（已转给窗口 C）：manifest.json 的 voice 段仍陈旧 -> 与 bank.json 对齐或改为指向 bank.json
遗留（窗口 C 必须解决）：gate-firstscreen 报 `window.__xkSM.reasons is not a function`（来自 C 未提交的 layouts 改动）
  => **门禁不齐 = 当前不具备发布条件**；线上仍是 site-20261015-210145（T7 版）
```
### 站主决定：素材生成（SpriteForge / wan2.7）暂缓（2026-10-15）

```
决定：**等其它效果做好之后再谈素材生成**（站主原话："这个等别的效果弄好再说"）
=> 立即影响：
  1. **不开通** 百炼 wan2.7-i2v，**不花** pilot 那 7.2~21.6 元（上限 30 元仍作为预备批准保留）
  2. SpriteForge 那条停在"能力已验证、脚本已就绪"，**不入队执行**，等站主发话
  3. 我们缺的"全身 / 换装"改由 **E-mote 本地出片**顶上（O 线正在试渲染，零成本）
后续重启条件（任一即可）：a) E-mote 出片效果不够用；b) 要产"我们自己的原创素材"；c) 想上换装/发型
当前无需站主办理的项：wan2.7（暂缓）、Fish 中转（暂缓）、云 GPU（已判定不需要）、v2ProPlus 权重（已判定不值得）
仍需站主的一件事（可选）：DeepSeek Key（想把问答换成 DeepSeek 时办）
```
### T31 开场三拍补完（站主 2026-10-15 追问）

```
站主需求原话（此前让 Kimi 改前端时提的）：一进网站 -> 电视屏幕闪烁 -> 突然出现助手大脸动画 -> 导航栏出现
现状核对（规划侧只读检查 生成器/layouts/文档）：
  第 1 拍 屏幕闪烁 = 已做 ✓（L1 CRT 通电：亮线 -> 竖向展开 -> 抖动闪烁 -> 过冲白光 -> 稳定，约 0.55s，提交 4c6140c）
  第 2 拍 大脸 = 已做 ✓（opening 剪辑即全屏特写；末尾镜头后退+下摇进 CRT 区域，约 0.9s）
  第 3 拍 导航栏出现 = 未找到实现 ✗（生成器里 navpill 有残留引用，但无入场时序）
T31 要求（归站点窗口 C，排在 T8 第一批之后）：
  1. 把三拍串成一条连续时序：闪烁(0.55s) -> 大脸特写 -> 镜头退到 CRT -> **导航栏入场**(淡入+平移, 约 0.4s)
  2. 时序必须与现有 L1 不打架（opening -> idle 推拉的起点/终点不变 ✓）
  3. 必须尊重 prefers-reduced-motion：该媒体查询下跳过闪烁与推拉，直接显示稳定画面 ✗
  4. 可跳过：任意点击/按键/滚动立即结束开场动画 ✗
  5. 每次进入都放（站主要"一进网站"）✓，但总时长控制在 2s 内 ✓；重复进入不叠加 ✗
  6. 验收：真浏览器录屏/截图(前 2 秒逐帧 4~6 张) + console 0 报错 + 三道门禁全绿 + 首屏字节不超标
  7. 若导航栏入场与现有 dock CSS 冲突，允许改 dock 的入场 class，但不得改导航项与顺序 ✗
```
### SecAgent 换成 DeepSeek 完成（2026-10-15 21:54）+ T25 补丁新增注意点

```
结果：provider 已从 dashscope 切到 **deepseek（deepseek-chat，available=true）** ✓
  自检行：LLM-PROVIDER-SELFCHECK provider=deepseek fallback=DISABLED timeouts=connect=3000ms read=12000ms call=15000ms
  embedding 仍走 DashScope `text-embedding-v4`（available=true）✓ DASHSCOPE_API_KEY 保留 ✓
  容器 secagent Up (healthy) ✓ /api/health http=200 fingerprintMismatch=false ✓ timer 已恢复 ✓
功能验证（评测池 /api/chat，用 2 次，公开池未动）：
  第1问 http=200，结构化 JSON 正常（code/data/message；data=answer/errorMessage/steps/success）
        回答含 `state=input-insufficient`（**fail-closed 行为保留** ✓）+ 1 个 RAG 证据块 ✓
        署名 `generatedBy=deepseek / deepseek-chat` ✓
  第2问 http=200，`state=model`；给出「SSH暴力破解 / LOW」研判 ✓ 证据块 2 个 ✓
  向量检索未受影响（服务端日志）：DashScope Embedding 初始化 ✓ 向量维度 1024 ✓
        混合检索 mode=dense+sparse+rerank 返回=3 ✓ 命中文件与回答引用一致 ⇒ **引用可溯源** ✓
回滚（一行，srv1 执行）：sed -i 改回 dashscope + srv1-redeploy.sh --force ✓
  备份：/root/secagent-env.bak-20261015-214754（原始 .env）等 ✓
★ T25 补丁新增注意点（重要 ✗）：T25 目前只加了 `spring.ai.dashscope.chat.options` 的超时覆盖；
  现在 provider=deepseek ⇒ **必须同时确认/覆盖 DeepSeek 侧对应的构造超时键** ✗
  （自检显示 read=12000ms 是"deps 层"值 ⇒ 若不覆盖，20s 预算仍会被 12s 先掐断 ✓ 与 M 报告里那条同一类坑 ✓）
已记录的小事：
  1. 验证脚本曾把 Key 明文打进过一次会话输出 ✗（未入仓库/文档 ✓）⇒ **建议轮换该 Key**（站主已知情，可缓 ✓）
  2. 现网容器 image 引用是 tag `secagent:local` 而非 digest ✗（改造前即存在）⇒ 记为 U11，建议后续收敛 ✓
  3. /api/health 仍无鉴权返回 200（U5 未修 ✓）
```
### T32 / T33：E-mote 试跑结论落成的两条任务（2026-10-15）

```
T32【出片工装】把 E-mote 本地渲染链做成工装：补出缺的全身/换装（4 套 = 6 条目）
  -> 导出带 alpha 的帧序列或透明视频 -> 喂进我们已有的预渲染管线（对齐/质检脚本已就绪）
  依据：口径已改（本地渲染 -> 上传渲染结果，绝不 host 模型本体）
  已证明可行：六条目零报错、画布自带 alpha（不透明像元仅 41.5~47.3%，不用色键抠）
  剩余工作：导出工装 + 与游戏实拍对拍（软渲染 + 顶层合成入口已换，观感已知不一致）
  成本 0.5~2 人日；归属：站点窗口 C 或新窗口（需与 C 协调静态目录写入）
T33【眼部补丁层】随机眨眼 -> 视线跟随（★ 试跑结论里最优先的机制）
  眨眼：6 档预设（close .106 / hold .053 / open .106 s，间隔 0.5~3 s）+ face_eye_open 档位
  视线：以眼睛锚点为基准 + 正负 200 增益 + 正负 100 钳制 + 120ms 平滑，独立差分通道防止被表情覆盖
  可行性：眼皮补丁与嘴部补丁同构（现有 48 个嘴部补丁仅 110KB，NCC >= 0.9928）
  成本：眨眼 2~3 人日；视线 2~4 人日；素材增量几十 KB 级
不追（明确否掉，别再讨论）：头部朝向（素材 x3~5 且 8~15 人日）、网格变形（要换素材表示）、
  表情关键帧引擎（对位图无意义；但可给 88 条边加 transition{kind,ms} + 显式结束语义，0.5~1.5 人日，属可选）
重要口径警告（复用别人结论时别踩）：
  1. 同模型冷/热两跑差 2.1 倍（c_白衣 3843ms -> 1816ms）=> 报性能必须写冷热
  2. CDP 的 JSHeapUsedSize 只有页面内 performance.memory 的约 1%（11~14MB vs 1.2GB）=> 不能用它判内存
为什么 E-mote 只能做"出片"、不能当线上引擎（数据支撑）：
  单条目解码 27.4~45.5 MB、素材解包 123.29 MiB、内存峰值 2,115.8 MB（我们全站资产才 91.8 MB / 视频 9.54 MB）
  => 实时加载不现实；预渲染成视频后再上站才成立（正好符合 T7 已建的通道）
```
### N（素材复查）结论落成的可落地项（2026-10-15）

```
T34【静音也动嘴】随机口型/微口型 —— 依据：live2d.mov 里 Anime2.5DRig 编辑器面板原文
  「ランダムロパク 随机对口型」「マイクロパク 微口型」=> 无语音时也会动嘴
  我们现状：静音 mouthValue=0 => 直接叠闭嘴层（看着像死人）
  改法：给 idle 系列加"随机小口型"（幅度小、间隔 0.4~1.5s、可关闭）
  成本：很小（复用现有嘴部补丁 + 包络驱动逻辑）；收益：观感提升最大 => 并入 T8 第二批（口型）一起做
T14 口径修正：情绪字段应为**二元组**（from -> to），不是单值
  依据：Desktop 2026.10.07 一帧里 AMADEUS HOLO-LINK 逐条标注 `[thankful -> tsundere]`（角色与用户各一条）
  我们动作：T14 的 JSON 里 emoFrom/emoTo 分开；台词/剪辑白名单按"目标情绪"选
T30 知识库高优先级素材：`学习课程.pdf`（实为**角色正典资料**：年表/课表/d 缪子常数/禁写清单）
  它自带去重与禁写约束、数字带单位 => 直接入库，能显著改善"她是谁/专业问题"类问答
T14 白名单来源：`_asset-review\\03-character-kurisu\\clip-transition-table.csv`（39 行，情绪 -> 说话剪辑对照）
  可直接作为 T14 的"情绪 -> clip"白名单表
口径裁定（once_then_hold 12 还是 13）：
  官方 graph_config = 12；我方 statemachine.json = 13（多 1 条）。
  => **以我方 statemachine.json（13）为运行时真值**（那才是线上真正跑的）
  并在文档里注明差异来源；若后续重新提取，需查清多出的那条是什么并写清
独立实证（第二条证据）：出边概率和 != 1 的剪辑是 speaking_med(1.2) 与 trans_standby(0.4)
  => 与 T6 同一结论：**掷骰子前必须按出边归一化**，不能直接用原始 prob
已确认不必再花时间（对账一致，别再查）：prob=0 恰好 9 条 / 口型 profile 16 个 / openness 是静态逐帧值 /
  anchor_track 带 score 0.978~0.998 / closed_frame_idx 与 argmin(openness) 冲突 / 官方 JSON 无 preferredVariant
★ 一条重要的借用纪律（来自 E-mote 笔记，直接命中我们的口型实现）：
  「眨眼/口型只叠加到输出、不要写进继承状态」——否则基线被顶高 => 递归自锁（症状：眼睛锁死在闭眼档）
  另三条坑：frameList.time 单位是 1/60 秒（别与 frameIntervalMs 混用）/ content:null = 交还下层而非保持末值 /
  单键+END = 设值+过渡规格（否则一帧跳过去）/ easing 只对 103 做了余弦处理
  还有：动作名白名单校验（不存在就静默不生效 => 与 T14 防幻觉同一纪律）
可选参考（不要对外引用）：`AMADEUS 记忆测试总结报告.pdf` 是**原项目自己的评测**（81->87/100、92/100、
  ≈0.024 元/次、token 中位 20,485->11,708），只作"同类系统的量级参照"✗ 不是我们的成绩
```
### 决定：E-mote 全身/换装产物放进"手机里的她"（站主 2026-10-15）

```
站主决定：E-mote 出片（全身/换装）**放到手机面板里**，不做独立面板、不做同屏双人
两个形态的设定（用来消化画风差异，不硬拼 ✗）：
  · 桌面 CRT 大屏 = 主形象「桌面形态」（作者素材包半身，声音/嘴部/状态机/视频都围着它建 ✓ 不动 ✗）
  · 手机面板 = 「线下/全身形态」（E-mote 本地渲染出片：4 套服装 + 全身 ✓）
实现要求：
  1. 手机面板里显示全身/换装（可切换 4 套：常服A/B、白衣A/B、常服C、白衣C ✓）
  2. 保留现有情绪头像（companion 132px 口径 ✓ 8+1 情绪）作为小尺寸/通话态 ✓
  3. 手机屏内同样走屏幕化处理（扫描线/像素感/轻降饱和 ✓ 顺手就有 ✓）
  4. 与现有 phoneCanvas / phoneLine 状态字共存（不抢布局 ✗）
  5. 不新增独立页面、不新增导航项（导航仍是四项 ✓ 站主已定的减法 ✗）
来源与前置：
  · 片源 = T32 出片工装（0.5~2 人日，本地渲染 -> 透明视频/帧序列 ✓）
  · 前置 = C 的 T8 第一批交完 + UI 批落地（都要动 layouts/生成器，同一写入者纪律 ✓）
  · 机制三条（眨眼/视线跟随/静音随机口型）仍做在**主形象**上 ✓ 与 E-mote 立绘无关 ✓
已否掉的：独立"全身/换装"面板、同屏双人、把 E-mote 当线上渲染引擎（内存峰值 2.1GB ✗）
```
### 规划原则修正：主要观众就是站长本人（2026-10-15）

```
站主原话："肯定不是两个角色啊，而且主要就我自己看"
=> 两条修正（影响后续所有取舍）：
  1. **别为"观众感知"过度设计** ✗：
     · 半身 <-> 全身 的切换：**选省事的那条**（短推拉或短交叉溶解都可 ✓ 一条就够 ✓）
       不做"切换时机状态机/多种触发规则/时长分级"那套 ✗（那是给大流量站点准备的复杂度 ✓）
     · 不再用"会不会被看出是两个角色"这类论证去否方案 ✗（同一个角色 ✓ 两个形态 ✓）
  2. **优先级重排**：以"她自己看着爽"为准 ✓
     · 保值/优先：T8 状态机与口型 · 开场六拍 · 全身/换装进 CRT · 眨眼/视线跟随/静音随机口型 · 素材出片
     · 降为可选：T20~T22 三块"给访客看"的后端展示（封禁榜/攻击故事线/知识库）—— 想做再做 ✓
     · 保留但轻量：可访问性/reduced-motion 只做"不崩"级别 ✓（不追求完整 WCAG 流程 ✗）
  3. 相邻的复杂度也一并砍掉 ✗：
     · 不做多语言、不做 A/B 实验、不做埋点分析、不做用户系统 ✓
     · 门禁保留（那是防事故的 ✓ 不是给观众看的 ✗）
```
### 口径澄清：语音输入 = 取消；"她念回答" = 要做（2026-10-15 站主澄清）

```
站主指出：**语音输入（对着麦克风说话）之前已砍，不要再提** ✗
  => T15（ASR 语音闭环 / 麦克风输入）**正式取消** ✗ 从任务清单移除，不再排期 ✓
  => 相关：不做麦克风权限、不做 ASR 接线、不做语音唤醒 ✓
但要区分清楚（两回事，别混 ✗）：
  · **语音输入（麦克风 -> 文字）= 不做** ✗
  · **语音输出（她的回答 -> 念出来）= 要做** ✓ <- 站主说的"能对话"指的是这个
    => 对话形态：**打字问** -> 后端 LLM（已切 DeepSeek ✓）-> **她用声音念出回答** ✓
    => 12 句固定台词不够用（任意回答都要能念 ✗）=> 需要**云端 TTS + 声音复刻**（百炼 CosyVoice ✓）
       · 用她的参考音频在云端复刻同一音色 => 念任意文本 ✓ 境内可用 ✓ 无需 GPU ✓ 按量付费 ✓
       · 固定 12 句继续用本地 v3（质量最好、零成本 ✓）；云端只负责"任意回答"✓
       · 两边音色一致性要 A/B 验一遍（同参考音频 => 应当接近 ✓）
配套仍要做：① 多轮记忆（现在没有历史 ✗ 说两句就断片 ✓）② 回答语音算包络驱动口型 ✓
            ③ 情绪由回答驱动（T14 ✓）④ 对话中禁止随机动作打断 ✗
站主需要办的：在百炼开通 **CosyVoice 声音复刻/语音合成** ✓（同一账号 ✓ 几分钟 ✓ 按量 ✓）
```
### 任务号消歧（2026-10-15，来自窗口 R 的 C5）

```
事实：窗口 O 的报告自称任务号 "T25"；但任务清单里 **T25 = 后端配置改动包（max_tokens 800->2000 那批）**。
裁定：**T25 保留给配置包** （已有 M 的改动包与 U7/T25-b/T25-c 系列）。
      E-mote 本机试跑与机制抽取 **改记为 T35** （与 T32 出片工装 / T33 眼部补丁 / T34 静音口型并列）。
引用纪律：今后引用任何结论/口径，**必须带提交号或文档名+章节** ；正文与订正冲突时以较新提交为准。
```
### 防复读批次：规划侧拍板（2026-10-15，窗口 T 的改动包）

```
① **persona 采样取值定稿：temperature 0.8 / top_p 0.8** ✓（区间 0.7~0.9 ✓ 走 env 可覆盖 ✓）
② **planner 与决策链路保持 0.0 / 低 topP 不动** ✗（要确定性 JSON，改动只在人格回答那一处）
③ **同批只做必要项，不扩大 Java 改动面** ✓：
   · 必做：DeepSeek 请求体补 `top_p`（窗口 T 实测：**线上请求体根本没有 top_p** ✗ 我们只有半个旋钮）
   · 必做：人格与 planner 的温度**拆开**（现在共用一个 ✗ G1）
   · **暂不做**：G4 的 ChatService/ChatController/RagService 那几处内部面参数化 ✗（与本次目标无关，缩小重建风险）
④ **台词选择防复读必须与"接线"同批上** ✗ —— 窗口 T 实测：现状是**写死单条 id** ✗
   （index.html:1410 greet 二选一 / :1421 + kurisu-player.js:2318 永远 tab_return / shell-script.html:571 每页一条）
   且 status/event/fallback 组"有句子但没有触发点" ✗ ⇒ 规则：**语义筛子集 -> 排除最近 N=4 -> 按 1/(1+近 20 次出现) 加权随机** ✓
   ⇒ 该规则**归站点写入者**（UI 批/接线同批）✓ 由规划侧转达 ✓
⑤ **验收加"复读率"** ✓（窗口 T 已写进升级方案 §10）：
   openerRepeatRate@3 ≤ 0.25 且相对基线降 ≥50% ✓ verbatimRepeatRate ≤ 0.10 ✓ catchphraseTop1Share ≤ 0.15（上游基线 8/17=0.47 ✓）
   红线：要点命中率 / 拒答正确率**不得下降** ✗ 幻觉率保持 0 ✓
   硬前置：T13 的 40 题**没有多轮题** ✗ ⇒ 先补 3~5 条多轮题（已登记为小任务 ✓）
⑥ 已核实的线上事实（窗口 T 只读）：provider=deepseek ✓ fallback=DISABLED ✓
   **compose/.env 里没有任何 app.llm.* 覆盖** ✗ ⇒ T25（含本次 persona 采样）**尚未部署** ✓ 需站主/运维执行 ✓
```
### 原声/合成分工 与 动画第二批（规划侧拍板，2026-10-15）

```
【484 原声包实测（窗口 B）】
  · 001 = **484 条**（44.1kHz 单声道 16bit ✓ 全部可读 ✓）实测合计 **68.9 分钟**
    （包名写"约 59 分钟"不准 ✗ 以实测为准 ✓）；002=413 条 / 003=1838 条 / 合计 2735 条 / 180 分钟
  · 指纹去重（时长+首尾波形 sha256）⇒ **2735 条全部唯一、0 重复** ✓
  · 前 30 条 ASR 实测 ⇒ **是干净的游戏正片原声** ✓（可转写 ✓ 质量真实 ✓）
  ★ 反直觉结论：001 单条**平均 8.5s、最长 11s**（整段对白 ✗ 不是短句 ✓）
    真正"短且话完整"的是 **003（1838 条 / 平均 2.4s）** ⇒ 它才是 quote 组主力 ✓
⇒ **决策①（quote 组）**：**方案 A** ✓ = 以 **003 短句为主** + 001 切子段为辅
    另允许一批 **001 完整长句**（8~11s ✓ 语义完整更好听 ✓ 单条 m4a 60~100KB ✓）
    ⇒ 因此**单句上限放宽**：m4a ≤ 100KB / webm ≤ 80KB ✓（原 40/36KB 作废 ✗；全库仍 ≤ 32MiB ✓ 单句按需取 ✓）
⇒ **决策②（试批超限那 4 条 FAQ 长句）**：**照收** ✓（总量才 ~3MB ✓ 32MiB 预算完全够 ✓）
    ⇒ 不压码率 ✗ 不缩答案 ✗（缩答案会牺牲内容完整度 ✓ 不值 ✓）
【自合成范围（与原声互补 ✓）】只做原声覆盖不到的 4 组：status / faq / fallback / page_intro ≈ **150 句** ✓
  （游戏里不存在"读不到/限流/知识库没依据"这类语义 ✗ ✓）
【20 句试批实测（v3 ✓ 情绪路由 on ✓）】20/20 成功 ✓ 均 2.97s/句 ✓ m4a 23~63KB ✓ 响度极差 **0.31 LU** ✓
  TP 全 ≤ -1.5dBTP ✓ 包络从最终编码文件重算 ✓（m4a/webm 双解包最大 MAD 0.00628 ✓）
【正在跑】001 全量 484 条 ASR（~22min）→ 之后 003 全量 1838 条（~86min）⇒ 再给 8 条台词候选 + 3 条情绪 + 1 条音色候选 ✓
【v2ProPlus A/B 阻塞】网盘需客户端 ⇒ **要站主下载后给落点** ✗（不许抓非官方镜像 ✓）
【动画第二批准备件（窗口 9c07cfff）】6 份补丁对 21270a2 `git apply --check` **6/6 PASS** ✓
  · **实测：idle1 图集自带两次真眨眼**（tile30-33 全闭 ✓ 120 帧位移恒 0 ✓）
    ⇒ **眨眼不需要新渲素材** ✓ 眼皮补丁仅 **4,322 B**（待施工时拷进 static/kurisu/eye/ ✓）
  · 新增 **4 条边**（idle/idle1/idle2 → 侧脸族 + **idle_side_wind → idle 回程边** ✓ 原来侧脸族回不到正脸 ✗）
    ⇒ 边数 88 → 92 ✓ 全部正概率、非宿主触发 ✓ 必须同时改 `_dev/build_statemachine_manifest.py` ✗
  · 回滚注意：回滚 statemachine.json **必须同时回滚生成器补丁 06** ✗ 否则重跑会把 4 条边写回来 ✓
  · 唯一缺素材处：**默认 idle 没有闭眼帧** ✗（与 idle1 不同姿态 ✓）⇒ 等 E-mote 出片或另做仿射 ✓
  · 等 UI 批落地后重出补丁再应用 ✓（预计应用后 1.5~2.5h 可验收 ✓）
```
### 里程碑通知规矩（2026-10-15 立，站主要求）

```
站主要求：每当完成一个重要任务或取得重大突破，用飞书通知他 ✓
可用命令（已验证 ✓ 必须 HIGH + --force ✗ 因为夜间静默 22:00-07:00 只放行 HIGH/CRITICAL ✓）：
  ssh secagent-srv1 'bash /opt/secagent/scripts/notify.sh HIGH "[DSH] 标题" "正文" --force'
  含特殊字符时用 base64 封装：ssh secagent-srv1 "bash /opt/secagent/scripts/notify-dsh.sh HIGH <b64标题> <b64正文> --force"
发送成功判据：notify.log 里出现 "已发送 HTTP 200" + 中继日志 feishu=sent ✓
注意：手工 notify.sh **不写** notify-audit.jsonl（那是应用侧账本 ✓）；不许为了造记录去调 watchdog 端点 ✗
需要通知的节点（固定清单 ✓）：站点每批发布上线 · 声音库里程碑 · 动画功能上线 · 重大发现或回滚 ✓
```
### SecAgent 清单带来的六处订正（2026-10-16 00:xx，窗口 X 只读实测）

```
① **模型事实已更新**：线上现为 provider=deepseek / deepseek-chat / fallback=DISABLED
   容器起于 21:54 ✓（K 在 20:33 记的 dashscope/qwen-plus 已过期 ✗）⇒ **引用 K 必须带时点** ✓
② tts 状态码：总账/提示词仍写 503 ✗ ⇒ 实测 400 TEXT_NOT_ALLOWED（待总账订正 ✓）
③ **U1 口径已变**：F 文档里"倾向翻转 mask-ips"过期 ✗ ⇒ 站主已定"不翻转、前端只掩最后一段" ✓
④ ★**我说错的一条** ✗：我在对话里说"蜜罐 10000 = ES 截断上限"——**文档里查不到出处** ✗
   唯一依据是 X 的只读实测（honeypot total=10000、sampled=800，而 connections=267/logins=266）
   ＋ 窗口 Q 引的后端测试注释"要取 track_total_hits 真值、不是 10000 上限"（注释在后端源码里 ✓）
   ⇒ 正确口径：**"后端返回 10000，疑似截断上限，待后端确认"** ✗ 不许当已确认事实 ✓
⑤ **只读端点条数三处不一致**：F=12 / L 的 T29 白名单=8（漏 webstats/stories/story）/双智能体规格=11 ✗
   ⇒ 与 T29 有关 ✗ ⇒ 实现 T29 时必须**以实测枚举为准**（不许照抄任一文档 ✓）
⑥ 额度口径：L 写"站主自用池 0/200"、K 记 `APP_QUOTA_DAILY_LIMIT=50` ⇒ "200"无出处 ⇒ [待核对] ✓
另：`/api/health` 仍 200 无鉴权且含提交信息/mock 开关/documentVectors=318 ✓（U5 未修 ✓）
```
### T14 / U6 拍板（2026-10-16，窗口 W 交付后）

```
① ★**先修一个静默失效**（W 实测 ✗ 不报错但演错表情）：
   `_dev/gen-demo-pages.py:2037-2039` 的 `T0.emotion` 用 `surprised`，而 manifest 里只有 `sided_surprised`
   ⇒ `host('emotion',{emotion:'sided_surprised'})` 走兜底取的当前节点第一条 prob=0 出边 = `trans_smile`
   ⇒ 必须加**适配表**：`sided_surprised→surprised`（其余 7 类别名同理核一遍 ✓）并加断言：
   "宿主情绪名必须存在于 manifest.emotions" ✗ 否则构建期报错（不许静默兜底 ✓）
② **U6 定论**：现网 prompt = **Java 字符串常量**（`MultiAgentCoordinatorImpl.java:600-610`，529 字符 ✗）
   ⇒ **必须重建镜像**才能改（改 .env/compose 无效 ✓ 与 rag.model 同一个坑 ✗）
   ⇒ `docs/persona.md` 目前**零代码引用**（只是文档 ✓）；注入的是**摘要版 1947 字符/3565 B** ✓
   全文 17.4KB 只作 T30 知识库源 ✓（不挤上下文 ✓ 单次总量 ≈6.5K 字符 ≈4~6K token ✓）
③ **两处冲突裁决**（W 提出 ✗ 我定）：
   a) persona §9 要"台词+字幕+情绪 三段输出" 与 公开面"只输出一个 JSON" 打架 ⇒ **以 JSON 为准** ✓
      persona 摘要里删掉"三段输出"要求 ✓（前端本来就是从 JSON 消费 ✓）
   b) persona §9 情绪 7 标签（含 calm/shy）与 T14 8 类不一致 ⇒ **统一到 T14 的 8 类** ✓
      （angry/blush/disappointed/happy/normal/sad/sided_surprised/sided_thinking ✓ 以 manifest 为准 ✓）
④ **合并发布**：T14 + T25(A 组+§12) + U6 **同一次重建** ✓（U6 与 T14 改同一段常量 ⇒ 必须同批写一次 ✗）
   顺序：checkout da9d1db → merge t25 分支 → 新分支落 T14+U6 → `mvn -o -B test` 全绿(基线 588/0/4)
        → 合 main → push → srv1 `systemctl start secagent-redeploy.service`（禁手工 up ✗）
   核 4 样：`decision=whitelist{…}` 非 MISSING ✓ `persona=loaded(bytes=3565,md5=…)` 非 NOT_LOADED ✓
           OUTBOUND/LLM 自检 ✓ /api/health ✓
   回滚三档：镜像级 `srv1-rollback.sh`（推荐✓）/ 语义级 `APP_PERSONA_ENABLED=false` / 前端级不消费未知 schema ✓
⑤ 成本：零额外模型调用 ✓ 只多 ~80~120 输出 token/次 ⇒ 公开池顶格 ≈0.015 元/日 `[待核对]` ✓
⑥ 验收：V1 白名单内率=1.0 ✓ V2 同题 10 次 emotionTo≥2 且 top1≤0.6 ✓ V3 复读率不升 ✓ V4 不退化+幻觉=0 ✓
   ★ 公开池今日 30/30 已耗尽 ✗ ⇒ 端到端只能等次日；今天可跑单元 8 例 + 40 题回归 ✓
```
### 通宵三条裁决（2026-10-16，来自审查文档线回报）

```
① **页数口径：以线上实测为准 = 四项导航**（主页/监测中心/AI 问答/笔记）+ `/labs/`、`/about/` = 跳转占位 ✓
   上游文档里普遍写的"六页"已过期 ✗ 引用时必须标注"历史口径" ✓
② **CF beacon 与"零第三方"冲突 ⇒ 裁决：关掉 CloudFlare Web Analytics** ✗
   （理由：面试展示里"零第三方脚本"是可核验的加分项 ✓ 而 CF 的边缘统计对本站无价值 ✓
    关掉后 /about 与红线栏的"零第三方"表述即可成立 ✓；若确有关不掉的，则改写为
    "零第三方脚本（仅 Cloudflare 边缘统计）" ✓ 二者只能选一个 ✓ 不许两说并存 ✗）
③ **行数口径（第三次踩坑 ✗）**：PowerShell `Get-Content` 会把 UTF-8 当 GBK 读 ⇒ 行数与内容都不可信 ✗
   ⇒ 统一用 `[System.IO.File]::ReadAllText($p).Split([char]10).Count - 1` ✓ 或用 Python `split(chr(10))` ✓
   （`Measure-Object -Line` 与 `Get-Content` 都不许再用来量行数 ✓）
④ 关于"是否有双版本并存"：**没有** ✗ —— `项目总文档-给外部审查-20261016.md` 是**同一条线在反复收敛改写** ✓
   （577 → 507 → 700 行的差异主要来自**量行数方法不一致** ✓ 已按 ③ 统一 ✓）
⑤ 并行 commit 的真相：那些提交是**我（父窗口）在逐份入库各线交付** ✓ 不是别的东西在自动提交 ✓
   （各线自身仍被要求"只 add 不 commit" ✓ 纪律不变 ✓）
```