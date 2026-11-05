#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""线上自检 —— 一条命令回答"这个站现在还活着、还是坏了"。

用法：
    python site-check.py                     # 默认查 https://xiaokeqing.cn + demo 接口
    python site-check.py --base http://127.0.0.1:18080 --api http://127.0.0.1:9900 --host xiaokeqing.cn
    python site-check.py --only 数据           # 只跑某一组

设计口径（2026-11-05）：
- 只读，不写任何东西；不改数据、不重启服务。
- 每条检查都要给出"期望"与"实测"，失败时打印**为什么**（不打印空结论）。
- 拿不到就写"取不到 + 原因"，绝不补 0、绝不假装通过。
- 退出码：0 = 全过；1 = 有 FAIL；2 = 有 WARN 无 FAIL。
"""
import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
import urllib.parse

OK, FAIL, WARN = 'PASS', 'FAIL', 'WARN'
results = []


def add(group, name, status, detail=''):
    results.append({'group': group, 'name': name, 'status': status, 'detail': detail})


def fetch(url, host=None, timeout=12, want_bytes=False):
    url = urllib.parse.quote(url, safe=':/?&=%#')
    req = urllib.request.Request(url, headers={'User-Agent': 'xk-site-check/1.0'})
    if host:
        req.add_header('Host', host)
    ctx = ssl.create_default_context()
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = r.read()
            ms = int((time.time() - t0) * 1000)
            return {'ok': True, 'status': r.status, 'len': len(body), 'ms': ms,
                    'body': body if want_bytes else None,
                    'headers': dict(r.headers), 'url': url}
    except urllib.error.HTTPError as e:
        body = b''
        try:
            body = e.read()
        except Exception:
            pass
        return {'ok': False, 'status': e.code, 'len': len(body), 'ms': int((time.time() - t0) * 1000),
                'body': body if want_bytes else None, 'headers': dict(e.headers or {}), 'url': url,
                'err': 'HTTP %d' % e.code}
    except Exception as e:
        return {'ok': False, 'status': 0, 'len': 0, 'ms': int((time.time() - t0) * 1000),
                'body': None, 'headers': {}, 'url': url, 'err': '%s: %s' % (type(e).__name__, e)}


def as_json(r):
    """解析 JSON；接口若包了 {code,message,data} 的信封就自动拆成 data。"""
    if not r.get('ok') or not r.get('body'):
        return None
    try:
        j = json.loads(r['body'].decode('utf-8'))
    except Exception:
        return None
    if isinstance(j, dict) and 'data' in j and 'code' in j:
        return j['data']
    return j


def style(r):
    return '%d / %d B / %d ms' % (r['status'], r['len'], r['ms'])


# ---------------------------------------------------------------- 站点（静态）
def check_site(base, host):
    pages = [
        ('/', 3000, '门页（开屏动画）'),
        ('/alerts/', 8000, '攻击实况'),
        ('/daily/', 8000, '安全日报'),
        ('/posts/', 8000, '笔记列表'),
        ('/posts/pki/', 8000, '笔记详情（windows 批）'),
        ('/posts/linux-notes-overview/', 8000, '笔记详情（linux 批）'),
        ('/more/', 3000, '更多（目录页）'),
        ('/room/', 8000, '我的房间'),
        ('/categories/windows系统/', 3000, '分类：windows系统'),
        ('/categories/linux系统/', 3000, '分类：linux系统'),
        ('/categories/网络基础/', 3000, '分类：网络基础'),
        ('/categories/靶机实战/', 3000, '分类：靶机实战'),
        ('/categories/ai笔记/', 3000, '分类：ai笔记'),
        ('/index.json', 800000, '搜索索引（全文）'),
        ('/index-lite.json', 20000, '搜索索引（轻量）'),
    ]
    for path, minlen, label in pages:
        r = fetch(base + path, host=host, want_bytes=(path == '/'))
        if not r['ok']:
            add('站点', '%s %s' % (path, label), FAIL, r.get('err', '取不到'))
            continue
        if r['len'] < minlen:
            add('站点', '%s %s' % (path, label), FAIL,
                '只有 %d B（期望 ≥ %d），可能被截断或构建不完整' % (r['len'], minlen))
            continue
        add('站点', '%s %s' % (path, label), OK, style(r))


def check_site_content(base, host):
    """关键内容必须在（防止"页面 200 但整块没渲染"）。"""
    checks = [
        ('/', 'gateCrt', '门页里有开屏画布'),
        ('/', 'opening.gate', '门页引用了开屏图集'),
        ('/alerts/', 'api/public', '攻击实况接的是公开接口'),
        ('/daily/', 'api/public/daily', '日报页接的是日报接口'),
        ('/more/', 'mr-card', '更多页是卡片目录'),
        ('/posts/pki/', 'loading=lazy', '正文图片是懒加载'),
    ]
    for path, needle, label in checks:
        r = fetch(base + path, host=host, want_bytes=True)
        if not r['ok']:
            add('内容', label, FAIL, r.get('err', '取不到'))
            continue
        text = (r['body'] or b'').decode('utf-8', 'ignore')
        if needle in text:
            add('内容', label, OK, '命中 %r' % needle)
        else:
            add('内容', label, FAIL, '页面里找不到 %r' % needle)


def check_mobile_light(base, host):
    """慢网/快网分档：只验证页面本身的判定脚本在（真正的网速判定要在浏览器里测）。"""
    r = fetch(base + '/alerts/', host=host, want_bytes=True)
    if not r['ok']:
        add('分档', '慢网判定脚本', FAIL, r.get('err', '取不到'))
        return
    text = (r['body'] or b'').decode('utf-8', 'ignore')
    add('分档', 'head 里有 xk-slow 判定', OK if 'xk-slow' in text else FAIL,
        '命中 xk-slow' if 'xk-slow' in text else '页面里没有 xk-slow 判定，慢网不会降档')


# ---------------------------------------------------------------- 接口（只读）
def check_api(api, host, api_host=None):
    host = api_host or host
    r = fetch(api + '/api/health', host=host, want_bytes=True)
    j = as_json(r)
    if not r['ok'] or not isinstance(j, dict):
        add('接口', '健康检查 /api/health', FAIL, r.get('err', '取不到') + ' ' + style(r))
    else:
        st = str(j.get('status', ''))
        fp = j.get('fingerprintMismatch')
        sha = str(j.get('embeddedGitCommit') or j.get('buildSha') or '')[:7]
        add('接口', '健康检查 /api/health', OK if st == 'ok' and fp is False else FAIL,
            'status=%s fingerprintMismatch=%s commit=%s' % (st, fp, sha))

    r = fetch(api + '/api/public/alerts.js', host=host, want_bytes=True)
    j = as_json(r)
    if not isinstance(j, dict):
        add('接口', '告警统计 /api/public/alerts.js', FAIL, r.get('err', '取不到或不是 JSON'))
    else:
        st = j.get('stats24h') if isinstance(j.get('stats24h'), dict) else {}
        total = j.get('alertTotal') or st.get('total') or j.get('total') or j.get('count')
        add('接口', '告警统计 /api/public/alerts.js', OK if total else WARN,
            'total=%s' % (total,))

    r = fetch(api + '/api/public/daily.js', host=host, want_bytes=True)
    j = as_json(r)
    if not isinstance(j, dict):
        add('接口', '今日日报 /api/public/daily.js', FAIL, r.get('err', '取不到或不是 JSON'))
    else:
        avail = j.get('available')
        add('接口', '今日日报 /api/public/daily.js', OK if avail else WARN,
            'available=%s date=%s alertTotal=%s' % (avail, j.get('date'), j.get('alertTotal')))

    r = fetch(api + '/api/public/daily/index.json', host=host, want_bytes=True)
    j = as_json(r)
    if not isinstance(j, dict):
        add('接口', '日报归档 /api/public/daily/index.json', FAIL, r.get('err', '取不到或不是 JSON'))
    else:
        days = j.get('count')
        add('接口', '日报归档 /api/public/daily/index.json', OK if isinstance(days, int) and days >= 1 else FAIL,
            'count=%s（归档至少要有 1 天）' % (days,))

    r = fetch(api + '/api/public/deploy.js', host=host, want_bytes=True)
    j = as_json(r)
    if not isinstance(j, dict):
        add('接口', '发布信息 /api/public/deploy.js', FAIL, r.get('err', '取不到或不是 JSON'))
    else:
        rel = (j.get('release') or {})
        add('接口', '发布信息 /api/public/deploy.js', OK if rel.get('available') else WARN,
            'release=%s files=%s' % (rel.get('path') or rel.get('release'), rel.get('files')))

    # 登录入口必须存在且**未登录时 401**（fail-closed）
    r = fetch(api + '/api/user/status', host=host)
    add('接口', '用户接口未登录必须 401', OK if r['status'] == 401 else FAIL,
        'status=%d（期望 401，fail-closed）' % r['status'])


# ---------------------------------------------------------------- 报告
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='https://xiaokeqing.cn')
    ap.add_argument('--api', default='https://demo.xiaokeqing.cn')
    ap.add_argument('--host', default=None, help='给源站回环测站点时用，例如 xiaokeqing.cn')
    ap.add_argument('--api-host', default=None, help='给源站回环测接口时用，例如 demo.xiaokeqing.cn')
    ap.add_argument('--only', default=None, help='站点 / 内容 / 分档 / 接口')
    ap.add_argument('--json', default=None, help='把结果写到这个 json 文件')
    a = ap.parse_args()

    groups = {
        '站点': lambda: check_site(a.base, a.host),
        '内容': lambda: check_site_content(a.base, a.host),
        '分档': lambda: check_mobile_light(a.base, a.host),
        '接口': lambda: check_api(a.api, a.host, a.api_host),
    }
    for name, fn in groups.items():
        if a.only and a.only != name:
            continue
        try:
            fn()
        except Exception as e:
            add(name, '这一组整体跑挂', FAIL, '%s: %s' % (type(e).__name__, e))

    n_ok = sum(1 for r in results if r['status'] == OK)
    n_fail = sum(1 for r in results if r['status'] == FAIL)
    n_warn = sum(1 for r in results if r['status'] == WARN)
    width = max(len(r['name']) for r in results) if results else 10
    print('线上自检 · base=%s api=%s' % (a.base, a.api))
    cur = None
    for r in results:
        if r['group'] != cur:
            cur = r['group']
            print('\n[%s]' % cur)
        print('  %-4s %-*s  %s' % (r['status'], width, r['name'], r['detail']))
    print('\n合计：通过 %d / 失败 %d / 提醒 %d' % (n_ok, n_fail, n_warn))
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump({'base': a.base, 'api': a.api, 'results': results,
                       'ok': n_ok, 'fail': n_fail, 'warn': n_warn}, f, ensure_ascii=False, indent=1)
    return 1 if n_fail else (2 if n_warn else 0)


if __name__ == '__main__':
    sys.exit(main())
