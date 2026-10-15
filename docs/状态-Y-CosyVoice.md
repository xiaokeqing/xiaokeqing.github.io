# 状态-Y-CosyVoice（窗口 Y）· 2026-10-16

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 `docs/窗口分工规范-20261015.md` §四 ✓

```
任务号 ：CosyVoice 声音复刻（API 路线）+ 前端接线说明 + zh 音色实测 + 代理方案草案
状态   ：已完成 ✓（无阻塞项）
         三条待拍板**已由规划侧全部结清** ✓：
           ① 中文念读 → **判不可行** ✗（zh 提示无效 + 无中文参考音频）⇒ 已删 kurisuzh、留 ja ✓
           ② 代理 ffmpeg 依赖 → **选 A（apt 官方包）** ✓（部署本身**暂不做** ✗ 触发条件 = 站主明确要"她真出声念回答"）
           ③ 额度口径 → **不按天归零** ✓（依据：站主控制台"10,000/10,000 剩余 · 过期 2026/12/21"= 总量额度）
         替代方案（二期，先记录不实现）：她本就"说日语 + 中文字幕"⇒ 念回答念**日语版**（需后端加 `speakJa` ⇒ 需一次重建 ✗）
```

## 改了哪些文件（先不 commit / 不 push ✗）

```
仓库内（只新增 3 份 md + 追加总账一处，未改任何代码/配置/素材）
  docs/CosyVoice声音复刻-20261016.md        新建：复刻全流程 + 证据 + 额度记账 + 踩坑
  docs/接线-CosyVoice前端念回答-20261016.md  新建：接线说明 + **§5.1b zh 音色实测** + **§9 代理契约/草案**
  docs/状态-Y-CosyVoice.md                  新建：本文件
  docs/总账-决策与事实台账-20261015.md      **追加**（§2.5 末尾）：
                                            ★第三方回源拉本站文件必须给 direct. 域（实测铁证）
仓库外（全部产物，**不进仓库** ✗）
  E:\DeepSeek1\work\_cosy\**                5 句样本（3 日语 + 2 中文）+ 请求/响应留证 + 包络验证 + ASR 回译
未碰 ✗
  layouts/** ｜ static/** ｜ scripts/** ｜ 任何服务器配置 ｜ 任何已上线的 site release（临时文件已删净 ✓）
```

## 验收证据（命令输出 / 产物路径）

```
① 服务可调通    cosyvoice-v3-flash / longanyang /「你好」→ HTTP 200，usage.characters=4
                key 归属判定：qwen-tts→404 Model not exist（**非 401**，说明 key 被认可）；
                cosyvoice-v3.5-plus→400 Required body invalid（模型存在）；最后 200 确认可合成 ✓
② 建音色        create_voice HTTP 200 / 4.937 s / usage.count=1
                voice_id = cosyvoice-v3.5-plus-kurisu-8eacef0d36b44939b7b9009046e335d1
                request_id = 0dcf7db7-8202-91a2-a689-bf39af4611d4
                **无任何权限缺失**（未见 401/403/"未开通"）✗
③ 3 句样本      3/3 HTTP 200（24 kHz / mono / 16-bit WAV，逐文件核头部 ✓）
  s1_intro.wav    3.20 s / 153,644 B / 合成 1.973→1.974 s / 下载 0.554→0.593 s / 29 字符
  s2_business.wav 4.96 s / 238,124 B / 合成 1.814→1.815 s / 下载 0.095→0.165 s / 42 字符
  s3_emotion.wav  5.92 s / 284,204 B / 合成 2.058→2.059 s / 下载 0.099→0.156 s / 33 字符
  sha256 e448cdf0… / 2f6c6829… / 8ed421e3…（全文见复刻文档 §5）
④ 额度记账      **173 / 10,000 = 1.73%**（3 句 104 + zh 2 句 61 + ①4 + 错误码表成功用例 4）≈ 0.0260 元 ✓
                另：**2 次成功的 create_voice**（各 usage.count=1）；失败调用无 usage ⇒ 不计费 ✓
⑤ 包络实测      前端 Web Audio 口径 clamp(RMS(10ms)×3.75,0,1)/首窗 0.12 **在云端 24k WAV 上验证通过**：
                窗数 640/992/1184 **逐条等于** 数据字节÷480 ✓；首值 0.12 ✓；值域 [0,1] ✓；末窗 0 ✓
                ⇒ **不需要后端写包络文件** ✓（与现有 12 句 envelopeFormula 同口径 ✓）
⑥ 错误码表      实测 7 例：401 InvalidApiKey ｜ 400 Model not exist ｜ 400 Engine 418（音色不匹配/缺失）
                ｜ 400 Request format is invalid ｜ 400 input text is valid ｜
                **反例 2 例**：sample_rate=12345 与 format 缺省**都返回 200**（未严格校验 ✗ 已如实记）
⑦ 临时文件删除   托管 https://direct.xiaokeqing.cn/assets/_tmp-voice/<32位随机>/crs_1393.wav
                （旁路写入 release，不在仓库）
                删除：sudo rm -rf 两个 release 下的该目录 + 删空的 _tmp-voice/ 与新建的 assets/
                FS 复核：find releases -name 'crs_1393.wav' → **0**；-name '4a8f7123…' → **0**
                公网复核：该 URL **不再返回音频**（只剩 text/html 63,811 B = index.html 的 SPA 兜底），
                          与任意不存在路径同形 ⇒ 音频公网不可得 ✓
                线上复核：软链未受影响；https://xiaokeqing.cn/ = 200 ✓
                srv1 侧：/tmp/_tvsrc 已删、临时 http.server 已停（NO_HTTPD）✓
                ★**第二轮（建 zh 音色时）又托管/又删了一次**（文件本机还在 ⇒ 重传）：
                  发布此时已切到 site-20261016-004459，且**装过该文件的旧 release 已被回收** ⇒ 重新 scp + install
                  用完同样删：FS `crs_1393.wav` → **0**；`4a8f7123…` → **0**；`assets/` 目录 → **0**
                  公网复核：该 URL 只剩 text/html 63,811 B（首 4 字节 `< ! d o`，**不是 RIFF** ⇒ 非 CF 缓存 wav ✓）
                  线上复核：软链 site-20261016-004459；home=200 ✓
⑧ 踩坑（重要）   DashScope 经 **CF** 拉参考音频 ⇒ 400 BadRequest.InputDownloadFailed（**50.476 s 失败**）✗
                换 **direct.xiaokeqing.cn（绕开 CF）** ⇒ **200 一次成功 4.937 s** ✓
                旁证：srv1→CF 193,740 B/s ｜ srv1→direct 288,853 B/s ｜ 本机→CF 首次 90 s 零字节、重试 927 B/s
                另：首次失败还有一半原因是**发布切了软链**（001942→003417 把文件挤出线上树）✗
⑨ zh 音色        `voice_id = cosyvoice-v3.5-plus-kurisuzh-f14ecf82e7244fa494055493e85ec5dd`
                create_voice HTTP 200 / 4.417 s / language_hints=["zh"] / prefix=kurisuzh
                ⚠ 首次用 prefix=`kurisu-zh` **被拒**：400 `prefix should be english letter and number`
                  ⇒ **prefix 不允许连字符**（文档只写"数字和英文字母"，实测补充：连字符也非法 ✗）
⑩ 中文 2 句     2/2 HTTP 200（24 kHz / mono / 16-bit WAV）
  zh1_endpoint.wav  2.88 s / 138,284 B / 合成 1.559→1.560 s / 下载 0.110→0.137 s / 29 字符
  zh2_no_basis.wav  3.68 s / 176,684 B / 合成 1.639→1.639 s / 下载 0.106→0.142 s / 32 字符
⑪ ★zh 音色念中文的客观结论（ASR 回译，qwen3-asr-flash）
  zh1「这个问题我需要查一下公开端点。」→ **「萨卡文大噶主要赛者公开探听。」**（不给中文提示时直接吐**日文假名**）
  zh2「公开知识库里没有依据，我不给结论。」→ **「公開知識庫，伊波次优伊克，结论。」**（只有后半念对）
  对照（同 ASR 同口径）ja1/ja3 **几乎逐字全对**（含人名 `マキセクリス` ✓）⇒ 排除"ASR 不行"的替代解释
  ⇒ **即使 language_hints=["zh"]，这个（日语素材复刻的）音色念中文仍按日语读音** ⇒ 有明显日语口音、可懂度低 ✗
  ⇒ 只改 language_hints **不解决问题**；要念中文需**中文参考音频**（同一说话人 10–20 s）`[待核对]`
  ⇒ **"像不像她"我给不出结论** ✗（无听觉）⇒ 需人耳盲听（建议对照听 s1_intro ↔ zh1 ↔ greet_first.m4a）
⑫ 代理落点侦察  srv2：Python 3.10.12 ✓｜**ffmpeg/sox/lame/opusenc 全无** ✗｜flask/uvicorn/numpy/pydub/av 全无 ✗
                ｜stdlib `audioop` 在 ✓（能算 PCM，**编不了 AAC**）｜apt 有 `ffmpeg 7:4.4.2` 候选 ✓
                ｜4 vCPU / 盘余 16G ｜回环 18190/18191/18290 **均空闲** ✓｜告警可复用 scripts/notify.sh ✓
                srv1：入站除 22 **全被安全组拦**（14 端口实测 000）⇒ **不能**做对外服务 ✗
```

## 下一步 / 移交

```
① ★站主拍板：要不要**中文参考音频**（同一说话人 10–20 s 中文清晰语音）——
   实测证明 `language_hints=["zh"]` **单独无效**（仍按日语读）✗；`kurisuzh` 音色若无用可删 ✓
② ★站主拍板：代理转 m4a 的 ffmpeg 依赖走 **A（apt 装系统包）** 还是 **B（静态包）**
   （srv2 现在**没有任何转码器**；A 会动服务器软件环境 ⇒ 须批 ✗）—— 见接线文档 §9.3
③ ★站主确认：额度是否**跨天归零**（我按"总量不归零"写；接线文档 §9.5 标 `[待核对]`）
④ 站点线在 §5.2 两条路里**选一条**（推荐 形态 B：只读代理 + 转 m4a；口型仍由前端现算 ✓）
⑤ 代理**接口契约定稿**已在接线文档 §9.2（含 reason 码表 10 条）；落点/部署步骤 §9.6–§9.8 —— **我未实现、未部署** ✗
⑥ 护栏开关名与落点请站点线按现有风格定稿（我给的是建议名，**未落代码** ✗）
⑦ 三份文档 + 总账追加，请规划侧统一 commit ✓（我未 commit/未 push ✓）
`[待核对]` 共 9+7 条，分别在 `docs/接线-CosyVoice前端念回答-20261016.md` §8 与复刻文档 §10 ✓
```

*窗口 Y · 2026-10-16 · 未 commit / 未 push ✓ · 临时公网文件两轮都已删净并验证 ✓*
