# -*- coding: utf-8 -*-
"""把 60 句产物打包成可替换进博客的 bank.json + manifest 片段 + 自检报告（**只写 _tts-trial，不碰博客仓库**）。

产物（默认 --out out）：
  bank%s.json" % (("_" + args.tag) if args.tag else "")          60 句，按 trigger 分组，字段见下方 NOTE
  bank_12lines%s.json" % (("_" + args.tag) if args.tag else "")            仅线上那 12 条的替换子集（最小改动上线用）
  manifest-voice.snippet.json  manifest.json 里 voice 段的替换片段（同 schema + 扩展字段）
  voice-budget.json            体积预算自检（static/kurisu/voice/ ≤ 3MiB 的实测投影）
  verify.json                  全量自检：格式/响度/sha256/包络自洽/句数/分组

NOTE（字段取舍）：播放器现在读 `lines[id].audio`（字符串 URL），所以本文件**保持 v1 兼容**：
  `audio` = m4a 相对路径（主用，Safari 最稳）；另加 `audioSources{m4a,webm}` 与 `sha256{m4a,webm}`、
  `trigger/durationMs/source/emotion/group`。要"Chrome/Edge 优先用 Opus"，只需播放器加一行
  `canPlayType('audio/webm; codecs="opus"')` 判断取 audioSources.webm —— 这条列在 REPORT 的改动清单里。

用法：python build_bank.py [--out out] [--lines lines60.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os

TRIAL = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TRIAL, "..", ".."))
REPO_VOICE = os.environ.get("KURISU_VOICE_DIR") or os.path.join(
    REPO_ROOT, "static", "kurisu", "voice")
BUDGET_BYTES = 3 * 1024 * 1024          # 评审要求：static/kurisu/voice/ ≤ 3MiB
GROUPS = ["greeting", "page_intro", "status", "event", "idle_banter", "fallback", "emotion"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(TRIAL, "out"))
    ap.add_argument("--lines", default=os.path.join(TRIAL, "lines60-bilingual.json"))
    ap.add_argument("--ids", default="", help="只打包这些 id（逗号分隔）；空=全部")
    ap.add_argument("--tag", default="", help="输出文件名后缀，如 sample8")
    args = ap.parse_args()

    tag_suffix = ("_" + args.tag) if args.tag else ""
    lines = json.load(open(args.lines, encoding="utf-8"))["lines"]
    if args.ids:
        want = [x for x in args.ids.split(",") if x]
        lines = [l for l in lines if l["id"] in want]
        if len(lines) != len(want):
            raise SystemExit("有 id 不在台词库里：%s" % (set(want) - {l["id"] for l in lines}))
    bank_lines, verify_lines, missing = {}, [], []
    total = 0
    for ln in lines:
        lid = ln["id"]
        mp = os.path.join(args.out, "meta", lid + ".json")
        if not os.path.exists(mp):
            missing.append(lid)
            continue
        meta = json.load(open(mp, encoding="utf-8"))
        m4a, webm = meta["m4a"], meta["webm"]
        env = meta["envelope"]
        dur_ms = int(round(m4a["seconds"] * 1000))
        rec = {
            "id": lid,
            "trigger": ln["trigger"],
            "group": ln["trigger"],
            "text": ln["text"],
            "scene": ln.get("scene", ""),
            "emotion": ln.get("emotion", ""),
            "source": ln.get("source", ""),
            # —— v1 兼容字段（播放器今天就读这个）——
            "audio": "kurisu/voice/%s.m4a" % lid,
            "envelope": "kurisu/voice/%s.envelope.json" % lid,
            "seconds": round(m4a["seconds"], 3),
            "audioBytes": m4a["bytes"],
            "envelopeValues": env["values"],
            # —— 评审要求的扩展字段 ——
            "audioSources": {"m4a": "kurisu/voice/%s.m4a" % lid,
                             "webm": "kurisu/voice/%s.webm" % lid},
            "durationMs": dur_ms,
            "sha256": {"m4a": m4a["sha256"], "webm": webm["sha256"]},
            "bytes": {"m4a": m4a["bytes"], "webm": webm["bytes"]},
            "loudness": {"lufs": m4a.get("lufs"), "target": -16.0},
            "envelopeSource": env["sourceFile"],
        }
        bank_lines[lid] = rec
        total += m4a["bytes"] + webm["bytes"]
        verify_lines.append({
            "id": lid, "trigger": ln["trigger"], "source": ln.get("source"),
            "m4a": m4a["bytes"], "webm": webm["bytes"], "seconds": rec["seconds"],
            "durationMs": dur_ms, "lufs": m4a.get("lufs"),
            "envelopeValues": env["values"], "envelopeFirst": env["first"],
            "madM4aVsWebm": env["madM4aVsWebm"],
            "sha256_m4a_ok": sha256_file(m4a["path"]) == m4a["sha256"],
            "sha256_webm_ok": sha256_file(webm["path"]) == webm["sha256"],
            "emotion": rec["emotion"],
            "textUnchangedVsLive": None,
        })

    # 与线上那 12 条逐字对照
    live = json.load(open(os.path.join(REPO_VOICE, "bank.json"), encoding="utf-8"))["lines"]
    for v in verify_lines:
        if v["id"] in live:
            v["textUnchangedVsLive"] = live[v["id"]]["text"] == bank_lines[v["id"]]["text"]

    bank = {
        "format": "xiaokeqing.kurisu.voicebank.v1",
        "generator": "GPT-SoVITS v3（本机 RTX 3060 Laptop 6GB，clone cu124 env）+ "
                     r"E:\DeepSeek1\work\_tts-trial\{synth.py,postprocess.py,build_bank.py}",
        "voiceNote": "音色 = GPT-SoVITS v3 桐莉栖（本机合成）。换音色/换句子 = 换 voice/ 下的文件 + 改 bank.json，播放器不用改。",
        "codec": "aac(m4a) + opus(webm)",
        "sampleRate": 8000,
        "hopMs": 10,
        "envelopeFormula": "clamp(RMS(10ms) * 3.75, 0, 1)，首窗保底 0.12，停止发 0（0.08 是播放器侧静音阈值，不写进包络）",
        "envelopeSource": "解码最终分发的 m4a 得到（不是母带 wav）",
        "loudnessTarget": -16.0,
        "groups": {g: sum(1 for l in bank_lines.values() if l["trigger"] == g) for g in GROUPS},
        "groupPolicy": "同组内轮转/随机抽取（避免重复感）；greeting 组首句进首屏预载，其余 <audio preload=none> 懒载",
        "lineCount": len(bank_lines),
        "totalBytes": total,
        "lines": bank_lines,
    }
    json.dump(bank, open(os.path.join(args.out, "bank%s.json" % tag_suffix), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    live_order = list(live.keys())
    sub = {"format": bank["format"], "generator": bank["generator"], "voiceNote": bank["voiceNote"],
           "codec": bank["codec"], "sampleRate": 8000, "hopMs": 10,
           "envelopeFormula": bank["envelopeFormula"],
           "lineCount": len(live_order),
           "totalBytes": sum(bank_lines[k]["audioBytes"] + bank_lines[k]["bytes"]["webm"]
                             for k in live_order if k in bank_lines),
           "lines": {k: bank_lines[k] for k in live_order if k in bank_lines}}
    json.dump(sub, open(os.path.join(args.out, "bank_12lines.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    mf = json.load(open(os.environ.get("KURISU_MANIFEST") or
                    os.path.join(REPO_ROOT, "static", "kurisu", "manifest.json"),
                    encoding="utf-8"))
    voice = dict(mf.get("voice") or {})
    voice.update({
        "bank": "kurisu/voice/bank.json",
        "codec": bank["codec"], "sampleRate": 8000, "hopMs": 10,
        "envelopeFormula": bank["envelopeFormula"], "voiceNote": bank["voiceNote"],
        "totalBytes": total, "lineCount": len(bank_lines),
        "groups": bank["groups"], "groupPolicy": bank["groupPolicy"],
        "lines": [{"id": k, "trigger": v["trigger"], "audio": v["audio"],
                   "audioSources": v["audioSources"], "envelope": v["envelope"],
                   "text": v["text"], "scene": v["scene"], "seconds": v["seconds"],
                   "durationMs": v["durationMs"], "audioBytes": v["audioBytes"],
                   "sha256": v["sha256"]}
                  for k, v in bank_lines.items()],
    })
    json.dump(voice, open(os.path.join(args.out, "manifest-voice.snippet.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    lufs_vals = [v["lufs"] for v in verify_lines if v["lufs"] is not None]
    budget = {
        "budgetBytes": BUDGET_BYTES,
        "totalM4aBytes": sum(v["m4a"] for v in verify_lines),
        "totalWebmBytes": sum(v["webm"] for v in verify_lines),
        "totalBytes": total,
        "ratioOfBudget": round(total / BUDGET_BYTES, 4),
        "withinBudget": total <= BUDGET_BYTES,
        "note": "线上 static/kurisu/voice 现在 926,278 B（含 8k wav 12 句）；换成 60 句 m4a+webm 后见 totalBytes",
        "onlineVoiceDirBytesNow": sum(os.path.getsize(os.path.join(REPO_VOICE, f))
                                      for f in os.listdir(REPO_VOICE)),
        "firstScreenPreload": "只预载 greeting 第一条（~%.1f KB m4a）" % (
            bank_lines[[l for l in lines if l["trigger"] == "greeting"][0]["id"]]["audioBytes"] / 1024),
    }
    json.dump(budget, open(os.path.join(args.out, "voice-budget%s.json" % tag_suffix), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    report = {
        "lines": len(verify_lines), "expected": len(lines), "missing": missing,
        "groups": bank["groups"],
        "allTextUnchangedVsLive": all(v["textUnchangedVsLive"] for v in verify_lines
                                      if v["textUnchangedVsLive"] is not None),
        "allSha256Ok": all(v["sha256_m4a_ok"] and v["sha256_webm_ok"] for v in verify_lines),
        "lufsMin": min(lufs_vals) if lufs_vals else None,
        "lufsMax": max(lufs_vals) if lufs_vals else None,
        "lufsSpreadLt1": (max(lufs_vals) - min(lufs_vals)) < 1.0 if lufs_vals else None,
        "totalSeconds": round(sum(v["seconds"] for v in verify_lines), 2),
        "meanSeconds": round(sum(v["seconds"] for v in verify_lines) / max(len(verify_lines), 1), 3),
        "budget": budget,
        "perLine": verify_lines,
    }
    json.dump(report, open(os.path.join(args.out, "verify%s.json" % tag_suffix), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({k: report[k] for k in ("lines", "expected", "missing", "groups",
                                            "allTextUnchangedVsLive", "allSha256Ok",
                                            "lufsMin", "lufsMax", "lufsSpreadLt1",
                                            "totalSeconds", "meanSeconds")},
                     ensure_ascii=False, indent=1))
    print("预算：合计 %.2f MB / 上限 %.2f MB（%.1f%%）→ withinBudget=%s"
          % (total / 1048576, BUDGET_BYTES / 1048576, total / BUDGET_BYTES * 100, budget["withinBudget"]))


if __name__ == "__main__":
    main()
