# 状态 · 素材与资料复查（2026-10-15）

> 只由本窗口自己更新；格式见 `docs/窗口分工规范-20261015.md` §四

| 项 | 内容 |
|---|---|
| 负责 | 对 `F:\7AAA\AI\命运石之门\`（六包 + `1\`）与 `F:\7AAA\AI\命运石之门\1\` 做**只读复查**，产出"有什么用 / 怎么用 / 值不值得用"的结论 |
| 状态 | **已完成**（索引 + 抽帧 + 逐项判读 + 结论） |
| 改了哪些文件 | 新增 `docs/素材与资料复查-20261015.md`、新增 `docs/状态-N-素材复查.md`（**仅此两个** ✓；`layouts/**`、`static/**`、`scripts/**`、`_dev/**`、活文档、任务清单一律未动 ✗） |
| 验收证据 | ① **45 个视频全数 ffprobe 建索引**（= 40 mp4 + 5 mov，**2,345.9 MB** ✓）：`E:\DeepSeek1\work\_asset-review\video-index\final-video-index.json` 与 `FINAL-INDEX.txt`；**发现容器 `avg_frame_rate` 不可信**（如 `live2d.mov` 报 `101100/1753`），改用 `-count_packets` 的 `nb_read_packets ÷ duration` 重算真帧率（真值 = 60/30/25 三档）<br>② **每个视频抽 4~8 帧并做接触表**：`video-index\sheet-<片名>.jpg`（45 张）+ `frames\<片名>\f_*.jpg`（全部可点开复核）<br>③ **最有价值证据（带路径）**：`frames\detail-live2d\char_t8s.jpg`（Anime2.5DRig 标题栏+日志原文）、`panel_t8s.jpg`（参数面板原文：`ランダムロパク 随机对口型`/`マイクロパク 迈克对口型`/`髪の物理`）、`frames\detail-mouth-ab2\full_open.jpg`（`AMADEUS HOLO-LINK` 逐条双情绪标签 `[thankful → tsundere]` + 桌面图标 `Kurisu手机模式启动/停止`）、`frames\detail-mouth-final2\AB.jpg`（嘴闭/嘴开 A/B，**像素差 MAE = 64.591**）、`frames\detail-desktop-crt\crt_t7.jpg` vs `crt_t17.jpg`（臂放下 → 双臂交叉+张嘴）<br>④ **口型同步定量测量**（诚实版）：`lipsync\roi-report.txt` —— 音频 10ms RMS 与脸部 ROI 逐帧像素变化 **Pearson r = +0.4698**，lag 扫描最佳 **r = +0.5123 @ +70ms**；**不宣称"已实现同步"**<br>⑤ **`04`/`03`/`05` 三包逻辑 JSON 抽到仓库外**（未全量解包）：`04-visual-runtime\scenario_graph.json`（**6 场景 / 19 边概率图**）、`03-character-kurisu\graph_config.json`（**37 节点/87 边**）与 `spriteforge_mouth_config.json`（**16 profile**）、`05-companion-kurisu\manifest.json`（**9 情绪 / 18 变体 / 688 帧**，实测 webp 网格 1056×396 与 manifest 一致、`fileBytes` 18/18 零失配）<br>⑥ **两个 PDF 全文抽取**：`pdf\pdf-extract.txt`（10,351 + 6,398 字）+ 首页渲染图<br>⑦ **回滚源自证**：`Get-FileHash` 实测 `ba0160999d6a…` 与官方 `SHA256SUMS.txt` **逐字符一致**（`04`/`05` 同样一致）<br>⑧ 只 `git add` 本行两个 docs；**未 push** ✓ |
| 结论（一句话） | **那 45 个视频不是游戏录屏，而是原项目作者本人的 Amadeus 开发/使用实录**；其中 **`live2d.mov`（Anime2.5DRig 编辑器参数面板）+ `Desktop 2026.10.07 - 13.18.21.07.mp4`（一帧同给"说话口型 + 换姿 + 逐条双情绪标签"）** 是**最值得现在就用**的两件东西；`04`/`05` **无任何代码**但当数据可借（场景概率图、8+1 情绪图集）；两个 PDF 中 **`学习课程.pdf` 建议入知识库**、评测报告只作基线参照 |
| 三条可落地 | ① **官方有"无语音随机对口型"状态**（`ランダムロパク`）⇒ 补 T8 的 `idle` 系列（我们现在静音只叠闭嘴层）<br>② **官方情绪是 `[用户情绪 → 角色心情]` 二元组 + 黏滞** ⇒ T14 的 `情绪` 字段由单值改为二元组（依据 `AMADEUS HOLO-LINK` 面板原文）<br>③ **官方有"同情绪多说话变体"**（`sided_thinking` 同时有 `speaking` 123帧 / `speakingAlternate` 74帧）⇒ `/ai/` 页连续同情绪时轮换变体 |
| 已核对且**无需重做** | 官方包与现有文档逐项一致：`prob=0` 恰好 **9 条**（目标名逐字对得上）、口型 profile **16 个**、`openness` 是静态逐帧值、`anchor_track` 每帧带 `score`≈0.978–0.998、`closed_frame_idx` 与 `argmin(openness)` 确实冲突、**官方 JSON 里没有 `preferredVariant`**（我方该字段是 `_dev/build_mouth_data.py:227` 自造）⇒ 下一步不必在这几条再花时间 |
| 未做 / 不做 | ✗ 未改任何素材（全程只读）｜✗ 未把 zip 解包到素材目录（只抽少量 JSON 到 `E:\DeepSeek1\work\_asset-review\`）｜✗ 未 push｜✗ 未代写活文档（§10 只给出**建议追加行**） |
| 卡点 | 无技术卡点 ✓。**唯一限制是本机原本没有 ffmpeg/ffprobe**（已自行在仓库外下 9.0.2-essentials 解决，SHA256 `60f46726…` 记录在案）。<br>**已知未覆盖**：14 个视频（#6/#7/#8/#10/#11/#28–#34/#36/#37）只做了索引+接触表、未逐个放大判读；`1789976770016.mp4`（2.75s）用途未判明 —— 见主文档 §11 诚实清单 |
| 下一步 | ① 需规划侧裁决：§9.2 三条是否派工（尤其 ② 会改 T14 的 JSON 契约）<br>② §10 的建议行由**有写权限的窗口**追加到 MasterPlan §11<br>③ 若要坐实"口型同步"，需一段**只有语音、无鼠标/换姿干扰**的片段重测 |

---

## 附：产物索引（仓库外，供复核）

| 路径 | 内容 |
|---|---|
| `E:\DeepSeek1\work\_asset-review\video-index\FINAL-INDEX.txt` | **45 个视频的最终索引表**（含真帧率/真帧数/码率/内容判断） |
| `E:\DeepSeek1\work\_asset-review\video-index\sheet-*.jpg` | 45 张接触表（每个视频 4~8 帧） |
| `E:\DeepSeek1\work\_asset-review\frames\detail-*\` | 关键证据放大帧（live2d 面板 / CRT / 悬浮窗 / 口型 A-B） |
| `E:\DeepSeek1\work\_asset-review\04-visual-runtime\scenario_graph.json` | 6 场景 / 19 边概率图 |
| `E:\DeepSeek1\work\_asset-review\03-character-kurisu\` | `graph_config.json` + `runtime_manifest.json` + `spriteforge_mouth_config.json` + `analysis.txt` + `clips-analysis.txt` |
| `E:\DeepSeek1\work\_asset-review\05-companion-kurisu\` | `manifest.json` + `analysis.txt` |
| `E:\DeepSeek1\work\_asset-review\pdf\pdf-extract.txt` | 两个 PDF 全文（10,351 + 6,398 字） |
| `E:\DeepSeek1\work\_asset-review\lipsync\roi-report.txt` | 口型同步定量测量（r=0.47 / 最佳 0.51@70ms） |
| `E:\DeepSeek1\work\_asset-review\tools\*.py`、`tools\*.ps1` | 本次全部脚本（可复跑：`probe_videos.ps1` / `probe_packets.ps1` / `extract_frames.ps1` / `extract_batch.ps1` / `analyze_03.py` / `analyze_clips.py` / `analyze_companion.py` / `read_pdfs.py` / `lipsync_check.py` / `roi_mouth_check.py` / `final_index.py`） |
