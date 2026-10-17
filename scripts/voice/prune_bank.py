#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 group / id / source 过滤 kurisu 语音库 bank.json（可重放、可回滚）。

只改 bank.json 的 `lines` 与顶部统计字段；**不删除任何音频/包络文件**。
默认 dry-run，只有显式 `--apply` 才写盘，写盘前先备份 `bank.json.bak-<时间戳>`。

典型用法（在仓库根目录跑，路径都可省略）：

    # 1) 只看：默认 --keep-groups 是全部 7 个组 ⇒ 一条都不删（安全空跑）
    python scripts/voice/prune_bank.py

    # 2) 只看：删掉不可达的老 page_intro（nav_* 之外那 18 条）
    python scripts/voice/prune_bank.py \
        --keep-groups greeting,fallback,faq,status,synth_quiet,idle_banter \
        --keep-ids nav_home,nav_monitor,nav_notes,nav_ai

    # 3) 真写（先备份；默认同时写 static/ 源与 public/ 产物两份）
    python scripts/voice/prune_bank.py --apply --keep-ids ...

写盘后 groups / lineCount / totalBytes 会按保留结果重算；`trigger` / `format` /
`generator` 等其它顶层字段原样保留，缩进与键序也保持（无改动时应与输入逐字节一致）。

退出码：0=正常；1=被安全检查拒绝（未写盘）；2=参数错误。
"""

from __future__ import print_function

import argparse
import io
import json
import os
import sys
import time

# ---------------------------------------------------------------- 常量

DEFAULT_KEEP_GROUPS = "greeting,page_intro,fallback,status,synth_quiet,faq,idle_banter"

DEFAULT_TARGETS = [
    os.path.join("static", "kurisu", "voice", "bank.json"),   # 真源（hugo 从 static 拷进 public）
    os.path.join("public", "kurisu", "voice", "bank.json"),   # 构建产物（当前线上直接服务这份）
]

# 被前端代码硬编码引用的 id —— 删了这些会真的出问题，默认拦住。
# 出处（2026-10-17 核对，行号为当时值）：
#   layouts/index.html:1877-1879  greet_welcome / greet_welcome_back 优先、greet_first / greet_back 兜底
#   layouts/index.html:1896       tab_return
#   static/js/kurisu-player.js:2930,2963,2972,2986,1674  greet_first/greet_back/nav_*/tab_return
#   layouts/partials/xk-demo/idcard.html:293-299        GROUP_OF + EMO_LINE 同上 10 条 + fallback_*
#   _dev/gen-demo-pages.py:3843-3862,3860              LINE_ZH / GROUP_OF 同一批
REFERENCED_IDS = {
    "greet_first": "layouts/index.html:1877-1879 兜底句 + kurisu-player.js:2930 首访开场",
    "greet_back": "layouts/index.html:1877-1879 兜底句 + kurisu-player.js:2930 回访开场",
    "greet_welcome": "layouts/index.html:1877-1879 首访优先句",
    "greet_welcome_back": "layouts/index.html:1877-1879 回访优先句",
    "tab_return": "layouts/index.html:1896 + kurisu-player.js:2986",
    "nav_home": "kurisu-player.js:1674/2963 NAV_VOICE/NAV_LINE",
    "nav_monitor": "kurisu-player.js:1674/2963",
    "nav_notes": "kurisu-player.js:1674/2963",
    "nav_ai": "kurisu-player.js:1674/2963",
    "fallback_no_data": "idcard.html:295 GROUP_OF + EMO_LINE:298",
    "fallback_offline": "idcard.html:295 GROUP_OF",
    "fallback_throttled": "idcard.html:295 GROUP_OF + EMO_LINE:299",
}


# ---------------------------------------------------------------- 工具

def repo_root():
    """脚本位于 <repo>/scripts/voice/ ⇒ 上溯两级即仓库根。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(here))


def split_csv(text):
    out = []
    for part in (text or "").split(","):
        part = part.strip()
        if part:
            out.append(part)
    return out


def line_bytes(rec):
    """单条 line 占的音频字节数：优先 bytes{m4a,webm} 之和，退 audioBytes。"""
    b = rec.get("bytes")
    if isinstance(b, dict) and b:
        total = 0
        for v in b.values():
            try:
                total += int(v)
            except (TypeError, ValueError):
                pass
        if total:
            return total
    try:
        return int(rec.get("audioBytes") or 0)
    except (TypeError, ValueError):
        return 0


def line_seconds(rec):
    try:
        return float(rec.get("seconds") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def mb(n):
    return n / 1048576.0


def fmt_mb(n):
    return "%.2f MB" % mb(n)


def rel(path, root):
    """相对仓库根的显示路径；跨盘符（如 %TEMP% 在 C:）时退回绝对路径。"""
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def line_group(rec):
    """选择层读 (rec.trigger || rec.group)；统计按 group 字段。"""
    return str(rec.get("group") or rec.get("trigger") or "")


# ---------------------------------------------------------------- 核心

def decide(lines, keep_groups, keep_ids, drop_ids, drop_sources):
    """返回 (kept_ids, dropped_ids)。优先级：keep-ids > drop-ids > group > source。"""
    kept, dropped = [], []
    for lid, rec in lines.items():
        group = line_group(rec)
        source = str(rec.get("source") or "")
        if lid in keep_ids:
            kept.append(lid)
        elif lid in drop_ids:
            dropped.append(lid)
        elif group not in keep_groups:
            dropped.append(lid)
        elif source in drop_sources:
            dropped.append(lid)
        else:
            kept.append(lid)
    return kept, dropped


def summarize_for_print(lines, kept, dropped, reserved):
    """按组打印，返回统计 dict。"""
    stats = {"kept": {}, "dropped": {}}
    for lid in kept:
        g = line_group(lines[lid]) or "(无 group)"
        s = stats["kept"].setdefault(g, {"n": 0, "sec": 0.0, "bytes": 0})
        s["n"] += 1
        s["sec"] += line_seconds(lines[lid])
        s["bytes"] += line_bytes(lines[lid])
    for lid in dropped:
        g = line_group(lines[lid]) or "(无 group)"
        s = stats["dropped"].setdefault(g, {"n": 0, "sec": 0.0, "bytes": 0})
        s["n"] += 1
        s["sec"] += line_seconds(lines[lid])
        s["bytes"] += line_bytes(lines[lid])

    groups = sorted(set(stats["kept"]) | set(stats["dropped"]))
    print("")
    print("  组           保留(条/秒/MB)              删除(条/秒/MB)")
    print("  " + "-" * 74)
    for g in groups:
        k = stats["kept"].get(g, {"n": 0, "sec": 0.0, "bytes": 0})
        d = stats["dropped"].get(g, {"n": 0, "sec": 0.0, "bytes": 0})
        flag = ""
        if d["n"] and not k["n"]:
            flag = "  <- 整组清空"
        elif d["n"]:
            flag = "  <- 部分删除"
        print("  %-12s %3d / %8.2fs / %7.2f      %3d / %8.2fs / %7.2f%s"
              % (g, k["n"], k["sec"], mb(k["bytes"]), d["n"], d["sec"], mb(d["bytes"]), flag))
    if reserved:
        print("")
        print("  参考：这 %d 条 id 被前端硬编码引用（建议 --keep-ids 强保留）" % len(reserved))
        for lid in sorted(reserved):
            mark = "删除" if lid in dropped else "保留"
            print("    [%s] %-20s %s" % (mark, lid, REFERENCED_IDS.get(lid, "")))
    return stats


def rebuild(doc, kept, dropped):
    """按保留结果生成新文档：lines 保序、groups 重算、顶部统计字段更新。"""
    lines = doc.get("lines") or {}
    new_lines = dict((lid, lines[lid]) for lid in kept)

    out = {}
    for k, v in doc.items():
        if k == "lines":
            out[k] = new_lines
        elif k == "groups":
            out[k] = None          # 占位，稍后按新结果填
        elif k in ("lineCount", "totalBytes"):
            out[k] = None          # 同上
        else:
            out[k] = v

    group_counts = {}
    total_bytes = 0
    for lid in kept:
        rec = lines[lid]
        g = line_group(rec) or "(无 group)"
        group_counts[g] = group_counts.get(g, 0) + 1
        total_bytes += line_bytes(rec)

    if "lineCount" in doc:
        out["lineCount"] = len(new_lines)
    if "totalBytes" in doc:
        out["totalBytes"] = total_bytes
    if "groups" in doc:
        # 沿用原有键序，再把新出现的组追加在后面
        order = list(doc.get("groups") or {}) + [g for g in group_counts if g not in (doc.get("groups") or {})]
        out["groups"] = dict((g, group_counts[g]) for g in order if g in group_counts)

    # 保持原有键序：groups 未必紧邻 lines
    ordered = {}
    for k in doc.keys():
        ordered[k] = out[k]
    for k, v in out.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


def dump_like_original(doc, sample_text):
    """按原文件的写法序列化：json.dump(indent=1, ensure_ascii=False, 无尾换行)。"""
    text = json.dumps(doc, ensure_ascii=False, indent=1)
    if sample_text.endswith("\n") and not text.endswith("\n"):
        text += "\n"
    elif not sample_text.endswith("\n"):
        text = text.rstrip("\n")
    return text


def read_json(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def main(argv):
    ap = argparse.ArgumentParser(
        description="按 group/id/source 过滤 kurisu voice bank.json（默认 dry-run，不写盘）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", default=False,
                    help="只统计不写盘（默认行为，可显式写出）")
    ap.add_argument("--apply", action="store_true",
                    help="真写盘：先备份 bank.json.bak-<时间戳>，再原子替换")
    ap.add_argument("--bank", default=None,
                    help="目标 bank.json（可逗号分隔多个）；默认 static/ 源 + public/ 产物两份")
    ap.add_argument("--repo", default=None, help="仓库根目录（默认由脚本位置推断）")
    ap.add_argument("--keep-groups", default=DEFAULT_KEEP_GROUPS,
                    help="逗号分隔的保留组名，默认全部 7 组 ⇒ 不删任何一条")
    ap.add_argument("--keep-groups-add", default="", help="在默认/指定组之外额外保留的组")
    ap.add_argument("--keep-ids", default="", help="逗号分隔，额外强保留的 id（优先级最高）")
    ap.add_argument("--drop-ids", default="", help="逗号分隔，明确要删的 id（仍被 --keep-ids 压过）")
    ap.add_argument("--drop-sources", default="",
                    help="逗号分隔，要删的 source（如 synth-rev4）")
    ap.add_argument("--allow-drop-referenced", action="store_true",
                    help="允许删除被前端硬编码引用的 id（默认拒绝）")
    ap.add_argument("--allow-empty-group", action="store_true",
                    help="允许把某个保留组清空（播放器会 NO_SUCH_GROUP，默认拒绝）")
    ap.add_argument("--json", action="store_true", help="额外输出一行机器可读 JSON")
    ap.add_argument("--quiet", action="store_true", help="只输出结论行")
    args = ap.parse_args(argv)

    if args.apply and args.dry_run:
        ap.error("--apply 与 --dry-run 互斥")

    root = os.path.abspath(args.repo) if args.repo else repo_root()

    if args.bank:
        targets = [os.path.abspath(os.path.join(root, p)) if not os.path.isabs(p) else p
                   for p in split_csv(args.bank)]
    else:
        targets = [os.path.join(root, p) for p in DEFAULT_TARGETS]
    targets = [t for t in targets if os.path.isfile(t)]
    if not targets:
        print("找不到 bank.json（试过：%s）" % ", ".join(DEFAULT_TARGETS))
        return 2

    keep_groups = set(split_csv(args.keep_groups)) | set(split_csv(args.keep_groups_add))
    keep_ids = set(split_csv(args.keep_ids))
    drop_ids = set(split_csv(args.drop_ids))
    drop_sources = set(split_csv(args.drop_sources))

    overlap = keep_ids & drop_ids
    if overlap:
        ap.error("--keep-ids 与 --drop-ids 冲突：%s（keep-ids 会赢，但请先改掉）"
                 % ", ".join(sorted(overlap)))

    mode = "APPLY" if args.apply else "DRY-RUN"
    print("=" * 78)
    print("kurisu voice bank 清理  ·  %s  ·  %s" % (mode, time.strftime("%Y-%m-%d %H:%M:%S")))
    print("仓库根 : %s" % root)
    print("目标   : %s" % " , ".join(rel(t, root) for t in targets))
    print("保留组 : %s" % (", ".join(sorted(keep_groups)) or "(空)"))
    if keep_ids:
        print("强保留 : %s" % ", ".join(sorted(keep_ids)))
    if drop_ids:
        print("指定删 : %s" % ", ".join(sorted(drop_ids)))
    if drop_sources:
        print("删来源 : %s" % ", ".join(sorted(drop_sources)))

    plans = []
    for path in targets:
        raw = read_json(path)
        try:
            doc = json.loads(raw)
        except ValueError as e:
            print("解析失败 %s: %s" % (path, e))
            return 1
        lines = doc.get("lines")
        if not isinstance(lines, dict) or not lines:
            print("%s 里没有 lines 字典" % path)
            return 1
        kept, dropped = decide(lines, keep_groups, keep_ids, drop_ids, drop_sources)
        plans.append((path, raw, doc, lines, kept, dropped))

    # 以第一份的判定为准（多份应当完全一致）
    path0, raw0, doc0, lines0, kept0, dropped0 = plans[0]
    print("")
    print("原始 : %d 条 / %s（顶部 lineCount=%s）"
          % (len(lines0), fmt_mb(sum(line_bytes(r) for r in lines0.values())), doc0.get("lineCount")))
    print("保留 : %d 条 / %s" % (len(kept0), fmt_mb(sum(line_bytes(lines0[x]) for x in kept0))))

    reserved = sorted(set(lines0) & set(REFERENCED_IDS))
    if not args.quiet:
        summarize_for_print(lines0, kept0, dropped0, reserved)

    freed_bytes = sum(line_bytes(lines0[x]) for x in dropped0)
    freed_sec = sum(line_seconds(lines0[x]) for x in dropped0)

    print("")
    print("将删除 %d 条 / 释放 %s（%d 字节，约 %.1f 秒台词语音）"
          % (len(dropped0), fmt_mb(freed_bytes), freed_bytes, freed_sec))
    print("（只从 bank.json 的选择池里摘掉；磁盘上的 m4a/webm/包络文件**不动**，"
          "真正的磁盘回收要另外删文件）")

    # ---------------- 安全检查 ----------------
    hard, warn = [], []
    dropped_ref = [x for x in dropped0 if x in REFERENCED_IDS]
    for x in dropped_ref:
        msg = "会删掉被前端硬编码引用的 id：%s（%s）" % (x, REFERENCED_IDS[x])
        (warn if args.allow_drop_referenced else hard).append(msg)
    if dropped_ref and not args.allow_drop_referenced:
        hard.append("→ 如确实要删，先改对应代码，或加 --allow-drop-referenced")

    kept_groups = {}
    for x in kept0:
        g = line_group(lines0[x])
        kept_groups[g] = kept_groups.get(g, 0) + 1
    before_groups = {}
    for x in lines0:
        g = line_group(lines0[x])
        before_groups[g] = before_groups.get(g, 0) + 1
    for g, n in before_groups.items():
        if n and not kept_groups.get(g):
            msg = "保留结果里 %s 组被清空（播放器会返回 NO_SUCH_GROUP，只出字幕）" % g
            (warn if args.allow_empty_group else hard).append(msg)

    if hard:
        print("")
        for p in hard:
            print("! %s" % p)
        print("")
        print("已拒绝：未写盘。")
        return 1
    for p in warn:
        print("! 风险（已按参数放行）：%s" % p)

    summary = {
        "mode": mode,
        "bank_total": len(lines0),
        "keep": len(kept0),
        "drop": len(dropped0),
        "freed_bytes": freed_bytes,
        "freed_mb": round(mb(freed_bytes), 3),
        "freed_seconds": round(freed_sec, 3),
        "dropped_ids": dropped0,
        "new_groups": dict((g, kept_groups[g]) for g in before_groups if g in kept_groups),
    }

    if not args.apply:
        print("")
        print("这是 DRY-RUN，什么都没改。确认后加 --apply 真写（会先备份）。")
        if args.json:
            print("JSON " + json.dumps(summary, ensure_ascii=False))
        return 0

    if not dropped0:
        print("")
        print("保留结果与现状一致（0 条要删），不写盘。")
        if args.json:
            print("JSON " + json.dumps(summary, ensure_ascii=False))
        return 0

    # ---------------- 真写 ----------------
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for path, raw, doc, lines, kept, dropped in plans:
        new_doc = rebuild(doc, kept, dropped)
        text = dump_like_original(new_doc, raw)

        # 写前自检：JSON 能解析、条数对、字节统计对
        check = json.loads(text)
        assert isinstance(check.get("lines"), dict)
        if len(check["lines"]) != len(kept):
            print("自检失败：写出的条数 %d != %d（%s），已中止" % (len(check["lines"]), len(kept), path))
            return 1
        if "totalBytes" in doc:
            want = sum(line_bytes(lines[x]) for x in kept)
            if int(check["totalBytes"]) != want:
                print("自检失败：totalBytes %s != %d（%s），已中止" % (check["totalBytes"], want, path))
                return 1
        if "groups" in doc:
            want = {}
            for x in kept:
                g = line_group(lines[x])
                want[g] = want.get(g, 0) + 1
            if dict(check["groups"]) != want:
                print("自检失败：groups 与保留结果不一致（%s），已中止" % path)
                return 1

        backup = "%s.bak-%s" % (path, stamp)
        with io.open(backup, "wb") as f:
            f.write(raw.encode("utf-8") if isinstance(raw, str) else raw)

        n_before = len(lines)
        tmp = path + ".tmp-prune"
        with io.open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)

        # 写后回读核对
        back = read_json(path)
        if json.loads(back) != json.loads(text):
            print("写后校验失败（%s），可从备份恢复：%s" % (path, backup))
            return 1
        print("已写 %s（%d → %d 条）" % (rel(path, root), n_before, len(kept)))
        print("     备份 %s" % rel(backup, root))

    print("")
    print("完成。回滚：把 bank.json.bak-%s 拷回原名即可。" % stamp)
    print("注意：bank-merged.origfirst.json 与 its counts 未同步 —— 那是 id→文件的分辨率表，"
          "本次不删文件所以仍然有效；如需完全一致，用 _dev/refresh_manifest_voice.py 重建（本脚本不跑它）。")
    if args.json:
        print("JSON " + json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
