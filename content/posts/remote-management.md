---
title: "服务器远程管理：RDP / telnet / SSH"
date: 2026-10-19T12:00:00+08:00
draft: false
categories: ["课程笔记", "windows系统"]
tags: ["Windows Server", "RDP", "运维", "课程笔记"]
summary: "RDP(3389)、telnet(23)、SSH(22) 三种远程管理方式的安全性对比，以及 nmap 扫描端口的基本用法。"
description: "RDP(3389)、telnet(23)、SSH(22) 三种远程管理方式的安全性对比，以及 nmap 扫描端口的基本用法。"
ShowToc: true
---

> 来源：Windows 服务基础课程讲义（`服务器远程管理.pdf`，共 4 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 一、远程管理类型

远程管理服务器有3种常见的类型：

1、远程桌面RDP（图形）：3389 windows服务器常用

2、telnet：23（命令行-不安全-密码明文传输）：windows服务器、linux服务器、路由器、防火墙、交换机等都常用

3、SSH：22  security shell（命令解释器）

（命令行-安全-加密传输）

linux服务器、路由器、防火墙、交换机等都常用服务访问方式：C/S    B/S

## 二、远程桌面

windows远程桌面服务：也叫RDP服务RDP服务：端口3389扫描端口：scanport.exe nmap扫描器之王（后期讲到）

扫描公司内部哪些设备开放了3389：

```
nmap  -p3389,80  10.100.4.2
nmap  -p3389,80-100  10.100.4.2-100
nmap  -p3389,80  10.100.4.0/24
```

实验拓扑图

![服务器远程管理 示意图 1](/images/windows-notes/remote-management/img-01.png)

步骤：

1、首先将PC桥接到用一个vm虚拟网络中，并配置IP地址，实现客户机与服务器可以互通。

2、服务器开启允许被远程控制：桌面右键属性 -- 远程设置 -- 选择允许 -- 确定。

开启后，使用netstat -an命令检查是否开启了3389服务。

注释：netstat -an查看自己对外开放了哪些端口服务！！

3、客户机上：开始 -- 运行 -- 输入mstsc 打开远程连接工具。

开始 -- 运行 -- 输入mstsc -v x.x.x.x

4、在mstsc工具上输入服务器的IP并点击确定。

5、输入服务器的账号及密码。

6、要求win7分别成功连接win2019的桌面！

## 三、telnet

telnet服务：端口23 telnet是一种命令行远程管理方式。

实验拓扑图：

![服务器远程管理 示意图 2](/images/windows-notes/remote-management/img-02.png)

步骤：

1、首先将配置网络，并实现客户机与服务器可以互通。

2、服务器开启允许被telnet远程控制：开始 -- 运行 -- 输入services.msc，并开启telnet服务。

3、客户机上：开始 -- 运行 -- 输入cmd。

4、在命令行窗口中输入：telnet 10.1.1.x，然后输入回车。（如没有telnet命令，安装:开始-运行-control-程序-程序-打开或关闭功能-telnet客户机程序-安装）

5、输入服务器的账号及密码。

![服务器远程管理 示意图 3](/images/windows-notes/remote-management/img-03.png)

## 四、Windows服务管理

打开服务管理窗口

开始--运行--输入services.msc

## 五、实验练习

要求win7分别成功远程连接03和08得RDP及telnet！

打开控制面板命令：开始--运行---输入control linux系统(kali)启动ssh服务

```
sudo systemctl start ssh   #启动
sudo systemctl stop  ssh   #停止
sudo systemctl restart ssh  #重启
sudo systemctl enable ssh  #永久开启（开机自启动）
sudo systemctl disable ssh  #开启不启动
sudo systemctl status ssh  #看服务状态
netstat -antupl
```

客户端连接

```
ssh  y
```
