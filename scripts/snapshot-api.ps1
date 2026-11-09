# 从服务器侧抓 /api/public/* 快照，落进仓库 static/api/public/（与线上路径同形）
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File scripts/snapshot-api.ps1
#
# 2026-11-09：除固定端点外，再抓「当前热点 IP」的档案快照 static/api/public/ip/<ip>.js
# —— /ip/ 页优先读同源快照，读不到才回源真实接口（隧道 <1 KB/s，不能让用户干等）。
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$tmpRoot = $env:TEMP
if (-not $tmpRoot) { $tmpRoot = Join-Path $env:LOCALAPPDATA 'Temp' }
New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
$tgz = Join-Path $tmpRoot 'xksnap.tgz'
$stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')

$paths = @(
  'alerts.js', 'home.js', 'geo.js', 'metrics.js', 'stories.js', 'password.js', 'webstats.js', 'daily.js'
)

# 热点 IP 清单：由仓库里的 scripts/snapshot-ips.py 在 srv2 上跑（不在 ssh 行里塞多行 python）
$ipsPyLocal = Join-Path $PSScriptRoot 'snapshot-ips.py'
scp -q $ipsPyLocal 'secagent-srv2:/tmp/xksnap_ips.py'

# 在 srv2 上跑（srv2 → 127.0.0.1:19900 → srv1 API，这段是快的）
$remote = "set -e; mkdir -p /tmp/xksnap; cd /tmp/xksnap; rm -f *.js; rm -rf ip; " +
  (($paths | ForEach-Object { "curl -s -m 25 'http://127.0.0.1:19900/api/public/$_' -o '$_' || true;" }) -join ' ') +
  "; mkdir -p ip; python3 /tmp/xksnap_ips.py > /tmp/xksnap/ips.txt || true; " +
  "while read -r ip; do if [ -n ""$ip"" ]; then curl -s -m 20 ""http://127.0.0.1:19900/api/public/ip.js?q=$ip"" -o ""ip/$ip.js"" || true; fi; done < /tmp/xksnap/ips.txt; " +
  "tar czf /tmp/xksnap.tgz *.js ip; ls -l /tmp/xksnap.tgz"

ssh -o ConnectTimeout=20 secagent-srv2 $remote | Out-Null
scp -q secagent-srv2:/tmp/xksnap.tgz $tgz

$dest = Join-Path $repo 'static\api\public'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$tmp = Join-Path $tmpRoot ("xksnap_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
tar -xzf $tgz -C $tmp

$meta = @{ generatedAt = $stamp; source = 'srv2 -> 127.0.0.1:19900 (srv1 api)'; files = @() }

# IP 档案快照：ip/<ip>.js
$ipSrc = Join-Path $tmp 'ip'
$ipDst = Join-Path $dest 'ip'
$kept = 0
if (Test-Path $ipSrc) {
  New-Item -ItemType Directory -Force -Path $ipDst | Out-Null
  Get-ChildItem $ipSrc -Filter *.js | ForEach-Object {
    $b = [IO.File]::ReadAllBytes($_.FullName)
    if ($b.Length -lt 16) { return }
    if (-not ([Text.Encoding]::UTF8.GetString($b)).TrimStart().StartsWith('{')) { return }
    Copy-Item $_.FullName (Join-Path $ipDst $_.Name) -Force
    $kept++
  }
}
if ($kept -gt 0) { $meta.files += @{ name = 'ip/*.js'; bytes = $kept } }

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
if (Test-Path $ipDst) {
  $n = (Get-ChildItem $ipDst -Filter *.js).Count
  $sz = (Get-ChildItem $ipDst -Filter *.js | Measure-Object Length -Sum).Sum
  "  ip/ {0} 个文件 {1:N0} B" -f $n, $sz
}
