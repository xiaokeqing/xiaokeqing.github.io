/* V1 攻击地理热力：零依赖、零外部请求。
   数据：/api/public/geo.js（同源快照）里的国家计次 → 质心经纬度 → 等距圆柱投影打气泡。
   底图不引海岸线（40KB 换不来信息量），用经纬网 + 国家名 + 气泡大小/颜色表达强弱。

   下钻（A5）：快照 byCountry[] 只有 country/countryName/count/uniqueIps/sharePercent/byProvince，
   **没有 topIp / ip / ipList 字段**（docs/攻击地图-可行性评估.md：只给聚合，响应里不含任何 IP），
   所以"点气泡跳 /ip/ 时间线"没有数据支撑；/ip/ 页也只认 ?q=，不认 ?country=。
   于是：点气泡（或下方国家按钮）⇒ 高亮 + 地图下方展开明细面板：
     · 次数 / 占比 / 独立 IP（byCountry 真数据）
     · 省/州分布（byProvince 真数据）
     · 再尝试从同源 alerts 快照按 srcGeo 过滤聚合 Top IP；有就列成 /ip/?q= 链接，
       没有（或 srcGeo 为空）就给一行解释 + /ip/ 入口。绝不出现"点了没反应"。
*/
(function () {
  'use strict';
  var doc = document;

  function ready(fn) {
    if (doc.readyState !== 'loading') fn();
    else doc.addEventListener('DOMContentLoaded', fn, { once: true });
  }
  ready(init);

  // 国家/地区质心（够用即止）：key = ISO2 或 geo.js 里的中文名
  var C = {
    'NL': [5.3, 52.1], '荷兰': [5.3, 52.1], 'AD': [1.5, 42.5], 'FR': [2.2, 46.2], '法国': [2.2, 46.2],
    'DE': [10.4, 51.2], '德国': [10.4, 51.2], 'US': [-98, 39], '美国': [-98, 39], 'CN': [104, 35], '中国': [104, 35],
    'SG': [103.8, 1.35], '新加坡': [103.8, 1.35], 'GB': [-1.5, 52.5], '英国': [-1.5, 52.5], 'RU': [96, 61], '俄罗斯': [96, 61],
    'BR': [-51, -10], '巴西': [-51, -10], 'IN': [78, 22], '印度': [78, 22], 'JP': [138, 36], '日本': [138, 36],
    'KR': [127.8, 36], '韩国': [127.8, 36], 'VN': [106, 16], '越南': [106, 16], 'TH': [101, 15], '泰国': [101, 15],
    'ID': [113, -1], '印尼': [113, -1], 'TR': [35, 39], '土耳其': [35, 39], 'UA': [31, 49], '乌克兰': [31, 49],
    'PL': [19, 52], '波兰': [19, 52], 'IT': [12.5, 42.8], '意大利': [12.5, 42.8], 'ES': [-4, 40], '西班牙': [-4, 40],
    'SE': [15, 62], '瑞典': [15, 62], 'CH': [8.2, 46.8], '瑞士': [8.2, 46.8], 'CA': [-106, 56], '加拿大': [-106, 56],
    'AU': [134, -25], '澳大利亚': [134, -25], 'ZA': [24, -29], '南非': [24, -29], 'AR': [-64, -34], '阿根廷': [-64, -34],
    'MX': [-102, 23], '墨西哥': [-102, 23], 'EG': [30, 26], '埃及': [30, 26], 'AE': [54, 24], '阿联酋': [54, 24],
    'HK': [114.1, 22.3], '香港': [114.1, 22.3], 'TW': [121, 23.7], '台湾': [121, 23.7]
  };

  function proj(lon, lat, w, h) {
    // 等距圆柱：经度 -180..180 → 0..w；纬度 83..-60（砍掉两极空白）→ 0..h
    return [((lon + 180) / 360) * w, ((83 - lat) / 143) * h];
  }

  function num(v) { var n = Number(v); return isFinite(n) ? n : 0; }
  function fmtN(n) { return num(n).toLocaleString('en-US'); }
  function fmtPct(v) {
    if (v === null || v === undefined || v === '' || !isFinite(Number(v))) return '';
    return String(Number(v).toFixed(2)).replace(/\.?0+$/, '') + '%';
  }
  function mk(tag, text, css) {
    var e = doc.createElement(tag);
    if (text != null) e.textContent = text;
    if (css) e.style.cssText = css;
    return e;
  }

  function init() {
    var ssr = doc.querySelector('[data-xk-ssr="monitor"]');
    if (!ssr) return;
    var box = doc.getElementById('xkGeoMap');
    if (!box) return;
    var tip = doc.getElementById('xkGeoTip');
    var note = doc.getElementById('xkGeoNote');

    // ---- 下钻面板：插在 note 前面（note 仍是最底下的总述） ----
    var panel = doc.getElementById('xkGeoDetail');
    if (!panel) {
      panel = doc.createElement('div');
      panel.id = 'xkGeoDetail';
      panel.className = 'xk-geo-detail';
      panel.setAttribute('role', 'region');
      panel.setAttribute('aria-live', 'polite');
      panel.setAttribute('aria-label', '国家来源明细');
      panel.style.cssText = 'margin:8px 0 0;padding:8px 10px;border:1px solid rgba(127,212,216,.28);'
        + 'border-radius:10px;background:rgba(127,212,216,.07);font-size:12px;line-height:1.75;'
        + 'color:var(--txt,#EDEAE4)';
      panel.hidden = true;
      if (note && note.parentNode) note.parentNode.insertBefore(panel, note);
      else (box.parentNode || box).appendChild(panel);
    }

    var state = { items: [], groups: {}, sel: -1, alerts: null, alertsDone: false, alerted: null };

    // ---- 高亮 ----
    function highlight(idx) {
      state.sel = idx;
      Object.keys(state.groups).forEach(function (k) {
        var g = state.groups[k];
        if (!g) return;
        var on = Number(k) === idx;
        var dim = idx >= 0 && !on;
        var c = g.querySelector('circle');
        var t = g.querySelector('text');
        if (c) {
          c.setAttribute('stroke-width', on ? '2.6' : '1');
          c.setAttribute('stroke', on ? 'rgba(255,255,255,.95)' : 'rgba(127,212,216,.85)');
          c.style.opacity = dim ? '0.42' : '1';
        }
        if (t) t.style.opacity = dim ? '0.42' : '1';
      });
    }

    // ---- 该国 IP 明细：alerts 快照只有 srcGeo 能给国家（当前快照里它全为 null） ----
    function loadAlerts() {
      if (state.alerted) return state.alerted;
      state.alerted = fetch('/api/public/alerts.js', { cache: 'force-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (o) {
          var d = (o && o.data) || o || {};
          state.alerts = Array.isArray(d.list) ? d.list : [];
        })
        .catch(function () { state.alerts = []; })
        .then(function () { state.alertsDone = true; return state.alerts; });
      return state.alerted;
    }

    function geoKey(it) {
      var g = it && it.srcGeo;
      if (!g) return '';
      if (typeof g === 'string') return g;
      return g.country || g.code || g.iso2 || g.countryCode || g.countryName || g.name || '';
    }

    function collectIps(item) {
      var want = [item.code, item.name].filter(Boolean).map(function (s) { return String(s).toUpperCase(); });
      var out = {}, anyGeo = false;
      (state.alerts || []).forEach(function (it) {
        var k = geoKey(it);
        if (k) anyGeo = true;
        if (!k || want.indexOf(String(k).toUpperCase()) < 0) return;
        var ip = it.srcIp || '';
        if (!ip) return;
        var o = out[ip] || (out[ip] = { ip: ip, hits: 0, last: '', rule: '' });
        o.hits += num(it.count) || 1;
        var t = it.occurredAt || it.endTime || it.startTime || '';
        if (t && (!o.last || t > o.last)) o.last = t;
        if (!o.rule) o.rule = it.ruleName || it.title || it.typeLabel || '';
      });
      var arr = Object.keys(out).map(function (k) { return out[k]; });
      arr.sort(function (a, b) { return b.hits - a.hits; });
      return { anyGeo: anyGeo, arr: arr };
    }

    function renderIps(item) {
      var wrap = mk('div');
      wrap.style.cssText = 'margin-top:6px;padding-top:6px;border-top:1px dashed rgba(127,212,216,.22)';
      function line(t) { return wrap.appendChild(mk('div', t)); }
      panel.appendChild(wrap);   /* 先挂上再分支：三条路径（取数中 / Top IP / 解释行）都必须真的进 DOM */

      if (!state.alertsDone) {
        wrap.appendChild(mk('div', '正在取 /api/public/alerts.js 的 IP 明细…'));
        loadAlerts().then(function () {
          if (state.sel < 0 || state.items[state.sel] !== item) return;
          wrap.parentNode && wrap.parentNode.removeChild(wrap);
          renderIps(item);
        });
        return;
      }

      var got = collectIps(item);
      if (got.arr.length) {
        wrap.appendChild(mk('div', 'Top 来源 IP（最近一批告警，按命中次数）', 'color:var(--mut,#9AA7B0)'));
        got.arr.slice(0, 8).forEach(function (o) {
          var row = mk('div', null, 'display:flex;flex-wrap:wrap;gap:8px;align-items:baseline');
          var a = doc.createElement('a');
          a.href = '/ip/?q=' + encodeURIComponent(o.ip);
          a.textContent = o.ip;
          a.style.cssText = 'color:var(--acc,#39D0D8);text-decoration:none;border-bottom:1px dotted currentColor';
          row.appendChild(a);
          row.appendChild(mk('span', fmtN(o.hits) + ' 次' + (o.rule ? ' · ' + o.rule : ''), 'color:var(--mut,#9AA7B0)'));
          wrap.appendChild(row);
        });
        var more = mk('div', null, 'margin-top:4px');
        var link = doc.createElement('a');
        link.href = '/ip/';
        link.textContent = '输入任意 IP 查时间线 →';
        link.style.cssText = 'color:var(--acc,#39D0D8);text-decoration:none';
        more.appendChild(link);
        wrap.appendChild(more);
        return;
      }

      // 没数据也必须说清楚为什么 —— 这是"点了没反应"的反面。
      line(got.anyGeo
        ? '最近一批告警里没有归到这个国家/地区的 IP（srcGeo 未命中），因此这里没有 IP 列表。'
        : 'geo 快照只给国家/地区聚合（byCountry 里没有 topIp/ipList，响应体不含任何 IP），'
          + 'alerts 快照的 srcGeo 目前也是空 —— 两者都拿不到"国家 → IP"，所以这里列不出该国 IP。');
      var tail = mk('div', null, 'margin-top:4px;color:var(--mut,#9AA7B0)');
      tail.appendChild(doc.createTextNode('要查具体 IP 的攻击时间线：'));
      var a2 = doc.createElement('a');
      a2.href = '/ip/';
      a2.textContent = '去 /ip/ 输入已知 IP →';
      a2.style.cssText = 'color:var(--acc,#39D0D8);text-decoration:none';
      tail.appendChild(a2);
      tail.appendChild(doc.createTextNode('（上方「点个 IP」卡片也可直接点已知 IP）'));
      wrap.appendChild(tail);
    }

    function renderDetail(idx) {
      var item = state.items[idx];
      if (!item) return;
      highlight(idx);

      while (panel.firstChild) panel.removeChild(panel.firstChild);
      panel.hidden = false;

      var hd = mk('div', null, 'display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;font-weight:600');
      hd.appendChild(mk('span', item.name + (item.code && item.code !== item.name ? ' · ' + item.code : '')));
      panel.appendChild(hd);

      var bits = [fmtN(item.n) + ' 次'];
      var pct = fmtPct(item.share);
      if (pct) bits.push('占比 ' + pct);
      if (item.uniqueIps != null) bits.push(fmtN(item.uniqueIps) + ' 个独立 IP');
      panel.appendChild(mk('div', bits.join(' · '), 'color:var(--mut,#9AA7B0)'));

      if (item.byProvince && item.byProvince.length) {
        var pw = mk('div', null, 'margin-top:6px');
        pw.appendChild(mk('div', '省/州分布（Top ' + Math.min(6, item.byProvince.length) + '）', 'color:var(--mut,#9AA7B0)'));
        item.byProvince.slice(0, 6).forEach(function (p) {
          pw.appendChild(mk('div', (p.province || '未知') + ' · ' + fmtN(p.count) + ' 次'
            + (p.uniqueIps != null ? ' · ' + fmtN(p.uniqueIps) + ' 个 IP' : '')));
        });
        panel.appendChild(pw);
      }

      renderIps(item);
    }

    // ---- 地图 ----
    function draw(items) {
      var w = box.clientWidth || 900, h = Math.max(240, Math.round(w * 0.42));
      var H = '';
      H += '<svg viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="' + h + '" role="img" aria-label="攻击来源地理分布">';
      H += '<rect width="' + w + '" height="' + h + '" fill="rgba(8,12,15,.55)"/>';
      for (var lon = -180; lon <= 180; lon += 30) {
        var x = proj(lon, 0, w, h)[0];
        H += '<line x1="' + x + '" y1="0" x2="' + x + '" y2="' + h + '" stroke="rgba(127,212,216,.10)" stroke-width="1"/>';
      }
      for (var lat = -60; lat <= 80; lat += 20) {
        var y = proj(0, lat, w, h)[1];
        H += '<line x1="0" y1="' + y + '" x2="' + w + '" y2="' + y + '" stroke="rgba(127,212,216,.10)" stroke-width="1"/>';
      }
      H += '<line x1="0" y1="' + proj(0, 0, w, h)[1] + '" x2="' + w + '" y2="' + proj(0, 0, w, h)[1]
        + '" stroke="rgba(127,212,216,.25)" stroke-width="1" stroke-dasharray="4 4"/>';

      var max = 1;
      items.forEach(function (it) { if (it.n > max) max = it.n; });
      var placed = [];
      items.forEach(function (it, i) {
        var c = C[it.code] || C[it.name];
        if (!c) return;
        var p = proj(c[0], c[1], w, h);
        var r = 4 + 20 * Math.sqrt(it.n / max);
        var op = 0.28 + 0.5 * Math.sqrt(it.n / max);
        var label = it.name + ' · ' + fmtN(it.n);
        H += '<g class="xk-geo-g" data-i="' + i + '" data-name="' + it.name + '" tabindex="0" role="button" '
          + 'aria-label="' + label + '，点击查看明细">'
          + '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="' + r + '" fill="rgba(127,212,216,' + op.toFixed(2) + ')" '
          + 'stroke="rgba(127,212,216,.85)" stroke-width="1"/>'
          + '<text x="' + (p[0] + r + 4) + '" y="' + (p[1] + 4) + '" fill="rgba(232,240,242,.9)" font-size="11">'
          /* 气泡旁只写国家名（窄栏里带数字会互相压字）；次数/占比进 hover 提示与下方按钮 */
          + it.name + '</text></g>';
        placed.push(i);
      });
      H += '</svg>';
      box.innerHTML = H;
      state.groups = {};
      placed.forEach(function (i) {
        var g = box.querySelector('.xk-geo-g[data-i="' + i + '"]');
        if (g) state.groups[i] = g;
      });

      // 无质心坐标的国家：给按钮兜底（否则那部分国家永远点不到）
      var offs = items.map(function (it, i) { return i; }).filter(function (i) {
        var it = items[i];
        return !(C[it.code] || C[it.name]);
      });

      // 国家按钮条：保证每个国家都有可点的入口
      var chips = doc.getElementById('xkGeoBtns');
      if (!chips) {
        chips = doc.createElement('div');
        chips.id = 'xkGeoBtns';
        chips.className = 'xk-geo-btns';
        chips.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 0';
        box.parentNode.insertBefore(chips, panel);
      }
      while (chips.firstChild) chips.removeChild(chips.firstChild);
      items.forEach(function (it, i) {
        var b = doc.createElement('button');
        b.type = 'button';
        b.textContent = it.name + ' · ' + fmtN(it.n);
        b.style.cssText = 'cursor:pointer;font:inherit;font-size:11px;padding:2px 8px;border-radius:999px;'
          + 'border:1px solid rgba(127,212,216,.35);background:rgba(127,212,216,.08);color:inherit';
        b.addEventListener('click', function () { renderDetail(i); });
        chips.appendChild(b);
      });

      // 气泡交互
      box.querySelectorAll('.xk-geo-g').forEach(function (g) {
        var idx = Number(g.getAttribute('data-i'));
        var it = items[idx];
        if (!it) return;
        g.style.cursor = 'pointer';
        var show = function (ev) {
          if (!tip) return;
          var s = it.name + ' · ' + fmtN(it.n) + ' 次';
          var pct = fmtPct(it.share);
          if (pct) s += ' · ' + pct;
          if (it.ip) s += ' · ' + it.ip;
          tip.textContent = s;
          tip.hidden = false;
          if (ev && ev.clientX) {
            tip.style.left = ev.clientX + 12 + 'px';
            tip.style.top = ev.clientY + 12 + 'px';
          }
        };
        g.addEventListener('mouseenter', show);
        g.addEventListener('mousemove', show);
        g.addEventListener('mouseleave', function () { if (tip) tip.hidden = true; });
        g.addEventListener('focus', function () {
          var r = g.getBoundingClientRect();
          show({ clientX: r.left, clientY: r.top });
        });
        g.addEventListener('blur', function () { if (tip) tip.hidden = true; });
        g.addEventListener('click', function (ev) {
          ev && ev.preventDefault && ev.preventDefault();
          // 有 topIp 才优先跳时间线；快照没有该字段，就走下方明细面板。
          if (it.ip && /^\d+\.\d+\.\d+\.\d+$/.test(it.ip)) {
            location.href = '/ip/?q=' + encodeURIComponent(it.ip);
            return;
          }
          renderDetail(idx);
        });
        g.addEventListener('keydown', function (ev) {
          if (ev.key === 'Enter' || ev.key === ' ' || ev.key === 'Spacebar') {
            ev.preventDefault();
            renderDetail(idx);
          }
        });
      });

      if (offs.length && note) {
        // 不覆盖总述，追加一行（下钻面板里仍可看到这些国家的明细）
        note.textContent += '（另有 ' + offs.length + ' 个来源国家/地区没有质心坐标，未落图：'
          + offs.map(function (i) { return items[i].name; }).join('、') + '；点下方按钮可看明细）';
      }
    }

    fetch('/api/public/geo.js', { cache: 'force-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (o) {
        var d = (o && o.data) ? o.data : (o || {});
        var list = d.byCountry || d.countries || d.list || d.top || [];
        if (!Array.isArray(list)) list = [];
        var items = list.map(function (it) {
          return {
            name: it.countryName || it.name || it.country || it.code || '未知',
            code: String(it.country || it.code || it.iso2 || '').toUpperCase(),
            n: num(it.count || it.n || it.hits),
            share: it.sharePercent,
            uniqueIps: it.uniqueIps,
            byProvince: Array.isArray(it.byProvince) ? it.byProvince : [],
            ip: it.topIp || it.ip || ''
          };
        }).filter(function (x) { return x.n > 0; });
        items.sort(function (a, b) { return b.n - a.n; });
        state.items = items;
        if (!items.length) {
          if (note) note.textContent = '没有可用的来源国家数据（geo 快照 byCountry 为空）· 这里不编数据';
          return;
        }
        var all = items.slice(0, 24);
        state.items = all;
        draw(all);
        var cov = d.coverage || {};
        var head = '共 ' + items.length + ' 个来源国家/地区';
        if (cov.geocoded != null) head += '（窗口 ' + (d.window || '24h') + ' 内可定位 ' + fmtN(cov.geocoded) + ' 条告警）';
        if (note) note.textContent = head + '，显示前 ' + all.length + ' 个；点气泡或下方按钮看该国明细（次数 · 占比 · 独立 IP · 省/州分布 · Top IP）。';
      })
      .catch(function (e) {
        if (note) note.textContent = '地理数据未取到（' + (e && e.message ? e.message : '网络错误') + '）· 这里不编数据';
      });
  }
})();
