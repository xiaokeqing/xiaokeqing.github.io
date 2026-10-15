# 旧 GitHub Pages 收口（gh-pages 由「整站镜像」改为「跳转页」）

> 窗口/线：站点线 · GitHub Pages 收口（目标清单第 ⑪ 条）
> 日期：2026-10-16（本地 UTC+8，作业时间 00:10~00:45）
> 基线：`main` = `acfed95`（作业期间另有窗口持续向 main 推送，提交前已 `pull --rebase`，无冲突）
> 本次提交：`922eee2`（`docs(ghpages): 收口旧 GitHub Pages —— gh-pages 只发跳转页，不再镜像整站`）
> 交付物：`.github/workflows/deploy.yml`（改）＋ `redirect-site/**`（新增）＋ 本文件 ＋ `docs/状态-AD-GHPages.md`
> 纪律：**只 add 自己的路径**；无强推；未动 GitHub Settings；未动任何 secret；未打印任何密钥

---

## 0. 先订正任务前提（重要，别照着过期描述去"修"）

任务书写的是"`https://xiaokeqing.github.io/` 现在还能打开旧原型（带 `DEMO v5 · 数字均为演示数据`）"。
**作业时实测：这条已不复现** ✓。改前实测三连（srv1 出网，2026-10-16 00:22 UTC+8）：

```
① curl -sI https://xiaokeqing.github.io/                ⇒ HTTP/2 301，location: http://xiaokeqing.cn/（不是 200）
② curl -s  https://xiaokeqing.github.io/ | grep -c 'DEMO v5'  ⇒ 0（响应体是 162 字节的 nginx 301 页）
③ git show origin/gh-pages:index.html                   ⇒ Hugo 新版站点首页（不是旧原型），文件内 DEMO v5 命中 0
```

为什么会这样：`gh-pages` 分支上有 `CNAME`（内容 `xiaokeqing.cn`，来自 `static/CNAME` 被 Hugo 构建进 `public/`，
再由 peaceiris 发布）。**只要 gh-pages 上有 CNAME，GitHub Pages 就把 `xiaokeqing.github.io` 301 到自定义域**
—— 所以旧原型早就不"对外展示"了，它只是"还能被 301 到主站"。

**但任务要收的那件事仍然成立，而且理由比"演示数据外泄"更硬**：

```
gh-pages 上的任何文件都会同时存在于 https://xiaokeqing.github.io/<path>；
GitHub 为 *.github.io 签发的证书对该域有效 ⇒ 那个 CNAME 的 301【不是访问控制】。
也就是说：只要 gh-pages 还是"整站镜像"，谁都可以绕过 CNAME 约束去取镜像内容。
并且历史上（gh-pages 内容为旧原型时）确实存在过"可直接打开旧原型"的窗口。
```

⇒ 结论：**"停止把整站发布到 gh-pages"该做，且已做**；但"现在打开是 DEMO v5"这个现象早就不在了，
不要把它当成本次修复的成绩 ✓。

---

## 1. 改了什么（两个路径，逐条）

### 1.1 新增 `redirect-site/`（gh-pages 的**全部**内容，5 个文件）

| 文件 | 作用 |
|---|---|
| `index.html` | `<meta http-equiv="refresh" content="0; url=https://xiaokeqing.cn/">` + `<link rel="canonical" href="https://xiaokeqing.cn/">` + 一行可见的「本站已迁移」说明 + 手点链接兜底。无外部资源，样式内联 |
| `404.html` | 同样跳转 + canonical（gh-pages 是分支部署，未知路径会拿它兜底；实测 `/no-such-path-20261016` → HTTP 404 且 canonical 命中 1） |
| `robots.txt` | `User-agent: * / Disallow: /`（这条入口不再需要被索引） |
| `.nojekyll` | 阻止 GitHub Pages 用 Jekyll 处理该分支 |
| `README.md` | 给接手人：为什么只剩跳转页、**为什么故意不放 CNAME**、一条命令回滚 |

**刻意不放 `CNAME`**（这是本次唯一"反直觉"的决定，理由已实测）：
旧行为下 `https://xiaokeqing.github.io/` 的 301 目标是 **`http://xiaokeqing.cn/`**（明文那一跳），
再由 nginx 跳回 https。去掉自定义域绑定后，`github.io` 直接用 HTTPS 服务跳转页，
再 meta refresh 走 `https://` 到主站 —— 少一跳明文，且不再有"GitHub 域名被绑定"这层耦合。
**副作用必须知道**：自定义域解绑后 `xiaokeqing.github.io` 就真的只是 github.io；主站
`https://xiaokeqing.cn/`（CF 隧道 → srv2）与此**完全无关**，不受影响（改后实测主站仍 200 / 63811 B ✓）。

### 1.2 改 `.github/workflows/deploy.yml`

```
- 发布步骤：publish_dir: ./public  →  publish_dir: ./redirect-site     （唯一影响行为的改动）
- 保留【一步不减】：检出 → 装 Hugo 0.167 extended（校验 sha256）→ hugo 构建
                    → bash scripts/assert-build.sh public（真实站点 11 类断言）
- 新增一步（发布前）：「发布内容自检（gh-pages 只许是跳转页，失败即不发布）」
     ① 发布目录文件数必须 = 5（超标 ⇒ 说明整站又被拷回来了）
     ② 不得存在 CNAME
     ③ index.html / 404.html 必须都含 meta refresh 与 canonical → https://xiaokeqing.cn/
     ④ 对外服务的页面里 DEMO v5 命中必须 = 0
     ⑤ 不得引第三方资源（src=/link href= 指向站外）
  任一失败 ⇒ 该步退出码非 0 ⇒ 发布步骤不跑 ⇒ gh-pages 保持原样
- 清掉一段【已过期】的注释：原文件写着"断言 ⑥ 目前会红，必须先删 /api/public/latest 两处引用"。
  该断言早已改成白名单制且 latest 已在白名单内（scripts/assert-build.sh:118 ALLOWED 含 latest）
  ⇒ 这段注释是误导，删掉，免得下一个人照着"修"一个不存在的问题 ✓
- 头部注释补上"这一版改了什么/为什么"，并写明 publish_dir 换掉是解绑自定义域的来源（刻意的）
```

**门禁为什么没被削弱**：`assert-build.sh` 仍然断言 `public/`（真实站点产物），构建坏了、产物夹
`localhost`、缺 CNAME/sitemap、端点不在白名单……照样红。只是"红了以后发出去的是什么"从"整站"
变成了"跳转页"。新守卫是**额外加的一道**，不是替换（CI 实测第 5、6 两步分别 success ✓）。

---

## 2. CI 结果（**全绿**）

```
运行：Deploy Blog #124（run id 38769461765），event=push，head_sha=922eee2
页面：https://github.com/xiaokeqing/xiaokeqing.github.io/actions/runs/38769461765
结论：completed / success（2026-10-16 16:37:58 UTC 落实）

各步骤（全部 success）：
  1 Set up job                                          success
  2 检出源码                                             success
  3 安装 Hugo 0.167.0 extended（校验 sha256）             success
  4 构建（参数与本机 deploy.ps1 一致）                     success
  5 断言产物（失败即不发布）                               success   ← 真实站点 11 类断言全过
  6 发布内容自检（gh-pages 只许是跳转页，失败即不发布）      success   ← 本次新增的守卫
  7 发布到 gh-pages（只发跳转页，不发整站）                 success
  （Post/Complete job 亦 success）
权限/secret 未出现任何失败 ⇒ 无需报障 ✓
```

`gh-pages` 分支改后实测（`git ls-tree -r origin/gh-pages`）：

```
.nojekyll 404.html README.md index.html robots.txt      ← 只有 5 个文件
CNAME：已不存在 ✓（git cat-file -e origin/gh-pages:CNAME 失败）
```

---

## 3. 核验方法（从 srv1 出网，不依赖本机；原始输出留档 `E:\DeepSeek1\work\_ghpages\evidence\*.txt`）

```bash
ssh secagent-srv1 "curl -sI --max-time 25 https://xiaokeqing.github.io/ | head -6"
ssh secagent-srv1 "curl -s  --max-time 25 https://xiaokeqing.github.io/ | head -20"
ssh secagent-srv1 "curl -s  --max-time 25 https://xiaokeqing.github.io/ | grep -c 'DEMO v5'"
ssh secagent-srv1 "curl -s  --max-time 25 https://xiaokeqing.github.io/ | grep -c 'rel=\"canonical\" href=\"https://xiaokeqing.cn/\"'"
ssh secagent-srv1 "curl -sI --max-time 25 https://xiaokeqing.cn/ | head -3"   # 主站必须仍是 200
```

## 4. 核验数字

**（改前基线，2026-10-16 00:22 UTC+8，srv1）**

| 项 | 改前 |
|---|---|
| `https://xiaokeqing.github.io/` 状态码 | **301** → `http://xiaokeqing.cn/`（不是 200） |
| 响应体 | 162 B 的 nginx 301 页（**没有 HTML**，所以 canonical 无从命中） |
| 响应体里 `DEMO v5` 命中 | **0** |
| `gh-pages` 分支内容 | 整站镜像（Hugo 新版首页，含 CNAME） |

**（改后，2026-10-16 00:38 UTC+8 实测，srv1 出网）**

| 项 | 改后 | 判据 |
|---|---|---|
| 状态码 | **200** ✓ | `curl -s -o /dev/null -w '%{http_code}'` |
| canonical 命中 | **1** ✓ | `grep -c 'rel="canonical" href="https://xiaokeqing.cn/"'` |
| `DEMO v5` 命中 | **0** ✓ | `grep -c 'DEMO v5'` |
| meta refresh 命中 | **1** ✓ | `grep -c 'http-equiv="refresh" content="0; url=https://xiaokeqing.cn/"'` |
| 响应体大小 | 2409 B（我们的跳转页） | 改前是 162 B 的 nginx 301 页 |
| `location:` 头 | **无**（不再 301 到自定义域） | 实测 `curl -sI \| grep -i ^location` 无输出 ⇒ github.io 直接用 HTTPS 服务跳转页 ✓ |
| 未知路径 `/no-such-path-20261016` | HTTP **404** + canonical 命中 **1**（走 404.html）✓ | |
| 主站 `https://xiaokeqing.cn/` | **200**，63811 B ✓ 未受影响 | |

## 5. 回滚方法（一条命令）

```powershell
cd F:\7AAA\AI\blog; (Get-Content .github\workflows\deploy.yml) -replace 'publish_dir: \./redirect-site', 'publish_dir: ./public' | Set-Content .github\workflows\deploy.yml; git add .github/workflows/deploy.yml; git commit -m "revert(ghpages): 恢复整站发布到 gh-pages"; git push origin main
```

语义：`publish_dir` 改回 `./public` 再 push `main` ⇒ 下一次 CI 就把整站重新发到 `gh-pages`
（旧行为完整回来，包括 `CNAME` 重新生效、github.io 又被 301 到 `http://xiaokeqing.cn/`）。
`redirect-site/` 留着不碍事（不发布即无效），删掉也可以。

> 注意：回滚会把"整站镜像可被 `*.github.io/<path>` 直接取到"这条暴露面一起恢复 ✗，
> 非必要不要回滚。真正的回滚需求通常只是"我改坏了跳转页" ⇒ 那时用 `git revert 922eee2` 更好。

## 6. 影响面与边界

```
· 改的文件：.github/workflows/deploy.yml（改）、redirect-site/**（新增 5 个）、
            docs/旧GitHubPages收口-20261016.md（本文件）、docs/状态-AD-GHPages.md
· 未碰：layouts/**、static/**、scripts/**（含 scripts/voice/**）、_dev/**、SecAgent 源码、
        GitHub 仓库 Settings、任何 secret ✗✗
· 未碰主站链路：CF 隧道 / srv2 nginx / 证书 / DNS 一律零变更 ✓（改后主站 200 实测）
· 提交用路径限定：git commit -F msg -- <路径>，提交前核对 git diff --cached --name-only ✓
· 作业期间另有窗口在同一仓库持续推送（HEAD 从 45c67ab → acfed95 多次前移）⇒
  提交前 git fetch + git pull --rebase origin main（autostash），本次无冲突
```

## 7. 建议追加进 MasterPlan §11（**未代改活文档** ✗，留给规划侧/站主拍板追加）

```
| 10-16 | 站点线（第 ⑪ 条） | **收口旧 GitHub Pages**：deploy.yml 的 publish_dir 由 ./public 改为 ./redirect-site
（保留构建+断言一步不减，新增"发布内容自检"守卫），gh-pages 从"整站镜像"变成"meta refresh + canonical →
https://xiaokeqing.cn/ 的跳转页"，且刻意不放 CNAME ⇒ github.io 不再 301 到 http:// 自定义域，改由 HTTPS 直服跳转页；
顺带清掉一段"断言 ⑥ 会红"的过期注释。**订正**：任务书说的"打开 github.io 还是 DEMO v5"实测已不复现
（改前就是 301 → http://xiaokeqing.cn/、响应体 162 B、DEMO v5 命中 0）；真正的暴露面是
`*.github.io/<path>` 可绕过 CNAME 的 301 直取镜像内容（301 不是访问控制） | 提交 922eee2 ｜ CI #124 全绿
｜ srv1 实测：200 / canonical 命中 1 / DEMO v5 命中 0 / 主站 200 | gh-pages 分支内容 5 个文件；
主站与 CF 隧道零变更 |
```

## 8. 给下一个人的三个坑

```
① 别再把整站 publish 到 gh-pages —— 会重新打开"*.github.io/<path> 可直接取内容"的通道（§0）
② 别往 redirect-site 里放 CNAME —— 会把自定义域绑回 gh-pages，301 目标退回 http://（§1.1）
③ scripts/assert-build.sh 盯的是 public/，它【看不见】redirect-site/ —— 所以才在 workflow 里
   另加了一道"发布内容自检"；改发布内容时两处都要想一遍
```
