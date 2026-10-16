<#
  scripts/install-note-watch.ps1 —— 显式安装/卸载"发笔记 B 版看守"的开机自启（2026-10-16）

  ★为什么要有这个脚本：看守**绝不会自己加启动项**（项目红线）。开机自启必须由站主显式运行本脚本。

  它会做三件事（都只作用于**当前用户**，不需要管理员）：
    1) 在「启动」文件夹建一个指向 note-watch.ps1 的隐藏快捷方式（登录后自动看守）
    2) 在桌面建一个「关掉自动发布」快捷方式（一键停）
    3) 清掉 STOP 文件（否则看守起来也不会发）

  用法：
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-note-watch.ps1
    powershell ... -File .\scripts\install-note-watch.ps1 -DryRun        # 只打印打算做什么，不落盘
    powershell ... -File .\scripts\install-note-watch.ps1 -Uninstall     # 全部撤掉并写 STOP
    powershell ... -File .\scripts\install-note-watch.ps1 -StartupDir "$env:TEMP\x" -DesktopDir "$env:TEMP\x"   # 自检用

  本文件必须 UTF-8 with BOM（PS 5.1 读无 BOM 的中文会乱码）。
#>
[CmdletBinding()]
param(
  [switch]$Uninstall,
  [switch]$DryRun,
  [string]$StartupDir = '',
  [string]$DesktopDir = ''
)

$ErrorActionPreference = 'Stop'
$repo   = Split-Path -Parent $PSScriptRoot
$ps1    = Join-Path $PSScriptRoot 'note-watch.ps1'
$stopCmd = Join-Path $PSScriptRoot 'note-watch-stop.cmd'
$plainPwsh = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

$stateDir = Join-Path $env:LOCALAPPDATA 'xk-note'
if (-not (Test-Path -LiteralPath $stateDir)) { New-Item -ItemType Directory -Force -Path $stateDir | Out-Null }
$stopFile = Join-Path $stateDir 'STOP'

if (-not (Test-Path -LiteralPath $ps1)) { throw "找不到看守脚本：$ps1" }
if (-not (Test-Path -LiteralPath $stopCmd)) { throw "找不到停止脚本：$stopCmd" }

if ([string]::IsNullOrWhiteSpace($StartupDir)) {
  $StartupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
}
if ([string]::IsNullOrWhiteSpace($DesktopDir)) {
  $DesktopDir = [Environment]::GetFolderPath('Desktop')
}

$lnkStartup = Join-Path $StartupDir '发笔记-自动发布.lnk'
$lnkStop    = Join-Path $DesktopDir '关掉自动发布.lnk'
$ws = New-Object -ComObject WScript.Shell

function New-Shortcut([string]$path, [string]$target, [string]$args, [string]$desc, [int]$iconIndex) {
  if ($DryRun) { Write-Host "[DryRun] 会创建：$path" -ForegroundColor Yellow; return }
  $sc = $ws.CreateShortcut($path)
  $sc.TargetPath       = $target
  $sc.Arguments        = $args
  $sc.WorkingDirectory = $repo
  $sc.Description      = $desc
  $sc.IconLocation     = (Join-Path $env:SystemRoot 'System32\shell32.dll') + ",$iconIndex"
  $sc.WindowStyle      = 7
  $sc.Save()
  if (-not (Test-Path -LiteralPath $path)) { throw "创建后找不到：$path" }
}

Write-Host '============ 发笔记 B 版：自动发布看守 ============' -ForegroundColor Cyan
Write-Host "仓库：$repo"
Write-Host "启动目录：$StartupDir"
Write-Host "桌面目录：$DesktopDir"
Write-Host ''

if ($Uninstall) {
  foreach ($f in @($lnkStartup, $lnkStop)) {
    if (Test-Path -LiteralPath $f) {
      if ($DryRun) { Write-Host "[DryRun] 会删除：$f" -ForegroundColor Yellow }
      else { Remove-Item -LiteralPath $f -Force; Write-Host "[已删除] $f" -ForegroundColor Green }
    } else { Write-Host "[本来就没有] $f" -ForegroundColor DarkGray }
  }
  if (-not $DryRun) {
    [System.IO.File]::WriteAllText($stopFile, "uninstalled at $(Get-Date -Format s)`r`n")
    Write-Host "[已写 STOP] 看守起来也不会发（手动恢复：note-watch.cmd -Start）" -ForegroundColor Yellow
  }
  Write-Host ''
  Write-Host '卸载完成。A 版（双击「发笔记」）不受影响。' -ForegroundColor Cyan
  exit 0
}

if (-not (Test-Path -LiteralPath $StartupDir)) { throw "找不到启动文件夹：$StartupDir" }
if (-not (Test-Path -LiteralPath $DesktopDir)) { throw "找不到桌面目录：$DesktopDir" }

# 1) 登录自启：隐藏窗口跑看守
New-Shortcut $lnkStartup $plainPwsh ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f $ps1) `
  '发笔记 B 版：监视 content\posts，保存并关闭后自动提交+构建+门禁+推送+发布' 44

# 2) 桌面：一键关掉
New-Shortcut $lnkStop (Join-Path $env:SystemRoot 'System32\cmd.exe') ('/c "{0}"' -f $stopCmd) `
  '关掉「发笔记」的自动发布（写 STOP 并结束看守进程）' 131

# 3) 清 STOP（否则看守起来也不发）
if (-not $DryRun) {
  if (Test-Path -LiteralPath $stopFile) { Remove-Item -LiteralPath $stopFile -Force; Write-Host '[已清除 STOP]' -ForegroundColor Green }
}

Write-Host ''
Write-Host '安装完成。说明：' -ForegroundColor Cyan
Write-Host '  · 登录后自动看守（隐藏窗口）—— 现在就已生效；想立刻开始不必重启：双击 scripts\note-watch.cmd' -ForegroundColor DarkGray
Write-Host '  · 日志：%LOCALAPPDATA%\xk-note\watcher.log（失败还会弹气泡 + 写 last-failure.txt）' -ForegroundColor DarkGray
Write-Host '  · 关掉：双击桌面「关掉自动发布」，或跑 note-watch.cmd -Stop' -ForegroundColor DarkGray
Write-Host '  · 撤销自启：本脚本加 -Uninstall' -ForegroundColor DarkGray
Write-Host '  · A 版（双击「发笔记」：只建文+构建+给命令，不自动发）完全不受影响' -ForegroundColor DarkGray
Write-Host '==================================================' -ForegroundColor Cyan
exit 0
