# CosyVoice 前端接线说明 · 「念 AI 回答」 · 2026-10-16

> 窗口 **Y**｜给站点线的**接线说明 + 实测数据 + 参考实现**（**不写 `layouts/**`、不部署、不改服务器配置** ✗）
> 上游事实见 `docs/CosyVoice声音复刻-20261016.md`。本次共建成**两个**复刻音色：
> `cosyvoice-v3.5-plus-kurisu-<…>`（`language_hints=["ja"]`，日语 3 句实测 ✓）
> 与 `cosyvoice-v3.5-plus-kurisuzh-<…>`（`language_hints=["zh"]`，中文 2 句实测 ⇒ **仍按日语读，见 §5.1b** ✗）
> 本文所有数字都是**本窗口实测**，未核实的标 `[待核对]` ✓

---

## 1. 链路与两个可选形态

```
形态 A（纯前端，最简）      前端拿到回答正文 → 前端直连 DashScope → 得签名 URL → fetch 音频 → decodeAudioData → 播放
形态 B（只读代理，推荐）    前端拿到回答正文 → 我方只读代理（持 key）→ 代理调 DashScope → 代理取回音频
                            → 代理原样回吐 wav（或转 m4a）→ 前端播放；代理同时**记账/限流/降级**
```

**推荐 B**，三条硬理由（都可复现，不是偏好）：

| 理由 | 说明 |
|---|---|
| **key 绝不能进前端** ✗ | 前端直连必须把 DashScope key 下发到浏览器 ⇒ 任何人可提取 ✗。B 把 key 留在服务端 ✓ |
| **计费/额度只能由可信端记** ✓ | 平台 `usage.characters` 只有调用方看得到；B 由代理累计 ⇒ 才可能做"用掉 >80% 自动退回只出字幕" ✓ |
| **失败降级要有单一判定点** ✓ | B 在代理侧"失败/超时/超额度"统一返回明确状态码 ⇒ 前端只认一个开关，不会各页各写一套 ✗ |

> A 形态**只允许**用于本地试跑（key 放本机环境变量），**不许上线** ✗。

---

## 2. 调用参数（**照抄即可**）

### 2.1 合成请求（我方代理内部 / 或形态 A 直连）

```
POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer
Authorization: Bearer <DASHSCOPE_API_KEY>      ← 只在服务端；绝不下发前端 ✗
Content-Type: application/json
```
```json
{
  "model": "cosyvoice-v3.5-plus",
  "input": {
    "text": "<只放回答正文，见 §6 红线②>",
    "voice": "cosyvoice-v3.5-plus-kurisu-8eacef0d36b44939b7b9009046e335d1",
    "format": "wav",
    "sample_rate": 24000
  }
}
```

| 字段 | 取值 | 实测依据 |
|---|---|---|
| `model` | `cosyvoice-v3.5-plus` | 站主已开通；1.5 元/万字符；RPM 180 |
| `voice` | `cosyvoice-v3.5-plus-kurisu-8eacef0d36b44939b7b9009046e335d1` | 本次复刻产物；**必须与 `target_model` 一致**，否则失败 |
| `format` | `wav` | 实测 3/3 成功；输出 = **24 kHz / mono / 16-bit**（浏览器可直接播 ✓） |
| `sample_rate` | `24000` | 实测 24000 ✓；⚠ 实测 `12345` **也返回 200**（未严格校验）⇒ **不要依赖它报错** ✗ |

> **语言**：本次复刻传的是 `language_hints: ["ja"]`（**建音色时**定，不是合成时的参数）。
> 合成时**没有** language 参数 ⇒ 中文正文用这个日语复刻音色**效果未知** `[待核对]`
> ⇒ 若"念 AI 回答"要念**中文**回答，**建议另建一个 `language_hints:["zh"]` 的音色**（同一参考音频也可，
> 或换中文参考音频），别硬用日语音色念中文 ✗。**这一点请站点线先拍板。**

### 2.2 合成响应（**字段按实测**）

```json
{
  "output": {
    "audio": {
      "data": "",
      "id": "audio_f2bbef1f-…",
      "url": "http://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/prod/cosyvoice-v3.5-plus/…wav?Expires=…&OSSAccessKeyId=…&Signature=…",
      "expires_at": 1792168957
    },
    "finish_reason": "stop"
  },
  "usage": { "characters": 33 },
  "request_id": "f2bbef1f-d8f2-9af4-b690-8b55888c59e2"
}
```

| 字段 | 用途 | 注意 |
|---|---|---|
| `output.audio.url` | **音频本体**，需再 GET 一次才拿到 wav | ★**签名 OSS 短链**（`Expires` 是 Unix 秒）；**别存 URL 当长期资源** ✗ 会被签名过期 |
| `output.audio.data` | 实测恒为 `""`（非流式） | 别指望它填 base64 ✗（**流式**模式才在 `data` 里给 base64 分片） |
| `usage.characters` | **计费字符数** ← 每次都记 | 实测比文本字数多 ~14.3%（见 §5） |
| `request_id` | 排障/对账 | 建议写进前端日志的 `debug` 字段 ✓ |

> ★ **签名 URL 的有效期**：实测 `expires_at - 现在 ≈ 1 小时量级` `[待核对]` 精确时长。
> ⇒ 代理形态**必须**当场把音频取回（流给前端或转存），**不能**把签名 URL 直接甩给前端缓存 ✓

---

## 3. 失败码表（**全部实测**）

| HTTP | `code` | `message` | 触发条件（实测用例） | 前端应做什么 |
|---|---|---|---|---|
| **401** | `InvalidApiKey` | `No API-key provided.` | 不带 `Authorization` | 记日志；**静默降级字幕** ✓ 别弹错 |
| **400** | `InvalidParameter` | `Model not exist.` | `model=no-such-model-xyz` | 配置错误 ⇒ 告警（不是用户错） |
| **400** | `InvalidParameter` | `[cosyvoice:]Engine return error code: 418` | **音色与模型不匹配 / 音色不存在 / 缺 `voice`** | **最常见的配置错**：核对 `voice` 的 `target_model` 前缀 ✓ |
| **400** | `InvalidParameter` | `Request format is invalid!` | `format=flac`（不支持） | 固定用 `wav` ✓ |
| **400** | `InvalidParameter` | `Please ensure input text is valid.` | `text=""` | **前端先判空**，别发请求 ✓ |
| **400** | `BadRequest.InputDownloadFailed` | `download audio failed` | **建音色时** `url` 服务端拉不到（本次踩过：CF 链路 ✗） | 只在建音色阶段出现；见 §7 |
| 429 | `Throttling` `[待核对]` | — | 超 RPM 180 / 超并发 | 退避重试一次，再失败 ⇒ 降级字幕 ✓ |
| **200** | — | — | 正常 | 播 |

> ★ `[cosyvoice:]Engine return error code: 418` 是**本次遇到最多**的坑：它把
> "音色不存在""音色与模型不匹配""缺 voice" **都归成同一个 418** ⇒ 前端**无法**从报错区分，
> 只能靠"我方音色白名单"在发请求前挡掉 ✓（见 §6 护栏）。

---

## 4. 包络（口型）：**前端 Web Audio 算，不需要后端写包络文件** ✓

### 4.1 与现有 12 句**完全同口径**（这是关键）

现有素材的包络契约（`static/kurisu/voice/bank.json` 与 `_dev/build_voice_bank.py` 原文）：
```
{ "sampleRate": 8000, "hopMs": 10, "values": [0..1] }
envelopeFormula: "clamp(RMS(10ms) * 3.75, 0, 1)，首窗保底 0.12，停止发 0
                  （0.08 是播放器侧静音阈值，不写进包络）"
```
⇒ **前端对云端 WAV 用同一条公式算**，就能直接喂现有的口型驱动，**无需任何后端改动** ✓

### 4.2 本窗口**实测验证**了这条公式（不是照抄规格）

对 §5 的 3 句 24 kHz WAV 直接按上式算（`_cosy\envelope_check.py`）：

| 文件 | 采样率 | 窗数 | **理论窗数**（数据字节 ÷ 480） | 首值 | 最大值 | 均值 | 0 值窗数 |
|---|---|---|---|---|---|---|---|
| `s1_intro.wav` | 24000 | **640** | **640** ✓ | 0.12 | 1.0 | 0.4432 | 148 |
| `s2_business.wav` | 24000 | **992** | **992** ✓ | 0.12 | 1.0 | 0.4733 | 138 |
| `s3_emotion.wav` | 24000 | **1184** | **1184** ✓ | 0.12 | 1.0 | 0.4221 | 174 |

⇒ 窗数**逐条严格相等** ✓、首窗保底 0.12 ✓、全程落在 `[0,1]` ✓、末窗为 0（停止发 0）✓
⇒ **公式在云端音频上可用**（不是只对本地 8 kHz m4a 成立）✓

### 4.3 参考实现（**前端可直接复制**）

```js
// 口径与 _dev/build_voice_bank.py 一致：hopMs=10 / gain=3.75 / 首窗保底 0.12 / 停止发 0
// 用法：先 decode 再算；算完再起播（见下方时序注意）
const HOP_MS = 10, GAIN = 3.75, FIRST_FLOOR = 0.12;

async function decodeToPcm16(arrayBuffer) {
  const ac = new (window.AudioContext || window.webkitAudioContext)();
  const ab = await ac.decodeAudioData(arrayBuffer);
  if (ab.numberOfChannels > 1) {                 // 现状是 mono，但别假设
    console.warn('[tts] multi-channel audio, using channel 0');
  }
  const ch = ab.getChannelData(0);               // Float32, [-1,1]
  return { ac, data: ch, sampleRate: ab.sampleRate, durationSec: ab.duration };
}

// 返回 { sampleRate, hopMs:10, values:[0..1] } —— 与 bank.json 的 envelope 同结构
function envelopeFromChannelData(data, sampleRate, hopMs = HOP_MS) {
  const win = Math.round(sampleRate * hopMs / 1000);
  const values = [];
  for (let i = 0; i + win <= data.length; i += win) {
    let sum = 0;
    for (let j = 0; j < win; j++) { const s = data[i + j]; sum += s * s; }
    const rms = Math.sqrt(sum / win);            // Float32 已在 [-1,1] 归一化，无需再除 32768
    values.push(Math.min(1, Math.max(0, rms * GAIN)));
  }
  if (values.length) values[0] = Math.max(values[0], FIRST_FLOOR);
  return { sampleRate, hopMs, values };
}

// 播放：<audio> 或 AudioBufferSourceNode 都行；口型定时器按 hopMs 栅格推进
async function ttsAndEnvelope(wavArrayBuffer) {
  const { ac, data, sampleRate } = await decodeToPcm16(wavArrayBuffer);
  const env = envelopeFromChannelData(data, sampleRate);
  // 把 env.values 交给现有口型驱动（与 12 句同一入口，逐 hopMs 取一个值）
  return { ac, env };
}
```

**时序注意（实测推论，非要紧）**：算包络是**纯 CPU、一次性**的（1,184 窗量级 ⇒ 毫秒级），
但 `decodeAudioData` 是异步的 ⇒ **先把包络算完再起播**，避免"音频已经响了、口型还没数据" ✓
（若想更稳，可把 decode+算包络放在**用户点击之后、请求等待期间**的空档里做 ✓）

---

## 5. 体积与时延实测（供选型）

### 5.1 3 句实测（**这是选 形态A/B 的判据**）

| # | 用途 | 朗读文本（日语） | 文件 | 时长 | 体积 | 合成 TTFB / 总 | 音频下载 TTFB / 总 | 计费字符 |
|---|---|---|---|---|---|---|---|---|
| 1 | 自我介绍 | はじめまして。牧瀬クリスです。よろしくお願いします。 | `_cosy\s1_intro.wav` | 3.20 s | **153,644 B** | **1.973 s** / 1.974 s | 0.554 s / 0.593 s | 29 |
| 2 | 业务解说 | 公開されている読み取り専用のエンドポイントを、ここにまとめておきました。 | `_cosy\s2_business.wav` | 4.96 s | **238,124 B** | **1.814 s** / 1.815 s | 0.095 s / 0.165 s | 42 |
| 3 | 情绪句 | はあ、また同じことを聞くの？しょうがないわね、一回だけよ。 | `_cosy\s3_emotion.wav` | 5.92 s | **284,204 B** | **2.058 s** / 2.059 s | 0.099 s / 0.156 s | 33 |

```
音频规格：24 kHz / mono / 16-bit WAV ⇒ **48,000 B/s**（= 153,600 ÷ 3.20 ✓ 逐条自洽）
WAV 传输耗时（从签名 OSS 短链取，本机直连）：0.156 ~ 0.593 s ✓（很快）
端到端可播时延（合成 TTFB + 下载总）≈ 1.91 s ~ 2.16 s → 首字节约 **1.8 ~ 2.1 s**
```

### 5.1b ★ 中文念读：**判定不可行** ✗（2026-10-16 定案 · 依据 + 替代方案）

**起因**：站主不赌"日语复刻音色念中文"⇒ 另建一个 `language_hints=["zh"]` 的音色并用**中文**试 2 句。

```
（已删）voice_id = cosyvoice-v3.5-plus-kurisuzh-f14ecf82e7244fa494055493e85ec5dd
create_voice: HTTP 200 / 4.417 s / usage.count=1 / language_hints=["zh"] / prefix=kurisuzh
参考音频仍是 crs_1393.wav（日语素材）—— 目的是"用她的音色说中文"⇒ 用 zh 提示建音色 ✓
```
| # | 朗读文本（中文） | 文件 | 时长 | 体积 | 合成 TTFB/总 | 下载 TTFB/总 | 计费字符 |
|---|---|---|---|---|---|---|---|
| 1 | 这个问题我需要查一下公开端点。 | `_cosy\zh1_endpoint.wav` | 2.88 s | 138,284 B | 1.559/1.560 s | 0.110/0.137 s | 29 |
| 2 | 公开知识库里没有依据，我不给结论。 | `_cosy\zh2_no_basis.wav` | 3.68 s | 176,684 B | 1.639/1.639 s | 0.106/0.142 s | 32 |

**客观指标：ASR 回译（`qwen3-asr-flash`，同模型同口径，手法同 `scripts/eval/asr_cer.py`）**

| 样本 | 原文 | ASR（`language=zh`） | 结论 |
|---|---|---|---|
| zh1 | 这个问题我需要查一下公开端点。 | **萨卡文大噶主要赛者公开探听。** | 「这个问题我需要查一下」→「萨卡文大噶主要赛者」 |
| zh2 | 公开知识库里没有依据，我不给结论。 | **公開知識庫，伊波次优伊克，结论。** | 「没有依据，我不给」→「伊波次优伊克」；**只有"公开知识库/结论"念对** |
| 对照 ja1 | はじめまして。牧瀬クリスです。… | はじめまして**マキセクリス**です。よろしくお願いします。 | **几乎全对**（含人名 `マキセクリス` ✓） |
| 对照 ja3 | はあ、また同じことを聞くの？… | はあまた同じことを聞くのしょうがないわね一回だけよ。 | **全对** |

⇒ ★**判定：即使指定 `language_hints=["zh"]`，这个（以日语素材复刻的）音色念中文时仍被按"日语读音"念** ✗
（ASR 不给中文提示时直接吐**日文假名** `サカムンダイ…`；给了 `zh` 提示后仍是"日语音节 + 汉字近音"；
而**同一 ASR 对日语合成几乎逐字全对** ⇒ 排除了"ASR 本身不行"这个替代解释 ✓）

**★ 最终判定（2026-10-16 由规划侧拍板）：中文念读 = 不可行** ✗
```
两条依据（都实测过，不是推测）：
  ① `language_hints=["zh"]` 单独无效 —— 仍按日语读音念（上表 zh1/zh2）；且删掉 zh 音色也改变不了这一点
  ② 本项目**没有可用的中文参考音频**：既有参考音频 crs_1393.wav 是**日语**素材；
     资源盘点里也没有同一说话人的 10–20 s 中文清晰语音 ⇒ **穷尽** ✗
处置：`kurisuzh` 音色**已删** ✓（`delete_voice` HTTP 200；随后 `list_voice prefix=kurisuzh` → `total_count=0` ✓）
      `kurisu`（ja）音色**保留** ✓（日语合成 ASR 几乎逐字全对 ✓ 有需要时可用）
```

> ★**替代方案（正解，先记录不实现）**：她本来就"**说日语、配中文字幕**"—— 这是全项目既定口径 ✓
> ⇒ "念 AI 回答"的正解 = **念日语版**：模型把回答转成**一句日语口吻**（中文字幕照旧），用 **ja 音色** 合成 ✓
> ⇒ 这需要后端多输出一个字段（例如 `speakJa`，一句 ≤40 字）⇒ **属于后端改动 ⇒ 需一次重建** ✗
> ⇒ **列为二期项**（2026-10-16 不下手：当天后端已重建两次 ✗）
> ⇒ 触发条件：**站主明确要"她真的出声念回答"** 时再排期 ✓

> **"像不像她"我给不出结论** ✗ —— 我是文本模型，**没有听觉**。
> 我只能给上面这张**客观可懂度**证据；**音色相似度请人耳盲听**。
> 建议对照听：`_cosy\s1_intro.wav`（日语，音色本身）↔ `_cosy\zh1_endpoint.wav`（同音色念中文，**已判不可行**）↔
> `static/kurisu/voice/greet_first.m4a`（线上现有 12 句）✓

### 5.2 两条路的取舍（**站点线请选一条**）

| | 形态 A：前端直播 WAV ✓ | 形态 B：代理转 m4a ✓ |
|---|---|---|
| 端到端首声 | ~1.9–2.2 s（实测口径） | ~2.0–2.4 s `[待核对]`（多一跳代理 + 转码） |
| 传量/句 | **150–290 KB** ✗（WAV 未压缩） | 参照现有 12 句：**3 s 级 m4a ≈ 23–38 KB** ✓（约 1/5~1/6） |
| 现有 12 句体积对照 | — | `static/kurisu/voice/*.m4a` 实测 **19,600–63,302 B**，同句 webm 略小 |
| 口型包络 | 前端 Web Audio 现算 ✓（§4，已实测 ✓） | 代理顺手回吐 envelope（要后端写文件 ✗ 违反"不用为它改 Java"） |
| key 安全 | ✗ 必须下发 key ⇒ **不许上线** | ✓ key 留服务端 |
| 额度记账/降级 | ✗ 前端各自为政，记不准 | ✓ 单点可信 |
| 结论 | 只用于**本地试跑** | **推荐上线**（但会多一次转码与代理带宽） |

> **如果选 B 且要口型**：包络应**仍由前端现算**（`decodeAudioData` 对 m4a 一样能解 ✓），
> 这样后端只需"取回音频 → 转 m4a → 原样吐出"，**完全不用写包络文件** ✓（符合父给的口径 ✓）。

### 5.3 带宽估算（给运维）
```
按"每次回答念 5 s"估：WAV ≈ 240 KB/次 ✗ ｜ m4a ≈ 45 KB/次 ✓ `[待核对]`
CF 链路本身慢（总账 §2.5 实测：22KB 页面 6~19 s ✗）⇒ **大体积 WAV 走 CF 会更痛** ✗
⇒ 这也是推荐"代理转 m4a"的一条现实理由 ✓（且代理可走直连/内网，不吃 CF 的慢）
```

---

## 6. 红线与护栏（**父给的四条 + 额度 80%**）

### 6.1 四条红线（**必须实现，缺一条就算没接线**）

| # | 红线 | 实现点（建议） |
|---|---|---|
| ① | **只在用户点击后才出声** ✓ | 所有 TTS 调用挂在一个"用户手势已发生"的布尔门后（与现有 L1 播放同款门控）；**禁止**回答一到就自动念 ✗ |
| ② | **只念回答正文** ✓ | 送 `text` 前**剥掉**：引用列表 / `citations` / 状态字段 / "参考来源" / 免责声明 / emoji；**只取 `answer` 正文字段** |
| ③ | **失败/超时 ⇒ 静默降级为只出字幕** ✓ | 任一非 200 或超时 ⇒ **只显示字幕、不弹错误、不刷 console.error** ✗（用 `console.info` 级） |
| ④ | **每次记费并累计** ✓ | 每次响应把 `usage.characters` 累加到计数器（代理侧落盘 + 前端埋点各一份） |

### 6.2 成本护栏：**用掉 >80% 免费额度 ⇒ 自动退回"只出字幕"**

```
免费额度            REF = 10000 字符（站主口径；到期 2026-12-21）
软阈值              SOFT = 0.80 × REF = 8000 字符
建议开关名          ttsEnabled = (usedChars < SOFT) && serverSwitch && userGesture
                    （三个条件**与**关系：额度够 ∧ 服务端总开关 ∧ 用户已手势）
```

| 判定点 | 位置 | 动作 |
|---|---|---|
| **主判定点（必须）** | 我方只读代理，**在调 DashScope 之前** | `usedChars + estChars(text) > SOFT` ⇒ **不发上游请求**，直接回 `tts_disabled` ⇒ 前端只出字幕 ✓ |
| 次要判定点（可选） | 前端 | 持有代理回吐的 `ttsDisabled` 标志；置位后**连请求都不发** ✓（省一次往返） |
| 运维告警（可选） | srv1 定时任务 | 读代理落盘的 `usedChars`，过 80% / 95% 各告警一次 ✓（复用现有 notify） |

```
estChars(text) 估算口径：实测平台计数 ≈ 文本字数 × 1.143（3 句实测 26→29 / 36→42 / 29→33）
  保守取   ceil(len(text) * 1.20)   ⇒ 宁可早停，不许超付 ✓
记账口径：以**平台返回的 usage.characters 为准**（估算只用于"发之前"的预判）✓
失败调用不计费：实测 400/401 响应**无 usage 字段** ⇒ 只在 200 时累加 ✓
```

> **开关名请站点线按现有命名风格定稿**（我给的是建议名，未落代码 ✗）。

---

## 7. 复刻侧的两个前置提醒（若以后要再建音色）

1. **参考音频 URL 必须用 `direct.xiaokeqing.cn`** ✗ 别用 apex/www（经 CF 会让 DashScope 拉不到：
   实测 `BadRequest.InputDownloadFailed`，50.5 s 失败；换 `direct.` ⇒ 200 一次成功）✓
   —— 已写入 `docs/总账-决策与事实台账-20261015.md` §2.5 ✓
2. **别把临时参考音频放进 `releases/site-*`** ✗ —— 站点发布是**整树替换**，
   本次就被发布切走一次（软链 `001942 → 003417`），文件当场掉出线上树。
   要长期托管请放 `site/` 之外的独立目录 + 另开映射（**须先报站主** ✓）。

---

## 8. `[待核对]` 清单

**已结清（不再是待核对）**
```
① 中文念读可行性 → **判不可行** ✗（§5.1b：zh 提示无效 + 无中文参考音频）｜处置：删 kurisuzh、留 ja ✓
② ffmpeg 依赖选型 → **选 A（apt 官方包）** ✓（§9.3）｜部署本身仍**暂不部署** ✗
③ 额度是否跨天归零 → **不归零** ✓（依据：站主控制台"10,000/10,000 剩余 · 过期 2026/12/21"= 总量额度）（§9.5）
④ `kurisuzh` 音色是否保留 → **已删** ✓（`delete_voice` 200；`list_voice prefix=kurisuzh` → total_count=0）
```

**仍待核对**
1. **"像不像她"（音色相似度）**：我**无听觉**，给不出结论 ✗ ⇒ 需人耳盲听（样本与对照见 §5.1b 末尾）
2. **代理转 m4a 的实际端到端时延与码率**：未实测（我没有代理环境）✗ —— §9.4 的尺寸是**估算**
3. **签名 OSS 短链的精确有效期**：只知 `expires_at` 是 Unix 秒，未测到期边界 ✗
4. **429 限流（RPM 180）的真实响应体**：未触发（本次只发了 ~12 次请求）✗
5. **`sample_rate` 非 24000 时的实际输出采样率**：`12345` 返回 200，但未核产出的 WAV 采样率 ✗
6. **单次合成文本长度上限**：未测（本次最长 36 字）✗ —— 长回答建议**按句切分**多次合成
7. **成本口径**：本文按 1.5 元/万字符线性估算；未核"最小计费单位/取整规则" ✗
8. **`speakJa`（替代方案的日语字段）的生成质量**：未测（属二期后端改动）✗

---

## 9. 形态 B 实施草案（**只出方案，暂不部署** ✗；落点由父/站点线定）

> ### ★ 部署状态：**暂不部署** ✗（2026-10-16 规划侧拍板）
> ```
> 触发条件：**站主明确要"她真的出声念回答"** 时才排期 ✓
> 前置：① 先报规划侧（我这边今天不部署、不动服务器 ✗）② 站主点头后才派运维/站点线执行
> 已定：**若做 ⇒ ffmpeg 走 A（apt 官方包）** ✓ —— 理由：来源可信、可 apt 审计升级，
>       比静态包（来源非 Ubuntu 官方 ✗ 供应链面更大）稳 ✓；`+100MB` 依赖可接受 ✓
>       ★「纯 Python 编 AAC」**已排除且经确认** ✗ 别再试 ✓
> 但：**nginx 反代（§9.6）属于"须先报站主"的动作** ✗ —— 即便将来做，也要先报 ✓
> ```
> ### ★ 前置的另一条（若走替代方案）
> 若采 §5.1b 的**替代方案（念日语版 + 中文字幕）**，则"念回答"用的是 **ja 音色** ⇒
> 仍需 §9 这个代理（key 不进前端 + 记账 + 转 m4a + 降级），只是 `voice` 固定为 ja ✓
> 另需后端多输出 `speakJa` 字段 ⇒ **属后端改动、需一次重建** ⇒ **二期项** ✗

### 9.1 落点与环境实测（**srv2，2026-10-16 实测**）

| 项 | 实测值 | 影响 |
|---|---|---|
| 落点建议 | **srv2**（与站点同机，走既有 CF 隧道即可暴露） | srv1 入站除 22 **全被安全组拦** ✗（实测 14 个端口全 000）⇒ **不能**做对外服务 |
| Python | **3.10.12** ✓ | 可用 stdlib `http.server`/`socketserver`，**不引第三方框架**更稳 |
| `flask` / `uvicorn` / `numpy` / `pydub` / `soundfile` / `av` | **全部没有** ✗ | ⇒ 别依赖它们 |
| stdlib 音频 | **`audioop` 在** ✓（py3.10） | WAV 解析/重采样可用；**但编不了 AAC** ✗ |
| **ffmpeg / ffprobe / sox / lame / opusenc** | **全部没有** ✗ | ⇒ **转 m4a 必须新装 ffmpeg**（决策点，见 §9.3） |
| apt 候选 | `ffmpeg 7:4.4.2-0ubuntu0.22.04.1`（universe，可装）✓ | 腾讯云镜像源可达 |
| 资源 | 4 vCPU / 40G 盘余 **16G** ✓ | 代理很轻；转码是短时 CPU 尖峰，建议 `CPUQuota` |
| 空闲回环端口 | `18190 / 18191 / 18290` 实测**均空闲** ✓ | 建议 `127.0.0.1:18190`（**只绑回环** ✓） |
| 现有单元命名风格 | `secagent-*`（`.service` + `.timer`）✓ | 建议单元名 `secagent-voice-proxy.service` |
| 复用告警 | `/opt/secagent/scripts/notify.sh`（存在 ✓） | 80%/95% 额度与降级率告警直接复用它 ✓ |

### 9.2 接口契约（**定稿草案，请站点线按此实现**）

```
POST /api/voice/speak
Content-Type: application/json
（可选）X-Voice-Token: <静态令牌>   ← 建议加；值放代理环境变量，前端从页面配置注入
```
```json
请求 {
  "text": "这个回答的正文，≤300 字，纯文本",
  "voice": "ja|zh",          // 可选，默认按站点配置；不接受任意 voice_id ✗
  "lang": "ja|zh",           // 可选，默认与 voice 配对
  "want": "m4a|wav"          // 可选，默认 m4a
}
```
```json
成功 200 {
  "ok": true,
  "audioUrl": "/api/voice/audio/<token>.m4a",   // 我方短链（同源，省 CORS）
  "m4aBytes": 24800,
  "chars": 29,
  "quotaPct": 2.13,
  "charsTotal": 213,
  "degraded": false
}
降级 200 {           // ★降级也用 200，前端只认 degraded/开关 ⇒ 不会弹错 ✗
  "ok": true, "degraded": true, "reason": "quota_soft_cap", "quotaPct": 81.2
}
被拒 4xx/5xx { "ok": false, "degraded": true, "reason": "<见下表>" }
```
**`reason` 码表（前端只需要"有 degraded 就只出字幕" ✓）**

| `reason` | 触发 | HTTP |
|---|---|---|
| `quota_soft_cap` | `usedChars + estChars > 0.80 × 10000` | 200（降级） |
| `quota_hard_cap` | `usedChars ≥ 10000` | 200（降级） |
| `text_too_long` | `len(text) > 300` | 400 |
| `empty_text` | 去空白后为空 | 400 |
| `markup_rejected` | 检出 SSML/指令/标签（`<speak`、`<break`、`<emphasis`、`<prosody`、`<phoneme`、`<sub`） | 400 |
| `rate_limited` | 超每 IP 限流 | 429 |
| `upstream_timeout` | DashScope 超时（代理侧上限 15 s） | 502（降级） |
| `upstream_error` | 上游非 200（含 401/400/429，**原文入服务端日志，不回前端**） | 502（降级） |
| `transcode_failed` | 取回音频但转码失败 | 502（降级） |
| `disabled` | `?tts=off` 或运维总开关关 | 200（降级） |

**三条"不做"（红线，写进实现注释）**
```
① 只允许纯文本：检出 SSML/指令即 400 markup_rejected（不给上游 ⇐ 也省额度）✗
② 上游错误**只回中间码**，绝不把 DashScope 原始 message/key 透给前端 ✓
③ 音频 URL 用**同源短链**（代理内存/临时文件，TTL 60 s，一次性删），不转发签名 OSS 短链 ✗
```

### 9.3 ffmpeg 依赖（**已定案：走 A（apt 官方包）** ✓）

`srv2` 现状 **完全没有任何转码器**（§9.1 实测）⇒ 转 m4a 曾有三条路，**2026-10-16 规划侧已拍板选 A** ✓：

| 方案 | 具体 | 优点 | 风险/代价 | 结论 |
|---|---|---|---|---|
| **A** | apt 装系统包 `ffmpeg 7:4.4.2`（Ubuntu jammy universe，腾讯云源 ✓） | 来源可信、可 `apt` 审计与升级、`libavcodec` 带 native AAC 编码器 ⇒ `-c:a aac` 可用 ✓ | 约 +100 MB 依赖（**已确认可接受** ✓）；改服务器软件环境 ⇒ 部署时须先报规划侧 ✗ | ★**选定** ✓ |
| B | 静态单文件（johnvansickle `ffmpeg-release-amd64-static` 或 BtbN builds 的 linux64）⇒ 解到 `/opt/secagent/tools/ffmpeg/` | 不污染系统包管理 | 需外网下载 + 校验 SHA256；来源非 Ubuntu 官方 ⇒ **供应链面更大** ✗ | 落选 ✗ |
| C | 不转码，回吐 **wav** | 零新依赖 ✓ | 150–290 KB/句 ✗ 体积目标（≤100 KB）达不到 | 落选 ✗ |

**建议**：A（或 B，若站主不希望动 apt）。**无论 A/B，都必须先 `ffprobe` 自检**（能解出音频头）再上线 ✓
**纯 Python 编 AAC 不可行** ✗（无库、无编码器；`audioop` 只能算/重采样 PCM）—— 不浪费时间试

### 9.4 转码参数草案与尺寸估算（**估算是标 `[待核对]` 的，未实测** ✗）

```
ffmpeg -v error -y -i in.wav -ac 1 -ar 24000 -c:a aac -b:a 32k -movflags +faststart out.m4a
尺寸估算（按 24 kHz/mono/16-bit WAV 实测 48,000 B/s 换算）：
  2.88 s 句 → WAV 138,284 B → m4a@32k ≈  11.5 KB  [+容器开销]  ⇒ 约 **1/12**
  3.68 s 句 → WAV 176,684 B → m4a@32k ≈  14.7 KB              ⇒ 约 **1/12**
  5.92 s 句 → WAV 284,204 B → m4a@32k ≈  23.7 KB              ⇒ 约 **1/12**
对照：线上现有 12 句 m4a 实测 **19,600–63,302 B** ✓ ⇒ 32 kbps 量级与现有资产同一档 ✓
⇒ **远低于 ≤100 KB/句 的目标** ✓（若想更稳可给 48k/64k；`[待核对]` 实际码率与听感）
```

### 9.5 存储与记账

```
密钥   代理环境变量 DASHSCOPE_API_KEY（systemd EnvironmentFile=/opt/secagent/.env.voice-proxy, 0640 root:xksite）
       绝不写进前端、绝不写进日志（日志里 `Authorization` 一律打码 ✓）
记账   累计文件 /var/lib/secagent/voice-proxy/usage.json {usedChars, calls, degraded, day, updatedAt}
       口径：**只在 HTTP 200 且上游返回 usage.characters 时累加** ✓（实测失败调用无 usage ⇒ 不计费 ✓）
       估算（发之前预判）：ceil(len(text) * 1.20)（实测平台计数 ≈ 字数×1.143）
音频   临时目录 /run/secagent-voice-proxy/（RuntimeDirectory，重启即清 ✓），音频 TTL 60 s 由代理自清 ✓
额度归零口径  ★**已定案：不按天归零** ✓（**不**归零）
       依据：站主控制台"免费额度"页截图 —— **10,000 / 10,000 剩余 · 过期时间 2026/12/21**
             ⇒ 这是**总量额度 + 固定过期日**，**不是每日额度** ⇒ 计数器**只增不减**，跨天**不**归零 ✓
       ⇒ 即 `usedChars` 一直累计到 2026-12-21；软阈值 80%（8,000 字符）一旦越过，
         代理**永久**返回 `degraded`（除非运维手工重置或站主扩容）✓
```

### 9.6 暴露方式（**需改 nginx 配置 ⇒ 属于"须先报站主"的动作** ✗）

```
现状问题：/api/voice/* 现在会被 nginx 的 `location /` 兜底成 **/index.html（200/text/html）** ✗
          （本窗口实测：任意不存在路径都回 index.html 63,811 B）
⇒ 必须新增一个 location 把 /api/voice/ 反代到 127.0.0.1:18190：
      location ^~ /api/voice/ { proxy_pass http://127.0.0.1:18190; ... }
   并加 `limit_req`（建议 10r/m per IP）与 `proxy_read_timeout 20s`
曝光路径：CF 隧道 secagent-static 四条路由已指向 127.0.0.1:18080 ⇒ **改 nginx 一处即可，不动隧道/DNS** ✓
回滚：删 location + `nginx -s reload`（5 秒级）；或 killswitch 变体（同现有做法）✓
```

### 9.7 前端接线要点（**给站点线，最小改动版**）

```
① 用户手势已发生后（与现有 L1 播放同款门控）才请求 POST /api/voice/speak ✓
② 只取回答正文（剥掉 citations/状态/URL）再放进 text ✓
③ 响应无 `degraded`：new Audio(json.audioUrl) 播放；口型用 §4.3 现算 ✓
   响应有 `degraded`（或请求失败/超时）：**只出字幕、静默** ✓（console.info 级，绝不 error ✗）
④ `?tts=off` 或本地记住"用户关过声音" ⇒ **连请求都不发** ✓
⑤ 每次成功把 json.chars 累加进前端埋点（与代理侧对账用）✓
```

### 9.8 部署步骤草案（**给运维/站点线，按序执行；未执行** ✗）

```
0. ★**前置：先报规划侧并取得站主点头**（今天**不做** ✗）；选型已定：**A（apt 官方包）** ✓；额度口径已定：**不归零** ✓
1. 装 ffmpeg：`apt-get install -y ffmpeg`（Ubuntu jammy universe，7:4.4.2）→ `ffprobe -version` 自检
2. 放代理脚本 /opt/secagent/scripts/voice-proxy.py（stdlib only，含 §9.2 契约）
3. 建 /opt/secagent/.env.voice-proxy（0640 root:xksite，含 DASHSCOPE_API_KEY）—— **key 从 srv1 .env 取，不经人眼** ✓
4. 建单元 secagent-voice-proxy.service（User=xksite / 绑 127.0.0.1:18190 / CPUQuota=50% / MemoryMax=256M）
5. ★改 nginx：加 `location ^~ /api/voice/` 反代 + limit_req → `nginx -t` → `nginx -s reload`
   （**这一步属于"须先报站主"的动作** ✗ 且与站点线互斥写 nginx ⇒ 同文件单写纪律）
6. 自检：curl 回环 127.0.0.1:18190 一次"你好"（走真实 key）→ 校验 m4a 可解、usage 落盘
7. 外网自检：curl https://xiaokeqing.cn/api/voice/speak（**注意 CF 链路**）→ 200 + m4a
8. 回归：主页/五页仍 200；`/api/voice/*` 非 GET/POST 405；限流生效（连打 20 次看 429）
9. 回滚预案：停单元 + 删 nginx location + reload（同现有 killswitch 纪律）
```

> ### ★ 本节全部为**草案**，**未执行任何一步** ✗（我未装 ffmpeg、未放脚本、未建单元、未改 nginx）
> 触发条件与前置见本节开头的"部署状态"横幅 ✓

---

## 10. 附录：本次全部产物的绝对路径

```
音频样本（仓库外）
  E:\DeepSeek1\work\_cosy\s1_intro.wav  s2_business.wav  s3_emotion.wav    （日语 3 句，音色 kurisu ✓ 保留）
  E:\DeepSeek1\work\_cosy\zh1_endpoint.wav  zh2_no_basis.wav               （中文 2 句；音色 kurisuzh **已删** ✗
                                                                            样本留作"不可行"的证据 ✓）
留证
  resp-s{1,2,3}*.json / resp-zh{1,2}*.json          合成响应（含 usage.characters）
  create-voice-direct.out.json                       ja 音色复刻响应（含 voice_id）
  create-voice-zh.out.json / delete-voice-zh.out.json / list-kurisuzh.out.json   zh 音色：建 → 删 → 列表复核
  asr2-zh1_endpoint.json / asr2-zh2_no_basis.json / asr2-s1_intro.json / asr2-s3_emotion.json
  envelope-verify.json  synth-result.json  zh-result.json  probe-bill.json
```


---

*窗口 Y · 2026-10-16 · 只产出说明与实测数据；**未写 `layouts/**`、未部署、未改服务器配置** ✓*
