# 提示词（可直接复制给别的 AI）——把 Amadeus 改造成我的静态博客主页

> 用法：把下面 `====` 之间的全部内容复制给对面 AI。若它能读我这边的文件，见 §七 的路径清单；
> 读不到也没关系，§一/§二 已把关键事实与数值写全。

====

你是一位资深的**前端 / 图形运行时 / 交互架构**评审。我要把一款开源桌面 AI 伴侣（**Amadeus**）的整套
"桌面宠物"体验，改造进我的**个人静态博客**主页。请你先完整理解原项目、再逐条评审我的改造方案，并给出你的方案。

**不要写完整代码**，给架构、模块划分、数值、取舍与理由。

---

# 一、原项目（Amadeus）是什么 —— 功能清单

出处：`github.com/Code-Amadeus/Amadeus`（我读过它的源码 `@ d8fc369`，4197 个文件）。
它是一个 **Windows 桌面壁纸程序**：把自己挂进 Lively / Wallpaper Engine 的**壁纸层**（`wallpaper_engine_bridge.py`、
`windows_desktop_layer.py` 用 `SetParent`/`SetWindowPos` 把窗口钉在桌面层），另有一个 Electron 交互层。
它**不是**网页应用，也不依赖任何 Web 框架。

## 1.1 视觉：一张实拍书桌 + CRT 显示器里的角色
```
· 一张实拍书桌大图 **cover 铺满**，是舞台**最底层、从头到尾常驻**（`addChildAt(nextBg, 0)`）
· 用**硬编码的 CRT 多边形**当屏幕遮罩（`wallpaper/crt_config.json:24-81`，AABB 550..1136 / 195..638，基准图 1672×941）
· 多边形**内部**依次贴：① 空房间底图（`BG_empty.png`）② 角色精灵（帧图集，透明底 RGBA）
  ③ 字幕板（`subtitle_frame_big.png`，做旧金属板 2564×430）④ 场景整图（6 个之一）
  ⑤ 之后叠：氛围光 high/low（两张 alpha 掩码逐值相同、只差亮度）、ADD 辉光、扫描线、暗角
· 坐标：`coverTransform`（`render/web/wallpaper_scene.js:16-25`）
· **角色落位公式**：`scale = min(W*0.64/764, H*0.90/1028)`，`x = 0.52W`，`y = bottom - 1.2%H`，anchor=(0.5,1)
  （`renderer.js:797-825`）
```
**注意**：6 张场景图（在电脑前 / 趴桌睡 / 喝咖啡 / 站着想事 / 白板前 / 贴脸看屏幕）**角色已经合成进画面**，
且自带 CRT 玻璃罩/暗角/扫描线 —— 也就是说"她在房间里活动"这层其实是**换整图（硬切）**，不是逐帧动画。

## 1.2 角色引擎：**预渲染帧序列 + 概率状态机**（没有骨骼、没有实时变形）
```
· 素材：**39 个剪辑 / 共 7552 帧**，每帧 764×1028 透明底 RGBA（另有 3 种帧尺寸变体：960×1028 / 764×1026 / 764×1027）
· 播放：PIXI ticker 逐帧换贴图（`renderer.js:987-1076`）；**`frameIntervalMs` 是每帧时长（毫秒）**，不是 fps
  全表：17ms × 22 个剪辑 / 21ms × 6 / 8ms × 10 / 5ms × 1（主力≈58.8fps）
· 12 个剪辑是 `once_then_hold`（播一遍停末帧后立刻换节点）；过渡剪辑在"没有语音"时停末帧等她说
· **状态机**：`graph_config.json` = **37 节点 / 87 条边**，`root = idle`；每段剪辑播完**掷骰子**按出边概率跳下一个节点
  （`_nextAutoNode:1534-1549`）→ 这是"她看起来活着"的真正来源
· **情绪入口的概率被写成 0.00** = 不被随机选中，**必须由宿主触发**（按钮/事件）；`sad` / `smile` 两个剪辑**不在图里**，只能手动播
· 动画节奏可调：环境变量 `AMADEUS_SCENARIO_STATIC_SECONDS` 之类可以固定停留时长
```

## 1.3 房间与节奏（"好几个动作"来自这一层）
```
· `scenario_graph.json` = **6 个节点 / 19 条边**（自环概率：computer use 0.8 / sleep_desk 0.8 / drink_coffee 0.8 /
  whiteboard use 0.8 / look at CRT 0.4 / stand_thinking **无自环**）
· **空闲场景起始节点是 `stand_thinking`**（`_startNode():1011-1018`）
· 触发：最后一次语音播放结束 **60 秒**后进入场景态；每个 pose 停留 **45~60 秒**（随机）；播完当前循环再换 pose
· 她不在时显示**空房间**（`BG_empty.png`；它和 `scenario_backplate.png` 逐像素相同）
```

## 1.4 过渡（**全项目没有相机动画**）
```
· 节点→节点是**硬切**：`_goNext()` 注释原文 "no fade-out gap"（`wallpaper_scene.js:1288-1299`）；
  那段"淡出→换图→淡入"的 `_pendingNode` 分支从未被赋真值（死代码）
· 全项目唯一的过渡常数：`_fadeDur = 0.35` 秒、**线性**（alpha = t，无缓动）、**只改 alpha**，
  且只用于「**角色态 ↔ 场景态**」切换（`wallpaper_scene.js:551-557, 967-992`）
· 宿主层（Lively / Electron / 桌面层脚本）**没有任何窗口或画布的缩放/位移/淡入动画**：
  日志生命周期文档全篇无动画；`setBounds` 全是静态 viewport；桌面层脚本只有"贴桌面层 + 0.2s 重连轮询"
· 「整张书桌可见」不需要动画：桌面底图一直就在
```

## 1.5 语音与口型
```
· 语音后端两条路（`tts/registry.py` 注册表）：
  ① **本地**：GPT-SoVITS 常驻子进程（`tts/gpt_sovits_sidecar.py`，JSON-lines 传输；模型路径 env `TTS_SOVITS_MODEL_PATH`；
     合成 revision 带 `local_only`）→ **吃显存/内存**
  ② **在线**：README 明确推荐 **Fish Audio S2.1 + 牧濑红莉栖音色**
· **口型不是 TTS 算的**：播放音频时按 **PCM 10ms 窗算 RMS × 3.75**（clamp 0~1，首窗保底 0.12），
  **先把这一窗的口型值发给渲染器，再把该段音频写进声卡**；停止时发 0（`tts/playback.py:80-90, 180-245`）
  · 注释说明：用 PCM 时间轴上的包络窗而不是"墙上时钟节流"，因为 50ms 窗会抹掉音节间的短停顿
· **口型渲染 = 两层拼装**：说话中用基础帧**自带的**嘴；**静音（mouthValue ≤ 0.08）**时叠一张**整帧"闭嘴"画面**，
  按嘴部锚点平移对齐 + **椭圆遮罩只露嘴部**
  ⚠️ 常见误读：`spriteforge_mouth_config.json` 里的 "34×18" 是**这个椭圆遮罩的尺寸来源**，**不是**补丁尺寸；
  `openness[]` 是**作者侧离线预分析**的静态逐帧值（用来找"哪一帧是闭嘴帧"），**不是**运行时音量
· 其它语音工程细节：首句音频缓存（`first_sentence_audio_cache.py`）、字幕（`subtitle.py`）、
  回声消除 AEC（`aec_realtime.py`）、延迟时钟（`latency_clock.py`）、语音起始点检测（`speech_onset.py`）、
  句级调度（`utterance_scheduler.py`）
```

## 1.6 人设（**分层文件，不是一个提示词**）
```
· `core/character_profiles.py`            角色档案
· `llm/character_prompts.py`（14KB）      **人设提示词**
· `llm/character_voice_lines.py`（31KB）  **台词库**（按场景/情绪的固定台词）
· `core/character_rag.py` + `config/catalog/models/character_rag.json` + `docs/character_rag*.md`（4 篇）
                                          **角色知识库（RAG）**
· `examples/character-rag/kurisu.zh.json` / `kurisu.ja.json`   角色知识样例（中/日）
· `render/character_pack.py`（14.6KB）    把"视觉 + 台词 + 情绪"打成**角色包**
· `docs/character-management.md` / `character-runtime.md` / `character_pack_authoring.md`  角色管理与制作规范
· 行为约束写进人设，例如：**内置人格通常最多回复 6 句**
· **音色**是独立一层：在线档=音色模型（Fish Audio），本地档=GPT-SoVITS 参考音频
```

## 1.7 视觉后端的另一条线
```
· **Live2D 是并行的 opt-in 后端**（2026-10-08 才加入，默认仍是上面的 Sprite 帧序列后端）
· 我手上的素材包 manifest 版本是 **2026-08-29**，比 Live2D 早 6 周；打包工具只吃 PNG 帧目录
  → **这套"帧序列 + 状态机"不是用 Live2D 生成的**
```

## 1.8 眨眼（决定"她像不像活的"的关键细节）
```
· 03 的 39 个剪辑：实测 idle/idle1/smile/sad 共 **480 帧，闭眼事件 0 个**（Sprite 路径没有眨眼机制）
· 04 有一段 **180 帧特写循环（1070×860，30fps）**，里面有**且仅有一次真眨眼**：
  第 **34–45** 帧一次完整眨眼，**完全闭合在第 39–42 帧**（30fps ⇒ t≈1.31–1.41s，全闭≈0.13s）
  （判据：紫色虹膜像素数，开眼基线≈2100；39–42 帧只有 20）
· 另有"闭眼**状态**"素材（不是眨眼）：`idle_closed_eye`（738 帧≈12.55s）、`closed_eye_trans`（120 帧@8ms，
  once_then_hold，睁→闭专用过渡）、`speaking_closed_eye_1`(180f) / `_2`(300f)
```

---

# 二、我手上有什么

```
· **三个官方素材包**（另有一位站长提供的参考录屏 1918×1078 / 30fps / 10:30）：
  ① 角色包 2.54GB：39 剪辑 / 7552 帧 KTX2（Basis/UASTC + ZSTD；zip 内 STORED，可随机读单帧）+
     `runtime_manifest.json`（clips + mouthOverlays）+ `graph_config.json`（状态机 37/87）+
     `spriteforge_mouth_config.json`（16 个口型 profile + 闭嘴帧信息）
  ② 视觉运行时 244MB：`scenarios/runtime` = **180 帧 look_at_CRT 循环** + **8 张独立 PNG 场景图**
     （其中 scenario_backplate 与 BG_empty 逐像素相同）+ `scenario_graph.json`；另有氛围光两张、字幕板、键盘音、
     与 180 帧同帧的 mp4（仅音轨独有）
  ③ 陪伴包 11.4MB：**8 情绪 × (idle/speaking) 已是 webp**
· **其源码克隆**（4197 文件），我把机制整理成了带源码行号的文档（1150 行）+ 15 份逐字源码切片
· **已导出的机器可读数据**：状态机 JSON（37 节点/87 边 + loopMode + frameIntervalMs + 帧数）、
  场景 JSON（6 节点/19 边 + 起始节点 + 空房间 + 停留参数）、字段说明书
· **已转好的网页资产（暂存）**：7 张房间背景 webp（源 PNG 11.65MB → **0.57MB**）、
  180 帧特写的图集、39 个剪辑的分档图集（boot 前 24 帧 / medium / atlas），合计约 300MB（含冗余分档）
· 参考录屏的逐帧结论（我做的）：**开头 0–2.033s 是静止睁眼特写（没有眨眼）**；能看到眨眼的两次在
  拉远后的站立段 t≈12.90–13.10s 与 t≈22.87–23.10s；"拉远"是**场景硬切**（用掩屏多尺度 NCC 把桌面底图配准到
  录屏：第 2 秒 = 原图 **1.00 倍 cover**、NCC 0.965，其余秒的取景差异完全由窗口宽高比解释）
```

---

# 三、我要把它改造成什么

**目标站**：我的个人安全实验室博客（静态站，Hugo + 原生 HTML/CSS/JS，无框架，哈希路由 SPA，**GitHub Pages** 托管）。
主页要变成：**一张实拍书桌照铺满全屏 + 正中间 CRT 显示器 + 屏幕里"活着"的角色**（读者一进站就看到），
她会自己动、会说话（字幕 + 语音）、会换房间活动位；页面底部一条输入条可以跟她对话。

**硬约束（不可违反）**：
```
① **零第三方依赖**：不得引用任何站外脚本/字体/图标库/CDN；不得新增站外域名（含对象存储域名，除非我特批）
② **零造假**：接口取不到数据就显示"读不到"，绝不用占位数字
③ **公开面不泄露**：蜜罐抓到的完整口令永不上公网（只给长度/字符类/结构）
④ **首屏加载 ≤1.5MB（严格）**；其余资产一律懒载；每次交付要给"首屏加载量 / 资产总量"两个实数
⑤ 一键回退：一个 `kurisuEnabled=false` 开关必须能让所有角色痕迹消失
⑥ 站内已有后端端点可直接用：`POST /api/public/ask`（问答，带限流与六态机读状态）、
   `POST /api/public/tts`（**语音代理：三道防滥用闸 + sha256 磁盘缓存 + kill switch；目前关闭态，等语音 Key**）、
   以及若干只读 `GET /api/public/*`（概览/告警/蜜罐/审计/地理/访问统计/攻击故事线）
⑦ 发布纪律：改完必须过两道门禁（发布断言 16 项 + 真浏览器 CDP 验收 125 项），全绿才发布
```

---

# 四、我的改造方案（请逐条评审、挑错、给替代）

## A. 渲染层（DOM + 单 canvas）
```
外层 fixed 铺满：桌面底图 <img>（零倍率 cover，按上游 coverTransform 公式算 scale/offset）
 ├ 氛围光 high/low（两张 img，mix-blend-mode: screen，交替做呼吸）
 ├ CRT 裁剪容器：CSS clip-path: polygon(14 点，来自上游 crt_config.json，按视口缩放)
 │   ├ 层1 空房间底图 <img>（BG_empty）
 │   ├ 层2 <canvas> 角色：基底帧 + 口型叠加层（同一 canvas 画两层）
 │   ├ 层3 字幕板 <img>（上游金属板）
 │   └ 层4 场景整图 <img>（6 个活动位之一；玻璃罩/暗角/扫描线在它里面 ⇒ 必须压在角色之上）
 └ 屏内状态行 / 字幕条（DOM，真实数据，取不到写"读不到"）
底部输入条（DOM）｜导航浮条（DOM，不遮挡 CRT）
```

## B. 运行时（自研，无第三方库）
```
1) 帧播放：每个剪辑一张 WebP 图集（保留 alpha）→ drawImage 切帧 → 按该剪辑的 frameIntervalMs 推进
   （rAF + 时间累加，不用 setInterval 做帧循环）；支持 once_then_hold
2) 状态机：读导出的 statemachine.json（37 节点/87 边 + 概率 + root）；每段播完按出边 prob 归一化掷骰子；
   prob=0 的边 = 宿主触发（8 个进入点）；sad/smile 只能手动播
3) 场景机：读 scenarios.json（6 节点/19 边 + 自环 + 起始 stand_thinking + 空房间 + dwell{60,45,60}）；
   她不在 = 空房间
4) 开场：播 180 帧真序列（眨眼 39–42 帧自带）→ **硬切**到中景（如需更顺：0.35s 线性 alpha，标注为我的扩展）
5) 降级：reduced-motion / 省流量 / 窄屏（≤980px 只用 132px 头像图集）/ 页面隐藏暂停 / 资产加载失败 → 静帧
6) 内存：图集懒载，只保留当前 + 下一段；canvas 尺寸按 CRT 屏幕矩形 × devicePixelRatio（上限 2）
```

## C. 口型与语音（**不跑任何本地 TTS**）
```
① 文本 → 站内 `POST /api/public/tts`（我的代理）→ **云端 Fish Audio** → 音频回浏览器（带磁盘缓存）
② **口型包络在浏览器里算**：Web Audio 按 **10ms 窗 RMS × 3.75**（clamp 0~1、首窗保底 0.12），
   照抄上游算法，但跑在读者浏览器 → 我的服务器/本机几乎零算力
③ 没有语音 Key 时的兜底（三条，按优先级）：
   a. **预生成固定台词音频**（进站问候/切页解说/状态播报等十几段小文件）+ **离线预计算的口型包络 JSON**
      → 嘴跟着声音动，运行时零算力
   b. 浏览器自带 speechSynthesis（零依赖，但音色机械、拿不到音频流 → 口型只能伪驱动）
   c. 只有字幕 + 帧里自带的嘴（观感"在说话"，但不同步）
④ 静音闭嘴层：说话中用基础帧自带嘴；mouthValue ≤ 0.08 时叠**整帧闭嘴图** + **椭圆遮罩只露嘴**
```

## D. 人设与台词
```
· 对话人设 → 我的 `/api/public/ask`：**系统提示词**（性格/说话风格/行为边界，例如最多 6 句）+ **RAG 知识库**
  （现有 318 条向量，可把角色设定与本站安全语料一起入）
· 台词库 → 固定场景若干句（问候/解说/取不到数据时），随站点资源下发；动态回答来自 /api/public/ask
· 视觉人设 → **情绪 ↔ 剪辑映射**（8 情绪 + 39 剪辑里的情绪剪辑）；注意情绪入口 prob=0 = **必须宿主触发**
· 音色 → 云端同一个音色模型（与上游 README 推荐的档位一致）
```

## E. 资产与加载
```
· 分层：`boot`（前 24 帧低清，首屏只载这个）+ `poster`（静帧）+ `atlas`（完整图集，懒载）
· 分辨率：图集高度 320~360、WebP q78、alpha 保留
· 体积：首屏 ≤1.5MB（严格）；**静态总量上限我打算从 12MB 改为 96MB**
  （理由：7552 帧在任何可用分辨率下都塞不进 12MB，估算 60~80MB；总量 ≠ 首屏，且全部懒载；
   Pages 软限 1GB、单文件 <100MB）
  → 替代：① 只发精选子集（约 10 个剪辑，15~25MB）② 整库放对象存储（引入站外域名，与我红线冲突）
```

## F. 验收（证据矩阵，不许口头结论）
```
P1 素材全量化（39 剪辑 + 7 场景 + 180 帧特写 + 口型闭嘴帧，给体积实数表）
P2 运行时（状态机 30 秒游走的节点序列 + 39 个剪辑逐一可播的截图矩阵）
P3 场景机 + 空房间 + 开场（0–15 秒每秒一帧印样与参考录屏并排 + **第 39–42 帧四连帧**证明眨眼）
P4 口型（说话中 / 静音对照截图）
P5 接线与降级（输入条 → /api/public/ask → 字幕 + 说话动画；reduced-motion / 窄屏 / 页面隐藏）
P6 上线（发布 → 线上复验，含首屏体积实测）
```

---

# 五、我要你回答什么（请逐条，按顺序）

```
1) 这套"帧序列 + 概率状态机"搬到浏览器，**模块划分**你会怎么做？我上面 A/B/C 的分层有没有冗余、缺失或耦合过重？
2) **资产策略**：39 剪辑 / 7552 帧，图集切分、懒载顺序、首屏预算你会怎么定？
   静态总量 96MB（GitHub Pages）这个口径你认可吗？有没有更好的做法（比如合并图集、按需解码、WebCodecs/视频流）？
3) **口型同步**：在"不跑本地 TTS"的前提下，怎么让"说话时嘴跟着声音"最稳？我给的三条兜底路线够不够？
   有没有更可靠且不引第三方的做法（例如 OfflineAudioContext 预分析、AudioWorklet、预生成包络）？
4) **人设**：怎么设计才不像"套壳聊天框"——她的话、情绪、动作三者怎么联动才自然？台词库与自由回答怎么分工？
5) **状态机保真度**：概率游走 + once_then_hold + 情绪宿主触发，在浏览器里跑要注意什么
   （时序、标签页隐藏、路由切换、多实例、内存回收）？
6) 我的方案里**最可能翻车的三处**是什么？给出替代方案与代价。
7) 如果只做三件事，先做哪三件（按"最小可行 + 可验收"排序）？
8) 还有哪些上游机制是我**漏掉的**（我列了合成/状态机/场景/口型/眨眼/过渡/人设/语音），请指出遗漏与它值不值得照抄。
```

# 六、输出格式

```
· Markdown，按上面 1–8 分节
· 关键数值用表格（像素 / 毫秒 / 字节 / 概率）
· 每条结论标注依据：[上游源码] / [实测] / [推断] / [我的设计]
· 最后给两节：**风险清单**（按严重度排序）与**最小可行路径**（3 步，每步的验收标准）
· 不要写完整代码；给规格、伪代码、数值与取舍
```

# 七、可附材料（若你能读文件）

```
· 源码级机制（1150 行，带 file:line）：F:\7AAA\AI\blog\docs\amadeus-research\HOW-IT-WORKS.md
· 15 份逐字源码切片：F:\7AAA\AI\blog\docs\amadeus-research\refs\
   （renderer_frame_transform.js / renderer_mouth_layer.js / renderer_graph_runtime.js /
     wallpaper_scene_composition.js / wallpaper_scene_placement.js / scenario_assets.py /
     spriteforge_animator_{constants,mouth}.py / tts_mouth_pipeline.py / package_mouth_overlays.py /
     detect_mouth_masks_core.py / doc_{mouth_sync_notes,live2d_and_pack_boundary,assets_boundary,pack_boundary}.md）
· 机器可读数据：F:\7AAA\AI\blog\docs\amadeus-research\data\
   （statemachine.json 37 节点/87 边｜scenarios.json 6 节点/19 边 + 起始/空房间/停留｜spec-runtime.md 字段说明）
· 实现方案总纲：F:\7AAA\AI\blog\docs\主页实现方案-照搬Amadeus原版.md
· 改造须知（站点约束/门禁/环境坑）：F:\7AAA\AI\blog\docs\改造须知-给前端AI.md
· 原项目源码：E:\DeepSeek1\work\_amadeus-src（4197 文件，@ d8fc369）
```

====
