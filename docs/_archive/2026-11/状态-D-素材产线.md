# 状态 · 窗口 D-素材产线

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 [窗口分工规范-20261015.md](窗口分工规范-20261015.md) §四

| 项 | 内容 |
|---|---|
| 负责 | **T18 能力建设** + **T23 SpriteForge 试点**（窗口分工规范 §一 的 D 行：`tools/**`、`_dev/asset-*.py`、云 GPU 侧产物） |
| 状态 | **T18 段一/段二 已完成** ✓（能生成评估 + **能对齐 + 能筛**）；**段三"能入库"未做** ✗；T23 试点：**评估 + 本机最小示例实测完成** ✓，**未跑任何生成（不花钱）** ✗ |
| 改了哪些文件 | 新建 `tools/asset_common.py`、`tools/asset-align.py`、`tools/asset-consistency.py`、`tools/asset-refset.py`、`tools/refs/kurisu-set/`（21 张 PNG + `refs.json`，1,133,054 B）、`tools/refs/kurisu-anchors.json`、`tools/refs/consistency-calibration.json`、`docs/素材产线能力-T18-20261015.md`、本文件。**未碰** `static/kurisu/**`、`layouts/**`、任何活文档 ✓ |
| 验收证据 | ① `tools/refs/consistency-calibration.json`（210 帧互测 + 7 个负样本，阈值可复核）<br>② 锚点实现与上游逐位一致：同一张 `idle-reference.png` 上本库 `21 / 387.66 / 370096` ⇔ SpriteForge `character.json` `21 / 387.66 / 370096`（三项全等，差 0）<br>③ `asset-align.py`：4 帧 268×360 视频首帧 → `scale 2.85556`、锚点偏差 ≤1.25 px；180 帧真实剪辑 → 漂移 0.0/0.23 px、QA 180/180 通过<br>④ `asset-consistency.py check`：对齐后 4 帧全 pass（最差 edgeNcc 0.92474）；反相/拍平假素材被 rgbNcc 拦下（edgeNcc 0.8311 也 fail）<br>⑤ SpriteForge 最小示例本机跑通（纯 CPU）：`init workspace --demo` + `review` 200、`production init/take import(placement & registration)/take accept/clip add/prompt/prepare` 全过、`/studio` 200、`production status` 显示全部 provider `key=missing`<br>命令原文与输出见 `docs/素材产线能力-T18-20261015.md` §3/§4/§5/§6 |
| 下一步 | ① 做 **段三"能入库"**：扩展 `_dev/build_statemachine_manifest.py` 支持"新剪辑登记表"→自动生成节点/概率边/`host_triggered` 入口（**归 C 窗口或规划侧派工**，因为要动 `_dev/build_statemachine_manifest.py` 与 `static/kurisu/statemachine.json` ✗ 不是我的路径）<br>② 建议把 `asset-align.py --sheet` 的页描述直接喂给入库脚本（字段已与 `medium.pages[]` 同构 ✓）<br>③ 若要做自动刚体注册（对齐静帧到基准帧），装 `cv2` 并把 ORB+RANSAC 合进 `asset-consistency.py` |
| 卡点 | 无（本轮零花费、零 GPU 完成）。两个口径类缺口已记 `[待核对]`：764×1028 在百炼按 720P 还是 1080P 计费；wan.video 会员积分的单价。**未决（需用户/规划侧拍板）**：pilot 首次花钱的量级（建议 2 个动作 = ¥7.2~¥21.6 或 8 会员积分） |
