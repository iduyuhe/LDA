"""相移器 / MZI 调制器物理模型（Merge-2a · 双出口引擎物理核）。

一物两用（双出口图纸，规划 v2 纪律）：
  - 设计量出口：给定目标（相移效率 deg/mW 或 V_π）→ 扫参几何/功率（design_engine 消费）
  - 行为黑箱出口：相位/透射响应 → 链路仿真（registry 消费）

物理模型（确定性解析，均来自文献公认常数，非拟合）：
  热光相移：Δφ = 2π/λ · (dn/dT · R_th · P) · L
            dn/dT = 1.86e-4 /K（Si @1550nm，D-73 同源）
            R_th = 热阻 (K/mW)，热光效率 η_π = V_π 对应功率（功率换π相移）
  MZI 调制器（推挽双臂）：T(V) = cos²(Δφ(V)/2)
            Δφ(V) = π·V/V_π（V_π = π 相移所需电压）
            载流子色散近似：Δn_eff = -k_n·N（Si 自由载流子效应），
            V_π ∝ L/(r·n³)（电光）或由设计参数标定

诚实边界：模型为文献级解析近似（标定参数显式暴露），发动期实测校准替换。
"""
from __future__ import annotations

import math
from typing import Dict, Any

# ---- 文献公认常数 ----
DN_DT_SI_PER_K = 1.86e-4      # Si 热光系数 @1550nm（D-73 同源）
N_EFF_SI = 2.6                 # SOI 波导典型 n_eff
WL_UM = 1.55                   # 工作波长

# 热阻典型值（SOI 加热器，文献量级）
R_TH_K_PER_MW = 1.0            # 热阻 (K/mW)，工艺可标定


def phase_shift_rad(P_mw: float, L_um: float, wl_um: float = WL_UM,
                    dn_dT: float = DN_DT_SI_PER_K,
                    R_th: float = R_TH_K_PER_MW) -> float:
    """热光相移（rad）：Δφ = 2π/λ · (dn/dT · R_th · P) · L。"""
    dT = R_th * P_mw                       # K
    dn = dn_dT * dT                        # 折射率变化
    return 2.0 * math.pi / wl_um * dn * L_um


def phase_efficiency_deg_per_mW(L_um: float, wl_um: float = WL_UM,
                                dn_dT: float = DN_DT_SI_PER_K,
                                R_th: float = R_TH_K_PER_MW) -> float:
    """相移效率（deg/mW）：单位功率产生的相移（设计量指标）。"""
    return math.degrees(phase_shift_rad(1.0, L_um, wl_um, dn_dT, R_th))


def power_for_pi(L_um: float, wl_um: float = WL_UM,
                 dn_dT: float = DN_DT_SI_PER_K,
                 R_th: float = R_TH_K_PER_MW) -> float:
    """P_π（mW）：产生 π 相移所需功率（热光"半波功率"）。"""
    phi_pi = math.pi
    # Δφ = k·P → P_π = π/k
    k = 2.0 * math.pi / wl_um * dn_dT * R_th * L_um
    return phi_pi / k if k > 0 else float("inf")


def mzi_transmission(V: float, V_pi: float) -> float:
    """MZI 调制器透射（推挽）：T = cos²(π·V/(2·V_π))。"""
    x = math.pi * V / (2.0 * V_pi)
    return math.cos(x) ** 2


def vpi_electrooptic(L_um: float, g_um: float = 1.0,
                     r_pm_per_V: float = 30.0, n_eff: float = N_EFF_SI,
                     wl_um: float = WL_UM) -> float:
    """电光 V_π（V）：V_π = λ·g / (L·r·n³)（LiNbO3 r=30pm/V 典型）。

    g_um：电极间距；r_pm_per_V：Pockels 系数（pm/V）。
    确定性解析（电光调制基础公式），工艺可标定。
    """
    r_m = r_pm_per_V * 1e-12
    g_m = g_um * 1e-6
    L_m = L_um * 1e-6
    return wl_um * 1e-6 * g_m / (L_m * r_m * n_eff ** 3)


def thermo_vpi_from_pi_power(P_pi_mw: float) -> Dict[str, Any]:
    """热光调制 V_π 语义：推挽双臂各 π 相移 = 单臂 P_π·2（电等效 V_π 不可比）。

    返回热光相移器的"半波功率 P_π"（热光域等价于电光 V_π 的指标）。
    """
    return {"p_pi_mw": P_pi_mw,
            "note": "热光相移器用 P_π（半波功率 mW）作为π相移指标，"
                    "等价于电光 V_π 的功能地位（分域定义，避免混用）"}


# ---- registry 行为黑箱出口 ----
def thermo_phase_response(P_mw: float, L_um: float,
                          wl_um: float = WL_UM) -> Dict[str, float]:
    """行为黑箱：给定功率/长度 → 相移（rad）+ P_π 对照（链路仿真消费）。"""
    phi = phase_shift_rad(P_mw, L_um, wl_um)
    p_pi = power_for_pi(L_um, wl_um)
    return {"phase_rad": phi, "phase_deg": math.degrees(phi),
            "p_pi_mw": p_pi, "P_over_P_pi": P_mw / p_pi if p_pi else 0.0}


def mzi_mod_response(V: float, V_pi: float,
                     wl_um: float = WL_UM) -> Dict[str, Any]:
    """行为黑箱：MZI 调制器驱动电压 → 透射（链路仿真消费）。"""
    return {"transmission": mzi_transmission(V, V_pi),
            "T_dB": 10.0 * math.log10(max(mzi_transmission(V, V_pi), 1e-12)),
            "V_pi": V_pi, "V": V}
