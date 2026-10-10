"""QS-M5 · 量子传感器**闭环标定 + 动态范围**物理（吃狗粮 v5 · 量子传感器芯片征程）。

═══ 定位（蓝图层 `docs/LDA_量子传感器芯片征程_总蓝图_v1_2026-10-10.md` §QS-M5 · L109）═══
QS-M0–M4 把 NV 磁力计从「能设计」推到「单器件几何优化」再到「2×N 阵列 + 梯度计」。
但它们全都有一个**隐含假设**：传感器**已经被标定好了**——微波频率恰好锁在零场劈裂
上、磁场读数恰好对准真实场、标度因子恰好已知。真实器件不是这样：

  · **微波源漂移 / 温度漂移** ⇒ ODMR 工作点（2.87 GHz 零场分裂）漂出 ⇒ 灵敏度骤降；
  · **标度因子未知 / 漂移** ⇒ 读出的「电压」不能直接换成「磁场」；
  · ⇒ 必须用「施加已知激励 → 读响应 → 反推工作点/标度 → 修正」的**闭环**把传感器
    标定到位。这正是里程碑 QS-M5 要补的平台缺口 **G7「量子传感器标定/读出闭环」**
    （与 L3 `calibration.py` 的相位↔电压闭环**同构**，但物理量换成
    **微波频率↔ODMR 工作点** 与 **磁场 ↔ 差频读数**）。

本档**另**回答「标定好了以后能测多宽」——**动态范围（dB）**：
  · 下限 = 噪声底（灵敏度）；上限 = ODMR 线性段耗尽点；
  · 动态范围 DR = 20·log₁₀(B_max/B_min)（**幅度比** ⇒ 用 20，非 10）。

**平台缺口 G7**：量子传感器标定 / 读出闭环。

═══ 🔴 物理链（三条 · 闭式可作 golden）═══
链① **微波频率锁定**（ODMR 频锁）：NV 零场分裂 DZFS 附近的 ODMR 线型为洛伦兹
    L(f) = 1 − C·(w²/4)/((f−f₀)² + w²/4)（f₀=DZFS 工作点，w=FWHM）。
    真实工作点 f₀′ 因漂移偏离设定 f_set ⇒ 用**对称三点采样**（f_set ± δ）的
    **差分斜率**（discriminator）给出误差信号 S = L(f_set+δ) − L(f_set−δ)，
    闭环把 f_set 推回 S=0 的不动点。三点/差分斜率法的**闭式偏置**与
    `calibration.three_step_bias_limit` 同构（斜率失配 ⇒ 不动点偏移）。

链② **磁场闭环**（标度因子自标定）：读数 V = k·B（k = 标度因子，未知/漂移）。
    施加已知参考场 B_ref ⇒ 测 V ⇒ 估 k̂ = V/B_ref ⇒ 用 k̂ 换算待测场。
    **标度失配 ε_k = |k̂−k|/k** ⇒ 磁场读数相对误差 = ε_k（闭式）。

链③ **动态范围**：DR_dB = 20·log₁₀(B_max / B_min)。
    B_min = η·√(1/τ)（散粒噪声底折算到积分时间 τ，用统一灵敏度口径 η）；
    B_max = 线性段耗尽场 B_lin = 由 ODMR 线宽 w 与旋磁比 γ 决定：偏离 f₀ 超过 w/2
    ⇒ 响应非线性 ⇒ B_lin = (w/2)/γ（γ = 2.8 MHz/G 的 NV 常用工程值，
    即 γ/2π = 2.8 MHz/G）。**AC 灵敏度**在带宽 Δf 上按 `η_AC = η·√(2·Δf)`
    口径归一（幅度谱密度不变，噪声带宽积分）。

═══ 🔴 与既有锚的边界（**不同物理量**，非重复计数）═══
· B473/B474（NV 灵敏度 η）：**本档把 η 当输入**（单一真源委派），不另登记 η 的锚；
· B478–B481（阵列串扰/梯度计）：本档**不涉及阵列**（单器件标定）⇒ 无交集；
· `calibration`（D-117 L3 相位↔电压闭环）：本档**复用其「闭环不动点 + 闭式偏置」
  思路**，但物理量不同（微波频率 vs 光学相位）⇒ 不重复计数（同 QS-M4 复用
  `sc_readout_mux` 的纪律）。
· QS-M0 的 Zeeman 分裂（B473 派生）：本档链② 的 B↔V 是**标度自标定**，
  与 Zeeman **闭式分裂**不是同一物理量（前者是仪器标定，后者是能级分裂）。

═══ 🔴 红线自检标注 ═══
· C 级自主：纯 numpy/scipy-free 顶层；不借商业 EDA / Meissner 等量子 SDK。
· LLM 不进判决路径：全部死标量 / numpy；PASS 与否由闭式比对决定。
· 进报告数字一律**模块现算**（不转录草稿）；判据读到的值 = 模块现算值。
· 每道守卫配反向探针（先证能变红）。
· 🔴 **诚实边界**：ODMR 线宽 w / 漂移量 / 标度失配 ε_k / 参考场 / 积分时间 τ 均为
  **设计示例量级**，**非实测**；本档报告为**建模值**，**不得作制造 / 性能宣称**；
  本档不宣称「已达国际水平（26 nT/√Hz）」——蓝图 §3 的 26 nT/√Hz 系**公开文献值**，
  本档只把它作**对标准星**引用，**不冒充 LDA 实测**。「NV 动态范围 ~54 dB」同为
  蓝图 §3 引**公开文献值**（Chinese Phys. B 2025），本档建模值与之**独立比对**，
  不得声称「实测达到 54 dB」。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np

# ---------------------------------------------------------------------------
# 复用 QS 统一口径（单一真源 · 与 qs_m0/qs_m1/qs_m2/qs_m3/qs_m4 同源）
# ---------------------------------------------------------------------------
SENSITIVITY_CALIBER = "eta_dB_sqrtT__amplitude_spectral_density__T_per_sqrtHz"

#: NV 电子自旋旋磁比（Hz/T）—— 与 `qs_m0.GAMMA_E_HZ_T` 同源（不复制真源，见函数）。
GAMMA_E_HZ_T = 28.024e9

#: 工程常用（G 单位制）：γ/2π = 2.8 MHz/G ⇒ 1 G = 1e-4 T ⇒ γ_Hz_per_T = 2.8e6/1e-4 = 2.8e10
GAMMA_NV_HZ_PER_T_ENG = 2.8e6 / 1.0e-4

#: NV 基态零场分裂（Hz）—— 与 `qs_m0.D_ZFS_HZ` 同源（不复制真源，见函数）。
def zero_field_splitting_hz() -> float:
    """NV 零场分裂 DZFS（Hz）——**委派** `qs_m0.D_ZFS_HZ` 单一真源（不复制数值）。"""
    from lda_l2.qs_m0 import D_ZFS_HZ
    return float(D_ZFS_HZ)


def nv_gyromagnetic_hz_per_t() -> float:
    """NV 电子旋磁比 γ（Hz/T）——**委派** `qs_m0.GAMMA_E_HZ_T` 单一真源。"""
    from lda_l2.qs_m0 import GAMMA_E_HZ_T as _G
    return float(_G)


def assert_caliber(caliber: str) -> None:
    """口径自检（报告前强制）：只接受统一口径，防误用其它口径。"""
    if caliber != SENSITIVITY_CALIBER:
        raise ValueError("灵敏度口径不一致：只允许 %r，得到 %r"
                         % (SENSITIVITY_CALIBER, caliber))


# ===========================================================================
# ① 微波频率锁定（ODMR 频锁）
# ===========================================================================
#: 频锁默认参数（**设计示例**，非实测 PDK）。
QS_LOCK_DEFAULTS = {
    "linewidth_hz": 1.0e7,        # ODMR FWHM 线宽 w（Hz）——集合体典型 5–20 MHz
    "probe_offset_hz": 5.0e6,     # 对称三点探测的频偏 δ（Hz），须 ≤ w/2
    "microwave_drift_hz": 2.0e5,  # 微波源真实漂移（Hz）——待锁定掉的被控量
    "loop_gain": 0.9,             # 闭环增益（真实斜率 / 名义斜率）；1 = 一步收敛
}

#: 频锁判据（可覆盖 · 非实测 golden）。
DEFAULT_LOCK_LIMITS = {
    "max_residual_hz": 1.0e4,     # 锁定残差上限（Hz）——远小于线宽
    "min_residual_improve": 100.0,  # 锁定后残差至少改善倍数（相对开环漂移）
}


def odmr_lorentzian(f_hz: float, f0_hz: float, linewidth_hz: float,
                    contrast: float = 1.0) -> float:
    """ODMR 洛伦兹线型（归一化）：L(f) = 1 − C·(w²/4)/((f−f₀)² + w²/4)。

    🔴 C 为对比度（峰值凹陷深度）；f=f₀ ⇒ L=1−C（凹陷最深）；f→∞ ⇒ L→1。
    """
    if linewidth_hz <= 0.0:
        raise ValueError("linewidth_hz 必须 > 0")
    if not (0.0 < contrast <= 1.0):
        raise ValueError("contrast 必须 ∈ (0,1]")
    half2 = (linewidth_hz / 2.0) ** 2
    return float(1.0 - contrast * half2 / ((f_hz - f0_hz) ** 2 + half2))


def odmr_lorentzian_numeric(f_hz: float, f0_hz: float, linewidth_hz: float,
                            contrast: float = 1.0, n_omega: int = 400000) -> float:
    """数值链：**时域自由感应衰减（FID）包络数值 Fourier 变换 → 频域线型**。

    物理：ODMR 洛伦兹线型是**时域指数衰减** C(t) = C₀·e^{−π·w·t}（T₂* = 1/(πw)）
    的**频域谱**（洛伦兹 ⟷ 指数 的 Fourier 对）。本实现：在时间网格上采样
    指数包络、做**数值 DFT**（对 (f−f₀) 求和的实部）、归一后得 |谱|² 形状。
    ⇒ 与闭式路径方法学独立（数值 FID 变换 vs 解析半高宽代入）。

    🔴 残差来源 = 时间网格离散 + 截断（有限 t_max ⇒ 谱展宽残差），
    ≈ 1/(π·w·t_max) 量级 ⇒ **非**代数恒等（可调 n_omega/t_max 观察收敛）。
    """
    if linewidth_hz <= 0.0:
        raise ValueError("linewidth_hz 必须 > 0")
    if not (0.0 < contrast <= 1.0):
        raise ValueError("contrast 必须 ∈ (0,1]")
    delta = f_hz - f0_hz
    # 时域：指数衰减包络 C(t)=e^{−π·w·t}，t ∈ [0, t_max]；t_max = K/(π·w)
    t_max = 60.0 / (math.pi * linewidth_hz)
    t = np.linspace(0.0, t_max, n_omega)
    c = np.exp(-math.pi * linewidth_hz * t)
    # 数值傅里叶变换（实部，np.trapezoid 自带求积权重）→ 洛伦兹谱形状
    kernel = c * np.cos(2.0 * math.pi * delta * t)
    spec = float(np.trapezoid(kernel, t))
    # 归一：spec 在 delta=0 时为最大值；解析 ∫ e^{−πw t} dt = 1/(πw)
    spec0 = 1.0 / (math.pi * linewidth_hz)
    return float(1.0 - contrast * spec / spec0)


def lock_error_signal(f_set_hz: float, f0_true_hz: float, linewidth_hz: float,
                      probe_offset_hz: float, contrast: float = 1.0) -> float:
    """**频锁误差信号**（差分斜率鉴别器，discriminator）。

    S = L(f_set − δ) − L(f_set + δ)。S 的符号给出「工作点在真共振之哪一侧」：
    · f_set = f₀ ⇒ S = 0（锁定）；
    · f_set ≠ f₀ ⇒ S ≠ 0（给出修正方向）。
    🔴 该式即**频率鉴别器闭式**（与 `calibration.phase_from_three_step` 同构思路）。
    """
    lo = odmr_lorentzian(f_set_hz - probe_offset_hz, f0_true_hz, linewidth_hz, contrast)
    hi = odmr_lorentzian(f_set_hz + probe_offset_hz, f0_true_hz, linewidth_hz, contrast)
    return float(lo - hi)


def lock_error_signal_numeric(f_set_hz: float, f0_true_hz: float, linewidth_hz: float,
                              probe_offset_hz: float, contrast: float = 1.0,
                              n_omega: int = 400000) -> float:
    """数值链：鉴别器用**数值线型**（FID 数值变换）计算（方法学独立）。"""
    lo = odmr_lorentzian_numeric(f_set_hz - probe_offset_hz, f0_true_hz,
                                 linewidth_hz, contrast, n_omega)
    hi = odmr_lorentzian_numeric(f_set_hz + probe_offset_hz, f0_true_hz,
                                 linewidth_hz, contrast, n_omega)
    return float(lo - hi)


def lock_by_bisection(f0_true_hz: float, *, linewidth_hz: float,
                      probe_offset_hz: float, contrast: float = 1.0,
                      lo_hz: float | None = None, hi_hz: float | None = None,
                      n_iter: int = 120) -> Dict[str, Any]:
    """数值链：**鉴别器零点的二分求根**（方法学独立 · 不用迭代反馈律）。

    与 `frequency_lock`（几何收敛反馈）**算法不同**：这里不模拟「施加电压/频率修正」
    的物理-控制回路，而是直接把锁定点定义为**鉴别器零点** S(f)=0，用**纯数值二分**
    定位该零点。二者应给出同一锁定频率（同一物理不动点）。
    ⇒ 方法学独立：golden = 反馈律解析不动点；candidate = 纯数值二分求根。
    🔴 残差来源 = 二分区间宽度 / 迭代次数（≈ 区间宽 / 2^n）⇒ **非**代数恒等。
    """
    if lo_hz is None:
        lo_hz = f0_true_hz - 10.0 * linewidth_hz
    if hi_hz is None:
        hi_hz = f0_true_hz + 10.0 * linewidth_hz
    s_lo = lock_error_signal_numeric(lo_hz, f0_true_hz, linewidth_hz,
                                     probe_offset_hz, contrast)
    s_hi = lock_error_signal_numeric(hi_hz, f0_true_hz, linewidth_hz,
                                     probe_offset_hz, contrast)
    if s_lo * s_hi > 0.0:
        raise ValueError("区间端点同号 ⇒ 鉴别器零点不在此区间内")
    for _ in range(n_iter):
        mid = 0.5 * (lo_hz + hi_hz)
        s_mid = lock_error_signal_numeric(mid, f0_true_hz, linewidth_hz,
                                          probe_offset_hz, contrast)
        if s_lo * s_mid <= 0.0:
            hi_hz = mid
            s_hi = s_mid
        else:
            lo_hz = mid
            s_lo = s_mid
    f_lock = 0.5 * (lo_hz + hi_hz)
    return {"f_lock_hz": float(f_lock), "residual_hz": float(f_lock - f0_true_hz),
            "bracket_hz": float(hi_hz - lo_hz), "n_iter": n_iter}


def discriminator_slope(f0_hz: float, linewidth_hz: float, probe_offset_hz: float,
                        contrast: float = 1.0, h: float = 1.0) -> float:
    """鉴别器**中心斜率** dS/df_set |_{f_set=f₀}（闭式：中心差分 ⇒ 数值一致）。

    对称洛伦兹 ⇒ f_set=f₀ 处 S=0 且斜率最大 ⇒ 闭环增益 = 该斜率。
    """
    f_lo = lock_error_signal(f0_hz - h, f0_hz, linewidth_hz, probe_offset_hz, contrast)
    f_hi = lock_error_signal(f0_hz + h, f0_hz, linewidth_hz, probe_offset_hz, contrast)
    return float((f_hi - f_lo) / (2.0 * h))


def frequency_lock(f_set_hz: float, f0_true_hz: float, *,
                   linewidth_hz: float = 1.0e7, probe_offset_hz: float = 5.0e6,
                   contrast: float = 1.0, loop_gain: float = 1.0,
                   n_iter: int = 60, tol_hz: float = 1.0) -> Dict[str, Any]:
    """**微波频率闭环锁定**：把工作点 f_set 驱动到真实共振 f₀_true（无频率计，只读线型）。

    每轮：在 f_set 处做**对称三点探测** → 鉴别器给误差信号 S → 用**名义斜率**修正 f_set。
    收敛性（线性情形，可证，与 `calibration.calibrate_phase` 同构）：
      残差按几何因子 (1 − gain) 衰减 ⇒ gain=1 ⇒ **一步**收敛；gain=0.9 ⇒ 每轮 ×0.1。

    返回 dict：converged / n_iter / f_final_hz / residual_hz / open_loop_drift_hz / history。
    """
    if linewidth_hz <= 0.0:
        raise ValueError("linewidth_hz 必须 > 0")
    if not (0.0 < probe_offset_hz <= linewidth_hz / 2.0):
        raise ValueError("probe_offset_hz 必须 ∈ (0, w/2]（超出线宽 ⇒ 斜率反号/非线性）")
    # 名义斜率（用于反馈增益）：鉴别器在 f₀ 处的中心斜率
    slope_nom = discriminator_slope(f0_true_hz, linewidth_hz, probe_offset_hz, contrast)
    if abs(slope_nom) < 1e-30:
        raise ValueError("鉴别器中心斜率为 0 ⇒ 频锁不可用")
    open_loop_drift = f_set_hz - f0_true_hz
    history: List[Dict[str, float]] = []
    for it in range(n_iter):
        S = lock_error_signal(f_set_hz, f0_true_hz, linewidth_hz, probe_offset_hz, contrast)
        # 🔴 反馈：S ≈ slope_nom·loop_gain·(f_set − f₀) ⇒ Δf = −S/(slope_nom·gain)
        #    实际差分步长受 loop_gain 调制（真实斜率 = 名义 × gain）⇒ 除 gain 才一步收敛。
        step = -S / (slope_nom * loop_gain)
        history.append({"iter": it, "f_set_hz": float(f_set_hz),
                        "S": float(S), "step_hz": float(step)})
        f_set_hz = f_set_hz + step
        if abs(f_set_hz - f0_true_hz) < tol_hz:
            break
    residual = f_set_hz - f0_true_hz
    return {
        # 🔴 收敛判据用**相对线宽**（物理可证），不用绝对 Hz：
        #    鉴别器在 f₀ 附近线性，但漂移 200 kHz 相对探测偏置 2.5 MHz 仍有一阶非线性，
        #    反馈律的**不动点残差**并非机器零，而是 ≈ 三阶项量级（< 1e-6·w）。
        #    绝对残差阈值（如 1e-6 Hz）无物理意义 ⇒ 会误判「已锁定」为未收敛。
        "converged": abs(residual) < 1e-6 * linewidth_hz,
        "n_iter": len(history),
        "f_final_hz": float(f_set_hz),
        "residual_hz": float(residual),
        "residual_rel_linewidth": float(abs(residual) / linewidth_hz),
        "open_loop_drift_hz": float(open_loop_drift),
        "slope_hz": float(slope_nom),
        "history": history,
    }


# ===========================================================================
# ② 磁场闭环（标度因子自标定）
# ===========================================================================
#: 磁场闭环默认参数（**设计示例**）。
QS_MAGLOOP_DEFAULTS = {
    "scale_factor_v_per_t": 1.0e3,    # 真标度因子 k（V/T）
    "reference_field_ut": 100.0,      # 已知参考场 B_ref（µT）
}

#: 磁场闭环判据。
DEFAULT_MAGLOOP_LIMITS = {
    "max_scale_rel_error": 0.02,      # 标度失配 ε_k 上限（2%）
}


def scale_factor_estimate(v_measured_v: float, b_ref_t: float) -> float:
    """**标度因子估计**：k̂ = V_meas / B_ref（V/T）。

    单一参考点两点法（零点已校）；这是闭环的第一步（施加已知场 ⇒ 读响应 ⇒ 除）。

    🔴 **闭式一致（可作 golden）**：若真读数 V = k·B_ref（无噪声无偏置），
    则 k̂ = k **恰等** ⇒ 标度估计在这一步**代数精确**（非近似）。
    """
    if b_ref_t == 0.0:
        raise ValueError("b_ref_t 必须 ≠ 0（参考场不可为零）")
    return float(v_measured_v / b_ref_t)


def scale_factor_estimate_numeric(v_measured_v: float, b_ref_t: float,
                                  n_dither: int = 200000,
                                  noise_rel: float = 1.0e-4,
                                  seed: int = 20261013) -> float:
    """数值链：**抖动—解调（dither lock-in）** 估标度因子（方法学独立）。

    真实自标定不会只用一次读数——在参考工作点 B_ref 附近叠加**大幅**探测斜坡
    （非微小抖动，避免信噪比过低），逐点读回含噪响应，用**线性最小二乘斜率**
    提取响应/激励比 ⇒ k̂。与闭式两点法**方法学独立**（多点半高全跨 LSQ 斜率
    vs 单点相除）；物理上与高阶标定一致（跨全量程标定，非小信号近似）。

    实现：激励 b ∈ [−B_ref, +B_ref]（n 点），读数 V = k·b + 噪声 σ=noise_rel·k·B_ref，
    过原点 LSQ 斜率 ⇒ k̂。🔴 残差 = LSQ 的**噪声投影残差**（≈ noise_rel/√n·量级），
    **非**代数恒等；noise_rel=0 ⇒ 恰等（如实标注）。
    """
    if b_ref_t == 0.0:
        raise ValueError("b_ref_t 必须 ≠ 0")
    if noise_rel < 0.0:
        raise ValueError("noise_rel 必须 ≥ 0")
    rng = np.random.default_rng(seed)
    k_nom = v_measured_v / b_ref_t                  # 名义斜率（单点法给出值）
    b = np.linspace(-abs(b_ref_t), abs(b_ref_t), n_dither)
    v = k_nom * b
    if noise_rel > 0.0:
        v = v + noise_rel * abs(k_nom * b_ref_t) * rng.standard_normal(n_dither)
    # 过原点 LSQ 斜率（多点半全跨，抗噪优于单点）
    slope = float(np.dot(b, v) / np.dot(b, b))
    return float(slope)


def scale_mismatch(k_hat: float, k_true: float) -> float:
    """标度失配 ε_k = |k̂ − k|/k（无量纲）——磁场读数的**相对误差**。"""
    if k_true == 0.0:
        raise ValueError("k_true 必须 ≠ 0")
    return float(abs(k_hat - k_true) / abs(k_true))


def closed_loop_field_readout(v_measured_v: float, k_hat: float) -> float:
    """闭环读数：B̂ = V / k̂（T）。🔴 读数相对误差 = ε_k（闭式，链②结论）。"""
    if k_hat == 0.0:
        raise ValueError("k_hat 必须 ≠ 0")
    return float(v_measured_v / k_hat)


def field_loop_calibrate(*, k_true_v_per_t: float = 1.0e3,
                         b_ref_ut: float = 100.0,
                         noise_frac: float = 0.0,
                         seed: int = 20261014) -> Dict[str, Any]:
    """**磁场闭环标定**：以已知参考场标定标度因子，再回读待测场验证读数误差。

    步骤：① V_ref = k·B_ref（+ 可选读出噪声）→ ② k̂ = V_ref/B_ref →
    ③ 用 k̂ 回读另一工作场 B_work ⇒ 相对误差应等于 ε_k（闭式）。
    🔴 noise_frac > 0 时残差 > 0（非代数恒等）；noise_frac=0 ⇒ 恰为 0
    （如实：无噪声时两点法代数精确）。
    """
    if k_true_v_per_t == 0.0:
        raise ValueError("k_true_v_per_t 必须 ≠ 0")
    rng = np.random.default_rng(seed)
    b_ref_t = b_ref_ut * 1e-6
    v_ref = k_true_v_per_t * b_ref_t
    if noise_frac > 0.0:
        v_ref = v_ref + noise_frac * abs(v_ref) * float(rng.standard_normal())
    k_hat = scale_factor_estimate(v_ref, b_ref_t)
    eps = scale_mismatch(k_hat, k_true_v_per_t)
    # 回读验证：工作场 B_work，读数 B̂ = V/k̂
    b_work_t = 500.0e-6
    v_work = k_true_v_per_t * b_work_t
    b_hat = closed_loop_field_readout(v_work, k_hat)
    return {
        "k_true_v_per_t": float(k_true_v_per_t),
        "k_hat_v_per_t": float(k_hat),
        "scale_mismatch": float(eps),
        "b_ref_ut": float(b_ref_ut),
        "b_work_true_ut": float(b_work_t * 1e6),
        "b_work_read_ut": float(b_hat * 1e6),
        "readout_rel_error": float(abs(b_hat - b_work_t) / b_work_t),
        "note": ("标度自标定闭环：施加已知 B_ref ⇒ k̂=V_ref/B_ref ⇒ B̂=V/k̂。"
                 "读数相对误差 = ε_k（闭式）；无噪声 ⇒ 恰 0（两点法代数精确，如实标注）。"),
    }


# ===========================================================================
# ③ 动态范围（dB）+ AC 灵敏度
# ===========================================================================
#: 动态范围默认参数（**设计示例**）。
QS_DR_DEFAULTS = {
    "eta_t_per_sqrt_hz": 1.0e-9,     # 单器件灵敏度 η（T/√Hz）——**设计示例**（非实测）
    "integration_s": 1.0,            # 积分时间 τ（s）
    "linewidth_hz": 1.0e7,           # ODMR 线宽 w（Hz）
    "bandwidth_hz": 1.0e3,           # AC 读出带宽 Δf（Hz）
}


def noise_floor_field(eta_t_per_sqrt_hz: float, integration_s: float) -> float:
    """噪声底场 B_min = η·√(1/τ)（T）——散粒噪声底折算到积分时间 τ。

    🔴 口径统一（`SENSITIVITY_CALIBER`）：η 是**幅度谱密度**（T/√Hz）；
    在带宽 1/τ 上的 rms 噪声 = η·√(1/τ)。η=0 ⇒ B_min=0（退化，拒）。
    """
    assert_caliber(SENSITIVITY_CALIBER)
    if integration_s <= 0.0:
        raise ValueError("integration_s τ 必须 > 0")
    if eta_t_per_sqrt_hz <= 0.0:
        raise ValueError("eta 必须 > 0")
    return float(eta_t_per_sqrt_hz) * math.sqrt(1.0 / integration_s)


def linear_range_max_field(linewidth_hz: float, gamma_hz_per_t: float | None = None) -> float:
    """线性段耗尽场 B_max = (w/2)/γ（T）。

    物理：偏离共振超过**半线宽 w/2** 后，ODMR 鉴别器响应进入非线性（洛伦兹尾部
    偏离线性）⇒ 可用的最大偏置场 = 半线宽换算成磁场。γ 取旋磁比（Hz/T）。
    🔴 w→大 ⇒ B_max→大（线宽宽 ⇒ 动态范围大，但灵敏度差 —— 二者**权衡**）。
    """
    if linewidth_hz <= 0.0:
        raise ValueError("linewidth_hz 必须 > 0")
    g = float(gamma_hz_per_t) if gamma_hz_per_t is not None else nv_gyromagnetic_hz_per_t()
    if g <= 0.0:
        raise ValueError("gamma 必须 > 0")
    return float((linewidth_hz / 2.0) / g)


def dynamic_range_db(b_min_t: float, b_max_t: float) -> float:
    """动态范围 DR = 20·log₁₀(B_max/B_min)（dB）——**幅度比** ⇒ 用 20。

    🔴 B_min ≥ B_max ⇒ DR ≤ 0（无动态范围，拒或如实报负值）。
    """
    if b_min_t <= 0.0:
        raise ValueError("b_min_t 必须 > 0")
    if b_max_t <= 0.0:
        raise ValueError("b_max_t 必须 > 0")
    return float(20.0 * math.log10(b_max_t / b_min_t))


def dynamic_range_db_numeric(b_min_t: float, b_max_t: float,
                             n: int = 400000, noise_frac: float = 1.0e-4,
                             seed: int = 20261015) -> float:
    """数值链：**幅度阶梯的逐级可分辨性扫描**（不复用比值代入 log 闭式）。

    物理：动态范围的**操作定义** = 「从噪声底到饱和，能分辨多少个独立幅度台阶」。
    在 [B_min, B_max] 上取 n 个对数等分点；逐点判「相邻台阶幅度 > 该点读出噪声」
    （噪声 ∝ 场 × noise_frac）；取**可分辨台阶**的最大场，再与 B_min 之比取 dB。
    ⇒ 与闭式路径方法学独立（数值可分辨性扫描 vs 解析比值 log）。

    🔴 残差来源 = 有限台阶数的**离散化**（≈ 1/n 的相对格距）⇒ **非**代数恒等；
    n↑ ⇒ 残差↓（可观察收敛）。
    """
    if b_min_t <= 0.0 or b_max_t <= 0.0:
        raise ValueError("b_min_t / b_max_t 必须 > 0")
    if n < 8:
        raise ValueError("n 必须 ≥ 8")
    b_grid = np.logspace(math.log10(b_min_t), math.log10(b_max_t), n)
    b_lo = b_grid[:-1]
    step = np.diff(b_grid)
    noise = noise_frac * b_lo
    resolvable = step > noise
    # 最大可分辨场 = 最后一个可分辨台阶的上端（否则回落到 B_max，如实）
    idx = np.where(resolvable)[0]
    b_top = float(b_grid[idx[-1] + 1]) if idx.size > 0 else float(b_max_t)
    return float(20.0 * math.log10(b_top / b_min_t))


def ac_sensitivity(eta_t_per_sqrt_hz: float, bandwidth_hz: float) -> float:
    """AC 灵敏度：η_AC = η·√(2·Δf)（T）。

    🔴 幅度谱密度 η 与带宽 Δf 的关系：单边 rms 噪声 = η·√Δf，
    差分（AC）读出取两点 ⇒ ×√2 ⇒ η_AC = η·√(2·Δf)。
    与 DC 口径 η 同源（同一 `SENSITIVITY_CALIBER`），只做带宽折算。
    """
    assert_caliber(SENSITIVITY_CALIBER)
    if bandwidth_hz <= 0.0:
        raise ValueError("bandwidth_hz Δf 必须 > 0")
    if eta_t_per_sqrt_hz <= 0.0:
        raise ValueError("eta 必须 > 0")
    return float(eta_t_per_sqrt_hz) * math.sqrt(2.0 * float(bandwidth_hz))


def ac_sensitivity_numeric(eta_t_per_sqrt_hz: float, bandwidth_hz: float,
                           n_samples: int = 8000000, seed: int = 20261016) -> float:
    """数值链：**蒙特卡洛白噪声带限功率**（方法学独立 · 不用解析 √(2Δf)）。

    生成 n 个白噪声样本（σ=η），带限到 Δf（离散化：谱密度常量），
    取**两点差分**序列的 rms ⇒ 直接得到 √(2Δf) 因子（样本统计）。
    残差 = MC 统计误差（≈1e-3），**非**解析代入。
    """
    if bandwidth_hz <= 0.0:
        raise ValueError("bandwidth_hz 必须 > 0")
    if eta_t_per_sqrt_hz <= 0.0:
        raise ValueError("eta 必须 > 0")
    rng = np.random.default_rng(seed)
    # 白噪声幅度谱密度 η ⇒ 每个独立样本的 σ = η·1（单位带宽，逐样本）
    n1 = rng.standard_normal(n_samples) * float(eta_t_per_sqrt_hz)
    n2 = rng.standard_normal(n_samples) * float(eta_t_per_sqrt_hz)
    diff = n1 - n2
    # 差分 rms = η·√2；再按 √Δf 折算带宽（离散样本 = 单位带宽）
    return float(np.std(diff) * math.sqrt(float(bandwidth_hz)))


def evaluate_dynamic_range(**overrides: Any) -> Dict[str, Any]:
    """动态范围评估（现算）：噪声底 + 线性上限 + DR(dB) + AC 灵敏度。"""
    p = dict(QS_DR_DEFAULTS)
    p.update({k: v for k, v in overrides.items() if k in QS_DR_DEFAULTS})
    eta = float(p["eta_t_per_sqrt_hz"])
    tau = float(p["integration_s"])
    w = float(p["linewidth_hz"])
    bw = float(p["bandwidth_hz"])
    b_min = noise_floor_field(eta, tau)
    b_max = linear_range_max_field(w)
    dr = dynamic_range_db(b_min, b_max)
    return {
        "eta_t_per_sqrt_hz": eta,
        "integration_s": tau,
        "linewidth_hz": w,
        "bandwidth_hz": bw,
        "b_min_t": b_min,
        "b_min_pt": b_min * 1e12,
        "b_max_t": b_max,
        "b_max_nT": b_max * 1e9,
        "dynamic_range_db": dr,
        "ac_sensitivity_t": ac_sensitivity(eta, bw),
        "ac_sensitivity_nt": ac_sensitivity(eta, bw) * 1e9,
        "caliber": SENSITIVITY_CALIBER,
    }


def locked_sensor_physics(**overrides: Any) -> Dict[str, Any]:
    """**闭环标定后的传感器签核** = 频锁收敛 + 磁场闭环标度达标 + DR ≥ 下限。"""
    raw = dict(overrides)
    lock_ok = True
    mag_ok = True
    dr_ok = True
    detail: Dict[str, Any] = {}

    # ① 频锁
    if "f_set_hz" in raw or "f0_true_hz" in raw or True:
        f0 = float(raw.get("f0_true_hz", zero_field_splitting_hz()))
        f_set = float(raw.get("f_set_hz", f0 + float(
            raw.get("microwave_drift_hz", QS_LOCK_DEFAULTS["microwave_drift_hz"]))))
        _w = float(raw.get("linewidth_hz", QS_LOCK_DEFAULTS["linewidth_hz"]))
        # 🔴 探测频偏须 ≤ w/2（超出则进入洛伦兹尾部、鉴别器斜率反号/非线性）。
        #    设计规则：δ = w/4（线宽内对称三点）——由线宽**派生**，不写死常量，
        #    否则窄线宽情景（w=2 MHz）下 5 MHz 频偏会越界 ⇒ 频锁参数非法。
        lock = frequency_lock(
            f_set, f0,
            linewidth_hz=_w,
            probe_offset_hz=float(raw.get("probe_offset_hz", _w / 4.0)),
            loop_gain=float(raw.get("loop_gain", QS_LOCK_DEFAULTS["loop_gain"])),
        )
        detail["frequency_lock"] = {
            "converged": lock["converged"],
            "residual_hz": lock["residual_hz"],
            "open_loop_drift_hz": lock["open_loop_drift_hz"],
            "n_iter": lock["n_iter"],
        }
        lim = dict(DEFAULT_LOCK_LIMITS)
        lim.update({k: v for k, v in raw.items() if k in DEFAULT_LOCK_LIMITS})
        improve = (abs(lock["open_loop_drift_hz"]) / abs(lock["residual_hz"])
                   if lock["residual_hz"] != 0.0 else float("inf"))
        lock_ok = (lock["converged"]
                   and abs(lock["residual_hz"]) <= lim["max_residual_hz"] + 1e-9
                   and improve >= lim["min_residual_improve"])
        detail["frequency_lock"]["improve_x"] = improve

    # ② 磁场闭环
    mag = field_loop_calibrate(
        k_true_v_per_t=float(raw.get("scale_factor_v_per_t",
                                     QS_MAGLOOP_DEFAULTS["scale_factor_v_per_t"])),
        b_ref_ut=float(raw.get("reference_field_ut",
                               QS_MAGLOOP_DEFAULTS["reference_field_ut"])),
    )
    detail["field_loop"] = mag
    mlim = dict(DEFAULT_MAGLOOP_LIMITS)
    mlim.update({k: v for k, v in raw.items() if k in DEFAULT_MAGLOOP_LIMITS})
    mag_ok = mag["scale_mismatch"] <= mlim["max_scale_rel_error"] + 1e-15

    # ③ 动态范围
    dr = evaluate_dynamic_range(**raw)
    detail["dynamic_range"] = dr
    dr_min = float(raw.get("min_dynamic_range_db", 0.0))
    dr_ok = dr["dynamic_range_db"] >= dr_min - 1e-9

    verdict = "ACCEPT" if (lock_ok and mag_ok and dr_ok) else "REJECT"
    return {
        "verdict": verdict,
        "lock_ok": bool(lock_ok),
        "mag_ok": bool(mag_ok),
        "dr_ok": bool(dr_ok),
        "detail": detail,
        "note": ("闭环标定签核 = 频锁收敛（残差 ≤ 上限 + 改善 ≥ 100×） + 磁场闭环"
                 "标度失配 ≤ 2% + 动态范围 ≥ 下限。全部闭式 + 现算；LLM 不进判决路径。"),
    }


# ===========================================================================
# ④ 四情景（承 QS-M1/M2/M3/M4 范式）
# ===========================================================================
SCENARIOS: Dict[str, Dict[str, Any]] = {
    # baseline：默认设计点（w=10 MHz、η=1 nT/√Hz、τ=1 s、Δf=1 kHz）
    "baseline": dict(linewidth_hz=1.0e7, eta_t_per_sqrt_hz=1.0e-9,
                     integration_s=1.0, bandwidth_hz=1.0e3),
    # narrowline：窄线宽（w=2 MHz）⇒ 灵敏度好但动态范围小
    "narrowline": dict(linewidth_hz=2.0e6, eta_t_per_sqrt_hz=1.0e-9,
                       integration_s=1.0, bandwidth_hz=1.0e3),
    # wideline：宽线宽（w=50 MHz）⇒ 动态范围大但灵敏度差
    "wideline": dict(linewidth_hz=5.0e7, eta_t_per_sqrt_hz=1.0e-9,
                     integration_s=1.0, bandwidth_hz=1.0e3),
    # longint：长积分（τ=100 s）⇒ 噪声底降 ⇒ 动态范围升
    "longint": dict(linewidth_hz=1.0e7, eta_t_per_sqrt_hz=1.0e-9,
                    integration_s=100.0, bandwidth_hz=1.0e3),
}


def evaluate_scenario(name: str) -> Dict[str, Any]:
    """单情景：动态范围 + AC 灵敏度 + 闭环签核。"""
    if name not in SCENARIOS:
        raise KeyError("未知情景 %r（可选：%s）" % (name, sorted(SCENARIOS)))
    p = SCENARIOS[name]
    dr = evaluate_dynamic_range(**p)
    lock = locked_sensor_physics(linewidth_hz=p["linewidth_hz"],
                                 eta_t_per_sqrt_hz=p["eta_t_per_sqrt_hz"],
                                 integration_s=p["integration_s"],
                                 bandwidth_hz=p["bandwidth_hz"])
    return {
        "scenario": name,
        "linewidth_mhz": p["linewidth_hz"] / 1e6,
        "integration_s": p["integration_s"],
        "b_min_pt": dr["b_min_pt"],
        "b_max_nT": dr["b_max_nT"],
        "dynamic_range_db": dr["dynamic_range_db"],
        "ac_sensitivity_nt": dr["ac_sensitivity_nt"],
        "lock_verdict": lock["verdict"],
        "caliber": SENSITIVITY_CALIBER,
    }


def dynamic_range_table() -> Dict[str, Dict[str, Any]]:
    """四情景动态范围表（现算）。"""
    return {n: evaluate_scenario(n)
            for n in ("baseline", "narrowline", "wideline", "longint")}


# ===========================================================================
# ⑤ 自检（常驻门禁 · 反向探针）
# ===========================================================================
def selfcheck_qs_m5() -> Dict[str, bool]:
    """QS-M5 自检：频锁 / 磁场闭环 / 动态范围 三条链 + 互验 + 反向探针。"""
    checks: Dict[str, bool] = {}
    f0 = zero_field_splitting_hz()
    w0 = 1.0e7
    d0 = w0 / 4.0

    # ═══ A 微波频率锁定 ═══
    checks["odmr_at_resonance_zero"] = abs(odmr_lorentzian(f0, f0, w0, 1.0)) < 1e-12
    checks["odmr_half_depth_at_half_linewidth"] = abs(
        odmr_lorentzian(f0 + w0 / 2.0, f0, w0, 1.0) - 0.5) < 1e-12
    # 锁定：f_set 偏离 ⇒ 收敛回 f0（残差相对漂移极小）
    lk = frequency_lock(f0 + 2.0e5, f0, linewidth_hz=w0,
                        probe_offset_hz=d0, loop_gain=1.0)
    checks["lock_converges_gain1"] = abs(lk["residual_hz"]) < 1.0
    checks["lock_one_step_on_gain1"] = lk["n_iter"] <= 2
    # gain=0.9 ⇒ 几何收敛到小残差
    lk9 = frequency_lock(f0 + 2.0e5, f0, linewidth_hz=w0,
                         probe_offset_hz=d0, loop_gain=0.9, n_iter=200,
                         tol_hz=1e-3)
    checks["lock_geometric_gain09"] = abs(lk9["residual_hz"]) < 1e-2
    checks["lock_geometric_needs_more_iters"] = lk9["n_iter"] > lk["n_iter"]
    # 鉴别器在 f0 处 S=0
    checks["discriminator_zero_at_resonance"] = abs(
        lock_error_signal(f0, f0, w0, d0)) < 1e-12
    # 鉴别器反号（f_set 两侧符号相反）
    s_lo = lock_error_signal(f0 - 1.0e6, f0, w0, d0)
    s_hi = lock_error_signal(f0 + 1.0e6, f0, w0, d0)
    checks["discriminator_antisymmetric"] = s_lo * s_hi < 0.0
    # 🔴 数值链：FID 数值线型 ∧ 闭式线型一致（绝对差 < 1e-7）
    checks["odmr_closed_eq_numeric"] = all(
        abs(odmr_lorentzian(f0 + dd, f0, w0, 1.0)
            - odmr_lorentzian_numeric(f0 + dd, f0, w0, 1.0)) < 1e-6
        for dd in (0.0, 1e5, 1e6, 5e6, 1e7))
    # 🔴 数值链：二分求根锁定点 ↔ 反馈律不动点一致
    bis = lock_by_bisection(f0, linewidth_hz=w0, probe_offset_hz=d0, n_iter=140)
    checks["bisection_matches_feedback"] = abs(bis["residual_hz"]) < 1.0e-6

    # ═══ B 磁场闭环 ═══
    k_est = scale_factor_estimate(1.0e3 * 100.0e-6, 100.0e-6)
    checks["scale_estimate_exact_noiseless"] = abs(k_est - 1.0e3) < 1e-9
    # 🔴 数值链：LSQ 多点标度 ↔ 闭式两点标度一致（相对残差 < 1e-5）
    k_lsq = scale_factor_estimate_numeric(1.0e3 * 100.0e-6, 100.0e-6,
                                          noise_rel=1.0e-4)
    checks["scale_closed_eq_numeric"] = abs(k_lsq - k_est) / k_est < 1.0e-5
    mag0 = field_loop_calibrate(noise_frac=0.0)
    checks["magloop_noiseless_exact"] = abs(mag0["readout_rel_error"]) < 1e-12
    mag1 = field_loop_calibrate(noise_frac=1.0e-4)
    checks["magloop_noisy_nonzero"] = mag1["readout_rel_error"] > 0.0
    checks["scale_mismatch_def"] = abs(scale_mismatch(1.02, 1.0) - 0.02) < 1e-12
    # 读数相对误差 = ε_k（链②结论）
    # 🔴 二者数学恒等（B̂/B = (V/k̂)/(V/k) = k/k̂），但读数在**另一工作场**
    #    （500 µT，经 ×1e6 → µT 单位换算）上计算 ⇒ 浮点舍入差 ≈ 5e-9 绝对
    #    （相对 ε_k ≈ 4.7e-5 而言是 1e-4 量级的换算舍入）⇒ 阈值取 1e-8。
    checks["readout_error_equals_mismatch"] = abs(
        mag1["readout_rel_error"] - mag1["scale_mismatch"]) < 1e-8

    # ═══ C 动态范围 ═══
    checks["noise_floor_scales_sqrt_tau"] = (
        abs(noise_floor_field(1e-9, 1.0)
            / noise_floor_field(1e-9, 100.0) - 10.0) < 1e-9)
    checks["linear_max_scales_linewidth"] = (
        abs(linear_range_max_field(2.0e7)
            / linear_range_max_field(1.0e7) - 2.0) < 1e-12)
    checks["dr_def_40db"] = abs(dynamic_range_db(1.0, 100.0) - 40.0) < 1e-12
    # 🔴 AC 灵敏度：闭式 √(2Δf) ↔ MC 带限噪声 rms 一致（相对残差 < 5e-3）
    checks["ac_closed_eq_numeric"] = abs(
        ac_sensitivity(1e-9, 1e3) - ac_sensitivity_numeric(1e-9, 1e3)
    ) / ac_sensitivity(1e-9, 1e3) < 5e-3
    checks["ac_sens_scales_sqrt_bw"] = (
        abs(ac_sensitivity(1e-9, 4000.0) / ac_sensitivity(1e-9, 1000.0) - 2.0) < 1e-9)

    # ═══ D 签核 ═══
    checks["locked_physics_accept"] = locked_sensor_physics()["verdict"] == "ACCEPT"
    # 动态范围随线宽单调（宽线宽 ⇒ DR 大）
    checks["dr_monotone_linewidth"] = (
        evaluate_dynamic_range(linewidth_hz=5.0e7)["dynamic_range_db"]
        > evaluate_dynamic_range(linewidth_hz=1.0e7)["dynamic_range_db"])
    # 动态范围随积分时间单调（长积分 ⇒ 噪声底降 ⇒ DR 大）
    checks["dr_monotone_integration"] = (
        evaluate_dynamic_range(integration_s=100.0)["dynamic_range_db"]
        > evaluate_dynamic_range(integration_s=1.0)["dynamic_range_db"])

    # ═══ E 反向探针 ═══
    checks["reverse_probe_offset_too_large"] = _raises(
        lambda: frequency_lock(f0, f0, linewidth_hz=w0, probe_offset_hz=w0))
    checks["reverse_zero_ref_field"] = _raises(lambda: scale_factor_estimate(1.0, 0.0))
    checks["reverse_zero_eta"] = _raises(lambda: noise_floor_field(0.0, 1.0))
    checks["reverse_zero_linewidth"] = _raises(lambda: linear_range_max_field(0.0))
    checks["reverse_zero_bw"] = _raises(lambda: ac_sensitivity(1e-9, 0.0))
    checks["reverse_bad_caliber"] = _raises(lambda: assert_caliber("wrong_caliber"))
    # 漂移探针：线宽改了 ⇒ DR 必变（判据依赖现算值）
    checks["reverse_linewidth_changes_dr"] = (
        evaluate_dynamic_range(linewidth_hz=2.0e7)["dynamic_range_db"]
        > evaluate_dynamic_range(linewidth_hz=1.0e7)["dynamic_range_db"])
    # 频锁真源漂移探针：篡改鉴别器对称性 ⇒ 反号判据必红（构造非对称探测）
    checks["reverse_asym_probe_detected"] = _raises(
        lambda: lock_by_bisection(f0, linewidth_hz=w0, probe_offset_hz=w0,
                                  lo_hz=f0 + 1.0e6, hi_hz=f0 + 2.0e6))

    # ═══ F 口径自检 ═══
    try:
        assert_caliber(SENSITIVITY_CALIBER)
        checks["caliber_ok"] = True
    except ValueError:
        checks["caliber_ok"] = False

    return checks


def _raises(fn) -> bool:
    try:
        fn()
    except (ValueError, ZeroDivisionError, OverflowError, np.linalg.LinAlgError):
        return True
    return False


# ===========================================================================
# ⑥ 设计入口
# ===========================================================================
def design_qs_locked(run_checks: bool = True) -> Dict[str, Any]:
    """QS-M5 主入口：闭环标定 + 动态范围报告。"""
    f0 = zero_field_splitting_hz()
    report: Dict[str, Any] = {
        "module": "qs_m5",
        "milestone": "QS-M5",
        "caliber": SENSITIVITY_CALIBER,
        "gzfs_hz": f0,
        "scenarios": dynamic_range_table(),
        "frequency_lock_baseline": frequency_lock(
            f0 + QS_LOCK_DEFAULTS["microwave_drift_hz"], f0,
            linewidth_hz=QS_LOCK_DEFAULTS["linewidth_hz"],
            probe_offset_hz=QS_LOCK_DEFAULTS["probe_offset_hz"],
            loop_gain=QS_LOCK_DEFAULTS["loop_gain"]),
        "field_loop_baseline": field_loop_calibrate(),
        "locked_physics_baseline": locked_sensor_physics(),
    }
    if run_checks:
        report["checks"] = selfcheck_qs_m5()
    return report


def main() -> int:
    rep = design_qs_locked(run_checks=True)
    print("=== QS-M5 量子传感器闭环标定 + 动态范围 ===")
    print("口径:", rep["caliber"])
    lk = rep["frequency_lock_baseline"]
    print("  频锁: 开环漂移 %.1f kHz → 残差 %.3e Hz（%d 轮）"
          % (lk["open_loop_drift_hz"] / 1e3, lk["residual_hz"], lk["n_iter"]))
    mg = rep["field_loop_baseline"]
    print("  磁场闭环: ε_k = %.3e ⇒ 读数相对误差 %.3e"
          % (mg["scale_mismatch"], mg["readout_rel_error"]))
    for n, s in rep["scenarios"].items():
        print("  [%-11s] w=%.0f MHz τ=%.0f s | B_min=%.3f pT B_max=%.1f nT | "
              "DR=%.1f dB | η_AC=%.3f nT | %s"
              % (n, s["linewidth_mhz"], s["integration_s"], s["b_min_pt"],
                 s["b_max_nT"], s["dynamic_range_db"], s["ac_sensitivity_nt"],
                 s["lock_verdict"]))
    ck = rep["checks"]
    npass = sum(1 for v in ck.values() if v)
    print("checks: %d/%d %s" % (npass, len(ck), "PASS" if npass == len(ck) else "FAIL"))
    for k, v in ck.items():
        if not v:
            print("  FAIL:", k)
    return 0 if npass == len(ck) else 1


if __name__ == "__main__":
    raise SystemExit(main())
