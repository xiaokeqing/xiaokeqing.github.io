# 清理"探针/发布"在临时目录留下的垃圾（防复发）
#
# 背景（2026-10-16 事故）：CDP 探针都给 Edge 一个隔离配置目录
#   --user-data-dir=%TEMP%\xk-<名字>-<随机>
# 每个 20~220MB，脚本跑完**没人清** ⇒ 一晚上 259 个 / **12.73 GB**，
# 把 C 盘挤到只剩 2.4GB，导致发布构建/打包失败（报"tar 包里没有 index.html"）。
#
# 用法：
#   pwsh -File _dev/clean-probe-temp.ps1            # 删 1 小时前的（默认，安全）
#   pwsh -File _dev/clean-probe-temp.ps1 -Hours 0   # 全删（只在确认没有探针在跑时用）
#   pwsh -File _dev/clean-probe-temp.ps1 -WhatIfOnly  # 只看不删
#
# 纪律：跑完探针/发布后**顺手跑一次**；发布脚本已把临时目录挪到 E:（见 publish-site-to-srv2.ps1 的 $TempBase）。

param(
    [int]$Hours = 1,
    [switch]$WhatIfOnly
)

$ErrorActionPreference = 'Continue'
$cutoff = (Get-Date).AddHours(-$Hours)
$bases = @($env:TEMP, 'E:\DeepSeek1\work\_pubtmp') | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

$totalBytes = 0
$totalItems = 0
$kept = 0

foreach ($base in $bases) {
    Write-Host "=== 扫描 $base ===" -ForegroundColor Cyan
    # xk-* = 探针隔离配置 / 发布临时物；只认这个前缀，别碰别人的东西
    $items = Get-ChildItem -LiteralPath $base -Force -Filter 'xk-*' -ErrorAction SilentlyContinue
    foreach ($i in $items) {
        # 目录用"最后写入时间"判断是否还在被使用；近 $Hours 小时内的一律不删
        if ($i.LastWriteTime -gt $cutoff) { $kept++; continue }
        $sz = if ($i.PSIsContainer) {
            (Get-ChildItem -LiteralPath $i.FullName -Recurse -File -Force -ErrorAction SilentlyContinue |
                Measure-Object -Property Length -Sum).Sum
        } else { $i.Length }
        if (-not $sz) { $sz = 0 }
        $totalBytes += $sz
        $totalItems++
        if ($WhatIfOnly) {
            Write-Host ("  [看] {0,9:N1} MB  {1}" -f ($sz / 1MB), $i.Name)
        } else {
            try {
                Remove-Item -LiteralPath $i.FullName -Recurse -Force -ErrorAction Stop
                Write-Host ("  [删] {0,9:N1} MB  {1}" -f ($sz / 1MB), $i.Name)
            } catch {
                Write-Host ("  [跳过/占用] {0}" -f $i.Name) -ForegroundColor Yellow
            }
        }
    }
}

if (-not $WhatIfOnly) {
    # 发布 worktree 的 git 注册也要清（目录删了但注册还在会报 stale）
    $blog = Join-Path (Split-Path -Parent $PSScriptRoot) ''
    Push-Location $PSScriptRoot
    try { & git -C (Split-Path -Parent $PSScriptRoot) worktree prune 2>$null } catch { }
    Pop-Location
}

$free = (Get-PSDrive C).Free
Write-Host ""
Write-Host ("合计 {0} 项 / {1:N2} GB；保留（{2} 小时内）{3} 项" -f $totalItems, ($totalBytes / 1GB), $Hours, $kept) -ForegroundColor Green
Write-Host ("C 盘空闲：{0:N2} GB" -f ($free / 1GB)) -ForegroundColor Green
