# -*- coding: utf-8 -*-
"""给静态资源引用加内容指纹查询串：/js/xk-saver.js -> /js/xk-saver.js?v=ab12cd34

为什么：Cloudflare 上有规则把 JS 的 Browser TTL 压到 300s（源站发的是 86400），
每次过期都回源。加内容哈希后：内容没变 URL 就不变（继续吃缓存），内容一变 URL 也变
（立刻失效，不会被旧缓存粘住）。

兼容 minify 后的无引号属性：`<script src=/js/xk-saver.js>`。

用法：python scripts/asset-version.py public
"""
import hashlib
import io
import os
import re
import sys

REF = re.compile(r'(src|href)=("?)(/(?:js|css)/[^"\'?#\s>]+)\2')
PREFIX = "?v="


def fingerprint(root, rel_path):
    fp = os.path.join(root, rel_path.lstrip("/").replace("/", os.sep))
    try:
        with open(fp, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
    except OSError:
        return None


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "public"
    cache = {}
    changed_files = 0
    changed_refs = 0
    missing = set()

    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith(".html"):
                continue
            p = os.path.join(dirpath, name)
            html = io.open(p, encoding="utf-8", errors="replace").read()
            orig = html

            def repl(m):
                nonlocal changed_refs
                attr, quote, path = m.group(1), m.group(2), m.group(3)
                if path not in cache:
                    cache[path] = fingerprint(root, path)
                h = cache[path]
                if not h:
                    missing.add(path)
                    return m.group(0)
                changed_refs += 1
                return '%s=%s%s%s%s%s' % (attr, quote, path, PREFIX, h, quote)

            html = REF.sub(repl, html)
            if html != orig:
                io.open(p, "w", encoding="utf-8", newline="").write(html)
                changed_files += 1

    print("asset-version: %d 个 html 被改写，%d 处引用加上指纹" % (changed_files, changed_refs))
    if missing:
        print("  缺文件（未加指纹）：%s" % ", ".join(sorted(missing)[:6]))


if __name__ == "__main__":
    main()
