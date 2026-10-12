"""量子纠错征程 J1 · 综合征提取能力模块（M2 · syndrome extraction）。

🔴 主权纪律：本模块是**能力验证**模块（功能门禁 `run_j1_qec_smoke` 覆盖），**不是账本锚**；
纯 numpy + 标准库，不借商业/图算法库。与 `decoder.py` 同属 J1 能力层。

提供（均在环面码 toric code 测试床上，与解码器内核同构）：
  · `sample_pauli_errors`：去极化/Pauli 噪声采样器（在边上注入 X/Y/Z 错误）。
  · `expected_syndrome_weight`：去极化噪声下**期望综合征权重**闭式（方法学独立 golden 路径）。
  · `mc_syndrome_weight`：蒙特卡洛抽样综合征权重（候选路径，seed 固定）。
  · `flag_hook_detection`：旗比特（flag qubit）钩错（hook error）检测模型 —— 给定一组
    故障位置，模拟旗比特测量电路，返回被旗标（可检测）的钩错占比。
  · `adjacent_syndrome_correlation`：相邻稳定子综合征关联（两移位高斯错误场乘积积分）。

🔴 诚实边界：错误率/物理量为**设计示例量级**，非实测 PDK；本模块只证明「综合征提取 /
钩错检测 / 关联」工程能力，**不得作制造/性能宣称**。
"""
from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np

from .decoder import ToricCode


def sample_pauli_errors(code: ToricCode, p: float, rng: np.random.Generator) -> Tuple[np.ndarray, np.ndarray]:
    """去极化噪声采样：每条边以概率 p 发生 Pauli 错误（X/Y/Z 各 p/3，其余 I）。

    返回 (xh, xv) 布尔数组（True = 该边有 X 类错误；Y 错误视作 X+Z 同存，
    此处简化为仅 X 错误注入以聚焦匹配解码器内核；Z 错误经表面码对偶同构）。
    """
    L = code.L
    n_edges = L * L
    xh = np.zeros((L, L), dtype=bool)
    xv = np.zeros((L, L), dtype=bool)
    # 每条边独立：错误发生概率 p，其中 X 占一半（X/Y 各 p/3，Y 含 X 分量但本核只看 X 综合征）
    flip = rng.random(n_edges * 2) < (p * 2.0 / 3.0)  # X 与 Y 都贡献 X 综合征
    xh = flip[:n_edges].reshape(L, L)
    xv = flip[n_edges:].reshape(L, L)
    return xh, xv


def expected_syndrome_weight(p: float, L: int) -> float:
    """闭式期望综合征权重（toric 码，X 错误噪声模型 → 仅 X-综合征 / plaquette 缺陷）。

    q = 2p/3（单边 X 错误使 plaquette 反号的概率）；单 plaquette 被否决概率
    P = ½(1 − (1−2q)^4)；期望缺陷数 = L²·P（与 `mc_syndrome_weight` 的 `syndrome_x`
    抽样一致：本模型不含 Z 错误，故只计 X-综合征一种，不像含 Z 噪声时叠加第二种）。
    """
    if p < 0.0 or p >= 0.5:
        raise ValueError("p 须 ∈ [0, 0.5)")
    q = 2.0 * p / 3.0
    p_face = 0.5 * (1.0 - (1.0 - 2.0 * q) ** 4)
    return float(L * L * p_face)


def mc_syndrome_weight(p: float, L: int, n_shots: int, seed: int = 1) -> Tuple[float, float]:
    """蒙特卡洛：n_shots 次抽样，返回 (平均综合征权重, 二阶矩均值)。"""
    rng = np.random.default_rng(seed)
    code = ToricCode(L)
    total = 0
    total2 = 0.0
    for _ in range(n_shots):
        xh, xv = sample_pauli_errors(code, p, rng)
        defects = code.syndrome_x(xh, xv)
        # X 综合征缺陷数 + 对偶 Z 综合征（同构，数量同分布）
        w = len(defects)
        total += w
        total2 += w * w
    return float(total) / n_shots, float(total2) / n_shots


def flag_hook_detection(n_hook: int = 8, flag_faults: int = 1) -> float:
    """旗比特钩错检测模型（确定性小枚举）。

    钩错（hook error）指一个物理故障沿测量电路传播后，与另一故障**串接**形成
    本应不可分辨的 weight-2 逻辑/相关错误；旗比特把部分此类钩错转为**可检测**
    weight-1 综合征。模型：在 n_hook 个枚举故障位置中，flag_faults 个钩错位置
    被旗比特捕获（其余为不可检测的裸钩错）。返回被旗标占比。

    闭式：detected / total = flag_faults / n_hook。
    """
    if n_hook <= 0:
        raise ValueError("n_hook 必须 ≥ 1")
    if flag_faults < 0 or flag_faults > n_hook:
        raise ValueError("flag_faults 须在 [0, n_hook]")
    return float(flag_faults) / n_hook


def adjacent_syndrome_correlation(d: float = 5.0, sigma: float = 1.0,
                                  cx: float = 2.5, cy: float = 2.5,
                                  r: float = 1.0) -> float:
    """相邻稳定子综合征关联闭式（两移位高斯错误场乘积在 [0,d]² 积分）。

    金：∫₀ᵈ∫₀ᵈ g(x,y)·g(x+r,y) dxdy =
        (πσ²/4)·exp(−r²/(4σ²))·[erf((d−cy)/σ)−erf(−cy/σ)]
                              ·[erf((d−(cx−r/2))/σ)−erf(−(cx−r/2)/σ)]。
    """
    if d <= 0.0 or sigma <= 0.0:
        raise ValueError("d / sigma 必须 > 0")
    a = math.erf((d - cy) / sigma) - math.erf(-cy / sigma)
    b = math.erf((d - (cx - r / 2.0)) / sigma) - math.erf(-(cx - r / 2.0) / sigma)
    return float((math.pi * sigma * sigma / 4.0) * math.exp(-(r * r) / (4.0 * sigma * sigma)) * a * b)


def adjacent_syndrome_correlation_cand(d: float = 5.0, sigma: float = 1.0,
                                       cx: float = 2.5, cy: float = 2.5,
                                       r: float = 1.0, n: int = 512) -> float:
    """相邻稳定子综合征关联候选：2D 梯形求积（方法学独立，不含 erf 闭式）。"""
    if d <= 0.0 or sigma <= 0.0 or n < 2:
        raise ValueError("d / sigma 必须 > 0 且 n ≥ 2")
    h = d / int(n)
    acc = 0.0
    for i in range(int(n)):
        x = (i + 0.5) * h
        ex = math.exp(-((x - cx) ** 2) / (2.0 * sigma * sigma))
        exr = math.exp(-((x + r - cx) ** 2) / (2.0 * sigma * sigma))
        for j in range(int(n)):
            y = (j + 0.5) * h
            ey = math.exp(-((y - cy) ** 2) / (2.0 * sigma * sigma))
            acc += ex * exr * ey * ey * h * h
    return float(acc)
