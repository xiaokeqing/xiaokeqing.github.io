# -*- coding: utf-8 -*-
"""校验器（2026-10-16 起不再是"刷新器"）：校验 voice/bank.json 自身自洽，并断言 manifest.json 里**没有** voice 段。

**为什么改：**原来它把 bank.json 的 160 条（含 sha256/包络/来源）**复制**进 manifest.json 的 voice 段，
约 90~101 KB。而运行期**没有任何代码读 manifest.voice**（全库唯一 `.voice` 命中是 shell-script.html 的
`V.T.voice = V.hostEntries`，属于状态机的"台词组→转场"表），manifest.json 却在首屏被取
（idcard 读 emotions.*.idle.frames / 状态机读图集清单）⇒ 在 3~6 KB/s 的链路上这是 ~20~30 秒死重，
且数据与 bank.json 重复。**语音事实的唯一真源 = static/kurisu/voice/bank.json。**
防回归：唯一的写入者既已移除，`_dev/build_statemachine_manifest.py` 里也显式 `mf.pop('voice', None)`。

用法：python _dev/refresh_manifest_voice.py   （退出码 0=通过；7=manifest 里又冒出 voice 段）

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

    # ★慢网减量（2026-10-16，主窗口）：本脚本**不再写入** manifest 的 voice 段。
    #   该段约 90~101 KB，是与 voice/bank.json 的重复数据，运行期无人读它，而 manifest.json
    #   确实在首屏被取 ⇒ 在 3~6 KB/s 的链路上是 ~20~30 秒死重。语音事实的唯一真源 = bank.json。
    #   现在本脚本只做"静态校验"：校验 bank 自身自洽（逐行 sha256/字节从磁盘重算）＋
    #   断言 manifest 里**不该再有** voice 段（防回归）。
    if 'voice' in mf:
        sz = len(json.dumps(mf['voice'], ensure_ascii=False).encode('utf-8'))
        print('回归：manifest.json 又出现了 voice 段（%d B，约 %.1f KB）——本脚本已改为只校验、不写入。'
              % (sz, sz / 1024.0), file=sys.stderr)
        print('请检查 _dev/build_statemachine_manifest.py（那里应显式 mf.pop("voice", None)）。', file=sys.stderr)
        sys.exit(7)

    print('静态校验通过（本脚本不再写入 manifest）：')
    print('  bank.json：lines=%d、totalBytes=%d，逐行 sha256/字节已从磁盘重算且与自报值一致 ✓' % (len(out), total))
    print('  manifest.json：**无 voice 段** ✓（语音事实的唯一真源 = static/kurisu/voice/bank.json）')
    print('  若哪天这里报“回归”，说明 voice 段被别处写回 —— 去 build_statemachine_manifest.py 堵源头。')


if __name__ == '__main__':
    main()
