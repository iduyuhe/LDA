"""QS-M2 烟雾测试：跑通「退相干 + 多源噪声 + 守卫 + 反向探针」并落盘交付物。

量子传感器芯片征程（QS-M2 · 退相干 + 多源噪声）基线常驻门禁：
  `qs_m2.selfcheck_qs_m2()` 全项判据（14 项）——
    · 回波方差 ≤ FID 方差 ×1
    · DC 阶数（回波四阶 1/32 / FID 二阶 1）×2
    · CPMG 滤波函数 DC 归零 ×1
    · 四源合成口径（baseline==纯光子散粒 / η_real≥任一分量）×2
    · 单调性（realistic 劣于 baseline / DD 优于 baseline）×2
    · 反向探针（零对比度发散 / 负 T₂ 抛异常 / 零脉冲抛异常 /
      DC 阶数判别力 / 微波零抖动口径）×5
    · 口径自检 ×1
  另加**锚接线复核**（B475 已入账 + 严格独立 + 候选有响应）——防「账本登记了但
  候选链没接上」的静默漏。

🔴 一次现算：`design_coherence_noise()` 的 report 与 selfcheck 共用同一次现算
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

from lda_l2.qs_m2 import design_coherence_noise  # noqa: E402


def _check_anchor_wiring() -> dict:
    """锚接线复核（B475）：入 BENCHMARK_ORDER + 严格独立 + 候选有响应。

    🔴 这是 QS-M0 血案（B473 曾因空 params 被误判自证桩）的常驻防线：
    「账本登记了」≠「候选链接上了」，必须现算验证。
    """
    from lda_harness.benchmarks import BENCHMARK_ORDER
    from lda_harness.golden import golden_value
    from lda_harness.harness import candidate_responds
    from lda_harness._adapter_p4 import _b475_echo_variance_time_integration_cand as cand

    res: dict = {"B475_in_order": "B475" in BENCHMARK_ORDER}
    params = {"omega_t": 2.0, "t": 1.0}

    class _S:
        pass

    sp = _S()
    sp.params = params
    sp.spec_id = "B475"
    g = golden_value("B475", params)
    res["B475_golden_finite"] = bool(g == g and g > 0)     # not NaN, >0
    res["B475_candidate_responds"] = bool(candidate_responds(sp, cand, g))
    c = cand(sp, g)
    rel = abs(c - g) / g
    res["B475_rel"] = rel
    res["B475_within_tol"] = bool(rel < 1e-3)              # tol=1e-3
    res["B475_independent_not_identity"] = bool(rel > 1e-12)  # 非机器精度 ⇒ 非代数恒等
    return res


def main(out_dir: str | None = None) -> int:
    # ① 一次现算：退相干 + 多源噪声（纯 numpy，<1s）
    rep = design_coherence_noise(run_checks=True)

    all_pass = True
    print("=" * 64)
    checks = rep["checks"]
    for k, v in checks.items():
        # 行首 [PASS]/[FAIL] 口径 —— 供 W10 README「当前版本」行判据数机器对照
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    npass = sum(1 for v in checks.values() if v)
    print(f"QS-M2 自校：{npass}/{len(checks)} "
          f"{'PASS' if npass == len(checks) else 'FAIL'}")
    if npass != len(checks):
        all_pass = False

    # ② 锚接线复核（B475）
    wiring = _check_anchor_wiring()
    wchecks = {k: v for k, v in wiring.items() if k != "B475_rel"}
    for k, v in wchecks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"  [----] B475_rel = {wiring['B475_rel']:.4e}")
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
        with open(os.path.join(out_dir, "qs_m2_report.json"), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False, default=str)

    print("-" * 64)
    print(f"  统一口径：{rep['caliber']}")
    for n, s in rep["noise_budget"].items():
        print(f"  [{n:11s}] η_real = {s['eta_real_pT_per_sqrtHz']:.4f} pT/√Hz "
              f"(T2={s['coherence_time_s']:.3g}s | 散粒 "
              f"{s['eta_photon_shot_T_per_sqrtHz'] * 1e12:.2f} / 微波 "
              f"{s['eta_microwave_T_per_sqrtHz'] * 1e12:.2f} / 温 "
              f"{s['eta_temperature_T_per_sqrtHz'] * 1e12:.2f} / 磁 "
              f"{s['eta_magnetic_T_per_sqrtHz'] * 1e12:.2f})")
    print(f"  交付物：{out_dir}")
    return 0


if __name__ == "__main__":
    _out = os.path.join(_HERE, "..", "outputs", "qs_m2")
    raise SystemExit(main(out_dir=_out))
