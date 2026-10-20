---
title: "静态 IP 配置与路由转发"
date: 2026-10-19T14:00:00+08:00
draft: false
categories: ["linux系统"]
tags: ["Linux", "网络", "路由", "课程笔记"]
summary: "CentOS 7 与 Kali 在 NAT 模式下的静态地址写法、DNS 设定，以及把主机配置成路由转发节点的步骤（截图为主）。"
description: "CentOS 7 与 Kali 在 NAT 模式下的静态地址写法、DNS 设定，以及把主机配置成路由转发节点的步骤（截图为主）。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`静态IP配置与路由转发.pdf`，共 15 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

centos7 和 kali都用nat模式

![静态 IP 配置与路由转发 示意图 1](/images/linux-notes/static-ip-routing/img-01.webp)

背着编辑配置文件，实现dhcp自动获取

![静态 IP 配置与路由转发 示意图 2](/images/linux-notes/static-ip-routing/img-02.webp)

尝试静态配置ip

![静态 IP 配置与路由转发 示意图 3](/images/linux-notes/static-ip-routing/img-03.webp)

kali操作系统静态配置ip地址

![静态 IP 配置与路由转发 示意图 4](/images/linux-notes/static-ip-routing/img-04.webp)

dns设定

![静态 IP 配置与路由转发 示意图 5](/images/linux-notes/static-ip-routing/img-05.webp)

linux系统中的路由转发如何实现拓扑如下

![静态 IP 配置与路由转发 示意图 6](/images/linux-notes/static-ip-routing/img-06.webp)

实验之前先确定一下自己虚拟机是否存在vment2和vmnet3

![静态 IP 配置与路由转发 示意图 7](/images/linux-notes/static-ip-routing/img-07.webp)

手动添加vmnet2 和 3

![静态 IP 配置与路由转发 示意图 8](/images/linux-notes/static-ip-routing/img-08.webp)

![静态 IP 配置与路由转发 示意图 9](/images/linux-notes/static-ip-routing/img-09.webp)

选择添加

![静态 IP 配置与路由转发 示意图 10](/images/linux-notes/static-ip-routing/img-10.webp)

![静态 IP 配置与路由转发 示意图 11](/images/linux-notes/static-ip-routing/img-11.webp)

以相同的配置建立vmnet3

![静态 IP 配置与路由转发 示意图 12](/images/linux-notes/static-ip-routing/img-12.webp)

1、针对客户机win主机确认连接的交换机为vmnet2同时配置ip

![静态 IP 配置与路由转发 示意图 13](/images/linux-notes/static-ip-routing/img-13.webp)

2、建立克隆虚拟机centos7 连接vmnet3同时配置ip地址

![静态 IP 配置与路由转发 示意图 14](/images/linux-notes/static-ip-routing/img-14.webp)

![静态 IP 配置与路由转发 示意图 15](/images/linux-notes/static-ip-routing/img-15.webp)

设定了ip和网关

3、为中间的网关服务器配置ip地址和新网卡

![静态 IP 配置与路由转发 示意图 16](/images/linux-notes/static-ip-routing/img-16.webp)

配置文件修改配置完成后确认

![静态 IP 配置与路由转发 示意图 17](/images/linux-notes/static-ip-routing/img-17.webp)

确定一下对应关系

![静态 IP 配置与路由转发 示意图 18](/images/linux-notes/static-ip-routing/img-18.webp)

4、验证 win客户机 192.168.2.1  ping通172.16.2.1 win验证ping网关

![静态 IP 配置与路由转发 示意图 19](/images/linux-notes/static-ip-routing/img-19.webp)

网关确认路由表分析数据如何返回

![静态 IP 配置与路由转发 示意图 20](/images/linux-notes/static-ip-routing/img-20.webp)

验证

![静态 IP 配置与路由转发 示意图 21](/images/linux-notes/static-ip-routing/img-21.webp)

克隆机确认

![静态 IP 配置与路由转发 示意图 22](/images/linux-notes/static-ip-routing/img-22.webp)

## 实验的核心路由转发开启

![静态 IP 配置与路由转发 示意图 23](/images/linux-notes/static-ip-routing/img-23.webp)

windows验证

验证克隆linux

![静态 IP 配置与路由转发 示意图 24](/images/linux-notes/static-ip-routing/img-24.webp)
