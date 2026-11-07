/* V1 攻击地理热力：零依赖、零外部请求。
   数据：/api/public/geo.js（同源快照）里的国家计次 → 质心经纬度 → 等距圆柱投影打气泡。
   底图不引海岸线（40KB 换不来信息量），用经纬网 + 国家名 + 气泡大小/颜色表达强弱。 */
(function () {
  var host = document.querySelector('[data-xk-ssr="monitor"]');
  if (!host) return;
  var box = document.getElementById('xkGeoMap');
  if (!box) return;

  // 国家/地区质心（够用即止）：key = geo.js 里出现的国家名或 ISO2
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

  function draw(items) {
    var w = box.clientWidth || 900, h = Math.max(240, Math.round(w * 0.42));
    var H = '';
    H += '<svg viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="' + h + '" role="img" aria-label="攻击来源地理分布">';
    H += '<rect width="' + w + '" height="' + h + '" fill="rgba(8,12,15,.55)"/>';
    // 经纬网
    for (var lon = -180; lon <= 180; lon += 30) {
      var x = proj(lon, 0, w, h)[0];
      H += '<line x1="' + x + '" y1="0" x2="' + x + '" y2="' + h + '" stroke="rgba(127,212,216,.10)" stroke-width="1"/>';
    }
    for (var lat = -60; lat <= 80; lat += 20) {
      var y = proj(0, lat, w, h)[1];
      H += '<line x1="0" y1="' + y + '" x2="' + w + '" y2="' + y + '" stroke="rgba(127,212,216,.10)" stroke-width="1"/>';
    }
    H += '<line x1="0" y1="' + proj(0, 0, w, h)[1] + '" x2="' + w + '" y2="' + proj(0, 0, w, h)[1] + '" stroke="rgba(127,212,216,.25)" stroke-width="1" stroke-dasharray="4 4"/>';

    var max = 1;
    items.forEach(function (it) { if (it.n > max) max = it.n; });
    items.forEach(function (it) {
      var c = C[it.code] || C[it.name];
      if (!c) return;
      var p = proj(c[0], c[1], w, h);
      var r = 4 + 20 * Math.sqrt(it.n / max);
      var op = 0.28 + 0.5 * Math.sqrt(it.n / max);
      H += '<g class="xk-geo-g" data-ip="' + (it.ip || '') + '" data-name="' + it.name + '">'
        + '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="' + r + '" fill="rgba(127,212,216,' + op.toFixed(2) + ')" '
        + 'stroke="rgba(127,212,216,.85)" stroke-width="1"/>'
        + '<text x="' + (p[0] + r + 4) + '" y="' + (p[1] + 4) + '" fill="rgba(232,240,242,.9)" font-size="11">'
        + it.name + ' · ' + it.n + '</text></g>';
    });
    H += '</svg>';
    box.innerHTML = H;

    var tip = document.getElementById('xkGeoTip');
    box.querySelectorAll('.xk-geo-g').forEach(function (g) {
      g.style.cursor = 'pointer';
      g.addEventListener('mouseenter', function () {
        if (!tip) return;
        tip.textContent = g.getAttribute('data-name') + (g.getAttribute('data-ip') ? ' · ' + g.getAttribute('data-ip') : '');
        tip.hidden = false;
      });
      g.addEventListener('mouseleave', function () { if (tip) tip.hidden = true; });
      g.addEventListener('click', function () {
        var ip = g.getAttribute('data-ip');
        if (ip && /^\d+\.\d+\.\d+\.\d+$/.test(ip)) location.href = '/ip/?q=' + encodeURIComponent(ip);
      });
    });
  }

  var note = document.getElementById('xkGeoNote');
  fetch('/api/public/geo.js', { cache: 'force-cache' })
    .then(function (r) { return r.json(); })
    .then(function (o) {
      var d = (o && o.data) ? o.data : o;
      var list = (d && (d.countries || d.list || d.top)) || [];
      if (!Array.isArray(list)) list = [];
      var items = list.map(function (it) {
        return {
          name: it.name || it.country || it.code || '未知',
          code: (it.code || it.iso2 || '').toUpperCase(),
          n: Number(it.count || it.n || it.hits || 0),
          ip: it.topIp || it.ip || ''
        };
      }).filter(function (x) { return x.n > 0; });
      items.sort(function (a, b) { return b.n - a.n; });
      if (!items.length) {
        if (note) note.textContent = '没有可用的来源国家数据（geo 快照里 countries 为空）';
        return;
      }
      draw(items.slice(0, 24));
      if (note) note.textContent = '共 ' + items.length + ' 个来源国家/地区，显示前 ' + Math.min(24, items.length) + ' 个；点击气泡看该 IP 的时间线。';
    })
    .catch(function (e) {
      if (note) note.textContent = '地理数据未取到（' + (e && e.message ? e.message : '网络错误') + '）· 这里不编数据';
    });
})();
