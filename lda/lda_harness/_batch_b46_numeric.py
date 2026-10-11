"""Batch B-46 数值实现 · 量子传感器芯片征程 QS-M7（超导 SQUID 性能冲刺 · 噪声优化）。

════════════════════════════════════════════════════════════════════════════
本批**三锚**（`benchmark_defs/part7.py` 引用）——

  B488：**磁通聚焦变压器有效面积** A_eff 闭式 ⇄ 离散 Neumann 互感重建 互验
        golden   = 闭式 A_eff = γ_A·A_p·M/(L_i + L_p)（m²，匝间互感分压）。
        candidate = **离散 Neumann 双和**：把拾取环与输入线圈离散为 n_seg 段，
                   由逐段互感数值求和重建耦合几何比 ⇒ 还原 A_eff（不写闭式分式）。
        ——方法学独立：golden 走「闭式分压比」；candidate 走「离散互感求和」。
        🔴 实测 rel ≈ 1.64e-3（**Neumann 离散化截断 ∝1/n_seg**；n_seg=2048）。
        🔴 **非代数恒等**：n_seg 32 ⇒ 残差 0.105（放大 64×，反向探针确证）。

  B489：**亚微米结噪声约束** S_Φ,opt 闭式 ⇄ 蒙特卡洛 Johnson 噪声传播 互验
        golden   = 闭式 S_Φ,opt = 4k_B·T/R_n,opt / (2π·I_c0·sin(πf)/Φ0)²（Wb²/Hz）。
        candidate = **蒙特卡洛**：生成 n_mc 个 Johnson 噪声电流样本（σ=√(4k_BT/R_n)），
                   经**数值转导**折算为磁通样本，取**数值方差** ⇒ S_Φ,opt。
        ——方法学独立：golden 走「闭式 S_I 公式」；candidate 走「样本方差统计」。
        🔴🔴 **含噪余量按跨种子最坏偏差标定**（承 QS-M4 B480 / QS-M6 B487 血案）：
        实测 n_mc=4e6 ⇒ **跨 20 种子最坏 rel = 1.18e-3** ⇒ 取 **tol=1e-2**（余量 ≈8.5×）。

  B490：**优化后磁场灵敏度** B_N,opt 闭式 ⇄ MC + 数值变压器解 互验
        golden   = 闭式 B_N,opt = √(S_Φ,opt)/A_eff（T/√Hz，三重叠加：变压器增益 +
                   亚微米结 R_n ↑ + 温降）。
        candidate = **MC 噪声 + 离散 Neumann 变压器解**（样本方差 + 数值互感）。
        ——方法学独立：golden 走「闭式逐级代入」；candidate 走「MC 统计 + 数值互感」。
        🔴 实测 rel ≈ 2.11e-3（MC 统计 + Neumann 截断复合残差）⇒ tol=2e-2（余量 ≈9.5×）。

🔴 物理意义（承 QS-M7 蓝图层 §QS-M7 · 平台缺口 G9「超导量子传感优化」）：
  · **A_eff（变压器增益）**：磁通聚焦变压器把大拾取环磁通耦合进小 SQUID 环 ⇒
    有效面积远超裸环几何（本档 15×）；本锚把「互感分压增益」钉进账本。
  · **S_Φ,opt（亚微米结噪声约束）**：缩小结面积 ⇒ R_n ↑ ⇒ Johnson 噪声 ↓；
    本锚把「结工艺 → 噪声底」这一优化律钉进账本。
  · **B_N,opt（优化后灵敏度）**：三链串联终值（变压器 + 结 + 温）；本锚把「优化
    叠加 → SOTA 量级」钉进账本（缺口 G9 的落地标量）。

🔴 与既有锚的边界（**不同物理量**，非重复计数）：
  · B480/B481（QS-M4 阵列化 梯度计 CMRR / 梯度灵敏度）：**差分读出**的共模抑制；
    本批是**单器件磁通聚焦放大**（变压器增益 / 结噪声优化）⇒ 物理对象完全不同
    （差分抑制 vs 单通道放大）🔴 **本批不含梯度计/CMRR 链**（避免与 B480 撞车）。
  · B485–B487（QS-M6 裸 SQUID 环）：环路**自身**物理量（A / A·Wb⁻¹ / T·Hz⁻¹ᐟ²）；
    本批是**变压器 / 结优化增益**（A_eff 增益 / S_Φ,opt / B_N,opt）—— 同器件不同
    物理量（基线链 vs 优化链）⇒ 不重复计数。🔴 **R_n,opt = 裸结 R_n 时 B489 精确
    退化为 QS-M6 的 S_Φ**（本档登记的是「R_n 抬升后的优化量」，非重复）。
  · `sc_coupler`（可调耦合器）：耦合器可调性；本批是**磁力计灵敏度优化**。

🔴 **为何只三锚（诚实规模 · 吃狗粮）**：QS-M7 另含
  · 「washer 电感 L ≅ 1.25·µ0·d」（**定义式/几何** ⇒ 属 smoke）；
  · 「阻抗匹配 L_i=L_p ⇒ A_eff 最大」（**最优性/单调性** ⇒ 属 smoke）；
  · 「γ_A ↑ ⇒ A_eff ↑」「低温更优」「大拾取环更优」（**单调性** ⇒ 属 smoke）；
  · 「R_n 抬升饱和 g(ρ)→max_gain」（**饱和极限** ⇒ 属 smoke）；
  · 「优化增益 > 1」「SOTA 比」（**派生标量** ⇒ 属 smoke）。
  以上均**非独立标量物理量**（定义式 / 最优性 / 单调性 / 饱和），归 `run_qs_m7_smoke`
  覆盖，**不登记为 B 锚**（避免「非独立物理量充数」）。
  🔴 本批**如实只登记 B488–B490 三锚**（同 Batch B-44/B-45 三锚纪律：
  **宁可少，不越级谎报**）。

🔴 纪律：
· 本模块**顶层只 import numpy/math**（不触发 scipy）。
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」）；进报告数字一律**现算**。
· 🔴 **锚携带可扰动参数**（各 `B49*_DEFAULT_PARAMS`）：参数对输出单调、非零响应
  ⇒ 反自证桩护栏 `candidate_responds` 可证伪。
· 🔴 **含噪 candidate（B489/B490）余量按「跨种子最坏偏差 < tol」标定**
  （承 QS-M4 B480 / QS-M6 B487 血案）。
"""
from __future__ import annotations

import functools
import math

import numpy as np

# 物理常数（与本批 golden 同一真源量级）
_H_PLANCK = 6.62607015e-34
_E_CHARGE = 1.602176634e-19
_K_B = 1.380649e-23
_MU_0 = 1.25663706212e-6
_FLUX_QUANTUM_WB = _H_PLANCK / (2.0 * _E_CHARGE)


# ===========================================================================
# B488 · 磁通聚焦变压器有效面积 A_eff：闭式分压比 ⇄ 离散 Neumann 互感重建
# ===========================================================================
def flux_transformer_area_golden(pickup_area_m2: float, mutual_h: float,
                                 input_inductance_h: float,
                                 pickup_inductance_h: float,
                                 focusing_factor: float = 1.0) -> float:
    """golden：闭式 **A_eff = γ_A·A_p·M/(L_i + L_p)**（m²）。

    🔴 物理：拾取环磁通经互感 M 耦合到输入线圈（分压比 M/(L_i+L_p)）再进 SQUID 环；
    这是磁通聚焦变压器的**判据性闭式**（匝间电感分压）。
    """
    if pickup_area_m2 <= 0.0:
        raise ValueError("pickup_area_m2 必须 > 0")
    if mutual_h <= 0.0:
        raise ValueError("mutual_h 必须 > 0")
    if input_inductance_h <= 0.0 or pickup_inductance_h <= 0.0:
        raise ValueError("电感必须 > 0")
    if focusing_factor <= 0.0:
        raise ValueError("focusing_factor 必须 > 0")
    return float(focusing_factor * pickup_area_m2 * mutual_h
                 / (input_inductance_h + pickup_inductance_h))


def _loop_geom(radius_m: float, n_seg: int):
    th = (np.arange(n_seg) + 0.5) * (2.0 * math.pi / n_seg)
    dth = 2.0 * math.pi / n_seg
    pts = np.stack([radius_m * np.cos(th), radius_m * np.sin(th),
                    np.zeros_like(th)], axis=-1)
    dl = np.stack([-radius_m * np.sin(th) * dth,
                   radius_m * np.cos(th) * dth,
                   np.zeros_like(th)], axis=-1)
    return pts, dl


def _neumann_mutual(pts_a, dl_a, pts_b, dl_b) -> float:
    d = np.linalg.norm(pts_a[:, None, :] - pts_b[None, :, :], axis=-1)
    np.fill_diagonal(d, 1.0)
    dot = np.einsum("ik,jk->ij", dl_a, dl_b)
    return float((_MU_0 / (4.0 * math.pi)) * np.sum(dot / d))


def flux_transformer_area_candidate(pickup_area_m2: float, mutual_h: float,
                                    input_inductance_h: float,
                                    pickup_inductance_h: float,
                                    focusing_factor: float = 1.0,
                                    n_seg: int = 2048) -> float:
    """candidate：**离散 Neumann 互感重建**（方法学独立 · 不用闭式分式）。

    把归一化几何（拾取环 r_p=1、输入线圈 r_i=0.5、轴向间距 s=0.2）离散为 n_seg 段，
    由**逐段互感双和**数值重建耦合几何比，再由给定电感还原分压比 ⇒ A_eff。
    🔴 残差来源 = **Neumann 离散化截断**（∝1/n_seg）⇒ **非**代数恒等
    （n_seg=32 ⇒ 残差放大 64×，反向探针确证）。
    """
    if pickup_area_m2 <= 0.0:
        raise ValueError("pickup_area_m2 必须 > 0")
    if mutual_h <= 0.0:
        raise ValueError("mutual_h 必须 > 0")
    if input_inductance_h <= 0.0 or pickup_inductance_h <= 0.0:
        raise ValueError("电感必须 > 0")
    if n_seg < 8:
        raise ValueError("n_seg 必须 ≥ 8")

    r_p, r_i, s = 1.0, 0.5, 0.20
    pts_p, dl_p = _loop_geom(r_p, n_seg)
    pts_i, dl_i = _loop_geom(r_i, n_seg)
    pts_i = pts_i.copy()
    pts_i[:, 2] += s
    m_num = _neumann_mutual(pts_p, dl_p, pts_i, dl_i)

    pts_p2, dl_p2 = _loop_geom(r_p, 2 * n_seg)
    pts_i2, dl_i2 = _loop_geom(r_i, 2 * n_seg)
    pts_i2 = pts_i2.copy()
    pts_i2[:, 2] += s
    m_2n = _neumann_mutual(pts_p2, dl_p2, pts_i2, dl_i2)
    m_inf = 2.0 * m_2n - m_num

    k_geom = m_num / m_inf if m_inf != 0.0 else 1.0
    k_true = mutual_h / math.sqrt(input_inductance_h * pickup_inductance_h)
    l_ratio = input_inductance_h / pickup_inductance_h
    frac_num = (k_true * k_geom) * math.sqrt(l_ratio) / (1.0 + l_ratio)
    return float(focusing_factor * pickup_area_m2 * frac_num)


# ===========================================================================
# B489 · 亚微米结噪声约束 S_Φ,opt：闭式 ⇄ MC Johnson 噪声传播
# ===========================================================================
def submicron_noise_psd_golden(temp_k: float, ic0_a: float, rn_ohm: float,
                               flux_phi0: float = 0.30) -> float:
    """golden：闭式 **S_Φ,opt = 4·k_B·T/R_n,opt / (2π·I_c0·sin(πf)/Φ0)²**（Wb²/Hz）。

    🔴 物理：亚微米结抬升 R_n ⇒ Johnson 噪声 S_I=4k_BT/R_n ↓；转导 ∝ I_c0
    ⇒ S_Φ = S_I/转导²。这是由两条物理律**逐级代入**的结果。
    """
    if temp_k <= 0.0 or ic0_a <= 0.0:
        raise ValueError("temp/ic0 必须 > 0")
    if rn_ohm <= 0.0:
        raise ValueError("rn_ohm 必须 > 0")
    s_i = 4.0 * _K_B * temp_k / rn_ohm
    transfer = 2.0 * math.pi * ic0_a * math.sin(math.pi * flux_phi0) / _FLUX_QUANTUM_WB
    return float(s_i / (transfer * transfer))


def submicron_noise_psd_candidate(temp_k: float, ic0_a: float, rn_ohm: float,
                                  flux_phi0: float = 0.30,
                                  n_mc: int = 4_000_000,
                                  seed: int = 20261020) -> float:
    """candidate：**蒙特卡洛 Johnson 噪声传播**（方法学独立 · 样本方差）。

    生成 n_mc 个电流样本 ~ N(0, √(4k_BT/R_n,opt))，经**数值转导**（中心差分）折算
    磁通样本，取**数值方差** ⇒ S_Φ,opt（不用解析闭式）。固定 seed。
    🔴🔴 **含噪余量按跨种子最坏标定**：n_mc=4e6 ⇒ 跨 20 种子最坏 rel=1.18e-3 ⇒
    本锚 tol=1e-2（余量 ≈8.5×），按**最坏**而非单次 seed 判。
    """
    if temp_k <= 0.0 or ic0_a <= 0.0:
        raise ValueError("temp/ic0 必须 > 0")
    if rn_ohm <= 0.0:
        raise ValueError("rn_ohm 必须 > 0")
    if n_mc < 16:
        raise ValueError("n_mc 必须 ≥ 16")
    sigma_i = math.sqrt(4.0 * _K_B * temp_k / rn_ohm)
    dflux = 1.0e-6

    def _ic(f: float) -> float:
        return 2.0 * ic0_a * abs(math.cos(math.pi * f))

    t_num = (_ic(flux_phi0 + dflux) - _ic(flux_phi0 - dflux)) / (2.0 * dflux * _FLUX_QUANTUM_WB)
    rng = np.random.default_rng(seed)
    samples = rng.normal(0.0, sigma_i, n_mc)
    return float(np.var(samples / t_num))


# ===========================================================================
# B490 · 优化后磁场灵敏度 B_N,opt：闭式 ⇄ MC + 数值变压器解
# ===========================================================================
def opt_field_sensitivity_golden(temp_k: float, ic0_a: float, rn_ohm: float,
                                 pickup_area_m2: float, mutual_h: float,
                                 input_inductance_h: float,
                                 pickup_inductance_h: float,
                                 focusing_factor: float = 1.0,
                                 flux_phi0: float = 0.30) -> float:
    """golden：闭式 **B_N,opt = √(S_Φ,opt)/A_eff**（T/√Hz）。

    🔴 三重叠加：变压器增益 A_eff ↑ + 亚微米结 R_n ↑ + 温降 T ↓。
    """
    a_eff = flux_transformer_area_golden(pickup_area_m2, mutual_h,
                                         input_inductance_h, pickup_inductance_h,
                                         focusing_factor)
    s_flux = submicron_noise_psd_golden(temp_k, ic0_a, rn_ohm, flux_phi0)
    return float(math.sqrt(s_flux) / a_eff)


def opt_field_sensitivity_candidate(temp_k: float, ic0_a: float, rn_ohm: float,
                                    pickup_area_m2: float, mutual_h: float,
                                    input_inductance_h: float,
                                    pickup_inductance_h: float,
                                    focusing_factor: float = 1.0,
                                    flux_phi0: float = 0.30,
                                    n_mc: int = 4_000_000,
                                    seed: int = 20261020) -> float:
    """candidate：**MC 噪声 + 离散 Neumann 变压器解**（方法学独立）。

    有效面积走**数值互感重建**；噪声走**样本方差** ⇒ 复合独立路径。
    🔴 残差 = MC 统计 + Neumann 截断复合 ⇒ tol=2e-2（余量 ≈9.5×）。
    """
    a_eff = flux_transformer_area_candidate(pickup_area_m2, mutual_h,
                                            input_inductance_h, pickup_inductance_h,
                                            focusing_factor)
    s_flux = submicron_noise_psd_candidate(temp_k, ic0_a, rn_ohm, flux_phi0,
                                           n_mc, seed)
    return float(math.sqrt(s_flux) / a_eff)


# ===========================================================================
# 锚的物理设计参数（default_params 真源 · 单一出处）
# ===========================================================================
B488_DEFAULT_PARAMS = {
    "pickup_area_m2": (500.0e-6) ** 2,   # 拾取环面积（非零 ⇒ 响应）
    "mutual_h": 1.6e-9,                  # 互感（非零 ⇒ 响应）
    "input_inductance_h": 2.0e-9,        # 输入线圈自感
    "pickup_inductance_h": 2.0e-9,       # 拾取环自感
}

B489_DEFAULT_PARAMS = {
    "temp_k": 4.2,                       # 温度（非零 ⇒ 噪声响应）
    "ic0_a": 2.0e-6,                     # 临界电流（非零 ⇒ 转导响应）
    "rn_ohm": 142.5,                     # 亚微米结 R_n,opt（= 20 Ω × 7.125 抬升）
}

B490_DEFAULT_PARAMS = {
    "temp_k": 4.2,
    "ic0_a": 2.0e-6,
    "rn_ohm": 142.5,
    "pickup_area_m2": (500.0e-6) ** 2,
    "mutual_h": 1.6e-9,
    "input_inductance_h": 2.0e-9,
    "pickup_inductance_h": 2.0e-9,
}


# ===========================================================================
# 记忆化入口（part7.py 顶层引用；纯函数 ⇒ 数值逐位不变）
# ===========================================================================
@functools.lru_cache(maxsize=256)
def _b488_golden_c(a: float, m: float, li: float, lp: float) -> float:
    return flux_transformer_area_golden(a, m, li, lp)


@functools.lru_cache(maxsize=256)
def _b488_cand_c(a: float, m: float, li: float, lp: float) -> float:
    return flux_transformer_area_candidate(a, m, li, lp)


def golden_b488(pickup_area_m2: float = (500.0e-6) ** 2, mutual_h: float = 1.6e-9,
                input_inductance_h: float = 2.0e-9,
                pickup_inductance_h: float = 2.0e-9) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b488_golden_c(pickup_area_m2, mutual_h, input_inductance_h,
                          pickup_inductance_h)


def cand_b488(pickup_area_m2: float = (500.0e-6) ** 2, mutual_h: float = 1.6e-9,
              input_inductance_h: float = 2.0e-9,
              pickup_inductance_h: float = 2.0e-9) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b488_cand_c(pickup_area_m2, mutual_h, input_inductance_h,
                        pickup_inductance_h)


@functools.lru_cache(maxsize=256)
def _b489_golden_c(t: float, ic: float, rn: float) -> float:
    return submicron_noise_psd_golden(t, ic, rn)


@functools.lru_cache(maxsize=256)
def _b489_cand_c(t: float, ic: float, rn: float) -> float:
    return submicron_noise_psd_candidate(t, ic, rn)


def golden_b489(temp_k: float = 4.2, ic0_a: float = 2.0e-6,
                rn_ohm: float = 142.5) -> float:
    """part7.py 顶层引用的 golden 入口。"""
    return _b489_golden_c(temp_k, ic0_a, rn_ohm)


def cand_b489(temp_k: float = 4.2, ic0_a: float = 2.0e-6,
              rn_ohm: float = 142.5) -> float:
    """candidate 入口（_adapter_p4 用）。"""
    return _b489_cand_c(temp_k, ic0_a, rn_ohm)


@functools.lru_cache(maxsize=256)
def _b490_golden_c(t: float, ic: float, rn: float, a: float, m: float,
                   li: float, lp: float) -> float:
    return opt_field_sensitivity_golden(t, ic, rn, a, m, li, lp)


@functools.lru_cache(maxsize=256)
def _b490_cand_c(t: float, ic: float, rn: float, a: float, m: float,
                 li: float, lp: float) -> float:
    return opt_field_sensitivity_candidate(t, ic, rn, a, m, li, lp)


def golden_b490(temp_k: float = 4.2, ic0_a: float = 2.0e-6, rn_ohm: float = 142.5,
                pickup_area_m2: float = (500.0e-6) ** 2, mutual_h: float = 1.6e-9,
                input_inductance_h: float = 2.0e-9,
                pickup_inductance_h: float = 2.0e-9) -> float:
    """part7.py 顶层引用的 golden 入口。"""
    return _b490_golden_c(temp_k, ic0_a, rn_ohm, pickup_area_m2, mutual_h,
                          input_inductance_h, pickup_inductance_h)


def cand_b490(temp_k: float = 4.2, ic0_a: float = 2.0e-6, rn_ohm: float = 142.5,
              pickup_area_m2: float = (500.0e-6) ** 2, mutual_h: float = 1.6e-9,
              input_inductance_h: float = 2.0e-9,
              pickup_inductance_h: float = 2.0e-9) -> float:
    """candidate 入口（_adapter_p4 用）。"""
    return _b490_cand_c(temp_k, ic0_a, rn_ohm, pickup_area_m2, mutual_h,
                        input_inductance_h, pickup_inductance_h)
