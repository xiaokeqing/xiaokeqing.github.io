# HANDOVER · 接手手册（给下一个 AI / 另一个人）

> 这份是**唯一入口**：先读它（5 分钟），再按 §2 的索引读细节文档。
> 项目：个人安全实验室博客 `xiaokeqing.cn`（Hugo + 原生 HTML/CSS/JS），核心卖点是
> **实拍书桌 + CRT 屏幕里活着的角色（帧/视频动画 + 桐莉栖语音 + 口型）**，以及真实的攻击监测数据。

---

## 0. 三十秒现状（2026-10-14 夜）

```
✅ 已上线（服务 srv2 直连，不经 Cloudflare）：
   · 六页 = 设计原型文档的**整份照搬**：/ · /alerts/ · /posts/ · /labs/ · /about/ · /ai/
   · 主域名 xiaokeqing.cn / www 已是 A → 43.143.114.79（灰云，直连）；LE 4-SAN 证书 + 自动续期
   · 实测吞吐：直连 271~338 KB/s（对照 GitHub Pages 9.6~17、CF 隧道 0~10.7 KB/s）
⏳ 进行中：① 语音（GPT-SoVITS 真音色第一句）② 六页原型缺陷修复（假数字/横幅/叠行/暗块）③ 视频接入
❌ 未做：把"真状态机 + 真视频 + 真语音 + 口型"接进六页；P1 尾巴；服务端历史待办
```

---

## 1. 环境与路径（含本机特有的坑）

```
代码仓：F:\7AAA\AI\blog            （Hugo 站点；main 分支；push 会触发 GitHub Actions → gh-pages）
构建产物：同仓 public/             （Hugo 生成，git 忽略）
Hugo：C:\Users\T\AppData\Local\Microsoft\WinGet\Packages\Hugo.Hugo.Extended_...\hugo.exe（0.167 extended）
Python：C:\Users\T\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe
素材暂存：E:\DeepSeek1\work\_kurisu-full\（旧包素材/工具）｜_kurisu-017\（0.17.0α 清点+视频管线）
Amadeus 源码 clone：E:\DeepSeek1\work\_amadeus-src（素材包安装到这里，**绝不装进博客仓**）
便携 ffmpeg：E:\DeepSeek1\work\_kurisu-017\video-pipeline\tools\ffmpeg-master-latest-win64-gpl\
服务器：ssh secagent-srv1（阿里云，检测+公开 API）｜ssh secagent-srv2（腾讯云，蜜罐+静态托管）
本机坑：
  · PowerShell **5.1**：没有三元运算符；`if` 不能当表达式；字符串里别套单引号 ✗
  · 用 edit/write 工具改 **.ps1 会丢 UTF-8 BOM** → PS5.1 按 GBK 读会报假语法错 ⇒ 改完必须补 BOM
  · 本机直连本站 443 会**被中间设备按 SNI 重置**（SNI 含 xiaokeqing.cn 就 reset；换 x.cn 就 200）✗
    → 验证线上请走 srv1（`ssh secagent-srv1 ... curl -k -H "Host: xiaokeqing.cn" https://43.143.114.79/`）
  · Clash Verge：**TUN 关、规则模式**；若浏览器打不开本站，切「全局」或加规则 `DOMAIN-SUFFIX,xiaokeqing.cn,<代理组>`
```

---

## 2. 权威文档索引（按需读，别一次全读）

| 文档 | 一句话 |
|---|---|
| `docs/角色动画与语音-实现全貌与服务器配置-给外部AI.md` | **最全**：目标与两次纠偏、动画机制（层序/落位公式/状态机/口型）、语音三层、两台服务器完整配置、事故清单、未决项 |
| `docs/方案v2-按0.17.0α素材包重做资产与渲染.md` | 视频化方案 + §9 实测补充（h268 VP9+alpha 9.54MB 替代 71MB；B 路线 vs B3 的取舍） |
| `docs/ops-博客托管切换与回滚.md` | 域名切换时间线、DNS 原文、**三档回滚**、四笔账（流量红线 ≤150GB/月等） |
| `docs/交接-六页整份搬demo-20261014.md` | 六页怎么搬的、与 demo 的全部差异、**demo 自身三处缺陷**、门禁改动、下游后果 |
| `docs/动画与语音实现规格-给外部AI.md` + `docs/评审-动画与语音实现规格-20261014.md` | 机制规格与外部评审意见（含"闭嘴补丁/包络契约/autoplay 门控"等要求） |
| `docs/素材包0.17.0α-优化评估-给外部AI.md` + `docs/评审-素材包0.17.0α评估-20261014.md` | 素材包清点与优化评估 + 外部评审（B1/B2/B3 三条视频路线） |
| `docs/amadeus-research/HOW-IT-WORKS.md` | 源码级机制研究（1150 行，含 file:line）—— 复刻 Amadeus 的依据 |
| `deploy/srv2-site/README.md` | srv2 静态托管的落地物说明（nginx/服务/发布/回滚） |
| `E:\DeepSeek1\work\_kurisu-017\{INVENTORY.md, VIDEO-OPTIMIZATION.md, video-assets\SIZES.md}` | 素材包清点、视频管线报告与逐文件体积/画质表 |
| `E:\DeepSeek1\work\断点状态-20261014-*.md` 与 `E:\DeepSeek1\work\push-gate.ps1` | 我的断点笔记 + **上线闸门脚本**（9 组检查） |
| `docs/demo-主页.html`（222 行，自包含） | **主页的设计基准**：自带 style/标记/内联脚本（4 剪辑逐帧 / 开场硬切 idle / HUD 打字 / 原版落位公式） |
| `docs/demo-内容页外壳.html`（8 个 view） | **五页的设计基准**：作战室 OPS-ROOM 等；注意它自带三处缺陷（见 `docs/交接-六页整份搬demo-20261014.md`） |
| `docs/HANDOVER-接手手册-给下一个AI.md` | **就是本文**（唯一入口，0~12 节） |
| `docs/AI项目升级方案-20261015.md` | ★ **项目升格方案**：定位改写（AI 驱动的安全数字人）+ 现有 AI 成分 + 三个缺口（评测/数据闭环/AI 决策）+ 阶段任务 **T13 评测包 / T14 LLM 决策行为 / T15 语音闭环 / T16 项目说明书** + 指标看板 + 风险 + 插点 + 4 条待拍板 |
| `docs/交接-执行AI批-20261015.md` | **执行批交接原文**（13 项完成清单 / 6 条机制 / 5 个被拦住的 bug / 未决三项 / 安全轮换提醒）；摘要已并入任务清单 **§16** |
| `docs/项目总体规划-MasterPlan-20261015.md` | ★★ **总纲（先读这份）**：一页速览 / 目标与口径 / 现状 / 已完成 / 未完成 T1~T12 / 执行顺序 / 硬前提红线 / 关键数字 / 风险 / 文档地图 / 第一小时 |
| `docs/总账-决策与事实台账-20261015.md` | ★ **散落信息的收口**：用户口径/决策、实测数字台账、我方已纠正的 12 处错判、12 条事故教训、流程与角色、7 件未决、资产路径总表 |
| `docs/待办-施工任务清单-给执行AI.md` | ★★ **执行入口**：T1~T11 逐条派工单（现象/证据/做法/验收/回滚/工时）+ 7 件待拍板 + 我与接手方的核验对照 |
| `docs/服务器配置-详细版-给外部AI.md` | ★ **服务器/托管详细版**（srv1+srv2 规格、7 容器、nginx 监听面、降权与限额、证书、防火墙、DNS/CF、发布链与三档回滚、流量与成本、监控缺口、单点风险与改进、10 个开放问题） |
| `docs/接线方案-动画与语音接入六页.md` | ★ **施工规格**：怎么把 状态机(38/88) + 视频(9.54MB) + 语音 + 口型 接进六页（三步、验收、feature flag 回退、10 条坑） |

---

## 3. 门禁、红线与发布链（最重要的一节）

```
三道门禁（都必须绿）：
  bash scripts/assert-build.sh ./public     # 资产 ≤80 MiB、零 0 字节资产、bg.jpg SHA256 不变、公开端点白名单、零第三方
  node _dev/gate-firstscreen.mjs            # 真浏览器逐页首屏 ≤1650KB（超预算 exit 1）
  python _dev/check-ssr-contract.py public  # 六页 data-xk-ssr + #xk-views
  （另：E:\DeepSeek1\work\push-gate.ps1 是我的一键闸门，可作交叉校验）

红线（违反即回滚）：
  · 零第三方请求（资源加载位站外 = 0）｜数字只来自真实接口，取不到写"读不到"，**不许留假数字**
  · CSS 一律容器前缀化（曾因整份搬入 `.view{display:none}` 白屏过一次 ✗）
  · 素材以**作者原始素材**为准：不许擅自降质/重编码（曾把字幕垫板 382KB→87KB 被要求撤回 ✗）
  · 一件事一个归属人；推前必须看本地产物 + 截图

★ 发布链（关键认知）：**push ≠ 上线** ✗
  push → GitHub Actions → gh-pages（只是备份/历史）
  真正上线要再跑：scripts/publish-site-to-srv2.ps1
    （本机 hugo 构建 → 校验 index.html 特征 → tar 上传 → srv2 端 verify_tree + 回环自检 + **原子 rename 切换**）
  回滚：① 秒级切回上一版 release ② 5 秒 killswitch off（退回只走隧道）③ 2 分钟 DNS 切回 Cloudflare+Pages
```

---

## 4. 口径（这个项目最容易搞错的地方）

```
用户要的是「**和作者想呈现的效果一样**」，不是"和 demo 文件逐字一样" ✗
  · demo 文件只是原型：它的演示数字、"主页 DEMO…"横幅、攻击流叠行、CRT 暗块、
    /about/ 空白、五页 TypeError、/posts/ 卡片不可点 —— **都是原型缺陷，要修掉** ✗
  · 要保留的是"效果"：实拍书桌 + CRT 内景 + 她在其中（开场特写→拉远）、作战室 OPS-ROOM 版式、
    暗色玻璃质感、真实数据、她能动/能说
  · 验收 = 用户看图判断"像不像"，**不要用自定的像素差/体积百分比当门槛**（我犯过这个错 ✗）
```

---

## 5. 当前进行中的活（接手前先决定它们的去留）

```
① 语音真音色（子智能体）：GPT-SoVITS v3 本机批量。**台词必须是日语** ✗（参考音频是日语；用中文文本等于没用上她的音色 —— 我犯过这个错）；第一句已出（GPU，热态 3~4s/句，显存峰值 4030MiB @6GB ✓），正在改双语台词库（ja 送 TTS / zh 做字幕）→ 批量 60 句
   （loudnorm -16 LUFS / 裁静音+fade / m4a(AAC)+webm(Opus) / 包络**从最终编码文件**重算，平均 41.9KB/句）
   60 句台词库已写（线上 12 条逐字未改）；**first sentence 未出**
② 六页原型缺陷修复（子智能体）：删 DEMO 横幅 → 换真接口数据 → 修攻击流叠行 → 修 CRT 暗块
   → 再补 /about/ 空白、五页 TypeError、/posts/ 卡片真链接
③ 视频接入（未开工）：资产已产出 40 webm(8.76MB)+40 poster(0.78MB)=9.54MB，B 路线（透明 VP9+alpha）最优
   （B 路线 alpha MAE 0.189 vs B3 双拼 0.69~1.05；体积小 23%；播放端直接 drawImage）
⇒ 接手时请先 `list_agents` / 看它们在改哪些文件，**同一文件不要两个归属人** ✗
```

---

## 6. 未完成任务（优先级从高到低）

```
0) **执行入口 = `docs/待办-施工任务清单-给执行AI.md`（T1~T11 派工单，先做 T1/T2/T3）**
1) 把「真状态机（38 节点/88 边）+ 真视频（9.54MB B 路线）+ 真语音（60 句）+ 口型」接进六页
   （视觉保持现状，只加少量非视觉代码；阈值/回退/预载纪律见方案 v2 §9）
2) 语音收尾：第一句 → 60 句批量 → 替换 static/kurisu/voice/* + bank.json → 上线
3) 视频替换图集（71MB → 9.54MB，分辨率还翻倍）；旧 82MB 图集留作回退源
4) P1 尾巴：房间活动位（电脑前/趴桌睡/喝咖啡/站着想事）、中景眨眼（idle1）、情绪焊真实告警严重度、
   首访/回访分流、切回标签页打招呼、定时器/rAF 清理、favicon、skin 接"科技模式"
5) demo 三处缺陷补齐（/about/ 内容、五页 TypeError、/posts/ 卡片链接）
6) 服务端历史待办：Wazuh 盯 web 进程 · srv2 外部可用性探测（现为整站单点）· gh-pages 可用性验证 ·
   案例管理/playbooks · MTTD/MTTC · Trivy 分级 · ACR 陈旧镜像告警 · 管理员密码轮换 · 日志脱敏 · 恢复演练
7) 用户待决：① Fish Audio Key（让自由回答也出声；含"只接受服务端产出的文本"防刷与月费用熔断）
   ② 视频上线时点 ③ 是否把媒体转对象存储+CDN（流量/海外访客变多时）
```

---

## 7. 已知陷阱（踩过的，别再踩）

```
① 整份搬入 demo CSS → 全局 `.view{display:none}` → **全站白屏** ⇒ 必须容器前缀化
② root 跑 `nginx -t` 会生成 root 属主日志 → 服务降权后起不来 ⇒ 跑完必须修回 www-data/xksite
③ srv2 不能绑 `0.0.0.0:443`（127.0.0.1:443 被 wazuh.dashboard 占用）⇒ 绑 EIP 映射的 10.0.0.10:443
④ 两条线同时改 `nginx.conf` → 配置被覆盖 + ~30 秒 502 ⇒ 一件事一个归属人
⑤ 发布脚本有"index.html > 20KB"老断言 → 新主页只有 9.5KB 会被误判 ✗ ⇒ 已改成 >4KB（发布脚本与接收脚本两处）
⑥ 素材包 `clip.json` 的 `layout` 有 2 组写错（1027 vs 实际 1028）⇒ 一律以**实际码流尺寸**为准
⑦ staging 图集脚本的剪辑清单来自缓存 `recon.json` ⇒ 新增剪辑要先刷 recon，否则不进流水线
⑧ 本机直连本站被 SNI 重置（见 §1）⇒ 线上验证走 srv1
⑨ `.ps1` 丢 BOM 会假报语法错（见 §1）
⑩ 流量红线：srv2 是 300GB/月包，站点素材红线 **≤150GB/月**（日报+告警已接）；10MB 约为一次全量访问
```

---

## 8. 凭据与安全

```
· 密钥/口令**一律不进仓库、不写进文档、不贴聊天** ✗
· 本机文件（仓库外）：E:\DeepSeek1\work\.cf-token（当前那串**无效**，CF 返回 Invalid API Token ✗）、
  待建的 .fish-key（Fish Audio）
· ssh：ssh secagent-srv1 / secagent-srv2（密钥在本机 ~/.ssh/，git 推送用的是同一个）
· 若密钥曾被贴进聊天：用完请到对应平台 Revoke 重建 ✓
```

---

## 9. 建议的第一小时

```powershell
cd F:\7AAA\AI\blog ; git log --oneline -5 ; git status --short        # 看状态
git pull --ff-only                                                     # 同步
# 1) 读 §2 索引里的前三份（角色与语音全貌 / 方案v2 / 六页交接）
# 2) 本地构建 + 三道门禁（必须绿）
& "<hugo.exe>" --gc --minify --cleanDestinationDir
& "C:\Program Files\Git\bin\bash.exe" scripts/assert-build.sh ./public
& node _dev/gate-firstscreen.mjs
& python _dev/check-ssr-contract.py public
# 3) 看线上现状（本机直连被重置，走 srv1）
ssh secagent-srv1 "curl -sS -k -o /dev/null -w '%{http_code} %{size_download}\n' -H 'Host: xiaokeqing.cn' https://43.143.114.79/"
# 4) 决定 §5 那三条在跑的活由谁继续，再动任何文件
```

> **本地预览页面**（六页是 demo 整份，含大量静态素材，必须走 HTTP 而不是 file://）：
> `hugo server` 或 `python -m http.server 8000 -d public` 然后开 `http://127.0.0.1:8000/`
> ⚠️ `hugo server` 会给产物注入 livereload 脚本 ✗ —— **跑三道门禁前必须先停掉它**，否则断言可能被那行脚本干扰。
>
> 有问题优先查 §7 陷阱表与 §2 的文档；**不要凭猜改动线上**（push 之外还有 srv2 发布这一步 ✗）。

---

## 10. 交接时点快照（写这份时）

```
HEAD              = 1c3f5b0（写这份时的快照；后续提交会变，以 git log 为准 ✓）
线上版本目录       = /opt/secagent/releases/site-20261014-230937（srv2，原子切换）
三道门禁           = assert-build 16/16 ✓ ｜ gate-firstscreen 6/6 PASS ✓（预算已改 1650KB）｜ check-ssr-contract 6/6 ✓
⚠️ 工作区未提交    = 32 项（六页原型缺陷修复那条线正在改：layouts/*、_dev/gate-firstscreen.mjs、
                     scripts/{publish-site-to-srv2.ps1,srv2-site-receive.sh} 等）
                     ⇒ 接手第一件事：`git status --short` 看清，再决定由谁继续 ✗
正在跑的活         = ① 语音：日文真音色（第一句已出，正在改双语台词库→批量 60 句）
                     ② 六页原型缺陷四处修复（横幅/假数字/叠行/暗块）+ 后续 /about//TypeError//posts/ 链接
                     ③ 视频资产已产出（40 webm + 40 poster = 9.54MB）但**未接入**
```

### ⚠️ 仓库外但必需的东西（**不在 git 里** ✗，交接时必须逐条交绝对路径）

| 路径 | 内容 | 体量 |
|---|---|---|
| `E:\DeepSeek1\work\_kurisu-017\video-assets\` | 视频资产：`video/<clip>.webm`×40 + `<clip>.poster.webp`×40 + `SIZES.md` + `build_video_assets.py` + `evidence/` | 33.5 MB |
| `E:\DeepSeek1\work\_tts-trial\` | 语音管线：`out\dist\*.m4a+webm`、`out\envelope\*.json`、`lines60.json`、脚本、日志 | 9.3 GB（**含 uv-cache，别整体拷** ✗） |
| `E:\DeepSeek1\work\_kurisu-full\` | 旧包素材暂存 + 图集/图集工具（medium 图集就是从这儿生成的） | 1.7 GB |
| `E:\DeepSeek1\work\_amadeus-src\` | Amadeus 源码 clone；新素材包已安装到它的 `assets\spriteforge\runtime\kurisu` | 数 GB |
| `E:\DeepSeek1\work\push-gate.ps1` | 我的 9 组上线闸门（交叉校验用；`powershell -File` 直接跑） | 小 |
| `E:\DeepSeek1\work\断点状态-20261014-*.md` | 我这两轮的断点笔记（口径变更、文件清单、在跑的活） | 小 |
| `E:\DeepSeek1\work\.cf-token` / `.fish-key` | 凭据（前者**当前无效** ✗；后者待建） | — |
| `E:\DeepSeek1\work\_video-frames\` | 录屏抽帧与眨眼取证（参考素材） | 数十 MB |

### 接手顺序（建议）
```
1) 读 §1~§4（环境/索引/门禁/口径）
2) `git status --short` + `list_agents` → 看清谁在改哪些文件
3) 本地构建 + 三道门禁（必须绿）→ 再动任何文件
4) 决定 §5 三条在跑的活由谁继续；**先接手再改动** ✗
```

### 安全
```
若交接前有人把任何密钥贴进过聊天（CF token / Fish Key / SSH 私钥），请到对应平台 **Revoke 重建** ✓
仓库里**没有**任何密钥；密钥只在上面那张表的 `.cf-token` / `.fish-key` 与 `~\.ssh\` 里 ✓
```

---

## 11. 工具与 SSH 速查（照着填/照着跑）

```
hugo     = C:\Users\T\AppData\Local\Microsoft\WinGet\Packages\Hugo.Hugo.Extended_Microsoft.Winget.Source_8wekyb3d8bbwe\hugo.exe
node     = F:\node.js\node.exe        # _dev/gate-firstscreen.mjs 需要
git      = C:\Program Files\Git\cmd\git.exe
bash     = C:\Program Files\Git\bin\bash.exe   # 跑 scripts/assert-build.sh
python   = C:\Users\T\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe
ffmpeg   = E:\DeepSeek1\work\_kurisu-017\video-pipeline\tools\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe
ssh 别名 = secagent-srv1（阿里云）｜ secagent-srv2（腾讯云）；配置在 %USERPROFILE%\.ssh\config
ssh 私钥 = %USERPROFILE%\.ssh\secagent_ed25519

# 推送前必须设（否则 GitHub 报 publickey 拒绝 ✗）：
$env:GIT_SSH_COMMAND = 'ssh -i "$env:USERPROFILE\.ssh\secagent_ed25519" -o IdentitiesOnly=yes'

# 完整一条龙（构建 → 门禁 → 提交 → 推送 → 发布到 srv2）：
& hugo --gc --minify --cleanDestinationDir
& bash scripts/assert-build.sh ./public
& node _dev/gate-firstscreen.mjs
& python _dev/check-ssr-contract.py public
git add <你自己的文件> ; git commit ; git push
powershell -ExecutionPolicy Bypass -File scripts\publish-site-to-srv2.ps1   # ← 这一步才上线 ✗
```

> 提醒：**两个 AI 不要同时改同一个仓库** ✗ —— 交接时先让上一个停手（`list_agents` 看有没有在跑的活）。
---

## 12. 最新进展（2026-10-15 00:0x 追加，§10 的快照已被本节覆盖）

```
HEAD            = ec3b841（六页修复 + 导航统一 + 语音管线 均已入库并发布）
线上版本目录     = /opt/secagent/releases/site-20261014-235208（srv2 原子切换）
三道门禁         = assert 16/16 ✓ ｜ 首屏 6/6 PASS（预算 1650KB）✓ ｜ 路由 6/6 ✓

【已上线】六页 = 设计原型整份 + **导航统一成左侧 dock**
  （XK-LAB ｜ 主页·监测中心·AI问答·笔记·靶场·关于；主页原来那个顶部胶囊与死 CSS 已删干净 ✓）
  四处原型缺陷已修：删掉 DEMO 横幅 ✓ ｜ 演示数字换真实接口（作战室 1,284 与 45.155 已清 0 ✓，
  取不到写"读不到" ✓）｜ 攻击流叠行 ✓ ｜ CRT 顶部暗块 ✓
  字幕垫板 = 原图 382,384 B（未降质 ✓）

【语音·已完成未接线】8 句样本 0.51MB（E:\DeepSeek1\work\_tts-trial\sample8\dist\*.m4a|webm）

---

## 12b. 接管批追加（2026-10-15 白天）

```
HEAD（本批）   = 229e0d7 / 4c6140c / 6b35e89 / d8e03e6（T1 修复已发布；L1+CRT；T5.4+T5.5；T5.6+T12）
线上版本目录     = /opt/secagent/releases/site-20261015-112007（含 T1 手机动画修复）
三道门禁         = assert 15/15 ✓（条件分支，别处可能显 16）｜ 首屏 6/6 ✓ ｜ 路由 6/6 ✓

【T1 手机动画不放 · 已修已上线】根因：iPhone 横屏 CRT 高 224px < 原型写死的 260px 阈值 →
  整屏 fallback 盖住动画。判据改为 (高度<260 && 非触屏)，触屏一律播动画；冻帧对拍像素差 0。
【T4 日语语音 · 已核实】12 句/7 分组/717KB，手势前 plays=0、手势后 plays=1、字幕逐字对齐（CDP 实测）。
【开场镜头语言】CRT 通电（亮线→展开→闪烁→稳定）+ opening→idle 镜头推拉（commit 4c6140c）。
【T5.4/T5.5】主页 CRT 状态行假数字改占位（api-bind 填真值）；/posts/ 卡片改 Hugo range 真文章链接。
【T5.6+T12】boot→hi 两段式：主页首屏 1569→840KB（−47%）、内容页 267→185KB；
  背景/配色面板连同背景图已删（body 静态 data-skin="warm" data-phone="v1"）。
  xkClipIm：hi 只 peek 缓存不触发下载；boot 档期间 opening 循环 24 帧等 hi 接力。
【T5.2】首屏门禁控制台错误改为有错即 exit 1（白名单空启动、只收实测无害条目）。
【T5.3】/about/ 填入四张真实内容卡（站点性质/数据来源/她/纪律），不再空白。
【Fish Audio L2】key/开关/短语表已在 srv1 配好（self-check key=SET phrases=3），
  但上游 api.fish.audio 被 SNI 重置 ⇒ UPSTREAM_IO。三条出路待拍板：CF Worker 中转 /
  DashScope TTS 进代理 / 暂缓（预渲染 bank 的 12 句不受影响）。

```
HEAD            = ec3b841（六页修复 + 导航统一 + 语音管线 均已入库并发布）
线上版本目录     = /opt/secagent/releases/site-20261014-235208（srv2 原子切换）
三道门禁         = assert 16/16 ✓ ｜ 首屏 6/6 PASS（预算 1650KB）✓ ｜ 路由 6/6 ✓

【已上线】六页 = 设计原型整份 + **导航统一成左侧 dock**
  （XK-LAB ｜ 主页·监测中心·AI问答·笔记·靶场·关于；主页原来那个顶部胶囊与死 CSS 已删干净 ✓）
  四处原型缺陷已修：删掉 DEMO 横幅 ✓ ｜ 演示数字换真实接口（作战室 1,284 与 45.155 已清 0 ✓，
  取不到写"读不到" ✓）｜ 攻击流叠行 ✓ ｜ CRT 顶部暗块 ✓
  字幕垫板 = 原图 382,384 B（未降质 ✓）

【语音·已完成未接线】8 句样本 0.51MB（E:\DeepSeek1\work\_tts-trial\sample8\dist\*.m4a|webm）

---

## 12b. 接管批追加（2026-10-15 白天，本批负责人：执行 AI）

```
HEAD（本批）   = 6b35e89 / d8e03e6（T5.4+T5.5 / T5.6+T12；T1 修复 229e0d7 已发布上线）
线上版本目录     = /opt/secagent/releases/site-20261015-112007（含 T1 手机动画修复）
三道门禁         = assert 15/15 ✓（条件分支，别处可能显 16）｜ 首屏 6/6 ✓ ｜ 路由 6/6 ✓

【T1 手机动画不放 · 已修已上线】根因：iPhone 横屏 CRT 高 224px < 原型写死的 260px 阈值 →
  整屏 fallback 盖住动画。判据改为 (高度<260 && 非触屏)，触屏一律播动画；冻帧对拍像素差 0。
【T4 日语语音 · 已核实】12 句/7 分组/717KB，手势前 plays=0、手势后 plays=1、字幕逐字对齐（CDP 实测）。
【开场镜头语言】CRT 通电（亮线→展开→闪烁→稳定）+ opening→idle 镜头推拉（commit 4c6140c）。
【T5.4/T5.5】主页 CRT 状态行假数字改占位（api-bind 填真值）；/posts/ 卡片改 Hugo range 真文章链接。
【T5.6+T12】boot→hi 两段式：主页首屏 1569→840KB（−47%）、内容页 267→185KB；
  背景/配色面板连同背景图已删（body 静态 data-skin="warm" data-phone="v1"）。
  xkClipIm：hi 只 peek 缓存不触发下载；boot 档期间 opening 循环 24 帧等 hi 接力。
【T5.2】首屏门禁控制台错误改为有错即 exit 1（白名单空启动、只收实测无害条目）。
【T5.3】/about/ 填入四张真实内容卡（站点性质/数据来源/她/纪律），不再空白。
【Fish Audio L2】key/开关/短语表已在 srv1 配好（self-check key=SET phrases=3），
  但上游 api.fish.audio 被 SNI 重置 ⇒ UPSTREAM_IO。三条出路待拍板：CF Worker 中转 /
  DashScope TTS 进代理 / 暂缓（预渲染 bank 的 12 句不受影响）。

```
HEAD            = ec3b841（六页修复 + 导航统一 + 语音管线 均已入库并发布）
线上版本目录     = /opt/secagent/releases/site-20261014-235208（srv2 原子切换）
三道门禁         = assert 16/16 ✓ ｜ 首屏 6/6 PASS（预算 1650KB）✓ ｜ 路由 6/6 ✓

【已上线】六页 = 设计原型整份 + **导航统一成左侧 dock**
  （XK-LAB ｜ 主页·监测中心·AI问答·笔记·靶场·关于；主页原来那个顶部胶囊与死 CSS 已删干净 ✓）
  四处原型缺陷已修：删掉 DEMO 横幅 ✓ ｜ 演示数字换真实接口（作战室 1,284 与 45.155 已清 0 ✓，
  取不到写"读不到" ✓）｜ 攻击流叠行 ✓ ｜ CRT 顶部暗块 ✓
  字幕垫板 = 原图 382,384 B（未降质 ✓）

【语音·已完成未接线】8 句样本 0.51MB（E:\DeepSeek1\work\_tts-trial\sample8\dist\*.m4a|webm）
  全量 60 句 3.13MiB（out-ja\dist\，超 3MiB 预算 4.5% ✗）→ 决定：**先用 8~12 句**；要全量按 m4a 40k / webm 32k 收口 ≈2.6MiB
  管线已入库：scripts/voice/（8 文件 +1746 行：README/合成/后处理/build_bank/双语表/shim）
  实测：RTF≈0.98 ｜ 平均 4.66s/句 ｜ 显存峰值 2070MiB（6GB 余 1.8GB ✓）｜ 响度 -16.35~-15.95（极差 0.40）｜
        包络与线上 12 句逐点 100% 一致 ✓；日语**不需要 BERT**，比中文更快更省显存 ✓

【视频·已完成未接线】40 webm + 40 poster = 9.54MB（B 路线透明 VP9+alpha，替代 71MB，分辨率翻倍）

【剩余工作 = 接线三步，各自可独立上线】
  ① 语音接线 1~2h（风险最低、成果最直接：她会开口说话）
  ② 视频接线 2~3h（canvas 从画 PNG 改为画 <video> + 预载纪律 + poster 回退；方案 v2 §9 有阈值与回退）
  ③ 状态机(38/88) + 口型(BigVGAN envelope→嘴部补丁) 接线 3~5h（最难）

【已知小尾巴，留给下一个 AI】
  · 主页静态 HTML 仍留 1 处 `1,284`（JS 覆盖前的占位 ✗，浏览器加载后被真实值替换 ✓）
  · docs/交接-六页整份搬demo-20261014.md:114 仍写旧断言 `.navpill`（文档未同步 ✗）
  · /about/ 那一屏在原型里本就是空的 ✗ ｜ 五页各一条原型 TypeError ✗ ｜ /posts/ 卡片不是链接 ✗
```