# -*- coding: utf-8 -*-
"""Batch B-5 独立候选数值核（纯 numpy / scipy · C 级自主 · 零商业依赖）。

设计纪律（同源 B-1..B-4）：每个锚 = 一个**确定性解析闭式 / 超越方程精确解** 对拍 一个
**方法学不同源真实数值法**。残差 = 离散化误差 / 建模近似差异（持久、随参数变化、
判据 D 响应、反向扰动 FAIL），不是「代数恒等」（B28 血案）也不是「纯数值误差沉底」（B10 血案）。

Batch B-5 锚清单（16 道，全为严格独立候选 · B89-B104）：
  氢原子径向族（Coulomb 势 · 径向薛定谔 FD 本征 ↔ Rydberg 闭式 −13.6·Z²/n²）：
    B89 氢 1s（l=0, n=1）            B90 氢 2s（l=0, n=2）
    B91 氢 2p（l=1, n=2）            B92 氢 3s（l=0, n=3）
    B93 氢 3p（l=1, n=3）            B94 氢 3d（l=2, n=3）
  三维各向同性谐振子径向族（V=½mω²r² · 径向 FD 本征 ↔ (2n_r+l+3/2)ℏω 闭式）：
    B95 3D-HO 基态（l=0）            B96 3D-HO（l=1）            B97 3D-HO（l=2）
  圆波导截止频率族（Bessel 闭式 ↔ 径向 ODE 数值积分，复用 B-3 circ_wg 方法学）：
    B98 圆波导 TE21 截止              B99 圆波导 TM01 截止          B100 圆波导 TE01 截止
  矩形金属波导高阶截止（复用 B-3 rect_wg_tm 二盒乘积 1D FD ↔ 解析闭式）：
    B101 矩形 TE12 截止              B102 矩形 TE22 截止
    B103 矩形 TE31 截止              B104 矩形 TE13 截止
"""
from __future__ import annotations

import math

import numpy as np
from scipy.linalg import eigh
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

# 复用 Batch B-2/B-3 已验证数值核（判据 D 由 run_d_criterion_smoke 已证）
try:
    from ._batch_b3_numeric import (
        rect_wg_tm_fc,
        rect_wg_tm_fd,
    )
except ImportError:  # 直接运行本文件时回退
    from _batch_b3_numeric import (  # type: ignore
        rect_wg_tm_fc,
        rect_wg_tm_fd,
    )

C0 = 299792458.0
HBAR = 1.054571817e-34
ME = 9.1093837015e-31
EV = 1.602176634e-19  # J -> eV
RYDBERG = 13.605693122994  # eV，氢原子基态 |E_1|
COULOMB = 1.43996448e-9   # eV·m，e²/(4πε0)

# ===========================================================================
# 径向薛定谔 FD 本征求解器（u(r)=r·R(r)，u(0)=u(R)=0 Dirichlet 盒）
# ===========================================================================
def _radial_fd_evals(R: float, N: int, l: int, m: float, V_central_J) -> np.ndarray:
    """径向方程 -ℏ²/2m·u'' + V_eff(r)·u = E·u 的 FD 本征值（升序，单位 J）。

    V_eff(r) = V_central(r) + ℏ²l(l+1)/(2m r²)。u(0)=u(R)=0（Dirichlet）。
    第 n_r 个径向束缚态 = 升序第 n_r 个本征值（n_r=0 基态）。
    """
    dr = R / (N + 1)
    r = dr * np.arange(1, N + 1)
    t = HBAR ** 2 / (2.0 * m * dr ** 2)
    diag = 2.0 * t * np.ones(N)
    off = -t * np.ones(N - 1)
    T = np.diag(diag) + np.diag(off, 1) + np.diag(off, -1)
    Vcen = np.array([V_central_J(ri) for ri in r], dtype=float)
    Vl = (HBAR ** 2) * l * (l + 1) / (2.0 * m * r ** 2)
    Veff = np.where(np.isfinite(Vcen + Vl), Vcen + Vl, 0.0)
    H = T + np.diag(Veff)
    H = (H + H.T) / 2.0
    return eigh(H, eigvals_only=True)  # 升序，J


# ===========================================================================
# B89-B94 · 氢原子径向能级（Rydberg 闭式 ↔ 径向 FD 本征）
# ===========================================================================
def _coulomb_V(Z: float):
    def V(r):
        return -COULOMB * Z * EV / r
    return V


def hydrogen_E_rydberg(Z: float, n: int) -> float:
    """golden：氢原子能级闭式 E_n = -RYDBERG·Z²/n²（eV）。"""
    return -RYDBERG * (Z ** 2) / (n ** 2)


def hydrogen_E_fd(Z: float, l: int, n_r: int, R: float = 4.0e-9, N: int = 4000) -> float:
    """候选：径向 FD 薛定谔本征第 n_r 态（eV），V(r)=-Z·e²/(4πε0 r)。"""
    e_j = float(_radial_fd_evals(R, N, l, ME, _coulomb_V(Z))[n_r])
    return e_j / EV


# ===========================================================================
# B95-B97 · 三维各向同性谐振子径向能级（(2n_r+l+3/2)ℏω ↔ 径向 FD 本征）
# ===========================================================================
def _ho_central_V(hbar_omega: float):
    omega = hbar_omega / HBAR
    def V(r):
        return 0.5 * ME * omega ** 2 * r ** 2
    return V


def ho3d_E_closed(n_r: int, l: int, hbar_omega: float) -> float:
    """golden：3D 各向同性谐振子能级 E = (2n_r + l + 3/2)·ℏω（eV）。"""
    return (2.0 * n_r + l + 1.5) * hbar_omega / EV


def ho3d_E_fd(n_r: int, l: int, hbar_omega: float, N: int = 1600) -> float:
    """候选：径向 FD 薛定谔本征第 n_r 态（eV），V(r)=½mω²r²。"""
    omega = hbar_omega / HBAR
    sigma = math.sqrt(HBAR / (ME * omega))
    R = 14.0 * sigma
    e_j = float(_radial_fd_evals(R, N, l, ME, _ho_central_V(hbar_omega))[n_r])
    return e_j / EV


# ===========================================================================
# B98-B100 · 圆波导 TE_mn / TM_mn 截止频率（Bessel 闭式 ↔ 径向 ODE 数值积分）
#   无量纲截止常数 X = kc·a；fc = X·c/(2πa)。复用 B-3 circ_wg 方法学（场方程数值积分
#   导出 X，与 golden 的 Bessel 零点查表不同源）。
#     B98 圆波导 TE21 截止  (X'_21 = J2' 首零点 = 3.05424)
#     B99 圆波导 TM01 截止  (X_01  = J0  首零点 = 2.40483)
#     B100 圆波导 TE01 截止  (X'_01 = J0' 首零点 = 3.83171)
# ===========================================================================
def _circ_bc_res(X: float, m: int, pol: str, a_dummy: float = 1.0) -> float:
    """圆波导 (m,pol) 边界残差：R'(a)（TE）或 R(a)（TM），零点即截止根。"""
    kc = X / a_dummy
    r0 = 1e-9
    if m == 0:
        R0, dR0 = 1.0, 0.0

        def rhs(r, y):
            R, dR = y
            return [dR, -(1.0 / r) * dR - kc * kc * R]

        sol = solve_ivp(rhs, [r0, a_dummy], [R0, dR0],
                        t_eval=[a_dummy], rtol=1e-11, atol=1e-14)
        R_a, dR_a = float(sol.y[0, 0]), float(sol.y[1, 0])
        return dR_a if pol == "TE" else R_a
    else:
        S0, dS0 = 1.0, 0.0

        def rhs(r, y):
            S, dS = y
            return [dS, -((2.0 * m + 1.0) / r) * dS - kc * kc * S]

        sol = solve_ivp(rhs, [r0, a_dummy], [S0, dS0],
                        t_eval=[a_dummy], rtol=1e-11, atol=1e-14)
        S_a, dS_a = float(sol.y[0, 0]), float(sol.y[1, 0])
        if pol == "TE":
            return m * a_dummy ** (m - 1) * S_a + a_dummy ** m * dS_a  # R'(a)
        return S_a  # TM：R(a)=a^m·S(a)=0 → S_a=0


def _circ_wg_cutoff_X(m: int, pol: str, a_dummy: float = 1.0) -> float:
    """数值导出圆波导 (m,pol) 模无量纲截止常数 X=kc·a（首根，与 a 无关）。

    径向 Helmholtz：R'' + (1/r)R' + (kc² − m²/r²)R = 0。
    m≥1 令 R=r^m·S 消去奇点项 → S'' + (2m+1)/r·S' + kc²S = 0（m=1 即 B-3 已证式）；
    m=0 直接积分。边界：TE 令 R'(a)=0（J_m' 零点），TM 令 R(a)=0（J_m 零点）。
    扫描 X 取首根；fc∝1/a，判据 D 可捕获被篡改 golden。
    """
    # 各 (m,pol) 的首根落在如下安全括号内（端点异号，brentq 稳健收敛）
    lo, hi = _CIRC_BRACKETS[(m, pol)]
    return float(brentq(lambda X: _circ_bc_res(X, m, pol, a_dummy),
                        lo, hi, xtol=1e-13, rtol=1e-15, maxiter=300))


# 预存 Bessel 闭式零点（golden 查表）
_CIRC_X = {
    (2, "TE"): 3.054236928,   # X'_21 = J2' 首零点
    (0, "TM"): 2.404825558,   # X_01  = J0  首零点
    (0, "TE"): 3.831705970,   # X'_01 = J0' 首零点
}

# brentq 安全括号（端点异号，首根落在内）
_CIRC_BRACKETS = {
    (2, "TE"): (0.1, 4.0),
    (0, "TM"): (0.1, 3.0),
    (0, "TE"): (0.1, 4.0),
}


def circ_wg_cutoff_fc(a: float, m: int, pol: str) -> float:
    """golden：圆波导 (m,pol) 截止频率（Hz）fc = X·c/(2πa)，X 为预存 Bessel 零点。"""
    return _CIRC_X[(m, pol)] * C0 / (2.0 * math.pi * a)


_CIRC_X_CACHE: dict = {}


def circ_wg_cutoff_fd(a: float, m: int, pol: str) -> float:
    """候选：圆波导 (m,pol) 截止频率（Hz），X 由径向 ODE 数值积分 + 边界根搜索得到。

    与 golden（预存 Bessel 零点查表）方法学不同源（场方程直接数值积分）。
    """
    key = (m, pol)
    if key not in _CIRC_X_CACHE:
        _CIRC_X_CACHE[key] = _circ_wg_cutoff_X(m, pol)
    kc = _CIRC_X_CACHE[key] / a
    return C0 * kc / (2.0 * math.pi)


# ===========================================================================
# 黄金闭式 / 候选（供 golden.py / verification_adapters.py 调用）
# ===========================================================================
# —— 氢原子径向（Z 默认 1；n=l+n_r+1）——
def golden_b89(Z=1.0):
    return hydrogen_E_rydberg(Z, 1)            # 1s: n=1


def golden_b90(Z=1.0):
    return hydrogen_E_rydberg(Z, 2)            # 2s: n=2


def golden_b91(Z=1.0):
    return hydrogen_E_rydberg(Z, 2)            # 2p: n=2


def golden_b92(Z=1.0):
    return hydrogen_E_rydberg(Z, 3)            # 3s: n=3


def golden_b93(Z=1.0):
    return hydrogen_E_rydberg(Z, 3)            # 3p: n=3


def golden_b94(Z=1.0):
    return hydrogen_E_rydberg(Z, 3)            # 3d: n=3


def cand_hydrogen(l, n_r, Z=1.0):
    return float(hydrogen_E_fd(Z, l, n_r))


# —— 3D 谐振子径向 ——
def golden_b95(hbar_omega):
    return ho3d_E_closed(0, 0, hbar_omega)     # l=0 基态


def golden_b96(hbar_omega):
    return ho3d_E_closed(0, 1, hbar_omega)     # l=1


def golden_b97(hbar_omega):
    return ho3d_E_closed(0, 2, hbar_omega)     # l=2


def cand_ho3d(n_r, l, hbar_omega):
    return float(ho3d_E_fd(n_r, l, hbar_omega))


# —— 圆波导截止频率族（复用 B-3 circ_wg 方法学）——
def golden_b98(a_nm):
    return circ_wg_cutoff_fc(a_nm * 1e-9, 2, "TE")     # TE21


def golden_b99(a_nm):
    return circ_wg_cutoff_fc(a_nm * 1e-9, 0, "TM")     # TM01


def golden_b100(a_nm):
    return circ_wg_cutoff_fc(a_nm * 1e-9, 0, "TE")     # TE01


def cand_circ(m, pol, a_nm):
    return float(circ_wg_cutoff_fd(a_nm * 1e-9, m, pol))


# —— 矩形波导高阶截止（复用 B-3）——
def golden_b101(a, b):
    return rect_wg_tm_fc(a, b, 1, 2)            # TE12


def golden_b102(a, b):
    return rect_wg_tm_fc(a, b, 2, 2)            # TE22


def golden_b103(a, b):
    return rect_wg_tm_fc(a, b, 3, 1)            # TE31


def golden_b104(a, b):
    return rect_wg_tm_fc(a, b, 1, 3)            # TE13


def cand_rect(m, n, a, b):
    return float(rect_wg_tm_fd(a, b, 700, 700, m, n))


if __name__ == "__main__":
    print("=== B89-B94 氢原子径向能级 (Z=1) ===")
    for bid, (l, nr) in (("B89", (0, 0)), ("B90", (0, 1)), ("B91", (1, 0)),
                          ("B92", (0, 2)), ("B93", (1, 1)), ("B94", (2, 0))):
        n = l + nr + 1
        g = hydrogen_E_rydberg(1.0, n)
        c = hydrogen_E_fd(1.0, l, nr)
        c2 = hydrogen_E_fd(1.1, l, nr)  # 判据 D：Z×1.1
        print(f"  {bid} (l={l},n_r={nr},n={n}): gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (Z×1.1->{c2:.6f})")

    print("=== B95-B97 3D 谐振子径向 (hbar_omega=0.5eV) ===")
    hw = 0.5 * EV
    for bid, (nr, l) in (("B95", (0, 0)), ("B96", (0, 1)), ("B97", (0, 2))):
        g = ho3d_E_closed(nr, l, hw)
        c = ho3d_E_fd(nr, l, hw)
        c2 = ho3d_E_fd(nr, l, hw * 1.1)
        print(f"  {bid} (n_r={nr},l={l}): gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (hw×1.1->{c2:.6f})")

    print("=== B98-B100 圆波导截止频率 (a=5mm) ===")
    aa = 5.0e-3
    for bid, (m, pol) in (("B98", (2, "TE")), ("B99", (0, "TM")), ("B100", (0, "TE"))):
        g = circ_wg_cutoff_fc(aa, m, pol) / 1e9
        c = circ_wg_cutoff_fd(aa, m, pol) / 1e9
        c2 = circ_wg_cutoff_fd(aa * 1.1, m, pol) / 1e9
        print(f"  {bid} (circ {pol}{m}): gold={g:.6f}GHz cand={c:.6f}GHz |d|={abs(c-g)/1e9:.2e}GHz  (a×1.1->{c2:.6f})")

    print("=== B101-B104 矩形波导高阶截止 (a=0.02286, b=0.01016) ===")
    a, b = 0.02286, 0.01016
    for bid, (m, n) in (("B101", (1, 2)), ("B102", (2, 2)), ("B103", (3, 1)), ("B104", (1, 3))):
        g = rect_wg_tm_fc(a, b, m, n) / 1e9
        c = rect_wg_tm_fd(a, b, 700, 700, m, n) / 1e9
        c2 = rect_wg_tm_fd(a * 1.1, b, 700, 700, m, n) / 1e9
        print(f"  {bid} (TE{m}{n}): gold={g:.6f}GHz cand={c:.6f}GHz |d|={abs(c-g)/1e9:.2e}GHz  (a×1.1->{c2:.6f})")
