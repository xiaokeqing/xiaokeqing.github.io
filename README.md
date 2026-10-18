# xiaokeqing.cn · 安全观测站（Hugo 静态站）

## 1. 一句话定位

> 把真实公网攻击数据做成面试官 30 秒内能自己验证的第一入口。

本仓库只负责**站点这一侧**：Hugo 静态页 + 自研页面生成器 + 前端取数逻辑。数据全部来自后端只读接口 `/api/public/*`；后端与部署脚本在 [SecAgent](https://github.com/xiaokeqing/SecAgent)。

## 2. 架构图（双机：srv2 采集 → srv1 只读 API → Cloudflare → 静态站）

```text
[真实公网攻击源] 扫描 / 爆破 / Web 攻击 / 蜜罐交互
        │
        ▼
srv2 上海 · 采集面 ───────────────────────────────────────────
  nginx 18080 隧道入口 · 443 公网直连 / Wazuh Dashboard
  Wazuh 4.9.2（manager / indexer / dashboard）
  Suricata（eve.json）· Cowrie 2222 · Dionaea 445/1433/3306
  decoy 诱饵端口 21/23/6379/8080/8443/27017
  labnet（--internal，禁出网）7 台靶场，只映射 127.0.0.1:8081-8087
        │  同机文件 / 本地 socket，只读拉取
        ▼
srv1 杭州 · 应用面 ───────────────────────────────────────────
  Spring Boot `secagent`，容器仅监听 127.0.0.1:9900
  /api/public/*（16 个映射）只读 + 应用内快照缓存（max-age=45s）
  规则判定 → 处置 → 真实防火墙落盘 + 审计留痕（模型只解释不拍板）
        │  HTTPS：demo.xiaokeqing.cn 是唯一 API 出口
        ▼
Cloudflare Tunnel / CDN
        ├──────────────► xiaokeqing.cn       ← 本仓库：Hugo 静态站 + 生成器 + 前端
        └──────────────► demo.xiaokeqing.cn  ← 只读 JSON API
```

## 3. 五个实测数字（全部来自 `docs/Amadeus-项目总文档-20261017.md`）

| # | 指标 | 实测值 | 出处 |
|---|---|---|---|
| 1 | 告警量级 | 24h 被分析告警 **78,130** 条（含源 IP 75,127；已定位 30,263；排除本机 44,003、内网 861） | §3 实测数字 |
| 2 | 后端单元测试 | **721** 例 / 0 失败 / 4 跳过（`mvn -o test`） | §19.2、§19.11 |
| 3 | 构建断言 | **42** 项（`scripts/assert-build.sh`，全过才允许发布） | §20.1 |
| 4 | 门禁 SSR 契约 | **9** 页（`_dev/check-ssr-contract.py`：home/monitor/notes/ai/test/what/lab/status/api） | §20.1 |
| 5 | 隔离靶场 | **7** 台（Pikachu / DVWA / Juice Shop / WebGoat / DVNA / DSVW + WebWolf） | §19.9 |

## 4. 在线地址与只读 API

| 入口 | 地址 | 说明 |
|---|---|---|
| 主页 | <https://xiaokeqing.cn/> | Canvas CRT + 竖排导航 + 开屏语音 |
| 监测中心 | <https://xiaokeqing.cn/alerts/> | 英雄数字、实时攻击流、威胁矩阵、TOP 来源、单源时间线 |
| 公开端点清单 | <https://xiaokeqing.cn/api/> | 人读的端点表 + 三条 curl（不是 JSON） |
| 状态页 | <https://xiaokeqing.cn/status/> | 8 个端点逐个 PASS/FAIL、构建 SHA、耗时、一致性 CI 卡 |
| API 基址 | <https://demo.xiaokeqing.cn> | 唯一数据出口，只读 |

```bash
curl -s https://demo.xiaokeqing.cn/api/health | head -c 300          # 健康探针 + buildSha
curl -s https://demo.xiaokeqing.cn/api/public/home.js | head -c 400  # 首屏聚合（alerts+geo+honeypot+audit+health）
curl -s https://demo.xiaokeqing.cn/api/public/audit | head -c 400    # 处置审计
curl -s -o /dev/null -w '%{http_code}\n' https://lab.xiaokeqing.cn/  # 应返回 404：靶场已撤出公网
```

写之前先看清三条口径（做不到的不写）：

- **靶场不对公网开放**：Cloudflare ingress 已删，入口返回 404；进法只有 SSH 隧道到 `127.0.0.1:8081–8087`（`scripts/打开靶场.cmd`）。
- **AI 只解释不拍板**：问答不取证、检索不到直接拒答；高危处置必须人工审批。
- **取不到就写「读不到 / 未接入」**：不补样例值，不把 mock 当真实数据（例：蜜罐 `commandsAvailable=false` 就如实显示未接入）。

## 5. 本地复现（照抄即可）

```bash
git clone https://github.com/xiaokeqing/xiaokeqing.github.io.git && cd xiaokeqing.github.io
hugo version                                  # 需 extended；CI 钉 0.167.0

python -X utf8 _dev/gen-demo-pages.py         # 生成 layouts/partials 与内容页（生成物源头在这里）
hugo --gc --minify --cleanDestinationDir
bash scripts/assert-build.sh                  # 42 项断言，全过才允许发布
python _dev/check-ssr-contract.py public      # SSR 契约 9 页
hugo server --bind 0.0.0.0 --port 1313        # 本地预览

# 只有站主会跑（需要 srv2 SSH）：site-<时间戳> → sha256 → 原子切换 → 失败可回滚
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/publish-site-to-srv2.ps1
```

其它现成脚本：`scripts/consistency-check.sh`（srv2 上 15 项一致性巡检，timer 每 15 分钟）、
`scripts/weekly-report.py`（战报 md/html + 目录页）、`scripts/note-publish.ps1`（发笔记）。
`_dev/` 只按白名单入库（生成器 + 两道门禁 + 素材产线），截图与探针不进仓库。
`.github/workflows/deploy.yml` 在 gh-pages 上**只发 `redirect-site/` 跳转页**，不整站镜像。

## 6. 技术栈

![Hugo](https://img.shields.io/badge/Hugo-extended%200.167.0-FF4088?logo=hugo&logoColor=white)
![Vanilla JS](https://img.shields.io/badge/frontend-vanilla%20JS-F7DF1E?logo=javascript&logoColor=black)
![Cloudflare](https://img.shields.io/badge/Cloudflare-Tunnel%20%2B%20CDN-F38020?logo=cloudflare&logoColor=white)
![Nginx](https://img.shields.io/badge/nginx-reverse%20proxy-009639?logo=nginx&logoColor=white)
![No third-party assets](https://img.shields.io/badge/third--party%20JS%2Ffont%2FCDN-0-brightgreen)
![Tests](https://img.shields.io/badge/build%20assertions-42%2F42-brightgreen)
