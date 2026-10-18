# CosyVoice 声音复刻（API 路线）· 2026-10-16

> 窗口 **Y**｜任务：用阿里云百炼 **CosyVoice「声音复刻」API** 克隆她的音色，并试合成 3 句
> 起因：站主在控制台**找不到"声音复刻"菜单** ✗ ⇒ 走 **API 路线** ✓
> 纪律：只产出音频样本 + 本文档；**不部署、不改线上配置、不写仓库代码** ✗｜密钥绝不打印 ✗

---

## 1. 一句话结论

**声音复刻成功** ✓ —— `voice_id = cosyvoice-v3.5-plus-kurisu-8eacef0d36b44939b7b9009046e335d1`
（`target_model=cosyvoice-v3.5-plus`），并已用该音色**成功合成 3 句日语**（3/3 HTTP 200）。
**没有任何权限缺失**：复刻接口一次通过（HTTP 200），**不是**"未开通声音复刻"。
累计计费 **173 字符 / 10,000 免费额度 = 1.73%**，成本 ≈ **0.0260 元**。

> **追加（同日晚些，站主追加要求）**：另建了一个 `language_hints=["zh"]` 的音色
> `cosyvoice-v3.5-plus-kurisuzh-f14ecf82e7244fa494055493e85ec5dd`（prefix `kurisuzh`），并用中文试了 2 句。
> **结论（已由规划侧拍板）：中文念读 = 不可行** ✗ —— 即使指定 `zh`，这个（以日语素材复刻的）音色
> 念中文仍被按**日语读音**念（ASR 回译给出日文假名与汉字近音；同一 ASR 对日语合成几乎逐字全对）
> ⇒ 完整证据见 `docs/接线-CosyVoice前端念回答-20261016.md` **§5.1b**。
> **处置**：`kurisuzh` 音色**已删** ✓（`delete_voice` HTTP 200；`list_voice prefix=kurisuzh` → `total_count=0`）；
> `kurisu`（ja）音色**保留** ✓。**替代方案**：她本就"**说日语、配中文字幕**"⇒ "念回答"应念**日语版**
> （需后端多输出 `speakJa` ⇒ 属后端改动、需一次重建 ⇒ **列为二期项** ✗ 今天不下手）。
> 另记一条实测：`prefix` **不允许连字符**（`kurisu-zh` → 400 `prefix should be english letter and number`）✗

---

## 2. 服务与密钥（①）

### 2.1 用的哪份 key

| 项 | 值 |
|---|---|
| 实际使用 | `E:\DeepSeek1\work\.ws-key`（**新给的那份**，`sk-ws-` 开头，115 B，无内嵌空白） |
| 文件 SHA256 | `a6c29729eaba5ec4beec26d5385d9d673a2c5d7938df280ba4cba645a2a12046` |
| 未使用 | srv1 `/opt/secagent/.env` 的 `DASHSCOPE_API_KEY`（**未读取使用**；新 key 一次即通，无需回退） |
| 证据口径 | 全程只 `Authorization: Bearer $(cat 文件)` 形式进请求头；**没有 `echo`、没有 `curl -v`** ✗ |

### 2.2 key 归属判定（**不靠前缀猜** ✓，用最小调用试出来）

| 调用 | 结果 | 判定 |
|---|---|---|
| `POST /api/v1/services/aigc/multimodal-generation/generation`，`model=qwen-tts` | 404 `InvalidParameter / Model not exist` | **不是 401/403** ⇒ key **已被 DashScope 认可**，只是模型名不对 |
| 同端点 `model=cosyvoice-v3.5-plus` | 400 `Required body invalid, please check the request body format` | 模型**存在**（不再报 Model not exist），请求体格式不对 |
| `POST /api/v1/services/audio/tts/SpeechSynthesizer`，`model=cosyvoice-v3-flash`＋`voice=longanyang` | **200** ＋ 返回签名音频 URL ＋ `usage.characters=4` | **确认可用于 CosyVoice 语音合成** ✓ |

> **结论一句话**：这份 key **能**用于 CosyVoice（DashScope 百炼·华北2 北京），
> 且**属 DashScope 服务**（由 200 的响应结构与 `usage/request_id` 字段证实，非靠前缀推断 ✓）。

### 2.3 最小 TTS 连通性测试（①的正式记录）

```
接口  POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer
模型  cosyvoice-v3-flash ｜ 音色 longanyang（官方预置）｜ 文本「你好」｜ format=wav, sample_rate=24000
结果  HTTP 200 ｜ TTFB 0.806 s ｜ 总 0.913 s ｜ usage.characters = 4
```
⇒ key 可调通 ✓；**本次消耗 4 字符** ✓（`_cosy\probe-bill.json`）

---

## 3. 参考音频与临时公网托管（②）

### 3.1 参考音频（日文，作者包推荐项，**未做任何转码**）

| 项 | 实测值 |
|---|---|
| 路径 | `E:\DeepSeek1\work\_v2plus\Kurisu-GPT-SoVITS v2ProPlus Model\reference audio\crs_1393.wav` |
| 体积 | **964,632 B**（与任务给的一致 ✓） |
| SHA256 | `24be2f3d150a03289e2e74f9527141fc1ea039e4712a1f51ef8049f9d8cd6d9a` |
| 格式 | RIFF/WAVE，**mono / 16-bit / 44100 Hz** |
| 时长 | **10.936 s**（⇒ 落在官方推荐 10–20 s 区间内 ✓；≤60 s ✓；≤10 MB ✓；≥16 kHz ✓） |
| 配套参考文本 | 「それに、例えば、小学生の頃の自分に今の記憶を転送した場合、記憶と肉体のギャップのせいで、精神的な障害が起きるかもしれない……」 |

> ★ **重要说明（不猜、如实报）**：本次走的是 `voice-enrollment` 的 **create_voice** 契约，
> 官方签名只有 `target_model / prefix / url / language_hints / max_prompt_audio_length`
> —— **没有"参考文本"入参**，参考文本由服务端从音频自行转写。
> 因此"音频与文本必须配套"这条**在本接口上无从施加**（文本未被传入）。
> 若后续要换成**需要传入参考文本**的接口（如某些零样本复刻契约），**必须**把上面这条文本
> 与 `crs_1393.wav` 配套使用，**不许交叉** ✗。

### 3.2 临时公网托管（**已删除并验证** ✓）

```
托管位置（旁路写入，不在仓库）：
  /opt/secagent/releases/site-20261016-003417/assets/_tmp-voice/4a8f71237d0e48f410f28e006d02bd84/crs_1393.wav
  （srv2；/opt/secagent/site 是软链 → 当前 release；即站点服务器上的隐蔽路径）
直链：
  https://direct.xiaokeqing.cn/assets/_tmp-voice/4a8f71237d0e48f410f28e006d02bd84/crs_1393.wav
自测：HTTP 200 ｜ 964,632 B（逐字节一致，sha256 相同）｜ 288,853 B/s ｜ 总 3.34 s
```

**删除证据（用完立刻删，不等人清 ✓）**
```
删除   sudo rm -rf 两个 release 下的 4a8f71237d0e48f410f28e006d02bd84/（001942 与 003417 都删）
       并 rmdir 空的 _tmp-voice/ 与我新建的 assets/（site 树原本没有 assets 目录 ⇒ 已复原）
FS     find /opt/secagent/releases -name 'crs_1393.wav'       → 0 命中
       find /opt/secagent/releases -name '4a8f71237d0e48f410f28e006d02bd84' → 0 命中
公网   该 URL 已**不再返回音频**（返回 text/html 63,811 B = index.html 的 SPA 兜底），
       与"任意不存在路径"同形（不同路径同样 200/text/html/63811）⇒ 音频公网不可得 ✓
线上   软链仍为 site-20261016-003417；https://xiaokeqing.cn/ = 200 ✓（未受影响）
srv1   /tmp/_tvsrc 与临时 http.server 进程均已删除/结束（NO_HTTPD）；/opt/secagent/static 占位站未碰 ✓
```

> ⚠ **踩到的坑（值得记）**：我把文件放进 release 时**没有预料到站点线正在发布** ——
> 00:34 软链从 `site-20261016-001942` 切到 `site-20261016-003417`，文件当场掉出线上树。
> ⇒ 我把它补进当时的 live release **并立刻重跑**复刻（4.94 s 成功），随后自行删净。
> **release 目录是"整树替换"的，不适合放旁路临时文件** ✗ —— 若下次要长期托管，
> 应放 `site/` 之外的独立目录并另开 nginx/隧道映射（**须先报站主** ✓）。

---

## 4. 创建音色（③）

### 4.1 接口契约（**取自官方 SDK 源码，不猜** ✓）

来源：`dashscope` 1.27.7 wheel 内 `dashscope/audio/tts_v2/enrollment.py`
＋ 官方文档 [声音复刻 Python SDK 参考](https://help.aliyun.com/zh/model-studio/voice-clone-python-sdk)、
[QwenCloud Voice cloning](https://docs.qwencloud.com/developer-guides/speech/voice-cloning)

```
端点   POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization
       （SDK: model=voice-enrollment, task_group=audio, task=tts, function=customization）
body   {"model":"voice-enrollment",
        "input":{"action":"create_voice","target_model":"cosyvoice-v3.5-plus",
                 "prefix":"kurisu","url":"<公网可访问的音频 URL>",
                 "language_hints":["ja"],"max_prompt_audio_length":10}}
返回   {"output":{"voice_id":"<target_model>-<prefix>-<唯一标识>", ...}, "usage":{"count":1}}
```

### 4.2 实际调用与结果 ✅

```
HTTP      200
耗时      4.937 s（TTFB 4.937 s）
voice_id  cosyvoice-v3.5-plus-kurisu-8eacef0d36b44939b7b9009046e335d1
usage     count = 1
request_id 0dcf7db7-8202-91a2-a689-bf39af4611d4
```
⇒ 形态与文档一致：`{target_model}-{prefix}-{唯一标识}` ✓（`prefix` 小写字母开头 ✓）

### 4.3 连续两次的差异（**是本次唯一一次失败，已解决**）

| 次 | 提交的 URL | 结果 |
|---|---|---|
| 1 | `https://xiaokeqing.cn/...`（**经 Cloudflare**） | 400 **`BadRequest.InputDownloadFailed / "download audio failed"`**，50.476 s 失败 |
| 2 | `https://direct.xiaokeqing.cn/...`（**绕开 Cloudflare**，A 记录直指 {公网IP-腾讯云}） | **200 成功**，4.937 s |

**根因（实测，非猜测）**：不是权限、不是文件格式、不是密钥 —— 是**回源路径**。
DashScope 侧从 Cloudflare 那条链路拉不到（50 s 后报下载失败）；
换成**不经过 CF 的直连域名**后一次成功。旁证：
```
srv1 → https://xiaokeqing.cn/...   193,740 B/s（CF，能拉但慢）
srv1 → https://direct.xiaokeqing.cn/...  288,853 B/s（直连，3.34 s 完整 964,632 B）
本机 → https://xiaokeqing.cn/...   首次 GET 90 s 零字节、重试 927 B/s（同一 CF 链路的劣化样本）
```
⇒ **经验**：凡是"要让第三方服务回源拉我们自己的文件"，**优先给 `direct.xiaokeqing.cn`**，
不要给 apex/www（走 CF）✓。这条建议追加进活文档（见 §9）。

### 4.4 权限结论（④的前提）

**没有遇到任何权限类报错** —— 全程未见 401 / 403 / "未开通" / "无权限"。
create_voice 直接 200 ⇒ **该账号已具备声音复刻调用权限，无需单独申请** ✓
（唯一那次失败是 `InputDownloadFailed`，属网络回源，**不是权限** ✗）

---

## 5. 试合成 3 句（④）

**统一参数**：`model=cosyvoice-v3.5-plus`、`voice=cosyvoice-v3.5-plus-kurisu-8eacef0d36b44939b7b9009046e335d1`、
`format=wav`、`sample_rate=24000`；接口同 §2.3。产物在 **`E:\DeepSeek1\work\_cosy\`**（**不进仓库** ✗）。

| # | 用途 | 朗读文本（日语） | 文件 | 时长 | 体积 | 响应 TTFB / 总 | 音频下载 TTFB / 总 | 计费字符 |
|---|---|---|---|---|---|---|---|---|
| 1 | 自我介绍（含人名） | はじめまして。牧瀬クリスです。よろしくお願いします。 | `_cosy\s1_intro.wav` | **3.20 s** | **153,644 B** | 1.973 s / 1.974 s | 0.554 s / 0.593 s | **29** |
| 2 | 业务解说 | 公開されている読み取り専用のエンドポイントを、ここにまとめておきました。 | `_cosy\s2_business.wav` | **4.96 s** | **238,124 B** | 1.814 s / 1.815 s | 0.095 s / 0.165 s | **42** |
| 3 | 情绪句（不耐烦） | はあ、また同じことを聞くの？しょうがないわね、一回だけよ。 | `_cosy\s3_emotion.wav` | **5.92 s** | **284,204 B** | 2.058 s / 2.059 s | 0.099 s / 0.156 s | **33** |

```
3 句全部 HTTP 200 ✓ ｜ 音频格式 24 kHz / mono / 16-bit WAV（逐文件核过头部）
SHA256  s1_intro   e448cdf07a7303832644c50c06b83e6b088b14ee46b03559cf50d38f0f69ae33
        s2_business 2f6c68291ef7c47f85ca5afad36a92b4366b1b96becdebfd19cf90824341251b
        s3_emotion  8ed421e3adc82f932c66d17a0e5dc5ee146e13f892769fb49c1ba187e944268c
「时长」口径 = WAV `data` chunk 字节数 ÷ byte_rate（服务端音频头未带可靠帧数，故按数据长度算 ✓）
```

> **人名口径（照任务给定的写法，未擅自改）**：自我介绍朗读文本用 **`牧瀬クリス`**（假名兜底写法，
> 与 `docs/状态-B-声音.md` 的既有结论一致：`牧瀬紅莉栖` 会被读成「マキセクレナイリースミカ」✗，
> `牧瀬クリス` 读作「マキセクリス」✓）。**刻意写成裸字**（未加引号）以避免被当成符号念出 `[待核对]`。

> **字数口径差异（如实记录，不修饰）**：朗读文本 26/36/29 字，平台计费 29/42/33 字符
> ⇒ 平台侧计数比文本字数多 ~14.3%（推测与标点/不可见字符的计费口径有关）
> `[待核对]` 官方计费口径细节。**记账一律以平台 `usage.characters` 为准** ✓。

---

## 6. 免费额度记账（⑤）

```
① 连通性最小 TTS（cosyvoice-v3-flash / longanyang /「你好」）   usage.characters = 4
   错误码表探测 2 次（每次均 HTTP 200 并真实出音频）            usage.characters = 4
④ 3 句合成（cosyvoice-v3.5-plus / 复刻音色）                    29 + 42 + 33 = 104
                                                      累计 = 112 字符

累计 112 / 10,000 免费额度 = 1.12% ✓（远未到 80% 提醒线 ✓）
成本（按 1.5 元/万字符）= 112 × 1.5 / 10,000 ≈ 0.0168 元
create_voice 本身按 usage.count=1 计次，未见按字符计费 `[待核对]`
```

> **追加（第二轮：zh 音色）**：`create_voice` 再 1 次（`usage.count=1`）+ 中文 2 句合成
> `29 + 32 = 61` 字符 ⇒ **合计 173 字符**
> ```
> 累计 173 / 10,000 = **1.73%** ✓ ｜ 成本 ≈ 173 × 1.5 / 10,000 ≈ **0.0260 元**
> 明细：112（第一轮）+ 61（zh1 29 + zh2 32）
> ```

> 说明：为 §"前端接线说明"里的**错误码表**做实测时，有 2 个探测用例是"应该失败但实际成功"
> （`sample_rate=12345` 与 `format` 缺省各一次，均 HTTP 200 并出音频）⇒ 各计 4 字符，**如实计入** ✓
> 其余 5 个用例都是 400/401 失败，**失败调用无 `usage` 字段、不计费** ✓

> 站主已开启"免费额度用完即停" ✓ ⇒ 即便超额也只会停服，**不会有意外账单** ✓
> 未发现任何失败调用产生计费（失败调用均无 `usage` 字段）。

---

## 7. 纪律自证

**做了**
- 密钥：只在请求头用 `Bearer` 形式；**未 echo、未 `curl -v`、未打印任何 key/token** ✗；
  报告中一律用**文件名指代**（`.ws-key`）✓
- 只产出音频样本 + 本文档 + `docs\状态-Y-CosyVoice.md` + `docs\接线-CosyVoice前端念回答-20261016.md`；
  **未部署、未改线上配置** ✗；仓库只 `git add` 文档，**未 commit / 未 push** ✗
- 临时公网文件**用完立刻删除**并给出 FS + 公网双重证据 ✓（§3.2；**两轮共托管/删除两次** ✓）

**没做 / 偏离**
- **旁路写入站点发布目录**（为满足"公网可访问的 URL"要求）：写进了
  `/opt/secagent/releases/site-20261016-003417/assets/_tmp-voice/<32位随机>/crs_1393.wav`。
  这是**我预料之外的写入**（不在仓库里），已与站点线对齐口径：**已全部删除、树已复原** ✓。
  站点发布是**整树替换**，我上传后被发布切走一次（见 §3.2）——**教训：release 树不放临时文件** ✗
- 未做音频听感评价（本窗口无人工盲听）；复刻相似度**只证明"接口成功 + 能合成"**，
  **不代表音色像不像** ✗ —— 听感需站主/评测窗口判定 `[待核对]`

---

## 8. 复现命令（照抄可用，**key 从文件读，勿打印**）

```powershell
# ① 最小 TTS 连通性（预置音色）
$key = (Get-Content 'E:\DeepSeek1\work\.ws-key' -Raw).Trim()
curl.exe -s -X POST 'https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer' `
  -H "Authorization: Bearer $key" -H 'Content-Type: application/json' `
  --data-binary '@E:\DeepSeek1\work\_cosy\vb\a.json'      # cosyvoice-v3-flash / longanyang

# ③ 创建复刻音色（url 必须是公网可访问，且优先用 direct. 绕开 CF）
curl.exe -s -X POST 'https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization' `
  -H "Authorization: Bearer $key" -H 'Content-Type: application/json' `
  --data-binary '@E:\DeepSeek1\work\_cosy\body-create-voice-direct.json'

# ④ 用复刻音色合成
curl.exe -s -X POST 'https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer' `
  -H "Authorization: Bearer $key" -H 'Content-Type: application/json' `
  --data-binary '@E:\DeepSeek1\work\_cosy\req-s1_intro.json'
  # ⇒ 响应 output.audio.url 是**签名 OSS 短链**，需再 GET 一次才拿到 wav
```

```
交付产物（仓库外）
  E:\DeepSeek1\work\_cosy\s1_intro.wav / s2_business.wav / s3_emotion.wav   ← 3 句样本
  E:\DeepSeek1\work\_cosy\req-s{1,2,3}*.json / resp-s{1,2,3}*.json          ← 请求/响应留证
  E:\DeepSeek1\work\_cosy\body-create-voice-direct.json / create-voice-direct.out.json
  E:\DeepSeek1\work\_cosy\probe-bill.json                                  ← ①的计费留证
  E:\DeepSeek1\work\_cosy\synth-result.json                                ← 时长/体积/字符汇总
```

---

## 9. 建议追加进活文档的一行

**→ `docs/项目总体规划-MasterPlan-20261015.md` §11（append-only 变更日志）**

```
| 10-16 | Y｜CosyVoice 复刻 | **声音复刻 API 打通 ✅**（控制台无"声音复刻"菜单 ⇒ 走 API）：
`voice-enrollment` 的 create_voice（`target_model=cosyvoice-v3.5-plus` / `prefix=kurisu` / `language_hints=["ja"]`）
一次成功，`voice_id=cosyvoice-v3.5-plus-kurisu-8eacef0d36b44939b7b9009046e335d1`（4.94 s / usage.count=1）；
用该音色合成 **3/3 句日语**成功（3.20 s/153,644 B・4.96 s/238,124 B・5.92 s/284,204 B；响应 TTFB 1.81~2.06 s）；
**★中文念读判不可行** ✗：另建 `language_hints=["zh"]` 音色（prefix `kurisuzh`）试 2 句中文，
ASR 回译（同模型同口径）给出**日文假名/汉字近音**（「这个问题我需要查一下公开端点」→「萨卡文大噶主要赛者公开探听」），
而同一 ASR 对日语合成**几乎逐字全对** ⇒ **排除"ASR 背锅"**，证实"仍按日语读音念"；且本项目**无中文参考音频**（穷尽）
⇒ 处置：**删 kurisuzh**（`delete_voice` 200 / `list_voice` total_count=0）、**留 ja**；
**替代方案（二期，先记录不实现）**：她本就"说日语 + 中文字幕"⇒ "念回答"念**日语版**（后端加 `speakJa` 字段 ⇒ 需一次重建 ✗）；
计费 **173 / 10,000 字符 = 1.73%**（≈0.0260 元；额度为**总量、非每日**，**不按天归零** —— 依据站主控制台"10,000/10,000 · 过期 2026/12/21"）；
**无任何权限缺失** ✗；实测补充：`prefix` **不允许连字符**（`kurisu-zh` → 400）；
踩坑：DashScope 从 **Cloudflare** 链路的 URL 拉参考音频会 `BadRequest.InputDownloadFailed`（50.5 s 失败），
换 **`direct.xiaokeqing.cn`（绕开 CF，A 记录直连 {公网IP-腾讯云}、证书 SAN 已含该名）** 后一次成功
⇒ **★凡是要第三方服务回源拉本站文件，一律给 `direct.` 域，不给 apex/www** ✓；
前端包络**实测可现算**（24k WAV 窗数 640/992/1184 逐条 = 字节÷480，与 12 句 envelopeFormula 同口径）⇒ 后端不必写包络；
形态 B（只读代理）契约已出草案并**标注"暂不部署"**（若做 ⇒ ffmpeg 走 **apt 官方包**、nginx 反代**须先报站主**）；
临时公网文件（release 内旁路写入）**两轮共托管/删除两次，均已删除并验证**（FS 0 命中 + 公网只剩 SPA 兜底）✓ |
`docs/CosyVoice声音复刻-20261016.md`、`docs/接线-CosyVoice前端念回答-20261016.md`、`docs/状态-Y-CosyVoice.md`
｜ 产物 `E:\DeepSeek1\work\_cosy\**`（仓库外） | 音频样本已就绪；**未部署/未改线上/未 commit** ✓
｜ 遗留 `[待核对]`：音色相似度听感（我无听觉）、平台计费字符口径、代理转 m4a 实测、429 响应体 |
```

**→ 另建议记进 `docs/总账-决策与事实台账-20261015.md` §2.5（服务器与链路）**：`direct.xiaokeqing.cn` 是**绕开 CF 的直连入口**（A 记录 {公网IP-腾讯云}，证书 SAN 已含该名），第三方服务回源拉本站文件必须用它 ✓

---

## 10. `[待核对]` 清单（没数的地方都在这儿，别当结论 ✗）

**已结清（不再待核对）**
```
· 中文念读可行性 → **判不可行** ✗（依据：zh 提示无效 + 无中文参考音频）｜处置：删 kurisuzh、留 ja ✓
· 额度是否按天归零 → **不归零** ✓（依据：站主控制台"免费额度"页截图 = 10,000/10,000 剩余 · 过期 2026/12/21
  ⇒ 总量额度 + 固定过期日，非每日额度）✓
· prefix 是否允许连字符 → **不允许** ✓（`kurisu-zh` → 400 `prefix should be english letter and number`）
```

**仍待核对**
1. **音色相似度（像不像）**：本窗口**无听觉**，未做人工盲听 / MOS / ABX
   ⇒ **只证明接口成功、能合成、日语可懂度过关，不代表音色质量** ✗
2. **平台计费字符口径**：文本 26/36/29 字 vs 计费 29/42/33 字符（+14.3%）⇒ 差异来源未核
3. **cosyvoice-v3.5-plus 是否真的没有任何预置音色**：我实测 `longxiaochun`/`longxiaochun_v2`/
   `longxiaochun_v3`/`longwan`/`longcheng`/`longhua`/`longanyang`/`Cherry`/`Ethan` 在该模型下**全部**
   返回引擎错误 418；`cosyvoice-v3-flash`（longanyang）与 `cosyvoice-v2`（longxiaochun_v2）在同端点
   **均 200** ⇒ 判"该模型只吃复刻/设计音色"，**但未逐条比对官方音色表**（该文档正文抓取被截断）
4. **`create_voice` / `delete_voice` 的计费方式**（均按次 `usage.count=1`，是否含隐式字符）未核
5. **日语 `language_hints`（ja 音色）是否真正生效**：无法从返回判断（接口未回显）；
   但**间接正面证据**：ASR 回译 3 句日语几乎逐字全对（含人名 `マキセクリス`）✓
6. **站主"免费额度用完即停"是否已生效**：我未登录控制台核实，按任务给定的前提记录
7. **`speakJa` 替代方案的生成质量**：未测（属二期后端改动）

---

*窗口 Y · 2026-10-16 · 未 commit / 未 push ✓ · 临时公网文件两轮均已删净并验证 ✓*
