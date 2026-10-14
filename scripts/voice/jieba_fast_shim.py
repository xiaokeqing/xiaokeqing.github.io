# -*- coding: utf-8 -*-
"""jieba-fast 的纯 Python 替身 shim。

背景：`jieba-fast==0.53`（Amadeus 的 local-cu124/local-models 依赖，供 GPT-SoVITS 的中文前端分词）
在 PyPI 上**从来只有 sdist**（0.48~0.53 全是 tar.gz，无任何 wheel），而本机没有 MSVC → 无法编译。
它本身只是 jieba 的 C 加速替代品（API 完全一致），仓库里只用到三个符号：
    GPT_SoVITS/text/chinese.py / chinese2.py :  jieba_fast.setLogLevel(..) + jieba_fast.posseg
    GPT_SoVITS/text/tone_sandhi.py           :  import jieba_fast as jieba
所以这里把它映射到**纯 Python 的 jieba**（local-models 里本来就有 jieba==0.42.1）。
代价：中文分词慢一点（12 句短片完全无感）；语义与 API 不变。

用法：python install_jieba_fast_shim.py     # 写进 clone 的 .venv/Lib/site-packages/jieba_fast.py
"""
import os
import sys

ROOT = os.environ.get("KURISU_AMADEUS_ROOT") or r"E:\DeepSeek1\work\_amadeus-src"
SHIM = '''# -*- coding: utf-8 -*-
"""jieba_fast 的替身（= 纯 Python jieba）。本机无 MSVC，无法编译真正的 jieba-fast；
它只是 jieba 的 C 加速版，API 相同。见 E:\\\\DeepSeek1\\\\work\\\\_tts-trial\\\\jieba_fast_shim.py。"""
import sys as _sys

import jieba as _jieba
import jieba.posseg as _posseg

from jieba import *          # noqa: F401,F403  (cut/lcut/lcut_for_search/tokenize/initialize ...)
from jieba import cut, lcut, lcut_for_search, tokenize, initialize, DEFAULT_DICT, dt  # noqa: F401

__version__ = getattr(_jieba, "__version__", "0.42.1")
posseg = _posseg
analyse = None
try:
    import jieba.analyse as _analyse
    analyse = _analyse
except Exception:            # pragma: no cover
    pass


def setLogLevel(level):
    return _jieba.setLogLevel(level)


def getLogLevel():
    return _jieba.getLogLevel()


# `import jieba_fast.posseg as psg` 需要子模块真的在 sys.modules 里
_sys.modules.setdefault(__name__ + ".posseg", _posseg)
_sys.modules.setdefault(__name__ + ".analyse", analyse) if analyse else None
'''


def main():
    sp = None
    for cand in (os.path.join(ROOT, ".venv", "Lib", "site-packages"),
                 os.path.join(ROOT, ".venv", "lib", "site-packages")):
        if os.path.isdir(cand):
            sp = cand
            break
    if not sp:
        print("找不到 .venv/Lib/site-packages —— 先跑 uv sync")
        return 1
    dst = os.path.join(sp, "jieba_fast.py")
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(SHIM)
    print("shim →", dst)
    # 立刻自检（在 clone 的 .venv 里跑）
    import subprocess
    py = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
    code = ("import jieba_fast, jieba_fast.posseg as psg;"
            "jieba_fast.setLogLevel(50);"
            "print('lcut:', jieba_fast.lcut('欢迎回来，实验室一切正常。'));"
            "print('posseg:', [(w.word, w.flag) for w in psg.cut('屏上的数字都来自真实接口')][:6])")
    p = subprocess.run([py, "-c", code], capture_output=True, text=True, encoding="utf-8")
    print("self-check rc=%s\nstdout: %s\nstderr: %s" % (p.returncode, p.stdout.strip(), p.stderr.strip()[-400:]))
    return 0 if p.returncode == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
