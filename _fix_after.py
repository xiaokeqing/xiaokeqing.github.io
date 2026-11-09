import io
p = r"F:\7AAA\AI\blog\assets\js\xk-after.js"
s = io.open(p, encoding="utf-8").read()
old = """  /* ② wb-api 抄写 + 清空 */
  try {
    var m = document.querySelector('meta[name="wb-api"]');
    if (m) {
      var v = m.getAttribute('content') || '';
      if (v) { document.documentElement.setAttribute('data-wb-api', v); }
      if (location.search.indexOf('live=1') < 0) { m.setAttribute('content', ''); }
    }
  } catch (e) { }

"""
assert old in s
s = s.replace(old, """  /* ② wb-api 抄写 + 清空 —— 2026-11-09 移到 xk-boot.js（阻塞脚本）：
        数据页的 xk-bind.js 是 body 里的普通脚本，会比这里（defer）更早执行，
        放在这里会导致它读到 demo 域名、去打 ~600 B/s 的隧道，整屏"读不到"。 */

""")
s = s.replace("   ② 把 <meta name=\"wb-api\"> 的原值抄到 <html data-wb-api> 再清空 meta：\n      数据页因此改读同源静态快照（static/api/public/*），只有 /ai/ 问答与 SSE 回退用这份原值。\n      ?live=1 时保留原值继续打实时接口。\n   ③ 无障碍兜底",
              "   ② 无障碍兜底")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("xk-after.js patched, bytes", len(s))
