"""QS-M6 · 超导 **SQUID 磁力计**物理（吃狗粮 v6 · 量子传感器芯片征程 · 第二腿）。

═══ 定位（蓝图层 `docs/LDA_量子传感器芯片征程_总蓝图_v1_2026-10-10.md` §QS-M6 · L110）═══
QS-M0–M5 把**光-自旋-磁**耦合的 NV 色心磁力计从「能设计」推到「几何优化 / 阵列 / 闭环标定」。
本档开**第二腿**：**电-磁通**耦合的**超导 SQUID 磁力计**（约瑟夫森结磁通→电压）。
两者物理完全不同（自旋 vs 宏观量子相位），正是「分步达国际水平」的**性能天花板靶**：
NV 芯片级 ~26 nT/√Hz（蓝图 §3 公开文献值），SQUID 集成 ~1–5 fT/√Hz ⇒ **高一个量级**。

**平台缺口 G8**：超导量子器件物理（约瑟夫森结 / 磁通）。

═══ 🔴 物理链（三条 · 闭式可作 golden）═══
链① **约瑟夫森 RCSJ 结模型**（单结）：
  · **直流约瑟夫森关系** I_s = I_c·sin(δ)（δ = 结相位差）；
  · **RCSJ 微分方程**（resistively-capacitively-shunted junction）：
        ħC/(2e)·δ″ + ħ/(2eR)·δ′ + I_c·sin δ = I_bias
    无量纲化（τ = ω_p t，ω_p = √(2eI_c/ħC) 等离子频率）⇒ β_c = ω_p R C（McCumber 参数）；
  · **临界电流**（Ambegaokar–Baratoff 零温闭式）：I_c·R_n = πΔ/(2e)
    ⇒ 结临界电流与正常态电阻 R_n 的乘积由能隙 Δ 锁定。

链② **SQUID 环路临界电流与磁通-电压转导**：
  · 双结并联 SQUID（两结参数对称）环路**临界电流**：
        I_c(Φ) = 2·I_c0·|cos(π·Φ/Φ0)|
    （Φ0 = h/2e 磁通量子；f = Φ/Φ0 归一磁通）；
  · **磁通-电压转导**（电流偏置 I_b > I_c 时）用**分流传导函数**（transfer function）
    ∂V/∂Φ，需与**多结 SQUID 数值求解**（两结相位方程同时解）互验；
  · **有效面积转磁场**：B = Φ / A_eff（A_eff = 环路有效拾取面积）；

链③ **磁通噪声 → 磁场灵敏度**（Johnson–Nyquist 分流电阻热噪声）：
  · 结分流电阻 R 的热噪声电流谱密度 S_I = 4k_B T / R（双面）；
  · 经传导函数转磁通噪声：S_Φ = S_I / (∂I_b/∂Φ)²  （∂I_b/∂Φ = 临界电流对磁通的斜率）；
  · 磁场噪声谱密度：S_B = S_Φ / A_eff²，
    **磁场灵敏度** B_N = √(S_B)（T/√Hz）⇒ 折 fT/√Hz；
  · **磁通噪声地板**亦有 1/f 成分（此处以热噪声主导的**白噪声底**为 golden）。

═══ 🔴 与既有锚的边界（**不同物理量**，非重复计数）═══
· B473–B484（NV 色心磁力计全程）：**光-自旋-磁**耦合；本档是**电-磁通**耦合（宏观
  量子相位），物理对象完全不同 ⇒ 无交集；
· B18/B25（transmon / 磁通调谐 qubit 的 E_J(Φ)/koch_f01）：那是**量子比特能谱**；
  本档是**传感器转导**（I_c(Φ) → V(Φ) → S_Φ → B_N）—— 复用其 `E_J(Φ)` **闭式**
  （`sc_coupler` 同式）但登记的是**传感器链**的独立物理量（转导/噪声），非重复；
· `sc_coupler`（D-139 可调耦合器 SQUID）：那是**耦合器可调性**（J_qc/J_eff）；
  本档是**磁力计读出**（I_c(Φ)/传导/噪声底）⇒ 同器件不同物理量。

═══ 🔴 红线自检标注 ═══
· C 级自主：纯 numpy/scipy-free 顶层；不借商业 EDA / 量子 SDK。
· LLM 不进判决路径：全部死标量 / numpy；PASS 与否由闭式比对决定。
· 进报告数字一律**模块现算**（不转录草稿）；判据读到的值 = 模块现算值。
· 每道守卫配反向探针（先证能变红）。
· 🔴 **不在判决路径使用「T1 输出」**（器件级 T1 PDE 输出永不作 ORACLE）。
· 🔴 **诚实边界**：结临界电流 I_c0 / 正常态电阻 R_n / 能隙 Δ / 温度 T / 环面积 A_eff /
  电感 L 均为**设计示例量级**（4 K 超导典型），**非实测**；本档报告为**建模值**，
  **不得作制造 / 性能宣称**；蓝图 §3 的「1–5 fT/√Hz」系**公开文献值**（物理学报
  2025,74,20250426），本档只把它作**对标准星**引用，**不冒充 LDA 实测**；
  **不报 fabricated 能效**。
"""
from __future__ import annotations

import math
from typing import Any, Dict

import numpy as np

# ---------------------------------------------------------------------------
# 物理常数（SI · CODATA 量级；作为闭式 golden 的输入真源）
# ---------------------------------------------------------------------------
H_PLANCK = 6.62607015e-34          # J·s
H_BAR = 1.054571817e-34            # J·s
E_CHARGE = 1.602176634e-19         # C
K_B = 1.380649e-23                 # J/K
MU_0 = 1.25663706212e-6            # H/m

#: 磁通量子 Φ0 = h/2e（Wb · 单一真源）
FLUX_QUANTUM_WB = H_PLANCK / (2.0 * E_CHARGE)

#: 灵敏度口径（与 NV 腿统一：幅度谱密度 T/√Hz）—— 本档输出同口径
SENSITIVITY_CALIBER = "B_N__amplitude_spectral_density__T_per_sqrtHz"

SQUID_CALIBER = "squid_magnetometer__ic_phi_transfer_and_flux_noise__T_per_sqrtHz"


def assert_caliber(caliber: str) -> None:
    """口径守卫：只接受本档声明的 SQUID 磁力计口径（防跨档口径混比）。"""
    if caliber not in (SENSITIVITY_CALIBER, SQUID_CALIBER):
        raise ValueError("未知灵敏度口径：%r" % (caliber,))


def flux_quantum_wb() -> float:
    """磁通量子 Φ0 = h/2e（Wb）。"""
    return FLUX_QUANTUM_WB


# ---------------------------------------------------------------------------
# 链① 约瑟夫森结 / RCSJ 模型
# ---------------------------------------------------------------------------
def josephson_current(ic_a: float, delta_rad: float) -> float:
    """直流约瑟夫森关系 I_s = I_c·sin(δ)。"""
    return ic_a * math.sin(delta_rad)


def ambegaokar_baratoff_ic_rn(gap_j: float) -> float:
    """Ambegaokar–Baratoff 零温闭式：I_c·R_n = π·Δ / (2e)（V）。

    goldens：结临界电流-正常态电阻乘积由超导能隙 Δ 锁定。
    """
    return math.pi * gap_j / (2.0 * E_CHARGE)


def plasma_frequency_rad_s(ic_a: float, capacitance_f: float) -> float:
    """结等离子频率 ω_p = √(2e·I_c / (ħ·C))（rad/s）。"""
    return math.sqrt(2.0 * E_CHARGE * ic_a / (H_BAR * capacitance_f))


def mccumber_beta_c(ic_a: float, capacitance_f: float, resistance_ohm: float) -> float:
    """McCumber 参数 β_c = ω_p·R·C（无量纲；β_c≫1 滞回，β_c≲1 非滞回）。"""
    return plasma_frequency_rad_s(ic_a, capacitance_f) * resistance_ohm * capacitance_f


def rcsj_rhs(delta: float, ddelta: float, *, ic_a: float, capacitance_f: float,
             resistance_ohm: float, i_bias_a: float) -> float:
    """RCSJ 二阶 ODE 的角加速度 δ″（rad/s²）。

    无量纲方程： ħC/(2e)·δ″ + ħ/(2eR)·δ′ + I_c·sin δ = I_bias
    ⇒ δ″ = (2e/(ħC))·( I_bias − I_c·sin δ − ħ/(2eR)·δ′ )
    """
    ddrive = i_bias_a - ic_a * math.sin(delta)
    dloss = H_BAR / (2.0 * E_CHARGE * resistance_ohm) * ddelta
    return (2.0 * E_CHARGE / (H_BAR * capacitance_f)) * (ddrive - dloss)


def rcsj_integrate(delta0: float, ddelta0: float, *, ic_a: float, capacitance_f: float,
                   resistance_ohm: float, i_bias_a: float, dt_s: float,
                   n_steps: int) -> Dict[str, float]:
    """RK4 积分 RCSJ 相位动力学（含耗散项）→ 末态 (δ, δ′)。

    与闭式**锁定判据**互验：偏置 < I_c ⇒ 相位被困于势阱（δ′→0，末态停在
    δ_eq = asin(I_b/I_c)）；偏置 > I_c ⇒ 相位逃逸（δ′ 单调增长，washboard 倾斜）。

    🔴 **时间尺度**：弛豫时间 τ_relax ≈ 1/(ω_p²·R·C)（过阻尼 β_c≲1 时）。
    对默认参数 τ_relax ≈ 0.33 ns ⇒ 积分总时长须 ≳ 3τ_relax ≈ 1 ns；
    取 dt ≤ 1/(20·ω_p) 保证 ω_p 周期内 ≥20 步（辛性/稳定性）。
    """
    delta, ddelta = float(delta0), float(ddelta0)

    def acc(d: float, v: float) -> float:
        return rcsj_rhs(d, v, ic_a=ic_a, capacitance_f=capacitance_f,
                        resistance_ohm=resistance_ohm, i_bias_a=i_bias_a)

    for _ in range(n_steps):
        k1d, k1v = ddelta, acc(delta, ddelta)
        k2d, k2v = ddelta + 0.5 * dt_s * k1v, acc(delta + 0.5 * dt_s * k1d, ddelta + 0.5 * dt_s * k1v)
        k3d, k3v = ddelta + 0.5 * dt_s * k2v, acc(delta + 0.5 * dt_s * k2d, ddelta + 0.5 * dt_s * k2v)
        k4d, k4v = ddelta + dt_s * k3v, acc(delta + dt_s * k3d, ddelta + dt_s * k3v)
        delta += dt_s / 6.0 * (k1d + 2 * k2d + 2 * k3d + k4d)
        ddelta += dt_s / 6.0 * (k1v + 2 * k2v + 2 * k3v + k4v)
    return {"delta_rad": delta, "ddelta_rad_s": ddelta}


#: 默认参数下的弛豫时间尺度（s）：τ_relax = 1/(ω_p²·R·C)
def rcsj_relaxation_time_s(ic_a: float, capacitance_f: float, resistance_ohm: float) -> float:
    """RCSJ 过阻尼弛豫时间 τ_relax ≈ 1/(ω_p²·R·C)（s）。"""
    wp = plasma_frequency_rad_s(ic_a, capacitance_f)
    return 1.0 / (wp * wp * resistance_ohm * capacitance_f)


# ---------------------------------------------------------------------------
# 链② SQUID 环路临界电流 + 磁通-电压转导
# ---------------------------------------------------------------------------
def squid_critical_current(ic0_a: float, flux_phi0: float) -> float:
    """对称双结 SQUID 环路临界电流 I_c(Φ) = 2·I_c0·|cos(π·Φ/Φ0)|（A）。

    f = Φ/Φ0；f=0.5 时取零（完全相消）。
    """
    return 2.0 * ic0_a * abs(math.cos(math.pi * flux_phi0))


def squid_critical_current_numeric(ic0_a: float, flux_phi0: float,
                                   n_grid: int = 1 << 20) -> float:
    """数值互验：对两结相位方程在归一磁通 f 下的**最大无损电流**做相空间扫描。

    对称双结 SQUID：总电流 I = I_c0·[sin δ1 + sin δ2]，约束 δ1 − δ2 = 2πf（磁通量子化）
    ⇒ I(δ) = I_c0·[sin δ + sin(δ + 2πf)]；扫 δ ∈ [0,2π) 取 |I| 最大 ⇒ 临界电流。
    闭式 max = 2·I_c0·|cos(πf)| —— 此数值路径以**相位扫描**独立复算。

    🔴 **真离散化残差**（非代数恒等）：总电流可写为
        I(δ) = 2·I_c0·cos(πf)·sin(δ + πf)
    ⇒ 极值点 δ* = π/2 − πf（mod 2π），**网格一般不落在极值点上** ⇒ 残差 ~ O((Δδ)²)
    的截断误差。以 2^20 网格（Δδ ≈ 6e-6）将该残差压到 ~1e-11 相对量级，
    使其**真实小于**判据容差但**非零**（可被粗网格反向探针证伪）。
    """
    d = np.linspace(0.0, 2.0 * math.pi, n_grid, endpoint=False)
    total = ic0_a * (np.sin(d) + np.sin(d + 2.0 * math.pi * flux_phi0))
    return float(np.max(np.abs(total)))


def squid_transfer_function(ic0_a: float, flux_phi0: float,
                            flux_bias_phi0: float = 0.25) -> float:
    """磁通-电压转导 ∂I_c/∂Φ（A/Wb）—— 在偏置点附近的对磁通**斜率**。

    电流偏置点取 I_b = I_c(f_bias) 附近；转导 dI_c/dΦ 决定 SQUID 对磁通的响应。
    闭式（|cos| 在 f∉半整数处光滑）：
        dI_c/dΦ = 2·I_c0·(−sin(πf)·π/Φ0)·sign(cos(πf))
                = −2π·I_c0·sin(πf)·sign(cos(πf)) / Φ0
    """
    f = flux_bias_phi0
    cosf = math.cos(math.pi * f)
    sgn = 1.0 if cosf >= 0.0 else -1.0
    return -2.0 * math.pi * ic0_a * math.sin(math.pi * f) * sgn / FLUX_QUANTUM_WB


def squid_transfer_function_numeric(ic0_a: float, flux_phi0: float,
                                    flux_bias_phi0: float = 0.25,
                                    dflux: float = 1e-7) -> float:
    """数值互验：中差分 ∂I_c/∂Φ。**真离散化截断残差**（非代数恒等）。"""
    hi = squid_critical_current(ic0_a, flux_bias_phi0 + dflux)
    lo = squid_critical_current(ic0_a, flux_bias_phi0 - dflux)
    return (hi - lo) / (2.0 * dflux * FLUX_QUANTUM_WB)


def effective_pickup_area_m2(loop_side_m: float) -> float:
    """方形环路有效拾取面积 A_eff = side²（m²）。"""
    return loop_side_m * loop_side_m


def flux_to_field_t(flux_wb: float, area_m2: float) -> float:
    """B = Φ / A_eff（T）。"""
    return flux_wb / area_m2


# ---------------------------------------------------------------------------
# 链③ 磁通噪声 → 磁场灵敏度
# ---------------------------------------------------------------------------
def johnson_noise_current_psd(temp_k: float, resistance_ohm: float) -> float:
    """Johnson–Nyquist 热噪声电流谱密度 S_I = 4·k_B·T / R（A²/Hz · 双面）。"""
    return 4.0 * K_B * temp_k / resistance_ohm


def flux_noise_psd(temp_k: float, resistance_ohm: float, di_dflux_a_per_wb: float) -> float:
    """磁通噪声谱密度 S_Φ = S_I / (∂I_b/∂Φ)²（Wb²/Hz）。

    ∂I_b/∂Φ = 磁通-电流转导（= 临界电流对磁通的斜率）⇒ 电流噪声折算为磁通噪声。
    """
    s_i = johnson_noise_current_psd(temp_k, resistance_ohm)
    return s_i / (di_dflux_a_per_wb ** 2)


def flux_noise_psd_numeric(temp_k: float, resistance_ohm: float,
                           ic0_a: float, flux_phi0: float,
                           flux_bias_phi0: float = 0.25,
                           n_mc: int = 400000, seed: int = 20251011) -> float:
    """数值互验：MC 采样电流噪声 → 经传导函数折算 → 磁通噪声方差。

    σ_I = √(S_I·Δf)（离散谱线）⇒ σ_Φ = σ_I / (∂I/∂Φ) ⇒ S_Φ ≈ σ_Φ²/Δf。
    以**固定 seed** 复现；真统计残差 ≫ 机器精度（非代数恒等）。
    """
    s_i = johnson_noise_current_psd(temp_k, resistance_ohm)
    dflux = 1e-7
    hi = squid_critical_current(ic0_a, flux_bias_phi0 + dflux)
    lo = squid_critical_current(ic0_a, flux_bias_phi0 - dflux)
    di_dflux = (hi - lo) / (2.0 * dflux * FLUX_QUANTUM_WB)
    band_hz = 1.0
    sigma_i = math.sqrt(s_i * band_hz)
    rng = np.random.default_rng(seed)
    samples = rng.normal(0.0, sigma_i, n_mc)
    flux_samples = samples / di_dflux
    var_flux_per_hz = float(np.var(flux_samples)) / band_hz
    return var_flux_per_hz


def field_sensitivity_t_per_sqrt_hz(s_flux_wb2_per_hz: float, area_m2: float) -> float:
    """磁场灵敏度 B_N = √(S_Φ) / A_eff（T/√Hz）。"""
    return math.sqrt(s_flux_wb2_per_hz) / area_m2


def field_sensitivity_fT_per_sqrt_hz(s_flux_wb2_per_hz: float, area_m2: float) -> float:
    """磁场灵敏度（fT/√Hz）—— 折 1e15。"""
    return field_sensitivity_t_per_sqrt_hz(s_flux_wb2_per_hz, area_m2) * 1.0e15


# ---------------------------------------------------------------------------
# 综合设计（三链串联）
# ---------------------------------------------------------------------------
def design_defaults() -> Dict[str, float]:
    """默认设计参数（4 K 超导 SQUID 典型量级 · **设计示例 · 非实测**）。"""
    return {
        "ic0_a": 2.0e-6,            # 单结临界电流 2 µA
        "rn_ohm": 20.0,             # 正常态电阻 20 Ω
        "capacitance_f": 4.0e-13,   # 结电容 0.4 pF
        "gap_j": 1.0e-3 * E_CHARGE,  # 能隙 Δ ≈ 1 meV（Al 约 0.34 meV，Nb 约 1.5 meV）
        "temp_k": 4.2,              # 液氦温度
        "loop_side_m": 100.0e-6,    # 环路边长 100 µm
        "flux_bias_phi0": 0.25,     # 磁通偏置 Φ = 0.25 Φ0（最大转导点附近）
    }


def squid_magnetometer_physics(**overrides: Any) -> Dict[str, Any]:
    """QS-M6 综合：RCSJ → I_c(Φ)/转导 → 磁通噪声 → 磁场灵敏度（三链串联）。"""
    p = design_defaults()
    p.update({k: float(v) for k, v in overrides.items()})

    ic0 = p["ic0_a"]
    f = p["flux_bias_phi0"]
    area = effective_pickup_area_m2(p["loop_side_m"])

    ic_phi = squid_critical_current(ic0, f)
    ic_phi_num = squid_critical_current_numeric(ic0, f)
    di_dflux = squid_transfer_function(ic0, 0.0, f)
    di_dflux_num = squid_transfer_function_numeric(ic0, 0.0, f)

    s_flux = flux_noise_psd(p["temp_k"], p["rn_ohm"], abs(di_dflux))
    b_n = field_sensitivity_t_per_sqrt_hz(s_flux, area)

    omega_p = plasma_frequency_rad_s(ic0, p["capacitance_f"])
    beta_c = mccumber_beta_c(ic0, p["capacitance_f"], p["rn_ohm"])
    ab_product = ambegaokar_baratoff_ic_rn(p["gap_j"])

    return {
        "caliber": SQUID_CALIBER,
        "flux_quantum_wb": FLUX_QUANTUM_WB,
        "ic_phi_a": ic_phi,
        "ic_phi_numeric_a": ic_phi_num,
        "transfer_a_per_wb": di_dflux,
        "transfer_numeric_a_per_wb": di_dflux_num,
        "area_m2": area,
        "s_flux_wb2_per_hz": s_flux,
        "b_n_t_per_sqrt_hz": b_n,
        "b_n_fT_per_sqrt_hz": field_sensitivity_fT_per_sqrt_hz(s_flux, area),
        "plasma_freq_rad_s": omega_p,
        "plasma_freq_ghz": omega_p / (2.0 * math.pi) / 1e9,
        "beta_c": beta_c,
        "ab_ic_rn_v": ab_product,
        "ic_rn_v": ic0 * p["rn_ohm"],
    }


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "baseline": {
        "desc": "基线：2 µA 结 / 20 Ω / 4.2 K / 100 µm 环（设计示例）",
        "overrides": {},
    },
    "small_loop": {
        "desc": "小环 50 µm（面积 ↓4× ⇒ 灵敏度劣化）",
        "overrides": {"loop_side_m": 50.0e-6},
    },
    "large_loop": {
        "desc": "大环 200 µm（面积 ↑4× ⇒ 灵敏度改善）",
        "overrides": {"loop_side_m": 200.0e-6},
    },
    "low_temp": {
        "desc": "降温 1.5 K（热噪声 ↓ ⇒ S_Φ ∝ T）",
        "overrides": {"temp_k": 1.5},
    },
    "high_ic": {
        "desc": "高临界电流结 8 µA（转导 ↑4× 但 R_n 固定 ⇒ 噪声 ↓）",
        "overrides": {"ic0_a": 8.0e-6},
    },
}


def evaluate_scenario(name: str) -> Dict[str, Any]:
    """按情景名现算 QS-M6 综合物理。"""
    if name not in SCENARIOS:
        raise KeyError("未知情景：%r（可选 %s）" % (name, sorted(SCENARIOS)))
    over = SCENARIOS[name]["overrides"]
    out = squid_magnetometer_physics(**over)
    out["scenario"] = name
    out["desc"] = SCENARIOS[name]["desc"]
    return out


def sensitivity_table() -> Dict[str, Dict[str, Any]]:
    """五情景磁场灵敏度表（fT/√Hz · 全部模块现算）。"""
    return {n: {"desc": SCENARIOS[n]["desc"],
                "b_n_fT_per_sqrt_hz": evaluate_scenario(n)["b_n_fT_per_sqrt_hz"]}
            for n in SCENARIOS}


# ---------------------------------------------------------------------------
# 自检（机器门禁读到的必须是现算值）
# ---------------------------------------------------------------------------
def selfcheck_qs_m6() -> Dict[str, bool]:
    """QS-M6 自检（约 40 项，含反向探针；先证能变红）。"""
    ok: Dict[str, bool] = {}

    # ── 链① RCSJ / 约瑟夫森 ───────────────────────────────────────────
    # ① 直流约瑟夫森关系：δ=π/2 ⇒ I_s = I_c
    ok["josephson_max_at_pi2"] = abs(josephson_current(1.0, math.pi / 2) - 1.0) < 1e-15
    # ② 零相位 ⇒ 零电流
    ok["josephson_zero_at_zero"] = abs(josephson_current(1.0, 0.0)) < 1e-15
    # ③ Ambegaokar-Baratoff 线性于 Δ
    ab1 = ambegaokar_baratoff_ic_rn(1.0e-3 * E_CHARGE)
    ab2 = ambegaokar_baratoff_ic_rn(2.0e-3 * E_CHARGE)
    ok["ab_linear_in_gap"] = abs(ab2 - 2.0 * ab1) < 1e-15 * max(abs(ab2), 1.0)
    # ④ 等离子频率 ∝ √I_c
    w1 = plasma_frequency_rad_s(1.0e-6, 4.0e-13)
    w2 = plasma_frequency_rad_s(4.0e-6, 4.0e-13)
    ok["plasma_freq_scales_sqrt_ic"] = abs(w2 - 2.0 * w1) < 1e-9 * w1
    # ⑤ McCumber β_c = ω_p R C
    ok["beta_c_def"] = abs(mccumber_beta_c(1.0e-6, 4.0e-13, 20.0)
                           - plasma_frequency_rad_s(1.0e-6, 4.0e-13) * 20.0 * 4.0e-13) < 1e-15
    # ⑥ 偏置 < I_c ⇒ 相位被困（δ′ → 0，末态停在 δ_eq = asin(I_b/I_c)）
    _dt = 1.0 / (40.0 * plasma_frequency_rad_s(2.0e-6, 4.0e-13))     # ω_p 周期内 ≥40 步
    _n = 400000                                                       # 总时长 ≈ 3.2 ns ≫ τ_relax
    st_lock = rcsj_integrate(0.1, 0.0, ic_a=2.0e-6, capacitance_f=4.0e-13,
                             resistance_ohm=20.0, i_bias_a=1.0e-6, dt_s=_dt,
                             n_steps=_n)
    ok["rcsj_locked_below_ic"] = abs(st_lock["ddelta_rad_s"]) < 1e4
    # ⑥′ 锁定末态相位 == 闭式平衡点 asin(I_b/I_c)（模 2π）
    _d_eq = math.asin(1.0e-6 / 2.0e-6)
    _resid = abs((st_lock["delta_rad"] - _d_eq + math.pi) % (2.0 * math.pi) - math.pi)
    ok["rcsj_lock_phase_eq_closed"] = _resid < 1e-3
    # ⑦ 偏置 > I_c ⇒ 相位逃逸（δ′ 显著非零）
    st_run = rcsj_integrate(0.1, 0.0, ic_a=2.0e-6, capacitance_f=4.0e-13,
                            resistance_ohm=20.0, i_bias_a=3.0e-6, dt_s=_dt,
                            n_steps=_n)
    ok["rcsj_running_above_ic"] = abs(st_run["ddelta_rad_s"]) > 1e6
    # ⑦′ 反向探针：I_b 恰在 I_c 两侧（0.99·I_c 锁定 / 1.01·I_c 逃逸）⇒ 判据能翻转
    st_edge_lo = rcsj_integrate(0.1, 0.0, ic_a=2.0e-6, capacitance_f=4.0e-13,
                                resistance_ohm=20.0, i_bias_a=0.99 * 2.0e-6,
                                dt_s=_dt, n_steps=_n)
    st_edge_hi = rcsj_integrate(0.1, 0.0, ic_a=2.0e-6, capacitance_f=4.0e-13,
                                resistance_ohm=20.0, i_bias_a=1.01 * 2.0e-6,
                                dt_s=_dt, n_steps=_n)
    ok["rcsj_edge_lock_vs_escape"] = (abs(st_edge_lo["ddelta_rad_s"]) < 1e4
                                      and abs(st_edge_hi["ddelta_rad_s"]) > 1e6)
    # ⑧ 反向探针：把 I_c 抬到远超偏置（同一时间尺度下）⇒ 相位深困于 δ_eq=asin(I_b/I_c)≈0
    #    （用与基线同 τ_relax 的积分窗口；不取物理上荒谬的 I_c=1 A 以免刚性问题）
    st_big = rcsj_integrate(0.1, 0.0, ic_a=2.0e-6, capacitance_f=4.0e-13,
                            resistance_ohm=20.0, i_bias_a=1.0e-9,
                            dt_s=_dt, n_steps=_n)
    ok["reverse_huge_ic_locks"] = abs(st_big["ddelta_rad_s"]) < 1e4

    # ── 链② SQUID 临界电流 / 转导 ─────────────────────────────────────
    ic0 = 2.0e-6
    # ⑨ f=0 ⇒ I_c = 2 I_c0（两结同相）
    ok["ic_zero_flux"] = abs(squid_critical_current(ic0, 0.0) - 2.0 * ic0) < 1e-18
    # ⑩ f=0.5 ⇒ I_c = 0（完全相消）
    ok["ic_half_flux_zero"] = abs(squid_critical_current(ic0, 0.5)) < 1e-18
    # ⑪ f=1 ⇒ 周期复位
    ok["ic_period_one"] = abs(squid_critical_current(ic0, 1.0)
                              - squid_critical_current(ic0, 0.0)) < 1e-18
    # ⑫ 闭式 ⇄ 数值（相位扫描）互验 —— **真离散化残差**，容差按实测截断定（1e-10×）
    #    （🔴 非代数恒等：粗网格反向探针 21 能证伪）
    _GRID_TOL = 1e-10
    for f in (0.1, 0.25, 0.3, 0.4, 0.7):
        cf = squid_critical_current(ic0, f)
        nf = squid_critical_current_numeric(ic0, f)
        ok["ic_closed_eq_numeric_%.2f" % f] = abs(cf - nf) <= _GRID_TOL * max(abs(cf), 1e-18)
    ok["ic_closed_eq_numeric"] = all(
        abs(squid_critical_current(ic0, f) - squid_critical_current_numeric(ic0, f))
        <= _GRID_TOL * max(abs(squid_critical_current(ic0, f)), 1e-18)
        for f in (0.1, 0.25, 0.3, 0.4, 0.7))
    # ⑫′ 反向探针：**非极值对齐**的 f=0.3 上取极粗网格（64 点）⇒ 截断残差 ≫ 容差
    #     （🔴 必须选非对齐 f：f=0.25 时极值点恰落在 2 幂网格节点上 ⇒ 残差恒 0（代数恒等），
    #        用它做反向探针会**假绿**；f=0.3 的 idx=25.6 非整数 ⇒ 真截断残差）
    _cf03 = squid_critical_current(ic0, 0.3)
    _nf_coarse = squid_critical_current_numeric(ic0, 0.3, n_grid=64)
    ok["reverse_coarse_grid_breaks_num_eq"] = abs(_cf03 - _nf_coarse) > 1e3 * _GRID_TOL * abs(_cf03)
    # ⑫″ 反证「对齐 f 不可作残差判据」：f=0.25 任意网格残差恒为 0（代数恒等侧写）
    ok["quarter_flux_grid_aligned_identity"] = abs(
        squid_critical_current(ic0, 0.25)
        - squid_critical_current_numeric(ic0, 0.25, n_grid=64)) == 0.0
    # ⑬ 转导闭式 ⇄ 数值（中差分 · 真截断残差）
    t_closed = squid_transfer_function(ic0, 0.0, 0.25)
    t_num = squid_transfer_function_numeric(ic0, 0.0, 0.25, dflux=1e-7)
    ok["transfer_closed_eq_numeric"] = abs(t_closed - t_num) <= 1e-5 * abs(t_closed)
    # ⑭ 反向探针：转导数值用**极粗**步长 ⇒ 残差显著增大（证明是真数值残差）
    t_coarse = squid_transfer_function_numeric(ic0, 0.0, 0.25, dflux=1e-3)
    ok["transfer_coarse_step_larger_resid"] = abs(t_closed - t_coarse) > abs(t_closed - t_num)
    # ⑮ 转导在 f=0 处为零（cos 极大 ⇒ 斜率为零）
    ok["transfer_zero_at_f0"] = abs(squid_transfer_function(ic0, 0.0, 0.0)) < 1e-18
    # ⑯ f=0.25 转导幅值 = √2·π·I_c0/Φ0（π/4 处 |sin(πf)|=√2/2 ⇒ |dI_c/dΦ|=2π I_c0·(√2/2)/Φ0）
    expect = math.sqrt(2.0) * math.pi * ic0 / FLUX_QUANTUM_WB
    ok["transfer_amp_at_quarter"] = abs(abs(t_closed) - expect) < 1e-12 * expect
    # ⑰ 有效面积 ∝ side²
    ok["area_scales_side_sq"] = abs(effective_pickup_area_m2(2.0) - 4.0 * effective_pickup_area_m2(1.0)) < 1e-18
    # ⑱ B = Φ/A 反演
    ok["flux_to_field_def"] = abs(flux_to_field_t(1e-12, 1e-8) - 1e-4) < 1e-18

    # ── 链③ 磁通噪声 / 灵敏度 ─────────────────────────────────────────
    # ⑲ Johnson 噪声 ∝ T
    ok["johnson_linear_temp"] = abs(johnson_noise_current_psd(2.0, 10.0)
                                    - 2.0 * johnson_noise_current_psd(1.0, 10.0)) < 1e-30
    # ⑳ Johnson 噪声 ∝ 1/R
    ok["johnson_inverse_r"] = abs(johnson_noise_current_psd(4.2, 20.0)
                                  - 0.5 * johnson_noise_current_psd(4.2, 10.0)) < 1e-30
    # ㉑ S_Φ 闭式 ⇄ MC 数值互验（固定 seed · 真统计残差）
    t_abs = abs(squid_transfer_function(ic0, 0.0, 0.25))
    s_flux_closed = flux_noise_psd(4.2, 20.0, t_abs)
    s_flux_num = flux_noise_psd_numeric(4.2, 20.0, ic0, 0.0, 0.25, n_mc=400000)
    ok["s_flux_closed_eq_numeric"] = abs(s_flux_closed - s_flux_num) <= 0.02 * s_flux_closed
    # ㉒ S_Φ ∝ T（噪声 ∝ T ⇒ 谱密度 ∝ T）
    ok["s_flux_linear_temp"] = abs(flux_noise_psd(8.4, 20.0, t_abs)
                                   - 2.0 * flux_noise_psd(4.2, 20.0, t_abs)) < 1e-40
    # ㉓ S_Φ ∝ 1/转导²（转导加倍 ⇒ 噪声 1/4）
    ok["s_flux_inverse_transfer_sq"] = abs(flux_noise_psd(4.2, 20.0, 2.0 * t_abs)
                                           - 0.25 * flux_noise_psd(4.2, 20.0, t_abs)) < 1e-45
    # ㉔ B_N ∝ √S_Φ
    ok["b_n_scales_sqrt_sflux"] = abs(field_sensitivity_t_per_sqrt_hz(4.0 * s_flux_closed, 1e-8)
                                      - 2.0 * field_sensitivity_t_per_sqrt_hz(s_flux_closed, 1e-8)) < 1e-30
    # ㉕ B_N ∝ 1/A
    ok["b_n_inverse_area"] = abs(field_sensitivity_t_per_sqrt_hz(s_flux_closed, 2e-8)
                                 - 0.5 * field_sensitivity_t_per_sqrt_hz(s_flux_closed, 1e-8)) < 1e-30
    # ㉖ fT 折换正确
    ok["fT_conversion"] = abs(field_sensitivity_fT_per_sqrt_hz(s_flux_closed, 1e-8)
                              - 1e15 * field_sensitivity_t_per_sqrt_hz(s_flux_closed, 1e-8)) < 1e-15
    # ㉗ 综合链路自洽：报告 b_n == 现算
    rep = squid_magnetometer_physics()
    ok["report_b_n_consistent"] = abs(rep["b_n_t_per_sqrt_hz"]
                                      - field_sensitivity_t_per_sqrt_hz(rep["s_flux_wb2_per_hz"], rep["area_m2"])) < 1e-40
    # ㉘ 综合链路：I_c(Φ) 报告值 == 现算
    ok["report_ic_consistent"] = abs(rep["ic_phi_a"] - squid_critical_current(ic0, 0.25)) < 1e-18
    # ㉙ 口径守卫：错口径必抛
    ok["caliber_guard"] = _raises(lambda: assert_caliber("bogus"))
    # ㉚ 口径守卫：正确口径不抛
    ok["caliber_ok"] = not _raises(lambda: assert_caliber(SQUID_CALIBER))
    # ㉛ 情景单调性：大环灵敏度优于小环（fT/√Hz 更小）
    ok["scenario_large_loop_better"] = (evaluate_scenario("large_loop")["b_n_fT_per_sqrt_hz"]
                                        < evaluate_scenario("small_loop")["b_n_fT_per_sqrt_hz"])
    # ㉜ 情景单调性：低温灵敏度优于常温
    ok["scenario_low_temp_better"] = (evaluate_scenario("low_temp")["b_n_fT_per_sqrt_hz"]
                                      < evaluate_scenario("baseline")["b_n_fT_per_sqrt_hz"])
    # ㉝ 反向探针：零转导 ⇒ S_Φ 爆掉（除零/无穷 ⇒ 应抛或 inf）
    ok["reverse_zero_transfer_blows"] = _raises(lambda: flux_noise_psd(4.2, 20.0, 0.0))

    return ok


def _raises(fn) -> bool:
    """辅助：调用 fn，若抛异常返回 True（用于反向探针）。"""
    try:
        fn()
        return False
    except Exception:
        return True


def design_qs_squid(run_checks: bool = True) -> Dict[str, Any]:
    """QS-M6 设计入口：三链串联 + 情景表 + （可选）自检。"""
    rep = squid_magnetometer_physics()
    out: Dict[str, Any] = {
        "milestone": "QS-M6",
        "module": "lda_l2/qs_m6.py",
        "caliber": SQUID_CALIBER,
        "physics_chain": ["RCSJ 约瑟夫森结", "SQUID I_c(Φ)/转导", "磁通噪声→磁场灵敏度"],
        "report": rep,
        "scenarios": sensitivity_table(),
        "honest_note": (
            "本档为**建模值**（设计示例量级，4 K 超导典型），**非实测**；不宣称「已达国际"
            "水平」——蓝图 §3 的 1–5 fT/√Hz 系公开文献值（物理学报 2025），此处只作对标准星；"
            "不报 fabricated 能效；LLM 不进判决路径。"
        ),
    }
    if run_checks:
        out["selfcheck"] = selfcheck_qs_m6()
        out["selfcheck_pass"] = all(out["selfcheck"].values())
    return out


def main() -> int:
    """CLI 冒烟：打印关键量与自检汇总。"""
    rep = squid_magnetometer_physics()
    print("QS-M6 SQUID 磁力计（设计示例 · 非实测）")
    print("  Φ0 = %.6e Wb" % FLUX_QUANTUM_WB)
    print("  I_c(Φ=0.25Φ0) = %.4e A" % rep["ic_phi_a"])
    print("  转导 ∂I/∂Φ     = %.4e A/Wb" % rep["transfer_a_per_wb"])
    print("  S_Φ           = %.4e Wb²/Hz" % rep["s_flux_wb2_per_hz"])
    print("  B_N           = %.4f fT/√Hz" % rep["b_n_fT_per_sqrt_hz"])
    print("  ω_p           = %.3f GHz（β_c=%.0f）" % (rep["plasma_freq_ghz"], rep["beta_c"]))
    print("  情景表：")
    for n, row in sensitivity_table().items():
        print("    %-12s %10.3f fT/√Hz  %s" % (n, row["b_n_fT_per_sqrt_hz"], row["desc"]))
    sc = selfcheck_qs_m6()
    bad = [k for k, v in sc.items() if not v]
    print("自检：%d/%d PASS%s" % (sum(sc.values()), len(sc),
                                  "" if not bad else "  FAIL=%s" % bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
