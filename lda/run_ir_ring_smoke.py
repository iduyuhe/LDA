"""LDA · D-11 环形谱形逆设计闭环 smoke（IR → bridge → agent 真跑）。

验证环形谐振器（B11 谱形匹配）闭环端到端：
  1. RingResonator IR（R/Q/kappa/target_fsr_nm + SpectrumSpec）过 validate；
  2. round-trip 零损失 + to_dsl 渲染；
  3. bridge.ir_to_intent 由 RingResonator 构造 ring intent（D-11 补上此前
     NotImplementedError 缺口）；
  4. RingBandAgent 真跑：黄金分割调 R → FSR 命中目标 → 逐波长洛伦兹梳谱
     提取 FSR 与解析公式对拍（方法一致性）；
  5. PDK ring 模板 derive_intent → 同闭环真跑；
  6. 断言 PASS（谱形误差 ≤ target_tol 且 方法一致性 ≤ method_tol）。

退出码 0=全绿；非 0=有失败。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_ir import (IRModel, RingResonator, SpectrumSpec, FoundryPlan,
                    dumps, from_dict, to_dict, to_dsl, validate)
from lda_ir.bridge import ir_to_intent
from lda_agent.ring_loop import RingBandAgent


def check(cond: bool, msg: str) -> bool:
    if cond:
        print("OK  " + msg)
        return True
    print("FAIL " + msg)
    return False


def main() -> int:
    print("=== D-11 环形谱形逆设计闭环 smoke ===")
    ok = True

    # 1) RingResonator IR（D-05 v0.2 字段）+ SpectrumSpec
    ring = RingResonator(id="ring1", R=10.0, Q=1.0e4, kappa=0.05,
                         target_fsr_nm=9.15, R_bounds=(8.0, 12.0))
    m = IRModel(
        domain="photon",
        name="ring-fsr-d11",
        components=[ring],
        spectrum=SpectrumSpec(kind="ring_fsr", target_fsr_nm=9.15,
                              wl0_um=1.55, n_g=4.2, primary_param="R"),
        foundry_plan=FoundryPlan(mode="all"),
        notes="D-11：环形谱形逆设计闭环（B11 匹配）",
    )
    errs = validate(m)
    ok &= check(not errs, f"RingResonator IR 过 validate errs={errs}")
    m2 = from_dict(to_dict(m))
    ok &= check(dumps(m) == dumps(m2), "round-trip 零损失")
    ok &= check("target_fsr_nm=9.15" in to_dsl(m), "to_dsl 渲染含 target_fsr_nm")
    print("--- to_dsl() ---")
    print(to_dsl(m))
    print("---------------")

    # 2) bridge：RingResonator → ring intent（此前 NotImplementedError 缺口已补）
    from lda_l2.pdk import get_default_registry
    registry = get_default_registry()
    fk = [k for k in registry.list_pdks() if "量子" not in k][0]
    intent = ir_to_intent(m, registry, fk)
    ok &= check(intent["geometry_type"] == "ring"
                and intent["extra"]["target_fsr_nm"] == 9.15
                and intent["extra"]["R_bounds"] == [8.0, 12.0],
                "bridge 由 RingResonator 构造 ring intent（target_fsr/R_bounds 正确）")

    # 3) RingBandAgent 真跑闭环
    rep = RingBandAgent().run(intent)
    ok &= check(rep["accepted"], "环形闭环 PASS（谱形误差 + 方法一致性双判据）")
    ok &= check(rep["final_spectrum_err"] <= 0.03,
                f"谱形误差 {rep['final_spectrum_err']:.2e} ≤ target_tol=0.03")
    ok &= check(rep["final_fsr_method_err"] <= 0.02,
                f"方法一致性 {rep['final_fsr_method_err']:.2e} ≤ method_tol=0.02")
    ok &= check(abs(rep["final_fsr_measured_nm"] - 9.15) < 0.05,
                f"谱形提取 FSR={rep['final_fsr_measured_nm']:.4f}nm ≈ 目标 9.15nm")
    print(f"    final_R={rep['final_R_um']:.4f}µm  FSR_analytic="
          f"{rep['final_fsr_analytic_nm']:.4f}  FSR_measured="
          f"{rep['final_fsr_measured_nm']:.4f}  iters={rep['iterations']}")
    print(f"    verdict: {rep['verdict']}")

    # 4) PDK ring 模板 derive_intent → 同闭环真跑
    from lda_l2.pdk import get_default_registry
    for key in registry.list_pdks():
        for tpl in registry.get(key).templates.values():
            if tpl.device_type != "ring_resonator":
                continue
            try:
                pintent = registry.derive_intent(key, tpl.name)
            except NotImplementedError:
                continue  # 多参数/B11 变体诚实未接入（不在此 smoke 范围）
            prep = RingBandAgent().run(pintent)
            ok &= check(prep["accepted"],
                        f"PDK ring 模板 [{tpl.name}@{key.split('::')[0]}] 闭环 PASS "
                        f"(R={prep['final_R_um']:.3f}, FSR={prep['final_fsr_analytic_nm']:.3f}nm)")
    n_ring_derived = sum(
        1 for key in registry.list_pdks()
        for tpl in registry.get(key).templates.values()
        if tpl.device_type == "ring_resonator"
        and len(tpl.tunables) == 1 and "R" in tpl.tunables
        and tpl.target_metric == "FSR_nm")
    ok &= check(n_ring_derived >= 3,
                f"PDK 中单 R 调 FSR 的 ring 模板 {n_ring_derived} 个均真跑")

    print("\n=== D-11 环形谱形逆设计闭环 smoke: "
          + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
