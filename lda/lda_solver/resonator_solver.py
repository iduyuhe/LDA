"""LDA L2 · 超导谐振器（λ/4）严格数值求解器（量子域物理定律锚）。

与 D-35 transmon「Koch 解析 ↔ 严格对角化」同构：谐振器侧用
「λ/4 闭式 f=1/(4l√(L′C′))（连续极限物理定律）↔ 传输线离散化严格本征值
（numpy 三对角对角化）」两条独立路径交叉验证 f0，落于确定性物理定律锚
（零外部依赖、零 GPU、LLM 不进判决路径）。

物理：一段长度 l 的传输线（分布参数 L′[H/m]、C′[F/m]），一端短路（V=0）、
一端开路（I=0）→ λ/4 谐振器。连续极限最低模 f0 = v_p/(4l)，v_p=1/√(L′C′)。
严格数值：把线离散为 N 段集总 LC，波动方程 d²V/dx² = −ω²L′C′V 二阶中心差分
→ 三对角特征问题（短路 V0=0、开路 Neumann V_{N+1}=V_N）→ eigh 解最低模
ω_num。随 N→∞ 单调收敛到闭式（探针验证：N=400 → rel=0.125%）。

纯 numpy，零外部依赖。
"""
from __future__ import annotations

import math

import numpy as np

__all__ = ["f_quarter_wave_closed_form", "solve_resonator"]


def f_quarter_wave_closed_form(Lp: float, Cp: float, l: float) -> float:
    """λ/4 谐振器最低模闭式（连续极限物理定律，Hz）。"""
    return 1.0 / (4.0 * l * math.sqrt(Lp * Cp))


def _discrete_f0(Lp: float, Cp: float, l: float, N: int) -> float:
    """离散 TL 严格本征值（Hz）：三对角差分 + 短路/开路边界 → eigh 最低模。"""
    dx = l / N
    A = np.zeros((N, N))
    for i in range(N):
        A[i, i] = -2.0
        if i > 0:
            A[i, i - 1] = 1.0
        if i < N - 1:
            A[i, i + 1] = 1.0
    # 开路端（x=l）：dV/dx=0 → V_{N+1}=V_N → 行 N-1: (V_{N-1}-V_N)/dx²
    A[N - 1, N - 2] = 1.0
    A[N - 1, N - 1] = -1.0
    lam = np.linalg.eigvalsh(A)
    idx = int(np.argmin(np.abs(lam)))
    omega2 = -lam[idx] / (Lp * Cp * dx * dx)
    return math.sqrt(omega2) / (2.0 * math.pi)


def solve_resonator(Lp: float = 0.4e-6, Cp: float = 1.5e-10,
                    l: float = 3000e-6, N: int = 200,
                    tol_rel: float = 0.01) -> dict:
    """λ/4 谐振器双验证：闭式 ↔ 离散严格本征值（N 自适应提精到 400）。

    返回 dict：f0_closed（GHz）、f0_num（GHz）、rel_err、N_used、
                converged（rel≤tol_rel）、passed、levels（前 4 模 GHz）。
    """
    f_closed = f_quarter_wave_closed_form(Lp, Cp, l)
    # N 自适应：rel 超容差则提精（网格色散收敛）
    N_used, f_num, rel = N, _discrete_f0(Lp, Cp, l, N), 1.0
    for NN in (N, N * 2, 400):
        f_num = _discrete_f0(Lp, Cp, l, NN)
        N_used = NN
        rel = abs(f_num - f_closed) / f_closed
        if rel <= tol_rel:
            break
    # 前 4 模（闭式：f_m=(2m+1)v_p/(4l)；数值最低模=λ/4）
    vp = 1.0 / math.sqrt(Lp * Cp)
    levels_closed = [(2 * m + 1) * vp / (4.0 * l) / 1e9 for m in range(4)]
    physical = bool(0.1 <= f_closed / 1e9 <= 100.0)
    accepted = bool(rel <= tol_rel)
    return {
        "f0_closed_ghz": round(f_closed / 1e9, 6),
        "f0_num_ghz": round(f_num / 1e9, 6),
        "rel_err": round(rel, 6),
        "tol_rel": tol_rel,
        "N_used": N_used,
        "converged": accepted,
        "physical_range": physical,
        "levels_closed_ghz": [round(x, 6) for x in levels_closed],
        "Lp": Lp, "Cp": Cp, "l_um": l * 1e6,
    }
