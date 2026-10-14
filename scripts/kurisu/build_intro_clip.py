# -*- coding: utf-8 -*-
"""开场特写：把原包 04-visual-runtime 的 `look_at_CRT_loop` **真序列**打成网页图集。

与上一版的区别（这一版按源码级研究重写）
----------------------------------------
1. 不再"整屏铺满含玻璃边框的成片"，而是照抄原版 `placementMode = "crt_screen"`：
   先按归一化裁剪框 **[113/1398, 119/1125, 1182/1398, 902/1125]** 把外圈玻璃切掉，
   得到的"内屏"再拉伸到 CRT 多边形包围盒（见 §1.5 HOW-IT-WORKS.md）。
2. **逐帧 stride = 1**（不再 stride=3）。原因：这 180 帧里第 **38–43 帧是一次真眨眼**
   （实测闭眼帧 39–42 的虹膜像素≈20，开眼基线≈2100）。stride=3 会把眨眼抽掉。
3. 只发"真正会被看到"的那一段：拼装后的时间线里，特写在 **≈2.0s** 就被交叉淡入到空房间，
   所以只有前 **60 帧**（60×33.3ms = 2.0s）会上屏；其余 120 帧永远看不到，
   发它们只会让图集大 3 倍。默认 `--frames 60`，要全量用 `--frames 180`（脚本支持）。

产物
----
    static/kurisu/full/opening.boot.webp    前 24 帧（首屏用，与 hi 同分辨率 → 切换不跳）
    static/kurisu/full/opening.hi.webp      全部 60 帧（首屏渲染完成后后台补）
    static/kurisu/full/opening.poster.webp  第 0 帧（降级静帧）
    static/kurisu/manifest.json             clips.opening + 首屏预算重算
    _dev/kurisu/opening-blink.png           第 34–48 帧印样（证明眨眼真的在图集里）

用法（仓库根目录）
    python scripts/kurisu/build_intro_clip.py
    python scripts/kurisu/build_intro_clip.py --frames 180 --width 380 --height 290
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_ZIP = r"F:\7AAA\AI\命运石之门\04-visual-runtime\amadeus-visual-runtime-2026-09-26.zip"
ZIP_DIR = "assets/scenarios/runtime/look_at_CRT/look_at_CRT_loop/loop/"

OUT_DIR = os.path.join(REPO, "static", "kurisu")
FULL_DIR = os.path.join(OUT_DIR, "full")
MANIFEST = os.path.join(OUT_DIR, "manifest.json")
DEV_DIR = os.path.join(REPO, "_dev", "kurisu")

# 原版 wallpaper/scene_assets.py:62-67 的内屏裁剪框。
# ⚠️ 原版写的是 [x0, y0, **w**, **h**]（归一化），不是 [x0,y0,x1,y1]：
#     _SCENARIO_DEFAULT_SOURCE_CROP_NORM = [113/1398, 119/1125, 1182/1398, 902/1125]
#     -> 内屏 x 113..1295, y 119..1021 = 1182 x 902（宽高比 1.3102）
#   下面按 [x0,y0,x1,y1] 归一化写出（= 113/1398, 119/1125, (113+1182)/1398, (119+902)/1125）。
#   1070x860 的循环帧与 1398x1125 的场景图宽高比相同（1.2442 vs 1.2427），同一组值可直接用。
CROP_NORM = (113.0 / 1398.0, 119.0 / 1125.0, (113.0 + 1182.0) / 1398.0, (119.0 + 902.0) / 1125.0)

SRC_FRAMES = 180
SOURCE_FPS = 30.0
SOURCE_INTERVAL_MS = 1000.0 / SOURCE_FPS     # 33.333
COLUMNS = 8


def log(msg):
    print(msg, flush=True)


def load_frames(zpath, wanted, crop, size):
    """wanted = 要的源帧号列表（升序）；返回 [(src_idx, Image)]"""
    out = []
    with zipfile.ZipFile(zpath) as z:
        names = set(z.namelist())
        for i in wanted:
            rel = ZIP_DIR + "frame_%04d.png" % i
            if rel not in names:
                raise RuntimeError("素材包里缺 %s" % rel)
            with z.open(rel) as fh:
                im = Image.open(io.BytesIO(fh.read())).convert("RGB")
            if crop:
                w, h = im.size
                box = (int(round(crop[0] * w)), int(round(crop[1] * h)),
                       int(round(crop[2] * w)), int(round(crop[3] * h)))
                im = im.crop(box)
            if im.size != size:
                im = im.resize(size, Image.LANCZOS)
            out.append((i, im))
    return out


def atlas(frames, size, quality, path):
    cols = COLUMNS
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (size[0] * cols, size[1] * rows), (8, 10, 14))
    for n, (_i, im) in enumerate(frames):
        sheet.paste(im, ((n % cols) * size[0], (n // cols) * size[1]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path, "WEBP", quality=quality, method=6)
    return sheet.size


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default=DEFAULT_ZIP)
    ap.add_argument("--frames", type=int, default=60, help="要发多少帧（源帧号 0..frames-1，stride=1）")
    ap.add_argument("--boot", type=int, default=24, help="首屏 boot 图集包含多少帧")
    ap.add_argument("--width", type=int, default=380)
    ap.add_argument("--height", type=int, default=290)
    ap.add_argument("--quality", type=int, default=72)
    ap.add_argument("--no-crop", action="store_true", help="不裁内屏（调试用）")
    args = ap.parse_args()

    if not os.path.exists(args.zip):
        log("找不到素材包：%s" % args.zip)
        return 1

    t0 = time.time()
    crop = None if args.no_crop else CROP_NORM
    frames = load_frames(args.zip, list(range(args.frames)), crop, (args.width, args.height))
    log("读到 %d 帧（stride=1，%dx%d，crop=%s）%.1fs"
        % (len(frames), args.width, args.height, "off" if args.no_crop else "on", time.time() - t0))

    boot = frames[: args.boot]
    hi_p = os.path.join(FULL_DIR, "opening.hi.webp")
    boot_p = os.path.join(FULL_DIR, "opening.boot.webp")
    post_p = os.path.join(FULL_DIR, "opening.poster.webp")

    ahi = atlas(frames, (args.width, args.height), args.quality, hi_p)
    aboot = atlas(boot, (args.width, args.height), args.quality, boot_p)
    frames[0][1].save(post_p, "WEBP", quality=min(90, args.quality + 10), method=6)
    log("hi    %s %dx%d %d 帧 %.1fKB" % (os.path.basename(hi_p), ahi[0], ahi[1], len(frames), os.path.getsize(hi_p) / 1024.0))
    log("boot  %s %dx%d %d 帧 %.1fKB" % (os.path.basename(boot_p), aboot[0], aboot[1], len(boot), os.path.getsize(boot_p) / 1024.0))
    log("poster %.1fKB" % (os.path.getsize(post_p) / 1024.0))

    # ---- 眨眼证据印样：第 34..48 帧 ----
    lo, hi_i = 34, min(48, args.frames - 1)
    if hi_i >= lo:
        sel = [f for f in frames if lo <= f[0] <= hi_i]
        if sel:
            os.makedirs(DEV_DIR, exist_ok=True)
            sc = 1
            w = sel[0][1].size[0] * sc
            h = sel[0][1].size[1] * sc
            sheet = Image.new("RGB", (w * len(sel), h + 16), (16, 16, 20))
            from PIL import ImageDraw
            d = ImageDraw.Draw(sheet)
            for n, (si, im) in enumerate(sel):
                sheet.paste(im, (n * w, 16))
                d.text((n * w + 4, 3), "f%03d" % si, fill=(255, 220, 120))
            bp = os.path.join(DEV_DIR, "opening-blink.png")
            sheet.save(bp)
            log("眨眼印样 %s（第 %d..%d 帧）" % (bp, lo, hi_i))

    # ---- 回填 manifest ----
    with io.open(MANIFEST, encoding="utf-8") as f:
        m = json.load(f)
    m.setdefault("clips", {})["opening"] = {
        "frames": len(frames),
        "frameIntervalMs": SOURCE_INTERVAL_MS,
        "loopMode": "once_then_hold",
        "role": "intro",
        "fit": "crt_screen",          # ★ 裁内屏后拉伸进 CRT 多边形包围盒（不是整屏铺满）
        "next": "empty",
        "columns": COLUMNS,
        "frameWidth": args.width,
        "frameHeight": args.height,
        "source": {
            "bundle": os.path.basename(args.zip),
            "clip": "look_at_CRT_loop",
            "sourceFrames": SRC_FRAMES,
            "sourceFps": SOURCE_FPS,
            "stride": 1,
            "cropNorm": list(CROP_NORM),
            "shippedFrames": len(frames),
            "note": ("原包 look_at_CRT_loop 的真序列（180 帧 @30fps）。逐帧 stride=1，"
                     "所以第 38–43 帧那一次真眨眼在图集里是帧对齐的（实测闭眼 39–42）。"
                     "拼装时间线里特写在 ≈2.0s 被交叉淡入到空房间，故只发前 %d 帧。"
                     % len(frames)),
        },
        "atlas": {
            "boot": {"url": "kurisu/full/opening.boot.webp", "frames": len(boot),
                     "w": aboot[0], "h": aboot[1], "bytes": os.path.getsize(boot_p)},
            "hi": {"url": "kurisu/full/opening.hi.webp", "frames": len(frames),
                   "w": ahi[0], "h": ahi[1], "bytes": os.path.getsize(hi_p),
                   "decodedBytes": ahi[0] * ahi[1] * 4},
        },
        "poster": {"url": "kurisu/full/opening.poster.webp",
                   "w": args.width, "h": args.height, "bytes": os.path.getsize(post_p)},
    }
    # 上一版（整屏铺满 + stride3）的素材作废，别留在库里
    dead = ["full/lookcrt.boot.webp", "full/lookcrt.poster.webp"]
    m.get("clips", {}).pop("lookcrt", None)
    for rel in dead:
        p = os.path.join(OUT_DIR, rel)
        if os.path.exists(p):
            os.remove(p)
            log("已删除作废素材 %s" % rel)

    first = ["full/opening.boot.webp", "full/idle.boot.webp", "full/idle.poster.webp",
             "avatar/normal.idle.webp", "avatar/normal.static.webp"]
    files = {}
    for relp in first:
        p = os.path.join(OUT_DIR, relp)
        if os.path.exists(p):
            files[relp] = os.path.getsize(p)
    b = m.setdefault("budgets", {})
    b["firstScreenFiles"] = files
    b["firstScreenBytes"] = sum(files.values())
    b["note"] = "首屏 = 开场 boot 图集 + idle boot 图集 + 静帧 + 头像静帧；hi 图集首屏渲染完成后后台补"
    with io.open(MANIFEST, "w", encoding="utf-8") as f:
        f.write(json.dumps(m, ensure_ascii=False, indent=1))
        f.write("\n")
    log("manifest.json 已更新：clips.opening + 首屏 %d 字节（%.2fMB）"
        % (b["firstScreenBytes"], b["firstScreenBytes"] / 1048576.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
