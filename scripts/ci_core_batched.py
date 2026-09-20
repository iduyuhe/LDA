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
    # T6.1 刷新超时预算基线（跨轮上界并入 · 只许 10 线程口径）
    python scripts/ci_core_batched.py --write-baseline
    python scripts/ci_core_batched.py --from-report _ci_core_batched_report.json

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


def _budget_margin_audit(results):
    """超时预算余量体检：对 `_BUILTIN_TIMEOUT_OVERRIDE` 覆盖项算 margin=budget/elapsed。

    为什么需要（v0.9.112 立）：本类缺陷已**复发两次** ——
      ① v0.9.111 修了 falsifiability / fuzz 两项假红 TIMEOUT，**但未做全表审计**；
      ② v0.9.112 全量回归再次假红（`run_d_criterion_smoke` 余量仅 1.03×），
         全表审计 14 项才发现 **5 项余量不足**（含 ① 刚配的 1800/2000，
         余量只有 1.61× / 1.46×）。
    根因恒为：**耗时随锚数增长，预算未同步上调**。故让每次全量跑完自动体检，
    把「什么时候该重新标定」变成机器结论，而不是靠人肉回忆（人肉已经漏了两次）。

    判读：margin < 2.0 ⇒ 欠标定，必须重新实测并上调（目标 ≥3×）。
    ⚠️ TIMEOUT / CRASH 项的 elapsed 是**被截断的**（= 当时预算，真实耗时未知且
    ≥ 预算）⇒ 其 margin 不可信，一律强制列入 low_margin（标记 `censored`）。
    """
    rows = []
    for r in results:
        b = _BUILTIN_TIMEOUT_OVERRIDE.get(r["script"])
        if b and r.get("elapsed_s"):
            censored = r["status"] in ("TIMEOUT", "CRASH")
            rows.append({"script": r["script"], "budget": float(b),
                         "elapsed": float(r["elapsed_s"]),
                         "status": r["status"], "censored": censored,
                         "margin": round(float(b) / float(r["elapsed_s"]), 2)})
    rows.sort(key=lambda x: x["margin"])
    return {"n_items": len(rows),
            "min_margin": rows[0]["margin"] if rows else None,
            "low_margin": [x for x in rows
                           if x["margin"] < 2.0 or x["censored"]],
            "rows": rows}


_BASELINE_PATH = os.path.join(_LDA, "timeout_budget_baseline.json")
_BASELINE_SCHEMA = "lda.timeout_budget_baseline/1"


def _write_baseline(results, *, label, threads, dst=_BASELINE_PATH):
    """把本轮实测**并入**既有基线后写回（v0.9.118 · T6.1 的刷新闭环）。

    为什么是「并入」而不是「覆盖」
    ----------------------------
    `elapsed_max_s` 的语义是**跨轮实测上界**（v0.9.116 立规：取历轮 `elapsed` 最大值，
    而非最近一次）。若用单轮覆盖，上界会退化成"最近一次"⇒ 棘轮失去意义（这正是
    v0.9.116 复查出的规则漏洞）。故本轮样本与既有样本**取并集**，上界取并集最大值。

    🔴 线程口径：内置预算按 **10 线程**标定，其它线程数的实测不可比 ⇒ 非 10 线程时
    **拒绝写基线**（否则会污染基线，让 B8/B9 的余量失真）。
    """
    import run_ci_regression as R
    try:
        from lda_harness.benchmarks import BENCHMARK_ORDER
        anchors = len(BENCHMARK_ORDER)
    except Exception as e:                                       # noqa: BLE001
        anchors = -1
        print("[warn] 读 BENCHMARK_ORDER 失败：%s" % e)

    prev, prev_src = {}, []
    try:
        with open(dst, encoding="utf-8") as fh:
            _p = json.load(fh)
        prev = {r["script"]: r for r in (_p.get("rows") or [])}
        prev_src = list(_p.get("source_reports") or [])
    except (OSError, ValueError):
        prev = {}

    censored, fresh = {}, {}
    for r in results:
        s = r.get("script")
        if s not in R._BUILTIN_TIMEOUT_OVERRIDE:
            continue
        if r.get("status") in ("TIMEOUT", "CRASH"):
            censored[s] = censored.get(s, 0) + 1
            continue
        if r.get("elapsed_s"):
            fresh.setdefault(s, set()).add(round(float(r["elapsed_s"]), 2))

    rows = []
    for s, b in R._BUILTIN_TIMEOUT_OVERRIDE.items():
        old = prev.get(s) or {}
        ss = {round(float(x), 2) for x in (old.get("samples_s") or [])}
        if old.get("elapsed_max_s") is not None:
            ss.add(round(float(old["elapsed_max_s"]), 2))
        ss |= fresh.get(s, set())
        if not ss:
            print("[warn] 基线跳过 %s：无实测样本（该轮未覆盖）" % s)
            continue
        mx = max(ss)
        rows.append({
            "script": s,
            "budget_s": float(b),
            "elapsed_max_s": mx,
            "margin_x": round(float(b) / mx, 3),
            "samples_s": sorted(ss),
            "n_rounds": len(ss),
            "censored_events": int(old.get("censored_events", 0))
                               + censored.get(s, 0),
        })
    rows.sort(key=lambda r: r["margin_x"])

    srcs = prev_src + ([label] if label and label not in prev_src else [])
    out = {
        "schema": _BASELINE_SCHEMA,
        "title": "CI core 超时预算基线（@10 线程 · 跨轮实测上界）",
        "threads": 10,
        "aggregation": "cross-round-max-elapsed(excluding-censored)",
        "hard_floor_x": 2.0,
        "target_x": 3.0,
        "ratchet_below_target": int(
            sum(1 for r in rows if r["margin_x"] < 3.0)),
        "anchors_at_measurement": anchors,
        "core_smokes_at_measurement": len(R.CORE_SMOKES),
        "updated_at": time.strftime("%Y-%m-%d"),
        "source_reports": srcs[-40:],
        "rules": ("预算 ≥ 2 × 跨轮实测上界（硬闸）；目标 3×（棘轮：低于 3× 的项数只降不升）；"
                  "锚数或 CI core 成员数变化 ⇒ 基线过期，须重跑全量并 --write-baseline 刷新"),
        "rows": rows,
    }
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("\n[baseline] 已并入并写回 %s（%d 项 · 锚数 %s · CI core %d）"
          % (dst, len(rows), anchors, out["core_smokes_at_measurement"]))
    for r in rows[:3]:
        print("  ⚠️ 最紧：%s %.3f×（budget=%.0f / 上界 %.1f）"
              % (r["script"], r["margin_x"], r["budget_s"], r["elapsed_max_s"]))
    tight = [r["script"] for r in rows if r["margin_x"] < 2.0]
    if tight:
        print("  🔴 欠标定（<2×）：%s —— 须上调 _BUILTIN_TIMEOUT_OVERRIDE 后重跑" % tight)
    return out


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
    ap.add_argument("--write-baseline", action="store_true",
                    help="跑完后把实测【并入】lda/timeout_budget_baseline.json"
                         "（跨轮上界语义 · T6.1 超时预算棘轮的刷新闭环）")
    ap.add_argument("--from-report", default=None,
                    help="从既有报告 JSON 刷新基线（**不重跑**）")
    a = ap.parse_args()

    if a.from_report:
        print("[baseline] 从既有报告刷新：%s" % a.from_report)
        with open(a.from_report, encoding="utf-8") as fh:
            rep = json.load(fh)
        if (a.threads or 0) not in (0, 10):
            print("[refuse] 非 10 线程口径的实测不可比 ⇒ 拒绝写基线")
            return 2
        _write_baseline(rep.get("results") or [], label=os.path.basename(a.from_report),
                        threads=a.threads)
        return 0

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
        # 超时预算余量体检（v0.9.112）：<2× 即欠标定，须重新实测并上调（目标 ≥3×）。
        "budget_audit": _budget_margin_audit(results),
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

    if a.write_baseline:
        if (a.threads or 0) not in (0, 10):
            print("[refuse] 非 10 线程口径的实测不可比 ⇒ 拒绝写基线"
                  "（见 run_ci_regression 文件头的标定纪律）")
        else:
            _write_baseline(results, label=os.path.basename(a.out), threads=a.threads)

    audit = out["budget_audit"]
    if audit["n_items"]:
        print(f"\n[预算余量体检] 覆盖 {audit['n_items']} 项 · 最低 {audit['min_margin']}×"
              f"（{audit['rows'][0]['script']}） · 目标 ≥3×，<2× 视为欠标定")
        for x in audit["low_margin"]:
            why = ("耗时被截断（TIMEOUT/CRASH），真实值 ≥ 预算"
                   if x["censored"] else "余量不足")
            print(f"  ⚠️ {x['script']}: budget={x['budget']:.0f}s "
                  f"实测={x['elapsed']:.1f}s 余量={x['margin']}× —— {why}，"
                  f"须重新实测并上调")
    print(out["verdict"])
    return 0 if not failed else 1


def _discover_names():
    """tag=all 时复用 run_ci_regression 的发现逻辑（保持单一真源）。"""
    import run_ci_regression as R
    return R._discover_all()


if __name__ == "__main__":
    sys.exit(main())
