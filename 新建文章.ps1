<#
  新建文章.ps1 —— 一键创建一篇新文章

  用法：在 blog 目录下双击或右键运行，按提示输入即可。

  它会：
    1. 问你文件名和标题
    2. 用 archetypes/posts.md 模板生成 content/posts/<文件名>.md
    3. 用记事本打开让你直接写

  写完发布：再运行 deploy.ps1
#>

$ErrorActionPreference = 'Stop'
$BlogDir   = $PSScriptRoot
$PostsDir  = Join-Path $BlogDir 'content\posts'
$Archetype = Join-Path $BlogDir 'archetypes\posts.md'

if (-not (Test-Path -LiteralPath $Archetype)) { throw "找不到模板：$Archetype" }
if (-not (Test-Path -LiteralPath $PostsDir)) { New-Item -ItemType Directory -Force $PostsDir | Out-Null }

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " 新建文章" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "文件名（用英文或拼音，会出现在网址里）" -ForegroundColor Yellow
Write-Host "例如：alert-aggregation" -ForegroundColor DarkGray
$slug = Read-Host "文件名"
if ([string]::IsNullOrWhiteSpace($slug)) { throw "文件名不能为空" }
$slug = ($slug.Trim() -replace '[^\w\-]', '-') -replace '-+', '-'
$slug = $slug.Trim('-')

Write-Host ""
Write-Host "文章标题（中文可以）" -ForegroundColor Yellow
Write-Host "例如：告警风暴怎么治" -ForegroundColor DarkGray
$title = Read-Host "标题"
if ([string]::IsNullOrWhiteSpace($title)) { throw "标题不能为空" }

$target = Join-Path $PostsDir "$slug.md"
if (Test-Path -LiteralPath $target) {
    Write-Host ""
    Write-Host "已存在同名文件：$target" -ForegroundColor Red
    $overwrite = Read-Host "覆盖吗？输入 y 确认"
    if ($overwrite -ne 'y') { Write-Host "已取消"; exit 0 }
}

# 用模板生成内容
$now = Get-Date -Format 'yyyy-MM-dd'
$body = [System.IO.File]::ReadAllText($Archetype, [System.Text.Encoding]::UTF8)
$body = $body -replace '\{\{ replace \.File\.ContentBaseName "-" " " \| title \}\}', $title
$body = $body -replace '\{\{ \.Date \}\}', $now

[System.IO.File]::WriteAllText($target, $body, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "已创建：$target" -ForegroundColor Green
Write-Host ""
Write-Host "注意：模板里 draft = true，写完记得改成 false 才会发布。" -ForegroundColor Yellow
Write-Host "      写完执行 deploy.ps1 即可上线。" -ForegroundColor Yellow
Write-Host ""

$open = Read-Host "现在用记事本打开它吗？(y/n)"
if ($open -eq 'y') { Start-Process notepad.exe $target }
