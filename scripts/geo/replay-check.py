#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
replay-check.py —— 「攻击来源地图 · 24h 回放」真浏览器自检（playwright / Edge）

为什么要有它：
  · 回放条是**运行时注入**的（不新增 <script>、不改生成物），Hugo minify 又会改 JS 标识符，
    所以"grep 源码里有没有函数名"证明不了任何事 —— 只能开真页面看 DOM 与画布像素。
  · 数据有两种合法状态：
      ① static/data/geo-hourly.json 的 available=false（公开接口没有「小时 × 国家」交叉）；
      ② available=true 且每个小时桶带 byCountry（后端补上交叉之后）。
    两种都要能验，所以跑三轮：
      A. 真数据：播放条必须是**禁用**态 + 文案含「读不到」「不回放」，静态视图画布已绘制；
      B. 夹具（**只在 public/data 里临时写，跑完还原，绝不提交**）：真小时总量 × 真 24h 国家占比，
         只为了让「播放」这条代码路径真的被点一次 —— 断言 700ms 换小时、画布重绘、标签变化、
         暂停可用、播到最后一格自动回静态；
      C. 手机口径 390×844：按钮 ≥40px、无横向溢出。
  · 控制台 error 要区分「本机没起后端导致的 /api/public 取数失败（预期）」与「其他 error」。

用法：
  python -X utf8 scripts/geo/replay-check.py [--public public] [--port 8811] [--channel msedge]
退出码：0 = 全部通过；1 = 有断言失败；2 = 环境问题（playwright / 浏览器 / 产物或数据缺失）。
"""
import argparse
import http.server
import json
import os
import shutil
import socketserver
import sys
import threading
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------- 本地静态服务
class _Quiet(http.server.SimpleHTTPRequestHandler):
    """禁缓存：夹具换内容后必须让浏览器真的重取，否则测到的是旧 JSON。"""

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        http.server.SimpleHTTPRequestHandler.end_headers(self)


def serve(directory, port):
    handler = lambda *a, **kw: _Quiet(*a, directory=directory, **kw)  # noqa: E731
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


# ---------------------------------------------------------------- 夹具（合成分布）
def build_fixture(real_path, sample_path):
    """真小时总量 × 真 24h 国家占比（每国带一点确定性抖动），只为覆盖播放代码路径。"""
    real = json.load(open(real_path, encoding="utf-8"))
    shares = {}
    try:
        raw = json.load(open(sample_path, encoding="utf-8"))
        data = raw.get("data", raw) if isinstance(raw, dict) else {}
        for c in data.get("byCountry") or []:
            cc = str(c.get("country") or c.get("countryCode") or "").upper()
            if len(cc) == 2 and float(c.get("count") or 0) > 0:
                shares[cc] = float(c["count"])
    except Exception:
        pass
    if not shares:
        shares = {"US": 6.0, "FR": 5.0, "NL": 4.0, "CN": 3.0, "GB": 2.0, "TR": 1.5, "AD": 1.0}
    tot = sum(shares.values())
    series = []
    for i, s in enumerate(real.get("series") or []):
        total = int(s.get("total") or 0)
        bc = {}
        for cc, w in shares.items():
            v = int(round(total * w / tot * (0.82 + 0.36 * ((i * 7 + len(cc)) % 5) / 4.0)))
            if v > 0:
                bc[cc] = v
        series.append({"hour": s.get("hour"), "total": total, "byCountry": bc})
    if not series:
        series = [{"hour": "2026-10-17T%02d:00" % h, "total": 100 + 20 * h,
                   "byCountry": {"US": 60 + h, "FR": 40 + (h % 5)}} for h in range(24)]
    return {
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hours": len(series),
        "source": "TEST FIXTURE（replay-check.py 临时合成：真小时总量 × 真 24h 国家占比）",
        "available": True,
        "series": series,
        "notes": "★测试夹具：scripts/geo/replay-check.py 写入 public/data/geo-hourly.json，"
                 "只为验证回放代码路径，跑完即还原，不提交、不代表真实分布。",
    }


# ---------------------------------------------------------------- 页面探针
PAINT_JS = """
() => {
  const c = document.getElementById('xkAtkMap');
  if (!c || !c.width || !c.height) return { ok: false, why: 'no canvas' };
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let n = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i]) n++;
  return { ok: true, w: c.width, h: c.height, painted: n };
}
"""

STATE_JS = """
() => {
  const box = document.querySelector('.xk-atkmap-replay');
  const play = box && box.querySelector('[data-xk-replay-play]');
  const pause = box && box.querySelector('[data-xk-replay-pause]');
  const seek = box && box.querySelector('[data-xk-replay-seek]');
  const lab = box && box.querySelector('[data-xk-replay-hour]');
  const r = play ? play.getBoundingClientRect() : null;
  return {
    hasBar: !!box,
    playDisabled: play ? !!play.disabled : null,
    pauseDisabled: pause ? !!pause.disabled : null,
    seekDisabled: seek ? !!seek.disabled : null,
    seekMax: seek ? Number(seek.max) : null,
    seekValue: seek ? Number(seek.value) : null,
    playText: play ? play.textContent.trim() : null,
    label: lab ? lab.textContent : null,
    playW: r ? Math.round(r.width) : null, playH: r ? Math.round(r.height) : null,
    replay: window.__xkReplay || null,
    scrollW: document.documentElement.scrollWidth,
    innerW: window.innerWidth,
  };
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", default="public")
    ap.add_argument("--port", type=int, default=8811)
    ap.add_argument("--channel", default="msedge", help="playwright 浏览器通道（本机只有 Edge）")
    ap.add_argument("--keep-fixture", action="store_true", help="排障用：跑完保留夹具")
    args = ap.parse_args()

    pub = args.public if os.path.isabs(args.public) else os.path.join(ROOT, args.public)
    if not os.path.isfile(os.path.join(pub, "alerts", "index.html")):
        print("环境问题：%s/alerts/index.html 不存在 —— 先跑 hugo" % pub)
        return 2
    target = os.path.join(pub, "data", "geo-hourly.json")
    if not os.path.isfile(target):
        print("环境问题：%s 不存在 —— 先跑 python -X utf8 scripts/geo/hourly.py 再 hugo" % target)
        return 2
    real = json.load(open(target, encoding="utf-8"))
    real_available = real.get("available") is True
    real_src = os.path.join(ROOT, "static", "data", "geo-hourly.json")
    sample = os.path.join(ROOT, "_dev", "api-samples", "geo-live.json")
    bak = target + ".real.bak"

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print("环境问题：playwright 不可用（%s）" % e)
        return 2

    httpd = serve(pub, args.port)
    base = "http://127.0.0.1:%d/alerts/#stats" % args.port
    fails, oks, errs = [], [], []
    wrote_fixture = [False]

    def ok(msg):
        oks.append(msg)
        print("  [PASS] " + msg)

    def bad(msg):
        fails.append(msg)
        print("  [FAIL] " + msg)

    def measure(name, val):
        print("  [MEASURE] %s = %s" % (name, json.dumps(val, ensure_ascii=False)))

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True, channel=args.channel)
            except Exception as e:
                print("环境问题：启动 %s 失败（%s）" % (args.channel, e))
                return 2

            def stats_page(width=1280, height=900):
                """每次都开新页：同一页二次导航/重载时外壳视图偶发停在 hidden，测不到地图卡。"""
                page = browser.new_page(viewport={"width": width, "height": height})
                page.on("console", lambda m: errs.append("%s: %s" % (m.type, m.text))
                        if m.type == "error" else None)
                page.on("pageerror", lambda e: errs.append("pageerror: %s" % e))
                page.goto(base, wait_until="domcontentloaded")
                page.wait_for_selector("[data-xk-atkmap]", state="visible", timeout=20000)
                page.locator("[data-xk-atkmap]").scroll_into_view_if_needed()
                page.wait_for_selector(".xk-atkmap-replay", state="visible", timeout=15000)
                page.wait_for_timeout(800)
                return page

            # ═════════════ A · 真数据 ═════════════
            print("\n=== A · 真数据（available=%s）===" % real_available)
            page = stats_page()
            st = page.evaluate(STATE_JS)
            paint = page.evaluate(PAINT_JS)
            measure("A.state", {k: st[k] for k in ("hasBar", "playDisabled", "seekDisabled",
                                                   "seekMax", "label", "playW", "playH", "replay")})
            measure("A.canvas", paint)
            if st["hasBar"]:
                ok("A 播放条已注入地图卡（运行时注入，HTML 里 <script> 数不变）")
            else:
                bad("A 播放条没注入（.xk-atkmap-replay 不存在）")
            lab = str(st.get("label") or "")
            if real_available:
                if st["playDisabled"] is False:
                    ok("A 真数据可用：播放按钮 enabled（available=true）")
                else:
                    bad("A available=true 但播放按钮 disabled")
            else:
                if st["playDisabled"] and st["seekDisabled"] and "读不到" in lab and "不回放" in lab:
                    ok("A 禁用态正确：▶/滑块 disabled + 「%s」" % lab[:80])
                else:
                    bad("A 禁用态不对：playDisabled=%s seekDisabled=%s label=%r"
                        % (st["playDisabled"], st["seekDisabled"], lab))
            if paint.get("ok") and paint["painted"] > 0:
                ok("A 静态视图画布已绘制（painted=%d / %dx%d）" % (paint["painted"], paint["w"], paint["h"]))
            else:
                bad("A 静态视图画布没画（%s）" % paint)
            page.close()

            # ═════════════ B · 夹具播放 ═════════════
            print("\n=== B · 夹具播放（临时写 public/data/geo-hourly.json，跑完还原）===")
            shutil.copy2(target, bak)
            fx = build_fixture(real_src, sample)
            open(target, "w", encoding="utf-8").write(json.dumps(fx, ensure_ascii=False, indent=1))
            wrote_fixture[0] = True

            page = stats_page()
            st0 = page.evaluate(STATE_JS)
            paint0 = page.evaluate(PAINT_JS)
            measure("B.before", {"label": st0["label"], "playDisabled": st0["playDisabled"],
                                 "seekMax": st0["seekMax"], "replay": st0["replay"],
                                 "painted": paint0.get("painted")})
            if st0["playDisabled"] is False and (st0.get("seekMax") or 0) == len(fx["series"]) - 1:
                ok("B 夹具被识别：播放可用，滑块上限 %d = 小时桶数-1" % st0["seekMax"])
            else:
                bad("B 夹具没被识别：playDisabled=%s seekMax=%s（数据没重取？）"
                    % (st0["playDisabled"], st0["seekMax"]))

            try:
                page.click(".xk-atkmap-replay [data-xk-replay-play]", timeout=8000)
            except Exception as e:
                bad("B 点播放失败：%s" % str(e).splitlines()[0])
            page.wait_for_timeout(3000)          # 3s ≈ 4 次 700ms 前进
            st1 = page.evaluate(STATE_JS)
            paint1 = page.evaluate(PAINT_JS)
            measure("B.after3s", {"label": st1["label"], "seekValue": st1["seekValue"],
                                  "playText": st1["playText"], "pauseDisabled": st1["pauseDisabled"],
                                  "replay": st1["replay"], "painted": paint1.get("painted")})
            if st1["label"] != st0["label"] or st1.get("seekValue") != st0.get("seekValue"):
                ok("B 播放推进：标签 %r → %r（滑块 %s）"
                   % ((st0["label"] or "")[:24], (st1["label"] or "")[:24], st1.get("seekValue")))
            else:
                bad("B 播放没推进：标签仍是 %r" % (st1["label"],))
            if paint1.get("ok") and paint1["painted"] > 0:
                ok("B 回放态画布已重绘（painted=%d / %dx%d）" % (paint1["painted"], paint1["w"], paint1["h"]))
            else:
                bad("B 回放态画布没画（%s）" % paint1)
            rp = st1.get("replay") or {}
            if rp.get("available") and rp.get("playing") and (rp.get("hour") or -1) >= 0:
                ok("B 回放状态标记：available=%s playing=%s hour=%s marks=%s"
                   % (rp.get("available"), rp.get("playing"), rp.get("hour"), rp.get("marks")))
            else:
                bad("B 回放状态标记不对：%s" % (rp,))

            page.click(".xk-atkmap-replay [data-xk-replay-pause]", timeout=6000)
            page.wait_for_timeout(200)
            stp = page.evaluate(STATE_JS)
            if "暂停" in str(stp.get("label") or "") and (stp.get("replay") or {}).get("playing") is False:
                ok("B 暂停可用：%r" % (stp["label"] or ""))
            else:
                bad("B 暂停没生效：label=%r replay=%s" % (stp.get("label"), stp.get("replay")))

            # 自动回静态：拖到倒数第二格再播放，两个 tick 后撞到最后一格
            page.evaluate("""() => { const s = document.querySelector('.xk-atkmap-replay [data-xk-replay-seek]');
                s.value = String(Number(s.max) - 1); s.dispatchEvent(new Event('input', {bubbles: true})); }""")
            page.wait_for_timeout(300)
            page.click(".xk-atkmap-replay [data-xk-replay-play]", timeout=6000)
            page.wait_for_timeout(2600)
            ste = page.evaluate(STATE_JS)
            if ste.get("label") == "静态 · 24h 汇总" and (ste.get("replay") or {}).get("hour") == -1:
                ok("B 播完自动回静态视图：label=%r，按钮文案回 %r" % (ste["label"], ste.get("playText")))
            else:
                bad("B 播完没回静态：label=%r replay=%s" % (ste.get("label"), ste.get("replay")))

            # ═════════════ C · 手机口径 ═════════════
            print("\n=== C · 手机 390×844（按钮 ≥40px / 无横向溢出）===")
            page.close()
            page = stats_page(390, 844)
            stm = page.evaluate(STATE_JS)
            sizes = page.evaluate("""() => Array.from(document.querySelectorAll('.xk-atkmap-replay button'))
                .map(b => { const r = b.getBoundingClientRect();
                            return {t: b.textContent.trim(), w: Math.round(r.width), h: Math.round(r.height)}; })""")
            measure("C.buttons", sizes)
            measure("C.widths", {"scrollW": stm["scrollW"], "innerW": stm["innerW"]})
            small = [s for s in sizes if s["w"] < 40 or s["h"] < 40]
            if sizes and not small:
                ok("C 播放条按钮 ≥40px（%s）" % ", ".join("%s %dx%d" % (s["t"], s["w"], s["h"]) for s in sizes))
            else:
                bad("C 有按钮小于 40px：%s" % small)
            if stm["scrollW"] <= stm["innerW"] + 1:
                ok("C 无横向溢出（scrollWidth %d ≤ innerWidth %d）" % (stm["scrollW"], stm["innerW"]))
            else:
                bad("C 横向溢出：scrollWidth %d > innerWidth %d" % (stm["scrollW"], stm["innerW"]))
            page.close()

            # ═════════════ 控制台 ═════════════
            offline = [e for e in errs if "/api/public" in e or "ERR_CONNECTION_REFUSED" in e
                       or "Failed to fetch" in e or "net::ERR" in e or "404" in e]
            other = [e for e in errs if e not in offline]
            measure("console.errors", {"total": len(errs), "离线/接口 404（预期）": len(offline),
                                       "其他": len(other)})
            if other:
                bad("控制台有 %d 条与回放无关的 error：%s" % (len(other), other[:3]))
            else:
                ok("控制台无 error（本机没起后端 → /api/public 取数失败 %d 条，属预期）" % len(offline))

            browser.close()
    except Exception:
        traceback.print_exc()
        print("  · 脚本异常（详见上面的 traceback）")
        fails.append("脚本异常")
    finally:
        httpd.shutdown()
        if wrote_fixture[0] and not args.keep_fixture:
            shutil.move(bak, target)
            print("\n  夹具已删除，public/data/geo-hourly.json 已还原为真数据")
        elif args.keep_fixture:
            print("\n  --keep-fixture：夹具保留在 %s（排障后记得还原）" % target)
        else:
            print("\n  这次没写夹具，未改动 public/data/geo-hourly.json")

    print("\n===== 结果：%d 项通过，%d 项失败 =====" % (len(oks), len(fails)))
    for f in fails:
        print("  · " + f)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
