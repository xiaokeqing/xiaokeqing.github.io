---
title: "红队攻防榜 · 27 条用例，4 条还没挡住"
description: "红队评测的真实数字：27 条离线用例，17 条攻击用例实跑拦住 13 条、绕过 4 条，8 条良性用例 0 误拦。样本集写死在 RedTeamEvalService 里，历史 run 落在 data/eval-runs.json；/api/eval/* 需登录且没对公网开 CORS，所以这一页的实时探测结果是「读不到」——不补数。"
type: "redteam"
layout: "list"
hideDate: true
---

<!--
  这一页的正文全部写在 layouts/redteam/list.html 里（手写整页，独立于 baseof.html），
  这里的 _index.md 只负责把 /redteam/ 这个 section 注册出来、给出 title / description。

  为什么写 type（/api/ 那页的注释说别写，这里有不同理由）：
  · type 决定 Hugo 的 layout 查找路径 layouts/<type>/list.html —— 与 section 同名，
    所以加了也照旧命中同一个模板，不会 404（对照 content/projects/_index.md 的同一写法）；
  · 真正的用处是让 .Type == "redteam"：layouts/partials/xk-demo/head-meta.html 用
    `in (slice "alerts" "status" "api") .Type` 决定要不要给 /api/public/home.js 发 preload。
    本页探测的是 /api/eval/*、不取 home 聚合，.Type 若还是空/默认就会白下一份 1MB 级预取。
  字段名必须是 description（Hugo 映射到 .Description）；写 desc 不会进 <meta name="description">。
-->
