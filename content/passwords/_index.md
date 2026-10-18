---
title: "高频弱口令 Top 100 · 只给结构，不给明文"
description: "我们自己蜜罐真实收到的口令尝试：6 位纯数字 2,260 次（占该源 6,931 次成功登录的 32.6%）、root 963 次（13.9%）、某 2.5 小时窗口里前 8 个口令合计 1,073 次。只展示结构类别、长度桶与次数，口令原文一律「已脱敏·只给结构」；填不满的 92 个槽位明写不补数。"
type: "passwords"
layout: "list"
hideDate: true
---

<!--
  这一页的正文全部写在 layouts/passwords/list.html 里（手写整页，独立于 baseof.html），
  这里的 _index.md 只负责把 /passwords/ 这个 section 注册出来、给出 title / description
  （Hugo 只把 description 映射到 .Description，写 desc 不会进 <meta name="description">）。

  为什么写 type / layout（对照 content/ip/_index.md 的同一写法）：
   · type → Hugo 的 layout 查找路径 layouts/<type>/list.html，与 section 同名，加了照旧命中；
   · 真正的用处是 .Type 参与外壳判定：layouts/partials/xk-demo/head-meta.html 只对
     `in (slice "alerts" "status" "api")` 的 .Type 预取 /api/public/home.js。本页是纯静态页，
     浏览器里一次请求都不发，所以 type 必须写成 passwords 且不在那份 slice 里。

  这一页刻意**不**往 dock / 菜单里加条目（hugo.toml 的 6 项导航是站主的硬约束，
  dock 那几行由 layouts/partials/xk-demo/shell-chrome.html 固定），入口先从 /what/ 与
  /posts/ 的正文链过去，要不要升成一级入口由站主定。

  数字口径见 layouts/passwords/list.html 页尾「每一行数字的出处」：
  窗口 A = content/posts/ssh-bruteforce-163.5.210.194.md（第 59 行），
  窗口 B = docs/样本分析-20261018.md（第 69 行），结构类别定义 = docs/日报-20261018.md §4.4。
-->
