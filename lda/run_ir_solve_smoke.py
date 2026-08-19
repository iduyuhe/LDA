"""LDA L0 · L3 直接消费 IR 的真值计算 smoke 测试。

证明"IR 即事实源"——L3 真值内核不必经由手写 DesignProblem，直接读 IR 的
spectrum / objectives 计算物理真值 + pass/fail 判定：
  1. 光子 IR（环形谱形 B11）+ 候选 R → ir_eval 直接算 B11 误差与 PASS；
  2. 量子 IR（transmon 频率 B9）+ 候选 E_J → ir_eval 直接算 f01 与 PASS；
  3. 与"经 agent 闭环优化"路径同源（共享 _inject_process_params 工艺窗口注入）；
  4. 断言：命中目标参数的 ir_eval.passed_all=True；失配参数判定 FAIL。
退出码 0=全绿；非 0=有失败。
"""
from __future__ import annotations

import sys

from lda_ir import (FoundryPlan, IRModel, ObjectiveSpec, RingResonator,
                    SpectrumSpec, Transmon, validate)
from lda_ir.bridge import ir_eval
from lda_l2.pdk import get_default_registry


def build_photon_ir() -> IRModel:
    # 注意：n_g 是工艺参数（由 foundry 决定），IR 不写死，由 bridge 注入
    # foundry.n_si——语义与量子 E_C 工艺固定完全对称：设计者只调几何 R。
    return IRModel(
        domain="photon",
        name="ring-fsr-B11",
        components=[RingResonator(id="ring", R=10.0, R_bounds=(8.0, 14.0))],
        spectrum=SpectrumSpec(kind="ring_fsr", target_fsr_nm=9.15,
                              wl0_um=1.55, primary_param="R"),
        foundry_plan=FoundryPlan(mode="all"),
    )


def build_quantum_ir() -> IRModel:
    return IRModel(
        domain="quantum",
        name="transmon-f01-B9",
        components=[Transmon(id="q1", E_J=20.0,
                             EJ_bounds=(5.0, 40.0), EC_bounds=(0.1, 1.0))],
        objectives=[ObjectiveSpec(bid="B9", target=5.0, tol=0.1,
                                  role="objective")],
        foundry_plan=FoundryPlan(mode="all"),
    )


def _assert(cond: bool, msg: str) -> int:
    print(("OK  " if cond else "FAIL ") + msg)
    return 0 if cond else 1


def main() -> int:
    print("=== L0 IR · L3 直接消费 IR 真值计算 smoke ===")
    reg = get_default_registry()
    fails = 0

    # --- 光子 B11 谱形 ---
    mp = build_photon_ir()
    fails += _assert(len(validate(mp)) == 0, "光子 IR 校验通过")

    # n_g 由 foundry 工艺注入（NOEIC n_si=3.48）；按该工艺窗口反解命中 R
    import math
    sp = mp.spectrum
    n_g = reg.get("NOEIC(演示近似)::SOI 180nm").n_si
    R_target = (sp.wl0_um ** 2) / (n_g * 2.0 * math.pi * (sp.target_fsr_nm / 1000.0))
    r_hit = ir_eval(mp, {"R": R_target}, foundry_key="NOEIC(演示近似)::SOI 180nm", registry=reg)
    print(f"  光子 B11 命中 R={R_target:.4f}µm → B11={r_hit['rows']['B11']['candidate']:.5f} "
          f"passed={r_hit['rows']['B11']['passed']}")
    fails += _assert(r_hit["passed_all"], "光子 B11 命中目标 R → ir_eval 判 PASS")

    r_miss = ir_eval(mp, {"R": 5.0}, foundry_key="NOEIC(演示近似)::SOI 180nm", registry=reg)
    print(f"  光子 B11 失配 R=5.0µm → B11={r_miss['rows']['B11']['candidate']:.5f} "
          f"passed={r_miss['rows']['B11']['passed']}")
    fails += _assert(not r_miss["passed_all"], "光子 B11 失配 R → ir_eval 判 FAIL")

    # --- 量子 B9 频率 ---
    mq = build_quantum_ir()
    fails += _assert(len(validate(mq)) == 0, "量子 IR 校验通过")

    # B 厂 E_C=0.45 → 命中 f01=5.0 所需 E_J
    EJ_target = (5.0 + 0.45) ** 2 / (8.0 * 0.45)
    q_hit = ir_eval(mq, {"E_J": EJ_target}, foundry_key="量子B(演示近似)::可调耦合 transmon（薄氧化层）", registry=reg)
    print(f"  量子 B9 命中 E_J={EJ_target:.4f}(E_C=0.45) → f01={q_hit['rows']['B9']['candidate']:.5f} "
          f"passed={q_hit['rows']['B9']['passed']}")
    fails += _assert(q_hit["passed_all"], "量子 B9 命中目标 E_J → ir_eval 判 PASS")

    q_miss = ir_eval(mq, {"E_J": 5.0}, foundry_key="量子B(演示近似)::可调耦合 transmon（薄氧化层）", registry=reg)
    print(f"  量子 B9 失配 E_J=5.0 → f01={q_miss['rows']['B9']['candidate']:.5f} "
          f"passed={q_miss['rows']['B9']['passed']}")
    fails += _assert(not q_miss["passed_all"], "量子 B9 失配 E_J → ir_eval 判 FAIL")

    if fails == 0:
        print("\n=== L0 IR · L3 直接消费 IR 真值计算: ALL GREEN ===")
        return 0
    print(f"\n=== FAIL ({fails}) ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())
