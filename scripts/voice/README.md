# scripts/voice —— 桐莉栖语音合成管线（GPT-SoVITS v3，本机 CUDA）

> 这套脚本的产物 = `static/kurisu/voice/` 下的 `*.m4a` / `*.webm` / `*.envelope.json` / `bank.json`。
> **纪律：整条管线只写文件，绝不播放**（脚本里没有任何 sounddevice / playsound / winsound / ffplay 调用）。要试听就自己点文件或开 `review.html`。

## 0. 一句话

台词库（`lines60-bilingual.json`，`ja` 进 TTS / `zh` 只做字幕）→ GPT-SoVITS v3 本机合成（日语）→
裁静音 → 响度闭环归一到 **-16 LUFS / true peak ≤ -1.5 dBTP** → 首尾 40ms fade → 编码 **m4a(AAC 48k) + webm(Opus 40k)**
→ **从最终 m4a 解码**重算口型包络 → 写 `bank.json`（含 sha256/durationMs/trigger 分组）+ 自检。

## 1. 环境要求

| 项 | 要求 | 说明 |
|---|---|---|
| Amadeus 源码 | 任意 clone（默认 `E:\DeepSeek1\work\_amadeus-src`，可用 `KURISU_AMADEUS_ROOT` 覆盖） | 必须已 `uv sync --locked --extra voice --extra vad --extra local-cu124` |
| Python | clone 的 `.venv`（Python 3.12.x） | `uv run --locked --no-sync python <脚本>` |
| torch | **2.6.0+cu124 / torchaudio 2.6.0+cu124** | 只有 CUDA 路径吃到 CUDA Graph / static-KV；CPU 会慢一个数量级 |
| GPU | ≥6GB 显存（实测 RTX 3060 Laptop 6GB：torch 峰值 ~2.0GB，含桌面 nvidia-smi 峰值 ~4.0GB） | 峰值时留 ≥500MB 余量 |
| ffmpeg/ffprobe | 便携构建（默认 `E:\DeepSeek1\work\_kurisu-017\video-pipeline\tools\ffmpeg-master-latest-win64-gpl\bin`，可用 `KURISU_FFMPEG_DIR` / `KURISU_FFMPEG` / `KURISU_FFPROBE` 覆盖） | 需要 `loudnorm` / `alimiter` / `aac` / `libopus` |
| `jieba-fast` | **故意不装**（见 §5） | 用 `jieba_fast_shim.py` 顶替（纯 Python `jieba`） |

模型/参考音频都在 Amadeus 的素材包里：`assets/models/gpt-sovits/**`、`assets/audio/reference/**`
（`tools/external_assets.py install <voice zip>` 装；**Qwen/ASR 不需要**）。

## 2. 参考音频：**日语**（这条最关键）

| 项 | 值 |
|---|---|
| 音频 | `assets/audio/reference/kurisu_reference.wav`（44.1kHz 立体声，7.56s） |
| 语种 | **日文** |
| 文本 | `そういえば,正式に自己紹介していませんでしたね……牧瀬紅莉栖です.改めてまして,よろしく` |
| 来源 | `config/catalog/voice/voice_reference_profile.json` 的 `TTS_REF_TEXT_JA.default` |

⚠️ **坑**：`local_tts_infer.py` 里"`config.settings` 导入失败时"的兜底参考文本**是另一句**（约 3s 长），
与 7.56s 的音频对不上，会让音色/语调跑偏。脚本一律从 `config.settings` 读真值，读不到才用 catalog 那句。
⚠️ **坑**：拿中文文本去合成 = 吃不到参考音色（我们踩过）。**目标语言必须跟参考一致 = 日文**。

## 3. 情绪参考（可选，0.17.0α with-emotions 包）

`assets/audio/reference/emotions/references.json`（`language: ja`）提供
`angry / sad / shy / blush / surprised / disappointed`（`blush` 与 `shy` 共用同一段）。
用法：`infer(..., semantic_reference=(音频, 日文文本, "日文"))` —— 脚本里 `--emotions on` 会自动按台词库的
`emotion` 字段做映射。上游原生路由要求 `TTS_OUTPUT_LANGUAGE=日文` + `ENABLE_EXPERIMENTAL_V3_EMOTION_ROUTING=true`。
**包里没有 happy/normal 参考**，"开心"用 `blush`/`shy` 近似（台词库里已标注）。

## 4. 命令

```powershell
# 0) 每次 uv sync 之后都要重装 shim（uv 会 prune site-packages）
python scripts\voice\jieba_fast_shim.py

# 1) 合成 + 后处理（-16 LUFS / -1.5 dBTP / 裁静音+fade / m4a+webm / 包络从最终文件重算）
cd <amadeus clone>
uv run --locked --no-sync python <repo>\scripts\voice\synth.py `
    --mode all60 --lang 日文 --emotions on --device cuda `
    --out E:\DeepSeek1\work\_tts-trial\out-ja --tag all60ja
#    --mode one|three|batch12|all60   --ids greet_first,event_bruteforce   --no-post

# 2) 打包 bank.json + manifest 片段 + 预算/自检
python scripts\voice\build_bank.py --out E:\DeepSeek1\work\_tts-trial\out-ja --tag sample8 `
    --ids greet_first,nav_monitor,status_all_clear,event_bruteforce,fallback_no_data,banter_tsundere,emo_calm_1,emo_surprised_2

# 3) 只验后处理链路（不需要 torch）：用现有 wav 跑裁静音/响度/编码/包络
python scripts\voice\postprocess.py --selftest
```

产物布局：`out-ja\{raw,master,dist,envelope,meta}\`、`summary-*.json`、`bank*.json`、`verify.json`、`voice-budget.json`。

## 5. 本机踩过的坑（照做可以省几小时）

1. **`jieba-fast==0.53` 装不上**：PyPI 上 0.48~0.53 **只有 sdist、从来没有 wheel**，本机没有 MSVC 14.0 → 编译必失败。
   绕行：`uv sync ... --no-install-package jieba-fast` + `jieba_fast_shim.py`（`from jieba import *`，
   并且**必须** `sys.modules['jieba_fast.posseg'] = jieba.posseg`，否则 `import jieba_fast.posseg as psg` 会 ModuleNotFoundError）。
   代价：中文分词慢一点；API 不变。要"零偏离"就得装 MSVC Build Tools 重新编译。
2. **`--lang` 必须日文**（见 §2），否则音色不对。
3. `uv sync` 会 prune 掉 shim → **每次 sync 后重装**。
4. **FlashAttention 未装**（Windows+cp312 无轮子，需 MSVC+CUDA 工具链）→ 走 SDPA + CUDA Graph/static-KV；
   BigVGAN 也走 PyTorch 实现（无 nvcc）。两者都在日志里显式打印，别当成"已启用"。
5. 包络必须用 **`audioop.rms`**（C 实现）。自写浮点 RMS 与既有 12 句包络**逐点不一致**（364 点里 165 点不同），
   因为近静音窗 1e-4 的差就会翻 `round(...,4)` 的边界。Python 3.13 起 audioop 被移除 → 届时需要换实现并重新对齐。
6. `loudnorm` 的二次通过（linear）在本机只做到 -20.3 LUFS；脚本改成"实测 → 线性增益 → 限幅 → 再实测"的闭环（同时守 TP）。

7. **产物不要落在仓库目录里**：本机实测 **ffmpeg 子进程对 F:\7AAA\AI\blog\\... 写入会 EACCES**
   （python/PowerShell 能写、ffmpeg 不能）→ 脚本默认把产物放到 %TEMP%\kurisu-voice-out（可用 KURISU_OUT 覆盖），
   postprocess.py --selftest 同理。仓库里只放脚本/JSON/README，音频产物放仓库外，确认后再拷进 static/kurisu/voice/。

## 6. 文件

| 文件 | 作用 |
|---|---|
| `synth.py` | 合成主入口（模型只加载一次；接后处理；`--mode/--lang/--emotions/--ids/--no-post`） |
| `postprocess.py` | 裁静音 → 响度闭环 → fade → m4a/webm → 从最终文件重算包络（`--selftest` 可免 torch 自检） |
| `build_bank.py` | 打 `bank.json` / `bank_12lines.json` / manifest 片段 / 体积预算 / 自检 |
| `make_bilingual.py` | 生成/维护双语台词库（`lines60-bilingual.json`） |
| `jieba_fast_shim.py` | `jieba-fast` 的纯 Python 替身（含自检） |
| `make_report_table.py` | 生成"id→日文→中文→时长→情绪→来源"对照表 |
| `lines60-bilingual.json` | 60 句双语台词库（greeting8/page_intro6/status10/event12/idle_banter12/fallback3/emotion9） |
