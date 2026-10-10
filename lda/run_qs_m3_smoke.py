"""QS-M3 烟雾测试：跑通「灵敏度几何优化 + 守卫 + 反向探针」并落盘交付物。

量子传感器芯片征程（QS-M3 · 灵敏度几何优化）基线常驻门禁：
  `qs_m3.selfcheck_qs_m3()` 全项判据（15 项）——
    · NA 收集效率 闭式 ∧ 数值 一致 ×1
    · η_NA 随 NA 单调增 + 边界 NA=1⇒1 ×2
    · 收集效率随深度单调降 ×1
    · 最优深度 闭式 ∧ 数值 一致 + 确为极小点 ×2
    · Purcell 计数率比 闭式 ∧ 数值 一致 + ≥1 ×2
    · bulk 对照 ∈ (0,1] ×1
    · 反向探针（NA 越界抛异常 / 负深度抛异常 / 错模型被判红 /
      β=0 无增强 / κ=0 发散）×5
    · 口径自检 ×1
  另加**锚接线复核**（B476/B477 已入账 + 严格独立 + 候选有响应）——防「账本登记了
  但候选链没接上」的静默漏。

🔴 一次现算：`design_geometry()` 的 report 与 selfcheck 共用同一次现算
（纯 numpy，单次 <1s）。
纯 stdlib + numpy ⇒ 入 CI core 集（run_ci_regression.py）；timeout 120s 留 ≥100× 余量。

退出码 0=PASS，非 0=FAIL（CI 契约：rc==0?PASS:FAIL，绝不允许 main() 恒 0 假绿）。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_l2.qs_m3 import design_geometry  # noqa: E402


def _check_one_anchor(bid: str, params: dict, cand) -> dict:
    """单锚接线复核：入 BENCHMARK_ORDER + golden 有限 + 候选有响应 + 非恒等。"""
    from lda_harness.benchmarks import BENCHMARK_ORDER
    from lda_harness.golden import golden_value
    from lda_harness.harness import candidate_responds

    res: dict = {f"{bid}_in_order": bid in BENCHMARK_ORDER}

    class _S:
        pass

    sp = _S()
    sp.params = params
    sp.spec_id = bid
    g = golden_value(bid, params)
    res[f"{bid}_golden_finite"] = bool(g == g and g > 0)     # not NaN, >0
    res[f"{bid}_candidate_responds"] = bool(candidate_responds(sp, cand, g))
    c = cand(sp, g)
    rel = abs(c - g) / g
    res[f"{bid}_rel"] = rel
    res[f"{bid}_within_tol"] = bool(rel < 1e-3)              # tol=1e-3
    res[f"{bid}_independent_not_identity"] = bool(rel > 1e-12)  # 非机器精度 ⇒ 非代数恒等
    return res


def _check_anchor_wiring() -> dict:
    """锚接线复核（B476/B477）：入 BENCHMARK_ORDER + 严格独立 + 候选有响应。

    🔴 这是 QS-M0 血案（B473 曾因空 params 被误判自证桩）的常驻防线：
    「账本登记了」≠「候选链接上了」，必须现算验证。
    """
    from lda_harness._adapter_p4 import (
        _b476_optimal_depth_grid_search_cand as cand476,
        _b477_na_efficiency_sampling_cand as cand477,
    )
    res: dict = {}
    res.update(_check_one_anchor("B476", {"d0_nm": 20.0, "d_att_nm": 200.0}, cand476))
    res.update(_check_one_anchor("B477", {"na": 0.75}, cand477))
    return res


def main(out_dir: str | None = None) -> int:
    # ① 一次现算：灵敏度几何优化（纯 numpy，<1s）
    rep = design_geometry(run_checks=True)

    all_pass = True
    print("=" * 64)
    checks = rep["checks"]
    for k, v in checks.items():
        # 行首 [PASS]/[FAIL] 口径 —— 供 W10 README「当前版本」行判据数机器对照
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    npass = sum(1 for v in checks.values() if v)
    print(f"QS-M3 自校：{npass}/{len(checks)} "
          f"{'PASS' if npass == len(checks) else 'FAIL'}")
    if npass != len(checks):
        all_pass = False

    # ② 锚接线复核（B476/B477）
    wiring = _check_anchor_wiring()
    wchecks = {k: v for k, v in wiring.items() if not k.endswith("_rel")}
    for k, v in wchecks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    for bid in ("B476", "B477"):
        print(f"  [----] {bid}_rel = {wiring[f'{bid}_rel']:.4e}")
    wfail = [k for k, v in wchecks.items() if not v]
    if wfail:
        all_pass = False

    if not all_pass:
        print(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return 1

    # ③ 落盘报告（含 selfcheck 结论 + 锚接线），供客户/审阅查看
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        rep["anchor_wiring"] = wiring
        with open(os.path.join(out_dir, "qs_m3_report.json"), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False, default=str)

    print("-" * 64)
    print(f"  统一口径：{rep['caliber']}")
    for n, s in rep["geometry"].items():
        print(f"  [{n:16s}] η_NA = {s['eta_na']:.5f} | d = {s['depth_nm']:.2f}nm "
              f"(d*={s['optimal_depth_nm']:.2f}) | η_coll = {s['eta_collection']:.6f} | "
              f"R/R0 = {s['purcell_rate_ratio']:.1f} | bulk = "
              f"{s['vs_bulk_fraction'] * 100.0:.2f}%")
    print(f"  交付物：{out_dir}")
    return 0


if __name__ == "__main__":
    _out = os.path.join(_HERE, "..", "outputs", "qs_m3")
    raise SystemExit(main(out_dir=_out))
