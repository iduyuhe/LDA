"""QS-M1 烟雾测试：跑通「量子传感灵敏度 FOM 体系 + 守卫 + 反向探针」并落盘交付物。

量子传感器芯片征程（QS-M1 · 灵敏度 FOM 体系）基线常驻门禁：
  `qs_m1.selfcheck_qs_m1()` 全项判据（12 项）——
    · 口径自检通过 ×1 / 口径反向探针（混入线宽受限 LOD 必被拒）×1
    · 双路径一致（T2* 路径 ↔ 线宽路径 rel<1e-9）×1
    · 单调性（T2*↑⇒η↓ / C↑⇒η↓ / n_ph↑⇒η↓）×3
    · 情景序（degraded 劣于 baseline / cited 优于 baseline）×2
    · 反向探针（零对比度发散 / 零光子率发散 / 零线宽抛异常）×3
    · 暗计数只劣化（a>0 ⇒ η 更大）×1
  另加**锚接线复核**（B474 已入账 + 严格独立 + 候选有响应）——防「账本登记了但
  候选链没接上」的静默漏。

🔴 一次现算：`design_fom_system()` 的 report 与 selfcheck 共用同一次现算
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

from lda_l2.qs_m1 import design_fom_system  # noqa: E402


def _check_anchor_wiring() -> dict:
    """锚接线复核（B474）：入 BENCHMARK_ORDER + 严格独立 + 候选有响应。

    🔴 这是 QS-M0 血案（B473 曾因空 params 被误判自证桩）的常驻防线：
    「账本登记了」≠「候选链接上了」，必须现算验证。
    """
    from lda_harness.benchmarks import BENCHMARK_ORDER
    from lda_harness.golden import golden_value
    from lda_harness.harness import candidate_responds
    from lda_harness._adapter_p4 import _b474_qs_fom_linewidth_cand as cand

    res: dict = {"B474_in_order": "B474" in BENCHMARK_ORDER}
    params = {"T2star_s": 1e-6, "n_ph_per_s": 1e5, "contrast": 0.03, "dark_ratio": 0.0}

    class _S:
        pass

    sp = _S()
    sp.params = params
    sp.spec_id = "B474"
    g = golden_value("B474", params)
    res["B474_golden_finite"] = bool(g == g and g > 0)     # not NaN, >0
    res["B474_candidate_responds"] = bool(candidate_responds(sp, cand, g))
    c = cand(sp, g)
    rel = abs(c - g) / g
    res["B474_rel"] = rel
    res["B474_within_tol"] = bool(rel < 1e-3)              # tol=1e-3
    res["B474_independent_not_identity"] = bool(rel > 1e-12)  # 非机器精度 ⇒ 非代数恒等
    return res


def main(out_dir: str | None = None) -> int:
    # ① 一次现算：灵敏度 FOM 体系（纯 numpy，<1s）
    rep = design_fom_system(run_checks=True)

    all_pass = True
    print("=" * 64)
    checks = rep["checks"]
    for k, v in checks.items():
        # 行首 [PASS]/[FAIL] 口径 —— 供 W10 README「当前版本」行判据数机器对照
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    npass = sum(1 for v in checks.values() if v)
    print(f"QS-M1 自校：{npass}/{len(checks)} "
          f"{'PASS' if npass == len(checks) else 'FAIL'}")
    if npass != len(checks):
        all_pass = False

    # ② 锚接线复核（B474）
    wiring = _check_anchor_wiring()
    wchecks = {k: v for k, v in wiring.items() if k != "B474_rel"}
    for k, v in wchecks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"  [----] B474_rel = {wiring['B474_rel']:.4e}")
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
        with open(os.path.join(out_dir, "qs_m1_report.json"), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False, default=str)

    print("-" * 64)
    print(f"  统一口径：{rep['caliber']}")
    print(f"  测量条件：{rep['conditions']}")
    for n, s in rep["scenarios"].items():
        print(f"  [{n:8s}] η = {s['eta_pT_per_sqrtHz']:.4f} pT/√Hz "
              f"(T2*={s['params']['T2star_s']:.3g}s, C={s['params']['contrast']:.3g}, "
              f"n_ph={s['params']['n_ph_per_s']:.3g}/s)")
    print(f"  交付物：{out_dir}")
    return 0


if __name__ == "__main__":
    _out = os.path.join(_HERE, "..", "outputs", "qs_m1")
    raise SystemExit(main(out_dir=_out))
