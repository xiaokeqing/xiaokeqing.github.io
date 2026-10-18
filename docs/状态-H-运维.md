# 状态 · 窗口 H · 服务器与运维（T11）

> 只由该窗口自己更新 ✓；格式见 `docs/窗口分工规范-20261015.md` §四

| 项 | 内容 |
|---|---|
| 负责 | **T11 服务器与运维**（4 个子项）：① 证书到期 21/7/1 三级告警 ② 站点可用性外部探测（每 5 分钟）③ 配置类备份 + 恢复演练 ④ 备案推进材料清单 |
| 状态 | **已完成**（2026-10-15 20:30~20:45；**服务器只做加法** ✓，**未改** nginx/证书/容器/DNS/防火墙 ✗，**未 push** ✗） |
| 改了哪些文件 | ① `docs/运维-T11-证书告警与可用性探测-20261015.md`（新建）② `docs/运维-T11-备份恢复演练-20261015.md`（新建）③ `docs/运维-T11-备案材料清单-20261015.md`（新建）④ `docs/状态-H-运维.md`（本文件）—— 仓内只此 4 个 ✗ |
| 服务器侧新增（全部可一条命令回滚） | srv2：`/opt/secagent/scripts/srv2-cert-expiry-alert.sh`、`/opt/secagent/scripts/srv2-site-config-backup.sh`、`secagent-cert-expiry.{service,timer}`、`secagent-site-config-backup.{service,timer}`、`/var/backups/secagent-site-config/`（备份产物）；srv1：`/opt/secagent/scripts/srv1-site-probe.sh`、`secagent-site-probe.{service,timer}`、`/var/lib/secagent/site-probe/`、`/var/log/secagent-site-probe.log` |
| 验收证据 | 见下方「证据台账 E1~E6」；原始输出留档 `E:\DeepSeek1\work\_t11\evidence\01~14-*.txt`（仓库外） |
| 下一步 | ① 规划侧把 §11 变更日志行补进 MasterPlan（本窗口**不改活文档** ✗，建议行见回报）② 站主拍板两件事：**备案材料清单 §3.2 的 CF↔灰云切换口径**、**配置备份要不要异地一份（需新增 srv2→srv1 只读密钥）** ③ T11 在 §4b 的总表里可从"未开始"改为"已完成" |
| 卡点 | **无阻塞**。两个需要拍板的点已写成清单等决策（不是卡住，是分工：DNS/密钥变更超出"只做加法"的授权范围 ✗） |

---

## 证据台账（每条都有命令原文/日志/实测数字支撑）

### E1 · ① 证书告警链路（srv2，2026-10-15 20:34）
```
证书现状 [已实测]：到期 Jan 12 13:08:05 2027 GMT（剩 89 天）｜签发者 CN=YR2(LE)｜rsaEncryption
                  ｜SAN 四名 xiaokeqing.cn/www/direct/static ｜对外证书 /etc/ssl/secagent/site-fullchain.pem 同样剩 89 天
                  ｜certbot.timer = active
三级阈值 [已实测 --dry-run]：--test 20 → MEDIUM ｜ --test 6 → HIGH ｜ --test 0 → CRITICAL ｜ 无证书文件 → CRITICAL
真实告警 [已实测]：sudo bash … --test 6 → notify.sh「已发送（HTTP 200）」
        notify.log: 2026-10-15 20:34:44 [HIGH] 【演练】[证书] LE 证书到期提醒：剩 6 天（HIGH）→ open.feishu.cn/…/<masked>
systemd 巡检 [已实测]：systemctl start secagent-cert-expiry.service → level=OK days=89 → INFO 回落通知 → 已发送（HTTP 200）
定时器 [已实测]：NEXT Fri 2026-10-16 09:40:58 CST（每日 09:40，排在 certbot 约 09:08 之后）
```

### E2 · ② 站点探测链路（srv1，2026-10-15 20:35~20:40）
```
探测判据：HTTP 200 + 体积≥10000B + <title>含 xiaokeqing + (charCanvas 或 crt-clip) + 总耗时≤15s；单 URL 连败 3 次即 HIGH
正常轮 [已实测]：https://xiaokeqing.cn/ 200 / 33,213 B / 1.30~3.16s；https://www.xiaokeqing.cn/ 200 / 33,213 B / 1.75~4.64s
失败注入 [已实测]：--self-test（.invalid 保留域）→ code=000 → HIGH 告警 → notify.sh HTTP 200
        notify.log: [HIGH] 【演练·自检注入】站点不可用：https://t11-selftest.invalid/ → http://172.20.0.1:8899/notify
        relay journal: notify seq=706 high=False feishu=sent mail=skipped（邮件通道本就关闭）
定时器 [已实测]：secagent-site-probe.timer enabled，OnCalendar=*:0/5，systemd 触发轮次记录见 E5
流量代价 [推算，基数实测]：33,213 B × 2 URL × 288 次/天 ≈ 18.2 MiB/天 ≈ 0.53 GiB/月（对照站点红线 150 GB/月 = 0.36%）
```

### E3 · ③ 现有备份范围（srv1/srv2，只读）
```
srv1 cron [已实测]：30 3 * * * /bin/bash /root/backup.sh >> /var/log/secagent-backup.log（= /opt/secagent/scripts/backup.sh，md5 20c64bc7…）
        backup.sh --list → 2 份（20261011-122935 / 20261011-113452），合计 3.4M
srv1 异地数据备份 [已实测]：srv1-data-backup.timer 每天 03:30 → srv2:/opt/secagent-backup（6 份，11M）
        最新 20261015-033001 = 1,861,424 B，sha256 3fa24817…f41bac，恢复抽测 13/13 逐字节一致
两台 config-snapshot.sh [已实测]：cron 10 4 * * 0（周日）→ /var/backups/secagent-config；srv2 包 3,863,001 B，--drill 17 条全 OK
空白 [已实测]：/etc/nginx、/etc/systemd/system 站点单元、/etc/letsencrypt、/opt/secagent/scripts 均不在上述任何一份里 ✗
```

### E4 · ③ 新增配置备份 + 恢复演练（srv2，2026-10-15 20:35~20:36）
```
打包 [已实测]：98 个文件 → /var/backups/secagent-site-config/VM-0-10-ubuntu-site-config-20261015-203533.tar.gz
        （123,383 B，chmod 600，耗时 0.18s；systemd 触发那次 0.58s）+ 同名 .sha256
演练 [已实测]：--drill → 98/98 sha256 通过 ｜ 7 项关键文件齐（nginx.conf / xk-site-locations.conf /
        secagent-static.service / fullchain / privkey / renewal/xk-site.conf / srv2-site-receive.sh）
        ｜ 证书 CN=xiaokeqing.cn notAfter=Jan 12 13:08:05 2027 GMT ｜ 证书与私钥公钥配对 OK（sha256:3e7b63ce…）
        ｜ 包自身 sha256 OK（24b55ff2…）｜ **PASS ｜ 耗时 0.05s ｜ 124K**
定时器 [已实测]：NEXT Fri 2026-10-16 03:52:12 CST（每日 03:50）
未跑 nginx -t（刻意）：项目陷阱「root 跑 nginx -t 会生成 root 属主日志 ⇒ 降权服务起不来」，改用只读等价校验 ✓
```

### E5 · 无人干预运行（关键：证明"加了会自己跑"）
```
srv1 secagent-site-probe.timer：systemd 按 5 分钟节拍自动触发，20:40 那轮（无人工干预）实测
        journal: 20:40:18 Starting → 20:40:20 apex code=200/33,213B/2.02s → 20:40:24 www code=200/33,213B/3.06s → Succeeded.
        下一轮 NEXT 20:45:14 已排定；`systemctl is-enabled` = enabled（重启后仍在）
srv2 secagent-cert-expiry.timer（enabled）/ secagent-site-config-backup.timer（enabled）：
        NEXT 分别为 2026-10-16 09:40:58 / 03:52:12
两台机器磁盘 [已实测]：srv1 40G 用 45%（余 21G）｜ srv2 40G 用 58%（余 17G）——新增备份约 120KB/份 ×14 ≈ 1.7MB，可忽略
```

### E6 · ④ 备案证据（可提交材料）
```
访客视角拦截 [已实测，站主本机 20:31]：http://{公网IP-腾讯云}/ + Host: xiaokeqing.cn → HTTP/1.1 302 OK
        Location: https://dnspod.qcloud.com/static/webblock.html?d=xiaokeqing.cn ；443 → curl (35) Connection was reset
服务器视角对照 [已实测]：srv1 → 同 IP/同 Host：80 返回 nginx 301、443 --resolve 返回 200/33,213 B；
        对照假 Host 也 301 ⇒ srv1/srv2 侧不复现拦截（只留现象，机制未定论 ✗ 不编解释）
实例事实 [已实测，腾讯云元数据]：instance-id ins-mawyt7d7 ｜ instance-name lh-1503609860-lhins-2zqpnb2c（lh- = Lighthouse 轻量）
        ｜ placement/region ap-shanghai ｜ public-ipv4 {公网IP-腾讯云} ｜ local-ipv4 10.0.0.10 ｜ meta-data/eipv4 → 404（未绑 EIP）
官方要求逐条对照 + 咨询问题清单：见 docs/运维-T11-备案材料清单-20261015.md §2/§3
```
