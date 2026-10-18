/* ============================================================================
   /noise/ · 告警噪音指数 —— 页面逻辑（外链，Hugo Pipes 带内容指纹；模板里一行 JS 都不内联）
   ----------------------------------------------------------------------------
   只做一件事：fetch('/data/noise-index.json') 之后把三块填上
     ① 一句结论（心跳占比）② 噪音 vs 信号占比条（改两个 div 的 width）
     ③ 按规则表（sid / 描述 / 条数 / 占比 / 归类）+ 检测缺口那段说明
   三条硬规则（与产物口径一致，任何一条不满足就不写数字）：
     · 只渲染 JSON 里真的有的字段；缺字段/读不到就写「读不到（原因）—— 不补数」，**绝不写 0**；
     · 占比只用 JSON 里的 share（它由脚本 count÷total 现算），页面自己不再除一遍，
       避免"页面按自己的分母重算"造出第二个数字；
     · 所有文本走 textContent / createElement，不用 innerHTML 拼外部字符串
       （JSON 是自家产出的，一样当不可信输入处理）。
   ============================================================================ */
(function () {
  'use strict';

  var DATA_URL = '/data/noise-index.json';

  function $(id) { return document.getElementById(id); }

  function clear(node) {
    if (!node) return;
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== null && text !== undefined && text !== '') n.textContent = String(text);
    return n;
  }

  /* 千分位：278405 → 278,405（不用 toLocaleString，避免不同浏览器/语言环境给出不同结果） */
  function group(n) {
    if (n === null || n === undefined || n === '') return null;
    var s = String(n);
    if (!/^-?\d+$/.test(s)) return s;
    return s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  /* share(0.9486) → '94.9%'；没给 share 就是 null（调用方写「占比读不到」） */
  function pct(share) {
    if (share === null || share === undefined) return null;
    var v = Number(share);
    if (!isFinite(v)) return null;
    return (v * 100).toFixed(1) + '%';
  }

  function setText(id, txt) {
    var n = $(id);
    if (n && txt !== null && txt !== undefined) n.textContent = String(txt);
  }

  function setSync(txt) { setText('nxSync', '● ' + txt); }

  function stamp() {
    var d = new Date();
    function p2(x) { return ('0' + x).slice(-2); }
    return p2(d.getHours()) + ':' + p2(d.getMinutes()) + ':' + p2(d.getSeconds());
  }

  /* 读不到的统一渲染：说清原因 + 「不补数」，并把所有数字位留空（不写 0） */
  function renderMiss(why) {
    var conc = $('nxConc');
    if (conc) {
      clear(conc);
      conc.appendChild(document.createTextNode('这一页的数字'));
      var b = el('b', 'nx-miss', '读不到');
      conc.appendChild(b);
      conc.appendChild(document.createTextNode('（' + why + '）—— 不补数。'));
    }
    setText('nxConcNum', '—');
    setText('nxLegNoise', '—');
    setText('nxLegSig', '—');
    setText('nxLegNoiseSub', '条 · 占比—');
    setText('nxLegSigSub', '条 · 占比—');
    var sn = $('nxSegNoise'), ss = $('nxSegSig');
    if (sn) { sn.style.width = '0'; sn.textContent = ''; }
    if (ss) { ss.style.width = '100%'; ss.textContent = ''; }   /* 空条，不假装是"全信号" */
    var body = $('nxTblBody');
    if (body) {
      clear(body);
      var tr = el('tr');
      tr.appendChild(el('td', 'sid', '—'));
      var td = el('td', 'msg nx-miss');
      td.appendChild(el('b', 'nx-miss', '读不到'));
      td.appendChild(document.createTextNode('（' + why + '）—— 不补数'));
      tr.appendChild(td);
      tr.appendChild(el('td', 'num', '—'));
      tr.appendChild(el('td', 'pct', '—'));
      var cls = el('td', 'cls');
      cls.appendChild(el('span', 'nx-tag na', '读不到'));
      tr.appendChild(cls);
      body.appendChild(tr);
    }
    setText('nxRuleTag', '读不到');
    setText('nxGen', '—');
    setText('nxSrcTag', '');
    setSync('读不到（' + why + '）· 不补数 · ' + stamp());
  }

  function renderOk(d) {
    var total = d.totalAlerts;
    var hb = d.heartbeat || {};
    var hbN = hb.count;
    var noisePct = pct(d.noiseRatio);

    /* ---------- ① 一句结论 ---------- */
    var conc = $('nxConc');
    if (conc) {
      clear(conc);
      conc.appendChild(document.createTextNode('你的告警面板里 '));
      conc.appendChild(el('em', '', noisePct === null ? '—' : noisePct));
      conc.appendChild(document.createTextNode(' 是自家 agent 的心跳。'));
    }
    var sub = $('nxConcSub');
    if (sub) {
      clear(sub);
      sub.appendChild(document.createTextNode('分母与分子都在 JSON 里，可以自己除一遍：'));
      sub.appendChild(el('b', '', group(hbN) + ' ÷ ' + group(total)));
      sub.appendChild(document.createTextNode('。剩下的 '));
      sub.appendChild(el('b', '', group(d.signalAlerts) + ' 条'));
      sub.appendChild(document.createTextNode(' 是信号 —— 但这不等于"剩下的都是攻击"（见下面的检测缺口）。'));
    }
    if (d.window) setText('nxWin', '窗口 ' + d.window);

    /* ---------- ② 占比条 ---------- */
    var nr = (d.noiseRatio === null || d.noiseRatio === undefined) ? null : Number(d.noiseRatio);
    var sn = $('nxSegNoise'), ss = $('nxSegSig');
    if (nr !== null && isFinite(nr)) {
      var w = Math.max(0, Math.min(100, nr * 100));
      var ws = 100 - w;
      if (sn) { sn.style.width = w.toFixed(2) + '%'; sn.textContent = w >= 8 ? noisePct : ''; }
      if (ss) { ss.style.width = ws.toFixed(2) + '%'; ss.textContent = ws >= 8 ? (100 - w).toFixed(1) + '%' : ''; }
      var bar = $('nxBar');
      if (bar) bar.setAttribute('aria-label',
        '噪音 ' + noisePct + ' / 信号 ' + pct(1 - nr) + '（窗口 ' + (d.window || '') + '）');
    } else {
      if (sn) { sn.style.width = '0'; sn.textContent = ''; }
      if (ss) { ss.style.width = '100%'; ss.textContent = ''; }
    }
    setText('nxLegNoise', group(hbN) === null ? '—' : group(hbN));
    setText('nxLegNoiseSub', '条 · 占比' + (noisePct === null ? '—' : noisePct));
    setText('nxLegSig', group(d.signalAlerts) === null ? '—' : group(d.signalAlerts));
    setText('nxLegSigSub', '条 · 占比' + (nr === null ? '—' : pct(1 - nr)));

    /* ---------- ③ 按规则表 ---------- */
    var body = $('nxTblBody');
    var rows = d.byRule || [];
    if (body) {
      clear(body);
      if (!rows.length) {
        var tr0 = el('tr');
        tr0.appendChild(el('td', 'sid', '—'));
        var td0 = el('td', 'msg nx-miss');
        td0.appendChild(el('b', 'nx-miss', '读不到'));
        td0.appendChild(document.createTextNode('（产物里 byRule 是空数组）—— 不补数'));
        tr0.appendChild(td0);
        tr0.appendChild(el('td', 'num', '—'));
        tr0.appendChild(el('td', 'pct', '—'));
        var c0 = el('td', 'cls');
        c0.appendChild(el('span', 'nx-tag na', '读不到'));
        tr0.appendChild(c0);
        body.appendChild(tr0);
      }
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i] || {};
        var tr = el('tr');
        var isNoise = r['class'] === 'noise';
        tr.appendChild(el('td', 'sid', (r.sid === null || r.sid === undefined) ? '—' : r.sid));
        tr.appendChild(el('td', 'msg', r.msg || '（未给出规则名）'));
        tr.appendChild(el('td', 'num', group(r.count) === null ? '—' : group(r.count)));
        var ps = pct(r.share);
        tr.appendChild(el('td', 'pct', ps === null ? '—' : ps));
        var cls = el('td', 'cls');
        var tag = el('span', 'nx-tag ' + (isNoise ? 'noise' : 'signal'),
          isNoise ? '噪音' : '信号');
        if (r.sid === 0 || r.sid === null || r.sid === undefined) {
          tag.className = 'nx-tag na';
          tag.textContent = '信号·未归类';
        }
        cls.appendChild(tag);
        tr.appendChild(cls);
        body.appendChild(tr);
      }
    }
    setText('nxRuleTag', rows.length ? (rows.length + ' 条规则') : '无规则数据');

    /* ---------- 检测缺口 ---------- */
    var gap = d.detectorGap;
    if (gap) {
      if (gap.hits !== null && gap.hits !== undefined) setText('nxGapHits', group(gap.hits));
      if (gap.note) setText('nxGapWhy', gap.note);
      var hp = $('nxGap');
      if (hp) hp.setAttribute('data-gap-rule', String(gap.rule || ''));
    }

    /* ---------- ④ 口径 / notes / 出处 ---------- */
    if (d.window) setText('nxKvWin', d.window);
    var ul = $('nxNotes');
    if (ul) {
      clear(ul);
      var notes = d.notes || [];
      if (!notes.length) {
        ul.appendChild(el('li', 'nx-na', '产物里没有 notes[] —— 这一页没有额外要交代的口径。'));
      }
      for (var j = 0; j < notes.length; j++) ul.appendChild(el('li', '', notes[j]));
    }
    setText('nxGen', d.generatedAt || '—');
    setText('nxSrcTag', d.source ? '（source：' + d.source + '）' : '');
    setSync((d.available === true ? '已读到产物' : '产物 available:false') +
      (d.source ? ' · source=' + d.source : '') + ' · ' + stamp());
  }

  function run() {
    var init = { method: 'GET', credentials: 'omit', cache: 'no-cache',
                 headers: { 'Accept': 'application/json' } };
    fetch(DATA_URL, init).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.text();
    }).then(function (text) {
      var d = null;
      try { d = JSON.parse(text); } catch (e) { d = null; }
      if (!d || typeof d !== 'object') {
        renderMiss('产物不是合法 JSON');
        return;
      }
      if (d.available !== true) {
        renderMiss(d.reason || '产物写着 available:false，没给原因');
        return;
      }
      renderOk(d);
    }).catch(function (e) {
      var why = (e && e.message) ? e.message : '请求没到（文件缺失或被拦下）';
      renderMiss(why);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run, { once: true });
  } else {
    run();
  }
})();
