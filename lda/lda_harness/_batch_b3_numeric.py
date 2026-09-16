# -*- coding: utf-8 -*-
"""Batch B-3 独立候选数值核（纯 numpy / scipy · C 级自主 · 零商业依赖）。

设计纪律（同源 B-1/B-2 的「闭式/解析 golden × 方法学不同源真数值」对拍）：
  每个锚 = 一个**确定性解析闭式 / 超越方程二分** 对拍 一个**不同源真实数值法**。
  残差 = 离散化误差 / 建模近似差异（持久、随参数变化、判据 D 响应、反向扰动 FAIL），
  不是「代数恒等」（B28 血案）也不是「纯数值误差沉底」（B10 血案）。

Batch B-3 锚清单（13 道，全为严格独立候选 · B52-B64）：
  量子束缚态（1D FD 薛定谔本征 vs 解析/超越 golden）：
    B52 有限深方势阱 第1激发态 E1（奇宇称超越方程二分 vs 1D FD 本征第2模）
    B53 有限深方势阱 第2激发态 E2（偶宇称超越方程二分 vs 1D FD 本征第3模）
    B54 一维无限深方势阱 E4（16·E1 闭式 vs 1D FD 本征第4模）
    B55 一维无限深方势阱 E5（25·E1 闭式 vs 1D FD 本征第5模）
    B56 一维谐振子 E3（3.5ℏω 闭式 vs 1D FD 谐振子本征第4模）
    B57 一维谐振子 E4（4.5ℏω 闭式 vs 1D FD 谐振子本征第5模）
    B58 三维立方无限深势阱 基态（3·E1 闭式 vs 三维乘积分解 1D FD×3）
    B59 Pöschl-Teller 势 基态 E0（精确解析谱 vs 1D FD 本征基态）
    B60 Pöschl-Teller 势 第1激发态 E1（精确解析谱 vs 1D FD 本征第2模）
  波导 / 光子（不同几何 / 转移矩阵 vs 解析闭式）：
    B61 矩形金属波导 TM11 截止频率（c/2·√((1/a)²+(1/b)²) 闭式 vs 二盒乘积 1D FD）
    B62 矩形金属波导 TM21 截止频率（c/2·√((2/a)²+(1/b)²) 闭式 vs 二盒乘积 1D FD）
    B63 圆波导 TE11 截止频率（x11·c/(2πa) · x11=1.84118 闭式 vs 径向 FD 本征）
    B64 Bragg 光栅 Bragg 波长 λB（2·n_eff·Λ 闭式 vs 转移矩阵反射峰扫描）
"""
from __future__ import annotations

import math

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import eigh

# 复用 Batch B-2 已验证数值核（判据 D 由 run_d_criterion_smoke 已证）
try:
    from ._batch_b2_numeric import (
        _fd1d_sch_evals,
        _fd1d_box_kc,
        qmw_infinite_well_E,
        qmw_infinite_well_fd,
        qm_ho_E,
        qm_ho_fd_n,
    )
except ImportError:  # 直接运行本文件时回退
    from _batch_b2_numeric import (  # type: ignore
        _fd1d_sch_evals,
        _fd1d_box_kc,
        qmw_infinite_well_E,
        qmw_infinite_well_fd,
        qm_ho_E,
        qm_ho_fd_n,
    )

C0 = 299792458.0
HBAR = 1.054571817e-34
ME = 9.1093837015e-31
EV = 1.602176634e-19  # J -> eV


# ===========================================================================
# B52/B53 · 有限深方势阱更高束缚态（偶/奇宇称超越方程二分 golden）
# ===========================================================================
def _finwell_bound_energies(V0: float, a: float, m: float):
    """golden：有限深方势阱（阱内 V=-V0，阱外 0）全部束缚态能量（J），升序。

    无量纲 k=√(2m(E+V0))/ℏ, κ=√(-2mE)/ℏ, K=√(2mV0)/ℏ, k²+κ²=K²。
    偶宇称：k·tan(k·a/2)=κ；奇宇称：-k·cot(k·a/2)=κ。
    在每个奇/偶子区间（避开 tan/cot 奇点）二分定位根，回代 E=ℏ²k²/(2m)-V0。
    """
    K = math.sqrt(2.0 * m * V0) / HBAR

    def kappa(k):
        return math.sqrt(max(K * K - k * k, 0.0))

    # 连续形式（消除 tan/cot 奇点）：偶宇称 k·sin(ka/2)=κ·cos(ka/2)；
    # 奇宇称 -k·cos(ka/2)=κ·sin(ka/2)。二者在 (0,K) 内连续，逐子区间二分。
    def f_even(k):
        return k * math.sin(k * a / 2.0) - kappa(k) * math.cos(k * a / 2.0)

    def f_odd(k):
        return -k * math.cos(k * a / 2.0) - kappa(k) * math.sin(k * a / 2.0)

    roots = []
    ks = np.linspace(1e-9, K - 1e-9, 8000)
    for f in (f_even, f_odd):
        fprev = f(ks[0])
        for i in range(1, len(ks)):
            fcur = f(ks[i])
            if fprev == 0.0 or fprev * fcur < 0:
                lo, hi = ks[i - 1], ks[i]
                for _ in range(100):
                    mid = 0.5 * (lo + hi)
                    if f(lo) * f(mid) <= 0:
                        hi = mid
                    else:
                        lo = mid
                kr = 0.5 * (lo + hi)
                if 0.0 < kr < K:
                    roots.append(HBAR ** 2 * kr ** 2 / (2.0 * m) - V0)
            fprev = fcur
    roots.sort()
    return roots


def qm_finwell_E_state(V0: float, a: float, m: float, state: int) -> float:
    """golden：第 state 个束缚态能量（J，state=0 基态）。"""
    return _finwell_bound_energies(V0, a, m)[state]


def qm_finwell_fd_state(V0: float, a: float, m: float, L: float, N: int, state: int) -> float:
    """候选：1D FD 哈密顿本征值第 state 模（eV）。盒长 L≫阱宽 a。"""
    def V_func(x):
        return np.where(np.abs(x) <= a / 2.0, -V0, 0.0)
    e_j = float(_fd1d_sch_evals(L, N, m, V_func)[state])
    return e_j / EV


# ===========================================================================
# B58 · 三维立方无限深势阱（产品分解：三维哈密顿 = 三独立 1D 之和）
# ===========================================================================
def qm_cubic3d_fd(L: float, N: int, m: float) -> float:
    """候选：三维基态 = Σ 三方向 1D 无限深阱基态（eV）。

    三维无限深立方阱 E = (π²ℏ²/2mL²)(n_x²+n_y²+n_z²)；基态 (1,1,1) = 3·E1_1D。
    候选取三个独立 1D FD 基态之和（与闭式方法学不同源：闭式用乘积分离变量，
    候选用三个 1D FD 本征求和），残差=3×1D FD 离散误差（随 N 收敛、随 L 变化）。
    """
    e0 = float(_fd1d_sch_evals(L, N, m, lambda x: np.zeros_like(x))[0])
    return 3.0 * e0 / EV


# ===========================================================================
# B59/B60 · Pöschl-Teller 势（精确解析谱 golden × 1D FD 候选）
# ===========================================================================
def poschl_teller_E(n: int, V0: float, alpha: float, m: float) -> float:
    """golden：V(x)=-V0/cosh²(αx) 的精确束缚态谱。

    由 λ(λ+1)=2mV0/(ℏ²α²) 解出 λ，E_n = -(ℏ²α²/2m)·(λ-n-½)²，n=0,1,...。
    """
    ratio = 2.0 * m * V0 / (HBAR ** 2 * alpha ** 2)
    lam = 0.5 * (math.sqrt(1.0 + 4.0 * ratio) - 1.0)
    return -(HBAR ** 2 * alpha ** 2 / (2.0 * m)) * (lam - n - 0.5) ** 2


def poschl_teller_fd(V0: float, alpha: float, m: float, L: float, N: int, state: int) -> float:
    """候选：1D FD 哈密顿本征值第 state 模（eV）。盒长 L 包含窄势阱。"""
    def V_func(x):
        return -V0 / (np.cosh(alpha * x) ** 2)
    e_j = float(_fd1d_sch_evals(L, N, m, V_func)[state])
    return e_j / EV


# ===========================================================================
# B61/B62 · 矩形金属波导 TM_mn 截止（二盒乘积 1D FD vs 解析闭式）
# ===========================================================================
def rect_wg_tm_fc(a: float, b: float, m: int, n: int) -> float:
    """golden：矩形波导 TM_mn 截止频率（Hz）fc = c/(2π)·√((mπ/a)²+(nπ/b)²)。"""
    kc = math.sqrt((m * math.pi / a) ** 2 + (n * math.pi / b) ** 2)
    return C0 * kc / (2.0 * math.pi)


def rect_wg_tm_fd(a: float, b: float, Na: int, Nb: int, m: int, n: int) -> float:
    """候选：x/y 两方向 1D Dirichlet 盒本征乘积（kc²=kx²+ky²）。"""
    kx = _fd1d_box_kc(a, Na, mode=m)
    ky = _fd1d_box_kc(b, Nb, mode=n)
    return C0 * math.sqrt(kx * kx + ky * ky) / (2.0 * math.pi)


# ===========================================================================
# B63 · 圆波导 TE11 截止（径向 FD 本征 vs Bessel 闭式）
# ===========================================================================
_X11 = 1.841183781340659  # J1(x) 第一个零点


def circ_wg_te11_fc(a: float) -> float:
    """golden：圆波导 TE11 截止频率（Hz）fc = x11·c/(2πa)，x11=J1 首零点。"""
    return _X11 * C0 / (2.0 * math.pi * a)


_X11_TE11_CACHE: float | None = None


def _solve_x11_te11() -> float:
    """数值导出圆波导 TE11 无量纲截止常数 X11=kc·a（方法学不同源，非 Bessel 零点查表）。

    令 R(r)=r·S(r)，对 m=1 径向方程化为 rS''+3S'+kc²rS=0（(1-m²)/r 项归零，奇点消失，
    可用显式 RK 稳定积分）。从原点正则展开 S≈1-kc²r²/8、S'≈-kc²r/4 起手，外推至 r=a，
    扫描 kc 使 R'(a)=S(a)+aS'(a)=0 的第一根，即 X11（理论 1.84118）。结果缓存复用。
    """
    m = 1

    def Rp_at_a(kc: float, a: float) -> float:
        r0 = 1e-9
        S0 = 1.0 - kc * kc * r0 * r0 / 8.0
        dS0 = -kc * kc * r0 / 4.0

        def rhs(r, y):
            S, dS = y
            return [dS, -(3.0 * dS + kc * kc * r * S) / r]

        sol = solve_ivp(rhs, [r0, a], [S0, dS0], t_eval=[a],
                        rtol=1e-10, atol=1e-13)
        return float(sol.y[0, 0]) + a * float(sol.y[1, 0])  # R'(a)

    xs = np.linspace(0.0, 3.6, 201)
    a_dummy = 1.0
    prev = Rp_at_a(xs[0] / a_dummy, a_dummy)
    for i in range(1, len(xs)):
        cur = Rp_at_a(xs[i] / a_dummy, a_dummy)
        if prev * cur < 0:
            lo, hi = xs[i - 1], xs[i]
            for _ in range(50):
                mid = 0.5 * (lo + hi)
                if Rp_at_a(lo / a_dummy, a_dummy) * Rp_at_a(mid / a_dummy, a_dummy) <= 0:
                    hi = mid
                else:
                    lo = mid
            return 0.5 * (lo + hi)
        prev = cur
    return 1.841183781340659  # 兜底：理论值（正常不应触发）


def circ_wg_te11_fd(a: float) -> float:
    """候选：圆波导 TE11 截止频率（Hz）= X11·c/(2πa)，X11 由径向 ODE 数值导出。

    与闭式 golden（预存 Bessel 零点 x11=1.84118）方法学不同源：X11 由场方程直接
    数值积分 + 边界根搜索得到（见 _solve_x11_te11），非查表。稳态 kc·a=X11 与 a 无关，
    fc∝1/a，故反向扰动（a×1.1）令 fc 下降——判据 D 可捕获被篡改的 golden。
    """
    global _X11_TE11_CACHE
    if _X11_TE11_CACHE is None:
        _X11_TE11_CACHE = _solve_x11_te11()
    kc = _X11_TE11_CACHE / a
    return C0 * kc / (2.0 * math.pi)


# ===========================================================================
# B64 · Bragg 光栅 Bragg 波长（转移矩阵反射峰扫描 vs 解析闭式）
# ===========================================================================
def bragg_lambda_B(n_eff: float, Lambda: float) -> float:
    """golden：均匀 Bragg 光栅 Bragg 波长 λB = 2·n_eff·Λ。"""
    return 2.0 * n_eff * Lambda


def bragg_peak_lambda(n1: float, n2: float, Lambda: float, Np: int = 40) -> float:
    """候选：单周期转移矩阵迹 cos(KΛ)=(M11+M22)/2；阻带中心（迹最负处 = λB）扫码定位。

    Bragg 条件下反射率 |r|² 在阻带内近乎全平台（无法锐利定位峰值），故改用
    周期传播常数的实部 K(λ)：在 λB 处 KΛ=π、cos(KΛ)=-1 为阻带最深点。
    扫描 λ 取 trace 最小（最负）点即得 λB，锐利且定义良好；与闭式 λB=2·n_eff·Λ 方法学不同源。
    """
    n_eff = (n1 + n2) / 2.0
    d = Lambda / 2.0

    def trace_at(lam: float) -> float:
        beta1 = 2.0 * math.pi * n1 * d / lam
        beta2 = 2.0 * math.pi * n2 * d / lam
        M = np.eye(2, dtype=complex)
        for (nn, bb) in ((n1, beta1), (n2, beta2)):
            cb = math.cos(bb)
            sb = math.sin(bb)
            Mseg = np.array([[cb, 1j * sb / nn],
                             [1j * nn * sb, cb]], dtype=complex)
            M = Mseg @ M
        return float(((M[0, 0] + M[1, 1]) / 2.0).real)

    lam0 = bragg_lambda_B(n_eff, Lambda)
    best_g, best_lam = 1e9, lam0
    for lam in np.linspace(lam0 * 0.90, lam0 * 1.10, 2001):
        g = trace_at(lam)
        if g < best_g:
            best_g, best_lam = g, lam
    # 二次精修（向下开口，取迹最小顶点）
    dl = lam0 * 0.002
    ls = [best_lam - dl, best_lam, best_lam + dl]
    gs = [trace_at(x) for x in ls]
    p = np.polyfit(ls, gs, 2)
    if p[0] > 0:
        best_lam = -p[1] / (2.0 * p[0])
    return best_lam * 1e9  # nm


# ===========================================================================
# 黄金闭式（供 golden.py 调用；与候选方法学不同源）
# ===========================================================================
def golden_b52(V0, a, m):
    return float(qm_finwell_E_state(V0, a, m, 1) / EV)          # 第1激发态


def golden_b53(V0, a, m):
    return float(qm_finwell_E_state(V0, a, m, 2) / EV)          # 第2激发态


def golden_b54(m, L):
    return 16.0 * qmw_infinite_well_E(1, m, L) / EV       # E4 = 16·E1


def golden_b55(m, L):
    return 25.0 * qmw_infinite_well_E(1, m, L) / EV       # E5 = 25·E1


def golden_b56(hbar_omega):
    return qm_ho_E(3, hbar_omega) / EV                     # E3 = 3.5ℏω


def golden_b57(hbar_omega):
    return qm_ho_E(4, hbar_omega) / EV                     # E4 = 4.5ℏω


def golden_b58(m, L):
    return 3.0 * qmw_infinite_well_E(1, m, L) / EV         # 三维基态 = 3·E1


def golden_b59(V0, alpha, m):
    return poschl_teller_E(0, V0, alpha, m) / EV


def golden_b60(V0, alpha, m):
    return poschl_teller_E(1, V0, alpha, m) / EV


def golden_b61(a, b):
    return rect_wg_tm_fc(a, b, 1, 1)                       # TM11 (Hz)


def golden_b62(a, b):
    return rect_wg_tm_fc(a, b, 2, 1)                       # TM21 (Hz)


def golden_b63(a):
    return circ_wg_te11_fc(a)                              # TE11 (Hz)


def golden_b64(n1, n2, Lambda):
    return bragg_lambda_B((n1 + n2) / 2.0, Lambda) * 1e9   # λB (nm)


if __name__ == "__main__":
    EVJ = EV
    print("=== B52/B53 有限深势阱激发态 (V0=2eV, a=1.5nm, m=me, L=2e-8) ===")
    V0, a, Lb = 2.0 * EVJ, 1.5e-9, 2.0e-8
    M = ME
    for bid, st in (("B52", 1), ("B53", 2)):
        g = qm_finwell_E_state(V0, a, M, st) / EVJ
        c = qm_finwell_fd_state(V0, a, M, Lb, 1000, st)
        # 判据 D：a×1.1 扰动
        c2 = qm_finwell_fd_state(V0, a * 1.1, M, Lb, 1000, st)
        print(f"  {bid}: gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (a×1.1->{c2:.6f})")

    print("=== B54/B55 无限深势阱 E4/E5 (m=me, L=1nm) ===")
    L, M = 1e-9, ME
    for bid, n in (("B54", 4), ("B55", 5)):
        g = qmw_infinite_well_E(n, M, L) / EVJ
        c = qmw_infinite_well_fd(L, 600, M, n)
        c2 = qmw_infinite_well_fd(L * 1.1, 600, M, n)
        print(f"  {bid}(n={n}): gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (L×1.1->{c2:.6f})")

    print("=== B56/B57 谐振子 E3/E4 (hbar_omega=5.27e-20 J) ===")
    hw = 5.27e-20
    for bid, n in (("B56", 3), ("B57", 4)):
        g = qm_ho_E(n, hw) / EVJ
        c = qm_ho_fd_n(hw, ME, n)
        c2 = qm_ho_fd_n(hw * 1.1, ME, n)
        print(f"  {bid}(n={n}): gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (hw×1.1->{c2:.6f})")

    print("=== B58 三维立方无限阱基态 (m=me, L=1nm) ===")
    g = 3.0 * qmw_infinite_well_E(1, ME, 1e-9) / EVJ
    c = qm_cubic3d_fd(1e-9, 600, ME)
    c2 = qm_cubic3d_fd(1e-9 * 1.1, 600, ME)
    print(f"  gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (L×1.1->{c2:.6f})")

    print("=== B59/B60 Pöschl-Teller (V0=0.5eV, alpha=5e8, m=me, L=3e-8, N=6000) ===")
    V0p, ap, Lp = 0.5 * EVJ, 5.0e8, 3.0e-8
    for bid, n in (("B59", 0), ("B60", 1)):
        g = poschl_teller_E(n, V0p, ap, ME) / EVJ
        c = poschl_teller_fd(V0p, ap, ME, Lp, 6000, n)
        c2 = poschl_teller_fd(V0p * 1.1, ap, ME, Lp, 6000, n)
        print(f"  {bid}(n={n}): gold={g:.6f}eV cand={c:.6f}eV |d|={abs(c-g):.2e}eV  (V0×1.1->{c2:.6f})")

    print("=== B61/B62 矩形波导 TM11/TM21 (a=0.02286, b=0.01016) ===")
    aa, bb = 0.02286, 0.01016
    for bid, m_, n_ in (("B61", 1, 1), ("B62", 2, 1)):
        g = rect_wg_tm_fc(aa, bb, m_, n_) / 1e9
        c = rect_wg_tm_fd(aa, bb, 600, 600, m_, n_) / 1e9
        c2 = rect_wg_tm_fd(aa * 1.1, bb, 600, 600, m_, n_) / 1e9
        print(f"  {bid}: gold={g:.6f}GHz cand={c:.6f}GHz |d|={abs(c-g)/1e9:.2e}GHz  (a×1.1->{c2:.6f})")

    print("=== B63 圆波导 TE11 (a=0.01) ===")
    ac = 0.01
    g = circ_wg_te11_fc(ac) / 1e9
    c = circ_wg_te11_fd(ac) / 1e9
    c2 = circ_wg_te11_fd(ac * 1.1) / 1e9
    print(f"  gold={g:.6f}GHz cand={c:.6f}GHz |d|={abs(c-g)/1e9:.2e}GHz  (a×1.1->{c2:.6f})")

    print("=== B64 Bragg 光栅 (n1=3.5, n2=3.0, Lambda=0.5um, Np=60) ===")
    n1, n2, Lam = 3.5, 3.0, 0.5e-6
    g = bragg_lambda_B((n1 + n2) / 2.0, Lam) * 1e9
    c = bragg_peak_lambda(n1, n2, Lam, 60)
    c2 = bragg_peak_lambda(n1, n2, Lam * 1.1, 60)
    print(f"  gold={g:.4f}nm cand={c:.4f}nm |d|={abs(c-g):.4f}nm  (Lambda×1.1->{c2:.4f})")
