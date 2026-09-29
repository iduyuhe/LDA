#!/usr/bin/env python
"""非 core 豁免项复测入口 + 台账写入（v0.9.144 · D-147 · 闭合「豁免=永不执行」缺口）。

为什么要有这个脚本
------------------
`NON_CORE_SMOKES`（18 项重仿真豁免）是「唯一合法的不进 core 通道」，且
`run_noncore_reason_smoke.py` 已守护**理由的格式**（须含『实测 Ns』∈[5,330]、
不得写「超时」搪塞、无 ghost、无双登记）。但守护的只是**字符串**：

    🔴 理由里的「实测 47.2s」是 2026-09-06 的快照 —— 没有机制要求它仍然为真，
       也没有机制要求这些 smoke 仍然能跑通。豁免表 ≠ 执行 ⇒ 23 天无人跑过。

本脚本补上「真值」维度：
  · 复刻 CI 子进程口径（`run_ci_regression._child_env`：@10 线程 + PYTHONHASHSEED=0）
    逐项串行复测，写 `lda/noncore_replay_ledger.json`（**受跟踪**，非 .cache scratch）；
  · 台账记 `last_green` / `elapsed_s` / `samples_s` / 复测时 HEAD sha；
  · `run_noncore_reason_smoke.py` 的 ⑪~⑯ 判据读该台账 ⇒ 超期或与理由矛盾即**红**。

🔴 掉电防护（技能 `lda-ci-batched-power-safe`）：逐项串行 + 项间冷却，
   避免满载连续运行触发整机硬断电（Kernel-Power 41）。

用法
----
  python scripts/noncore_replay.py                 # 复测全部 18 项（1 轮）· 写台账
  python scripts/noncore_replay.py --rounds 2      # 2 轮（跨轮上界更稳）
  python scripts/noncore_replay.py --only run_ir_smoke.py
  python scripts/noncore_replay.py --check         # 只读台账（秒级）· 打印时效 + 依赖漂移提示
  python scripts/noncore_replay.py --check --json  # 机器可读

出口：复测模式全绿退 0（有红退 1）；--check 模式台账健康退 0。LLM 不进判决路径。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from typing import Any, Dict, List

# 与 run_noncore_reason_smoke._SEC_RE 同口径（本地定义 ⇒ 不跨 smoke 依赖）
_SEC_RE = re.compile(r"实测\s*(\d+(?:\.\d+)?)s")

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.join(os.path.dirname(_HERE), "lda")
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

import run_ci_regression as R  # noqa: E402

LEDGER = os.path.join(_LDA, "noncore_replay_ledger.json")
SCHEMA = "lda.noncore_replay_ledger/1"
CALIB_THREADS = 10
COOLDOWN_S = 5.0
CAP_S = 400.0                 # 实测上限（高于当前生效 300s，取「真耗时」而非截断值）
DEP_DIRS = ("lda_solver", "lda_l2", "lda_harness", "lda_qeda")   # 依赖面（漂移提示用）


def _today() -> str:
    return date.today().isoformat()


def _head_sha() -> str:
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=os.path.dirname(_LDA),
                           capture_output=True, text=True, timeout=20)
        return (p.stdout or "").strip() if p.returncode == 0 else ""
    except Exception:                                            # noqa: BLE001
        return ""


def _dep_drift(ledger: Dict[str, Any]) -> List[str]:
    """自台账 commit 以来，依赖面改动的文件（git 不可用 ⇒ 返回 []，不阻断）。"""
    sha = (ledger.get("commit") or "").strip()
    if not sha:
        return []
    try:
        p = subprocess.run(["git", "diff", "--name-only", sha + "..HEAD", "--"]
                           + list(DEP_DIRS),
                           cwd=os.path.dirname(_LDA), capture_output=True,
                           text=True, timeout=30)
        if p.returncode != 0:
            return []
        return [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]
    except Exception:                                            # noqa: BLE001
        return []


def _load_ledger() -> Dict[str, Any]:
    try:
        with open(LEDGER, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _age_days(stamp: str) -> float:
    y, m, d = (int(x) for x in stamp.split("-"))
    return (date.today() - date(y, m, d)).days


# ------------------------------------------------------------------ 台账写入（单一真源）
def build_ledger(acc: Dict[str, Dict[str, Any]], rounds: int,
                 ledger_prev: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """把「逐项多轮实测」折成台账（**唯一写入口** ⇒ 格式单一真源）。

    acc: {script: {"statuses": [...], "samples": [...]}}
    规则：`last_green` **只在本次全绿时前移**；红 ⇒ 保留旧值 ⇒ 时效判据自然变红。
    """
    led_prev = ledger_prev or {}
    rows = dict(led_prev.get("rows") or {})
    all_green = True
    for s, e in acc.items():
        if s not in R.NON_CORE_SMOKES:
            continue
        mx = max(e["samples"])
        ok = all(st in ("PASS", "SKIP") for st in e["statuses"])
        all_green = all_green and ok
        old = rows.get(s) or {}
        entry = {
            "status": "PASS" if ok else e["statuses"][-1],
            "last_attempt": _today(),
            "last_attempt_status": e["statuses"][-1],
            "elapsed_s": round(sum(e["samples"]) / len(e["samples"]), 2),
            "elapsed_max_s": mx,
            "samples_s": e["samples"],
            "threads": CALIB_THREADS,
        }
        if ok:
            entry["last_green"] = _today()
        elif old.get("last_green"):
            entry["last_green"] = old["last_green"]
        rows[s] = entry
    return {
        "schema": SCHEMA,
        "threads": CALIB_THREADS,
        "rounds": rounds,
        "updated": _today(),
        "commit": _head_sha(),
        "dep_dirs": list(DEP_DIRS),
        "all_green": all_green,
        "note": ("非 core 豁免项的复测台账（受跟踪）。由 scripts/noncore_replay.py 写入；"
                 "run_noncore_reason_smoke.py 的 ⑪~⑱ 判据读之。"
                 "last_green 只在复测为绿时前移 ⇒ 红了就保留旧值，时效自然变红。"),
        "rows": rows,
    }


def write_ledger(led: Dict[str, Any]) -> None:
    with open(LEDGER, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(led, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


# ------------------------------------------------------------------ --check 模式
def cmd_check(as_json: bool = False) -> int:
    led = _load_ledger()
    rows = led.get("rows") or {}
    want = sorted(R.NON_CORE_SMOKES)
    missing = [s for s in want if s not in rows]
    stale, untruthful = [], []
    for s in want:
        e = rows.get(s) or {}
        lg = e.get("last_green")
        if not lg:
            stale.append((s, "无 last_green"))
        elif _age_days(lg) > 90:
            stale.append((s, "%s（%d 天）" % (lg, _age_days(lg))))
        m = _SEC_RE.search(R.NON_CORE_SMOKES.get(s, ""))
        if m and e.get("elapsed_s"):
            claimed = float(m.group(1))
            actual = float(e["elapsed_s"])
            rel = abs(actual - claimed) / claimed
            if rel > 0.25:
                untruthful.append(
                    (s, f"账面 {actual:.1f}s vs 理由 {claimed:.1f}s"
                        f"（偏差 {rel * 100:.0f}%）"))
    drift = _dep_drift(led)
    nco = dict(getattr(R, "NON_CORE_TIMEOUT_OVERRIDE", {}) or {})
    tight = []
    for s in want:
        mx = (rows.get(s) or {}).get("elapsed_max_s")
        if not mx:
            continue
        b = float(nco.get(s, 300.0))
        if b / float(mx) < 3.0:
            tight.append((s, f"{b:.0f}s/{float(mx):.1f}s = {b / float(mx):.2f}× < 3×"))
    ok = not missing and not stale and not untruthful and not tight
    if as_json:
        print(json.dumps({"ok": ok, "updated": led.get("updated"),
                          "commit": led.get("commit"),
                          "missing": missing, "stale": stale,
                          "untruthful": untruthful, "budget_below_target": tight,
                          "dep_drift_files": len(drift)}, ensure_ascii=False))
        return 0 if ok else 1
    print("=" * 74)
    print("非 core 豁免台账 — 只读体检（%s）" % LEDGER)
    print("=" * 74)
    upd = led.get("updated") or "(无)"
    sha = (led.get("commit") or "(无)")[:12]
    print(f"  台账更新 {upd} · commit {sha} · 条目 {len(rows)}/{len(want)}")
    print("  ① 覆盖完备：%s%s" % ("PASS" if not missing else "FAIL",
                                 "" if not missing else " 缺 " + str(missing)))
    print("  ② 时效（≤90 天）：%s%s" % ("PASS" if not stale else "FAIL",
                                       "" if not stale else " " + str(stale)))
    _t = "PASS" if not untruthful else "FAIL"
    print(f"  ③ 真值一致（±25%）：{_t}{'' if not untruthful else ' ' + str(untruthful)}")
    _b = "PASS" if not tight else "FAIL"
    print(f"  ④ 预算余量（≥3× · 生效预算=专属或全局300s）：{_b}"
          f"{'' if not tight else ' ' + str(tight)}")
    print(f"  ⚠️ 依赖面漂移（提示，不判红）：自台账以来 {len(drift)} 个文件"
          f"（{'、'.join(DEP_DIRS)}）")
    if drift:
        for f in drift[:6]:
            print("       · %s" % f)
        if len(drift) > 6:
            print("       · … 另 %d 个" % (len(drift) - 6))
        print("     ⇒ 建议跑 `python scripts/noncore_replay.py` 复测后刷新台账")
    print("-" * 74)
    print("结论：%s" % ("台账健康" if ok else "台账不健康（见上）"))
    return 0 if ok else 1


# ------------------------------------------------------------------ 复测模式
def cmd_replay(only: List[str], rounds: int) -> int:
    os.environ.setdefault("LDA_FDTD_THREADS", str(CALIB_THREADS))
    scripts = sorted(only) if only else sorted(R.NON_CORE_SMOKES)
    unknown = [s for s in scripts if s not in R.NON_CORE_SMOKES]
    if unknown:
        print("[warn] 不在豁免表内（照跑但不写台账）：%s" % unknown)
    py = sys.executable
    print("=" * 74)
    print("非 core 豁免复测（%d 项 · %d 轮 · @%d 线程 · 复刻 _child_env）"
          % (len(scripts), rounds, CALIB_THREADS))
    print("=" * 74)

    acc: Dict[str, Dict[str, Any]] = {}
    for rnd in range(1, rounds + 1):
        print("\n──── 第 %d/%d 轮 ────" % (rnd, rounds), flush=True)
        for s in scripts:
            r = R._run_one(py, s, CAP_S)
            print("  [%-7s] %-38s rc=%-3s %7.2fs · %s"
                  % (r["status"], s, r["rc"], r["elapsed_s"], _today()), flush=True)
            if r["status"] in R._FAIL_STATUSES:
                for ln in (r.get("tail") or "").splitlines():
                    print("            │ %s" % ln, flush=True)
            e = acc.setdefault(s, {"statuses": [], "samples": [], "tails": []})
            e["statuses"].append(r["status"])
            e["samples"].append(round(float(r["elapsed_s"]), 2))
            if r["status"] in R._FAIL_STATUSES:
                e["tails"].append(r.get("tail") or "")
            time.sleep(COOLDOWN_S)

    print("\n" + "=" * 74)
    print("复测汇总（跨轮上界 = max · 红项必须当场处置，不是「下次再说」）")
    print("=" * 74)
    for s in sorted(acc, key=lambda x: -max(acc[x]["samples"])):
        e = acc[s]
        mx = max(e["samples"])
        ok = all(st in ("PASS", "SKIP") for st in e["statuses"])
        print("  %-38s max=%7.2fs  %s  %s"
              % (s, mx, "绿" if ok else "红!", e["statuses"]))
        if not ok:
            for t in e["tails"]:
                print("      │ %s" % (t or "").replace("\n", "\n      │ "))

    led = build_ledger(acc, rounds, _load_ledger())
    write_ledger(led)
    all_green = bool(led.get("all_green"))
    print("\n台账已写：%s（%d 条 · %s）"
          % (LEDGER, len(led.get("rows") or {}), "全绿" if all_green else "存在红项"))
    return 0 if all_green else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="非 core 豁免项复测 / 台账体检")
    ap.add_argument("--check", action="store_true", help="只读台账（不跑 smoke）")
    ap.add_argument("--json", action="store_true", help="--check 输出 JSON")
    ap.add_argument("--rounds", type=int, default=1, help="复测轮数（默认 1）")
    ap.add_argument("--only", action="append", default=[],
                    help="只复测指定脚本（可重复）")
    a = ap.parse_args()
    if a.check:
        return cmd_check(as_json=a.json)
    return cmd_replay(a.only, max(1, a.rounds))


if __name__ == "__main__":
    raise SystemExit(main())
