# -*- coding: utf-8 -*-
"""Batch B-7 独立候选数值核（纯 numpy / scipy · C 级自主 · 零商业依赖）。

设计纪律（同源 B-1..B-6）：每个锚 = 一个**确定性解析闭式 / 超越方程精确解** 对拍 一个
**方法学不同源真实数值法**。残差 = 离散化误差 / 建模近似差异（持久、随参数变化、
判据 D 响应、反向扰动 FAIL），不是「代数恒等」（B28 血案）也不是「纯数值误差沉底」（B10 血案）。

🔴 本批不复用 scipy `eigh(subset_by_index=...)`（B-6 血案：大矩阵 off-by-one 静默返回第 2 低本征）
   —— 一律「较小网格 + 全量 `np.linalg.eigvalsh` / 全量 `scipy.linalg.eigh`」或
   Kronecker 和分解（1D 本征值组合），杜绝子集选择。

Batch B-7 锚清单（16 道，全为严格独立候选 · B121-B136 · v0.9.87 · 腿① 续加锚稀释 terminal）：
  Morse 势双原子分子振动族（1D FD 薛定谔本征 ↔ 解析非谐谱 E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e)）：
    B121 Morse n=0                      B122 Morse n=1             B123 Morse n=2
    B124 Morse n=3
  二维各向异性谐振子族（2D FD 本征 Kronecker 和 ↔ 闭式 E=ℏω_x(n_x+½)+ℏω_y(n_y+½)，ω_x≠ω_y）：
    B125 2D-HO (0,0)                    B126 2D-HO (1,0)           B127 2D-HO (0,1)
    B128 2D-HO (1,1)
  三维长方体无限深势阱族（3D FD 拉普拉斯 Kronecker 和 ↔ 闭式 E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²)，L_x≠L_y≠L_z）：
    B129 3D 阱 (1,1,1)                  B130 3D 阱 (2,1,1)         B131 3D 阱 (1,2,1)
    B132 3D 阱 (1,1,2)
  类氢离子激发态族（径向 FD 本征 ↔ Rydberg 闭式 E=−RYDBERG·Z²/n²，n=4/5 高激发 + 高 l 离心项）：
    B133 H 4s  (Z=1,l=0,n=4)            B134 He⁺ 4d (Z=2,l=2,n=4)
    B135 Li²⁺ 4f (Z=3,l=3,n=4)          B136 H 5d  (Z=1,l=2,n=5)
"""
from __future__ import annotations

import math

import numpy as np

# 复用 Batch B-5 已验证氢原子径向核（判据 D 由 run_d_criterion_smoke 已证）
try:
    from ._batch_b5_numeric import (
        hydrogen_E_rydberg,
        hydrogen_E_fd,
    )
except ImportError:  # 直接运行本文件时回退
    from _batch_b5_numeric import (  # type: ignore
        hydrogen_E_rydberg,
        hydrogen_E_fd,
    )

HBAR = 1.054571817e-34
ME = 9.1093837015e-31
EV = 1.602176634e-19  # J -> eV

# ===========================================================================
# 族 1 · Morse 势双原子分子振动
#   V(r) = D_e·(1 − e^{−a(r−r_e)})²，解析谱 E_n = ℏω(n+½) − [ℏω(n+½)]²/(4D_e)，
#   ω = a·√(2D_e/μ)（非谐修正项为 Morse 势特征，非谐振子简谐极限）。
#   候选 = 1D FD 薛定谔本征（Dirichlet 盒 [0,R]），与解析谱方法学不同源。
# ===========================================================================
MORSE_MU = 1.1385e-26      # kg，约化质量（CO 分子量级）
MORSE_DE_EV = 11.2         # eV，解离能 D_e
MORSE_A = 2.3e10           # 1/m，势宽参数 a
MORSE_RE = 1.13e-10        # m，平衡键长 r_e


def _morse_V(de_ev: float, r: np.ndarray) -> np.ndarray:
    de = de_ev * EV
    return de * (1.0 - np.exp(-MORSE_A * (r - MORSE_RE))) ** 2


def morse_E_closed(n: int, de_ev: float) -> float:
    """golden：Morse 势振动能级（eV，含非谐修正）。"""
    de = de_ev * EV
    hw = HBAR * MORSE_A * math.sqrt(2.0 * de / MORSE_MU)  # ℏω
    x = hw * (n + 0.5)
    return (x - x * x / (4.0 * de)) / EV


def morse_E_fd(n: int, de_ev: float, N: int = 3000, R: float = 8.0e-10) -> float:
    """候选：1D FD 薛定谔本征第 n 个束缚态（eV），V=Morse 势，Dirichlet 盒 [0,R]。"""
    dx = R / (N + 1)
    r = dx * np.arange(1, N + 1)
    t = HBAR ** 2 / (2.0 * MORSE_MU * dx ** 2)
    diag = 2.0 * t + _morse_V(de_ev, r)
    off = -t * np.ones(N - 1)
    H = np.diag(diag) + np.diag(off, 1) + np.diag(off, -1)
    H = (H + H.T) / 2.0
    ev = np.sort(np.real(np.linalg.eigvalsh(H)))[: max(n + 1, 10)]
    return float(ev[n]) / EV


# ===========================================================================
# 族 2 · 二维各向异性谐振子
#   V = ½m(ω_x²x² + ω_y²y²)，闭式 E = ℏω_x(n_x+½) + ℏω_y(n_y+½)。
#   候选 = 2D FD 本征（两 1D FD 谐振子本征值 Kronecker 和），与闭式不同源。
# ===========================================================================
M_STAR = 0.067 * ME        # kg，GaAs 电子有效质量
OMEGA_X = 1.0e15           # rad/s
OMEGA_Y = 1.4e15           # rad/s


def _ho1d_evals(omega: float, N: int = 500, M: int = 20) -> np.ndarray:
    """1D 谐振子 FD 本征值（升序，单位 J），Dirichlet 盒 [−L/2, L/2]，L=12·a_osc。"""
    a_osc = math.sqrt(HBAR / (M_STAR * omega))
    L = 12.0 * a_osc
    dx = L / (N + 1)
    x = -L / 2.0 + dx * np.arange(1, N + 1)
    t = HBAR ** 2 / (2.0 * M_STAR * dx ** 2)
    diag = 2.0 * t + 0.5 * M_STAR * omega ** 2 * x ** 2
    off = -t * np.ones(N - 1)
    H = np.diag(diag) + np.diag(off, 1) + np.diag(off, -1)
    H = (H + H.T) / 2.0
    return np.sort(np.real(np.linalg.eigvalsh(H)))[:M]


def _ho2d_evals(ox: float, oy: float, M: int = 20) -> np.ndarray:
    """2D 各向异性谐振子最低 M 个本征值（升序，单位 J）= 1D 本征值 Kronecker 和。"""
    ex = _ho1d_evals(ox, M=20)
    ey = _ho1d_evals(oy, M=20)
    return np.sort(np.add.outer(ex, ey).ravel())[:M]


def ho2d_E_closed(nx: int, ny: int, ox: float, oy: float) -> float:
    """golden：2D 各向异性谐振子能级（eV）。"""
    return (HBAR * ox * (nx + 0.5) + HBAR * oy * (ny + 0.5)) / EV


def ho2d_E_fd(nx: int, ny: int, ox: float, oy: float) -> float:
    """候选：2D FD 本征取最接近解析目标态者（eV），最近邻匹配避免 rank 脆弱性。"""
    ev = _ho2d_evals(ox, oy, M=20)  # J，升序
    target = ho2d_E_closed(nx, ny, ox, oy) * EV  # J
    idx = int(np.argmin(np.abs(ev - target)))
    return float(ev[idx]) / EV


# ===========================================================================
# 族 3 · 三维长方体无限深势阱（L_x≠L_y≠L_z）
#   -∇²u = k²u，Dirichlet 盒；E = (π²ℏ²/2m)(n_x²/L_x² + n_y²/L_y² + n_z²/L_z²)。
#   候选 = 3D FD 拉普拉斯 Kronecker 和（1D Dirichlet 本征值三路组合）。
# ===========================================================================
L1 = 1.0e-9                # m，x 边长
L2 = 1.5e-9                # m，y 边长
L3 = 2.0e-9                # m，z 边长


def _lap1d_evals(L: float, N: int = 200) -> np.ndarray:
    """1D Dirichlet 拉普拉斯 −d²/dx² 最低本征值（升序，单位 1/m²）。"""
    dx = L / (N + 1)
    t = 1.0 / dx ** 2
    T = (2.0 * t) * np.eye(N) - t * (np.eye(N, k=1) + np.eye(N, k=-1))
    T = (T + T.T) / 2.0
    return np.sort(np.real(np.linalg.eigvalsh(T)))[: min(N, 50)]


def _box3d_evals(a: float, b: float, c: float, M: int = 30) -> np.ndarray:
    """3D 长方体势阱最低 M 个本征值（升序，单位 J）。"""
    ex = _lap1d_evals(a)
    ey = _lap1d_evals(b)
    ez = _lap1d_evals(c)
    s = np.add.outer(np.add.outer(ex, ey).ravel(), ez).ravel()
    return (HBAR ** 2) / (2.0 * ME) * np.sort(s)[:M]


def box3d_E_closed(nx: int, ny: int, nz: int, a: float, b: float, c: float) -> float:
    """golden：三维长方体无限深势阱能级（eV）。"""
    k2 = (nx * math.pi / a) ** 2 + (ny * math.pi / b) ** 2 + (nz * math.pi / c) ** 2
    return (HBAR ** 2) * k2 / (2.0 * ME) / EV


def box3d_E_fd(nx: int, ny: int, nz: int, a: float, b: float, c: float) -> float:
    """候选：3D FD 拉普拉斯本征取最接近解析目标态者（eV）。"""
    ev = _box3d_evals(a, b, c, M=30)  # J，升序
    target = box3d_E_closed(nx, ny, nz, a, b, c) * EV  # J
    idx = int(np.argmin(np.abs(ev - target)))
    return float(ev[idx]) / EV


# ===========================================================================
# 族 4 · 类氢离子激发态（n=4/5 高激发 + 高 l 离心项）
#   golden：Rydberg 闭式 E_n = −RYDBERG·Z²/n²（eV）；cand：径向 FD 本征（复用 B-5 核）。
#   n_r = n − l − 1 为径向节点数（FD 升序第 n_r 态的物理口径）。
# ===========================================================================
def cand_hydrogen(l: int, n_r: int, Z: float) -> float:
    """候选：类氢径向 FD 薛定谔本征第 n_r 态（eV）。"""
    return float(hydrogen_E_fd(Z, l, n_r))


# ===========================================================================
# 黄金闭式 / 候选（供 golden.py / verification_adapters.py 调用）
# ===========================================================================
# —— Morse 势分子振动（默认 D_e=11.2 eV）——
def golden_b121(de_ev=MORSE_DE_EV):
    return morse_E_closed(0, de_ev)


def golden_b122(de_ev=MORSE_DE_EV):
    return morse_E_closed(1, de_ev)


def golden_b123(de_ev=MORSE_DE_EV):
    return morse_E_closed(2, de_ev)


def golden_b124(de_ev=MORSE_DE_EV):
    return morse_E_closed(3, de_ev)


def cand_morse(n, de_ev):
    return float(morse_E_fd(n, de_ev))


# —— 2D 各向异性谐振子（ω_x≠ω_y）——
def golden_b125(ox=OMEGA_X, oy=OMEGA_Y):
    return ho2d_E_closed(0, 0, ox, oy)


def golden_b126(ox=OMEGA_X, oy=OMEGA_Y):
    return ho2d_E_closed(1, 0, ox, oy)


def golden_b127(ox=OMEGA_X, oy=OMEGA_Y):
    return ho2d_E_closed(0, 1, ox, oy)


def golden_b128(ox=OMEGA_X, oy=OMEGA_Y):
    return ho2d_E_closed(1, 1, ox, oy)


def cand_ho2d(nx, ny, ox, oy):
    return float(ho2d_E_fd(nx, ny, ox, oy))


# —— 3D 长方体势阱（L_x≠L_y≠L_z）——
def golden_b129(a=L1, b=L2, c=L3):
    return box3d_E_closed(1, 1, 1, a, b, c)


def golden_b130(a=L1, b=L2, c=L3):
    return box3d_E_closed(2, 1, 1, a, b, c)


def golden_b131(a=L1, b=L2, c=L3):
    return box3d_E_closed(1, 2, 1, a, b, c)


def golden_b132(a=L1, b=L2, c=L3):
    return box3d_E_closed(1, 1, 2, a, b, c)


def cand_box3d(nx, ny, nz, a, b, c):
    return float(box3d_E_fd(nx, ny, nz, a, b, c))


# —— 类氢离子激发态（n=4/5，高 l 离心项）——
def golden_b133(Z=1.0):
    return hydrogen_E_rydberg(Z, 4)


def golden_b134(Z=2.0):
    return hydrogen_E_rydberg(Z, 4)


def golden_b135(Z=3.0):
    return hydrogen_E_rydberg(Z, 4)


def golden_b136(Z=1.0):
    return hydrogen_E_rydberg(Z, 5)


if __name__ == "__main__":
    print("=== B121-B124 Morse 势分子振动 (De=11.2eV) ===")
    for bid, n in (("B121", 0), ("B122", 1), ("B123", 2), ("B124", 3)):
        g = morse_E_closed(n, MORSE_DE_EV)
        c = morse_E_fd(n, MORSE_DE_EV)
        c2 = morse_E_fd(n, MORSE_DE_EV * 1.1)  # 判据 D：De×1.1
        print(f"  {bid} n={n}: gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (De×1.1->{c2:.6f})")

    print("=== B125-B128 2D 各向异性谐振子 (wx=1.0e15, wy=1.4e15) ===")
    for bid, (nx, ny) in (("B125", (0, 0)), ("B126", (1, 0)), ("B127", (0, 1)), ("B128", (1, 1))):
        g = ho2d_E_closed(nx, ny, OMEGA_X, OMEGA_Y)
        c = ho2d_E_fd(nx, ny, OMEGA_X, OMEGA_Y)
        c2 = ho2d_E_fd(nx, ny, OMEGA_X * 1.1, OMEGA_Y)  # 判据 D：ωx×1.1
        print(f"  {bid} ({nx},{ny}): gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (wx×1.1->{c2:.6f})")

    print("=== B129-B132 3D 长方体势阱 (L=1.0/1.5/2.0 nm) ===")
    for bid, (nx, ny, nz) in (("B129", (1, 1, 1)), ("B130", (2, 1, 1)),
                              ("B131", (1, 2, 1)), ("B132", (1, 1, 2))):
        g = box3d_E_closed(nx, ny, nz, L1, L2, L3)
        c = box3d_E_fd(nx, ny, nz, L1, L2, L3)
        c2 = box3d_E_fd(nx, ny, nz, L1 * 1.1, L2, L3)  # 判据 D：Lx×1.1
        print(f"  {bid} ({nx},{ny},{nz}): gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (Lx×1.1->{c2:.6f})")

    print("=== B133-B136 类氢离子激发态 ===")
    for bid, (Z, l, n, n_r) in (("B133", (1.0, 0, 4, 3)), ("B134", (2.0, 2, 4, 1)),
                                ("B135", (3.0, 3, 4, 0)), ("B136", (1.0, 2, 5, 2))):
        g = hydrogen_E_rydberg(Z, n)
        c = hydrogen_E_fd(Z, l, n_r)
        c2 = hydrogen_E_fd(Z * 1.1, l, n_r)  # 判据 D：Z×1.1
        print(f"  {bid} Z={Z} l={l} n={n}: gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (Z×1.1->{c2:.6f})")
