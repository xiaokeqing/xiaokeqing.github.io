# -*- coding: utf-8 -*-
"""把"原声入库"产物打成**独立的 bank 分片** `bank-orig.json`（窗口 B）。

为什么要独立分片（不并进 bank.json）：
  · 现有 `static/kurisu/voice/bank.json` 的 12 条是**已上线素材**，规划侧明确"不许覆盖" ✗；
  · 原声片段与合成句**来源不同**（`source=orig-001` / `orig-000-short` vs `synth`），
    前端需要按"**有原声优先**"策略读取 ⇒ 分开两份 + 一份 `orig-ref` 索引最清楚 ✓；
  · 将来合并只需读两份、按 source 排序，不必改任何既有字节 ✓。

输入：--ingest <out-orig>/orig-ingest.json（ingest_orig.py 的台账）
产物：
  bank-orig.json      原声分片（同 bank.json v1 字段契约 + source/origName/origBucket）
  bank-orig.verify.json  自检：条数/字节/区间/响度极差/超限清单/失败清单
  orig-ref.json       前端用的索引：{ byId, byTrigger, groups }（便于"播出的那一句"按需取）
用法：python build_bank_orig.py --ingest ... --lines <lines275.json> --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MAX_M4A = 120 * 1024
MAX_WEBM = 100 * 1024
BUDGET = 64 * 1024 * 1024          # 规划侧 2026-10-15 拍板：原声分片独立预算 ≤64MiB ✓
LUFS_TOL = 0.5                     # 响度偏离容差；超出即标 loudnessOutlier 并**移出可播 quote 组** ✗
OUTLIER_TRIGGER = "quote_quiet"    # 只可用于状态/兜底等非引用场景（避免连续播放听出音量突变）


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest", required=True, help="orig-ingest.json")
    ap.add_argument("--lines", default="", help="台词库（可用于给原声补 scene/组语义，可选）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--trigger", default="quote", help="原声分片归到哪个 trigger 组")
    ap.add_argument("--tag", default="orig")
    args = ap.parse_args()

    ing = json.loads(Path(args.ingest).read_text(encoding="utf-8-sig"))
    out = Path(args.out)
    items = ing.get("items") or []

    lines = {}
    if args.lines:
        for l in json.loads(Path(args.lines).read_text(encoding="utf-8-sig"))["lines"]:
            lines[l["id"]] = l

    bank_lines, rows, missing_env = {}, [], []
    for it in items:
        lid = it["id"]
        mp = out / "meta" / (lid + ".json")
        ep = out / "envelope" / (lid + ".envelope.json")
        if not mp.is_file():
            missing_env.append({"id": lid, "why": "meta 缺失"})
            continue
        meta = json.loads(mp.read_text(encoding="utf-8"))
        if not ep.is_file():
            missing_env.append({"id": lid, "why": "envelope 缺失"})
            continue
        m4a, webm, env = meta["m4a"], meta["webm"], meta["envelope"]
        use = it.get("use") or "quote"
        trigger = args.trigger if use == "quote" or use.startswith("quote") else use
        # 响度异常（真峰优先的代价）⇒ 标记 + 移出可播组（规划侧 2026-10-15 拍板 ✓）
        lufs_val = m4a.get("lufs")
        outlier = (lufs_val is not None) and (abs(lufs_val + 16.0) > LUFS_TOL)
        if outlier:
            trigger = OUTLIER_TRIGGER
        env_doc = json.loads(ep.read_text(encoding="utf-8"))
        rec = {
            "id": lid,
            "trigger": trigger,
            "group": trigger,
            "text": it.get("asr") or "",
            "scene": "原声片段（%s / %s）" % (it.get("bucket"), it.get("origName")),
            "emotion": "",
            "source": "orig-%s" % it.get("bucket"),
            "audio": "kurisu/voice/orig/%s.m4a" % lid,
            "envelope": "kurisu/voice/orig/%s.envelope.json" % lid,
            "seconds": round(m4a["seconds"], 3),
            "audioBytes": m4a["bytes"],
            "envelopeValues": len(env_doc.get("values") or []),
            "audioSources": {"m4a": "kurisu/voice/orig/%s.m4a" % lid,
                             "webm": "kurisu/voice/orig/%s.webm" % lid},
            "durationMs": int(round(m4a["seconds"] * 1000)),
            "sha256": {"m4a": m4a["sha256"], "webm": webm["sha256"]},
            "bytes": {"m4a": m4a["bytes"], "webm": webm["bytes"]},
            "loudness": {"lufs": m4a.get("lufs"), "target": -16.0},
            "envelopeSource": env["sourceFile"],
            "origName": it.get("origName"),
            "origBucket": it.get("bucket"),
            "use": use,
        }
        if outlier:
            rec["loudnessOutlier"] = True
            rec["loudnessOutlierNote"] = ("真峰优先的代价：该片段峰顶密集，压到 ≤-1.5 dBTP 后响度无法回到 -16 LUFS "
                                          "（实测 %s）；已移出可播 quote 组，仅可用于状态/兜底等非引用场景。" % lufs_val)
        bank_lines[lid] = rec
        rows.append({"id": lid, "use": use, "seconds": rec["seconds"],
                     "m4a": m4a["bytes"], "webm": webm["bytes"], "lufs": m4a.get("lufs"),
                     "env": rec["envelopeValues"]})

    total = sum(r["m4a"] + r["webm"] for r in rows)
    lufs = [r["lufs"] for r in rows if r["lufs"] is not None]
    groups = {}
    for v in bank_lines.values():
        groups[v["trigger"]] = groups.get(v["trigger"], 0) + 1

    bank = {
        "format": "xiaokeqing.kurisu.voicebank.v1",
        "generator": "原声素材包（484 条 / 素材包 000·001·002·003）+ scripts/voice/postprocess.py（-16 LUFS 闭环 / 40ms fade / m4a+webm / 包络从最终编码重算）",
        "voiceNote": "本分片是**原声片段**（非合成）。与 bank.json（合成/线上 12 句）分开，前端按"
                     "「有原声优先、命中不到再播合成句、都没有才只出字幕」读取。",
        "codec": "aac(m4a) + opus(webm)",
        "sampleRate": 8000,
        "hopMs": 10,
        "envelopeFormula": "clamp(RMS(10ms) * 3.75, 0, 1)，首窗保底 0.12，停止发 0",
        "envelopeSource": "解码最终分发的 m4a 得到（不是母带 wav）",
        "loudnessTarget": -16.0,
        "groups": groups,
        "lineCount": len(bank_lines),
        "totalBytes": total,
        "note": "原声片段引自站主合法持有副本（本机素材包），仅个人非商业展示，逐条注明出处，可随时下架。",
        "lines": bank_lines,
    }
    (out / "bank-orig.json").write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")

    ref = {
        "format": "xiaokeqing.kurisu.voicebank.origref.v1",
        "bank": "kurisu/voice/orig/bank-orig.json",
        "byId": {k: {"audio": v["audioSources"]["m4a"], "webm": v["audioSources"]["webm"],
                     "envelope": v["envelope"], "trigger": v["trigger"], "seconds": v["seconds"],
                     "source": v["source"]} for k, v in bank_lines.items()},
        "byTrigger": {},
        "groups": groups,
    }
    for k, v in bank_lines.items():
        ref["byTrigger"].setdefault(v["trigger"], []).append(k)
    (out / "bank-orig.origref.json").write_text(json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 合并视图（前端"原声优先"的唯一查找表）：同一句话的原声 / 合成两种版本并排 ----
    # 为什么用合并视图而不是"在 bank.json 每行加一个 orig 字段"：bank.json 的 12 条是**已上线素材**，
    # 规划侧要求不许覆盖 ✗ ⇒ 合并视图放仓库外/独立文件，前端只读它一处即可，既有字节零改动 ✓。
    merged = {"format": "xiaokeqing.kurisu.voicebank.merged.v1",
              "note": "前端唯一查找表：按 id 命中后，**优先用 orig（原声）**；没有 orig 再用 synth；两者都无 ⇒ 只出字幕。",
              "banks": {"synth": "kurisu/voice/bank.json", "orig": "kurisu/voice/orig/bank-orig.json"},
              "lookup": {}}
    for k, v in bank_lines.items():
        merged["lookup"].setdefault(k, {"id": k, "trigger": v["trigger"]})
        merged["lookup"][k]["orig"] = {"audio": v["audioSources"]["m4a"], "webm": v["audioSources"]["webm"],
                                       "envelope": v["envelope"], "seconds": v["seconds"],
                                       "source": v["source"], "text": v["text"]}
    if args.lines:
        for lid, l in lines.items():
            e = merged["lookup"].setdefault(lid, {"id": lid, "trigger": l.get("trigger", "")})
            e["synth"] = {"audio": "kurisu/voice/%s.m4a" % lid, "webm": "kurisu/voice/%s.webm" % lid,
                          "envelope": "kurisu/voice/%s.envelope.json" % lid,
                          "text": l.get("text", ""), "source": "synth"}
    # 线上 12 句（既有 bank.json 的 lines）也算 synth 侧
    live_bank = out.parent / "bank-live-snapshot.json"
    if live_bank.is_file():
        lb = json.loads(live_bank.read_text(encoding="utf-8-sig"))
        for lid, v in (lb.get("lines") or {}).items():
            e = merged["lookup"].setdefault(lid, {"id": lid, "trigger": v.get("trigger", "")})
            e.setdefault("synth", {"audio": v.get("audio"), "webm": (v.get("audioSources") or {}).get("webm"),
                                   "envelope": v.get("envelope"), "text": v.get("text"),
                                   "source": "existing"})
    merged["counts"] = {
        "ids": len(merged["lookup"]),
        "withOrig": sum(1 for v in merged["lookup"].values() if "orig" in v),
        "withSynth": sum(1 for v in merged["lookup"].values() if "synth" in v),
        "withBoth": sum(1 for v in merged["lookup"].values() if "orig" in v and "synth" in v),
    }
    (out / "bank-merged.origfirst.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")

    verify = {
        "n": len(rows), "expected": len(items), "totalBytes": total,
        "budgetBytes": BUDGET, "withinBudget": total <= BUDGET,
        "m4aMin": min(r["m4a"] for r in rows), "m4aMax": max(r["m4a"] for r in rows),
        "m4aMean": round(sum(r["m4a"] for r in rows) / len(rows), 1),
        "webmMin": min(r["webm"] for r in rows), "webmMax": max(r["webm"] for r in rows),
        "webmMean": round(sum(r["webm"] for r in rows) / len(rows), 1),
        "lufsMin": min(lufs) if lufs else None, "lufsMax": max(lufs) if lufs else None,
        "lufsSpread": round(max(lufs) - min(lufs), 3) if lufs else None,
        "over100KBm4a": [r["id"] for r in rows if r["m4a"] > MAX_M4A],
        "over80KBwebm": [r["id"] for r in rows if r["webm"] > MAX_WEBM],
        "missingEnvelope": missing_env, "groups": groups,
        "rows": rows,
    }
    (out / "bank-orig.verify.json").write_text(json.dumps(verify, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: verify[k] for k in ("n", "expected", "totalBytes", "withinBudget",
                                             "m4aMin", "m4aMax", "m4aMean", "webmMin", "webmMax", "webmMean",
                                             "lufsMin", "lufsMax", "lufsSpread", "groups")},
                     ensure_ascii=False, indent=1))
    print("超 100KB 的 m4a：%d 条 %s" % (len(verify["over100KBm4a"]), verify["over100KBm4a"][:8]))
    print("超 80KB 的 webm：%d 条 %s" % (len(verify["over80KBwebm"]), verify["over80KBwebm"][:8]))
    print("缺包络/meta：", verify["missingEnvelope"][:5])
    print("→", out / "bank-orig.json")
    print("→", out / "bank-orig.verify.json")
    print("→", out / "bank-orig.origref.json")


if __name__ == "__main__":
    main()
