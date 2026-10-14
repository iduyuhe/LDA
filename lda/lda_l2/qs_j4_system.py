# -*- coding: utf-8 -*-
"""J4-M4 量子传感系统总装与签核（Quantum Sensing System Integration · Layer 4 · 收官）。

═══ 这是什么 ═══
把 J4 四档串成**一条可复算的系统签核链**：

    M0 多参数解耦（qs_j4_multiparam）   → 四场参数能否被分离（κ / N_amp / 解耦残差）
    M1 芯片级 OPM 微型化（qs_j4_microcell）→ 微型化后弛豫率上升多少（劣化倍率）
    M2 单芯片集成（qs_j4_integration）   → 跨域隔离度是否够（净灵敏度劣化）
    M3 封装热负载（qs_j4_packaging）     → 线束热负载是否在冷量预算内

四档各自签核 ⇒ 系统级签核（**全 ACCEPT 才 ACCEPT**，任一 REJECT 即 REJECT）。
—— 这是「器件级灵敏度」第一次被**系统级成本项**（解耦稳定性 / 微型化 / 集成 / 热负载）校正。

🔴 **账本锚归属（如实登记）**：本模块**不新增锚**（总装层是验证产物，非独立物理量）；
系统链的锚来源 = **B515**（M0 多参数解耦）+ **B518**（M3 低温线束热负载）；
M1 / M2 **锚净增 0**（候选物理量被既有锚占用，见两模块的避让表）。

═══ 诚实边界 ═══
· 所有参数为**设计示例量级**（非实测 PDK / 非流片 / 非商用器件数据表）；
· 只证「四档签核链可运行 + 系统级成本项量级合理」，**不作制造/性能宣称**；
· 未建模：系统级功耗/散热耦合、长期漂移、多传感器组网。
零商业依赖（纯 numpy + math；零 RNG）。
"""
from __future__ import annotations

from lda_l2.qs_j4_integration import integration_report
from lda_l2.qs_j4_microcell import microcell_report
from lda_l2.qs_j4_multiparam import multiparam_report
from lda_l2.qs_j4_packaging import package_report

_CALIBER = "量子传感系统集成总装 · 四档签核链 · 设计示例量级"

#: 本档系统链的账本锚来源（如实登记 · 总装层本身不新增锚）
SYSTEM_ANCHORS = ("B515", "B518")
ZERO_ANCHOR_STAGES = ("M1_microcell", "M2_integration")


def assert_caliber(caliber: str) -> None:
    if caliber != _CALIBER:
        raise ValueError("系统口径不符：本模块仅支持 %r" % _CALIBER)


def qs_system_report(coupling: float = 1.0, iter_steps: int = 320,
                     n_wires: int = 20, budget_w: float = 1.0) -> dict:
    """J4 四档总装报告（各档签核 + 系统签核 + 锚归属）。"""
    m0 = multiparam_report(coupling, iter_steps)
    m1 = microcell_report()
    m2 = integration_report()
    m3 = package_report(n_wires=n_wires, budget_w=budget_w)
    stages = {"M0_multiparam": m0["verdict"], "M1_microcell": m1["verdict"],
              "M2_integration": m2["verdict"], "M3_packaging": m3["verdict"]}
    all_accept = all(v == "ACCEPT" for v in stages.values())
    return {
        "caliber": _CALIBER,
        "stages": stages,
        "all_accept": bool(all_accept),
        "m0_condition_number": float(m0["condition_number"]),
        "m0_noise_amplification": float(m0["noise_amplification_temperature"]),
        "m0_tau_hat": float(m0["tau_hat_temperature"]),
        "m1_miniaturization_penalty": float(m1["miniaturization_penalty"]),
        "m2_net_sensitivity_penalty": float(m2["net_sensitivity_penalty"]),
        "m3_total_load_w": float(m3["total_load_w"]),
        "m3_budget_fraction": float(m3["budget_fraction"]),
        "system_anchors": list(SYSTEM_ANCHORS),
        "zero_anchor_stages": list(ZERO_ANCHOR_STAGES),
        "verdict": "ACCEPT" if all_accept else "REJECT",
    }


# ── 自检 ────────────────────────────────────────────────────────────────
def selfcheck_qs_j4_system() -> dict:
    checks = {}
    rep = qs_system_report()
    checks["four_stages_present"] = bool(len(rep["stages"]) == 4)
    checks["all_stages_accept"] = bool(rep["all_accept"])
    checks["system_verdict_accept"] = bool(rep["verdict"] == "ACCEPT")
    checks["anchors_are_b515_b518"] = bool(list(rep["system_anchors"]) == ["B515", "B518"])
    checks["zero_anchor_stages_registered"] = bool(
        list(rep["zero_anchor_stages"]) == ["M1_microcell", "M2_integration"])
    # 各档数值跨模块一致（总装不重算 ⇒ 与子模块同源）
    m0 = multiparam_report()
    checks["m0_tau_matches_submodule"] = bool(
        abs(rep["m0_tau_hat"] - m0["tau_hat_temperature"]) == 0.0)
    checks["m0_cond_matches_submodule"] = bool(
        abs(rep["m0_condition_number"] - m0["condition_number"]) == 0.0)
    m3 = package_report()
    checks["m3_load_matches_submodule"] = bool(
        abs(rep["m3_total_load_w"] - m3["total_load_w"]) == 0.0)
    # 反向探针：超预算 ⇒ M3 REJECT ⇒ 系统 REJECT
    bad = qs_system_report(n_wires=2000, budget_w=1.0)
    checks["reverse_over_budget_rejects"] = bool(
        bad["stages"]["M3_packaging"] == "REJECT" and bad["verdict"] == "REJECT")
    checks["reverse_bad_caliber_raises"] = _raises(lambda: assert_caliber("x"))
    return checks


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def main() -> int:
    sc = selfcheck_qs_j4_system()
    bad = 0
    print("=" * 64)
    print("J4-M4 系统总装签核自检：")
    for k, v in sc.items():
        ok = bool(v)
        bad += 0 if ok else 1
        print("  [%s] %s" % ("PASS" if ok else "FAIL", k))
    print("=" * 64)
    print("ALL PASS" if bad == 0 else "%d FAIL" % bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
