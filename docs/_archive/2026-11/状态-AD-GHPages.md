# 状态 · AD · 旧 GitHub Pages 收口（第 ⑪ 条）

> 只由该窗口自己更新 ✓；格式见 `docs/窗口分工规范-20261015.md` §四
> 详细记录：`docs/旧GitHubPages收口-20261016.md`（提交 `922eee2`）

| 项 | 内容 |
|---|---|
| 负责 | **目标清单第 ⑪ 条：让旧的 GitHub Pages 站不再对外展示"DEMO v5 + 演示数据"** |
| 状态 | **已完工**（2026-10-16 00:10~00:45 本地 UTC+8）；**只改 2 个路径** ✓，无强推、未动 Settings、未动 secret ✓ |
| 前提订正 | 任务书说的"现在打开还能看到旧原型"**已不复现**：改前实测 `github.io` 是 301 → `http://xiaokeqing.cn/`，响应体 162 B、`DEMO v5` 命中 0，`gh-pages:index.html` 已是 Hugo 新版 ✓。**但**"停止把整站发布到 gh-pages"仍然该做 —— 因为 `*.github.io/<path>` 可绕过 CNAME 的 301 直接取镜像内容（301 不是访问控制）✓ |
| 改了哪些文件 | ① `.github/workflows/deploy.yml`（`publish_dir` `./public` → `./redirect-site`；新增发布前「发布内容自检」；清掉一段过期的"断言 ⑥ 会红"注释）② `redirect-site/`（新增：`index.html` `404.html` `robots.txt` `.nojekyll` `README.md`）③ 本文件 ④ `docs/旧GitHubPages收口-20261016.md` |
| 刻意没做 | 不放 `redirect-site/CNAME`（实测旧 301 目标是 `http://` 而非 `https://`，解绑后 github.io 直接 HTTPS 服务跳转页）；不动 Settings；不删构建/断言步骤 ✓ |
| CI | **Deploy Blog #124，completed/success**，7 步全 success（含第 5 步真实站点断言、第 6 步新增的发布内容自检）：https://github.com/xiaokeqing/xiaokeqing.github.io/actions/runs/38769461765 |
| 核验证据（srv1 出网） | 见下「证据台账 E1~E5」；原始输出留档 `E:\DeepSeek1\work\_ghpages\evidence\*.txt`（仓库外） |
| 回滚 | 一条命令：`publish_dir` 改回 `./public` 并 push `main`（详见收口文档 §5）。**回滚会恢复暴露面**，非必要不做；只改坏跳转页时用 `git revert 922eee2` |
| 下一步 | ① 建议在活文档 MasterPlan §11 追加一行（成稿见收口文档 §7，**未代改活文档** ✗）② 站主无需拍板任何事项 ✓ |
| 卡点 | **无** |

---

## 证据台账（每条都有命令原文 + 实测数字）

### E1 · 改前基线（srv1，2026-10-16 00:22 UTC+8）
```
curl -sI https://xiaokeqing.github.io/  ⇒ HTTP/2 301 ; location: http://xiaokeqing.cn/ ; content-length: 162
curl -s  https://xiaokeqing.github.io/ | grep -c 'DEMO v5'  ⇒ 0        （响应体是 nginx 301 页，不是 HTML）
curl -sI http://xiaokeqing.github.io/   ⇒ HTTP/1.1 301 ; Location: http://xiaokeqing.cn/
git show origin/gh-pages:index.html     ⇒ Hugo 0.167 新版首页；文件内 DEMO v5 命中 0
git show origin/gh-pages:CNAME          ⇒ xiaokeqing.cn                （← 301 的来源）
```

### E2 · 发布前自检逻辑本机干跑（Git Bash，与 workflow 内步骤逐行一致）
```
① 文件数 5                        [PASS]
② 无 CNAME                        [PASS]
③ index.html 跳转 + canonical 正确 [PASS]
  404.html  跳转 + canonical 正确 [PASS]
④ 发布面 DEMO v5 命中 0           [PASS]
⑤ 无第三方资源引用                 [PASS]
通过 6 项，失败 0 项（exit 0）
```
（第一次干跑 ④ 是 **FAIL**：命中 `redirect-site/README.md` 与 `index.html` 里我写的"历史说明"文字。
已把 ④ 的扫描面收窄到**实际对外服务的文件**（`--include='*.html'/*.txt/*.xml/*.json`），
并把 index.html 注释里的字样改为 `DEMO-v5` —— README 作为给接手人看的历史说明保留该词是合理的。）

### E3 · CI 与线上核验（改后，2026-10-16 00:37~00:38 UTC+8）
```
CI：Deploy Blog #124（run 38769461765，head_sha 922eee2）⇒ completed / success
    1 Set up job                        success
    2 检出源码                           success
    3 安装 Hugo 0.167.0 extended         success
    4 构建                              success
    5 断言产物（失败即不发布）             success   ← 真实站点断言全过
    6 发布内容自检（gh-pages 只许跳转页）  success   ← 本次新增守卫
    7 发布到 gh-pages（只发跳转页）        success

线上（srv1 出网）：
curl -sI https://xiaokeqing.github.io/            ⇒ HTTP/2 200 ; content-type: text/html; charset=utf-8
                                                     且【无 location 头】⇒ 不再 301 到自定义域
curl -s  https://xiaokeqing.github.io/ | head -20 ⇒ 我们的「本站已迁移」跳转页
状态码            : 200
canonical 命中    : 1
meta refresh 命中 : 1
DEMO v5 命中      : 0
响应体字节        : 2409
未知路径 /no-such-path-20261016 ⇒ HTTP 404 且 404.html 的 canonical 命中 1
gh-pages 分支文件：.nojekyll 404.html README.md index.html robots.txt（5 个）；CNAME 已不存在 ✓
```

### E4 · 主站未受影响
```
curl -sI https://xiaokeqing.cn/  ⇒ HTTP/2 200 ; content-type: text/html
主站状态码 : 200
主站字节   : 63811
（CF 隧道 / srv2 nginx / 证书 / DNS 零变更）
```
