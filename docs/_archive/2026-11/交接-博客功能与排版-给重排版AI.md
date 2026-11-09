# 交接文档：xiaokeqing.cn 博客 —— 功能清单、排版现状、重排版的约束与验收

> 读者：接手"重新规划排版/信息架构"的 AI 或人。
> 目的：**在不破坏既有功能、口径与验收闸门的前提下**，重新设计排版。
> 仓库：`F:\7AAA\AI\blog`（Hugo 站点）｜线上：<https://xiaokeqing.cn/>（GitHub Pages）
> 最后更新：2026-10-14（第十一轮改版上线后）

---

## 0. 一句话背景（决定了一切设计取舍）

这不是一个"技术博客模板"，而是一个**个人网络安全项目的对外门面**：
**让一个陌生访客（尤其面试官）在 30 秒内相信"这套安全运营系统真的在跑，而且做得硬"**。
所以每一处设计的评判标准不是"好不好看"，而是：**访客会更信任什么？** 答不出来的功能就该删。

站主明确表达过的审美要求（原话）：
- 界面要**透明**：背景照片整屏透出来，**不要用白团盖住**；
- AI 问答要像**对话界面**（像豆包那种聊天，不是表单）；
- 系统监控要**一页大屏**（指标带 + 攻击态势 + 动态事件流），**不要拆成一个个小模块**；
- 攻防靶场要"**能立刻玩**、并且有解释"；
- 整体要"**高级、科技感**"，不要"像垃圾功能"。

---

## 1. 技术形态（重排版前必须知道）

```
· Hugo 静态站（Hugo 0.167+），**原生 HTML/CSS/JS，零第三方依赖**（无字体/图标/图表/统计/CDN 外链）
· 前端是一个**单页应用（SPA）**，用 **hash 路由**（/#/home、/#/ai、/#/monitor…），全部逻辑在 static/js/app.js（116KB）
· **SSR**：Hugo 为每个路由生成一份 HTML，服务端只渲染"当前路由"的内容进 <main>，
  所有路由的模板表放在文档末尾的 #xk-views（**这是踩过坑的设计，见 §7 坑 1**）
· 样式：assets/css/extended/site.css（109KB，含一整套设计令牌）+ chroma.css（代码高亮）
· 构建产物 105 页；`scripts/assert-build.sh` 7 项断言 + `_dev/verify-redesign.ps1` 110 项闸门
· 发布：push 到 main → GitHub Actions → 跑断言 → 发布 gh-pages（**push 即上线**）
```

---

## 2. 信息架构：菜单 + 视图 + 内容

### 2.1 主导航（hugo.toml `[[menu.main]]`）
`主页 /#/home` ｜ `监测中心 /#/monitor` ｜ `AI 问答 /#/ai` ｜ `靶场 /#/labs`
｜ `笔记 /#/notes` ｜ `分类` ｜ `关于 /#/about` ｜ `搜索`

### 2.2 视图清单（layouts/partials/spa-view-*.html）
| 视图 | 文件 | 功能（真实数据来源） |
|---|---|---|
| 主页 | spa-view-home.html（14.6KB） | Hero（品牌/标题/导语 + **可玩的靶场入口**）、实时指标卡、能力总览、最新告警/蜜罐摘要、文章入口 |
| 监测中心 | spa-view-monitor.html（7KB） | **一页大屏**：指标带（带相对量）+ 攻击来源网段 Top（自绘 SVG）+ 近 24h 节奏 + 事件时间轴 + 自动滚动实时流 + 规则 Top/严重度/采集通道三态灯；底部**如实标注读不到的字段** |
| AI 问答 | spa-view-ai.html（6.7KB） | **对话界面**：消息列表（用户右气泡/AI 左卡片）+ 输入区（Enter 发送 / Shift+Enter 换行）+ **state 状态徽标** + 引用卡片内联展开 + 5 个预设问题 + "回答非流式传输"如实标注 |
| 靶场 | spa-view-range.html（6.4KB） | 一键预设样本（6 个，点一下真跑 `POST /api/playground/check`）+ 三组件判定卡 + `coverageWarning` 常显 + 公开面/内部面对照 |
| 笔记列表 | spa-view-notes.html（4.9KB） | 笔记列表 + 分类/标签、URL 可分享 |
| 笔记详情 | spa-view-note.html（7.4KB） | 单篇笔记/文章渲染（含代码高亮、目录、上下篇） |
| 关于 | spa-view-about.html（8KB） | 项目说明、公开端点清单与口径、可核验性说明、已知局限 |
| 404 | spa-view-notfound.html（1.5KB） | 找不到路由时的提示 + 返回入口 |
| 公共 | spa-nav / spa-side / spa-footer / spa-search / head | 顶部导航、侧栏、页脚、搜索、head 元信息 |

### 2.3 内容（Hugo content）
```
content/posts/*.md      10 篇（笔记/文章，front-matter：title/date/categories/tags/description）
content/{about,ai,alerts,demo,labs,projects}/  这些是为路由与列表页准备的目录（SSR 会用到）
```
新增笔记：`scripts/new-note.ps1 -Title "…" -Category … -Tags … -Summary …`（**默认只落盘，`-Publish` 才本地 commit，永不 push**）

---

## 3. 数据契约（排版可以改，数据口径不能编）

后端基址：`https://demo.xiaokeqing.cn`（写死在 hugo.toml `wbApiBase`，前端 `API` 变量）
公开端点（**只读、匿名、有独立限流**）：

| 端点 | 用途 | 限流 | 缓存 |
|---|---|---|---|
| `GET /api/public/overview` | 指标总览（含 stats24h、六态、额度） | 20/min | 15s 快照 + ETag |
| `GET /api/public/alerts` | 告警聚合（含 stats24h、来源、severity） | 20/min | 15s + ETag |
| `GET /api/public/alerts/{aggId}` | 单条告警详情 | 20/min | 15s + ETag |
| `GET /api/public/honeypot` | 蜜罐战报（连接/登录/来源 Top/口令**结构**/时间线） | 20/min | 15s + ETag |
| `GET /api/public/audit` | 处置审计（封禁记录/动作/理由） | 20/min | 15s + ETag |
| `GET /api/public/latest` | 窗口聚合（**已上线**，返回 windowSize/windowAlertCount） | 20/min | 15s + ETag |
| `GET /api/public/geo` | **地理分布聚合**（按国家/省/ASN + 24h 趋势 + coverage 分母） | 20/min | 15s + ETag |
| `GET /api/public/kb` | 知识库片段检索 | 20/min | — |
| `POST /api/public/ask` | 公开问答（多 Agent 编排 + 引用） | **6/min**、并发 1 | — |
| `POST /api/playground/check` | 靶场判定（只检测不执行） | 有独立限流 | — |

**必须遵守的展示口径**：
```
① **不造假**：取不到就显示「未接入 / 读不到 / 最近同步」+ 原因，**绝不编数字、绝不把 mock 当真实**
② 每处数字要能回答"它从哪来、多久更新、什么口径"（页面用 hover/折叠说明，不要堆在首屏）
③ 六态徽标机读值：model / model-failed / input-insufficient / no-retrieval / retrieval-failed / rule-based
④ `/geo` 的 `coverage` 必须一起展示（totalAlerts / withSourceIp / geocoded / excludedSelf / excludedInternal…）
   —— 现在 24h 有约 11 万条告警，但**只有约 10.7 万条带来源 IP 字段**，其中真实公网归属约 6.3 万条；
   **不许把子集画成"全量攻击"**
⑤ 公开面**不含任何 IP 的逐条明细用于反查**这件事已由站主拍板放开（告警/蜜罐列表显示**观测到的真实来源 IP**），
   但必须带统一口径字段 `ipDisclosure`（notice + removalContact），且 **蜜罐完整口令、内部资产名永不出现**
⑥ **不给匿名访客 SSE/WebSocket**：只能轮询（自适应、页面隐藏即暂停、失败退避，**只放慢不加快**）
```

---

## 4. 设计系统（改排版时优先改这里，而不是逐处写死）

`assets/css/extended/site.css` 顶部有一张令牌表（`:root`），**两套主题**（tech 深色玻璃=默认 / read 浅色玻璃=阅读模式，顶部一键切 + localStorage 记忆）。关键令牌：

| 类别 | 令牌 |
|---|---|
| 页面/卡片 | `--xk-page`（=背景图加暗纱）、`--xk-card`、`--xk-card-line`、`--xk-card-in`、`--xk-card-in-line`、`--xk-line`、`--xk-line-2`、`--xk-shadow` |
| 文字 | `--xk-title`、`--xk-text`、`--xk-muted`、`--xk-link` |
| 语义色 | `--xk-blue`、`--xk-blue-soft`、`--xk-green`、`--xk-red`、`--xk-orange` |
| 圆角 | `--r-card`、`--r-ctl`、`--r-pill` |
| 间距 | `--xk-gap`、`--xk-pad-y`、`--xk-pad-x`、`--xk-guide-gap` |
| 尺寸 | `--xk-maxw`（内容封顶 ~1320px）、`--xk-side-w`、`--xk-side-left`、`--xk-sidew`、`--xk-hero-align`、`--xk-hero-shift` |
| 玻璃 | `--xk-blur`、`--xk-blur-soft` |
| 字体 | `--xk-sans`、`--xk-sans-hand`（手写体点缀）、`--xk-mono` |
| **主题覆盖**（read 模式下重定义） | `--xk-t-card`、`--xk-t-card-line`、`--xk-t-card-in`、`--xk-t-title`、`--xk-t-text`、`--xk-t-muted`、`--xk-t-link`、`--xk-t-accent`、`--xk-t-glow` |

**视觉语言**：背景照片 + 暗纱（`brightness(.52)` + 冷色暗纱 .34–.60，替代旧的白纱）→ 深色玻璃卡片 + 霓虹描边/发光；动效**全部 CSS**（条形入场、消息淡入、网格扫描、脉冲），`prefers-reduced-motion` 下真的关掉位移。

**对比度（已实测，必须保持）**：正文最低 read-1280 **5.31** / tech-1280 **8.88**；标题最低 **12.41** / **16.85**；两主题 × 两视口 **0 项不达标**。
背景压暗值 `.52` 是"背景清晰可见 vs 浅色文字 ≥4.5:1"的折中；调到 `.6` 更清楚但 Hero 辅助小字会掉到 4.2–4.4（正文标题仍达标）——**这是站主可决定的一档**。

---

## 5. 当前排版规格（重排版的起点）

```
· 桌面：三栏 `grid-template-columns: 300px minmax(0,1fr) 320px`（左导航/中内容/右辅助），列间距 20px
· 内容区封顶 1320px；主内容单列阅读宽度友好（文章页 ~760px 正文宽）
· 卡片：玻璃底 + 1px 描边 + 大圆角（--r-card）+ 内层内阴影
· 移动端（<=900px）：三栏收成一栏，侧栏折叠进抽屉；大屏指标带换行两列；时间流高度压缩
· 断点：900px（主要）、1280px（三栏/大屏差异）、390px（手机基准）
· 每页顶部有统一的「页面说明/口径」折叠块（aria-controls 指向内容区，**id 名被闸门断言钉住**）
```

**首屏信息架构的硬要求**（闸门第 11 组）：首屏必须让访客一眼看到"这是什么 + 现在真在跑什么 + 数据从哪来"。

---

## 6. 红线（违反即返工）与验收

### 6.1 红线
```
① **零第三方资源**：无外链字体/图标/图表库/统计脚本；所有资源自托管
② `static/images/bg.jpg` **一个字节都不许动**（正确 SHA256 = 4B1E13EE54EF5DF240543EEF85DE864F69823CCAD25E023533A5E3F1E9A55660）
③ 不给匿名访客 SSE/WebSocket
④ 不造假数据（取不到就如实说"读不到"）
⑤ 公开面不得出现：蜜罐完整口令、内部资产名（web-01 之类）、规则正则原文、内网地址
⑥ 对比度：正文 ≥4.5:1、标题 ≥7:1（必须实测，不许目测）
⑦ 桌面三栏不回归（除非站主明确同意改 IA）
⑧ 提交时**只 `git add` 你自己改的文件**（绝不 `git add -A`）
```

### 6.2 验收闸门（改完必须全过）
```bash
# 本地预览（站主会上来看）
hugo server --bind 0.0.0.0 --port 1313

# 构建 + 发布断言（CI 里同一条，7 项）
hugo --gc --minify --cleanDestinationDir
bash scripts/assert-build.sh ./public

# 完整验收闸门（110 项：桌面/移动/a11y/SEO/性能/靶场/SSR/首屏/功能落地）
pwsh -File _dev/verify-redesign.ps1
```
发布：`git add <你改的文件> && git commit && git push origin main`（**push 即自动上线**；远端必须是
`ssh://git@ssh.github.com:443/xiaokeqing/xiaokeqing.github.io.git`，用 `git@github.com:` 会被网络重置握手）。

---

## 7. 已知坑（都是踩过的，别重踩）

1. **`<template>` 不能放在 `<main>` 中间** —— 浏览器解析器会吞掉后续节点，导致 SSR 容器位置错乱、
   整页被 JS 替换成 404（`/ai/`、`/labs/` 都中过）。修法：服务端只渲染当前路由进 `<main>`，模板表放文档末尾 `#xk-views`。
   **纯 HTML 文本断言全绿，只有真浏览器 + DOM 断言能抓住**。
2. **hash 路由**：新增页面必须同时加 `routeFromPath` 分支（少一个分支 → 直接打开该 URL 会被判成 notfound）。
3. **API 基址**：线上是 `https://demo.xiaokeqing.cn`；产物里**绝不能出现 localhost**（断言会拦）。
4. **断言不要写"会过期的前提"**：曾有一条写死"不得出现 `/api/public/latest`（死端点）"，
   后来该端点上线了，于是把正确文档当成违规、**整轮发布被拒**。现在改成"所有出现的 `/api/public/*` 必须在白名单里"。
5. **`.gitignore` 有 `_*/`** → `_dev/`、`_shots/` 进不了仓库；要进 CI 的脚本放 `scripts/`。
6. **Windows PowerShell 5.1**：`.ps1` 必须 UTF-8 **with BOM**；不要用 `$home`；`$x = if(...){}` 不合法。
7. **CDN/缓存**：改完若看不到变化，加 `?v=<时间戳>` 或强刷；`_dev` 里的截图脚本要用 `?wb_noblur=1`（取色用），
   但**给站主看的截图不能带这个参数**。

---

## 8. 交给重排版方的"必须顺手修"清单（已知问题）

| # | 问题 | 正确做法 |
|---|---|---|
| 1 | `hugo.toml` 里 `testsRun = 239`（**已过期**） | 改为 **471**，`testsSkipped = 3`、`testsFailed = 0`、`testsAsOf` 更新为当前日期；同步更新引用它的断言与文案（口径来源：SecAgent 仓库 `mvn -B test`） |
| 2 | 监测中心缺「7 天 × 24h 热力图」「HTTP 状态码分布」 | 公开端点**暂无** `statusCode` 与历史日桶字段 → 现在**如实显示"读不到"+原因**。后端已排期（`/api/public/webstats`，会给状态码类别 + 7 天桶），**字段到位后再画**，不许拿 24h 数据冒充 7 天 |
| 3 | 没有 GIF/录屏 | 本机无录屏工具，装一个会违反零第三方；已用"两次独立会话截图数值不同 + 相对时间三档 + reduced-motion 下 `transform:none`"作替代证据 |
| 4 | 背景压暗值 `.52` | 站主可决定是否调到 `.6`（更清楚，代价：Hero 辅助小字 4.2–4.4）——一行改动 + 一条断言 |
| 5 | 靶场/大屏的部分文案偏"说明书" | 重排版时应把"口径/来源"收进 hover 或折叠，首屏只留结论与数字 |

---

## 9. 文件地图：改排版该动哪里

```
hugo.toml                       站点参数、菜单、Hero 文案、公开数字（testsRun 等）
layouts/baseof.html             全站骨架（含 <main data-xk-ssr> 与 #xk-views 模板表）
layouts/index.html              首页入口（把当前路由渲染进 main）
layouts/partials/spa-view-*.html 每个视图的结构与文案（**排版改动主战场**）
layouts/partials/{spa-nav,spa-side,spa-footer,spa-search,head}.html  公共区域
layouts/posts/single.html       文章页（正文排版、目录、代码块）
layouts/_default/{list,taxonomy,term}.html  列表/分类/标签页
assets/css/extended/site.css    **设计令牌 + 全部样式**（改视觉优先改令牌）
static/js/app.js                路由、取数、渲染、交互（116KB，谨慎改；改路由要同步 routeFromPath）
static/images/bg.jpg            背景图（**禁改**）
content/posts/*.md              文章/笔记
scripts/assert-build.sh         发布断言（7 项）
_dev/verify-redesign.ps1        验收闸门（110 项，含截断/像素取色/DOM 断言）
_dev/r11/{DEFECTS,REPORT,WHY,CONTRAST}.md  第十一轮的缺陷报告/报告/理由/对比度实测
```

---

## 10. 一句话交接

**你可以重新设计排版、信息层级、动效与视觉语言；但不能改数据口径、不能引第三方、不能造假数字、
不能动 bg.jpg、不能给匿名访客长连接；改完必须让 `assert-build.sh`（7 项）与 `verify-redesign.ps1`（110 项）全过，
然后 push（push 即上线）。** 任何"取不到的数据"都如实写"读不到 + 原因"，这是这个站最大的卖点，也是它区别于模板的地方。
