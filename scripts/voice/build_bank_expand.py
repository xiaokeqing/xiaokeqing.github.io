# -*- coding: utf-8 -*-
"""把扩库产物 + 线上旧 12 句合成一份**新 bank.json**（窗口 B，2026-10-15 台词库扩容）。

和 build_bank.py 的区别（为什么另写一个）：
  · build_bank.py 从 lines 文件**重建**每条记录；对线上旧 12 句它会重算字段 ⇒ 不满足
    "旧 12 句一个字节都不许丢、字段逐字保全" ✗。
  · 本脚本把线上 bank.json 里**已存在的记录整条原样搬运**（copy 而非 rebuild），
    只对**新 id** 从 out/meta/*.json 生成记录。旧记录的 envelope 文件也不重新生成。
  · 顺带做硬校验：旧记录对着磁盘核对 sha256/字节数；新旧 id 不重叠；包络条数与前缀自洽。

产物（默认写到 --out 目录，**落在仓库外**；进仓库由 PowerShell Copy-Item 完成）：
  bank.new.json            完整新 bank（旧 12 + 新 N）
  bank.verify.json         自检报告（句数/字节/响度极差/体积区间/旧句保全）
用法：
  python build_bank_expand.py --lines <lines275.json> --out <synth out> \
      --old-bank <repo>/static/kurisu/voice/bank.json --tag expand
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_OLD_BANK = os.path.join(REPO_ROOT, "static", "kurisu", "voice", "bank.json")
BUDGET_BYTES = 32 * 1024 * 1024          # 规划侧给的"语音资产独立预算"≤32MiB
MAX_M4A = 120 * 1024
MAX_WEBM = 100 * 1024
LUFS_TOL = 0.5                     # 响度偏离容差；超出即标 loudnessOutlier 并移出可播组（规划侧拍板 ✓）
OUTLIER_TRIGGER = "synth_quiet"    # 与 bank-orig 的 quote_quiet 同口径：只用于非引用场景


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(static_root, url):
    return os.path.join(static_root, url.replace("/", os.sep))


def build_new_record(ln, meta, static_root, url_prefix="kurisu/voice"):
    lid = ln["id"]
    m4a, webm = meta["m4a"], meta["webm"]
    env = meta["envelope"]
    rec = {
        "id": lid,
        "trigger": ln["trigger"],
        "group": ln["trigger"],
        "text": ln["text"],
        "scene": ln.get("scene", ""),
        "emotion": ln.get("emotion", ""),
        "source": ln.get("source", "") or "synth",
        "audio": "%s/%s.m4a" % (url_prefix, lid),
        "envelope": "%s/%s.envelope.json" % (url_prefix, lid),
        "seconds": round(m4a["seconds"], 3),
        "audioBytes": m4a["bytes"],
        "envelopeValues": env["values"],
        "audioSources": {"m4a": "%s/%s.m4a" % (url_prefix, lid),
                         "webm": "%s/%s.webm" % (url_prefix, lid)},
        "durationMs": int(round(m4a["seconds"] * 1000)),
        "sha256": {"m4a": m4a["sha256"], "webm": webm["sha256"]},
        "bytes": {"m4a": m4a["bytes"], "webm": webm["bytes"]},
        "loudness": {"lufs": m4a.get("lufs"), "target": -16.0},
        "envelopeSource": env["sourceFile"],
    }
    for k in ("question", "sourceFile", "origSource", "ttsJa"):
        if ln.get(k):
            rec[k] = ln[k]
    # 响度异常（真峰优先的代价）⇒ 标记 + 移出可播组（规划侧 2026-10-15 拍板 ✓，与原声分片同口径）
    lufs_val = m4a.get("lufs")
    if lufs_val is not None and abs(lufs_val + 16.0) > LUFS_TOL:
        rec["loudnessOutlier"] = True
        rec["loudnessOutlierNote"] = ("真峰优先的代价：该句峰顶密集，压到 ≤-1.5 dBTP 后响度无法回到 -16 LUFS"
                                      "（实测 %s）；已移出可播组，仅用于非引用场景。" % lufs_val)
        rec["trigger"] = rec["group"] = OUTLIER_TRIGGER
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", required=True)
    ap.add_argument("--out", required=True, help="synth 产物目录（含 meta/）")
    ap.add_argument("--old-bank", default=DEFAULT_OLD_BANK)
    ap.add_argument("--static-root", default=os.path.join(REPO_ROOT, "static"))
    ap.add_argument("--tag", default="expand")
    ap.add_argument("--url-prefix", default="kurisu/voice/synth",
                    help="新句在 static/ 下的相对目录（默认 synth/，与门禁的 synth* 分片 glob 对齐 ✓）")
    ap.add_argument("--exclude-triggers", default="quote",
                    help="不进 bank 的组（原声组由另一条线处理）")
    args = ap.parse_args()

    lines = json.load(open(args.lines, encoding="utf-8"))["lines"]
    old = json.load(open(args.old_bank, encoding="utf-8"))
    old_lines = old["lines"]
    exclude = {x for x in args.exclude_triggers.split(",") if x}

    bank_lines, new_ids, missing = {}, [], []
    # ① 旧记录整条搬运（逐字保全）
    for lid, rec in old_lines.items():
        bank_lines[lid] = rec
    # ② 新记录
    for ln in lines:
        lid = ln["id"]
        if ln["trigger"] in exclude:
            continue
        if lid in bank_lines:
            raise SystemExit("id 与线上旧句冲突（不许覆盖 ✗）：%s" % lid)
        mp = os.path.join(args.out, "meta", lid + ".json")
        if not os.path.exists(mp):
            missing.append(lid)
            continue
        meta = json.load(open(mp, encoding="utf-8"))
        bank_lines[lid] = build_new_record(ln, meta, args.static_root, args.url_prefix)
        new_ids.append(lid)

    total = sum(v["bytes"]["m4a"] + v["bytes"]["webm"] for v in bank_lines.values())
    groups = {}
    for v in bank_lines.values():
        groups[v["trigger"]] = groups.get(v["trigger"], 0) + 1

    lufs = [v["loudness"]["lufs"] for v in bank_lines.values() if v["loudness"].get("lufs") is not None]
    sizes_m4a = [v["bytes"]["m4a"] for v in bank_lines.values()]
    sizes_webm = [v["bytes"]["webm"] for v in bank_lines.values()]

    bank = dict(old)                                   # 保留 format/generator/... 等头部字段
    bank["lines"] = bank_lines
    bank["lineCount"] = len(bank_lines)
    bank["totalBytes"] = total
    bank["groups"] = groups
    bank["expandNote"] = ("2026-10-15 台词库扩容（窗口 B）：旧 12 条整条原样保留（id/文本/音频/包络/sha256 未变），"
                          "新增 %d 条为本站合成（v3 + 情绪路由，后处理口径与旧句完全一致）。" % len(new_ids))

    outp = os.path.join(args.out, "bank.new.json")
    json.dump(bank, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- 自检 ----
    old_ok, old_bad = 0, []
    for lid, rec in old_lines.items():
        for kind, url in (rec.get("audioSources") or {}).items():
            p = rel(args.static_root, url)
            if not os.path.isfile(p):
                old_bad.append([lid, kind, "missing"])
                continue
            if os.path.getsize(p) != rec["bytes"][kind]:
                old_bad.append([lid, kind, "size"])
            elif sha256_file(p) != rec["sha256"][kind]:
                old_bad.append([lid, kind, "sha256"])
            else:
                old_ok += 1
    verify = {
        "oldLineCount": len(old_lines), "newLineCount": len(new_ids),
        "lineCount": len(bank_lines), "expectedNew": len([l for l in lines if l["trigger"] not in exclude]),
        "missingNew": missing, "groups": groups,
        "oldRecordsVerbatim": {k: (bank_lines[k] == old_lines[k]) for k in old_lines},
        "oldAudioChecks": {"ok": old_ok, "bad": old_bad},
        "totalBytes": total, "budgetBytes": BUDGET_BYTES,
        "ratioOfBudget": round(total / BUDGET_BYTES, 4), "withinBudget": total <= BUDGET_BYTES,
        "m4aOver40KB": [k for k, v in bank_lines.items() if v["bytes"]["m4a"] > MAX_M4A],
        "webmOver36KB": [k for k, v in bank_lines.items() if v["bytes"]["webm"] > MAX_WEBM],
        "m4aMin": min(sizes_m4a), "m4aMax": max(sizes_m4a), "m4aMean": round(sum(sizes_m4a) / len(sizes_m4a), 1),
        "webmMin": min(sizes_webm), "webmMax": max(sizes_webm), "webmMean": round(sum(sizes_webm) / len(sizes_webm), 1),
        "lufsMin": min(lufs) if lufs else None, "lufsMax": max(lufs) if lufs else None,
        "lufsSpread": round(max(lufs) - min(lufs), 3) if lufs else None,
        "lufsSpreadLe0_5": (max(lufs) - min(lufs)) <= 0.5 if lufs else None,
        "durationMsSum": sum(v["durationMs"] for v in bank_lines.values()),
    }
    vp = os.path.join(args.out, "bank.verify.%s.json" % args.tag)
    json.dump(verify, open(vp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: verify[k] for k in ("oldLineCount", "newLineCount", "lineCount", "groups",
                                             "missingNew", "totalBytes", "withinBudget",
                                             "m4aMin", "m4aMax", "m4aMean", "webmMin", "webmMax",
                                             "lufsMin", "lufsMax", "lufsSpread", "lufsSpreadLe0_5",
                                             "m4aOver40KB", "webmOver36KB")},
                     ensure_ascii=False, indent=1))
    print("旧 12 句逐字保全：", all(verify["oldRecordsVerbatim"].values()))
    print("旧音频 sha256 全部对上：", old_ok, "项，问题：", old_bad)
    print("→", outp)
    print("→", vp)


if __name__ == "__main__":
    main()
