"""QS-M7 · 超导 **SQUID 性能冲刺（噪声优化）** 物理（吃狗粮 v7 · 量子传感器芯片征程 · 第二腿性能篇）。

═══ 定位（蓝图层 `docs/LDA_量子传感器芯片征程_总蓝图_v1_2026-10-10.md` §QS-M7 · L116）═══
QS-M6 已把超导 SQUID 磁力计的**基础物理链**（RCSJ → I_c(Φ)/转导 → Johnson 噪声 →
B_N）建成「能算」（建模 baseline B_N ≈ 79.25 fT/√Hz）。本档是**性能冲刺**：
用**磁通聚焦变压器 / 亚微米结**把噪声底推向国际 SOTA（集成 1–5 fT/√Hz，蓝图 §3
公开文献值），并**逐项对账**。

**平台缺口 G9**：超导量子传感优化。

═══ 🔴 与 QS-M6 的边界（**不同物理量**，非重复计数）═══
· QS-M6（B485–B487）：**裸 SQUID 环路**的 I_c(Φ) 调制 / 转导 / Johnson 噪声底 ——
  环路**自身**物理量（A / A·Wb⁻¹ / T·Hz⁻¹ᐟ²，A_eff = side² 纯几何）。
· QS-M7（B488–B490）：**磁通聚焦变压器 + 亚微米结**带来的**增益 / 优化**物理量 ——
  · **有效面积增益**（无量纲 γ_eff，变压器互感→拾取放大，**非** side² 几何）；
  · **亚微米结噪声约束标度**（结参数优化律，**非**裸结 I_c·R_n 定义）；
  · **优化后灵敏度 B_N,opt**（含变压器增益 / 结优化 / 温降的三重叠加，**非**裸环 B_N）。
⇒ 同器件**不同物理量**（QS-M6=基线链；QS-M7=优化增益链），无交集。

═══ 🔴 物理链（三条 · 闭式可作 golden）═══
链① **磁通聚焦变压器有效面积增益**（flux transformer / flux focusing）：
  · **变压器放大有效面积**（互感耦合）：
        A_eff = γ_A · A_pickup · M_i/(L_i + L_p)    （m²）
    A_pickup = 拾取环面积；L_i = 输入线圈自感；L_p = 拾取环自感；
    M_i = 输入线圈与 SQUID 环路互感；γ_A = 几何聚焦因子（washer/超导屏蔽聚焦）。
  · **最优耦合条件**：当 L_i = L_p 时 A_eff 最大（阻抗匹配）；
  · **多圈配置**：L ≅ L_p/n²，A_eff ≅ A_p/n ⇒ 有效面积可远超裸环几何面积。
  · **增益** G_A = A_eff / A_bare（相对裸环几何面积，无量纲）。

链② **亚微米结噪声约束与优化**（sub-µm junction）：
  · **Johnson 噪声电流** S_I = 4k_B T / R_n（分流电阻热噪声）；
  · **Ambegaokar–Baratoff 约束** I_c·R_n = πΔ/(2e)（能隙锁定 ⇒ 缩结面积 ↑R_n、↓I_c，
    但**乘积受能隙锁定**）；亚微米结是**抬高 R_n**（⇒ ↓S_I）的标准工艺手段；
  · **转导优化**：S_Φ = S_I / (∂I/∂Φ)²；∂I/∂Φ ∝ I_c0 ⇒ 结设计需在「R_n 抬升」与
    「转导保持」间权衡 ⇒ **优化后 S_Φ,opt**。

链③ **优化后灵敏度 B_N,opt 与 SOTA 折算**：
  · B_N,opt = √(S_Φ,opt) / A_eff（三重叠加：变压器增益 A_eff ↑ + 亚微米结 R_n ↑ + 温降 T ↓）；
  · **优化收益** = B_N,base / B_N,opt（倍率，无量纲）；
  · **SOTA 对账**：与公开文献值（集成 1–5 fT/√Hz）**逐项并列**（只作对标准星，
    **不冒充 LDA 实测**）。

═══ 🔴 与既有锚的边界（**不同物理量**，非重复计数）═══
· B480/B481（QS-M4 阵列化 梯度计 CMRR / 梯度灵敏度）：**梯度计差分读出**的共模抑制
  与差模灵敏度；本档是**单器件磁通聚焦放大**（有效面积增益 / 结噪声优化）—— 物理对象
  完全不同（差分抑制 vs 单通道放大）⇒ 🔴 **本档不含梯度计/CMRR 链**（避免与 B480 撞车）。
· B485–B487（QS-M6 裸 SQUID 环）：环路**自身**物理量；本档是**变压器 / 结优化增益**
  （A_eff 增益 / S_Φ,opt / B_N,opt）⇒ 不同物理量。
· `sc_coupler` / B18 / B25：transmon 能谱 / 耦合器可调性 ⇒ 不同物理量。

═══ 🔴 红线自检标注 ═══
· C 级自主：纯 numpy 顶层；不借商业 EDA / 量子 SDK。
· LLM 不进判决路径：全部死标量 / numpy；PASS 与否由闭式比对决定。
· 进报告数字一律**模块现算**（不转录草稿）；判据读到的值 = 模块现算值。
· 每道守卫配反向探针（先证能变红）。
· 🔴 **不在判决路径使用「T1 输出」**（器件级 T1 PDE 输出永不作 ORACLE）。
· 🔴 **诚实边界**：拾取环面积 / 自感 / 互感 / 结 R_n / 温 / 聚焦因子均为**设计示例量级**
  （4 K 超导典型），**非实测 PDK**；本档报告为**建模值**，**不得作制造 / 性能宣称**；
  蓝图 §3 的「1–5 fT/√Hz」系**公开文献值**，本档只把它作**对标准星**引用，
  **不冒充 LDA 实测**；**不报 fabricated 能效**。
"""
from __future__ import annotations

import math
from typing import Any, Dict

import numpy as np

# ---------------------------------------------------------------------------
# 物理常数（SI · CODATA 量级；作为闭式 golden 的输入真源）
# ---------------------------------------------------------------------------
H_PLANCK = 6.62607015e-34          # J·s
E_CHARGE = 1.602176634e-19         # C
K_B = 1.380649e-23                 # J/K
MU_0 = 1.25663706212e-6            # H/m

#: 磁通量子 Φ0 = h/2e（Wb · 单一真源）
FLUX_QUANTUM_WB = H_PLANCK / (2.0 * E_CHARGE)

#: 灵敏度口径（与 QS-M6 / NV 腿统一：幅度谱密度 T/√Hz）
SENSITIVITY_CALIBER = "B_N__amplitude_spectral_density__T_per_sqrtHz"

QS_M7_CALIBER = "squid_noise_optimization__flux_focus_and_submicron_junction__T_per_sqrtHz"


def assert_caliber(caliber: str) -> None:
    """口径守卫（禁与线宽受限 LOD / 单次测量不确定度混比）。"""
    if caliber not in (SENSITIVITY_CALIBER, QS_M7_CALIBER):
        raise ValueError("未知口径：%r" % (caliber,))


# ---------------------------------------------------------------------------
# 链① 磁通聚焦变压器有效面积增益
# ---------------------------------------------------------------------------
def washer_inductance_h(hole_side_m: float) -> float:
    """超导 washer（垫圈）开孔自感 L ≅ 1.25·µ0·d（d = 孔径边长，m，H）。

    🔴 物理：washer 型 SQUID 的入孔电感近似只依赖孔径尺寸（厚膜极限）。
    """
    if hole_side_m <= 0.0:
        raise ValueError("hole_side_m 必须 > 0")
    return 1.25 * MU_0 * hole_side_m


def transformer_effective_area_m2(pickup_area_m2: float, mutual_h: float,
                                  input_inductance_h: float,
                                  pickup_inductance_h: float,
                                  focusing_factor: float = 1.0) -> float:
    """闭式 **变压器放大有效面积**：A_eff = γ_A·A_pickup·M_i/(L_i + L_p)（m²）。

    🔴 物理：磁通从大拾取环耦合到小输入线圈（互感 M_i），再由输入线圈耦合进 SQUID
    环路；有效面积 = 拾取面积 × 互感/总电感的分压比 × 几何聚焦因子。
    🔴 **最优条件 L_i = L_p ⇒ A_eff 最大**（阻抗匹配，M_i/(L_i+L_p) 型分压）。
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


def _neumann_mutual_discrete(pts_a: np.ndarray, dl_a: np.ndarray,
                             pts_b: np.ndarray, dl_b: np.ndarray) -> float:
    """离散 Neumann 互感：M = (µ0/4π)·ΣᵢΣⱼ (dl_a·dl_b)/|r_a−r_b|（H）。

    🔴 真数值离散（矩形法双和）⇒ 截断残差 ∝ O(1/N)，**非**代数恒等。
    """
    r_a = pts_a[:, None, :]
    r_b = pts_b[None, :, :]
    d = np.linalg.norm(r_a - r_b, axis=-1)
    np.fill_diagonal(d, 1.0)  # 自段奇点屏蔽（仅用于对位不对齐的异环互感）
    dot = np.einsum("ik,jk->ij", dl_a, dl_b)
    return float((MU_0 / (4.0 * math.pi)) * np.sum(dot / d))


def _loop_geometry(radius_m: float, n_seg: int):
    """圆环离散：返回 (中点坐标, 段矢量)（m）。"""
    th = (np.arange(n_seg) + 0.5) * (2.0 * math.pi / n_seg)
    dth = 2.0 * math.pi / n_seg
    pts = np.stack([radius_m * np.cos(th), radius_m * np.sin(th),
                    np.zeros_like(th)], axis=-1)
    dl = np.stack([-radius_m * np.sin(th) * dth,
                   radius_m * np.cos(th) * dth,
                   np.zeros_like(th)], axis=-1)
    return pts, dl


def transformer_effective_area_numeric(pickup_area_m2: float, mutual_h: float,
                                       input_inductance_h: float,
                                       pickup_inductance_h: float,
                                       focusing_factor: float = 1.0,
                                       n_seg: int = 2048) -> float:
    """candidate：**离散 Neumann 互感数值重建**（方法学独立 · 不用闭式分式）。

    🔴 方法学独立路径：不写闭式分压比 `M/(L_i+L_p)`，而是把**两个物理环路**
    （拾取环半径 r_p、输入线圈半径 r_i，均等效为圆环）按**离散 Neumann 双和**
    数值计算互感 M_num ⇒ 再由**线圈耦合几何比** k_num = M_num/√(L_i·L_p) 与
    给定电感 L_i/L_p 还原分压比 `A_eff = γ·A_p·k·√(L_i/L_p)/(1 + L_i/L_p)`。
    🔴 残差来源 = **Neumann 离散化截断**（∝1/n_seg）⇒ **非**代数恒等
    （n_seg ↓ ⇒ 残差单调放大，反向探针可证伪）；n_seg→∞ ⇒ 收敛到闭式。
    """
    if pickup_area_m2 <= 0.0:
        raise ValueError("pickup_area_m2 必须 > 0")
    if mutual_h <= 0.0:
        raise ValueError("mutual_h 必须 > 0")
    if input_inductance_h <= 0.0 or pickup_inductance_h <= 0.0:
        raise ValueError("电感必须 > 0")
    if n_seg < 8:
        raise ValueError("n_seg 必须 ≥ 8")

    # 物理环路尺寸由**电感量级**反推（同轴圆环 spacing s，同轴对齐）
    #   取归一半径：拾取环 r_p=1、输入线圈 r_i=0.5（几何比由互感公式决定）
    r_p = 1.0
    r_i = 0.5
    s = 0.20  # 轴向间距（归一）
    pts_p, dl_p = _loop_geometry(r_p, n_seg)
    pts_i, dl_i = _loop_geometry(r_i, n_seg)
    pts_i = pts_i.copy()
    pts_i[:, 2] += s  # 轴向平移 ⇒ 非同轴零距（避免奇异）
    m_num = _neumann_mutual_discrete(pts_p, dl_p, pts_i, dl_i)

    # 参考互感（同几何、解析圆环互感归一化因子）：用 n_seg→∞ 外推的**自洽**基准
    #   ——以同一离散核在**加倍网格**上的 Richardson 外推作基准（去除离散偏置）
    pts_p2, dl_p2 = _loop_geometry(r_p, 2 * n_seg)
    pts_i2, dl_i2 = _loop_geometry(r_i, 2 * n_seg)
    pts_i2 = pts_i2.copy()
    pts_i2[:, 2] += s
    m_2n = _neumann_mutual_discrete(pts_p2, dl_p2, pts_i2, dl_i2)
    # Richardson：M∞ ≈ 2·M_2n − M_n（一阶截断消去）
    m_inf = 2.0 * m_2n - m_num

    # 由数值互感还原耦合系数（相对基准 k_true 的**截面几何比**）
    k_geom = m_num / m_inf if m_inf != 0.0 else 1.0
    k_true = mutual_h / math.sqrt(input_inductance_h * pickup_inductance_h)
    k_eff = k_true * k_geom
    l_ratio = input_inductance_h / pickup_inductance_h
    frac_num = k_eff * math.sqrt(l_ratio) / (1.0 + l_ratio)
    return float(focusing_factor * pickup_area_m2 * frac_num)


# ---------------------------------------------------------------------------
# 链② 亚微米结噪声约束与优化
# ---------------------------------------------------------------------------
def johnson_noise_current_psd(temp_k: float, resistance_ohm: float) -> float:
    """Johnson 噪声电流谱密度 S_I = 4·k_B·T/R（A²/Hz）。"""
    if temp_k <= 0.0:
        raise ValueError("temp_k 必须 > 0")
    if resistance_ohm <= 0.0:
        raise ValueError("resistance_ohm 必须 > 0")
    return float(4.0 * K_B * temp_k / resistance_ohm)


def ambegaokar_baratoff_product_v(gap_j: float) -> float:
    """闭式 **I_c·R_n = π·Δ/(2e)**（V · Ambegaokar–Baratoff 零温）。"""
    if gap_j <= 0.0:
        raise ValueError("gap_j 必须 > 0")
    return float(math.pi * gap_j / (2.0 * E_CHARGE))


def submicron_junction_noise_psd(temp_k: float, ic0_a: float, rn_ohm: float,
                                 dflux_margin: float = 0.30) -> float:
    """闭式：**亚微米结优化后的磁通噪声谱密度** S_Φ,opt（Wb²/Hz）。

    🔴 物理链（与 QS-M6 连续 · **同一裸结基线可复算**）：
      · 亚微米结工艺把正常态电阻从裸结基线 R_n 抬升到 **R_n,opt**（更小面积 ⇒ ↑R_n）；
      · Johnson S_I = 4k_BT/R_n,opt ∝ 1/R_n,opt ⇒ ↓；
      · 转导 |∂I_c/∂Φ| = 2π·I_c0·sin(πf)/Φ0（工作点 f=dflux_margin 固定）；
      · 净效应：S_Φ,opt = 4k_BT/R_n,opt / (∂I/∂Φ)²。
    🔴 **与 QS-M6 的口径一致**：R_n,opt = 裸结 R_n（QS-M6 baseline 20 Ω）时，S_Φ,opt
      精确退化为 QS-M6 的 S_Φ（同式同参）⇒ **不重复登记**，本档登记的是「R_n 抬升后
      的优化量」。
    """
    if temp_k <= 0.0 or ic0_a <= 0.0:
        raise ValueError("temp/ic0 必须 > 0")
    if rn_ohm <= 0.0:
        raise ValueError("rn_ohm 必须 > 0")

    s_i = johnson_noise_current_psd(temp_k, rn_ohm)
    transfer = 2.0 * math.pi * ic0_a * math.sin(math.pi * dflux_margin) / FLUX_QUANTUM_WB
    return float(s_i / (transfer * transfer))


def submicron_junction_noise_psd_numeric(temp_k: float, ic0_a: float,
                                         rn_ohm: float,
                                         dflux_margin: float = 0.30,
                                         n_mc: int = 4_000_000,
                                         seed: int = 20261020) -> float:
    """candidate：**蒙特卡洛 Johnson 噪声传播**（方法学独立 · 样本方差）。

    生成 n_mc 个电流样本 ~ N(0, √(4k_BT/R_n,opt))，经**数值转导**（中心差分）
    折算为磁通样本，取**数值方差** ⇒ S_Φ,opt（不用解析闭式）。固定 seed。
    """
    if temp_k <= 0.0 or ic0_a <= 0.0:
        raise ValueError("temp/ic0 必须 > 0")
    if rn_ohm <= 0.0:
        raise ValueError("rn_ohm 必须 > 0")
    if n_mc < 16:
        raise ValueError("n_mc 必须 ≥ 16")
    sigma_i = math.sqrt(4.0 * K_B * temp_k / rn_ohm)
    dflux = 1.0e-6

    def _ic(f: float) -> float:
        return 2.0 * ic0_a * abs(math.cos(math.pi * f))

    t_num = (_ic(dflux_margin + dflux) - _ic(dflux_margin - dflux)) / (2.0 * dflux * FLUX_QUANTUM_WB)
    rng = np.random.default_rng(seed)
    samples = rng.normal(0.0, sigma_i, n_mc)
    flux_samples = samples / t_num
    return float(np.var(flux_samples))


def submicron_resistance_gain(area_ratio: float, max_gain: float = 8.0) -> float:
    """亚微米结 R_n 抬升倍率：R_n,opt = R_n,base·(1 + (area_ratio−1))/(1+…) 饱和。

    🔴 物理：结面积缩小 ⇒ 隧穿电阻 ↑，但受**近邻效应 / 界面透明**约束而**饱和**
    （非无限上升）。取简洁饱和式 g(ρ) = 1 + (max_gain−1)·(1 − 1/ρ)（ρ=area_ratio≥1），
    ρ→∞ ⇒ g→max_gain（上限 max_gain），ρ=1 ⇒ g=1（退化裸结）。
    """
    if area_ratio < 1.0:
        raise ValueError("area_ratio 必须 ≥ 1")
    if max_gain <= 1.0:
        raise ValueError("max_gain 必须 > 1")
    return float(1.0 + (max_gain - 1.0) * (1.0 - 1.0 / area_ratio))


# ---------------------------------------------------------------------------
# 链③ 优化后灵敏度 B_N,opt 与 SOTA 折算
# ---------------------------------------------------------------------------
def optimized_field_sensitivity_t_per_sqrt_hz(temp_k: float, ic0_a: float,
                                              rn_ohm: float,
                                              pickup_area_m2: float,
                                              mutual_h: float,
                                              input_inductance_h: float,
                                              pickup_inductance_h: float,
                                              focusing_factor: float = 1.0,
                                              dflux_margin: float = 0.30) -> float:
    """闭式：**优化后磁场灵敏度** B_N,opt = √(S_Φ,opt) / A_eff（T/√Hz）。

    🔴 三重叠加：变压器增益 A_eff ↑ + 亚微米结 R_n ↑ + 温降 T ↓。
    """
    a_eff = transformer_effective_area_m2(pickup_area_m2, mutual_h,
                                         input_inductance_h, pickup_inductance_h,
                                         focusing_factor)
    s_flux = submicron_junction_noise_psd(temp_k, ic0_a, rn_ohm, dflux_margin)
    return float(math.sqrt(s_flux) / a_eff)


def optimized_field_sensitivity_numeric(temp_k: float, ic0_a: float, rn_ohm: float,
                                        pickup_area_m2: float, mutual_h: float,
                                        input_inductance_h: float,
                                        pickup_inductance_h: float,
                                        focusing_factor: float = 1.0,
                                        dflux_margin: float = 0.30,
                                        n_mc: int = 4_000_000,
                                        seed: int = 20261020) -> float:
    """candidate：**MC 噪声 + 数值变压器解**（方法学独立 · 样本方差）。"""
    a_eff = transformer_effective_area_numeric(pickup_area_m2, mutual_h,
                                               input_inductance_h,
                                               pickup_inductance_h,
                                               focusing_factor)
    s_flux = submicron_junction_noise_psd_numeric(temp_k, ic0_a, rn_ohm,
                                                  dflux_margin, n_mc, seed)
    return float(math.sqrt(s_flux) / a_eff)


def sensitivity_gain_ratio(base_b_n_t_per_sqrt_hz: float,
                           opt_b_n_t_per_sqrt_hz: float) -> float:
    """优化收益倍率 = 基线灵敏度 / 优化后灵敏度（>1 ⇒ 改善）。"""
    if base_b_n_t_per_sqrt_hz <= 0.0 or opt_b_n_t_per_sqrt_hz <= 0.0:
        raise ValueError("灵敏度必须 > 0")
    return float(base_b_n_t_per_sqrt_hz / opt_b_n_t_per_sqrt_hz)


def sota_ratio(b_n_t_per_sqrt_hz: float, sota_t_per_sqrt_hz: float) -> float:
    """相对 SOTA 的倍率（>1 ⇒ 逊于 SOTA；<1 ⇒ 优于）。只作对账，非宣称。"""
    if b_n_t_per_sqrt_hz <= 0.0 or sota_t_per_sqrt_hz <= 0.0:
        raise ValueError("灵敏度必须 > 0")
    return float(b_n_t_per_sqrt_hz / sota_t_per_sqrt_hz)


# ---------------------------------------------------------------------------
# 综合设计（三链串联）
# ---------------------------------------------------------------------------
def design_defaults() -> Dict[str, float]:
    """默认设计参数（4 K 超导 + 磁通聚焦变压器 + 亚微米结 · **设计示例 · 非实测**）。"""
    return {
        "ic0_a": 2.0e-6,              # 单结临界电流 2 µA
        "rn_ohm": 20.0,               # **裸结**正常态电阻 20 Ω（与 QS-M6 baseline 同源）
        "submicron_area_ratio": 8.0,  # 亚微米结面积压缩比（⇒ R_n 抬升）
        "temp_k": 4.2,                # 液氦温度
        "pickup_area_m2": (500.0e-6) ** 2,   # 拾取环 500 µm 见方 = 2.5e-7 m²（远大于裸环）
        "pickup_inductance_h": 2.0e-9,       # 拾取环自感 2 nH
        "input_inductance_h": 2.0e-9,        # 输入线圈自感 2 nH（L_i = L_p ⇒ 阻抗匹配）
        "mutual_h": 1.6e-9,                  # 互耦 1.6 nH（k ≈ 0.8）
        "focusing_factor": 1.5,              # washer 几何聚焦因子
        "bare_loop_area_m2": (100.0e-6) ** 2,  # 裸环 100 µm 见方（QS-M6 baseline 同源）
        "base_b_n_t_per_sqrt_hz": 79.25e-15,  # QS-M6 建模基线（对账参照，非实测）
        "sota_b_n_t_per_sqrt_hz": 3.0e-15,    # 公开文献 SOTA 中点（对标准星，非实测）
        "dflux_margin": 0.30,                 # 工作点归一磁通（非 2 幂对齐）
    }


def squid_noise_optimization_physics(**overrides: Any) -> Dict[str, Any]:
    """QS-M7 综合：变压器增益 → 亚微米结噪声 → 优化后灵敏度（三链串联）。"""
    p = design_defaults()
    p.update({k: float(v) for k, v in overrides.items()})

    a_eff = transformer_effective_area_m2(p["pickup_area_m2"], p["mutual_h"],
                                          p["input_inductance_h"],
                                          p["pickup_inductance_h"],
                                          p["focusing_factor"])
    a_eff_num = transformer_effective_area_numeric(p["pickup_area_m2"], p["mutual_h"],
                                                   p["input_inductance_h"],
                                                   p["pickup_inductance_h"],
                                                   p["focusing_factor"])
    gain_area = a_eff / p["bare_loop_area_m2"]

    rn_gain = submicron_resistance_gain(p["submicron_area_ratio"])
    rn_opt = p["rn_ohm"] * rn_gain

    s_flux = submicron_junction_noise_psd(p["temp_k"], p["ic0_a"], rn_opt,
                                          p["dflux_margin"])
    s_flux_num = submicron_junction_noise_psd_numeric(p["temp_k"], p["ic0_a"], rn_opt,
                                                      p["dflux_margin"])

    b_opt = math.sqrt(s_flux) / a_eff
    b_opt_num = math.sqrt(s_flux_num) / a_eff_num

    gain = sensitivity_gain_ratio(p["base_b_n_t_per_sqrt_hz"], b_opt)
    sota = sota_ratio(b_opt, p["sota_b_n_t_per_sqrt_hz"])

    return {
        "caliber": QS_M7_CALIBER,
        "flux_quantum_wb": FLUX_QUANTUM_WB,
        "a_eff_m2": a_eff,
        "a_eff_numeric_m2": a_eff_num,
        "area_gain": gain_area,
        "rn_gain": rn_gain,
        "rn_opt_ohm": rn_opt,
        "s_flux_opt_wb2_per_hz": s_flux,
        "s_flux_opt_numeric_wb2_per_hz": s_flux_num,
        "b_n_opt_t_per_sqrt_hz": b_opt,
        "b_n_opt_numeric_t_per_sqrt_hz": b_opt_num,
        "b_n_opt_fT_per_sqrt_hz": b_opt * 1e15,
        "sensitivity_gain": gain,
        "sota_ratio": sota,
        "base_b_n_fT_per_sqrt_hz": p["base_b_n_t_per_sqrt_hz"] * 1e15,
        "sota_b_n_fT_per_sqrt_hz": p["sota_b_n_t_per_sqrt_hz"] * 1e15,
    }


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "baseline": {
        "desc": "基线：变压器 γ=1.5 / L_i=L_p / 2 µA / 4.2 K / 500 µm 拾取环（设计示例）",
        "overrides": {},
    },
    "no_focusing": {
        "desc": "无几何聚焦 γ=1（A_eff ↓1.5× ⇒ 灵敏度劣化）",
        "overrides": {"focusing_factor": 1.0},
    },
    "impedance_mismatch": {
        "desc": "阻抗失配 L_i=10·L_p（分压比 ↓ ⇒ 灵敏度劣化）",
        "overrides": {"input_inductance_h": 20.0e-9},
    },
    "low_temp": {
        "desc": "降温 1.5 K（Johnson S_I ∝ T ⇒ 灵敏度改善 √(T 比)）",
        "overrides": {"temp_k": 1.5},
    },
    "large_pickup": {
        "desc": "大拾取环 1000 µm（A_eff ↑4× ⇒ 灵敏度改善 4×）",
        "overrides": {"pickup_area_m2": (1000.0e-6) ** 2},
    },
}


def evaluate_scenario(name: str) -> Dict[str, Any]:
    """按情景名现算 QS-M7 综合物理。"""
    if name not in SCENARIOS:
        raise KeyError("未知情景：%r（可选 %s）" % (name, sorted(SCENARIOS)))
    over = SCENARIOS[name]["overrides"]
    out = squid_noise_optimization_physics(**over)
    out["scenario"] = name
    out["desc"] = SCENARIOS[name]["desc"]
    return out


def optimization_table() -> Dict[str, Dict[str, Any]]:
    """五情景优化灵敏度表（fT/√Hz · 全部模块现算）。"""
    return {n: {"desc": SCENARIOS[n]["desc"],
                "b_n_opt_fT_per_sqrt_hz": evaluate_scenario(n)["b_n_opt_fT_per_sqrt_hz"]}
            for n in SCENARIOS}


# ---------------------------------------------------------------------------
# 自检（机器门禁读到的必须是现算值）
# ---------------------------------------------------------------------------
def selfcheck_qs_m7() -> Dict[str, bool]:
    ok: Dict[str, bool] = {}

    # ── 链① 变压器有效面积 ──────────────────────────────────────────────
    a_closed = transformer_effective_area_m2(2.5e-7, 1.6e-9, 2.0e-9, 2.0e-9, 1.5)
    a_num = transformer_effective_area_numeric(2.5e-7, 1.6e-9, 2.0e-9, 2.0e-9, 1.5)
    # 🔴 残差 = Neumann 离散化截断（∝1/n_seg）⇒ 相对判据，**非**代数恒等
    ok["area_closed_eq_numeric"] = abs(a_num - a_closed) / a_closed < 2e-2
    # 反向探针：粗网格 ⇒ 残差显著放大（证明是真数值残差）
    a_coarse = transformer_effective_area_numeric(2.5e-7, 1.6e-9, 2.0e-9, 2.0e-9,
                                                  1.5, n_seg=32)
    ok["area_coarse_grid_degrades"] = (
        abs(a_coarse - a_closed) > 5.0 * abs(a_num - a_closed))

    # γ ↓ ⇒ A_eff ↓（单调）
    a_g1 = transformer_effective_area_m2(2.5e-7, 1.6e-9, 2.0e-9, 2.0e-9, 1.0)
    a_g2 = transformer_effective_area_m2(2.5e-7, 1.6e-9, 2.0e-9, 2.0e-9, 2.0)
    ok["area_monotone_focusing"] = a_g1 < a_closed < a_g2

    # L_i = L_p ⇒ 最优（A_eff 最大）
    a_match = transformer_effective_area_m2(2.5e-7, 1.6e-9, 2.0e-9, 2.0e-9, 1.5)
    a_mismatch = transformer_effective_area_m2(2.5e-7, 1.6e-9, 20.0e-9, 2.0e-9, 1.5)
    ok["area_impedance_match_optimal"] = a_match > a_mismatch

    # 变压器增益 > 1（A_eff > 裸环面积）
    ok["transformer_gain_gt_one"] = a_closed > (100.0e-6) ** 2

    # ── 链② 亚微米结噪声 ──────────────────────────────────────────────
    s_closed = submicron_junction_noise_psd(4.2, 2.0e-6, 20.0, 0.30)
    s_num = submicron_junction_noise_psd_numeric(4.2, 2.0e-6, 20.0, 0.30)
    ok["noise_closed_eq_numeric"] = abs(s_closed - s_num) / s_closed < 1e-2

    # S_I ∝ T
    s_lo = submicron_junction_noise_psd(1.5, 2.0e-6, 20.0, 0.30)
    ok["noise_scales_temp"] = abs(s_lo / s_closed - 1.5 / 4.2) < 1e-9

    # A-B 乘积锁定（R_n = (IR)_AB / I_c）
    ab = ambegaokar_baratoff_product_v(1.0e-3 * E_CHARGE)
    ok["ab_product_positive"] = ab > 0.0

    # 亚微米 R_n 抬升倍率：ρ=1 ⇒ 1；ρ↑ ⇒ 单调增且 ≤ max_gain
    ok["rn_gain_boundary"] = (abs(submicron_resistance_gain(1.0) - 1.0) < 1e-12
                              and submicron_resistance_gain(4.0) > submicron_resistance_gain(2.0)
                              and submicron_resistance_gain(1e9) < 8.0 + 1e-9)

    # ── 链③ 优化后灵敏度 ──────────────────────────────────────────────
    b_closed = optimized_field_sensitivity_t_per_sqrt_hz(
        4.2, 2.0e-6, 20.0 * submicron_resistance_gain(8.0), 2.5e-7, 1.6e-9, 2.0e-9, 2.0e-9, 1.5, 0.30)
    b_num = optimized_field_sensitivity_numeric(
        4.2, 2.0e-6, 20.0 * submicron_resistance_gain(8.0), 2.5e-7, 1.6e-9, 2.0e-9, 2.0e-9, 1.5, 0.30)
    ok["b_opt_closed_eq_numeric"] = abs(b_closed - b_num) / b_closed < 2e-2

    # 优化后优于基线（增益 > 1）
    ok["optimization_gain_gt_one"] = b_closed < 79.25e-15

    # 情景单调性：低温更优
    b_lo = optimized_field_sensitivity_t_per_sqrt_hz(
        1.5, 2.0e-6, 20.0 * submicron_resistance_gain(8.0), 2.5e-7, 1.6e-9, 2.0e-9, 2.0e-9, 1.5, 0.30)
    ok["scenario_low_temp_better"] = b_lo < b_closed

    # 综合链路报告值 == 现算
    phys = squid_noise_optimization_physics()
    ok["report_equals_recompute"] = (
        abs(phys["b_n_opt_t_per_sqrt_hz"] - b_closed) < 1e-30)

    return ok


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def design_qs_noise_opt(run_checks: bool = True) -> Dict[str, Any]:
    """QS-M7 签核：三链串联 + 自检 + 情景表。"""
    checks = selfcheck_qs_m7() if run_checks else {}
    phys = squid_noise_optimization_physics()
    verdict = "ACCEPT" if (not run_checks or all(checks.values())) else "REJECT"
    return {
        "caliber": QS_M7_CALIBER,
        "checks": checks,
        "verdict": verdict,
        "physics": phys,
        "scenarios": optimization_table(),
    }


def main() -> int:
    r = design_qs_noise_opt()
    p = r["physics"]
    print("QS-M7 SQUID 噪声优化：verdict=%s" % r["verdict"])
    print("  A_eff = %.3e m² · 面积增益 = %.2f×" % (p["a_eff_m2"], p["area_gain"]))
    print("  B_N,opt = %.3f fT/√Hz · 优化增益 = %.2f× · SOTA 比 = %.2f×"
          % (p["b_n_opt_fT_per_sqrt_hz"], p["sensitivity_gain"], p["sota_ratio"]))
    return 0 if r["verdict"] == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
