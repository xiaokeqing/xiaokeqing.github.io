#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 /hunters/ 的追踪卡快照（data/hunters.json）。

数据源（只读）：
  static/api/public/stories.js        主数据：data.sources[]，四阶段计数
  static/api/public/alerts.js         24h 总量 / 分级，页头口径
  static/api/public/ip/<ip>.js        可选：独立 IP 档案（窗口通常 168h），只做补充

规则：
  * 排序键 = sum(stages.alerts, stages.decoyPorts, stages.honeypotLogins,
    stages.auditActions) 降序；并列时 alerts 降序、srcIp 升序。
  * 取前 5 个（页面展示上限）；快照接口自己还有 data.limit 个源的上限。
  * 展示用 IP 一律打码：保留前两段，后两段换成 xx。
  * 缺口 stages 不补 0：stageList 里 hasData=false，页面显示「未取到」。
  * 幂等：同样的输入产生逐字节相同的输出；内容没变就不重写文件。

用法：python scripts/hunters-dossiers.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "static" / "api" / "public" / "stories.js"
ALERTS = ROOT / "static" / "api" / "public" / "alerts.js"
IP_DIR = ROOT / "static" / "api" / "public" / "ip"
OUT = ROOT / "data" / "hunters.json"

STAGE_ORDER = ["alerts", "decoyPorts", "honeypotLogins", "auditActions"]
STAGE_LABELS = {
    "alerts": "告警",
    "decoyPorts": "诱饵端口",
    "honeypotLogins": "蜜罐登录",
    "auditActions": "处置审计",
}
DISPLAY_LIMIT = 5


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def stage_sum(src: dict) -> int:
    stages = src.get("stages") or {}
    return sum(int(stages.get(k) or 0) for k in STAGE_ORDER)


def mask_ip(ip: str) -> str:
    """保留前两段，后两段换成 xx（IPv4）。"""
    parts = str(ip).split(".")
    if len(parts) == 4:
        return "%s.%s.xx.xx" % (parts[0], parts[1])
    # 非 IPv4 的兜底：只留前 1/3，其余打码，绝不整段露出。
    text = str(ip)
    keep = max(1, len(text) // 3)
    return text[:keep] + "…"


def fmt_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def load_dossier(ip: str) -> dict | None:
    """独立 IP 档案只在文件存在时读取；窗口可能不是 24h，必须原样标注。"""
    path = IP_DIR / ("%s.js" % ip)
    if not path.is_file():
        return None
    try:
        data = load_json(path).get("data") or {}
    except (ValueError, OSError):
        return None
    if not data.get("available"):
        return None

    ports = []
    for item in data.get("ports") or []:
        try:
            ports.append({"port": fmt_int(item.get("port")), "count": fmt_int(item.get("count"))})
        except AttributeError:
            continue
    ports.sort(key=lambda p: (-p["count"], p["port"]))

    kinds = []
    for name, count in (data.get("byKind") or {}).items():
        kinds.append({"name": str(name), "count": fmt_int(count)})
    kinds.sort(key=lambda k: (-k["count"], k["name"]))

    return {
        "generatedAt": data.get("generatedAt"),
        "window": data.get("window"),
        "windowHours": fmt_int(data.get("windowHours")),
        "events": fmt_int(data.get("events")),
        "ports": ports,
        "byKind": kinds,
    }


def build() -> dict:
    payload = load_json(STORIES)
    data = payload.get("data") or {}
    if not data.get("available"):
        raise SystemExit("stories.js: data.available is false; refusing to build a page from no data")

    stage_labels = dict(STAGE_LABELS)
    stage_labels.update({k: v for k, v in (data.get("stageLabels") or {}).items() if v})

    sources = list(data.get("sources") or [])
    ranked = sorted(
        sources,
        key=lambda s: (
            -stage_sum(s),
            -fmt_int((s.get("stages") or {}).get("alerts")),
            str(s.get("srcIp") or ""),
        ),
    )
    top = ranked[:DISPLAY_LIMIT]

    hunters = []
    for rank, src in enumerate(top, start=1):
        stages = src.get("stages") or {}
        gaps = [k for k in STAGE_ORDER if k in (src.get("gaps") or [])]
        gap_set = set(gaps)

        stage_list = []
        for key in STAGE_ORDER:
            count = fmt_int(stages.get(key))
            stage_list.append(
                {
                    "key": key,
                    "label": stage_labels.get(key, key),
                    "count": count,
                    "hasData": key not in gap_set,
                }
            )

        covered = [s for s in stage_list if s["hasData"]]
        missing_labels = [stage_labels.get(k, k) for k in STAGE_ORDER if k in gap_set]
        n = len(covered)
        if n >= len(STAGE_ORDER):
            conclusion = "四阶段走通 4 段，四段都有记录。"
        else:
            tail = "（该阶段无记录）" if len(missing_labels) == 1 else "（均无记录）"
            conclusion = "四阶段走通 %d 段，缺%s%s。" % (n, "、".join(missing_labels), tail)

        coverage_text = "；".join(
            "%s%s" % (s["label"], "有记录" if s["hasData"] else "未取到") for s in stage_list
        )
        gap_text = "、".join("%s：无记录" % lab for lab in missing_labels)

        hunters.append(
            {
                "rank": rank,
                "srcIp": str(src.get("srcIp") or ""),
                "ipMasked": mask_ip(src.get("srcIp") or ""),
                "severityMax": str(src.get("severityMax") or ""),
                "severityMaxLabel": str(src.get("severityMaxLabel") or src.get("severityMax") or "未取到"),
                "stages": {k: fmt_int(stages.get(k)) for k in STAGE_ORDER},
                "stageList": stage_list,
                "stagesWithData": fmt_int(src.get("stagesWithData") or n),
                "stageTotal": stage_sum(src),
                "firstSeen": str(src.get("firstSeen") or "未取到"),
                "lastSeen": str(src.get("lastSeen") or "未取到"),
                "gaps": gaps,
                "gapText": gap_text,
                "coverageText": coverage_text,
                "conclusion": conclusion,
                "dossier": load_dossier(str(src.get("srcIp") or "")),
            }
        )

    stats24h = {"available": False}
    alerts_generated_at = None
    if ALERTS.is_file():
        try:
            adata = load_json(ALERTS).get("data") or {}
            stats24h = dict(adata.get("stats24h") or {"available": False})
            alerts_generated_at = adata.get("generatedAt")
        except (ValueError, OSError):
            stats24h = {"available": False}

    meta = {
        "script": "scripts/hunters-dossiers.py",
        "generatedAt": data.get("generatedAt"),
        "window": data.get("window"),
        "windowHours": fmt_int(data.get("windowHours")),
        "candidates": fmt_int(data.get("candidates")),
        "sourceCount": fmt_int(data.get("sourceCount") or len(sources)),
        "limit": fmt_int(data.get("limit")),
        "displayLimit": DISPLAY_LIMIT,
        "selected": len(hunters),
        "stageOrder": STAGE_ORDER,
        "stageLabels": stage_labels,
        "sortKey": "sum(stages.alerts + decoyPorts + honeypotLogins + auditActions) 降序；并列时告警数降序、IP 升序",
        "stats24h": stats24h,
        "alertsGeneratedAt": alerts_generated_at,
        "notes": [
            "这是自动挑选，不是人工认定；排序只看四阶段的记录数，不评价动机。",
            "缺口字段显示「未取到」，不补 0；没记录不等于没发生。",
            "页面展示的 IP 一律打码，完整 IP 只出现在 /ip/?q= 的链接参数里。",
            "独立 IP 档案的窗口可能是 168h，与上方 24h 四阶段不同口径，只作补充、不相加。",
        ],
    }

    return {"meta": meta, "hunters": hunters}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    result = build()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    old = OUT.read_text(encoding="utf-8") if OUT.is_file() else None
    if old == text:
        print("hunters.json unchanged (%d hunters)" % len(result["hunters"]))
    else:
        with OUT.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("wrote %s (%d hunters)" % (OUT.relative_to(ROOT), len(result["hunters"])))

    print(
        "candidates=%s sources=%s limit=%s selected=%s window=%s"
        % (
            result["meta"]["candidates"],
            result["meta"]["sourceCount"],
            result["meta"]["limit"],
            result["meta"]["selected"],
            result["meta"]["window"],
        )
    )
    for h in result["hunters"]:
        print(
            "#%d %-15s %-6s sum=%-6d stages=%s gaps=%s"
            % (
                h["rank"],
                h["ipMasked"],
                h["severityMaxLabel"],
                h["stageTotal"],
                "/".join(str(h["stages"][k]) for k in STAGE_ORDER),
                ",".join(h["gaps"]) or "-",
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
