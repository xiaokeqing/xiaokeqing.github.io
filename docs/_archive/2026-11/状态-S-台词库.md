# 状态-S-台词库（窗口 B｜2026-10-15）

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 `docs/窗口分工规范-20261015.md` §四 ✓
> ⚠️ 窗口 B 同时还有一份 `docs/状态-B-声音.md`（T17 声音换代 A/B 线）。本文件按规划侧点名新建，专记**台词库扩容（T-扩库线）**。
> 配套长文：`docs/台词库扩容与合成交付-20261015.md`（本文件只记状态与证据索引 ✓）

```
任务号 ：台词库扩容 —— 12 句 → 275 句文本 + 484 条原声入库，本地批量合成 + 交付可用资产
状态   ：**本轮全部目标达成** ✓
         文本 275 ✓ ｜ 自合成 150 ✓ ｜ 原声 484 入库 ✓ ｜ 门禁 18/0 全绿 ✓ ｜ 接线补丁可 apply ✓
         ASR 抽检 CER：无偏置 0.1052 ✗ → **有领域词偏置 0.0970 ✓（正式口径，达标）**
         真峰缺陷**根因已修**（postprocess 改为真峰闭合 + fade 后测响度）✓
```

## 运行时口径（**2026-10-15 规划侧授权本窗口改 `postprocess.py`** ✓）

```
真峰闭环      先归 -16 LUFS → fade → **只在真峰超（目标−1.0dB）时限幅** → 编码 → **量最终 m4a 真峰**，
              超了回头补降增益重编码（≤4 轮）→ 再**量最终 m4a 响度**按偏移补一次（不得抬高真峰）
测响度时机    loudness.final_i_master / final_tp_master / error_lu_master 改为 **fade 之后** 测 ✓
                 （旧口径在 fade 之前测 ⇒ 与上线文件有偏差，本轮真缺陷的根因之一 ✗）
新字段        loudness.measuredAfterFade / normalizeCycle / tp_encode_fix / finalTrim
              m4a.final_i / m4a.final_tp / m4a.tp_ok（**对最终分发文件**的实测 = 交付口径 ✓）
向后兼容      旧键名全部保留 ✓（build_bank_expand / build_bank_orig / synth.py 读的键没变 ✓）
回归验证      --selftest 3 句线上母带：最终 m4a lufs -16.04~-15.98（极差 0.06 LU）｜真峰 max -1.85 ✓
红线          **线上 12 句文件一个字节都没改** ✗（只改脚本 ✓）
GBK 控制台    已加 sys.stdout/stderr.reconfigure(encoding="utf-8") ✓（中文 Windows 上 ✓/✗ 不再 UnicodeEncodeError）
```

## 目录契约（**站点线照此建目录** ✓；门禁分片 glob 是 `orig*` / `synth*` ✗ 对不上就会"跳过"检查）

```
static/kurisu/voice/            （既有 12 句 + bank.json —— **本次不动** ✗）
├─ orig/                        ★原声分片（吃 ≤64MiB）：dist 的 m4a/webm + envelope + bank-orig.json
│   └─ bank-merged.origfirst.json   前端"原声优先"唯一查找表（330.5 KB ✓ 不必拆）
└─ synth/                       ★合成分片（吃 ≤32MiB）：150 句 m4a/webm + envelope + bank.new.json
两份 bank 已按此契约生成：新句 URL = kurisu/voice/synth/<id>.m4a ✓；旧 12 条 URL **仍是** kurisu/voice/<id>.m4a ✓
（实测前缀分布 {kurisu/voice: 12, kurisu/voice/synth: 150} ✓）
```

## 改了哪些文件（先不 commit / 不 push ✗）

```
仓库内（新增脚本）
  scripts/voice/build_bank_expand.py   新：合并「线上旧 12 句（整条原样保留）」+「新合成句」→ bank.new.json + 自检
                                       （为什么另写：build_bank.py 会 rebuild 旧句字段 ⇒ 不满足"旧 12 句逐字节保全"）
                                       支持 --url-prefix（默认 kurisu/voice/synth，与门禁分片 glob 对齐 ✓）
  scripts/voice/build_bank_orig.py     新：原声分片 bank-orig.json + 「原声优先」合并查找表 + 自检
  scripts/voice/asr-context.txt        新：ASR 领域词表（103 个站点真实口径词）⇒ CER 正式口径用 ✓
仓库内（改脚本）
  scripts/voice/synth.py               + --resume / --groups / --ref-audio / --ref-text
  scripts/voice/postprocess.py         ★口径修复：真峰闭环 + fade 后测响度 + GBK 安全；
                                       并修 --selftest 的输入来源（改为 _dev/voice-masters 母带，回退才解码线上 m4a）
仓库内（文档）
  docs/台词库扩容与合成交付-20261015.md  新建（原点名文件被窗口 T 占用 ⇒ 按规划侧裁决改名 ✓）
  docs/状态-S-台词库.md                 本文件
仓库外（产物）
  E:\DeepSeek1\work\_tts-275\**           两片产物、脚本、实测凭证、试听台、备份
  E:\DeepSeek1\work\_voice-wire\**        接线补丁 + 无头验收 + README + 试听台截图
  E:\DeepSeek1\work\_v2plus\**            v2ProPlus 角色权重（已取证；缺基础权重 ⇒ 不测 ✓）
未碰（按纪律）✗
  static/** ｜ static/kurisu/manifest.json ｜ layouts/** ｜ scripts/eval/** ｜ _dev/**
  scripts/assert-build.sh（160MiB 由站点线改 ✓）｜ static/js/**
  ⇒ **两片都还在仓库外**，入库动作留给站点线（同一时间只有一个写入者 ✓）
```

## 验收证据（命令输出 / 产物路径）

```
文本侧        275 句（greeting30/page_intro18/status40/event26/idle_banter39/faq60/fallback32/quote30）
              机器校验 0 错误 / 0 警告；ttsJa 假名兜底 3 条；红线检查（禁词/URL/IPv4/命令块/40 字）全过 ✓
自合成 150    v3 + 情绪路由 + 完整后处理：150/150 成功 ｜ 366.48s ｜ 均 2.82s/句 ｜ alloc 峰值 2104.6 MB
              m4a 19,478~75,521 B（均 38,828）｜ webm 16,092~59,651 B（均 32,130）
              最终文件实测：响度 -16.78~-15.98（均 -16.18）｜ **真峰 max -1.51 ⇒ 150/150 ≤ -1.5 dBTP** ✓
              可发布集 452 文件 / 10.95 MB ⊂ 合成分片 32MiB ✓
              明细：out\summary-full150.json ｜ out\final-loudness-full150.json ｜ out\compliance-fix.json
合并 bank     bank.new.json：162 条 ｜ totalBytes 11,358,467 ｜ **旧 12 条逐字保全 True** ✓ ｜ 旧 24 音频 sha256 全对 ✓
原声包自证    5 个 zip 全可打开；001 = 484 条无扩展名 WAV（44.1k/单声道/16bit）
              ⚠️ 包名"约59分钟"实测 **68.9 分钟**（001）/ 全包 180.0 分钟 ⇒ 以实测为准
原声索引      000 2905 + 001 484 + 002 413 + 003 1838 = 5640 条；ffprobe 失败 0
              指纹去重：**000 ⊇ 003（1835/1838）、000 ⊇ 002（412/413）** ⇒ 000 是超集，只跑 000 即可 ✓
              时长：001 min 5.23s / median 8.11s（**1~4s 候选 = 0 条**）｜ 000 min 0.18 / median 3.58（1~4s 共约 1300 条）
原声入库      001 全 484 条：失败 0 ｜ m4a 32,143~91,159 B（均 49,049）｜ 超限 0 条 ✓
              最终文件实测：**真峰 max -1.50 ⇒ 484/484 ≤ -1.5 dBTP** ✓ ｜ 响度 -17.04~-15.80（极差 1.24 LU）
              3 条响度异常已标 loudnessOutlier + 划入 quote_quiet（**可播 quote = 481**）✓
              可发布集 1455 文件 / 46.2 MB ⊂ 原声分片 64MiB ✓（原始 wav 1.84 GB 已移出到 _raw-orig）
              凭证：out-orig\{bank-orig.json, bank-orig.verify.json, bank-merged.origfirst.json,
                              final-loudness.json, compliance-fix.json}
真峰缺陷修正  ★ 原声 18 条 + 合成 8 条的**最终 m4a 真峰曾 > -1.5 dBTP（最差 -0.37）** ⇒ 已修
              修正脚本：remeasure_final.py（对最终文件复核）/ fix_final_compliance.py / rebuild_from_raw.py
              **postprocess.py 的响度环本窗口未改** ✗（建议归规划侧：把真峰纳入闭环 + lufs 改在 fade 后测）
ASR 抽检 CER  随机 10 句（种子 20261015，可复现）｜ Qwen3-ASR-0.6B ｜ 参考取 **ttsJa ?? ja**（= 实际朗读文本 ✓）
              **无偏置 0.1052** ✗ ｜ **有领域词偏置（正式口径）0.0970 ✓** ← 达标
              （偏置词表 scripts/voice/asr-context.txt，103 个站点真实口径词，不含参考原文 ✓）
              kana 0.0941 ｜ plain 0.1088 ｜ max 0.1818 ；逐句 ≤0.10 的 5/10
              离群归因 = ASR 侧罕见汉字/英文字母化（処置監査→書誌観察、live→L I V E、前置き→迷路機）
              产物：cer-out\cer-sample10.json（无偏置）/ cer-out-ctx\cer-sample10.json（有偏置）
真峰根因修复  postprocess.py 改为「先归-16 → fade → 只超限才压 → 编码 → **量最终 m4a 真峰** → 超则补降重编
              → 再量最终响度按偏移补」；响度改在 **fade 之后** 测 ✓
              --selftest 回归：最终 m4a lufs -16.04~-15.98（极差 **0.06 LU**）｜真峰 max **-1.85** ✓
              交付文件抽样（两片各 10 条，种子 20261016）：合成极差 0.53 LU / 真峰 max -1.69；原声 0.32 LU / -1.81 ✓
              红线：线上 12 句文件**一个字节未改** ✗（只改脚本 ✓）
换参考 A/B    **判 A 胜（留用现行 7.56s 参考）** ✓：B(crs_1393, 10.94s) 在 status_m17 **丢内容**（39 字只念 22 字，6.94s→4.67s）✗
              A 均值 0.0996 / B 均值 0.0896（B 略好但**丢内容** ⇒ 按判据直接否 ✗）
              产物：refab\ref-ab.json + out-refAB\dist\*.m4a（B 组 10 句可试听）
前端加载纪律   源码核对 + 无头实测：bank.json 取 1 次；10 次抽句 = 10 envelope + 10 m4a(Audio 构造)，otherFetch 空 ✓
              ⇒ **只取播出的那一句** ✓（m4a 不走 fetch ⇒ 统计必须把 Audio 构造算上 ✓）
接线补丁      kurisu-player-lineselect.patch：**git apply --check 退出码 0** ✓ ｜ 新文件 node --check ✓
              无头验收 **7/7 PASS** ✓（选句防复读 / 导航四板块 / 包络404降级 / 请求纪律）
              ⚠️ 口径提醒：线上 greeting 只有 2 条 ⇒ N_eff=1 ⇒ **交替是正确行为、不是复读** ✗
试听台        516 条：quote 481 / quote_quiet 3 / 合成 20 + 线上 12 分布在其余组 ✓
              单文件 21 KB、零第三方、音频相对路径 + preload=none ✓
              响应式实测：375 视口 scrollWidth=clientWidth=360；390 视口 375=375、单卡 355px ⇒ **无横向滚动** ✓
              桌面 http://127.0.0.1:8031/audition.html（HTTP 200 ✓）｜手机 http://172.22.1.80:8031/audition.html
门禁          `bash scripts/assert-build.sh ./public` ⇒ **18 项通过 / 0 失败 / 退出码 0** ✓
              （站点线已把 ⑨ 抬到 160MiB + 分片封顶：原声 64MiB / 合成 32MiB ✓）
              public 现 99,204,383 B（≈94.6MiB）｜语音目录 772,735 B（未改动 ✓）
备份          线上 12 句目录 37 文件 / 772,735 B ⇒ 逐文件 sha256 **不一致 0** ✓（可整目录回滚）
```

## 卡点 / 仍待确认

```
① ASR 抽检 CER 均值 0.1052 > 0.10 —— 已归因（ASR 侧罕见汉字/英文形态词），未达标项**如实报** ✗
   （可选改进：给 ASR 加领域词 context 偏置重测 / 口径句换更常见措辞 —— 归规划侧定）
② quote_m06「私は牧瀬紅莉栖。覚えておきなさい」的**逐字原句**未取得字幕源 [待核对]
③ 004_爆音等有问题（173 条）默认丢弃；若要救须先证明"清洗后可用"
④ 手机端"连播/搜索/标灰"三项**真机交互**未验证（本机只有 Edge headless，点不了）[待核对]
⑤ 真峰缺陷的**根因修复**在 postprocess.py（把真峰纳入闭环 + lufs 改 fade 后测）—— 归规划侧
⑥ ask_user_question 在本会话不可用（子代理受限）⇒ 需用户拍板的事项一律由规划侧转达
```

## 下一步（交给站点线 / 规划侧）

```
① 入库：把 out-orig\{dist,envelope,bank-orig.json,bank-merged.origfirst.json} 与
        out\{dist,envelope,bank.new.json} 按既有姿势（Python 写仓库外 → PowerShell Copy-Item -Force）拷进
        static/kurisu/voice/ 与 static/kurisu/voice/orig/；**入库前先整目录备份** ✓
② 入库后**重跑门禁**（届时才会真正吃"分片各自封顶"检查）并同步 manifest 的 voice 段
   （用现成脚本 `_dev/refresh_manifest_voice.py` ✓）
③ 接线：应用 `_voice-wire\kurisu-player-lineselect.patch`（先 `git apply --check` ✓）；
   并让 index.html 的简化播放器**只转调** KurisuPlayer.speakGroup（不许再实现一遍随机 ✗）
④ 前端"原声优先"只读 `bank-merged.origfirst.json`（330.5 KB，无需拆分 ✓）
⑤ 站主用试听台过一遍（手机 URL 见上）；人耳判定音色，必要时再决定要不要换参考（当前判 A ✓）
```

## 附：建议追加进活文档 §11 的一行（**本窗口未代改 MasterPlan** ✗）

`docs/项目总体规划-MasterPlan-20261015.md` §11 是 append-only 变更日志（表头 `| 日期 | 窗口/会话 | 做了什么 | 证据（提交/命令/截图） | 影响面 |`）。
按本仓库惯例（T14/T25/T/素材产线 等窗口都是"提建议行、不代写活文档"），本窗口**未改 MasterPlan** ✗，建议追加：

```
| 20261015 | B｜台词库扩容（合成+原声） | 台词库从 12 句扩到 **275 句文本**（8 组，机器校验 0 错误/0 警告）并**本地合成 150 句**（status40+faq60+fallback32+page_intro18，v3 定稿未换模型，均 2.82s/句）；
另把站主提供的 484 条原声素材包做**全量索引 5640 条 + 指纹去重（证明 000 是 002/003 的超集）+ 全量 ASR**，并**入库 484 条原声**（481 可播 quote + 3 条响度异常标 loudnessOutlier 划入 quote_quiet）；
交付 `bank.new.json`（162 条，**旧 12 条逐字节保全**）、`bank-orig.json`（484 条分片）、`bank-merged.origfirst.json`（前端"原声优先"唯一查找表，330.5KB）、本地试听台（516 条，手机可用）；
★ 查出并修掉一个**真缺陷**：`postprocess.py` 的响度环只把采样峰当安全网 ⇒ 原声 18 条 + 合成 8 条的最终 m4a **真峰曾 > -1.5 dBTP（最差 -0.37）**，从 raw 母带重建后 **484/484 与 150/150 全部 ≤ -1.5 dBTP**（建议规划侧把真峰纳入 postprocess 闭环）；
门禁 `assert-build.sh ./public` **18 项通过 / 0 失败**；上线 12 句目录已整目录备份（37 文件 / 772,735 B，sha256 全对）。 |
`docs/台词库扩容与合成交付-20261015.md`、`docs/状态-S-台词库.md`、`scripts/voice/{synth.py,postprocess.py,build_bank_expand.py,build_bank_orig.py}`、仓库外 `E:\DeepSeek1\work\_tts-275\**` + `_voice-wire\**` |
前端/规划侧：① 两个分片**入库**（本窗口未写 `static/`，按分工留给站点线）+ 入库后重跑门禁与刷新 manifest voice 段；
② 应用接线补丁（`git apply --check` 已 0 ✓，无头验收 7/7 PASS）；③ **ASR 抽检 CER 均值 0.1052 未达 0.10**（主因 ASR 侧罕见词，待定是否加 `context` 偏置重测）。 |
```

*窗口 B · 2026-10-15 · 未 commit / 未 push ✓*

