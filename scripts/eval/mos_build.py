#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T13-③ MOS / ABX 主观评测 · 试卷生成器（出题 → 发卷 → 收卷 → 算分）

做什么
    从音频目录出**盲听试卷**：MOS 打分表 + ABX 配对表 + 零第三方请求的本地播放页，
    用固定随机种子打乱顺序、隐藏 A/B/X 身份，保证**同一次评测可复现** ✓

盲法怎么做（不这么做 MOS 结果不可信 ✗）
  ① **不透明音频副本**：把两套系统的音频统一转成 PCM wav 并改名为 `<item>_a.wav` / `<item>_b.wav`，
     ABX 试次再额外复制一份 `<item>_x.wav`（内容等于 A 或 B 之一）。
     ⇒ 文件名、扩展名、码率都看不出身份，**评委翻 devtools 也看不出来** ✓
     ⇒ 顺带把试卷做成"一个文件夹打包即发"，评委本地双击即可，全程不联网 ✓
  ② A/B 与 (被测 / 对照) 的对应、X 等于谁，只写在 `mos-abx-key-*.json`（**发卷前不给评委** ✗）
  ③ 每个评委有自己的题目顺序（顺序效应抵消）
  ④ 音频经 ffmpeg 统一为 22050Hz 单声道 PCM ⇒ 容器/采样率不构成系统间差异 ✓

用法
    PY=...python.exe
    & $PY -X utf8 scripts/eval/mos_build.py `
        --audio-dir   E:\\DeepSeek1\\work\\_tts-trial\\sample8\\dist `
        --control-dir E:\\DeepSeek1\\work\\_eval-t13\\mos\\control-sapi-zh `
        --lines       E:\\DeepSeek1\\work\\_tts-trial\\lines60-bilingual.json `
        --out-dir     E:\\DeepSeek1\\work\\_eval-t13\\mos\\run-01 `
        --seed 20261015 --raters R01,R02,R03

    对照组怎么选（见 mos_template.md §2）：优先"上一代真音色"，退而用"占位音"（弱对照，必须写明 ✗）
    不带 `--control-dir` 也能跑：只出单系统 MOS，没有 A/B 与 ABX ✓

产出（--out-dir）
    audio/                    不透明 wav（发给评委的就是这个文件夹）
    mos-items-<stamp>.json    题目清单 + 真实映射（**只有主试看**）
    mos-abx-key-<stamp>.json  ABX 正确答案（**发卷前不要给评委**）
    mos-sheet-<stamp>.csv     MOS 打分表（空表，rater × item）
    mos-abx-<stamp>.csv       ABX 答题表（空表）
    mos-player-<stamp>.html   本地盲听播放页（自动导出上面两张表）
    README-<stamp>.md         发卷说明
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

AUDIO_EXT = (".m4a", ".wav", ".webm", ".mp3", ".flac", ".ogg")
FFMPEG_CANDIDATES = (
    "ffmpeg",
    r"E:\DeepSeek1\work\_kurisu-017\video-pipeline\tools\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe",
)


def find_ffmpeg():
    for c in FFMPEG_CANDIDATES:
        exe = shutil.which(c) or (c if Path(c).is_file() else None)
        if exe:
            return exe
    return None


def find_audio(directory: Path):
    out = {}
    if not directory.is_dir():
        return out
    for p in sorted(directory.iterdir()):
        if p.suffix.lower() in AUDIO_EXT:
            out[p.stem] = p
    return out


def normalize_to_wav(src: Path, dst: Path, ffmpeg: str | None) -> str:
    """统一成 22050Hz 单声道 PCM wav；没有 ffmpeg 就原样复制（并在报告里标出这个口径差异 ✗）。"""
    if ffmpeg:
        proc = subprocess.run(
            [ffmpeg, "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "22050",
             "-c:a", "pcm_s16le", str(dst)],
            capture_output=True,
        )
        if proc.returncode == 0 and dst.is_file() and dst.stat().st_size > 1024:
            return "ffmpeg->pcm_s16le 22050Hz mono"
        print(f"[WARN] ffmpeg failed on {src.name}: {proc.stderr.decode('utf-8','replace')[:200]}", file=sys.stderr)
    shutil.copyfile(src, dst.with_suffix(src.suffix))
    return f"raw-copy({src.suffix})  ← 无 ffmpeg，容器未统一，盲法偏弱 ✗"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MOS/ABX sheet builder (opaque-audio blinding)")
    ap.add_argument("--audio-dir", required=True, help="被测系统（本轮 TTS）的音频目录")
    ap.add_argument("--control-dir", default="", help="对照组音频目录（同 id 命名）")
    ap.add_argument("--lines", default="", help="台词库 JSON（有 id/ja/zh 就显示文本）")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=20261015)
    ap.add_argument("--raters", default="R01,R02,R03")
    ap.add_argument("--n", type=int, default=0, help="抽多少条（0=全部）")
    ap.add_argument("--abx-ratio", type=float, default=0.5, help="做成 ABX 试次的比例")
    args = ap.parse_args(argv)

    test_dir = Path(args.audio_dir).resolve()
    if not test_dir.is_dir():
        raise SystemExit(f"[FATAL] audio dir not found: {test_dir}")
    control_dir = Path(args.control_dir).resolve() if args.control_dir else None
    out_dir = Path(args.out_dir).resolve()
    (out_dir / "audio").mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    rng = random.Random(args.seed)

    texts = {}
    if args.lines:
        data = json.loads(Path(args.lines).read_text(encoding="utf-8"))
        for line in data.get("lines", []):
            texts[line["id"]] = {"ja": line.get("ja", ""), "zh": line.get("zh", "")}

    test = find_audio(test_dir)
    control = find_audio(control_dir) if control_dir else {}
    ids = [i for i in test if i in control] if control else list(test)
    if not ids:
        raise SystemExit("[FATAL] no usable ids (need same stem in both dirs when --control-dir is used)")
    rng.shuffle(ids)
    if args.n:
        ids = ids[: args.n]

    ffmpeg = find_ffmpeg()
    modes = set()
    n_abx = int(round(len(ids) * args.abx_ratio)) if control else 0
    abx_ids = set(rng.sample(ids, n_abx)) if n_abx else set()

    items, abx_key = [], {}
    for item_id in ids:
        # 每题独立决定：A 段放谁、B 段放谁
        a_src, b_src = ("test", "control") if control else ("test", "test")
        if control and rng.random() < 0.5:
            a_src, b_src = b_src, a_src
        files = {}
        for label, src_kind, src_path in (("A", a_src, test), ("B", b_src, control if control else test)):
            name = f"{item_id}_{label.lower()}.wav"
            src = (src_path if control else test)[item_id]
            modes.add(normalize_to_wav(src, out_dir / "audio" / name, ffmpeg))
            files[label] = f"audio/{name}"
        entry = {
            "item_id": item_id,
            "ja": texts.get(item_id, {}).get("ja", ""),
            "zh": texts.get(item_id, {}).get("zh", ""),
            "files": dict(files),
            "ab": {"A": a_src, "B": b_src},
            "abx": item_id in abx_ids,
        }
        if item_id in abx_ids:
            x_is = rng.choice(["A", "B"])
            src = out_dir / files[x_is]
            x_path = out_dir / "audio" / f"{item_id}_x.wav"
            shutil.copyfile(src, x_path)
            entry["xIs"] = x_is
            entry["files"]["X"] = f"audio/{item_id}_x.wav"
            abx_key[item_id] = {"A": a_src, "B": b_src, "xIs": x_is}
        items.append(entry)

    raters = [r.strip() for r in args.raters.split(",") if r.strip()]
    rater_order = {r: rng.sample([i["item_id"] for i in items], len(items)) for r in raters}

    (out_dir / f"mos-items-{stamp}.json").write_text(
        json.dumps({"seed": args.seed, "testDir": str(test_dir),
                    "controlDir": str(control_dir) if control_dir else None,
                    "containerMode": sorted(modes), "items": items, "raters": raters,
                    "raterOrder": rater_order, "abxRatio": args.abx_ratio},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / f"mos-abx-key-{stamp}.json").write_text(
        json.dumps({"seed": args.seed, "key": abx_key,
                    "note": "A/B 是被测还是对照、X 等于 A 还是 B；**发卷前不可给评委** ✗"},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    sheet = out_dir / f"mos-sheet-{stamp}.csv"
    with open(sheet, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rater_id", "item_id", "order_in_session", "MOS_自然度_1-5", "MOS_可懂度_1-5",
                    "MOS_音色像不像_1-5", "备注"])
        for r in raters:
            for k, item_id in enumerate(rater_order[r], 1):
                w.writerow([r, item_id, k, "", "", "", ""])

    abx_sheet = out_dir / f"mos-abx-{stamp}.csv"
    if abx_ids:
        with open(abx_sheet, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["rater_id", "item_id", "order_in_session", "X是A还是B", "把握程度_1-5", "备注"])
            for r in raters:
                for k, it in enumerate([i for i in items if i["abx"]], 1):
                    w.writerow([r, it["item_id"], k, "", "", ""])

    (out_dir / f"mos-player-{stamp}.html").write_text(
        build_player(items, raters, rater_order, stamp, sheet.name, abx_sheet.name if abx_ids else ""),
        encoding="utf-8")

    readme = f"""# MOS / ABX 发卷说明（{stamp}）

- 被测：`{test_dir}`
- 对照：`{control_dir if control_dir else '（无 —— 本轮只有单系统 MOS）'}`
- 题量 {len(items)} 条 ｜ ABX {len(abx_ids)} 条 ｜ 评委 {', '.join(raters)} ｜ 种子 `{args.seed}`
- 音频口径：{'; '.join(sorted(modes))}

## 发给评委
**整个文件夹**（含 `audio/` 与 `mos-player-{stamp}.html`）。评委本地双击 HTML，全程不联网 ✓ 零第三方请求 ✓
**不要**把 `mos-abx-key-{stamp}.json` 与 `mos-items-{stamp}.json` 给评委 ✗（里面有身份与答案）
"""
    (out_dir / f"README-{stamp}.md").write_text(readme, encoding="utf-8")

    print(f"items={len(items)} abx={len(abx_ids)} raters={len(raters)} container={sorted(modes)}")
    print(f"audio  → {out_dir / 'audio'}")
    print(f"sheet  → {sheet}")
    if abx_ids:
        print(f"abx    → {abx_sheet}")
    print(f"player → {out_dir / f'mos-player-{stamp}.html'}")
    return 0


def build_player(items, raters, rater_order, stamp, sheet_name, abx_sheet_name):
    payload = [{
        "id": it["item_id"], "ja": it["ja"], "zh": it["zh"],
        "A": it["files"]["A"], "B": it["files"]["B"], "X": it["files"].get("X"),
        "abx": it["abx"],
    } for it in items]
    cfg = json.dumps({"items": payload, "raters": raters, "orders": rater_order,
                      "sheetName": sheet_name, "abxSheetName": abx_sheet_name}, ensure_ascii=False)
    return """<!doctype html>
<html lang="zh-cn"><head><meta charset="utf-8"><title>MOS / ABX 盲听试卷 · __STAMP__</title>
<style>
 body{font-family:system-ui,"Segoe UI",sans-serif;margin:0;background:#12141a;color:#e8eaf0}
 header{padding:16px 20px;background:#1b1f2a;position:sticky;top:0;border-bottom:1px solid #2b3140;z-index:5}
 h1{font-size:16px;margin:0 0 8px}
 .row{margin:14px 0;padding:14px;background:#181c26;border:1px solid #262c39;border-radius:10px}
 .q{font-size:14px;line-height:1.6}.q .ja{color:#9fd0ff}.q .zh{color:#8d93a3;font-size:13px}
 button{background:#2a3346;color:#e8eaf0;border:1px solid #3a445c;border-radius:8px;padding:6px 12px;margin:4px 6px 4px 0;cursor:pointer}
 button:hover{background:#33405a}
 label{margin-right:14px;font-size:13px}
 select,input[type=number]{background:#0f1218;color:#e8eaf0;border:1px solid #333c4f;border-radius:6px;padding:4px 6px}
 .note{color:#8d93a3;font-size:12px}
 footer{padding:18px 20px 60px}
</style></head><body>
<header>
  <h1>MOS / ABX 盲听试卷 · __STAMP__</h1>
  <div class="note">零第三方请求 · 数据不出本机 · 评分只在内存里，点「导出答卷」才落盘 ✓</div>
  <div style="margin-top:8px">评委：<select id="rater"></select>
    <span class="note">A/B 身份已隐藏（音频已改名为不透明 wav）</span></div>
</header>
<main id="main"></main>
<footer>
  <button onclick="exportCsv()">导出我的答卷（CSV）</button>
  <div class="note" id="stat"></div>
</footer>
<script>
const CFG = __CFG__;
const state = {}; let current = [];
function el(t,a,c){const e=document.createElement(t); if(a)for(const k in a)e.setAttribute(k,a[k]); if(c!=null)e.textContent=c; return e;}
function play(src){const a=new Audio(src); a.play();}
function render(){
  const rater=document.getElementById('rater').value;
  const main=document.getElementById('main'); main.innerHTML='';
  const order=CFG.orders[rater]||CFG.items.map(i=>i.id);
  current=order.map(id=>CFG.items.find(i=>i.id===id)).filter(Boolean);
  current.forEach((it,idx)=>{
    state[it.id]=state[it.id]||{mos:{},abx:{}};
    const box=el('div',{class:'row'});
    box.appendChild(el('div',{class:'q'},(idx+1)+'. ['+it.id+']'+(it.abx?' ABX 试次':'')));
    const txt=el('div',{class:'q'});
    txt.innerHTML='<span class="ja">'+(it.ja||'')+'</span><br><span class="zh">'+(it.zh||'')+'</span>';
    box.appendChild(txt);
    [['A',it.A],['B',it.B]].forEach(([lab,src])=>{
      const b=el('button',null,'▶ 播放 '+lab); b.onclick=()=>play(src); box.appendChild(b);
    });
    if(it.abx){
      const xb=el('button',null,'▶ 播放 X'); xb.onclick=()=>play(it.X); box.appendChild(xb);
      const sel=el('select');
      ['','A','B'].forEach(v=>sel.appendChild(el('option',{value:v},v===''?'X 更像谁？':v)));
      sel.onchange=()=>{state[it.id].abx.choice=sel.value;};
      box.appendChild(sel);
      const conf=el('input',{type:'number',min:1,max:5,placeholder:'把握1-5',style:'width:100px'});
      conf.onchange=()=>{state[it.id].abx.conf=conf.value;};
      box.appendChild(conf);
    }
    ['自然度','可懂度','音色像不像'].forEach(dim=>{
      const wrap=el('label',null,dim+' ');
      const s=el('select'); ['','1','2','3','4','5'].forEach(v=>s.appendChild(el('option',{value:v},v===''?'—':v)));
      s.onchange=()=>{state[it.id].mos[dim]=s.value;};
      wrap.appendChild(s); box.appendChild(wrap);
    });
    main.appendChild(box);
  });
  document.getElementById('stat').textContent='本会话已加载 '+current.length+' 题';
}
function csvEscape(v){v=(v==null?'':String(v));return /[",\\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;}
function exportCsv(){
  const rater=document.getElementById('rater').value;
  let mos='rater_id,item_id,order_in_session,MOS_自然度_1-5,MOS_可懂度_1-5,MOS_音色像不像_1-5,备注\\n';
  let abx='rater_id,item_id,order_in_session,X是A还是B,把握程度_1-5,备注\\n';
  current.forEach((it,idx)=>{
    const st=state[it.id]||{mos:{},abx:{}};
    mos+=[rater,it.id,idx+1,st.mos['自然度']||'',st.mos['可懂度']||'',st.mos['音色像不像']||'',''].map(csvEscape).join(',')+'\\n';
    if(it.abx) abx+=[rater,it.id,idx+1,st.abx.choice||'',st.abx.conf||'',''].map(csvEscape).join(',')+'\\n';
  });
  download(CFG.sheetName,mos);
  if(CFG.abxSheetName) download(CFG.abxSheetName,abx);
}
function download(name,text){
  const blob=new Blob([text],{type:'text/csv;charset=utf-8'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name; a.click();
}
(function boot(){
  const rs=document.getElementById('rater');
  CFG.raters.forEach(r=>rs.appendChild(el('option',{value:r},r)));
  rs.onchange=render; render();
})();
</script></body></html>
""".replace("__CFG__", cfg).replace("__STAMP__", stamp)


if __name__ == "__main__":
    raise SystemExit(main())
