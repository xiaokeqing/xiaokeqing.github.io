/* XK-LAB 大屏 —— 数据装配 + 动效 + 助手播报
 * 数据全部来自同源静态快照 /api/public/*.js（构建期抓取，Vercel CDN），
 * 5s 轮询用 ?t= 绕缓存；有 SSE 时以推流为主，断线自动退回轮询。
 * 不编数：取不到的字段写「未取到 / NO DATA」，不补 0。
 */
(function () {
  var d = document, q = function (s) { return d.querySelector(s); };
  var qa = function (s) { return Array.prototype.slice.call(d.querySelectorAll(s)); };
  var nf = new Intl.NumberFormat('en-US');
  var fmt = function (n) { return n == null || isNaN(n) ? '—' : nf.format(Math.round(n)); };
  var pct = function (n, t) { return t > 0 ? (n / t * 100).toFixed(1) + '%' : '—'; };

  /* ---------- 数字补间 ---------- */
  function anim(el, to) {
    if (!el) return;
    var from = Number(el.getAttribute('data-v') || 0);
    if (from === to) { el.textContent = fmt(to); return; }
    var t0 = performance.now(), D = 700;
    (function step() {
      var k = Math.min(1, (performance.now() - t0) / D), e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(from + (to - from) * e);
      if (k < 1) requestAnimationFrame(step);
      else { el.setAttribute('data-v', to); el.textContent = fmt(to); }
    })();
  }
  function setNum(id, v) { var el = d.getElementById(id); if (el) anim(el, Number(v) || 0); }
  function setTxt(id, v) { var el = d.getElementById(id); if (el) el.textContent = v; }

  /* ---------- 取数 ---------- */
  function J(path) {
    return fetch(path + (path.indexOf('?') < 0 ? '?' : '&') + 't=' + Date.now(), { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  var ST = { alerts: null, geo: null, audit: null, atk: null, home: null, daily: null, deploy: null, stories: null, pwd: null, web: null };

  /* ---------- 条形组 ---------- */
  function bars(host, list, colorFn, unit) {
    if (!host) return;
    var max = Math.max.apply(null, list.map(function (x) { return x.n; }).concat([1]));
    host.innerHTML = list.map(function (x) {
      var w = Math.max(2, Math.round(x.n / max * 100));
      var c = colorFn ? colorFn(x) : 'rgba(111,211,216,.55)';
      return '<div class="br"><span class="bl">' + x.k + '</span>' +
        '<span class="bt"><i style="width:0" data-w="' + w + '%" data-c="' + c + '"></i></span>' +
        '<span class="bv">' + fmt(x.n) + (unit || '') + '</span></div>';
    }).join('');
    requestAnimationFrame(function () {
      
      Array.prototype.forEach.call(host.querySelectorAll('i[data-w]'), function (el, i) {
        setTimeout(function () { el.style.width = el.getAttribute('data-w'); el.style.background = el.getAttribute('data-c'); }, 40 * i);
      });
    });
  }

  /* ---------- 助手台词 ---------- */
  var L = {
    line: d.getElementById('hudLine'), st: d.getElementById('hudSt'), stTag: d.getElementById('hudStTag')
  };
  var facts = [], hintHold = false, rot = 0;
  function speak(txt, tag) {
    if (!L.line) return;
    L.line.textContent = txt;
    if (L.st) L.st.textContent = 'SPEAKING';
    if (L.stTag) L.stTag.textContent = tag || '数据播报';
    clearTimeout(speak._t);
    speak._t = setTimeout(function () { if (L.st) L.st.textContent = 'STANDBY'; if (L.stTag) L.stTag.textContent = '等待事件'; }, 7000);
  }
  function buildHints() {
    var h = [];
    function add(sel, txt) { var el = q(sel); if (el) { el.setAttribute('data-hint', txt); h.push(txt); } }
    add('#hudBand', '过去 24 小时的 8 个关键数：总量、四档严重度、真封 IP、可定位 IP、来源国家数。5 秒刷新一次。');
    add('#hudSev', '严重度构成：按 CRITICAL/HIGH/MEDIUM/LOW 四档，占比按本窗口总量算。');
    add('#hudType', '攻击类型 Top5：服务端给的 typeLabel，前 5 个。');
    add('#hudSrc', '三源占比：Wazuh 主机 / Suricata 网络 / 蜜罐 / 内置样本。');
    add('#hudCty', '来源国家 Top7：按来源 IP 的国家质心聚合，24h 窗口。');
    add('#hudSys', '体系与质量：自研规则、ATT&CK 覆盖、样本、蜜罐、归档。端口 Top5 后端没有字段，写 NO DATA。');
    add('#hudMap', '攻击来自哪里：点是国家质心，点大小是告警量，弧线是从该国到本站。');
    add('#hudLog', '正在发生：最近 5 分钟告警流，按时间倒序，左侧色条是严重度。');
    add('#hudChat', '牧濑红莉栖：用真实数据播报结论；鼠标移到任意块，她解释那块数从哪来。');
    add('#hudSpk', '24 小时攻击量：25 个整点桶，峰值会标出。');
    add('#hudHour', '近 24 小时分布：按整点聚合，看一天里哪个小时最凶。');
    add('#hudS2', '第二屏：攻击者档案、弱口令、访问热力、会话、降噪漏斗、规则、CVE。');
    return h;
  }
  var hints = [];
  d.addEventListener('mouseover', function (e) {
    var el = e.target.closest && e.target.closest('[data-hint]');
    if (el) { hintHold = true; speak(el.getAttribute('data-hint'), '口径解释'); }
  });
  d.addEventListener('mouseout', function (e) {
    if (e.target.closest && e.target.closest('[data-hint]')) hintHold = false;
  });
  setInterval(function () {
    if (hintHold) return;
    var pool = facts.length ? facts : hints;
    if (pool.length) speak(pool[rot++ % pool.length], '定时播报');
  }, 25000);

  /* ---------- 渲染 ---------- */
  /* 规则标题 → 攻击类型。后端 stats.byType 只有 OTHER/BRUTE_FORCE/SQL_INJECTION/SCAN 四类，
     OTHER 会吃掉一多半；这里按标题关键词再分一层，分不出来的明确写「未归类」。 */
  function kType(t) {
    var s = String(t || '');
    /* 顺序要紧：一条标题常常同时含「蜜罐」和「SSH」，要先判更具体的那个 */
    if (/登录成功|login success|logged in/i.test(s)) return '蜜罐登录成功';
    if (/\bMSSQL\b|MySQL|数据库探测|database port/i.test(s)) return '数据库探测';
    if (/SQL\s*注入|sqli|SQL_INJECTION|SQL Injection/i.test(s)) return 'SQL 注入';
    if (/SSH[\s\S]*?(爆破|暴力|brute)|brute|暴力破解/i.test(s)) return 'SSH 爆破';
    if (/sweep|端口扫描|port sweep|scan/i.test(s)) return '端口扫描';
    if (/\.env|\.git|web\.config|路径穿越|probe|HTTP\b/i.test(s)) return 'Web 探测';
    if (/蜜罐|honeypot|decoy/i.test(s)) return '蜜罐诱捕';
    if (/DNS|TLS|flow|Suricata/i.test(s)) return '网络流量';
    return '未归类';
  }
  function renderTop() {
    var a = ST.alerts && ST.alerts.data; if (!a) return;
    var s = a.stats24h || {}, sv = s.bySeverity || {};
    var total = s.total || 0;
    setNum('hudTotal', total);
    setNum('hudCrit', sv.CRITICAL); setNum('hudHigh', sv.HIGH); setNum('hudMed', sv.MEDIUM); setNum('hudLow', sv.LOW);
    setTxt('hudCritP', pct(sv.CRITICAL || 0, total)); setTxt('hudHighP', pct(sv.HIGH || 0, total));
    setTxt('hudMedP', pct(sv.MEDIUM || 0, total)); setTxt('hudLowP', pct(sv.LOW || 0, total));
    if (ST.daily && ST.daily.days && ST.daily.days.length > 1) {
      var prev = ST.daily.days[1].alertTotal;
      if (prev > 0) {
        var dd = (total - prev) / prev * 100;
        setTxt('hudDelta', (dd >= 0 ? '▲ +' : '▼ ') + dd.toFixed(1) + '% 较上一份日报');
      }
    }
    if (s.trend && s.trend.length) {
      var pts = s.trend.map(function (x) { return x.count || 0; });
      drawSpark(pts);
      var last8 = s.trend.slice(-8);
      bars(q('#hudHourList'), last8.map(function (x) { return { k: x.time, n: x.count }; }), null, '');
    }
    if (a.stats) {
      /* ★2026-11-10 站主：其他 142 条占满，为什么不能分出来。「后端只给 4 个 type」所以这里
         按「规则标题」再细分一层：用 list[] 的 count 汇总，未命中的归「未归类」并如实显示，
         不做二次摊派。分类规则写死在 kType() 里，改了要同步改文案。 */
      var seeds = (a.list || []).map(function (x) { return { k: kType(x.title || x.rule || ''), n: x.count || 1 }; });
      var agg = {}, tot2 = 0;
      seeds.forEach(function (x) { agg[x.k] = (agg[x.k] || 0) + x.n; tot2 += x.n; });
      var rows = Object.keys(agg).map(function (k) { return { k: k, n: agg[k] }; })
        .sort(function (p, q) { return q.n - p.n; }).slice(0, 8);
      if (rows.length >= 3) {
        var sum2 = rows.reduce(function (s, x) { return s + x.n; }, 0);
        if (tot2 > sum2) rows.push({ k: '未归类', n: tot2 - sum2 });
        bars(q('#hudTypeList'), rows, function () { return 'rgba(240,178,96,.6)'; }, '');
      } else {
        bars(q('#hudTypeList'), (a.stats.byType || []).slice(0, 5).map(function (x) { return { k: x.label || x.key, n: x.count }; }), function () { return 'rgba(240,178,96,.6)'; }, '');
      }
      bars(q('#hudSrcList'), (a.stats.bySource || []).slice(0, 4).map(function (x) { return { k: x.label || x.key, n: x.count }; }), null, '');
    }
    renderSevBars(sv);
    renderLog(a.list || []);
  }
  function renderSevBars(sv) {
    var host = q('#hudSevList'); if (!host) return;
    var arr = [['严重', sv.CRITICAL || 0, 'rgba(255,120,120,.62)'], ['高危', sv.HIGH || 0, 'rgba(240,178,96,.6)'],
      ['中危', sv.MEDIUM || 0, 'rgba(111,211,216,.55)'], ['低危', sv.LOW || 0, 'rgba(150,170,180,.45)']];
    bars(host, arr.map(function (x) { return { k: x[0], n: x[1], c: x[2] }; }), function (x) { return x.c; }, '');
  }
  function renderLog(list) {
    var host = q('#hudLogList'); if (!host) return;
    if (!list.length) { if (!host.children.length) host.innerHTML = '<div class="lg na">未取到</div>'; return; }
    var first = list[0], key = (first.aggId || '') + (first.occurredAt || '');
    /* 首屏必须填：只有「本次 key 与上次不同」或「还没写过」才整段重画 */
    if (!host.getAttribute('data-key') || key !== host.getAttribute('data-key')) {
      host.innerHTML = list.slice(0, 15).map(function (x) { return row(x, false); }).join('');
    }
    host.setAttribute('data-key', key);
  }
  function row(x, isNew) {
    var col = x.severity === 'CRITICAL' ? '#ff7878' : x.severity === 'HIGH' ? '#f0b260' : 'rgba(111,211,216,.85)';
    var t = (x.occurredAt || '').slice(11, 19);
    return '<div class="rw lg' + (isNew ? ' new' : '') + '"><b class="t">' + t + '</b><i style="background:' + col + '"></i>' +
      '<b class="ip">' + (x.srcIp || '') + '</b><span>' + (x.typeLabel || '') + (x.sourceLabel ? ' · ' + x.sourceLabel : '') + '</span></div>';
  }

  function renderGeo() {
    var g = ST.geo && ST.geo.data; if (!g) return;
    var list = (g.byCountry || []).slice(0, 7);
    bars(q('#hudCtyList'), list.map(function (x) { return { k: x.countryName || x.country, n: x.count }; }), null, '');
    setNum('hudIps', g.coverage && g.coverage.withSourceIp);
    setNum('hudCountries', g.countryCount != null ? g.countryCount : (g.byCountry || []).length);
    drawDots(list);
  }

  /* ---------- 地图：质心点 + 本站 + 脉冲 ---------- */
  var CEN = {
    NL: [5.3, 52.1], AD: [1.6, 42.5], FR: [2.2, 46.6], DE: [10.4, 51.2], US: [-98, 39], CN: [104, 35],
    IN: [78, 21], IR: [53, 32], RU: [100, 60], GB: [-1.5, 52.5], UA: [31, 49], RO: [25, 46], RS: [21, 44],
    VN: [106, 16], KR: [128, 36], JP: [138, 36], SG: [104, 1], TH: [101, 15], ID: [113, -1], BR: [-51, -10],
    CA: [-106, 56], AU: [134, -25], ZA: [24, -29], TR: [35, 39], PL: [19, 52], SE: [16, 62], FI: [26, 64],
    NO: [9, 61], LT: [24, 55], LV: [25, 57], EE: [26, 59], MD: [29, 47], BG: [25, 43], HU: [19, 47], AT: [14, 47],
    CH: [8, 47], IT: [12, 42], ES: [-4, 40], PT: [-8, 39], BE: [4.5, 50.5], DK: [10, 56], IE: [-8, 53],
    MX: [-102, 23], AR: [-64, -34], CL: [-71, -33], PE: [-75, -10], CO: [-74, 4], EG: [30, 27], NG: [8, 9],
    KE: [38, 0], SA: [45, 24], AE: [54, 24], IL: [35, 31], PK: [69, 30], BD: [90, 24], MY: [102, 4], PH: [122, 12],
    TW: [121, 24], HK: [114, 22], NZ: [174, -41], KZ: [67, 48], BY: [28, 53], GR: [22, 39], HR: [16, 45]
  };
  function proj(lon, lat) { return [(lon + 180) / 360 * 1000, (90 - lat) / 180 * 500]; }
  function drawDots(list) {
    var svg = q('#hudMap'); if (!svg) return;
    var layer = svg.querySelector('#hudDots');
    if (!layer) { layer = d.createElementNS('http://www.w3.org/2000/svg', 'g'); layer.setAttribute('id', 'hudDots'); svg.appendChild(layer); }
    var max = Math.max.apply(null, list.map(function (x) { return x.count || 0; }).concat([1]));
    var seen = [], out = '';
    list.forEach(function (x) {
      var cc = String(x.country || '').toUpperCase(), c = CEN[cc]; if (!c) return;
      var p = proj(c[0], c[1]);
      var cx = Math.max(40, Math.min(960, p[0])), cy = Math.max(12, Math.min(492, p[1]));
      var r = (3.5 + 12 * Math.sqrt((x.count || 0) / max)).toFixed(1);
      var label = seen.some(function (s) { return Math.abs(s[0] - cx) < 90 && Math.abs(s[1] - cy) < 22; }) ? '' :
        '<text x="' + cx + '" y="' + (cy - 11) + '" fill="rgba(220,236,241,.92)" font-size="12.5" text-anchor="middle">' +
        (x.countryName || cc) + ' ' + fmt(x.count) + '</text>';
      if (label) seen.push([cx, cy]);
      out += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="rgba(111,211,216,.16)" stroke="rgba(111,211,216,.5)"/>' +
        '<circle cx="' + cx + '" cy="' + cy + '" r="1.8" fill="rgba(160,240,255,.9)"/>' + label;
    });
    var s = proj(121.5, 31.2);
    out += '<circle cx="' + s[0] + '" cy="' + s[1] + '" r="3.2" fill="none" stroke="rgba(240,178,96,.9)" stroke-width="1.3"/>' +
      '<circle cx="' + s[0] + '" cy="' + s[1] + '" r="1.6" fill="rgba(240,178,96,.95)"/>' +
      '<text x="' + (s[0] + 7) + '" y="' + (s[1] + 4) + '" fill="rgba(240,178,96,.9)" font-size="10">本站</text>';
    layer.innerHTML = out;
  }
  window.__hudPulse = function (cc, sev) {
    var svg = q('#hudMap'); if (!svg) return false;
    var c = CEN[String(cc || '').toUpperCase()]; if (!c) return false;
    var p = proj(c[0], c[1]);
    var col = sev === 'CRITICAL' ? '255,120,120' : '111,211,216';
    var layer = svg.querySelector('#hudDots') || svg;
    var g = d.createElementNS('http://www.w3.org/2000/svg', 'g');
    var ring = d.createElementNS('http://www.w3.org/2000/svg', 'circle');
    ring.setAttribute('cx', p[0]); ring.setAttribute('cy', p[1]); ring.setAttribute('r', 3);
    ring.setAttribute('fill', 'none'); ring.setAttribute('stroke', 'rgb(' + col + ')'); ring.setAttribute('stroke-width', '1.3');
    g.appendChild(ring); layer.appendChild(g);
    var t0 = 0;
    requestAnimationFrame(function step(ts) {
      if (!t0) t0 = ts;
      var k = Math.min(1, (ts - t0) / 1100);
      ring.setAttribute('r', (3 + 22 * k).toFixed(1));
      ring.setAttribute('opacity', (0.85 * (1 - k)).toFixed(2));
      if (k < 1) requestAnimationFrame(step); else if (g.parentNode) g.parentNode.removeChild(g);
    });
    return true;
  };
  function buildFacts() {
    facts = [];
    var a = ST.alerts && ST.alerts.data, s = (a && a.stats24h) || {}, sv = s.bySeverity || {};
    var g = ST.geo && ST.geo.data, au = (ST.audit && ST.audit.data && ST.audit.data.summary) ||
      (ST.home && ST.home.data && ST.home.data.audit && ST.home.data.audit.summary);
    if (s.trend && s.trend.length) {
      var peak = s.trend.reduce(function (m, x) { return x.count > m.count ? x : m; }, s.trend[0]);
      facts.push('今天 ' + peak.time + ' 那一小时最猛，' + fmt(peak.count) + ' 条。');
    }
    if (g && g.byCountry && g.byCountry.length) {
      facts.push('最多的是' + (g.byCountry[0].countryName || g.byCountry[0].country) + '，' + fmt(g.byCountry[0].count) + ' 次。');
    }
    if (sv.CRITICAL) facts.push('严重 ' + fmt(sv.CRITICAL) + ' 条，占 ' + pct(sv.CRITICAL, s.total) + '。');
    if (au) facts.push('现在封着 ' + fmt(au.blockActive) + ' 个 IP，累计 ' + fmt(au.blockTotal) + ' 次。');
  }
  function renderAudit() {
    var a = ST.audit && ST.audit.data;
    var sm = (a && a.summary) || (ST.home && ST.home.data && ST.home.data.audit && ST.home.data.audit.summary);
    if (!sm) return;
    setNum('hudBlocks', sm.blockActive);
    setTxt('hudBlockSub', '累计 ' + fmt(sm.blockTotal) + ' · 护栏 ' + fmt(sm.blockedByGuard));
    setTxt('hudBlockSub2', fmt(sm.blockTotal));
  }
  function renderSys() {
    var atk = ST.atk && (ST.atk.data || ST.atk);
    if (atk && atk.mappedPct != null) setTxt('hudAtkPct', (atk.mappedPct).toFixed(1) + '%');
    var home = ST.home && ST.home.data;
    if (home && home.honeypot) {
      setNum('hudHoneyConn', home.honeypot.connections || home.honeypot.sessions);
      setNum('hudHoneyLogin', home.honeypot.logins);
    }
    if (ST.daily && ST.daily.count != null) setNum('hudArchive', ST.daily.count);
    var sm = d.body && d.body.getAttribute('data-samples');
    if (sm) setTxt('hudSamples', fmt(Number(sm)));
    if (ST.deploy && ST.deploy.data && ST.deploy.data.build) setTxt('hudSha', (ST.deploy.data.build.sha || '').slice(0, 7));
  }

  function drawSpark(pts) {    var svg = q('#hudSpark'); if (!svg) return;
    var W = 900, H = 120, max = Math.max.apply(null, pts.concat([1])), min = 0;
    var step = W / Math.max(1, pts.length - 1);
    var line = pts.map(function (v, i) {
      return (i ? 'L' : 'M') + (i * step).toFixed(1) + ' ' + (H - (v - min) / (max - min || 1) * (H - 12) - 6).toFixed(1);
    }).join(' ');
    var area = line + ' L' + W + ' ' + H + ' L0 ' + H + ' Z';
    svg.innerHTML = '<defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0" stop-color="rgba(111,211,216,.30)"/><stop offset="1" stop-color="rgba(111,211,216,0)"/></linearGradient></defs>' +
      '<path d="' + area + '" fill="url(#sg)"/><path d="' + line + '" fill="none" stroke="rgba(111,211,216,.9)" stroke-width="1.6"/>';
    var pi = pts.indexOf(max);
    if (pi >= 0) svg.insertAdjacentHTML('beforeend', '<circle cx="' + (pi * step).toFixed(1) + '" cy="' +
      (H - (max - min) / (max - min || 1) * (H - 12) - 6).toFixed(1) + '" r="3" fill="#f0b260"/>');
  }

  /* ---------- 第二屏 ---------- */
  function renderS2() {
    var s = ST.stories && ST.stories.data;
    if (s && s.sources) {
      var top = s.sources.slice(0, 5);
      q('#hudHunters').innerHTML = top.map(function (x, i) {
        var st = x.stages || {};
        var bar = [['告警', st.alerts], ['诱饵端口', st.decoyPorts], ['蜜罐登录', st.honeypotLogins], ['处置', st.auditActions]]
          .map(function (p) {
            return '<span class="hs' + (p[1] ? '' : ' z') + '">' + p[0] + ' ' + (p[1] ? fmt(p[1]) : '—') + '</span>';
          }).join('');
        return '<div class="hn"><b>' + (i + 1) + '</b><span class="hip">' + (x.srcIp || '').replace(/\.\d+$/, '.x') + '</span>' +
          '<span class="hsev">' + (x.severityMax || '') + '</span><div class="hst">' + bar + '</div></div>';
      }).join('');
    }
    /* 弱口令：优先用 home.js 的蜜罐 topCredentials（password.js 快照常为空） */
    var hp = ST.home && ST.home.data && ST.home.data.honeypot;
    var p = ST.pwd && ST.pwd.data;
    var plist = (hp && hp.topCredentials) || (p && (p.top || p.passwords || p.items)) || [];
    bars(q('#hudPwd'), plist.slice(0, 6).map(function (x) {
      return { k: (x.key || x.password || x.value || '').split(' / ')[0], n: x.count || x.tries || 0 };
    }), null, '');
    var w = ST.web && ST.web.data;
    var wl = (w && (w.topCategories || w.hours)) || [];
    bars(q('#hudWeb'), wl.slice(0, 6).map(function (x) {
      return { k: x.category || x.name || x.hour || x.time, n: x.count || x.hits || 0 };
    }), null, '');
  }

  /* ---------- 轮询 + SSE ---------- */

  /* ---------- 陆地轮廓（构建期生成的 SVG，运行期只取一次） ---------- */
  (function () {
    var g = d.getElementById('hudLand'); if (!g) return;
    fetch('/images/crt/world-land.svg').then(function (r) { return r.text(); }).then(function (t) {
      var box = d.createElement('div'); box.innerHTML = t;
      var svg = box.querySelector('svg'); if (svg) g.innerHTML = svg.innerHTML;
    }).catch(function () {});
  })();

  /* ---------- 角色：真素材精灵动画（会眨眼、会说话，按事件换表情） ----------
     素材：/kurisu/avatar/<emotion>.{idle,speaking}.webp（每个格子 132px，8 列）
       idle     3 帧 / 170ms；speaking 40 帧 / 41ms（manifest.json 的 emotions.* 口径） */
  (function () {
    var cv = d.getElementById('hudAv'); if (!cv || !cv.getContext) return;
    var ctx = cv.getContext('2d'), CELL = 132, COLS = 8;
    ctx.imageSmoothingQuality = 'high';
    var EMO = ['normal', 'happy', 'angry', 'sad', 'blush', 'disappointed', 'sided_thinking', 'sided_surprised'];
    var cache = {}, cur = 'normal', t0 = performance.now(), speakUntil = 0;
    function url(e, k) { return '/kurisu/avatar/' + e + '.' + k + '.webp'; }
    function img(u) { if (!cache[u]) { var m = new Image(); m.src = u; cache[u] = m; } return cache[u]; }
    function geom(k) { return k === 'speaking' ? { f: 40, ms: 41 } : { f: 3, ms: 170 }; }
    EMO.forEach(function (e) { img(url(e, 'idle')); });
    img(url('normal', 'speaking'));
    function tick() {
      var now = performance.now(), k = now < speakUntil ? 'speaking' : 'idle', g = geom(k), im = img(url(cur, k));
      if (im.complete && im.naturalWidth) {
        var i = Math.floor((now - t0) / g.ms) % g.f, sx = (i % COLS) * CELL, sy = Math.floor(i / COLS) * CELL;
        ctx.clearRect(0, 0, cv.width, cv.height);
        ctx.drawImage(im, sx, sy, CELL, CELL, 0, 0, cv.width, cv.height);
      }
      requestAnimationFrame(tick);
    }
    window.__hudChar = {
      emotion: function (e) { if (EMO.indexOf(e) >= 0 && e !== cur) { cur = e; t0 = performance.now(); } },
      speak: function (ms) { speakUntil = performance.now() + (ms || 1600); }
    };
    var last = '';
    setInterval(function () {
      var el = d.getElementById('hudLine'); if (!el) return;
      var t = el.textContent || '';
      if (t !== last) { if (t.length > last.length) window.__hudChar.speak(Math.min(5200, t.length * 70)); last = t; }
      var e = 'normal';
      if (/封禁|拦下|处置|暴力/.test(t)) e = 'angry';
      else if (/最猛|峰值|高峰/.test(t)) e = 'sided_surprised';
      else if (/建议|可以|应该|看哪/.test(t)) e = 'sided_thinking';
      else if (/成功|恢复|正常/.test(t)) e = 'happy';
      window.__hudChar.emotion(e);
    }, 1200);
    requestAnimationFrame(tick);
  })();

  function pull() {
    return Promise.all([
      J('/api/public/alerts.js'), J('/api/public/geo.js'), J('/api/public/audit.js'),
      J('/api/public/attack.js'), J('/api/public/home.js'), J('/api/public/daily/index.json'), J('/api/public/deploy.js')
    ]).then(function (r) {
      ST.alerts = r[0]; ST.geo = r[1]; ST.audit = r[2]; ST.atk = r[3]; ST.home = r[4]; ST.daily = r[5]; ST.deploy = r[6];
      renderTop(); renderGeo(); renderAudit(); renderSys();
      /* 第二屏的弱口令依赖 home.js 的 honeypot，pullS2 可能先跑完，这里补渲染一次 */
      try { renderS2(); } catch (e) {}
      buildFacts();
      setTxt('hudSync', '同步 ' + new Date().toTimeString().slice(0, 8));
    });
  }
  function pullS2() {
    return Promise.all([J('/api/public/stories.js'), J('/api/public/password.js'), J('/api/public/webstats.js')])
      .then(function (r) { ST.stories = r[0]; ST.pwd = r[1]; ST.web = r[2]; renderS2(); });
  }

  /* ---------- 启动 ---------- */
  var reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduced) d.documentElement.classList.add('hud-nofx');
  hints = buildHints();
  pull().then(function () {
    if (facts.length) speak(facts[0], '首轮播报');
  });
  pullS2();
  setInterval(pull, 5000);
  setInterval(pullS2, 60000);

  // SSE：有就用推流（更快的日志流），断线不报错，轮询继续
  try {
    if (window.EventSource && !d.documentElement.classList.contains('xk-slow')) {
      var es = new EventSource('/api/public/stream');
      es.addEventListener('alert', function (ev) {
        try {
          var it = JSON.parse(ev.data);
          var host = q('#hudLogList'); if (!host) return;
          host.insertAdjacentHTML('afterbegin', row({ occurredAt: ' ' + (it.time || ''), srcIp: it.src, typeLabel: (it.kind || '') + ' ' + (it.rule || '').slice(0, 40), severity: it.sev }, true));
          while (host.children.length > 16) host.removeChild(host.lastElementChild);
          if (it.cc && window.__hudPulse) window.__hudPulse(it.cc, it.sev);
        } catch (e) {}
      });
      es.onerror = function () { es.close(); };
    }
  } catch (e) {}
})();
