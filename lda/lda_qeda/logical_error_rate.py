"""量子纠错征程 J1 · 端到端逻辑错误率能力模块（M4 · end-to-end logical error rate）。

🔴 主权纪律：本模块是**能力验证**模块（功能门禁 `run_j1_qec_smoke` 覆盖），**不是账本锚**；
纯 numpy + 标准库，seed 固定。与 `decoder.py`/`qec_noise.py`/`fault_tolerant_gates.py` 同属 J1 能力层。

提供（端到端流水线：噪声 → 综合征 → 解码 → 逻辑错误计数）：
  · `decode_logical`：注入错误 → 取综合征 → Union-Find 解码 → 恢复 → 返回剩余逻辑 X 宇称
    （非平凡 ⇒ 逻辑错误）。
  · `end_to_end_p_logical`：蒙特卡洛估计端到端逻辑错误率 p_L(p, d)（seed 固定）。
  · `subthreshold_suppression`：能力校验——返回 (p_L(3), p_L(7), 比值)；子阈值下应有 p_L(7) ≪ p_L(3)。
  · `logical_error_accumulated` / `logical_error_accumulated_cand`：端到端累计逻辑失效
    闭式 1−exp(−∫λ(1+βt+γt²)dt) ⇄ 1D 中点求积（供门禁顺带验证标度积分）。

🔴 诚实边界：错误率/物理量为**设计示例量级**，非实测 PDK；蒙特卡洛输出为**仿真证据**（③级，
非 golden），只用于验证标度关系（p_L(7)<p_L(3)），**不作性能宣称**。
"""
from __future__ import annotations

import math
from typing import Tuple

import numpy as np

from .decoder import ToricCode, union_find_decode
from .qec_noise import sample_pauli_errors


def decode_logical(code: ToricCode, xh: np.ndarray, xv: np.ndarray,
                   method: str = "uf") -> int:
    """注入错误 (xh,xv) → 取综合征 → 解码 → 恢复 → 剩余逻辑 X 宇称（0/1）。

    剩余错误 = 错误 XOR 恢复；逻辑错误 ⇔ 剩余错误含非平凡竖直环（逻辑 X）。
    """
    defects = code.syndrome_x(xh, xv)
    if not defects:
        # 无综合征 ⇒ 无逻辑错误
        return 0
    matching = union_find_decode(code, defects) if method == "uf" else None
    if matching is None:
        raise ValueError("method 须为 uf（MWPM 仅 d≤5，端到端用 uf）")
    rh, rv = code.recovery_from_matching(defects, matching)
    # 剩余错误 = 错误 XOR 恢复
    res_h = xh.astype(bool) ^ rh.astype(bool)
    res_v = xv.astype(bool) ^ rv.astype(bool)
    return code.logical_x(res_h, res_v)


def end_to_end_p_logical(p: float, d: int, n_shots: int = 2000,
                        seed: int = 1, method: str = "uf") -> float:
    """蒙特卡洛端到端逻辑错误率 p_L(p, d)。"""
    rng = np.random.default_rng(seed)
    code = ToricCode(d)
    n_logical = 0
    for _ in range(n_shots):
        xh, xv = sample_pauli_errors(code, p, rng)
        n_logical += decode_logical(code, xh, xv, method=method)
    return float(n_logical) / n_shots


def subthreshold_suppression(p: float = 0.005, n_shots: int = 2500,
                           seed: int = 3) -> Tuple[float, float, float]:
    """能力校验：返回 (p_L(3), p_L(7), p_L(7)/p_L(3))。子阈值下比值应 ≪ 1。"""
    p3 = end_to_end_p_logical(p, 3, n_shots=n_shots, seed=seed)
    p7 = end_to_end_p_logical(p, 7, n_shots=n_shots, seed=seed + 1)
    return float(p3), float(p7), float(p7 / p3) if p3 > 0 else float("inf")


def logical_error_accumulated(lam: float, T: float, beta: float = 0.0,
                             gamma: float = 0.0) -> float:
    """闭式：端到端累计逻辑失效 P = 1 − exp(−∫₀ᵀ λ(1+βt+γt²)dt)
    = 1 − exp(−λ(T + βT²/2 + γT³/3))。"""
    if lam < 0.0 or T < 0.0 or beta < 0.0 or gamma < 0.0:
        raise ValueError("参数须 ≥ 0")
    return float(1.0 - math.exp(-lam * (T + beta * T * T / 2.0 + gamma * T * T * T / 3.0)))


def logical_error_accumulated_cand(lam: float, T: float, beta: float = 0.0,
                                  gamma: float = 0.0, n: int = 1024) -> float:
    """候选：1D 中点求积 ∫₀ᵀ λ(1+βt+γt²)dt 后 1−exp（方法学独立）。"""
    if lam < 0.0 or T < 0.0 or beta < 0.0 or gamma < 0.0 or n < 2:
        raise ValueError("参数非法")
    h = T / int(n)
    acc = 0.0
    for i in range(int(n)):
        t = (i + 0.5) * h
        acc += lam * (1.0 + beta * t + gamma * t * t) * h
    return float(1.0 - math.exp(-acc))
