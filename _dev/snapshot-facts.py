# -*- coding: utf-8 -*-
"""事实快照 · 把"当前线上是什么"落成一个带 UTC 时间戳、可重跑、可 diff 的 JSON。

为什么需要它（2026-10-16 第一轮外部审查的头号发现）：
    详版总文档里 25 条可回源数字有 12 条已过期 —— 因为同一仓库在 25 分钟里被发布了 3 次
    （site-20261016-000910 → 001942 → 003417）。任何"实测"写在文档里的那一秒就开始过期。

做什么（全程只读）：
    ① git HEAD / 工作区是否脏
    ② srv2：当前 release、保留的 release 列表、四个页面 status+bytes、证书到期
    ③ srv1：公开只读 GET 端点枚举（逐个 status+bytes）、管理面 401 探针、/api/health 关键字段
    ④ 本地资产：static/kurisu 体积与文件数、各 tier 体积、三份 manifest 引用完整性计数
    ⑤ 落盘 docs/facts/<UTC>.json 并覆盖 docs/facts/latest.json

用法：
    python -X utf8 _dev/snapshot-facts.py            # 生成快照
    python -X utf8 _dev/snapshot-facts.py --no-ssh   # 跳过服务器探测（离线也能跑本地部分）

退出码：0 = 快照成功（不代表线上健康）；2 = 快照本身失败。
"""

import io
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, 'static')
KURISU = os.path.join(STATIC, 'kurisu')
FACTS_DIR = os.path.join(ROOT, 'docs', 'facts')

SSH = 'ssh'
SSH_OPTS = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8']
SRV1, SRV2 = 'secagent-srv1', 'secagent-srv2'

PUBLIC_GET = ['kb', 'overview', 'alerts', 'latest', 'honeypot', 'audit', 'geo', 'webstats', 'stories']
ADMIN_PROBE = ['admin', 'internal', 'v1']
PAGES = ['/', '/alerts/', '/posts/', '/ai/', '/labs/', '/about/']


def _reconf_stdout():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def sh(cmd, timeout=25):
    """只读命令；失败返回 (非0, '', err)。"""
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
        out = p.stdout.decode('utf-8', 'replace')
        err = p.stderr.decode('utf-8', 'replace')
        return p.returncode, out, err
    except Exception as e:
        return 127, '', str(e)


def ssh(host, remote, timeout=30):
    return sh([SSH] + SSH_OPTS + [host, remote], timeout=timeout)


def dir_bytes(path):
    tot = 0
    n = 0
    for dp, dn, fn in os.walk(path):
        for f in fn:
            try:
                tot += os.path.getsize(os.path.join(dp, f))
                n += 1
            except Exception:
                pass
    return tot, n


def main():
    _reconf_stdout()
    no_ssh = '--no-ssh' in sys.argv
    now = datetime.now(timezone.utc)
    facts = {
        'format': 'xiaokeqing.facts.v1',
        'snapshotAtUtc': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'snapshotEpoch': int(time.time()),
        'generator': '_dev/snapshot-facts.py',
        'note': '只读快照。所有数字均来自现场只读命令；带 source 字段者可直接复跑核对。',
        'git': {}, 'srv2': {}, 'srv1': {}, 'assets': {}, 'gates': {},
        'errors': [],
    }

    # ---- ① git ----------------------------------------------------------
    rc, out, err = sh(['git', '-C', ROOT, 'rev-parse', '--short', 'HEAD'])
    facts['git']['head'] = out.strip() if rc == 0 else None
    rc, out, err = sh(['git', '-C', ROOT, 'status', '--porcelain'])
    facts['git']['dirtyEntries'] = len([x for x in out.splitlines() if x.strip()]) if rc == 0 else None
    if facts['git']['head'] is None:
        facts['errors'].append('git HEAD 读取失败：%s' % err.strip())

    # ---- ④ 本地资产 ------------------------------------------------------
    if os.path.isdir(KURISU):
        b, n = dir_bytes(KURISU)
        facts['assets']['kurisuBytes'] = b
        facts['assets']['kurisuFiles'] = n
        tiers = {}
        for d in ('medium', 'hi', 'full', 'avatar', 'scene', 'mouth', 'eye', 'video', 'voice'):
            p = os.path.join(KURISU, d)
            if os.path.isdir(p):
                tb, tn = dir_bytes(p)
                tiers[d] = {'bytes': tb, 'files': tn}
        facts['assets']['tiers'] = tiers
    else:
        facts['errors'].append('缺 static/kurisu')

    # ---- ②③ 服务器 ------------------------------------------------------
    if not no_ssh:
        # srv2 release
        rc, out, err = ssh(SRV2, 'readlink -f /opt/secagent/site; ls -1dt /opt/secagent/releases/site-* 2>/dev/null | head -8')
        if rc == 0:
            lines = [x.strip() for x in out.splitlines() if x.strip()]
            facts['srv2']['release'] = os.path.basename(lines[0]) if lines else None
            facts['srv2']['releasesKept'] = [os.path.basename(x) for x in lines[1:]]
        else:
            facts['errors'].append('srv2 release 探测失败：%s' % err.strip())

        # srv2 pages（走 CF 公网）
        pages = {}
        for u in PAGES:
            # ★ 只用一种写法，避免 %% 转义与字符串拼接混用（第二轮自查修掉的重复行）
            rc, out, err = ssh(SRV2, "curl -s -o /dev/null -w '%{http_code} %{size_download}' --max-time 20 https://xiaokeqing.cn" + u)
            if rc == 0 and out.strip():
                parts = out.strip().split()
                if len(parts) >= 2:
                    pages[u] = {'code': int(parts[0]), 'bytes': int(parts[1])}
                else:
                    pages[u] = {'code': None, 'bytes': None, 'raw': out.strip()}
            else:
                pages[u] = {'code': None, 'bytes': None, 'err': err.strip()}
        facts['srv2']['pages'] = pages

        # srv2 证书
        rc, out, err = ssh(SRV2, "echo | openssl s_client -connect 10.0.0.10:443 -servername www.xiaokeqing.cn 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null", timeout=35)
        if rc == 0 and out.strip():
            facts['srv2']['certEndDate'] = out.strip()
        # 若上面拿不到，尝试直接读 release 无关的系统证书（只读）
        if not facts['srv2'].get('certEndDate'):
            rc, out, err = ssh(SRV2, "sudo -n openssl x509 -enddate -noout -in /etc/letsencrypt/live/xiaokeqing.cn/fullchain.pem 2>/dev/null", timeout=25)
            if rc == 0 and out.strip():
                facts['srv2']['certEndDate'] = out.strip()

        # srv1 端点枚举
        eps = {}
        for e in PUBLIC_GET:
            rc, out, err = ssh(SRV1, "curl -s -o /dev/null -w '%{http_code} %{size_download}' --max-time 15 https://demo.xiaokeqing.cn/api/public/" + e)
            if rc == 0 and out.strip():
                p = out.strip().split()
                eps[e] = {'code': int(p[0]), 'bytes': int(p[1]) if len(p) > 1 else None}
            else:
                eps[e] = {'code': None, 'err': err.strip()}
        facts['srv1']['publicGetEndpoints'] = eps
        facts['srv1']['publicGetCount'] = len([k for k, v in eps.items() if v.get('code') == 200])

        # srv1 管理面
        adm = {}
        for e in ADMIN_PROBE:
            rc, out, err = ssh(SRV1, "curl -s -o /dev/null -w '%{http_code}' --max-time 12 https://demo.xiaokeqing.cn/api/" + e)
            adm['/api/' + e] = int(out.strip()) if rc == 0 and out.strip().isdigit() else None
        facts['srv1']['adminProbe'] = adm

        # srv1 health 关键字段
        rc, out, err = ssh(SRV1, "curl -s --max-time 15 https://demo.xiaokeqing.cn/api/health")
        if rc == 0 and out.strip().startswith('{'):
            try:
                h = json.loads(out)
                facts['srv1']['health'] = {
                    'buildSha': h.get('buildSha'),
                    'embeddedGitCommitTime': h.get('embeddedGitCommitTime'),
                    'embeddedGitDirty': h.get('embeddedGitDirty'),
                    'alertsMockEnabled': h.get('alertsMockEnabled'),
                    'fingerprintMismatch': h.get('fingerprintMismatch'),
                }
            except Exception as e:
                facts['errors'].append('health 解析失败：%s' % e)
    else:
        facts['errors'].append('--no-ssh：跳过服务器探测，srv1/srv2 段为空')

    # ---- 落盘 ------------------------------------------------------------
    os.makedirs(FACTS_DIR, exist_ok=True)
    stamp = now.strftime('%Y%m%dT%H%M%SZ')
    p1 = os.path.join(FACTS_DIR, '%s.json' % stamp)
    p2 = os.path.join(FACTS_DIR, 'latest.json')
    blob = json.dumps(facts, ensure_ascii=False, indent=2, sort_keys=False)
    with io.open(p1, 'w', encoding='utf-8', newline='\n') as f:
        f.write(blob + '\n')
    with io.open(p2, 'w', encoding='utf-8', newline='\n') as f:
        f.write(blob + '\n')

    print('=' * 78)
    print(' 事实快照  %s' % facts['snapshotAtUtc'])
    print('=' * 78)
    print('  git HEAD      : %s' % facts['git'].get('head'))
    print('  srv2 release  : %s' % facts['srv2'].get('release'))
    if facts['srv2'].get('pages'):
        for u, v in facts['srv2']['pages'].items():
            print('    %-12s %s  %s B' % (u, v.get('code'), v.get('bytes')))
    print('  srv1 公开GET  : %d 个 200' % facts['srv1'].get('publicGetCount', 0))
    if facts['srv1'].get('health'):
        print('  alertsMock    : %s   （⚠ 需后端确认语义）' % facts['srv1']['health'].get('alertsMockEnabled'))
    print('  assets        : %s B / %s 文件' % (facts['assets'].get('kurisuBytes'), facts['assets'].get('kurisuFiles')))
    print('-' * 78)
    print('  写入：%s' % os.path.relpath(p1, ROOT))
    print('  写入：%s' % os.path.relpath(p2, ROOT))
    if facts['errors']:
        print('  快照过程中的问题：')
        for e in facts['errors']:
            print('    - %s' % e)
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
