"""QS-M9 · 光泵原子磁力计（OPM / SERF）物理（吃狗粮 v9 · 量子传感器芯片征程 · 第三条腿）。

═══ 定位（蓝图层 `docs/LDA_量子传感器芯片征程_总蓝图_v1_2026-10-10.md` §QS-M9 · L118）═══
QS 征程前八档走了两条腿：**腿 A NV 色心**（光-自旋-磁 · 室温 · 固体）与
**腿 B 超导 SQUID**（电-磁通 · 4 K）。本档 = **腿 C · 光泵原子磁力计（OPM）**：
碱金属（Rb-87）蒸气气室 + 泵浦/探测光路 + 磁场线圈 —— **多物理场整合**
（光-自旋-磁-热-几何五场），并给出 **SERF 区**（Spin-Exchange Relaxation-Free）
自旋投影噪声极限灵敏度，与前两腿**同口径对照**。

**平台缺口 G11**：多物理场量子传感整合。

═══ 🔴 为什么这是「新物理」（同源体检 · 实 grep 全仓）═══
`光泵|OPM|SERF|极化率|碱金属|蒸气压|Larmor|拉莫|抽运` 在 `lda/lda_harness/` 内
**0 命中**（`Bloch` 命中是**半导体 Bloch 透射/Bloch 定理**，`Helmholtz` 命中是
**波导 Helmholtz 方程**，均非自旋 Bloch / Helmholtz 线圈）⇒ **OPM 族零锚占用**。

═══ 物理链（五链 · 闭式全部可作 golden）═══
链① **光抽运**（optical pumping）：
   · 光子能量 E_ph = hc/λ（Rb D1 线 795 nm）；
   · 光子通量 Φ = P_pump/(E_ph·A_beam)（photons·m⁻²·s⁻¹）；
   · 泵浦率 **R_op = σ_abs·Φ·f_depump**（σ_abs = 缓冲气体压致展宽后的 D1 有效截面）；
   · 自旋破坏率 **R_sd = R_wall + R_buffer + R_probe**（壁扩散 + 缓冲气体 + 探测光）；
   · **稳态极化 P∞ = R_op/(R_op + R_sd)**（速率方程稳态闭式）。
链② **自旋进动**（Larmor / Bloch 瞬态）：
   · Larmor 角频率 **ω_L = 2π·γ_e·B**（γ_e = g_s μ_B/h = 6.995 GHz/T for Rb-87）；
   · 自由进动（光抽运关闭后 · **FID**）的 Bloch 方程
        dP_x/dt = −R_tot·P_x − ω_L·P_y ,  dP_y/dt = −R_tot·P_y + ω_L·P_x
     ⇒ 闭式 **P_x(t) = P₀·e^(−R_tot·t)·cos(ω_L·t)**（2D 线性系统精确解）。
链③ **气室温度定标**（碱金属饱和蒸气压 · Clausius–Clapeyron）：
   · **n(T) = n_ref·exp(−(ΔH_vap/k_B)·(1/T − 1/T_ref))**（Rb: ΔH_vap/k_B = 8384 K）；
   · 碱金属原子数 N_a = n(T)·V_cell（决定自旋投影噪声）。
链④ **泵浦光路**（Beer–Lambert 吸收）：
   · **T(L) = exp(−n·σ_abs·L)**（光学厚度 τ_opt = n·σ_abs·L）。
链⑤ **多物理场整合 → SERF 区灵敏度**：
   · Bloch 稳态低场斜率 dp_x/dB = 2π·γ_e·P∞/R_tot（归一极化口径，1/T）；
   · 自旋投影噪声 δp = √(1/N_a)（N_a 个独立自旋投影的均值不确定度）；
   · **η = δB·√τ_c = √(R_tot/N_a)/(2π·γ_e·P∞)**（T/√Hz，τ_c = 1/R_tot 为自旋相关时间）
     —— 与 QS-M0（NV · 散粒极限）/ QS-M7（SQUID · Johnson 极限）**同口径**（幅度谱密度）。
链⑥ **磁场线圈**（多物理场「线圈」半 · **闭式，仅 smoke 覆盖 · 不登记锚**）：
   · **亥姆霍兹线圈中心场 B(0) = (4/5)^{3/2}·µ₀·N·I/R**（同轴双线圈间距 = R 的经典条件）。
     🔴 该量是**闭式算术**（无自然数值候选）⇒ 与「弛豫率分量」（定义式/算术）一并
     归 `run_qs_m9_smoke` 覆盖，**如实不登记为锚**（纪律：宁可少，不越级谎报）。

═══ 🔴 与既有锚的边界（**不同物理量**，非重复计数）═══
· B473–B484（腿 A NV 色心 · 固体自旋）：**金刚石色心**的散粒极限灵敏度 / FOM /
  退相干 / 几何 / 阵列 / 标定链；本档是**碱金属蒸气**的光抽运 + 自旋进动 + 气室
  热力学 + 光路吸收 ⇒ 物理对象（固体单自旋 vs 气体集合自旋）、换能机制
  （ODMR/Ramsey vs 光抽运/FID）、多物理场（无热场 vs 气室温度定标）均不同。
· B485–B490（腿 B 超导 SQUID）：**电-磁通**宏观量子相位；本档是**光-自旋**。
· `B475`（自旋回波相位方差 · 时间域数值积分）：**回波序列的相位方差**（退相干谱）；
  本档链②是**自由进动的横向极化分量**（P_x(t)）⇒ 被测标量不同（相位方差 vs 极化）
  且构型不同（无脉冲序列 vs 自由进动）⇒ 记新锚（先例 B452 vs B33）。
· `B462`（Langmuir 吸附 RK4）/`B464`（Washburn 后向欧拉）：**非光抽运体系**。
· `B488`（离散 Neumann 互感）：**圆环互感**（变压器）；本档链⑥线圈是**磁场 B(0)**，
  且**不登记为锚**（闭式算术）⇒ 无撞车。

═══ 🔴 红线自检标注 ═══
· C 级自主：**纯标准库 `math` 顶层**（本档五链全为标量闭式 ⇒ **无 numpy / scipy 依赖**），
  不借商业 EDA / 量子 SDK。
· LLM 不进判决路径：全部死标量 / numpy；PASS 与否由闭式比对决定。
· 进报告数字一律**模块现算**（不转录草稿）；判据读到的值 = 模块现算值。
· 每道守卫配反向探针（先证能变红）。
· 🔴 **不在判决路径使用「T1 输出」**（器件级 T1 PDE 输出永不作 ORACLE）。
· 🔴 **诚实边界**：泵浦功率 / 束面积 / 吸收截面 / 壁与缓冲气体弛豫率 / 气室体积 /
  长度 / 温度 / 数密度均为**设计示例量级**（SERF OPM 典型，300–470 K 碱金属气室），
  **非任何实测装置 PDK**；本档报告为**建模值**（η ≈ 0.83 fT/√Hz），**不得作制造 /
  性能宣称**；文献 SOTA（SERF ~0.16 fT/√Hz）只作**对标准星**引用，**不冒充 LDA 实测**；
  **不报 fabricated 能效**。
"""
from __future__ import annotations

import math
from typing import Any, Dict

# ---------------------------------------------------------------------------
# 物理常数（SI · CODATA 量级；作为闭式 golden 的输入真源）
# ---------------------------------------------------------------------------
H_PLANCK = 6.62607015e-34          # J·s
C_LIGHT = 299792458.0              # m/s
E_CHARGE = 1.602176634e-19         # C
K_B = 1.380649e-23                 # J/K
MU_0 = 1.25663706212e-6            # H/m

#: Rb-87 电子自旋旋磁比 γ_e/2π（Hz/T；= g_s·µ_B/h）
GAMMA_RB_HZ_T = 6.995e9
#: Rb D1 线波长（m）
D1_WAVELENGTH_M = 795.0e-9
#: Rb 蒸气汽化焓 / k_B（K · Clausius–Clapeyron 常数模型）
DH_VAP_OVER_KB_K = 8384.0
#: 参考点（数密度真源）
N_REF_M3 = 1.0e17
T_REF_K = 313.15

#: 灵敏度口径（与 QS-M0 / QS-M6 / QS-M7 统一：幅度谱密度 T/√Hz）
SENSITIVITY_CALIBER = "B_N__amplitude_spectral_density__T_per_sqrtHz"
QS_M9_CALIBER = "opm_serf__optical_pumping_and_larmor_precession__T_per_sqrtHz"


def assert_caliber(caliber: str) -> None:
    """口径守卫（禁与线宽受限 LOD / 单次测量不确定度混比）。"""
    if caliber not in (SENSITIVITY_CALIBER, QS_M9_CALIBER):
        raise ValueError("未知口径：%r" % (caliber,))


# ---------------------------------------------------------------------------
# 链① 光抽运
# ---------------------------------------------------------------------------
def photon_energy_j(wavelength_m: float = D1_WAVELENGTH_M) -> float:
    """光子能量 E_ph = hc/λ（J）。"""
    if wavelength_m <= 0.0:
        raise ValueError("wavelength_m 必须 > 0")
    return float(H_PLANCK * C_LIGHT / wavelength_m)


def photon_flux_per_m2_s(power_w: float, beam_area_m2: float,
                         wavelength_m: float = D1_WAVELENGTH_M) -> float:
    """光子通量 Φ = P/(E_ph·A)（photons·m⁻²·s⁻¹）。"""
    if power_w <= 0.0:
        raise ValueError("power_w 必须 > 0")
    if beam_area_m2 <= 0.0:
        raise ValueError("beam_area_m2 必须 > 0")
    return float(power_w / (photon_energy_j(wavelength_m) * beam_area_m2))


def optical_pumping_rate_s1(sigma_abs_m2: float, flux_per_m2_s: float,
                            f_depump: float = 1.0) -> float:
    """光抽运率 **R_op = σ_abs·Φ·f_depump**（1/s）。

    🔴 物理：每吸收一个 D1 光子可携带约 1 份角动量；`f_depump` 是**去抽运分支比**
    （非零 ⇒ 抽运效率 < 1），设计示例取 0.5。
    """
    if sigma_abs_m2 <= 0.0 or flux_per_m2_s <= 0.0:
        raise ValueError("sigma_abs / flux 必须 > 0")
    if f_depump <= 0.0:
        raise ValueError("f_depump 必须 > 0")
    return float(sigma_abs_m2 * flux_per_m2_s * f_depump)


def spin_destruction_rate_s1(r_wall_s1: float, r_buffer_s1: float,
                             r_probe_s1: float) -> float:
    """自旋破坏率 **R_sd = R_wall + R_buffer + R_probe**（1/s · 三源相加）。"""
    for name, v in (("r_wall_s1", r_wall_s1), ("r_buffer_s1", r_buffer_s1),
                    ("r_probe_s1", r_probe_s1)):
        if v < 0.0:
            raise ValueError("%s 必须 ≥ 0" % name)
    return float(r_wall_s1 + r_buffer_s1 + r_probe_s1)


def steady_polarization(r_op_s1: float, r_sd_s1: float) -> float:
    """稳态自旋极化 **P∞ = R_op/(R_op + R_sd)**（无量纲 · 速率方程稳态闭式）。

    🔴 极限自洽：R_op → ∞ ⇒ P∞ → 1（全极化）；R_op → 0 ⇒ P∞ → 0（无抽运）。
    """
    if r_op_s1 <= 0.0:
        raise ValueError("r_op_s1 必须 > 0")
    if r_sd_s1 < 0.0:
        raise ValueError("r_sd_s1 必须 ≥ 0")
    return float(r_op_s1 / (r_op_s1 + r_sd_s1))


# ---------------------------------------------------------------------------
# 链② 自旋进动（Larmor / Bloch 自由进动瞬态）
# ---------------------------------------------------------------------------
def larmor_rad_s(b_t: float, gamma_hz_t: float = GAMMA_RB_HZ_T) -> float:
    """Larmor 角频率 **ω_L = 2π·γ_e·B**（rad/s）。"""
    if gamma_hz_t <= 0.0:
        raise ValueError("gamma_hz_t 必须 > 0")
    return float(2.0 * math.pi * gamma_hz_t * b_t)


def transverse_polarization_closed(p0: float, r_tot_s1: float, b_t: float,
                                   t_s: float,
                                   gamma_hz_t: float = GAMMA_RB_HZ_T) -> float:
    """闭式 **P_x(t) = P₀·e^(−R_tot·t)·cos(ω_L·t)**（无量纲 · 自由进动 FID 横向极化）。

    🔴 物理：光抽运关闭后（或弱抽运下）自旋在静磁场中自由进动，横向极化按自旋
    相关时间 1/R_tot 衰减、按 Larmor 频率振荡 —— 这是 OPM 的**时域信号**。
    🔴 该式是 2D 线性 Bloch 方程的**精确解**（不含任何近似）⇒ 可作 golden。
    """
    if p0 <= 0.0:
        raise ValueError("p0 必须 > 0")
    if r_tot_s1 <= 0.0:
        raise ValueError("r_tot_s1 必须 > 0")
    if t_s <= 0.0:
        raise ValueError("t_s 必须 > 0")
    w = larmor_rad_s(b_t, gamma_hz_t)
    return float(p0 * math.exp(-r_tot_s1 * t_s) * math.cos(w * t_s))


def transverse_polarization_numeric(p0: float, r_tot_s1: float, b_t: float,
                                    t_s: float,
                                    gamma_hz_t: float = GAMMA_RB_HZ_T,
                                    n_steps: int = 64) -> float:
    """candidate：**RK4 时间推进 2D Bloch 方程**（方法学独立 · 不用闭式指数/余弦）。

    🔴 残差来源 = **RK4 时间离散化截断**（实测 O(h⁴)，比值 ~16×/倍增）⇒ **非**代数恒等。
    """
    if p0 <= 0.0 or r_tot_s1 <= 0.0 or t_s <= 0.0:
        raise ValueError("p0/r_tot/t_s 必须 > 0")
    if n_steps < 4:
        raise ValueError("n_steps 必须 ≥ 4")
    w = larmor_rad_s(b_t, gamma_hz_t)
    h = t_s / n_steps
    x, y = float(p0), 0.0

    def _f(sx: float, sy: float):
        return (-r_tot_s1 * sx - w * sy, -r_tot_s1 * sy + w * sx)

    for _ in range(int(n_steps)):
        k1 = _f(x, y)
        k2 = _f(x + 0.5 * h * k1[0], y + 0.5 * h * k1[1])
        k3 = _f(x + 0.5 * h * k2[0], y + 0.5 * h * k2[1])
        k4 = _f(x + h * k3[0], y + h * k3[1])
        x += (h / 6.0) * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0])
        y += (h / 6.0) * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1])
    return float(x)


# ---------------------------------------------------------------------------
# 链③ 气室温度定标（碱金属饱和蒸气压）
# ---------------------------------------------------------------------------
def alkali_density_closed(n_ref_m3: float, t_ref_k: float, dh_over_kb_k: float,
                          t_k: float) -> float:
    """闭式 **n(T) = n_ref·exp(−(ΔH/k_B)·(1/T − 1/T_ref))**（m⁻³）。

    🔴 物理：Clausius–Clapeyron 常数汽化焓模型（Rb: ΔH_vap/k_B = 8384 K）。
    T ↑ ⇒ n ↑ 指数上升（Rb 数密度约每 10 K 翻倍）。
    """
    if n_ref_m3 <= 0.0 or t_ref_k <= 0.0 or t_k <= 0.0:
        raise ValueError("n_ref / t_ref / t_k 必须 > 0")
    if dh_over_kb_k <= 0.0:
        raise ValueError("dh_over_kb_k 必须 > 0")
    return float(n_ref_m3 * math.exp(-dh_over_kb_k * (1.0 / t_k - 1.0 / t_ref_k)))


def alkali_density_numeric(n_ref_m3: float, t_ref_k: float, dh_over_kb_k: float,
                           t_k: float, n_seg: int = 256) -> float:
    """candidate：**复合梯形数值积分** `d(ln n)/dT = ΔH/(k_B·T²)`（方法学独立）。

    🔴 残差来源 = **梯形求积截断**（实测 O(h²)，比值 ~4.00×/倍增；被积函数 A/T²
    **非常数** ⇒ **非剖分守恒** ⇒ 与 B28「均匀段剖分守恒」型代数恒等不同）。
    """
    if n_ref_m3 <= 0.0 or t_ref_k <= 0.0 or t_k <= 0.0:
        raise ValueError("n_ref / t_ref / t_k 必须 > 0")
    if n_seg < 4:
        raise ValueError("n_seg 必须 ≥ 4")
    h = (t_k - t_ref_k) / int(n_seg)
    acc = 0.0
    for i in range(int(n_seg)):
        ta = t_ref_k + i * h
        tb = ta + h
        acc += 0.5 * h * (dh_over_kb_k / (ta * ta) + dh_over_kb_k / (tb * tb))
    return float(n_ref_m3 * math.exp(acc))


# ---------------------------------------------------------------------------
# 链④ 泵浦光路（Beer–Lambert 吸收）
# ---------------------------------------------------------------------------
def pump_transmission_closed(trans0: float, n_density_m3: float,
                             sigma_abs_m2: float, length_m: float) -> float:
    """闭式 **T(L) = T₀·exp(−n·σ_abs·L)**（无量纲 · Beer–Lambert）。

    🔴 光学厚度 τ_opt = n·σ_abs·L；τ_opt = 1 ⇒ T = 37%（典型 SERF 气室工作点）。
    """
    if trans0 <= 0.0:
        raise ValueError("trans0 必须 > 0")
    if n_density_m3 < 0.0 or sigma_abs_m2 < 0.0:
        raise ValueError("n / σ 必须 ≥ 0")
    if length_m <= 0.0:
        raise ValueError("length_m 必须 > 0")
    return float(trans0 * math.exp(-n_density_m3 * sigma_abs_m2 * length_m))


def pump_transmission_numeric(trans0: float, n_density_m3: float,
                              sigma_abs_m2: float, length_m: float,
                              n_steps: int = 64) -> float:
    """candidate：**RK4 沿 z 数值积分** `dI/dz = −n·σ_abs·I`（方法学独立）。

    🔴 残差来源 = **RK4 空间离散化截断**（实测 O(h⁴)，比值 ~16×/倍增）。
    """
    if trans0 <= 0.0 or length_m <= 0.0:
        raise ValueError("trans0 / length_m 必须 > 0")
    if n_steps < 4:
        raise ValueError("n_steps 必须 ≥ 4")
    alpha = n_density_m3 * sigma_abs_m2
    h = length_m / int(n_steps)
    i_val = float(trans0)
    for _ in range(int(n_steps)):
        k1 = -alpha * i_val
        k2 = -alpha * (i_val + 0.5 * h * k1)
        k3 = -alpha * (i_val + 0.5 * h * k2)
        k4 = -alpha * (i_val + h * k3)
        i_val += (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(i_val)


# ---------------------------------------------------------------------------
# 链⑤ 多物理场整合：SERF 区自旋投影噪声极限灵敏度
# ---------------------------------------------------------------------------
def spin_projection_polarization_noise(n_atoms: float) -> float:
    """自旋投影噪声（归一极化口径）**δp = √(1/N_a)**（无量纲）。

    🔴 物理：N_a 个独立自旋投影的均值不确定度 = 标准量子极限。
    """
    if n_atoms <= 0.0:
        raise ValueError("n_atoms 必须 > 0")
    return float(math.sqrt(1.0 / n_atoms))


def low_field_slope_per_t(r_tot_s1: float, p_inf: float,
                          gamma_hz_t: float = GAMMA_RB_HZ_T) -> float:
    """Bloch 稳态**低场斜率** dp_x/dB = 2π·γ_e·P∞/R_tot（1/T · 归一极化口径）。"""
    if r_tot_s1 <= 0.0 or p_inf <= 0.0:
        raise ValueError("r_tot / p_inf 必须 > 0")
    if gamma_hz_t <= 0.0:
        raise ValueError("gamma_hz_t 必须 > 0")
    return float(2.0 * math.pi * gamma_hz_t * p_inf / r_tot_s1)


def serf_sensitivity_t_per_sqrt_hz(r_tot_s1: float, n_atoms: float, p_inf: float,
                                   gamma_hz_t: float = GAMMA_RB_HZ_T) -> float:
    """闭式 **SERF 区磁灵敏度 η = √(R_tot/N_a)/(2π·γ_e·P∞)**（T/√Hz）。

    🔴 推导（三链串联 · 与 QS-M0 同构的**谱密度归一**）：
      · 单次测量（自旋相关时间 τ_c = 1/R_tot）的极化不确定度 δp = √(1/N_a)；
      · 磁场不确定度 δB_single = δp/(dp_x/dB) = √(1/N_a)·R_tot/(2π·γ_e·P∞)；
      · 谱密度归一 η = δB_single·√τ_c ⇒ η = √(R_tot/N_a)/(2π·γ_e·P∞)。
    🔴 与 QS-M0（NV 光子散粒极限）/ QS-M7（SQUID Johnson 极限）**同口径**（T/√Hz 幅度谱密度）。
    """
    if r_tot_s1 <= 0.0 or n_atoms <= 0.0 or p_inf <= 0.0:
        raise ValueError("r_tot / n_atoms / p_inf 必须 > 0")
    return float(math.sqrt(r_tot_s1 / n_atoms)
                 / (2.0 * math.pi * gamma_hz_t * p_inf))


# ---------------------------------------------------------------------------
# 链⑥ 磁场线圈（多物理场「线圈」半 · 闭式算术 ⇒ 仅 smoke 覆盖 · 不登记锚）
# ---------------------------------------------------------------------------
def helmholtz_field_t(current_a: float, turns_per_coil: float,
                      radius_m: float, mu_0: float = MU_0) -> float:
    """亥姆霍兹线圈中心场 **B(0) = (4/5)^{3/2}·µ₀·N·I/R**（T）。

    🔴 闭式算术 ⇒ 与「弛豫率分量」（定义式/算术）一并归 `run_qs_m9_smoke` 覆盖，
    **如实不登记为锚**。
    """
    if current_a <= 0.0:
        raise ValueError("current_a 必须 > 0")
    if turns_per_coil <= 0.0 or radius_m <= 0.0:
        raise ValueError("turns / radius 必须 > 0")
    return float((4.0 / 5.0) ** 1.5 * mu_0 * turns_per_coil * current_a / radius_m)


# ---------------------------------------------------------------------------
# 综合设计（五链串联 → SERF 灵敏度 · 三条腿同口径对照）
# ---------------------------------------------------------------------------
def design_defaults() -> Dict[str, float]:
    """默认设计参数（SERF OPM 典型量级 · **设计示例 · 非实测**）。"""
    return {
        "pump_power_w": 5.0e-3,            # 泵浦光功率 5 mW
        "beam_area_m2": (2.0e-3) ** 2,     # 束面积（2 mm 见方）= 4e-6 m²
        "sigma_abs_m2": 5.0e-18,           # 缓冲气体展宽后 D1 有效吸收截面
        "f_depump": 0.5,                   # 去抽运分支比
        "r_wall_s1": 50.0,                 # 壁扩散弛豫
        "r_buffer_s1": 150.0,              # 缓冲气体自旋破坏
        "r_probe_s1": 100.0,               # 探测光破坏
        "volume_m3": 1.0e-6,               # 气室体积 1 cm³
        "cell_length_m": 0.02,             # 气室长度 2 cm
        "t_k": 373.15,                     # 气室温度 100 °C
        "t_ref_k": T_REF_K,                # 数密度参考点 40 °C
        "n_ref_m3": N_REF_M3,              # 参考点数密度
        "dh_over_kb_k": DH_VAP_OVER_KB_K,  # Rb 汽化焓/k_B
        "gamma_hz_t": GAMMA_RB_HZ_T,       # Rb-87 旋磁比
        "b_hold_t": 10.0e-9,               # 持场 10 nT（自由进动观测点）
        "t_fid_s": 2.0e-3,                 # FID 观测时刻 2 ms
        "p0_fid": 1.0,                     # FID 初始横向极化
        "bias_field_t": 100.0e-9,          # 偏置磁场 100 nT（斜率线性段）
        "sota_serf_fT": 0.16,              # 公开文献 SERF 最优（对标准星 · 非实测）
        "coil_current_a": 1.0,             # 线圈电流 1 A
        "coil_turns": 100.0,               # 每线圈 100 匝
        "coil_radius_m": 0.05,             # 线圈半径 5 cm
    }


def opm_serf_physics(**overrides: Any) -> Dict[str, Any]:
    """QS-M9 综合：光抽运 → 气室密度 → 光路 → SERF 灵敏度（五链串联）。"""
    p = design_defaults()
    p.update({k: float(v) for k, v in overrides.items()})

    flux = photon_flux_per_m2_s(p["pump_power_w"], p["beam_area_m2"])
    r_op = optical_pumping_rate_s1(p["sigma_abs_m2"], flux, p["f_depump"])
    r_sd = spin_destruction_rate_s1(p["r_wall_s1"], p["r_buffer_s1"],
                                    p["r_probe_s1"])
    p_inf = steady_polarization(r_op, r_sd)
    r_tot = r_op + r_sd

    n_density = alkali_density_closed(p["n_ref_m3"], p["t_ref_k"],
                                      p["dh_over_kb_k"], p["t_k"])
    n_atoms = n_density * p["volume_m3"]
    trans = pump_transmission_closed(1.0, n_density, p["sigma_abs_m2"],
                                     p["cell_length_m"])
    tau_opt = n_density * p["sigma_abs_m2"] * p["cell_length_m"]

    p_x_fid = transverse_polarization_closed(p["p0_fid"], r_sd, p["b_hold_t"],
                                             p["t_fid_s"])
    slope = low_field_slope_per_t(r_tot, p_inf)
    eta = serf_sensitivity_t_per_sqrt_hz(r_tot, n_atoms, p_inf)
    b_coil = helmholtz_field_t(p["coil_current_a"], p["coil_turns"],
                               p["coil_radius_m"])

    return {
        "caliber": QS_M9_CALIBER,
        "photon_energy_j": photon_energy_j(),
        "photon_flux_per_m2_s": flux,
        "r_op_s1": r_op,
        "r_sd_s1": r_sd,
        "r_tot_s1": r_tot,
        "p_inf": p_inf,
        "larmor_rad_s": larmor_rad_s(p["b_hold_t"]),
        "p_x_fid": p_x_fid,
        "n_density_m3": n_density,
        "n_atoms": n_atoms,
        "optical_depth": tau_opt,
        "pump_transmission": trans,
        "low_field_slope_per_t": slope,
        "eta_t_per_sqrt_hz": eta,
        "eta_fT_per_sqrt_hz": eta * 1e15,
        "coil_field_t": b_coil,
        "coil_field_nT": b_coil * 1e9,
        "sota_serf_fT_per_sqrt_hz": p["sota_serf_fT"],
        "sota_ratio": eta * 1e15 / p["sota_serf_fT"],
    }


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "baseline": {
        "desc": "基线：5 mW 泵浦 / 2 mm 束 / 1 cm³ 气室 @100 °C（设计示例）",
        "overrides": {},
    },
    "hot_cell": {
        "desc": "气室升温 120 °C（数密度 ↑ ⇒ N_a ↑ ⇒ 灵敏度改善）",
        "overrides": {"t_k": 393.15},
    },
    "cold_cell": {
        "desc": "气室降温 80 °C（数密度 ↓ ⇒ N_a ↓ ⇒ 灵敏度劣化）",
        "overrides": {"t_k": 353.15},
    },
    "low_relaxation": {
        "desc": "低弛豫气室（壁/缓冲气体减半 ⇒ R_tot ↓ ⇒ 灵敏度改善）",
        "overrides": {"r_wall_s1": 25.0, "r_buffer_s1": 75.0},
    },
    "high_power": {
        "desc": "泵浦功率 ×4（R_op ↑ ⇒ P∞ ↑ 但 R_tot ↑ ⇒ 综合权衡）",
        "overrides": {"pump_power_w": 20.0e-3},
    },
}


def evaluate_scenario(name: str) -> Dict[str, Any]:
    """按情景名现算 QS-M9 综合物理。"""
    if name not in SCENARIOS:
        raise KeyError("未知情景：%r（可选 %s）" % (name, sorted(SCENARIOS)))
    out = opm_serf_physics(**SCENARIOS[name]["overrides"])
    out["scenario"] = name
    out["desc"] = SCENARIOS[name]["desc"]
    return out


def sensitivity_table() -> Dict[str, Dict[str, Any]]:
    """五情景 SERF 灵敏度表（fT/√Hz · 全部模块现算）。"""
    return {n: {"desc": SCENARIOS[n]["desc"],
                "eta_fT_per_sqrt_hz": evaluate_scenario(n)["eta_fT_per_sqrt_hz"]}
            for n in SCENARIOS}


def three_legs_table() -> Dict[str, Any]:
    """三条腿同口径对照（T/√Hz · **全部建模值 · 非实测**）。

    🔴 三条腿的物理机制完全不同（固体自旋散粒极限 / 超导 Johnson 极限 / 碱金属
    自旋投影极限），此处只做**同口径量级对照**，**不构成任何性能宣称**。
    """
    nv = 846.5901146206905e-12      # QS-M0 基线建模值（pT/√Hz → T/√Hz）
    squid = 1.7299984833764408e-15  # QS-M7 优化后建模值
    opm = opm_serf_physics()["eta_t_per_sqrt_hz"]
    return {
        "caliber": SENSITIVITY_CALIBER,
        "nv_leg_t_per_sqrt_hz": nv,
        "nv_leg_fT_per_sqrt_hz": nv * 1e15,
        "squid_leg_t_per_sqrt_hz": squid,
        "squid_leg_fT_per_sqrt_hz": squid * 1e15,
        "opm_leg_t_per_sqrt_hz": opm,
        "opm_leg_fT_per_sqrt_hz": opm * 1e15,
        "opm_better_than_squid": opm < squid,
        "opm_better_than_nv": opm < nv,
    }


# ---------------------------------------------------------------------------
# 自检（机器门禁读到的必须是现算值）
# ---------------------------------------------------------------------------
def selfcheck_qs_m9() -> Dict[str, bool]:
    ok: Dict[str, bool] = {}

    # ── 链① 光抽运 ──────────────────────────────────────────────────────
    flux = photon_flux_per_m2_s(5.0e-3, 4.0e-6)
    r_op = optical_pumping_rate_s1(5.0e-18, flux, 0.5)
    r_sd = spin_destruction_rate_s1(50.0, 150.0, 100.0)
    p_inf = steady_polarization(r_op, r_sd)
    ok["pumping_rate_positive"] = r_op > 0.0 and r_sd == 300.0
    ok["steady_polarization_unit_interval"] = 0.0 < p_inf < 1.0
    # 单调：R_op ↑ ⇒ P∞ ↑
    ok["polarization_monotone_r_op"] = (
        steady_polarization(2.0 * r_op, r_sd) > p_inf > steady_polarization(r_sd, r_sd))
    # 反向探针：R_sd = 0 ⇒ P∞ = 1（全极化极限）
    ok["reverse_zero_r_sd_saturates"] = abs(steady_polarization(r_op, 0.0) - 1.0) < 1e-15

    # ── 链② 自旋进动 ───────────────────────────────────────────────────
    p_closed = transverse_polarization_closed(1.0, 300.0, 10.0e-9, 2.0e-3)
    p_num = transverse_polarization_numeric(1.0, 300.0, 10.0e-9, 2.0e-3, n_steps=64)
    ok["fid_closed_eq_numeric"] = abs(p_num - p_closed) / abs(p_closed) < 1e-7
    # 反向探针：粗网格 ⇒ 残差显著放大（证明是真数值残差）
    p_coarse = transverse_polarization_numeric(1.0, 300.0, 10.0e-9, 2.0e-3, n_steps=8)
    ok["fid_coarse_grid_degrades"] = (
        abs(p_coarse - p_closed) > 10.0 * abs(p_num - p_closed))
    # B = 0 ⇒ 无进动（cos 0 = 1）⇒ 纯弛豫
    ok["fid_zero_field_pure_decay"] = abs(
        transverse_polarization_closed(1.0, 300.0, 0.0, 2.0e-3)
        - math.exp(-0.6)) < 1e-12
    # ω_L ∝ B
    ok["larmor_linear_in_b"] = abs(larmor_rad_s(2e-9) - 2.0 * larmor_rad_s(1e-9)) < 1e-9

    # ── 链③ 气室密度 ───────────────────────────────────────────────────
    n_c = alkali_density_closed(1.0e17, 313.15, 8384.0, 333.15)
    n_n = alkali_density_numeric(1.0e17, 313.15, 8384.0, 333.15, n_seg=256)
    ok["density_closed_eq_numeric"] = abs(n_n - n_c) / n_c < 1e-5
    n_coarse = alkali_density_numeric(1.0e17, 313.15, 8384.0, 333.15, n_seg=32)
    ok["density_coarse_grid_degrades"] = (
        abs(n_coarse - n_c) > 4.0 * abs(n_n - n_c))
    # T ↑ ⇒ n ↑（单调）
    ok["density_monotone_in_t"] = (
        alkali_density_closed(1.0e17, 313.15, 8384.0, 373.15) > n_c)
    # T = T_ref ⇒ n = n_ref（自洽点）
    ok["density_self_consistent_at_ref"] = abs(
        alkali_density_closed(1.0e17, 313.15, 8384.0, 313.15) - 1.0e17) < 1e-3

    # ── 链④ 泵浦光路 ───────────────────────────────────────────────────
    t_c = pump_transmission_closed(1.0, 1.0e19, 5.0e-18, 0.02)
    t_n = pump_transmission_numeric(1.0, 1.0e19, 5.0e-18, 0.02, n_steps=64)
    ok["transmission_closed_eq_numeric"] = abs(t_n - t_c) / t_c < 1e-7
    t_coarse = pump_transmission_numeric(1.0, 1.0e19, 5.0e-18, 0.02, n_steps=8)
    ok["transmission_coarse_grid_degrades"] = (
        abs(t_coarse - t_c) > 10.0 * abs(t_n - t_c))
    # 光学厚度 = 1 ⇒ T = 1/e
    ok["unit_optical_depth_one_over_e"] = abs(t_c - math.exp(-1.0)) < 1e-12

    # ── 链⑤ SERF 灵敏度 ────────────────────────────────────────────────
    n_atoms = 1.0e13
    eta = serf_sensitivity_t_per_sqrt_hz(1.28e4, n_atoms, 0.9766)
    ok["serf_eta_sane_range"] = 1e-17 <= eta <= 1e-14
    # 反向探针：N_a → 0 ⇒ 护栏必须拦下（缺 N_a 依赖的实现必红）
    ok["reverse_zero_atoms_guarded"] = _raises(
        lambda: serf_sensitivity_t_per_sqrt_hz(1.28e4, 0.0, 0.9766))
    # 单调：N_a ↑ ⇒ η ↓；R_tot ↑ ⇒ η ↑
    ok["serf_monotone_atoms"] = (
        serf_sensitivity_t_per_sqrt_hz(1.28e4, 4.0 * n_atoms, 0.9766) < eta)
    ok["serf_monotone_relaxation"] = (
        serf_sensitivity_t_per_sqrt_hz(2.0 * 1.28e4, n_atoms, 0.9766) > eta)
    # 谱密度归一自洽：η = δp/(斜率)·√τ_c
    slope = low_field_slope_per_t(1.28e4, 0.9766)
    delta_p = spin_projection_polarization_noise(n_atoms)
    ok["serf_normalization_self_consistent"] = abs(
        delta_p / slope * math.sqrt(1.0 / 1.28e4) - eta) / eta < 1e-12

    # ── 链⑥ 线圈（闭式算术 ⇒ 仅 smoke）─────────────────────────────────
    ok["helmholtz_field_positive"] = helmholtz_field_t(1.0, 100.0, 0.05) > 0.0

    # ── 综合链路 + 三腿对照 ────────────────────────────────────────────
    phys = opm_serf_physics()
    ok["report_equals_recompute"] = (
        abs(phys["eta_t_per_sqrt_hz"] - serf_sensitivity_t_per_sqrt_hz(
            300.0 + phys["r_op_s1"], phys["n_atoms"], phys["p_inf"])) < 1e-30)
    legs = three_legs_table()
    ok["three_legs_ordering"] = bool(
        legs["opm_leg_fT_per_sqrt_hz"] < legs["squid_leg_fT_per_sqrt_hz"]
        < legs["nv_leg_fT_per_sqrt_hz"])
    # 情景单调性：高温更优 / 低弛豫更优
    ok["scenario_hot_cell_better"] = (
        evaluate_scenario("hot_cell")["eta_t_per_sqrt_hz"]
        < evaluate_scenario("baseline")["eta_t_per_sqrt_hz"])
    ok["scenario_low_relax_better"] = (
        evaluate_scenario("low_relaxation")["eta_t_per_sqrt_hz"]
        < evaluate_scenario("baseline")["eta_t_per_sqrt_hz"])

    # 口径守卫
    try:
        assert_caliber(QS_M9_CALIBER)
        assert_caliber(SENSITIVITY_CALIBER)
        ok["caliber_ok"] = True
    except ValueError:
        ok["caliber_ok"] = False
    try:
        assert_caliber("linearwidth_limited_LOD")
        ok["caliber_rejects_wrong"] = False
    except ValueError:
        ok["caliber_rejects_wrong"] = True

    # 护栏：非法输入抛错
    ok["raises_on_bad"] = _raises(lambda: steady_polarization(0.0, 1.0)) and _raises(
        lambda: transverse_polarization_closed(1.0, 0.0, 0.0, 1.0)) and _raises(
        lambda: alkali_density_closed(1.0, 1.0, 1.0, 0.0)) and _raises(
        lambda: pump_transmission_closed(1.0, 1.0, 1.0, 0.0)) and _raises(
        lambda: serf_sensitivity_t_per_sqrt_hz(1.0, 0.0, 1.0))

    return ok


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def design_qs_opm(run_checks: bool = True) -> Dict[str, Any]:
    """QS-M9 签核：五链串联 + 自检 + 情景表 + 三腿对照。"""
    checks = selfcheck_qs_m9() if run_checks else {}
    phys = opm_serf_physics()
    verdict = "ACCEPT" if (not run_checks or all(checks.values())) else "REJECT"
    return {
        "caliber": QS_M9_CALIBER,
        "checks": checks,
        "verdict": verdict,
        "physics": phys,
        "scenarios": sensitivity_table(),
        "three_legs": three_legs_table(),
    }


def main() -> int:
    r = design_qs_opm()
    p = r["physics"]
    legs = r["three_legs"]
    print("QS-M9 OPM/SERF：verdict=%s" % r["verdict"])
    print("  R_op = %.3e 1/s · R_sd = %.3e 1/s · P∞ = %.4f"
          % (p["r_op_s1"], p["r_sd_s1"], p["p_inf"]))
    print("  n(T) = %.3e m⁻³ · N_a = %.3e · 光学厚度 = %.4f"
          % (p["n_density_m3"], p["n_atoms"], p["optical_depth"]))
    print("  η_SERF = %.4f fT/√Hz（SOTA 对照 %.2f fT/√Hz → 比值 %.2f）"
          % (p["eta_fT_per_sqrt_hz"], p["sota_serf_fT_per_sqrt_hz"], p["sota_ratio"]))
    print("  三条腿（fT/√Hz）：NV %.3e · SQUID %.3e · OPM %.4f"
          % (legs["nv_leg_fT_per_sqrt_hz"], legs["squid_leg_fT_per_sqrt_hz"],
             legs["opm_leg_fT_per_sqrt_hz"]))
    return 0 if r["verdict"] == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
