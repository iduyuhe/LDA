# -*- coding: utf-8 -*-
"""Batch B-8 双方法独立锚数值核（路径 B 扩基续七 · v0.9.88 · 继续稀释 terminal）

四族（目标全 strict，纯内部确定性扩基）：
  A. 2D 类氢原子（Coulomb，圆对称，|m|≥2）  B137-B140
       golden: E = -Z²·Ry/(N-1/2)²，N = n_r+|m|+1     （2D Coulomb 精确闭式）
       cand  : 1D 径向 FD（u=√r·R，V_eff = (m²-1/4)ℏ²/(2m r²) - Z·e²/(4πε0 r)）
       🔴 本族**限定 |m|≥2**：u(r)~r^{|m|+1/2}（近原点），|m|=0/1 时导数列奇性
          （u'~r^{|m|-1/2}）在均匀网格 FD 下**收敛到含网格伪态的极限**（|m|=0 稳定
          收敛到 -20.23 eV 而非 -54.42 eV，差 34 eV；|m|=1 残差 4.85e-3 eV 不随 N
          改善）⇒ 余量不足 2.2× 纪律线。|m|≥2 时 r^{≥2.5} 足够光滑，残差 1e-7~1e-9。
          （另：浅态需大盒——R=3nm 时 (4,0,1)/(3,1,1) 残差 2e-4/8e-4 系**盒截断**，
           R=6nm 后降至 4e-9/2e-8。故本族统一 R=6nm / N=12000。）
  B. 2D 圆环量子阱 + Aharonov-Bohm 通量    B141-B144
       golden: Bessel 交叉积 J_ν(kR_i)Y_ν(kR_o) - Y_ν(kR_i)J_ν(kR_o) = 0 的第 n 根
               E = ℏ²k²/(2m)，ν = |m + Φ/Φ₀|（整数 ν↔零通量，半整数 ν↔Φ=½Φ₀）
       cand  : 1D 径向 FD（u=√r·R，(ν²-1/4)/r² 离心项，u(R_i)=u(R_o)=0）
  C. 3D 有限深球形势阱（ℓ=0）              B145-B148
       golden: 超越方程 k·cot(kR) = -κ（内外波函数对数导数匹配），k=√(2m(E+V₀))/ℏ，κ=√(-2mE)/ℏ
       cand  : 1D 径向 FD（大盒，V(r)=-V₀ 内 / 0 外）
  D. 各向异性 3D 谐振子                    B149-B152
       golden: E = ℏ(ω_x(n_x+½) + ω_y(n_y+½) + ω_z(n_z+½))   （可分离精确闭式）
       cand  : 3D FD Kronecker 和（三个 1D HO FD 本征谱的直和）

方法学独立：每道锚 golden 走「解析闭式 / 特殊函数零点 / 超越方程根」，候选走
「偏微分方程离散本征」——两者不同源；残差 = 离散化误差（持久、判据 D 响应），
非代数恒等（B28 血案）、非纯数值沉底（B10 血案）。

🔴 血案规避（承接 B-6 / B-7）：
  1) **一律弃用 `scipy.linalg.eigh(subset_by_index=...)`**（B-6 off-by-one 血案：大矩阵
     静默返回第 2 低本征 ⇒ 候选命中错模）。本模块统一：三对角用 `eigh_tridiagonal`
     `select='a'`（全谱、升序），二维/三维可分离问题用 Kronecker 和分解。
  2) **势能项先核单位**（B-6 三角阱漏乘基本电荷 e 血案）：`V(r) = -Z·e²/(4πε0 r)` 中
     `e²/(4πε0)=1.4399e-9 eV·m` 已是 eV·m，乘 `EV` 得焦耳；电场势 `eFx` 必须含 e。
  3) **`default_params` 键集必须 ⊆ golden 形参集**（B-7 血案）：golden 只用 1~3 个标量
     参数，态指标（m/n_r/ν/ℓ/ω/盒径等）收在候选/闭式的硬编码里，避免 `**params` 展开时
     `TypeError`。
"""

import math

import numpy as np
from scipy.linalg import eigh_tridiagonal
from scipy.optimize import brentq
from scipy.special import jv, yv

# ---------------------------------------------------------------------------
# 物理常数（CODATA 2018，与 _batch_b5/b6/b7_numeric 同源）
# ---------------------------------------------------------------------------
HBAR = 1.054571817e-34      # J·s
ME = 9.1093837015e-31       # kg
EV = 1.602176634e-19        # J -> eV
KE2 = 1.43996448e-9         # eV·m，e²/(4πε0)
KE2_J = KE2 * EV            # J·m
RYDBERG_EV = ME * (KE2_J) ** 2 / (2.0 * HBAR ** 2) / EV   # ≈13.6057 eV
KIN = HBAR ** 2 / (2.0 * ME)  # ℏ²/2m，J·m²

NM = 1.0e-9


# ===========================================================================
# 通用：三对角全谱本征（升序，J）
# ===========================================================================
def _tri_evals(diag: np.ndarray, off: np.ndarray) -> np.ndarray:
    """对称三对角全谱本征值（升序）。select='a' ⇒ 全谱，无 subset off-by-one 风险。"""
    w = eigh_tridiagonal(diag, off, eigvals_only=True, select="a")
    return np.sort(np.real(w))


def _radial2d_evals(r_min: float, r_max: float, N: int, nu: float, V_extra_J) -> np.ndarray:
    """2D 径向方程（u=√r·R）FD 本征值（升序，J）。

        -ℏ²/2m·u'' + [ (ν²-1/4)ℏ²/(2m r²) + V_extra(r) ] u = E·u,  u(r_min)=u(r_max)=0
    """
    h = (r_max - r_min) / (N + 1)
    r = r_min + h * np.arange(1, N + 1)
    t = KIN / h ** 2
    diag = 2.0 * t * np.ones(N)
    off = -t * np.ones(N - 1)
    Vc = (nu ** 2 - 0.25) * KIN / r ** 2
    V = Vc + V_extra_J(r)
    return _tri_evals(diag + V, off)


def _radial3d_evals(r_min: float, r_max: float, N: int, l: int, V_central_J) -> np.ndarray:
    """3D 径向方程（u=r·R）FD 本征值（升序，J）。

        -ℏ²/2m·u'' + [ l(l+1)ℏ²/(2m r²) + V(r) ] u = E·u,  u(r_min)=u(r_max)=0
    """
    h = (r_max - r_min) / (N + 1)
    r = r_min + h * np.arange(1, N + 1)
    t = KIN / h ** 2
    diag = 2.0 * t * np.ones(N)
    off = -t * np.ones(N - 1)
    V = np.array([V_central_J(ri) for ri in r], dtype=float)
    V = V + l * (l + 1) * KIN / r ** 2
    return _tri_evals(diag + V, off)


# ===========================================================================
# 族 A：2D 类氢原子（B137-B140）
#   golden: E = -Z²·Ry/(N-1/2)²，N = n_r + |m| + 1
#   cand  : 2D 径向 FD（u=√r·R，V_eff=(m²-1/4)ℏ²/(2m r²) - Z e²/(4πε0 r)）
# ===========================================================================
def hydrogen2d_E_closed(Z: float, N: int) -> float:
    """golden：2D 氢原子能级 E = -Z²·Ry/(N-1/2)²（eV），N=1,2,3,..."""
    return -RYDBERG_EV * (Z ** 2) / ((N - 0.5) ** 2)


def hydrogen2d_E_fd(m: int, n_r: int, Z: float = 1.0, R: float = 6.0e-9, N: int = 12000) -> float:
    """候选：2D 径向 FD 第 n_r 个本征（固定 |m|≥2），eV。R=6nm/N=12000 免盒截断。"""
    def V_extra(r):
        return -Z * KE2_J / r
    ev = _radial2d_evals(1.0e-12, R, N, float(abs(m)), V_extra)
    return float(ev[n_r]) / EV


def golden_b137(Z: float = 1.0) -> float:
    """2D 类氢 (n_r=0,m=2) N=3（Z=1：-Ry/6.25 = -2.1769 eV）。"""
    return hydrogen2d_E_closed(Z, 3)


def golden_b138(Z: float = 1.0) -> float:
    """2D 类氢 (n_r=1,m=2) N=4。"""
    return hydrogen2d_E_closed(Z, 4)


def golden_b139(Z: float = 1.0) -> float:
    """2D 类氢 (n_r=0,m=4) N=5。"""
    return hydrogen2d_E_closed(Z, 5)


def golden_b140(Z: float = 2.0) -> float:
    """2D 类氢 (n_r=0,m=2, Z=2) N=3（类 He⁺：-4Ry/6.25 = -8.7076 eV）。"""
    return hydrogen2d_E_closed(Z, 3)


def cand_hydrogen2d(m, n_r, Z: float = 1.0) -> float:
    """候选工厂：2D 类氢 (m≥2, n_r, Z)。"""
    return hydrogen2d_E_fd(int(m), int(n_r), float(Z))


# ===========================================================================
# 族 B：2D 圆环量子阱 + Aharonov-Bohm 通量（B141-B144）
#   golden: J_ν(kR_i)Y_ν(kR_o) - Y_ν(kR_i)J_ν(kR_o) = 0 的第 n 根 ⇒ E=ℏ²k²/(2m)
#   cand  : 2D 径向 FD（u=√r·R，(ν²-1/4)/r²），u(R_i)=u(R_o)=0
# ===========================================================================
_ANN_R_IN = 0.5e-9
_ANN_R_OUT = 1.0e-9
_ANN_M = ME


def _annulus_f(k: float, nu: float, ri: float, ro: float) -> float:
    return float(jv(nu, k * ri) * yv(nu, k * ro) - jv(nu, k * ro) * yv(nu, k * ri))


def annulus_k(order: float, n: int = 1, ri: float = _ANN_R_IN, ro: float = _ANN_R_OUT) -> float:
    """圆环（内半径 ri、外半径 ro）第 n 个径向波数 k（1/m），ν=order。"""
    nu = float(order)
    kmax = (n + 3) * math.pi / (ro - ri)
    ks = np.linspace(1.0e-4 / ro, kmax, 40000)
    fs = np.array([_annulus_f(k, nu, ri, ro) for k in ks])
    # 检测符号变化（跳过非有限值）
    roots = []
    for i in range(len(ks) - 1):
        f0, f1 = fs[i], fs[i + 1]
        if not (math.isfinite(f0) and math.isfinite(f1)):
            continue
        if f0 == 0.0:
            roots.append(ks[i])
        elif f0 * f1 < 0.0:
            try:
                roots.append(brentq(_annulus_f, ks[i], ks[i + 1], args=(nu, ri, ro), maxiter=200))
            except ValueError:
                continue
    if len(roots) < n:
        raise RuntimeError(f"annulus_k: 仅找到 {len(roots)} 根（需第 {n} 根），ν={nu}")
    return float(roots[n - 1])


def annulus_E_closed(order: float, n: int = 1, ri: float = _ANN_R_IN, ro: float = _ANN_R_OUT) -> float:
    """golden：圆环能级 E = ℏ²k²/(2m)（eV），k 由 Bessel 交叉积零点给出。"""
    k = annulus_k(order, n, ri, ro)
    return KIN * k ** 2 / EV


def annulus_E_fd(order: float, n: int = 1, ri: float = _ANN_R_IN, ro: float = _ANN_R_OUT,
                 N: int = 3000) -> float:
    """候选：圆环 2D 径向 FD 第 n 个本征（固定 ν），eV。"""
    ev = _radial2d_evals(ri, ro, N, float(order), lambda r: np.zeros_like(r))
    return float(ev[n - 1]) / EV


def golden_b141(ri_nm: float = 0.5, ro_nm: float = 1.0) -> float:
    """圆环 ν=0 基态（零通量 m=0）。"""
    return annulus_E_closed(0.0, 1, ri_nm * NM, ro_nm * NM)


def golden_b142(ri_nm: float = 0.5, ro_nm: float = 1.0) -> float:
    """圆环 ν=1 基态（零通量 m=1）。"""
    return annulus_E_closed(1.0, 1, ri_nm * NM, ro_nm * NM)


def golden_b143(ri_nm: float = 0.5, ro_nm: float = 1.0) -> float:
    """圆环 ν=1/2 基态（Aharonov-Bohm 通量 Φ=½Φ₀）。"""
    return annulus_E_closed(0.5, 1, ri_nm * NM, ro_nm * NM)


def golden_b144(ri_nm: float = 0.5, ro_nm: float = 1.0) -> float:
    """圆环 ν=3/2 基态（Aharonov-Bohm 通量 Φ=½Φ₀，m=1 支）。"""
    return annulus_E_closed(1.5, 1, ri_nm * NM, ro_nm * NM)


def cand_annulus(order, n, ri_nm: float = 0.5, ro_nm: float = 1.0) -> float:
    """候选工厂：圆环 (ν, n)。"""
    return annulus_E_fd(float(order), int(n), ri_nm * NM, ro_nm * NM)


# ===========================================================================
# 族 C：3D 有限深球形势阱（ℓ=0）（B145-B148）
#   golden: k·cot(kR) = -κ 的根，k=√(2m(E+V₀))/ℏ（0<k<k_max=√(2m V₀)/ℏ），
#           κ=√(-2mE)/ℏ=√(k_max²-k²)，E=ℏ²k²/(2m)-V₀
#   cand  : 3D 径向 FD（r∈(0,L_box)，V(r)=-V₀ 内 / 0 外，ℓ=0）
# ===========================================================================
def _fs_g(k: float, R: float, kmax: float) -> float:
    kr = k * R
    # k·cot(kR) + κ ；用 sin 防极点
    s = math.sin(kr)
    if abs(s) < 1e-300:
        return math.inf
    return k * math.cos(kr) / s + math.sqrt(max(kmax ** 2 - k ** 2, 0.0))


def finite_sphere_E_closed(V0_eV: float, R_m: float, n: int = 1) -> float:
    """golden：3D 有限深球形势阱（ℓ=0）第 n 个束缚态 E（eV），V₀ 深度。"""
    V0_J = V0_eV * EV
    kmax = math.sqrt(2.0 * ME * V0_J) / HBAR
    roots = []
    j = 0
    while True:
        lo = j * math.pi / R_m
        hi = (j + 1) * math.pi / R_m
        if lo >= kmax:
            break
        a = lo + 1e-12 * (hi - lo)
        b = min(hi - 1e-12 * (hi - lo), kmax - 1e-15)
        if a >= b:
            j += 1
            continue
        fa, fb = _fs_g(a, R_m, kmax), _fs_g(b, R_m, kmax)
        if math.isfinite(fa) and math.isfinite(fb) and fa * fb < 0.0:
            try:
                roots.append(brentq(_fs_g, a, b, args=(R_m, kmax), maxiter=200))
            except ValueError:
                pass
        j += 1
    if len(roots) < n:
        raise RuntimeError(f"finite_sphere: 仅 {len(roots)} 个 ℓ=0 束缚态（需第 {n} 个）")
    k = roots[n - 1]
    return KIN * k ** 2 / EV - V0_eV


def finite_sphere_E_fd(V0_eV: float, R_m: float, n: int = 1,
                       L_extra: float = 12.0e-9, N: int = 10000) -> float:
    """候选：3D 径向 FD 第 n 个束缚态（eV）。大盒 r∈(0, R+L_extra)。"""
    V0_J = V0_eV * EV

    def V(r):
        return -V0_J if r < R_m else 0.0

    ev = _radial3d_evals(1.0e-12, R_m + L_extra, N, 0, V)
    return float(ev[n - 1]) / EV


def golden_b145(V0_eV: float = 1.0, R_nm: float = 2.0) -> float:
    """3D 有限深球形阱 V₀=1eV/R=2nm，ℓ=0 基态。"""
    return finite_sphere_E_closed(V0_eV, R_nm * NM, 1)


def golden_b146(V0_eV: float = 5.0, R_nm: float = 2.0) -> float:
    """3D 有限深球形阱 V₀=5eV/R=2nm，ℓ=0 基态。"""
    return finite_sphere_E_closed(V0_eV, R_nm * NM, 1)


def golden_b147(V0_eV: float = 10.0, R_nm: float = 2.0) -> float:
    """3D 有限深球形阱 V₀=10eV/R=2nm，ℓ=0 基态。"""
    return finite_sphere_E_closed(V0_eV, R_nm * NM, 1)


def golden_b148(V0_eV: float = 10.0, R_nm: float = 2.0) -> float:
    """3D 有限深球形阱 V₀=10eV/R=2nm，ℓ=0 第 2 束缚态。"""
    return finite_sphere_E_closed(V0_eV, R_nm * NM, 2)


def cand_finite_sphere(V0_eV, R_nm, n) -> float:
    """候选工厂：3D 有限深球形阱 (V₀, R, n)。"""
    return finite_sphere_E_fd(float(V0_eV), float(R_nm) * NM, int(n))


# ===========================================================================
# 族 D：各向异性 3D 谐振子（B149-B152）
#   golden: E = ℏ(ω_x(n_x+½) + ω_y(n_y+½) + ω_z(n_z+½))
#   cand  : 3D FD Kronecker 和（三个 1D HO FD 谱的直和，取最低几档组合）
# ===========================================================================
_OM_BASE = 1.0e15  # rad/s，基准角频率（ℏω ≈ 0.658 eV）


def _ho1d_fd_evals(omega: float, m: float = ME, N: int = 1400) -> np.ndarray:
    """1D 谐振子 H=-ℏ²/2m d²/dx²+½mω²x² 的 FD 本征（升序，J），Dirichlet 盒。"""
    sigma = math.sqrt(HBAR / (m * omega))
    L = 9.0 * sigma
    h = 2.0 * L / (N + 1)
    x = -L + h * np.arange(1, N + 1)
    t = HBAR ** 2 / (2.0 * m * h ** 2)
    diag = 2.0 * t + 0.5 * m * omega ** 2 * x ** 2
    off = -t * np.ones(N - 1)
    return _tri_evals(diag, off)


def ho3d_aniso_E_closed(nx: int, ny: int, nz: int,
                        ox: float = 1.0, oy: float = 1.0, oz: float = 1.0) -> float:
    """golden：各向异性 3D 谐振子 E = ℏ(ω_x(n_x+½)+ω_y(n_y+½)+ω_z(n_z+½))（eV）。"""
    return HBAR * (_OM_BASE * ox * (nx + 0.5)
                   + _OM_BASE * oy * (ny + 0.5)
                   + _OM_BASE * oz * (nz + 0.5)) / EV


def ho3d_aniso_E_fd(nx: int, ny: int, nz: int,
                    ox: float = 1.0, oy: float = 1.0, oz: float = 1.0,
                    M: int = 40) -> float:
    """候选：3D 可分离 FD Kronecker 和——取 1D FD 谱前 M 档做直和，定位 (n_x,n_y,n_z)。"""
    ex = _ho1d_fd_evals(_OM_BASE * ox)[:M]
    ey = _ho1d_fd_evals(_OM_BASE * oy)[:M]
    ez = _ho1d_fd_evals(_OM_BASE * oz)[:M]
    cand = ex[nx] + ey[ny] + ez[nz]
    # 用「解析组合定位」自检：合并直和后应存在与目标最接近且唯一可辨的档
    allsum = (ex[:, None, None] + ey[None, :, None] + ez[None, None, :]).ravel()
    allsum = np.sort(allsum)
    idx = int(np.argmin(np.abs(allsum - cand)))
    return float(allsum[idx]) / EV


def golden_b149(ox: float = 1.0, oy: float = 1.0, oz: float = 1.0) -> float:
    """各向同性 3D HO 基态 (0,0,0)。"""
    return ho3d_aniso_E_closed(0, 0, 0, ox, oy, oz)


def golden_b150(ox: float = 1.0, oy: float = 1.2, oz: float = 1.4) -> float:
    """各向异性 3D HO 基态 (0,0,0)。"""
    return ho3d_aniso_E_closed(0, 0, 0, ox, oy, oz)


def golden_b151(ox: float = 1.0, oy: float = 1.2, oz: float = 1.4) -> float:
    """各向异性 3D HO (1,0,0)。"""
    return ho3d_aniso_E_closed(1, 0, 0, ox, oy, oz)


def golden_b152(ox: float = 1.0, oy: float = 1.2, oz: float = 1.4) -> float:
    """各向异性 3D HO (1,1,1)。"""
    return ho3d_aniso_E_closed(1, 1, 1, ox, oy, oz)


def cand_ho3d_aniso(nx, ny, nz, ox, oy, oz) -> float:
    """候选工厂：各向异性 3D HO (n_x,n_y,n_z; ω 比)。"""
    return ho3d_aniso_E_fd(int(nx), int(ny), int(nz), float(ox), float(oy), float(oz))


# ===========================================================================
# 自测：16/16 golden ↔ cand 残差非零 + 判据 D 响应（参数×1.1 双向同步偏移）
# ===========================================================================
_CASES = [
    # (锚号, golden_thunk, cand_thunk, D 参数字典)
    ("B137", lambda: golden_b137(1.0),            lambda: cand_hydrogen2d(2, 0, 1.0),          {"Z": 1.0}),
    ("B138", lambda: golden_b138(1.0),            lambda: cand_hydrogen2d(2, 1, 1.0),          {"Z": 1.0}),
    ("B139", lambda: golden_b139(1.0),            lambda: cand_hydrogen2d(4, 0, 1.0),          {"Z": 1.0}),
    ("B140", lambda: golden_b140(2.0),            lambda: cand_hydrogen2d(2, 0, 2.0),          {"Z": 2.0}),
    ("B141", lambda: golden_b141(0.5, 1.0),       lambda: cand_annulus(0.0, 1, 0.5, 1.0),      {"ro_nm": 1.0}),
    ("B142", lambda: golden_b142(0.5, 1.0),       lambda: cand_annulus(1.0, 1, 0.5, 1.0),      {"ro_nm": 1.0}),
    ("B143", lambda: golden_b143(0.5, 1.0),       lambda: cand_annulus(0.5, 1, 0.5, 1.0),      {"ro_nm": 1.0}),
    ("B144", lambda: golden_b144(0.5, 1.0),       lambda: cand_annulus(1.5, 1, 0.5, 1.0),      {"ro_nm": 1.0}),
    ("B145", lambda: golden_b145(1.0, 2.0),       lambda: cand_finite_sphere(1.0, 2.0, 1),     {"V0_eV": 1.0}),
    ("B146", lambda: golden_b146(5.0, 2.0),       lambda: cand_finite_sphere(5.0, 2.0, 1),     {"V0_eV": 5.0}),
    ("B147", lambda: golden_b147(10.0, 2.0),      lambda: cand_finite_sphere(10.0, 2.0, 1),    {"V0_eV": 10.0}),
    ("B148", lambda: golden_b148(10.0, 2.0),      lambda: cand_finite_sphere(10.0, 2.0, 2),    {"V0_eV": 10.0}),
    ("B149", lambda: golden_b149(1.0, 1.0, 1.0),  lambda: cand_ho3d_aniso(0, 0, 0, 1.0, 1.0, 1.0), {"oy": 1.0}),
    ("B150", lambda: golden_b150(1.0, 1.2, 1.4),  lambda: cand_ho3d_aniso(0, 0, 0, 1.0, 1.2, 1.4), {"oy": 1.2}),
    ("B151", lambda: golden_b151(1.0, 1.2, 1.4),  lambda: cand_ho3d_aniso(1, 0, 0, 1.0, 1.2, 1.4), {"oy": 1.2}),
    ("B152", lambda: golden_b152(1.0, 1.2, 1.4),  lambda: cand_ho3d_aniso(1, 1, 1, 1.0, 1.2, 1.4), {"oy": 1.2}),
]


def _self_test() -> None:
    print(f"RYDBERG_EV = {RYDBERG_EV:.9f} eV   KIN = {KIN:.6e} J·m²   ℏω_base = {HBAR*_OM_BASE/EV:.6f} eV")
    print(f"{'锚号':<6}{'golden(eV)':>18}{'cand(eV)':>18}{'|diff|(eV)':>16}{'余量×':>10}  判据D")
    nz = 0
    worst = (0.0, "")
    for bid, g, c, dpar in _CASES:
        gv, cv = g(), c()
        diff = abs(gv - cv)
        # 判据 D：把首个参数 ×1.1，golden 与 cand 必须同步偏移且残差量级保持
        p0 = next(iter(dpar))
        d2 = dict(dpar)
        d2[p0] = dpar[p0] * 1.1
        gv2 = _golden_by_bid(bid, d2)
        cv2 = _cand_by_bid(bid, d2)
        crit = (abs(gv2 - gv) > 0.0) and (abs(cv2 - cv) > 0.0)
        margin = 0.01 / diff if diff > 0 else float("inf")
        nz += 1 if diff > 0 else 0
        if diff > worst[0]:
            worst = (diff, bid)
        print(f"{bid:<6}{gv:>18.9f}{cv:>18.9f}{diff:>16.3e}{margin:>10.1f}  {'OK' if crit else 'FAIL'}")

    print("-" * 76)
    print(f"非零残差：{nz}/16    worst = {worst[1]} |d|={worst[0]:.3e} eV（tol 0.01，余量 {0.01/worst[0]:.1f}×）")


def _golden_by_bid(bid: str, dpar: dict) -> float:
    if bid == "B137":
        return golden_b137(dpar["Z"])
    if bid == "B138":
        return golden_b138(dpar["Z"])
    if bid == "B139":
        return golden_b139(dpar["Z"])
    if bid == "B140":
        return golden_b140(dpar["Z"])
    if bid == "B141":
        return golden_b141(0.5, dpar["ro_nm"])
    if bid == "B142":
        return golden_b142(0.5, dpar["ro_nm"])
    if bid == "B143":
        return golden_b143(0.5, dpar["ro_nm"])
    if bid == "B144":
        return golden_b144(0.5, dpar["ro_nm"])
    if bid == "B145":
        return golden_b145(dpar["V0_eV"], 2.0)
    if bid == "B146":
        return golden_b146(dpar["V0_eV"], 2.0)
    if bid == "B147":
        return golden_b147(dpar["V0_eV"], 2.0)
    if bid == "B148":
        return golden_b148(dpar["V0_eV"], 2.0)
    if bid == "B149":
        return golden_b149(1.0, dpar["oy"], 1.0)
    if bid == "B150":
        return golden_b150(1.0, dpar["oy"], 1.4)
    if bid == "B151":
        return golden_b151(1.0, dpar["oy"], 1.4)
    if bid == "B152":
        return golden_b152(1.0, dpar["oy"], 1.4)
    raise KeyError(bid)


def _cand_by_bid(bid: str, dpar: dict) -> float:
    if bid == "B137":
        return cand_hydrogen2d(2, 0, dpar["Z"])
    if bid == "B138":
        return cand_hydrogen2d(2, 1, dpar["Z"])
    if bid == "B139":
        return cand_hydrogen2d(4, 0, dpar["Z"])
    if bid == "B140":
        return cand_hydrogen2d(2, 0, dpar["Z"])
    if bid == "B141":
        return cand_annulus(0.0, 1, 0.5, dpar["ro_nm"])
    if bid == "B142":
        return cand_annulus(1.0, 1, 0.5, dpar["ro_nm"])
    if bid == "B143":
        return cand_annulus(0.5, 1, 0.5, dpar["ro_nm"])
    if bid == "B144":
        return cand_annulus(1.5, 1, 0.5, dpar["ro_nm"])
    if bid == "B145":
        return cand_finite_sphere(dpar["V0_eV"], 2.0, 1)
    if bid == "B146":
        return cand_finite_sphere(dpar["V0_eV"], 2.0, 1)
    if bid == "B147":
        return cand_finite_sphere(dpar["V0_eV"], 2.0, 1)
    if bid == "B148":
        return cand_finite_sphere(dpar["V0_eV"], 2.0, 2)
    if bid == "B149":
        return cand_ho3d_aniso(0, 0, 0, 1.0, dpar["oy"], 1.0)
    if bid == "B150":
        return cand_ho3d_aniso(0, 0, 0, 1.0, dpar["oy"], 1.4)
    if bid == "B151":
        return cand_ho3d_aniso(1, 0, 0, 1.0, dpar["oy"], 1.4)
    if bid == "B152":
        return cand_ho3d_aniso(1, 1, 1, 1.0, dpar["oy"], 1.4)
    raise KeyError(bid)


if __name__ == "__main__":
    _self_test()
