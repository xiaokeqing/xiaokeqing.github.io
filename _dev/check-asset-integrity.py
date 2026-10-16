# -*- coding: utf-8 -*-
"""第四道门禁（候选）· 角色资产引用完整性检查 —— 纯只读，零第三方依赖。

背景（2026-10-16 第一轮外部审查发现）：
    `static/kurisu/statemachine.json` 里 38/38 个节点的 `mouthPatch.file` 写成
    `<clip>.patch.png`，而磁盘 `static/kurisu/mouth/` 实际是 `<clip>.patch.webp`。
    这类"引用了不存在的文件"在构建期不报错，只有播到那个节点才 404，
    属于**现有三道门禁（assert-build / gate-firstscreen / check-ssr-contract）都测不到**的空档。

做什么：
    ① 递归扫三份 manifest（statemachine / manifest / video-manifest），抓出所有资产引用；
    ② 逐个按"多基准回退"解析，检查是否真实存在；
    ③ 专项检查 mouthPatch（嘴部补丁三件套：patch / closedRegion / json）；
    ④ 输出"剪辑集合差"与"hi 档覆盖率"两个口径指标；
    ⑤ 有任一引用断链 → 退出码 1（真门禁，不是报告）。

★ 引用基准不统一（本脚本必须处理，也是项目内的一个口径坑）：
    · `medium.pages[].url` / `hi.pages[].url` / `video-manifest.clips.*` → 基准 `static/`（形如 `kurisu/medium/x.atlas.webp`）
    · `nodes[].mouthPatch.file`                                          → 基准 `static/kurisu/mouth/`（形如 `x.patch.png`）

用法：
    python -X utf8 _dev/check-asset-integrity.py [--strict] [--json _shots/asset-integrity.json]

    --strict  把"hi 档覆盖率 < 100%"也判失败（默认只报不拦）
"""

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, 'static')
KURISU = os.path.join(STATIC, 'kurisu')

MANIFESTS = [
    ('statemachine.json', os.path.join(KURISU, 'statemachine.json')),
    ('manifest.json', os.path.join(KURISU, 'manifest.json')),
    ('video-manifest.json', os.path.join(KURISU, 'video-manifest.json')),
]

# 资产子目录（用于"纯文件名"引用的回退查找）
SUBDIRS = ('medium', 'hi', 'full', 'avatar', 'scene', 'mouth', 'eye', 'video', 'voice')

# 相对 static/ 的完整路径引用
FULL_REF_RE = re.compile(r'^(kurisu|images)/[A-Za-z0-9_\-./]+\.[A-Za-z0-9]+$')
# 纯文件名引用（以 mouthPatch.file 为代表）
BARE_REF_RE = re.compile(r'^[A-Za-z0-9_\-.]+\.[A-Za-z0-9]+$')

KEY_HINT = ('file', 'url', 'src', 'poster', 'patch', 'atlas', 'path', 'webm', 'm4a')


def _reconf_stdout():
    """Windows + GBK 控制台下 print 中文会 UnicodeEncodeError（本项目 E3 坑），这里兜底。"""
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def walk_refs(node, out, keypath=()):
    """递归收集所有疑似资产引用，返回 [(keypath_tuple, ref_str, kind)]，kind ∈ {full, bare}。"""
    if isinstance(node, dict):
        for k, v in node.items():
            walk_refs(v, out, keypath + (str(k),))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_refs(v, out, keypath + (str(i),))
    elif isinstance(node, str):
        s = node.strip()
        if not s:
            return
        # ★ 关键修正（第二轮自检发现）：原先只认"键名白名单"，会漏掉
        #   video-manifest.json 里键名为 `video` / `poster` 的引用（只识别出 38/76）。
        #   改为"路径形状优先 + 键名兜底"：只要值长得像 static/ 下的相对路径就算引用，
        #   再用"无空格 + 长度上限"过滤掉 note/description 之类的说明文字。
        if len(s) > 120 or ' ' in s:
            return
        if FULL_REF_RE.match(s):
            out.append((keypath, s, 'full'))
        elif BARE_REF_RE.match(s) and 'mouth' in '/'.join(keypath).lower():
            out.append((keypath, s, 'bare'))


def resolve(ref, kind):
    """多基准回退解析：返回真实存在的绝对路径，或 None。"""
    if kind == 'full':
        cands = [os.path.join(STATIC, ref.replace('/', os.sep))]
    else:
        cands = [os.path.join(KURISU, 'mouth', ref)]
        cands += [os.path.join(KURISU, d, ref) for d in SUBDIRS]
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def main():
    _reconf_stdout()
    strict = '--strict' in sys.argv
    json_out = None
    # --json=路径 与 --json 路径 两种写法都支持（只认等号会静默不落盘，很坑）
    for i, a in enumerate(sys.argv):
        if a.startswith('--json='):
            json_out = a.split('=', 1)[1]
        elif a == '--json' and i + 1 < len(sys.argv):
            json_out = sys.argv[i + 1]

    per_file = {}
    all_refs = []
    for label, p in MANIFESTS:
        if not os.path.isfile(p):
            print('  [FAIL] 缺 manifest：%s' % os.path.relpath(p, ROOT))
            return 1
        try:
            with io.open(p, encoding='utf-8') as f:
                d = json.load(f)
        except Exception as e:
            print('  [FAIL] 解析失败 %s：%s' % (label, e))
            return 1
        refs = []
        walk_refs(d, refs)
        per_file[label] = refs
        for kp, s, kind in refs:
            all_refs.append((label, kp, s, kind))

    print('=' * 78)
    print(' 资产引用完整性检查（只读）  ROOT=%s' % ROOT)
    print('=' * 78)

    missing = []
    for label, kp, s, kind in all_refs:
        if resolve(s, kind) is None:
            missing.append((label, '/'.join(kp), s, kind))

    # ---- ① 总览 --------------------------------------------------------
    print('\n① 引用总览')
    for label, refs in per_file.items():
        print('   %-24s 引用 %3d 条' % (label, len(refs)))
    print('   %-24s 引用 %3d 条' % ('合计', len(all_refs)))

    # ---- ② 断链明细 ------------------------------------------------------
    print('\n② 断链明细（%d 条）' % len(missing))
    if not missing:
        print('   无 ✓')
    else:
        agg = {}
        for label, kp, s, kind in missing:
            ext = os.path.splitext(s)[1] or '(无扩展名)'
            agg.setdefault((label, kind, ext), []).append(s)
        for (label, kind, ext), items in sorted(agg.items()):
            print('   %-22s %-5s %-6s %3d 条   例：%s'
                  % (label, kind, ext, len(items), items[0]))
            if len(items) <= 6:
                for it in items:
                    print('        - %s' % it)

    # ---- ③ mouthPatch 专项 ----------------------------------------------
    print('\n③ mouthPatch 专项（嘴部补丁三件套 patch / closedRegion / json）')
    try:
        with io.open(MANIFESTS[0][1], encoding='utf-8') as f:
            sm = json.load(f)
    except Exception:
        sm = {'nodes': []}
    disk_mouth = set()
    if os.path.isdir(os.path.join(KURISU, 'mouth')):
        disk_mouth = set(os.listdir(os.path.join(KURISU, 'mouth')))
    hit = miss = 0
    for n in sm.get('nodes', []):
        mp = n.get('mouthPatch')
        f = mp.get('file') if isinstance(mp, dict) else (mp if isinstance(mp, str) else None)
        if not f:
            continue
        if f in disk_mouth:
            hit += 1
        else:
            miss += 1
    print('   状态机节点 %d ／ 引用命中磁盘 %d ／ 断链 %d' % (len(sm.get('nodes', [])), hit, miss))
    print('   mouth/ 磁盘 %d 个文件 ⇒ 每剪辑 3 件套 ⇒ 约 %d 个剪辑有真实嘴型素材'
          % (len(disk_mouth), len(disk_mouth) // 3 if disk_mouth else 0))
    if miss:
        print('   ★ 有 %d 个节点的 mouthPatch 指向不存在的文件，播到即 404。' % miss)
        print('     修法：有 profile 的把 .png → .webp；没有的显式置 null（别留假路径）。')

    # ---- ④ 集合口径 ------------------------------------------------------
    print('\n④ 剪辑集合口径')
    clips_sm = {n.get('clip') for n in sm.get('nodes', []) if n.get('clip')}
    clips_vid = set()
    if os.path.isdir(os.path.join(KURISU, 'video')):
        clips_vid = {f[:-5] for f in os.listdir(os.path.join(KURISU, 'video')) if f.endswith('.webm')}
    print('   状态机图内剪辑 %d ／ video 剪辑 %d' % (len(clips_sm), len(clips_vid)))
    print('   video 有·图内无 : %s' % (sorted(clips_vid - clips_sm) or '无'))
    print('   图内有·video 无 : %s' % (sorted(clips_sm - clips_vid) or '无'))

    hi_clips = sorted(sm.get('hi_clips') or [])
    cov = (100.0 * len(hi_clips) / len(clips_sm)) if clips_sm else 0.0
    print('   hi 档覆盖 %d / %d 剪辑 = %.1f%%' % (len(hi_clips), len(clips_sm), cov))
    if cov < 100.0:
        print('   ★ "boot→hi 两段式最终仍出 hi" 仅对这 %d 个剪辑成立。' % len(hi_clips))

    # ---- ⑤ 结论 ----------------------------------------------------------
    fail = bool(missing)
    print('\n⑤ 结论')
    if fail:
        print('   [FAIL] 存在断链引用 → 拒绝发布（与既有三道门禁同口径）')
    else:
        print('   [PASS] 引用完整')
    if strict and cov < 100.0:
        print('   [FAIL] --strict：hi 档未全覆盖')
        fail = True
    print('=' * 78)

    if json_out:
        try:
            d = os.path.dirname(os.path.abspath(json_out))
            if d:
                os.makedirs(d, exist_ok=True)
            with io.open(json_out, 'w', encoding='utf-8') as f:
                json.dump({
                    'root': ROOT,
                    'refTotal': len(all_refs),
                    'missingCount': len(missing),
                    'missing': [{'src': s, 'key': k, 'ref': r, 'kind': kd} for s, k, r, kd in missing],
                    'mouthPatch': {'nodes': len(sm.get('nodes', [])), 'hit': hit, 'miss': miss},
                    'clips': {'inGraph': sorted(clips_sm), 'video': sorted(clips_vid)},
                    'hiClips': hi_clips,
                    'hiCoveragePct': round(cov, 2),
                    'pass': not fail,
                }, f, ensure_ascii=False, indent=2)
            print('   结果已写入 %s' % json_out)
        except Exception as e:
            print('   写 JSON 失败：%s' % e)

    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
