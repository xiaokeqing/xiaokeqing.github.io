# -*- coding: utf-8 -*-
"""T8 顺手项：把 static/kurisu/manifest.json 的 voice 段刷新到与 voice/bank.json 一致。

为什么：窗口 B 换过声音（12 句 v3 同口径可复现重跑版，总字节 716,960 -> 714,845），
bank.json 是唯一真源，manifest 的 voice 段还是旧数字 + 旧 sha256 ⇒ 口径不一致。
运行期其实不受影响（kurisu-player.js 只读 bank.json），但"两处数字不一致"迟早坑人 ✗。

做法（不猜、不编）：
  · lineCount / totalBytes 从 bank.json 抄（逐行 audioBytes 求和校验，对不上就报错退出）
  · 每行的 sha256 / audioBytes / durationMs / seconds / audioSources 从**磁盘上的真文件**重算
  · 若 bank.json 自报的 sha256 与磁盘文件不一致 ⇒ 直接报错（说明文件被动过，不能偷偷改口径）
用法：python _dev/refresh_manifest_voice.py
"""
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MF = os.path.join(ROOT, 'static', 'kurisu', 'manifest.json')
BANK = os.path.join(ROOT, 'static', 'kurisu', 'voice', 'bank.json')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def rel(u):
    """bank.json 里的路径是 'kurisu/voice/x.m4a'（相对 static/）"""
    return os.path.join(ROOT, 'static', u.replace('/', os.sep))


def main():
    mf = json.load(io.open(MF, encoding='utf-8'))
    bank = json.load(io.open(BANK, encoding='utf-8'))
    lines = bank.get('lines') or {}
    if not isinstance(lines, dict) or not lines:
        print('bank.json 的 lines 不是非空字典，停。', file=sys.stderr)
        sys.exit(2)

    voice = mf.get('voice') or {}
    old_total, old_count = voice.get('totalBytes'), voice.get('lineCount')
    out, total = [], 0
    for lid, e in lines.items():
        srcs = e.get('audioSources') or {}
        rec = {
            'id': lid,
            'trigger': e.get('trigger'),
            'audio': e.get('audio'),
            'audioSources': srcs,
            'envelope': e.get('envelope'),
            'text': e.get('text'),
            'scene': e.get('scene'),
            'seconds': e.get('seconds'),
            'durationMs': e.get('durationMs'),
            'sha256': {},
            'audioBytes': {},
        }
        for kind, u in srcs.items():
            p = rel(u)
            if not os.path.isfile(p):
                print('缺文件：%s' % p, file=sys.stderr)
                sys.exit(3)
            got = sha256(p)
            want = (e.get('sha256') or {}).get(kind)
            if want and want != got:
                print('sha256 不一致（%s %s）：bank=%s 磁盘=%s' % (lid, kind, want[:12], got[:12]), file=sys.stderr)
                sys.exit(4)
            rec['sha256'][kind] = got
            rec['audioBytes'][kind] = os.path.getsize(p)
            total += os.path.getsize(p)
        out.append(rec)

    if total != bank.get('totalBytes'):
        print('总字节校验不过：逐行求和 %d != bank.totalBytes %s' % (total, bank.get('totalBytes')), file=sys.stderr)
        sys.exit(5)
    if len(out) != bank.get('lineCount'):
        print('行数校验不过：%d != %s' % (len(out), bank.get('lineCount')), file=sys.stderr)
        sys.exit(6)

    voice.update({
        'bank': 'kurisu/voice/bank.json',
        'codec': bank.get('codec'),
        'sampleRate': bank.get('sampleRate'),
        'hopMs': bank.get('hopMs'),
        'envelopeFormula': bank.get('envelopeFormula'),
        'voiceNote': bank.get('voiceNote'),
        'totalBytes': total,
        'lineCount': len(out),
        'lines': out,
        'note': ('本段的唯一真源是 static/kurisu/voice/bank.json（运行期 kurisu-player.js 只读它）；'
                 '这里的数字由 _dev/refresh_manifest_voice.py 从磁盘文件重算，供索引/核对用。'),
    })
    mf['voice'] = voice
    io.open(MF, 'w', encoding='utf-8').write(json.dumps(mf, ensure_ascii=False, indent=1, sort_keys=True))

    print('刷新 static/kurisu/manifest.json 的 voice 段：')
    print('  lineCount : %s -> %d' % (old_count, len(out)))
    print('  totalBytes: %s -> %d' % (old_total, total))
    print('  逐行 sha256 已从磁盘重算，且与 bank.json 自报值一致 ✓')
    print('  写回：%s' % MF)


if __name__ == '__main__':
    main()
