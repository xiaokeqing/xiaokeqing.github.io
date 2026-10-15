# -*- coding: utf-8 -*-
"""T18 素材产线 · 公共库（几何 / 锚点 / 指标）

本文件被以下脚本共用，不含可执行入口：
  tools/asset-refset.py        建立"角色定妆集"（一致性基准）
  tools/asset-align.py         任意生成结果 → 对齐到 764×1028 与既有锚点
  tools/asset-consistency.py   与定妆集比对（相似度 / 边缘 NCC / 关键点距离）

★ 关键事实（全部实测，来源见 docs/素材产线能力-T18-20261015.md）：
  1. 逻辑画布 = **764×1028**（`statemachine.json` 的 `frame_size`；38/39 个剪辑如此，
     1 个是 960×1028 —— 本库不猜，调用方必须显式给画布）。
  2. 逐帧时长 = **8 / 17 / 21 ms**（`frameIntervalMs`，不是 60fps 语义）。
  3. **锚点定义与上游 SpriteForge 完全一致**（`docs/production.md` §Character contract）：
       headTopY    = 第一条 alpha > 128 的行
       headCenterX = 头部带（headTopY 往下 4% 画布高）内 alpha > 128 像素的 x 均值
       area        = alpha > 128 的像素数
     容差默认：头部上沿 / 头心 **3 px**、面积 **15%**（上游同值）。
     ★ 本库的实现已用上游公布的已发布包锚点复算验证：
        idle f0 上游 20 / 387.82 → 本库 20 / 387.82（差 0.00 px）
        trans_smile 末帧 上游 21 / 385.58 → 本库 21 / 385.66（差 0.08 px）
        closed_eye_trans 末帧 上游 24 / 387.14 → 本库 24 / 387.21（差 0.07 px）
        idle_side_wind f0 上游 side (top 37, centre ≈375) → 本库 36 / 374.86
     ⇒ 因此"对齐到既有锚点"= 把新素材的 headTopY/headCenterX 放到已发布素材的同一位置。
  4. **不用 `statemachine.json` 的 `opaque_bbox`** ✗：实测它与真实 alpha 包围盒不符
     （x1 恒等于画布宽，如 idle 写 [116,0,764,1028] 而实测 alpha 外框是 [11,17,661,1022]）。
     本库一律**实测** alpha 外框。

依赖：numpy + Pillow（**无 cv2 / scipy / skimage**）。
"""
import hashlib
import json
import os

import numpy as np
from PIL import Image

# ---------------------------------------------------------------- 路径与常量

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATEMACHINE = os.path.join(REPO, 'static', 'kurisu', 'statemachine.json')
MEDIUM_MANIFEST = os.path.join(REPO, 'static', 'kurisu', 'manifest.json')
VIDEO_ASSETS = r'E:\DeepSeek1\work\_kurisu-017\video-assets'
REFSET_DIR = os.path.join(REPO, 'tools', 'refs', 'kurisu-set')
REFSET_JSON = os.path.join(REFSET_DIR, 'refs.json')
ANCHORS_JSON = os.path.join(REPO, 'tools', 'refs', 'kurisu-anchors.json')
CALIB_JSON = os.path.join(REPO, 'tools', 'refs', 'consistency-calibration.json')

# 逻辑画布（基准）与上采样档位（实测自 static/kurisu/medium 与 /hi 的瓦片尺寸）
CANVAS = (764, 1028)
TIERS = {'medium': (134, 180), 'hi': (268, 360)}   # (瓦片宽, 瓦片高) for 764×1028

# 指标空间 = 画布 ÷4（整数倍，无各向异性）。像素类指标（NCC/边缘/关键点）在此空间算；
# 几何类指标（headTopY/headCenterX/area/bbox）一律在**画布分辨率**上算，避免 4× 量化误差。
METRIC_DIV = 4
METRIC_SIZE = (CANVAS[0] // METRIC_DIV, CANVAS[1] // METRIC_DIV)   # 191×257

# 上游同值容差（docs/production.md §Character contract）
ANCHOR_TOL_PX = 3.0        # 头部上沿 / 头心
AREA_TOL_REL = 0.15        # 面积相对容差

# 上游 QA 口径（docs/production.md §QA），本库只借"等级"这一套，阈值另行标定
QA_LEVELS = ('pass', 'watch', 'fix', 'fail')


# ---------------------------------------------------------------- 基础 IO

IMG_EXT = ('.png', '.webp', '.tif', '.tiff', '.bmp', '.jpg', '.jpeg')


def collect_inputs(spec):
    """把 --in 的写法（目录 / 单文件 / 逗号分隔 / glob）展开成**有序**帧列表。

    排序 = Python 默认字典序（与上游 SpriteForge 一致：文件名按字典序排 ⇒ 必须零填充）。
    """
    import glob as _glob
    items = []
    for part in (spec or '').split(','):
        part = part.strip()
        if not part:
            continue
        if os.path.isdir(part):
            items += [os.path.join(part, f) for f in os.listdir(part) if f.lower().endswith(IMG_EXT)]
        elif any(ch in part for ch in '*?['):
            items += _glob.glob(part)
        elif os.path.isfile(part):
            items.append(part)
        else:
            raise FileNotFoundError('读不到：%s' % part)
    if not items:
        raise FileNotFoundError('没有可用帧')
    return sorted(items)


def warn_padding(paths):
    """帧名不零填充 ⇒ 字典序会乱（上游明确要求零填充）—— 只警告，不擅自改名。"""
    names = [os.path.basename(p) for p in paths]
    if len(names) < 2:
        return None
    digits = [''.join(ch for ch in n if ch.isdigit()) for n in names]
    if any(not d for d in digits):
        return '部分文件名不含数字 ⇒ 无法判断零填充'
    if len(set(len(d) for d in digits)) > 1:
        return ('帧名数字位宽不一致（位宽 %s）⇒ 字典序排序会错位，请先零填充重命名 ✗'
                % ','.join(sorted(set(str(len(d)) for d in digits))))
    if names != sorted(names, key=lambda n: int(''.join(ch for ch in n if ch.isdigit()))):
        return '字典序与数字序不一致 ⇒ 请零填充 ✗'
    return None


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def dump_json(path, obj, indent=1, sort_keys=False):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent, sort_keys=sort_keys)
    return path


def sha256_file(path, bufsize=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(bufsize), b''):
            h.update(chunk)
    return h.hexdigest()


def load_rgba(path):
    """读成 RGBA。没有 alpha 通道会抛错（本库不猜抠图，抠图是外部处理器的事）。"""
    im = Image.open(path)
    if im.mode not in ('RGBA', 'LA', 'P') and 'transparency' not in im.info:
        raise ValueError('无 alpha 通道：%s（mode=%s）—— 请先用抠图处理器出 RGBA' % (path, im.mode))
    return im.convert('RGBA')


def rgb_to_lstar(rgb):
    """sRGB(0~255) → CIE L*（D65）。返回与输入同形状的浮点数组。"""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    # D65 白点
    x = (0.4124564 * lin[..., 0] + 0.3575761 * lin[..., 1] + 0.1804375 * lin[..., 2]) / 0.95047
    y = (0.2126729 * lin[..., 0] + 0.7151522 * lin[..., 1] + 0.0721750 * lin[..., 2]) / 1.00000
    z = (0.0193339 * lin[..., 0] + 0.1191920 * lin[..., 1] + 0.9503041 * lin[..., 2]) / 1.08883
    def f(t):
        return np.where(t > 216.0 / 24389.0, np.cbrt(t), (24389.0 / 27.0 * t + 16.0) / 116.0)
    return 116.0 * f(y) - 16.0


def luma_u8(rgba_arr):
    """快速亮度（Rec.709，输出 0~255 浮点）—— 用于 NCC / 边缘，不用于 L*。"""
    a = np.asarray(rgba_arr, dtype=np.float64)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


# ---------------------------------------------------------------- 状态机 / 图集

_SM_CACHE = {}


def statemachine():
    if 'sm' not in _SM_CACHE:
        _SM_CACHE['sm'] = load_json(STATEMACHINE)
    return _SM_CACHE['sm']


def nodes_by_clip():
    if 'nodes' not in _SM_CACHE:
        _SM_CACHE['nodes'] = {n['clip']: n for n in statemachine()['nodes']}
    return _SM_CACHE['nodes']


def clips_not_in_graph():
    """sad / smile 这类"有素材但不在状态机里"的剪辑（白名单外）。"""
    return list(statemachine().get('clips_not_in_graph') or [])


def medium_manifest_clips():
    if 'mm' not in _SM_CACHE:
        mm = load_json(MEDIUM_MANIFEST)
        _SM_CACHE['mm'] = ((mm.get('clipsMedium') or {}).get('clips')) or {}
    return _SM_CACHE['mm']


def is_reverse(clip):
    """图集是否是倒放的（目前只有 key_point_to_thinking = thinking_to_key_point 倒放）。"""
    return bool((medium_manifest_clips().get(clip) or {}).get('reverse'))


def canvas_of(node):
    fs = node.get('frame_size') or list(CANVAS)
    return (int(fs[0]), int(fs[1]))


def tier_tile_size(tier, canvas=CANVAS):
    """按画布等比推出瓦片尺寸（medium 134×180 / hi 268×360 对应 764×1028）。"""
    tw, th = TIERS[tier]
    if canvas == CANVAS:
        return tw, th
    import math
    return (int(round(canvas[0] * tw / CANVAS[0])), int(round(canvas[1] * th / CANVAS[1])))


def atlas_page_path(page):
    return os.path.join(REPO, 'static', page['url'].replace('/', os.sep))


def read_atlas_page(page):
    return Image.open(atlas_page_path(page)).convert('RGBA')


def atlas_frame(node, idx, tier='medium'):
    """取第 idx 帧（0-based），返回 **(画布分辨率)** 的 RGBA Image。

    图集里一页一个 webp，帧按 `cols` 逐行排列；`frame_size` 是逻辑画布，
    瓦片是它的等比缩放 ⇒ 这里一律 resize 回画布，让所有几何/锚点口径统一。
    多页图集（idle_closed_eye / idle2 / …）会按 first_frame/last_frame 选页。
    """
    f1 = idx + 1                                   # statemachine 的帧号是 1-based
    pages = (node.get(tier) or {}).get('pages') or []
    for p in pages:
        if p['first_frame'] <= f1 <= p['last_frame']:
            loc = f1 - p['first_frame']
            src = read_atlas_page(p)
            sx = (loc % p['cols']) * p['tile_w']
            sy = (loc // p['cols']) * p['tile_h']
            tile = src.crop((sx, sy, sx + p['tile_w'], sy + p['tile_h']))
            cw, ch = canvas_of(node)
            if tile.size != (cw, ch):
                tile = tile.resize((cw, ch), Image.LANCZOS)
            return tile
    raise IndexError('帧 %d 不落在任何页里（clip=%s tier=%s）' % (f1, node['clip'], tier))


def poster_path(clip):
    return os.path.join(VIDEO_ASSETS, 'video', clip + '.poster.webp')


def video_manifest():
    if 'vm' not in _SM_CACHE:
        _SM_CACHE['vm'] = load_json(os.path.join(VIDEO_ASSETS, 'manifest-video.json'))
    return _SM_CACHE['vm']


# ---------------------------------------------------------------- 几何 / 锚点

def alpha_bbox(alpha, thr=128):
    """alpha 外框 [x0, y0, x1, y1]（右/下开区间）。空图返回 None。"""
    m = np.asarray(alpha) > thr
    rows = np.nonzero(m.any(axis=1))[0]
    if len(rows) == 0:
        return None
    cols = np.nonzero(m.any(axis=0))[0]
    return (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)


def alpha_bbox_loose(alpha, thr=8):
    """更宽的阈值，用于"最外沿"（和上游 128 的定义区分开，报告里分开说）。"""
    return alpha_bbox(alpha, thr)


def head_anchors(alpha, canvas_h=None):
    """★ 与上游 SpriteForge 同定义。

    返回 dict：headTopY（浮点=行号）、headCenterX、area（alpha>128 像素数）、
    headBandRows、bbox（alpha>8 的宽松外框，仅作参考）。
    alpha>128 全空时返回 None。
    """
    a = np.asarray(alpha)
    h = int(canvas_h or a.shape[0])
    m = a > 128
    rows = np.nonzero(m.any(axis=1))[0]
    if len(rows) == 0:
        return None
    top = int(rows[0])
    band = max(1, int(round(0.04 * h)))
    y0, y1 = top, min(a.shape[0], top + band)
    sub = m[y0:y1]
    ys, xs = np.nonzero(sub)
    cx = float(xs.mean()) if len(xs) else float('nan')
    return {
        'headTopY': float(top),
        'headCenterX': cx,
        'area': int(m.sum()),
        'headBandRows': [int(y0), int(y1)],
        'bbox': alpha_bbox(a, 8),
    }


def shift_canvas(img_rgba, size, dx, dy):
    """把 RGBA 平移 (dx, dy) 后贴到 size 的透明画布上（整数像素，无缩放）。"""
    out = Image.new('RGBA', size, (0, 0, 0, 0))
    out.paste(img_rgba, (int(round(dx)), int(round(dy))))
    return out


def resize_to_canvas(img_rgba, canvas=CANVAS):
    if img_rgba.size == canvas:
        return img_rgba
    return img_rgba.resize(canvas, Image.LANCZOS)


def to_metric(img_rgba):
    """画布分辨率的 RGBA → 指标空间阵列（191×257，float）。"""
    im = img_rgba if img_rgba.size == METRIC_SIZE else img_rgba.resize(METRIC_SIZE, Image.LANCZOS)
    return np.asarray(im, dtype=np.float64)


# ---------------------------------------------------------------- 像素指标

def _box(a, r):
    """可分离盒式滤波（cumsum 实现，r 半径）。"""
    if r < 1:
        return a
    k = 2 * r + 1
    p = np.pad(a, ((r, r + 1), (0, 0)))
    cs = p.cumsum(axis=0)
    s = cs[k:, :] - cs[:-k, :]
    p2 = np.pad(s, ((0, 0), (r, r + 1)))
    cs2 = p2.cumsum(axis=1)
    s2 = cs2[:, k:] - cs2[:, :-k]
    return s2 / float(k * k)


def sobel(gray):
    g = np.asarray(gray, dtype=np.float64)
    p = np.pad(g, 1, mode='edge')
    gx = (p[0:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[0:-2, 0:-2] + 2 * p[1:-1, 0:-2] + p[2:, 0:-2])
    gy = (p[2:, 0:-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[0:-2, 0:-2] + 2 * p[0:-2, 1:-1] + p[0:-2, 2:])
    return gx, gy


def edge_mag(gray):
    gx, gy = sobel(gray)
    return np.sqrt(gx * gx + gy * gy)


def ncc(a, b, mask=None):
    """归一化互相关。mask=None 时用 a、b 的公共非零区域。"""
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    if mask is not None:
        m = np.asarray(mask, dtype=bool).ravel()
        a, b = a[m], b[m]
    if a.size < 8:
        return float('nan')
    a = a - a.mean()
    b = b - b.mean()
    den = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / den) if den > 1e-12 else float('nan')


def mask_iou(ma, mb):
    """两个二值掩码的 IoU。"""
    ma = np.asarray(ma, dtype=bool)
    mb = np.asarray(mb, dtype=bool)
    u = int((ma | mb).sum())
    return float((ma & mb).sum() / u) if u else 1.0


def centroid(alpha, thr=128):
    m = np.asarray(alpha) > thr
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return (float('nan'), float('nan'))
    return (float(xs.mean()), float(ys.mean()))


def dilate(mask, r=1):
    """形态学膨胀（方形结构元，最大滤波实现）。"""
    m = np.asarray(mask, dtype=bool)
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx == 0 and dy == 0:
                continue
            out |= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
    return out


# ---------------------------------------------------------------- 关键点

def harris_keypoints(alpha, gray, max_n=160, r=2, k=0.04, nms_r=3, rel_thr=0.01):
    """Harris 角点（numpy 实现，无 cv2）。

    只在 alpha>128 的区域内找 —— 我们要的是"角色身上的稳定结构点"（眼、发际、肩线…），
    不是画面四角的噪声。返回 (N,3) 数组：x, y, R（画布/指标空间像素坐标，按 R 降序）。
    """
    m = np.asarray(alpha) > 128
    if m.sum() < 64:
        return np.zeros((0, 3), dtype=np.float64)
    g = np.asarray(gray, dtype=np.float64) / 255.0
    gx, gy = sobel(g)
    Ixx = _box(gx * gx, r)
    Iyy = _box(gy * gy, r)
    Ixy = _box(gx * gy, r)
    det = Ixx * Iyy - Ixy * Ixy
    tr = Ixx + Iyy
    R = det - k * tr * tr
    R = np.where(m, R, 0.0)
    rmax = float(R.max())
    if rmax <= 0:
        return np.zeros((0, 3), dtype=np.float64)
    # 3×3 局部极大（NMS）
    keep = np.ones_like(R, dtype=bool)
    for dy in range(-nms_r, nms_r + 1):
        for dx in range(-nms_r, nms_r + 1):
            if dx == 0 and dy == 0:
                continue
            keep &= R >= np.roll(np.roll(R, dy, axis=0), dx, axis=1)
    R = np.where(keep & (R > rel_thr * rmax), R, 0.0)
    ys, xs = np.nonzero(R > 0)
    if len(xs) == 0:
        return np.zeros((0, 3), dtype=np.float64)
    vals = R[ys, xs]
    order = np.argsort(-vals)[:max_n]
    return np.stack([xs[order].astype(np.float64), ys[order].astype(np.float64), vals[order]], axis=1)


def keypoint_match(pts_a, pts_b, gate_px):
    """贪心最近邻匹配（无描述子，只按坐标 + 互相最近）。

    返回 dict：matched / rate / meanDistPx / maxDistPx / gatePx / nA / nB。
    说明：这是"坐标级"匹配，能测出**整体对位与五官间距**是否漂移；
    它不能替代描述子匹配，报告里必须写清（见 docs 里的口径）。
    """
    A = np.asarray(pts_a, dtype=np.float64)
    B = np.asarray(pts_b, dtype=np.float64)
    if len(A) == 0 or len(B) == 0:
        return {'matched': 0, 'rate': 0.0, 'meanDistPx': None, 'maxDistPx': None,
                'gatePx': float(gate_px), 'nA': int(len(A)), 'nB': int(len(B))}
    d = np.sqrt(((A[:, None, :2] - B[None, :, :2]) ** 2).sum(axis=2))
    ia = d.argmin(axis=1)
    ib = d.argmin(axis=0)
    dists = []
    for i, j in enumerate(ia):
        if ib[j] == i and d[i, j] <= gate_px:
            dists.append(d[i, j])
    dists = np.asarray(dists, dtype=np.float64)
    return {
        'matched': int(dists.size),
        'rate': float(dists.size / max(1, min(len(A), len(B)))),
        'meanDistPx': float(dists.mean()) if dists.size else None,
        'maxDistPx': float(dists.max()) if dists.size else None,
        'gatePx': float(gate_px),
        'nA': int(len(A)),
        'nB': int(len(B)),
    }


# ---------------------------------------------------------------- 综合指标

def lower_face_lstar(alpha, rgb, anchors, canvas=CANVAS):
    """上游 QA 的"下脸亮度 ROI"：headTopY 往下 24%~30% 画布高、头心左右各 5% 画布宽。"""
    if not anchors:
        return float('nan')
    h, w = canvas[1], canvas[0]
    y0 = int(round(anchors['headTopY'] + 0.24 * h))
    y1 = int(round(anchors['headTopY'] + 0.30 * h))
    x0 = int(round(anchors['headCenterX'] - 0.05 * w))
    x1 = int(round(anchors['headCenterX'] + 0.05 * w))
    y0, y1 = max(0, y0), min(h, y1)
    x0, x1 = max(0, x0), min(w, x1)
    if y1 <= y0 or x1 <= x0:
        return float('nan')
    a = np.asarray(alpha)[y0:y1, x0:x1] > 128
    if a.sum() < 16:
        return float('nan')
    L = rgb_to_lstar(np.asarray(rgb, dtype=np.float64)[y0:y1, x0:x1])
    return float(L[a].mean())


def frame_features(img_canvas, canvas=CANVAS):
    """把一张**画布分辨率**的 RGBA 变成一组可比特征。"""
    im = resize_to_canvas(img_canvas, canvas)
    arr = np.asarray(im, dtype=np.float64)
    alpha = arr[:, :, 3]
    anchors = head_anchors(alpha, canvas[1])
    m = to_metric(im)
    ma = m[:, :, 3]
    gray = luma_u8(m)
    eg = edge_mag(gray)
    mask = ma > 128
    return {
        'canvas': [int(canvas[0]), int(canvas[1])],
        'anchors': anchors,
        'area': int(anchors['area']) if anchors else 0,
        'bbox': alpha_bbox(alpha, 8),
        'centroid': centroid(alpha, 128),
        'lstar_lower_face': lower_face_lstar(alpha, arr[:, :, :3], anchors, canvas),
        'metric': m,
        'metric_alpha': ma,
        'metric_gray': gray,
        'metric_edge': eg,
        'metric_mask': mask,
        'metric_mask_dil': dilate(mask, 2),
        'keypoints': harris_keypoints(ma, gray),
    }


def compare_features(q, r, metric_scale, kp_gate_metric_px=None):
    """把查询特征 q 与参考特征 r 比成一组指标（都会返回，不做判定）。

    metric_scale = 画布像素 / 指标像素（本库 = 4）。
    """
    mask = q['metric_mask'] | r['metric_mask']
    mask_dil = q['metric_mask_dil'] | r['metric_mask_dil']
    edge_ncc = ncc(q['metric_edge'], r['metric_edge'], mask_dil)
    rgb_ncc = ncc(q['metric_gray'], r['metric_gray'], mask)
    out = {
        'alphaIoU': round(mask_iou(q['metric_mask'], r['metric_mask']), 5),
        'rgbNcc': None if rgb_ncc != rgb_ncc else round(rgb_ncc, 5),
        'edgeNcc': None if edge_ncc != edge_ncc else round(edge_ncc, 5),
        'areaRatio': round(q['area'] / r['area'], 5) if r['area'] else None,
        'lstarDelta': None,
    }
    if q['lstar_lower_face'] == q['lstar_lower_face'] and r['lstar_lower_face'] == r['lstar_lower_face']:
        out['lstarDelta'] = round(q['lstar_lower_face'] - r['lstar_lower_face'], 3)
    if q['anchors'] and r['anchors']:
        out['headTopDeltaPx'] = round(q['anchors']['headTopY'] - r['anchors']['headTopY'], 3)
        out['headCenterDeltaPx'] = round(q['anchors']['headCenterX'] - r['anchors']['headCenterX'], 3)
    # 关键点：参考集的点作为基准，查询的点去匹配（坐标已是**画布像素**，这里统一换算）
    pa = q['keypoints'].copy()
    pb = r['keypoints'].copy()
    # harris 在指标空间算的 ⇒ 换算成画布像素再比距离，读数才有物理意义
    pa[:, :2] *= metric_scale
    pb[:, :2] *= metric_scale
    gate = kp_gate_metric_px if kp_gate_metric_px is not None else 0.08 * float(np.hypot(*CANVAS))
    out['keypoints'] = keypoint_match(pa, pb, gate)
    return out


def qa_verdict(m, thr):
    """按标定出来的阈值给等级（pass / watch / fix / fail），与上游 QA 等级同构。"""
    lvl = 0
    reasons = []
    if m.get('edgeNcc') is not None and m['edgeNcc'] < thr['edgeNcc_fail']:
        return 'fail', ['edgeNcc %.4f < %.4f' % (m['edgeNcc'], thr['edgeNcc_fail'])]
    if m.get('rgbNcc') is not None and m['rgbNcc'] < thr['rgbNcc_fail']:
        return 'fail', ['rgbNcc %.4f < %.4f' % (m['rgbNcc'], thr['rgbNcc_fail'])]
    kp = m.get('keypoints') or {}
    if kp.get('meanDistPx') is not None and kp['meanDistPx'] > thr['kpMean_fail']:
        return 'fail', ['kpMean %.2f > %.2f' % (kp['meanDistPx'], thr['kpMean_fail'])]
    if m.get('headTopDeltaPx') is not None and abs(m['headTopDeltaPx']) > thr['headTop_fail']:
        return 'fail', ['headTopDelta %.2f > %.2f' % (m['headTopDeltaPx'], thr['headTop_fail'])]
    if m.get('headCenterDeltaPx') is not None and abs(m['headCenterDeltaPx']) > thr['headCenter_fail']:
        return 'fail', ['headCenterDelta %.2f > %.2f' % (m['headCenterDeltaPx'], thr['headCenter_fail'])]
    if m.get('edgeNcc') is not None and m['edgeNcc'] < thr['edgeNcc_fix']:
        lvl = max(lvl, 2)
        reasons.append('edgeNcc %.4f < %.4f' % (m['edgeNcc'], thr['edgeNcc_fix']))
    if m.get('rgbNcc') is not None and m['rgbNcc'] < thr['rgbNcc_fix']:
        lvl = max(lvl, 2)
        reasons.append('rgbNcc %.4f < %.4f' % (m['rgbNcc'], thr['rgbNcc_fix']))
    if m.get('areaRatio') is not None and abs(m['areaRatio'] - 1.0) > thr['areaRel_fix']:
        lvl = max(lvl, 2)
        reasons.append('areaRatio %.3f' % m['areaRatio'])
    if kp.get('meanDistPx') is not None and kp['meanDistPx'] > thr['kpMean_fix']:
        lvl = max(lvl, 2)
        reasons.append('kpMean %.2f' % kp['meanDistPx'])
    if m.get('edgeNcc') is not None and m['edgeNcc'] < thr['edgeNcc_watch']:
        lvl = max(lvl, 1)
    if m.get('rgbNcc') is not None and m['rgbNcc'] < thr['rgbNcc_watch']:
        lvl = max(lvl, 1)
    return QA_LEVELS[lvl], reasons
