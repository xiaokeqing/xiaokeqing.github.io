<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   docs/live2d_character_visuals.md
     quoted: L1-L3, L31-L53
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- Live2D is an explicit opt-in experimental backend; Sprite remains default  [docs/live2d_character_visuals.md L1-L3] ---- */
# 角色形象与 Live2D 实验支持

日期：2026-10-08。分支：`codex/live2d-character-renderer`。默认仍为 Sprite；Live2D 是显式选择的实验性美术后端。原生 Main Host render、真实 Host 壁纸页面、统一人物取景、Sprite 往返、连接恢复及 SDK 错误/加载竞态均已有实测。桌面宿主支持范围见下方限制。

/* ---- architecture boundary table + E-mote not implemented  [docs/live2d_character_visuals.md L31-L53] ---- */
## 架构边界

| 层 | 责任 |
| --- | --- |
| 既有 parser、ChatRuntime、TTS/StreamPlayer | 解释现有标签、安排句子播放与幅度信号。Live2D 不增加 LLM 调用、分类器或第二份语音分析。 |
| [CharacterPresentationCoordinator](../server/character_presentation.py) | 继续拥有 utterance/ambient 来源优先级、释放和 handoff。Sprite 路由在广播前解析一次，两个展示面不独立抽签。 |
| [VisualHandler](../server/handlers/visual_handler.py) 与 store | 选择美术后端、校验/持久化配置、下发当前选择及收取真实状态。保存和重连恢复当前 claim/playback 状态，不重放已结束语句。 |
| [model_character.js](../render/web/model_character.js) | 一个显式模型 adapter 构造边界；当前只构造 Live2D，没有注册表或插件平台。 |
| [Live2DCharacter](../render/web/live2d_character.js) | SDK 加载、表达、模型参数、嘴型更新顺序、原始人物取景、RenderTexture 和资源生命周期。SDK 细节留在此层。 |
| render / wallpaper 场景 | 提供视口、mask、图层、颜色效果、时钟和可见性。Cubism 先画到视口大小的 RenderTexture，再由普通 Pixi 层接受裁剪。 |
| [SettingsPage](../electron/src/renderer/components/SettingsPage.tsx) 与 [形象管理组件](../electron/src/renderer/components/CharacterVisualsPage.tsx) | 草稿与 applied 分开；独立预览等待 ready 握手并检查消息来源。离开分区按条件卸载，不保留隐藏预览。 |

语义事件使用 `render.character_config`、`render.character_intent`、`render.character_release`；真正的 Sprite 资产图事件 `render.spriteforge_graph` 保留专用命名。表达名称和 Cubism 参数 ID 不与 VTS 的 EXPR/PARAM/HOTKEY 命名空间混用。

**公开协议迁移：** `render.spriteforge_intent` 与 `render.spriteforge_release` 分别改名为 `render.character_intent` 与 `render.character_release`。这项共享协议变更也影响只使用 Sprite 的外部订阅者；“Live2D 默认关闭”不代表旧订阅者自动兼容。Host 与随附前端应一同升级，外部订阅者需更新事件名称并按 payload 的 backend 处理人物表现。现有来源优先级、释放和播放语义不变，不发送永久并行的两套事件。旧 Expression 入口由 Settings → 角色形象替代，新 `visual.*` 控制及形象配置文件不迁移会话或人格。没有形象配置时仍默认 Sprite；回切 Sprite 不会恢复旧协议名称。迁移约定与合并前的产品决定跟踪于 [Issue #165](https://github.com/Code-Amadeus/Amadeus/issues/165)。

状态为 `loading/ready/error/unloaded`，含 `profile_id`、Host 实例 `runtime_id` 和配置 `revision`。状态是观察，不是新的执行或选择权限。Host 拒绝旧实例/旧选择回执；Electron 只转发自己 iframe 的 render 状态。掉线时关闭该 iframe 的 speaking/mouth，已经完成加载的 iframe 在连接恢复时请求 `render.ready`，由 Host 重放当前选择。

Live2D 模式禁用会隐藏前景、换成旧人物素材的活动场景及其专属动作音效；背景、环境、字幕与 Work Canvas 保留。停用场景时释放其自有纹理缓存，既有加载令牌阻止晚完成的加载重新驻留；共享背景纹理不随场景销毁。回切 Sprite 后重新加载所需场景资源并恢复原场景能力。

## 后续 E-mote

尚未实现 E-mote，也不展示占位选项。未来 adapter 可以复用工厂入口与已有 configure、intent/release、speaking/mouth、viewport、pause、status、unload/destroy 边界；必要的 SDK 加载、参数及绘制细节由新 adapter 自己拥有。只在实际 SDK 需求得到证明后扩展相应配置校验，不建设通用插件平台，不把 E-mote 伪装成 SpriteForge 节点。
