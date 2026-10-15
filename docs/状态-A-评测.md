# 状态 · 窗口 A-评测

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 `docs/窗口分工规范-20261015.md` §四

| 项 | 内容 |
|---|---|
| 负责 | **T13 评测包**（ASR 回译 CER / 问答质量集 / MOS·ABX 流程） |
| 状态 | **① 已完成 ✅**（60 句 CER 出数，均值 0.0683）｜ **② 题库已完成、得分表🟡部分**（40 条成文；有效采集 4/40，拒答 4/4 正确、幻觉 0；其余受公开额度池 30 次/日限制）｜ **③ 流程与脚本已完成 ✅、结果待人工**（MOS/ABX 空模板，无真实评委） |
| 改了哪些文件 | 新增 `scripts/eval/{README.md,asr_cer.py,qa_run.py,qa_score.py,mos_build.py,mos_analyze.py,mos_template.md}`、`scripts/eval/datasets/{qa-40.jsonl,refusal-rubric.json}`、`docs/评测报告-语音与问答-20261015.md`；本文件。**未碰** `layouts/**`、`static/kurisu/**`、`_dev/gen-demo-pages.py`、活文档 ✗ |
| 验收证据 | ① `asr_cer.py` 输出 `n=60 cer_norm_mean=0.0683 cer_kana_mean=0.0621 cer_plain_mean=0.0902 zero=26/60 under10%=46/60`（产物 `E:\DeepSeek1\work\_eval-t13\asr-cer-final\asr-cer-20261015-203146.{md,csv,json}`）② `qa_score.py` 输出 `valid=4/40 invalid=2 refusalAcc=1.0 strict=1.0 citations=0.75 fabrication=0 stateMatch=4/4`（原始响应 6 份在 `_eval-t13\qa-runs\20261015-203236\raw\`）③ `mos_build.py` 输出 `items=8 abx=4 raters=3 container=['ffmpeg->pcm_s16le 22050Hz mono']` + 算分器自检跑通 |
| 下一步 | ① 明日用同一条 `qa_run.py` 命令续跑剩余 34 条（额度 30/日）→ 拿到**要点命中率**；② MOS 需人盲听 20 分钟（待拍板）；③ 把 §5 的五条发现交给规划侧（不动活文档 ✗） |
| 卡点 | **公开问答 `public-demo` 额度池 30 次/日**（20:33 已 30/30 用尽）⇒ 全量得分表无法一天出；**MOS 无真实评委数据** ⇒ 结果表只能是空模板（不许编 ✗）。两项都不是技术故障，脚本与题库已就绪 ✓ |
