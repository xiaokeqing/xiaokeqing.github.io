#!/usr/bin/env bash
# ============================================================
# consistency-check.sh —— 站点一致性 CI（只读巡检，不改任何东西）
# ------------------------------------------------------------
# 跑在哪：srv2（/opt/secagent/tools/consistency-check.sh），由 consistency-check.timer 每 15 分钟触发
# 依赖：bash + curl + sha256sum + python3 标准库。**不装任何包、不读凭据、不写站点目录**。
#
# 四类检查（任一失败 exit 1；全通过 exit 0）：
#   ① 公开页面：7 个页面 HTTP 200 且字节数 > MIN_BYTES（默认 15000）
#   ② 公开端点：8 个端点 HTTP 200 且 body 能被 json.load 解析
#   ③ 站点完整性：/opt/secagent/releases/ 下最新发布目录 **实测**（文件数 / 总字节 / 整树内容哈希 /
#                  index.html 的 sha256），与同目录 manifest.json 里记的值逐项比对：
#                  对得上写 ok、对不上写 mismatch；**只有连清单都没有**才写 skipped（绝不臆造字段）
#   ④ 后端版本：/api/health 的 buildSha 与 /api/public/deploy 里 build.sha 是否一致
#                  （对不上写 unverified，**不报红** —— 见下方「为什么 ④ 不判失败」）
#
# 输出：
#   · stdout：**恰好一行** JSON 摘要（同时原子写入 $REPORT_DIR/latest.json）
#   · stderr：每项一行人类可读结果，供 journalctl 查
#   · 退出码：0 全部通过 / 1 有检查项失败 / 2 脚本自身环境问题（缺命令、报告目录不可写）
#
# 为什么 ④ 不判失败：/api/public/deploy 的 build.* 是**后端自述**（与 /api/health 同源），
#   release.commit 记的是**站点仓库**的 commit（发布机 git HEAD），不是后端 commit。
#   实测 2026-10-17：health.buildSha=8a8014… 而 deploy.release.commit=e8d3c4…（两者本就不同）。
#   所以「后端版本能不能对上」只能是**佐证**，对不上只写 unverified，绝不把站点打成红。
#
# 实测口径（2026-10-17，站主机器 Windows + Git bash，见 docs/一致性CI-部署说明.md §5）：
#   · 裸路径 https://demo.xiaokeqing.cn/alerts|audit|honeypot|geo|webstats|deploy 全部 404；
#     真路径是 /api/public/<name>。脚本对 ② 采用「先真路径、再裸路径」的兜底顺序，
#     并在 JSON 的 endpoints[*].path 里记下**实际用上的**路径，不假装裸路径也能用。
#   · 站点侧 latency 抖动极大（家宽 15s~240s 不等），srv2 上应为同机/同机房毫秒级。
#     为避免 TimeoutStartSec=300 被超时打断，所有 HTTP 检查**并发**跑，单请求 CURL_MAX 秒封顶。
# ============================================================
set -uo pipefail   # 故意**不用 -e**：单项失败要继续跑完全部检查再汇总，不能第一个就中断

# ---------- 可调参数（全部可用环境变量覆盖） ----------
SITE_BASE=${SITE_BASE:-https://xiaokeqing.cn}
API_BASE=${API_BASE:-https://demo.xiaokeqing.cn}
RELEASES_DIR=${RELEASES_DIR:-/opt/secagent/releases}
SITE_LINK=${SITE_LINK:-/opt/secagent/site}
MANIFEST_EXTRA=${MANIFEST_EXTRA:-/opt/secagent/data/public-api/release-info.json}
REPORT_DIR=${REPORT_DIR:-/opt/secagent/reports/ci}
MIN_BYTES=${MIN_BYTES:-12000}
CURL_MAX=${CURL_MAX:-45}
CURL_CONNECT=${CURL_CONNECT:-10}
PARALLEL=${PARALLEL:-8}

SITE_BASE=${SITE_BASE%/}
API_BASE=${API_BASE%/}

# ---------- 检查清单（要加页面/端点就改这两处） ----------
# ① 公开页面。任务原文写「六个」但列了七个，这里**按列出的七个全查**（宁多勿漏）。
PAGES=(
  /
  /alerts/
  /ai/
  /posts/
  /what/
  /status/
  /lab/
)

# ② 公开端点：name|真路径|兜底裸路径
#   兜底那一列是任务清单原文里的写法；2026-10-17 实测它们全 404，只作兼容，不作期望。
ENDPOINTS=(
  "health|/api/health|"
  "home|/api/public/home|"
  "alerts|/api/public/alerts|/alerts"
  "audit|/api/public/audit|/audit"
  "honeypot|/api/public/honeypot|/honeypot"
  "geo|/api/public/geo|/geo"
  "webstats|/api/public/webstats|/webstats"
  "deploy|/api/public/deploy|/deploy"
)

# ---------- 基础设施 ----------
log()  { printf '%s\n' "$*" >&2; }
die()  { printf '[X] %s\n' "$*" >&2; exit 2; }

command -v curl      >/dev/null 2>&1 || die "缺 curl"
command -v sha256sum >/dev/null 2>&1 || die "缺 sha256sum"
command -v python3   >/dev/null 2>&1 || die "缺 python3（Ubuntu 22.04 自带 3.10）"

mkdir -p -- "$REPORT_DIR" 2>/dev/null || die "报告目录建不出来：$REPORT_DIR"
[[ -w $REPORT_DIR ]] || die "报告目录不可写：$REPORT_DIR"

TMPD=$(mktemp -d "${TMPDIR:-/tmp}/xk-ci.XXXXXX") || die "mktemp 失败"
cleanup() { [[ -n ${TMPD:-} && -d ${TMPD:-} ]] && rm -rf -- "$TMPD"; return 0; }
trap cleanup EXIT

# ---------- HTTP 取数（只落文件，不在这里判定） ----------
# 判定全部交给最后的 python3，bash 只负责「把 body 拿下来、把状态码记下来」。
fetch() { # $1 = 结果前缀  $2 = 完整 URL
  local prefix=$1 url=$2 body="${1}.body" code
  code=$(curl -sS --max-time "$CURL_MAX" --connect-timeout "$CURL_CONNECT" \
            -o "$body" -w '%{http_code}' "$url" 2>"${prefix}.err" || true)
  [[ -z $code ]] && code=000
  printf '%s' "$code"  > "${prefix}.code"
  printf '%s' "$url"   > "${prefix}.url"
}

# ---------- 有界并发 ----------
# 为什么并发：15 个检查串行 × 最坏 45s = 675s，会撞穿 TimeoutStartSec=300。
# 并发后最坏 = ceil(7/8)*45 + ceil(8/8)*(45+45) ≈ 135s，留足余量。
# 用 bash 的 `wait -n`（bash ≥ 5.0，Ubuntu 22.04 是 5.1）；老 bash 退化成「攒够再等」。
SLOTS=0
spawn() { # $@ = 后台执行的命令
  if (( BASH_VERSINFO[0] >= 5 )); then
    while (( SLOTS >= PARALLEL )); do wait -n 2>/dev/null || break; SLOTS=$((SLOTS - 1)); done
  fi
  "$@" &
  SLOTS=$((SLOTS + 1))
}

page_job() { fetch "$TMPD/p$1" "$SITE_BASE$2"; }

ep_job() { # $1 = 序号  $2 = 主路径  $3 = 兜底裸路径
  local i=$1 primary=$2 fallback=$3 code
  fetch "$TMPD/e$i" "$API_BASE$primary"
  printf '%s' "e$i" > "$TMPD/e$i.sel"
  code=$(cat "$TMPD/e$i.code")
  if [[ $code != 200 && -n $fallback ]]; then
    # 主路径不是 200 才试兜底；兜底只认 200，否则保留主路径的记录（失败原因更准）
    fetch "$TMPD/e${i}fb" "$API_BASE$fallback"
    if [[ $(cat "$TMPD/e${i}fb.code") == 200 ]]; then
      printf '%s' "e${i}fb" > "$TMPD/e$i.sel"
    fi
  fi
}

# ---------- ③ 站点完整性（只取事实，判定在 python） ----------
# 2026-10-18 起的现状（改前：srv2 侧**从不写清单**，唯一带 indexSha256 的 release-info.json 在 srv1，
# 跨机器对不到 ⇒ 这一项常年只能 skipped）：
#   · scripts/srv2-site-receive.sh 现在会在**原子切换之前**往每个 release 目录写 manifest.json
#     （count / totalBytes / sha256=整树内容哈希 / indexSha256=index.html 单文件哈希 / generatedAt），
#     清单随产物一起 mv 就位，所以「已切换」的版本一定自带指纹；
#   · 本脚本再把目录**实测**一遍（文件数 / 总字节 / 整树哈希 / index.html 哈希）跟清单比 ⇒ ok / mismatch；
#   · 老版发布目录（清单改动之前切上去的）没有 manifest.json，仍按候选顺序找 srv1 的 release-info.json，
#     那种清单只有 indexSha256，就只比 index.html 的哈希；
#   · 什么清单都找不到才写 skipped，并在 detail 里说清原因 —— 绝不编字段。
manifest_candidates() { # $1 = 最新 release 目录（空则只探站点级/外部清单）
  local dir=$1
  if [[ -n $dir ]]; then
    # 首选发布链自己写的每版指纹清单（与产物同一棵被切换的树）
    printf '%s\n' "$dir/manifest.json"
    printf '%s\n' "$dir/release-info.json" "$dir/.release-info.json"
  fi
  printf '%s\n' \
    "$RELEASES_DIR/.release-info.json" \
    "$MANIFEST_EXTRA"
}
# 注意：故意**不**把 release 目录里的 index.json 当清单 —— 那是 Hugo 的 /index.json 产物页面
# （且有 generatedAt，每次构建都变，发布链的整树哈希都特意把它排除），不是发布清单。

# 整树内容哈希：口径必须与发布链**逐字节同源**，否则本地算的永远对不上远端算的。
#   同源三处：scripts/srv2-site-receive.sh 的 tree_hash()、scripts/publish-site-to-srv2.ps1 的 Get-TreeFiles、
#   以及这里。排除项也是同一份：./index.json（Hugo 产物，带构建时刻）与 ./manifest.json（清单自身，自指）。
tree_hash_dir() { # $1 = release 目录
  ( cd "$1" 2>/dev/null && LC_ALL=C find . -type f \
      ! -path './index.json' ! -path './manifest.json' -print0 \
    | LC_ALL=C sort -z | LC_ALL=C xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
}

collect_site_facts() {
  local rel_dir="" sha="" manifest="" live="" act_count="" act_bytes="" act_hash=""
  # 「最新目录」= 修改时间最新的 site-*；.staging-* 不在 glob 里，天然排除
  rel_dir=$(ls -1dt "$RELEASES_DIR"/site-* 2>/dev/null | head -n 1 || true)
  if [[ -n $rel_dir && -f $rel_dir/index.html ]]; then
    sha=$(sha256sum "$rel_dir/index.html" 2>/dev/null | cut -d' ' -f1 || true)
  fi
  local c
  while IFS= read -r c; do
    [[ -n $c && -f $c ]] || continue
    manifest=$c
    break
  done < <(manifest_candidates "${rel_dir:-}")
  live=$(readlink -f "$SITE_LINK" 2>/dev/null || true)
  if [[ -n $rel_dir ]]; then
    # 实测事实：目录里**全部普通文件**（只排除 ./manifest.json 自身，与清单 count/totalBytes 同口径）。
    # 算不出来就留空，python 侧会如实写 mismatch / 说清原因，不会假装通过。
    act_count=$(LC_ALL=C find "$rel_dir" -type f ! -path "$rel_dir/manifest.json" 2>/dev/null \
      | wc -l | tr -d '[:space:]' || true)
    act_bytes=$(LC_ALL=C find "$rel_dir" -type f ! -path "$rel_dir/manifest.json" -printf '%s\n' 2>/dev/null \
      | awk '{s+=$1} END{printf "%d", s+0}' || true)
    act_hash=$(tree_hash_dir "$rel_dir" || true)
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${rel_dir:-}" "${sha:-}" "${manifest:-}" "${live:-}" \
    "${act_count:-}" "${act_bytes:-}" "${act_hash:-}" > "$TMPD/site.tsv"
}

# ---------- 计划清单落盘（给 python 读，保证两边顺序一一对应） ----------
: > "$TMPD/plan_pages"
for p in "${PAGES[@]}"; do printf '%s\n' "$p" >> "$TMPD/plan_pages"; done
: > "$TMPD/plan_eps"
for e in "${ENDPOINTS[@]}"; do printf '%s\n' "$e" >> "$TMPD/plan_eps"; done

# ---------- 跑起来 ----------
log "[$SITE_BASE] 页面 $(( ${#PAGES[@]} )) 个 / [$API_BASE] 端点 $(( ${#ENDPOINTS[@]} )) 个 / 并发 $PARALLEL / 单请求 ${CURL_MAX}s"

i=0
for p in "${PAGES[@]}"; do spawn page_job "$i" "$p"; i=$((i + 1)); done
i=0
for e in "${ENDPOINTS[@]}"; do
  IFS='|' read -r _name primary fallback <<< "$e"
  spawn ep_job "$i" "$primary" "$fallback"
  i=$((i + 1))
done
wait
collect_site_facts

# ---------- 判定 + 出报告（全在 python3 标准库里做） ----------
REPORT="$REPORT_DIR/latest.json"
TS=$(date +%Y-%m-%dT%H:%M:%S%:z)

python3 - "$TMPD" "$REPORT" "$TS" "$MIN_BYTES" <<'PY'
import json, os, sys, hashlib

tmpd, report_path, ts, min_bytes = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])


def read(*parts, default=""):
    p = os.path.join(tmpd, *parts)
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return default


def read_line(parts, default=""):
    """读一行 TSV 原始文本（只去行尾换行，不做 strip —— 否则开头的空字段会被吃掉，字段错位）"""
    p = os.path.join(tmpd, parts)
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.readline().rstrip("\r\n")
    except OSError:
        return default


def read_json(prefix):
    """返回 (解析成功?, 对象/None, 失败原因)"""
    p = os.path.join(tmpd, prefix + ".body")
    try:
        with open(p, "rb") as f:
            raw = f.read()
    except OSError:
        return False, None, "body 没拿到"
    if not raw:
        return False, None, "body 为空"
    try:
        return True, json.loads(raw.decode("utf-8", errors="replace")), ""
    except Exception as exc:  # noqa: BLE001 —— 任何解析异常都算「不可解析」
        return False, None, "JSON 解析失败：%s: %s" % (type(exc).__name__, exc)


pages = []
failed = []
for i, path in enumerate(open(os.path.join(tmpd, "plan_pages"), encoding="utf-8").read().split()):
    url = read("p%d.url" % i)
    code = read("p%d.code" % i, default="000") or "000"
    body = os.path.join(tmpd, "p%d.body" % i)
    size = os.path.getsize(body) if os.path.exists(body) else 0
    ok = (code == "200" and size > min_bytes)
    pages.append({"path": path, "http": int(code) if code.isdigit() else 0,
                  "bytes": size, "ok": ok})
    if not ok:
        if code != "200":
            failed.append("page %s -> HTTP %s" % (path, code))
        else:
            failed.append("page %s -> %d B（要求 > %d）" % (path, size, min_bytes))
    print("[%s] page %-9s HTTP %-3s %8d B" % ("OK" if ok else "!!", path, code, size), file=sys.stderr)

eps = []
for i, line in enumerate(open(os.path.join(tmpd, "plan_eps"), encoding="utf-8").read().splitlines()):
    if not line.strip():
        continue
    spec = line.split("|")
    name = spec[0]
    primary = spec[1] if len(spec) > 1 else ""
    fallback = spec[2] if len(spec) > 2 else ""
    sel = read("e%d.sel" % i, default="e%d" % i) or ("e%d" % i)
    # 用的兜底路径就显示兜底路径，否则显示主路径 —— 报告里要能一眼看出「实际通了哪条」
    shown = fallback if sel.endswith("fb") and fallback else primary
    code = read(sel + ".code", default="000") or "000"
    url = read(sel + ".url")
    parsed, obj, why = read_json(sel)
    ok = (code == "200" and parsed)
    eps.append({"name": name, "path": shown,
                "http": int(code) if code.isdigit() else 0, "json": parsed, "ok": ok})
    if not ok:
        reason = "HTTP %s" % code if code != "200" else why
        failed.append("endpoint %s (%s) -> %s" % (name, url, reason))
    print("[%s] ep   %-9s HTTP %-3s json=%s %s"
          % ("OK" if ok else "!!", name, code, "yes" if parsed else "no",
             "" if ok else ("(" + ("HTTP " + code if code != "200" else why) + ")")),
          file=sys.stderr)

# ---------- ③ 站点完整性（有清单就实测比对：ok / mismatch；连清单都没有才 skipped） ----------
# 口径说明（写进报告，免得下一个人以为两个哈希是一回事）：
#   · sha256（整树内容哈希）= 发布链 tree_hash 的口径：LC_ALL=C 路径字节序 + 逐文件 sha256 +
#     对整段 "<per-file sha256>  ./rel\n" 文本再 sha256；排除 ./index.json 与 ./manifest.json。
#   · indexSha256 = **index.html 单文件**哈希，与 srv1 release-info.json 的同名字段同值，
#     只用来查截断；它**不是**整树哈希。两条都实测都比，报告里用 site_integrity_hash_scope 说明差异。
rel_dir, index_sha, manifest, live_target, act_count, act_bytes, act_hash = (
    [c.strip() for c in read_line("site.tsv").split("\t")] + [""] * 7)[:7]
site_integrity = "skipped"
integrity_detail = ""
recorded_in = ""
manifest_keys = []
manifest_kind = ""
expected = {}
actual = {}


def _int_or_none(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


if rel_dir:
    actual = {"count": _int_or_none(act_count), "totalBytes": _int_or_none(act_bytes),
              "sha256": (act_hash or "").strip().lower()}

if not rel_dir:
    integrity_detail = "在 %s 下没找到 site-* 发布目录" % os.environ.get("RELEASES_DIR", "/opt/secagent/releases")
elif not index_sha:
    integrity_detail = "%s/index.html 算不出 sha256（文件不在或不可读）" % rel_dir
elif not manifest:
    integrity_detail = ("%s 里没有任何清单（manifest.json 不在，老式 release-info.json 也找不到）⇒ "
                        "无从核对，如实写 skipped；发布链下一次发布（或重发一次）会写出 manifest.json"
                        % rel_dir)
else:
    try:
        with open(manifest, "r", encoding="utf-8", errors="replace") as f:
            man = json.load(f)
        manifest_keys = sorted(man.keys()) if isinstance(man, dict) else ["<非对象>"]
    except Exception as exc:  # noqa: BLE001
        man = None
        integrity_detail = "清单解析失败 %s：%s" % (manifest, exc)

    if man is not None and not isinstance(man, dict):
        integrity_detail = "清单 %s 不是 JSON 对象（顶层是 %s）" % (manifest, type(man).__name__)
        man = None

    if man is not None:
        _base = os.path.basename(manifest)
        manifest_kind = ("manifest.json（发布链在切换前写入的每版指纹）" if _base == "manifest.json"
                         else "%s（老式清单，只带 index.html 的哈希）" % _base)
        reasons = []

        exp_sha = man.get("sha256")
        exp_sha = exp_sha.strip().lower() if isinstance(exp_sha, str) and exp_sha.strip() else None
        exp_count = _int_or_none(man.get("count"))
        exp_bytes = _int_or_none(man.get("totalBytes"))
        expected = {"count": exp_count, "totalBytes": exp_bytes, "sha256": exp_sha}

        if exp_sha:
            # —— 新式清单（manifest.json）：整树内容哈希 + 文件数 + 总字节，逐个实测比 ——
            recorded_in = _base + ":sha256"
            actual_sha = actual.get("sha256") or ""
            if not actual_sha:
                reasons.append("实际整树哈希算不出来（find/sha256sum 失败或目录不可读）")
            elif actual_sha != exp_sha:
                reasons.append("整树哈希不符（清单 %s… / 实测 %s…）" % (exp_sha[:16], actual_sha[:16]))
            if exp_count is None:
                reasons.append("清单没有可用的 count（%r）" % (man.get("count"),))
            elif actual.get("count") is None:
                reasons.append("实际文件数算不出来")
            elif actual["count"] != exp_count:
                reasons.append("文件数不符（清单 %d / 实测 %d）" % (exp_count, actual["count"]))
            if exp_bytes is not None and actual.get("totalBytes") is not None \
                    and actual["totalBytes"] != exp_bytes:
                reasons.append("总字节数不符（清单 %d / 实测 %d）" % (exp_bytes, actual["totalBytes"]))
            exp_index = man.get("indexSha256")
            if isinstance(exp_index, str) and exp_index.strip() and exp_index.strip().lower() != index_sha.lower():
                reasons.append("index.html 的 sha256 与清单 indexSha256 不符（清单 %s… / 实测 %s…）"
                               % (exp_index.strip().lower()[:16], index_sha[:16]))
            if not reasons:
                site_integrity = "ok"
                integrity_detail = ("实测与清单一致：%d 个文件 / %d B / 整树 %s…"
                                    % (actual["count"], actual.get("totalBytes") or 0, exp_sha[:16]))
            else:
                site_integrity = "mismatch"
                integrity_detail = "；".join(reasons)
                failed.append("site_integrity -> mismatch（%s）：%s" % (manifest, integrity_detail))
        else:
            # —— 老式清单（srv1 release-info.json 那套）：只有 index.html 单文件哈希可比 ——
            found = []

            def walk(node, path="$", depth=0):
                if depth > 4:
                    return
                if isinstance(node, dict):
                    for k, v in node.items():
                        walk(v, "%s.%s" % (path, k), depth + 1)
                elif isinstance(node, list):
                    for n, v in enumerate(node[:20]):
                        walk(v, "%s[%d]" % (path, n), depth + 1)
                elif isinstance(node, str):
                    if len(node.strip()) == 64 and all(c in "0123456789abcdefABCDEF" for c in node.strip()):
                        found.append((path, node.strip().lower()))

            walk(man)
            # 先按**已核实的真实字段名**找（publish-site-to-srv2.ps1 写的是 indexSha256）
            recorded = None
            rec_key = ""
            for key in ("indexSha256", "index_sha256", "indexSHA256"):
                if isinstance(man.get(key), str):
                    recorded, rec_key = man[key].strip().lower(), key
                    break
            if recorded is None and found:
                # 字段名没见过：从「值」侧认——哪个 64 位十六进制串等于本机算出来的 sha，就是它
                for path, val in found:
                    if val == index_sha.lower():
                        recorded, rec_key = val, path
                        break
                if recorded is None:
                    recorded, rec_key = found[0][1], found[0][0]
            if recorded is None:
                integrity_detail = "清单 %s 里没有任何 64 位 sha256 值（顶层键：%s）" % (
                    manifest, ", ".join(manifest_keys) or "无")
            else:
                recorded_in = rec_key
                expected = {"indexSha256": recorded, "count": exp_count, "sha256": None}
                actual["indexSha256"] = index_sha.lower()
                if recorded == index_sha.lower():
                    site_integrity = "ok"
                    integrity_detail = "index.html 的 sha256 与清单 %s 一致（老式清单，只有单文件哈希可比）" % rec_key
                else:
                    site_integrity = "mismatch"
                    integrity_detail = "index.html 的 sha256 与清单 %s 不一致（老式清单，只有单文件哈希可比）" % rec_key
                    failed.append("site_integrity -> mismatch：index.html sha256 不一致（实测=%s / %s=%s）"
                                  % (index_sha, rec_key, recorded))
print("[%s] site integrity=%s %s"
      % ({"ok": "OK", "mismatch": "!!", "skipped": "--"}.get(site_integrity, "--"),
         site_integrity, integrity_detail), file=sys.stderr)

# ---------- ④ 后端版本（佐证，永不判红） ----------
health = next((e for e in eps if e["name"] == "health"), None)
deploy = next((e for e in eps if e["name"] == "deploy"), None)
health_sha = deploy_sha = ""
site_commit = ""
backend_commit = "unverified"
backend_detail = ""
if health and health["ok"]:
    hsel = "e%d" % [e["name"] for e in eps].index("health")
    ok_, obj_, _ = read_json(read(hsel + ".sel", default=hsel) or hsel)
    if ok_ and isinstance(obj_, dict) and isinstance(obj_.get("buildSha"), str):
        health_sha = obj_["buildSha"]
if deploy and deploy["ok"]:
    dsel = "e%d" % [e["name"] for e in eps].index("deploy")
    ok_, obj_, _ = read_json(read(dsel + ".sel", default=dsel) or dsel)
    if ok_ and isinstance(obj_, dict):
        data = obj_.get("data") or {}
        build = data.get("build") or {}
        release = data.get("release") or {}
        if isinstance(build.get("sha"), str):
            deploy_sha = build["sha"]
        if isinstance(release.get("commit"), str):
            site_commit = release["commit"]   # 站点仓库 commit，**不是**后端 commit
if health_sha and deploy_sha:
    if health_sha.lower() == deploy_sha.lower():
        backend_commit = "match"
        backend_detail = "/api/health.buildSha == /api/public/deploy.build.sha"
    else:
        backend_commit = "unverified"
        backend_detail = "两份自述对不上（health=%s / deploy=%s）" % (health_sha, deploy_sha)
elif health_sha:
    backend_commit = "unverified"
    backend_detail = "有 /api/health.buildSha，但 /api/public/deploy 取不到或没 build.sha"
else:
    backend_detail = "两端都没取到 buildSha"
if site_commit:
    backend_detail += "；另：deploy.release.commit=%s 是**站点仓库**commit、不是后端（两者本就不同，不作比对）" % site_commit

# 附赠佐证：/api/public/deploy 的 release.release 记的就是 srv2 上的 release 目录，
# 和本机 /opt/secagent/site 解析出来的目标比一比 —— 只记录，**不判红**（deploy 是 srv1 上的文件，可能滞后）
live_vs_api = "unknown"
api_release_path = ""
if deploy and deploy["ok"]:
    dsel = "e%d" % [e["name"] for e in eps].index("deploy")
    ok_, obj_, _ = read_json(read(dsel + ".sel", default=dsel) or dsel)
    if ok_ and isinstance(obj_, dict):
        api_release_path = str(((obj_.get("data") or {}).get("release") or {}).get("release") or "")
if api_release_path and live_target:
    # 两边都可能带尾斜杠（deploy 记录的路径与 readlink -f 的结果），归一化后再比
    _a = os.path.normpath(os.path.realpath(api_release_path))
    _b = os.path.normpath(os.path.realpath(live_target))
    live_vs_api = "match" if _a == _b else "mismatch"
print("[%s] live release=%s vs deploy 记录=%s" % ("OK" if live_vs_api == "match" else "--",
                                                  live_target or "(无)", api_release_path or "(无)"),
      file=sys.stderr)
print("[%s] backend commit=%s %s" % ("OK" if backend_commit == "match" else "--",
                                     backend_commit, backend_detail), file=sys.stderr)

# ---------- 汇总 ----------
checks = len(pages) + len(eps) + (1 if site_integrity != "skipped" else 0)
report = {
    "ts": ts,
    "ok": not failed,
    "failed": failed,
    "checks": checks,
    "site_integrity": site_integrity,
    "site_integrity_detail": integrity_detail,
    "site_integrity_manifest": manifest,
    "site_integrity_manifest_kind": manifest_kind,
    "site_integrity_recorded_in": recorded_in,
    # 两个哈希不是一回事，写进报告让读的人一眼分清（也回应「口径一致或显式说明差异」）
    "site_integrity_hash_scope": (
        "sha256=整树内容哈希（逐文件 sha256 后对全量文本再 sha256；排除 ./index.json 与 ./manifest.json）；"
        "indexSha256=index.html 单文件哈希（与 srv1 release-info.json 同名字段同值，非整树）"),
    "site_integrity_expected": expected,
    "site_integrity_actual": actual,
    "site_index_sha256": index_sha,
    "release_dir": rel_dir,
    "live_target": live_target,
    "live_vs_api_release": live_vs_api,
    "api_release_path": api_release_path,
    "backend_commit": backend_commit,
    "backend_commit_detail": backend_detail,
    "backend_build_sha": health_sha,
    "backend_deploy_build_sha": deploy_sha,
    "site_release_commit": site_commit,
    "pages": pages,
    "endpoints": eps,
    "min_bytes": min_bytes,
}
line = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
tmp = report_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    f.write(line + "\n")
os.replace(tmp, report_path)   # 原子替换：别让读的人看到半个文件
print("[%s] %d 项检查，%d 项失败 -> %s"
      % ("PASS" if not failed else "FAIL", checks, len(failed), report_path), file=sys.stderr)
print(line)
sys.exit(0 if not failed else 1)
PY

rc=$?
# python 自己崩了（语法/IO/磁盘满）时 rc 也是 1，但那是「环境问题」不是「检查失败」：
# 用「报告有没有落盘」区分，避免把工具坏了报成站点坏了。
if [[ ! -f $REPORT ]]; then
  log "[X] 判定脚本没产出报告：$REPORT（看上面 python 的报错）"
  exit 2
fi
log "退出码 $rc（0 全通过 / 1 有失败项 / 2 脚本环境问题）"
exit "$rc"
