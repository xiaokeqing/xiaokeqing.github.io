import glob, re, io, collections
files = sorted(glob.glob("public/**/index.html", recursive=True))
print("pages", len(files))
cls = collections.Counter()
tags = collections.Counter()
for f in files:
    t = io.open(f, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r'class="([^"]*)"', t):
        for c in m.group(1).split():
            cls[c] += 1
    for m in re.finditer(r'<(\w+)[\s>]', t):
        tags[m.group(1).lower()] += 1
for c, n in cls.most_common(40):
    print("%5d %s" % (n, c))
print("--- tags ---")
for c, n in tags.most_common(15):
    print("%5d %s" % (n, c))
for p in ("public/index.html","public/status/index.html","public/alerts/index.html"):
    t = io.open(p, encoding="utf-8", errors="replace").read()
    print(p, "len", len(t), "table", t.count("<table"), "dock", t.count("dock"), "idcard", t.count("xk-idcard"), "mod", len(re.findall(r'class="mod', t)), "screen-hd", t.count("screen-hd"))
