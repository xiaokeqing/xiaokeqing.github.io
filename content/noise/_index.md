---
title: "告警噪音指数 · 告警里有多少是噪声"
description: "把「告警里有多少条其实不是攻击」量化出来：窗口 2026-10-11~10-18 的 293,482 条 alert 里有 278,405 条（94.9%）是腾讯云 agent 每 5 分钟一次的心跳（sid 2013031，10.0.0.10 → 169.254.0.4:80 POST /ca_report.cgi），剩下 5.1% 才是信号。按规则拆开看占比与归类，并写清检测缺口：规则 100110 命中 0 不代表没攻击。数字来自 srv2 的 eve.json 分析，读不到就写「读不到（原因）—— 不补数」。"
layout: "list"
hideDate: true
---

<!--
  这一页的正文全部写在 layouts/noise/list.html 里（手写整页，独立于 baseof.html），
  这里的 _index.md 只负责把 /noise/ 这个 section 注册出来、给出 title / description
  （Hugo 只把 description 映射到 .Description，写 desc 不会进 <meta name="description">）。

  为什么没有写 type（照 content/tools/cve/_index.md 的同一写法）：
    · 不加 type 时 .Type = "noise"，layout 查找直接命中 layouts/noise/list.html；
    · ★不要写 type（写错会 404 或退回骨架页）：本站其它 section 页（/ip/、/passwords/）
      是把 type 写成与 section 同名的目录来做布局匹配的，这里靠目录同名就够了。
    · 另外 layouts/partials/xk-demo/head-meta.html 只对 `in (slice "alerts" "status" "api")`
      的 .Type 预取 /api/public/home.js —— 本页是纯静态文件 + 一次同域 fetch，
      不该白背一页 home 聚合。

  数字口径（改数只改生成器，不改页面）：全部来自 static/data/noise-index.json，
  由 scripts/noise/build-noise.py 生成（--from-written = 已核实摘要；--in = 现场数 eve.json）。
  占比一律由 条数 ÷ alert 总数 现算 —— 页面摆着分子分母，谁都能自己除一遍。
-->
