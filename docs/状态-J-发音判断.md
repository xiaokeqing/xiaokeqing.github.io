# 状态 · 窗口 J-发音判断

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 `docs/窗口分工规范-20261015.md` §四

| 项 | 内容 |
|---|---|
| 负责 | **判定合成句里「牧瀬紅莉栖」有没有念错**（第二证人法：不依赖人耳） |
| 状态 | **已完成 ✅** |
| 一句话结论 | **是我们合成念歪了 —— 根因是出货管线的日文文本前端（pyopenjtalk / Open JTalk）把「牧瀬紅莉栖」读成「マキセクレナイリースミカ」（紅→クレナイ、栖→ースミカ），不是 ASR 的锅；ASR 只是如实转写** |
| 改了哪些文件 | 新增 `docs/发音判断-牧瀬紅莉栖-20261015.md`、本文件。**未碰** `scripts/voice/**`（B/他人正在改）、`docs/状态-G-*.md`、任何音频与活文档 ✗；仓库外产物在 `E:\DeepSeek1\work\_eval-name\**` |
| 验收证据 | ① 同套 Qwen3-ASR 跑官方真人原音 → `マキセクリスです`（读音正确）vs 我们 → `巻きせくれないリスミかよ`（`results\asr-qwen-official.json` / `asr-qwen-all.json`）② 独立 ASR faster-whisper `small`（`model.bin` sha256 `3e305921…`，non-Qwen 架构）→ 我们段 `巻きせくれないリースみかよ`、官方段 `マキセクリス`（`results\asr-whisper-small.json`）③ 名字段孤立 ASR + 5 个滑窗仍全错 ⇒ 非上下文问题 ④ teacher-forcing 似然比：我们段错读法胜（−103.34/−4.49 vs 正确 −130.85/−7.27），官方段正确读法胜（−11.29/−1.61 vs −77.14/−6.43）——镜像结果（`results\asr-likelihood.json`）⑤ 因果闭环：`clean_text(原文,"ja","v2")` → `m a ] k i s e UNK k u [ r e n a i UNK r i [ i s u ] m i k a y o`（`results\frontend-e2e.json`），逐音素等于 ASR 听到的 `巻きせくれないリスミかよ`；`git ls-files GPT_SoVITS/text/ja_userdic` 为空 ⇒ 无用户词典，读音由通用词典逐字决定 ⑥ 钉到出货那次运行：`out-ja\summary-all60ja.json` 的 `m4a.sha256=163ed1fd…` 与受测文件一致，`synth-all60ja.log` 记 `SoVITS version: v2, model version: v3` |
| 影响面 | 60 句候选库里**仅 1 句**含此人名（`greet_first_ever`）；线上 12 句 `bank.json` **不含**该句 ⇒ 属上线前拦下，非线上事故 |
| 下一步 | ① 修法 1（推荐）：给 `_amadeus-src\GPT_SoVITS\text\ja_userdic\userdict.csv` 加 `牧瀬紅莉栖→マキセクリス`（仓库已有该机制，`japanese.py:53-60` 自动建词典）；② 修法 2（兜底，已验证）：该行文本改写假名 `牧瀬クリス` ⇒ 出货前端读音变正确；③ 把结论转给窗口 B（声音换代）与规划侧 |
| 卡点 | 用户词典的**正确 CSV 列格式 `[待核对]`**：按 naist-jdic 13 列试写虽被 `mecab_dict_index` 接受（生成 6171 B `.dic`），但 `g2p` 返回空串（名字被吞）⇒ 列序需按 mecab-jtalk-dic 核对；**反证已明确**：换参考音频 / 换 v2ProPlus / 拆句**都不能修**（各档读音逐字相同、名字孤立仍被听错） |
