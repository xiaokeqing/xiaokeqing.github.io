---
title: "华为交换机实验手册（实验一～十三）"
date: 2026-10-20T14:00:00+08:00
draft: false
categories: ["课程笔记", "网络基础"]
tags: ["网络基础", "交换机", "实验", "VLAN", "STP", "华为"]
summary: "华为交换机实验一到十三的完整手册：基本设置与 Telnet、VLAN 划分与跨交换机 VLAN、hybrid、单臂路由、多层交换、GVRP、STP/MSTP、链路聚合、端口镜像。"
description: "华为交换机实验一到十三的完整手册：基本设置与 Telnet、VLAN 划分与跨交换机 VLAN、hybrid、单臂路由、多层交换、GVRP、STP/MSTP、链路聚合、端口镜像。"
ShowToc: true
---

> 来源：网络基础课程讲义（`华为交换机基本设置-实验1-2.docx`、`华为交换机.docx`、`交换机实验.docx`）。由 PDF/PPTX/DOCX 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 一、实验一～三：基本设置、Telnet、配置文件管理

交换机管理

### 实验一 华为交换机基本设置

实验目标

熟练掌握进入交换机的方式方法

熟悉路由器的登录模式

掌握路由器时间的配置

关闭弹LOG信息功能

掌握密码设置方法

掌握不同视图的使用及切换

![一、实验一～三：基本设置、Telnet、配置文件管理 示意图 1](/images/network-notes/huawei-switch-labs/s1/img-01.webp)

拓扑结构

拓扑描述：客户端PC使用com或者USB转接口利用Console线连接至交换机的Console口，进行带外网管 。

配置步骤

用户模式（用户视图）。

```
<Huawei> //以下为刚进入交换机时的默认模式，用大于号表示
```

用户模式进入特权模式（系统视图）：

```
<Huawei> system-view
Enter system view, return user view with Ctrl+Z.
[Huawei]
// 以上是特权模式。用 [ ]表示
```

从特权模式进入接口模式：

```
[Huawei] interface Ethernet 0/0/1
[Huawei-Ethernet0/0/0]
// 以上为接口模式。
[Huawei-Ethernet0/0/0] quit
[Huawei]
// 退出的时候打 quit
```

系统视图下设置一个名字：

```
[Huawei] sysname topsec
[topsec]
// 可以发现交换机的名字己经变成了 topsec
```

配置 console 口密码

```
[topsec] user-interface console 0
[topsec-ui-console0]authentication-mode password
[topsec-ui-console0]set authentication password cipher topsec
[topsec-ui-console0]quit
[topsec]
```

/ /进入 console 口配置模式

/ /以上设置 console 认证的模式是本地密码的方式，还可以选择不认证与 AAA 认证

/ /以上是设备 console 口登陆密码为 topsec ，以后再登陆 console 将需要密码

设置系统时间和时区

```
<topsec>clock timezone CST add 8
<topsec>clock datetime 19:57:00 2013-5-13
```

显示系统运行配置信息

```
[Topsec] display current-configuration
sysname Topsec
```

#

------ 省略以下部分 ------=

配置 IP 地址，并打开接口

```
[topsec] interface Vlanif 1 #进入网口
[topsec-Vlanif1]ip add 192.168.0.1 24 #设置ip
[topsec-Vlanif1]display ip interface brief #查看ip
```

显示接口状态：

```
[Topsec] display ip interface brief
```

关闭弹 LOG 信息：

```
[Topsec] undo info-center enable
```

注意事项

通过Console口连接设备时，如果电脑上没有COM口，可以使用USB转COM口连接，然后用securtCRT或者其他连接软件连接交换机设备。

### 实验二 交换机设置Telnet远程登陆

实验目标

掌握交换机接口连通性设置

掌握交换机设备使用telnet登录配置

![一、实验一～三：基本设置、Telnet、配置文件管理 示意图 2](/images/network-notes/huawei-switch-labs/s1/img-02.webp)

拓扑结构

拓扑说明：两台华为交换机192.168.1.10（客户端）和192.168.1.254（服务端） 通过Console线与网线相连

实验需求

客户端通过telnet的方式登陆交换机，并管理交换机。

配置步骤

配置两端连通性

服务端交换机配置：

```
[topsec1] interface Vlanif 1
[topsec1-Vlanif1]ip address 192.168.1.254 255.255.255.0
```

客户端配置：

```
[topsec1] interface Vlanif 1
[topsec1-Vlanif1]ip address 192.168.1.10 255.255.255.0
```

联通性测试：服务端ping客户端交换机测试

![一、实验一～三：基本设置、Telnet、配置文件管理 示意图 3](/images/network-notes/huawei-switch-labs/s1/img-03.webp)

连通性良好，可以配置telnet服务

服务端开启Telnet登陆

交换机配置：

```
[R2]user-interface vty 0 4 // 进入 telnet 的虚拟接口 vty 下
[R2-ui-vty0-4]authentication-mode password 设置特权登陆密码
[R2-ui-vty0-4]set authentication password simple topsec
[R2-ui-vty0-4]user privilege level 3 // 设备登陆进来的权限为控制级
```

![一、实验一～三：基本设置、Telnet、配置文件管理 示意图 4](/images/network-notes/huawei-switch-labs/s1/img-04.webp)

用户级别和命令级别对应关系表：

验证配置可行性

![一、实验一～三：基本设置、Telnet、配置文件管理 示意图 5](/images/network-notes/huawei-switch-labs/s1/img-05.webp)

客户端通过CLI的方式 Telnet到交换机

实验成功

注意事项

端到端 (end-to-end)的连接，直连的接口必须处于同一子网

Telnet远程连接，如果客户端是华为设备需要退到用户模式连接telnet。

### 实验三 管理配置文件

实验目标

掌握运行文件与启动文件的作用

设置下次重启加载的文件

掌握清除配置文件方法

配置步骤

保存配置文件

![一、实验一～三：基本设置、Telnet、配置文件管理 示意图 6](/images/network-notes/huawei-switch-labs/s1/img-06.webp)

显示已保存的文件

![一、实验一～三：基本设置、Telnet、配置文件管理 示意图 7](/images/network-notes/huawei-switch-labs/s1/img-07.webp)

![一、实验一～三：基本设置、Telnet、配置文件管理 示意图 8](/images/network-notes/huawei-switch-labs/s1/img-08.webp)

路由中可以存放多个配置文件。根据需要，我们可以设置交换机下次启动时使用的配置文件

```
<topsec1>startup saved-configuration isacfg.zip //此isacfg.zip必须在flash里存在
```

清除存储的配置文件

```
<topsec1>reset saved-configuration
```

This will delete the configuration in the flash memory.

The device configuratio

ns will be erased to reconfigure.

Are you sure? (y/n)[n]:y

Clear the configuration in the device successfully.

重启交换机

```
<topsec1>reboot
Info: The system is comparing the configuration, please wait.
Warning: All the configuration will be saved to the next startup configuration.
```

Continue ? [y/n]:y

It will take several minutes to save configuration file, please wait..........

Configuration file had been saved successfully

Note: The configuration file will take effect after being activated

## 二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP

VLAN管理

### 实验四、VLAN划分

实验目标

了解交换机VLAN的原理

熟练掌握华为二层交换机VLAN的划分

掌握华为验证VLAN的划分的方法

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 1](/images/network-notes/huawei-switch-labs/s2/img-09.webp)

实验拓扑

实验需求

交换机划分两个基于端口的VLAN：VLAN10、VLAN20

| VLAN | 端口 |
| --- | --- |
| 10 | 1，2 |
| 20 | 3，4 |

使得VLAN10 的成员能够相互访问，VLAN20的成员能够互相访问，VLAN10和VLAN20不能相互访问。

PC1-PC4的网络设置为：

| 设备 | IP地址 | 子网掩码 |
| --- | --- | --- |
| PC1 | 172.16.10.1 | 255.255.255.0 |
| PC2 | 172.16.10.2 | 255.255.255.0 |
| PC3 | 192.168.1.1 | 255.255.255.0 |
| PC4 | 192.168.1.2 | 255.255.255.0 |

PC1、PC2接在VLAN10的成员接口1-2上，两台PC可以ping通；PC3、PC4接在VLAN20的成员接口3-4上，两台PC可以ping通；

配置步骤

PC端地址配置IP地址

略

创建VLAN

```
[Switch]vlan batch 10 20
```

将端口划入相关的VLAN

```
[Swich]interface g0/0/1
[Switch-GigabitEthernet0/0/1]port link-type access
[Switch-GigabitEthernet0/0/1]port default vlan 10
[Swich]interface g0/0/2
[Switch-GigabitEthernet0/0/2]port link-type access
[Switch-GigabitEthernet0/0/2]port default vlan 10
[Swich]interface g0/0/3
[Switch-GigabitEthernet0/0/3]port link-type access
[Switch-GigabitEthernet0/0/3]port default vlan 20
[Swich]interface g0/0/4
[Switch-GigabitEthernet0/0/4]port link-type access
[Switch-GigabitEthernet0/0/4]port default vlan 20
```

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 2](/images/network-notes/huawei-switch-labs/s2/img-10.webp)

查看VLAN配置情况：命令：display vlan

验证相互VLAN间的通信

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 3](/images/network-notes/huawei-switch-labs/s2/img-11.webp)

VLAN 10 PC1与PC2相互通信

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 4](/images/network-notes/huawei-switch-labs/s2/img-12.webp)

VLAN20 PC3 与PC4 相互通信

满足实验要求，配置完成

注意事项

默认情况下，交换下所有的端口都属于VLAN1，因此我们通常把VLAN1作为交换机的管理VLAN，因此VLAN1接口的IP地址就是交换机的管理地址。

### 实验五 跨交换机相同VLAN通信

实验目标

掌握IEEE802.1Q的实现方式，掌握跨二层交换机相同VLAN间通信的调试方法；

掌握交换机的trunk、access接口模式

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 5](/images/network-notes/huawei-switch-labs/s2/img-13.webp)

实验拓扑

实验需求

在两台交换机上分别划分两个基于端口的VLAN：VLAN10、VLAN20。

| VLAN | 交换机 | 端口 |
| --- | --- | --- |
| 10 | SW1, SW2 | 1 |
| 20 | SW1, SW2 | 2 |

使得VLAN10 的成员能够相互访问，VLAN20的成员能够互相访问，VLAN10和VLAN20默认不能互访。

PC1-PC4的网络设置为：

| 设备 | IP地址 | 子网掩码 |
| --- | --- | --- |
| PC1 | 172.16.10.1 | 255.255.255.0 |
| PC2 | 172.16.10.2 | 255.255.255.0 |
| PC3 | 192.168.1.1 | 255.255.255.0 |
| PC4 | 192.168.1.2 | 255.255.255.0 |

PC1、PC2接SW1的1-2端口，；PC3、PC4接SW2的1-2端口，PC1与PC3同属VLAN10，PC2与PC4同属VLAN20。

配置步骤

配置SW1与SW2各自VLAN

```
[SW1]vlan batch 10 20
[SW2]vlan batch 10 20
```

将端口划入相关的VLAN

SW1

```
[SW1]interface Ethernet0/0/1
[SW1-Ethernet0/0/1]port link-type access
[SW1-Ethernet0/0/1]port default vlan 10
[SW1]interface g0/0/2
[SW1-Ethernet0/0/2]port link-type access
[SW1-Ethernet0/0/2]port default vlan 20
```

SW2

```
[SW2]interface g0/0/1
[SW2-Ethernet0/0/1]port link-type access
[SW2-Ethernet0/0/1]port default vlan 10
[SW2]interface g0/0/2
[SW2-Ethernet0/0/2]port link-type access
[SW2-Ethernet0/0/2]port default vlan 20
```

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 6](/images/network-notes/huawei-switch-labs/s2/img-14.webp)

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 7](/images/network-notes/huawei-switch-labs/s2/img-15.webp)

校验两台交换机VLAN配置情况：

配置交换机互连trunk 链路

SW1

```
[SW1]interface g0/0/1
[SW1-GigabitEthernet0/0/1]port link-type trunk
[SW1-GigabitEthernet0/0/1]port trunk allow-pass vlan 10 20
```

SW2

```
[SW1]interface g0/0/1
[SW1-GigabitEthernet0/0/1]port link-type trunk
[SW1-GigabitEthernet0/0/1]port trunk allow-pass vlan 10 20
```

查看TRUNK配置状态

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 8](/images/network-notes/huawei-switch-labs/s2/img-16.webp)

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 9](/images/network-notes/huawei-switch-labs/s2/img-17.webp)

通过命令：display port vlan

验证VLAN相互通信

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 10](/images/network-notes/huawei-switch-labs/s2/img-18.webp)

VLAN10的连通情况，通过PC1 与PC3通信

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 11](/images/network-notes/huawei-switch-labs/s2/img-19.webp)

VLAN20的连通情况，通过PC2 与PC4通信

跨交换机的相同VLAN可以实现通信，实验完成

注意事项

Trunk 接口默认只允许 VLAN 1 通过，所以配置允许 VLAN10 、VLAN20 通过

### 实验六 hybrid 接口互连

实验目标

掌握Hybrid接口的作用，与ACCESS、Trunk的区别

掌握Hybrid接口的适用场景，配置方法

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 12](/images/network-notes/huawei-switch-labs/s2/img-20.webp)

实验拓扑

实验需求

通过配置Hybrid端口使得两个不同的VLAN终端可以互通

配置步骤

交换机建立VLAN

```
[SW1]vlan batch 10 20
```

将端口划入相关的VLAN

SW1

```
[SW1]interface g0/0/1
[SW1-GigabitEthernet0/0/1]port link-type hybrid
[SW1-GigabitEthernet0/0/1]port hybrid pvid vlan 10
[SW1-GigabitEthernet0/0/1]port hybrid untagged vlan 10 20
[SW1]interface g0/0/2
[SW1-GigabitEthernet0/0/2]port link-type hybrid
[SW1-GigabitEthernet0/0/2]port hybrid pvid vlan 20
[SW1-GigabitEthernet0/0/2]port hybrid untagged vlan 10 20
```

校验交换机VLAN配置情况：

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 13](/images/network-notes/huawei-switch-labs/s2/img-21.webp)

操作命令：Display vlan 可以看到G0/0/1 G0/0/2既属于VLAN10 也属于VLAN20

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 14](/images/network-notes/huawei-switch-labs/s2/img-22.webp)

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 15](/images/network-notes/huawei-switch-labs/s2/img-23.webp)

配置终端地址

验证终端跨VLAN相互通信

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 16](/images/network-notes/huawei-switch-labs/s2/img-24.webp)

通过PC1 与PC2通信

可以看到通信正常，也实现了不同VLAN之间的通信，但是他们都是属于同一个三层子网

### 实验七 VLAN间互访-单臂路由

实验目标

掌握单臂路由的逻辑原理

掌握单臂路由的配置方法

实验拓扑

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 17](/images/network-notes/huawei-switch-labs/s2/img-25.webp)

实验需求

SW1 , SW2两台交换机都有VLAN10,VLAN20，根据拓扑跨交换机的相同VLAN可以相互通信，但不同VLAN不能直接通信，要求实现不同的VLAN间相互可通信。地址信息如下：

PC1-PC4的网络设置为：

| 设备 | VLAN | IP地址 | 子网掩码 | 默认网关 |
| --- | --- | --- | --- | --- |
| PC1 | 10 | 172.16.10.1 | 255.255.255.0 | 172.16.10.254 |
| PC2 | 20 | 192.168.1.1 | 255.255.255.0 | 192.168.1.254 |
| PC3 | 10 | 172.16.10.2 | 255.255.255.0 | 172.16.10.254 |
| PC4 | 20 | 192.168.1.2 | 255.255.255.0 | 192.168.1.254 |

配置步骤

配置SW1与SW2各自VLAN

```
[SW1]vlan batch 10 20
[SW2]vlan batch 10 20
```

将端口划入相关的VLAN

SW1

```
[SW1]interface g0/0/1
[SW1-GigabitEthernet0/0/1]port link-type access
[SW1-GigabitEthernet0/0/1]port default vlan 10
[SW1]interface g0/0/2
[SW1-GigabitEthernet0/0/2]port link-type access
[SW1-GigabitEthernet0/0/2]port default vlan 20
```

SW2

```
[SW2]interface g0/0/1
[SW2-GigabitEthernet0/0/1]port link-type access
[SW2-GigabitEthernet0/0/1]port default vlan 10
[SW2]interface g0/0/2
[SW2-GigabitEthernet0/0/2]port link-type access
[SW2-GigabitEthernet0/0/2]port default vlan 20
```

校验两台交换机VLAN配置情况：

配置交换机互连trunk 链路

SW1

```
[SW1]interface g0/0/24
[SW1-GigabitEthernet0/0/24]port link-type trunk
[SW1-GigabitEthernet0/0/24]port trunk allow-pass vlan 10 20
```

SW2

```
[SW2]interface g0/0/24
[SW2-GigabitEthernet0/0/24]port link-type trunk
[SW2-GigabitEthernet0/0/24]port trunk allow-pass vlan 10 20
```

查看TRUNK配置状态

通过命令：display port vlan

验证VLAN相同相互通信

VLAN10的连通情况，通过PC1 与PC3可通信

VLAN20的连通情况，PC2与PC4可正常通信。

VLAN10、VLAN20的连通情况，通过PC1与PC2通信，结果如下：

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 24](/images/network-notes/huawei-switch-labs/s2/img-26.webp)

由于跨越不同的网段没有路由，通信失败

配置单臂路由

交换机配置

```
[SW1]interface g0/0/23
[SW1-GigabitEthernet0/0/23]port link-type trunk
[SW1-GigabitEthernet0/0/23]port trunk allow-pass vlan 10 20
```

路由器配置

```
[AR1]interface g0/0/0
```

[AR1- GigabitEthernet0/0/0]undo shutdown

```
[AR1]interface g0/0/0.10
[AR1-GigabitEthernet0/0/0.10]dot1q termination vid 10
[AR1-GigabitEthernet0/0/0.10]ip address 172.16.10.254 255.255.255.0
[AR1-GigabitEthernet0/0/0.10]arp broadcast enable
[AR1]int g0/0/0.20
[AR1-GigabitEthernet0/0/0.20]dot1q termination vid 20
[AR1-GigabitEthernet0/0/0.20]ip address 192.168.1.254 255.255.255.0
[AR1-GigabitEthernet0/0/0.20]arp broadcast enable
```

查看路由器接口地址

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 25](/images/network-notes/huawei-switch-labs/s2/img-27.webp)

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 26](/images/network-notes/huawei-switch-labs/s2/img-28.webp)

配置PC1、PC2、PC3、PC4相对应的VLAN网关，如下图PC1网关：

其他PC根据各自的网关配置，此处略

验证配置情况

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 27](/images/network-notes/huawei-switch-labs/s2/img-29.webp)

VLAN10与VLAN20通信，PC1与PC2相互PING。

PING结果显示，PC1与PC2可达。

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 28](/images/network-notes/huawei-switch-labs/s2/img-30.webp)

验证 PC3与PC4相互PING

根据PING结果，PC3与PC4可以相互通信。

注意事项

单臂路由分为主接口与子接口，主接口必须开启后子接口才正常工作，另外IP地址是配置在子接口下，并绑定相应的VLAN，打开ARP广播，实现单臂路由。

### 实验八 VLAN间互访-多层交换

实验目标

理解多层交换机的路由原理

掌握不同VLAN间的SVI路由实现方法

了解多层交换机在网络中的常用配置

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 29](/images/network-notes/huawei-switch-labs/s2/img-31.webp)

实验拓扑

实验需求

SW1 , SW2两台交换机连接至CORE交换机，都有VLAN10,VLAN20，根据拓扑跨交换机的相同VLAN可以相互通信，但不同VLAN不能直接通信，要求使用多层交换机实现不同的VLAN间相互可通信。地址信息如下：

PC1-PC4的网络设置为：

| 设备 | VLAN | IP地址 | 子网掩码 | 默认网关 |
| --- | --- | --- | --- | --- |
| PC1 | 10 | 172.16.10.1 | 255.255.255.0 | 172.16.10.254 |
| PC2 | 20 | 192.168.1.1 | 255.255.255.0 | 192.168.1.254 |
| PC3 | 10 | 172.16.10.2 | 255.255.255.0 | 172.16.10.254 |
| PC4 | 20 | 192.168.1.2 | 255.255.255.0 | 192.168.1.254 |

配置步骤

配置SW1、SW2、Core各自VLAN

```
[SW1]vlan batch 10 20
[SW2]vlan batch 10 20
[Core]vlan batch 10 20
```

SW1,SW2交换机端口划入相关的VLAN

SW1

```
[SW1]interface g0/0/1
[SW1-GigabitEthernet0/0/1]port link-type access
[SW1-GigabitEthernet0/0/1]port default vlan 10
[SW1]interface g0/0/2
[SW1-GigabitEthernet0/0/2]port link-type access
[SW1-GigabitEthernet0/0/2]port default vlan 20
```

SW2

```
[SW2]interface g0/0/1
[SW2-GigabitEthernet0/0/1]port link-type access
[SW2-GigabitEthernet0/0/1]port default vlan 10
[SW2]interface g0/0/2
[SW2-GigabitEthernet0/0/2]port link-type access
[SW2-GigabitEthernet0/0/2]port default vlan 20
```

配置交换机SW1、SW2与CORE交换机互连trunk

SW1

```
[SW1]interface g0/0/23
[SW1-GigabitEthernet0/0/23]port link-type trunk
[SW1-GigabitEthernet0/0/23]port trunk allow-pass vlan 10 20
```

SW2

```
[SW2]interface g0/0/24
[SW2-GigabitEthernet0/0/24]port link-type trunk
[SW2-GigabitEthernet0/0/24]port trunk allow-pass vlan 10 20
```

CORE

```
[Core]interface g0/0/23
[Core-GigabitEthernet0/0/23]port link-type trunk
[Core-GigabitEthernet0/0/23]port trunk allow-pass vlan
[Core-GigabitEthernet0/0/23]int g0/0/24
[Core-GigabitEthernet0/0/24]port link-type trunk
[Core-GigabitEthernet0/0/24]port trunk allow-pass vlan 10 20
```

配置SVI接口，为各VLAN提供路由

```
[Core]interface Vlanif 10
[Core-Vlanif10]ip address 172.16.10.254 255.255.255.0
[Core-Vlanif10]quit
[Core]interface Vlanif 20
[Core-Vlanif20]ip address 192.168.1.254 255.255.255.0
[Core-Vlanif20]quit
```

配置各PC相对应的VLAN网关，如下图：

其他PC根据各自的VLAN所对应的网关配置，此处略

验证各VLAN相互通信

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 31](/images/network-notes/huawei-switch-labs/s2/img-32.webp)

VLAN10与VLAN20通信，PC1与PC2相互PING。

PING结果显示，PC1与PC2可达。

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 32](/images/network-notes/huawei-switch-labs/s2/img-33.webp)

验证 PC3与PC4相互PING

根据PING结果，PC3与PC4可以相互通信。

注意事项

华为交换机VLAN trunk链路默认禁止所有VLAN通过，必须单独允许通过的VLAN，否则网络不通。

### 实验九 GVRP配置

实验目标

掌握GVRP工作原理

掌握GRVP 的模式

掌握GRVP的配置方法

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 33](/images/network-notes/huawei-switch-labs/s2/img-34.webp)

实验拓扑

实验需求

CORE作为核心交换机，允许编辑VLAN

SW1从CORE同步VLAN，也可以自己创建VLAN

SW2自己维护自己的VLAN表，不同步其他设备，也不被其他设备同步。

配置要点

配置各交换机互连TRUNK

开启GVRP

设置GVRP模式

配置步骤

配置交换机SW1、SW2与CORE交换机互连Trunk

SW1

```
[SW1]interface g0/0/23
[SW1-GigabitEthernet0/0/23]port link-type trunk
[SW1-GigabitEthernet0/0/23]port trunk allow-pass vlan all
```

SW2

```
[SW2]interface g0/0/24
[SW2-GigabitEthernet0/0/24]port link-type trunk
[SW2-GigabitEthernet0/0/24]port trunk allow-pass vlan all
```

CORE

```
[Core]interface g0/0/23
[Core-GigabitEthernet0/0/23]port link-type trunk
[Core-GigabitEthernet0/0/23]port trunk allow-pass vlan
[Core-GigabitEthernet0/0/23]int g0/0/24
[Core-GigabitEthernet0/0/24]port link-type trunk
[Core-GigabitEthernet0/0/24]port trunk allow-pass vlan all
```

配置各交换机GVRP及模式

CORE

```
[Core-GigabitEthernet0/0/23]gvrp
[Core-GigabitEthernet0/0/23]gvrp registration normal
[Core-GigabitEthernet0/0/24]gvrp
[Core-GigabitEthernet0/0/24]gvrp registration normal
```

SW1

```
[SW1]interface g0/0/23
[SW1-GigabitEthernet0/0/23]gvrp
[SW1-GigabitEthernet0/0/23]gvrp registration normal
```

SW2

```
[SW2]interface g0/0/24
[SW2-GigabitEthernet0/0/24]gvrp
[SW2-GigabitEthernet0/0/24]gvrp registration forbidden
```

验证：

在CORE交换机创建多个VLAN。

命令：[Core]vlan batch 10 20 30 40

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 34](/images/network-notes/huawei-switch-labs/s2/img-35.webp)

查看VLAN配置情况 命令：display vlan summary

查看SW1交换机的VLAN数量

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 35](/images/network-notes/huawei-switch-labs/s2/img-36.webp)

可以看到当前已经从CORE交换机学习到VLAN,保存到动态VLAN表里。

![二、实验四～九：VLAN、hybrid、单臂路由、多层交换、GVRP 示意图 36](/images/network-notes/huawei-switch-labs/s2/img-37.webp)

查看SW2交换机的VLAN信息

SW2交换机配置了GVRP的fordidden模式，所有VLAN信息不会被同步。

注意事项

GVRP 把VLAN分为静态VLAN（自动创建） 动态VLAN（学习到）

GVRP normal 模式 可以同步其他交换机，也可以被同步，静态、动态都可以

GVRP Fixed 模式 不接受动态VLAN，可以同步自己的VLAN到Normal模式

GVRP forbidden 禁止模式，相当于是关闭GVRP同步

## 三、实验十～十三：STP、MSTP、链路聚合、端口镜像

### 实验十 STP（生成树）

实验目标

掌握STP 的工作原理

掌握STP根桥的作用

掌握STP 的类型

掌握STP 的特性

掌握STP 根防护

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 1](/images/network-notes/huawei-switch-labs/s3/img-38.webp)

实验拓扑

实验需求

CORE_1交换机为根CORE_2为备份备份根桥

SW1作为接入交换机，如果其他交换机试图接入网络并抢夺根桥角色，将其所连接的端口down掉。

配置步骤

将4个VLAN配置到所有交换机，并配置交换机互连TRUNK

配置3台交换机以下命令：

CORE_1

```
[CORE_1]vlan batch 10 20 30 40
[CORE_1]int g0/0/22
[CORE_1-GigabitEthernet0/0/22]port link-type trunk
[CORE_1-GigabitEthernet0/0/22]port trunk allow-pass vlan all
[CORE_1]int g0/0/23
[CORE_1-GigabitEthernet0/0/23]port link-type trunk
[CORE_1-GigabitEthernet0/0/23]port trunk allow-pass vlan all
```

CORE_2与SW1交换机配置参考CORE_1配置。

配置交换机主根桥，备份根桥

CORE_1

```
[CORE_1]stp enable
[CORE_1]stp mode stp
[CORE_1]stp root primary
```

CORE_2

```
[CORE_2]stp enable
[CORE_2]stp mode stp
[CORE_2]stp root secondary
```

SW1

```
[SW1]stp enable
[SW1]stp mode stp
```

查看两台核心交换机的生成树状态

命令：display stp

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 2](/images/network-notes/huawei-switch-labs/s3/img-39.webp)

CORE_1

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 3](/images/network-notes/huawei-switch-labs/s3/img-40.webp)

CORE_2

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 4](/images/network-notes/huawei-switch-labs/s3/img-41.webp)

查看SW1的生成树情况

可以看到CORE_1为根桥优先级为0 ，CORE_2为备份根桥优先级为4096，SW1非根桥优先级为32768。

查看三台交换机的端口角色。命令：display stp brief

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 5](/images/network-notes/huawei-switch-labs/s3/img-42.webp)

CORE_1

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 6](/images/network-notes/huawei-switch-labs/s3/img-43.webp)

CORE_2

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 7](/images/network-notes/huawei-switch-labs/s3/img-44.webp)

SW1

配置交换机根防护

在SW1交换机执行如下命令：

```
[SW1]interface g0/0/1
[SW1-GigabitEthernet0/0/1]stp root-protection
```

测试根防护

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 8](/images/network-notes/huawei-switch-labs/s3/img-45.webp)

在SW1交换机的1口接入一台STP优先级置为0且互连接口为trunk的交换机。如下图：

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 9](/images/network-notes/huawei-switch-labs/s3/img-46.webp)

此时交换机SW1会根据设置的根防护原则，将新加入的交换机所对应接口置为DISCARDING，阻塞状态。

注意事项

华为交换机STP 支持STP RSTP MSTP

RSTP 快速生成树与STP的配置方法一致，与STP的区别是比STP收敛更快

配置根防护一定是在可能会造成抢夺根桥的端口上

### 实验十一 MSTP（多生成树）

实验目标

掌握MSTP 的工作原理

掌握MSTP 负载的方式

掌握MSTP 配置方法

实验拓扑

实验需求

CORE_1交换机作为VLAN_10,VLAN_20的根。CORE_2作为VLAN_30,VLAN_40的根，并相互根桥

SW1作为接入交换机，访问VLAN10的数据通过CORE_1交换机转发，访问VLAN_30,40的数据由CORE_2负责转发。实验负载均衡的目的

配置步骤

将4个VLAN配置到所有交换机，并配置交换机互连TRUNK

配置3台交换机以下命令：

CORE_1

```
[CORE_1]vlan batch 10 20 30 40
[CORE_1]int g0/0/22
[CORE_1-GigabitEthernet0/0/22]port link-type trunk
[CORE_1-GigabitEthernet0/0/22]port trunk allow-pass vlan all
[CORE_1]int g0/0/23
[CORE_1-GigabitEthernet0/0/23]port link-type trunk
[CORE_1-GigabitEthernet0/0/23]port trunk allow-pass vlan all
```

CORE_2与SW1交换机配置参考CORE_1配置。

配置MST

CORE_1

```
[CORE_1]stp mode mstp
[CORE_1]stp region-configuration
[CORE_1-mst-region]region-name topsec.com
[CORE_1-mst-region]instance 1 vlan 10 20
[CORE_1-mst-region]instance 2 vlan 30 40
[CORE_1-mst-region]active region-configuration
```

CORE_2

```
[CORE_2]stp mode mstp
[CORE_2]stp region-configuration
[CORE_2-mst-region]region-name topsec.com
[CORE_2-mst-region]instance 1 vlan 10 20
[CORE_2-mst-region]instance 2 vlan 30 40
[CORE_2-mst-region]active region-configuration
```

SW1

```
[SW1]stp mode mstp
[SW1]stp region-configuration
[SW1-mst-region]region-name topsec.com
[SW1-mst-region]instance 1 vlan 10 20
[SW1-mst-region]instance 2 vlan 30 40
[SW1-mst-region]active region-configuration
```

查看两台核心交换机的生成树状态

命令：display stp region-configuration

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 11](/images/network-notes/huawei-switch-labs/s3/img-47.webp)

CORE_1

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 12](/images/network-notes/huawei-switch-labs/s3/img-48.webp)

CORE_2

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 13](/images/network-notes/huawei-switch-labs/s3/img-49.webp)

查看SW1的生成树情况

配置CORE_1为instance1的根桥instance2为备份根桥，配置CORE_2为Instance1的备份根桥，instance2的根桥

```
[CORE_1]stp instance 1 root primary
[CORE_1]stp instance 2 root secondary
[CORE_2]stp instance 1 root secondary
[CORE_2]stp instance 2 root primary
```

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 14](/images/network-notes/huawei-switch-labs/s3/img-50.webp)

查看SW1的路径选择 命令：display stp brief

根据SW1的显示结果，可以得出 实例1走G0/0/22口（CORE_1），实例2走G0/0/24口（CORE_2），可以实现负载均衡，也是多实例STP

注意事项

配置MSTP 不能设置GVRP为forbidden模式

### 实验十二 链路聚合

实验目标

掌握多条链路聚合的作用

掌握链路聚合的配置方法

掌握链路聚合的负载均衡模式

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 15](/images/network-notes/huawei-switch-labs/s3/img-51.webp)

实验拓扑

实验需求

配置端口聚合，使得两台交换机可以相互通信

配置步骤

配置链路聚合

配置SW1

```
[SW1]interface Eth-Trunk 1
[SW1-Eth-Trunk1]mode lacp-static
[SW1]interface g0/0/23
[SW1-GigabitEthernet0/0/23]eth-trunk 1
[SW1-GigabitEthernet0/0/23]int g0/0/24
[SW1-GigabitEthernet0/0/24]eth-trunk 1
[SW1-GigabitEthernet0/0/24]quit
```

配置SW2

```
[SW2]interface Eth-Trunk 1
[SW2-Eth-Trunk1]mode lacp-static
[SW2]interface g0/0/23
[SW2-GigabitEthernet0/0/23]eth-trunk 1
[SW2-GigabitEthernet0/0/23]int g0/0/24
[SW2-GigabitEthernet0/0/24]eth-trunk 1
[SW2-GigabitEthernet0/0/24]quit
```

查看Eth-trunk配置

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 16](/images/network-notes/huawei-switch-labs/s3/img-52.webp)

```
[SW1]display eth-trunk
```

以上红色部分显示了运行的模式，负载均衡的方式，以及被捆进来的接口，和各个接口的状态。此时二个接口 down 掉任何一个， eth-trunk 接口都不会 down 。

之后在eth-trunk端口配置相关模式，例如端口为access或者trunk 无需单独在物理端口配置。

注意事项

配好Eth-trunk组后后，在Eth-trunk接口下配的参数会对所有物理接口生效，但对单个物理接口配置的只对单物理接口生效。

两边交换机的Eth-trunk组号码可以采用不同号码。

多个接口捆绑成单条Eth-trunk后，在STP中，被当作单条链路来计算，同时 Path Cost值会和原物理链路有所不同

最多支持8条线路捆绑，且线路的连接方式两端必须一致，比如两端的速率、带宽，类型

### 实验十三 端口镜像

实验目标

掌握端口镜像的作用

掌握端口镜像的配置方法

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 17](/images/network-notes/huawei-switch-labs/s3/img-53.webp)

实验拓扑

实验需求

PC1与PC2相互通信，通过端口镜像的功能将双方通信的信息转发到3口目标端口，并在3口上使用Wireshark协议分析软件进行收集分析。

配置步骤

配置交换机端口镜像

```
[Huawei]observe-port 1 interface g0/0/3 //作为目标端口
[Huawei]interface g0/0/1
[Huawei-GigabitEthernet0/0/1]port-mirroring to observe-port 1 both 作为源端口
[Huawei-GigabitEthernet0/0/1]int g0/0/2
[Huawei-GigabitEthernet0/0/2]port-mirroring to observe-port 1 both 作为源端口
```

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 18](/images/network-notes/huawei-switch-labs/s3/img-54.webp)

安装Wireshark并打开此协议分析软件

根据连接交换机的接口选择捕获数据包，比如通过网线连接选择以太网卡。

PC1-与PC2进行PING测试

PC的IP地址为：192.168.1.1 ；PC2的地址192.168.1.2

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 19](/images/network-notes/huawei-switch-labs/s3/img-55.webp)

查收在wireshark客户端接收到的PC1与PC2连接的PING数据包。如下图：

首先会看到PC 请求ARP信息，查看自己的IP地址为否被占用。每个刚开机的电脑或者网卡重启都会发此ARP信息。

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 20](/images/network-notes/huawei-switch-labs/s3/img-56.webp)

![三、实验十～十三：STP、MSTP、链路聚合、端口镜像 示意图 21](/images/network-notes/huawei-switch-labs/s3/img-57.webp)

在看PING数据包，能看到两台PC 之间相互请求，回复。

注意事项

交换机上支持最多两个配置会话

源和目标的速率要一致。

当一个接口变成目标端口后，所有配置丢失，关闭镜像后，则配置恢复。

目标不能是安全端口，也不能是源。
