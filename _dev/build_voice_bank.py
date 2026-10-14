# -*- coding: utf-8 -*-
"""L1 语音产物：母带（16k/16bit PCM）→ 站点用 8kHz G.711 µ-law WAV + 口型包络 JSON + bank.json

为什么**不是** µ-law：第一版发的是 8kHz G.711 µ-law（更小），但真浏览器实测
  `Audio.play()` 抛 `NotSupportedError` —— Chrome 的 WAV 解复用器不吃 µ-law（ffmpeg 里
  pcm_mulaw 在 wav 里并没有被接上）。**没声音就是没做到**，所以改成 8kHz / 16bit PCM
  （浏览器必然支持），代价是 16KB/s → 一句 ~75KB、12 句共 ~0.9MB（仍不是首屏资产，懒载）。
换成 Opus 只需把这些 .wav 换掉 + 改 bank.json 里的 url，播放器一行都不用改。

包络口径（照抄规格 §4）：hopMs=10、mouthValue = clamp(RMS(10ms 窗) × 3.75, 0, 1)、首窗保底 0.12、
停止发 0。格式固定为 {sampleRate, hopMs:10, values[0..1]}。
用法：python _dev/build_voice_bank.py
"""
import json
import os
import struct
import audioop
import wave

REPO = r'F:\7AAA\AI\blog'
DEV = os.path.join(REPO, '_dev')
MASTERS = os.path.join(DEV, 'voice-masters')
OUT = os.path.join(REPO, 'static', 'kurisu', 'voice')
LINES = os.path.join(DEV, 'voice-lines.json')
BANK = os.path.join(OUT, 'bank.json')

TARGET_RATE = 8000
HOP_MS = 10
GAIN = 3.75
FIRST_FLOOR = 0.12


def pcm_wav(pcm, rate):
    """标准 PCM WAVE 头（fmt tag 1、16bit、单声道）"""
    n = len(pcm)
    hdr = b'RIFF' + struct.pack('<I', 36 + n) + b'WAVE'
    hdr += b'fmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * 2, 2, 16)
    hdr += b'data' + struct.pack('<I', n)
    return hdr + pcm


def envelope(pcm8k):
    hop = int(TARGET_RATE * HOP_MS / 1000)
    vals = []
    for i in range(0, len(pcm8k) - 1, hop * 2):
        chunk = pcm8k[i:i + hop * 2]
        if not chunk:
            break
        r = audioop.rms(chunk, 2) / 32768.0
        v = r * GAIN
        vals.append(1.0 if v > 1.0 else round(v, 4))
    if vals:
        if vals[0] < FIRST_FLOOR:
            vals[0] = FIRST_FLOOR
    return vals


def main():
    raw = json.load(open(LINES, encoding='utf-8'))
    lines = raw['lines']
    scenes = raw.get('scenes') or {}
    os.makedirs(OUT, exist_ok=True)
    bank = {
        'format': 'xiaokeqing.kurisu.voicebank.v1',
        'generator': '_dev/synth-voice.ps1（Windows SAPI 5，Microsoft Huihui Desktop）'
                     ' + _dev/build_voice_bank.py',
        'voiceNote': '音色是系统 TTS（Huihui），不是桐莉栖。换音色 = 换这批 wav，播放器不用改。',
        'codec': 'pcm_s16le', 'sampleRate': TARGET_RATE, 'hopMs': HOP_MS,
        'envelopeFormula': 'clamp(RMS(10ms) * 3.75, 0, 1)，首窗保底 0.12，停止发 0',
        'lines': {},
    }
    rows = []
    tot = 0
    for lid, text in lines.items():
        mpath = os.path.join(MASTERS, lid + '.wav')
        if not os.path.exists(mpath):
            raise SystemExit('缺母带：%s（先跑 _dev/synth-voice.ps1）' % mpath)
        with wave.open(mpath, 'rb') as w:
            assert w.getnchannels() == 1 and w.getsampwidth() == 2, lid
            src_rate = w.getframerate()
            pcm = w.readframes(w.getnframes())
        pcm8, _ = audioop.ratecv(pcm, 2, 1, src_rate, TARGET_RATE, None)
        wav = pcm_wav(pcm8, TARGET_RATE)
        opath = os.path.join(OUT, lid + '.wav')
        open(opath, 'wb').write(wav)
        env = envelope(pcm8)
        epath = os.path.join(OUT, lid + '.envelope.json')
        json.dump({'sampleRate': TARGET_RATE, 'hopMs': HOP_MS, 'values': env},
                  open(epath, 'w', encoding='utf-8'), ensure_ascii=False)
        secs = len(pcm8) / 2.0 / TARGET_RATE
        bank['lines'][lid] = {
            'text': text,
            'scene': scenes.get(lid, ''),
            'audio': 'kurisu/voice/%s.wav' % lid,
            'envelope': 'kurisu/voice/%s.envelope.json' % lid,
            'seconds': round(secs, 3),
            'audioBytes': len(wav),
            'envelopeValues': len(env),
        }
        tot += len(wav)
        rows.append((lid, secs, len(wav), len(env), text))
    json.dump(bank, open(BANK, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # ---- 同一份契约写进 manifest.json 的 voice 段（运行时与 L2 读同一份，别靠约定） ----
    mf_path = os.path.join(REPO, 'static', 'kurisu', 'manifest.json')
    mf = json.load(open(mf_path, encoding='utf-8'))
    mf['voice'] = {
        'bank': 'kurisu/voice/bank.json',
        'codec': bank['codec'],
        'sampleRate': bank['sampleRate'],
        'hopMs': bank['hopMs'],
        'envelopeFormula': bank['envelopeFormula'],
        'voiceNote': bank['voiceNote'],
        'totalBytes': tot,
        'lineCount': len(bank['lines']),
        'lines': [
            {'id': lid, 'audio': v['audio'], 'envelope': v['envelope'], 'text': v['text'],
             'scene': v['scene'], 'seconds': v['seconds'], 'audioBytes': v['audioBytes']}
            for lid, v in bank['lines'].items()
        ],
    }
    json.dump(mf, open(mf_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('voice 段（%d 条）→ %s' % (len(bank['lines']), mf_path))

    print('| 台词 id | 时长s | 音频字节 | 包络点数 | 文本 |')
    print('|---|---:|---:|---:|---|')
    for lid, secs, b, n, text in rows:
        print('| `%s` | %.2f | %s | %d | %s |' % (lid, secs, format(b, ','), n, text))
    print()
    print('共 %d 句 / %s B = %.2f MB（8kHz u-law(G.711)，平均 %.0f KB/句）'
          % (len(rows), format(tot, ','), tot / 1048576.0, tot / 1024.0 / len(rows)))
    print('bank →', BANK)


if __name__ == '__main__':
    main()
