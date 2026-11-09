#!/usr/bin/env python3
"""为 /ip/ 页面生成「热点 IP 档案」静态快照。

背景
----
`/ip/` 查任意 IP 需要调用真实接口 `/api/public/ip.js?q=<ip>`。该接口经 Cloudflare
隧道转发，实测对「大于约 1 KB 的响应」吞吐会掉到 600 B/s 量级，浏览器里经常超时，
页面只能显示「读不到」。而 Vercel 上的静态资源是快的（36 KB 的 home.js 约 0.9 s）。

做法
----
在 **srv1**（API 所在机器，`http://127.0.0.1:9900` 直连，不受隧道影响）上：
1. 读 `alerts.js?w=60` 的聚合列表，按出现次数取前 N 个来源 IP；
2. 逐个请求 `ip.js?q=<ip>`，把响应原样存成 `<ip>.js`；
3. 打成 tar.gz 便于 scp 回开发机。

然后把解包出的 `<ip>.js` 放进仓库 `static/api/public/ip/`，页面就会优先命中静态
快照（同源、Vercel 边缘缓存），未命中的 IP 才回退到实时接口。

用法
----
    # 在 srv1 上（或任何能直连 API 的机器）
    python3 scripts/snapshot-ip-dossiers.py
    # 本地取回
    scp secagent-srv1:/tmp/xkip.tar.gz .
    tar -xzf xkip.tar.gz -C /tmp && cp /tmp/xkip/*.js static/api/public/ip/

注意
----
- 只存「接口真实返回」，接口说读不到就存读不到的那份 JSON，不补数、不造样例。
- 文件名就是 IP 本身，页面按 `/api/public/ip/<ip>.js` 取；不要带查询串。
- 快照有生成时间（JSON 里的 `generatedAt`），页面展示时以它为准，不要伪装成实时。
"""

import argparse
import json
import os
import sys
import tarfile
import urllib.request
from collections import Counter

DEFAULT_BASE = "http://127.0.0.1:9900"
DEFAULT_OUT = "/tmp/xkip"


def http_get(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def pick_top_ips(base: str, minutes: int, limit: int, timeout: float):
    raw = http_get("%s/api/public/alerts.js?w=%d" % (base, minutes), timeout)
    doc = json.loads(raw.decode("utf-8"))
    data = doc.get("data") or {}
    items = data.get("items") or data.get("list") or []

    counter = Counter()
    for item in items:
        ip = item.get("srcIp") or item.get("src") or item.get("sourceIp") or item.get("ip")
        if not ip:
            continue
        # 聚合列表里会出现「未知」「内网/未知」这类占位值，不是 IP，跳过
        if any(ch in str(ip) for ch in "/非未知内网"):
            continue
        counter[str(ip)] += int(item.get("count") or 1)

    return [ip for ip, _ in counter.most_common(limit)]


def main(argv=None):
    ap = argparse.ArgumentParser(description="为 /ip/ 生成热点 IP 档案静态快照")
    ap.add_argument("--base", default=DEFAULT_BASE, help="API 基址（默认本机 9900）")
    ap.add_argument("--out", default=DEFAULT_OUT, help="输出目录")
    ap.add_argument("--minutes", type=int, default=60, help="取热点的时间窗口（分钟）")
    ap.add_argument("--limit", type=int, default=12, help="最多取多少个 IP")
    ap.add_argument("--timeout", type=float, default=40.0, help="单次请求超时（秒）")
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    for name in os.listdir(args.out):
        os.remove(os.path.join(args.out, name))

    ips = pick_top_ips(args.base, args.minutes, args.limit, args.timeout)
    if not ips:
        print("没有取到任何来源 IP（alerts.js 的 items 为空？）", file=sys.stderr)
        return 2

    saved = 0
    for ip in ips:
        try:
            body = http_get("%s/api/public/ip.js?q=%s" % (args.base, ip), args.timeout)
        except Exception as exc:  # 单个 IP 失败不影响其它
            print("fail %s %s %s" % (ip, type(exc).__name__, str(exc)[:60]), file=sys.stderr)
            continue
        try:
            doc = json.loads(body.decode("utf-8"))
        except Exception:
            print("skip %s 响应不是 JSON" % ip, file=sys.stderr)
            continue
        if doc.get("code") not in (0, 200, None):
            print("skip %s code=%s" % (ip, doc.get("code")), file=sys.stderr)
            continue
        path = os.path.join(args.out, "%s.js" % ip)
        with open(path, "wb") as fh:
            fh.write(body)
        saved += 1
        print("saved %s %d bytes" % (ip, len(body)))

    tar_path = args.out.rstrip("/") + ".tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for name in sorted(os.listdir(args.out)):
            tar.add(os.path.join(args.out, name), arcname=os.path.basename(args.out.rstrip("/")) + "/" + name)

    print("TAR %s %d bytes, files %d, saved %d" % (tar_path, os.path.getsize(tar_path), len(os.listdir(args.out)), saved))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
