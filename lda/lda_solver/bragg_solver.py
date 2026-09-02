"""LDA L2 · 波导 Bragg 光栅严格数值求解器（光子域物理定律锚）。

B15「Bragg 光栅中心波长」的独立候选：与 golden 的一阶相位匹配闭式
λ_B = 2·n_eff·Λ 不同源的方法学——**反周期 Bloch 本征值问题**。

物理：沿传播方向的折射率周期调制 E(z) = n_eff²·(1 + m·cos(2πz/Λ))。
在 k=π/Λ 处前进波与一阶后向波相位匹配（Bragg 条件的波动方程表述），
发生强耦合打开带隙。数值上：一个周期 Λ 内离散 N 点，反周期边界
ψ(z+Λ) = −ψ(z)（等价 ψ[−1] = −ψ[N−1]）把 Bloch 波矢锁定在 k=±π/Λ，
离散亥姆霍兹算子与 E(z) 构成**广义本征值问题** A·ψ = β²·B·ψ
（A = −d²/dz² 三点差分 + 反周期角耦合，B = diag(E)），
谱最低的一对简并态（k=±π/Λ，无调制时机器精度简并，实测劈裂
3.7e-13 ~ 2.7e-11）即第一 Bragg 带隙的上下边沿，带隙中心即 λ_B。

与 golden 的独立性：
- golden = 相位匹配条件（运动学，k 演化只计基波）
- cand   = 本征值问题（动力学，全波场 ψ 的本征谱，调制强度 m 进入算子）
二者物理同源（同一物理定律）、方法独立（闭式 vs 广义本征值对角化）⇒
|cand − golden| 反映**一阶条件的固有近似误差**，是真可证伪验证。

网格标定（v0.9.19 实测，n_eff=2.4/Λ=0.323/m=0.004，基准
golden=1.550400）：
- N=120 → diff 4.16e-5 · N=240 → 8.36e-6 · N=480 → 5.41e-8（偶然抵消
  点，避开）· N=960 → 2.02e-6（LAPACK 数值地板后反升，同 B22 现象）
  ⇒ 取 N=240（收敛段稳定点，O(1/N²) 离散色散主导）
- m 扫描：m=0.008 为扰动-近似误差偶然抵消点（2.2e-7，同 B26 现象），
  避开；取 m=0.004（弱调制典型值，Δn/n≈0.2%）
- 判据窗口（baseline < tol < min 扰动信号）：
  baseline 8.36e-6 < tol 0.01（余量 1196×）< 反向信号 1.55e-1（15.5×）✓

纯 numpy + scipy.linalg.eigvalsh（广义本征值），零 GPU、零外部重依赖，
LLM 不进判决路径。
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import eigvalsh

__all__ = ["bloch_gap_center", "lambda_B_bloch"]


def bloch_gap_center(n_eff: float, period: float, mod_depth: float = 0.004,
                     N: int = 240) -> float:
    """反周期 Bloch 广义本征值问题 → 第一带隙中心 β_c（rad/µm）。

    无调制极限解析自检：β_c → (π/Λ)/n_eff · (1 + O(π²/12N²))，
    与 ψ=exp(±iπz/Λ) 平面波的 k 演化一致（数值内部自校）。
    """
    if N < 8 or N % 2 != 0:
        raise ValueError(f"N 须为 ≥8 的偶数（带隙对索引需谱对称），得 N={N}")
    dx = period / N
    z = (np.arange(N) + 0.5) * dx          # cell-centered：每周期恰 N 采样，
    eps = (n_eff ** 2) * (1.0 + mod_depth * np.cos(2.0 * np.pi * z / period))
    d = np.full(N, 2.0 / dx ** 2)
    e = np.full(N - 1, -1.0 / dx ** 2)
    A = np.diag(d) + np.diag(e, 1) + np.diag(e, -1)
    A[0, N - 1] += 1.0 / dx ** 2           # 反周期：ψ[−1] = −ψ[N−1] ⇒ 角耦合 +1/dx²
    A[N - 1, 0] += 1.0 / dx ** 2
    B = np.diag(eps)
    w = eigvalsh(A, B)                     # 升序；w[0],w[1] = k=±π/Λ 简并对
    return float(np.sqrt(0.5 * (w[0] + w[1])))


def lambda_B_bloch(n_eff: float, period: float, mod_depth: float = 0.004,
                   N: int = 240) -> float:
    """Bragg 带隙中心波长 λ_B = 2π/β_c（µm）—— B15 独立候选入口。"""
    return 2.0 * np.pi / bloch_gap_center(n_eff, period, mod_depth, N)
