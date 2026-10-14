<#
  publish-site-to-srv2.ps1 —— 把博客整站的 Hugo 构建产物发布到 srv2（经 SSH），原子切换。

  为什么需要它：
    站点现在托管在 srv2（宿主 nginx，回环 127.0.0.1:18080，对外只经 Cloudflare 命名隧道），
    不再是 GitHub Pages。发布要「先传完、校验完，再一次性露面」，避免半成品对外。

  它做什么：
    [1/6] 找 hugo（Get-Command 找不到就去 winget 目录里翻）
    [2/6] 构建：hugo --gc --minify --cleanDestinationDir
    [3/6] 产物基本特征校验：index.html 存在且 > 4 KB、文件数 > 0、产物里不出现 localhost
    [4/6] 打包 public/ 为 tar.gz（Windows 自带 tar.exe）
    [5/6] scp 上传到 srv2 的 /tmp，并同步接收脚本到 /opt/secagent/scripts/
    [6/6] 远端 sudo 跑 srv2-site-receive.sh（解包 → 校验 → 原子切换 → 自检，失败自动回滚）
          再本地复核：远端 index.html 的 sha256 == 本地；若给了 -CheckUrl，curl 公网 200 且字节数一致

  用法（Windows PowerShell 5.1，不是 pwsh）：
    powershell -ExecutionPolicy Bypass -File .\scripts\publish-site-to-srv2.ps1
    powershell -ExecutionPolicy Bypass -File .\scripts\publish-site-to-srv2.ps1 -FromRef HEAD
    powershell -ExecutionPolicy Bypass -File .\scripts\publish-site-to-srv2.ps1 -CheckUrl https://staging.xiaokeqing.cn/
    powershell -ExecutionPolicy Bypass -File .\scripts\publish-site-to-srv2.ps1 -DryRun

  参数：
    -FromRef <git-ref>  在临时目录里按该 ref 拉一份干净源码再构建（发布「已提交的版本」用它，
                        默认空 = 直接用当前工作区）。发布线上站点建议总是显式给 -FromRef HEAD，
                        避免把别人未完成的改版一起发出去。
    -CheckUrl <url>     发布后在站主这台机器上再验一次公网 URL（期望 200 且字节数与本地一致）
    -KeepRemoteTarball  保留远端 /tmp 里的 tar 包（默认删掉）
    -DryRun             只构建+校验+打包，不上传
#>
[CmdletBinding()]
param(
    [string]$SshHost = 'secagent-srv2',
    [string]$FromRef = '',
    [string]$CheckUrl = '',
    [switch]$KeepRemoteTarball,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
$BlogDir = Split-Path -Parent $PSScriptRoot
$Stamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
$WorkDir = Join-Path $env:TEMP "xk-site-publish-$Stamp"
$TmpTar  = Join-Path $env:TEMP "xk-site-$Stamp.tar.gz"
$RemoteTar = "/tmp/xk-site-$Stamp.tar.gz"
$ReceiveLocal = Join-Path $PSScriptRoot 'srv2-site-receive.sh'
$ReceiveRemote = '/opt/secagent/scripts/srv2-site-receive.sh'
$WorktreeAdded = $false
$MinIndexBytes = 4096

function Step($n, $text) { Write-Host "`n[$n] $text" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "    [OK] $text" -ForegroundColor Green }
function Warn($text) { Write-Host "    [!]  $text" -ForegroundColor Yellow }
function Die($text)  { Write-Host "    [X]  $text" -ForegroundColor Red; exit 1 }

function Invoke-Checked {
    param([string]$Exe, [string[]]$CmdArgs, [string]$What)
    # 注意：PS 5.1 在 $ErrorActionPreference='Stop' 下，原生命令往 stderr 写一行
    # （例如 `git worktree add` 的 "Preparing worktree..."）就会抛 NativeCommandError，
    # 让整个脚本看似失败、进程退出码变 1。这里临时放宽，只看退出码。
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Exe @CmdArgs } finally { $ErrorActionPreference = $eap }
    if ($LASTEXITCODE -ne 0) { Die "$What 失败（$Exe 退出码 $LASTEXITCODE）" }
}

# ---------- 0) 前置 ----------
Step '0/6' "环境检查（blog=$BlogDir）"
foreach ($exe in 'ssh', 'scp', 'tar.exe') {
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { Die "找不到 $exe（Windows 10 1803+ 自带 OpenSSH 与 tar）" }
}
if (-not (Test-Path -LiteralPath $ReceiveLocal)) { Die "缺少接收脚本：$ReceiveLocal" }
Ok "ssh / scp / tar.exe 都在"

# ---------- 1) hugo ----------
Step '1/6' '找 hugo'
$hugo = (Get-Command hugo -ErrorAction SilentlyContinue).Source
if (-not $hugo) {
    foreach ($root in @("$env:LOCALAPPDATA\Microsoft\WinGet\Packages", "$env:ProgramFiles\Hugo", "$env:LOCALAPPDATA\Programs\Hugo")) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        $found = Get-ChildItem -Path $root -Recurse -Filter 'hugo.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { $hugo = $found.FullName; break }
    }
}
if (-not $hugo) { Die '找不到 hugo.exe（需要 Hugo extended）' }
Ok "$hugo"
$ver = (& $hugo version) -join ' '
Ok $ver

# ---------- 2) 构建 ----------
if ($FromRef) {
    Step '2/6' "从 git ref 拉干净源码再构建：$FromRef"
    Push-Location $BlogDir
    try {
        Invoke-Checked 'git' @('rev-parse', '--verify', "$FromRef^{commit}") "解析 $FromRef"
        $sha = ((& git rev-parse "$FromRef^{commit}") -join '').Trim()
        if ($sha.Length -gt 7) { $sha = $sha.Substring(0, 7) }
        Ok "ref 提交：$sha"
        Invoke-Checked 'git' @('worktree', 'prune') 'git worktree prune'
        if (Test-Path -LiteralPath $WorkDir) { Remove-Item -Recurse -Force -LiteralPath $WorkDir }
        # 用 git worktree 而不是 `git archive` + 本地 tar 解包：
        # 实测 Windows 自带 bsdtar 解 git archive 的 UTF-8 成员名会翻车（"Invalid empty pathname"），
        # worktree 由 git 自己检出，中文文件名（docs/ 里那些）不会出问题。
        Invoke-Checked 'git' @('worktree', 'add', '--detach', '--force', $WorkDir, "$FromRef^{commit}") "git worktree add"
        Ok "干净源码：$WorkDir"
    } finally { Pop-Location }
    $BuildDir = $WorkDir
    $WorktreeAdded = $true
} else {
    Step '2/6' '构建（直接用当前工作区）'
    Warn '当前工作区可能含未提交改动；正式发布建议加 -FromRef HEAD'
    $BuildDir = $BlogDir
}

Push-Location $BuildDir
try {
    Invoke-Checked $hugo @('--gc', '--minify', '--cleanDestinationDir') 'hugo 构建'
    $PublicDir = Join-Path $BuildDir 'public'
    if (-not (Test-Path -LiteralPath (Join-Path $PublicDir 'index.html'))) { Die "构建产物里没有 index.html：$PublicDir" }
} finally { Pop-Location }

# ---------- 3) 产物基本特征校验 ----------
Step '3/6' '校验产物基本特征'
$indexPath = Join-Path $PublicDir 'index.html'
$indexLen  = (Get-Item -LiteralPath $indexPath).Length
if ($indexLen -le $MinIndexBytes) { Die "index.html 只有 $indexLen B（要求 > $MinIndexBytes B）—— 产物疑似被截断" }
$allFiles = Get-ChildItem -Path $PublicDir -Recurse -File
$totalBytes = ($allFiles | Measure-Object -Property Length -Sum).Sum
Ok ("index.html = {0:N0} B" -f $indexLen)
Ok ("文件数 = {0}，合计 {1:N2} MB" -f $allFiles.Count, ($totalBytes / 1MB))
$indexSha = (Get-FileHash -LiteralPath $indexPath -Algorithm SHA256).Hash.ToLower()
Ok "index.html sha256 = $($indexSha.Substring(0,16))..."
$localhostHits = @(Select-String -Path (Join-Path $PublicDir '*.html') -Pattern 'localhost' -SimpleMatch -ErrorAction SilentlyContinue)
if ($localhostHits.Count -gt 0) { Warn "产物里出现 localhost（$($localhostHits.Count) 处）—— SEO canonical 可能不对" }
else { Ok '产物里没有 localhost' }

# ---------- 4) 打包 ----------
Step '4/6' "打包 → $TmpTar"
if (Test-Path -LiteralPath $TmpTar) { Remove-Item -LiteralPath $TmpTar -Force }
Invoke-Checked 'tar.exe' @('-czf', $TmpTar, '-C', $PublicDir, '.') '打包'
$tarLen = (Get-Item -LiteralPath $TmpTar).Length
Ok ("tar.gz = {0:N2} MB" -f ($tarLen / 1MB))

if ($DryRun) {
    Write-Host "`n[DryRun] 已构建 + 校验 + 打包，未上传。包在：$TmpTar" -ForegroundColor Yellow
    exit 0
}

# ---------- 5) 上传 ----------
Step '5/6' "上传到 ${SshHost}:$RemoteTar（并同步接收脚本）"
Invoke-Checked 'scp' @('-q', '-o', 'BatchMode=yes', $TmpTar, "${SshHost}:$RemoteTar") 'scp 上传 tar 包'
Ok 'tar 包已上传'
Invoke-Checked 'scp' @('-q', '-o', 'BatchMode=yes', $ReceiveLocal, "${SshHost}:/tmp/srv2-site-receive.sh") 'scp 上传接收脚本'
Invoke-Checked 'ssh' @('-o', 'BatchMode=yes', $SshHost, "sudo -n install -m 0755 -o root -g root /tmp/srv2-site-receive.sh $ReceiveRemote") '安装接收脚本'
Ok "接收脚本已就位：$ReceiveRemote"

# ---------- 6) 远端切换 + 自检 ----------
Step '6/6' '远端解包 / 校验 / 原子切换 / 自检'
$remoteOut = & ssh -o BatchMode=yes $SshHost "sudo -n bash $ReceiveRemote $RemoteTar" 2>&1
$remoteText = ($remoteOut | Out-String)
Write-Host $remoteText
if ($LASTEXITCODE -ne 0) { Die "远端切换失败（ssh 退出码 $LASTEXITCODE）" }
if ($remoteText -notmatch 'RESULT=ok' -and $remoteText -notmatch 'RESULT=no-change') {
    Die '远端没有返回 RESULT=ok / RESULT=no-change，视为失败'
}
$release = ''
if ($remoteText -match 'RELEASE=(\S+)') { $release = $Matches[1] }
if ($release) {
    Ok "线上版本目录：$release"
    $remoteSha = (& ssh -o BatchMode=yes $SshHost "sudo -n sha256sum '$release/index.html' | cut -d' ' -f1") -join ''
    $remoteSha = $remoteSha.Trim()
    if ($remoteSha -ne $indexSha) { Die "远端 index.html sha256 与本地不一致（远端 $($remoteSha.Substring(0,16))… / 本地 $($indexSha.Substring(0,16))…）" }
    Ok "远端 index.html sha256 与本地一致（$($remoteSha.Substring(0,16))…）"
}

# 公网复核（可选）
if ($CheckUrl) {
    Ok "公网复核：$CheckUrl"
    $curlOut = & curl.exe -s -o NUL --max-time 60 -w '%{http_code} %{size_download}' $CheckUrl
    $curlText = ($curlOut | Out-String).Trim()
    Write-Host "    $CheckUrl -> $curlText"
    $parts = $curlText -split '\s+'
    if ($parts[0] -ne '200') { Die "公网复核失败：HTTP $($parts[0])" }
    if ([int64]$parts[1] -ne $indexLen) { Die "公网复核字节数不一致：远端 $($parts[1]) / 本地 $indexLen" }
    Ok "公网 200 且字节数与本地一致（$indexLen B）"
} else {
    Warn '未给 -CheckUrl，跳过了公网复核（远端回环自检已在接收脚本里做过）'
}

if (-not $KeepRemoteTarball) {
    & ssh -o BatchMode=yes $SshHost "rm -f $RemoteTar" | Out-Null
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host ' 发布完成（srv2 已原子切换）' -ForegroundColor Green
Write-Host " 线上版本：$release" -ForegroundColor Green
Write-Host " index.html：$indexLen B（sha256 $($indexSha.Substring(0,16))…）" -ForegroundColor Green
Write-Host " 入口：https://xiaokeqing.cn/（切域名前可用 Host 头/回环或 staging 域名验证）" -ForegroundColor DarkGray
Write-Host '========================================' -ForegroundColor Green

if ($WorktreeAdded) {
    Write-Host "`n[清理] 移除临时 worktree：$WorkDir" -ForegroundColor Cyan
    & git -C $BlogDir worktree remove --force $WorkDir
    & git -C $BlogDir worktree prune
    Ok '已清理临时 worktree'
}

exit 0
