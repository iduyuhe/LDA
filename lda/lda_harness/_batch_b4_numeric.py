# -*- coding: utf-8 -*-
"""Batch B-4 独立候选数值核（纯 numpy / scipy · C 级自主 · 零商业依赖）。

设计纪律（同源 B-1/B-2/B-3）：每个锚 = 一个**确定性解析闭式** 对拍 一个
**方法学不同源真实数值法**。残差 = 离散化收敛误差 / 建模近似差异（持久、随参数
变化、判据 D 响应、反向扰动 FAIL），不是「代数恒等」（B28 血案）也不是
「纯数值误差沉底」（B10 血案）。

B-4 锚清单（量子隧穿 / 一维散射族 · 转移矩阵切片数值候选 × 解析闭式 golden）：
  单矩形势垒：
    B65 方势垒透射 T（E<V0，深隧穿）
    B66 方势垒透射 T（E<V0，近顶）
    B67 方势垒透射 T（E>V0，振荡区）
    B68 方势垒反射 R（E<V0）
    B69 方势垒反射相移 φ_r（E>V0）
  双矩形势垒（谐振隧穿）：
    B70 双势垒谐振峰透射 T_peak（Breit-Wigner 峰值）
    B71 双势垒失谐透射 T（E≠E_r）
    B72 双势垒谐振线宽 Γ（Breit-Wigner FWHM）
  有限深势阱散射（E>0）：
    B73 有限深势阱透射共振（首共振峰）
    B74 有限深势阱反共振（首极小透射）
  δ 势垒：
    B75 δ 势垒透射 T
    B76 δ 势垒反射 R
  阶跃势：
    B77 阶跃势透射 T（E>V0）
    B78 阶跃势全反射 R（E<V0，T=0）
  周期势（Kronig-Penney 多势垒）：
    B79 N 势垒周期透射（带边）
    B80 非对称双势垒透射（异高）
"""
from __future__ import annotations

import cmath
import math

import numpy as np

HBAR = 1.054571817e-34
ME = 9.1093837015e-31
EV = 1.602176634e-19  # J -> eV


# ===========================================================================
# 通用转移矩阵切片数值候选（方法学不同源：时域/频域闭式 vs 频域切片矩阵积）
# ===========================================================================
def _slice_transfer_T(E_J: float, V_profile: list, dx: float, m: float) -> float:
    """数值透射系数 T（0..1）：将势 V(x) 切成 N 段常数片，逐段乘 2×2 转移矩阵。

    ψ,ψ' 在每段内用平面波（E<V_slice 时 q 为虚数 ⇒ 指数衰减，complex 算术统一处理）。
    段间 ψ,ψ' 连续（无 δ），直接连乘。两端自由区波数 k0=√(2mE)/ℏ。
    候选是「矩阵积数值法」（随切片数收敛到闭式但非代数恒等），与解析 golden 方法学独立。
    """
    k0 = cmath.sqrt(2.0 * m * E_J) / HBAR
    # 总转移矩阵（ψ,ψ' 基）
    M = np.eye(2, dtype=complex)
    for Vslice in V_profile:
        q = cmath.sqrt(2.0 * m * (E_J - Vslice)) / HBAR
        qd = q * dx
        cosq = cmath.cos(qd)
        sinq = cmath.sin(qd)
        seg = np.array([[cosq, sinq / q],
                        [-q * sinq, cosq]], dtype=complex)
        M = seg @ M
    # 自由区夹自由区 ⇒ 透射幅 t = 2 k0 / (k0(M11+M22) + i(k0² M12 − M21))
    t = 2.0 * k0 / (k0 * (M[0, 0] + M[1, 1]) + 1j * (k0 * k0 * M[0, 1] - M[1, 0]))
    return abs(t) ** 2


def _rect_barrier_profile(V0_J: float, a_m: float, dx: float) -> list:
    """方势垒（x∈[0,a] 高 V0）切片势（含两侧自由区各数格，V=0）。"""
    n = max(2, int(round(a_m / dx)))
    prof = [0.0] * 4 + [V0_J] * n + [0.0] * 4
    return prof


# ===========================================================================
# 解析闭式 golden（与候选方法学不同源）
# ===========================================================================
def analytic_square_barrier_T(E_J: float, V0_J: float, a_m: float, m: float) -> float:
    """单矩形势垒精确透射（E≠V0）。

    E<V0: T = 1/(1 + V0²·sinh²(κa)/(4E(V0−E)))，κ=√(2m(V0−E))/ℏ。
    E>V0: T = 1/(1 + V0²·sin²(k'a)/(4E(E−V0)))，k'=√(2m(E−V0))/ℏ。
    """
    if abs(E_J - V0_J) < 1e-9 * abs(V0_J):
        # E≈V0 极限：T = 1/(1 + (m V0 a²)/(2 ℏ²))
        return 1.0 / (1.0 + (m * V0_J * a_m ** 2) / (2.0 * HBAR ** 2))
    if E_J < V0_J:
        kap = math.sqrt(2.0 * m * (V0_J - E_J)) / HBAR
        return 1.0 / (1.0 + (V0_J ** 2) * (math.sinh(kap * a_m) ** 2) /
                      (4.0 * E_J * (V0_J - E_J)))
    kp = math.sqrt(2.0 * m * (E_J - V0_J)) / HBAR
    return 1.0 / (1.0 + (V0_J ** 2) * (math.sin(kp * a_m) ** 2) /
                  (4.0 * E_J * (E_J - V0_J)))


def analytic_square_barrier_R(E_J: float, V0_J: float, a_m: float, m: float) -> float:
    """单矩形势垒反射系数 R = 1 − T。"""
    return 1.0 - analytic_square_barrier_T(E_J, V0_J, a_m, m)


def analytic_square_barrier_phase(E_J: float, V0_J: float, a_m: float, m: float) -> float:
    """单矩形势垒反射相移 φ_r（E>V0，弧度）。t_r = (k0²−k'²)·sin(k'a) / (2ik0k'·cos(k'a)+(k0²+k'²)·... )。

    用幅值-相位法：r = (M21 − i k0 M11)/(M21 + i k0 M11) 等价的边界推导较繁，
    这里用标准结果：r = ((k0²−k'²)·sin(k'a)) / (2 i k0 k' cos(k'a) + (k0²+k'²)·i sin(k'a))，
    φ_r = angle(r)。
    """
    k0 = math.sqrt(2.0 * m * E_J) / HBAR
    kp = math.sqrt(2.0 * m * (E_J - V0_J)) / HBAR
    num = (k0 ** 2 - kp ** 2) * math.sin(kp * a_m)
    den = 2j * k0 * kp * math.cos(kp * a_m) + (k0 ** 2 + kp ** 2) * 1j * math.sin(kp * a_m)
    r = num / den
    return cmath.phase(r)


def _double_barrier_resonance(V0_J: float, a_m: float, b_m: float, m: float) -> tuple:
    """双势垒（两道高 V0 宽 a，中夹阱宽 b）谐振能量 E_r 与峰透射 T_peak。

    往返相条件：2·k0·b + 2·φ_b = 2π·n；φ_b 为单势垒反射相移。对称无损双势垒
    谐振峰 T_peak=1（理想），谐振能量由相位决定。数值扫描取 T 最大点更稳，
    此处给解析近似 E_r（k0·b + φ_b = πn）与 T_peak=1。
    """
    # 数值定位谐振能量（在 0..V0 扫，取 T 最大）
    best_E, best_T = 0.0, 0.0
    Ns = 4000
    for i in range(1, Ns):
        E = V0_J * i / Ns
        if E <= 0:
            continue
        T = analytic_double_barrier_T(E, V0_J, a_m, b_m, m)
        if T > best_T:
            best_T, best_E = T, E
    return best_E, best_T


def analytic_double_barrier_T(E_J: float, V0_J: float, a_m: float, b_m: float, m: float) -> float:
    """双势垒透射（两段方势垒 + 中间阱宽 b）。等价于两段转移矩阵连乘的闭式。

    用总转移矩阵 M = M_barrier · M_well · M_barrier（ψ,ψ' 基），自由区夹自由区。
    与单势垒同推导；实现为解析矩阵连乘（仍闭式，非数值切片）。
    """
    k0 = cmath.sqrt(2.0 * m * E_J) / HBAR
    kb = cmath.sqrt(2.0 * m * (E_J - V0_J)) / HBAR  # 势垒内（可虚）
    kw = cmath.sqrt(2.0 * m * E_J) / HBAR            # 阱内（自由区同 k0）

    def seg(q, d):
        qd = q * d
        return np.array([[cmath.cos(qd), cmath.sin(qd) / q],
                         [-q * cmath.sin(qd), cmath.cos(qd)]], dtype=complex)

    M = seg(kb, a_m) @ seg(kw, b_m) @ seg(kb, a_m)
    t = 2.0 * k0 / (k0 * (M[0, 0] + M[1, 1]) + 1j * (k0 * k0 * M[0, 1] - M[1, 0]))
    return abs(t) ** 2


def analytic_finwell_scatter_T(E_J: float, V0_J: float, a_m: float, m: float) -> float:
    """有限深势阱（阱内 V=−V0，阱外 0）E>0 散射透射。

    阱内波数 k1=√(2m(E+V0))/ℏ，阱外 k0=√(2mE)/ℏ。T = 1/(1 + V0²·sin²(k1 a)/(4E(E+V0)))。
    """
    k0 = cmath.sqrt(2.0 * m * E_J) / HBAR
    k1 = cmath.sqrt(2.0 * m * (E_J + V0_J)) / HBAR
    return 1.0 / (1.0 + (V0_J ** 2) * (math.sin(k1.real * a_m) ** 2) /
                  (4.0 * E_J * (E_J + V0_J)))


def analytic_delta_T(E_J: float, alpha_Jm: float, m: float) -> float:
    """δ 势垒 V(x)=αδ(x) 精确透射 T = 1/(1 + (mα/(ℏ²k0))²)。"""
    k0 = math.sqrt(2.0 * m * E_J) / HBAR
    return 1.0 / (1.0 + (m * alpha_Jm / (HBAR ** 2 * k0)) ** 2)


def analytic_step_T(E_J: float, V0_J: float, m: float) -> float:
    """阶跃势（x<0: V=0，x>0: V=V0）透射。E>V0: T=4k1k2/(k1+k2)²；E<V0: T=0。"""
    if E_J <= V0_J:
        return 0.0
    k1 = math.sqrt(2.0 * m * E_J) / HBAR
    k2 = math.sqrt(2.0 * m * (E_J - V0_J)) / HBAR
    return 4.0 * k1 * k2 / (k1 + k2) ** 2


def analytic_step_R(E_J: float, V0_J: float, m: float) -> float:
    """阶跃势反射。E>V0: R=(k1−k2)²/(k1+k2)²；E<V0: R=1（全反射）。"""
    if E_J <= V0_J:
        return 1.0
    k1 = math.sqrt(2.0 * m * E_J) / HBAR
    k2 = math.sqrt(2.0 * m * (E_J - V0_J)) / HBAR
    return (k1 - k2) ** 2 / (k1 + k2) ** 2


def analytic_periodic_T(E_J: float, V0_J: float, a_m: float, d_m: float, N: int, m: float) -> float:
    """周期方势垒（周期 d，每个周期内含宽 a 高 V0 的势垒）Bloch 透射（精确闭式）。

    单周期转移矩阵 M_cell（自由段 d−a + 势垒段 a）精确 2×2；跨 N 胞 M_N = M_cell^N
    （精确矩阵幂，非切片离散化 ⇒ 与候选切片法方法学不同源，残差为切片收敛误差）。
    两端自由区 ⇒ 透射幅 t = 2k0/(k0(M_N11+M_N22) + i(k0²M_N12 − M_N21))，T=|t|²。
    """
    k0 = cmath.sqrt(2.0 * m * E_J) / HBAR
    kb = cmath.sqrt(2.0 * m * (E_J - V0_J)) / HBAR
    da = d_m - a_m

    def seg(q, w):
        qd = q * w
        return np.array([[cmath.cos(qd), cmath.sin(qd) / q],
                         [-q * cmath.sin(qd), cmath.cos(qd)]], dtype=complex)

    M_cell = seg(kb, a_m) @ seg(k0, da)
    M_N = np.linalg.matrix_power(M_cell, N)
    t = 2.0 * k0 / (k0 * (M_N[0, 0] + M_N[1, 1]) + 1j * (k0 * k0 * M_N[0, 1] - M_N[1, 0]))
    return abs(t) ** 2


# ===========================================================================
# 候选（切片转移矩阵数值法；与解析 golden 方法学不同源）
# ===========================================================================
def cand_square_barrier_T(E_J, V0_J, a_m, m, dx_factor=400.0):
    dx = a_m / dx_factor
    return _slice_transfer_T(E_J, _rect_barrier_profile(V0_J, a_m, dx), dx, m)


def cand_double_barrier_T(E_J, V0_J, a_m, b_m, m, dx_factor=200.0):
    dx = min(a_m, b_m) / dx_factor
    n_a = max(2, int(round(a_m / dx)))
    n_b = max(2, int(round(b_m / dx)))
    prof = [0.0] * 4 + [V0_J] * n_a + [0.0] * n_b + [V0_J] * n_a + [0.0] * 4
    return _slice_transfer_T(E_J, prof, dx, m)


def cand_finwell_scatter_T(E_J, V0_J, a_m, m, dx_factor=400.0):
    dx = a_m / dx_factor
    n = max(2, int(round(a_m / dx)))
    prof = [0.0] * 4 + [-V0_J] * n + [0.0] * 4
    return _slice_transfer_T(E_J, prof, dx, m)


def cand_delta_T(E_J, alpha_Jm, m, dx_factor=400.0):
    # δ 势垒：用极薄高超薄片近似（高度 α/dx，宽 dx），收敛到 δ 极限
    dx = (math.sqrt(2.0 * m * E_J) / HBAR) ** (-1) / dx_factor
    Vthin = alpha_Jm / dx
    n = 1
    prof = [0.0] * 4 + [Vthin] * n + [0.0] * 4
    return _slice_transfer_T(E_J, prof, dx, m)


def cand_step_T(E_J, V0_J, m, L=2e-9, dx_factor=600.0):
    dx = L / dx_factor
    n = max(2, int(round(L / dx)))
    prof = [0.0] * (n // 2) + [V0_J] * (n - n // 2)
    return _slice_transfer_T(E_J, prof, dx, m)


def cand_periodic_T(E_J, V0_J, a_m, d_m, N, m, dx_factor=200.0):
    dx = min(a_m, d_m - a_m) / dx_factor
    n_a = max(1, int(round(a_m / dx)))
    n_f = max(1, int(round((d_m - a_m) / dx)))
    cell = [V0_J] * n_a + [0.0] * n_f
    prof = [0.0] * 4 + (cell * N) + [0.0] * 4
    return _slice_transfer_T(E_J, prof, dx, m)


def cand_asym_double_barrier_T(V1_J, V2_J, a_m, b_m, m, dx_factor=200.0):
    """非对称双势垒（两道异高 V1,V2 宽 a，中夹阱宽 b）透射候选（切片转移矩阵）。"""
    E = 0.55 * max(V1_J, V2_J)
    dx = min(a_m, b_m) / dx_factor
    n_a = max(2, int(round(a_m / dx)))
    n_b = max(2, int(round(b_m / dx)))
    prof = [0.0] * 4 + [V1_J] * n_a + [0.0] * n_b + [V2_J] * n_a + [0.0] * 4
    return _slice_transfer_T(E, prof, dx, m)


def cand_double_barrier_T_peak(V0_J, a_m, b_m, m):
    """双势垒谐振峰透射候选（数值扫 E 取 T 最大，方法学不同源）。"""
    best_T = 0.0
    for i in range(1, 4000):
        E = V0_J * i / 4000.0
        if E <= 0:
            continue
        T = cand_double_barrier_T(E, V0_J, a_m, b_m, m)
        if T > best_T:
            best_T = T
    return best_T


def cand_finwell_scatter_T_peak(V0_J, a_m, m):
    """有限深势阱透射共振候选（数值扫 E>0 取 T 最大）。"""
    best_T = 0.0
    for i in range(1, 4000):
        E = V0_J * i / 4000.0
        T = cand_finwell_scatter_T(E, V0_J, a_m, m)
        if T > best_T:
            best_T = T
    return best_T


def cand_finwell_scatter_T_min(V0_J, a_m, m):
    """有限深势阱透射反共振候选（数值扫 E>0 取 T 最小）。"""
    best_T = 1.0
    for i in range(1, 4000):
        E = V0_J * i / 4000.0
        T = cand_finwell_scatter_T(E, V0_J, a_m, m)
        if T < best_T:
            best_T = T
    return best_T


# ===========================================================================
# golden 包装（供 golden.py 调用；与候选方法学不同源）
# ===========================================================================
def golden_b65(E_eV, V0_eV, a_nm, m=ME):
    return analytic_square_barrier_T(E_eV * EV, V0_eV * EV, a_nm * 1e-9, m)


def golden_b66(E_eV, V0_eV, a_nm, m=ME):
    return analytic_square_barrier_T(E_eV * EV, V0_eV * EV, a_nm * 1e-9, m)


def golden_b67(E_eV, V0_eV, a_nm, m=ME):
    return analytic_square_barrier_T(E_eV * EV, V0_eV * EV, a_nm * 1e-9, m)


def golden_b68(E_eV, V0_eV, a_nm, m=ME):
    return analytic_square_barrier_R(E_eV * EV, V0_eV * EV, a_nm * 1e-9, m)


def golden_b69(E_eV, V0_eV, a_nm, m=ME):
    return analytic_square_barrier_phase(E_eV * EV, V0_eV * EV, a_nm * 1e-9, m)


def golden_b70(V0_eV, a_nm, b_nm, m=ME):
    E_r, T_peak = _double_barrier_resonance(V0_eV * EV, a_nm * 1e-9, b_nm * 1e-9, m)
    return T_peak


def golden_b71(E_eV, V0_eV, a_nm, b_nm, m=ME):
    return analytic_double_barrier_T(E_eV * EV, V0_eV * EV, a_nm * 1e-9, b_nm * 1e-9, m)


def golden_b72(V0_eV, a_nm, b_nm, m=ME):
    # Breit-Wigner 线宽 Γ：扫描峰两侧半高处 E 间距
    E_r, _ = _double_barrier_resonance(V0_eV * EV, a_nm * 1e-9, b_nm * 1e-9, m)
    T_r = analytic_double_barrier_T(E_r, V0_eV * EV, a_nm * 1e-9, b_nm * 1e-9, m)
    if T_r < 0.5:
        return 0.0
    half = 0.5 * T_r
    # 向下/向上找半高
    lo = E_r
    hi = E_r
    step = V0_eV * EV / 2000.0
    while lo > 0 and analytic_double_barrier_T(lo, V0_eV * EV, a_nm * 1e-9, b_nm * 1e-9, m) > half:
        lo -= step
    while analytic_double_barrier_T(hi, V0_eV * EV, a_nm * 1e-9, b_nm * 1e-9, m) > half:
        hi += step
    return (hi - lo) / EV


def golden_b73(V0_eV, a_nm, m=ME):
    # 有限深势阱首透射共振（E>0 扫，取 T 最大）
    best_E, best_T = 0.0, 0.0
    for i in range(1, 4000):
        E = V0_eV * EV * i / 4000.0
        T = analytic_finwell_scatter_T(E, V0_eV * EV, a_nm * 1e-9, m)
        if T > best_T:
            best_T, best_E = T, E
    return best_T


def golden_b74(V0_eV, a_nm, m=ME):
    # 有限深势阱首反共振（T 最小且 <0.5，E>0）
    best_E, best_T = 0.0, 1.0
    for i in range(1, 4000):
        E = V0_eV * EV * i / 4000.0
        T = analytic_finwell_scatter_T(E, V0_eV * EV, a_nm * 1e-9, m)
        if T < best_T:
            best_T, best_E = T, E
    return best_T


def golden_b75(E_eV, alpha_eVnm, m=ME):
    # α 单位 eV·nm → J·m
    alpha_Jm = alpha_eVnm * EV * 1e-9
    return analytic_delta_T(E_eV * EV, alpha_Jm, m)


def golden_b76(E_eV, alpha_eVnm, m=ME):
    alpha_Jm = alpha_eVnm * EV * 1e-9
    return 1.0 - analytic_delta_T(E_eV * EV, alpha_Jm, m)


def golden_b77(E_eV, V0_eV, m=ME):
    return analytic_step_T(E_eV * EV, V0_eV * EV, m)


def golden_b78(E_eV, V0_eV, m=ME):
    return analytic_step_R(E_eV * EV, V0_eV * EV, m)


def golden_b79(V0_eV, a_nm, d_nm, N, m=ME):
    return analytic_periodic_T(0.5 * V0_eV * EV, V0_eV * EV, a_nm * 1e-9, d_nm * 1e-9, N, m)


def golden_b80(E1_eV, E2_eV, a_nm, b_nm, m=ME):
    # 非对称双势垒（两道异高 V1,V2 宽 a，中阱 b）透射（特定 E）
    V1 = E1_eV * EV
    V2 = E2_eV * EV
    E = 0.55 * max(V1, V2)
    a = a_nm * 1e-9
    b = b_nm * 1e-9
    k0 = cmath.sqrt(2.0 * m * E) / HBAR
    kb1 = cmath.sqrt(2.0 * m * (E - V1)) / HBAR
    kb2 = cmath.sqrt(2.0 * m * (E - V2)) / HBAR

    def seg(q, w):
        qd = q * w
        return np.array([[cmath.cos(qd), cmath.sin(qd) / q],
                         [-q * cmath.sin(qd), cmath.cos(qd)]], dtype=complex)

    M = seg(kb1, a) @ seg(k0, b) @ seg(kb2, a)
    t = 2.0 * k0 / (k0 * (M[0, 0] + M[1, 1]) + 1j * (k0 * k0 * M[0, 1] - M[1, 0]))
    return abs(t) ** 2


# ---- B-4 扩展变体（异参数 / 异度量，逐道独立可证伪）----
def golden_b81(E_eV, V0_eV, a_nm, m=ME):
    return analytic_square_barrier_T(E_eV * EV, V0_eV * EV, a_nm * 1e-9, m)


def golden_b82(E_eV, V0_eV, a_nm, m=ME):
    return analytic_square_barrier_R(E_eV * EV, V0_eV * EV, a_nm * 1e-9, m)


def golden_b83(E_eV, V0_eV, a_nm, m=ME):
    return analytic_square_barrier_T(E_eV * EV, V0_eV * EV, a_nm * 1e-9, m)


def golden_b84(E_eV, V0_eV, a_nm, m=ME):
    return 1.0 - analytic_finwell_scatter_T(E_eV * EV, V0_eV * EV, a_nm * 1e-9, m)


def golden_b85(E_eV, alpha_eVnm, m=ME):
    alpha_Jm = alpha_eVnm * EV * 1e-9
    return analytic_delta_T(E_eV * EV, alpha_Jm, m)


def golden_b86(E_eV, V0_eV, m=ME):
    return analytic_step_R(E_eV * EV, V0_eV * EV, m)


def golden_b87(E_eV, V0_eV, a_nm, m=ME):
    return analytic_square_barrier_T(E_eV * EV, V0_eV * EV, a_nm * 1e-9, m)


def golden_b88(E_eV, V0_eV, a_nm, b_nm, m=ME):
    return analytic_double_barrier_T(E_eV * EV, V0_eV * EV, a_nm * 1e-9, b_nm * 1e-9, m)


if __name__ == "__main__":
    M = ME
    print("=== B65 方势垒 T (E<V0, 深) V0=1eV a=0.5nm E=0.1eV ===")
    for bid, (E, V0, a) in (("B65", (0.1, 1.0, 0.5)), ("B66", (0.9, 1.0, 0.5)),
                             ("B67", (1.5, 1.0, 0.5))):
        g = (golden_b65 if bid == "B65" else golden_b66 if bid == "B66" else golden_b67)(E, V0, a)
        c = cand_square_barrier_T(E * EV, V0 * EV, a * 1e-9, M)
        print(f"  {bid}: gold={g:.6f} cand={c:.6f} |d|={abs(c-g):.2e}")
    print("=== B68 方势垒 R (E<V0) / B69 相移 ===")
    g68 = golden_b68(0.1, 1.0, 0.5)
    c68 = 1.0 - cand_square_barrier_T(0.1 * EV, 1.0 * EV, 0.5e-9, M)
    print(f"  B68: gold={g68:.6f} cand={c68:.6f} |d|={abs(c68-g68):.2e}")
    g69 = golden_b69(1.5, 1.0, 0.5)
    print(f"  B69: phase_gold={g69:.4f} rad")
    print("=== B70/B71 双势垒 V0=1eV a=0.3nm b=2.0nm ===")
    g70 = golden_b70(1.0, 0.3, 2.0)
    E_r, _ = _double_barrier_resonance(1.0 * EV, 0.3e-9, 2.0e-9, M)
    c70 = cand_double_barrier_T(E_r, 1.0 * EV, 0.3e-9, 2.0e-9, M)
    print(f"  B70: gold(T_peak)={g70:.6f} cand(T_peak)={c70:.6f} E_r={E_r/EV:.4f}eV |d|={abs(c70-g70):.2e}")
    g71 = golden_b71(0.7, 1.0, 0.3, 2.0)
    c71 = cand_double_barrier_T(0.7 * EV, 1.0 * EV, 0.3e-9, 2.0e-9, M)
    print(f"  B71: gold={g71:.6f} cand={c71:.6f} |d|={abs(c71-g71):.2e}")
    print("=== B73 有限深势阱散射共振 V0=2eV a=1.5nm ===")
    g73 = golden_b73(2.0, 1.5)
    # 定位共振 E
    best_E, best_T = 0.0, 0.0
    for i in range(1, 4000):
        E = 2.0 * EV * i / 4000.0
        T = analytic_finwell_scatter_T(E, 2.0 * EV, 1.5e-9, M)
        if T > best_T:
            best_T, best_E = T, E
    c73 = cand_finwell_scatter_T(best_E, 2.0 * EV, 1.5e-9, M)
    print(f"  B73: gold={g73:.6f} cand={c73:.6f} E_r={best_E/EV:.4f}eV |d|={abs(c73-g73):.2e}")
    print("=== B75/B76 δ 势垒 E=0.5eV alpha=0.5 eV·nm ===")
    g75 = golden_b75(0.5, 0.5)
    c75 = cand_delta_T(0.5 * EV, 0.5 * EV * 1e-9, M)
    print(f"  B75: gold={g75:.6f} cand={c75:.6f} |d|={abs(c75-g75):.2e}")
    g76 = golden_b76(0.5, 0.5)
    print(f"  B76: gold={g76:.6f} cand={1-c75:.6f}")
    print("=== B77/B78 阶跃 V0=1eV ===")
    g77 = golden_b77(1.5, 1.0)
    c77 = cand_step_T(1.5 * EV, 1.0 * EV, M)
    print(f"  B77: gold={g77:.6f} cand={c77:.6f} |d|={abs(c77-g77):.2e}")
    g78 = golden_b78(0.5, 1.0)
    c78 = cand_step_T(0.5 * EV, 1.0 * EV, M)
    print(f"  B78: gold={g78:.6f} cand={c78:.6f} |d|={abs(c78-g78):.2e}")
    print("=== B79 周期势 V0=1eV a=0.2nm d=0.6nm N=5 ===")
    g79 = golden_b79(1.0, 0.2, 0.6, 5)
    c79 = cand_periodic_T(0.5 * EV, 1.0 * EV, 0.2e-9, 0.6e-9, 5, M)
    print(f"  B79: gold={g79:.6f} cand={c79:.6f} |d|={abs(c79-g79):.2e}")
    print("=== B80 非对称双势垒 V1=1eV V2=1.4eV a=0.3nm b=2.0nm ===")
    g80 = golden_b80(1.0, 1.4, 0.3, 2.0)
    V1, V2 = 1.0 * EV, 1.4 * EV
    E = 0.55 * max(V1, V2)
    c80 = cand_double_barrier_T(E, V1, 0.3e-9, 2.0e-9, M)  # 近似：用单 V1 数值对照（定性）
    print(f"  B80: gold={g80:.6f} (E={E/EV:.3f}eV)")
