@echo off
rem Double-click entry for the desktop note tool (Chinese-named launcher).
rem Logic lives in scripts\note-publish.ps1. Content is pure ASCII on purpose: no BOM, no codepage risk.
chcp 65001 >nul
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0note-publish.ps1" %*
set RC=%ERRORLEVEL%
echo.
if "%~1"=="" pause
exit /b %RC%
