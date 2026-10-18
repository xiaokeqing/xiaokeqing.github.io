#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""24h 小时 × 国家 聚合 → static/data/geo-hourly.json（攻击来源地图的「时间回放」数据）

用法（在仓库根目录）：
  python -X utf8 scripts/geo/hourly.py                          # 自动找本地样本，再退到本机 API
  python -X utf8 scripts/geo/hourly.py --in _dev/api-samples/geo-live.json
  python -X utf8 scripts/geo/hourly.py --api http://127.0.0.1:9900/api/public/alerts
  python -X utf8 scripts/geo/hourly.py --out static/data/geo-hourly.json

输出（有小时 × 国家时）：
  {"generatedAt":"2026-10-18T07:00","hours":24,"source":"/api/public/alerts@24h",
   "series":[{"hour":"2026-10-18T07:00","total":N,"byCountry":{"FR":N,...}}, ...],
   "available":true,"notes":"..."}
取不到分布时（口径见下）：
  {"available":false,"reason":"...", "series":[...24 个小时总量...], ...}

口径（红线，和地图卡一致）：
  · 只有输入里**真的有**「每条告警的时间 + 国家」时才做小时 × 国家聚合；
  · 公开接口（/api/public/geo、/api/public/home 的 geo 块、/api/public/alerts）只给
    24h byCountry 合计 + 小时总量 trend —— 见 docs/design-geo-endpoint.md。
    这种输入**不拆**：不拿 24h 合计按比例摊到小时（那是编造），直接 available:false + reason；
    trend 的 24 个小时总量照实写进 series（total 真实、byCountry 留空），方便对账。
  · 末尾「当前小时」桶不完整（窗口没走完），不计入 24 桶，写在 notes 里。
"""
import argparse
import datetime as _dt
import json
import os
import sys
import urllib.request
from collections import OrderedDict

HOURS = 24
DEFAULT_API = 'http://127.0.0.1:9900/api/public/alerts'
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(REPO, 'static', 'data', 'geo-hourly.json')

# 本地样本候选（先仓库内，再任务里提到的工作区路径）
CANDIDATES = [
    os.path.join(REPO, '_dev', 'api-samples', 'geo-live.json'),
    os.path.join(REPO, '_dev', 'api-samples', 'alerts.json'),
    r'E:\DeepSeek1\work\_dev\api-samples\geo-live.json',
]


def now_str():
    return _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def fetch_json(url, timeout=6):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'xk-lab-hourly/1.0 (+static-site data generator)',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def unwrap(obj):
    """兼容 {code,message,data} 信封；不是信封就原样返回。"""
    if isinstance(obj, dict) and isinstance(obj.get('data'), dict) and ('code' in obj or 'message' in obj):
        return obj['data']
    return obj


# ---------------------------------------------------------------- 时间归一

def norm_hour(ts, base=None):
    """任意时间表示 → 'YYYY-MM-DDTHH:00'（取整到小时）；失败返回 None。
    支持：'YYYY-MM-DD HH:MM:SS' / 'YYYY-MM-DDTHH:MM:SS' / 纪元秒·毫秒 / 只有 'HH:00'。"""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        v = float(ts)
        if v > 1e12:      # 毫秒
            v /= 1000.0
        try:
            return _dt.datetime.fromtimestamp(v).strftime('%Y-%m-%dT%H:00')
        except (ValueError, OSError, OverflowError):
            return None
    s = str(ts).strip()
    if not s:
        return None
    # 只有小时标签（alerts.json 的 stats24h.trend[].time = 'HH:00'）
    if len(s) == 5 and s[2] == ':':
        try:
            hh = int(s[:2])
        except ValueError:
            return None
        base = base or _dt.datetime.now()
        d = base.replace(hour=hh, minute=0, second=0, microsecond=0)
        if d > base:
            d -= _dt.timedelta(days=1)
        return d.strftime('%Y-%m-%dT%H:00')
    s = s.replace('/', '-').replace(' ', 'T')
    if s.endswith('Z'):
        s = s[:-1]
    try:
        d = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return d.strftime('%Y-%m-%dT%H:00')


def add_hours(hour_label, n):
    d = _dt.datetime.strptime(hour_label, '%Y-%m-%dT%H:00') + _dt.timedelta(hours=n)
    return d.strftime('%Y-%m-%dT%H:00')


# ---------------------------------------------------------------- 输入抽取

def alerts_of(d):
    """拿「每条告警」列表（只有当列表里真的有国家字段时才值得聚合）。"""
    if not isinstance(d, dict):
        return []
    for key in ('list', 'alerts', 'items', 'records'):
        v = d.get(key)
        if isinstance(v, list) and v:
            return [x for x in v if isinstance(x, dict)]
    return []


def country_of(a):
    """从一条告警里取 ISO-3166 alpha-2 国家码；取不到返回 ''。"""
    for key in ('srcGeo', 'geo', 'srcgeo'):
        g = a.get(key)
        if isinstance(g, dict):
            cc = g.get('country') or g.get('countryCode') or g.get('code') or g.get('country_code')
            if isinstance(cc, str) and len(cc.strip()) == 2 and cc.strip().isalpha():
                return cc.strip().upper()
    for key in ('countryCode', 'country', 'srcCountry', 'country_code'):
        cc = a.get(key)
        if isinstance(cc, str) and len(cc.strip()) == 2 and cc.strip().isalpha():
            return cc.strip().upper()
    return ''


def time_of(a):
    for key in ('occurredAt', 'occurred_at', 'timestamp', 'ts', 'time', 'startTime', 'endTime'):
        if a.get(key) is not None:
            return a.get(key)
    return None


def agg_per_alert(d):
    """真·小时 × 国家聚合。数据里没有国家/时间就返回 None（不编）。"""
    rows = alerts_of(d)
    if not rows:
        return None
    per = {}
    hit_country = hit_time = 0
    for a in rows:
        cc = country_of(a)
        ts = time_of(a)
        if not cc:
            continue
        hit_country += 1
        hl = norm_hour(ts, _dt.datetime.now())
        if not hl:
            continue
        hit_time += 1
        per.setdefault(hl, {})
        per[hl][cc] = per[hl].get(cc, 0) + 1
    if not hit_country or not hit_time:
        return None
    hours = sorted(per.keys())[-HOURS:]
    series = []
    for hl in hours:
        bc = OrderedDict(sorted(per[hl].items(), key=lambda kv: (-kv[1], kv[0])))
        series.append({'hour': hl, 'total': sum(bc.values()), 'byCountry': bc})
    return series


def trend_buckets(d):
    """小时总量（没有国家维度）。返回 [(hour, count), ...]，取不到返回 []。"""
    tr = d.get('trend') if isinstance(d, dict) else None
    if not isinstance(tr, list):
        stats = d.get('stats24h') if isinstance(d, dict) else None
        tr = stats.get('trend') if isinstance(stats, dict) else None
    if not isinstance(tr, list) or not tr:
        return []
    base = None
    g = d.get('generatedAt') or d.get('generated_at')
    if g:
        try:
            base = _dt.datetime.strptime(str(g).replace('T', ' ').strip()[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            base = None
    out = []
    for p in tr:
        if not isinstance(p, dict):
            continue
        ts = p.get('ts') or p.get('time') or p.get('hour')
        c = p.get('count', p.get('total'))
        if c is None:
            continue
        hl = norm_hour(ts, base)
        if not hl:
            continue
        try:
            out.append((hl, int(c)))
        except (TypeError, ValueError):
            continue
    return out


def build_from(data, source):
    """返回最终对象（dict）。available 只在**真的有小时 × 国家**时为 True。"""
    per_alert = agg_per_alert(data)
    geo_meta = {}
    if isinstance(data, dict):
        for k in ('generatedAt', 'geoSource', 'window', 'coverage', 'thresholds', 'countryCount'):
            if k in data:
                geo_meta[k] = data[k]
    generated = str(geo_meta.get('generatedAt') or now_str())
    if per_alert:
        return OrderedDict([
            ('generatedAt', generated),
            ('hours', len(per_alert)),
            ('source', source + '@' + str(geo_meta.get('window') or '24h')),
            ('available', True),
            ('series', per_alert),
            ('notes', '逐条告警按「发生时间整点 × 国家码」直接计数（未做任何摊派）。'),
        ])

    buckets = trend_buckets(data)
    if not buckets:
        return OrderedDict([
            ('available', False),
            ('reason', '输入里既没有「每条告警的时间 + 国家」，也没有小时总量 trend（%s）' % source),
            ('generatedAt', generated),
            ('hours', 0),
            ('source', source),
            ('series', []),
            ('notes', '取不到小时数据；页面显示「读不到」，不回放。'),
        ])

    # 末尾「当前小时」桶不完整：trend 首尾都可能是窗口边界，这里只丢**最后**一桶（当前小时未走完）
    keep = buckets[-HOURS:]
    dropped = None
    if len(buckets) > HOURS:
        dropped = buckets[-1]
        keep = buckets[-HOURS - 1:-1]
    series = [OrderedDict([('hour', hl), ('total', c), ('byCountry', OrderedDict())])
              for hl, c in keep]
    reason = ('公开接口只给 24h 国家合计 + 小时总量（docs/design-geo-endpoint.md），'
              '没有「小时 × 国家」交叉；按口径不拿合计摊到小时（会变成编造分布），'
              '因此不回放 —— 需要后端按小时输出 byCountry，或提供带国家字段的逐条告警。')
    note = ('series 里的 total 是真实小时总量（照实保留，byCountry 留空，表示「该小时国家分布读不到」）。')
    if dropped:
        note += ' 末尾 %s 桶是当前小时（窗口未走完），未计入 24 桶。' % dropped[0]
    return OrderedDict([
        ('generatedAt', generated),
        ('hours', len(series)),
        ('source', source + '@' + str(geo_meta.get('window') or '24h')),
        ('available', False),
        ('reason', reason),
        ('series', series),
        ('notes', note),
    ])


def main(argv=None):
    ap = argparse.ArgumentParser(description='24h 小时 × 国家 聚合 → static/data/geo-hourly.json')
    ap.add_argument('--in', dest='inp', help='输入 JSON（样本/接口快照）；不给就自动找')
    ap.add_argument('--out', dest='out', default=DEFAULT_OUT)
    ap.add_argument('--api', dest='api', default=None, help='本机 API（默认 %s）' % DEFAULT_API)
    ap.add_argument('--timeout', type=float, default=6.0)
    args = ap.parse_args(argv)

    data = None
    source = ''
    tried = []

    if args.inp:
        p = args.inp if os.path.isabs(args.inp) else os.path.join(REPO, args.inp)
        if not os.path.isfile(p):
            sys.stderr.write('输入不存在：%s\n' % p)
            return 2
        data, source = read_json(p), os.path.relpath(p, REPO).replace('\\', '/')
    else:
        for p in CANDIDATES:
            tried.append(p)
            if os.path.isfile(p):
                data, source = read_json(p), os.path.relpath(p, REPO).replace('\\', '/') \
                    if os.path.abspath(p).startswith(os.path.abspath(REPO)) else p
                break
        if data is None and args.api is not False:
            url = args.api or DEFAULT_API
            tried.append(url)
            try:
                data, source = fetch_json(url, args.timeout), url
            except Exception as e:  # noqa: BLE001 - 取不到就如实报
                data, source = None, url
                sys.stderr.write('API 读不到（%s）：%s\n' % (url, e))

    if data is None:
        out = OrderedDict([
            ('available', False),
            ('reason', '样本与 API 都读不到（试过：%s）' % '、'.join(tried)),
            ('generatedAt', now_str()),
            ('hours', 0),
            ('source', ''),
            ('series', []),
            ('notes', '取不到数据；页面显示「读不到」，不回放。'),
        ])
    else:
        out = build_from(unwrap(data), source)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(tmp, args.out)

    ser = out.get('series') or []
    print('写出 %s' % os.path.relpath(args.out, REPO).replace('\\', '/'))
    print('available=%s hours=%s source=%s' % (out.get('available'), out.get('hours'), out.get('source')))
    if ser:
        print('首桶 %s total=%s' % (ser[0]['hour'], ser[0]['total']))
        print('末桶 %s total=%s' % (ser[-1]['hour'], ser[-1]['total']))
        if out.get('available'):
            print('末桶国家数 %s' % len(ser[-1].get('byCountry') or {}))
    else:
        print('（没有小时桶：%s）' % (out.get('reason') or ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
