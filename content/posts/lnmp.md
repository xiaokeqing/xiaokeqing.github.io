---
title: "LNMP 平台搭建：Nginx + PHP-FPM"
date: 2026-10-19T12:00:00+08:00
draft: false
categories: ["课程笔记", "linux系统"]
tags: ["Linux", "Nginx", "LNMP", "课程笔记"]
summary: "Nginx 的多并发与负载均衡优势、编译安装前建程序用户与装开发包、./configure 参数、默认主页路径，以及配合 PHP-FPM 与 MySQL 组成 LNMP 的步骤。"
description: "Nginx 的多并发与负载均衡优势、编译安装前建程序用户与装开发包、./configure 参数、默认主页路径，以及配合 PHP-FPM 与 MySQL 组成 LNMP 的步骤。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`LNMP.pdf`，共 6 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

web服务，无法支持php解析的。nginx可以实现多并发访问，支持负载均衡。安装nginx前的准备工作

  - 1、要建立一个程序用户用来专门启动nginx

```
[root@localhost Desktop]# useradd -u 250 -s /sbin/nologin -M nginx
[root@localhost Desktop]# id nginx
uid=250(nginx) gid=1001(nginx) groups=1001(nginx)
```

  - 2、提前安装需要用的开发包

```
[root@localhost Desktop]# yum install pcre-devel zlib-devel -y
```

  - 3、解压缩后安装

```
./configure --prefix=/usr/local/nginx --user=nginx --group=nginx
make -j 2  #双核编译
make install
```

  - 4、进入到安装路径进行启动

```
/usr/local/nginx/sbin
```

启动时候遇到的问题分析

![LNMP 平台搭建 示意图 1](/images/linux-notes/lnmp/img-01.webp)

默认主页的存放路径为

/usr/local/nginx/html    目录

如何配合nginx实现 lnmp平台首先验证

![LNMP 平台搭建 示意图 2](/images/linux-notes/lnmp/img-02.webp)

![LNMP 平台搭建 示意图 3](/images/linux-notes/lnmp/img-03.webp)

解决方法 安装 php-fpm，作用是让php编程一个服务端提供服务 开端口 开监听

```
安装php-fpm
yum install php-fpm -y
```

  - 启动

php-fpm &  在后台启动

  - 验证

ss -antpl | grep php-fpm  能够看到9000端口即可

![LNMP 平台搭建 示意图 4](/images/linux-notes/lnmp/img-04.webp)

但是nginx不会主动找9000端口，修改配置文件使其主动连接9000端口对php文件进行解析修改配置文件

![LNMP 平台搭建 示意图 5](/images/linux-notes/lnmp/img-05.webp)

设定配置文件

![LNMP 平台搭建 示意图 6](/images/linux-notes/lnmp/img-06.webp)

识别php页面信息

![LNMP 平台搭建 示意图 7](/images/linux-notes/lnmp/img-07.webp)

遇到 File not found. 出现的问题解决：

解决方法一：

修改nginx的主配置文件。

vi /etc/nginx/nginx.conf location ~ .php$ {root           html;fastcgi_pass   127.0.0.1:9000;fastcgi_index  index.php;fastcgi_param  SCRIPT_FILENAME  $document_root$fastcgi_script_name;include        fastcgi_params;}将 fastcgi_param SCRIPT_FILENAME /scripts$fastcgi_script_name;修改为fastcgi_param  SCRIPT_FILENAME  $document_root$fastcgi_script_name;

修改完成后使用下面命令重新加载nginx配置：

nginx -s reload重新启动nginx解决方法二：

修改php-fpm配置文件vi /etc/php-fpm.d/www.conf查找apache:/apache修改属主和属组，这里我修改为nginx为例。

修改完毕后重启php-fpm。

systemctl restart php-fpm利用lnmp实现农场复现

![LNMP 平台搭建 示意图 8](/images/linux-notes/lnmp/img-08.webp)

验证

![LNMP 平台搭建 示意图 9](/images/linux-notes/lnmp/img-09.webp)
