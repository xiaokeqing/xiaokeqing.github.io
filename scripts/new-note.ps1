<#
  scripts/new-note.ps1 —— 命令行一键新建笔记（第十一轮 E 项）

  与根目录的「新建文章.ps1」的区别：
    · 那个是交互式向导（问一句答一句），适合偶尔写一篇；
    · 这个是**带参数的命令行工具**，适合脚本化 / 连着建几篇 / 从模板起骨架。

  用法（在仓库根目录）：
    .\scripts\new-note.ps1 -Title "安全运营周报 2026-W42" -Category "安全运营" `
        -Tags "周报,安全运营" -Summary "本周数据与口径" -Slug "weekly-2026-w42"
    .\scripts\new-note.ps1 -Title "..." -Category "..." -Tags "a,b" -Summary "..." -Publish

  参数：
    -Title     必填。文章标题（中文可以）。
    -Category  分类，默认「工程实践」。写进 front matter 的 categories。
    -Tags      标签，逗号分隔（中英文逗号都行）。
    -Summary   摘要（一句话）。留空则自动填一句提醒你补。
    -Slug      可选。文件名（会出现在 URL 里）；不给就按时间戳生成。
    -NoDraft   生成 draft: false（默认是 draft: true —— 写完自己改，防误发）。
    -Publish   默认【不提交】。给 -Publish 才执行 git add + commit。
               **永远不 push**（站主网络问题，推送由站主/父会话决定）。
    -Open      生成后用记事本打开。
    -Force     同名文件存在时覆盖。

  文件名规范：<日期>-<短标题>.md（例如 2026-10-13-verifiable-deploy-chain.md）
    —— 日期前缀让 ls / git log 天然按时间排序，短标题让 URL 可读。

  纪律：
    · 只落盘，不推送；-Publish 也只 commit 这一个新文件（不带 -A / -u）；
    · 已存在同名文件时拒绝覆盖（除非显式 -Force）。
    · 本文件必须存成【UTF-8 with BOM】：Windows PowerShell 5.1 读无 BOM 的 .ps1
      会按 ANSI 解码，中文会乱码并把 here-string 的结束标记一起破坏（实测踩过）。
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Title,
  [string]$Category = '工程实践',
  [string]$Tags = '',
  [string]$Summary = '',
  [string]$Slug = '',
  [switch]$NoDraft,
  [switch]$Publish,
  [switch]$Open,
  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repo     = Split-Path -Parent $PSScriptRoot
$postsDir = Join-Path $repo 'content\posts'
if (-not (Test-Path -LiteralPath $postsDir)) { New-Item -ItemType Directory -Force $postsDir | Out-Null }

$today = Get-Date -Format 'yyyy-MM-dd'

# ---------- slug ----------
if ([string]::IsNullOrWhiteSpace($Slug)) {
  $Slug = 'note-' + (Get-Date -Format 'HHmmss')
  Write-Host "[提示] 没有给 -Slug，文件名用默认值 $Slug（建议显式指定英文短名，URL 更好看）" -ForegroundColor Yellow
}
$Slug = ($Slug.Trim().ToLower() -replace '[^\w\-]', '-') -replace '-+', '-'
$Slug = $Slug.Trim('-')

$fileName = "$today-$Slug.md"
$target = Join-Path $postsDir $fileName
if ((Test-Path -LiteralPath $target) -and (-not $Force)) {
  Write-Host "[中止] 已存在：$target" -ForegroundColor Red
  Write-Host "       要覆盖请加 -Force；或换一个 -Slug。" -ForegroundColor Red
  exit 1
}

# ---------- tags ----------
$tagList = @()
if (-not [string]::IsNullOrWhiteSpace($Tags)) {
  $tagList = ($Tags -split '[,，]') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }
}
$tagsYaml = ($tagList | ForEach-Object { '"' + ($_ -replace '"', '\"') + '"' }) -join ', '

# ---------- summary ----------
if ([string]::IsNullOrWhiteSpace($Summary)) {
  $Summary = '待补：一句话说清这篇要回答什么问题（面试官只会读这一句）。'
}

$isDraft = if ($NoDraft) { 'false' } else { 'true' }

# 用【行数组】拼正文，不在这里用 here-string：
# PowerShell 5.1 对无 BOM 脚本的编码判断很脆，行数组最不容易被编码问题破坏。
$lines = @(
  '---'
  ('title: "' + ($Title -replace '"', '\"') + '"')
  ('date: ' + $today)
  ('draft: ' + $isDraft)
  ('tags: [' + $tagsYaml + ']')
  ('categories: ["' + ($Category -replace '"', '\"') + '"]')
  ('summary: "' + ($Summary -replace '"', '\"') + '"')
  ('description: "' + ($Summary -replace '"', '\"') + '"')
  'ShowToc: true'
  '---'
  ''
  '## 这篇要回答什么'
  ''
  '（先写一句话：读完这篇，读者应该能回答哪个具体问题。）'
  ''
  '## 背景'
  ''
  '（为什么会有这件事。有可核对的数字就写数字；没有就说明「没有可核对的数字」。）'
  ''
  '## 做了什么'
  ''
  '（判据 / 动作 / 命令。**只写自己做过的**。）'
  ''
  '## 证据'
  ''
  '（可核对的东西：退出码、字段、文件、时间戳。截图放 static/images/ 下再引用。）'
  ''
  '## 代价与没做到的'
  ''
  '（至少一条。写不出来通常说明没细看。）'
  ''
  '---'
  ''
  '*本文的数字与命令来自真实执行记录；取不到的地方写「未接入」，不估算。*'
)

$text = ($lines -join "`r`n") + "`r`n"
[System.IO.File]::WriteAllText($target, $text, (New-Object System.Text.UTF8Encoding($false)))

Write-Host "[已创建] $target" -ForegroundColor Green
if ($isDraft -eq 'true') {
  Write-Host "         draft: true —— 写完把它改成 false 才会被发布。" -ForegroundColor Yellow
}

# ---------- 可选：提交（绝不推送） ----------
if ($Publish) {
  Push-Location $repo
  try {
    & git add -- "$target"
    if ($LASTEXITCODE -ne 0) { throw "git add 失败" }
    & git commit -m ("post: " + $Title)
    if ($LASTEXITCODE -ne 0) { throw "git commit 失败" }
    Write-Host "[已提交] 仅本地 commit，未 push（推送请自行执行）。" -ForegroundColor Green
  } finally { Pop-Location }
} else {
  Write-Host "         未提交（默认行为）。要本地提交加 -Publish；本脚本永远不会 push。" -ForegroundColor DarkGray
}

if ($Open) { Start-Process notepad.exe $target }
