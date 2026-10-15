# 状态-S-台词库（窗口 B｜2026-10-15）

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 `docs/窗口分工规范-20261015.md` §四 ✓
> ⚠️ 窗口 B 同时还有一份 `docs/状态-B-声音.md`（T17 声音换代 A/B 线）。本文件按规划侧点名新建，专记**台词库扩容（T-扩库线）**。
> 若规划侧认为"一个窗口只该有一个状态文件"，请指示合并哪一份 ✓。

```
任务号 ：台词库扩容 —— 12 句 → 200~300 句，本地批量合成 + 交付可用资产（花费 ¥0 / 走现成管线 / 不换模型）
状态   ：进行中（文本侧已定稿 275 句 ✓；20 句试批已完成 ✓；484 原声包已索引、全量 ASR 进行中）
```

## 改了哪些文件（先不 commit / 不 push ✗）

```
仓库内（新增）
  scripts/voice/build_bank_expand.py   新增：合并「线上旧 12 句（整条原样保留）」+「新合成句」→ bank.new.json + 自检
                                       （为什么另写：build_bank.py 会 rebuild 旧句字段 ⇒ 不满足"旧 12 句逐字节保全"）
仓库内（文档）
  docs/台词库扩容-20261015-窗口B.md      新建（原点名文件名被窗口 T 占用，见文首 ⚠️）
  docs/状态-S-台词库.md                 本文件
仓库外（全部产物）
  E:\DeepSeek1\work\_tts-275\src\**                 275 句分组源 JSON（8 组）
  E:\DeepSeek1\work\_tts-275\lines275-bilingual.json 合并后的双语台词库
  E:\DeepSeek1\work\_tts-275\tools\**               校验 / 索引 / ASR / 汇总脚本
  E:\DeepSeek1\work\_tts-275\out\**                 合成产物 + 试批实测 + 原声索引 + 原声 ASR
  E:\DeepSeek1\work\_tts-275\orig\**                 484 包解包结果（001/002/003）
未碰（按纪律）✗
  static/kurisu/voice/** 尚未改动（仍在合成阶段）｜ static/kurisu/manifest.json 未改
  layouts/** ｜ scripts/eval/** ｜ _dev/** ｜ scripts/assert-build.sh ｜ static/js/**
```

## 验收证据（命令输出 / 产物路径）

```
bank 计数疑问   逐字节核对：bank lineCount=12 且 lines=12；manifest voice 同为 12 / 714845；sha256 全对
                ⇒ **"计数不一致"不成立**，未做任何"顺手修正" ✓
台词库定稿      275 句（greeting30/page_intro18/status40/event26/idle_banter39/faq60/fallback32/quote30）
                机器校验 0 错误 / 0 警告；ttsJa 假名兜底 3 条（含「牧瀬紅莉栖」的句子全覆盖）
                红线检查：中文/日文禁词、URL、IPv4、命令块、40 字长度 —— 全部通过
20 句试批       v3 + 情绪路由 + 完整后处理：20/20 成功 ｜ 均 2.97s/句 ｜ alloc 峰值 2090 MB / smi 4513 MB
                m4a 23,444~63,304 B（均 37,666）｜ webm 19,456~52,601 B（均 31,313）
                响度极差 **0.31 LU** ✓ ｜ TP **全部 ≤ -1.5 dBTP** ✓ ｜ 包络首窗全部 ≥0.12 ✓、双解最大 MAD 0.00628
                明细：out\summary-trial20.json ｜ out\stats-trial20.json
                5 句试听：out\dist\{status_m01,fallback_m02,status_m22,fallback_m27,faq_m17}.m4a
原声包自证      5 个 zip 全部可打开；无残留 .downloading；001 = 484 条无扩展名 WAV（44.1k/单声道/16bit）
                ⚠️ 包名"约 59 分钟"实测 **68.9 分钟**（001）/ 全包 180.0 分钟 ⇒ 以实测为准
原声索引        2735 条（001 484 + 002 413 + 003 1838），ffprobe 失败 0，指纹去重后**重复 0 条**
                out\orig-index.csv / orig-index.json / orig-dups.json
原声覆盖矩阵   能：quote、情绪口癖（主力 003）；部分能：greeting/idle_banter
                不能：status / faq / fallback / page_intro（本项目独有语义）
                ⇒ 自合成必要范围 = 150 句（status40+faq60+fallback32+page_intro18）
前端加载纪律   源码核对：kurisu-player.js 只有 loadVoiceBank（1 次）+ playLine（按 id 取 1 条 m4a + 1 个 envelope）
                无任何整库预载 ✗；每次播放新增请求 2（首句 3）—— 运行时计数待全量接线后补测 [待核对]
门禁           未跑（语音尚未入库）；基线 public = 99,078,064 B（≈94.5MiB）；语音目录当前 772,735 B
```

## 卡点 / 待规划侧拍板

```
① docs/台词库扩容-20261015.md 被窗口 T 占用（已 git 跟踪的成品）⇒ 本窗口另写 -窗口B.md，请裁决是否合并
② quote 组用 003 短句为主，还是保留 001 的完整长句（8~11s，单条 m4a 60~100KB 超 40KB 报告口径）
③ 4 条长答案超单句上限（faq_m01/m07/m17 + status_m17）⇒ 照收 / 压码率 / 压文本重合成
④ quote_m06 的逐字原句 [待核对]
⑤ v2ProPlus A/B：网盘需登录 ⇒ 等站主下载后给落点；不抓非官方镜像 ✗
⑥ ask_user_question 在本会话不可用（子代理受限）⇒ 需要用户拍板的事项一律由规划侧转达
```

## 下一步

```
① 001 全量 484 条 ASR（后台，~22min）→ 立跑 003 全量 1838 条（~86min）
② 原声台账（zip 档位/原名/时长/ASR/sha256/用途）+ 8 条台词候选 + 3 条情绪参考候选 + 1 条音色参考候选
③ 全量合成（先 status/faq/fallback/page_intro 四组 150 句，GPU 串行不抢）
④ build_bank_expand.py 出 bank.new.json（旧 12 句整条保留 ✓）→ 备份整目录到仓库外 → PowerShell Copy-Item 入库
⑤ 跑 _dev/refresh_manifest_voice.py 同步 manifest 的 voice 段
⑥ 随机 10 句 ASR 回译 CER + assert-build 全绿 + 前端请求数证据 → 回填两份文档
```

*窗口 B · 2026-10-15 · 未 commit / 未 push ✓*
