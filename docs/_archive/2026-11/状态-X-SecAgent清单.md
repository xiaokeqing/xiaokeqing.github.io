# 状态 · 窗口 X · SecAgent 未添加功能清单（2026-10-15）

> 格式对齐 `docs/窗口分工规范-20261015.md` §四（任务号 / 状态 / 改了哪些文件 / 验收证据 / 下一步）。

| 项 | 内容 |
|---|---|
| 任务号 | **X（一次性盘点件，未占 T 号）**：产出"SecAgent 还没添加上去的功能"权威清单 |
| 状态 | **已完成**（2026-10-16 00:05 CST 收工；**只写文档** ✓） |
| 改了哪些文件 | ① `docs/SecAgent未添加功能清单-20261015.md`（新建，99 行 / 23,783 B）② `docs/状态-X-SecAgent清单.md`（本文件）—— **仓内只此两个** ✗ |
| 服务器动作 | **只有只读** ✓：`ssh secagent-srv1` 的 `curl`（公开端点计时 + `/api/health` 状态码）、`docker logs | grep LLM-PROVIDER-SELFCHECK`、`docker ps`；**未改任何配置、未重启、未重建容器、未打印任何密钥字面值** ✗ |
| 验收证据 | 见下方「证据台账」E1~E4；清单正文每条带"文档名 + 章节/行号"出处 |
| 下一步 | ① 站主/规划侧按清单 §③ 批"先做三条"（T25 A 组 → 提示词语义分层 → T20 封禁榜）② 清单 §⑥ 的 6 条矛盾交规划侧订正（尤其 **③U1 结论已变** 与 **①模型时点**）③ T29 白名单按 F 的 12 端点收口（不是 L §2.7 的 8 个） |

---

## 证据台账（每条都有命令输出 / 文件路径支撑）

### E1 · 只读复核：端点计时 + health 状态 [已实测 2026-10-16 00:01 CST]
```
ssh secagent-srv1 'curl -sS -o /dev/null -m 12 -w %{http_code}:%{time_total}s:%{size_download}B ...'
alerts → 200 / 2.201412s / 8462 B（单次样本，含冷快照因素 ⇒ 根因未定，清单 §⑤-⑲）
geo    → 200 / 0.085072s / 3205 B
health → 200 / 0.001687s（**无鉴权仍 200**，正文含 embeddedGitCommit / 提交信息 / mock 开关 / documentVectors:318）
```
> 同批响应里 `ipDisclosure.masked=false`（全部端点）、`honeypot.total=10000` 且 `sampled=800`、`connections=267`、
> `stories.candidates=137` 且 10 条来源 `auditActions` **全为 0**、`audit.summary={blockTotal:10,blockActive:0,blockedByGuard:26,executedActions:20}`。

### E2 · 只读复核：当前生效的"大脑"（纠正 K 的时点口径）[已实测]
```
2026-10-15T21:54:39+08:00 LLM-PROVIDER-SELFCHECK provider=deepseek fallback=DISABLED
  deepseek{model=deepseek-chat,key=SET,available=true} | fallback=none{available=false}
  embedding{model=text-embedding-v4,key=SET} | outbound read=12000ms call=15000ms
docker ps：secagent Up 2 hours (healthy) ｜ wazuh-tunnel Up 2 days
⇒ K（20:33）记的 dashscope/qwen-plus 已被 21:54 的供应商切换取代；清单 §⑥-① 记录该矛盾
```

### E3 · 出处核对（本文只引用、不改动任何上游文档）
```
F  §2.1/§2.3/§2.5/§2.6/§3 A-C/§4.1~§4.4/§5 R1-R5/§7 U1-U7/§9
K  §0/§2.1~§2.4/§3/§4/§6/§7          L  §1/§2.1~§2.8/§3.1~§3.3/§4 A-G/§5/§6.1/§7/§10
T25 §12.1~§12.9    防复读 §一/§二/§三 G1-G6/§四/§五/§六
待办 §A（T1~T30/L1）+ §附录-5.1/5.3/5.4/5.5/5.7/5.10/5.13/5.14
另引用（复核矛盾用）：HANDOVER §6-6 · 运维-T11-备份恢复演练 第 181~195 行 · 服务器配置-详细版 Q7 · 状态-P-UI批 第 13 行
```

### E4 · 纪律自证
```
✗ 未改服务器任何文件/配置（`/opt/secagent/**` 一个字都没动）、未重启、未重建容器、未 docker cp/解压
✗ 未发任何 /api/public/ask 或 /api/chat 请求、未消耗任何模型额度（只打只读 GET，均带 `-o /dev/null`）
✗ 未打印任何密钥 / Token / 口令字面值（自检行只有 key=SET/MISSING；curl 输出未落盘到仓库）
✗ 未 commit、未 push（工作区其他窗口的在改文件一律未碰，只 `git add` 本件两个路径）
```

---

## 交付清单

| 产出 | 位置 | 状态 |
|---|---|---|
| ① 未添加功能清单（26 条 = A15 + B8 + C3） | `docs/SecAgent未添加功能清单-20261015.md` | ✅ 已写（② 表格 / ③ 性价比排序 / ④ 不做暂缓 / ⑤ 待核对 18 项 / ⑥ 矛盾 6 条 / ⑦ 出处索引） |
| ② 本状态文件 | `docs/状态-X-SecAgent清单.md` | ✅ 已写 |
| 代码 / 配置 / 发布 | — | ✗ 一律未动（符合纪律） |
