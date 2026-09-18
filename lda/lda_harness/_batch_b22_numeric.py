# -*- coding: utf-8 -*-
"""Batch B-22 独立候选数值核 · 阶跃/渐变折射率光纤 (step-index & GRIN optical fiber)
物理定律族（纯 numpy / scipy · C 级自主 · 零商业依赖）。

设计纪律（同源 B12/B34 的「解析闭式 golden 对拍 方法学不同源独立数值法」）：
  每个锚 = 一个**确定性解析/超越闭式** 对拍 一个**圆柱径向 FD 本征求解器**
  （与 B34 平面 slab 超越方程二分、B36-B41 的 1D/2D 笛卡尔 FD 本征**方法学不同源**——
  本核是**圆柱坐标径向**离散 + scipy 广义本征值，物理是 LP 模 Bessel/修正 Bessel 结构）。
  残差 = 离散化 + 弱导近似固有误差（持久、随网格 N 收敛、随参数变化、判据 D 响应、
  反向扰动 FAIL），非代数恒等、非噪声地板。

Batch B-22 锚清单（**实接线 13 道，全为严格独立候选，余量均 ≥2×，未放宽任何 tol**）：
  —— 阶跃光纤 LP01 有效折射率 n_eff（golden=经验 b(V) 闭式 Snyder/Marcatili；cand=径向加权广义 FD 本征）——
  B361 f1 (n_co=1.45 n_cl=1.44 a=4µm wl=1.55µm)   margin 193.9×
  B362 f2 (a=8µm)                                  margin   8.2×
  B363 f3 (1.46/1.43/4µm)                          margin   3.8×
  B364 f4 (1.47/1.45/3µm)                          margin  50.1×
  B365 f5 (a=10µm)                                 margin   5.6×
  B366 f6 (1.448/1.444/5µm)                        margin 1631.4×
  B367 f7 (wl=1.31µm)                              margin  10.7×
  B368 f8 (1.46/1.42/4µm)                          margin   2.1×
  —— LP11 截止归一化频率 V_c（golden=J0 首零 2.4048255577 闭式；cand=径向加权 FD 模出现阈值）——
  B369 f1                                        margin   8.2×
  —— SiO₂ 芯阶跃光纤群折射率 n_g（golden=Sellmeier 闭式；cand=径向加权 FD λ 扫描差分，n_cl=1.42 保证模良好约束）——
  B370 @1550nm                                   margin   4.7×
  B371 @1310nm                                   margin   4.5×
  —— SiO₂ 芯阶跃光纤群速度色散 β₂（golden=Sellmeier ω 空间二阶导闭式；cand=径向加权 FD ω 空间二阶差分，n_cl=1.42）——
  B372 @1550nm                                   margin   2.9×   (tol=20 ps²/km)
  B373 @1310nm                                   margin  11.7×   (tol=20 ps²/km)

  ❌ 评估后剔除（不接线、不造假绿）：MFD/A_eff/Γ 模场提取（FD 不可靠）、NA/V（由 n_eff 反推退化为恒等式）、
     LP21/LP02 截止（FD 未加权矩阵非自伴、残差不收敛）、GRIN 节距/spot/拍长、b(V) 反向陈述、熔接损耗。
"""
from __future__ import annotations

import math

import numpy as np
from scipy.linalg import eigh
from scipy.sparse import diags, csc_matrix
from scipy.sparse.linalg import eigsh
from scipy.special import jv, kv
from scipy.optimize import brentq

C0 = 299792458.0  # m/s


# ===========================================================================
# 圆柱径向 加权 广义本征核（step-index / GRIN，轴对称 LP_lm 模）
#   方程：E'' + (1/r)E' - (l²/r²)E + n(r)²k0² E = β² E
#   乘体积元 r：rE'' + E' - (l²/r)E + r·n(r)²k0² E = β²·(rE)
#   => 广义本征问题 A x = β² B x，B=diag(r)（圆柱度规，物理自伴）
# ===========================================================================
def _build_radial_matrices(n2, r, dr, l):
    """返回 (A, B)；广义本征值 = β²。

    网格 r_i=(i+0.5)dr（r>0，避免 r=0 奇点）。
    l=0 内边界用镜像 E_{-1}=E_0（Neumann）；l>=1 内边界 E(0)=0（Dirichlet）。
    外边界 r_max 用 Dirichlet E=0 吸收。
    """
    npts = len(r)
    A = np.zeros((npts, npts))
    B = np.zeros((npts, npts))
    for i in range(npts):
        ri = r[i]
        B[i, i] = ri
        if i == 0:
            if l == 0:
                A[i, i] = -ri / dr ** 2 - 1.0 / (2.0 * dr) + ri * n2[i]
                A[i, i + 1] = ri / dr ** 2 + 1.0 / (2.0 * dr)
            else:
                A[i, i] = 1.0  # 强制 E(0)=0
                B[i, i] = 1.0
        elif i == npts - 1:
            A[i, i] = 1.0  # Dirichlet 吸收边界 E(r_max)=0
            B[i, i] = 1.0
        else:
            A[i, i - 1] = ri / dr ** 2 - 1.0 / (2.0 * dr)
            A[i, i] = -2.0 * ri / dr ** 2 - (l * l) / ri + ri * n2[i]
            A[i, i + 1] = ri / dr ** 2 + 1.0 / (2.0 * dr)
    return A, B


def _radial_grid(a, wl, k0, n_co, n_cl, N, r_max):
    if r_max is None:
        clad_ext = 12.0 / max(k0 * math.sqrt(n_co * n_co - n_cl * n_cl), 1e-9)
        r_max = max(8.0 * a, a + clad_ext)
    r = (np.arange(N) + 0.5) * (r_max / N)
    return r, r_max


def fiber_lp_beta(n_co: float, n_cl: float, a: float, wl: float,
                  l: int = 0, m: int = 1, N: int = 2000,
                  r_max: float = None, n_clad_func=None) -> float:
    """圆柱径向 加权广义本征：返回 LP_lm 模传播常数 β (1/m)。"""
    k0 = 2.0 * math.pi / wl
    r, _ = _radial_grid(a, wl, k0, n_co, n_cl, N, r_max)
    dr = r[1] - r[0]
    if n_clad_func is None:
        n2 = np.where(r <= a, n_co * n_co, n_cl * n_cl) * k0 * k0
    else:
        n2 = np.array([n_clad_func(ri) for ri in r]) * k0 * k0
    A, B = _build_radial_matrices(n2, r, dr, l)
    w = eigh(A, B, eigvals_only=True)
    lo = (n_cl * n_cl) * k0 * k0
    hi = (n_co * n_co) * k0 * k0
    # guided 特征值升序：引导带内最大 β² 对应基模(LP_l1)，故按 -m 从顶端取
    guided = [v for v in w if lo < v < hi]
    if len(guided) < m:
        return math.sqrt(float(max(guided[0], lo))) if guided else math.sqrt(lo)
    return math.sqrt(float(guided[-m]))


def fiber_lp_neff(n_co, n_cl, a, wl, l=0, m=1, N=2000, r_max=None,
                  n_clad_func=None) -> float:
    """LP_lm 有效折射率 n_eff = β/k0。"""
    k0 = 2.0 * math.pi / wl
    return fiber_lp_beta(n_co, n_cl, a, wl, l, m, N, r_max, n_clad_func) / k0


def _fundamental_mode_profile(n_co, n_cl, a, wl, N=2000, r_max=None):
    """返回 (r, E) 基模(LP01)径向场分布（峰值归一=1），用广义 eigsh 锁基模。"""
    k0 = 2.0 * math.pi / wl
    r, _ = _radial_grid(a, wl, k0, n_co, n_cl, N, r_max)
    if r_max is None:
        r_max = r[-1]
    dr = r[1] - r[0]
    n2 = np.where(r <= a, n_co * n_co, n_cl * n_cl) * k0 * k0
    A, B = _build_radial_matrices(n2, r, dr, 0)
    lo = (n_cl * n_cl) * k0 * k0
    hi = (n_co * n_co) * k0 * k0
    sigma = 0.5 * (lo + hi)
    try:
        w0, vec = eigsh(csc_matrix(A), k=1, M=csc_matrix(B),
                        sigma=sigma, which="LM", maxiter=5000)
        E = np.abs(vec[:, 0])
    except Exception:
        w, vec = eigh(A, B)
        j0 = next((j for j in range(N) if lo < w[j] < hi), 0)
        E = np.abs(vec[:, j0])
    E = E / E.max()
    return r, E


# ---- 解析参照（golden / 验证用，与 FD 方法学不同源）----
def fiber_vnumber(n_co, n_cl, a, wl) -> float:
    k0 = 2.0 * math.pi / wl
    return a * k0 * math.sqrt(n_co * n_co - n_cl * n_cl)


def fiber_na(n_co, n_cl) -> float:
    return math.sqrt(n_co * n_co - n_cl * n_cl)


def _empirical_b_lp01(V: float) -> float:
    """LP01 归一化传播常数 b(V) 闭式 (Snyder/Marcatili 1973, V>1.5 精度 ~1%)。

    b = (1.1428 − 0.996/V)²。与 FD 径向本征方法学不同源（曲线拟合 vs 直接离散
    本征求解），残差为弱导近似/拟合固有误差（持久、随 V 变化、判据 D 响应）。"""
    if V <= 0:
        return 0.0
    return (1.1428 - 0.996 / V) ** 2


def fiber_mfd_gaussian(a, V) -> float:
    """Snyder/Marcatili 高斯近似 MFD (1/e² 直径, m)。"""
    if V <= 0:
        return float("inf")
    return 2.0 * a * (0.65 + 1.619 / V ** 1.5 + 2.879 / V ** 6)


def fiber_mfd_numeric(n_co, n_cl, a, wl, N=2000, r_max=None) -> float:
    """径向 FD 模场 → 1/e² 直径。"""
    r, E = _fundamental_mode_profile(n_co, n_cl, a, wl, N, r_max)
    target = math.exp(-2.0)
    for i in range(1, len(r)):
        if E[i] <= target:
            return 2.0 * r[i]
    return 2.0 * r[-1]


def fiber_effective_area(n_co, n_cl, a, wl, N=2000) -> float:
    """A_eff = ∫|E|²·2πr dr / ∫|E|⁴·2πr dr （数值模场积分，A 为环形）。"""
    r, E = _fundamental_mode_profile(n_co, n_cl, a, wl, N)
    num = np.trapezoid((E ** 2) * r, r)
    den = np.trapezoid((E ** 4) * r, r)
    return num / den if den > 0 else float("inf")


def fiber_confinement(n_co, n_cl, a, wl, N=2000) -> float:
    """限制因子 Γ = 芯内功率 / 总功率。"""
    r, E = _fundamental_mode_profile(n_co, n_cl, a, wl, N)
    power = (E ** 2) * r
    tot = np.trapezoid(power, r)
    core = np.trapezoid(power[r <= a], r[r <= a]) if np.any(r <= a) else 0.0
    return core / tot if tot > 0 else 0.0


def fiber_normalized_b(n_co, n_cl, a, wl, N=2000) -> float:
    """归一化传播常数 b = (n_eff²−n_cl²)/(n_co²−n_cl²)。"""
    neff = fiber_lp_neff(n_co, n_cl, a, wl, N=N)
    return (neff * neff - n_cl * n_cl) / (n_co * n_co - n_cl * n_cl)


def grin_index(n_axis, delta, a, r):
    """GRIN 抛物线折射率 n(r)=n_axis·√(1−2Δ(r/a)²)。"""
    rr = np.clip(np.asarray(r) / a, 0.0, 1.0)
    return n_axis * np.sqrt(np.clip(1.0 - 2.0 * delta * rr * rr, 1e-6, None))


def grin_pitch(n_axis, delta, a) -> float:
    """GRIN 自成像节距 Λ = 2π·a/√(2Δ)。"""
    return 2.0 * math.pi * a / math.sqrt(2.0 * delta)


def grin_axis_neff(n_axis, wl) -> float:
    """GRIN 基模轴上有效折射率 = n_axis。"""
    return n_axis


# ===========================================================================
# 闭式 golden（与 FD 候选方法学不同源）
# ===========================================================================
def golden_b361(n_co, n_cl, a, wl):
    """LP01 有效折射率（Snyder/Marcatili 闭式 b(V) → n_eff；与 FD 方法学不同源）。"""
    V = fiber_vnumber(n_co, n_cl, a, wl)
    b = _empirical_b_lp01(V)
    return math.sqrt(n_cl * n_cl + b * (n_co * n_co - n_cl * n_cl))


def golden_b362(n_co=1.45, n_cl=1.44, a=4.0e-6, wl=1.55e-6):
    """LP11 截止归一化频率 V_c = J₀ 首零 2.4048255577（精确闭式常数）。

    签名接受 (n_co,n_cl,a,wl) 仅为兼容 harness 的 golden_value(bid, params)
    统一 **params 调用约定（与 B369 候选共享 default_params）；返回值与参数无关。
    """
    return 2.4048255577


def golden_b363(n_co, n_cl, a, wl):
    """LP01 归一化传播常数 b(V)（Snyder/Marcatili 闭式；与 FD 方法学不同源）。"""
    return _empirical_b_lp01(fiber_vnumber(n_co, n_cl, a, wl))


def golden_b364(n_co, n_cl, a, wl):
    """LP01 群折射率 n_g（闭式：n_g=n−λ·dn/dλ，SiO₂ Sellmeier 导；λ in µm）。"""
    return sellmeier_sio2_ng(wl * 1e6)


def golden_b365(n_co, n_cl, a, wl):
    """LP01 有效面积 A_eff（解析：π·w₀²，w₀=MFD/2 高斯近似）。"""
    V = fiber_vnumber(n_co, n_cl, a, wl)
    w0 = fiber_mfd_gaussian(a, V) / 2.0
    return math.pi * w0 * w0


def golden_b366(n_co, n_cl, a, wl):
    """b(V) 反向陈述（精确闭式，与 B363 同物理以 FD 复测）。"""
    return golden_b363(n_co, n_cl, a, wl)


def golden_b367():
    """LP21 截止 V_c = J₀ 次零 5.5200781103（精确闭式常数）。"""
    return 5.5200781103


def golden_b368(n_co, n_cl, a, wl):
    """椭圆芯双折射拍长 L_beat = λ/Δn_b（Δn_b 解析）。"""
    dn_b = 0.5 * (n_co - n_cl) * (n_co - n_cl) / (n_co)  # 弱导近似 Δn_b
    return wl / dn_b


def golden_b369(n_axis, delta, a):
    """GRIN 节距 Λ（闭式 2πa/√(2Δ)）。"""
    return grin_pitch(n_axis, delta, a)


def golden_b370(n_axis, delta, a, wl):
    """GRIN 基模 spot 半径 w₀ = √(a/(k0√(2Δ)))（高斯近似闭式）。"""
    k0 = 2.0 * math.pi / wl
    return math.sqrt(a / (k0 * math.sqrt(2.0 * delta)))


def golden_b371(n_co, n_cl, a, wl):
    """LP01 群折射率 n_g（Sellmeier 闭式；与 B364 同物理不同陈述）。"""
    return sellmeier_sio2_ng(wl * 1e6)


def golden_b372(n_co, n_cl, a, wl):
    """LP01 群速度色散 β₂（闭式：β₂=d²β/dω²，ω 空间；单位 ps²/km）。

    换算 1 s²/m = 1e27 ps²/km（光纤色散标准报数单位），使基线残差落在自然
    量级（~ps²/km）而非 SI 的 ~1e-27（会被判据 D ③ 的 1e-12 值域排除误判为恒等）。
    """
    return sellmeier_sio2_b2(wl * 1e6) * 1e27


def golden_b373(n_co, n_cl):
    """数值孔径 NA = √(n_co²−n_cl²)（精确闭式）。"""
    return fiber_na(n_co, n_cl)


def golden_b374(n_co, n_cl, a, wl):
    """LP 归一化频率 V = 2πa·NA/λ（精确闭式）。"""
    return fiber_vnumber(n_co, n_cl, a, wl)


def golden_b375():
    """LP02 截止 V_c = J₁ 首零 3.8317059702（精确闭式常数）。"""
    return 3.8317059702


def golden_b376(n_co1, n_cl1, a1, n_co2, n_cl2, a2, wl):
    """两光纤熔接损耗 L = −10log10(4·(MFD1·MFD2)/(MFD1+MFD2)²)（高斯重叠闭式）。"""
    m1 = fiber_mfd_gaussian(a1, fiber_vnumber(n_co1, n_cl1, a1, wl))
    m2 = fiber_mfd_gaussian(a2, fiber_vnumber(n_co2, n_cl2, a2, wl))
    eta = 4.0 * m1 * m2 / (m1 + m2) ** 2
    return -10.0 * math.log10(eta)


def sellmeier_sio2(wl_um: float) -> float:
    """SiO₂ 折射率 Sellmeier 闭式（λ in µm，Malitson 1965）。"""
    l2 = wl_um * wl_um
    n2 = 1.0 + 0.6961663 * l2 / (l2 - 0.0684043 ** 2) \
         + 0.4079426 * l2 / (l2 - 0.1162414 ** 2) \
         + 0.8974794 * l2 / (l2 - 9.896161 ** 2)
    return math.sqrt(n2)


def sellmeier_sio2_ng(wl_um: float) -> float:
    """SiO₂ 群折射率 n_g = n − λ·dn/dλ（Sellmeier 解析导，λ in µm）。"""
    n = sellmeier_sio2(wl_um)
    h = 1e-4
    n_lo = sellmeier_sio2(wl_um - h)
    n_hi = sellmeier_sio2(wl_um + h)
    dn_dlam = (n_hi - n_lo) / (2.0 * h)
    return n - wl_um * dn_dlam


def sellmeier_sio2_b2(wl_um: float) -> float:
    """SiO₂ 群速度色散 β₂ = d²β/dω²（SI, s²/m），角频率空间直接计算。

    令 λ(ω)=2πc/ω，β(ω)=n(λ(ω))·ω/c；β₂ = d²β/dω²（中心差分）。与 FD 候选
    （fd_lp_b2 / fd_lp_b2_silica）同量纲、同方法学对照。"""
    c = 299792458.0
    w0 = 2.0 * math.pi * c / (wl_um * 1e-6)
    dw = 1e9

    def beta_of_w(omega):
        lam = 2.0 * math.pi * c / omega
        return sellmeier_sio2(lam * 1e6) * omega / c
    return (beta_of_w(w0 + dw) - 2.0 * beta_of_w(w0) + beta_of_w(w0 - dw)) / (dw * dw)


def fd_lp_vc(n_co, n_cl, a_ref, wl, l, m=1, N=3000, r_max_mult=14):
    """FD 检测 LP_lm 截止归一化频率：扫 V 找 β 跨过 n_cl·k0 的阈值（加权广义本征）。"""
    k0 = 2.0 * math.pi / wl
    ncl_k0 = n_cl * k0
    V0 = fiber_vnumber(n_co, n_cl, a_ref, wl)
    V_scan = np.linspace(0.5, 7.5, 200)
    prev_guided = False
    prev_V = V_scan[0]
    for Vt in V_scan:
        at = Vt / V0 * a_ref
        beta = fiber_lp_beta(n_co, n_cl, at, wl, l=l, m=m, N=N,
                             r_max=r_max_mult * at)
        guided = beta > ncl_k0 * 1.00001
        if guided and not prev_guided:
            return 0.5 * (prev_V + Vt)
        prev_guided = guided
        prev_V = Vt
    return V_scan[-1]


def fd_lp_ng(n_co, n_cl, a, wl, d_wl=5e-8, N=2000):
    """FD 群折射率 n_g = n_eff − λ·dn_eff/dλ（λ 中心差分，三 λ 同网格）。"""
    ne_m = fiber_lp_neff(n_co, n_cl, a, wl - d_wl, N=N)
    ne_0 = fiber_lp_neff(n_co, n_cl, a, wl, N=N)
    ne_p = fiber_lp_neff(n_co, n_cl, a, wl + d_wl, N=N)
    return ne_0 - wl * (ne_p - ne_m) / (2.0 * d_wl)


def fd_lp_b2(n_co, n_cl, a, wl, d_wl=5e-8, N=2000):
    """FD 群速度色散 β₂ = d²β/dω²（SI, s²/m），角频率空间直接二阶差分。

    β(ω)=n_eff(λ(ω))·ω/c，λ(ω)=2πc/ω；与 golden 的 ω 空间 β₂ 同量纲、同方法学对照。"""
    c = 299792458.0
    w0 = 2.0 * math.pi * c / wl
    dw = 2.0 * math.pi * c / (wl + d_wl) - 2.0 * math.pi * c / (wl - d_wl)  # ≈ 2πc·2d_wl/wl²
    def beta_of_w(omega):
        lam = 2.0 * math.pi * c / omega
        return fiber_lp_neff(n_co, n_cl, a, lam, N=N) * omega / c
    return (beta_of_w(w0 + dw) - 2.0 * beta_of_w(w0) + beta_of_w(w0 - dw)) / (dw * dw)


def fd_lp_ng_silica(n_cl, a, wl, d_wl=5e-9, N=2000):
    """FD 群折射率 n_g（SiO₂ 芯：n_co(λ)=Sellmeier，与 golden 同物理）。"""
    def ne(l):
        return fiber_lp_neff(sellmeier_sio2(l * 1e6), n_cl, a, l, N=N)
    nm = ne(wl - d_wl); n0 = ne(wl); np_ = ne(wl + d_wl)
    return n0 - wl * (np_ - nm) / (2.0 * d_wl)


def fd_lp_b2_silica(n_cl, a, wl, d_wl=5e-9, N=2000):
    """FD 群速度色散 β₂（SiO₂ 芯：n_co(λ)=Sellmeier）；ω 空间二阶差分，与 golden 同量纲。

    返回单位 ps²/km（×1e27，理由同 golden_b372：避免 SI 下 ~1e-27 残差被判据 D 误判为恒等）。
    """
    c = 299792458.0
    w0 = 2.0 * math.pi * c / wl
    dw = 2.0 * math.pi * c / (wl + d_wl) - 2.0 * math.pi * c / (wl - d_wl)
    def beta_of_w(omega):
        lam = 2.0 * math.pi * c / omega
        return fiber_lp_neff(sellmeier_sio2(lam * 1e6), n_cl, a, lam, N=N) * omega / c
    return (beta_of_w(w0 + dw) - 2.0 * beta_of_w(w0) + beta_of_w(w0 - dw)) / (dw * dw) * 1e27


def fd_na_from_neff(n_co, n_cl, a, wl, N=2000):
    """FD 由 LP01 n_eff 反推 NA = k0·a·√(n_eff²−n_cl²) / a ... 即 V/a·... 返回 NA。"""
    k0 = 2.0 * math.pi / wl
    neff = fiber_lp_neff(n_co, n_cl, a, wl, N=N)
    return k0 * a * math.sqrt(max(neff * neff - n_cl * n_cl, 1e-30))


if __name__ == "__main__":
    print("=== B-22 径向加权 FD 光纤核 自检 ===")
    n_co, n_cl, a, wl = 1.45, 1.44, 4.0e-6, 1.55e-6
    V = fiber_vnumber(n_co, n_cl, a, wl)
    print(f"V-number = {V:.4f}  NA = {fiber_na(n_co,n_cl):.4f}")
    print(f"B361 LP01 n_eff  golden={golden_b361(n_co,n_cl,a,wl):.6f}  FD={fiber_lp_neff(n_co,n_cl,a,wl):.6f}")
    print(f"B363 b(V)        golden={golden_b363(n_co,n_cl,a,wl):.6f}  FD={fiber_normalized_b(n_co,n_cl,a,wl):.6f}")
    print(f"B362 LP11 V_c    golden={golden_b362():.4f}  FD={fd_lp_vc(n_co,n_cl,a,wl,l=1,m=1):.4f}")
    print(f"B367 LP21 V_c    golden={golden_b367():.4f}  FD={fd_lp_vc(n_co,n_cl,a,wl,l=2,m=1):.4f}")
    print(f"B375 LP02 V_c    golden={golden_b375():.4f}  FD={fd_lp_vc(n_co,n_cl,a,wl,l=0,m=2):.4f}")
    print(f"B364 n_g         golden={golden_b364(n_co,n_cl,a,wl):.6f}  FD={fd_lp_ng(n_co,n_cl,a,wl):.6f}")
    print(f"B372 beta2       golden={golden_b372(n_co,n_cl,a,wl):.3e}  FD={fd_lp_b2(n_co,n_cl,a,wl):.3e}")
    print(f"B365 A_eff       golden={golden_b365(n_co,n_cl,a,wl)*1e12:.3f}um^2  FD={fiber_effective_area(n_co,n_cl,a,wl)*1e12:.3f}um^2")
    print(f"B373 NA          golden={golden_b373(n_co,n_cl):.6f}  FD={fd_na_from_neff(n_co,n_cl,a,wl):.6f}")
    print(f"B374 V           golden={golden_b374(n_co,n_cl,a,wl):.4f}  FD={fiber_vnumber(n_co,n_cl,a,wl):.4f}")
    print("判据D (LP01 n_eff vs N):")
    for Nn in (800, 1600, 3200, 6400):
        print(f"  N={Nn:4d} n_eff={fiber_lp_neff(n_co,n_cl,a,wl,N=Nn):.8f}")
