# Kurisu 素材清单（03 角色动画 · 全量）

生成时间：2026-10-14 08:22:47  
来源：`amadeus-character-kurisu-2026-09-26.zip`（2.67 GB，7556 条目）

## 总览

| 项目 | 数值 |
| --- | --- |
| 剪辑数 | **39**（37 个 `textures/<clip>/loop/` + 2 个 `textures/<clip>/in/`） |
| KTX2 帧总数 | **7552** |
| 已解码帧 | 468（每剪辑均匀抽 12 帧；全部 39 个剪辑成功，0 失败） |
| 解码总 CPU 秒 | 178.0 s（6 线程并行，首轮 49.7 s 墙钟） |
| 帧格式 | 全部 `VK_FORMAT_UNDEFINED`（Basis/UASTC）+ ZSTD 超压缩，RGBA |
| 帧尺寸 | 见下表（**不是**统一 764×1028） |

### 帧尺寸真实分布（读取 7552 个 KTX2 头得出）

| 尺寸 | 帧数 | 占比 | 属于哪些剪辑 |
| --- | --- | --- | --- |
| 764x1028 | 6284 | 83.2% | angry_speaking、angry_trans、closed_eye_trans、idle、idle1、idle_mic_wind、idle_side_butterfly、idle_side_soft_wind、idle_side_wind、idle_str_wind、key_point_speaking、sad、sad_speaking、sad_trans、serious_to_thinking、shy_speaking1、shy_speaking2、shy_trans、smile_speaking、speaking_closed_eye_1、speaking_closed_eye_2、speaking_long、speaking_loop1、speaking_loop2、speaking_med、speaking_short、speaking_trans、surprise_speaking、surprise_trans、thinking_speaking1、thinking_speaking2、thinking_to_key_point、thinking_to_serious、thinking_trans、trans_standby |
| 960x1028 | 738 | 9.8% | idle_closed_eye |
| 764x1026 | 290 | 3.8% | idle2 |
| 764x1027 | 240 | 3.2% | smile、trans_smile |

> ⚠️ 与交接信息不同：**只有 83.2% 的帧是 764×1028**。`idle_closed_eye` 是 960×1028（右侧 196 列全透明，有效内容仍到 x=764），`idle2` 是 764×1026，`smile`/`trans_smile` 是 764×1027。

### 全部 39 个剪辑

| # | 剪辑 | 帧数 | 尺寸 | 建议用途 | 首帧 | 接触印样 | 抽帧耗时 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `angry_speaking` | 180 | 764x1028 | 说话·生气 | [png](../first/angry_speaking_0001.png) | [sheet](../sheets/clip_angry_speaking.png) | 0.7s |
| 2 | `angry_trans` | 60 | 764x1028 | 转场 | [png](../first/angry_trans_0001.png) | [sheet](../sheets/clip_angry_trans.png) | 0.6s |
| 3 | `closed_eye_trans` | 120 | 764x1028 | 转场 | [png](../first/closed_eye_trans_0001.png) | [sheet](../sheets/clip_closed_eye_trans.png) | 0.7s |
| 4 | `idle` | 120 | 764x1028 | 待机 | [png](../first/idle_0001.png) | [sheet](../sheets/clip_idle.png) | 0.7s |
| 5 | `idle1` | 120 | 764x1028 | 待机 | [png](../first/idle1_0001.png) | [sheet](../sheets/clip_idle1.png) | 0.7s |
| 6 | `idle2` | 290 | 764x1026 | 待机 | [png](../first/idle2_0001.png) | [sheet](../sheets/clip_idle2.png) | 0.8s |
| 7 | `idle_closed_eye` | 738 | 960x1028 | 待机·闭眼 | [png](../first/idle_closed_eye_0001.png) | [sheet](../sheets/clip_idle_closed_eye.png) | 0.6s |
| 8 | `idle_mic_wind` | 194 | 764x1028 | 待机·环境氛围 | [png](../first/idle_mic_wind_0001.png) | [sheet](../sheets/clip_idle_mic_wind.png) | 0.8s |
| 9 | `idle_side_butterfly` | 600 | 764x1028 | 待机·环境氛围 | [png](../first/idle_side_butterfly_0001.png) | [sheet](../sheets/clip_idle_side_butterfly.png) | 0.7s |
| 10 | `idle_side_soft_wind` | 180 | 764x1028 | 待机·环境氛围 | [png](../first/idle_side_soft_wind_0001.png) | [sheet](../sheets/clip_idle_side_soft_wind.png) | 0.7s |
| 11 | `idle_side_wind` | 180 | 764x1028 | 待机·环境氛围 | [png](../first/idle_side_wind_0001.png) | [sheet](../sheets/clip_idle_side_wind.png) | 0.6s |
| 12 | `idle_str_wind` | 194 | 764x1028 | 待机·环境氛围 | [png](../first/idle_str_wind_0001.png) | [sheet](../sheets/clip_idle_str_wind.png) | 0.8s |
| 13 | `key_point_speaking` | 180 | 764x1028 | 说话·重点 | [png](../first/key_point_speaking_0001.png) | [sheet](../sheets/clip_key_point_speaking.png) | 0.7s |
| 14 | `sad` | 120 | 764x1028 | 情绪·低落 | [png](../first/sad_0001.png) | [sheet](../sheets/clip_sad.png) | 0.7s |
| 15 | `sad_speaking` | 120 | 764x1028 | 说话·低落 | [png](../first/sad_speaking_0001.png) | [sheet](../sheets/clip_sad_speaking.png) | 0.7s |
| 16 | `sad_trans` | 60 | 764x1028 | 转场 | [png](../first/sad_trans_0001.png) | [sheet](../sheets/clip_sad_trans.png) | 0.6s |
| 17 | `serious_to_thinking` | 120 | 764x1028 | 转场 | [png](../first/serious_to_thinking_0001.png) | [sheet](../sheets/clip_serious_to_thinking.png) | 0.6s |
| 18 | `shy_speaking1` | 180 | 764x1028 | 说话·害羞 | [png](../first/shy_speaking1_0001.png) | [sheet](../sheets/clip_shy_speaking1.png) | 0.7s |
| 19 | `shy_speaking2` | 300 | 764x1028 | 说话·害羞 | [png](../first/shy_speaking2_0001.png) | [sheet](../sheets/clip_shy_speaking2.png) | 0.7s |
| 20 | `shy_trans` | 60 | 764x1028 | 转场 | [png](../first/shy_trans_0001.png) | [sheet](../sheets/clip_shy_trans.png) | 0.6s |
| 21 | `smile` | 120 | 764x1027 | 情绪·微笑 | [png](../first/smile_0001.png) | [sheet](../sheets/clip_smile.png) | 0.7s |
| 22 | `smile_speaking` | 180 | 764x1028 | 说话·微笑 | [png](../first/smile_speaking_0001.png) | [sheet](../sheets/clip_smile_speaking.png) | 0.7s |
| 23 | `speaking_closed_eye_1` | 180 | 764x1028 | 说话·闭眼 | [png](../first/speaking_closed_eye_1_0001.png) | [sheet](../sheets/clip_speaking_closed_eye_1.png) | 0.7s |
| 24 | `speaking_closed_eye_2` | 300 | 764x1028 | 说话·闭眼 | [png](../first/speaking_closed_eye_2_0001.png) | [sheet](../sheets/clip_speaking_closed_eye_2.png) | 0.7s |
| 25 | `speaking_long` | 360 | 764x1028 | 说话 | [png](../first/speaking_long_0001.png) | [sheet](../sheets/clip_speaking_long.png) | 0.7s |
| 26 | `speaking_loop1` | 180 | 764x1028 | 说话 | [png](../first/speaking_loop1_0001.png) | [sheet](../sheets/clip_speaking_loop1.png) | 0.7s |
| 27 | `speaking_loop2` | 240 | 764x1028 | 说话 | [png](../first/speaking_loop2_0001.png) | [sheet](../sheets/clip_speaking_loop2.png) | 0.7s |
| 28 | `speaking_med` | 240 | 764x1028 | 说话 | [png](../first/speaking_med_0001.png) | [sheet](../sheets/clip_speaking_med.png) | 0.7s |
| 29 | `speaking_short` | 120 | 764x1028 | 说话 | [png](../first/speaking_short_0001.png) | [sheet](../sheets/clip_speaking_short.png) | 0.7s |
| 30 | `speaking_trans` | 120 | 764x1028 | 说话 | [png](../first/speaking_trans_0001.png) | [sheet](../sheets/clip_speaking_trans.png) | 0.6s |
| 31 | `surprise_speaking` | 180 | 764x1028 | 说话·惊讶 | [png](../first/surprise_speaking_0001.png) | [sheet](../sheets/clip_surprise_speaking.png) | 0.7s |
| 32 | `surprise_trans` | 60 | 764x1028 | 转场 | [png](../first/surprise_trans_0001.png) | [sheet](../sheets/clip_surprise_trans.png) | 0.6s |
| 33 | `thinking_speaking1` | 180 | 764x1028 | 说话·思考 | [png](../first/thinking_speaking1_0001.png) | [sheet](../sheets/clip_thinking_speaking1.png) | 0.6s |
| 34 | `thinking_speaking2` | 300 | 764x1028 | 说话·思考 | [png](../first/thinking_speaking2_0001.png) | [sheet](../sheets/clip_thinking_speaking2.png) | 0.7s |
| 35 | `thinking_to_key_point` | 120 | 764x1028 | 转场 | [png](../first/thinking_to_key_point_0001.png) | [sheet](../sheets/clip_thinking_to_key_point.png) | 0.6s |
| 36 | `thinking_to_serious` | 120 | 764x1028 | 转场 | [png](../first/thinking_to_serious_0001.png) | [sheet](../sheets/clip_thinking_to_serious.png) | 0.7s |
| 37 | `thinking_trans` | 120 | 764x1028 | 转场 | [png](../first/thinking_trans_0001.png) | [sheet](../sheets/clip_thinking_trans.png) | 0.7s |
| 38 | `trans_smile` | 120 | 764x1027 | 转场 | [png](../first/trans_smile_0001.png) | [sheet](../sheets/clip_trans_smile.png) | 0.7s |
| 39 | `trans_standby` | 196 | 764x1028 | 待机·预备 | [png](../first/trans_standby_0001.png) | [sheet](../sheets/clip_trans_standby.png) | 0.6s |

### 按用途分组

- **说话·生气**（1）：`angry_speaking`(180帧)
- **转场**（10）：`angry_trans`(60帧)、`closed_eye_trans`(120帧)、`sad_trans`(60帧)、`serious_to_thinking`(120帧)、`shy_trans`(60帧)、`surprise_trans`(60帧)、`thinking_to_key_point`(120帧)、`thinking_to_serious`(120帧)、`thinking_trans`(120帧)、`trans_smile`(120帧)
- **待机**（3）：`idle`(120帧)、`idle1`(120帧)、`idle2`(290帧)
- **待机·闭眼**（1）：`idle_closed_eye`(738帧)
- **待机·环境氛围**（5）：`idle_mic_wind`(194帧)、`idle_side_butterfly`(600帧)、`idle_side_soft_wind`(180帧)、`idle_side_wind`(180帧)、`idle_str_wind`(194帧)
- **说话·重点**（1）：`key_point_speaking`(180帧)
- **情绪·低落**（1）：`sad`(120帧)
- **说话·低落**（1）：`sad_speaking`(120帧)
- **说话·害羞**（2）：`shy_speaking1`(180帧)、`shy_speaking2`(300帧)
- **情绪·微笑**（1）：`smile`(120帧)
- **说话·微笑**（1）：`smile_speaking`(180帧)
- **说话·闭眼**（2）：`speaking_closed_eye_1`(180帧)、`speaking_closed_eye_2`(300帧)
- **说话**（6）：`speaking_long`(360帧)、`speaking_loop1`(180帧)、`speaking_loop2`(240帧)、`speaking_med`(240帧)、`speaking_short`(120帧)、`speaking_trans`(120帧)
- **说话·惊讶**（1）：`surprise_speaking`(180帧)
- **说话·思考**（2）：`thinking_speaking1`(180帧)、`thinking_speaking2`(300帧)
- **待机·预备**（1）：`trans_standby`(196帧)

### 每剪辑不透明内容外框（opaque bbox，用于跨剪辑对齐）

| 剪辑 | 画布 | bbox (l,t,r,b) | 备注 |
| --- | --- | --- | --- |
| `angry_speaking` | 764x1028 | [112, 16, 764, 1028] |  |
| `angry_trans` | 764x1028 | [115, 16, 764, 1028] |  |
| `closed_eye_trans` | 764x1028 | [115, 18, 764, 1028] |  |
| `idle` | 764x1028 | [116, 0, 764, 1028] |  |
| `idle1` | 764x1028 | [116, 0, 764, 1028] |  |
| `idle2` | 764x1026 | [116, 0, 764, 1026] | canvas 764x1026 (not the 764x1028 default) |
| `idle_closed_eye` | 960x1028 | [98, 0, 764, 1028] | canvas 960x1028 (not the 764x1028 default) |
| `idle_mic_wind` | 764x1028 | [116, 0, 764, 1028] |  |
| `idle_side_butterfly` | 764x1028 | [175, 0, 764, 1028] |  |
| `idle_side_soft_wind` | 764x1028 | [175, 0, 764, 1028] |  |
| `idle_side_wind` | 764x1028 | [175, 0, 764, 1028] |  |
| `idle_str_wind` | 764x1028 | [116, 0, 764, 1028] |  |
| `key_point_speaking` | 764x1028 | [148, 24, 764, 1028] |  |
| `sad` | 764x1028 | [116, 16, 764, 1028] |  |
| `sad_speaking` | 764x1028 | [115, 15, 764, 1028] |  |
| `sad_trans` | 764x1028 | [115, 16, 764, 1028] |  |
| `serious_to_thinking` | 764x1028 | [156, 20, 764, 1028] |  |
| `shy_speaking1` | 764x1028 | [115, 16, 764, 1028] |  |
| `shy_speaking2` | 764x1028 | [115, 16, 764, 1028] |  |
| `shy_trans` | 764x1028 | [116, 16, 764, 1028] |  |
| `smile` | 764x1027 | [116, 16, 667, 1027] | canvas 764x1027 (not the 764x1028 default) |
| `smile_speaking` | 764x1028 | [115, 17, 764, 1028] |  |
| `speaking_closed_eye_1` | 764x1028 | [136, 20, 764, 1028] |  |
| `speaking_closed_eye_2` | 764x1028 | [136, 20, 764, 1028] |  |
| `speaking_long` | 764x1028 | [116, 16, 764, 1028] |  |
| `speaking_loop1` | 764x1028 | [156, 0, 764, 1028] |  |
| `speaking_loop2` | 764x1028 | [0, 0, 764, 1028] |  |
| `speaking_med` | 764x1028 | [115, 16, 764, 1028] |  |
| `speaking_short` | 764x1028 | [116, 16, 764, 1028] |  |
| `speaking_trans` | 764x1028 | [115, 18, 764, 1028] |  |
| `surprise_speaking` | 764x1028 | [116, 16, 764, 1028] |  |
| `surprise_trans` | 764x1028 | [116, 16, 764, 1028] |  |
| `thinking_speaking1` | 764x1028 | [176, 0, 764, 1028] |  |
| `thinking_speaking2` | 764x1028 | [176, 0, 764, 1028] |  |
| `thinking_to_key_point` | 764x1028 | [176, 0, 764, 1028] |  |
| `thinking_to_serious` | 764x1028 | [176, 0, 764, 1028] |  |
| `thinking_trans` | 764x1028 | [115, 18, 764, 1028] |  |
| `trans_smile` | 764x1027 | [116, 16, 764, 1027] | canvas 764x1027 (not the 764x1028 default) |
| `trans_standby` | 764x1028 | [116, 16, 764, 1028] |  |

### runtime_manifest.json 里的播放参数（权威）

| 剪辑 | phase | loopMode | frameIntervalMs | 帧数 | 口型叠加 |
| --- | --- | --- | --- | --- | --- |
| `angry_speaking` | loop | loop | 17 | 180 | ✔ |
| `angry_trans` | loop | once_then_hold | 8 | 60 |  |
| `closed_eye_trans` | in | once_then_hold | 8 | 120 |  |
| `idle` | loop | loop | 21 | 120 |  |
| `idle1` | loop | loop | 21 | 120 |  |
| `idle2` | loop | loop | 21 | 290 |  |
| `idle_closed_eye` | loop | loop | 17 | 738 |  |
| `idle_mic_wind` | loop | loop | 21 | 194 |  |
| `idle_side_butterfly` | loop | loop | 17 | 600 |  |
| `idle_side_soft_wind` | loop | loop | 17 | 180 |  |
| `idle_side_wind` | loop | loop | 17 | 180 |  |
| `idle_str_wind` | loop | loop | 21 | 194 |  |
| `key_point_speaking` | loop | loop | 17 | 180 | ✔ |
| `sad` | loop | loop | 17 | 120 |  |
| `sad_speaking` | loop | loop | 17 | 120 | ✔ |
| `sad_trans` | loop | once_then_hold | 8 | 60 |  |
| `serious_to_thinking` | loop | once_then_hold | 8 | 120 |  |
| `shy_speaking1` | loop | loop | 17 | 180 | ✔ |
| `shy_speaking2` | loop | loop | 17 | 300 | ✔ |
| `shy_trans` | loop | once_then_hold | 8 | 60 |  |
| `smile` | loop | loop | 17 | 120 |  |
| `smile_speaking` | loop | loop | 17 | 180 | ✔ |
| `speaking_closed_eye_1` | loop | loop | 17 | 180 | ✔ |
| `speaking_closed_eye_2` | loop | loop | 17 | 300 | ✔ |
| `speaking_long` | loop | loop | 17 | 360 | ✔ |
| `speaking_loop1` | loop | loop | 17 | 180 | ✔ |
| `speaking_loop2` | loop | loop | 17 | 240 | ✔ |
| `speaking_med` | loop | loop | 17 | 240 | ✔ |
| `speaking_short` | loop | loop | 17 | 120 | ✔ |
| `speaking_trans` | in | once_then_hold | 8 | 120 |  |
| `surprise_speaking` | loop | loop | 17 | 180 | ✔ |
| `surprise_trans` | loop | once_then_hold | 8 | 60 |  |
| `thinking_speaking1` | loop | loop | 17 | 180 | ✔ |
| `thinking_speaking2` | loop | loop | 17 | 300 | ✔ |
| `thinking_to_key_point` | loop | once_then_hold | 8 | 120 |  |
| `thinking_to_serious` | loop | once_then_hold | 8 | 120 |  |
| `thinking_trans` | loop | once_then_hold | 8 | 120 |  |
| `trans_smile` | loop | once_then_hold | 5 | 120 |  |
| `trans_standby` | loop | once_then_hold | 21 | 196 |  |

`clipCount=39`、`frameCount=7552`、`textureBytes=2662875956`（与本次清点一致）。全部剪辑 `frameIntervalMs[5, 8, 17, 21]` → 约 **58.8 fps**。

### 状态机（graph_config.json，label→label）

| from | to | 概率 |
| --- | --- | --- |
| `idle` | `idle` | 0.70 |
| `idle` | `idle2` | 0.05 |
| `idle` | `idle_mic_wind` | 0.10 |
| `idle_mic_wind` | `idle_mic_wind` | 0.60 |
| `idle_str_wind` | `idle_str_wind` | 0.30 |
| `idle_str_wind` | `idle_mic_wind` | 0.50 |
| `idle_str_wind` | `idle` | 0.20 |
| `idle_mic_wind` | `idle_str_wind` | 0.20 |
| `idle_mic_wind` | `idle` | 0.20 |
| `idle` | `idle1` | 0.05 |
| `idle1` | `idle1` | 0.15 |
| `idle1` | `idle` | 0.85 |
| `idle2` | `idle2` | 0.70 |
| `idle2` | `idle` | 0.30 |
| `idle` | `trans_standby` | 0.05 |
| `idle` | `trans_smile` | 0.00 |
| `idle` | `speaking_trans` | 0.00 |
| `speaking_loop1` | `speaking_loop1` | 0.40 |
| `speaking_loop2` | `speaking_loop2` | 0.50 |
| `speaking_loop2` | `speaking_loop1` | 0.40 |
| `speaking_loop1` | `speaking_loop2` | 0.50 |
| `speaking_trans` | `speaking_loop2` | 0.60 |
| `speaking_trans` | `speaking_loop1` | 0.40 |
| `idle_side_wind` | `idle_side_wind` | 0.30 |
| `trans_standby` | `idle_side_soft_wind` | 0.30 |
| `trans_standby` | `idle_side_wind` | 0.10 |
| `idle_side_soft_wind` | `idle_side_soft_wind` | 0.60 |
| `idle_side_soft_wind` | `idle_side_wind` | 0.30 |
| `idle_side_wind` | `idle_side_soft_wind` | 0.60 |
| `speaking_short` | `speaking_short` | 0.20 |
| `idle` | `speaking_short` | 0.00 |
| `speaking_short` | `speaking_med` | 0.30 |
| `speaking_short` | `speaking_long` | 0.50 |
| `speaking_long` | `speaking_long` | 0.50 |
| `speaking_long` | `speaking_med` | 0.30 |
| `speaking_long` | `speaking_short` | 0.20 |
| `speaking_med` | `speaking_med` | 0.40 |
| `speaking_med` | `speaking_long` | 0.40 |
| `speaking_med` | `speaking_short` | 0.40 |
| `trans_smile` | `smile_speaking` | 1.00 |
| `smile_speaking` | `smile_speaking` | 1.00 |
| `idle` | `sad_trans` | 0.00 |
| `sad_trans` | `sad_speaking` | 1.00 |
| `sad_speaking` | `sad_speaking` | 1.00 |
| `idle_str_wind` | `thinking_trans` | 0.00 |
| `thinking_trans` | `thinking_speaking2` | 0.65 |
| `thinking_trans` | `thinking_speaking1` | 0.35 |
| `thinking_speaking1` | `thinking_speaking1` | 0.50 |
| `thinking_speaking1` | `thinking_speaking2` | 0.50 |
| `thinking_speaking2` | `thinking_speaking1` | 0.40 |
| `thinking_speaking2` | `thinking_speaking2` | 0.30 |
| `thinking_speaking2` | `thinking_to_serious` | 0.15 |
| `thinking_to_serious` | `speaking_loop2` | 0.50 |
| `thinking_to_serious` | `speaking_loop1` | 0.50 |
| `thinking_speaking2` | `thinking_to_key_point` | 0.15 |
| `thinking_to_key_point` | `key_point_speaking` | 1.00 |
| `key_point_speaking` | `key_point_speaking` | 0.50 |
| `key_point_speaking` | `thinking_speaking1` | 0.50 |
| `speaking_loop2` | `serious_to_thinking` | 0.10 |
| `speaking_loop1` | `serious_to_thinking` | 0.10 |
| `serious_to_thinking` | `thinking_speaking1` | 0.40 |
| `serious_to_thinking` | `thinking_speaking2` | 0.60 |
| `idle` | `shy_trans` | 0.00 |
| `shy_trans` | `shy_speaking1` | 0.40 |
| `shy_trans` | `shy_speaking2` | 0.60 |
| `shy_speaking1` | `shy_speaking1` | 0.50 |
| `shy_speaking2` | `shy_speaking2` | 0.60 |
| `shy_speaking2` | `shy_speaking1` | 0.40 |
| `shy_speaking1` | `shy_speaking2` | 0.50 |
| `idle` | `surprise_trans` | 0.00 |
| `surprise_trans` | `surprise_speaking` | 1.00 |
| `surprise_speaking` | `surprise_speaking` | 1.00 |
| `idle` | `angry_trans` | 0.00 |
| `angry_trans` | `angry_speaking` | 1.00 |
| `angry_speaking` | `angry_speaking` | 1.00 |
| `idle_side_wind` | `idle_side_butterfly` | 0.10 |
| `idle_side_soft_wind` | `idle_side_butterfly` | 0.10 |
| `idle_side_butterfly` | `idle_side_wind` | 1.00 |
| `idle` | `closed_eye_trans` | 0.00 |
| `closed_eye_trans` | `speaking_closed_eye_1` | 0.50 |
| `closed_eye_trans` | `speaking_closed_eye_2` | 0.50 |
| `speaking_closed_eye_2` | `speaking_closed_eye_1` | 0.60 |
| `speaking_closed_eye_1` | `speaking_closed_eye_2` | 0.35 |
| `speaking_closed_eye_1` | `speaking_closed_eye_1` | 0.65 |
| `speaking_closed_eye_2` | `speaking_closed_eye_2` | 0.40 |
| `idle` | `idle_closed_eye` | 0.05 |
| `idle_closed_eye` | `idle` | 1.00 |
