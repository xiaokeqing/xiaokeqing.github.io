# -*- coding: utf-8 -*-
"""T18 素材产线 · 把**任意生成结果**对齐到既有规格（764×1028 / 8·17·21ms / 透明 alpha / 既有锚点）

它解决的问题（对应角色能力深化方案 §6.2 段二 a）：
  生成出来的一段素材（图序 / 单图 / 一段视频抽的帧）尺寸、构图、可见大小都跟
  已发布素材对不上 ⇒ 直接进状态机会"落位不对、忽大忽小、锚点漂" ⇒ 等于白产 ✗
  本脚本把几何**一次性**算好（同一变换套用到整段，不许逐帧各自缩放 ✗），
  输出画布规格的 RGBA 帧序 + 逐帧时长 + （可选）图集 + （可选）透明 WebM。

★ 锚点口径 = **上游 SpriteForge 的定义**（headTopY / headCenterX / area），已复算验证：
     idle f0        上游 20 / 387.82 → 本库 20 / 387.82
     trans_smile 末 上游 21 / 385.58 → 本库 21 / 385.66
     closed_eye 末  上游 24 / 387.14 → 本库 24 / 387.21
  目标锚点来源（`--anchor-from`）三选一：
     clip:<已发布剪辑名>  ← 把新素材对到那个剪辑的实测锚点上（**最常用**：补同一姿态家族的片段）
     family:front|side|emotion|closed  ← 对到定妆集里该族的锚点中位数
     anchors:<tools/refs/kurisu-anchors.json> 的全局共识（headTopY 21 / headCenterX 387.7）

★ 三条不许省的纪律（都来自上游 invariant，不是我们自己拍的）：
   ① 一段素材**只用一套变换**（帧 0 定标 → 全段套用），否则会看到"呼吸式缩放"✗
   ② 输出必须**零填充编号**（0000.png…），因为上游与我们按文件名字典序排帧
   ③ 逐帧时长来自**目标剪辑规格**（`frameIntervalMs`），**不拿容器 fps 当间隔** ✗
      （现有视频容器是 60fps，真实播放语义在 statemachine 的 8/17/21ms）

用法（产物默认落仓库外 E:\\DeepSeek1\\work\\_asset-out\\<name>，不往仓库里塞大文件 ✓）：
  # 对到某个已发布剪辑的锚点与时长，出帧序 + 图集 + 透明 WebM
  python tools/asset-align.py --in E:\\gen\\coffee_frames --name coffee --anchor-from clip:idle ^
        --interval 17 --loop-mode loop --sheet --webm
  # 单图（新姿态静帧）→ 只出画布帧 + 报告
  python tools/asset-align.py --in pose.png --name new_pose --anchor-from family:front --interval 17
  # 只看不改：打印会怎么对齐
  python tools/asset-align.py --in E:\\gen\\x --name x --anchor-from clip:idle --dry-run

依赖：numpy + Pillow（图集）；ffmpeg 仅在 `--webm` 时需要。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

import asset_common as ac

DEFAULT_OUT_ROOT = r'E:\DeepSeek1\work\_asset-out'
FFMPEG_DEFAULT = r'E:\DeepSeek1\work\_kurisu-017\video-pipeline\tools\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe'
IMG_EXT = ac.IMG_EXT
collect_inputs = ac.collect_inputs
warn_padding = ac.warn_padding

# 上游 QA 口径里可以直接借用的两条（docs/production.md §QA）
BROKEN_FRAME_AREA_REL = 0.12     # 相邻帧可见面积变化 > 12% ⇒ 断帧
ANCHOR_DRIFT_PX = 3.0            # 头部锚点跨帧漂移 > 3px ⇒ 抖动（与静帧容差同值）


# ------------------------------------------------------------------ 帧输入（实现见 asset_common：--in 展开 + 零填充告警）


# ------------------------------------------------------------------ 目标锚点

def load_refset(family=None):
    if not os.path.isfile(ac.REFSET_JSON):
        raise FileNotFoundError('还没有定妆集，先跑 python tools/asset-refset.py build')
    d = ac.load_json(ac.REFSET_JSON)
    refs = d['refs']
    if family:
        refs = [r for r in refs if r['family'] == family]
        if not refs:
            raise KeyError('定妆集里没有族 %s' % family)
    return d, refs


def resolve_target(args):
    """返回 (target dict, 说明文本)。"""
    canvas = ac.CANVAS
    if args.canvas:
        w, h = args.canvas.lower().split('x')
        canvas = (int(w), int(h))
    src = args.anchor_from or ('clip:' + args.target_clip if args.target_clip else 'anchors')
    if src.startswith('clip:'):
        clip = src.split(':', 1)[1]
        node = ac.nodes_by_clip().get(clip)
        if node is None:
            raise KeyError('剪辑不在 statemachine.json：%s' % clip)
        canvas = ac.canvas_of(node)
        idxs = sorted(set([0, node['frames'] // 2, node['frames'] - 1]))
        hs = []
        for i in idxs:
            img = ac.atlas_frame(node, i, tier='medium')
            a = np.asarray(img, dtype=np.float64)[:, :, 3]
            hh = ac.head_anchors(a, canvas[1])
            if hh:
                hs.append(hh)
        med = lambda k: float(np.median([x[k] for x in hs]))
        area = int(np.median([x['area'] for x in hs]))
        bbs = [x['bbox'] for x in hs if x['bbox']]
        vb_w = float(np.median([b[2] - b[0] for b in bbs])) if bbs else None
        vb_h = float(np.median([b[3] - b[1] for b in bbs])) if bbs else None
        return ({
            'source': 'clip:' + clip,
            'canvas': list(canvas),
            'headTopY': med('headTopY'),
            'headCenterX': med('headCenterX'),
            'area': area,
            'visibleWidthPx': vb_w,
            'visibleHeightPx': vb_h,
            'probedFrames': idxs,
            'note': '已发布剪辑 %s 的实测锚点（%d 个采样帧中位数）' % (clip, len(idxs)),
        }, 'clip:%s' % clip)
    if src.startswith('family:'):
        fam = src.split(':', 1)[1]
        d, refs = load_refset(fam)
        ht = float(np.median([r['anchorsCanvas']['headTopY'] for r in refs]))
        hc = float(np.median([r['anchorsCanvas']['headCenterX'] for r in refs]))
        area = int(np.median([r['anchorsCanvas']['area'] for r in refs]))
        return ({
            'source': 'family:' + fam, 'canvas': list(ac.CANVAS),
            'headTopY': ht, 'headCenterX': hc, 'area': area,
            'visibleWidthPx': None, 'visibleHeightPx': None,
            'memberIds': [r['id'] for r in refs],
            'note': '定妆集 %s 族 %d 张的锚点中位数' % (fam, len(refs)),
        }, 'family:%s' % fam)
    if src.startswith('anchors') or args.anchor_from in (None, ''):
        if os.path.isfile(ac.ANCHORS_JSON):
            d = ac.load_json(ac.ANCHORS_JSON)
            c = d['consensus764']
        else:
            refd, refs = load_refset()
            c = {'headTopY': float(np.median([r['anchorsCanvas']['headTopY'] for r in refs])),
                 'headCenterX': float(np.median([r['anchorsCanvas']['headCenterX'] for r in refs])),
                 'area': int(np.median([r['anchorsCanvas']['area'] for r in refs]))}
        return ({
            'source': 'anchors-consensus', 'canvas': list(ac.CANVAS),
            'headTopY': float(c['headTopY']), 'headCenterX': float(c['headCenterX']),
            'area': int(c['area']),
            'visibleWidthPx': c.get('visibleWidthPx'), 'visibleHeightPx': c.get('visibleHeightPx'),
            'note': '38 个已发布剪辑的全局共识锚点（见 tools/refs/kurisu-anchors.json）',
        }, 'anchors-consensus')
    raise ValueError('不认识的 --anchor-from：%s' % src)


# ------------------------------------------------------------------ 对齐

def analyse_frames(paths):
    """逐帧实测：尺寸一致性 + alpha 外框 + 头部锚点。同一尺寸是硬要求。"""
    sizes = set()
    bboxes, anchors, areas = [], [], []
    for p in paths:
        im = ac.load_rgba(p)
        sizes.add(im.size)
        a = np.asarray(im, dtype=np.float64)[:, :, 3]
        bb = ac.alpha_bbox(a, 8)
        hh = ac.head_anchors(a, im.size[1])
        bboxes.append(bb)
        anchors.append(hh)
        areas.append(int((a > 128).sum()))
    if len(sizes) != 1:
        raise ValueError('帧尺寸不一致：%s ⇒ 拒绝处理（同一段素材必须同尺寸）✗' % sorted(sizes))
    return {'size': sizes.pop(), 'bboxes': bboxes, 'anchors': anchors, 'areas128': areas}


def union_bbox(bboxes):
    got = [b for b in bboxes if b]
    if not got:
        return None
    return (min(b[0] for b in got), min(b[1] for b in got),
            max(b[2] for b in got), max(b[3] for b in got))


def compute_transform(info, target, args):
    """算**唯一一套**变换（s, dx, dy）：先定标，再平移。返回 dict。"""
    bboxes = info['bboxes']
    anchors = [a for a in info['anchors'] if a]
    if not anchors:
        raise RuntimeError('所有帧都是全透明（alpha>128 无像素）⇒ 无法定标 ✗')
    src_bb = union_bbox(bboxes)
    src_top = float(np.median([a['headTopY'] for a in anchors]))
    src_cx = float(np.median([a['headCenterX'] for a in anchors]))
    note = []
    s = 1.0
    if args.fit in ('canvas', 'auto'):
        # ★ 默认口径：**源帧的整幅矩形 == 画布矩形**
        #   依据：生成服务（Wan/Seedance…）收到的是我们给的首尾帧（画布尺寸），
        #   返回的是一段等比缩放后的视频 ⇒ 它的整幅矩形就是画布矩形。
        #   本机验证：268×360 的已发布视频首帧 → s=canvas_h/src_h=2.8556，得到可见高 1011 px、
        #   可见宽 554 px，与目标剪辑实测的 1005 / 550 px 差 0.6%（见 align-report.json）。
        sx = target['canvas'][0] / float(info['size'][0])
        sy = target['canvas'][1] / float(info['size'][1])
        if abs(sx / sy - 1.0) > 0.005:
            s = min(sx, sy)
            note.append('源宽高比 %dx%d 与画布 %dx%d 差 %.2f%% ⇒ 按 min(%.4f, %.4f) 缩放以完整放入；'
                        '横向余量由锚点平移吸收'
                        % (info['size'][0], info['size'][1], target['canvas'][0], target['canvas'][1],
                           100 * abs(sx / sy - 1), sx, sy))
        else:
            s = sy
    elif args.fit == 'h':
        if not target.get('visibleHeightPx') or not src_bb:
            raise ValueError('--fit h 需要目标与来源都有可见外框')
        s = target['visibleHeightPx'] / float(src_bb[3] - src_bb[1])
    elif args.fit == 'w':
        if not target.get('visibleWidthPx') or not src_bb:
            raise ValueError('--fit w 需要目标与来源都有可见外框')
        s = target['visibleWidthPx'] / float(src_bb[2] - src_bb[0])
    elif args.fit == 'area':
        src_area = float(np.median(info['areas128']))
        s = float(np.sqrt(target['area'] / src_area)) if src_area > 0 else 1.0
    elif args.fit not in ('head', 'none'):
        raise ValueError('不认识的 --fit：%s' % args.fit)
    if args.scale_min and s < args.scale_min:
        note.append('scale %.4f 被 --scale-min %.4f 夹住' % (s, args.scale_min))
        s = args.scale_min
    if args.scale_max and s > args.scale_max:
        note.append('scale %.4f 被 --scale-max %.4f 夹住' % (s, args.scale_max))
        s = args.scale_max
    tcx = float(target['headCenterX'])
    tty = float(target['headTopY'])
    if args.anchor_mode == 'head':
        dx = tcx - s * src_cx
        dy = tty - s * src_top
    elif args.anchor_mode == 'bbox':
        if not src_bb:
            raise ValueError('--anchor-mode bbox 需要来源有 alpha 外框')
        sx_c = (src_bb[0] + src_bb[2]) / 2.0
        sy_b = float(src_bb[3])
        dx = tcx - s * sx_c
        dy = float(target.get('visibleBottomY') or target['canvas'][1]) - s * sy_b
    elif args.anchor_mode == 'none':
        dx = (target['canvas'][0] - info['size'][0] * s) / 2.0
        dy = (target['canvas'][1] - info['size'][1] * s) / 2.0
    else:
        raise ValueError('不认识的 --anchor-mode：%s' % args.anchor_mode)
    if args.margin_px:
        dx += args.margin_px
    return {
        'scale': s, 'dx': dx, 'dy': dy,
        'srcCanvasSize': [info['size'][0], info['size'][1]],
        'srcUnionBBoxThr8': list(src_bb) if src_bb else None,
        'srcHeadTopYMedian': src_top, 'srcHeadCenterXMedian': src_cx,
        'anchorMode': args.anchor_mode, 'fit': args.fit, 'notes': note,
    }


def apply_transform(im, tr, canvas, margin_px=0):
    """缩放 + 平移。两步重采样：**缩放用 LANCZOS**（PIL 的 AFFINE 不支持 LANCZOS），
    平移用 BICUBIC 的 1:1 仿射（只在有亚像素余量时才动）。"""
    w = canvas[0] + 2 * margin_px
    h = canvas[1]
    s = tr['scale']
    if s <= 0:
        raise ValueError('scale 必须 > 0')
    tw = max(1, int(round(im.size[0] * s)))
    th = max(1, int(round(im.size[1] * s)))
    scaled = im.resize((tw, th), Image.LANCZOS) if (tw, th) != im.size else im
    if abs(tr['dx'] - round(tr['dx'])) < 1e-6 and abs(tr['dy'] - round(tr['dy'])) < 1e-6:
        out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        out.paste(scaled, (int(round(tr['dx'])), int(round(tr['dy']))))
        return out
    coeff = (1.0, 0.0, -tr['dx'], 0.0, 1.0, -tr['dy'])
    return scaled.transform((w, h), Image.AFFINE, coeff, resample=Image.BICUBIC)


def edge_guard(im, px):
    """清掉贴着**左右上**三边的半透明像素（上游 edgeGuardPx 的等价物；底边是允许的 cutEdge）。"""
    if not px:
        return im, 0
    a = np.asarray(im).copy()
    cleared = 0
    for sl in (np.s_[:, :px], np.s_[:, -px:], np.s_[:px, :]):
        sub = a[sl]
        m = sub[:, :, 3] > 0
        cleared += int(m.sum())
        sub[:, :, 3] = np.where(m, 0, sub[:, :, 3])
    return Image.fromarray(a, 'RGBA'), cleared


# ------------------------------------------------------------------ QA

def qa_frames(frames, target, canvas, margin_px):
    """逐帧锚点 + 面积 + 断帧 + 贴边（口径与上游 QA 表同构）。"""
    cw = canvas[0] + 2 * margin_px
    ch = canvas[1]
    per = []
    prev_area = None
    for i, im in enumerate(frames):
        a = np.asarray(im, dtype=np.float64)[:, :, 3]
        hh = ac.head_anchors(a, ch)
        area = int((a > 128).sum())
        rec = {'frame': i, 'area': area}
        if hh:
            rec['headTopY'] = round(hh['headTopY'], 2)
            rec['headCenterX'] = round(hh['headCenterX'] - margin_px, 2)
            rec['headTopDeltaPx'] = round(hh['headTopY'] - target['headTopY'], 3)
            rec['headCenterDeltaPx'] = round((hh['headCenterX'] - margin_px) - target['headCenterX'], 3)
        else:
            rec['headTopDeltaPx'] = None
            rec['headCenterDeltaPx'] = None
        rec['areaRatio'] = round(area / target['area'], 5) if target.get('area') else None
        # 贴边检查：底边允许（cutEdge=bottom），左右上三边不许碰
        touch = []
        if (a[0] > 128).any():
            touch.append('top')
        if (a[:, 0] > 128).any():
            touch.append('left')
        if (a[:, -1] > 128).any():
            touch.append('right')
        if (a[-1] > 128).any():
            touch.append('bottom')
        rec['edgesTouched'] = touch
        if prev_area is not None and prev_area > 0:
            rec['areaChangeRel'] = round(abs(area - prev_area) / prev_area, 5)
        prev_area = area
        per.append(rec)
    bad_top = [r['frame'] for r in per if r.get('edgesTouched') and
               any(e in ('top', 'left', 'right') for e in r['edgesTouched'])]
    drift = None
    tops = [r['headTopY'] for r in per if r.get('headTopY') is not None]
    cxs = [r.get('headCenterX') for r in per if r.get('headCenterX') is not None]
    if tops:
        drift = {'headTopRangePx': round(max(tops) - min(tops), 2),
                 'headCenterRangePx': round(max(cxs) - min(cxs), 2)}
    broken = [r['frame'] for r in per if r.get('areaChangeRel') is not None
              and r['areaChangeRel'] > BROKEN_FRAME_AREA_REL]
    anchor_bad = [r['frame'] for r in per
                  if r.get('headTopDeltaPx') is not None
                  and (abs(r['headTopDeltaPx']) > ANCHOR_TOL_VIOLATION or abs(r['headCenterDeltaPx']) > ANCHOR_TOL_VIOLATION)]
    return {
        'frames': per,
        'judge': {
            'anchorTolPx': ANCHOR_TOL_VIOLATION,
            'areaTolRel': ac.AREA_TOL_REL,
            'cutEdgeAllowed': 'bottom',
            'brokenFrameAreaRel': BROKEN_FRAME_AREA_REL,
            'anchorDriftTolPx': ANCHOR_DRIFT_PX,
        },
        'fail': {
            'anchorOutOfTolFrames': anchor_bad,
            'forbiddenEdgeTouchedFrames': bad_top,
            'brokenFrameCandidates': broken,
        },
        'pass_anchor': not anchor_bad,
        'pass_edges': not bad_top,
        'headAnchorDrift': drift,
        'pass_drift': (drift is None) or (drift['headTopRangePx'] <= ANCHOR_DRIFT_PX
                                          and drift['headCenterRangePx'] <= ANCHOR_DRIFT_PX),
    }


ANCHOR_TOL_VIOLATION = 3.0     # 上游静帧容差（headTop / headCenter）


# ------------------------------------------------------------------ 输出

def write_frames(frames, out_dir):
    d = os.path.join(out_dir, 'frames')
    os.makedirs(d, exist_ok=True)
    for old in os.listdir(d):
        p = os.path.join(d, old)
        if os.path.isfile(p):
            os.remove(p)
    for i, im in enumerate(frames):
        im.save(os.path.join(d, '%04d.png' % i), 'PNG', optimize=True)
    return d


def build_atlas(frames, out_dir, name, tier='medium', want_cols=8, page_frames=512):
    """按 statemachine 的页结构出图集（多页命名 X.atlas.webp / X.atlas.p01.webp…）。"""
    cw, ch = frames[0].size
    tw, th = ac.tier_tile_size(tier, (cw, ch))
    plates = []
    pages = []
    n = len(frames)
    per_page = min(n, max(1, page_frames))
    n_pages = int(np.ceil(n / per_page))
    sub = os.path.join(out_dir, 'atlas')
    os.makedirs(sub, exist_ok=True)
    first = 1
    for pi in range(n_pages):
        chunk = frames[pi * per_page:(pi + 1) * per_page]
        cols = min(want_cols, len(chunk))
        rows = int(np.ceil(len(chunk) / cols))
        page_im = Image.new('RGBA', (cols * tw, rows * th), (0, 0, 0, 0))
        for k, im in enumerate(chunk):
            tile = im.resize((tw, th), Image.LANCZOS)
            page_im.paste(tile, ((k % cols) * tw, (k // cols) * th))
        fn = '%s.atlas.webp' % name if pi == 0 else '%s.atlas.p%02d.webp' % (name, pi)
        fp = os.path.join(sub, fn)
        page_im.save(fp, 'WEBP', quality=80, method=5)
        pages.append({
            'url': None, 'file': fn,
            'tile_w': tw, 'tile_h': th, 'cols': cols, 'rows': rows,
            'frames': len(chunk), 'first_frame': first, 'last_frame': first + len(chunk) - 1,
            'pixels': [cols * tw, rows * th], 'bytes': os.path.getsize(fp),
        })
        plates.append(fp)
        first += len(chunk)
    return {'tier': tier, 'dir': sub, 'files': plates, 'pages': pages,
            'bytes': sum(p['bytes'] for p in pages)}


def build_webm(frames, out_dir, name, interval_ms, ffmpeg, size=None, fps=60.0, crf=32):
    """透明 VP9+alpha。★ 帧率默认 **60**（沿用既有 video 管线的容器口径），
    真实播放间隔看 frameIntervalMs —— 渲染器按帧号取帧，不按容器时间 ✗。"""
    tmp = os.path.join(out_dir, '_webm_src')
    os.makedirs(tmp, exist_ok=True)
    for old in os.listdir(tmp):
        p = os.path.join(tmp, old)
        if os.path.isfile(p):
            os.remove(p)
    for i, im in enumerate(frames):
        im2 = im if (size is None or im.size == size) else im.resize(size, Image.LANCZOS)
        im2.save(os.path.join(tmp, '%04d.png' % i), 'PNG')
    vdir = os.path.join(out_dir, 'video')
    os.makedirs(vdir, exist_ok=True)
    out = os.path.join(vdir, name + '.webm')
    cmd = [ffmpeg, '-y', '-v', 'error', '-framerate', '%g' % fps,
           '-i', os.path.join(tmp, '%04d.png'),
           '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-auto-alt-ref', '0',
           '-crf', str(crf), '-b:v', '0', '-row-mt', '1', out]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError('ffmpeg 失败：\n%s' % p.stderr.decode('utf-8', 'replace')[-2000:])
    return {'path': out, 'bytes': os.path.getsize(out), 'fps': fps, 'crf': crf,
            'pixFmt': 'yuva420p', 'size': list(size or frames[0].size),
            'note': '容器 %g fps；真实逐帧时长 = frameIntervalMs %d ms（渲染器按帧号取帧）' % (fps, interval_ms)}


# ------------------------------------------------------------------ 主流程

def spec_from_clip(clip):
    node = ac.nodes_by_clip().get(clip)
    if node is None:
        return None
    return {'clip': clip, 'canvas': list(ac.canvas_of(node)),
            'frameIntervalMs': int(node['frameIntervalMs']),
            'loopMode': node['loopMode'], 'reverse': ac.is_reverse(clip),
            'frames': int(node['frames'])}


def main():
    ap = argparse.ArgumentParser(description='T18 素材对齐（任意生成结果 → 764×1028 + 既有锚点 + 逐帧时长）')
    ap.add_argument('--in', dest='src', required=True, help='帧目录 / 单图 / 逗号分隔 / glob')
    ap.add_argument('--name', required=True, help='新剪辑名（决定输出文件名）')
    ap.add_argument('--out', help='输出根目录（默认 %s）' % DEFAULT_OUT_ROOT)
    ap.add_argument('--target-clip', help='沿用该已发布剪辑的规格（画布/时长/循环语义）')
    ap.add_argument('--anchor-from', help='clip:<剪辑> | family:front|side|emotion|closed | anchors')
    ap.add_argument('--interval', type=int, help='逐帧时长 ms（8/17/21；不给则取 --target-clip 的）')
    ap.add_argument('--loop-mode', choices=['loop', 'once_then_hold'], help='循环语义')
    ap.add_argument('--canvas', help='画布 WxH（默认 764x1028）')
    ap.add_argument('--anchor-mode', choices=['head', 'bbox', 'none'], default='head')
    ap.add_argument('--fit', choices=['canvas', 'head', 'h', 'w', 'area', 'none'], default='canvas',
                    help='canvas=源整幅矩形→画布矩形（默认，生成服务返回的等比缩放成品）；'
                         'head=只平移不改大小；h/w/area=按可见高/宽/面积定标')
    ap.add_argument('--scale-min', type=float, default=None)
    ap.add_argument('--scale-max', type=float, default=None)
    ap.add_argument('--margin-px', type=int, default=0, help='左右各加多少透明列（上游 marginPx 等价物）')
    ap.add_argument('--edge-guard', type=int, default=0, help='清掉左右上三边贴边的 alpha 像素')
    ap.add_argument('--sheet', action='store_true', help='出图集 webp + 页描述')
    ap.add_argument('--tier', choices=['medium', 'hi'], default='medium')
    ap.add_argument('--webm', action='store_true', help='出透明 VP9+alpha webm')
    ap.add_argument('--webm-fps', type=float, default=60.0, help='容器帧率（默认 60，沿用既有视频管线）')
    ap.add_argument('--webm-crf', type=int, default=32)
    ap.add_argument('--ffmpeg', default=FFMPEG_DEFAULT)
    ap.add_argument('--durations-file', help='逐帧时长列表 JSON（覆盖 --interval；长度必须等于帧数）')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    paths = collect_inputs(args.src)
    padwarn = warn_padding(paths)
    spec = spec_from_clip(args.target_clip) if args.target_clip else None
    if spec is None and args.target_clip:
        print('警告：--target-clip %s 不在 statemachine.json ⇒ 当成新剪辑处理' % args.target_clip, file=sys.stderr)

    canvas = tuple(spec['canvas']) if spec else ac.CANVAS
    if args.canvas:
        w, h = args.canvas.lower().split('x')
        canvas = (int(w), int(h))
    interval = args.interval if args.interval else (spec['frameIntervalMs'] if spec else None)
    if interval is None:
        print('错误：必须给 --interval（或用 --target-clip 取到规格）', file=sys.stderr)
        return 2
    loop_mode = args.loop_mode or (spec['loopMode'] if spec else 'loop')

    target, target_desc = resolve_target(args)
    print('输入    : %d 帧 ← %s' % (len(paths), args.src))
    if padwarn:
        print('  [警告] %s' % padwarn)
    print('规格    : 画布 %dx%d ｜ 逐帧 %d ms ｜ 循环 %s%s'
          % (canvas[0], canvas[1], interval, loop_mode,
             (' ｜ 沿用 %s' % args.target_clip) if spec else ''))
    print('目标锚点: %s ｜ headTopY %.2f ｜ headCenterX %.2f ｜ area %d'
          % (target_desc, target['headTopY'], target['headCenterX'], target['area']))

    info = analyse_frames(paths)
    tr = compute_transform(info, target, args)
    print('来源    : %dx%d ｜ 并集外框 %s ｜ 头部锚点中位 (%.1f, %.2f)'
          % (info['size'][0], info['size'][1], tr['srcUnionBBoxThr8'], tr['srcHeadTopYMedian'], tr['srcHeadCenterXMedian']))
    print('变换    : scale %.5f ｜ dx %.3f ｜ dy %.3f（**整段一套**）%s'
          % (tr['scale'], tr['dx'], tr['dy'], ('  ' + '; '.join(tr['notes'])) if tr['notes'] else ''))
    if args.dry_run:
        print('--dry-run：不写任何文件。')
        return 0

    out_dir = os.path.join(args.out or DEFAULT_OUT_ROOT, args.name)
    os.makedirs(out_dir, exist_ok=True)

    frames, guarded = [], 0
    for p in paths:
        im = ac.load_rgba(p)
        out = apply_transform(im, tr, canvas, args.margin_px)
        out, c = edge_guard(out, args.edge_guard)
        guarded += c
        frames.append(out)
    qa = qa_frames(frames, target, canvas, args.margin_px)
    fdir = write_frames(frames, out_dir)

    # ---- 逐帧时长（按目标剪辑规格写）
    if args.durations_file:
        durations = ac.load_json(args.durations_file)
        if isinstance(durations, dict):
            durations = durations.get('durationsMs') or durations.get('durations')
        if not isinstance(durations, list) or len(durations) != len(frames):
            print('错误：--durations-file 长度 %s ≠ 帧数 %d' % (
                len(durations) if isinstance(durations, list) else '?', len(frames)), file=sys.stderr)
            return 3
    else:
        durations = [int(interval)] * len(frames)
    dur_path = os.path.join(out_dir, 'frames-durations.json')
    ac.dump_json(dur_path, {
        'format': 'xiaokeqing.kurisu.frame-durations.v1',
        'clip': args.name,
        'frames': len(frames),
        'frameIntervalMs': int(interval),
        'constantInterval': True if args.durations_file is None else (len(set(durations)) == 1),
        'totalMs': int(sum(durations)),
        'durationsMs': durations,
        'note': ('逐帧播放时长。取值口径 = 目标剪辑规格（8 / 17 / 21 ms），'
                 '**不是视频容器的 60fps** ✗（渲染器按帧号取帧）。'),
    })

    sheet = build_atlas(frames, out_dir, args.name, args.tier) if args.sheet else None
    webm = None
    if args.webm:
        wsize = ac.tier_tile_size('hi', canvas) if canvas == ac.CANVAS else None
        webm = build_webm(frames, out_dir, args.name, interval, args.ffmpeg,
                          size=wsize if wsize and wsize != canvas else None, fps=args.webm_fps,
                          crf=args.webm_crf)

    record = {
        'format': 'xiaokeqing.kurisu.new-clip.v1',
        'clip': args.name,
        'builtBy': 'tools/asset-align.py',
        'builtAtFrom': args.src,
        'sourceFrames': len(paths),
        'sourceFrameSize': [info['size'][0], info['size'][1]],
        'sourcePaddingWarning': padwarn,
        'canvas': [canvas[0], canvas[1]],
        'marginPx': int(args.margin_px),
        'outputFrameSize': [canvas[0] + 2 * args.margin_px, canvas[1]],
        'frameIntervalMs': int(interval),
        'loopMode': loop_mode,
        'frames': len(frames),
        'durationsMs': durations,
        'transform': tr,
        'targetAnchor': target,
        'targetAnchorFrom': target_desc,
        'edgeGuardPx': int(args.edge_guard),
        'edgeGuardClearedPixels': guarded,
        'qa': qa,
        'outputs': {
            'framesDir': fdir,
            'durations': dur_path,
            'atlas': ({'tier': sheet['tier'], 'pages': sheet['pages'], 'bytes': sheet['bytes']} if sheet else None),
            'webm': webm,
        },
        'registrationRecord': {
            'note': ('新素材登记表：把这条填进 _dev/build_statemachine_manifest.py 的登记入口即可入库。'
                     '入库动作**不在本脚本**（本脚本只负责"能对齐"这一段）✗'),
            'suggestedNode': {
                'clip': args.name, 'frames': len(frames), 'frameIntervalMs': int(interval),
                'loopMode': loop_mode, 'frame_size': [canvas[0], canvas[1]],
                'atlasDir': 'static/kurisu/%s/' % sheet['tier'] if sheet else None,
            },
        },
        'evidence': {
            'targetAnchorIsMeasured': True,
            'anchorDefinition': 'headTopY/headCenterX/area ＝ 上游 SpriteForge docs/production.md §Character contract 同定义',
        },
    }
    rep = os.path.join(out_dir, 'align-report.json')
    ac.dump_json(rep, record)

    print()
    print('输出    : %s' % out_dir)
    print('  帧序      : %s（%d 张，%s）' % (fdir, len(frames), '%dx%d' % frames[0].size))
    print('  逐帧时长  : %s（%d ms × %d）' % (dur_path, interval, len(frames)))
    if sheet:
        print('  图集      : %s tier=%s ｜ %d 页 ｜ %d B ｜ %s'
              % (sheet['dir'], sheet['tier'], len(sheet['pages']), sheet['bytes'],
                 ', '.join(p['file'] for p in sheet['pages'])))
    if webm:
        print('  WebM      : %s ｜ %d B ｜ %s ｜ 容器 %g fps'
              % (webm['path'], webm['bytes'], webm['pixFmt'], webm['fps']))
    print('  报告      : %s' % rep)
    print()
    print('QA（口径与上游同构）：')
    print('  头部锚点 3px 内 : %s%s' % (qa['pass_anchor'],
          '' if qa['pass_anchor'] else '  超差帧 %s' % qa['fail']['anchorOutOfTolFrames'][:12]))
    print('  只碰底边        : %s%s' % (qa['pass_edges'],
          '' if qa['pass_edges'] else '  碰到上/左/右的帧 %s' % qa['fail']['forbiddenEdgeTouchedFrames'][:12]))
    print('  锚点跨帧漂移    : %s  %s' % (qa['pass_drift'], qa['headAnchorDrift']))
    if qa['fail']['brokenFrameCandidates']:
        print('  断帧嫌疑(面积变化>12%%) : %s' % qa['fail']['brokenFrameCandidates'][:12])
    return 0


if __name__ == '__main__':
    sys.exit(main())
