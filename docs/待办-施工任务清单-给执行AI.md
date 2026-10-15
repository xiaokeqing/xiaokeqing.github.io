# 施工任务清单 · 给执行 AI（2026-10-15）

> **本文用途**：把"还只在对话里、没进文档"的东西**全部落纸**。执行方按编号取任务，**每条都可独立验收、可独立回滚**。
> **规格与背景**：`docs/接线方案-动画与语音接入六页.md`（施工规格）、`docs/服务器配置-详细版-给外部AI.md`（基础设施）、
> `docs/HANDOVER-接手手册-给下一个AI.md`（入口）。
> **工作量**：T1–T4 约 1 天；T5–T8 约 1–1.5 天；T9–T13 按需。
> **标注**：`[已实测]` 有命令输出/截图支撑 ｜ `[契约]` 不许改 ｜ `[风险]` ｜ `[已纠正]` 我先前写错、以本文为准

---

## 0. 硬前提（先读这 6 条，否则白干）

```
① **未备案 = 不能直连**：腾讯云对未备案域名的 80/443 做阻断 —— 铁证：
   `curl -H 'Host: xiaokeqing.cn' http://43.143.114.79/` → `302 Location: https://dnspod.qcloud.com/static/webblock.html?d=xiaokeqing.cn`
   443 直接 reset（浏览器显示"连接被重置"）✗ `[已实测]`
   ⇒ **今天所有"连接被重置/超时"的真因就是这条**；我先前写的"本地 SNI 过滤"是误判 ✗ `[已纠正]`
② 当前对外路径（2026-10-15 起）：CF 边缘 → **隧道 `secagent-static`（出站）** → srv2 `127.0.0.1:18080` → `/opt/secagent/site`
   · DNS：`xiaokeqing.cn` 与 `www` 已从 A 记录改为 **Tunnel `secagent-static`** ✓（`direct.*` 仍保留 A 43.143.114.79 / DNS only ✓）
   · 四条隧道路由的 Service 均为 `http://127.0.0.1:18080` ✓ `[已实测]`
   · **`static.xiaokeqing.cn` 只服务 `/opt/secagent/static`（248 B 占位页）** ✗ —— 它**不是主站备份**，别拿它当备份用 `[已纠正]`
③ **push ≠ 上线** ✗：push 只更新 gh-pages；上线必须再跑 `scripts/publish-site-to-srv2.ps1`（srv2 原子切换）
④ **六页是生成器产物** ✗：改 `layouts/*` 必须同步 `_dev/gen-demo-pages.py`，否则下次跑生成器会覆盖（`_dev/` 已在 .gitignore 白名单里 ✓）
⑤ 本机直连线上会被①阻断 ✗ ⇒ 线上核验走 `ssh secagent-srv1`（从服务器侧 curl）或 CF 路径
⑥ 三道门禁：`bash scripts/assert-build.sh ./public`（**16 项** `[已实测]`）｜`node _dev/gate-firstscreen.mjs`（6 页 ≤1650KB）｜
   `python _dev/check-ssr-contract.py public`（6/6）
```

---

## 1. T1（P0）手机打开时"她"的动画不放出来

**现象** `[已实测：站长手机]`：整站约 10 秒加载完、能打开，但**进页面后 canvas 不播**（静帧/空）。

**首要怀疑（先证伪）**：原型写死降级阈值 ——
```js
// layouts/partials/xk-demo/shell-script.html:512（五页共用；主页别处也有同款逻辑）
document.getElementById('fallback').style.display = r.height < 260 ? 'grid' : 'none';
```
手机上 CRT 显示高度很可能 <260px ⇒ 直接切 fallback 静帧 ⇒ 动画永不播 ✓（`#fallback` 只在主页存在 ⇒ 五页还会抛 TypeError ✗）

**做法**
```
1. 先确证：手机横屏 / DevTools iPhone 尺寸（1242×2688）复现，检查 #fallback 是否显示、canvas 是否有内容
2. 若是阈值：把判据从"CRT 高度 <260px"改成基于可视宽度/DPR 的合适判据，或"小屏也播动画、只是更小"（只改判据 ✗ 不改视觉）
3. 若确为加载慢：接 T5 的 boot→hi 两段式（opening.boot.webp 281,664 B 先顶上）
4. 同批修五页 TypeError：const fb = document.getElementById('fallback'); if (fb) fb.style.display = ...
```
**验收**：真机竖屏 30 秒内画布出现 ≥2 种不同帧（截图/录屏）｜五页控制台 0 报错｜三道门禁绿｜非角色区像素差 0
**工时/风险**：1~2h ｜ 低

---

## 2. T2（P0）文档修正：7 处，逐条给出"改成什么"

> 这些都是**我写错或漏写**的地方 ✗（其中 6 处由接手方 AI 实测发现、我已复现确认 ✓）。执行方改完请把改动贴回来。

| # | 文件 | 原文/问题 | 改成 |
|---|---|---|---|
| 2.1 | `docs/接线方案-动画与语音接入六页.md` §3.1 | 写 `"nodes": { "<clipName>": {...} }`（对象）、节点有 `geometry`、边只有 `{from,to,prob}` | **nodes 是数组**（38 元素，元素含 `id`（如 `_8ms718k`）+ `clip`（如 `idle`））；节点真实字段：`atlas_source/clip/fps/frameIntervalMs/frame_size/frames/has_mouth_profile/hi/id/incoming_prob_positive/is_root/loopMode/medium/mouthPatch/opaque_bbox/phase/tier`（**无 geometry**）；几何在 `frame_size:[764,1028]` + `medium.pages[]`/`hi.pages[]`（含 url/file/tile_w/h/cols/rows/frames/first_frame/last_frame/pixels/bytes）；边是 `{from, from_id, prob, to, to_id}`（**节点 id ≠ 剪辑名，缺 from_id/to_id 无法跳转**） |
| 2.2 | 同上 §3.1 | 写"12 个剪辑是 once_then_hold" | **13 个**（`loop_mode_counts = {loop: 27, once_then_hold: 13}` `[已实测]`） |
| 2.3 | 同上 §3.1（漏写） | 未提顶层两个字段 | 补：`host_triggered_entries`（**8 个剪辑名**）与 `clips_not_in_graph: ["sad","smile"]`；并注明 `prob=0` 边目标实际 **9 个** ⇒ 清单缺 `thinking_trans`（见 T6） |
| 2.4 | 同上 §1 验收②/§4.3 | 写"纯概率游走只覆盖 9/38" | **10/38**（idle 家族 9 + `trans_standby`）`[已实测]`；反例判据同步改为 10/38 |
| 2.5 | 同上 §6 首屏预算 | 写"接线后首屏 ≤700KB"，未算 opening | 补：**首屏大头是 `opening.hi.webp`（1,004 KB，占当前 1569KB 的 65%）**，视频接线对首屏**零帮助** ✗；要降必须做 T5 的 boot→hi |
| 2.6 | 同上 §10 PR-3 | 写"替换原型那段 4 剪辑循环（保留它作为最终降级路径）" | 改写：原型 4 剪辑 = `opening/idle/speaking/thinking`，其中**只有 `idle` 在状态机且有视频** ✗；`opening/speaking/thinking` **既不在状态机、也无视频** ⇒ **不能整体替换**；必须先给出 `opening` 的处置（保留原型 opening 作为开场 ✓ 或另出视频） |
| 2.7 | `docs/服务器配置-详细版-给外部AI.md` §3.5 | 写"`/opt/secagent/static/` = 静态根（当前内容 = 站点产物）" | 改成：**`/opt/secagent/site` = 主站真身**（软链 → `releases/site-<时间戳>`，server_name = xiaokeqing.cn/www/direct）；**`/opt/secagent/static` = `static.xiaokeqing.cn` 的占位根（248 B），与主站无关** ✗；并补一句：`systemctl is-active nginx` 在 srv2 返回 `inactive` **是设计如此**（nginx 是 `secagent-static.service` 的主进程、以 `xksite` 身份跑）✗ 别误判为故障 |
| 2.8 | 同 §4 / `docs/ops-博客托管切换与回滚.md` / `docs/HANDOVER-§7§12` | 缺"备案=硬前提" | 三处都补：**未备案 ⇒ 境内 80/443 被阻断（含 §0① 的 302 铁证命令）**；**现行方案 = 走 CF 隧道**；备案完成后再把 apex 切回 A 记录（271~338 KB/s ✓） |

**验收**：改完 `grep` 一遍确保旧说法（`9/38`、`12 个 once_then_hold`、`geometry`、"本地 SNI 过滤"、"/opt/secagent/static = 站点产物"）在仓库里**不再出现** ✗
**工时/风险**：30~40min ｜ 极低（纯文档）

---

## 3. T3（P1）"会对话"接线 —— 性价比最高

**事实** `[已实测]`：后端**已经跑在生产上**
```
POST https://demo.xiaokeqing.cn/api/public/ask  →  200 ✓
 返回：answer / state / stateLabel / generated / citations[] / quota{pool:"public-demo",limit:30,used,remaining} /
       note / retrievalNote / ttsTextHash / outputFindings / maxQuestionChars:600 / deadlineMs:20000
 口径：publicDemo=true、toolExecutionAllowed=false、fail-closed（检索不到就说"没有生成结论"，不编造）
 **CORS 已验证**：带 `Origin: https://xiaokeqing.cn` → 响应头 `access-control-allow-origin: https://xiaokeqing.cn` ✓（无跨域障碍 ✓）
 小 bug：`GET /api/public/ask` 返回 500（应 405）
```
**现成可复用**：`static/js/app.js` L1607-1914（发包+超时、契约注释、引用卡片渲染、输入框行为、预设问题、"不许 SSE/WebSocket"纪律）
**现状**：六页是 demo 整份搬、**不加载 app.js** ✗；`/ai/` 的 `askDemo()` 是假的（等 900ms 塞固定文案、不发请求 ✗ `[已实测]`）

**做法**
```
1. 把 /ai/ 页的 askDemo() 改为真调用（API base 已在 <meta name="wb-api"> 里 ✓）
2. 渲染 answer + citations[] + state/stateLabel + quota（照 app.js 的渲染逻辑，别引入新框架 ✗）
3. 用响应状态驱动她：THINKING → 回答 → IDLE（demo 已有 emo / mode / speak() 钩子 ✓）
4. 失败/无检索：显示"读不到 / 没有依据"，**前端不兜底造假** ✗（后端已 fail-closed）
5. 可选：把 answer 文本喂 `/api/public/tts`（响应里的 `ttsTextHash` 就是为这条链路设计的 ✓）—— 需在 T4 之后
```
**验收**：真实提问打通（截图为证）｜引用卡片与 quota 正确显示｜失败时显示"读不到"且控制台 0 报错｜首屏字节不超标
**回滚**：把 `askDemo()` 换回假实现（一行）✓ ｜ **工时/风险**：1~2h ｜ 低
**纪律**：不许 SSE/WebSocket ✗；不许前端编造答案 ✗

---

## 4. T4（P1）语音 L1 接线（她会开口）

**素材已就绪** `[已实测]`
```
E:\DeepSeek1\work\_tts-trial\sample8\dist\*.m4a|webm（8 句 / 529,864 B，覆盖 7 个 trigger，含 shy/surprised）
全量 60 句在 out-ja\dist\（3.13 MiB，超 3 MiB 预算 4.5% ✗ → 要全量就按 m4a 40k / webm 32k 压到 ≈2.6 MiB）
bank.json：out-ja\bank_sample8.json（含 ja/zh/envelope/durationMs/sha256/source ✓）
管线与复现命令：仓库 `scripts/voice/README.md`（含 7 条坑 ✓）
线上现状：那 12 句是 **Windows SAPI 占位音** ✗
```
**做法**
```
1. 只上 8~12 句，**按 7 个分组各取 1~2 条** ✗ 别随机取（否则触发规则形同虚设）
2. 放进 static/kurisu/voice/* + bank.json（契约兼容 ⇒ 播放器一行不用改 ✓）
3. 页面接线：autoplay 门控（手势前 0 播放、按钮"🔊 点我开声"）+ 字幕用 zh（写进原型已有字幕元素，不新增元素 ✗）
   + 包络（10ms 窗）暴露 mouthValue 给 T8；失败只落字幕 ✓
4. 语音目录预算 ≤3 MiB，首屏只预载 greeting 一句，其余 <audio preload="none">
```
**验收**：手势前 plays=0 / 手势后 plays≥1、字幕与音频对齐 <100ms｜`static/kurisu/voice/` ≤3MiB｜首屏不超标
**回滚**：删 manifest 的 voice 段（页面判定无 bank 就不初始化 ✓）｜ **工时/风险**：1~2h ｜ 低

---

## 5. T5（P1）界面清理 + 首屏 boot→hi（零风险、用户可见）

```
T5.1（A1）五页 TypeError：shell-script.html:512 → `const fb = document.getElementById('fallback'); if (fb) …`（1 行）
T5.2（A2）门禁补硬断言：把"控制台错误"从"只报不拦"改成**有错即 exit 1**（需给已知无害告警留白名单）；
          同时给首屏门禁补"状态机 reason 统计"断言（host:voice/emotion/idle 各 ≥1）
T5.3（A3）/about/ 空白那屏：属实（原型里 `v-about` 只有 87 字节的 `</div>` ✗ 当前产物正文 0 字）；
          按站点口径自己写一屏（真实数据，取不到写"读不到" ✗ 不许编）
T5.4（A4）主页静态残留假数字：`layouts/index.html:126` → `24h 告警 1,284 · 拦截 96` 改为占位 `—`，由 JS 填真值
T5.5（A5）/posts/ 卡片改成真链接（进具体文章）——注意单篇文章页仍是旧版式 ✓
T5.6（D1）★ boot→hi 两段式：原型脚本直接加载 hi ✗，仓库里现成的 boot 档完全没用（引用次数 0 `[已实测]`）：
          opening.boot.webp **281,664 B**（hi 1,004 KB）｜idle.boot 531,854 ｜speaking.boot 444,430 ｜thinking.boot 475,680
          做法：先画 boot 顶上 → hi 到位后替换 ⇒ 主页首屏 1569KB → **约 823KB（−47%）**，**最终画质不变** ✓
```
**验收**：五页 0 报错｜主页首屏 ≤900KB（门禁②）｜boot→hi 替换后与 hi 直出**同帧对拍像素差 0**｜其余页面字节不退化
**回滚**：boot→hi 是一段加载逻辑，删除即回到 hi 直出 ✓ ｜ **工时/风险**：T5.6 约 1h（要动 demo 内联脚本 ⇒ 属口径问题，见 §12 待拍板）；其余各 10~20min

---

## 6. T6（P2）状态机生成器：补 `host_triggered_entries` 的 `thinking_trans`

**实测** `[已实测]`：`prob=0` 的边目标是 **9 个**剪辑：
`angry_trans · closed_eye_trans · sad_trans · shy_trans · speaking_short · speaking_trans · surprise_trans · **thinking_trans** · trans_smile`
但顶层 `host_triggered_entries` **只有 8 个**，**缺 `thinking_trans`** ✗（它的 prob=0 入边来自 `idle_str_wind`）
⇒ 若执行方照这份清单实现宿主触发，`thinking_trans` **永远不会被触发**，状态机走进 `idle_str_wind` 后出不来（观感=发呆 ✗）

**做法**：修 `_dev/build_statemachine_manifest.py` 的清单生成（按"所有 prob=0 边的目标剪辑"取，别按别的口径 ✗），重新生成
`static/kurisu/statemachine.json` 与 `docs/amadeus-research/data/statemachine.json`（源），并核对 manifest/预载清单不受影响
**验收**：重新生成后 `host_triggered_entries` = **9 个**且包含 `thinking_trans`；38/88 不变；门禁绿
**工时/风险**：20~30min ｜ 低

---

## 7. T7（P2）视频接线（9.54 MB 替代 71 MB）

```
素材（已产出、自检 40/40 过）：E:\DeepSeek1\work\_kurisu-017\video-assets\video\<clip>.webm ×40（8,763,277 B）
                              + <clip>.poster.webp ×40（779,892 B）
路线：**B 路线（透明 VP9+alpha）** —— alpha MAE 0.189、体积小 23%、播放端直接 drawImage ✓（B3 只在颜色 PSNR 占优，且每帧多一次全帧合成 ✗）
做法：canvas 从"画 PNG 图集"改为"画 <video>"；离屏 <video>（不进 DOM ✗）；同时存活 ≤4 枚 + LRU；
      硬切用两枚 video 交替；缺视频/解码失败 → 图集 → poster；首帧先画 poster（不留空框 ✗）；
      **预载纪律**：只预载 root→idle→出边 top-2；首次手势前不预载视频 ✗；saveData/reduced-motion 只用 poster
坑（已踩）：只能 VP9+alpha（AV1+alpha Chromium 解不出透明 ✗）；WebM 无 faststart 但索引天生前置 ✓；
      色彩标记必须输入端也写；`clip.json` 的 `layout` 有 2 组写错（1027 vs 1028）⇒ 一律以实际码流尺寸为准；
      转码前必须 pad=764:1028:100:0:black，否则角色横向跳 9.5% ✗
```
**验收**：30 秒 ≥8 个不同帧指纹｜四角品红采样证明 alpha（已有方法 ✓）｜首屏仍 ≤1650KB｜与图集同帧 NCC ≥0.99
**回滚**：`data-xk-kurisu-mode="pixel"` 一行 ✓ ｜ **工时/风险**：2~3h ｜ 中

---

## 8. T8（P2）状态机 + 口型接线（最难）

```
状态机：38 节点/88 边；root=idle；出边概率**归一化后**掷骰子；`prob=0` 的 9 条=宿主触发入口（见 T6）；
      13 个 once_then_hold 播完停末帧；支持 ?seed=<n> 与 ?replay=<base64>；每次切换记 reason（auto:<edge> / host:<kind>）
宿主触发事件表：greeting（首访/回访分流）/ page_intro（每页一条，同页 10 分钟去重）/ status（**真实文本变化时**，20s 防抖）/
      event（新告警/故事线，按事件 id 去重，可打断 status）/ idle_banter（无操作 >90s）/ fallback（接口取不到）/
      emotion（点击她 / 严重度变化）/ cadence（>25s 无宿主事件兜底）
口型：mouthValue = clamp(envelope.values[floor(t/10ms)] × 3.75, 0, 1)；≤0.08 叠闭嘴层
      12 个剪辑用小补丁、4 个用原方案（截块+椭圆遮罩，按 mouthPatch.preferredVariant）；
      逐帧用 anchor_track 定位（**不许写死坐标** ✗）；说话段不叠（帧里自带嘴在动 ✗）
```
**验收**：30 秒内 reason 统计出现 host:voice / host:emotion / host:idle 各 ≥1（**反例：只有 10/38 的 idle 家族 = 接线失败** ✗）｜
静音/说话两张嘴部对照图｜页面隐藏 60s 后切回不快进（清零累加器 ✓）
**工时/风险**：状态机 3~5h（高）；口型 1~2h（中）

---

## 9. T9（P2）资产瘦身（**有前提，别乱删** ✗）

```
实测：static/kurisu 共 82,400,264 B（78.58 MiB）；六页实际只引用 23 个文件 ≈ 7,325 KB（7.15 MiB）
      ⇒ 约 68.8 MiB"部署了但拉不到"（medium/ 48.15 MiB + hi/ 19.62 MiB + voice/ + mouth/ + statemachine.json）
原因：六页不加载 kurisu-player ✗；状态机默认关（需挂载点带 data-xk-kurisu-sm="on"，产物里没有 ✗）
⚠️ **但文章页加载 kurisu-player（实测 1 处 + xk-kurisu 12 处）**，播放器**运行时**会取 `medium/*.atlas.webp`
   ⇒ **不能**先把 medium/ 移出 git ✗（会让文章页角色失效/降质）
做法（顺序不能反）：① 先接线（T7/T8）让视频替代 medium → ② 观察一段时间 → ③ 再删 medium 与 hi（保留 release 里的回退源 ✓）
门禁口径建议拆两个指标（现在的 ⑨ 是"仓库占用"口径，与"线上载荷"差约 10 倍 ✗）：
      repo ≤ N MiB（防 git 膨胀）｜ per-page payload ≤ M MiB（用户体感）｜ first-screen ≤ K MiB（已有 ✓）
发布包：现在每次 tar 81.86 MB（含未引用的 68.8 MiB）✗ → 瘦身后可降到 ~15 MB
```
**验收**：删前后文章页 + 六页的角色都正常（截图对拍）｜`assert-build.sh` 全绿（含我调整后的新口径）
**工时/风险**：瘦身 1h（但要等 T7/T8 完成）｜ 中（顺序错了会伤文章页）

---

## 10. T10（P3）遗留文件与双轨架构

```
E2 双轨：站点原 SPA（app.js + #xk-views + data-xk-ssr）与 demo 内联脚本（六页各自完整 HTML、不走 baseof.html）
        + baseof.html 仍在给文章页用、且加载 kurisu-player ⇒ **接线时先确认改动落在哪一轨** ✗
E3 遗留：static/preview-shell.html（71 KB）、layouts/partials/xk-views/v-home.html、assets/css/xk-app.css 等
        （上一版外壳，当前口径下不挂载）⇒ 确认后**归档或删除**
E4 文档漂移：`docs/交接-六页整份搬demo-20261014.md:114` 仍写旧断言 `.navpill`（导航已改成 dock ✗）
           · 注意：接手方 AI 报告"assert 实测 15 项"与本节不符 —— 我**连跑三次都是 16 项** `[已实测]`，
             该脚本含条件分支（如 `if [ -f "$PUB/CNAME" ]`）⇒ 不同环境计数可能差 1 ✓ **不是文档漂移** ✗
```
**验收**：仓库无"当前口径下不挂载"的死文件（或明确标注归档）｜文档旧说法清零
**工时/风险**：30min ｜ 低

---

## 11. T11（P3）服务器与运维（补充项）

```
· 备案：**这是唯一能回到直连速度的路**（271~338 KB/s）⇒ 建议尽快办；办下来后 apex/www 改回 A 43.143.114.79（灰云）
· 证书续期告警（到期前 21/7/1 天三级）+ 续期后自动访问一次 https 校验 ✗ 现在没有
· srv2 站点可用性**外部探测**（srv2 是整站单点 ✗；现在靠 CF 隧道顶着，路径已变 ⇒ 探测目标应为
  `https://xiaokeqing.cn/`（经 CF）**和** srv1 侧直连 `direct.xiaokeqing.cn`（若开放）两条各测）
· `static.xiaokeqing.cn` 只服务 248 B 占位页 ✗ ⇒ 文档与监控都不要再把它当"主站备份路径"（已在 T2.8/T0② 写明）
· 备份范围建议：/etc/nginx、/etc/systemd/system/secagent-static.service、/etc/letsencrypt、/opt/secagent/scripts + **恢复演练**
· 媒体迁 COS/OSS + CDN（流量/海外访客变大时）；"同域 CNAME 到 CDN"是否算违反零第三方请求 → 见 §12 待拍板
```
**工时/风险**：按项取（每项 20min~1h）

---

## 12. 需要站长/评审拍板的 7 件事（执行前先问）

```
① 先做哪条？（我建议：T1 → T5.2/T5.1 → T3 → T4 → T5.6 → T7 → T6 → T8）
② boot→hi（T5.6）要动 demo 内联脚本 ⇒ 允许吗？（视觉不变、首屏 −47% ✓ 我认为不算降质）
③ 语音先上 8~12 句（按 7 分组各 1~2 条）还是全量 60 句（需压码率到 ≈2.6 MiB）？
④ /about/ 那屏的内容谁写、写什么口径？（必须真实数据、取不到写"读不到" ✗）
⑤ 资产瘦身：是否接受"先接线、再删 medium/hi"的顺序（不能反过来 ✗）
⑥ 媒体走 CDN 的"同域"边界（CNAME 到 CDN 是否算第三方请求）——影响 T11 取舍
⑦ Fish Audio Key 给不给（给了 L2 才能把回答说出来；代理已实现三道闸 + 磁盘缓存 + kill switch，现 503 关闭态）
```

---

## 13. 我与接手方 AI 的核验结论对照（省得重复查）

```
✅ 接手方 AI（E:\DeepSeek1\123\接手方案与优化点汇总-20261015.md）**实测正确的**：
   F1 契约 6 处、F2 纯概率 10/38、F2② thinking_trans 缺失、F3 opening/speaking/thinking 无视频且不在状态机、
   F4 /opt/secagent/static 与 /site 的区别、A1 报错行、B1 资产对账（82.4MB vs 引用 7.15MiB）、
   C2 后端 ask 200 + 返回字段 + GET 应 405、C4 tts 503、D1 boot 档存在且未被引用、E1 生成器、E2 双轨、E3 遗留
✗ 它**唯一写错**的：E4-①「assert 实测 15 项」—— 我连跑三次 **16 项** ✓（脚本有条件分支，环境差异可解释）
⚠️ 它 **B1 路线二**（把 medium/hi 移出 git）需加限制 ⇒ 见 T9（文章页运行时会取 medium ✗）
✅ 我已实测确认：**CORS 允许 https://xiaokeqing.cn**（`access-control-allow-origin` 回显 ✓）⇒ T3 无跨域障碍
✅ 我已实测确认：**未备案阻断**（302 → dnspod.qcloud.com/static/webblock.html）⇒ 本文 §0①
```

---

## 14. 公共纪律（每条任务都适用）

```
· 只改自己的文件；`git add` 只加自己的路径（禁入 public/、_shots/、大文件）✗
· 改完必跑三道门禁；**push ≠ 上线** ✗（要跑 publish-site-to-srv2.ps1）
· 改 `layouts/*` 必同步 `_dev/gen-demo-pages.py` ✗
· 不许停留假数字/演示数据 ✗（取不到写"读不到"）；不许前端兜底造假 ✗
· 不许在用户手势前播放音频 ✗；不许给页面加第三方请求 ✗
· 本机直连线上会被未备案阻断 ✗ ⇒ 核验走 srv1 或 CF
· 一条任务一个归属人 ✗（同一文件别两个人同时改）
```

---

## 15. 状态板（2026-10-15 复核，接手批已入库）

| 任务 | 状态 | 证据 / 说明 |
|---|---|---|
| T1 手机动画不放 | ✅ 已修并上线（229e0d7→site-20261015-181533） | 站点现在约 1 秒打开、素材 548KB/s ✓；请手机复测：出来了=当时素材没到；不动=`r.height<260` 降级阈值成立 ✗ |
| T2 我文档的 7 处错误 | ✅ 已修（5c443dc） | 见本文 §2 逐条"改成什么" |
| T3 会对话接线 | ✅ 代码完成 | `/ai/` 已真调 `POST /api/public/ask`；跨域已验证 ✓；**未发布** ✗ |
| T4 语音 L1 | 🟡 一半 | 播放链已接（手势门控 ✓）；**只剩换日语素材**（`sample8/dist/*.m4a|webm` + bank.json → `static/kurisu/voice/`，契约兼容 ✓）|
| T5.1 五页 TypeError | ✅ | `shell-script.html:692 const fb=...` 空值保护 ✓，六页 console=0 ✓ |
| T5.2 门禁硬断言 | ✅ 有错即 exit 1（8f33aa6，故障注入实测） | 控制台错误仍未 exit 1 |
| T5.3 /about/ 空白 | ✅ 四张真实卡，正文 0→591（8f33aa6） | 产物正文仍 0 字 |
| T5.4 主页残留 `1,284` | ✅ 改占位+api-bind 填真值（6b35e89） | 静态里改占位，JS 填真值 |
| T5.5 /posts/ 卡片非链接 | ✅ Hugo range 8 篇真文章（6b35e89） | |
| T5.6 boot→hi | ✅ 已实施（d8e03e6） | 省 47%~70%、视觉不变 ✓ |
| T6 生成器 thinking_trans | ✅ | 已改"从 prob=0 边派生" ⇒ 9 个含 thinking_trans ✓，38/88 不变 ✓ |
| T7 视频接线 | ❌ | 留到 T8 一起（对 opening/speaking 零帮助 ✗）|
| T8 状态机 + 口型 | ❌ | 最难；"活起来"的关键 |
| T9 资产瘦身 | ❌ | **顺序不能反**：先接线再删 medium/hi ✗ |
| T10 遗留文件 / 双轨 | ❌ | preview-shell.html 等归档或删 |
| T11 服务器与运维 | ❌ | 备案是回直连的唯一路 ✓ |
| **T12 删背景选择器 + boot→hi** | ✅ **已完成**（d8e03e6） | 用户投诉"加载太卡"✗：① 删右下角「背景/配色」面板 + 配套 CSS/JS/生成器片段（实测首屏只载当前 1 张 room_empty 84KB ⇒ 内容页 267→约190KB）② **并做 T5.6**（主页 −47%、ai 页 −70%，视觉不变 ✓）｜**T7 不并做** ✗ |

**接手批额外做的（方向对 ✓）**：表情 5→8 套（改用会动的 `avatar/*.idle/speaking.webp`）｜主页加"表情模式" XK_ACT + 表情条 ｜ 语音播放时不覆盖语音字幕

**✅ 2026-10-15 执行AI批**：T1/T5.1~T5.6/T12/T2 全部完成并已发布上线（HEAD 8f33aa6 → site-20261015-181533，home 首屏 840KB）；交接见 `交接-执行AI批-20261015.md`。

**⚠️ 已提交未发布**（历史记录）：接手批只在仓库（HEAD `0112ce2`），线上仍是 `site-20261014-235208` ✗ —— 不发布的原因：一发布就会播**旧 SAPI 占位音** ✗；建议先做 T4 换日语素材，再一起 `scripts/publish-site-to-srv2.ps1` ✓
---

## 16. 执行批完成情况（2026-10-15，源：`docs/交接-执行AI批-20261015.md`）

**基线**：HEAD `8f33aa6`（已 push）｜线上 srv2 `/opt/secagent/releases/site-20261015-181533`（上一版 `site-20261015-112007` 保留 ⇒ 秒级回滚）｜工作区干净

**门禁**：assert-build **15/15**（注意：计数含条件分支，我这边跑出 16 项 —— 两者都算绿 ✓）｜firstscreen **6/6**（home **840KB** / 预算 1650KB）｜ssr-contract 6/6 ｜ **控制台错误已改成 exit 1**（T5.2）

### 16.1 状态板覆盖（§15 的更新，直接以本节为准）

| 任务 | 状态 | 关键证据 |
|---|---|---|
| T1 手机动画 | ✅ 已上线 | iPhone 横屏 CRT 高 224px < 原型死阈值 260px ⇒ 整屏 fallback 盖住动画；判据改为 `r.height<260 && !matchMedia("(pointer:coarse)").matches` ⇒ 触屏一律播动画；冻帧对拍像素差 0 |
| T2 文档 7 处 | ✅ | statemachine 契约（nodes 数组/无 geometry/from_id-to_id）· 13 个 once_then_hold · 10/38 · opening 占首屏 65% · PR-3 不能整体替换 · `/opt/secagent/site` 才是主站真身 · 备案硬前提 |
| T3 会对话 | ✅（早前） | /ai/ 真调 `POST /api/public/ask` |
| T4 语音 L1 | ✅ 已上线（核实） | 12 句 / 7 分组 / 717KB；CDP 实测手势前 plays=0、手势后 plays=1、字幕逐字对齐 |
| T5.1 TypeError | ✅（早前） | #fallback/#bootveil 存在性判断 + opening 门控 |
| T5.2 门禁硬断言 | ✅ | console error/未捕获异常即 FAIL + exit 1；**故障注入实测拦获** |
| T5.3 /about/ | ✅ | 87 字节残 div → 四张真实内容卡，正文 0→591 字 |
| T5.4 假数字 | ✅ | 1,284/96/37 改 `—` 占位，api-bind 填真值 |
| T5.5 /posts/ 链接 | ✅ | 死笔记 → Hugo range 渲染 8 篇真文章链接（shell-views 的 dict 需带 `"page" .`）|
| T5.6 boot→hi | ✅ | 四个剪辑各加 boot 档（前 24 帧、281–532KB）⇒ 主页 **1569→840KB（−47%）**、内容页 267→185KB、/ai/ 1637→1555KB；最终画质不变（14s 时 demoClip=idle、画布 52,032 像素与旧版一致）|
| T6 生成器 | ✅（早前） | prob=0 边派生 ⇒ host_triggered_entries 9 个 |
| T12 删背景选择器 | ✅ | 面板+压暗+配色/手机切换+背景图全删；body 静态 `data-skin="warm" data-phone="v1"` |
| L1 镜头语言 | ✅ 新增 | CRT 通电（亮线→竖向展开→抖动→过冲白光→稳定）+ opening→idle 推拉 0.9s（末段交叉融化）；仅主页，RM 用户走静态 idle |
| T7 视频接线 | ❌ 未做 | 2–3h |
| T8 状态机+口型 | ❌ 未做 | 3–5h，最难 |
| T9 资产瘦身 | ❌ 未做 | **必须先接线再删 medium/hi** ✗ |
| T10 遗留文件/双轨 | ❌ 未做 | |
| T11 服务器/备案 | ❌ 未做 | 备案=回直连唯一路 |

### 16.2 必须知道的 6 条机制（细节见 `docs/交接-执行AI批-20261015.md` §3）

```
① 双轨 + 生成器：六页由 _dev/gen-demo-pages.py 从 docs/demo-*.html 重新生成 —— 改 layouts/* 必须同步生成器并重跑；
   生成器锚点必须匹配 **demo 原文**（不是产物文本）；补丁有先后依赖（L1/CRT 补丁要在 T5.6 引用的代码之后）
② 动画链：CLIPS 四剪辑逐帧；xkClipIm(name) 先 **peek** hi 缓存（绝不能 img() 创建 —— 创建即发请求 ✗）、
   未就绪兜底 boot 档、hi 到位按同一帧号无缝接力；boot 期间 opening 走 fi % 24 循环等 hi；门禁 home 检查点已改 9s
③ 语音链：bank.json 12 句日语 + 中字幕；手势门控（首次 pointerdown/keydown 解锁）；XKV 状态可观测
④ 发布链：push ≠ 上线 ✗。`scripts/publish-site-to-srv2.ps1 -FromRef HEAD`；
   **scp 报 `pipe: Unknown error` 是 Windows OpenSSH 老毛病** ⇒ 手动通道：`scp -O` 传 tar → install 接收脚本 →
   `sudo -n bash /opt/secagent/scripts/srv2-site-receive.sh <tar>`（原子切换 + 失败自动回滚）
⑤ 门禁方法论：改完必跑三件套；对"拦截型"逻辑必须做**故障注入**验证真能拦 ✓
⑥ 回滚：把 /opt/secagent/site 软链指回上一个 release 目录即可；发布脚本保留最近 4 版
```

### 16.3 本批踩过并拦住的 5 个真 bug（教训，别重犯）

| # | 现象 | 根因 | 教训 |
|---|---|---|---|
| 1 | L1 生成代码缺 xkDrawTrans | 生成器编辑手滑把旧补丁顶掉 | 每次生成后 grep 函数存在性 |
| 2 | 生成器补丁"对不上 0 次" | 锚点写成产物里才有的行 | 锚点永远匹配 demo 原文 |
| 3 | 开场卡 boot 档永不落幕 | xkClipIm 先兜底 boot 再 peek hi | peek/兜底顺序；门禁 demoClip 抓到 |
| 4 | 门禁一遇错误就崩 | `pass=false` 赋给 const pass | 故障注入逼出来；pass 计算里 fold |
| 5 | 门禁启动即崩 | Node 侧误用 window | evalJs 里的表达式才在浏览器跑 |

### 16.4 现存未决（**要站长拍板/动手**）

```
① [已由我 5 分钟完成] 状态板更新 ⇒ 见本节 16.1 ✓
② [待拍板] TTS"念回答"(L2) 三选一 —— srv1 上 key/开关/短语表**已配好**（self-check `key=SET phrases=3`），
   但 **api.fish.audio 在境内被 SNI 重置**（TCP 可建、TLS 漏 SNI 即 RST）⇒ UPSTREAM_IO：
     A. CF Worker 中转（需站长在 CF 面板操作；现有 API token 已失效 ✗）
     B. DashScope TTS 进代理（境内实测 0.22s，但要改 Java 代码 + 重建）
     C. 暂缓（预渲染 12 句不受影响 ✓）  回滚 A/C = 删 .env 三行 + compose 五行
③ 下一层：T7 视频 → T8 状态机+口型 → T9 瘦身（先接线 ✗）→ T11 备案运维
④ 远期王牌：**SpriteForge**（Code-Amadeus/Amadeus-SpriteForge 官方资产生成工具，可产新表情动作）
   ｜ **Kurisu GPT-SoVITS v2ProPlus 模型**（可给 12 句 bank 提质，本地合成、不受 fish.audio 阻断影响 ✓）
④ ★安全：**Fish Audio key 曾在聊天里出现** ⇒ 请到 fish.audio 控制台**轮换**，换新后同步 srv1 `.env` 的 `APP_TTS_API_KEY` ✓
```
---

## 17. AI 项目升格任务（T13~T16，详见 `docs/AI项目升级方案-20261015.md`）

| 编号 | 任务 | 工时 | 依赖/插点 | 一句话验收 |
|---|---|---|---|---|
| **T13** | **评测包**（ASR 回译 CER + 问答质量集 ≥30 条含拒答用例 + MOS/ABX 流程 + `scripts/eval/` 可重跑） | 1 天 | **不依赖别的任务，现在就能做 ✓**；产出喂 T16 | 60 句 CER 逐句+均值表 ｜ 质量集得分表 ｜ MOS 结果表 ｜ 脚本可重跑 |
| **T14** | **LLM 决策行为**（告警摘要 → 严格 JSON：情绪/剪辑/台词/urgency/reason；白名单校验防幻觉；缓存；超时回退） | 1~2 天 | **与 T8 状态机+口型接线合并做**（9 个 prob=0 宿主入口就是为它准备的 ✓） | 5 组场景合法输出（附 JSON）｜ 幻觉率 0 ｜ 失败注入可回退 ｜ 5 分钟内同场景缓存命中 |
| **T15** | **语音闭环**（ASR → LLM → TTS + 打断 + 延迟预算） | 2~3 天 | 放 T14 之后；受 ASR 环境影响 ✗ | 端到端录屏（含打断）｜ 延迟分解表（首字 ≤1.5s / 首音 ≤3s）｜ 降级可用 |
| **T16** | **《AI 项目说明书》**（1~2 页：定位/四层架构/技术栈/指标表/成本表/难点解法/可复现/边界与不足） | 半天 | 放 T13 之后（要用它的数字） | 文档可直接用于简历/答辩 ✓ |

**三个缺口（升格的本质）**：① 没有 AI 质量评测 ✗（只有工程指标）② 没有数据闭环 ✗（真攻击日志没系统化成语料+评测集）③ AI 没参与她的行为 ✗（LLM 只管问答，动作还是概率+固定事件）

**四项待拍板**：① 语音评测做不做主观 MOS（需人盲听 20 分钟 ✓）② 她说话只允许预渲染台词 ✗ 还是允许自由文本（花钱 ✓）③ 语音输入做不做（做=最像 AI 项目，但受 ASR 环境影响 ✗）④ 面向"简历/答辩"还是"真给访客用"（前者重报告与演示，后者重稳定与成本 ✓）

**建议顺序**：T13 →（T7 视频 + T8 状态机口型 + T14 决策）→ T15 → T16 → T9 瘦身 → T11 备案运维
---

## 18. 角色能力深化任务（T17~T19，详见 `docs/角色能力深化与双智能体协作方案-20261015.md`）

| 编号 | 任务 | 工时 | 要点 | 验收 |
|---|---|---|---|---|
| **T17** | **声音模型换代 A/B** | 0.5 天 | 先听素材 `F:\7AAA\AI\命运石之门\1\00_all_emotions__order-v2pro_v2proplus_v3.wav`（三代模型×全情绪对比 ✓）；候选 = v3 / v2ProPlus(e80+e12) / e100；同句同情绪三方盲听 | 三代同句 m4a 各 1 个 + 盲听结论 + 选定模型实测（RTF/显存/响度）｜回滚=bank.json 换回旧 12 句 |
| **T18** | **素材产线评估（SpriteForge + Wan）** | 1 天 | 读 SpriteForge 文档与 `discussions/27`；搞清输入要求/输出规格/显存需求/成本；评估"新动作 pilot（2 个）· 半身换装 · 全身/腿部（不建议 ✗）"；**先评估不要先买 GPU** ✗ | 一份评估报告（含 1 个 pilot 可执行步骤、成本区间、一致性验收=必须对齐 764×1028 ✗）+ 明确的做/不做建议 |
| **T19** | **双智能体协作方案** | 1 天 | 落地三层模型（只读 / 决策 / 提议）+ 权限矩阵 + 审计字段；写 `persona.md`（性格/口癖/禁忌/说话风格 → LLM system prompt）；定义 `POST /public/decide`、`/public/propose`（需审批）契约草案；画"谁能调谁"边界图 | 方案文档 + 接口草案 + persona.md（可直接喂 LLM）｜**铁律：她的输出永不进执行链** ✗ |

**另有一个可选活**：`F:\7AAA\AI\命运石之门\1\` 里 40 个 mp4 + 5 个 mov（2.3GB，疑似作者演示录屏）⇒ 逐帧分析产出"**情绪↔动作↔语调对照表**"（约半天 ✓），是 T14 的输入 ✓

**建议顺序**：T13 评测包 →（T7 视频 + T8 状态机口型 + **T14 决策**）→ **T17 声音换代**（可并行）→ **T18 产线评估** → T15 语音闭环 → **T19 双智能体** → T16 项目说明书 → T9 瘦身 → T11 备案运维
> **口径修正（2026-10-15）**：**T18 的目标是"建设能力"而不是"产某个素材"** ✗ ——
> 即打通三段：**能生成（SpriteForge/ComfyUI + 云 GPU）→ 能对齐+能筛（`tools/asset-align.py`、
> `tools/asset-consistency.py` + 角色定妆集）→ 能入库（生成器支持"新剪辑登记表" + 一页 SOP）** ✓
> 验收看"能力"：SOP 跑通一次、脚本可重跑、一致性阈值是**互测标定**出来的、附每动作成本表 ✓
> 详见 `docs/角色能力深化与双智能体协作方案-20261015.md` §六（含能力分级表：新动作/半身换装 ✅ 可达；
> 全身与发型 🟡 困难；整段行走 ❌ 不建议）✓
---

## 19. 后端展示落地任务（T20~T22）+ 问题单（源：窗口 F，2026-10-15）

> F 的完整规划见 `docs/后端功能与博客展示规划-20261015.md`（49.8KB）；状态见 `docs/状态-F-后端功能展示.md` ✓

| 编号 | 任务 | 归谁 | 工时 | 要点 |
|---|---|---|---|---|
| **T20** | **处置成果「封禁榜」上屏** | C 落地 + G 出 UI | 2~3h | 放 `/alerts/`「数据统计」pane 的 grid32（现有故事线卡旁）；数据 `GET /api/public/audit`：`summary{blockTotal,blockActive,blockedByGuard,executedActions}` + `blocks[]{ip,durationMinutes,source,actor,createdAt,unblocked,unblockMode,auditId}`；**IP 按站主规则掩码**：保留前三段、最后一段换 `x`（`172.16.18.12` → `172.16.18.x`）✓；空态区分"读不到（HTTP xxx）"与"本窗口没有封禁记录"✓；复用 `.mod/.row/.chip` 不新增 CSS ✓；**验收含"DOM 里不出现完整四段 IP"** ✓（掩码函数只改显示、**不改用于分组的原始值** ✗ 否则同 /24 攻击者会被合并 ✓） |
| **T21** | **攻击故事线上屏** | C + G | 5~6h | `/alerts/` 现有故事线卡原地升级；候选池 `/stories` + **点击才懒加载** `GET /api/public/story?src=` 画时间线（`events[]` 升序、每段 ≤40、`truncated` 如实标注 ✓）；必须区分"该来源这段没数据"与"尚未接入（coverage.status=NOT_WIRED）"✗；脱敏要覆盖 `srcIp` **与 `events[].summary` 内嵌 IP**（同一规则：最后一段 → `x` ✓）；**验收含"点击前 0 个 /story 请求"** ✓ |
| **T22** | **知识库栏目** | C + G | 2~3h | 放 `/ai/`（该页现在 0 轮询、最干净 ✓）；`GET /api/public/kb?q=`（独立 20 次/分钟上限、有 embedding 成本 ✗）⇒ 固定话题按钮 + Enter 才发 + 会话内缓存 + **不轮询** ✓；显著写明后端白名单口径（`allowed-roots=security-docs,data/kb-approved`、`allowed-source-types=community`）；结果最多 3 条；空态写"公开知识库没有命中「X」的内容（不是取不到，是确实没有）"✓；**验收含"静置 60s 0 请求"** ✓ |

### 问题单（按优先级，需要拍板或修 ✗）
```
U1【红线冲突·最重要】后端**早就有全局 IP 掩码开关**（`app.public.mask-ips`，唯一读取点 PublicIpPolicy.java），
   但**生产默认 = false ⇒ 展示真实 IP** ✗；实测所有响应 ipDisclosure.masked=false、stories[].srcIp 是完整公网 IP。
   ① 后端翻开关（≈1 个环境变量，所有端点含存量页面一次性合规 ✓ 但属后端线操作 + 要重启应用）
   ② 不翻、只在前端脱敏（存量页面继续打完整 IP ✗ ）——**我的建议是 ①**，需站主一句话 ✓
R1【站主已裁定：**不算违规、保留** ✓】
   掩码规则改为"只掩最后一段"⇒ 存量三处（api-bind.html L223/L276/L335）**无需改动即可接受** ✓；
   若要统一成掩码显示，顺手加一个 `maskIp()` 即可（非必须 ✗）。原描述：老页面渲染攻击者 IP：`layouts/partials/xk-demo/api-bind.html` L223（路径图节点）·
   L276（/stories tag）· L335（攻击流终端行）⇒ 必须与 T20/T21 同批改，或明确豁免 ✓
U5【信息泄漏】`/api/health` **无鉴权且 200** ✗，泄漏 embeddedGitCommit/提交信息/mock 开关/documentVectors ⇒ 建议收口 ✓
R3【文案与实现不符】靶场页卡头写 `POST /api/playground/check`，实现却是 `PG_DEMO` 本地假结果 ✗ ⇒ 要么接真接口、要么改文案 ✓
U4【后端线提醒】`/opt/secagent/src` 源码树**落后于运行 jar** ✗（没有 stories/story/webstats 实现）⇒ 后端线若"改源码重编"会丢掉这三个端点 ✓
订正：`POST /api/public/tts` 实测 **400 TEXT_NOT_ALLOWED**（不是 503 ✗，说明已启用但只接受白名单短语 ✓）⇒ 总账待订正
订正：srv2 现行 release = **site-20261015-181533**（总账 §2.6 里旧值 site-20261014-235208 应更新 ✓）
```

### F 从 GitHub Discussion #27 得到的结论（对我们直接可用=没有 ✗，方法论三条可用 ✓）
```
① "用户意图会在交互中途漂移 ⇒ 必须重新路由" 正对应我们"公开面只解释概念/内部面才有事件数据"的分层 ✓
② "短期 branch 只把可验证证据交回主线" 对应"处置留痕 auditId/actions 才算证据，模型自述不算"✓（与 T20 展示 auditId 同源）
③ "边界必须靠对照实验定义" 正对应 R3 这类"文案承诺了接口、实现却是本地演示"的坑 ✓
旁证：maintainer 自述"做 Kurisu 角色与执行解耦" ⇒ **角色层不承担执行**是被上游认可的架构 ✓（与我们的铁律同源 ✓）
```
### U1 决议（站主 2026-10-15 拍板）

```
**不翻转后端全局 mask-ips 开关** ✓（保留真实攻击源地址）
**展示规则**：攻击者 IP **保留前三段、最后一段换成 x** ✓（例 `172.16.18.12` → `172.16.18.x`）
  · 实现：一个 `maskIp(s)` 只作用于**显示**；用于分组的原始值**不许改** ✗（否则同 /24 攻击者会被合并 ✗）
  · 已对 `***`/`x` 之类的字符串做幂等处理（避免二次掩码 ✗）
**唯一真红线**：访客自己的 IP、我们内部/内网地址 —— **一律不上页面** ✗（与攻击源地址区分对待 ✓）
⇒ 影响：T20/T21/T22 与 Kimi 设计稿全部按此改；**R1 存量三处不算违规、无需改动** ✓（能顺手统一更好，非必须 ✗）
```