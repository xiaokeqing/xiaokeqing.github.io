# 从服务器侧抓 /api/public/* 快照，落进仓库 static/api/public/（与线上路径同形）
# 用法：pwsh -File scripts/snapshot-api.ps1
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')

$paths = @(
  'alerts.js', 'home.js', 'geo.js', 'metrics.js', 'stories.js', 'password.js', 'webstats.js'
)

# 在 srv2 上跑（srv2 → 127.0.0.1:19900 → srv1 API，这段是快的）
$remote = "set -e; mkdir -p /tmp/xksnap; cd /tmp/xksnap; rm -f *.js; " +
  (($paths | ForEach-Object { "curl -s -m 25 'http://127.0.0.1:19900/api/public/$_' -o '$_' || true;" }) -join ' ') +
  "tar czf /tmp/xksnap.tgz *.js; ls -l /tmp/xksnap.tgz"

ssh -o ConnectTimeout=20 secagent-srv2 $remote | Out-Null
scp -q secagent-srv2:/tmp/xksnap.tgz "$env:TEMP\xksnap.tgz"

$dest = Join-Path $repo 'static\api\public'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$tmp = Join-Path $env:TEMP "xksnap_$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
tar -xzf "$env:TEMP\xksnap.tgz" -C $tmp

$meta = @{ generatedAt = $stamp; source = 'srv2 -> 127.0.0.1:19900 (srv1 api)'; files = @() }
Get-ChildItem $tmp -Filter *.js | ForEach-Object {
  $bytes = [IO.File]::ReadAllBytes($_.FullName)
  if ($bytes.Length -lt 8) { return }             # 空/失败的不写
  $txt = [Text.Encoding]::UTF8.GetString($bytes)
  if (-not $txt.TrimStart().StartsWith('{')) { return }
  Copy-Item $_.FullName (Join-Path $dest $_.Name) -Force
  $meta.files += @{ name = $_.Name; bytes = $bytes.Length }
}
$meta | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $dest '_snapshot.json') -Encoding UTF8
Remove-Item -Recurse -Force $tmp

"snapshot -> $dest"
Get-ChildItem $dest | ForEach-Object { "  {0} {1:N0} B" -f $_.Name, $_.Length }
