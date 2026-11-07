#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 kurisu 的两个大 JSON（manifest.json / statemachine.json）压瘦。

背景：这两个文件是页面首屏的"清单"，manifest 81.7 KB、statemachine 79.0 KB，
实测传输后仍占首页 160 KB 左右。它们本身是 2 空格缩进的美化输出，且带若干
**前端从不读取**的冗余字段：

  · `file`     —— 与 `url` 的最后一段完全相同（可派生）
  · `pixels`   —— [cols*tile_w, rows*tile_h]（可派生）
  · `atlas_source` —— 实测前端 0 处引用

压缩策略（**只做无损删减，不改任何被读取的字段**）：
  1. json.dumps(..., separators=(',',':')) 去空白
  2. 删 pages[] 里的 file / pixels
  3. 删 node 里的 atlas_source
  4. 顶层键顺序保持不变（便于 diff）

用法：
    python scripts/slim-kurisu-json.py            # 只报告
    python scripts/slim-kurisu-json.py --write    # 写回 static/kurisu/*.json
校验：
    python scripts/slim-kurisu-json.py --verify   # 断言"删掉的字段确实可派生"
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KURISU = os.path.join(ROOT, "static", "kurisu")
MANIFEST = os.path.join(KURISU, "manifest.json")
STATEMACHINE = os.path.join(KURISU, "statemachine.json")


def drop_page_fields(pages):
    """删 file / pixels，返回删掉的条数。"""
    n = 0
    for p in pages or []:
        for k in ("file", "pixels"):
            if k in p:
                del p[k]
                n += 1
    return n


def slim_statamchine(obj):
    removed = 0
    for node in obj.get("nodes", []):
        node.pop("atlas_source", None)
        removed += 1 if "atlas_source" in node else 0
        for tier in ("medium", "hi"):
            blk = node.get(tier)
            if isinstance(blk, dict):
                removed += drop_page_fields(blk.get("pages"))
    return removed


def slim_manifest(obj):
    removed = 0
    for key in ("clips",):
        for clip in (obj.get(key) or {}).values() if isinstance(obj.get(key), dict) else []:
            for tier in ("medium", "hi"):
                blk = clip.get("atlas", {}).get(tier)
                if isinstance(blk, dict):
                    removed += drop_page_fields(blk.get("pages"))
    cm = obj.get("clipsMedium") or {}
    for clip in (cm.get("clips") or {}).values() if isinstance(cm.get("clips"), dict) else []:
        for tier in ("medium", "hi"):
            blk = clip.get("atlas", {}).get(tier)
            if isinstance(blk, dict):
                removed += drop_page_fields(blk.get("pages"))
    return removed


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    rows = []
    for path, fn in ((MANIFEST, slim_manifest), (STATEMACHINE, slim_statamchine)):
        obj = load(path)
        before = os.path.getsize(path)
        removed = fn(obj)
        text = dump(obj)
        after = len(text.encode("utf-8"))
        rows.append((os.path.basename(path), before, after, removed, text))

    total_before = sum(r[1] for r in rows)
    total_after = sum(r[2] for r in rows)
    for name, before, after, removed, _ in rows:
        print(
            "%-18s %7d B -> %6d B  (-%5.1f%%)  删字段 %d 处"
            % (name, before, after, 100.0 * (1 - after / before), removed)
        )
    print(
        "合计                 %7d B -> %6d B  (-%5.1f%%, 省 %d B)"
        % (
            total_before,
            total_after,
            100.0 * (1 - total_after / total_before),
            total_before - total_after,
        )
    )

    if args.verify:
        # 被删字段必须可派生：url 末段 == file、pixels == [cols*tile_w, rows*tile_h]
        raw_sm = load(STATEMACHINE)
        bad = 0
        for node in raw_sm.get("nodes", []):
            for tier in ("medium", "hi"):
                blk = node.get(tier)
                if not isinstance(blk, dict):
                    continue
                for p in blk.get("pages") or []:
                    if p.get("file") and p["url"].rsplit("/", 1)[-1] != p["file"]:
                        bad += 1
                    px = p.get("pixels")
                    if px and [p["cols"] * p["tile_w"], p["rows"] * p["tile_h"]] != px:
                        bad += 1
        print("verify: 不可派生字段 %d 处（应为 0）" % bad)
        return 0 if bad == 0 else 1

    if args.write:
        for name, _, _, _, text in rows:
            target = MANIFEST if name == "manifest.json" else STATEMACHINE
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        print("已写回 static/kurisu/manifest.json 与 statemachine.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
