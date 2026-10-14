# -*- coding: utf-8 -*-
"""生成 REPORT 用的对照表：id → 日文 → 中文 → 时长 → 情绪 → 来源（线上原文/本轮新写）
   数据源：lines60-bilingual.json（文案）+ out-ja/verify.json（实测时长/体积/响度）
输出：lines60-final-table.md
"""
import json
import os

T = os.path.dirname(os.path.abspath(__file__))
bi = json.load(open(os.path.join(T, "lines60-bilingual.json"), encoding="utf-8"))
vp = os.path.join(T, "out-ja", "verify.json")
ver = json.load(open(vp, encoding="utf-8")) if os.path.exists(vp) else {"perLine": []}
meas = {v["id"]: v for v in ver.get("perLine", [])}

rows = ["| # | id | trigger | 来源 | 情绪参考 | 时长 | m4a | webm | 日文（进 TTS） | 中文（仅字幕） |",
        "|---:|---|---|---|---|---:|---:|---:|---|---|"]
n_new = n_ex = 0
for i, x in enumerate(bi["lines"], 1):
    m = meas.get(x["id"], {})
    dur = "%.2fs" % m["seconds"] if m.get("seconds") else "—"
    m4a = "%d B" % m["m4a"] if m.get("m4a") else "—"
    webm = "%d B" % m["webm"] if m.get("webm") else "—"
    src = "线上原文" if x["source"] == "existing" else "**本轮新写**"
    n_new += x["source"] == "new"
    n_ex += x["source"] == "existing"
    rows.append("| %d | `%s` | %s | %s | %s | %s | %s | %s | %s | %s |" % (
        i, x["id"], x["trigger"], src, x.get("emotion") or "默认参考", dur, m4a, webm, x["ja"], x["zh"]))
out = os.path.join(T, "lines60-final-table.md")
open(out, "w", encoding="utf-8").write("\n".join(rows) + "\n")
print("→", out, "| 条数", len(bi["lines"]), "| 线上原文", n_ex, "| 新写", n_new,
      "| 有实测", len(meas))
