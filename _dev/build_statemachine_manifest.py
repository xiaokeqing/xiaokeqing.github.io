# -*- coding: utf-8 -*-
"""把 docs/amadeus-research/data/statemachine.json 变成**运行时可取**的
static/kurisu/statemachine.json —— 逐节点补上 medium 档图集的分页几何（真实字节数），
并逐文件核对 static/kurisu/medium/ 里的文件确实存在、大小与元数据一致。

口径：
  · 37 个节点 = 37 个"图内剪辑"（statemachine.json 的 node_count 就是 37）
  · 49 个图集文件（9 个剪辑是 0.5× 新生成的，会分 2~4 页）
  · 元数据来源：web/meta/<clip>.json 的 medium_pages；9 个新生成的取 _dev/medium-manifest.json
用法：python _dev/build_statemachine_manifest.py [--dry]
"""
import json
import os
import sys

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
gen = json.load(open(GEN_META, encoding='utf-8'))['clips']

problems = []
tot_referenced = 0
files_seen = set()
files_seen_hi = set()
rows = []
nodes_out = []

for n in sm['nodes']:
    clip = n['clip']
    meta = json.load(open(os.path.join(SRC_META, clip + '.json'), encoding='utf-8'))
    raw_pages = meta.get('medium_pages')
    origin = 'copied'
    if not raw_pages:
        g = gen.get(clip)
        if not g:
            problems.append('%s: 既无 source medium_pages，也不在 _dev/medium-manifest.json' % clip)
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
        tot_referenced += real
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
    rows.append((clip, n['frames'], n['frameIntervalMs'], n['loopMode'], origin,
                 len(pages), sum(p['bytes'] for p in pages)))

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
    'host_triggered_entries': sm.get('host_triggered_entries'),
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
    mf['clipsMedium'] = {
        'note': '37 个"图内剪辑"的 medium 档（其中 6 段另有 hi 档）。由 _dev/build_statemachine_manifest.py '
                '从 docs/amadeus-research/data/statemachine.json 一次生成，与 static/kurisu/statemachine.json 同源，不会漂移。'
                'clips.* 那 4 段（idle/speaking/thinking/opening）仍是既有 hi+boot 契约，未改动；本段是新增的第二档。',
        'count': len(cm),
        'mediumTotalBytes': tot_referenced,
        'hiTotalBytes': tot_hi,
        'clips': cm,
    }
    json.dump(mf, open(MANIFEST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('clipsMedium 段（%d 段）→ %s' % (len(cm), MANIFEST))
print('OK：%d 节点 / %d 边 / medium %d 文件 %.2f MB / hi %d 文件 %.2f MB → %s' %
      (len(nodes_out), len(sm['edges']), len(files_seen), tot_referenced / 1048576,
       len(files_seen_hi), tot_hi / 1048576, SM_OUT))
print('体积表 →', TABLE)
