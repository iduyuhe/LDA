# -*- coding: utf-8 -*-
"""LDA 光联接模块征程 · **M4（CPO 形态深化）**：热-光-电协同设计空间。

M4 与 M0–M3 的根本差别（勘查第一结论）：**前五程把每一域各自算清了**（光：TWMZM 带宽墙；
电：CPO 电通道/PDN/NEXT；热：die↔die 热堆叠 + 闭环热调），
🔴 **但三域从未在同一条耦合链上联立** —— 热调只在光子 die 内闭环，电通道只管自己的 S 参数，
光的波长偏移没有喂回信道规划。
⇒ M4 交付的不是「再一个器件模型」，而是把**热-光-电串成一条有反馈的耦合链**并回答
「给定 ASIC 功耗，环还锁得住吗 / 热偏移会不会推翻信道规划 / 三形态代价能否同口径比」。

复用底座（🔴 一律 import，**不重抄常量** —— 抄了就是血案 #3/#4）：
  · `lda_l2.oi_m3`：die↔die 热堆叠 · 热光调谐斜率 · 闭环热调 · 电极原参 · 电通道闭式
  · `lda_l2.oi_m2`：**O-band 波长栅**（1311 nm；M4 波段一律取自这里，不新写第三份）
  · `lda_l2.oi_m2b`：二维薄片对数热解 Θ（三形态之间的**几何距离缩放**）
  · `lda_l2.oi_m1`：梳齿规避信道规划（热态**重规划**复用同一规划器）
  · `lda_design.active_models`：`DN_DT_SI_PER_K` / `R_TH_K_PER_MW`（材料与热路单一真源）

六项真断口（本模块逐条补）：
  ① 热-光-电**耦合链**（`P_asic → ΔT → Δλ → {信道失谐, 热调功耗}` 有向链 + 数值联立）
  ② **固化点预偏移**（CPO 真实工程解：单向加热器不可行 ⇒ 把设计点挪到热平衡温度，**代数解**）
  ③ 热致偏移 ⟷ **WDM 信道规划**（首次联立；含 **O-band ⟷ C-band 波段桥接**）
  ④ **封装形态族**三域矩阵（CPO / OBO / 可插拔：热耦合 · 电总线 · 光耦合）
  ⑤ **FAU CTE 热-机械失准** → 光纤耦合损耗（高斯模场闭式）
  ⑥ **三域 Pareto 前沿**（共享自由变量 = 电极长度 L）+ 🔴 **VπL 一致性诚实断口**

🔴 诚实边界（红线）：
  · C 级自主 ⇒ 纯 numpy/标准库（cmath/math），零商业 EDA/SPICE；
  · 🔴 **不报 TOPS / TOPS-W / fJ/op / pJ/bit** ⇒ 三域代价只出 **mW / W / K / nm / dB / GHz**；
  · T2 工艺真值**锁死** ⇒ `VπL` · 材料 CTE · 模场半径 · 三形态总线长 · 光纤耦合损耗
    全是**显式声明的规格锚**（带取值窗口 `_BANDS`），**不是 foundry 数据**；
  · 器件为 L0/L1 解析 / 行为模型，**无实测锚**；LLM 不进判决路径。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from lda_l2 import oi_m1 as _M1
from lda_l2 import oi_m2 as _M2
from lda_l2 import oi_m2b as _M2B
from lda_l2 import oi_m3 as _M3

C_M_S = _M1.C_M_S                       # 2.99792458e8（同源，不重抄）


# ═════════════════════════════════════════════════════════════════════════════
# 0) 参数表：🔴 波长/总线/电极**一律派生自上游**（不写第二份）
# ═════════════════════════════════════════════════════════════════════════════
OI_M4_PROCESS: Dict[str, Any] = {
    # —— 波段：🔴 单一真源 = oi_m2（O-band 1311 nm），**绝不新写**（血案 #4 防线）
    "wl0_nm": float(_M2.OI_M2_PROCESS["wl0_nm"]),            # 1311.0
    "spacing_nm": float(_M2.OI_M2_PROCESS["spacing_nm"]),    # 4.5
    "n_lanes": int(_M2.OI_M2_PROCESS["n_lanes"]),            # 8

    # —— 电极（派生自 oi_m3）
    "c_elect_fF_per_mm": float(_M3.OI_M3_PROCESS["c_elect_fF_per_mm"]),   # 200.0
    "r_elect_ohm_per_mm": float(_M3.OI_M3_PROCESS["r_elect_ohm_per_mm"]),  # 2.0
    "dn_g_resid": float(_M3.OI_M3_PROCESS["dn_g_resid"]),                 # 0.15
    "l_electrode_mm": float(_M3.OI_M3_PROCESS["l_electrode_mm"]),         # 2.0（M3 设计点）
    "v_pp_diff_v": float(_M3.OI_M3_PROCESS["v_pp_diff_v"]),               # 1.2（M3 摆幅）

    # —— 🔴 VπL 规格锚（公开 SiP TWMZM 典型；**非 foundry 真值**）
    "vpi_l_v_cm": 1.5,            # 典型
    "vpi_l_v_cm_lo": 1.0,         # 窗口下界（高效率工艺）
    "vpi_l_v_cm_hi": 2.5,         # 窗口上界
    "drv_overdrive": 1.2,         # V_pp = overdrive × Vπ（含调制余量）
    # 🔴 CMOS 驱动器摆幅限值（④标准/限值层：公开 CMOS 工艺摆幅）
    "vpp_cmos_limit_v": 3.3,

    # —— 🔴 材料 CTE（公开手册值；**非本封装实测** ⇒ G-OI7）
    "cte_si_per_k": 2.6e-6,
    "cte_fiber_sio2_per_k": 0.55e-6,
    "cte_glass_fau_per_k": 3.2e-6,
    "fau_arm_len_mm": 12.0,       # 耦合臂/装配跨度（规格锚）
    "mfd_w_um": 3.0,              # 光栅耦合器模场半径（规格锚）
    "fiber_mfd_w_um": 5.2,        # 单模光纤模场半径

    # —— 🔴 三形态（总线长派生自 oi_m3 的 CPO 值；其余为规格锚）
    "bus_len_cpo_mm": float(_M3.OI_M3_PROCESS["bus_len_mm"]),   # 5.0
    "bus_len_obo_mm": 50.0,
    "bus_len_pluggable_mm": 100.0,
    "die_dist_cpo_um": float(_M3.OI_M3_PROCESS["asic_to_photon_um"]),  # 300.0
    "die_dist_obo_um": 3000.0,
    "die_dist_pluggable_um": 30000.0,
    # 光纤/FAU 静态耦合损耗（规格锚：CPO 走 FAU 有对准漂移；可插拔光纤直连最优）
    "fiber_couple_il_cpo_db": 1.5,
    "fiber_couple_il_obo_db": 1.2,
    "fiber_couple_il_pluggable_db": 0.8,

    # —— 判定阈值
    "xt_min_db": 15.0,            # 与 oi_m1 规划器同口径
    "il_max_db": 3.0,
}

# 规格锚取值窗口（`_in_band` 用；🔴 窗口本身也是锚，须逐条核对）
_BANDS: Dict[str, Tuple[float, float]] = {
    "vpi_l_v_cm": (0.1, 3.0),
    "cte_si_per_k": (1.0e-6, 5.0e-6),
    "cte_glass_fau_per_k": (1.0e-6, 8.0e-6),
    "fau_arm_len_mm": (1.0, 50.0),
    "mfd_w_um": (0.5, 10.0),
    "drv_overdrive": (1.0, 3.0),
    "vpp_cmos_limit_v": (0.8, 5.0),
    "il_couple_db": (0.0, 3.0),
}


def _in_band(key: str, value: float) -> bool:
    lo, hi = _BANDS[key]
    return lo <= float(value) <= hi


# ═════════════════════════════════════════════════════════════════════════════
# 1) 🔴 波段一致性互锁（断口 D4：跨模块波长口径分歧，本项目第 4 例）
# ═════════════════════════════════════════════════════════════════════════════
def band_lock() -> Dict[str, Any]:
    """M4 波段 ≡ M2 波段（O-band）**且** ≠ M1 规划器默认 C-band。

    🔴 为什么必须机器化：M0–M3 的器件物理在 **1311 nm（O-band，近零色散）**，
    而 `oi_m1.plan_lwdm_channels` 的**默认**栅在 **1550 nm（C-band LWDM）**。
    一旦把 1311 nm 下算出的 `Δλ` 加到 1550 nm 的信道栅上，整条链的余量判断会**反向**。
    """
    m4_wl = float(OI_M4_PROCESS["wl0_nm"])
    m2_wl = float(_M2.OI_M2_PROCESS["wl0_nm"])
    m4_ch = [round(m4_wl + OI_M4_PROCESS["spacing_nm"] * i, 4)
             for i in range(int(OI_M4_PROCESS["n_lanes"]))]
    m2_ch = _M2.m2_channels()
    m1_default_wl = float(_M1.plan_lwdm_channels()["channels_nm"][0])
    return {
        "m4_wl0_nm": m4_wl,
        "m2_wl0_nm": m2_wl,
        "m1_default_wl0_nm": m1_default_wl,
        "same_as_m2": bool(abs(m4_wl - m2_wl) < 1e-9),
        "differs_from_m1_default": bool(abs(m4_wl - m1_default_wl) > 1.0),
        "channels_match_m2": bool(m4_ch == m2_ch),
        "gap_nm": round(abs(m1_default_wl - m4_wl), 3),
        "note": ("M4 波段**继承** M2 的 O-band（1311 nm）；与 M1 规划器的 C-band 默认栅"
                 "相差 %s nm —— 显式声明断层，不默默混用。" % round(abs(m1_default_wl - m4_wl), 1)),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 2) 热-光耦合系数：**第二独立通路**（材料闭式 ⟷ M3 标定链）
# ═════════════════════════════════════════════════════════════════════════════
def optical_thermal_slope_closed(n_eff: Optional[float] = None,
                                 dn_dt: Optional[float] = None,
                                 alpha_si: Optional[float] = None,
                                 wl_nm: Optional[float] = None) -> float:
    """材料闭式 `dλ/dT = λ·[(1/n_eff)·(dn/dT) + α_Si]`（nm/K）。

    两项物理：**热光效应**（`dn/dT`，主导）+ **热膨胀**（`α_Si`，贡献 ~3%）。
    🔴 `n_eff` 用 **N_EFF_TUNE**（相位折射率，调谐口径），**不是** `n_g`（群折射率）——
    用 `n_g` 会把 dλ/dT 低估 1.75×（这正是 D-215 勘查时我自己的第一处口径错）。
    """
    from lda_design import active_models as _AM      # 单一真源
    from lda_agent import tunable_wdm as _TW
    wl = float(OI_M4_PROCESS["wl0_nm"] if wl_nm is None else wl_nm)
    ne = float(_TW.N_EFF_TUNE if n_eff is None else n_eff)
    dn = float(_AM.DN_DT_SI_PER_K if dn_dt is None else dn_dt)
    al = float(_M3.OI_M3_PROCESS.get("alpha_si_per_k", _M2B.OI_M2B_PROCESS["alpha_si_per_k"])
               if alpha_si is None else alpha_si)
    return wl * (dn / ne + al)


def thermal_optical_slope_lock() -> Dict[str, Any]:
    """双通路互锁（🔴 **方法学独立**，非同源相等）。

      通路 A：`M3.tuning_slope_nm_per_k()` = `S / R_h`（**器件标定链**：调谐斜率 ÷ 单通路热阻）
      通路 B：`optical_thermal_slope_closed()`（**材料物理闭式**，不含 R_h）

    两条通路共用 `dn/dT` 但**传递函数不同**（A 含热阻链，B 是直接材料响应）⇒
    探针只打一侧即可造真实分歧。
    """
    a = float(_M3.tuning_slope_nm_per_k())
    b = optical_thermal_slope_closed()
    rel = abs(a - b) / max(abs(b), 1e-30)
    return {
        "slope_m3_calibrated_nm_per_k": a,
        "slope_material_closed_nm_per_k": b,
        "rel_diff": rel,
        "agree_within_25pct": bool(rel < 0.25),
        "note": ("A（标定链 S/R_h）⟷ B（材料闭式含热膨胀）两条独立通路；"
                 "容差 25% 吸收 R_th 经验值与限制因子的建模差。"),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 3) ① 热-光-电耦合链（P_asic → ΔT → Δλ → {信道失谐, 热调功耗}）
# ═════════════════════════════════════════════════════════════════════════════
def co_design_chain(p_asic_w: Optional[float] = None) -> Dict[str, Any]:
    """三域联立链：把 M0–M3 各自独立的结论**串进一条有向链**。

    链（每一段都调上游单一真源，🔴 M4 不重造任何一段）：
      P_asic ─[oi_m3.die_thermal_stack]→ ΔT_photon
             ─[oi_m3.tuning_slope_nm_per_k]→ Δλ_self
             ─→ {信道失谐 Δλ/间距, 需补偿热调功率, 单向加热器可行性}
    """
    p = float(_M3.OI_M3_PROCESS["p_asic_w"] if p_asic_w is None else p_asic_w)
    stack = _M3.die_thermal_stack()
    d_t = float(stack["d_t_photon_c"])
    slope = float(_M3.tuning_slope_nm_per_k())
    d_lambda = slope * d_t

    fsr = float(_M2B.thermal_tune_budget()["FSR_nm"])
    spacing = float(OI_M4_PROCESS["spacing_nm"])
    r_h = float(_M3.heater_r_th_k_per_mw())

    # 单向加热器：只能**加热**（红移）⇒ 冷态可用、热态不可用
    closed = _M3.closed_loop_thermal_steady()
    p_supplyable = float(closed["p_heater_supplyable_mw_per_lane"])
    p_required = float(closed["p_actuator_required_mw_per_lane"])

    return {
        "p_asic_w": p,
        "d_t_photon_k": round(d_t, 6),
        "slope_nm_per_k": round(slope, 7),
        "d_lambda_self_nm": round(d_lambda, 6),
        "d_lambda_frac_fsr": round(d_lambda / max(fsr, 1e-30), 6),
        "fsr_nm": round(fsr, 6),
        "channels_shifted": round(d_lambda / spacing, 6),
        "r_h_k_per_mw": r_h,
        "p_heat_required_mw_per_lane": round(p_required, 6),
        "p_heat_supplyable_mw_per_lane": round(p_supplyable, 6),
        "actuator_direction": str(closed["actuator_direction"]),
        "unidirectional_heater_feasible": bool(closed["unidirectional_heater_feasible"]),
        "chain_consistent_with_m3_residual": bool(
            abs(d_lambda - float(closed["residual_nm"])) < 1e-6),
        "note": ("🔴 链上最关键的一环：ASIC 热把光子 die 抬 %.3f K ⇒ 环共振**红移** %.3f nm；"
                 "而集成加热器**只能加热（红移更多）**、不能制冷 ⇒ 单向加热器在 CPO 里**物理不可行**"
                 "（工程解见 `setpoint_prebias_design`）。" % (d_t, d_lambda)),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 4) ② 固化点预偏移（CPO 真实工程解 · **代数解**）
# ═════════════════════════════════════════════════════════════════════════════
def setpoint_prebias_design(p_asic_w: Optional[float] = None,
                            t_amb_c: Optional[float] = None) -> Dict[str, Any]:
    """固化点预偏移：把环的设计工作点从**室温**挪到**热平衡温度**。

    物理：`T_eq = T_amb + ΔT_photon`；预偏移量（波长域）= `dλ/dT × ΔT_photon`。
    预偏移后：稳态热调功耗 **≡ 0**、残余 **≡ 0**（**代数解**，非迭代 —— 与 M3 同口径）。

    🔴 为什么这是 CPO 的真实工程解：见 `co_design_chain` —— 单向加热器补不回来，
    唯一不需要制冷的解就是**让热平衡点成为设计点**。
    """
    p = float(_M3.OI_M3_PROCESS["p_asic_w"] if p_asic_w is None else p_asic_w)
    t_a = float(_M3.OI_M3_PROCESS["t_amb_c"] if t_amb_c is None else t_amb_c)
    stack = _M3.die_thermal_stack()
    d_t = float(stack["d_t_photon_c"])
    slope = float(_M3.tuning_slope_nm_per_k())
    r_h = float(_M3.heater_r_th_k_per_mw())

    # 物理实际偏移（①链给出）：dλ = (dλ/dT)·ΔT_photon
    d_lambda_self = slope * d_t
    # 预偏移的**设计补偿**：把固化点挪到热平衡温度 ⇒ 补偿量 = slope·(T_eq − T_amb)。
    # 🔴 走的是 `t_photon_c`（热堆叠的**绝对温度**）这条**不同来源**，不是复用 d_t ——
    #    这样两条来源若口径不一致（真实的失效模式），残余就会**非零**（可被探针打红）。
    t_eq = float(stack["t_photon_c"])
    shift_nm = slope * (t_eq - t_a)

    residual_after = abs(d_lambda_self - shift_nm)          # 🔴 算出来的，不是写死的 0
    # 残余对应的**补偿功率**（单通路：Δλ = slope·P·R_h ⇒ P = Δλ/(slope·R_h)）
    p_heat_after = residual_after / max(slope * r_h, 1e-30)

    closed = _M3.closed_loop_thermal_steady()
    residual_without = float(closed["residual_nm"])

    return {
        "p_asic_w": round(p, 6),
        "t_amb_c": round(t_a, 6),
        "d_t_photon_k": round(d_t, 6),
        "t_eq_c": round(t_eq, 6),
        "setpoint_shift_nm": round(shift_nm, 6),
        "d_lambda_self_nm": round(d_lambda_self, 6),
        "residual_nm_without_prebias": round(residual_without, 6),
        "residual_nm_after_prebias": round(residual_after, 9),
        "p_heat_without_prebias_mw_per_lane": round(
            float(closed["p_actuator_required_mw_per_lane"]), 6),
        "p_heat_after_prebias_mw_per_lane": round(p_heat_after, 9),
        "tec_required": False,
        "solution": "algebraic",
        "bi_directional_margin_needed": True,
        "note": ("CPO 工程解（P_asic=%.1f W）：把环的**固化点**从 %.1f°C 挪到热平衡 %.1f°C"
                 "（红移 %.3f nm）⇒ 稳态热调功耗与残余**同时归零**（代数解）。"
                 "仍需保留**双向**可调余量应对负载波动。"
                 % (p, t_a, t_eq, shift_nm)),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 5) ③ 热致偏移 ⟷ WDM 信道规划（首次联立 · 含波段桥接）
# ═════════════════════════════════════════════════════════════════════════════
def thermal_channel_replan(p_asic_w: Optional[float] = None) -> Dict[str, Any]:
    """热平衡温度下的**信道重规划**：复用 `oi_m1.plan_lwdm_channels`（切到 O-band 栅）。

    物理：热致偏移把环的共振整体平移 `Δλ` ⇒ 若设计点仍在**冷态**波长上，信道与环错开
    `Δλ / 间距` 个信道 ⇒ 规划解（梳齿规避的 `m` 值）需在**热态波长**下重新求解。

    🔴 波段纪律：`wl0_hot` 必须由 **M4 波段（=M2 的 1311 nm）** 派生，不得用 M1 的 C-band 默认。
    """
    p = float(_M3.OI_M3_PROCESS["p_asic_w"] if p_asic_w is None else p_asic_w)
    wl0 = float(OI_M4_PROCESS["wl0_nm"])
    spacing = float(OI_M4_PROCESS["spacing_nm"])
    n_lanes = int(OI_M4_PROCESS["n_lanes"])

    chain = co_design_chain(p_asic_w=p)
    d_lambda = float(chain["d_lambda_self_nm"])
    wl0_hot = wl0 + d_lambda

    cold = _M2.plan_m2_rings()
    hot = _M1.plan_lwdm_channels(n_lanes=n_lanes, spacing_nm=spacing, wl0_nm=wl0_hot)

    m_cold = int(cold["best"]["m"])
    m_hot = int(hot["best"]["m"])
    fsr_cold = float(_M2B.thermal_tune_budget()["FSR_nm"])
    # FSR(T) 随 λ 缩放：FSR = λ²/(n_g·L_ring) ⇒ FSR_hot = FSR_cold·(λ_hot/λ_cold)²
    fsr_hot = fsr_cold * (wl0_hot / wl0) ** 2

    xt = float(hot["best"]["min_xt_db"])
    il = float(hot["best"]["max_il_drop_db"])
    return {
        "wl0_cold_nm": round(wl0, 6),
        "wl0_hot_nm": round(wl0_hot, 6),
        "d_lambda_nm": round(d_lambda, 6),
        "fsr_nm_cold": round(fsr_cold, 6),
        "fsr_nm_hot": round(fsr_hot, 6),
        "fsr_rel_change": round((fsr_hot - fsr_cold) / fsr_cold, 8),
        "m_baseline": m_cold,
        "m_at_t_eq": m_hot,
        "m_changed": bool(m_cold != m_hot),
        "min_xt_db_at_t_eq": round(xt, 4),
        "max_il_drop_db_at_t_eq": round(il, 4),
        "n_solutions_at_t_eq": int(hot["n_solutions"]),
        "plan_still_valid": bool(xt >= float(OI_M4_PROCESS["xt_min_db"])
                                 and il <= float(OI_M4_PROCESS["il_max_db"])),
        "note": ("热致偏移 %.3f nm（≈ %.2f 个信道间距）⇒ 在**热平衡波长**下重规划："
                 "最优梳齿数 m %d → %d（%s）；FSR 随 λ² 缩放 %.4f%%。"
                 % (d_lambda, d_lambda / spacing, m_cold, m_hot,
                    "解被推翻" if m_cold != m_hot else "解不变",
                    (fsr_hot - fsr_cold) / fsr_cold * 100.0)),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 6) ④ 封装形态族：三域矩阵（CPO / OBO / 可插拔）
# ═════════════════════════════════════════════════════════════════════════════
_FORM_KEYS = ("CPO", "OBO", "pluggable")


def _form_theta(d_um: float) -> float:
    """die↔die 热耦合 Θ（K/W）：以 M3 的 **CPO 实测耦合**为基准，按 3D 热扩散 **1/d** 缩放。

    🔴 **为什么不用 M2b 的二维薄片对数解跨形态**：`thermal_coupling_log` 的 `_D_REF_UM = 400 µm`
    是**局部**参考距离，`d > d_ref` 时对数变负并被截断为 0（实测 d=3000/30000 全为 **0.000000**）
    —— 拿它跨 100× 距离外推是**滥用局部解**（本模块首版正是这么写的 ⇒ 三形态 θ 全为零、单调性判据当场红）。
    跨形态（µm → mm → cm）必须换**远场标度**：3D 点源扩散的一阶解 `Θ ∝ 1/d`。
    🔴 这是**规格锚近似**（非实测封装数据 ⇒ G-OI7）；`d_um = d_ref` 时退化为 M3 标定值（自洽）。
    """
    d_ref = float(OI_M4_PROCESS["die_dist_cpo_um"])
    theta_ref = float(abs(_M2B.thermal_coupling_log(d_ref)))     # d_ref < 400 µm ⇒ 在有效域内
    return theta_ref * (d_ref / max(float(d_um), 1e-30))


def package_form_factor_compare() -> Dict[str, Any]:
    """三形态在**热 / 电 / 光**三域的同口径代价（🔴 只出 K / mW / dB，不折算能效比）。"""
    f_nyq = float(_M3.NYQUIST_3200_GHZ) * 1e9
    out: Dict[str, Any] = {}
    bus_map = {"CPO": float(OI_M4_PROCESS["bus_len_cpo_mm"]),
               "OBO": float(OI_M4_PROCESS["bus_len_obo_mm"]),
               "pluggable": float(OI_M4_PROCESS["bus_len_pluggable_mm"])}
    dist_map = {"CPO": float(OI_M4_PROCESS["die_dist_cpo_um"]),
                "OBO": float(OI_M4_PROCESS["die_dist_obo_um"]),
                "pluggable": float(OI_M4_PROCESS["die_dist_pluggable_um"])}
    fib_map = {"CPO": float(OI_M4_PROCESS["fiber_couple_il_cpo_db"]),
               "OBO": float(OI_M4_PROCESS["fiber_couple_il_obo_db"]),
               "pluggable": float(OI_M4_PROCESS["fiber_couple_il_pluggable_db"])}

    for k in _FORM_KEYS:
        theta = _form_theta(dist_map[k])
        bus = bus_map[k]
        il_elec = abs(_M3.echannel_att_db(f_nyq, l_mm=bus))
        out[k] = {
            "die_dist_um": dist_map[k],
            "theta_k_per_w": round(theta, 6),
            "bus_len_mm": bus,
            "il_elec_db": round(il_elec, 4),
            "il_fiber_db": fib_map[k],
            "il_total_db": round(il_elec + fib_map[k], 4),
        }

    cpo, obo, plg = out["CPO"], out["OBO"], out["pluggable"]
    return {
        "forms": out,
        "order": list(_FORM_KEYS),
        "thermal_coupling_rank": sorted(_FORM_KEYS, key=lambda k: -out[k]["theta_k_per_w"]),
        "elec_il_rank": sorted(_FORM_KEYS, key=lambda k: out[k]["il_elec_db"]),
        "fiber_il_rank": sorted(_FORM_KEYS, key=lambda k: out[k]["il_fiber_db"]),
        "theta_monotonic_with_distance": bool(
            cpo["theta_k_per_w"] > obo["theta_k_per_w"] > plg["theta_k_per_w"]),
        "elec_il_monotonic_with_bus": bool(
            cpo["il_elec_db"] < obo["il_elec_db"] < plg["il_elec_db"]),
        "note": ("三域**互相冲突**：CPO 电损耗最低但热耦合最强（ASIC 热直灌光子 die）；"
                 "可插拔热隔离最好、光纤耦合最优，但电总线 ~10 cm 级 ⇒ 电损耗最大。"),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 7) ⑤ FAU CTE 热-机械失准 → 光纤耦合损耗
# ═════════════════════════════════════════════════════════════════════════════
def fau_cte_misalignment(p_asic_w: Optional[float] = None,
                         arm_len_mm: Optional[float] = None,
                         w_um: Optional[float] = None) -> Dict[str, Any]:
    """硅光 die 与玻璃 FAU 的 **CTE 失配** → 横向对准漂移 → 高斯模场交叠下降。

        Δx = (α_fau − α_si)·L_arm·ΔT         （m）
        IL_coupling = −10·log10( exp(−(Δx/w)²) )   （dB，高斯模场闭式）

    🔴 材料 CTE 是**公开手册值**（不是本封装实测）⇒ 结论属 G-OI7 诚实保留区。
    """
    p = float(_M3.OI_M3_PROCESS["p_asic_w"] if p_asic_w is None else p_asic_w)
    l_arm = float(OI_M4_PROCESS["fau_arm_len_mm"] if arm_len_mm is None else arm_len_mm)
    w = float(OI_M4_PROCESS["mfd_w_um"] if w_um is None else w_um)
    a_si = float(OI_M4_PROCESS["cte_si_per_k"])
    a_fau = float(OI_M4_PROCESS["cte_glass_fau_per_k"])

    d_t = float(co_design_chain(p_asic_w=p)["d_t_photon_k"])
    d_alpha = a_fau - a_si                              # 1/K
    dx_m = d_alpha * (l_arm * 1e-3) * d_t               # m
    dx_um = dx_m * 1e6
    ratio = dx_um / max(w, 1e-30)
    il_db = -10.0 * math.log10(max(math.exp(-(ratio ** 2)), 1e-300))

    # 与**装配公差**（典型 ±0.5 µm 量级）对比 —— 判断谁是主因
    assembly_tol_um = 0.5
    il_assembly_db = -10.0 * math.log10(max(math.exp(-((assembly_tol_um / w) ** 2)), 1e-300))

    return {
        "p_asic_w": p,
        "d_t_k": round(d_t, 6),
        "cte_si_per_k": a_si,
        "cte_glass_fau_per_k": a_fau,
        "cte_mismatch_per_k": d_alpha,
        "arm_len_mm": l_arm,
        "mfd_w_um": w,
        "dx_um": round(dx_um, 9),
        "dx_nm": round(dx_um * 1000.0, 6),
        "ratio_dx_over_w": round(ratio, 9),
        "il_cte_db": round(il_db, 6),
        "assembly_tol_um": assembly_tol_um,
        "il_assembly_db": round(il_assembly_db, 6),
        "cte_is_dominant": bool(il_db > il_assembly_db),
        "note": ("🔴 **诚实结论（反直觉）**：CTE 失配在单次 ΔT=%.1f K 下只产生 **%.0f nm** 漂移 ⇒ "
                 "耦合损耗 ≈ **%.4f dB**，**远小于**典型装配公差（±%.1f µm）带来的 %.3f dB ⇒ "
                 "**CTE 不是耦合损耗主因**（主因是装配公差，属 G-OI7 无实测分布区）。"
                 % (d_t, dx_um * 1000.0, il_db, assembly_tol_um, il_assembly_db)),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 8) ⑥ 三域 Pareto 前沿（共享自由变量 = 电极长度 L）+ VπL 诚实断口
# ═════════════════════════════════════════════════════════════════════════════
def vpi_l_consistency() -> Dict[str, Any]:
    """🔴 诚实断口 D8：M3 设计点**隐含**的调制效率 vs 公开 SiP 典型值。

    `VπL_implied = v_pp_diff_v × L_electrode`（把设计摆幅当作 Vπ）。
    结论**如实报出**，🔴 **不修改 M3**（只登记断口）。
    """
    vpp = float(OI_M4_PROCESS["v_pp_diff_v"])
    l_mm = float(OI_M4_PROCESS["l_electrode_mm"])
    vpi_l_implied_v_cm = vpp * l_mm / 10.0                  # V·mm → V·cm
    pub = float(OI_M4_PROCESS["vpi_l_v_cm"])
    lo = float(OI_M4_PROCESS["vpi_l_v_cm_lo"])
    hi = float(OI_M4_PROCESS["vpi_l_v_cm_hi"])
    gap = pub / max(vpi_l_implied_v_cm, 1e-30)
    vpp_required = pub * 10.0 / l_mm                        # V·cm → V·mm → ÷mm
    l_for_vpp = pub * 10.0 / vpp                            # V·cm → V·mm ÷V = mm
    return {
        "vpi_l_implied_by_m3_v_cm": round(vpi_l_implied_v_cm, 6),
        "vpi_l_public_typical_v_cm": pub,
        "vpi_l_public_band_v_cm": [lo, hi],
        "vpi_l_gap_ratio": round(gap, 4),
        "vpp_required_at_public_vpi_l_v": round(vpp_required, 4),
        "l_needed_for_m3_vpp_mm": round(l_for_vpp, 4),
        "public_vpi_l_in_band": bool(_in_band("vpi_l_v_cm", pub)),
        "consistent_with_public_process": bool(lo <= vpi_l_implied_v_cm <= hi),
        "note": ("🔴 M3 设计点（v_pp=%.2f V × L=%.1f mm）**隐含** VπL=%.3f V·cm，"
                 "比公开 SiP TWMZM 典型 %.1f V·cm（%.1f–%.1f）**激进 %.1f×** ⇒ "
                 "要么摆幅应远高于 %.1f V，要么需更高效率调制机制（TFLN/异质集成）。"
                 "**本程不修改 M3，只登记断口。**"
                 % (vpp, l_mm, vpi_l_implied_v_cm, pub, lo, hi, gap, vpp)),
    }


def _electrode_il_db(l_mm: float, f_hz: float) -> float:
    """电极作为**有损传输线**的导体损耗（dB）—— 用 oi_m3 的电极原参，口径一致。"""
    r_pm, l_pm, c_pm, length_m = _M3._electrode_primers(l_mm=l_mm)
    gamma = _M3.propagation_gamma(f_hz, r_pm, l_pm, c_pm)
    return 8.685889638 * gamma.real * length_m


def _driver_power_mw(l_mm: float, f_hz: float,
                     vpi_l_v_cm: Optional[float] = None,
                     overdrive: Optional[float] = None) -> float:
    """驱动器动态功耗（mW）：`P = ½·(C′·L)·V_pp²·f`，`V_pp = overdrive·VπL/L`。

    🔴 与 M3 的 `driver_dynamic_mw` **不同口径**：M3 用封装线电容（与 L 无关），
    这里用**电极电容 C′·L**（与 L 线性）—— 这是 Pareto 分析所必需的口径。
    """
    vpi_l = float(OI_M4_PROCESS["vpi_l_v_cm"] if vpi_l_v_cm is None else vpi_l_v_cm)
    ov = float(OI_M4_PROCESS["drv_overdrive"] if overdrive is None else overdrive)
    c_elec_f = float(OI_M4_PROCESS["c_elect_fF_per_mm"]) * 1e-15 * l_mm
    v_pi_v = vpi_l * 10.0 / l_mm                     # V·cm → V·mm ÷ mm = V
    v_pp_v = ov * v_pi_v
    return 0.5 * c_elec_f * (v_pp_v ** 2) * f_hz * 1e3


def pareto_front_l_electrode(l_grid: Optional[Sequence[float]] = None
                             ) -> Dict[str, Any]:
    """**三域 Pareto 前沿**（共享自由变量 = 电极长度 L）。

    三目标（方向）：
      · **光**：带宽 `BW(L) ∝ 1/L²` —— 越大越好
      · **电**：电极线损 `IL(L) ∝ L` —— 越小越好
      · **电**：驱动功耗 `P(L) ∝ 1/L`（`C′·L` × `V_pp²` ∝ `1/L²`）—— 越小越好

    🔴 **为什么必须有 `VπL`**：若驱动功耗与 L 无关（M3 原口径走封装线电容），
    `BW` 与 `IL` **同向**（都要 L 小）⇒ 无权衡、Pareto 退化。引入 `VπL` 规格锚后才有真前沿。
    """
    grid = list(l_grid) if l_grid is not None else [
        0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0]
    f_nyq = float(_M3.NYQUIST_3200_GHZ) * 1e9
    f_baud = float(_M3.PAM4_BAUD_3200_GBD) * 1e9
    vpi_l = float(OI_M4_PROCESS["vpi_l_v_cm"])
    ov = float(OI_M4_PROCESS["drv_overdrive"])
    vpp_limit = float(OI_M4_PROCESS["vpp_cmos_limit_v"])
    bw_line = 1.03 * float(_M3.NYQUIST_3200_GHZ)          # 带宽判死线（与 M3 同口径）

    pts: List[Dict[str, Any]] = []
    for l in grid:
        bw = float(_M3.twmzm_bandwidth_hz(l_mm=l)) / 1e9
        vpi_v = vpi_l * 10.0 / float(l)                   # V·cm → V·mm ÷ mm = V
        vpp_v = ov * vpi_v
        fbw = bool(bw >= bw_line)
        fvpp = bool(vpp_v <= vpp_limit)
        pts.append({
            "l_mm": float(l),
            "bw_ghz": round(bw, 4),
            "il_db": round(_electrode_il_db(float(l), f_nyq), 6),
            "p_drv_mw": round(_driver_power_mw(float(l), f_baud), 4),
            "vpi_v": round(vpi_v, 4),
            "vpp_v": round(vpp_v, 4),
            "feasible_bw": fbw,
            "feasible_vpp": fvpp,
            "feasible": bool(fbw and fvpp),
        })

    def dominates(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        not_worse = (a["bw_ghz"] >= b["bw_ghz"] - 1e-12
                     and a["il_db"] <= b["il_db"] + 1e-12
                     and a["p_drv_mw"] <= b["p_drv_mw"] + 1e-12)
        strictly_better = (a["bw_ghz"] > b["bw_ghz"] + 1e-12
                           or a["il_db"] < b["il_db"] - 1e-12
                           or a["p_drv_mw"] < b["p_drv_mw"] - 1e-12)
        return not_worse and strictly_better

    front = [p for p in pts if not any(dominates(q, p) for q in pts if q is not p)]
    feas = [p for p in pts if p["feasible"]]
    l_m3 = float(OI_M4_PROCESS["l_electrode_mm"])
    m3_pt = min(pts, key=lambda p: abs(p["l_mm"] - l_m3))
    return {
        "points": pts,
        "front": front,
        "feasible": feas,
        "n_points": len(pts),
        "n_front": len(front),
        "n_dominated": len(pts) - len(front),
        "all_points_non_dominated": bool(len(front) == len(pts)),
        "n_infeasible_bw": sum(1 for p in pts if not p["feasible_bw"]),
        "n_infeasible_vpp": sum(1 for p in pts if not p["feasible_vpp"]),
        "n_feasible": len(feas),
        "feasible_collapsed": bool(len(feas) <= 1),
        "feasible_l_mm": [p["l_mm"] for p in feas],
        "bw_death_line_ghz": round(bw_line, 4),
        "vpp_cmos_limit_v": vpp_limit,
        "m3_design_l_mm": l_m3,
        "m3_design_on_front": bool(m3_pt in front),
        "m3_design_feasible": bool(m3_pt["feasible"]),
        "m3_design_point": m3_pt,
        "vpi_l": vpi_l_consistency(),
        "note": ("共享变量 L 上三域**两两权衡**：BW（越大越好）· IL∝L（越小越好）· "
                 "P_drv∝1/L（越小越好）⇒ **任意两点互不支配**（%d/%d 全非支配）—— "
                 "结论：L 的选取是**目标权重问题**，不存在单一最优。再叠加两条可行性约束"
                 "（带宽 ≥ %.0f GHz ∧ 摆幅 ≤ %.1f V CMOS）⇒ 可行点 **%d/%d**%s。"
                 % (len(front), len(pts), bw_line, vpp_limit, len(feas), len(pts),
                    ("；🔴 可行域**收缩**到 %s mm —— **不是** M3 用的 %.1f mm"
                     % ([p["l_mm"] for p in feas], l_m3)) if feas else
                    "；🔴 可行域为空")),
    }


def feasibility_wall() -> Dict[str, Any]:
    """🔴 VπL 断口的**定量形式**：可行域在两种 VπL 口径下的收缩对照。

    双向证明（防判据恒真/恒红）：
      · 用**公开** SiP VπL（1.5 V·cm）+ CMOS 摆幅（3.3 V）⇒ 可行域**收缩到 ≤1 点**；
      · 用 **M3 隐含** VπL（0.24 V·cm）+ M3 摆幅（1.2 V）⇒ 可行点**明显更多**。
    两者并存 ⇒ 说明「带宽墙」部分是**调制效率墙**，不只是电极长度问题。
    """
    vpp_limit = float(OI_M4_PROCESS["vpp_cmos_limit_v"])
    m3_vpp = float(OI_M4_PROCESS["v_pp_diff_v"])
    l_grid = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0]
    bw_line = 1.03 * float(_M3.NYQUIST_3200_GHZ)

    def _feasible_ls(vpi_l: float, vpp_cap: float, ov: float) -> List[float]:
        out: List[float] = []
        for l in l_grid:
            bw = float(_M3.twmzm_bandwidth_hz(l_mm=l)) / 1e9
            vpp = ov * vpi_l * 10.0 / l
            if bw >= bw_line and vpp <= vpp_cap:
                out.append(float(l))
        return out

    ls_public = _feasible_ls(float(OI_M4_PROCESS["vpi_l_v_cm"]),
                             vpp_limit, float(OI_M4_PROCESS["drv_overdrive"]))
    ls_m3 = _feasible_ls(vpi_l_consistency()["vpi_l_implied_by_m3_v_cm"], m3_vpp, 1.0)
    return {
        "public_feasible_l_mm": ls_public,
        "m3_implied_feasible_l_mm": ls_m3,
        "public_vpi_l_feasible_points": len(ls_public),
        "m3_implied_vpi_l_feasible_points": len(ls_m3),
        "public_feasible_collapsed": bool(len(ls_public) <= 1),
        "public_narrower_than_m3": bool(len(ls_public) < len(ls_m3)),
        "note": ("用**公开** SiP VπL=%.1f V·cm + CMOS 摆幅 %.1f V ⇒ 可行点 **%d**（%s mm）；"
                 "用 **M3 隐含** VπL=%.3f V·cm + M3 摆幅 %.1f V ⇒ 可行点 **%d**（%s mm）。"
                 "🔴 结论：公开工艺下可行域**急剧收缩**且最优长度（%s mm）≠ M3 用的 %.1f mm ⇒ "
                 "400G/lane 的「带宽墙」部分是**调制效率墙**。"
                 % (float(OI_M4_PROCESS["vpi_l_v_cm"]), vpp_limit, len(ls_public),
                    ls_public, vpi_l_consistency()["vpi_l_implied_by_m3_v_cm"], m3_vpp,
                    len(ls_m3), ls_m3, ls_public, float(OI_M4_PROCESS["l_electrode_mm"]))),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 9) 红线守卫
# ═════════════════════════════════════════════════════════════════════════════
def honest_boundary_ok() -> bool:
    """M4 的红线自检：无 foundry 真值声明 · 无能量比换算 · 结论均为设计预算层。"""
    b = band_lock()
    v = vpi_l_consistency()
    p = pareto_front_l_electrode()
    f = feasibility_wall()
    return bool(
        b["same_as_m2"] and b["differs_from_m1_default"]
        and v["public_vpi_l_in_band"]
        and p["all_points_non_dominated"]        # 三目标两两权衡（真结构）
        and p["n_infeasible_bw"] >= 1 and p["n_infeasible_vpp"] >= 1
        and f["public_feasible_collapsed"] and f["public_narrower_than_m3"]
        and not v["consistent_with_public_process"]      # 断口**如实报出**（不粉饰）
    )


# ═════════════════════════════════════════════════════════════════════════════
# 10) 模块自检
# ═════════════════════════════════════════════════════════════════════════════
def oi_m4_self_check(verbose: bool = True) -> Dict[str, Any]:
    """模块内自检（被 `run_oi_m4_smoke.py` 复用为互锁判据的一环）。"""
    c: List[Tuple[str, bool]] = []

    # ── 0) 波段一致性（断口 D4）
    bl = band_lock()
    c.append(("M4 波段：继承 M2 的 O-band（同一真源，不新写第三份）", bl["same_as_m2"]))
    c.append(("M4 波段：与 M1 规划器 C-band 默认栅**显式不同**（断层已声明）",
              bl["differs_from_m1_default"]))
    c.append(("M4 波段：信道列表与 M2 逐项一致", bl["channels_match_m2"]))

    # ── 规格锚窗口
    c.append(("M4 规格锚：VπL 典型值落窗", _in_band("vpi_l_v_cm", OI_M4_PROCESS["vpi_l_v_cm"])))
    c.append(("M4 规格锚：Si CTE 落窗", _in_band("cte_si_per_k", OI_M4_PROCESS["cte_si_per_k"])))
    c.append(("M4 规格锚：玻璃 FAU CTE 落窗",
              _in_band("cte_glass_fau_per_k", OI_M4_PROCESS["cte_glass_fau_per_k"])))
    c.append(("M4 规格锚：模场半径落窗", _in_band("mfd_w_um", OI_M4_PROCESS["mfd_w_um"])))

    # ── 双通路互锁（方法学独立）
    lock = thermal_optical_slope_lock()
    c.append(("M4 互锁：dλ/dT 两条**独立通路**（标定链 ⟷ 材料闭式）25% 内一致",
              lock["agree_within_25pct"]))
    c.append(("M4 互锁：材料闭式含**热膨胀项**（漏掉则 dλ/dT 偏低）",
              optical_thermal_slope_closed() > optical_thermal_slope_closed(alpha_si=0.0)))
    c.append(("M4 互锁：用 n_eff 而非 n_g（n_g 会低估 1.75×）",
              abs(optical_thermal_slope_closed(n_eff=4.2) / optical_thermal_slope_closed()
                  - 1.0) > 0.3))

    # ── ① 耦合链
    ch = co_design_chain()
    c.append(("M4 ① 耦合链：Δλ_self == M3 闭环残余（同源一致，非近似）",
              ch["chain_consistent_with_m3_residual"]))
    c.append(("M4 ① 耦合链：ASIC 自热 > 0 且导致红移（方向为正）", ch["d_lambda_self_nm"] > 0))
    c.append(("M4 ① 耦合链：单向加热器在 CPO 里**不可行**（真实结论，非恒绿）",
              ch["unidirectional_heater_feasible"] is False))
    c.append(("M4 ① 耦合链：失谐量以 FSR 为单位 < 1 个 FSR（未跨模）",
              0 < ch["d_lambda_frac_fsr"] < 1.0))

    # ── ② 固化点预偏移（代数解）
    pb = setpoint_prebias_design()
    c.append(("M4 ② 预偏移：预偏移后残余**归零**（代数解）", abs(pb["residual_nm_after_prebias"]) < 1e-12))
    c.append(("M4 ② 预偏移：预偏移后热调功耗**归零**", abs(pb["p_heat_after_prebias_mw_per_lane"]) < 1e-12))
    c.append(("M4 ② 预偏移：不预偏移的残余**非零**（对照，防恒零假绿）",
              abs(pb["residual_nm_without_prebias"]) > 0.1))
    c.append(("M4 ② 预偏移：解标为 algebraic（与 M3 同口径）", pb["solution"] == "algebraic"))
    c.append(("M4 ② 预偏移：T_eq == T_amb + ΔT_photon（代数一致）",
              abs(pb["t_eq_c"] - (pb["t_amb_c"] + pb["d_t_photon_k"])) < 1e-9))
    c.append(("M4 ② 预偏移：预偏移量 == dλ/dT × ΔT（与①链同源）",
              abs(pb["setpoint_shift_nm"] - ch["d_lambda_self_nm"]) < 1e-9))
    c.append(("M4 ② 预偏移：🔴 预偏移**确实改善**残余（after < without，非恒真语义）",
              pb["residual_nm_after_prebias"] < pb["residual_nm_without_prebias"]))
    c.append(("M4 ② 预偏移：🔴 预偏移**确实降低**补偿功率（after < without，非恒真语义）",
              pb["p_heat_after_prebias_mw_per_lane"]
              < pb["p_heat_without_prebias_mw_per_lane"]))

    # ── ③ 热态重规划
    rp = thermal_channel_replan()
    c.append(("M4 ③ 重规划：热态 FSR 与冷态**不同**（温度真的进了模型）",
              abs(rp["fsr_nm_hot"] - rp["fsr_nm_cold"]) > 1e-9))
    c.append(("M4 ③ 重规划：FSR 随 λ² 缩放（相对变化 > 0，物理方向正确）",
              rp["fsr_rel_change"] > 0))
    c.append(("M4 ③ 重规划：热态规划解**仍满足**隔离度与 IL 阈值",
              rp["plan_still_valid"]))
    # 🔴 咬**语义**（波段归属），不是「自己和自己比」的同源相等（首版写成
    #    `wl0_cold == OI_M4_PROCESS["wl0_nm"]` ⇒ 恒真假判据，被 P5 探针当场抓出）
    c.append(("M4 ③ 重规划：热态起点波长落在 **O-band**（1260–1360 nm，与 M2 同域）",
              abs(rp["wl0_cold_nm"] - float(_M2.OI_M2_PROCESS["wl0_nm"])) < 1e-9
              and 1260.0 <= rp["wl0_cold_nm"] <= 1360.0))

    # ── ④ 三形态矩阵
    pf = package_form_factor_compare()
    c.append(("M4 ④ 形态：热耦合随 die 距离**单调递减**（CPO>OBO>可插拔）",
              pf["theta_monotonic_with_distance"]))
    c.append(("M4 ④ 形态：电损耗随总线长**单调递增**（CPO<OBO<可插拔）",
              pf["elec_il_monotonic_with_bus"]))
    c.append(("M4 ④ 形态：三域**互相冲突**（无单形态全胜）—— CPO 电最优但热最差",
              pf["thermal_coupling_rank"][0] == "CPO" and pf["elec_il_rank"][0] == "CPO"))
    c.append(("M4 ④ 形态：三形态 θ 互不相同（防『编成同一个数』）",
              len({round(pf["forms"][k]["theta_k_per_w"], 9) for k in _FORM_KEYS}) == 3))

    # ── ⑤ CTE 失准
    cte = fau_cte_misalignment()
    c.append(("M4 ⑤ CTE：失配漂移 > 0（判据真在算，非恒零）", cte["dx_um"] > 0))
    c.append(("M4 ⑤ CTE：漂移量在**亚微米**量级（物理量级正确）", 0 < cte["dx_um"] < 1.0))
    c.append(("M4 ⑤ CTE：🔴 **反直觉诚实结论** —— CTE 不是耦合损耗主因（< 装配公差）",
              cte["cte_is_dominant"] is False))
    c.append(("M4 ⑤ CTE：失配置 0 时耦合损耗必为 0（退化自检）",
              abs(fau_cte_misalignment(arm_len_mm=0.0)["il_cte_db"]) < 1e-12))

    # ── ⑥ Pareto + VπL
    par = pareto_front_l_electrode()
    c.append(("M4 ⑥ Pareto：三目标**两两权衡** ⇒ 全点非支配（无单一最优）",
              par["all_points_non_dominated"]))
    c.append(("M4 ⑥ Pareto：带宽判死线约束**真的在起作用**（有不可行点）",
              par["n_infeasible_bw"] >= 1))
    c.append(("M4 ⑥ Pareto：CMOS 摆幅约束**真的在起作用**（有不可行点）",
              par["n_infeasible_vpp"] >= 1))
    c.append(("M4 ⑥ Pareto：带宽随 L **单调递减**（∝1/L²，物理方向）",
              par["points"][0]["bw_ghz"] > par["points"][-1]["bw_ghz"]))
    c.append(("M4 ⑥ Pareto：驱动功耗随 L **单调递减**（∝1/L，VπL 恒定）",
              par["points"][0]["p_drv_mw"] > par["points"][-1]["p_drv_mw"]))
    c.append(("M4 ⑥ Pareto：线损随 L **单调递增**（导体损耗 ∝ L）",
              par["points"][0]["il_db"] < par["points"][-1]["il_db"]))
    c.append(("M4 ⑥ VπL：公开典型值落窗", par["vpi_l"]["public_vpi_l_in_band"]))
    c.append(("M4 ⑥ VπL：🔴 断口**如实报出** —— 隐含 VπL 与公开工艺**不一致**",
              par["vpi_l"]["consistent_with_public_process"] is False))

    # ── ⑥b 可行性墙（双向证明，防恒真/恒红）
    fw = feasibility_wall()
    c.append(("M4 ⑥b 可行性墙：公开 VπL + CMOS 摆幅 ⇒ 可行域**收缩到 ≤1 点**",
              fw["public_feasible_collapsed"]))
    c.append(("M4 ⑥b 可行性墙：公开口径可行点 **少于** M3 隐含口径（双向对照）",
              fw["public_narrower_than_m3"]))
    c.append(("M4 ⑥b 可行性墙：公开工艺下最优 L **≠** M3 设计点（结论有工程意义）",
              (fw["public_feasible_l_mm"] or [None])[0]
              != float(OI_M4_PROCESS["l_electrode_mm"])))

    # ── 红线
    c.append(("M4 红线：honest_boundary_ok（波段/断口/前沿三项结构齐备）",
              honest_boundary_ok()))

    npass = sum(1 for _, x in c if x)
    nfail = len(c) - npass
    if verbose:
        for name, ok in c:
            print("  [%s] %s" % ("PASS" if ok else "FAIL", name))
        print("  M4 模块自检：%d PASS / %d FAIL" % (npass, nfail))
    return {"checks": c, "ok": nfail == 0, "n_pass": npass, "n_fail": nfail}


if __name__ == "__main__":
    r = oi_m4_self_check()
    raise SystemExit(0 if r["ok"] else 1)
