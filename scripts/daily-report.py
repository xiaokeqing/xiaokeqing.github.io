#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日攻击日报生成器（本地文件版）—— 完全离线，只写报告，不联网、不处置、不发布。

为什么是「读本地文件」而不是走公开端点：
  1) 日报要的是「今天 00:00 之后」的精确切片，公开端点的 /alerts 只给最近几分钟的聚合
     （windowMinutes 实测 5 分钟），/honeypot 只给服务端累计值 —— 端点没有日粒度，
     用它出日报只能靠估；
  2) 日报必须在断网/端点挂掉时也能出，而且出的东西要能回查原始行（eve.json / cowrie.json）；
  3) 读不到就写「读不到（原因）」，不补数、不用 0 冒充 —— 这是本脚本的第一条纪律。

数据源（三个路径都从参数来，逐个做存在性/可读性检查）：
  --eve     /var/lib/suricata/eve.json            Suricata JSON Lines（event_type=alert 等）
  --cowrie  /opt/cowrie/logs/cowrie.json          Cowrie JSON Lines（eventid=cowrie.*）
  --ci      /opt/secagent/reports/ci/latest.json  一致性巡检结果（只用来写「巡检状态」）

口径要点（详见 docs/日报-20261018.md）：
  - 「今日」= 本地时区的自然日 00:00 → 次日 00:00（含头不含尾），时区默认 Asia/Shanghai；
  - 告警分成两类：**心跳自噪声**（SID 2013031 / 1000108，目标 169.254.0.4:80 的云 agent
    上报；2026-10-18 04:25 实测占全部 alert 的 94.9%）与**真实告警**，两类的分母分开写；
  - 「高危」只数真实告警里 severity=1 的条数（Suricata severity 1/2/3 = 高危/中危/低危）；
  - 来源 IP 只在展示层掩码（a.b.c.d → a.b.c.x），去重与计数用原始值；
  - 口令**只写结构**（长度 + 字符类别），报告里不出现任何口令原文。

退出码：
  0  三个数据源全部读到
  3  部分读不到（报告照写，缺失项写「读不到（原因）」，stderr 打印原因）
  2  三个数据源全部读不到（报告仍写出：日报的价值就是记录「今天读不到什么」）
  4  参数错误

用法：
  python3 daily-report.py                       # 打印到 stdout（本机没装 Suricata 就是 3 个「读不到」）
  python3 daily-report.py --eve /var/lib/suricata/eve.json \
      --cowrie /opt/cowrie/logs/cowrie.json --ci /opt/secagent/reports/ci/latest.json \
      --out /opt/secagent/reports/daily-%Y-%m-%d.md
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

UNREADABLE = "读不到"
EVE_DEFAULT = "/var/lib/suricata/eve.json"
COWRIE_DEFAULT = "/opt/cowrie/logs/cowrie.json"
CI_DEFAULT = "/opt/secagent/reports/ci/latest.json"

# 心跳自噪声的识别口径：SID 优先，其次「目标就是那条链路本地地址」。
HB_SIDS_DEFAULT = "2013031,1000108"
HB_DST_DEFAULT = "169.254.0.4"
# 「默认识别出的心跳 SID」的集合：用来在 §8.2 里标出哪些私有 SID 属于心跳类
HB_SIDS_SET = frozenset(int(x) for x in HB_SIDS_DEFAULT.split(","))

# 2026-10-18 04:25 实测基线（content/posts/ssh-bruteforce-163.5.210.194.md）：
# 294,112 条 alert 里 279,099 条 = 94.9%，全部是 10.0.0.10 → 169.254.0.4:80 的
# `POST /ca_report.cgi`（签名 2013031 ET INFO Python-urllib/ Suspicious User Agent）。
HB_BASELINE_SHARE = 94.9
HB_BASELINE_TEXT = ("2026-10-18 04:25 实测基线：294,112 条 alert 里 279,099 条（94.9%）"
                    "是 `10.0.0.x → 169.254.0.x:80 POST /ca_report.cgi`（SID 2013031）的云 agent 心跳")

# 本地私有 SID 段的规则名（detections/suricata/xk-lab.rules，便于把 SID 读成人话）
KNOWN_SIDS = {
    1000101: "SSH 客户端指纹：Go 语言 SSH 库（爆破工具默认 banner）",
    1000102: "SSH 客户端指纹：libssh / libssh2（自动化爆破框架默认库）",
    1000103: "Cowrie 诱捕端口 2222：同源 5 分钟 ≥10 次连接",
    1000104: "多诱捕端口顺序扫描：同源 60 秒 ≥3 次 SYN",
    1000105: "HTTP 敏感文件探测：.env 家族 / .git/config / web.config",
    1000106: "已知测绘/渗透工具 UA 指纹（低优先级线索）",
    1000107: "外部源直连数据库端口（1433/3306/6379/9200/27017）",
    1000108: "【抑制型】169.254.0.4:80 云 agent 上报（opt-in，默认未部署）",
    2013031: "ET INFO Python-urllib/ Suspicious User Agent（心跳自噪声的来源规则）",
}

# 端口 → 服务名（只写常识映射，别当成「侦测到的服务」）
SERVICES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http", 110: "pop3",
    143: "imap", 443: "https", 445: "smb", 993: "imaps", 995: "pop3s", 1433: "mssql",
    1521: "oracle", 2049: "nfs", 2222: "ssh（Cowrie 诱捕）", 2375: "docker", 3306: "mysql",
    3389: "rdp", 5432: "postgres", 5900: "vnc", 6379: "redis", 8080: "http-alt",
    8443: "https-alt", 9000: "http-alt", 9200: "elasticsearch", 27017: "mongodb",
}

# 内置「高频弱口令小表」：只用来数「命中多少次」，报告里不输出任何命中值
WEAK_PASSWORDS = frozenset((
    "123456", "1234567", "12345678", "123456789", "1234567890", "12345", "1234", "111111",
    "000000", "password", "passw0rd", "p@ssw0rd", "qwerty", "qwerty123", "1qaz2wsx", "1q2w3e4r",
    "abc123", "admin", "root", "toor", "guest", "test", "test123", "ubuntu", "letmein",
    "welcome", "dragon", "monkey", "default", "changeme", "raspberry", "oracle", "postgres",
))

SEV_LABEL = {1: "高危", 2: "中危", 3: "低危"}


# --------------------------------------------------------------------------
# 通用小工具（与 scripts/weekly-report.py 保持同一套写法/口径）
# --------------------------------------------------------------------------
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
    return UNREADABLE if value is None else format(value, ",")


def pct(part, whole):
    if not whole or part is None:
        return None
    return 100.0 * part / whole


def delta_str(today, yest):
    """今日 - 昨日；两个数都得是真的才给差值，缺一个就写「—」。"""
    if today is None or yest is None:
        return "—"
    d = today - yest
    if d == 0:
        return "0"
    return ("+%s" % format(d, ",")) if d > 0 else format(d, ",")


def delta_ratio_str(today, yest):
    """带百分比的差值：+1,234（+23.5%）；昨日为 0 时只给绝对差，不给除不出来的百分比。"""
    base = delta_str(today, yest)
    if base == "—" or today is None or yest is None:
        return base
    if yest == 0:
        return base if today == 0 else "%s（昨日 0，百分比无意义）" % base
    return "%s（%+.1f%%）" % (base, 100.0 * (today - yest) / yest)


# 展示层掩码：保留前三段 + 末段换 x（仓库既有口径 172.16.18.12 → 172.16.18.x）
# 只影响显示，不影响去重/计数。
def mask_ip(ip):
    if not ip or not isinstance(ip, str):
        return "未知"
    ip = ip.strip()
    if ip in ("内网/未知", "未知", "unknown", "null", "-", ""):
        return "未知" if ip != "null" else "未知"
    parts = ip.split(".")
    if len(parts) == 4 and all(re.fullmatch(r"\d{1,3}", p) for p in parts):
        return "%s.%s.%s.x" % (parts[0], parts[1], parts[2])
    if ":" in ip:  # IPv6：保留前四段
        hextets = [h for h in ip.split(":") if h]
        if len(hextets) >= 4:
            return ":".join(hextets[:4]) + ":x::"
        return "IPv6·已隐藏"
    return ip


IPV4_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3})\.(\d{1,3})\b")


def scrub_ips(text):
    """自由文本（规则名里常拼着来源 IP）一并掩码；结构化字段的计数仍用原始值。"""
    if not isinstance(text, str):
        return text
    return IPV4_RE.sub(lambda m: "%s.x" % m.group(1), text)


def cell(text):
    """表格单元格：把 ASCII 竖线换成全角竖线。

    用全角而不是 `\\|` 转义：weekly-report.py 的 render_md_html 是 `split("|")`，
    不认反斜线转义 —— 真写 `\\|` 反而会把表格拆坏。
    """
    return str(text).replace("|", "｜")


# --------------------------------------------------------------------------
# 时间：事件时间戳解析（Suricata：2026-10-11T09:23:07.131065+0000；Cowrie：…Z）
# --------------------------------------------------------------------------
_TS_RE = re.compile(
    r"^\s*(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?\s*(Z|[+-]\d{2}:?\d{2})?\s*$"
)


def parse_ts(value):
    """返回带时区的 datetime（缺时区标记时按 UTC 解释），失败返回 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    m = _TS_RE.match(value)
    if not m:
        return None
    y, mo, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))
    frac = m.group(7) or ""
    micro = int((frac + "000000")[:6]) if frac else 0
    tzs = m.group(8)
    if tzs is None or tzs == "Z":
        off = timedelta(0)
    else:
        sign = 1 if tzs[0] == "+" else -1
        body = tzs[1:].replace(":", "")
        off = sign * timedelta(hours=int(body[:2]), minutes=int(body[2:4]))
    try:
        return datetime(y, mo, d, h, mi, s, micro, tzinfo=timezone(off))
    except ValueError:
        return None


def load_tz(name, offset_hours):
    """优先用 zoneinfo；老 Python / 缺 tzdata 时退回固定偏移（默认 +08:00）。"""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 —— 没有 tzdata 不是错误，退回固定偏移
        try:
            off = float(offset_hours)
            return timezone(timedelta(hours=off))
        except (TypeError, ValueError):
            raise SystemExit("--utc-offset 解析失败：%r" % (offset_hours,))


def day_bounds(day, tz):
    """本地自然日 [day 00:00, day+1 00:00) → 两个 UTC 时刻。"""
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def fmt_local(dt, tz, with_date=True):
    if dt is None:
        return UNREADABLE
    local = dt.astimezone(tz)
    return local.strftime("%Y-%m-%d %H:%M:%S" if with_date else "%H:%M:%S")


# --------------------------------------------------------------------------
# 聚合桶：一个「今日」、一个「昨日」，同一份文件一遍扫完
# --------------------------------------------------------------------------
class Bucket(object):
    def __init__(self, label):
        self.label = label
        # Suricata（event_type=alert）
        self.alert_total = 0            # 全部 alert（含心跳）
        self.alert_hb = 0               # 心跳自噪声
        self.sev = Counter()            # 真实告警按 severity
        self.src = Counter()            # 真实告警按源 IP（原始值）
        self.src_ports = defaultdict(set)
        self.port = Counter()           # 真实告警按目标端口
        self.rule = Counter()           # 真实告警按 (sid, signature)
        self.rule_hb = Counter()        # 心跳按 (sid, signature)
        # Cowrie（eventid=cowrie.*）
        self.honey_events = 0
        self.sess_connect = 0
        self.sess_ids = set()           # 去重会话（任何 cowrie 事件里的 session 都收）
        self.login_ok = 0
        self.login_fail = 0
        self.login_src = Counter()
        self.commands = 0
        self.pw_struct = Counter()          # 结构 → 次数（失败+成功）
        self.pw_struct_ok = Counter()
        self.pw_struct_fail = Counter()
        self.pw_unique = set()              # 只在内存里用于「唯一口令数」，不落盘
        self.pw_user_same = 0               # 口令 == 用户名（结构层面的弱口令信号）
        self.pw_weak = 0                    # 命中内置弱口令小表（只给计数）

    # --- 概览用的派生值 ---
    def real_alerts(self):
        return self.alert_total - self.alert_hb

    def high(self):
        return self.sev.get(1, 0)


class SourceStat(object):
    """一个数据源的读取结果。ok=False 时 reason 是给人看的原因原文。"""

    def __init__(self, name, spec):
        self.name = name
        self.spec = spec
        self.ok = False
        self.reason = None
        self.paths = []
        self.lines = 0
        self.parsed = 0
        self.bad = 0
        self.events = 0                 # 落在「今日+昨日」窗口内的事件数
        self.min_ts = None
        self.max_ts = None

    def fail(self, reason):
        self.ok = False
        self.reason = reason
        return self


# --------------------------------------------------------------------------
# 数据源定位：文件 / 目录 / glob / stdin 都认；读不到就把原因写进 reason
# --------------------------------------------------------------------------
def resolve_source(spec, prefix):
    """返回 (paths, reason)。reason 为 None 表示定位成功。"""
    if spec == "-":
        return ["-"], None
    if not isinstance(spec, str) or not spec.strip():
        return [], "路径为空"
    if any(ch in spec for ch in "*?["):
        hits = sorted(p for p in glob.glob(spec) if os.path.isfile(p))
        return (hits, None) if hits else ([], "没有文件匹配 `%s`" % spec)
    if os.path.isdir(spec):
        try:
            names = sorted(os.listdir(spec))
        except OSError as exc:
            return [], "目录不可读（%s）" % exc
        hits = [os.path.join(spec, n) for n in names if n.startswith(prefix)
                and os.path.isfile(os.path.join(spec, n))]
        if not hits:
            return [], "目录里没有以 `%s` 开头的文件（共 %d 个条目）" % (prefix, len(names))
        return hits, None
    if not os.path.exists(spec):
        return [], "文件不存在"
    if not os.path.isfile(spec):
        return [], "不是普通文件"
    if not os.access(spec, os.R_OK):
        return [], "无读权限（本进程身份读不了）"
    return [spec], None


def iter_json_lines(paths):
    """逐行读 JSON Lines：产出 (path, lineno, obj_or_None)，坏行 obj 为 None。"""
    for path in paths:
        if path == "-":
            fh = sys.stdin
            close = False
        else:
            try:
                fh = open(path, "r", encoding="utf-8", errors="replace")
            except OSError as exc:
                yield path, 0, {"__error__": "打开失败（%s）" % exc}
                return
            close = True
        try:
            for lineno, line in enumerate(fh, 1):
                if not line.strip():
                    continue  # 空行不算坏行，也不计数
                try:
                    obj = json.loads(line)
                except ValueError:
                    yield path, lineno, None
                    continue
                # 行是合法 JSON 但不是对象：算坏行，不喂给聚合
                yield path, lineno, obj if isinstance(obj, dict) else None
        finally:
            if close:
                try:
                    fh.close()
                except OSError:
                    pass


def is_heartbeat(ev, hb_sids, hb_dst):
    sid = as_int(dig(ev, "alert", "signature_id"))
    if sid is not None and sid in hb_sids:
        return True
    dst = ev.get("dest_ip")
    if isinstance(dst, str) and dst in hb_dst:
        return True
    return False


def feed_suricata(bucket, ev, hb_sids, hb_dst):
    if ev.get("event_type") != "alert":
        return
    sid = as_int(dig(ev, "alert", "signature_id"))
    sig = dig(ev, "alert", "signature") or "（无签名名）"
    sev = as_int(dig(ev, "alert", "severity"))
    src = ev.get("src_ip")
    dport = as_int(ev.get("dest_port"))
    bucket.alert_total += 1
    if is_heartbeat(ev, hb_sids, hb_dst):
        bucket.alert_hb += 1
        bucket.rule_hb[(sid, sig)] += 1
        return
    bucket.sev[sev] += 1
    if src:
        bucket.src[src] += 1
        bucket.src_ports[src].add(dport)
    if dport is not None:
        bucket.port[dport] += 1
    bucket.rule[(sid, sig)] += 1


def pw_shape(pw):
    """口令结构：只给「字符类别 + 长度分桶」，永不返回原文。"""
    if pw is None:
        return "无口令字段"
    s = str(pw)
    n = len(s)
    if n == 0:
        return "空口令"
    bucket = "<6 位" if n < 6 else "6-8 位" if n <= 8 else "9-12 位" if n <= 12 else ">12 位"
    if s.isdigit():
        kind = "纯数字"
    elif s.isalpha():
        if s.islower():
            kind = "纯小写字母"
        elif s.isupper():
            kind = "纯大写字母"
        else:
            kind = "大小写混合字母"
    elif not any(not c.isalnum() for c in s):
        kind = "字母+数字"
    elif any(c.isalpha() for c in s) and any(c.isdigit() for c in s):
        kind = "字母+数字+符号"
    elif any(c.isalpha() for c in s):
        kind = "字母+符号"
    elif any(c.isdigit() for c in s):
        kind = "数字+符号"
    else:
        kind = "纯符号"
    return "%s · %s" % (kind, bucket)


def feed_cowrie(bucket, ev):
    eid = ev.get("eventid") or ""
    sid = ev.get("session")
    if sid:
        bucket.sess_ids.add(sid)
    bucket.honey_events += 1
    if eid == "cowrie.session.connect":
        bucket.sess_connect += 1
        return
    if eid == "cowrie.command.input":
        bucket.commands += 1
        return
    if eid in ("cowrie.login.success", "cowrie.login.failed"):
        src = ev.get("src_ip")
        if src:
            bucket.login_src[src] += 1
        pw = ev.get("password")
        user = ev.get("username")
        shape = pw_shape(pw)
        bucket.pw_struct[shape] += 1
        if eid == "cowrie.login.success":
            bucket.login_ok += 1
            bucket.pw_struct_ok[shape] += 1
        else:
            bucket.login_fail += 1
            bucket.pw_struct_fail[shape] += 1
        if isinstance(pw, str) and pw:
            bucket.pw_unique.add(pw)
            if isinstance(user, str) and user and pw == user:
                bucket.pw_user_same += 1
            if pw.strip().lower() in WEAK_PASSWORDS:
                bucket.pw_weak += 1


# --------------------------------------------------------------------------
# 扫一遍文件，把今日/昨日两个桶填满
# --------------------------------------------------------------------------
def scan_sources(args, tz, today, ys, ye, ts):
    """ts = 今日窗口起点（UTC）；窗口 = [ys, ye) 覆盖昨日+今日两段。"""
    win_start, win_end = ys, ye
    today_start = ts
    buckets = {"today": Bucket("今日"), "yesterday": Bucket("昨日")}
    hb_sids = set(int(x) for x in re.findall(r"\d+", args.heartbeat_sids or ""))
    hb_dst = set(x.strip() for x in (args.heartbeat_dst or "").split(",") if x.strip())

    # ---- Suricata ----
    eve = SourceStat("eve.json", ",".join(args.eve))
    paths, reason = [], None
    for spec in args.eve:
        p, r = resolve_source(spec, "eve")
        paths.extend(p)
        if r:
            reason = "%s（参数 `%s`）" % (r, spec)
    if not paths:
        eve.fail(reason or "路径没有给出")
    else:
        eve.paths = paths
        eve.ok = True
        for _p, _ln, obj in iter_json_lines(paths):
            eve.lines += 1
            if obj is None:
                eve.bad += 1
                continue
            if "__error__" in obj:
                eve.ok = False
                eve.fail(obj["__error__"])
                continue
            eve.parsed += 1
            d = parse_ts(obj.get("timestamp"))
            if d is None:
                eve.bad += 1
                continue
            eve.min_ts = d if eve.min_ts is None or d < eve.min_ts else eve.min_ts
            eve.max_ts = d if eve.max_ts is None or d > eve.max_ts else eve.max_ts
            if not (win_start <= d < win_end):
                continue
            eve.events += 1
            feed_suricata(buckets["today"] if d >= today_start else buckets["yesterday"],
                          obj, hb_sids, hb_dst)
        if eve.ok and eve.parsed == 0:
            eve.fail("文件里没有可解析的 JSON 行（读到了 %d 行，全部不可用）" % eve.lines)

    # ---- Cowrie ----
    cow = SourceStat("cowrie.json", ",".join(args.cowrie))
    paths, reason = [], None
    for spec in args.cowrie:
        p, r = resolve_source(spec, "cowrie")
        paths.extend(p)
        if r:
            reason = "%s（参数 `%s`）" % (r, spec)
    if not paths:
        cow.fail(reason or "路径没有给出")
    else:
        cow.paths = paths
        cow.ok = True
        for _p, _ln, obj in iter_json_lines(paths):
            cow.lines += 1
            if obj is None:
                cow.bad += 1
                continue
            if "__error__" in obj:
                cow.ok = False
                cow.fail(obj["__error__"])
                continue
            if not str(obj.get("eventid") or "").startswith("cowrie."):
                cow.bad += 1
                continue
            cow.parsed += 1
            d = parse_ts(obj.get("timestamp"))
            if d is None:
                cow.bad += 1
                continue
            cow.min_ts = d if cow.min_ts is None or d < cow.min_ts else cow.min_ts
            cow.max_ts = d if cow.max_ts is None or d > cow.max_ts else cow.max_ts
            if not (win_start <= d < win_end):
                continue
            cow.events += 1
            feed_cowrie(buckets["today"] if d >= today_start else buckets["yesterday"], obj)
        if cow.ok and cow.parsed == 0:
            cow.fail("文件里没有 cowrie.* 事件（读到了 %d 行）" % cow.lines)

    # ---- 一致性巡检结果（只要它自己的汇总字段）----
    ci = SourceStat("ci/latest.json", args.ci)
    p, r = resolve_source(args.ci, "latest")
    ci_data, ci_err = None, r
    if p and p[0] == "-":
        p = []
        ci_err = "不支持从 stdin 读巡检结果"
    if p:
        try:
            with open(p[0], "r", encoding="utf-8", errors="replace") as fh:
                ci_data = json.loads(fh.read())
            ci.paths = [p[0]]
            ci.ok = isinstance(ci_data, dict)
            if not ci.ok:
                ci_err = "文件内容不是 JSON 对象"
        except OSError as exc:
            ci_err = "打开失败（%s）" % exc
        except ValueError as exc:
            ci_err = "JSON 解析失败（%s）" % exc
    if not ci.ok:
        ci.fail(ci_err or "未给出")
    return {"eve": eve, "cowrie": cow, "ci": ci}, buckets, ci_data


# --------------------------------------------------------------------------
# 覆盖面判断：文件不一定覆盖「今日」或「昨日」（轮转/只留当天）
# --------------------------------------------------------------------------
def day_status(stat, start, end, tz):
    """某一天的窗口在这份文件里是否成立。

    返回 {"reason": 整日不成立的原因 or None, "partial": 只有半段的描述 or None}。
    判据只用文件里真实出现的事件时间戳：
      - 最晚事件都早于窗口起点 → 该日完全没覆盖（轮转后只剩别的日子）；
      - 读到的事件全部晚于窗口终点 → 文件只覆盖之后的时段（少见，但要认）；
      - 有事件跨越窗口、但最早晚于起点 / 最晚早于终点 → 只覆盖半段。
    reason 与 partial 互斥：整日不成立就不再谈半段。
    """
    if not stat.ok:
        return {"reason": "数据源读不到", "partial": None}
    if stat.max_ts is not None and stat.max_ts <= start:
        return {"reason": "文件未覆盖该日（最晚事件 %s，早于窗口起点）" % fmt_local(stat.max_ts, tz),
                "partial": None}
    if stat.min_ts is not None and stat.min_ts >= end:
        return {"reason": "文件未覆盖该日（最早事件 %s，不早于窗口终点）" % fmt_local(stat.min_ts, tz),
                "partial": None}
    bits = []
    if stat.min_ts is not None and stat.min_ts > start:
        bits.append("缺 %s → %s" % (fmt_local(start, tz), fmt_local(stat.min_ts, tz)))
    if stat.max_ts is not None and stat.max_ts < end:
        bits.append("缺 %s → %s" % (fmt_local(stat.max_ts, tz), fmt_local(end, tz)))
    return {"reason": None, "partial": "；".join(bits) if bits else None}


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------
def top_source_groups(bucket, limit=10):
    """Top 来源：按掩码后的前缀聚合（`/24` 或 IPv6 前 4 段）。

    同一段里并列多个原始 IP 时掩码会让表格出现几行完全一样的标签；按段聚合 + 附「原始 IP 数」
    才读得懂。计数、去重仍用原始 IP；展示用 mask_ip。
    """
    groups = {}
    for ip, cnt in bucket.src.items():
        key = mask_ip(ip)
        g = groups.setdefault(key, {"ips": set(), "cnt": 0, "ports": set()})
        g["ips"].add(ip)
        g["cnt"] += cnt
        g["ports"] |= {p for p in bucket.src_ports.get(ip, set()) if p is not None}
    rows = []
    for key, g in groups.items():
        ports = g["ports"]
        main_port = max(ports) if ports else None
        rows.append((key, len(g["ips"]), g["cnt"], ports, main_port))
    rows.sort(key=lambda r: (-r[2], -len(r[3]), r[0]))
    return rows[:limit]


def top_sources(bucket, limit=10):
    rows = []
    for ip, cnt in bucket.src.items():
        ports = {p for p in bucket.src_ports.get(ip, set()) if p is not None}
        main_port = None
        if ports:
            main_port = max(ports)
        rows.append((ip, cnt, ports, main_port))
    rows.sort(key=lambda r: (-r[1], -len(r[2]), r[0]))
    return rows[:limit]


def build_report(ctx):
    tz = ctx["tz"]
    today = ctx["today"]
    ydate = today - timedelta(days=1)
    buckets = ctx["buckets"]
    b, y = buckets["today"], buckets["yesterday"]
    stats = ctx["stats"]
    eve, cow, ci = stats["eve"], stats["cowrie"], stats["ci"]
    ci_data = ctx["ci_data"]
    args = ctx["args"]
    now = ctx["now"]
    ts, te = ctx["today_start"], ctx["today_end"]
    ystart = ctx["yesterday_start"]

    add_lines = []
    add = add_lines.append

    def v_or(value, reason=None):
        """数值 or 「读不到（原因）」——不存在「0 冒充」这条路径。"""
        if reason:
            return "%s（%s）" % (UNREADABLE, reason)
        return fmt_num(value)

    # 数据源覆盖状态：今日 / 昨日各自判，整日不成立（reason）与只覆盖半段（partial）分开
    eve_day = day_status(eve, ts, te, tz)
    eve_reason, cov_eve = eve_day["reason"], eve_day["partial"]
    cow_day = day_status(cow, ts, te, tz)
    cow_reason, cov_cow = cow_day["reason"], cow_day["partial"]
    y_eve_day = day_status(eve, ystart, ts, tz)
    y_eve_reason, y_cov_eve = y_eve_day["reason"], y_eve_day["partial"]
    y_cow_day = day_status(cow, ystart, ts, tz)
    y_cow_reason, y_cov_cow = y_cow_day["reason"], y_cow_day["partial"]

    # ---- 标题 ----
    add("# 安全日报 · %s" % today.strftime("%Y-%m-%d"))
    add("")
    add("> 统计窗口（今日）：`%s 00:00` → `%s 00:00`（%s，含头不含尾）" % (
        today.strftime("%Y-%m-%d"), te.astimezone(tz).strftime("%Y-%m-%d"), ctx["tz_name"]))
    add("> 生成时间：%s ｜ 数据源：本机文件（离线读，不联网、不做任何处置）" % now.strftime("%Y-%m-%d %H:%M:%S"))
    add("> 输入参数：`--eve %s` ｜ `--cowrie %s` ｜ `--ci %s`" % (
        args.eve and ",".join(args.eve) or "—",
        args.cowrie and ",".join(args.cowrie) or "—", args.ci))
    add("")
    missing = [name for name, st in (("eve.json", eve), ("cowrie.json", cow), ("ci/latest.json", ci)) if not st.ok]
    if missing:
        add("> ⚠️ 有 %d 个数据源读不到：%s —— 下文对应项写「%s（原因）」，不补数、不用 0 冒充。" % (
            len(missing), "、".join(missing), UNREADABLE))
        add("")

    # ---- 1. 今日概览 ----
    add("## 1. 今日概览")
    add("")
    add("| 指标 | 数值 | 口径（文件 · 字段 · 窗口） |")
    add("|---|---|---|")
    add("| 告警总数（含心跳自噪声） | %s | `eve.json` · `event_type=alert` · **今日** |" % v_or(b.alert_total, eve_reason))
    add("| 其中：心跳自噪声 | %s | SID %s / 目标 %s；见 §5 的口径说明 |" % (
        v_or(b.alert_hb, eve_reason), cell(args.heartbeat_sids), cell(args.heartbeat_dst)))
    add("| 真实告警数 | %s | 告警总数 − 心跳自噪声 · **今日** |" % v_or(b.real_alerts(), eve_reason))
    add("| 去重源 IP（真实告警） | %s | `alert.src_ip` 去重后计数 · **今日** |" % v_or(len(b.src), eve_reason))
    add("| 高危数（severity=1） | %s | 真实告警里 `alert.severity=1` 的条数 · **今日** |" % v_or(b.high(), eve_reason))
    add("| 蜜罐会话数（去重） | %s | `cowrie.*` 事件里的 `session` 去重 · **今日** |" % v_or(len(b.sess_ids), cow_reason))
    add("")
    if not eve.ok:
        add("> ⚠️ Suricata 读不到：**%s（%s）**。今日概览里的告警/来源 IP/高危三格一律不填数。" % (
            eve.name, eve.reason))
        add("")
    elif cov_eve:
        add("> ⚠️ Suricata 今日只覆盖半段：**%s（%s）**。下面的计数是这半段里读到的，不等于全天。"
            % (eve.name, cov_eve))
        add("")

    # 蜜罐细分
    add("### 1.1 蜜罐细分（Cowrie）")
    add("")
    add("| 项 | 数值 | 口径 |")
    add("|---|---|---|")
    add("| 会话建立（`cowrie.session.connect`） | %s | 今日 |" % v_or(b.sess_connect, cow_reason))
    add("| 登录尝试（成功 / 失败） | %s / %s | 今日；**蜜罐接受一切口令，成功 ≠ 被攻破** |" % (
        v_or(b.login_ok, cow_reason), v_or(b.login_fail, cow_reason)))
    add("| 命令输入（`cowrie.command.input`） | %s | 今日 |" % v_or(b.commands, cow_reason))
    add("| 蜜罐源 IP（去重） | %s | 今日登录尝试的 `src_ip` 去重 |" % v_or(len(b.login_src), cow_reason))
    add("| 蜜罐事件总数 | %s | 今日全部 `cowrie.*` 事件 |" % v_or(b.honey_events, cow_reason))
    add("")
    if not cow_reason and cov_cow:
        add("> ⚠️ Cowrie 今日只覆盖半段：**%s（%s）**。" % (cow.name, cov_cow))
        add("")

    # ---- 2. Top 10 来源 ----
    add("## 2. Top 10 来源（真实告警，已掩码）")
    add("")
    add("> 口径：`eve.json` 里 `event_type=alert` 且**不是**心跳的 `src_ip`，按今日条数排序；"
        "展示按仓库既有规则「保留前三段 + 末段换 `x`」（`a.b.c.d` → `a.b.c.x`），"
        "**同一掩码前缀（/24）合并成一行**，并标出其中有多少个不同的原始 IP；去重与计数用原始值。")
    add("")
    add("| # | 来源前缀（已掩码） | 真实告警 | 其中原始 IP | 独立目标端口 | 主要目标端口 |")
    add("|---|---|---|---|---|---|")
    if eve_reason:
        add("| — | %s | — | — | — | — |" % v_or(None, eve_reason))
    else:
        rows = top_source_groups(b, args.top_sources)
        for i, (key, n_ips, cnt, ports, main_port) in enumerate(rows, 1):
            add("| %d | `%s` | %s | %d | %d | %s |" % (
                i, key, fmt_num(cnt), n_ips, len(ports),
                ("`%s` %s" % (main_port, SERVICES.get(main_port, ""))).strip() if main_port is not None else "—"))
        if not rows:
            add("| — | 今日真实告警 0 条 | 0 | 0 | — | — |")
    add("")
    if not eve_reason and b.rule_hb:
        add("（心跳自噪声 %s 条按 `--heartbeat-dst` 计为内部链路，不进上表；按 SID 拆开见 §5。）"
            % fmt_num(b.alert_hb))
        add("")
    if not eve_reason and cov_eve:
        add("> `*半段` 提醒：今日 Suricata 只覆盖 %s。" % cov_eve)
        add("")

    # ---- 3. Top 5 被攻击端口 ----
    add("## 3. Top 5 被攻击端口（真实告警）")
    add("")
    add("| # | 目标端口 | 服务（常识映射） | 真实告警 | 占比（真实告警） |")
    add("|---|---|---|---|---|")
    if eve_reason:
        add("| — | %s | — | — | — |" % v_or(None, eve_reason))
    else:
        ports = sorted(b.port.items(), key=lambda kv: (-kv[1], kv[0]))[:args.top_ports]
        real = b.real_alerts()
        for i, (port, cnt) in enumerate(ports, 1):
            share = pct(cnt, real)
            add("| %d | `%s` | %s | %s | %s |" % (
                i, port, SERVICES.get(port, "未知服务"), fmt_num(cnt),
                ("%.1f%%" % share) if share is not None else "—"))
        if not ports:
            add("| — | %s | — | 0 | — |" % (
                "今日真实告警 0 条" if real == 0 else "今日真实告警 %s 条，但都没读到目标端口" % fmt_num(real)))
    add("")
    if not eve_reason and cov_eve:
        add("> 今日 Suricata 只覆盖半段：%s；本表是这半段里的分布。" % cov_eve)
        add("")

    # ---- 4. 口令结构分布 ----
    add("## 4. 口令结构分布（只写结构，不写明文）")
    add("")
    add("> 来源：`cowrie.json` 的 `cowrie.login.failed` / `cowrie.login.success` 里的 `password` 字段，"
        "**只在内存里做分类，报告里不出现任何口令原文**；结构 = 字符类别 + 长度分桶。")
    add("")
    add("| # | 口令结构 | 次数 | 占比 | 其中失败 | 其中成功 |")
    add("|---|---|---|---|---|---|")
    if cow_reason:
        add("| — | %s | — | — | — | — |" % v_or(None, cow_reason))
    else:
        total = b.login_ok + b.login_fail
        structs = sorted(b.pw_struct.items(), key=lambda kv: (-kv[1], kv[0]))
        for i, (shape, cnt) in enumerate(structs, 1):
            share = pct(cnt, total)
            add("| %d | %s | %s | %s | %s | %s |" % (
                i, cell(shape), fmt_num(cnt), ("%.1f%%" % share) if share is not None else "—",
                fmt_num(b.pw_struct_fail.get(shape, 0)), fmt_num(b.pw_struct_ok.get(shape, 0))))
        if not structs:
            add("| — | 今日无登录尝试 | 0 | — | — | — |")
    add("")
    if not cow_reason:
        add("结构层面的旁证（都只是计数，不涉及具体值）：唯一口令 **%s** 个；"
            "口令与用户名相同 **%s** 次；命中内置高频弱口令小表 **%s** 次。" % (
                fmt_num(len(b.pw_unique)), fmt_num(b.pw_user_same), fmt_num(b.pw_weak)))
        add("")

    # ---- 5. 规则命中排行 ----
    add("## 5. 规则命中排行（心跳自噪声 vs 真实告警）")
    add("")
    add("> 为什么要分开：%s。**心跳不是攻击**，把它算进 Top 榜会让「Top 规则」永远是同一条。"
        "本节把心跳单独排在最前，真实告警另外排序。" % HB_BASELINE_TEXT)
    add("")
    add("| # | SID | 规则名 | 命中 | 占全部告警 | 分类 |")
    add("|---|---|---|---|---|---|")
    if eve_reason:
        add("| — | — | %s | — | — | — |" % v_or(None, eve_reason))
    else:
        total = b.alert_total
        i = 0
        for (sid, sig), cnt in sorted(b.rule_hb.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            i += 1
            share = pct(cnt, total)
            add("| %d | `%s` | %s | %s | %s | **心跳自噪声** |" % (
                i, sid if sid is not None else "?", cell(scrub_ips(sig)), fmt_num(cnt),
                ("%.1f%%" % share) if share is not None else "—"))
        for (sid, sig), cnt in sorted(b.rule.items(), key=lambda kv: (-kv[1], str(kv[0])))[:10]:
            i += 1
            share = pct(cnt, total)
            add("| %d | `%s` | %s | %s | %s | 真实告警 |" % (
                i, sid if sid is not None else "?", cell(scrub_ips(sig)), fmt_num(cnt),
                ("%.1f%%" % share) if share is not None else "—"))
        if i == 0:
            add("| — | — | 今日无 alert | 0 | — | — |")
        if cov_eve:
            add("| — | — | （今日只覆盖半段：%s） | — | — | — |" % cell(cov_eve))
    add("")
    if not eve_reason:
        share = pct(b.alert_hb, b.alert_total)
        if b.alert_hb == 0:
            why = []
            why.append("可能是 SID %s 的抑制已生效（`1000108` 是 opt-in 规则）" % cell(args.heartbeat_sids))
            why.append("也可能今天确实没跑云 agent")
            if not (args.heartbeat_sids or args.heartbeat_dst):
                why = ["本次**没传** `--heartbeat-sids` / `--heartbeat-dst`，心跳本来就没法被识别；"
                       "要分开算心跳就补上这两个参数（心跳 SID 见 §5 上方的基线说明）"]
            add("**心跳一条都没命中**：%s。真实告警 %s 条。%s" % (
                "，".join(why), fmt_num(b.real_alerts()),
                "（注意：抑制生效时「心跳占比」应读作 0，不是没有心跳流量。）"))
        elif share is not None:
            add("心跳自噪声 %s 条，占今日全部告警 **%.1f%%**（同口径基线 %.1f%%，%s）。" % (
                fmt_num(b.alert_hb), share, HB_BASELINE_SHARE,
                "与基线基本一致" if abs(share - HB_BASELINE_SHARE) <= 1.5 else "与基线偏离，值得看一眼"))
        add("")
    if eve.ok and b.rule:
        known = [(sid, KNOWN_SIDS[sid]) for sid, _sig in b.rule if sid in KNOWN_SIDS]
        if known:
            add("命中里的本仓库私有规则：%s。" % "；".join(
                "`%s` %s" % (sid, desc) for sid, desc in known[:6]))
            add("")

    # ---- 6. 与昨日对比 ----
    add("## 6. 与昨日对比（%s）" % ydate.strftime("%Y-%m-%d"))
    add("")
    add("> 昨日和今日用**同一份文件、同一个口径**现算；哪一天在文件里不成立就写「未取到 + 原因」，"
        "只覆盖半段的写「*半段」并在本行脚注里给出缺的时间段，不给自造基准、也不拿半段冒充全天。")
    add("")
    add("| 指标 | 今日 | 昨日 | 变化 |")
    add("|---|---|---|---|")
    rows = (
        ("告警总数（含心跳）", b.alert_total, y.alert_total, eve_reason, y_eve_reason, cov_eve, y_cov_eve),
        ("心跳自噪声", b.alert_hb, y.alert_hb, eve_reason, y_eve_reason, cov_eve, y_cov_eve),
        ("真实告警", b.real_alerts(), y.real_alerts(), eve_reason, y_eve_reason, cov_eve, y_cov_eve),
        ("去重源 IP（真实）", len(b.src), len(y.src), eve_reason, y_eve_reason, cov_eve, y_cov_eve),
        ("高危（severity=1）", b.high(), y.high(), eve_reason, y_eve_reason, cov_eve, y_cov_eve),
        ("蜜罐会话（去重）", len(b.sess_ids), len(y.sess_ids), cow_reason, y_cow_reason, cov_cow, y_cov_cow),
        ("登录尝试", b.login_ok + b.login_fail, y.login_ok + y.login_fail,
         cow_reason, y_cow_reason, cov_cow, y_cov_cow),
    )
    partial_footnotes = []
    for label, tv, yv, tr, yr, tp, yp in rows:
        def day_cell(value, reason, partial_desc):
            if reason:
                return "%s（%s）" % (UNREADABLE, reason)
            if partial_desc:
                return "%s *半段" % fmt_num(value)
            return fmt_num(value)

        def delta_cell():
            if tr or yr:
                return "—"
            if tp or yp:
                return "暂不可比"
            return delta_ratio_str(tv, yv)

        add("| %s | %s | %s | %s |" % (
            label, day_cell(tv, tr, tp), day_cell(yv, yr, yp), delta_cell()))
        if tp or yp:
            partial_footnotes.append((label, tp, yp))
    if partial_footnotes:
        add("")
        for label, tp, yp in partial_footnotes:
            bits = []
            if tp:
                bits.append("今日%s" % tp)
            if yp:
                bits.append("昨日%s" % yp)
            add("- `*半段`（%s）：%s。缺口时段里没有任何事件被读到 —— 可能只是没日志，"
                "也可能确实没攻击；半段数字不等于全天。" % (
                label, "；".join(bits)))
    add("")

    # ---- 7. 一句话结论 ----
    add("## 7. 一句话结论")
    add("")
    bits = []
    if not eve_reason:
        if b.alert_total:
            bits.append("今日 alert %s 条，其中心跳自噪声 %s 条（%.1f%%）、真实告警 %s 条、涉及去重源 IP %s 个、高危 %s 条" % (
                fmt_num(b.alert_total), fmt_num(b.alert_hb), pct(b.alert_hb, b.alert_total) or 0.0,
                fmt_num(b.real_alerts()), fmt_num(len(b.src)), fmt_num(b.high())))
        else:
            bits.append("今日 0 条 alert（真实告警 0、高危 0）")
    if not cow_reason:
        parts = "蜜罐会话 %s 个、登录尝试 %s 次（成功 %s / 失败 %s）" % (
            fmt_num(len(b.sess_ids)), fmt_num(b.login_ok + b.login_fail),
            fmt_num(b.login_ok), fmt_num(b.login_fail))
        if b.login_fail and b.login_ok > b.login_fail * 10:
            parts += "，成功远多于失败（该蜜罐接受一切口令，不能读成「被打穿」）"
        bits.append(parts)
    if not eve_reason and b.port:
        top_port, top_cnt = sorted(b.port.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        bits.append("被攻击最多的端口是 `%s`（%s，%s 条）" % (
            top_port, SERVICES.get(top_port, "未知服务"), fmt_num(top_cnt)))
    if not eve_reason and b.src:
        top = top_sources(b, 1)[0]
        top_ip, top_cnt = top[0], top[1]
        share = pct(top_cnt, b.real_alerts())
        bits.append("最活跃来源 `%s`（%s 条，占真实告警 %s）" % (
            mask_ip(top_ip), fmt_num(top_cnt), ("%.1f%%" % share) if share is not None else "—"))
    if not eve_reason and not y_eve_reason and not cov_eve and not y_cov_eve:
        d = b.real_alerts() - y.real_alerts()
        if d:
            bits.append("真实告警较昨日%s %s 条" % ("上升" if d > 0 else "下降", format(abs(d), ",")))
        else:
            bits.append("真实告警与昨日持平")
    elif not eve_reason and not y_eve_reason:
        bits.append("今日/昨日只有半段覆盖，「与昨日对比」暂不可比")
    if cov_eve:
        bits.append("覆盖缺口：今日 Suricata %s" % cov_eve)
    if bits:
        add("**%s。**" % "；".join(bits))
    else:
        add("**今日三个数据源全部读不到，给不出结论**（原因见 §8；这是「没取到」，不是「没攻击」）。")
    add("")
    if args.note:
        add("> 人工备注：%s" % args.note)
        add("")

    # ---- 8. 取数状态 ----
    add("## 8. 取数状态（读不到的原因原文）")
    add("")
    add("| 数据源 | 参数 | 状态 | 行数 / 可用 | 覆盖区间（%s） |" % ctx["tz_name"])
    add("|---|---|---|---|---|")
    for name, st in (("Suricata eve.json", eve), ("Cowrie log", cow), ("一致性 CI latest.json", ci)):
        if st.ok:
            span = "%s ~ %s" % (fmt_local(st.min_ts, tz) if st.min_ts else "—",
                                fmt_local(st.max_ts, tz) if st.max_ts else "—")
            if st.min_ts is None and st.max_ts is None:
                span = "不适用（单文件快照）"
            state = "读到"
        else:
            span = "—"
            state = "%s（%s）" % (UNREADABLE, cell(st.reason or "未知"))
        detail = "%s / %s" % (fmt_num(st.lines), fmt_num(st.parsed)) if st.lines else "—"
        add("| %s | `%s` | %s | %s | %s |" % (name, cell(st.spec), state, detail, span))
    add("")
    add("坏行（JSON 解析失败 / 时间戳读不出）会被跳过并计数：eve.json %s 行、cowrie %s 行。"
        "坏行不为 0 时上面的数字是**下限**。" % (fmt_num(eve.bad), fmt_num(cow.bad)))
    add("")
    # 覆盖旗标（半段 / 缺日都用 day_status 的判据，不重复手写条件）
    flags = []
    if eve.ok and cov_eve:
        flags.append("eve.json 今日只覆盖半段：%s" % cov_eve)
    if eve.ok and y_cov_eve:
        flags.append("eve.json 昨日只覆盖半段：%s（§6 的昨日列据此标 *半段）" % y_cov_eve)
    if cow.ok and cov_cow:
        flags.append("cowrie 今日只覆盖半段：%s" % cov_cow)
    if ci.ok and isinstance(ci_data, dict):
        try:
            ci_ts_f = parse_ts(ci_data.get("ts"))
        except Exception:  # noqa: BLE001
            ci_ts_f = None
        if ci_ts_f is not None and ci_ts_f > ctx["now_utc"]:
            flags.append("ci/latest.json 的 ts 在未来（%s）—— 时钟不同步，别拿它算新鲜度"
                         % fmt_local(ci_ts_f, tz))
    if flags:
        for f in flags:
            add("- ⚠️ %s" % f)
        add("")
    # 巡检状态
    add("### 8.1 一致性巡检（`consistency-check`）")
    add("")
    if ci.ok and isinstance(ci_data, dict):
        ci_ts = parse_ts(ci_data.get("ts"))
        failed = ci_data.get("failed") or []
        age = None
        if ci_ts is not None:
            age = (ctx["now_utc"] - ci_ts).total_seconds() / 60.0
        checks = as_int(ci_data.get("checks"))
        ok_field = ci_data.get("ok")
        add("| 项 | 值 |")
        add("|---|---|")
        add("| 运行时间 | %s |" % (fmt_local(ci_ts, tz) if ci_ts else "未提供（`ts` 缺失或无法解析）"))
        add("| 结果 | `ok=%s` ｜ `checks=%s` ｜ 失败 %s 项 |" % (
            "未提供" if ok_field is None else ok_field,
            fmt_num(checks) if checks is not None else "未提供", fmt_num(len(failed))))
        integrity = ci_data.get("site_integrity")
        add("| 站点完整性 | `%s` ｜ %s |" % (
            "未提供" if integrity is None else cell(str(integrity)),
            cell(ci_data.get("site_integrity_detail") or "—")))
        if age is not None:
            if age < 0:
                add("| 距现在 | —（ts 在未来 %.0f 分钟，时钟不同步） |" % abs(age))
            else:
                add("| 距现在 | %.0f 分钟%s |" % (
                    age, "（>20 分钟 ⇒ 巡检可能没在跑）" if age > 20 else ""))
        add("")
        for item in failed[:10]:
            add("- 失败项：%s" % cell(scrub_ips(str(item))))
        if failed:
            add("")
    else:
        add("%s（%s）。" % (UNREADABLE, cell(ci.reason or "未知")))
        add("")

    # ---- 8.2 私有规则口径 ----
    add("### 8.2 本仓库私有规则（`detections/suricata/xk-lab.rules`）的识别口径")
    add("")
    add("| SID | 含义 | 本报告怎么归类 |")
    add("|---|---|---|")
    for sid in sorted(KNOWN_SIDS):
        kind = "**心跳自噪声**（抑制型，opt-in）" if sid in HB_SIDS_SET else "真实告警（命中了才进 §5 真实榜）"
        add("| `%s` | %s | %s |" % (sid, cell(KNOWN_SIDS[sid]), kind))
    add("")
    add("> SID 不在上表里的命中一律按真实告警统计；心跳只认 `--heartbeat-sids` 里的 SID（默认 `%s`）"
        "或 `--heartbeat-dst` 里的目标地址。" % cell(args.heartbeat_sids))
    add("")

    # ---- 9. 已知限制 ----
    add("## 9. 已知限制 / 口径")
    add("")
    add("- 「今日」按本地时区自然日切；事件时间戳带偏移就按事件自己的偏移换算，没有偏移标记的按 UTC 解释。")
    add("- 心跳自噪声按 SID（默认 `%s`）+ 目标地址（默认 `%s`）识别，两者都能用参数改；"
        "抑制生效时心跳为 0，报告会明说「不是没有心跳流量」。" % (
            cell(args.heartbeat_sids), cell(args.heartbeat_dst)))
    add("- 蜜罐 `login.success` ≠ 入侵成功：Cowrie 是假 shell，按设计接受任意口令。")
    add("- 「高危」= Suricata `severity=1`（ET 规则的 high）；severity 缺失的条目不计入高危，也不补猜。")
    add("- 日志轮转/截断时，某一天可能只覆盖半段：报告标 `*半段`、在 §6 脚注给出缺口时段、"
        "并在 §8 的覆盖旗标里复述；整日被轮转掉则写「%s（原因）」，不写 0。" % UNREADABLE)
    add("- **「未取到」与「真 0」严格区分**：只有文件读到、且该日窗口被覆盖时，0 才是 0；"
        "读不到一律写原因，半段一律标 `*半段`。")
    add("- 一致性巡检的 `ts` 距生成时间 >20 分钟 ⇒ 巡检可能没在跑；`ts` 在未来 ⇒ 时钟不同步（§8.1 会标）。")
    add("- Top 榜只覆盖今日文件里的事件；坏行（JSON 坏/时间戳坏）被跳过并计数，坏行不为 0 时数字是下限。")
    add("- 本报告不联网、不调用公开端点、不做任何封禁/处置；生成器只写报告文件（不写目录 index）。")
    add("- 心跳识别是 SID + 目标地址两条：换过云 agent 链路地址后，旧心跳可能落进真实告警，"
        "跨月统计别直接拿日报口径拼，改用周报或临时补 `--heartbeat-dst`。")
    add("")
    add("> 生成器：`scripts/daily-report.py`（python3 标准库，无第三方依赖），只读、不处置、不部署。")
    add("")
    return "\n".join(add_lines)


# --------------------------------------------------------------------------
# 静态页导出：正文渲染复用 scripts/weekly-report.py 的 render_md_html（同一套转换器），
# 页面模板沿用它的内联样式（CSS 原样搬，标题/导航按日报改）。
# --------------------------------------------------------------------------
def _load_weekly_renderer():
    """动态加载同目录的 weekly-report.py，只取 render_md_html；失败返回 (None, 原因)。"""
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(here, "weekly-report.py")
    if not os.path.isfile(cand):
        return None, "找不到 %s（正文渲染复用它）" % cand
    try:
        spec = importlib.util.spec_from_file_location("dsh_weekly_report", cand)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, "render_md_html", None)
        if not callable(fn):
            return None, "%s 里没有 render_md_html" % cand
        return fn, None
    except Exception as exc:  # noqa: BLE001 —— HTML 是附加产物，坏了不能让 .md 也跟着失败
        return None, "加载 %s 失败（%s: %s）" % (cand, type(exc).__name__, exc)


_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}


def _esc(t):
    return "".join(_ESC.get(c, c) for c in t)


# 与 scripts/weekly-report.py 的 _PAGE 同一套 CSS（内联），只改标题/导航/占位符写法
_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITLE}}</title>
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
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13.5px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:#101820;color:var(--mut);font-weight:600}
code{background:#101820;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:12.5px}
ul{padding-left:20px}
.nav{font-size:13px;color:var(--mut);margin-bottom:14px}
</style></head><body><main>
<div class="nav"><a href="/">← 回站点</a> · 安全日报 · 本页由 <code>scripts/daily-report.py</code> 离线生成，数据来自本机文件</div>
{{BODY}}
</main></body></html>
"""


def write_html_for(md_path, report):
    """写同名 .html；正文复用 weekly-report.py 的 render_md_html。

    故意不写目录 index.html：日报和周报可能落在同一个 /opt/secagent/reports/ 下，
    而 weekly-report.py 的 index.html 列的是 weekly-*.html —— 日报再写一个 index.html
    会把周报目录页顶掉。要目录页就单独指定 --out-dir，别共用。
    """
    render, why = _load_weekly_renderer()
    if render is None:
        sys.stderr.write("HTML 未生成：%s\n" % why)
        return None
    html_path = os.path.splitext(md_path)[0] + ".html"
    title = (report.split("\n", 1)[0].lstrip("# ").strip() or "安全日报")
    body = render(report)
    page = _PAGE.replace("{{TITLE}}", _esc(title)).replace("{{BODY}}", body)
    with open(html_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    return html_path


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------
class _Parser(argparse.ArgumentParser):
    """argparse 默认参数错退出 2，会和「全部读不到」的 2 撞车 —— 这里统一改成 4。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(4)


def expand_strftime(pattern, now):
    if "%" not in pattern:
        return pattern
    try:
        return now.strftime(pattern)
    except ValueError as exc:
        raise SystemExit("--out 时间格式非法：%s（%s）" % (pattern, exc))


def parse_day(spec, today):
    s = (spec or "").strip().lower()
    if s in ("", "today"):
        return today
    if s == "yesterday":
        return today - timedelta(days=1)
    try:
        return date.fromisoformat(spec.strip())
    except ValueError:
        raise SystemExit("--date 无法解析：%r（可用 today / yesterday / 2026-10-18）" % spec)


def main(argv=None):
    ap = _Parser(
        description="生成每日攻击日报（本地文件，离线，Markdown + HTML）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python3 daily-report.py\n"
               "  python3 daily-report.py --eve /var/lib/suricata/eve.json \\\n"
               "      --cowrie /opt/cowrie/logs/cowrie.json \\\n"
               "      --ci /opt/secagent/reports/ci/latest.json \\\n"
               "      --out /opt/secagent/reports/daily-%Y-%m-%d.md\n",
    )
    ap.add_argument("--eve", action="append", default=None, metavar="PATH",
                    help="Suricata eve.json（文件 / 目录 / glob 都行；默认 %s；可重复）" % EVE_DEFAULT)
    ap.add_argument("--cowrie", action="append", default=None, metavar="PATH",
                    help="Cowrie JSON Lines（默认 %s；可重复）" % COWRIE_DEFAULT)
    ap.add_argument("--ci", default=CI_DEFAULT, metavar="PATH",
                    help="一致性巡检结果 JSON（默认 %s；只用于「巡检状态」一节）" % CI_DEFAULT)
    ap.add_argument("--date", default="today",
                    help="报告日期：today（默认）/ yesterday / 2026-10-18")
    ap.add_argument("--out", metavar="PATH", help="写入 Markdown 文件（可含 %%Y-%%m-%%d 占位符）；缺省写 stdout")
    ap.add_argument("--out-dir", metavar="DIR", help="写入 DIR/daily-<日期>.md；与 --out 二选一")
    ap.add_argument("--tz", default=os.environ.get("TZ") or "Asia/Shanghai",
                    help="「今日」的时区名，默认 Asia/Shanghai（没有 tzdata 时退回 --utc-offset）")
    ap.add_argument("--utc-offset", type=float, default=8.0,
                    help="拿不到 --tz 时用的固定偏移（小时），默认 8")
    ap.add_argument("--top-sources", type=int, default=10, help="来源 IP Top N，默认 10")
    ap.add_argument("--top-ports", type=int, default=5, help="被攻击端口 Top N，默认 5")
    ap.add_argument("--heartbeat-sids", default=HB_SIDS_DEFAULT,
                    help="心跳自噪声的 SID 列表（逗号分隔），默认 %s" % HB_SIDS_DEFAULT)
    ap.add_argument("--heartbeat-dst", default=HB_DST_DEFAULT,
                    help="心跳自噪声的目标地址列表（逗号分隔），默认 %s" % HB_DST_DEFAULT)
    ap.add_argument("--note", default="", help="人工备注，写进报告导语之后（可选）")
    ap.add_argument("--no-html", action="store_true", help="只写 .md，不导出同名 .html")
    args = ap.parse_args(argv)

    if args.out and args.out_dir:
        sys.stderr.write("参数冲突：--out 与 --out-dir 只能给一个\n")
        return 4
    if args.eve is None:
        args.eve = [EVE_DEFAULT]
    if args.cowrie is None:
        args.cowrie = [COWRIE_DEFAULT]
    if args.top_sources <= 0 or args.top_ports <= 0:
        sys.stderr.write("参数错误：--top-sources / --top-ports 必须 > 0\n")
        return 4
    if args.heartbeat_sids != HB_SIDS_DEFAULT:
        given = set(int(x) for x in re.findall(r"\d+", args.heartbeat_sids or ""))
        if not given:
            sys.stderr.write("[提示] --heartbeat-sids 为空：一条心跳都不会被识别，心跳占比会读成 0。\n")
        elif 2013031 not in given:
            sys.stderr.write("[提示] --heartbeat-sids 里没有 2013031（已知 94.9%% 心跳的 SID）；"
                             "心跳占比会偏低。默认值是 %s\n" % HB_SIDS_DEFAULT)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass

    now = datetime.now().astimezone()
    try:
        day = parse_day(args.date, now.date())
    except SystemExit as exc:
        sys.stderr.write("%s\n" % exc)
        return 4
    tz = load_tz(args.tz, args.utc_offset)
    try:
        today_start, today_end = day_bounds(day, tz)
    except (OverflowError, ValueError) as exc:
        sys.stderr.write("时间窗口算不出来：%s\n" % exc)
        return 4
    yesterday_start, _ = day_bounds(day - timedelta(days=1), tz)

    stats, buckets, ci_data = scan_sources(args, tz, day, yesterday_start, today_end, today_start)
    ctx = {
        "args": args, "tz": tz, "tz_name": args.tz if _tz_name_ok(args.tz) else "UTC%+d" % int(args.utc_offset),
        "today": day, "now": now, "now_utc": now.astimezone(timezone.utc),
        "today_start": today_start, "today_end": today_end,
        "yesterday_start": yesterday_start,
        "stats": stats, "buckets": buckets, "ci_data": ci_data,
    }
    report = build_report(ctx)

    out_path = None
    if args.out:
        try:
            out_path = expand_strftime(args.out, now)
        except SystemExit as exc:
            sys.stderr.write("%s\n" % exc)
            return 4
    elif args.out_dir:
        out_path = os.path.join(args.out_dir, "daily-%s.md" % day.strftime("%Y-%m-%d"))

    if out_path:
        parent = os.path.dirname(os.path.abspath(out_path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(report)
        sys.stderr.write("已写入 %s（%d 字节）\n" % (out_path, len(report.encode("utf-8"))))
        if out_path.endswith(".md") and not args.no_html:
            try:
                html_path = write_html_for(out_path, report)
                if html_path:
                    sys.stderr.write("已写入 %s\n" % html_path)
            except OSError as exc:
                sys.stderr.write("HTML 导出失败（不影响 .md）：%s\n" % exc)
    else:
        sys.stdout.write(report)

    # 退出码：全部读到 0 / 部分 3 / 全挂 2（报告都已写出）
    unreadable = [n for n, st in (("eve.json", stats["eve"]), ("cowrie", stats["cowrie"]),
                                  ("ci/latest.json", stats["ci"])) if not st.ok]
    if not unreadable:
        return 0
    for name, st in (("eve.json", stats["eve"]), ("cowrie", stats["cowrie"]), ("ci/latest.json", stats["ci"])):
        if not st.ok:
            sys.stderr.write("[读不到] %s：%s\n" % (name, st.reason))
    if len(unreadable) == 3:
        sys.stderr.write("三个数据源全部读不到；报告仍写出（记录「今天读不到什么、为什么」）。\n")
        return 2
    sys.stderr.write("有 %d 个数据源读不到（%s），报告已按「%s（原因）」如实生成。\n" % (
        len(unreadable), "、".join(unreadable), UNREADABLE))
    return 3


def _tz_name_ok(name):
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(name)
        return True
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    sys.exit(main())
