// 仅用于本仓库的已解包 Motion 数据；二进制格式参考见 README。
import { fail } from "./i18n.js";
const utf8 = new TextEncoder();
const join = (parts) => {
  const result = new Uint8Array(parts.reduce((size, part) => size + part.length, 0));
  let offset = 0;
  for (const part of parts) { result.set(part, offset); offset += part.length; }
  return result;
};
const u32 = (value) => {
  const bytes = new Uint8Array(4);
  new DataView(bytes.buffer).setUint32(0, value, true);
  return bytes;
};
const array = (values) => join([Uint8Array.of(0x10), u32(values.length), Uint8Array.of(0x10), ...values.map(u32)]);

export function nameTable(names) {
  const root = { children: new Map(), id: 0 };
  names.forEach((name, index) => {
    if (name.includes("\0")) throw fail("error.nulField");
    let node = root;
    for (const byte of [...utf8.encode(name), 0]) {
      if (!node.children.has(byte)) node.children.set(byte, { children: new Map() });
      node = node.children.get(byte);
    }
    node.index = index;
  });
  const bases = [1], parents = [0], terminals = [], used = new Set([0]);
  const visit = (node) => {
    if (!node.children.size) { bases[node.id] = node.index; terminals[node.index] = node.id; return; }
    const codes = [...node.children.keys()];
    let base = 1;
    // ponytail: 小模型用线性寻找空槽；大量模型批处理时换占用位图。
    while (codes.some((code) => used.has(base + code))) base++;
    bases[node.id] = base;
    for (const [code, child] of node.children) {
      child.id = base + code;
      parents[child.id] = node.id;
      used.add(child.id);
    }
    for (const child of node.children.values()) visit(child);
  };
  visit(root);
  return [Array.from(bases, (v) => v ?? 0), Array.from(parents, (v) => v ?? 0), terminals];
}

export function encodePsb(model, resources, extras) {
  const keys = new Set(), strings = new Map();
  const collect = (value) => {
    if (Array.isArray(value)) value.forEach(collect);
    else if (value && typeof value === "object") {
      for (const [key, child] of Object.entries(value)) { keys.add(key); collect(child); }
    } else if (typeof value === "string" && !/^#resource[#@]\d+$/.test(value)) {
      if (value.includes("\0")) throw fail("error.nulString");
      if (!strings.has(value)) strings.set(value, strings.size);
    }
  };
  collect(model);
  const names = [...keys].sort(), ids = new Map(names.map((key, i) => [key, i]));
  const encode = (value) => {
    if (value === null) return Uint8Array.of(1);
    if (typeof value === "boolean") return Uint8Array.of(value ? 3 : 2);
    if (typeof value === "number") {
      if (!Number.isFinite(value)) throw fail("error.nonFinite");
      if (Number.isInteger(value) && value >= -2147483648 && value <= 2147483647) {
        return join([Uint8Array.of(8), u32(value)]);
      }
      const bytes = new Uint8Array(9);
      if (Number.isInteger(value)) {
        if (!Number.isSafeInteger(value)) throw fail("error.integerRange");
        bytes[0] = 0x0c;
        new DataView(bytes.buffer).setBigInt64(1, BigInt(value), true);
      } else {
        bytes[0] = 0x1f;
        new DataView(bytes.buffer).setFloat64(1, value, true);
      }
      return bytes;
    }
    if (typeof value === "string") {
      const ref = /^#resource([#@])(\d+)$/.exec(value);
      if (ref) {
        const index = Number(ref[2]), pool = ref[1] === "#" ? resources : extras;
        if (!(pool[index] instanceof Uint8Array)) throw fail("error.missingResource", { value });
        return join([Uint8Array.of(ref[1] === "#" ? 0x1c : 0x25), u32(index)]);
      }
      return join([Uint8Array.of(0x18), u32(strings.get(value))]);
    }
    const isList = Array.isArray(value);
    const entries = isList ? value : Object.keys(value).sort((a, b) => ids.get(a) - ids.get(b));
    const parts = entries.map((entry) => encode(isList ? entry : value[entry]));
    let offset = 0;
    const offsets = parts.map((part) => { const start = offset; offset += part.length; return start; });
    return join([Uint8Array.of(isList ? 0x20 : 0x21),
      ...(isList ? [] : [array(entries.map((key) => ids.get(key)))]), array(offsets), ...parts]);
  };
  const header = new Uint8Array(56), view = new DataView(header.buffer);
  header.set([80, 83, 66, 0, 4, 0, 0, 0]);
  view.setUint32(8, 56, true);
  const sections = [header];
  let position = header.length;
  const add = (headerOffset, bytes) => {
    view.setUint32(headerOffset, position, true);
    sections.push(bytes); position += bytes.length;
  };
  add(12, join(nameTable(names).map(array)));
  add(36, encode(model));
  let stringOffset = 0;
  const stringData = [...strings.keys()].map((s) => join([utf8.encode(s), Uint8Array.of(0)]));
  add(16, array(stringData.map((s) => { const offset = stringOffset; stringOffset += s.length; return offset; })));
  add(20, join(stringData));
  const addResources = (pool, offset) => {
    let total = 0;
    add(offset, array(pool.map((bytes) => { const start = total; total += bytes.length; return start; })));
    add(offset + 4, array(pool.map((bytes) => bytes.length)));
    const padding = new Uint8Array((4 - position % 4) % 4);
    sections.push(padding); position += padding.length;
    add(offset + 8, join(pool));
  };
  addResources(extras, 44);
  addResources(resources, 24);
  let a = 1, b = 0;
  for (const byte of [...header.slice(8, 40), ...header.slice(44, 56)]) {
    a = (a + byte) % 65521; b = (b + a) % 65521;
  }
  view.setUint32(40, ((b << 16) | a) >>> 0, true);
  return join(sections);
}

export function partVariables(metadata, values = {}) {
  const controls = metadata.customSelectorList.filter((control) => control.enabled);
  for (const label of Object.keys(values)) {
    if (!controls.some((control) => control.label === label)) throw fail("error.partControlUnsupported", { label });
  }
  const result = {};
  for (const control of controls) {
    const value = values[control.label] ?? metadata.variableMetaInfoList.find((variable) => variable.id === control.label)?.defaultValue ?? 0;
    const selected = control.optionList.filter((option) => value >= option.lower && value <= option.upper);
    if (!Number.isFinite(value) || selected.length !== 1) throw fail("error.partControlRange", { label: control.label, value });
    result[control.label] = value;
    for (const option of control.optionList) {
      if (option.label) result[option.label] = option === selected[0] ? option.onValue : option.offValue;
    }
  }
  return result;
}

export function prepareModel(model) {
  const metadata = model.metadata;
  const ranged = metadata.selectorControl.filter((control) => control.enabled && control.optionList.some((option) => option.lower !== undefined));
  // 新模型以 face_mouth 选部件、face_talk 控制开合；旧合并口控会覆盖 face_mouth。
  metadata.mouthControl = metadata.mouthControl.filter((control) => !ranged.some((selector) => selector.label === control.label));
  for (const selector of ranged) {
    // 3.9 的选择器按选项序号工作，不识别新版 lower/upper 区间。
    for (const timeline of metadata.timelineControl) {
      for (const track of timeline.variableList.filter((track) => track.label === selector.label)) {
        for (const frame of track.frameList) {
          if (!frame.content) continue;
          const index = selector.optionList.findIndex((option) => frame.content.value >= option.lower && frame.content.value <= option.upper);
          if (index < 0) throw fail("error.selectorRange", { label: selector.label, value: frame.content.value });
          frame.content.value = index;
        }
      }
    }
    for (const option of selector.optionList) { delete option.lower; delete option.upper; }
  }
  const opacity = (layers) => {
    for (const layer of layers) {
      for (const { content } of layer.frameList ?? []) {
        if (!content || content.cw === undefined || !(content.mask & 0x80000000)) continue;
        // ponytail: 只适配当前素材的中性 RGB 权重；彩色 cw 需完整的颜色混合实现。
        if (![0x808080, 0x7f7f7f].includes(content.cw >>> 8)) throw fail("error.cwColor");
        content.opa = Math.round((content.opa ?? 255) * (content.cw & 255) / 255);
        content.mask = ((content.mask & 0x7fffffff) | 0x400) >>> 0;
        delete content.cw;
      }
      opacity(layer.children ?? []);
    }
  };
  for (const object of Object.values(model.object)) {
    for (const motion of Object.values(object.motion)) opacity(motion.layer ?? []);
  }
  model.spec = "ems";
  for (const source of Object.values(model.source)) source.texture.type = "RGBA8";
  if (!model.object?.all_parts?.motion?.全体構造) throw fail("error.missingEntry");
  // ponytail: 旧 WebGL 3.9 在顶层合成入口呈现黑色剪影；完整特效需新版运行时验证。
  model.metadata.base = { chara: "all_parts", motion: "全体構造" };
  return model;
}

export async function loadModel(name, report = () => {}) {
  /* ★2026-10-17 修：原来写 `./红莉栖E-mote模型/${name}/` 是**相对页面 URL** 的，
     在 /ai/ 这类子路径页面会 404（实测 /ai/红莉栖E-mote模型/... ⇒ error.loadResource）。
     改成相对**本模块自身**的 URL（import.meta.url）⇒ 永远指向 /kurisu/emote/loader/ 下。 */
  const folder = new URL(`./红莉栖E-mote模型/${name}/`, import.meta.url).href;
  const url = (path) => folder + path.split("/").map(encodeURIComponent).join("/");
  const get = async (path) => {
    const response = await fetch(url(path));
    if (!response.ok) throw fail("error.loadResource", { status: response.status, path });
    return response;
  };
  report("status.readingIndex");
  const [model, resx] = await Promise.all([
    get(`${name}.psb.m.json`).then((r) => r.json()),
    get(`${name}.psb.m.resx.json`).then((r) => r.json()),
  ]);
  if (model.metadata?.format !== "emote" || resx.PsbVersion !== 4) throw fail("error.unsupportedData");
  const resources = [], extras = [];
  for (const [key, values] of Object.entries(resx.ExtraFlattenArrays)) {
    const bytes = new Uint8Array(values.length * 4), view = new DataView(bytes.buffer);
    values.forEach((value, i) => view.setFloat32(i * 4, value, true));
    extras[Number(key.slice(1))] = bytes;
  }
  for (const [key, path] of Object.entries(resx.ExtraResources)) {
    extras[Number(key.slice(1))] = new Uint8Array(await (await get(path)).arrayBuffer());
  }
  // 浏览器负责 PNG 解码；不要把现有 PNG 当成原始 BC7 数据上传。
  for (const [key, path] of Object.entries(resx.Resources)) {
    report("status.decodingAtlas", { index: resources.filter(Boolean).length + 1, total: Object.keys(resx.Resources).length });
    const bitmap = await createImageBitmap(await (await get(path)).blob(), { premultiplyAlpha: "none", colorSpaceConversion: "none" });
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width; canvas.height = bitmap.height;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    context.drawImage(bitmap, 0, 0);
    resources[Number(key)] = new Uint8Array(context.getImageData(0, 0, canvas.width, canvas.height).data.buffer);
    bitmap.close(); canvas.width = canvas.height = 1;
  }
  prepareModel(model);
  report("status.assembling");
  return { bytes: encodePsb(model, resources, extras), metadata: model.metadata };
}
