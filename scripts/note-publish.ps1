<#
  scripts/note-publish.ps1 —— 桌面「发笔记」入口（C1-A 方案，2026-10-16 站主定）

  站主要的是：**不用开命令行敲命令**。双击 → 填标题 → 自动建 md 并打开编辑器 →
  写完保存关闭 → 自动构建 + 生成待发布命令。

  它**不做**什么（故意隔离）：
    · **默认不发布线上**（只打印将执行的发布命令）。要真发加 -Publish。
    · 永不 push；只提交自己新建的那一个文件（路径限定，永不用 -a/-A）。
    · 不改 .gitignore。

  复用（不重写）：
    · scripts/new-note.ps1                 建 md（front matter 模板、slug 规范、draft 默认 true）
    · scripts/publish-site-to-srv2.ps1     发布（必须 -FromRef；有 -DryRun）

  用法（双击走 scripts\发笔记.cmd；命令行用法）：
    .\scripts\note-publish.ps1 -Title "安全运营周报 2026-W42" -Category "安全运营" -Slug weekly-2026-w42
    .\scripts\note-publish.ps1 -Publish -NoEditor -Title "..." -Slug ...      # 无人值守真发布
    .\scripts\note-publish.ps1 -NoEditor -NoBuild -NoCommit -Title "..." -Slug ...   # 只建文件（自检用）

  编辑器等待的边界（照实说）：
    · notepad（默认）关掉窗口即继续 ✓
    · VS Code 请用 -Editor code -EditorArgs --wait（`code` 自身是启动器，不加 --wait 会立刻返回）
#>
[CmdletBinding()]
param(
  [string]$Title = '',
  [string]$Category = '',
  [string]$Slug = '',
  [string]$Tags = '',
  [string]$Summary = '',
  [string]$Editor = 'notepad',
  [string[]]$EditorArgs = @(),
  [string]$BuildDir = 'public',
  [switch]$NoDraft,
  [switch]$NoEditor,
  [switch]$NoBuild,
  [switch]$NoCommit,
  [switch]$Publish,
  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repo          = Split-Path -Parent $PSScriptRoot
$postsDir      = Join-Path $repo 'content\posts'
$newNote       = Join-Path $PSScriptRoot 'new-note.ps1'
$publishScript = Join-Path $PSScriptRoot 'publish-site-to-srv2.ps1'
$logFile       = Join-Path $repo '_dev\note-publish.log'
$utf8NoBom     = New-Object System.Text.UTF8Encoding($false)

function Log([string]$msg) {
  try {
    $line = ('[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg)
    [System.IO.File]::AppendAllText($logFile, $line + "`r`n", $utf8NoBom)
  } catch { }
}
function Say([string]$msg, [string]$color = 'Gray') {
  Write-Host $msg -ForegroundColor $color
  Log $msg
}
function Die([string]$msg) {
  Say "[中止] $msg" 'Red'
  exit 1
}
function Ask([string]$prompt, [string]$default) {
  try { Add-Type -AssemblyName Microsoft.VisualBasic -ErrorAction SilentlyContinue } catch { }
  $r = [Microsoft.VisualBasic.Interaction]::InputBox($prompt, '发笔记', $default)
  return $r
}
# 与 scripts/new-note.ps1 的 slug 规范化逐字一致（否则算不中新文件名）
function NormalizeSlug([string]$s) {
  $t = ($s.Trim().ToLower() -replace '[^\w\-]', '-')
  $t = $t -replace '-+', '-'
  return $t.Trim('-')
}
function Find-Tool([string]$name, [string[]]$searchRoots) {
  $c = Get-Command $name -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  foreach ($root in $searchRoots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $f = Get-ChildItem -Path $root -Recurse -Filter "$name.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($f) { return $f.FullName }
  }
  return ''
}

Say ''
Say '==================== 发笔记（桌面入口） ====================' 'Cyan'
Say "仓库：$repo"

if (-not (Test-Path -LiteralPath $postsDir)) { Die "找不到 content\posts：$postsDir" }

# ---------- 1) 问标题 / 分类 / 短名 ----------
if ([string]::IsNullOrWhiteSpace($Title)) {
  $Title = Ask '写什么？（标题，中文可以）' ''
  if ([string]::IsNullOrWhiteSpace($Title)) { Die '没有给标题，已取消。' }
}
if ([string]::IsNullOrWhiteSpace($Category)) {
  $Category = Ask '分类？（默认：工程实践）' '工程实践'
  if ([string]::IsNullOrWhiteSpace($Category)) { $Category = '工程实践' }
}
if ([string]::IsNullOrWhiteSpace($Slug)) {
  $Slug = Ask ('文件名短名（英文更利于 URL；留空＝ note-' + (Get-Date -Format 'HHmmss') + '）') ('note-' + (Get-Date -Format 'HHmmss'))
  if ([string]::IsNullOrWhiteSpace($Slug)) { $Slug = 'note-' + (Get-Date -Format 'HHmmss') }
}

$slugNorm = NormalizeSlug $Slug
if ([string]::IsNullOrWhiteSpace($slugNorm)) { Die '短名规范化后为空，请换一个（建议用英文字母/数字）。' }

Say ("标题：{0}" -f $Title)
Say ("分类：{0}    短名：{1}" -f $Category, $slugNorm)
Log ("参数：Title=$Title; Category=$Category; Slug=$slugNorm; NoDraft=$NoDraft; NoCommit=$NoCommit; NoBuild=$NoBuild; Publish=$Publish")

# ---------- 2) 建文件（复用 new-note.ps1；不带 -Publish/-Open，提交与编辑器由本脚本掌控）----------
$noteArgs = @{ Title = $Title; Category = $Category; Slug = $slugNorm }
if (-not [string]::IsNullOrWhiteSpace($Tags))    { $noteArgs.Tags = $Tags }
if (-not [string]::IsNullOrWhiteSpace($Summary)) { $noteArgs.Summary = $Summary }
if ($NoDraft) { $noteArgs.NoDraft = $true }
if ($Force)   { $noteArgs.Force = $true }

# 文件名规则与 scripts/new-note.ps1 一致：<日期>-<规范化短名>.md
$fileName = ('{0}-{1}.md' -f (Get-Date -Format 'yyyy-MM-dd'), $slugNorm)
$target   = Join-Path $postsDir $fileName

# ★不要看 new-note.ps1 的 $LASTEXITCODE：它是 PowerShell 脚本，**成功路径不调用 exit**，
#   于是 $LASTEXITCODE 保持 null（冒烟实测踩过：文件明明建好了，却被误判成失败并中止）。
#   改成"先查同名 → 调用 → 再验文件真的存在"。
if ((Test-Path -LiteralPath $target) -and (-not $Force)) {
  Die ("同名的笔记已存在：{0}（加 -Force 覆盖，或换一个短名）" -f $fileName)
}
& $newNote @noteArgs

if (-not (Test-Path -LiteralPath $target)) {
  # 兜底：取最近 3 分钟内新建的 md（防止 slug 规范化与 new-note 有细微差异）
  $cand = Get-ChildItem -LiteralPath $postsDir -Filter *.md |
          Where-Object { $_.LastWriteTime -gt (Get-Date).AddMinutes(-3) } |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($cand) { $target = $cand.FullName; Say "[提示] 用最近新建的文件作为目标：$($cand.Name)" 'Yellow' }
  else { Die "建完文件但找不到目标：$target" }
}
Say ("文件：{0}" -f $target) 'Green'

# ---------- 3) 打开编辑器并等它关闭 ----------
if (-not $NoEditor) {
  Say ("[打开编辑器] {0} —— 写完保存并关闭窗口后会自动继续" -f $Editor) 'Cyan'
  $spArgs = @()
  if ($EditorArgs -and $EditorArgs.Count -gt 0) { $spArgs += $EditorArgs }
  $spArgs += $target
  try {
    Start-Process -FilePath $Editor -ArgumentList $spArgs -Wait
  } catch {
    Die ("打开编辑器失败：$($_.Exception.Message)（用 -NoEditor 可跳过）")
  }
} else {
  Say '[跳过编辑器] -NoEditor' 'DarkGray'
}

# ---------- 4) 草稿闸门（draft: true 的帖子发布后线上看不到）----------
$content = [System.IO.File]::ReadAllText($target, [System.Text.Encoding]::UTF8)
if ($content -match '(?m)^draft:\s*true\s*$') {
  if ($NoDraft) { } else {
    Say '这篇还是草稿（draft: true）⇒ 即使发布，线上也不会出现。' 'Yellow'
    $ans = Read-Host '改成 draft: false 吗？[Y/n]'
    if ([string]::IsNullOrWhiteSpace($ans) -or $ans -match '^(?i)y') {
      $new = [regex]::Replace($content, '(?m)^draft:\s*true\s*$', 'draft: false')
      [System.IO.File]::WriteAllText($target, $new, $utf8NoBom)
      Say '[已改] draft: false ⇒ 发布后线上可见' 'Green'
    } else {
      Say '[保持草稿] 发布后线上不会出现这篇（Hugo 默认不构建 draft）' 'Yellow'
    }
  }
} else {
  Say '[草稿检查] 已是 draft: false 或没有该字段' 'DarkGray'
}

$rel = $target.Substring($repo.Length).TrimStart('\', '/') -replace '\\', '/'

# ---------- 5) 路径限定提交（永不 push）----------
$sha = ''
if (-not $NoCommit) {
  Push-Location $repo
  try {
    & git add -- $rel
    if ($LASTEXITCODE -ne 0) { Die 'git add 失败' }
    $staged = @(& git -c core.quotepath=false diff --cached --name-only | Where-Object { $_ -and $_.Trim() -ne '' })
    if ($staged.Count -ne 1) {
      & git reset -q HEAD -- $rel | Out-Null
      Die ("暂存区不是恰好 1 个文件（项目规矩：路径限定提交），已撤销暂存。实际：{0}" -f ($staged -join ' | '))
    }
    if ($staged[0].Trim() -ne $rel) {
      Say ("[警告] 暂存路径与预期不同：{0} vs {1}（只有一个文件，继续）" -f $staged[0].Trim(), $rel) 'Yellow'
    }
    $msgFile = Join-Path $env:TEMP ('note-msg-' + [guid]::NewGuid().ToString('N') + '.txt')
    $msg = "post: $Title`r`n`r`n由桌面「发笔记」入口创建（scripts/note-publish.ps1）；仅本地提交，未 push。`r`n文件：$rel`r`n"
    [System.IO.File]::WriteAllText($msgFile, $msg, $utf8NoBom)
    & git commit -q -F $msgFile -- $rel
    $rc = $LASTEXITCODE
    Remove-Item -LiteralPath $msgFile -Force -ErrorAction SilentlyContinue
    if ($rc -ne 0) { Die 'git commit 失败' }
    $sha = (& git rev-parse HEAD).Trim()
    Say "[已本地提交] $sha（未 push）" 'Green'
  } finally { Pop-Location }
} else {
  $sha = (& git -C $repo rev-parse HEAD).Trim()
  Say "[跳过提交] -NoCommit；用当前 HEAD 当 -FromRef：$sha" 'Yellow'
}

# ---------- 6) 构建 + SSR 契约门禁（门禁不过就不给发布命令）----------
if (-not $NoBuild) {
  $hugo = Find-Tool 'hugo' @("$env:LOCALAPPDATA\Microsoft\WinGet\Packages", "$env:ProgramFiles\Hugo", "$env:LOCALAPPDATA\Programs\Hugo")
  if (-not $hugo) { Die '找不到 hugo.exe（需要 Hugo extended）' }
  $buildPath = Join-Path $repo $BuildDir
  Say "[构建] hugo --gc --minify --destination $buildPath" 'Cyan'
  Push-Location $repo
  try {
    & $hugo --gc --minify --destination $buildPath
    if ($LASTEXITCODE -ne 0) { Die "hugo 构建失败（退出码 $LASTEXITCODE）⇒ 不发布" }
  } finally { Pop-Location }

  $py = Find-Tool 'python' @('F:\Pycharm', "$env:LOCALAPPDATA\Programs\Python")
  if (-not $py) { $py = 'python' }
  $env:PYTHONIOENCODING = 'utf-8'
  Say "[门禁① SSR 契约] $py -X utf8 _dev/check-ssr-contract.py $BuildDir" 'Cyan'
  Push-Location $repo
  try {
    & $py -X utf8 '_dev/check-ssr-contract.py' $BuildDir
    if ($LASTEXITCODE -ne 0) { Die 'SSR 契约门禁未通过 ⇒ 不给出发布命令' }
  } finally { Pop-Location }
  Say '[门禁①] PASS' 'Green'
} else {
  Say '[跳过构建与门禁] -NoBuild' 'DarkGray'
}

# ---------- 7) 发布（默认只打印命令；-Publish 才真发）----------
$pubCmd = 'powershell -NoProfile -ExecutionPolicy Bypass -File "{0}" -FromRef {1}' -f $publishScript, $sha
Say ''
Say '==================== 待发布（默认不执行） ====================' 'Cyan'
Write-Host $pubCmd -ForegroundColor White
Log ("发布命令：$pubCmd")
Say '  它会：hugo 重建 → 打包整站（约 94.85MB，其中 kurisu/ 素材 87.57MB，压不动）→ scp 到 srv2 →' 'DarkGray'
Say '        整树内容哈希校验 → 原子切换（自检失败自动回滚，KEEP=4）' 'DarkGray'
Say '  必须带 -FromRef（否则会带上别人在途的提交；工作区 CRLF 陈旧副本会被判差异）' 'DarkGray'

if ($Publish) {
  Say '[发布] -Publish 已给出 ⇒ 开始真实发布' 'Yellow'
  & $publishScript -FromRef $sha
  if ($LASTEXITCODE -ne 0) { Die "发布失败（退出码 $LASTEXITCODE）——线上未变或已自动回滚，看上面的输出" }
  Say '[发布完成] 线上已切换' 'Green'
} else {
  Say ''
  Say '[未发布] 默认只到这一步。要真发：复制上面那条命令，或重跑本工具加 -Publish' 'Yellow'
}
Say ''
Say '下一步：想改内容就再运行一次；想上线上就跑上面那条发布命令。' 'DarkGray'
Say '============================================================' 'Cyan'
exit 0
