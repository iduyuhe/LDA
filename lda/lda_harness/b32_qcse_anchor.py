# -*- coding: utf-8 -*-
"""
B32 EAM-QCSE 吸收边位移锚 (T1-C W4, v0.9.69, A 档有源扩展 #3)

LOCK (2026-09-12): 器件类型 = MQW-QCSE (多量子阱 · 量子限制 Stark 效应)。
  - 评审 §2 初稿误锁 FK (体材料 Kane 1956)；但锚名 "EAM-QCSE" + 体 Si FK@1550nm
    因 Si 间接带隙 (E_g ~1.1eV >> 0.8eV 光子能) 可忽略 => 锁定 MQW-QCSE。
  - golden = QCSE 吸收边位移闭式 (无穷深方势阱二阶微扰, Miller 1985 / Bastard /
    Handwiki)：
        ΔE ≈ -24*(2/(3π))^6 * e^2 * F^2 * (m_e*Le^4 + m_h*Lh^4) / hbar^2
    const = 24*(2/(3π))^6 ≈ 2.1924e-3 (与专利 C1 = -2.19e-3 一致, WebSearch 双重佐证)。
  - candidate = 无穷深方势阱 1D 薛定谔有限差分数值对角化 (直接对角化 Hamiltonian,
    含场项 -eFz / +eFz) -> 与微扰闭式方法学独立 (数值 vs 解析), 判据 D 不撞。
  - V_mod -> F = V_mod / d_stack (闭式, 零 TCAD, 红线); ΔE(F) 红移 (吸收边向长波移)。
  - honest_tier = "qcse-closed-form"; MQW 外延 (生长) 属 foundry T2, 经 L/mass 文献
    消费而非求解 -> 红线安全 (行为层 A 档, 同 B28/B29/B31 范式)。
  - 红线自检：纯能带/电磁闭式 + 数值带结构, 无载流子动力学/无增益/无TCAD/无A级。
"""
import math
from typing import Dict, Any

# ---- 物理常数 ----
E_CHARGE = 1.602176634e-19       # C
M0 = 9.1093837015e-31            # kg
HBAR = 1.054571817e-34           # J*s
K_QCSE = 24.0 * (2.0 / (3.0 * math.pi)) ** 6   # ≈ 2.1924e-3

# ---- 默认材料参数 (Ge/SiGe MQW on Si, 文献消费, 非拟合非求解) ----
B32_M_E_DEFAULT = 0.12 * M0      # Ge/SiGe QW 电子限制质量 (representative)
B32_M_H_DEFAULT = 0.20 * M0      # Ge/SiGe QW 重空穴质量 (representative)
B32_L_DEFAULT = 8.0e-9           # 8 nm 量子阱宽
B32_D_STACK_DEFAULT = 5.0e-7     # 0.5 um MQW 栈厚 (V->F 消费)
B32_F_MAX = 1.0e8                # 1e6 V/cm 电离上限 (红线阈值)
B32_DOMAIN_LO = 1e-9             # 1 nm
B32_DOMAIN_HI = 50e-9            # 50 nm


def b32_voltage_to_field(V_mod: float, d_stack: float = None) -> float:
    """reverse bias V_mod (V) -> 场强 F (V/m), F = V_mod / d_stack。

    闭式换算, 红线零 TCAD：MQW 栈厚 d_stack 为文献/PDK 消费参数, 不作电学求解。
    """
    if d_stack is None:
        d_stack = B32_D_STACK_DEFAULT
    if V_mod < 0.0:
        raise ValueError("B32: V_mod must be >= 0 (reverse-bias magnitude)")
    if d_stack <= 0.0:
        raise ValueError("B32: d_stack must be > 0")
    return V_mod / d_stack


def b32_conf_e(m_e: float = None, L: float = None) -> float:
    """电子限制能 E_conf = hbar^2*pi^2/(2*m_e*L^2) (J)。用于红线: 扰动失效判据。"""
    if m_e is None:
        m_e = B32_M_E_DEFAULT
    if L is None:
        L = B32_L_DEFAULT
    return (HBAR ** 2) * (math.pi ** 2) / (2.0 * m_e * L ** 2)


def b32_qcse_shift_joule(F_Vpm: float, m_e: float = None, m_h: float = None,
                         L_e: float = None, L_h: float = None) -> float:
    """golden: QCSE 吸收边位移 (无穷深方势阱二阶微扰闭式), 返回 Joule (负=红移)。

    ΔE ≈ -K * e^2 * F^2 * (m_e*Le^4 + m_h*Lh^4) / hbar^2,  K=24*(2/3π)^6.
    默认 Le=Lh=L (对称阱)。F<=0 或阱宽越界即 raise (红线/适用域)。
    """
    if m_e is None:
        m_e = B32_M_E_DEFAULT
    if m_h is None:
        m_h = B32_M_H_DEFAULT
    if L_e is None:
        L_e = B32_L_DEFAULT
    if L_h is None:
        L_h = B32_L_DEFAULT
    if F_Vpm <= 0.0:
        raise ValueError("B32: F must be > 0 (reverse-bias field)")
    if not (B32_DOMAIN_LO <= L_e <= B32_DOMAIN_HI and B32_DOMAIN_LO <= L_h <= B32_DOMAIN_HI):
        raise ValueError("B32: well width out of sane domain 1-50 nm")
    return -K_QCSE * (E_CHARGE ** 2) * (F_Vpm ** 2) * (m_e * L_e ** 4 + m_h * L_h ** 4) / (HBAR ** 2)


def _b32_ground_state(m: float, F: float, L: float, charge_sign: float, N: int = 500) -> float:
    """candidate 内核: 无穷深方势阱 [-L/2,L/2] 1D 薛定谔有限差分数值对角化。

    H = -hbar^2/(2m) d2/dz2 + charge_sign*e*F*z  (电子 charge_sign=-1, 空穴 +1)。
    Dirichlet BC (psi=0 边界), 取基态本征值。直接对角化 => 与微扰闭式方法学独立。
    """
    import numpy as np
    z = np.linspace(-0.5 * L, 0.5 * L, N)
    dz = float(z[1] - z[0])
    t_diag = (HBAR ** 2) / (m * dz ** 2)
    t_off = -0.5 * t_diag
    diag = np.full(N, t_diag) + (charge_sign * E_CHARGE * F * z)
    off = np.full(N - 1, t_off)
    H = np.diag(diag) + np.diag(off, 1) + np.diag(off, -1)
    w = np.linalg.eigh(H)[0]
    return float(w[0])


def b32_qcse_shift_numerical_joule(F_Vpm: float, m_e: float = None, m_h: float = None,
                                   L: float = None, N: int = 500) -> float:
    """candidate: 数值对角化 QCSE 吸收边位移 = (E_e(F)+E_h(F)) - (E_e(0)+E_h(0)) (J)。"""
    if m_e is None:
        m_e = B32_M_E_DEFAULT
    if m_h is None:
        m_h = B32_M_H_DEFAULT
    if L is None:
        L = B32_L_DEFAULT
    if F_Vpm <= 0.0:
        raise ValueError("B32: F must be > 0 (reverse-bias field)")
    E_e0 = _b32_ground_state(m_e, 0.0, L, -1.0, N)
    E_h0 = _b32_ground_state(m_h, 0.0, L, +1.0, N)
    E_eF = _b32_ground_state(m_e, F_Vpm, L, -1.0, N)
    E_hF = _b32_ground_state(m_h, F_Vpm, L, +1.0, N)
    return (E_eF + E_hF) - (E_e0 + E_h0)


def b32_qcse_edge_shift_meV(V_mod: float, d_stack: float = None, m_e: float = None,
                            m_h: float = None, L_e: float = None, L_h: float = None) -> float:
    """golden 全链路: V_mod -> F -> ΔE (meV, 负=红移)。含红线: 扰动失效 + 电离上限。"""
    F = b32_voltage_to_field(V_mod, d_stack)
    if F > B32_F_MAX:
        raise ValueError("B32 red-line: field exceeds ionization threshold (>1e6 V/cm)")
    Le = L_e if L_e is not None else B32_L_DEFAULT
    dE_J = b32_qcse_shift_joule(F, m_e, m_h, L_e, L_h)
    E_conf = b32_conf_e(m_e, Le)
    if abs(dE_J) > 0.3 * E_conf:
        raise ValueError("B32 red-line: QCSE perturbation breaks (|dE| > 0.3 confinement energy)")
    return dE_J / E_CHARGE * 1e3


def b32_qcse_edge_shift_meV_numerical(V_mod: float, d_stack: float = None, m_e: float = None,
                                       m_h: float = None, L: float = None, N: int = 500) -> float:
    """candidate 全链路: V_mod -> F -> 数值对角化 ΔE (meV, 负=红移)。"""
    F = b32_voltage_to_field(V_mod, d_stack)
    if F > B32_F_MAX:
        raise ValueError("B32 red-line: field exceeds ionization threshold (>1e6 V/cm)")
    dE_J = b32_qcse_shift_numerical_joule(F, m_e, m_h, L, N)
    return dE_J / E_CHARGE * 1e3


def b32_qcse_report(V_mod: float, d_stack: float = None, m_e: float = None, m_h: float = None,
                    L_e: float = None, L_h: float = None, N: int = 500) -> Dict[str, Any]:
    """交叉验证报告: golden(闭式) vs candidate(数值对角化)。

    判据 D 不撞: 两法方法学不同源, 同号同量级 (ratio 0.2-3.0) 即证捕捉同一 QCSE 物理。
    """
    if m_e is None:
        m_e = B32_M_E_DEFAULT
    if m_h is None:
        m_h = B32_M_H_DEFAULT
    if L_e is None:
        L_e = B32_L_DEFAULT
    if L_h is None:
        L_h = B32_L_DEFAULT
    F = b32_voltage_to_field(V_mod, d_stack)
    dE_gold_J = b32_qcse_shift_joule(F, m_e, m_h, L_e, L_h)
    dE_num_J = b32_qcse_shift_numerical_joule(F, m_e, m_h, L_e, N)
    same_sign = (dE_gold_J < 0.0) and (dE_num_J < 0.0)
    ratio = (abs(dE_gold_J) / abs(dE_num_J)) if dE_num_J != 0.0 else float("inf")
    # 反向单调性扫描: F 增 -> |ΔE| 增
    Fs = [F * 0.25, F * 0.5, F * 0.75, F]
    mags = [abs(b32_qcse_shift_joule(ff, m_e, m_h, L_e, L_h)) for ff in Fs]
    monotone = all(mags[i] <= mags[i + 1] for i in range(len(mags) - 1))
    E_conf = b32_conf_e(m_e, L_e)
    perturbation_ok = (abs(dE_gold_J) <= 0.3 * E_conf) and (F <= B32_F_MAX)
    honest_tier = "qcse-closed-form"
    return {
        "F_Vpm": F,
        "dE_gold_meV": dE_gold_J / E_CHARGE * 1e3,
        "dE_num_meV": dE_num_J / E_CHARGE * 1e3,
        "same_sign": same_sign,
        "ratio_gold_over_num": ratio,
        "monotone_F_up": monotone,
        "E_conf_meV": E_conf / E_CHARGE * 1e3,
        "perturbation_ok": perturbation_ok,
        "honest_tier": honest_tier,
    }


if __name__ == "__main__":
    r = b32_qcse_report(3.0)
    print("B32 QCSE report @ V_mod=3.0V:", r)
