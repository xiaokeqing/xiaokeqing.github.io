---
title: "蜜罐会话"
description: "srv2 上 Cowrie 蜜罐最近 7 天的真实 SSH 会话时间线：连接、客户端指纹、登录与断开。这站没有开 ttylog，命令输入为 0，页面如实标注，不伪造终端录像；来源地址遮成 a.b.c.x。"
layout: "list"
data-xk-ssr: session
---

这一页只回放 Cowrie 真实记录下来的会话。当前实例没有开启 `output_ttylog`，
`cowrie.command.input` 也是 0 条，所以没有终端字节流可还原；每条会话展示的是
连接、客户端指纹、登录、断开的时间线，不冒充"终端录像"。
