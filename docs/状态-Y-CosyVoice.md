# 状态-Y-CosyVoice（窗口 Y）· 2026-10-16

> 只由该窗口自己更新（避免多窗口抢同一个文件 ✗）；格式见 `docs/窗口分工规范-20261015.md` §四 ✓

```
任务号 ：CosyVoice 声音复刻（API 路线）+ 前端接线说明
状态   ：已完成 ✓（无阻塞项；两条 [待核对] 需站主拍板：中文用日语音色 / 是否另建 zh 音色）
```

## 改了哪些文件（先不 commit / 不 push ✗）

```
仓库内（只新增 3 份 md，未改任何代码/配置/素材）
  docs/CosyVoice声音复刻-20261016.md        新建：复刻全流程 + 证据 + 额度记账 + 踩坑
  docs/接线-CosyVoice前端念回答-20261016.md  新建：前端接线说明（参数/字段/错误码/包络/时延体积/护栏）
  docs/状态-Y-CosyVoice.md                  新建：本文件
  docs/总账-决策与事实台账-20261015.md      **追加**（§2.5 末尾）：
                                            ★第三方回源拉本站文件必须给 direct. 域（实测铁证）
仓库外（全部产物，**不进仓库** ✗）
  E:\DeepSeek1\work\_cosy\**                3 句样本 + 请求/响应留证 + 包络验证 + 复刻响应
未碰 ✗
  layouts/** ｜ static/** ｜ scripts/** ｜ 任何服务器配置 ｜ 任何已上线的 site release（临时文件已删净）
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
④ 额度记账      112 / 10,000 = **1.12%**（3 句 104 + ①4 + 错误码表成功用例 4）≈ 0.0168 元 ✓
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
                线上复核：软链仍 site-20261016-003417；https://xiaokeqing.cn/ = 200 ✓ 未受影响
                srv1 侧：/tmp/_tvsrc 已删、临时 http.server 已停（NO_HTTPD）✓
⑧ 踩坑（重要）   DashScope 经 **CF** 拉参考音频 ⇒ 400 BadRequest.InputDownloadFailed（**50.476 s 失败**）✗
                换 **direct.xiaokeqing.cn（绕开 CF）** ⇒ **200 一次成功 4.937 s** ✓
                旁证：srv1→CF 193,740 B/s ｜ srv1→direct 288,853 B/s ｜ 本机→CF 首次 90 s 零字节、重试 927 B/s
                另：首次失败还有一半原因是**发布切了软链**（001942→003417 把文件挤出线上树）✗
```

## 下一步 / 移交

```
① 站主拍板：念**中文**回答要不要**另建 language_hints=["zh"] 的音色**（现音色是 ja）✗
② 站点线在 §5.2 两条路里**选一条**（推荐 形态 B：只读代理 + 转 m4a；口型仍由前端现算 ✓）
③ 护栏开关名与落点请站点线按现有风格定稿（我给的是建议名，**未落代码** ✗）
④ 两份复刻/接线文档 + 本状态 + 总账追加，请规划侧统一 commit ✓（我未 commit/未 push ✓）
5 条 [待核对] 全部记在 `docs/接线-CosyVoice前端念回答-20261016.md` §8 与复刻文档 §10 ✓
```

*窗口 Y · 2026-10-16 · 未 commit / 未 push ✓ · 临时公网文件已删净并验证 ✓*
