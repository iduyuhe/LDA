# -*- coding: utf-8 -*-
"""Batch B-2 独立候选数值核（纯 numpy / scipy · C 级自主 · 零商业依赖）。

设计纪律（同源 B12/B22/B34-B41 的「闭式/解析 golden × 方法学不同源真数值」对拍）：
  每个锚 = 一个**确定性解析闭式 / 超越方程二分** 对拍 一个**不同源真实数值法**。
  残差 = 离散化误差 / 建模近似差异（持久、随参数变化、判据 D 响应、反向扰动 FAIL），
  不是「代数恒等」（B28 血案）也不是「纯数值误差沉底」（B10 血案）。

Batch B-2 锚清单（12 道，全为严格独立候选）：
  B42 一维无限深方势阱 基态 E1      —— 量子力学闭式 E1=ℏ²π²/(2mL²) vs 1D FD 哈密顿本征值(基态)
  B43 一维无限深方势阱 第2能级 E2  —— 闭式 4×E1 vs 1D FD 哈密顿本征值(第2模)
  B44 一维无限深方势阱 第3能级 E3  —— 闭式 9×E1 vs 1D FD 哈密顿本征值(第3模)
  B45 一维谐振子 基态 E0            —— 闭式 ½ℏω vs 1D FD 谐振子哈密顿本征值(基态)
  B46 一维谐振子 第1激发态 E1       —— 闭式 1.5ℏω vs 1D FD(第2模)
  B47 一维谐振子 第2激发态 E2       —— 闭式 2.5ℏω vs 1D FD(第3模)
  B48 一维有限深方势阱 基态         —— 偶宇称超越方程二分 vs 1D FD 哈密顿本征值(基态)
  B49 方势垒透射系数 T（E<V0 隧穿） —— 闭式 sinh 公式 vs 1D FD 转移矩阵离散散射
  B50 矩形金属波导 TE30 截止频率    —— 3c/(2a) 闭式 vs 1D Dirichlet 盒 FD 本征(mode=3)
  B51 矩形金属波导 TE40 截止频率    —— 2c/a 闭式 vs 1D Dirichlet 盒 FD 本征(mode=4)
  （2D FD 传输线 Z0 候选见文件末尾 B52/B53 段，独立追加后经标定启用）

注：1D FD 数值核与 B36/B37 的 TL 本征核同源（Dirichlet 盒），但物理对象不同
（量子能级 vs 波导截止），golden 来自不同物理定律闭式，方法学不同源；
判据 D 由 B12/B22 已证（离散网格 N 为真参数，收敛性可测）。
"""
from __future__ import annotations

import math

import numpy as np
from scipy.linalg import eigh

C0 = 299792458.0
HBAR = 1.054571817e-34
ME = 9.1093837015e-31
EV = 1.602176634e-19  # J -> eV

# ===========================================================================
# 1D FD 薛定谔哈密顿本征求解器（Dirichlet 盒，升序本征值：w[0]=基态）
# ===========================================================================
def _fd1d_sch_evals(L: float, N: int, m: float, V_func) -> np.ndarray:
    """1D 定态薛定谔 -ℏ²/2m·ψ'' + V(x)ψ = Eψ 的 FD 本征值（升序）。"""
    dx = L / (N + 1)
    x = -L / 2.0 + dx * np.arange(1, N + 1)
    diag = 2.0 / (dx * dx) * np.ones(N)
    off = -1.0 / (dx * dx) * np.ones(N - 1)
    T = (HBAR ** 2 / (2.0 * m)) * (
        np.diag(diag) + np.diag(off, 1) + np.diag(off, -1)
    )
    V = np.diag(np.asarray(V_func(x), dtype=float))
    H = T + V
    H = (H + H.T) / 2.0
    return eigh(H, eigvals_only=True)  # 升序


# ===========================================================================
# B42-B44 · 一维无限深方势阱（V=0 内，∞ 外）
# ===========================================================================
def qmw_infinite_well_E(n: int, m: float, L: float) -> float:
    """解析闭式（J）：E_n = n²π²ℏ²/(2mL²)。"""
    return (HBAR ** 2) * (math.pi ** 2) * (n ** 2) / (2.0 * m * (L ** 2))


def qmw_infinite_well_fd(L: float, N: int, m: float, n: int) -> float:
    """候选：1D FD 哈密顿本征值（盒内 V=0）第 n 能级（eV）。"""
    e_j = float(_fd1d_sch_evals(L, N, m, lambda x: np.zeros_like(x))[n - 1])
    return e_j / EV


# ===========================================================================
# B45-B47 · 一维谐振子（V=½mω²x²）
# ===========================================================================
def qm_ho_E(n: int, hbar_omega: float) -> float:
    """解析闭式（J）：E_n = (n+½)ℏω。"""
    return (n + 0.5) * hbar_omega


def qm_ho_fd_n(hbar_omega: float, m: float, n: int, N: int = 800) -> float:
    """候选：1D FD 谐振子哈密顿本征值第 n 模（eV）。"""
    omega = hbar_omega / HBAR
    sigma = math.sqrt(HBAR / (m * omega))
    L = 14.0 * sigma
    V_func = lambda x: 0.5 * m * omega ** 2 * x ** 2
    e_j = float(_fd1d_sch_evals(L, N, m, V_func)[n])
    return e_j / EV


# ===========================================================================
# B48 · 一维有限深方势阱（阱内 V=-V0，阱外 0）基态
# ===========================================================================
def qm_finwell_E_analytic(V0: float, a: float, m: float) -> float:
    """golden：一维有限深方势阱（V=-V0 内，0 外）偶宇称基态能量（J）。

    无量纲化消去 tan 奇点：令 z = a·√(2mV0)/(2ℏ)，偶宇称基态满足
    u = z·cos(u)，u∈(0,π/2)。
    对 g(u)=u - z·cos(u) 在 (0,π/2) 二分（g(0)=-z<0，g(π/2)=π/2>0），
    稳健定位基态，再回代 k=2u/a、E=ℏ²k²/(2m)-V0。
    """
    z = a * math.sqrt(2.0 * m * V0) / (2.0 * HBAR)
    lo, hi = 1e-9, math.pi / 2.0 - 1e-9
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mid - z * math.cos(mid) < 0:
            lo = mid
        else:
            hi = mid
    u = 0.5 * (lo + hi)
    k = 2.0 * u / a
    return (HBAR ** 2) * (k ** 2) / (2.0 * m) - V0


def qm_finwell_fd(V0: float, a: float, m: float, L: float, N: int = 800) -> float:
    """候选：1D FD 哈密顿本征值基态（eV）。盒长 L 远大于阱宽 a。"""
    def V_func(x):
        return np.where(np.abs(x) <= a / 2.0, -V0, 0.0)
    e_j = float(_fd1d_sch_evals(L, N, m, V_func)[0])
    return e_j / EV


# ===========================================================================
# B49 · 方势垒透射系数 T（E<V0 隧穿）
# ===========================================================================
def barrier_transmit_analytic(E: float, V0: float, a: float, m: float) -> float:
    """golden：闭式 T = 1/(1 + V0²·sinh²(κa)/(4E(V0-E)))，κ=√[2m(V0-E)]/ℏ。"""
    kappa = math.sqrt(2.0 * m * (V0 - E)) / HBAR
    return 1.0 / (1.0 + (V0 ** 2) * (math.sinh(kappa * a) ** 2) / (4.0 * E * (V0 - E)))


def _numerov_fwd(k2: np.ndarray, h: float, psi0: complex, dpsi0: complex) -> np.ndarray:
    """Numerov 正向（x₀→x_N）外推单个解 ψ''=-k²(x)ψ；返回 ψ[0..N]。

    a_n=1+h²k²_n/12, b_n=2(1+5h²k²_n/12)=2+5h²k²_n/6；
    递推 a_{n+1}ψ_{n+1}=b_n ψ_n - a_{n-1}ψ_{n-1}。初值 ψ_1=ψ_0+hψ'_0-h²k²_0ψ_0/2。
    """
    N = len(k2) - 1
    a = 1.0 + (h * h / 12.0) * k2
    b = 2.0 - (5.0 * h * h / 6.0) * k2
    psi = np.zeros(N + 1, dtype=complex)
    psi[0] = psi0
    psi[1] = psi0 + h * dpsi0 - 0.5 * (h * h) * k2[0] * psi0
    for n in range(1, N):
        psi[n + 1] = (b[n] * psi[n] - a[n - 1] * psi[n - 1]) / a[n + 1]
    return psi


def _numerov_bwd(k2: np.ndarray, h: float, psiN: complex, dpsiN: complex) -> np.ndarray:
    """Numerov 反向（x_N→x₀）外推单个解 ψ''=-k²(x)ψ；返回 ψ[0..N]。"""
    N = len(k2) - 1
    a = 1.0 + (h * h / 12.0) * k2
    b = 2.0 - (5.0 * h * h / 6.0) * k2
    psi = np.zeros(N + 1, dtype=complex)
    psi[N] = psiN
    psi[N - 1] = psiN - h * dpsiN - 0.5 * (h * h) * k2[N] * psiN
    for n in range(N - 1, 0, -1):
        psi[n - 1] = (b[n] * psi[n] - a[n + 1] * psi[n + 1]) / a[n - 1]
    return psi


def barrier_transmit_fd(E: float, V0: float, a: float, m: float, X: float | None = None, N: int = 2000) -> float:
    """候选：1D FD 中心匹配双基 Numerov 散射求透射系数 T（与闭式双曲公式方法学不同源）。

    在网格上离散 ψ''=-k²(x)ψ：从两端各外推两个基解（e^{±ikx} 在左/右端），
    在屏障中心 x_c 做 ψ 与 ψ' 的连续性匹配，解出反射 B、透射 C，T=|C|²。
    匹配点取在屏障内部，所有量均 O(1)，数值条件稳定（Numerov 对隧穿区非病态）；
    残差=离散化误差（随 N 收敛、随 a 变化、判据 D 响应）。
    """
    if E <= 0.0:
        return 0.0
    k_free = math.sqrt(2.0 * m * E) / HBAR
    k2_free = k_free ** 2
    if X is None:
        X = max(8.0 * a, 20.0 / k_free)
    h = (2.0 * X) / N
    x = -X + h * np.arange(N + 1)
    k2 = np.where(np.abs(x) <= a / 2.0, 2.0 * m * (E - V0) / HBAR ** 2, k2_free)
    c = N // 2  # 屏障中心（≈x=0）
    y1 = _numerov_fwd(k2, h, 1.0, 1j * k_free)   # 左端入射基 e^{ikx}
    y2 = _numerov_fwd(k2, h, 1.0, -1j * k_free)  # 左端反射基 e^{-ikx}
    z1 = _numerov_bwd(k2, h, 1.0, 1j * k_free)   # 右端出射基 e^{ikx}
    z2 = _numerov_bwd(k2, h, 1.0, -1j * k_free)  # 右端入射基 e^{-ikx}（D=0）
    y1c, y2c, z1c = y1[c], y2[c], z1[c]
    y1p = (y1[c + 1] - y1[c - 1]) / (2.0 * h)
    y2p = (y2[c + 1] - y2[c - 1]) / (2.0 * h)
    z1p = (z1[c + 1] - z1[c - 1]) / (2.0 * h)
    ratio = z1p / z1c
    B = (y1c * ratio - y1p) / (y2p - y2c * ratio)
    C = (y1c + B * y2c) / z1c
    return abs(C) ** 2


# ===========================================================================
# B50/B51 · 矩形波导高阶 TE 模截止（1D Dirichlet 盒 FD 本征，复用 B36/B37 核）
# ===========================================================================
def _fd1d_box_kc(a: float, n: int, mode: int = 1) -> float:
    """1D Dirichlet 盒第 mode 个最弱本征模空间波数（FD 本征值）。"""
    dx = a / (n + 1)
    L = np.diag(np.full(n, -2.0)) + np.diag(np.ones(n - 1), 1) + np.diag(np.ones(n - 1), -1)
    A = (1.0 / dx ** 2) * L
    w = eigh(A, eigvals_only=True)
    return math.sqrt(-float(w[-mode]))


def rect_wg_te30_fc(a: float, n: int = 600) -> float:
    """矩形波导 TE30 截止频率（Hz）：kc=3π/a ⇒ fc=3c/(2a)。"""
    return C0 * _fd1d_box_kc(a, n, mode=3) / (2.0 * math.pi)


def rect_wg_te40_fc(a: float, n: int = 600) -> float:
    """矩形波导 TE40 截止频率（Hz）：kc=4π/a ⇒ fc=2c/a。"""
    return C0 * _fd1d_box_kc(a, n, mode=4) / (2.0 * math.pi)


# ===========================================================================
# 黄金闭式（供 golden.py 调用；与候选方法学不同源）
# ===========================================================================
def golden_b42(m, L):
    return qmw_infinite_well_E(1, m, L) / EV


def golden_b43(m, L):
    return qmw_infinite_well_E(2, m, L) / EV


def golden_b44(m, L):
    return qmw_infinite_well_E(3, m, L) / EV


def golden_b45(hbar_omega):
    return qm_ho_E(0, hbar_omega) / EV


def golden_b46(hbar_omega):
    return qm_ho_E(1, hbar_omega) / EV


def golden_b47(hbar_omega):
    return qm_ho_E(2, hbar_omega) / EV


def golden_b48(V0, a, m):
    return qm_finwell_E_analytic(V0, a, m) / EV


def golden_b49(E, V0, a, m):
    return barrier_transmit_analytic(E, V0, a, m)


def golden_b50(a):
    return 3.0 * C0 / (2.0 * a)


def golden_b51(a):
    return 2.0 * C0 / a


if __name__ == "__main__":
    print("=== B42-B44 无限深势阱 (m=me, L=1nm) ===")
    L, M = 1e-9, ME
    for n in (1, 2, 3):
        g = qmw_infinite_well_E(n, M, L) / EV
        c = qmw_infinite_well_fd(L, 600, M, n)
        print(f"  n={n}: gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (perturb Lx1.1 -> {qmw_infinite_well_fd(L*1.1,600,M,n):.6f})")

    print("=== B45-B47 谐振子 (hbar_omega=5.27e-20 J) ===")
    hw = 5.27e-20
    for n in (0, 1, 2):
        g = qm_ho_E(n, hw) / EV
        c = qm_ho_fd_n(hw, ME, n)
        print(f"  n={n}: gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV")

    print("=== B48 有限深势阱 (V0=0.5eV, a=1nm, m=me, L=10nm) ===")
    V0, a, Lb = 0.5 * EV, 1e-9, 1e-8
    g = qm_finwell_E_analytic(V0, a, ME) / EV
    c = qm_finwell_fd(V0, a, ME, Lb)
    print(f"  gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (perturb V0x1.1 -> {qm_finwell_fd(V0*1.1,a,ME,Lb):.6f})")

    print("=== B49 方势垒透射 (E=0.1eV, V0=0.3eV, a=0.5nm, m=me) ===")
    E, V0b, ab = 0.1 * EV, 0.3 * EV, 5e-10
    g = barrier_transmit_analytic(E, V0b, ab, ME)
    c = barrier_transmit_fd(E, V0b, ab, ME)
    print(f"  gold={g:.6f} cand={c:.6f} |d|={abs(c-g):.2e}  (perturb ax1.1 -> {barrier_transmit_fd(E,V0b,ab*1.1,ME):.6f})")

    print("=== B50/B51 矩形波导 TE30/TE40 (a=0.02286m) ===")
    aa = 0.02286
    for name, gfn, cfn in (("TE30", golden_b50, rect_wg_te30_fc), ("TE40", golden_b51, rect_wg_te40_fc)):
        g = gfn(aa) / 1e9
        c = cfn(aa) / 1e9
        print(f"  {name}: gold={g:.6f}GHz cand={c:.6f}GHz |d|={abs(c-g)/1e9:.2e}GHz  (perturb ax1.1 -> {cfn(aa*1.1)/1e9:.6f})")
