#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATT&CK 覆盖率快照 —— Wazuh（mitre 字段）+ Suricata（人工 category→战术对照）。

两部分互相独立，条数**不可相加**（两套告警源，口径不同）：
  · Wazuh    —— 按 mitre.id / mitre.tactic 聚合，未映射 = 没有 mitre.id 的告警；
  · Suricata —— 只按 alert.category 聚合，再用本文件的显式对照表映射战术。
                Suricata 不输出 ATT&CK 字段，所以这张表是**人工对照**：
                表里没有 / 留空的 category 一律进未映射桶，绝不按签名关键词猜。
                srv2 取数失败只让 suricata.available=false，整页照常构建。

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
  python scripts/attack-coverage.py                     # 取数（Wazuh + Suricata）并写两份产物
  python scripts/attack-coverage.py --from-json a.json  # 用已抓到的 ES 响应重建产物（离线）
  python scripts/attack-coverage.py --from-json a.json --suricata-from-json s.json  # 全离线
  python scripts/attack-coverage.py --print             # 只打印，不写文件
"""

from __future__ import annotations

import argparse
import base64
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
SURICATA_LOGS = "/opt/suricata/logs"  # srv2 宿主机目录（容器外直读，不需要 docker exec）
SURICATA_EVE = "eve.json"

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

# ---- Suricata：alert.category → 战术（人工对照表，改之前先读依据）-------------
# 数据：srv2 的 /opt/suricata/logs/eve.json*，只取 event_type=alert。
# Suricata 不输出 ATT&CK 字段；alert.category 就是 classification.config 里
# classtype 的 description（不是原始 classtype 名），所以这张表按 description 写。
# 规则只有一条：**不能从 category 语义直接读出战术的，值写空串 = 未映射**。
# 不做签名关键词二次分配：同一个 category 下签名一混，拆出来的数就是猜的。
SURICATA_CATEGORY_TACTIC = {
    # attempted-recon。实测签名全是 internet → 蜜罐的入站动作：SSH 客户端指纹、
    # 多诱饵端口扫描、数据库端口探测、ssh 扫描。这是攻击发生前的侦察（TA0043），
    # 不是 Collection/Discovery —— 后两者是"已经进内网"之后的动作。
    "Attempted Information Leak": "Reconnaissance",
    # Zmap User-Agent 等扫描器特征从外部打进来，同上属外部侦察。
    "Detection of a Network Scan": "Reconnaissance",
    # info-leak。实测 6 条全是 "ET WEB_SERVER WEB-PHP phpinfo access"：
    # phpinfo 页直接回显 PHP 配置/路径/模块，攻击者据此了解目标环境 → Discovery。
    "Information Leak": "Discovery",
    # attempted-admin。实测含 Dell UnityVSA 预认证命令注入（CVE-2025-36604），
    # 目标是拿管理员权限 → Privilege Escalation。
    "Attempted Administrator Privilege Gain": "Privilege Escalation",
    # attempted-user。与 admin 同族、只是目标权限级别更低，仍属提权。
    "Attempted User Privilege Gain": "Privilege Escalation",
    # web-application-attack。实测是 URI 里的 /bin/sh 命令注入、webshell wget 上传，
    # 都是利用对外 Web 服务打进来 → Initial Access。
    "Web Application Attack": "Initial Access",
    # trojan-activity。网络木马/后门通信特征 → Command and Control。
    "A Network Trojan was detected": "Command and Control",
    # ---- 以下显式留空 = 未映射（不是漏写）------------------------------------
    # ET INFO / USER_AGENTS 之类的信息类签名（ssh 版本串、Go UA），没有攻击阶段语义。
    "Misc activity": "",
    # DROP/Spamhaus/CINS 信誉名单命中：只知道"来源 IP 坏"，不知道攻击者想干什么。
    "Misc Attack": "",
    # 实测同一 category 里既有"可疑 MSSQL/MySQL 端口入站扫描"又有"webshell wget 上传"，
    # 一条 category 横跨侦察与初始访问；摊进任一战术都是编，整桶单列。
    "Potentially Bad Traffic": "",
    # SURICATA STREAM/HTTP/TLS 解析异常：引擎的协议观察，不是攻击阶段。
    "Generic Protocol Command Decode": "",
    # 字面意思：Not Suspicious。
    "Not Suspicious Traffic": "",
    # eve.json 里确有 2 条告警 alert.category 为空；空值只能是未映射。
    "": "",
}

# 未映射 category 的页面上的一句话依据（不参与计数，只用来解释"为什么不摊派"）
SURICATA_UNMAPPED_WHY = {
    "Misc activity": "信息类签名（SSH 版本串/Go UA），无攻击阶段语义",
    "Misc Attack": "DROP/Spamhaus/CINS 信誉名单命中，只知道来源坏",
    "Potentially Bad Traffic": "同桶混有端口扫描与 webshell 上传，跨战术不摊派",
    "Generic Protocol Command Decode": "STREAM/HTTP 解析异常，是引擎观察不是攻击阶段",
    "Not Suspicious Traffic": "签名自述非可疑，不映射",
    "": "告警本身没有 category 字段",
}

# 远端聚合程序：只输出一行 JSON，正文（eve.json）不落到本机，避免 300 MB 级传输。
# 由本脚本 base64 后经 ssh 喂给 srv2 的 python3；改这里等于改线上取数口径。
REMOTE_AGG_PY = r'''
import argparse, glob, gzip, json, os
from datetime import datetime, timezone, timedelta

ap = argparse.ArgumentParser()
ap.add_argument("--dir", default="/opt/suricata/logs")
ap.add_argument("--days", type=int, default=7)
ap.add_argument("--max-bytes", type=int, default=2048 * 1024 * 1024)
a = ap.parse_args()

cutoff = datetime.now(timezone.utc) - timedelta(days=a.days)
files = sorted(glob.glob(os.path.join(a.dir, "eve.json*")), key=os.path.getmtime, reverse=True)
cats = {}
n = 0
tmin = tmax = None
scanned = 0
used = []
for path in files:
    try:
        st = os.stat(path)
    except OSError:
        continue
    if st.st_mtime < cutoff.timestamp():
        continue
    if used and scanned >= a.max_bytes:
        break
    used.append(os.path.basename(path))
    op = gzip.open if path.endswith(".gz") else open
    try:
        fh = op(path, "rt", encoding="utf-8", errors="replace")
    except OSError:
        continue
    with fh:
        for line in fh:
            scanned += len(line)
            if '"event_type":"alert"' not in line and '"event_type": "alert"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("event_type") != "alert":
                continue
            ts = d.get("timestamp") or ""
            if len(ts) >= 19:
                try:
                    dt = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                    if dt < cutoff:
                        continue
                except ValueError:
                    pass
            a_ = d.get("alert") or {}
            c = a_.get("category") or ""
            cats[c] = cats.get(c, 0) + 1
            if ts:
                tmin = ts if tmin is None or ts < tmin else tmin
                tmax = ts if tmax is None or ts > tmax else tmax
            n += 1
    if scanned >= a.max_bytes:
        break

print(json.dumps({
    "total": n, "from": tmin or "", "to": tmax or "",
    "bytes": scanned, "files": used, "categories": cats,
}, ensure_ascii=False, sort_keys=True))
'''


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


# ---- Suricata 取数 ----------------------------------------------------------
def fetch_suricata(host: str, key: str, days: int, max_mb: int, logs_dir: str) -> dict:
    """把聚合程序经 base64 喂给 srv2 的 python3，只回传一行 JSON。

    读宿主机 /opt/suricata/logs/eve.json*（含轮转件 .gz），不需要 docker exec：
    这些文件宿主机用户可直读。时间窗仍按 7 天过滤；日志保留不足 7 天时以实际为准。
    """
    py = REMOTE_AGG_PY.strip()
    b64 = base64.b64encode(py.encode("utf-8")).decode("ascii")
    remote = (
        "echo " + shell_quote(b64) + " | base64 -d > /tmp/.attack-suricata-agg.py && "
        "python3 /tmp/.attack-suricata-agg.py"
        " --dir " + shell_quote(logs_dir)
        + " --days " + str(int(days))
        + " --max-bytes " + str(int(max_mb) * 1024 * 1024)
    )
    eprint("[attack] ssh", host, "→ Suricata", logs_dir, "(最近 %d 天) …" % days)
    p = subprocess.run(ssh_cmd(host, remote, key), capture_output=True, timeout=420)
    out = p.stdout.decode("utf-8", "replace").strip()
    err = p.stderr.decode("utf-8", "replace").strip()
    if p.returncode != 0 or not out:
        raise RuntimeError(
            "ssh/python3 聚合失败（exit %s）：%s" % (p.returncode, (err or out)[:500])
        )
    try:
        raw = json.loads(out.splitlines()[-1])
    except json.JSONDecodeError:
        raise RuntimeError("Suricata 聚合返回的不是 JSON：\n" + out[:500])
    if not isinstance(raw, dict) or "categories" not in raw:
        raise RuntimeError("Suricata 聚合返回缺 categories 字段：\n" + out[:500])
    return raw


def load_suricata_cache(path: str) -> dict:
    """读离线缓存。兼容远端聚合格式（categories {...}）与上一版产物（byCategory [...]）。"""
    with open(path, "r", encoding="utf-8-sig") as f:
        raw = json.load(f)
    if isinstance(raw, dict) and "suricata" in raw:
        raw = raw["suricata"]
    if not isinstance(raw, dict):
        raise RuntimeError("Suricata 缓存不是 JSON 对象")
    if "categories" not in raw and "byCategory" in raw:
        raw = dict(raw)
        raw["categories"] = {
            str(e.get("category") or ""): int(e.get("count") or 0)
            for e in (raw.get("byCategory") or [])
        }
    if "categories" not in raw:
        raise RuntimeError("Suricata 缓存缺 categories / byCategory")
    return raw


def _bj_time(ts: str) -> str:
    """eve.json 的 UTC 时间（+0000）→ 北京时间字符串；解析不了一律原样返回。"""
    if not ts:
        return ""
    try:
        dt = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return (dt + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ts


def _sanitize(s: str) -> str:
    # 页面全站断言禁止 localhost 作为接口基址；错误文本里出现也一并换掉，免得上页。
    return (s or "").replace("localhost", "本机").replace("Localhost", "本机")


def build_suricata(raw: dict | None, days: int, reason: str = "") -> dict:
    """把远端聚合(或离线缓存)变成页面块；取不到数时 available=false，不抛。"""
    mapping_n = len(SURICATA_CATEGORY_TACTIC)
    mapped_n = sum(1 for v in SURICATA_CATEGORY_TACTIC.values() if v)
    if not raw:
        return {
            "available": False,
            "reason": _sanitize(reason) or "未取到 Suricata 数据",
            "windowDays": days,
            "total": 0,
            "mapped": 0,
            "unmapped": 0,
            "mappedPct": 0.0,
            "byCategory": [],
            "tactics": [],
            "unmappedCategories": [],
            "note": "Suricata 取数失败时本块不显示任何数字；上下两块互相独立，整页不因此失败。",
        }

    raw_cats = raw.get("categories") or {}
    cats: dict[str, int] = {}
    for k, v in raw_cats.items():
        cats[str(k or "")] = cats.get(str(k or ""), 0) + int(v or 0)

    by_category = []
    grouped: dict[str, dict] = {}
    unmapped = 0
    unmapped_cats = []
    total = 0
    for cat, count in cats.items():
        if count <= 0:
            continue
        total += count
        tactic_name = SURICATA_CATEGORY_TACTIC.get(cat, "")
        tid = TACTIC_IDS.get(tactic_name, "") if tactic_name else ""
        if tid:
            row = {
                "category": cat,
                "count": count,
                "tactic": tid,
                "tacticName": tactic_name,
                "mapped": True,
            }
            g = grouped.setdefault(tid, {
                "id": tid, "name": tactic_name, "count": 0, "categories": []
            })
            g["count"] += count
            g["categories"].append({"category": cat, "count": count})
        else:
            unmapped += count
            why = SURICATA_UNMAPPED_WHY.get(cat) or "不在人工对照表里（新增 category，未评估）"
            row = {
                "category": cat,
                "count": count,
                "tactic": "",
                "tacticName": "",
                "mapped": False,
                "why": why,
            }
            unmapped_cats.append({"category": cat, "count": count, "why": why})
        by_category.append(row)
    by_category.sort(key=lambda r: r["count"], reverse=True)
    unmapped_cats.sort(key=lambda r: r["count"], reverse=True)

    tactics = sorted(grouped.values(), key=lambda t: t["count"], reverse=True)
    for t in tactics:
        t["categories"].sort(key=lambda c: c["count"], reverse=True)

    mapped = total - unmapped
    pct = round(mapped * 100.0 / total, 2) if total else 0.0
    files = raw.get("files") or []
    scanned = int(raw.get("bytes") or 0)
    from_bj = _bj_time(str(raw.get("from") or ""))
    to_bj = _bj_time(str(raw.get("to") or ""))
    coverage = ""
    if from_bj and to_bj:
        try:
            d0 = datetime.strptime(from_bj, "%Y-%m-%d %H:%M")
            d1 = datetime.strptime(to_bj, "%Y-%m-%d %H:%M")
            span = (d1 - d0).total_seconds() / 86400.0
        except ValueError:
            span = 0.0
        coverage = (
            "窗口 %d 天；可读日志 %d 个文件（约 %.2f GB），实际覆盖 %s → %s（约 %.1f 天）"
            % (days, len(files), scanned / (1024.0 ** 3), from_bj, to_bj, span)
        )
    note = (
        "Suricata 没有 ATT&CK 字段：本块是 %d 条 category 的人工对照"
        "（%d 条映射到 %d 个战术），表外/留空的 category 一律进未映射；"
        "与上面 Wazuh 是两套数据源，条数不可相加。"
        % (mapping_n, mapped_n, len({v for v in SURICATA_CATEGORY_TACTIC.values() if v}))
    )
    return {
        "available": True,
        "reason": "",
        "windowDays": days,
        "total": total,
        "mapped": mapped,
        "unmapped": unmapped,
        "mappedPct": pct,
        "byCategory": by_category,
        "tactics": tactics,
        "unmappedCategories": unmapped_cats,
        "observedFrom": from_bj,
        "observedTo": to_bj,
        "files": len(files),
        "bytes": scanned,
        "coverage": coverage,
        "note": note,
        "source": {
            "system": "Suricata " + SURICATA_EVE + "*",
            # 写明宿主路径，但不写任何会触发 localhost 断言的地址
            "channel": "ssh " + SSH_HOST + " → 直读 " + SURICATA_LOGS + "/" + SURICATA_EVE + "*",
            "table": "scripts/attack-coverage.py 的 SURICATA_CATEGORY_TACTIC（人工对照 %d 条）"
            % mapping_n,
        },
    }


def build_payload(es: dict, days: int, suricata: dict | None = None) -> dict:
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
        # 向后兼容：Wazuh 的原字段一个没动，只在顶层追加这一块
        "suricata": suricata or build_suricata(None, days, "未取到 Suricata 数据"),
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
    ap.add_argument("--suricata-from-json", default="",
                    help="Suricata 聚合结果/缓存（离线重建；缺省时 suricata.available=false）")
    ap.add_argument("--suricata-logs", default=os.environ.get("ATTACK_SURICATA_LOGS", SURICATA_LOGS))
    ap.add_argument("--suricata-max-mb", type=int, default=2048,
                    help="Suricata 取数最多读多少 MB（按解压后计，默认 2048）")
    ap.add_argument("--no-suricata", action="store_true", help="跳过 Suricata 取数（整块降级）")
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

    # Suricata 是"加分块"：任何失败都只降级成 available=false，绝不让整页失败。
    suricata_raw = None
    sur_reason = ""
    if args.suricata_from_json:
        try:
            suricata_raw = load_suricata_cache(args.suricata_from_json)
            eprint("[attack] Suricata 离线缓存：", args.suricata_from_json)
        except Exception as e:  # noqa: BLE001 —— 取不到就降级，不中断构建
            sur_reason = "离线缓存读取失败：%s" % e
    elif args.from_json:
        sur_reason = "离线重建（--from-json）未提供 --suricata-from-json，本次不取 Suricata"
    elif args.no_suricata:
        sur_reason = "本次以 --no-suricata 跳过取数"
    else:
        try:
            suricata_raw = fetch_suricata(
                args.host, args.key, args.days, args.suricata_max_mb, args.suricata_logs
            )
        except Exception as e:  # noqa: BLE001 —— 同上
            sur_reason = "srv2 取数失败：%s" % e

    suricata = build_suricata(suricata_raw, args.days, sur_reason)
    payload = build_payload(es, args.days, suricata)
    pct = payload["mappedPct"]
    eprint(
        "[attack] window=%dd total=%d mapped=%d (%.2f%%) unmapped=%d techniques=%d"
        % (payload["windowDays"], payload["total"], payload["mapped"], pct,
           payload["unmapped"], len(payload["techniques"]))
    )
    if suricata["available"]:
        eprint(
            "[attack] suricata total=%d mapped=%d (%.2f%%) unmapped=%d tactics=%d categories=%d"
            % (suricata["total"], suricata["mapped"], suricata["mappedPct"],
               suricata["unmapped"], len(suricata["tactics"]), len(suricata["byCategory"]))
        )
    else:
        eprint("[attack] suricata 未取到：", suricata["reason"])
    if args.print:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0
    write_outputs(payload, args.out, args.data_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
