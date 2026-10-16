@echo off
rem Double-click launcher for the B-version note watcher (auto publish on save).
rem Logic lives in scripts\note-watch.ps1. Content is pure ASCII on purpose: no BOM, no codepage risk.
rem Usage: double-click = start watching (foreground, Ctrl+C to stop);
rem        note-watch.cmd -Stop   = turn auto-publish OFF;
rem        note-watch.cmd -Start  = turn it back ON.
chcp 65001 >nul
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0note-watch.ps1" %*
set RC=%ERRORLEVEL%
echo.
if "%~1"=="" pause
exit /b %RC%
