# -*- coding: utf-8 -*-
"""告警噪音指数 · 静态数据生成器（Python 3 stdlib，无第三方依赖）

产出：static/data/noise-index.json  （Hugo 原样拷进 public/data/，/noise/ 页面 fetch 它）
      → 页面上所有数字都从这份 JSON 来，模板里不写死任何一个数。

这一页回答的问题只有一句：**告警面板里有多少条其实是噪声？**
所以产物里同时给「分子（心跳条数）」和「分母（alert 总数）」，占比一律由这两个数现算 ——
不允许出现"占比写 0.949、条数却是别的分母"这种自相矛盾（踩过一次，见 §口径冲突留档）。

两种取数模式，出处都写进产物（页面照抄，不美化）：
  --from-written   直接用已核实的摘要数字（srv2 eve.json 分析，2026-10-18 核过），
                   产物写 source = "已核实摘要(2026-10-18)" —— **绝不伪装成实时取数**；
  --in <file>      真的去数一遍，支持三种输入（按内容自动识别）：
                     · eve.json / eve.json.gz（Suricata JSON Lines，每行一个事件）
                     · 事件数组 [{"event_type":"alert", ...}, ...]
                     · 已聚合摘要 {"totalAlerts":…, "byRule":[…]}（现场补算占比）

三条铁律（与站内其它公开页同口径）：
  · 取不到就 available:false + reason 原文，**不补数**、不写 0 顶替；
  · 占比（share / noiseRatio）只能由 count / total 现算；
  · 先判心跳、再判其余 —— 心跳是 94.9% 的那一条，判晚了等于没判。

用法：
  python -X utf8 scripts/noise/build-noise.py --from-written
  python -X utf8 scripts/noise/build-noise.py --from-written --dry-run     # 只打印统计
  python -X utf8 scripts/noise/build-noise.py --in /opt/suricata/logs/eve.json \
         --window "2026-10-11 ~ 10-18" --out /tmp/noise.json
退出码：0 = 产物已写（或 dry-run 通过）；1 = 连产物都写不出来；2 = 参数错误
"""
from __future__ import print_function

import argparse
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(ROOT, 'static', 'data', 'noise-index.json')
CST = timezone(timedelta(hours=8))          # 产物里的 generatedAt 用 +08:00（与 cve-digest 同口径）

# ---------------------------------------------------------------- 已核实摘要
# 出处：srv2 /opt/suricata/logs/eve.json（2026-10-11 09:23 ~ 2026-10-18 12:00 UTC），
#       1,471,376 行 → 1,475,091 行；alert 293,482 条，其中 278,405 条是同一个心跳。
# 同一组数在站点里还有两处复用，改数必须三处一起改：
#   docs/噪音指数设计-20261018.md:30/143、content/posts/purple-team-self-attack-20261018.md:120
WRITTEN_SOURCE = '已核实摘要(2026-10-18)'
WRITTEN_WINDOW = '2026-10-11 ~ 10-18'
WRITTEN_TOTAL = 293482          # alert 事件总数（样本期合计）
WRITTEN_HB = 278405             # 其中心跳告警条数
HB_SID = 2013031                # 腾讯云 agent 心跳的 Suricata SID
HB_SRC = '10.0.0.10'
HB_DST = '169.254.0.4'
HB_MSG = '腾讯云 agent 心跳：POST http://169.254.0.4/ca_report.cgi（每 5 分钟一次）'
GAP_RULE = '100110'
GAP_MSG = 'Cowrie 登录失败：120 秒内 5 次（按失败次数判）'
GAP_NOTE = ('10-17 全天 Cowrie 只有 19 条 login.failed，对 14,061 条 login.success —— '
            '机器人拿泄露口令表一枪就中，「失败 5 次」在这套蜜罐上永远凑不齐。'
            '所以「命中 0」证明的是这条规则没东西可判，不是没人攻击。')

NOTES_WRITTEN = [
    '数据来源：srv2 /opt/suricata/logs/eve.json，窗口 2026-10-11 09:23 ~ 10-18 12:00 UTC，'
    '1,471,376 行 → 1,475,091 行；本页数字来自对这份日志的分析，不是实时取数。',
    '口径冲突留档：交付说明里写的是「278,405 / 279,099 = 94.9%」，但 278,405 ÷ 279,099 = 99.75%，'
    '这两个数对不上。与设计文档、紫队复盘一致的是 278,405 / 293,482 = 94.86%（记作 94.9%），本页取后者；'
    '279,099 这个分母没有找到出处，留档待核 —— 宁可写清冲突，也不挑一个"看起来顺眼"的分母。',
    '蜜罐量级（同一窗口）：10-17 单日 Cowrie 14,147 个会话（login.success 14,061 / login.failed 19）；'
    ':2222 的 flow 139,987 条。会话数是比 Suricata 单包告警更硬的行为信号。',
    '「噪音 / 信号」的判据只有一条：同一个 sid（或同一组 src→dst）在窗口内反复发生、且不含任何攻击语义 = 噪音；'
    '其余一律算信号，不做二次猜测。',
    '本页数字由 scripts/noise/build-noise.py 写入；--from-written 模式 = 已核实摘要，'
    '--in 模式才是现场数 eve.json。产物里 source 字段写明是哪一种。',
]


def now_iso():
    return datetime.now(CST).replace(microsecond=0).isoformat()


def pct(count, total):
    """占比一律现算；分母为 0 就返回 None（不写 0 —— "算不出"与"就是 0"是两件事）。"""
    if not total:
        return None
    return round(float(count) / float(total), 4)


# ------------------------------------------------------------------ 判心跳 ----
def is_heartbeat(ev):
    """先判心跳：sid 命中，或 src/dst 这对固定内网地址命中（两条都算，防 sid 变更）。"""
    al = ev.get('alert') or {}
    if al.get('signature_id') == HB_SID:
        return True
    src = ev.get('src_ip') or ''
    dst = ev.get('dest_ip') or ''
    return src == HB_SRC and dst == HB_DST and ev.get('dest_port') in (80, None)


def rule_msg(ev):
    al = ev.get('alert') or {}
    return al.get('signature') or al.get('signature_id') or '(未给出规则名)'


# -------------------------------------------------------------- 现场数事件 ----
def read_events(path):
    """读 eve.json / eve.json.gz / 事件数组 / 已聚合摘要，返回 (events|None, summary|None, 行数)。"""
    opener = io.open
    if path.lower().endswith('.gz'):
        import gzip
        opener = gzip.open
    with opener(path, 'rt', encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    s = text.lstrip('\ufeff \t\r\n')
    if not s:
        return None, None, 0
    if s[0] == '[':                                   # 事件数组
        data = json.loads(s)
        return (data if isinstance(data, list) else []), None, len(text.splitlines())
    if s[0] == '{':
        try:                                          # 单个 JSON 对象：可能是摘要
            obj = json.loads(s)
        except ValueError:
            obj = None
        if isinstance(obj, dict) and ('totalAlerts' in obj or 'byRule' in obj):
            return None, obj, len(text.splitlines())
    events = []                                       # JSON Lines
    lines = 0
    for ln in text.splitlines():
        lines += 1
        ln = ln.strip()
        if not ln:
            continue
        try:
            events.append(json.loads(ln))
        except ValueError:
            continue                                  # 坏行跳过（eve.json 尾部常见被截断的一行）
    return events, None, lines


def build_from_events(events, window):
    counts = {}
    msgs = {}
    total = 0
    for ev in events:
        if not isinstance(ev, dict) or ev.get('event_type') != 'alert':
            continue
        total += 1
        key = HB_SID if is_heartbeat(ev) else ((ev.get('alert') or {}).get('signature_id') or 0)
        counts[key] = counts.get(key, 0) + 1
        if key not in msgs:
            msgs[key] = HB_MSG if key == HB_SID else rule_msg(ev)
    if total == 0:
        return None
    hb = counts.get(HB_SID, 0)
    return assemble(total=total, hb=hb, counts=counts, msgs=msgs, window=window,
                    source='eve 现场统计', extra_note=None)


def build_from_summary(obj, window):
    total = int(obj.get('totalAlerts') or 0)
    if total <= 0:
        return None
    counts = {}
    msgs = {}
    extra = obj.get('notes')
    for row in (obj.get('byRule') or []):
        sid = row.get('sid')
        key = HB_SID if (sid == HB_SID or row.get('class') == 'noise') else (sid or 0)
        counts[key] = counts.get(key, 0) + int(row.get('count') or 0)
        msgs.setdefault(key, row.get('msg') or (HB_MSG if key == HB_SID else str(sid)))
    return assemble(total=total, hb=counts.get(HB_SID, 0), counts=counts, msgs=msgs,
                    window=window or obj.get('window') or '', source='eve 摘要',
                    extra_note=extra)


def assemble(total, hb, counts, msgs, window, source, extra_note=None):
    """把「总条数 + 分规则条数」装配成产物；占比全部现算。"""
    ratio = pct(hb, total)
    by_rule = []
    for sid, cnt in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if sid == HB_SID:
            cls, msg = 'noise', msgs.get(sid, HB_MSG)
        else:
            cls, msg = 'signal', msgs.get(sid, str(sid))
        by_rule.append({
            'sid': sid if sid else None,
            'msg': msg,
            'count': cnt,
            'share': pct(cnt, total),
            'class': cls,
        })
    gap = None
    if GAP_RULE.isdigit():
        hits = counts.get(int(GAP_RULE), 0)
        gap = {'rule': GAP_RULE, 'hits': hits, 'note': GAP_NOTE}
    notes = []
    if extra_note:
        notes.extend(str(x) for x in extra_note)
    notes.append('占比一律由 条数 ÷ alert 总数 现算（分母 %d），不做二次凑数。' % total)
    return {
        'generatedAt': now_iso(),
        'source': source,
        'window': window,
        'available': True,
        'totalAlerts': total,
        'heartbeat': {'sid': HB_SID, 'count': hb, 'share': ratio, 'src': HB_SRC, 'dst': HB_DST},
        'signalAlerts': total - hb,
        'noiseRatio': ratio,
        'byRule': by_rule,
        'detectorGap': gap,
        'notes': notes,
    }


def build_from_written():
    counts = {HB_SID: WRITTEN_HB}
    msgs = {HB_SID: HB_MSG}
    # 其余告警：只给"总数相减"的合计，不逐条编 sid —— 没核对过的规则不配发假 sid。
    counts[0] = WRITTEN_TOTAL - WRITTEN_HB
    msgs[0] = '其余告警（alert 总数 − 心跳，未逐条归类）'
    d = assemble(total=WRITTEN_TOTAL, hb=WRITTEN_HB, counts=counts, msgs=msgs,
                 window=WRITTEN_WINDOW, source=WRITTEN_SOURCE)
    d['byRule'].append({
        'sid': GAP_RULE and int(GAP_RULE), 'msg': GAP_MSG, 'count': 0, 'share': 0.0, 'class': 'signal',
    })
    d['byRule'].sort(key=lambda r: (-(r['count'] or 0), r['sid'] or 0))
    d['notes'] = list(NOTES_WRITTEN)
    return d


def unavailable(reason, window=''):
    """取不到就如实写读不到：available:false + reason 原文 + 不补数。页面据此写「读不到」。"""
    return {
        'generatedAt': now_iso(),
        'source': '读不到',
        'window': window,
        'available': False,
        'reason': reason,
        'totalAlerts': None,
        'heartbeat': None,
        'signalAlerts': None,
        'noiseRatio': None,
        'byRule': [],
        'detectorGap': None,
        'notes': ['取不到就写读不到 —— 不补数。本产物没有用任何默认值/示例值顶替缺失字段。'],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='生成 /noise/ 页面的静态数据（告警噪音指数）')
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--from-written', action='store_true',
                     help='用已核实摘要的数字（source = 已核实摘要(2026-10-18)，非实时）')
    src.add_argument('--in', dest='inp', metavar='FILE',
                     help='eve.json / eve.json.gz / 事件数组 / 已聚合摘要')
    ap.add_argument('--window', default='', help='窗口文案，例如 "2026-10-11 ~ 10-18"')
    ap.add_argument('--out', default=DEFAULT_OUT, help='产物路径（默认 static/data/noise-index.json）')
    ap.add_argument('--dry-run', action='store_true', help='只打印统计，不写文件')
    args = ap.parse_args(argv)

    if args.from_written:
        d = build_from_written()
    else:
        p = args.inp
        if not os.path.isfile(p):
            d = unavailable('输入文件不存在：%s' % p, args.window)
        else:
            try:
                events, summary, _lines = read_events(p)
            except (IOError, OSError) as e:
                events, summary = None, None
                d = unavailable('输入文件读不到：%s' % e, args.window)
            except ValueError as e:
                events, summary = None, None
                d = unavailable('输入不是合法 JSON/JSON Lines：%s' % e, args.window)
            else:
                built = None
                if summary is not None:
                    try:
                        built = build_from_summary(summary, args.window)
                    except (TypeError, ValueError) as e:
                        built = None
                        d = unavailable('摘要结构对不上：%s' % e, args.window)
                elif events is not None:
                    built = build_from_events(events, args.window)
                if built is None:
                    d = unavailable('这份输入里没有一条 event_type=alert 的事件（有效行 0）', args.window)
                else:
                    d = built

    if d['available']:
        print('alert 总数 %d ｜ 心跳 %d ｜ 占比 %.2f%% ｜ 信号 %d ｜ 规则 %d 条' % (
            d['totalAlerts'], d['heartbeat']['count'], (d['noiseRatio'] or 0) * 100,
            d['signalAlerts'], len(d['byRule'])))
        print('source = %s ｜ window = %s' % (d['source'], d['window']))
    else:
        print('读不到（%s）—— 不补数' % d.get('reason'))

    if args.dry_run:
        return 0
    try:
        out_dir = os.path.dirname(os.path.abspath(args.out))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        with io.open(args.out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    except (IOError, OSError) as e:
        print('产物写不出来：%s' % e, file=sys.stderr)
        return 1
    print('已写 %s（%d 字节）' % (args.out, os.path.getsize(args.out)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
