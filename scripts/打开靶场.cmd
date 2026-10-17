@echo off
chcp 65001 >nul
setlocal
set HOST=secagent-srv2

echo ============================================
echo  打开靶场（Pikachu / DVWA / Juice Shop）
echo --------------------------------------------
echo  靶场只在服务器内网，公网没有入口。
echo  这个窗口就是在服务器和你电脑之间挖的那条隧道：
echo    本机 8081 -^> 服务器 Pikachu
echo    本机 8082 -^> 服务器 DVWA
echo    本机 8083 -^> 服务器 Juice Shop
echo.
echo  浏览器会自动打开。用完了直接关掉这个黑窗口，
echo  隧道就断了，服务器那边不留任何对外入口。
echo ============================================
echo.

rem 先让 ssh 把端口拉起来，再开浏览器（否则浏览器先打开会报拒绝连接）
start "" cmd /c "timeout /t 5 >nul & start "" http://127.0.0.1:8081/ & start "" http://127.0.0.1:8082/ & start "" http://127.0.0.1:8083/"

ssh -N -o ExitOnForwardFailure=yes -L 8081:127.0.0.1:8081 -L 8082:127.0.0.1:8082 -L 8083:127.0.0.1:8083 %HOST%

echo.
echo 隧道已关闭。
pause
