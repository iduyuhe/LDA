# -*- coding: utf-8 -*-
"""P3 附属突变探针：证明 `ci_core_batched._write_baseline` 的棘轮阈值**只降不升**。

为什么需要它（血案 · 本轮实测，非推测）
----------------------------------------
v0.9.132（P3「横向交叉验证网」全量 CI core 200 条后的基线刷新）实测到一个**真实缺口**：

  原 `_write_baseline` 把 `ratchet_below_target` **无条件重算**为当轮实际值
  ⇒ **刷新即静默放宽棘轮**；而 B9 判据是拿「基线里记的值」与「当轮实际值」比较
  ⇒ **同源恒绿** ⇒ 棘轮「只降不升」在**刷新通道**上完全失守。

  实测血案：`run_splitter_readout_smoke.py` 本轮 **231.7s / 660s = 2.849×**
  ⇒ 刷新把 `ratchet_below_target` 从 **0 写成 1**，B9 照绿，汇总行还印着
  「最低 2.849×，目标 ≥3.0× · ALL PASS」的**自相矛盾**结论。

修法（已落地于 `scripts/ci_core_batched.py`）：`min(prev_ratchet, 当轮实际项数)`
—— 阈值**只能人工下调，绝不被刷新自动上调**；当轮实际项数高于历史阈值时
B9 必须红（把「欠标定」推回给人）。首刷（无基线）无历史可锚 ⇒ 用当轮实际值起步。

本探针（人工运行 · **不进 CI** · 遵「突变探针只人工跑」铁律）
------------------------------------------------------------
在 tmp 目录复刻一次**真刷新**（`dst=` 临时路径 ⇒ **零副作用**，不碰真基线），
用同一份输入验证四件（缺一不可）：

  ① **不上调**：基线锚 0 + 本轮出现 1 项 <3× ⇒ 刷新后阈值仍 **0**（旧实现会给 1）
  ② **仍并入**：同一轮的 `elapsed_max_s` **必须**抬到新上界
     （防「为了保住阈值，连并入语义一起砍掉」这种把判据改坏的『修法』）
  ③ **可下调**：基线锚 5（虚高）+ 实际 1 项 ⇒ 刷新后降到 **1**
     （防「一律冻结」的假硬化 —— 阈值确实允许人工下调后重新锚定）
  ④ **新旧分叉**：同输入下内联**旧公式**给 1、**新实现**给 0
     ⇒ 判据非空转，有效性自证（「有效性 = 判据跑新旧两版」）

运行（仓库根）：python scripts/p3_ratchet_probe.py   → 4/4 全过则 rc=0
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, os.path.join(_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_ci_regression as R          # noqa: E402
import ci_core_batched as B            # noqa: E402

TARGET_X = 3.0
_PROBE_LABEL = "__p3_ratchet_probe__"


def _make_prev(victim, budget, anchor, hist):
    """造一份最小可信的『上一版基线』：只含 victim 一行 + 指定历史锚。"""
    return {
        "schema": "lda.timeout_budget_baseline/1",
        "ratchet_below_target": anchor,
        "rows": [{
            "script": victim,
            "budget_s": budget,
            "elapsed_max_s": hist,
            "margin_x": round(budget / hist, 3),
            "samples_s": [hist],
            "n_rounds": 1,
            "censored_events": 0,
        }],
        "source_reports": [],
    }


def _refresh(victim, budget, hot, anchor, hist):
    """在 tmp 里复刻一次真刷新（零副作用），返回刷新后的基线 dict。"""
    with tempfile.TemporaryDirectory() as td:
        dst = os.path.join(td, "baseline_probe.json")
        with open(dst, "w", encoding="utf-8") as fh:
            json.dump(_make_prev(victim, budget, anchor, hist), fh)
        buf = io.StringIO()                      # 吞掉 183 行「基线跳过…」warn
        with contextlib.redirect_stdout(buf):
            out = B._write_baseline(
                [{"script": victim, "rc": 0, "status": "PASS", "elapsed_s": hot}],
                label=_PROBE_LABEL, threads=10, dst=dst)
    return out, buf.getvalue()


def main() -> int:
    victim = "run_benchmark_falsifiability_smoke.py"
    if victim not in R._BUILTIN_TIMEOUT_OVERRIDE:      # 回退：取覆盖表里预算最大项
        victim = max(R._BUILTIN_TIMEOUT_OVERRIDE,
                     key=lambda k: R._BUILTIN_TIMEOUT_OVERRIDE[k])
    budget = float(R._BUILTIN_TIMEOUT_OVERRIDE[victim])
    hot = round(budget / 2.9, 2)      # margin = 2.90 ⇒ <3× 且 ≥2×（贴线态）
    hist = round(budget / 4.0, 2)     # 历史上界 ⇒ margin = 4.00

    print("=" * 74)
    print("P3 棘轮阈值探针：刷新不得上调 ratchet_below_target（只降不升）")
    print("=" * 74)
    print("  样本脚本 : %s" % victim)
    print("  预算     : %.0fs（覆盖表现值）" % budget)
    print("  本轮实测 : %.2fs ⇒ margin = %.3f×（<%.1f ⇒ 贴线 1 项）"
          % (hot, budget / hot, TARGET_X))
    print("  历史上界 : %.2fs ⇒ margin = %.3f×" % (hist, budget / hist))
    print("-" * 74)

    out_a, log_a = _refresh(victim, budget, hot, 0, hist)
    rows_a = {r["script"]: r for r in out_a["rows"]}
    row_a = rows_a.get(victim)
    below_a = [r["script"] for r in out_a["rows"] if r["margin_x"] < TARGET_X]
    ratchet_a = int(out_a["ratchet_below_target"])
    old_formula_a = len(below_a)              # 旧实现会把这个数写进阈值

    c1 = ratchet_a == 0
    c2 = row_a is not None and abs(float(row_a["elapsed_max_s"]) - hot) < 1e-6
    c4 = (old_formula_a == 1) and (ratchet_a == 0)

    out_b, _ = _refresh(victim, budget, hot, 5, hist)
    ratchet_b = int(out_b["ratchet_below_target"])
    c3 = ratchet_b == 1

    print("  ① 不上调  : 锚 0 + 实际 1 项 <3× ⇒ 刷新后阈值 = %d  %s"
          % (ratchet_a, "PASS" if c1 else "FAIL"))
    print("  ② 仍并入  : elapsed_max_s = %s（期望 %.2f）  %s"
          % (None if row_a is None else row_a["elapsed_max_s"], hot,
             "PASS" if c2 else "FAIL"))
    print("  ③ 可下调  : 锚 5 + 实际 1 项 ⇒ 刷新后阈值 = %d（期望 1）  %s"
          % (ratchet_b, "PASS" if c3 else "FAIL"))
    print("  ④ 新旧分叉: 旧公式 %d ≠ 新实现 %d  %s"
          % (old_formula_a, ratchet_a, "PASS" if c4 else "FAIL"))
    print("-" * 74)
    print("  贴线项   : %s" % (below_a or "（无）"))
    print("  吞掉的刷新日志行数：%d" % len(log_a.splitlines()))

    ok = c1 and c2 and c3 and c4
    print("=" * 74)
    print("汇总：%d/4 PASS —— %s"
          % (sum([c1, c2, c3, c4]),
             "刷新已不可能静默放宽棘轮 ✅" if ok else "缺口未堵住 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
