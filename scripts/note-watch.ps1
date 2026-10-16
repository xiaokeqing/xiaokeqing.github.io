<#
  scripts/note-watch.ps1 —— 桌面「发笔记」B 版：**常驻看守 + 存了自动发**（2026-10-16）

  与 A 版（scripts/note-publish.ps1）的关系：
    · A = 双击 → 填标题 → 建 md → 打开编辑器 → 保存关闭 → 构建 → **打印**发布命令（人再复制去跑）
    · B = **常驻看守 content\posts\*.md**：你保存并关闭后，自动走完
          路径限定提交 → 构建 → 三道门禁 → 推送 → 发布站点
    · **A 完全保留可用**，B 不改 A 的任何行为；两者共用同一条发布链（publish-site-to-srv2.ps1）

  ★安全护栏（缺一不可，代码里逐条落实）
    1) 路径限定提交：只 `git add -- <该笔记>`；**永不** -a / -A / `git commit -a`；
       且提交前校验"暂存区恰好 1 个文件且等于该笔记"，否则 `git reset` 撤销并中止。
    2) 仓库脏时不许乱提：若还有**与本次无关**的未提交改动 ⇒ 只提交该笔记路径，
       并在日志里逐条列出"这些未提交改动我没动"。
    3) 门禁不过就不发：hugo 构建 → check-ssr-contract（要 5/5）→ assert-build（要 18/18）
       → check-asset-integrity（要断链 0）；任一失败 ⇒ **停手、保留笔记、写清日志、弹提示**，
       不提交后续动作、不推送、不发布。
    4) 失败可见：日志固定落 %LOCALAPPDATA%\xk-note\watcher.log，
       失败时同时写 last-failure.txt 并**弹一次**气泡提示（绝不静默失败）。
    5) 可关：`-Stop` 立刻停（写 STOP 文件并结束看守进程）；配置 `enabled:false` 也会在下个循环退出。
       **开机自启必须显式安装**（scripts\install-note-watch.ps1），本脚本绝不自己加启动项。
    6) 草稿闸门：`draft: true` 的笔记**不发布**（线上根本看不到），只记日志 + 提示，
       除非配置 `autoUndraft:true`（默认 false —— 不替站主改内容）。

  用法：
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\note-watch.ps1            # 前台跑看守
    powershell ... -File .\scripts\note-watch.ps1 -Stop                                    # 立刻停掉并禁止再发
    powershell ... -File .\scripts\note-watch.ps1 -Start                                   # 清掉 STOP（配合自启用）
    powershell ... -File .\scripts\note-watch.ps1 -Path content\posts\x.md -DryRun         # 自检：只检测+构建+门禁
    powershell ... -File .\scripts\note-watch.ps1 -Once                                    # 处理一批待处理变更后退出
  -DryRun：**不提交、不推送、不发布**（只做检测 + 构建 + 三道门禁 + 日志），自检专用。

  本文件必须 UTF-8 with BOM（PS 5.1 读无 BOM 的中文会乱码 —— 项目实测踩过两次）。
#>
[CmdletBinding()]
param(
  [switch]$Stop,
  [switch]$Start,
  [switch]$Once,
  [switch]$DryRun,
  [string]$Path = '',
  [int]$DebounceSeconds = 0,      # 0 = 用配置里的值
  [switch]$NoToast,
  [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$repo  = Split-Path -Parent $PSScriptRoot
$notes = Join-Path $repo 'content\posts'

# ---------- 固定落点 ----------
$stateDir = Join-Path $env:LOCALAPPDATA 'xk-note'
if (-not (Test-Path -LiteralPath $stateDir)) { New-Item -ItemType Directory -Force -Path $stateDir | Out-Null }
$logFile   = Join-Path $stateDir 'watcher.log'
$stopFile  = Join-Path $stateDir 'STOP'
$pidFile   = Join-Path $stateDir 'watcher.pid'
$failFile  = Join-Path $stateDir 'last-failure.txt'
$cfgPath   = Join-Path $PSScriptRoot 'note-watch.config.json'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Log([string]$msg, [string]$level = 'INFO') {
  $line = ('[{0}] {1,-5} {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $level, $msg)
  try { [System.IO.File]::AppendAllText($logFile, $line + "`r`n", $utf8NoBom) } catch { }
  if (-not $Quiet) { Write-Host $line }
}

# 失败提示：**另起进程**弹气泡，避免模态框把看守循环卡死
function Toast([string]$title, [string]$text) {
  if ($NoToast) { Log "[提示] 已按 -NoToast 跳过弹窗：$title" 'WARN'; return }
  $safeTitle = $title.Replace("'", "''")
  $safeText  = $text.Replace("'", "''")
  $code = @"
Add-Type -AssemblyName System.Windows.Forms
`$ni = New-Object System.Windows.Forms.NotifyIcon
`$ni.Icon = [System.Drawing.SystemIcons]::Warning
`$ni.BalloonTipTitle = '$safeTitle'
`$ni.BalloonTipText  = '$safeText'
`$ni.Visible = `$true
`$ni.ShowBalloonTip(15000)
Start-Sleep -Seconds 16
`$ni.Dispose()
"@
  try {
    Start-Process -FilePath 'powershell' -WindowStyle Hidden -ArgumentList @(
      '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $code) | Out-Null
  } catch { Log "[提示] 弹窗进程启动失败（不影响日志）：$($_.Exception.Message)" 'WARN' }
}

# ---------- 配置 ----------
$defaults = [ordered]@{
  enabled        = $true
  autoPublish    = $true
  autoUndraft    = $false
  push           = $true
  debounceSeconds = 4
  watchDir       = 'content\posts'
  sshKey         = 'C:/Users/T/.ssh/secagent_ed25519'
  gitRemote      = 'origin'
  gitBranch      = 'main'
  publishBacklogOnStart = $false   # 看守启动前的存量笔记默认不补发（防止一开机把历史全发一遍）
}
$cfg = @{}
foreach ($k in $defaults.Keys) { $cfg[$k] = $defaults[$k] }
if (Test-Path -LiteralPath $cfgPath) {
  try {
    $raw = [System.IO.File]::ReadAllText($cfgPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    foreach ($p in $raw.PSObject.Properties) { $cfg[$p.Name] = $p.Value }
  } catch { Log "配置解析失败，改用默认值：$($_.Exception.Message)" 'WARN' }
}
if ($DebounceSeconds -le 0) { $DebounceSeconds = [int]$cfg.debounceSeconds }
$notes = Join-Path $repo ([string]$cfg.watchDir)

# ---------- 控制开关 ----------
if ($Stop) {
  [System.IO.File]::WriteAllText($stopFile, "stopped at $(Get-Date -Format s)`r`n", $utf8NoBom)
  $killed = 0
  if (Test-Path -LiteralPath $pidFile) {
    $oldPid = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    if ($oldPid -match '^\d+$') {
      try { Stop-Process -Id ([int]$oldPid) -Force -ErrorAction Stop; $killed = 1 } catch { }
    }
  }
  Log "收到 -Stop：已写 STOP 文件、结束看守进程（killed=$killed）。再次启动用 -Start。" 'WARN'
  Write-Host "[已停止] 自动发布已关闭。重新开启：note-watch.cmd -Start" -ForegroundColor Yellow
  exit 0
}
if ($Start) {
  if (Test-Path -LiteralPath $stopFile) { Remove-Item -LiteralPath $stopFile -Force }
  Log '收到 -Start：已清除 STOP 文件。' 'INFO'
  Write-Host '[已开启] 自动发布重新生效。' -ForegroundColor Green
  # ★只做"开关"这一件事，做完就退出：**绝不能往下继续落进看守循环**。
  #   自检实测踩过：`-Start` 清完 STOP 后继续往下跑、且未带 -DryRun ⇒ 变成一个"武装"的看守
  #   （任何笔记保存都会自动提交+推送+发布）；外层管道又等它结束 ⇒ 自检直接挂死。
  exit 0
}

if (-not (Test-Path -LiteralPath $notes)) { Log "找不到笔记目录：$notes" 'ERROR'; exit 1 }
$hugo = $null
function Find-Hugo {
  if ($script:hugo) { return $script:hugo }
  $c = Get-Command hugo -ErrorAction SilentlyContinue
  if ($c) { $script:hugo = $c.Source; return $script:hugo }
  foreach ($root in @("$env:LOCALAPPDATA\Microsoft\WinGet\Packages", "$env:ProgramFiles\Hugo", "$env:LOCALAPPDATA\Programs\Hugo")) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $f = Get-ChildItem -Path $root -Recurse -Filter 'hugo.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($f) { $script:hugo = $f.FullName; return $script:hugo }
  }
  return ''
}
function Find-Py {
  $c = Get-Command python -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  foreach ($root in @('F:\Pycharm', "$env:LOCALAPPDATA\Programs\Python")) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $f = Get-ChildItem -Path $root -Recurse -Filter 'python.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($f) { return $f.FullName }
  }
  return 'python'
}
function Find-Bash {
  foreach ($p in @('C:\Program Files\Git\bin\bash.exe', 'C:\Program Files (x86)\Git\bin\bash.exe')) {
    if (Test-Path -LiteralPath $p) { return $p }
  }
  $c = Get-Command bash -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  return ''
}

function Invoke-Capture([string]$exe, [string[]]$argv, [string]$workDir, [string]$outFile) {
  # 用 Start-Process 取**真实退出码**（不要用 `2>&1 | Select-Object`，会把 stderr 记成失败）
  $sp = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory $workDir -Wait -PassThru `
        -RedirectStandardOutput $outFile -RedirectStandardError "$outFile.err" -NoNewWindow
  return $sp.ExitCode
}

function Get-Rel([string]$full) {
  return ($full.Substring($repo.Length).TrimStart('\', '/') -replace '\\', '/')
}

function Test-FileClosed([string]$full) {
  # 编辑器还占着文件时视为"没写完"，继续等；能独占打开才认为用户已保存关闭
  try {
    $fs = [System.IO.File]::Open($full, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $fs.Close(); $fs.Dispose()
    return $true
  } catch { return $false }
}

# ---------- 单文件流水线 ----------
function Publish-One([string]$full) {
  $rel  = Get-Rel $full
  $name = Split-Path -Leaf $full
  $t0   = Get-Date
  Log "──── 检测到笔记变更：$rel（DryRun=$DryRun）"

  # 0) 草稿闸门
  $text = [System.IO.File]::ReadAllText($full, [System.Text.Encoding]::UTF8)
  if ($text -match '(?m)^draft:\s*true\s*$') {
    if ($cfg.autoUndraft) {
      $new = [regex]::Replace($text, '(?m)^draft:\s*true\s*$', 'draft: false')
      if (-not $DryRun) { [System.IO.File]::WriteAllText($full, $new, $utf8NoBom) }
      Log '[草稿] autoUndraft=true ⇒ 已把 draft 改成 false（DryRun 时不写盘）' 'WARN'
    } else {
      Log '[跳过] draft: true —— 线上一律看不到，故不发布。想发就把它改成 draft: false（或配置 autoUndraft:true）' 'WARN'
      Toast '发笔记：这篇还是草稿' "《$name》是 draft: true，线上看不到，所以没有发布。"
      return
    }
  }

  # 1) 路径限定提交
  $sha = ''
  if ($DryRun) {
    $sha = (& git -C $repo rev-parse HEAD).Trim()
    Log "[DryRun] 跳过提交；用当前 HEAD 当 -FromRef：$sha" 'INFO'
  } else {
    $commitErr = ''
    Push-Location $repo
    try {
      # 先记录**与本笔记无关**的未提交改动（只报告，绝不动它们）
      $others = @(& git -c core.quotepath=false status --porcelain | Where-Object { $_ -and $_.Trim() -ne '' -and ($_ -notmatch [regex]::Escape($rel)) })
      if ($others.Count -gt 0) {
        Log "仓库里还有 $($others.Count) 处与本笔记无关的未提交改动 —— **我没有动它们**：" 'WARN'
        foreach ($o in $others) { Log "   · $o" 'WARN' }
      }
      & git add -- $rel
      if ($LASTEXITCODE -ne 0) { throw 'git add 失败' }
      $staged = @(& git -c core.quotepath=false diff --cached --name-only | Where-Object { $_ -and $_.Trim() -ne '' })
      if ($staged.Count -ne 1 -or $staged[0].Trim() -ne $rel) {
        & git reset -q HEAD -- $rel | Out-Null
        throw ("暂存区不是恰好这一个文件（路径限定提交规矩），已撤销暂存。实际：{0}" -f ($staged -join ' | '))
      }
      $msgFile = Join-Path $stateDir ('msg-' + [guid]::NewGuid().ToString('N') + '.txt')
      $msg = "post: $name`r`n`r`n由桌面看守（scripts/note-watch.ps1，B 版）自动提交；仅这一个文件。`r`n文件：$rel`r`n"
      [System.IO.File]::WriteAllText($msgFile, $msg, $utf8NoBom)
      & git commit -q -F $msgFile -- $rel
      $rc = $LASTEXITCODE
      Remove-Item -LiteralPath $msgFile -Force -ErrorAction SilentlyContinue
      if ($rc -ne 0) { throw 'git commit 失败' }
      $sha = (& git rev-parse HEAD).Trim()
      Log "[已提交] $sha（路径限定：$rel）"
    } catch {
      $commitErr = $_.Exception.Message
    } finally {
      Pop-Location
    }
    if ($commitErr) {
      Log "提交阶段失败：$commitErr" 'ERROR'
      [System.IO.File]::WriteAllText($failFile, "阶段=提交`r`n文件=$rel`r`n原因=$commitErr`r`n时间=$(Get-Date -Format s)`r`n", $utf8NoBom)
      Toast '发笔记：提交失败' "$name 没有发布。原因见日志：$logFile"
      return
    }
  }

  # 2) 构建
  $hugoExe = Find-Hugo
  if (-not $hugoExe) { Log '找不到 hugo.exe' 'ERROR'; Toast '发笔记：找不到 Hugo' '没发布。装好 Hugo extended 再试。'; return }
  $buildOut = Join-Path $stateDir 'build.log'
  Log "[构建] hugo --gc --minify --destination public"
  $rc = Invoke-Capture $hugoExe @('--gc', '--minify', '--destination', 'public') $repo $buildOut
  if ($rc -ne 0) {
    Log "hugo 构建失败（退出码 $rc），日志：$buildOut" 'ERROR'
    [System.IO.File]::WriteAllText($failFile, "阶段=构建`r`n文件=$rel`r`n退出码=$rc`r`n时间=$(Get-Date -Format s)`r`n", $utf8NoBom)
    Toast '发笔记：构建失败' "$name 没有发布（Hugo 退出码 $rc）。日志：$logFile"
    return
  }
  Log '[构建] 通过'

  # 3) 三道门禁（不过就不发）
  $py   = Find-Py
  $bash = Find-Bash
  $env:PYTHONIOENCODING = 'utf-8'
  $gate1 = Join-Path $stateDir 'gate-ssr.log'
  $rc = Invoke-Capture $py @('-X', 'utf8', '_dev/check-ssr-contract.py', 'public') $repo $gate1
  $g1txt = ''
  try { $g1txt = [System.IO.File]::ReadAllText($gate1, [System.Text.Encoding]::UTF8) } catch { }
  # 该脚本的真实输出 = 5 行 `... PASS` + `结论：全部通过（0 项不合格）`
  # （**不含 "5/5" 字样** —— 自检时按"5/5"判定过，结果把通过的门禁误判成失败，已改正）
  $passRows = ([regex]::Matches($g1txt, 'PASS')).Count
  $ok1 = ($rc -eq 0) -and ($g1txt -match '全部通过') -and ($passRows -ge 5) -and ($g1txt -notmatch '[1-9][0-9]* 项不合格')
  if (-not $ok1) {
    Log "门禁① SSR 契约未通过（退出码 $rc；PASS 行 $passRows，要求 ≥5 且 0 项不合格）。日志：$gate1" 'ERROR'
    [System.IO.File]::WriteAllText($failFile, "阶段=门禁①SSR`r`n文件=$rel`r`n退出码=$rc`r`nPASS行=$passRows`r`n时间=$(Get-Date -Format s)`r`n", $utf8NoBom)
    Toast '发笔记：门禁①未过' "$name 没有发布（静态路由契约未全过）。"
    return
  }
  Log "[门禁①] SSR 契约通过（$passRows 页 PASS、0 项不合格）"

  if (-not $bash) { Log '找不到 bash.exe（Git for Windows），门禁② 无法执行 ⇒ 按"门禁不过就不发"处理' 'ERROR'; Toast '发笔记：缺少 bash' "$name 没有发布（跑不了门禁②）。"; return }
  $gate2 = Join-Path $stateDir 'gate-build.log'
  $rc = Invoke-Capture $bash @('scripts/assert-build.sh', 'public') $repo $gate2
  $g2txt = ''
  try { $g2txt = [System.IO.File]::ReadAllText($gate2, [System.Text.Encoding]::UTF8) } catch { }
  $ok2 = ($rc -eq 0) -and ($g2txt -match '通过 18 项') -and ($g2txt -notmatch '失败 [1-9]')
  if (-not $ok2) {
    Log "门禁② 构建断言未通过（退出码 $rc，要求 通过 18 项 / 失败 0 项）。日志：$gate2" 'ERROR'
    [System.IO.File]::WriteAllText($failFile, "阶段=门禁②构建断言`r`n文件=$rel`r`n退出码=$rc`r`n时间=$(Get-Date -Format s)`r`n", $utf8NoBom)
    Toast '发笔记：门禁②未过' "$name 没有发布（构建断言未到 18/18）。"
    return
  }
  Log '[门禁②] 构建断言通过（18 项 / 失败 0）'

  $gate3 = Join-Path $stateDir 'gate-assets.log'
  $rc = Invoke-Capture $py @('-X', 'utf8', '_dev/check-asset-integrity.py') $repo $gate3
  $g3txt = ''
  try { $g3txt = [System.IO.File]::ReadAllText($gate3, [System.Text.Encoding]::UTF8) } catch { }
  $ok3 = ($rc -eq 0) -and ($g3txt -match '\[PASS\]') -and ($g3txt -notmatch '\[FAIL\]')
  if (-not $ok3) {
    Log "门禁③ 资产完整性未通过（退出码 $rc，要求 [PASS] 且无 [FAIL]）。日志：$gate3" 'ERROR'
    [System.IO.File]::WriteAllText($failFile, "阶段=门禁③资产完整性`r`n文件=$rel`r`n退出码=$rc`r`n时间=$(Get-Date -Format s)`r`n", $utf8NoBom)
    Toast '发笔记：门禁③未过' "$name 没有发布（资产完整性未过）。"
    return
  }
  Log '[门禁③] 资产完整性通过（[PASS]、无 [FAIL]）'

  if (-not $cfg.autoPublish) { Log '[停止] autoPublish=false ⇒ 门禁已过，但不推送不发布（改配置即可开启）。' 'WARN'; return }
  if ($DryRun) {
    Log "[DryRun] 到此为止：**没有推送、没有发布**。真实流程会执行：git push $($cfg.gitRemote) HEAD:$($cfg.gitBranch) → publish-site-to-srv2.ps1 -FromRef $sha" 'WARN'
    Log ("──── 完成（DryRun）耗时 {0:N1}s" -f ((Get-Date) - $t0).TotalSeconds)
    return
  }

  # 4) 推送
  if ($cfg.push) {
    $pushOut = Join-Path $stateDir 'push.log'
    $env:GIT_SSH_COMMAND = ('ssh -i {0} -o IdentitiesOnly=yes -o BatchMode=yes' -f $cfg.sshKey)
    $rc = Invoke-Capture 'git' @('-C', $repo, 'push', [string]$cfg.gitRemote, ('HEAD:{0}' -f $cfg.gitBranch)) $repo $pushOut
    Remove-Item Env:\GIT_SSH_COMMAND -ErrorAction SilentlyContinue
    if ($rc -ne 0) {
      Log "推送失败（退出码 $rc），日志：$pushOut ⇒ 不发布（线上保持上一版）" 'ERROR'
      [System.IO.File]::WriteAllText($failFile, "阶段=推送`r`n文件=$rel`r`n退出码=$rc`r`n时间=$(Get-Date -Format s)`r`n", $utf8NoBom)
      Toast '发笔记：推送失败' "$name 已本地提交（$sha），但推送失败 ⇒ 没有发布。"
      return
    }
    Log "[已推送] $($cfg.gitRemote)/$($cfg.gitBranch) ← $sha"
  } else {
    Log '[跳过推送] 配置 push=false' 'WARN'
  }

  # 5) 发布站点
  $pub = Join-Path $PSScriptRoot 'publish-site-to-srv2.ps1'
  $pubOut = Join-Path $stateDir ('publish-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
  Log "[发布] publish-site-to-srv2.ps1 -FromRef $sha（日志 $pubOut）"
  $rc = Invoke-Capture 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $pub, '-FromRef', $sha) $repo $pubOut
  $ptxt = ''
  try { $ptxt = [System.IO.File]::ReadAllText($pubOut, [System.Text.Encoding]::UTF8) } catch { }
  $ok = ($rc -eq 0) -and ($ptxt -match 'RESULT=ok' -or $ptxt -match '发布完成')
  if (-not $ok) {
    Log "发布未成功（退出码 $rc；日志 $pubOut）⇒ 线上未变或已自动回滚" 'ERROR'
    [System.IO.File]::WriteAllText($failFile, "阶段=发布`r`n文件=$rel`r`n退出码=$rc`r`n日志=$pubOut`r`n时间=$(Get-Date -Format s)`r`n", $utf8NoBom)
    Toast '发笔记：发布失败' "$name 已提交并推送，但发布未成功（线上未变或已回滚）。"
    return
  }
  $rel2 = ''
  $m = [regex]::Match($ptxt, 'RELEASE=(\S+)')
  if ($m.Success) { $rel2 = $m.Groups[1].Value }
  if (Test-Path -LiteralPath $failFile) { Remove-Item -LiteralPath $failFile -Force -ErrorAction SilentlyContinue }
  Log "[发布完成] 线上已切换：$rel2 ；笔记 $rel ；耗时 $([math]::Round(((Get-Date) - $t0).TotalSeconds,1))s"
}

# ---------- 自检入口：只处理指定文件一次 ----------
if (-not [string]::IsNullOrWhiteSpace($Path)) {
  $full = $Path
  if (-not [System.IO.Path]::IsPathRooted($full)) { $full = Join-Path $repo $Path }
  if (-not (Test-Path -LiteralPath $full)) { Log "指定的文件不存在：$full" 'ERROR'; exit 1 }
  Publish-One ([System.IO.Path]::GetFullPath($full))
  exit 0
}

# ---------- 单实例 ----------
$mutex = New-Object System.Threading.Mutex($false, 'Local\xk-note-watch')
if (-not $mutex.WaitOne(0)) { Log '已有一个看守在跑（单实例），本次退出。' 'WARN'; exit 0 }
[System.IO.File]::WriteAllText($pidFile, "$PID`r`n", $utf8NoBom)

$startMsg = "看守启动：目录=$notes ；debounce=${DebounceSeconds}s ；autoPublish=$($cfg.autoPublish) ；push=$($cfg.push) ；DryRun=$DryRun"
Log ('=' * 72)
Log $startMsg
if (-not $DryRun -and $cfg.autoPublish) {
  Log '★★ 武装状态：content\posts 里任何一次"保存并关闭"都会被自动走完 提交→构建→门禁→推送→发布线上。要停：note-watch.cmd -Stop（或桌面「关掉自动发布」）' 'WARN'
}
if (Test-Path -LiteralPath $stopFile) {
  Log '发现 STOP 文件 ⇒ 看守不会处理任何变更（用 -Start 清除）。' 'WARN'
}

# 监视方式：**轮询扫描**（不用 FileSystemWatcher + Register-ObjectEvent -Action ——
#   那种写法在 PS 5.1 里依赖事件队列泵，长时间 Start-Sleep 时不可靠、也无法稳定自证）。
# 判据三重：① LastWriteTime 变化过 ② 静置 ≥ debounce 秒（你还在打字时不打断）
#           ③ 能独占打开（编辑器已释放 ⇒ 你确实保存并关掉了）
$known  = @{}     # full path -> LastWriteTimeUtc.Ticks（已登记）
$cand   = @{}     # full path -> 候选（等静置与释放）
$publishBacklog = $false
if ($cfg.ContainsKey('publishBacklogOnStart')) { $publishBacklog = [bool]$cfg.publishBacklogOnStart }
foreach ($f in @(Get-ChildItem -LiteralPath $notes -Filter *.md -ErrorAction SilentlyContinue)) {
  $known[$f.FullName] = $f.LastWriteTimeUtc.Ticks
}
Log ("已登记现有笔记 {0} 篇（启动前的存量默认**不补发**；要补发把配置 publishBacklogOnStart 设为 true）" -f $known.Count)
Log "开始轮询监视（每 2 秒一扫）：$notes"

try {
  while ($true) {
    Start-Sleep -Seconds 2
    if (-not $cfg.enabled) { Log '配置 enabled=false ⇒ 退出看守。' 'WARN'; break }
    if (Test-Path -LiteralPath $stopFile) { Log '发现 STOP 文件 ⇒ 停止处理（看守退出）。' 'WARN'; break }

    foreach ($f in @(Get-ChildItem -LiteralPath $notes -Filter *.md -ErrorAction SilentlyContinue)) {
      $p = $f.FullName
      $ticks = $f.LastWriteTimeUtc.Ticks
      $prev = -1
      if ($known.ContainsKey($p)) { $prev = $known[$p] }
      if ($ticks -ne $prev) {
        $known[$p] = $ticks
        if ($prev -lt 0 -and -not $publishBacklog) {
          Log "新出现但按配置不补发（publishBacklogOnStart=false）：$(Split-Path -Leaf $p)" 'WARN'
          continue
        }
        $cand[$p] = Get-Date
        Log "发现变更（进入候选，等 ${DebounceSeconds}s 静置）：$(Split-Path -Leaf $p)"
      }
    }

    foreach ($p in @($cand.Keys)) {
      if (-not (Test-Path -LiteralPath $p)) { $cand.Remove($p); continue }
      # ★静置计时必须以"**首次看到这次变化**的时刻"为基准。
      #   自检实测踩过：原先用 [datetime]::FromFileTimeUtc($known[$p]) 去解释 DateTime.Ticks
      #   （两个"ticks"纪元不同：FileTime 从 1601 起、DateTime 从 0001 起）⇒ 年龄被算成负数
      #   ⇒ 候选永远不熟、流水线一次都不跑（只记"发现变更"）。
      $age = ((Get-Date) - $cand[$p]).TotalSeconds
      if ($age -lt $DebounceSeconds) { continue }
      if (-not (Test-FileClosed $p)) { continue }   # 编辑器还占着 ⇒ 等你关
      $cand.Remove($p)
      Publish-One $p
      if ($Once) { break }
    }
    if ($Once) { break }
  }
} finally {
  if ($mutex) { try { $mutex.ReleaseMutex() } catch { }; $mutex.Dispose() }
  Log '看守已退出。'
}
exit 0
