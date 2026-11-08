#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""蜜罐会话快照（M3 /session/ 构建期数据，纯 stdlib）。

实测结论（2026-11-08）：cowrie 容器没开 output_ttylog —— var 卷里的
lib/cowrie/tty 只有 .gitignore，cowrie.json 里 cowrie.command.input 也是 0 条。
所以本脚本走 B 方案：不拉 ttylog，只按会话聚合 cowrie.json 的连接/登录/断开
事件，产出 data/sessions/index.json；页面用「会话时间线」展示，不伪造终端输出。

如果将来打开 ttylog，本脚本会把 ttylog.available 标成 true 并在 note 里写明
「字节流未接入回放」，不假装有录像。

取数通道：ssh secagent-srv2 → sudo python3（远端脚本只读 /opt/cowrie/logs；
国家来自 wazuh.indexer 的 ingest-geoip（_ingest/pipeline/_simulate），失败写「未知」）。
"""
import datetime
import json
import os
import re
import shlex
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "sessions")
SSH_HOST = os.environ.get("HONEYPOT_SSH", "secagent-srv2")
LIMIT = int(os.environ.get("HONEYPOT_SESSIONS", "24"))
WINDOW_DAYS = 7

REMOTE = r'''
import json, os, subprocess, time, sys

sys.stdout.reconfigure(encoding="utf-8")

def run(cmd):
    return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)

info = json.loads(run("docker inspect cowrie"))[0]
mounts = {m["Destination"]: m["Source"] for m in info["Mounts"]}
logs = mounts.get("/cowrie/cowrie-git/var/log/cowrie") or "/opt/cowrie/logs"
dl = mounts.get("/cowrie/cowrie-git/var/lib/cowrie/downloads") or "/opt/cowrie/dl"
ttydirs = [os.path.join(m["Source"], "lib", "cowrie", "tty")
           for m in info["Mounts"] if m["Destination"].endswith("/var")]

current = os.path.join(logs, "cowrie.json")
now = time.time()
cut = now - 7 * 86400
cut_s = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(cut))

# ---- ttylog 探测 ----
tty_files = []
for d in ttydirs:
    if os.path.isdir(d):
        for fn in os.listdir(d):
            if fn == ".gitignore":
                continue
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                tty_files.append({"name": fn, "bytes": os.path.getsize(p)})

# ---- downloads ----
dl_files = []
for fn in os.listdir(dl):
    p = os.path.join(dl, fn)
    if os.path.isfile(p):
        st = os.stat(p)
        dl_files.append({"name": fn, "bytes": st.st_size, "mtime": st.st_mtime})
dl_recent = [f for f in dl_files if f["mtime"] >= cut]

# ---- 7 天窗口统计（8 个日志文件，流式、不做全量 json.loads）----
stats_files = [current]
for fn in sorted(os.listdir(logs)):
    if fn.startswith("cowrie.json.") and fn[12:22] >= "2026-11-01":
        stats_files.append(os.path.join(logs, fn))
seen_files = []
events = connects = logins = login_fails = commands = 0
cmd_sessions = set()
top = {}
for path in stats_files:
    if not os.path.isfile(path):
        continue
    if path != current and os.path.getmtime(path) < cut - 2 * 86400:
        continue
    seen_files.append(os.path.basename(path))
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            i = line.find('"timestamp":"')
            if i < 0:
                continue
            if line[i + 13:i + 32] < cut_s:
                continue
            j = line.find('"eventid":"')
            if j < 0:
                continue
            k = line.find('"', j + 11)
            e = line[j + 11:k]
            events += 1
            if e == "cowrie.session.connect":
                connects += 1
            elif e == "cowrie.login.success":
                logins += 1
            elif e == "cowrie.login.failed":
                login_fails += 1
            elif e == "cowrie.command.input":
                commands += 1
                try:
                    o = json.loads(line)
                    cmd_sessions.add(o.get("session"))
                    msg = (o.get("message") or "").strip()
                    top[msg] = top.get(msg, 0) + 1
                except Exception:
                    pass

# ---- 最近会话（倒着取最后 N 个，只保留 600 个在内存）----
sessions = {}
order = []
def new_sess(sid, o):
    sessions[sid] = {
        "id": sid,
        "ts": o.get("timestamp", ""),
        "ip": o.get("src_ip", ""),
        "events": [],
        "logins": 0,
        "fails": 0,
        "cmds": [],
        "client": "",
        "closed": False,
        "duration": None,
    }
    order.append(sid)
    while len(order) > 600:
        old = order.pop(0)
        sessions.pop(old, None)

with open(current, "r", encoding="utf-8", errors="replace") as fh:
    for line in fh:
        if '"eventid":"' not in line:
            continue
        j = line.find('"eventid":"')
        e = line[j + 11:line.find('"', j + 11)]
        if e not in ("cowrie.session.connect", "cowrie.login.success",
                     "cowrie.login.failed", "cowrie.client.version",
                     "cowrie.session.closed", "cowrie.command.input"):
            continue
        si = line.find('"session":"')
        if si < 0:
            continue
        sid = line[si + 11:line.find('"', si + 11)]
        if e == "cowrie.session.connect":
            try:
                o = json.loads(line)
            except Exception:
                continue
            if sid in sessions:
                sessions[sid]["ip"] = o.get("src_ip", "") or sessions[sid]["ip"]
                continue
            new_sess(sid, o)
            continue
        s = sessions.get(sid)
        if s is None:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        ts = o.get("timestamp", "")
        if e == "cowrie.login.success":
            s["logins"] += 1
            if len([ev for ev in s["events"] if ev[0] == "login"]) < 2:
                s["events"].append(("login", ts, "登录成功（口令已隐藏）"))
        elif e == "cowrie.login.failed":
            s["fails"] += 1
            if len([ev for ev in s["events"] if ev[0] == "fail"]) < 1:
                s["events"].append(("fail", ts, "登录失败"))
        elif e == "cowrie.client.version":
            m = o.get("message") or ""
            for p in ("SSH client version:", "Remote SSH version:"):
                if p in m:
                    s["client"] = m.split(p, 1)[1].strip()[:120]
                    break
            if not s["client"]:
                s["client"] = (o.get("version") or "")[:120]
        elif e == "cowrie.session.closed":
            s["closed"] = True
            s["duration"] = o.get("duration_ms")
            s["events"].append(("close", ts, "连接断开"))
        elif e == "cowrie.command.input":
            if len(s["cmds"]) < 30:
                s["cmds"].append((o.get("message") or "").strip()[:300])

done = [s for s in sessions.values() if s["logins"] > 0 and s["closed"] and s["ip"]]
done.sort(key=lambda s: s["ts"], reverse=True)
picked = done[:24]

out = []
for s in picked:
    out.append({
        "id": s["id"],
        "start": s["ts"],
        "ip": s["ip"],
        "client": s["client"],
        "logins": s["logins"],
        "fails": s["fails"],
        "duration_ms": s["duration"],
        "events": [{"kind": k, "ts": t, "text": x} for (k, t, x) in
                   [("connect", s["ts"], "TCP 连接建立")] + s["events"]],
        "commands": s["cmds"],
    })

print(json.dumps({
    "logsDir": logs,
    "statsFiles": seen_files,
    "stats": {
        "windowDays": 7,
        "start": cut_s + "Z",
        "files": len(seen_files),
        "events": events,
        "connects": connects,
        "logins": logins,
        "loginFails": login_fails,
        "commands": commands,
        "commandSessions": len(cmd_sessions),
        "topCommands": sorted(top.items(), key=lambda kv: -kv[1])[:20],
    },
    "ttylog": {
        "available": bool(tty_files),
        "files": len(tty_files),
        "dirs": ttydirs,
        "note": "容器未开 output_ttylog：原始字节流从未落盘" if not tty_files else
                "检测到 ttylog 文件，但本页未接入字节流回放",
    },
    "downloads": {
        "files": len(dl_files),
        "bytes": sum(f["bytes"] for f in dl_files),
        "recent": len(dl_recent),
        "newest": time.strftime("%Y-%m-%d", time.localtime(max([f["mtime"] for f in dl_files] or [0]))),
    },
    "sessions": out,
}, ensure_ascii=False))
'''


def ssh(cmd, stdin_text=None, timeout=300):
    p = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", SSH_HOST, cmd],
        input=(stdin_text.encode("utf-8") if stdin_text is not None else None),
        capture_output=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError("ssh %s 失败(%s): %s" % (
            SSH_HOST, p.returncode, p.stderr.decode("utf-8", "replace")[:1500]))
    return p.stdout.decode("utf-8", "replace")


def fmt_cst(ts):
    if not ts:
        return ""
    try:
        dt = datetime.datetime.strptime(ts[:26].replace("Z", ""), "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        try:
            dt = datetime.datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return ts
    dt = dt.replace(tzinfo=datetime.timezone.utc) + datetime.timedelta(hours=8)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def hhmmss(ts):
    s = fmt_cst(ts)
    return s[11:19] if len(s) >= 19 else s


def mask_ip(ip):
    parts = (ip or "").split(".")
    if len(parts) == 4:
        return "%s.%s.%s.x" % (parts[0], parts[1], parts[2])
    return "未知"


def geo_lookup(ips):
    """wazuh.indexer 的 ingest-geoip 批量查国家（失败返回 {}）。"""
    if not ips:
        return {}
    user = os.environ.get("WAZUH_ES_USER", "admin")
    pwd = os.environ.get("WAZUH_ES_PASS", "")
    if not pwd:
        # 单一口径：凭据只在 attack-coverage.py 里维护，这里读它，不再抄一份。
        # 并发编辑可能把这个文件短暂移走，所以再退一步从 git HEAD 里取。
        src = ""
        try:
            src = open(os.path.join(ROOT, "scripts", "attack-coverage.py"),
                       encoding="utf-8").read()
        except OSError:
            try:
                src = subprocess.check_output(
                    ["git", "-C", ROOT, "show", "HEAD:scripts/attack-coverage.py"],
                    text=True, encoding="utf-8", stderr=subprocess.DEVNULL)
            except Exception:
                src = ""
        try:
            m = re.search(r'ES_PASS\s*=\s*"([^"]+)"', src)
            u = re.search(r'ES_USER\s*=\s*"([^"]+)"', src)
            if m:
                pwd = m.group(1)
            if u and "WAZUH_ES_USER" not in os.environ:
                user = u.group(1)
        except OSError:
            pass
    if not pwd:
        print("[session] 无索引器凭据，国家写「未知」", file=sys.stderr)
        return {}
    body = json.dumps({
        "pipeline": {"processors": [{"geoip": {"field": "ip"}}]},
        "docs": [{"_source": {"ip": ip}} for ip in ips],
    }, ensure_ascii=False)
    remote = ("sudo docker exec -i wazuh.indexer curl -s -k -u %s "
              "https://localhost:9200/_ingest/pipeline/_simulate "
              "-H Content-Type:application/json --data-binary @-"
              % shlex.quote("%s:%s" % (user, pwd)))
    raw = ssh(remote, body, timeout=120).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("[session] geoip 返回非 JSON：%s" % raw[:300], file=sys.stderr)
        return {}
    out = {}
    for ip, doc in zip(ips, data.get("docs") or []):
        src = (((doc or {}).get("doc") or {}).get("_source") or {})
        g = src.get("geoip") or {}
        if g.get("country_iso_code"):
            out[ip] = {"code": g.get("country_iso_code"),
                       "name": g.get("country_name") or g.get("country_iso_code")}
    return out


def main():
    print("[session] 探明 srv2 cowrie …")
    payload = json.loads(ssh("sudo python3 -", REMOTE, timeout=420))
    stats = payload["stats"]
    sessions = payload["sessions"]
    print("[session] 7 天：%d 事件 / %d 连接 / %d 登录 / %d 命令 / ttylog=%s" % (
        stats["events"], stats["connects"], stats["logins"], stats["commands"],
        payload["ttylog"]["available"]))
    print("[session] 抓到最近 %d 个完整会话" % len(sessions))

    ips = sorted({s["ip"] for s in sessions if s["ip"]})
    geo = geo_lookup(ips)

    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
    out_sessions = []
    for s in sessions:
        start = fmt_cst(s["start"])
        dur = s.get("duration_ms")
        events = []
        for ev in s["events"]:
            events.append({
                "t": hhmmss(ev["ts"]),
                "kind": ev["kind"],
                "text": ev["text"],
            })
        if s.get("client"):
            events.insert(1, {"t": "", "kind": "client",
                              "text": "客户端 %s" % s["client"]})
        cmds = s.get("commands") or []
        if cmds:
            for c in cmds:
                events.append({"t": "", "kind": "cmd", "text": "$ %s" % c})
        g = geo.get(s["ip"]) or {}
        out_sessions.append({
            "id": s["id"],
            "start": start,
            "t": hhmmss(s["start"]),
            "duration": dur if isinstance(dur, int) else None,
            "ip": mask_ip(s["ip"]),
            "country": g.get("code") or "??",
            "countryName": g.get("name") or "未知",
            "client": s.get("client") or "",
            "logins": s.get("logins") or 0,
            "commands": cmds,
            "events": events,
        })

    data = {
        "generatedAt": now.strftime("%Y-%m-%d %H:%M"),
        "windowDays": WINDOW_DAYS,
        "stats": {
            "events": stats["events"],
            "connects": stats["connects"],
            "logins": stats["logins"],
            "loginFails": stats["loginFails"],
            "commands": stats["commands"],
            "commandSessions": stats["commandSessions"],
            "files": stats["files"],
        },
        "ttylog": payload["ttylog"],
        "downloads": payload["downloads"],
        "sessions": out_sessions,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "index.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("[session] 写入 %s（%d 会话，%d 字节）" % (
        os.path.relpath(path, ROOT), len(out_sessions), os.path.getsize(path)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
