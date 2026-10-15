# -*- coding: utf-8 -*-
"""T7 视频接线 · 生成 static/kurisu/video-manifest.json（可重跑）

输入（只读，都在仓库外）：
  E:\\DeepSeek1\\work\\_kurisu-017\\video-assets\\video\\<clip>.webm        ×40  透明 VP9+alpha
  E:\\DeepSeek1\\work\\_kurisu-017\\video-assets\\video\\<clip>.poster.webp ×40  视频第 0 帧
  E:\\DeepSeek1\\work\\_kurisu-017\\video-assets\\manifest-video.json      逐剪辑码流尺寸/字节/自检指标
  static/kurisu/statemachine.json                                        剪辑 → 帧数/单帧时长/循环语义

输出：
  static/kurisu/video-manifest.json   给站点运行时用的**白名单 + 逐帧时长**表

为什么必须以 statemachine.json 为准：
  视频容器是按 60fps 编的（durationMs = frames/60*1000），**那不是播放语义**；
  真正的单帧时长在 statemachine 的 frameIntervalMs（8/17/21ms）。渲染器按 frameIndex 逐帧画，
  所以这里只抄 frameIntervalMs，绝不拿 durationMs 当间隔（否则 8ms 的转场会被慢放 2 倍）。

数字纪律：所有字节都来自真实文件 stat；clip 的帧数必须与 statemachine 完全相等，
  不相等就直接报错退出（不允许把对不上的素材默默写进清单）。
用法：python _dev/build_video_manifest.py
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SM = os.path.join(ROOT, 'static', 'kurisu', 'statemachine.json')
OUT = os.path.join(ROOT, 'static', 'kurisu', 'video-manifest.json')
DST_DIR = os.path.join(ROOT, 'static', 'kurisu', 'video')
SRC_DIR = r'E:\DeepSeek1\work\_kurisu-017\video-assets\video'
SRC_MANIFEST = r'E:\DeepSeek1\work\_kurisu-017\video-assets\manifest-video.json'
MEDIUM_MANIFEST = os.path.join(ROOT, 'static', 'kurisu', 'manifest.json')

if not os.path.isfile(SRC_MANIFEST):
    print('读不到源清单：%s' % SRC_MANIFEST, file=sys.stderr)
    sys.exit(2)

sm = json.load(open(SM, encoding='utf-8'))
vm = json.load(open(SRC_MANIFEST, encoding='utf-8'))
sm_clips = {n['clip']: n for n in sm['nodes']}
# reverse 标记只在上游 medium manifest 里（`key_point_to_thinking` = thinking_to_key_point 倒放）：
#   实测（_shots/video-align.json）该剪辑的**视频是正放、图集是倒放** —— 首末帧剪影质心差 ±1.9px、
#   中间帧完全吻合 ⇒ 播放端必须按 video[i] = atlas[n-1-i] 取帧，否则入场/收尾会跳一下。
#   （总账 C9 已记过这条坑的另一个后果：倒放剪辑的嘴部锚点不能倒放复用。）
mm = json.load(open(MEDIUM_MANIFEST, encoding='utf-8'))
mm_clips = ((mm.get('clipsMedium') or {}).get('clips')) or {}

clips = {}
warn = []
for clip, meta in sorted(vm['clips'].items()):
    node = sm_clips.get(clip)
    if node is None:
        # sad / smile：有素材但不在状态机里（state machine 的白名单外）⇒ 不写进运行时可播清单
        warn.append('%s: 不在 statemachine.json（clips_not_in_graph）-> 不进白名单' % clip)
        continue
    webm = os.path.join(DST_DIR, clip + '.webm')
    poster = os.path.join(DST_DIR, clip + '.poster.webp')
    for p in (webm, poster):
        if not os.path.isfile(p):
            print('缺文件：%s（先跑第 1 步资产入库）' % p, file=sys.stderr)
            sys.exit(2)
    wb, pb = os.path.getsize(webm), os.path.getsize(poster)
    if node['frames'] != meta['frames']:
        print('帧数对不上：%s statemachine=%d video=%d' % (clip, node['frames'], meta['frames']), file=sys.stderr)
        sys.exit(3)
    clips[clip] = {
        'clip': clip,
        'frames': node['frames'],
        'frameIntervalMs': node['frameIntervalMs'],
        'loopMode': node['loopMode'],
        'reverse': bool((mm_clips.get(clip) or {}).get('reverse')),   # true ⇒ 播放端取 video[n-1-i]
        'canvas': meta['canvas'],          # [764,1028] 状态机画幅（不是码流尺寸）
        'coded': meta['coded'],            # pad 后的码流尺寸
        'video': 'kurisu/video/%s.webm' % clip,
        'poster': 'kurisu/video/%s.poster.webp' % clip,
        'bytes': {'webm': wb, 'poster': pb},
        # 自检指标照抄上游 manifest（不自己算、不改口径）——只留报告用的三个数
        'alphaMae': meta['alphaMae'],
        'rgbPsnr': meta['rgbPsnr'],
        'edgeNcc': meta['edgeNcc'],
        'codec': meta['codec'],
        'hasAlpha': meta['hasAlpha'],
    }

if not clips:
    print('一个剪辑都没写进来，停。', file=sys.stderr)
    sys.exit(4)

# 只预载 root + root 出边 top-2（T7 预载纪律）；这里把"可预载集"算好写进清单，
# 页面侧不再自己推断（少一处会漂的逻辑）。
edges = [e for e in sm['edges'] if e['from'] == sm['root']]
edges.sort(key=lambda e: -float(e['prob']))
preload, seen = [], set()
for c in [sm['root']] + [e['to'] for e in edges[:2]]:
    if c in clips and c not in seen:
        seen.add(c)
        preload.append(c)

out = {
    'format': 'xiaokeqing.kurisu.video-manifest.v1',
    'tier': vm.get('tier'),
    'generatedBy': '_dev/build_video_manifest.py',
    'source': 'video-assets/manifest-video.json（2026-10-15 自检 40/40 过）+ static/kurisu/statemachine.json',
    'note': ('frameIntervalMs 来自 statemachine（播放语义）；容器 60fps 的 durationMs 不是帧间隔，'
             '渲染器按 frameIndex 逐帧画。解码失败/404 ⇒ 逐级降级 video→图集→poster。'),
    'root': sm['root'],
    'preload': preload,
    'clipCount': len(clips),
    'totalBytes': {'webm': sum(c['bytes']['webm'] for c in clips.values()),
                   'poster': sum(c['bytes']['poster'] for c in clips.values())},
    'clips': clips,
}
out['totalBytes']['all'] = out['totalBytes']['webm'] + out['totalBytes']['poster']

json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)

print('写入：%s' % OUT)
print('  clip 数        : %d' % out['clipCount'])
print('  webm 字节      : %d' % out['totalBytes']['webm'])
print('  poster 字节    : %d' % out['totalBytes']['poster'])
print('  合计           : %d' % out['totalBytes']['all'])
print('  首屏预载集     : %s' % ','.join(out['preload']))
print('  清单自身字节   : %d' % os.path.getsize(OUT))
for w in warn:
    print('  [跳过] %s' % w)
print('  逐剪辑帧数已与 statemachine.json 全等校验通过 ✓')
