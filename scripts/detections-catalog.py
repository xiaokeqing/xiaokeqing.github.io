#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 detections/ 下的自研规则文件解析成 data/detections.json（构建期一次性产物）。

口径（页面 /detections/ 直接引用本文件，不手填数字）：
  * 只读仓库内文件，不联网、不读线上实例；
  * Suricata 条数 = 规则动作行（alert/pass/drop/reject）数；注释态规则单独标 enabled=false，
    不混进「生效」计数；
  * Wazuh 条数 = <rule id=...> 元素数；
  * 取不到的字段写 null / 空列表，不补 0、不估算；
  * 所有对外字符串统一 sanitize：IPv4 字面量 → x.x.x.x，口令类赋值 → [口令已隐藏]；
  * 输出确定：sort_keys + 固定缩进 + LF + 无时间戳，重复运行字节完全一致（幂等）。

用法：python scripts/detections-catalog.py
"""

import io
import json
import os
import re
import sys

from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRC_SURICATA = os.path.join(ROOT, "detections", "suricata", "xk-lab.rules")
SRC_THRESHOLD = os.path.join(ROOT, "detections", "suricata", "threshold.conf")
SRC_WAZUH = [
    os.path.join(ROOT, "detections", "wazuh", "xk-lab_rules.xml"),
    os.path.join(ROOT, "detections", "wazuh", "cowrie_rules.xml"),
]
OUT = os.path.join(ROOT, "data", "detections.json")

IPV4 = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
SECRET = re.compile(
    r"((?:password|passwd|pwd|\u53e3\u4ee4|\u5bc6\u7801)\s*[=:\uff1a]\s*)"
    r"(?!\[\u53e3\u4ee4\u5df2\u9690\u85cf\])[^\s\uff0c,;\uff1b\uff09)]+",
    re.IGNORECASE,
)

RULE_START = re.compile(
    r"^\s*(#\s*)?(alert|pass|drop|reject)\s+(tcp|udp|icmp|ip|http|ssh|dns|tls|any|flow)\b"
)
RULE_HEAD = re.compile(
    r"^(alert|pass|drop|reject)\s+(\S+)\s+(\S+)\s+(\S+)\s+(->|<>)\s+(\S+)\s+(\S+)\s*\("
)
TRACK = {"by_src": "\u540c\u6e90", "by_dst": "\u540c\u76ee\u6807", "by_both": "\u540c\u6e90+\u540c\u76ee\u6807"}
TITLE_SURICATA = re.compile(r"^#\s*(\d{6,7})\s{1,3}(\S.*)$")
TITLE_WAZUH = re.compile(r"^\s+(\d{6})\s{2,}(\S.*)$")


def sanitize(value):
    """对外字符串统一脱敏：IP 字面量 / 口令赋值。"""
    if not isinstance(value, str):
        return value
    out = IPV4.sub("x.x.x.x", value)
    out = SECRET.sub("\\1[\u53e3\u4ee4\u5df2\u9690\u85cf]", out)
    return out


def sanitize_tree(obj):
    if isinstance(obj, str):
        return sanitize(obj)
    if isinstance(obj, list):
        return [sanitize_tree(v) for v in obj]
    if isinstance(obj, dict):
        return dict((k, sanitize_tree(v)) for k, v in obj.items())
    return obj


def read_text(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def parse_metadata(raw):
    """metadata:xk_lab evidence_count 41, confidence high;  ->  {evidence_count: 41, ...}"""
    if not raw:
        return {}
    body = raw.strip()
    if body.startswith("xk_lab "):
        body = body[len("xk_lab "):]
    meta = {}
    for chunk in body.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(None, 1)
        if len(parts) == 2:
            meta[parts[0]] = parts[1].strip()
        elif len(parts) == 1:
            meta[parts[0]] = ""
    return meta


def title_map_suricata(lines):
    titles = {}
    for line in lines:
        hit = TITLE_SURICATA.match(line)
        if hit:
            sid = int(hit.group(1))
            if sid not in titles:
                titles[sid] = hit.group(2).strip()
    return titles


def title_map_wazuh(lines):
    titles = {}
    for line in lines:
        hit = TITLE_WAZUH.match(line)
        if hit:
            rid = int(hit.group(1))
            if rid not in titles:
                titles[rid] = hit.group(2).strip()
    return titles


def observable_suricata(text, proto, dport, has_flags_s, action):
    if "ssh.software" in text:
        return "SSH 客户端 banner\uff08ssh.software\uff09"
    if "http.uri" in text:
        return "HTTP 请求路径\uff08http.uri\uff09"
    if "http.user_agent" in text:
        return "HTTP User-Agent\uff08http.user_agent\uff09"
    if action == "pass":
        return "\u51fa\u7ad9 %s \u2192 \u76ee\u6807\u7aef\u53e3 %s\uff08flow:established\uff09" % (
            proto.upper(),
            dport,
        )
    if has_flags_s and dport != "any":
        return "%s \u76ee\u6807\u7aef\u53e3 %s \u7684 SYN" % (proto.upper(), dport)
    if dport != "any":
        return "%s \u76ee\u6807\u7aef\u53e3 %s" % (proto.upper(), dport)
    return proto.upper()


def parse_suricata():
    text = read_text(SRC_SURICATA)
    lines = text.splitlines()
    titles = title_map_suricata(lines)

    rules = []
    i = 0
    while i < len(lines):
        hit = RULE_START.match(lines[i])
        if not hit:
            i += 1
            continue
        commented = bool(hit.group(1))
        buf = [re.sub(r"^\s*#\s?", "", lines[i]) if commented else lines[i]]
        while not buf[-1].rstrip().endswith(")") and i + 1 < len(lines):
            i += 1
            nxt = lines[i]
            if commented:
                nxt = re.sub(r"^\s*#\s?", "", nxt)
            buf.append(nxt)
        joined = " ".join(part.strip().rstrip("\\").strip() for part in buf)
        i += 1

        head = RULE_HEAD.match(joined)
        if not head:
            continue
        action, proto, _src, _sport, _dir, dst, dport = head.groups()

        msg = re.search(r'msg:"(.*?)"\s*;', joined)
        sid = re.search(r"\bsid\s*:\s*(\d+)\s*;", joined)
        rev = re.search(r"\brev\s*:\s*(\d+)\s*;", joined)
        classtype = re.search(r"classtype\s*:\s*([A-Za-z0-9_.\-]+)\s*;", joined)
        metadata = re.search(r"metadata\s*:\s*(.*?)\s*;", joined)
        threshold = re.search(
            r"threshold\s*:\s*type\s+(\w+)\s*,\s*track\s+(\w+)\s*,"
            r"\s*count\s+(\d+)\s*,\s*seconds\s+(\d+)\s*;",
            joined,
        )
        if not sid:
            continue
        sid_i = int(sid.group(1))
        mitre = sorted(set(re.findall(r"\bmitre\s+([A-Z]\d{3}(?:\.\d{3})?)", joined)))

        th = None
        if threshold:
            th = {
                "type": threshold.group(1),
                "track": threshold.group(2),
                "count": int(threshold.group(3)),
                "seconds": int(threshold.group(4)),
            }

        sev = classtype.group(1) if classtype else None
        rev_i = int(rev.group(1)) if rev else None
        sev_bits = []
        if sev:
            sev_bits.append(sev)
        if rev_i is not None:
            sev_bits.append("rev %d" % rev_i)
        if th:
            sev_bits.append(
                "\u9608\u503c %d/%ds\uff08%s\uff09"
                % (th["count"], th["seconds"], TRACK.get(th["track"], th["track"]))
            )

        rules.append(
            {
                "engine": "suricata",
                "sid": sid_i,
                "action": action,
                "enabled": not commented,
                "status": "commented" if commented else "enabled",
                "msg": sanitize(msg.group(1)) if msg else None,
                "topic": sanitize(titles.get(sid_i)),
                "classtype": sev,
                "rev": rev_i,
                "threshold": th,
                "metadata": parse_metadata(metadata.group(1) if metadata else ""),
                "mitre": mitre,
                "observable": observable_suricata(
                    joined, proto, dport, "flags:S" in joined or "flags: S" in joined, action
                ),
                "severity": " \u00b7 ".join(sev_bits) if sev_bits else None,
                "attack": ", ".join(mitre) if mitre else None,
                "proto": proto,
                "dst_port": dport,
                "dst": sanitize(dst),
            }
        )

    rules.sort(key=lambda r: r["sid"])
    active = [r for r in rules if r["enabled"]]
    classified = {}
    for r in rules:
        if r["classtype"]:
            classified[r["classtype"]] = classified.get(r["classtype"], 0) + 1

    summary = {
        "total": len(rules),
        "alert": len([r for r in rules if r["action"] == "alert" and r["enabled"]]),
        "pass": len([r for r in rules if r["action"] == "pass"]),
        "enabled": len(active),
        "commented": len([r for r in rules if not r["enabled"]]),
        "sid_min": min(r["sid"] for r in active) if active else None,
        "sid_max": max(r["sid"] for r in active) if active else None,
        "sid_min_all": min(r["sid"] for r in rules) if rules else None,
        "sid_max_all": max(r["sid"] for r in rules) if rules else None,
        "with_mitre": len([r for r in rules if r["mitre"]]),
        "with_threshold": len([r for r in rules if r["threshold"]]),
        "classtypes": classified,
    }
    return {"file": rel(SRC_SURICATA), "summary": summary, "rules": rules}


def parse_threshold_conf():
    text = read_text(SRC_THRESHOLD)
    active = 0
    commented = 0
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^suppress\s+", stripped):
            active += 1
        elif re.match(r"^#\s*suppress\s+", stripped):
            commented += 1
    return {"file": rel(SRC_THRESHOLD), "active": active, "commented": commented}


def clean_eventid(raw):
    if not raw:
        return None
    out = raw.strip()
    if out.startswith("^"):
        out = out[1:]
    if out.endswith("$"):
        out = out[:-1]
    return out.replace("\\", "")


RULE_BLOCK = re.compile(r"<rule\b([^>]*)>(.*?)</rule>", re.S)
ATTR = re.compile(r'([A-Za-z_][\w.-]*)="([^"]*)"')
TAG_TEXT = re.compile(r"<([a-z_][\w.-]*)\b[^>]*>(.*?)</\1>", re.S)


def parse_wazuh():
    """Wazuh 规则文件是片段 + 注释里带 `----`（严格 XML 不允许 `--`），
    所以不用 ElementTree：先剥注释，再按 <rule> 块取标签文本。"""
    rules = []
    per_file = {}
    for path in SRC_WAZUH:
        text = read_text(path)
        titles = title_map_wazuh(text.splitlines())
        body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        count = 0
        for attrs_raw, inner in RULE_BLOCK.findall(body):
            attrs = dict(ATTR.findall(attrs_raw))
            rid = attrs.get("id")
            if not rid:
                continue
            rid_i = int(rid)
            tags = {}
            for name, value in TAG_TEXT.findall(inner):
                tags.setdefault(name, value)
            desc = (tags.get("description") or "").strip()
            eventid = None
            credentials = False
            for fm in re.finditer(r'<field\s+name="([^"]+)"\s*>(.*?)</field>', inner, re.S):
                fname = fm.group(1)
                fval = (fm.group(2) or "").strip()
                if fname == "eventid":
                    eventid = clean_eventid(fval)
                elif fname == "credentials":
                    credentials = True
            parent_sid = [
                (tags.get(k) or "").strip()
                for k in ("if_matched_sid", "if_sid")
                if (tags.get(k) or "").strip()
            ]
            parent_group = [
                (tags.get(k) or "").strip()
                for k in ("if_matched_group",)
                if (tags.get(k) or "").strip()
            ]
            mitre = sorted(
                set(
                    (m.group(1) or "").strip()
                    for m in re.finditer(r"<id>(.*?)</id>", inner, re.S)
                    if (m.group(1) or "").strip()
                )
            )
            level = int(attrs["level"]) if attrs.get("level") else None
            freq = int(attrs["frequency"]) if attrs.get("frequency") else None
            tf = int(attrs["timeframe"]) if attrs.get("timeframe") else None

            obs_parts = []
            if eventid:
                obs_parts.append("Cowrie \u4e8b\u4ef6 %s" % eventid)
            if credentials:
                obs_parts.append("\u5b57\u6bb5 credentials")
            for sid in parent_sid:
                obs_parts.append("\u7236\u89c4\u5219 %s" % sid)
            for grp in parent_group:
                obs_parts.append("\u7236\u7ec4 %s" % grp)

            sev_bits = []
            if level is not None:
                sev_bits.append("L%d" % level)
            if freq is not None and tf is not None:
                sev_bits.append("%d \u6b21/%ds" % (freq, tf))

            rules.append(
                {
                    "engine": "wazuh",
                    "sid": rid_i,
                    "enabled": True,
                    "msg": sanitize(desc),
                    "topic": sanitize(titles.get(rid_i)),
                    "level": level,
                    "frequency": freq,
                    "timeframe": tf,
                    "mitre": mitre,
                    "observable": " \u00b7 ".join(obs_parts) if obs_parts else "\u672a\u53d6\u5230",
                    "severity": " \u00b7 ".join(sev_bits) if sev_bits else None,
                    "attack": ", ".join(mitre) if mitre else None,
                    "file": rel(path),
                }
            )
            count += 1
        per_file[rel(path)] = count

    rules.sort(key=lambda r: r["sid"])
    levels = {}
    for r in rules:
        key = str(r["level"]) if r["level"] is not None else "unknown"
        levels[key] = levels.get(key, 0) + 1
    mitre_ids = sorted(set(m for r in rules for m in r["mitre"]))

    summary = {
        "total": len(rules),
        "files": len(per_file),
        "per_file": per_file,
        "sid_min": min(r["sid"] for r in rules) if rules else None,
        "sid_max": max(r["sid"] for r in rules) if rules else None,
        "with_mitre": len([r for r in rules if r["mitre"]]),
        "levels": levels,
        "mitre_ids": mitre_ids,
    }
    return {"summary": summary, "rules": rules}


def main():
    suricata = parse_suricata()
    wazuh = parse_wazuh()
    payload = {
        "schema": 1,
        "sources": [suricata["file"]] + [rel(p) for p in SRC_WAZUH],
        "suricata": suricata,
        "wazuh": wazuh,
        "threshold_conf": parse_threshold_conf(),
        "generator": "scripts/detections-catalog.py",
    }
    payload = sanitize_tree(payload)
    payload["sums"] = {
        "rules_total": suricata["summary"]["alert"] + wazuh["summary"]["total"],
        "suricata_alert": suricata["summary"]["alert"],
        "wazuh_total": wazuh["summary"]["total"],
        "with_mitre": suricata["summary"]["with_mitre"] + wazuh["summary"]["with_mitre"],
    }

    out_dir = os.path.dirname(OUT)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(data)
        fh.write(u"\n")

    print(
        "detections.json: suricata alert=%d (enabled=%d, commented=%d), "
        "wazuh=%d (mitre=%d) -> %s"
        % (
            suricata["summary"]["alert"],
            suricata["summary"]["enabled"],
            suricata["summary"]["commented"],
            wazuh["summary"]["total"],
            wazuh["summary"]["with_mitre"],
            rel(OUT),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
