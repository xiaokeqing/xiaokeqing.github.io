# 状态 · Q（站点接手窗口，2026-10-15）

> 角色：本窗口是**站点代码的唯一写入者**（窗口 C 已交活停止）。基准 HEAD 起点 `15a8a97`，
> 中途站主/规划侧的 `17bcf52` 把上一窗口 C 的 T8 文件与我在做的删除一起提交了（它自己已声明是误提交 ✗）。
> 本文件只记**我这一轮做过什么、证据在哪、还差什么**。

---

## 1. ai 页首屏超标（2314 KB > 1650 KB）—— 根因与修法

**根因（CDP 抓 initiator 实测，不是猜）**：`_shots/probe-firstscreen.json`（工装 `_dev/probe-firstscreen-initiator.mjs`）

| 页 | 1.5s 首屏 | 是哪两条撑起来的 | 发起者 |
|---|---|---|---|
| ai（改前） | **2369400 B = 2314 KB** ✗ | `/kurisu/full/speaking.hi.webp` 1592000 B + `/kurisu/medium/idle.atlas.webp` 777400 B | 前者 = `parser`（电话面板全身播放器，页面自己设计，HEAD 就有）；**后者 = T8 状态机在 667ms 预取**（`img()`@脚本） |
| 其余四页（改前） | 966758 B = 944 KB | `/kurisu/avatar/normal.speaking.webp` 189358 B + 同一个 759KB 图集 | 图集同样是 T8 预取 |
| 其余四页（上一窗口自报） | 185 KB | 只有头像 189358 B | —— 那份自报**早于** T8 的 600ms boot 定时器，所以数字是过期的 |

关键取证：五个内容页上 `#charCanvas` **在关着的 `v-home` 里，`getBoundingClientRect()` 恒为 0×0**
（`_shots/probe-firstscreen.json` 的 `dom.charCanvas`），而 `XK_SM_JS.boot()` 在 600ms 无条件接管并按
root 剪辑 `prefetch()` ⇒ **为一块看不见的画布白拉 759KB**。ai 页自己还挂着手机面板的 1555KB 全身图，
两项相加就顶破预算。

**修法（只改加载时机，取帧公式/几何/版式一字未动 —— 站主第四批口径③允许的行为级懒加载）**：
在 `XK_SM_JS.img()` 前面加 `canvasRendered()`（`getBoundingClientRect().width>0`，节流 250ms）；
画布不渲染就不设 `src`，只留占位 `Image`（`complete=false` ⇒ `paintOps` 不落笔 ⇒ 原型那一帧继续留着），
画布真露出来（SPA 切回主页）后下一帧就地补拉。
**落点在生成器** `_dev/gen-demo-pages.py` 的 `XK_SM_JS` 常量里（否则下次跑生成器会被覆盖 ✗）。

**前后字节（同一台机器、同一预算 1689600 B）**

| 页 | 改前 | 改后 |
|---|---|---|
| home | 840 KB | **840 KB**（不变：主页画布真的可见，惰性判据不生效） |
| monitor / notes | 944 KB | **185 KB** |
| ai | **2314 KB** ✗ | **1555 KB** ✓ |

---

## 2. 减法（T27 / T28）：删 /labs/ + 删 /about/ + 收旧问答入口

- 导航 **六项 → 四项**（主页 · 监测中心 · AI 问答 · 笔记）：`hugo.toml` 菜单、`layouts/partials/xk-demo/shell-chrome.html`（脚本内容页）、
  `layouts/index.html`（主页产物）、生成器 `DOCK_HREF`/`DOCK_HTML`/chrome 后置裁剪四处同源。
- 删页：`content/labs`、`content/about`、`layouts/labs`、`layouts/about`、`layouts/partials/spa-view-range.html`、
  `layouts/partials/xk-kurisu-bar.html`（旧 SPA 底部问答条）；`layouts/baseof.html` 的 labs→range 分支、
  `tpl-range`、旧输入条挂载点；`static/js/app.js` 的 range 路由/hash 别名/`initRange` 分发。
- 旧 URL 不留死链：`content/alerts/_index.md` `aliases: ["/labs/"]` → `/alerts/`，`content/ai/_index.md` `aliases: ["/about/"]` → `/ai/`（0 秒跳转页，实测原文见下）。
- **站内死链证明**（清空 `public/` 重新构建后全库扫描）：
  `grep -r '/labs/' public/** → 0 命中` ｜ `grep -r '/about/' public/** → 0 命中` ｜ `grep -r '#/range|#/about' → 0 命中`。
  剩下两个路径只有 0 秒跳转页：`public/labs/index.html` = `<meta http-equiv=refresh content="0; url=https://xiaokeqing.cn/alerts/">`。

### 2.1 批内三处接线问题（UI 批自检没抓到，我实测抓到并修了）

1. **生成器 T31 注入锚点与 T8 撞车**：`T31_START_OLD` 原为 `}else{\n play('opening');\n}\nstarted = true;`，
   T8 在中间插了三行（`window.__xkSmIsHome` / `xkSmBoot` / `setTimeout`）⇒ 跑生成器直接 `SystemExit 出现 0 次`，
   `git apply 01-...patch` 同一处也 FAIL。改成只钉 `started = true; lastT = performance.now();`（demo 里唯一一处），
   执行顺序语义不变。
2. **删了 v-range 屏，但 demo 自带的"靶场演示"脚本没删** ⇒ `document.getElementById('pgBtn').onclick` 对 null 赋值，
   五个内容页每页抛 `TypeError: Cannot set properties of null (setting 'onclick')`（实测 gate console=2 ✗）。
   改为在生成器里**整段删除**（`PG_DEMO` 本地假结果那一段），并断言 `PG_DEMO/runPg/pgBtn/pgInput/.pgrun/pgResult` 一个不剩。
3. **`spa-view-range.html` 已删但 `baseof.html` 里 `tpl-range` 是*无条件*求值** ⇒ 构建会报 partial not found。
   连带把死分支、`spa-view-notfound.html` 的 `/#/range`、`spa-view-about.html` 的 `/#/range`、
   `xk-navpill.html` / `xk-dock.html` 的两个死项一起收掉。
4. **/projects/ 与 /demo/（站主拍板④）**：这两节映射到 `about` 路由名，`spa-view-about.html` 里那一段
   个人介绍卡（来源 `site.GetPage "/about"`）随页删除已成空卡 ⇒ 连同"我是谁"锚点一起摘掉，
   页面标题/副标题按节改成"项目"/"在线 Demo"（不再出现"关于"字样），"各栏目在做什么"里那条靶场说明也删掉
   （留着就是假描述）。**残留**：这两个老地址仍由旧 SPA 的 `about` 视图渲染项目/ Demo /数据口径三张卡
   —— 要不要连页面一起退休，需要站主一句话（我按"至少不让关于内容露出来"这条底线做的）。
5. **IP 掩码口径（站主拍板⑧）**：`content/alerts/_index.md` 的描述、`spa-view-monitor.html` 的提示、
   `spa-view-about.html` 的免责段，原来都写"掩码到网段"⇒ 改成站主口径"前三段保留 + 末段 x（分组用原值）"。
   `content/posts/*.md` 里还有两处旧写法（站主自己的文章，本轮没动 ✗ 需他点头）。

---

## 3. 三道门禁原文（本批 4 页口径）

```
① python _dev/check-ssr-contract.py public
   静态路由契约断言（public=public）
   页面                   data-xk-ssr 期望       xk-views  站外资源  结论
   index.html             home       home       True      0         PASS
   alerts/index.html      monitor    monitor    True      0         PASS
   posts/index.html       notes      notes      True      0         PASS
   ai/index.html          ai         ai         True      0         PASS
   结论：全部通过（0 项不合格）

② bash scripts/assert-build.sh ./public
   ……（15 项逐条 PASS）……
   通过 15 项，失败 0 项
   断言全部通过 → 允许发布          （exit=0）
   ★注意：这个脚本现有断言集**就是 15 项**（逐条 grep `ok "` 可数），台账里旧写的"16 项"与脚本不符；
     不是少跑了一条。

③ node _dev/gate-firstscreen.mjs --budget=1689600
   == 首屏字节门禁（预算 1689600 B = 1650 KB）· 真浏览器 1280×900 ==
     [PASS] home     首屏   840 KB / 预算 1650 KB   nonOk=0 console=0 …
     [PASS] monitor  首屏   185 KB / 预算 1650 KB   nonOk=0 console=0 …
     [PASS] notes    首屏   185 KB / 预算 1650 KB   nonOk=0 console=0 …
     [PASS] ai       首屏  1555 KB / 预算 1650 KB   nonOk=0 console=0 …
   == 四页初始屏（新口径）==  [PASS]×4
   == 结论 == 首屏门禁：PASS（0 页超标 / 4 页）｜四页初始屏：PASS（0 页不符）
```

**T31 开场六阶段 · 前 1.5s 逐帧采样**（`_dev/probe-boot-phases.mjs` → `_shots/boot-phases.json`）：

```
   22ms  phase=0  data-xk-boot=0  dock.opacity=0     crtBoot=block  画布不透明像素=0
  348ms  phase=2  data-xk-boot=2  dock.opacity=0     crtBoot=block  画布不透明像素=237440
  948ms  phase=5  data-xk-boot=5  dock.opacity=0.548 crtBoot=none   画布不透明像素=237440
 1567ms  phase=5  data-xk-boot=5  dock.opacity=1     crtBoot=none   画布不透明像素=237440
前 8 个请求：+11ms /index.html ｜ +41ms /images/crt/desk.webp ｜ +66ms /kurisu/full/opening.boot.webp …
（T=0 只有壁纸一张图 ✓；导航栏由闪烁结束事件放行，实测不透明度 0 → 0.55 → 1）
★采样是 100ms 一轮、每轮还要跑一次 evaluate，phase 3/4（大脸闪断）太快**没采到**——
  这两拍本轮没有独立取证，不许当成"已验证" ✓。
```

---

## 4. 待办 / 移交

1. **站主新增的四项（本窗口未做 ✗，按站主给的顺序排在减法之后）**：
   ① 加载提速（preload 壁纸+字体、`requestIdleCallback` 分批预热、导航 hover prefetch、视频先 poster、缓存/字体/图片口径 + 改前/改后数字）；
   ② 左上角品牌区放她的头像（同一张图、压缩、preload、与 /ai/ 手机卡片共用一份）；
   ③ 全站统一成 `/ai/` 那张手机卡片的一套资源（抽共用 partial、删旧的第二份实现）；
   ④ 导航进页介绍（复用 nav_home/nav_monitor/nav_ai/nav_notes；nav_labs/nav_about 随删除作废）
      + "对话中"做成宿主状态（说话/思考/等待）并留 TTS 接口。
2. **T30（知识库条目）需要的两份原文**（/about/ 页删了，文字没丢，别再去翻 git 历史）：
   - 页面 Markdown 原文：`git show 17bcf52^:content/about/_index.md`
   - `/about/` 那一屏的四张卡（ABOUT / SOURCES / KURISU / RULES）：本轮从生成器里删掉的那段，
     已在 `E:\DeepSeek1\work\_ui-batch\data\kb-条目草案-T5.3迁移.md` 里有草案 ✓
3. **不归我动的**：`docs/状态-G-展示设计.md`、`docs/需要站主处理的账户与费用总表-20261015.md`（别人未提交的改动，
   我一个字节没碰）、`docs/展示原型-Kimi/`、`docs/展示设计-Kimi-*.md`（别人的未跟踪文件，未加入提交）。
4. **本轮只按授权改了台账两处口径**：`docs/待办-施工任务清单-给执行AI.md`（附录-5.13 的"六项→五项 / 6→5"）
   与 `docs/项目总体规划-MasterPlan-20261015.md`（第 254/278 行的同一句）⇒ 订正为"六→四 / 6→4"，
   并补记"删两页"。用户纪律原写"不许碰 docs/项目总体规划-*.md"，这两处是站主/规划侧明确授权后才改的。
