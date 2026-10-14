# 改造须知（给直接改这个博客仓库的 AI）

> 这个仓库是**已上线的生产站点**（GitHub Pages，<https://xiaokeqing.cn>）。请先读完本文再动手。
> 你可以改任何文件，但下面这些是**硬约束**，违反会导致发布失败或线上事故。

## 1. 站点结构（先理解，再改）

```
Hugo 0.167 extended + 原生 HTML/CSS/JS，**无框架、无构建期依赖**
哈希路由 SPA：#/home、#/notes、#/monitor、#/labs、#/about、#/ai…
  · 服务端渲染：Hugo 把**当前路由**渲染进 <main>，客户端靠 hashchange 换页
  · 文档末尾有一个 <div id="xk-views"> 模板表：SPA 换页用的其它路由模板（inert，不渲染在主页上）
    ⚠️ 统计"某选择器是否出现在主页"时必须先剥掉这一段，否则会误判
· 主页 layouts/partials/spa-view-home.html 目前 = 全屏场景（正文只留一个 sr-only h1）
· 其它页面（monitor/notes/labs/about）保持三栏契约（300px / 1fr / 320px），不要动它们的分栏
```

## 2. 八条硬约束

```
① **零第三方依赖**：不得引入任何站外脚本/字体/图标库/CDN；不得新增站外域名。
   断言会扫产物，一旦出现站外引用即失败。
② **零造假**：数据取不到就显示"读不到 / 未接入"，不要用占位数字糊。
③ **公开面不泄露**：蜜罐抓到的**完整口令永不上公网**（只给长度/字符类/结构）。
   公开 API 的响应在服务端已统一脱敏，前端不要再引入原始字段。
④ `static/images/bg.jpg` 的 SHA256 固定（4B1E13EE…A55660），**不要替换或改字节**。
⑤ **首屏加载 ≤1.5MB（严格）**：大资产一律懒载；改完要能报出"首屏实际加载量"。
⑥ 静态资产总量：目前门禁上限较小（历史上写过 12MB），**若要引入大批美术资源，先确认上限口径**
   （见 docs/主页实现方案-照搬Amadeus原版.md §4；39 个剪辑全量约需 60~80MB）。
⑦ **一键回退**：hugo.toml 的 `kurisuEnabled=false` 必须能让所有角色相关痕迹消失（已有实现，别破坏）。
⑧ **角色素材契约**：`static/kurisu/manifest.json` + `static/kurisu/**` + `static/images/crt/**`
   是运行时的数据契约（剪辑/帧间隔/图集几何/loopMode/CRT 多边形/开场条目）。
   改布局可以，但**不要改这些字段名与含义**（播放器按它读）；要改就同步改播放器并更新文档。
```

## 3. 改完必须跑的门禁（不通过不要推）

```bash
# 1) 生产构建（注意：不要让 hugo server 往 public/ 写，它注入 livereload 会把产物弄脏）
hugo --gc --minify --cleanDestinationDir

# 2) 发布断言（16 项；exit != 0 即失败）
bash scripts/assert-build.sh ./public

# 3) 真浏览器验收（125 项，需本机 Edge/Chrome；脚本在 _dev/，该目录已 gitignore）
powershell -ExecutionPolicy Bypass -File _dev/verify-redesign.ps1
```
⚠️ 常见坑：**曾有一个遗留的 `hugo server` 在后台往 `public/` 写开发构建**，导致断言时红时绿、产物里出现
`127.0.0.1` baseURL。跑门禁前先确认没有它（`Get-Process hugo`），或给 server 加 `--renderToMemory`。

## 4. 发布方式与纪律

```
· 推送即发布：push 到 main → GitHub Actions 构建 → 发布 gh-pages（CI 里也会跑 assert）
· 本网络下 git 远端必须用 ssh://git@ssh.github.com:443/...（git@github.com 的握手会被重置）
· **只 add 你自己改的文件**（绝不 `git add -A`）；工作区里别人的改动不要碰
· 不要提交 `_dev/`（已 gitignore）、不要提交 `public/`
```

## 5. 本机环境（Windows / PowerShell 5.1）

```
· hugo：C:\Users\T\AppData\Local\Microsoft\WinGet\Packages\Hugo.Hugo.Extended_…\hugo.exe（v0.167.0 extended）
· **没有 pwsh，只有 Windows PowerShell 5.1**：不支持 `? :` 三元运算符；`curl` 是 Invoke-WebRequest 的别名
  （要用真 curl 写 `curl.exe`）；`||` 在 PS5.1 会解析失败
· .NET 静态方法（如 [System.IO.File]::ReadAllText）用**相对路径时会按进程工作目录解析**，
  不是 PowerShell 的当前目录 → 一律用绝对路径
· **任何"用变量拼替换模式/正则"的地方先断言非空**：曾有脚本用空字符串当 awk 替换模式
  （`awk -v a=`），`index(rest,"")` 恒为真导致死循环，把服务器内存吃到 113MB。
  一次性文本处理一律加 timeout。
```

## 6. 与角色运行时的边界（建议的分工）

```
· **视觉/排版/内容呈现**：你可以随意重做（这也是站长请你来的原因）
· **帧运行时与素材契约**（manifest.json 字段、图集切帧方式、fps=1000/frameIntervalMs、
  状态机 37 节点/87 边、场景机 6 节点/19 边、口型两层机制、开场 180 帧）：请**先读**
  docs/amadeus-research/HOW-IT-WORKS.md（1150 行，源码级）与 docs/主页实现方案-照搬Amadeus原版.md，
  改这部分时保持字段兼容；不确定就先问，别猜。
· 已核实的机制要点（别踩反）：
  - 合成层序：桌面底图（常驻）→ CRT **多边形**遮罩 → 遮罩内「空房间底图 → 角色帧 → 字幕板 → 场景整图」
    → 氛围光/辉光/扫描线；**玻璃罩/暗角在角色之上**
  - 角色落位：scale = min(W*0.64/764, H*0.90/1028)，x = 0.52W，y = bottom − 1.2%H，anchor=(0.5,1)
  - **整屏/窗口不许做缩放或位移动画**（原项目全仓无相机动画；做了会与平面实拍的透视冲突）
  - 场景之间是**硬切**；全项目唯一过渡是 0.35 秒**线性 alpha**，只用于"角色态 ↔ 场景态"
  - 眨眼只在 180 帧特写循环里（第 38–43 帧）；中景 39 个剪辑没有眨眼机制
  - 口型：说话中用基础帧自带的嘴；静音（mouthValue ≤ 0.08）叠**整帧闭嘴图** + 椭圆遮罩只露嘴
```

## 7. 参考文档（都在仓库里，不需要外部访问）

```
docs/主页实现方案-照搬Amadeus原版.md        实现方案总纲（效果目标/机制/资产/体积/分期/未决项）
docs/amadeus-research/HOW-IT-WORKS.md      源码级机制（1150 行，附 file:line 出处）
docs/amadeus-research/data/statemachine.json   37 节点/87 边（播放器直接读）
docs/amadeus-research/data/scenarios.json      6 场景/19 边 + start/empty_room/dwell
docs/amadeus-research/data/spec-runtime.md     字段说明书
docs/amadeus-research/refs/                15 个逐字源码切片
docs/kurisu-素材来源与用途声明.md            角色/场景来源与一键下线说明
```
