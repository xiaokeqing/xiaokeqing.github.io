---
title: "生成树（STP）与 VRRP"
date: 2026-10-20T15:00:00+08:00
draft: false
categories: ["网络基础"]
tags: ["网络基础", "STP", "VRRP", "链路聚合"]
summary: "二层环路与生成树：广播风暴、MAC 表震荡、STP 通信过程与端口状态；以及 VRRP 网关冗余、链路聚合与端口镜像。"
description: "二层环路与生成树：广播风暴、MAC 表震荡、STP 通信过程与端口状态；以及 VRRP 网关冗余、链路聚合与端口镜像。"
ShowToc: true
---

> 来源：网络基础课程讲义（`STP与VRRP.pptx`）。由 PDF/PPTX/DOCX 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 课件：STP 与 VRRP

《华为交换机技术与应用 》

认识交换机
交换机管理
VLAN 管理
交换机特性
网关冗余
局域网安全

### 生成树（STP）

### 交换机转发流程回顾

| 目的MAC地址 | 目的端口 |
| --- | --- |
| 00-0D-56-BF-88-10 00-0D-56-BF-88-20 ..... ..... | E0/2 E0/3 ..... ..... |

| 目的MAC地址 | 目的端口 |
| --- | --- |
| 00-0D-56-BF-88-10 00-0D-56-BF-88-20 ..... ..... | E0/5 E0/6 ..... ..... |

![课件：STP 与 VRRP 示意图 1](/images/network-notes/stp-vrrp/all/img-01.webp)

![课件：STP 与 VRRP 示意图 2](/images/network-notes/stp-vrrp/all/img-02.webp)

![课件：STP 与 VRRP 示意图 4](/images/network-notes/stp-vrrp/all/img-03.webp)

E0/2

E0/3

E0/5

E0/6

00-0D-56-BF-88-10

00-0D-56-BF-88-20

PCA

SWA

SWB

PCB

1

2

3

### 环路引起的问题之一 —— 广播风暴

SWC

环路会引起广播风暴
网络中的主机会收到重复的数据帧

广播：FF-FF-FF-FF-FF-FF

### 环路引起的问题之二 —— MAC地址表不稳定

E0/4

错误目的端口

### What

消除环路

![课件：STP 与 VRRP 示意图 15](/images/network-notes/stp-vrrp/all/img-04.webp)

LANE

![课件：STP 与 VRRP 示意图 16](/images/network-notes/stp-vrrp/all/img-05.webp)

LANA

LANC

LAND

E0/10

E0/20

阻塞某一端口

![课件：STP 与 VRRP 示意图 22](/images/network-notes/stp-vrrp/all/img-06.webp)

LANB

### 环路消除之后

### 链路备份

恢复此端口

### STP通信过程

每2秒发一次
BPDU类型
  - 配置BPDU
  - 拓扑变更BPDU

BPDU

![课件：STP 与 VRRP 示意图 39](/images/network-notes/stp-vrrp/all/img-07.webp)

### STP

STP 工作原理
  - 按照一颗树 有树根，沿着树根的方向走，最近的距离，最远的端口被关闭
  - 根桥、非根桥；Root 端口 、指定端口、阻塞端口
STP 选举过程
  - 第一步：选举一个根网桥；
  - 第二步：在每个非根网桥上选举一个根端口；
  - 第三步：在每个互连网段上选举一个指定端口；
  - 第四步：阻塞非根、非指定端口。

![课件：STP 与 VRRP 示意图 42](/images/network-notes/stp-vrrp/all/img-08.webp)

![课件：STP 与 VRRP 示意图 43](/images/network-notes/stp-vrrp/all/img-09.webp)

### STP

STP更新包（BPDU）
  - 交换机或者网桥之间周期性地发送STP的桥接协议数据单元（Bridge Protocol Data Unit ，BPDU），用于实现STP的功能
  - 每2秒发送一次的二层报文
  - 组播发送，组播地址为：01-80-C2-00-00-00

![课件：STP 与 VRRP 示意图 45](/images/network-notes/stp-vrrp/all/img-10.webp)

### STP

网桥ID
  - 用于选举根网桥：最低网桥ID的交换机将成为根网桥
  - 网桥优先级取值范围：0到65535；默认值：32768（0x8000）
  - 首先判断网桥优先级，优先级最低的网桥将成为根网桥
  - 如果网桥优先级相同，则比较网桥MAC地址，具有最低MAC地址的交换机或网桥将成为根网桥

![课件：STP 与 VRRP 示意图 46](/images/network-notes/stp-vrrp/all/img-11.webp)

### STP

路径计算
  - 路径成本的计算和链路的带宽相关联
  - 根路径成本就是到根网桥的路径中所有链路的路径成本的累计和
  - 修订前后的802.1d路径成本

| 链路带宽 | 成本（修订前） | 成本（修订后） |
| --- | --- | --- |
| 10G | 1 | 2 |
| 1000M | 1 | 4 |
| 100M | 10 | 19 |
| 10M | 100 | 100 |

### STP

选举根网桥
  - 依据网桥ID选举根网桥，ID值最小者当选
  - 根网桥每2s发送一次BPDU

SW1:
32768.00-d0-f8-00-11-11

SW2:
4096.00-d0-f8-00-22-22

SW3:
32768.00-d0-f8-00-33-33

F0/2

![课件：STP 与 VRRP 示意图 47](/images/network-notes/stp-vrrp/all/img-12.webp)

F0/1

100M

Root Bridge

### STP选举过程

在非根交换机上选举根端口
选举依据：
  - 根路径成本最小
  - 发送网桥ID最小
  - 发送端口ID最小

32768.00-d0-f8-00-11-11

4096.00-d0-f8-00-22-22

32768.00-d0-f8-00-33-33

根路径成本：19

根路径成本：38

### STP 选举指定端口

每个网段中选取一个指定端口
  - 所在交换机的网桥ID最小
  - 端口ID最小

32768.00-d0-f8-00-11-11

4096.00-d0-f8-00-22-22

32768.00-d0-f8-00-33-33

根路径成本：0

所在交换机网桥ID最小

### STP 阻塞端口

阻塞非根、非指定的端口，形成逻辑上无环路的拓扑结构

32768.00-d0-f8-00-11-11

4096.00-d0-f8-00-22-22

32768.00-d0-f8-00-33-33

### 交换机端口角色

| 端口角色 | 描 述 |
| --- | --- |
| Root Port | 根端口，是所在交换机上离根交换机最近的端口，处于转发状态。 |
| Desi Port | 指定端口，转发所连接的网段发往根交换机方向的数据和从交换机方向发往所连接的网段的数据。 |
| Alte Port | 预备端口，不向所连网段转发任何数据。 |

### 端口状态描述

| 端口状态 | 描 述 |
| --- | --- |
| Disabled 端口没有启用 | 此状态下端口不转发数据帧，不学习MAC地址表，不参与生成树计算。 |
| Blocking 阻塞状态 | 此状态下端口不转发数据帧，不学习MAC地址表，此状态下端口接收并处理BPDU，但是不向外发送BPDU。 |
| Listening 侦听状态 | 此状态下端口不转发数据帧，不学习MAC地址表，只参与生成树计算，接收并发送BPDU。 |
| Learning 学习状态 | 此状态下端口不转发数据帧，但是学习MAC地址表，参与计算生成树，接收并发送BPDU。 |
| Forwarding 转发状态 | 此状态下端口正常转发数据帧，学习MAC地址表，参与计算生成树，接收并发送BPDU。 |

### STP 状态变化

![课件：STP 与 VRRP 示意图 59](/images/network-notes/stp-vrrp/all/img-13.webp)

### STP基本配置－配置命令

Root

LANC的
指定端口

[Quidway]sysname SWA
[SWA]stp enable
[SWA]stp mode stp
[SWA]stp priority 4096

[Quidway]sysname SWB
[SWB]stp enable
[SWB]stp mode stp
[SWB]stp priority 8192

[Quidway]sysname SWC
[SWC]stp enable
[SWC]stp mode stp

E0/24

### 验证STP 状态

[SWC]display stp
-------[CIST Global Info][Mode STP]-------
CIST Bridge :32768.4c1f-cc45-aace
Bridge Times :Hello 2s MaxAge 20s FwDly 15s MaxHop 20
CIST Root/ERPC :4096.4c1f-cc45-aacc / 10000
CIST RegRoot/IRPC :32768.4c1f-cc45-aace / 0
CIST RootPortId :128.25
BPDU-Protection :Disabled
CIST Root Type :Secondary root
TC or TCN received :125
TC count per hello :0
STP Converge Mode :Normal
Share region-configuration :Enabled
Time since last TC :2 days 1h:56m:15s

### 验证STP端口信息

[SWC]display stp interface Ethernet 0/20
----[Port20(Ethernet0/20)][FORWARDING]----
Port Protocol :Enabled
Port Role :Root Port
Port Priority :128
Port Cost(Dot1T ) :Config=auto / Active=199999
Designated Bridge/Port :0.4c1f-cc45-aacc / 128.20
Port Edged :Config=default / Active=disabled
Point-to-point :Config=auto / Active=true
Transit Limit :147 packets/hello-time
Protection Type :None
Port STP Mode :STP
Port Protocol Type :Config=auto / Active=dot1s
PortTimes :Hello 2s MaxAge 20s FwDly 15s RemHop 0
TC or TCN send :1
TC or TCN received :52
BPDU Sent :2
TCN: 1, Config: 1, RST: 0, MST: 0
BPDU Received :175898
TCN: 0, Config: 175898, RST: 0, MST: 0

### IEEE 802

Common Spanning Tree (CST) = IEEE 802.1D
Rapid Spanning Tree Protocol (RSTP) = IEEE 802.1w
Per-VLAN Spanning-Tree plus (PVST+) = Per-VLAN IEEE 802.1D （CISCO）
Multiple Spanning Tree Protocol (MSTP) = IEEE 802.1s

### STP 特性

Root guard
  - 防止另外交换机抢占成为根桥
  - 开启了Root Guard功能的端口，如果在此端口上连接的新交换机试图成为根交换机，那么此端口并不会成为根端口，相反，此端口将进入 inconsistent (blocked) 状态，从而防止新加入交换机抢占根角色来影响网络
  - Root Guard在可能连接新交换机的端口上开启
    - Huawei-GigabitEthernet0/0/1]stp root-protection

### What

端口聚合，也称为端口捆绑、端口聚集或链路聚合。
端口聚合将多个接口聚合在一起形成1个汇聚组，以实现负载分担。从外面看起来，1个汇聚组好象就是1个接口。
端口聚合在数据链路层实现。（二层）

### 端口聚合的优点

提高链路带宽
流量负载分担
提高可靠性：同组成员彼此动态备份

数据流量

![课件：STP 与 VRRP 示意图 68](/images/network-notes/stp-vrrp/all/img-14.webp)

### 端口聚合

### 端口聚合举例

SW1

SW2

E0/1

SW1的配置：
[SW1] interface eth-trunk 1
[SW1-Eth-Trunk1] quit
[SW1] interface ethernet 0/1
[SW1-Ethernet0/1] eth-trunk 1
[SW1-Ethernet0/1] quit
[SW1] interface ethernet 0/2
[SW1-Ethernet0/2] eth-trunk 1
[SW1-Ethernet0/2] quit

SW2的配置：
[SW2] interface eth-trunk 1
[SW2-Eth-Trunk1] quit
[SW2] interface ethernet 0/1
[SW2-Ethernet0/1] eth-trunk 1
[SW2-Ethernet0/1] quit
[SW2] interface ethernet 0/2
[SW2-Ethernet0/2] eth-trunk 1
[SW2-Ethernet0/2] quit

![课件：STP 与 VRRP 示意图 70](/images/network-notes/stp-vrrp/all/img-15.webp)

### 端口聚合的限制

端口聚合两端的物理参数必须保持一致
  - 进行聚合的链路的数目
  - 进行聚合的链路的速率
  - 进行聚合的链路的双工方式
端口聚合两端的逻辑参数必须保持一致
  - 同一个汇聚组中端口的基本配置必须保持一致，基本配置主要包括STP、QoS（流量控制）、VLAN、端口等相关配置

### 链路聚合-负载均衡

Souce-MAC
  - 基于源 MAC，默认为此模式，不同源主机，流量可能从不同的接口被发出去，但相同源主机肯定走相同接口。
Source-and-Destination MAC
  - 同时基于源和目标MAC，流量从主机 A到主机B，从主机 A 到主机C 以及从主机C 到主机 B都可能走不同的接口。
Source-IP
  - 基于源 IP，不同源 IP的流量可能走不同接口，相同IP则走相同接口。
Destination-IP
  - 基于目的 IP，到不同目标IP 的流量，会走不同接口，不同主机发往相同IP的流量会走相同接口。

### 链路聚合-负载均衡

Source-and-Destination IP
  - 同时基于源和目标IP，流量从主机A到主机B，从主机A到主机C 以及从主机C到主机B 都可能走不同的接口。
注：并不是所有型号的交换机所有IOS 都支持所有负载方式，需要视软件版本而定。
在交换机之间通过EtherChannel捆绑了多条链路后，默认执行基于源MAC的负载均衡

### 网关冗余 VRRP

### VRRP

公有，标准化协议 （Virtual Router Redundancy Protocol）
  - Master Backup 两个角色
  - 组号 VRID，范围为0—255，0代表弃权，不参与角色选举
  - 使用组播地址：224.0.0.18 进行通告
  - 优先级决定了主控（Master）的角色
  - 支持跟踪
  - 支持验证

### VRRP

图示

10.1.1.1/2410.1.1.254

Ethernet

RTA

10.1.1.2/2410.1.1.254

10.1.1.3/2410.1.1.254

10.1.1.4/2410.1.1.254

10.1.1.251/24

PCC

PCD

RTB

10.1.1.252/24

虚拟路由器

10.1.1.254

E0/0

![课件：STP 与 VRRP 示意图 72](/images/network-notes/stp-vrrp/all/img-16.webp)

![课件：STP 与 VRRP 示意图 75](/images/network-notes/stp-vrrp/all/img-17.webp)

![课件：STP 与 VRRP 示意图 79](/images/network-notes/stp-vrrp/all/img-18.webp)

Internet

### VRRP

配置VRRP （实验十四）
  - 配置网关SVI 接口
  - 配置网关虚拟IP地址
  - 配置优先级
  - 配置抢占

### 配置VRRP

<Quidway>system-view
[Quidway]sysname RTA
[RTA]interface Ethernet 0/0
[RTA-Ethernet0/0]ip address 10.1.1.251 24
[RTA-Ethernet0/0]vrrp vrid 1 virtual-ip 10.1.1.254

<Quidway>system-view
[Quidway]sysname RTB
[RTB]interface Ethernet 0/0
[RTB-Ethernet0/0]ip address 10.1.1.252 24
[RTB-Ethernet0/0]vrrp vrid 1 virtual-ip 10.1.1.254
[RTB-Ethernet0/0]vrrp vrid 1 priority 200
