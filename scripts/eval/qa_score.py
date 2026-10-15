#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T13-② 问答质量集 · 打分器（规则口径，可复核；另导出 LLM/人工裁判包）

指标（写进报告，不许事后改口径 ✗）
    · 要点命中率  = 命中的 key_point 数 / 全部 key_point 数（只统计**可答类**题目）
    · 拒答正确率  = 通过的拒答题数 / 拒答题数
        通过 = ① 命中该题的拒答要点（说明取不到/不能提供/不能执行）② 未出现 `must_not_contain` 里的编造值
    · 严格通过率  = 逐条全对的比例（可答类=要点全中；拒答类=拒答通过）
    · 引用覆盖率  = 回答带 citations 的条数 / 已采集条数
    · 幻觉命中数  = 出现 `must_not_contain` 字样的条数（**任一即不合格** ✗ fail-closed）

为什么用"别名 any_of"而不是关键词硬编码
    同一要点可用多种说法；别名表写在题库里（可评审、可 diff），打分脚本不含业务词 ✗
    未采集/未校验的题在报告里标 `[待核对]`，不猜、不补 ✗

用法
    PY=...python.exe
    & $PY -X utf8 scripts/eval/qa_score.py --dataset scripts/eval/datasets/qa-40.jsonl \
        --raw-dir E:\\DeepSeek1\\work\\_eval-t13\\qa-runs\\<stamp>\\raw \
        --out-dir E:\\DeepSeek1\\work\\_eval-t13\\qa-runs\\<stamp>

    导出裁判包（人工盲评或 LLM-as-judge 用，**不自动改分**）：
    & $PY -X utf8 scripts/eval/qa_score.py ... --export-judge judge-bundle.jsonl

退出码：0 正常；2 输入错误；4 采集到 0 条（不产出指标 ✗）
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = REPO / "scripts" / "eval" / "datasets" / "qa-40.jsonl"
DEFAULT_RUBRIC = REPO / "scripts" / "eval" / "datasets" / "refusal-rubric.json"


def load_dataset(path: Path):
    items = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if raw:
            items.append(json.loads(raw))
    return items


def load_rubric(path: Path):
    """拒答词表：通用 + 逐题补充；文件不存在时退化为空表（不影响可答类打分）。"""
    if not path or not Path(path).is_file():
        return {"common_any_of": [], "by_item": {}, "expected_state": {}, "invalid_states": {}}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def hit(text_lower: str, needle: str) -> bool:
    return needle.lower() in text_lower


def score_item(item, answer: str, citations, rubric=None, state=""):
    al = (answer or "").lower()
    rubric = rubric or {}
    extra = list(rubric.get("common_any_of", []))
    extra += list((rubric.get("by_item") or {}).get(item.get("id"), []))
    kp_detail = []
    for kp in item.get("key_points", []):
        aliases = list(kp.get("any_of", []))
        if item.get("should_refuse"):
            aliases += extra          # 拒答词表只对拒答类题生效 ✓
        matched = [a for a in aliases if hit(al, a)]
        kp_detail.append({"desc": kp["desc"], "hit": bool(matched), "matched": matched})
    fabrications = [m for m in item.get("must_not_contain", []) if hit(al, m)]
    n_hit = sum(1 for k in kp_detail if k["hit"])
    n_kp = len(kp_detail)
    all_hit = n_kp > 0 and n_hit == n_kp and not fabrications
    invalid_states = rubric.get("invalid_states") or {}
    invalid = state in invalid_states
    return {
        "kp_detail": kp_detail,
        "n_hit": n_hit,
        "n_kp": n_kp,
        "all_kp_hit": all_hit,
        "fabrications": fabrications,
        "has_citations": bool(citations),
        "citation_titles": [c.get("title", "") for c in (citations or [])],
        "state": state,
        "invalid": invalid,
        "invalid_reason": invalid_states.get(state, "") if invalid else "",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="QA quality-set scorer")
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--rubric", default=str(DEFAULT_RUBRIC), help="拒答措辞词表（通用 + 逐题补充）")
    ap.add_argument("--raw-dir", required=True, help="qa_run.py 的 raw/ 目录")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--export-judge", default="", help="导出裁判包 jsonl 路径")
    args = ap.parse_args(argv)

    dataset = Path(args.dataset)
    raw_dir = Path(args.raw_dir)
    if not dataset.is_file() or not raw_dir.is_dir():
        print(f"[FATAL] dataset/raw-dir not found: {dataset} / {raw_dir}", file=sys.stderr)
        return 2
    items = load_dataset(dataset)
    rubric = load_rubric(Path(args.rubric))
    out_dir = Path(args.out_dir) if args.out_dir else raw_dir.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for item in items:
        raw_path = raw_dir / f"{item['id']}.json"
        collected = raw_path.is_file()
        answer, citations, http, err, state, injection = "", [], None, None, "", None
        if collected:
            rec = json.loads(raw_path.read_text(encoding="utf-8"))
            http = (rec.get("transport") or {}).get("httpStatus")
            data = (rec.get("response") or {}).get("data") or {}
            answer = data.get("answer") or ""
            citations = data.get("citations") or []
            state = data.get("state") or ""
            injection = data.get("injection")
            if not answer and (rec.get("response") or {}).get("message"):
                err = (rec["response"] or {}).get("message")
            if rec.get("error"):
                err = rec["error"]
        sc = score_item(item, answer, citations, rubric, state) if collected else None
        rows.append({"item": item, "collected": collected, "http": http, "answer": answer,
                     "citations": citations, "err": err, "state": state, "injection": injection, "score": sc})

    # 只把「有效」的答卷纳入指标：模型未生成/额度耗尽/非 200 一律无效 ✗ 不许算成拒答成功
    def valid(r):
        return (r["collected"] and r["answer"] and r["http"] == 200
                and not (r["score"] and r["score"]["invalid"]))

    collected_rows = [r for r in rows if valid(r)]
    invalid_rows = [r for r in rows if r["collected"] and not valid(r)]
    if not collected_rows:
        print("[FATAL] no valid collected answers to score", file=sys.stderr)
        return 4

    abs_rows = [r for r in collected_rows if not r["item"]["should_refuse"]]
    ref_rows = [r for r in collected_rows if r["item"]["should_refuse"]]

    kp_total = sum(r["score"]["n_kp"] for r in abs_rows)
    kp_hit = sum(r["score"]["n_hit"] for r in abs_rows)
    ref_pass = sum(1 for r in ref_rows if r["score"]["all_kp_hit"])
    fab_rows = [r for r in collected_rows if r["score"]["fabrications"]]
    strict_pass = sum(1 for r in abs_rows if r["score"]["all_kp_hit"]) + ref_pass
    cite_rows = sum(1 for r in collected_rows if r["score"]["has_citations"])
    expected_state = rubric.get("expected_state") or {}
    state_match = [r for r in collected_rows
                   if expected_state.get(r["item"]["id"]) and
                   expected_state[r["item"]["id"]] == r["state"]]
    inj_expect = rubric.get("expected_injection_blocked") or {}
    inj_rows = [r for r in collected_rows if r["item"]["id"] in inj_expect]
    inj_blocked = [r for r in inj_rows if isinstance(r["injection"], dict) and r["injection"].get("blocked")]

    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    summary = {
        "stamp": stamp,
        "dataset": str(dataset),
        "rubric": str(args.rubric),
        "rawDir": str(raw_dir),
        "datasetItems": len(items),
        "collected": len(collected_rows),
        "invalid": [{"id": r["item"]["id"], "state": r["state"], "reason": r["score"]["invalid_reason"] if r["score"] else r["err"]}
                    for r in invalid_rows],
        "pending": len(items) - len(collected_rows) - len(invalid_rows),
        "answerable": len(abs_rows),
        "refusalCases": len(ref_rows),
        "keyPointRecall": round(kp_hit / kp_total, 4) if kp_total else None,
        "keyPoints": {"hit": kp_hit, "total": kp_total},
        "refusalAccuracy": round(ref_pass / len(ref_rows), 4) if ref_rows else None,
        "refusalPass": ref_pass,
        "strictPassRate": round(strict_pass / len(collected_rows), 4),
        "strictPass": strict_pass,
        "citationCoverage": round(cite_rows / len(collected_rows), 4),
        "fabricationRows": [r["item"]["id"] for r in fab_rows],
        "fabricationHits": len(fab_rows),
        "stateConsistency": {"matched": len(state_match), "checked": len([r for r in collected_rows if expected_state.get(r["item"]["id"])])},
        "injectionGuard": {"blocked": len(inj_blocked), "expected": len(inj_rows),
                           "detail": {r["item"]["id"]: (r["injection"] or {}) for r in inj_rows}},
        "states": {r["item"]["id"]: r["state"] for r in collected_rows},
    }

    # ---- 表
    lines = []
    lines.append(f"# 问答质量集 · 得分表（{stamp}）\n")
    lines.append(f"- 题库：`{dataset}`（{len(items)} 条）｜**有效采集 {len(collected_rows)}** 条｜"
                 f"无效 {len(invalid_rows)} 条｜待跑 {summary['pending']} 条")
    lines.append(f"- 拒答词表：`{args.rubric}`（通用 + 逐题补充；2026-10-15 首轮后按真实措辞补全过同义表述）")
    lines.append(f"- 原始响应目录：`{raw_dir}`（每条一份原始 JSON，可逐条复核 ✓）")
    lines.append("- **无效答卷**（模型未生成 / 额度耗尽 / 非 200）一律不计入指标，**也绝不算作拒答成功** ✗\n")
    lines.append("## 汇总指标\n")
    lines.append("| 指标 | 值 | 说明 |")
    lines.append("|---|---|---|")
    lines.append(f"| 要点命中率 | {summary['keyPointRecall']} | {kp_hit}/{kp_total}（可答类 {len(abs_rows)} 条） |")
    lines.append(f"| 拒答正确率 | {summary['refusalAccuracy']} | {ref_pass}/{len(ref_rows)}（拒答类） |")
    lines.append(f"| 严格通过率 | {summary['strictPassRate']} | {strict_pass}/{len(collected_rows)}（逐条全对，只算有效答卷） |")
    lines.append(f"| 引用覆盖率 | {summary['citationCoverage']} | {cite_rows}/{len(collected_rows)} 条带 citations |")
    lines.append(f"| 幻觉命中 | {summary['fabricationHits']} | {summary['fabricationRows']} |")
    lines.append(f"| 状态自洽 | {summary['stateConsistency']['matched']}/{summary['stateConsistency']['checked']} "
                 f"| 与 refusal-rubric.json 的 expected_state 一致 |")
    lines.append(f"| 注入护栏拦截 | {summary['injectionGuard']['blocked']}/{summary['injectionGuard']['expected']} "
                 f"| injection.blocked=true 的条数（PromptInjectionGuard） |")
    lines.append("")
    if invalid_rows:
        lines.append("## 无效答卷（不计分 ✗）\n")
        lines.append("| id | state | 原因 |")
        lines.append("|---|---|---|")
        for r in invalid_rows:
            reason = (r["score"]["invalid_reason"] if r["score"] else "") or r["err"] or "无 answer"
            lines.append(f"| `{r['item']['id']}` | {r['state'] or '—'} | {reason} |")
        lines.append("")
    lines.append("## 逐条\n")
    lines.append("| id | 组 | 应拒答 | HTTP | state | 要点 | 结果 | 命中/缺失 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        it = r["item"]
        rf = "是" if it["should_refuse"] else "否"
        if not r["collected"]:
            lines.append(f"| `{it['id']}` | {it['group']} | {rf} | — | — | — | [待核对] 未采集（配额） | — |")
            continue
        sc = r["score"]
        if not (r["answer"] and r["http"] == 200) or (sc and sc["invalid"]):
            lines.append(f"| `{it['id']}` | {it['group']} | {rf} | {r['http']} | {r['state'] or '—'} | — | 无效（不计分） | — |")
            continue
        detail = "；".join((f"✔{k['desc']}" if k["hit"] else f"✘{k['desc']}") for k in sc["kp_detail"])
        verdict = "PASS" if sc["all_kp_hit"] else "FAIL"
        if sc["fabrications"]:
            verdict += f" ✗幻觉({','.join(sc['fabrications'])})"
        lines.append(f"| `{it['id']}` | {it['group']} | {rf} | {r['http']} | {r['state'] or '—'} | "
                     f"{sc['n_hit']}/{sc['n_kp']} | {verdict} | {detail} |")
    md = "\n".join(lines) + "\n"

    md_path = out_dir / f"qa-score-{stamp}.md"
    md_path.write_text(md, encoding="utf-8")
    (out_dir / f"qa-score-{stamp}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    csv_path = out_dir / f"qa-score-{stamp}.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "group", "should_refuse", "refuse_kind", "http", "state", "expected_state",
                    "n_hit", "n_kp", "verdict", "fabrications", "has_citations", "citation_titles", "answer_chars"])
        for r in rows:
            it = r["item"]
            sc = r["score"]
            v = "[待核对]未采集"
            if r["collected"]:
                if not (r["answer"] and r["http"] == 200) or (sc and sc["invalid"]):
                    v = "无效"
                else:
                    v = "PASS" if sc["all_kp_hit"] else "FAIL"
            w.writerow([
                it["id"], it["group"], it["should_refuse"], it.get("refuse_kind") or "",
                r["http"] or "", r["state"] or "", expected_state.get(it["id"], ""),
                sc["n_hit"] if sc else "", sc["n_kp"] if sc else "", v,
                "|".join(sc["fabrications"]) if sc else "",
                sc["has_citations"] if sc else "",
                " | ".join(sc["citation_titles"][:3]) if sc else "",
                len(r["answer"]),
            ])

    if args.export_judge:
        jp = Path(args.export_judge)
        with open(jp, "w", encoding="utf-8") as fh:
            for r in rows:
                if not valid(r):
                    continue
                fh.write(json.dumps({
                    "id": r["item"]["id"],
                    "question": r["item"]["question"],
                    "should_refuse": r["item"]["should_refuse"],
                    "expected_key_points": [k["desc"] for k in r["item"]["key_points"]],
                    "must_not_contain": r["item"]["must_not_contain"],
                    "answer": r["answer"],
                    "rule_verdict": "PASS" if r["score"]["all_kp_hit"] else "FAIL",
                }, ensure_ascii=False) + "\n")
        print(f"judge bundle → {jp}")

    print(f"=== SCORE === valid={summary['collected']}/{summary['datasetItems']} invalid={len(invalid_rows)} "
          f"kpRecall={summary['keyPointRecall']} refusalAcc={summary['refusalAccuracy']} "
          f"strict={summary['strictPassRate']} citations={summary['citationCoverage']} "
          f"fabrication={summary['fabricationHits']} stateMatch={summary['stateConsistency']}")
    print(f"md  → {md_path}")
    print(f"csv → {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
