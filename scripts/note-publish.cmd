@echo off
rem ASCII-named alias of the Chinese-named launcher (identical behavior).
rem Content is pure ASCII on purpose: no BOM, no codepage risk.
chcp 65001 >nul
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0note-publish.ps1" %*
set RC=%ERRORLEVEL%
echo.
if "%~1"=="" pause
exit /b %RC%
