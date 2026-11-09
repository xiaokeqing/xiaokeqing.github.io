# 状态-B-声音（窗口 B）· 2026-10-15

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 `docs/窗口分工规范-20261015.md` §四 ✓

```
任务号 ：T17 声音模型换代 A/B（含站长升级的"产出可替换的更好版本"）
状态   ：已完成（1 项卡点：v2ProPlus 权重缺失；1 项移交：gate-firstscreen 异常归窗口 C）
```

## 改了哪些文件（先不 commit / 不 push ✗）

```
仓库内
  scripts/voice/synth.py                      + --model v3|v2pro|v2plus / --gpt / --sovits / --noise-seed /
                                               --emotions-ids 白名单；ttsJa（朗读文本）优先；缺权重显式报错
  scripts/voice/README.md                     + §4.1 模型档与 v2Pro/v2ProPlus（装包路径 / 情绪参考只 v3 能用 / GBK help 崩）
  scripts/voice/lines60-bilingual.json        + ttsFieldOverride 说明；greet_first_ever.ttsJa（ja/zh 一字未改 ✓）
  static/kurisu/voice/<12 句>.m4a/.webm/.envelope.json   换为 v3 同口径重跑版
  static/kurisu/voice/bank.json               sha256/bytes/seconds/durationMs/envelopeValues/loudness/totalBytes 同步
仓库外（全部产物）
  E:\DeepSeek1\work\_tts-trial\ab3\**        （见报告 §8）
  E:\DeepSeek1\work\_tts-trial\ab3\_prev-v3\ 旧 12 句备份（37 文件 / 774,781 B，回滚用）
未碰（按分工规范）✗
  static/kurisu/manifest.json ｜ layouts/** ｜ static/js/** ｜ _dev/**
```

## 验收证据（命令输出 / 产物路径）

```
模型可用性   v3 ✅ ｜ v2Pro ✅（从 06-voice-…-v2pro-experimental 解包 3 文件后）｜ v2ProPlus ❌ 全盘 0 命中（未测）
同句 A/B     v3(带 shy) RTF 0.944 / 峰值 2069 MiB ｜ v3(无情绪) 0.674 / 2085 MiB ｜ v2Pro 0.589 / 1296 MiB
             ab3\v3|v3-noemo|v2pro-noemo\dist\greet_first.{m4a,webm}（三条可试听）
硬卡点       v2Pro + --emotions on → ValueError: Mixed semantic references require V3（local_tts_infer.py:1035）
12 句重生成  文件：ab3\rep-v3（已入库）｜ ab3\rep-v2pro（落选）｜ ab3\rep-v3-emo（3 句情绪版）
             v3   合计 714,845 B ｜ 42.02s ｜ 平均 3.50s/句 ｜ RTF 0.669 ｜ 峰值 2085.9 MiB
             v2Pro 合计 655,490 B ｜ 17.99s ｜ 平均 1.50s/句 ｜ RTF 0.316 ｜ 峰值 1291.1 MiB
             响度极差 v3 0.35 LU / v2Pro 0.16 LU（规格 ≤0.5 ✓）
内容完整性   ASR 回译 CER：v3 平均 0.0235 / v2Pro 平均 0.1228，v2Pro 有 2 句真丢内容
             greet_first 59 字→念 37 字（CER 0.390）｜ fallback_offline 36 字→念 21 字（CER 0.417）
             ab3\probe\asr12-cer.json
人名读音     pyopenjtalk.g2p('牧瀬紅莉栖よ') = m a k I s e k u r e n a i r i i s u m i k a y o（错读）
             pyopenjtalk.g2p('牧瀬クリスよ') = m a k I s e k u r i s u y o（正确）
             ASR 端到端：旧→「巻きてくれないリスミかよ」｜ 新→「マキス、クリスよ」  ab3\probe\asr-namefix.json
门禁         换版前 assert-build 16 项通过 0 失败
             换版后 assert-build 16 项通过 0 失败 ｜ check-ssr-contract 6/6 PASS
             gate-firstscreen：home 840 KB / 1650 KB PASS，随后 FAILED：window.__xkSM.reasons is not a function
             （归窗口 C：layouts/index.html 正在重写 __xkSM，未提交，非我改动的文件）
体积         static/kurisu + static/images/crt：91,817,051 → 91,823,153 B（+6,102 B）
             距 96 MiB 门禁余 8.43 MiB ✓；static/kurisu/voice 774,781 → 772,735 B
一致性       bank.json 的 sha256/bytes 与磁盘 24 个文件逐一对齐 ✓（ab3\sync_bank.py 复核输出）
契约自检     12/12 句：包络点数 / m4a+webm 字节 / durationMs / sampleRate=8000 / hopMs=10 全部自洽 ✓
写仓库姿势   Python 写 static/** 会 PermissionError；改用「Python 写到仓库外 + PowerShell Copy-Item -Force」
             （已记入 scripts/voice/README.md §5 第 8 条）
```

## 下一步 / 移交

```
① v2ProPlus（e80+e12 / e100）权重到位后，一条命令即可复跑（--model v2plus 已预置，缺文件会显式报错）
② 站长的听感结论决定是否保留本轮 v3 重跑版（不同意就整目录回滚 _prev-v3，一条命令）
③ gate-firstscreen 的 __xkSM.reasons 异常 → 窗口 C 修完请重跑；三位门禁齐绿才具备发布条件
④ static/kurisu/manifest.json 的 voice 段已陈旧（totalBytes 716960 / 旧 sha256）→ 规划侧统一刷新
   （运行期播放只读 kurisu/voice/bank.json，功能不受影响）
⑤ 60 句若要全量上：greet_first_ever 已修好人名；其余 59 句无需改
```

*窗口 B · 2026-10-15 · 未 commit / 未 push ✓*
