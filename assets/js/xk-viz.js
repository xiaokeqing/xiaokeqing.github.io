/* V2 热力 + V3 环形：纯 CSS，零依赖，只吃页面已有响应 */
(function () {
  var SEV = [['CRITICAL', '严重', '--bad'], ['HIGH', '高危', '--warn'],
             ['MEDIUM', '中危', '--xk-sev-medium'], ['LOW', '低危', '--acc']];
  var pad = function (n) { return (n < 10 ? '0' : '') + n; };
  var fmt = function (n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); };

  function heat(done, trend) {
    var el = document.querySelector('[data-vz-heat]'), nt = document.querySelector('[data-vz-heatnote]');
    if (!el) return;
    var slot = [], has = [], ord = [], i, v, max = 0, pk = 0, seen = 0, html = '', txt;
    for (i = 0; i < 24; i++) { slot[i] = 0; has[i] = 0; }
    if (trend && trend.length) for (i = 0; i < trend.length; i++) {
      var t = trend[i] || {}, h = parseInt(t.time, 10), c = Number(t.count);
      if (!(h >= 0 && h < 24) || !isFinite(c) || c < 0) continue;
      slot[h] += c; has[h] = 1;
    }
    for (i = 0; i < 24; i++) if (has[i]) {
      seen++; ord.push(slot[i]);
      if (slot[i] > max) { max = slot[i]; pk = i; }
    }
    ord.sort(function (a, b) { return a - b; });
    for (i = 0; i < 24; i++) {
      v = has[i] ? slot[i] : null;
      html += '<b class="vz-c ' + (v === null ? 'nd' : 'l' + (1 + Math.min(4, Math.floor(ord.indexOf(v) / seen * 5)))) +
        '" title="' + pad(i) + ':00 · ' + (v === null ? '无数据' : fmt(v) + ' 条') + '">' +
        (v === null ? '—' : pad(i)) + '</b>';
    }
    el.innerHTML = html;
    if (!seen && !done) return;
    txt = seen ? '峰值 ' + pad(pk) + ':00 · ' + fmt(max) + ' 条 · ' + seen + '/24 有数' : '无按小时数据：24 格均为 —';
    el.setAttribute('aria-label', '24h 热力：' + txt);
    if (nt) nt.textContent = txt;
  }

  function ring(done, sev, total) {
    var el = document.querySelector('[data-vz-ring]'), nt = document.querySelector('[data-vz-ringnote]');
    if (!el) return;
    var i, v, raw, vals = [], sum = 0, known = 0, acc = 0, stops = [], rows = '', aria = '', pct;
    for (i = 0; i < 4; i++) {
      raw = sev ? sev[SEV[i][0]] : null;
      v = (raw === null || raw === undefined || raw === '' || !isFinite(Number(raw))) ? null : Number(raw);
      vals.push(v);
      if (v !== null) { sum += v; known++; }
    }
    var n0 = Number(total);
    var tot = (total === null || total === undefined || total === '' || !isFinite(n0)) ? sum : n0;
    for (i = 0; i < 4; i++) {
      v = vals[i];
      pct = (sum > 0 && v !== null) ? (v / sum * 100).toFixed(1) + '%' : '';
      if (v > 0) {
        var a = acc / sum * 360; acc += v;
        stops.push('var(' + SEV[i][2] + ') ' + a.toFixed(2) + 'deg ' + (acc / sum * 360).toFixed(2) + 'deg');
      }
      rows += '<span class="vz-l"><i style="background:var(' + SEV[i][2] + ')"></i><span>' + SEV[i][1] +
        '</span><b>' + (v === null ? '无' : fmt(v)) + '</b><em>' + pct + '</em></span>';
      aria += SEV[i][1] + (v === null ? '无数据' : ' ' + fmt(v) + ' 条' + (pct ? '，' + pct : '')) + '；';
    }
    el.innerHTML = '<div class="vz-rw"><div class="vz-r" role="img" aria-label="24h 严重度分布：' + aria +
      '合计 ' + (known ? fmt(tot) : '—') + ' 条"><i class="vz-d" style="--g:conic-gradient(' +
      (stops.length ? stops.join(',') : 'var(--line) 0deg 360deg') + ')"></i><span class="vz-m"><b>' +
      (known ? fmt(tot) : '—') + '</b><em>24h 总数</em></span></div><div class="vz-ls">' + rows + '</div></div>';
    if ((known || done) && nt) nt.textContent = known
      ? '合计 ' + fmt(sum) + ' 条 · INFO 不计入'
      : '读不到分级数据：环不画';
  }

  var drew = 0;
  window.__xkViz = function (opt) {
    opt = opt || {}; drew++;
    heat(true, 'trend' in opt ? opt.trend : window.XK24H);
    ring(true, 'sev' in opt ? opt.sev : window.XK_SEV24, 'total' in opt ? opt.total : window.XK_TOT24);
  };
  /* 首帧：数据没到 → 24 个 — 灰格 + 空环，绝不先写 0 */
  heat(false, null); ring(false, null, null);

  setTimeout(function () {
    if (drew || window.XK24H || window.XK_SEV24) return;
    var tip = '本页不请求实时分级数据，<a href="/alerts/">去作战室</a>看 24h 热力与分级';
    var h = document.querySelector('[data-vz-heatnote]'), r = document.querySelector('[data-vz-ringnote]');
    if (h) h.innerHTML = tip;
    if (r) r.innerHTML = tip;
  }, 6000);
})();