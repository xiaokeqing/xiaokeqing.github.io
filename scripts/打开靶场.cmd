@echo off
chcp 65001 >nul
setlocal
set HOST=secagent-srv2

echo ============================================
echo  打开靶场（Pikachu / DVWA / Juice Shop / WebGoat / WebWolf / DVNA / DSVW）
echo --------------------------------------------
echo  靶场只在服务器内网，公网没有入口。
echo  这个窗口就是在服务器和你电脑之间挖的那条隧道：
echo    本机 8081 -^> 服务器 Pikachu
echo    本机 8082 -^> 服务器 DVWA
echo    本机 8083 -^> 服务器 Juice Shop
echo    本机 8084 -^> 服务器 WebGoat
echo    本机 8087 -^> 服务器 WebWolf（WebGoat 配套：收邮件 / 伪造请求）
echo    本机 8085 -^> 服务器 DVNA
echo    本机 8086 -^> 服务器 DSVW
echo.
echo  浏览器会自动打开。用完了直接关掉这个黑窗口，
echo  隧道就断了，服务器那边不留任何对外入口。
echo ============================================
echo.

rem 先让 ssh 把端口拉起来，再开浏览器（否则浏览器先打开会报拒绝连接）
start "" cmd /c "timeout /t 5 >nul & start "" http://127.0.0.1:8081/ & start "" http://127.0.0.1:8082/ & start "" http://127.0.0.1:8083/ & start "" http://127.0.0.1:8084/ & start "" http://127.0.0.1:8085/ & start "" http://127.0.0.1:8086/ & start "" http://127.0.0.1:8087/"

ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L 8081:127.0.0.1:8081 -L 8082:127.0.0.1:8082 -L 8083:127.0.0.1:8083 -L 8084:127.0.0.1:8084 -L 8085:127.0.0.1:8085 -L 8086:127.0.0.1:8086 -L 8087:127.0.0.1:8087 %HOST%

echo.
echo 隧道已关闭。
pause
