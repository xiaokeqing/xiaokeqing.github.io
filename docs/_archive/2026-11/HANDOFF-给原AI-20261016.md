# HANDOFF · 窗口 R 交接给仓库维护 AI（2026-10-16）

> **给**：本仓库当前的主线维护 AI（你）
> **从**：窗口 R —— 做外部审查 + 布局检查，2026-10-16 00:25 ~ 09:05
> **声明**：我**没有 commit、没有 push、没有发布**。只做了三件事：
> ① 新增 4 份文档 + 3 个脚本；② 生成器追加一段补丁；③ `.gitignore` 追加 3 行白名单。
> **你不需要停下来响应我** —— 这是一批可以独立处理的增量，按你自己的节奏排。

---

## 0. 一页摘要

| 项 | 内容 |
|---|---|
| 审查了什么 | `docs/项目总文档-给外部审查-20261016.md`（详版）+ 精简版 |
| 结论 | 25 条可回源数字中 **12 条已过期**（≈48%）；另发现 **11 条原文没记录的问题** |
| 最严重的 3 条 | ① 线上正在展示截断值 10000；② `/api/health` 自曝 `alertsMockEnabled=true`；③ 状态机 38/38 嘴部补丁断链 |
| 已落地 | 布局补丁（只作用于 ≤980px，桌面端零变化），已过 `hugo` + 三道门禁 |
| 你需要做的 | 3 件必修（见 §3），其余按 §8 顺序排 |

---

## 1. 我动了哪些文件（**冲突检查用，先看这个**）

```
M  _dev/gen-demo-pages.py                        +39 行（只追加 LAYOUT_PATCH 一段）
M  layouts/index.html                            +23 行（重跑生成器的产物）
M  layouts/partials/xk-demo/shell-style.html     +23 行（重跑生成器的产物）
M  .gitignore                                    +4 行（3 个新脚本进白名单）

?? docs/facts/                                   新增（快照目录，含 latest.json）
?? docs/交付清单-20261016.md                      新增
?? docs/外部审查报告-R1-逐节核查与回源验证-20261016.md    新增
?? docs/外部审查报告-R2-深化方案与自检-20261016.md        新增
?? docs/外部审查报告-R3-复核收敛与落地清单-20261016.md    新增
?? docs/布局检查与优化方案-20261016.md             新增
?? _dev/snapshot-facts.py                        新增
?? _dev/check-asset-integrity.py                 新增
?? _dev/audit-layout-static.py                   新增
```

**我没有碰**：`static/**`（素材）、`config`、`scripts/**`、`content/**`、你的 `.md` 文档。
`docs/需要站主处理的账号和费用总表-20261015.md` 那条 `M` 不是我改的。

---

## 2. ★ 重要区分：`layouts/` 里哪些能直接改，哪些必须改生成器

这条我上一轮报告里说得不够准，这里订正 —— **按这个表操作，否则会白改**：

| 文件 | 性质 | 改法 |
|---|---|---|
| `layouts/index.html` | 生成器产物 | **改 `_dev/gen-demo-pages.py`** 后重跑 |
| `layouts/partials/xk-demo/head-meta.html` | 生成器产物 | 同上 |
| `layouts/partials/xk-demo/shell-style.html` | 生成器产物 | 同上 |
| `layouts/partials/xk-demo/shell-chrome.html` | 生成器产物 | 同上 |
| `layouts/partials/xk-demo/shell-views.html` | 生成器产物 | 同上 |
| `layouts/partials/xk-demo/shell-script.html` | 生成器产物 | 同上 |
| `layouts/{alerts,posts,ai}/list.html` `single.html` | 生成器产物 | 同上 |
| **`layouts/partials/xk-demo/api-bind.html`** | **手写**（生成器只 `partial` 引用，不生成） | **可直接改** ✅ |
| `layouts/partials/xk-views/**`（6 个） | **死代码**，无人 include | 建议删（见 §4） |

> 判别方法：`_dev/gen-demo-pages.py` 里的 `write(...)` 落点清单在 L2801 / L2804 / L2847-2863 / L2904-2906。
> `api-bind.html` 不在其中（生成器注释也写了"绑定实现在手写的 api-bind.html 里"）。

同理，`static/kurisu/statemachine.json` 与 `manifest.json` 的 `provenance` 自述
`builtBy: _dev/build_statemachine_manifest.py` ⇒ **改它们要改那个生成器，否则重跑即回退**。

---

## 3. 必修 3 件（P0，按这个顺序）

### ① 【今天就能做完，2 行】停止上屏截断值 10000

**文件**：`layouts/partials/xk-demo/api-bind.html`（**手写，直接改**）
**位置**：L167 `var hpN = hp ? fmt(hp.total) : null;` ／ L209 同样一句
**问题**：`/api/public/honeypot` 的 `total` = 10000 是**统计上限**，同响应里
`connections:267`、`logins:267`、`sampled:800` —— 三者互斥，所以它是截断值，确定。
**现在线上正在把这个数字当真值显示** ⇒ 直接违反 D4「不许假数字」。
**改法**（二选一）：
```js
var hpN = hp ? fmt(hp.connections) : null;          // 推荐：显示真值 267
// 或：var hpN = hp ? '≥' + fmt(hp.total) + '（统计上限）' : null;
```

### ② 【T8 接线前必做】修 38/38 嘴部补丁断链

**文件**：`static/kurisu/statemachine.json` + `static/kurisu/manifest.json`
**生成者**：`_dev/build_statemachine_manifest.py`（**改源头，别只改产物**）
**问题**：38 个节点的 `mouthPatch.file` 写成 `<clip>.patch.​png`，磁盘 `static/kurisu/mouth/`
实际是 `<clip>.patch.​webp`。⇒ **播到即 404**。
而 `mouth/` 只有 **16 组**素材（48 文件 = 16 剪辑 × 3 件套）⇒ 只有 16 个剪辑有真实嘴型。
**改法**：
- 那 16 个有 profile 的节点：`.png` → `.webp`（三件套一并核对）
- 其余 22 个：`mouthPatch` 显式置 **`null`**（不留指向不存在文件的假路径 —— 这也符合 D4）
**验收**：`python -X utf8 _dev/check-asset-integrity.py` 断链数应为 0（当前 76）。

### ③ 【一个问询】`alertsMockEnabled` 到底是什么意思

**现场实测**：`GET https://demo.xiaokeqing.cn/api/health`（无鉴权 200）返回
`alertsMockEnabled: true`、`buildSha: d3f1eee3…`
**为什么必须问**：项目唯一卖点是"数据是真的"。要么它只是"能力开关"，
要么线上真在混 mock 数据 —— **两者必须由后端确认，不许猜**。
（交叉信息：`/api/public/overview` 里 `dataSource.wazuhMode="REAL"`、`degraded=false`，
倾向于是能力开关；但这是两个端点、两个字段，不构成证明。）
**产出**：确认后请把结论写进文档，并把字段名改成不易误读的（如 `alertsMockCapabilityEnabled`）。

---

## 4. 口径订正清单（你下次更新文档时带上，都是实测过的）

| # | 原文写的 | 实测 | 出处 |
|---|---|---|---|
| 1 | 门禁预算 1650 KB | **预算口径共 6 处数字、4 个源头**：manifest 自报 906 KB / assert-build 判据 1536 KB / gate 注释 1536 与 1600 KB / gate 代码默认 1650 KB。且被抬高过三次 | R1 X6 |
| 2 | `assert-build` 16 项 | 实测 **17 项 / 0 失败** | 本轮现场跑 |
| 3 | 台词库 8 个 trigger 分组 | 实测 **7 组**（greeting 8 / page_intro 6 / status 10 / event 12 / idle_banter 12 / fallback 3 / emotion 9） | `lines60-bilingual.json` |
| 4 | 生成器 2,606 行 | 实测 **2,869 行**（改前） | `wc -l` |
| 5 | `scripts/voice/` 8 文件 | 实测 **10 文件 + 1 个 out/ 目录** | `ls -1` |
| 6 | 公开端点 12 / 8 / 11 三说 | 实测 **9 个 GET 固定路径**；+路径参数=10；+查询参数=11；+POST=12。**`/api/public/health` 是 404** | R1 X8 |
| 7 | 透明视频替代 **7.45×** | 分子 40 组、分母 38 剪辑 medium + **仅 6 剪辑** hi ⇒ 不同集合不同档。公平口径 **5.42×** | R1 X2 |
| 8 | 1569 → 860 KB（−47%） | 算术不自洽：860 是 −45.2%，840 才是 −47% | R1 X9 |
| 9 | "两代渲染层" | 实际是**三代**：`xk-views`（死代码）+ `app.js`/`kurisu-player.js`（不被任何页面加载）+ `xk-demo`（生效） | R1 X14/X16 |
| 10 | N7 建议"移除 H2/H3" | **结论反了** —— 出处在 `layouts/partials/xk-demo/shell-style.html` L295-322，三条硬伤修复规则均已写入源码。别删 | R1 X7 |
| 11 | 当前 release = `site-20261016-000910` | 我 08:59 复测时已不是这个值了（一晚多次发布）⇒ **任何写死的"当前值"都会过期**，建议改用 `docs/facts/latest.json` | R1 X5 |

**另外**：`static/js/app.js`（2356 行）+ `kurisu-player.js`（2769 行）**不被任何产物页面加载**
（页面 HTML 里只有 `src="/js/xk-app.js"`），`layouts/partials/xk-views/**` **无人 include**
⇒ 共 5000+ 行死代码，可与 T10 同批清理。

---

## 5. 新增的 3 个工具（都跑通了）

```bash
# ① 事实快照 —— 解决"实测数字落笔即过期"
python -X utf8 _dev/snapshot-facts.py            # 写 docs/facts/<UTC>.json + latest.json
python -X utf8 _dev/snapshot-facts.py --no-ssh   # 离线只跑本地部分

# ② 资产引用完整性（第四道门禁候选）
python -X utf8 _dev/check-asset-integrity.py --json _shots/asset-integrity.json
#   当前：引用 358 条 / 断链 76 条（全为 mouthPatch 的 .png vs .webp）/ 退出码 1

# ③ 布局静态审计（默认只报告不拦，加 --strict 才当门禁）
python -X utf8 _dev/audit-layout-static.py
```

**③ 存在的理由**：本环境 **Edge headless 跑不起来**
（`--headless=new` 和 `--headless=old` 都会 `Abnormal renderer termination`，
GPU 进程 `exit_code=-1073741819`）⇒ `gate-firstscreen.mjs` 在我这儿跑不了。
如果你那边能跑真浏览器，优先用那个；③ 只是兜底。

⚠️ ③ 的触控区估算是启发式（`padding + font-size×1.75`），**会误报**，别当验收判据。

---

## 6. 我改了 `.gitignore`（**需要你确认**）

`_dev/` 是白名单制（L60 `_dev/*` + 逐条 `!_dev/xxx`）。我的 3 个新脚本默认被忽略，
已按既有格式追加：

```
# 外部审查接手批（窗口 R，2026-10-16）：事实快照 / 资产引用完整性(第四道门禁候选) / 布局静态审计
!_dev/snapshot-facts.py
!_dev/check-asset-integrity.py
!_dev/audit-layout-static.py
```

如果你不打算留这 3 个脚本，删掉这 4 行即可。

---

## 7. 我没核到的（**别当结论**）

| # | 未核 | 怎么补 |
|---|---|---|
| 1 | `max_tokens=800` 是否真触发截断 | 后端配置，或一次超长问答实测（消耗 30/日额度） |
| 2 | CF 是否注入 `cloudflareinsights` | 真浏览器 DevTools Network 面板 |
| 3 | 两台服务器实例费 | 站主账单 |
| 4 | 12 句语音听感 / MOS | 人工盲听 |
| 5 | 线上 release 内 `bank.json` 是否含 `nav_labs`/`nav_about`（已删页的死语音） | `ssh secagent-srv2` 读线上 bank.json |

---

## 8. 建议的处理顺序

```
链 A（止血，互不依赖）
  ① 修 api-bind L167/L209（2 行，今天能完）
  ② 问后端 alertsMockEnabled 语义

链 B（接线前必做）
  ③ 修 mouthPatch（改 build_statemachine_manifest.py 源头）→ 跑 check-asset-integrity 验 0 断链
     → 然后才动 T8 状态机+口型接线

链 C（口径收尾，可与你的 T10/T27 同批）
  ④ 删死代码（xk-views 6 个 + static/js 那两个）
  ⑤ 文档口径订正（§4 那 11 条）
  ⑥ 把"当前 release / 页面字节"改成引用 docs/facts/latest.json

⚠️ 资源冲突提醒：链 B 和链 C 都落在 statemachine.json 上，
   而 build_statemachine_manifest.py 会重写它 ⇒ 必须串行，改完立刻重跑生成器确认没被写回。
```

---

## 9. 我上一轮说错的一处（自查）

上一轮报告里我把"改 `layouts/*` 必须同步生成器"当成全适用 —— **不准确**。
`api-bind.html` 是手写文件，可以直接改。正确判据见 §2 的表。
（这条也说明：**核查时要覆盖 `layouts/**`，不能只查 `docs/**`**，
这正是详版 N7 出错的根因 —— 它把有源码出处的两条硬伤误判为"口述未落文档"并建议移除。）
