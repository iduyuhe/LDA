"""Batch B-45 数值实现 · 量子传感器芯片征程 QS-M6（超导 SQUID 磁力计 · 第二腿）。

════════════════════════════════════════════════════════════════════════════
本批**三锚**（`benchmark_defs/part7.py` 引用）——

  B485：**SQUID 环路临界电流磁通调制** I_c(Φ) 闭式 ⇄ 数值相空间扫描 互验
        golden   = 闭式 I_c(Φ) = 2·I_c0·|cos(π·Φ/Φ0)|（对称双结并联环路，
                   磁通量子化约束 δ1−δ2 = 2πf ⇒ 两结临界电流矢量叠加取模）。
        candidate = **数值相空间扫描**：对 I(δ) = I_c0·[sin δ + sin(δ+2πf)] 在
                   δ∈[0,2π) 上以 2^18 网格扫 |I| 最大 ⇒ 独立复算临界电流。
        ——方法学独立：golden 走「闭式矢量叠加」；candidate 走「逐相位扫描取极值」。
        🔴 实测 rel ≈ 5e-11（**非极值对齐** f 上的网格截断残差；N=2^18）。
        🔴 **坑**：f=0.25（及一切 2 幂对齐 f）时极值点恰落网格节点 ⇒ 残差**恒 0**
        ⇒ 是**代数恒等**，不可作独立锚；本锚固定在**非对齐** f=0.30。

  B486：**磁通-电压转导** ∂I_c/∂Φ（分流传导函数）闭式 ⇄ 数值中心差分 互验
        golden   = 闭式解析导数 ∂I_c/∂Φ = −2π·I_c0·sin(πf)·sgn(cos πf)/Φ0
                   （f 在 |cos| 光滑区间内）。
        candidate = **数值中心差分**：对闭式 I_c(Φ±ΔΦ) 做 (hi−lo)/(2ΔΦ)，取 f=0.30。
        ——方法学独立：golden 走「解析求导」；candidate 走「离散差分」。
        🔴 实测 rel ≈ 3e-11（**有限差分截断 + 舍入**双向折衷 ⇒ 残差对 ΔΦ **非单调**，
        正是真数值残差（非代数恒等）的签名）。

  B487：**磁场灵敏度谱密度** B_N 闭式 ⇄ 蒙特卡洛 Johnson 噪声传播 互验
        golden   = 闭式 B_N = √(4k_B·T/R) / |∂I_c/∂Φ| / A_eff（T/√Hz）。
        candidate = **蒙特卡洛**：生成 n_mc 个 Johnson 噪声电流样本（σ=√(4k_BT/R)），
                   经转导折算为磁通样本，取**数值方差** ⇒ S_Φ ⇒ B_N（不用解析 √）。
        ——方法学独立：golden 走「闭式 S_I 公式」；candidate 走「样本方差统计」。
        🔴🔴 **含噪余量按跨种子最坏偏差标定**（承 QS-M4 B480 血案）：
        实测 n_mc=4e6 ⇒ **跨 20 种子最坏 rel = 8.09e-4** ⇒ 取 **tol=1e-2**（余量 ≈12.4×）。

🔴 物理意义（承 QS-M6 蓝图层 §QS-M6 · 平台缺口 G8「超导量子器件物理（约瑟夫森结/磁通）」）：
  · **I_c(Φ)**：SQUID 一切功能之源——环路临界电流随磁通周期调制（周期 Φ0）。
    本锚把「磁通量子化 ⇒ 临界电流调制」钉进账本 ⇒ 误改调制律必被机器判红。
  · **∂I_c/∂Φ（转导）**：灵敏度**正比于**转导的倒数平方根 ⇒ 转导是性能核心；
    本锚把「转导律」钉进账本（决定磁通→电流读出增益）。
  · **B_N（磁灵敏度）**：三链串联终值（RCSJ → I_c(Φ)/转导 → 热噪声 → B_N）；
    本锚把「Johnson 噪声 + 转导 + 有效面积」的耦合钉进账本（缺口 G8 的落地标量）。

🔴 与既有锚的边界（**不同物理量**，非重复计数）：
  · B473–B484（NV 色心磁力计全程）：**光-自旋-磁**耦合（自旋能级 / ODMR / 集合体）；
    本批是**电-磁通**耦合（宏观量子相位 / 约瑟夫森效应）⇒ 物理对象完全不同，无交集。
  · B18/B25（transmon / 磁通调谐 qubit 的 E_J(Φ) / koch_f01）：那是**量子比特能谱**
    （f01，GHz 频率）；本批是**传感器转导**（I_c / ∂I_c/∂Φ / B_N）—— 物理量纲与用途
    均不同（能谱 vs 灵敏度）⇒ 不重复计数。
  · `sc_coupler`（D-139 可调耦合器 SQUID 的 J_qc/J_eff）：那是**耦合器可调性**（J 单位）；
    本批是**磁力计读出链**（A / A·Wb⁻¹ / T·Hz⁻¹ᐟ²）⇒ 同器件不同物理量。

🔴 **为何只三锚（诚实规模 · 吃狗粮）**：QS-M6 另含
  · 「RCSJ 锁定判据 δ_eq = asin(I_b/I_c)」（**平衡态几何/定义** ⇒ 属 smoke）；
  · 「β_c 判据滞回/非滞回」（**无量纲参数定义** ⇒ 属 smoke）；
  · 「I_c 在 f=0 取极大 / f=0.5 取零」（**对称性/边界** ⇒ 属 smoke）；
  · 「A_eff = side²」「B = Φ/A」（**纯几何定义式** ⇒ 属 smoke）；
  · 「S_Φ ∝ T」「S_Φ ∝ 1/转导²」「B_N ∝ √S_Φ」「B_N ∝ 1/A」（**标度律/单调性** ⇒ smoke）；
  · 「情景单调性（大环/低温更优）」（**单调性** ⇒ 属 smoke）。
  以上均**非独立标量物理量**（定义式 / 对称性 / 标度律 / 单调性），归
  `run_qs_m6_smoke` 覆盖，**不登记为 B 锚**（避免「非独立物理量充数」）。
  🔴 本批**如实只登记 B485–B487 三锚**（同 Batch B-44 三锚、B-42 两锚纪律：
  **宁可少，不越级谎报**）。

🔴 纪律：
· 本模块**顶层只 import numpy/math**（不触发 scipy）。
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」）；进报告数字一律**现算**。
· 🔴 **锚携带可扰动参数**（各 `B48*_DEFAULT_PARAMS`）：参数对输出单调、非零响应
  ⇒ 反自证桩护栏 `candidate_responds` 可证伪。
· 🔴 **含噪 candidate（B487）余量按「跨种子最坏偏差 < tol」标定**（承 QS-M4 B480 血案）。
"""
from __future__ import annotations

import functools
import math

import numpy as np

# 磁通量子 Φ0 = h/2e（Wb）—— 与本批 golden 同一真源量级
_H_PLANCK = 6.62607015e-34
_E_CHARGE = 1.602176634e-19
_K_B = 1.380649e-23
_FLUX_QUANTUM_WB = _H_PLANCK / (2.0 * _E_CHARGE)


# ===========================================================================
# B485 · SQUID 环路临界电流磁通调制 I_c(Φ)：闭式矢量叠加 ⇄ 数值相位扫描
# ===========================================================================
def squid_ic_modulation_golden(ic0_a: float = 2.0e-6,
                               flux_phi0: float = 0.30) -> float:
    """golden：闭式 **I_c(Φ) = 2·I_c0·|cos(π·Φ/Φ0)|**（对称双结 SQUID 环路）。

    🔴 物理：磁通量子化把两结相位差锁定为 δ1−δ2 = 2πf ⇒ 两结临界电流**矢量叠加**
    取模 ⇒ 周期为 Φ0 的 |cos| 调制。这是 SQUID 的**判据性闭式**（物理定律）。
    """
    if ic0_a <= 0.0:
        raise ValueError("ic0_a 必须 > 0")
    return float(2.0 * ic0_a * abs(math.cos(math.pi * flux_phi0)))


def squid_ic_modulation_candidate(ic0_a: float = 2.0e-6,
                                  flux_phi0: float = 0.30,
                                  n_grid: int = 1 << 18) -> float:
    """candidate：**数值相空间扫描**取最大无损电流（方法学独立 · 不用闭式）。

    I(δ) = I_c0·[sin δ + sin(δ + 2πf)]（f=Φ/Φ0）；δ 扫 [0,2π) 网格，取 |I| 最大。

    🔴 残差来源 = **相位网格截断**：极值点 δ* = π/2 − πf 一般不落网格节点 ⇒
    残差 ~ O((Δδ)²)。**非**代数恒等 ⇒ 粗网格可证伪（反向探针）。
    🔴 **必须选非对齐 f**：f=0.25（或任何使 δ*/Δδ 为整数的 f）时残差恒 0（代数恒等，
    会被 falsifiability smoke 判自证桩）⇒ 本锚固定 f=0.30（δ*/Δδ = 25.6 非整数）。
    """
    if ic0_a <= 0.0:
        raise ValueError("ic0_a 必须 > 0")
    if n_grid < 4:
        raise ValueError("n_grid 必须 ≥ 4")
    d = np.linspace(0.0, 2.0 * math.pi, n_grid, endpoint=False)
    total = ic0_a * (np.sin(d) + np.sin(d + 2.0 * math.pi * flux_phi0))
    return float(np.max(np.abs(total)))


# ===========================================================================
# B486 · 磁通-电压转导 ∂I_c/∂Φ：闭式解析导数 ⇄ 数值中心差分
# ===========================================================================
def squid_transfer_golden(ic0_a: float = 2.0e-6,
                          flux_phi0: float = 0.30) -> float:
    """golden：闭式 **∂I_c/∂Φ = −2π·I_c0·sin(πf)·sgn(cos πf) / Φ0**（A/Wb）。

    🔴 物理：转导 = 环路临界电流对磁通的斜率 ⇒ 决定磁通→电流读出增益；
    灵敏度 B_N ∝ 1/|转导|。这是由 I_c(Φ) 闭式**解析求导**得到的物理律。
    """
    if ic0_a <= 0.0:
        raise ValueError("ic0_a 必须 > 0")
    cosf = math.cos(math.pi * flux_phi0)
    sgn = 1.0 if cosf >= 0.0 else -1.0
    return float(-2.0 * math.pi * ic0_a * math.sin(math.pi * flux_phi0)
                 * sgn / _FLUX_QUANTUM_WB)


def squid_transfer_candidate(ic0_a: float = 2.0e-6,
                             flux_phi0: float = 0.30,
                             dflux: float = 1.0e-6) -> float:
    """candidate：**数值中心差分** (I_c(f+Δf) − I_c(f−Δf)) / (2ΔΦ)（A/Wb）。

    🔴 方法学独立：golden 走**解析求导**；candidate 走**离散差分**（只调用 I_c 闭式，
    不求导）。残差 = **有限差分截断**（∝ΔΦ²）与**舍入**（∝1/ΔΦ）的折衷 ⇒
    对 ΔΦ **非单调**（真数值残差签名，非代数恒等）。
    """
    if ic0_a <= 0.0:
        raise ValueError("ic0_a 必须 > 0")
    if dflux <= 0.0:
        raise ValueError("dflux 必须 > 0")

    def _ic(f: float) -> float:
        return 2.0 * ic0_a * abs(math.cos(math.pi * f))

    hi = _ic(flux_phi0 + dflux)
    lo = _ic(flux_phi0 - dflux)
    return float((hi - lo) / (2.0 * dflux * _FLUX_QUANTUM_WB))


# ===========================================================================
# B487 · 磁场灵敏度 B_N：闭式 ⇄ 蒙特卡洛 Johnson 噪声传播
# ===========================================================================
def field_sensitivity_golden(temp_k: float = 4.2, resistance_ohm: float = 20.0,
                             ic0_a: float = 2.0e-6, flux_phi0: float = 0.25,
                             loop_side_m: float = 100.0e-6) -> float:
    """golden：闭式 **B_N = √(4·k_B·T/R) / |∂I_c/∂Φ| / A_eff**（T/√Hz）。

    🔴 三链串联终值：Johnson 噪声电流 S_I=4k_BT/R ⇒ 经转导折算磁通噪声
    S_Φ=S_I/(∂I/∂Φ)² ⇒ 除以有效面积 ⇒ B_N。这是由物理律闭式**逐级代入**的结果。
    """
    if temp_k <= 0.0 or resistance_ohm <= 0.0 or ic0_a <= 0.0:
        raise ValueError("temp/resistance/ic0 必须 > 0")
    if loop_side_m <= 0.0:
        raise ValueError("loop_side_m 必须 > 0")
    t = abs(squid_transfer_golden(ic0_a, flux_phi0))
    s_i = 4.0 * _K_B * temp_k / resistance_ohm
    s_flux = s_i / (t * t)
    area = loop_side_m * loop_side_m
    return float(math.sqrt(s_flux) / area)


def field_sensitivity_candidate(temp_k: float = 4.2, resistance_ohm: float = 20.0,
                                ic0_a: float = 2.0e-6, flux_phi0: float = 0.25,
                                loop_side_m: float = 100.0e-6,
                                n_mc: int = 4_000_000,
                                seed: int = 20261019) -> float:
    """candidate：**蒙特卡洛 Johnson 噪声传播**（方法学独立 · 不用闭式 √）。

    生成 n_mc 个电流样本 ~ N(0, √(4k_BT/R))；经转导（数值差分）折算为磁通样本；
    取**数值方差** ⇒ S_Φ；再 √/A_eff ⇒ B_N（用样本统计，不用解析 S_I 公式）。固定 seed。

    🔴🔴 **含噪余量标定**（承 QS-M4 B480 血案）：n_mc=4e6 ⇒ **跨 20 种子最坏
    rel = 8.09e-4** ⇒ 本锚 tol=1e-2（余量 ≈12.4×），按**最坏**而非单次 seed 判。
    """
    if temp_k <= 0.0 or resistance_ohm <= 0.0 or ic0_a <= 0.0:
        raise ValueError("temp/resistance/ic0 必须 > 0")
    if loop_side_m <= 0.0:
        raise ValueError("loop_side_m 必须 > 0")
    if n_mc < 16:
        raise ValueError("n_mc 必须 ≥ 16")

    dflux = 1.0e-6

    def _ic(f: float) -> float:
        return 2.0 * ic0_a * abs(math.cos(math.pi * f))

    t_num = (_ic(flux_phi0 + dflux) - _ic(flux_phi0 - dflux)) / (2.0 * dflux * _FLUX_QUANTUM_WB)
    sigma_i = math.sqrt(4.0 * _K_B * temp_k / resistance_ohm)
    rng = np.random.default_rng(seed)
    samples = rng.normal(0.0, sigma_i, n_mc)
    flux_samples = samples / t_num
    s_flux_num = float(np.var(flux_samples))
    area = loop_side_m * loop_side_m
    return float(math.sqrt(s_flux_num) / area)


# ===========================================================================
# 锚的物理设计参数（default_params 真源 · 单一出处）
# ===========================================================================
# 🔴 为什么必须带**数值参数**（v0.9.216 吃狗粮抓到 · 反自证桩护栏盲区）：
#   反自证桩护栏的行为判据 `candidate_responds` 需**扰动数值参数**方可证伪。
B485_DEFAULT_PARAMS = {
    "ic0_a": 2.0e-6,        # 单结临界电流（A）；非零 ⇒ 响应
    "flux_phi0": 0.30,      # 归一磁通 f=Φ/Φ0（**非 2 幂对齐** ⇒ 真截断残差）
}

B486_DEFAULT_PARAMS = {
    "ic0_a": 2.0e-6,        # 单结临界电流（A）；非零 ⇒ 响应
    "flux_phi0": 0.30,      # 归一磁通（光滑区 · 非半整数）
}

B487_DEFAULT_PARAMS = {
    "temp_k": 4.2,          # 温度（K）；非零 ⇒ 噪声响应
    "resistance_ohm": 20.0,  # 分流电阻（Ω）；非零 ⇒ 噪声响应
    "ic0_a": 2.0e-6,        # 单结临界电流（A）⇒ 转导响应
    "loop_side_m": 100.0e-6,  # 环路边长（m）⇒ 面积响应
}


# ===========================================================================
# 记忆化入口（part7.py 顶层引用；纯函数 ⇒ 数值逐位不变）
# ===========================================================================
@functools.lru_cache(maxsize=256)
def _b485_golden_c(ic0_a: float, flux_phi0: float) -> float:
    return squid_ic_modulation_golden(ic0_a, flux_phi0)


@functools.lru_cache(maxsize=256)
def _b485_cand_c(ic0_a: float, flux_phi0: float) -> float:
    return squid_ic_modulation_candidate(ic0_a, flux_phi0)


def golden_b485(ic0_a: float = 2.0e-6, flux_phi0: float = 0.30) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b485_golden_c(ic0_a, flux_phi0)


def cand_b485(ic0_a: float = 2.0e-6, flux_phi0: float = 0.30) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b485_cand_c(ic0_a, flux_phi0)


@functools.lru_cache(maxsize=256)
def _b486_golden_c(ic0_a: float, flux_phi0: float) -> float:
    return squid_transfer_golden(ic0_a, flux_phi0)


@functools.lru_cache(maxsize=256)
def _b486_cand_c(ic0_a: float, flux_phi0: float) -> float:
    return squid_transfer_candidate(ic0_a, flux_phi0)


def golden_b486(ic0_a: float = 2.0e-6, flux_phi0: float = 0.30) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b486_golden_c(ic0_a, flux_phi0)


def cand_b486(ic0_a: float = 2.0e-6, flux_phi0: float = 0.30) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b486_cand_c(ic0_a, flux_phi0)


@functools.lru_cache(maxsize=256)
def _b487_golden_c(temp_k: float, resistance_ohm: float, ic0_a: float,
                   loop_side_m: float) -> float:
    return field_sensitivity_golden(temp_k, resistance_ohm, ic0_a,
                                    loop_side_m=loop_side_m)


@functools.lru_cache(maxsize=256)
def _b487_cand_c(temp_k: float, resistance_ohm: float, ic0_a: float,
                 loop_side_m: float) -> float:
    return field_sensitivity_candidate(temp_k, resistance_ohm, ic0_a,
                                       loop_side_m=loop_side_m)


def golden_b487(temp_k: float = 4.2, resistance_ohm: float = 20.0,
                ic0_a: float = 2.0e-6, loop_side_m: float = 100.0e-6) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b487_golden_c(temp_k, resistance_ohm, ic0_a, loop_side_m)


def cand_b487(temp_k: float = 4.2, resistance_ohm: float = 20.0,
              ic0_a: float = 2.0e-6, loop_side_m: float = 100.0e-6) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b487_cand_c(temp_k, resistance_ohm, ic0_a, loop_side_m)
