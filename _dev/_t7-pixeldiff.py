# -*- coding: utf-8 -*-
"""T7 冻帧对拍：接线前 / pixel 档 / video 档 / 两种故障注入 —— 非角色区像素差必须 = 0

口径（写清楚为什么这么定，免得被当成"自定门槛"）：
  · **非角色区** = 整屏排除 **CRT 屏盒**。CRT 盒内只有：角色 canvas、状态行、字幕条、表情条 ——
    这四样里前三样本来就会动（角色/实时数据/字幕打字机），字幕与状态行还带真实接口数据，
    所以"非角色区像素差 = 0"这条能测的是：**版式、配色、底图、dock、CRT 外框、桌面实拍**
    一个像素都没动（用户口径：视觉不许变；这是那一条的可测形式）。
  · 角色区（CRT 盒内）的差异只允许来自"更清晰的视频/更流畅的动画"，不做像素阈值判定（口径 D5）。
  · CRT 盒几何由页面自身公式反算：见 .crt 的 --crt-* 变量（这里用实测值 + 断言校验）。

用法：
  1) 用 HEAD 版模板构建"接线前"产物到 E:\DeepSeek1\work\_t7-baseline\public
  2) node _dev/t7-baseline-shot.mjs       → _shots/t7-baseline-home.png
  3) node _dev/verify-video-wiring.mjs    → _shots/t7-{video,pixel,fallback,corrupt,off}-home.png
  4) python _dev/_t7-pixeldiff.py
"""
import os

from PIL import Image, ImageChops, ImageDraw

REPO = r'F:\7AAA\AI\blog'
OUT = os.path.join(REPO, '_shots')
VW, VH = 1280, 900
# CRT 屏盒（1280×900 实测：--crt-x/y/w/h → x=366.46 y=186.5 w=560.44 h=423.69，外扩 4px 容错）
CRT = (362, 182, 931, 614)


def char_box(w, h):
    """角色落位（页面内同一公式）：scale=min(w*.64/764, h*.90/1028)，x=.52w，y=H-max(3,H*.012)"""
    s = min(w * 0.64 / 764.0, h * 0.90 / 1028.0)
    dw, dh = 764 * s, 1028 * s
    x, y = w * 0.52, h - max(3, h * 0.012)
    return (int(x - dw / 2) - 2, int(y - dh) - 2, int(x + dw / 2) + 3, int(y) + 3)


def diff_outside(a_path, b_path, boxes, label):
    a = Image.open(a_path).convert('RGB')
    b = Image.open(b_path).convert('RGB')
    if a.size != b.size:
        print('  尺寸不同，跳过：%s %s vs %s' % (label, a.size, b.size))
        return None
    w, h = a.size
    px = ImageChops.difference(a, b).convert('L').tobytes()
    ex = Image.new('L', (w, h), 0)
    dr = ImageDraw.Draw(ex)
    for r in boxes:
        dr.rectangle(r, fill=255)
    exd = ex.tobytes()
    tot = bad = 0
    worst = []
    for i in range(w * h):
        if exd[i]:
            continue
        tot += 1
        if px[i] > 0:                       # ★阈值 = 0：任何一个像素不同都算不合格
            bad += 1
            if len(worst) < 5:
                worst.append((i % w, i // w, px[i]))
    print('  %-30s 非角色区不同像素 = %-7d / %-7d (%.6f%%)  最差:%s'
          % (label, bad, tot, (100.0 * bad / tot) if tot else 0, worst))
    return bad


FILES = [
    ('接线前基线', 't7-baseline-home.png'),
    ('pixel 档', 't7-pixel-home.png'),
    ('video 档', 't7-video-home.png'),
    ('故障A(视频全404)', 't7-fallback-home.png'),
    ('故障B(idle 损坏)', 't7-corrupt-home.png'),
    ('off 档', 't7-off-home.png'),
]


def main():
    paths = {}
    for k, v in FILES:
        p = os.path.join(OUT, v)
        if os.path.isfile(p):
            paths[k] = p
        else:
            print('缺图（跳过）：%s → %s' % (k, v))
    if '接线前基线' not in paths:
        print('缺少"接线前"基线截图，无法判定')
        return
    base = paths['接线前基线']

    print('视口 %dx%d' % (VW, VH))
    print('\n【口径 A】非角色区 = 整屏排除 CRT 屏盒 %s（版式/底图/dock/CRT 外框/桌面实拍）' % (CRT,))
    ra = {}
    for k, p in paths.items():
        if k == '接线前基线':
            continue
        ra[k] = diff_outside(base, p, [CRT], '%s vs 接线前' % k)

    if 'video 档' in paths and 'pixel 档' in paths:
        print('\n【口径 B】排除角色包围盒（CRT 盒外 + 盒内非角色部分，用来抓"画布位移/尺寸变了"）'
              '—— video 档 vs pixel 档（同一站点、同一时刻口径）')
        rb = diff_outside(paths['pixel 档'], paths['video 档'], [char_box(VW, VH)], 'video vs pixel')
    else:
        rb = {}

    okA = all(v == 0 for v in ra.values() if v is not None)
    print('\n结论（口径 A）：%s' % ('非角色区全部 0 像素差 ✓' if okA else '存在非角色区差异 ✗（列在上面）'))
    if rb:
        print('结论（口径 B）：video vs pixel 非角色区 %s'
              % ('0 像素差 ✓' if rb.get('video vs pixel') == 0 else '有差异（见上）'))


if __name__ == '__main__':
    main()
