/* XK-LAB 攻击图谱：用 /api/public/stories 的真实故事画「攻击者 → 传感器四阶段」粒子流。
 * 其余卡片（矩阵 / 数字 / 柱子 / TOP 来源 / 故事线）已由 api-bind.html 用 .js 快照绑定，
 * 这里【不碰】，避免两套口径互相覆盖。 */
(function () {
  'use strict';
  var meta = document.querySelector('meta[name="wb-api"]');
  var API = ((meta && meta.content) || '').replace(/\/+$/, '');
  var STAGES = [
    ['alerts', '告警'],
    ['decoyPorts', '诱饵端口'],
    ['honeypotLogins', '蜜罐登录'],
    ['auditActions', '处置审计']
  ];

  function num(v) { return (typeof v === 'number' && isFinite(v)) ? v : 0; }

  function load() {
    var url = API + '/api/public/stories?limit=8';
    return fetch(url, { cache: 'no-store', credentials: 'omit' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (o) { return (o && o.data) ? o.data : o; })
      .catch(function () { return null; });
  }

  function mount(stories) {
    var old = document.getElementById('atkGraph');
    if (!old || old.dataset.real === '1') return;

    var attackers = (stories || []).map(function (s) {
      var st = s.stages || {}, tot = 0;
      STAGES.forEach(function (k) { tot += num(st[k[0]]); });
      return { ip: s.srcIp || '未知', sev: s.severityMaxLabel || '', stages: st, total: tot };
    }).filter(function (a) { return a.total > 0; })
      .sort(function (a, b) { return b.total - a.total; })
      .slice(0, 7);

    var c = document.createElement('canvas');
    c.id = 'atkGraph'; c.dataset.real = '1';
    if (old.style.height) c.style.height = old.style.height;
    old.parentNode.replaceChild(c, old);

    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var W = 0, H = 340;
    var x = c.getContext('2d');
    function resize() {
      W = c.clientWidth || c.parentNode.clientWidth || 480;
      H = c.clientHeight || 340;
      c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
      x.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener('resize', resize);

    var A = attackers.map(function (a, i) {
      return { a: a, fx: 0.13, fy: (i + 1) / (attackers.length + 1) };
    });
    var S = STAGES.map(function (s, i) {
      var tot = 0;
      A.forEach(function (n) { tot += num(n.a.stages[s[0]]); });
      return { id: s[0], label: s[1], total: tot, fx: 0.82, fy: (i + 1) / (STAGES.length + 1) };
    });
    function pose(n) { return { x: n.fx * W, y: 26 + n.fy * (H - 58) }; }

    var parts = [], lastEmit = 0, t0 = performance.now();
    function frame(t) {
      requestAnimationFrame(frame);
      var pane = document.querySelector('.ops-tab[data-pane="graph"]');
      if (!W || (pane && pane.offsetParent === null)) return;
      x.clearRect(0, 0, W, H);
      x.font = '11px ui-monospace,Consolas,monospace';

      S.forEach(function (s) {
        var p = pose(s);
        x.textAlign = 'left';
        x.fillStyle = 'rgba(150,205,210,.55)';
        x.fillText(s.label, p.x + 14, p.y - 8);
        x.fillStyle = 'rgba(210,203,189,.32)';
        x.fillText(String(s.total), p.x + 14, p.y + 8);
      });

      if (A.length && t - lastEmit > 240) {
        lastEmit = t;
        var ai = Math.floor(Math.random() * A.length);
        var best = -1, bk = 0;
        S.forEach(function (s, k) { if (s.total > best) { best = s.total; bk = k; } });
        var sk = Math.random() < 0.6 ? bk : Math.floor(Math.random() * S.length);
        parts.push({ a: ai, s: sk, k: 0, sp: 0.008 + Math.random() * 0.010 });
        if (parts.length > 48) parts.shift();
      }

      parts = parts.filter(function (p) {
        p.k += p.sp;
        var pa = pose(A[p.a]), ps = pose(S[p.s]);
        for (var j = 0; j < 5; j++) {
          var q = p.k - j * 0.022;
          if (q < 0) break;
          x.fillStyle = 'rgba(232,180,90,' + (0.9 - j * 0.17).toFixed(3) + ')';
          x.beginPath();
          x.arc(pa.x + (ps.x - pa.x) * q, pa.y + (ps.y - pa.y) * q, 2.6 - j * 0.35, 0, 7);
          x.fill();
        }
        return p.k < 1;
      });

      A.forEach(function (n) {
        var p = pose(n);
        var r = 4 + Math.min(6, Math.log10(n.a.total + 1) * 3.2);
        x.fillStyle = /严重|高/.test(n.a.sev) ? '#E8837B' : 'rgba(232,131,123,.82)';
        x.beginPath(); x.arc(p.x, p.y, r, 0, 7); x.fill();
        x.textAlign = 'left';
        x.fillStyle = 'rgba(210,203,189,.88)';
        x.fillText(n.a.ip, p.x + 11, p.y - 1);
        x.fillStyle = 'rgba(210,203,189,.4)';
        x.fillText(n.a.total + ' 次', p.x + 11, p.y + 11);
      });

      var el = (t - t0) / 1000;
      S.forEach(function (s, i) {
        var p = pose(s);
        x.fillStyle = 'rgba(127,212,216,.16)';
        x.beginPath(); x.arc(p.x, p.y, 11 + Math.sin(el * 2 + i * 0.9) * 2.2, 0, 7); x.fill();
        x.fillStyle = '#7FD4D8';
        x.beginPath(); x.arc(p.x, p.y, 3.4, 0, 7); x.fill();
      });

      if (!A.length) {
        x.textAlign = 'center';
        x.fillStyle = 'rgba(210,203,189,.55)';
        x.fillText('未取到攻击故事（/api/public/stories）', W / 2, H / 2);
      }
    }
    requestAnimationFrame(frame);
  }

  function boot() {
    if (!API) return;
    load().then(mount);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
