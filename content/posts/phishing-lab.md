---
title: "钓鱼网站实训（DNS 欺骗与 ARP 攻击）"
date: 2026-10-20T12:00:00+08:00
draft: false
categories: ["网络基础"]
tags: ["网络基础", "钓鱼网站", "DNS", "ARP", "实训"]
summary: "网络安全实训：DNS 欺骗、ARP 攻击与钓鱼网站的制作过程与原理分析。"
description: "网络安全实训：DNS 欺骗、ARP 攻击与钓鱼网站的制作过程与原理分析。"
ShowToc: true
---

> 来源：网络基础课程讲义（`钓鱼网站.pdf`）。由 PDF/PPTX/DOCX 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## 钓鱼网站实训

> 来源：（`钓鱼网站.pdf`，共 18 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

钓鱼者运用社会工程学（social engineering）知识诱骗受害者，以在未授权情况下获取对方的姓名、年龄、邮箱账号、甚至是银行卡密码等私人信息钓鱼往往和社会工程学相结合进行诱导，而社会工程学是黑客的内功，能否灵活运用可以体现一个黑客的个人修为，所以说“防人之心不可无”这句话并非没有道理，凡事不要害人但是总要留个心眼否则最终受伤的就是自己。社会工程学黑客常见伎俩：

  - 电话号码欺骗

  - 利用坏消息作案

  - 滥用网民对社交等网站的信任

  - 二维码引诱

  - 等等

本案例利用虚假的京东网站，并且使用DNS与ARP欺骗手段诱使用户输入真实的用户名密码，。

使用kali系统模拟攻击者，利用中间人的攻击手段来对受害者进行DNS欺骗、使受害者通过访问假的京东网站，来获取用户登录的用户名与密码。

1、虚拟机软件

  - VMware  V12.0版本

2、虚拟机

  - WindowsXP----模拟客户机

  - Windows server 2003----模拟公网的DNS服务器与京东网站服务器

  - Kali ----模拟攻击机

3、Web站点素材

  - JD网站站点素材

4、工具

ettercap（kali自带）

5、实验拓扑图

![钓鱼网站.pdf 示意图 1](/images/network-notes/phishing-lab/all/img-01.webp)

6、站点素材关键代码

```
<?php
$nam = stripslashes($_POST['name']);
$pas = stripslashes($_POST['pass']);
$content = "您已捕获京东账号及密码1个：" . " 用户名 " . $nam . " 密码 " . $pas;
$filed = @fopen("1.txt", "a+");
@fwrite($filed, "$content\n");
?>
<html>
<head>
<script type="text/javascript">
function goBack()
{
window.history.back()  //后退+刷新
}
</script>
</head>
<body onload="goBack()">   <!-- 加载之后立即执行一段 JavaScript -->
</body>
</html>
```

## 五、实验流程

1、开启虚拟机并配置IP

1.1、开启Kali﹑XP及win2003三台虚拟机，注意第一次开虚拟机时会出现如图中的情况，选择我已移动该虚拟机即可！

![钓鱼网站.pdf 示意图 2](/images/network-notes/phishing-lab/all/img-02.webp)

1.2、并将此三台虚拟机放到同一个虚拟网络中，本实验为VMnet2，如图。

![钓鱼网站.pdf 示意图 3](/images/network-notes/phishing-lab/all/img-03.webp)

1.3、设置客户机win XP的IP地址为10.1.1.1

1.4、配置攻击机kali的IP地址为10.1.1.2，命令如下：

```
root@kali:~# ifconfig eth0 10.1.1.2/24
```

![钓鱼网站.pdf 示意图 4](/images/network-notes/phishing-lab/all/img-04.webp)

1.5、设置服务器win2003的IP地址为10.1.1.3（方法同XP）

  - 注意：

  - 1、三台虚拟机的子网掩码均为255.255.255.0

1.6、IP设置完毕后，使用ping命令测试网络连通性。（应确保防火墙已关闭）

2、在win2003中搭建京东WEB服务器及DNS服务器

2.1、将实验网站的文件夹JD，放到win2003的D盘中。

2.2、部署WEB服务器及DNS服务器启动IIS：开始—管理工具—Internet信息服务（IIS）管理器。

然后打开 Internet信息服务（IIS）管理器 ，点击默认网站右键属性。

主目录--指向D盘的JD站点目录。

![钓鱼网站.pdf 示意图 5](/images/network-notes/phishing-lab/all/img-05.webp)

设置默认首页：

打开DNS服务工具。

![钓鱼网站.pdf 示意图 6](/images/network-notes/phishing-lab/all/img-06.webp)

新建jd.com解析文件，并添加一条A记录：www.jd.com  ---指向-- 10.1.1.3

![钓鱼网站.pdf 示意图 7](/images/network-notes/phishing-lab/all/img-07.webp)

3、客户机尝试访问真正的京东

3.1、在XP虚拟机中，用浏览器打开图中的网址www.jd.com

3.2、尝试解析京东网站域名，结果为正确的IP地址。

![钓鱼网站.pdf 示意图 8](/images/network-notes/phishing-lab/all/img-08.webp)

4、开启ARP欺骗、DNS欺骗

4.1、将钓鱼网页的所有文件放到 kali 的/var/www/html/路径下， 并修改 1.txt 的权限， 使这个文档可以写入数据。

4.2、开启apache服务，并检查80端口是否已开启。

![钓鱼网站.pdf 示意图 9](/images/network-notes/phishing-lab/all/img-09.webp)

4.3、修改 DNS 欺骗配置文件， 使用 vim 编辑器， 命令： vim /etc/ettercap/etter.dns，然后  添加一条 A 记录，添加一条 PTR 记录，使用户访问任何网页，全部指向为10.1.1.2

![钓鱼网站.pdf 示意图 10](/images/network-notes/phishing-lab/all/img-10.webp)

4.4、打开ettercap软件，如图，在搜索框中输入etter，即可搜索到ettercap软件。

![钓鱼网站.pdf 示意图 11](/images/network-notes/phishing-lab/all/img-11.webp)

4.5、选择sniﬀ--uniﬁed sniﬃng，并选择监听eth0。

![钓鱼网站.pdf 示意图 12](/images/network-notes/phishing-lab/all/img-12.webp)

4.6、然后选择Hosts——Scan for hosts,如图，

![钓鱼网站.pdf 示意图 13](/images/network-notes/phishing-lab/all/img-13.webp)

4.7、扫描完成后选择Hosts——Hosts list,可以看到扫描到的主机，如图.

4.8、添加欺骗记录选中10.1.1.1，点击Add to Target 1。

![钓鱼网站.pdf 示意图 14](/images/network-notes/phishing-lab/all/img-14.webp)

选中10.1.1.3，然后点击 Add to Target2.

4.9、在Mitm选择ARP欺骗，如图。

![钓鱼网站.pdf 示意图 15](/images/network-notes/phishing-lab/all/img-15.webp)

在弹出的窗口中，勾选第一个点击确定，

![钓鱼网站.pdf 示意图 16](/images/network-notes/phishing-lab/all/img-16.webp)

4.10、选择plugins -- Manage the plugins，准备进行DNS欺骗

在弹出的窗口中， 找到 dns spoof 并双击出现*号，开始DNS欺骗， 如图

![钓鱼网站.pdf 示意图 17](/images/network-notes/phishing-lab/all/img-17.webp)

5、开始钓鱼

5.1、在XP系统中，再次登录www.jd.com输入用户名密码等，如图，然后点击登录。

5.2、在kali虚拟机中，已经钓鱼成功，并钓到京东的登录账户及密码。
