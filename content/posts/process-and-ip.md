---
title: "开机流程与进程管理：systemd、ps 与 top"
date: 2026-10-19T16:00:00+08:00
draft: false
categories: ["课程笔记", "linux系统"]
tags: ["Linux", "systemd", "进程", "课程笔记"]
summary: "BIOS→GRUB→内核→systemd 的开机链条、systemd 的工作模式与 systemctl 控制项、ps aux 与 top 的实时观察与排序，以及进程启动状态调整。"
description: "BIOS→GRUB→内核→systemd 的开机链条、systemd 的工作模式与 systemctl 控制项、ps aux 与 top 的实时观察与排序，以及进程启动状态调整。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`进程管理与IP配置.pdf`，共 5 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

进程  程序程序 未启动之前叫程序启动之后 会在内存中加载 cpu运行，此时其状态称为进程bios-> 硬盘 -> 加载分区表 446 主引导软件 grub读配置文件 -> 加载内核 和驱动-> 启动第一个进程确认系统第一个启动的进程 systemd systemd 会管理启动其他子进程  决定开机以后默认进入哪个工作模式

![开机流程与进程管理 示意图 1](/images/linux-notes/process-and-ip/img-01.png)

如何查看后台进程ps aux

![开机流程与进程管理 示意图 2](/images/linux-notes/process-and-ip/img-02.png)

命令常用选项了解服务启动状态

![开机流程与进程管理 示意图 3](/images/linux-notes/process-and-ip/img-03.png)

调整了进程的启动状态

![开机流程与进程管理 示意图 4](/images/linux-notes/process-and-ip/img-04.png)

## 对于进程管理与查看top

top工具可以实时观察进程变化快捷键 q 退出m 显示不同方式的内存占用M 按照内存占用比排序P 按照cpu占用比排序k 可以杀死选定的进程  可以选择使用哪个编号的kill界面介绍

![开机流程与进程管理 示意图 5](/images/linux-notes/process-and-ip/img-05.png)

使用脚本测试

![开机流程与进程管理 示意图 6](/images/linux-notes/process-and-ip/img-06.png)

关于kill命令的应用学习为虚拟机配置IP地址kali虚拟机   centos虚拟通过配置好的ip地址 实现相互ping通 实验要求两台主机同时都使用nat模式确认kali虚拟机ip地址

![开机流程与进程管理 示意图 7](/images/linux-notes/process-and-ip/img-07.png)

手动为centos7 配置ip地址

![开机流程与进程管理 示意图 8](/images/linux-notes/process-and-ip/img-08.png)

配置ip并验证与kali联通

![开机流程与进程管理 示意图 9](/images/linux-notes/process-and-ip/img-09.png)

确认kali的网关

centos7配置网关

![开机流程与进程管理 示意图 10](/images/linux-notes/process-and-ip/img-10.png)

查看kali的dns

![开机流程与进程管理 示意图 11](/images/linux-notes/process-and-ip/img-11.png)

设定centos7的dns
