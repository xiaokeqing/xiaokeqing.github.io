---
title: "样本投递箱（不构建成页面）"
build:
  render: never
  list: never
cascade:
  - target:
      path: /redteam/submissions/**
    build:
      render: never
      list: never
      publishResources: false
---

<!--
  这个目录是**数据目录**，不是页面目录（2026-10-18 新增）。

  为什么要有这个文件：
  · 投递箱 `content/redteam/submissions/` 每个样本一个 .md（front matter 见
    /redteam/ 页面的「提交样本」区块）。这些 .md 的**正文就是攻击载荷原文**，
    绝不能被 Hugo 渲染成 /redteam/submissions/<slug>/ 这样的页面 —— 那等于
    把载荷原文连同作者字段一起挂到公网上。
  · 但 Hugo 只要看到 content/ 下的目录就会生成 section 页面、每个 .md 再生成
    detail 页面。所以这里用 `build.render: never` + `build.list: never` 把它们
    从产物里彻底摘掉：section 页不渲染（本文件），子页面靠下面的 cascade 一并
    不渲染（子文件自己的 front matter 不用写 build，投递格式保持干净）。
  · 断言侧钉死这一条：scripts/assert-build.sh 的 ⑰ 检查产物里**不存在**
    public/redteam/submissions/。写回榜单的只有 80 字摘要 + 判定，
    正文留在仓库里，由 scripts/redteam/score-submissions.py 离线读。
-->
