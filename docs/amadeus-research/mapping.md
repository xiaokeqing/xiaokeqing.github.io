# mapping.md — Kurisu 素材语义映射表

> 站长口径：**动画都是原包做好的，解包直接用**。所以本表只做一件事：把原包里每个素材**本来对应什么**找出来，并明确标注每个说法**来自哪里**。

| 标记 | 含义 |
| --- | --- |
| `[原包]` | 原包文件里**写明**的（runtime_manifest / graph_config / scenario_graph / companion manifest） |
| `[实测]` | 本次解包**量出来**的（帧数、尺寸、像素、音频参数） |
| `[推断]` | 我按画面给的**人话用途**，原包并未这样写 |

生成时间：2026-10-14 08:22:47 ｜ 脚本：`tools/11_mapping.py`

## 0. 三个 `ASSET_BUNDLE_MANIFEST.json` 里到底有什么（重要）

**结论先说：三个包根目录的 `ASSET_BUNDLE_MANIFEST.json` 只有 `path` / `sha256` / `size` 三个字段，没有任何 name / 描述 / 用途 / 时长 / 帧数。** 所以「语义」不能从这三个文件里读，必须去读包内其它 JSON（下面第 1 节）。`[原包]`

| 包 | format | file_count | total_bytes（原包自报） | pack id / spec_version | entry 字段 |
| --- | --- | --- | --- | --- | --- |
| 03 | amadeus.external-asset-bundle.v1 | 7555 | 2664006607 | `character-kurisu` v1 | `path`, `sha256`, `size` |
| 04 | amadeus.external-asset-bundle.v1 | 195 | 255433877 | `visual-runtime` v1 | `path`, `sha256`, `size` |
| 05 | amadeus.external-asset-bundle.v1 | 19 | 11921046 | `companion-kurisu` v1 | `path`, `sha256`, `size` |

对照 `[实测]`：

| 包 | 原包 file_count | 实测 zip 内文件数 | 差异原因 |
| --- | --- | --- | --- |
| 03 | 7555 | 7556 | manifest 自己不把自己算进去（7555 = 7552 ktx2 + 3 json） |
| 04 | 195 | 196 | manifest 不把自己算进去（195 = 188 png + 1 mp4 + 2 json + 3 ui png + 1 wav） |
| 05 | 19 | 20 | manifest 不把自己算进去（19 = 18 webp + 1 manifest.json） |

**`[原包]` 唯一一条跨包语义线索**：`05/assets/companion/kurisu/manifest.json` 里的 `sourceManifestSha256 = 259dfc10…210ebb`，与 03 的 `runtime_manifest.json` 的 sha256 **完全一致** → 05 的头像图集**明确声明**是从 03 的角色包派生的（同一角色、同一 manifest）。

## 1. 语义信息实际在这 5 个文件里

| 文件 | 大小 | 原包写了什么 |
| --- | --- | --- |
| `03 …/kurisu/runtime_manifest.json` | 540,865 B | `clips{<id>: {phase, loopMode, frameIntervalMs, frames[]}}`、`mouthOverlays`、`clipCount`、`frameCount`、`textureBytes`、`quality`、`zcmp` |
| `03 …/kurisu/graph_config.json` | 12,401 B | 角色状态机：`nodes[{id,label,isRoot}]` + `edges[{from,to,prob}]` |
| `03 …/kurisu/spriteforge_mouth_config.json` | 577,385 B | `canvas_size`、16 个口型 profile（`openness[]`、口型锚点） |
| `04 …/look_at_CRT/look_at_CRT_loop/spriteforge_clip.json` | 383 B | 这段循环的参数：`type`、`role`、`source`、`frames_dir`、`frame_pattern`、`source_fps`、`fps`、`source_frame_count`、`frame_count`、`stride`
| `04 …/scenario_graph.json` | 4,186 B | 场景状态机：6 个**有 label 的场景** + 带概率的转移 |
| `05 …/companion/kurisu/manifest.json` | 16,568 B | 9 个情绪 × (idle/speaking/idleStatic) 的 `url/size/columns/sequence/durationMs` |

### 1.1 `spriteforge_clip.json`（看 CRT 循环，原包全文）`[原包]`

```json
{
 "type": "spriteforge_graph_clip",
 "role": "loop",
 "source": "assets/source/project-asset/scenarios/look_at_CRT/look_at_CRT_loop.mp4",
 "frames_dir": "assets/source/project-asset/scenarios/look_at_CRT/look_at_CRT_loop/loop",
 "frame_pattern": "frame_%04d.png",
 "source_fps": 30.0,
 "fps": 30.0,
 "source_frame_count": 180,
 "frame_count": 180,
 "stride": 1
}
```
→ `[原包]` 这段循环的 `role` 字段就是原包对它的定性；`stride`/`frame_count`/`fps` 是播放参数。

## 2. 39 个角色剪辑：原包命名 → 人话用途

列含义：`原包-clip` = runtime_manifest 里的 clip id（= 目录名）；`原包-参数` = runtime_manifest 给的 phase/loopMode/frameIntervalMs；`原包-状态机` = 它在 graph_config 中的角色；`实测` = 本次量到的帧数/画布；`人话用途` = `[推断]`。

### 2.1 状态机骨架（`graph_config.json`，原包）`[原包]`

- **根节点 / 默认起手**：`idle`（`isRoot: true`）
- 节点数 37，边数 87；`runtime_manifest.clipCount = 39`
- 情绪入口（`idle → X`，原包把概率写成 **0.00** = 不随机触发，必须由宿主程序触发）：
  `angry_trans`、`closed_eye_trans`、`sad_trans`、`shy_trans`、`speaking_short`、`speaking_trans`、`surprise_trans`、`trans_smile`
- 剪辑里**没有出现在状态机**的（=原包做了但运行时不会自动播到）：`sad`, `smile`

### 2.2 全部 39 个剪辑

| # | 原包-clip | 原包-参数（phase / loop / 帧间隔） | 原包-状态机 | 实测 帧数 / 画布 | 人话用途 `[推断]` |
| --- | --- | --- | --- | --- | --- |
| 1 | `angry_speaking` | loop / loop / 17ms | 节点 入边2 口型叠加 | 180 / 764x1028 | 说话·生气 |
| 2 | `angry_trans` | loop / once_then_hold / 8ms | 节点 入边1 | 60 / 764x1028 | 转场 |
| 3 | `closed_eye_trans` | in / once_then_hold / 8ms | 节点 入边1 | 120 / 764x1028 | 转场 |
| 4 | `idle` | loop / loop / 21ms | 节点 根 入边6 | 120 / 764x1028 | 待机 |
| 5 | `idle1` | loop / loop / 21ms | 节点 入边2 | 120 / 764x1028 | 待机 |
| 6 | `idle2` | loop / loop / 21ms | 节点 入边2 | 290 / 764x1026 | 待机 |
| 7 | `idle_closed_eye` | loop / loop / 17ms | 节点 入边1 | 738 / 960x1028 | 待机·闭眼 |
| 8 | `idle_mic_wind` | loop / loop / 21ms | 节点 入边3 | 194 / 764x1028 | 待机·环境氛围 |
| 9 | `idle_side_butterfly` | loop / loop / 17ms | 节点 入边2 | 600 / 764x1028 | 待机·环境氛围 |
| 10 | `idle_side_soft_wind` | loop / loop / 17ms | 节点 入边3 | 180 / 764x1028 | 待机·环境氛围 |
| 11 | `idle_side_wind` | loop / loop / 17ms | 节点 入边4 | 180 / 764x1028 | 待机·环境氛围 |
| 12 | `idle_str_wind` | loop / loop / 21ms | 节点 入边2 | 194 / 764x1028 | 待机·环境氛围 |
| 13 | `key_point_speaking` | loop / loop / 17ms | 节点 入边2 口型叠加 | 180 / 764x1028 | 说话·重点 |
| 14 | `sad` | loop / loop / 17ms | **不在状态机** | 120 / 764x1028 | 情绪·低落 |
| 15 | `sad_speaking` | loop / loop / 17ms | 节点 入边2 口型叠加 | 120 / 764x1028 | 说话·低落 |
| 16 | `sad_trans` | loop / once_then_hold / 8ms | 节点 入边1 | 60 / 764x1028 | 转场 |
| 17 | `serious_to_thinking` | loop / once_then_hold / 8ms | 节点 入边2 | 120 / 764x1028 | 转场 |
| 18 | `shy_speaking1` | loop / loop / 17ms | 节点 入边3 口型叠加 | 180 / 764x1028 | 说话·害羞 |
| 19 | `shy_speaking2` | loop / loop / 17ms | 节点 入边3 口型叠加 | 300 / 764x1028 | 说话·害羞 |
| 20 | `shy_trans` | loop / once_then_hold / 8ms | 节点 入边1 | 60 / 764x1028 | 转场 |
| 21 | `smile` | loop / loop / 17ms | **不在状态机** | 120 / 764x1027 | 情绪·微笑 |
| 22 | `smile_speaking` | loop / loop / 17ms | 节点 入边2 口型叠加 | 180 / 764x1028 | 说话·微笑 |
| 23 | `speaking_closed_eye_1` | loop / loop / 17ms | 节点 入边3 口型叠加 | 180 / 764x1028 | 说话·闭眼 |
| 24 | `speaking_closed_eye_2` | loop / loop / 17ms | 节点 入边3 口型叠加 | 300 / 764x1028 | 说话·闭眼 |
| 25 | `speaking_long` | loop / loop / 17ms | 节点 入边3 口型叠加 | 360 / 764x1028 | 说话 |
| 26 | `speaking_loop1` | loop / loop / 17ms | 节点 入边4 口型叠加 | 180 / 764x1028 | 说话 |
| 27 | `speaking_loop2` | loop / loop / 17ms | 节点 入边4 口型叠加 | 240 / 764x1028 | 说话 |
| 28 | `speaking_med` | loop / loop / 17ms | 节点 入边3 口型叠加 | 240 / 764x1028 | 说话 |
| 29 | `speaking_short` | loop / loop / 17ms | 节点 入边4 口型叠加 | 120 / 764x1028 | 说话 |
| 30 | `speaking_trans` | in / once_then_hold / 8ms | 节点 入边1 | 120 / 764x1028 | 说话 |
| 31 | `surprise_speaking` | loop / loop / 17ms | 节点 入边2 口型叠加 | 180 / 764x1028 | 说话·惊讶 |
| 32 | `surprise_trans` | loop / once_then_hold / 8ms | 节点 入边1 | 60 / 764x1028 | 转场 |
| 33 | `thinking_speaking1` | loop / loop / 17ms | 节点 入边5 口型叠加 | 180 / 764x1028 | 说话·思考 |
| 34 | `thinking_speaking2` | loop / loop / 17ms | 节点 入边4 口型叠加 | 300 / 764x1028 | 说话·思考 |
| 35 | `thinking_to_key_point` | loop / once_then_hold / 8ms | 节点 入边1 | 120 / 764x1028 | 转场 |
| 36 | `thinking_to_serious` | loop / once_then_hold / 8ms | 节点 入边1 | 120 / 764x1028 | 转场 |
| 37 | `thinking_trans` | loop / once_then_hold / 8ms | 节点 入边1 | 120 / 764x1028 | 转场 |
| 38 | `trans_smile` | loop / once_then_hold / 5ms | 节点 入边1 | 120 / 764x1027 | 转场 |
| 39 | `trans_standby` | loop / once_then_hold / 21ms | 节点 入边1 | 196 / 764x1028 | 待机·预备 |

### 2.3 转场类剪辑的原包去向（`prob` 来自 graph_config）`[原包]`

| 转场剪辑 | 原包写的去向（概率） |
| --- | --- |
| `angry_trans` | `angry_speaking` (1.00) |
| `closed_eye_trans` | `speaking_closed_eye_1` (0.50)、`speaking_closed_eye_2` (0.50) |
| `sad_trans` | `sad_speaking` (1.00) |
| `serious_to_thinking` | `thinking_speaking1` (0.40)、`thinking_speaking2` (0.60) |
| `shy_trans` | `shy_speaking1` (0.40)、`shy_speaking2` (0.60) |
| `speaking_trans` | `speaking_loop2` (0.60)、`speaking_loop1` (0.40) |
| `surprise_trans` | `surprise_speaking` (1.00) |
| `thinking_to_key_point` | `key_point_speaking` (1.00) |
| `thinking_to_serious` | `speaking_loop2` (0.50)、`speaking_loop1` (0.50) |
| `thinking_trans` | `thinking_speaking2` (0.65)、`thinking_speaking1` (0.35) |
| `trans_smile` | `smile_speaking` (1.00) |
| `trans_standby` | `idle_side_soft_wind` (0.30)、`idle_side_wind` (0.10) |

## 3. 04 场景资产：188 张 PNG 的分组与用途

### 3.1 `scenario_graph.json` 的 6 个有名场景（原包命名）`[原包]`

| 原包 label | 原包 sceneId | 原包 resource | 实测尺寸 |
| --- | --- | --- | --- |
| `computer use` | `computer_use` | `computer_use/computer_uses_mastered.png` | 1398x1125 |
| `sleep_desk` | `computer_use` | `computer_use/sleep_at_work_desk.png` | 1398x1125 |
| `drink_coffee` | `read_books` | `read_books/drinking_coffee.png` | 1398x1125 |
| `stand thinking` | `stand_thinking` | `stand_thinking/stand_thinking.png` | 1398x1125 |
| `whiteboard use` | `whiteboard_use` | `whiteboard_use/white_board_use.png` | 1398x1125 |
| `look at CRT` | `look_at_CRT` | `look_at_CRT/look_at_CRT.png` | 1398x1125 |

场景级转移（`scenario_graph.json`，原包）`[原包]`：

| from | to | 概率 |
| --- | --- | --- |
| `stand thinking` | `look at CRT` | 0.30 |
| `stand thinking` | `computer use` | 0.30 |
| `stand thinking` | `drink_coffee` | 0.10 |
| `stand thinking` | `whiteboard use` | 0.20 |
| `stand thinking` | `sleep_desk` | 0.10 |
| `drink_coffee` | `drink_coffee` | 0.80 |
| `computer use` | `computer use` | 0.80 |
| `sleep_desk` | `sleep_desk` | 0.80 |
| `sleep_desk` | `computer use` | 0.20 |
| `computer use` | `sleep_desk` | 0.10 |
| `computer use` | `stand thinking` | 0.10 |
| `whiteboard use` | `whiteboard use` | 0.80 |
| `whiteboard use` | `stand thinking` | 0.20 |
| `look at CRT` | `look at CRT` | 0.40 |
| `look at CRT` | `drink_coffee` | 0.20 |
| `look at CRT` | `stand thinking` | 0.20 |
| `look at CRT` | `computer use` | 0.20 |
| `drink_coffee` | `stand thinking` | 0.10 |
| `drink_coffee` | `computer use` | 0.10 |

### 3.2 全部 188 张 PNG

| 组 | 张数 | 原包路径 | 原包怎么引用它 | 实测 |
| --- | --- | --- | --- | --- |
| 看 CRT 循环帧 | 180 | `look_at_CRT/look_at_CRT_loop/loop/frame_0000..0179.png` | `spriteforge_clip.json` 的 `frames_dir`/`frame_pattern` | 1070×860 RGB，同一循环 |
| **未被任何 JSON 引用** | 1 | `BG_empty.png` | 无 | 1398x1125 RGB |
| [推断] 场景图 | 1 | `computer_use/computer_uses_mastered.png` | `scenario_graph` 节点 `computer use` | 1398x1125 RGB |
| [推断] 场景图 | 1 | `computer_use/sleep_at_work_desk.png` | `scenario_graph` 节点 `sleep_desk` | 1398x1125 RGB |
| [推断] 场景图 | 1 | `look_at_CRT/look_at_CRT.png` | `scenario_graph` 节点 `look at CRT` | 1398x1125 RGBA |
| [推断] 场景图 | 1 | `read_books/drinking_coffee.png` | `scenario_graph` 节点 `drink_coffee` | 1398x1125 RGB |
| **未被任何 JSON 引用** | 1 | `scenario_backplate.png` | 无 | 1398x1125 RGB |
| [推断] 场景图 | 1 | `stand_thinking/stand_thinking.png` | `scenario_graph` 节点 `stand thinking` | 1398x1125 RGB |
| [推断] 场景图 | 1 | `whiteboard_use/white_board_use.png` | `scenario_graph` 节点 `whiteboard use` | 1398x1125 RGB |

**空房间背景结论**：`BG_empty.png`（1398×1125 RGB）**没有**出现在 `scenario_graph.json` 里，原包未说明它的用途 `[原包-缺失]`；从画面看它就是**空房间（无人的实验室）**，而 `scenario_backplate.png` 与它**像素完全相同**（本次逐像素比对 `identical=True`）`[实测]`。→ 两张都可以当整页底图，用一张即可。

**角色是否是合成的？** `computer_use/sleep_at_work_desk.png` 等图里 Kurisu 是**画进图里的**（原包就把她合成好了）`[实测]`，而 03 的 39 个剪辑是**透明底 RGBA 角色**（50–61% 像素 alpha=0）`[实测]` → 所以有两条路：用 04 的成品场景图，或把 03 的透明角色叠到 `BG_empty` 上。

## 4. 原版 UI / 氛围素材怎么用

| 素材 | 实测尺寸 | 实测通道 | 原包说明 | 本次判断 |
| --- | --- | --- | --- | --- |
| `subtitle_frame_big.png` | 2564×430（≈6:1 横条） | P→RGBA：全透明 0%，半透明 91.0%，不透明 9.0% | **只有 sha256/size，无文字说明** `[原包-缺失]` | `[推断]` **不是空心框**，是一块半透明的做旧锈蚀金属板，顶部有一条黄色警示条 → 适合当**底部字幕底板 / 横向分割装饰条**；因为整体半透明，直接铺在背景上会透出背景 |
| `amadeus_ambient_high_blend.png` | 1672x941 | 全透明 1298785 px（82.5%）、半透明 274567 px、**完全不透明 0 px** | **无文字说明** `[原包-缺失]` | `[推断]` 氛围**光层/辉光叠加**：有效发光区 bbox `(1114, 0, 1629, 680)`（集中在中上偏右的 515x680 区域），叠在房间图上做 CRT 冷光/泛光 |
| `amadeus_ambient_low_blend.png` | 1672x941 | 全透明 1298785 px（82.5%）、半透明 274567 px、**完全不透明 0 px** | **无文字说明** `[原包-缺失]` | `[推断]` 氛围**光层/辉光叠加**：有效发光区 bbox `(1114, 0, 1629, 680)`（集中在中上偏右的 515x680 区域），叠在房间图上做 CRT 冷光/泛光 |
| `assets/audio/sfx/computer_use_keyboard_loop.wav` | 8.25 s | 单声道 44.1 kHz 16 bit，peak 9877/32767（≈-10.4 dBFS）、RMS 395 | 无文字说明 | `[推断]` 打字/操作电脑的循环音效，配 `computer_use/*` 场景 |

**两个氛围层的 alpha 掩码完全相同**（全透明 1,298,785 px / 半透明 274,567 px，逐值一致）`[实测]`，差别只在颜色亮度 → `[推断]` 可以把 high/low 交替叠加做**光晕呼吸/闪烁**，或只用一层当静态泛光。

## 5. 05 头像图集（原包已 webp，直接可用）

原包 `manifest.json` **写明**：`amadeus.companion-atlas.v1` v2026.09.19，9 个情绪 × (idle / speaking / idleStatic)，每个条目给出 `url / size(单元边长) / columns / sequence / durationMs`。`[原包]`

| 情绪 | 状态 | 文件 | 实测尺寸 | 单元 | 列 | 帧数(sequence) | durationMs | 原包 fileBytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `normal` | `idle` | `normal/idle-selected.webp` | 1056x396 | 132 px | 8 | 21 | 2520 | 382568 |
| `normal` | `speaking` | `normal/speaking.webp` | 1056x924 | 132 px | 8 | 49 | 2040 | 781380 |
| `normal` | `idleStatic` | `normal/idle.webp` | 132x132 | 132 px | 1 | 3 | 510 | 17902 |
| `sided_thinking` | `idle` | `sided_thinking/idle.webp` | 132x132 | 132 px | 1 | 3 | 510 | 17216 |
| `sided_thinking` | `speaking` | `sided_thinking/speaking.webp` | 1056x2112 | 132 px | 8 | 123 | 5100 | 2365580 |
| `sided_thinking` | `speakingAlternate` | `sided_thinking/speaking-alternate.webp` | 1056x1320 | 132 px | 8 | 74 | 3060 | 1354200 |
| `sided_surprised` | `idle` | `sided_surprised/idle.webp` | 264x132 | 132 px | 2 | 3 | 510 | 35486 |
| `sided_surprised` | `speaking` | `sided_surprised/speaking.webp` | 1056x1320 | 132 px | 8 | 74 | 3060 | 1225728 |
| `happy` | `idle` | `happy/idle.webp` | 132x132 | 132 px | 1 | 3 | 510 | 17680 |
| `happy` | `speaking` | `happy/speaking.webp` | 1056x1320 | 132 px | 8 | 74 | 3060 | 1242116 |
| `blush` | `idle` | `blush/idle.webp` | 264x132 | 132 px | 2 | 3 | 510 | 35758 |
| `blush` | `speaking` | `blush/speaking.webp` | 1056x2112 | 132 px | 8 | 123 | 5100 | 2147396 |
| `angry` | `idle` | `angry/idle.webp` | 264x132 | 132 px | 2 | 3 | 510 | 35172 |
| `angry` | `speaking` | `angry/speaking.webp` | 1056x1320 | 132 px | 8 | 74 | 3060 | 1310020 |
| `sad` | `idle` | `sad/idle.webp` | 132x132 | 132 px | 1 | 3 | 510 | 17286 |
| `sad` | `speaking` | `sad/speaking.webp` | 1056x924 | 132 px | 8 | 49 | 2040 | 864630 |
| `disappointed` | `idle` | `disappointed/idle.webp` | 132x132 | 132 px | 1 | 3 | 510 | 17640 |
| `disappointed` | `speaking` | `disappointed/speaking.webp` | 396x132 | 132 px | 3 | 3 | 510 | 36720 |

→ `[实测]` 全部为 RGBA、132 px 单元的**横向图集**（8 列或 1 列），在浏览器里用 `background-position` 或 canvas 按 `sequence` 播即可；`idleStatic` 是 3 帧静止图（durationMs 510）。

## 6. 「贴脸大头 / 靠近镜头」到底在哪 —— 定位结论

**在 04 的 `look_at_CRT`，不在 03 的 39 个剪辑里。** 证据链：

1. `[原包]` `scenario_graph.json` 有一个节点，`label = "look at CRT"`，`sceneId = look_at_CRT`，`resource = look_at_CRT/look_at_CRT.png`；它还有**自环 prob=0.40**（原包设计成会长时间停在这一幕）。
2. `[实测]` `look_at_CRT/look_at_CRT.png`（1398×1125）画面就是**她的脸贴着镜头**，占据画面绝大部分——这就是「贴脸大头」。
3. `[原包]` 同目录 `look_at_CRT_loop/spriteforge_clip.json` 把 180 帧 PNG 循环定义成一段 clip（`frames_dir`/`frame_pattern`/`fps`/`stride`），`look_at_CRT_loop.mp4` 是它的视频版。
4. `[实测]` mp4 的 180 帧与 zip 里的 180 张 PNG **逐像素完全一致**（6 帧全分辨率采样 `identical=True`）→ mp4 视频流是冗余的，**唯一独有的是它的音轨**（已抽出 `audio/look_at_CRT_loop.mp4.audio.m4a`，99,235 B）。

补充：`[实测]` 03 的 39 个剪辑**全部是 764×1028 的中景（头到腰）**，没有一个是面部特写；所以开场「贴脸」只能用 `look_at_CRT*`。其它 04 场景图（`computer_use/*`、`stand_thinking/*` 等）里她都是**远景全身**，且已经合成进房间了。

## 7. 原包未说明 / 本次没做的事（如实）

| 项 | 状态 |
| --- | --- |
| 三个 `ASSET_BUNDLE_MANIFEST.json` 的素材描述 | **原包未提供**（只有 path/sha256/size） |
| `BG_empty.png`、`scenario_backplate.png` 的用途 | **原包未引用、未说明**；两者像素完全相同 |
| `subtitle_frame_big.png` / `amadeus_ambient_*_blend.png` / `*.wav` 的用途 | **原包未说明**；本表第 4 节结论标为 `[推断]` |
| `smile` / `sad` 两个剪辑为何不在状态机 | **原包未说明**（实测：graph 37 节点 vs 39 剪辑） |
| 口型叠加（`mouthOverlays` + `mouth_config`）的运行时画法 | **未复现**；只确认了 39 个基础帧里**已经含口型动画**（`speaking_med` 抽帧可见嘴部变化） `[实测]` |
| 7552 帧中未解码的部分 | **只解码了 468 帧**（每剪辑均匀 12 帧，用于印样）；其余 7084 帧未解码，脚本可全量重跑 |
| 03 剪辑的整体「故事顺序」 | 原包只给**概率状态机**，没给剧本；播放顺序需自己决定 |

