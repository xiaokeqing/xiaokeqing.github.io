#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATT&CK 覆盖率快照 —— 从 Wazuh indexer 取真实告警，按 mitre.id / mitre.tactic 聚合。

为什么不是直连 ES：
  宿主机 `curl 127.0.0.1:9200` 是 000（索引器只在 docker 容器网络里监听）。
  已验证的通道是 `ssh secagent-srv2` + `sudo docker exec <indexer> curl https://localhost:9200`。
  本脚本就把这条链路固化下来：查询体从 stdin 喂给容器里的 curl，结果原样取回本地解析。

产出两份（同一份 JSON，内容一致）：
  static/api/public/attack.js   —— 公开快照（纯 JSON，与 alerts.js 同一套口味）
  data/attack.json              —— Hugo data，构建时模板直接读，页面是 SSR 的，不 fetch

口径：
  · 窗口 7 天（= 索引保留上限），`range @timestamp gte now-7d`
  · total    = 窗口内全部告警条数
  · unmapped = must_not exists rule.mitre.id 的条数（必须有；不能算进任何技术）
  · 技术条数 = 该技术出现的告警条数（同一告警带多个技术时各计一次，故∑技术 ≥ 已映射）
  · 战术条数 = rule.mitre.tactic 的桶（Wazuh 输出的是战术“名字”，不是 TA 号，本地映射回 ID）
  · 一条告警可带多个战术，故∑战术 ≥ 已映射；页面上把这条写在明处。

名称表写死在本文件里（不联网）。Wazuh 告警自带的 rule.mitre.technique 优先用作技术名，
表只兜底。

用法：
  python scripts/attack-coverage.py                     # 取数并写两份产物
  python scripts/attack-coverage.py --from-json a.json  # 用已抓到的 ES 响应重建产物（离线）
  python scripts/attack-coverage.py --print             # 只打印，不写文件
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

# ---- 通道默认值（可用参数/环境变量覆盖）------------------------------------
SSH_HOST = "secagent-srv2"
SSH_KEY = ""  # 空 = 走 ~/.ssh/config 里的 Host 段
CONTAINER = ""  # 空 = 自动探测名字里带 indexer 的容器
INDEX = "wazuh-alerts-*"
ES_USER = "admin"
ES_PASS = "Aa1*CDqK2HvlGOU6A5jt"

# ---- 战术名 → ATT&CK 战术 ID（Wazuh 告警里只给名字）--------------------------
TACTIC_IDS = {
    "Reconnaissance": "TA0043",
    "Resource Development": "TA0042",
    "Initial Access": "TA0001",
    "Execution": "TA0002",
    "Persistence": "TA0003",
    "Privilege Escalation": "TA0004",
    "Defense Evasion": "TA0005",
    "Credential Access": "TA0006",
    "Discovery": "TA0007",
    "Lateral Movement": "TA0008",
    "Collection": "TA0009",
    "Exfiltration": "TA0010",
    "Command and Control": "TA0011",
    "Impact": "TA0040",
}

# ---- 技术名兜底表（只覆盖实际出现的 + 常见项；实际告警里的 technique 字段优先）----
TECH_NAMES = {
    "T1040": "Network Sniffing",
    "T1046": "Network Service Discovery",
    "T1048": "Exfiltration Over Alternative Protocol",
    "T1053": "Scheduled Task/Job",
    "T1059": "Command and Scripting Interpreter",
    "T1059.001": "PowerShell",
    "T1059.004": "Unix Shell",
    "T1070": "Indicator Removal",
    "T1071": "Application Layer Protocol",
    "T1078": "Valid Accounts",
    "T1078.001": "Default Accounts",
    "T1078.002": "Domain Accounts",
    "T1078.003": "Local Accounts",
    "T1078.004": "Cloud Accounts",
    "T1082": "System Information Discovery",
    "T1087": "Account Discovery",
    "T1098": "Account Manipulation",
    "T1105": "Ingress Tool Transfer",
    "T1110": "Brute Force",
    "T1110.001": "Password Guessing",
    "T1110.003": "Password Spraying",
    "T1110.004": "Credential Stuffing",
    "T1112": "Modify Registry",
    "T1133": "External Remote Services",
    "T1136": "Create Account",
    "T1190": "Exploit Public-Facing Application",
    "T1505.003": "Web Shell",
    "T1548": "Abuse Elevation Control Mechanism",
    "T1548.003": "Sudo and Sudo Caching",
    "T1562.001": "Disable or Modify Tools",
    "T1565.001": "Stored Data Manipulation",
    "T1566": "Phishing",
    "T1592": "Gather Victim Host Information",
    "T1595": "Active Scanning",
    "T1595.001": "Scanning IP Blocks",
    "T1595.002": "Vulnerability Scanning",
    "T1021": "Remote Services",
    "T1021.001": "Remote Desktop Protocol",
    "T1021.002": "SMB/Windows Admin Shares",
    "T1021.004": "SSH",
    "T1003": "OS Credential Dumping",
    "T1018": "Remote System Discovery",
}


def eprint(*a: object) -> None:
    print(*a, file=sys.stderr)


def build_query(days: int) -> dict:
    """一条查询拿全部四个数：total / 技术 / 战术 / 未映射。

    技术桶下挂两个子聚合：战术（画出矩阵的“技术属于哪个战术”）与技术名（真名，
    避免只靠本地表猜）。size 60 / 30 远大于实际出现的数量。
    """
    return {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"@timestamp": {"gte": f"now-{days}d", "lte": "now"}}}
                ]
            }
        },
        "aggs": {
            "tech": {
                "terms": {"field": "rule.mitre.id", "size": 60},
                "aggs": {
                    "tac": {"terms": {"field": "rule.mitre.tactic", "size": 30}},
                    "tname": {"terms": {"field": "rule.mitre.technique", "size": 3}},
                },
            },
            "tac": {"terms": {"field": "rule.mitre.tactic", "size": 30}},
            "unmapped": {
                "filter": {"bool": {"must_not": [{"exists": {"field": "rule.mitre.id"}}]}}
            },
        },
    }


def ssh_cmd(host: str, remote: str, key: str = "") -> list:
    cmd = ["ssh"]
    if key:
        cmd += ["-i", key]
    cmd += [
        "-o", "ConnectTimeout=12",
        "-o", "ServerAliveInterval=15",
        "-o", "StrictHostKeyChecking=accept-new",
        host, remote,
    ]
    return cmd


def detect_container(host: str, key: str) -> str:
    remote = "sudo docker ps --format '{{.Names}}' | grep -i indexer | head -1"
    out = subprocess.run(
        ssh_cmd(host, remote, key), capture_output=True, timeout=60
    )
    name = out.stdout.decode("utf-8", "replace").strip()
    if not name:
        raise RuntimeError(
            "srv2 上找不到名字带 indexer 的容器（sudo docker ps 为空？）：\n"
            + out.stderr.decode("utf-8", "replace")
        )
    return name


def fetch(host: str, key: str, container: str, query: dict, user: str, pwd: str, index: str) -> dict:
    body = json.dumps(query, ensure_ascii=False)
    sh_url = f"https://localhost:9200/{index}/_search"
    remote = (
        "sudo docker exec -i " + container + " curl -s -k -u " + shell_quote(f"{user}:{pwd}")
        + " " + shell_quote(sh_url)
        + " -H 'Content-Type: application/json' --data-binary @-"
    )
    cmd = ssh_cmd(host, remote, key)
    eprint("[attack] ssh", host, "→", container, "…")
    p = subprocess.run(cmd, input=body.encode("utf-8"), capture_output=True, timeout=180)
    raw = p.stdout.decode("utf-8", "replace").strip()
    if p.returncode != 0 and not raw:
        raise RuntimeError(
            "ssh/容器调用失败（exit %s）：%s" % (p.returncode, p.stderr.decode("utf-8", "replace")[:800])
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("索引器返回的不是 JSON：\n" + raw[:1000])
    if "error" in data:
        raise RuntimeError("ES 报错：\n" + json.dumps(data["error"], ensure_ascii=False)[:1200])
    return data


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def build_payload(es: dict, days: int) -> dict:
    aggs = es.get("aggregations") or {}
    total = int(((es.get("hits") or {}).get("total") or {}).get("value") or 0)
    unmapped = int((aggs.get("unmapped") or {}).get("doc_count") or 0)

    tech_buckets = (aggs.get("tech") or {}).get("buckets") or []
    tac_buckets = (aggs.get("tac") or {}).get("buckets") or []

    # 战术桶 → 带 TA 号；未知名字保留原名、id 空，页面照样显示（不丢）。
    tactics = []
    for b in tac_buckets:
        name = str(b.get("key"))
        tactics.append(
            {"id": TACTIC_IDS.get(name, ""), "name": name, "count": int(b.get("doc_count") or 0)}
        )
    tactics.sort(key=lambda t: t["count"], reverse=True)

    techniques = []
    for b in tech_buckets:
        tid = str(b.get("key"))
        tname_buckets = ((b.get("tname") or {}).get("buckets") or [])
        builtin = TECH_NAMES.get(tid, "")
        real_name = str(tname_buckets[0]["key"]) if tname_buckets else ""
        # 内置表优先：实测 Wazuh 有规则把 T1021.004 的 technique 名写成 "Password Guessing"
        # （真实名是 SSH），直接采信告警里的名字会把错名搬上页面。表里没有的再退回告警名。
        name = builtin or real_name or tid
        cells = []
        for tb in ((b.get("tac") or {}).get("buckets") or []):
            tname = str(tb.get("key"))
            cells.append(
                {"tactic": TACTIC_IDS.get(tname, tname), "count": int(tb.get("doc_count") or 0)}
            )
        cells.sort(key=lambda c: c["count"], reverse=True)
        techniques.append(
            {
                "id": tid,
                "name": name,
                "count": int(b.get("doc_count") or 0),
                "tactics": [c["tactic"] for c in cells],
                "cells": cells,
            }
        )
    techniques.sort(key=lambda t: t["count"], reverse=True)

    # 格子底色深浅：对数归一化后写进 cells[].alpha（页面只管取用，不再算一次）。
    # 线性映射会让 25 条的格子看不见；log 让 10^0..10^6 四档都能分出来。
    max_c = max((t["count"] for t in techniques), default=1) or 1
    denom = math.log1p(max_c)
    for t in techniques:
        for c in t["cells"]:
            c["alpha"] = round(0.07 + 0.35 * (math.log1p(c["count"]) / denom), 2) if denom else 0.07

    mapped = total - unmapped
    pct = round(mapped * 100.0 / total, 2) if total else 0.0
    now = datetime.now(timezone(timedelta(hours=8)))
    return {
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "windowDays": days,
        "total": total,
        "mapped": mapped,
        "unmapped": unmapped,
        "mappedPct": pct,
        "tactics": tactics,
        "techniques": techniques,
        "source": {
            "system": "Wazuh " + INDEX,
            # 不写 localhost/127.0.0.1：那是容器内网地址，写进公开产物会被误读成"线上接口基址"
            "channel": "ssh " + SSH_HOST + " → docker exec " + ("indexer" if not CONTAINER else CONTAINER)
            + " → curl https://[indexer]:9200",
            "note": "Wazuh 规则未带 mitre.id 的告警计入 unmapped，不计入任何技术。",
        },
    }


def write_outputs(payload: dict, out_js: str, out_data: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    for path in (out_js, out_data):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
        eprint("[attack] 写入", path, len(text.encode("utf-8")), "字节")


def main() -> int:
    global SSH_HOST, CONTAINER
    ap = argparse.ArgumentParser(description="Wazuh → ATT&CK 覆盖快照")
    ap.add_argument("--host", default=os.environ.get("ATTACK_SSH_HOST", SSH_HOST))
    ap.add_argument("--key", default=os.environ.get("ATTACK_SSH_KEY", SSH_KEY))
    ap.add_argument("--container", default=os.environ.get("ATTACK_CONTAINER", CONTAINER))
    ap.add_argument("--index", default=os.environ.get("ATTACK_INDEX", INDEX))
    ap.add_argument("--user", default=os.environ.get("WAZUH_ES_USER", ES_USER))
    ap.add_argument("--password", default=os.environ.get("WAZUH_ES_PASS", ES_PASS))
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--from-json", default="", help="已抓到的 ES 响应（离线重建）")
    ap.add_argument("--out", default="static/api/public/attack.js")
    ap.add_argument("--data-out", default="data/attack.json")
    ap.add_argument("--print", action="store_true", help="只打印 JSON，不写文件")
    args = ap.parse_args()

    SSH_HOST = args.host
    if args.from_json:
        with open(args.from_json, "r", encoding="utf-8-sig") as f:
            es = json.load(f)
        eprint("[attack] 离线重建：", args.from_json)
    else:
        CONTAINER = args.container or detect_container(args.host, args.key)
        es = fetch(args.host, args.key, CONTAINER, build_query(args.days),
                   args.user, args.password, args.index)

    payload = build_payload(es, args.days)
    pct = payload["mappedPct"]
    eprint(
        "[attack] window=%dd total=%d mapped=%d (%.2f%%) unmapped=%d techniques=%d"
        % (payload["windowDays"], payload["total"], payload["mapped"], pct,
           payload["unmapped"], len(payload["techniques"]))
    )
    if args.print:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0
    write_outputs(payload, args.out, args.data_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
