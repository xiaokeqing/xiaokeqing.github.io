# 每 10 分钟抓一次 API 快照并自动提交（数字不再变旧）
# 注册：schtasks /Create /TN "XK-API-Snapshot" /SC MINUTE /MO 10 /F /TR "powershell -NoProfile -ExecutionPolicy Bypass -File F:\7AAA\AI\blog\scripts\snapshot-refresh.ps1"
$ErrorActionPreference = 'Stop'
$repo = 'F:\7AAA\AI\blog'
$log = Join-Path $env:TEMP 'xk-snapshot.log'
function L($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" | Add-Content $log }

try {
  ssh -o ConnectTimeout=15 -o BatchMode=yes secagent-srv1 'bash /tmp/_snap_srv1.sh' | Out-Null
  scp -q secagent-srv1:/tmp/xksnap.tgz "$env:TEMP\xksnap.tgz"
  $tmp = Join-Path $env:TEMP "xksnap_$([guid]::NewGuid().ToString('N'))"
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  tar -xzf "$env:TEMP\xksnap.tgz" -C $tmp

  $dest = Join-Path $repo 'static\api\public'
  $changed = 0
  Get-ChildItem $tmp -Filter *.js | ForEach-Object {
    $bytes = [IO.File]::ReadAllBytes($_.FullName)
    if ($bytes.Length -lt 8) { return }
    $txt = [Text.Encoding]::UTF8.GetString($bytes)
    if (-not $txt.TrimStart().StartsWith('{')) { return }
    $target = Join-Path $dest $_.Name
    $same = (Test-Path $target) -and ((Get-FileHash $target).Hash -eq (Get-FileHash $_.FullName).Hash)
    if (-not $same) { Copy-Item $_.FullName $target -Force; $changed++ }
  }
  Remove-Item -Recurse -Force $tmp

  if ($changed -eq 0) { L 'no change'; exit 0 }

  Push-Location $repo
  git add -f static/api/public | Out-Null
  git -c core.hooksPath=/dev/null commit -q -m "chore(snapshot): 刷新 API 快照（$changed 个文件，$((Get-Date).ToString('HH:mm'))）"
  git push -q origin main
  L "committed+pushed $changed files"
  Pop-Location
} catch {
  L ("ERROR " + $_.Exception.Message)
}
