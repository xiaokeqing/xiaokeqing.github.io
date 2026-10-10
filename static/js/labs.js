/* ============================================================
   交互式靶场 —— 全部在浏览器本地运行
   ------------------------------------------------------------
   设计原则（很重要，决定了这个页面的安全性）：

   1. 绝不 eval、绝不用 innerHTML 插入用户输入。
      所有输出一律 createElement + textContent，
      所以即使输入 <script>alert(1)</script> 也只会被显示成文字。

   2. 所有的"漏洞代码"都是【字符串拼接的模拟】，不会真的执行。
      比如 SQL 演示只是把 SQL 语句拼出来给你看，
      不会连数据库；命令注入演示只是把命令字符串拼出来，
      不会调用任何系统接口。

   3. 目的不是教怎么打，而是让你看见"后台那一刻到底发生了什么"。
      所以每个演示都强调：拼接后的原始结果 + 如何修复。
   ============================================================ */
(function () {
    'use strict';

    /* ---------------- 通用小工具 ---------------- */

    // 创建一个元素，children 可以是字符串或元素。
    // 字符串一律走 textContent，从根上杜绝 XSS。
    function h(tag, opts, children) {
        var node = document.createElement(tag);
        opts = opts || {};
        if (opts.className) node.className = opts.className;
        if (opts.text != null) node.textContent = String(opts.text);
        (children || []).forEach(function (c) {
            if (c == null) return;
            node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
        });
        return node;
    }

    // 把字符串按"命中区间"切片，命中部分加上高亮样式。
    // ranges: [{start, end, cls}]
    function highlight(text, ranges) {
        var wrap = h('span', { className: 'labs-code' });
        if (!ranges || !ranges.length) {
            wrap.appendChild(document.createTextNode(text));
            return wrap;
        }
        var sorted = ranges.slice().sort(function (a, b) { return a.start - b.start; });
        var pos = 0;
        sorted.forEach(function (r) {
            if (r.start < pos) return;           // 重叠区间跳过，避免错乱
            if (r.start > pos) {
                wrap.appendChild(document.createTextNode(text.slice(pos, r.start)));
            }
            wrap.appendChild(h('mark', {
                className: 'labs-mark ' + (r.cls || 'danger'),
                text: text.slice(r.start, r.end)
            }));
            pos = r.end;
        });
        if (pos < text.length) wrap.appendChild(document.createTextNode(text.slice(pos)));
        return wrap;
    }

    // 在字符串里找所有 needle 的位置（用于高亮用户输入部分）
    function findRanges(text, needle, cls) {
        var out = [];
        if (!needle) return out;
        var i = text.indexOf(needle);
        while (i !== -1) {
            out.push({ start: i, end: i + needle.length, cls: cls });
            i = text.indexOf(needle, i + needle.length);
        }
        return out;
    }

    function resultRow(label, valueNode, note) {
        return h('div', { className: 'labs-row' }, [
            h('div', { className: 'labs-row-label', text: label }),
            h('div', { className: 'labs-row-value' }, [valueNode]),
            note ? h('div', { className: 'labs-row-note', text: note }) : null
        ]);
    }

    function verdict(level, text) {
        return h('div', { className: 'labs-verdict labs-verdict-' + level }, [
            h('span', { className: 'labs-verdict-dot' }),
            h('span', { text: text })
        ]);
    }

    function presetButton(label, payload, onClick) {
        var b = h('button', { className: 'labs-preset', text: label });
        b.type = 'button';
        b.addEventListener('click', function () { onClick(payload); });
        return b;
    }

    /* ============================================================
       演示 1：SQL 注入
       ============================================================ */

    function sqlDemo() {
        var input = h('input', { className: 'labs-input' });
        input.type = 'text';
        input.value = "admin' OR '1'='1";
        input.spellcheck = false;

        var out = h('div', { className: 'labs-out' });

        function render() {
            var v = input.value;
            // 这就是"有漏洞的写法"：把用户输入直接拼进 SQL
            var sql = "SELECT id, username, role FROM users WHERE username = '" + v +
                      "' AND password = '" + "***" + "'";

            // 判断是否可能让条件恒真
            var tautology = /('\s*or\s*'?[^']*'?\s*=\s*'?[^']*'?)|(\bor\b\s+1\s*=\s*1)|(--|\/\*)/i.test(v);
            var comment = /(--|#|\/\*)/.test(v);

            out.textContent = '';
            out.appendChild(resultRow(
                '有漏洞的写法',
                h('div', { className: 'labs-codeblock' }, [
                    highlight(sql, findRanges(sql, v, 'danger'))
                ]),
                '用户输入被当作 SQL 语法的一部分，而不是数据'
            ));

            out.appendChild(resultRow(
                '数据库实际执行的条件',
                h('div', { className: 'labs-codeblock' }, [
                    h('span', { text: "username = '" }),
                    highlight(v, findRanges(v, v, 'danger')),
                    h('span', { text: "' AND password = '***'" })
                ]),
                comment
                    ? '输入里的注释符会把后半段 AND 条件整段注释掉'
                    : null
            ));

            out.appendChild(verdict(
                tautology ? 'bad' : 'ok',
                tautology
                    ? '⚠️ 判定：条件可能恒真 —— 密码校验被绕过，查询会返回用户记录'
                    : '判定：本次输入未构成条件恒真，但拼接写法本身依然不安全'
            ));

            // 修复版本：参数化查询
            var fixed = "SELECT id, username, role FROM users WHERE username = ? AND password = ?";
            out.appendChild(resultRow(
                '修复后的写法（参数化查询）',
                h('div', { className: 'labs-codeblock' }, [
                    highlight(fixed, findRanges(fixed, '?', 'safe'))
                ]),
                '占位符交给数据库预编译。整个输入被当作一个字符串值，无法改变语法结构'
            ));
            out.appendChild(h('div', { className: 'labs-tip' }, [
                h('strong', { text: '同样输入 ' }),
                h('code', { text: v }),
                h('strong', { text: ' 在修复版本里的下场：' }),
                h('div', { className: 'labs-codeblock' }, [
                    h('span', { text: 'username = ' }),
                    h('mark', { className: 'labs-mark safe', text: "'" + v + "'" }),
                    h('span', { text: '   ← 被当成一个普通字符串，查不到任何用户' })
                ])
            ]));
        }

        input.addEventListener('input', render);

        return {
            title: 'SQL 注入',
            subtitle: '用户输入被当成 SQL 语法，而不是数据',
            presets: [
                ['正常输入', 'admin'],
                ["经典绕过  ' OR '1'='1", "admin' OR '1'='1"],
                ['注释截断  --', "admin'--"],
                ['永真式  1=1', "' OR 1=1--"]
            ],
            controls: [input],
            output: out,
            render: render
        };
    }

    /* ============================================================
       演示 2：路径穿越
       ============================================================ */

    var BASE_DIR = '/var/www/uploads';

    // 真正实现一遍路径规范化：处理 . 和 ..
    function normalizePath(p) {
        var isAbs = p.charAt(0) === '/';
        var parts = p.replace(/\\/g, '/').split('/');
        var stack = [];
        parts.forEach(function (seg) {
            if (seg === '' || seg === '.') return;
            if (seg === '..') {
                // 已经到顶了就保留 ..（相对路径的情形）
                if (stack.length && stack[stack.length - 1] !== '..') stack.pop();
                else if (!isAbs) stack.push('..');
            } else {
                stack.push(seg);
            }
        });
        return (isAbs ? '/' : '') + stack.join('/');
    }

    function traversalDemo() {
        var input = h('input', { className: 'labs-input' });
        input.type = 'text';
        input.value = '../../etc/passwd';
        input.spellcheck = false;

        var out = h('div', { className: 'labs-out' });

        function render() {
            var v = input.value;
            var naive = BASE_DIR + '/' + v;
            var normalized = normalizePath(naive);
            var escaped = normalized.indexOf(BASE_DIR + '/') !== 0 && normalized !== BASE_DIR;

            out.textContent = '';
            out.appendChild(resultRow(
                '有漏洞的写法',
                h('div', { className: 'labs-codeblock' }, [
                    h('span', { text: 'File f = new File("' + BASE_DIR + '/" + ' }),
                    highlight(v, findRanges('File f = new File("' + BASE_DIR + '/" + ' + v + '")', v, 'danger')),
                    h('span', { text: ');' })
                ]),
                '用户输入直接参与路径拼接'
            ));

            out.appendChild(resultRow(
                '拼接后的原始路径',
                h('div', { className: 'labs-codeblock' }, [
                    highlight(naive, findRanges(naive, v, 'danger'))
                ]),
                '看起来还在 uploads 目录下 —— 这正是危险的地方'
            ));

            out.appendChild(resultRow(
                '操作系统实际解析到的路径',
                h('div', { className: 'labs-codeblock' }, [
                    h('mark', { className: escaped ? 'labs-mark danger' : 'labs-mark safe', text: normalized })
                ]),
                '内核会把 .. 逐级回退，最终指向的才是真正被打开的文件'
            ));

            out.appendChild(verdict(
                escaped ? 'bad' : 'ok',
                escaped
                    ? '⚠️ 判定：路径已越出 ' + BASE_DIR + ' —— 可以读取任意文件'
                    : '判定：路径仍在允许目录内'
            ));

            // 修复版本
            var fixedCode = 'Path base = Paths.get("' + BASE_DIR + '").toRealPath();\n' +
                            'Path target = base.resolve(userInput).normalize().toRealPath();\n' +
                            'if (!target.startsWith(base)) throw new SecurityException("非法路径");';
            out.appendChild(resultRow(
                '修复后的写法',
                h('div', { className: 'labs-codeblock labs-pre' }, [
                    h('span', { text: fixedCode })
                ]),
                '先规范化，再校验前缀。顺序不能反 —— 先校验后规范化会被绕过'
            ));
        }

        input.addEventListener('input', render);

        return {
            title: '路径穿越',
            subtitle: '路径拼好看着没问题，内核解析后却跑到了别处',
            presets: [
                ['正常文件', 'report.pdf'],
                ['经典穿越', '../../etc/passwd'],
                ['多层回退', '../../../../../../etc/shadow'],
                ['Windows 反斜杠', '..\\..\\windows\\win.ini'],
                ['看似合法', 'a/./../report.pdf']
            ],
            controls: [input],
            output: out,
            render: render
        };
    }

    /* ============================================================
       演示 3：命令注入
       ============================================================ */

    var SHELL_META = [
        { ch: ';', desc: '顺序执行：前面成功与否，后面都执行' },
        { ch: '|', desc: '管道：把前面的输出交给后面的命令' },
        { ch: '&', desc: '后台/顺序执行' },
        { ch: '`', desc: '命令替换：先执行反引号里的内容' },
        { ch: '$', desc: '变量展开或 $(...) 命令替换' },
        { ch: '>', desc: '重定向输出到文件' },
        { ch: '<', desc: '重定向输入' },
        { ch: '\n', desc: '换行：在 shell 里等同于分号' }
    ];

    function cmdDemo() {
        var input = h('input', { className: 'labs-input' });
        input.type = 'text';
        input.value = '127.0.0.1; whoami';
        input.spellcheck = false;

        var out = h('div', { className: 'labs-out' });

        function render() {
            var v = input.value;
            var cmd = 'ping -c 4 ' + v;

            // 找出输入里所有 shell 元字符
            var ranges = [];
            var hits = [];
            for (var i = 0; i < v.length; i++) {
                var c = v.charAt(i);
                for (var j = 0; j < SHELL_META.length; j++) {
                    if (SHELL_META[j].ch === c) {
                        ranges.push({ start: cmd.indexOf(v) + i, end: cmd.indexOf(v) + i + 1, cls: 'danger' });
                        if (hits.indexOf(c) === -1) hits.push(c);
                        break;
                    }
                }
            }

            out.textContent = '';
            out.appendChild(resultRow(
                '有漏洞的写法',
                h('div', { className: 'labs-codeblock' }, [
                    h('span', { text: 'Runtime.getRuntime().exec("ping -c 4 " + ' }),
                    h('span', { text: 'userInput' }),
                    h('span', { text: ');' })
                ]),
                '单字符串形式会交给 shell 解析，元字符会生效'
            ));

            out.appendChild(resultRow(
                'shell 实际收到的命令',
                h('div', { className: 'labs-codeblock' }, [highlight(cmd, ranges)]),
                hits.length
                    ? '红色部分会被 shell 当作语法，而不是 IP 地址的一部分'
                    : '本次输入没有 shell 元字符'
            ));

            if (hits.length) {
                var list = h('ul', { className: 'labs-list' });
                hits.forEach(function (c) {
                    var meta = SHELL_META.filter(function (m) { return m.ch === c; })[0];
                    list.appendChild(h('li', {}, [
                        h('code', { text: c === '\n' ? '\\n' : c }),
                        h('span', { text: ' — ' + (meta ? meta.desc : '') })
                    ]));
                });
                out.appendChild(resultRow('命中的元字符', list, null));
            }

            out.appendChild(verdict(
                hits.length ? 'bad' : 'ok',
                hits.length
                    ? '⚠️ 判定：输入可逃出原命令 —— 攻击者能执行任意命令'
                    : '判定：本次输入未包含 shell 元字符'
            ));

            var fixedCode =
                '// 一层：格式白名单，只接受合法 IP\n' +
                'if (!ip.matches("^(\\\\d{1,3}\\\\.){3}\\\\d{1,3}$")) throw new IllegalArgumentException();\n' +
                '\n' +
                '// 二层：用数组形式传参，不走 shell\n' +
                'new ProcessBuilder("ping", "-c", "4", ip).start();';
            out.appendChild(resultRow(
                '修复后的写法（两层防护）',
                h('div', { className: 'labs-codeblock labs-pre' }, [h('span', { text: fixedCode })]),
                'ProcessBuilder 的数组形式不经过 shell，元字符失去意义；白名单再兜一层'
            ));
        }

        input.addEventListener('input', render);

        return {
            title: '命令注入',
            subtitle: '拼接出来的字符串，交给 shell 后就不只是参数了',
            presets: [
                ['正常 IP', '127.0.0.1'],
                ['分号执行', '127.0.0.1; whoami'],
                ['管道', '127.0.0.1 | cat /etc/passwd'],
                ['命令替换', '127.0.0.1$(id)'],
                ['反引号', '127.0.0.1`id`'],
                ['换行绕过', '127.0.0.1\nid']
            ],
            controls: [input],
            output: out,
            render: render
        };
    }

    /* ============================================================
       演示 4：敏感信息扫描
       （对应 SecAgent 里真实存在的 SensitiveContentScanner）
       ============================================================ */

    var DLP_RULES = [
        { name: '阿里云 AccessKey', re: /LTAI[A-Za-z0-9]{12,20}/g, level: 'high' },
        { name: 'AWS Access Key', re: /AKIA[0-9A-Z]{16}/g, level: 'high' },
        { name: 'OpenAI 风格密钥', re: /sk-[A-Za-z0-9]{20,}/g, level: 'high' },
        { name: '私钥文件头', re: /-----BEGIN [A-Z ]*PRIVATE KEY-----/g, level: 'high' },
        { name: '身份证号', re: /[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]/g, level: 'high' },
        { name: '银行卡号', re: /\b\d{16,19}\b/g, level: 'medium' },
        { name: '手机号', re: /\b1[3-9]\d{9}\b/g, level: 'medium' },
        { name: '电子邮箱', re: /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, level: 'low' },
        { name: '内网 IP', re: /\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b/g, level: 'low' },
        { name: '代码里的口令赋值', re: /(?:password|passwd|pwd|secret|token)\s*[=:]\s*["']?[^\s"';,]{6,}/gi, level: 'medium' }
    ];

    function mask(s) {
        if (s.length <= 8) return s.charAt(0) + '***';
        return s.slice(0, 4) + '***' + s.slice(-3);
    }

    function dlpDemo() {
        var ta = h('textarea', { className: 'labs-textarea' });
        ta.value = [
            '服务器配置备份：',
            'accessKeyId = LTAI5tFakeKeyForDemo99',
            'db.password = Prod@2026!secret',
            '联系邮箱 admin@example.com，手机 13800138000',
            '内网数据库 192.168.10.23:3306'
        ].join('\n');
        ta.rows = 7;
        ta.spellcheck = false;

        var out = h('div', { className: 'labs-out' });

        function render() {
            var text = ta.value;
            var findings = [];

            DLP_RULES.forEach(function (rule) {
                var re = new RegExp(rule.re.source, rule.re.flags);
                var m;
                while ((m = re.exec(text)) !== null) {
                    findings.push({
                        rule: rule.name,
                        level: rule.level,
                        value: m[0],
                        start: m.index,
                        end: m.index + m[0].length
                    });
                    if (m.index === re.lastIndex) re.lastIndex++;   // 防零长度死循环
                }
            });

            findings.sort(function (a, b) { return a.start - b.start; });

            out.textContent = '';

            if (!findings.length) {
                out.appendChild(verdict('ok', '未命中任何敏感信息规则'));
                return;
            }

            var byLevel = { high: 0, medium: 0, low: 0 };
            findings.forEach(function (f) { byLevel[f.level]++; });

            out.appendChild(verdict('bad',
                '命中 ' + findings.length + ' 处：高危 ' + byLevel.high +
                ' / 中危 ' + byLevel.medium + ' / 低危 ' + byLevel.low));

            // 标注后的原文
            var ranges = findings.map(function (f) {
                return { start: f.start, end: f.end, cls: f.level === 'high' ? 'danger' : (f.level === 'medium' ? 'warn' : 'info') };
            });
            out.appendChild(resultRow(
                '原文标注',
                h('div', { className: 'labs-codeblock labs-pre' }, [highlight(text, ranges)]),
                '红=高危 橙=中危 蓝=低危'
            ));

            // 命中明细
            var table = h('table', { className: 'labs-table' });
            var thead = h('thead');
            var tr = h('tr');
            ['规则', '等级', '命中内容（已打码）', '位置'].forEach(function (t) {
                tr.appendChild(h('th', { text: t }));
            });
            thead.appendChild(tr);
            table.appendChild(thead);

            var tbody = h('tbody');
            findings.forEach(function (f) {
                var tr2 = h('tr');
                tr2.appendChild(h('td', { text: f.rule }));
                tr2.appendChild(h('td', {}, [
                    h('span', { className: 'labs-badge labs-badge-' + f.level, text: f.level === 'high' ? '高危' : (f.level === 'medium' ? '中危' : '低危') })
                ]));
                tr2.appendChild(h('td', {}, [h('code', { text: mask(f.value) })]));
                tr2.appendChild(h('td', { text: '第 ' + (text.slice(0, f.start).split('\n').length) + ' 行 · 偏移 ' + f.start }));
                tbody.appendChild(tr2);
            });
            table.appendChild(tbody);

            out.appendChild(resultRow('命中明细', table, null));

            out.appendChild(h('div', { className: 'labs-tip' }, [
                h('strong', { text: '这段逻辑在 SecAgent 里是真实存在的：' }),
                h('span', { text: 'SensitiveContentScanner 会在知识库入库和对话输出两个环节扫描，命中高危规则的内容会被拦截，不允许写进向量库、也不允许原样返回给用户。' })
            ]));
        }

        ta.addEventListener('input', render);

        return {
            title: '敏感信息扫描',
            subtitle: '这段规则在生产系统里真的在跑，不是玩具',
            presets: [
                ['还原示例', null],
                ['干净的文本', '这是一份不包含任何敏感信息的普通说明文档。'],
                ['混入私钥', '-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----'],
                ['混入身份证', '客户身份证号 110101199003071234，请核对。']
            ],
            controls: [ta],
            output: out,
            render: render
        };
    }

    /* ============================================================
       页面组装
       ============================================================ */

    function buildDemo(def, index) {
        var panel = h('section', { className: 'labs-panel' });
        panel.id = 'labs-panel-' + index;

        // 预设按钮
        if (def.presets && def.presets.length) {
            var bar = h('div', { className: 'labs-presets' });
            bar.appendChild(h('span', { className: 'labs-presets-label', text: '试试这些：' }));
            def.presets.forEach(function (p) {
                var target = def.controls[0];
                bar.appendChild(presetButton(p[0], p[1], function (payload) {
                    if (payload === null) { location.reload(); return; }
                    target.value = payload;
                    target.dispatchEvent(new Event('input'));
                    target.focus();
                }));
            });
            panel.appendChild(bar);
        }

        def.controls.forEach(function (c) { panel.appendChild(c); });
        panel.appendChild(def.output);

        def.render();
        return panel;
    }

    function init() {
        var root = document.getElementById('labs-app');
        if (!root) return;

        var demos = [sqlDemo(), traversalDemo(), cmdDemo(), dlpDemo()];

        var tabbar = h('div', { className: 'labs-tabs' });
        var body = h('div', { className: 'labs-body' });

        demos.forEach(function (def, i) {
            var btn = h('button', { className: 'labs-tab' });
            btn.type = 'button';
            btn.appendChild(h('span', { className: 'labs-tab-title', text: def.title }));
            btn.appendChild(h('span', { className: 'labs-tab-sub', text: def.subtitle }));
            btn.addEventListener('click', function () { select(i); });
            tabbar.appendChild(btn);

            body.appendChild(buildDemo(def, i));
        });

        var panels = body.querySelectorAll('.labs-panel');
        var tabs = tabbar.querySelectorAll('.labs-tab');

        function select(i) {
            for (var k = 0; k < panels.length; k++) {
                panels[k].classList.toggle('is-active', k === i);
                tabs[k].classList.toggle('is-active', k === i);
            }
            // 切回来后同步一次，保证显示的是当前输入的结果
            demos[i].render();
        }

        root.appendChild(tabbar);
        root.appendChild(body);
        select(0);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
