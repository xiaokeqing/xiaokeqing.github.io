---
title: "CVE 每日速递 · 每日快照（不是实时）"
description: "每天一张 CVE 快照：CISA KEV 今日新增（影响什么 / 漏洞 / 在野状态 / 我要做什么）、最近 7 天 KEV 表、NVD 当日 CVSSv3 HIGH。只照抄官方字段，缺字段写「官方未给出」；某个源读不到就整块写「读不到（原因）—— 不补数」，绝不把读不到渲染成 0 条。"
layout: "list"
hideDate: true
---

<!--
  这一页的正文全部写在 layouts/tools/cve/list.html 里（手写整页，独立于 baseof.html），
  这里的 _index.md 只负责把 /tools/cve/ 这个 section 注册出来、给出 title / description。

  数据不是页面自己抓的：构建前由 scripts/cve/fetch-cve.py 抓一次，落到
  static/data/cve-digest.json → 产物 /data/cve-digest.json；页面打开时 fetch 它
  （同域静态文件，不碰任何第三方接口、不跨域）。

  为什么没有写 type：
    · 不加 type 时 .Type = "tools"，layout 查找会先命中 layouts/tools/cve/list.html；
    · ★也不要写 type（写错会 404 或退回骨架页）：本站其它 section 页（/ip/、/passwords/）
      是把 type 写成与 section 同名的目录来做布局匹配的，这里靠路径前缀就够了。
    · 另外 head-meta.html 只对 `in (slice "alerts" "status" "api")` 的 .Type 预取
      /api/public/home.js —— 本页是纯静态文件 + 一次同域 fetch，不该白背一页 home 聚合。

  数字口径（改数只改抓取器，不改页面）：kevNew = dateAdded 等于快照目标日；
  kevRecent7d = 目标日往前 7 天（含当天）、倒序、最多 40 条；nvdHigh = 当日窗口内
  cvssV3Severity=HIGH 的 1 页（≤50 条）；shortDescription 抓取时截到 240 字符。
-->
