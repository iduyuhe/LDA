#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CI core 分批回归（Windows 本机防掉电的安全跑法）。

为什么需要它
------------
本机跑 `lda/run_ci_regression.py --tag core`（当前 178 条）是纯串行长任务，
最重的两条（`run_benchmark_falsifiability_smoke` / `run_redteam_anchor_fuzz_smoke`）
在 10 线程下各自就要 18~22 分钟。全程单进程满载连续跑有 **Kernel-Power Event 41
硬断电** 病史（见 `lda/lda_solver/threads.py` 头部取证）。本脚本把全量切成若干批，
批间强制冷却，把连续满载段切短。

线程数策略（重要）
------------------
默认**不设**线程 env ⇒ 子进程由 `run_ci_regression._child_env()` 走
`lda_solver.threads.thread_env_overrides()` 以 `setdefault` 注入
`budget_threads() = min(DEFAULT_CAP=10, cpu//2)` = 项目文档化的治标上限。

🔴 若用 `--threads N` 显式改线程数，**内置超时覆盖的标定就失效了**：那些预算是按
10 线程实测耗时配的（见 `run_ci_regression._BUILTIN_TIMEOUT_OVERRIDE`）。改小线程
⇒ 变慢 ⇒ 可能假红 TIMEOUT。此时必须自己按新线程数实测后用 `--timeout-extra` 或
直接改内置表重新标定，**不要**把 TIMEOUT 当 FAIL 去改物理判据。

用法
----
    python scripts/ci_core_batched.py                     # core · 10 线程 · 18 条/批
    python scripts/ci_core_batched.py --batch 24 --cooldown 20
    python scripts/ci_core_batched.py --tag all --out D:/tmp/ci_all.json

结果
----
`--out`（默认 `_ci_core_batched_report.json`）。`summary.fail == 0` 即全绿；
`failed` 列出 FAIL/CRASH/TIMEOUT/ERROR 项（四者同属失败态，宁可红也不假绿）。

CRASH 语义
----------
子进程「非零 rc **且零输出**」= 被外部硬杀（OOM / 掉电 / 热保护），**不是断言失败**，
应单独重跑该 smoke 复验，不要去改物理判据。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_LDA = os.path.join(_ROOT, "lda")
sys.path.insert(0, _LDA)

from run_ci_regression import (          # noqa: E402
    CORE_SMOKES,
    _BUILTIN_TIMEOUT_OVERRIDE,
    run_ci_regression,
)


def _existing(names):
    return [s for s in names if os.path.exists(os.path.join(_LDA, s))]


def main() -> int:
    ap = argparse.ArgumentParser(description="CI 分批回归（防掉电）")
    ap.add_argument("--tag", choices=["core", "all"], default="core")
    ap.add_argument("--batch", type=int, default=18, help="每批条数（默认 18）")
    ap.add_argument("--cooldown", type=float, default=12.0, help="批间冷却秒（默认 12）")
    ap.add_argument("--threads", type=int, default=None,
                    help="显式线程数；不给则用项目默认（DEFAULT_CAP=10）")
    ap.add_argument("--python", default=None, help="解释器；默认当前解释器")
    ap.add_argument("--timeout", type=float, default=300.0, help="全局兜底超时")
    ap.add_argument("--out", default=os.path.join(_ROOT, "_ci_core_batched_report.json"))
    a = ap.parse_args()

    if a.threads:
        # setdefault 语义：父进程显式设了才不会被 _child_env 覆盖
        for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                  "OPENBLAS_NUM_THREADS", "NUMBA_NUM_THREADS"):
            os.environ[k] = str(a.threads)
        os.environ["LDA_FDTD_THREADS"] = str(a.threads)
        print(f"[warn] 显式 {a.threads} 线程：内置超时预算按 10 线程标定，"
              f"变慢可能假红 TIMEOUT，须按实测重新标定后再判读。")
    for k, v in (("OMP_DYNAMIC", "FALSE"), ("MKL_DYNAMIC", "FALSE")):
        os.environ.setdefault(k, v)

    all_scripts = _existing(CORE_SMOKES) if a.tag == "core" else None
    if all_scripts is None:                     # tag=all：交给 run_ci_regression 发现
        all_scripts = _existing(_discover_names())

    n = len(all_scripts)
    batches = [all_scripts[i:i + a.batch] for i in range(0, n, max(1, a.batch))]
    t0 = time.time()
    print(f"[batched] tag={a.tag} 脚本 {n} 条 → {len(batches)} 批"
          f"（每批 {a.batch} · 冷却 {a.cooldown}s）"
          f" · 线程 {'显式 %d' % a.threads if a.threads else '项目默认(10)'}")
    print(f"[batched] 内置超时覆盖 {len(_BUILTIN_TIMEOUT_OVERRIDE)} 项；"
          f"falsifiability={_BUILTIN_TIMEOUT_OVERRIDE.get('run_benchmark_falsifiability_smoke.py')}s "
          f"fuzz={_BUILTIN_TIMEOUT_OVERRIDE.get('run_redteam_anchor_fuzz_smoke.py')}s")

    results, per_batch = [], []
    for bi, b in enumerate(batches, 1):
        keep = set(b)
        others = [s for s in all_scripts if s not in keep]
        tb = time.time()
        print(f"\n===== 批次 {bi}/{len(batches)}：{len(b)} 条 =====", flush=True)
        r = run_ci_regression(python=a.python, tag=a.tag, timeout=a.timeout,
                              exclude=others)
        dt = time.time() - tb
        results.extend(r["results"])
        s = r["summary"]
        per_batch.append({"batch": bi, "n": len(b), "pass": s["pass"],
                          "skip": s["skip"], "fail": s["fail"],
                          "seconds": round(dt, 1)})
        if bi < len(batches):
            print(f"----- 批次 {bi} 完成：{s['pass']}P/{s['skip']}S/{s['fail']}F"
                  f" {dt:.0f}s；冷却 {a.cooldown}s -----", flush=True)
            time.sleep(a.cooldown)

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_skip = sum(1 for r in results if r["status"] == "SKIP")
    failed = [r for r in results if r["status"] in ("FAIL", "ERROR", "TIMEOUT", "CRASH")]
    skipped = [r for r in results if r["status"] == "SKIP"]
    tally = {"PASS": n_pass, "SKIP": n_skip}
    for r in failed:
        tally[r["status"]] = tally.get(r["status"], 0) + 1

    out = {
        "title": f"CI 分批回归（tag={a.tag}）",
        "tag": a.tag, "n_scripts": n,
        "batch_size": a.batch, "cooldown_s": a.cooldown,
        "threads": a.threads or "project-default(10)",
        "summary": {"pass": n_pass, "skip": n_skip, "fail": len(failed),
                    "total_s": round(time.time() - t0, 1),
                    "by_status": tally,
                    "failed": [{k: r[k] for k in
                                ("script", "status", "rc", "elapsed_s")}
                               for r in failed],
                    "skipped": [r["script"] for r in skipped]},
        "per_batch": per_batch,
        "results": results,
        "verdict": (f"CI 分批回归 {a.tag}：{n_pass} PASS / {n_skip} SKIP / "
                    f"{len(failed)} FAIL（{n} 条 · {len(batches)} 批）"
                    + (" —— 全绿" if not failed else
                       " —— 失败项：" + "; ".join(r["script"] for r in failed[:5]))),
    }
    try:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n[written] {a.out}")
    except OSError as e:                      # 写盘失败不得掩盖判决
        print(f"[warn] 报告写入失败（不影响判决）：{e}", file=sys.stderr)

    print(out["verdict"])
    return 0 if not failed else 1


def _discover_names():
    """tag=all 时复用 run_ci_regression 的发现逻辑（保持单一真源）。"""
    import run_ci_regression as R
    return R._discover_all()


if __name__ == "__main__":
    sys.exit(main())
