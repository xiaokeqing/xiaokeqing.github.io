#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数字复算 —— 把写进文档/简历里的数字，重新算一遍。

为什么要有这个：文档里的数字一旦过期（比如"24h 告警 29 万条"），面试或演示时被追问
就会发现对不上。这个脚本只做一件事：**从线上接口和仓库文件里重新算**，然后和
"口径表"里的值比较，过期就报错。

用法：
    python audit-numbers.py                       # 默认线上
    python audit-numbers.py --api http://127.0.0.1:9900 --api-host demo.xiaokeqing.cn
    python audit-numbers.py --site F:/7AAA/AI/blog/public     # 顺便算静态站规模

退出码：0 = 全部对得上；1 = 有数字对不上（说明文档过期了）。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------- 口径表
# 每项：key、说明、来源（api 路径 / site 文件）、取值函数名、容差（相对）、是否硬要求
EXPECT = [
    ('alerts24h', '过去 24h 告警总数', 'api:/api/public/alerts.js', 'alerts_total', 0.35, False),
    ('noiseRatio', '低价值事件占比（噪音率）', 'api:/api/public/alerts.js', 'noise_ratio', 0.05, False),
    ('dailyAvailable', '今日日报已生成', 'api:/api/public/daily.js', 'daily_available', 0, True),
    ('archiveDays', '日报归档天数（≥1）', 'api:/api/public/daily/index.json', 'archive_days', 0, True),
    ('releaseFiles', '线上发布文件数', 'api:/api/public/deploy.js', 'release_files', 0, True),
    ('posts', '笔记篇数（index-lite）', 'api:/index-lite.json', 'posts', 0, True),
    ('assetBytes', '前端资产字节上限', 'const:176MiB', 'asset_cap', 0, False),
]

# 文档里出现过的"基线数字"（人工确认过的口径，改动时要一起改这里）
DOC_BASELINE = {
    'posts': 51,
    'tree_files': 3147,
    'assertions': 86,
}


def fetch_json(url, host=None):
    url = urllib.parse.quote(url, safe=':/?&=%#')
    req = urllib.request.Request(url, headers={'User-Agent': 'xk-number-audit/1.0'})
    if host:
        req.add_header('Host', host)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        return None, '%s: %s' % (type(e).__name__, e)
    if isinstance(j, dict) and 'data' in j and 'code' in j:
        return j['data'], None
    return j, None


# ---------------------------------------------------------------- 取值器
def alerts_total(j):
    if not isinstance(j, dict):
        return None
    st = j.get('stats24h') if isinstance(j.get('stats24h'), dict) else {}
    return j.get('alertTotal') or st.get('total') or j.get('total')


def noise_ratio(j):
    """低价值占比 =（低危 + 信息）/ 总数；接口给的是分严重程度的计数。"""
    if not isinstance(j, dict):
        return None
    sev = None
    for k in ('alertsBySeverity', 'bySeverity', 'severity'):
        if isinstance(j.get(k), dict):
            sev = j[k]
            break
    if not sev:
        st = j.get('stats24h') if isinstance(j.get('stats24h'), dict) else {}
        for k in ('alertsBySeverity', 'bySeverity'):
            if isinstance(st.get(k), dict):
                sev = st[k]
                break
    if not sev:
        return None
    low = float(sev.get('LOW') or sev.get('low') or 0)
    info = float(sev.get('INFO') or sev.get('info') or 0)
    total = sum(float(v or 0) for v in sev.values() if isinstance(v, (int, float)))
    if total <= 0:
        return None
    return round((low + info) / total * 100.0, 2)


def daily_available(j):
    return bool(isinstance(j, dict) and j.get('available'))


def archive_days(j):
    return (j or {}).get('count') if isinstance(j, dict) else None


def release_files(j):
    if not isinstance(j, dict):
        return None
    rel = j.get('release') if isinstance(j.get('release'), dict) else {}
    return rel.get('files') or j.get('files')


def posts_count(j):
    if not isinstance(j, dict):
        return None
    for k in ('count',):
        if isinstance(j.get(k), int):
            return j[k]
    for k in ('notes', 'items', 'pages'):
        if isinstance(j.get(k), list):
            return len(j[k])
    return None


GETTERS = {
    'alerts_total': alerts_total,
    'noise_ratio': noise_ratio,
    'daily_available': daily_available,
    'archive_days': archive_days,
    'release_files': release_files,
    'posts': posts_count,
}


def site_stuff(site_dir):
    html = 0
    files = 0
    if site_dir and os.path.isdir(site_dir):
        for root, _dirs, fs in os.walk(site_dir):
            for f in fs:
                files += 1
                if f.endswith('.html'):
                    html += 1
    return html, files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site-api', default='https://xiaokeqing.cn')
    ap.add_argument('--api', default='https://demo.xiaokeqing.cn')
    ap.add_argument('--api-host', default=None)
    ap.add_argument('--site', default=None, help='本地构建产物目录，给了就顺便算 html/文件数')
    ap.add_argument('--group', default='all', choices=['all', 'api', 'site'],
                    help='只查接口数字（在 srv1 跑）或只查站点数字（在 srv2 跑）')
    a = ap.parse_args()

    rows = []
    fails = 0
    cache = {}

    def get_json(api_path):
        if api_path not in cache:
            base = a.api if api_path.startswith('/api/') else a.site_api
            cache[api_path] = fetch_json(base + api_path, host=a.api_host)
        return cache[api_path]

    for key, label, src, gname, tol, hard in EXPECT:
        if a.group == 'api' and not src.startswith('api:/api/'):
            continue
        if a.group == 'site' and not src.startswith('api:/index'):
            continue
        if src.startswith('const:'):
            rows.append((label, src[6:], src[6:], 'PASS', '常量口径，脚本内固定'))
            continue
        path = src.split(':', 1)[1]
        j, err = get_json(path)
        if err:
            rows.append((label, '取不到', '-', 'FAIL' if hard else 'WARN', err))
            fails += 1 if hard else 0
            continue
        fn = GETTERS.get(gname)
        val = fn(j) if fn else None
        if val is None:
            rows.append((label, '取不到', '-', 'FAIL' if hard else 'WARN', '接口有响应但字段缺失：%s' % path))
            fails += 1 if hard else 0
            continue
        base = DOC_BASELINE.get(key)
        if base is None:
            rows.append((label, str(val), '-', 'PASS', '实时值（无基线可比）'))
            continue
        ok = abs(val - base) <= max(1, base * tol)
        rows.append((label, '%s（基线 %s）' % (val, base), str(base),
                     'PASS' if ok else 'FAIL',
                     '在容差 %d%% 内' % int(tol * 100) if ok else '偏差超过 %d%%，文档该更新了' % int(tol * 100)))
        if not ok:
            fails += 1

    w = max(len(r[0]) for r in rows)
    print('数字复算 · api=%s site-api=%s' % (a.api, a.site_api))
    for label, now, base, st, why in rows:
        print('  %-4s %-*s  现在=%-24s  %s' % (st, w, label, now, why))

    if a.site:
        html, files = site_stuff(a.site)
        print('\n构建产物：%d 个 html / %d 个文件（口径基线 %d 个文件，容差 ±2%%）'
              % (html, files, DOC_BASELINE['tree_files']))
        ok = abs(files - DOC_BASELINE['tree_files']) <= max(5, DOC_BASELINE['tree_files'] * 0.02)
        if not ok:
            print('  FAIL 文件数偏差超过 2%%：文档里的"3147 个文件"该更新了')
            fails += 1
        else:
            print('  PASS 文件数与文档一致')

    print('\n合计：%s（断言条数基线 %d）' % ('全部对得上' if fails == 0 else '%d 项对不上' % fails,
                                       DOC_BASELINE['assertions']))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
