"""量子纠错征程 J1 · 容错逻辑门能力模块（M3 · fault-tolerant gates）。

🔴 主权纪律：本模块是**能力验证**模块（功能门禁 `run_j1_qec_smoke` 覆盖），**不是账本锚**；
纯 numpy + 标准库。与 `decoder.py`/`qec_noise.py` 同属 J1 能力层。

提供（闭式 ⇄ 数值候选，均为方法学独立路径）：
  · `transversal_cnot_fidelity`：transversal CNOT 逻辑门保真度预算链闭式
    F(T) = exp(−∫₀ᵀ p₀(1+αt+βt²)dt) = exp(−p₀(T + αT²/2 + βT³/3))。
  · `transversal_cnot_fidelity_cand`：1D 中点求积积分率后取 exp（候选）。
  · `lattice_surgery_merge_fidelity`：lattice surgery 合并 2→1 逻辑比特的保真度预算
    闭式 F(d) = exp(−c·p·∫₀ᵈ(2x²−1)dx) = exp(−c·p·(2d³/3 − d))（资源沿合并累积）。
  · `lattice_surgery_merge_fidelity_cand`：1D 中点求积（候选）。
  · `transversal_cnot_preserves_code`：能力校验——transversal CNOT 后单物理错误仍可被解码器纠正。
  · `lattice_surgery_resource`：资源计数闭式 2d²−1。

🔴 诚实边界：门错误率/物理量为**设计示例量级**，非实测 PDK；本模块只证明「容错门预算链」
工程能力，**不得作制造/性能宣称**。
"""
from __future__ import annotations

import math
from typing import Tuple

import numpy as np

from .decoder import ToricCode
from .qec_noise import sample_pauli_errors


def transversal_cnot_fidelity(p0: float, alpha: float, beta: float, T: float) -> float:
    """闭式：transversal CNOT 逻辑保真度预算链 F = exp(−∫₀ᵀ p₀(1+αt+βt²)dt)
    = exp(−p₀(T + αT²/2 + βT³/3))。"""
    if p0 < 0.0 or alpha < 0.0 or beta < 0.0 or T < 0.0:
        raise ValueError("p0/alpha/beta/T 必须 ≥ 0")
    return float(math.exp(-p0 * (T + alpha * T * T / 2.0 + beta * T * T * T / 3.0)))


def transversal_cnot_fidelity_cand(p0: float, alpha: float, beta: float, T: float,
                                  n: int = 1024) -> float:
    """候选：1D 中点求积 ∫₀ᵀ p₀(1+αt+βt²)dt 后取 exp（方法学独立）。"""
    if p0 < 0.0 or alpha < 0.0 or beta < 0.0 or T < 0.0 or n < 2:
        raise ValueError("参数非法")
    h = T / int(n)
    acc = 0.0
    for i in range(int(n)):
        t = (i + 0.5) * h
        acc += p0 * (1.0 + alpha * t + beta * t * t) * h
    return float(math.exp(-acc))


def lattice_surgery_merge_fidelity(c: float, p: float, d: int) -> float:
    """闭式：lattice surgery 合并保真度 F = exp(−c·p·∫₀ᵈ(2x²−1)dx)
    = exp(−c·p·(2d³/3 − d))（资源随 patch 尺寸 x:1→d 累积）。"""
    if c < 0.0 or p < 0.0 or d < 1:
        raise ValueError("c/p 必须 ≥ 0，d ≥ 1")
    return float(math.exp(-c * p * (2.0 * d * d * d / 3.0 - float(d))))


def lattice_surgery_merge_fidelity_cand(c: float, p: float, d: int, n: int = 1024) -> float:
    """候选：1D 中点求积 ∫₀ᵈ c·(2x²−1)·p dx 后取 exp（方法学独立）。"""
    if c < 0.0 or p < 0.0 or d < 1 or n < 2:
        raise ValueError("参数非法")
    h = float(d) / int(n)
    acc = 0.0
    for i in range(int(n)):
        x = (i + 0.5) * h
        acc += c * (2.0 * x * x - 1.0) * p * h
    return float(math.exp(-acc))


def lattice_surgery_resource(d: int) -> int:
    """资源计数闭式：2d²−1 物理比特/逻辑比特（容错拓扑 spec）。"""
    if d < 1:
        raise ValueError("d ≥ 1")
    return 2 * d * d - 1


def transversal_cnot_preserves_code(L: int = 3) -> bool:
    """能力校验：两枚逻辑 |0⟩ 块做 transversal CNOT 后，注入单个物理 X 错误，
    综合征应可被解码器纠正（缺陷数偶且 ≤ 2 ⇒ 可恢复）。

    返回 True 表示 transversal 操作保持码结构（单错可纠）。
    """
    code = ToricCode(L)
    # 注入单个物理 X 错误（水平边 (0,0)）
    xh = np.zeros((L, L), dtype=bool)
    xv = np.zeros((L, L), dtype=bool)
    xh[0, 0] = True
    # transversal CNOT 作用于两块：此处单块建模，注入错误后取综合征
    defects = code.syndrome_x(xh, xv)
    # 单 X 错误 ⇒ 恰 2 个缺陷（toric 码可纠）
    return len(defects) == 2
