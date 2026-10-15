# -*- coding: utf-8 -*-
"""T7 前置核验：视频逐帧 vs statemachine 图集（**同一帧号**）的对齐与 alpha 实测

为什么先做这个：接线的整个前提是"video 的第 i 帧 == 图集的第 i 帧"，且 VP9+alpha 在浏览器里
真解得出透明。这两条不成立，后面写多好的渲染器都是错的。所以先用最硬的实测把前提钉住，
数字写进 _shots/video-align.json，接线方案 / 总账只引用它。

输入（都在仓库外，只读）：
  E:\\DeepSeek1\\work\\_kurisu-017\\video-assets\\video\\<clip>.webm
输出（都落仓库外，避免动仓库）：
  E:\\DeepSeek1\\work\\_video-check\\frames\\<clip>.f0000.png / .fNNNN.png ...
  E:\\DeepSeek1\\work\\_video-check\\report.json
仓库内唯一产物：_shots/video-align.json（证据，小文件）

用法：python _dev/check-video-align.py [clip ...]（默认抽 38 个剪辑里的 8 个代表）
全程零第三方库依赖（ffmpeg + Pillow + numpy）。
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

REPO = r'F:\7AAA\AI\blog'
SM = os.path.join(REPO, 'static', 'kurisu', 'statemachine.json')
MEDIUM_MANIFEST = os.path.join(REPO, 'static', 'kurisu', 'manifest.json')
VDIR = r'E:\DeepSeek1\work\_kurisu-017\video-assets\video'
WORK = r'E:\DeepSeek1\work\_video-check'
FFMPEG = r'E:\DeepSeek1\work\_kurisu-017\video-pipeline\tools\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe'
OUT = os.path.join(REPO, '_shots', 'video-align.json')

# 代表剪辑：覆盖 loop / once_then_hold、8ms / 17ms / 21ms 三种单帧时长、单页与多页图集、
# 以及 pad 过的（coded 620x1028, padX=72）与没 pad 的（coded 764x1028）。
DEFAULT = ['idle', 'speaking_trans', 'angry_speaking', 'idle_side_butterfly',
           'closed_eye_trans', 'shy_speaking1', 'trans_smile', 'idle_closed_eye']


def run(cmd):
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError('ffmpeg 失败：%s\n%s' % (' '.join(cmd[:6]), p.stderr.decode('utf-8', 'replace')[-1200:]))
    return p.stdout


def extract(clip, idxs):
    """抽指定帧号 → 一张 RGBA PNG（alpha 也从同一帧解出），返回 {idx: png_path}

    要点：VP9+alpha 的 alpha 存在独立 plane，**必须 `-c:v libvpx-vp9` 强制用 libvpx 解码器**
    才解得出（ffmpeg 自己会提示 "use the libvpx-vp9 decoder to decode it"；native vp9 解码器
    会 ignore WebM alpha side data，alphaextract 报 "Requested planes not available" —— 实测踩过）。
    """
    d = os.path.join(WORK, 'frames')
    os.makedirs(d, exist_ok=True)
    sel = '+'.join('eq(n\\,%d)' % i for i in idxs)
    tpl = os.path.join(d, '%s.%%05d.png' % clip)
    for old in os.listdir(d):
        if old.startswith(clip + '.'):
            os.remove(os.path.join(d, old))
    src = os.path.join(VDIR, clip + '.webm')
    run([FFMPEG, '-y', '-v', 'error', '-c:v', 'libvpx-vp9', '-i', src,
         '-vf', 'select=%s' % sel, '-fps_mode', 'passthrough', '-pix_fmt', 'rgba', tpl])
    files = sorted(f for f in os.listdir(d) if f.startswith(clip + '.'))
    if len(files) != len(idxs):
        raise RuntimeError('%s 抽帧数不符：要 %d，得到 %d' % (clip, len(idxs), len(files)))
    return {i: os.path.join(d, f) for i, f in zip(idxs, files)}


def atlas_tile(node, frame0):
    """frame0 = 0-based 帧号（= statemachine 里的帧序号 - 1）；返回该帧的 RGBA 图（134×180）"""
    f1 = frame0 + 1                      # statemachine 的 first_frame/last_frame 是 1-based
    for p in node['medium']['pages']:
        if p['first_frame'] <= f1 <= p['last_frame']:
            local = f1 - p['first_frame']
            im = Image.open(os.path.join(REPO, 'static', p['url'].replace('/', os.sep))).convert('RGBA')
            cw, ch = p['tile_w'], p['tile_h']
            sx, sy = (local % p['cols']) * cw, (local // p['cols']) * ch
            return im.crop((sx, sy, sx + cw, sy + ch))
    raise RuntimeError('帧 %d 不落在任何页' % f1)


def ncc(a, b):
    a = a.astype(np.float64).ravel()
    b = b.astype(np.float64).ravel()
    a = a - a.mean()
    b = b - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den else float('nan')


def iou(a, b):
    """二值 alpha 的交并比 —— 这才是"同一帧"的判据。
    RGB 逐像素 NCC 比不了两个不同编码的有损产物（video=VP9@2x 降采样、atlas=WebP q=72）：
    实测 idle 同一帧 RGB-NCC 只有 0.97，但二值 IoU 0.9992、剪影质心差 0.01px ⇒ 帧是对的，
    差的只是编码噪声。所以验收口径 = 二值 IoU（阈值 0.96）+ 质心偏移（阈值 1px）。"""
    A, B = a > 0.5, b > 0.5
    u = (A | B).sum()
    return float((A & B).sum() / u) if u else 1.0


def centroid(a, thr=0.5):
    ys, xs = np.nonzero(a > thr)
    if len(xs) == 0:
        return (float('nan'), float('nan'))
    return (float(xs.mean()), float(ys.mean()))


def main():
    clips = sys.argv[1:] or DEFAULT
    sm = json.load(open(SM, encoding='utf-8'))
    nodes = {n['clip']: n for n in sm['nodes']}
    mm = json.load(open(MEDIUM_MANIFEST, encoding='utf-8'))
    mm_clips = ((mm.get('clipsMedium') or {}).get('clips')) or {}
    os.makedirs(WORK, exist_ok=True)
    report = {'format': 'xiaokeqing.kurisu.video-align.v1',
              'method': ('ffmpeg(libvpx-vp9 解码器，native vp9 解不出 alpha) 按**帧号**抽 video 帧 → '
                         '与 statemachine.json 指到的图集瓦片（同帧号）比：'
                         '主判据 = 二值 alpha IoU + 剪影质心偏移；辅助 = alpha MAE / 四角 alpha 采样；'
                         'RGB 逐像素 NCC 仅作参考（video 是 VP9@2x 降采样、atlas 是 WebP q=72，'
                         '两者都是有损产物，跨编码器比 NCC 天生到不了 0.99 —— 实测同一帧只有 0.97，'
                         '但二值 IoU 0.9992、质心差 0.01px）。'),
              'clips': {}}
    for clip in clips:
        node = nodes.get(clip)
        if node is None:
            print('跳过 %s（不在状态机里）' % clip)
            continue
        n = node['frames']
        idxs = sorted(set([0, n // 2, n - 1]))
        # 倒放剪辑（reverse=true）：图集倒放、视频正放 ⇒ 比 video[n-1-i] vs atlas[i]
        rev = bool((mm_clips.get(clip) or {}).get('reverse'))
        vidxs = sorted(set((n - 1 - i) if rev else i for i in idxs))
        got = extract(clip, vidxs)
        rec = {'frames': n, 'frameIntervalMs': node['frameIntervalMs'], 'loopMode': node['loopMode'],
               'reverse': rev, 'tier': 'medium', 'probes': []}
        for i in idxs:
            png = got[(n - 1 - i) if rev else i]
            rgba = Image.open(png).convert('RGBA')
            alpha = rgba.split()[3]
            tile = atlas_tile(node, i)
            small = rgba.resize(tile.size, Image.LANCZOS)
            a = np.asarray(small, dtype=np.float64)
            b = np.asarray(tile, dtype=np.float64)
            # alpha 只比 alpha（上采样到图集尺寸）
            al = np.asarray(alpha.resize(tile.size, Image.BILINEAR), dtype=np.float64) / 255.0
            be = b[:, :, 3] / 255.0
            corners = []
            for cy, cx in ((0, 0), (0, -1), (-1, 0), (-1, -1)):
                corners.append(round(float(al[cy, cx]), 4))
            occ = float((al > 0.5).mean())
            cvx, cvy = centroid(al)
            ctx_, cty = centroid(be)
            rec['probes'].append({
                'frame': i,
                'videoFrame': (n - 1 - i) if rev else i,
                'alphaIoU': round(iou(al, be), 5),                 # ★主判据：同一帧的剪影一致性
                'centroidDxPx': None if cvx != cvx else round(cvx - ctx_, 3),
                'centroidDyPx': None if cvy != cvy else round(cvy - cty, 3),
                'rgbNccAll': round(ncc(a[:, :, :3], b[:, :, :3]), 5),   # 仅参考（跨编码器，不作判据）
                'alphaMae': round(float(np.abs(al - be).mean()), 5),
                'alphaMeanVideo': round(float(al.mean()), 4),
                'alphaMeanAtlas': round(float(be.mean()), 4),
                'cornerAlphaVideo': corners,
                'cornerAlphaAtlas': [round(float(be[cy, cx]), 4) for cy, cx in ((0, 0), (0, -1), (-1, 0), (-1, -1))],
                'opaqueRatioVideo': round(occ, 4),
                'opaqueRatioAtlas': round(float((be > 0.5).mean()), 4),
            })
        report['clips'][clip] = rec
        worst = min(p['alphaIoU'] for p in rec['probes'])
        amae = max(p['alphaMae'] for p in rec['probes'])
        dmax = max(abs(p['centroidDxPx'] or 0) + abs(p['centroidDyPx'] or 0) for p in rec['probes'])
        print('%-24s frames=%-4d iv=%-3d %-15s alphaIoU(最差)=%.4f alphaMAE(最大)=%.5f 质心偏移(最大)=%.2fpx'
              % (clip, n, node['frameIntervalMs'], node['loopMode'], worst, amae, dmax))
    # 汇总阈值判定：主判据 = 二值 alpha IoU ≥ 0.96 且剪影质心偏移 ≤ 1px
    allp = [p for c in report['clips'].values() for p in c['probes']]
    report['summary'] = {
        'judge': '二值 alpha IoU ≥ 0.96 且剪影质心偏移 ≤ 1px（RGB-NCC 仅参考：跨编码器不可作判据）',
        'clips': len(report['clips']),
        'probes': len(allp),
        'alphaIoUMin': round(min(p['alphaIoU'] for p in allp), 5),
        'alphaMaeMax': round(max(p['alphaMae'] for p in allp), 5),
        'centroidOffsetMaxPx': round(max(abs(p['centroidDxPx'] or 0) + abs(p['centroidDyPx'] or 0) for p in allp), 3),
        'cornerAlphaVideoMax': round(max(max(p['cornerAlphaVideo']) for p in allp), 4),
        'rgbNccAllMin': round(min(p['rgbNccAll'] for p in allp), 5),
        'pass_iou_ge_096': all(p['alphaIoU'] >= 0.96 for p in allp),
        'pass_centroid_le_1px': all(abs(p['centroidDxPx'] or 0) + abs(p['centroidDyPx'] or 0) <= 1.0 for p in allp),
        'pass_cornerAlpha_zero': all(max(p['cornerAlphaVideo']) == 0 for p in allp),
    }
    json.dump(report, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    s = report['summary']
    print('\n汇总：%d 剪辑 / %d 帧探针 ｜ 二值 alpha IoU 最小 %.5f ｜ alpha MAE 最大 %.5f'
          % (s['clips'], s['probes'], s['alphaIoUMin'], s['alphaMaeMax']))
    print('      剪影质心偏移最大 %.3f px ｜ 四角 alpha 最大 %.4f（=0 表示边缘真透明）｜ RGB-NCC 最小 %.5f（仅参考）'
          % (s['centroidOffsetMaxPx'], s['cornerAlphaVideoMax'], s['rgbNccAllMin']))
    print('      判定：IoU>=0.96 %s ｜ 质心<=1px %s ｜ 四角全透明 %s'
          % (s['pass_iou_ge_096'], s['pass_centroid_le_1px'], s['pass_cornerAlpha_zero']))
    print('证据 -> %s' % OUT)


if __name__ == '__main__':
    main()
