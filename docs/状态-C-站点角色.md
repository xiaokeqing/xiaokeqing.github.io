# 状态 · 窗口 C-站点角色

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 `docs/窗口分工规范-20261015.md` §四

| 项 | 内容 |
|---|---|
| 负责 | T7 视频 → T8 状态机+口型 → T14 决策（含发布） |
| 状态 | **T7 进行中（代码与自验完成，等规划侧两件事：① assert-build ⑨ 上限口径 ② .gitignore 白名单）** |
| 改了哪些文件 | `_dev/gen-demo-pages.py`（新增 T7 补丁块 + `xk_video_patches()` 幂等）；生成器产物 `layouts/index.html`、`layouts/{alerts,posts,labs,about,ai}/list.html`、`layouts/about/single.html`、`layouts/partials/xk-demo/shell-script.html`；新增未跟踪：`_dev/build_video_manifest.py`、`_dev/check-video-align.py`、`_dev/verify-video-wiring.mjs`、`_dev/t7-baseline-shot.mjs`、`_dev/_t7-pixeldiff.py`、`static/kurisu/video/**`（80 文件 9,543,169 B，原样拷贝未重编码）、`static/kurisu/video-manifest.json` |
| 验收证据 | ① 对齐/alpha：`_shots/video-align.json`（38 剪辑/114 探针，四角 alpha 全 0，倒放剪辑按 `video[n-1-i]` 修正后 IoU 0.9966）② 真浏览器五档 + 两种故障注入：`_shots/t7-video.json`（含 alpha 品红采样 0.516、`<video>` 0 个进 DOM、console 0 报错、idle 损坏只请求 1 次并永久降级）③ 冻帧对拍：`_shots/t7-{baseline-home,pixel-home,video-home,fallback-home,corrupt-home,off-home}.png` → **非角色区 0 像素差**（五档 + video vs pixel）④ 汇总说明：`_shots/t7-evidence.md` ⑤ 门禁：gate-firstscreen **PASS 6/6**（home 860KB/四页 185KB/ai 1555KB）、check-ssr-contract **6/6 PASS**、assert-build **15/16**（⑨ 见卡点） |
| 下一步 | ① 规划侧改 `scripts/assert-build.sh` ⑨ 上限 80→96 MiB（理由：T7 视频入库 +9.10 MiB；**不改的话 T9 瘦身会违反 D9"先接线再删"**）；② 规划侧在 `.gitignore` 里把 `_dev/build_video_manifest.py` / `_dev/check-video-align.py` / `_dev/verify-video-wiring.mjs` / `_dev/t7-baseline-shot.mjs` / `_dev/_t7-pixeldiff.py` 加进白名单（`_dev/*` 是忽略 + 白名单例外，我不改 .gitignore）；③ 两项批了就进 T8 |
| 卡点 | 见上两条（都需要规划侧的文件，不在窗口 C 允许写的清单里） |

## T7 实现要点（T8 会用到，先记这里）

```
· 总开关：<html data-xk-kurisu-mode="video|pixel|off">；?xk-kurisu-mode= 与 localStorage 可覆盖
  pixel = 逐像素等于接线前（已用冻帧对拍证明）；off = 角色层完全不加载（0 请求）
· 模块形态：内联 `XKV2_BLOCK`（由生成器补丁注入主页脚本与五页 scene-js），回滚 = 一行
· 逐帧 seek：video 第 i 帧 == 图集第 i 帧；单帧时长取 statemachine 的 frameIntervalMs
  （容器 60fps 的 durationMs **不是**帧间隔 ✗）；倒放剪辑按 manifest.reverse 取 video[n-1-i]
· ≤4 枚 <video> + LRU；<video> 绝不上 DOM；解好的帧先搬进离屏 canvas 再 drawImage
· **偏离接线方案 §4.2 一处**：方案写"两枚 video 交替以防 seek 白屏"，本实现走"逐帧 seek 定位"
  ⇒ 同剪辑用一枚（两枚各自 seek 会打架），防白屏改由"poster 先顶位 + 离屏帧缓冲"承担
· 预载纪律：首次手势前不取清单、不取视频（实测首屏 1.5s 内 video/poster/manifest 请求数 = 0）
· 降级链：video → 图集(boot/hi) → poster；单剪辑失败**永久降级**不重试；连续 2 个剪辑解不出
  alpha ⇒ 整站回 pixel
· 诊断口径：window.__xkVid（mode/reason/drawn/fallbackDrawn/failed/decoded/probe/errors）
```
