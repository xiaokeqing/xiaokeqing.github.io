---
title: "Linux 操作系统的安装：虚拟机建立与系统安装"
date: 2026-10-19T19:00:00+08:00
draft: false
categories: ["课程笔记", "linux系统"]
tags: ["Linux", "虚拟机", "课程笔记"]
summary: "从新建虚拟机、选择安装介质到分区与系统安装完成，逐步走完一台 Linux 虚拟机的落地过程（图为主）。"
description: "从新建虚拟机、选择安装介质到分区与系统安装完成，逐步走完一台 Linux 虚拟机的落地过程（图为主）。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`linux操作系统的安装.pdf`，共 33 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

虚拟机建立过程和安装过程

1、建立

![Linux 操作系统的安装 示意图 1](/images/linux-notes/linux-install/img-01.webp)

![Linux 操作系统的安装 示意图 2](/images/linux-notes/linux-install/img-02.webp)

![Linux 操作系统的安装 示意图 3](/images/linux-notes/linux-install/img-03.webp)

![Linux 操作系统的安装 示意图 4](/images/linux-notes/linux-install/img-04.webp)

![Linux 操作系统的安装 示意图 5](/images/linux-notes/linux-install/img-05.webp)

![Linux 操作系统的安装 示意图 6](/images/linux-notes/linux-install/img-06.webp)

![Linux 操作系统的安装 示意图 7](/images/linux-notes/linux-install/img-07.webp)

![Linux 操作系统的安装 示意图 8](/images/linux-notes/linux-install/img-08.webp)

![Linux 操作系统的安装 示意图 9](/images/linux-notes/linux-install/img-09.webp)

2、准备开始安装前

![Linux 操作系统的安装 示意图 10](/images/linux-notes/linux-install/img-10.webp)

设定双网卡

![Linux 操作系统的安装 示意图 11](/images/linux-notes/linux-install/img-11.webp)

安装

![Linux 操作系统的安装 示意图 12](/images/linux-notes/linux-install/img-12.webp)

语言选择

![Linux 操作系统的安装 示意图 13](/images/linux-notes/linux-install/img-13.webp)

选择软件

![Linux 操作系统的安装 示意图 14](/images/linux-notes/linux-install/img-14.webp)

选择

![Linux 操作系统的安装 示意图 15](/images/linux-notes/linux-install/img-15.webp)

确认硬盘

![Linux 操作系统的安装 示意图 16](/images/linux-notes/linux-install/img-16.webp)

选择安装硬盘

![Linux 操作系统的安装 示意图 17](/images/linux-notes/linux-install/img-17.webp)

选择时区

![Linux 操作系统的安装 示意图 18](/images/linux-notes/linux-install/img-18.webp)

![Linux 操作系统的安装 示意图 19](/images/linux-notes/linux-install/img-19.webp)

修改主机名

![Linux 操作系统的安装 示意图 20](/images/linux-notes/linux-install/img-20.webp)

![Linux 操作系统的安装 示意图 21](/images/linux-notes/linux-install/img-21.webp)

![Linux 操作系统的安装 示意图 22](/images/linux-notes/linux-install/img-22.webp)

点击开始安装

![Linux 操作系统的安装 示意图 23](/images/linux-notes/linux-install/img-23.webp)

设定root密码，root为linux操作系统管理员的名称。

![Linux 操作系统的安装 示意图 24](/images/linux-notes/linux-install/img-24.webp)

必须建立一个普通用户

![Linux 操作系统的安装 示意图 25](/images/linux-notes/linux-install/img-25.webp)

![Linux 操作系统的安装 示意图 26](/images/linux-notes/linux-install/img-26.webp)

![Linux 操作系统的安装 示意图 27](/images/linux-notes/linux-install/img-27.webp)

点击重启之后

![Linux 操作系统的安装 示意图 28](/images/linux-notes/linux-install/img-28.webp)

![Linux 操作系统的安装 示意图 29](/images/linux-notes/linux-install/img-29.webp)

用户登录

![Linux 操作系统的安装 示意图 30](/images/linux-notes/linux-install/img-30.webp)

![Linux 操作系统的安装 示意图 31](/images/linux-notes/linux-install/img-31.webp)

有欢迎提示一路next

![Linux 操作系统的安装 示意图 32](/images/linux-notes/linux-install/img-32.webp)

正式进入桌面

![Linux 操作系统的安装 示意图 33](/images/linux-notes/linux-install/img-33.webp)

3、系统登录和优化了解操作系统

3.1 cpu型号  内存大小  硬盘大小   内核版本cat /proc/cpuinfo cat /proc/meminfo

fdisk -l

![Linux 操作系统的安装 示意图 34](/images/linux-notes/linux-install/img-34.webp)

uname -r

![Linux 操作系统的安装 示意图 35](/images/linux-notes/linux-install/img-35.webp)

对该系统关机init 0 关机调整系统的分辨率还有电源管理

![Linux 操作系统的安装 示意图 36](/images/linux-notes/linux-install/img-36.webp)

![Linux 操作系统的安装 示意图 37](/images/linux-notes/linux-install/img-37.webp)

![Linux 操作系统的安装 示意图 38](/images/linux-notes/linux-install/img-38.webp)

![Linux 操作系统的安装 示意图 39](/images/linux-notes/linux-install/img-39.webp)

设定 防火墙功能要关闭

![Linux 操作系统的安装 示意图 40](/images/linux-notes/linux-install/img-40.webp)

![Linux 操作系统的安装 示意图 41](/images/linux-notes/linux-install/img-41.webp)

关闭selinux 服务 属于应用层的限制程序

```
nano /etc/selinux/config
```

![Linux 操作系统的安装 示意图 42](/images/linux-notes/linux-install/img-42.webp)

关闭一个虚拟网卡

![Linux 操作系统的安装 示意图 43](/images/linux-notes/linux-install/img-43.webp)

熟悉基本的操作页面 还有 加入中文的输入法

![Linux 操作系统的安装 示意图 44](/images/linux-notes/linux-install/img-44.webp)

![Linux 操作系统的安装 示意图 45](/images/linux-notes/linux-install/img-45.webp)

![Linux 操作系统的安装 示意图 46](/images/linux-notes/linux-install/img-46.webp)

linux虚拟机和真实机之间如何拷贝文件。

只需要右键复制，到虚拟机中粘贴即可。

最后一步优化建立关机快照普通用户如果是用systemct poweroff 关机需要加 -i

![Linux 操作系统的安装 示意图 47](/images/linux-notes/linux-install/img-47.webp)

建立关机快照

![Linux 操作系统的安装 示意图 48](/images/linux-notes/linux-install/img-48.webp)

基本命令的使用和目录结构的分析cd      ls      pwd打开终端后显示的 [root@localhost ~]# 什么意思[当前的用户名@主机名 当前所在的目录名] ## 表示当前用户的身份为超级管理员如果是其他用户 用 $符号提示pwd 命令查看当前所在的路径

```
[root@localhost ~]# cd /root/Desktop/
[root@localhost Desktop]# pwd
/root/Desktop
[root@localhost Desktop]#
cd  change  directory
[root@localhost Desktop]# pwd
/root/Desktop
[root@localhost Desktop]# cd ..   返回上一级目录
[root@localhost ~]# pwd
/root
[root@localhost ~]# cd ..
[root@localhost /]# pwd
/
[root@localhost /]# cd ..   已经到头了 没法继续往上了
```

```
[root@localhost /]# pwd
/
[root@localhost /]#
```

ls == dir  相当于windows的列出当前目录中的内容  （list 列出）

![Linux 操作系统的安装 示意图 49](/images/linux-notes/linux-install/img-49.webp)

目录分析/   操作系统的起始路径/bin   目录中保存了系统中普通用户和管理员都可以运行的命令字/sbin  只有管理员才可以运行的命令（普通用户也可以运行某些命令 但是显示效果不如管理员多）bin目录的分析对于绝对路径和相对路径的理解

![Linux 操作系统的安装 示意图 50](/images/linux-notes/linux-install/img-50.webp)

通过练习学命令（增 删 改 查）

mkdir  nano  mv  cp   rm   cat  ln

1、要求在 /tmp 目录中建立一个名为 nz2002的目录，并且在该nz2002目录中 建立一个名为nz2002.txt的文件，并写入自己的名字。

```
[root@localhost sbin]# md /tmp/nz2002
bash: md: command not found...  #表示没有这个命令
[root@localhost sbin]# mkdir /tmp/nz2002   #建立目录
[root@localhost sbin]# cd /tmp/nz2002
[root@localhost nz2002]# pwd
/tmp/nz2002
[root@localhost nz2002]# notepad
bash: notepad: command not found...
[root@localhost nz2002]# nano /tmp/nz2002/nz2002.txt  #用该编辑器打开一个文件
[root@localhost nz2002]# cat /tmp/nz2002/nz2002.txt  #查看文件内容
```

大家好我是胡洋老师

![Linux 操作系统的安装 示意图 51](/images/linux-notes/linux-install/img-51.webp)

此时按ctrl+o 确认写入提示用户名直接回车确认再出现提示窗 按ctrl+x 退出

2、要求将/tmp/nz2002 目录剪切到 /opt目录中。然后进入 /opt目录将 nz2002文件夹，拷贝回/tmp

```
[root@localhost tmp]# cd /opt
[root@localhost opt]# ls
rh
[root@localhost opt]#
[root@localhost opt]# ls
rh
[root@localhost opt]# mv /tmp/nz2002 /opt   #剪切文件夹
[root@localhost opt]# ls
nz2002  rh
[root@localhost opt]# cd /tmp/nz2002
bash: cd: /tmp/nz2002: No such file or directory
[root@localhost opt]# cd nz2002
[root@localhost nz2002]# ls
nz2002.txt
[root@localhost nz2002]# cat nz2002.txt
```

大家好我是胡洋老师

```
[root@localhost nz2002]# pwd
/opt/nz2002
[root@localhost nz2002]# cp /opt/nz2002  /tmp  #拷贝文件夹的时候必须加入 -r选项才可以拷
```

贝

```
cp: omitting directory ‘/opt/nz2002’
[root@localhost nz2002]# cp -r /opt/nz2002  /tmp
[root@localhost nz2002]# pwd
/opt/nz2002
[root@localhost nz2002]# cd /tmp/nz2002
[root@localhost nz2002]# ls
nz2002.txt
[root@localhost nz2002]#
```

3、将/opt目录中的nz2002文件夹删除

```
[root@localhost opt]# ls
```

```
nz2002  rh
[root@localhost opt]# rm /opt/nz2002  #目录不可以直接删除
rm: cannot remove ‘/opt/nz2002’: Is a directory
[root@localhost opt]# rmdir /opt/nz2002
rmdir: failed to remove ‘/opt/nz2002’: Directory not empty
[root@localhost opt]# rm -r /opt/nz2002  #删除目录要依次确认文件
rm: descend into directory ‘/opt/nz2002’? y
rm: remove regular file ‘/opt/nz2002/nz2002.txt’? y
rm: remove directory ‘/opt/nz2002’? y
[root@localhost opt]# ls
rh
[root@localhost opt]# cp -r /tmp/nz2002/ /opt
[root@localhost opt]# ls
nz2002  rh
[root@localhost opt]# rm -rf /opt/nz2002  #删除的时候进行强制删除
[root@localhost opt]# ls
rh
[root@localhost opt]#
```

4、将 /tmp/nz2002/nz2002.txt 建立一个符号链接在桌面上，要求可以双击打开该文件

![Linux 操作系统的安装 示意图 52](/images/linux-notes/linux-install/img-52.webp)
