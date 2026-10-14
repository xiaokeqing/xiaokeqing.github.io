# -*- coding: utf-8 -*-
"""桐莉栖真音色合成（GPT-SoVITS v3 + 本机 CUDA）：1 句 / 3 句 / 12 句 / 60 句，并直接接后处理链路。

跑法（clone 的 cu124 环境）：
  uv run --locked --no-sync python E:\DeepSeek1\work\_tts-trial\synth.py --mode one
  ... --mode three | batch12 | all60        （--lines 默认 lines60.json，bank 表示只读线上 bank.json）
  可选 --no-post（只出 raw wav，不做 loudnorm/编码/包络）、--emotions on（用情绪参考包）、--device cuda|cpu

产物（默认 out/）：
  raw/<id>.wav                原始推理输出
  master/<id>.wav(.norm/.faded)  裁静音 + -16 LUFS 归一 + fade
  dist/<id>.m4a + <id>.webm   分发用双格式
  envelope/<id>.envelope.json 契约 {sampleRate:8000, hopMs:10, values[]}（从 dist 的 m4a 解码重算）
  meta/<id>.json              每句全部实测数字（含 sha256 / 响度 / 体积 / 耗时 / 显存）
  summary-<tag>.json          本轮汇总
"""
from __future__ import annotations

import argparse
import array
import json
import os
import sys
import time
import wave

ROOT = os.environ.get("KURISU_AMADEUS_ROOT") or r"E:\DeepSeek1\work\_amadeus-src"
# 本脚本放在 <blog repo>/scripts/voice/ 下 → 仓库根 = 上两级
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
TRIAL = os.path.dirname(os.path.abspath(__file__))
REPO_BANK = os.environ.get("KURISU_BANK") or os.path.join(
    REPO_ROOT, "static", "kurisu", "voice", "bank.json")
LINES60 = os.path.join(TRIAL, "lines60.json")

# 参考音频/文本一律从 config.settings（= catalog 默认）取；取不到才用 catalog 里那句兜底。
# ⚠️ 不要用 local_tts_infer.py 里的兜底串：kurisu_reference.wav 是 7.56s 的自我介绍，
#    文本配错会让音色/语调跑偏。
REF_TEXT_FALLBACK = "そういえば,正式に自己紹介していませんでしたね……牧瀬紅莉栖です.改めてまして,よろしく"
REF_AUDIO = os.path.join(ROOT, "assets", "audio", "reference", "kurisu_reference.wav")
GPT = os.path.join(ROOT, "assets", "models", "gpt-sovits", "weights", "gpt", "v3", "xxx-e15.ckpt")
SOVITS = os.path.join(ROOT, "assets", "models", "gpt-sovits", "weights", "sovits", "v3", "xxx_e2_s174_l32.pth")
EMOTION_ROOT = os.path.join(ROOT, "assets", "audio", "reference", "emotions")

sys.path.insert(0, ROOT)
REF_TEXT = REF_TEXT_FALLBACK
APP_SWITCHES = {}
try:
    import config.settings as _settings
    REF_AUDIO = _settings.TTS_REF_AUDIO_JA if os.path.isabs(_settings.TTS_REF_AUDIO_JA) \
        else os.path.abspath(os.path.join(ROOT, _settings.TTS_REF_AUDIO_JA))
    REF_TEXT = _settings.TTS_REF_TEXT_JA or REF_TEXT_FALLBACK
    APP_SWITCHES = {
        "TTS_OUTPUT_LANGUAGE": _settings.TTS_OUTPUT_LANGUAGE,
        "TTS_DEVICE": _settings.TTS_DEVICE,
        "TTS_BACKEND": _settings.TTS_BACKEND,
        "ENABLE_EXPERIMENTAL_V3_EMOTION_ROUTING": bool(
            getattr(_settings, "ENABLE_EXPERIMENTAL_V3_EMOTION_ROUTING", False)),
    }
except Exception as _exc:                      # pragma: no cover
    APP_SWITCHES = {"settings_import_error": str(_exc)}

os.environ.setdefault("ENABLE_CUDA_GRAPH", "auto")
os.environ.setdefault("TTS_T2S_FLASH_ATTN", "auto")

GEN_PARAMS = dict(how_to_cut="不切", top_k=5, top_p=1.0, temperature=0.6, speed=0.97,
                  sample_steps=16, if_sr=False, pause_second=0.4, enable_static_kv=True)


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


class VramSampler(object):
    """进程内显存采样：nvidia-smi 每 500ms 一次，记录真实峰值（torch 的 max_memory_allocated
    只统计本进程的 allocator，看不到桌面/别的进程，也没算 CUDA context 开销）"""

    def __init__(self, interval_ms=500):
        import subprocess
        import threading
        self.samples = []
        self._stop = False
        self._subprocess = subprocess

        def loop():
            while not self._stop:
                try:
                    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu",
                                          "--format=csv,noheader,nounits"],
                                         capture_output=True, timeout=10).stdout.decode().strip()
                    parts = [x.strip() for x in out.split(",")]
                    if parts and parts[0].isdigit():
                        self.samples.append((time.time(), int(parts[0]), int(parts[1]) if len(parts) > 1 else -1))
                except Exception:
                    pass
                time.sleep(interval_ms / 1000.0)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        self._thread.join(timeout=3)

    def stats(self):
        if not self.samples:
            return {"samples": 0}
        mem = [s[1] for s in self.samples]
        ut = [s[2] for s in self.samples if s[2] >= 0]
        return {"samples": len(mem), "peakMiB": max(mem), "minMiB": min(mem),
                "meanMiB": round(sum(mem) / len(mem), 1),
                "baselineMiB": mem[0], "peakUtilPct": max(ut) if ut else None,
                "deltaPeakMiB": max(mem) - mem[0]}


def emotion_reference(label):
    pack = json.load(open(os.path.join(EMOTION_ROOT, "references.json"), encoding="utf-8"))
    r = pack["references"][label]
    audio = os.path.join(EMOTION_ROOT, r["audio"])
    text = open(os.path.join(EMOTION_ROOT, r["transcript"]), encoding="utf-8").read().strip()
    return audio, text, "日文"


def write_wav_mono(path, samples_i16, rate):
    a = array.array("h")
    a.frombytes(samples_i16 if isinstance(samples_i16, (bytes, bytearray)) else samples_i16.tobytes())
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(a.tobytes())


def load_lines(which):
    if which == "bank":
        bank = json.load(open(REPO_BANK, encoding="utf-8"))
        return [{"id": k, "text": v["text"], "trigger": "bank", "emotion": "", "source": "existing",
                 "scene": v.get("scene", "")} for k, v in bank["lines"].items()]
    data = json.load(open(which, encoding="utf-8"))
    return data["lines"]


def pick(lines, mode, ids_arg):
    if ids_arg:
        want = [x for x in ids_arg.split(",") if x]
        return [l for l in lines if l["id"] in want]
    if mode == "one":
        return [l for l in lines if l["id"] == "greet_first"]
    if mode == "three":
        return [l for l in lines if l["id"] in ("greet_first", "greet_back", "nav_home")]
    if mode == "batch12":
        bank = json.load(open(REPO_BANK, encoding="utf-8"))
        order = list(bank["lines"].keys())
        return [l for l in lines if l["id"] in order]
    return lines                                     # all60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="one", choices=["one", "three", "batch12", "all60"])
    ap.add_argument("--ids", default="")
    ap.add_argument("--lines", default=os.path.join(TRIAL, "lines60-bilingual.json"))
    ap.add_argument("--lang", default="日文", choices=["日文", "中文"],
                    help="送进 TTS 的语言：日文=用 line['ja']（参考音频就是日语，音色才对；且日语不需要 BERT）")
    ap.add_argument("--out", default=os.environ.get("KURISU_OUT") or
                    os.path.join(os.environ.get("TEMP", TRIAL), "kurisu-voice-out"))
    ap.add_argument("--tag", default="")
    ap.add_argument("--emotions", default="off", choices=["off", "on"])
    ap.add_argument("--emotion", default="")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--no-post", action="store_true")
    ap.add_argument("--sample-steps", type=int, default=GEN_PARAMS["sample_steps"])
    args = ap.parse_args()

    lines_all = load_lines(args.lines if args.lines != "bank" else "bank")
    todo = pick(lines_all, args.mode, args.ids)
    if not todo:
        raise SystemExit("没有可合成的台词（检查 --mode/--ids/--lines）")
    os.makedirs(os.path.join(args.out, "raw"), exist_ok=True)

    log("importing torch + GPT-SoVITS …")
    import torch
    import numpy as np
    from local_tts_infer import TTSInferencer

    if args.device.startswith("cuda"):
        log("cuda available=%s device=%s" % (torch.cuda.is_available(), torch.cuda.get_device_name(0)
                                             if torch.cuda.is_available() else "-"))
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            log("vram before load: free=%.0fMiB / %.0fMiB" % (free / 2**20, total / 2**20))

    t0 = time.time()
    sampler = VramSampler()
    inf = TTSInferencer(device=args.device, gpt_path=GPT, sovits_path=SOVITS)
    load_s = time.time() - t0
    log("model loaded in %.1fs (is_half=%s device=%s)" % (load_s, inf.is_half, inf.device))
    if args.device.startswith("cuda") and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        free, _ = torch.cuda.mem_get_info()
        log("vram after load: free=%.0fMiB | nvidia-smi=%s" % (free / 2**20, sampler.stats()))

    results = []
    for line in todo:
        lid = line["id"]
        if args.lang == "日文":
            text = line.get("ja") or line.get("text") or ""
        else:
            text = line.get("zh") or line.get("text") or ""
        if not text:
            log("skip %s：没有 %s 文本" % (lid, args.lang))
            continue
        emo = args.emotion or (line.get("emotion", "") if args.emotions == "on" else "")
        sem = None
        if emo and os.path.isdir(EMOTION_ROOT):
            try:
                sem = emotion_reference(emo)
            except Exception as exc:
                log("emotion %r unavailable (%s) → 用默认参考" % (emo, exc))
                emo, sem = "", None
        ts = time.time()
        kw = dict(GEN_PARAMS)
        kw.update(text=text, ref_audio_path=REF_AUDIO, prompt_text=REF_TEXT, text_language=args.lang,
                  prompt_language="日文", sample_steps=args.sample_steps)
        if sem:
            kw["semantic_reference"] = sem
        sr, audio = inf.infer(**kw)
        synth_s = time.time() - ts
        a = np.asarray(audio)
        if a.dtype != np.int16:
            a = (np.clip(a, -1.0, 1.0) * 32767.0).astype(np.int16)
        raw_path = os.path.join(args.out, "raw", lid + ".wav")
        write_wav_mono(raw_path, a, sr)
        peak = torch.cuda.max_memory_allocated() / 2**20 if (args.device.startswith("cuda") and torch.cuda.is_available()) else 0
        free = torch.cuda.mem_get_info()[0] / 2**20 if (args.device.startswith("cuda") and torch.cuda.is_available()) else 0
        rec = {"id": lid, "trigger": line.get("trigger", ""), "source": line.get("source", ""),
               "lang": args.lang, "text": text, "textZh": line.get("zh") or line.get("text") or "", "scene": line.get("scene", ""), "emotion": emo or "",
               "sampleRate": int(sr), "seconds": round(len(a) / sr, 3), "samples": int(len(a)),
               "synthSeconds": round(synth_s, 3), "rawWav": raw_path,
               "rawBytes": os.path.getsize(raw_path),
               "cudaPeakAllocMiB": round(peak, 1), "cudaFreeMiB": round(free, 1)}
        if not args.no_post:
            import postprocess
            meta = postprocess.postprocess(raw_path, lid, args.out)
            rec.update({"m4a": meta["m4a"], "webm": meta["webm"],
                        "envelope": {k: meta["envelope"][k] for k in
                                     ("values", "first", "max", "madM4aVsWebm", "sourceFile")},
                        "loudness": {"final_i_master": meta["loudness"]["final_i_master"],
                                     "final_tp_master": meta["loudness"]["final_tp_master"],
                                     "error_lu": meta["loudness"]["error_lu_master"]},
                        "masterSeconds": meta["master"]["seconds"]})
        results.append(rec)
        log(json.dumps({k: rec.get(k) for k in ("id", "emotion", "seconds", "synthSeconds",
                                                "cudaPeakAllocMiB", "cudaFreeMiB")}, ensure_ascii=False)
            + (" | " + json.dumps({"m4a": rec["m4a"]["bytes"], "webm": rec["webm"]["bytes"],
                                   "lufs": rec["m4a"].get("lufs")}, ensure_ascii=False) if not args.no_post else ""))

    summary = {
        "mode": args.mode, "ids": [r["id"] for r in results], "device": args.device,
        "modelLoadSeconds": round(load_s, 2), "gpt": GPT, "sovits": SOVITS,
        "refAudio": REF_AUDIO, "refText": REF_TEXT, "refLanguage": "日文", "targetLanguage": args.lang,
        "params": dict(GEN_PARAMS, sample_steps=args.sample_steps,
                       note="对齐 tts/pipeline.py get_sovits_params() 的非首句档；CLI 默认是 top_k20/top_p0.6/speed1.0"),
        "env": {"ENABLE_CUDA_GRAPH": os.environ.get("ENABLE_CUDA_GRAPH"),
                "TTS_T2S_FLASH_ATTN": os.environ.get("TTS_T2S_FLASH_ATTN"), **APP_SWITCHES},
        "torch": torch.__version__, "cuda": getattr(torch.version, "cuda", None),
        "cuda_available": bool(torch.cuda.is_available()),
        "cudaDeviceName": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
        "cudaPeakAllocMiB": round(torch.cuda.max_memory_allocated() / 2**20, 1) if torch.cuda.is_available() else 0,
        "lines": results,
        "totalSynthSeconds": round(sum(r["synthSeconds"] for r in results), 2),
        "meanSynthSeconds": round(sum(r["synthSeconds"] for r in results) / max(len(results), 1), 2),
        "maxSynthSeconds": round(max(r["synthSeconds"] for r in results), 2),
    }
    if not args.no_post:
        summary["totalM4aBytes"] = sum(r["m4a"]["bytes"] for r in results)
        summary["totalWebmBytes"] = sum(r["webm"]["bytes"] for r in results)
        summary["totalSeconds"] = round(sum(r["masterSeconds"] for r in results), 2)
    tag = args.tag or args.mode
    sampler.stop()
    summary["vramSampler"] = sampler.stats()
    summary["gpuName"] = summary.get("cudaDeviceName")
    spath = os.path.join(args.out, "summary-%s.json" % tag)
    json.dump(summary, open(spath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log("summary → %s" % spath)
    log(json.dumps({k: summary.get(k) for k in ("mode", "device", "modelLoadSeconds",
                                               "totalSynthSeconds", "meanSynthSeconds",
                                               "maxSynthSeconds", "cudaPeakAllocMiB",
                                               "totalM4aBytes", "totalWebmBytes")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
