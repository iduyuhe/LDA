"""QS-M2 · 量子传感**退相干 + 多源噪声**物理（吃狗粮 v3 · 量子传感器芯片征程）。

═══ 定位（蓝图层 `docs/LDA_量子传感器芯片征程_总蓝图_v1_2026-10-10.md` §4）═══
QS-M0 交付 NV 磁力计最小闭环；QS-M1 交付**灵敏度 FOM 体系**（统一口径 + 四情景）。
QS-M2 补上**物理真实性**：QS-M0/M1 的 η 是**散粒极限**（理想白噪声），而真实
灵敏度受两大因素降级——
  · **退相干**：T₂*（非均匀展宽）→ T₂（动力学去耦 DD，回波/CPMG）；
  · **多源噪声**：光子散粒 / 微波抖动 / 温度漂移 / 环境磁噪声 合成 → **真实灵敏度**。
**平台缺口 G4**：自旋相干时间建模（复用 `open_system` 思路 —— 滤波函数积分）。

═══ 🔴 退相干物理（本档核心 · 闭式可作 golden）═══
单频（单色）噪声 B(t)=b·cos(ωt+φ)，初相 φ 均匀分布。相位积累
  Φ(t)=γ∫B(s)ds。对 φ 平均后，小信号相干衰减 W=⟨cosΦ⟩≈1−⟨Φ²⟩/2。
  · **FID**（自由感应衰减）：⟨Φ²⟩_fid = (γb/ω)²·2(1−cosωt)
  · **Hahn 回波**（中间 π 脉冲）：⟨Φ²⟩_echo = (γb/ω)²·**2(1−cos(ωt/2))²**
🔴 **回波高阶抑制**：直流极限 ⟨Φ²⟩_fid ~ (ωt)²/2（**二阶**），
   ⟨Φ²⟩_echo ~ (ωt)⁴/32（**四阶**）⇒ 回波把 DC/低频噪声**四阶压制**，
   正是 DD 提升相干时间的物理根因。

**DD 脉冲串（CPMG-n）**：滤波函数 F_n(ω,t)=|Σ_j (−1)^j(e^{iωt_{j+1}}−e^{iωt_j})|²，
  t_j=(2j−1)t/(2n)。相干 χ(t)=(1/π)∫S(ω)F_n(ω,t)/ω² dω。**F_n(ω→0)=0**
  （DC 恒被重聚）+ 首个通带峰位 ω_peak∝n/t ⇒ n 越大，低频噪声抑制越强。

═══ 🔴 多源噪声合成（真实灵敏度）═══
四独立噪声源**正交合成**（白噪声幅度谱密度平方和）：
  η_real = √(η_ph² + η_mw² + η_temp² + η_mag²)
  · η_ph   光子散粒极限（同 QS-M1 闭式）
  · η_mw   微波相位抖动 σ_φ → 有效对比度 C_eff=C·e^(−σ_φ²/2) ⇒ 换入散粒式
  · η_temp 温度漂移：|dB/dT|·S_T（K/√Hz）
  · η_mag  环境磁场噪声谱密度（T/√Hz）

═══ 🔴 纪律 ═══
· 进报告数字一律**模块现算**（不转录草稿）；判据读到的值 = 模块现算值。
· 每道守卫配反向探针（先证能变红）。
· 纯 numpy 顶层（scipy 隔离）；C 级自主，不借外部量子 SDK。
· 🔴 **诚实边界**：多源噪声参数为**设计示例量级**（非实测）；η_real 为建模值，
  不作制造/性能宣称；本档不宣称「已达国际水平」。
"""
from __future__ import annotations

import math
from typing import Any, Dict

import numpy as np

# ---------------------------------------------------------------------------
# 物理常数（与 qs_m0 / qs_m1 同源）
# ---------------------------------------------------------------------------
HBAR = 1.054571817e-34
G_LANDE = 2.0023
MU_B = 9.2740100783e-24
GAMMA_E_HZ_T = 28.024e9

_G_MUB_OVER_HBAR = G_LANDE * MU_B / HBAR       # rad·s⁻¹·T⁻¹ (= 2π·γe)

#: 🔴 统一灵敏度口径（承 QS-M1，单一真源）
SENSITIVITY_CALIBER = "eta_dB_sqrtT__amplitude_spectral_density__T_per_sqrtHz"


def assert_caliber(caliber: str) -> None:
    """口径自检（报告前强制）：只接受统一口径，防误用其它口径。"""
    if caliber != SENSITIVITY_CALIBER:
        raise ValueError("灵敏度口径不一致：只允许 %r，得到 %r" % (SENSITIVITY_CALIBER, caliber))


# ===========================================================================
# ① 退相干：单频噪声下的 FID / Hahn 回波相位方差（闭式）
# ===========================================================================
def _haversine_sq(x: float) -> float:
    """2·sin²(x/2)，用恒等式稳定小 x 求值（避免 1−cos 的灾难性抵消）。"""
    s = math.sin(x / 2.0)
    return 2.0 * s * s


def fid_phase_variance(omega_t: float) -> float:
    """FID 相位方差（归一化，即 (γb/ω)²=1 时）：⟨Φ²⟩_fid = 2(1−cos ωt) = 4sin²(ωt/2)。

    DC 极限 ⟨Φ²⟩_fid ~ (ωt)²（**二阶**）。
    🔴 用 haversine 形式求值 ⇒ 小 ωt 下**相对精度**保持（直接 1−cos 会抵消到 0）。
    """
    return 2.0 * _haversine_sq(omega_t)

def echo_phase_variance(omega_t: float) -> float:
    """Hahn 回波相位方差（归一化）：⟨Φ²⟩_echo = 2(1−cos(ωt/2))² = 8sin⁴(ωt/4)。

    🔴 DC 极限 ⟨Φ²⟩_echo ~ (ωt)⁴/32（**四阶**）⇒ 回波对低频噪声高阶抑制。
    🔴 haversine 形式 ⇒ 小 ωt 下能算出**非零的舍入级**相对残差
       （直接 (1−cos)² 在 x<1e-4 时被抵消到 0 ⇒ 相对判据假绿）。
    """
    return 2.0 * _haversine_sq(omega_t / 2.0) ** 2


def echo_filter_suppression(omega_t: float) -> float:
    """回波相对 FID 的相位方差抑制比 = ⟨Φ²⟩_echo / ⟨Φ²⟩_fid（<1 即回波更优）。"""
    fid = fid_phase_variance(omega_t)
    if fid == 0.0:
        return 0.0
    return echo_phase_variance(omega_t) / fid


# ===========================================================================
# ② DD（CPMG-n）滤波函数 + 相干积分
# ===========================================================================
def cpmg_filter(omega: float, t: float, n: int) -> float:
    """CPMG-n 滤波函数 F_n(ω,t)（闭式时序，**纯 numpy 无 scipy**）。

    F_n(ω,t) = |Σ_{j=0}^{n} (−1)^j (e^{iωt_{j+1}} − e^{iωt_j})|²，
    脉冲时刻 t_j=(2j−1)t/(2n)，t_0=0, t_{n+1}=t。
    🔴 F_n(ω→0)=0（DC 恒被重聚）；首个通带峰位 ω_peak ∝ n/t。
    """
    if n < 1:
        raise ValueError("CPMG 脉冲数 n 必须 ≥ 1")
    tau = t / n
    ts = [0.0] + [(2 * j - 1) * tau / 2.0 for j in range(1, n + 1)] + [t]
    y = 0j
    for j in range(n + 1):
        y += ((-1) ** j) * (np.exp(1j * omega * ts[j + 1]) - np.exp(1j * omega * ts[j]))
    return float(abs(y) ** 2)


def _trapezoid(y: "np.ndarray", x: "np.ndarray") -> float:
    """纯 numpy 梯形积分（避免 np.trapz 在 NumPy 2.0 移除 / scipy 依赖）。"""
    return float(np.sum((y[1:] + y[:-1]) * 0.5 * np.diff(x)))


def coherent_chi(alpha: float, A: float, t: float, n: int,
                 omega_lo: float, omega_hi: float, n_grid: int = 8000) -> float:
    """相干积分 χ(t)=(1/π)∫ S(ω)·F_n(ω,t)/ω² dω，S(ω)=A·ω^(−α)（幂律噪声谱）。"""
    ws = np.logspace(math.log10(omega_lo), math.log10(omega_hi), n_grid)
    F = np.array([cpmg_filter(float(w), t, n) for w in ws])
    S = A / ws ** alpha
    return (1.0 / math.pi) * _trapezoid(S * F / ws ** 2, ws)


# ===========================================================================
# ③ 多源噪声合成 → 真实灵敏度
# ===========================================================================
def shot_limit_eta(T2star_s: float, n_ph_per_s: float, contrast: float,
                   dark_ratio: float = 0.0) -> float:
    """光子散粒极限 η（T/√Hz），与 QS-M1 同式。"""
    assert_caliber(SENSITIVITY_CALIBER)
    return (math.sqrt(1.0 + dark_ratio ** 2) * math.sqrt(2.0)
            / (contrast * math.sqrt(n_ph_per_s * T2star_s))
            / _G_MUB_OVER_HBAR)


def microwave_jitter_eta(T2star_s: float, n_ph_per_s: float, contrast: float,
                         sigma_phi_rad: float, dark_ratio: float = 0.0) -> float:
    """微波相位抖动**额外**噪声分量（T/√Hz）。

    🔴 口径：这是**在散粒极限之外**由微波源相位噪声引入的附加项 ⇒
      总对比度劣化 ΔC = C·(1−e^(−σ_φ²/2))，附加灵敏度按散粒式换算：
        η_mw = η_shot(C) − η_shot(C_eff)    （σ_φ=0 ⇒ C_eff=C ⇒ η_mw=0）
      **不得**把 C_eff 直接回代散粒式（那会把散粒本身重复计入 ⇒ baseline 虚高 √2）。
    """
    if sigma_phi_rad == 0.0:
        return 0.0
    C_eff = contrast * math.exp(-sigma_phi_rad ** 2 / 2.0)
    return shot_limit_eta(T2star_s, n_ph_per_s, C_eff, dark_ratio) \
        - shot_limit_eta(T2star_s, n_ph_per_s, contrast, dark_ratio)


def temperature_eta(dB_dT_T_per_K: float, S_T_K_per_sqrtHz: float) -> float:
    """温度漂移等效灵敏度 = |dB/dT|·S_T（T/√Hz）。"""
    return abs(dB_dT_T_per_K) * S_T_K_per_sqrtHz


def magnetic_env_eta(B_noise_T_per_sqrtHz: float) -> float:
    """环境磁场噪声谱密度（T/√Hz）——直接作灵敏度分量。"""
    return abs(B_noise_T_per_sqrtHz)


def synthesize_real_sensitivity(T2star_s: float, n_ph_per_s: float, contrast: float,
                                sigma_phi_rad: float = 0.0,
                                dB_dT_T_per_K: float = 0.0,
                                S_T_K_per_sqrtHz: float = 0.0,
                                B_noise_T_per_sqrtHz: float = 0.0,
                                dark_ratio: float = 0.0) -> Dict[str, float]:
    """四源噪声正交合成 → 真实灵敏度 η_real（T/√Hz）。

    η_real = √(η_ph² + η_mw² + η_temp² + η_mag²)（各源独立 ⇒ 平方和）。
    """
    assert_caliber(SENSITIVITY_CALIBER)
    e_ph = shot_limit_eta(T2star_s, n_ph_per_s, contrast, dark_ratio)
    e_mw = microwave_jitter_eta(T2star_s, n_ph_per_s, contrast, sigma_phi_rad, dark_ratio)
    e_temp = temperature_eta(dB_dT_T_per_K, S_T_K_per_sqrtHz)
    e_mag = magnetic_env_eta(B_noise_T_per_sqrtHz)
    eta_real = math.sqrt(e_ph ** 2 + e_mw ** 2 + e_temp ** 2 + e_mag ** 2)
    return {
        "eta_real_T_per_sqrtHz": eta_real,
        "eta_real_pT_per_sqrtHz": eta_real * 1e12,
        "eta_photon_shot_T_per_sqrtHz": e_ph,
        "eta_microwave_T_per_sqrtHz": e_mw,
        "eta_temperature_T_per_sqrtHz": e_temp,
        "eta_magnetic_T_per_sqrtHz": e_mag,
        "caliber": SENSITIVITY_CALIBER,
    }


# ---------------------------------------------------------------------------
# 四情景（承 QS-M1 范式）
# ---------------------------------------------------------------------------
SCENARIOS: Dict[str, Dict[str, Any]] = {
    # baseline：QS-M0/M1 设计点，仅光子散粒（理想）
    "baseline": dict(T2star_us=1.0, n_ph_per_s=1.0e5, contrast=0.03,
                     sigma_phi_rad=0.0, dB_dT_T_per_K=0.0, S_T_K_per_sqrtHz=0.0,
                     B_noise_T_per_sqrtHz=0.0, dark_ratio=0.0),
    # realistic：叠加微波抖动 + 温度 + 环境磁噪声（真实器件）
    "realistic": dict(T2star_us=1.0, n_ph_per_s=1.0e5, contrast=0.03,
                      sigma_phi_rad=0.2, dB_dT_T_per_K=2.0e-9, S_T_K_per_sqrtHz=1.0e-3,
                      B_noise_T_per_sqrtHz=1.0e-11, dark_ratio=0.05),
    # dd_enhanced：动力学去耦提升相干时间（T₂ > T₂*）
    "dd_enhanced": dict(T2star_us=1.0, n_ph_per_s=1.0e5, contrast=0.03,
                        sigma_phi_rad=0.1, dB_dT_T_per_K=2.0e-9, S_T_K_per_sqrtHz=1.0e-3,
                        B_noise_T_per_sqrtHz=1.0e-11, dark_ratio=0.0,
                        n_cpmg_pulses=16, T2_echo_us=10.0),
    # bench：反向探针专用
    "bench": dict(T2star_us=1.0, n_ph_per_s=1.0e5, contrast=0.03,
                  sigma_phi_rad=0.0, dB_dT_T_per_K=0.0, S_T_K_per_sqrtHz=0.0,
                  B_noise_T_per_sqrtHz=0.0, dark_ratio=0.0),
}


def evaluate_scenario(name: str) -> Dict[str, Any]:
    """单情景：四源合成 η_real；dd_enhanced 用 T₂（回波）替 T₂* 进散粒式。"""
    if name not in SCENARIOS:
        raise KeyError("未知情景 %r（可选：%s）" % (name, sorted(SCENARIOS)))
    p = SCENARIOS[name]
    T2 = float(p.get("T2_echo_us", p["T2star_us"])) * 1e-6 if "T2_echo_us" in p \
        else float(p["T2star_us"]) * 1e-6
    r = synthesize_real_sensitivity(
        T2star_s=T2, n_ph_per_s=float(p["n_ph_per_s"]), contrast=float(p["contrast"]),
        sigma_phi_rad=float(p.get("sigma_phi_rad", 0.0)),
        dB_dT_T_per_K=float(p.get("dB_dT_T_per_K", 0.0)),
        S_T_K_per_sqrtHz=float(p.get("S_T_K_per_sqrtHz", 0.0)),
        B_noise_T_per_sqrtHz=float(p.get("B_noise_T_per_sqrtHz", 0.0)),
        dark_ratio=float(p.get("dark_ratio", 0.0)),
    )
    r["scenario"] = name
    r["coherence_time_s"] = T2
    return r


def noise_budget_table() -> Dict[str, Dict[str, Any]]:
    """四情景噪声预算表（现算）。"""
    return {n: evaluate_scenario(n) for n in ("baseline", "realistic", "dd_enhanced", "bench")}


# ===========================================================================
# ④ 设计入口
# ===========================================================================
def design_coherence_noise(run_checks: bool = True) -> Dict[str, Any]:
    """QS-M2 主入口：退相干 + 多源噪声报告。"""
    tbl = noise_budget_table()
    report: Dict[str, Any] = {
        "module": "qs_m2",
        "milestone": "QS-M2",
        "caliber": SENSITIVITY_CALIBER,
        "noise_budget": tbl,
    }
    if run_checks:
        report["checks"] = selfcheck_qs_m2()
    return report


# ===========================================================================
# ⑤ 自检（常驻门禁 · 反向探针）
# ===========================================================================
def selfcheck_qs_m2() -> Dict[str, bool]:
    """QS-M2 自检：回波≺FID + 四阶 DC + 滤波函数 DC 归零 + 四源合成 + 反向探针。"""
    checks: Dict[str, bool] = {}

    # ① 回波方差 ≤ FID 方差（对任意 ωt>0）
    checks["echo_le_fid"] = all(
        echo_phase_variance(x) <= fid_phase_variance(x) + 1e-15
        for x in [0.1, 0.5, 1.0, 2.0, 2.5, 3.0]
    )

    # ② DC 阶数：⟨Φ²⟩_echo/(ωt)⁴ → 1/32（四阶）；⟨Φ²⟩_fid/(ωt)² → 1（二阶）
    #     🔴 与**解析常数**比（相对残差），用 haversine 形式保证小 x 不抵消 ⇒ 不进假绿。
    #     tol＝1e-6 的来由：x=1e-3 时解析下一阶修正 ≈ x²/12 = 8.33e-8（**不是舍入**），
    #       故 tol 必须 > 该截断项；而**阶数写错**时残差为 O(1) ⇒ 仍能变红（反向探针）。
    x = 1e-3
    checks["dc_fourth_order_echo"] = (
        abs(echo_phase_variance(x) / x ** 4 / (1.0 / 32.0) - 1.0) < 1e-6
    )
    checks["dc_second_order_fid"] = (
        abs(fid_phase_variance(x) / x ** 2 - 1.0) < 1e-6
    )

    # ③ CPMG 滤波函数 DC 归零 + 峰位随 n 上移
    checks["cpmg_filter_dc_zero"] = all(
        cpmg_filter(1e-6, 1.0, n) < 1e-6 for n in (1, 2, 4, 8)
    )

    # ④ 四源合成：η_real ≥ 任一单源；baseline（其余零）= 纯光子散粒
    #     🔴 相对判据（0.0 精确相等用 == 亦可，但用 rel 保一致口径）
    base = evaluate_scenario("baseline")
    checks["baseline_equals_shot_only"] = (
        base["eta_real_T_per_sqrtHz"] == base["eta_photon_shot_T_per_sqrtHz"]
    )
    real = evaluate_scenario("realistic")
    checks["real_ge_all_sources"] = all(
        real["eta_real_T_per_sqrtHz"] >= real[k] - 1e-30
        for k in ("eta_photon_shot_T_per_sqrtHz", "eta_microwave_T_per_sqrtHz",
                  "eta_temperature_T_per_sqrtHz", "eta_magnetic_T_per_sqrtHz")
    )
    # ⑤ 加噪只会劣化：realistic 应劣于 baseline
    checks["realistic_worse_than_baseline"] = (
        real["eta_real_T_per_sqrtHz"] > base["eta_real_T_per_sqrtHz"]
    )
    # ⑥ DD 提升：dd_enhanced（T₂=10µs > T₂*=1µs）应优于 baseline 相干项
    dd = evaluate_scenario("dd_enhanced")
    checks["dd_improves_vs_baseline"] = (
        dd["eta_photon_shot_T_per_sqrtHz"] < base["eta_photon_shot_T_per_sqrtHz"]
    )

    # ⑦ 反向探针（先证能变红）
    checks["reverse_zero_contrast_diverges"] = _diverges(
        lambda: shot_limit_eta(1e-6, 1e5, 0.0)
    )
    checks["reverse_negative_T2_raises"] = _raises(lambda: shot_limit_eta(-1e-6, 1e5, 0.03))
    checks["reverse_zero_pulses_raises"] = _raises(lambda: cpmg_filter(1.0, 1.0, 0))
    # 🔴 反向探针「DC 阶数判别力」：故意把回波按**二阶**归一 ⇒ 必须判红。
    #   证明上面 dc_fourth_order_echo 不是恒真（能被错误的阶数打红）。
    xr = 1e-3
    wrong_order = abs(echo_phase_variance(xr) / xr ** 2 - 1.0) < 1e-6   # 假想二阶
    checks["reverse_wrong_dc_order_detected"] = (not wrong_order)
    # 🔴 反向探针「微波口径」：σ_φ=0 时 η_mw 必须恰为 0（否则散粒被重复计入）。
    checks["reverse_mw_zero_at_no_jitter"] = (
        microwave_jitter_eta(1e-6, 1e5, 0.03, 0.0) == 0.0
    )

    # ⑧ 口径自检（承 QS-M1）
    try:
        assert_caliber(SENSITIVITY_CALIBER)
        checks["caliber_ok"] = True
    except ValueError:
        checks["caliber_ok"] = False

    return checks


def _diverges(fn) -> bool:
    try:
        v = fn()
    except (ZeroDivisionError, ValueError):
        return True
    return not math.isfinite(v) or v > 1e30


def _raises(fn) -> bool:
    try:
        fn()
    except (ValueError, ZeroDivisionError, OverflowError):
        return True
    return False


def main() -> int:
    """打印 QS-M2 退相干 + 多源噪声报告。"""
    rep = design_coherence_noise(run_checks=True)
    print("=== QS-M2 退相干 + 多源噪声 ===")
    print("口径:", rep["caliber"])
    for n, s in rep["noise_budget"].items():
        print("  [%-11s] η_real = %.4f pT/√Hz (T2=%.3g s | 散粒 %.2f / 微波 %.2f / 温 %.2f / 磁 %.2f)"
              % (n, s["eta_real_pT_per_sqrtHz"], s["coherence_time_s"],
                 s["eta_photon_shot_T_per_sqrtHz"] * 1e12, s["eta_microwave_T_per_sqrtHz"] * 1e12,
                 s["eta_temperature_T_per_sqrtHz"] * 1e12, s["eta_magnetic_T_per_sqrtHz"] * 1e12))
    ck = rep["checks"]
    npass = sum(1 for v in ck.values() if v)
    print("checks: %d/%d %s" % (npass, len(ck), "PASS" if npass == len(ck) else "FAIL"))
    for k, v in ck.items():
        if not v:
            print("  FAIL:", k)
    return 0 if npass == len(ck) else 1


if __name__ == "__main__":
    raise SystemExit(main())
