---
title: "你的密码在攻击者字典里吗 · k-匿名自查"
description: "在浏览器本地算 SHA-256，只把前 5 位发出去问一句：这个前缀下，攻击者在我们蜜罐里试过的口令里有没有落在这的。口令原文不离开页面；命中只说明「这个口令被真实攻击者试过」，不说明是谁的；不在字典里也不代表安全。读不到就写「读不到（原因）—— 不补数」。"
layout: "list"
hideDate: true
---

<!--
  这一页的正文全部写在 layouts/tools/password/list.html 里（手写整页，独立于 baseof.html），
  这里的 _index.md 只负责把 /tools/password/ 这个 section 注册出来、给出 title / description。

  页面逻辑不在模板里：全部在 assets/js/password-check.js（外链，走 Hugo Pipes
  minify + fingerprint）。HTML 里只有两个字面 script 标签：/js/xk-saver.js 与本页外链脚本；
  外壳那 2 个由 partials/xk-demo/shell-script.html 提供。

  数据只有一个来源：GET /api/public/password?p=<sha256 前 5 位 hex>（后端
  PublicApiController#password + PasswordDictionaryService，索引文件
  data/password-hashes.json 由 scripts/password-dict-build.py 离线生成）。
  索引里只有「sha256 + 次数 + 最后出现时间」，没有任何明文字符。

  为什么没有写 type：
    · 不加 type 时 .Type = "tools"，layout 查找会先命中 layouts/tools/password/list.html；
    · ★也不要写 type（写错会 404 或退回骨架页）：本站其它 section 页（/ip/、/passwords/）
      是把 type 写成与 section 同名的目录来做布局匹配的，这里靠路径前缀就够了；
    · 另外 head-meta.html 只对 `in (slice "alerts" "status" "api")` 的 .Type 预取
      /api/public/home.js —— 本页是一次按需 GET，不该白背一页 home 聚合。

  文案铁律（改文案前先读）：
    · 不说"你的密码已被泄露"：蜜罐里没有真实账号，只能说「这个口令被攻击者尝试过」；
    · 「不在字典里」≠ 安全：数据集只有自己蜜罐 24h 内的真实爆破口令 + 公开弱口令榜；
    · 读不到（索引没生成 / 格式坏 / 429 / 超时）一律写「读不到（原因）—— 不补数」，
      绝不渲染成"没命中"。
-->
