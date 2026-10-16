<#
  scripts/安装桌面快捷方式.ps1 —— 中文名入口（薄包装，逻辑在 install-desktop-shortcut.ps1）
  必须 UTF-8 with BOM。
#>
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'install-desktop-shortcut.ps1') @args
exit $LASTEXITCODE
