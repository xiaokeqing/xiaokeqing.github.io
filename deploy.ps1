<#
  deploy.ps1 — 构建博客并发布到 GitHub Pages 的 gh-pages 分支

  用法（在 blog 目录下）：
      powershell -ExecutionPolicy Bypass -File .\deploy.ps1

  为什么需要这个脚本：
      本站当前采用「分支部署」——源码在 main，构建产物在 gh-pages。
      正常情况下这应该由 GitHub Actions 自动完成，但推送 workflow 文件
      需要 token 具备 workflow 权限，暂时未开通，所以先用手动方式。
      等 Actions 启用后，这个脚本就可以弃用。

  脚本做的事：
      1. 用 Hugo 构建站点
      2. 把产物复制到临时目录并初始化一个独立仓库
      3. 强制推送到 gh-pages 分支（GitHub Pages 会自动重新发布）
#>

$ErrorActionPreference = 'Stop'
$BlogDir = $PSScriptRoot
$TmpDir  = Join-Path (Split-Path $BlogDir -Parent) '.ghpages-tmp'
$Remote  = 'https://github.com/xiaokeqing/xiaokeqing.github.io.git'

# ---------- 1. 找到 hugo ----------
$hugo = (Get-Command hugo -ErrorAction SilentlyContinue).Source
if (-not $hugo) {
    $candidates = @(
        "$env:LOCALAPPDATA\Microsoft\WinGet\Packages",
        "$env:ProgramFiles\Hugo",
        "$env:LOCALAPPDATA\Programs\Hugo"
    )
    foreach ($root in $candidates) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        $found = Get-ChildItem -Path $root -Recurse -Filter 'hugo.exe' -ErrorAction SilentlyContinue |
                 Select-Object -First 1
        if ($found) { $hugo = $found.FullName; break }
    }
}
if (-not $hugo) { throw '找不到 hugo.exe，请确认已安装 Hugo extended' }
Write-Host "使用 Hugo: $hugo" -ForegroundColor Cyan

# ---------- 2. 构建 ----------
Write-Host "`n[1/4] 构建站点..." -ForegroundColor Cyan
Push-Location $BlogDir
try {
    & $hugo --gc --minify --cleanDestinationDir
    if ($LASTEXITCODE -ne 0) { throw "Hugo 构建失败（退出码 $LASTEXITCODE）" }

    $publicDir = Join-Path $BlogDir 'public'
    $fileCount = (Get-ChildItem -Recurse -File $publicDir).Count
    Write-Host "      构建完成：$fileCount 个文件" -ForegroundColor Green

    # ---------- 3. 准备发布目录 ----------
    Write-Host "`n[2/4] 准备发布目录..." -ForegroundColor Cyan
    if (Test-Path -LiteralPath $TmpDir) { Remove-Item -Recurse -Force $TmpDir }
    New-Item -ItemType Directory -Force $TmpDir | Out-Null
    Copy-Item "$publicDir\*" $TmpDir -Recurse -Force
    # .nojekyll 阻止 GitHub 用 Jekyll 处理产物（否则下划线开头的文件会被忽略）
    New-Item -ItemType File -Force (Join-Path $TmpDir '.nojekyll') | Out-Null

    # ---------- 4. 提交并推送 ----------
    Write-Host "`n[3/4] 提交..." -ForegroundColor Cyan
    Push-Location $TmpDir
    try {
        git init -b gh-pages --quiet
        git add -A
        $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        git -c user.name=xiaokeqing -c user.email=3053970237@qq.com `
            commit --quiet -m "deploy: 发布站点构建产物（$stamp）"

        Write-Host "`n[4/4] 推送到 gh-pages..." -ForegroundColor Cyan
        git remote add origin $Remote 2>$null
        git push -f origin gh-pages
        if ($LASTEXITCODE -ne 0) { throw '推送失败' }
    }
    finally { Pop-Location }
}
finally { Pop-Location }

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " 发布完成" -ForegroundColor Green
Write-Host " 网站：https://xiaokeqing.github.io/" -ForegroundColor Green
Write-Host " （GitHub Pages 需要约 1 分钟重新发布）" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Green
