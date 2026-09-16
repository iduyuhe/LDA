# -*- coding: utf-8 -*-
"""Batch B-9 双方法独立锚数值核（路径 B 扩基续八 · v0.9.89 · 继续稀释 terminal）

四族（目标全 strict，纯内部确定性扩基）：
  A. Euler-Bernoulli 等截面梁横向振动（4 阶 ODE，结构动力学）   B153-B156
       golden: cos(βL)·cosh(βL) = 1 的第 n 根（固支-固支）⇒
               f_n = (β_nL)²/(2π L²)·√(E·I/(ρ·A))，I=bh³/12、A=bh
       cand  : Hermite 梁单元 FEM（固支-固支，Ne=200 单元）＋一致质量矩阵
               ⇒ 广义本征 w''''=μw，f_n = (1/2π)·√(μ_n·E·I/(ρ·A·L⁴))
       🔴 本族是**新算子阶数**：既有无任何四阶 ODE 锚（全是一/二阶）。
  B. Hulthen 势 3D s-wave 束缚态（指数屏蔽 Coulomb）          B157-B160
       golden: E_n = -V₀[ (β²-n²)/(2nβ) ]²，β² = 2mV₀a²/ℏ²，n=1,2,…
               （s-wave 精确闭式；超几何/Jacobi 解）
       cand  : 3D 径向 FD（u=r·R，ℓ=0，V(r) = -V₀ e^{-r/a}/(1-e^{-r/a})）
       🔴 自检：a→∞ 极限应还原氢原子 E_n = -m·KE2²/(2ℏ²n²)（本模块 _self_test 已验）
  C. Fock-Darwin 2D 量子点（抛物约束 + 垂直磁场）              B161-B164
       golden: ε = ℏΩ(2n_r+|m|+1) - (ℏω_c/2)·m，Ω = √(ω₀²+ω_c²/4)，ω_c = eB/m*
       cand  : 2D 径向 FD（u=√r·R，ν=|m|≥2，V_extra = ½m*Ω²r²）＋ L_z 项解析本征
               （L_z=ℏm 在 m 表象严格对角 ⇒ 加 (ℏω_c/2)m 是精确项，非近似）
  D. Rosen-Morse II 势束缚态（sech² + tanh 双曲势）            B165-B168
       golden: b_n = √(γ+1/4)-n-1/2，a_n = -β/(2b_n)，E_n = -(ℏ²α²/2μ)(a_n²+b_n²)
               其中 β = 2μB/(ℏ²α²)、γ = 2μC/(ℏ²α²)，V = B·tanh(αx) - C·sech²(αx)
       cand  : 1D FD（大盒 Dirichlet，V 双曲）
       🔴 与 B59-B60 Pöschl-Teller 的区别：本势含**奇宇称 tanh 项**（B→0 才退化为 PT），
          本模块 B=0.4 eV ≠ 0，golden 多出 -B²/(A-n)² 项 ⇒ 非同一本征值问题。

同源体检（本批第一道闸，v0.9.89 立）：四族均与既有 152 道锚**方程/算子不同**——
  A：四阶 ODE（新阶数）；B：指数屏蔽势（非 1/r、非 sech²）；C：磁场哈密顿量（新算子项）；
  D：tanh+sech²（非纯 sech²）。
  被否候选：① 2D 量子圆盘（Bessel J 零点 ≡ B-5 圆波导 B98/B99 同源）
            ② Landau 能级（≡ 1D HO FD 结构同源）③ 非谐振子 x⁴ 微扰（golden 是截断近似）。

方法学独立：每道锚 golden 走「解析闭式 / 特殊函数零点 / 超越方程根」，候选走
「偏微分方程离散本征」——两者不同源；残差 = 离散化误差（持久、判据 D 响应），
非代数恒等（B28 血案）、非纯数值沉底（B10 血案）。

🔴 血案规避（承接 B-5 / B-6 / B-7 / B-8）：
  1) **一律弃用 `scipy.linalg.eigh(subset_by_index=...)`**（B-6 off-by-one 血案）。
     本模块：三对角用 `eigh_tridiagonal(select='a')` 全谱升序；族 A 用稠密广义本征
     `scipy.linalg.eigvalsh(Kf, Mf)`（Hermite 梁单元，402×402 规模）。
     🔴 **不用 ARPACK `eigsh`**：梁本征量级 ~1e24（h⁻⁴ 放大），`which='SA'` 实测
     30001 次迭代 0/8 不收敛（v0.9.89 血案）。
     🔴 **不用 4 阶中心差分**：4 阶算子 λ∝n⁴、cond~N⁴ ⇒ 加密网格残差反升
     （N=4000 时 0.092 MHz、N=12000 时 5.17 MHz）。Hermite 梁单元离散化 ∈ O(h⁴)
     且条件数良好 ⇒ 残差单调收敛（Ne=200 时 worst 2.8e-5 MHz）。
  2) **原点采样陷阱（B-9 新增体检）**：径向 FD 首节点 r₁=h 处 |V(r₁)| 可能 ≫ 动能
     t=ℏ²/(2m h²) ⇒ 出现「格点伪态」抢走最低本征。**判据 t ≫ |V(r₁)|**：
     t/|V(r₁)| = ℏ²/(2m h V₀ a)。本模块族 B 取 h=5e-13 m ⇒ t/|V(r₁)| ≈ 8.7（氢 B89-94
     实测 t/|V| = 3.8e4/1.4e3 ≈ 26，两者均安全）。
  3) **`default_params` 键集必须 ⊆ golden 形参集**（B-7 血案）：态指标（n/n_r/m/ℓ）
     收在 golden/cand 的硬编码或默认形参里，避免 `**params` 展开时 `TypeError`。
  4) **势能项先核单位**（B-6 三角阱漏乘 e 血案）：B/eV 一律先 `*EV` 转焦耳。
"""

import math

import numpy as np
from scipy.linalg import eigh_tridiagonal, eigvalsh
from scipy.optimize import brentq

# ---------------------------------------------------------------------------
# 物理常数（CODATA 2018，与 _batch_b5/b6/b7/b8_numeric 同源）
# ---------------------------------------------------------------------------
HBAR = 1.054571817e-34      # J·s
ME = 9.1093837015e-31       # kg
EV = 1.602176634e-19        # J -> eV
KE2 = 1.43996448e-9         # eV·m，e²/(4πε0)
KE2_J = KE2 * EV            # J·m
RYDBERG_EV = ME * (KE2_J) ** 2 / (2.0 * HBAR ** 2) / EV   # ≈13.6057 eV
KIN = HBAR ** 2 / (2.0 * ME)  # ℏ²/2m，J·m²
ECHARGE = 1.602176634e-19   # C，基本电荷

NM = 1.0e-9


# ===========================================================================
# 通用：三对角全谱本征（升序，J）
# ===========================================================================
def _tri_evals(diag: np.ndarray, off: np.ndarray) -> np.ndarray:
    """对称三对角全谱本征值（升序）。select='a' ⇒ 全谱，无 subset off-by-one 风险。"""
    w = eigh_tridiagonal(diag, off, eigvals_only=True, select="a")
    return np.sort(np.real(w))


def _radial2d_evals(r_min: float, r_max: float, N: int, nu: float, V_extra_J,
                    mass: float = ME) -> np.ndarray:
    """2D 径向方程（u=√r·R）FD 本征值（升序，J）。

        -ℏ²/2m·u'' + [ (ν²-1/4)ℏ²/(2m r²) + V_extra(r) ] u = E·u,  u(r_min)=u(r_max)=0

    🔴 `mass` 必须与所解问题一致（B-9 血案：Fock-Darwin 用 m*=0.067m₀，
    初版漏传 ⇒ 用电子质量 ⇒ 本征偏低 ~4×）。
    """
    h = (r_max - r_min) / (N + 1)
    r = r_min + h * np.arange(1, N + 1)
    kin = HBAR ** 2 / (2.0 * mass)
    t = kin / h ** 2
    diag = 2.0 * t * np.ones(N)
    off = -t * np.ones(N - 1)
    Vc = (nu ** 2 - 0.25) * kin / r ** 2
    V = Vc + V_extra_J(r)
    return _tri_evals(diag + V, off)


def _radial3d_evals(r_min: float, r_max: float, N: int, l: int, V_central_J,
                    mass: float = ME) -> np.ndarray:
    """3D 径向方程（u=r·R）FD 本征值（升序，J）。

        -ℏ²/2m·u'' + [ l(l+1)ℏ²/(2m r²) + V(r) ] u = E·u,  u(r_min)=u(r_max)=0
    """
    h = (r_max - r_min) / (N + 1)
    r = r_min + h * np.arange(1, N + 1)
    kin = HBAR ** 2 / (2.0 * mass)
    t = kin / h ** 2
    diag = 2.0 * t * np.ones(N)
    off = -t * np.ones(N - 1)
    V = np.array([V_central_J(ri) for ri in r], dtype=float)
    V = V + l * (l + 1) * kin / r ** 2
    return _tri_evals(diag + V, off)


# ===========================================================================
# 族 A：Euler-Bernoulli 等截面梁横向振动（4 阶 ODE）（B153-B156）
#   golden: cos(βL)cosh(βL)=1 根 ⇒ f_n = (β_nL)²/(2π L²)√(EI/ρA)
#   cand  : Hermite 梁单元 FEM（固支-固支，Ne=200）⇒ ω_n=√(μ_n EI/(ρA L⁴))
#   材料/截面固定（Si 微梁）：E=169 GPa、ρ=2330 kg/m³、b=1 µm、h=0.5 µm
# ===========================================================================
_BEAM_E = 169.0e9       # Pa
_BEAM_RHO = 2330.0      # kg/m³
_BEAM_B = 1.0e-6        # m
_BEAM_H = 0.5e-6        # m


def _beam_cc_root(k: int) -> float:
    """cos(x)cosh(x)=1 的第 k 个根（k=1,2,3,…）。括号取 ((k±0.1)π) 内。"""
    a = (k + 0.4) * math.pi
    b = (k + 0.6) * math.pi
    fa = math.cos(a) * math.cosh(a) - 1.0
    fb = math.cos(b) * math.cosh(b) - 1.0
    if fa * fb >= 0.0:  # 兜底：扩大括号
        a, b = (k - 0.1) * math.pi, (k + 0.9) * math.pi
    return float(brentq(lambda x: math.cos(x) * math.cosh(x) - 1.0, a, b, maxiter=200))


def beam_freq_closed(n: int, L_m: float) -> float:
    """golden：固支-固支梁第 n 阶横向振动频率 f_n（**MHz**）。"""
    x = _beam_cc_root(n)
    I = _BEAM_B * _BEAM_H ** 3 / 12.0
    A = _BEAM_B * _BEAM_H
    return (x / L_m) ** 2 * math.sqrt(_BEAM_E * I / (_BEAM_RHO * A)) / (2.0 * math.pi) / 1.0e6


def _beam_ke_me(le: float):
    """Hermite 梁单元刚度/一致质量矩阵（单元长 le，无量纲坐标）。"""
    ke = np.array([
        [12.0, 6.0 * le, -12.0, 6.0 * le],
        [6.0 * le, 4.0 * le ** 2, -6.0 * le, 2.0 * le ** 2],
        [-12.0, -6.0 * le, 12.0, -6.0 * le],
        [6.0 * le, 2.0 * le ** 2, -6.0 * le, 4.0 * le ** 2],
    ]) / le ** 3
    me = np.array([
        [156.0, 22.0 * le, 54.0, -13.0 * le],
        [22.0 * le, 4.0 * le ** 2, 13.0 * le, -3.0 * le ** 2],
        [54.0, 13.0 * le, 156.0, -22.0 * le],
        [-13.0 * le, -3.0 * le ** 2, -22.0 * le, 4.0 * le ** 2],
    ]) * le / 420.0
    return ke, me


def beam_freq_fem(n: int, L_m: float, Ne: int = 200) -> float:
    """候选：Hermite 梁单元 FEM（固支-固支），第 n 阶频率（MHz）。

    4 阶 ODE ``E·I·w\'\'\'\' = ρ·A·ω²·w`` 弱形式离散：单元刚度 ke、一致质量 me；
    固支 BC 令两端 (w, θ) 自由度固定；解广义本征 K v = μ M v ⇒
        f_n = (1/2π)·√(μ_n·E·I/(ρ·A·L⁴))（μ_n = (β_nL)⁴）
    🔴 弃用 4 阶中心差分（条件数病态，加密反恶化）；Hermite 单元离散化 ∈ O(h⁴)。
    """
    EI = _BEAM_E * _BEAM_B * _BEAM_H ** 3 / 12.0
    rhoA = _BEAM_RHO * _BEAM_B * _BEAM_H
    le = 1.0 / Ne
    ke, me = _beam_ke_me(le)
    ndof = 2 * (Ne + 1)
    K = np.zeros((ndof, ndof))
    M = np.zeros((ndof, ndof))
    for e in range(Ne):
        d = np.arange(2 * e, 2 * e + 4)
        K[np.ix_(d, d)] += ke
        M[np.ix_(d, d)] += me
    free = np.arange(2, ndof - 2)
    mu = np.sort(np.real(eigvalsh(K[np.ix_(free, free)], M[np.ix_(free, free)])))
    omega = math.sqrt(float(mu[n - 1]) * EI / (rhoA * L_m ** 4))
    return omega / (2.0 * math.pi) / 1.0e6


def golden_b153(L_um: float = 5.0) -> float:
    """固支梁第 1 阶频率 f₁（MHz）。"""
    return beam_freq_closed(1, L_um * 1.0e-6)


def golden_b154(L_um: float = 5.0) -> float:
    """固支梁第 2 阶频率 f₂（MHz）。"""
    return beam_freq_closed(2, L_um * 1.0e-6)


def golden_b155(L_um: float = 5.0) -> float:
    """固支梁第 3 阶频率 f₃（MHz）。"""
    return beam_freq_closed(3, L_um * 1.0e-6)


def golden_b156(L_um: float = 5.0) -> float:
    """固支梁第 4 阶频率 f₄（MHz）。"""
    return beam_freq_closed(4, L_um * 1.0e-6)


def cand_beam(n, L_um) -> float:
    """候选工厂：固支梁第 n 阶频率（MHz）。"""
    return beam_freq_fem(int(n), float(L_um) * 1.0e-6)


# ===========================================================================
# 族 B：Hulthen 势 3D s-wave 束缚态（B157-B160）
#   golden: E_n = -V₀[ (β²-n²)/(2nβ) ]²，β² = 2mV₀a²/ℏ²
#   cand  : 3D 径向 FD（ℓ=0，u=rR，V=-V₀ e^{-r/a}/(1-e^{-r/a})）
#   默认 V₀=0.5878 eV、a=1.5277 nm ⇒ β²=36，前 4 个束缚态 -5.000/-1.045/-0.3306/-0.1021 eV
#   🔴 参数标定血案：能量公式乘的是 **V₀**（非 ℏ²/2ma²）——初版误用后者 ⇒ β²=100 档
#      算出 E₁=-490 eV（深束缚、波函数被压缩到 0.009 nm）⇒ 网格分辨率不足、残差 0.41 eV。
# ===========================================================================
_HUL_A_M = 1.5277e-9


def hulthen_E_closed(V0_eV: float, a_m: float, n: int) -> float:
    """golden：Hulthen 势 s-wave 第 n 个束缚态 E（eV），n=1,2,…（须 β²>n²）。"""
    V0_J = V0_eV * EV
    beta2 = 2.0 * ME * V0_J * a_m ** 2 / HBAR ** 2
    if beta2 <= n * n:
        raise ValueError(f"hulthen: β²={beta2:.3f} ≤ n²={n*n}，第 {n} 态不存在")
    ratio = (beta2 - n * n) / (2.0 * n * math.sqrt(beta2))
    return -V0_eV * ratio ** 2


def hulthen_E_fd(V0_eV: float, a_m: float, n: int,
                 R: float = 12.0e-9, N: int = 12000) -> float:
    """候选：3D 径向 FD 第 n 个束缚态（eV）。h=1e-12 m（t/|V(r₁)|≈42，免格点伪态）。"""
    V0_J = V0_eV * EV

    def V(r):
        x = r / a_m
        ex = np.exp(-x)
        return -V0_J * ex / (1.0 - ex)

    ev = _radial3d_evals(0.0, R, N, 0, V)
    return float(ev[n - 1]) / EV


def golden_b157(V0_eV: float = 0.5878, a_nm: float = 1.5277) -> float:
    """Hulthen s-wave 第 1 束缚态。"""
    return hulthen_E_closed(V0_eV, a_nm * NM, 1)


def golden_b158(V0_eV: float = 0.5878, a_nm: float = 1.5277) -> float:
    """Hulthen s-wave 第 2 束缚态。"""
    return hulthen_E_closed(V0_eV, a_nm * NM, 2)


def golden_b159(V0_eV: float = 0.5878, a_nm: float = 1.5277) -> float:
    """Hulthen s-wave 第 3 束缚态。"""
    return hulthen_E_closed(V0_eV, a_nm * NM, 3)


def golden_b160(V0_eV: float = 0.5878, a_nm: float = 1.5277) -> float:
    """Hulthen s-wave 第 4 束缚态。"""
    return hulthen_E_closed(V0_eV, a_nm * NM, 4)


def cand_hulthen(n, V0_eV, a_nm) -> float:
    """候选工厂：Hulthen s-wave 第 n 束缚态（eV）。"""
    return hulthen_E_fd(float(V0_eV), float(a_nm) * NM, int(n))


# ===========================================================================
# 族 C：Fock-Darwin 2D 量子点（抛物约束 + 垂直磁场）（B161-B164）
#   golden: ε = ℏΩ(2n_r+|m|+1) - (ℏω_c/2)m，Ω=√(ω₀²+ω_c²/4)，ω_c=eB/m*
#   cand  : 2D 径向 FD（ν=|m|≥2，V_extra=½m*Ω²r²）+ L_z 项 (ℏω_c/2)m 解析本征
#   默认：m*=0.067 m₀、ℏω₀=5 meV、B=5 T ⇒ ℏω_c≈8.639 meV、ℏΩ≈6.607 meV
# ===========================================================================
_MSTAR = 0.067 * ME
_FD_HBAR_OM0_MEV = 5.0     # ℏω₀


def _fd_omega(B_T: float):
    """返回 (Ω, ω_c)，rad/s。"""
    omega0 = _FD_HBAR_OM0_MEV * 1.0e-3 * EV / HBAR
    wc = ECHARGE * B_T / _MSTAR
    Om = math.sqrt(omega0 ** 2 + wc ** 2 / 4.0)
    return Om, wc


def fock_darwin_E_closed(n_r: int, m: int, B_T: float = 5.0) -> float:
    """golden：Fock-Darwin 能级 ε（meV）。符号约定：ε=ℏΩ(2n_r+|m|+1)-(ℏω_c/2)m。"""
    Om, wc = _fd_omega(B_T)
    e_j = HBAR * Om * (2 * n_r + abs(m) + 1) - 0.5 * HBAR * wc * m
    return e_j / EV * 1.0e3


def fock_darwin_E_fd(n_r: int, m: int, B_T: float = 5.0,
                     R_mult: float = 8.0, N: int = 6000) -> float:
    """候选：2D 径向 FD 第 n_r 个本征（固定 ν=|m|≥2）+ L_z 项，meV。"""
    Om, wc = _fd_omega(B_T)
    lam = math.sqrt(HBAR / (2.0 * _MSTAR * Om))
    R = R_mult * lam

    def V_extra(r):
        return 0.5 * _MSTAR * Om ** 2 * r ** 2

    ev = _radial2d_evals(0.0, R, N, float(abs(m)), V_extra, mass=_MSTAR)
    e_rad = float(ev[n_r])                      # J（= ℏΩ(2n_r+|m|+1)）
    e_j = e_rad - 0.5 * HBAR * wc * float(m)    # ＋L_z 项（严格对角，非近似）
    return e_j / EV * 1.0e3


def golden_b161(B_T: float = 5.0) -> float:
    """Fock-Darwin (n_r=0,m=2)。"""
    return fock_darwin_E_closed(0, 2, B_T)


def golden_b162(B_T: float = 5.0) -> float:
    """Fock-Darwin (n_r=0,m=3)。"""
    return fock_darwin_E_closed(0, 3, B_T)


def golden_b163(B_T: float = 5.0) -> float:
    """Fock-Darwin (n_r=0,m=4)。"""
    return fock_darwin_E_closed(0, 4, B_T)


def golden_b164(B_T: float = 5.0) -> float:
    """Fock-Darwin (n_r=1,m=2)。"""
    return fock_darwin_E_closed(1, 2, B_T)


def cand_fock_darwin(n_r, m, B_T) -> float:
    """候选工厂：Fock-Darwin (n_r, m, B)（meV）。"""
    return fock_darwin_E_fd(int(n_r), int(m), float(B_T))


# ===========================================================================
# 族 D：Rosen-Morse II 势束缚态（sech² + tanh）（B165-B168）
#   V(x) = B·tanh(αx) - C·sech²(αx)
#   β=2μB/(ℏ²α²)、γ=2μC/(ℏ²α²)、b_n=√(γ+1/4)-n-1/2、a_n=-β/(2b_n)
#   E_n = -(ℏ²α²/2μ)(a_n²+b_n²)
#   默认：α⁻¹=1 nm、C=4 eV、B=0.4 eV ⇒ 前 4 态 -3.6397/-2.9368/-2.3111/-1.7637 eV
# ===========================================================================
def rosen_morse_E_closed(C_eV: float, B_eV: float, alpha_inv_nm: float, n: int) -> float:
    """golden：Rosen-Morse II 第 n 态 E（eV）。"""
    alpha = 1.0 / (alpha_inv_nm * NM)
    scale = HBAR ** 2 * alpha ** 2 / (2.0 * ME) / EV    # eV
    gamma = C_eV / scale
    beta = B_eV / scale
    b_n = math.sqrt(gamma + 0.25) - n - 0.5
    if b_n <= 0.0:
        raise ValueError(f"rosen_morse: b_n={b_n:.4f} ≤ 0，第 {n} 态不存在")
    a_n = -beta / (2.0 * b_n)
    return -scale * (a_n ** 2 + b_n ** 2)


def rosen_morse_E_fd(C_eV: float, B_eV: float, alpha_inv_nm: float, n: int,
                     L_nm: float = 12.0, N: int = 20000) -> float:
    """候选：1D FD 第 n 个束缚态（eV）。x∈(-L,L) Dirichlet，大盒 L=12 nm。"""
    alpha = 1.0 / (alpha_inv_nm * NM)
    L = L_nm * NM
    h = 2.0 * L / (N + 1)
    x = -L + h * np.arange(1, N + 1)
    t = HBAR ** 2 / (2.0 * ME * h ** 2)
    V = (B_eV * np.tanh(alpha * x) - C_eV / np.cosh(alpha * x) ** 2) * EV
    ev = _tri_evals(2.0 * t + V, -t * np.ones(N - 1))
    return float(ev[n]) / EV


def golden_b165(C_eV: float = 4.0, B_eV: float = 0.4, alpha_inv_nm: float = 1.0) -> float:
    """Rosen-Morse II 第 0 态（基态）。"""
    return rosen_morse_E_closed(C_eV, B_eV, alpha_inv_nm, 0)


def golden_b166(C_eV: float = 4.0, B_eV: float = 0.4, alpha_inv_nm: float = 1.0) -> float:
    """Rosen-Morse II 第 1 态。"""
    return rosen_morse_E_closed(C_eV, B_eV, alpha_inv_nm, 1)


def golden_b167(C_eV: float = 4.0, B_eV: float = 0.4, alpha_inv_nm: float = 1.0) -> float:
    """Rosen-Morse II 第 2 态。"""
    return rosen_morse_E_closed(C_eV, B_eV, alpha_inv_nm, 2)


def golden_b168(C_eV: float = 4.0, B_eV: float = 0.4, alpha_inv_nm: float = 1.0) -> float:
    """Rosen-Morse II 第 3 态。"""
    return rosen_morse_E_closed(C_eV, B_eV, alpha_inv_nm, 3)


def cand_rosen_morse(n, C_eV, B_eV) -> float:
    """候选工厂：Rosen-Morse II 第 n 态（eV）。"""
    return rosen_morse_E_fd(float(C_eV), float(B_eV), 1.0, int(n))


# ===========================================================================
# 自测：16/16 golden ↔ cand 残差非零 + 判据 D 响应（参数×1.1 双向同步偏移）
# ===========================================================================
_CASES = [
    # (锚号, golden_thunk, cand_thunk, D 参数字典)
    ("B153", lambda: golden_b153(5.0),    lambda: cand_beam(1, 5.0),          {"L_um": 5.0}),
    ("B154", lambda: golden_b154(5.0),    lambda: cand_beam(2, 5.0),          {"L_um": 5.0}),
    ("B155", lambda: golden_b155(5.0),    lambda: cand_beam(3, 5.0),          {"L_um": 5.0}),
    ("B156", lambda: golden_b156(5.0),    lambda: cand_beam(4, 5.0),          {"L_um": 5.0}),
    ("B157", lambda: golden_b157(0.5878, 1.5277), lambda: cand_hulthen(1, 0.5878, 1.5277), {"V0_eV": 0.5878}),
    ("B158", lambda: golden_b158(0.5878, 1.5277), lambda: cand_hulthen(2, 0.5878, 1.5277), {"V0_eV": 0.5878}),
    ("B159", lambda: golden_b159(0.5878, 1.5277), lambda: cand_hulthen(3, 0.5878, 1.5277), {"V0_eV": 0.5878}),
    ("B160", lambda: golden_b160(0.5878, 1.5277), lambda: cand_hulthen(4, 0.5878, 1.5277), {"V0_eV": 0.5878}),
    ("B161", lambda: golden_b161(5.0),    lambda: cand_fock_darwin(0, 2, 5.0), {"B_T": 5.0}),
    ("B162", lambda: golden_b162(5.0),    lambda: cand_fock_darwin(0, 3, 5.0), {"B_T": 5.0}),
    ("B163", lambda: golden_b163(5.0),    lambda: cand_fock_darwin(0, 4, 5.0), {"B_T": 5.0}),
    ("B164", lambda: golden_b164(5.0),    lambda: cand_fock_darwin(1, 2, 5.0), {"B_T": 5.0}),
    ("B165", lambda: golden_b165(4.0, 0.4, 1.0), lambda: cand_rosen_morse(0, 4.0, 0.4), {"B_eV": 0.4}),
    ("B166", lambda: golden_b166(4.0, 0.4, 1.0), lambda: cand_rosen_morse(1, 4.0, 0.4), {"B_eV": 0.4}),
    ("B167", lambda: golden_b167(4.0, 0.4, 1.0), lambda: cand_rosen_morse(2, 4.0, 0.4), {"B_eV": 0.4}),
    ("B168", lambda: golden_b168(4.0, 0.4, 1.0), lambda: cand_rosen_morse(3, 4.0, 0.4), {"B_eV": 0.4}),
]


def _self_test() -> None:
    print(f"RYDBERG_EV = {RYDBERG_EV:.9f} eV   KIN = {KIN:.6e} J·m²")
    # Hulthen → 氢原子极限自检（a→∞ 时应还原 -m·KE2²/(2ℏ²n²)）
    a_big = 1.0e6 * NM
    V0_big = KE2 / (a_big / NM * NM)          # V₀·a = KE2 ⇒ 纯 Coulomb 极限
    e_h = hulthen_E_closed(V0_big, a_big, 1)
    e_ry = -RYDBERG_EV
    print(f"[自检] Hulthen a→∞ 极限 E₁ = {e_h:.6f} eV  vs  氢 1s {e_ry:.6f} eV  "
          f"（差 {abs(e_h - e_ry):.2e}）")
    print(f"{'锚号':<6}{'golden':>18}{'cand':>18}{'|diff|':>16}{'余量×':>10}  判据D")
    nz = 0
    worst = (0.0, "")
    for bid, g, c, dpar in _CASES:
        gv, cv = g(), c()
        diff = abs(gv - cv)
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
    print(f"非零残差：{nz}/16    worst = {worst[1]} |d|={worst[0]:.3e}（tol 0.01，余量 {0.01/worst[0]:.1f}×）")


def _golden_by_bid(bid: str, dpar: dict) -> float:
    if bid == "B153":
        return golden_b153(dpar["L_um"])
    if bid == "B154":
        return golden_b154(dpar["L_um"])
    if bid == "B155":
        return golden_b155(dpar["L_um"])
    if bid == "B156":
        return golden_b156(dpar["L_um"])
    if bid == "B157":
        return golden_b157(dpar["V0_eV"], 1.5277)
    if bid == "B158":
        return golden_b158(dpar["V0_eV"], 1.5277)
    if bid == "B159":
        return golden_b159(dpar["V0_eV"], 1.5277)
    if bid == "B160":
        return golden_b160(dpar["V0_eV"], 1.5277)
    if bid == "B161":
        return golden_b161(dpar["B_T"])
    if bid == "B162":
        return golden_b162(dpar["B_T"])
    if bid == "B163":
        return golden_b163(dpar["B_T"])
    if bid == "B164":
        return golden_b164(dpar["B_T"])
    if bid == "B165":
        return golden_b165(4.0, dpar["B_eV"], 1.0)
    if bid == "B166":
        return golden_b166(4.0, dpar["B_eV"], 1.0)
    if bid == "B167":
        return golden_b167(4.0, dpar["B_eV"], 1.0)
    if bid == "B168":
        return golden_b168(4.0, dpar["B_eV"], 1.0)
    raise KeyError(bid)


def _cand_by_bid(bid: str, dpar: dict) -> float:
    if bid == "B153":
        return cand_beam(1, dpar["L_um"])
    if bid == "B154":
        return cand_beam(2, dpar["L_um"])
    if bid == "B155":
        return cand_beam(3, dpar["L_um"])
    if bid == "B156":
        return cand_beam(4, dpar["L_um"])
    if bid == "B157":
        return cand_hulthen(1, dpar["V0_eV"], 1.5277)
    if bid == "B158":
        return cand_hulthen(2, dpar["V0_eV"], 1.5277)
    if bid == "B159":
        return cand_hulthen(3, dpar["V0_eV"], 1.5277)
    if bid == "B160":
        return cand_hulthen(4, dpar["V0_eV"], 1.5277)
    if bid == "B161":
        return cand_fock_darwin(0, 2, dpar["B_T"])
    if bid == "B162":
        return cand_fock_darwin(0, 3, dpar["B_T"])
    if bid == "B163":
        return cand_fock_darwin(0, 4, dpar["B_T"])
    if bid == "B164":
        return cand_fock_darwin(1, 2, dpar["B_T"])
    if bid == "B165":
        return cand_rosen_morse(0, 4.0, dpar["B_eV"])
    if bid == "B166":
        return cand_rosen_morse(1, 4.0, dpar["B_eV"])
    if bid == "B167":
        return cand_rosen_morse(2, 4.0, dpar["B_eV"])
    if bid == "B168":
        return cand_rosen_morse(3, 4.0, dpar["B_eV"])
    raise KeyError(bid)


if __name__ == "__main__":
    _self_test()
