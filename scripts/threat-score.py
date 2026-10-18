#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""威胁评分（离线批处理）—— 只读已有日志，给来源 IP 打 0-100 分。

数据全部来自本机已落盘的运行数据，不调用任何外部 API：
  * Suricata eve.json（alert 事件：告警次数、独立 signature_id、目的端口）
  * Cowrie JSON 日志（session.connect / login.success / login.failed）
  * Dionaea SQLite（connections + logins）或 dionaea.json（连接/凭据）
  * blocked-ips.json 或 --ban-ip（是否曾触发封禁）
  * --self-ip（自有/内部资产，记 0 分自噪声）

计分（满分 100）：
  告警次数 28 + 独立规则 16 + 蜜罐会话 20 + 口令尝试 14 + 端口跨度 12 + 封禁 10
自噪声（心跳 169.254.0.4 相关、RFC1918 内部源，或 --self-ip 指定）直接 0 分。

用法示例：
  python3 scripts/threat-score.py \
    --suricata /opt/suricata/logs/eve.json \
    --cowrie '/opt/cowrie/logs/cowrie.json*' \
    --dionaea-db /opt/dionaea/var/lib/dionaea/dionaea.sqlite \
    --ban-ip 198.18.0.9 --self-ip 47.96.106.187 \
    --out-csv /tmp/threat-score.csv --out-md /tmp/threat-score.md

只写 CSV / Markdown，不改动任何输入数据。
"""

from __future__ import annotations

import argparse
import csv
import glob
import gzip
import ipaddress
import json
import math
import os
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Iterator, TextIO

# ---- 权重（合计 100）----
W_ALERTS = 28.0
W_RULES = 16.0
W_SESSIONS = 20.0
W_CREDS = 14.0
W_PORTS = 12.0
W_BANNED = 10.0

# 归一化上限
ALERTS_FULL = 1000.0     # 1000 条告警封顶
RULES_FULL = 4.0         # 4 条不同规则封顶
SESSIONS_FULL = 500.0    # 500 个蜜罐会话封顶（对数）
CREDS_FULL = 500.0       # 500 次口令尝试封顶（对数）
PORTS_FULL = 5.0         # 5 个不同服务端口封顶

HEARTBEAT_MARKER = "169.254.0.4"


def eprint(*a: object) -> None:
    print(*a, file=sys.stderr)


def parse_ts(value: object) -> float | None:
    """尽量把日志时间戳转成 UTC epoch 秒；失败返回 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if v > 1e8 else None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def iso(epoch: float | None) -> str:
    if not epoch:
        return ""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class IPStat:
    ip: str
    alerts: int = 0
    rules: set[str] = field(default_factory=set)
    sessions: int = 0
    creds: int = 0
    ports: set[int] = field(default_factory=set)
    dests: set[str] = field(default_factory=set)
    first_seen: float | None = None
    last_seen: float | None = None
    banned: bool = False
    sources: set[str] = field(default_factory=set)
    rule_names: dict[str, str] = field(default_factory=dict)

    def touch(self, ts: float | None) -> None:
        if ts is None:
            return
        if self.first_seen is None or ts < self.first_seen:
            self.first_seen = ts
        if self.last_seen is None or ts > self.last_seen:
            self.last_seen = ts

    def add_port(self, port: object) -> None:
        try:
            p = int(str(port).strip())
        except (TypeError, ValueError):
            return
        if 0 < p < 65536:
            self.ports.add(p)


class Agg:
    def __init__(self) -> None:
        self.ips: dict[str, IPStat] = {}
        self.stats: dict[str, int] = defaultdict(int)
        self.sig_names: dict[str, str] = {}
        self.window_min: float | None = None
        self.window_max: float | None = None

    def get(self, ip: str) -> IPStat:
        st = self.ips.get(ip)
        if st is None:
            st = IPStat(ip=ip)
            self.ips[ip] = st
        return st

    def note_ts(self, ts: float | None) -> None:
        if ts is None:
            return
        if self.window_min is None or ts < self.window_min:
            self.window_min = ts
        if self.window_max is None or ts > self.window_max:
            self.window_max = ts


def open_text(path: str) -> TextIO:
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def expand_paths(patterns: Iterable[str]) -> list[str]:
    out: list[str] = []
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if hits:
            out.extend(hits)
        elif os.path.exists(pat):
            out.append(pat)
        else:
            eprint(f"[warn] 路径不存在，跳过: {pat}")
    # 去重且保持顺序
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def iter_json_lines(path: str, needle: str = "") -> Iterator[dict]:
    with open_text(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            if needle and needle not in line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(obj, dict):
                yield obj


# ---------------- 各数据源 ----------------

def load_suricata(agg: Agg, patterns: list[str]) -> None:
    for path in expand_paths(patterns):
        n = 0
        for obj in iter_json_lines(path, '"event_type"'):
            if obj.get("event_type") != "alert":
                continue
            src = obj.get("src_ip") or ""
            if not src:
                continue
            st = agg.get(str(src))
            st.alerts += 1
            st.sources.add("suricata")
            agg.stats["suricata_alert"] += 1
            alert = obj.get("alert") or {}
            sid = alert.get("signature_id")
            if sid is not None:
                key = str(sid)
                st.rules.add("sid:" + key)
                sig = str(alert.get("signature") or "")
                if sig:
                    st.rule_names.setdefault("sid:" + key, sig)
                    agg.sig_names.setdefault("sid:" + key, sig)
            st.add_port(obj.get("dest_port"))
            dst = obj.get("dest_ip")
            if dst:
                st.dests.add(str(dst))
            ts = parse_ts(obj.get("timestamp"))
            st.touch(ts)
            agg.note_ts(ts)
            n += 1
        eprint(f"[suricata] {path}: {n} 条 alert")


def load_cowrie(agg: Agg, patterns: list[str]) -> None:
    for path in expand_paths(patterns):
        n = 0
        for obj in iter_json_lines(path):
            ev = str(obj.get("eventid") or "")
            if not ev.startswith("cowrie."):
                continue
            src = obj.get("src_ip") or ""
            if not src:
                continue
            st = agg.get(src)
            st.sources.add("cowrie")
            ts = parse_ts(obj.get("timestamp"))
            st.touch(ts)
            agg.note_ts(ts)
            if ev == "cowrie.session.connect":
                st.sessions += 1
                agg.stats["cowrie_session"] += 1
                st.add_port(obj.get("dst_port"))
                dst = obj.get("dst_ip")
                if dst:
                    st.dests.add(str(dst))
            elif ev in ("cowrie.login.success", "cowrie.login.failed"):
                st.creds += 1
                agg.stats["cowrie_login"] += 1
            n += 1
        eprint(f"[cowrie] {path}: {n} 条事件")


def load_dionaea_db(agg: Agg, path: str) -> None:
    if not os.path.exists(path):
        eprint(f"[warn] dionaea sqlite 不存在，跳过: {path}")
        return
    # 只读打开，绝不能写库
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        n = 0
        for host, cnt, local_ports, tmin, tmax in cur.execute(
            "select remote_host, count(*), group_concat(distinct local_port), "
            "min(connection_timestamp), max(connection_timestamp) "
            "from connections where connection_type='accept' group by remote_host"
        ):
            if not host:
                continue
            st = agg.get(str(host))
            st.sessions += int(cnt or 0)
            st.sources.add("dionaea-db")
            for p in str(local_ports or "").replace(",", " ").split():
                st.add_port(p)
            st.touch(parse_ts(tmin))
            st.touch(parse_ts(tmax))
            agg.note_ts(parse_ts(tmin))
            agg.note_ts(parse_ts(tmax))
            agg.stats["dionaea_session"] += int(cnt or 0)
            n += int(cnt or 0)
        lgn = 0
        for host, cnt in cur.execute(
            "select c.remote_host, count(*) from logins l "
            "join connections c on l.connection=c.connection group by c.remote_host"
        ):
            if not host:
                continue
            st = agg.get(str(host))
            st.creds += int(cnt or 0)
            st.sources.add("dionaea-db")
            agg.stats["dionaea_login"] += int(cnt or 0)
            lgn += int(cnt or 0)
        eprint(f"[dionaea-db] {path}: {n} 连接 / {lgn} 条凭据")
    finally:
        con.close()


def load_dionaea_json(agg: Agg, patterns: list[str]) -> None:
    for path in expand_paths(patterns):
        n = 0
        for obj in iter_json_lines(path):
            conn = obj.get("connection") or {}
            if str(conn.get("type") or "") != "accept":
                continue
            src = obj.get("src_ip") or ""
            if not src:
                continue
            st = agg.get(src)
            st.sessions += 1
            st.sources.add("dionaea-json")
            st.add_port(obj.get("dst_port"))
            dst = obj.get("dst_ip")
            if dst:
                st.dests.add(str(dst))
            creds = obj.get("credentials") or []
            if isinstance(creds, list):
                st.creds += len(creds)
            ts = parse_ts(obj.get("timestamp"))
            st.touch(ts)
            agg.note_ts(ts)
            agg.stats["dionaea_json_conn"] += 1
            n += 1
        eprint(f"[dionaea-json] {path}: {n} 条连接")


def load_bans(agg: Agg, path: str | None, extra: list[str]) -> None:
    banned: set[str] = set()
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
            for it in items:
                if isinstance(it, dict) and it.get("ip"):
                    banned.add(str(it["ip"]).strip())
                elif isinstance(it, str):
                    banned.add(it.strip())
        except (json.JSONDecodeError, OSError) as exc:
            eprint(f"[warn] 封禁列表读取失败 {path}: {exc}")
    for ip in extra:
        if ip.strip():
            banned.add(ip.strip())
    for ip in banned:
        st = agg.ips.get(ip)
        if st is None:
            continue
        st.banned = True
        st.sources.add("blocked")
    agg.stats["banned_ips"] = len(banned)
    eprint(f"[blocked] {len(banned)} 个历史封禁 IP")


# ---------------- 打分 ----------------

def is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.is_private or addr.is_link_local or addr.is_loopback


def score_all(agg: Agg, self_ips: set[str] | None = None) -> list[dict]:
    self_ips = self_ips or set()
    rows: list[dict] = []
    for st in agg.ips.values():
        noise_reason = ""
        if st.ip in self_ips:
            noise_reason = "自有资产/内部源"
        elif st.ip.startswith("169.254.") or is_private(st.ip) or any(d == HEARTBEAT_MARKER for d in st.dests):
            noise_reason = "心跳/内部自噪声"
        # 心跳签名只在“目的=169.254.0.4”时成立，避免把真实攻击误清零
        alert_pts = W_ALERTS * min(1.0, math.log10(1 + st.alerts) / 3.0)
        rule_pts = W_RULES * min(1.0, len(st.rules) / RULES_FULL)
        sess_pts = W_SESSIONS * min(1.0, math.log10(1 + st.sessions) / math.log10(1 + SESSIONS_FULL))
        cred_pts = W_CREDS * min(1.0, math.log10(1 + st.creds) / math.log10(1 + CREDS_FULL))
        port_pts = W_PORTS * min(1.0, max(0, len(st.ports) - 1) / (PORTS_FULL - 1))
        ban_pts = W_BANNED if st.banned else 0.0
        total = alert_pts + rule_pts + sess_pts + cred_pts + port_pts + ban_pts
        if noise_reason:
            total = 0.0
        port_span = (max(st.ports) - min(st.ports) + 1) if st.ports else 0
        rows.append({
            "ip": st.ip,
            "score": round(total, 1),
            "alert_pts": round(alert_pts, 1),
            "rule_pts": round(rule_pts, 1),
            "session_pts": round(sess_pts, 1),
            "cred_pts": round(cred_pts, 1),
            "port_pts": round(port_pts, 1),
            "ban_pts": round(ban_pts, 1),
            "alerts": st.alerts,
            "rules": len(st.rules),
            "sessions": st.sessions,
            "creds": st.creds,
            "ports": len(st.ports),
            "port_span": port_span,
            "banned": int(st.banned),
            "self_noise": int(bool(noise_reason)),
            "noise_reason": noise_reason,
            "first_seen": iso(st.first_seen),
            "last_seen": iso(st.last_seen),
            "top_rules": "; ".join(
                f"{k.replace('sid:', '')} {(st.rule_names.get(k) or agg.sig_names.get(k) or '')[:60]}"
                for k in sorted(st.rules)[:5]
            ),
            "top_dests": ",".join(sorted(st.dests)[:6]),
            "sources": "+".join(sorted(st.sources)),
        })
    rows.sort(key=lambda r: (-r["score"], -r["alerts"], r["ip"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def write_csv(rows: list[dict], path: str | None) -> None:
    cols = [
        "rank", "ip", "score", "alerts", "rules", "sessions", "creds", "ports",
        "port_span", "banned", "self_noise", "noise_reason",
        "alert_pts", "rule_pts", "session_pts", "cred_pts", "port_pts", "ban_pts",
        "first_seen", "last_seen", "top_rules", "top_dests", "sources",
    ]
    if path:
        fh = open(path, "w", encoding="utf-8", newline="")
    else:
        fh = sys.stdout
    try:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    finally:
        if path:
            fh.close()


def write_md(rows: list[dict], agg: Agg, path: str | None, argv: list[str]) -> None:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    wmin = agg.window_min
    wmax = agg.window_max
    top = [r for r in rows if r["score"] > 0][:10]
    lines: list[str] = []
    add = lines.append
    add("# 威胁评分 Top 10（离线批处理）")
    add("")
    add(f"- 生成时间：{now}")
    add(f"- 数据窗口：{iso(wmin)} ~ {iso(wmax)}")
    add(f"- 输入规模：Suricata alert {agg.stats['suricata_alert']} 条，"
        f"Cowrie 会话 {agg.stats['cowrie_session']} 个 / 登录 {agg.stats['cowrie_login']} 次，"
        f"Dionaea 连接 {agg.stats['dionaea_session'] or agg.stats['dionaea_json_conn']} 个 / 凭据 {agg.stats['dionaea_login']} 条，"
        f"封禁名单 {agg.stats['banned_ips']} 个")
    add(f"- 计分脚本：`scripts/threat-score.py`（离线，无外部 API）")
    add("")
    add("## 计分构成")
    add("")
    add("| 特征 | 权重 | 归一化 |")
    add("|---|---:|---|")
    add("| 告警次数 | 28 | log10(1+n)/3，1000 条封顶 |")
    add("| 独立规则命中 | 16 | 每 1 条 4 分，4 条封顶 |")
    add("| 蜜罐会话数 | 20 | log 归一，500 个封顶 |")
    add("| 口令尝试次数 | 14 | log 归一，500 次封顶 |")
    add("| 端口跨度 | 12 | 去重服务端口，5 个封顶 |")
    add("| 是否封禁 | 10 | 历史封禁名单命中即 10 |")
    add("")
    add("## 前 10 名")
    add("")
    add("| # | 来源 IP | 总分 | 告警 | 规则 | 会话 | 口令 | 端口 | 封禁 |")
    add("|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in top:
        add(f"| {r['rank']} | `{r['ip']}` | **{r['score']}** | {r['alert_pts']} | {r['rule_pts']} | "
            f"{r['session_pts']} | {r['cred_pts']} | {r['port_pts']} | {r['ban_pts']} |")
    add("")
    add("## 原始计数（同一排序）")
    add("")
    add("| # | IP | 告警条数 | 不同规则 | 会话 | 口令 | 服务端口 | 端口跨度 | 封禁 | 首次/末次（UTC） |")
    add("|---:|---|---:|---:|---:|---:|---:|---:|---|---|")
    for r in top:
        first = r["first_seen"][:16] if r["first_seen"] else "-"
        last = r["last_seen"][:16] if r["last_seen"] else "-"
        add(f"| {r['rank']} | `{r['ip']}` | {r['alerts']} | {r['rules']} | {r['sessions']} | "
            f"{r['creds']} | {r['ports']} | {r['port_span']} | {'是' if r['banned'] else '否'} | {first} / {last} |")
    add("")
    if top:
        add("## 主要规则命中")
        add("")
        for r in top:
            if r["top_rules"]:
                add(f"- `{r['ip']}`：{r['top_rules']}")
        add("")
    noise = [r for r in rows if r["self_noise"]]
    if noise:
        add("## 自噪声（记 0 分，不参与排名）")
        add("")
        for r in noise[:10]:
            add(f"- `{r['ip']}`：{r['noise_reason']}；原始计数 告警 {r['alerts']} / 会话 {r['sessions']} / 口令 {r['creds']}")
        add("")
    add("## 口径与限制")
    add("")
    add("- 来源 IP 只取日志里的 `src_ip`；Dionaea 用 SQLite 的 accept 连接与 logins 关联，避免和 dionaea.json 重复计数。")
    add("- 独立规则按 Suricata `signature_id` 去重；本仓库的 xk-lab 规则未部署，因此这里反映的是线上 ET 规则命中。")
    add("- 端口跨度按“去重后的目的服务端口数”计分；`port_span` 另列 max-min+1 供核对。")
    add("- 心跳（10.0.0.10 → 169.254.0.4:80）与 RFC1918 内部源自噪声直接 0 分，但保留原始计数。")
    add("- 时间窗口由日志本身决定，不裁剪；封禁名单按历史记录计，不区分是否已过期。")
    text = "\n".join(lines) + "\n"
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="离线威胁评分（0-100）")
    ap.add_argument("--suricata", action="append", default=[], help="eve.json 路径/通配符，可多次")
    ap.add_argument("--cowrie", action="append", default=[], help="cowrie.json* 路径/通配符，可多次")
    ap.add_argument("--dionaea-db", default="", help="dionaea.sqlite（优先）")
    ap.add_argument("--dionaea-json", action="append", default=[], help="dionaea.json*（无 DB 时用）")
    ap.add_argument("--ban-json", default="", help="blocked-ips.json")
    ap.add_argument("--ban-ip", action="append", default=[], help="额外封禁 IP，可多次")
    ap.add_argument("--self-ip", action="append", default=[], help="自有/内部资产 IP，记 0 分自噪声，可多次")
    ap.add_argument("--out-csv", default="", help="CSV 输出路径；缺省打印到 stdout")
    ap.add_argument("--out-md", default="", help="Markdown 输出路径；缺省打印到 stdout")
    args = ap.parse_args(argv)

    if not (args.suricata or args.cowrie or args.dionaea_db or args.dionaea_json):
        ap.error("至少给一个数据源（--suricata / --cowrie / --dionaea-db / --dionaea-json）")

    agg = Agg()
    load_suricata(agg, args.suricata)
    load_cowrie(agg, args.cowrie)
    if args.dionaea_db:
        load_dionaea_db(agg, args.dionaea_db)
    else:
        load_dionaea_json(agg, args.dionaea_json)
    load_bans(agg, args.ban_json, args.ban_ip)

    rows = score_all(agg, set(args.self_ip))
    write_csv(rows, args.out_csv or None)
    if args.out_md or not args.out_csv:
        write_md(rows, agg, args.out_md or None, argv)
    eprint(f"[done] {len(rows)} 个来源 IP，非零 {sum(1 for r in rows if r['score'] > 0)} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
