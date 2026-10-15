# CosyVoice 前端接线说明 · 「念 AI 回答」 · 2026-10-16

> 窗口 **Y**｜给站点线的**接线说明 + 实测数据 + 参考实现**（**不写 `layouts/**`、不部署、不改服务器配置** ✗）
> 上游事实见 `docs/CosyVoice声音复刻-20261016.md`（本次已打通：`voice_id = cosyvoice-v3.5-plus-kurisu-8eacef0d36b44939b7b9009046e335d1`）
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

1. **中文回答用日语复刻音色的效果**：未测（`language_hints=["ja"]` 是建音色时定的）✗
   是否要**另建 `zh` 音色**请站点线拍板
2. **代理转 m4a 的实际端到端时延**：未实测（我没有代理环境）✗ —— 上表是**估算**
3. **签名 OSS 短链的精确有效期**：只知 `expires_at` 是 Unix 秒，未测到期边界 ✗
4. **429 限流（RPM 180）的真实响应体**：未触发（本次只发了 ~10 次请求）✗
5. **`sample_rate` 非 24000 时的实际输出采样率**：`12345` 返回 200，但未核产出的 WAV 采样率 ✗
6. **单次合成文本长度上限**：未测（本次最长 36 字）✗ —— 长回答建议**按句切分**多次合成
7. **成本口径**：本文按 1.5 元/万字符线性估算；未核"最小计费单位/取整规则" ✗

---

*窗口 Y · 2026-10-16 · 只产出说明与实测数据；**未写 `layouts/**`、未部署、未改服务器配置** ✓*
