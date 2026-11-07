/* 处置时效（MTTD / MTTR）卡片 —— 只读，吃 /api/public/metrics（脱敏聚合，不含 IP）。
 *
 * 口径四条（和后端一致，别在页面上改）：
 *   1. 样本 <3 → 后端返回 {available:false, reason:"样本不足", samples:n}，
 *      页面照抄 reason，**不写 0 分钟** —— 0 会被读成"处理得飞快"。
 *   2. 窗口内一条封禁都没产生（samples.blocks === 0）时，MTTD/MTTR 没有分母，
 *      要写清"没有封禁记录所以不显示中位数，不是取数失败"，别让人以为是接口坏了。
 *   3. 取不到 / 接口 4xx-5xx / 非 JSON ⇒ 两个数字写 "—"，脚下说明写"未取到（原因）"，
 *      不编数、不补 0。
 *   4. 只在 /alerts/（data-xk-ssr=monitor）且不是慢网时跑；慢网省掉这一次请求，
 *      但要把"取数中…"改成如实说明（否则看起来像一直在转圈）。
 *
 * 取数口：全站已改"同源静态快照优先"（head-meta 把 meta[name=wb-api] 清空）。
 * 这里按同样的规矩读 meta —— 空 ⇒ 同源 /api/public/metrics.js 快照（秒开、免 CORS）；
 * 非空 ⇒ 直连那个 base 的实时端点 ?live=1 时才有。
 */
(function () {
  'use strict';
  var doc = document;

  var host = doc.getElementById('modMetrics') || doc.getElementById('xkMetricsCard');
  if (!host) return;

  var ssr = doc.getElementById('content');
  if (!ssr || ssr.getAttribute('data-xk-ssr') !== 'monitor') return;

  // 先取元素引用，再决定跑不跑 —— 顺序反了会在慢网分支上引用未定义变量（踩过一次：
  // "Cannot set properties of undefined (setting 'textContent')"，卡片还会显示成别的行的文案）。
  var elTtd = doc.getElementById('xkMtTtd');
  var elTtr = doc.getElementById('xkMtTtr');
  var elNote = doc.getElementById('xkMtNote');
  if (!elTtd || !elTtr || !elNote) return;

  // 卡底一行口径小字：常驻，和本次取数成败无关（成败写在 elNote 里）。
  (function foot() {
    var p = doc.getElementById('xkMtFoot');
    if (!p) {
      p = doc.createElement('p');
      p.id = 'xkMtFoot';
      p.className = 'xk-mt-foot';
      p.style.cssText = 'margin:6px 0 0;font-size:11px;line-height:1.6;color:var(--mut,#9AA7B0)';
      var body = (host.querySelector && host.querySelector('.mod-bd')) || host;
      body.appendChild(p);
    }
    p.textContent = '口径：MTTD = 告警 → 处置、MTTR = 封禁 → 恢复，都取 24h 窗口内的中位数；'
      + '可配对数 < 3 只写原因，不写 0 分钟。数据来自 /api/public/metrics（脱敏聚合，不含 IP）。';
  })();

  if (doc.documentElement.classList.contains('xk-slow')) {
    elTtd.textContent = '—';
    elTtr.textContent = '—';
    elNote.textContent = '慢网下不请求这一项（省一次往返）；网速正常时刷新即可看到中位数。';
    return;
  }

  function apiBase() {
    var m = doc.querySelector('meta[name="wb-api"]');
    var w = (m && m.getAttribute('content')) || window.wb_api || window.WB_API || '';
    w = String(w || '').trim().replace(/\/+$/, '');
    if (w) return w;
    return ''; // 空 ⇒ 同源静态快照（head-meta 已把 meta 清空）
  }

  function url(base) {
    return base ? base + '/api/public/metrics?hours=24' : '/api/public/metrics.js?hours=24';
  }

  function fmt(v) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    var n = Number(v);
    if (n >= 60) return (n / 60).toFixed(1).replace(/\.0$/, '') + ' 小时';
    return (n < 10 ? n.toFixed(1).replace(/\.0$/, '') : Math.round(n)) + ' 分钟';
  }

  function cell(el, m) {
    if (!m) { el.textContent = '—'; return false; }
    if (m.available) { el.textContent = fmt(m.medianMinutes); return true; }
    el.textContent = m.reason || '样本不足';
    return false;
  }

  fetch(url(apiBase()), { headers: { Accept: 'application/json' } })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (j) {
      var d = (j && j.data) || {};
      var s = d.samples || {};
      var avail = (d.mttd && d.mttd.available === true) || (d.mttr && d.mttr.available === true);
      var blocksZero = s.blocks === 0 || s.blocks === '0';

      if (blocksZero && !avail) {
        // blocks=0：窗口内没有任何封禁动作 ⇒ MTTD/MTTR 没有样本可配，不是取数失败。
        elTtd.textContent = '不适用';
        elTtr.textContent = '不适用';
        var detail = [];
        if (s.alerts != null) detail.push('窗口内告警 ' + s.alerts + ' 条');
        if (s.mttdPairs != null) detail.push('可配对 ' + s.mttdPairs + ' 对');
        elNote.textContent = '24h 内没有产生封禁记录（blocks=0），因此暂不显示 MTTD/MTTR 中位数；这不是取数失败。'
          + (detail.length ? '（' + detail.join(' · ') + '）' : '');
        if (d.mode && d.mode !== 'REAL') elNote.textContent += ' · 模式 ' + d.mode;
        return;
      }

      var okTtd = cell(elTtd, d.mttd);
      var okTtr = cell(elTtr, d.mttr);
      var bits = ['24 小时窗口'];
      if (s.alerts != null) bits.push('告警 ' + s.alerts + ' 条');
      if (s.blocks != null) bits.push('封禁 ' + s.blocks + ' 次');
      if (s.mttdPairs != null) bits.push('可配对 ' + s.mttdPairs + ' 对');
      if (!okTtd || !okTtr) bits.push('配对数不足 3 只报原因、不报 0');
      if (d.mode && d.mode !== 'REAL') bits.push('模式 ' + d.mode);
      elNote.textContent = bits.join(' · ');
    })
    .catch(function (e) {
      elTtd.textContent = '—';
      elTtr.textContent = '—';
      elNote.textContent = '未取到（' + (e && e.message ? e.message : '接口不可用') + '）· 这里不编数';
    });
})();
