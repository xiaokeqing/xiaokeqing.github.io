---
title: "用户与组管理：/etc/passwd、shadow 与权限模型"
date: 2026-10-19T18:00:00+08:00
draft: false
categories: ["linux系统"]
tags: ["Linux", "用户", "权限", "课程笔记"]
summary: "超级用户/普通用户/程序用户的 UID 划分、Shell 与内核的关系、passwd/shadow/group 的字段含义，以及用户与组管理的常用命令。"
description: "超级用户/普通用户/程序用户的 UID 划分、Shell 与内核的关系、passwd/shadow/group 的字段含义，以及用户与组管理的常用命令。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`用户与组管理.pdf`，共 4 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 0x01 linux用户管理

### 1.1 linux用户分类

超级用户：root    	uid=0       用户身份user identify普通用户：可以登录系统 uid 1000-60000程序用户：程序依托一个用户的权限，权限非常小，不能登陆系统，没有家目录 用来启动程序（进程）uid 1-999

### 1.2 什么是Shell

shell：命令解释器（类似于windows里cmd环境）

```
shell种类：sh  Bash （最流行） Csh  Ksh  Zsh（最高级）
查看当前的shell环境：echo $SHELL
查看当前支持的shell环境列表：cat /etc/shells       ls  /etc/*sh
安装zsh环境：rpm -ivh zsh.....
```

shell与用户，内核的关系，如图：

![用户与组管理 示意图 1](/images/linux-notes/users-groups/img-01.webp)

### 1.3 查看用户信息

/etc/passwd             # 存储着账号信息

/etc/passwd文件格式：

```
root:x:0:0:root:/root:/bin/bash
```

字段1：用户名字段2：密码占位符字段3：uid字段4：gid字段5：用户详细信息（全名，地址，邮件，电话）

字段6：用户的宿主目录/家目录字段7：用户的shell环境

### 1.4 查看用户密码信息

/etc/shadow             # 存储着密码信息

/etc/shadow文件格式：

```
root:%$#EYTF&$GJGItaistd765wq7$$^$0:16282:0:99999:7:3:8:
```

字段1：用户名字段2：密码（SHA512二次加密）

字段3：天数，距离1970年1月1日到最后一次修改密码的天数，也就是最后一次修改密码是哪天 1970unix诞生日字段4：密码最少使用天数   如：7字段5：密码最大使用天数   如：20字段6：密码失效前多少天提醒用户，默认7天字段7：密码非活跃期，密码失效后，账号几天会被停用字段8：密码被停用几天？

字段9：目前没有定义每一个用户都必须拥有一个基本组，多个附加组（公共组）

/etc/group     存储着组账号信息/etc/group文件格式：

```
root:x:0:root
```

字段1：组名字段2：组密码占位符字段3：组id（gid）

字段4：组成员

### 1.5 用户管理命令

#### 创建账号

```
命令：useradd  用户名             # 或者adduser
-u 指定uid号
```

-g 指定基本组-G 指定附加组-M 不需要家目录

-s 指定用户的登录shell 如：/sbin/nologin 不能登陆

#### 临时切换用户

su 用户名                      # 临时切换用户

#### 查看用户简要信息

id 用户名                      # 查看用户信息

#### 设置密码

passwd  用户名                 # 为用户设置密码，不输入用户名则为自己设置密码。

passwd  -d  用户名             # 清空密码

-l 锁定用户                     # /etc/shadow的密码前出现!!符号-u 解锁用户

#### 删除用户

userdel 选项 用户名

-r  删除用户的同时删除用户家目录

#### 修改用户属性

```
usermod 选项 用户名
-u -g -G -s
```

-L 锁定用户                     # /etc/shadow的密码前出现!!符号-U 解锁用户

### 1.6 练习题

1.要求建立出一个名为top2022的组 而且组的ID号是2000

```
groupadd groupdel groupmod -g
```

2.建立一个名为allen的 uid号为1500 基本组是top2022,再建立一个名为top2023的组，作为Allen的附加组

```
useradd  usermod  id
```

3.为allen创建密码，观察状态

```
passwd -S
```

4.锁定该用户使其不能登陆

```
passwd -l  -u
```

5.修改allen用户密码最长有效期90天，并设定账户失效时间，月底失效

```
chage -M  -E
```

6.建立一个名为topuser的用户，要求其uid为200，而且没有家目录，不能登陆系统

```
useradd -s -M
```

## 0x02 linux组管理

### 2.1 查看组信息

```
cat /etc/group
```

/etc/group文件格式：

```
root:x:0:root
```

字段1：组名字段2：组密码占位符字段3：组id（gid）

字段4：组成员

### 2.2 组管理命令

#### 创建组

```
groupadd  组名
-g  指定组id
```

#### 修改gid

groupmod -g 1500 组名

#### 添加成员

gpasswd -a 用户名 组名

#### 删除组

groupdel 组名

### 2.3 练习

1.创建新组ceo

2.将ceo组的id号改为2000

3.创建用户aa及bb

4.将aa用户的附加组设置为ceo，将bb用户的基本组改为ceo组

5.成功删除ceo组
