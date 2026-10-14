# -*- coding: utf-8 -*-
"""P0-④ 口型两层的**离线**数据与素材（闭嘴补丁 + 闭嘴源帧截块 + 逐帧锚点）

依据（都是源码级，见 docs/amadeus-research/HOW-IT-WORKS.md §2.6）：
  · 坐标系 = 帧像素、**原点在帧中心**、+y 向下；嘴部框 width×height 以 (cx,cy) 为中心
    → 帧左上角系 = (frameW/2 + cx, frameH/2 + cy)   ← 本机已人工核对（_tmp/anchor_check 里
      speaking_loop1 的 A_centre 框正好落在嘴上，标注 (398,311) = (382+15.5, 514-203)）
  · 遮罩椭圆（amplitude=0.75 的静音值）：半宽 = width/2 * 1.8，半高 = height/2 * (1.0+1.5*0.75)
    → speaking_loop1: 61.2 × 38.25 帧像素
  · 补丁与整帧的对齐：`overlay.x = anchor.cx - sourceAnchor.cx`（只平移，不缩放，alpha=1）
  · 可见性：`!speaking || mouthValue <= 0.08`
  · 闭嘴源帧以 `runtime_manifest.mouthOverlays[label][0]` 为准（**不用 argmin(openness)**）

产出（进仓库）：
  static/kurisu/mouth/<label>.patch.webp        34×18 帧像素的"嘴部小补丁"（我自己按锚点框裁的）
  static/kurisu/mouth/<label>.closedRegion.webp 74×52 帧像素的闭嘴源帧截块（椭圆 61×38 完全落在里面）
  static/kurisu/mouth/<label>.json              逐帧锚点 cx/cy + 源帧信息 + 椭圆尺寸
产出（不进仓库，只作对照与验收）：_dev/mouth-verify.json、_shots/mouth-compare-a.png / -b.png / -ab.png
用法：python _dev/build_mouth_data.py
"""
import json
import os
import shutil

from PIL import Image, ImageChops, ImageDraw

REPO = r'F:\7AAA\AI\blog'
SRC = r'E:\DeepSeek1\work\_kurisu-full'
PNG = os.path.join(SRC, '_tmp', 'png')
ATLAS = os.path.join(SRC, 'web', 'atlas')
CFG = os.path.join(SRC, 'meta_json', 'spriteforge_mouth_config.json')
RM = os.path.join(SRC, 'meta_json', 'runtime_manifest.json')
OUT = os.path.join(REPO, 'static', 'kurisu', 'mouth')
VERIFY = os.path.join(REPO, '_dev', 'mouth-verify.json')

FRAME_W, FRAME_H = 764, 1028
PATCH_BOX = (34, 18)
REGION = (74, 52)
AMP = 0.75                      # silenceMaskAmplitude
ELL_W = 1.8                     # 上半宽系数
ELL_H = 1.0 + 1.5 * AMP         # 上半高系数 = 2.125


def load_cfg():
    cfg = json.load(open(CFG, encoding='utf-8'))
    rm = json.load(open(RM, encoding='utf-8'))
    return cfg, rm


def source_of(path):
    """textures/<clip>/loop/kurisu_<something><NNNN>.ktx2 → (clip, 帧下标 0 基)"""
    parts = path.replace('\\', '/').split('/')
    clip = parts[1]
    stem = parts[-1].rsplit('.', 1)[0]
    num = ''.join(ch for ch in stem if ch.isdigit())
    idx = int(num) - 1 if num else 0
    return clip, idx


def frame_image(clip, idx):
    """优先用全分辨率 PNG；没有就退回 web/atlas 的 268×360 图集并放大（记进 verify 里）"""
    p = os.path.join(PNG, '%s__%05d.png' % (clip, idx))
    if os.path.exists(p):
        return Image.open(p).convert('RGBA'), 'png-fullres'
    meta = json.load(open(os.path.join(SRC, 'web', 'meta', clip + '.json'), encoding='utf-8'))
    page = meta['atlas_pages'][0]
    ap = os.path.join(ATLAS, page['file'])
    with Image.open(ap) as im:
        cols = page['cols']
        tw, th = page['tile_w'], page['tile_h']
        local = idx - (page['first_frame'] - 1)
        tile = im.convert('RGBA').crop(((local % cols) * tw, (local // cols) * th,
                                        (local % cols) * tw + tw, (local // cols) * th + th))
    return tile.resize((FRAME_W, FRAME_H), Image.LANCZOS), 'atlas-%dx%d-upscaled' % (tw, th)


def box_at(cx, cy, w, h):
    """帧左上角系里的框（左, 上, 右, 下）"""
    mx = FRAME_W / 2.0 + cx
    my = FRAME_H / 2.0 + cy
    return (int(round(mx - w / 2.0)), int(round(my - h / 2.0)),
            int(round(mx + w / 2.0)), int(round(my + h / 2.0)))


def ellipse_mask(size, cx, cy, w, h):
    m = Image.new('L', size, 0)
    d = ImageDraw.Draw(m)
    mx = FRAME_W / 2.0 + cx
    my = FRAME_H / 2.0 + cy
    wHalf = max(1.0, w) / 2.0 * ELL_W
    hHalf = max(1.0, h) / 2.0 * ELL_H
    d.ellipse((mx - wHalf, my - hHalf, mx + wHalf, my + hHalf), fill=255)
    return m


def ncc(a, b, box):
    ra, rb = a.crop(box), b.crop(box)
    da, db = list(ra.convert('L').getdata()), list(rb.convert('L').getdata())
    n = len(da)
    ma, mb = sum(da) / n, sum(db) / n
    va = sum((x - ma) ** 2 for x in da)
    vb = sum((x - mb) ** 2 for x in db)
    if va <= 0 or vb <= 0:
        return 1.0 if va == vb else 0.0
    cov = sum((da[i] - ma) * (db[i] - mb) for i in range(n))
    return cov / (va ** 0.5 * vb ** 0.5)


def mean_abs_diff(a, b, box):
    d = ImageChops.difference(a.crop(box).convert('L'), b.crop(box).convert('L'))
    hist = d.histogram()
    return sum(i * c for i, c in enumerate(hist)) / float(sum(hist))


def main():
    cfg, rm = load_cfg()
    overlays = rm['mouthOverlays']
    os.makedirs(OUT, exist_ok=True)
    report = {'labels': {}, 'checked': 0, 'note': ''}
    rows = []
    for label, paths in overlays.items():
        prof = cfg['profiles'].get(label)
        if not prof:
            report['labels'][label] = {'ok': False, 'why': 'profile 缺失'}
            continue
        src_clip, src_idx = source_of(paths[0])
        own = cfg['profiles'][label]
        box_w = float(own.get('width') or PATCH_BOX[0])
        box_h = float(own.get('height') or PATCH_BOX[1])
        ov = own.get('runtime_overlay_anchor') or {'cx': own['cx'], 'cy': own['cy']}
        ax, ay = float(ov['cx']), float(ov['cy'])
        track = own.get('anchor_track') or []
        if not track:
            track = [{'cx': ax, 'cy': ay, 'width': box_w, 'height': box_h}] * int(own.get('frames') or 0)

        closed, how = frame_image(src_clip, src_idx)
        pbox = box_at(ax, ay, box_w, box_h)
        rbox = (int(round((pbox[0] + pbox[2]) / 2.0 - REGION[0] / 2.0)),
                int(round((pbox[1] + pbox[3]) / 2.0 - REGION[1] / 2.0)),
                int(round((pbox[0] + pbox[2]) / 2.0 + REGION[0] / 2.0)),
                int(round((pbox[1] + pbox[3]) / 2.0 + REGION[1] / 2.0)))
        patch = closed.crop(pbox)
        region = closed.crop(rbox)
        patch.save(os.path.join(OUT, label + '.patch.webp'), 'WEBP', lossless=True, quality=100)
        region.save(os.path.join(OUT, label + '.closedRegion.webp'), 'WEBP', lossless=True, quality=100)

        # ---- 同帧对照：基础帧 = 该 label 自己剪辑的第 0 帧（与闭嘴源帧同画布）----
        base, base_how = frame_image(label if label in rm.get('clips', {}) else src_clip, 0)
        cur = track[0] if track else {'cx': ax, 'cy': ay, 'width': box_w, 'height': box_h}
        dx, dy = float(cur['cx']) - ax, float(cur['cy']) - ay
        ix, iy = int(round(dx)), int(round(dy))   # PIL 只能整数位移；运行时 canvas 用浮点，更准
        # 方案 A：闭嘴源帧整帧 + 椭圆遮罩（上游原算法）
        full = Image.new('RGBA', (FRAME_W, FRAME_H), (0, 0, 0, 0))
        full.paste(closed, (ix, iy))
        mask = ellipse_mask((FRAME_W, FRAME_H), float(cur['cx']), float(cur['cy']), box_w, box_h)
        a = base.copy()
        a.paste(full, (0, 0), Image.composite(full.split()[3], Image.new('L', (FRAME_W, FRAME_H), 0), mask))
        # 方案 A′：闭嘴源帧的 74×52 截块 + 同一条椭圆遮罩（椭圆完全落在截块内 → 与 A 等价）
        #   ★ 位置只能由【源框 + 同一个 delta】推出：用 cur 重新算框再位移会多一次取整，
        #     在 4 个"借别的剪辑的闭嘴帧"的 label 上会错 1px（实测 edge diff 最大 120）。
        reg = Image.new('RGBA', (FRAME_W, FRAME_H), (0, 0, 0, 0))
        reg.paste(region, (rbox[0] + ix, rbox[1] + iy))
        a2 = base.copy()
        a2.paste(reg, (0, 0), Image.composite(reg.split()[3], Image.new('L', (FRAME_W, FRAME_H), 0), mask))
        d = ImageChops.difference(a.convert('RGB'), a2.convert('RGB')).convert('L')
        dpix, mpix = list(d.getdata()), list(mask.getdata())
        inside = [dpix[i] for i in range(len(dpix)) if mpix[i] > 0]
        outside = [dpix[i] for i in range(len(dpix)) if mpix[i] == 0]
        diff_a = d.getbbox()
        # 方案 B：嘴部小补丁（按该 profile 自己的框裁、平移后贴在同一条椭圆中心上）
        pb = box_at(float(cur['cx']), float(cur['cy']), box_w, box_h)
        b = base.copy()
        b.paste(patch, (pb[0], pb[1]), patch)
        ncc_ab = ncc(a, b, pb)
        mad_ab = mean_abs_diff(a, b, pb)
        ncc_a2b = ncc(a2, b, pb)

        anchor_delta_max = 0.0
        for t in track[:400]:
            anchor_delta_max = max(anchor_delta_max,
                                   abs(float(t['cx']) - ax), abs(float(t['cy']) - ay))
        report['labels'][label] = {
            'ok': True, 'patchSource': how, 'baseSource': base_how,
            'sourceClip': src_clip, 'sourceFrame': src_idx,
            'sourceAnchor': [ax, ay], 'box': [box_w, box_h],
            'ellipse': [round(box_w * ELL_W, 2), round(box_h * ELL_H, 2)],
            'frames': len(track), 'anchorDeltaMax': round(anchor_delta_max, 2),
            'patchBox': list(pb),
            'A_vs_Aregion_identical': diff_a is None,
            'A_vs_Aregion': {
                'diffBBox': list(diff_a) if diff_a else None,
                'maxDiffInsideEllipse': max(inside) if inside else 0,
                'pixelsInsideEllipseOver2': sum(1 for v in inside if v > 2),
                'maxDiffOutsideEllipse': max(outside) if outside else 0,
                'ellipsePixels': len(inside),
            },
            'A_vs_B_ncc': round(ncc_ab, 5), 'A_vs_B_meanAbsDiff': round(mad_ab, 3),
            'Aregion_vs_B_ncc': round(ncc_a2b, 5),
            'anchorCheckUrl': '_tmp/anchor_check/%s_full_marked.png' % label,
        }
        report['checked'] += 1
        rows.append((label, src_clip, src_idx, box_w, box_h, len(track),
                     round(anchor_delta_max, 1), round(ncc_ab, 4), round(mad_ab, 2)))

    # 逐帧锚点写进 JSON（只留 cx/cy，两数组；宽度/高度按 profile 默认值，缺失就兜底）
    for label in overlays:
        if not report['labels'].get(label, {}).get('ok'):
            continue
        prof = cfg['profiles'][label]
        track = prof.get('anchor_track') or []
        data = {
            'label': label,
            'frames': len(track),
            'sourceClip': report['labels'][label]['sourceClip'],
            'sourceFrame': report['labels'][label]['sourceFrame'],
            'sourceAnchor': report['labels'][label]['sourceAnchor'],
            'box': report['labels'][label]['box'],
            'ellipse': report['labels'][label]['ellipse'],
            'maskAmplitude': AMP,
            'silenceThreshold': 0.08,
            'borrowedSource': report['labels'][label]['sourceClip'] != label,
            # 默认变体：自己的闭嘴帧 → 小补丁（等价且省一张图）；
            # 借别的剪辑的帧 → 原方案（整帧截块 + 椭圆遮罩）——因为借来的帧肤色/光照与基础帧
            # 不完全一样，补丁的**矩形硬边**看得出来（实测 shy_speaking1/2、surprise_speaking、
            # angry_speaking 这 4 个），椭圆遮罩把接缝推得离嘴更远、观感更好。
            # 数字依据见 _shots/mouth-compare.json。
            'preferredVariant': ('patch' if report['labels'][label]['sourceClip'] == label else 'frame'),
            'patch': 'kurisu/mouth/%s.patch.webp' % label,
            'closedRegion': 'kurisu/mouth/%s.closedRegion.webp' % label,
            'anchorTrack': [[round(float(t['cx']), 2), round(float(t['cy']), 2)] for t in track],
            'note': 'anchorTrack[i] 是第 i 帧的嘴部框中心（帧中心坐标系，+y 向下）；'
                    '对齐规则照抄上游：patch.x = cur.cx - sourceAnchor.cx（只平移不缩放）。'
                    '闭嘴源帧以 runtime_manifest.mouthOverlays[label][0] 为准，不用 argmin(openness)。',
        }
        json.dump(data, open(os.path.join(OUT, label + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False)
    json.dump(report, open(VERIFY, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('| label | 源剪辑 | 源帧 | 框 | 帧数 | 锚点最大位移 | A vs B NCC | A vs B 平均差 |')
    print('|---|---|---:|---|---:|---:|---:|---:|')
    for r in rows:
        print('| `%s` | %s | %d | %.0fx%.0f | %d | %.1f | %.4f | %.2f |' % r)
    print()
    print('共 %d 个 label；A（整帧+椭圆）与 A′（截块+椭圆）是否逐像素相同：%s'
          % (report['checked'],
             all(v.get('A_vs_Aregion_identical') for v in report['labels'].values() if v.get('ok'))))
    print('产出 →', OUT, '；对照报告 →', VERIFY)


if __name__ == '__main__':
    main()
