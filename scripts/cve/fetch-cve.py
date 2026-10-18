# -*- coding: utf-8 -*-
"""CVE 每日速递 · 静态数据抓取器（Python 3 stdlib，无第三方依赖）

产出：static/data/cve-digest.json  （Hugo 原样拷进 public/data/，页面 fetch 它）

两个数据源，口径都写在产物里：
  ① CISA KEV      https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
                  官方 JSON 快照，字段 vulnerabilities[]（cveID/vendorProject/product/
                  vulnerabilityName/dateAdded/shortDescription/requiredAction/
                  knownRansomwareCampaignUse/dueDate）。**必成功**，失败就 ok:false + error 原文。
  ② NVD CVE 2.0   https://services.nvd.nist.gov/rest/json/cves/2.0
                  可选增强：只取 1 页（≤50 条），无 API key 时限速 5 次/30 秒。
                  **失败必须降级不报错**：ok:false + error 原文，nvdHigh 留空，页面据此写
                  「读不到（NVD API：<原因>）—— 不补数」。

三条铁律（与站内其它公开页同口径）：
  · 抓不到就写 ok:false + error 原文，**不伪造数据**；
  · 抓到了但没有当天/近 7 天的条目，才允许写空数组（那是"今天确实没有新增"，不同于"抓不到"）；
  · 只做字段裁剪与截断，**不改写任何原文**（shortDescription 截到 240 字符，其余照抄）。

用法：
  python -X utf8 scripts/cve/fetch-cve.py
  python -X utf8 scripts/cve/fetch-cve.py --dry-run          # 只打印统计，不写文件
  python -X utf8 scripts/cve/fetch-cve.py --date 2026-10-18  # 补跑某一天
  python -X utf8 scripts/cve/fetch-cve.py --out /tmp/x.json --timeout 20
退出码：0 = 产物已写（或有源失败但已如实记录）；1 = 连产物都写不出来
"""
from __future__ import print_function

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KEV_URL = 'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json'
NVD_URL = 'https://services.nvd.nist.gov/rest/json/cves/2.0'
UA = 'xk-lab-cve-digest/1.0 (+https://xiaokeqing.cn/tools/cve/; static daily snapshot)'
CST = timezone(timedelta(hours=8))          # 产物里的 generatedAt 用 +08:00
KEEP_FIELDS = ('cveID', 'vendorProject', 'product', 'vulnerabilityName',
               'dateAdded', 'requiredAction', 'knownRansomwareCampaignUse',
               'shortDescription')
DESC_MAX = 240
RECENT_DAYS = 7
RECENT_MAX = 40
NVD_PAGE = 50
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(ROOT, 'static', 'data', 'cve-digest.json')


# ------------------------------------------------------------------ HTTP ----
def http_json(url, timeout, retries=1, backoff=6.0):
    """GET 一个 JSON。返回 (data, err)；err 是原文（HTTPError/URLError/解析错都照抄）。"""
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={
            'User-Agent': UA,
            'Accept': 'application/json',
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            return json.loads(raw.decode('utf-8')), None
        except urllib.error.HTTPError as e:
            # 429/403/503 是 NVD 限速与维护窗口的常见脸色，等一下再试一次
            last = 'HTTP %s %s' % (e.code, e.reason)
            if e.code in (403, 429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(backoff)
                continue
            return None, last
        except urllib.error.URLError as e:
            last = 'URLError: %s' % (e.reason,)
            if attempt < retries:
                time.sleep(backoff)
                continue
            return None, last
        except Exception as e:                      # 超时、JSON 解析失败、编码错误……
            last = '%s: %s' % (type(e).__name__, e)
            return None, last
    return None, last or 'unknown error'


# ------------------------------------------------------------------ CISA KEV -
def fetch_kev(timeout):
    data, err = http_json(KEV_URL, timeout)
    if data is None:
        return None, err
    vulns = data.get('vulnerabilities')
    if not isinstance(vulns, list):
        return None, 'KEV JSON 里没有 vulnerabilities[] 数组（结构变了？）'
    return vulns, None


def trim_kev(v):
    out = {}
    for k in KEEP_FIELDS:
        val = v.get(k)
        if k == 'shortDescription' and isinstance(val, str) and len(val) > DESC_MAX:
            val = val[:DESC_MAX]
        out[k] = val
    return out


def pick_kev(vulns, day):
    """day = 目标日（UTC date）。kevNew = 当天新增；kevRecent7d = 最近 7 天（含当天）倒序 ≤40。"""
    lo = day - timedelta(days=RECENT_DAYS - 1)
    new, recent = [], []
    for v in vulns:
        added = (v.get('dateAdded') or '').strip()
        if not added:
            continue
        try:
            d = datetime.strptime(added[:10], '%Y-%m-%d').date()
        except ValueError:
            continue                            # 日期读不出来就不进任何一栏，不猜
        if d == day:
            new.append(trim_kev(v))
        if lo <= d <= day:
            recent.append(trim_kev(v))
    recent.sort(key=lambda x: (x.get('dateAdded') or '', x.get('cveID') or ''), reverse=True)
    return new, recent[:RECENT_MAX]


# ------------------------------------------------------------------ NVD ------
def nvd_window(day, backfill):
    """真实跑：今天 00:00Z → 现在；补跑（--date）：那天 00:00Z → 23:59:59Z。"""
    if backfill:
        start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(days=1) - timedelta(seconds=1)
    else:
        now = datetime.now(timezone.utc)
        start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
        end = now
    fmt = lambda d: d.strftime('%Y-%m-%dT%H:%M:%S.000')
    return start, end, fmt(start), fmt(end)


def fetch_nvd(start_s, end_s, timeout):
    q = urllib.parse.urlencode({
        'pubStartDate': start_s,
        'pubEndDate': end_s,
        'cvssV3Severity': 'HIGH',
        'resultsPerPage': NVD_PAGE,
        'startIndex': 0,
    }, safe=':.-')
    url = NVD_URL + '?' + q
    data, err = http_json(url, timeout, retries=1, backoff=7.0)
    if data is None:
        return None, err, url
    if not isinstance(data.get('vulnerabilities'), list):
        return None, 'NVD 响应里没有 vulnerabilities[] 数组（结构变了？）', url
    return data['vulnerabilities'], None, url


def trim_nvd(v):
    cve = v.get('cve') or {}
    desc = ''
    for d in cve.get('descriptions') or []:
        if (d or {}).get('lang') == 'en':
            desc = d.get('value') or ''
            break
    if len(desc) > DESC_MAX:
        desc = desc[:DESC_MAX]
    metrics = cve.get('metrics') or {}
    score, sev = None, None
    for key in ('cvssMetricV31', 'cvssMetricV30', 'cvssMetricV40', 'cvssMetricV2'):
        arr = metrics.get(key) or []
        if not arr:
            continue
        m0 = arr[0] or {}
        cd = m0.get('cvssData') or {}
        score = cd.get('baseScore')
        sev = cd.get('baseSeverity') or m0.get('baseSeverity')
        if score is not None:
            break
    return {
        'cveID': cve.get('id'),
        'published': cve.get('published'),
        'severity': sev,
        'cvssScore': score,
        'shortDescription': desc,
    }


# ------------------------------------------------------------------ main -----
def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True, description='CVE 每日速递静态数据抓取器')
    ap.add_argument('--out', default=DEFAULT_OUT, help='产物路径（默认 static/data/cve-digest.json）')
    ap.add_argument('--date', default=None, help='补跑某一天（YYYY-MM-DD，UTC）')
    ap.add_argument('--dry-run', action='store_true', help='只打印统计，不写文件')
    ap.add_argument('--timeout', type=float, default=20.0, help='单次请求超时秒数（默认 20）')
    args = ap.parse_args(argv)

    backfill = args.date is not None
    if backfill:
        try:
            day = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            print('[错误] --date 只接受 YYYY-MM-DD：%r' % (args.date,), file=sys.stderr)
            return 1
    else:
        day = datetime.now(timezone.utc).date()

    # ① CISA KEV
    vulns, kev_err = fetch_kev(args.timeout)
    if vulns is None:
        kev_new, kev_recent = [], []
    else:
        kev_new, kev_recent = pick_kev(vulns, day)

    # ② NVD（可选增强，失败降级）
    start, end, start_s, end_s = nvd_window(day, backfill)
    nvd, nvd_err, nvd_url = fetch_nvd(start_s, end_s, args.timeout)
    nvd_high = [trim_nvd(v) for v in (nvd or [])]

    generated_at = datetime.now(CST).isoformat(timespec='seconds')
    sources = [
        {'name': 'CISA KEV', 'url': KEV_URL,
         'ok': kev_err is None,
         'count': (len(vulns) if vulns is not None else 0)},
        {'name': 'NVD CVE API 2.0', 'url': NVD_URL,
         'ok': nvd_err is None,
         'count': (len(nvd) if nvd is not None else 0)},
    ]
    if kev_err is not None:
        sources[0]['error'] = kev_err
    if nvd_err is not None:
        sources[1]['error'] = nvd_err
    sources[1]['window'] = {'pubStartDate': start_s, 'pubEndDate': end_s,
                            'cvssV3Severity': 'HIGH', 'resultsPerPage': NVD_PAGE,
                            'startIndex': 0, 'requestUrl': nvd_url}

    doc = {
        'generatedAt': generated_at,
        'targetDay': day.isoformat(),
        'sources': sources,
        'kevNew': kev_new,
        'kevRecent7d': kev_recent,
        'nvdHigh': nvd_high,
        'limits': {
            'note': (
                '这是每日快照，不是实时。CISA KEV 官方按天更新（多为工作日），'
                '本文件由 scripts/cve/fetch-cve.py 抓取时定点生成。'
                'NVD 只取 1 页（≤%d 条，cvssV3Severity=HIGH），无 API key 时限速 5 次/30 秒，'
                '所以 nvdHigh 不是当天高危全量。任一源 ok:false 时页面写「读不到（原因）—— 不补数」，'
                '绝不把读不到渲染成 0 条。' % NVD_PAGE
            ),
            'kevNewRule': 'dateAdded == targetDay',
            'kevRecent7dRule': 'dateAdded ∈ [targetDay-%d, targetDay]，倒序，≤%d 条' % (RECENT_DAYS - 1, RECENT_MAX),
            'shortDescriptionMax': DESC_MAX,
            'nvdPageSize': NVD_PAGE,
            'targetDay': day.isoformat(),
            'backfill': backfill,
        },
    }

    written = None
    if not args.dry_run:
        out = args.out
        d = os.path.dirname(os.path.abspath(out))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write('\n')
        written = out

    # ---- 4 行数据源健康摘要（--dry-run 的验收就数这 4 行）----
    print('[1/4] CISA KEV      ok=%-5s count=%-6s kevNew=%d kevRecent7d=%d%s'
          % (str(kev_err is None), (len(vulns) if vulns is not None else '-'),
             len(kev_new), len(kev_recent),
             ('  error="%s"' % kev_err) if kev_err else ''))
    print('[2/4] NVD CVE 2.0   ok=%-5s count=%-6s window=%s → %s（1 页 / cvssV3Severity=HIGH）%s'
          % (str(nvd_err is None), (len(nvd) if nvd is not None else '-'),
             start_s, end_s, ('  error="%s"' % nvd_err) if nvd_err else ''))
    print('[3/4] 产出          %s  nvdHigh=%d  limits.note=见产物'
          % ('dry-run，未写文件' if args.dry_run else written, len(nvd_high)))
    print('[4/4] 数据时刻      generatedAt=%s  targetDay=%s%s'
          % (generated_at, day.isoformat(), '（补跑）' if backfill else '（UTC 当天）'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
