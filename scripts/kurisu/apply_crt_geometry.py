# -*- coding: utf-8 -*-
"""把原版 `wallpaper/crt_config.json` 的几何**换算**进 manifest.json，并打印 CSS 要用的百分比。

为什么要有这一步
----------------
上一版 manifest 里的 `scene.crtRect` = {x:566, y:168, w:608, h:500} **是错的**：
原版的 CRT 屏幕不是矩形，是 `crt_config.json` 里**手写的 14 点多边形**
（`[源码] _amadeus-src/wallpaper/crt_config.json:24-81`）。多边形的包围盒是
x 550..1136、y 195..638（586×443），与那个矩形差得很远（566..1174 / 168..668）。

原版的坐标流水线（照抄）
------------------------
    scale = max(screenW/imgW, screenH/imgH)          # cover
    t.x   = (screenW - imgW*scale) / 2
    t.y   = (screenH - imgH*scale) / 2
    crt_px[i] = { x: poly[i][0]*scale + t.x, y: poly[i][1]*scale + t.y }
    bounds = AABB(crt_px)                            # 角色/场景图的落位基准
    [源码] render/web/wallpaper_scene.js:16-25, 2113-2133

因为 cover 是**等比**的，把 stage 元素做成"按底图比例、cover 铺满视口"的盒子
（CSS: width:max(100vw,177.68vh); height:max(56.28vw,100vh)）之后，
底图坐标 → stage 坐标就只是 `x/1672`、`y/941`，**与视口尺寸无关** —— 所以
下面所有的百分比都可以写死在 CSS 里，不需要 JS 参与。

产物
----
  static/kurisu/manifest.json   scene.crtPolygon / crtBounds / cover / character / sourceCrop
  标准输出                       CSS 可直接粘贴的百分比（多边形 clip-path 顶点等）
"""
from __future__ import annotations

import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST = os.path.join(REPO, "static", "kurisu", "manifest.json")
CRT_CONFIG = r"E:\DeepSeek1\work\_amadeus-src\wallpaper\crt_config.json"

IMG_W, IMG_H = 1672, 941

# 兜底：万一源码 checkout 不在，就用这份逐字抄录（含来源行号）
POLY_FALLBACK = [
    (560, 205), (676, 197), (844, 195), (1014, 198), (1127, 209),
    (1134, 343), (1136, 496), (1130, 628), (1012, 636), (846, 638),
    (676, 634), (556, 626), (550, 494), (552, 342),
]
CORNERS_FALLBACK = [(556, 629), (560, 199), (1127, 204), (1132, 630)]

# 角色落位（[源码] render/web/renderer.js:797-825 + spriteforge_mouth_config.json canvas_size）
CHAR_CANVAS = (764, 1028)
CHAR_MAX_W = 0.64     # b.width  * 0.64
CHAR_MAX_H = 0.90     # b.height * 0.90
CHAR_X = 0.52         # b.x + b.width * 0.52
CHAR_FOOT = 0.012     # b.bottom - max(3, b.height * 0.012)

# 场景图内屏裁剪（[源码] wallpaper/scene_assets.py:62-67）
# ⚠️ 原版是 [x0, y0, w, h]（归一化），**不是** [x0,y0,x1,y1]：
#     [113/1398, 119/1125, 1182/1398, 902/1125] -> x 113..1295, y 119..1021 = 1182x902 (1.3102)
SRC_CROP_XYWH = (113, 119, 1182, 902)
SRC_WH = (1398, 1125)
SUB_PLATE = (2564, 430)


def load_poly():
    """从源码 checkout 读权威多边形；读不到就用兜底并标注"""
    try:
        with io.open(CRT_CONFIG, encoding="utf-8") as f:
            d = json.load(f)
        poly = [tuple(p) for p in d["crt_polygon"]]
        corners = [tuple(p) for p in d.get("crt_corners") or []]
        return poly, corners, "source-checkout:%s" % CRT_CONFIG
    except Exception as e:
        return POLY_FALLBACK, CORNERS_FALLBACK, "fallback(%s)" % e


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    poly, corners, prov = load_poly()
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    bx, by = min(xs), min(ys)
    bw, bh = max(xs) - bx, max(ys) - by

    def pct_abs(v, total):
        return round(v / total * 100.0, 4)

    def pct_rel(v, origin, size):
        return round((v - origin) / size * 100.0, 4)

    poly_abs = [(pct_abs(x, IMG_W), pct_abs(y, IMG_H)) for x, y in poly]
    poly_rel = [(pct_rel(x, bx, bw), pct_rel(y, by, bh)) for x, y in poly]

    print("== 多边形（相对 stage 的百分比，可直接写 CSS）==")
    print("  ".join("%.4f%% %.4f%%" % p for p in poly_abs))
    print("== 多边形（相对包围盒的百分比 → clip-path 顶点）==")
    print(", ".join("%.4f%% %.4f%%" % p for p in poly_rel))
    print("== 包围盒 = 屏内层盒子 ==")
    print("left=%.4f%% top=%.4f%% width=%.4f%% height=%.4f%%"
          % (pct_abs(bx, IMG_W), pct_abs(by, IMG_H), pct_abs(bw, IMG_W), pct_abs(bh, IMG_H)))
    print("  AABB px = x %d..%d, y %d..%d  (%dx%d, ratio %.4f)"
          % (bx, bx + bw, by, by + bh, bw, bh, bw / float(bh)))
    print("== 底图内屏裁剪框 ==")
    _x0, _y0, _w, _h = SRC_CROP_XYWH
    print("  px x %d..%d, y %d..%d = %dx%d, ratio %.4f"
          % (_x0, _x0 + _w, _y0, _y0 + _h, _w, _h, _w / float(_h)))

    with io.open(MANIFEST, encoding="utf-8") as f:
        m = json.load(f)

    scene = m.setdefault("scene", {})
    scene["source"] = {"w": IMG_W, "h": IMG_H,
                       "note": "实拍桌面大图（原版 amadeus_desktop_wallpaper.png）"}
    # ★ 删掉上一版那个"矩形" —— 它和原版多边形对不上
    scene.pop("crtRect", None)
    scene.pop("crtRectNorm", None)
    scene["crtPolygon"] = {
        "provenance": prov,
        "units": "底图 px（1672x941）",
        "points": [[x, y] for x, y in poly],
        "pointsNorm": [[round(x / IMG_W, 6), round(y / IMG_H, 6)] for x, y in poly],
        "pointsPctOfBounds": [[px, py] for px, py in poly_rel],
        "cornersApprox": [[x, y] for x, y in corners],
        "note": ("原版手写的 14 点 CRT 屏幕多边形（不是矩形）。CSS 里用 clip-path: polygon() "
                 "套在 .xk-crt__screen 上，顶点就是 pointsPctOfBounds。"),
    }
    scene["crtBounds"] = {
        "px": {"x": bx, "y": by, "w": bw, "h": bh, "right": bx + bw, "bottom": by + bh},
        "pctOfStage": {"x": pct_abs(bx, IMG_W), "y": pct_abs(by, IMG_H),
                       "w": pct_abs(bw, IMG_W), "h": pct_abs(bh, IMG_H)},
        "aspect": round(bw / float(bh), 6),
        "note": "多边形包围盒；角色落位与场景图拉伸都以它为基准（原版 bounds）",
    }
    scene["cover"] = {
        "imgW": IMG_W, "imgH": IMG_H,
        "css": {
            "width": "max(100vw, 177.68vh)",
            "height": "max(56.28vw, 100vh)",
        },
        "formula": ("scale = max(screenW/imgW, screenH/imgH); "
                    "t.x = (screenW - imgW*scale)/2; t.y = (screenH - imgH*scale)/2; "
                    "stage 元素按底图比例 cover 铺满 → 底图 px 坐标映射到 stage 只是 x/1672、y/941，"
                    "与视口无关，所以百分比可写死"),
        "note": ("★ 2026-10-14 返工：删掉上一版 1.386 倍的『取景放大』。"
                 "实测站主录屏第 2 秒 = 原图 1.00 倍 cover（masked NCC 0.965，屏宽 35.0% vs 预测 35.05%），"
                 "所以正解就是原版的 cover，不加任何倍率。"),
    }
    scene["character"] = {
        "canvasSize": {"w": CHAR_CANVAS[0], "h": CHAR_CANVAS[1]},
        "formula": "scale = min(bounds.w*%.2f/canvasW, bounds.h*%.2f/canvasH); "
                   "x = bounds.x + bounds.w*%.2f; y = bounds.bottom - max(3, bounds.h*%.3f); anchor=(0.5,1.0)"
                   % (CHAR_MAX_W, CHAR_MAX_H, CHAR_X, CHAR_FOOT),
        "maxWidthRatio": CHAR_MAX_W, "maxHeightRatio": CHAR_MAX_H,
        "xRatio": CHAR_X, "footRatio": CHAR_FOOT,
        "source": "render/web/renderer.js:797-825",
    }
    scene["sourceCrop"] = {
        "units": "原版是 [x0,y0,w,h]（归一化，基于 1398x1125）；下面同时给出 [x0,y0,x1,y1] 形式",
        "xywhPx": {"x": SRC_CROP_XYWH[0], "y": SRC_CROP_XYWH[1], "w": SRC_CROP_XYWH[2], "h": SRC_CROP_XYWH[3]},
        "normX0Y0X1Y1": [round(SRC_CROP_XYWH[0] / SRC_WH[0], 6), round(SRC_CROP_XYWH[1] / SRC_WH[1], 6),
                         round((SRC_CROP_XYWH[0] + SRC_CROP_XYWH[2]) / SRC_WH[0], 6),
                         round((SRC_CROP_XYWH[1] + SRC_CROP_XYWH[3]) / SRC_WH[1], 6)],
        "innerScreenPx": {"w": SRC_CROP_XYWH[2], "h": SRC_CROP_XYWH[3],
                          "aspect": round(SRC_CROP_XYWH[2] / float(SRC_CROP_XYWH[3]), 4)},
        "note": ("场景图/特写帧先按这个框裁掉外圈玻璃，再拉伸进 crtBounds（placementMode=crt_screen）。"
                 "内屏宽高比 1.3102 ≈ crtBounds 的 1.3228，这就是『场景图是给这块屏幕准备的』的像素级证据。"),
        "source": "wallpaper/scene_assets.py:62-67",
    }
    scene["subtitlePlate"] = {
        "srcW": SUB_PLATE[0], "srcH": SUB_PLATE[1], "aspect": round(SUB_PLATE[0] / float(SUB_PLATE[1]), 4),
        "formula": ("w = clamp(bounds.w*0.72, 180, bounds.w-24); h = clamp(w/aspect, 34, bounds.h*0.16); "
                    "x = bounds.x + (bounds.w-w)/2; y = bounds.bottom - h"),
        "source": "render/web/wallpaper_scene.js:176-196",
    }
    # 旧的 compose 数值（charHRatio/footYRatio）是"对着视频估的"，已被上面的公式取代
    comp = scene.get("compose")
    if isinstance(comp, dict):
        for k in ("charHRatio", "footYRatio"):
            comp.pop(k, None)
        comp["note"] = ("bgZoom/bgBright/bgSaturate 是底图烘焙时的历史参数；"
                        "角色落位已改用 scene.character 的源码公式，不再用估计值")

    with io.open(MANIFEST, "w", encoding="utf-8") as f:
        f.write(json.dumps(m, ensure_ascii=False, indent=1))
        f.write("\n")
    print("\nmanifest.json 已更新：scene.crtPolygon / crtBounds / cover / character / sourceCrop / subtitlePlate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
