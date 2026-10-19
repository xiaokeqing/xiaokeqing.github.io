---
title: "PKI 完整版：加密、数字签名与证书体系"
date: 2026-10-19T06:00:00+08:00
draft: false
categories: ["课程笔记", "Windows 服务基础"]
tags: ["Windows Server", "PKI", "密码学", "课程笔记"]
summary: "对称/非对称加密与哈希、数字签名与证书、CA 层级与证书吊销，以及 HTTPS 如何串起这一整套。"
description: "对称/非对称加密与哈希、数字签名与证书、CA 层级与证书吊销，以及 HTTPS 如何串起这一整套。"
ShowToc: true
---

> 来源：Windows 服务基础课程讲义（`PKI（完整版）.pdf`，共 21 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

名称：Public Key Infrastructure  （公钥基础设施）

作用：通过加密技术和数字签名，保证信息存储和传输的安全！

（http://www.leichi.com:80   https://www.leichi.com:443）

组成：公钥加密技术、数字证书、CA、RA

  - 机密性

  - 完整性

  - 身份验证

（操作的不可否认性）=第四要素=身份验证

  - 也有另外得安全三要素说法：

  - 机密性

  - 完整性

  - 可用性

  - Https （s:  SSL/pki）  端口:443   https://www.leichi.com

  - VPN--IPsecVPN

  - VPN--部分远程访问VPN、pptpvpn 、sslvpn

作用：通过加密技术和数字签名，保证信息存储和传输的安全！

## ---- 加密算法分类

  - （加密）对称加密算法 （一种密钥，负责加密和解密，）

  - （身份）非对称加密算法 （一对钥匙，公钥和私钥，公钥加密，私钥解密，私钥加密，公钥解密）（完整）哈希算法（hash算法）（sha256 512 MD5

  - 1、无论数据多大，加密后都可以固定长度字符串

  - 2、源数据不变，加密后的密文不变

  - 3、加密不可逆）

  - 注释：加密算法就是数学公式！如：x + 5 = y   再比如：x * 5= y

  - 公式本身就是加密算法，x代表未加密数据，y是加密后的数据（密文）

  - 加密与解密必须使用相同的加密算法！！！！！！！

  - 5就是密钥key！！！

## 4.1 对称加密算法

所谓对称加密算法

  - 加密和解密时用的密钥一致！而这个密钥称为“对称密钥”！

对称密钥的生成

  - 对称密钥是由通信双方的对称算法协商并生成的！

对称加密算法缺点

  - 协商密钥期间，是明文传输，密钥容易泄露！

对称加密算法优点

  - 加密速度快！！

对称加密常见的算法

  - DES、3DES、AES（高级加密算法）

举个例子：kali系统aes加密算法配合密码实现文件加解密

1、使用openssl（开源安全套接层）加密一个文件（test1.txt为原始文件，test1.enc为加密之后的文件）

```
openssl enc -e -aes256 -in test1.txt -out test1.enc
```

解释：enc （encrypt）表示对文件进行对称加密或解密， -e 表示对一个文件进行加密操作，-aes256 表示使用aes256 算法进行加密， -in表示需要被加密的文件， -out 表示加密之后生成的新文件。加密过程中会要求输入一个加密密码， 重复输入两次即可完成对文件的加密。（ 同时由于kali系统添加更加复杂的加密算法， 加密过程会有警告提示不推荐使用，但不影响实验效果）。

2、使用openssl解密一个文件（test1.enc为加密文件，test1.txt为解密之后的文件）

```
openssl enc -d -aes256 -in test1.enc -out test1.txt
```

解释：-d 表示对文件进行解密操作，-in表示需要被解密的文件，-out表示揭秘之后生成的新文件，解密一个文件的时候会要求输入加密文件时设置的密码才能进行解密，

## 4.2 非对称加密算法

非对称加密常见的算法

```
RSA
```

  - DH（迪菲.赫尔曼）

所谓非对称加密算法

  - 加密的密钥和解密的密钥是2个不同的密钥，这2个密钥称之为一对公私钥！

公私钥关系：

  - 非对称加密算法自己产生一对公私钥，而不需要双方协商！！

  - 公钥：是要公开的！

  - 私钥：自己私有，不发送给任何人！！！

  - 公钥和私钥为互相加解密关系！

  - 公钥和私钥不可以互相逆推！

  - 加密双方要彼此交换各自的公钥！

![PKI 完整版 示意图 1](/images/windows-notes/pki/img-01.png)

![PKI 完整版 示意图 2](/images/windows-notes/pki/img-02.png)

非对称加密算法优点

  - 安全（机密性，身份验证）

非对称加密算法缺点

  - 效率低，速度慢！

机密性

  - 使用对方的公钥加密！对方使用自己的私钥解密！

数字签名

  - 用自己的私钥对摘要信息加密！

举个例子：在kali系统中生成一对密钥，并通过公钥加密私钥解密

1 、首先需要使用openssl 生成一个2048 位的密钥rsa. key 文件(rsa.key 密钥文件中包含了私钥和公钥）

```
openssl genrsa -out rsa.key 2048
```

2、然后从rsa.key密钥文件中提取出公钥pub.key

```
openssl rsa -in rsa.key -pubout -out pub.key
```

对比图，下图分别是私钥和公钥，虽然位置略有不同，但仍然可以找到相同的字符串内容

![PKI 完整版 示意图 3](/images/windows-notes/pki/img-03.png)

3、使用pub.key公钥加密一个文件（test2.txt 为原始文件，test2.enc为加密之后的文件）

```
openssl pkeyutl -encrypt -inkey pub.key -pubin -in test2.txt -out test2.enc
```

4、使用key 私解密一个文件(test2.enc 为加密的文件，test3.txt 为解密之后的文件）

```
openssl pkeyutl -decrypt -inkey rsa.key -in test2.enc -out test3.txt
```

## 4.3 哈希算法（解决数据完整性）

常见的哈希算法

```
MD5
SHA
```

哈希加密算法特点

  - 加密不可逆！

哈希值 == hash值 == 摘要值： 一般是4个字节哈希算法作用

  - 保证数据的完整性

哈希算法流程

![PKI 完整版 示意图 4](/images/windows-notes/pki/img-04.png)

完整的加密流程图：（包括机密性、完整性、身份验证）

![PKI 完整版 示意图 5](/images/windows-notes/pki/img-05.png)

### 0x05 数字证书

数字证书

  - 用于公正/保证公钥的合法性！

CA

（证书颁发机构）Certificate Authority

  - 作用：接受证书申请、制作证书、颁发证书。

如何对自己的公钥进行权威认证？

证书格式

  - 遵循X.509标准

证书内容：

  - 使用者/申请者的公钥

  - 使用者的表示信息（域名，ip，名称，电子邮件地址）

  - 证书有效期

  - 颁发者的标识信息

  - 颁发者的数字签名（钢印、指纹）

![PKI 完整版 示意图 6](/images/windows-notes/pki/img-06.png)

### 0x05 实验

## 实验目标

  - 部署HTTPS服务器

## 实验环境

  - 开启3台虚拟机：

```
------ win2008 作为CA认证服务器 dns服务器：192.168.188.136
------ win2003 web服务器雷池：192.168.188.128
------ win7 作为客户机 ：192.168.188.130
```

  - ------ 必须还原快照，并桥接到vmnet8NAT

## 实验步骤

1.还原快照，开机，桥接到vmnet8也就是nat模式

2.测试连通性！

3.开启80域名访问

  - win2019准备好leichi网站文件夹，安装IIS（参考web服务动态网站建立），安装完毕后，

然后我们新建leichi网站，并绑定http://www.leichi.com

  - win2019建立ca建立过程中会建立web服务而且IIS会自带一个默认网站，千万不要动这个默认网站！！！

并在服务器上安装DNS角色，然后添加www.leichi.com域名解析为192.168.188.128

  - 此时可以去客户机上验证是否可以通过域名访问网站！

![PKI 完整版 示意图 7](/images/windows-notes/pki/img-07.png)

![PKI 完整版 示意图 8](/images/windows-notes/pki/img-08.png)

![PKI 完整版 示意图 9](/images/windows-notes/pki/img-09.png)

![PKI 完整版 示意图 10](/images/windows-notes/pki/img-10.png)

4.搭建部署CA服务器(类似于政府/公安局)

  - 在win2008上安装CA角色组件：

  - 计算机右键管理---角色--添加角色---选择Active Directory 证书服务

要求在win2008上测试使用http://192.168.188.136/certsrv可以访问CA服务器即可！

5、创建证书申请08证书请求文件建立

![PKI 完整版 示意图 11](/images/windows-notes/pki/img-11.png)

![PKI 完整版 示意图 12](/images/windows-notes/pki/img-12.png)

![PKI 完整版 示意图 13](/images/windows-notes/pki/img-13.png)

![PKI 完整版 示意图 14](/images/windows-notes/pki/img-14.png)

上一步没有指定路径，发现原来在c:\windows\system32中

![PKI 完整版 示意图 15](/images/windows-notes/pki/img-15.png)

6、向CA服务器提交申请单！

![PKI 完整版 示意图 16](/images/windows-notes/pki/img-16.png)

方法：在win2008上，打开IE，输入：http://192.168.188.136/certsrv，选择申请证书--高级申请-

  - -base64编码，提交！

![PKI 完整版 示意图 17](/images/windows-notes/pki/img-17.png)

![PKI 完整版 示意图 18](/images/windows-notes/pki/img-18.png)

![PKI 完整版 示意图 19](/images/windows-notes/pki/img-19.png)

7、CA审核，并颁发证书！

![PKI 完整版 示意图 20](/images/windows-notes/pki/img-20.png)

![PKI 完整版 示意图 21](/images/windows-notes/pki/img-21.png)

8、web服务器下载颁发好的证书

打开IE，输入：http://192.168.188.136/certsrv，下载颁发后得证书！

![PKI 完整版 示意图 22](/images/windows-notes/pki/img-22.png)

![PKI 完整版 示意图 23](/images/windows-notes/pki/img-23.png)

9、导入证书到IIS服务器中08导入证书

![PKI 完整版 示意图 24](/images/windows-notes/pki/img-24.png)

![PKI 完整版 示意图 25](/images/windows-notes/pki/img-25.png)

![PKI 完整版 示意图 26](/images/windows-notes/pki/img-26.png)

![PKI 完整版 示意图 27](/images/windows-notes/pki/img-27.png)

10、win7客户机访问并验证https客户机使用https://www.leichi.com访问，验证是否成功访问，此时应该会报错，显示为不信任CA，但依然可以选择继续访问成功！

![PKI 完整版 示意图 28](/images/windows-notes/pki/img-28.png)

==================接下来解决报错问题====================

12、客户机信任CA机构首先在win7客户上，IE关闭安全增强，如下2个图：

![PKI 完整版 示意图 29](/images/windows-notes/pki/img-29.png)

![PKI 完整版 示意图 30](/images/windows-notes/pki/img-30.png)

接下来，CA证书并信任之：安装导入CA证书到信任列表中

![PKI 完整版 示意图 31](/images/windows-notes/pki/img-31.png)

![PKI 完整版 示意图 32](/images/windows-notes/pki/img-32.png)

火狐

![PKI 完整版 示意图 33](/images/windows-notes/pki/img-33.png)

13、再次用客户机win7，访问https://www.leichi.com，没有再报错，成功！

![PKI 完整版 示意图 34](/images/windows-notes/pki/img-34.png)

====================接下来解决禁用http 80访问问题，只能用https访问========================

14、禁止使用http访问，必须使用https方式访问!

![PKI 完整版 示意图 35](/images/windows-notes/pki/img-35.png)

15、验证，此时在win7客户机上，应该只能通过https访问！
