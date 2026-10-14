# -*- coding: utf-8 -*-
"""后处理管线（评审 6 条硬要求的落地）：raw wav → 裁静音 → loudnorm(-16 LUFS) → fade → m4a + webm
                              → **从最终编码文件**重算 envelope → 元数据(sha256/时长/字节)。

用法：
  python postprocess.py --in <raw.wav> --id greet_first --out out
  python postprocess.py --selftest          # 用现有 SAPI wav 验证链路（不需要 torch）

产物（每个 id）：
  raw/<id>.wav              —— 原始推理输出（保真，留档）
  master/<id>.wav           —— 裁静音 + 归一后、编码前的母带（32k/16bit/mono）
  dist/<id>.m4a             —— 主用（AAC，Safari 最稳）
  dist/<id>.webm            —— 更小（Opus，Chrome/Edge 优先）
  envelope/<id>.envelope.json —— 契约 {sampleRate:8000, hopMs:10, values[0..1]}，**从 dist/<id>.m4a 解出的 PCM 算**
  meta/<id>.json            —— 全部实测数字 + sha256
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import os
import re
import subprocess
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
_FF_DIR = os.environ.get("KURISU_FFMPEG_DIR") or r"E:\DeepSeek1\work\_kurisu-017\video-pipeline\tools\ffmpeg-master-latest-win64-gpl\bin"
FFMPEG = os.environ.get("KURISU_FFMPEG") or os.path.join(_FF_DIR, "ffmpeg.exe")
FFPROBE = os.environ.get("KURISU_FFPROBE") or os.path.join(_FF_DIR, "ffprobe.exe")

TARGET_RATE = 8000          # 包络口径（与线上 12 句一致）
HOP_MS = 10
GAIN = 3.75
FIRST_FLOOR = 0.12
LOUDNESS_I = -16.0          # EBU R128 目标
LOUDNESS_TP = -1.5
LOUDNESS_LRA = 11.0
FADE_S = 0.04               # 首尾 40ms（评审要 30~50ms）
TRIM_DB = -45               # 静音判定
AAC_BITRATE = "48k"
OPUS_BITRATE = "40k"
AAC_SR = 32000
OPUS_SR = 48000


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, **kw)
    return p.returncode, (p.stdout or b""), (p.stderr or b"")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def probe_duration_s(path):
    rc, out, err = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", path])
    if rc != 0:
        raise RuntimeError("ffprobe failed: " + err.decode("utf-8", "replace")[-300:])
    return float(out.decode().strip())


def envelope_from_pcm_bytes(raw, hop_samples):
    """与 _dev/build_voice_bank.py 逐点一致（audioop.rms），只是 PCM 来自**最终编码文件**的解码结果"""
    import audioop
    hop_bytes = hop_samples * 2
    vals = []
    for i in range(0, len(raw) - 1, hop_bytes):
        chunk = raw[i:i + hop_bytes]
        if not chunk:
            break
        v = audioop.rms(chunk, 2) / 32768.0 * GAIN
        vals.append(1.0 if v > 1.0 else round(v, 4))
    if vals and vals[0] < FIRST_FLOOR:
        vals[0] = FIRST_FLOOR
    return vals


def decode_to_envelope(path, rate=TARGET_RATE):
    """从"最终分发文件"解出 mono/16bit PCM（重采样到 rate）→ 包络 + 采样数"""
    rc, out, err = run([FFMPEG, "-v", "error", "-i", path, "-ac", "1", "-ar", str(rate),
                        "-f", "s16le", "-"])
    if rc != 0:
        raise RuntimeError("decode failed: " + err.decode("utf-8", "replace")[-300:])
    hop = int(rate * HOP_MS / 1000)
    return envelope_from_pcm_bytes(out, hop), len(out) // 2


def measure_loudness(path):
    """用 ffmpeg 的 EBU R128（loudnorm）测量 integrated LUFS / true peak / LRA"""
    filt = ("loudnorm=I=%s:TP=%s:LRA=%s:print_format=json" % (LOUDNESS_I, LOUDNESS_TP, LOUDNESS_LRA))
    rc, out, err = run([FFMPEG, "-v", "info", "-i", path, "-af", filt, "-f", "null", "-"])
    txt = err.decode("utf-8", "replace")
    m = re.findall(r"\{\s*\"input_i\".*?\}", txt, re.S)
    if not m:
        raise RuntimeError("loudnorm 测量没拿到 JSON:\n" + txt[-500:])
    return json.loads(m[-1])


def normalize_to_target(src, dst, max_iters=5):
    """measure → (线性增益 + true-peak 限幅) → 再实测，闭环收敛：**同时**满足
      · integrated ≈ -16 LUFS（|误差| < 0.3 LU）
      · true peak ≤ -1.5 dBTP
    alimiter 只压 sample peak，真峰(TP)会比它高 ~1.4dB，所以限幅起点取 TP-1.5dB 并逐轮收紧。
    """
    cur = src
    log = []
    lim = LOUDNESS_TP - 1.5                     # -3.0 dB 起步
    for i in range(max_iters):
        meas = measure_loudness(cur)
        got, tp = float(meas["input_i"]), float(meas["input_tp"])
        gain = LOUDNESS_I - got
        need_gain = abs(gain) >= 0.3
        need_lim = tp > LOUDNESS_TP
        if not need_gain and not need_lim:
            log.append({"iter": i, "measured_i": got, "measured_tp": tp, "gain_db": 0.0,
                        "limiter_db": None, "done": True})
            break
        af_parts = []
        if need_gain:
            af_parts.append("volume=%.3fdB" % gain)
        if need_lim or (tp + gain) > (LOUDNESS_TP - 0.05):
            af_parts.append("alimiter=limit=%.2fdB:level=disabled:attack=5:release=50" % lim)
            lim = round(lim - 0.5, 2)           # 下一轮再收紧 0.5dB
        af = ",".join(af_parts)
        nxt = dst if i == max_iters - 1 else dst.replace(".wav", ".i%d.wav" % i)
        rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", cur, "-af", af, "-ac", "1",
                          "-c:a", "pcm_s16le", nxt])
        if rc != 0:
            raise RuntimeError("normalize failed: " + err.decode("utf-8", "replace")[-300:])
        log.append({"iter": i, "measured_i": got, "measured_tp": tp,
                    "gain_db": round(gain, 3) if need_gain else 0.0,
                    "limiter_db": lim + 0.5 if "alimiter" in af else None, "done": False})
        cur = nxt
    if os.path.abspath(cur) != os.path.abspath(dst):
        with open(cur, "rb") as a, open(dst, "wb") as b:
            b.write(a.read())
    final = measure_loudness(dst)
    return {"target_I": LOUDNESS_I, "target_TP": LOUDNESS_TP, "target_LRA": LOUDNESS_LRA,
            "applied": log, "final_i": float(final["input_i"]), "final_tp": float(final["input_tp"]),
            "final_lra": float(final["input_lra"]),
            "error_lu": round(float(final["input_i"]) - LOUDNESS_I, 3),
            "tp_ok": float(final["input_tp"]) <= LOUDNESS_TP}


def postprocess(raw_path, lid, out_root, keep_raw=True):
    dirs = {k: os.path.join(out_root, k) for k in ("raw", "master", "dist", "envelope", "meta")}
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    raw_out = os.path.join(dirs["raw"], lid + ".wav")
    if keep_raw and os.path.abspath(raw_path) != os.path.abspath(raw_out):
        with open(raw_path, "rb") as a, open(raw_out, "wb") as b:
            b.write(a.read())

    # ① 裁静音（首尾；-45dB 判定）→ 母带
    trim = ("silenceremove=start_periods=1:start_duration=0:start_threshold=%ddB:detection=peak,"
            "areverse,"
            "silenceremove=start_periods=1:start_duration=0:start_threshold=%ddB:detection=peak,"
            "areverse" % (TRIM_DB, TRIM_DB))
    master = os.path.join(dirs["master"], lid + ".wav")
    rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", raw_path, "-af", trim, "-ac", "1",
                      "-c:a", "pcm_s16le", master])
    if rc != 0:
        raise RuntimeError("trim failed: " + err.decode("utf-8", "replace")[-300:])

    # ② 响度归一到 -16 LUFS（确定性闭环：实测 → 增益 → 再实测）
    norm = os.path.join(dirs["master"], lid + ".norm.wav")
    loud = normalize_to_target(master, norm)
    # ③ 首尾 fade（用 areverse 做尾淡出，避免先算时长）→ 最终母带
    faded = os.path.join(dirs["master"], lid + ".faded.wav")
    chain = "afade=t=in:st=0:d=%s,areverse,afade=t=in:st=0:d=%s,areverse" % (FADE_S, FADE_S)
    rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", norm, "-af", chain, "-ac", "1",
                      "-c:a", "pcm_s16le", faded])
    if rc != 0:
        raise RuntimeError("fade failed: " + err.decode("utf-8", "replace")[-400:])
    norm = faded

    # ④ 双格式分发编码
    m4a = os.path.join(dirs["dist"], lid + ".m4a")
    webm = os.path.join(dirs["dist"], lid + ".webm")
    rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", norm, "-c:a", "aac", "-b:a", AAC_BITRATE,
                      "-ac", "1", "-ar", str(AAC_SR), "-movflags", "+faststart", m4a])
    if rc != 0:
        raise RuntimeError("aac failed: " + err.decode("utf-8", "replace")[-300:])
    rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", norm, "-c:a", "libopus",
                      "-b:a", OPUS_BITRATE, "-ac", "1", "-ar", str(OPUS_SR), webm])
    if rc != 0:
        raise RuntimeError("opus failed: " + err.decode("utf-8", "replace")[-300:])

    # ⑤ 包络：从**最终分发的 m4a**解码（评审要求；有损编码会改变 RMS）
    env_vals, env_samples = decode_to_envelope(m4a)
    env_path = os.path.join(dirs["envelope"], lid + ".envelope.json")
    json.dump({"sampleRate": TARGET_RATE, "hopMs": HOP_MS, "values": env_vals},
              open(env_path, "w", encoding="utf-8"), ensure_ascii=False)

    # 校验：webm 解出的包络应与 m4a 版几乎一致（同一母带 → 两种编码）
    env_webm, _ = decode_to_envelope(webm)
    n = min(len(env_vals), len(env_webm))
    mad = sum(abs(env_vals[i] - env_webm[i]) for i in range(n)) / max(n, 1)

    dur_m4a = probe_duration_s(m4a)
    dur_webm = probe_duration_s(webm)
    meta = {
        "id": lid,
        "raw": {"path": raw_out, "bytes": os.path.getsize(raw_out) if os.path.exists(raw_out) else 0},
        "master": {"path": master, "bytes": os.path.getsize(master),
                   "normPath": norm, "normBytes": os.path.getsize(norm),
                   "seconds": round(probe_duration_s(master), 3)},
        "loudness": {"target_I": LOUDNESS_I, "target_TP": LOUDNESS_TP, "target_LRA": LOUDNESS_LRA,
                     "normalize": loud,
                     "final_i_master": loud["final_i"], "final_tp_master": loud["final_tp"],
                     "error_lu_master": loud["error_lu"]},
        "m4a": {"path": m4a, "bytes": os.path.getsize(m4a), "seconds": round(dur_m4a, 3),
                "codec": "aac", "bitrate": AAC_BITRATE, "sampleRate": AAC_SR,
                "sha256": sha256_file(m4a), "lufs": None},
        "webm": {"path": webm, "bytes": os.path.getsize(webm), "seconds": round(dur_webm, 3),
                 "codec": "opus", "bitrate": OPUS_BITRATE, "sampleRate": OPUS_SR,
                 "sha256": sha256_file(webm), "lufs": None},
        "envelope": {"path": env_path, "sampleRate": TARGET_RATE, "hopMs": HOP_MS,
                     "values": len(env_vals), "decodedSamples": env_samples,
                     "sourceFile": "dist/%s.m4a" % lid,
                     "first": env_vals[0] if env_vals else None,
                     "max": max(env_vals) if env_vals else None,
                     "madM4aVsWebm": round(mad, 5)},
    }
    # 复核：最终 m4a 的实测响度
    rc, out, err = run([FFMPEG, "-v", "info", "-i", m4a, "-af",
                        "loudnorm=I=%s:TP=%s:LRA=%s:print_format=json" % (LOUDNESS_I, LOUDNESS_TP, LOUDNESS_LRA),
                        "-f", "null", "-"])
    mm = re.findall(r"\{\s*\"input_i\".*?\}", err.decode("utf-8", "replace"), re.S)
    if mm:
        meta["m4a"]["lufs"] = float(json.loads(mm[-1])["input_i"])
    mpath = os.path.join(dirs["meta"], lid + ".json")
    json.dump(meta, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return meta


def selftest():
    """用现有 SAPI wav 跑全链路：验证响度/体积/包络自洽（不需要 torch）

    ⚠️ 输出目录默认**不在仓库里**：本机实测 ffmpeg（子进程）对 `F:\\7AAA\\AI\\blog\\...` 写入会 EACCES
    （python/PowerShell 能写、ffmpeg 不能），所以产物一律落到 %TEMP%\\kurisu-voice-out 或 KURISU_OUT。
    """
    V = os.environ.get("KURISU_VOICE_DIR") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "static", "kurisu", "voice")
    out = os.path.join(os.environ.get("KURISU_OUT") or os.path.join(
        os.environ.get("TEMP", HERE), "kurisu-voice-out"), "_selftest")
    ids = ["nav_notes", "greet_first", "fallback_throttled"]
    rows = []
    for lid in ids:
        m = postprocess(os.path.join(V, lid + ".wav"), lid, out)
        rows.append(m)
        print(json.dumps({"id": lid, "master_s": m["master"]["seconds"],
                          "m4a": [m["m4a"]["bytes"], m["m4a"]["seconds"], m["m4a"]["lufs"]],
                          "webm": [m["webm"]["bytes"], m["webm"]["seconds"]],
                          "env": [m["envelope"]["values"], m["envelope"]["first"], m["envelope"]["max"]],
                          "mad_m4a_vs_webm": m["envelope"]["madM4aVsWebm"],
                          "online_wav_bytes": os.path.getsize(os.path.join(V, lid + ".wav"))},
                         ensure_ascii=False))
    tot_m4a = sum(r["m4a"]["bytes"] for r in rows)
    tot_webm = sum(r["webm"]["bytes"] for r in rows)
    tot_wav = sum(os.path.getsize(os.path.join(V, r["id"] + ".wav")) for r in rows)
    print(json.dumps({"selftest": True, "ids": ids,
                      "m4a_bytes": tot_m4a, "webm_bytes": tot_webm, "wav_bytes_online": tot_wav,
                      "mean_m4a": tot_m4a // len(rows), "mean_webm": tot_webm // len(rows),
                      "ratio_vs_wav": round((tot_m4a + tot_webm) / tot_wav, 3)}, ensure_ascii=False))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp")
    ap.add_argument("--id", dest="lid")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.inp or not args.lid:
        raise SystemExit("需要 --in 与 --id（或用 --selftest）")
    m = postprocess(args.inp, args.lid, args.out)
    print(json.dumps(m, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
