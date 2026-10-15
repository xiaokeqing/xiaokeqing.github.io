# -*- coding: utf-8 -*-
"""把 docs/amadeus-research/data/statemachine.json 变成**运行时可取**的
static/kurisu/statemachine.json —— 逐节点补上 medium 档图集的分页几何（真实字节数），
并逐文件核对 static/kurisu/medium/ 里的文件确实存在、大小与元数据一致。

口径：
  · 38 个节点 = 38 个"图内剪辑"（statemachine.json 的 node_count 就是 38）
  · 49 个图集文件（9 个剪辑是 0.5× 新生成的，会分 2~4 页）
  · 元数据来源：web/meta/<clip>.json 的 medium_pages；9 个新生成的取 _dev/medium-manifest.json
  · 资产别名：节点带 `atlas_clip` 时，几何/图集全部沿用源剪辑的 meta（0.17.0α 的"返回过渡"
    key_point_to_thinking 就是 thinking_to_key_point 的逐帧倒序 → 复用同一张图集，新增字节 = 0），
    节点带 `reverse: True` 时播放器反向取帧；两者都只在需要时写进产物。
  · 同时把 manifest.json 的 clipsMedium 段与 stateMachine 段里可推导的字段（nodeCount/edgeCount/
    hiClips/hiTotalBytes/hostTriggeredEntries）一起刷新，两处不会再与 statemachine.json 漂移。
用法：python _dev/build_statemachine_manifest.py [--dry]
"""
import json
import os
import sys

try:                                  # 控制台是 GBK 时，非 GBK 字符（⇒ 等）会让本脚本在**写盘前**就崩，
    sys.stdout.reconfigure(encoding='utf-8')   # 于是看起来"跑过了"其实一个字都没写。强制 UTF-8 输出。
except Exception:
    pass

REPO = r'F:\7AAA\AI\blog'
SRC_META = r'E:\DeepSeek1\work\_kurisu-full\web\meta'
SM_IN = os.path.join(REPO, 'docs', 'amadeus-research', 'data', 'statemachine.json')
SM_OUT = os.path.join(REPO, 'static', 'kurisu', 'statemachine.json')
MEDIA = os.path.join(REPO, 'static', 'kurisu', 'medium')
HI = os.path.join(REPO, 'static', 'kurisu', 'hi')
GEN_META = os.path.join(REPO, '_dev', 'medium-manifest.json')
TABLE = os.path.join(REPO, '_dev', 'medium-volume-table.md')
DRY = '--dry' in sys.argv

sm = json.load(open(SM_IN, encoding='utf-8'))

# ---- 第二批"活起来"的 4 条边（T33-b 视线跟随用；2026-10-15 批次2）---------------
# 事实：`idle → 侧脸族` 原本**没有直边**（只能 idle→idle_closed_eye→idle 打转），
# 实测 2000 步只覆盖 9/37 个节点。这里给三条 idle 变体各加 1 条通往侧脸族的正概率边
# （prob = 0.1 / 0.15 / 0.15），再加 1 条侧脸族回 idle 的边（prob = 0.3）—— 正好 4 条，
# 且**全部是概率边**（prob ≠ 0 ⇒ 自动游走可走 ✓），不是宿主触发入口。
# 站主要"一个正脸一个侧脸"：正脸 idle 家族 6 个节点 ⇄ 侧脸族 3 个节点。
GAZE_EDGES = [
    {'from': 'idle', 'to': 'idle_side_wind', 'from_id': '_8ms718k', 'to_id': '_cpu0zpb', 'prob': 0.1},
    {'from': 'idle1', 'to': 'idle_side_soft_wind', 'from_id': '_5qqy7vp', 'to_id': '_vo874gi', 'prob': 0.15},
    {'from': 'idle2', 'to': 'idle_side_soft_wind', 'from_id': '_6fknbp9', 'to_id': '_vo874gi', 'prob': 0.15},
    {'from': 'idle_side_wind', 'to': 'idle', 'from_id': '_cpu0zpb', 'to_id': '_8ms718k', 'prob': 0.3},
]
# ★修正（窗口 Q，2026-10-15）：原守卫拿**边端点名**（'idle'）去比**节点 id**（'_8ms718k'）——
#   两者永不相同（上游节点没有 name，节点名在 `clip` 字段上），于是这 4 条边必然被拒、
#   一条都加不上 ⇒ 重跑生成器会把补丁 05 的 4 条边改回 88 条，正是要防的漂移。
#   改成比 `clip`（与边端点同一套命名），并且**非法端点直接失败**，不再静默跳过。
_node_names = set(n['clip'] for n in sm['nodes'])
_have = set((e['from'], e['to']) for e in sm['edges'])
_added = 0
for _e in GAZE_EDGES:
    if (_e['from'], _e['to']) in _have:
        continue
    if _e['from'] not in _node_names or _e['to'] not in _node_names:
        raise SystemExit('视线边引用了不存在的节点名：%s' % _e)
    sm['edges'].append(_e)
    _added += 1
print('视线跟随的 4 条边：新增 %d 条 / 共 %d 条 ⇒ 边总数 %d'
      % (_added, len(GAZE_EDGES), len(sm['edges'])))

gen = json.load(open(GEN_META, encoding='utf-8'))['clips']

problems = []
tot_referenced = 0
files_seen = set()
medium_file_bytes = {}   # file → 真实字节；同一份图集被多个节点引用时只算一次
files_seen_hi = set()
rows = []
nodes_out = []

for n in sm['nodes']:
    clip = n['clip']
    # 资产别名（见文件头）：几何与图集沿用源剪辑的 meta
    meta_clip = n.get('atlas_clip') or clip
    meta = json.load(open(os.path.join(SRC_META, meta_clip + '.json'), encoding='utf-8'))
    raw_pages = meta.get('medium_pages')
    origin = 'copied' if meta_clip == clip else 'copied(%s)' % meta_clip
    if not raw_pages:
        g = gen.get(meta_clip)
        if not g:
            problems.append('%s: 既无 source medium_pages，也不在 _dev/medium-manifest.json' % meta_clip)
            continue
        raw_pages = g['medium_pages']
        origin = 'generated(0.5x q=%s)' % g.get('quality')
    pages = []
    for p in raw_pages:
        f = p['file']
        path = os.path.join(MEDIA, f)
        if not os.path.exists(path):
            problems.append('%s: 缺文件 %s' % (clip, f))
            continue
        real = os.path.getsize(path)
        decl = p.get('bytes')
        if decl and decl != real:
            problems.append('%s: %s 字节不一致 元数据=%s 实际=%s' % (clip, f, decl, real))
        files_seen.add(f)
        # 字节按文件去重：同一张图集被别名节点引用时不能算两次，否则 medium_total_bytes
        # 会虚高，与 static/kurisu/medium/ 的真实占用对不上（这正是"新增字节 = 0"的核对口径）
        medium_file_bytes[f] = real
        pages.append({
            'url': 'kurisu/medium/' + f,
            'file': f,
            'tile_w': p['tile_w'], 'tile_h': p['tile_h'],
            'cols': p['cols'], 'rows': p['rows'],
            'frames': p['frames'],
            'first_frame': p['first_frame'], 'last_frame': p['last_frame'],
            'pixels': p['pixels'], 'bytes': real,
        })
    mouth = meta.get('mouth_patch') or {}
    # hi 档（可选）：主页最常用那几段才有。几何取 web/meta 的 atlas_pages，文件必须真在 static/kurisu/hi/
    hi_pages = []
    hi_bytes = 0
    for p in (meta.get('atlas_pages') or []):
        path = os.path.join(HI, p['file'])
        if not os.path.exists(path):
            continue
        real = os.path.getsize(path)
        if p.get('bytes') and p['bytes'] != real:
            problems.append('%s: hi/%s 字节不一致 元数据=%s 实际=%s' % (clip, p['file'], p['bytes'], real))
        files_seen_hi.add(p['file'])
        hi_bytes += real
        hi_pages.append({
            'url': 'kurisu/hi/' + p['file'],
            'file': p['file'],
            'tile_w': p['tile_w'], 'tile_h': p['tile_h'],
            'cols': p['cols'], 'rows': p['rows'],
            'frames': p['frames'],
            'first_frame': p['first_frame'], 'last_frame': p['last_frame'],
            'pixels': p['pixels'], 'bytes': real,
        })
    nodes_out.append({
        'id': n['id'],
        'clip': clip,
        'is_root': bool(n.get('is_root')),
        'loopMode': n['loopMode'],
        'phase': n.get('phase'),
        'frameIntervalMs': n['frameIntervalMs'],
        'fps': n.get('fps'),
        'frames': n['frames'],
        'frame_size': n['frame_size'],
        'opaque_bbox': n.get('opaque_bbox'),
        'tier': n.get('tier'),
        'incoming_prob_positive': n.get('incoming_prob_positive'),
        'has_mouth_profile': bool(n.get('has_mouth_profile')),
        'atlas_source': origin,
        'medium': {'pages': pages, 'bytes': sum(p['bytes'] for p in pages)},
        'hi': ({'pages': hi_pages, 'bytes': hi_bytes} if hi_pages else None),
        # 嘴部补丁：34x18 的小图（P0-④ 的闭嘴层素材），这里只登记来源，不搬运
        'mouthPatch': {
            'file': mouth.get('file'),
            'size': mouth.get('size'),
            'overlay_entry': mouth.get('overlay_entry'),
            'closed_frame_idx': mouth.get('closed_frame_idx'),
        },
    })
    if n.get('atlas_clip'):
        nodes_out[-1]['atlas_clip'] = n['atlas_clip']
    if n.get('reverse'):
        nodes_out[-1]['reverse'] = True
    rows.append((clip, n['frames'], n['frameIntervalMs'], n['loopMode'], origin,
                 len(pages), sum(p['bytes'] for p in pages)))

tot_referenced = sum(medium_file_bytes.values())   # 按文件去重后的真实占用
extra = sorted(set(os.listdir(MEDIA)) - files_seen)
if extra:
    problems.append('static/kurisu/medium/ 里有 %d 个没被任何节点引用的文件：%s' % (len(extra), extra))
extra_hi = sorted(set(os.listdir(HI)) - files_seen_hi) if os.path.isdir(HI) else []
if extra_hi:
    problems.append('static/kurisu/hi/ 里有 %d 个没被任何节点引用的文件：%s' % (len(extra_hi), extra_hi))
tot_hi = sum(n['hi']['bytes'] for n in nodes_out if n.get('hi'))

node_clips = [x['clip'] for x in nodes_out]
edge_bad = []
for e in sm['edges']:
    if e['from'] not in node_clips or e['to'] not in node_clips:
        edge_bad.append(e)
if edge_bad:
    problems.append('边引用了不存在的节点：%s' % edge_bad[:5])

# ---- host_triggered_entries：改成从 prob=0 出边**派生**（单一事实来源）----
# 【2026-10-15 接手批】原来这里是 sm.get('host_triggered_entries') —— 直接从源文件抄。
#   实测源文件抄漏了一个：prob=0 的出边目标是 9 个，而声明只有 8 个（缺 thinking_trans）。
#   后果不是"少一条注释"：kurisu-player.js 用这份名单做宿主触发入口，
#   缺 thinking_trans ⇒ 那条边永远进不去，状态机在 idle_str_wind 之后会卡住。
#   现在从 prob=0 边派生，并与源文件声明比对：不一致就报出来（不再静默漂移）。
declared_hte = sm.get('host_triggered_entries') or []
zero_targets = sorted({e['to'] for e in sm['edges'] if e.get('prob') == 0})
if sorted(declared_hte) != zero_targets:
    # **不阻断**：错的是源文件的声明（抄漏 thinking_trans），产物按 prob=0 派生 → 派生值才是对的。
    # 只把不一致大声报出来，免得下次有人反过来以为产物写错了。
    print('!! 警告：源文件 host_triggered_entries 与 prob=0 出边目标不一致（产物按派生值写）')
    print('   声明 %d 个：%s' % (len(declared_hte), sorted(declared_hte)))
    print('   实算 %d 个：%s' % (len(zero_targets), zero_targets))

out = {
    'format': 'xiaokeqing.kurisu.statemachine.v1',
    'provenance': {
        'source': 'docs/amadeus-research/data/statemachine.json（原版 graph_config.json 的机械提取）',
        'builtBy': '_dev/build_statemachine_manifest.py',
        'atlasDir': 'static/kurisu/medium/',
        'note': '每个节点补上 medium 档图集分页几何 + 真实字节数；帧播放契约与 manifest.json 的 clips.* 一致 '
                '（columns/rows/tile 尺寸来自图集本身，frameIntervalMs/loopMode/frames 来自原状态机）',
    },
    'root': sm['root'],
    'node_count': len(nodes_out),
    'edge_count': len(sm['edges']),
    'host_triggered_entries': zero_targets,   # ★派生自 prob=0 出边（见上方说明）
    'clips_not_in_graph': sm.get('clips_not_in_graph'),
    'loop_mode_counts': sm.get('loop_mode_counts'),
    'medium_total_bytes': tot_referenced,
    'hi_total_bytes': tot_hi,
    'hi_clips': [n['clip'] for n in nodes_out if n.get('hi')],
    'nodes': nodes_out,
    'edges': sm['edges'],
}

lines = []
lines.append('| 剪辑 | 帧数 | 帧间隔ms | loopMode | 来源 | 页数 | medium 字节 | hi 字节 |')
lines.append('|---|---:|---:|---|---|---:|---:|---:|')
for c, fr, iv, lm, org, np_, b in sorted(rows, key=lambda r: -r[6]):
    hb = next((n['hi']['bytes'] for n in nodes_out if n['clip'] == c and n.get('hi')), 0)
    lines.append('| `%s` | %d | %s | %s | %s | %d | %s | %s |' % (c, fr, iv, lm, org, np_, format(b, ','), format(hb, ',') if hb else '—'))
lines.append('')
lines.append('medium 合计 %d 个剪辑 / %d 个图集文件 / %s B = %.2f MB' %
             (len(rows), len(files_seen), format(tot_referenced, ','), tot_referenced / 1048576))
lines.append('hi 合计 %d 个剪辑 / %d 个图集文件 / %s B = %.2f MB（名单：%s）' %
             (len([n for n in nodes_out if n.get('hi')]), len(files_seen_hi), format(tot_hi, ','),
              tot_hi / 1048576, ', '.join(n['clip'] for n in nodes_out if n.get('hi'))))

if problems:
    print('!! 阻断问题：')
    for p in problems:
        print('   ', p)
    sys.exit(2)

if not DRY:
    json.dump(out, open(SM_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(TABLE, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    # ---- 同时把 37 个剪辑的几何写进 manifest.json 的 clipsMedium 段 ----
    # 为什么要有这一段：manifest.json 是"剪辑清单"的正式契约文件，只读它的人
    # （别的工具/别的 AI）也该看见全部 37 段；字段名沿用**既有契约名**
    # （frameWidth/frameHeight/columns/frames/frameIntervalMs/loopMode）——不改名，
    # 改名的代价是同步改播放器（docs/实施计划 §1.4 明写这条是契约）。
    # 单一事实来源仍是 docs/amadeus-research/data/statemachine.json，两个文件由本脚本一次生成，不会漂移。
    MANIFEST = os.path.join(REPO, 'static', 'kurisu', 'manifest.json')
    mf = json.load(open(MANIFEST, encoding='utf-8'))
    cm = {}
    for n in nodes_out:
        pages = (n['hi']['pages'] if n.get('hi') else n['medium']['pages'])
        cm[n['clip']] = {
            'frames': n['frames'],
            'frameIntervalMs': n['frameIntervalMs'],
            'loopMode': n['loopMode'],
            'frameWidth': pages[0]['tile_w'],
            'frameHeight': pages[0]['tile_h'],
            'columns': pages[0]['cols'],
            'tier': ('hi' if n.get('hi') else 'medium'),
            'atlas': {
                'medium': {'pages': n['medium']['pages'], 'bytes': n['medium']['bytes']},
            },
            'source': 'statemachine.json / ' + n['atlas_source'],
        }
        if n.get('hi'):
            cm[n['clip']]['atlas']['hi'] = {'pages': n['hi']['pages'], 'bytes': n['hi']['bytes']}
        if n.get('mouthPatch') and n['mouthPatch'].get('file'):
            cm[n['clip']]['mouthPatch'] = n['mouthPatch']
        # 倒放复用：manifest 里也要看得见（只读 manifest 的工具/AI 才知道这段不是新素材）
        if n.get('atlas_clip'):
            cm[n['clip']]['atlas_clip'] = n['atlas_clip']
        if n.get('reverse'):
            cm[n['clip']]['reverse'] = True
    mf['clipsMedium'] = {
        'note': '%d 个"图内剪辑"的 medium 档（其中 6 段另有 hi 档）。由 _dev/build_statemachine_manifest.py '
                '从 docs/amadeus-research/data/statemachine.json 一次生成，与 static/kurisu/statemachine.json 同源，不会漂移。'
                'clips.* 那 4 段（idle/speaking/thinking/opening）仍是既有 hi+boot 契约，未改动；本段是新增的第二档。'
                '其中 key_point_to_thinking 是 0.17.0α 的返回过渡：atlas_clip + reverse 表示它复用 '
                'thinking_to_key_point 的同一张图集、播放时倒放，没有新增任何素材字节。' % len(cm),
        'count': len(cm),
        'mediumTotalBytes': tot_referenced,
        'hiTotalBytes': tot_hi,
        'clips': cm,
    }
    # stateMachine 段里凡是**能从同一事实来源推导**的字段，也由本脚本写，
    # 免得它手改后与 statemachine.json 漂移（nodeCount/edgeCount 曾长期停在 37/87）。
    st = mf.get('stateMachine')
    if isinstance(st, dict):
        st['nodeCount'] = len(nodes_out)
        st['edgeCount'] = len(sm['edges'])
        st['hiClips'] = [n['clip'] for n in nodes_out if n.get('hi')]
        st['hiTotalBytes'] = tot_hi
        st['hostTriggeredEntries'] = zero_targets
    json.dump(mf, open(MANIFEST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('clipsMedium 段（%d 段）→ %s' % (len(cm), MANIFEST))
print('OK：%d 节点 / %d 边 / medium %d 文件 %.2f MB / hi %d 文件 %.2f MB → %s' %
      (len(nodes_out), len(sm['edges']), len(files_seen), tot_referenced / 1048576,
       len(files_seen_hi), tot_hi / 1048576, SM_OUT))
print('体积表 →', TABLE)
