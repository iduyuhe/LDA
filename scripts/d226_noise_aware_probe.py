"""D-226 突变探针（scratch · 不入 CI）：证明 run_noise_aware_schedule_smoke.py 能变红。

惯例：`scripts/*_probe.py` 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件**），逐条造假后重跑门禁，
确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 `p_exact` 放大成 1.5×Σp                      ⇒ D1 应红（破可证上界）
  · M2 `p_exact` 缩成 0.5×p_max                     ⇒ D1 应红（破可证下界）
  · M3 `p_exact` 恒返回常量（与 op 数脱钩）          ⇒ D2 应红（严格单调被破坏）
  · M4 未登记门静默当 0（不报 fallback）            ⇒ D4 应红（兜底被抹）
  · M5 `parallel_gain` 恒返 1（抹掉并行收益）        ⇒ P1/P2 应红
  · M6 `syndrome_rounds` 返 r−1（欠算一轮）         ⇒ Q1 应红（定义式左边破）
  · M7 `syndrome_rounds` 返 r+1（多算一轮）         ⇒ Q1 应红（定义式左边破）
  · M8 `parallel_gain` 的 depth 多报 1              ⇒ C2 应红（跨模块同口径被破坏）
🔴 教训：探针必须 patch 门禁**同一模块对象**（`lda_qeda.noise_aware_schedule`）；
   `layer_profile` / `budget_report` 内部也是按模块全局名调 `error_budget` / `syndrome_rounds`，
   故 patch 模块属性可一路命中最内层。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_noise_aware_schedule_smoke as S      # noqa: E402
from lda_qeda import noise_aware_schedule as NS  # noqa: E402  同一 sys.modules 实例


def run_smoke():
    S.PASS = 0
    S.FAIL = 0
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = S.main()
    except Exception as e:                     # 突变致病态 ⇒ 崩溃也算红
        rc = 99
        buf.write("[FAIL] 门禁异常：%s: %s" % (type(e).__name__, e))
    out = buf.getvalue()
    return rc, out.count("[FAIL]")


def main() -> int:
    rows = []
    rows.append(("baseline 无突变（须全绿）", *run_smoke()))

    _budget = NS.error_budget
    _gain = NS.parallel_gain
    _rounds = NS.syndrome_rounds
    _p_of = NS._p_of

    # M1 破上界：p_exact 放大成 1.5×Σp
    def _budget_hi(ops, **kw):
        d = dict(_budget(ops, **kw))
        d["p_exact"] = 1.5 * d["p_first_order"]
        d["bound_ok"] = False
        return d

    NS.error_budget = _budget_hi
    rows.append(("M1 p_exact 放大成 1.5×Σp（破上界）", *run_smoke()))
    NS.error_budget = _budget

    # M2 破下界：p_exact 缩成 0.5×p_max
    def _budget_lo(ops, **kw):
        d = dict(_budget(ops, **kw))
        d["p_exact"] = 0.5 * d["p_max"]
        d["bound_ok"] = False
        return d

    NS.error_budget = _budget_lo
    rows.append(("M2 p_exact 缩成 0.5×p_max（破下界）", *run_smoke()))
    NS.error_budget = _budget

    # M3 破单调：p_exact 恒常量
    def _budget_flat(ops, **kw):
        d = dict(_budget(ops, **kw))
        d["p_exact"] = 1e-2
        return d

    NS.error_budget = _budget_flat
    rows.append(("M3 p_exact 恒常量（与 op 数脱钩）", *run_smoke()))
    NS.error_budget = _budget

    # M4 未登记门静默当 0
    def _p_zero(kind, per_gate):
        try:
            return _p_of(kind, per_gate)
        except Exception:
            return (0.0, "fallback")

    def _p_silent(kind, per_gate):
        if (per_gate and kind in per_gate) or kind in NS.DEFAULT_GATE_ERROR:
            return _p_of(kind, per_gate)
        return (0.0, "default")            # 冒充已登记，且 p=0

    NS._p_of = _p_silent
    rows.append(("M4 未登记门静默当 0（不报 fallback）", *run_smoke()))
    NS._p_of = _p_of

    # M5 抹掉并行收益
    def _gain_one(result):
        d = dict(_gain(result))
        if d["n_ops"] > 0:
            d["gain"] = 1.0
            d["gain_in_range"] = True
        return d

    NS.parallel_gain = _gain_one
    rows.append(("M5 parallel_gain 恒返 1（抹掉并行收益）", *run_smoke()))
    NS.parallel_gain = _gain

    # M6 欠算一轮
    NS.syndrome_rounds = lambda pc, pl: max(0, _rounds(pc, pl) - 1)
    rows.append(("M6 syndrome_rounds 返 r−1（欠算一轮）", *run_smoke()))
    NS.syndrome_rounds = _rounds

    # M7 多算一轮
    NS.syndrome_rounds = lambda pc, pl: _rounds(pc, pl) + 1
    rows.append(("M7 syndrome_rounds 返 r+1（多算一轮）", *run_smoke()))
    NS.syndrome_rounds = _rounds

    # M8 depth 多报 1（破坏与 ft_compiler.resource_report 的同口径）
    def _gain_depth(result):
        d = dict(_gain(result))
        if d["n_ops"] > 0:
            d["depth"] = d["depth"] + 1
        return d

    NS.parallel_gain = _gain_depth
    rows.append(("M8 depth 多报 1（跨模块同口径被破坏）", *run_smoke()))
    NS.parallel_gain = _gain

    print("=" * 78)
    bad = 0
    for name, rc, nfail in rows:
        good = (rc == 0 and nfail == 0) if name.startswith("baseline") else (rc != 0 and nfail > 0)
        if not good:
            bad += 1
        print("%-6s %-50s rc=%-3d FAIL=%d" % ("[OK]" if good else "[BAD]", name, rc, nfail))
    print("=" * 78)
    print("突变探针：%d 条，%d 条未按预期变红" % (len(rows) - 1, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
