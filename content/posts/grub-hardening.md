---
title: "GRUB 引导菜单加固：给启动项加密码"
date: 2026-10-19T13:00:00+08:00
draft: false
categories: ["课程笔记", "linux系统"]
tags: ["Linux", "GRUB", "加固", "课程笔记"]
summary: "grub.cfg 与 /etc/grub.d/10_linux 的生成关系、为什么改脚本而不是改 grub.cfg、用 grub2-setpassword 生成密码并重建配置、重启验证。"
description: "grub.cfg 与 /etc/grub.d/10_linux 的生成关系、为什么改脚本而不是改 grub.cfg、用 grub2-setpassword 生成密码并重建配置、重启验证。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`grub引导菜单如何加固.pdf`，共 2 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

grub引导菜单配置文件 /boot/grub2/grub.cfg  配置文件，但是不能修改

![GRUB 引导菜单加固 示意图 1](/images/linux-notes/grub-hardening/img-01.png)

查看对应文件内容

![GRUB 引导菜单加固 示意图 2](/images/linux-notes/grub-hardening/img-02.png)

配置就脚本目录分析

![GRUB 引导菜单加固 示意图 3](/images/linux-notes/grub-hardening/img-03.png)

根据源配置文件分析为何要修改10_linux需要首先生成密码

![GRUB 引导菜单加固 示意图 4](/images/linux-notes/grub-hardening/img-04.png)

编辑10_linux添加密码

![GRUB 引导菜单加固 示意图 5](/images/linux-notes/grub-hardening/img-05.png)

生成配置文件

![GRUB 引导菜单加固 示意图 6](/images/linux-notes/grub-hardening/img-06.png)

重启后验证

![GRUB 引导菜单加固 示意图 7](/images/linux-notes/grub-hardening/img-07.png)
