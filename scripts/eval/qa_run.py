#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T13-② 问答质量集 · 采集器（可重跑 / 可断点续跑 / 配额感知）

做什么
    把 `datasets/qa-40.jsonl`（或你换的任何题库）逐条发给问答端点，
    把**原始响应 JSON 原样落盘**（留证，不是转述 ✗），供 qa_score.py 打分 / 人工复核。

三种传输 × 两个池
    --pool public --transport ssh   （默认）本机 → `ssh secagent-srv1 curl 127.0.0.1:9900/api/public/ask`
                                    走服务器本机回环，不经 Cloudflare；请求体走 stdin，无引号地狱 ✓
    --pool public --transport http  POST 到 https://demo.xiaokeqing.cn/api/public/ask（经 CF，最贴近访客路径）
    --pool self   --transport ssh   POST 到 `http://127.0.0.1:9900/api/user/ask`，带 `X-User-Token`
                                    ★令牌**只在 srv1 上**读取与使用：本脚本不上传、不打印、不落盘任何令牌；
                                      它只是调用 srv1 上的包装脚本 `/tmp/xk-self-ask.sh`（首次自动装，700）
    --pool self   --transport http  **不支持**（会把令牌带出服务器 ⇒ 明确拒绝，见下）
    --pool X      --transport local **在 srv1 上跑时用**：不经 ssh、不经 CF，直接 POST
                                    `http://127.0.0.1:9900/…`；self 池时令牌从 `--self-token-file`
                                    （默认 `/root/xk-self-token.txt`）**在本进程内读取**，
                                    因此令牌依旧**不离开脚本所在主机**（在 srv1 上跑 = 不出服务器）。
                                    为什么要这个模式：站主电脑会关机/断网，而评测要跨零点跑 ⇒
                                    脚本必须能在 srv1 上脱离会话独立跑（`setsid nohup python3 … &`）。

为什么要有 self 池
    公开池 `public-daily-limit=30`（每 IP 6 次/分钟）⇒ 想跑满「≥96 轮/臂」要 7~13 天。
    自用池 `self-daily-soft-limit=500` 是**软上限（只提醒不硬停）**，且登录面是**独立限流桶**
    （`app.ratelimit.login-per-minute=10`，与 `/api/user/status` 共用）⇒ 10 次/分钟下
    120 轮约 12 分钟可采完，且**不需要改任何线上额度**。

限流纪律
    · 串行发送，不并发压测 ✗；默认 `--interval 11`（公开池 6 次/分钟）；自用池建议 `--interval 8`（登录面 10 次/分钟）
    · 命中 429 → 读 `Retry-After`（优先**响应头**，其次**响应体** `retryAfter`，都取不到用 `--retry-default`）
      等待后有限次重试（`--retry429`），**不绕过限流**，如实记录等待来源
    · 公开池额度用尽（`quota.remaining<=0`）→ 停下并标记 `exhausted`，**不伪造结果** ✗
    · 自用池是**软**上限：`remaining<=0` **不停手**（只提醒），仅 429 真拦时才退避/停

重复轮次（`--repeat N`）
    `N=1`（默认）保持**历史目录形状**：`<out-dir>/<stamp>/raw/<id>.json`（老调用方零变化 ✓）
    `N>1`：每轮一个独立目录 `<out-dir>/<stamp>/r<K>/raw/<id>.json`
          —— 这样**未改动的 `qa_score.py`**（它按 `raw/<id>.json` 一对一读取）可以逐轮计分，
          再由调用方汇总（不覆盖、不改打分器）。

多轮（`--conversation` / `--turns`）
    · self 池支持 `conversationId`（最多 5 轮 / 30 分钟；公开面**没有**多轮）
    · `--conversation per-item`：同一题的所有请求共用一个 `conversationId`（保持上下文，可当"真会话"用）
    · `--turns M`：若题库条目的 `followups[]` 非空，第一问之后再问 M-1 条追问（题库没有 followups 时退化为单轮并如实记录）

用法
    PY=E:\\DeepSeek1\\work\\_amadeus-src\\.venv\\Scripts\\python.exe
    & $PY -X utf8 scripts/eval/qa_run.py --out-dir E:\\DeepSeek1\\work\\_eval-t13\\qa-runs
    & $PY -X utf8 scripts/eval/qa_run.py --pool self --transport ssh --interval 8 --repeat 3 --conversation per-item `
        --out-dir E:\\DeepSeek1\\work\\_ab-run\\self-qa\\runs
    & $PY -X utf8 scripts/eval/qa_run.py --transport http --force --id qa-live-01   # 单条重跑

产出（<out-dir>/<stamp>/ ；--repeat>1 时在 r<K>/ 下）
    raw/<id>.json      该条的原始响应（或错误对象，含 http 状态/耗时/Retry-After）
    run-<stamp>.json   本次运行的汇总（含 quota 轨迹、逐条状态、池、多轮）
    run-<stamp>.log    进度日志

退出码：0 完成；2 参数/数据集错误；3 传输不可用（**不产出任何得分** ✗）
"""

import argparse
import base64
import datetime as _dt
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ★兼容性：本文件要能在 **srv1 的 Python 3.6.8** 上直接跑（站主电脑 00:00 关机，
#   阶段二采集必须在 srv1 上脱离会话执行）。因此**不用** 3.7+ 才有的写法：
#   · 不写 `from __future__ import annotations`（3.7+）
#   · 不用 `subprocess.run(capture_output=...)`（3.7+）⇒ 显式写 stdout=PIPE / stderr=PIPE
#   · 不用 `list[str]` / `X | Y` 之类注解
#   · 中文输出靠环境变量 `PYTHONIOENCODING=utf-8`（`python3 -X utf8` 也是 3.7+ 才有）

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = REPO / "scripts" / "eval" / "datasets" / "qa-40.jsonl"
SSH_HOST = "secagent-srv1"
LOCAL_URL = "http://127.0.0.1:9900/api/public/ask"
PUBLIC_URL = "https://demo.xiaokeqing.cn/api/public/ask"
LOCAL_SELF_URL = "http://127.0.0.1:9900/api/user/ask"
HELPER_PATH = "/tmp/xk-self-ask.sh"

# 令牌只在 srv1 上被读取：Windows 侧只看到这个包装脚本的路径。
# 为什么这样做：令牌明文一旦出现在 Windows 的命令行/日志里就可能被复制到别处；
# 这里让它**永不离开 srv1**（脚本内部 `tail -1` 读取）。脚本 700，仅 root 可读。
HELPER_SRC = """#!/bin/bash
# 自用池提问包装器（由 scripts/eval/qa_run.py 自动安装；只在本机读令牌，绝不打印）
# 用法：xk-self-ask.sh <timeout秒> <url>   ；请求体走 stdin
T="$(tail -1 /root/xk-self-token.txt 2>/dev/null)"
if [ -z "$T" ]; then echo "__NO_TOKEN__"; exit 9; fi
exec curl -sS -D - -m "$1" -X POST "$2" \\
  -H "Content-Type: application/json" \\
  -H "X-User-Token: $T" \\
  --data-binary @- \\
  -w "__HTTP__%{http_code}"
"""


def load_dataset(path: Path):
    items = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        try:
            items.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[FATAL] dataset line {lineno} is not JSON: {exc}")
    if not items:
        raise SystemExit(f"[FATAL] dataset empty: {path}")
    for it in items:
        if "id" not in it or "question" not in it:
            raise SystemExit(f"[FATAL] item missing id/question: {it!r}")
    return items


def _split_headers(out: str):
    """`curl -D -` 的输出 = 响应头 + 空行 + 响应体 + `__HTTP__<code>`。

    ★返回 **(code, headers, body)** —— 三个 `call_*` 一律按这个顺序返回，调用处统一解包。
    （踩过：这里曾返回 (headers, body, code)，而调用处按 (code, headers, text) 解包 ⇒
      `json.loads()` 收到 int 直接 TypeError。所以顺序必须在**一处**定义并被断言。）
    找不到 HTTP 标记时抛错（与旧实现同口径：宁可失败也不产出可疑记录）。
    """
    if "__HTTP__" not in out:
        raise RuntimeError(f"no http marker in output: {out[:200]!r}")
    payload, _, code = out.rpartition("__HTTP__")
    head, body = "", payload
    for sep in ("\r\n\r\n", "\n\n"):
        idx = payload.find(sep)
        if idx >= 0:
            head, body = payload[:idx], payload[idx + len(sep):]
            break
    headers = {}
    for line in head.replace("\r\n", "\n").split("\n")[1:]:  # 跳过状态行
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
    return int(code.strip() or 0), headers, body.strip()


def install_helper(host: str) -> None:
    b64 = base64.b64encode(HELPER_SRC.encode("utf-8")).decode("ascii")
    cmd = (f"echo {b64} | base64 -d > {HELPER_PATH} && chmod 700 {HELPER_PATH} "
           f"&& test -s {HELPER_PATH} && echo OK")
    proc = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host, cmd],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if proc.returncode != 0 or b"OK" not in proc.stdout:
        raise RuntimeError(f"install helper failed rc={proc.returncode}: "
                           f"{proc.stderr.decode('utf-8', 'replace')[:300]}")


def call_ssh(host: str, url: str, body: bytes, timeout: int):
    """ssh → 远端 curl（公开池）；请求体走 stdin。

    坑：ssh 会把 argv 用空格拼成一条远端命令行，再由远端 shell 拆分 ⇒
        **任何含空格/需要引号的参数都不能用独立 argv 传** ✗
        所以：Content-Type 用 `k:v` 无空格写法；write-out 用 `--opt=value` 单 token 写法。
        坑2：srv1 的 curl 7.61.1 **不认** `--write-out=<fmt>` 写法（报 unknown），
             `-w <fmt>` 又会被远端 shell 拆成两个词 ⇒ 只能把值贴在短选项后面：`-w<fmt>` ✓
    返回 (httpStatus, headers, bodyText)。
    """
    argv = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host,
        "curl", "-sS", "-D", "-", "-m", str(timeout), "-X", "POST", url,
        "-H", "Content-Type:application/json",
        "--data-binary", "@-",
        "-w__HTTP__%{http_code}",
    ]
    proc = subprocess.run(argv, input=body, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 30)
    if proc.returncode != 0:
        raise RuntimeError(f"ssh/curl failed rc={proc.returncode}: {proc.stderr.decode('utf-8', 'replace')[:400]}")
    code, headers, text = _split_headers(proc.stdout.decode("utf-8", "replace"))
    if code == 0:
        # curl 连不上/被拒时 `%{http_code}` 是 000 ⇒ 必须显式当传输错误，
        # 否则会被记成 "http_0" 的"成功跑过"，掩盖真实故障。
        raise RuntimeError(f"curl 未拿到 HTTP 状态（连接失败？）输出片段: {text[:200]!r}")
    return code, headers, text


def call_ssh_self(host: str, url: str, body: bytes, timeout: int):
    """自用池：调用 srv1 上的包装脚本（令牌只在 srv1 读，永不回到 Windows）。"""
    argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host,
            f"bash {HELPER_PATH} {timeout} {url}"]
    proc = subprocess.run(argv, input=body, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 30)
    text = proc.stdout.decode("utf-8", "replace")
    if "__NO_TOKEN__" in text:
        raise RuntimeError("self token file missing/empty on srv1 (/root/xk-self-token.txt)")
    if proc.returncode != 0 and "__HTTP__" not in text:
        raise RuntimeError(f"ssh/helper failed rc={proc.returncode}: "
                           f"{proc.stderr.decode('utf-8', 'replace')[:400]}")
    code, headers, body_text = _split_headers(text)
    if code == 0:
        raise RuntimeError(f"自用池未拿到 HTTP 状态（连接失败？）输出片段: {body_text[:200]!r}")
    return code, headers, body_text


def call_local(url: str, token: str, body: bytes, timeout: int):
    """在本机（通常就是 srv1）直连端点：不经 ssh、不经 CF。

    self 池时 token 由调用方从 `--self-token-file` 读出并传入 ⇒ 令牌**不离开本进程所在主机**。
    """
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-User-Token"] = token
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, exc.read().decode("utf-8", "replace")


def read_token_file(path: str) -> str:
    """读取令牌文件的**最后一行非空内容**（与 srv1 侧包装脚本 `tail -1` 同口径）。

    绝不打印/不落盘：本函数只把值交给 HTTP 头。
    """
    p = Path(path)
    if not p.is_file():
        return ""
    lines = [ln.strip() for ln in p.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def call_http(url: str, body: bytes, timeout: int):
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, exc.read().decode("utf-8", "replace")


def retry_wait_seconds(headers: dict, payload, default: int):
    """429 等待秒数：优先响应头 Retry-After → 响应体 retryAfter → 默认值。

    为什么两处都读：跨域下浏览器读响应头需要 Access-Control-Expose-Headers（后端已补），
    非浏览器客户端（本脚本）本来就能读头；两处都给才不会有"永远 60 秒"的退化。
    """
    raw = (headers or {}).get("retry-after")
    if raw:
        try:
            return max(1, int(str(raw).strip())), "header"
        except ValueError:
            pass
    if isinstance(payload, dict):
        for key in ("retryAfter",):
            v = payload.get(key)
            if isinstance(v, int) and v > 0:
                return v, "body"
        data = payload.get("data")
        if isinstance(data, dict) and isinstance(data.get("retryAfter"), int) and data["retryAfter"] > 0:
            return data["retryAfter"], "body.data"
    return max(1, int(default)), "default"


def has_token_leak(record) -> bool:
    """自检：原始响应里**不许**出现 64 位十六进制串（令牌形状）。"""
    blob = json.dumps(record, ensure_ascii=False)
    if "xk-self-token" in blob or "X-User-Token" in blob:
        return True
    return bool(re.search(r"\b[0-9a-f]{64}\b", blob))


def prev_record_is_good(prev) -> bool:
    """判断"已有的 raw 记录"是不是**有效答卷**（决定续跑时跳过还是重采）。

    为什么单独抽出来：这条判断决定"断点续跑"是不是真的有用 —— 只按"文件存在"跳过，
    会把上一次因后端切容器/网络抖动而失败的记录**永久固化**。抽出来才能离线单测（不烧额度）。
    有效 = 无 error 字段 + httpStatus==200 + data.answer 非空。
    """
    if not isinstance(prev, dict) or prev.get("error"):
        return False
    status = (prev.get("transport") or {}).get("httpStatus")
    resp = prev.get("response")
    data = (resp or {}).get("data") if isinstance(resp, dict) and isinstance((resp or {}).get("data"), dict) else {}
    return status == 200 and bool(data.get("answer"))


def run_once(args, items, run_dir: Path, log, pool_tag: str):
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    results, done, exhausted = [], 0, False
    for item in items:
        rid = item["id"]
        raw_path = raw_dir / f"{rid}.json"
        if raw_path.is_file() and not args.force:
            try:
                prev = json.loads(raw_path.read_text(encoding="utf-8"))
                if prev_record_is_good(prev):
                    log(f"skip {rid} (已有有效答卷, http 200)")
                    results.append({"id": rid, "status": "skipped", "http": 200})
                    continue
                # ★上次是失败/传输错误（例如后端切容器的 30~90s 窗口）⇒ **必须重采**。
                #   踩过：只按"文件存在"跳过，会把失败永久固化，续跑等于没续跑。
                log(f"retry {rid} (上次无效: http={(prev.get('transport') or {}).get('httpStatus')} "
                    f"err={prev.get('error')!r})")
            except Exception:  # noqa: BLE001
                pass
        if args.max and done >= args.max:
            log(f"stop: reached --max {args.max}")
            break
        if exhausted:
            log(f"stop: quota exhausted before {rid}")
            break

        # 多轮：同一题的所有轮次共用一个 conversationId（self 池才支持）
        # ★故意**不带轮次前缀**：带上就变成"每轮一个新会话 ⇒ round 恒为 1"，多轮永远走不到。
        #   代价要说清：这样一来，`--repeat 3 --conversation per-item` 的 3 条是**同一会话的 3 轮**，
        #   统计上**不独立**（要独立样本就配 `--conversation none`，那是 3 个新会话）。
        conv = ""
        if args.pool == "self" and args.conversation == "per-item":
            conv = f"xk-eval-{rid}"
        questions = [item["question"]]
        if args.turns > 1 and isinstance(item.get("followups"), list):
            questions += [q for q in item["followups"][: args.turns - 1] if isinstance(q, str) and q.strip()]
        if args.turns > 1 and len(questions) < args.turns:
            log(f"note {rid}: dataset 无 followups ⇒ 实际 {len(questions)} 轮（如实记录，不补题）")

        for turn_no, question in enumerate(questions, 1):
            payload_obj = {"question": question}
            if conv:
                payload_obj["conversationId"] = conv
            body = json.dumps(payload_obj, ensure_ascii=False).encode("utf-8")
            attempt, code, text, headers, payload, dt = 0, 0, "", {}, {}, 0.0
            attempts_log = []
            while True:
                attempt += 1
                t0 = time.time()
                try:
                    if args.transport == "local":
                        code, headers, text = call_local(args.url,
                                                         getattr(args, "self_token", "") if args.pool == "self" else "",
                                                         body, args.timeout)
                    elif args.pool == "self":
                        code, headers, text = call_ssh_self(args.ssh_host, args.url, body, args.timeout)
                    elif args.transport == "ssh":
                        code, headers, text = call_ssh(args.ssh_host, args.url, body, args.timeout)
                    else:
                        code, headers, text = call_http(args.url, body, args.timeout)
                except Exception as exc:  # noqa: BLE001
                    log(f"ERROR {rid} turn{turn_no}: {exc}")
                    rec = {"id": rid, "turn": turn_no, "question": question, "error": str(exc),
                           "transport": {"kind": args.transport, "pool": args.pool, "url": args.url}}
                    suffix = "" if len(questions) == 1 else f".t{turn_no}"
                    (raw_dir / f"{rid}{suffix}.json").write_text(
                        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
                    results.append({"id": rid, "turn": turn_no, "status": "transport_error", "error": str(exc)})
                    break
                dt = time.time() - t0
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    payload = {"_unparsed": text[:4000]}
                wait_s, src = retry_wait_seconds(headers, payload, args.retry_default)
                # ★把每一次尝试都留证：429 到底是"头没有/体没有"，只能靠这里说清楚
                attempts_log.append({
                    "attempt": attempt,
                    "httpStatus": code,
                    "wallSeconds": round(dt, 2),
                    "retryAfterHeader": headers.get("retry-after"),
                    "retryAfterBody": (payload.get("retryAfter") if isinstance(payload, dict) else None),
                    "rateLimitReason": (payload.get("reason") if isinstance(payload, dict) else None)
                                       or ((payload.get("data") or {}).get("reason")
                                           if isinstance(payload.get("data"), dict) else None),
                    "bodySnippet": None if code == 200 else (
                        json.dumps(payload, ensure_ascii=False)[:300] if isinstance(payload, dict) else str(payload)[:300]),
                    "waitSeconds": wait_s if code == 429 else 0,
                    "waitSource": src if code == 429 else None,
                })
                if code == 429 and attempt <= args.retry429:
                    log(f"429 {rid} turn{turn_no} → 等待 {wait_s}s（来源 {src}）后重试 {attempt}/{args.retry429}")
                    time.sleep(wait_s)
                    continue
                if code == 429:
                    log(f"429 {rid} turn{turn_no} → 重试 {args.retry429} 次仍失败，停止本轮（不绕过 ✗）")
                    exhausted = True
                break

            suffix = "" if len(questions) == 1 else f".t{turn_no}"
            record = {
                "id": rid,
                "turn": turn_no,
                "question": question,
                "collectedAt": _dt.datetime.now().isoformat(timespec="seconds"),
                "pool": args.pool,
                "conversationId": conv or None,
                "transport": {"kind": args.transport, "pool": args.pool, "url": args.url,
                              "httpStatus": code, "wallSeconds": round(dt, 2),
                              "attempts": attempt},
                "attemptLog": attempts_log,
                "rateLimit": {"retryAfterHeader": headers.get("retry-after"),
                              "retryAfterBody": payload.get("retryAfter") if isinstance(payload, dict) else None},
                "response": payload,
            }
            (raw_dir / f"{rid}{suffix}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                                         encoding="utf-8")
            if has_token_leak(record):
                log(f"[SECURITY] {rid} turn{turn_no} 原始记录疑似含令牌形状串 ⇒ 已记录，需人工复核 ✗")

            data = payload.get("data") or {}
            quota = data.get("quota") if isinstance(data, dict) else None
            ans_len = len(data.get("answer") or "") if isinstance(data, dict) else 0
            log(f"done {rid} turn{turn_no}/{len(questions)} http={code} {dt:.1f}s pool={args.pool} "
                f"state={data.get('state') if isinstance(data, dict) else '-'} "
                f"round={data.get('round') if isinstance(data, dict) else '-'} answerChars={ans_len} "
                f"quota={quota.get('used') if isinstance(quota, dict) else '-'}"
                f"/{quota.get('limit') if isinstance(quota, dict) else '-'}"
                f" remain={quota.get('remaining') if isinstance(quota, dict) else '-'}"
                f" soft={quota.get('softLimitReached') if isinstance(quota, dict) else '-'}")
            results.append({"id": rid, "turn": turn_no, "status": "ok" if code == 200 else f"http_{code}",
                            "http": code, "seconds": round(dt, 2), "answerChars": ans_len, "quota": quota})
            done += 1
            if exhausted:
                break

            # 自用池是软上限：remaining<=0 只提醒，不停手（与公开池不同，这里显式区分）
            if args.pool == "public" and isinstance(quota, dict) and isinstance(quota.get("remaining"), int) \
                    and quota["remaining"] <= 0:
                log("quota.remaining<=0 → 公开池额度已尽，停止本轮（明日续跑）")
                exhausted = True
                break
            if isinstance(quota, dict) and quota.get("softLimitReached"):
                log("quota.softLimitReached=true → 自用池软上限（只提醒，不限额，继续）")
            time.sleep(args.interval)
    return results, done, exhausted


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="QA quality-set collector (public / self ask endpoint)")
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--out-dir", default=str(Path.cwd() / "eval-out" / "qa-runs"))
    ap.add_argument("--transport", default="ssh", choices=["ssh", "http", "local"])
    ap.add_argument("--self-token-file", default="/root/xk-self-token.txt",
                    help="仅 --transport local + --pool self 用：本机令牌文件（只读最后一行，绝不打印）")
    ap.add_argument("--pool", default="public", choices=["public", "self"],
                    help="public=公开池（匿名）；self=自用池（X-User-Token，软上限 500/日）")
    ap.add_argument("--ssh-host", default=SSH_HOST)
    ap.add_argument("--url", default="")
    ap.add_argument("--interval", type=float, default=11.0, help="两条间隔秒数（公开 6/分；自用登录面 10/分 ⇒ 建议 8）")
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--max", type=int, default=0, help="本次最多采集多少条（额度控制用）")
    ap.add_argument("--id", action="append", default=[], help="只跑指定 id（可重复）")
    ap.add_argument("--force", action="store_true", help="忽略已有 raw，重跑")
    ap.add_argument("--stamp", default="",
                    help="固定本次运行目录名（断点续跑用：重跑传同一个 stamp 才会跳过已完成条目；"
                         "不传＝按时间戳新建。踩过：靠时间戳目录时重跑会新建目录 ⇒ 什么都跳不过去）")
    ap.add_argument("--repeat", type=int, default=1, help="重复轮次（>1 时每轮独立目录 r<K>/，供逐轮计分）")
    ap.add_argument("--conversation", default="none", choices=["none", "per-item"],
                    help="per-item=同一题共用一个 conversationId（仅 self 池支持多轮）")
    ap.add_argument("--turns", type=int, default=1, help="每题轮数（题库带 followups[] 时才 >1）")
    ap.add_argument("--retry429", type=int, default=2, help="429 时的有限重试次数（默认 2）")
    ap.add_argument("--retry-default", type=int, default=60, help="429 无 Retry-After（头/体）时的默认等待秒数")
    args = ap.parse_args(argv)

    if args.pool == "self" and args.transport == "http":
        print("[FATAL] --pool self 只支持 --transport ssh|local：令牌不允许离开脚本所在主机"
              "（http 会把令牌带到客户端/CF）", file=sys.stderr)
        return 2
    if args.pool == "self" and args.transport == "local":
        tok = read_token_file(args.self_token_file)
        if not tok:
            print(f"[FATAL] 读不到令牌文件 {args.self_token_file}（local+self 需要它，且绝不会被打印）",
                  file=sys.stderr)
            return 2
        # 只挂在 args 上，供 run_once 使用；不写日志、不落盘、不进 report
        args.self_token = tok
        del tok
    if args.repeat < 1:
        print("[FATAL] --repeat 必须 >= 1", file=sys.stderr)
        return 2

    dataset = Path(args.dataset)
    if not dataset.is_file():
        print(f"[FATAL] dataset not found: {dataset}", file=sys.stderr)
        return 2
    items = load_dataset(dataset)
    if args.id:
        wanted = set(args.id)
        items = [i for i in items if i["id"] in wanted]
        if not items:
            print("[FATAL] --id matched nothing", file=sys.stderr)
            return 2

    if args.url:
        url = args.url
    elif args.pool == "self":
        url = LOCAL_SELF_URL
    else:
        url = PUBLIC_URL if args.transport == "http" else LOCAL_URL
    # ★必须回写：run_once 用的是 args.url（单一真相）。踩过：只算局部变量 url，
    # 结果远端 curl 收到空 URL ⇒ HTTP 状态 0、响应为空，而日志看起来"跑过了"。
    args.url = url

    if args.pool == "self" and args.transport == "ssh":
        try:
            install_helper(args.ssh_host)
        except Exception as exc:  # noqa: BLE001
            print(f"[FATAL] 自用池需要 srv1 上的包装脚本，安装失败：{exc}", file=sys.stderr)
            return 3

    # ★`--stamp` 是断点续跑的关键：目录名固定，重跑才会走到 "skip 已完成" 分支。
    stamp = args.stamp or _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base_dir = Path(args.out_dir) / stamp
    existed = base_dir.is_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    log_path = base_dir / f"run-{stamp}.log"
    # 续跑时**追加**日志（不截断上一次的进度记录）
    log_fh = open(log_path, "a" if existed else "w", encoding="utf-8")

    def log(msg):
        line = f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        log_fh.write(line + "\n")
        log_fh.flush()

    log(f"pool={args.pool} transport={args.transport} url={url} items={len(items)} "
        f"repeat={args.repeat} conversation={args.conversation} turns={args.turns} interval={args.interval}s")

    multi = args.repeat > 1
    rounds = []
    for k in range(1, args.repeat + 1):
        run_dir = (base_dir / f"r{k}") if multi else base_dir
        tag = f"r{k}" if multi else "r1"
        if multi:
            log(f"--- repeat {k}/{args.repeat} → {run_dir} ---")
        results, done, exhausted = run_once(args, items, run_dir, log, tag)
        rounds.append({"repeat": k, "runDir": str(run_dir), "attempted": done, "exhausted": exhausted,
                       "ok": sum(1 for r in results if r.get("status") == "ok"), "results": results})

    summary = {
        "stamp": stamp,
        "pool": args.pool,
        "transport": args.transport,
        "url": url,
        "dataset": str(dataset),
        "datasetItems": len(items),
        "repeat": args.repeat,
        "conversation": args.conversation,
        "turns": args.turns,
        "attempted": sum(r["attempted"] for r in rounds),
        "ok": sum(r["ok"] for r in rounds),
        "exhausted": any(r["exhausted"] for r in rounds),
        "rounds": rounds,
    }
    (base_dir / f"run-{stamp}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    log_fh.close()
    print(f"\n=== SUMMARY === pool={args.pool} ok={summary['ok']} attempted={summary['attempted']} "
          f"exhausted={summary['exhausted']} rounds={args.repeat}")
    print(f"raw → {base_dir / ('r1/raw' if multi else 'raw')}")
    print(f"run → {base_dir / f'run-{stamp}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
