# 状态 · 窗口 O / T25-E-mote 本机试跑

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 `docs/窗口分工规范-20261015.md` §四

| 项 | 内容 |
|---|---|
| 负责 | T25 **E-mote 本机试跑 + 机制抽取**（★ 纯本地实验：只在本机看一眼、把可借鉴的机制抽出来；**不发布 / 不进仓库素材 / 不改站点** ✗） |
| 状态 | **已完成**（试跑跑通 + 7 条机制抽取 + 与现状逐条对照） |
| 改了哪些文件 | 新增 `docs/E-mote本机试跑与机制抽取-20261015.md`、新增 `docs/状态-O-E-mote试跑.md`（**仅此两个** ✓）；站点代码/配置/素材/线上**零改动** ✓（`F:\7AAA\AI\blog\static\**` 一个字节未动 ✓）；仓库外产物在 `E:\DeepSeek1\work\_emote-trial\**` ✓ |
| 验收证据 | ① 解包校验：32 文件 = **129,281,861 B = 123.29 MiB**，zip sha256 与 T24 记录一致 ✓<br>② demo 只下 zip（**未 git clone**）= 43,723 B，commit `3008f3ef90527e5c2ec144bb0496ce3ee67cf1a3`；vendored 运行时 sha256：`FreeMoteDriver.js 64a38cbc…0641`（1,255,818 B）、`emoteplayer.js 807e5c6a…9eba`（40,211 B）✓<br>③ 加载成功（`node tools/probe.mjs verify`，原始数据 `logs/verify-six.json`）：六条目逐条 **`window.demo.ready === true`**、**0 error / 0 exception / 0 loadingFailed / 0 warning**；就绪 **1,507~3,663 ms**、解码字节 **27,374,381~45,494,902 B**；像素判据 **18 张全部 0.7172~0.9829**（"黑剪影"阈值 0.4）⇒ 非黑剪影 ✓<br>★ 两条**会被数字骗**的口径警告：同模型冷/温两跑差 **2.1×**（`c_白衣` 3,843→1,816 ms）；**CDP `Performance.getMetrics.JSHeapUsedSize` 只有页面内 `performance.memory` 的 ~1%**（11~14 MB vs 760 MB~1.22 GB）⇒ 别用 CDP 那个指标判内存 ✗<br>④ 内存：**512 MiB wasm 堆在 t=175 ms 就已一次性预分配**（`Module.TOTAL_MEMORY`）；页面内 JS 堆点采样 **760 MB~1.22 GB**（受 GC 时机影响）；Edge 进程组工作集**峰值 2,115.8 MB**（t=10.4 s，11 进程；空页基线 497 MB；加载完回落到 579 MB）⇒ 按 **≥2 GB 级**记 ✓<br>⑤ 截图 **18 张 PNG**：`E:\DeepSeek1\work\_emote-trial\shots\`（12 张 = 6 条目 × 半身/全身 + 6 张行为；`logs/shots.json` 的 20 条记录里另有 2 条是纯数值测量、不出图）；行为数值证据：`head_LR=100`、`face_talk=5`、`mainTimelineLabel=表情_笑`、`diffTimelineSlot1=うん`、`face_eye_open` 200 帧内 0↔10 插值、视线跟随像素差 bbox **(295,187)-(406,227) 仅 655 px 且全在上 45%**（只有眼睛动了）✓<br>⑥ 机制数据：`logs/model-analysis.json`（四套模型 metadata 全表；ab 813 图层/2268 cel/**1672 带网格**/101 时间线；c 655/1703/1453/76）+ `tools/analyze_timeline.py` 统计（c 759 轨道中 **单键+END 515 条**，ab 966 中 659 条）✓<br>⑦ demo 自检 `node psb.test.mjs` **6/6 通过**（四套源往返 + 口型/表情映射 + i18n 对齐）✓ |
| 结论（一句话） | **本机跑通了**（六条目逐条核验 0 报错、18 张截图、字节/内存/时间三组量化在手 ✓），但它对我们是**"另一套资产表示"**：7 条机制里**只有"锚点+小补丁"这条路能用我们现有素材实现** ⇒ 结论是**只追"眨眼 → 视线跟随"（2~4 人日、素材增量几十 KB 级）**，头部朝向（素材 ×3）与网格变形（要换素材体系）**不追** ✗ |
| 下一步 | ① 若规划侧点头：把 `static/kurisu/mouth/` 那套"逐帧锚点 + 小补丁"扩成**眼部补丁层**，先做随机眨眼（照抄 E-mote 六档预设：close .106 / hold .053 / open .106 s，间隔 0.5~3 s），再做视线跟随（眼睛锚点为基准 + ±200 增益 + ±100 钳制 + 120 ms 平滑）⇒ 需另开施工任务（本文只做研究，**不动站点** ✗）<br>② 把"边的过渡规格 + 结束语义（loop/once_then_hold 归位）+ 离散维度不插值"写进状态机约定（0.5~1.5 人日）<br>③ 本窗口无写权限：§11 那一行交有写权限的窗口追加（见下）✓ |
| 卡点 | **无技术卡点** ✓。过程卡点两个**都已解决**并写进正文：① `python -m http.server`（本机 Python 3.9.13）不认 `.mjs` ⇒ 判成 `text/plain` ⇒ 模块脚本被拒（症状=页面全空、只有一条 MIME 报错），改用补了 MIME 的同款服务器（8011）✓；② demo 默认从 jsDelivr 拉运行时 ⇒ 按任务要求 vendor 到本地（此处**故意违反** demo `AGENTS.md` 的"不要 vendor"那条，原因已记进正文 ⚠️）。<br>未测项：触摸端视线（headless 只发 mouse 事件）、真实网络带宽成本（本地测不出）、移动端表现、长时运行的内存增长 ✗ |

---

## 附：建议追加进 MasterPlan §11 变更日志的一行（**本窗口无写权，交有写权限的窗口追加** ✗）

```
| 10-15 | O｜E-mote 本机试跑 | 跑通 E-mote demo（仓库外解包 123.29 MiB + vendored 运行时 + 本地 8011 + headless Edge/CDP 自写驱动）：**六条目逐条核验** `window.demo.ready===true`、**0 error/0 exception/0 loadingFailed**、像素比 0.9188~0.9829；解码字节 27.37~45.49 MB，就绪 1,507~3,663 ms（同模型冷/温差 2.1×）；内存：512 MiB wasm 堆 t=175 ms 即预分配、页面内 JS 堆 760 MB~1.22 GB、Edge 进程组峰值 **2,115.8 MB**；**18 张截图**；机制抽取 7 条逐条给出"能否用现有素材实现 + 成本"；结论：只借"锚点+小补丁"层做"眨眼→视线跟随"（2~4 人日），头部朝向与网格变形不追；另记两条口径警告（CDP JSHeapUsedSize 只有页面内口径 ~1%） | `docs/E-mote本机试跑与机制抽取-20261015.md`、`docs/状态-O-E-mote试跑.md`；仓库外 `E:\DeepSeek1\work\_emote-trial\shots\`（18 张）+ `logs\` | 只读研究；站点/素材/仓库零改动（`static/**` 与线上六页未触碰）；无发布、无 push |
```
