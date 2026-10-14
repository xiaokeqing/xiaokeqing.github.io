# 博客主页「CRT 里的她」实现方案（照搬 Amadeus 原版机制）

> 目的：把本站主页做成"一张书桌实拍照 + 正中间 CRT 显示器 + 屏幕里活着的角色"的效果。
> 本文档记录**已核实的事实**（含源码出处）、**实现方案**、**资产与体积口径**、**分期与验收**、**未决项**。
> 写作时间：2026-10-14 上午。当前主页已上线（见 §9 现状）。

---

## 0. 效果目标（站长口径）

```
· 主页除导航外不出现任何旧仪表盘内容（指标卡 / 靶场表单 / 笔记流 / 口径块 —— 全部移除）
· 全屏书桌实拍照 + 正中间 CRT；角色活在 CRT 屏幕里
· 她是**帧动画**（不是静态图、不是 CSS 缩放假装），会眨眼、说话时嘴在动、会在状态之间变化
· 进入站点时先播开场（贴脸特写 → 硬切到整张书桌可见的中景）
· 页面底部一条输入条（走站内已有的 /api/public/ask），屏内有状态行与字幕条
· 零第三方库、零站外资源；素材走 GitHub Pages；一键回退开关 kurisuEnabled
```

---

## 1. 已核实的原版机制（源码级，出处：`github.com/Code-Amadeus/Amadeus` @ `d8fc369`）

本机克隆：`E:\DeepSeek1\work\_amadeus-src`；完整研究文档：`E:\DeepSeek1\work\_kurisu-full\HOW-IT-WORKS.md`（1150 行，含逐字源码切片 `refs/`）。

### 1.1 合成方式（不是 3D，无透视投影）
```
1) 一张实拍桌面大图 cover 铺满整个视口，作为**最底层，从头到尾常驻**（addChildAt(nextBg, 0)）
2) 用**硬编码的 CRT 多边形**当遮罩（wallpaper/crt_config.json:24-81；AABB 550..1136 / 195..638，基准图 1672×941）
3) 多边形**内部**依次贴：
     ① 空房间 backplate（BG_empty.png）
     ② 角色精灵（帧图集，透明底 RGBA）
     ③ 字幕板（subtitle_frame_big.png，做旧金属板 2564×430）
     ④ 场景整图（6 个活动位之一；**这些图里角色已经合成进画面，且自带 CRT 玻璃罩/暗角/扫描线**）
4) 最后叠：氛围光 high/low（两张 alpha 掩码逐值相同、只差亮度）、ADD 辉光、扫描线、暗角
坐标换算：coverTransform（render/web/wallpaper_scene.js:16-25）+ crt_polygon（硬编码）
角色落位公式：scale = min(W*0.64/764, H*0.90/1028)，x = 0.52W，y = bottom - 1.2%H，anchor=(0.5, 1)
              （renderer.js:797-825）
```

### 1.2 她为什么"活着"
```
· 引擎：PIXI ticker 逐帧推进（renderer.js:987-1076）
· 剪辑：每段播完**掷骰子**选下一个节点（_nextAutoNode:1534-1549），概率来自 graph_config.json
· frameIntervalMs = **每帧时长（毫秒）**，不是 fps。全表：17ms×22 个剪辑 / 21ms×6 / 8ms×10 / 5ms×1，共 7552 帧
· loopMode：12 个剪辑是 `once_then_hold`（播一遍停末帧后立刻换节点）；过渡剪辑在没说话时"停末帧等她开口"
· **口型 = 两层拼装**：说话中用基础帧**自带的**嘴；**静音时（mouthValue ≤ 0.08）**叠一张**整帧闭嘴画面**，
  按嘴部锚点平移对齐 + **椭圆遮罩只露嘴**。
  ⚠️ 关于"34×18"：它是**遮罩椭圆的尺寸来源**，**不是**补丁尺寸（补丁是整帧，package_spriteforge_character.py:302）
· openness[] 是**作者侧预分析**的静态逐帧属性，**不是**运行时音量
· 音量→口型（有语音时）：PCM **10ms 窗 RMS × 3.75**，clamp 0~1，首窗保底 0.12；**先发口型再写声卡**，停止发 0
  （tts/playback.py:84,87,186-206,225-240）
· ⚠️ 已知陷阱：`holdClosedFrame()` 用 argmin(openness) **覆盖** closed_frame_idx，两个值在 shipped 包里
  对 speaking_loop1 互相矛盾（0 vs 150）→ **以 mouthOverlays 指向的那帧为准**
```

### 1.3 眨眼（结论：素材里有，但只在特写循环里）
```
· 03 的 39 个剪辑：实测 idle/idle1/smile/sad 共 480 帧，**闭眼事件 0 个**（Sprite 路径没有眨眼机制）
· 04 的 look_at_CRT 180 帧循环：**有且仅有一次真眨眼**
    帧索引 k034–k045 一次完整眨眼；**完全闭合 k039–k042**（30fps ⇒ t≈1.31–1.41s，全闭≈0.13s）
    判据：紫色虹膜像素数（开眼基线≈2100）→ k039–k042 只有 20（≈1%）；k038=1432、k043=568
· 另有"闭眼状态"素材（不是眨眼）：idle_closed_eye（738 帧≈12.55s）、closed_eye_trans（120 帧@8ms，
  once_then_hold，睁→闭专用过渡）、speaking_closed_eye_1（180f）/ _2（300f）
· 包内印样显示 `idle1`（120 帧@21ms loop）在 f023–f028 与 f073–f078 各有一次眨眼（可作站立态眨眼来源）
```

### 1.4 过渡与"拉远"（结论：**没有相机动画**）
```
· 宿主层零动画：Lively 只挂载一次同一个 URL 项目，之后所有 pose 变化都在同一页面内（docs/windows_wallpaper_lifecycle.md:39-41）
  → Wallpaper Engine/Lively 自带的场景过渡**不参与**
  · electron/src/main/index.ts 的 setBounds 全是静态 viewport；wallpaper/windows_desktop_layer.py 只有
    "贴桌面层 + 0.2s 重连轮询"
· 节点→节点 = **硬切**：`_goNext()` 注释原文 "no fade-out gap"（render/web/wallpaper_scene.js:1288-1299）；
  那段"淡出→换图→淡入"的 `_pendingNode` 分支**从未被赋真值 = 死代码**
· 全仓**唯一**的过渡常数：`_fadeDur = 0.35` 秒、**线性**（alpha = t，无缓动）、**只改 alpha**（无 scale/translate），
  且只用于「角色态 ↔ 场景态」切换（进入方向角色硬切消失、只有场景淡入；退出方向才是真交叉）
· "整张书桌可见"不需要动画：桌面底图**从头到尾都在**
· 空闲场景起始节点是 **stand_thinking**（不是 look at CRT，_startNode():1011-1018）
· 节奏（可照抄）：最后一次语音结束 **60 秒**后进入空闲场景；每个 pose **停 45~60 秒**随机；
  动画按作者帧率播完当前循环再换 pose
```

### 1.5 与 Live2D 的关系
```
· Live2D 是**并行 opt-in 后端**（2026-10-08 才加，默认仍是 Sprite），**不是**这套帧素材的生成器
  （包 manifest 版本 2026-08-29，比 Live2D 早 6 周；打包工具只吃 PNG 帧目录 + downloads/*.mp4 取 fps）
· 结论：**不用 Live2D**；这套帧素材 + 状态机就是原版的"Live2D 观感"来源
```

---

## 2. 资产盘点（三个包，本机 `F:\7AAA\AI\命运石之门\`）

| 包 | 大小 | 内容 | 已用 |
|---|---|---|---|
| `03-character-kurisu` | 2544 MB（7556 条目） | **39 个剪辑 / 7552 帧** KTX2（Basis/UASTC + ZSTD，zip 内 STORED 可随机读）；帧尺寸 4 变体：764×1028（6284 帧）/ 960×1028（738，idle_closed_eye）/ 764×1026（290，idle2）/ 764×1027（240，smile+trans_smile）；全部透明底 RGBA；含 runtime_manifest.json / graph_config.json / spriteforge_mouth_config.json | 仅 3 个剪辑（idle/speaking/thinking，≈6% 帧） |
| `04-visual-runtime` | 244 MB（196 条目） | `scenarios/runtime`：**180 帧 look_at_CRT 循环**（1070×860，30fps）+ **8 张独立 PNG 场景图**（BG_empty / scenario_backplate(=前者逐像素副本) / computer_use×2 / read_books·drinking_coffee / stand_thinking / whiteboard_use / look_at_CRT）+ `scenario_graph.json`；另有 `amadeus_ambient_{high,low}_blend.png`、`subtitle_frame_big.png`、键盘 sfx、`look_at_CRT_loop.mp4`（与 180 帧逐像素同帧，冗余，仅音轨独有） | 桌面底图 + 约 2 张场景 |
| `05-companion-kurisu` | 11.4 MB（20 条目） | 8 情绪 × (idle/speaking) 已是 webp + manifest（声明派生自 03） | 8 情绪 ×3 形态 |

**7 张"房间背景"**（CRT 屏内）：BG_empty（空房间）/ computer_use / sleep_desk / drink_coffee / stand_thinking / whiteboard_use / look_at_CRT。
**1 张"桌面背景"**（CRT 外）：`amadeus_desktop_wallpaper.png`（实拍书桌，原版最底层常驻）。
**2 张氛围光层** + **1 张字幕板**不是背景，是叠加层。

已解出并落在暂存区 `E:\DeepSeek1\work\_kurisu-full\`：44 张接触印样、39 个剪辑首帧、188 张场景 webp、
3 个 UI 素材、键盘音/循环音轨、`mapping.md`/`inventory.md`/`HOW-IT-WORKS.md`、`meta_json/`（9 个原始 JSON）、
`web/scenes/*.webp`（7 张，共 0.57 MB）、`web/statemachine.json`（37/87）、`web/scenarios.json`（6/19）。

**原始包（2.8 GB）不进仓库**；只把可复现的构建脚本入库。

---

## 3. 实现方案（浏览器端，零第三方库）

### 3.1 渲染层（DOM + 单 canvas）
```
kurisu-stage（fixed，铺满视口）
 ├ 桌面底图 <img>：零倍率 cover（按 coverTransform 公式算 scale/offset），**不模糊、不缩放动效**
 ├ 氛围光 high/low（两张 <img>，mix-blend-mode: screen，交替做呼吸；可选）
 ├ CRT 裁剪容器：CSS clip-path: polygon(14 点，来自 crt_config.json，按视口缩放)
 │   ├ 层1 空房间 backsplate <img>（BG_empty）
 │   ├ 层2 <canvas> 角色：帧图集 drawImage + 口型叠加层（同一 canvas 画两层）
 │   ├ 层3 字幕板 <img>（原版金属板）
 │   └ 层4 场景整图 <img>（6 个活动位之一；自带玻璃罩/暗角/扫描线 ⇒ 必须压在角色之上）
 └ 屏内状态行 / 字幕条（DOM，真实数据，取不到写"读不到"）
底部输入条（DOM，走 /api/public/ask）｜导航浮条（DOM，不遮挡 CRT）
```

### 3.2 运行时模块 `static/js/kurisu-runtime.js`（替代现有 kurisu-player.js 的职责）
```
1) 帧播放：每剪辑一张 WebP 图集（alpha 保留）→ drawImage 切帧 → 按**该剪辑的 frameIntervalMs** 推进
   （rAF + 时间累加；不用 setInterval 做帧循环）；支持 once_then_hold
2) 状态机：读 statemachine.json（nodes/edges/root/prob）→ 每段播完按出边 prob 归一化掷骰子；
   prob=0 的边为"宿主触发"（8 个进入点）；clips_not_in_graph=[sad, smile] 只能手动播
3) 场景机：读 scenarios.json（6 节点/19 边，自环 0.8、look at CRT 0.4、stand_thinking 无自环）；
   起始 stand_thinking；dwell 45~60s 随机；空闲（最后一次语音后 60s）进入场景态；她不在 = BG_empty
4) 口型：说话中用基础帧自带的嘴；静音（mouthValue ≤ 0.08）叠**整帧闭嘴图** + 椭圆遮罩只露嘴；
   有语音时按 10ms 窗 RMS × 3.75 驱动
5) 开场：播 look_at_CRT **180 帧真序列**（30fps；眨眼在 k039–k042）→ **硬切**到中景
   （如要更顺：0.35s 线性 alpha 交叉，并标注"节点之间用淡入属我方扩展"）
6) 降级：prefers-reduced-motion / 省流量 / 窄屏 → 只显示静帧；页面隐藏 → 暂停 rAF
7) 尺寸与内存：图集按需懒载；只保留当前+下一个剪辑；canvas 尺寸按 CRT 屏幕矩形 × devicePixelRatio（上限 2）
```

### 3.3 数据文件（仓库 `static/kurisu/`）
```
manifest.json        剪辑/帧间隔/图集几何/loopMode/scene 几何（含 crtPolygon 14 点）+ 开场条目
statemachine.json    37 节点 / 87 边 + root=idle + loop_mode_counts / frame_interval_counts
scenarios.json       6 节点 / 19 边 + start="stand thinking" + empty_room + dwell{60,45,60}
```
字段细节见 `E:\DeepSeek1\work\_kurisu-full\web\meta\spec-runtime.md`。

### 3.4 与站点其它部分的接线
```
· 输入条 → 现有 POST /api/public/ask（**不新增端点**）
· 她的回答 → 屏内字幕条逐句 + 播放 speaking 剪辑（说话中基础帧自带嘴动）
· 语音：等 Fish Audio Key（未提供）；无语音时只有字幕 + 嘴部帧，功能不残
· 屏内状态行 → 现有 /api/public/overview 等；取不到写"读不到"，不补数
· 其它页面（监测中心/笔记/靶场/关于）保持现状；主页只有场景 + 导航 + 输入条
· 回退：hugo 参数 kurisuEnabled=false（已实测：所有角色痕迹消失，仓库无需改代码）
```

---

## 4. 素材托管与体积口径

```
位置：全在博客仓库 `static/kurisu/**` → 由 **GitHub Pages** 分发
  （Pages = 免费全球 CDN、零出网费；srv1 是 ¥0.8/GB 按流量计费、峰值 3Mbps，不放）
首屏预算：**≤ 1.5 MB（严格）** —— 只载：当前剪辑 boot（前 24 帧低清）+ poster + 字幕板 + 开场 boot
其余：**全部懒载**（用哪段载哪段）；开场 hi 只留前 84 帧（覆盖眨眼 k039–k042）
静态总量：原闸门上限 12 MB → **建议改为 96 MB**（原因：7552 帧在任何可用分辨率下都塞不进 12 MB；
  总量不等于首屏，且全部懒载；Pages 软限 1GB / 单文件 <100MB，远未触及）
  替代方案（若要更省）：① 只发精选子集（约 10 个剪辑 ≈ 15~25 MB）；
  ② 整库放 Cloudflare R2（出网免费，但引入一个站外域名，与"零第三方"红线冲突，需站主点头）
本机实测：首屏 0.88 MB ｜ 角色+场景现状 10.02 MB ｜ 7 张场景 webp 共 0.57 MB
```

---

## 5. 构建流水线（可复现，产物进仓库）
```
scripts/kurisu/build_kurisu_assets.py    03 剪辑 → 图集/boot/poster + manifest（KTX2 解码用 ktx.exe）
scripts/kurisu/build_intro_clip.py       04 的 180 帧 → 开场图集（30fps / stride 1 / role=intro）
scripts/kurisu/apply_crt_geometry.py     crt_config.json 多边形 → manifest.scene.crtPolygon
scripts/kurisu/build_scene_webps.py      04 的 8 张 PNG → 7 张 webp（去掉逐像素重复的 backplate）
（素材线的 tools/*.py 亦可迁入。）约束：原始 zip 不入库；脚本 fail-closed（0 字节 / 解不开 / 引用不符 → 拒绝产出）
```

## 6. 门禁（每次发布都跑）
```
· scripts/assert-build.sh（16 项）：零第三方外链 / bg.jpg SHA256 不变 / 无 0 字节资产 /
  首屏预算 1.5MB（兜底只算 idle 系）/ 发布链一致性 / 播放器保留 reduced-motion+visibility+图集逻辑 等
· _dev/verify-redesign.ps1（125 项，真浏览器 CDP）：取景标定、遮挡自查、对比度、降级、端点结构不变 等
· SecAgent 侧另有 586 个单测（与本站无关，但同一红线：零造假）
```

## 7. 分期与验收（每期都要证据，不许口头结论）
```
P1 素材全量化：39 剪辑 + 7 场景 + 180 帧特写 + 口型闭嘴帧 → 图集（给体积实数表：每个 KiB/MB + 合计）
P2 运行时：状态机自动游走（给 30 秒节点序列）+ 39 剪辑逐一可播（**证据矩阵：逐行剪辑 → 截图 → ✅/❌**）
P3 场景机 + 空房间 + 开场：0–15 秒每秒一帧 4×4 印样与录屏印样并排 + **k039–k042 那 4 张连续帧**（证明眨眼）
P4 口型：说话中 / 静音 对照截图
P5 接线与降级：输入条→ask→字幕+说话动画；reduced-motion / 窄屏 / 页面隐藏
P6 上线：push → CI → gh-pages → 线上复验（含首屏体积实测）
```

## 8. 未决项 / 风险（需站主或评审者定）
```
① 静态总量上限：12 MB → 96 MB？（否则 39 个动作无法全量进仓库；替代方案见 §4）
② 眨眼范围：素材只在特写循环里有真眨眼（k034–k045）；中景站立态要眨眼只能用 idle1 自带的眨眼帧
   或 closed_eye_trans 的"闭眼状态"（原版就是这么用的）→ 是否只在开场保留眨眼？
③ 鼠标跟随：原版 Sprite 路径**没有**此法；要做属新增功能（原版侧看靠 idle_side_* 剪辑）
④ 无语音时的口型：只有字幕 + 基础帧自带嘴动（RMS 驱动需要音频）；是否接受
⑤ 开场过渡：硬切（原版）＝最忠实；0.35s 线性 alpha 交叉＝"节点间使用属我方扩展"
⑥ 录屏事实更正：录屏开头 0–2.033s **是静止睁眼特写、没有眨眼**；录屏里的眨眼在站立段
   t≈12.90–13.10s 与 t≈22.87–23.10s（各约 0.23s）。原包特写循环的眨眼在 k039–k042。
```

## 9. 当前实现现状（2026-10-14 上午）
```
· 主页已上线：正文旧内容全部移除（正文里 xk-hero/xk-hstat/xk-notes = 0、scrollHeight == innerHeight）
· 场景：全屏书桌 + CRT 内角色；CRT 用原版 14 点多边形（替掉先前错误的矩形）；
  取景 = 零倍率 cover（用掩屏多尺度 NCC 把 desk.webp 配准到录屏：第 2 秒 = 原图 1.00 倍 cover、NCC 0.965）
· 开场：播原包 180 帧真序列（线上 opening.boot.webp 275 KB / opening.hi.webp 1004 KB，已裁到 84 帧）
· 屏内：状态行（真实数据，取不到写"读不到"）+ 字幕条（对比度 10.7:1）
· 底部输入条（走 /api/public/ask）｜导航浮条｜其它页面不受影响
· 体积：首屏 0.88 MB（预算 1.5 MB）｜发布断言 16/16
· **未做**：39 个动作全部可播、状态机自动游走、6 个房间活动位、空房间状态、口型叠加层（素材已产出待接线）
```

## 10. 关键证据文件（可复核）
```
E:\DeepSeek1\work\_kurisu-full\HOW-IT-WORKS.md     源码级机制（1150 行，含 §⑦ 宿主层过渡专章）
E:\DeepSeek1\work\_kurisu-full\refs\               15 个逐字源码切片（renderer.js / wallpaper_scene.js 等）
E:\DeepSeek1\work\_kurisu-full\web\statemachine.json / scenarios.json / meta\spec-runtime.md
E:\DeepSeek1\work\_kurisu-full\sheets\ALL_clips_overview.png   39 剪辑总览（每格标剪辑名/帧数/尺寸）
E:\DeepSeek1\work\_video-frames\sheet-16s.png      录屏开头 0–15 秒每秒一帧（目标效果参照）
E:\DeepSeek1\work\_video-frames\blink-report.md    眨眼逐帧报告（21 张证据图 blink-evidence\）
F:\7AAA\AI\blog\_dev\kurisu\                       截图、并排对照、闸门原文、取景标定 JSON
```
