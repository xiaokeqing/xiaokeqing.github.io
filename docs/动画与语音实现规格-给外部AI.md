# 博客助手「动画 + 说话 + 表情」实现规格（给外部 AI 评审）

> 用途：交给另一个 AI 评审/优化。本文档把**用户要的效果、已核实的原版机制、素材清单、实现规格、未决项**一次写全。
> 标注：`[源码]` 读原项目源码得出（附文件行号）｜`[实测]` 有原始输出｜`[原包]` 来自官方素材包｜`[设计]` 我方设计｜`[推断]` 推断。
> 不含任何凭据。

---

## §0 用户要的东西（效果清单）

```
① 主页：一张实拍书桌照铺满全屏 + 正中间 CRT 显示器，**角色活在屏幕里**
   · 帧动画（不是静态图、不是 CSS 缩放假装）
   · 进站先播开场：贴脸特写（**含一次真眨眼**）→ 到"整张书桌可见"的中景
   · 屏内：右上状态行（真实数据，取不到写"读不到"）+ 底部字幕条（原版做旧金属板作底）
   · 页面底部：输入条（走站内 /api/public/ask）
   · 导航浮条（不遮挡 CRT）
② 她会**开口说话（语音）**，说话时**嘴在动**；**不做语音输入**（不申请麦克风、不引入 Web Speech）
③ 她会在**房间里活动**：待机 / 在电脑前 / 趴桌睡 / 喝咖啡 / 站着想事 / 白板前 / 贴脸看屏幕；她不在时=空房间
   · **关键要求：房间里的她也要是"动"的**（不是只会切换静态整图）
④ 表情随情境变化（对话情绪 / 站点事件 / 访客交互触发）
⑤ 把**素材包里的所有东西都利用上**（现在只用了 4 段剪辑 + 8 张头像静帧）
⑥ 手机端与桌面**共用同一套素材**（手机版界面是另一个 AI 做的，只做共用接口）
```

---

## §1 已核实的原版机制（照抄依据）

出处：`github.com/Code-Amadeus/Amadeus` @ `d8fc369`（本机 clone `E:\DeepSeek1\work\_amadeus-src`）；
完整研究 `F:\7AAA\AI\blog\docs\amadeus-research\HOW-IT-WORKS.md`（1150 行，带 file:line）+ `refs/`（15 份逐字源码切片）。

### 1.1 画面合成（不是 3D，无透视投影）
```
实拍桌面大图 cover 铺满（**最底层、从头到尾常驻**）→ **硬编码的 CRT 多边形**遮罩
（crt_config.json:24-81，AABB 550..1136 / 195..638，基准图 1672×941）
→ 多边形内依次贴：① 空房间 backplate ② 角色精灵（帧图集，透明底 RGBA） ③ 字幕板 ④ 场景整图
→ 再叠：氛围光 high/low、ADD 辉光、扫描线、暗角
坐标：coverTransform（wallpaper_scene.js:16-25）
**角色落位公式**（renderer.js:797-825）：scale = min(W*0.64/764, H*0.90/1028)，x = 0.52W，
                              y = bottom − 1.2%H，anchor=(0.5,1)
```

### 1.2 帧播放与状态机
```
· 39 个剪辑 / 共 **7552 帧**；每帧透明底 RGBA；帧尺寸 4 种变体：
  764×1028（6284 帧）/ 960×1028（738，idle_closed_eye）/ 764×1026（290，idle2）/ 764×1027（240，smile+trans_smile）
· **`frameIntervalMs` 是每帧时长（毫秒）**，不是 fps。全表：17ms × 22 个剪辑 / 21ms × 6 / 8ms × 10 / 5ms × 1
· 12 个剪辑是 `once_then_hold`（播一遍停末帧后立刻换节点）；过渡剪辑在"没说话"时停末帧等她开口
· **状态机**：`graph_config.json` = **37 节点 / 87 条边**，root = `idle`；每段播完**掷骰子**按出边概率跳下一个
  （`_nextAutoNode:1534-1549`）→ 这是"她看起来活着"的真正来源
· **情绪入口概率 = 0.00** = 永不被随机选中，**必须由宿主触发**；`sad` / `smile` 两个剪辑**不在图里**，只能手动播
```

### 1.3 房间/场景（"好几个动作"来自这一层）
```
· `scenario_graph.json` = **6 节点 / 19 条边**：computer use / sleep_desk / drink_coffee /
  stand thinking / whiteboard use / look at CRT
· 自环概率：前四个 0.8、look at CRT 0.4、**stand_thinking 无自环**
· **空闲场景起始节点 = `stand_thinking`**（_startNode():1011-1018）
· 最后一次语音结束 **60 秒**后进入场景态；每个 pose 停留 **45~60 秒**（随机）；播完当前循环再换 pose
· ⚠️ 6 张场景图是"**她已烘进画面**"的整图，且自带 CRT 玻璃罩/暗角/扫描线 → 那种状态下她是**静止**的
  （原版也是硬切整图）。要做"她在房间里动"必须走 §6 的方案
```

### 1.4 过渡（**全项目没有相机动画**）
```
· 节点→节点 = **硬切**（`_goNext()` 注释原文 "no fade-out gap"；"淡出→换图→淡入"的 `_pendingNode` 分支是死代码）
· 全项目**唯一**过渡常数：`_fadeDur = 0.35` 秒、**线性**（alpha = t）、**只改 alpha**，
  且只用于「角色态 ↔ 场景态」切换（进入方向角色硬切消失、只有场景淡入；退出方向才是真交叉）
· 宿主层（Lively / Electron / 桌面层脚本）**零窗口/画布动画**；`setBounds` 全是静态 viewport
· ⇒ **禁止**对整屏/窗口做 scale/translate（会连桌面带键盘一起缩放，与平面实拍透视冲突，一眼假）
· `[实测]` 参考录屏的"拉远"= 场景硬切 + 窗口宽高比差异：把 desk.webp 掩屏配准到录屏，第 2 秒 = 原图 **1.00 倍 cover**、NCC 0.965
```

### 1.5 眨眼
```
· 03 的 39 个剪辑：实测 idle/idle1/smile/sad 共 **480 帧，闭眼事件 0 个**（中景没有眨眼机制）
· 04 的 `look_at_CRT` **180 帧循环**里有**且仅有一次**真眨眼：帧 **34–45** 一次完整眨眼，**完全闭合 39–42**
  `[实测]` 判据 = 紫色虹膜像素数（开眼基线 ≈2100；39–42 帧只有 20）
· 另有"闭眼**状态**"素材（不是眨眼）：idle_closed_eye（738 帧）、closed_eye_trans（120 帧@8ms，once_then_hold）、
  speaking_closed_eye_1(180f)/_2(300f)
· `[实测]` 包内印样显示 `idle1` 在第 f023–f028 / f073–f078 各有一次眨眼 → 中景眨眼只能用它或闭眼状态
```

### 1.6 语音与口型（见 §3/§4 的实现规格）
```
· 口型**不是从文字推的，是从音频波形推的**；"说话时嘴在动"本来画在帧里
· 唯一动态控制 = 静音闸：10ms 窗 PCM **RMS × 3.75**，clamp 0~1（首窗保底 0.12）→ mouthValue
  静音（≤0.08）时叠**整帧闭嘴图** + **椭圆遮罩只露嘴**（**34×18 是遮罩尺寸来源，不是补丁尺寸**）
· `openness[]` 是**作者侧离线分析**的静态逐帧值（定位闭嘴帧用），**不是运行时音量**
· `anchor_track[]` = **逐帧嘴部坐标**（头在动，嘴位置每帧变）→ 贴闭嘴图必须逐帧对位
· ⚠️ 陷阱：上游 `holdClosedFrame()` 用 `argmin(openness)` **覆盖** shipped 的 `closed_frame_idx`
  （speaking_loop1 两值冲突：0 vs 150）→ **我方显式读 `closed_frame_idx` / `mouthOverlays` 指向的那帧**
· 上游 2026-09-15 公告的"惊讶/害羞/生气 闭嘴 mask 映射错误"就是这个区域（素材没问题，是打包映射）
```

### 1.7 与 Live2D 的关系
```
Live2D 是**并行 opt-in 后端**（2026-10-08 才加，默认仍是本套 Sprite 帧序列），**不是**这套帧素材的生成器
（包 manifest 版本 2026-08-29，早 6 周）→ 我们用帧序列，不用 Live2D
```

---

## §2 素材清单 + "全部用上"对照表

### 2.1 六个包（本机 `F:\7AAA\AI\命运石之门\`）
| 包 | 大小 | 内容 | 用途判定 |
|---|---|---|---|
| `03-character-kurisu` | 2.54 GB | **39 剪辑 / 7552 帧** KTX2 + `runtime_manifest.json`（clips + mouthOverlays）+ `graph_config.json`（37/87）+ `spriteforge_mouth_config.json`（16 口型 profile） | **核心**：全部 39 剪辑都要入状态机 |
| `04-visual-runtime` | 244 MB | **180 帧 look_at_CRT 循环**（1070×860@30fps）+ **8 张独立 PNG 场景图**（含 1 张逐像素重复的 backplate）+ `scenario_graph.json` + 氛围光 ×2 + **字幕板** + **键盘音效** + mp4（与 180 帧同帧，仅音轨独有） | 开场（眨眼）+ 6 活动位 + 空房间 + UI 素材 + 音效 |
| `05-companion-kurisu` | 11 MB | **8 情绪 ×（idle / speaking / static）** 已是 webp + manifest | 面板头像、手机端、情绪联动 |
| `02-voice-kurisu-gpt-sovits-v3`（新） | 2.77 GB | **GPT-SoVITS v3 权重 + `assets/audio/reference` 参考音频** | ✅ **本地合成 Kurisu 语音的原料**（L1 离线生成） |
| `06-voice-kurisu-gpt-sovits-v2pro-experimental`（新） | 379 MB | v2Pro 语音 + speaker-encoder 权重（**需先装 v3**） | ✅ 备选音色/更省资源的一档（6GB 显存可先试它） |
| `01-asr-qwen3-0.6b`（新） | 1.79 GB | 本地语音识别模型 | ❌ **不用**（明确不做语音输入） |
安装方式（上游 README）：先装 Amadeus 源码环境，再在源码根目录
`python tools/external_assets.py verify/install "<zip>"`（校验 hash、拒绝意外覆盖）——**绝不装进博客仓库**。

### 2.2 39 个剪辑 → 用途映射（"全部用上"的第一层）
```
待机/呼吸：  idle, idle1, idle2, idle_mic_wind, idle_str_wind, idle_side_soft_wind, idle_side_wind,
             idle_side_butterfly, idle_closed_eye（738 帧，闭眼休息态）
说话：       speaking_short, speaking_med, speaking_long, speaking_loop1, speaking_loop2, speaking_trans,
             speaking_closed_eye_1/_2
情绪说话：   smile_speaking, sad_speaking, angry_speaking, shy_speaking1, shy_speaking2,
             surprise_speaking, thinking_speaking1, thinking_speaking2, key_point_speaking
情绪/单次：  smile, sad（**不在状态机里**，只能宿主触发）
转场：       trans_smile, trans_standby, angry_trans, shy_trans, sad_trans, surprise_trans, thinking_trans,
             closed_eye_trans, serious_to_thinking, thinking_to_key_point, thinking_to_serious, thinking_to_thinking
（其中 12 个是 once_then_hold；全部按 frameIntervalMs 播放）
```

### 2.3 其它素材
```
· 7 张房间背景：BG_empty（空房间；`scenario_backplate` 是它逐像素副本，只留一份）/
  computer_use / sleep_desk / drink_coffee / stand_thinking / whiteboard_use / look_at_CRT
  `[实测]` 源 PNG 11.65MB → webp **0.57MB**
· 桌面底图：amadeus_desktop_wallpaper（已用 desk.webp）
· UI：字幕板 `subtitle_frame_big`（做旧金属板 2564×430）、氛围光 high/low（两图 alpha 掩码逐值相同、只差亮度）
· 音效：`computer_use_keyboard_loop.wav`（"她在电脑前"的环境音，成本极低、氛围收益高）
· 口型闭嘴帧：`mouthOverlays` 指向的**整帧**资源
```

---

## §3 语音实现规格

### 3.1 三层（服务器不跑模型 —— 已定红线）
| 层 | 内容 | 合成位置 | 服务器/本机负担 | 有声音吗 |
|---|---|---|---|---|
| L1 固定台词 | 问候 / 切页解说 / 状态播报 / 取不到数据时的兜底句 | **离线一次性合成**（本机 GPT-SoVITS 或云端同一音色） | 零（静态 Opus 文件分发） | ✅ 永远有，不需要 Key |
| L2 自由回答 | `/api/public/ask` 的返回文本 | 云端 Fish Audio，经站内 `POST /api/public/tts` 代理（三道闸 + sha256 缓存 + kill switch） | 只转发字节流 | ✅ 有 Key 就有 |
| L3 无 Key | 动态回答只出字幕 | — | 零 | ⚠️ 字幕 + 帧里自带的嘴 |

### 3.2 L1 离线生成流程（本地 GPT-SoVITS 路线）
```
① 在**独立目录**装 Amadeus 源码环境（本机已有 clone `_amadeus-src`）→ `external_assets.py install` 装 02（+06 可选）
② 装 GPT-SoVITS 运行依赖（最大不确定项，可能几 GB 依赖）→ **先只合成 1 句**，量：显存峰值 / 单句耗时 / 音质
   判据：显存不爆 + 单句 ≤10 秒（离线批量可接受）→ 通过再批量；不通过 → 改用云端同一音色
③ 批量产出台词表 → **Opus**（一句几秒 ≈ 30~80KB）+ **口型包络 JSON**（见 §4）
④ 文件名带 hash（配合 CDN 缓存，避免同名更新看不到）
```

### 3.3 播放与自动播放门控（**必做**）
```
· 浏览器在**首次用户手势前**会静音拦截音频（Chrome/Safari/iOS 皆然）
· 设计：未交互态 = 动画与字幕照常、**声音静默**，显示"🔊 点我开声"；
  首次 pointerdown/keydown 解锁 AudioContext → 补放/续播语音
· 验收必须包含一项：**"无手势进站"**（动画正常、不报错、有开声入口）
```

### 3.4 包络的产出位置
```
· **服务端随合成返回**（推荐）：`/api/public/tts` 在云端合成后、落盘缓存前，按同款 10ms 窗算好 envelope，
  返回 `{audio, envelope[], sampleRate, durationMs}` → 客户端零算力、无播放时钟漂移
· L1：离线生成时一并算好存 JSON
· 备选（无服务端包络时）：客户端 `OfflineAudioContext` 预分析一遍再播（比实时 AnalyserNode 更确定）
· `speechSynthesis`（浏览器自带）**只作最后兜底**：机械音色会击穿人设，宁可纯字幕 + 帧里自带的嘴
```

---

## §4 口型（嘴型）实现规格

```
渲染：`<canvas>` 上画两层
  ① 基底帧：说话剪辑的当前帧（嘴本来就在帧里动）
  ② 静音闭嘴层：当 mouthValue ≤ **0.08** 时，把**整帧闭嘴图**按 **anchor_track[frameIdx]** 的坐标平移贴上去，
     并用**椭圆遮罩**（尺寸来自 34×18 那组值，按 CRT 屏幕缩放）只露出嘴部区域
数据：每个说话剪辑需要 `closed_frame_idx` / `mouthOverlays` 指向的闭嘴帧 / `anchor_track[]` / `openness[]`
      （都在 `spriteforge_mouth_config.json` + `runtime_manifest.json`，已导出）
阈值与系数：mouthValue = clamp(RMS(10ms 窗) × 3.75, 0, 1)；说话首窗保底 0.12；停止发 0
⚠️ 不要用 `argmin(openness)` 去猜闭嘴帧（上游就是在这里出 bug、并覆盖了 shipped 配置）
⚠️ 闭嘴补丁要做**逐帧对位**（头在动），坐标用 CRT 内归一化坐标 + devicePixelRatio 取整，避免漂移
无语音时：字幕 + 基底帧自带的嘴（观感是"在说话"，但不是跟声音的精确同步）
```

---

## §5 表情 / 情绪规格

```
素材：① 39 剪辑里的情绪剪辑（smile / sad / angry_trans / shy_trans / surprise_trans / *_speaking / key_point_speaking）
     ② 05 包 8 情绪 ×（idle / speaking / static）—— 面板头像与手机端
触发源（原版情绪入口 prob=0 = 必须宿主触发，所以规则由我们定）：
  ① 对话情绪：`/api/public/ask` 额外返回 emotion 标签（模型输出或前端关键词/规则映射）
  ② 站点事件：新告警 / 故事线推进 / 切页 / 深夜时段
  ③ 访客交互：点击她 / 情绪按钮
说话中的对应规则：
  · 播"该情绪的 speaking 剪辑"（例：生气回答 → angry_speaking）→ 脸与嘴同时是该情绪
  · 停顿 → 闭嘴整帧 + 椭圆遮罩（脸保持该情绪）
  · 缺该情绪 speaking 剪辑 → neutral speaking 打底 + 头像切到该情绪（降级）
优先级与防抖：交互 > 事件 > 对话情绪 > 状态机随机游走；**每次切换设最短驻留时间**
```

---

## §6 房间动画规格（"她在房间里也动" —— 用户明确要求）

```
原理：06/04 包里的 6 张场景图是"她已烘进画面"的**静态整图**；
     要她"在房间里动"，必须用 **空房间底图 + 角色 canvas 实时叠**（就是主视图那套层序）
现状：素材里**只有 1 张空房间**（BG_empty）→ 所以：
  (a) 主视图（贴脸/中景）：BG_empty + 角色 canvas ✅ 已能做到"她在动"
  (b) 其它 5 个活动位：素材没有对应"空底图" → 两个解法：
      ① 直接用现成 6 张整图当"静止 pose"（她能切换但不逐帧动）
      ② **离线合成**那几个位置的空底图（把整图里的她抹掉 / 用 BG_empty 局部拼接 / 重新裁切）
         → 完成后 6 个位置全都能"她在里面动"（离线合成，不花算力，不需要模型）
运行时：状态机 + 场景机照抄原版（6 节点/19 边、dwell 45~60s、空闲 60s、她不在=BG_empty）
```

---

## §7 运行时架构与数据文件

```
渲染层（DOM + 单 canvas，零第三方库）：
  桌面底图 cover（零倍率）→ 氛围光 high/low（mix-blend-mode:screen，交替呼吸）
  → CRT **14 点多边形** clip-path → 内层：BG_empty → <canvas>角色（基底帧 + 闭嘴层）→ 字幕板
    → 场景整图（可选）→ 扫描线/暗角
  → 屏内状态行 / 字幕条（DOM，真实数据，取不到写"读不到"）；页面底部输入条；导航浮条
模块划分（评审建议后确定）：
  · `asset-loader`：懒载顺序、降级（reduced-motion / 省流量 / 加载失败）、内存回收（只留当前+下一段）
  · `graph-walker`：**状态机与场景机共用**的"加权有向图游走"原语（掷骰子 + once_then_hold + dwell），
    两份 JSON 只是配置
  · `frame-player`：图集 drawImage + 按各剪辑 frameIntervalMs 推进（rAF + 时间累加，不用 setInterval 做帧循环）
  · `mouth-layer`：包络 → mouthValue → 闭嘴层（§4）
  · `emotion-router`：触发源 → 情绪剪辑（§5）
数据文件（仓库 `static/kurisu/`）：
  · `manifest.json`：剪辑 / 帧间隔 / 图集几何 / loopMode / scene.crtPolygon（**播放器契约，字段名别改**）
  · `statemachine.json`：37 节点 / 87 边 + root=idle + loopMode/frameIntervalMs/frames
  · `scenarios.json`：6 节点 / 19 边 + start="stand thinking" + empty_room + dwell{60,45,60}
降级：reduced-motion / 省流量 / 窄屏（≤980px 用 132px 头像图集）/ 页面隐藏暂停 / 资产加载失败 → 静帧
```

---

## §8 托管与体积（实测数字）

```
· 站点与素材：**整站搬到 srv2（腾讯云检测机）**，由 Cloudflare 隧道对外；GitHub Pages 保留为备份
  `[实测]` srv2 经隧道 **≈249 KB/s**（2MB×3 次，稳定）；Pages **≈22 KB/s**（小文件）、大文件 30 秒超时、
  主页 HTML 只有 ≈1 KB/s → **srv2 快 10 倍以上**
· 另建 `static.xiaokeqing.cn`（同一个 srv2 静态目录）承载素材，并已在 Cloudflare 加 Cache Rule
  （Hostname=static.xiaokeqing.cn + Path 起 `/kurisu/` → Eligible for cache）
· 体积纪律：**首屏 ≤1.5MB（严格）**；**静态总量 ≤60MB**（原 12MB 上限已按计划提高；
  39 剪辑补齐后 ≈44MB + boot/poster/scenes/mouth ≈ 48~52MB，主页常用 6~10 段再发一档 hi → 55~60MB）
· 大素材一律懒载（用哪段载哪段）；文件名带 hash 以配合 CDN 缓存
· 服务器红线：srv1 / srv2 **都不跑任何本地模型**（TTS 走云端或离线预生成；生成素材只在离线做一次）
```

---

## §9 验收（证据矩阵，缺一不可）

```
P1 场景层：0–15 秒每秒一帧印样与参考录屏并排一致（可用**掩屏多尺度 NCC** 做自动化比对，不靠人肉看）
P2 角色层：30 秒自动游走的节点序列 + **39 个剪辑逐一可播的截图矩阵** + 第 39–42 帧四连帧（证明眨眼）
P3 房间层：6 个活动位各一张截图（其中至少 2~3 个是"她在动"的实时合成）
P4 语音层：L1 固定台词有声 + L2 走代理（有 Key 时）+ **无手势进站**用例 + reduced-motion / 窄屏
P5 口型层：说话中 vs 静音 的对照截图（能看到闭嘴层只在静音时出现）
P6 上线：全绿后发布，线上复验（首屏字节数、开场眨眼、门禁原文）
```

---

## §10 未决项 / 风险 / 已知陷阱

```
1) 语音 Key（Fish Audio）何时到位 → 决定 L2"自由回答也能出声"的上线时点；没 Key 时 L1 仍有声
2) L1 用**本机 GPT-SoVITS**（零成本、要装环境 + 用 02 包的参考音频）还是**云端同一音色**（省事、音色与 L2 统一）
3) 5 个活动位的"空底图"要不要离线合成（合成后她在那些位置也能动）
4) 静态总量上限 60MB 是否接受（超了就得只发子集 / 或把大库放对象存储）
5) 上游已修复的"闭口 mask 映射错误"：我们的包是 2026-09-26（在修复之后），且我方实现显式读
   `closed_frame_idx`，不回退到 `argmin` → 预计不受影响；上线后要抽查"说完话嘴是否闭"
6) 【今天踩过的坑，务必写进任何实现规范】
   · **绝不要把 demo 的整份 CSS 原样搬进生产站**：曾经的 `.view{display:none}` 把全站隐藏（白屏事故）
     → 正确做法：所有选择器加容器前缀（如 `#xk-app `），并检查 `html/body/:root` 与 fixed/overflow 规则
   · **推之前必须看本地产物**（正文长度 / 关键标记 / 站外链接=0 / 图片路径能落到真实文件）+ 一张截图
   · `hugo server` 会给产物注入 livereload，跑门禁前先确认没有它
   · 本机是 PowerShell 5.1（无 pwsh）：不支持 `? :`；`curl` 是别名要用 `curl.exe`；.NET 静态方法用绝对路径
   · 不许用变量拼 awk/sed 替换模式（曾有脚本因此死循环把服务器内存压到 113MB）
```

---

## §11 路径索引
```
机制研究：F:\7AAA\AI\blog\docs\amadeus-research\HOW-IT-WORKS.md（1150 行）+ refs\（15 份逐字源码切片）
数据文件：docs\amadeus-research\data\{statemachine.json, scenarios.json, spec-runtime.md}
素材暂存：E:\DeepSeek1\work\_kurisu-full\（mapping.md / inventory.md / sheets\ / meta_json\ / web\）
录屏与抽帧：E:\DeepSeek1\work\_video-frames\（sheet-16s.png / crt180\ / blink-report.md / blink-evidence\）
原版源码：E:\DeepSeek1\work\_amadeus-src（4197 文件 @ d8fc369）
实施计划（含页面搬运与重规划）：F:\7AAA\AI\blog\docs\实施计划-页面搬运与Amadeus重规划-20261014.md
```
