---
title: "Tomcat 部署：JDK 与 Catalina 启动"
date: 2026-10-19T11:00:00+08:00
draft: false
categories: ["linux系统"]
tags: ["Linux", "Tomcat", "Java", "课程笔记"]
summary: "先装 JDK 再装 Tomcat 的顺序、用 startup.sh / catalina.sh 命令启动而不是任务管理器、开启 manager 远程访问，以及 Linux 下的部署实录。"
description: "先装 JDK 再装 Tomcat 的顺序、用 startup.sh / catalina.sh 命令启动而不是任务管理器、开启 manager 远程访问，以及 Linux 下的部署实录。"
ShowToc: true
---

> 来源：Linux 服务基础课程讲义（`Tomcat.pdf`，共 6 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

## Tomcat 的安装与配置

首先需要安装两个软件tomcat和java，先装java-jdk再装tomcat

![Tomcat 部署 示意图 1](/images/linux-notes/tomcat/img-01.webp)

![Tomcat 部署 示意图 2](/images/linux-notes/tomcat/img-02.webp)

启动tomcat，不要使用右下角的任务管理器管理tomcat使用命令启动#linux部署案例

```
root@VulTomcatUbuntu:~/apache-tomcat-8.5.32/bin# pwd
/root/apache-tomcat-8.5.32/bin
root@VulTomcatUbuntu:~/apache-tomcat-8.5.32/bin# chmod 755 startup.sh
root@VulTomcatUbuntu:~/apache-tomcat-8.5.32/bin# chmod 755 catalina.sh
root@VulTomcatUbuntu:~/apache-tomcat-8.5.32/bin# ./startup.sh
Using CATALINA_BASE:   /root/apache-tomcat-8.5.32
Using CATALINA_HOME:   /root/apache-tomcat-8.5.32
Using CATALINA_TMPDIR: /root/apache-tomcat-8.5.32/temp
Using JRE_HOME:        /usr
Using CLASSPATH:       /root/apache-tomcat-8.5.32/bin/bootstrap.jar:/root/apache-
tomcat-8.5.32/bin/tomcat-juli.jar
Tomcat started.
root@VulTomcatUbuntu:~/apache-tomcat-8.5.32/bin#
```

  - 开启manager 远程访问

```
D:\apache-tomcat-8.5.32\webapps\manager\META-INF
/webapps/manager/META-INF/context.xml
```

![Tomcat 部署 示意图 3](/images/linux-notes/tomcat/img-03.webp)

![Tomcat 部署 示意图 4](/images/linux-notes/tomcat/img-04.webp)

```
<Context antiResourceLocking="false" privileged="true" >
<Valve className="org.apache.catalina.valves.RemoteAddrValve"
allow="^.*$" />
<Manager sessionAttributeValueClassNameFilter="java\.lang\.
(?:Boolean|Integer|Long|Number|String)|org\.apache\.catalina\.filters\.CsrfPreven
tionFilter\$LruCache(?:\$1)?|java\.util\.(?:Linked)?HashMap"/>
</Context>
```

  - 配置管理控制台

```
/conf/tomcat-users.xml
<role rolename="manager-gui"/>
<role rolename="manager-script"/>
<role rolename="manager-jmx"/>
<role rolename="manager-status"/>
<role rolename="admin-gui"/>
<role rolename="admin-script"/>
<user username="tomcat" password="tomcat" roles="manager-gui,manager-
script,manager-jmx,manager-status,admin-gui,admin-script"/>
```

配置完成后重启tomcat服务弱口令到getshell

使用tomcat/tomcat  ，登录Manager App 。

![Tomcat 部署 示意图 5](/images/linux-notes/tomcat/img-05.webp)

![Tomcat 部署 示意图 6](/images/linux-notes/tomcat/img-06.webp)

![Tomcat 部署 示意图 7](/images/linux-notes/tomcat/img-07.webp)

将jshell.jsp大马文件进行打包成war，在打包之前需要先观察该文件的密码

![Tomcat 部署 示意图 8](/images/linux-notes/tomcat/img-08.webp)

![Tomcat 部署 示意图 9](/images/linux-notes/tomcat/img-09.webp)

```
jar cvf jshell.war jshell.jsp
```

![Tomcat 部署 示意图 10](/images/linux-notes/tomcat/img-10.webp)

```
http://192.168.16.111:8080/jshell/jshell.jsp
```

![Tomcat 部署 示意图 11](/images/linux-notes/tomcat/img-11.webp)
