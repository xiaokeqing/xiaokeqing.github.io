---
title: "DNS 部署与安全：域名结构、解析与攻防"
date: 2026-10-19T10:00:00+08:00
draft: false
categories: ["课程笔记", "Windows 服务基础"]
tags: ["Windows Server", "DNS", "课程笔记"]
summary: "域名组成、DNS 解析的递归与迭代、正向/反向解析与记录类型，以及 DNS 劫持、欺骗与投毒的区别和防护。"
description: "域名组成、DNS 解析的递归与迭代、正向/反向解析与记录类型，以及 DNS 劫持、欺骗与投毒的区别和防护。"
ShowToc: true
---

> 来源：Windows 服务基础课程讲义（`DNS部署与安全.pdf`，共 11 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 1、DNS

Domain Name Service域名服务作用：为客户机提供域名解析服务器（域名 -- 解析为 -- IP地址）

## 2、域名组成

### 2.1、域名组成概述

如"www.sina.com."是一个域名"sina.com"才被称为域名(全球唯一)

"www"是主机名。

"主机名.域名后缀"称为完全限定域名(FQDN)。（FQDN完整合格的域名）FQDN=Full Quality Domain Name

```
www.    sina.     com       .
```

主机名   二级域名   顶级域名   根域

```
www.      topsec.   com.   cn      .
```

主机名     三级       二级   顶级     根案例：

```
购买了域名sina.com ,花了500万
sina.com       ----  3.3.3.3
www.sina.com   ----  3.3.3.3    注册到DNS服务器上去！(备案)
blog.sina.com  ----  4.4.4.4    注册到DNS服务器上去！
bbs.sina.com   ----  5.5.5.5
nba.sina.com   ----  6.6.6.6
```

### 2.2、域名组成

域名树形结构

![DNS 部署与安全 示意图 1](/images/windows-notes/dns/img-01.png)

根域         .顶级域（也叫一级域名）

国家和地区顶级域  cn  jp  hk  tw  uk

商业顶级域

```
com    商业机构
gov    政府机构
mil    军事机构
edu    教育机构
org    民间组织架构
net    互联网
```

二级域名

如：www.baidu.com.

.为根域com为顶级域baidu为二级域名www为主机名万网

```
map.baidu.com
FQDN=主机名.DNS后缀
```

FQDN（完整合格的域名）

如：

```
www.baidu.com.（完整合格的域名）
baidu.com.为域名后缀
```

www为主机名也有教科书上称DNS后缀为FQDN

## 3、监听端口

DNS服务监听端口：

```
53  udp/tcp
```

## 4、DNS解析种类

### 4.1、按照查询方式分类：

客户机 通过域名www.baidu.com上网的过程

1）检查本机是否有该域名的缓存信息 ipconfig /displaydns

2）hosts文件   c:\windows\system32\dirvers\etc\hosts

3）dns服务器   114.114.114.114

4）dns服务器接收域名之后分析

1、分析有没有缓存过该地址  114.114.114.114 分析

2、如果dns没有缓存过该地址记录，看看自己有没有配置转发dns（8.8.8.8）

3、如果没有配置dns转发服务器，当前dns服务器开始分析域名结构

```
www .baidu .com .
```

1）递归查询：客户机与本地DNS服务器之间 ,DNS服务器转发器的过程也是递归查询

2）迭代查询：本地DNS服务器与根等其他DNS服务器的解析过程

![DNS 部署与安全 示意图 2](/images/windows-notes/dns/img-02.png)

### 4.2、按照查询内容分类：

1）正向解析：已知域名，解析IP地址

2）反向解析：已知IP地址，解析域名

## 5、客户机域名请求解析顺序

1.DNS缓存----2.本地hosts文件--3.找本地DNS服务器hosts文件路径：c:\windows\system32\drivers\etc\hosts win7之后得系统，若要修改hosts文件，需要给自己添加NTFS权限，才可以修改！！

hosts文件得格式：1.1.1.1  www.teacher.com

## 6、DNS服务器处理域名请求的顺序

1）DNS高速缓存（学生必须学会如何查看及清空  如果区域配置有该域名会删除该缓存）

2）DNS权威区域配置文件（查看自己是否负责该区域，如baidu.com区域）

3）DNS转发器

4）根提示（目前全球只有13个根域服务器）

## 7、DNS服务器部署过程

1）还原快照，开机，桥接vmnet1，配置IP地址，其中要求服务器的IP必须是静态IP地址！

2）安装DNS服务器插件（也就是安装并开启53端口），可以使用netstat  -an验证是否开启了53端口

![DNS 部署与安全 示意图 3](/images/windows-notes/dns/img-03.png)

3）创建区域文件（负责一个域名后缀的解析，如baidu.com为域名后缀，一台DNS服务器内可存放多个区域文件）

![DNS 部署与安全 示意图 4](/images/windows-notes/dns/img-04.png)

![DNS 部署与安全 示意图 5](/images/windows-notes/dns/img-05.png)

4）新建A记录

![DNS 部署与安全 示意图 6](/images/windows-notes/dns/img-06.png)

![DNS 部署与安全 示意图 7](/images/windows-notes/dns/img-07.png)

![DNS 部署与安全 示意图 8](/images/windows-notes/dns/img-08.png)

同时我们也可以解析其他地址因为本身就能找到根服务器

![DNS 部署与安全 示意图 9](/images/windows-notes/dns/img-09.png)

对于解析过的域名dns服务器本身具有缓存

![DNS 部署与安全 示意图 10](/images/windows-notes/dns/img-10.png)

![DNS 部署与安全 示意图 11](/images/windows-notes/dns/img-11.png)

清除缓存后dns之前的解析信息都会清除

## 8、DNS客户机如何解析

1）必须指向DNS服务器

2）手工解析域名：

nslookup  域名

## 9、客户机上关于DNS的命令

如果更新了dns解析，但是用ping等命令测式域名 仍然会显示旧域名原因在缓存学会查看缓存

```
ipconfig  /displaydns       # 显示DNS缓存
ipconfig  /flushdns         # 清空DNS缓存
```

转发dns练习，缓解当前服务器每次寻找根服务器的压力，可以让其指向另一个dns服务器

![DNS 部署与安全 示意图 12](/images/windows-notes/dns/img-12.png)

其优势在于作为dns服务器减少了对每个域名解析时侯去与根服务器沟通的压力

## 10、域名解析记录类型

SOA：权威服务器NS：域名服务器A记录： 正向解析记录  主机名对ip CNAME记录：别名PTR记录：反向解析记录 （反向指针）  ip对域名MX：邮件交换记录（知悉即可）

## 11、练习

1、win7，win2019均桥接到nat，全部能上网，将2019部署为DNS服务器，win7的DNS指向2019，且依然可以上网！（此时2019的DNS服务器是通过找根完成对客户的解析请求！）

2、win2019设置转发器设置为当地dns，提高win7的解析速度，且保证win7依然可以上网！

3、学会查看客户机的本地缓存，win2019DNS服务器上的缓存

4、新建权威本地解析文件：jd.com www--6.6.6.6 写入到hosts文件当中，结果win7无法访问jd网站，然后删除权威文件，测式win7是否可以正常上网！新建权威本地解析文件：teacher.com www--7.7.7.7，并实现员工可以解析www.teacher.com为7.7.7.7

5、（真实机）作业网站可否自己创建域名？
