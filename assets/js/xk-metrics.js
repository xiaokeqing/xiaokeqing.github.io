/* 处置时效（MTTD / MTTR）卡片 —— 只读，吃 /api/public/metrics（脱敏聚合，不含 IP）。
 *
 * 口径三条（和后端一致，别在页面上改）：
 *   1. 样本 <3 → 后端返回 {available:false, reason:"样本不足", samples:n}，
 *      页面照抄 reason，**不写 0 分钟** —— 0 会被读成"处理得飞快"。
 *   2. 取不到 / 接口 4xx-5xx / 非 JSON ⇒ 两个数字写 "—"，脚下说明写"未取到（原因）"，
 *      不编数、不补 0。
 *   3. 只在 /alerts/（data-xk-ssr=monitor）且不是慢网时跑；慢网省掉这一次请求。
 */
(function () {
  'use strict';
  var doc = document;
  var host = doc.getElementById('modMetrics');
  if (!host) return;
  var ssr = doc.getElementById('content');
  var page = ssr && ssr.getAttribute('data-xk-ssr');
  if (page !== 'monitor') return;
  if (doc.documentElement.classList.contains('xk-slow')) {
    // 慢网不为此多打一次请求：把"取数中…"改成如实说明，别让人以为一直在转圈。
    elTtd.textContent = '—';
    elTtr.textContent = '—';
    elNote.textContent = '慢网下不请求这一项（省一次往返）；换个网速正常的网络刷新就能看到。';
    return;
  }

  var elTtd = doc.getElementById('mtMttd');
  var elTtr = doc.getElementById('mtMttr');
  var elNote = doc.getElementById('mtNote');
  if (!elTtd || !elTtr || !elNote) return;

  function apiBase() {
    var w = window.wb_api || window.WB_API || '';
    if (w) return String(w).replace(/\/+$/, '');
    return 'https://demo.xiaokeqing.cn';
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

  var url = apiBase() + '/api/public/metrics?hours=24';
  fetch(url, { headers: { Accept: 'application/json' } })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (j) {
      var d = (j && j.data) || {};
      var okTtd = cell(elTtd, d.mttd);
      var okTtr = cell(elTtr, d.mttr);
      var s = d.samples || {};
      var bits = [];
      bits.push('24 小时窗口');
      if (s.alerts != null) bits.push('告警 ' + s.alerts + ' 条');
      if (s.mttdPairs != null) bits.push('可配对 ' + s.mttdPairs + ' 对');
      if (!okTtd || !okTtr) bits.push('配对数不足 3 时只报原因、不报 0');
      if (d.mode && d.mode !== 'REAL') bits.push('模式 ' + d.mode + '（含演练数据已剔除）');
      elNote.textContent = bits.join(' · ');
    })
    .catch(function (e) {
      elTtd.textContent = '—';
      elTtr.textContent = '—';
      elNote.textContent = '未取到（' + (e && e.message ? e.message : '接口不可用') + '）· 这里不编数';
    });
})();
