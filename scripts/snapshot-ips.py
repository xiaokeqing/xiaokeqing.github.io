#!/usr/bin/env python3
"""从 srv2 上已抓好的 /tmp/xksnap/alerts.js 里挑出当前热点来源 IP（去重、保序、最多 12 个）。

用途：scripts/snapshot-api.ps1 会把它 scp 到 srv2 执行，再逐个抓 /api/public/ip.js?q=<ip>
      落成 static/api/public/ip/<ip>.js —— /ip/ 页优先读同源快照，别让用户等隧道。
口径：只取 /alerts 5 分钟窗口里出现过的来源地址，不做任何扩写；读不到就输出空。
"""
import json
import sys

LIMIT = 12
SRC = "/tmp/xksnap/alerts.js"


def main() -> int:
    try:
        with open(SRC, encoding="utf-8") as f:
            data = json.load(f).get("data", {})
    except Exception:
        return 0
    out = []
    for item in data.get("list", []) or []:
        ip = item.get("srcIp")
        if ip and ip not in out:
            out.append(ip)
    for ip in out[:LIMIT]:
        print(ip)
    return 0


if __name__ == "__main__":
    sys.exit(main())
