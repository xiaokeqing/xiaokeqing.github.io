---
title: "路由原理与静态路由"
date: 2026-10-20T13:00:00+08:00
draft: false
categories: ["网络基础"]
tags: ["网络基础", "路由", "静态路由"]
summary: "路由的基本概念：路由表与路由来源、静态路由与动态路由的区别、路由协议分类与常见算法。"
description: "路由的基本概念：路由表与路由来源、静态路由与动态路由的区别、路由协议分类与常见算法。"
ShowToc: true
---

> 来源：网络基础课程讲义（`路由原理与静态路由.pptx`）。由 PDF/PPTX/DOCX 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 课件：路由原理与静态路由

《华为路由器技术与应用》

### 路由 · 原理

### 什么是路由

路由是指导IP报文发送的路径信息

![课件：路由原理与静态路由 示意图 1](/images/network-notes/routing-static/all/img-01.webp)

目标网络N

其它网络

![课件：路由原理与静态路由 示意图 2](/images/network-notes/routing-static/all/img-02.webp)

E0/0

S0/0

E0/1

RTA

RTB

RTC

### 路由原理

.1

E0

10.1.2.0/24

![课件：路由原理与静态路由 示意图 7](/images/network-notes/routing-static/all/img-03.webp)

10.2.1.0/24

E1

.2

![课件：路由原理与静态路由 示意图 10](/images/network-notes/routing-static/all/img-04.webp)

10.3.1.0

10.4.1.0

| 目标网络 | 下一跳 | 出接口 |
| --- | --- | --- |
| 10.1.2.0 | 10.1.2.1 | E0 |
| 10.2.1.0 | 10.1.2.2 | E0 |
| 10.3.1.0 | 10.3.1.1 | E1 |
| 10.4.1.0 | 10.1.2.2 | E0 |

| 目标网络 | 下一跳 | 出接口 |
| --- | --- | --- |
| 10.1.2.0 | 10.1.2.2 | E0 |
| 10.2.1.0 | 10.1.2.1 | E0 |
| 10.3.1.0 | 10.1.2.1 | E0 |
| 10.4.1.0 | 10.2.1.2 | E1 |

| 目标网络 | 下一跳 | 出接口 |
| --- | --- | --- |
| 10.1.2.0 | 10.2.1.2 | E0 |
| 10.2.1.1 | 10.2.1.2 | E0 |
| 10.3.1.0 | 10.2.1.1 | E0 |
| 10.4.1.0 | 10.4.1.1 | E1 |

### 路由器关键功能

检查数据包的目的地
确定信息源
发现可能的路由
选择最佳路由
验证和维护路由信息

### 建立路由表

路由来源 目标网络 出接口

Direct 10.1.1.0 E0/0
Static 192.168.1.0 E1/0
OSPF 192.168.2.0 E1/0

E1/0

![课件：路由原理与静态路由 示意图 17](/images/network-notes/routing-static/all/img-05.webp)

10.1.1.0

192.168.2.0

192.168.1.0

### 路由的来源—链路层发现的路由

直连路由

[RTB]display ip routing-table
Routing Tables: Public
Destinations : 8 Routes : 8
Destination/Mask Proto Pre Cost NextHop Interface
10.1.1.0/30 Direct 0 0 10.1.1.1 Serial0/0/0
10.1.1.1/32 Direct 0 0 127.0.0.1 InLoopBack0
……
10.1.2.1/32 Direct 0 0 127.0.0.1 InLoopBack0
10.1.2.2/32 Direct 0 0 10.1.2.2 Serial0/0/1
127.0.0.0/8 Direct 0 0 127.0.0.1 InLoopBack0
127.0.0.1/32 Direct 0 0 127.0.0.1 InLoopBack0

10.1.1.0/30

### 静态路由

  - [RTA] display ip routing-table
  - Routing Tables: Public
  - Destinations : 8 Routes : 8
  - Destination/Mask Proto Pre Cost NextHop Interface
  - 2.2.2.2/32 Static 60 0 10.1.1.2 Serial0
  - 10.1.1.0/30 Direct 0 0 10.1.1.1 Serial0
  - 10.1.1.1/32 Direct 0 0 127.0.0.1 InLoopBack0
  - 10.1.1.2/32 Direct 0 0 10.1.1.2 Serial0
  - 127.0.0.0/8 Direct 0 0 127.0.0.1 InLoopBack0
  - 127.0.0.1/32 Direct 0 0 127.0.0.1 InLoopBack0

2.2.2.2/32

配置到2.2.2.2/32网络的静态路由

### 动态路由

[RTB]display ip routing-table
Routing Tables: Public
Destinations : 10 Routes : 10
Destination/Mask Proto Pre Cost NextHop Interface
10.1.1.0/30 Direct 0 0 10.1.1.2 Serial0/0/0
10.1.1.1/32 Direct 0 0 10.1.1.1 Serial0/0/0
127.0.0.1/32 Direct 0 0 127.0.0.1 InLoopBack0
172.16.1.1/32 OSPF 10 1562 10.1.2.2 Serial0/0/1
192.168.2.0/24 RIP 100 1 10.1.1.1 Serial0/0/0

10.1.1.0/8

OSPF

RIP

172.16.1.1/32

192.168.2.1/24

### 静态路由 · 动态路由

![课件：路由原理与静态路由 示意图 28](/images/network-notes/routing-static/all/img-06.webp)

静态路由

动态路由

由网络管理员手工指定的路由。
当网络拓扑发生变化时，管理员需要手工更新静态路由。

路由器使用路由协议从其他路由器那里获悉的路由。
当网络拓扑发生变化时，路由器会自动更新路由信息。

### 路由协议分类

![课件：路由原理与静态路由 示意图 30](/images/network-notes/routing-static/all/img-07.webp)

![课件：路由原理与静态路由 示意图 31](/images/network-notes/routing-static/all/img-08.webp)

![课件：路由原理与静态路由 示意图 32](/images/network-notes/routing-static/all/img-09.webp)

![课件：路由原理与静态路由 示意图 37](/images/network-notes/routing-static/all/img-10.webp)

IGPs：RIP OSPF ISIS

EGPs：BGP

AS100

AS200

### 协议算法

根据协议算法分类
  - 距离矢量路由选择协议（Distance-Vector）
    - 包括RIP和BGP。
    - 其中BGP也被称为路径矢量协议（Path-Vector）。
  - 链路状态路由选择协议（Link-State）
    - 又称为最短路径优先路由选择协议，包括OSPF和IS-IS。

### 路由表解析

  - [Huawei] display ip routing-table
  - Routing Tables:
  - Destination/Mask proto pref cost Nexthop Interface
  - 0.0.0.0/0 Static 60 0 120.0.0.2 Serial0/0
  - 8.0.0.0/8 RIP 100 3 120.0.0.2 Serial0/1
  - 9.0.0.0/8 OSPF 10 50 20.0.0.2 Ethernet0/0
  - 9.1.0.0/16 RIP 100 4 120.0.0.2 Serial0/0
  - 11.0.0.0/8 Static 60 0 120.0.0.2 Serial0/1
  - 20.0.0.0/8 Direct 0 0 20.0.0.1 Ethernet0/2
  - 20.0.0.1/32 Direct 0 0 127.0.0.1 LoopBack0

### 路由优先级（Preference）

当存在多个路由来源时，具有较高优先级（数值越小表明优先级越高）的路由来源提供的路由将被激活，用于指导报文的转发。

路由表

10.0.0.0 R0

10.0.0.0 R1

### 路由优先级（Preference）

VRP缺省的路由优先级如下表

| 路由协议 | 优先级 |
| --- | --- |
| DIRECT | 0 |
| OSPF | 10 |
| IS-IS | 15 |
| STATIC | 60 |
| RIP | 100 |
| OSPF ASE | 150 |

### 最长匹配原则

目的地址为9.1.2.1的数据报文，将命中9.1.0.0/16的路由

  - [Quidway] display ip routing-table
  - Destination/Mask proto pref Cost Nexthop Interface
  - 0.0.0.0/0 Static 60 0 120.0.0.2 Serial0/1
  - 8.0.0.0/8 RIP 100 3 120.0.0.2 Serial0/1
  - 9.0.0.0/8 OSPF 10 50 20.0.0.2 Ethernet0/0
  - 9.1.0.0/16 RIP 100 4 120.0.0.2 Serial0/1
  - 11.0.0.0/8 Static 60 0 120.0.0.2 Serial0/1
  - 20.0.0.0/8 Direct 0 0 20.0.0.1 Ethernet0/2
  - 20.0.0.1/32 Direct 0 0 127.0.0.1 LoopBack0

### 最长匹配原则

匹配

目的地址与掩码
分别做“与”操作

与路由表中的目
的地址作比较

查找路由表

挑选出最
长匹配项

### 静态路由

### 静态路由

由管理员手工配置而成，配置简单。
需要人工维护：当一个网络故障发生后，静态路由不会自动发生改变。
适合于网络拓扑简单的网络。

### 配置静态路由

在路由器B上配置到达路由器A的10.1.1.1网段的静态路由。

10.1.1.1/32

1.1.1.0/24

S0

20.1.1.1/32

[RTB] ip route-static 10.1.1.1 255.255.255.255 1.1.1.1
或者 [RTB] ip route-static 10.1.1.1 32 1.1.1.1
或者 [RTB] ip route-static 10.1.1.1 32 Serial 0

![课件：路由原理与静态路由 示意图 43](/images/network-notes/routing-static/all/img-11.webp)

### 静态路由配置

  - <RTB> display ip routing-table
  - Routing Tables: Public
  - Destinations : 7 Routes : 7
  - Destination/Mask Proto Pre Cost NextHop Interface
  - 1.1.1.0/24 Direct 0 0 1.1.1.2 Serial0
  - 1.1.1.1/32 Direct 0 0 1.1.1.1 Serial0
  - 1.1.1.2/32 Direct 0 0 127.0.0.1 InLoopBack0
  - 10.1.1.1/32 Static 60 0 1.1.1.1 Serial0
  - 20.1.1.1/32 Direct 0 0 127.0.0.1 InLoopBack0
  - 127.0.0.0/8 Direct 0 0 127.0.0.1 InLoopBack0
  - 127.0.0.1/32 Direct 0 0 127.0.0.1 InLoopBack0
