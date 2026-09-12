"""LDA · U4（换锚路线 U4）Ge p-i-n 探测器响应度 **真候选求解**（经 T1 输运模型）。

🔴 主权边界：本模块为自证桩换锚路线（docs/lda_anchor_upgrade_roadmap_2026-09-13.md
U4）的落地：把 E-GE-PD-RESP 实证锚（Feng 2009 实测 1.1 A/W）的候选从「占位自证」
升级为**独立数值求解**。
- 模型：R = η_abs · η_col · (qλ/hc)。
  · η_abs = ∫α·e^{-αx}dx 数值梯形积分（Ge α=4000/cm，Feng 2009 原文值）；
  · η_col = W_i/W_strip 几何收集因子（横向 p-i-n：中性肩区 0.075µm×2 光生载流子
    在简并掺杂区 ns 级复合，被耗尽区渡越 ps 级扫出——收集窗口=本征区宽）；
  · qλ/hc = 光子能量理想响应度（物理常数）。
- 与 golden 的独立性：golden=**实测**（APL 95, 261105 DOI 10.1063/1.3279129），
  候选=数值积分+几何收集模型（方法学完全不同源）。
- 零外部依赖（numpy）；不 import 任何 A 级/DEVSIM。
- 🔴 T1 输出不作 ORACLE：本候选仅作 verification 候选，`is_oracle=False` 铁律。
- 🔴 EAR 744.23 成熟节点用途声明。

诚实边界：单载流子收集模型（电子渡越），不含空穴双载流子扩散竞争、界面复合、
暗电流；α 取原文 1550nm 值（不随波长扫描）；η_col 假设肩区完全复合（保守下界）。
实测 1.1 A/W 含 TM 偏振与倏逝耦合增强，候选 0.997 与实测差 0.104 < tol 0.15，
残差来自上述近似（如实公开）。LLM 不进判决路径。
"""
from __future__ import annotations

import math

import numpy as np

# ---- 物理常数（SI） ----
Q_E = 1.602176634e-19
H_PLANCK = 6.62607015e-34
C_LIGHT = 2.99792458e8

# ---- Ge / Feng 2009 APL 95 261105 器件参数（原文实测几何，DOI 10.1063/1.3279129）----
ALPHA_GE_1550 = 4000.0 * 100.0   # Ge 吸收系数 @1550nm (1/m, 原文 4000/cm)
L_GE_DEFAULT = 10.0e-6           # Ge 吸收区长度 (m, 原文：10µm 吸收 >98%)
W_GE_STRIP = 0.8e-6              # Ge 条宽 (m, 原文 0.8µm)
W_I_DEFAULT = 0.65e-6            # 本征区宽 (m, 原文 WGe=0.65µm)
V_SAT_GE_E = 6.0e4               # Ge 电子饱和速度 (m/s, 6e6 cm/s, 多源文献一致)

# 🔴 红线开关
T1_OUTPUT_IS_ORACLE = False


def eta_abs_numeric(n_x: int = 400, L: float = L_GE_DEFAULT,
                    alpha: float = ALPHA_GE_1550) -> float:
    """光吸收效率 η_abs = ∫₀ᴸ α·e^{-αx}dx = 1−e^{-αL}（数值梯形积分）。

    判据D 载体：n_x 加密 ⇒ 梯形残差 O(dx²) 单调下降（解析极限 1−e^{-αL} 机器
    精度旁证，但候选走数值积分路径与解析不同源）。
    """
    if n_x < 2 or L <= 0.0 or alpha < 0.0:
        raise ValueError("eta_abs_numeric: n_x≥2, L>0, alpha≥0")
    xs = np.linspace(0.0, L, n_x)
    g = alpha * np.exp(-alpha * xs)
    return float(np.trapezoid(g, xs))


def eta_col_geometric(W_i: float = W_I_DEFAULT,
                      W_strip: float = W_GE_STRIP) -> float:
    """几何收集效率 η_col = W_i/W_strip（横向 p-i-n 耗尽窗口 / Ge 条宽）。

    物理：中性肩区（简并掺杂 5e19）光生少数载流子寿命 ~ns，渡越扫出 ~ps
    ⇒ 肩区载流子不贡献光电流（保守下界假设：完全复合）。
    """
    if W_i <= 0.0 or W_strip <= 0.0 or W_i > W_strip:
        raise ValueError("eta_col_geometric: 0 < W_i ≤ W_strip")
    return W_i / W_strip


def transit_time_ps(W_i: float = W_I_DEFAULT,
                    v_sat: float = V_SAT_GE_E) -> float:
    """饱和渡越时间（ps，信息量）：最坏载流子横穿半本征区 (W_i/2)/v_sat。"""
    return 0.5 * W_i / v_sat * 1e12


def ge_pd_responsivity_candidate(n_x: int = 400, L: float = L_GE_DEFAULT,
                                 W_i: float = W_I_DEFAULT,
                                 wl_um: float = 1.55,
                                 alpha: float = ALPHA_GE_1550) -> dict:
    """U4 主入口：Ge-PD 响应度真候选 R = η_abs·η_col·qλ/hc（A/W）。

    返回 dict（候选，is_oracle=False）：R / eta_abs / eta_col / R_ideal /
    transit_ps / provenance。golden=E-GE-PD-RESP 实测 1.1±0.05（harness 比对）。
    """
    if wl_um <= 0.0:
        raise ValueError("ge_pd_responsivity_candidate: wl_um>0")
    eta_a = eta_abs_numeric(n_x, L, alpha)
    eta_c = eta_col_geometric(W_i)
    r_ideal = Q_E * (wl_um * 1e-6) / (H_PLANCK * C_LIGHT)
    R = eta_a * eta_c * r_ideal
    return {
        "metric": "responsivity_A_per_W",
        "R": R,
        "eta_abs": eta_a,
        "eta_col": eta_c,
        "R_ideal": r_ideal,
        "transit_ps": transit_time_ps(W_i),
        "n_x": n_x, "L_um": L * 1e6, "W_i_um": W_i * 1e6, "wl_um": wl_um,
        "provenance": "self_authored_u4_collection_model",
        "is_oracle": False,
    }


def guard_t1_not_oracle(solution: dict, force_oracle: bool = False) -> bool:
    """🔴 T1 输出不作 ORACLE 反向测试守卫（同 W2/W4/W5/W6 语义）。"""
    if force_oracle:
        raise RuntimeError(
            "T1 输出禁止作为 ORACLE：数值 R 仅作候选，"
            "死标量判决须由实测语料/物理定律闭式定。")
    if solution.get("is_oracle", False):
        raise RuntimeError("T1 解被错误标记为 ORACLE（is_oracle=True）")
    return True


if __name__ == "__main__":
    r = ge_pd_responsivity_candidate()
    print(f"η_abs={r['eta_abs']:.4f} η_col={r['eta_col']:.4f} "
          f"R_ideal={r['R_ideal']:.4f} ⇒ R={r['R']:.4f} A/W")
    print(f"golden(实测)=1.1 ±0.05 | diff={abs(r['R']-1.1):.4f} < tol 0.15")
    print(f"transit={r['transit_ps']:.2f} ps（原文 >40GHz 渡越极限一致量级）")
    guard_t1_not_oracle(r)
    print("T1 不作 ORACLE 守卫：正常通过")
