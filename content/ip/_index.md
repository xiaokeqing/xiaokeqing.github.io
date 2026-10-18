---
title: "这个 IP 干过什么 · 个人版 AbuseIPDB"
description: "输入一个 IPv4，把本机告警 / 蜜罐 / 处置留痕里跟它有关的记录摊开：首末时间、事件数、行为类型、碰过的蜜罐端口、口令结构、GeoIP、封禁状态。取不到就写「读不到（原因）—— 不补数」，不按网段或 ASN 扩张，不公开任何口令原文。"
type: "ip"
layout: "list"
hideDate: true
---

<!--
  这一页的正文全部写在 layouts/ip/list.html 里（手写整页，独立于 baseof.html），
  这里的 _index.md 只负责把 /ip/ 这个 section 注册出来、给出 title / description
  （Hugo 只把 description 映射到 .Description，写 desc 不会进 <meta name="description">）。

  为什么写 type / layout（对照 content/redteam/_index.md 的同一写法）：
   · type → Hugo 的 layout 查找路径 layouts/<type>/list.html —— 与 section 同名，
     加了也照旧命中同一个模板；
   · 真正的用处是 .Type == "ip" 参与外壳判定：layouts/partials/xk-demo/head-meta.html
     只对 `in (slice "alerts" "status" "api")` 的 .Type 预取 /api/public/home.js。
     本页查的是 /api/public/ip（按需一次 GET），不该白背一份 home 聚合预取，
     所以 type 必须写成 ip 且不在那份 slice 里。
-->
