# 桐莉栖角色与场景素材：来源、用途与一键下线

> 本页是站点的**素材来源声明**。站主知情并选择上线；如权利方提出异议，按下文"一键下线"即可全站移除。

## 一、素材来源

| 用途 | 素材 | 来源 |
|---|---|---|
| 角色（8 情绪头像 + 全身 idle/speaking 图集） | 角色动画帧（KTX2 / UASTC / zstd） | 商业游戏的资源包（本地素材包 `03-character-kurisu` / `05-companion-kurisu` 等） |
| CRT 场景内的实验室背景 | 房间背景图 | 同上（`04-visual-runtime`） |
| 实拍书桌 + CRT 底图 | `static/images/crt/desk*.webp` | **Amadeus 开源项目**仓库内的 `amadeus_desktop_wallpaper.png`，按其仓库许可使用 |

## 二、加工方式（构建期完成，仓库只保留产物）

```
KTX2(UASTC+zstd) --ktx extract--> PNG --Pillow--> WebP / 图集（8 列网格）
构建脚本：scripts/kurisu/build_kurisu_assets.py（可复现；产物清单与体积见 static/kurisu/manifest.json）
角色配色**未做任何调色**（历史上曾尝试"压暗去色以融入环境"，结果发灰发白，已回退并锁定为原色）。
```

## 三、用途与边界

```
· 本站点是**个人非商业**的学习/研究/作品展示；不销售、不授权、不用于任何商业分发。
· 角色与原始素材的**版权归原权利方**；本站仅作展示，不主张任何权利。
· 不使用任何人声/音乐素材；语音功能默认关闭（`app.tts.enabled=false`，未配置 Key 时前端不显示按钮）。
```

## 四、一键下线（实测有效）

```
① 关总开关：`hugo.toml` → `kurisuEnabled = false`
   实测：用 HUGO_PARAMS_KURISUENABLED=false 构建，产物里 kurisu-player.js / xk-crt / data-xk-kurisu / xk-kurisu-stage 全部消失
   （页面回到纯文本版，其余功能不受影响）
② 彻底移除素材：删除 `static/kurisu/` 与 `static/images/crt/`，并提交
③ 若只是想让某页不显示：见 layouts/baseof.html 里的三个 `{{- if site.Params.kurisuEnabled }}` 门控点
```

## 五、体积与加载策略（与站点性能预算一致）

```
首屏只加载：full/idle.boot.webp + full/idle.poster.webp + avatar/normal.idle.webp + avatar/normal.static.webp
（manifest.budgets.firstScreenBytes ≈ 292KB，预算 1.5MB）
其余 hi 档图集在首屏渲染后按需后台补；移动端只用 132px 头像图集；
`prefers-reduced-motion` / `saveData` / 窄屏 → 只显示静态帧；页面隐藏时暂停动画与解码。
```