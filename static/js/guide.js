/* ============================================================
   项目速查助手
   ------------------------------------------------------------
   为什么不用大模型做这个：

   1. 面试官问"这个项目解决什么问题"，他想要的是【准确答案】，
      不是一段可能编造的回答。本地知识库给出的每句话都是
      确定事实，不会幻觉。

   2. 博客是纯静态站，没有后端。要调大模型就必须在前端放 API Key
      —— 那等于把密钥公开在 GitHub 上，是最基础的错误。

   3. 它永远可用。服务器挂了、额度用完了、隧道断了，这个助手照常工作。

   想真的问大模型？面板底部有入口，跳转到在线 Demo 去问。
   ============================================================ */
(function () {
    'use strict';

    /* ---------------- 知识库 ----------------
       keywords 用于打分匹配，可以写多组同义词。
       links 是可选的跳转。 */
    var KB = [
        {
            q: '这个项目解决什么问题？',
            keywords: ['解决', '什么', '问题', '痛点', '为什么做', '背景', '价值', '做什么', '用途'],
            a: '安全运营中心每天产生几千到几万条告警，其中九成以上是误报和重复，真正的攻击被淹没在噪声里。分析师要在告警系统、日志平台、知识库、资产表之间来回切换才能下判断；判断完还要手工封 IP、锁账号 —— 慢、容易出错，而且处置没有留痕，事后无法复盘。SecAgent 就是把「告警 → 研判 → 处置」这条链路做成一个可编排、可审计、有护栏的闭环。',
            links: [{ t: '项目页', u: '/projects/' }]
        },
        {
            q: '你负责哪部分？',
            keywords: ['你', '负责', '贡献', '做', '写', '作者', '谁做', '自己', '独立', '多少'],
            a: '诚实说：代码是 AI 辅助生成的。我的角色是提需求、定方案、做取舍、逐步调试验证 —— 比如「处置护栏必须放在代码层而不是提示词层」「向量库要做存储抽象以免耦合 Milvus」这些决定是我做的，实现细节由 AI 写出来后我再逐条验证和调整。我的代码能力是：能改配置、改提示词、加简单接口，不能从零手写复杂逻辑。',
            links: [{ t: '关于我', u: '/about/' }]
        },
        {
            q: '为什么处置护栏要写在代码里，而不是提示词里？',
            keywords: ['护栏', '提示词', 'prompt', '代码', '绕过', '白名单', '处置', '安全', '注入'],
            a: '因为提示词可以被精心构造的输入绕过，而代码层的白名单绕不过去。比如「不要封禁内网地址」这句话写在提示词里，攻击者只要让模型相信这是外网地址就可能绕过；但如果封禁动作在执行前必须通过一个校验函数，内网地址在那里被硬拦下来，模型说什么都没用。所有处置动作都走 whitelist 校验 + 高危动作强制人工审批 + 全量写审计，这三层都在代码里，不在提示词里。',
            links: [{ t: '在线 Demo 里问', u: '/labs/' }]
        },
        {
            q: '技术栈是什么？',
            keywords: ['技术栈', '用什么', '框架', '语言', '版本', 'spring', 'java', '架构'],
            a: '后端 Spring Boot 3.2 + Spring AI / Spring AI Alibaba；RAG 用 text-embedding-v4（1024 维）；多 Agent 编排是自己写的调度层 + Tool Calling + ReAct；流式输出走 SSE；向量存储做了 VectorStoreGateway 抽象，默认内存实现（免部署），可切 Milvus；导出 PDF 用 OpenPDF；部署是 Docker + Docker Compose，前端是原生 JS（无构建步骤）。',
            links: [{ t: '项目页', u: '/projects/' }]
        },
        {
            q: '为什么自研向量存储抽象，不直接用 Milvus？',
            keywords: ['向量', 'milvus', '抽象', '存储', 'rag', '检索', 'embedding', '为什么不用'],
            a: '两个原因。一是部署成本：Milvus 要额外一套服务，2G 内存的机器上跑不动，而内存实现配合文件持久化就够用 —— 318 条向量、4.4 MB 的 JSON，启动直接加载。二是避免耦合：如果业务代码直接调 Milvus 的 SDK，以后想换 pgvector、想换云厂商的托管向量库，就要改一大片。抽一层 VectorStoreGateway 之后，切换只是改一个配置项。',
            links: []
        },
        {
            q: '多 Agent 是怎么协作的？',
            keywords: ['多agent', 'agent', '智能体', '协作', 'planner', '调度', '研判', '取证', 'responder', '协同'],
            a: '一个调度层先把问题分类，判给对应角色的专职智能体。目前有四类：PLANNER（调度，判定任务类型）、ANALYST（研判分析，查知识库）、FORENSICS（取证，拉告警和日志）、RESPONDER（处置，执行动作）。每个专职智能体有自己的一组工具，通过 Tool Calling 拿数据，最后汇总成「结论 + 证据 + 处置结果」。关键在于职责分离：研判的不管处置，处置的不能自己决定要不要处置。',
            links: []
        },
        {
            q: '告警聚合去重怎么做的？',
            keywords: ['告警', '聚合', '去重', '降噪', '风暴', '关联', '重复'],
            a: '三个维度一起用：同一源 IP + 时间窗（默认 5 分钟，可配）+ 同类告警，合成一条。单独用任何一个都不行 —— 只用 IP 会把同一台机器上的不同类型攻击混在一起；只用时间会把全网的攻击混在一起；只用类型会把不同攻击源合并。聚合行会带一个 ×N 徽标、时间窗范围、涉及资产，并且能下钻看原始明细。API 默认返回聚合结果，同时给出 rawTotal 和 aggregatedTotal 两个计数，加 ?raw=true 可以看原始数据。',
            links: []
        },
        {
            q: '误报率是多少？怎么测的？',
            keywords: ['误报', '漏报', '评测', '准确率', '红队', '测试', '指标', '效果', '多准'],
            a: '评测集是 19 个用例：11 条攻击用例 + 8 条正常流量用例（还有 2 条需要真实 Key 的标记为 SKIPPED）。为什么要放正常流量？因为只测攻击成功率会得到一个「宁可错杀」的系统 —— 什么都拦的系统攻击成功率是 0，但完全没法用。所以绕过率和误报率必须是两个独立维度，分开看。具体数值要跑一遍评测才有，评测框架会输出攻击成功率、绕过率、误报率、平均耗时和 Token 成本。',
            links: []
        },
        {
            q: '做过安全审计吗？发现了什么？',
            keywords: ['审计', '漏洞', '加固', '安全测试', '发现了', '修复', '渗透', '自查'],
            a: '做过。切入角度按风险排序：输入校验、鉴权覆盖、跨域配置、会话管理、错误信息泄露、依赖与配置。修完之后补了三样东西：可复现的 PoC 脚本、对应的回归测试、以及启动期的凭据校验（CredentialGuard，弱口令直接拒绝启动，fail-closed）。审计的收获不是修了几个洞，而是意识到「AI 生成的代码功能能跑，但边界条件和异常路径常常是空的」—— 所以检查不能交给 AI 自己判断。',
            links: []
        },
        {
            q: '这个项目有什么局限？没做完的部分？',
            keywords: ['局限', '不足', '缺', '没做', '缺点', '问题', '待改进', '下一步', 'todo'],
            a: '说几个实在的：① 用的是 MOCK 告警和日志数据，没在真实 SOC 环境验证过；② 评测集只有 19 例，覆盖不了真实攻击面；③ 多 Agent 的调度目前偏规则，复杂场景的泛化能力有限；④ 测试覆盖不完整；⑤ 20 小时的周投入下，很多想法只做了一半。这些我都写在项目页里，不藏着。',
            links: [{ t: '项目页', u: '/projects/' }]
        },
        {
            q: '怎么部署的？成本多少？',
            keywords: ['部署', '上线', '服务器', 'docker', '成本', '多少钱', '运维', '阿里云'],
            a: 'Docker 多阶段构建：构建阶段装 Maven 依赖并打包，运行阶段用 JRE + 中文字体（导出 PDF 需要），非 root 用户运行。镜像 867 MB，容器实际占用 251~384 MB 内存。跑在阿里云 2 核 2G 上，加 2G Swap 保底。对外用 Cloudflare 隧道，所以服务器不用暴露任何入站端口，只监听 127.0.0.1。成本主要是百炼 API 调用，量小的话每月几块钱。',
            links: []
        },
        {
            q: '你在哪里用到了 AI？',
            keywords: ['ai', '大模型', '怎么用', '使用', 'llm', '人工智能'],
            a: '分两层。产品层：SecAgent 本身就是 AI 应用 —— RAG 检索增强、多 Agent 编排、Tool Calling，让模型去读知识库、拉告警、给研判结论。工程层：这个项目的代码主要由 AI 生成，我负责需求、方案取舍和验证。第二层里我学到的最重要一件事是：AI 生成的代码「能跑」和「能用」之间差着输入校验、异常处理、权限检查这一整套，而这些恰恰是 AI 最容易漏掉的。',
            links: []
        },
        {
            q: '没有真实攻击数据怎么证明有用？',
            keywords: ['真实', '数据', '证明', '有效', '验证', 'mock', '假数据'],
            a: '现在是没法充分证明的，这也是最大的短板。计划是架一个低交互蜜罐（Cowrie）收集真实攻击数据，用真实数据重跑评测。但要说清楚：低交互蜜罐本身也有风险，必须做出口流量限制、跟其他服务隔离，不能变成攻击者的跳板。这件事排在在线 Demo 之后。',
            links: []
        }
    ];

    /* ---------------- 匹配打分 ---------------- */

    // 极简中文分词：没有词库，就用「问句里是否出现关键词」来打分。
    // 命中的关键词越长，权重越高（"向量库" 比 "库" 更有信息量）。
    function score(question, item) {
        var s = 0;
        var q = question.toLowerCase();
        item.keywords.forEach(function (k) {
            if (q.indexOf(k.toLowerCase()) !== -1) {
                s += k.length * k.length;   // 长度平方，长词权重明显更高
            }
        });
        return s;
    }

    function search(question) {
        var q = (question || '').trim();
        if (!q) return [];

        var scored = KB.map(function (item) {
            return { item: item, s: score(q, item) };
        }).filter(function (x) { return x.s > 0; });

        scored.sort(function (a, b) { return b.s - a.s; });

        // 分数太低就当作没匹配上，避免答非所问
        if (!scored.length || scored[0].s < 4) return [];
        return scored.slice(0, 3).map(function (x) { return x.item; });
    }

    /* ---------------- DOM ---------------- */

    function el(tag, cls, text) {
        var n = document.createElement(tag);
        if (cls) n.className = cls;
        if (text != null) n.textContent = text;   // 始终 textContent
        return n;
    }

    function build() {
        var fab = el('button', 'guide-fab');
        fab.type = 'button';
        fab.setAttribute('aria-label', '项目速查');
        fab.appendChild(el('span', 'guide-fab-icon', '💬'));
        fab.appendChild(el('span', 'guide-fab-text', '项目速查'));

        var panel = el('div', 'guide-panel');
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-label', '项目速查');

        // 头部
        var head = el('div', 'guide-head');
        head.appendChild(el('div', 'guide-head-title', '项目速查'));
        var closeBtn = el('button', 'guide-close', '×');
        closeBtn.type = 'button';
        closeBtn.setAttribute('aria-label', '关闭');
        head.appendChild(closeBtn);
        panel.appendChild(head);

        var hint = el('div', 'guide-hint',
            '本地知识库匹配，不走大模型 —— 答案都是确定的事实，不会编。想追问可以跳在线 Demo。');
        panel.appendChild(hint);

        // 输入
        var input = el('input', 'guide-input');
        input.type = 'text';
        input.placeholder = '比如：护栏为什么不写在提示词里？';
        panel.appendChild(input);

        // 常见问题
        var chips = el('div', 'guide-chips');
        var POPULAR = [
            '这个项目解决什么问题',
            '为什么护栏写在代码里',
            '多 Agent 怎么协作',
            '误报率怎么测',
            '你负责哪部分',
            '有什么局限'
        ];
        POPULAR.forEach(function (t) {
            var c = el('button', 'guide-chip', t);
            c.type = 'button';
            c.addEventListener('click', function () {
                input.value = t;
                run();
            });
            chips.appendChild(c);
        });
        panel.appendChild(chips);

        var out = el('div', 'guide-out');
        panel.appendChild(out);

        // 底部：跳转到真 AI
        var foot = el('div', 'guide-foot');
        var a = el('a', 'guide-foot-link', '去在线 Demo 问真的大模型 →');
        a.href = '/labs/';
        foot.appendChild(a);
        panel.appendChild(foot);

        function run() {
            var q = input.value;
            out.textContent = '';
            var hits = search(q);

            if (!hits.length) {
                var empty = el('div', 'guide-empty');
                empty.appendChild(el('div', null, '本地知识库里没有匹配这一问。'));
                empty.appendChild(el('div', 'guide-empty-sub',
                    '试试上面那些常见问题，或者去在线 Demo 直接问系统本身。'));
                out.appendChild(empty);
                return;
            }

            hits.forEach(function (item) {
                var card = el('div', 'guide-card');
                card.appendChild(el('div', 'guide-card-q', item.q));
                card.appendChild(el('div', 'guide-card-a', item.a));
                if (item.links && item.links.length) {
                    var lk = el('div', 'guide-card-links');
                    item.links.forEach(function (l) {
                        var la = el('a', null, l.t + ' →');
                        la.href = l.u;
                        lk.appendChild(la);
                    });
                    card.appendChild(lk);
                }
                out.appendChild(card);
            });
        }

        input.addEventListener('input', run);
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); run(); }
        });
        closeBtn.addEventListener('click', function () {
            document.body.classList.remove('guide-open');
        });
        fab.addEventListener('click', function () {
            document.body.classList.toggle('guide-open');
            if (document.body.classList.contains('guide-open')) {
                setTimeout(function () { input.focus(); }, 80);
            }
        });

        var wrap = el('div', 'guide-root');
        wrap.appendChild(fab);
        wrap.appendChild(panel);
        return wrap;
    }

    function init() {
        // 靶场页自己已经很长了，不叠加这个浮层
        if (/^\/labs\//.test(location.pathname)) return;
        var root = build();
        document.body.appendChild(root);
        // 先给几个默认结果，打开就有东西看
        var inp = root.querySelector('.guide-input');
        if (inp) {
            inp.value = '这个项目解决什么问题';
            inp.dispatchEvent(new Event('input'));
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
