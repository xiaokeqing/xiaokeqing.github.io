#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kurisu 素材流水线：从 Amadeus 官方素材包（KTX2/zip）生成网页可用的 WebP 图集 + manifest.json
================================================================================

为什么需要这个脚本
------------------
1. 浏览器**不能**直接播 KTX2(UASTC+zstd) —— 必须离线转码成 WebP。
2. 角色素材 7552 帧 / 2.48GB，**不能**每帧一个 WebP 请求（120 个请求 = 首屏灾难），
   所以每个剪辑合成**一张大图集**（8 列 × N 行），运行时用 canvas drawImage 切帧。
3. 首屏体积必须 ≤1.5MB，所以每个剪辑额外产出一张 **boot 图集**（只含前 N 帧、与 hi 同分辨率），
   首屏只载 boot（无模糊、可立即播放），hi 图集在首屏渲染完成后后台补；
   两者分辨率相同 ⇒ 切换时**画面不跳变**。

产物（默认写到仓库 static/ 下）
------------------------------
    static/kurisu/manifest.json                 播放器的唯一输入契约（含体积实测）
    static/kurisu/full/<clip>.hi.webp           全帧图集（8 列）
    static/kurisu/full/<clip>.boot.webp         前 N 帧图集（同分辨率，首屏用）
    static/kurisu/full/<clip>.poster.webp       单帧静态图（reduced-motion / 无 JS 降级）
    static/kurisu/avatar/<emo>.idle.webp        头像图集（132px，素材自带，重新打包）
    static/kurisu/avatar/<emo>.speaking.webp    头像说话图集
    static/kurisu/avatar/<emo>.static.webp      头像静态帧（降级用）
    static/images/crt/desk.webp                 CRT 场景底图（实拍书桌，整屏背景）
    static/images/crt/desk-1024.webp            同上，1024 宽（小屏省流量）
    static/images/crt/desk-mobile.webp          竖屏裁切（围绕 CRT，手机用）
    static/images/crt/lab.webp                  CRT 屏幕内的实验室背景（已烤入放大/提亮参数）

可复现性
--------
* 输入全部来自本机素材包 + Amadeus 官方仓库底图；脚本只用 **Python 标准库 + Pillow**。
* 依赖外部可执行文件 `ktx.exe`（Khronos KTX-Software，开发期工具，**不进站点运行时**）。
  获取方式二选一：`npm i ktx2tools`（内含 Windows 二进制）或 winget 安装 KTX-Software。
* 解码结果按条目名缓存到 `--cache-dir`，重跑只补缺失帧（幂等、可中断续跑）。
* 转码参数全部可通过命令行覆盖；默认值就是仓库里当前产物的参数。

用法
----
    python scripts/kurisu/build_kurisu_assets.py                 # 全量构建
    python scripts/kurisu/build_kurisu_assets.py --verify-hashes  # 先校验素材包 SHA256
    python scripts/kurisu/build_kurisu_assets.py --clips idle --limit-frames 8   # 快速自检
    python scripts/kurisu/build_kurisu_assets.py --preview        # 额外输出几何校验图
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageChops, ImageEnhance, ImageMath

# ---------------------------------------------------------------- 默认参数

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

DEFAULT_ZIPS_ROOT = r"F:\7AAA\AI\命运石之门"
DEFAULT_CACHE = r"E:\DeepSeek1\work\_tmp\kurisu-cache"
DEFAULT_WALLPAPER = r"E:\DeepSeek1\work\_probe\wallpaper\amadeus_desktop_wallpaper.png"

WALLPAPER_URL = (
    "https://raw.githubusercontent.com/Code-Amadeus/Amadeus/main/"
    "assets/images/amadeus_desktop_wallpaper.png"
)
# 底图指纹（构建时记录进 manifest；换源会被发现）
WALLPAPER_SHA256 = "EB7B9EEF20B06BECDE6DB2D89D9FF5EF74BD5EEB105D515561846F8F34794514"

CHAR_ZIP_GLOB = ("03-character-kurisu", "*.zip")
VISUAL_ZIP_GLOB = ("04-visual-runtime", "*.zip")
COMPANION_ZIP_GLOB = ("05-companion-kurisu", "*.zip")

CHAR_MANIFEST_IN_ZIP = "assets/spriteforge/runtime/kurisu/runtime_manifest.json"
CHAR_FRAME_PREFIX = "assets/spriteforge/runtime/kurisu/"
COMPANION_PREFIX = "assets/companion/kurisu/"

# 需要转码的剪辑。stride=2 表示隔帧取（59fps→29fps，站立/说话动画肉眼几乎无差，体积减半）
CLIPS = [
    {"name": "idle", "source": "idle", "stride": 2, "boot": 24, "intro": True},
    {"name": "speaking", "source": "speaking_loop1", "stride": 2, "boot": 24},
    {"name": "thinking", "source": "thinking_speaking1", "stride": 2, "boot": 24},
]

COLUMNS = 8          # 图集列数（8 列 × N 行，切帧公式 col=i%8, row=i//8）
HI_HEIGHT = 432      # 全身帧图集高度（源 1028 → 0.42×）
HI_QUALITY = 80
AVATAR_SIZE = 132    # 头像单帧边长（素材原生）
AVATAR_QUALITY = 82
AVATAR_STRIDE_OVER = 64  # 帧数超过此值才隔帧抽
AVATAR_EMOTIONS = [
    "normal", "happy", "sad", "angry",
    "blush", "disappointed", "sided_thinking", "sided_surprised",
]

DESK_FULL_W = 1672
DESK_MID_W = 1024
DESK_QUALITY = 80
LAB_QUALITY = 78

# 合成参数。
# ⚠️ 与 03-技术规格 §四 的差异（站主 2026-10-14 视频校准，优先级更高）：
#   03 给的是 CHAR_H_RATIO=1.16 / FOOT_Y_RATIO=1.22（角色被屏幕裁掉脚，是"贴近"版）；
#   站主看了目标视频后明确要求"**拉远到全身站立**"，所以这里改成 0.68 / 1.00：
#   角色完整站在屏幕地板上、头顶留白、全身可见。屏幕内 UI（字幕条/状态行）的位置不变。
SX0, SY0, SX1, SY1 = 566, 168, 1174, 668      # CRT 屏幕内显示区（源底图坐标）
SW, SH = SX1 - SX0, SY1 - SY0                  # 608 × 500
BG_ZOOM = 1.45
BG_BRIGHT = 1.30
BG_SATURATE = 1.10
CHAR_H_RATIO = 0.68
FOOT_Y_RATIO = 1.00
CRT_RENDER_SCALE = 1.5                         # lab.webp 相对屏幕区的超采样倍率

# 屏幕内 UI 几何（源视频标定，03 §四）：字幕条起于屏幕高 84.5%、高 11.5%；状态行在 3.5%
SUB_BAR_TOP = 0.845
SUB_BAR_H = 0.115
STATUS_TOP = 0.035

INTRO_FRAMES = 1        # "大头出场"用的特写静帧数（原生分辨率，素材里没有独立特写镜头 → 用静帧 + 缩放模拟）
INTRO_HEIGHT = 0        # 0 = 用源帧原生高度（1028）；>0 则缩到该高度

MANIFEST_FORMAT = "xiaokeqing.kurisu.v2"

# 首屏（Hero 首帧）必须能装下的角色相关资源集合
FIRST_SCREEN_KEYS = ["full/idle.intro.webp", "full/idle.boot.webp", "full/idle.poster.webp",
                     "avatar/normal.idle.webp", "avatar/normal.static.webp"]
FIRST_SCREEN_BUDGET = 1_500_000                # 1.5 MB 硬预算


# ---------------------------------------------------------------- 小工具

def log(msg=""):
    print(msg, flush=True)


def human(n):
    if n is None:
        return "-"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % n
        n /= 1024.0


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest().upper()


def pick(*cands):
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def find_ktx(explicit=None):
    cands = [
        explicit,
        os.environ.get("KTX_EXE"),
        r"E:\DeepSeek1\work\_tools\ktx2tools\node_modules\ktx2tools\bin\windows\ktx.exe",
        r"E:\DeepSeek1\work\_probe\node_modules\ktx2tools\bin\windows\ktx.exe",
        os.path.join(REPO, "node_modules", "ktx2tools", "bin", "windows", "ktx.exe"),
        os.path.join(os.path.dirname(REPO), "node_modules", "ktx2tools", "bin", "windows", "ktx.exe"),
        shutil.which("ktx"),
        shutil.which("ktx.exe"),
    ]
    p = pick(*cands)
    if not p:
        die("找不到 ktx 可执行文件。请 `npm i ktx2tools`（开发期依赖）或用 --ktx 指定路径。")
    return p


def die(msg):
    log("错误：" + msg)
    sys.exit(2)


def resize_rgba_premul(im, size):
    """带 alpha 感知的缩放：先预乘 alpha 再缩放，避免透明像素的白色 RGB 渗到边缘形成白边。"""
    r, g, b, a = im.split()
    rgb = Image.merge("RGB", (r, g, b))
    pm = ImageChops.multiply(rgb, a.convert("RGB")).resize(size, Image.LANCZOS)
    a2 = a.resize(size, Image.LANCZOS)

    def un(ch):
        return ImageMath.lambda_eval(
            lambda args: args["convert"](args["c"] * 255 / (args["a"] + 1), "L"),
            c=ch, a=a2)

    pr, pg, pb = pm.split()
    return Image.merge("RGBA", (un(pr), un(pg), un(pb), a2))


def fit_cover(im, tw, th, zoom=1.0, top_bias=0.42):
    """等比铺满 + 可放大（与 docs-plan/tools/compose_scene.py 完全一致）。"""
    r = max(tw / im.width, th / im.height) * zoom
    nw, nh = int(im.width * r), int(im.height * r)
    im2 = im.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    top = int((nh - th) * top_bias)
    return im2.crop((left, top, left + tw, top + th))


# ---------------------------------------------------------------- 源素材

class SourceZips(object):
    def __init__(self, root, overrides=None):
        overrides = overrides or {}
        self.root = root
        self.char_zip = overrides.get("char") or self._find(CHAR_ZIP_GLOB)
        self.visual_zip = overrides.get("visual") or self._find(VISUAL_ZIP_GLOB)
        self.companion_zip = overrides.get("companion") or self._find(COMPANION_ZIP_GLOB)
        for label, p in (("03-character-kurisu", self.char_zip),
                         ("04-visual-runtime", self.visual_zip),
                         ("05-companion-kurisu", self.companion_zip)):
            if not p:
                die("在 %s 下找不到 %s 的 zip" % (root, label))
        self._z = {}

    def _find(self, glob_pair):
        d = os.path.join(self.root, glob_pair[0])
        if not os.path.isdir(d):
            return None
        names = sorted(n for n in os.listdir(d) if n.lower().endswith(".zip"))
        return os.path.join(d, names[0]) if names else None

    def zip(self, which):
        if which not in self._z:
            self._z[which] = zipfile.ZipFile(
                {"char": self.char_zip, "visual": self.visual_zip,
                 "companion": self.companion_zip}[which])
        return self._z[which]


# ---------------------------------------------------------------- ktx 解码

class Decoder(object):
    """KTX2 → PNG（RGBA）。带磁盘缓存，便于中断续跑。

    ⚠️ 坑：ktx.exe 把 PNG 输出到系统 %TEMP% 时会报 permission denied（沙箱/权限）。
       所以中间文件一律写在 `--cache-dir`（默认 E:\\DeepSeek1\\work\\_tmp\\kurisu-cache），
       **不要**改成 tempfile.gettempdir()。
    """

    def __init__(self, ktx_exe, cache_dir, jobs=6):
        self.ktx = ktx_exe
        self.cache = os.path.join(cache_dir, "png")
        self.raw = os.path.join(cache_dir, "ktx2")
        os.makedirs(self.cache, exist_ok=True)
        os.makedirs(self.raw, exist_ok=True)
        self.jobs = jobs

    def _paths(self, entry):
        key = hashlib.sha1(entry.encode("utf-8")).hexdigest()[:20]
        return (os.path.join(self.raw, key + ".ktx2"),
                os.path.join(self.cache, key + ".png"))

    def decode_one(self, entry, data):
        kp, pp = self._paths(entry)
        if not os.path.exists(pp) or os.path.getsize(pp) == 0:
            with open(kp, "wb") as f:
                f.write(data)
            tmp = pp + ".tmp"
            r = subprocess.run([self.ktx, "extract", "--transcode", "rgba8", kp, tmp],
                               capture_output=True)
            if r.returncode != 0 or not os.path.exists(tmp):
                die("ktx extract 失败：%s\n%s" % (entry, r.stderr.decode("utf-8", "replace")[:400]))
            os.replace(tmp, pp)
        return pp

    def decode_many(self, entries, zf, base, label=""):
        """entries 是 zip 内的相对路径列表；返回 PNG 路径列表（顺序一致）。"""
        out = [None] * len(entries)
        todo = []
        for i, rel in enumerate(entries):
            kp, pp = self._paths(base + rel)
            if os.path.exists(pp) and os.path.getsize(pp) > 0:
                out[i] = pp
            else:
                todo.append((i, base + rel))
        if todo:
            if label:
                log("    %s 需解码 %d 帧（其余命中缓存）" % (label, len(todo)))
            t0 = time.time()

            def work(item):
                i, entry = item
                return i, self.decode_one(entry, zf.read(entry))

            with ThreadPoolExecutor(max_workers=self.jobs) as ex:
                for n, (i, pp) in enumerate(ex.map(work, todo), 1):
                    out[i] = pp
                    if n % 20 == 0 or n == len(todo):
                        log("      解码 %d/%d  %.1fs" % (n, len(todo), time.time() - t0))
        return out


# ---------------------------------------------------------------- 图集

def frame_size(src_w, src_h, height):
    fh = int(height)
    fw = max(1, int(round(src_w * height / float(src_h))))
    return fw, fh


def build_atlas(png_paths, out_path, height, columns=COLUMNS, quality=HI_QUALITY):
    """把一串帧打包成一张 8 列图集 WebP（RGBA）。返回 (w, h, bytes)。"""
    with Image.open(png_paths[0]) as im0:
        sw, sh = im0.size
    fw, fh = frame_size(sw, sh, height)
    rows = int(math.ceil(len(png_paths) / float(columns)))
    sheet = Image.new("RGBA", (columns * fw, rows * fh), (0, 0, 0, 0))
    for i, p in enumerate(png_paths):
        with Image.open(p) as im:
            im = im.convert("RGBA")
            sheet.paste(resize_rgba_premul(im, (fw, fh)),
                        ((i % columns) * fw, (i // columns) * fh))
    sheet.save(out_path, "WEBP", quality=quality, method=6)
    return sheet.width, sheet.height, os.path.getsize(out_path)


def build_poster(png_path, out_path, height, quality=HI_QUALITY):
    """单帧静图。height=0/None 时用源帧原生分辨率（"大头出场"的特写静帧就靠这个）。"""
    with Image.open(png_path) as im:
        im = im.convert("RGBA")
        sw, sh = im.size
        fw, fh = (sw, sh) if not height else frame_size(sw, sh, height)
        resize_rgba_premul(im, (fw, fh)).save(out_path, "WEBP", quality=quality, method=6)
    return fw, fh, os.path.getsize(out_path)


# ---------------------------------------------------------------- 场景图

def build_desk(wallpaper_png, out_dir, quality=DESK_QUALITY):
    out = {}
    with Image.open(wallpaper_png) as im:
        im = im.convert("RGB")
        log("    底图源 %s %s" % (im.size, os.path.basename(wallpaper_png)))
        p = os.path.join(out_dir, "desk.webp")
        im.resize((DESK_FULL_W, int(round(im.height * DESK_FULL_W / float(im.width)))),
                  Image.LANCZOS).save(p, "WEBP", quality=quality, method=6)
        out["desk"] = (DESK_FULL_W, os.path.getsize(p))

        p2 = os.path.join(out_dir, "desk-1024.webp")
        im.resize((DESK_MID_W, int(round(im.height * DESK_MID_W / float(im.width)))),
                  Image.LANCZOS).save(p2, "WEBP", quality=quality, method=6)
        out["desk-1024"] = (DESK_MID_W, os.path.getsize(p2))

        # 竖屏裁切：以 CRT 屏幕中心为中心，取 9:19.5 左右的窄条（手机整屏背景用）
        ccx = (SX0 + SX1) / 2.0
        cw = int(round(im.height * 0.462))
        x0 = max(0, min(im.width - cw, int(round(ccx - cw / 2.0))))
        crop = im.crop((x0, 0, x0 + cw, im.height))
        p3 = os.path.join(out_dir, "desk-mobile.webp")
        crop.save(p3, "WEBP", quality=quality, method=6)
        out["desk-mobile"] = (crop.width, os.path.getsize(p3))
    return out


def build_lab(visual_zip, out_dir, quality=LAB_QUALITY):
    """CRT 屏幕内的实验室背景：把 03 规格里锁定的「放大 + 提亮 + 加饱和」参数在构建期烤进图片，
    运行时直接把整张图贴进 CRT 矩形即可，零运行时开销。"""
    name = "assets/scenarios/runtime/BG_empty.png"
    if name not in visual_zip.namelist():
        return None
    with Image.open(io.BytesIO(visual_zip.read(name))) as im:
        im = im.convert("RGB")
        tw, th = int(SW * CRT_RENDER_SCALE), int(SH * CRT_RENDER_SCALE)
        b = fit_cover(im, tw, th, BG_ZOOM).convert("RGB")
        b = ImageEnhance.Brightness(b).enhance(BG_BRIGHT)
        b = ImageEnhance.Color(b).enhance(BG_SATURATE)
        p = os.path.join(out_dir, "lab.webp")
        b.save(p, "WEBP", quality=quality, method=6)
    return (tw, th, os.path.getsize(p))


# ---------------------------------------------------------------- 头像

def build_avatars(companion_zip, out_dir, quality=AVATAR_QUALITY, stride_over=AVATAR_STRIDE_OVER,
                  emotions=None):
    """重新打包素材自带的头像图集：统一成 8 列、并按需隔帧抽（长序列体积）。
    返回 {emotion: {kind: {...}}}"""
    raw = companion_zip.read(COMPANION_PREFIX + "manifest.json")
    src = json.loads(raw.decode("utf-8"))
    out = {}
    os.makedirs(out_dir, exist_ok=True)
    for emo, variants in src["emotions"].items():
        if emotions and emo not in emotions:
            continue
        rec = {}
        for kind in ("idle", "speaking"):
            v = variants.get(kind)
            if not v:
                continue
            with Image.open(io.BytesIO(companion_zip.read(COMPANION_PREFIX + v["url"]))) as atlas:
                atlas = atlas.convert("RGBA")
                size, cols = int(v["size"]), int(v["columns"])
                seq = list(v["sequence"])
                frames = []
                for idx in seq:
                    x, y = (idx % cols) * size, (idx // cols) * size
                    frames.append(atlas.crop((x, y, x + size, y + size)))
                stride = 2 if (stride_over and len(frames) > stride_over) else 1
                kept = frames[::stride]
                rows = int(math.ceil(len(kept) / float(COLUMNS)))
                sheet = Image.new("RGBA", (COLUMNS * size, rows * size), (0, 0, 0, 0))
                for i, fr in enumerate(kept):
                    sheet.paste(fr, ((i % COLUMNS) * size, (i // COLUMNS) * size))
                p = os.path.join(out_dir, "%s.%s.webp" % (emo, kind))
                sheet.save(p, "WEBP", quality=quality, method=6)
                interval = int(round(v.get("durationMs", 0) / float(max(1, len(frames)))))
                rec[kind] = {
                    "url": "kurisu/avatar/%s.%s.webp" % (emo, kind),
                    "frames": len(kept),
                    "columns": COLUMNS,
                    "frameSize": size,
                    "atlasW": sheet.width, "atlasH": sheet.height,
                    "frameIntervalMs": interval,
                    "durationMs": interval * len(kept),
                    "sourceFrames": len(frames),
                    "stride": stride,
                    "bytes": os.path.getsize(p),
                    "decodedBytes": sheet.width * sheet.height * 4,
                }
        if "idle" in rec:
            with Image.open(os.path.join(out_dir, "%s.idle.webp" % emo)) as sheet:
                stat = sheet.crop((0, 0, AVATAR_SIZE, AVATAR_SIZE))
                p = os.path.join(out_dir, "%s.static.webp" % emo)
                stat.save(p, "WEBP", quality=quality, method=6)
            rec["static"] = {"url": "kurisu/avatar/%s.static.webp" % emo,
                             "frameSize": AVATAR_SIZE, "bytes": os.path.getsize(p)}
        out[emo] = rec
    return out


# ---------------------------------------------------------------- 主流程

def verify_outputs(out_dir, crt_dir, manifest, root):
    """fail-closed 自检：产物逐个解码 + 体积下限 + manifest 引用一致性。

    为什么必须有：曾经在一次「边写边被别人检查」的情况下产出过 0 字节的
    `full/thinking.hi.webp` —— 这种文件在页面上就是一张坏图（控制台报错），
    但构建过程完全"成功"。所以这里宁可让脚本失败，也不静默产出坏资产。

    两档严重性（刻意区分）：
      · 硬失败：0 字节 / 解不开 / manifest 引用的文件不存在或字节数不符 / 像素数 > 2000 万
        → 直接 exit 2，拒绝产出。
      · 警告：像素数 > 1200 万（旧 iOS Safari 的画布上限在 1670 万附近）。
        这些图集**只在桌面端**才会被载入（窄屏一律走 132px 头像静帧，
        见 kurisu-player.js 的 staticOnly 判定），所以不是阻断项；但必须打印出来、
        并且会写进 manifest.budgets.warnings，方便下一轮决定要不要降一档。
    """
    log("")
    log("[自检] 逐张解码校验产物（fail-closed）")
    problems = []
    warnings = []
    dirs = [os.path.join(out_dir, "full"), os.path.join(out_dir, "avatar"), crt_dir]
    checked = 0
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            p = os.path.join(d, fn)
            if not os.path.isfile(p) or not fn.lower().endswith(".webp"):
                continue
            sz = os.path.getsize(p)
            if sz < 1024:
                problems.append("%s 体积异常：%d 字节（<1KB，多半是写坏/截断）" % (fn, sz))
                continue
            try:
                with Image.open(p) as im:
                    im.load()
                    w, h = im.size
            except Exception as e:
                problems.append("%s 无法解码：%s" % (fn, e))
                continue
            if w * h > 20_000_000:
                problems.append("%s 像素数 %d 超过 2000 万（移动端大图解码会失败）" % (fn, w * h))
            elif w * h > 12_000_000:
                warnings.append("%s 像素数 %d（>1200 万：仅桌面端会载入，窄屏走头像静帧）" % (fn, w * h))
            checked += 1

    # manifest 里引用的每个 url 都必须真实存在且字节数一致。
    # url 是**相对 static/ 的路径**（kurisu/full/... 与 images/crt/... 两种都在同一根下）。
    static_root = os.path.dirname(out_dir)

    def walk(node):
        if isinstance(node, dict):
            if "url" in node and isinstance(node["url"], str) and node["url"].endswith(".webp"):
                rel = node["url"]
                p = os.path.join(static_root, rel.replace("/", os.sep))
                if not os.path.exists(p):
                    problems.append("manifest 引用了不存在的文件：%s" % rel)
                elif "bytes" in node and os.path.getsize(p) != node["bytes"]:
                    problems.append("manifest 字节数与文件不符：%s（%d ≠ %d）"
                                    % (rel, node["bytes"], os.path.getsize(p)))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(manifest)
    if warnings:
        log("  ⚠ 警告（不阻断）：")
        for w in warnings:
            log("     - %s" % w)
    if problems:
        log("  ❌ 自检未通过（%d 项）：" % len(problems))
        for p in problems:
            log("     - %s" % p)
        die("产物自检失败 —— 已拒绝产出（修好再跑；不要带着坏资产上线）")
    log("  ✅ %d 张 WebP 全部可解码、体积正常、manifest 引用一致" % checked)
    return {"checked": checked, "warnings": warnings}


def dir_size(d):
    tot = 0
    for root, _dirs, files in os.walk(d):
        for fn in files:
            tot += os.path.getsize(os.path.join(root, fn))
    return tot


def reuse_dims(paths):
    """--reuse 用：所有目标文件都在且 >1KB 时，返回 {path: (w, h, bytes)}，否则 None。"""
    for p in paths:
        if not (os.path.exists(p) and os.path.getsize(p) > 1024):
            return None
    out = {}
    for p in paths:
        try:
            with Image.open(p) as im:
                out[p] = (im.width, im.height, os.path.getsize(p))
        except Exception:
            return None
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="kurisu 素材流水线（KTX2 → WebP 图集 + manifest）")
    ap.add_argument("--zips-root", default=DEFAULT_ZIPS_ROOT)
    ap.add_argument("--char-zip"), ap.add_argument("--visual-zip"), ap.add_argument("--companion-zip")
    ap.add_argument("--wallpaper", default=None, help="实拍书桌底图 PNG（默认用本机缓存副本）")
    ap.add_argument("--fetch-sources", action="store_true", help="底图缺失时从 Amadeus 官方仓库下载")
    ap.add_argument("--ktx", default=None, help="ktx 可执行文件路径")
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE)
    ap.add_argument("--out", default=os.path.join(REPO, "static", "kurisu"))
    ap.add_argument("--crt-out", default=os.path.join(REPO, "static", "images", "crt"))
    ap.add_argument("--hi-height", type=int, default=HI_HEIGHT)
    ap.add_argument("--hi-quality", type=int, default=HI_QUALITY)
    ap.add_argument("--intro-height", type=int, default=INTRO_HEIGHT,
                    help="'大头出场'特写静帧的高度；0 = 源帧原生高度（1028，最清晰）")
    ap.add_argument("--stride", type=int, default=None, help="覆盖所有剪辑的隔帧步长")
    ap.add_argument("--clips", default=None, help="只构建指定剪辑（逗号分隔，调试用）")
    ap.add_argument("--limit-frames", type=int, default=0, help="每个剪辑只取前 N 帧（调试用）")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--avatar-quality", type=int, default=AVATAR_QUALITY)
    ap.add_argument("--avatar-emotions", default=None)
    ap.add_argument("--skip-avatars", action="store_true")
    ap.add_argument("--skip-scene", action="store_true")
    ap.add_argument("--verify-hashes", action="store_true", help="校验素材包 SHA256（慢，2.6GB）")
    ap.add_argument("--reuse", action="store_true",
                    help="已存在的图集/静帧直接复用（跳过解码与重编码）；改过转码参数就别用")
    ap.add_argument("--preview", action="store_true", help="输出几何校验图（CT 场景合成预览）")
    ap.add_argument("--report", default=None, help="把体积报告写到这个 json 路径")
    args = ap.parse_args()

    t_start = time.time()
    log("=" * 78)
    log("kurisu 素材流水线")
    log("=" * 78)

    if args.verify_hashes:
        verify_hashes(args.zips_root)

    src = SourceZips(args.zips_root, {"char": args.char_zip, "visual": args.visual_zip,
                                     "companion": args.companion_zip})
    log("素材包：")
    for label, p in (("03 角色", src.char_zip), ("04 场景", src.visual_zip),
                     ("05 头像", src.companion_zip)):
        log("  %-8s %10s  %s" % (label, human(os.path.getsize(p)), p))

    ktx = find_ktx(args.ktx)
    log("ktx：%s" % ktx)
    dec = Decoder(ktx, args.cache_dir, jobs=args.jobs)

    os.makedirs(args.out, exist_ok=True)
    os.makedirs(os.path.join(args.out, "full"), exist_ok=True)
    os.makedirs(args.crt_out, exist_ok=True)

    # ---- 1) 角色全身剪辑 → 图集 --------------------------------------
    zf = src.zip("char")
    rman = json.loads(zf.read(CHAR_MANIFEST_IN_ZIP).decode("utf-8"))
    clips_src = rman["clips"]
    want = [c.strip() for c in args.clips.split(",")] if args.clips else None

    manifest_clips = {}
    order = list(CLIPS)
    if want:
        order = [c for c in CLIPS if c["name"] in want]
        if not order:
            die("--clips 里没有匹配的剪辑：%s（可选 %s）"
                % (want, ",".join(c["name"] for c in CLIPS)))

    for cfg in order:
        name, sname = cfg["name"], cfg["source"]
        if sname not in clips_src:
            log("  跳过 %s：源素材里没有剪辑 %s" % (name, sname))
            continue
        src_clip = clips_src[sname]
        all_frames = src_clip["frames"]
        stride = args.stride or cfg["stride"]
        picked = all_frames[::stride]
        if args.limit_frames:
            picked = picked[:args.limit_frames]
        interval = int(round(src_clip["frameIntervalMs"] * stride))
        log("")
        log("[剪辑] %s  ← %s：源 %d 帧 / %dms，取 %d 帧（stride=%d，%dms/帧）"
            % (name, sname, len(all_frames), src_clip["frameIntervalMs"], len(picked), stride, interval))

        hi_p = os.path.join(args.out, "full", name + ".hi.webp")
        boot_p = os.path.join(args.out, "full", name + ".boot.webp")
        post_p = os.path.join(args.out, "full", name + ".poster.webp")
        intro_p = os.path.join(args.out, "full", name + ".intro.webp")
        boot_n = min(cfg["boot"], len(picked))

        # --reuse：图集/静帧已存在且达标时跳过解码与重编码（只用于反复调下层的迭代；
        # 转码参数变了就必须去掉这个开关，否则会沿用旧图）
        want = [hi_p, boot_p, post_p] + ([intro_p] if cfg.get("intro") else [])
        dims = reuse_dims(want) if args.reuse else None
        if dims:
            log("    复用已有产物（--reuse）：%s" % ", ".join(
                "%s %dx%d" % (os.path.basename(p), dims[p][0], dims[p][1]) for p in want))
            hw, hh, hb = dims[hi_p]
            bw, bh, bb = dims[boot_p]
            fw, fh, pb = dims[post_p]
            intro_rec = None
            if cfg.get("intro"):
                iw, ihh, ib = dims[intro_p]
                intro_rec = {"url": "kurisu/full/%s.intro.webp" % name, "w": iw, "h": ihh,
                             "bytes": ib,
                             "note": "素材无独立特写帧：用 idle 首帧原生分辨率当特写，"
                                     "运行时 transform scale 缩回全身"}
        else:
            pngs = dec.decode_many(picked, zf, CHAR_FRAME_PREFIX, label=name)
            boot_n = min(boot_n, len(pngs))
            hw, hh, hb = build_atlas(pngs, hi_p, args.hi_height, quality=args.hi_quality)
            bw, bh, bb = build_atlas(pngs[:boot_n], boot_p, args.hi_height, quality=args.hi_quality)
            fw, fh, pb = build_poster(pngs[0], post_p, args.hi_height, quality=args.hi_quality)
            # "大头出场"的特写静帧：素材里【没有】独立的贴脸镜头，
            # 所以拿 idle 首帧的【原生分辨率】当特写底图，运行时用 transform scale 从特写缩到全身。
            intro_rec = None
            if cfg.get("intro"):
                iw, ihh, ib = build_poster(pngs[0], intro_p, args.intro_height)
                intro_rec = {"url": "kurisu/full/%s.intro.webp" % name,
                             "w": iw, "h": ihh, "bytes": ib,
                             "note": "素材无独立特写帧：用 idle 首帧原生分辨率当特写，"
                                     "运行时 transform scale 缩回全身"}
                log("    intro %dx%d  %8s（原生分辨率特写静帧）" % (iw, ihh, human(ib)))
        log("    hi  %dx%d  %8s" % (hw, hh, human(hb)))
        log("    boot(%d帧) %dx%d  %8s" % (boot_n, bw, bh, human(bb)))
        log("    poster %dx%d  %8s" % (fw, fh, human(pb)))

        manifest_clips[name] = {
            "frames": len(picked),
            "frameIntervalMs": interval,
            "loopMode": src_clip.get("loopMode", "loop"),
            "frameWidth": fw, "frameHeight": fh, "columns": COLUMNS,
            "rows": int(math.ceil(len(picked) / float(COLUMNS))),
            "source": {"clip": sname, "frames": len(all_frames),
                       "frameIntervalMs": src_clip["frameIntervalMs"], "stride": stride},
            "atlas": {
                "hi": {"url": "kurisu/full/%s.hi.webp" % name, "w": hw, "h": hh,
                       "bytes": hb, "decodedBytes": hw * hh * 4},
                "boot": {"url": "kurisu/full/%s.boot.webp" % name, "frames": boot_n,
                         "w": bw, "h": bh, "bytes": bb, "decodedBytes": bw * bh * 4},
            },
            "poster": {"url": "kurisu/full/%s.poster.webp" % name, "w": fw, "h": fh, "bytes": pb},
            "intro": intro_rec,
        }

    # ---- 2) 头像 -----------------------------------------------------
    manifest_emotions = {}
    if not args.skip_avatars:
        log("")
        log("[头像] 从 05 包重新打包（132px，8 列）")
        emos = [e.strip() for e in args.avatar_emotions.split(",")] if args.avatar_emotions else AVATAR_EMOTIONS
        manifest_emotions = build_avatars(
            src.zip("companion"), os.path.join(args.out, "avatar"),
            quality=args.avatar_quality, emotions=emos)
        for emo, rec in manifest_emotions.items():
            log("    %-18s idle=%-6s speaking=%s"
                % (emo,
                   human(rec.get("idle", {}).get("bytes")),
                   human(rec.get("speaking", {}).get("bytes"))))

    # ---- 3) 场景图 ---------------------------------------------------
    scene = {}
    if not args.skip_scene:
        log("")
        log("[场景] CRT 底图 + 屏幕内实验室背景")
        wall = args.wallpaper or pick(DEFAULT_WALLPAPER,
                                     os.path.join(args.cache_dir, "sources",
                                                  "amadeus_desktop_wallpaper.png"))
        if not wall and args.fetch_sources:
            wall = fetch_wallpaper(os.path.join(args.cache_dir, "sources"))
        if not wall:
            log("    ⚠ 找不到底图；用 --wallpaper 指定，或加 --fetch-sources 让脚本下载")
        else:
            h = sha256_file(wall)
            if h != WALLPAPER_SHA256:
                log("    ⚠ 底图 SHA256 与预期不同：%s" % h)
            else:
                log("    底图 SHA256 校验通过")
            sizes = build_desk(wall, args.crt_out)
            for k, (w, b) in sizes.items():
                log("    %-14s w=%-6d %8s" % (k, w, human(b)))
            scene["desk"] = {
                "url": "images/crt/desk.webp", "w": DESK_FULL_W, "bytes": sizes["desk"][1]}
            scene["desk1024"] = {
                "url": "images/crt/desk-1024.webp", "w": DESK_MID_W, "bytes": sizes["desk-1024"][1]}
            scene["deskMobile"] = {
                "url": "images/crt/desk-mobile.webp", "w": sizes["desk-mobile"][0],
                "bytes": sizes["desk-mobile"][1]}
            # 只留指纹、不留 URL：manifest 是**运行时**文件（播放器要 fetch 它），
            # 站点运行时零外链 —— 来源 URL 属于文档（scripts/kurisu/README.md 与 docs/）。
            scene["wallpaperSha256"] = h

        lab = build_lab(src.zip("visual"), args.crt_out)
        if lab:
            log("    %-14s %dx%d %8s" % ("lab", lab[0], lab[1], human(lab[2])))
            scene["lab"] = {"url": "images/crt/lab.webp", "w": lab[0], "h": lab[1], "bytes": lab[2]}

    # ---- 4) manifest -------------------------------------------------
    clip_dir = os.path.join(args.out, "full")
    av_dir = os.path.join(args.out, "avatar")
    first_screen = {}
    for key in FIRST_SCREEN_KEYS:
        p = os.path.join(args.out, key.replace("/", os.sep))
        if os.path.exists(p):
            first_screen[key] = os.path.getsize(p)
    first_total = sum(first_screen.values())

    manifest = {
        "format": MANIFEST_FORMAT,
        "generator": {
            "script": "scripts/kurisu/build_kurisu_assets.py",
            "builtAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ktx": os.path.basename(ktx),
            "sourceManifestSha256": hashlib.sha256(
                zf.read(CHAR_MANIFEST_IN_ZIP)).hexdigest().upper(),
            "wallpaperSha256": WALLPAPER_SHA256,
        },
        "budgets": {
            "firstScreenBudgetBytes": FIRST_SCREEN_BUDGET,
            "firstScreenBytes": first_total,
            "firstScreenFiles": first_screen,
            "note": "首屏只载 idle.boot + 静态头像；hi 图集在首屏渲染完成后 200ms 后台补",
        },
        "scene": {
            "source": {"w": DESK_FULL_W, "h": 941},
            "crtRect": {"x": SX0, "y": SY0, "w": SW, "h": SH},
            "crtRectNorm": {"x": round(SX0 / float(DESK_FULL_W), 6),
                            "y": round(SY0 / 941.0, 6),
                            "w": round(SW / float(DESK_FULL_W), 6),
                            "h": round(SH / 941.0, 6)},
            "compose": {"charHRatio": CHAR_H_RATIO, "footYRatio": FOOT_Y_RATIO,
                        "bgZoom": BG_ZOOM, "bgBright": BG_BRIGHT, "bgSaturate": BG_SATURATE},
            "images": scene,
        },
        "clips": manifest_clips,
        "emotions": manifest_emotions,
    }
    # 先自检（fail-closed），再把自检里的警告写进 manifest —— 这样"能不能发布"
    # 与"哪些资产偏大"都留在了产物自身里，而不是只留在构建日志里。
    check = verify_outputs(args.out, args.crt_out, manifest, REPO)
    manifest["budgets"]["warnings"] = check["warnings"]

    mpath = os.path.join(args.out, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    log("")
    log("=" * 78)
    log("产物清单（%s）" % args.out)
    log("=" * 78)
    rows = []
    for d, label in ((clip_dir, "full"), (av_dir, "avatar")):
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            p = os.path.join(d, fn)
            rows.append((label + "/" + fn, os.path.getsize(p)))
    for fn, sz in sorted(rows, key=lambda r: -r[1]):
        log("  %-34s %10s" % (fn, human(sz)))
    log("  %-34s %10s  (%d 个文件)" % ("full/ 合计", human(dir_size(clip_dir)),
                                       len(os.listdir(clip_dir)) if os.path.isdir(clip_dir) else 0))
    if os.path.isdir(av_dir):
        log("  %-34s %10s  (%d 个文件)" % ("avatar/ 合计", human(dir_size(av_dir)),
                                           len(os.listdir(av_dir))))
    log("  %-34s %10s" % ("场景图合计", human(dir_size(args.crt_out))))
    log("  %-34s %10s" % ("kurisu/ 合计", human(dir_size(args.out))))
    log("")
    log("首屏角色资源（≤ %s 硬预算）：" % human(FIRST_SCREEN_BUDGET))
    for k, v in first_screen.items():
        log("  %-34s %10s" % (k, human(v)))
    log("  %-34s %10s  %s" % ("合计", human(first_total),
                              "✅ 在预算内" if first_total <= FIRST_SCREEN_BUDGET else "❌ 超预算"))
    log("")
    log("manifest -> %s（%s）" % (mpath, human(os.path.getsize(mpath))))
    log("总耗时 %.1fs" % (time.time() - t_start))

    if args.report:
        files = [{"path": r[0], "bytes": r[1]} for r in rows]
        files += [{"path": k, "bytes": v} for k, v in first_screen.items()]
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump({"manifest": manifest, "files": files,
                       "totals": {"kurisu": dir_size(args.out), "crt": dir_size(args.crt_out)}},
                      f, ensure_ascii=False, indent=1)
        log("报告 -> %s" % args.report)

    if args.preview:
        preview(args.out, args.crt_out, manifest)


def fetch_wallpaper(dest_dir):
    import urllib.request
    os.makedirs(dest_dir, exist_ok=True)
    p = os.path.join(dest_dir, "amadeus_desktop_wallpaper.png")
    log("    下载官方底图 -> %s" % p)
    urllib.request.urlretrieve(WALLPAPER_URL, p)
    return p


def verify_hashes(root):
    log("[校验] 素材包 SHA256")
    for sub in ("03-character-kurisu", "04-visual-runtime", "05-companion-kurisu"):
        d = os.path.join(root, sub)
        sums = os.path.join(d, "SHA256SUMS.txt")
        if not os.path.isfile(sums):
            log("  %-22s 无 SHA256SUMS.txt，跳过" % sub)
            continue
        line = open(sums, encoding="utf-8", errors="replace").read().strip().splitlines()[0]
        parts = line.split()
        want = parts[0].upper()
        names = [n for n in os.listdir(d) if n.lower().endswith(".zip")]
        if not names:
            continue
        zip_p = os.path.join(d, names[0])
        t0 = time.time()
        got = sha256_file(zip_p)
        log("  %-22s %s  %s (%.0fs)" % (sub, "✅" if got == want else "❌ 不一致",
                                        got[:16] + "...", time.time() - t0))
    log("")


def preview(out_dir, crt_dir, manifest):
    """按 manifest 里的几何参数合成预览图（不参与站点运行，仅用于核对几何/色值/开场）。

    ⚠️ 关键：角色必须【裁剪在 CRT 屏幕矩形内】（源工具 compose_scene.py 就是先合成到
       一张 SW×SH 的透明层、再贴到屏幕上）。不裁剪的话角色的腿会溢到显像管边框上。
    """
    from PIL import ImageDraw, ImageFont
    pv_dir = os.path.join(REPO, "_dev", "kurisu")
    os.makedirs(pv_dir, exist_ok=True)
    desk = Image.open(os.path.join(crt_dir, "desk.webp")).convert("RGBA")
    lab_p = os.path.join(crt_dir, "lab.webp")

    def font(sz):
        for f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
            if os.path.exists(f):
                try:
                    return ImageFont.truetype(f, sz)
                except Exception:
                    pass
        return ImageFont.load_default()

    def screen_layer(sw, sh, char_img, subtitle, status, char_scale=1.0, char_origin=(0.5, 0.08)):
        """把"屏幕里能看到的一切"（背景 + 角色 + 屏内 UI）画到一张 sw×sh 的层上。

        char_scale / char_origin 用来复现运行时的"大头出场"：
        运行时是给角色图加 CSS transform: scale(k) 且 transform-origin 落在头部，
        所以这里也只缩放**角色**（背景与字幕条不动），缩放中心 = 角色框内的 (0.5, 0.08)。
        """
        layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        if os.path.exists(lab_p):
            with Image.open(lab_p) as lab:
                layer.alpha_composite(lab.convert("RGBA").resize((sw, sh), Image.LANCZOS), (0, 0))
        if char_img is not None:
            chh = int(sh * CHAR_H_RATIO)
            chw = int(char_img.width * chh / float(char_img.height))
            cx = (sw - chw) / 2.0
            cy = sh * FOOT_Y_RATIO - chh
            cimg = char_img.resize((chw, chh), Image.LANCZOS)
            if char_scale and char_scale != 1.0:
                k = char_scale
                ox = cx + char_origin[0] * chw
                oy = cy + char_origin[1] * chh
                nw, nh = int(chw * k), int(chh * k)
                cimg = cimg.resize((nw, nh), Image.LANCZOS)
                cx, cy = ox - nw * char_origin[0], oy - nh * char_origin[1]
            # 贴到临时层上 = 自动裁剪到屏幕矩形内（源合成脚本就是这么做的）
            tmp = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            tmp.alpha_composite(cimg, (int(round(cx)), int(round(cy))))
            layer.alpha_composite(tmp, (0, 0))
        d = ImageDraw.Draw(layer, "RGBA")
        # 底部字幕条（源视频标定：起于屏高 84.5%、高 11.5%）
        by0 = int(sh * SUB_BAR_TOP)
        bh = int(sh * SUB_BAR_H)
        d.rectangle([int(sw * 0.06), by0, sw - int(sw * 0.06), by0 + bh], fill=(10, 12, 16, 205))
        fs = max(11, int(bh * 0.42))
        d.text((int(sw * 0.09), by0 + int(bh * 0.30)), subtitle, font=font(fs), fill=(238, 240, 246))
        # 右上状态行（屏高 3.5%）
        sy2 = int(sh * STATUS_TOP)
        d.text((int(sw * 0.52), sy2), status, font=font(max(9, int(sh * 0.026))), fill=(150, 200, 160))
        d.ellipse([sw - int(sw * 0.055), sy2, sw - int(sw * 0.030), sy2 + int(sh * 0.022)],
                  fill=(90, 210, 130))
        return layer

    poster = intro = None
    fp = os.path.join(out_dir, "full", "idle.poster.webp")
    if os.path.exists(fp):
        poster = Image.open(fp).convert("RGBA")
    fi = os.path.join(out_dir, "full", "idle.intro.webp")
    if os.path.exists(fi):
        intro = Image.open(fi).convert("RGBA")

    for width, name, img, subtitle, k in (
            (1280, "preview-1280.webp", poster, "这里是安全运营工作台 —— 数据都是真实在跑的。", 1.0),
            (390, "preview-390.webp", poster, "数据来自真实接口，读不到就直说。", 1.0),
            (1280, "preview-intro-1280.webp", intro, "大头出场：贴脸特写 → 拉远到全身（transform scale）", 2.6)):
        th = int(round(width * 9 / 16.0))
        r = max(width / float(desk.width), th / float(desk.height))
        W, H = int(round(desk.width * r)), int(round(desk.height * r))
        left = (W - width) // 2
        canvas = desk.resize((W, H), Image.LANCZOS).crop((left, 0, left + width, th))
        sx, sy = SX0 * r - left, SY0 * r
        sw, sh = int(round(SW * r)), int(round(SH * r))
        layer = screen_layer(sw, sh, img, subtitle, "运行中 · 待处理 N · 已处置 N", char_scale=k)
        canvas.alpha_composite(layer, (int(sx), int(sy)))
        canvas.convert("RGB").save(os.path.join(pv_dir, name), "WEBP", quality=82, method=6)
        log("    预览 -> %s" % os.path.join(pv_dir, name))


if __name__ == "__main__":
    main()
