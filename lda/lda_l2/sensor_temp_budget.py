# -*- coding: utf-8 -*-
"""📐 温漂预算：把「须片载温控」这句处方变成**可判红的可行性判定**（`sensor_temp_budget`）。

定位：`sensor` 卡的 `G_temp_drift` 一直写着「LOD_real 由温漂主导 ⇒ **须片载温控 / 参考通道**」。
但「须片载温控」是一句**处方**，从没有人算过它到底要求多稳 —— 本层把它算出来，然后发现：
**这条处方在常规意义上不可行**。

物理链（三行闭式）
  ① 微环热容        `C = ρc_p·V`，`V = 2πR·w·h`（`ρc_p` **引用** `lda_l2.pm_thermal.RC_SI`）
  ② 热力学涨落下限  `δT_rms = T·√(k_B/C)`（正则系综 `⟨δE²⟩=k_BT²C` ⇒ `⟨δT²⟩=k_BT²/C`）
  ③ 温漂预算        `LOD_temp = dn/dT · dT_stab / CMR`（与卡内 `_lod_real` 同式）
     反解 parity（`LOD_temp = LOD_elec`）：
       `dT_req = LOD_elec·CMR / (dn/dT)`   ·   `CMR_req = (dn/dT)·dT_stab / LOD_elec`

🔴 **两条处方互为倒数替代（本层最锋利的一行）**
  parity 条件只看**一个数**：`dT_stab / CMR ≤ LOD_elec/(dn/dT)`。
  ⇒ 恒等式 `CMR_req(δT) ≡ δT / dT_req`：**温度稳定度与共模抑制可以任意兑换**
    （温控好 100 倍 ⇔ CMR 差 100 倍，LOD 完全不变）。
  ⇒ 🔴 这也是「比值判据」的老陷阱第五次现身：`dT_stab×100 且 CMR×100 ⇒ LOD **逐位不变**`
    ⇒ **只判比值等于什么都没判**。故本层必须另配**两个各自独立、各有物理来源的上限**：
      · `dT_stab` 的上限来自**热力学**：`δT_rms = T√(k_B/C)`（器件自身的热涨落）
      · `CMR` 的上限来自**工艺**：`CMR = 1/δ`，片上 MMI 分光比失配典型 1–3%（v0.9.291）

🔴 **诚实边界**：`R = 10 µm` / `w = 0.5 µm` / `h = 0.22 µm` / `T = 293.15 K` 为**设计示例**；
  `δT_rms` 是**平衡热涨落**（常规 PID/被动温控的可达下限量级），**不是绝对不可能** ——
  反馈若要把温度压到它以下，必须靠**主动冷阻尼**把涨落挤进控制环（代价是额外热导与噪声注入），
  那条路径本层**不建模**。且只建模**单模体热容**：未含衬底/包层的热扩散长度修正、
  多模温度梯度、泵浦吸收导致的局部温升、以及探测器侧的温漂。
  零商业依赖（纯 `math`）；零 RNG；**LLM 不进判决路径**。
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from lda_l2.pm_thermal import RC_SI

__all__ = [
    "SENSOR_TEMP_BUDGET_CALIBER",
    "K_B_SI",
    "DEFAULT_TEMP_K",
    "DEFAULT_W_WG_UM",
    "DEFAULT_H_WG_UM",
    "CMR_TYPICAL_PUBLIC",
    "ring_heat_capacity_j_per_k",
    "thermal_fluctuation_floor_k",
    "lod_temp_riu",
    "required_dt_for_parity_k",
    "required_cmr_for_parity",
    "temp_budget_report",
    "selfcheck_sensor_temp_budget",
]

SENSOR_TEMP_BUDGET_CALIBER = "temp_drift_budget__riu"

#: 🔴 Boltzmann（**SI 2019 起为定义值** · 精确）—— 与 `qnet_thermal_noise.KB_SI` 逐位同源（判据机核）
K_B_SI = 1.380649e-23

#: 器件工作温度（**设计示例** · 室温档）
DEFAULT_TEMP_K = 293.15

#: 波导截面（**设计示例** · 卡上 `G_pdk_geometry` 已声明「SOI 平板 220 nm」）
DEFAULT_W_WG_UM = 0.50
DEFAULT_H_WG_UM = 0.22

#: 工艺典型共模抑制 `CMR = 1/δ`（δ = 3% 片上 MMI 分光比失配 · 与 `sensor_case` 同口径）
#: 🔴 门禁里与 `sensor_case.cmr_from_mismatch(REFERENCING_MISMATCH_TYPICAL)` **逐位对拍**
CMR_TYPICAL_PUBLIC = 1.0 / 3.0e-2


def _pos(name: str, value: float) -> float:
    v = float(value)
    if not v > 0.0:
        raise ValueError("%s 须 > 0" % name)
    return v


def ring_heat_capacity_j_per_k(R_um: float,
                               w_wg_um: float = DEFAULT_W_WG_UM,
                               h_wg_um: float = DEFAULT_H_WG_UM) -> float:
    """微环**芯层**热容 `C = ρc_p·(2πR·w·h)`（J/K）。

    `ρc_p` **引用** `lda_l2.pm_thermal.RC_SI`（同源，不重写常量）。
    参考档（R = 10 µm · 0.5 × 0.22 µm²）⇒ `V = 6.912e-18 m³` ⇒ `C ≈ 1.127e-11 J/K`。
    """
    r = _pos("半径 R", R_um) * 1e-6
    w = _pos("波导宽", w_wg_um) * 1e-6
    h = _pos("波导高", h_wg_um) * 1e-6
    return float(RC_SI * (2.0 * math.pi * r * w * h))


def thermal_fluctuation_floor_k(temp_k: float, cap_j_per_k: float) -> float:
    """热力学温度涨落（**平衡态下限**）`δT_rms = T·√(k_B/C)`（K）。

    由正则系综能量涨落 `⟨δE²⟩ = k_B T² C_v` 与 `δE = C_v·δT` 得 `⟨δT²⟩ = k_B T²/C`。
    参考档（293.15 K · C = 1.127e-11 J/K）⇒ **0.3245 mK**。
    """
    t = _pos("温度", temp_k)
    c = _pos("热容", cap_j_per_k)
    return float(t * math.sqrt(K_B_SI / c))


def lod_temp_riu(dn_dT: float, dT_stab_k: float, cmr: float) -> float:
    """温漂项 `LOD_temp = (dn/dT)·dT_stab / CMR`（RIU）—— 与卡内 `_lod_real` 同式。"""
    dn = _pos("dn/dT", dn_dT)
    dt = _pos("温度稳定度", dT_stab_k)
    m = _pos("CMR", cmr)
    return float(dn * dt / m)


def required_dt_for_parity_k(lod_elec_riu: float, dn_dT: float, cmr: float) -> float:
    """**温控处方**：使 `LOD_temp = LOD_elec` 所需的温度稳定度 `dT = LOD_elec·CMR/(dn/dT)`。"""
    le = _pos("LOD_elec", lod_elec_riu)
    dn = _pos("dn/dT", dn_dT)
    m = _pos("CMR", cmr)
    return float(le * m / dn)


def required_cmr_for_parity(dn_dT: float, dT_stab_k: float, lod_elec_riu: float) -> float:
    """**参考通道处方**：使 `LOD_temp = LOD_elec` 所需的共模抑制 `CMR = (dn/dT)·dT/LOD_elec`。"""
    dn = _pos("dn/dT", dn_dT)
    dt = _pos("dT_stab", dT_stab_k)
    le = _pos("LOD_elec", lod_elec_riu)
    return float(dn * dt / le)


def temp_budget_report(R_um: float,
                       lod_elec_riu: float,
                       dn_dT: float,
                       dT_stab_k: float,
                       cmr: float,
                       temp_k: float = DEFAULT_TEMP_K,
                       cmr_typical: Optional[float] = None) -> Dict[str, Any]:
    """温漂预算报告（**现役点 / 两条处方 / 可行性判定** 三块一次给全）。"""
    cap = ring_heat_capacity_j_per_k(R_um)
    floor = thermal_fluctuation_floor_k(temp_k, cap)
    lod_t = lod_temp_riu(dn_dT, dT_stab_k, cmr)
    dT_req = required_dt_for_parity_k(lod_elec_riu, dn_dT, cmr)
    cmr_req_floor = required_cmr_for_parity(dn_dT, floor, lod_elec_riu)
    cmr_req_now = required_cmr_for_parity(dn_dT, dT_stab_k, lod_elec_riu)
    if cmr_typical is None:
        cmr_typical = CMR_TYPICAL_PUBLIC
    return {
        "design_point": {
            "R_um": float(R_um),
            "temp_k": float(temp_k),
            "heat_capacity_J_per_K": float(cap),
            "dT_stab_K": float(dT_stab_k),
            "CMR": float(cmr),
            "dn_dT_per_K": float(dn_dT),
            "LOD_temp_riu": float(lod_t),
            "LOD_elec_riu": float(lod_elec_riu),
            "temp_over_elec": float(lod_t / lod_elec_riu),
        },
        "requirement": {
            # 处方 A：片载温控（现役 CMR 下）
            "dT_req_K": float(dT_req),
            # 处方 B：参考通道（现役 dT 下）—— 与处方 A 的关系见 feasibility.identity
            "CMR_req_at_dT_typ": float(cmr_req_now),
            # 处方 B'：退到热力学下限时所需的 CMR
            "CMR_req_at_floor": float(cmr_req_floor),
        },
        "feasibility": {
            "thermal_floor_K": float(floor),
            # 🔴 温控缺口 = 热力学下限 / 所需稳定度（>1 ⇒ 处方 A 不可行）
            "temp_control_shortfall": float(floor / dT_req),
            "temp_control_feasible": bool(dT_req >= floor),
            "CMR_typical_public": float(cmr_typical),
            # 🔴 参考通道缺口 = 所需 CMR / 工艺典型（>1 ⇒ 需优于典型档）
            "cmr_shortfall_vs_typical": float(cmr_req_floor / cmr_typical),
            "referencing_feasible_at_typical": bool(cmr_req_floor <= cmr_typical),
            # 🔴 等价恒等式：CMR_req(δT) ≡ δT / dT_req —— 两条处方互为倒数替代
            "identity_cmr_req_times_dt_req": float(cmr_req_floor * dT_req),
            "identity_holds_on_floor": bool(
                abs(cmr_req_floor * dT_req - floor) <= 1e-12 * floor),
            "verdict": ("temp_control_infeasible_use_referencing"
                        if dT_req < floor else "temp_control_feasible"),
        },
        "note": (
            "温漂预算：LOD_temp=(dn/dT)·dT_stab/CMR。parity 条件只看 dT_stab/CMR 一个数 ⇒ "
            "温控与参考通道互为倒数替代（CMR_req·dT_req ≡ δT）。"
            "温控侧的上限是器件自身热涨落 δT=T√(k_B/C)（平衡态下限，突破需主动冷阻尼，本卡不建模）；"
            "参考侧的上限是工艺失配 CMR=1/δ（典型 1–3%）。三者都是设计预算，非实测。"
        ),
        "caliber": SENSOR_TEMP_BUDGET_CALIBER,
    }


def selfcheck_sensor_temp_budget() -> Dict[str, bool]:
    """温漂预算自检（**两条闭式已知答案 + 两条恒等式 + 绝对量级**）。"""
    c: Dict[str, bool] = {}
    R, lod_elec, dn, dt, cmr = 10.0, 1.4244685071556232e-09, 1.86e-4, 5e-3, 1.0
    rep = temp_budget_report(R, lod_elec, dn, dt, cmr)

    # ① 热容线性于 R（`2πR` 的直接后果 · 精确比例）
    c["heat_capacity_linear_in_R"] = bool(
        ring_heat_capacity_j_per_k(2.0 * R) == 2.0 * ring_heat_capacity_j_per_k(R))

    # ② 🔴 闭式已知答案：回代 ⟨δT²⟩·C ≡ k_B·T²（相对 1e-15）
    _fl = thermal_fluctuation_floor_k(DEFAULT_TEMP_K, ring_heat_capacity_j_per_k(R))
    _cap = ring_heat_capacity_j_per_k(R)
    c["fluctuation_closed_form_roundtrip"] = bool(
        abs(_fl * _fl * _cap - K_B_SI * DEFAULT_TEMP_K ** 2)
        <= 1e-15 * K_B_SI * DEFAULT_TEMP_K ** 2)

    # ③ δT ∝ T（精确比例）∧ δT ∝ C^(−1/2)（C×4 ⇒ 减半）
    c["fluctuation_linear_in_T"] = bool(
        thermal_fluctuation_floor_k(2.0 * DEFAULT_TEMP_K, _cap)
        == 2.0 * thermal_fluctuation_floor_k(DEFAULT_TEMP_K, _cap))
    c["fluctuation_inverse_sqrt_C"] = bool(
        abs(thermal_fluctuation_floor_k(DEFAULT_TEMP_K, 4.0 * _cap)
            - 0.5 * _fl) <= 1e-15 * _fl)

    # ④ 两条处方的**反解往返**：代回必须恰好 parity（相对 1e-14）
    c["dT_req_roundtrip"] = bool(
        abs(lod_temp_riu(dn, rep["requirement"]["dT_req_K"], cmr) - lod_elec)
        <= 1e-14 * lod_elec)
    c["cmr_req_roundtrip"] = bool(
        abs(lod_temp_riu(dn, rep["feasibility"]["thermal_floor_K"],
                         rep["requirement"]["CMR_req_at_floor"]) - lod_elec)
        <= 1e-14 * lod_elec)

    # ⑤ 🔴 等价恒等式：CMR_req(δT)·dT_req(CMR) ≡ δT（两条处方互为倒数替代）
    c["two_prescriptions_are_reciprocal"] = bool(
        rep["feasibility"]["identity_holds_on_floor"])
    c["identity_value_equals_floor"] = bool(
        abs(rep["feasibility"]["identity_cmr_req_times_dt_req"]
            - rep["feasibility"]["thermal_floor_K"]) <= 1e-12 * rep["feasibility"]["thermal_floor_K"])

    # ⑥ 🔴 比值不变性（老陷阱第五次）：dT×100 且 CMR×100 ⇒ LOD_temp **逐位不变**
    c["ratio_only_invariance_exact"] = bool(
        lod_temp_riu(dn, 100.0 * dt, 100.0 * cmr) == lod_temp_riu(dn, dt, cmr))

    # ⑦ 绝对量级锚点（防单位/量级错 —— ⑥ 已证比值判据在此恒失效）
    c["reference_magnitude"] = bool(
        5.0e-12 <= _cap <= 3.0e-11
        and 2.0e-4 <= _fl <= 5.0e-4
        and 5.0e-6 <= rep["requirement"]["dT_req_K"] <= 1.0e-5
        and 20.0 <= rep["feasibility"]["temp_control_shortfall"] <= 80.0)

    # ⑧ K_B 是 SI 定义值 ∧ 与其他模块逐位同源（跨模块）
    c["kb_is_si_definition_value"] = bool(K_B_SI == 1.380649e-23)
    try:
        from lda_l2.qnet_thermal_noise import KB_SI as _KB_OTHER
        c["kb_bitwise_same_as_other_module"] = bool(K_B_SI == _KB_OTHER)
    except Exception:
        c["kb_bitwise_same_as_other_module"] = False

    # ⑨ 单调：LOD_temp 随 dT_stab 升、随 CMR 降
    c["monotone_in_dT"] = bool(
        lod_temp_riu(dn, 0.1 * dt, cmr) < lod_temp_riu(dn, dt, cmr)
        < lod_temp_riu(dn, 10.0 * dt, cmr))
    c["monotone_in_cmr"] = bool(
        lod_temp_riu(dn, dt, 10.0 * cmr) < lod_temp_riu(dn, dt, cmr)
        < lod_temp_riu(dn, dt, 0.1 * cmr))

    # ⑩ 判定为**机核**而非手填：现役点温漂确实主导，且温控处方确实不可行
    c["design_point_is_temp_dominated"] = bool(rep["design_point"]["temp_over_elec"] > 1.0)
    c["temp_control_infeasible_by_margin"] = bool(
        rep["feasibility"]["temp_control_feasible"] is False
        and rep["feasibility"]["temp_control_shortfall"] > 10.0)
    c["verdict_matches_flag"] = bool(
        (rep["feasibility"]["verdict"] == "temp_control_infeasible_use_referencing")
        == (rep["feasibility"]["temp_control_feasible"] is False))

    # 反向探针：非法入参必抛
    def _raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    c["reverse_bad_R_raise"] = bool(_raises(lambda: ring_heat_capacity_j_per_k(0.0)))
    c["reverse_bad_cmr_raise"] = bool(_raises(lambda: lod_temp_riu(dn, dt, 0.0)))
    c["reverse_bad_lod_raise"] = bool(_raises(lambda: required_dt_for_parity_k(0.0, dn, cmr)))
    return c


def main() -> int:  # pragma: no cover
    checks = selfcheck_sensor_temp_budget()
    bad = [k for k, v in checks.items() if not v]
    for k, v in checks.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    rep = temp_budget_report(10.0, 1.4244685071556232e-09, 1.86e-4, 5e-3, 1.0)
    d, q, f = rep["design_point"], rep["requirement"], rep["feasibility"]
    print("\n现役点：C=%.6e J/K · LOD_temp=%.6e · LOD_elec=%.6e ⇒ 温漂/电学 = %.1f×"
          % (d["heat_capacity_J_per_K"], d["LOD_temp_riu"], d["LOD_elec_riu"], d["temp_over_elec"]))
    print("处方 A（片载温控）：需 dT_stab ≤ %.4e K = %.2f µK"
          % (q["dT_req_K"], q["dT_req_K"] * 1e6))
    print("  器件自身热涨落下限 δT = %.4e K = %.1f µK ⇒ 缺口 **%.1f×** ⇒ 可行=%s"
          % (f["thermal_floor_K"], f["thermal_floor_K"] * 1e6,
             f["temp_control_shortfall"], f["temp_control_feasible"]))
    print("处方 B（参考通道）：需 CMR ≥ %.2f（退到热力学下限时）· 工艺典型 %.2f ⇒ 缺口 %.2f× ⇒ 可行=%s"
          % (q["CMR_req_at_floor"], f["CMR_typical_public"],
             f["cmr_shortfall_vs_typical"], f["referencing_feasible_at_typical"]))
    print("恒等式 CMR_req·dT_req ≡ δT：%.6e vs %.6e（成立=%s）"
          % (f["identity_cmr_req_times_dt_req"], f["thermal_floor_K"], f["identity_holds_on_floor"]))
    print("判读：%s" % f["verdict"])
    print("自检：%s（FAIL=%s）" % ("ALL PASS" if not bad else "FAIL", bad or "无"))
    return 0 if not bad else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
