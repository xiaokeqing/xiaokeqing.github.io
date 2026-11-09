# 状态 · 窗口 F · 后端功能与展示面规划

> 只由该窗口自己更新 ✓；格式见 `docs/窗口分工规范-20261015.md` §四

| 项 | 内容 |
|---|---|
| 负责 | 梳理 SecAgent 全部后端功能（只读取证）→ 判定 A/B/C 展示三类 → 给展示规划与派工单（T20/T21/T22） |
| 状态 | **已完成**（2026-10-15，只读盘点 + 两份文档；**未动站点代码、未动服务器配置、未 push** ✓） |
| 改了哪些文件 | ① `docs/后端功能与博客展示规划-20261015.md`（新建）② `docs/状态-F-后端功能展示.md`（本文件）—— 只此两个 ✗ |
| 验收证据 | **见下方"证据台账"**（命令原文摘要 + 文件路径 + 实测数字） |
| 下一步 | ① 站主拍板 U1（全局 `mask-ips` 是否翻转）② 规划侧把 T20/T21/T22 合并进任务清单主文件 ③ 窗口 G 出 UI 规格、窗口 C 落地 |
| 卡点 | **U1 卡住"是否要前端脱敏"这个决定性选择**：后端已有全局掩码开关但生产默认显示真实 IP，且存量页面（攻击流/攻击路径图/故事线 tag）已在渲染完整 IP ✗ ⇒ 需站主改口或明确豁免；F 只读，**不自行改配置** ✗。其余无卡点（盘点与规划已闭环） |

---

## 证据台账（每条都有命令输出/文件路径支撑）

### E1 · srv1 连通与运行面 [已实测]
```
ssh secagent-srv1 → iZbp1eix0bsjl4c6nhktorZ / root / Linux 5.10.134-19.8.al8.x86_64 / Thu Oct 15 08:18:13 PM CST 2026
docker ps：secagent Up 5 hours (healthy) 127.0.0.1:9900->9900/tcp ｜ wazuh-tunnel Up 2 days
systemd running（过滤命中）：secagent-applog-mirror / secagent-notify-relay / secagent-wazuh-agent-tunnel / wazuh-agent
crontab -l：30 3 * * * /bin/bash /root/backup.sh >> /var/log/secagent-backup.log 2>&1
（差异：本次未见 cloudflared 命中 → 标 [待核对]）
```

### E2 · 公开端点 12 个 + 鉴权面 [已实测]
```
kb 200/586 ｜ overview 200/1295 ｜ alerts 200/14378 ｜ latest 200/1422 ｜ honeypot 200/9082
audit 200/9533 ｜ geo 200/2981 ｜ webstats 200/4037 ｜ stories 200/5306 ｜ health 404/49
POST ask 200/5933（--data-binary 真问句）｜ POST tts 400/120 TEXT_NOT_ALLOWED（拒绝自由文本）
/api/admin 401 ｜ /api/internal 401 ｜ /api/v1 401 ｜ /api/v1/ 401 ｜ /api/health 200（无鉴权）｜ /api/public 404 ｜ / 200
新发现端点：GET /api/public/alerts/agg-71fcadeffefe → 200/1004（下钻）
            GET "/api/public/story?src=195.177.94.117" → 200/13589 ｜ 缺 src → 400 MISSING_SRC
```
> 探针脚本（本机临时目录，不入仓库）：`E:\DeepSeek1\work\_wF-probe\*.json`
> 注意：**所有响应 `ipDisclosure.masked=false`**，`stories[].srcIp`/`story.srcIp`/`honeypot.topSources[].key` 均为**完整公网 IP** [已实测]

### E3 · 数据面 / 脚本面 [已实测]
```
/opt/secagent/data/ 共 18 项（含提示词未列的）：tool-call-audit.json 280,611 ｜ tts-phrases.yml 605 ｜ tts-quota.json 110
  blocked-ips.json 3,226（list，10 条，keys=actor,auditId,createdAt,durationMinutes,expiresAt,id,ip,source,unblockMode,unblocked,unblockedAt）
  response-audit.json 15,314 ｜ response-audit.eval.json 1,850 ｜ kb-pending.json 1,892（list，3 条）
  model-quota{,-eval,-public}.json 30~31 ｜ notify-audit.jsonl 2,530,302 ｜ security-events.json 2,722（list，3 条）｜ vector-store.json 4,636,972
/opt/secagent/scripts/ 共 139 项（本次只登记：analyze-citations.mjs / citation_audit.py / public-ask-sample.py / eval-* / srv1-* / srv2-*）
```

### E4 · 运行 jar 里读到的关键事实 [已实测]
```
容器 /app/app.jar = 84,390,421 B (2026-10-14 03:03)；服务器源码树 PublicApiController.java = 66,729 B (2026-10-14 02:14)
源码树 grep webstats/stories/AttackStoryService → 0 命中；jar 内 → WebStatsAggregator* 8 类 + AttackStoryService + 常量池 /webstats /stories /story
  ⇒ 服务器源码树落后于运行 jar（后端线接手前必须先对齐）
jar 内 application.yml（公开面口径）：
  public-api.requests-per-minute=20 ｜ cache-seconds=15 ｜ expose-build-sha=true
  allowed-origins=xiaokeqing.cn,www,localhost:1313,127.0.0.1:1313
  ask.rpm=6 max-question-chars=600 deadline-ms=20000 ｜ kb.rpm=20 ｜ public-kb top-k=3 snippet-chars=300
  geo min-count=3 min-share-percent=1.0 top-ips=1000 ｜ story top-sources=50 max-events-per-stage=40 max-limit=20
  app.public.mask-ips=${APP_PUBLIC_MASK_IPS:false}   ← ★ 生产 = 显示真实 IP（红线冲突点）
  源码侧：PublicIpPolicy.java（唯一开关读取点，注释写明"站主 2026-10-14 拍板：显示真实来源 IP"）
          PublicIpMask.mask → IPv4 = A.B.***.***（内网/保留 → 「内部地址」）
```

### E5 · 博客现有版式与存量问题 [已实测，文件路径]
```
layouts/index.html                               656 行（主页 CRT 场景）
layouts/partials/xk-demo/shell-views.html        267 行（六屏 .view，含 stats pane 的 grid32 与被占位的故事线卡）
layouts/partials/xk-demo/shell-style.html        377 行（tokens：.mod/.card/.row/.chip/.grid32/.tl/.term 等）
layouts/partials/xk-demo/shell-script.html       758 行（含 PG_DEMO 本地假结果、xkQuota 已用真值、语音 bank.json 链）
layouts/partials/xk-demo/api-bind.html           409 行（JOBS：monitor=alerts,overview,honeypot,audit,geo,webstats,stories；REFRESH=40000）
_dev/gen-demo-pages.py                          1742 行（改 layouts 必同步）
存量完整 IP 渲染（api-bind.html）：第 223 行 bindGraphData、第 276 行 /stories tag、第 335 行 bindFeed
```

### E6 · 线上可达性 [已实测]
```
https://xiaokeqing.cn 六页全 200：/ 33,213 ｜ /alerts/ 77,559 ｜ /ai/ 77,189 ｜ /posts/ 79,046 ｜ /labs/ 77,364 ｜ /about/ 76,949
srv2 releases：site-20261014-234405 / site-20261014-235208 / site-20261015-112007 / site-20261015-181533
/opt/secagent/site → /opt/secagent/releases/site-20261015-181533
```

### E7 · GitHub Discussion #27 [已实测，抓取成功]
```
本机 web_fetch 只得外壳壳层（正文截断）✗ → 改从 srv1 curl 抓 252,541 B 全文后正则解析 → 拿到楼主帖 + maintainer 回复全文
URL：https://github.com/Code-Amadeus/Amadeus/discussions/27（302 → /orgs/Code-Amadeus/discussions/27）
结论：对我们的链路无直接可用补丁（我们不用 Browser Provider），但三条方法论可用（意图漂移要重新路由 / 短期 branch 只回交可验证证据 / 边界靠对照实验定义）
```

---

## 交付清单

| 产出 | 位置 | 状态 |
|---|---|---|
| ① 后端功能与博客展示规划 | `docs/后端功能与博客展示规划-20261015.md` | ✅ 已写（含功能清单 / A-B-C 判定 / 三块重点设计 / 派工单 T20~T22 / 未决 7 条 / Discussion #27 摘要 / 证据索引） |
| ② 本状态文件 | `docs/状态-F-后端功能展示.md` | ✅ 已写 |
| ③ "建议新增任务 T20/T21/T22"一段话 | 已回报给规划侧（由规划侧合并进任务清单主文件 ✗ F 不改） | ✅ |
| 站点代码 / 服务器配置 / 发布 | — | ✗ 一律未动（符合纪律） |
