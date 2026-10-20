---
title: "数据链路层"
date: 2026-10-20T17:00:00+08:00
draft: false
categories: ["课程笔记", "网络基础"]
tags: ["网络基础", "数据链路层", "MAC"]
summary: "数据链路层的职责：帧的封装与解封装、差错检测、MAC 地址与以太网帧格式。"
description: "数据链路层的职责：帧的封装与解封装、差错检测、MAC 地址与以太网帧格式。"
ShowToc: true
---

> 来源：网络基础课程讲义（`数据链路层.pdf`）。由 PDF/PPTX/DOCX 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 数据链路层

> 来源：（`数据链路层.pdf`，共 4 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 一、数据链路层的概述

### 1.1 概述

数据链路层是二层！

数据链路层的传输单元：帧以太网Ethernet === 局域网LAN === 内网osi 7层模型每一层都是为上一层提供服务的

![数据链路层.pdf 示意图 1](/images/network-notes/data-link-layer/all/img-01.webp)

### 1.2 帧结构（本章重点学习）

![数据链路层.pdf 示意图 2](/images/network-notes/data-link-layer/all/img-02.webp)

数据链路层的协议：MAC子层协议MAC子层协议：封装帧头和帧尾帧结构的构成：MAC子层+上三层数据+FCS（帧校验序列）

MAC子层头部包含：目标MAC地址（6 byte字节 48bit） + 源MAC地址（6字节）+  类型（2字节） 上一层是什么协义类型的数据    0x0800  ip协义    0x0806  arp协议       一共14个字节MAC地址：也称为物理地址，是一台PC的身份，是被固化到网卡的全球唯一标识，如下图：

![数据链路层.pdf 示意图 3](/images/network-notes/data-link-layer/all/img-03.webp)

  - MAC地址=厂家标识+内部编号====实现了全球唯一！

  - 怎么查看自己的MAC地址？ipconfig  /all

类型字段的作用：区分上层协议，0806代表上层协议是ARP协议，0800代表上层是IP协议帧尾：FCS（Frame Checksum Sequence）=帧校验序列，长度4个字节

FCS作用：对整个帧进行序列校验，可以检测帧在传输过程中是否发送错误一个帧是有最大承载能力限制的。一个帧的最大承受能力叫MTU值=1500 字节MTU:（最大传输单元 max trans unit）·帧结构最终效果图如下：

![数据链路层.pdf 示意图 4](/images/network-notes/data-link-layer/all/img-04.webp)

面试官问：您描述一下帧结构答：帧是由帧头+上三层数据+帧尾，帧头包含目MAC，源MAC，类型，帧尾是FCS，MTU：1500

## 二、本层的设备

  - 工作在2层的设备：交换机/网桥

## 三、交换机的工作原理（本章重点学习）

  - 交换机：用来组建一个局域网！

  - 交换机的工作原理：交换机是如何工作的？从收到一个帧，到将该帧转发出去的过程！面试题问：交换机的工作原理？

  - 1）当收到一个帧，首先学习帧中的源MAC地址来形成自己的MAC地址表！

  - 2）然后检查帧中的目标MAC地址，并匹配MAC地址表

  - 如表中匹配成功，则单播转发！

  - 如表中无匹配项，则广播转发！

  - 3）MAC地址表的老化时间/生存时间是：300秒！

效果图如下：

## 四、如何配置交换机？

  - 傻瓜式交换机不支持配置（不支持化区 化vlan  ）！如TP-link

  - 企业级交换机支持配置高级功能及高级配置，价格要高，一般称为【企业管理型交换机】

思科、juniper、华为、锐捷、启明、天融信、360（红帽认证rhca 思科 ccie）

购买一台cisco思科交换机，一般会自带一根console线！如何配置？看下图

![数据链路层.pdf 示意图 5](/images/network-notes/data-link-layer/all/img-05.webp)

![数据链路层.pdf 示意图 6](/images/network-notes/data-link-layer/all/img-06.webp)

console口：控制台接口

![数据链路层.pdf 示意图 7](/images/network-notes/data-link-layer/all/img-07.webp)

![数据链路层.pdf 示意图 8](/images/network-notes/data-link-layer/all/img-08.webp)

com口转USB线

![数据链路层.pdf 示意图 9](/images/network-notes/data-link-layer/all/img-09.webp)

电脑端：超级终端做实验，我们用软件：华为ensp接口编号如下：
