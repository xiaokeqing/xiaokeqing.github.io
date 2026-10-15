# `scripts/eval/` · T13 评测包（语音 + 问答）

> 一句话：**给"她说话"和"她答话"两件事各一套可复现的评测** ✓
> 口径与数字来源：`docs/总账-决策与事实台账-20261015.md`；本目录的报告见 `docs/评测报告-语音与问答-20261015.md`
> 红线：**不许假数字** ✗ —— 取不到就写"读不到"，没核实就写 `[待核对]`；脚本一律"可重跑、换输入不改代码" ✓

## 0. 目录

```
scripts/eval/
├── asr_cer.py            T13-① ASR 回译 CER（字符级，日语；逐句表 + 均值 + 分 trigger 均值）
├── qa_run.py             T13-② 问答质量集采集器（公开 /ask 端点；限流/额度感知；断点续跑）
├── qa_score.py           T13-② 打分器（要点命中率 / 拒答正确率 / 引用覆盖 / 幻觉命中）+ 裁判包导出
├── mos_build.py          T13-③ MOS/ABX 出题（不透明音频 + 零第三方请求播放页 + 空表）
├── mos_analyze.py        T13-③ 收卷算分（逐题 MOS + 95%CI + ABX 精确二项 + 可疑答卷）
├── mos_template.md       T13-③ 可执行评测流程（怎么发 / 怎么收 / 表格模板 / 质量控制）
└── datasets/qa-40.jsonl  问答质量集 40 条（含 19 条 fail-closed 拒答用例；每条带期望要点与真实数据锚点）
```

## 1. 环境（本机实测可用）

| 用途 | 解释器 / 工具 | 说明 |
|---|---|---|
| ASR（Qwen3-ASR-0.6B） | `E:\DeepSeek1\work\_amadeus-src\.venv\Scripts\python.exe` | 内含 `qwen_asr 0.0.6` + `torch 2.6.0+cu124` + `av` + `librosa`；模型已装在 `_amadeus-src\assets\models\asr\qwen3-asr-0.6b`（8 文件，sha256 已校验 ✓） |
| 问答采集 | 同上（只用标准库）＋ `ssh secagent-srv1` | 默认走服务器回环，不经 Cloudflare |
| MOS 出题 | 同上 ＋ ffmpeg | ffmpeg 在 `_kurisu-017\video-pipeline\tools\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe`（PATH 里没有也能用；脚本里写死了候选路径） |
| MOS 对照（可选） | Windows SAPI（`System.Speech`） | 本机只有 `zh-CN` / `en-US`，**无 ja-JP** ⇒ 只能做跨语言弱对照 ✗ |

ASR 模型装机（一次即可，已做）：
```powershell
& $PY -X utf8 <解压+校验脚本>   # 按 ASSET_BUNDLE_MANIFEST.json 逐文件 sha256 校验，PASS 才用 ✓
# 落地：_amadeus-src\assets\models\asr\qwen3-asr-0.6b\{config.json,model.safetensors,...}  1.88 GB
```
模型包来源：`F:\7AAA\AI\命运石之门\01-asr-qwen3-0.6b\amadeus-asr-qwen3-0.6b-2026-09-26.zip`
（zip 自身 sha256 = `d9ac6046…b26896`，与同目录 `SHA256SUMS.txt` 一致 ✓）

## 2. 怎么跑

### 2.1 ASR 回译 CER（全自动、零成本）

```powershell
$PY = 'E:\DeepSeek1\work\_amadeus-src\.venv\Scripts\python.exe'
cd F:\7AAA\AI\blog
& $PY -X utf8 scripts/eval/asr_cer.py `
    --audio-dir E:\DeepSeek1\work\_tts-trial\out-ja\dist `
    --lines     E:\DeepSeek1\work\_tts-trial\lines60-bilingual.json `
    --out-dir   E:\DeepSeek1\work\_eval-t13\asr-cer-final
```
- 换数据集 = 换 `--audio-dir` / `--lines`，**文件名按 `<id>.m4a` ↔ `lines[].id` 对齐** ✓
- 三个口径都会出（写报告时**不许只挑好看的** ✗）：`cer_plain` / **`cer_norm`（主口径）** / `cer_kana`
- `--context "牧瀬紅莉栖"` 可给 ASR 领域词偏置（默认关；**禁止**把参考原文当 context —— 那是泄题 ✗）
- 试跑：`--limit 3`；单条重跑：`--id greet_first`

### 2.2 问答质量集

```powershell
# 采集（公开端点限 6 次/分钟 ⇒ 默认 11s 间隔；额度池 30 次/日 ⇒ 用 --max 控量，明日续跑）
& $PY -X utf8 scripts/eval/qa_run.py --out-dir E:\DeepSeek1\work\_eval-t13\qa-runs --interval 11 --max 9
# 打分（+ 导出人工/LLM 裁判包）
& $PY -X utf8 scripts/eval/qa_score.py `
    --dataset scripts/eval/datasets/qa-40.jsonl `
    --raw-dir E:\DeepSeek1\work\_eval-t13\qa-runs\<stamp>\raw `
    --out-dir E:\DeepSeek1\work\_eval-t13\qa-runs\<stamp> `
    --export-judge E:\DeepSeek1\work\_eval-t13\qa-runs\<stamp>\judge-bundle.jsonl
```
- 题库是**数据文件**（`datasets/*.jsonl`），换题库不用改代码 ✓
- 每条记录：`question` / `key_points[].any_of`（可评审的别名表）/ `should_refuse` / `refuse_kind` /
  `must_not_contain`（编造即判幻觉）/ `ground_truth`（真实数据锚点 + 采集时间）/ `calibrated`
- 原始响应**逐条原样落盘**（`raw/<id>.json`），任何人可复核 ✓

### 2.3 MOS / ABX

```powershell
& $PY -X utf8 scripts/eval/mos_build.py `
    --audio-dir   E:\DeepSeek1\work\_tts-trial\sample8\dist `
    --control-dir E:\DeepSeek1\work\_eval-t13\mos\control-sapi-zh `
    --lines       E:\DeepSeek1\work\_tts-trial\lines60-bilingual.json `
    --out-dir     E:\DeepSeek1\work\_eval-t13\mos\run-01 `
    --seed 20261015 --raters R01,R02,R03
& $PY -X utf8 scripts/eval/mos_analyze.py --dir E:\DeepSeek1\work\_eval-t13\mos\run-01
```
完整流程（怎么发/怎么收/表格模板/质量控制/伦理）见 **`mos_template.md`** ✓

## 3. 口径速查（别在报告里临时改 ✗）

- CER = 字符级编辑距离 / 参考长度；文本先 NFKC
- 主口径 `cer_norm` 删空白+标点/符号；`cer_kana` 再把片假名归一为平假名（分离表记差异）
- 要点命中率 = 命中的 key_point / 全部 key_point（**只统计可答类题**）
- 拒答正确率 = 通过 / 拒答题数；通过 = 命中拒答要点 **且** 未出现 `must_not_contain`
- ABX 用精确二项检验；MOS 的 95% CI 小样本用 t 表
- **空值/缺失一律不算 0 分** ✗
