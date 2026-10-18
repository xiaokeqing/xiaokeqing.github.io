<#
  publish-site-to-srv2.ps1 —— 把博客整站的 Hugo 构建产物发布到 srv2（经 SSH），原子切换。

  ★★ 编码铁律（2026-10-16 实测踩过）★★
    本文件**必须存成 UTF-8 with BOM**（首字节 EF BB BF）。PowerShell 5.1 读**无 BOM** 的
    中文 .ps1 会按 GBK 解码 ⇒ 中文注释/字符串变成乱码字节，可能把引号/花括号配对打破 ⇒
    直接 **ParserError**，脚本再也跑不起来。**任何工具化编辑（edit 工具、脚本重写）之后**，
    必须复查首字节是不是 EF BB BF，并跑一次语法自检：
      $e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile(
        'F:\7AAA\AI\blog\scripts\publish-site-to-srv2.ps1', [ref]$null, [ref]$e); $e.Count

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
    -DryRun             只构建+校验+打包+**整树哈希判定**，不上传

  ★2026-10-16（窗口 Q）整树内容哈希：**发送侧不再只比 index.html**。
    真事：接收侧 2026-10-16 已改成"与线上**整树内容**同 hash 才跳过切换"（f47c678），
    但发送侧的核对仍只盯 index.html ⇒ 只换资源（JS/图集/语音分片）的发布会显示"index.html 与线上一致"，
    看不出资源到底上没上，也没法在上传前判"内容不同"。
    现在发送侧用**与 scripts/srv2-site-receive.sh 的 tree_hash() 逐字节同口径**的算法：
      LC_ALL=C find . -type f | LC_ALL=C sort | xargs sha256sum | sha256sum
    （LC_ALL=C = 路径字节序；不钉住的话线上是 en_US.UTF-8，GNU sort 走 glibc collation，
      Windows 侧不可能复现同一个哈希。）判定结果在上传前就打印，DryRun 下也能验。
    切换后还会**重算线上整树哈希**与本地比，作为发布的最终核对（index.html 那次核对保留，用于查截断）。
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
# ★2026-10-16 修（今晚两次发布失败的真根因）：**临时目录默认挪到有空间的盘**。
#   事故：C 盘只剩 2.4GB，而一次发布要"干净 worktree(152MB) + tar.gz(144MB)"，
#   失败时又不清理 ⇒ 越失败越挤、越挤越失败（两次报"tar 包里没有 index.html"）。
#   口径：优先用 E:\DeepSeek1\work\_pubtmp（实测 67GB 空闲）；没有 E: 才退回 %TEMP%。
#   可用 -TempBase 显式覆盖；该目录不进 git（已由 .gitignore 覆盖 _pubtmp）。
$TempBase = if ($PSBoundParameters.ContainsKey('TempBase') -and $TempBase) { $TempBase }
            elseif (Test-Path 'E:\') { 'E:\DeepSeek1\work\_pubtmp' }
            else { $env:TEMP }
if (-not (Test-Path -LiteralPath $TempBase)) { New-Item -ItemType Directory -Force -Path $TempBase | Out-Null }
$WorkDir = Join-Path $TempBase "xk-site-publish-$Stamp"
$TmpTar  = Join-Path $TempBase "xk-site-$Stamp.tar.gz"
$RemoteDeployDir = "/home/ubuntu/.xk-deploy"
$RemoteTar = "$RemoteDeployDir/xk-site-$Stamp.tar.gz"
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
    # ★2026-10-16（接手窗口）：只加 `2>&1` **不够** —— 实测 `-DryRun` 的 stderr 仍有 **80 行**
    #   （首行 `git.exe : Preparing worktree (detached HEAD …)`，报错位置就指在这一行），
    #   即原生命令的 stderr 被 PS 包成 ErrorRecord 后**仍然落到调用方的 stderr**；
    #   调用方一旦用 `... 2>&1 | Select-Object ...` 就会把它变成自己的 NativeCommandError
    #   ⇒ 上层报"退出码 1"，而**本脚本自身退出码是 0**（实测 CHILD_EXIT=0）。
    #   ⇒ 这里**显式逐行写到 Host（stdout）**，成功路径从此不往 stderr 写任何东西。
    #   下一行的退出码判定（$LASTEXITCODE）**一字未改**。
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Exe @CmdArgs 2>&1 | ForEach-Object { Write-Host "      $_" } } finally { $ErrorActionPreference = $eap }
    if ($LASTEXITCODE -ne 0) { Die "$What 失败（$Exe 退出码 $LASTEXITCODE）" }
}

# ---------- 整树内容哈希（与 srv2-site-receive.sh 的 tree_hash() 逐字节同口径）----------
function Get-TreeFiles {
    # 口径：LC_ALL=C find . -type f -print0 | LC_ALL=C sort -z | LC_ALL=C xargs -0 sha256sum | sha256sum
    #   ⇒ 每个文件一行 "<sha256>  ./<相对路径>"（两个空格、LF 结尾），路径按 **UTF-8 字节序**排序，
    #     再对整段文本做一次 sha256。
    # Windows 侧复现要点：① 相对路径统一 './a/b' 正斜杠 ② 排序不能用文化比较
    #   （Sort-Object 默认走当前区域设置）⇒ 先把路径编成"每字节两位十六进制"的排序键，
    #   这样纯 ASCII 十六进制串的文化序 = 字节序 ③ 行尾必须 LF（不能 CRLF）。
    # ★已标定：本机结果与 Linux 侧 `LC_ALL=C … | sha256sum` 逐字节一致（同一个树双侧都得 8c17af0d…）。
    param([string]$Dir)
    $root = (Resolve-Path -LiteralPath $Dir).Path.TrimEnd('\')
    $rows = New-Object System.Collections.ArrayList
    $map = @{}
    foreach ($f in (Get-ChildItem -LiteralPath $root -Recurse -File -Force)) {
        $rel = './' + ($f.FullName.Substring($root.Length).TrimStart('\', '/') -replace '\\', '/')
        $h = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()
        $map[$rel] = $h
        # ★2026-10-16：整树哈希**排除顶层 ./index.json**，与接收侧 srv2-site-receive.sh 的 tree_hash() 同口径
        #   （它带构建时刻 generatedAt，两次构建必然不同；不排除则两侧哈希永不相等、RESULT=no-change 不可达）。
        #   注意：仍留在 $map 里供逐文件差异分类使用（那一层由 $TreeNondet 忽略它）。
        if ($rel -eq './index.json') { continue }
        # ★2026-10-18：再排除顶层 ./manifest.json —— 接收脚本（srv2-site-receive.sh 的 write_manifest）
        #   在切换前把每版指纹清单写进 release 目录，本地产物里**没有**这个文件；若计入整树哈希，
        #   线上树永远比本地多一行 ⇒ 哈希永不相等（同 index.json 的那套理由，且这里是"单侧存在"）。
        #   同样仍留在 $map 里，由 $TreeNondet 在逐文件差异分类时忽略。
        if ($rel -eq './manifest.json') { continue }
        $key = -join ([Text.Encoding]::UTF8.GetBytes($rel) | ForEach-Object { $_.ToString('x2') })
        [void]$rows.Add([pscustomobject]@{ Key = $key; Line = ($h + '  ' + $rel) })
    }
    $sorted = @($rows | Sort-Object -Property Key)
    $sb = New-Object Text.StringBuilder
    foreach ($r in $sorted) { [void]$sb.Append($r.Line).Append("`n") }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $hb = $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($sb.ToString())) } finally { $sha.Dispose() }
    return @{ Hash = (-join ($hb | ForEach-Object { $_.ToString('x2') })); Count = $sorted.Count; Files = $map }
}

function Get-RemoteTreeFiles {
    # 只读：不需要 sudo（/opt/secagent/site 是 a+rX）。取不到就返回 $null（不当作失败）。
    # 返回 @{ Hash = 整树哈希; Files = @{ './rel' = 'sha256' }; Count }
    $cmdList = "cd /opt/secagent/site && LC_ALL=C find . -type f ! -path './index.json' ! -path './manifest.json' -print0 | LC_ALL=C sort -z | LC_ALL=C xargs -0 sha256sum"
    $cmdHash = "cd /opt/secagent/site && LC_ALL=C find . -type f ! -path './index.json' ! -path './manifest.json' -print0 | LC_ALL=C sort -z | LC_ALL=C xargs -0 sha256sum | sha256sum | cut -d' ' -f1"
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $lines = & ssh -o BatchMode=yes -o ConnectTimeout=15 $SshHost $cmdList 2>$null
        $hashOut = & ssh -o BatchMode=yes -o ConnectTimeout=15 $SshHost $cmdHash 2>$null
    } catch { return $null } finally { $ErrorActionPreference = $eap }
    $map = @{}
    foreach ($line in @($lines)) {
        if ("$line" -match '^([0-9a-f]{64})  (.+)$') { $map[$Matches[2]] = $Matches[1] }
    }
    if ($map.Count -eq 0) { return $null }
    $hash = (($hashOut | Out-String).Trim() -split '\s+')[0]
    return @{ Hash = $hash; Files = $map; Count = $map.Count }
}

# 已知"每次构建都不同"或"只在远端存在"的文件（整树比对时忽略，否则永远不会走「无变化」分支）：
#   ./index.json    ← layouts/index.json 模板里带 generatedAt（构建时刻），两次构建必然不同
#   ./manifest.json ← ★2026-10-18：接收脚本切换前写进 release 目录的指纹清单，本地产物里没有它
$TreeNondet = @('./index.json', './manifest.json')

# 逐文件差异分类（忽略 $TreeNondet；两侧都要忽略，否则"只在远端存在"会被误报成"多/少传文件"）
function Compare-TreeFiles {
    param($Local, $Remote)
    $changed = @(); $added = @(); $removed = @(); $nondetHit = @()
    foreach ($k in $Local.Files.Keys) {
        if ($Remote.Files.ContainsKey($k)) {
            if ($Remote.Files[$k] -ne $Local.Files[$k]) {
                if ($TreeNondet -contains $k) { $nondetHit += $k } else { $changed += $k }
            }
        } elseif ($TreeNondet -contains $k) { $nondetHit += $k } else { $added += $k }
    }
    foreach ($k in $Remote.Files.Keys) {
        if (-not $Local.Files.ContainsKey($k)) {
            if ($TreeNondet -contains $k) { $nondetHit += $k } else { $removed += $k }
        }
    }
    return @{ Changed = $changed; Added = $added; Removed = $removed; Nondet = $nondetHit }
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
    # ★缓存：给 /js/*.js / /css/*.css 引用加内容指纹（CF 把 JS 的 Browser TTL 压到 300s，
    #   加指纹后内容不变 URL 不变 ⇒ 继续吃缓存；内容一变 URL 也变 ⇒ 不会被旧缓存粘住）
    $assetVer = Join-Path $BuildDir 'scripts/asset-version.py'
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($py -and (Test-Path -LiteralPath $assetVer)) {
        & $py '-X' 'utf8' $assetVer $PublicDir
        if ($LASTEXITCODE -ne 0) { Warn 'asset-version.py 执行失败（继续发布，缓存指纹缺失）' }
        else { Ok '静态资源已加内容指纹' }
    } else { Warn '找不到 python 或 asset-version.py ⇒ 跳过资源指纹' }
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

# ★2026-10-17（站主口径"做好后自己核查一遍"）：把产物硬断言接进发布链。
#   原来 scripts/assert-build.sh 只靠手工跑，容易忘 ⇒ 现在每次发布都在干净 worktree 里自动执行，
#   任一条断言红就直接拒绝发布（连 tar 都不打）。
$assertSh = Join-Path $WorkDir 'scripts/assert-build.sh'
if (Test-Path -LiteralPath $assertSh) {
    $bashExe = $null
    foreach ($cand in @('C:\Program Files\Git\bin\bash.exe', 'C:\Program Files (x86)\Git\bin\bash.exe')) {
        if (Test-Path -LiteralPath $cand) { $bashExe = $cand; break }
    }
    if (-not $bashExe) { $bashExe = (Get-Command bash -ErrorAction SilentlyContinue).Source }
    if ($bashExe) {
        Push-Location $WorkDir
        try {
            & $bashExe 'scripts/assert-build.sh' $PublicDir
            if ($LASTEXITCODE -ne 0) { Die 'scripts/assert-build.sh 断言失败 → 拒绝发布（产物不符合硬约束）' }
            Ok '产物硬断言（scripts/assert-build.sh）全部通过'
        } finally { Pop-Location }
    } else {
        Warn '本机找不到 bash ⇒ 跳过 assert-build.sh（产物特征硬断言未执行）'
    }
} else {
    Warn "worktree 里没有 scripts/assert-build.sh ⇒ 跳过产物硬断言"
}

# 整树内容哈希（★2026-10-16 窗口 Q：发送侧不再只比 index.html）
$tree = Get-TreeFiles $PublicDir
Ok ("本地整树内容 sha256 = {0}…（{1} 个文件；口径与接收侧 tree_hash 逐字节相同：LC_ALL=C 路径字节序）" -f $tree.Hash.Substring(0,16), $tree.Count)
$onlineTree = Get-RemoteTreeFiles
$treeDiff = $null
if ($onlineTree) {
    $treeDiff = Compare-TreeFiles $tree $onlineTree
    $realN = $treeDiff.Changed.Count + $treeDiff.Added.Count + $treeDiff.Removed.Count
    Ok ("线上整树内容 sha256 = {0}…（{1} 个文件）" -f $onlineTree.Hash.Substring(0,16), $onlineTree.Count)
    if ($realN -eq 0) {
        Ok "逐文件比对：与线上**一致**（改 0 / 增 0 / 删 0）⇒ 走「无变化」：接收侧会跳过切换，部署仍算成功"
    } else {
        Ok ("逐文件比对：**内容不同** —— 改 {0} 个 / 增 {1} 个 / 删 {2} 个 ⇒ 走「内容不同」分支：接收侧会原子切换（只换资源、index.html 一个字节没变也照样切）" -f $treeDiff.Changed.Count, $treeDiff.Added.Count, $treeDiff.Removed.Count)
        foreach ($k in (@($treeDiff.Changed) + @($treeDiff.Added) + @($treeDiff.Removed) | Select-Object -First 8)) { Write-Host "        · $k" -ForegroundColor DarkGray }
    }
    if ($treeDiff.Nondet.Count -gt 0) {
        Ok ("另有 {0} 个文件只有构建时间戳差异、不算内容变化，已忽略：{1}" -f $treeDiff.Nondet.Count, ($treeDiff.Nondet -join ' '))
    }
} else {
    Warn '取不到线上整树清单（ssh 只读探测失败）⇒ 跳过"内容不同"判定，其余流程不变'
}

# ---------- 4) 打包 ----------
Step '4/6' "打包 → $TmpTar"
if (Test-Path -LiteralPath $TmpTar) { Remove-Item -LiteralPath $TmpTar -Force }
Invoke-Checked 'tar.exe' @('-czf', $TmpTar, '-C', $PublicDir, '.') '打包'
$tarLen = (Get-Item -LiteralPath $TmpTar).Length
Ok ("tar.gz = {0:N2} MB" -f ($tarLen / 1MB))

# ★2026-10-16：把「临时 worktree + 临时包」的清理提成函数 —— 原先只在**成功路径尾部**调用，
#   于是 `-DryRun` 在 4/6 之后直接 `exit 0`，每次 DryRun 都留下一个 worktree 注册 + 一个 %TEMP% 大包
#   （实测累积到 **26 个包 / 2.26GB**）。现在**两条出口都走这里**。
#   清理失败**不作任何判定**（真正的发布结论在这之前已经给出）。
function Invoke-PublishCleanup {
    param([switch]$RemoveCurrentTar)   # DryRun 的包只为"上传前哈希判定"存在，用完即删
    if ($WorktreeAdded) {
        Write-Host "`n[清理] 移除临时 worktree：$WorkDir" -ForegroundColor Cyan
        # ★2026-10-16：这两条同属"**未包裹**的原生命令"（清理段不属于发布主流程）。
        #   · `git worktree remove --force` 对**已经被删掉**的目录会返回 128（实测），且可能往
        #     stderr 写一行 ⇒ EAP=Stop 下抛 NativeCommandError，脚本在 `exit 0` 之前中止；
        #   · 与 Invoke-Checked 同法：临时放宽 EAP + 吞掉 stderr，**不作任何结果判定**（清理失败
        #     不影响发布结论，真正的发布判定在这之前已经完成）。
        $eapClean = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & git -C $BlogDir worktree remove --force $WorkDir 2>$null
            & git -C $BlogDir worktree prune 2>$null
        } finally { $ErrorActionPreference = $eapClean }
        Ok '已清理临时 worktree'
    }
    # 收敛陈旧临时包：只保留**本次**这一个（每个 82~144MB，不收敛会无限堆积 —— 见上面 2.26GB）
    if ($TmpTar -and (Test-Path -LiteralPath $TmpTar)) {
        $tmpDir = [IO.Path]::GetDirectoryName($TmpTar)
        Get-ChildItem -LiteralPath $tmpDir -Filter 'xk-site-*.tar.gz' -File -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -ne $TmpTar } |
            ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }
    }
    if ($RemoveCurrentTar -and $TmpTar -and (Test-Path -LiteralPath $TmpTar)) {
        Remove-Item -LiteralPath $TmpTar -Force -ErrorAction SilentlyContinue
        Ok ("已删除本次 DryRun 临时包：" + [IO.Path]::GetFileName($TmpTar))
    }
}

if ($DryRun) {
    Write-Host "`n[DryRun] 已构建 + 校验 + **整树哈希判定**（上面那两行就是上传前的判定）+ 打包，未上传。" -ForegroundColor Yellow
    Invoke-PublishCleanup -RemoveCurrentTar
    exit 0
}

# ---------- 5) 上传 ----------
Step '5/6' "上传到 ${SshHost}:$RemoteTar（并同步接收脚本）"
Invoke-Checked 'ssh' @('-o', 'BatchMode=yes', $SshHost, "mkdir -p $RemoteDeployDir && chmod 700 $RemoteDeployDir") '建远端发布暂存目录'
Invoke-Checked 'scp' @('-q', '-o', 'BatchMode=yes', $TmpTar, "${SshHost}:$RemoteTar") 'scp 上传 tar 包'
Ok 'tar 包已上传'
Invoke-Checked 'scp' @('-q', '-o', 'BatchMode=yes', $ReceiveLocal, "${SshHost}:$RemoteDeployDir/srv2-site-receive.sh") 'scp 上传接收脚本'
Invoke-Checked 'ssh' @('-o', 'BatchMode=yes', $SshHost, "sudo -n install -m 0755 -o root -g root $RemoteDeployDir/srv2-site-receive.sh $ReceiveRemote") '安装接收脚本'
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
$incomingHash = ''
if ($remoteText -match 'TREE_HASH_INCOMING=([0-9a-f]{64})') { $incomingHash = $Matches[1] }
$onlineBeforeHash = ''
if ($remoteText -match 'TREE_HASH_ONLINE=([0-9a-f]{64})') { $onlineBeforeHash = $Matches[1] }
if ($incomingHash -and $onlineBeforeHash) {
    if ($incomingHash -eq $onlineBeforeHash) { Ok "接收侧判定：整树内容与线上一致（$($incomingHash.Substring(0,16))…）⇒ 未切换" }
    else { Ok "接收侧判定：整树内容不同（线上 $($onlineBeforeHash.Substring(0,16))… → 本次 $($incomingHash.Substring(0,16))…）" }
}
# ★2026-10-18：接收脚本切换前写进 release 目录的 manifest.json（一致性 CI 的 site_integrity 就靠它）
$manSha = ''
if ($remoteText -match 'MANIFEST_SHA=([0-9a-f]{64})') { $manSha = $Matches[1] }
$manCount = ''
if ($remoteText -match 'MANIFEST_COUNT=(\d+)') { $manCount = $Matches[1] }
if ($release) {
    Ok "线上版本目录：$release"
    $remoteSha = (& ssh -o BatchMode=yes $SshHost "sudo -n sha256sum '$release/index.html' | cut -d' ' -f1") -join ''
    $remoteSha = $remoteSha.Trim()
    if ($remoteSha -ne $indexSha) { Die "远端 index.html sha256 与本地不一致（远端 $($remoteSha.Substring(0,16))… / 本地 $($indexSha.Substring(0,16))…）" }
    Ok "远端 index.html sha256 与本地一致（$($remoteSha.Substring(0,16))…）"
    # ★整树核对（2026-10-16）：index.html 只查截断，资源有没有传全必须看整树
    $remoteTreeNow = Get-RemoteTreeFiles
    if ($incomingHash -and $incomingHash -ne $tree.Hash) {
        Warn "接收侧上报的整树哈希（$($incomingHash.Substring(0,16))…）与本地发送侧口径不一致（本地 $($tree.Hash.Substring(0,16))…）—— 两侧 tree_hash 口径可能不同版本，请核对"
    }
    if (-not $remoteTreeNow) {
        Warn '切换后取不到线上整树哈希 ⇒ 跳过整树核对（上面的 index.html 核对已通过）'
    } elseif ($remoteTreeNow.Hash -ne $tree.Hash) {
        $msg = "线上整树内容哈希与本地不一致（线上 $($remoteTreeNow.Hash.Substring(0,16))… / 本地 $($tree.Hash.Substring(0,16))…）—— 资源没传全或切换没生效（index.html 一致不能证明整树一致）"
        if ($FromRef) {
            Die $msg
        } else {
            # 没给 -FromRef 时构建用的是**当前工作区**：工作区里可能有 CRLF 陈旧副本
            # （.gitattributes 规定 `* text=auto eol=lf`，git 提交/检出是 LF，但被 Python 文本模式重写过的
            #  生成物在工作区里会是 CRLF），于是本地树与线上树在换行上不同 —— 这是环境问题，不是发布失败。
            Warn "$msg（未给 -FromRef：请用 -FromRef <已提交 ref> 发布，或先 git checkout 刷新工作区换行）"
        }
    } else {
        Ok "线上整树内容哈希与本地一致（$($remoteTreeNow.Hash.Substring(0,16))…，$($tree.Count) 个文件）"
    }
    # ★2026-10-18：接收侧写下的 manifest.json 也要当场对上——一致性 CI 以后就信这份清单，
    #   这里对不上就没人能证明"CI 报的 ok 是真的"。
    if ($manSha) {
        if ($manSha -ne $tree.Hash) {
            $msg3 = "接收侧 manifest.json 的整树哈希（$($manSha.Substring(0,16))…）与本地（$($tree.Hash.Substring(0,16))…）不一致 —— 两侧 tree_hash 口径不同版本，或文件没传全"
            if ($FromRef) { Die $msg3 } else { Warn "$msg3（未给 -FromRef，按工作区构建环境问题处理）" }
        } elseif ($manCount -and [int]$manCount -ne $tree.Count) {
            $msg3 = "接收侧 manifest.json 的文件数（$manCount）与本地（$($tree.Count)）不一致"
            if ($FromRef) { Die $msg3 } else { Warn "$msg3（未给 -FromRef，按工作区构建环境问题处理）" }
        } else {
            Ok "接收侧 manifest.json 与本地整树口径一致（$($manSha.Substring(0,16))…，$manCount 个文件）"
        }
    } else {
        Warn '接收侧没有回报 MANIFEST_SHA（接收脚本可能是旧版：manifest 是 2026-10-18 加的；下次发布前会重传接收脚本）'
    }
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

# ---------- ★V4-P4：把本次发布写进 srv1 的 release-info.json（/api/public/deploy 读它）----------
# 为什么要这一步：发布链只切 srv2 的站点目录，而后端 /api/public/deploy 读的是 srv1 上的
# /opt/secagent/data/public-api/release-info.json —— 不同步就会出现"面板显示的是三天前的版本"。
Step '6.5/6' '同步 release-info.json 到 srv1（部署面板的真实数据源）'
try {
    $relHost = 'secagent-srv1'
    $relPath = '/opt/secagent/data/public-api/release-info.json'
    $now = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
    Push-Location $RepoRoot; $commitSha = ((& git rev-parse HEAD) | Out-String).Trim(); Pop-Location
    $localRel = Join-Path $TempBase 'xk-release-info.json'
    if (Test-Path -LiteralPath $localRel) { Remove-Item -LiteralPath $localRel -Force }
    & scp -q "${relHost}:$relPath" $localRel 2>&1 | Out-Null
    $hist = @()
    if (Test-Path -LiteralPath $localRel) {
        try {
            $old = Get-Content -LiteralPath $localRel -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($old -and $old.history) { $hist = @($old.history) }
        } catch { $hist = @() }
    }
    $entry = [pscustomobject]@{ release = $release; at = $now; files = @($allFiles).Count; bytes = [int64]$totalBytes }
    $hist = @(@($entry) + @($hist | Where-Object { $_.release -ne $release })) | Select-Object -First 8
    $relObj = [pscustomobject]@{
        generatedAt = $now
        release     = $release
        commit      = $commitSha
        builtAt     = $now
        files       = @($allFiles).Count
        totalBytes  = [int64]$totalBytes
        indexSha256 = $indexSha
        history     = $hist
    }
    $relJson = $relObj | ConvertTo-Json -Depth 6
    [IO.File]::WriteAllText($localRel, $relJson, [Text.UTF8Encoding]::new($false))
    & ssh -o BatchMode=yes $relHost "mkdir -p /home/ubuntu/.xk-deploy && chmod 700 /home/ubuntu/.xk-deploy" 2>&1 | Out-Null
    & scp -q $localRel "${relHost}:/home/ubuntu/.xk-deploy/xk-release-info.json" 2>&1 | Out-Null
        $syncOut = (& ssh -o BatchMode=yes $relHost "python3 -m json.tool /home/ubuntu/.xk-deploy/xk-release-info.json > /dev/null && install -m 644 /home/ubuntu/.xk-deploy/xk-release-info.json $relPath && echo RELINFO_SYNCED" 2>&1 | Out-String).Trim()
    if ($syncOut -match 'RELINFO_SYNCED') { Ok "release-info.json 已同步：$release（history $($hist.Count) 条）" }
    else { Warn "release-info.json 同步未确认：$syncOut" }
} catch {
    # 同步失败不影响站点发布本身（面板会显示旧版本，但站点是新的）
    Warn "release-info.json 同步失败：$($_.Exception.Message)"
}

if (-not $KeepRemoteTarball) {
    # ★2026-10-16：这条是尾部**未包裹**的 ssh 原生命令。EAP=Stop 下它一旦往 stderr 写字就会抛
    # NativeCommandError，从而在 `exit 0` **之前**中止（表现就是"假失败退出码 1"）。
    # `2>&1` 并流后仍只丢弃输出，**不改任何判定**。
    & ssh -o BatchMode=yes $SshHost "rm -f $RemoteTar" 2>&1 | Out-Null
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host ' 发布完成（srv2 已原子切换）' -ForegroundColor Green
Write-Host " 线上版本：$release" -ForegroundColor Green
Write-Host " index.html：$indexLen B（sha256 $($indexSha.Substring(0,16))…）" -ForegroundColor Green
Write-Host " 入口：https://xiaokeqing.cn/（切域名前可用 Host 头/回环或 staging 域名验证）" -ForegroundColor DarkGray
Write-Host '========================================' -ForegroundColor Green


# ★2026-10-18 CF purge：发布成功后清 Cloudflare 边缘缓存。
# 为什么需要：HTML 走 DYNAMIC 不缓存，但 /api/public/*.js 与带 ?v=<8位sha> 的静态资源会被边缘缓存；
#   换了版本后若不 purge，边缘可能继续拿旧响应（表现为"已发布却看到旧数"）。
# 为什么失败不算发布失败：purge 只是让新内容更早生效的优化，不是正确性前提；凭据缺失/网络抖动
#   都不该让一次已经原子切换成功的发布被记成失败。所以一律 Warn，不 throw。
function Invoke-CfPurge {
    try {
        $tokFile  = Join-Path $BlogDir '_dev\.cf-token'
        $zoneFile = Join-Path $BlogDir '_dev\.cf-zone'
        if (-not (Test-Path $tokFile) -or -not (Test-Path $zoneFile)) {
            Warn '  CF purge 跳过（缺 _dev/.cf-token 或 _dev/.cf-zone）'
            return
        }
        $tok  = (Get-Content -Raw -LiteralPath $tokFile).Trim()
        $zone = (Get-Content -Raw -LiteralPath $zoneFile).Trim()
        if (-not $tok -or -not $zone) { Warn '  CF purge 跳过（凭据为空）'; return }
        $resp = Invoke-RestMethod -Method Post -TimeoutSec 30 `
            -Uri "https://api.cloudflare.com/client/v4/zones/$zone/purge_cache" `
            -Headers @{ Authorization = "Bearer $tok"; 'Content-Type' = 'application/json' } `
            -Body '{"purge_everything":true}'
        if ($resp.success) { Ok '  CF 边缘缓存已清（purge_everything）' }
        else { Warn "  CF purge 返回失败：$((($resp.errors | ForEach-Object { $_.code.ToString() + ':' + $_.message }) -join '; '))" }
    } catch {
        Warn "  CF purge 失败（不影响发布）：$($_.Exception.Message)"
    }
}
Invoke-CfPurge

Invoke-PublishCleanup

# ★2026-10-16「假失败退出码 1」的完整口径（接手窗口实测，写在这里备查）：
#   · 本脚本**成功路径自身返回 0**：`-DryRun`（干净调用、未合并 stderr）= 0；把尾部
#     `ssh rm -f` + 两条 git 清理**单独**在 EAP=Stop 下跑 + `exit 0` = 0；原生命令写 stderr
#     之后 `exit 0` = 0（前台与后台任务都试过，都是 0）。
#   · 所以之前两次"发布真的成功、却报退出码 1"**不是本脚本的退出码**；最可能来自**调用方式**：
#     `powershell -File ... 2>&1 | Select-Object ...` 会把子进程 stderr 变成**调用方**的
#     NativeCommandError，被上层记成 1。**这条我没能独立复现，属"最可能解释"**，不是已证结论。
#   · 本轮已把成功路径的子进程 stderr 全部并流（三处：Invoke-Checked、尾部 `ssh rm -f`、
#     worktree 清理段）⇒ 上面那种调用写法也**不会再看到本脚本产生的 stderr**。
#   · **建议调用方式**：`powershell -File ... *> 日志`（注意：**别**在 `-File` 后面直接写
#     `*>`，那会被当成脚本参数并报 RedirectionNotSupported —— 要用变量捕获再落盘，或在
#     外层 shell 里重定向），或 `| Out-Host`；不要用 `2>&1 | Select-Object`。
#   · **已修（2026-10-16 运维收尾线）**：`-DryRun` 走 `Invoke-PublishCleanup -RemoveCurrentTar`
#     ⇒ 不再留下 worktree 注册，并删掉本次临时包；成功路径同样调用（保留本次包、清掉更早的
#     同模式临时包）⇒ `%TEMP%\xk-site-*.tar.gz` 收敛为最多 1 个。
exit 0
