# -*- coding: utf-8 -*-
"""原声资产核查（只读）：bank.json 的 line 引用 与 static/kurisu/voice/ 实际文件 对账。

为什么：语音资产是「清单驱动」的——页面上能播什么，由 bank.json 的 154 条 line
决定，不是由目录里躺着几个文件决定。清单和磁盘一旦脱钩，会出现两种病：
  1) 清单里有、磁盘上没有  -> 线上点了没声（破音），最严重；
  2) 磁盘上有、清单里没有  -> 孤儿文件，白占体积、混淆后续清理判断。
本脚本只读，不改不删不动任何文件；孤儿只列清单。

口径（三组数字）：
  A 引用数  ：bank.json 的 line 条数 / 去重后被引用的音频文件数 / 信封文件数
              （同一个路径被多条 line 引用时只算 1 个文件，另记「引用条目数」）
  B 实际数  ：磁盘上 .m4a 与 .webm 的实际文件数（按扩展名分别计数）+ 字节体积
  C 孤儿数  ：B(音频文件) - A(被引用音频文件)，逐文件列出；体积取磁盘真实大小
  另外单独报「缺失引用」（A 有、B 没有）——它才是会掉音的那一类，退出码用它。

路径口径：bank.json 里的路径是站点相对路径，锚在 `static/` 下，例如
`kurisu/voice/synth/faq_m46.m4a` -> `static/kurisu/voice/synth/faq_m46.m4a`。

交叉口径：voice 目录里还有别的清单（orig/bank-orig.json、bank-merged.origfirst.json）。
它们引用的文件对 *bank.json* 而言仍是孤儿，但删了会破坏别的清单——所以孤儿表里
额外标一列「其他清单是否还引用」，避免把溯源音源当成垃圾清掉。

用法：
  python scripts/voice-audit.py                 # 人读报告
  python scripts/voice-audit.py --json out.json  # 机器可读（仍打印人读报告）
  python scripts/voice-audit.py --check-sha     # 额外校验 sha256/bytes 是否与磁盘一致
  python scripts/voice-audit.py --quiet         # 只打印三组数字与有问题的行

退出码：0 = 引用全部落地；1 = 存在缺失引用（破音风险）；2 = 参数/读盘错误。
孤儿不影响退出码（孤儿不是故障，是需要人判断的资产决策）。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys

AUDIO_EXTS = (".m4a", ".webm")
ENVELOPE_SUFFIX = ".envelope.json"
MANIFEST_NAMES = ("bank.json", "bank-orig.json", "bank-merged.origfirst.json")


# ---------------------------------------------------------------- 基础工具

def setup_stdout():
    """Windows 控制台默认 GBK，中文/箭头符号会炸；统一成 utf-8。"""
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass


def load_json(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def human(n):
    """字节 -> 1.23 MiB 这类可读值；报告里同时给精确字节。"""
    if n is None:
        return "-"
    step = 1024.0
    v = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(v) < step or unit == "GiB":
            return ("%d B" % int(v)) if unit == "B" else ("%.2f %s" % (v, unit))
        v /= step
    return "%.2f GiB" % v


def norm_rel(p):
    """统一成 / 分隔、无前导斜杠的站点相对路径。"""
    if not p:
        return None
    return p.replace("\\", "/").lstrip("./").lstrip("/")


# ---------------------------------------------------------------- 引用侧

def collect_refs(bank, static_root, check_sha=False):
    """从 bank.json 抽引用。返回 (refs, refs_entries, missing, integrity)。

    refs: {rel_audio_path: set(line_id)}   —— 用于算「被引用文件数」
    refs_entries: 引用条目总数（同文件被多条 line 引用时重复计数）
    missing: [(line_id, field, rel_path)]  —— 清单里有、磁盘上没有
    integrity: [(line_id, kind, rel_path, 期望, 实际)]
    """
    lines = bank.get("lines") or {}
    refs = {}
    refs_entries = 0
    missing = []
    integrity = []
    envelope_refs = {}

    for line_id, line in lines.items():
        if not isinstance(line, dict):
            continue
        audio_paths = []
        # 主字段 audio（.m4a 口径）
        if line.get("audio"):
            audio_paths.append(("audio", norm_rel(line["audio"])))
        # 双源字段 audioSources {m4a:…, webm:…}
        sources = line.get("audioSources")
        if isinstance(sources, dict):
            for codec in sorted(sources):
                if sources.get(codec):
                    audio_paths.append(("audioSources.%s" % codec, norm_rel(sources[codec])))
        seen_this_line = set()
        for field, rel in audio_paths:
            if not rel or rel in seen_this_line:
                continue
            seen_this_line.add(rel)
            refs.setdefault(rel, set()).add(line_id)
            refs_entries += 1
            disk = os.path.join(static_root, rel.replace("/", os.sep))
            if not os.path.isfile(disk):
                missing.append((line_id, field, rel))
            else:
                # 清单自带的体积/哈希是否与磁盘吻合（只报，不改）
                if line.get("bytes") and isinstance(line["bytes"], dict):
                    ext = os.path.splitext(rel)[1].lstrip(".")
                    want = line["bytes"].get(ext)
                    if isinstance(want, int):
                        got = os.path.getsize(disk)
                        if want != got:
                            integrity.append((line_id, "bytes." + ext, rel, want, got))
                if check_sha and line.get("sha256") and isinstance(line["sha256"], dict):
                    ext = os.path.splitext(rel)[1].lstrip(".")
                    want = line["sha256"].get(ext)
                    if want:
                        got = sha256_file(disk)
                        if want.lower() != got:
                            integrity.append((line_id, "sha256." + ext, rel, want, got))
        # 信封（口型数据）单独一组
        env = norm_rel(line.get("envelope")) if line.get("envelope") else None
        if env:
            envelope_refs.setdefault(env, set()).add(line_id)
            if not os.path.isfile(os.path.join(static_root, env.replace("/", os.sep))):
                missing.append((line_id, "envelope", env))

    return {
        "refs": refs,
        "refs_entries": refs_entries,
        "missing": missing,
        "integrity": integrity,
        "envelope_refs": envelope_refs,
        "line_count": len(lines),
    }


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- 磁盘侧

def scan_disk(voice_dir, static_root):
    """扫 static/kurisu/voice 下真实文件。

    返回 dict：
      audio: {rel_path: (bytes, subdir)}   .m4a / .webm
      envelope: {rel_path: bytes}          *.envelope.json
      other_json: [rel_path]               清单等非信封 json
    """
    audio = {}
    envelope = {}
    other_json = []
    for dirpath, _dirnames, filenames in os.walk(voice_dir):
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = -1
            rel = os.path.relpath(full, static_root).replace(os.sep, "/")
            lower = name.lower()
            if lower.endswith(AUDIO_EXTS):
                sub = os.path.dirname(os.path.relpath(full, voice_dir)).replace(os.sep, "/") or "."
                audio[rel] = (size, sub)
            elif lower.endswith(ENVELOPE_SUFFIX):
                envelope[rel] = size
            elif lower.endswith(".json"):
                other_json.append(rel)
    return {"audio": audio, "envelope": envelope, "other_json": other_json}


def collect_other_manifest_refs(voice_dir, static_root, exclude):
    """收集同目录其他清单引用的音频路径（只为给孤儿表标注，不做判定）。

    覆盖两种结构：{lines:{…}} 与 {banks:{…}}（合并清单只存路径/元信息）。
    """
    used = {}
    for dirpath, _dirnames, filenames in os.walk(voice_dir):
        for name in filenames:
            if not name.lower().endswith(".json") or name.lower().endswith(ENVELOPE_SUFFIX):
                continue
            full = os.path.join(dirpath, name)
            rel_manifest = os.path.relpath(full, static_root).replace(os.sep, "/")
            if rel_manifest == exclude:
                continue
            try:
                data = load_json(full)
            except Exception:
                continue
            paths = set()
            _harvest_paths(data, paths)
            for p in paths:
                used.setdefault(p, set()).add(rel_manifest)
    return used


def _harvest_paths(node, out, depth=0):
    """递归捞形如 kurisu/voice/**/*.{m4a,webm} 的字符串值。"""
    if depth > 12:
        return
    if isinstance(node, dict):
        for v in node.values():
            _harvest_paths(v, out, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _harvest_paths(v, out, depth + 1)
    elif isinstance(node, str):
        s = node.replace("\\", "/")
        if s.lower().endswith(AUDIO_EXTS) and "/" in s:
            out.add(norm_rel(s))


# ---------------------------------------------------------------- 报告

def build_report(args):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(script_dir)
    static_root = args.static or os.path.join(repo, "static")
    voice_dir = args.voice_dir or os.path.join(static_root, "kurisu", "voice")
    bank_path = args.bank or os.path.join(voice_dir, "bank.json")

    if not os.path.isdir(voice_dir):
        raise SystemExit("voice 目录不存在：%s" % voice_dir)
    if not os.path.isfile(bank_path):
        raise SystemExit("bank.json 不存在：%s" % bank_path)

    bank = load_json(bank_path)
    ref = collect_refs(bank, static_root, check_sha=args.check_sha)
    disk = scan_disk(voice_dir, static_root)

    refs = ref["refs"]
    disk_audio = disk["audio"]
    disk_set = set(disk_audio)
    ref_set = set(refs)

    referenced_present = sorted(ref_set & disk_set)
    orphans = sorted(disk_set - ref_set)

    # 清单自报 vs 磁盘，用于交叉印证 lineCount/总体积
    declared_lines = bank.get("lineCount")
    declared_bytes = bank.get("totalBytes")

    rel_bank = os.path.relpath(bank_path, static_root).replace(os.sep, "/")
    other_refs = collect_other_manifest_refs(voice_dir, static_root, exclude=rel_bank)

    by_ext = {}
    for rel, (size, _sub) in disk_audio.items():
        ext = os.path.splitext(rel)[1].lower()
        slot = by_ext.setdefault(ext, {"files": 0, "bytes": 0})
        slot["files"] += 1
        slot["bytes"] += max(size, 0)

    ref_by_ext = {}
    for rel in ref_set:
        ext = os.path.splitext(rel)[1].lower()
        ref_by_ext[ext] = ref_by_ext.get(ext, 0) + 1

    orphan_rows = []
    for rel in orphans:
        size, sub = disk_audio[rel]
        orphan_rows.append({
            "path": rel,
            "dir": sub,
            "bytes": size,
            "alsoReferencedBy": sorted(other_refs.get(rel, [])),
        })
    orphan_bytes = sum(r["bytes"] for r in orphan_rows if r["bytes"] > 0)
    referenced_bytes = sum(max(disk_audio[r][0], 0) for r in referenced_present)

    # 信封孤儿（有 .m4a 没对应信封，或信封没有音频）
    env_disk = set(disk["envelope"])
    env_ref = set(ref["envelope_refs"])
    env_orphans = sorted(env_disk - env_ref)

    return {
        "inputs": {
            "bank": rel_bank,
            "voiceDir": os.path.relpath(voice_dir, repo).replace(os.sep, "/"),
            "staticRoot": os.path.relpath(static_root, repo).replace(os.sep, "/"),
            "audioExts": list(AUDIO_EXTS),
        },
        "groupA_referenced": {
            "lines": ref["line_count"],
            "bankDeclaredLineCount": declared_lines,
            "referencedAudioFiles": len(ref_set),
            "referencedEntries": ref["refs_entries"],
            "byExt": ref_by_ext,
            "referencedEnvelopes": len(env_ref),
            "referencedAll": len(ref_set) + len(env_ref),
            "referencedBytes": referenced_bytes,
        },
        "groupB_actual": {
            "audioFiles": len(disk_audio),
            "audioBytes": sum(max(s, 0) for s, _ in disk_audio.values()),
            "byExt": by_ext,
            "envelopeFiles": len(disk["envelope"]),
            "otherJsonFiles": sorted(p for p in disk["other_json"] if p != rel_bank),
        },
        "groupC_orphans": {
            "count": len(orphan_rows),
            "bytes": orphan_bytes,
            "byExt": _count_by_ext(orphan_rows),
            "byDir": _count_by_dir(orphan_rows),
            "files": orphan_rows,
            "alsoReferencedCount": sum(1 for r in orphan_rows if r["alsoReferencedBy"]),
            "neverReferencedCount": sum(1 for r in orphan_rows if not r["alsoReferencedBy"]),
        },
        "missing": [{"line": l, "field": f, "path": p} for l, f, p in ref["missing"]],
        "envelopeOrphans": env_orphans,
        "integrity": [{"line": l, "kind": k, "path": p, "declared": w, "actual": g}
                      for l, k, p, w, g in ref["integrity"]],
        "declared": {"lineCount": declared_lines, "totalBytes": declared_bytes,
                     "bankBytesOnDisk": os.path.getsize(bank_path)},
    }


def _count_by_ext(rows):
    out = {}
    for r in rows:
        ext = os.path.splitext(r["path"])[1].lower()
        slot = out.setdefault(ext, {"files": 0, "bytes": 0})
        slot["files"] += 1
        slot["bytes"] += max(r["bytes"], 0)
    return out


def _count_by_dir(rows):
    out = {}
    for r in rows:
        slot = out.setdefault(r["dir"], {"files": 0, "bytes": 0})
        slot["files"] += 1
        slot["bytes"] += max(r["bytes"], 0)
    return out


def print_report(rep, quiet=False):
    A = rep["groupA_referenced"]
    B = rep["groupB_actual"]
    C = rep["groupC_orphans"]

    print("=" * 72)
    print("原声资产核查（只读）  bank = %s" % rep["inputs"]["bank"])
    print("voice = %s" % rep["inputs"]["voiceDir"])
    print("=" * 72)

    print("\n[A] 引用数（bank.json 说要播的）")
    print("  line 条数            : %d%s" % (
        A["lines"], "" if A["bankDeclaredLineCount"] in (None, A["lines"])
        else "  (清单自报 lineCount=%s，不一致)" % A["bankDeclaredLineCount"]))
    print("  被引用音频文件(去重) : %d   条目(含重复引用) %d" % (A["referencedAudioFiles"], A["referencedEntries"]))
    for ext in sorted(A["byExt"]):
        print("      %-6s : %d" % (ext, A["byExt"][ext]))
    print("  被引用信封文件       : %d" % A["referencedEnvelopes"])
    dec = rep["declared"].get("totalBytes")
    if isinstance(dec, int):
        flag = "一致" if dec == A["referencedBytes"] else "不一致"
        print("  被引用音频体积       : %s   （清单自报 totalBytes=%d，%s）"
              % (human(A["referencedBytes"]), dec, flag))

    print("\n[B] 实际文件数（磁盘上的）")
    print("  音频文件合计         : %d   %s" % (B["audioFiles"], human(B["audioBytes"])))
    for ext in sorted(B["byExt"]):
        e = B["byExt"][ext]
        print("      %-6s : %6d 个   %s" % (ext, e["files"], human(e["bytes"])))
    print("  信封文件             : %d" % B["envelopeFiles"])
    if B["otherJsonFiles"]:
        print("  其他 json（清单等）  : %d  -> %s" % (
            len(B["otherJsonFiles"]), ", ".join(os.path.basename(p) for p in B["otherJsonFiles"])))

    print("\n[C] 孤儿数（磁盘上有、bank.json 没引用）")
    print("  孤儿文件合计         : %d   %s" % (C["count"], human(C["bytes"])))
    for ext in sorted(C["byExt"]):
        e = C["byExt"][ext]
        print("      %-6s : %6d 个   %s" % (ext, e["files"], human(e["bytes"])))
    for d in sorted(C["byDir"]):
        e = C["byDir"][d]
        print("      %-14s : %6d 个   %s" % (d, e["files"], human(e["bytes"])))
    print("  其中仍被其他清单引用 : %d   （删前先看，别把溯源音源清掉）" % C["alsoReferencedCount"])
    print("  谁都不引用的         : %d" % C["neverReferencedCount"])
    never = [r for r in C["files"] if not r["alsoReferencedBy"]]
    if never:
        nb = sum(max(r["bytes"], 0) for r in never)
        print("      真死资产合计     : %s（%d 个，任何清单都不提）" % (human(nb), len(never)))
        if not quiet:
            for r in sorted(never, key=lambda x: x["path"]):
                print("        %-46s %10s" % (r["path"], human(r["bytes"])))

    if rep["missing"]:
        print("\n[!] 缺失引用 %d 条（清单里有、磁盘没有 -> 会掉音）" % len(rep["missing"]))
        for m in rep["missing"]:
            print("    %-22s %-20s %s" % (m["line"], m["field"], m["path"]))
    else:
        print("\n[OK] 缺失引用 0 条：bank.json 引用的音频全部落地。")

    if rep["envelopeOrphans"]:
        print("\n[!] 信封孤儿 %d 个（*.envelope.json 没有对应 line 引用，不影响播放）" % len(rep["envelopeOrphans"]))
        if quiet:
            print("    （--quiet 下不展开，见 --json）")
        else:
            for p in rep["envelopeOrphans"][:20]:
                print("    " + p)
            if len(rep["envelopeOrphans"]) > 20:
                print("    … 其余 %d 个见 --json" % (len(rep["envelopeOrphans"]) - 20))

    if rep["integrity"]:
        print("\n[!] 清单与磁盘不一致 %d 处（bytes/sha256）" % len(rep["integrity"]))
        for it in rep["integrity"][:40]:
            print("    %-22s %-12s %s  declared=%s actual=%s"
                  % (it["line"], it["kind"], it["path"], it["declared"], it["actual"]))
        if len(rep["integrity"]) > 40:
            print("    … 其余 %d 处见 --json" % (len(rep["integrity"]) - 40))
    elif rep["integrity"] == []:
        print("\n[OK] 清单体积/哈希与磁盘一致（0 处不符）。")

    print("\n三组数字：引用 %d / 实际 %d / 孤儿 %d   体积：引用口径 %s / 孤儿口径 %s / 实际合计 %s"
          % (A["referencedAudioFiles"], B["audioFiles"], C["count"],
             human(A["referencedBytes"]), human(C["bytes"]), human(B["audioBytes"])))

    if C["count"] and not quiet:
        print("\n孤儿清单（%d 个，按目录分组；本脚本只读，不删除任何文件）" % C["count"])
        for d in sorted(_group_orphans(C["files"])):
            items = _group_orphans(C["files"])[d]
            print("\n  -- %s  (%d 个, %s)" % (d, len(items), human(sum(i["bytes"] for i in items))))
            for it in items:
                mark = ""
                if it["alsoReferencedBy"]:
                    mark = "  <- 仍被 %s 引用" % ", ".join(os.path.basename(x) for x in it["alsoReferencedBy"])
                print("     %-46s %10s%s" % (it["path"].split("/")[-1], human(it["bytes"]), mark))


def _group_orphans(rows):
    out = {}
    for r in rows:
        out.setdefault(r["dir"], []).append(r)
    for v in out.values():
        v.sort(key=lambda x: (-max(x["bytes"], 0), x["path"]))
    return out


# ---------------------------------------------------------------- 入口

def main(argv=None):
    setup_stdout()
    ap = argparse.ArgumentParser(description="原声资产核查（只读）：bank.json 引用 vs static/kurisu/voice 实际文件")
    ap.add_argument("--static", help="static 根目录，默认 <repo>/static")
    ap.add_argument("--voice-dir", dest="voice_dir", help="voice 目录，默认 <static>/kurisu/voice")
    ap.add_argument("--bank", help="清单 json，默认 <voice-dir>/bank.json")
    ap.add_argument("--json", dest="json_out", help="把完整结果另存为 json（不覆盖任何输入）")
    ap.add_argument("--check-sha", dest="check_sha", action="store_true",
                    help="额外校验 sha256（更慢；默认也校验 bytes 字段）")
    ap.add_argument("--quiet", action="store_true", help="不展开长清单")
    args = ap.parse_args(argv)

    try:
        rep = build_report(args)
    except SystemExit:
        raise
    except Exception as exc:  # 参数/读盘错误
        print("核查失败：%s" % exc, file=sys.stderr)
        return 2

    print_report(rep, quiet=args.quiet)

    if args.json_out:
        with io.open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        print("\n[json] %s" % args.json_out)

    return 1 if rep["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
