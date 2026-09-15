# -*- coding: utf-8 -*-
"""Batch B-1 独立候选数值核（纯 numpy / scipy · C 级自主 · 零商业依赖）。

设计纪律（同源 B12/B22 的 FD 本征路线 + B2 的「闭式近似 vs 严格数值」对拍）：
  每个锚 = 一个**确定性解析闭式 / 近似黄金** 对拍 一个**方法学不同源的真实数值法**。
  残差 = 建模 / 离散差异（持久、随参数变化、判据 D 响应、反向扰动 FAIL），
  不是「代数恒等」（B28 血案）也不是「纯数值误差沉底」（B10 血案）。

Batch B-1 锚清单（5 道，全为严格独立候选）：
  B34 条形介质波导 TE0 有效折射率 —— Marcatili 闭式近似 vs 严格横向谐振超越方程二分
  B36 矩形金属波导 TE10 截止频率 —— c/(2a) 闭式 vs 1D FD 本征值（基模）
  B37 矩形金属波导 TE20 截止频率 —— c/a 闭式 vs 1D FD 本征值（第二模）
  B40 矩形金属波导 TE11 截止频率 —— c/(2π)√((π/a)²+(π/b)²) 闭式 vs 2D FD 本征值
  B41 Fabry-Pérot 1D 腔谐振波长 —— 2nL/m 闭式 vs 1D FD 本征值（腔模）

注：B36/B37/B41 复用同一 1D FD 本征核（与 B12/B22 的 TL 本征核同源），
判据 D 的离散化响应性由 run_d_criterion_smoke（B12/B22）已证；B34 为超越方程
二分（无离散参数，判据 D 不适用，同 B9 闭式互证先例，于 note 论证）。
"""
from __future__ import annotations

import math

import numpy as np

C0 = 299792458.0          # m/s


# ===========================================================================
# B34 · 条形介质波导 TE0 有效折射率（Marcatili 近似 vs 严格超越方程二分）
# ===========================================================================
def marcatili_slab_neff(n_f: float, n_c: float, t: float, wl: float) -> float:
    """Marcatili 一阶等效宽度近似（TE0，对称条形波导）。"""
    k0 = 2.0 * math.pi / wl
    d = 1.0 / (k0 * math.sqrt(n_f * n_f - n_c * n_c))
    w_eff = t + 2.0 * d
    val = n_f * n_f - (wl / (2.0 * w_eff)) ** 2
    return math.sqrt(val) if val > 0 else float(n_c)


def _slab_phase(n_f, n_c, t, wl, neff):
    k0 = 2.0 * math.pi / wl
    a = math.sqrt(max(n_f * n_f - neff * neff, 1e-30))
    b = math.sqrt(max(neff * neff - n_c * n_c, 1e-30))
    return k0 * a * (t / 2.0) - (math.pi / 2.0 - math.atan(a / b))


def exact_slab_neff(n_f: float, n_c: float, t: float, wl: float) -> float:
    """严格 TE0 n_eff（横向谐振超越方程二分，候选求解器）。"""
    lo, hi = n_c + 1e-6, n_f - 1e-6
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if _slab_phase(n_f, n_c, t, wl, mid) > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ===========================================================================
# 1D / 2D FD 本征核（Dirichlet 壁；w[-mode] 取第 mode 个最弱本征模，最接近 0）
# ===========================================================================
def _fd1d_box_kc(a: float, n: int, mode: int = 1) -> float:
    """1D Dirichlet 盒第 mode 个最弱本征模空间波数（FD 本征值）。"""
    from scipy.linalg import eigh
    dx = a / (n + 1)
    L = (np.diag(np.full(n, -2.0))
         + np.diag(np.ones(n - 1), 1)
         + np.diag(np.ones(n - 1), -1))
    A = (1.0 / dx ** 2) * L
    w = eigh(A, eigvals_only=True)
    return math.sqrt(-float(w[-mode]))


def _fd2d_box_kc(a: float, b: float, nx: int, ny: int) -> float:
    """2D Dirichlet 盒最弱本征模空间波数（FD 本征值，w[-1]）。"""
    from scipy.linalg import eigh
    dx = a / (nx + 1)
    dy = b / (ny + 1)
    Lx = np.diag(np.full(nx, -2.0)) + np.diag(np.ones(nx - 1), 1) + np.diag(np.ones(nx - 1), -1)
    Ly = np.diag(np.full(ny, -2.0)) + np.diag(np.ones(ny - 1), 1) + np.diag(np.ones(ny - 1), -1)
    A = (1.0 / dx ** 2) * np.kron(np.eye(ny), Lx) + (1.0 / dy ** 2) * np.kron(Ly, np.eye(nx))
    A = (A + A.T) / 2.0
    w = eigh(A, eigvals_only=True)
    return math.sqrt(-float(w[-1]))


# ---- 候选求解器（签名 (spec, oracle_value) -> float，见 verification_adapters）----
def fd1d_rect_te10_fc(a: float, n: int = 400) -> float:
    """矩形波导 TE10 截止频率（Hz）。"""
    return C0 * _fd1d_box_kc(a, n) / (2.0 * math.pi)


def fd1d_rect_te20_fc(a: float, n: int = 400) -> float:
    """矩形波导 TE20 截止频率（Hz，第二模 k=2π/a）。"""
    return C0 * _fd1d_box_kc(a, n, mode=2) / (2.0 * math.pi)


def fd2d_rect_te11_fc(a: float, b: float, nx: int = 60, ny: int = 40) -> float:
    """矩形波导 TE11 截止频率（Hz）。"""
    return C0 * _fd2d_box_kc(a, b, nx, ny) / (2.0 * math.pi)


def fd1d_cavity_lambda(n: float, L: float, m: int = 1, ng: int = 400) -> float:
    """Fabry-Pérot 1D 腔谐振真空波长（m）：空间模 k=mπ/L ⇒ λ0=2π·n/k。"""
    k = _fd1d_box_kc(L, ng, mode=m)
    return 2.0 * math.pi * n / k


# ===========================================================================
# 黄金闭式（供 golden.py 调用；与候选方法学不同源）
# ===========================================================================
def golden_b34(n_f, n_c, t, wl):
    return marcatili_slab_neff(n_f, n_c, t, wl)


def golden_b36(a, b):
    return C0 / (2.0 * a)


def golden_b37(a, b):
    return C0 / a


def golden_b40(a, b):
    return C0 / (2.0 * math.pi) * math.sqrt((math.pi / a) ** 2 + (math.pi / b) ** 2)


def golden_b41(n, L, m=1):
    return 2.0 * n * L / m


if __name__ == "__main__":
    print("=== B34 slab TE0 n_eff (n_f=3.48,n_c=1.44,t=0.5,wl=1.55) ===")
    g34 = golden_b34(3.48, 1.44, 0.5, 1.55)
    c34 = exact_slab_neff(3.48, 1.44, 0.5, 1.55)
    print(f"  exact={c34:.6f} marcatili={g34:.6f} |d|={abs(c34-g34):.2e}")
    print(f"  perturb t×1.1 -> {exact_slab_neff(3.48,1.44,0.55,1.55):.6f}  t×0.9 -> {exact_slab_neff(3.48,1.44,0.45,1.55):.6f}")

    print("=== B36 rect WG TE10 (a=0.02286) ===")
    g36 = golden_b36(0.02286, 0.01016)
    for N in (200, 400, 800):
        c = fd1d_rect_te10_fc(0.02286, N)
        print(f"  N={N} cand={c/1e9:.6f}GHz gold={g36/1e9:.6f}GHz |d|={abs(c-g36)/1e9:.2e}GHz")
    print(f"  perturb a×1.1 -> {fd1d_rect_te10_fc(0.025146,400)/1e9:.6f}GHz")

    print("=== B37 rect WG TE20 (a=0.02286) ===")
    g37 = golden_b37(0.02286, 0.01016)
    for N in (200, 400, 800):
        c = fd1d_rect_te20_fc(0.02286, N)
        print(f"  N={N} cand={c/1e9:.6f}GHz gold={g37/1e9:.6f}GHz |d|={abs(c-g37)/1e9:.2e}GHz")
    print(f"  perturb a×1.1 -> {fd1d_rect_te20_fc(0.025146,400)/1e9:.6f}GHz")

    print("=== B40 rect WG TE11 (a=0.02286,b=0.01016) ===")
    g40 = golden_b40(0.02286, 0.01016)
    for Nx, Ny in ((40, 30), (60, 40), (100, 60)):
        c = fd2d_rect_te11_fc(0.02286, 0.01016, Nx, Ny)
        print(f"  Nx={Nx},Ny={Ny} cand={c/1e9:.6f}GHz gold={g40/1e9:.6f}GHz |d|={abs(c-g40)/1e9:.2e}GHz")
    print(f"  perturb a×1.1 -> {fd2d_rect_te11_fc(0.025146,0.01016,60,40)/1e9:.6f}GHz")

    print("=== B41 FP cavity (n=3.48,L=0.01,m=1) ===")
    g41 = golden_b41(3.48, 0.01, 1)
    for N in (200, 400, 800):
        c = fd1d_cavity_lambda(3.48, 0.01, 1, N)
        print(f"  N={N} cand={c*1e3:.6f}mm gold={g41*1e3:.6f}mm |d|={abs(c-g41)*1e3:.2e}mm")
    print(f"  perturb L×1.1 -> {fd1d_cavity_lambda(3.48,0.011,1,400)*1e3:.6f}mm")
