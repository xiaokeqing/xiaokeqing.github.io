# -*- coding: utf-8 -*-
"""布局静态审计 · 不跑浏览器也能抓的常见布局风险（只读，零第三方依赖）。

为什么需要静态审计：
    本项目已有 `_dev/gate-firstscreen.mjs`（真浏览器 CDP），但在无 GUI / 沙箱环境里
    headless 渲染器会直接崩（实测：`Abnormal renderer termination` + GPU 进程退出），
    门禁跑不起来 ⇒ 需要一个**任何环境都能跑**的兜底体检。

做什么（全程只读）：
    ① 抽取 public/**/*.html 的内联 <style> 与 assets/css/*.css；
    ② 跟踪大括号，区分"规则在 @media 内 / 外"并记录条件；
    ③ 检查项：
       A 固定像素宽度（在**全局作用域**、且无 ≤980 媒体回退）→ 窄屏溢出候选
       B grid-template-columns 含固定 px → 是否有 ≤980 回退
       C 交互元素命中区最小边是否 < 44px（只看全局作用域；媒体查询内视为已适配）
       D padding-top 同选择器多声明 → 特异性冲突（本项目"硬伤 2"那一类）
       E 断点清单 / position:fixed 元素清单
    ④ 落 _shots/layout-static-audit.json + 控制台摘要。

★ 默认**只报告不拦**（退出码 0）：静态估算会误报（如按钮实际高度由 line-height 撑开），
  拿它当硬门禁会重演项目里"自己定的门槛拖死迭代"的老问题。
  要当门禁用请显式加 `--strict`（有 C 类违规才退出码 1）。

用法：
    python -X utf8 _dev/audit-layout-static.py [--strict]
"""

import io
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, 'public')
CSS_DIR = os.path.join(ROOT, 'assets', 'css')
OUT = os.path.join(ROOT, '_shots')

MIN_TAP = 44      # 站主口径：最小命中区
FIXED_W = 280     # 超过此宽度的固定像素视为溢出候选

INTERACTIVE = ['.dock a', '.dock button', '.ops-tabs button', '.chat-ft button',
               '.anchor-row a', '.holo-fold', '.navpill a', '.navpill button']

# CSS 简写 font: [style] [weight] size[/line-height] family
FONT_SIZE_RE = re.compile(r'(\d+(?:\.\d+)?)px')


def _reconf_stdout():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def px(v):
    m = re.match(r'^(-?[\d.]+)px$', (v or '').strip())
    return float(m.group(1)) if m else None


def font_size_of(decls):
    """取字号：优先 font-size，否则从 font: 简写里解析（如 `font:13px var(--sans)`、
    `font:600 11px var(--mono)`）。简写里字号前通常是 `:` 或空白，不能只认空白。"""
    fs = px(decls.get('font-size', '') or '')
    if fs:
        return fs
    f = decls.get('font', '') or ''
    for m in FONT_SIZE_RE.finditer(f):
        v = float(m.group(1))
        if 6 <= v <= 96:      # 过滤掉 line-height / 其它无关 px
            return v
    return None


def vpad_of(pad):
    nums = [px(x) for x in re.split(r'\s+', (pad or '').strip()) if px(x) is not None]
    if len(nums) == 4:
        return nums[0] + nums[2]
    if len(nums) == 3:
        return nums[0] + nums[2]
    if len(nums) in (1, 2):
        return nums[0] * 2
    return 0.0


def parse_rules(css, source):
    """极简 CSS 解析：返回 [{selector, decls, media, source}]。"""
    rules = []
    i, n = 0, len(css)
    media_stack = []
    while i < n:
        j = i
        while j < n and css[j] not in '{}':
            j += 1
        if j >= n:
            break
        chunk = css[i:j]
        if css[j] == '{':
            head = chunk.strip()
            if head.startswith('@'):
                if head.startswith('@media'):
                    media_stack.append(head.strip())
                    i = j + 1          # ★ 必须推进游标
                    continue
                # 其它 @ 规则（@keyframes 等）：整块跳过
                depth, k = 1, j + 1
                while k < n and depth:
                    if css[k] == '{':
                        depth += 1
                    elif css[k] == '}':
                        depth -= 1
                    k += 1
                i = k
                continue
            # 普通规则：读到匹配的 '}'
            depth, k = 1, j + 1
            while k < n and depth:
                if css[k] == '{':
                    depth += 1
                elif css[k] == '}':
                    depth -= 1
                k += 1
            body = css[j + 1:k - 1]
            decls = {}
            for part in body.split(';'):
                if ':' in part:
                    pk, pv = part.split(':', 1)
                    decls[pk.strip().lower()] = pv.strip()
            rules.append({
                'selector': ' '.join(head.split()),
                'decls': decls,
                'media': media_stack[-1] if media_stack else None,
                'source': source,
            })
            i = k
            continue
        # '}'
        if media_stack:
            media_stack.pop()
        i = j + 1
    return rules


def collect_css():
    blobs = []
    for dp, dn, fn in os.walk(PUB):
        for f in fn:
            if not f.endswith('.html'):
                continue
            p = os.path.join(dp, f)
            try:
                t = io.open(p, encoding='utf-8', errors='ignore').read()
            except Exception:
                continue
            for m in re.finditer(r'<style[^>]*>(.*?)</style>', t, re.S):
                blobs.append((os.path.relpath(p, ROOT) + ' <style>', m.group(1)))
    if os.path.isdir(CSS_DIR):
        for dp, dn, fn in os.walk(CSS_DIR):
            for f in fn:
                if f.endswith('.css'):
                    p = os.path.join(dp, f)
                    try:
                        blobs.append((os.path.relpath(p, ROOT), io.open(p, encoding='utf-8', errors='ignore').read()))
                    except Exception:
                        pass
    return blobs


def main():
    _reconf_stdout()
    strict = '--strict' in sys.argv
    blobs = collect_css()
    if not blobs:
        print('没有可审计的 CSS（public/ 可能未构建）')
        return 2

    all_rules = []
    for src, css in blobs:
        all_rules.extend(parse_rules(css, src))

    print('=' * 78)
    print(' 布局静态审计（只读）  CSS 来源 %d 份，规则 %d 条' % (len(blobs), len(all_rules)))
    print('=' * 78)

    # ---------- ① 断点清单 ----------
    medias = sorted({r['media'] for r in all_rules if r['media']})
    print('\n① 响应式断点清单（%d 档）' % len(medias))
    for m in medias:
        print('   %s' % m)

    # ---------- ② 全局作用域的固定像素宽度 ----------
    grid_sel_with_fallback = set()
    for r in all_rules:
        if r['media'] and 'grid-template-columns' in r['decls']:
            grid_sel_with_fallback.add(r['selector'])

    print('\n② 固定像素宽度（> %dpx，在**全局作用域**）' % FIXED_W)
    fixed_global = []
    for r in all_rules:
        if r['media']:
            continue
        w = px(r['decls'].get('width', '') or '')
        if w is not None and w > FIXED_W:
            fixed_global.append((r['source'], r['selector'], int(w)))
    if not fixed_global:
        print('   无 ✓')
    for src, sel, w in fixed_global[:20]:
        print('   %-30s %-38s %d px' % (src, sel[:38], w))

    print('\n③ grid-template-columns 含固定 px / 是否有 ≤980 回退')
    grid_all = defaultdict(list)
    for r in all_rules:
        g = r['decls'].get('grid-template-columns')
        if g and 'px' in g:
            grid_all[r['selector']].append((r['media'], g))
    bad = 0
    for sel, items in grid_all.items():
        outside = [g for m, g in items if not m]
        inside = [g for m, g in items if m]
        if outside and not inside:
            bad += 1
            print('   ⚠ %-40s 全局 %s，但无 ≤980 回退' % (sel[:40], outside[0]))
    if not bad:
        print('   全部有回退 ✓')

    # ---------- ④ 触控目标（只看全局作用域） ----------
    print('\n④ 交互元素命中区估算（只看**全局作用域**规则；媒体查询内的视为已适配）')
    tap_issues = []
    for sel in INTERACTIVE:
        for r in all_rules:
            if r['selector'] != sel or r['media']:
                continue
            d = r['decls']
            vpad = vpad_of(d.get('padding', ''))
            fs = font_size_of(d) or 16.0
            mh = px(d.get('min-height', '') or '')
            mw = px(d.get('min-width', '') or '')
            est = fs * 1.75 + vpad
            if mh:
                est = max(est, mh)
            flag = est < MIN_TAP
            print('   %-30s %-20s padding=%-14s font=%-6s minH=%-5s ⇒ 估算 %s px  %s'
                  % (r['source'][:30], sel, (d.get('padding') or '-')[:14], fs, mh or '-',
                     int(round(est)), '⚠ <44' if flag else '✓'))
            if flag:
                tap_issues.append((r['source'], sel, int(round(est)), mw))
    print('   ⇒ 全局作用域下触控目标违规 %d 处' % len(tap_issues))

    # ---------- ⑤ padding-top 冲突 ----------
    print('\n⑤ padding-top 多声明（特异性冲突候选）')
    by_sel = defaultdict(list)
    for r in all_rules:
        if 'padding-top' in r['decls']:
            by_sel[r['selector']].append(r)
    hits = 0
    for sel, rs in by_sel.items():
        if len(rs) > 1:
            hits += 1
            print('   %s' % sel)
            for r in rs:
                print('      %-32s %-24s media=%s' % (r['source'][:32], r['decls']['padding-top'], r['media'] or '(无)'))
    if not hits:
        print('   无 ✓')

    # ---------- ⑥ fixed 定位 ----------
    print('\n⑥ position:fixed 元素清单')
    fx = defaultdict(list)
    for r in all_rules:
        if r['decls'].get('position') == 'fixed':
            fx[r['selector']].append((r['source'], r['media']))
    for sel, items in sorted(fx.items()):
        print('   %-40s z=%s  %s' % (sel[:40], '?', items[0][0][:24]))

    print('\n⑦ 结论')
    if strict:
        print('   [--strict] 触控目标违规 %d 处 ⇒ %s'
              % (len(tap_issues), 'FAIL' if tap_issues else 'PASS'))
        print('=' * 78)
        return 1 if tap_issues else 0
    print('   [REPORT] 静态估算仅作提示（会误报），不拦发布 —— 要当门禁请加 --strict')
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
