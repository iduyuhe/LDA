"""LDA L2 · 米氏散射严格级数求解器（光子域物理定律锚）。

B1「米氏散射远场散射效率 Q_scat」的独立候选：与 golden 的 Rayleigh
（偶极子）一阶极限不同源的求解路径——**完整 Mie 级数**。

物理：均匀介质球（相对折射率 m、尺寸参数 x=2πr/λ）的麦克斯韦方程
矢量球谐展开解。散射效率
    Q_scat = (2/x²) Σ_{n=1}^{nmax} (2n+1)(|a_n|² + |b_n|²)     [B&H 4.53]
Mie 系数（B&H 维度形式，Riccati-Bessel 函数 ψ_n=z·j_n(z)、χ_n=−z·y_n(z)、
ξ_n=ψ_n+i·χ_n）：
    a_n = [m·ψ_n(mx)·ψ_n'(x) − ψ_n'(mx)·ψ_n(x)] /
          [m·ψ_n(mx)·ξ_n'(x) − ψ_n'(mx)·ξ_n(x)]
    b_n = [ψ_n(mx)·ψ_n'(x) − m·ψ_n'(mx)·ψ_n(x)] /
          [ψ_n(mx)·ξ_n'(x) − m·ψ_n'(mx)·ξ_n(x)]
递推：ψ_n = (2n+1)/z·ψ_{n−1} − ψ_{n−2}（χ 同式）；导数
ψ_n' = ψ_{n−1} − n·ψ_n/z（χ 同式）。截断 nmax = x + 4x^{1/3} + 2
（Wiscombe 判据）。

与 golden 的独立性：
- golden = Rayleigh 一阶极限 Q=(8/3)·x⁴·r²，r=(m²−1)/(m²+2)
           （x≪1 时把球看作感生偶极子，只保留 a_1 首项）
- cand   = 完整级数（所有多极子 a_n/b_n 求和到 nmax）
二者物理同源（同一麦克斯韦方程）、方法独立（一阶展开 vs 全阶求和）⇒
|cand−golden| 反映 **Rayleigh 极限的固有截断误差**（x⁶ 首项），
随 x 增大单调增长（0.001%@x=0.01 → 1.39%@x=0.4）——这正是
「x≪1 时与完整 Mie 精确一致」宣称的定量边界。

自检锚（写进实现的物理不变量）：
- x→0 收敛 Rayleigh（实测 rel −0.001%@x=0.01，O(x²) 高阶项消失）
- 递推 vs scipy.special.spherical_jn/yn 交叉验证 max|Δ|≤3e-8（x=0.4）

标定（v0.9.21 实测，m=1.33/x=0.4，golden=Rayleigh=2.8413e-3）：
- baseline |diff| = 3.945e-5（rel 1.388%，tol=2e-4 未动，余量 5.1×）
- 判据窗口：baseline 3.945e-5 < tol 2e-4 < min 反向信号 1.246e-3（x×1.1，
  6.2×）✓；扰动谱 m×1.1→2.357e-3（11.9×）· x×1.1→1.246e-3（6.2×）
  ⇒ PERTURB 固定扰 m（最强键）。

纯 numpy（递推 + 复数算术），零外部依赖（**不依赖 miepython**——其存在
会使 golden 在不同环境走不同路径），零 GPU，LLM 不进判决路径。
"""
from __future__ import annotations

import numpy as np

__all__ = ["mie_q_scat", "rayleigh_q_scat"]


def rayleigh_q_scat(m: float, x: float) -> float:
    """Rayleigh（偶极子）一阶极限 Q_scat——golden 同式（供对拍）。"""
    r = (m * m - 1.0) / (m * m + 2.0)
    return (8.0 / 3.0) * x ** 4 * r * r


def _riccati_all(z: complex, nmax: int):
    """Riccati-Bessel ψ_n(z)=z·j_n、χ_n(z)=−z·y_n 向上递推（n=0..nmax+1）。"""
    psi = np.zeros(nmax + 2, dtype=complex)
    chi = np.zeros(nmax + 2, dtype=complex)
    psi[0] = np.sin(z)
    psi[1] = psi[0] / z - np.cos(z)
    chi[0] = np.cos(z)
    chi[1] = chi[0] / z + np.sin(z)
    for n in range(1, nmax + 1):
        psi[n + 1] = (2 * n + 1) / z * psi[n] - psi[n - 1]
        chi[n + 1] = (2 * n + 1) / z * chi[n] - chi[n - 1]
    return psi, chi


def mie_q_scat(m: float, x: float) -> float:
    """完整 Mie 级数 Q_scat（B&H 4.53 + 维度形式系数）——B1 独立候选入口。

    数值自检锚：x→0 收敛 rayleigh_q_scat（O(x²) 高阶项消失）。
    """
    if x <= 0:
        raise ValueError(f"x 须为正（尺寸参数），得 x={x}")
    nmax = int(x + 4 * x ** (1 / 3) + 2)          # Wiscombe 截断
    z = complex(x)
    mx = complex(m) * x
    psi, chi = _riccati_all(z, nmax)
    psim, _ = _riccati_all(mx, nmax)
    n_arr = np.arange(0, nmax + 2)
    # 导数 ψ_n' = ψ_{n−1} − n·ψ_n/z；ψ_{−1}=cos z（z·j_{−1}）、χ_{−1}=−sin z
    psip = np.empty(nmax + 2, dtype=complex)
    chip = np.empty(nmax + 2, dtype=complex)
    psimp = np.empty(nmax + 2, dtype=complex)
    psip[0] = np.cos(z)
    chip[0] = -np.sin(z)
    psimp[0] = np.cos(mx)
    psip[1:] = psi[:-1] - n_arr[1:] * psi[1:] / z
    chip[1:] = chi[:-1] - n_arr[1:] * chi[1:] / z
    psimp[1:] = psim[:-1] - n_arr[1:] * psim[1:] / mx

    q = 0.0
    for n in range(1, nmax + 1):
        xi = psi[n] + 1j * chi[n]
        xip = psip[n] + 1j * chip[n]
        a = (m * psim[n] * psip[n] - psimp[n] * psi[n]) / \
            (m * psim[n] * xip - psimp[n] * xi)
        b = (psim[n] * psip[n] - m * psimp[n] * psi[n]) / \
            (psim[n] * xip - m * psimp[n] * xi)
        q += (2 * n + 1) * (abs(a) ** 2 + abs(b) ** 2)
    return float(2.0 / x ** 2 * q)
