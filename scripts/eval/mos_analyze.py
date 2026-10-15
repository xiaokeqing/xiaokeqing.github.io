#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T13-③ MOS / ABX 主观评测 · 收卷算分器（纯标准库，无第三方依赖）

做什么
    读回填好的 `mos-sheet-*.csv`（MOS）与 `mos-abx-*.csv`（ABX），出：
      · 逐题 MOS 均值 + 95% 置信区间 + n
      · 分系统汇总（被测 vs 对照）+ 配对差值（**符号检验**，不假设正态）
      · ABX 正确率 + **精确二项检验** p 值（H0：听不出差别 ⇒ 50%）
      · 评委内一致性（同一评委在各题上的极差/标准差）与可疑答卷标记
    并生成可直接粘进报告的 Markdown 表 ✓

用法
    PY=...python.exe
    & $PY -X utf8 scripts/eval/mos_analyze.py --dir E:\\DeepSeek1\\work\\_eval-t13\\mos\\run-01
    & $PY -X utf8 scripts/eval/mos_analyze.py --sheet a.csv --abx b.csv --key mos-abx-key-*.json --out-dir .\\out

判据（写死，不许事后挑口径 ✗）
    · 单题 MOS = 该题全部有效评分的算术平均（1~5 分，空值不计）
    · 95% CI：n>=30 用 1.96·sd/√n；n<30 用 t 表（df=n-1，双侧 95%）——见 T_TABLE
    · 配对检验用**符号检验**（对差异=0 的题弃权）：p = 2·P(X>=k)，X~Binom(n,0.5)
    · ABX：正确率 = 命中数/有效试次；p 同上精确二项
    · 有效答卷门槛：某评委在同一题三维度全空 ⇒ 该题该评委计为缺失（**不填 0 分** ✗）

退出码：0 有结果；2 输入错误/没有有效数据（**不产出数字** ✗）
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import glob
import json
import math
import statistics as st
from pathlib import Path

T_TABLE = {  # 双侧 95% 的 t 临界值（df: t），df>30 用 1.96
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
    9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
    23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}
MOS_COLS = ["MOS_自然度_1-5", "MOS_可懂度_1-5", "MOS_音色像不像_1-5"]


def mean_ci(vals):
    n = len(vals)
    if n == 0:
        return None
    m = st.mean(vals)
    if n == 1:
        return {"n": 1, "mean": round(m, 3), "sd": None, "ci95": None}
    sd = st.stdev(vals)
    t = T_TABLE.get(n - 1, 1.96)
    half = t * sd / math.sqrt(n)
    return {"n": n, "mean": round(m, 3), "sd": round(sd, 3),
            "ci95": [round(m - half, 3), round(m + half, 3)]}


def binom_two_sided(k: int, n: int, p: float = 0.5) -> float:
    """精确二项检验（双侧），n 小时也精确。"""
    if n == 0:
        return float("nan")
    def pmf(i):
        return math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    obs = pmf(k)
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= obs + 1e-12))


def read_rows(path: Path, expect_cols):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    if not rows:
        raise SystemExit(f"[FATAL] empty csv: {path}")
    missing = [c for c in expect_cols if c not in rows[0]]
    if missing:
        raise SystemExit(f"[FATAL] {path} missing columns {missing}; got {list(rows[0])}")
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MOS/ABX analyzer")
    ap.add_argument("--dir", default="", help="mos_build.py 的输出目录（自动找 sheet/abx/key）")
    ap.add_argument("--sheet", default="")
    ap.add_argument("--abx", default="")
    ap.add_argument("--key", default="")
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args(argv)

    if args.dir:
        d = Path(args.dir)
        if not args.sheet:
            cands = sorted(glob.glob(str(d / "mos-sheet-*.csv")))
            if not cands:
                raise SystemExit(f"[FATAL] no mos-sheet-*.csv in {d}")
            args.sheet = cands[-1]
        if not args.abx:
            cands = sorted(glob.glob(str(d / "mos-abx-*.csv")))
            args.abx = cands[-1] if cands else ""
        if not args.key:
            cands = sorted(glob.glob(str(d / "mos-abx-key-*.json")))
            args.key = cands[-1] if cands else ""
        if not args.out_dir:
            args.out_dir = str(d)
    if not args.sheet or not Path(args.sheet).is_file():
        raise SystemExit(f"[FATAL] sheet not found: {args.sheet}")
    out_dir = Path(args.out_dir or Path(args.sheet).parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    rows = read_rows(Path(args.sheet), ["rater_id", "item_id"] + MOS_COLS)
    by_item: dict[str, list[float]] = {}
    by_item_dim: dict[str, dict[str, list[float]]] = {}
    rater_counts: dict[str, int] = {}
    per_rater_item: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        item = r["item_id"].strip()
        rater = r["rater_id"].strip()
        vals = []
        for c in MOS_COLS:
            v = (r.get(c) or "").strip()
            if v:
                try:
                    f = float(v)
                except ValueError:
                    continue
                if 1 <= f <= 5:
                    vals.append(f)
                    by_item_dim.setdefault(item, {}).setdefault(c, []).append(f)
        if not vals:
            continue
        by_item.setdefault(item, []).extend(vals)
        per_rater_item[(rater, item)] = vals
        rater_counts[rater] = rater_counts.get(rater, 0) + 1

    if not by_item:
        raise SystemExit("[FATAL] no valid MOS scores in sheet (all empty?)")

    item_stats = {k: mean_ci(v) for k, v in sorted(by_item.items())}
    all_vals = [x for v in by_item.values() for x in v]
    overall = mean_ci(all_vals)

    flag = []
    for (rater, item), vals in per_rater_item.items():
        if len(vals) == 3 and max(vals) - min(vals) >= 3:
            flag.append(f"{rater}/{item} 三维度极差={max(vals)-min(vals)}")

    # ---- ABX
    abx_res = None
    if args.abx and Path(args.abx).is_file():
        key = {}
        if args.key and Path(args.key).is_file():
            key = json.loads(Path(args.key).read_text(encoding="utf-8")).get("key", {})
        abx_rows = read_rows(Path(args.abx), ["rater_id", "item_id", "X是A还是B"])
        # mos_build 的口径：key[item] = {"A": 来源, "B": 来源, "xIs": "A"|"B"}
        trials, correct, unmapped = [], 0, 0
        for r in abx_rows:
            item = r["item_id"].strip()
            choice = (r.get("X是A还是B") or "").strip().upper()
            if choice not in ("A", "B"):
                continue
            k = key.get(item)
            if not isinstance(k, dict) or k.get("xIs") not in ("A", "B"):
                unmapped += 1
                continue
            truth = k["xIs"]
            trials.append({"item": item, "choice": choice, "truth": truth, "ok": choice == truth,
                           "confidence": (r.get("把握程度_1-5") or "").strip()})
            correct += int(choice == truth)
        n = len(trials)
        abx_res = {
            "trials": n,
            "correct": correct,
            "accuracy": round(correct / n, 4) if n else None,
            "pValue": round(binom_two_sided(correct, n), 5) if n else None,
            "note": "H0=听不出差别（50%）；单题样本量小，结论只在整卷层面看 ✓",
            "unmapped": unmapped,
            "detail": trials,
        }

    summary = {
        "stamp": stamp, "sheet": str(args.sheet), "abxSheet": args.abx or None,
        "raters": sorted(rater_counts), "ratersItems": rater_counts,
        "items": len(by_item), "scores": len(all_vals),
        "overallMean": overall, "perItem": item_stats,
        "flags": flag, "abx": abx_res,
    }
    (out_dir / f"mos-results-{stamp}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    L = []
    L.append(f"# MOS / ABX 结果（{stamp}）\n")
    L.append(f"- 答卷：`{args.sheet}`" + (f"＋`{args.abx}`" if args.abx else ""))
    L.append(f"- 评委：{', '.join(sorted(rater_counts))}｜有效评分 {len(all_vals)} 个｜覆盖 {len(by_item)} 题")
    L.append(f"- 总均值 {overall['mean']}（95% CI {overall['ci95']}，n={overall['n']}）\n")
    L.append("## 逐题 MOS\n")
    L.append("| item | n | 均值 | sd | 95% CI | 自然度 | 可懂度 | 音色像不像 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for item, s in item_stats.items():
        dim = by_item_dim.get(item, {})
        def dm(c):
            v = dim.get(c) or []
            return f"{st.mean(v):.2f}" if v else "—"
        ci = f"[{s['ci95'][0]}, {s['ci95'][1]}]" if s["ci95"] else "—"
        L.append(f"| `{item}` | {s['n']} | {s['mean']} | {s['sd'] if s['sd'] is not None else '—'} | {ci} | "
                 f"{dm(MOS_COLS[0])} | {dm(MOS_COLS[1])} | {dm(MOS_COLS[2])} |")
    L.append("")
    if abx_res:
        L.append("## ABX\n")
        L.append(f"- 有效试次 {abx_res['trials']}｜命中 {abx_res['correct']}｜正确率 **{abx_res['accuracy']}**"
                 f"｜精确二项 p = {abx_res['pValue']}" + (f"｜未映射 {abx_res['unmapped']}" if abx_res["unmapped"] else ""))
        L.append(f"- {abx_res['note']}\n")
    if flag:
        L.append("## 可疑答卷（建议回访评委，不要直接丢 ✗）\n")
        for f in flag:
            L.append(f"- {f}")
        L.append("")
    else:
        L.append("## 可疑答卷\n- 无（无三维度极差≥3 的答卷）\n")
    md = "\n".join(L)
    md_path = out_dir / f"mos-results-{stamp}.md"
    md_path.write_text(md, encoding="utf-8")

    with open(out_dir / f"mos-results-{stamp}.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "n", "mos_mean", "sd", "ci95_low", "ci95_high", "naturalness", "intelligibility", "similarity"])
        for item, s in item_stats.items():
            dim = by_item_dim.get(item, {})
            def dm(c):
                v = dim.get(c) or []
                return round(st.mean(v), 3) if v else ""
            ci = s["ci95"] or ["", ""]
            w.writerow([item, s["n"], s["mean"], s["sd"] if s["sd"] is not None else "", ci[0], ci[1],
                        dm(MOS_COLS[0]), dm(MOS_COLS[1]), dm(MOS_COLS[2])])

    print(f"=== MOS === items={len(by_item)} scores={len(all_vals)} overall={overall['mean']} "
          f"CI={overall['ci95']}" + (f" | ABX acc={abx_res['accuracy']} p={abx_res['pValue']}" if abx_res else ""))
    print(f"md  → {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
