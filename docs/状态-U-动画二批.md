# 状态 · U｜第二批动画（T34 静音口型 / T33-a 眨眼 / T33-b 视线跟随 / T8-b 口型契约）

> **窗口**：执行侧 · 动画批 2 ｜ **日期**：2026-10-15
> **基准 HEAD**：开工 `21270a2` → 出件期间被推进到 `2276419`（**只动 6 个 docs** ⇒ 本批目标文件零漂移 ✓）
> **实施件**：`docs/动画第二批实施件-20261015.md`（同目录）｜ **产物**：`E:\DeepSeek1\work\_anim-batch2\**`（仓库外）
> **纪律**：本轮**未写** `layouts/**`、`_dev/gen-demo-pages.py`、`static/**`、`scripts/voice/**`、`static/kurisu/voice/**`、
> 别人的状态文档 ✗；**只 `git add` 了本文件与实施件两份 docs**（未 commit、未 push）✓

---

## 1. 一句话状态

| 项 | 状态 | 现在能做什么 |
|---|---|---|
| **T34 静音随机口型** | **可应用** ✓ | 补丁 01（6,876 B）+ 开关 `?xk-mouth-idle=0`，无需素材 |
| **T33-a 眨眼** | **可应用** ✓（素材问题已解决） | 补丁 02 + 素材 `payload\static\kurisu\eye\`（4,322 B）；`idle1` 图集自带真眨眼，已抽出眼皮补丁 |
| **T33-b 视线跟随** | **可应用** ✓ | 补丁 03 + 补丁 05（4 条边）+ 补丁 06（生成器不漂移） |
| **T8-b 口型第二批** | **可应用** ✓（裁决待跑） | 补丁 04（契约显式化）+ `tools\test-mouth-variant.mjs` 逐条实测脚本（应用后跑一次即出"补丁/遮罩"结论） |

**六份补丁对 `21270a2` 的 `git apply --check` = 6/6 PASS ✓**（在含 `.git` 的仓库副本上验的，真仓库零改动 ✓）；
按序 apply 后终态与 `generated\**` **逐字节一致** ✓；`node --check` / `py_compile` / 结构化自检全绿 ✓。

---

## 2. 关键事实（本次会话新产出的，可直接引用）

```
[已实测] idle1 图集（static/kurisu/medium/idle1.atlas.webp，134×180 tile，120 帧）**自带两次真眨眼**：
         tile 30-33 全闭（无争议）；12× 网格印样 + 逐帧眼带差分为证
[已实测] idle1 整段 120 帧**逐帧位移恒为 (0,0)**（脸部区域 ±4px 模板匹配）⇒ 眼皮补丁可用固定锚点
[已实测] 眼皮补丁 = 闭眼帧眼带矩形 66×26 tile px（源帧 376.3×148.2）×5 上采样 + 羽化 = **4,322 B**
[已实测] 眼带中心在源帧坐标 y ≈ 176.8 → 相对"脚踩点"的纵向比例 0.35（`eyePoint()` 的默认基准就用它）
[已实测] 16 个口型 label ↔ static/kurisu/mouth/*.json **一一对应、媒体文件 0 缺失**；has_mouth_profile=16
[已实测] statemachine.json 加 4 条边后 = 38 节点 / **92 边**；host_triggered_entries 仍 9 个（4 条都是正概率边）
[风险]   侧脸族 3 段 medium 图集约 0.3 MB/段 —— 带宽闸 SM_DEFAULT_MAX_BYTES=6MB 不变
[风险]   idle2 / idle_mic_wind / idle_str_wind 的"与 idle1 同机位"是推断（frame_size 一致 + 同族命名），
        未逐帧验证 ⇒ 应用后看一眼 blink-closed 截图即可确认；不吻合就把该剪辑从 eye json 的白名单去掉
[风险]   默认 idle（主页最常出现的那个）**戴不了**：它与 idle1 不是同一姿态，而 idle 图集里没有闭眼帧
```

---

## 3. 等什么 / 下一步

```
⏳ 等 UI 批落地（另一条线在改 layouts/** + _dev/gen-demo-pages.py）并 commit
   → 收到"UI 批已落地"后：重跑 build_patches.py 重出补丁（锚点若被改会直接报错，不会静默写坏）
   → 按 §7 施工顺序 apply 六份补丁 + 拷 static/kurisu/eye/ 素材
   → 跑两个验收脚本（verify-anim-batch2.mjs / test-mouth-variant.mjs）+ 生成器闭环 + 三道门禁
预计"应用后到可验收"：约 **1.5~2.5 小时**（apply+生成器+hugo+门禁 ~40min；两个脚本各 ~10~15min；
  截图人眼复核 + 可能的剪辑白名单微调 ~30~60min）
```

---

## 4. 自证（本窗口的写操作清单）

```
[已实测] 仓库写入 = 仅两个新文件（本文件 + 实施件），且只 git add、未 commit、未 push：
   git status --porcelain →  A  docs/动画第二批实施件-20261015.md
                              A  docs/状态-U-动画二批.md
   git log --oneline -1   →  2276419（**不是**本窗口的提交，本窗口无提交）
[已实测] 本窗口改动的仓库外文件：E:\DeepSeek1\work\_anim-batch2\**（补丁/成品/payload/标定数据/工具）
[已实测] 唯一一次误操作及修复：pwsh 的 Set-Content 把**仓库外**一个工具脚本的中文注释写成乱码，
         已整份重写修复 ✓；真仓库与其它产物未受影响（实施件 §9 记了这条坑）
```

---

## 5. 一行摘要（可贴进总台账）

> **动画批 2**：出齐 6 份补丁（`git apply --check` 6/6 PASS）+ 眼皮补丁素材（4,322 B）+ 两个验收脚本 + 离线几何标定；
> 实测确认 **`idle1` 图集自带两次真眨眼**（tile 30-33 全闭、120 帧位移恒 0）⇒ 眨眼**不需要新渲素材**；
> 新增 **4 条边**（`idle/idle1/idle2 → 侧脸族`，`idle_side_wind → idle`；全部正概率、非宿主触发）；
> 四项 T34/T33-a/T33-b/T8-b 均"可应用"，唯一未覆盖的是六页内联动画脚本与默认 `idle` 的闭眼补丁（待 UI 批之后）。
