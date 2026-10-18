#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""noise-index.py —— 计算「本平台观测到的互联网背景噪音强度」(NIS, 0–100)

设计书：docs/噪音指数设计-20261018.md

只读脚本：仅以只读方式打开数据源，结果只写 stdout（--json 也是一行 stdout）。
不写 eve.json 所在目录、不写任何线上路径、不发网络请求。

数据源
-------
--eve    Suricata eve.json（JSON Lines）。可传单个文件、glob（'/opt/suricata/logs/eve.json*'）
         或目录（取目录下 *.json*，自动跳过 .gz 轮转）。
--cowrie Cowrie 日志（JSON Lines）。同上，常用 '/opt/cowrie/logs/cowrie.json*'。

用法
----
    python3 scripts/noise-index.py --dry-run
    python3 scripts/noise-index.py --eve /opt/suricata/logs/eve.json \
        --cowrie '/opt/cowrie/logs/cowrie.json*' --window-hours 24
    python3 scripts/noise-index.py --since 2026-10-17T00:00:00Z \
        --until 2026-10-18T00:00:00Z --json

退出码
------
0 = 算出分（可能带 degraded 提示）
1 = 数据不可读 / 有效行数为 0（不编造分数）
2 = 参数错误
"""

import argparse
import glob
import ipaddress
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------- 常量与口径

# 诱捕端口（设计书 §2.2 记录的开着的门）
DECOY_PORTS = [21, 22, 23, 1433, 2222, 3306, 6379, 9080, 27017]

# 心跳告警指纹：Wazuh agent 每 5 分钟 POST /ca_report.cgi 到 169.254.0.4:80
# 这一条 signature 覆盖了全量 alert 的 94.9%，必须剔除并在报告里单列。
HB_SIGNATURE = "ET INFO Python-urllib/ Suspicious User Agent"
HB_SRC = "10.0.0.10"
HB_DST = "169.254.0.4"
HB_DPORT = 80

# 保留 / 内网地址：不计入「互联网噪音」
RESERVED_NETS = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24",
    "192.168.0.0/16", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24",
    "224.0.0.0/4", "240.0.0.0/4", "::1/128", "fc00::/7", "fe80::/10",
)]

# 权重（设计书 §3.2）：A 0.40 / U 0.25 / H 0.20 / P 0.15
WEIGHTS = {"A": 0.40, "U": 0.25, "H": 0.20, "P": 0.15}

# 饱和常数：x = K × 参考值 时该通道逼近 1.0
K = 10.0

# 冷启动参考值（x_ref）。跑出 30 天 p50 后用 --ref 覆盖。
REF_DEFAULT = {
    "A": 2200.0,   # 清洁告警 / 24h（7 日清洁量 15,077 折算日 ≈ 2,154）
    "U": 600.0,    # 去重外源 IP / 24h
    "H": 14000.0,  # Cowrie 建连 / 24h（10-17 单日 14,147）
    "P": 6.0,      # 有命中的诱捕端口数（上限 9）
}

# 等级（设计书 §3.4）：先按 p50≈29 标定
GRADES = [(20.0, "静"), (40.0, "正常"), (60.0, "偏高"), (80.0, "高")]


# ---------------------------------------------------------------- 工具函数

def is_reserved(ip):
    """True = 内网/保留/回环。解析失败也当保留，避免污染分母。"""
    if not ip:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        addr = mapped
    return any(addr in net for net in RESERVED_NETS)


def parse_ts(value):
    """容忍 eve.json 的 '2026-10-18T13:03:21.123456+0800' 写法。"""
    if not value:
        return None
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if len(s) >= 5 and s[-5] in "+-" and s[-4:].isdigit():
        s = s[:-2] + ":" + s[-2:]
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def expand(paths):
    """把 --eve/--cowrie 展开成真实文件列表（只读定位）。"""
    out = []
    for p in paths:
        if os.path.isdir(p):
            out.extend(sorted(glob.glob(os.path.join(p, "*.json*"))))
        elif os.path.isfile(p):
            out.append(p)
        else:
            out.extend(sorted(glob.glob(p)))
    return [f for f in out if not f.endswith(".gz")]


def in_window(ts, since, until):
    return ts is not None and since <= ts < until


def grade(nis):
    for limit, label in GRADES:
        if nis < limit:
            return label
    return "极异常"


def channel_score(x, ref):
    """s = min(1, ln(1 + x/ref) / ln(1+K))：单调、有界、抗长尾。"""
    if ref <= 0 or x <= 0:
        return 0.0
    return min(1.0, math.log1p(x / ref) / math.log1p(K))


def fmt_row(key, x, ref, s, w, unit):
    return ("  %-4s %10.1f%-6s ref=%-9.1f s=%5.3f w=%-5.2f -> %5.2f"
            % (key, x, unit, ref, s, w, 100.0 * w * s))


# ---------------------------------------------------------------- 采集

def scan_eve(files, since, until):
    """流式读 eve.json，绝不整文件入内存。"""
    st = {
        "files": len(files), "lines": 0, "parsed": 0, "bad": 0,
        "alert_total": 0, "alert_hb": 0, "alert_internal": 0,
        "flow_total": 0, "http_total": 0, "ssh_total": 0, "dns_total": 0, "tls_total": 0,
    }
    src_clean = set()
    per_src_alerts = {}
    decoy_hits = dict((p, 0) for p in DECOY_PORTS)
    decoy_srcs = dict((p, set()) for p in DECOY_PORTS)
    hit_count = {}

    for path in files:
        try:
            fh = open(path, "r", encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            print("[warn] 打不开 %s: %s" % (path, exc), file=sys.stderr)
            continue
        with fh:
            for line in fh:
                st["lines"] += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    st["bad"] += 1
                    continue
                st["parsed"] += 1
                if not isinstance(ev, dict):
                    continue
                ts = parse_ts(ev.get("timestamp"))
                if not in_window(ts, since, until):
                    continue
                etype = ev.get("event_type")
                src = ev.get("src_ip") or ""

                # 心跳必须先于内网过滤判定：它本来就是 10.0.0.10 -> 169.254.0.4，
                # 先按 reserved 丢掉就永远量不出那 94.9% 的占比。
                if etype == "alert":
                    st["alert_total"] += 1
                    sig = (ev.get("alert") or {}).get("signature") or ""
                    if (sig == HB_SIGNATURE and src == HB_SRC
                            and ev.get("dest_ip") == HB_DST
                            and ev.get("dest_port") == HB_DPORT):
                        st["alert_hb"] += 1
                        continue

                if is_reserved(src):
                    if etype == "alert":
                        st["alert_internal"] += 1
                    continue

                if etype == "alert":
                    src_clean.add(src)
                    per_src_alerts[src] = per_src_alerts.get(src, 0) + 1
                elif etype in ("flow", "http", "ssh", "dns", "tls"):
                    st[etype + "_total"] += 1

                dport = ev.get("dest_port")
                if dport in decoy_hits:
                    decoy_hits[dport] += 1
                    decoy_srcs[dport].add(src)
                    hit_count[src] = hit_count.get(src, 0) + 1

    st["uniq_src"] = len(src_clean)
    st["decoy_hits"] = decoy_hits
    st["decoy_srcs"] = dict((p, len(v)) for p, v in decoy_srcs.items())
    st["hit_ports"] = sum(1 for n in decoy_hits.values() if n > 0)
    st["multi_port_srcs"] = sum(1 for n in hit_count.values() if n >= 3)
    st["src_any_hit"] = len(hit_count)
    if per_src_alerts:
        top_src, top_n = max(per_src_alerts.items(), key=lambda kv: kv[1])
        total = sum(per_src_alerts.values())
        st["top_src"] = top_src
        st["top_src_share"] = round(top_n / float(total), 4) if total else 0.0
    else:
        st["top_src"], st["top_src_share"] = None, 0.0
    return st


def scan_cowrie(files, since, until):
    """Cowrie：建连按 session 去重；登录事件分开数。"""
    st = {"files": len(files), "lines": 0, "parsed": 0, "sessions": 0,
          "logins": 0, "login_fails": 0, "ports": {}}
    seen = set()
    srcs = set()
    for path in files:
        try:
            fh = open(path, "r", encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            print("[warn] 打不开 %s: %s" % (path, exc), file=sys.stderr)
            continue
        with fh:
            for line in fh:
                st["lines"] += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                st["parsed"] += 1
                if not isinstance(ev, dict):
                    continue
                if not in_window(parse_ts(ev.get("timestamp")), since, until):
                    continue
                src = ev.get("src_ip") or ""
                if is_reserved(src):
                    continue
                evid = ev.get("eventid") or ""
                if evid == "cowrie.session.connect":
                    sid = ev.get("session") or ""
                    if sid not in seen:
                        seen.add(sid)
                        st["sessions"] += 1
                        srcs.add(src)
                elif evid == "cowrie.login.success":
                    st["logins"] += 1
                elif evid == "cowrie.login.failed":
                    st["login_fails"] += 1
                dport = ev.get("dst_port")
                if dport is not None:
                    st["ports"][str(dport)] = st["ports"].get(str(dport), 0) + 1
    st["uniq_src"] = len(srcs)
    return st


# ---------------------------------------------------------------- 组装

def compute(st_eve, st_cowrie, ref):
    a = st_eve["alert_total"] - st_eve["alert_hb"] - st_eve["alert_internal"]
    x = {
        "A": float(max(a, 0)),
        "U": float(st_eve["uniq_src"]),
        "H": float(st_cowrie["sessions"]),
        "P": float(st_eve["hit_ports"]),
    }
    s = dict((k, channel_score(x[k], ref[k])) for k in x)
    contrib = dict((k, WEIGHTS[k] * s[k]) for k in x)
    nis = round(100.0 * sum(contrib.values()), 1)
    return x, s, contrib, nis


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="计算本平台观测到的互联网背景噪音强度 (NIS 0-100)。只读，不写线上。")
    ap.add_argument("--eve", action="append",
                    default=["/opt/suricata/logs/eve.json", "/var/lib/suricata/eve.json"],
                    help="eve.json 路径/glob/目录，可重复；默认试两个已知位置")
    ap.add_argument("--cowrie", action="append", default=["/opt/cowrie/logs/cowrie.json*"],
                    help="Cowrie 日志路径/glob/目录，可重复")
    ap.add_argument("--window-hours", type=float, default=24.0,
                    help="窗口长度（默认 24；右端为 --until 或当前时间）")
    ap.add_argument("--since", help="ISO8601 起点（覆盖 --window-hours）")
    ap.add_argument("--until", help="ISO8601 终点（默认现在）")
    ap.add_argument("--ref", help='覆盖参考值 JSON，如 {"A":3000,"U":800,"H":12000,"P":8}')
    ap.add_argument("--json", action="store_true", help="只输出一行 JSON")
    ap.add_argument("--explain", action="store_true", help="附上各通道原始分母")
    ap.add_argument("--dry-run", action="store_true",
                    help="只检查数据源可读性，不计算（本机无 eve.json 时用）")
    args = ap.parse_args(argv)

    ref = dict(REF_DEFAULT)
    if args.ref:
        try:
            over = json.loads(args.ref)
            for k, v in over.items():
                ref[k] = float(v)
        except (ValueError, AttributeError, TypeError) as exc:
            print("参数错误：--ref 不是合法 JSON 对象：%s" % exc, file=sys.stderr)
            return 2

    until = parse_ts(args.until) if args.until else datetime.now(timezone.utc)
    if args.since:
        since = parse_ts(args.since)
    else:
        since = None
    if since is None and not args.since:
        since = until - timedelta(hours=args.window_hours)
    if until is None or since is None or since >= until:
        print("参数错误：时间窗口为空或无法解析", file=sys.stderr)
        return 2
    hours = (until - since).total_seconds() / 3600.0

    eve_files = expand(args.eve)
    cowrie_files = expand(args.cowrie)

    if args.dry_run:
        print("窗口      %s -> %s  (%.1fh)" % (since.isoformat(), until.isoformat(), hours))
        print("eve.json  %d 个：%s" % (len(eve_files), eve_files or "（找不到）"))
        print("cowrie    %d 个：%s" % (len(cowrie_files), cowrie_files or "（找不到）"))
        print("参考值    %s" % json.dumps(ref, ensure_ascii=False))
        ok = bool(eve_files or cowrie_files)
        print("自检      " + ("通过（至少一路数据可读）" if ok else "失败：两路数据都找不到"))
        return 0 if ok else 1

    st_eve = scan_eve(eve_files, since, until)
    st_cowrie = scan_cowrie(cowrie_files, since, until)

    # 数据完整性闸门：没有有效行就不出分（宁可报错，不编数字）
    if st_eve["parsed"] == 0 and st_cowrie["parsed"] == 0:
        print("没有读到任何有效事件行 —— 不给分数。先 --dry-run 确认路径与权限。",
              file=sys.stderr)
        return 1

    degraded = []
    if hours < 20:
        degraded.append("窗口仅 %.1fh（<20h），按比例外推会失真" % hours)
    if st_eve["parsed"] == 0:
        degraded.append("eve.json 无有效行：A/U/P 通道缺数据")
    if st_cowrie["parsed"] == 0:
        degraded.append("cowrie 无有效行：H 通道缺数据")
    if st_eve["top_src_share"] > 0.5:
        degraded.append("单源占比 %.0f%%：A 通道被一个源主导，需人工复核"
                        % (100 * st_eve["top_src_share"]))

    x, s, contrib, nis = compute(st_eve, st_cowrie, ref)
    scale = 24.0 / hours if hours > 0 else 1.0
    hb_share = (st_eve["alert_hb"] / float(st_eve["alert_total"])
                if st_eve["alert_total"] else 0.0)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"since": since.isoformat(timespec="seconds"),
                   "until": until.isoformat(timespec="seconds"),
                   "hours": round(hours, 2)},
        "nis": nis,
        "grade": grade(nis),
        "channels": {},
        "heartbeat": {
            "alert_hb": st_eve["alert_hb"],
            "alert_total": st_eve["alert_total"],
            "share": round(hb_share, 4),
            "note": "已从 A 通道剔除；占比明显高于 0 说明心跳仍在刷 alert",
        },
        "decoy": {
            "open_ports": DECOY_PORTS,
            "hit_ports": st_eve["hit_ports"],
            "hits": dict((str(p), n) for p, n in st_eve["decoy_hits"].items()),
            "srcs": dict((str(p), n) for p, n in st_eve["decoy_srcs"].items()),
            "multi_port_srcs": st_eve["multi_port_srcs"],
            "src_any_hit": st_eve["src_any_hit"],
        },
        "cowrie": {"sessions": st_cowrie["sessions"],
                   "logins": st_cowrie["logins"],
                   "login_fails": st_cowrie["login_fails"],
                   "uniq_src": st_cowrie["uniq_src"]},
        "eve": dict((k, st_eve[k]) for k in
                    ("files", "lines", "parsed", "bad", "flow_total", "http_total",
                     "ssh_total", "dns_total", "tls_total", "top_src", "top_src_share")),
        "degraded": degraded,
    }
    for k in ("A", "U", "H", "P"):
        result["channels"][k] = {
            "x": x[k],
            "x_24h": round(x[k] * scale, 1) if k != "P" else x[k],
            "ref": ref[k],
            "s": round(s[k], 4),
            "w": WEIGHTS[k],
            "contribution": round(100.0 * contrib[k], 2),
        }

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0

    print("互联网噪音指数 NIS = %.1f / 100   等级：%s   窗口 %.1fh (%s -> %s)"
          % (nis, grade(nis), hours,
             since.isoformat(timespec="minutes"), until.isoformat(timespec="minutes")))
    print("  A=清洁告警  U=去重外源IP  H=蜜罐建连  P=诱捕端口面")
    for k in ("A", "U", "H", "P"):
        unit = "" if k == "P" else "/24h"
        print(fmt_row(k, x[k], ref[k], s[k], WEIGHTS[k], unit))
    print("  %-4s %10s %-6s %-13s %5s %-5s -> %5.1f" % ("合计", "", "", "", "", "", nis))
    print("  心跳剔除 %d/%d = %.1f%%（单列，不进 A）"
          % (st_eve["alert_hb"], st_eve["alert_total"], 100 * hb_share))
    print("  蜜罐端口命中 %d/%d，多端口源 %d 个，触及诱捕端口源 %d 个"
          % (st_eve["hit_ports"], len(DECOY_PORTS), st_eve["multi_port_srcs"],
             st_eve["src_any_hit"]))
    print("  Cowrie 建连 %d，登录成功 %d，失败 %d"
          % (st_cowrie["sessions"], st_cowrie["logins"], st_cowrie["login_fails"]))
    if args.explain:
        print("  eve 行数 %d（解析 %d / 坏行 %d）；cowrie 行数 %d（解析 %d）"
              % (st_eve["lines"], st_eve["parsed"], st_eve["bad"],
                 st_cowrie["lines"], st_cowrie["parsed"]))
        print("  单源最大占比 %.2f%%（%s）"
              % (100 * st_eve["top_src_share"], st_eve["top_src"]))
        print("  flow %d http %d ssh %d dns %d tls %d"
              % (st_eve["flow_total"], st_eve["http_total"], st_eve["ssh_total"],
                 st_eve["dns_total"], st_eve["tls_total"]))
    for d in degraded:
        print("  [!] %s" % d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
