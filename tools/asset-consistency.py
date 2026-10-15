# -*- coding: utf-8 -*-
"""T18 素材产线 · 一致性筛（与"角色定妆集"比：相似度 + 边缘 NCC + 关键点距离）

价值：进入图集/状态机之前，先把"不像她"的自动筛掉 ✗ ——
      一致性失败率会直接乘成本（生成 3 个过 1 个 = 3 倍钱），所以这步在规模化之前。

三个指标（都会算，都会报，判定用标定出来的阈值）：
  ① 相似度      `rgbNcc`   —— 可见区内灰度的归一化互相关（对光照/编码噪声宽容，对"换了个人"敏感）
  ② 边缘 NCC    `edgeNcc`  —— Sobel 边缘幅度图、在膨胀后的剪影掩码内做 NCC
                              （这是**最锐**的指标：五官位置、发丝走向、肩线一错就掉）
  ③ 关键点距离  `kpMeanDistPx` / 关键点匹配率
                            —— Harris 角点（numpy 自实现，**没有 cv2**）在 alpha>128 内检测，
                               互相最近邻 + 距离门限匹配，报平均/最大距离（画布像素）
                               口径必须写清：这是**坐标级**匹配、无描述子 ⇒
                               能测"整体对位/五官间距漂移"，不能当特征匹配的替代品
  附：`alphaIoU`（剪影重叠）、`areaRatio`、`headTopDeltaPx`/`headCenterDeltaPx`
      （后两个与上游 SpriteForge 同定义，容差 3 px）

阈值**不是拍的**：`calibrate` 子命令拿现有素材互测，算出"像"的分布（另配一组
明确标注的"不像"负样本），把两者分开的区间写进 tools/refs/consistency-calibration.json。
证据链与限制都写在 docs/素材产线能力-T18-20261015.md。

用法：
  python tools/asset-consistency.py calibrate            # 互测标定，写标定数据
  python tools/asset-consistency.py check --in DIR --out report.json
  python tools/asset-consistency.py check --in DIR --clip new_action --family front
  python tools/asset-consistency.py refs-matrix          # 定妆集自身互测矩阵（快速体检）
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

import asset_common as ac
from asset_common import collect_inputs, IMG_EXT  # noqa: F401  （--in 展开与扩展名表）

# 关键点匹配门限：画布对角线的 8%（764×1028 对角线 1281 px ⇒ 102.5 px）
KP_GATE_PX = 0.08 * float(np.hypot(*ac.CANVAS))

# 阈值兜底（标定文件缺失时才会用到；标定存在时**一律用标定值**）
THR_FALLBACK = {
    'edgeNcc_fail': 0.7000, 'edgeNcc_fix': 0.8000, 'edgeNcc_watch': 0.8800,
    'rgbNcc_fail': 0.8500, 'rgbNcc_fix': 0.9200, 'rgbNcc_watch': 0.9600,
    'kpMean_fail': 40.0, 'kpMean_fix': 25.0,
    'areaRel_fix': 0.15, 'headTop_fail': 3.0, 'headCenter_fail': 3.0,
    'source': 'fallback（未标定，别当真 ✗）',
}


def load_thresholds():
    if os.path.isfile(ac.CALIB_JSON):
        d = ac.load_json(ac.CALIB_JSON)
        t = dict(d.get('thresholds') or {})
        if t:
            t['source'] = ac.CALIB_JSON
            t.setdefault('areaRel_fix', 0.15)
            t.setdefault('headTop_fail', 3.0)
            t.setdefault('headCenter_fail', 3.0)
            return t
    return dict(THR_FALLBACK)


# ------------------------------------------------------------------ 定妆集特征

_REF_CACHE = {}


def ref_features(use_cache=True):
    global _REF_CACHE
    if use_cache and _REF_CACHE:
        return _REF_CACHE
    d = ac.load_json(ac.REFSET_JSON)
    out = []
    for r in d['refs']:
        p = os.path.join(ac.REPO, r['file'].replace('/', os.sep))
        im = ac.load_rgba(p)
        # 定妆集存的是指标空间（191×257）；但锚点/面积要画布口径 ⇒ 用记录里的实测值覆盖
        f = ac.frame_features(im, ac.METRIC_SIZE)
        f['anchors_record'] = dict(r['anchorsCanvas'])
        f['anchors'] = dict(r['anchorsCanvas'])         # 画布口径（实测记录，非从 191×257 反推）
        f['area'] = int(r['anchorsCanvas']['area'])
        f['bbox'] = r.get('alphaBBoxCanvasThr8')
        f['id'] = r['id']; f['clip'] = r['clip']; f['family'] = r['family']
        out.append(f)
    _REF_CACHE = out
    return out


def query_features(path_or_img, canvas=ac.CANVAS, is_path=None, allow_opaque=False):
    """一张查询图 → 特征。`allow_opaque=True` 时无 alpha 的图按"全不透明"处理
    （负样本需要这种：整幅场景图就是"不是她"的典型）。"""
    if is_path is None:
        is_path = isinstance(path_or_img, (str, bytes, os.PathLike))
    if is_path:
        try:
            im = ac.load_rgba(path_or_img)
        except ValueError:
            if not allow_opaque:
                raise
            im = Image.open(path_or_img).convert('RGB').convert('RGBA')
    else:
        im = path_or_img
        if allow_opaque and im.mode != 'RGBA':
            im = im.convert('RGBA')
        elif im.mode != 'RGBA':
            raise ValueError('图像不是 RGBA')
    return ac.frame_features(ac.resize_to_canvas(im, canvas), canvas)


def best_match(q, refs):
    """对每个参考算一遍，返回 (最优记录, 全部记录)。最优 = edgeNcc 最大。"""
    rows = []
    for r in refs:
        m = ac.compare_features(q, r, ac.METRIC_DIV, KP_GATE_PX)
        # 定妆集参考的锚点用记录值（画布口径）覆盖，避免 191×257 的 4× 量化
        if r.get('anchors_record') and q.get('anchors'):
            m['headTopDeltaPx'] = round(q['anchors']['headTopY'] - r['anchors_record']['headTopY'], 3)
            m['headCenterDeltaPx'] = round(q['anchors']['headCenterX'] - r['anchors_record']['headCenterX'], 3)
        m['refId'] = r['id']; m['refClip'] = r['clip']; m['refFamily'] = r['family']
        m['sameClip'] = (r['clip'] == q.get('clip'))
        rows.append(m)
    ok = [r for r in rows if r.get('edgeNcc') is not None]
    if not ok:
        return None, rows
    best = max(ok, key=lambda r: (r['edgeNcc'], r.get('rgbNcc') or -1))
    return best, rows


# ------------------------------------------------------------------ 负样本集

def negative_samples(limit_note=True):
    """明确标注的"不像"样本（**没有第二个角色素材**，这点必须诚实写在报告里）。"""
    out = []
    scene = os.path.join(ac.REPO, 'static', 'kurisu', 'scene')
    for fn in ('amadeus_ambient_high_blend.webp', 'subtitle_frame_big.webp'):
        p = os.path.join(scene, fn)
        if os.path.isfile(p):
            out.append(('scene:' + fn, p))
    # SpriteForge 仓库自带的"几何图形 demo"帧（不是角色）
    probe = r'E:\DeepSeek1\work\_spriteforge-probe\Amadeus-SpriteForge\examples\minimal\projects\demo\frames'
    if os.path.isdir(probe):
        for sub in sorted(os.listdir(probe))[:2]:
            d = os.path.join(probe, sub, 'loop')
            if os.path.isdir(d):
                fs = sorted(f for f in os.listdir(d) if f.endswith('.png'))
                if fs:
                    out.append(('spriteforge-geometric:%s/%s' % (sub, fs[0]), os.path.join(d, fs[0])))
    return out


def synthetic_negatives(canvas=ac.CANVAS, seed=20261015):
    """合成负样本（确定性种子，可复现）：圆盘+噪声 / 圆盘+平色 / 竖条矩形 3 个。

    在**画布分辨率**上生成，和真实素材走同一条特征路径（锚点带高 = 4% 画布高）。
    """
    rng = np.random.default_rng(seed)
    w, h = canvas
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy, r = w * 0.5, h * 0.5, h * 0.35
    disk = ((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r
    out = []

    def mk(name, rgb, mask):
        a = (mask * 255).astype(np.uint8)
        arr = np.dstack([rgb.astype(np.uint8), a])
        out.append((name, Image.fromarray(arr, 'RGBA')))

    noise = rng.integers(0, 256, size=(h, w, 3))
    mk('synthetic:disk-noise', noise, disk)
    mk('synthetic:disk-flat', np.full((h, w, 3), 128), disk)
    stripes = np.zeros((h, w, 3), dtype=np.uint8)
    stripes[:, ::16] = 255
    mk('synthetic:stripes-rect', stripes, (xx > w * 0.1) & (xx < w * 0.9) & (yy > h * 0.1))
    # ★ 两个"专门打指标盲区"的负样本（用已发布 idle 首帧改造，来源可复现）：
    #   ① 轮廓完全一样、颜色反相   → 剪影/边缘指标必然照样高 ⇒ 必须靠 rgbNcc / L* 兜
    #   ② 轮廓完全一样、颜色拍平   → 同上
    #   这两条是为了**暴露指标的盲区**，不是为了让标定好看 ✓
    p = ac.poster_path('idle')
    if os.path.isfile(p):
        base = np.asarray(ac.resize_to_canvas(ac.load_rgba(p), canvas), dtype=np.uint8)
        alpha = base[:, :, 3:4]
        inv = np.dstack([255 - base[:, :, :3], base[:, :, 3]])
        out.append(('synthetic:idle-rgb-inverted', Image.fromarray(inv, 'RGBA')))
        flat = np.dstack([np.full((h, w, 3), 110, dtype=np.uint8), alpha])
        out.append(('synthetic:idle-silhouette-flat', Image.fromarray(flat, 'RGBA')))
    return out


# ------------------------------------------------------------------ 标定

def _dist(rows, key):
    v = [r[key] for r in rows if r.get(key) is not None]
    if not v:
        return None
    v = np.asarray(v, dtype=np.float64)
    return {'n': int(v.size), 'min': float(v.min()), 'p05': float(np.percentile(v, 5)),
            'p10': float(np.percentile(v, 10)), 'p25': float(np.percentile(v, 25)),
            'median': float(np.median(v)), 'p75': float(np.percentile(v, 75)),
            'p95': float(np.percentile(v, 95)), 'max': float(v.max())}


def calibrate(args):
    refs = ref_features()
    sm = ac.statemachine()
    clips = [n for n in sm['nodes'] if ac.canvas_of(n) == ac.CANVAS]
    skipped = [n['clip'] for n in sm['nodes'] if ac.canvas_of(n) != ac.CANVAS]
    per_clip = args.frames_per_clip
    pos_rows, same_clip_rows, detail = [], [], {}
    for node in clips:
        clip = node['clip']
        n = int(node['frames'])
        idxs = sorted(set(int(round(i * (n - 1) / max(1, per_clip - 1))) for i in range(per_clip)))
        local = []
        for i in idxs:
            q = query_features(ac.atlas_frame(node, i, tier='medium'))
            q['clip'] = clip
            sub = [r for r in refs if r['clip'] != clip]          # 留一剪辑出
            b, _ = best_match(q, sub)
            if b:
                b['frame'] = i
                local.append(b)
                pos_rows.append(b)
            b2, _ = best_match(q, [r for r in refs if r['clip'] == clip])
            if b2:
                b2['frame'] = i
                same_clip_rows.append(b2)
        detail[clip] = {
            'frames': idxs, 'frameIntervalMs': int(node['frameIntervalMs']),
            'edgeNccMin': round(min(r['edgeNcc'] for r in local), 5) if local else None,
            'edgeNccMedian': round(float(np.median([r['edgeNcc'] for r in local])), 5) if local else None,
            'rgbNccMin': round(min((r['rgbNcc'] or 0) for r in local), 5) if local else None,
            'kpMeanMax': round(max((r['keypoints']['meanDistPx'] or 0) for r in local), 3) if local else None,
            'bestRefs': sorted(set(r['refId'] for r in local)),
        }
        print('  标定 %-24s edgeNcc %.4f~%.4f ｜ bestRef %s'
              % (clip, detail[clip]['edgeNccMin'] or -1, detail[clip]['edgeNccMedian'] or -1,
                 ','.join(detail[clip]['bestRefs'])))

    # 定妆集自身互测（不同剪辑之间）
    ref_rows = []
    within_family, cross_family = [], []
    for i, q in enumerate(refs):
        sub = [r for j, r in enumerate(refs) if r['clip'] != q['clip']]
        b, _ = best_match(q, sub)
        if b:
            b['queryId'] = q['id']
            ref_rows.append(b)
        b2, _ = best_match(q, [r for j, r in enumerate(refs) if r['clip'] == q['clip']])
        if b2:
            b2['queryId'] = q['id']
            same_clip_rows.append(b2)
        # ★ 同族基线：只跟**同族**参考比（新素材落在已知姿态族时该用这条阈值）
        same_fam = [r for j, r in enumerate(refs) if r['family'] == q['family'] and r['clip'] != q['clip']]
        bw, _ = best_match(q, same_fam)
        if bw:
            bw['queryId'] = q['id']
            bw['familyOfQuery'] = q['family']
            within_family.append(bw)
        other = [r for j, r in enumerate(refs) if r['family'] != q['family'] and r['clip'] != q['clip']]
        bc, _ = best_match(q, other)
        if bc:
            bc['queryId'] = q['id']
            cross_family.append(bc)

    # 负样本
    neg_rows = []
    negs = []
    for name, p in negative_samples():
        try:
            negs.append((name, query_features(p, allow_opaque=True)))
        except Exception as e:                                    # noqa: BLE001
            print('  [跳过负样本] %s: %s' % (name, e))
    negs += [(n, query_features(im, is_path=False)) for n, im in synthetic_negatives()]
    for name, q in negs:
        b, _ = best_match(q, refs)
        if b:
            b['name'] = name
            neg_rows.append(b)
    print('  负样本 %d 个' % len(neg_rows))

    def kp_mean(rows):
        return [{'kpMeanDistPx': r['keypoints']['meanDistPx']} for r in rows]

    pos_metrics = {
        'edgeNcc': _dist(pos_rows, 'edgeNcc'),
        'rgbNcc': _dist(pos_rows, 'rgbNcc'),
        'alphaIoU': _dist(pos_rows, 'alphaIoU'),
        'kpMeanDistPx': _dist(kp_mean(pos_rows), 'kpMeanDistPx'),
        'areaRatio': _dist([{'areaRatio': r['areaRatio']} for r in pos_rows if r.get('areaRatio')], 'areaRatio'),
        'absHeadTopDeltaPx': _dist([{'v': abs(r['headTopDeltaPx'])} for r in pos_rows if r.get('headTopDeltaPx') is not None], 'v'),
        'absHeadCenterDeltaPx': _dist([{'v': abs(r['headCenterDeltaPx'])} for r in pos_rows if r.get('headCenterDeltaPx') is not None], 'v'),
    }
    neg_metrics = {
        'edgeNcc': _dist(neg_rows, 'edgeNcc'),
        'rgbNcc': _dist(neg_rows, 'rgbNcc'),
        'alphaIoU': _dist(neg_rows, 'alphaIoU'),
        'kpMeanDistPx': _dist(kp_mean(neg_rows), 'kpMeanDistPx'),
    }
    same_clip = {
        'edgeNcc': _dist(same_clip_rows, 'edgeNcc'),
        'rgbNcc': _dist(same_clip_rows, 'rgbNcc'),
    }

    # ---- 阈值：先用"像/不像"分离，再在"像"的分布里取分位
    p_edge, n_edge = pos_metrics['edgeNcc'], neg_metrics['edgeNcc']
    p_rgb, n_rgb = pos_metrics['rgbNcc'], neg_metrics['rgbNcc']
    sep_edge = {'positiveMin': p_edge['min'], 'negativeMax': n_edge['max'],
                'separated': bool(p_edge['min'] > n_edge['max']),
                'margin': round(p_edge['min'] - n_edge['max'], 5)}
    sep_rgb = {'positiveMin': p_rgb['min'], 'negativeMax': n_rgb['max'],
               'separated': bool(p_rgb['min'] > n_rgb['max']),
               'margin': round(p_rgb['min'] - n_rgb['max'], 5)}

    def split_line(pmin, nmax, fallback):
        """fail 线。分离成立 ⇒ 取两者中点；不成立 ⇒ 保守取**正样本最小值**
        （宁可漏放一个不像的，也不要误杀一个真的 —— 误杀会白烧生成钱 ✗）。"""
        if pmin > nmax:
            return round((pmin + nmax) / 2.0, 4), 'midpoint(separated)'
        return round(pmin, 4), 'positiveMin(not separated, conservative)'

    kp_pos = pos_metrics['kpMeanDistPx']
    e_fail, e_mode = split_line(p_edge['min'], n_edge['max'], 0.70)
    r_fail, r_mode = split_line(p_rgb['min'], n_rgb['max'], 0.85)

    # ---- 同族阈值：新素材落在已知姿态族时用这条
    #      （跨姿态用全局阈值会被姿态本身打穿 ✗ —— 标定数据里 edgeNcc 最低到 0.177）
    fam_thr = {}
    for fam in ('front', 'side', 'emotion', 'closed'):
        rows_this = [r for r in within_family if r.get('familyOfQuery') == fam]
        if not rows_this:
            continue
        pe = np.asarray([r['edgeNcc'] for r in rows_this if r.get('edgeNcc') is not None])
        pr = np.asarray([r['rgbNcc'] for r in rows_this if r.get('rgbNcc') is not None])
        pk = np.asarray([r['keypoints']['meanDistPx'] for r in rows_this
                         if r['keypoints']['meanDistPx'] is not None])
        if pe.size == 0:
            continue
        fam_thr[fam] = {
            'queries': int(pe.size),
            'edgeNccMin': round(float(pe.min()), 4),
            'edgeNccP05': round(float(np.percentile(pe, 5)), 4),
            'edgeNccMedian': round(float(np.median(pe)), 4),
            'rgbNccMin': round(float(pr.min()), 4) if pr.size else None,
            'kpMeanMax': round(float(pk.max()), 3) if pk.size else None,
            'edgeNcc_fail': round(float(pe.min()) * 0.95, 4),
            'edgeNcc_fix': round(float(np.percentile(pe, 5)), 4),
            'edgeNcc_watch': round(float(np.percentile(pe, 10)), 4),
            'note': '同族（%s）参考帧互测的最优匹配分布；新素材若属于该族，判定用这组线' % fam,
        }

    thr = {
        'edgeNcc_fail': e_fail,
        'edgeNcc_fix': round(p_edge['p05'], 4),
        'edgeNcc_watch': round(p_edge['p10'], 4),
        'rgbNcc_fail': r_fail,
        'rgbNcc_fix': round(p_rgb['p05'], 4),
        'rgbNcc_watch': round(p_rgb['p10'], 4),
        'kpMean_fail': round(kp_pos['max'], 3),
        'kpMean_fix': round(kp_pos['p95'], 3),
        'areaRel_fix': ac.AREA_TOL_REL,
        'headTop_fail': ac.ANCHOR_TOL_PX,
        'headCenter_fail': ac.ANCHOR_TOL_PX,
        'failLineMode': {'edgeNcc': e_mode, 'rgbNcc': r_mode},
        'rules': {
            'fail': 'edgeNcc < edgeNcc_fail，或 rgbNcc < rgbNcc_fail，或 kpMean > kpMean_fail，或 |headTop/headCenter 偏移| > 3 px',
            'fix': 'edgeNcc < edgeNcc_fix（正样本 p05），或 rgbNcc < rgbNcc_fix，或 |areaRatio-1| > 15%，或 kpMean > kpMean_fix（p95）',
            'watch': 'edgeNcc < edgeNcc_watch（正样本 p10），或 rgbNcc < rgbNcc_watch',
            'pass': '其余',
        },
        'derivation': ('fail 线 = "像"的最小值与"不像"的最大值的中点（分离成立时）/ 正样本最小值（不成立时）；'
                       'fix/watch 线 = "像"分布的 p05 / p10；'
                       'kpMean_fail = "像"的最大值、kpMean_fix = p95；'
                       '头部锚点容差 3 px 直接取上游 SpriteForge docs/production.md §Character contract 的值。'),
    }
    out = {
        'format': 'xiaokeqing.kurisu.consistency-calibration.v1',
        'builtBy': 'tools/asset-consistency.py calibrate',
        'canvas': list(ac.CANVAS),
        'metricSpace': list(ac.METRIC_SIZE),
        'kpGatePx': round(KP_GATE_PX, 3),
        'positives': {
            'what': ('"像"= 38 个已发布剪辑的 medium 图集帧，逐帧与定妆集比（**留一剪辑出**：'
                     '排除同剪辑的参考帧，否则会跟同一帧自己比，虚高 ✗）'),
            'framesPerClip': per_clip,
            'queries': len(pos_rows),
            'clipsUsed': len(clips),
            'clipsSkippedNon764Canvas': skipped,
            'metrics': pos_metrics,
            'perClip': detail,
        },
        'sameClipComparisons': {
            'what': ('同一剪辑的帧 ↔ 该剪辑自己的参考帧。⚠ 这**不是"上界"**：'
                     '转场剪辑（trans_standby / closed_eye_trans / speaking_trans）的首末帧姿态差异极大，'
                     '所以这个分布里也会出现接近 0 的 edgeNcc（实测 min -0.039）⇒ '
                     '它只说明"同一条剪辑内部也会跨姿态"，不能当阈值依据 ✗'),
            'queries': len(same_clip_rows), 'metrics': same_clip,
        },
        'refsetInternal': {
            'what': '定妆集内部互测（不同剪辑之间）',
            'queries': len(ref_rows),
            'metrics': {'edgeNcc': _dist(ref_rows, 'edgeNcc'), 'rgbNcc': _dist(ref_rows, 'rgbNcc'),
                        'kpMeanDistPx': _dist(kp_mean(ref_rows), 'kpMeanDistPx')},
            'pairs': [{'query': r.get('queryId'), 'bestRef': r['refId'], 'edgeNcc': r['edgeNcc'],
                       'rgbNcc': r['rgbNcc'], 'kpMeanDistPx': r['keypoints']['meanDistPx']} for r in ref_rows],
        },
        'withinFamily': {
            'what': ('只跟**同族**参考帧比（不同剪辑）—— 新素材落在已知姿态族时，这条才是可用的阈值；'
                     '跨姿态用全局阈值会被姿态本身打穿 ✗'),
            'queries': len(within_family),
            'metrics': {'edgeNcc': _dist(within_family, 'edgeNcc'),
                        'rgbNcc': _dist(within_family, 'rgbNcc'),
                        'kpMeanDistPx': _dist(kp_mean(within_family), 'kpMeanDistPx')},
            'perFamily': fam_thr,
            'pairs': [{'query': r.get('queryId'), 'family': r.get('familyOfQuery'),
                       'bestRef': r['refId'], 'edgeNcc': r['edgeNcc'], 'rgbNcc': r['rgbNcc'],
                       'kpMeanDistPx': r['keypoints']['meanDistPx']} for r in within_family],
        },
        'crossFamily': {
            'what': '只跟**其他族**参考帧比（不同剪辑）—— 说明"跨姿态比边缘"这个动作本身有多难',
            'queries': len(cross_family),
            'metrics': {'edgeNcc': _dist(cross_family, 'edgeNcc'),
                        'rgbNcc': _dist(cross_family, 'rgbNcc'),
                        'kpMeanDistPx': _dist(kp_mean(cross_family), 'kpMeanDistPx')},
        },
        'negatives': {
            'what': '明确标注的"不像"样本',
            'sources': ([n for n, _ in negative_samples()] + ['synthetic:disk-noise', 'synthetic:disk-flat',
                                                              'synthetic:stripes-rect']),
            'LIMITATION': ('⚠ 本仓库**没有第二个角色的素材** ⇒ 负样本只有"非角色图（场景/webp 垫板/几何 demo）'
                           '与合成形状"。所以本标定保证的是"明显不像能被拦住"，'
                           '**不能**保证"另一个动漫角色也被拦住" [待核对]。'
                           '要收紧这条，需要再找一份他人角色图当负样本。'),
            'count': len(neg_rows),
            'metrics': neg_metrics,
            'rows': [{'name': r['name'], 'bestRef': r['refId'], 'edgeNcc': r['edgeNcc'],
                      'rgbNcc': r['rgbNcc'], 'alphaIoU': r['alphaIoU'],
                      'kpMeanDistPx': r['keypoints']['meanDistPx']} for r in neg_rows],
        },
        'separation': {'edgeNcc': sep_edge, 'rgbNcc': sep_rgb},
        'thresholds': thr,
        'familyThresholds': fam_thr,
        'generatedFor': 'tools/asset-consistency.py check（判定一律读这里的阈值，不读代码常量）',
    }
    ac.dump_json(ac.CALIB_JSON, out)
    print()
    print('标定 → %s' % ac.CALIB_JSON)
    print('  "像"（留一剪辑出，%d 帧）：edgeNcc min %.4f / p05 %.4f / 中位 %.4f ｜ rgbNcc min %.4f / 中位 %.4f'
          % (len(pos_rows), p_edge['min'], p_edge['p05'], p_edge['median'], p_rgb['min'], p_rgb['median']))
    print('  "像"关键点距离：中位 %.2f px / p95 %.2f px / max %.2f px'
          % (kp_pos['median'], kp_pos['p95'], kp_pos['max']))
    print('  "不像"（%d 个）：edgeNcc max %.4f ｜ rgbNcc max %.4f ｜ alphaIoU max %.4f'
          % (len(neg_rows), n_edge['max'], n_rgb['max'], neg_metrics['alphaIoU']['max']))
    print('  分离      ：edgeNcc %s（margin %.4f）｜ rgbNcc %s（margin %.4f）'
          % (sep_edge['separated'], sep_edge['margin'], sep_rgb['separated'], sep_rgb['margin']))
    print('  阈值      ：fail edgeNcc<%.4f rgbNcc<%.4f ｜ fix edgeNcc<%.4f ｜ watch edgeNcc<%.4f'
          % (thr['edgeNcc_fail'], thr['rgbNcc_fail'], thr['edgeNcc_fix'], thr['edgeNcc_watch']))
    print('  同族基线  ：%s' % (' ｜ '.join(
        '%s edgeNcc %.3f~%.3f(中位 %.3f)' % (f, v['edgeNccMin'], v['edgeNccP05'], v['edgeNccMedian'])
        for f, v in sorted(fam_thr.items())) or '无'))
    cf = _dist(cross_family, 'edgeNcc')
    if cf:
        print('  跨族对照  ：edgeNcc min %.4f / 中位 %.4f（越跨姿态越低 ⇒ 全局阈值只能挡"明显不是角色"）'
              % (cf['min'], cf['median']))
    return 0


# ------------------------------------------------------------------ check

def check(args):
    thr = load_thresholds()
    refs = ref_features()
    if args.family:
        refs = [r for r in refs if r['family'] == args.family]
        if not refs:
            print('定妆集里没有族 %s' % args.family, file=sys.stderr)
            return 2
    paths = collect_inputs(args.src)
    rows = []
    verdicts = {}
    for i, p in enumerate(paths):
        q = query_features(p)
        q['clip'] = args.clip
        if args.clip:                                  # 留一剪辑出（不拿目标剪辑自己的参考帧自证 ✓）
            sub = [r for r in refs if r['clip'] != args.clip] or refs
        else:
            sub = refs
        b, allrows = best_match(q, sub)
        if b is None:
            print('  [跳过] %s：全是透明或指标算不出' % p)
            continue
        v, reasons = ac.qa_verdict(b, thr)
        b['file'] = os.path.basename(p); b['verdict'] = v; b['reasons'] = reasons
        b['topRefs'] = sorted([(r['refId'], r['edgeNcc'], r['rgbNcc']) for r in allrows
                               if r.get('edgeNcc') is not None], key=lambda t: -t[1])[:3]
        rows.append(b)
        verdicts[v] = verdicts.get(v, 0) + 1
        print('  %-34s %-4s bestRef=%-22s edgeNcc=%.4f rgbNcc=%s kpMean=%s areaRatio=%s %s'
              % (b['file'], v, b['refId'], b['edgeNcc'],
                 ('%.4f' % b['rgbNcc']) if b.get('rgbNcc') is not None else '  n/a ',
                 ('%.2f' % b['keypoints']['meanDistPx']) if b['keypoints']['meanDistPx'] is not None else ' n/a ',
                 ('%.3f' % b['areaRatio']) if b.get('areaRatio') is not None else ' n/a ',
                 ('← ' + '; '.join(reasons)) if reasons else ''))
    out = {
        'format': 'xiaokeqing.kurisu.consistency-report.v1',
        'builtBy': 'tools/asset-consistency.py check',
        'input': args.src,
        'clip': args.clip,
        'familyFilter': args.family,
        'refCount': len(refs),
        'thresholdsUsed': thr,
        'frames': rows,
        'summary': {
            'frames': len(rows),
            'verdicts': verdicts,
            'worstEdgeNcc': min((r['edgeNcc'] for r in rows), default=None),
            'failed': [r['file'] for r in rows if r['verdict'] == 'fail'],
        },
    }
    if args.out:
        ac.dump_json(args.out, out)
        print('\n报告 → %s' % args.out)
    print('汇总：%d 帧 ｜ %s ｜ 最差 edgeNcc %s'
          % (len(rows), verdicts, out['summary']['worstEdgeNcc']))
    return 0


def refs_matrix(args):
    refs = ref_features()
    print('定妆集互测（edgeNcc，行=查询，列取每行最优）')
    worst = None
    for q in refs:
        sub = [r for r in refs if r['clip'] != q['clip']]
        b, _ = best_match(q, sub)
        if not b:
            continue
        print('  %-22s → %-22s edgeNcc %.4f ｜ rgbNcc %.4f ｜ kpMean %s'
              % (q['id'], b['refId'], b['edgeNcc'], b['rgbNcc'] or float('nan'),
                 ('%.2f' % b['keypoints']['meanDistPx']) if b['keypoints']['meanDistPx'] is not None else 'n/a'))
        if worst is None or b['edgeNcc'] < worst[1]:
            worst = (q['id'], b['edgeNcc'], b['refId'])
    if worst:
        print('最差：%s → %s  edgeNcc %.4f' % (worst[0], worst[2], worst[1]))
    return 0


def main():
    ap = argparse.ArgumentParser(description='T18 一致性筛（与定妆集比：相似度 / 边缘 NCC / 关键点距离）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('calibrate', help='用现有素材互测标定阈值')
    c.add_argument('--frames-per-clip', type=int, default=6)
    k = sub.add_parser('check', help='对一批帧做一致性筛')
    k.add_argument('--in', dest='src', required=True)
    k.add_argument('--out', help='报告 JSON 路径')
    k.add_argument('--clip', help='目标新剪辑名（用于留一剪辑出）')
    k.add_argument('--family', choices=['front', 'side', 'emotion', 'closed'], help='只用该族的参考帧')
    sub.add_parser('refs-matrix', help='定妆集自身互测矩阵')
    args = ap.parse_args()
    if args.cmd == 'calibrate':
        return calibrate(args)
    if args.cmd == 'check':
        return check(args)
    if args.cmd == 'refs-matrix':
        return refs_matrix(args)
    return 1


if __name__ == '__main__':
    sys.exit(main())
