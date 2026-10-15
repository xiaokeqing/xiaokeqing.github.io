# MOS / ABX 主观评测流程（可执行版）· T13-③

> 配套脚本：`scripts/eval/mos_build.py`（出题/发卷）＋ `scripts/eval/mos_analyze.py`（收卷/算分）
> 自动指标（ASR 回译 CER）见 `scripts/eval/asr_cer.py`；问答质量集见 `scripts/eval/qa_*.py`
> 事实口径以 `docs/总账-决策与事实台账-20261015.md` 为准；**凡本文没有实测支撑的数字一律标 `[待核对]`** ✗

---

## 0. 为什么要有这一套

CER 只证明"**机器听得懂**"，不证明"**人觉得像不像桐莉栖**"。TTS 的最终验收是**人耳**，而人耳评测最容易做歪
（不盲、不随机、不设对照、评委被话术带偏）✗ ⇒ 所以流程固定成三件事：**盲、随机、有对照** ✓

---

## 1. 指标定义（写死，跑完不许改口径 ✗）

| 指标 | 定义 | 判读 |
|---|---|---|
| MOS-自然度 | 1~5 分，像不像真人说话 | 主指标，目标 ≥3.5/5 `[待核对]`（该阈值来自 `docs/AI项目升级方案-20261015.md` §5） |
| MOS-可懂度 | 1~5 分，一遍能不能听清 | 下界守卫：低于 3 分说明合成失败，CER 再好看也没用 |
| MOS-音色相似度 | 1~5 分，像不像同一角色 | **有对照才有意义**；单系统时为空 ✗ |
| ABX 正确率 | 三选一（A/B 中挑出与 X 一致的那个）正确率 | 50% = 听不出差别；`>50%` 且精确二项 p<0.05 = **人能分辨**（此时再看谁更好 ✓） |

统计口径：
- 单题 MOS = 该题所有有效评分的算术平均；**空值不算 0 分** ✗
- 95% CI：n≥30 用 1.96σ/√n；n<30 用 t 表（脚本内置，见 `mos_analyze.py` 的 `T_TABLE`）
- ABX 用**精确二项检验**（样本量小时也精确），不用近似
- 系统间比较用**符号检验**（不假设正态）；逐题差值的中位数作为效应量

---

## 2. 对照组怎么选（**没有对照的报告不算 MOS 报告** ✗）

`docs/AI项目升级方案-20261015.md` §3 建议"与 Windows SAPI 占位音做 A/B" —— **本机实测这条走不通**：
`Microsoft Huihui Desktop(zh-CN)` / `Microsoft Zira Desktop(en-US)`，**没有 ja-JP 声音** ⇒ SAPI 读不了日语台词 ✗。
所以按下面顺序选，并在报告里写明选的是哪一种 ✓

| 优先级 | 对照组 | 怎么来 | 强度 | 备注 |
|---|---|---|---|---|
| ① 首选 | **上一代真音色**（线上旧 bank） | 同一批文本、另一代模型的渲染 | 最强 | 与 T17「声音换代 A/B」共用；注意先把 id 对齐 ✗ |
| ② 次选 | **占位音 SAPI**（读**中文**字幕） | `E:\DeepSeek1\work\_eval-t13\make-sapi-control.ps1`（已跑通，8 句 zh-CN，见 `mos/control-sapi-zh/`） | 弱：语言都不同 | **必须在报告里写明"跨语言弱对照"** ✗ 不许说成日语对照 |
| ③ 兜底 | 无对照 | 只跑单系统 MOS | 最弱 | 只能给"绝对分"，不能给"谁更像" |

> 实测命令（本机可复现）：
> ```
> Add-Type -AssemblyName System.Speech
> (New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() |
>   ForEach-Object { $_.VoiceInfo.Name + ' / ' + $_.VoiceInfo.Culture.Name }
> # → Microsoft Huihui Desktop / zh-CN ｜ Microsoft Zira Desktop / en-US   （无 ja-JP）
> ```

---

## 3. 预算与样本量

| 项 | 建议值 | 理由 |
|---|---|---|
| 评委人数 | 5~10 人 | 少于 5 人时 CI 宽到没有结论 ✗ |
| 题量 | 15~20 句 | 约 20 分钟/人（含 ABX），太长发卷回收率会掉 |
| ABX 试次 | 题量的 50% | 一半打分、一半辨听，负担平衡 |
| 总时长 | 准备 0.5h + 收数 0.5 天 | 与 `docs/AI项目升级方案-20261015.md` §3 一致 |

---

## 4. 发卷（执行）

```powershell
$PY = 'E:\DeepSeek1\work\_amadeus-src\.venv\Scripts\python.exe'
cd F:\7AAA\AI\blog
& $PY -X utf8 scripts/eval/mos_build.py `
    --audio-dir   E:\DeepSeek1\work\_tts-trial\sample8\dist `
    --control-dir E:\DeepSeek1\work\_eval-t13\mos\control-sapi-zh `
    --lines       E:\DeepSeek1\work\_tts-trial\lines60-bilingual.json `
    --out-dir     E:\DeepSeek1\work\_eval-t13\mos\run-01 `
    --seed 20261015 --raters R01,R02,R03
```

产出与**谁能看**：

| 文件 | 用途 | 发给评委？ |
|---|---|---|
| `audio/`（不透明 wav） | 播放素材 | ✅ |
| `mos-player-<stamp>.html` | 盲听页（零第三方请求，本地双击） | ✅ |
| `README-<stamp>.md` | 发卷说明 | ✅ |
| `mos-sheet-<stamp>.csv` | MOS 空表 | ✅（也可由页面导出） |
| `mos-abx-<stamp>.csv` | ABX 空表 | ✅ |
| `mos-items-<stamp>.json` | 真实映射 | ❌ 只有主试看 |
| `mos-abx-key-<stamp>.json` | **ABX 答案** | ❌ **绝对不能给** ✗ |

**盲法是怎么保证的**：两套系统的音频都被转成统一的 22050Hz 单声道 PCM wav 并改名为 `<item>_a.wav` / `<item>_b.wav`；
ABX 试次再单独复制一份 `<item>_x.wav`（内容等于 A 或 B 之一）⇒ 文件名、扩展名、码率都看不出身份，
评委翻 devtools 也看不出来 ✓（若本机没有 ffmpeg，脚本会退化成原样复制并在 README 里写明"盲法偏弱" ✗）

---

## 5. 收卷

1. 评委在盲听页填完 → 点「导出我的答卷（CSV）」 → 得到 `mos-sheet-*.csv` 与 `mos-abx-*.csv`（文件名带 rater 列）
2. 把每位评委的两个 CSV 汇总到同一个目录，**文件名加前缀**：`R01-mos-sheet.csv`、`R01-mos-abx.csv`
3. 合并：把各人的行**追加**到一份总表（保留 `rater_id` 列，不要按题聚合后再交 ✗）
4. 回收后立刻把 `mos-abx-key-*.json` 归档，**不要**贴进任何共享文档/聊天 ✗

**表格模板（MOS 总表）**

| rater_id | item_id | order_in_session | MOS_自然度_1-5 | MOS_可懂度_1-5 | MOS_音色像不像_1-5 | 备注 |
|---|---|---|---|---|---|---|
| R01 | greet_first | 1 | 4 | 5 | 4 | |
| R01 | nav_monitor | 2 | 3 | 4 | 3 | 第二句有点电音 |

**表格模板（ABX 总表）**

| rater_id | item_id | order_in_session | X是A还是B | 把握程度_1-5 | 备注 |
|---|---|---|---|---|---|
| R01 | event_bruteforce | 1 | A | 3 | |

---

## 6. 算分

```powershell
& $PY -X utf8 scripts/eval/mos_analyze.py --dir E:\DeepSeek1\work\_eval-t13\mos\run-01
```

产出 `mos-results-<stamp>.md / .csv / .json`，其中：

**结果表模板（贴进报告用）**

| item | n | MOS 均值 | sd | 95% CI | 自然度 | 可懂度 | 音色像不像 |
|---|---|---|---|---|---|---|---|
| `greet_first` | 6 | 4.17 | 0.75 | [3.37, 4.96] | 4.00 | 4.33 | 4.17 |

| ABX | 值 |
|---|---|
| 有效试次 | 12 |
| 命中 | 9 |
| 正确率 | 0.750 |
| 精确二项 p | 0.146 |
| 结论 | p>0.05 ⇒ 本批样本下**不能**断言两套系统可被分辨 `[待核对]`（样本太小） |

---

## 7. 质量控制

- **静音项**：播放无声/破音 ⇒ 该题该评委记缺失，并单独记录为"合成缺陷"，**不许当低分算** ✗
- **可疑答卷**：脚本自动列出"同一题三维度极差 ≥3"的答卷 → 回访评委，**不要直接丢**（可能是真缺陷 ✓）
- **顺序效应**：脚本已按 rater 打乱题目顺序；A/B 播放先后也逐题随机 ⇒ 不许人工重排 ✗
- **评委培训**：先让每位评委听 2 条**校准样本**（一条明显好的、一条明显差的），再正式开始
- **不要给评委看答案**：包括 CER 结果、系统名、本文件 §2 的对照表 ✗

---

## 8. 伦理与边界

- 志愿参与、可随时退出、不收集任何个人信息（只用代号 `R01…`）
- 音频仅在评委本机播放，播放页零第三方请求、不上传任何数据 ✓
- 报告里只出现**代号 + 分数**，不出现姓名/单位

---

## 9. 与 T17 的关系

T17「声音模型换代 A/B」（v3 / v2ProPlus / e100）**直接复用本流程**：
`--audio-dir` 指向候选模型产物、`--control-dir` 指向现役 bank ⇒ 出的是同一份试卷格式，
算分脚本不用改 ✓。区别只在报告里要额外写"模型三代 × 同句同情绪"的对照矩阵 `[待核对]`。

---

## 10. 已知限制（诚实段）

- 本机**没有 ja-JP 系统语音** ⇒ ②号对照只能读中文（跨语言弱对照），别当成日语对照 ✗
- MOS 阈值（≥3.5）来自升级方案，**不是**本项目实测标定 ⇒ 属工程护栏，不是验收门槛 `[待核对]`
- 评委人数、题量、是否做 MOS 属于**待拍板事项**（见升级方案 §8 第①条）
- 本流程到目前为止**只跑通过"出题→收卷→算分"的链路自检**；**没有真实评委数据**，
  因此报告里的 MOS/ABX 结果表是**空表 + 模板**，不得填任何数字 ✗
