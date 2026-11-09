/* ============================================================================
   xk-explain.js —— /tour/ 与 /detections/ 的「让桐莉讲讲这段」
   ----------------------------------------------------------------------------
   零新增后端：只调站内已有的公开问答端点（同源，vercel.json 已 rewrite 到 demo）
     POST /api/public/ask
     body  : {"q": "<问题文本>"}
     resp  : {code, message, data:{answer, state, citations, quota, ...}}
     实测（2026-11-09）：HTTP 200；答案字段 = data.answer；请求体用 q 可正常返回。
     限流：每 IP 6 次/分钟（429）；后端 deadlineMs≈25000，这里 30s 兜底。
   纪律：
     · 每个 .mod 小节注入一个 12px 无边框按钮；标题行不改结构，靠 flex-wrap 让按钮
       在窄屏换行到标题下方（390 不挤爆标题）。
     · 请求体 = 本节标题 + 正文前三行 + 「只用这页上已有的信息回答，不要编造数字」。
     · 答案只用 textContent 落 DOM（不拼 innerHTML）；剥掉后端的 [EMO:x] 标记与末尾
       「依据：N 条 ›」引用行（本块不渲染引用卡，留着就是一条点不动的悬空提示）。
     · 失败如实写 HTTP 码 / 网络不可达 / 超时，不用「暂无内容」兜底。
     · 同一小节只请求一次；再点 = 折叠 / 展开切换，不重复计限流额度。
   ========================================================================== */
(function () {
  'use strict';

  var ASK_URL = '/api/public/ask';
  var ASK_TIMEOUT = 30000;               /* 后端 deadlineMs=25000，多给 5s */
  var ASK_MAX = 600;                     /* 公开面 maxQuestionChars=1200，留余量 */
  var TAG_TEXT = 'AI 生成 · 可能不准 · 不对数字负责';
  var TAIL = '只用这页上已有的信息回答，不要编造数字。';
  var BTN_TEXT = '让桐莉讲讲这段';
  var BLOCK_SEL = 'p, li, blockquote, figcaption, summary';
  var uid = 0;

  function norm(s) {
    return String(s == null ? '' : s).replace(/[\s\u00a0]+/g, ' ').trim();
  }
  function clip(s, n) {
    s = norm(s);
    return s.length > n ? s.slice(0, n) + '…' : s;
  }
  function headOf(mod) {
    for (var i = 0; i < mod.children.length; i++) {
      var c = mod.children[i];
      if (!c.classList) continue;
      if (c.classList.contains('mod-hd') || c.classList.contains('ch')) return c;
    }
    return null;
  }
  function bodyOf(mod, head) {
    for (var i = 0; i < mod.children.length; i++) {
      var c = mod.children[i];
      if (c !== head && c.classList && c.classList.contains('mod-bd')) return c;
    }
    return mod;
  }
  /* 标题：整行文字（含 /alerts/ 这类右侧标签），去掉注入的按钮本身 */
  function titleOf(head) {
    var c = head.cloneNode(true);
    var b = c.querySelector('.xk-ex-btn');
    if (b) { b.parentNode.removeChild(b); }
    return clip(c.textContent, 80);
  }
  /* 正文前三行：优先段落 / 列表项 / 折叠栏标题（顺序 = 文档顺序），
     没有这些块才退回直接子节点。每行截 120 字，避免把整张规则表塞进问题。 */
  function linesOf(root, head, limit) {
    var out = [], i, n, t;
    var nodes = root.querySelectorAll(BLOCK_SEL);
    for (i = 0; i < nodes.length && out.length < limit; i++) {
      n = nodes[i];
      if (head && head.contains(n)) continue;
      if (n.closest && n.closest('.xk-ex-panel')) continue;
      t = norm(n.textContent);
      if (t) out.push(clip(t, 120));
    }
    if (!out.length) {
      for (i = 0; i < root.children.length && out.length < limit; i++) {
        n = root.children[i];
        if (n === head || /^(SCRIPT|STYLE|BUTTON)$/.test(n.tagName)) continue;
        if (n.classList && n.classList.contains('xk-ex-panel')) continue;
        t = norm(n.textContent);
        if (t) out.push(clip(t, 120));
      }
    }
    return out;
  }
  function buildQuestion(head, body) {
    var title = titleOf(head);
    var lines = linesOf(body, head, 3);
    var q = '这一节的小标题是「' + title + '」。正文开头是：\n' +
      (lines.length ? lines.join('\n') : '（这一节没有正文段落）') + '\n' +
      '请用两三句话讲讲这一节在说什么。' + TAIL;
    if (q.length > ASK_MAX) {
      q = q.slice(0, ASK_MAX - TAIL.length - 2) + '\n' + TAIL;
    }
    return q;
  }
  /* 后端答案里的机器标记与悬空引用行不属于正文 */
  function cleanAnswer(a) {
    var s = String(a == null ? '' : a);
    s = s.replace(/\[EMO:[a-z0-9_-]+\]/gi, '');
    s = s.replace(/(^|\n)[ \t]*依据：[ \t]*\d+[ \t]*条[ \t]*›?[ \t]*$/g, '');
    return s.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  }

  var sections = document.querySelectorAll('.mod');
  for (var si = 0; si < sections.length; si++) {
    var mod = sections[si];
    if (mod.getAttribute('data-xk-ex')) continue;        /* 幂等：脚本重复引入也只挂一次 */
    var head = headOf(mod);
    if (!head) continue;
    mod.setAttribute('data-xk-ex', '1');

    var body = bodyOf(mod, head);
    var idx = ++uid;
    var panel = null, state = 'idle', pendingQ = '';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'xk-ex-btn';
    btn.textContent = BTN_TEXT;
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', 'xk-ex-panel-' + idx);
    head.appendChild(btn);

    (function (mod, head, body, btn, idxRef) {
      function makePanel() {
        if (panel) return panel;
        panel = document.createElement('div');
        panel.className = 'xk-ex-panel';
        panel.id = 'xk-ex-panel-' + idxRef;
        panel.hidden = true;
        panel.setAttribute('aria-live', 'polite');
        var tag = document.createElement('span');
        tag.className = 'xk-ex-tag';
        tag.textContent = TAG_TEXT;
        var p = document.createElement('p');
        p.className = 'xk-ex-body';
        panel.appendChild(tag);
        panel.appendChild(p);
        /* 紧跟小节标题后面：点完立刻能看见，不用滚到大表格底部 */
        if (body !== mod) body.insertBefore(panel, body.firstChild);
        else head.parentNode.insertBefore(panel, head.nextSibling);
        return panel;
      }
      function setBody(text) {
        makePanel().querySelector('.xk-ex-body').textContent = text;
      }
      function fail(msg) {
        var p = makePanel();
        p.className = 'xk-ex-panel is-err';
        p.querySelector('.xk-ex-body').textContent = msg;
        p.hidden = false;
        state = 'open';
        btn.textContent = '收起讲解';
        btn.disabled = false;
        btn.setAttribute('aria-expanded', 'true');
      }
      function succeed(answer) {
        var p = makePanel();
        p.className = 'xk-ex-panel';
        p.querySelector('.xk-ex-body').textContent = answer;
        p.hidden = false;
        state = 'open';
        btn.textContent = '收起讲解';
        btn.disabled = false;
        btn.setAttribute('aria-expanded', 'true');
      }
      function post(q) {
        var ctrl = (typeof AbortController === 'function') ? new AbortController() : null;
        var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, ASK_TIMEOUT);
        var opts = {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          cache: 'no-store',
          body: JSON.stringify({ q: q })
        };
        if (ctrl) opts.signal = ctrl.signal;
        return fetch(ASK_URL, opts).then(function (res) {
          clearTimeout(timer);
          return res.json().catch(function () { return null; }).then(function (bodyJson) {
            return { status: res.status, ok: res.ok, body: bodyJson };
          });
        }, function (err) {
          clearTimeout(timer);
          if (err && err.name === 'AbortError') { err.timeout = true; }
          throw err;
        });
      }
      function onClick() {
        if (state === 'loading') return;
        if (state === 'open') {
          panel.hidden = true;
          state = 'closed';
          btn.textContent = '展开讲解';
          btn.setAttribute('aria-expanded', 'false');
          return;
        }
        if (state === 'closed') {           /* 已请求过：只展开，不再打接口 */
          panel.hidden = false;
          state = 'open';
          btn.textContent = '收起讲解';
          btn.setAttribute('aria-expanded', 'true');
          return;
        }
        state = 'loading';
        btn.disabled = true;
        btn.textContent = '讲解中…';
        if (!pendingQ) pendingQ = buildQuestion(head, body);
        post(pendingQ).then(function (r) {
          if (r.status === 429) { fail('讲解失败：HTTP 429（限流，请等一分钟）'); return; }
          if (!r.ok) { fail('讲解失败：HTTP ' + r.status); return; }
          if (!r.body) { fail('讲解失败：返回不是 JSON'); return; }
          var d = (r.body.data !== undefined && r.body.data !== null) ? r.body.data : r.body;
          var ans = cleanAnswer(d && d.answer);
          if (!ans) {
            var why = r.body.reason || r.body.message;
            fail('讲解失败：接口没有返回 answer 正文' + (why ? '（' + norm(why) + '）' : ''));
            return;
          }
          succeed(ans);
        })['catch'](function (err) {
          if (err && err.timeout) { fail('讲解失败：超时（' + (ASK_TIMEOUT / 1000) + ' 秒未返回）'); return; }
          fail('讲解失败：网络不可达');
        });
      }
      btn.addEventListener('click', onClick);
    })(mod, head, body, btn, idx);
  }
})();
