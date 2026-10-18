#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""noise-index.py —— 计算「本平台观测到的互联网背景噪音强度」(NIS, 0–100)

设计书：docs/噪音指数设计-20261018.md

只读脚本：仅 open(..., "r") 读取数据源，结果只写 stdout（或 --json 输出到 stdout）。
不写 eve.json 所在目录、不写任何线上路径、不发网络请求。

数据源
-------
--eve    Suricata eve.json（JSON Lines）。支持传入单个文件、glob（如
         '/opt/suricata/logs/eve.json*'）或目录（取目录下 eve.json* 全部轮转文件）。
--cowrie Cowrie 日志（JSON Lines）。同上，支持 glob/目录（取 cowrie.json*）。
         默认路径是文档记录的位置；本机不存在时用 --dry-run 自检。

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

# 诱捕端口（docs/噪音指数设计-20261018.md §2.2）
DECOY_PORTS = [21, 22, 23, 1433, 2222, 3306, 6379, 9080, 27017]

# 心跳告警指纹：Wazuh agent 每 5 分钟 POST /ca_report.cgi 到 169.254.0.4:80
# 单条 signature 覆盖了全量 alert 的 94.9%，必须剔除，单列 NIS_HB。
HB_SIGNATURE = "ET INFO Python-urllib/ Suspicious User Agent"
HB_SRC = "10.0.0.10"
HB_DST = "169.254.0.4"
HB_DPORT = 80
HB_URL_MARK = "/ca_report.cgi"

# 保留/内部地址：不计入「互联网噪音」
RESERVED_NETS = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24",
    "192.168.0.0/16", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24",
    "224.0.0.0/4", "240.0.0.0/4", "::1/128", "fc00::/7", "fe80::/10",
)]

# 权重（§3.2 表）：为什么是这四个数写在设计书里
WEIGHTS = {"A": 0.40, "U": 0.25, "H": 0.20, "P": 0.15}

# 饱和常数：x = K × 参考值 时该通道得分 ≈ 1.0
K = 10.0

# 冷启动参考值（x_ref）。首次跑出 30 天 p50 后应由 --ref 覆盖。
REF_DEFAULT = {
    "A": 2200.0,   # 清洁告警 / 24h（7 日清洁量 15,077 折算日 ≈ 2,154）
    "U": 600.0,    # 去重外源 IP / 24h
    "H": 14000.0,  # Cowrie 建连 / 24h（10-17 单日 14,147）
    "P": 6.0,      # 有命中的诱捕端口数（满分 9）
}

# 等级（§3.4），先按 p50≈29 标定，30 天后用实测分位数替换
GRADES = [(20.0, "静"), (40.0, "正常"), (60.0, "偏高"), (80.0, "高")]


# ---------------------------------------------------------------- 工具函数

def is_reserved(ip: str) -> bool:
    """True = 内网/保留/回环，不算互联网噪音。解析失败也当保留（不污染分母）。"""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if getattr(addr, "ipv4_mapped", None):
        addr = addr.ipv4_mapped
    return any(addr in net for net in RESERVED_NETS)


def parse_ts(value):
    """容忍 eve.json 的 '2026-10-18T13:03:21.123456+0800' 这类写法。"""
    if not value:
        return None
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # +0800 -> +08:00
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
    """把 --eve/--cowrie 的取值展开成真实文件列表（只读）。"""
    out = []
    for p in paths:
        if os.path.isdir(p):
            out.extend(sorted(glob.glob(os.path.join(p, "*.json*"))))
        elif os.path.isfile(p):
            out.append(p)
        else:
            out.extend(sorted(glob.glob(p)))
    # 轮转文件 .gz 跳过（不引第三方库解压）
    return [f for f in out if not f.endswith(".gz")]


def in_window(ts, since, until):
    return ts is not None and ts >= since and ts < until


def grade(nis):
    for limit, label in GRADES:
        if nis < limit:
            return label
    return "极异常"


def channel_score(x, ref):
    """s = min(1, ln(1 + x/ref) / ln(1+K))，x/ref 单调、饱和、抗长尾。"""
    if ref <= 0 or x <= 0:
        return 0.0
    return min(1.0, math.log1p(x / ref) / math.log1p(K))


def fmt_row(name, x, ref, s, w):
    unit = "" if name == "P" else "/24h"
    return f"  {name:<4} {str(x):>10}{unit:<6} ref={ref:<9.1f} s={s:5.3f} w={w:<5.2f} → {100*w*s:5.2f}"


# ---------------------------------------------------------------- 采集

def scan_eve(files, since, until, want_hb):
    """流式读 eve.json。返回 计数/去重集合/端口分布。永不把整文件读进内存。"""
    st = {
        "lines": 0, "parsed": 0, "bad": 0,
        "alert_total": 0, "alert_hb": 0, "alert_internal": 0,
        "flow_total": 0, "http_total": 0, "ssh_total": 0, "dns_total": 0, "tls_total": 0,
    }
    src_all, src_clean = set(), set()
    per_src_alerts = {}
    decoy_hits = {p: 0 for p in DECOY_PORTS}
    decoy_srcs = {p: set() for p in DECOY_PORTS}
    multi_port_srcs = set()
    hit_count = {}

    for path in files:
        try:
            fh = open(path, "r", encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"[warn] 打不开 {path}: {exc}", file=sys.stderr)
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
                etype = ev.get("event_type")
                ts = parse_ts(ev.get("timestamp"))
                if not in_window(ts, since, until):
                    continue
                src = ev.get("src_ip") or ""

                # 心跳必须先于内部地址过滤判定：它本身就是 10.0.0.10 发往
                # 169.254.0.4，若先按 reserved 丢掉，就永远量不出 94.9% 的占比。
                if etype == "alert":
                    st["alert_total"] += 1
                    sig = (ev.get("alert") or {}).get("signature") or ""
                    is_hb = (
                        sig == HB_SIGNATURE
                        and src == HB_SRC
                        and ev.get("dest_ip") == HB_DST
                        and ev.get("dest_port") == HB_DPORT
                    )
                    if is_hb:
                        st["alert_hb"] += 1
                        continue

                if is_reserved(src):
                    if etype == "alert":
                        st["alert_internal"] += 1
                    continue

                if etype == "alert":
                    src_all.add(src)
                    src_clean.add(src)
                    per_src_alerts[src] = per_src_alerts.get(src, 0) + 1
                elif etype in ("flow", "http", "ssh", "dns", "tls"):
                    st[etype + "_total"] += 1

                # 诱捕端口命中（alert / flow / ssh / 任意事件带 dest_port）
                dport = ev.get("dest_port")
                if dport in decoy_hits:
                    decoy_hits[dport] += 1
                    decoy_srcs[dport].add(src)
                    hit_count[src] = hit_count.get(src, 0) + 1

    for s, n in hit_count.items():
        if n >= 3:
            multi_port_srcs.add(s)

    st["uniq_src"] = len(src_all or src_clean)
    st["decoy_hits"] = decoy_hits
    st["decoy_srcs"] = {p: len(v) for p, v in decoy_srcs.items()}
    st["hit_ports"] = sum(1 for p, n in decoy_hits.items() if n > 0)
    st["multi_port_srcs"] = len(multi_port_srcs)
    st["src_hit3"] = len(hit_count)
    # 单源刷量保护：最大单源占比
    if per_src_alerts:
        top = max(per_src_alerts.values())
        total = sum(per_src_alerts.values())
        st["top_src_share"] = round(top / total, 4) if total else 0.0
        st["top_src"] = max(per_src_alerts, key=per_src_alerts.get)
    else:
        st["top_src_share"], st["top_src"] = 0.0, None
    return st


def scan_cowrie(files, since, until):
    """Cowrie：建连按 session 去重；登录成功/失败分事件。"""
    st = {"lines": 0, "parsed": 0, "sessions": 0, "logins": 0,
          "login_fails": 0, "srcs": set(), "ports": {}}
    seen = set()
    for path in files:
        try:
            fh = open(path, "r", encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"[warn] 打不开 {path}: {exc}", file=sys.stderr)
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
                        st["srcs"].add(src)
                elif evid == "cowrie.login.success":
                    st["logins"] += 1
                elif evid == "cowrie.login.failed":
                    st["login_fails"] += 1
                port = ev.get("dst_port")
                if port is not None:
                    st["ports"][port] = st["ports"].get(port, 0) + 1
    st["uniq_src"] = len(st["srcs"])
    st.pop("srcs", None)
    return st


# ---------------------------------------------------------------- 组装

def compute(st_eve, st_cowrie, ref):
    x = {
        "A": float(st_eve["alert_total"] - st_eve["alert_hb"] - st_eve.get("alert_internal", 0)),
        "U": float(st_eve["uniq_src"]),
        "H": float(st_cowrie["sessions"]),
        "P": float(st_eve["hit_ports"]),
    }
    s = {k: channel_score(x[k], ref[k]) for k in x}
    parts = {k: WEIGHTS[k] * s[k] for k in x}
    nis = round(100.0 * sum(parts.values()), 1)
    return x, s, parts, nis


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="计算本平台观测到的互联网背景噪音强度 (NIS 0–100)。只读，不写线上。")
    ap.add_argument("--eve", action="append",
                    default=["/opt/suricata/logs/eve.json"],
                    help="eve.json 路径/glob/目录，可重复")
    ap.add_argument("--cowrie", action="append",
                    default=["/opt/cowrie/logs/cowrie.json*"],
                    help="Cowrie 日志路径/glob/目录，可重复")
    ap.add_argument("--window-hours", type=float, default=24.0,
                    help="窗口长度（默认 24，窗口右端为 --until 或现在）")
    ap.add_argument("--since", help="ISO8601 UTC 起点（覆盖 --window-hours）")
    ap.add_argument("--until", help="ISO8601 UTC 终点（默认 now）")
    ap.add_argument("--ref", help='JSON 覆盖参考值，如 {"A":3000,"U":800,"H":12000,"P":8}')
    ap.add_argument("--json", action="store_true", help="只输出一行 JSON")
    ap.add_argument("--explain", action="store_true", help="附上每个通道的原始分母")
    ap.add_argument("--dry-run", action="store_true",
                    help="只检查数据源可读性，不计算（本机无 eve.json 时用）")
    args = ap.parse_args(argv)

    ref = dict(REF_DEFAULT)
    if args.ref:
        try:
            ref.update({k: float(v) for k, v in json.loads(args.ref).items()})
        except (ValueError, AttributeError) as exc:
            print(f"参数错误：--ref 不是合法 JSON 对象：{exc}", file=sys.stderr)
            return 2

    until = parse_ts(args.until) if args.until else datetime.now(timezone.utc)
    if args.since:
        since = parse_ts(args.since)
        if since is None:
            print("参数错误：--since 不是 ISO8601", file=sys.stderr)
            return 2
    else:
        since = until - timedelta(hours=args.window_hours)
    if until is None or since >= until:
        print("参数错误：时间窗口为空", file=sys.stderr)
        return 2
    hours = (until - since).total_seconds() / 3600.0

    eve_files = expand(args.eve)
    cowrie_files = expand(args.cowrie)

    if args.dry_run:
        print(f"窗口      {since.isoformat()} → {until.isoformat()}  ({hours:.1f}h)")
        print(f"eve.json  {len(eve_files)} 个：{eve_files or '（找不到）'}")
        print(f"cowrie    {len(cowrie_files)} 个：{cowrie_files or '（找不到）'}")
        print(f"参考值    {json.dumps(ref, ensure_ascii=False)}")
        ok = bool(eve_files or cowrie_files)
        print("自检      " + ("通过（至少一路数据可读）" if ok else "失败：两路数据都找不到"))
        return 0 if ok else 1

    st_eve = scan_eve(eve_files, since, until, want_hb=True)
    st_cowrie = scan_cowrie(cowrie_files, since, until)

    # 数据完整性闸门：没有有效行就不出分（宁可报错，不编数字）
    if st_eve["parsed"] == 0 and st_cowrie["parsed"] == 0:
        print("没有读到任何有效事件行 —— 不出版本化的分数。"
              "先跑 --dry-run 确认路径，或检查文件权限。", file=sys.stderr)
        return 1

    degraded = []
    if hours < 20:
        degraded.append(f"窗口仅 {hours:.1f}h（<20h），按比例外推会失真")
    if st_eve["parsed"] == 0:
        degraded.append("eve.json 无有效行：A/U/P 通道缺数据")
    if st_cowrie["parsed"] == 0:
        degraded.append("cowrie 无有效行：H 通道缺数据")

    x, s, parts, nis = compute(st_eve, st_cowrie, ref)
    # 24h 标准化（A/U/H 都是速率为准；P 是面，不标准化）
    scale = 24.0 / hours if hours > 0 else 1.0

    hb_rate = (st_eve["alert_hb"] / st_eve["alert_total"]) if st_eve["alert_total"] else 0.0
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"since": since.isoformat(timespec="seconds"),
                   "until": until.isoformat(timespec="seconds"),
                   "hours": round(hours, 2)},
        "nis": nis,
        "grade": grade(nis),
        "channels": {
            k: {"x": x[k], "x_24h": round(x[k] * scale, 1) if k != "P" else x[k],
                "ref": ref[k], "s": round(s[k], 4), "w": WEIGHTS[k],
                "contribution": round(100 * parts[k], 2)}
            for k in x
        },
        "heartbeat": {
            "alert_hb": st_eve["alert_hb"],
            "alert_total": st_eve["alert_total"],
            "share": round(hb_rate, 4),
            "note": "已从 A 通道剔除；占比 >0.5 说明心跳仍在刷告警，需查 Wazuh agent 轮询",
        },
        "decoy": {
            "open_ports": DECOY_PORTS,
            "hit_ports": st_eve["hit_ports"],
            "hits": {str(p): n for p, n in st_eve["decoy_hits"].items()},
            "srcs": {str(p): n for p, n in st_eve["decoy_srcs"].items()},
            "multi_port_srcs": st_eve["multi_port_srcs"],
            "src_hit_ge3": st_eve["src_hit3"],
        },
        "cowrie": {"sessions": st_cowrie["sessions"], "logins": st_cowrie["logins"],
                   "login_fails": st_cowrie["login_fails"],
                   "uniq_src": st_cowrie["uniq_src"]},
        "eve": {k: st_eve[k] for k in
                ("lines", "parsed", "bad", "flow_total", "http_total",
                 "ssh_total", "dns_total", "tls_total", "top_src", "top_src_share")},
        "degraded": degraded,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0

    print(f"互联网噪音指数 NIS = {nis} / 100   等级：{grade(nis)}   "
          f"窗口 {hours:.1f}h ({since.isoformat(timespec='minutes')} → "
          f"{until.isoformat(timespec='minutes')})")
    print("  A=清洁告警  U=去重外源IP  H=蜜罐建连  P=诱捕端口面")
    for k in ("A", "U", "H", "P"):
        print(fmt_row(k, x[k], ref[k], s[k], WEIGHTS[k]))
    print(f"  {'合计':<4} {'':>10}  {'':<6}{'':>9} {'':>5} {'':>5} → {nis:5.1f}")
    print(f"  心跳剔除 {st_eve['alert_hb']}/{st_eve['alert_total']} = {hb_rate:.1%}"
          f"（单列，不进 A）")
    print(f"  蜜罐端口命中 {st_eve['hit_ports']}/{len(DECOY_PORTS)}"
          f"，多端口源 {st_eve['multi_port_srcs']} 个，触及≥3 次源 {st_eve['src_hit3']} 个")
    print(f"  Cowrie 建连 {st_cowrie['sessions']}，登录成功 {st_cowrie['logins']}，"
          f"失败 {st_cowrie['login_fails']}")
    if args.explain:
        print(f"  eve 行数 {st_eve['lines']}（解析 {st_eve['parsed']} / 坏行 "
              f"{st_eve['bad']}）；cowrie 行数 {st_cowrie['lines']}（解析 {st_cowrie['parsed']}）")
        print(f"  单源最大占比 {st_eve['top_src_share']:.2%}（{st_eve['top_src']}）")
        print(f"  flow {st_eve['flow_total']} http {st_eve['http_total']} "
              f"ssh {st_eve['ssh_total']} dns {st_eve['dns_total']} tls {st_eve['tls_total']}")
    for d in degraded:
        print(f"  ⚠ {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
