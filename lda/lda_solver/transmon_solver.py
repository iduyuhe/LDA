"""LDA L2 · transmon 哈密顿量严格对角化（量子域物理定律锚）。

与光子栈「slab 闭式解析 ↔ FDTD 严格数值」双验证完全同构：量子侧用
「Koch 解析色散近似 ↔ Josephson 电路严格数值对角化」两种**独立路径**交叉
验证 f01，落于确定性物理定律锚（零外部依赖、零 GPU、LLM 不进判决路径）。

物理：超导 transmon 在电荷 basis |n>（Cooper 对数，截断 [-N, N]）
    H = 4 E_C (n - n_g)^2 - E_J cos(phi)
    cos(phi) 在电荷基底 = 1/2 Σ_n (|n+1><n| + h.c.)
矩阵元：对角 4 E_C (n-n_g)^2；非对角相邻耦合 -E_J/2。
E_J, E_C 以频率单位（GHz，即 E/h）给出，对角化后 (E_{i+1}-E_i) 直接是 GHz。

Koch2007 近似（E_J >> E_C 极限的渐近解）：
    f01 ≈ sqrt(8 E_J E_C) - E_C   (GHz)
    alpha ≈ -E_C                  (GHz)
严格对角化给出略低/更负的 f01、alpha（高阶修正 + 截断效应），二者在
transmon 工作区（E_J/E_C ~ 30-100）相对偏差 < 1%（f01）/ ~10%（alpha）。

纯 numpy（numpy.linalg.eigh 对角化小矩阵，维度 2N+1 ≤ 41），零外部依赖。
"""
from __future__ import annotations
import numpy as np

__all__ = ["transmon_hamiltonian", "solve_transmon", "koch_f01", "koch_alpha"]


def koch_f01(E_J: float, E_C: float) -> float:
    """Koch2007 解析色散近似（GHz）。"""
    return float(np.sqrt(8.0 * E_J * E_C) - E_C)


def koch_alpha(E_C: float) -> float:
    """Koch 近似 anharmonicity（GHz，应为负）。"""
    return float(-E_C)


def transmon_hamiltonian(E_J: float, E_C: float, n_g: float = 0.0,
                         N: int = 20) -> np.ndarray:
    """构造 transmon 哈密顿量（电荷 basis 截断 [-N, N]，维度 2N+1，实对称）。"""
    dim = 2 * N + 1
    ns = np.arange(-N, N + 1, dtype=float) - n_g
    H = np.zeros((dim, dim), dtype=float)
    np.fill_diagonal(H, 4.0 * E_C * ns ** 2)
    idx = np.arange(dim - 1)
    H[idx, idx + 1] = -E_J / 2.0
    H[idx + 1, idx] = -E_J / 2.0
    return H


def solve_transmon(E_J: float, E_C: float, n_g: float = 0.0,
                   N: int = 20) -> dict:
    """严格对角化 transmon 哈密顿量，返回前 5 能级与频率量（GHz）。

    返回 dict：levels_ghz（升序前 5）、f01、f12、alpha（=f12-f01）、
                ratio_EJ_EC，及输入 E_J/E_C/N。
    """
    H = transmon_hamiltonian(E_J, E_C, n_g=n_g, N=N)
    evals = np.sort(np.linalg.eigh(H)[0])[:5]
    f01 = float(evals[1] - evals[0])
    f12 = float(evals[2] - evals[1])
    alpha = float(f12 - f01)
    return {
        "levels_ghz": [float(e) for e in evals],
        "f01": f01,
        "f12": f12,
        "alpha": alpha,
        "E_J": float(E_J),
        "E_C": float(E_C),
        "N": N,
    }
