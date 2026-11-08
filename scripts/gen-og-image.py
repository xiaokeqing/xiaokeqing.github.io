# -*- coding: utf-8 -*-
"""生成 OG / Twitter 分享图（1200×630 JPEG，<200KB）。

为什么单独做一张：
  · 原分享图直接指向 static/images/bg.jpg（3245×1440，674,601 B）—— 社交平台抓一次就是 659KB，
    而且裁成 1.91:1 时人物脸部经常被切掉；
  · 这张用 bg-1920.webp 做底、压暗后写上站名与三个可核对的数字，固定 1200×630 / <200KB。

用法：python scripts/gen-og-image.py
产物：static/images/og-1200x630.jpg
数字口径：24h 告警 78,130 条（README §3 实测值）；27 条攻防用例（/redteam/）；
          41 个只读端点（README N:endpoints）。数字变了就改下面的 STATS 重跑。
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "static" / "images" / "bg-1920.webp"
OUT = ROOT / "static" / "images" / "og-1200x630.jpg"

W, H = 1200, 630
ACCENT = (127, 211, 227)
TEXT = (233, 241, 244)
DIM = (159, 176, 186)

STATS = [("78,130", "24h 告警"), ("27", "条攻防用例"), ("41", "个只读端点")]


def font(path, size):
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / path), size)


def cover(im, w, h):
    sw, sh = im.size
    scale = max(w / sw, h / sh)
    im = im.resize((round(sw * scale), round(sh * scale)), Image.LANCZOS)
    left = (im.width - w) // 2
    top = (im.height - h) // 2
    return im.crop((left, top, left + w, top + h))


def main():
    base = cover(Image.open(SRC).convert("RGB"), W, H)

    # 压暗：整张一层，左侧再压一层，保证文字对比度 ≥ 7:1
    dark = Image.new("RGBA", (W, H), (8, 13, 16, 150))
    base = Image.alpha_composite(base.convert("RGBA"), dark)
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for x in range(W):
        a = int(150 * max(0.0, 1 - x / (W * 0.78)))
        gd.line([(x, 0), (x, H)], fill=(6, 10, 13, a))
    base = Image.alpha_composite(base, grad)
    im = base.convert("RGB")
    d = ImageDraw.Draw(im)

    d.rectangle([0, 0, W, 6], fill=ACCENT)

    f_brand = font("consola.ttf", 22)
    f_title = font("msyh.ttc", 74)
    f_sub = font("consola.ttf", 30)
    f_num = font("msyh.ttc", 46)
    f_lab = font("msyh.ttc", 21)
    f_note = font("msyh.ttc", 19)

    d.text((76, 64), "XK-LAB", font=f_brand, fill=ACCENT)
    d.line([(76, 108), (232, 108)], fill=(127, 211, 227, 120), width=2)

    d.text((76, 152), "公网安全观测站", font=f_title, fill=TEXT)
    d.text((80, 258), "xiaokeqing.cn", font=f_sub, fill=ACCENT)

    d.line([(80, 342), (1120, 342)], fill=(150, 178, 188, 90), width=1)

    x = 80
    for num, lab in STATS:
        d.text((x, 392), num, font=f_num, fill=TEXT)
        nw = d.textlength(num, font=f_num)
        d.text((x + nw + 10, 414), lab, font=f_lab, fill=DIM)
        x += 330

    d.text(
        (80, 540),
        "Wazuh / Suricata / 蜜罐三层告警 · 公开只读接口 · 取不到就写读不到",
        font=f_note,
        fill=(178, 195, 204),
    )
    d.text((1120 - d.textlength("只读 · 可复现", font=f_note), 64), "只读 · 可复现", font=f_note, fill=DIM)

    for q in (88, 84, 80, 76):
        im.save(OUT, "JPEG", quality=q, optimize=True, progressive=True)
        size = OUT.stat().st_size
        if size <= 190 * 1024:
            break
    print("wrote %s  %d bytes  %dx%d  q=%d" % (OUT, OUT.stat().st_size, W, H, q))


if __name__ == "__main__":
    main()
