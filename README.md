# gh-pages 的发布前自检（被 .github/workflows/deploy.yml 调用）

这个目录是**发布到 `gh-pages` 分支的全部内容**。它曾经是 Hugo 构建产物（`public/`）——
整套博客前端因此能被 `https://xiaokeqing.github.io/` 访问到，其中包括带
「DEMO v5 · 数字均为演示数据」字样的旧原型。演示数据挂在对外域名上，对面试展示是硬伤。

现在：CI 照旧构建 + 跑 `scripts/assert-build.sh`（构建/门禁一点没减），
但 `publish_dir` 指向这里，`gh-pages` 上只剩一个跳转页。

## 为什么这里**没有** `CNAME`

`CNAME` 会把 `xiaokeqing.cn` 这个自定义域绑到 `gh-pages` 上，于是 GitHub Pages 会把
`https://xiaokeqing.github.io/` 301 到自定义域 —— 但**用的是 `http://` 而不是 `https://`**
（本机实测：`location: http://xiaokeqing.cn/`），平白多一跳明文再靠 nginx 跳回来。
去掉 `CNAME` 后 `github.io` 就干净地只服务这个跳转页：HTTPS 直达 + meta refresh 到
`https://xiaokeqing.cn/`。

**副作用（必须知道）**：自定义域解绑后，`xiaokeqing.github.io` 就真的"只是 github.io"了。
主站 `https://xiaokeqing.cn/`（CF 隧道 → srv2）与此**完全无关**，不受影响。

## 回滚

`publish_dir` 一行改回 `./public` 再 push 到 `main`，即可恢复"整站发布到 gh-pages"的旧行为。
一条命令的完整写法见 `docs/旧GitHubPages收口-20261016.md`。
