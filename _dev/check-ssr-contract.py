# -*- coding: utf-8 -*-
"""静态产物契约断言（**不跑浏览器、不依赖任何脚本时序**）

口径（与 static/js/app.js 对齐，2026-10-14 核实）：
  · 每页 <main id="content"> 必须有 `data-xk-ssr="<路由名>"`；
  · 路由名 = app.js 的 VIEW_TPL 键（routeFromPath 的返回值），**不是** URL 段的名字：
      /            → home      /alerts/  → monitor   /posts/  → notes
      /ai/         → ai
    ★T27（2026-10-15 站主）：/labs/ 与 /about/ 两页已删 ⇒ 六页 → 四页，本清单同步删两行。
    ★2026-10-16（窗口 Q）：新增测试模块页 /test/ ⇒ 四页 → 五页（gate-firstscreen.mjs 同步）。
  · 每页必须有 `#xk-views` 模板表（SPA 换页依赖它）；
  · 七页都不得出现站外资源引用（2026-10-17 新增 /what/ 介绍页与 /lab/ 靶场页）。
用法：python _dev/check-ssr-contract.py [public]
退出码：0 全通过 / 1 有不合格项
"""
import os
import re
import sys

PUB = sys.argv[1] if len(sys.argv) > 1 else 'public'
PAGES = [
    ('index.html', 'home'),
    ('alerts/index.html', 'monitor'),
    ('posts/index.html', 'notes'),
    ('ai/index.html', 'ai'),
    ('test/index.html', 'test'),
    ('what/index.html', 'what'),
    ('lab/index.html', 'lab'),
    ('status/index.html', 'status'),
    ('api/index.html', 'api'),
    ('redteam/index.html', 'redteam'),
]
RE_MAIN = re.compile(r'<main\b[^>]*>', re.I)
RE_SSR = re.compile(r'data-xk-ssr=["\']?([a-z-]+)', re.I)
RE_VIEWS = re.compile(r'id=["\']?xk-views', re.I)
RE_EXT_RES = re.compile(r'(?:src|href|poster)="https?://(?![^"]*xiaokeqing\.cn)[^"]+"', re.I)

fail = 0
print('静态路由契约断言（public=%s）' % PUB)
print('%-22s %-10s %-10s %-9s %-9s %s' % ('页面', 'data-xk-ssr', '期望', 'xk-views', '站外资源', '结论'))
for rel, want in PAGES:
    p = os.path.join(PUB, rel)
    if not os.path.exists(p):
        print('%-22s %-10s %-10s %-9s %-9s 缺产物' % (rel, '-', want, '-', '-'))
        fail += 1
        continue
    h = open(p, encoding='utf-8').read()
    main = RE_MAIN.search(h)
    got = None
    if main:
        m = RE_SSR.search(main.group(0))
        got = m.group(1) if m else None
    if got is None:                      # 兜底：整页找（属性可能被 minifier 挪位）
        m = RE_SSR.search(h)
        got = m.group(1) if m else None
    views = bool(RE_VIEWS.search(h))
    ext = RE_EXT_RES.findall(h)
    good = (got == want) and views and not ext
    if not good:
        fail += 1
    print('%-22s %-10s %-10s %-9s %-9s %s' % (
        rel, str(got), want, str(views), str(len(ext)), 'PASS' if good else 'FAIL'))
print()
print('结论：%s（%d 项不合格）' % ('全部通过' if fail == 0 else '有不合格项', fail))
sys.exit(1 if fail else 0)
