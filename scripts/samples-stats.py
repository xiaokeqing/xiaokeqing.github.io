#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集蜜罐样本落盘的真实数字，产出 data/samples.json。

只做一件事：ssh 到蜜罐主机，把 dionaea bistreams / Cowrie downloads 的
文件数、字节数、近 7 天增量、类型分布、大小分桶、sha256 唯一数取回来。
取不到的一律 null，并在 notes 里写原因 —— 绝不补 0。

用法：
    python scripts/samples-stats.py            # 写 data/samples.json
    python scripts/samples-stats.py --stdout   # 只打印，不写文件
    python scripts/samples-stats.py --host secagent-srv2
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "samples.json")

BISTREAMS = "/opt/dionaea/var/lib/dionaea/bistreams"
COWRIE_DL = "/opt/cowrie/dl"

REMOTE = r"""
set -u
B="__B__"
C="__C__"
NOW=$(date +%s)
echo "TS	$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if sudo test -d "$B"; then
  # 一次快照固定文件清单，后面所有统计都基于同一批，避免蜜罐边写边数
  sudo find "$B" -type f -printf '%s\t%T@\t%p\n' | sort -k3 > /tmp/xk_smp_files.tsv
  awk -F'\t' '{n++; s+=$1} END{printf "DIONAEA\t%d\t%.0f\n", n, s+0}' /tmp/xk_smp_files.tsv
  awk -F'\t' -v now="$NOW" '{if ($2 > now-604800) {n++; s+=$1}} END{printf "DIONAEA7\t%d\t%.0f\n", n+0, s+0}' /tmp/xk_smp_files.tsv
  awk -F'\t' '{k=split($3,a,"/"); d=a[k-1]; c[d]++; b[d]+=$1} END{for (d in c) printf "DAY\t%s\t%d\t%.0f\n", d, c[d], b[d]}' /tmp/xk_smp_files.tsv
  awk -F'\t' '{k=split($3,a,"/"); b=a[k]; split(b,sv,"-"); c[sv[1]]++; z[sv[1]]+=$1} END{for (s in c) printf "SVC\t%s\t%d\t%.0f\n", s, c[s], z[s]}' /tmp/xk_smp_files.tsv
  awk -F'\t' '{b=$1; if (b<1024) k="<1K"; else if (b<10240) k="1K-10K"; else if (b<102400) k="10K-100K"; else if (b<1048576) k="100K-1M"; else k=">1M"; c[k]++; z[k]+=b} END{for (k in c) printf "SZ\t%s\t%d\t%.0f\n", k, c[k], z[k]}' /tmp/xk_smp_files.tsv
  cut -f3 /tmp/xk_smp_files.tsv | tr '\n' '\0' | xargs -0 file > /tmp/xk_smp_types.txt 2>/dev/null
  awk -F'\t' 'NR==FNR { sz[$3]=$1; next } {
      # file 输出冒号后的空格数不定（"path:  ASCII text" / "path:     CSV text"），
      # 必须整段吃掉 /: +/，否则残留前导空格会让类型落到 tolower(w[1])="ascii"。
      p = match($0, /: +/); if (p == 0) next;
      path = substr($0, 1, p-1); t = substr($0, p+RLENGTH);
      sub(/,.*/, "", t);
      if (t == "ASCII text") e = "txt";
      else if (t == "CSV text") e = "csv";
      else if (t == "empty") e = "(empty)";
      else { split(t, w, " "); e = tolower(w[1]) }
      if (e ~ /^pe/ || e ~ /^elf/) r++;
      if (path in sz) { c[e]++; z[e] += sz[path] }
  } END {
      for (e in c) printf "EXT\t%s\t%d\t%.0f\n", e, c[e], z[e];
      printf "READABLE\t%d\n", r+0;
  }' /tmp/xk_smp_files.tsv /tmp/xk_smp_types.txt
  cut -f3 /tmp/xk_smp_files.tsv | tr '\n' '\0' | sudo xargs -0 sha256sum 2>/dev/null \
      | cut -d' ' -f1 | sort -u | awk 'END{printf "SHA\t%d\n", NR}'
else
  echo "MISS	$B"
fi

if sudo test -d "$C"; then
  sudo find "$C" -type f -printf '%s\t%T@\n' > /tmp/xk_smp_cowrie.tsv
  awk -F'\t' -v now="$NOW" '{n++; s+=$1; if ($2 > now-604800) {n7++; s7+=$1}}
      END{printf "COWRIE\t%d\t%.0f\t%d\t%.0f\n", n+0, s+0, n7+0, s7+0}' /tmp/xk_smp_cowrie.tsv
else
  echo "MISS	$C"
fi

YT=""
for t in yara clamscan; do
  if command -v "$t" >/dev/null 2>&1; then YT="$YT $t"; fi
done
echo "SCANNER	${YT# }"
if sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'wazuh.manager'; then
  W=$(sudo docker exec wazuh.manager sh -c 'grep -c bistreams /var/ossec/etc/ossec.conf 2>/dev/null || true' 2>/dev/null | tr -d '[:space:]')
  echo "WAZUH	${W:-0}"
else
  echo "WAZUH	?"
fi
""".strip()


def run_remote(host, timeout=240):
    script = REMOTE.replace("__B__", BISTREAMS).replace("__C__", COWRIE_DL)
    try:
        p = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes", host, "bash -s"],
            input=script.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except FileNotFoundError:
        return None, ["本机没有 ssh 客户端"]
    except subprocess.TimeoutExpired:
        return None, ["ssh %s 超时（%d 秒）" % (host, timeout)]
    if p.returncode != 0:
        err = p.stderr.decode("utf-8", "replace").strip().splitlines()
        return None, ["ssh %s 退出码 %d：%s" % (host, p.returncode, err[-1] if err else "无 stderr")]
    return p.stdout.decode("utf-8", "replace"), []


SIZE_ORDER = ["<1K", "1K-10K", "10K-100K", "100K-1M", ">1M"]


def parse(text):
    rows = {"DAY": [], "SVC": [], "SZ": [], "EXT": []}
    for line in text.splitlines():
        if not line.strip():
            continue
        f = line.split("\t")
        tag = f[0]
        if tag in rows:
            rows[tag].append(f[1:])
        else:
            rows[tag] = f[1:]
    return rows


def build(host):
    notes = []
    text, errs = run_remote(host)
    notes.extend(errs)
    r = parse(text or "")

    def num(x):
        try:
            return int(x)
        except (TypeError, ValueError):
            return None

    gen = (r.get("TS") or [None])[0]

    dionaea = {"files": None, "bytes": None, "d7": None, "d7Bytes": None,
               "byExt": None, "bySize": None, "byService": None}
    if "DIONAEA" in r:
        dionaea["files"] = num(r["DIONAEA"][0])
        dionaea["bytes"] = num(r["DIONAEA"][1])
    else:
        notes.append("dionaea bistreams 取不到（目录不存在或不可读）")
    if "DIONAEA7" in r:
        dionaea["d7"] = num(r["DIONAEA7"][0])
        dionaea["d7Bytes"] = num(r["DIONAEA7"][1])

    if r["EXT"]:
        ext = [{"ext": e[0], "n": num(e[1]), "bytes": num(e[2])} for e in r["EXT"]]
        ext.sort(key=lambda x: (-(x["n"] or 0)))
        dionaea["byExt"] = ext
    if r["SZ"]:
        sz = {e[0]: {"bucket": e[0], "n": num(e[1]), "bytes": num(e[2])} for e in r["SZ"]}
        dionaea["bySize"] = [sz[k] for k in SIZE_ORDER if k in sz]
    if r["SVC"]:
        svc = [{"service": e[0], "n": num(e[1]), "bytes": num(e[2])} for e in r["SVC"]]
        svc.sort(key=lambda x: -(x["n"] or 0))
        dionaea["byService"] = svc

    if "DAY" in r and r["DAY"]:
        days = [{"date": d[0], "n": num(d[1]), "bytes": num(d[2])} for d in r["DAY"]]
        days.sort(key=lambda x: x["date"] or "")
        dionaea["byDay"] = days

    uniq = num(r.get("SHA", [None])[0]) if "SHA" in r else None

    cowrie = {"files": None, "bytes": None, "d7": None, "d7Bytes": None}
    if "COWRIE" in r:
        cowrie["files"] = num(r["COWRIE"][0])
        cowrie["bytes"] = num(r["COWRIE"][1])
        cowrie["d7"] = num(r["COWRIE"][2])
        cowrie["d7Bytes"] = num(r["COWRIE"][3])
    else:
        notes.append("Cowrie downloads 取不到（目录不存在或不可读）")

    scanner_available = False
    scanner_tool = None
    scanner_note = "yara 与 clamscan 均未安装（command -v 无输出）"
    if "SCANNER" in r:
        tools = [t for t in r["SCANNER"] if t]
        if tools:
            scanner_available = True
            scanner_tool = tools[0]
            scanner_note = "已安装：" + "、".join(tools)
    waz = (r.get("WAZUH") or [None])[0]
    if waz == "0":
        scanner_note += "；Wazuh manager 的 ossec.conf 未监控 bistreams"
    elif waz == "?":
        scanner_note += "；未找到 wazuh.manager 容器，无法确认"

    readable = num(r.get("READABLE", [None])[0]) if "READABLE" in r else None

    both = all(isinstance(x, int) for x in (dionaea["files"], cowrie["files"]))
    data = {
        "generatedAt": gen,
        "source": {
            "host": host,
            "dionaea": BISTREAMS,
            "cowrie": COWRIE_DL,
        },
        "dionaea": dionaea,
        "cowrie": cowrie,
        "total": {
            "files": (dionaea["files"] + cowrie["files"]) if both else None,
            "bytes": (dionaea["bytes"] + cowrie["bytes"]) if both else None,
        },
        "dedupe": {
            "unique": uniq,
            "duplicates": (dionaea["files"] - uniq) if (isinstance(uniq, int) and isinstance(dionaea["files"], int)) else None,
        },
        "scanner": {
            "available": scanner_available,
            "tool": scanner_tool,
            "note": scanner_note,
        },
        "samplesReadable": readable,
        "notes": notes,
    }
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="secagent-srv2")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    data = build(args.host)
    if data.get("notes") is None:
        data["notes"] = []
    txt = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.stdout:
        sys.stdout.write(txt)
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    print("wrote %s (%d bytes)" % (os.path.relpath(OUT, ROOT), len(txt.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
