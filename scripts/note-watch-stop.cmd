@echo off
rem Turns the B-version note watcher OFF (writes STOP file, ends the watcher process).
rem ASCII only on purpose: no BOM, no codepage risk.
chcp 65001 >nul
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0note-watch.ps1" -Stop
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%
