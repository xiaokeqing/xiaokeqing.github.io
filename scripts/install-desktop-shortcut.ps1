<#
  scripts/install-desktop-shortcut.ps1 —— 在桌面建一个「发笔记」快捷方式

  用法（双击 scripts\安装桌面快捷方式.ps1 或直接跑）：
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-desktop-shortcut.ps1
    powershell ... -File .\scripts\install-desktop-shortcut.ps1 -Name "写笔记"
    powershell ... -File .\scripts\install-desktop-shortcut.ps1 -Directory "$env:TEMP"   # 自检用，不碰真桌面

  做三件事：定目标目录（默认桌面，含 OneDrive 重定向）→ 建指向 scripts\发笔记.cmd 的 .lnk → 打印结果。
  本文件必须 UTF-8 with BOM（PS 5.1 读无 BOM 的中文会乱码）。
#>
[CmdletBinding()]
param(
  [string]$Name = '发笔记',
  [string]$Directory = ''
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$cmd  = Join-Path $PSScriptRoot '发笔记.cmd'

if (-not (Test-Path -LiteralPath $cmd)) { throw "找不到入口脚本：$cmd" }

if ([string]::IsNullOrWhiteSpace($Directory)) {
  $Directory = [Environment]::GetFolderPath('Desktop')
}
if ([string]::IsNullOrWhiteSpace($Directory) -or -not (Test-Path -LiteralPath $Directory)) {
  throw "找不到目标目录（Directory=$Directory）"
}
$lnk = Join-Path $Directory ($Name + '.lnk')

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath       = (Join-Path $env:SystemRoot 'System32\cmd.exe')
$sc.Arguments        = '/c "' + $cmd + '"'
$sc.WorkingDirectory = $repo
$sc.Description      = '发笔记：填标题 → 自动建 md → 写完保存关闭 → 自动构建并给出发布命令'
$sc.IconLocation     = (Join-Path $env:SystemRoot 'System32\shell32.dll') + ',70'
$sc.Save()

if (-not (Test-Path -LiteralPath $lnk)) { throw "创建后找不到快捷方式：$lnk" }
$chk = $ws.CreateShortcut($lnk)
Write-Host "[已创建] $lnk" -ForegroundColor Green
Write-Host ("         目标：{0}" -f $chk.TargetPath) -ForegroundColor DarkGray
Write-Host ("         参数：{0}" -f $chk.Arguments) -ForegroundColor DarkGray
Write-Host ("         工作目录：{0}" -f $chk.WorkingDirectory) -ForegroundColor DarkGray
Write-Host '         用法：双击图标 → 填标题 → 写完保存关闭 → 看窗口里的发布命令' -ForegroundColor DarkGray
Write-Host '         想连发布一起做：右键快捷方式 → 属性 → 在「目标」末尾加  -Publish' -ForegroundColor DarkGray
exit 0
