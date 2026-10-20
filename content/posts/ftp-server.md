---
title: "FTP 服务器：主动/被动模式与用户隔离"
date: 2026-10-19T08:00:00+08:00
draft: false
categories: ["windows系统"]
tags: ["Windows Server", "FTP", "课程笔记"]
summary: "FTP 的 21/20 双端口、主动与被动模式的区别、Windows 下搭建 FTP 站点与用户隔离部署。"
description: "FTP 的 21/20 双端口、主动与被动模式的区别、Windows 下搭建 FTP 站点与用户隔离部署。"
ShowToc: true
---

> 来源：Windows 服务基础课程讲义（`FTP服务器.pdf`，共 5 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

author：讲师

## 0x01 概述

File  Transfor Protocol  === 文件传输协议FTP服务器功能几乎等于445文件共享服务器（SMB）

一般情况：

公司内部文件共享使用FTP/SMB服务公司对外文件共享使用FTP服务器

## 2、FTP协议端口

两个端口：21  20 21端口：控制端口（身份验证、指令传送等）

20端口：数据端口（默认不开启，只有在传输数据瞬间才打开使用，传输完毕，端口也关闭）对2个端口的初步了解，如下：

![FTP 服务器 示意图 1](/images/windows-notes/ftp-server/img-01.webp)

FTP协议有2中连接模式

  - 主动模式

  - 被动模式（默认模式）

## 3、使用IIS发布部署FTP服务器

--实验步骤--

![FTP 服务器 示意图 2](/images/windows-notes/ftp-server/img-02.webp)

1）开启2台虚拟机，，还原快照，开机，桥接到vmnet8，配置IP，并互相ping通！

2）在2019服务器，安装IIS之FTP插件

3）FTP安装完毕后，默认已经对外发布了FTP站点文件夹，路径是c:\inetpub\ftproot

4）此时客户访问：我的电脑---地址栏输入---ftp://10.1.1.2  直接成功访问！

![FTP 服务器 示意图 3](/images/windows-notes/ftp-server/img-03.webp)

![FTP 服务器 示意图 4](/images/windows-notes/ftp-server/img-04.webp)

5）但是不建议使用默认得FTP站点，此时停用默认FTP站点！

6）在D盘上建立文件夹【学习资料】

7）打开IIS，新建FTP站点，并指定【学习资料】路径，勾选全部FTP权限：读取和写入（用户得最终权限为FTP权限和NTFS权限取交集）

8）FTP站点--右键属性--安全账户---取消匿名登录权限；

9）新建student与teacher用户，设置【学习资料】文件夹得NTFS权限，要求student只能下载笔记+视频，并能上传作业，teacher用户拥有完全控制权限

10）最后在客户机上登录FTP服务器，并分别使用student与teacher用户来验证FTP权限！

## 4、ftp命令登录

```
C:\Users\teacher>ftp 192.168.75.131
连接到 192.168.75.131。
220 Microsoft FTP Service
用户(192.168.75.131:(none)): teacher                  用户名
331 Password required for teacher.
密码:                                                 密码
230 User teacher logged in.
ftp>
ftp>
```

匿名登录（前提是服务器允许匿名）

```
C:\Users\teacher>ftp 192.168.75.131
连接到 192.168.75.131。
220 Microsoft FTP Service
用户(192.168.75.131:(none)): anonymous                用户名
331 Password required for teacher.
密码:                                                 无密码
230 User teacher logged in.
ftp>
ftp>
```

## 5、通过kali验证FTP的主被动模式

选择网卡

![FTP 服务器 示意图 5](/images/windows-notes/ftp-server/img-05.webp)

默认为被动模式，直接get下载即可通过passive命令切换主动模式验证

![FTP 服务器 示意图 6](/images/windows-notes/ftp-server/img-06.webp)
