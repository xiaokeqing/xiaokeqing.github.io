#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 README 里的数字换成真实值，避免"文档写 42、实际 90"这种漂移。

用法（cwd = F:\\7AAA\\AI\\blog）：
    python scripts/readme-numbers.py            # 只报告，不写
    python scripts/readme-numbers.py --write    # 写入 README.md
    python scripts/readme-numbers.py --write --skip-assert   # 跳过 40 秒的断言实跑

README 里的占位写法（脚本只认这种）：
    <!--N:assert-->90<!--/N-->        断言项数
    <!--N:tests-->858<!--/N-->        后端单测数
    <!--N:endpoints-->20<!--/N-->     /api/public/* 映射数
"""
import argparse
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
BACKEND = r"F:\7AAA\AI\SecAgent\sec-agent"
GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"


def count_assertions():
    """实跑 scripts/assert-build.sh public，取 '通过 N 项'。"""
    env = dict(os.environ)
    env["PATH"] = ";".join(
        p for p in env.get("PATH", "").split(";") if p and "WindowsApps" not in p
    )
    try:
        out = subprocess.run(
            [GIT_BASH, "scripts/assert-build.sh", "public"],
            cwd=ROOT, env=env, capture_output=True, timeout=900,
        )
    except Exception as exc:  # noqa: BLE001
        return None, "断言脚本跑不起来：%s" % exc
    text = (out.stdout or b"").decode("utf-8", "replace") + (out.stderr or b"").decode("utf-8", "replace")
    m = re.search(r"通过\s*(\d+)\s*项", text)
    if not m:
        return None, "断言输出里没找到『通过 N 项』"
    return int(m.group(1)), "实跑 assert-build.sh"


def count_tests():
    """从后端 surefire 报告汇总 Tests run 数。"""
    files = glob.glob(os.path.join(BACKEND, "target", "surefire-reports", "*.txt"))
    if not files:
        return None, "没找到 %s\\target\\surefire-reports" % BACKEND
    total = fails = errs = skip = 0
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                head = fh.read(4000)
        except OSError:
            continue
        m = re.search(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)", head)
        if not m:
            continue
        total += int(m.group(1))
        fails += int(m.group(2))
        errs += int(m.group(3))
        skip += int(m.group(4))
    if not total:
        return None, "surefire 报告里没解析到 Tests run"
    if fails or errs:
        return None, "测试不绿（Failures=%d Errors=%d），不写数字" % (fails, errs)
    return total, "surefire 汇总（Skipped=%d）" % skip


def count_endpoints():
    """数后端 publicapi 包里的公开端点（按**路径去重**）。

    为什么不数注解个数：2026-11-07 把 god controller 拆成 5 个按域 controller 之后，
    旧的 `PublicApiController` 仍保留为"测试专用委托门面"（20 个一行转发方法，仍带同样的
    `@GetMapping`），注解数会变成 20+21=41 的重复计数；文档要的是真实端点个数，
    所以按注解里的路径字面量去重。
    """
    root = os.path.join(BACKEND, "src", "main", "java", "org", "example", "publicapi")
    if not os.path.isdir(root):
        return None, "没找到 %s" % root
    paths = set()
    for path in glob.glob(os.path.join(root, "**", "*.java"), recursive=True):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        for m in re.finditer(r"@(?:Get|Post|Put|Delete)Mapping\s*\(([^)]*)\)", src):
            for lit in re.findall(r'"([^"]*)"', m.group(1)):
                paths.add(lit)
    return len(paths), "publicapi 包路径去重计数"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="真的写回 README.md")
    ap.add_argument("--skip-assert", action="store_true", help="不实跑断言（用 README 现有值）")
    args = ap.parse_args()

    with open(README, "r", encoding="utf-8") as fh:
        text = fh.read()

    found = {}
    for key, value, why in [
        (None if args.skip_assert else "assert", *count_assertions()),
        ("tests", *count_tests()),
        ("endpoints", *count_endpoints()),
    ]:
        if key is None:
            continue
        if value is None:
            print("[SKIP] %-9s %s" % (key, why))
        else:
            found[key] = value
            print("[OK]   %-9s %-5d  (%s)" % (key, value, why))

    changed = 0
    for key, value in found.items():
        pattern = re.compile(r"(<!--N:%s-->)(\d+)(<!--/N-->)" % re.escape(key))
        new_text, n = pattern.subn(lambda m: m.group(1) + str(value) + m.group(3), text)
        if n:
            changed += n
            text = new_text
        print("        %-9s 占位 %d 处" % (key, n))

    if not changed:
        print("\n没有可替换的占位（README 里没有 <!--N:key-->…<!--/N-->）。")
        return 0
    # 徽章 URL 不能带 HTML 注释，单独用正则维护
    if "assert" in found:
        text, badge_n = re.subn(
            r"build%20assertions-\d+%2F\d+",
            "build%%20assertions-%d%%2F%d" % (found["assert"], found["assert"]),
            text,
        )
        print("        badge     替换 %d 处" % badge_n)
        changed += badge_n
    if not args.write:
        print("\n[dry-run] 加 --write 才写回 README.md")
        return 0
    with open(README, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print("\n已写回 README.md（%d 处）" % changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
