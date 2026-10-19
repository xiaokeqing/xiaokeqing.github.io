---
title: "网络地址配置与日志服务"
date: 2026-10-19T15:00:00+08:00
draft: false
categories: ["课程笔记", "linux系统"]
tags: ["Linux", "网络", "日志", "课程笔记"]
summary: "ip addr / ip route 的命令行配置与配置文件静态写法、/etc/resolv.conf 的 DNS 设定、systemctl 管理服务自启，以及日志服务的基本用法。"
description: "ip addr / ip route 的命令行配置与配置文件静态写法、/etc/resolv.conf 的 DNS 设定、systemctl 管理服务自启，以及日志服务的基本用法。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`网络地址配置以及日志服务.pdf`，共 22 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

linux 3版本内核   systemd第一个启动的进程systemctl  控制命令   控制进程启动与关闭 ，控制开机后默认的启动项systemctl  控制项  进程名称控制项：start   stop   enable  disable  status get-default  查看当前启动进入的工作模式  图形set-default  设定默认进入的模式关机   救援模式   多用户字符界面   图形界面   重启ip地址配置ip addr  查看ip地址ip addr add ip地址 dev ens33 ip route 网关查看ip route  add default via 网关ip/etc/resolv.conf centos7 和 kali都用nat模式

![网络地址配置与日志服务 示意图 1](/images/linux-notes/network-and-logs/img-01.webp)

背着编辑配置文件，实现dhcp自动获取

![网络地址配置与日志服务 示意图 2](/images/linux-notes/network-and-logs/img-02.webp)

尝试静态配置ip

![网络地址配置与日志服务 示意图 3](/images/linux-notes/network-and-logs/img-03.webp)

kali操作系统静态配置ip地址

![网络地址配置与日志服务 示意图 4](/images/linux-notes/network-and-logs/img-04.webp)

dns设定

![网络地址配置与日志服务 示意图 5](/images/linux-notes/network-and-logs/img-05.webp)

linux系统中的路由转发如何实现拓扑如下实验之前先确定一下自己虚拟机是否存在vment2和vmnet3

![网络地址配置与日志服务 示意图 6](/images/linux-notes/network-and-logs/img-06.webp)

手动添加vmnet2 和 3

![网络地址配置与日志服务 示意图 7](/images/linux-notes/network-and-logs/img-07.webp)

![网络地址配置与日志服务 示意图 8](/images/linux-notes/network-and-logs/img-08.webp)

选择添加

![网络地址配置与日志服务 示意图 9](/images/linux-notes/network-and-logs/img-09.webp)

![网络地址配置与日志服务 示意图 10](/images/linux-notes/network-and-logs/img-10.webp)

以相同的配置建立vmnet3

1、针对客户机win主机确认连接的交换机为vmnet2同时配置ip

![网络地址配置与日志服务 示意图 11](/images/linux-notes/network-and-logs/img-11.webp)

2、建立克隆虚拟机centos7 连接vmnet3同时配置ip地址

![网络地址配置与日志服务 示意图 12](/images/linux-notes/network-and-logs/img-12.webp)

![网络地址配置与日志服务 示意图 13](/images/linux-notes/network-and-logs/img-13.webp)

设定了ip和网关

3、为中间的网关服务器配置ip地址和新网卡

![网络地址配置与日志服务 示意图 14](/images/linux-notes/network-and-logs/img-14.webp)

配置文件修改配置完成后确认

![网络地址配置与日志服务 示意图 15](/images/linux-notes/network-and-logs/img-15.webp)

确定一下对应关系

![网络地址配置与日志服务 示意图 16](/images/linux-notes/network-and-logs/img-16.webp)

4、验证 win客户机 192.168.2.1  ping通172.16.2.1 win验证ping网关

![网络地址配置与日志服务 示意图 17](/images/linux-notes/network-and-logs/img-17.webp)

网关确认路由表分析数据如何返回

![网络地址配置与日志服务 示意图 18](/images/linux-notes/network-and-logs/img-18.webp)

验证

![网络地址配置与日志服务 示意图 19](/images/linux-notes/network-and-logs/img-19.webp)

克隆机确认

![网络地址配置与日志服务 示意图 20](/images/linux-notes/network-and-logs/img-20.webp)

## 实验的核心路由转发开启

![网络地址配置与日志服务 示意图 21](/images/linux-notes/network-and-logs/img-21.webp)

windows验证

验证克隆linux

![网络地址配置与日志服务 示意图 22](/images/linux-notes/network-and-logs/img-22.webp)

日志服务如何去记录的   搭建日志服务器分析日志位置

![网络地址配置与日志服务 示意图 23](/images/linux-notes/network-and-logs/img-23.webp)

进程一般都有配置文件配置文件分析

![网络地址配置与日志服务 示意图 24](/images/linux-notes/network-and-logs/img-24.webp)

全局配置部分

![网络地址配置与日志服务 示意图 25](/images/linux-notes/network-and-logs/img-25.webp)

关于日志记录的一个小验证

![网络地址配置与日志服务 示意图 26](/images/linux-notes/network-and-logs/img-26.webp)

关于日志级别 分析日志级别分析

![网络地址配置与日志服务 示意图 27](/images/linux-notes/network-and-logs/img-27.webp)

手动触发一下日志

![网络地址配置与日志服务 示意图 28](/images/linux-notes/network-and-logs/img-28.webp)

emerg触发

![网络地址配置与日志服务 示意图 29](/images/linux-notes/network-and-logs/img-29.webp)

## 如果有人ssh登录了服务器 清理痕迹

```
systemctl stop rsyslog    |    service rsyslog stop
echo "" > /var/log/secure  登录日志清理
last -f /var/log/wtmp 日志查看  清理同上
apache或者nginx web服务的日志
history -c 历史记录
```

建立日志服务器实现针对以上问题的日志异地备份（备份登录日志）

![网络地址配置与日志服务 示意图 30](/images/linux-notes/network-and-logs/img-30.webp)

1、配置日志客户机修改日志服务的配置文件

![网络地址配置与日志服务 示意图 31](/images/linux-notes/network-and-logs/img-31.webp)

一定要重启服务才能生效  systemctl  restart rsyslog

2、配置日志服务器

![网络地址配置与日志服务 示意图 32](/images/linux-notes/network-and-logs/img-32.webp)

同时添加规则

![网络地址配置与日志服务 示意图 33](/images/linux-notes/network-and-logs/img-33.webp)

重启服务验证systemctl  restart rsyslog

3、验证日志是否会被发送过来windows主机登录日志客户机

![网络地址配置与日志服务 示意图 34](/images/linux-notes/network-and-logs/img-34.webp)

日志服务器验证日志接收

![网络地址配置与日志服务 示意图 35](/images/linux-notes/network-and-logs/img-35.webp)

日志服务器接收规则梳理

  - 格式

  - :属性, 匹配符号,  "值"   保存位置

  - 属性：

fromhost-ip   按照ip地址来接收

  - fromhost  按照发送过来的主机名接收（dns）

  - msg   按照日志内容接收

  - hostname  按照日志内容中的主机名接收

  - 匹配符号：

```
isequal  等于  “172.16.2.254”
startswith  以什么开头  “172.16.2.”
contains 包含 “172”
```

验证

![网络地址配置与日志服务 示意图 36](/images/linux-notes/network-and-logs/img-36.webp)
