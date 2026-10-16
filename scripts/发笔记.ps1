<#
  scripts/发笔记.ps1 —— 中文名入口（薄包装，逻辑全在 note-publish.ps1，不复制第二份）

  直接用中文名调用时也能用：
    .\scripts\发笔记.ps1 -Title "安全运营周报" -NoEditor -NoBuild -NoCommit
  双击走的是 scripts\发笔记.cmd。

  注意：本文件与 note-publish.ps1 都必须存成 **UTF-8 with BOM**（无 BOM 时 PowerShell 5.1
  会按 GBK 读，中文会乱码）——项目实测踩过。
#>
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'note-publish.ps1') @args
exit $LASTEXITCODE
