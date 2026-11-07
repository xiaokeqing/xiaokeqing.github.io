/* 「点个 IP，看它干过什么」——把 /alerts/ 上已经有的 Top 来源做成可点的入口，
 * 点击直接跳 /ip/?q=<IP>（那页有 /api/public/story 的攻击时间线）。
 *
 * 约束：
 *   · 不新增任何接口请求：chips 只读本页已有的 DOM（.row .k 里的 IP）与 window.XK24H 之类，
 *     一个都拿不到就只留输入框，不编数据。
 *   · 只跳转，不 POST；输入框做一次宽松的 IPv4 校验（明显不是 IP 就不放行，提示原因）。
 */
(function () {
  'use strict';
  var doc = document;
  var form = doc.getElementById('ipjumpForm');
  var input = doc.getElementById('ipjumpInput');
  var chips = doc.getElementById('ipjumpChips');
  var note = doc.getElementById('ipjumpNote');
  if (!form || !input) return;

  var IPV4 = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;

  function isPrivate(ip) {
    var p = ip.split('.').map(Number);
    if (p[0] === 10 || p[0] === 127) return true;
    if (p[0] === 192 && p[1] === 168) return true;
    if (p[0] === 172 && p[1] >= 16 && p[1] <= 31) return true;
    if (p[0] === 169 && p[1] === 254) return true;
    return false;
  }

  form.addEventListener('submit', function (e) {
    var v = (input.value || '').trim();
    if (!IPV4.test(v) || isPrivate(v)) {
      e.preventDefault();
      if (note) note.textContent = '这不是可查的公网 IPv4（内网/保留地址查不到公网攻击记录）—— 换一个再试。';
      input.focus();
    }
  });

  // 从本页已有 DOM 里捞 Top 来源：/geo 的榜单行形如 "NL · 荷兰  121,607 次 · 46.18%" 不含 IP，
  // 但实时流每行结尾有"← 193.32.162.20"，所以从那里取，去重后取前 6 个。
  function collect() {
    var seen = {};
    var out = [];
    var nodes = doc.querySelectorAll('.term-bd .ln, .term-bd .t-line, .term-bd div');
    for (var i = 0; i < nodes.length && out.length < 6; i++) {
      var txt = nodes[i].textContent || '';
      var m = txt.match(/\b((?:\d{1,3}\.){3}\d{1,3})\b/g);
      if (!m) continue;
      for (var k = 0; k < m.length; k++) {
        var ip = m[k];
        if (!IPV4.test(ip) || isPrivate(ip) || seen[ip]) continue;
        seen[ip] = 1;
        out.push(ip);
        if (out.length >= 6) break;
      }
    }
    return out;
  }

  function render() {
    if (!chips) return;
    var list = collect();
    if (!list.length) {
      chips.textContent = '';
      return;
    }
    chips.textContent = 'Top 来源：';
    list.forEach(function (ip) {
      var a = doc.createElement('a');
      a.className = 'ipjump-chip';
      a.href = '/ip/?q=' + encodeURIComponent(ip);
      a.textContent = ip;
      chips.appendChild(a);
    });
  }

  // 实时流是 SSE/轮询异步填的：先跑一次，再在 3 s / 8 s 各补一次（有就补，没有就算了）。
  render();
  setTimeout(render, 3000);
  setTimeout(render, 8000);
})();
