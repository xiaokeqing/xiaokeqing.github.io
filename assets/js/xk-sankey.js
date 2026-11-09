/* ★2026-11-09 告警链路桑基图（/alerts/ › 数据统计 tab）
   ----------------------------------------------------------------------------
   为什么不用 ECharts：全站图表都是零依赖（CSS/Canvas/SVG 手写）。为一张卡引 1 MB
   库，既违反这条约定，又要在慢网下单独做一套「手动加载」分支。这里改成手写 SVG：
   约 4 KB、无第三方、无需懒加载、无网络请求。

   数据口径（红线）：
   · 只吃 window.XK_FEED —— xk-bind 从 /api/public/alerts 取到的「5 分钟窗口原始聚合清单」
     （每行：来源 sourceLabel × 类型 typeLabel × 严重度 severityLabel × 条数 count），
     真实联合分布，不是拼凑。
   · 24h 聚合（stats24h）是分维度独立统计，**拼不成链路**，所以本图只有 5 分钟版。
   · XK_FEED === null ⇒ 照抄 window.XK_FEED_NOTE 的原因；=== [] ⇒ 「真实的 0」。
   钩子：xk-bind.js 的 bindFeed() 尾部调 window.__xkSankeyFeed（有就调）。 */
(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  ready(function () {
    var card = document.querySelector('[data-xk-sankey]');
    var host = document.getElementById('xkSankey');
    if (!card || !host) return;
    var note = card.querySelector('[data-xk-sankey-note]');
    var NS = 'http://www.w3.org/2000/svg';

    function say(t) {
      if (note) note.textContent = t;
      host.setAttribute('aria-label', '告警链路桑基图：' + t);
    }
    function fmt(n) { return Number(n).toLocaleString('zh-CN'); }

    var SEV_COLOR = {
      '严重': '#E8837B', '高危': '#E8B45A', '中危': '#B0A0E8', '低危': '#6FD3A0', '信息': '#8A9DA8'
    };
    var TEAL = '#7FD4D8';

    /* ---- 聚合：来源 → 类型 → 严重度（权重 = 该组真实条数） -------------------- */
    function build(feed) {
      var idx = {}, mid = {}, total = 0;
      function put(layer, name, n) {
        var k = layer + '|' + name;
        if (!idx[k]) idx[k] = { layer: layer, name: name, value: 0 };
        idx[k].value += n;
      }
      var links = [];
      var pairIdx = {};
      function link(a, b, n) {
        var k = a + '>' + b;
        if (!pairIdx[k]) { pairIdx[k] = { source: a, target: b, value: 0 }; links.push(pairIdx[k]); }
        pairIdx[k].value += n;
      }
      feed.forEach(function (it) {
        var d = (it && it.d) || {};
        var s = String(d.src2 || '未标注来源');
        var t = String(d.typ || '未标注类型');
        var v = String(d.sev || '未标注严重度');
        var n = Number(d.n) || 1;
        total += n;
        put(0, s, n); put(1, t, n); put(2, v, n);
        link(s, t, n); link(t, v, n);
      });
      var layers = [[], [], []];
      Object.keys(idx).forEach(function (k) { layers[idx[k].layer].push(idx[k]); });
      layers.forEach(function (arr) { arr.sort(function (a, b) { return b.value - a.value; }); });
      return { layers: layers, links: links, total: total, groups: feed.length };
    }

    /* ---- 排版：三列节点，按该列数值比例分高度，节点之间留缝 -------------------- */
    function layout(model, W, H) {
      var padTop = 14, padBottom = 20, gap = 10;
      /* 标签宽度按本列最长名字算（中文按 11px≈11.5px 估），避免左侧「Wazuh 主机告警」被裁 */
      var maxLen = function (arr) {
        return arr.reduce(function (a, b) { return Math.max(a, String(b.name).length); }, 0);
      };
      var labelL = Math.min(148, Math.max(72, Math.round(maxLen(model.layers[0]) * 11.5) + 20));
      var labelR = Math.min(140, Math.max(78, Math.round(maxLen(model.layers[2]) * 11.5) + 30));
      var nodeW = 12;
      var x = [labelL, Math.round(W / 2) - 6, W - labelR];
      var usable = H - padTop - padBottom;
      model.layers.forEach(function (arr, layer) {
        var sum = arr.reduce(function (a, b) { return a + b.value; }, 0) || 1;
        var gaps = Math.max(0, arr.length - 1) * gap;
        var h = usable - gaps;
        var y = padTop;
        arr.forEach(function (nd) {
          var hh = Math.max(6, h * (nd.value / sum));
          nd.x = x[layer]; nd.y = y; nd.h = hh; nd.w = nodeW;
          y += hh + gap;
        });
      });
      /* 每条链路在源/目标节点内的偏移，避免叠在同一处 */
      var outOff = {}, inOff = {};
      model.links.forEach(function (lk) {
        var s = findNode(model, lk.source), t = findNode(model, lk.target);
        if (!s || !t) return;
        var so = outOff[lk.source] || 0, ti = inOff[lk.target] || 0;
        var sTh = Math.max(1.5, s.h * (lk.value / (s.value || 1)));
        var tTh = Math.max(1.5, t.h * (lk.value / (t.value || 1)));
        lk.x1 = s.x + s.w; lk.y1 = s.y + so + sTh / 2;
        lk.x2 = t.x;       lk.y2 = t.y + ti + tTh / 2;
        lk.w = Math.max(1.2, tTh);
        lk.color = SEV_COLOR[String(lk.target)] || TEAL;
        outOff[lk.source] = so + sTh;
        inOff[lk.target] = ti + tTh;
      });
    }

    function findNode(model, name) {
      for (var l = 0; l < 3; l++) {
        for (var i = 0; i < model.layers[l].length; i++) {
          if (model.layers[l][i].name === name) return model.layers[l][i];
        }
      }
      return null;
    }

    function el(name, attrs, text) {
      var e = document.createElementNS(NS, name);
      for (var k in attrs) if (attrs.hasOwnProperty(k)) e.setAttribute(k, attrs[k]);
      if (text != null) e.textContent = text;
      return e;
    }

    function draw(model) {
      var W = host.clientWidth || 900;
      var H = host.clientHeight || 300;
      layout(model, W, H);
      host.textContent = '';
      var svg = el('svg', { width: '100%', height: '100%', viewBox: '0 0 ' + W + ' ' + H, role: 'presentation' });
      /* 彩带（先画，压在节点下面） */
      model.links.forEach(function (lk) {
        if (lk.x1 == null) return;
        var mx = (lk.x1 + lk.x2) / 2;
        var d = 'M' + lk.x1 + ',' + lk.y1 + 'C' + mx + ',' + lk.y1 + ' ' + mx + ',' + lk.y2 + ' ' + lk.x2 + ',' + lk.y2;
        var g = el('g', {});
        var p = el('path', {
          d: d, fill: 'none', stroke: lk.color, 'stroke-opacity': '0.26',
          'stroke-width': Math.max(1.2, Math.min(26, lk.w)), 'stroke-linecap': 'round'
        });
        var ttl = el('title', {}, lk.source + ' → ' + lk.target + '：' + fmt(lk.value) + ' 条');
        p.appendChild(ttl);
        g.appendChild(p);
        svg.appendChild(g);
      });
      /* 节点 + 标签 */
      model.layers.forEach(function (arr, layer) {
        arr.forEach(function (nd) {
          svg.appendChild(el('rect', {
            x: nd.x, y: nd.y, width: nd.w, height: nd.h, rx: 2,
            fill: SEV_COLOR[nd.name] || TEAL, 'fill-opacity': '0.92'
          }));
          var isR = layer === 2, isM = layer === 1;
          var tx = isR ? nd.x + nd.w + 8 : (isM ? nd.x + nd.w + 8 : nd.x - 8);
          var anchor = isR || isM ? 'start' : 'end';
          var ty = nd.y + Math.min(nd.h, 16) / 2 + 3;
          var label = nd.name + (nd.h > 30 ? ' · ' + fmt(nd.value) : '');
          svg.appendChild(el('text', {
            x: tx, y: ty, 'text-anchor': anchor, 'font-size': '11',
            fill: '#C9D8DE', style: 'paint-order:stroke;stroke:#0B0F11;stroke-width:2.5px;stroke-linejoin:round'
          }, label.length > 22 ? label.slice(0, 21) + '…' : label));
        });
      });
      host.appendChild(svg);
    }

    function render() {
      var feed = window.XK_FEED;
      if (feed === undefined || feed === null) {
        say(window.XK_FEED_NOTE || '未取到（/api/public/alerts）—— 不画样例链路');
        return;
      }
      if (!feed.length) { say('本窗口 0 条告警，链路图为空（真实的 0，不是没取到）'); return; }
      var model = build(feed);
      draw(model);
      say('近 5 分钟窗口 ' + fmt(model.total) + ' 条告警（服务端聚合为 ' + model.groups +
          ' 组）；线宽 = 该条链路的真实条数，悬停看具体数值');
    }

    /* 数据经 __xkSankeyFeed 钩子推送（xk-bind 每次取到 /alerts 后调用） */
    window.__xkSankeyFeed = function () { render(); };

    /* 卡片在隐藏的 tab 里时 clientWidth=0，切回来要重画 */
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (es) {
        for (var i = 0; i < es.length; i++) {
          if (es[i].isIntersecting) { render(); break; }
        }
      }, { rootMargin: '80px' });
      io.observe(host);
    }
    window.addEventListener('resize', function () { if (Array.isArray(window.XK_FEED) && window.XK_FEED.length) render(); });
    render();
  });
})();
