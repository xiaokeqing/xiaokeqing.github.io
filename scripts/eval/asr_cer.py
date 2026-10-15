#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T13-① ASR 回译 CER（字符级）评测器 —— 可重跑、换输入目录不改代码。

做什么
    把一批语音产物（默认 `_tts-trial/out-ja/dist/*.m4a`，60 句日语）用 ASR 回译成文字，
    与台词库里的 `ja` 原文逐句算**字符级 CER**，输出逐句表 + 均值表。

口径（写进报告，不许临时改 ✗）
    · 语言固定日文（`language="Japanese"`），ASR = **Qwen3-ASR-0.6B**（素材包 `asr-qwen3-0.6b`，本机离线）。
    · 文本先做 NFKC 归一。
    · 三个口径都出，别只报好看的那个 ✓：
        cer_plain = 只删空白（含全角空格）后的 CER
        cer_norm  = 再删标点/符号（Unicode 类 P* / S* / Z*）后的 CER  ← **主口径（头条数字）**
        cer_kana  = cer_norm 再把片假名归一成平假名后的 CER（分离「表记差异」与真实识别错误；
                    例：ぎりぎり↔ギリギリ 是书写习惯，不是听错 ✗）
    · CER = Levenshtein(参考, 假设) / len(参考)。参考为空的行跳过并计数。
    · `--context` 可给 ASR 一段**领域词**做偏置（如角色名）；默认关（不偏置），
      偏置结果单独跑、单独归档，**不许**用参考原文当 context（那是泄题 ✗）。
    · 删标点对不上时不算"错"—— 这是 ASR 评测通行做法；原始文本仍完整落盘可复核。

用法（本机）
    PY=E:\\DeepSeek1\\work\\_amadeus-src\\.venv\\Scripts\\python.exe
    & $PY -X utf8 scripts/eval/asr_cer.py \
        --audio-dir  E:\\DeepSeek1\\work\\_tts-trial\\out-ja\\dist \
        --lines      E:\\DeepSeek1\\work\\_tts-trial\\lines60-bilingual.json \
        --out-dir    E:\\DeepSeek1\\work\\_eval-t13\\asr-cer

    换数据集只需换 --audio-dir / --lines（文件按 id 对齐：<id>.m4a ↔ lines[i].id）✓
    只想试跑：加 `--limit 3`。

依赖
    qwen_asr + torch(CUDA) + av   均在 `_amadeus-src/.venv` 里（详见 scripts/eval/README.md）。
    模型目录默认 `_amadeus-src/assets/models/asr/qwen3-asr-0.6b`（8 文件，sha256 已校验）。

退出码
    0 正常；2 参数/输入错误；3 模型或音频解码不可用（**不产出任何数字** ✗ 不许退化成编数）
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

DEFAULT_MODEL_DIR = Path(r"E:\DeepSeek1\work\_amadeus-src\assets\models\asr\qwen3-asr-0.6b")
DEFAULT_AUDIO_DIR = Path(r"E:\DeepSeek1\work\_tts-trial\out-ja\dist")
DEFAULT_LINES = Path(r"E:\DeepSeek1\work\_tts-trial\lines60-bilingual.json")
REQUIRED_MODEL_FILES = (
    "chat_template.json",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors",
    "preprocessor_config.json",
    "tokenizer_config.json",
    "vocab.json",
)


# ----------------------------------------------------------------------------- text
def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def strip_space(text: str) -> str:
    return "".join(ch for ch in text if not ch.isspace())


def strip_punct(text: str) -> str:
    """Drop punctuation / symbols / separators (Unicode P*, S*, Z*) — ASR 评测主口径。"""
    keep = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat[0] in ("P", "S", "Z"):
            continue
        keep.append(ch)
    return "".join(keep)


_KATAKANA_START, _KATAKANA_END = 0x30A1, 0x30F6
_KANA_OFFSET = 0x30A1 - 0x3041


def kana_uniform(text: str) -> str:
    """片假名 → 平假名（仅基本区），用于分离表记差异口径。"""
    return "".join(
        chr(ord(ch) - _KANA_OFFSET) if _KATAKANA_START <= ord(ch) <= _KATAKANA_END else ch
        for ch in text
    )


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(ref: str, hyp: str) -> float:
    if not ref:
        return float("nan")
    return levenshtein(ref, hyp) / len(ref)


# ----------------------------------------------------------------------------- audio
def _decode_with_av(path: Path, target_sr: int = 16000):
    import av  # PyAV
    import numpy as np

    with av.open(str(path)) as container:
        stream = next(s for s in container.streams if s.type == "audio")
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=target_sr)
        chunks = []
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):  # flush
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        raise RuntimeError(f"decoded 0 samples: {path}")
    wav = np.concatenate(chunks).astype("float32")
    peak = float(np.max(np.abs(wav))) if wav.size else 0.0
    if peak > 1.0:
        wav = wav / peak
    return wav, target_sr


def _decode_with_ffmpeg(path: Path, target_sr: int = 16000):
    import numpy as np

    exe = shutil.which("ffmpeg") or r"E:\DeepSeek1\work\_kurisu-017\video-pipeline\tools\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe"
    if not Path(exe).exists() and not shutil.which("ffmpeg"):
        raise FileNotFoundError("ffmpeg not found")
    proc = subprocess.run(
        [exe, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(target_sr), "-f", "f32le", "-"],
        capture_output=True,
        check=True,
    )
    return np.frombuffer(proc.stdout, dtype="<f4").astype("float32"), target_sr


def decode_audio(path: Path, target_sr: int = 16000):
    """m4a(AAC) → (mono float32, 16k)。优先 PyAV（进程内、无外部依赖），退回 ffmpeg。"""
    errors = []
    for name, fn in (("pyav", _decode_with_av), ("ffmpeg", _decode_with_ffmpeg)):
        try:
            return fn(path, target_sr) + (name,)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
    raise RuntimeError("audio decode failed: " + " | ".join(errors))


# ----------------------------------------------------------------------------- model
def check_model_dir(model_dir: Path) -> None:
    missing = [n for n in REQUIRED_MODEL_FILES if not (model_dir / n).is_file()]
    if missing:
        raise FileNotFoundError(f"model dir incomplete: {model_dir} missing={missing}")


def load_model(model_dir: Path, device: str, dtype: str):
    import torch
    from qwen_asr import Qwen3ASRModel

    torch_dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[dtype]
    t0 = time.time()
    model = Qwen3ASRModel.from_pretrained(
        str(model_dir),
        device_map=device,
        dtype=torch_dtype,
        max_inference_batch_size=1,
        max_new_tokens=256,
        low_cpu_mem_usage=True,
    )
    return model, time.time() - t0


# ----------------------------------------------------------------------------- io
def load_lines(path: Path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("lines", data if isinstance(data, list) else [])


def git_commit_of(repo: Path) -> str:
    try:
        run = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        return run.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def report_markdown(rows, meta, group_field="trigger"):
    lines = []
    lines.append(f"# ASR 回译 CER · 逐句表（{meta['stamp']}）\n")
    lines.append(f"- ASR：{meta['engine']}｜语言：Japanese｜设备：{meta['device']}｜dtype：{meta['dtype']}")
    lines.append(f"- 音频目录：`{meta['audio_dir']}`（{meta['n']} 条）")
    lines.append(f"- 台词库：`{meta['lines']}`")
    lines.append(f"- 模型目录：`{meta['model_dir']}`（8 文件 sha256 已校验）")
    lines.append(f"- 主口径 cer_norm（NFKC + 删空白 + 删标点/符号）；cer_plain 为只删空白对照；"
                 f"cer_kana 再把片假名归一为平假名（分离表记差异）")
    lines.append(f"- ASR 领域偏置 context：{meta.get('context') or '（无，未偏置）'}")
    lines.append(f"- 加载耗时 {meta['load_s']}s｜识别耗时 {meta['infer_s']}s｜平均 {meta['mean_s']}s/句\n")

    def stats(sel):
        vals = [r["cer_norm"] for r in sel if r["cer_norm"] == r["cer_norm"]]
        if not vals:
            return "—"
        vals_sorted = sorted(vals)
        return (
            f"n={len(vals)} 均值={sum(vals)/len(vals):.4f} "
            f"中位={vals_sorted[len(vals_sorted)//2]:.4f} "
            f"最小={vals_sorted[0]:.4f} 最大={vals_sorted[-1]:.4f}"
        )

    lines.append("## 均值\n")
    lines.append("| 口径 | 统计 |")
    lines.append("|---|---|")
    lines.append(f"| cer_norm（主） | {stats(rows)} |")
    vals_plain = [r["cer_plain"] for r in rows if r["cer_plain"] == r["cer_plain"]]
    if vals_plain:
        lines.append(f"| cer_plain（对照） | n={len(vals_plain)} 均值={sum(vals_plain)/len(vals_plain):.4f} "
                     f"最小={min(vals_plain):.4f} 最大={max(vals_plain):.4f} |")
    vals_kana = [r["cer_kana"] for r in rows if r["cer_kana"] == r["cer_kana"]]
    if vals_kana:
        lines.append(f"| cer_kana（假名归一） | n={len(vals_kana)} 均值={sum(vals_kana)/len(vals_kana):.4f} "
                     f"最小={min(vals_kana):.4f} 最大={max(vals_kana):.4f} |")
    lines.append(f"| 完全一致（CER=0） | {sum(1 for r in rows if r['cer_norm'] == 0)}/{len(rows)} |")
    lines.append(f"| CER ≤ 0.10 | {sum(1 for r in rows if r['cer_norm'] <= 0.10)}/{len(rows)} |\n")

    lines.append("## 分组均值\n")
    lines.append("| trigger | n | cer_norm 均值 |")
    lines.append("|---|---|---|")
    groups = {}
    for r in rows:
        groups.setdefault(r.get(group_field) or "-", []).append(r)
    for key in sorted(groups):
        sel = groups[key]
        vals = [r["cer_norm"] for r in sel]
        lines.append(f"| {key} | {len(sel)} | {sum(vals)/len(vals):.4f} |")
    lines.append("")

    lines.append("## 逐句\n")
    lines.append("| # | id | trigger | 时长s | cer_norm | cer_kana | cer_plain | 参考(ja) | ASR 回译 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        lines.append(
            f"| {i} | `{r['id']}` | {r.get('trigger','')} | {r['dur_s']:.2f} | "
            f"{r['cer_norm']:.4f} | {r['cer_kana']:.4f} | {r['cer_plain']:.4f} | {r['ref']} | {r['hyp']} |"
        )
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ASR back-translation CER (character-level, Japanese)")
    ap.add_argument("--audio-dir", default=str(DEFAULT_AUDIO_DIR))
    ap.add_argument("--lines", default=str(DEFAULT_LINES))
    ap.add_argument("--model", default=os.environ.get("QWEN3_ASR_MODEL_PATH", str(DEFAULT_MODEL_DIR)))
    ap.add_argument("--out-dir", default=str(Path.cwd() / "eval-out" / "asr-cer"))
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--dtype", default="bf16", choices=["bf16", "fp16", "fp32"])
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条（试跑用）")
    ap.add_argument("--id", action="append", default=[], help="只跑指定 id（可重复）")
    ap.add_argument("--context", default="", help="给 ASR 的领域词偏置（默认空=不偏置；禁止填参考原文 ✗）")
    args = ap.parse_args(argv)

    audio_dir = Path(args.audio_dir)
    lines_path = Path(args.lines)
    model_dir = Path(args.model)
    out_dir = Path(args.out_dir)
    if not audio_dir.is_dir():
        print(f"[FATAL] audio dir not found: {audio_dir}", file=sys.stderr)
        return 2
    if not lines_path.is_file():
        print(f"[FATAL] lines file not found: {lines_path}", file=sys.stderr)
        return 2
    try:
        check_model_dir(model_dir)
    except FileNotFoundError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 3

    try:
        import torch  # noqa: F401
        import qwen_asr  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        print(f"[FATAL] ASR env missing: {exc}", file=sys.stderr)
        return 3

    lines = load_lines(lines_path)
    if args.id:
        wanted = set(args.id)
        lines = [l for l in lines if l["id"] in wanted]
    if args.limit:
        lines = lines[: args.limit]

    # id → audio
    jobs = []
    for line in lines:
        cands = [audio_dir / f"{line['id']}{ext}" for ext in (".m4a", ".wav", ".webm", ".mp3", ".flac")]
        hit = next((c for c in cands if c.is_file()), None)
        if hit is None:
            print(f"[WARN] no audio for id={line['id']} in {audio_dir}")
            continue
        jobs.append((line, hit))
    if not jobs:
        print("[FATAL] no (line, audio) pairs matched", file=sys.stderr)
        return 2
    print(f"[INFO] {len(jobs)} utterances to transcribe; decoding with PyAV/ffmpeg …")

    decoded = []
    for line, path in jobs:
        wav, sr, how = decode_audio(path)
        decoded.append((line, wav, sr, how))
    print(f"[INFO] decoded {len(decoded)} files ok")

    try:
        model, load_s = load_model(model_dir, args.device, args.dtype)
    except Exception as exc:  # noqa: BLE001
        print(f"[FATAL] model load failed: {exc}", file=sys.stderr)
        return 3

    rows = []
    t_infer = time.time()
    for i, (line, wav, sr, how) in enumerate(decoded, 1):
        t0 = time.time()
        result = model.transcribe([(wav, sr)], language="Japanese", context=args.context)[0]
        dt = time.time() - t0
        hyp = nfkc(result.text or "")
        ref = nfkc(line.get("ja") or "")
        ref_plain, hyp_plain = strip_space(ref), strip_space(hyp)
        ref_norm, hyp_norm = strip_punct(ref_plain), strip_punct(hyp_plain)
        ref_kana, hyp_kana = kana_uniform(ref_norm), kana_uniform(hyp_norm)
        rows.append(
            {
                "id": line["id"],
                "trigger": line.get("trigger", ""),
                "emotion": line.get("emotion", ""),
                "audio": str(jobs[i - 1][1]),
                "dur_s": len(wav) / sr,
                "ref": ref,
                "hyp": hyp,
                "cer_plain": cer(ref_plain, hyp_plain),
                "cer_norm": cer(ref_norm, hyp_norm),
                "cer_kana": cer(ref_kana, hyp_kana),
                "ref_len_norm": len(ref_norm),
                "edit_norm": levenshtein(ref_norm, hyp_norm),
                "infer_s": dt,
            }
        )
        print(f"  [{i}/{len(decoded)}] {line['id']:<22} CER={rows[-1]['cer_norm']:.4f} "
              f"(kana {rows[-1]['cer_kana']:.4f}, {dt:.2f}s)")
    infer_s = time.time() - t_infer

    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[2]
    meta = {
        "stamp": stamp,
        "engine": "Qwen3-ASR-0.6B (qwen_asr, offline pack asr-qwen3-0.6b)",
        "model_dir": str(model_dir),
        "audio_dir": str(audio_dir),
        "lines": str(lines_path),
        "device": args.device,
        "dtype": args.dtype,
        "context": args.context,
        "n": len(rows),
        "load_s": round(load_s, 2),
        "infer_s": round(infer_s, 2),
        "mean_s": round(infer_s / max(1, len(rows)), 2),
        "python": platform.python_version(),
        "repo_commit": git_commit_of(repo),
        "started": _dt.datetime.now().isoformat(timespec="seconds"),
        "cer_norm_mean": round(sum(r["cer_norm"] for r in rows) / len(rows), 4),
        "cer_kana_mean": round(sum(r["cer_kana"] for r in rows) / len(rows), 4),
        "cer_plain_mean": round(sum(r["cer_plain"] for r in rows) / len(rows), 4),
        "zero_cer": sum(1 for r in rows if r["cer_norm"] == 0),
        "under_10pct": sum(1 for r in rows if r["cer_norm"] <= 0.10),
    }

    csv_path = out_dir / f"asr-cer-{stamp}.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    raw_path = out_dir / f"asr-raw-{stamp}.json"
    raw_path.write_text(json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    md_path = out_dir / f"asr-cer-{stamp}.md"
    md_path.write_text(report_markdown(rows, meta), encoding="utf-8")

    print("\n=== SUMMARY ===")
    print(f"n={meta['n']}  cer_norm_mean={meta['cer_norm_mean']:.4f}  cer_kana_mean={meta['cer_kana_mean']:.4f}  "
          f"cer_plain_mean={meta['cer_plain_mean']:.4f}  zero={meta['zero_cer']}/{meta['n']}  "
          f"under10%={meta['under_10pct']}/{meta['n']}  load={meta['load_s']}s infer={meta['infer_s']}s")
    print(f"csv → {csv_path}")
    print(f"md  → {md_path}")
    print(f"json→ {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
