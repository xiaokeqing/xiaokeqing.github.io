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
# ⚠️ 中文 Windows 控制台是 GBK，脚本里的 ✓/✗ 会 UnicodeEncodeError（本窗口在别的脚本上踩过 ✓）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001  （老 Python / 被重定向时不致命）
    pass
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
TP_ENCODE_HEADROOM = 1.0    # ★真峰口径：母带压到（目标 − 1.0dB）再编码，给 AAC 码间过冲留余量
TP_ENCODE_FIX_ROUNDS = 4    # ★编码后若仍超目标，回头降增益重编码的最大轮次
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


def clip_true_peak_inplace(master_path, log=None, max_rounds=8):
    """把**母带**的真峰值压到 ≤ LOUDNESS_TP（默认 -1.5 dBTP），原地覆盖 master_path。

    ★ 为什么需要这一步（2026-10-15 窗口 B 实测的真缺陷，别删）：
      `alimiter` 压的是**采样峰**，而验收口径（也是 loudnorm 报的）是 **true peak**；
      更要命的是**已贴满 0 dBFS 的信号**，alimiter 只改增益包络、对样本值本身几乎是空操作
      ⇒ 限幅阈值越紧，真峰反而可能升高 ✗。
      所以正确做法是：**在对的层级（母带）上迭代压低真峰到（目标 − 编码余量）**，
      编码带来的码间过冲由调用方（postprocess）在编码后复核，不够再回头补增益 ✓。
    返回 True 表示动过手（调用方需要重新编码），False 表示本来就合规（**零改动** ✓）。
    """
    meas = measure_loudness(master_path)
    tp = float(meas["input_tp"])
    if tp <= LOUDNESS_TP - TP_ENCODE_HEADROOM:
        if log is not None:
            log.append({"stage": "preclip", "tp": tp, "action": "skip（本来就合规）"})
        return False
    cur = master_path
    lim = LOUDNESS_TP - TP_ENCODE_HEADROOM        # 起点：目标 − 余量
    for i in range(max_rounds):
        meas = measure_loudness(cur)
        tp = float(meas["input_tp"])
        if tp <= LOUDNESS_TP - TP_ENCODE_HEADROOM:
            break
        nxt = master_path + ".tp%d.wav" % i
        rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", cur, "-af",
                          "alimiter=limit=%.2fdB:level=disabled:attack=5:release=50" % lim,
                          "-ac", "1", "-c:a", "pcm_s16le", nxt])
        if rc != 0:
            raise RuntimeError("true-peak clip failed: " + err.decode("utf-8", "replace")[-300:])
        if log is not None:
            log.append({"stage": "preclip", "iter": i, "limit_db": lim, "tp_before": tp,
                        "file": os.path.basename(nxt)})
        cur = nxt
        lim = round(lim - 0.5, 2)
    # 落回原路径（后续编码统一读原路径 ✓）
    with open(cur, "rb") as a, open(master_path, "wb") as b:
        b.write(a.read())
    if os.path.abspath(cur) != os.path.abspath(master_path):
        try:
            for i in range(max_rounds):
                p = master_path + ".tp%d.wav" % i
                if os.path.exists(p):
                    os.remove(p)
        except OSError:
            pass
    # ★ 限幅会把整体电平也压下去一点（alimiter 的增益包络对通过信号同样生效）
    #   ⇒ 这里在**不重新抬高真峰**的前提下把响度补回 -16：增益上限 = 目标 − 真峰 − 余量 ✓
    m2 = measure_loudness(master_path)
    i2, tp2 = float(m2["input_i"]), float(m2["input_tp"])
    want = round(LOUDNESS_I - i2, 2)
    room = round((LOUDNESS_TP - TP_ENCODE_HEADROOM) - tp2, 2)
    gain = min(want, room)
    if abs(gain) >= 0.25:
        tmp = master_path + ".tpnorm.wav"
        rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", master_path, "-af",
                          "volume=%.2fdB" % gain, "-ac", "1", "-c:a", "pcm_s16le", tmp])
        if rc == 0:
            m3 = measure_loudness(tmp)
            if float(m3["input_tp"]) <= LOUDNESS_TP - 0.05:
                with open(tmp, "rb") as a, open(master_path, "wb") as b:
                    b.write(a.read())
                if log is not None:
                    log.append({"stage": "preclip-renorm", "gain_db": gain,
                                "lufs": float(m3["input_i"]), "tp": float(m3["input_tp"])})
            try:
                os.remove(tmp)
            except OSError:
                pass
    return True


def normalize_to_target(src, dst, max_iters=5):
    """measure → (线性增益 + true-peak 限幅) → 再实测，闭环收敛：**同时**满足
      · integrated ≈ -16 LUFS（|误差| < 0.3 LU）
      · true peak ≤ -1.5 dBTP
    ⚠️ 这一步**在 fade 之前**做；最终交付文件是否合规由 `postprocess()` 编码后再复核（见那里的闭环 ✓）。
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
    loud_chain = list(loud.get("applied") or [])
    # ③ 首尾 fade（用 areverse 做尾淡出，避免先算时长）→ 最终母带
    faded = os.path.join(dirs["master"], lid + ".faded.wav")
    chain = "afade=t=in:st=0:d=%s,areverse,afade=t=in:st=0:d=%s,areverse" % (FADE_S, FADE_S)
    rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", norm, "-af", chain, "-ac", "1",
                      "-c:a", "pcm_s16le", faded])
    if rc != 0:
        raise RuntimeError("fade failed: " + err.decode("utf-8", "replace")[-400:])
    norm = faded

    # ③b ★真峰预压（**只在需要时**动手 ✓）：先把响度归到 -16，再检查真峰；
    #     真峰超（目标 − 编码余量）才限幅 ⇒ 绝大多数条目响度保持精确 -16 ✓
    loud_chain.append({"stage": "fade", "note": "响度在 fade **之后**测（口径修正）"})
    clipped = clip_true_peak_inplace(norm, loud_chain)
    if clipped:
        norm = faded          # 原地覆盖，路径不变

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

    # ④b ★真峰闭环（对**最终分发的 m4a** 复核）：编码会带来码间过冲 ⇒ 仍超目标就回头补降增益再编 ✓
    #     为什么必须在这一层闭合：`alimiter` 压采样峰，而验收口径是 true peak；
    #     只在母带上压、不量最终文件，就会出现"母带合规、上线文件超标"（本轮真踩过 ✗）
    tp_fix = 0
    extra_db = 0.0
    final_meas = measure_loudness(m4a)
    while float(final_meas["input_tp"]) > LOUDNESS_TP and tp_fix < TP_ENCODE_FIX_ROUNDS:
        deficit = float(final_meas["input_tp"]) - LOUDNESS_TP
        extra_db = round(extra_db - (deficit + 0.2), 2)
        tmp_master = os.path.join(dirs["master"], lid + ".tpfix.wav")
        rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", norm, "-af",
                          "volume=%.2fdB" % extra_db, "-ac", "1", "-c:a", "pcm_s16le", tmp_master])
        if rc != 0:
            raise RuntimeError("tp-fix volume failed: " + err.decode("utf-8", "replace")[-300:])
        rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", tmp_master, "-c:a", "aac",
                          "-b:a", AAC_BITRATE, "-ac", "1", "-ar", str(AAC_SR),
                          "-movflags", "+faststart", m4a])
        if rc != 0:
            raise RuntimeError("tp-fix aac failed: " + err.decode("utf-8", "replace")[-300:])
        rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", tmp_master, "-c:a", "libopus",
                          "-b:a", OPUS_BITRATE, "-ac", "1", "-ar", str(OPUS_SR), webm])
        if rc != 0:
            raise RuntimeError("tp-fix opus failed: " + err.decode("utf-8", "replace")[-300:])
        final_meas = measure_loudness(m4a)
        tp_fix += 1
        loud_chain.append({"stage": "encode-tp-fix", "round": tp_fix, "extra_db": extra_db,
                           "tp_after": float(final_meas["input_tp"]),
                           "i_after": float(final_meas["input_i"])})
    loud["tp_encode_fix"] = {"rounds": tp_fix, "extra_db": extra_db,
                             "clip_pre_applied": clipped,
                             "final_tp_m4a": float(final_meas["input_tp"]),
                             "final_i_m4a": float(final_meas["input_i"]),
                             "tp_ok": float(final_meas["input_tp"]) <= LOUDNESS_TP}
    # 先落到"当前最终文件"的实测值，后面的补偿都以它为准 ✓
    final_i_m4a = float(final_meas["input_i"])
    final_tp_m4a = float(final_meas["input_tp"])

    # ④c ★对**最终交付文件**收响度（口径以编码后为准 ✓，补偿"母带 → 编码"之间的系统偏移）
    #     为什么需要：AAC 编码后 loudnorm 实测比母带低约 0.3~0.5 LU（本机实测 ✓），
    #     若只对母带归 -16，交付文件就会系统偏低 ⇒ 这里按"实测偏移"补一次，且**不得抬高真峰** ✓
    trim_db = 0.0
    if abs(final_i_m4a - LOUDNESS_I) >= 0.25:
        want = round(LOUDNESS_I - final_i_m4a, 2)
        room = round((LOUDNESS_TP - 0.05) - float(final_meas["input_tp"]), 2)
        trim_db = min(want, room)
        if abs(trim_db) >= 0.15:
            # ⚠️ 候选文件写到**临时名**，采纳时把内容拷回 `norm`（规范路径）再重编码；
            #    绝不能让 `norm` 指向"用完就删"的临时文件（否则后面 probe/包络会 FileNotFound ✗ 踩过）
            cand_master = os.path.join(dirs["master"], lid + ".i-trim.wav")
            rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", norm, "-af",
                              "volume=%.2fdB" % trim_db, "-ac", "1", "-c:a", "pcm_s16le", cand_master])
            applied = False
            if rc == 0:
                cand_m4a = os.path.join(dirs["master"], lid + ".i-trim.m4a")
                cand_webm = os.path.join(dirs["master"], lid + ".i-trim.webm")
                rc_a, _, _ = run([FFMPEG, "-y", "-v", "error", "-i", cand_master, "-c:a", "aac",
                                  "-b:a", AAC_BITRATE, "-ac", "1", "-ar", str(AAC_SR),
                                  "-movflags", "+faststart", cand_m4a])
                rc_b, _, _ = run([FFMPEG, "-y", "-v", "error", "-i", cand_master, "-c:a", "libopus",
                                  "-b:a", OPUS_BITRATE, "-ac", "1", "-ar", str(OPUS_SR), cand_webm])
                if rc_a == 0 and rc_b == 0:
                    cand = measure_loudness(cand_m4a)
                    if (float(cand["input_tp"]) <= LOUDNESS_TP
                            and abs(float(cand["input_i"]) - LOUDNESS_I) < abs(final_i_m4a - LOUDNESS_I)):
                        # 采纳：拷回规范路径 + 覆盖 dist（保证 meta 描述的就是磁盘上的文件 ✓）
                        for src_p, dst_p in ((cand_master, norm), (cand_m4a, m4a), (cand_webm, webm)):
                            with open(src_p, "rb") as a, open(dst_p, "wb") as b:
                                b.write(a.read())
                        final_meas = measure_loudness(m4a)
                        applied = True
                        loud_chain.append({"stage": "final-loudness-trim", "trim_db": trim_db,
                                           "lufs": float(final_meas["input_i"]),
                                           "tp": float(final_meas["input_tp"]), "applied": True})
                    else:
                        loud_chain.append({"stage": "final-loudness-trim", "trim_db": trim_db,
                                           "applied": False, "why": "更远或真峰不合规 ⇒ 保留原编码"})
                for tmp_p in (cand_master, cand_m4a, cand_webm):
                    try:
                        os.remove(tmp_p)
                    except OSError:
                        pass
            if not applied and not any(x.get("stage") == "final-loudness-trim" for x in loud_chain):
                loud_chain.append({"stage": "final-loudness-trim", "trim_db": trim_db,
                                   "applied": False, "why": "候选生成失败 ⇒ 保留原编码"})
    loud["finalTrim"] = {"db": trim_db, "lufs_final": float(final_meas["input_i"]),
                         "tp_final": float(final_meas["input_tp"])}
    final_i_m4a = float(final_meas["input_i"])
    final_tp_m4a = float(final_meas["input_tp"])
    loud["applied"] = loud_chain

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
    # ★ fade **之后** 的最终母带实测（口径修正 ✓）
    m_master = measure_loudness(norm)
    final_i_master = float(m_master["input_i"])
    final_tp_master = float(m_master["input_tp"])
    # ★ 最终分发文件实测（真正的交付口径 ✓）
    final_i_m4a = float(final_meas["input_i"])
    final_tp_m4a = float(final_meas["input_tp"])
    meta = {
        "id": lid,
        "raw": {"path": raw_out, "bytes": os.path.getsize(raw_out) if os.path.exists(raw_out) else 0},
        "master": {"path": master, "bytes": os.path.getsize(master),
                   "normPath": norm, "normBytes": os.path.getsize(norm),
                   "seconds": round(probe_duration_s(master), 3)},
        "loudness": {"target_I": LOUDNESS_I, "target_TP": LOUDNESS_TP, "target_LRA": LOUDNESS_LRA,
                     "normalize": loud,
                     # ⚠️ 口径修正（2026-10-15 窗口 B）：这两个字段以前是 **fade 之前** 测的，
                     #    与真正上线的 m4a 有偏差 ⇒ 现在改成 **fade 之后** 的最终母带实测值 ✓；
                     #    交付口径以 `m4a.final_i` / `m4a.final_tp`（对**编码后**文件的实测）为准 ✓
                     "final_i_master": final_i_master, "final_tp_master": final_tp_master,
                     "error_lu_master": round(final_i_master - LOUDNESS_I, 3),
                     "measuredAfterFade": True,
                     "normalizeCycle": {"final_i": loud["final_i"], "final_tp": loud["final_tp"]}},
        "m4a": {"path": m4a, "bytes": os.path.getsize(m4a), "seconds": round(dur_m4a, 3),
                "codec": "aac", "bitrate": AAC_BITRATE, "sampleRate": AAC_SR,
                "sha256": sha256_file(m4a), "lufs": final_i_m4a,
                "final_i": final_i_m4a, "final_tp": final_tp_m4a,
                "tp_ok": final_tp_m4a <= LOUDNESS_TP},
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
    # 复核块已删除：现在 `m4a.lufs` / `m4a.final_i` / `m4a.final_tp` 直接取自上面 ④b 的真峰闭环实测
    # （那份测量本来就是"对最终分发文件"做的 ✓，再测一遍只是浪费一次 ffmpeg ✓）
    mpath = os.path.join(dirs["meta"], lid + ".json")
    json.dump(meta, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return meta


def _selftest_input(lid, voice_dir):
    """找一条可用于自检的**原始输入** wav，返回 (路径, 说明)。

    为什么需要这个（2026-10-15 修）：本函数原先硬编码读 `static/kurisu/voice/<id>.wav`，
    但线上那 12 个 wav 在 T17 声音换代时已被 v3 的 `m4a/webm` 取代 ⇒ `--selftest` 直接
    `FileNotFoundError: nav_notes.wav`（窗口 B 实测）。自检应当用"**当前真实存在**的输入"。

    查找顺序（先本地母带、再解码线上 m4a）：
      ① `KURISU_SELFTEST_WAV_DIR` 指定的目录
      ② `_dev/voice-masters/<id>.wav`（T17 留下的**母带**，32k/单声道/16bit，是理想输入 ✓）
      ③ `static/kurisu/voice/<id>.wav`（历史位置，现已不存在 ⇒ 仅作兼容）
      ④ `static/kurisu/voice/<id>.m4a` 存在 ⇒ 先解码成临时 wav 再喂进链路（多一次有损再编码，
         所以**只在前三条都落空时**才用；返回值里会写明来源，避免把结果当"母带级"证据 ✗）
    """
    cand_dirs = [os.environ.get("KURISU_SELFTEST_WAV_DIR") or "",
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_dev", "voice-masters"),
                 voice_dir]
    for d in cand_dirs:
        if not d:
            continue
        p = os.path.join(d, lid + ".wav")
        if os.path.isfile(p):
            return p, "wav:%s" % os.path.abspath(p)
    m4a = os.path.join(voice_dir, lid + ".m4a")
    if os.path.isfile(m4a):
        tmp = os.path.join(os.environ.get("TEMP", HERE), "kurisu-selftest-in")
        os.makedirs(tmp, exist_ok=True)
        wav = os.path.join(tmp, lid + ".wav")
        rc, _, err = run([FFMPEG, "-y", "-v", "error", "-i", m4a, "-ac", "1",
                          "-c:a", "pcm_s16le", wav])
        if rc == 0:
            return wav, "decoded-from:%s（有损再编码 ⇒ 体积/包络数字只作链路自检用）" % m4a
        raise RuntimeError("从 m4a 解码自检输入失败：" + err.decode("utf-8", "replace")[-200:])
    raise FileNotFoundError("自检找不到 %s 的输入：试过 %s 与 %s" % (lid, cand_dirs, m4a))


def selftest():
    """用**当前真实存在**的输入 wav 跑全链路：验证响度/体积/包络自洽（不需要 torch）

    ⚠️ 输出目录默认**不在仓库里**：本机实测 ffmpeg（子进程）对 `F:\\7AAA\\AI\\blog\\...` 写入会 EACCES
    （python/PowerShell 能写、ffmpeg 不能），所以产物一律落到 %TEMP%\\kurisu-voice-out 或 KURISU_OUT。
    ⚠️ 输入优先级见 `_selftest_input()`：优先 `_dev/voice-masters/<id>.wav`（T17 母带），
    最后才回退到"解码线上 m4a"，且结果里写明来源（免得把有损输入的数字当母带证据 ✗）。
    """
    V = os.environ.get("KURISU_VOICE_DIR") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "static", "kurisu", "voice")
    out = os.path.join(os.environ.get("KURISU_OUT") or os.path.join(
        os.environ.get("TEMP", HERE), "kurisu-voice-out"), "_selftest")
    ids = ["nav_notes", "greet_first", "fallback_throttled"]
    rows = []
    for lid in ids:
        src, how = _selftest_input(lid, V)
        m = postprocess(src, lid, out)
        rows.append(m)
        print(json.dumps({"id": lid, "input": how, "master_s": m["master"]["seconds"],
                          "m4a": [m["m4a"]["bytes"], m["m4a"]["seconds"], m["m4a"]["lufs"]],
                          "webm": [m["webm"]["bytes"], m["webm"]["seconds"]],
                          "loudness": [m["loudness"]["final_i_master"], m["loudness"]["final_tp_master"],
                                       m["loudness"]["error_lu_master"]],
                          "env": [m["envelope"]["values"], m["envelope"]["first"], m["envelope"]["max"]],
                          "mad_m4a_vs_webm": m["envelope"]["madM4aVsWebm"],
                          "input_bytes": os.path.getsize(src)},
                         ensure_ascii=False))
    tot_m4a = sum(r["m4a"]["bytes"] for r in rows)
    tot_webm = sum(r["webm"]["bytes"] for r in rows)
    print(json.dumps({"selftest": True, "ids": ids,
                      "inputNote": "输入 = _selftest_input()（优先 _dev/voice-masters 母带；回退时写明来源）",
                      "m4a_bytes": tot_m4a, "webm_bytes": tot_webm,
                      "mean_m4a": tot_m4a // len(rows), "mean_webm": tot_webm // len(rows),
                      "lufsSpread": round(max(r["loudness"]["final_i_master"] for r in rows) -
                                          min(r["loudness"]["final_i_master"] for r in rows), 3),
                      "maxTruePeak": max(r["loudness"]["final_tp_master"] for r in rows),
                      "allTpOk": all(r["loudness"]["final_tp_master"] <= -1.5 for r in rows)},
                     ensure_ascii=False))
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
