# 状态 · 窗口 C-站点角色

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 `docs/窗口分工规范-20261015.md` §四

| 项 | 内容 |
|---|---|
| 负责 | T7 视频 → T8 状态机+口型 → T14 决策（含发布） |
| 状态 | **T7 已完成并上线（`site-20261015-210145` / `fc79d0c`）**；**T8 第一批（状态机 + 宿主触发）已达"可验收"状态，等规划侧核验发布**；第二批（口型）**未开工**（按排期变更等指令） |
| 改了哪些文件 | **T8 第一批**：`_dev/gen-demo-pages.py`（新增 `XK_SM_JS` 模块 + `xk_sm_patches()`，生成器仍幂等可重跑）；生成器产物 `layouts/index.html`、`layouts/partials/xk-demo/shell-script.html`、`layouts/{alerts,posts,labs,about,ai}/list.html`、`layouts/about/single.html`；新增未跟踪 `_dev/verify-sm-walker.mjs`、`_dev/refresh_manifest_voice.py`；`static/kurisu/manifest.json`（**voice 段刷新**）；`docs/状态-C-站点角色.md`。**T7**：`static/kurisu/video/**`（80 文件 9,543,169 B 原样拷贝）、`static/kurisu/video-manifest.json`、`_dev/{build_video_manifest.py,check-video-align.py,verify-video-wiring.mjs,t7-baseline-shot.mjs,_t7-pixeldiff.py}` |
| 验收证据 | ① 帧指纹 **213**（≥8 ✓）② reason 统计 `{host:voice:1, host:emotion:19, host:idle:10, host:cadence:3}`（四类全 ≥1 ✓）③ `?seed=20261015` 两次 timeline **逐字一致**（33 条，`timelineEqual=true`）④ 回落注入两种：`statemachine HTTP 404` / 坏 JSON → `on=false`、原型剪辑仍在推进（`cur=opening`）、**console 0 报错** ⑤ hidden 6s：`fi 59→59`、`hiddenSkipped=287`、切回续播不快进 ⑥ 冻帧对拍 video/pixel/off + 故障A/B **非角色区全部 0 像素差**（0/905190，video vs pixel 0/655872）⑦ 三道门禁：assert-build **16/16**、gate-firstscreen **6/6 PASS**、check-ssr-contract **6/6** ⑧ 证据文件：`_shots/t8-sm.json`、`_shots/t8-sm-{run1,run2,replay,fallback404,fallbackbadjson}.png`、`_shots/video-align.json`、`_shots/t7-video.json`、`_shots/t7-{baseline-home,pixel-home,video-home,fallback-home,corrupt-home,off-home}.png` |
| 下一步 | 等规划侧核验并发布 T8 第一批 ⇒ **第二批（口型）等指令**（排期已变：UI 批要动 `_dev/gen-demo-pages.py` + `layouts/*`，与我同文件，需先交接） |
| 卡点 | 无（门禁全绿）。两项**需规划侧动手**：① `.gitignore` 白名单加 `_dev/verify-sm-walker.mjs`、`_dev/refresh_manifest_voice.py`；② T7 已发布，本批 T8 需再发一次 |

## T8 第一批：实现要点与口径（第二批会接着用）

```
· 模块 XK_SM_JS（内联，生成器注入主页脚本与五页 scene-js）：
  读 /kurisu/statemachine.json（38 节点/88 边，root=idle），懒加载（setTimeout 600ms，首屏零影响）
· 游走：出边概率**归一化后**掷骰子；prob=0 的边永不参与随机；13 个 once_then_hold 播完**停末帧**
· 取帧：优先 T7 视频层（同一帧号 == 同一帧），拿不到画 medium 图集；两条路共用 CHAR_BOX 落位公式；
  **不用 opaque_bbox**（U8 已实测是坏的），只用 medium.pages 的 first_frame/last_frame + frame_size
· 单帧时长 = statemachine 的 frameIntervalMs，保留 Math.max(16, ...) 夹取
· 宿主触发四类 + 冷却：voice / emotion / idle（可见且连续 12s 无宿主事件）/ cadence（>25s 无宿主事件兜底）
  · **cadence 的判据是"没有宿主事件"（lastHostEvt），不是"没有跳转"** —— 否则 idle 每 8s 刷新一次，
    兜底永远轮不到（本轮改过这处）
  · 每次切换记 reason = `auto:<edge>` 或 `host:<kind>`，验收按 reason 统计
· 触发规则：greeting 首访/回访（localStorage 分流，沿用接手批那套）｜page_intro 每页一条 / 同页 10 分钟去重｜
  status **只在状态行真实文本变化时**（轮询 + 20s 防抖，不按定时器）｜event 可打断 status
· 可复现：`?seed=<n>`（种子化 RNG）+ `?replay=<base64>`（按 timeline 回放）
· 回落：JSON 404 / 解析失败 / 结构不对 ⇒ `on=false`，**回到原型 4 剪辑循环**（实测 console 0 报错、角色照常动）
· hidden：暂停推进 + **清零累加器**（实测 fi 不变、hiddenSkipped 增长、切回续播）
· 验收旋钮（只在 URL 上生效，默认值不变）：`?xk-host=<ms>`（host 冷却）、`?xk-idle=<ms>`（idle 阈值）、
  `?xk-sm=off`（关状态机）。**验收用的是压缩节奏 ?xk-idle=3000&xk-host=800，不是真实节奏** ✗
· 诊断口径：`window.__xkSM`（既是状态对象也是 API —— 两套口径指向同一份状态；
  `__xkSM.reasons()` / `.stats()` 给门禁与验收脚本用，状态字段在 `.on/.cur/.why/.reasonCounts/.tl`）

## 本轮踩过并修掉的 4 个真 bug（都写进代码注释了，别重犯）

```
① 生成器变量用错：T7 收尾把 shell_scripts[0]（外壳业务脚本）当成带 CLIPS 的 scene-js 打补丁 ⇒ 补丁对不上
② 生成器不可重跑：补丁不幂等，上一次中途中止已在盘上的产物会让再跑直接报错 ⇒ 所有补丁加存在性门
③ API/状态**字段名冲突**（连踩两次）：状态里的 reasons:{} 顶掉 reasons()（门禁报 reasons is not a function）、
   host:[...] 顶掉 host()、cur 顶掉 cur()；现已改名 reasonCounts / hostEntries / currentClip，
   并在 assignObj 里加了冲突自检（一旦再重名会写进 __xkSM.errs）
④ 状态机 fetch 用 force-cache：换版/注入 404 都会被缓存吃掉（实测 sm=[200]）⇒ 改 cache:'default'
另：headless 的 rAF 会在数秒后停摆（接线前的产物也一样）⇒ 确定性验收改用固定虚拟时钟 stepFixed(33ms)
```

## T7 实现要点（已上线，第二批口型会用到）

```
· 总开关 data-xk-kurisu-mode="video|pixel|off"；?xk-kurisu-mode= 与 localStorage 可覆盖
· 逐帧 seek：video 第 i 帧 == 图集第 i 帧；倒放剪辑（key_point_to_thinking，manifest.reverse）取 video[n-1-i]
· ≤4 枚离屏 <video> + LRU，绝不进 DOM；解好的帧先搬进离屏 canvas
· 降级链 video → 图集 → poster；单剪辑失败永久降级；连续 2 个解不出 alpha ⇒ 整站回 pixel
· 预载纪律：首次手势前不取清单/视频（首屏 1.5s 内 video+poster+manifest 请求数 = 0）
· 偏离接线方案 §4.2 一处：方案写"两枚 video 交替防 seek 白屏"，本实现走逐帧 seek（一枚剪辑一枚 video），
  防白屏由"poster 先顶位 + 离屏帧缓冲"承担
```
