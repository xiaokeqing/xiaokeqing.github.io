# 状态 · 窗口 P / UI 批实施件（T31 / T27 / T28 / T20-T22 + 全身形态）

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 `docs/窗口分工规范-20261015.md` §四

| 项 | 内容 |
|---|---|
| 负责 | **UI 批出实施件**：T31 开场六阶段 / T27 删靶场+关于 / T28 收旧问答入口 / T20-T22 三块展示 / 追加：手机面板全身形态 + 主页 CRT 半身⇄全身 + 正脸·侧脸两条路线 |
| 状态 | **已完成（实施件阶段）** —— 11 份补丁 + 8 份文档 + 2 份追加设计 + 视觉对照图；**未写仓库、未 commit、未 push** ✗（等窗口 C 的 T8 第一批交完）<br>★ 出件过程中 HEAD 从 `ed57739` 被推进到 **`15a8a97`**（该提交只改任务清单文档 17 行、**没碰任何锚点文件**）⇒ 已在**新 HEAD 上重跑全套自检**：11/11 PASS、生成器闭环 0 漂移、hugo + 契约门禁 4/4 ✓，补丁已按新 HEAD 重出 ✓ |
| 改了哪些文件 | 仓库内**只 `git add` 两份 docs**（`docs/UI批实施件-20261015.md`、`docs/状态-P-UI批.md`），**未 commit** ✗；站点代码/配置/素材/线上**零改动** ✓（`layouts/**`、`_dev/gen-demo-pages.py`、`static/**`、`scripts/**` 一个字节未动 ✓）。<br>产物全在仓库外 `E:\DeepSeek1\work\_ui-batch\**`：`patches\`（11 份）、`00-README.md`…`05-口径冲突与需站主拍板.md`、`自检记录.md`、`追加-手机面板\`（6 图）、`追加-CRT舞台\`（12 图）、`data\kb-条目草案-T5.3迁移.md`、`tools\build-patches.py`、`_work\`（仓库外副本，可直接 hugo 构建复看） |
| 验收证据 | ① **11/11** patch `git apply --check` **PASS**（对 HEAD `ed57739`，`git archive HEAD` 取的干净副本里验）<br>② 依序全部应用后**重跑 `_dev/gen-demo-pages.py` → 全工作树逐文件 sha256 差异 = 0** ✓（证明"产物补丁 ↔ 生成器"同源，不会被下次生成冲掉）<br>③ `hugo --cleanDestinationDir` **exit 0**；`python _dev/check-ssr-contract.py public` **4/4 PASS**（改前 6 页）<br>④ 核心补丁下：`public/labs/`、`public/about/` **不存在** ✓，`sitemap.xml` 里 `labs\|about` **0 命中** ✓；打上可选 10 号后两页变成 `meta refresh` 到 `/alerts/`、`/ai/`（原文已核）<br>⑤ 字节（实测文件大小）：`desk.webp` 77,608 B（T=0 唯一图片）；被推迟的 glow 45,352 + lab 59,950 + plate 382,384；补丁后 `public/index.html` 76,400 B（HEAD 同产物 53,374 B ⇒ 本批 +23,026 B）<br>⑥ 视觉对照图全部用**真实素材**（E-mote 试跑 18 张取证图 + `idle.boot.webp` 图集第 0 帧）；动效部分图上已标"合成示意" |
| 结论（一句话） | 下一批 UI 活已经做成**可直接落地且已自检的补丁 + 设计决定** ✓：T31 按站主逐帧规格重做（显式状态机 + 导航由"闪烁结束事件"触发 + 首帧只剩壁纸）、T27/T28 减法连带全清（含三门禁页数与生成器）、T20-T22 三块按 F 的字段映射落地（真实只读端点、IP 打码、空态照稿、不轮询、零新 CSS 类）；**只差站主裁 3 件事**（IP 段数 / 老 URL 去留 / 删页连带 projects·demo 与个人简介）与一句"开始写" |
| 卡点 | **无技术卡点** ✓。<br>过程卡点 1：`git archive \| tar -x` 经 PowerShell 管道会坏（`bad header checksum`）⇒ 改用 Python `tarfile` 解 ✓<br>过程卡点 2：`_dev/gen-demo-pages.py` 里 `sub1/subn` 定义在 L400，晚于 L334 的 dock 改写 ⇒ 后置裁剪必须放到 L400 之后（已按此写，注释写明）<br>过程卡点 3：最初手改生成产物（index/shell-views/shell-chrome）导致"重跑生成器必漂移" ⇒ 改成**只改手写件 + 生成器，产物由生成器跑出来**（自检第 ② 条因此才可能为 0）✓<br>过程卡点 4：`gate-firstscreen.mjs` 与 `check-ssr-contract.py` 必须与删页同批改，否则门禁 FAIL（已同批）✓ |
| 下一步 | ① 站主裁 `05-口径冲突与需站主拍板.md` 的 10 条（**第 0 条最新**：T20~T22 已按 `15a8a97` 降为可选 —— 若决定不上，我可再出一版"T31+T27/T28 only"补丁集；其余会改补丁内容的 3 条：老 URL / 删页连带 / IP 段数已按站主定）<br>② 等窗口 C 的 T8 第一批 **commit** ⇒ 跑 `tools\build-patches.py` 重出补丁（锚点若有变会直接报错，不静默写坏）<br>③ 按 `04-实施顺序与施工顺序.md §4` 的剧本落库：apply → 生成器 → hugo → 三道门禁 → 真浏览器前 1.2s 逐帧取证（T31 验收 ①）<br>④ 需要时我把"路线 A 的侧脸边（`idle→idle_side_soft_wind` 等 4 条）"写成 T8 的独立补丁（本轮未写 ✗：属 C 的 `_dev` 状态机概率表）<br>⑤ 台账订正（**非本窗口写** ✗）：`docs/待办-施工任务清单-给执行AI.md` 与 `MasterPlan §10-15` 里 T27 的"六→五 / 6→5"应改为"六→四 / 6→4" |

---

## 附：本轮实测到的两条与口径不符（建议规划侧收进台账）

```
① `look_at_CRT`（带真眨眼）**不在** `static/kurisu/statemachine.json`（38 节点/92 边）里 ✗
   —— 它在 `static/kurisu/manifest.json:489` 叫 `look_at_CRT_loop`（180 帧 @30fps，第 38–43 帧是真眨眼）；
   站点的 `opening` 剪辑 = 它的**前 84 帧**（manifest.json:500 的 note 原文）。
   ⇒ 派单里"`look_at_CRT`（带一次真眨眼）"这句要改成"`opening` 的前 84 帧即含那次真眨眼"；
   状态机里能用的是 `closed_eye_trans`（**host_triggered_entries** ✓）与 `idle→idle_closed_eye`。
② 从 `idle` 到侧脸族**没有直边** ✗：唯一通路 `idle→trans_standby`(0.05)→`idle_side_*`(0.3/0.1)
   ⇒ 实际概率 ≈0.015/0.005，"随机转头看侧脸"必须**加边/提概率**（T8 的地盘）。
   侧脸族共 3 条：idle_side_wind / idle_side_soft_wind / idle_side_butterfly（medium 分别 1.21MB / 1.09MB / 4.46MB；
   webm 侧已有 idle_side_butterfly 1.20MB、idle_str_wind 0.37MB）。
```
