---
title: "紫队演练 · 我打的攻击，我的平台能看见吗"
description: "紫队自测设计稿：在自己靶场里发起三条可测攻击（SSH 爆破 / 端口扫描 / Web 探测），每条指定它应当命中的规则（Suricata SID 1000101–1000108、Wazuh 100400–100402），给出 eve.json 与 alerts.json 的 grep 验证方法。规则未部署，所以「实测命中」一栏统一写「未验证」——grep 返回 0 只证明没加载，不证明没命中。"
type: "purpleteam"
layout: "list"
hideDate: true
---

<!--
  这一页的正文全部写在 layouts/purpleteam/list.html 里（手写整页，独立于 baseof.html），
  这里的 _index.md 只负责把 /purpleteam/ 这个 section 注册出来、给出 title / description。

  为什么写 type（同 content/redteam/_index.md 的理由）：
  · type 决定 Hugo 的 layout 查找路径 layouts/<type>/list.html —— 与 section 同名，
    所以加了也照旧命中同一个模板，不会 404；
  · 真正的用处是让 .Type == "purpleteam"：layouts/partials/xk-demo/head-meta.html 用
    `in (slice "alerts" "status" "api") .Type` 决定要不要给 /api/public/home.js 发 preload，
    本页一次都不打 demo API，页脚也不取 home 聚合，所以不能落到默认值之外的那几个 type 里。
  字段名必须是 description（Hugo 映射到 .Description）；写 desc 不会进 <meta name="description">。
-->
