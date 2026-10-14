# spec-runtime.md —— `_kurisu-full/web/` 运行期产物的字段说明

> 目的：让播放器**直接读**这些 JSON 就能跑起来，不必再回去读原包的 `graph_config.json` /
> `scenario_graph.json` / `runtime_manifest.json`。字段除注明外全部来自原包**逐字**，没有猜测值。
> 本文件由「素材与规格线」维护（2026-10-14）。

---

## 0. 目录清单

| 路径 | 内容 | 谁产出 |
|---|---|---|
| `web/scenes/*.webp` | **7 张 04 场景背景**（空房间 backplate + 6 个活动位），q80 | 本线（`tools/build_scene_webps.py`） |
| `web/scenes/_sizes.json` | 上面 7 张的体积实数表（含源 PNG 字节、sha256） | 本线 |
| `web/statemachine.json` | **角色状态机**：37 节点 / 87 边（03 剪辑之间的自动游走） | 素材线 |
| `web/scenarios.json` | **房间活动位**：6 场景 / 19 边 + 起始节点 + 空房间 + 节奏常数 | 素材线（本线补了 4 个字段） |
| `web/atlas/` `boot/` `medium/` `poster/` `mouth/` | 39 个剪辑的图集 / 引导档 / 中档 / 静帧 / 口型补丁 | 素材线 |
| `web/crt/` | 180 帧特写的多种分页与分辨率（`crt_full_*.pageNN.webp`、`look_at_CRT.boot24.webp`、`native_still`） | 素材线 |
| `web/opening/` | 开场编码的 7 个候选（A–G，不同帧数/步长/高度），供选型 | 素材线 |
| `web/meta/<clip>.json` | 每个剪辑的逐帧元数据（39 个） | 素材线 |
| `web/meta/spec-runtime.md` | 本文件 | 本线 |

---

## 1. `statemachine.json` —— 角色状态机

顶层：

| 字段 | 含义 |
|---|---|
| `format` | `"amadeus.kurisu.statemachine.v1"` |
| `source` | 原包路径 `03-character-kurisu/.../graph_config.json` |
| `root` | **起始节点 = `"idle"`**（原包 `isRoot: true`） |
| `node_count` / `edge_count` | 37 / 87 |
| `host_triggered_entries` | 8 个**只能由宿主（页面）触发**的入口剪辑名：`angry_trans, closed_eye_trans, sad_trans, shy_trans, speaking_short, speaking_trans, surprise_trans, trans_smile`。它们只能从 root 出发的**第一跳**进入（见 §4 的 `prob=0` 规则），自动游走永不选它们。 |
| `clips_not_in_graph` | `["sad","smile"]` —— 作者端有这两个剪辑，但图里没有对应节点 → **不进自动游走**，只能手动播。 |
| `loop_mode_counts` | `{loop:27, once_then_hold:12}` |
| `frame_interval_counts` | `{"21":6, "5":1, "8":10, "17":22}` —— 每帧毫秒的分布 |

`nodes[]`（37 条）：

| 字段 | 含义 |
|---|---|
| `id` | 原包节点 id（如 `_8ms718k`），仅作溯源 |
| `clip` | **剪辑名**（如 `idle`）—— 播放器用它去 `manifest.clips[clip]` 取图集 |
| `is_root` | 是否根节点（只有 `idle` 为 true） |
| `loopMode` | `"loop"` 或 `"once_then_hold"` |
| `phase` | 原包的 phase（`loop` / `in`） |
| `frameIntervalMs` | **每帧时长**（毫秒），不是帧率。`fps = 1000/frameIntervalMs`（另给 `fps` 字段） |
| `frames` | 该剪辑的**源帧数**（未隔帧） |
| `frame_size` | 源单帧像素尺寸。**实测有 4 种变体**：`764×1028 / 960×1028 / 764×1026 / 764×1027`。⚠️ 缩放一律按 `canvas_size`（764×1028）算，**不要用单帧尺寸**，否则 960 宽的 `idle_closed_eye` 会让角色忽大忽小 |
| `opaque_bbox` | 该剪辑的不透明包围盒，可用来做居中/裁边 |
| `incoming_prob_positive` | 入边里 `prob>0` 的条数（用于判断可达性） |
| `has_mouth_profile` | 是否有口型档（`openness` / `anchor_track`） |
| `atlas` / `boot` / `poster` | 图集文件名（相对 `web/`）、引导档、静帧 |
| `atlas_bytes` / `tier` | 体积与档位（`featured` 等） |

`edges[]`（87 条）：

| 字段 | 含义 |
|---|---|
| `from` / `to` | **剪辑名**（播放器直接用这两个值选下一段），不是节点 id |
| `from_id` / `to_id` | 原包节点 id，溯源用 |
| `prob` | 转移权重。**运行时按出边总和归一化**，不必加到 1 |

---

## 2. `scenarios.json` —— 房间活动位（"发呆"状态）

顶层：

| 字段 | 含义 |
|---|---|
| `format` | `"amadeus.kurisu.scenarios.v1"` |
| `source` | 原包 `04-visual-runtime/.../scenario_graph.json` |
| `node_count` / `edge_count` | 6 / 19 |
| `start` / `startSceneId` | **起始节点 = `"stand thinking"` / `stand_thinking`**。源码结论：空闲进入场景态时从 **stand_thinking** 开始，**不是** `look at CRT`。 |
| `empty_room` | `{webp: "scenes/BG_empty.webp", role:"backplate", ...}` —— **她不在时就显示这张空房间**。它是 backplate **层**，不是图里的节点。 |
| `dwell` | `{inactivitySeconds:60, staticHoldSeconds:45, staticHoldMaxSeconds:60}` —— **最后一次语音播完后 60s** 才进入空闲场景；每个 pose 停 **45~60s（随机）**；动画要**播完当前循环**再换 pose。 |
| `crt_loop` | 特写循环：180 帧 / 1070×860 / 30fps / 6.0s |
| `extra_assets` | 不在图里、但运行时要用的图（`BG_empty`）。 |

`nodes[]`（6 条）：

| 字段 | 含义 |
|---|---|
| `id` | 原包节点 id |
| `label` | **场景名（键）**，`edges` 用这个值互相引用 |
| `sceneId` | 原包 `sceneId`。注意 `sleep_desk` 的 `sceneId` 是 `computer_use`，`drink_coffee` 的是 `read_books` —— **`label` 才是唯一键** |
| `resource` | 原包 PNG 路径（溯源） |
| `png_size` | `[1398,1125]` |
| `webp` | **实际要加载的文件**（相对 `web/`），本线已产出 |
| `src_mode` | 源 PNG 的色彩模式（`RGB` / `RGBA`） |
| `self_loop_prob` | 自环概率；`stand thinking` **没有自环**（见边表总和 = 1.0） |

`edges[]`（19 条）：`from`/`to` 用 **label**，另有 `from_id`/`to_id` 溯源，`prob` 同 §1。

实测自环：`computer use 0.8 / sleep_desk 0.8 / drink_coffee 0.8 / whiteboard use 0.8 / look at CRT 0.4 / stand thinking 无`。

---

## 3. `web/scenes/` —— 7 张房间背景

| 文件 | 场景键 | 源 PNG 字节 | WebP 字节 | 模式 |
|---|---|---|---|---|
| `scenes/BG_empty.webp` | （backplate） | 1,665,593 | 84,020 | RGB |
| `scenes/computer_use/computer_uses_mastered.webp` | computer use | 1,690,992 | 85,614 | RGB |
| `scenes/computer_use/sleep_at_work_desk.webp` | sleep_desk | 1,673,664 | 83,174 | RGB |
| `scenes/read_books/drinking_coffee.webp` | drink_coffee | 1,676,223 | 84,642 | RGB |
| `scenes/stand_thinking/stand_thinking.webp` | stand thinking | 1,702,769 | 86,624 | RGB |
| `scenes/whiteboard_use/white_board_use.webp` | whiteboard use | 1,683,901 | 84,014 | RGB |
| `scenes/look_at_CRT/look_at_CRT.webp` | look at CRT | 2,124,797 | 89,436 | **RGBA** |
| **合计** | | **12,217,939 (11.65 MB)** | **597,524 (0.57 MB)** | 压缩到 4.9% |

要点：

* **源用的是 zip 里的 PNG**（`04-visual-runtime/assets/scenarios/runtime/**/*.png`），
  **不是** `_kurisu-full/scenes/*.webp` —— 后者已是有损 WebP，再编码就是二次有损。
  实测：本脚本从 PNG 编码出的 7 个文件与 `_kurisu-full/scenes/*.webp` **逐字节完全相同**，
  说明那边本来就是同一套 q80 参数编出来的，可互相印证。
* **`look_at_CRT` 必须保留 alpha**（实测 `alphaMin = 0`，真的有全透明像素）；
  其余 6 张 `alphaMin` 不存在/不用 alpha → 编码成 RGB 更省。
* **`scenario_backplate.png` 与 `BG_empty.png` 逐字节相同**
  （两者 sha256 都是 `2732c57a30adb909…`）→ 按站主口径**只产出一份**，即 `scenes/BG_empty.webp`。
  `scenarios.json` 里原先把 `scenes/scenario_backplate.webp` 当成独立文件，
  现已改成指回 `BG_empty` 并标 `deduplicated:true, emitted:false`（避免 404）。
* 场景图**自带 CRT 玻璃外框/暗角/扫描线**，使用时先按 §5 的 `sourceCrop` 裁掉外圈玻璃再拉伸。

---

## 4. 运行时语义（照抄原版，别自己发明）

**`prob` 的用法规约**（`how-it-works` §2.2）：
* `prob > 0` = 自动转移权重，**运行时按出边总和归一化**。
* **`prob = 0` = 手动触发边**：自动遍历**永远不会选**；只有"从起始节点出发的**第一跳**"允许走 `prob=0` 边。
  这就是 §1 里 `host_triggered_entries` 那 8 个剪辑的进入方式。

**`loopMode`**：
* `loop` —— 循环播。
* `once_then_hold`（12 个）—— 播一遍**停在末帧**；到末帧即触发换节点。
  过渡类剪辑在"没在说话"时会**停在末帧等她开口**。

**`frameIntervalMs` 是每帧时长**，不是 fps；推进由剪辑播完这个事件驱动（原版是 PIXI ticker）。

**两种状态并存**（决定"她在屏幕上还是在场景里"）：
* **常态**：`BG_empty` backplate + **03 角色精灵**（她动、房间不动）。
* **场景态**：空闲 `inactivitySeconds=60s` 后进入，**隐藏角色层**，改播 04 的成品场景整图
  （她已画在画里）。节点之间是**硬切**（换贴图，无 crossfade）。

**唯一的过渡常数**：`_fadeDur = 0.35s`，**线性**、**只改 alpha**（无 scale/translate），
且只用于**角色态 ↔ 场景态**切换。进入方向：角色硬切消失、场景淡入；退出方向才是真交叉。

**❗ 没有相机动画**：全库无 zoom/dolly/camera 实现；实拍桌面是 stage 最底层、从头到尾都在。
**禁止**对整屏/桌面底图做 scale/translate（会连桌面带键盘一起缩放，与平面实拍透视对不上）。
若页面想要"贴脸→整张书桌"的平滑感，只能做**屏内** alpha 交叉，并标注"我方扩展"。

---

## 5. 几何常数（合成场景图/角色时要用）

| 常数 | 值 | 来源 |
|---|---|---|
| 底图 | 1672×941 | `wallpaper/crt_config.json:img_size` |
| **CRT 多边形** | 14 点手写，非矩形；包围盒 x 550..1136, y 195..638（586×443，比例 1.3228） | `crt_config.json:24-81` |
| cover 变换 | `scale=max(sw/iw, sh/ih)`；`t.x=(sw-iw*scale)/2`；`t.y=(sh-ih*scale)/2` | `wallpaper_scene.js:16-25` |
| **内屏裁剪** | `[x0,y0,w,h]`(归一化) = `[113/1398, 119/1125, 1182/1398, 902/1125]` → 内屏 1182×902（比例 **1.3102**） | `scene_assets.py:62-67` |
| 角色落位 | `scale = min(W*0.64/764, H*0.90/1028)`；`x = 0.52W`；`y = bottom − max(3, 1.2%H)`；anchor `(0.5,1)` | `renderer.js:797-825` |
| 角色画布 | 764×1028（**不是单帧尺寸**） | `spriteforge_mouth_config.json:canvas_size` |
| 字幕板 | 源 2564×430；`w=clamp(W*0.72,180,W−24)`；`h=clamp(w/5.963,34,0.16H)`；贴底边 | `wallpaper_scene.js:176-196` |
| 层序（下→上） | 实拍桌面 → CRT 多边形遮罩内[**空房间 backplate → 角色 → 字幕板 → 场景整图**] → 氛围光/ADD 辉光/扫描线/暗角 | `wallpaper_scene.js:1822-1830` |

---

## 6. 已知缺口 / 注意事项（如实）

1. **`sad` / `smile` 两个剪辑不在状态机里** → 自动游走永不播到，需要手动触发。
2. `scenarios.json` 的 `start` / `empty_room` / `dwell` 是本线**追加**的（原始导出没有）。
   如果 `scenarios.json` 会被上游脚本重新生成，**请把这三个字段并进那个生成器**，否则会被覆盖。
   （本线改前已备份 `scenarios.json.bak`。）
3. `look at CRT` 的 `sceneId` 是 `look_at_CRT`，同时 `web/crt/` 下还有**同一节点的 180 帧动画**；
   静态图与动画是两件事，别混用：场景态节点切静态整图，特写开场用 180 帧。
4. 本目录下 `web/opening/` 的 A–G 是**候选编码**，未定选型；`web/scenes/_sizes.json` 才是本线确定的产出。
