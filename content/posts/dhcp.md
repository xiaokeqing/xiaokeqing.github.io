---
title: "DHCP 部署与安全：地址池、租约与 DHCP 攻击"
date: 2026-10-19T11:00:00+08:00
draft: false
categories: ["windows系统"]
tags: ["Windows Server", "DHCP", "课程笔记"]
summary: "动态主机配置协议的四个报文、作用域与租约、地址保留，以及 DHCP 饿死攻击与防护。"
description: "动态主机配置协议的四个报文、作用域与租约、地址保留，以及 DHCP 饿死攻击与防护。"
ShowToc: true
---

> 来源：Windows 服务基础课程讲义（`DHCP部署与安全.pdf`，共 10 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## DHCP部署与安全

### 1、DHCP作用

```
Dynamic Host Configure Protoco l
```

动态主机配置协议作用：自动为客户机分配IP地址等参数，子网掩码、网关、dns、租期client 客户端（笔记本） server服务（路由器，dhcp服务器） 结构协议：一种标准，各种服务都 有自己的协议，服务端和客户端都必须遵循这个协议，协议才能使用！

### 2、DHCP服务优点

减少工作量、避免IP冲突、提高地址利用率

### 3、DHCP相关概念

地址池/作用域：（IP、子网掩码、网关、DNS、租期）

DHCP协议端口是 67/68

netstat -an命令查看是否开放端口

### 4、部署DHCP服务器步骤

1）IP地址固定（服务器必须固定IP地址，用什么地址？必须用将来给员工提供得地址在同一网段得IP！）

2）安装DHCP服务插件/软件，输入netstat  -an  验证67/68是否开启！

![DHCP 部署与安全 示意图 1](/images/windows-notes/dhcp/img-01.webp)

![DHCP 部署与安全 示意图 2](/images/windows-notes/dhcp/img-02.webp)

3）打开DHCP软件：开始--管理工具--DHCP，并新建作用域（也就是地址池）及作用域选项

![DHCP 部署与安全 示意图 3](/images/windows-notes/dhcp/img-03.webp)

![DHCP 部署与安全 示意图 4](/images/windows-notes/dhcp/img-04.webp)

4）激活作用域(否，稍后配置)

5）客户机验证：可以图形界面禁用再启用网卡来获取地址，也可以使用命令来完成。

ipconfig  /release  释放IP（取消租约，或者改为手动配置IP，也可以释放租约）

ipconfig  /renew  重新获取IP（有IP时，发送request续约，无IP时发送Discovery重新获取IP）

### 5、地址保留

这对指定的MAC地址，固定动态分配IP地址

### 6、练习实验

1）在2019服务器上部署DHCP服务器，并在win7客户机上验证获取IP地址，并练习ipconfig /release

与ipconfig /renew

2）设置DHCP地址保留，并验证成功性！

### 7、DHCP原理

原理 == 工作过程，也称为DHCP租约过程，分为4个步骤：

（注释：客户机租用IP地址的过程，就好像现实中人租房的过程！）

1）客户机发送DHCP Discovery广播包客户机广播请求IP地址（包含客户机的MAC地址）

255.255.255.255:67 全局广播地址

2）服务器响应DHCP Offer包服务器响应提供的IP地址（但无子网掩码、网关等参数）

（包含一个可用的IP，含义是：哥们，你用这个IP行不？但是并不包含子网掩码、网关dns等参数）

3）客户机发送DHCP Request请求包（我决定使用x.x.x.x这个IP了，请把其他参数都给我吧）

4）服务器发送DHCP ACK确认包服务器确定了租约，并提供网卡详细@参数IP、掩码、网关、DNS、租期等所有报文discover报文-----发现报文，用来发现网络中的DHCP服务器offer报文--------由服务器进行回复，当收到discover报文后，并且服务器本地存在可用IP地址，则回复信息request报文------正式向服务器请求IP地址ack报文----------服务器同意使用该IP地址decline报文------当客户端检测到IP地址冲突时，发送给服务器，用以告知服务器，IP不可用nak报文----服务器拒绝客户端使用该IP地址----一般看不到release报文-----客户端主动释放IP地址。

```
ipconfig /release
ipconfig /renew
```

在win2019部署dhcp服务并抓包验证

![DHCP 部署与安全 示意图 5](/images/windows-notes/dhcp/img-05.webp)

![DHCP 部署与安全 示意图 6](/images/windows-notes/dhcp/img-06.webp)

双击dhcp项后分析最后的状态从发现开始的4个数据包就是整个dhcp租用的过程=======================================

1、discover

![DHCP 部署与安全 示意图 7](/images/windows-notes/dhcp/img-07.webp)

2、offer

![DHCP 部署与安全 示意图 8](/images/windows-notes/dhcp/img-08.webp)

3、request

![DHCP 部署与安全 示意图 9](/images/windows-notes/dhcp/img-09.webp)

4、ack

![DHCP 部署与安全 示意图 10](/images/windows-notes/dhcp/img-10.webp)

### 8、DHCP续约

客户机：

情况1：1h关机走人了，2h回来了还在租期中，再开机，会再次发送Discovery包，服务器直接回应ACK情况2：一直不关机的话，12h的时候，客户机会主动发送Request包请求续约！不成功！87.5%的时候，再次发送Request包请求续约！如还不成功，则直接释放IP地址，重新发送Discovery包，重新全新的获取地址，如依然没反应，则给自己分配一个全球统一的无效IP地址：169.254.x.x/16 用来临时通信。

情况3：1h关机走人了，25h的时候过了租期，回来了，因为租期到期了，优先使用最近使用过的IP，如果ip被别人用了，则按照顺序来分配！

### 9、DHCP攻击与防御

![DHCP 部署与安全 示意图 11](/images/windows-notes/dhcp/img-11.webp)

1）DHCP服务器地址耗尽攻击频繁的发送伪装DHCP发现请求，直到将DHCP地址池资源耗尽使用DHCPig.py软件可以进行DHCP服务器耗尽攻击，dhcpig.py软件下载地址： python https://github.com/kamorin/DHCPig www.github.com 提供所有开发爱好者上传的免费开源的软件软件下载

```
DHCPig-master.zip
Scapy-master.zip
```

安装：

```
unzip Scapy-master.zip   #解压缩
cd Scapy-master          #进入目录
sudo python2 setup.py install   #通过python安装所需要的软件
```

cd ..  #返回上一级目录

```
unzip DHCPig-master.zip
cd DHCPig-master
sudo python2 setup.py install
```

攻击：

```
sudo python2 pig.py eth0            # 从eth0网卡对外开始攻击DHCP服务器，不断的伪装MAC地
址发送Discovery包！
```

![DHCP 部署与安全 示意图 12](/images/windows-notes/dhcp/img-12.webp)

防御方法在交换机（管理型）的端口上做MAC地址数量限制（后期网络中会学习交换机原理和命令）

2）伪装DHCP服务器攻击hack通过将自己部署为DHCP服务器，为客户机提供非法ip地址防御方法在交换机上（管理型），除合法的DHCP服务器所在接口外，全部设置为禁止发送dhcp offer包（后期网络中会学习交换机原理和命令）

注意：不要再真实环境中使用
