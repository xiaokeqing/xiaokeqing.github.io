#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T13-② 问答质量集 · 采集器（可重跑 / 可断点续跑 / 配额感知）

做什么
    把 `datasets/qa-40.jsonl`（或你换的任何题库）逐条发给**公开问答端点**，
    把**原始响应 JSON 原样落盘**（留证，不是转述 ✗），供 qa_score.py 打分 / 人工复核。

两种传输（同一端点，同一额度池 `public-demo`）
    --transport ssh   （默认）本机 → `ssh secagent-srv1 curl 127.0.0.1:9900/api/public/ask`
                      走服务器本机回环，不经 Cloudflare；请求体走 stdin，无引号地狱 ✓
    --transport http  POST 到 https://demo.xiaokeqing.cn/api/public/ask（经 CF，最贴近访客路径）

限流纪律（公开端点：**每 IP 6 次/分钟、并发 1**；额度池 30 次/日）
    · 默认 `--interval 11`（>10s），串行发送，不并发压测 ✗
    · 命中 429 → 读 `Retry-After` 等待后重试（**不绕过限流**，如实记录）
    · 额度用尽（quota.remaining<=0 或 429 不解）→ 停下并标记 `exhausted`，**不伪造结果** ✗
    · 题库 > 当日额度是常态：脚本天然断点续跑（已采集的 id 默认跳过），明日再跑即可 ✓

用法
    PY=E:\\DeepSeek1\\work\\_amadeus-src\\.venv\\Scripts\\python.exe
    & $PY -X utf8 scripts/eval/qa_run.py --out-dir E:\\DeepSeek1\\work\\_eval-t13\\qa-runs
    & $PY -X utf8 scripts/eval/qa_run.py --dataset scripts/eval/datasets/qa-40.jsonl --max 9 --interval 11
    & $PY -X utf8 scripts/eval/qa_run.py --transport http --force --id qa-live-01   # 单条重跑

产出（<out-dir>/<stamp>/）
    raw/<id>.json      该条的原始响应（或错误对象，含 http 状态/耗时/Retry-After）
    run-<stamp>.json   本次运行的汇总（含 quota 轨迹、逐条状态）
    run-<stamp>.log    进度日志

退出码：0 完成；2 参数/数据集错误；3 传输不可用（**不产出任何得分** ✗）
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = REPO / "scripts" / "eval" / "datasets" / "qa-40.jsonl"
SSH_HOST = "secagent-srv1"
LOCAL_URL = "http://127.0.0.1:9900/api/public/ask"
PUBLIC_URL = "https://demo.xiaokeqing.cn/api/public/ask"


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


def call_ssh(host: str, url: str, body: bytes, timeout: int):
    """ssh → 远端 curl；请求体走 stdin。

    坑：ssh 会把 argv 用空格拼成一条远端命令行，再由远端 shell 拆分 ⇒
        **任何含空格/需要引号的参数都不能用独立 argv 传** ✗
        所以：Content-Type 用 `k:v` 无空格写法；write-out 用 `--opt=value` 单 token 写法。
    """
    argv = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host,
        "curl", "-sS", "-m", str(timeout), "-X", "POST", url,
        "-H", "Content-Type:application/json",
        "--data-binary", "@-",
        # 坑2：srv1 的 curl 7.61.1 **不认** `--write-out=<fmt>` 写法（报 unknown），
        #      `-w <fmt>` 又会被远端 shell 拆成两个词 ⇒ 只能把值贴在短选项后面：`-w<fmt>` ✓
        "-w__HTTP__%{http_code}",
    ]
    proc = subprocess.run(argv, input=body, capture_output=True, timeout=timeout + 30)
    if proc.returncode != 0:
        raise RuntimeError(f"ssh/curl failed rc={proc.returncode}: {proc.stderr.decode('utf-8', 'replace')[:400]}")
    out = proc.stdout.decode("utf-8", "replace")
    if "__HTTP__" not in out:
        raise RuntimeError(f"no http marker in output: {out[:200]!r}")
    payload, _, code = out.rpartition("__HTTP__")
    return int(code.strip() or 0), payload.strip()


def call_http(url: str, body: bytes, timeout: int):
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="QA quality-set collector (public ask endpoint)")
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--out-dir", default=str(Path.cwd() / "eval-out" / "qa-runs"))
    ap.add_argument("--transport", default="ssh", choices=["ssh", "http"])
    ap.add_argument("--ssh-host", default=SSH_HOST)
    ap.add_argument("--url", default="")
    ap.add_argument("--interval", type=float, default=11.0, help="两条间隔秒数（公开端点限 6 次/分钟）")
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--max", type=int, default=0, help="本次最多采集多少条（额度控制用）")
    ap.add_argument("--id", action="append", default=[], help="只跑指定 id（可重复）")
    ap.add_argument("--force", action="store_true", help="忽略已有 raw，重跑")
    args = ap.parse_args(argv)

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

    url = args.url or (PUBLIC_URL if args.transport == "http" else LOCAL_URL)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.out_dir) / stamp
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / f"run-{stamp}.log"
    log_fh = open(log_path, "w", encoding="utf-8")

    def log(msg):
        line = f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        log_fh.write(line + "\n")
        log_fh.flush()

    log(f"transport={args.transport} url={url} items={len(items)} interval={args.interval}s")
    results = []
    done = 0
    exhausted = False
    for item in items:
        rid = item["id"]
        raw_path = raw_dir / f"{rid}.json"
        if raw_path.is_file() and not args.force:
            try:
                prev = json.loads(raw_path.read_text(encoding="utf-8"))
                status = prev.get("transport", {}).get("httpStatus")
                log(f"skip {rid} (already collected, http {status})")
                results.append({"id": rid, "status": "skipped", "http": status})
                continue
            except Exception:  # noqa: BLE001
                pass
        if args.max and done >= args.max:
            log(f"stop: reached --max {args.max}")
            break
        if exhausted:
            log(f"stop: quota exhausted before {rid}")
            break

        body = json.dumps({"question": item["question"]}, ensure_ascii=False).encode("utf-8")
        t0 = time.time()
        try:
            if args.transport == "ssh":
                code, text = call_ssh(args.ssh_host, url, body, args.timeout)
            else:
                code, text = call_http(url, body, args.timeout)
        except Exception as exc:  # noqa: BLE001
            log(f"ERROR {rid}: {exc}")
            raw_path.write_text(
                json.dumps({"id": rid, "error": str(exc), "transport": {"kind": args.transport, "url": url}},
                           ensure_ascii=False, indent=1), encoding="utf-8")
            results.append({"id": rid, "status": "transport_error", "error": str(exc)})
            done += 1
            time.sleep(args.interval)
            continue
        dt = time.time() - t0

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"_unparsed": text[:4000]}
        record = {
            "id": rid,
            "question": item["question"],
            "collectedAt": _dt.datetime.now().isoformat(timespec="seconds"),
            "transport": {"kind": args.transport, "url": url, "httpStatus": code, "wallSeconds": round(dt, 2)},
            "response": payload,
        }
        raw_path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")

        quota = (payload.get("data") or {}).get("quota") if isinstance(payload, dict) else None
        ans_len = len(((payload.get("data") or {}).get("answer") or "")) if isinstance(payload, dict) else 0
        log(f"done {rid} http={code} {dt:.1f}s answerChars={ans_len} "
            f"quota={quota.get('used') if isinstance(quota, dict) else '-'}"
            f"/{quota.get('limit') if isinstance(quota, dict) else '-'}"
            f" remaining={quota.get('remaining') if isinstance(quota, dict) else '-'}")
        results.append({"id": rid, "status": "ok" if code == 200 else f"http_{code}",
                        "http": code, "seconds": round(dt, 2), "answerChars": ans_len,
                        "quota": quota})
        done += 1

        if code == 429:
            log("429 → 公开端点限流/额度耗尽，停止本轮（不绕过 ✗）")
            exhausted = True
        elif isinstance(quota, dict) and isinstance(quota.get("remaining"), int) and quota["remaining"] <= 0:
            log("quota.remaining<=0 → 额度已尽，停止本轮（明日续跑）")
            exhausted = True
        elif done < len(items):
            time.sleep(args.interval)

    summary = {
        "stamp": stamp,
        "transport": args.transport,
        "url": url,
        "dataset": str(dataset),
        "datasetItems": len(items),
        "attempted": done,
        "ok": sum(1 for r in results if r.get("status") == "ok"),
        "skipped": sum(1 for r in results if r.get("status") == "skipped"),
        "exhausted": exhausted,
        "results": results,
    }
    (run_dir / f"run-{stamp}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    log_fh.close()
    print(f"\n=== SUMMARY === ok={summary['ok']} attempted={done} exhausted={exhausted}")
    print(f"raw → {raw_dir}")
    print(f"run → {run_dir / f'run-{stamp}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
