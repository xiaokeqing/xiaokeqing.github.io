#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日 rollup：把"当天的最新快照"固化成一行 append-only 历史。

为什么需要它（站主 2026-11-08 定调，来自外部方案的 M0）：
  · Wazuh 索引只留 7 天（wazuh-retention.timer 每天 05:30 删 7 天前索引）
  · static/api/public/*.js 是"最新覆盖写"，旧值不留
  ⇒ MTTD/MTTR 趋势、覆盖率演进、样本周报这类"看历史"的功能全都做不出来。
  这个脚本每天把关键聚合抽一行写进 data/rollup/YYYY-MM-DD.json，只增不改，
  跟着仓库一起进版本控制，前端在构建期直接读（SSR，不 fetch）。

口径纪律（与全站一致）：
  · 只抄快照里已有的数，不做任何推算；取不到的字段写 null 并在 missing 里登记原因
  · IP 一律只保留快照里的聚合口径，本文件不落任何完整 IP
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "static", "api", "public")
OUT = os.path.join(ROOT, "data", "rollup")
CST = timezone(timedelta(hours=8))


def load(name):
    """读 static/api/public/<name>.js（内容是 JSON，可能带 BOM/空文件）。"""
    p = os.path.join(SNAP, name + ".js")
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            raw = f.read().strip()
        if not raw or raw[0] not in "{[":
            return None
        return json.loads(raw)
    except Exception:
        return None


def unwrap(obj):
    """后端信封 {code,message,data} → data；已是裸对象就原样返回。"""
    if isinstance(obj, dict) and "data" in obj and ("code" in obj or "message" in obj):
        d = obj.get("data")
        return d if d is not None else {}
    return obj or {}


def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    return None


def main():
    today = (datetime.now(CST) - timedelta(hours=4)).strftime("%Y-%m-%d")  # 凌晨跑时归到前一天
    missing = []

    alerts = unwrap(load("alerts"))
    stats24 = alerts.get("stats24h") or {}
    bysev = stats24.get("bySeverity") or {}
    if not bysev:
        missing.append("alerts.stats24h.bySeverity 未取到")

    home = unwrap(load("home"))
    geo = unwrap(load("geo"))
    metrics = unwrap(load("metrics"))
    webstats = unwrap(load("webstats"))
    eval_ = unwrap(load("eval"))

    countries = []
    for c in (geo.get("byCountry") or [])[:5]:
        countries.append({
            "cc": c.get("country"),
            "name": c.get("countryName"),
            "count": num(c.get("count")),
            "share": num(c.get("sharePercent")),
        })
    if not countries:
        missing.append("geo.byCountry 未取到")

    row = {
        "date": today,
        "generatedAt": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "alerts24h": {
            "total": num(stats24.get("total")),
            "cr": num(bysev.get("CRITICAL")),
            "hi": num(bysev.get("HIGH")),
            "me": num(bysev.get("MEDIUM")),
            "lo": num(bysev.get("LOW")),
            "available": bool(stats24.get("available")),
        },
        # home.js 的真实结构：data.audit.summary.{blockedByGuard,blockTotal,blockActive}
        "guard": {
            "blocked": num((audit_sum := ((home.get("audit") or {}).get("summary") or {})).get("blockedByGuard")),
            "blockTotal": num(audit_sum.get("blockTotal")),
            "blockActive": num(audit_sum.get("blockActive")),
        },
        # data.honeypot.{total,connections,logins}；total 是"最近 800 条告警"的窗口，不是全量
        "honeypot": {
            "connections": num((home.get("honeypot") or {}).get("connections")),
            "logins": num((home.get("honeypot") or {}).get("logins")),
        },
        "topCountries": countries,
        "metrics": {
            "mttd": num((metrics.get("mttd") or {}).get("medianMinutes")),
            "mttr": num((metrics.get("mttr") or {}).get("medianMinutes")),
            "blocks": num((metrics.get("samples") or {}).get("blocks")),
            "alerts": num((metrics.get("samples") or {}).get("alerts")),
        },
        # webstats.totals.requests（/webstats.js 的窗口口径，带 window 字段，页面自己会标）
        "web": {
            "requests": num((webstats.get("totals") or {}).get("requests")),
        },
        # eval.js 目前只有 available/reason，没有用例数；如实记录可用性
        "redteam": {
            "available": bool(eval_.get("available")),
        },
        "missing": missing,
    }

    # ATT&CK 快照（由 scripts/attack-coverage.py 生成，不在 /api/public 的 HTTP 快照里）
    ap = os.path.join(ROOT, "data", "attack.json")
    if os.path.exists(ap):
        try:
            with open(ap, "r", encoding="utf-8") as f:
                a = json.load(f)
            total = num(a.get("total"))
            unmapped = num(a.get("unmapped"))
            row["attack"] = {
                "total": total,
                "unmapped": unmapped,
                "coveragePct": (round((total - unmapped) * 100.0 / total, 2)
                                if total and unmapped is not None else None),
                "techniques": len(a.get("techniques") or []),
            }
        except Exception as e:
            missing.append("data/attack.json 解析失败: %s" % e)
    else:
        missing.append("data/attack.json 不存在")

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, today + ".json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(row, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")

    print("[OK] rollup %s → %s" % (today, os.path.relpath(path, ROOT)))
    if missing:
        print("[!] 缺字段 %d 项：%s" % (len(missing), "；".join(missing)))
    return 0 if row["alerts24h"]["available"] else 3


if __name__ == "__main__":
    sys.exit(main())
