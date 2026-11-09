# 状态 · 窗口 V · 飞书通知接入（把「通知站主」接成一条命令）

> 只由该窗口自己更新 ✓；格式见 `docs/窗口分工规范-20261015.md` §四、`docs/项目总体规划-MasterPlan-20261015.md` §13

| 项 | 内容 |
|---|---|
| 负责 | 服务器侧**通知出口**接入：摸清 `notify.sh` 真实契约 → 接通「一行命令 → 飞书」→ 出可复用命令与排查文档（srv1 为主，只读为纪律） |
| 任务号 | V（通知接入） |
| 状态 | **已完成** ✓（通道已接、已实测到达；srv1 新增 1 支脚本，既有脚本/.env 零改动） |
| 产出 | `docs/飞书通知接入-20261015.md`（主文档：机制/契约/一行命令/证据/排查/安全）＋ `docs/状态-V-通知接入.md`（本文件）＋ 服务端 `srv1:/opt/secagent/scripts/notify-dsh.sh`（新文件，base64 封装，**无密钥**） |
| 改了哪些文件 | 仓库：**仅新增**上述 2 份 docs（已 `git add`，**未 commit / 未 push** ✗）。服务器：**仅新增** `/opt/secagent/scripts/notify-dsh.sh`（2572 B，0755，sha256 `30df46ed…`）；**既有脚本 0 改动、`.env` 0 改动、未 restart 任何服务** ✓ |
| 验收证据 | ① 调用契约：`bash /opt/secagent/scripts/notify.sh --help`（头部注释生成）+ 第 72–101 行参数解析 ⇒ `<级别> <标题> [正文] [--key/--cooldown/--config/--force/--dry-run]`，退出码 0/2/3/4/5/6 ✓<br>② **真发两条**并落到飞书：`notify.log` `23:35:50 已发送 HTTP 200：[LOW] [DSH] 飞书通知通道测试`、`23:38:55 已发送 HTTP 200：[LOW] [DSH] 通知通道测试·封装命令验证`（`notify_exit=0`）✓<br>③ 中继回执：`23:35:50 notify seq=750 high=False feishu=sent`、`23:38:55 notify seq=751 high=False feishu=sent`（`send_feishu()` 仅在飞书 API `code==0` 时记 `sent`）✓<br>④ 根因铁证：`23:32:54 [notify.sh] 夜间静默（22:00-07:00，mode=high-only）：INFO「DSH通知测试」按阈值压制 —— 没发出去`（退出码 6）✓<br>⑤ 纠偏铁证：发送前后 `data/notify-audit.jsonl` **9156 → 9156 行、mtime 未变**（末条仍是真实 `HIGH_ALERT/outcome=MERGED`）⇒ 手工 notify.sh **不写**该文件 ✓<br>⑥ 脱敏：两份日志中 `open.feishu.cn` **0 次**；`notify.sh` 全文 0 处 `feishu`；`.env` 为 `600 root` ✓ |
| 卡点 | **无技术卡点** ✓。唯一限制：`LOW/MEDIUM/INFO` 在 22:00–07:00（`NOTIFY_NIGHT_QUIET_MODE=high-only`）会被压制 ⇒ 手工发必须带 `--force`，或直接用 `HIGH`。另：**srv2 未做端到端验证**（srv2 无 relay 服务）⇒ 统一用 srv1 ✗ |
| 下一步 | ① 站主直接用 `ssh secagent-srv1 'bash /opt/secagent/scripts/notify.sh HIGH \"[DSH] 任务完成\" \"正文\" --force'`（PS 5.1 内层引号写 `\"`）✓<br>② 正文含引号/`$`/换行 ⇒ 用主文档 §4.2 的 base64 封装 ✓<br>③ 是否把 `notify-dsh.sh` 入 `/opt/secagent` 仓库：`git -C /opt/secagent add scripts/notify-dsh.sh`（**本包未做**，交有写权限窗口）✗<br>④ MasterPlan §11 那一行见主文档 §9（**本包不代写活文档**）✗ |

## 备注

- 站主口径："每当完成一个重要任务或取得重大突破时通知他" ⇒ 建议**固定 `HIGH` ＋ `--force`**（`HIGH` 穿夜间静默，`--force` 同时绕过 600s 冷却）✓。
- `--dry-run` 可零副作用验证载荷（本次用它验过中文 UTF-8 无损）✓。
- 本次**只读**服务器，例外仅两处：发测试消息（2 条）＋ 新增 `/opt/secagent/scripts/notify-dsh.sh` 一支新文件 ✓。
