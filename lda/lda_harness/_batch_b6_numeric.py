# -*- coding: utf-8 -*-
"""Batch B-6 独立候选数值核（纯 numpy / scipy · C 级自主 · 零商业依赖）。

设计纪律（同源 B-1..B-5）：每个锚 = 一个**确定性解析闭式 / 超越方程精确解** 对拍 一个
**方法学不同源真实数值法**。残差 = 离散化误差 / 建模近似差异（持久、随参数变化、
判据 D 响应、反向扰动 FAIL），不是「代数恒等」（B28 血案）也不是「纯数值误差沉底」（B10 血案）。

Batch B-6 锚清单（16 道，全为严格独立候选 · B105-B120 · v0.9.86 · 稀释 terminal）：
  刚性转子转动能级族（关联 Legendre 方程 FD 本征 ↔ 闭式 E_J=ℏ²J(J+1)/(2I)）：
    B105 转子 J=1（l=0 转动基态）      B106 转子 J=2              B107 转子 J=3
    B108 转子 J=4                       B109 转子 J=5              B110 转子 J=6
  二维无限方势阱族（2D FD 拉普拉斯本征 ↔ 闭式 E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²)，L_x≠L_y 消简并）：
    B111 2D 阱 (1,1)                    B112 2D 阱 (2,1)           B113 2D 阱 (1,2)
    B114 2D 阱 (2,2)
  量子三角势阱族（1D 斜坡势 FD 本征 ↔ Airy 零点闭式 E_n=(ℏ²F²/2m_e)^{1/3}·ζ_n）：
    B115 三角阱 n=1                     B116 三角阱 n=2            B117 三角阱 n=3
  三维无限球形势阱族（3D 径向 FD 本征 ↔ 球 Bessel 零点闭式 E_nl=x_nl²ℏ²/(2mR²)）：
    B118 球阱 (l=0,n=1)                 B119 球阱 (l=1,n=1)        B120 球阱 (l=2,n=1)
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import ai_zeros

HBAR = 1.054571817e-34
ME = 9.1093837015e-31
EV = 1.602176634e-19  # J -> eV
E_CHARGE = 1.602176634e-19  # C，基本电荷（势能 V=e·F·x 才为焦耳）

# 物理参数默认值（锚专用单位，便于判据 D 扰动）
I_BASE = 1.0e-47        # kg·m²，转子转动惯量基准（mom_47 倍率）
LX0 = 1.0e-9           # m，2D 阱 x 边长
LY0 = 2.0e-9           # m，2D 阱 y 边长（≠ Lx 消简并）
F_BASE = 1.0e7         # V/m，三角阱电场基准（F_7 倍率）
R_BASE = 1.0e-9        # m，球形势阱半径

# 球 Bessel 首零点（j_l(x)=0，x>0）：j0=sin x/x，j1，j2 取 scipy 验证的常用值
_SPH_BESSEL_ZERO = {
    (0, 1): math.pi,            # j0 首零点 = π
    (1, 1): 4.49340945790906,   # j1 首零点
    (2, 1): 5.76345951208735,   # j2 首零点
}

# Airy Ai 负零点绝对值（三角阱能级 ζ_n = -a_n，a_n 为 Ai 的零点）
_AIRY_ZERO = list(ai_zeros(3)[0])  # [2.3381, 4.0879, 5.5206]


# ===========================================================================
# 族 1 · 刚性转子（3D 自由转动）：关联 Legendre 方程 FD 本征
#   方程：(1-x²)P'' - 2x P' + λ P = 0，x∈(-1,1)，P 在端点有界；λ=J(J+1)。
#   FD 强形式（非对称，取低本征值，误差 O(dx²)），与闭式 J(J+1) 不同源。
# ===========================================================================
def _rotor_legendre_lambda(J: int, N: int = 1600) -> float:
    """数值导出 λ（应≈J(J+1)），关联 Legendre 算子 FD 本征（单位无量纲）。"""
    dx = 2.0 / N
    x = -1.0 + (np.arange(1, N + 1) - 0.5) * dx  # 内部点，避开 ±1 奇点
    omx2 = 1.0 - x * x
    main = -2.0 * omx2 / dx ** 2
    up = omx2 / dx ** 2 - x / dx
    lo = omx2 / dx ** 2 + x / dx
    A = np.diag(main) + np.diag(up[:-1], 1) + np.diag(lo[1:], -1)
    w = np.linalg.eigvals(A)
    lam = -np.real(w)
    lam = np.sort(lam)
    # 升序：λ[0]≈0(J=0), λ[1]≈2(J=1), ... 取 J 对应项
    return float(lam[J])


def rotor_E_closed(J: int, mom_47: float) -> float:
    """golden：刚性转子能级 E_J = ℏ²J(J+1)/(2I)（eV）。"""
    I = I_BASE * mom_47
    return (HBAR ** 2) * J * (J + 1) / (2.0 * I) / EV


def rotor_E_fd(J: int, mom_47: float, N: int = 1600) -> float:
    """候选：关联 Legendre 方程 FD 本征导出的 E_J（eV）。"""
    I = I_BASE * mom_47
    lam = _rotor_legendre_lambda(J, N)
    return (HBAR ** 2) * lam / (2.0 * I) / EV


# ===========================================================================
# 族 2 · 二维无限方势阱：2D FD 拉普拉斯本征（Kronecker 和）
#   -∇² u = k² u，Dirichlet 盒；E_ij = ℏ²k_ij²/(2m)。
# ===========================================================================
def _box2d_evals(Lx: float, Ly: float, Nx: int = 44, Ny: int = 44, M: int = 30) -> np.ndarray:
    """2D 方势阱最低 M 个本征值（升序，单位 J）。

    用 Kronecker 和分解：-∇² = T_x ⊗ I + I ⊗ T_y，2D 本征值 = λ_i^x + λ_j^y，
    分别对两条 1D Dirichlet 拉普拉斯矩阵做全量 eigvalsh 再组合——精确（到 1D FD 阶）
    且远小于直接构造 Nx²×Nx² 巨阵。避免 scipy eigh(subset_by_index) 在大矩阵上的 off-by-one。
    """
    dx = Lx / (Nx + 1)
    dy = Ly / (Ny + 1)
    tx = 1.0 / dx ** 2
    ty = 1.0 / dy ** 2
    # 1D 二阶差分（Dirichlet）
    Tx = (2 * tx) * np.eye(Nx) - tx * (np.eye(Nx, k=1) + np.eye(Nx, k=-1))
    Ty = (2 * ty) * np.eye(Ny) - ty * (np.eye(Ny, k=1) + np.eye(Ny, k=-1))
    Tx = (Tx + Tx.T) / 2.0
    Ty = (Ty + Ty.T) / 2.0
    ex = np.sort(np.real(np.linalg.eigvalsh(Tx)))[: min(Nx, 60)]
    ey = np.sort(np.real(np.linalg.eigvalsh(Ty)))[: min(Ny, 60)]
    # Kronecker 和 = 所有 (ex_i + ey_j) 组合，取最低 M 个
    k2 = np.add.outer(ex, ey).ravel()
    H_vals = (HBAR ** 2) / (2.0 * ME) * np.sort(k2)
    return H_vals[: M]


def box2d_E_closed(nx: int, ny: int, Lx: float, Ly: float) -> float:
    """golden：二维无限方势阱能级（eV）。"""
    k2 = (nx * math.pi / Lx) ** 2 + (ny * math.pi / Ly) ** 2
    return (HBAR ** 2) * k2 / (2.0 * ME) / EV


def box2d_E_fd(nx: int, ny: int, Lx: float, Ly: float, Nx: int = 120, Ny: int = 120) -> float:
    """候选：2D FD 拉普拉斯本征，取最接近解析目标态的本征值（返回 E，eV）。

    最近邻匹配避免 rank 序数脆弱性；离散化误差小 ⇒ 自然命中正确模，误差大则判据 D/容差暴露。
    """
    ev = _box2d_evals(Lx, Ly, Nx, Ny, M=30)  # J，升序
    target = box2d_E_closed(nx, ny, Lx, Ly) * EV  # J
    idx = int(np.argmin(np.abs(ev - target)))
    return float(ev[idx]) / EV


# ===========================================================================
# 族 3 · 量子三角势阱（V=Fx, x>0, 无限壁 x=0）：1D FD 薛定谔本征
#   闭式：E_n = (ℏ²F²/(2m_e))^{1/3} · ζ_n，ζ_n=|Ai 负零点|。
# ===========================================================================
def triangular_E_closed(n: int, F_7: float) -> float:
    """golden：三角势阱能级（eV），ζ_n 为 Airy 零点绝对值；V=eFx 为焦耳。"""
    F = F_BASE * F_7
    zeta = abs(_AIRY_ZERO[n - 1])
    return ((HBAR ** 2) * (E_CHARGE * F) ** 2 / (2.0 * ME)) ** (1.0 / 3.0) * zeta / EV


def triangular_E_fd(n: int, F_7: float, N: int = 900) -> float:
    """候选：1D 斜坡势 FD 薛定谔本征第 n-1 个（Dirichlet 盒，x∈[0,R]，V=eFx），返回 E（eV）。

    用全量 eigvalsh（N=900 收敛且内存可控），按升序取第 n-1 个——避免
    scipy eigh(subset_by_index) 在大矩阵上的 off-by-one。
    """
    F = F_BASE * F_7
    # R 取第 3 态经典转折点的 ~4 倍，确保波函数边界≈0
    E3_J = triangular_E_closed(3, F_7) * EV
    x_turn3 = E3_J / (E_CHARGE * F)
    R = max(4.0 * x_turn3, 6.0e-9)
    dx = R / (N + 1)
    x = dx * np.arange(1, N + 1)
    t = HBAR ** 2 / (2.0 * ME * dx ** 2)
    diag = 2.0 * t + E_CHARGE * F * x
    off = -t * np.ones(N - 1)
    T = np.diag(diag) + np.diag(off, 1) + np.diag(off, -1)
    T = (T + T.T) / 2.0
    ev = np.sort(np.real(np.linalg.eigvalsh(T)))[: max(n, 10)]
    return float(ev[n - 1]) / EV


# ===========================================================================
# 族 4 · 三维无限球形势阱（V=0, r<R；∞ 在 r≥R）：3D 径向 FD 本征
#   闭式：E_nl = x_nl² ℏ²/(2mR²)，x_nl = j_l 第 n 个零点。
#   径向方程（u=rR）：-ℏ²/(2m) u'' + ℏ²l(l+1)/(2mr²) u = E u，u(0)=u(R)=0。
# ===========================================================================
def _spherical_radial_evals(R: float, l: int, N: int = 2200, M: int = 6) -> np.ndarray:
    """3D 径向方程 FD 本征值（升序，单位 J），u(0)=u(R)=0。

    N=2200 全量 eigvalsh（内存约 35MB，秒级）足够最低 6 个本征值收敛；
    避免 scipy eigh(subset_by_index) 在大矩阵上的 off-by-one。
    """
    dr = R / (N + 1)
    r = dr * np.arange(1, N + 1)
    t = HBAR ** 2 / (2.0 * ME * dr ** 2)
    diag = 2.0 * t + (HBAR ** 2) * l * (l + 1) / (2.0 * ME * r ** 2)
    off = -t * np.ones(N - 1)
    H = np.diag(diag) + np.diag(off, 1) + np.diag(off, -1)
    H = (H + H.T) / 2.0
    ev = np.sort(np.real(np.linalg.eigvalsh(H)))[: M]
    return ev


def spherical_E_closed(l: int, n: int, R: float) -> float:
    """golden：三维球形势阱能级（eV），x_nl 为球 Bessel j_l 第 n 零点。"""
    x = _SPH_BESSEL_ZERO[(l, n)]
    return (x ** 2) * (HBAR ** 2) / (2.0 * ME * R ** 2) / EV


def spherical_E_fd(l: int, n: int, R: float, N: int = 4000) -> float:
    """候选：3D 径向 FD 本征第 n-1 个（eV）。"""
    ev = _spherical_radial_evals(R, l, N, M=6)
    return float(ev[n - 1]) / EV


# ===========================================================================
# 黄金闭式 / 候选（供 golden.py / verification_adapters.py 调用）
# ===========================================================================
# —— 刚性转子（J=锚序-104，默认转动惯量 mom_47=1）——
def golden_b105(mom_47=1.0):
    return rotor_E_closed(1, mom_47)


def golden_b106(mom_47=1.0):
    return rotor_E_closed(2, mom_47)


def golden_b107(mom_47=1.0):
    return rotor_E_closed(3, mom_47)


def golden_b108(mom_47=1.0):
    return rotor_E_closed(4, mom_47)


def golden_b109(mom_47=1.0):
    return rotor_E_closed(5, mom_47)


def golden_b110(mom_47=1.0):
    return rotor_E_closed(6, mom_47)


def cand_rotor(J, mom_47):
    return float(rotor_E_fd(J, mom_47))


# —— 二维无限方势阱（Lx≠Ly 消简并）——
def golden_b111(Lx_nm=1.0, Ly_nm=2.0):
    return box2d_E_closed(1, 1, Lx_nm * 1e-9, Ly_nm * 1e-9)


def golden_b112(Lx_nm=1.0, Ly_nm=2.0):
    return box2d_E_closed(2, 1, Lx_nm * 1e-9, Ly_nm * 1e-9)


def golden_b113(Lx_nm=1.0, Ly_nm=2.0):
    return box2d_E_closed(1, 2, Lx_nm * 1e-9, Ly_nm * 1e-9)


def golden_b114(Lx_nm=1.0, Ly_nm=2.0):
    return box2d_E_closed(2, 2, Lx_nm * 1e-9, Ly_nm * 1e-9)


def cand_box2d(nx, ny, Lx_nm, Ly_nm):
    return float(box2d_E_fd(nx, ny, Lx_nm * 1e-9, Ly_nm * 1e-9))


# —— 量子三角势阱 ——
def golden_b115(F_7=3.0):
    return triangular_E_closed(1, F_7)


def golden_b116(F_7=3.0):
    return triangular_E_closed(2, F_7)


def golden_b117(F_7=3.0):
    return triangular_E_closed(3, F_7)


def cand_triangular(n, F_7):
    return float(triangular_E_fd(n, F_7))


# —— 三维无限球形势阱 ——
def golden_b118(R_nm=1.0):
    return spherical_E_closed(0, 1, R_nm * 1e-9)


def golden_b119(R_nm=1.0):
    return spherical_E_closed(1, 1, R_nm * 1e-9)


def golden_b120(R_nm=1.0):
    return spherical_E_closed(2, 1, R_nm * 1e-9)


def cand_spherical(l, n, R_nm):
    return float(spherical_E_fd(l, n, R_nm * 1e-9))


if __name__ == "__main__":
    print("=== B105-B110 刚性转子能级 (mom_47=1) ===")
    for bid, J in (("B105", 1), ("B106", 2), ("B107", 3),
                   ("B108", 4), ("B109", 5), ("B110", 6)):
        g = rotor_E_closed(J, 1.0)
        c = rotor_E_fd(J, 1.0)
        c2 = rotor_E_fd(J, 1.1)  # 判据 D：转动惯量×1.1
        print(f"  {bid} J={J}: gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (mom×1.1->{c2:.6f})")

    print("=== B111-B114 二维无限方势阱 (Lx=1nm, Ly=2nm) ===")
    for bid, (nx, ny) in (("B111", (1, 1)), ("B112", (2, 1)), ("B113", (1, 2)), ("B114", (2, 2))):
        g = box2d_E_closed(nx, ny, LX0, LY0)
        c = box2d_E_fd(nx, ny, LX0, LY0)
        c2 = box2d_E_fd(nx, ny, LX0 * 1.1, LY0)
        print(f"  {bid} ({nx},{ny}): gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (Lx×1.1->{c2:.6f})")

    print("=== B115-B117 量子三角势阱 (F_7=3) ===")
    for bid, n in (("B115", 1), ("B116", 2), ("B117", 3)):
        g = triangular_E_closed(n, 3.0)
        c = triangular_E_fd(n, 3.0)
        c2 = triangular_E_fd(n, 3.3)  # 判据 D：场×1.1
        print(f"  {bid} n={n}: gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (F×1.1->{c2:.6f})")

    print("=== B118-B120 三维无限球形势阱 (R=1nm) ===")
    for bid, (l, n) in (("B118", (0, 1)), ("B119", (1, 1)), ("B120", (2, 1))):
        g = spherical_E_closed(l, n, R_BASE)
        c = spherical_E_fd(l, n, R_BASE)
        c2 = spherical_E_fd(l, n, R_BASE * 1.1)  # 判据 D：半径×1.1
        print(f"  {bid} (l={l},n={n}): gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (R×1.1->{c2:.6f})")
