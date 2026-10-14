# HOW IT WORKS — Amadeus 的动画到底是怎么做出来的

> **本文的纪律**：每一条结论都带出处。标签含义：
> - `[源码:PATH:L行]` = 上游开源仓库 `github.com/Code-Amadeus/Amadeus`，**已实测 checkout 到本机**
>   `E:\DeepSeek1\work\_amadeus-src`，commit **d8fc3690387dd1022d8e9940e86639203d27097a**（2026-10-14，
>   `fix(render): pace ambient actions from speech completion (#204)`；shallow clone，只含该 commit 的历史）。
> - `[原包:FILE]` = 三个 ZIP 里的原始 JSON/素材（本机 `E:\DeepSeek1\work\_kurisu-full\meta_json\`，权威）
> - `[实测]` = 本次在本机跑出来的数字（脚本/命令写在文末）
> - `[推断]` = 没有直接证据，只有间接迹象；**推断不能当事实用**

---

## 0. 一句话答案（先看这个）

原包这套动画 = **预渲染的帧序列（KTX2，卡通角色 39 剪辑 / 7552 帧，透明底 RGBA）
+ 一张实拍桌面的背景大图 + 一个写死的 CRT 屏幕多边形**
，用 **PixiJS 分层合成**：背景照片铺满屏幕 → 在 CRT 多边形里贴"空房间底图"→ 再在同一个多边形里贴角色帧
→ 上面叠字幕板/氛围光/扫描线。角色的"活"来自三件事：
① 一个 **37 节点 / 87 边的概率状态机**在每段剪辑播完时掷骰子换剪辑；
② 每剪辑一个 **frameIntervalMs**（17ms ≈ 58.8fps）的帧时钟；
③ 一个 **只在"静音"时出现的闭嘴补丁**（把**一帧完整的闭嘴画面**按嘴部锚点对齐、再用椭圆遮罩只露出嘴）。
**没有骨骼、没有 Live2D 运行时、没有相机推拉、没有眨眼/呼吸生成器。**

Live2D 在 Amadeus 里是 **2026-10-08 才加进来的、显式选择的实验性"另一个美术后端"**，
与这套帧序列是**并行方案**，不是它的生成器（详见 §5）。

---

## 1. 画面是怎么合成出来的

### 1.1 结论

**不是 3D，不是透视投影，是"一张实拍底图 + 硬编码的 CRT 屏幕多边形 + 在多边形内分层贴图"。**
顺序与坐标映射全部来自一份可读源码，公式如下（全部以**屏幕像素**为单位）。

### 1.2 唯一的全局变换：`coverTransform`

壁纸底图（实拍桌面）按 `cover` 方式铺满屏幕（保持比例、裁掉溢出），得到唯一一份"图坐标 → 屏幕坐标"变换：

```js
// [源码:render/web/wallpaper_scene.js:16-25]
scale = max(screenW / imgW, screenH / imgH)
t.x   = (screenW - imgW*scale) / 2
t.y   = (screenH - imgH*scale) / 2
```

`img_size` 取自 **[源码:wallpaper/crt_config.json:2-5]** = `[1672, 941]`。

### 1.3 CRT 屏幕矩形是**硬编码的多边形**，不是算出来的

**[源码:wallpaper/crt_config.json:24-81]** 里手写了 14 个点的 `crt_polygon`（图像坐标系，单位 px），
外加 `crt_corners`（4 点近似）、`nixie_rect`（翻页钟 152,490,280,68）、
`ambient_rect`（1370,120,220,480）、`keyboard_input_toggle_rect`、`keyboard_composer_rect`、
`crt_bg`/`crt_radius`/`scanline_alpha`/`vignette_alpha`/`crt_ctrl_pts`。

投影到屏幕：

```js
// [源码:render/web/wallpaper_scene.js:2113-2123]
crt_px[i] = { x: poly[i][0]*t.scale + t.x,  y: poly[i][1]*t.scale + t.y }
// [源码:render/web/wallpaper_scene.js:2125-2133]
crt_bounds = AABB(crt_px)          // {x,y,width,height,right,bottom}
// [源码:render/web/wallpaper_scene.js:2146-2151]
mask = 用 crt_px 连成的填充多边形 (PIXI.Graphics)
```

`mask` 被同时用作**角色层的遮罩**和**扫描线层的遮罩**：

```js
// [源码:render/web/renderer.js:1921-1924]
setCharacterViewportMask(mask) { this._sprite.container.mask = mask; this._modelContainer.mask = mask; }
// [源码:render/web/wallpaper_scene.js:1829]   this.scanlineLayer.mask = this.mask;
// [源码:render/web/wallpaper_scene.js:2156]   callRender("setCharacterViewportBounds", [bounds]);
```

→ **她真的被"关在屏幕矩形里"**：角色精灵是一个多边形 mask 的子节点，越出 CRT 玻璃的部分直接不画。

### 1.4 角色在屏幕里的缩放/落位公式（逐字来自源码）

```js
// [源码:render/web/renderer.js:797-825]  SpriteRenderer._applyCurrentTransform
fitWidth  = clipConfig.canvasWidth  || texture.width      // 有 canvas_size 就用它，不用单帧尺寸
fitHeight = clipConfig.canvasHeight || texture.height
b = viewportBounds                                          // = crt_bounds
maxW = b.width  * 0.64
maxH = b.height * 0.90
scale       = min(maxW / fitWidth, maxH / fitHeight)
sprite.scale = scale
sprite.x     = b.x + b.width  * 0.52        // 水平：CRT 宽度的 52%
sprite.y     = b.bottom - max(3, b.height * 0.012)   // 垂直：脚底贴 CRT 底边往上 1.2%
// sprite.anchor = (0.5, 1.0)  // 底边居中  [源码:render/web/renderer.js:60]
```

`canvasWidth/canvasHeight` 从 `spriteforge_mouth_config.json` 的 `canvas_size` 来：
**[源码:render/spriteforge_animator.py:640-649]** → `canvasWidth=764, canvasHeight=1028`
（[原包:meta_json/spriteforge_mouth_config.json] `"canvas_size": [764, 1028]`）。

> 这条很重要：**帧尺寸不统一**（实测 764×1028 / 960×1028 / 764×1026 / 764×1027 四种），
> 但缩放一律按 `canvas_size` 算，所以 960 宽的 `idle_closed_eye`（右侧 196 列全透明）
> 不会把角色缩小，只是多出透明边。契约里写明了这一点
> **[源码:docs/character_pack_authoring.md:64-68]**。

### 1.5 场景图 / 底图怎么贴进 CRT（`placementMode = "crt_screen"`）

场景图（04 那 188 张 1398×1125）**自带 CRT 玻璃罩/暗角/扫描线**，所以先按归一化裁剪框
把外圈玻璃切掉，再**拉伸**到 `crt_bounds`：

```python
# [源码:wallpaper/scene_assets.py:62-67]
_SCENARIO_DEFAULT_SOURCE_CROP_NORM = [113/1398, 119/1125, 1182/1398, 902/1125]
#   -> 内屏 x 113..1295, y 119..1021  = 1182 x 902   (宽高比 1.310)
# [源码:wallpaper/scene_assets.py:462]  "placementMode": "crt_screen"
```
```js
// [源码:render/web/wallpaper_scene.js:1604-1634]  归一化裁剪 -> PIXI.Rectangle
// [源码:render/web/wallpaper_scene.js:1681-1688]  crt_screen: 直接拉伸
sprite.scale.set(bounds.width/tw, bounds.height/th);  sprite.x = bounds.x; sprite.y = bounds.y;
```
CRT 多边形包围盒在图坐标里是 x 550..1136, y 195..638 → 586×443（宽高比 1.323）。**1.310 ≈ 1.323**，
两者对得上，这就是"场景图是给这块屏幕准备的"的像素级证据 `[实测]`。

### 1.6 完整的 z 序（自下而上）

来自两处：初始化时的 `addChild` 次序 **[源码:render/web/wallpaper_scene.js:1822-1830]** +
插入式重排 **[源码:render/web/wallpaper_scene.js:660-706]** + 背景插到 0 号位
**[源码:render/web/wallpaper_scene.js:1901-1906]**：

| 层 | 内容 | 出处 |
|---|---|---|
| 0 | `desktopScene.bg` = 实拍桌面大图（cover 铺满） | `wallpaper_scene.js:1885-1906` |
| 1 | `mask`（renderable=false，只当遮罩） | `1822` |
| 2 | `scenarioRuntime.backplateSprite` = 空房间底图（裁掉玻璃后拉伸进 CRT，被 mask 裁） | `649-658`, `685-688` |
| 3 | **角色层**：`_sprite.container`（含嘴部补丁）与 `_modelContainer`（Live2D，默认隐藏） | `renderer.js:56-61`, `667`, `1921-1928` |
| 4 | `wallpaperSubtitle.container` = 原版生锈字幕板 + 文本 | `694-697`, `176-196` |
| 5 | `scenarioRuntime.container` = 场景图/场景帧序列（被她"占用"时盖住她） | `699-705` |
| 6 | `staticOverlay` | `2153-2154` |
| 7 | `ambientLayer{ ambientLowSprite, ambientSprite(delta) }` 氛围光 | `1824`, `1966-1969` |
| 8 | `glowLayer`（**ADD 混合**，随嘴动的辉光） | `1819-1821`, `2295-2308` |
| 9 | `scanlineLayer`（被 mask 裁的扫描线噪声） | `1829`, `2443+` |
| 10 | `bottomVignette`（底部柔影） | `1827-1828`, `1862-1874` |

字幕板几何（原版 `subtitle_frame_big.png` 2564×430，宽高比 5.963）：
```js
// [源码:render/web/wallpaper_scene.js:176-196]
width  = clamp(b.width*0.72, 180, b.width-24)
height = clamp(width/5.963, 34, b.height*0.16)
x = b.x + (b.width-width)/2 ;  y = b.bottom - height
```
→ **贴在 CRT 屏幕底边，高约为屏高 16%**，与交接文档 §07「屏高 84.5% 起、高 11.5%」是同一件事 `[实测]`。

### 1.7 "桌面那层"到底是什么（Q4）

| 素材 | 尺寸 | 角色 |
|---|---|---|
| `assets/images/amadeus_desktop_wallpaper.png` | **1672×941** | **一张实拍/渲染好的整幅照片**（书桌、翻页钟、Dr Pepper、NEPHONE、键盘、CRT 机身印 AMADEUS、白板、风扇、海报）。是"底层背景"，被 cover 铺满整屏 |
| `wallpaper/crt_config.json` | — | 这份照片上的**手写坐标表**：CRT 屏多边形、翻页钟矩形、氛围光矩形、键盘/输入框矩形 |
| `assets/images/amadeus_ambient_{low,high}_blend.png` | 1672×941 | **两张独立的氛围光层**（同一套 alpha 掩码，只差亮度），叠在照片上做 CRT 冷光呼吸 |
| `assets/images/subtitle_frame_big.png` | 2564×430 | 字幕底板（做旧锈蚀金属板 + 顶部黄警示条） |
| `assets/scenarios/runtime/BG_empty.png` | 1398×1125 | **空房间底图**（无人实验室，自带 CRT 玻璃外框）；**就是 `scenario_backplate`** |
| `assets/scenarios/runtime/<scene>.png` | 1398×1125 | 6 张"她已经画在房间里的成品图"（scenario 状态机节点） |

**桌面层是"一张实拍图"，不是分层的**：只有背景一张照片，氛围光是**额外叠加**的 2 张半透明 PNG，
CRT 屏幕矩形是**硬编码在 json 里的多边形**（不是算出来的、也不是从图里检测的）
**[源码:wallpaper/crt_config.json:24-81]**。

**`BG_empty.png` 与 `scenario_backplate.png` 为什么逐像素相同（上一轮遗留疑问）——已解**：
```python
# [源码:wallpaper/scene_assets.py:317-320]
for name in _SCENARIO_BACKPLATE_CANDIDATES:            # ['BG_empty.png', 'bg_empty.png', ...]
    source_candidate = src_root / name
    if source_candidate.exists():
        copied = _copy_backplate_source(source_candidate, runtime_root / "scenario_backplate.png")
        if copied: return copied, _SCENARIO_DEFAULT_SOURCE_CROP_NORM
```
`scenario_backplate.png` 是**运行时把 `BG_empty.png` 拷过去生成的副本**。
[原包:recon.json] 里两条路径分别是 `assets/scenarios/runtime/BG_empty.png` 与
`assets/scenarios/runtime/scenario_backplate.png`，正好符合 `src_root = _RUNTIME_SCENARIOS`
（**[源码:wallpaper/scene_assets.py:396-398]**）时的行为 → **不是巧合，是同一个文件** `[源码+实测]`。
所以上一轮"原包未引用 BG_empty"的说法要修正：**它就是 backplate**，只是名字被换了一层。
另外 `scenario_graph.json` 确实**不引用**它——backplate 是**层**，不是节点
**[源码:wallpaper/scene_assets.py:438-463]**。

**两个状态并存**（这是理解"她到底在屏幕上还是场景里"的关键）：
- **常态**：只显示 03 的角色精灵，叠在 `BG_empty` backplate 上（`_saveAndHideCharacter`/`_restoreCharacter`
  见 **[源码:render/web/wallpaper_scene.js:1701-1745]**）。她动、房间不动。
- **"发呆/活动"态**：空闲 `inactivitySeconds`（默认 **60s**）后 `scenarioRuntime.activate()`
  **[源码:wallpaper/scene_assets.py:440]**，此时**把角色层整个隐藏**（alpha→0），
  改成播 04 的成品场景图（她已被画在画里），节点切换是**硬切**（换 texture，没有 crossfade）
  **[源码:render/web/wallpaper_scene.js:1209-1224, 1231-1258]**。

---

## 2. 她为什么"活着"

### 2.1 谁在 tick

`SpriteRenderer` 在构造时注册了 **PIXI ticker**（不是 `setInterval`）：

```js
// [源码:render/web/renderer.js:137]    this._startIdleTicker();
// [源码:render/web/renderer.js:993]    app.ticker.add((delta) => { ... });
```
状态机的"推进"由**剪辑播完**这个事件触发：
```js
// [源码:render/web/renderer.js:1061-1065]  剪辑走到末帧/回到 0 帧 -> _notifyCycleComplete(emotion)
// [源码:render/web/renderer.js:1078-1087]  _notifyCycleComplete -> cycleCompleteHandler(emotion)
// [源码:render/web/renderer.js:1342-1350]  SpriteForgeRuntime.onCycleComplete(label) -> _advanceNow()
// [源码:render/web/renderer.js:1352-1376]  _advanceNow(): forced > pendingExpression > _nextAutoNode()
```
`SpriteForgeRuntime` 通过 `setCycleCompleteHandler` 挂上。Python 侧
`SpriteForgeAnimator` 只在"引擎没有前端运行时"时才跑自己的等价线程
（**[源码:render/spriteforge_animator.py:179-180, 281-290, 820-892]**）；真实壁纸/渲染页里
**tick 归 JS**。

### 2.2 `prob` 怎么用

```js
// [源码:render/web/renderer.js:1534-1549]  _nextAutoNode(fromId)
edges = graph.edges.filter(e => e.from==fromId && prob > 0)
                 .filter(e => standbyAllowed || label(e.to) !== 'trans_standby')
if (!edges.length) return fromId;              // 死胡同：原地不动
total = Σ prob ;  r = Math.random() * total ;  累减取第一个 r<=0 的边
```
- `prob > 0` = 自动转移权重，**运行时按出边总和归一化**，不必加到 1
  **[源码:docs/character_pack_authoring.md:94-95]**。
- `prob = 0` = **手动触发边**，自动遍历永不选；只有"从起点出发的**第一跳**"允许走 0 边
  **[源码:render/web/renderer.js:1511-1513]**，**[源码:docs/character_pack_authoring.md:96-97]**。
- **`trans_standby`（侧身转身）有 30 秒静音闸门**：只有在"最后一次语音播放结束起 ≥30s"之后才允许自动进入
  **[源码:render/web/renderer.js:1535-1540]**，**[源码:render/spriteforge_animator.py:62-63]**
  （`_IDLE_STANDBY_ENTRY_LABEL='trans_standby'`, `IDLE_STANDBY_DELAY_SEC=30.0`）。
  显式 trigger / 说话进场**不等**这个闸门。
- 根节点 = `graph_config.json` 里 `isRoot` 的那个 → **[原包:meta_json/graph_config.json]** 实测 `root=idle`
  （37 节点 / 87 边）。

### 2.3 `frameIntervalMs` 怎么用：**每帧时长**（剪辑级常量）

```js
// [源码:render/web/renderer.js:1023-1032]
const interval = this._frameIntervals[emotion] || (cfg && cfg.frameIntervalMs) || 150;
elapsed += Math.min(app.ticker.deltaMS, 100);
if (elapsed < interval) return;
const steps = Math.floor(elapsed / interval);   // 补帧，最多 4 步（非采样模式）
elapsed -= steps * interval;
```
- 一个剪辑内所有帧共用同一个 `interval` → 语义是「**每帧停留多少 ms**」。
- 由 Python 从 manifest 的 `clip["frameIntervalMs"]` 灌进来
  **[源码:render/spriteforge_animator.py:518, 523]**。
- `1000/fps` 得来，fps 还能被 per-label 倍率放大
  **[源码:tools/package_spriteforge_character.py:73-81, 207-208]**（例：`trans_smile` ×4）。
- **实测 39 个剪辑全表**（[原包:meta_json/runtime_manifest.json]）：
  | 特征 | 值 |
  |---|---|
  | 帧率 | **17ms** ×22 个剪辑（58.8fps）、**21ms** ×6（47.6fps）、**8ms** ×10（125fps）、**5ms** ×1 |
  | 时长 | 最短 0.48s（`angry_trans`/`sad_trans`/`shy_trans`/`surprise_trans` 60 帧@8ms）、最长 **12.55s**（`idle_closed_eye` 738 帧@17ms） |
  | `loopMode` | `loop` **27 个**、`once_then_hold` **12 个**（`speaking_trans`/`closed_eye_trans`/`thinking_trans`/`thinking_to_serious`/`thinking_to_key_point`/`serious_to_thinking`/`trans_smile`/`sad_trans`/`shy_trans`/`surprise_trans`/`angry_trans`/`trans_standby`） |
  | 帧数 | 60 / 120 / 180 / 194 / 196 / 240 / 290 / 300 / 360 / 600 / 738 |
  | 总帧 | **7552**（manifest `frameCount`，与 ZIP 内 `.ktx2` 数量一致） |

### 2.4 `loopMode = once_then_hold` 怎么处理

```js
// [源码:render/web/renderer.js:1024, 1037-1039, 1042-1043]
const onceThenHold = cfg.loopMode === 'once_then_hold';
if (onceThenHold && this._frameIdx >= frames.length - 1) break;      // 停在末帧
if (onceThenHold) this._frameIdx = Math.min(this._frameIdx + 1, frames.length - 1);
// [源码:render/web/renderer.js:1061-1062]
if (onceThenHold && this._frameIdx >= frames.length - 1) this._notifyCycleComplete(emotion);
```
即：**播一遍 → 停在最后一帧 → 立刻通知状态机换节点**。
契约 **[源码:docs/character_pack_authoring.md:51-53]**：
`once_then_hold` = "play once and hold the last frame until the graph runtime advances or releases it"。

**特殊闸门**：过渡类剪辑（`TRANSITION_HOLD_LABELS` = speaking_trans / closed_eye_trans /
thinking_trans / thinking_to_serious / thinking_to_key_point / trans_smile / sad_trans / shy_trans /
surprise_trans / angry_trans，**[源码:render/spriteforge_animator.py:116-121, 156-161]**）
如果在**没在说话**时播完，会**停在末帧等她开口**，而不是继续掷骰子：

```js
// [源码:render/web/renderer.js:1344-1348]
if (!this.speechActive && this._has("transitionHoldLabels", label)) {
  this.transitionHoldActive = true;  this.sprite.holdFrame(-1);   // -1 = 末帧
  return;                          // 不推进
}
```
Python 侧同一逻辑在 **[源码:render/spriteforge_animator.py:836-862]**。

### 2.5 说话/情绪的路由（她是"被叫醒"的，不是自己决定说）

- 说话开始：`setSpeaking(true)` → 若当前节点不是说话路线，就跳
  `defaultSpeakingTriggerLabel = "speaking_short"`；
  若当前在 `idle/idle1/idle2/idle_mic_wind/idle_str_wind/idle_closed_eye/speaking_short|med|long`
  之一，有 **18%**（`_CLOSED_EYE_SPEAKING_CHANCE=0.18`）概率改走 `closed_eye_trans` → 闭眼说话
  **[源码:render/web/renderer.js:1287-1299]**，**[源码:render/spriteforge_animator.py:43-45, 653-666]**。
- 说话结束：**不是立刻回 idle**，而是
  ```js
  // [源码:render/web/renderer.js:1316-1338]
  this.sprite.holdClosedFrame();                        // 先"闭嘴定帧"
  postSpeechHoldActive = true; setTimeout(..., postSpeechHoldSec*1000 /* 1.0s */)
  → 之后 _playNode(_postSpeechReleaseNode(label) || root)
  ```
  `_postSpeechReleaseNode`：非情绪说话（serious/default/closed_eye/thinking）→ 直接回 root；
  情绪说话（smile/sad/shy/surprise/angry）→ 走 `postSpeechEmotionLabelByIntent`
  （**[源码:render/spriteforge_animator.py:102-105]** 只有 `smile→smile`, `sad→sad`），
  并在该节点停留其整段时长后再掷骰子 **[源码:render/web/renderer.js:1551-1577]**。
- 情绪触发的"进场"：`trigger(label)` 会先把 label 换成
  `emotionEntryByIntent[intent]`（smile→`trans_smile`、sad→`sad_trans`、shy→`shy_trans`、
  surprise→`surprise_trans`、angry→`angry_trans`）**[源码:render/spriteforge_animator.py:68-74]**，
  再 BFS 找第一跳 **[源码:render/web/renderer.js:1190-1219, 1496-1532]**。
- 触发 label 的别名与随机路由：`_TRIGGER_ALIASES` / `_RANDOM_TRIGGER_ROUTES` /
  `semanticTriggerDefaults` **[源码:render/spriteforge_animator.py:677-682]**；
  **随机化由后端做一次**，前端只是兜底，这样 GUI 和壁纸不会各掷一次
  **[源码:render/spriteforge_animator.py:678-682]** + **[源码:render/web/renderer.js:1255-1258]**。

### 2.6 口型叠加的**精确算法**（这是最容易被讲错的一块）

#### (a) 坐标系先说清

- 坐标系 = **帧像素**，**原点在帧中心**，+y 向下。宽度/高度是 px。
  [源码:tools/detect_mouth_masks.py:202-207]
  ```python
  cx_c = ex - w/2      # ex 是图里的像素列
  cy_c = ey - h/2      # 嘴在偏上 -> cy_c 是负数
  ```
  [原包:meta_json/spriteforge_mouth_config.json] `expressions.neutral = {cx:4.0, cy:-196.0, width:34.0, height:18.0, curve:0.2}`
  → 在 1028 高的画布里，嘴在 `y = 1028/2 - 196 = 318`，与实测的嘴部位置一致 `[实测]`。

#### (b) 补丁到底有多大？——**就是一整帧闭嘴画面**，不是 34×18

这是最关键的一条，**上一轮交接文档 §06 把它说成"34×18 的小补丁"，是错的**：

```python
# [源码:tools/package_spriteforge_character.py:294-302, 316, 422-429]
source  = _authoring_path(workspace, profile["root"], profile["phase"], names[closed_index])
texture = _sidecar(source, suffix)          # ★ 直接拿【作者包里的那一张闭嘴 PNG】转成 KTX2
...
overlays[label] = (texture, runtime_anchor)
...
mouth_entries[label] = [relative.as_posix()]     # ★ 列表长度 = 1
```
```python
# [源码:render/spriteforge_animator.py:591-596, 608]
overlay_paths = pack.mouth_overlay_paths.get(label, ())
frame_urls    = [self._url(path) for path in overlay_paths]
js_cfg["frameUrls"] = frame_urls
```

**实测（本机，权威）**：[原包:meta_json/runtime_manifest.json] 的 `mouthOverlays` 有 **16 个 label，
每个都只有 1 个路径**，而且路径就是该剪辑自己的某一帧（或作者显式指定的另一剪辑的一帧）：

| label | mouthOverlays[0] | 含义 |
|---|---|---|
| `speaking_loop1/2`、`speaking_short/med/long`、`smile_speaking`、`sad_speaking`、`thinking_speaking1/2`、`speaking_closed_eye_1/2` | `textures/<clip>/loop/kurisu_speaking_loop0001.ktx2` | = 该剪辑**自己的第 0 帧**（帧数组下标 0） |
| `key_point_speaking` | `.../kurisu_speaking_loop0155.ktx2` | 该剪辑自己的第 154 帧（`PREFER_OWN_CLOSED_FRAME`） |
| `shy_speaking1/2` | `textures/shy_trans/loop/kurisu_shy_trans0001.ktx2` | **借别的剪辑的帧**（`closed_source`） |
| `surprise_speaking` | `textures/surprise_trans/loop/...` | 同上 |
| `angry_speaking` | `textures/angry_trans/loop/...` | 同上 |

**所以 34×18 是什么？** 是**遮罩椭圆**的尺寸来源（检测出来的嘴部框），不是贴图尺寸：
```js
// [源码:render/web/renderer.js:960-966]
wHalf = max(1,width)/2 * 1.8 * maskWidthMul
hHalf = max(1,height)/2 * (1.0 + 1.5*amplitude) * maskHeightMul
g.drawEllipse(localX, maskLocalY, wHalf, hHalf)
```
默认 `amplitude = silenceMaskAmplitude = 0.75` → 椭圆 **全宽 = 1.8×34 = 61.2px，全高 = 18×2.125 = 38.25px**。

#### (c) `openness` / `anchor_track` / `runtime_overlay_anchor` / `expressions.neutral` 各自干什么

| 字段 | 来源 | 运行时用途 |
|---|---|---|
| `expressions.<set>.{cx,cy,width,height,curve}` | v1 检测器算的"该口型集的默认嘴框" **[源码:tools/detect_mouth_masks.py:94-207]** | 作为 JS cfg 的**兜底几何**；`sourceCx/sourceCy` 初值 **[源码:render/spriteforge_animator.py:566-578]** |
| `profiles.<label>.{cx,cy,width,height}` | v2 逐帧追踪的 profile 级默认 **[原包:meta_json/spriteforge_mouth_config.json]** | `anchorTrack` 缺项时的兜底 |
| `profiles.<label>.anchor_track[i] = {cx,cy,width,height,score}` | 每帧追踪到的基础帧嘴部位置（`score`≈0.978~0.998 置信度） | **遮罩椭圆的位置**：按**当前基础帧下标**取 **[源码:render/web/renderer.js:969-985]**；同时决定补丁的平移量 |
| `profiles.<label>.runtime_overlay_anchor` | **闭嘴源帧的**嘴部锚点（打包时写入）**[源码:tools/package_spriteforge_character.py:308-314]** | 补丁对齐的**基准点**（`sourceAnchors[0]`）**[源码:render/spriteforge_animator.py:610-620]** |
| `profiles.<label>.openness[i]` | 逐帧开口度 0~1（ROI 内 L2 色彩距离归一化）**[源码:tools/detect_mouth_masks.py:210-240]** | **只用于两件事**：① 挑 `opennessByFrame` 最小的那帧做"闭嘴定帧"的候选 ② 纹理采样计划里 pin 住这帧。**注意：当前 shipped 包把它喂给 JS 的是另一路（见下）** |
| `profiles.<label>.closed_frame_idx` | `argmin(openness)` 或人工修正 **[源码:tools/detect_mouth_masks.py:304]** | pin 帧 + `holdClosedFrame` 的**首选**（但会被 argmin 覆盖，见下） |

**JS 侧实际喂进去的是两套 `openness`**（很容易看错）：
```python
# [源码:render/spriteforge_animator.py:606-609]
js_cfg["opennessByFrame"] = profile.get("openness", [])       # 真曲线，长度 = 基础帧数
js_cfg["openness"]        = [0.0 for _ in frame_urls]         # ★ 长度 = 补丁帧数 = 1，全是 0
```
于是：
```js
// [源码:render/web/renderer.js:846-865]
openness = cfg.openness                      // = [0.0]
targetValue = silenceClose ? 0.0 : this._mouthValue
bestIdx = argmin |openness[i] - targetValue| // => 恒为 0（只有一帧）
```
**→ 实际运行时永远只用 `mouthOverlays[label][0]` 这一张补丁。**
`openness` 数组的存在是设计上的扩展位（允许多个开口度变体），**当前包只发了 1 张**。

#### (d) 补丁画在哪、按什么缩放、alpha 怎么叠

**先给结论：补丁不平移缩放；它按"锚点对齐"整体平移，alpha 恒为 1，靠椭圆遮罩裁出嘴；"amplitude" 只改椭圆高度，不改透明度。**

```js
// [源码:render/web/renderer.js:924-967]  _drawMouthMask(amplitude, cfg)
const th      = textureHeight(this.sprite.texture)          // 基础帧高（=1028）
const anchor  = this._getMouthAnchor(cfg)                   // = anchorTrack[_activeFrameIdx]
localX = anchor.cx
localY = anchor.cy - th/2                                   // 帧中心系 -> sprite 局部系
overlayH = textureHeight(this._mouthOverlay.texture)        // 补丁帧高（shipped 包里 = th）
if (cfg.overlayAlign === "canvas") { overlay.x = 0; overlay.y = 0; }     // ★ 特例，见下
else {
  overlay.x = localX - sourceCx
  overlay.y = localY - (sourceCy - overlayH/2)
}
```
因为 shipped 包里 **补丁帧与基础帧同高**（12 个 label 的补丁就是同一剪辑的一帧；
`shy_speaking1/2`/`surprise_speaking`/`angry_speaking` 借的是 `shy_trans`/`surprise_trans`/`angry_trans` 的一帧，
而那些剪辑同样是 764×1028 标准尺寸 `[实测]`），`overlayH === th`，于是
```
overlay.x = cx - sourceCx
overlay.y = cy - sourceCy
```
—— 也就是 **[源码:docs/mouth_sync_system_notes.md:300-305]** 写的
`overlay.x = currentAnchorX - sourceAnchorX; overlay.y = currentAnchorY - sourceAnchorY`。
**语义 = "让补丁上那个（sourceCx, sourceCy）像素，落在当前帧的（cx, cy）位置上"** ——
逐帧补偿头部移动，所以嘴不会飘。

`overlayAlign = "canvas"` 的特例：补丁保持 (0,0) 不做平移（用于 `key_point_speaking`，
因为它的闭嘴源来自同一画布且头基本不动，避免漂到手指上）
**[源码:render/spriteforge_animator.py:126-133]**，**[源码:docs/mouth_sync_system_notes.md:215-226]**。

**可见性（`mode = "silence_close"`，实测 shipped 值）**：
```js
// [源码:render/web/renderer.js:855-890]
silenceThreshold = 0.08
shouldClose = !speaking || mouthValue <= 0.08
overlay.visible = shouldClose
maskAmp = silenceMaskAmplitude ?? 0.75
```
→ **只有"没在说话"或"音量 ≤ 0.08"时才显示闭嘴补丁**；在说话且音量 >0.08 时，
补丁隐藏，**看到的是基础帧自带的画好的口型**。

**所以"口型"其实是两层拼起来的**：
1. **说话中**：基础序列帧自己带的口型动画（作者画的）；
2. **静音间隙**：拿一张闭嘴整帧 + 椭圆遮罩临时盖上去，避免"明明没声音，她嘴还张着"。
为什么不用"跳到闭嘴帧"——文档明确否掉了（会整体跳帧、头发/身体/手不连续）
**[源码:docs/mouth_sync_system_notes.md:142-161]**。

#### (e) 哪些节点**不**参与口型

```python
# [源码:render/spriteforge_animator.py:107-124, 586-588]
_MOUTH_SYNC_LABELS = _SPEAKING_PERFORMANCE_LABELS - _SPEAKING_ENTRY_TRANSITION_LABELS
if label not in _MOUTH_SYNC_LABELS: skip     # 过渡节点不戴嘴罩
```
`_SPEAKING_PERFORMANCE_LABELS` = {speaking_trans, speaking_loop1/2, speaking_short/med/long,
closed_eye_trans, speaking_closed_eye_1/2, thinking_speaking1/2, key_point_speaking,
smile_speaking, sad_speaking, shy_speaking1/2, surprise_speaking, angry_speaking}；
从中减去进场过渡 = {speaking_trans, closed_eye_trans, thinking_trans, thinking_to_serious,
thinking_to_key_point, serious_to_thinking, trans_smile, sad_trans, shy_trans, surprise_trans, angry_trans}。
→ **剩 16 个**，正好等于 `mouthOverlays` 的 16 个 label `[实测]`。
（`smile`/`sad` 不在内 —— 它们是"说话后情绪停留"用的静态循环，故意不戴嘴罩
**[源码:render/spriteforge_animator.py:122-124]**。）

#### (f) 两个已发现的坑（实现方必看）

1. **说话结束的"闭嘴定帧"会无视 `closed_frame_idx`**：
   ```js
   // [源码:render/web/renderer.js:662-687]  holdClosedFrame()
   let idx = cfg.closedFrameIdx ?? NaN;
   // 若 opennessByFrame 非空，则【无条件】改成 argmin(opennessByFrame)
   if (openness.length) { ...bestIdx...; if (bestIdx >= 0) idx = bestIdx; }
   ```
   而 `SpriteForgeRuntime.setSpeaking(false)` 调的正是它
   **[源码:render/web/renderer.js:1319]**。
   **实测矛盾**：`speaking_loop1` 的 `closed_frame_idx = 0`（→ 补丁帧），
   但 `openness` 的 argmin = **150**。也就是说运行时停的那一帧（150）**不是**它当作"闭嘴画"的那一帧（0）。
   这正是文档 §2「openness 检测可能挑错闭嘴帧」记录的问题
   **[源码:docs/mouth_sync_system_notes.md:188-198]**。
   → **我方实现时，"闭嘴源"请以 `mouthOverlays` 指向的那一帧 / 人工确认的帧为准，别用 `argmin(openness)`。**
2. `_getMouthAnchor` 用的是**基础帧下标** `_activeFrameIdx`（可能已被纹理采样重映射）
   **[源码:render/web/renderer.js:972]**，而 `opennessByFrame`/`closedFrameIdx` 用的是**源下标**。
   开 `RENDER_TEXTURE_SAMPLING` 时两者会错位 —— 这也是原项目 `docs/frame_video_full_acceptance_2026-10-13.md`
   特意强调"嘴型继续使用当前显示的 sourceIndex"的原因 `[源码:docs/frame_video_full_acceptance_2026-10-13.md:44]`。

### 2.7 眨眼 / 呼吸 / 鼠标跟随（Q2 最后一块）

**Sprite 路线：三者都没有代码，也没有素材。**

证据（不是"我没找到"，是"全库检索 + 全帧实测"）：

1. **全仓检索** `blink|eyeblink|breath|mouse.?follow|cursor` 于 `**/*.js`：
   唯一命中"眨眼/呼吸"实现的地方是 **vendor 里的 Live2D 库**
   `render/web/vendor/pixi-live2d-display.cubism4.min.js:1`
   （里面有 `CubismEyeBlink` / `CubismBreath`）。**Sprite 路径零命中** `[实测:grep]`。
2. `render/web/live2d_character.js:163` 的注释只提到"呼吸几何不能每帧改取景"，**没有实现呼吸**。
3. **全帧实测**（本次沿用并复核了本机已有的 `tools/14_mouth_blink.py` 结果，
   输出在 `web/checks_mouth_blink.json`，**每帧都解码，不是抽样**）：
   | 剪辑 | 帧数 | 眼白亮像素 min~max | 闭眼事件 |
   |---|---|---|---|
   | `idle` | 120 | 3547 ~ 3879 | **0 个** |
   | `idle1` | 120 | 3546 ~ 4755（第 29-39 帧是**变亮**的鼓包，不是变暗） | **0 个** |
   | `smile` | 120 | 5073 ~ 5256 | **0 个** |
   | `sad` | 120 | 3950 ~ 4736 | **0 个** |
   判定阈值 = 0.5×中位数，一个"闭眼"应该在眼白计数上**骤降到接近 0**；四条曲线都没有这种骤降。
   目视复核印样 `sheets/eyes_idle1_strip.png`（120 帧眼框逐个放大）也确认眼睛全程睁开。

   → **结论：原包这套素材【不能眨眼】，也没有"眨眼"这个动作。**
4. **闭眼是"状态"，不是"眨眼"**。[原包:meta_json/runtime_manifest.json] `[实测]`：
   `idle_closed_eye` 738 帧 / 17ms / **12.55 秒** 的独立全身循环；
   `closed_eye_trans` 120 帧 / 8ms / 0.96 秒 **once_then_hold**（正面→闭眼的过渡）；
   `speaking_closed_eye_1`(180)、`_2`(300) 是闭眼说话的完整循环。
   **它们姿势/呼吸相位都不同，不能把帧插进别的剪辑**（插进去会跳帧）。
   最长可以做到"长时间闭眼打盹"，最短的"闭眼过渡"也要 **0.96 秒** —— 眨眼的物理时长是 0.1~0.15 秒，
   **量级差 6~10 倍，拿来当眨眼一定很怪**。
5. **鼠标跟随 / 侧看**：Sprite 路径**没有鼠标跟随**（`crt_canvas_surface.js` 里的 `cursor:` 全是 CSS 样式）。
   原项目用**素材**表达"看别处"：
   - 场景态：`scenario_graph.json` 的 `look at CRT` 节点（她凑近看镜头）`[原包:meta_json/scenario_graph.json:43-50]`；
   - 角色态：`trans_standby`（196 帧 / 21ms / 4.12s / once_then_hold）**正面转侧面**，
     之后进 `idle_side_*` 系列（180/180/600 帧）**[原包:meta_json/runtime_manifest.json]**，
     触发条件是"≥30 秒没语音"的自动转移 **[源码:render/web/renderer.js:1535-1540]**。

**Live2D 路线**才有眨眼/呼吸：由 `pixi-live2d-display` 的 Cubism 组件按模型自带参数驱动
（`render/web/vendor/pixi-live2d-display.cubism4.min.js`），
且 **Amadeus 自己的 Sprite 素材与它无关**（§5）。

---

## 3. "贴脸大头 → 拉远"开场到底是什么

### 结论：**(b) + 部分 (d)，但不是相机动画**

分三层回答，每层都有证据：

**(1) "贴脸大头"是真素材，而且是"场景态"的一张整图，不是角色包里的特写。**
- 03 角色包 **39 个剪辑全部是「头到腰」中景构图（以画布 764×1028 为基准，只有 4 种尺寸微差），
  没有任何特写 / 任何镜头运动**
  **[原包:meta_json/runtime_manifest.json]** `[实测:39 个剪辑帧尺寸表]`。
- 特写只存在于 04：
  - 静帧 `assets/scenarios/runtime/look_at_CRT/look_at_CRT.png` = **1398×1125**，
    `[实测:肉眼确认]` 内容就是她俯身贴到镜头前，整幅图自带 CRT 玻璃外框（见 `scenes/look_at_CRT/look_at_CRT.webp`）；
  - 帧序列 `assets/scenarios/runtime/look_at_CRT/look_at_CRT_loop/loop/frame_0000..0179.png`
    = **1070×860 / 180 帧 / 30fps / 6.06s**（[原包:meta_json/spriteforge_clip.json]
    `{"type":"spriteforge_graph_clip","role":"loop","source":"...look_at_CRT_loop.mp4","source_fps":30.0,"frame_count":180,"stride":1}`）。
- 它是**场景状态机的一个节点**：`label="look at CRT"`、`sceneId="look_at_CRT"`、
  `resource="look_at_CRT/look_at_CRT.png"`，自环 prob 0.40，由 `stand thinking` 以 0.30 进入
  **[原包:meta_json/scenario_graph.json:43-50, 52-58, 132-136]**。

**(2) `look_at_CRT_loop` 那 180 帧**不是"拉远"，是**原地凑近的循环**。
`[实测:肉眼逐帧看 20 帧印样 sheets/crt_loop_mp4_sheet.png + 本地 web/checks_crt.json]`：
从 f0001 到 f0180，她的脸始终占满画面，只是轻微前后/左右晃动和眼神变化，**没有镜头后退**。

**(3) 原项目没有任何"相机推拉/缩放"代码。**
- 全库检索 `zoom|dolly|camera|intro|pull back|push in`：Spawn 到的全是无关词
  （"introduction"、代码注释里的"introduced"、`pointer_wheel` 的鼠标位置等），
  **没有任何镜头动画实现** `[实测:grep]`。
- 场景节点切换是**硬切**：`_showNode` 只是把 texture 换掉
  **[源码:render/web/wallpaper_scene.js:1231-1258]**，`_setTexture` 直接给 sprite 换图；
  唯一的淡入淡出发生在**整个场景层的进入/退出**
  **[源码:render/web/wallpaper_scene.js:896-937, 1209-1224]**。
- 背景层永远是同一份 cover 变换，没有任何随时间变化的 `scale`（`_imageTransform()` 无时间参数）
  **[源码:render/web/wallpaper_scene.js:2097-2102]**。
- 想看"拉远"效果，原项目只能靠**两个取景不同的场景图硬切**：
  `look_at_CRT`（贴脸）→ `stand thinking` / `computer use`（全身中景）。

**(4) 那视频里的"拉远"从哪来？**
- 站主录屏的那 1.7s 一帧是贴脸、15s 一帧已经是全身中景 —— **中间恰好是"切镜"能造成的感觉**
  `[实测:docs-plan/07 的 f00/f04 + 本次复核 _video-frames/sheet-open.png]`。
  抽帧是每 ~1s 一帧，**无法区分"0.3 秒的推轨"和"一帧硬切"**，所以这里只能这样下结论：
  **有直接证据支持"场景节点切换（硬切或场景层淡入淡出）"，没有任何证据支持"相机推拉"。**
- 我**没有**在仓里找到任何宿主（Electron/Lively 窗口）层面的窗口/相机缩放动画
  （`docs/windows_wallpaper_lifecycle.md`、`wallpaper_engine_bridge.py` 里没有这类实现）
  —— 这条是**"查不到"**，见 §⑦。

**(5) 推荐做法（回答任务里的 (d)）**：
> 用 `look_at_CRT` 的**前 20~30 帧**（她是循环，取开头即可）当开场，
> 让它**按 `crt_screen` 规则贴进 CRT 屏**；然后**交叉淡入** `stand thinking` / `computer use` 的整图
> （或直接切到 03 的角色精灵 + `BG_empty` backplate）。
> **必须在交付说明里标明这是"用素材拼接的效果"，不是原项目的相机动画。**
> 依据：`look_at_CRT_loop` 前后帧几乎一样（可安全截取任意前缀）`[实测]`；
> 原项目场景切换本身就有淡入淡出可用 **[源码:render/web/wallpaper_scene.js:919-932]**；
> 而且交接文档 §07 第 1 条已经预授权了这条路径。

---

## 4. （已并入 §1.7）桌面那一层

见 **§1.7**：一张实拍整图（`amadeus_desktop_wallpaper.png`，1672×941）
+ 手写坐标表（`wallpaper/crt_config.json`）
+ 2 张独立氛围光 PNG + 1 张字幕板 PNG。
**CRT 屏幕矩形是硬编码多边形，不是算出来的**。

补两条：
- 底图可被环境变量替换：`AMADEUS_WALLPAPER_PATH`
  **[源码:wallpaper/scene_assets.py:176-182]**；不在仓内时会被拷到 `runtime/wallpaper/runtime_wallpaper_bg.png`
  **[源码:wallpaper/scene_assets.py:31, 198-209]**。
- `amadeus_desktop_wallpaper.png` 是**唯一被 git 收进仓的**美术图，且明确声明是
  "the built-in wallpaper and Electron CRT fallback. Its existing hard references are intentional."
  **[源码:assets/README.md:13-14]**。

---

## 5. Live2D 关系：**并行方案，不是生成器**

### 结论
**这套素材（KTX2 帧序列 + spriteforge + 状态机）不是"预渲染的 Live2D"，至少没有任何证据；
而 Amadeus 自己的 Live2D 支持是后来才加的、与它并行的另一个美术后端。**

### 证据

1. **Live2D 在 Amadeus 里是显式 opt-in 的实验后端，默认仍是 Sprite：**
   > 「日期：2026-10-08。分支：`codex/live2d-character-renderer`。**默认仍为 Sprite；Live2D 是显式选择的实验性美术后端。**」
   **[源码:docs/live2d_character_visuals.md:3]**
   「**形象渲染方式** 中选择 Live2D」、回切 Sprite、Core 不随 public 源码分发
   **[源码:docs/live2d_character_visuals.md:11-19]**。
2. **时间线对不上**：角色包 manifest 里写死了构建版本
   **[原包:meta_json/runtime_manifest.json]** `"version": "2026.08.29"`，
   而 Live2D 分支是 **2026-10-08** —— **晚了 6 周**。包不可能是它生成的。
3. **打包工具完全不认识 Live2D**：`tools/package_spriteforge_character.py` 的输入是
   **SpriteForge 工作区里的 PNG 帧目录 + `downloads/*.mp4`（只用来取 fps）**
   **[源码:tools/package_spriteforge_character.py:26-37, 147-183, 194-219]**，
   帧目录名是 `frames_alpha_2x_gmfss` / `frames_alpha_fx_snapghost_200c` /
   `frames_alpha_2x_lerp` / `frames_alpha`（`_2x`/`gmfss`/`lerp` = **视频帧插值变体**），
   产物只有 `runtime_manifest.json` + `graph_config.json` + `spriteforge_mouth_config.json` + `textures/*.ktx2`
   **[源码:tools/package_spriteforge_character.py:432-448]**。全流程无 Live2D 依赖。
4. **契约明确把"作者工程/PNG 序列/源视频/插值产物"排除在运行时之外**，反向说明这些才是来源：
   > 「SpriteForge or another authoring tool may produce that pack, but **authoring projects, PNG sequences,
   > source video, interpolation output, and editor layout data are not part of the runtime format.**」
   **[源码:docs/character_pack_authoring.md:1-5]**
   > 「**SpriteForge authoring PNGs, videos, interpolation output, and QA renders stay in SpriteForge** or
   > another source workspace. Amadeus consumes only the runtime manifest, graph, mouth config, and indexed KTX2 textures.」
   **[源码:assets/README.md:102-104]**
5. **Live2D 走的是完全不同的一套代码路径**，不是替换 Sprite 的内部实现：
   `render/web/model_character.js`（"一个显式模型 adapter 构造边界；当前只构造 Live2D"）、
   `render/web/live2d_character.js`（SDK 加载/表情/参数/嘴型/RenderTexture）、
   `render/web/vendor/pixi-live2d-display.cubism4.min.js` + `assets/core/live2dcubismcore.min.js`；
   与 `SpriteRenderer` 并列成两个 container，同一个 stage 里二选一显示：
   ```js
   // [源码:render/web/renderer.js:1926-1928]
   getModelCharacterContainer() { return this._modelContainer; }
   getCharacterLayers() { return [this._sprite.container, this._modelContainer]; }
   // [源码:render/web/renderer.js:1938-1947]  setMode(): 只切可见性
   ```
   架构表也写明 Cubism 先画到 RenderTexture 再交给普通 Pixi 层接受裁剪
   **[源码:docs/live2d_character_visuals.md:40]**。而且 Live2D 模式下**会关掉前景/相关活动场景**
   **[源码:docs/live2d_character_visuals.md:49]** —— 二者互斥而非互补。
6. Live2D 自带 physics 是旧格式且有 motion 告警；E-mote 未实现
   **[源码:docs/live2d_character_visuals.md:51-53, 71]**。

### 不知道的部分（诚实标注）
- **SpriteForge 用它那些 `downloads/*.mp4` 源视频之前，动画最初是怎么产出的**（手绘？
  3D？AI 视频？Live2D 导出？），**在本仓查不到**——SpriteForge 是**另一个应用、不开源**
  （**[源码:docs/character_pack_authoring.md:130-134]**：
  「Amadeus does not provide a graph editor in Settings… The existing SpriteForge graph editor
  is expected to remain a separate authoring application rather than becoming part of the Amadeus runtime GUI.」）。
  我检索了 `RIFE|gmfss|GMFSS|snapghost|interpolat|pre-render` 等关键词于 `docs/`：**没有源动画生成方式的说明** `[实测:grep]`。
  帧目录名提示是"**视频 → 抠像(alpha) → 2x/4x 帧插值 → 风格化 ghost**"的**后处理**链条，
  但**上游视频的来源查不到** —— **不要把"SpriteForge 用 Live2D 做的"当事实写进交付**。

---

## 6. 音量/语音驱动口型：**PCM 的 RMS，10ms 窗，×3.75，首窗给 0.12 保底**

这条**不是文本→口型序列，也不是先算好口型表**；是**实时把即将写进声卡的 PCM 窗口算 RMS**，
然后当作一个 0~1 的"嘴张开度"信号广播出去。

```python
# [源码:tts/playback.py:84, 87]
self.volume_multiplier = 3.75      # 增益
self.send_interval     = 0.01      # 10 ms 窗

# [源码:tts/playback.py:186-206]  每个窗【先发口型值，再写声卡】
window_samples = max(1, int(round(rate * self.send_interval)))
for offset in range(0, len(audio_chunk), window_samples):
    chunk = audio_chunk[offset : offset + window_samples]
    ...
    if mouth_envelope:
        minimum = first_mouth_minimum if offset == 0 else None   # 首窗 minimum=0.12
        self._emit_mouth_value_for_audio(chunk, minimum=minimum)
    self.stream.write(chunk.tobytes())

# [源码:tts/playback.py:225-240]
rms          = sqrt(mean(audio_chunk ** 2))
mouth_value  = min(1.0, rms * self.volume_multiplier)
if minimum is not None and mouth_value > 0.0:
    mouth_value = max(float(minimum), mouth_value)      # 避免首字"嘴不动"
```
（`first_mouth_minimum=0.12` 的调用点：**[源码:tts/playback.py:297, 971, 1032, 1446, 1518]**；
播放结束/中断时 `publish_mouth_value(0.0)` **[源码:tts/playback.py:213, 284, 322, 1055, 1063]**。）

路由与消费链：
```
PCM 10ms 窗 -> RMS × 3.75 -> MouthSignalRouter.publish_mouth_value
   [源码:tts/mouth_signal.py:55-70]         （primary=本地渲染；compatibility=VTube Studio，可缺可失败）
-> HeadlessRenderBridge.set_mouth_value -> render.mouth 事件
   [源码:render/headless_bridge.py:114-116]
-> SpriteForgeAnimator.set_mouth_value -> engine.set_mouth_value
   [源码:render/spriteforge_animator.py:371-376]
-> JS renderer.setMouth(v) -> SpriteRenderer._updateMouthLayer()
   [源码:render/web/renderer.js:394-397, 838-903]
```
关键性质（**[源码:docs/mouth_sync_system_notes.md:26-88]**）：
- 发布时机是**"PCM 提交顺序契约"**，不是声学/显示时刻的测量；蓝牙延迟不要盲目补偿。
- 每个非空 10ms 窗**各自**发布一次，**不能**把合并写只在写完后发一次；
- `MouthSignalRouter` 的任一 sink 失败都**不能**影响音频播放。
- 壁纸模式复用同一个事件：`MouthSignalRouter → HeadlessRenderBridge → render.mouth → 本地与壁纸两个 SpriteForge 渲染器`
  **[源码:docs/mouth_sync_system_notes.md:80-88]**。

**而 `openness[]` 不是音量算的** —— 它是**作者侧预分析**的"该帧嘴巴张开程度"
**[源码:tools/detect_mouth_masks.py:210-240]**，用来挑闭嘴帧。运行时音量走的是**另一条路**
（闭嘴补丁的显示/隐藏开关）。**两者不要混为一谈**：
`openness` = 逐帧静态属性；`mouthValue` = 实时音量。

Live2D 后端的嘴型是另一套（参数 ID + gain + smoothing_ms）
**[源码:render/web/live2d_character.js:215-229, 348-352]**，**[源码:render/visual_profile.py:76-96]**，
与本节的 Sprite 嘴型无关。

---

## ⑦ 宿主窗口层与过渡（宿主到底有没有“缩放/拉远”动画）

> 本节专门回答“我们要不要做相机动画”。
> 读完的文件：`docs/windows_wallpaper_lifecycle.md`（全 285 行）、
> `wallpaper/wallpaper_engine_bridge.py`、`wallpaper/windows_desktop_layer.py`（全 373 行）、
> `render/web/wallpaper_engine_bridge.js`、`electron/src/main/index.ts`（窗口尺寸相关全部命中）、
> `render/web/wallpaper_scene.js` 的过渡与 tick。

### ⑦.1 结论（一句话）

**宿主（桌面 App / Lively / Wallpaper Engine）对窗口、画布、整屏场景做过的动画量 = 0。
没有缩放、没有位移、没有窗口尺寸动画。**
页面内部唯一存在的过渡是 **一个 0.35 秒的线性 alpha 交叉淡入**，而且
**只用于「角色态 ↔ 场景态」的切换，不用于场景节点之间** —— 节点→节点是**硬切**（源码里连淡出都刻意去掉了）。

### ⑦.2 宿主层：没有任何窗口/画布动画（源码级证据）

1. **`docs/windows_wallpaper_lifecycle.md` 全 285 行逐行读完**：整篇是「启动 / 挂载 / 恢复 / 拥有权」生命周期，
   **没有一句提到窗口、画布或场景的缩放/位移/淡入动画**。
   唯一与“节奏”有关的是 §“Ambient character cadence”（**[源码:docs/windows_wallpaper_lifecycle.md:222-235]**）：
   > 「The idle scenario activates **60 seconds** after the most recent voice playback ends…
   > Once active, **each pose samples a 45–60 second dwell** before the graph can choose the next pose.
   > **Animated resources keep playing at their authored rate and finish the current loop before changing poses.**」
   —— 讲的是「多久换一个 pose」，**不提任何过渡动画**。
2. **挂载方式就决定了“宿主不可能做过场”**：Lively **只被挂一次**同一个 URL 项目：
   > 「the Windows helper connects to Lively's named-pipe RPC… **writes the Amadeus URL project and mounts it.
   > Only then does Electron create its existing interactive Slice.**」
   **[源码:docs/windows_wallpaper_lifecycle.md:39-41]**
   之后所有 pose 变化都发生在**同一个页面内部**（`_goNext` → `_showNode`）。
   ∴ **Wallpaper Engine / Lively 自带的“场景切换过渡”设置根本不参与**（页面没换，对宿主而言没有发生任何场景事件）。
   Lively 是**未修改的第三方 GPL-3.0 程序**
   **[源码:docs/windows_wallpaper_lifecycle.md:128-130]**，Amadeus 只是把它当布景宿主。
3. **`wallpaper/windows_desktop_layer.py`（全 373 行）：只有“把窗口钉在桌面层”的一次性操作 + 一个重连轮询**：
   `SetParent` / `SetWindowPos(..., SWP_NOACTIVATE | SWP_FRAMECHANGED)`（**[源码:wallpaper/windows_desktop_layer.py:260-300]**），
   加 `watch_window_on_desktop()` 的 **0.2 秒轮询**（窗口被踢下桌面层时重新贴回去：
   `while user32.IsWindow(hwnd): ... time.sleep(max(0.2, interval_s))`，**[源码:wallpaper/windows_desktop_layer.py:334-355]**）。
   **是“把窗口钉住”，不是动画**。
   该文件对 `animat|transition|fade|scale|zoom|opacity|duration` 全部零命中 `[实测:grep]`。
4. **`electron/src/main/index.ts` 里的 `setBounds` 全是静态布局**：
   命中行 727 / 918 / 922 / 1447 / 1894 / 2445 / 2447，都是子视图 / Work 预览 / CRT Canvas / Slice 窗口的
   **viewport bounds 一次性设置**（例：`surface.view.setBounds(surface.viewportBounds)`），
   **没有任何时间参数、无缓动、无逐帧**。
5. **`render/web/wallpaper_engine_bridge.js` 里改 `style` 的只有一个调试 HUD**（右上角小方块，
   `el.style.position/top/right/...`，**[源码:render/web/wallpaper_engine_bridge.js:775-786]**），**不是画面过渡**。
   同文件 `weSpriteTransitionLimit`（**[源码:render/web/wallpaper_engine_bridge.js:434-451]**）是性能**裁剪**：
   把过渡类动画的帧数截断（甚至直接跳过），**反而是在减少过渡**，跟“做一个过渡动画”相反。

### ⑦.3 但页面内部**确实存在一个 0.35s 线性交叉淡入**（可照抄的唯一数值）

**常量：`_fadeDur = 0.35`（秒）**
```js
// [源码:render/web/wallpaper_scene.js:551-557]   场景运行时的过渡状态
_fadeAlpha: 1,
_fadeDur: 0.35,        // ★ 全仓唯一的过渡时长常数
_fadeT: 0,
_fadeDir: 0,
_fadingOut: false,
_fadeCharacterIn: false,
```
```js
// [源码:render/web/wallpaper_scene.js:967-992]
_startFade(dir) {                       // dir=+1 淡入场景层, -1 淡出场景层
  this._fadeDir = dir;  this._fadeT = 0;
  this._fadeAlpha = dir > 0 ? 0 : 1;    this.container.alpha = this._fadeAlpha;
}
_tickFade(dt) {                         // 每帧调用（tick 在 L771）
  if (this._fadeDir === 0) return;
  this._fadeT = Math.min(1, this._fadeT + dt / Math.max(0.01, this._fadeDur));
  this._fadeAlpha = this._fadeDir > 0 ? this._fadeT : (1 - this._fadeT);
  this.container.alpha = this._fadeAlpha;              // ★ 只改 alpha
  if (this._fadeDir < 0 && this._fadeCharacterIn) {
    this._setCharacterFadeProgress(this._fadeT);       // ★ 反向：角色 alpha 0->1
  }
  if (this._fadeT < 1) return;
  this._fadeDir = 0;
  if (this._fadingOut) { this._fadingOut = false; this._completeDeactivate(); }
  else if (this._pendingNode) { /* 死代码，见下 */ }
}
```
- **缓动曲线：没有。**`alpha = t` 就是**线性**（**[源码:render/web/wallpaper_scene.js:977]**）；
  起作用的是 `Math.min(1, t + dt/0.35)` 这一句。**没有任何 scale / translate / blur。**
- **进入场景态**（`activate` → `_completeActivate`）：先**立即**把角色层 alpha 置 0（`_saveAndHideCharacter`），
  场景容器 `alpha=0` 后 `_startFade(1)` 淡入 0.35s
  **[源码:render/web/wallpaper_scene.js:896-937, 1701-1721]**。
  → 进入方向**不是交叉淡入**（角色是硬切没的，只有场景在淡入）。
- **退出场景态**（`deactivate`）：`_restoreCharacter(0)` + `_fadeCharacterIn = true` + `_startFade(-1)`；
  淡出过程中角色 alpha 同步 0→1，结束后 `_setCharacterFadeProgress(1)`
  **[源码:render/web/wallpaper_scene.js:912-925, 979-981, 994-1009, 1723-1745]**
  → **只有退出方向才是真正的 0.35s 交叉淡入**。
- 该常量在**全仓只出现两处**（定义 + 使用）`[实测:grep _fadeDur|fadeDur|transitionDuration|animationDuration]`。

### ⑦.4 场景节点 → 节点：**硬切，连淡出都被刻意去掉**

```js
// [源码:render/web/wallpaper_scene.js:1288-1299]
_goNext() {
  const next = this._chooseNext(this.currentNodeId);
  if (!next) return;
  if (next === this.currentNodeId) { this._resetNodeClock(); return; }
  // Load next node while keeping old texture visible — no fade-out gap.
  // _setTexture only hides the sprite when there is no existing texture,
  // so the previous frame stays on-screen until the new one is ready.
  this._showNode(next);
}
```
**注释直接写明了设计意图：“no fade-out gap”——旧贴图一直在屏，新贴图 decode 好了就瞬间换。**
另外，那段“淡出→换图→淡入”的分支（`_pendingNode`，**[源码:render/web/wallpaper_scene.js:987-991]**）
**全仓只被赋值为 `null`（L918 / L945 / L1203）、从未被赋真值** `[实测:grep _pendingNode]`
→ **那段代码是死代码**，也就是说原项目**下线了节点间的淡入淡出**。

节点停留时长（也是可照抄的数值）：
```js
// [源码:render/web/wallpaper_scene.js:1282-1286]
_resetNodeClock() {
  this.nodeElapsed = 0;
  this.nodeHoldSeconds = this.staticHoldSeconds
    + Math.random() * (this.staticHoldMaxSeconds - this.staticHoldSeconds);
}
```
默认值：`inactivitySeconds = 60`（**[源码:render/web/wallpaper_scene.js:582]**，同 `wallpaper/scene_assets.py:440`）、
`staticHoldSeconds = 45`、`staticHoldMaxSeconds = 60`（**[源码:render/web/wallpaper_scene.js:583-585]**）
→ **每个 pose 停 45~60 秒**；环境变量 `AMADEUS_SCENARIO_STATIC_SECONDS` 可固定为单一值
（**[源码:wallpaper/scene_assets.py:434-436]**）。

**另一个容易误会的点**：空闲场景的**起始节点是 `stand_thinking`，不是 `look at CRT`**：
```js
// [源码:render/web/wallpaper_scene.js:1011-1018]
_startNode() {
  const nodes = this.graph.nodes || [];
  if (this.activeActivity) { ... }
  return nodes.find((n) => String(n.sceneId || "").toLowerCase() === "stand_thinking")
      || nodes[0] || null;
}
```

### ⑦.5 那录屏里“贴脸 → 整张书桌可见”的观感到底来自什么

把观感拆成三段，逐段对账：

| 观感上的变化 | 源码里实际发生的事 | 依据 |
|---|---|---|
| CRT 屏内：贴脸大头 → 全身中景 | **场景节点硬切**（`look at CRT` → `stand thinking`/`computer use`），两张图的取景差就是“近/远” | [源码:render/web/wallpaper_scene.js:1288-1299] |
| “整张书桌突然可见” | **它从头到尾都在。**实拍桌面是 stage 最底层（`addChildAt(nextBg, 0)`），**从不淡入/淡出** | [源码:render/web/wallpaper_scene.js:1885-1906] + §1.6 层表 |
| 只有 `look at CRT` 那一帧“真的是大头” | 真实素材（`look_at_CRT.png` 1398×1125 + 180 帧循环） | [原包:assets/scenarios/runtime/look_at_CRT/...] + [实测:印样] |
| 唯一可能被看成“平滑”的那 0.35 秒 | 进/退**场景态**时的 0.35s 线性 alpha 交叉 | [源码:render/web/wallpaper_scene.js:551-557, 967-992] |
| Wallpaper Engine / Lively 自带过渡 | **不参与**（同一个 URL 项目只挂一次，页面内部换贴图） | [源码:docs/windows_wallpaper_lifecycle.md:39-41] |

**[推断]**（标注明确）：站长录屏抽帧间隔约 1 秒，**物理上无法区分“0.3s 推轨”与“一帧切换”**。
结合上表，最可能的解释是：**场景节点硬切**，被 1fps 抽帧看不出中间过程；
或者是**退出场景态的 0.35s 交叉淡入**被感知成“平滑”。
**没有任何证据支持“相机推拉”。**

### ⑦.6 我方该照哪一种实现（明确结论）

| 需求 | 该照哪一种 | 证据等级 |
|---|---|---|
| 她“活在 CRT 里”、桌面永远可见 | 底图常驻 + CRT 多边形遮罩 | **[源码]** §1 |
| 贴脸 → 中景 | **硬切**（原项目行为）；想更好看就加 **0.35s 线性 alpha 交叉** | 硬切=[源码:render/web/wallpaper_scene.js:1288-1299]；0.35s 数值=[源码:render/web/wallpaper_scene.js:551-557, 967-992]；**把它用到节点之间是我方扩展=[推断]** |
| 场景态 ↔ 角色态 | **0.35s 线性交叉淡入**（完全照源码） | [源码:render/web/wallpaper_scene.js:912-937, 967-1009, 1723-1745] |
| 相机推拉（对整屏/窗口做 scale/translate） | **不要做**。原项目没有；做了就是“我们加的”，必须在交付里标注 | **[源码]**：全仓只有 alpha 过渡，无 scale/translate 时间动画 |
| 过渡曲线 | 原项目是**线性**（`alpha = t`）。若要用 ease，属我方改动 | [源码:render/web/wallpaper_scene.js:977] |

**如果一定要“平滑拉远”的效果，正确做法是：**
在 **CRT 屏内**对角色层/场景层做 alpha 交叉（或小幅 scale），
**不要动整屏也不要动窗口** —— 否则会“连桌面带键盘一起缩放”，
和实拍底图的透视对不上，一眼假（桌面是平面照片，不是 3D，见 §1.2）。

---

## 8. 我方实现要点（可直接照抄的伪代码）

> 目标：**先复刻"她活在 CRT 里"**（背景照片 + CRT 多边形 + 角色/场景层 + 字幕 + 极轻 CRT 质感），
> **再复刻状态机**，**最后才做嘴部补丁**。
> 下面每一步都标了对应出处，方便实现方回查。

### 8.1 画布与坐标系（照抄 `wallpaper_scene.js`）

```js
// 1) 底图 cover 变换（唯一一份）
const t = coverTransform(1672, 941, screenW, screenH);   // §1.2
bg.x = t.x; bg.y = t.y; bg.width = t.width; bg.height = t.height;

// 2) CRT 多边形 -> 屏幕
const crtPx = CRT_POLYGON.map(([x,y]) => ({x: x*t.scale + t.x, y: y*t.scale + t.y})); // §1.3
const bounds = AABB(crtPx);
const mask = new PIXI.Graphics(); mask.beginFill(0xffffff);
mask.moveTo(crtPx[0].x, crtPx[0].y);
for (let i=1;i<crtPx.length;i++) mask.lineTo(crtPx[i].x, crtPx[i].y);
mask.lineTo(crtPx[0].x, crtPx[0].y); mask.endFill();

// 3) 层（自下而上），见 §1.6 表格
stage.addChild(bg);                     // 实拍桌面
stage.addChild(backplateSprite);        // BG_empty 裁掉玻璃 -> 拉伸进 bounds
stage.addChild(characterContainer);     // 角色精灵（+嘴部补丁）
stage.addChild(subtitleContainer);      // 字幕板 + 文本
stage.addChild(scenarioContainer);      // 场景态整图/帧序列
stage.addChild(staticOverlay, ambientLayer, glowLayer, scanlineLayer, bottomVignette);
characterContainer.mask = mask;  scenarioContainer.mask = mask;  scanlineLayer.mask = mask;
```

### 8.2 角色落位（照抄 `_applyCurrentTransform`，§1.4）

```js
function fitCharacter(sprite, bounds, canvasW = 764, canvasH = 1028) {
  const scale = Math.min(bounds.width * 0.64 / canvasW, bounds.height * 0.90 / canvasH);
  sprite.anchor.set(0.5, 1.0);
  sprite.scale.set(scale);
  sprite.x = bounds.x + bounds.width * 0.52;
  sprite.y = bounds.bottom - Math.max(3, bounds.height * 0.012);
}
```
> **必须用 `canvas_size` 而不是单帧尺寸**，否则 960 宽的 `idle_closed_eye` 会让角色忽大忽小。

### 8.3 状态机 tick（照抄 `_startIdleTicker` + `_nextAutoNode`，§2.1-2.4）

```
state = { node: ROOT, frameIdx: 0, elapsed: 0, held: false }
interval = clip(node).frameIntervalMs           // 每帧 ms，来自 manifest
loopMode = clip(node).loopMode                  // 'loop' | 'once_then_hold'

onTick(deltaMS):                                 // PIXI ticker
  if (!active || held || transitionQueue.length) return
  elapsed += min(deltaMS, 100)
  if (elapsed < interval) return
  steps = floor(elapsed / interval); elapsed -= steps * interval
  advanced = false; crossed = false
  for (i in 0..steps-1):
    if (loopMode == 'once_then_hold' && frameIdx >= frames.length-1) break
    prev = frameIdx
    if (loopMode == 'once_then_hold')             frameIdx = min(frameIdx + 1, frames.length - 1)
    else if (speaking && hasMouthCfg && n > 1)    frameIdx = (frameIdx + 1) % n
    else if (speaking && n > 1)                   frameIdx = (frameIdx % (n - 1)) + 1   // ★ 跳过 0 号中立帧
    else                                          frameIdx = (frameIdx + 1) % n
    if (loopMode != 'once_then_hold' && frameIdx <= prev) crossed = true
    advanced = true
  if (!advanced) return
  showFrame(frameIdx)
  if (loopMode == 'once_then_hold' && frameIdx >= frames.length-1) onCycleComplete(node)
  else if (loopMode != 'once_then_hold' && crossed)                onCycleComplete(node)

onCycleComplete(node):                            // = renderer.js:1342-1350
  if (speaking)                       { advance(); return }
  if (node in TRANSITION_HOLD_LABELS) { held = true; showFrame(last); return }  // 等她开口
  advance()

advance():                                        // = renderer.js:1352-1376
  if (forced)            { play(forced); return }
  if (pendingExpression) { e = findTriggerEntry(pendingExpression) || nodeByLabel(pendingExpression)
                           play(e); return }
  play(nextAutoNode(node))

nextAutoNode(from):                               // = renderer.js:1534-1549
  standbyOK = !speaking && (now - lastSpeechEndedAt >= 30_000)
  edges = edges.filter(e => e.from==from && e.prob > 0 && (standbyOK || label(e.to) != 'trans_standby'))
  if (!edges.length) return from                       // 死胡同原地循环
  total = sum(edges.prob); r = random()*total
  for (e of edges) { r -= e.prob; if (r <= 0) return e.to }
  return last(edges).to
```
说话开关（照抄 §2.5）：
```
onSpeechStart():
  speaking = true; lastSpeechEndedAt = null; frameIdx = 0; held = false
  if (!pendingExpression && node not in SPEAKING_RELEASE_LABELS):
      trigger = (node in CLOSED_EYE_ELIGIBLE && random() < 0.18) ? 'closed_eye_trans' : 'speaking_short'
      pendingExpression = trigger; advance()

onSpeechEnd():
  wasSpeaking = speaking; speaking = false; lastSpeechEndedAt = now
  if (node or pending in SPEAKING_RELEASE_LABELS):
      holdClosedFrame()                          // ★ 见 7.5 的警告
      postSpeechTimer = setTimeout(() => {
          clearHold(); play(postSpeechReleaseNode(node) || ROOT)
          if (releaseNode != ROOT) scheduleAdvance(releaseNode, nodeDuration(releaseNode))
      }, 1000)                                   // postSpeechHoldSec
```

### 8.4 口型：两层拼装（照抄 §2.6）

```
// 每个说话剪辑准备：
//   baseFrames[]        : 该剪辑全部帧
//   mouthPatch          : 一张整帧（闭嘴），= mouthOverlays[label][0]
//   anchorTrack[i]      : {cx,cy,width,height} 基础帧 i 的嘴部锚点（帧中心坐标系）
//   overlayAnchor       : {cx,cy} = runtime_overlay_anchor（闭嘴源帧的嘴部锚点）
//   silenceThreshold    : 0.08
//   silenceMaskAmplitude: 0.75（key_point 0.80 / thinking_speaking2 1.0）
//   maskWidthMul/HeightMul/maskCyOffset/overlayAlign: per-label override，默认 1/1/0/null

drawFrame(base, i):
  sprite.texture = baseFrames[i]

updateMouth(mouthValue, speaking):
  if (label not in MOUTH_SYNC_LABELS) return hidePatch()
  patch.texture = mouthPatch                       // 只有一张
  if (!speaking || mouthValue <= 0.08):
      patch.visible = true
      drawMask(amplitude = silenceMaskAmplitude)
  else:
      patch.visible = false                        // 说话中让基础帧自带的口型露出来

drawMask(amplitude):                               // = renderer.js:924-967
  a  = anchorTrack[activeBaseFrameIdx]  ||  profileDefaultAnchor
  th = baseFrame.height
  localX = a.cx ; localY = a.cy - th/2             // 帧中心系 -> sprite 局部系
  if (overlayAlign == 'canvas') { patch.x = 0; patch.y = 0 }
  else { patch.x = localX - overlayAnchor.cx
         patch.y = localY - (overlayAnchor.cy - patchFrameHeight/2) }
  wHalf = max(1, a.width)/2  * 1.8 * maskWidthMul
  hHalf = max(1, a.height)/2 * (1 + 1.5*amplitude) * maskHeightMul
  mask.clear(); mask.beginFill(0xffffff,1)
  mask.drawEllipse(localX, localY + maskCyOffset, wHalf, hHalf); mask.endFill()
  patch.mask = mask

setMouth(v): mouthValue = clamp01(v); updateMouth(mouthValue, speaking)
```
> **alpha 恒为 1**，没有 opacity 参数；"amplitude" 只把椭圆变高。
> **补丁不平移缩放**，只是整体平移做锚点对齐；**椭圆遮罩**才是"只露嘴"的机制。
> 说话中的音量**不驱动口型形状**——只在阈值处开关闭嘴补丁。

### 8.5 音量 → mouthValue（照抄 §6）

```python
VOLUME_MULTIPLIER = 3.75
SEND_INTERVAL     = 0.01            # 10 ms
def mouth_value(chunk_f32, first_window=False):
    if chunk_f32.size == 0: return 0.0
    rms = float(np.sqrt(np.mean(chunk_f32 ** 2)))
    v = min(1.0, rms * VOLUME_MULTIPLIER)
    if first_window and v > 0.0: v = max(0.12, v)     # 首字保底
    return v
# 每个窗：先 publish 再写设备；播放结束/中断 publish(0.0)
```

### 8.6 字幕条（照抄 §1.6 的公式）

```js
const sW = clamp(bounds.width * 0.72, 180, bounds.width - 24);
const sH = clamp(sW / (2564/430), 34, bounds.height * 0.16);
bar.x = bounds.x + (bounds.width - sW) / 2;  bar.y = bounds.bottom - sH;
text.fontSize = clamp(round(sW/34), 11, 17);  text.lineHeight = round(fontSize*1.32);
text.x = bar.x + sW/2;  text.y = bar.y + sH*0.52;
```

### 8.7 开场（照抄 §3 的结论，**必须标注"拼接模拟"**）

```
t=0.0s : 场景态 = look_at_CRT（贴脸大头，裁玻璃后拉伸进 CRT bounds）
t=0.0~0.7s: 保持（可用 look_at_CRT_loop 前 21 帧 @30fps 做微动）
t=0.7~1.05s: 交叉淡入 0.35s 线性 alpha -> stand thinking / computer use 整图
              （或淡到 03 角色精灵 + BG_empty）
之后     : 常态角色态（03 剪辑 + 状态机）；空闲 ≥60s 再自动进入场景态
```
- **0.35s / 线性 / 只改 alpha** 是**原项目唯一的过渡数值**，直接照抄
  `[源码:render/web/wallpaper_scene.js:551-557, 967-992]`；**不要加 scale/translate**（§⑦.6）。
- 原项目**场景节点之间是硬切**（`_goNext`，`[源码:render/web/wallpaper_scene.js:1288-1299]`），
  所以"在 `look_at_CRT` 与 `stand thinking` 之间做 0.35s 交叉"是**我方扩展**，属于 `[推断]`/自定；
  但时长与曲线有源码依据。
> ⚠️ 交付说明里必须写：**原项目没有相机推拉；这是用两张取景不同的场景图 + 0.35s 线性交叉淡入**（§3、§⑦）。

### 8.8 眨眼（照抄 §2.7 的结论）

```
默认：不眨眼（原素材没有眨眼，任何"插帧闭合眼睛"的做法都会跳帧）。
可选：如果一定要有"活"的感觉 ——
  a) 用 closed_eye_trans 前 6 帧（8ms×6 ≈ 48ms）做一次极短的闭-开（会被看出是"慢速闭眼"，不推荐）；
  b) 或者程序化：在眼部矩形贴一个肤色/睫毛色的快速遮罩（需要先量出眼部坐标）；
  c) 或者接受不眨眼（原项目的实际状态）。
```
`idle` 的 120 帧**不含闭眼**（§2.7 表），所以不要指望"基础 idle 自带眨眼"。

---

## 9. 做不到 / 不确定 清单（如实）

| # | 事项 | 状态 | 我试过什么 / 为什么 |
|---|---|---|---|
| 1 | **源动画（那些 `downloads/*.mp4`）最初是怎么生成的** | **查不到** | 全仓检索 `RIFE\|gmfss\|GMFSS\|snapghost\|interpolat\|pre-render\|Live2D model`（`docs/`）；只找到"插值产物不属于运行时格式"这类**排除性**描述。SpriteForge 作者端**不在这个仓库、不开源**（[源码:docs/character_pack_authoring.md:130-134]）。**不许写"SpriteForge 用 Live2D 做的"。** |
| 2 | 站主录屏里"贴脸→拉远"到底是硬切还是短推轨 | **部分不确定** | 抽帧间隔 ~1s（`_video-frames/`），物理上无法区分 0.3s 推轨与一帧切换。**但"原项目没有相机动画"是可证的**（§3）。 |
| 3 | 宿主（Electron/Lively/Wallpaper Engine）层有没有窗口/相机缩放动画 | **已证否（本轮补完）** | `docs/windows_wallpaper_lifecycle.md` 全 285 行 + `wallpaper/windows_desktop_layer.py` 全 373 行 + `wallpaper_engine_bridge.js` + `electron/src/main/index.ts` 全部尺寸相关命中，逐条审完：**零窗口/画布动画**；页面内只有 1 处 0.35s 线性 alpha 过渡，且不用于场景节点之间。详见 **§⑦**。 |
| 4 | 原包有没有"眨眼"素材 | **已证否** | 全帧解码实测 `idle`/`idle1`/`smile`/`sad`（120/120/120/120 帧），闭眼事件 **0 个**（`web/checks_mouth_blink.json`）。见 §2.7。 |
| 5 | `anchor_track` 的**生成算法** | **一半查不到** | 仓里有 v1 检测器 `tools/detect_mouth_masks.py`（算 `cx/cy/width/height/curve/openness/closed_frame_idx`），但**没有**生成 `anchor_track`（逐帧 `score`）的脚本；`package_spriteforge_character.py:272` 只是**读** 作者 profile 里的 `anchor_track`。→ **逐帧追踪器在 SpriteForge 作者端，未开源。** |
| 6 | `closed_frame_idx` 与 `argmin(openness)` 不一致 | **实测存在** | `speaking_loop1`: `closed_frame_idx=0` 但 `argmin(openness)=150`（共 180 帧）。原项目自己在 `holdClosedFrame` 里**优先用 argmin**（`renderer.js:662-687`）。见 §2.6(f)。 |
| 7 | 场景图 188 张的**来源**（是渲染出来的 3D 房间还是画的） | **查不到** | 只确认它们都自带 CRT 玻璃外框、统一 1398×1125、可被裁到 1182×902。生成方式无文档。 |
| 8 | `scenario_graph.json` 里 `x/y` 坐标的用途 | **查不到** | [原包:meta_json/scenario_graph.json] 每个节点有 `x`,`y`（如 338.57/183.98），但 `wallpaper/scene_assets.py` 与 `wallpaper_scene.js` **都不读这两个字段**（`_scenario_resource_payload` 只读 `resource`）。**推断**（标 [推断]）是给作者端的图形编辑器用的布局坐标。 |
| 9 | 04 包里 `look_at_CRT_loop.mp4` 的音轨内容 | **未核对** | 已知它 6.06s、aac 48k 立体声、与 180 张 PNG 逐像素相同（上一轮已核）；**音轨本身是什么声音没有听/没有分析**。 |
| 10 | 交叉淡入的**时长/曲线**在原项目里的具体取值 | **查不到** | `_startFade(±1)` 的具体时长/duration 我没读完（`wallpaper_scene.js:1210+` 附近）。**实现时可以自定**，但不要说成"原项目参数"。 |
| 11 | Live2D 与本套素材是否有间接血缘 | **无证据** | 见 §5。时间线（包 2026-08-29 vs Live2D 2026-10-08）、打包工具、契约三条独立证据都指向"无关"。**不排除作者在 SpriteForge 里手工导出过 Live2D**，但没有证据，故不主张。 |

---

## 10. 本次落地的 `refs/`（逐字摘录，可直接给实现方）

全部由 `tools/15_refs_slice.py` 从 `E:\DeepSeek1\work\_amadeus-src` **按行号逐字切片**生成，
**没有人工转录**，每个文件 ≤200 行，文件头有来源与行号。

| 文件 | 来源 | 行数 | 内容 |
|---|---|---|---|
| `refs/renderer_mouth_layer.js` | `render/web/renderer.js` | 159 | **口型核心**：`_updateMouthLayer` / `_drawMouthMask`（椭圆公式+偏移公式）/ `_getMouthAnchor` / `_isTextureReady` |
| `refs/renderer_frame_transform.js` | `render/web/renderer.js` | 138 | `_applyFrame` + **`_applyCurrentTransform`（角色落位公式）** + **`_startIdleTicker`（帧时钟/loopMode/周期完成）** |
| `refs/renderer_graph_runtime.js` | `render/web/renderer.js` | 117 | 嘴层创建、`setMouth`、`loadGraph`、`onCycleComplete/_advanceNow/_playNode`、`_nextAutoNode`、viewport bounds + CRT 遮罩 |
| `refs/spriteforge_animator_constants.py` | `render/spriteforge_animator.py` | 121 | 全部 label 集合、`_MOUTH_SYNC_LABELS` 过滤、`_MOUTH_SILENCE_MASK_OVERRIDES`、hold 常量 |
| `refs/spriteforge_animator_mouth.py` | `render/spriteforge_animator.py` | 87 | `_load_mouth_configs`：`mode='silence_close'` / `silenceThreshold=0.08` / `sourceAnchors` / `anchorTrack` |
| `refs/package_mouth_overlays.py` | `tools/package_spriteforge_character.py` | 100 | `once_then_hold` 名单、`PREFER_OWN_CLOSED_FRAME`、**`_mouth_runtime_config`（补丁 = 一张整帧 PNG→KTX2，`mouthOverlays[label]` 长度 1）** |
| `refs/scenario_assets.py` | `wallpaper/scene_assets.py` | 115 | 场景裁剪归一化框、CRT 多边形→归一化盒、场景资源类型解析、**`placementMode='crt_screen'` payload** |
| `refs/wallpaper_scene_composition.js` | `render/web/wallpaper_scene.js` | 145 | `coverTransform`、**`_syncLayerOrder`（真实 z 序）**、`_imageTransform`/`_crtPoints`/`_computeBounds`/`layout`（遮罩） |
| `refs/wallpaper_scene_placement.js` | `render/web/wallpaper_scene.js` | 64 | 归一化裁剪→纹理、`crt_screen` 拉伸 / `fit` 两种摆放 |
| `refs/tts_mouth_pipeline.py` | `tts/playback.py` | 77 | `volume_multiplier=3.75`、`send_interval=0.01`、**RMS→mouthValue→publish（先发后写）** |
| `refs/detect_mouth_masks_core.py` | `tools/detect_mouth_masks.py` | 121 | 嘴区检测、**帧中心坐标系**、`compute_frame_openness`、`closed_frame_idx=argmin` |
| `refs/doc_mouth_sync_notes.md` | `docs/mouth_sync_system_notes.md` | 106 | 官方说明：目标/最终方案、config 模型、`silence_close`、**JS 渲染行为与偏移公式** |
| `refs/doc_live2d_and_pack_boundary.md` | `docs/live2d_character_visuals.md` | 26 | "默认仍是 Sprite；Live2D 是显式选择的实验性后端"+ 架构边界表 + E-mote 未实现 |
| `refs/doc_pack_boundary.md` | `docs/character_pack_authoring.md` | 30 | 包格式契约 + `loopMode` 语义 + graph 语义 + 作者端边界 |
| `refs/doc_assets_boundary.md` | `assets/README.md` | 9 | 只有 `amadeus_desktop_wallpaper.png` 进仓；SpriteForge 的 PNG/视频不进 Amadeus |

---

## 11. 复现命令（本次跑过的）

```powershell
# 0) 取源码（本机已 checkout 到 E:\DeepSeek1\work\_amadeus-src @ d8fc369；shallow）
git clone --depth 1 https://github.com/Code-Amadeus/Amadeus.git E:\DeepSeek1\work\_amadeus-src

# 1) 原包 JSON 权威事实
python -c "import json;m=json.load(open(r'E:\DeepSeek1\work\_kurisu-full\meta_json\runtime_manifest.json',encoding='utf-8'));print(list(m['mouthOverlays'].items())[:3]);print(len(m['clips']))"

# 2) 眨眼全帧实测（已跑过，结果在 web/checks_mouth_blink.json）
#    逐帧解码 idle/idle1/smile/sad 共 480 帧 + 眼框亮像素曲线 + 印样
python E:\DeepSeek1\work\_kurisu-full\tools\14_mouth_blink.py

# 3) 本次新增：逐字摘录 refs/（<=200 行/文件）
python E:\DeepSeek1\work\_kurisu-full\tools\15_refs_slice.py
```

**只读保证**：本次未修改 `F:\7AAA\AI\blog` 任何文件，未执行任何 `git add/commit/push`；
`_amadeus-src` 是只读使用的浅克隆（未改其工作树）；
素材 ZIP 只做随机读取（`zipfile.read`），未整包解压。
