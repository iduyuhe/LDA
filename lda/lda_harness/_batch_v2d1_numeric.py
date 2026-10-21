# -*- coding: utf-8 -*-
"""蓝图 v2 · D1 光-量异质集成 · **M0/M3 数值核**（`_batch_v2d1_numeric`）。

锚 **B523**：多模换能阵列的**平均孔径截断效率 γ̄**。

- **golden（闭式）**：`γ_i = 0.5·[erf((a−x_i)/(√2w)) + erf((a+x_i)/(√2w))]` · `γ̄=(1/N)Σγ_i`。
  这是**精确初等闭式**（高斯在有限区间的积分 = erf 差），非截断近似。
- **candidate（数值）**：逐单元在 `[−a, a]` 上做**复合 Simpson 求积**
  `∫ exp(−(x−x_i)²/(2w²))dx`，除以**解析总积分** `w√(2π)`（已知归一化常数，非 golden 的
  erf 路径），再取平均。残差 = 限窗 Simpson 截断误差（实测趋近 **O(h⁴)**）。

锚 **B524**：异质界面的 **Kapitza 界面热导 h_K**（蓝图 v2 · D1 · M3 低温共集成热接口）。

- **golden（闭式）**：`h_K = (1/4)[α_{1→2}v₁C₁ + α_{2→1}v₂C₂]`，
  `α_{1→2}=v₁²/(v₁²+v₂²)`（DMM 细致平衡），`C=(12π⁴/5)·n·k_B·(T/θ)³`（低温 Debye **精确**极限）。
- **candidate（数值）**：**内能差商** `C ≈ [U(T(1+ε)) − U(T(1−ε))]/(2εT)`，
  其中 `U(T)=9n k_B T⁴/θ³·∫₀^{θ/T} x³/(e^x−1)dx`，谱积分用**复合 Simpson** 现算
  （**不用 π⁴、不用闭式 C**）。残差 = 中心差商截断 **O(ε²)**。

🔴 **为何 candidate 不直接在频率上做求积（实测踩过 · 重要）**：`x⁴e^x/(e^x−1)²` 与
  `x³/(e^x−1)` 都是光滑指数衰减被积函数 ⇒ **梯形/Simpson 均呈指数收敛**，实测 n=256 时
  残差已跌到 `1e-16` 相对（= 浮点地板，**等同一律**）⇒ 判据「残差 ≫ 1e-13 非恒等」不成立
  （即 B28 型「同式异写 ⇒ 虚报」病理）。故把截断**移到位移轴**：对 T 做中心差商，
  截断 O(ε²) 可控、可比、可单调（实测比值恒 **4.00**）。谱积分用 Simpson 只为把它的
  贡献压到 `≲1e-13` 相对（**如实披露**：它不是残差主项）。

🔴 **方法学独立**：golden 走 `math.pi**4` 闭式（解析求导）；candidate 走**谱积分数值求和 +
温度中心差商**（不调用 π⁴、不调用闭式 C）⇒ 残差是真数值残差，不是代数恒等。
🔴 **与 B522 避让**：B522 是单节点换能的**频域**效率；B523 是阵列的**几何孔径**因子
  （无协同度、无洛伦兹带、无频域积分）⇒ 物理量不同。
🔴 零商业依赖（纯 `math`；零 RNG）。

确定性：本模块只做纯函数计算，无时钟/随机/文件 IO。
"""

from __future__ import annotations

import math

__all__ = [
    "B523_DEFAULT_PARAMS",
    "B524_DEFAULT_PARAMS",
    "array_average_clip_golden",
    "golden_b523",
    "cand_b523",
    "kapitza_conductance_golden",
    "golden_b524",
    "cand_b524",
    "_M_BY_BID",
    "_N_CHAIN",
    "_TOL_BY_BID",
    "_EPS_BY_BID",
    "_EPS_CHAIN",
]

#: B523 默认参数（与 `lda_l2.qnet_hetero_array` 设计点一致）
B523_DEFAULT_PARAMS = {
    "n_modes": 8,
    "spacing_m": 2.0e-6,
    "waist_m": 1.5e-6,
    "aperture_half_m": 6.0e-6,
}

#: B524 默认参数（与 `lda_l2.hetero_thermal.DEBYE_DEFAULTS` 设计点一致）
B524_DEFAULT_PARAMS = {
    "T_K": 4.0,
    "theta1_K": 428.0, "v1_m_s": 5100.0, "n1_m3": 6.02e28,
    "theta2_K": 645.0, "v2_m_s": 6400.0, "n2_m3": 5.00e28,
}

#: 默认候选段数（偶数 · 收敛链见 `_N_CHAIN`）
_M_BY_BID = {"B523": 512}
#: 收敛链（残差随 n 单调降、比趋近 16）
_N_CHAIN = {"B523": [16, 32, 64, 128, 256]}
#: 默认 tol（绝对口径 · |γ̄| ~ O(1)；B524 单位 W/(m²·K)，|h| ~ 1.16e5 ⇒ 0.05 = 4.3e-7 相对）
_TOL_BY_BID = {"B523": 1e-7, "B524": 0.05}

#: B524 默认相对位移步长（中心差商 · 截断 O(ε²)）与收敛链
_EPS_BY_BID = {"B524": 1.0e-5}
_EPS_CHAIN = {"B524": [1.0e-2, 5.0e-3, 2.5e-3, 1.25e-3]}

#: 谱积分数值档（复合 Simpson 段数；只用于把谱积分压到机器精度）
_N_SPEC = 4096

_KB = 1.380649e-23
_PI4 = math.pi ** 4

_SQRT2 = math.sqrt(2.0)


def _offsets(n_modes: int, spacing_m: float):
    n = int(n_modes)
    d = float(spacing_m)
    if n < 1:
        raise ValueError("n_modes 须 ≥ 1")
    if not d > 0.0:
        raise ValueError("spacing_m 须 > 0")
    return [(i - (n - 1) / 2.0) * d for i in range(n)]


def array_average_clip_golden(n_modes: int = B523_DEFAULT_PARAMS["n_modes"],
                              spacing_m: float = B523_DEFAULT_PARAMS["spacing_m"],
                              waist_m: float = B523_DEFAULT_PARAMS["waist_m"],
                              aperture_half_m: float = B523_DEFAULT_PARAMS["aperture_half_m"]) -> float:
    """闭式 golden：`γ̄ = (1/N)Σ 0.5[erf((a−x_i)/(√2w)) + erf((a+x_i)/(√2w))]`。"""
    w = float(waist_m)
    a = float(aperture_half_m)
    if not w > 0.0:
        raise ValueError("waist_m 须 > 0")
    if not a > 0.0:
        raise ValueError("aperture_half_m 须 > 0")
    s2 = _SQRT2 * w
    xs = _offsets(n_modes, spacing_m)
    total = 0.0
    for x in xs:
        total += 0.5 * (math.erf((a - x) / s2) + math.erf((a + x) / s2))
    return float(total / len(xs))


#: 别名（golden.py 派发用）
golden_b523 = array_average_clip_golden


def _simpson(f, lo: float, hi: float, n: int) -> float:
    """复合 Simpson（n 段偶数）。"""
    n = int(n)
    if n % 2:
        n += 1
    if n < 2:
        return 0.5 * (hi - lo) * (f(lo) + f(hi))
    h = (hi - lo) / n
    s = f(lo) + f(hi)
    for k in range(1, n):
        s += (4.0 if (k % 2) else 2.0) * f(lo + k * h)
    return s * h / 3.0


def cand_b523(n_modes: int = B523_DEFAULT_PARAMS["n_modes"],
              spacing_m: float = B523_DEFAULT_PARAMS["spacing_m"],
              waist_m: float = B523_DEFAULT_PARAMS["waist_m"],
              aperture_half_m: float = B523_DEFAULT_PARAMS["aperture_half_m"],
              n: int = _M_BY_BID["B523"]) -> float:
    """数值 candidate：逐单元限窗复合 Simpson ÷ 解析总积分 `w√(2π)`，再平均。"""
    w = float(waist_m)
    a = float(aperture_half_m)
    if not w > 0.0:
        raise ValueError("waist_m 须 > 0")
    if not a > 0.0:
        raise ValueError("aperture_half_m 须 > 0")
    full = w * math.sqrt(2.0 * math.pi)
    xs = _offsets(n_modes, spacing_m)
    total = 0.0
    for x in xs:
        def g(t, _x=x):
            return math.exp(-((t - _x) ** 2) / (2.0 * w * w))
        total += _simpson(g, -a, a, n) / full
    return float(total / len(xs))


# ─────────────────────────────────────────────────────────────────────────────
# B524 · Kapitza 界面热导（蓝图 v2 · D1 · M3 低温共集成热接口）
# ─────────────────────────────────────────────────────────────────────────────

def _dmm_alpha(v1: float, v2: float) -> float:
    """DMM 透射概率 `α_{1→2}=v₁²/(v₁²+v₂²)`（细致平衡 + 声子通量 `Φ ∝ 1/v²`）。"""
    v1 = float(v1)
    v2 = float(v2)
    if not v1 > 0.0:
        raise ValueError("v1_m_s 须 > 0")
    if not v2 > 0.0:
        raise ValueError("v2_m_s 须 > 0")
    return v1 * v1 / (v1 * v1 + v2 * v2)


def kapitza_conductance_golden(T_K: float = B524_DEFAULT_PARAMS["T_K"],
                               theta1_K: float = B524_DEFAULT_PARAMS["theta1_K"],
                               v1_m_s: float = B524_DEFAULT_PARAMS["v1_m_s"],
                               n1_m3: float = B524_DEFAULT_PARAMS["n1_m3"],
                               theta2_K: float = B524_DEFAULT_PARAMS["theta2_K"],
                               v2_m_s: float = B524_DEFAULT_PARAMS["v2_m_s"],
                               n2_m3: float = B524_DEFAULT_PARAMS["n2_m3"]) -> float:
    """闭式 golden：`h_K=(1/4)[α_{1→2}v₁C₁+α_{2→1}v₂C₂]`，`C=(12π⁴/5)n k_B(T/θ)³`。"""
    T = float(T_K)
    th1 = float(theta1_K)
    th2 = float(theta2_K)
    v1 = float(v1_m_s)
    v2 = float(v2_m_s)
    n1 = float(n1_m3)
    n2 = float(n2_m3)
    if not T > 0.0:
        raise ValueError("T_K 须 > 0")
    if not th1 > 0.0 or not th2 > 0.0:
        raise ValueError("theta 须 > 0")
    if not n1 > 0.0 or not n2 > 0.0:
        raise ValueError("n 须 > 0")
    a12 = _dmm_alpha(v1, v2)
    a21 = 1.0 - a12
    C1 = (12.0 * _PI4 / 5.0) * n1 * _KB * (T / th1) ** 3
    C2 = (12.0 * _PI4 / 5.0) * n2 * _KB * (T / th2) ** 3
    return 0.25 * (a12 * v1 * C1 + a21 * v2 * C2)


#: 别名（golden.py 派发用）
golden_b524 = kapitza_conductance_golden


def _debye_spectrum_int(x_max: float, n: int = _N_SPEC) -> float:
    """`∫₀^{x_max} x³/(e^x−1) dx` —— 复合 Simpson（**不使用 π⁴**）。"""
    x_max = float(x_max)
    if not x_max > 0.0:
        raise ValueError("x_max 须 > 0")

    def g(x):
        if x <= 0.0:
            return 0.0
        return x ** 3 / (math.exp(x) - 1.0)

    return _simpson(g, 0.0, x_max, n)


def _debye_energy_density(T_K: float, theta_K: float, n_atom: float,
                          n_spec: int = _N_SPEC) -> float:
    """声子能密度 `U = 9·n·k_B·T⁴/θ³·∫₀^{θ/T}x³/(e^x−1)dx`（J/m³ · 谱积分现算）。"""
    T = float(T_K)
    th = float(theta_K)
    n = float(n_atom)
    if not T > 0.0 or not th > 0.0 or not n > 0.0:
        raise ValueError("T/theta/n 须 > 0")
    return 9.0 * n * _KB * (T ** 4) / (th ** 3) * _debye_spectrum_int(th / T, n_spec)


def cand_b524(T_K: float = B524_DEFAULT_PARAMS["T_K"],
              theta1_K: float = B524_DEFAULT_PARAMS["theta1_K"],
              v1_m_s: float = B524_DEFAULT_PARAMS["v1_m_s"],
              n1_m3: float = B524_DEFAULT_PARAMS["n1_m3"],
              theta2_K: float = B524_DEFAULT_PARAMS["theta2_K"],
              v2_m_s: float = B524_DEFAULT_PARAMS["v2_m_s"],
              n2_m3: float = B524_DEFAULT_PARAMS["n2_m3"],
              eps: float = _EPS_BY_BID["B524"],
              n_spec: int = _N_SPEC) -> float:
    """数值 candidate：**内能温度中心差商** + **谱积分数值求和**（不用 π⁴ / 不用闭式 C）。

    `C ≈ [U(T(1+ε)) − U(T(1−ε))]/(2εT)` ⇒ 残差 = 中心差商截断 **O(ε²)**。
    """
    T = float(T_K)
    eps = float(eps)
    if not T > 0.0:
        raise ValueError("T_K 须 > 0")
    if not (0.0 < eps < 0.5):
        raise ValueError("eps 须落在 (0, 0.5)")
    th1 = float(theta1_K)
    th2 = float(theta2_K)
    v1 = float(v1_m_s)
    v2 = float(v2_m_s)
    if not th1 > 0.0 or not th2 > 0.0:
        raise ValueError("theta 须 > 0")
    if not float(n1_m3) > 0.0 or not float(n2_m3) > 0.0:
        raise ValueError("n 须 > 0")

    t_up = T * (1.0 + eps)
    t_dn = T * (1.0 - eps)
    denom = 2.0 * eps * T
    C1 = (_debye_energy_density(t_up, th1, n1_m3, n_spec)
          - _debye_energy_density(t_dn, th1, n1_m3, n_spec)) / denom
    C2 = (_debye_energy_density(t_up, th2, n2_m3, n_spec)
          - _debye_energy_density(t_dn, th2, n2_m3, n_spec)) / denom

    a12 = _dmm_alpha(v1, v2)
    a21 = 1.0 - a12
    return 0.25 * (a12 * v1 * C1 + a21 * v2 * C2)
