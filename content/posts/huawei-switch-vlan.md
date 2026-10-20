---
title: "华为交换机技术与应用（VLAN 部分）"
date: 2026-10-20T16:00:00+08:00
draft: false
categories: ["网络基础"]
tags: ["网络基础", "交换机", "VLAN", "华为"]
summary: "华为交换机课程课件：认识交换机、二层转发原理、MAC 地址表、VLAN 划分与配置。"
description: "华为交换机课程课件：认识交换机、二层转发原理、MAC 地址表、VLAN 划分与配置。"
ShowToc: true
---

> 来源：网络基础课程讲义（`华为交换机技术与应用.pptx`）。由 PDF/PPTX/DOCX 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 课件：华为交换机技术与应用

《华为交换机技术与应用 》

认识交换机
交换机管理
VLAN 管理
交换机特性
网关冗余
局域网安全

### 认识交换机

### What

交换机（Switch）
  - 基于帧的目的地址过滤、转发或者泛洪的网络设备。交换机又叫多端口网桥，交换机和网桥一样
  - 常见的以太网设备包括Hub、交换机等，他们的工作原理也是不一样的
  - 基于数据包转发过程（演示）

### 二层交换机的工作原理

网桥/二层以太网交换机的工作模式

应用层

表示层

会话层

传输层

网络层

链路层

物理层

二层交换机

### 认识交换机

MAC 地址
  - MAC 地址用来标识以太网上每个节点(node) 的地址,即物理地址.
  - MAC 地址为48 位(bit) 长,即6 个字节.如下图:
  - MAC 地址是烧录在网卡(Network Interface Controller,NIC) 的ROM 里的.为了保证MAC 地址的唯一性,IEEE 规定MAC 地址前24 位为厂商代码(vendor code), 后24 位为序列号(serial number)

![课件：华为交换机技术与应用 示意图 1](/images/network-notes/huawei-switch-vlan/all/img-01.webp)

### MAC地址

MAC 地址表
  - 交换机在转发数据时，需要根据MAC地址表来做出相应转发，
  - 交换机的 MAC 地址表除了动态学习之外，还可以静态手工指定
  - 交换机上，一个接口可以对应多个MAC 地址，地址的数量无上限，但不超过交换机所支持的MAC 地址最大数量。
  - [Huawei]display mac-address

### MAC地址

MAC地址老化
  - 交换机在一个接口上学习到 MAC 地址之后，该 MAC 与接口的映射并不会永远被保存在 MAC 地址表中，除非是手工静态指定的。
  - MAC 地址在 MAC 地址表中是有最大停留时间，称为老化时间（aging-time）， 当相应MAC地址在超出老化时间后还没有数据传输时，该 MAC 地址将从表中被清除。
  - 默认的MAC 地址老化时间为300秒（5 分 钟） 。
    - [Huawei]mac-address aging-time

### 交换机的功能

地址学习
帧的转发/过滤
环路防止

### 基于源地址学习

分段1

分段2

A

B

C

PORT1

PORT2

D

交换机

MAC地址

所在端口

MAC A

1

MAC B

MAC C

2

MAC D

![课件：华为交换机技术与应用 示意图 2](/images/network-notes/huawei-switch-vlan/all/img-02.webp)

![课件：华为交换机技术与应用 示意图 3](/images/network-notes/huawei-switch-vlan/all/img-03.webp)

### 基于目的地址转发

MACD

MACA

......

端口1

端口2

MACB

MACC

![课件：华为交换机技术与应用 示意图 7](/images/network-notes/huawei-switch-vlan/all/img-04.webp)

### 转发过程

帧输入

泛洪该帧（源端口除外）

转发该帧（源端口除外）

目的MAC地址

地址表查找

单播

广播

查找成功

没有找到匹配条目

### VLAN 管理

### 数据转发

冲突域
  - 处于冲突域里的某个设备在某个网段发送数据包, 强迫该网段的其他所有设备注意到这个包.而在某1 个相同时间里,不同设备尝试同时发送包, 那么将在这个网段导致冲突的发生,降低网络性能
  - 接入设备越多冲突机率越大
  - 采用CSMA/CD技术

![课件：华为交换机技术与应用 示意图 8](/images/network-notes/huawei-switch-vlan/all/img-05.webp)

![课件：华为交换机技术与应用 示意图 9](/images/network-notes/huawei-switch-vlan/all/img-06.webp)

![课件：华为交换机技术与应用 示意图 10](/images/network-notes/huawei-switch-vlan/all/img-07.webp)

### 数据转发

每个端口有自己的冲突域
广播包向所有段转发

缓冲区

交换

### 认识交换机

广播域
  - 能够收到某台设备发送广播帧的所有设备的集合。 路由器一般用于限定广播域，因为路由器不转发广播帧。
VLAN 就是将交换机划分为多个广播域的技术
  - 虚拟局域网（VLAN）技术为以太网引入了灵活的控制手段，被广泛应用。

### WHY

缺少转发控制手段

用户：我不想收到C
的广播报文

管理员：B不能
访问A

![课件：华为交换机技术与应用 示意图 18](/images/network-notes/huawei-switch-vlan/all/img-08.webp)

![课件：华为交换机技术与应用 示意图 20](/images/network-notes/huawei-switch-vlan/all/img-09.webp)

![课件：华为交换机技术与应用 示意图 23](/images/network-notes/huawei-switch-vlan/all/img-10.webp)

### What

VLAN技术的目标

![课件：华为交换机技术与应用 示意图 39](/images/network-notes/huawei-switch-vlan/all/img-11.webp)

组1

组2

### How

通过标签管理实现VLAN

![课件：华为交换机技术与应用 示意图 42](/images/network-notes/huawei-switch-vlan/all/img-12.webp)

![课件：华为交换机技术与应用 示意图 43](/images/network-notes/huawei-switch-vlan/all/img-13.webp)

![课件：华为交换机技术与应用 示意图 45](/images/network-notes/huawei-switch-vlan/all/img-14.webp)

5

Permit VLAN 1 only

### 生成VLAN标签

主机A

主机B

主机C

主机D

Port 1

Port 2

Port 7

Port 10

| 端口 | PVID |
| --- | --- |
| Port1 | 5 |
| Port2 | 10 |
| …… | …… |
| Port7 | 5 |
| …… | …… |
| Port10 | 10 |

### VLAN标签文件格式

Untagged frame

Tagged frame

TPID

TCI

6B

2B

64-1500B

4B

### VLAN标签文件格式

![课件：华为交换机技术与应用 示意图 51](/images/network-notes/huawei-switch-vlan/all/img-15.webp)

### VLAN类型

端口类型
  - Access
    - 访问型接口，一般接PC终端
  - Trunk
    - 交换机互连，通过多个VLAN数据
  - Hybrid
    - 类似与Trunk接口但可以接入PC，也可以实现多个VLAN数据转发

### 配置Access接口属性

\\配置接口类型
[SWA-Ethernet0/1]port link-type access
[SWA-Ethernet0/2]port link-type access
\\创建VLAN
[SWA]vlan 3
[SWA]vlan 5
\\设置接口PVID
[SWA-Ethernet0/1]port default vlan 3
[SWA-Ethernet0/2]port default vlan 5

Port-0/1 : VLAN-3

Port-0/2 : VLAN-5

SWA

### 配置Trunk端口属性

\\配置端口类型
[SWA-Ethernet0/3]port link-type trunk
\\配置Trunk-Link所允许通过的VLAN（permitted VLAN）
[SWA-Ethernet0/3] port trunk allow-pass vlan 5

Port-0/3

SWB

注：Trunk默认禁止除VLAN1之外的VLAN通过，需要单独放行

### Hybrid端口VLAN属性

[Quidway-Ethernet1/0/1]port link-type hybrid
[Quidway-Ethernet1/0/1]port hybrid pvid vlan 2
[Quidway-Ethernet1/0/1] port hybrid untagged vlan 2 99
[Quidway-Ethernet1/0/24]port link-type hybrid
[Quidway-Ethernet1/0/24]port hybrid pvid vlan 2
[Quidway-Ethernet1/0/24]port hybrid untagged vlan 2 99
[Quidway-Ethernet2/0/0]port link-type hybrid
[Quidway-Ethernet2/0/0]port hybrid pvid vlan 99
[Quidway-Ethernet2/0/0]port hybrid untagged vlan 2 to 3

Port-2/0/0

Port-1/0/1

![课件：华为交换机技术与应用 示意图 57](/images/network-notes/huawei-switch-vlan/all/img-16.webp)

![课件：华为交换机技术与应用 示意图 59](/images/network-notes/huawei-switch-vlan/all/img-17.webp)

Port-1/0/24

### GVRP

端口VLAN属性动态配置
过渡交换机添加VLAN信息
  - 手动配置
    - 只适合小型网络
  - 自动配置

手动/自动配置VLAN

![课件：华为交换机技术与应用 示意图 61](/images/network-notes/huawei-switch-vlan/all/img-18.webp)

SWC

VLAN-2

PC-2

PC-1

### GVRP

模式
  - Normal
    - 可以同步其他交换机，也可以被同步，静态、动态都可以
  - Fixed
    - 不接受动态VLAN，可以同步自己的VLAN到Normal模式
  - Forbidden
    - 相当于是关闭GVRP同步

### 配置GVRP

Eth0/1

Eth0/2

[Switch]gvrp
[Switch]interface e0/1
[Switch-Ethernet0/1]port link-type trunk
[Switch-Ethernet0/1]port trunk allow-pass vlan all
[Switch-Ethernet0/1]gvrp
[Switch-Ethernet0/1]gvrp registration normal

### VLAN缺点

VLAN隔离了二层广播域，也就严格地隔离了各个VLAN之间的任 何流量，分属于不同VLAN的用户不能互相通信。

VLAN 100

![课件：华为交换机技术与应用 示意图 69](/images/network-notes/huawei-switch-vlan/all/img-19.webp)

VLAN 200

![课件：华为交换机技术与应用 示意图 71](/images/network-notes/huawei-switch-vlan/all/img-20.webp)

### 解决方案

![课件：华为交换机技术与应用 示意图 75](/images/network-notes/huawei-switch-vlan/all/img-21.webp)

Port 3
VLAN100

Port 5
VLAN200

Ethernet1
192.168.100.1

Ethernet0
192.168.200.1

192.168.200.200

192.168.100.100

### 使用VLAN Trunking

二层交换机和路由器之间相连的接口配置VLAN Trunking，使多个VLAN共享同一条物理链路连接到路由器

VLAN 300

Ethernet0.300

Ethernet0.200

Ethernet0.100

### 每个VLAN一个物理连接

在二层交换机上配置VLAN，每一个VLAN使用一条独占的物理连接连接到路由器的一个接口上。

Ethernet2

### 交换和路由的集成

二层交换机和路由器在功能上的集成构成了三层交换机，
三层交换机在功能上实现了VLAN的划分、VLAN内部的二层交换和VLAN间路由的功能。

![课件：华为交换机技术与应用 示意图 86](/images/network-notes/huawei-switch-vlan/all/img-22.webp)

![课件：华为交换机技术与应用 示意图 92](/images/network-notes/huawei-switch-vlan/all/img-23.webp)

![课件：华为交换机技术与应用 示意图 93](/images/network-notes/huawei-switch-vlan/all/img-24.webp)

三层交换机

### 单臂路由

Ethernet0/1

Port 24

IP:192.168.20.20
GW:192.168.20.1

IP:192.168.10.10
GW:192.168.10.1

RTA

### 单臂路由配置

[SWA]vlan 100
[SWA-vlan100]port ethernet 0/1
[SWA]vlan 200
[SWA-vlan200]port ethernet 0/2
[SWA]interface ethernet 0/24
[SWA-Ethernet0/24]port link-type trunk
[SWA-Ethernet0/24]port trunk allow-pass vlan all

![课件：华为交换机技术与应用 示意图 105](/images/network-notes/huawei-switch-vlan/all/img-25.webp)

![课件：华为交换机技术与应用 示意图 106](/images/network-notes/huawei-switch-vlan/all/img-26.webp)

[RTA]interface ethernet 0/1.1
[RTA-Ethernet0/1.1]dot1q termination vid 100//给子接口封装dot1q协议，剥离vlan100，让数据可以通过
[RTA-Ethernet0/1.1]arp broadcast enable
[RTA-Ethernet0/1.1]ip address 192.168.10.1 255.255.255.0
[RTA]interface ethernet 0/1.2
[RTA-Ethernet0/1.2]dot1q termination vid 200
[RTA-Ethernet0/1.2]arp broadcast enable
[RTA-Ethernet0/1.2]ip address 192.168.20.1 255.255.255.0

### 三层交换机配置

[SWA]interface vlanif 100
[SWA-Vlanif1]ip add 192.168.10.1 255.255.255.0
[SWA]interface vlanif 200
[SWA-Vlanif200]ip add 192.168.20.1 255.255.255.0

创建VLAN三层接口
