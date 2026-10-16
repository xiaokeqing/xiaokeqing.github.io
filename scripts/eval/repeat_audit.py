#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复读率审计脚本（只读；口径 = `docs/后端问答能力升级方案-20261015.md` §10 追加节）

定位（2026-10-16 站主拍板）
    **评测链上的回归工具**：每次改 prompt / 采样参数（T25 §12、T14 V3）前后**各跑一次**，
    看 D1/D2/D3 有没有变差。它**不**用于对外宣称"模型复读率 = xx%" ✗。
    ★ 红线（防误读）：**D1 高 ≠ 模型在复读**。现有语料里 D1 主要来自「模板抬头 + 同 topic 的模板正文」，
      不是模型侧口头禅复读；D2 的重复也 100% 来自 `rule-based-eval-simulated` 的相同模板正文。
      详见 `docs/复读率审计脚本-20261016.md` §1/§5。

它做什么
    · 吃「响应审计数据」（json / jsonl / 目录 / stdin 均可），算出文档 §10.1 定义的三条指标：
        D1 openerRepeatRate@3     开场白复读率（归一化开头前 8 字符 vs 近 3 轮，会话内）
        D2 verbatimRepeatRate     逐字复读率（指纹：优先 ttsTextHash，缺字段回退归一化全文 sha1）
        D3 catchphraseTop1Share   口头禅 top1 占比（≤3 条**事先冻结**的正则，见 catchphrases.json）
    · 输出 `--json report.json`（机读，含每个会话的明细）+ 人读一页 markdown。
    · 分母口径照文档 §10.2「排除项」：state ∈ {model-failed, retrieval-failed, no-retrieval,
      input-insufficient}、HTTP != 200、无 answer 正文的记录**一律不计入**（也绝不当成"没复读"）。
      **另加一条（2026-10-16 站主拍板）：`state=*-eval-simulated`（评测模拟，非真实流量）默认不进分母**；
      报告里**同时给"不含 / 含评测模拟"两行**，`--include-simulated` 可显式纳入当对照。
    · `--selftest`：内置合成样本（含"同一句重复 8 次"的构造），断言指标算对，打印 PASS/FAIL。

为什么这么定口径（依据）
    · 归一化 = 逐字复用已存在的实现 `E:\\DeepSeek1\\work\\_t14\\verify_t14_contract.py` 的 `norm()`
      ＋ `[:8]` —— 与 §10.1 D1「去空白/标点/引号与 markdown 记号 → 取前 8 个字符」同一口径，
      **避免第二套归一化**。
    · 逐字复读 = `(n - |distinct|) / n`，与 `verify_t14_contract.py` 的
      `verbatimRepeatRate` 同一算法（"不是首现的轮次占比"，等价于"出现过的重复数 / 轮次"）。
    · 剥壳（去固定抬头与引用尾）：§10.1 说"口径与 `scripts/eval/qa_score.py` 一致"，但**实测该文件里
      不存在任何剥壳实现**（296 行全文读过：只有 lowercase 包含判断）⇒ 已定案（2026-10-16）改为读
      **版本化的模板串清单** `strippers.v1.json`（每条含 匹配串 + 出处 + 加入日期 + 理由，**只追加不修改**，
      要改就出 v2）；报告里同时给出**未剥壳**的 D1 作为上界对照，谁都不藏。
    · 这两份配置（`catchphrases.json` / `strippers.v1.json`）**必须与脚本同目录**，否则别人跑不了。

纪律
    · 只读：不写任何被审计目录，不发任何请求，不消耗任何额度。
    · 不打印任何密钥/Token（本脚本只处理回答正文与状态字段）。

用法
    PY="C:\\Users\\T\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe"
    # ① 目录/文件（可重复 --input）
    & $PY -X utf8 F:\\7AAA\\AI\\blog\\scripts\\eval\\repeat_audit.py `
        --input E:\\DeepSeek1\\work\\_rep-audit\\srv1\\eval-runs --json report.json --md report.md
    # ② stdin jsonl（便于以后接评测池导出）
    Get-Content x.jsonl | & $PY -X utf8 ...\\repeat_audit.py - --json r.json --md r.md
    # ③ 自检
    & $PY -X utf8 ...\\repeat_audit.py --selftest

退出码：0 正常；1 自检失败；2 输入错误；4 有效记录 0 条（不产出指标 ✗）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

# ★GBK 修复（2026-10-16）：Windows 上 `python scripts/eval/repeat_audit.py --selftest` 会在
#   `print()` 那一步炸 `UnicodeEncodeError: 'gbk' codec can't encode character '\u21d2'`
#   —— 控制台/管道的默认编码是 cp936（GBK），而本脚本的说明与断言名里用了 ⇒ ★ ✓ ✗ → 这类字符。
#   这是**显示层**的编码问题，跟指标算得对不对无关；不修的话 `--selftest` 会以非 0 退出，
#   在 CI / 批处理里会被误读成"断言失败"。这里把两个流显式改成 UTF-8（拿不到就安静跳过）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
TOOL = "repeat_audit.py"
VERSION = "1.0"
SPEC_REF = "docs/后端问答能力升级方案-20261015.md §10（D1/D2/D3 + 排除项）"
SPEC_REF2 = "docs/T14-情绪决策改动包-20261015.md V3（ttsTextHash 指纹）"

# ---------------------------------------------------------------- 分母口径
# §10.2「排除项」原文：model-failed / 额度耗尽 / 非 200 的答卷一律不计入本指标
EXCLUDE_STATES = {"model-failed", "retrieval-failed", "no-retrieval", "input-insufficient"}

# ---------------------------------------------------------------- 归一化（复用既有实现）
# 逐字抄自 E:\DeepSeek1\work\_t14\verify_t14_contract.py 的 norm()（正则字符类原样）
_PUNCT = r"[，。、；：？！,.;:?!\"'“”‘’（）()\[\]【】#*>`~\-—…]+"
OPENER_CHARS = 8


def norm(s: str) -> str:
    """去空白 + 去标点/引号/markdown 记号（与 verify_t14_contract.py 同一实现）"""
    s = re.sub(r"[\s\u3000]+", "", s or "")
    return re.sub(_PUNCT, "", s)


# ---------------------------------------------------------------- 剥壳（固定抬头 / 引用尾）
# 每条的出处都是**后端源码的固定模板串**（`sb.append("…")` / `body = "…"` 的字面量），
# 不是从答案里事后挑的。这就是 §10.1「先去掉回答里固定的抬头与引用尾」的物理依据。
SHELL_HEAD = [
    (r"^##\s*多智能体协同结果\s*$", "MultiAgentCoordinatorImpl.java:1387"),
    (r"^>\s*调度员判定本次任务为.*$", "MultiAgentCoordinatorImpl.java:1388"),
    (r"^##\s*研判结论\s*$", "MultiAgentCoordinatorImpl.java:710/727/733"),
    (r"^##\s*取证发现\s*$", "MultiAgentCoordinatorImpl.java:1187"),
    (r"^>\s*证据采集方式：.*$", "MultiAgentCoordinatorImpl.java:1188"),
    (r"^##\s*处置结果（评测模式）\s*$", "MultiAgentCoordinatorImpl.java:1355"),
    (r"^>\s*\*\*评测身份：.*$", "MultiAgentCoordinatorImpl.java:1356"),
    (r"^##\s*处置结果\s*$", "MultiAgentCoordinatorImpl.java:1276"),
    (r"^##\s*处置类请求：公开演示不执行\s*$", "MultiAgentCoordinatorImpl.java:1221"),
    (r"^##\s*知识库参考（未经 AI 加工）\s*$", "MultiAgentCoordinatorImpl.java:714/730/737"),
    (r"^##\s*本次没有生成结论\s*$", "PublicAskService.java:359"),
    (r"^###\s*证据解读\s*$", "MultiAgentCoordinatorImpl.java:1192"),
    (r"^>\s*结论生成方式：.*$", "MultiAgentCoordinatorImpl.java:505/1194/1221区/1357"),
    (r"^>\s*state=[\w-]+\s*$", "MultiAgentCoordinatorImpl.java:485/514/540/944/1358 / PublicAskService.java:360"),
    (r"^原因：.*$", "PublicAskService.java:361"),
    (r"^⚠️\s*注意：.*$", "MultiAgentCoordinatorImpl.java:1392"),
    (r"^---\s*$", "markdown 分隔线（多段拼接产生）"),
]
SHELL_TAIL = [
    (r"^###\s*命中的公开知识库片段", "PublicKbService.java:189（引用尾起点）"),
    (r"^>\s*说明：以上为模型基于", "MultiAgentCoordinatorImpl.java:976/979（模板说明尾）"),
]


def _cut_tail(lines, tail):
    for i, ln in enumerate(lines):
        t = ln.strip()
        if any(re.search(p, t) for p, _ in tail):
            return lines[:i]
    return lines


def _strip_leading(lines, head):
    changed = True
    while changed and lines:
        changed = False
        while lines and not lines[0].strip():
            lines.pop(0)
            changed = True
        if lines:
            t = lines[0].strip()
            for p, _ in head:
                if re.search(p, t):
                    lines.pop(0)
                    changed = True
                    break
    while lines and (not lines[-1].strip() or re.search(r"^---\s*$", lines[-1].strip())):
        lines.pop()
    return lines


def _strip_with(text: str, head, tail) -> str:
    """剥壳内核：给什么清单就用什么清单"""
    lines = (text or "").replace("\r\n", "\n").split("\n")
    return "\n".join(_strip_leading(_cut_tail(lines, tail), head)).strip()


def strip_shell(text: str, head=None, tail=None) -> str:
    """字面量口径（默认、主口径）：只剥**清单里写死的**抬头与引用尾（head=None 时用内置清单）"""
    head = SHELL_HEAD if head is None else head
    tail = SHELL_TAIL if tail is None else tail
    return _strip_with(text, head, tail)


def strip_structural(text: str, head=None, tail=None) -> str:
    """结构口径（上界对照）：把开头的 markdown 标题 / 引用块 / 分隔线统统当抬头剥掉。
    它比字面量口径更狠 ⇒ 得到的 D1 是"连模板结构都去掉后"的下界，用来判断
    高 D1 到底是"模型复读"还是"模板抬头"造成的。"""
    lines = (text or "").replace("\r\n", "\n").split("\n")
    lines = _cut_tail(lines, SHELL_TAIL)
    head = [(r"^#{1,6}\s", "markdown 标题"), (r"^>\s", "引用块"), (r"^---\s*$", "分隔线"),
            (r"^⚠️", "模板注意行"), (r"^```", "代码围栏")]
    return "\n".join(_strip_leading(lines, head)).strip()


def strip_none(text: str, head=None, tail=None) -> str:
    return text or ""


SHELL_FN = strip_shell          # 主口径；CLI 可覆盖
SHELL_MODE = "literal"          # literal | structural | none | file:<path>
DEFAULT_STRIPPER = "strippers.v1.json"   # 版本化冻结的模板串清单（只追加不修改；要改就出 v2）


def load_strippers(path: Path):
    """读版本化剥壳清单。返回 (spec, head, tail)；文件不存在则回退内置清单（并在报告里标明）"""
    if not path.is_file():
        return ({"version": "builtin-fallback", "file": str(path),
                 "note": "strippers JSON 缺失 ⇒ 用脚本内置清单；这不算冻结口径，请补文件"}, SHELL_HEAD, SHELL_TAIL)
    spec = json.loads(path.read_text(encoding="utf-8"))
    head = [(e["pattern"], e["source"]) for e in spec.get("head", [])]
    tail = [(e["pattern"], e["source"]) for e in spec.get("tail", [])]
    spec["file"] = str(path)
    spec["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return spec, head, tail


def _sha256_file(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:
        return ""


def opener_key(text: str, shell=None) -> str:
    fn = SHELL_FN if shell is None else shell
    return norm(fn(text))[:OPENER_CHARS]


# ---------------------------------------------------------------- 指纹
def fingerprint(rec) -> str:
    """§10.1 D2：优先 ttsTextHash（已物化字段 ✓），缺字段回退"归一化全文 sha1" """
    h = (rec.get("ttsTextHash") or "").strip()
    if h:
        return "h:" + h
    return "t:" + hashlib.sha1(norm(rec.get("answer") or "").encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 统计工具
def wilson(k: int, n: int, z: float = 1.96):
    """Wilson 95% CI（§10.2：样本 ≤10 会话时必须报）"""
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round(max(0.0, (c - r) / d), 4), round(min(1.0, (c + r) / d), 4)]


def rate(k: int, n: int):
    return None if n <= 0 else round(k / n, 4)


def _ci(k, n):
    return {"numerator": k, "denominator": n, "value": rate(k, n), "wilson95": wilson(k, n)}


# ---------------------------------------------------------------- 载入（多形状适配）
def _answer_of(d: dict):
    for k in ("answer", "answerFull", "answerExcerpt"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v, k
    for k in ("answer", "answerFull", "answerExcerpt"):        # 空串也算"取到了字段"
        if k in d:
            return "", k
    return "", ""


def _states(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if str(x).strip()]
    return [str(v)]


def _date_of(raw: str, source: str) -> str:
    """从 collectedAt/startedAt/文件名里抠出 YYYY-MM-DD（public-samples 的 startedAt 是 20261013-002219 这种戳）"""
    for probe in (str(raw or ""), Path(source).stem):
        m = re.search(r"(\d{4})-?(\d{2})-?(\d{2})", probe)
        if m and m.group(1).startswith("20") and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31:
            return "%s-%s-%s" % m.groups()
    return ""


def record_from_generic(j: dict, source: str, idx: int, meta: dict | None = None):
    """把一个任意形状的响应对象归一成审计记录；形状不认识就返回 None"""
    meta = meta or {}
    if not isinstance(j, dict):
        return None
    data, http = None, None
    if isinstance(j.get("response"), dict):                     # qa_run.py raw/*.json
        data = j["response"].get("data") or {}
        http = (j.get("transport") or {}).get("httpStatus", j["response"].get("code"))
    elif isinstance(j.get("data"), dict):
        data = j["data"]
        http = j.get("http", j.get("httpCode", j.get("status")))
    elif any(k in j for k in ("answer", "answerFull", "answerExcerpt", "ttsTextHash", "state")):
        data = j
    if data is None:
        return None
    answer, field = _answer_of(data)
    if not answer and isinstance(j.get("answer"), str) and j["answer"].strip():
        answer, field = j["answer"], "answer(root)"
    states = _states(data.get("state", j.get("state")))
    q = data.get("question") or j.get("question") or meta.get("question") or ""
    kind = data.get("kind") or j.get("kind") or j.get("category") or j.get("layer") or meta.get("kind") or ""
    date = (j.get("collectedAt") or data.get("generatedAt") or meta.get("startedAt") or "")
    # 会话身份：只有真正标识"一次对话"的字段才算会话；runId 是**批次**，不算（见 §10.3 硬前置）
    conv = data.get("conversationId") or data.get("sessionId") or j.get("conversationId") or j.get("sessionId")
    return {
        "id": str(j.get("id") or data.get("id") or ("%s#%d" % (Path(source).stem, idx))),
        "source": source,
        "session": (("conv:" + str(conv)) if conv else (meta.get("session") or Path(source).name)),
        "session_kind": "conversation" if conv else ("run-batch" if meta.get("session") else "file"),
        "session_explicit": bool(conv),
        "date": _date_of(j.get("collectedAt") or data.get("generatedAt") or meta.get("startedAt"), source),
        "kind": str(kind),
        "question": str(q)[:200],
        "answer": answer,
        "answer_field": field,
        "states": states,
        "http": http,
        "ttsTextHash": data.get("ttsTextHash"),
    }


def iter_json_object(j, src: str):
    """把一个已解析的 JSON 文档（dict/list）展开成记录"""
    if isinstance(j, dict) and isinstance(j.get("results"), list):        # eval-quality/safety
        meta = {"session": "run:" + str(j.get("runId") or Path(src).stem), "startedAt": j.get("startedAt"),
                "kind": j.get("paper") or ""}
        for i, r in enumerate(j["results"]):
            rec = record_from_generic(r, src, i, meta)
            if rec:
                rec["kind"] = rec["kind"] or str(meta.get("kind") or "")
                yield rec
        return
    if isinstance(j, dict) and isinstance(j.get("rows"), list):           # public-samples
        meta = {"session": "batch:" + Path(src).stem, "startedAt": j.get("startedAt")}
        for i, r in enumerate(j["rows"]):
            rec = record_from_generic(r, src, i, meta)
            if rec:
                rec["kind"] = rec["kind"] or str(r.get("category") or "")
                yield rec
        return
    if isinstance(j, list):
        for i, r in enumerate(j):
            rec = record_from_generic(r, src, i)
            if rec:
                yield rec
        return
    rec = record_from_generic(j, src, 0)
    if rec:
        yield rec


def iter_path(path: Path):
    """把一个文件（json/jsonl）展开成记录列表"""
    src = str(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".jsonl" or path.name.endswith(".jsonl"):
        for i, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except Exception:
                continue
            r = record_from_generic(j, src, i)
            if r:
                yield r
        return
    for r in iter_json_object(json.loads(text), src):
        yield r


def collect(inputs, use_stdin: bool):
    recs = []
    for spec in inputs:
        p = Path(spec)
        if p.is_dir():
            files = sorted([q for q in p.rglob("*") if q.is_file()
                            and q.suffix in (".json", ".jsonl")])
            for f in files:
                try:
                    recs.extend(iter_path(f))
                except Exception as e:
                    print("[WARN] 跳过 %s：%s" % (f, e), file=sys.stderr)
        elif p.is_file():
            recs.extend(iter_path(p))
        else:
            raise SystemExit("[FATAL] --input 不存在：%s" % spec)
    if use_stdin:
        text = sys.stdin.read()
        got = 0
        for i, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except Exception:
                continue
            r = record_from_generic(j, "<stdin>", i)
            if r:
                recs.append(r)
                got += 1
        if got == 0:                     # 不是 jsonl ⇒ 试一次"整份 JSON 文档"
            try:
                recs.extend(iter_json_object(json.loads(text), "<stdin>"))
            except Exception:
                pass
    return recs


# ---------------------------------------------------------------- 分母判定
def judge(rec):
    """返回 (core_ok, reason, simulated)。
    core_ok/ reason = 文档 §10.2 的排除项（4 种 state / 非 200 / 无正文）；
    simulated = 该条 state 含 `*-eval-simulated`（**默认不进分母**，见 2026-10-16 站主拍板）。"""
    if not (rec.get("answer") or "").strip():
        return False, "no-answer-text", False
    http = rec.get("http")
    if http is not None:
        try:
            if int(http) != 200:
                return False, "http!=200", False
        except Exception:
            pass
    states = rec.get("states") or []
    sim = any(s.endswith("-eval-simulated") for s in states)
    for s in states:
        if s in EXCLUDE_STATES:
            return False, "state:" + s, sim
    return True, "", sim


# ---------------------------------------------------------------- 指标
def metrics_for_session(turns, patterns, shell=None):
    fn = SHELL_FN if shell is None else shell
    n = len(turns)
    openers = [opener_key(t["answer"], fn) for t in turns]
    op = sum(1 for i in range(n)
             if openers[i] and any(openers[j] == openers[i] for j in range(max(0, i - 3), i)))
    fps = [fingerprint(t) for t in turns]
    seen, dup = set(), 0
    for f in fps:
        if f in seen:
            dup += 1
        else:
            seen.add(f)
    texts = [fn(t["answer"]) for t in turns]
    per_pat = {}
    for p in patterns:
        rx = re.compile(p["regex"])
        per_pat[p["id"]] = sum(1 for x in texts if rx.search(x))
    top1 = max(per_pat.values()) if per_pat and n else 0
    top1_id = max(per_pat, key=lambda k: per_pat[k]) if per_pat and n else None
    return {"n": n, "openerRepeat": op, "verbatimDup": dup, "perPattern": per_pat,
            "top1": top1, "top1Pattern": top1_id}


def combine(ms):
    """把**逐会话**的计数相加（micro 平均）——绝不能把跨会话的轮次串成一条序列"""
    n = sum(m["n"] for m in ms)
    per = {}
    for m in ms:
        for k, v in m["perPattern"].items():
            per[k] = per.get(k, 0) + v
    top1_id = max(per, key=lambda k: per[k]) if per and n else None
    return {"n": n,
            "openerRepeat": sum(m["openerRepeat"] for m in ms),
            "verbatimDup": sum(m["verbatimDup"] for m in ms),
            "top1": sum(m["top1"] for m in ms),
            "top1Pattern": top1_id,
            "perPattern": per}


def _rate3(m, n):
    return {
        "openerRepeatRate@3": rate(m["openerRepeat"], n),
        "verbatimRepeatRate": rate(m["verbatimDup"], n),
        "catchphraseTop1Share": rate(m["top1"], n),
    }


def audit(records, patterns, session_key="auto", stripper_spec=None, catchphrase_sha="", stripper_sha=""):
    """主口径（不含评测模拟）+ 对照口径（含评测模拟）**一次跑出两行**。
    2026-10-16 站主拍板：`state=*-eval-simulated` 不是真实流量 ⇒ 默认不进分母，但要给对照。"""
    rows = []
    for r in records:
        ok, why, sim = judge(r)
        r = dict(r)
        r["included"] = ok and not sim          # 主口径：排除评测模拟
        r["includedIncludingSimulated"] = ok     # 对照口径：含评测模拟
        r["exclude_reason"] = ("state:*-eval-simulated（评测模拟，默认不进分母）"
                              if (ok and sim) else why)
        r["simulated"] = sim
        rows.append(r)

    included = [r for r in rows if r["included"]]
    included_alt = [r for r in rows if r["includedIncludingSimulated"]]
    excl = {}
    for r in rows:
        if not r["included"]:
            excl[r["exclude_reason"]] = excl.get(r["exclude_reason"], 0) + 1

    # 会话归组
    def sess(r):
        if session_key == "global":
            return "__global__"
        if session_key == "question":
            return r["question"] or "__noq__"
        if session_key.startswith("field:"):
            return str(r.get(session_key.split(":", 1)[1]) or "__none__")
        if session_key == "file":
            return Path(r["source"]).name
        return r["session"] if r["session_explicit"] else Path(r["source"]).name

    def group(rs):
        g = {}
        for r in rs:
            g.setdefault(sess(r), []).append(r)
        return g

    sessions = group(included)
    sessions_alt = group(included_alt)

    detail = {}
    raw_ms, struct_ms = [], []
    for k, ts in sessions.items():
        m = metrics_for_session(ts, patterns)
        mraw = metrics_for_session(ts, patterns, strip_none)
        mst = metrics_for_session(ts, patterns, strip_structural)
        raw_ms.append(mraw)
        struct_ms.append(mst)
        m["openerRepeatRate@3_rawNoShell"] = rate(mraw["openerRepeat"], mraw["n"])
        m["openerRepeatRate@3_structural"] = rate(mst["openerRepeat"], mst["n"])
        m.update(_rate3(m, m["n"]))
        m["openerRepeatRate@3"] = rate(m["openerRepeat"], m["n"])
        m["verbatimRepeatRate"] = rate(m["verbatimDup"], m["n"])
        m["catchphraseTop1Share"] = rate(m["top1"], m["n"])
        detail[k] = m

    # 汇总 = 逐会话计数相加（micro），**不是**把所有轮次串成一条序列
    all_turns = [t for ts in sessions.values() for t in ts]
    M = combine(list(detail.values()))
    Mraw = combine(raw_ms)
    Mstruct = combine(struct_ms)
    n = M["n"]

    # 对照口径（含评测模拟）：同样逐会话相加
    alt_ms = [metrics_for_session(ts, patterns) for ts in sessions_alt.values()]
    alt_raw = [metrics_for_session(ts, patterns, strip_none) for ts in sessions_alt.values()]
    alt_struct = [metrics_for_session(ts, patterns, strip_structural) for ts in sessions_alt.values()]
    Malt = combine(alt_ms)
    n_alt = Malt["n"]

    # 分布：按天 / 按题型（先按 (会话, 桶) 分组再合并，保持会话隔离）
    def dist(keyfn):
        groups = {}
        for k, ts in sessions.items():
            by = {}
            for t in ts:
                by.setdefault(keyfn(t), []).append(t)
            for bk, bts in by.items():
                g = groups.setdefault(bk, ([], []))
                g[0].append(metrics_for_session(bts, patterns))
                g[1].append(metrics_for_session(bts, patterns, strip_none))
        out = {}
        for bk in sorted(groups):
            ms, raws = groups[bk]
            c = combine(ms)
            out[bk or "（空）"] = {
                "turns": c["n"], **_rate3(c, c["n"]),
                "openerRepeatRate@3_rawNoShell": rate(combine(raws)["openerRepeat"], c["n"]),
                "verbatimRepeatRate_rawNoShell": rate(combine(raws)["verbatimDup"], c["n"]),
            }
        return out

    hashes = sum(1 for t in all_turns if (t.get("ttsTextHash") or "").strip())
    conv = sum(1 for t in all_turns if t.get("session_kind") == "conversation")
    batch = sum(1 for t in all_turns if t.get("session_kind") == "run-batch")
    conv_sessions = {k for k, ts in sessions.items() if any(t.get("session_kind") == "conversation" for t in ts)}
    conv_max_turn = max([len(ts) for k, ts in sessions.items()
                         if any(t.get("session_kind") == "conversation" for t in ts)], default=0)

    # 基线可用性（照 §10.3 硬前置：复读是会话级现象，必须先有 3~5 条多轮题）
    reasons = []
    if conv == 0:
        reasons.append("数据里没有任何会话标识字段（conversationId/sessionId）⇒ 只有批次/文件级**伪会话**，"
                       "不是 §10 定义的「同一会话」")
    if len(conv_sessions) < 3:
        reasons.append("真会话数 %d < 3（§10.3 要求先补 3~5 条多轮题）" % len(conv_sessions))
    if conv_max_turn < 3:
        reasons.append("真会话最长仅 %d 轮（无多轮会话）" % conv_max_turn)
    if n < 30:
        reasons.append("有效轮次 %d < 30" % n)
    eligible = not reasons

    return {
        "tool": TOOL, "version": VERSION, "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "spec": [SPEC_REF, SPEC_REF2],
        "sessionKeyMode": session_key,
        "excludeStates": sorted(EXCLUDE_STATES),
        "simPolicy": {
            "default": "exclude",
            "note": "2026-10-16 站主拍板：state=*-eval-simulated 不是真实流量 ⇒ 默认不进分母；"
                    "报告同时给「不含 / 含评测模拟」两行，--include-simulated 可显式纳入",
            "simulatedTurns": sum(1 for r in rows if r.get("simulated")),
            "includedExcludingSimulated": len(included),
            "includedIncludingSimulated": len(included_alt),
        },
        "catchphraseSpec": patterns,
        "catchphraseSpecSha256": catchphrase_sha,
        "stripperSpec": (stripper_spec or {}),
        "stripperSpecSha256": stripper_sha,
        "counts": {
            "recordsRead": len(rows), "included": len(included), "excluded": len(rows) - len(included),
            "includedIncludingSimulated": len(included_alt),
            "excludedByReason": excl,
            "sessions": len(detail), "maxTurnsPerSession": max(m["n"] for m in detail.values()) if detail else 0,
            "turnsWithTtsTextHash": hashes,
            "fingerprintFallbackTurns": n - hashes,
            "turnsWithConversationId": conv,
            "turnsInRunBatchPseudoSession": batch,
            "conversationSessions": len(conv_sessions),
            "maxTurnsPerConversation": conv_max_turn,
        },
        "metrics": {
            "openerRepeatRate@3": _ci(M["openerRepeat"], n),
            "verbatimRepeatRate": _ci(M["verbatimDup"], n),
            "catchphraseTop1Share": {**_ci(M["top1"], n), "top1Pattern": M["top1Pattern"]},
            "openerRepeatRate@3_rawNoShell": _ci(Mraw["openerRepeat"], Mraw["n"]),
            "openerRepeatRate@3_structural": _ci(Mstruct["openerRepeat"], Mstruct["n"]),
            "catchphrasePerPattern": M["perPattern"],
        },
        "metricsIncludingSimulated": {
            "denominator": n_alt,
            "openerRepeatRate@3": _ci(Malt["openerRepeat"], n_alt),
            "verbatimRepeatRate": _ci(Malt["verbatimDup"], n_alt),
            "catchphraseTop1Share": _ci(Malt["top1"], n_alt),
            "openerRepeatRate@3_rawNoShell": _ci(combine(alt_raw)["openerRepeat"], n_alt),
            "openerRepeatRate@3_structural": _ci(combine(alt_struct)["openerRepeat"], n_alt),
        },
        "shellMode": SHELL_MODE,
        "targets": {"openerRepeatRate@3": "<=0.25 且相对基线降>=50%",
                    "verbatimRepeatRate": "<=0.10", "catchphraseTop1Share": "<=0.15"},
        "baseline": {"eligible": eligible,
                     "reason": "可用作基线" if eligible else "样本太少/无真会话，不可作基线：" + "；".join(reasons)},
        "byDay": dist(lambda t: t["date"]),
        "byKind": dist(lambda t: t["kind"]),
        "perSession": detail,
        "rows": [{"id": r["id"], "session": sess(r) if r["included"] else "-", "source": Path(r["source"]).name,
                  "date": r["date"], "kind": r["kind"], "states": r["states"], "http": r["http"],
                  "included": r["included"], "excludeReason": r["exclude_reason"],
                  "answerChars": len(r["answer"]), "hasTtsTextHash": bool((r.get("ttsTextHash") or "").strip()),
                  "opener": opener_key(r["answer"]) if r["included"] else ""} for r in rows],
    }


# ---------------------------------------------------------------- 报告
def md_report(res, sources):
    m, c = res["metrics"], res["counts"]
    L = []
    A = L.append
    A("# 复读率审计报告（%s）" % res["generatedAt"])
    A("")
    A("- 工具：`%s` v%s（只读；不写被审计目录、不发请求、不消耗额度）" % (res["tool"], res["version"]))
    A("- 口径出处：%s ／ %s" % (SPEC_REF, SPEC_REF2))
    A("- 归一化：复用 `_t14\\verify_t14_contract.py` 的 `norm()` + 前 %d 字符（同一实现，无第二套）" % OPENER_CHARS)
    A("- 剥壳（去固定抬头 / 引用尾）：读**版本化冻结**模板串 `%s`（每条含 匹配串 + 出处 + 加入日期 + 理由，"
      "只追加不修改）" % (res.get("stripperSpec") or {}).get("version", "?"))
    A("  - 模板档：`%s` ｜ sha256 `%s` ｜ 条数 head=%d / tail=%d"
      % (Path((res.get("stripperSpec") or {}).get("file", "")).name,
         (res.get("stripperSpec") or {}).get("sha256", "")[:16],
         len((res.get("stripperSpec") or {}).get("head", [])),
         len((res.get("stripperSpec") or {}).get("tail", []))))
    A("- 口头禅词表：**事先冻结**的 ≤3 条正则（来源见 `catchphraseSpec`；sha256 `%s`），先定词表再跑"
      % (res.get("catchphraseSpecSha256") or "")[:16])
    A("- 分母策略：`%s`（%s）" % (res["simPolicy"]["default"], res["simPolicy"]["note"]))
    A("")
    A("## 1. 分母口径（照 §10.2 排除项 + 评测模拟默认不进分母）")
    A("")
    A("| 项 | 条数 |")
    A("|---|---|")
    A("| 读入记录 | %d |" % c["recordsRead"])
    A("| **计入分母（主口径：不含评测模拟）** | **%d** |" % c["included"])
    A("| 计入分母（对照口径：含评测模拟） | %d |" % c["includedIncludingSimulated"])
    A("| 排除合计 | %d |" % c["excluded"])
    for k, v in sorted(c["excludedByReason"].items()):
        A("| └ 排除：`%s` | %d |" % (k, v))
    A("| 会话数（当前分组方式 `%s`） | %d |" % (res["sessionKeyMode"], c["sessions"]))
    A("| └ 其中**真会话**（带 conversationId/sessionId） | %d 个 / %d 轮 |"
      % (c["conversationSessions"], c["turnsWithConversationId"]))
    A("| └ 批次级伪会话（runId / 文件，**不是** §10 定义的会话） | %d 轮 |" % c["turnsInRunBatchPseudoSession"])
    A("| 最长会话轮次 | %d（真会话最长 %d 轮） |"
      % (c["maxTurnsPerSession"], c["maxTurnsPerConversation"]))
    A("| 带 `ttsTextHash` 的轮次 | %d（回退归一化全文 sha1：%d） |"
      % (c["turnsWithTtsTextHash"], c["fingerprintFallbackTurns"]))
    A("")
    A("## 2. 三条指标（**两行口径都给**）")
    A("")
    primary_alt = res.get("simPolicy", {}).get("primary") == "including"
    tag_ex, tag_in = ("对照（不含评测模拟）", "**主**（含评测模拟）") if primary_alt \
        else ("**主**（不含评测模拟）", "对照（**含**评测模拟）")
    A("| 口径 | 指标 | 值 | 目标 | 计数 | Wilson 95% CI |")
    A("|---|---|---|---|---|---|")
    def row(tag, key, label):
        d = m[key]
        A("| %s | %s | %s | %s | %s/%s | %s |" % (
            tag, label, "—" if d["value"] is None else "**%.4f**" % d["value"], res["targets"][key],
            d["numerator"], d["denominator"], d["wilson95"] if d["wilson95"] else "—"))
    sources_ = (m, res["metricsIncludingSimulated"]) if not primary_alt else (res["metricsIncludingSimulated"], m)
    p_m, c_m = sources_
    def prow(tag, key, label, src=None):
        d = (src or c_m)[key]
        A("| %s | %s | %s | %s | %s/%s | %s |" % (
            tag, label, "—" if d["value"] is None else "**%.4f**" % d["value"], res["targets"][key],
            d["numerator"], d["denominator"], d["wilson95"] if d["wilson95"] else "—"))
    prow(tag_ex, "openerRepeatRate@3", "`openerRepeatRate@3` 开场白复读率", p_m)
    prow(tag_ex, "verbatimRepeatRate", "`verbatimRepeatRate` 逐字复读率", p_m)
    prow(tag_ex, "catchphraseTop1Share", "`catchphraseTop1Share` 口头禅 top1 占比", p_m)
    for key, tag in (("openerRepeatRate@3_structural", "D1s"), ("openerRepeatRate@3_rawNoShell", "D1r")):
        d = p_m[key]
        A("| %s | %s | %s | 仅对照 | %s/%s | %s |" % (
            tag_ex, tag, "—" if d["value"] is None else "%.4f" % d["value"], d["numerator"],
            d["denominator"], d["wilson95"] if d["wilson95"] else "—"))
    prow(tag_in, "openerRepeatRate@3", "`openerRepeatRate@3` 开场白复读率", c_m)
    prow(tag_in, "verbatimRepeatRate", "`verbatimRepeatRate` 逐字复读率", c_m)
    prow(tag_in, "catchphraseTop1Share", "`catchphraseTop1Share` 口头禅 top1 占比", c_m)
    A("")
    A("> 主口径 = **字面量剥壳**（只剥后端源码里写死的抬头 / 引用尾，每条带 `文件:行号`）；"
      "`D1s` 结构口径与 `D1r` 不剥壳都列出来当上下界，**不藏任何选择**。")
    A("> 若 D1 高而 D1s 低，说明高出来的是**模板抬头**而不是模型复读；反之才是真复读。")
    A("")
    A("口头禅逐词命中（分母同上）：" + "；".join("`%s`=%d" % (k, v) for k, v in m["catchphrasePerPattern"].items()))
    A("")
    A("## 3. 基线可用性")
    A("")
    A("- **%s**" % ("可用作基线 ✓" if res["baseline"]["eligible"] else "不可作基线 ✗ " + res["baseline"]["reason"]))
    A("")
    if res["byDay"]:
        A("## 4. 按天分桶（D1 / D2 / D3 / D1r）")
        A("")
        A("| 日期 | 轮次 | D1 | D2 | D3 | D1r(不剥壳) |")
        A("|---|---|---|---|---|---|")
        for k, v in res["byDay"].items():
            A("| %s | %d | %s | %s | %s | %s |" % (
                k, v["turns"], v["openerRepeatRate@3"], v["verbatimRepeatRate"],
                v["catchphraseTop1Share"], v["openerRepeatRate@3_rawNoShell"]))
        A("")
    if res["byKind"]:
        A("## 5. 按题型/类别分桶（D1 / D2 / D3）")
        A("")
        A("| 题型 | 轮次 | D1 | D2 | D3 |")
        A("|---|---|---|---|---|")
        for k, v in res["byKind"].items():
            A("| `%s` | %d | %s | %s | %s |" % (
                k, v["turns"], v["openerRepeatRate@3"], v["verbatimRepeatRate"], v["catchphraseTop1Share"]))
        A("")
    A("## 6. 逐会话明细")
    A("")
    A("| 会话（=runId / 文件） | 轮次 | D1 | D2 | D3 | D1r(不剥壳) |")
    A("|---|---|---|---|---|---|")
    for k, v in sorted(res["perSession"].items()):
        A("| `%s` | %d | %s | %s | %s | %s |" % (
            k, v["n"], v["openerRepeatRate@3"], v["verbatimRepeatRate"],
            v["catchphraseTop1Share"], v["openerRepeatRate@3_rawNoShell"]))
    A("")
    A("## 7. 数据来源")
    A("")
    for s in sources:
        A("- %s" % s)
    A("")
    A("## 8. 局限与 `[待核对]`")
    A("")
    A("- **真会话级指标目前测不出来**：数据里没有会话标识、也没有多轮题（§10.3 硬前置）⇒ "
      "当前分组是「同一批 / 同一 runId」的**伪会话**，只作量级参考，**不能当验收数字** ✗。")
    A("- `[待核对]` §10.1 说剥壳口径「与 `scripts/eval/qa_score.py` 一致」，但**该文件里没有剥壳实现**"
      "（296 行全文核对过）；本脚本用「后端源码固定模板串」代替，需站主确认后冻结。")
    A("- `[待核对]` 归一化字符类逐字复用 `verify_t14_contract.py`，若 §10 归一化要再加字符（如 `_`、`|`），两处要同改。")
    A("- `[待核对]` 口头禅词表直接用 §10.1 D3 的三条示例正则（上游日文语料），在本项目中文语料上命中率极低 ⇒ "
      "该指标在站主给定本语料词表前**无判别力**。")
    A("- 未做：未改任何后端/前端/配置；未发任何请求；未消耗任何额度。")
    A("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- 自检
def _rec(i, ans, state=("model",), http=200, h=None, sess="S1", date="2026-10-16", kind="k", q=""):
    return {"id": "c%d" % i, "source": sess + ".json", "session": sess, "session_explicit": False,
            "date": date, "kind": kind, "question": q or ("q%d" % i), "answer": ans,
            "answer_field": "answer", "states": list(state), "http": http, "ttsTextHash": h}


def selftest():
    pats = json.loads((HERE / "catchphrases.json").read_text(encoding="utf-8"))["patterns"]
    fails = []

    def check(name, got, want):
        ok = got == want
        print("%-5s %-52s got=%s want=%s" % ("[PASS]" if ok else "[FAIL]", name, got, want))
        if not ok:
            fails.append(name)

    # ① 上游形态：17 轮里同一句出现 8 次（外部基线 8/17=0.47）
    same = "は？　助手って呼ぶな…"
    kana = "アイウエオカキクケコサシスセソタチツテト"
    turns = [_rec(i, same) for i in range(8)]
    for i in range(8):
        turns.append(_rec(8 + i, kana[i] + "の説明文です"))    # 首 8 字符各不相同
    turns.append(_rec(16, "結論として対応が必要です"))
    m = metrics_for_session(turns, pats)
    check("① 开场白复读率@3 = 7/17", rate(m["openerRepeat"], m["n"]), round(7 / 17, 4))
    check("① 逐字复读率 = 7/17", rate(m["verbatimDup"], m["n"]), round(7 / 17, 4))
    check("① 口头禅 top1 占比 = 8/17（上游 0.47）", rate(m["top1"], m["n"]), round(8 / 17, 4))

    # ② 归一化：markdown/标点/空白差异不算不同（且不是"原样取前 8 字符"）
    check("② 归一化（相等 且 ≠原样）",
          (opener_key("**开头一样**，你好。"), opener_key("**开头一样**，你好。") == "**开头一样**，你好。"[:8]),
          (opener_key("开头一样你好"), False))

    # ③ 会话隔离：同一开头在两个会话各 1 次 ⇒ 都不算复读
    r = audit([_rec(0, "同样开头甲乙", sess="A"), _rec(1, "同样开头甲乙", sess="B"),
               _rec(2, "另外的开头丙丁", sess="A"), _rec(3, "另外的开头丙丁", sess="B")],
              pats, session_key="file")
    check("③ 会话隔离（跨会话不算复读）", r["metrics"]["openerRepeatRate@3"]["value"], 0.0)

    # ④ 窗口 @3：相隔 4 轮不算
    seq = [_rec(0, "甲开头一号内容"), _rec(1, "乙开头二号内容"), _rec(2, "丙开头三号内容"),
           _rec(3, "丁开头四号内容"), _rec(4, "甲开头五号内容")]
    m4 = metrics_for_session(seq, pats)
    check("④ 窗口@3（相隔 4 轮不算）", m4["openerRepeat"], 0)

    # ⑤ 排除项：四种 state + 非 200 + 空正文全部不进分母（分母与逐项计数一起断言）
    recs = [_rec(0, "正常回答一二三四"), _rec(1, "模型失败回答", state=["model-failed"]),
            _rec(2, "检索失败回答", state=["retrieval-failed"]), _rec(3, "无检索回答", state=["no-retrieval"]),
            _rec(4, "依据不足回答", state=["input-insufficient"]), _rec(5, "非200回答", http=500),
            _rec(6, "   ")]
    r5 = audit(recs, pats, session_key="file")
    check("⑤ 分母与排除原因计数",
          (r5["counts"]["included"], r5["counts"]["excludedByReason"]),
          (1, {"state:model-failed": 1, "state:retrieval-failed": 1, "state:no-retrieval": 1,
               "state:input-insufficient": 1, "http!=200": 1, "no-answer-text": 1}))

    # ⑥ 剥壳：固定抬头不参与比对（未剥壳时两条会被判成同一开头）
    a = "## 多智能体协同结果\n\n> 调度员判定本次任务为【取证分析员】，由对应专职智能体执行。\n\n甲方案说明"
    b = "## 多智能体协同结果\n\n> 调度员判定本次任务为【取证分析员】，由对应专职智能体执行。\n\n乙方案说明"
    m6 = metrics_for_session([_rec(0, a), _rec(1, b)], pats)
    m6raw = metrics_for_session([_rec(0, a), _rec(1, b)], pats, strip_none)
    check("⑥ 剥壳后不同开头", m6["openerRepeat"], 0)
    check("⑥ 未剥壳会误判成同开头（对照）", m6raw["openerRepeat"], 1)

    # ⑦ 引用尾剥掉
    c = "正文结论甲\n\n---\n\n### 命中的公开知识库片段（未经 AI 加工，供你自行判断）\n\n> 公开演示只基于公开知识库回答：…\n\n1. **X**"
    check("⑦ 引用尾被剥掉", strip_shell(c), "正文结论甲")

    # ⑧ ttsTextHash 优先于文本
    check("⑧ 指纹优先用 ttsTextHash",
          fingerprint(_rec(0, "文本甲", h="H1")) != fingerprint(_rec(1, "文本甲")), True)
    check("⑧ 同 hash 视为逐字相同",
          metrics_for_session([_rec(0, "甲", h="H1"), _rec(1, "乙", h="H1")], pats)["verbatimDup"], 1)

    # ⑨ Wilson CI 合理性
    ci = wilson(8, 17)
    check("⑨ Wilson 95% CI 含点估计", ci[0] <= 8 / 17 <= ci[1], True)

    # ⑩ 基线门槛：无会话字段 ⇒ 不可作基线
    r10 = audit(turns, pats, session_key="file")
    check("⑩ 无真会话 ⇒ 不可作基线", r10["baseline"]["eligible"], False)

    # ⑪ 评测模拟默认不进分母，且报告给出「含」的对照（2026-10-16 站拍板）
    sim = [_rec(0, "评测模拟回答甲", state=["rule-based-eval-simulated"], sess="S1"),
           _rec(1, "评测模拟回答甲", state=["rule-based-eval-simulated"], sess="S1"),
           _rec(2, "真实模型回答乙", state=["model"], sess="S1")]
    r11 = audit(sim, pats, session_key="file")
    check("⑪ 评测模拟默认排除（含/不含两行）",
          (r11["counts"]["included"], r11["counts"]["includedIncludingSimulated"],
           r11["metricsIncludingSimulated"]["verbatimRepeatRate"]["value"]),
          (1, 3, 0.3333))   # 含口径 3 轮里那 2 条同文本 ⇒ (3-2)/3

    # ⑫ strippers.v1.json 是合法冻结清单（版本 + 每条四要素齐）
    spec, head, tail = load_strippers(HERE / DEFAULT_STRIPPER)
    ok12 = bool(spec.get("version")) and len(head) > 0 and all(
        e.get("pattern") and e.get("source") and e.get("added") and e.get("reason") for e in spec.get("head", []))
    check("⑫ strippers 清单合法（版本+四要素）", ok12, True)

    print("")
    if fails:
        print("SELFTEST FAIL ✗ 未通过 %d 项：%s" % (len(fails), "; ".join(fails)))
        return 1
    print("SELFTEST PASS ✓ 12 组 / 16 断言全部通过")
    return 0


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description="复读率审计（只读；口径见 docs/后端问答能力升级方案 §10）")
    ap.add_argument("--input", action="append", default=[], help="jsonl/json/目录（可重复）")
    ap.add_argument("--stdin", action="store_true", help="从 stdin 读 jsonl")
    ap.add_argument("--session-key", default="auto", help="auto|file|question|global|field:NAME")
    ap.add_argument("--json", default="", help="report.json 落盘路径")
    ap.add_argument("--md", default="", help="人读 markdown 落盘路径")
    ap.add_argument("--catchphrase-file", default=str(HERE / "catchphrases.json"),
                    help="事先冻结的 ≤3 条口头禅正则（JSON）")
    ap.add_argument("--stripper-file", default=str(HERE / DEFAULT_STRIPPER),
                    help="版本化冻结的剥壳模板清单（默认与脚本同目录的 strippers.v1.json）")
    ap.add_argument("--shell-file", default="", help="覆盖剥壳模板（JSON：head_regex/tail_regex）")
    ap.add_argument("--shell-mode", default="literal", choices=("literal", "structural", "none"),
                    help="literal=按 strippers 清单剥（默认，主口径）；structural=连 markdown 标题/引用块一起剥；none=不剥")
    ap.add_argument("--include-simulated", action="store_true",
                    help="把 state=*-eval-simulated（评测模拟）**显式纳入**主口径（默认排除；报告两行都给）")
    ap.add_argument("--exclude-simulated", action="store_true",
                    help="（已废弃，等价于默认行为）排除 state=*-eval-simulated")
    ap.add_argument("--data-source-note", action="append", default=[],
                    help="写进报告的「数据来源」一行（可重复）")
    ap.add_argument("paths", nargs="*", help="位置参数：文件/目录，或 `-` 表示读 stdin jsonl")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    pats_path = Path(args.catchphrase_file)
    pats = json.loads(pats_path.read_text(encoding="utf-8"))["patterns"]
    global strip_shell, SHELL_FN, SHELL_MODE
    SHELL_MODE = args.shell_mode
    spec, sh_json, st_json = load_strippers(Path(args.stripper_file))
    if args.shell_mode == "literal":
        # 主口径：按 strippers.vN.json 清单剥（缺失则回退内置，并在报告里标 builtin-fallback）
        SHELL_FN = lambda t, head=None, tail=None: _strip_with(t, sh_json, st_json)   # noqa: E731
    if args.shell_file:
        sf = json.loads(Path(args.shell_file).read_text(encoding="utf-8"))
        sh = [(p, "shell-file") for p in sf.get("head_regex", [])]
        st = [(p, "shell-file") for p in sf.get("tail_regex", [])]
        SHELL_FN = lambda t, head=None, tail=None: _strip_with(t, sh, st)   # noqa: E731
        SHELL_MODE = "file:%s" % args.shell_file
    elif args.shell_mode == "none":
        SHELL_FN = strip_none
    elif args.shell_mode == "structural":
        SHELL_FN = strip_structural

    use_stdin = bool(args.stdin)
    for p in args.paths or []:
        if p == "-":
            use_stdin = True
            continue
        args.input.append(p)
    if not args.input and not use_stdin and not sys.stdin.isatty():
        use_stdin = True
    if not args.input and not use_stdin:
        print("[FATAL] 要么 --input <文件/目录>，要么用管道喂 stdin jsonl", file=sys.stderr)
        return 2
    recs = collect(args.input, use_stdin)
    if not recs:
        print("[FATAL] 一条记录都没读到（输入路径对吗？）", file=sys.stderr)
        return 4
    res = audit(recs, pats, session_key=args.session_key, stripper_spec=spec,
                catchphrase_sha=_sha256_file(pats_path), stripper_sha=spec.get("sha256", ""))
    if res["counts"]["included"] == 0:
        print("[FATAL] 有效记录 0 条 ⇒ 不产出指标（分母为空，不许编数字 ✗）", file=sys.stderr)
        print("[HINT] 排除明细：%s" % res["counts"]["excludedByReason"], file=sys.stderr)
        return 4
    if args.include_simulated:
        res["simPolicy"]["primary"] = "including"
        res["simPolicy"]["note"] += "；本次**显式纳入**：主口径 = 含评测模拟（两行仍都给）"
        print("[WARN] --include-simulated：主口径改为「含评测模拟」——评测模拟不是真实流量，慎用 ✗",
              file=sys.stderr)

    srv = list(args.data_source_note)
    for spec in args.input:
        p = Path(spec)
        if p.is_dir():
            fs = sorted(q for q in p.rglob("*") if q.is_file() and q.suffix in (".json", ".jsonl"))
            srv.append("`%s`（%d 个文件）" % (p, len(fs)))
        else:
            srv.append("`%s`" % p)
    if use_stdin:
        srv.append("stdin（jsonl 流）")
    srv.append("会话分组方式：`%s`" % res["sessionKeyMode"])

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(md_report(res, srv), encoding="utf-8")

    m = res["metrics"]
    print("=== REPEAT-AUDIT === 主口径=不含评测模拟  included=%d/%d sessions=%d"
          % (res["counts"]["included"], res["counts"]["recordsRead"], res["counts"]["sessions"]))
    for k in ("openerRepeatRate@3", "verbatimRepeatRate", "catchphraseTop1Share"):
        d = m[k]
        print("  %-24s %s  (%d/%d, CI %s)"
              % (k, "—" if d["value"] is None else "%.4f" % d["value"],
                 d["numerator"], d["denominator"], d["wilson95"]))
    print("  %-24s %s  (结构口径下界)"
          % ("openerRepeatRate@3s", m["openerRepeatRate@3_structural"]["value"]))
    print("  %-24s %s  (不剥壳上界)"
          % ("openerRepeatRate@3r", m["openerRepeatRate@3_rawNoShell"]["value"]))
    a = res["metricsIncludingSimulated"]
    print("  对照·含评测模拟  included=%d" % a["denominator"])
    for k in ("openerRepeatRate@3", "verbatimRepeatRate", "catchphraseTop1Share"):
        d = a[k]
        print("  %-24s %s  (%d/%d, CI %s)"
              % (k + "(含)", "—" if d["value"] is None else "%.4f" % d["value"],
                 d["numerator"], d["denominator"], d["wilson95"]))
    print("  shell/stripper: %s sha=%s" % ((res.get("stripperSpec") or {}).get("version"),
                                           (res.get("stripperSpec") or {}).get("sha256", "")[:16]))
    print("  baseline: %s" % ("可用 ✓" if res["baseline"]["eligible"] else "不可作基线 ✗ " + res["baseline"]["reason"]))
    if args.json:
        print("json → %s" % args.json)
    if args.md:
        print("md   → %s" % args.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
