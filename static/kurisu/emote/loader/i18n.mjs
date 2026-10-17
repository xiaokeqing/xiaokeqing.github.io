// 界面文案（中/英）。新增文案必须同时补全两种语言，否则英文界面会回落成 key。
export const fail = (key, params) => Object.assign(new Error(key), { i18n: { key, params } });

export const messages = {
  zh: {
    appName: "红莉栖 E-mote",
    tagline: "E-mote · 原模型实时渲染 · 兼容预览",
    stage: "红莉栖 E-mote 实时模型",
    "label.language": "语言",
    "label.model": "模型",
    "label.view": "取景",
    "label.expression": "原生表情时间轴",
    "label.head": "头部左右",
    "label.gaze": "眼球左右",
    "label.mouth": "口型开合",
    "model.a": "常服 A",
    "model.b": "常服 B",
    "model.a_white": "白衣 A",
    "model.b_white": "白衣 B",
    "model.c": "常服 C",
    "model.c_white": "白衣 C",
    "view.portrait": "半身近景",
    "view.full": "全身",
    follow: "视线跟随鼠标",
    talk: "自动口型演示（非语音同步）",
    nod: "点头",
    reset: "复位",
    note: "A：自然垂手；B：抱臂；C：手扶领带。切换会重新加载页面，复位会保留所选姿态。默认高清近景，可切全身。当前为兼容预览，不保证原版顶层合成特效完全一致。",
    "credit.note": "仅作本地非商业技术验证；角色素材权利归原权利人。",
    "status.loading": "正在加载运行时…",
    "status.failed": "加载失败：",
    "status.readingIndex": "读取模型与资源索引…",
    "status.decodingAtlas": "解码图集 {index}/{total}…",
    "status.assembling": "组装 PSB 并加载 WebGL…",
    "status.ready": "{model} · {width}×{height} · {scale}× 像素密度 · {count} 种表情",
    "error.nulField": "字段名不能包含 NUL",
    "error.nulString": "字符串不能包含 NUL",
    "error.nonFinite": "模型含非有限数值",
    "error.integerRange": "整数超出 JavaScript 安全范围",
    "error.missingResource": "缺失资源：{value}",
    "error.partControlUnsupported": "模型不支持部件控制：{label}",
    "error.partControlRange": "部件控制超出区间：{label}={value}",
    "error.selectorRange": "{label} 超出选择器区间：{value}",
    "error.cwColor": "暂不支持非中性 cw 颜色权重",
    "error.missingEntry": "缺少兼容播放入口：全体構造",
    "error.loadResource": "资源读取失败 {status}：{path}",
    "error.unsupportedData": "需要本仓库的 E-mote / PSB v4 数据",
    "error.unknownModel": "未知模型，请从模型列表重新选择",
    "error.runtimeNotReady": "FreeMote 运行时未就绪，请检查 CDN 连接",
    "error.webgl": "WebGL 初始化失败，请启用硬件加速",
    "error.modelUnrecognized": "运行时无法识别该模型",
  },
  en: {
    appName: "Kurisu E-mote",
    tagline: "E-mote · real-time rendering of the original model · compatibility preview",
    stage: "Kurisu E-mote live model",
    "label.language": "Language",
    "label.model": "Model",
    "label.view": "Framing",
    "label.expression": "Native expression timeline",
    "label.head": "Head turn",
    "label.gaze": "Eye direction",
    "label.mouth": "Mouth open",
    "model.a": "Casual A",
    "model.b": "Casual B",
    "model.a_white": "Lab coat A",
    "model.b_white": "Lab coat B",
    "model.c": "Casual C",
    "model.c_white": "Lab coat C",
    "view.portrait": "Upper body",
    "view.full": "Full body",
    follow: "Eyes follow the cursor",
    talk: "Auto mouth demo (not lip sync)",
    nod: "Nod",
    reset: "Reset",
    note: "A: arms down; B: arms folded; C: hand on tie. Switching reloads the page; Reset keeps the selected pose. HD close-up by default, full body optional. This is a compatibility preview and does not reproduce every composite effect of the original game.",
    "credit.note": "For local non-commercial technical verification only; character assets belong to their respective rights holders.",
    "status.loading": "Loading runtime…",
    "status.failed": "Load failed: ",
    "status.readingIndex": "Reading model and resource index…",
    "status.decodingAtlas": "Decoding atlas {index}/{total}…",
    "status.assembling": "Assembling PSB and loading WebGL…",
    "status.ready": "{model} · {width}×{height} · {scale}× pixels · {count} expressions",
    "error.nulField": "Field name must not contain NUL",
    "error.nulString": "String must not contain NUL",
    "error.nonFinite": "Model contains a non-finite number",
    "error.integerRange": "Integer outside the safe JavaScript range",
    "error.missingResource": "Missing resource: {value}",
    "error.partControlUnsupported": "Model does not support part control: {label}",
    "error.partControlRange": "Part control out of range: {label}={value}",
    "error.selectorRange": "{label} out of selector range: {value}",
    "error.cwColor": "Non-neutral cw colour weights are not supported yet",
    "error.missingEntry": "Missing compatible playback entry: 全体構造",
    "error.loadResource": "Failed to read resource ({status}): {path}",
    "error.unsupportedData": "This demo needs the unpacked E-mote / PSB v4 data of this repository",
    "error.unknownModel": "Unknown model; pick another one from the list",
    "error.runtimeNotReady": "FreeMote runtime not ready; check the CDN connection",
    "error.webgl": "WebGL initialisation failed; enable hardware acceleration",
    "error.modelUnrecognized": "The runtime cannot recognise this model",
  },
};

export const languages = Object.keys(messages);

export function translate(language, key, values = {}) {
  const template = messages[language]?.[key] ?? messages.zh[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (_, name) => (values[name] ?? ""));
}

/** 显式指定 > 浏览器语言；只依赖 URL，避免禁用存储时抛错。 */
export function pickLanguage() {
  const requested = new URL(location.href).searchParams.get("lang");
  if (languages.includes(requested)) return requested;
  return (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";
}

export function applyTranslations(language) {
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  const titleKey = document.documentElement.dataset.i18nTitle;
  if (titleKey) document.title = translate(language, titleKey);
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = translate(language, node.dataset.i18n);
  }
  for (const node of document.querySelectorAll("[data-i18n-label]")) {
    node.setAttribute("aria-label", translate(language, node.dataset.i18nLabel));
  }
}
