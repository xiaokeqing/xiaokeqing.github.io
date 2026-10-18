# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
JS = """() => {
  const out = [];
  for (const s of ['.dock', '.xk-idcard', '.screen-hd', '.mod']) {
    document.querySelectorAll(s).forEach((el, i) => {
      const r = el.getBoundingClientRect();
      const st = getComputedStyle(el);
      out.push([s + '#' + i, Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height),
                st.position, st.display, st.visibility, st.opacity, (el.className||'').toString().slice(0,40)]);
    });
  }
  return out;
}"""
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    pg = b.new_page(viewport={"width": 390, "height": 900})
    for url in ("http://127.0.0.1:8126/", "http://127.0.0.1:8126/alerts/"):
        pg.goto(url, wait_until="load")
        pg.wait_for_timeout(300)
        print(url)
        for row in pg.evaluate(JS):
            print("  ", row)
    b.close()
