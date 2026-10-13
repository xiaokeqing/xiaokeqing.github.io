# CLAUDE.md — xiaokeqing 博客（知微安全实验室的门面）

> 给任何接手这个仓库的 AI/人看的"项目指令"。**先读完这一页再动手。**

## 这是什么
Hugo 静态站（`xiaokeqing.cn`），是 SecAgent 项目的**对外门面**：展示真实运行中的安全运营数据、
公开问答（只解释不取证）、知识库、可玩的攻防靶场，以及笔记/文章。
定位不是"技术博客模板"，而是**"让陌生人 30 秒内相信这个项目真在跑、而且做得硬"**。

## 硬红线（违反即返工）
```
1. **零第三方资源**：无外链字体/图标/图表/统计/JS 库；所有资源自托管。
2. **固定浅色或"深色玻璃"自有主题**，不引外部主题；`static/images/bg.jpg` **一个字节都不许动**
   （正确 SHA256 = 4B1E13EE54EF5DF240543EEF85DE864F69823CCAD25E023533A5E3F1E9A55660）。
3. **不给匿名访客 SSE/WebSocket**：只轮询（自适应、页面隐藏即暂停、失败退避，只放慢不加快）。
4. **不造假数据**：取不到就显示「未接入 / 最近同步」；绝不编数字、绝不把 mock 当真实、绝不假装流式。
5. 公开面数据一律来自 `/api/public/*`（只读、IP 已掩码）；不得在前端还原/加工真实 IP。
6. 对比度：正文 ≥4.5:1、标题 ≥7:1（用 `_dev/` 下的像素采样法实测，**截图取值时 URL 带 `?wb_noblur=1`**；
   但给站主看观感的截图**不能**带这个参数）。
7. 桌面三栏不回归：`grid-template-columns: 300px minmax(0,1fr) 320px`、间距 20px、内容区封顶 1320px、一屏不整页滚动。
8. 提交：**只 `git add` 你自己改/新增的文件**（绝不 `git add -A`）。
```

## 环境事实（今天的血泪）
```
· **远端必须是 `ssh://git@ssh.github.com:443/xiaokeqing/xiaokeqing.github.io.git`**
  （用 `git@github.com:` 在站主网络上 SSH 握手会被重置）。
· **push 到 main 即自动发布**：`.github/workflows/deploy.yml`（Hugo 0.167 + `scripts/assert-build.sh` 断言 + peaceiris 发 gh-pages）。
  断言会拦下：产物含 `localhost`、缺 CNAME/sitemap、引用死端点（如 `/api/public/latest` 的旧文案）。
· 本机没有 pwsh 7，用 Windows PowerShell 5.1；`.ps1` **必须 UTF-8 with BOM**，且别用 `$home` 这类只读变量。
· `_dev/` 与 `_shots/` 被 `.gitignore` 忽略（`_*/`）→ **测试脚本放 `_dev/` 就进不了仓库**，要进 CI 的脚本放 `scripts/`。
· 本地预览：`hugo server --bind 0.0.0.0 --port 1313`（站主会自己登上来看，别只给截图）。
```

## 结构与验收
```
layouts/partials/spa-*.html  各视图（home/monitor/notes/note/ai/range/about）
static/js/app.js             SPA 路由 + 取数 + 渲染（唯一前端逻辑文件）
assets/css/extended/site.css 全部样式与设计令牌（:root 里有一张"视觉令牌表"）
content/posts/*.md           笔记与文章（front-matter：title/date/categories/tags/description）
_dev/verify-redesign.ps1     **验收闸门**（桌面/移动/a11y/SEO/性能/靶场，当前 64 项）—— 改完必须仍全过
_dev/                        截图/CDP/对比度/测量工具（不进库）
```

## 设计取向（站主明确要求过的）
```
· 界面要**透明**：背景照片整屏透出来，不要用"白团"盖住；文字仍要清楚（深色玻璃 + 霓虹描边是当前方向）
· AI 问答要像**对话界面**（气泡 + 引用卡片内联 + 状态徽标），不是表单
· 监测要像**大屏**（指标带 + 攻击态势 + 自动滚动事件流 + 规则命中），不要拆成一堆小模块
· 攻防靶场要"**能立刻玩且有解释**"（三组件判定 + 未命中≠无害 + 只检测不执行）
· 每一项功能都要能回答"访客会更信任什么"；答不出来的就删掉
```

## 现在不该做的事
```
· 不要 push 前不跑闸门 ｜ 不要改 bg.jpg ｜ 不要引第三方库/CDN ｜ 不要在前端写死数字
· 不要把接口路径、口径说明当正文堆在首屏（放 hover/折叠里）
· 不要在公开页给"完整口令/真实 IP/内部资产名"
```
