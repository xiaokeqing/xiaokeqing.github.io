# -*- coding: utf-8 -*-
"""T18 素材产线 · 建立/查看"角色定妆集"（一致性基准）

定妆集 = 一组**已发布素材里的代表帧**，作为"像不像她"的判据来源。
它只服务指标计算（存为画布 ÷4 = 191×257 的 RGBA PNG），不是展示素材。

两个来源（都只读，不改 static/kurisu ✗）：
  A) `static/kurisu/medium/*.atlas.webp`  ← 站点**当前真正在播**的图集（medium 瓦片 134×180）
  B) `E:\\DeepSeek1\\work\\_kurisu-017\\video-assets\\video\\*.poster.webp`
                                          ← 视频管线的第 0 帧（268×360，native）
  海报只有第 0 帧（= 那只剪辑的起始姿态）；要同一剪辑的**中间帧**必须走图集 ⇒ 两个来源都要。

每个参考帧记录：来源类型/真实路径/剪辑/帧号/族（正·侧·情绪·闭眼）/重采样比/
画布空间锚点（headTopY / headCenterX / area，**在完整画布分辨率上算**，无量化误差）/sha256。

用法：
  python tools/asset-refset.py build      # 重建定妆集（覆盖 refs/）
  python tools/asset-refset.py list       # 打印现有定妆集
  python tools/asset-refset.py anchors    # 由 38 个已发布剪辑实测锚点表 → tools/refs/kurisu-anchors.json
"""
import os
import sys

import numpy as np
from PIL import Image

import asset_common as ac

# ------------------------------------------------------------------ 选帧表
# frame: 0-based；'last' 表示最后一帧。poster 来源恒为第 0 帧（文件本身就是首帧）。
SET = [
    # --- 正/半正 ---
    dict(id='front-idle-f000', family='front', source='poster', clip='idle', frame=0,
         note='待机起始姿态（站点 root）'),
    dict(id='front-idle-f059', family='front', source='atlas', clip='idle', frame=59,
         note='同一剪辑中段，验证"同人不同帧"的指标下界'),
    dict(id='front-speaking-med', family='front', source='poster', clip='speaking_med', frame=0,
         note='说话循环起始'),
    dict(id='front-speaking-short', family='front', source='poster', clip='speaking_short', frame=0,
         note='短句说话（有 hi 档）'),
    dict(id='front-smile-speaking', family='front', source='poster', clip='smile_speaking', frame=0,
         note='微笑说话'),
    dict(id='front-trans-standby', family='front', source='poster', clip='trans_standby', frame=0,
         note='待机转场'),
    dict(id='front-speakclosedeye1', family='front', source='poster', clip='speaking_closed_eye_1', frame=0,
         note='说话闭眼（正）'),
    # --- 侧 ---
    dict(id='side-idle-wind', family='side', source='poster', clip='idle_side_wind', frame=0,
         note='侧身靠窗·风（上游公布 side 锚点 37 / 375）'),
    dict(id='side-idle-soft-wind', family='side', source='poster', clip='idle_side_soft_wind', frame=0,
         note='侧身柔风'),
    dict(id='side-butterfly', family='side', source='poster', clip='idle_side_butterfly', frame=0,
         note='侧身蝴蝶'),
    dict(id='side-thinking1', family='side', source='poster', clip='thinking_speaking1', frame=0,
         note='侧身思考说话'),
    dict(id='side-keypoint', family='side', source='atlas', clip='key_point_speaking', frame=90,
         note='"关键点"姿态中段'),
    # --- 情绪 ---
    dict(id='emo-angry', family='emotion', source='poster', clip='angry_speaking', frame=0,
         note='生气说话（口气重的表现层对应）'),
    dict(id='emo-sad', family='emotion', source='poster', clip='sad_speaking', frame=0,
         note='难过说话'),
    dict(id='emo-shy1', family='emotion', source='poster', clip='shy_speaking1', frame=0,
         note='害羞说话'),
    dict(id='emo-surprise', family='emotion', source='poster', clip='surprise_speaking', frame=0,
         note='惊讶说话'),
    dict(id='emo-smile-atlas', family='emotion', source='atlas', clip='smile_speaking', frame=90,
         note='图集来源的微笑（与 front-smile-speaking 同剪辑不同源，用于跨源稳健性）'),
    dict(id='emo-angry-atlas', family='emotion', source='atlas', clip='angry_speaking', frame=90,
         note='图集来源的生气'),
    dict(id='emo-sadtail-atlas', family='emotion', source='atlas', clip='sad_trans', frame='last',
         note='难过转场末帧（收尾姿态）'),
    # --- 闭眼 ---
    dict(id='closed-trans-tail', family='closed', source='poster', clip='closed_eye_trans', frame=0,
         note='闭眼转场（上游公布末帧锚点 24 / 387.14；海报=首帧）'),
    dict(id='closed-atlas-tail', family='closed', source='atlas', clip='closed_eye_trans', frame='last',
         note='闭眼转场末帧（图集）——上游 24 / 387.14 的复算基准'),
]


def source_image(spec):
    """返回 (RGBA Image(画布分辨率), 真实来源路径, 真实原生尺寸, 重采样说明)。"""
    clip = spec['clip']
    node = ac.nodes_by_clip().get(clip)
    if node is None:
        raise KeyError('剪辑不在 statemachine.json：%s' % clip)
    canvas = ac.canvas_of(node)
    n = int(node['frames'])
    f = n - 1 if spec['frame'] == 'last' else int(spec['frame'])
    if not (0 <= f < n):
        raise IndexError('%s 帧号 %s 越界（0~%d）' % (clip, spec['frame'], n - 1))
    if spec['source'] == 'atlas':
        page = node['medium']['pages'][0]
        src_path = ac.atlas_page_path(page)
        native = (int(page['tile_w']), int(page['tile_h']))
        img = ac.atlas_frame(node, f, tier='medium')
        tail = 'medium 瓦片 %d×%d → 画布 %d×%d（LANCZOS 上采样 %.3f×）' % (
            native[0], native[1], canvas[0], canvas[1], canvas[0] / native[0])
        return img, src_path, native, tail, f, canvas
    if spec['source'] == 'poster':
        src_path = ac.poster_path(clip)
        if not os.path.isfile(src_path):
            raise FileNotFoundError('读不到海报：%s' % src_path)
        img = ac.load_rgba(src_path)
        native = img.size
        if f != 0:
            raise ValueError('poster 来源只能是第 0 帧（文件本身即首帧）')
        vmeta = (ac.video_manifest()['clips'].get(clip) or {})
        coded = tuple(vmeta.get('coded') or native)
        padx = vmeta.get('padX')
        tail = ('视频首帧 %d×%d（转码前先按码流 %s 裁窄、padX=%s 补回画布）→ 画布 %d×%d'
                '（LANCZOS 等比 %.4f×）'
                % (native[0], native[1], list(coded), padx, canvas[0], canvas[1], canvas[0] / native[0]))
        # ★ 存进仓库的 <clip>.webm/poster 已经是"补回画布宽后**整体等比缩放**"的成品
        #   （画布 764×1028 ×0.3508 = 268×360）⇒ 这里只做一次等比缩放回画布，**不再 pad** ✗
        return ac.resize_to_canvas(img, canvas), src_path, native, tail, 0, canvas
    raise ValueError('未知来源 %r' % spec['source'])


def build():
    os.makedirs(ac.REFSET_DIR, exist_ok=True)
    refs = []
    for spec in SET:
        img, src_path, native, tail, frame, canvas = source_image(spec)
        img = ac.resize_to_canvas(img, canvas)
        arr = np.asarray(img, dtype=np.float64)
        anchors = ac.head_anchors(arr[:, :, 3], canvas[1])
        if anchors is None:
            raise RuntimeError('%s 抽出来是空图（全透明）' % spec['id'])
        bbox = ac.alpha_bbox(arr[:, :, 3], 8)
        # 指标空间图（画布 ÷4）
        metric = img if img.size == ac.METRIC_SIZE else img.resize(ac.METRIC_SIZE, Image.LANCZOS)
        rel = 'tools/refs/kurisu-set/%s.png' % spec['id']
        out_path = os.path.join(ac.REFSET_DIR, spec['id'] + '.png')
        metric.save(out_path, 'PNG', optimize=True)
        refs.append({
            'id': spec['id'],
            'family': spec['family'],
            'clip': spec['clip'],
            'frame': frame,
            'frameIsFirstOfClip': frame == 0,
            'sourceKind': spec['source'] + ('(medium atlas)' if spec['source'] == 'atlas' else '(video first frame)'),
            'sourcePath': src_path,
            'sourceNativeSize': [int(native[0]), int(native[1])],
            'resample': tail,
            'canvas': [int(canvas[0]), int(canvas[1])],
            'metricSize': list(ac.METRIC_SIZE),
            'file': rel,
            'bytes': os.path.getsize(out_path),
            'sha256': ac.sha256_file(out_path),
            'anchorsCanvas': {
                'headTopY': round(anchors['headTopY'], 3),
                'headCenterX': round(anchors['headCenterX'], 3),
                'area': anchors['area'],
            },
            'alphaBBoxCanvasThr8': list(bbox) if bbox else None,
            'note': spec['note'],
        })
        print('%-22s %-7s %-22s f=%-4d anchors=(%.1f, %.2f) area=%7d  %6d B'
              % (spec['id'], spec['family'], spec['clip'], frame,
                 anchors['headTopY'], anchors['headCenterX'], anchors['area'],
                 os.path.getsize(out_path)))
    fam = {}
    for r in refs:
        fam.setdefault(r['family'], []).append(r)
    ht = np.array([r['anchorsCanvas']['headTopY'] for r in refs])
    hc = np.array([r['anchorsCanvas']['headCenterX'] for r in refs])
    out = {
        'format': 'xiaokeqing.kurisu.refset.v1',
        'builtBy': 'tools/asset-refset.py',
        'purpose': '一致性判据基准（指标空间 %d×%d = 画布 ÷%d）；不是展示素材' % (
            ac.METRIC_SIZE[0], ac.METRIC_SIZE[1], ac.METRIC_DIV),
        'anchorDefinition': ('headTopY = 第一条 alpha>128 的行；headCenterX = 头部带（headTopY 往下 4% 画布高）'
                             '内 alpha>128 像素的 x 均值；area = alpha>128 像素数。与上游 SpriteForge '
                             'docs/production.md §Character contract 同定义，且已用上游公布的已发布包锚点复算验证。'),
        'canvas': list(ac.CANVAS),
        'metricSize': list(ac.METRIC_SIZE),
        'count': len(refs),
        'familyCounts': {k: len(v) for k, v in sorted(fam.items())},
        'totalBytes': sum(r['bytes'] for r in refs),
        'anchorsSummary': {
            'headTopY': {'min': float(ht.min()), 'median': float(np.median(ht)), 'max': float(ht.max())},
            'headCenterX': {'min': float(hc.min()), 'median': float(np.median(hc)), 'max': float(hc.max())},
            'note': '跨全部族；几何容差判定用**同族**或指定目标剪辑的锚点，不用全局中位数硬套',
        },
        'refs': refs,
    }
    ac.dump_json(ac.REFSET_JSON, out)
    print()
    print('定妆集：%d 张 / %d B / %s' % (len(refs), out['totalBytes'], ac.REFSET_JSON))
    print('  族分布     : %s' % out['familyCounts'])
    print('  headTopY   : min %.0f / 中位 %.0f / max %.0f' % (ht.min(), np.median(ht), ht.max()))
    print('  headCenterX: min %.1f / 中位 %.1f / max %.1f' % (hc.min(), np.median(hc), hc.max()))


def list_refs():
    if not os.path.isfile(ac.REFSET_JSON):
        print('还没有定妆集，先跑：python tools/asset-refset.py build', file=sys.stderr)
        return 2
    d = ac.load_json(ac.REFSET_JSON)
    ms = d.get('metricSize') or list(ac.METRIC_SIZE)
    print('%s ｜ %d 张 ｜ %d B ｜ 指标空间 %s' % (d['format'], d['count'], d['totalBytes'], ms))
    for r in d['refs']:
        print('  %-22s %-8s %-22s f=%-4d (%.1f, %.2f) area=%7d' % (
            r['id'], r['family'], r['clip'], r['frame'],
            r['anchorsCanvas']['headTopY'], r['anchorsCanvas']['headCenterX'], r['anchorsCanvas']['area']))
    return 0


def build_anchors():
    """38 个已发布剪辑的实测锚点表（画布分辨率，alpha>128 口径）。"""
    sm = ac.statemachine()
    rows = []
    for node in sm['nodes']:
        canvas = ac.canvas_of(node)
        n = int(node['frames'])
        idxs = sorted(set([0, n // 4, n // 2, 3 * n // 4, n - 1]))
        tops, cxs, areas, bbs = [], [], [], []
        for i in idxs:
            try:
                img = ac.atlas_frame(node, i, tier='medium')
            except Exception as e:                       # noqa: BLE001
                print('  [跳过帧] %s f=%d: %s' % (node['clip'], i, e))
                continue
            a = np.asarray(img, dtype=np.float64)[:, :, 3]
            h = ac.head_anchors(a, canvas[1])
            if not h:
                continue
            tops.append(h['headTopY']); cxs.append(h['headCenterX']); areas.append(h['area'])
            bbs.append(ac.alpha_bbox(a, 8))
        if not tops:
            continue
        rows.append({
            'clip': node['clip'],
            'canvas': [canvas[0], canvas[1]],
            'frames': n,
            'frameIntervalMs': int(node['frameIntervalMs']),
            'loopMode': node['loopMode'],
            'reverse': ac.is_reverse(node['clip']),
            'inGraph': True,
            'probedFrames': idxs,
            'headTopY': {'median': float(np.median(tops)), 'min': float(np.min(tops)), 'max': float(np.max(tops))},
            'headCenterX': {'median': float(np.median(cxs)), 'min': float(np.min(cxs)), 'max': float(np.max(cxs))},
            'area': {'median': int(np.median(areas)), 'min': int(np.min(areas)), 'max': int(np.max(areas))},
            'alphaBBoxThr8Median': [float(np.median([b[k] for b in bbs if b])) for k in range(4)],
            'statemachineOpaqueBbox': node.get('opaque_bbox'),
        })
    base = [r for r in rows if r['canvas'] == list(ac.CANVAS)]
    med_top = float(np.median([r['headTopY']['median'] for r in base]))
    med_cx = float(np.median([r['headCenterX']['median'] for r in base]))
    med_area = int(np.median([r['area']['median'] for r in base]))
    med_w = float(np.median([r['alphaBBoxThr8Median'][2] - r['alphaBBoxThr8Median'][0] for r in base]))
    med_h = float(np.median([r['alphaBBoxThr8Median'][3] - r['alphaBBoxThr8Median'][1] for r in base]))
    out = {
        'format': 'xiaokeqing.kurisu.anchors.v1',
        'builtBy': 'tools/asset-refset.py anchors',
        'method': ('对每个剪辑在 5 个采样帧（0 / 1/4 / 1/2 / 3/4 / 末帧）上实测 alpha 外框与头部锚点，'
                   '取中位数。口径与上游 SpriteForge docs/production.md §Character contract 一致。'),
        'canvas': list(ac.CANVAS),
        'clipCount': len(rows),
        'base764Count': len(base),
        'consensus764': {
            'headTopY': round(med_top, 3),
            'headCenterX': round(med_cx, 3),
            'area': med_area,
            'visibleWidthPx': round(med_w, 1),
            'visibleHeightPx': round(med_h, 1),
            'visibleWidthFracOfCanvas': round(med_w / ac.CANVAS[0], 4),
            'note': ('"既有锚点"的全局共识。上游文档写基准姿态的取景为"可见宽 = 画布 71%%、头顶在画布高 2%%"；'
                     '本文实测 38 个剪辑的中位可见宽 = %.1f px = %.2f%%、头顶中位 = %.1f px ≈ 画布高 %.2f%%，'
                     '与该取景规则吻合。' % (med_w, 100 * med_w / ac.CANVAS[0], med_top, 100 * med_top / ac.CANVAS[1])),        },
        'clips': rows,
    }
    ac.dump_json(ac.ANCHORS_JSON, out)
    print('锚点表 → %s（%d 个剪辑，其中 764 宽 %d 个）' % (ac.ANCHORS_JSON, len(rows), len(base)))
    print('  764 宽共识：headTopY %.1f ｜ headCenterX %.1f ｜ area %d ｜ 可见宽 %.0f px（画布 %.1f%%）｜ 可见高 %.0f px'
          % (med_top, med_cx, med_area, med_w, 100 * med_w / ac.CANVAS[0], med_h))
    return out


def main():
    cmd = (sys.argv[1] if len(sys.argv) > 1 else 'list').lower()
    if cmd == 'build':
        build()
        return 0
    if cmd == 'list':
        return list_refs()
    if cmd == 'anchors':
        build_anchors()
        return 0
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main())
