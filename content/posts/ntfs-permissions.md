---
title: "NTFS 安全权限：文件系统、权限与共享"
date: 2026-10-19T14:00:00+08:00
draft: false
categories: ["课程笔记", "windows系统"]
tags: ["Windows Server", "NTFS", "权限", "课程笔记"]
summary: "FAT32/NTFS/EXT 的差别、NTFS 权限的继承与累加、拒绝优先、取得所有权与 EFS 加密。"
description: "FAT32/NTFS/EXT 的差别、NTFS 权限的继承与累加、拒绝优先、取得所有权与 EFS 加密。"
ShowToc: true
---

> 来源：Windows 服务基础课程讲义（`NTFS安全权限.pdf`，共 7 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 一、NTFS权限概述

1、通过设置NTFS权限，实现不同的用户对文件访问不同的权限

2、分配了正确的访问权限后，用户才能访问其资源

3、设置权限防止资源被篡改、删除

![NTFS 安全权限 示意图 1](/images/windows-notes/ntfs-permissions/img-01.png)

## 二、文件系统概述

文件系统即在存储设备上组织文件的方法（磁盘文件的存储方式）

常用的文件系统：

•FAT32        windows

•NTFS         windows

•EXT 和 XFS   linux常见

![NTFS 安全权限 示意图 2](/images/windows-notes/ntfs-permissions/img-02.png)

## 三、NTFS文件系统特点（考点）

1. 提高磁盘读写性能

2. 可靠性

  - 加密文件系统

  - 访问控制列表（安全权限）

3. 磁盘利用率

  - 压缩

  - 磁盘配额

4. 支持单个文件大于4个G

## 四、修改NTFS权限

### 4.1、取消权限继承

作用：取消后，可以任意修改权限列表了。

方法：文件夹右键属性---安全---高级---去掉第一个对号--选择复制即可

![NTFS 安全权限 示意图 3](/images/windows-notes/ntfs-permissions/img-03.png)

### 4.2、文件及文件夹权限

| 文件权限 | 权限内容 |
| --- | --- |
| 完全控制 | 拥有读取、写入、修改、删除文件、及特殊的权限（在高级中可见特殊权限包括用户自定义权限的共） |
| 修改 | 具有rename重命名功能，该选项依赖读取和执行读取写入三个权限都要有 |
| 读取和执行 | 执行指的exe文件不是bat文件（只有读取也可以运行bat文件） |
| 读取 | 查看文件内容 |
| 写入 | 配合读取权限才能写入 |
| 特殊权限 | 高级中可见 |

| 文件夹权限 | 权限内容 |
| --- | --- |
| 完全控制 | 拥有对文件及文件夹读取、写入、修改、删除文件、及特殊的权限（在高级中可见特殊权限包括用户自定义权限的共） |
| 修改 | 删除文件目录依赖以下所有权限 （读取和执行读取列出文件夹内容写入） |
| 读取和执行 | 在该目录中建立的文件，也会具有该权限，该权限依赖（列出文件夹内容读取 ） |
| 列出文件夹内容 | 可以进入，目录并列出 |
| 读取 | （不进入）dir列出目录内容 |
| 写入 | 建立文件目录 |
| 特殊权限 | 高级中可见 |

案例1：telnet方式验证比较方便

```
net localgroup telnetclients a /add
```

建立jimi文件夹，并设置NTFS权限，要求a用户只能读取文件夹中的文件，不能在jimi文件夹中创建新的文件，b用户只能在jimi文件夹中创建新的文件，不能读取文件，c用户有完全控制权限。

### 4.3、权限累加

当用户同时属于多个组时，权限是累加的!telnet 做验证的时侯最好重新登录，使得你修改的权限可以生效案例2：

```
net localgroup it /add
net localgroup hr /add
```

用户a同时属于IT组与HR组，IT组对文件夹jimi可以读取，HR组可以对jimi文件夹写入，则a用户最终的权限为读取和写入。

### 4.4、取得所有权

默认只有administrator有这个权限！

作用：可以将任何文件夹的所有者改为administrator

![NTFS 安全权限 示意图 4](/images/windows-notes/ntfs-permissions/img-04.png)

案例3：

用户a已离职，但xxx文件夹的属主（所属者）是a，由于a用户对xxx文件夹做过权限修改，导致其他用户对xxx文件夹没有任何权限，现需要管理员administrator用户将xxx文件夹重新修改权限，并成功删除xxx文件夹。

## 五、练习

1、以administrator身份创建文件夹公共资料，要求实现student可以只读，teacher可以任意修改，其中公共资料文件夹中有一个“作业上传”文件夹，要求改文件夹student用户不能读取，只能上传写入！

2、以sutdent用户再D盘建立一个文件夹，并设置权限为只有自己有权限，此时使用administrator登录验证权限，并成功干掉该文件夹！

3、在win7上练习，打开win7虚拟机，并桥接到NAT模式可以上网，然后篡改hosts文件，实现禁止访问百度和京东！

注释：hosts文件路径：c:\windows\system32\drivers\etc\hosts

windows系统中c:\windows\system32\drivers\etc\hosts 是本地主机映射文件。其作用是指定ip和域名的对应关系，其优先级要高于dns服务器因此早些时候常被人恶意篡改导致无法访问正常的网站。

![NTFS 安全权限 示意图 5](/images/windows-notes/ntfs-permissions/img-05.png)

```
ipconfig  /displaydns  #显示dns缓存
ipconfig  /flushdns     #清除dns缓存
```
