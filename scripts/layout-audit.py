#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""排版审计（layout audit）—— 对 public/ 里每一页在多个宽度下做 9 项排版检查。

为什么要有这个脚本
------------------
站点的排版问题（横向溢出、浮层压住正文、文字被裁、窄屏表格撑破页面）在
1280 桌面宽度下看不出来，而在 390 手机宽度下才暴露。肉眼看 90 多页 × 3 个宽度
不现实，所以把判据变成数字：谁越界、越过多少、哪个选择器、什么字号。

三种运行模式（自动选择，报告里会写明用的是哪一种）
--------------------------------------------------
1. real      playwright + 本机 Chromium 内核（默认 Edge，即 channel=msedge）。
             真实渲染，9 项全部可判。这是唯一"算真测过"的模式。
2. static    没有 playwright / 浏览器时，退化为纯静态分析（读 HTML + CSS 文本）。
             只做能量出来的两三项，其余全部标 NA 并在报告里明确写
             【未做真实渲染】—— 不假装测过。退出码 2。
3. check      --check-only：不重新测，只读已有的 docs/layout-audit.json 复核结论，
              给 CI / assert-build.sh 用（毫秒级）。默认只有「必须修（P0）」命中才
              返回 1；加 --strict 才把任意 FAIL（含 P1/P2 建议项）算失败。

退出码
------
0  全部 PASS（NA 不算失败；check-only 下 = 无 P0）
1  有 FAIL（check-only 下 = 有 P0，或 --strict 且有任意 FAIL）
2  环境不满足（没有真实渲染能力 / 页面全部渲染失败 / 没有可复核的 JSON）

用法
----
  python -X utf8 scripts/layout-audit.py --widths 390,768,1280
  python -X utf8 scripts/layout-audit.py --pages /alerts/ /status/
  python -X utf8 scripts/layout-audit.py --json - --check-only     # CI 复核
  python -X utf8 scripts/layout-audit.py --serve                   # 站没起时自己拉一个

注意：本脚本只测量，不改任何页面样式。
"""

import argparse
import datetime
import glob as globmod
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Windows 控制台默认 cp936，中文一 print 就 UnicodeEncodeError；统一成 utf-8/replace。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

DEFAULT_WIDTHS = [390, 768, 1280]
DEFAULT_BASE = "http://127.0.0.1:8126"
DEFAULT_JSON = os.path.join("docs", "layout-audit.json")
DEFAULT_MD = os.path.join("docs", "排版检查-20261018.md")
VIEWPORT_HEIGHT = 900
NAV_TIMEOUT_MS = 20000
IDLE_TIMEOUT_MS = 4000
SETTLE_MS = 200  # 布局在 load 后 ~200ms 定型；页面有轮询，等 networkidle 会空耗
REMEASURE_MS = 400  # 有 FAIL 时再等这么久复测一次，滤掉「脚本替换文案」这类瞬态
MOBILE_MAX = 420  # <= 这个宽度才算"手机宽度"，点击区检查只在这里做

# 9 项检查的元信息。severity 决定报告里落到「必须修 / 建议修」哪一档。
CHECKS = [
    {"id": 1, "key": "c1", "name": "横向溢出", "sev": "P0",
     "rule": "documentElement.scrollWidth > innerWidth + 1"},
    {"id": 2, "key": "c2", "name": "元素重叠", "sev": "P0",
     "rule": ".dock / .xk-idcard / 首个 .screen-hd|.mod 的 getBoundingClientRect 相交（>1px）"},
    {"id": 3, "key": "c3", "name": "文字被裁", "sev": "P0",
     "rule": "overflow 含 hidden|clip 且 scrollWidth > clientWidth+2 且含非空文本节点"},
    {"id": 4, "key": "c4", "name": "表格窄屏", "sev": "P0",
     "rule": "table 自身溢出或宽于视口时，祖先必须有 overflow-x: auto|scroll"},
    {"id": 5, "key": "c5", "name": "卡片一致性", "sev": "P2",
     "rule": ".mod（缺则退化为 .xk-card）的 border-radius / border / background 取值种类，任一 > 3 种记 FAIL"},
    {"id": 6, "key": "c6", "name": "中英混排行高", "sev": "P1",
     "rule": "p/li/td 的 font-size < 13px，或 line-height/font-size < 1.4"},
    {"id": 7, "key": "c7", "name": "点击区尺寸", "sev": "P1",
     "rule": "手机宽度下 a/button 的 height < 40 或 width < 40（仅 <=420px 宽度适用）"},
    {"id": 8, "key": "c8", "name": "空态/降级文案", "sev": "P1",
     "rule": "含「读不到/不补数/取数中」的元素必须 white-space: normal 且不横向溢出"},
    {"id": 9, "key": "c9", "name": "对比度", "sev": "P1",
     "rule": "p/li/td 文字色与最近不透明祖先底色的 WCAG 对比度 < 3.0 记 FAIL"},
]
CHECK_BY_ID = {}
for _c in CHECKS:
    CHECK_BY_ID[_c["id"]] = _c
    CHECK_BY_ID[str(_c["id"])] = _c  # checks 字典的键统一是 str，这里两种都认

# --------------------------------------------------------------------------
# 浏览器内测量：一次 evaluate 把 9 项全部量完，返回纯 JSON。
# 所有阈值与 CHECKS 里的 rule 一一对应。
# --------------------------------------------------------------------------
MEASURE_JS = r"""
(arg) => {
  const mobile = (arg && arg.mobile) || 390;
  const vw = window.innerWidth;
  const out = {};

  function sel(el) {
    if (!el || !el.tagName) return '?';
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    let cn = '';
    try {
      cn = (typeof el.className === 'string') ? el.className
         : (el.getAttribute && el.getAttribute('class')) || '';
    } catch (e) { cn = ''; }
    cn = String(cn).trim().split(/\s+/).filter(Boolean).slice(0, 3).join('.');
    if (cn) s += '.' + cn;
    return s;
  }
  function snippet(el) {
    const t = (el && el.textContent ? el.textContent : '').replace(/\s+/g, ' ').trim();
    return t.slice(0, 60);
  }
  function vis(el) {
    if (!el || !el.getClientRects || !el.getClientRects().length) return false;
    const r = el.getBoundingClientRect();
    if (!(r.width > 1 && r.height > 1)) return false;
    // opacity:0 的元素（如 .dock--wait 的加载态）在屏幕上看不见，不能算"压住"
    if (parseFloat(getComputedStyle(el).opacity) < 0.2) return false;
    return true;
  }
  function rect(el) { return el.getBoundingClientRect(); }
  function parseColor(v) {
    if (!v) return null;
    const m = String(v).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(function (x) { return parseFloat(x); });
    if (p.length < 3 || p.some(function (x) { return isNaN(x); })) return null;
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  }
  function lum(c) {
    function f(x) { x = x / 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); }
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  }
  function contrast(a, b) {
    const l1 = lum(a), l2 = lum(b);
    const hi = Math.max(l1, l2), lo = Math.min(l1, l2);
    return (hi + 0.05) / (lo + 0.05);
  }
  // 背景判定：这个站的正文压在「整屏照片 + 半透明暗色遮罩」上，遮罩常常不是祖先
  // （固定定位的场景层 + rgba 半透明卡片各管一层），只看「alpha≥0.9 的祖先」会一路
  // 走到 body 的浅色底，于是白字被判成 1.03:1 —— 假 FAIL。所以改成：
  //   1) 从元素往上收集所有 alpha>0.15 的底色层，按 over 合成到最底下的不透明层；
  //   2) 整页存在「铺满视口的固定背景层」时，且文字自己这一路没有任何填充层
  //      （等于直接压在照片上）→ 判不了，跳过，不瞎判。
  function sceneBackdrop() {
    const out = [];
    const all = document.querySelectorAll('body *');
    for (let i = 0; i < all.length && i < 1500; i++) {
      const el = all[i];
      const cs = getComputedStyle(el);
      if (cs.position !== 'fixed') continue;
      const r = el.getBoundingClientRect();
      if (r.width < vw * 0.9 || r.height < window.innerHeight * 0.9) continue;
      const c = parseColor(cs.backgroundColor) || [0, 0, 0, 0];
      const hasImg = cs.backgroundImage && cs.backgroundImage !== 'none';
      if (hasImg || c[3] > 0.3) out.push(sel(el));
    }
    return out;
  }
  const BACKDROP = sceneBackdrop();
  function bgOf(el) {
    const layersC = [];
    const names = [];
    let cur = el, depth = 0, base = null;
    while (cur && depth++ < 18) {
      const cs = getComputedStyle(cur);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') {
        return { unknown: true, from: 'bgimg@' + sel(cur), layersC: layersC, opaque: false, base: [255, 255, 255] };
      }
      const c = parseColor(cs.backgroundColor);
      if (c && c[3] > 0.15 && c[3] < 0.99) { layersC.push(c); names.push(sel(cur)); }
      if (c && c[3] >= 0.99) { base = { c: c, from: sel(cur), tag: cur.tagName }; break; }
      cur = cur.parentElement;
    }
    // body/html 的底色会被整屏固定背景层盖住，不能当作「真底色」
    if (!base) {
      const b = document.body ? parseColor(getComputedStyle(document.body).backgroundColor) : null;
      base = { c: (b && b[3] > 0.5) ? b : [255, 255, 255, 1], from: 'body', tag: 'BODY' };
    }
    const opaque = !(BACKDROP.length && /^(BODY|HTML)$/.test(base.tag || ''));
    const from = names.length ? names[0] + (names.length > 1 ? "+" + (names.length - 1) + "层" : "") : base.from;
    return { unknown: false, layersC: layersC, names: names, base: base.c, opaque: opaque, from: from };
  }

  const meta = {
    innerWidth: vw,
    innerHeight: window.innerHeight,
    scrollWidth: document.documentElement.scrollWidth,
    scrollHeight: document.documentElement.scrollHeight,
    elementCount: document.querySelectorAll('body *').length,
    title: document.title || ''
  };

  // ---- ① 横向溢出 --------------------------------------------------------
  const over = [];
  if (meta.scrollWidth > vw + 1) {
    const els = document.querySelectorAll('body *');
    for (let i = 0; i < els.length && over.length < 24; i++) {
      const el = els[i];
      if (!vis(el)) continue;
      const r = rect(el);
      if (r.right > vw + 1) {
        over.push({ sel: sel(el), right: Math.round(r.right), width: Math.round(r.width), text: snippet(el) });
      }
    }
  }
  out.c1 = {
    scrollWidth: meta.scrollWidth,
    innerWidth: vw,
    exceed: meta.scrollWidth - vw,
    fail: meta.scrollWidth > vw + 1,
    count: over.length,
    samples: over
  };

  // ---- ② 元素重叠 --------------------------------------------------------
  const roles = [['.dock', '.dock'], ['.xk-idcard', '.xk-idcard'], ['.screen-hd', '.screen-hd'], ['.mod', '.mod']];
  const found = [];
  roles.forEach(function (pair) {
    const label = pair[0];
    const s = pair[1];
    let el = null;
    try { el = document.querySelector(s); } catch (e) { el = null; }
    if (el && vis(el)) found.push({ name: label, el: el, sel: sel(el) });
  });
  const pairs = [];
  for (let i = 0; i < found.length; i++) {
    for (let j = i + 1; j < found.length; j++) {
      const a = found[i], b = found[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      const ra = rect(a.el), rb = rect(b.el);
      const ox = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
      const oy = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
      if (ox > 1 && oy > 1) {
        const pa = getComputedStyle(a.el).position, pb = getComputedStyle(b.el).position;
        pairs.push({
          a: a.name, b: b.name, aSel: a.sel, bSel: b.sel,
          overlapW: Math.round(ox), overlapH: Math.round(oy), area: Math.round(ox * oy),
          bothFixed: (pa === 'fixed' && pb === 'fixed'),
          thin: Math.min(ox, oy) <= 16
        });
      }
    }
  }
  // 两个 position:fixed 的装饰层之间只差几个像素的相交（顶栏 vs 下挂头像卡），
  // 更像刻意层叠而不是排版事故：仍记 FAIL（判据就是"相交"），但标注出来交给人判断。
  const soft = pairs.length > 0 && pairs.every(function (p) { return p.bothFixed && p.thin; });
  out.c2 = {
    found: found.map(function (f) { return f.sel; }),
    fail: pairs.length > 0,
    soft: soft,
    count: pairs.length,
    samples: pairs
  };

  // ---- ③ 文字被裁 --------------------------------------------------------
  const clipped = [];
  const els3 = document.querySelectorAll('body *');
  for (let i = 0; i < els3.length; i++) {
    if (clipped.length >= 30) break;
    const el = els3[i];
    if (!el.firstChild) continue;
    const cw = el.clientWidth;
    if (!(cw > 0)) continue;
    if (!(el.scrollWidth > cw + 2)) continue;
    const rr = el.getBoundingClientRect();
    // 1×1 的 sr-only / 视觉隐藏工具类不是"文字被裁"，它有意图地藏起内容
    if (rr.width <= 4 || rr.height <= 4) continue;
    const cls = String(el.className || '');
    if (/(sr-only|visually-hidden|screen-reader|only-screen-reader|hl-hidden)/i.test(cls)) continue;
    if (el.getAttribute && el.getAttribute('aria-hidden') === 'true') continue;
    const st = getComputedStyle(el);
    const ovx = st.overflowX, ovy = st.overflowY;
    if (!/(hidden|clip)/.test(ovx) && !/(hidden|clip)/.test(ovy)) continue;
    let hasText = false;
    for (let k = 0; k < el.childNodes.length; k++) {
      const n = el.childNodes[k];
      if (n.nodeType === 3 && n.textContent.trim()) { hasText = true; break; }
    }
    if (!hasText) continue;
    clipped.push({
      sel: sel(el), scrollW: el.scrollWidth, clientW: cw,
      overflow: ovx + '/' + ovy, text: snippet(el)
    });
  }
  out.c3 = { fail: clipped.length > 0, count: clipped.length, samples: clipped };

  // ---- ④ 表格窄屏 --------------------------------------------------------
  let tables = [];
  try { tables = Array.prototype.slice.call(document.querySelectorAll('table')); } catch (e) { tables = []; }
  const tableInfo = tables.map(function (t) {
    const cw = t.clientWidth, swd = t.scrollWidth;
    const selfNeed = swd > cw + 1;
    const r = rect(t);
    const viewportNeed = r.width > vw + 1;
    let anc = t.parentElement, guard = 0, wrapper = null;
    // table itself is the scroll container (.screen-bd table{display:block;overflow-x:auto})
    // user can scroll to see all columns, equivalent to a scrollable ancestor -> not FAIL
    const tst = getComputedStyle(t);
    if (/(auto|scroll)/.test(tst.overflowX)) { wrapper = sel(t) + ' (self)'; }
    while (anc && guard++ < 24 && anc !== document.body) {
      const s = getComputedStyle(anc);
      if (/(auto|scroll)/.test(s.overflowX)) { wrapper = sel(anc); break; }
      anc = anc.parentElement;
    }
    return {
      sel: sel(t), scrollW: swd, clientW: cw, width: Math.round(r.width),
      need: selfNeed || viewportNeed, selfNeed: selfNeed, viewportNeed: viewportNeed,
      wrapper: wrapper
    };
  });
  const tableBad = tableInfo.filter(function (t) { return t.need && !t.wrapper; });
  out.c4 = {
    tables: tables.length,
    fail: tableBad.length > 0,
    count: tableBad.length,
    samples: tableBad,
    all: tableInfo.slice(0, 8)
  };

  // ---- ⑤ 卡片一致性 ------------------------------------------------------
  let scope = '.mod';
  let cards = Array.prototype.slice.call(document.querySelectorAll('.mod'));
  if (!cards.length) {
    scope = '.xk-card';
    cards = Array.prototype.slice.call(document.querySelectorAll('.xk-card'));
  }
  cards = cards.slice(0, 60);
  const radii = {}, borders = {}, bgs = {};
  cards.forEach(function (el) {
    const st = getComputedStyle(el);
    const r = [st.borderTopLeftRadius, st.borderTopRightRadius, st.borderBottomRightRadius, st.borderBottomLeftRadius].join(' ');
    radii[r] = (radii[r] || 0) + 1;
    const b = st.borderTopWidth + ' ' + st.borderTopStyle + ' ' + st.borderTopColor;
    borders[b] = (borders[b] || 0) + 1;
    const g = st.backgroundColor + (st.backgroundImage && st.backgroundImage !== 'none' ? ' +img' : '');
    bgs[g] = (bgs[g] || 0) + 1;
  });
  const nR = Object.keys(radii).length, nB = Object.keys(borders).length, nG = Object.keys(bgs).length;
  out.c5 = {
    scope: scope,
    cards: cards.length,
    radii: radii, borders: borders, bgs: bgs,
    distinct: { radius: nR, border: nB, background: nG },
    fail: cards.length > 0 && (nR > 3 || nB > 3 || nG > 3),
    count: Math.max(0, Math.max(nR, nB, nG) - 3),
    samples: []
  };

  // ---- ⑥ 中英混排行高 ----------------------------------------------------
  const small = [], tight = [];
  let smallN = 0, tightN = 0;
  Array.prototype.slice.call(document.querySelectorAll('p,li,td')).forEach(function (el) {
    if (!vis(el)) return;
    const st = getComputedStyle(el);
    const fs = parseFloat(st.fontSize) || 0;
    if (!fs) return;
    const lhRaw = st.lineHeight;
    let lhv = (lhRaw === 'normal') ? fs * 1.2 : parseFloat(lhRaw);
    if (!(lhv > 0)) lhv = fs * 1.2;
    const rat = lhv / fs;
    if (fs < 13) {
      smallN++;
      if (small.length < 12) small.push({ sel: sel(el), fontSize: +fs.toFixed(1), text: snippet(el) });
    } else if (rat < 1.4 - 0.001) {
      tightN++;
      if (tight.length < 12) {
        tight.push({ sel: sel(el), fontSize: +fs.toFixed(1), lineHeight: +lhv.toFixed(1), ratio: +rat.toFixed(2), text: snippet(el) });
      }
    }
  });
  out.c6 = {
    fail: (smallN + tightN) > 0,
    count: smallN + tightN,
    smallFontCount: smallN,
    tightLineHeightCount: tightN,
    samples: small.concat(tight).slice(0, 16)
  };

  // ---- ⑦ 点击区尺寸（仅手机宽度）---------------------------------------
  const taps = [];
  let tapN = 0;
  if (vw <= 420) {
    Array.prototype.slice.call(document.querySelectorAll('a,button')).forEach(function (el) {
      if (!vis(el)) return;
      const r = rect(el);
      const w = Math.round(r.width), h = Math.round(r.height);
      if (w < 40 || h < 40) {
        tapN++;
        if (taps.length < 12) taps.push({ sel: sel(el), w: w, h: h, text: snippet(el) });
      }
    });
  }
  out.c7 = { applicable: vw <= 420, fail: tapN > 0, count: tapN, samples: taps };

  // ---- ⑧ 空态/降级文案 ---------------------------------------------------
  const KW = ['读不到', '不补数', '取数中'];
  const deg = [];
  try {
    const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT, null);
    let n;
    while ((n = walker.nextNode())) {
      const t = n.textContent || '';
      if (KW.indexOf(t.replace(/\s+/g, '').slice(0, 3)) < 0) {
        let hit = false;
        for (let i = 0; i < KW.length; i++) { if (t.indexOf(KW[i]) >= 0) { hit = true; break; } }
        if (!hit) continue;
      }
      const el = n.parentElement;
      if (!el) continue;
      let dup = false;
      for (let i = 0; i < deg.length; i++) { if (deg[i].el === el) { dup = true; break; } }
      if (dup) continue;
      const st = getComputedStyle(el);
      const r = rect(el);
      const ws = st.whiteSpace;
      const overflow = el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2;
      deg.push({
        el: el, sel: sel(el), whiteSpace: ws,
        width: Math.round(r.width), height: Math.round(r.height),
        clientW: el.clientWidth, scrollW: el.scrollWidth,
        overflow: overflow, nowrap: (ws === 'nowrap'),
        text: t.replace(/\s+/g, ' ').trim().slice(0, 40)
      });
    }
  } catch (e) { /* TreeWalker 不可用时留空 */ }
  const degBad = deg.filter(function (d) { return d.nowrap || d.overflow; });
  out.c8 = {
    found: deg.length,
    fail: degBad.length > 0,
    count: degBad.length,
    samples: degBad.map(function (d) {
      return { sel: d.sel, whiteSpace: d.whiteSpace, width: d.width, clientW: d.clientW, scrollW: d.scrollW,
               overflow: d.overflow, nowrap: d.nowrap, text: d.text };
    }).slice(0, 12),
    all: deg.map(function (d) {
      return { sel: d.sel, whiteSpace: d.whiteSpace, width: d.width, text: d.text };
    }).slice(0, 8)
  };

  // ---- ⑨ 对比度 ----------------------------------------------------------
  // 这个站的正文文字大量落在 div/span 里（p/li/td 只在少数页有内容），
  // 所以取「叶子文字容器」：有直接文本节点、且子元素都是行内。否则整站这项会全是 NA。
  const low = [];
  let checked = 0, lowN = 0, skipped = 0, backdropSkipped = 0;
  const c9sel = 'p,li,td,th,dd,dt,blockquote,span,div,label,strong,em,b,i,small,a,button,h1,h2,h3,h4';
  Array.prototype.slice.call(document.querySelectorAll(c9sel)).forEach(function (el) {
    if (checked >= 400) return;
    if (!vis(el)) return;
    let direct = 0;
    for (let k = 0; k < el.childNodes.length; k++) {
      const n = el.childNodes[k];
      if (n.nodeType === 3) direct += n.textContent.trim().length;
    }
    if (direct < 2) return;
    let mixed = false;
    for (let k = 0; k < el.children.length; k++) {
      const d = getComputedStyle(el.children[k]).display;
      if (d !== 'inline' && d !== 'inline-block' && d !== 'contents' && d !== 'inline-flex') { mixed = true; break; }
    }
    if (mixed) return;  // 容器里混着块级子元素，文字色可能不一致，跳过
    const st = getComputedStyle(el);
    const fg = parseColor(st.color);
    if (!fg) return;
    const bg = bgOf(el);
    if (bg.unknown) { skipped++; return; }  // 背景是图片：判不了就不判
    // 合成：把收集到的半透明层按 over 叠到某个底色上
    function comp(baseRGB) {
      let rgb = baseRGB.slice(0, 3);
      for (let i = bg.layersC.length - 1; i >= 0; i--) {
        const l = bg.layersC[i], a = l[3];
        rgb = [a * l[0] + (1 - a) * rgb[0], a * l[1] + (1 - a) * rgb[1], a * l[2] + (1 - a) * rgb[2]];
      }
      return rgb;
    }
    function contrastOn(baseRGB) {
      const b = comp(baseRGB);
      const f = fg[3] < 0.99
        ? [fg[3] * fg[0] + (1 - fg[3]) * b[0], fg[3] * fg[1] + (1 - fg[3]) * b[1], fg[3] * fg[2] + (1 - fg[3]) * b[2]]
        : [fg[0], fg[1], fg[2]];
      return { ratio: contrast(f, b), bg: b };
    }
    // 有整屏固定背景（照片/遮罩）且文字这一路没有不透明填充时，真实底色在「最暗」和「最亮」
    // 之间摆动 —— 两个边界都算，只有两边都 < 3.0 才算 FAIL，跨阈值的记「未定」而不是瞎判。
    const bases = bg.opaque ? [bg.base]
      : (BACKDROP.length ? [[10, 13, 17], [248, 251, 255]] : [bg.base]);
    const evals = bases.map(contrastOn);
    let cr = evals[0], lo = evals[0].ratio, hi = evals[0].ratio, undet = false;
    evals.forEach(function (v) {
      if (v.ratio < lo) { lo = v.ratio; cr = v; }
      if (v.ratio > hi) hi = v.ratio;
    });
    if (evals.length > 1 && !(hi < 3.0) && !(lo >= 3.0)) undet = true;
    if (undet) { backdropSkipped++; return; }
    checked++;
    if (lo < 3.0) {
      lowN++;
      if (low.length < 12) {
        low.push({
          sel: sel(el), fg: st.color,
          bg: 'rgb(' + cr.bg.map(function (x) { return Math.round(x); }).join(',') + ')@' + bg.from,
          ratio: +lo.toFixed(2), text: snippet(el)
        });
      }
    }
  });
  out.c9 = { checked: checked, skipped: skipped, backdropSkipped: backdropSkipped,
             backdrop: BACKDROP.slice(0, 3), fail: lowN > 0, count: lowN, samples: low };

  return { meta: meta, checks: out };
}
"""


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------
def log(msg):
    sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


def norm_route(rel_path):
    """public/about/index.html -> /about/ ；public/index.html -> /"""
    s = rel_path.replace("\\", "/")
    s = s[len("public/"):] if s.startswith("public/") else s
    if s.endswith("index.html"):
        s = s[: -len("index.html")]
    if not s.startswith("/"):
        s = "/" + s
    return s


def url_for(base, route):
    q = urllib.parse.quote(route, safe="/")
    return base.rstrip("/") + q


def discover_pages(public_dir, only=None):
    """glob 扫出 public 下所有 index.html，返回 [(route, rel_path)]。"""
    pat = os.path.join(public_dir, "**", "index.html")
    found = sorted(globmod.glob(pat, recursive=True))
    rows = []
    for p in found:
        rel = os.path.relpath(p, public_dir).replace("\\", "/")
        route = norm_route(rel)
        rows.append((route, rel))
    if only:
        want = set(x if x.startswith("/") else "/" + x for x in only)
        want = set(x if x.endswith("/") else x + "/" for x in want)
        rows = [r for r in rows if r[0] in want]
    return rows


def fetch_ok(url, timeout=3):
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return s.connect_ex(("127.0.0.1", port)) != 0
    finally:
        s.close()


def pick_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# --------------------------------------------------------------------------
# 真实渲染（playwright）
# --------------------------------------------------------------------------
def have_playwright():
    try:
        import playwright  # noqa: F401
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except Exception:
        return False


def launch_browser(p):
    """优先 msedge，其次 chrome，最后 playwright 自带 chromium。返回 (browser, mode_name)。"""
    attempts = []
    attempts.append(("chromium", {"channel": "msedge", "headless": True}))
    attempts.append(("chromium", {"channel": "chrome", "headless": True}))
    attempts.append(("chromium", {"headless": True}))
    errs = []
    for name, kw in attempts:
        try:
            browser = getattr(p, name).launch(**kw)
            label = "playwright+" + (kw.get("channel") or "bundled-chromium")
            return browser, label
        except Exception as e:
            errs.append("%s: %s" % (kw.get("channel") or "bundled", str(e).split("\n")[0][:160]))
    raise RuntimeError("所有浏览器启动方式都失败：" + " | ".join(errs))


def status_from(ok_flag):
    return "PASS" if ok_flag else "FAIL"


def normalise_checks(raw, width):
    """把浏览器返回的原始数值翻译成 {check_id: {status, detail, samples}}。"""
    c = raw.get("checks", {})
    res = {}

    # ① 横向溢出
    x = c.get("c1", {})
    body = "scrollWidth=%s innerWidth=%s" % (x.get("scrollWidth"), x.get("innerWidth"))
    if x.get("fail"):
        extra = "；越界 %s px" % x.get("exceed")
        smp = x.get("samples") or []
        if smp:
            extra += "；首个越界元素 " + smp[0]["sel"] + " right=" + str(smp[0]["right"])
        res[1] = {"status": "FAIL", "detail": body + extra,
                  "samples": [s["sel"] + " right=%s w=%s" % (s["right"], s["width"]) for s in smp]}
    else:
        res[1] = {"status": "PASS", "detail": body + "（无越界）", "samples": []}

    # ② 元素重叠
    y = c.get("c2", {})
    found = y.get("found") or []
    if not found:
        res[2] = {"status": "NA", "detail": "本页没有 .dock / .xk-idcard / .screen-hd / .mod 中的可测量元素",
                  "samples": []}
    elif y.get("fail"):
        smp = y.get("samples") or []
        soft = bool(y.get("soft"))
        detail = "%s 处相交；%s" % (len(smp), "；".join(
            "%s×%s 重叠 %sx%s" % (s["a"], s["b"], s["overlapW"], s["overlapH"]) for s in smp))
        rec = {"status": "FAIL", "detail": detail,
               "samples": ["%s × %s area=%s" % (s["aSel"], s["bSel"], s["area"]) for s in smp]}
        if soft:
            # 两者都是 position:fixed 的固定装饰层、且只差几像素 → 刻意层叠，交人判断
            rec["detail"] = detail + "（两者都是 position:fixed 的固定装饰，重叠 ≤16px：疑似刻意层叠，需人工确认是否要修）"
            rec["tier"] = "建议修"
        res[2] = rec
    else:
        res[2] = {"status": "PASS", "detail": "测了 " + " / ".join(found) + "，两两不相交", "samples": []}

    # ③ 文字被裁
    z = c.get("c3", {})
    smp = z.get("samples") or []
    if z.get("fail"):
        res[3] = {"status": "FAIL",
                  "detail": "%s 处 overflow:hidden 且内容超宽；首例 %s scrollWidth=%s clientWidth=%s" % (
                      len(smp), smp[0]["sel"], smp[0]["scrollW"], smp[0]["clientW"]),
                  "samples": ["%s %s/%s «%s»" % (s["sel"], s["scrollW"], s["clientW"], s["text"][:24]) for s in smp]}
    else:
        res[3] = {"status": "PASS", "detail": "没有「overflow 裁剪 + 内容超宽 + 有文本」的元素", "samples": []}

    # ④ 表格窄屏
    w = c.get("c4", {})
    if not w.get("tables"):
        res[4] = {"status": "NA", "detail": "本页没有 <table>", "samples": []}
    elif w.get("fail"):
        smp = w.get("samples") or []
        res[4] = {"status": "FAIL",
                  "detail": "%s 个表格需要横向滚动但祖先没有 overflow-x:auto|scroll：%s" % (
                      len(smp), "；".join("%s scrollWidth=%s clientWidth=%s" % (s["sel"], s["scrollW"], s["clientW"]) for s in smp)),
                  "samples": ["%s w=%s scrollWidth=%s clientWidth=%s（%s）" % (
                      s["sel"], s.get("width"), s["scrollW"], s["clientW"],
                      "表体溢出" if s.get("selfNeed") else "表格宽于视口") for s in smp]}
    else:
        res[4] = {"status": "PASS",
                  "detail": "本页 %s 个表格，需要滚动的都有 overflow-x 祖先（%s）" % (
                      w.get("tables"), ", ".join(sorted({s["wrapper"] for s in (w.get("all") or []) if s.get("wrapper")})) or "无需滚动"),
                  "samples": []}

    # ⑤ 卡片一致性
    v = c.get("c5", {})
    if not v.get("cards"):
        res[5] = {"status": "NA", "detail": "本页既没有 .mod 也没有 .xk-card", "samples": []}
    else:
        d = v.get("distinct") or {}
        det = "%s × %s 张：border-radius %s 种 / border %s 种 / background %s 种" % (
            v.get("scope"), v.get("cards"), d.get("radius"), d.get("border"), d.get("background"))
        allvals = []
        for k, vv in (v.get("radii") or {}).items():
            allvals.append("radius=%s×%s" % (k, vv))
        for k, vv in (v.get("bgs") or {}).items():
            allvals.append("bg=%s×%s" % (k, vv))
        res[5] = {"status": status_from(not v.get("fail")), "detail": det, "samples": allvals[:10]}

    # ⑥ 字号 / 行高
    u = c.get("c6", {})
    smp = u.get("samples") or []
    if u.get("fail"):
        parts = []
        if u.get("smallFontCount"):
            parts.append("font-size<13px %s 个" % u["smallFontCount"])
        if u.get("tightLineHeightCount"):
            parts.append("line-height/font-size<1.4 %s 个" % u["tightLineHeightCount"])
        res[6] = {"status": "FAIL", "detail": "；".join(parts),
                  "samples": ["%s fs=%s %s" % (s["sel"], s.get("fontSize"),
                                               ("lh=%s ratio=%s" % (s.get("lineHeight"), s.get("ratio"))) if s.get("ratio") else "«%s»" % s.get("text", "")[:20])
                              for s in smp]}
    else:
        res[6] = {"status": "PASS", "detail": "p/li/td 没有 font-size<13px，也没有行高比<1.4", "samples": []}

    # ⑦ 点击区
    t = c.get("c7", {})
    if not t.get("applicable"):
        res[7] = {"status": "NA", "detail": "点击区只在手机宽度（<=420px）判定，本宽度不适用", "samples": []}
    elif t.get("fail"):
        smp = t.get("samples") or []
        res[7] = {"status": "FAIL",
                  "detail": "%s 个 a/button 小于 40×40；首例 %s %sx%s" % (
                      t.get("count"), smp[0]["sel"], smp[0]["w"], smp[0]["h"]),
                  "samples": ["%s %sx%s «%s»" % (s["sel"], s["w"], s["h"], s["text"][:20]) for s in smp]}
    else:
        res[7] = {"status": "PASS", "detail": "所有 a/button 都 >= 40×40", "samples": []}

    # ⑧ 降级文案
    s8 = c.get("c8", {})
    if not s8.get("found"):
        res[8] = {"status": "NA", "detail": "本页没有「读不到 / 不补数 / 取数中」文案", "samples": []}
    elif s8.get("fail"):
        smp = s8.get("samples") or []
        res[8] = {"status": "FAIL",
                  "detail": "%s 处降级文案 nowrap 或横向溢出；首例 %s white-space=%s clientWidth=%s scrollWidth=%s" % (
                      len(smp), smp[0]["sel"], smp[0]["whiteSpace"],
                      smp[0].get("clientW"), smp[0].get("scrollW")),
                  "samples": ["%s white-space=%s clientWidth=%s scrollWidth=%s%s" % (
                      s["sel"], s["whiteSpace"], s.get("clientW"), s.get("scrollW"),
                      "（nowrap 不换行）" if s.get("nowrap") else "（文字横向超出，被挤/裁）" if s.get("overflow") else "") for s in smp]}
    else:
        res[8] = {"status": "PASS",
                  "detail": "%s 处降级文案均可换行（%s）" % (
                      s8.get("found"), ", ".join(sorted({a["whiteSpace"] for a in (s8.get("all") or [])}))),
                  "samples": []}

    # ⑨ 对比度
    s9 = c.get("c9", {})
    sk = (s9.get("skipped") or 0) + (s9.get("backdropSkipped") or 0)
    bits = []
    if s9.get("skipped"):
        bits.append("%s 个背景是图片" % s9.get("skipped"))
    if s9.get("backdropSkipped"):
        bits.append("%s 个文字直接压在整屏固定背景上（%s）" % (
            s9.get("backdropSkipped"), "、".join(s9.get("backdrop") or []) or "照片层"))
    sk_note = "（未评估：%s）" % "；".join(bits) if bits else ""
    if not s9.get("checked"):
        res[9] = {"status": "NA",
                  "detail": "没有背景可判定的叶子文字容器" + sk_note, "samples": []}
    elif s9.get("fail"):
        smp = s9.get("samples") or []
        res[9] = {"status": "FAIL",
                  "detail": "%s/%s 个文本节点对比度 < 3.0；首例 %s %s on %s = %s%s" % (
                      s9.get("count"), s9.get("checked"), smp[0]["sel"], smp[0]["fg"], smp[0]["bg"],
                      smp[0]["ratio"], sk_note),
                  "samples": ["%s %s/%s ratio=%s" % (s["sel"], s["fg"], s["bg"], s["ratio"]) for s in smp]}
    else:
        res[9] = {"status": "PASS",
                  "detail": "%s 个文本节点全部 >= 3.0%s" % (s9.get("checked"), sk_note), "samples": []}

    # 键统一成 str：JSON 里 int 键会被悄悄转成 str，md 表格按 str 取，
    # 两边不一致会让表格全变 NA（踩过一次）。
    return {str(k): v for k, v in res.items()}, raw.get("meta", {})


def measure(page, js, arg, attempts=3):
    """量化一次；页面偶尔还在导航（documentElement 为 null）时会炸，重试几次。"""
    last = None
    for i in range(attempts):
        try:
            return page.evaluate(js, arg)
        except Exception as e:
            last = e
            try:
                page.wait_for_timeout(300 * (i + 1))
            except Exception:
                pass
    raise last


ALIAS_RE = re.compile(r'http-equiv=["\']?refresh["\']?[^>]*?url=([^"\'\s>]+)', re.I)


def alias_target(html_text):
    """Hugo 的 alias 页：243 字节的 <meta http-equiv=refresh> 跳转壳，没有可审计的排版。
    不识别出来就会被当成真页面：浏览器跟跳后落到外站（或错误页），
    于是量到 908px 的「横向溢出」，其实是 Chromium 的错误提示页。
    """
    m = ALIAS_RE.search(html_text[:2000])
    return m.group(1) if m else None


def scan_aliases(pages, public_dir):
    out = {}
    for route, rel in pages:
        fp = os.path.join(public_dir, rel)
        try:
            with io.open(fp, encoding="utf-8", errors="replace") as fh:
                head = fh.read(2000)
        except Exception:
            continue
        tgt = alias_target(head)
        if tgt:
            out[route] = tgt
    return out


def audit_real(pages, base, widths, public_dir):
    from playwright.sync_api import sync_playwright

    aliases = scan_aliases(pages, public_dir)
    results = []
    t0 = time.time()
    with sync_playwright() as p:
        browser, label = launch_browser(p)
        log("浏览器：%s" % label)
        ctx = browser.new_context(viewport={"width": widths[0], "height": VIEWPORT_HEIGHT},
                                  device_scale_factor=1)
        page = ctx.new_page()
        total = len(pages) * len(widths)
        done = 0
        for idx, (route, rel) in enumerate(pages):
            url = url_for(base, route)
            entry = {"path": route, "file": rel, "url": url, "title": "", "status": "PASS", "widths": {}}
            if route in aliases:
                # 别名页：只记录跳转目标，9 项全部 NA，不占审计时长
                entry["status"] = "NA"
                entry["alias"] = aliases[route]
                for w in widths:
                    done += 1
                    entry["widths"][str(w)] = {"innerWidth": None, "checks": {
                        str(c["id"]): {"status": "NA",
                                       "detail": "别名页：<meta refresh> 跳转到 %s，没有独立排版" % aliases[route],
                                       "samples": []} for c in CHECKS}}
                    sys.stderr.write("\r  [%d/%d] %-40s %dpx 别名页   " % (done, total, route, w))
                    sys.stderr.flush()
                results.append(entry)
                log("跳过别名页 %s → %s" % (route, aliases[route]))
                continue
            for w in widths:
                done += 1
                page.set_viewport_size({"width": w, "height": VIEWPORT_HEIGHT})
                item = {"innerWidth": None, "checks": {}}
                err = None
                try:
                    page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
                    # 页面有轮询请求，networkidle 永远等不到（每页白吃 4s）；
                    # 布局在首屏 CSS/字体就位后即定型，固定短稳定期即可。
                    try:
                        page.wait_for_timeout(SETTLE_MS)
                    except Exception:
                        pass
                    try:
                        page.evaluate("() => Promise.race([document.fonts ? document.fonts.ready : 1, new Promise(function(r){setTimeout(r,800)})]).then(function(){return 1})")
                    except Exception:
                        pass
                    raw = measure(page, MEASURE_JS, {"mobile": min(widths)})
                    checks, meta = normalise_checks(raw, w)
                    # 有些页（如 /redteam/）首帧的降级文案还在被脚本替换，量到的
                    # 「文字超出容器」会在 200ms 后自己消失 —— 只有 FAIL 时才复核一次，
                    # 拿第二次结果覆盖，避免把瞬态当缺陷写进报告。
                    if any(cv["status"] == "FAIL" for cv in checks.values()):
                        try:
                            page.wait_for_timeout(REMEASURE_MS)
                            raw2 = measure(page, MEASURE_JS, {"mobile": min(widths)})
                            checks2, meta2 = normalise_checks(raw2, w)
                            checks, meta = checks2, meta2
                        except Exception:
                            pass
                    item["checks"] = checks
                    item["innerWidth"] = meta.get("innerWidth")
                    item["scrollWidth"] = meta.get("scrollWidth")
                    item["elementCount"] = meta.get("elementCount")
                    entry["title"] = entry["title"] or meta.get("title", "")
                    for cid, cv in checks.items():
                        if cv["status"] == "FAIL":
                            entry["status"] = "FAIL"
                except Exception as e:
                    err = str(e).split("\n")[0][:200]
                    item["error"] = err
                    for cid in [c["id"] for c in CHECKS]:
                        item["checks"][str(cid)] = {"status": "NA",
                                                    "detail": "渲染失败，未测：%s" % err,
                                                    "samples": []}
                    entry["status"] = "FAIL"
                entry["widths"][str(w)] = item
                sys.stderr.write("\r  [%d/%d] %-40s %dpx %s   " % (
                    done, total, route, w, item["checks"].get(1, {}).get("status", "?")))
                sys.stderr.flush()
            results.append(entry)
            log("完成 %s（累计 %.0fs）" % (route, time.time() - t0))
        ctx.close()
        browser.close()
    return results, {"mode": "real", "engine": label}


# --------------------------------------------------------------------------
# 静态退化模式（没有 playwright/浏览器时）
# --------------------------------------------------------------------------
def audit_static(pages, base, widths, public_dir):
    """只做能靠文本算出来的项；需要布局的一律 NA，并明确写「未做真实渲染」。"""
    css_text = []
    for pat in ("public/**/*.css", os.path.join(public_dir, "**", "*.css")):
        for f in globmod.glob(pat, recursive=True):
            try:
                with io.open(f, encoding="utf-8", errors="replace") as fh:
                    css_text.append(fh.read())
            except Exception:
                pass
    css = "\n".join(css_text)
    decl = {
        "radius": sorted(set(re.findall(r"border-radius\s*:\s*([^;}]+)", css))),
        "font_small": len(re.findall(r"font-size\s*:\s*(?:[0-9]|1[0-2])(?:\.\d+)?px", css)),
        "lh_small": len(re.findall(r"line-height\s*:\s*0?\.\d+|line-height\s*:\s*1(?:\.\d+)?(?!\d)", css)),
    }
    results = []
    for route, rel in pages:
        with io.open(os.path.join(public_dir, rel), encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        n_tables = len(re.findall(r"<table\b", html, re.I))
        has_dock = bool(re.search(r'class="[^"]*\bdock\b', html))
        has_idc = "xk-idcard" in html
        entry = {"path": route, "file": rel, "url": url_for(base, route), "title": "", "status": "PASS", "widths": {}}
        for w in widths:
            _na = "未做真实渲染（无 playwright / 浏览器）：需要 getBoundingClientRect/computed style"
            checks = {
                1: {"status": "NA", "detail": _na, "samples": []},
                2: {"status": "NA", "detail": _na + ("；本页存在 .dock=%s .xk-idcard=%s" % (has_dock, has_idc)), "samples": []},
                3: {"status": "NA", "detail": _na, "samples": []},
                4: {"status": "NA", "detail": "未做真实渲染；静态只数到 %s 个 <table>（祖先 overflow-x 需布局才能判）" % n_tables, "samples": []},
                5: {"status": "NA", "detail": "静态近似：全站 CSS 里 border-radius 出现 %s 种取值（无法确认哪张卡片命中哪条规则）" % len(decl["radius"]), "samples": decl["radius"][:8]},
                6: {"status": "NA", "detail": "静态近似：全站 CSS 里 font-size<13px 的声明 %s 条、行高<1.4 声明 %s 条（无元素级命中）" % (decl["font_small"], decl["lh_small"]), "samples": []},
                7: {"status": "NA", "detail": _na, "samples": []},
                8: {"status": "NA", "detail": _na, "samples": []},
                9: {"status": "NA", "detail": _na, "samples": []},
            }
            entry["widths"][str(w)] = {"innerWidth": None, "checks": checks}
        results.append(entry)
    return results, {"mode": "static", "engine": "static-only"}


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------
SEV_TIER = {"P0": "必须修", "P1": "建议修", "P2": "建议修"}


def collect_findings(results):
    rows = []
    for e in results:
        for w, item in e["widths"].items():
            for cid, cv in item["checks"].items():
                if cv["status"] != "FAIL":
                    continue
                c = CHECK_BY_ID[cid]
                rows.append({
                    "path": e["path"], "width": int(w), "check": cid, "name": c["name"],
                    "sev": c["sev"], "tier": cv.get("tier") or SEV_TIER[c["sev"]],
                    "detail": cv["detail"], "samples": cv.get("samples", [])[:4],
                })
    rows.sort(key=lambda r: ({"必须修": 0, "建议修": 1, "不用管": 2}.get(r["tier"], 3),
                             {"P0": 0, "P1": 1, "P2": 2}[r["sev"]], r["path"], r["width"], r["check"]))
    return rows


def build_summary(results, findings):
    total = {"PASS": 0, "FAIL": 0, "NA": 0}
    for e in results:
        for item in e["widths"].values():
            for cv in item["checks"].values():
                total[cv["status"]] = total.get(cv["status"], 0) + 1
    tiers = {"必须修": [], "建议修": [], "不用管": []}
    for f in findings:
        tiers.setdefault(f["tier"], []).append(f)
    rendered = sum(1 for e in results if any(
        cv["status"] != "NA" for item in e["widths"].values() for cv in item["checks"].values()))
    return {
        "checks_pass": total.get("PASS", 0),
        "checks_fail": total.get("FAIL", 0),
        "checks_na": total.get("NA", 0),
        "pages": len(results),
        "pages_fail": sum(1 for e in results if e["status"] == "FAIL"),
        "pages_with_data": rendered,
        "p0": [f for f in findings if f["sev"] == "P0" and f["tier"] == "必须修"],
        "p0_all": [f for f in findings if f["sev"] == "P0"],
        "p1": [f for f in findings if f["sev"] == "P1"],
        "p2": [f for f in findings if f["sev"] == "P2"],
        "must_fix": tiers.get("必须修", []),
        "suggest": tiers.get("建议修", []),
        "ignore": tiers.get("不用管", []),
    }


def md_table_cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def write_md(path, results, summary, meta, widths, base):
    L = []
    A = L.append
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    A("# 排版检查报告（%s）" % "20261018")
    A("")
    A("> 生成时间：%s　|　脚本：`scripts/layout-audit.py`" % now)
    A("> 渲染模式：**%s**（engine=`%s`）　|　基准地址：`%s`" % (
        "真实渲染（playwright + 浏览器内核）" if meta["mode"] == "real" else "⚠ 未做真实渲染（纯静态分析）",
        meta.get("engine", "?"), base))
    A("> 宽度：%s px　|　视口高度：%s px　|　页面：%s 个（%s 个页面在 3 个宽度下都有真实测量数据）" % (
        " / ".join(str(w) for w in widths), VIEWPORT_HEIGHT, summary["pages"], summary["pages_with_data"]))
    A("")
    if meta["mode"] != "real":
        A("## ⚠ 本报告未做真实渲染")
        A("")
        A("本机没有可用的 playwright/浏览器内核，脚本退化成了纯静态分析。")
        A("需要 `getBoundingClientRect()` 与 computed style 的检查（横向溢出、元素重叠、文字被裁、")
        A("表格窄屏、点击区、降级文案换行、对比度）**全部标为 NA，没有测过就是没测过**。")
        A("")
    A("判定口径：PASS = 该项在本页本宽度下无问题；FAIL = 命中判据；NA = 本页没有可测目标，或环境不支持该项。")
    A("报告只测量、不改样式；任何修复都应在确认数字之后单独进行。")
    A("")

    # ---- P0 ----
    A("## 一、P0 清单（必须修）")
    A("")
    if not summary["p0"]:
        A("**无。** %s 个页面 × %s 个宽度下，横向溢出 / 元素重叠 / 文字被裁 / 表格窄屏 四项都没有命中判据。" % (
            summary["pages"], len(widths)))
        A("")
        A("数字：总检查点 %s 个（PASS %s / FAIL %s / NA %s）。" % (
            summary["checks_pass"] + summary["checks_fail"] + summary["checks_na"],
            summary["checks_pass"], summary["checks_fail"], summary["checks_na"]))
        A("")
    else:
        A("共 %s 条（同一页同一宽度下的同类问题合并为一条）。" % len(summary["p0"]))
        A("")
        for i, f in enumerate(summary["p0"], 1):
            smp = ""
            if f["samples"]:
                smp = "　样例：" + "、".join("`%s`" % md_table_cell(s) for s in f["samples"][:3])
            A("%s. **%s** @ %spx · %s —— %s%s" % (i, f["path"], f["width"], f["name"], md_table_cell(f["detail"]), smp))
        A("")

    # 用户点名要的第三类数字：字号 < 13px 的页面与元素数（三宽度都要）
    small = []
    for e in results:
        for w in widths:
            cv = e["widths"].get(str(w), {}).get("checks", {}).get("6")
            if cv and cv["status"] == "FAIL":
                small.append((e["path"], w, cv))
    A("### 1.1 补充数字：字号 < 13px / 行高偏紧的页面（各宽度）")
    A("")
    if small:
        A("| 页面 | 宽度 | 命中情况 | 样例 |")
        A("|---|---|---|---|")
        for pg_path, pg_w, pg_cv in small[:24]:
            det = md_table_cell(pg_cv["detail"])[:140]
            smp = "、".join(str(s)[:70] for s in (pg_cv.get("samples") or [])[:2])
            A("| `%s` | %s | %s | %s |" % (pg_path, pg_w, det, md_table_cell(smp)))
        if len(small) > 24:
            A("")
            A("（只列前 24 行；共 %s 个「页面 × 宽度」点位命中，完整数据见 `docs/layout-audit.json` 的 `c6` 字段。）" % len(small))
        A("")
    else:
        A("无命中（或数据不足，见第四节）。")
        A("")

    # ---- 逐页 ----
    A("## 二、逐页明细")
    A("")
    A("每页一张表：9 项检查 × %s 个宽度的状态，最后一列是证据（数值或选择器）。" % len(widths))
    A("")
    for e in results:
        if e.get("alias"):
            page_status = "NA（别名页 → %s）" % e["alias"]
        else:
            page_status = "FAIL" if e["status"] == "FAIL" else "PASS"
        per = []
        for w in widths:
            item = e["widths"].get(str(w), {})
            nf = sum(1 for cv in item.get("checks", {}).values() if cv["status"] == "FAIL")
            nna = sum(1 for cv in item.get("checks", {}).values() if cv["status"] == "NA")
            nall = len(item.get("checks", {}))
            if nf:
                per.append("%s:FAIL×%s" % (w, nf))
            elif nall and nna == nall:
                per.append("%s:NA" % w)
            else:
                per.append("%s:PASS" % w)
        A("### `%s`　%s（%s）" % (e["path"], page_status, " / ".join(per)))
        A("")
        A("| # | 检查项 | %s | 证据（数值 / 选择器） |" % " | ".join(str(w) for w in widths))
        A("|---|--------|%s|------|" % "|".join(["----"] * len(widths)))
        for c in CHECKS:
            cid = c["id"]
            cells = []
            groups = []  # [([宽度...], detail)]：同一条证据在多个宽度下重复时折叠成一行
            for w in widths:
                cv = e["widths"].get(str(w), {}).get("checks", {}).get(str(cid))
                if cv is None:
                    cells.append("NA")
                    continue
                cells.append(cv["status"])
                if cv["status"] != "FAIL":
                    continue
                for g in groups:
                    if g[1] == cv["detail"]:
                        g[0].append(w)
                        break
                else:
                    groups.append([[w], cv["detail"]])
            if groups:
                ev = ["%spx %s" % ("/".join(str(x) for x in g[0]), g[1]) for g in groups]
            else:
                first = e["widths"].get(str(widths[0]), {}).get("checks", {}).get(str(cid), {})
                ev = ["%spx %s" % (widths[0], first.get("detail", ""))]
            A("| %s | %s | %s | %s |" % (cid, c["name"], " | ".join(cells), md_table_cell("；".join(ev)[:400])))
        A("")
        # 有 FAIL 的项补一条样例行，避免表格被挤爆
        fails = []
        for w in widths:
            for cid, cv in e["widths"].get(str(w), {}).get("checks", {}).items():
                if cv["status"] == "FAIL" and cv.get("samples"):
                    fails.append("`%s`@%spx %s：%s" % (e["path"], w, CHECK_BY_ID[int(cid)]["name"],
                                                       "、".join("`%s`" % str(s)[:70] for s in cv["samples"][:3])))
        if fails:
            A("样例：")
            for f in fails[:6]:
                A("- " + f)
            A("")

    # ---- 三档 ----
    A("## 三、结论（必须修 / 建议修 / 不用管）")
    A("")
    A("### 必须修（P0：横向溢出、元素重叠、文字被裁、表格窄屏）")
    A("")
    if summary["must_fix"]:
        for f in summary["must_fix"]:
            A("- `%s` @ %spx · %s —— %s" % (f["path"], f["width"], f["name"], md_table_cell(f["detail"])[:220]))
    else:
        A("- 无。四项 P0 检查在全部页面、全部宽度下都通过（或该页没有可测目标）。")
    A("")
    A("### 建议修（P1/P2：字号与行高、点击区、降级文案换行、对比度、卡片取值一致性；含「疑似刻意层叠」的重叠项）")
    A("")
    if summary["suggest"]:
        # 同类问题按检查项聚合，避免 90 页逐条铺开
        agg = {}
        for f in summary["suggest"]:
            k = (f["check"], f["name"], f["sev"])
            agg.setdefault(k, []).append(f)
        for (cid, name, sev), rows in sorted(agg.items()):
            pages = sorted({r["path"] for r in rows})
            dds = []
            for r in rows:
                d = md_table_cell(r["detail"])[:140]
                if d not in dds:
                    dds.append(d)
                if len(dds) >= 2:
                    break
            A("- **%s**（%s，%s 条命中，涉及 %s 页）：%s" % (
                name, sev, len(rows), len(pages), "；另外 ".join(dds)))
            A("  - 命中页：%s" % ("、".join("`%s`" % p for p in pages[:12]) + ("…等 %s 页" % len(pages) if len(pages) > 12 else "")))
    else:
        A("- 无。")
    A("")
    A("### 不用管")
    A("")
    A("- 卡片一致性里的「取值种类」是抽样统计：`border-radius` / `border` / `background` 各不相同不代表视觉不一致，")
    A("  只有同类取值超过 3 种才记 FAIL，这里没有命中。")
    A("- NA 项不算问题：没有 `<table>`、没有 `.mod`/`.xk-card`、没有降级文案、非手机宽度不做点击区判定，都属于「本页没有这个目标」。")
    A("- 点击区只在 %spx 判断（桌面宽度下 24×24 的小按钮不算问题）。" % min(widths))
    A("")

    # ---- 数据不足 ----
    errs = []
    for e in results:
        for w, item in e["widths"].items():
            if item.get("error"):
                errs.append("`%s` @ %spx：%s" % (e["path"], w, item["error"]))
    A("## 四、数据不足 / 已知限制")
    A("")
    if meta["mode"] != "real":
        A("- **未做真实渲染**：本机缺 playwright 或浏览器内核，所有需要布局的检查都是 NA，不是 PASS。")
    if errs:
        A("- 有 %s 个「页面×宽度」组合渲染失败（已标 NA，原因逐条列出）：" % len(errs))
        for x in errs[:20]:
            A("  - " + x)
    A("- 对比度取「叶子文字容器」（有直接文本、子元素全为行内）的文字色，与其背景按 `over` 合成后的颜色比较；"
      "半透明卡片会一层层叠到最底下的不透明层。本站页面底部是「整屏照片 + 暗色遮罩」（`div.xk-bg` 等固定层），"
      "这类遮罩不是文字的祖先：此时若文字这一路没有不透明填充，就分别按最暗底色和最亮底色各算一次，"
      "**两边都 < 3.0 才记 FAIL**，跨阈值的记「未评估」而不是判过或判错。背景是图片（`background-image`）时直接记未评估。")
    A("- 元素重叠只比对 `.dock`、`.xk-idcard`、首个 `.screen-hd`、首个 `.mod` 两两之间；正文内部互相压字不在本项范围内。")
    A("- 文字被裁只认 `overflow: hidden|clip` + `scrollWidth > clientWidth+2` + 直接文本节点；用 `text-overflow: ellipsis` 的省略号截断同样算命中（有意为之的省略号需要人工豁免）。")
    A("- 表格窄屏按「table 自身溢出 或 宽于视口」判定；用 transform 缩放出来的表格不会被识别为溢出。")
    A("- 所有数值来自无头浏览器（%s，视口 %spx 高，device_scale_factor=1）；真机字体渲染可能有 1–2px 差异。" % (
        meta.get("engine") or "?", VIEWPORT_HEIGHT))
    A("- 重叠判定里，两个 `position:fixed` 装饰层之间 ≤16px 的相交会标注「疑似刻意层叠」，"
      "不计入必须修（例如顶栏 `.dock` 与下挂头像卡 `.xk-idcard` 固定相差 10px）。")
    A("- 页面清单是 `public/**/index.html` 的 glob 结果（%s 页），不含 `404.html`、不含 RSS/JSON 等非 HTML 产物。" % len(results))
    al = [(e["path"], e["alias"]) for e in results if e.get("alias")]
    if al:
        A("- 其中 %s 个是 Hugo 别名页（`<meta http-equiv=refresh>` 跳转壳），没有独立排版，9 项全 NA、不参与判定：%s" % (
            len(al), "、".join("`%s` → %s" % (p, t) for p, t in al)))
    A("")
    A("## 五、复现")
    A("")
    A("```bash")
    A("cd public && python -m http.server 8126 --bind 127.0.0.1 &   # 或给脚本加 --serve")
    A("python -X utf8 scripts/layout-audit.py --widths 390,768,1280")
    A("```")
    A("")
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")


def write_json(path, payload):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if path == "-":
        sys.stdout.write(text + "\n")
    else:
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")


# --------------------------------------------------------------------------
# check-only：读已有 json 复核
# --------------------------------------------------------------------------
def check_only(json_path, strict=False):
    """只读已有 JSON 复核结论。
    默认只在「必须修（P0）」命中时返回 1——否则 38px 按钮、12px 字号这类 P1
    会让发布门禁永远红着，起不到提示作用；--strict 才把任意 FAIL 当失败。
    """
    p = json_path if json_path and json_path != "-" else DEFAULT_JSON
    if not os.path.isfile(p):
        log("check-only：找不到 %s" % p)
        return 2
    try:
        with io.open(p, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        log("check-only：%s 解析失败：%s" % (p, e))
        return 2
    if data.get("mode") != "real":
        log("check-only：%s 是静态模式产物（未做真实渲染），不据此判定" % p)
        return 2
    s = data.get("summary", {})
    fails = int(s.get("checks_fail", 0))
    p0 = s.get("p0") or []
    if p0:
        log("check-only：必须修 %s 条（P0）；总计 FAIL %s 项 / PASS %s 项 / NA %s 项" % (
            len(p0), fails, s.get("checks_pass"), s.get("checks_na")))
        return 1
    if strict and fails:
        log("check-only（--strict）：FAIL %s 项（P0 已清空，但仍有 P1/P2 命中）" % fails)
        return 1
    log("check-only：无必须修项（P1/P2 命中 %s 项，不算失败；NA %s 项）" % (fails, s.get("checks_na")))
    return 0


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def parse_args(argv):
    ap = argparse.ArgumentParser(
        description="排版审计：public/ 下每页在 390/768/1280 下做 9 项排版检查（只测量，不改样式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="退出码：0 全 PASS；1 有 FAIL；2 环境不满足（无真实渲染能力）")
    ap.add_argument("--widths", default=",".join(str(w) for w in DEFAULT_WIDTHS),
                    help="逗号分隔的宽度，默认 390,768,1280")
    ap.add_argument("--pages", nargs="*", default=None,
                    help="只审计这些路由（如 --pages /alerts/ /status/），默认全部 index.html")
    ap.add_argument("--json", default=DEFAULT_JSON, help="JSON 输出路径，'-' 表示 stdout（默认 %s）" % DEFAULT_JSON)
    ap.add_argument("--md", default=DEFAULT_MD, help="Markdown 报告路径（默认 %s）" % DEFAULT_MD)
    ap.add_argument("--strict", action="store_true",
                    help="严格模式：除 FAIL 外，任何 NA（测不到）也算失败")
    ap.add_argument("--check-only", action="store_true",
                    help="不重新测量，只复核已有 JSON 的结论（给 CI 用；默认只有 P0/必须修命中才返回 1）")
    ap.add_argument("--base-url", default=DEFAULT_BASE, help="站点基址，默认 %s" % DEFAULT_BASE)
    ap.add_argument("--public", default=os.path.join(REPO, "public"), help="产物目录，默认 <repo>/public")
    ap.add_argument("--serve", action="store_true", help="基址连不上时自己拉一个 http.server")
    ap.add_argument("--port", type=int, default=8126, help="--serve 时用的端口，默认 8126")
    ap.add_argument("--quiet", action="store_true", help="不打印每页进度")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.check_only:
        return check_only(args.json, args.strict)

    widths = [int(x) for x in re.split(r"[,\s]+", args.widths.strip()) if x.strip()]
    if not widths:
        log("--widths 不能为空")
        return 2
    public_dir = os.path.abspath(args.public)
    if not os.path.isdir(public_dir):
        log("找不到产物目录：%s" % public_dir)
        return 2

    pages = discover_pages(public_dir, args.pages)
    if not pages:
        log("没有匹配到任何 index.html（--pages 过滤过严？）")
        return 2
    log("发现 %s 个页面，宽度 %s" % (len(pages), widths))

    base = args.base_url.rstrip("/")
    server = None
    if not fetch_ok(base + "/"):
        if args.serve:
            port = args.port if port_free(args.port) else pick_port()
            log("基址连不上，自动起 http.server :%s（根目录 %s）" % (port, public_dir))
            server = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                cwd=public_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            base = "http://127.0.0.1:%s" % port
            for _ in range(40):
                if fetch_ok(base + "/"):
                    break
                time.sleep(0.25)
        if not fetch_ok(base + "/"):
            log("连不上 %s —— 先起站：cd public && python -m http.server 8126 --bind 127.0.0.1" % base)
            if server:
                server.terminate()
            return 2

    try:
        # LAYOUT_AUDIT_FORCE_STATIC=1 可以强制走静态退化路径（用来验证「没有浏览器时」的报告，别装假）
        if have_playwright() and os.environ.get("LAYOUT_AUDIT_FORCE_STATIC") != "1":
            try:
                results, meta = audit_real(pages, base, widths, public_dir)
            except Exception as e:
                log("真实渲染失败（%s），退化到静态分析" % str(e).split("\n")[0][:160])
                results, meta = audit_static(pages, base, widths, public_dir)
        else:
            log("没有 playwright —— 退化到纯静态分析（报告会写明未做真实渲染）")
            results, meta = audit_static(pages, base, widths, public_dir)
    finally:
        if server:
            server.terminate()

    findings = collect_findings(results)
    summary = build_summary(results, findings)

    payload = {
        "schema": "layout-audit/1",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "mode": meta["mode"],
        "engine": meta.get("engine"),
        "base_url": base,
        "widths": widths,
        "viewport_height": VIEWPORT_HEIGHT,
        "mobile_max_width": MOBILE_MAX,
        "checks": [{"id": c["id"], "name": c["name"], "severity": c["sev"], "rule": c["rule"]} for c in CHECKS],
        "page_count": len(results),
        "pages": results,
        "summary": summary,
    }

    md_path = args.md if args.md != "-" else None
    # JSON 先落盘：报告模板出 bug 时，至少测量结果不会白跑（曾经白跑 8 分钟）
    if args.json == "-":
        write_json("-", payload)
    else:
        d = os.path.dirname(os.path.abspath(args.json))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        write_json(args.json, payload)
        log("JSON：%s" % os.path.abspath(args.json))
    if md_path:
        d = os.path.dirname(os.path.abspath(md_path))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        try:
            write_md(md_path, results, summary, meta, widths, base)
            log("Markdown：%s" % os.path.abspath(md_path))
        except Exception as e:  # 报告模板出错不能掩盖测量结果
            log("Markdown 生成失败（JSON 已保存）：%s: %s" % (type(e).__name__, e))
            raise

    log("结果：PASS %s / FAIL %s / NA %s（页面 %s，其中 %s 页有 FAIL）" % (
        summary["checks_pass"], summary["checks_fail"], summary["checks_na"],
        summary["pages"], summary["pages_fail"]))

    if meta["mode"] != "real":
        return 2
    if summary["checks_fail"] > 0:
        return 1
    if args.strict and summary["checks_na"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
