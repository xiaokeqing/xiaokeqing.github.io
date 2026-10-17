#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每周安全战报生成器（公开只读端点版）—— 只写报告，不做任何处置。

为什么是「公开只读端点」而不是直接读日志：
  1) 本机/srv2 都不该为了出一份周报去要 /var/log/nginx 的读权限（实测 ubuntu
     用户读 /var/log/nginx/lab.access.log 是 Permission denied）；
  2) 公开端点在服务端已经做过脱敏（IP 口径、口令结构、自由文本过滤），
     周报直接引用它，口径与站点展示完全一致，不会出现「周报数字和页面数字对不上」；
  3) 端点拿不到时能如实写「未取到」，而不是把本地日志缺行当成 0。

口径纪律（抄自 content/posts/weekly-report-template.md）：
  - 每一格都写清来源端点 + 字段 + 窗口；
  - 没有周粒度就不编「较上周」，如实写「未接入 + 原因」；
  - 取不到就写「未取到」，不补数、不用 0 冒充。

端点与真实字段（2026-10-17 实测响应）：
  /api/public/audit    data.summary{blockTotal,blockActive,blockedByGuard,executedActions}
                       data.blocks[]{ip,durationMinutes,source,actor,createdAt,unblocked,...}
                       data.actions[]{id,time,actor,action,target,reason,riskLevel,mode,success}
                       （blocks[] 是留痕文件，按 createdAt 可在本地切出「本周」）
  /api/public/honeypot data.total(=10000 截断哨兵)/connections/logins/loginFails/sampled
                       data.topSources[]{key,count} / topClients[] / topCredentials[] / timeline[]
  /api/public/geo      data.byCountry[]{country,countryName,count,uniqueIps,sharePercent}
                       data.byAsnTop[]{asn,org,count,uniqueIps}
                       data.coverage{...} / window 固定 24h（传 window=72h/7d 也返回 24h）
  /api/public/alerts   data.stats24h{available,total,bySeverity,trend,windowHours}
                       data.list[]{count,ruleName,srcIp,severity,typeLabel,sourceLabel,...}
                       data.windowMinutes（list 只覆盖最近几分钟）

退出码：
  0  四个端点全部取到
  3  部分端点失败（报告照写，失败项写「未取到」，stderr 打印原因）
  2  四个端点全部失败（不写报告文件，stderr 打印每个端点的错误原文）
  4  参数/时间解析错误
"""

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

DEFAULT_BASE = "https://demo.xiaokeqing.cn"
UA = "secagent-weekly-report/1.0 (+https://xiaokeqing.cn/; read-only report generator)"
UNKNOWN = "未取到"
HONEYPOT_TOTAL_SENTINEL = 10000  # 实测 total 恒为 10000：统计上限哨兵值，不是真实累计


# --------------------------------------------------------------------------
# 取数
# --------------------------------------------------------------------------
def fetch_json(url, timeout):
    """取一个公开只读端点。返回 (data, error_text)；失败时 data 为 None。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    last = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                payload = json.loads(raw.decode("utf-8", "replace"))
            # 统一 {code,message,data} 包装；也容忍直接返回 data 端点
            if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
                return payload["data"], None
            if isinstance(payload, dict):
                return payload, None
            return None, "响应不是 JSON 对象: %r" % (payload,)[:200]
        except urllib.error.HTTPError as exc:
            last = "HTTP %s %s（%s）" % (exc.code, exc.reason, url)
            if 400 <= exc.code < 500 and exc.code != 429:
                break
        except urllib.error.URLError as exc:
            last = "URLError: %s（%s）" % (exc.reason, url)
        except socket.timeout:
            last = "socket timeout: 超过 %ss（%s）" % (timeout, url)
        except ValueError as exc:
            last = "JSON 解析失败: %s（%s）" % (exc, url)
        except Exception as exc:  # noqa: BLE001 —— 取数不能把整份报告搞崩
            last = "%s: %s（%s）" % (type(exc).__name__, exc, url)
        if attempt == 1:
            time.sleep(2)
    return None, last


def dig(obj, *path, **kw):
    """安全取值：任一层缺失/类型不对就返回 default（默认 None）。"""
    default = kw.get("default")
    cur = obj
    for key in path:
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and isinstance(key, int) and -len(cur) <= key < len(cur):
            cur = cur[key]
        else:
            return default
        if cur is None:
            return default
    return cur


def as_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value.strip())
    return None


def fmt_num(value):
    return UNKNOWN if value is None else format(value, ",")


def fmt_with(value, unit):
    """'266 次'；值为空就只写「未取到」，不留下孤零零的单位。"""
    return UNKNOWN if value is None else "%s %s" % (fmt_num(value), unit)


def pct(part, whole):
    if not whole or part is None:
        return None
    return 100.0 * part / whole


# --------------------------------------------------------------------------
# 时间窗口
# --------------------------------------------------------------------------
def parse_week_arg(spec, now):
    """--week 支持 this / last / 2026-W42 / 2026W42 / 2026-10-17（取该日所在 ISO 周）。"""
    today = now.date()
    if not spec or spec.lower() in ("this", "current"):
        ref = today
    elif spec.lower() in ("last", "prev", "previous"):
        ref = today - timedelta(days=7)
    else:
        m = re.fullmatch(r"(\d{4})-?[Ww](\d{1,2})", spec.strip())
        if m:
            year, week = int(m.group(1)), int(m.group(2))
            try:
                ref = date.fromisocalendar(year, week, 1)
            except ValueError as exc:
                raise SystemExit("--week 周号非法（%s）：%s" % (spec, exc))
        else:
            try:
                ref = date.fromisoformat(spec.strip())
            except ValueError:
                raise SystemExit("--week 无法解析：%r；可用 this / last / 2026-W42 / 2026-10-17" % spec)
    monday = ref - timedelta(days=ref.weekday())
    start = datetime(monday.year, monday.month, monday.day)  # 本地时区周一 00:00
    return start, start + timedelta(days=7), "%d-W%02d" % monday.isocalendar()[:2]


def parse_dt(text):
    """端点时间形如 '2026-10-17 14:48:16'（本地时间，无时区标记）。"""
    if not isinstance(text, str):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# 脱敏：保留前三段 + 末段换 x（仓库既有口径：172.16.18.12 → 172.16.18.x）
# 只影响显示，不影响去重/计数（去重用原始值，否则同 /24 会被合并）
# --------------------------------------------------------------------------
def mask_ip(ip):
    if not ip or not isinstance(ip, str):
        return "未知"
    ip = ip.strip()
    if ip in ("内网/未知", "未知", "unknown", "null", "-"):
        return ip if ip != "null" else "未知"
    parts = ip.split(".")
    if len(parts) == 4 and all(re.fullmatch(r"\d{1,3}", p) for p in parts):
        return "%s.%s.%s.x" % (parts[0], parts[1], parts[2])
    if ":" in ip:  # IPv6：保留前四段
        hextets = [h for h in ip.split(":") if h]
        if len(hextets) >= 4:
            return ":".join(hextets[:4]) + ":x::"
        return "IPv6·已隐藏"
    return ip


# --------------------------------------------------------------------------
# 各端点的归一化
# --------------------------------------------------------------------------
IPV4_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3})\.(\d{1,3})\b")


def scrub_ips(text):
    """把自由文本（规则名/告警标题里常拼着来源 IP）里的四段 IPv4 一并掩码。
    只用于展示文本；结构化字段的计数去重仍用原始值。"""
    if not isinstance(text, str):
        return text
    return IPV4_RE.sub(lambda m: "%s.x" % m.group(1), text)


def norm_audit(data):
    """把 /audit 归一成 report 直接可用的结构；字段缺失用 None，不抛异常。"""
    if not data:
        return None
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    blocks = data.get("blocks") if isinstance(data.get("blocks"), list) else []
    actions = data.get("actions") if isinstance(data.get("actions"), list) else []
    return {
        "summary": {
            "blockTotal": as_int(summary.get("blockTotal")),
            "blockActive": as_int(summary.get("blockActive")),
            "blockedByGuard": as_int(summary.get("blockedByGuard")),
            "executedActions": as_int(summary.get("executedActions")),
        },
        "blocks": [b for b in blocks if isinstance(b, dict)],
        "actions": [a for a in actions if isinstance(a, dict)],
        "generatedAt": data.get("generatedAt"),
    }


def norm_honeypot(data):
    if not data:
        return None
    return {
        "total": as_int(data.get("total")),
        "connections": as_int(data.get("connections")),
        "logins": as_int(data.get("logins")),
        "loginFails": as_int(data.get("loginFails")),
        "sampled": as_int(data.get("sampled")),
        "commandsAvailable": data.get("commandsAvailable"),
        "topSources": [x for x in (data.get("topSources") or []) if isinstance(x, dict)],
        "topClients": [x for x in (data.get("topClients") or []) if isinstance(x, dict)],
        "note": data.get("note"),
        "generatedAt": data.get("generatedAt"),
    }


def norm_geo(data):
    if not data:
        return None
    return {
        "window": data.get("window"),
        "geoSource": data.get("geoSource"),
        "coverage": data.get("coverage") if isinstance(data.get("coverage"), dict) else {},
        "byCountry": [x for x in (data.get("byCountry") or []) if isinstance(x, dict)],
        "byAsnTop": [x for x in (data.get("byAsnTop") or []) if isinstance(x, dict)],
        "thresholds": data.get("thresholds") if isinstance(data.get("thresholds"), dict) else {},
        "generatedAt": data.get("generatedAt"),
    }


def norm_alerts(data):
    if not data:
        return None
    stats24h = data.get("stats24h") if isinstance(data.get("stats24h"), dict) else {}
    by_sev = stats24h.get("bySeverity") if isinstance(stats24h.get("bySeverity"), dict) else {}
    return {
        "stats24h": {
            "available": stats24h.get("available"),
            "total": as_int(stats24h.get("total")),
            "bySeverity": {k: as_int(v) for k, v in by_sev.items()},
            "windowHours": as_int(stats24h.get("windowHours")),
            "state": stats24h.get("state"),
            "reason": stats24h.get("reason"),
        },
        "windowMinutes": as_int(data.get("windowMinutes")),
        "windowSize": as_int(data.get("windowSize")),
        "total": as_int(data.get("total")),
        "rawTotal": as_int(data.get("rawTotal")),
        "list": [x for x in (data.get("list") or []) if isinstance(x, dict)],
        "generatedAt": data.get("generatedAt"),
    }


# --------------------------------------------------------------------------
# 本地现算的聚合
# --------------------------------------------------------------------------
def week_blocks(blocks, start, end):
    out = []
    for b in blocks:
        dt = parse_dt(b.get("createdAt"))
        if dt is not None and start <= dt < end:
            out.append(b)
    return out


def top_rules(alerts, limit=5):
    """规则命中 Top N：把当前聚合窗口内同 ruleName 的 count 累加。"""
    if not alerts:
        return []
    agg = {}
    for item in alerts.get("list") or []:
        name = item.get("ruleName") or item.get("title")
        count = as_int(item.get("count"))
        if not name or count is None:
            continue
        agg[name] = agg.get(name, 0) + count
    rows = sorted(agg.items(), key=lambda kv: (-kv[1], kv[0]))
    return rows[:limit]


def sev_line(alerts):
    if not alerts:
        return None
    sev = alerts["stats24h"].get("bySeverity") or {}
    total = alerts["stats24h"].get("total")
    high = sev.get("HIGH")
    crit = sev.get("CRITICAL")
    if high is None and crit is None:
        return None
    parts = []
    if crit is not None:
        parts.append("严重 %s" % fmt_num(crit))
    if high is not None:
        parts.append("高危 %s" % fmt_num(high))
    line = "，".join(parts)
    h = (crit or 0) + (high or 0)
    ratio = pct(h, total)
    if ratio is not None:
        line += "（合计占比 %.1f%%）" % ratio
    return line


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------
def build_report(now, ws, we, wk, endpoints, errors, base):
    audit, honey, geo, alerts = (endpoints.get(k) for k in ("audit", "honeypot", "geo", "alerts"))

    # ---- 审计：本周切片（只用 createdAt，不改原始值）----
    wk_blocks = week_blocks(audit["blocks"], ws, we) if audit else []
    prev_ws, prev_we = ws - timedelta(days=7), we - timedelta(days=7)
    prev_blocks = week_blocks(audit["blocks"], prev_ws, prev_we) if audit else []
    wk_ips = sorted({b.get("ip") for b in wk_blocks if b.get("ip")})
    prev_ips = sorted({b.get("ip") for b in prev_blocks if b.get("ip")})
    all_ips = sorted({b.get("ip") for b in (audit or {}).get("blocks", []) if b.get("ip")})
    block_total = dig(audit, "summary", "blockTotal")
    blocked_by_guard = dig(audit, "summary", "blockedByGuard")
    executed = dig(audit, "summary", "executedActions")
    active = dig(audit, "summary", "blockActive")

    # ---- 蜜罐：total 恒为 10000 → 统计上限哨兵 ----
    honey_total = dig(honey, "total")
    honeypot_capped = honey_total is not None and honey_total >= HONEYPOT_TOTAL_SENTINEL

    # ---- 24h 告警 ----
    alerts_total = dig(alerts, "stats24h", "total")
    alerts_win = dig(alerts, "windowMinutes")

    L = []
    add = L.append
    add("# 安全战报 · %s（%s ~ %s）" % (wk, ws.strftime("%Y-%m-%d"), (we - timedelta(days=1)).strftime("%Y-%m-%d")))
    add("")
    add("> 统计窗口（本周）：`%s 00:00` → `%s 00:00`（本地时区，含头不含尾）" % (ws.strftime("%Y-%m-%d"), we.strftime("%Y-%m-%d")))
    add("> 生成时间：%s ｜ 数据源：%s 的四个公开只读端点（不读服务器日志、不做任何处置）" % (now.strftime("%Y-%m-%d %H:%M:%S"), base))
    add("")
    if errors:
        add("> ⚠️ 有 %d 个端点未取到：%s —— 下文对应项写「%s」，不补数。" % (
            len(errors), "、".join(sorted(errors)), UNKNOWN))
        add("")

    # 0. 一句话结论
    add("## 0. 一句话结论")
    add("")
    bits = []
    if blocked_by_guard is not None:
        bits.append("护栏累计拦下 %s 个动作、已执行 %s 个处置动作" % (fmt_num(blocked_by_guard), fmt_num(executed)))
    if audit:
        if wk_blocks:
            bits.append("本周新增 %d 条封禁留痕、涉及 %d 个地址（去重）" % (len(wk_blocks), len(wk_ips)))
        else:
            bits.append("本周没有新增封禁留痕（留痕总数 %s 条，口径见 §1）" % fmt_num(block_total))
    if dig(honey, "connections") is not None:
        bits.append("蜜罐累计连接 %s 次" % fmt_num(dig(honey, "connections")))
    if alerts_total is not None:
        bits.append("最近 24h 告警 %s 条" % fmt_num(alerts_total))
    countries = dig(geo, "byCountry") or []
    if countries:
        c0 = countries[0]
        share = c0.get("sharePercent")
        bits.append("24h 来源以 %s 为主（%s%%）" % (
            c0.get("countryName") or c0.get("country") or "未知国家",
            ("%.1f" % share) if isinstance(share, (int, float)) else UNKNOWN))
    if bits:
        add("**%s。**" % "；".join(bits))
    else:
        add("**本周无可用数据**：四个公开端点全部未取到，见 §7 的原因原文。")
    add("")

    # 1. 口径表
    add("## 1. 指标与口径（每个数字都能回查）")
    add("")
    add("| 指标 | 数值 | 口径（端点 · 字段 · 窗口） |")
    add("|---|---|---|")
    add("| 拦截总数（护栏拦下） | %s | `audit` · `summary.blockedByGuard` · **累计**，非本周 |" % fmt_num(blocked_by_guard))
    add("| 已执行处置动作 | %s | `audit` · `summary.executedActions` · **累计** |" % fmt_num(executed))
    add("| 本周新增封禁留痕 | %s | `audit` · `blocks[].createdAt` 归周现算 · **本周** |" % (
        ("%d 条" % len(wk_blocks)) if audit else UNKNOWN))
    add("| 封禁 IP 数（本周，去重） | %s | 同上，按 `blocks[].ip` 去重后计数 · **本周** |" % (len(wk_ips) if audit else UNKNOWN))
    add("| 封禁 IP 数（留痕内累计，去重） | %s | `audit` · `blocks[].ip` 全量去重 · 留痕文件范围 |" % (len(all_ips) if audit else UNKNOWN))
    add("| 当前生效中的封禁 | %s | `audit` · `summary.blockActive` · **累计** |" % fmt_num(active))
    add("| 蜜罐连接数 | %s | `honeypot` · `connections` · 服务端累计 |" % fmt_num(dig(honey, "connections")))
    add("| 蜜罐登录尝试 / 登录失败 | %s / %s | `honeypot` · `logins` / `loginFails` · 同一响应内 |" % (
        fmt_num(dig(honey, "logins")), fmt_num(dig(honey, "loginFails"))))
    add("| 蜜罐累计事件（total） | %s | `honeypot` · `total`%s |" % (
        fmt_num(honey_total), " · **统计上限哨兵值，非真实累计**" if honeypot_capped else ""))
    add("| 24h 告警总量 | %s | `alerts` · `stats24h.total` · **24h 未去重** |" % fmt_num(alerts_total))
    add("| 24h 严重 / 高危 | %s | `alerts` · `stats24h.bySeverity` · 同一 24h 桶 |" % (sev_line(alerts) or UNKNOWN))
    add("")
    if honeypot_capped:
        add("> ⚠️ **蜜罐 `total` 的「统计上限」语义**：实测四个时点 `total` 恒为 10000，"
            "而 `connections` 只有几百 —— 10000 是服务端的截断/哨兵值，不是真实累计。"
            "本报告一律用 `connections` 当连接数，`total` 只作「已到上限」的标记。")
        add("")

    # 2. 告警 / 蜜罐
    add("## 2. 告警与蜜罐")
    add("")
    add("| 项 | 数值 | 说明 |")
    add("|---|---|---|")
    add("| 24h 告警 | %s | `stats24h.total`，未去重；state=%s |" % (
        fmt_with(alerts_total, "条"), dig(alerts, "stats24h", "state") or UNKNOWN))
    add("| 24h 严重 / 高危 | %s | 同一 24h 桶 |" % (sev_line(alerts) or UNKNOWN))
    win_total = dig(alerts, "total")
    add("| 当前聚合窗口告警（去重） | %s | `alerts.total`，窗口 %s |" % (
        fmt_with(win_total, "条"), fmt_with(alerts_win, "分钟")))
    add("| 当前窗口原始条数 | %s | `alerts.rawTotal`；`alerts.windowSize` = %s 条为取数上限 |" % (
        fmt_num(dig(alerts, "rawTotal")), fmt_num(dig(alerts, "windowSize"))))
    add("| 蜜罐连接 / 登录 / 登录失败 | %s / %s / %s | 同一响应内字段（口径一致） |" % (
        fmt_num(dig(honey, "connections")), fmt_num(dig(honey, "logins")), fmt_num(dig(honey, "loginFails"))))
    add("| 蜜罐采样窗口 | %s | `honeypot.sampled`（Top 榜只在这个窗口内计数） |" % fmt_num(dig(honey, "sampled")))
    honey_cmd = dig(honey, "commandsAvailable")
    add("| 命令时间线 | %s | `commandsAvailable=%s`%s |" % (
        UNKNOWN if honey is None else ("数据源未接入" if honey_cmd in (False, None) else "可用"),
        honey_cmd, "，数据源未接入（不编造）" if honey is not None and honey_cmd in (False, None) else ""))
    add("")

    # 3. Top5 国家 / ASN
    add("## 3. Top 5 来源国家 / ASN")
    add("")
    add("> 窗口：`geo.window` = **%s**（端点固定 24 小时；实测传 `window=72h` / `7d` 仍返回 24h）。"
        "周粒度的国别/ASN 聚合**未接入**，所以这一节不是「本周」口径，读的时候别当成周数据。" % (
            dig(geo, "window") or UNKNOWN))
    add("")
    add("| # | 国家 | 24h 告警数 | 唯一来源 IP | 占比 |")
    add("|---|---|---|---|---|")
    for i, c in enumerate(countries[:5], 1):
        add("| %d | %s（`%s`） | %s | %s | %s |" % (
            i, scrub_ips(c.get("countryName")) or "未知", c.get("country") or "?", fmt_num(as_int(c.get("count"))),
            fmt_num(as_int(c.get("uniqueIps"))),
            ("%.1f%%" % c["sharePercent"]) if isinstance(c.get("sharePercent"), (int, float)) else UNKNOWN))
    if not countries:
        add("| — | %s | — | — | — |" % UNKNOWN)
    add("")
    add("| # | ASN | 组织 | 24h 告警数 | 唯一来源 IP |")
    add("|---|---|---|---|---|")
    for i, a in enumerate((dig(geo, "byAsnTop") or [])[:5], 1):
        add("| %d | `AS%s` | %s | %s | %s |" % (
            i, a.get("asn") if a.get("asn") is not None else "?", scrub_ips(a.get("org")) or "未知",
            fmt_num(as_int(a.get("count"))), fmt_num(as_int(a.get("uniqueIps")))))
    if not (dig(geo, "byAsnTop") or []):
        add("| — | %s | — | — | — |" % UNKNOWN)
    add("")
    cov = dig(geo, "coverage") or {}
    if cov:
        add("分母（`geo.coverage`）：窗口内告警 %s 条，其中带来源 IP %s 条，成功定位 %s 条，"
            "排除自身 %s 条、内网 %s 条；入榜门槛 count≥%s 且占比≥%s%%。" % (
                fmt_num(as_int(cov.get("totalAlerts"))), fmt_num(as_int(cov.get("withSourceIp"))),
                fmt_num(as_int(cov.get("geocoded"))), fmt_num(as_int(cov.get("excludedSelf"))),
                fmt_num(as_int(cov.get("excludedInternal"))),
                dig(geo, "thresholds", "minCount") or "?", dig(geo, "thresholds", "minSharePercent") or "?"))
        add("")

    # 4. Top5 攻击 IP（脱敏）
    add("## 4. Top 5 攻击 IP（脱敏）")
    add("")
    add("> 口径：`honeypot.topSources[]`，采样窗口 `sampled=%s`；IP 显示按仓库既有规则"
        "「保留前三段 + 末段换 `x`」（`a.b.c.d` → `a.b.c.x`）。"
        "去重与计数用原始值，只有展示被掩码。" % fmt_num(dig(honey, "sampled")))
    add("")
    add("| # | 来源 IP（已掩码） | 命中次数 |")
    add("|---|---|---|")
    srcs = dig(honey, "topSources") or []
    for i, s in enumerate(srcs[:5], 1):
        add("| %d | `%s` | %s |" % (i, mask_ip(s.get("key")), fmt_num(as_int(s.get("count")))))
    if not srcs:
        add("| — | %s | — |" % UNKNOWN)
    add("")
    if wk_ips:
        add("本周封禁留痕涉及的地址（去重，已掩码）：%s。" % "、".join("`%s`" % mask_ip(ip) for ip in wk_ips[:10]))
        add("")
    elif audit:
        add("本周封禁留痕涉及的地址：本周无新增留痕。")
        add("")

    # 5. 规则命中 / ATT&CK
    add("## 5. Top 5 规则命中（ATT&CK）")
    add("")
    add("> ATT&CK 技术编号**未接入**：四个公开端点都没有 `attack.*` 字段（`alerts` 只给 `type`/`typeLabel`/"
        "`ruleName`），所以本节给的是**规则命中**，不是 ATT&CK 矩阵。"
        "窗口：`alerts.list` 只覆盖最近 %s 分钟（windowSize=%s），非本周。" % (
            fmt_num(alerts_win), fmt_num(dig(alerts, "windowSize"))))
    add("")
    add("| # | 规则名 | 命中次数 |")
    add("|---|---|---|")
    rules = top_rules(alerts)
    for i, (name, cnt) in enumerate(rules, 1):
        add("| %d | %s | %s |" % (i, scrub_ips(name).replace("|", "\\|"), fmt_num(cnt)))
    if not rules:
        add("| — | %s | — |" % UNKNOWN)
    add("")

    # 6. 本周变化
    add("## 6. 本周变化")
    add("")
    add("只写真能算的。算不出来的写「未接入 + 原因」，不编基准、不给自造的百分比。")
    add("")
    add("| 项 | 本周（%s） | 上一周（%s ~ %s） | 变化 |" % (
        wk, prev_ws.strftime("%m-%d"), (prev_we - timedelta(days=1)).strftime("%m-%d")))
    add("|---|---|---|---|")
    delta_n = len(wk_blocks) - len(prev_blocks)
    add("| 封禁留痕条数 | %s | %s | %s |" % (
        len(wk_blocks) if audit else UNKNOWN, len(prev_blocks) if audit else UNKNOWN,
        ("+%d" % delta_n) if delta_n > 0 else str(delta_n) if audit else UNKNOWN))
    delta_ip = len(wk_ips) - len(prev_ips)
    add("| 封禁 IP 数（去重） | %s | %s | %s |" % (
        len(wk_ips) if audit else UNKNOWN, len(prev_ips) if audit else UNKNOWN,
        ("+%d" % delta_ip) if delta_ip > 0 else str(delta_ip) if audit else UNKNOWN))
    add("| 24h 告警 | %s | 未接入 | — |" % fmt_num(alerts_total))
    add("| 蜜罐连接 | %s | 未接入 | — |" % fmt_num(dig(honey, "connections")))
    add("")
    add("**为什么大部分是「未接入」**：`alerts.stats24h` 只有 24 小时桶、`geo` 固定 24h、"
        "`honeypot` 只有服务端累计值 —— 公开端点**没有**日/周粒度聚合，"
        "所以「较上周」只在 `audit.blocks[].createdAt` 上能诚实计算。")
    add("")
    if audit and len(prev_blocks) == 0:
        add("> 注意：上一周留痕为 0 条，既可能是那一周确实没有封禁，也可能是留痕文件只保留了最近一段"
            "（当前文件内共 %d 条）。这一行读作「留痕文件里的上一周」，不是「上周真实封禁数」。"
            % len(audit.get("blocks") or []))
        add("")

    # 7. 取数状态
    add("## 7. 取数状态（失败项与原因原文）")
    add("")
    add("| 端点 | 状态 | 错误原文 |")
    add("|---|---|---|")
    for name in ("audit", "honeypot", "geo", "alerts"):
        if name in errors:
            add("| `/api/public/%s` | 失败 | %s |" % (name, errors[name].replace("|", "\\|")))
        else:
            add("| `/api/public/%s` | 成功（generatedAt=%s） | — |" % (
                name, dig(endpoints.get(name), "generatedAt") or UNKNOWN))
    add("")

    # 8. 已知限制
    add("## 8. 已知限制 / 口径变更")
    add("")
    add("- 本报告**没有**读 srv2 的 `/var/log/nginx`，也不需要该权限；所有数字来自公开只读端点。")
    add("- 端点缓存 45s；同一分钟重复跑结果可能相同。")
    add("- 「本周」按本机时区的 ISO 周（周一 00:00 起）现算；端点自身不提供周窗口。")
    add("- 口径变更：无（首次生成）。")
    add("")
    add("---")
    add("")
    add("*生成器：`scripts/weekly-report.py`（python3 标准库，无第三方依赖），只读、不处置、不部署。*")
    add("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# 静态页导出（给 nginx 的 /reports/ 目录用）
#   为什么不用 markdown 库：这里只依赖标准库，而报告本身就是我们生成的固定结构
#   （# / ## 标题、> 引用、| 表格 |、- 列表、**粗体**、`代码`），一个小转换器够了。
# ---------------------------------------------------------------------------
_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}


def _esc(t):
    return "".join(_ESC.get(c, c) for c in t)


def _inline(t):
    t = _esc(t)
    out = []
    i = 0
    while i < len(t):
        if t.startswith("**", i):
            j = t.find("**", i + 2)
            if j > 0:
                out.append("<b>%s</b>" % t[i + 2:j])
                i = j + 2
                continue
        if t[i] == "`":
            j = t.find("`", i + 1)
            if j > 0:
                out.append("<code>%s</code>" % t[i + 1:j])
                i = j + 1
                continue
        out.append(t[i])
        i += 1
    return "".join(out)


def render_md_html(md):
    lines = md.split("\n")
    html = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.rstrip()
        if not s.strip():
            i += 1
            continue
        if s.startswith("# "):
            html.append("<h1>%s</h1>" % _inline(s[2:]))
        elif s.startswith("## "):
            html.append("<h2>%s</h2>" % _inline(s[3:]))
        elif s.startswith("### "):
            html.append("<h3>%s</h3>" % _inline(s[4:]))
        elif s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                buf.append(_inline(lines[i].lstrip().lstrip(">").strip()))
                i += 1
            html.append("<blockquote>%s</blockquote>" % "<br>".join(buf))
            continue
        elif s.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            body = []
            for r, cells in enumerate(rows):
                if set("".join(cells)) <= set("-: "):
                    continue
                tag = "th" if r == 0 else "td"
                body.append("<tr>" + "".join("<%s>%s</%s>" % (tag, _inline(c), tag) for c in cells) + "</tr>")
            html.append("<table>%s</table>" % "".join(body))
            continue
        elif s.lstrip().startswith("- "):
            items = []
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                items.append("<li>%s</li>" % _inline(lines[i].lstrip()[2:]))
                i += 1
            html.append("<ul>%s</ul>" % "".join(items))
            continue
        else:
            html.append("<p>%s</p>" % _inline(s))
        i += 1
    return "\n".join(html)


_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
<style>
:root{--bg:#0b0f12;--fg:#dfe7ea;--mut:#8ea3ab;--acc:#78e6e1;--line:#22313a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.75 -apple-system,"Segoe UI",system-ui,"Microsoft YaHei",sans-serif}
main{max-width:82ch;margin:0 auto;padding:28px 18px 64px}
a{color:var(--acc)}
h1{font-size:22px;margin:8px 0 6px}
h2{font-size:17px;margin:26px 0 8px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:15px;margin:18px 0 6px;color:var(--acc)}
p,li{color:var(--fg)}
blockquote{margin:12px 0;padding:10px 14px;border-left:3px solid var(--acc);background:#101820;color:var(--mut)}
table{width:100%%;border-collapse:collapse;margin:12px 0;font-size:13.5px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:#101820;color:var(--mut);font-weight:600}
code{background:#101820;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:12.5px}
ul{padding-left:20px}
.nav{font-size:13px;color:var(--mut);margin-bottom:14px}
</style></head><body><main>
<div class="nav"><a href="/">← 回站点</a> · <a href="/reports/">全部周报</a></div>
%s
</main></body></html>
"""


def write_html_for(md_path, report):
    """写同名 .html + 目录 index.html（列表按文件名倒序）。"""
    import glob
    import os
    html_path = os.path.splitext(md_path)[0] + ".html"
    title = report.split("\n", 1)[0].lstrip("# ").strip() or "安全战报"
    with open(html_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_PAGE % (title, render_md_html(report)))
    d = os.path.dirname(os.path.abspath(md_path))
    items = []
    for p in sorted(glob.glob(os.path.join(d, "weekly-*.html")), reverse=True):
        name = os.path.basename(p)
        head = ""
        try:
            with open(p, encoding="utf-8") as fh:
                txt = fh.read()
            k = txt.find("<h1>")
            if k >= 0:
                head = txt[k + 4:txt.find("</h1>", k)]
        except OSError:
            pass
        items.append('<li><a href="%s">%s</a>%s</li>' % (_esc(name), _esc(name),
                                                          ("<br><span style=\"color:var(--mut);font-size:13px\">%s</span>" % head) if head else ""))
    idx = _PAGE % ("安全战报 · 周报目录",
                   "<h1>安全战报 · 周报目录</h1><p>每周一 06:00 自动生成；每个数字都能追溯到公开端点。"
                   "没有条目就是还没跑过。</p><ul>" + "".join(items) + "</ul>")
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(idx)
    return html_path


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="生成每周安全战报（公开只读端点，Markdown）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python3 weekly-report.py\n"
               "  python3 weekly-report.py --week 2026-W42 --out /opt/secagent/reports/weekly-%Y-%m-%d.md\n"
               "  python3 weekly-report.py --week last --timeout 30",
    )
    ap.add_argument("--week", default="this",
                    help="this（默认）/ last / 2026-W42 / 2026W42 / 2026-10-17（取该日所在 ISO 周）")
    ap.add_argument("--out", metavar="PATH",
                    help="写入文件（可含 strftime 占位符，如 weekly-%%Y-%%m-%%d.md）；缺省写 stdout")
    ap.add_argument("--out-dir", metavar="DIR",
                    help="写入 DIR/weekly-<运行日期>.md；与 --out 二选一")
    ap.add_argument("--base-url", default=os.environ.get("WEEKLY_REPORT_BASE", DEFAULT_BASE),
                    help="端点根地址，默认 %s（也可用环境变量 WEEKLY_REPORT_BASE）" % DEFAULT_BASE)
    ap.add_argument("--timeout", type=int, default=30, help="单端点超时秒数，默认 30")
    args = ap.parse_args(argv)

    if args.out and args.out_dir:
        sys.stderr.write("参数冲突：--out 与 --out-dir 只能给一个\n")
        return 4
    if args.timeout <= 0:
        sys.stderr.write("参数错误：--timeout 必须 > 0\n")
        return 4

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    now = datetime.now()
    try:
        ws, we, wk = parse_week_arg(args.week, now)
    except SystemExit as exc:
        sys.stderr.write("%s\n" % exc)
        return 4

    base = args.base_url.rstrip("/")
    raw, errors = {}, {}
    for name, path in (("audit", "/api/public/audit"),
                       ("honeypot", "/api/public/honeypot"),
                       ("geo", "/api/public/geo"),
                       ("alerts", "/api/public/alerts?limit=200")):
        data, err = fetch_json(base + path, args.timeout)
        if err:
            errors[name] = err
            sys.stderr.write("[取数失败] %s%s：%s\n" % (base, path, err))
        else:
            raw[name] = data

    if not raw:
        sys.stderr.write("\n四个端点全部失败，不生成报告。原因：\n")
        for name in ("audit", "honeypot", "geo", "alerts"):
            sys.stderr.write("  - %s: %s\n" % (name, errors.get(name, "未知")))
        return 2

    endpoints = {
        "audit": norm_audit(raw.get("audit")),
        "honeypot": norm_honeypot(raw.get("honeypot")),
        "geo": norm_geo(raw.get("geo")),
        "alerts": norm_alerts(raw.get("alerts")),
    }
    # generatedAt 用于状态表
    for name, normed in endpoints.items():
        if normed is not None:
            normed["generatedAt"] = raw[name].get("generatedAt")

    report = build_report(now, ws, we, wk, endpoints, errors, base)

    out_path = None
    if args.out:
        out_path = expand_strftime(args.out, now)
    elif args.out_dir:
        out_path = os.path.join(args.out_dir, "weekly-%s.md" % now.strftime("%Y-%m-%d"))

    if out_path:
        parent = os.path.dirname(os.path.abspath(out_path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(report)
        sys.stderr.write("已写入 %s（%d 字节）\n" % (out_path, len(report.encode("utf-8"))))
        if out_path.endswith(".md"):
            try:
                write_html_for(out_path, report)
                sys.stderr.write("已写入同名 .html 与目录 index.html\n")
            except OSError as exc:
                sys.stderr.write("HTML 导出失败（不影响 .md）：%s\n" % exc)
    else:
        sys.stdout.write(report)

    if errors:
        sys.stderr.write("部分端点失败（%s），报告已按「%s」如实生成。\n" % ("、".join(sorted(errors)), UNKNOWN))
        return 3
    return 0


def expand_strftime(pattern, now):
    """把 %Y-%m-%d 这类占位符按运行时间展开；不含 % 时原样返回。"""
    if "%" not in pattern:
        return pattern
    try:
        return now.strftime(pattern)
    except ValueError as exc:
        raise SystemExit("--out 时间格式非法：%s（%s）" % (pattern, exc))


if __name__ == "__main__":
    sys.exit(main())
