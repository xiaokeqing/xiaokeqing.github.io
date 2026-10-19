---
title: "Linux 服务基础 · 全篇合并整理版（面试背诵版）"
date: 2026-10-19T21:00:00+08:00
draft: false
categories: ["课程笔记", "linux系统"]
tags: ["Linux", "基础", "课程笔记"]
summary: "把起源与派系、基本命令、用户与组、权限、进程、网络配置、vim 与服务部署压成一份连续通读稿，按必背要点、对比表与高频面试题组织。"
description: "把起源与派系、基本命令、用户与组、权限、进程、网络配置、vim 与服务部署压成一份连续通读稿，按必背要点、对比表与高频面试题组织。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`Linux服务基础笔记.pdf`，共 11 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

  - 按必背要点 / 表格对比 / 安全视角 / 高频面试题整理 · 源自实训课件

## 一、Linux 系统基础

### 1.1 Linux 起源（面试一句带过）

Unix 诞生于 1969 年贝尔实验室（Ken Thompson / Dennis Ritchie，C 语言之父）；GNU 社区（斯托曼）提供开源软件但缺内核；1991 年芬兰人林纳斯·托瓦兹发布 Linux 内核，Linus 取名"Linux"（like Unix）。

### 1.2 主流派系（背熟）

| 派系 | 代表发行版 | 说明 |
| --- | --- | --- |
| Debian 系 | Ubuntu、Kali | Kali = 安全渗透必备系统 |
| RedHat 系 | CentOS、RedHat | RedHat 唯一靠操作系统盈利； CentOS 是它的免费版 |
| 其他 | SUSE、Arch 等 | 了解即可 |

### 1.3 命令行提示符含义

**必背**

| 提示符 | 含义 |
| --- | --- |
| [root@localhost ~]# | [当前用户名@主机名当前目录] #；# = 超级管理员 （root） |
| [user@localhost ~]$ | $ = 普通用户 |
| ~ | 家目录（root 是 /root，普通用户是 /home/用户名） |
| / | 根目录，一切路径的起点 |

### 1.4 目录结构（面试常问）

**必背**

| 目录 | 作用 |
| --- | --- |
| /bin | 普通用户和管理员都能用的命令（ls、cd 等） |
| /sbin | 只有管理员可运行的系统命令（多数） |
| /etc | 配置文件目录（passwd、shadow、grub 等都在这） |
| /home | 普通用户的家目录 |
| /root | root 管理员的家目录 |
| /tmp | 临时文件目录 |
| /var | 存放日志（/var/log）、缓存等变化的数据 |
| /dev | 设备文件（一切皆文件） |
| /proc | 内存中的虚拟目录，实时反映系统状态 |

### 1.5 基本命令（必会）

| 命令 | 作用 | 要点 |
| --- | --- | --- |
| cd | 切换目录 | cd .. 上一级；cd / 回根；cd ~ 回家 |
| pwd | 显示当前路径 |  |
| ls | 列出目录内容 | ls -a 含隐藏文件；ls -l 详细信息 |
| mkdir | 建目录 | mkdir -p 一次性建多级 |
| mv | 移动/重命名 | 即"剪切"，目录无需 -r |
| cp | 复制 | 复制目录必须 cp -r |
| rm | 删除 | rm -rf 强制递归删除（高危！）； rmdir 删空目录 |
| cat | 查看文件内容 |  |
| ln | 建立链接 | ln -s 软链接（快捷方式）；ln 硬链接 |

绝对路径：以 / 开头（如 /tmp/nz2002.txt）；相对路径：以当前位置为参照（./ 当前、../ 上一级）。

## 二、用户与组管理（面试重点）

### 2.1 用户分类与 UID 🔴必背

| 用户类型 | UID | 特点 |
| --- | --- | --- |
| 超级用户 root | 0 | 最高权限，不受权限限制 |
| 程序用户（伪用户） | 1~999 | 用来启动程序/服务，权限极小， 不能登录系统，一般无家目录 |
| 普通用户 | 1000~60000 | 可登录系统，权限受限 |

### 2.2 用户相关文件（必背）

文件：三个核心文件，一切用户/组信息都在这里：

| 文件 | 存什么 | 关键字段 |
| --- | --- | --- |
| /etc/passwd | 账号信息 | 用户名:密码占位符(x):UID:GID:描述:家目录:登录Shell |
| /etc/shadow | 密码信息（加密） | 用户名:密码(SHA512):最近修改天数:最小使用:最大使用:失效前警告: 非活跃期:失效日期:保留 |
| /etc/group | 组账号信息 | 组名:组密码占位符(x):GID:组成员 |

安全点：/etc/shadow 只有 root 能读，密码是 SHA512 二次加密存储；锁定用户的标志是密码字段前出现 !!。

### 2.3 用户管理命令（必背）

  - 命令

  - 作用

  - 常用选项

| useradd 用户名 | 创建用户 | -u 指定UID；-g 基本组；-G 附加组；-M 不建家目录；-s 指定 Shell（/sbin/nologin = 禁止登录） |
| --- | --- | --- |
| passwd 用户名 | 设置/修改密码 | -d 清空密码；-l 锁定；-u 解锁；-S 查看状态 |
| usermod 用户名 | 修改用户属性 | -u -g -G -s -L 锁定 -U 解锁 |
| userdel 用户名 | 删除用户 | -r 连同家目录一起删 |
| id 用户名 | 查看用户信息 | UID/GID/所属组 |
| su 用户名 | 临时切换用户 | 不输用户名默认切 root |

### 2.4 组管理命令

| 命令 | 作用 |
| --- | --- |
| groupadd 组名 | 创建组（-g 指定GID） |
| groupmod -g 新GID 组名 | 修改组ID |
| gpasswd -a 用户组 | 把用户加入组 |
| groupdel 组名 | 删除组 |

### 2.5 高频面试题

（1）/etc/passwd 和 /etc/shadow 的区别？

  - passwd 存账号基本信息（可读），shadow 存加密密码（仅 root 可读，SHA512）。

（2）如何创建一个不能登录系统的用户？

  - useradd -s /sbin/nologin -M 用户名（-M 无家目录，-s 指定 nologin Shell）。

（3）锁定/解锁用户的方法？

  - passwd -l 锁定（shadow 密码前出现 !!）、passwd -u 解锁；或 usermod -L / -U。

（4）程序用户是什么？为什么存在？

  - UID 1~999，给程序/服务提供运行身份，权限最小化，不能登录，防止程序以 root 运行造成风

  - 险。

（5）删除用户时家目录怎么办？

  - userdel -r 连家目录一起删，否则会残留目录。

## 三、Vim 编辑器

### 3.1 三大工作模式（必背）

| 模式 | 能做什么 | 进入/返回 |
| --- | --- | --- |
| 命令模式 | 复制、粘贴、删除、定位、撤销 （默认进入） | 打开 vim 即命令模式 |
| 输入模式 | 输入文字内容 | 按 i 进入；按 Esc 返回命令模式 |

末行模式保存、退出、查找、替换等编辑命

  - 按 : 进入；执行完自动回命令模式令

### 3.2 末行模式常用命令（必背）

| 命令 | 作用 |
| --- | --- |
| :w | 保存 |
| :wq | 保存并退出 |
| :q! | 不保存强制退出 |
| :set nu / :set nonu | 显示/取消行号 |
| :/字符串 | 向下查找（n 下一个，N 上一个） |
| :%s/old/new/g | 全文替换 |
| :2,6s/old/new/g | 第 2~6 行替换 |
| :r 文件名 | 读取别的文件内容到当前 |

### 3.3 命令模式常用操作（必背）

| 操作 | 作用 |
| --- | --- |
| yy / yw | 复制当前行 / 复制一个单词 |
| p | 粘贴到光标下方 |
| dd / 10dd | 删除当前行 / 向下删 10 行 |
| dw / x | 删除一个单词 / 删除光标处字符 |
| gg / G / 100G | 跳到第一行 / 最后一行 / 第 100 行 |
| u / Ctrl+r | 撤销 / 恢复撤销 |

### 3.4 别名 alias

alias cc="ls -l" 临时生效；写入 ~/.bashrc 永久生效（source ~/.bashrc 立即生效）；/etc/bashrc 是全局别名文件；unalias 取消。

## 四、进程管理（面试重点）

### 4.1 程序 vs 进程

程序是静态的、存在硬盘上的文件；启动后加载到内存被 CPU 运行，就叫进程。

### 4.2 开机流程（必背）

| 步骤 | 做什么 |
| --- | --- |
| 1 BIOS | 加电自检，加载硬盘 |
| 2 MBR（主引导记录 446 字节） | 找引导程序 |
| 3 GRUB | 引导菜单，读配置文件加载内核 |
| 4 内核 + 驱动 | 加载核心 |

5 systemd启动的第一个进程（PID=1），负责启动其他所有进

  - 程、决定进入哪个运行模式

### 4.3 systemctl 控制（必背）

| 命令 | 作用 |
| --- | --- |
| systemctl start 服务 | 启动服务 |
| systemctl stop 服务 | 停止服务 |
| systemctl restart 服务 | 重启服务 |
| systemctl enable 服务 | 开机自启 |
| systemctl disable 服务 | 取消开机自启 |
| systemctl status 服务 | 查看状态 |
| systemctl get-default / set-default | 查看/设置默认运行模式（图形/多用户字符） |

### 4.4 进程查看与操作

| 命令 | 作用 |
| --- | --- |
| ps aux | 查看所有后台进程（静态快照） |
| top | 实时监控进程（M 按内存排、P 按CPU 排、k 杀死进程、q 退出） |
| kill PID / kill -9 PID | 结束进程 / 强制结束 |
| 命令 & | 后台运行 |
| nohup 命令 & | 后台运行且不随终端退出而终止 |

### 4.5 高频面试题

（1）Linux 开机启动的第一个进程是什么？

  - systemd（PID=1），早期是 init。

（2）systemctl 和 service 的区别？

  - systemctl 是 systemd 的管理命令（新），service 是旧 init 时代的封装（老系统/兼容）。

（3）怎么让服务开机自启？

  - systemctl enable 服务名。

（4）kill 和 kill -9 区别？

  - kill 发 TERM 信号让进程正常退出；kill -9 发 KILL 信号强制杀死，可能丢数据。

## 五、IP 配置与网络（必背）

### 5.1 查看命令

| 命令 | 作用 |
| --- | --- |
| ip addr | 查看 IP 地址 |
| ip route | 查看路由/网关 |

| ip addr add IP dev 网卡名 | 临时加 IP |
| --- | --- |
| nmcli connection up/down 网卡 | 启用/停用网卡 |

### 5.2 静态 IP 配置文件（必背）

路径：/etc/sysconfig/network-scripts/ifcfg-eth0（网卡名可能不同，如 ifcfg-ens33）。

| 配置项 | 含义 |
| --- | --- |
| BOOTPROTO=static | 静态IP（dhcp=自动获取） |
| ONBOOT=yes | 开机自动启用 |
| IPADDR=192.168.1.100 | IP 地址 |
| NETMASK=255.255.255.0 | 子网掩码 |
| GATEWAY=192.168.1.1 | 网关 |
| DNS1=114.114.114.114 | 首选 DNS |

改完重启网络：systemctl restart network。DNS 也可写 /etc/resolv.conf（nameserver 114.114.114.114）。

### 5.3 路由转发（实验核心）

开启：Linux 默认不做路由转发（不做网关），要开启：

| 步骤 | 命令 |
| --- | --- |
| 1 修改配置 | vim /etc/sysctl.conf 添加 net.ipv4.ip_forward = 1 |
| 2 立即生效 | sysctl -p |

实验拓扑：Windows(192.168.2.x) ↔ 网关服务器(双网卡) ↔ CentOS(172.16.2.x)，网关服务器开启ip_forward 后两边才能互通。

### 5.4 高频面试题

（1）怎么给 Linux 配静态 IP？

  - 编辑 /etc/sysconfig/network-scripts/ifcfg-eth0，设

  - BOOTPROTO=static、IPADDR、NETMASK、GATEWAY、DNS1，然后 systemctl restart

  - network。

（2）Linux 怎么做路由器/网关？

  - 开启内核路由转发：/etc/sysctl.conf 设 net.ipv4.ip_forward=1，sysctl -p 生效。

（3）ip addr 和 ifconfig 区别？

  - ip addr 是新 iproute2 工具；ifconfig 是老 net-tools，CentOS7 默认没装。

## 六、日志服务 rsyslog（安全重点）

### 6.1 常见日志文件（必背）

  - 文件

  - 记录什么

| /var/log/messages | 系统常规信息、报错（通用日志） |
| --- | --- |
| /var/log/secure | 安全/认证日志（SSH 登录、sudo 都记这，最常看） |
| /var/log/cron | 计划任务日志 |
| /var/log/maillog | 邮件日志 |
| /var/log/boot.log | 开机日志 |

### 6.2 日志规则格式

格式：配置文件 /etc/rsyslog.conf，规则格式：facility.priority 动作（记到哪里）。

| 部分 | 含义 | 例子 |
| --- | --- | --- |
| facility（类型） | 哪个服务的日志 | authpriv、cron、mail、kern、d aemon |
| priority（级别） | 什么级别才记 | info、err、emerg |
| 动作 | 记到哪 | /var/log/secure、@IP、用户、* |

### 6.3 日志级别（从低到高，必背）

debug < info < notice < warn/warning < err/error < crit < alert < emerg（emerg 最严重，系统崩溃）。

例子：authpriv.* /var/log/secure 表示 authpriv 服务所有级别都记到 secure；*.info;mail.none 表示所有 info 以上但排除 mail。

### 6.4 远程日志服务器（日志异地备份）

| 端 | 配置 |
| --- | --- |
| 客户端 | 规则里加 *.* @@服务器 IP:514（@@=TCP，@=UDP），重启 systemctl restart rsyslog |
| 服务器 | /etc/rsyslog.conf 打开 imudp/imtcp 模块监听 514 端口，重启 |

### 6.5 清理痕迹（渗透/应急都懂）

history -c 清历史命令；echo "" > /var/log/secure 清登录日志；last -f /var/log/wtmp 查看登录记录。

### 6.6 高频面试题

（1）SSH 登录日志在哪个文件？

  - /var/log/secure（记录认证成功/失败、sudo 等安全事件）。

（2）rsyslog 规则格式是什么？

  - facility.priority 动作，如 authpriv.* /var/log/secure。

（3）日志级别从低到高？

  - debug→info→notice→warn→err→crit→alert→emerg。

（4）日志怎么异地备份？

  - 配置 rsyslog 客户端 *.* @@服务器:514，服务器开 514 监听，实现实时转发。

## 七、系统加固

### 7.1 GRUB 引导加密（防进单用户模式改密码）

| 步骤 | 命令/文件 |
| --- | --- |
| 1 生成密码 | grub2-mkpasswd-pbkdf2（生成 PBKDF2 哈希） |
| 2 配置用户 | 编辑 /etc/grub.d/01_users：set superusers="root"; password_pbkdf2 root 哈希 |
| 3 重新生成配置 | grub2-mkconfig -o /boot/grub2/grub.cfg |
| 4 重启验证 | 进入 GRUB 菜单必须先输用户名密码 |

注意：/boot/grub2/grub.cfg 是生成文件不能直接改，要改 /etc/grub.d/ 下的源文件再重新生成。

### 7.2 其他加固点

关闭 SELinux（/etc/selinux/config 设 SELINUX=disabled）；关闭防火墙（systemctl stop firewalld / disable）；及时打补丁；最小权限原则。

## 八、Web 服务部署（LNMP / Tomcat）

### 8.1 LNMP 架构（必背）

架构：LNMP = Linux + Nginx + MySQL + PHP。核心考点：nginx 本身不能解析 PHP，要靠 php-fpm。

| 组件 | 作用 |
| --- | --- |
| Nginx | Web 服务器，处理静态请求，高并发、负载均衡 |
| php-fpm | PHP 的解释服务进程，监听 9000 端口 |
| MySQL | 数据库 |
| PHP | 动态脚本语言 |

工作流程：浏览器 → Nginx →（把 .php 请求转发）→ php-fpm(9000) 解析后返回 → Nginx → 浏览器。

### 8.2 Nginx 关键配置（必背）

nginx.conf 中解析 PHP 的 location 配置：

| 配置项 | 作用 |
| --- | --- |
| location ~ \.php$ | 匹配 .php 结尾的请求 |
| fastcgi_pass 127.0.0.1:9000 | 转发给 php-fpm 的 9000 端口 |

| fastcgi_index index.php | 默认首页 |
| --- | --- |
| fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name | 告诉 php-fpm 脚本真实路径（排错关键） |

改完配置：nginx -s reload 平滑重载（不用停服务）。

### 8.3 File not found 排错（面试加分）

原因：SCRIPT_FILENAME 路径配置错误（默认 /scripts$fastcgi_script_name 不存在）。修复：改为 $document_root$fastcgi_script_name，或修改 php-fpm 配置 /etc/php-fpm.d/www.conf 中属主属组与 nginx 一致，重启 php-fpm。

### 8.4 Tomcat 部署与渗透（必背）

| 要点 | 内容 |
| --- | --- |
| 端口 | 默认 8080 |
| 特点 | Java 应用服务器，发布 JSP/WAR 包 |
| 环境 | 先装 JDK 再装 Tomcat |
| 启动 | ./bin/startup.sh（Linux）/ tomcat8 start（Windows） |

渗透：Manager 弱口令 getshell 链路（面试经典）：

| 步骤 | 操作 |
| --- | --- |
| 1 开放远程访问 | 改 webapps/manager/META-INF/context.xml 允许所有 IP |
| 2 配账号 | /conf/tomcat-users.xml 添加 manager-gui 等角色和用户（如 tomcat/tomcat） |
| 3 登录 Manager | 访问 /manager/html 弱口令登录 |
| 4 传马 | 把 JSP 大马打成 WAR 包（jar cvf shell.war shell.jsp）上传部署 |
| 5 getshell | 访问 http://IP:8080/shell/shell.jsp |

### 8.5 高频面试题

（1）Nginx 为什么不直接解析 PHP？

  - Nginx 是 Web 服务器不内置 PHP 解释器，需要把 .php 请求通过 fastcgi 转发给 php-fpm（9000）处理。

（2）Nginx 改配置后怎么生效？

  - nginx -s reload 平滑重载，不中断服务。

（3）LNMP 和 LAMP 区别？

  - LNMP 用 Nginx，LAMP 用 Apache；Nginx 高并发更强。

（4）Tomcat 弱口令 getshell 流程？

  - manager 开放远程+配账号 → 登录 Manager → 上传 JSP 大马 WAR 包 → 访问 getshell。

## 九、渗透实战链路（靶机项目提炼）

### 9.1 通用渗透流程（必背）

| 阶段 | 操作 | 工具 |
| --- | --- | --- |
| 1 信息收集 | 网段扫描、全端口+服务扫描 | nmap -sP 网段；nmap -A -p- IP |
| 2 目录扫描 | 扫敏感目录、后台、备份文件 | dirb、dirsearch、nikto |
| 3 漏洞发现 | 识别中间件/CMS 版本找对应漏洞 | searchsploit、wpscan、msf |
| 4 漏洞利用 | 拿 WebShell / 反弹 Shell | msf、python 脚本、蚁剑 |
| 5 权限提升 | SUID / sudo / 内核提权拿 root | find、sudo -l、searchsploit |

### 9.2 提权方法（必背）

| 方法 | 原理/操作 |
| --- | --- |
| SUID 提权 | find / -perm -u=s 找 SUID 程序，利用 find -exec 执行命令 |
| sudo 提权 | sudo -l 看当前用户能免密执行什么，配合 GTFOBins 找利用（如 sudo git、sudo php） |
| 内核提权 | 系统版本老、未打补丁，用 searchsploit 找内核漏洞利用脚本编译执行 |

### 9.3 靶机实战要点（简历可写）

| 靶机 | 核心考点 |
| --- | --- |
| DC-1 | Drupal 7（Drupalgeddon CVE-2014-3704）SQL 注入建管理员；mysql 读配置/改密码；find SUID 提权 |
| DC-2 | cewl 生成密码字典；wpscan 枚举爆破 WordPress； rbash 绕过（BASH_CMDS / vi shell）；sudo git 提权 |
| Node | 用户枚举、源码泄露、base64 解码、fcrackzip 爆破压缩包、SSH 登录、内核提权 |
| Me | 源码泄露、sudo -l 配合 GTFOBins（sudo php -r 执行命令）提权 |

rbash 绕过思路：BASH_CMDS[a]=/bin/bash 然后 a，或 vi 里 :set shell=/bin/bash | shell；再补PATH 环境变量。

## 附录：Linux 必背速查（考前 5 分钟）

| 主题 | 一句话 |
| --- | --- |
| 用户文件 | /etc/passwd（账号）、/etc/shadow（密码）、/ etc/group（组） |
| root UID | 0；程序用户 1-999；普通用户 1000+ |

| 禁登录 | useradd -s /sbin/nologin -M |
| --- | --- |
| 开机第一进程 | systemd（PID=1） |
| 服务自启 | systemctl enable 服务 |
| 静态IP | ifcfg-eth0：BOOTPROTO=static + IPADDR/NETMASK/GATEWAY/DNS1 |
| 路由转发 | net.ipv4.ip_forward=1 + sysctl -p |
| 登录日志 | /var/log/secure |
| 日志级别 | debug<info<notice<warn<err<crit<alert<emerg |
| Nginx+PHP | fastcgi_pass 127.0.0.1:9000 交给 php-fpm |
| Tomcat | 8080；manager 弱口令传 WAR getshell |
| 提权三招 | SUID（find -exec）、sudo（GTFOBins）、内核提权 |
