"""QS-M3c · 腔 QED 物理链（cavity Q / V_eff / g · 吃狗粮 v3c · 量子传感器芯片征程）。

═══ 定位（蓝图层 `docs/LDA_量子传感器芯片征程_总蓝图_v1_2026-10-10.md` §QS-M3 · 链④引申）═══
QS-M3 链④ 把 Purcell 因子 **F_P = 4g²/(κγ₁)** 当 design-magnitude 用，但腔几何
（品质因子 Q、有效模体积 V_eff、单光子耦合 g）从未被**独立建模**——QS-M3 定稿
「未竟项」明列「腔的真实几何（光子晶体腔 / 微盘）未建模」。本档 = 把 F_P 的
**三个输入量 (Q, V_eff, g)** 拆成**腔 QED 物理链**，逐量给出「闭式 golden ⇄ 数值
候选 方法学独立」的可证伪锚（B494 / B495 / B496）。

═══ 🔴 物理链（三条 · 闭式全部可作 golden）═══
链① **腔品质因子 Q = ω/κ**：
    · 腔能量 Ring-down：dU/dt = −κU（κ = 能量衰减率 = 角频率线宽）；
    · 闭式 **Q = ω/κ**（ω = 2πc/λ 为谐振角频率）；
    · 数值候选：**RK4 时间推进能量衰减** → 取 U(T)/U₀ = e^(−κT) → 数值反解
      κ_cand = −ln(U(T)/U₀)/T → Q_cand = ω/κ_cand（方法学独立：解析除式 vs
      数值 ODE 反解）。
链② **有效模体积 V_eff = ∫ε|E|²dV / max(ε|E|²)**：
    · 单波腹腔模包络 E(x)=E₀·(1−4x²/a²)（x∈[−a/2, a/2]，中心单极大、边界归零，
      腔长 a，横向截面 A 均匀）⇒ **闭式 V_eff = A·∫(1−4x²/a²)²dx / 1 = A·8a/15**
      （∫_{-a/2}^{a/2}(1−4x²/a²)²dx = 8a/15，纯算术闭式）；
    · 数值候选：**中点求积** ∫_{-a/2}^{a/2}(1−4x²/a²)²dx（方法学独立：解析积分 vs 数值积分；
      被积函数为四次非多项式 ⇒ 中点非精确 ⇒ 真 O(h²) 残差）。
链③ **单光子耦合 g = (μ/ħ)·√(ħω/(ε·V_eff))**：
    · 单光子能量 U = ½ħω = ½ε∫|E|²dV ⇒ 场幅 **E₀ = √(ħω/(ε·V_eff))**，
      g = μ·E₀/ħ（μ = 跃迁偶极矩）；
    · 数值候选：**数值积分 ∫|E|²dV**（⇒ 数值 V_eff）⇒ E₀ ⇒ g（方法学独立）。

═══ 🔴 与既有锚的边界（**不同物理量**，非重复计数）═══
· **B18**（谐振腔 Purcell 因子 F_P = 4g²/(κγ₁)）：本档的 Q/V_eff/g 是 **F_P 的
  输入量**（Q/V/g 决定 F_P，但 Q/V/g 本身 ≠ F_P）—— 同 QS-M3 链④「Purcell 物理
  已覆盖、不另登 B18」的口径相反：本档登的是**腔自身属性**（B18 登的是 Purcell
  增强因子这种**组合标量**）⇒ 物理对象不同，记新锚（先例：B491 自由进动极化 vs
  B475 回波相位方差 —— 同物理域不同标量即分立）。
· B473–B490（腿 A NV / 腿 B SQUID）：固体自旋 / 超导磁通，无腔 QED 量。
· B476–B477（QS-M3 几何优化）：色心深度 / NA 收集效率，无腔 QED 量。
· B491–B493（QS-M9 OPM）：碱金属气室光-自旋，无腔 QED 量。

═══ 🔴 真实物理整合（诚实口径 · 模块内自洽）═══
· **finesse ↔ Q**：ℱ = FSR/Δν，FSR = c/(2n a)，Δν = κ/(2π) ⇒ ℱ = Q·λ/(2na)；
· **cooperativity 两口径（🔴 K1 结算 · 断口 G-K-2 · 二者**不是**同一个量）**：
  `g_form` `C_g = 4g²/(κγ_rad)`（**协同度** · 语义由第三参数决定：传总线宽 ⇒ 标准协同度）·
  `qv_form` `C_qv = F_P·(γ_rad/γ₁)`（**非协同度** · Purcell 因子 × 分支比）；
  🔴 **精确闭式比值** `C_g/C_qv = 2n·γ₁/γ_rad`（本仓约定 γ_rad = 真空 Einstein-A =
  ω³μ²/(3πε₀ħc³)、腔模 ε = ε₀n² ⇒ `C_g = 2n·F_P`，为两因子的乘积）。🔴 **旧版本行曾断言
  `4g²/(κγ_rad) ≡ (3λ³Q/4π²V)(γ_rad/γ₁)` —— 该等式不成立**（实测差 `2n·γ₁/γ_rad`，
  旧门禁只查 `C_g/F_P = 2n` ⇒ 无判据拦截）⇒ 见 `cooperativity_calibers()` 与
  `run_k1_cooperativity_settlement_smoke`；
· **Purcell FOM**：F_P = (3/4π²)(λ/n)³(Q/V)（标准腔 QED）。

═══ 🔴 红线自检标注 ═══
· C 级自主：纯 `math`（数值候选 RK4 / 中点求积均不借 numpy / scipy / 量子 SDK）。
· LLM 不进判决路径：全部死标量；PASS 与否由闭式比对决定。
· 进报告数字一律**模块现算**（不转录草稿）；判据读到的值 = 模块现算值。
· 每道守卫配反向探针（先证能变红）。
· 🔴 **诚实边界**：ω/κ/a/A/μ/n 均为**设计示例量级**（金刚石微盘腔 telecom 典型），
  **非任何实测 PDK**；本档报告为**建模值**，**不得作制造 / 性能宣称**、**不报
  fabricated 能效**；QS-M3 的 F_P 组合标量（B18）与本档的 Q/V/g 输入量**对照而不混**。
"""
from __future__ import annotations

import math
from typing import Any, Dict

# ---------------------------------------------------------------------------
# 物理常数（SI · CODATA 量级；作为闭式 golden 的输入真源 · 与 `_batch_qs_m3c_numeric` 同源）
# ---------------------------------------------------------------------------
HBAR = 1.054571817e-34           # J·s
C_LIGHT = 299792458.0            # m/s
EPSILON_0 = 8.8541878128e-12     # F/m

#: 灵敏度口径（与 QS-M0/M3/M6/M7/M9 统一：幅度谱密度 T/√Hz）
SENSITIVITY_CALIBER = "B_N__amplitude_spectral_density__T_per_sqrtHz"
QS_M3C_CALIBER = "cavity_qed__Q_V_eff_g_physical_chain__unitless_or_SI"


def assert_caliber(caliber: str) -> None:
    """口径守卫（禁与线宽受限 LOD / 单次测量不确定度混比）。"""
    if caliber not in (SENSITIVITY_CALIBER, QS_M3C_CALIBER):
        raise ValueError("未知口径：%r" % (caliber,))


# ---------------------------------------------------------------------------
# 链① 腔品质因子 Q = ω/κ（RK4 能量衰减 ⇒ 数值反解 κ ⇒ Q）
# ---------------------------------------------------------------------------
def cavity_q_factor(omega: float, kappa: float) -> float:
    """闭式 **Q = ω/κ**（无量纲 · 腔 QED 品质因子）。"""
    if kappa <= 0.0:
        raise ValueError("kappa 必须 > 0")
    if omega <= 0.0:
        raise ValueError("omega 必须 > 0")
    return float(omega / kappa)


def _energy_decay_rk4(kappa: float, t_observe: float, n_steps: int) -> float:
    """RK4 数值推进 dU/dt = −κU（U₀=1），返回 U(T)（方法学独立于闭式 e^(−κT)）。"""
    if kappa <= 0.0 or t_observe <= 0.0:
        raise ValueError("kappa / t_observe 必须 > 0")
    if n_steps < 4:
        raise ValueError("n_steps 必须 ≥ 4")
    h = t_observe / int(n_steps)
    u = 1.0
    for _ in range(int(n_steps)):
        k1 = -kappa * u
        k2 = -kappa * (u + 0.5 * h * k1)
        k3 = -kappa * (u + 0.5 * h * k2)
        k4 = -kappa * (u + h * k3)
        u += (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(u)


def cavity_q_factor_numeric(omega: float, kappa: float, t_observe: float = 8.22e-12,
                            n_steps: int = 64) -> float:
    """candidate：**RK4 时间推进能量衰减** → 取 U(T) ⇒ 反解 κ_cand = −ln(U(T))/T
    → Q_cand = ω/κ_cand（方法学独立）。

    🔴 残差来源 = **RK4 时间离散化截断**（实测 O(h⁴)，比值 ~16×/倍增）⇒ **非**代数恒等。
    """
    u = _energy_decay_rk4(kappa, t_observe, n_steps)
    if u <= 0.0:
        raise ValueError("RK4 数值衰减越界（U(T) 必须 > 0）")
    kappa_cand = -math.log(u) / t_observe
    return float(omega / kappa_cand)


# ---------------------------------------------------------------------------
# 链② 有效模体积 V_eff（驻波 sin² 积分 · 闭式 ⇄ 中点求积）
# ---------------------------------------------------------------------------
def mode_volume_closed(a: float, A: float) -> float:
    """闭式 **V_eff = A·8a/15**（m³ · 单波腹腔模包络 E(x)=E₀(1−4x²/a²) 可分离模式）。

    🔴 推导：∫_{-a/2}^{a/2}(1−4x²/a²)²dx = 8a/15（令 u=2x/a ⇒ (a/2)∫_{-1}^{1}(1−u²)²du
      = (a/2)(16/15) = 8a/15）；max|E|² = E₀²（中心 x=0）⇒ V_eff = A·8a/15。
    """
    if a <= 0.0 or A <= 0.0:
        raise ValueError("a / A 必须 > 0")
    return float(A * 8.0 * a / 15.0)


def mode_volume_numeric(a: float, A: float, n_seg: int = 256) -> float:
    """candidate：**中点求积** ∫_{-a/2}^{a/2}(1−4x²/a²)²dx（方法学独立）。

    🔴 残差来源 = **中点求积截断**（实测 O(h²)，比值 ~4×/倍增；被积函数为四次非多项式
    ⇒ 中点非精确（仅对 ≤3 次多项式精确）⇒ 真数值残差，非「同式异写」/ 非机器零残差）。
    """
    if a <= 0.0 or A <= 0.0:
        raise ValueError("a / A 必须 > 0")
    if n_seg < 4:
        raise ValueError("n_seg 必须 ≥ 4")
    h = a / int(n_seg)
    acc = 0.0
    for i in range(int(n_seg)):
        x = -0.5 * a + (i + 0.5) * h
        u = 1.0 - 4.0 * x * x / (a * a)
        acc += u * u * h
    return float(A * acc)


# ---------------------------------------------------------------------------
# 链③ 单光子耦合 g = (μ/ħ)·√(ħω/(ε·V_eff))（闭式 ⇄ 数值场能）
# ---------------------------------------------------------------------------
def single_photon_coupling_closed(mu: float, omega: float, eps: float,
                                  a: float, A: float) -> float:
    """闭式 **g = (μ/ħ)·√(ħω/(ε·V_eff))**（Hz · 单光子 Rabi 频率）。

    🔴 V_eff = A·a/2（闭式）；E₀ = √(ħω/(ε·V_eff))（单光子场幅）。
    """
    if mu <= 0.0 or omega <= 0.0 or eps <= 0.0:
        raise ValueError("mu / omega / eps 必须 > 0")
    v_eff = mode_volume_closed(a, A)
    e0 = math.sqrt(omega * HBAR / (eps * v_eff))
    return float(mu * e0 / HBAR)


def single_photon_coupling_numeric(mu: float, omega: float, eps: float,
                                   a: float, A: float, n_seg: int = 256) -> float:
    """candidate：**数值积分 ∫|E|²dV**（⇒ 数值 V_eff）⇒ E₀ ⇒ g（方法学独立）。

    🔴 残差来源 = **中点求积截断**（与 B495 同源 O(h²)）；V_eff 数值误差以 ½ 比例
    传入 g（g ∝ V_eff^(−1/2)）。
    """
    if mu <= 0.0 or omega <= 0.0 or eps <= 0.0:
        raise ValueError("mu / omega / eps 必须 > 0")
    v_eff_num = mode_volume_numeric(a, A, n_seg)
    if v_eff_num <= 0.0:
        raise ValueError("数值 V_eff 必须 > 0")
    e0 = math.sqrt(omega * HBAR / (eps * v_eff_num))
    return float(mu * e0 / HBAR)


# ---------------------------------------------------------------------------
# 真实物理整合（诚实口径 · 模块内自洽 · 不宣示跨约定恒等式）
# ---------------------------------------------------------------------------
def cavity_finesse_from_qv(Q: float, lambda0: float, n_r: float, a: float) -> float:
    """finesse ℱ = Q·λ/(2na)（由 FSR/Δν 推出 · 闭式算术）。"""
    if Q <= 0.0 or lambda0 <= 0.0 or n_r <= 0.0 or a <= 0.0:
        raise ValueError("Q / λ / n / a 必须 > 0")
    return float(Q * lambda0 / (2.0 * n_r * a))


def cavity_finesse_from_defs(Q: float, lambda0: float, n_r: float, a: float) -> float:
    """finesse ℱ = FSR/Δν（FSR = c/(2na)，Δν = κ/(2π) = ω/(2πQ)）· 与上式应逐位一致。"""
    if Q <= 0.0 or lambda0 <= 0.0 or n_r <= 0.0 or a <= 0.0:
        raise ValueError("Q / λ / n / a 必须 > 0")
    fsr = C_LIGHT / (2.0 * n_r * a)
    delta_nu = (2.0 * math.pi * C_LIGHT / lambda0) / (2.0 * math.pi * Q)
    return float(fsr / delta_nu)


def radiative_rate_gamma_rad(mu: float, omega: float) -> float:
    """真空 Einstein-A（自发辐射率 γ_rad）：γ_rad = ω³μ²/(3πε₀ħc³)（1/s）。"""
    if mu <= 0.0 or omega <= 0.0:
        raise ValueError("mu / omega 必须 > 0")
    return float(omega ** 3 * mu ** 2 / (3.0 * math.pi * EPSILON_0 * HBAR * C_LIGHT ** 3))


def purcell_factor_qv(Q: float, lambda0: float, n_r: float, v_eff: float) -> float:
    """Purcell FOM（标准腔 QED）：F_P = (3/4π²)(λ/n)³·(Q/V)。"""
    if Q <= 0.0 or lambda0 <= 0.0 or n_r <= 0.0 or v_eff <= 0.0:
        raise ValueError("Q / λ / n / V 必须 > 0")
    return float((3.0 / (4.0 * math.pi ** 2)) * (lambda0 / n_r) ** 3 * (Q / v_eff))


def cooperativity_from_g(g: float, kappa: float, gamma_rad: float) -> float:
    """cooperativity（g 形式）：C = 4g²/(κγ_rad)。"""
    if kappa <= 0.0 or gamma_rad <= 0.0:
        raise ValueError("kappa / gamma_rad 必须 > 0")
    return float(4.0 * g ** 2 / (kappa * gamma_rad))


def cooperativity_from_qv(Q: float, lambda0: float, n_r: float, v_eff: float,
                         gamma_rad: float, gamma1: float) -> float:
    """cooperativity（Q/V 形式）：C = (3λ³Q/4π²V)(γ_rad/γ₁)。"""
    if gamma1 <= 0.0:
        raise ValueError("gamma1 必须 > 0")
    return float(purcell_factor_qv(Q, lambda0, n_r, v_eff)
                 * (gamma_rad / gamma1))


# ---------------------------------------------------------------------------
# 🔴 K 征程 K1 · 断口 G-K-2 结算：协同度两口径**并报**（不得选择性披露）
# ---------------------------------------------------------------------------
#: 协同度口径登记（两口径**并存但物理量不同** · 比值有精确闭式）：
#:   `g_form`  `C_g  = 4g²/(κ·γ)`    —— **协同度**（标准形式；**语义由第三参数决定**：
#:                                      传**总线宽** γ₁ ⇒ 标准协同度；传辐射率 γ_rad ⇒ 相对辐射通道）
#:   `qv_form` `C_qv = F_P·(γ_rad/γ₁)` —— **不是协同度**（Purcell 因子 × 分支比；
#:                                      未计 Purcell 对分母本身的增强 ⇒ 亦不可读作 β）
#: 🔴 **闭式比值（机器精度级实测）**：`C_g/C_qv = 2n · γ₁/γ_rad`
#:   —— 两个因子的乘积：① 约定因子 **2n**（`C_g = 2n·F_P` · 本仓实现自洽 · 见
#:   `run_qs_m3c_smoke` F2）② 分母口径差 **γ₁/γ_rad**（总线宽 vs 辐射通道）。
#: 🔴 **断口本体（J5 章程 R3b 登记 · 本档结算）**：模块旧注释与账本 note 曾断言
#:   `4g²/(κγ_rad) ≡ (3λ³Q/4π²V)(γ_rad/γ₁)` —— **该等式不成立**（实测差
#:   `2n·γ₁/γ_rad` 倍），且旧门禁只查 `C_g/F_P = 2n` ⇒ **无判据拦截**（假自洽）。
COOPERATIVITY_CALIBERS = ("g_form", "qv_form")

#: 主账口径（**被消费面**（`qnet_transducer` ⇒ B522 golden）用的那一条）
COOPERATIVITY_MAIN_ACCOUNT = "g_form"


def cooperativity_calibers(**overrides: Any) -> Dict[str, Any]:
    """**协同度两口径并报**（K1 结算面 · 机读字段强制 · 缺字段即红）。

    返回**同一次调用**下的两个口径值 + **精确闭式比值** + **恒等式残差** +
    「哪一条才是协同度」的判定字段。🔴 并报是硬要求：调用方不得只取其一。

    🔴 **为什么 g 口径为主账**：
      ① 它是**被消费的口径**（`lda_l2/qnet_transducer.cooperativity()` 复用 ⇒ B522 的
         `C=25` 与其 golden 依赖它）；
      ② 其函数形式 `4x²/(yz)` 即**标准协同度形式**，语义由第三参数（应为**总**衰减率）决定；
      ③ Q/V 口径 `F_P·(γ_rad/γ₁)` 经分析**既非协同度亦非有效 β**（用 `F_Pγ_rad/γ₁` 当 β
         会 >1 —— 它忽略了 Purcell 对**分母本身**的增强）⇒ 不能作主账。
    """
    ph = cavity_qed_physics(**overrides)
    d = design_defaults()
    d.update({k: float(v) for k, v in overrides.items()})

    n_r = d["n_r"]
    gr = ph["gamma_rad_s1"]
    g1 = d["gamma1_s1"]
    g = ph["g_Hz"]
    kappa = ph["kappa_s1"]
    fp = ph["purcell_F_P"]
    c_g = ph["cooperativity_g_form"]
    c_qv = ph["cooperativity_qv_form"]

    ratio = c_g / c_qv
    ratio_closed = 2.0 * n_r * g1 / gr
    id_2n = 2.0 * n_r * fp                       # C_g = 2n·F_P（本仓实现自洽）

    return {
        "caliber": QS_M3C_CALIBER,
        "n_r": n_r,
        "gamma_rad_s1": gr,
        "gamma1_s1": g1,
        "purcell_F_P": fp,
        "g_form": c_g,
        "qv_form": c_qv,
        "ratio_g_over_qv": ratio,
        "ratio_closed_form": ratio_closed,
        "ratio_closed_form_expr": "2n*g1/gamma_rad",
        "ratio_closed_form_resid_rel": abs(ratio - ratio_closed) / ratio_closed,
        "identity_2n_value": id_2n,
        "identity_2n_resid_rel": abs(c_g - id_2n) / id_2n,
        "cooperativity_std_total_linewidth": 4.0 * g * g / (kappa * g1),
        "is_cooperativity": {"g_form": True, "qv_form": False},
        "g_form_denominator": "gamma (third argument; pass total linewidth => standard cooperativity)",
        "qv_form_is": "purcell_factor_times_branching_ratio (NOT a cooperativity)",
        "main_account": COOPERATIVITY_MAIN_ACCOUNT,
        "calibers": list(COOPERATIVITY_CALIBERS),
    }


# ---------------------------------------------------------------------------
# 默认设计（金刚石微盘腔 · telecom 典型量级 · 设计示例 · 非实测）
# ---------------------------------------------------------------------------
def design_defaults() -> Dict[str, float]:
    return {
        "n_r": 3.4,                    # 金刚石折射率
        "lambda0_m": 1550.0e-9,        # telecom 真空波长
        "Q": 1.0e4,                    # 微腔品质因子（设计示例）
        "a_m": 1.55e-6,               # 腔长 a（~λ）
        "A_m2": 5.0e-14,              # 模横向截面 A（~0.22µm×0.22µm）
        "mu_Cm": 1.0e-29,             # 跃迁偶极矩 μ（NV 量级）
        "gamma1_s1": 1.0e9,           # 总退相干率 γ₁（设计示例，1/s）
    }


def cavity_qed_physics(**overrides: Any) -> Dict[str, Any]:
    """QS-M3c 综合：Q/V_eff/g 物理链 + 整合（finesse / cooperativity / Purcell）。"""
    p = design_defaults()
    p.update({k: float(v) for k, v in overrides.items()})

    n_r = p["n_r"]
    lam = p["lambda0_m"]
    Q = p["Q"]
    a = p["a_m"]
    A = p["A_m2"]
    mu = p["mu_Cm"]
    gamma1 = p["gamma1_s1"]

    omega = 2.0 * math.pi * C_LIGHT / lam
    kappa = omega / Q
    eps = EPSILON_0 * n_r ** 2

    q_c = cavity_q_factor(omega, kappa)
    v_eff = mode_volume_closed(a, A)
    g = single_photon_coupling_closed(mu, omega, eps, a, A)
    gamma_rad = radiative_rate_gamma_rad(mu, omega)

    finesse = cavity_finesse_from_qv(Q, lam, n_r, a)
    finesse_def = cavity_finesse_from_defs(Q, lam, n_r, a)
    f_p = purcell_factor_qv(Q, lam, n_r, v_eff)
    c_g = cooperativity_from_g(g, kappa, gamma_rad)
    c_qv = cooperativity_from_qv(Q, lam, n_r, v_eff, gamma_rad, gamma1)

    return {
        "caliber": QS_M3C_CALIBER,
        "omega_rad_s": omega,
        "kappa_s1": kappa,
        "eps_Fm": eps,
        "Q": q_c,
        "V_eff_m3": v_eff,
        "g_Hz": g,
        "gamma_rad_s1": gamma_rad,
        "finesse": finesse,
        "finesse_from_defs": finesse_def,
        "purcell_F_P": f_p,
        "cooperativity_g_form": c_g,
        "cooperativity_qv_form": c_qv,
    }


# ---------------------------------------------------------------------------
# 自检（机器门禁读到的必须是现算值）
# ---------------------------------------------------------------------------
def selfcheck_qs_m3c() -> Dict[str, bool]:
    ok: Dict[str, bool] = {}

    # ── 链① Q ─────────────────────────────────────────────────────────────
    om = 1.2158e15
    kap = om / 1.0e4
    q_c = cavity_q_factor(om, kap)
    q_n = cavity_q_factor_numeric(om, kap, 8.22e-12, 64)
    q_coarse = cavity_q_factor_numeric(om, kap, 8.22e-12, 8)
    ok["q_closed_eq_numeric"] = abs(q_n - q_c) / abs(q_c) < 1e-6
    # 粗网格 ⇒ 残差显著放大（证明是真数值残差 · O(h⁴)）
    ok["q_coarse_grid_degrades"] = (
        abs(q_coarse - q_c) > 100.0 * abs(q_n - q_c))
    # 单调：κ ↑ ⇒ Q ↓
    ok["q_monotone_in_kappa"] = (
        cavity_q_factor(om, 2.0 * kap) < q_c < cavity_q_factor(om, 0.5 * kap))
    # 反向探针：κ → 0 ⇒ Q 发散（护栏）
    ok["reverse_zero_kappa_guarded"] = _raises(lambda: cavity_q_factor(om, 0.0))

    # ── 链② V_eff ─────────────────────────────────────────────────────────
    aa = 1.55e-6
    AA = 5.0e-14
    v_c = mode_volume_closed(aa, AA)
    v_n = mode_volume_numeric(aa, AA, 256)
    v_coarse = mode_volume_numeric(aa, AA, 32)
    ok["veff_closed_eq_numeric"] = abs(v_n - v_c) / abs(v_c) < 1e-4
    ok["veff_coarse_grid_degrades"] = (
        abs(v_coarse - v_c) > 20.0 * abs(v_n - v_c))
    # 单调：a ↑ ⇒ V_eff ↑
    ok["veff_monotone_in_a"] = mode_volume_closed(2.0 * aa, AA) > v_c
    # 反向探针：A → 0 ⇒ V_eff → 0
    ok["reverse_zero_area_guarded"] = _raises(lambda: mode_volume_closed(aa, 0.0))

    # ── 链③ g ─────────────────────────────────────────────────────────────
    mu = 1.0e-29
    eps = EPSILON_0 * 3.4 ** 2
    g_c = single_photon_coupling_closed(mu, om, eps, aa, AA)
    g_n = single_photon_coupling_numeric(mu, om, eps, aa, AA, 256)
    g_coarse = single_photon_coupling_numeric(mu, om, eps, aa, AA, 32)
    ok["g_closed_eq_numeric"] = abs(g_n - g_c) / abs(g_c) < 1e-4
    ok["g_coarse_grid_degrades"] = (
        abs(g_coarse - g_c) > 20.0 * abs(g_n - g_c))
    # g 随 μ 线性（g ∝ μ ⇒ g(μ)/g(μ/2) ≈ 2）
    ok["g_linear_in_mu"] = abs(
        single_photon_coupling_closed(mu, om, eps, aa, AA)
        / single_photon_coupling_closed(mu / 2.0, om, eps, aa, AA) - 2.0) < 1e-9
    # 反向探针：μ → 0 ⇒ 护栏（闭合型用 ≤0 守卫）
    ok["reverse_zero_mu_guarded"] = _raises(
        lambda: single_photon_coupling_closed(0.0, om, eps, aa, AA))
    # 反向探针：V_eff → 0 ⇒ g 发散（护栏）
    ok["reverse_zero_veff_guarded"] = _raises(
        lambda: single_photon_coupling_closed(mu, om, eps, 0.0, AA))

    # ── 整合：finesse 两式逐位一致 ─────────────────────────────────────────
    _ph = cavity_qed_physics()
    ok["finesse_two_forms_match"] = abs(
        _ph["finesse"] - _ph["finesse_from_defs"]) / abs(_ph["finesse"]) < 1e-12

    # ── 整合：cooperativity 约定因子 2n（诚实口径 · 模块内自洽）──────────────
    # 约定：γ_rad = 真空 Einstein-A、腔模 ε = ε₀n² ⇒
    #   4g²/(κγ_rad) = 2n · (3/4π²)(λ/n)³(Q/V)  （已严格推导；n_r=3.4 为本档设计值）
    _ratio = _ph["cooperativity_g_form"] / _ph["purcell_F_P"]
    ok["cooperativity_convention_factor_2n"] = abs(_ratio - 2.0 * 3.4) < 1e-9

    # ── 🔴 K1 结算面（断口 G-K-2）：两口径并报 + 闭式比值 + 防「以为相等」────
    _cal = cooperativity_calibers()
    ok["cooperativity_2n_identity_machine_precision"] = (
        _cal["identity_2n_resid_rel"] < 1e-12)
    ok["cooperativity_ratio_closed_form_machine_precision"] = (
        _cal["ratio_closed_form_resid_rel"] < 1e-12)
    # 🔴 两口径**不相等**（旧注释断言相等 ⇒ 该断言为假 · 本判据钉死「确有断口」）
    ok["cooperativity_two_calibers_not_equal"] = (
        abs(_cal["g_form"] - _cal["qv_form"]) / _cal["g_form"] > 1e-3)
    ok["cooperativity_main_account_is_g_form"] = (
        _cal["main_account"] == COOPERATIVITY_MAIN_ACCOUNT == "g_form")
    # 🔴 并报硬要求：机读字段齐备（**缺字段即红** ⇒ 防选择性披露）
    _need = ("g_form", "qv_form", "ratio_g_over_qv", "ratio_closed_form",
             "is_cooperativity", "main_account")
    ok["cooperativity_settlement_fields_present"] = all(k in _cal for k in _need)

    # 口径守卫
    try:
        assert_caliber(QS_M3C_CALIBER)
        assert_caliber(SENSITIVITY_CALIBER)
        ok["caliber_ok"] = True
    except ValueError:
        ok["caliber_ok"] = False
    try:
        assert_caliber("linearwidth_limited_LOD")
        ok["caliber_rejects_wrong"] = False
    except ValueError:
        ok["caliber_rejects_wrong"] = True

    return ok


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def design_qs_m3c(run_checks: bool = True) -> Dict[str, Any]:
    """QS-M3c 签核：物理链 + 整合 + 自检 + **协同度两口径结算面**（K1）。"""
    checks = selfcheck_qs_m3c() if run_checks else {}
    phys = cavity_qed_physics()
    verdict = "ACCEPT" if (not run_checks or all(checks.values())) else "REJECT"
    return {"caliber": QS_M3C_CALIBER, "checks": checks, "verdict": verdict,
            "physics": phys,
            "cooperativity_settlement": cooperativity_calibers()}


def main() -> int:
    r = design_qs_m3c()
    p = r["physics"]
    print("QS-M3c 腔 QED 物理链：verdict=%s" % r["verdict"])
    print("  ω = %.4e rad/s · κ = %.4e 1/s · Q = %.4e" % (p["omega_rad_s"], p["kappa_s1"], p["Q"]))
    print("  V_eff = %.4e m³ · g = %.4e Hz" % (p["V_eff_m3"], p["g_Hz"]))
    print("  finesse = %.4e · Purcell F_P = %.4e · C = %.4e"
          % (p["finesse"], p["purcell_F_P"], p["cooperativity_g_form"]))
    return 0 if r["verdict"] == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
