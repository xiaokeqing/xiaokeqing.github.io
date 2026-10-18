/* ============================================================================
   /tools/password/ 的唯一逻辑：本地算 SHA-256 → 只发前 5 位 hex → 用桶内 hash 的后 59 位自行比对。
   ----------------------------------------------------------------------------
   三条红线（页面上写的口径，这里逐条落实；改代码前先读这三条）：
     1. 口令原文只活在「输入框的 value」与「一次 TextEncoder 调用」里：
        不进请求（请求里只有 5 位前缀）、不进 console、不进 localStorage / sessionStorage、
        不进地址栏、不发第二次请求；算完立刻把输入框清空。
     2. 读不到就写「读不到（原因）—— 不补数」：绝不把"没回数据"渲染成"没命中"。
        Http 429 / 400 / 超时 / 响应形状不对 / 后端 available:false 是**五件不同的事**，
        各写各的原因。
     3. 文案不许说"你的密码已被泄露"：蜜罐只证明「这个口令被攻击者试过」，
        不证明它属于谁、也不证明它现在还能用。
   ★后端契约（PublicApiController#password，2026-10-18）：GET API/api/public/password?p=<5 hex>
     data = { prefix, match:null, available, bucketCount, bucketLastSeen, hashes[], listed[],
              truncated, limits{perMinute,maxHashesPerBucket,cacheSeconds,prefixHexChars,suffixHexChars},
              notes, generatedAt?, totalAttempts?, unique? }
     hashes = 蜜罐里**真实出现过**的口令（suffix）；listed = 只在公开弱口令榜里、蜜罐还没抓到过的。
     两者文案必须分开 —— 「榜上有名」不等于「被攻击者试过 N 次」。
   ============================================================================ */
(function () {
  'use strict';

  var TIMEOUT = 12000;
  var PREFIX_HEX = 5;   /* 与后端 limits.prefixHexChars 一致 */
  var SUFFIX_HEX = 59;  /* 与后端 limits.suffixHexChars 一致（64 - 5） */

  var meta = document.querySelector('meta[name="wb-api"]');
  var API = ((meta && meta.getAttribute('content')) || '').replace(/\/+$/, '');

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }
  function pad2(n) { return ('0' + n).slice(-2); }
  function clock(d) { return pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds()); }
  function setSync(txt) { var s = $('pwdSync'); if (s) s.textContent = '● ' + txt; }
  function setTag(txt) { var t = $('pwdTag'); if (t) t.textContent = txt; }
  function setLocal(txt) {
    var l = $('pwdLocal');
    if (l) { l.textContent = txt; }
  }

  /* 读不到的统一渲染：哪一项 + 原因 + 「不补数」 */
  function miss(what, why) {
    return '<b class="pwd-null">读不到</b>' +
      (why ? '<span class="pwd-na">（' + esc(why) + '）</span>' : '') +
      ' <span class="pwd-na">—— 不补数</span>';
  }

  /* ---------- 本地哈希：只在浏览器里发生，没有 fallback ---------- */
  function toHex(buf) {
    var b = new Uint8Array(buf), out = '';
    for (var i = 0; i < b.length; i++) { out += (b[i] < 16 ? '0' : '') + b[i].toString(16); }
    return out;
  }
  function sha256Hex(pw) {
    /* 没有 crypto.subtle（http 页面 / 太老的浏览器）就**不查**：
       绝不退化成"把口令发给后端算"——那等于把这条红线的另一半也踩了。 */
    if (!window.crypto || !window.crypto.subtle || !window.TextEncoder) { return null; }
    return window.crypto.subtle.digest('SHA-256', new window.TextEncoder().encode(pw)).then(toHex);
  }

  /* ---------- 结果渲染：命中 / 只在榜上 / 未命中 ---------- */
  function card(k, n, d, cls) {
    return '<div class="pwd-card' + (cls ? ' ' + cls : '') + '">' +
      '<span class="k">' + esc(k) + '</span>' +
      '<span class="n">' + n + '</span>' +
      '<span class="d">' + d + '</span></div>';
  }
  function countsRow(d) {
    var html = '<div class="pwd-cards">';
    html += card('同前缀桶合计 bucketCount',
      (d.bucketCount === null || d.bucketCount === undefined)
        ? miss('bucketCount', '后端这次没给数')
        : esc(d.bucketCount) + ' 次',
      '这 5 位前缀下**所有**口令的尝试次数合计，不是你这一个的次数');
    html += card('桶内最后一次出现 bucketLastSeen',
      (d.bucketLastSeen === null || d.bucketLastSeen === undefined)
        ? '<span class="pwd-na">这个桶没有时间戳</span>'
        : esc(d.bucketLastSeen),
      '蜜罐里这个前缀最后一次被尝试的时间');
    html += card('本桶下发的 hash 条数',
      esc((d.hashes || []).length) + ' 条',
      (d.truncated === true)
        ? '<b class="pwd-null">已截断（truncated:true）</b>'
        : '未被截断');
    html += '</div>';
    return html;
  }
  function truncNote(d) {
    if (d.truncated !== true) { return ''; }
    var cap = (d.limits && d.limits.maxHashesPerBucket) ? d.limits.maxHashesPerBucket : '上限';
    return '<p class="pwd-note"><b class="pwd-null">这次是截断的</b>：本桶只下发了前 ' + esc(cap) +
      ' 条（<code>truncated:true</code>）—— <b>未命中可能只是被截断了</b>，不代表这个口令不在字典里。</p>';
  }

  function renderHit(d) {
    return '<p class="pwd-p"><b class="pwd-bad">命中：这个口令在我们的蜜罐里被真实攻击者尝试过。</b></p>' +
      '<p class="pwd-p">同一个 5 位前缀桶里，攻击者一共试了 <b>' + esc(d.bucketCount) + '</b> 次' +
      '（<b>同前缀桶合计</b>，不是"你这一个口令被试了 ' + esc(d.bucketCount) + ' 次"）。' +
      (d.bucketLastSeen ? '这个桶最后一次出现是 <b>' + esc(d.bucketLastSeen) + '</b>。' : '') + '</p>' +
      countsRow(d) +
      '<p class="pwd-p"><b>该做什么</b>：如果这是你在用的口令（<b>请不要在这里输入常用口令</b>，见页面下方说明），' +
      '立刻换掉；换的地方优先是邮箱、银行、公司账号 —— 它们一旦被撞开，损失比一个小论坛大得多。' +
      '同一个口令不要在多处复用。</p>' +
      '<p class="pwd-note">命中只说明「这个口令被攻击者试过」，<b>不说明</b>它是谁的、也不说明哪个账号中招 —— ' +
      '蜜罐里没有真实账号，只有被尝试的记录。</p>' +
      truncNote(d);
  }

  function renderListed(d) {
    return '<p class="pwd-p"><b class="pwd-warn">榜上有名：这个口令在公开弱口令榜里。</b></p>' +
      '<p class="pwd-p">它出现在我们收录的<b>公开弱口令榜</b>里，但<b>我们的蜜罐还没抓到过它</b> —— ' +
      '所以这里<b>不能</b>说"被攻击者试过 N 次"（那是另一个数，见下面的桶合计）。' +
      '公开榜上的口令，攻击者拿现成字典撞库时同样会试。</p>' +
      countsRow(d) +
      '<p class="pwd-p"><b>该做什么</b>：既然在公开字典里，就按"已经被公开"对待，找机会换掉。</p>' +
      truncNote(d);
  }

  function renderMiss(d) {
    return '<p class="pwd-p"><b class="pwd-ok">未命中：这个前缀下没有记录。</b></p>' +
      '<p class="pwd-p">这<b>不代表绝对安全</b>：我们只统计自己蜜罐 24 小时窗口里真实出现过的爆破口令，' +
      '加上公开弱口令榜 —— 攻击者字典不是全集，别人手里的私有字典我们也看不到。</p>' +
      countsRow(d) +
      '<p class="pwd-note">' +
      (Number(d.bucketCount) > 0
        ? '这个桶里确实有 <b>' + esc(d.bucketCount) + '</b> 次尝试、<b>' + esc((d.hashes || []).length) +
          '</b> 条不同的口令，只是<b>都不是你查的这一个</b>。'
        : '这个 5 位前缀在我们的记录里一次都没出现过（蜜罐没抓到过任何落在这个桶里的口令）。') +
      ' 数据集生成于 <b>' + esc(d.generatedAt || '读不到') + '</b>' +
      (d.totalAttempts !== undefined && d.totalAttempts !== null
        ? '，共 <b>' + esc(d.totalAttempts) + '</b> 条尝试 / <b>' + esc(d.unique) + '</b> 个不同口令。'
        : '。') +
      '</p>' +
      truncNote(d);
  }

  function renderUnavailable(d, status) {
    return '<p class="pwd-p"><b class="pwd-null">读不到（' + esc(reasonOf(d, status)) + '）—— 不补数。</b></p>' +
      '<p class="pwd-p">' + esc(d && d.notes ? d.notes : '后端这次没有给出原因文本。') + '</p>' +
      '<p class="pwd-note">「读不到」<b>不等于</b>「没查到」，也<b>不等于</b>「安全」：这一页不会用任何本地估算值填空。' +
      '稍后再试；如果一直这样，说明字典索引还没生成（见下方「数据从哪来」）。</p>';
  }
  function reasonOf(d, status) {
    if (d && d.notes) {
      var m = /（([A-Z_]+[^）]*)）/.exec(String(d.notes));
      if (m) { return m[1]; }
    }
    return status ? ('HTTP ' + status) : '端点不可用';
  }

  function renderError(status, json, raw) {
    var reason = (json && json.reason) ? json.reason : ('HTTP ' + status);
    var msg = (json && json.message) ? json.message : '';
    var head = '<div class="pwd-cards">' +
      card('检查结果', '<b class="pwd-bad">读不到</b>', '原因：' + esc(reason), 'na') + '</div>';
    var hint = '';
    if (status === 429) {
      hint = '<p class="pwd-note">这是<b>防刷</b>，不是不让你查：同一个 IP 每分钟有次数上限（见 <code>limits.perMinute</code>）。' +
        '这个限制<b>不会</b>影响"本地算 hash"这一步 —— 你可以等一分钟再来。</p>';
    } else if (status === 400) {
      hint = '<p class="pwd-note">这多半是本页自己的 bug（正常流程只会发出 5 位小写 hex）。' +
        '把它当"读不到"处理，<b>不要</b>因此认为口令安全。</p>';
    }
    return head +
      '<p class="pwd-p" style="margin-top:12px"><b>读不到（' + esc(reason) + '）—— 不补数。</b> ' +
      esc(msg || '服务端拒绝了这个查询。') + '</p>' + hint +
      (json ? '' : '<p class="pwd-note">原始响应片段：<code>' + esc(String(raw || '').slice(0, 200)) + '</code></p>');
  }

  /* ---------- 主流程 ---------- */
  function run(pw) {
    var out = $('pwdOut'), btn = $('pwdGo'), box = $('pwdQ');
    if (!out) { return; }
    if (typeof pw !== 'string' || pw.length === 0) {
      out.innerHTML = '<p class="pwd-p"><b class="pwd-null">还没输入口令</b>：上面输入框里敲一个（<b>别敲常用口令</b>，' +
        '见页面下方说明），再点「检查」。</p>';
      setSync('待检查（本地算 hash，只发 5 位前缀）');
      setTag('未检查');
      return;
    }

    var pending;
    try {
      pending = sha256Hex(pw);
    } catch (e) {
      pending = null;
    }
    if (!pending) {
      out.innerHTML = '<p class="pwd-p"><b class="pwd-bad">这个浏览器不给本地 SHA-256</b>（' +
        '<code>crypto.subtle</code> 只在 <code>https://</code> 页面（或浏览器认定的本机回环地址）里才可用）。</p>' +
        '<p class="pwd-p">本页<b>拒绝</b>把口令原文发出去让服务器算 —— 那等于放弃这一页唯一的隐私保证。' +
        '<b>不补数</b>：这次没有任何结果。</p>' +
        '<p class="pwd-note">换 HTTPS 打开这一页，或用现代浏览器（Chrome / Edge / Firefox / Safari 近几年的版本都行）。</p>';
      setSync('读不到（浏览器不给本地 SHA-256，非 HTTPS？）· 不补数 · ' + clock(new Date()));
      setTag('读不到');
      return;
    }

    /* ★原文到此为止：立刻清空输入框，之后只用 hash */
    if (box) { box.value = ''; }
    if (btn) { btn.disabled = true; }
    setSync('本地算 SHA-256 …（口令不会离开浏览器）');
    setTag('计算中');

    pending.then(function (hex) {
      var prefix = hex.slice(0, PREFIX_HEX);
      var suffix = hex.slice(PREFIX_HEX, PREFIX_HEX + SUFFIX_HEX);
      setLocal('已本地算好 SHA-256，只发出前缀 ' + prefix + '（其余 59 位留在浏览器里比对）');
      setSync('正在查前缀 ' + prefix + ' …');
      setTag('查询中');

      var init = { method: 'GET', mode: 'cors', credentials: 'omit', cache: 'no-store',
                   headers: { 'Accept': 'application/json' } };
      var ctrl = null, timer = null, t0 = Date.now();
      if (window.AbortController) {
        ctrl = new AbortController();
        init.signal = ctrl.signal;
        timer = setTimeout(function () { ctrl.abort(); }, TIMEOUT);
      }
      fetch(API + '/api/public/password?p=' + prefix, init).then(function (res) {
        return res.text().then(function (text) {
          var json = null;
          try { json = JSON.parse(text); } catch (e) { json = null; }
          if (!res.ok) {
            out.innerHTML = renderError(res.status, json, text);
            setSync('读不到（HTTP ' + res.status + '）· 不补数 · ' + clock(new Date()));
            setTag('读不到');
            return;
          }
          if (!json || json.code !== 200 || !json.data) {
            out.innerHTML = renderError(res.status, json, text);
            setSync('读不到（响应不是约定的 {code,message,data}）· 不补数 · ' + clock(new Date()));
            setTag('读不到');
            return;
          }
          var d = json.data, ms = Date.now() - t0;
          if (d.available === false) {
            out.innerHTML = renderUnavailable(d, res.status);
            setSync('读不到（字典索引不可用）· 不补数 · ' + clock(new Date()));
            setTag('读不到');
            return;
          }
          var hashes = d.hashes || [], listed = d.listed || [];
          var hit = hashes.indexOf(suffix) >= 0;
          var onList = !hit && listed.indexOf(suffix) >= 0;
          out.innerHTML = hit ? renderHit(d) : (onList ? renderListed(d) : renderMiss(d));
          setSync('已查前缀 ' + prefix + ' · ' + (hit ? '命中蜜罐记录' : (onList ? '只在公开榜上' : '未命中')) +
                  ' · ' + clock(new Date()) + ' · ' + ms + ' ms');
          setTag(hit ? '命中' : (onList ? '榜上有名' : '未命中'));
        });
      }).catch(function (e) {
        var why = (e && e.name === 'AbortError')
          ? ('超时 ' + Math.round(TIMEOUT / 1000) + 's 未返回')
          : ('请求没到源站或被浏览器拦下：' + ((e && e.message) || e));
        out.innerHTML = '<p class="pwd-p"><b class="pwd-null">读不到</b>（' + esc(why) +
          '）—— <b>不补数</b>。</p><p class="pwd-note">哈希是在本地算的，这次只是查询请求没成功；' +
          '这一页不会用任何本地估算值填空。</p>';
        setSync('读不到（' + why + '）· 不补数 · ' + clock(new Date()));
        setTag('读不到');
      }).then(function () {
        if (timer) { clearTimeout(timer); }
        if (btn) { btn.disabled = false; }
      });
    }).catch(function (e) {
      /* digest 失败（极少见）：同样按"读不到"处理，绝不补数 */
      if (btn) { btn.disabled = false; }
      out.innerHTML = '<p class="pwd-p"><b class="pwd-null">读不到</b>（本地 SHA-256 计算失败：' +
        esc((e && e.message) || e) + '）—— <b>不补数</b>。</p>';
      setSync('读不到（本地哈希失败）· 不补数 · ' + clock(new Date()));
      setTag('读不到');
    });
  }

  var form = $('pwdForm');
  if (form) {
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var box = $('pwdQ');
      run(box && typeof box.value === 'string' ? box.value : '');
    }, false);
  }

  /* 页面里没有任何自动查询：不读地址栏、不读存储、不在载入时算任何东西。
     预填过的输入框一律清掉（浏览器"记住密码"不归本页管，但本页自己不留）。 */
  var initial = $('pwdQ');
  if (initial) { initial.value = ''; }
  setSync('待检查（本地算 hash，只发 5 位前缀）');
})();
