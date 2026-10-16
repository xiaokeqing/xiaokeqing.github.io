# 博客角色「动画 + 语音」实现全貌 · 前因后果 + 服务器配置（给外部 AI 评审）

> 目的：把**这件事怎么来的、做过什么、现在是什么样、服务器怎么配的、有哪些坑与未决项**一次写全，
> 交给外部 AI 判断"有没有更好的方案"。
> 标注：`[实测]` 有原始输出可复核 ｜ `[约定]` 契约/纪律 ｜ `[未验证]` 尚未实测 ｜ `[已否决]` 试过并放弃。
> 不含任何密钥。域名 `xiaokeqing.cn`，站点是个人安全实验室博客（Hugo + 原生 HTML/CSS/JS）。

---

## 1. 目标与用户诉求（按时间顺序，含两次纠偏）

```
① 最初：主页做成"实拍书桌照 + 正中间 CRT 显示器 + 角色活在屏幕里"，要**类似 Live2D 的动效**，
   并研究开源项目 Amadeus（github.com/Code-Amadeus/Amadeus）是怎么做的
② 我研究后确认：Amadeus 的 Sprite 后端 = **预渲染帧序列 + 概率状态机**（不是骨骼/Live2D），
   于是整套机制照着它复刻（详见 §3）
③ 用户拿到并下载了官方素材包（角色 39 剪辑 / 场景 / 伙伴头像 / GPT-SoVITS 语音 等）
④ **纠偏 A（重要）**：用户要求"所有模块都照着那个别的 AI 做的改，人家的好看" ——
   我最初只"借用设计语言"（保留站点自己的结构，只换视觉风格）✗
   → 用户明确推翻：**整站照 `docs/demo-内容页外壳.html` / `docs/demo-主页.html` 改，一字不增不减** ✗
     （我先前还自己加了"像素差 ≤2%"的验收门槛，也是我自定的，已作废）
⑤ **纠偏 B（重要）**：我曾把素材**降质**（大部分剪辑只发 0.5× 档；字幕垫板 382KB→87KB）✗
   → 用户要求"以作者素材为准、不许降质" ⇒ 现在：垫板已换回原图 ✓、视频方案走 1x 高分辨率 ✓
⑥ Amadeus 发布 0.17.0 α（本地 ASR/TTS + 视频供帧 + 新角色包）→ 用户要求评估"能不能用来优化"
   ⇒ 结论：**能**（见 §6），主角是那 40 组视频，而不是"重新校色"
```

---

## 2. 素材与硬事实（`[实测]`）

| 项 | 值 |
|---|---|
| 角色包（现行） | `amadeus-character-kurisu-2026.10.14-keypoint-return-v3.zip` 2,764,878,533 B<br>sha256 `feff14e2c9aeeaee1f8d7a6b780a2f183be71b79a1a1bca2c02b2d4bc61c72e6` |
| 校验/安装 | `uv run --locked --no-sync python tools\external_assets.py verify/install "<zip>"` → `OK: packs=1 files=7812 bytes=2760906925`；安装到 `…\assets\spriteforge\runtime\kurisu`（7812 文件 / 2.63GiB） |
| 构成 | `.ktx2` 7688 ｜ `.ivf` 80（=40 组「color 流 + alpha 流」）｜ `.json` 44 |
| 与旧包（2026-09-26）差异 | only_new 257 ｜ only_old 0 ｜ 未变 5 ｜ **变更 7550**；变更后体积反而小 5.7%（裁掉透明边） |
| 语音包 | `02-voice-kurisu-gpt-sovits-v3`（2.77GB，v3 权重 + `assets/audio/reference` 参考音频）<br>另有 `…v3-with-emotions-2026-10-14.zip`（2.78GB，带情绪）；ASR 包（2.69GB）**明确不用**（不做语音输入） |
| 现有线上角色资产 | `static/kurisu/` ≈ **82MB**：medium 49 文件 / 48.2MB（37 个图内剪辑）、hi 8 文件 / 20.6MB、voice 25 文件 / 0.47MB、mouth 48、avatar 24 |
| 资源上限（门禁） | `scripts/assert-build.sh` ⑨：`static/kurisu + static/images/crt ≤ 80 MiB`（当前 79MB，余量约 1.5MB） |

---

## 3. 动画实现（照 Amadeus 复刻，源码级）

### 3.1 合成层序（不是 3D、无相机动画）
```
实拍桌面大图 cover 常驻（最底层）
→ 氛围光（mix-blend-mode: screen，呼吸动画，7s）
→ **硬编码的 CRT 多边形** 裁剪（`crt_config.json` 的 14 点多边形，AABB 550..1136 / 195..638，基准图 1672×941）
→ 多边形内依次：① 空房间 backplate ② 角色 <canvas>（帧图集）③ 字幕垫板 ④ 场景整图（可选）
→ 扫描线 + 暗角
`[实测]` 参考录屏的"拉远"= **场景硬切**（掩屏多尺度 NCC 配准第 2 秒 = 原图 1.00× cover、NCC 0.965）
⇒ 全项目**没有相机动画**；唯一过渡常数 `_fadeDur=0.35s` 线性 alpha，且只用于「角色态 ↔ 场景态」切换
```

### 3.2 角色落位（源码公式，`[约定]` 不许改）
```
scale = min(W * 0.64 / 764, H * 0.90 / 1028)
x = 0.52W ｜ y = bottom − 1.2%H ｜ anchor = (0.5, 1)
```
（对应 demo 里的 `CHAR_BOX = {w:764, h:1028, maxW:0.64, maxH:0.90, xRatio:0.52, footRatio:0.012}`）

### 3.3 帧播放与状态机
```
· 剪辑帧表：39 个剪辑 / 7552 帧；**frameIntervalMs 是每帧时长**（17ms×22 / 21ms×6 / 8ms×10 / 5ms×1）
· 12 个剪辑是 `once_then_hold`（播一遍停末帧）
· 状态机：37 节点 / 87 边，root = idle，每段播完按出边概率掷骰子
  · **`prob=0` 的 9 条边 = "宿主触发入口"**（原版语义：永不被随机选中）
  · `[实测]` 我独立模拟 2000 步：**纯概率游走只能覆盖 9/37 个剪辑**，其余 28 个（全部说话/情绪/思考）
    必须由宿主事件触发 ⇒ 这是原版设计，不是 bug
· 我们已实现：**事件驱动宿主触发**（`voice` / `emotion`（状态行真实文本变了才换，20s 防抖）/ `idle`（>12s）/ `cadence`），
  时间线记入 `__xkSm.hostTimeline`
· 新增动画 `key_point_to_thinking`（0.17.0 α）：`[实测]` **逐帧等于已有 `thinking_to_key_point` 的倒放（mean/max diff = 0）**
  ⇒ 用"倒放开关"实现，**0 新增字节**；状态机 → **38 节点 / 88 边**
```

### 3.4 口型（两层，与原版一致）
```
说话中：基础帧**自带的嘴**在动（作者把口型画进帧里）
静音时：mouthValue ≤ 0.08 → 叠**闭嘴层**（原版做法：整帧闭嘴图 + 椭圆遮罩，34×18 是遮罩尺寸来源）
数据：16 个剪辑有口型 profile（`closed_frame_idx` / `anchor_track`逐帧嘴部坐标 / `openness` 静态分析值）
我们的取舍：12 个"用自己的闭嘴帧"的剪辑用**离线裁好的嘴部小补丁**；4 个"借别的剪辑闭嘴帧"的
（shy_speaking1/2、surprise_speaking、angry_speaking → 指向各自的 trans 剪辑）用**原方案（截块+椭圆遮罩）**
`[实测]` 同帧同锚点 A/B：NCC **0.9928~0.9949**、平均差 <0.6/255 ⇒ 对得齐
`[约定]` **不使用**上游 `holdClosedFrame()` 的 `argmin(openness)` 覆盖逻辑（那是上游已知 bug 区域）
```

### 3.5 眨眼（诚实结论）
```
39 个剪辑的 480 帧里**没有闭眼事件**（中景不眨眼）；只有 `look_at_CRT` 的 180 帧里有**一次真眨眼**（帧 34–45，完全闭合 39–42）
另有"闭眼状态"素材：idle_closed_eye(738f) / closed_eye_trans(120f@8ms) / speaking_closed_eye_1·2
`[未做]` 中景眨眼计划：用 `idle1`（包内印样显示 f023–f028 / f073–f078 各有一次眨眼）加权插播
```

### 3.6 当前实现状态（诚实）
```
· **口径刚被用户推翻**：不再"套我们自己的 SPA 外壳 + kurisu-player"，改成
  **把 demo 文件整份搬成生产页**（含它自己的内联样式与脚本），只把素材路径指到我们 static/ 下的真实文件
· 主页 demo（222 行，自包含）已读完：4 剪辑（opening 84f/33.3ms → idle 60f/42ms → speaking 90f/34ms →
  thinking 90f/34ms）、canvas 逐帧、开场放完**硬切** idle、HUD 打字、bootveil、reduced-motion 静帧、
  CRT 高度 <260px 降级；**demo 自身缺 `opening.hi.webp`**（所以它自己开场画不出来），我们那份是有的
· 五页（monitor/notes/labs/about/ai）尚未搬 ✗
```

---

## 4. 语音实现

### 4.1 三层结构（`[约定]`）
```
L1 固定台词（问候/切页解说/状态播报/兜底/事件播报）→ **预生成静态音频**，随站分发，零运行成本
L2 任意句子（AI 自由回答）→ **运行时合成**：站内代理 `POST /api/public/tts` → 云端（Fish Audio）→
   返回 {audio, envelope}；代理内有三道防滥用闸 + sha256 磁盘缓存 + kill switch（**无 Key 时 503 关闭态**）
L3 无音频时：字幕 + 帧里自带的嘴（**不会**假装对口型）
```

### 4.2 口型同步的契约（`[约定]`，服务端与离线生成都产同一格式）
```
envelope = { sampleRate, hopMs: 10, values[0..1] }
生成：10ms 窗 PCM RMS × 3.75，clamp 0~1；说话首窗保底 0.12；停止发 0
播放：mouthValue ≤ 0.08 → 叠加闭嘴层（见 §3.4）
```

### 4.3 autoplay 门控（`[实测]`）
```
浏览器策略：首次用户手势前**禁止出声** ⇒ 未交互 = 动画/字幕照常 + 静音 + 按钮写"🔊 点我开声"
真浏览器实测：手势前 unlocked=false / blockedPlays=2 / plays=0；手势后 unlocked=true / plays=1 /
             currentTime=2.13s / speaking=true / **mouthValue=0.3019（由包络算出）** / errors=[]
```

### 4.4 音色的现状与计划（这是用户最不满的一点）
```
现状：那 12 句是 **Windows SAPI（zh-CN 女声 Huihui）** 合成的**占位音** ✗ —— 又平又怪、和角色完全不搭
计划：用包里的 GPT-SoVITS v3 权重 + `assets/audio/reference` 参考音频，**本机离线批量**生成桐莉栖真音色
     · 换音色只需替换 12 个 wav + 改 `static/kurisu/voice/bank.json`，**播放器一行不改** ✓
     · 硬件：RTX 3060 Laptop **6GB**（0.17.0 α 把 TTS 的 **KV 缓存**显存 561MiB → 48MiB，`[包内自报]`
       且原文强调"特定负载结果、非通用"；**该优化只对 CUDA 生效，CPU/远程配置拿不到**）
     · `[实测]` 本机安装目前**卡在 `jieba-fast` 需要 MSVC 14.0**（无构建工具）→ 绕行：用纯 Python `jieba`
       或直接跑 GPT-SoVITS 官方推理脚本（torch/torchaudio-2.6.0+cu124/transformers/librosa/soundfile 都已在 uv 缓存 ✓）
L2 云端：**Fish Audio `$15 / 百万 UTF-8 字节`**（`s2.1-pro`/`s2-pro`；另有 `s2.1-pro-free` = $0）
     → 一句 20 汉字 ≈ 60 字节 ≈ **$0.0009 ≈ ¥0.0065**；个人站一个月通常**不到 1 元**（代理有磁盘缓存，重复句只算一次）
     → 用户要"就是那个声音" ⇒ 用同一桐莉栖音色（引用社区模型 或 用参考音频做专属音色）
     · 授权：素材包写明"非商业技术学习/研究/演示"⇒ 个人站可行 ✓，禁止付费分发/商业推广 ✓
```

---

## 5. 服务器配置（全部说清）

### 5.1 srv1（阿里云）— 检测与公开 API
```
规格：Aliyun Linux 3 ｜ 2 vCPU ｜ 1870 MB ｜ **按流量计费 ¥0.800/GB** ｜ 峰值带宽 3 Mbps
职责：SecAgent 检测/分析栈 + 公开只读 API `/api/public/*`
      （ask, kb, overview, alerts, latest, honeypot, audit, geo, webstats, stories, tts[503 关闭态]）
隧道：cloudflared `secagent` → `demo.xiaokeqing.cn`（Proxied，橙云）—— **备用/演示用，不动它**
`[实测]` srv1 → Cloudflare 上行 **2.9 MB/s**（服务器侧不是瓶颈）
```

### 5.2 srv2（腾讯云）— 蜜罐检测 + 博客静态托管（**本次新增的角色**）
```
规格：4 vCPU ｜ 3719 MB ｜ **300 GB/月流量包**（2026-11-11 重置）｜ 公网 IP 43.143.114.79（EIP 1:1 NAT 到私网 10.0.0.10）
职责（原）：**7 个容器** —— cowrie / dionaea / secagent-decoy / suricata / wazuh.dashboard /
          wazuh.indexer / wazuh.manager；蜜罐网段 `cowrie_honeypot 172.19.0.0/16`
职责（新增）：**博客整站 + 角色素材的静态托管**
  · 宿主 nginx 1.18.0：`10.0.0.10:80` + `10.0.0.10:443`（**公网面**，只读静态、只 GET/HEAD、限速 30r/s burst 60、
    限连接 24/IP、无动态功能）+ `127.0.0.1:18080`（隧道回源口）
    ⚠️ **不能绑 0.0.0.0:443**：`127.0.0.1:443` 被 `wazuh.dashboard` 的 docker-proxy 占用 → 会 EADDRINUSE；
       绑 EIP 映射到的 `10.0.0.10:443` 才能拿到真 443 且**不碰 Wazuh** ✓（非 root 绑 <1024 需 `AmbientCapabilities=CAP_NET_BIND_SERVICE`）
  · systemd `secagent-static.service`：**专用低权账号 `xksite`**（uid 997，no-login/无 home）、
    `ReadOnlyPaths=/opt/secagent/static /opt/secagent/releases`、`CPUQuota=25%`、`MemoryMax=128M`、`TasksMax=64`
  · 发布布局：`/opt/secagent/releases/site-<时间戳>` + **符号链接原子切换**（失败自动回滚、保留上一版）
  · 证书：**Let's Encrypt 4-SAN**（`xiaokeqing.cn` / `www` / `direct` / `static`），到期 2027-01-12，
    `certbot.timer` 自动续期 + deploy hook 自动同步证书并 reload ✓
  · 隧道：cloudflared `secagent-static` → `static.xiaokeqing.cn`（Proxied，**保留为备用路径** ✓）
  · 防火墙顺序 `[实测]`：`DOCKER-USER` = ESTABLISHED → 127.0.0.11 DNS → **DROP** → 端口 ACCEPT（**放行 80/443 前后逐行 diff 一致** ✓）；
    ufw 放行 80/443；腾讯云安全组入站放行 `TCP 80/443`
  · 隔离回归 `[实测]`：蜜罐网段对外 TCP 全部被 DROP（9 个端口 SYN=0，**对照组 SYN=3 证明测量有效**）、7 容器全 Up
  · 流量账：静态站 `used=125.2 MB`、红线 **≤150 GB/月**（进日报 + 告警，level=OK）
```

### 5.3 DNS 与 Cloudflare（`xiaokeqing.cn` 区）
```
direct.xiaokeqing.cn  A     43.143.114.79        DNS only（灰云）
xiaokeqing.cn (apex)  A     43.143.114.79        DNS only（灰云）   ← 2026-10-14 21:47~22:0x 从 CF 代理切过来
www.xiaokeqing.cn     A     43.143.114.79        DNS only（灰云）
demo.xiaokeqing.cn    Tunnel secagent            Proxied（橙云，srv1）
static.xiaokeqing.cn  Tunnel secagent-static     Proxied（橙云，srv2，备用路径）
Cache Rule：Hostname = static.xiaokeqing.cn 且 Path 以 /kurisu/ 开头 → Eligible for cache
回滚（原文备份在 docs/ops-博客托管切换与回滚.md）：apex/www → CNAME xiaokeqing.github.io + Proxied（1~5 分钟全球生效）
```

### 5.4 发布链
```
源码仓（GitHub main）→ GitHub Actions（hugo 构建 + 断言 + 发布 gh-pages）✓
但**线上不再由 gh-pages 提供** ⇒ 每次发布还要：
  `scripts/publish-site-to-srv2.ps1`（本机 hugo 构建 → 校验 → 打包）→ `scripts/srv2-site-receive.sh`
  （幂等接收 + 备份上一版 + **原子 rename 切换** + 失败回滚）
三档回滚：① 秒级切回上一版 release ② 5 秒 killswitch off（退回只走隧道）③ 2 分钟 DNS 切回 Cloudflare+Pages
```

### 5.5 实测吞吐（站主机器，2026-10-14 21:43–22:10）
```
直连 srv2 443：**271~338 KB/s**（3 轮都下完 2MB）   ← 现在线路径
GitHub Pages ：9.6~17 KB/s（2MB 30s 下不完）
CF 隧道      ：0~10.7 KB/s（**即使 cf-cache-status: HIT、Age 168 也只有 10 KB/s**）
走不走本机 Clash 代理对"直连 srv2"几乎无差别（Clash 把国内 IP 走 DIRECT）
⇒ 结论：瓶颈是"用户链路 → Cloudflare 边缘"这一段 ⇒ **切直连提速 18~30 倍**（已生效）
   · srv1 → CF 上行 2.9 MB/s（服务器侧无问题）；srv2 本机 loopback 1.47 GB/s
```

---

## 6. 0.17.0 α 素材包：能优化的三件事（含外部评审补的路线）

```
① 新动画：`key_point_to_thinking` = 已有剪辑倒放（逐帧 mean/max diff = 0）⇒ **0 字节** 实现 ✓ 已做
② **40 组视频（真正的优化点）**：
   · 源：80 个 IVF（VP9 profile 0、60fps、高 1028、宽 500~904），**alpha 是独立第二条 VP9 码流**、容器 IVF（浏览器不认 ✗）
   · `[实测]` 便携 ffmpeg remux → **VP9-with-alpha WebM**：alpha 与源 **bit-exact（MAE 0）**；
     Edge headless 里 <video> 画到品红底 canvas → **透明像素占比 38.6%（alpha 真解出）** ✓
   · ❗ **AV1+alpha 在 Chromium 解不出透明（0.0%，已实测否决）** ⇒ 只能 VP9-with-alpha
   · 体积（40 组）：m134 = 3,471,550 B ｜ **h268 = 9,813,430 B** ｜ q382 = 23,149,605 B
     同尺子：h268 比现有 hi 图集省 **14.9×**、比 medium 省 **21.1×**；画质同级（32~34 dB vs 33 dB）而像素 4 倍
   · 几何：新包帧是 0.738×（564/764）**居中裁窄** ⇒ 转码前必须 `pad=764:1028:100:0:black` 补回旧画布
     （播放器/嘴型坐标/落位公式全部零改动；实测 pad 后字节更小）
③ 重新校色：差异仅 0.23~1.08/255（肉眼不可辨）⇒ **不建议为它做全量重生成**（且会引入 33 个几何裁切）
路线（外部评审给的三条，供外部 AI 排序）：
  B3（推荐）每帧横向加倍：左半 RGB + 右半 alpha 灰度 → 不透明 H.264/MP4 → 单 <video> + canvas 两次 drawImage 合成
            ⇒ 全平台含 iOS Safari ✓、保持透明与层序 ✓、单文件同步 ✓、PNG 可全砍、闸门可降到 ≤30MiB
  B1 带 alpha 的 VP9 WebM：Safari 不支持透明 ✗，且必须保留全量 PNG 回退（≈44MB）⇒ 省不动
  B2 预合成到房间背景（不透明 MP4）：兼容性最好但房间烘死、交叉淡入会露接缝 ✗
  `[未验证]` Safari 的 VP9-alpha 支持（只在 Windows Edge 测过）
```

---

## 7. 门禁与纪律（`[约定]`，任何方案都要过）
```
· `scripts/assert-build.sh`：零 0 字节资产、`static/kurisu + static/images/crt ≤ 80 MiB`、
  首屏角色资源 ≤1.5MB、`bg.jpg` SHA256 不变、公开端点白名单、零第三方资源引用…
· `_dev/gate-firstscreen.mjs`：**真浏览器 CDP**，逐页首屏 ≤1,536KB（超预算 exit 1，有反例验证过）
· `_dev/check-ssr-contract.py`：五页 `data-xk-ssr` 与 `#xk-views` 契约
· 站点红线：零第三方请求（资源加载位站外 = 0）｜零造假（数字只来自真实接口，取不到写"读不到"）｜
  CSS 一律加容器前缀（曾因整份搬入 `.view{display:none}` **白屏一次**）｜推前必看本地产物 + 截图
· 资产纪律：单一事实来源（`docs/amadeus-research/data/statemachine.json` → 生成器 → 产物）、
  素材暂存不重复、旧包保留作回滚源
```

---

## 8. 已发生的事故与教训（外部 AI 请避免同类）
```
① 整份搬入 demo 的 CSS → `.view{display:none}` 把全站隐藏（白屏）⇒ 规则：CSS 必须容器前缀化
② manifest 与播放器不同步 → 主页一直转圈（真因是覆盖层没撤；后修）
③ 我擅自把垫板 382KB→87KB（降质），用户明确反对 ⇒ 已换回原图，改用"延后 3 秒加载"保首屏预算
④ 我在 srv2 上与另一条线**同时改 nginx.conf**，导致配置被覆盖 + 约 30 秒 502 ⇒ 规则：**一件事一个归属人**
⑤ `nginx -t` 以 root 跑会生成 root 属主日志 → 服务降权后起不来（已写进脚本）
⑥ 本地 DNS 负缓存会让"解析预检"误判（LE 用公共解析不受影响）⇒ 预检改用 8.8.8.8
⑦ 直连 srv2 时**走 Clash 的 TUN/全局模式反而更慢**（出现过 60s 超时）
```

---

## 9. 未决项（请外部 AI 给意见）
```
1) 视频架构：B3 / B2 / B1 选哪个？先做哪两个剪辑的 pilot（建议 idle + speaking_med，前者验高频路径、后者验口型）？
2) 视频化后：PNG 图集是否保留为回退？资产闸门是否**下调到 30MiB** 作为"成功"判据？
3) 旧 82MB 图集仍留在 git 历史 → LFS / history rewrite / 视频走 CDN，怎么选？
4) Safari：VP9-alpha 未测；是否接受"Safari 看 poster 静帧"？
5) 语音：固定台词本机批量（零成本、音色最正）+ 动态句子 Fish（¥几毛/月）这个组合是否最优？
   还有没有"自建常驻服务"的省成本方案（我们没有 GPU 服务器，srv1/srv2 都无显卡 ✗）？
6) 界面口径：用户要求"demo 整份搬"（含它的演示数字）；这与他自己的"数字只来自真实接口"纪律冲突 ✗
   —— 接真接口的时点与范围怎么定？
7) 本地 LLM（用户想学/想自己跑一个）：6GB 显存上限 ≈ 7~8B 的 4bit；两台服务器都无 GPU，
   要云上跑只能按量租 GPU（T4 16GB ≈ ¥3~8/h）。有没有更划算的"个人站本地/半本地 LLM"方案？
```

---

## 10. 参考路径
```
机制研究：docs\amadeus-research\HOW-IT-WORKS.md（1150 行，源码级）
规格与评审：docs\动画与语音实现规格-给外部AI.md ｜ docs\评审-动画与语音实现规格-20261014.md
素材包评估：docs\素材包0.17.0α-优化评估-给外部AI.md ｜ docs\评审-素材包0.17.0α评估-20261014.md
方案：docs\方案v2-按0.17.0α素材包重做资产与渲染.md（含 §9 实测补充）
托管与回滚：docs\ops-博客托管切换与回滚.md ｜ deploy\srv2-site\README.md
清点与视频管线：E:\DeepSeek1\work\_kurisu-017\{INVENTORY.md, VIDEO-OPTIMIZATION.md, video-pipeline\}
```
