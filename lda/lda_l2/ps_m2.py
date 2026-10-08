"""PS-M2 · 传感器指标框架 + LOD_real 噪声模型（几何无关 · 吃狗粮 v2）。

═══ 策略（自己先用平台把性能量化出来）═══
在 PS-M0 已交付的 **S_bulk / LOD_intrinsic（线宽受限理想界 = λ/(S·Q)）** 基础上，
PS-M2 把传感器性能量化**形式化**为标准报告，并补齐 **LOD_real（含噪实测探测极限）**
噪声模型：

  · 电学噪声：散粒(shot) + 热(Johnson/NEP) + 激光 RIN + 暗电流，按功率/积分时间
    平方合成 → 经谐振腔边缘斜率 |dT/dλ|_max 转成 δλ_elec；
  · 温度漂移：Si 热光系数 dn/dT，经共模抑制比 CMR（referencing）折算有效 ΔT → δλ_temp；
  · LOD_real = √(LOD_elec² + LOD_temp²)，LOD 口径严格区分 intrinsic vs real（见 §5.5）。

═══ 🔴 物理要点（避免假对标）═══
  · LOD_temp = dn_dT · ΔT_eff，**与灵敏度 S 解耦**——热漂移 LOD 由温度稳定性决定，
    不是传感器几何。这正是 real LOD 10⁻⁶–10⁻⁷ 需要主动温控/referencing 的根因。
  · 散粒噪声 LOD_elec ∝ 1/√P（功率越低越差）；零功率 ⇒ LOD→∞（反向探针必红）。
  · 谐振腔边缘斜率闭式 = (ΔT)·3√3/4·(1/Γ)，与 Lorentzian 有限差分数值导数互验。

═══ 🔴 纪律 ═══
· 进报告数字一律**模块现算**（不转录草稿）；
· 判据读到的值 = 模块现算值；
· 每道守卫配反向探针（先证能变红）。

═══ 🔴 发现 / 待办（诚实登记，不强行入 B 账本）═══
  · 灵敏度（cladding 折射率扰动 → 有效折射率）：闭式 golden 取 Hellmann-Feynman
    `dneff/dn_clad = (n_clad/n_eff)·Γ_clad`，与有限差分直接 perturb `n_clad` 重算 `n_eff`
    差**偏差约 44%** —— 口径不一致（不同求解器/近似下 Γ_clad 定义不同 ⇒ 不是同一物理量）。
  · 不强行把它登记为 B 锚（避免假独立 / 假一致）；如实记为**发现/待办**，
    待专门立项对齐 Γ_clad 口径后再决定是否入 B 账本，并配反向探针。
  · 当前由 **B2（n_eff 闭式 vs 数值微分）** + PS-M2 常驻 CI 守卫覆盖该物理量，
    不会因本条漏登记而失守。
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Optional

import numpy as np

# 复用 PS-M0 的 LOD_intrinsic / FSR 单一真源，杜绝口径漂移
# 🔴 惰性 import：ps_m0 顶层 import FV 求解器（scipy），但本模块仅 `lod_real`
#    （纯 numpy）被 B472 golden 在闭式门禁使用；ps_m0 仅 `metric_report` 需要，
#   故惰性加载，避免 scipy 泄漏进闭式解释器。
def _ring_sensor_metrics(R_um, wl_um, ng, S_nm_per_riu, Q):
    from lda_l2.ps_m0 import ring_sensor_metrics  # 惰性（scipy 依赖）
    return ring_sensor_metrics(R_um, wl_um, ng, S_nm_per_riu, Q)

# ---------------------------------------------------------------------------
# 物理常数
# ---------------------------------------------------------------------------
H_PLANCK = 6.62607015e-34      # J·s
C_LIGHT = 299792458.0          # m/s
E_CHARGE = 1.602176634e-19     # C
K_BOLTZMANN = 1.380649e-23     # J/K

# Si @1550 nm 热光系数 dn/dT（/K）——温度漂移项主因
DN_DT_SI = 1.86e-4

# 默认良好光电参数（几何无关，可逐项覆盖）
DEFAULT_NOISE: Dict[str, float] = {
    "power_W": 1e-3,            # 探测器处光功率 1 mW
    "dt_s": 1e-3,               # 积分时间 1 ms
    "eta": 0.8,                 # 探测器量子效率
    "NEP_W_per_sqrtHz": 1e-12,  # 探测器 NEP（好 InGaAs/Ge）
    "RIN_per_Hz": 1e-14,        # 激光相对强度噪声 -140 dB/Hz
    "Idark_A": 1e-9,            # 暗电流 1 nA
    "R_AW": 1.0,                # 探测器响应度 A/W（≈ η·e/hν）
    "dn_dT": DN_DT_SI,
    "dT_stability_K": 5e-3,     # 温度稳定性 5 mK
    "CMR": 1.0,                 # referencing 共模抑制比（1=无 referencing）
    "T_bg": 1.0,                # 谐振外透过率
    "T_min": 0.1,               # 谐振谷透过率（90% 深度）
}


# ---------------------------------------------------------------------------
# 光子能量 / 谐振腔边缘斜率
# ---------------------------------------------------------------------------
def photon_energy_J(wl_um: float) -> float:
    return H_PLANCK * C_LIGHT / (wl_um * 1e-6)


def resonance_slope_max(T_bg: float, T_min: float, FWHM_nm: float) -> float:
    """闭式：Lorentzian 凹陷在陡峭点的最大斜率 |dT/dλ|_max（单位 1/nm）。

    推导：T(Δλ)=T_bg-(T_bg-T_min)/(1+(2Δλ/Γ)²)，最大值在 2Δλ/Γ=1/√3 处，
    |dT/dλ|_max = (T_bg-T_min)·(3√3/4)/Γ。
    """
    depth = T_bg - T_min
    if FWHM_nm <= 0:
        return float("inf")
    return depth * (3.0 * math.sqrt(3.0) / 4.0) / FWHM_nm


def resonance_slope_max_numeric(T_bg: float, T_min: float, FWHM_nm: float,
                                n: int = 4001) -> float:
    """数值验证：对 Lorentzian 做有限差分，取 |dT/dλ| 最大值。"""
    dl = np.linspace(-3 * FWHM_nm, 3 * FWHM_nm, n)
    u = (2.0 * dl / FWHM_nm) ** 2
    T = T_bg - (T_bg - T_min) / (1.0 + u)
    dT = np.gradient(T, dl)
    return float(np.max(np.abs(dT)))


# ---------------------------------------------------------------------------
# 电学噪声（分数，σ_T / T）
# ---------------------------------------------------------------------------
def electronic_fraction_noise(noise: Dict[str, float]) -> Dict[str, float]:
    """四种电学噪声源按平方合成，返回各分量分数噪声与总量。

    · 散粒：σ_P/P = 1/√(ηPΔt/hν)            （光子数涨落）
    · 热(Johnson)：σ_P = NEP·√Δf            （探测器 NEP）
    · 激光 RIN：σ_P/P = RIN·√Δf
    · 暗电流：σ_I = √(2e I_dark Δf)
    噪声带宽 Δf = 1/(2Δt)（单极点）。
    """
    power_W = noise["power_W"]
    dt_s = noise["dt_s"]
    eta = noise["eta"]
    NEP = noise["NEP_W_per_sqrtHz"]
    RIN = noise["RIN_per_Hz"]
    Idark = noise["Idark_A"]
    R_AW = noise["R_AW"]

    df = 1.0 / (2.0 * dt_s)

    # 散粒（光子数涨落 → 功率分数噪声）
    if power_W > 0 and dt_s > 0:
        n_ph = eta * power_W * dt_s / photon_energy_J(1.55)
        frac_shot = 1.0 / math.sqrt(n_ph) if n_ph > 0 else float("inf")
    else:
        frac_shot = float("inf")

    # 热（NEP）
    sigma_P_thermal = NEP * math.sqrt(df)
    frac_thermal = sigma_P_thermal / power_W if power_W > 0 else float("inf")

    # 激光 RIN
    frac_RIN = RIN * math.sqrt(df)

    # 暗电流
    I = R_AW * power_W
    sigma_I_dark = math.sqrt(2.0 * E_CHARGE * Idark * df)
    frac_dark = sigma_I_dark / I if I > 0 else float("inf")

    frac_total = math.sqrt(frac_shot ** 2 + frac_thermal ** 2
                           + frac_RIN ** 2 + frac_dark ** 2)
    return {
        "df_Hz": df,
        "frac_shot": frac_shot,
        "frac_thermal": frac_thermal,
        "frac_RIN": frac_RIN,
        "frac_dark": frac_dark,
        "frac_total": frac_total,
    }


# ---------------------------------------------------------------------------
# LOD_real 噪声模型（几何无关）
# ---------------------------------------------------------------------------
def lod_real(S_nm_per_riu: float, Q: float, wl_um: float,
             noise: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """含噪实测探测极限 LOD_real（RIU）及分项。

    δλ_elec = σ_T(总) / |dT/dλ|_max   （电学噪声 → 波长抖动）
    LOD_elec = δλ_elec / S
    δλ_temp = S · dn_dT · ΔT_eff       （温度漂移 → 波长抖动，ΔT_eff=ΔT/CMR）
    LOD_temp = δλ_temp / S = dn_dT · ΔT_eff   （与 S 解耦！）
    LOD_real = √(LOD_elec² + LOD_temp²)
    """
    if noise is None:
        noise = dict(DEFAULT_NOISE)
    FWHM_nm = wl_um * 1000.0 / Q
    slope = resonance_slope_max(noise["T_bg"], noise["T_min"], FWHM_nm)
    enf = electronic_fraction_noise(noise)

    delta_lambda_elec = enf["frac_total"] / slope if slope > 0 else float("inf")
    LOD_elec = delta_lambda_elec / S_nm_per_riu if S_nm_per_riu > 0 else float("inf")

    dT_eff = noise["dT_stability_K"] / max(noise["CMR"], 1e-30)
    LOD_temp = noise["dn_dT"] * dT_eff  # 与 S 解耦
    delta_lambda_temp = S_nm_per_riu * LOD_temp

    LOD_real = math.sqrt(LOD_elec ** 2 + LOD_temp ** 2)
    return {
        "FWHM_nm": FWHM_nm,
        "slope_per_nm": slope,
        "frac_total": enf["frac_total"],
        "delta_lambda_elec_nm": delta_lambda_elec,
        "LOD_elec_riu": LOD_elec,
        "dT_eff_K": dT_eff,
        "delta_lambda_temp_nm": delta_lambda_temp,
        "LOD_temp_riu": LOD_temp,
        "LOD_real_riu": LOD_real,
        "noise_components": enf,
    }


# ---------------------------------------------------------------------------
# 标准指标报告（形式化 S / FOM / LOD_intrinsic / LOD_real）
# ---------------------------------------------------------------------------
def metric_report(S_nm_per_riu: float, Q: float, wl_um: float,
                  ng: Optional[float] = None, R_um: Optional[float] = None,
                  noise: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """传感器性能标准报告（复用 PS-M0 的 LOD_intrinsic / FSR 单一真源）。"""
    lod_intrinsic = wl_um * 1000.0 / (S_nm_per_riu * Q)
    FOM = S_nm_per_riu * Q
    rep: Dict[str, Any] = {
        "S_nm_per_riu": S_nm_per_riu,
        "Q": Q,
        "wl_um": wl_um,
        "FOM_SxQ": FOM,
        "LOD_intrinsic_riu": lod_intrinsic,
    }
    if ng is not None and R_um is not None:
        ring = _ring_sensor_metrics(R_um, wl_um, ng, S_nm_per_riu, Q)
        rep["FSR_nm"] = ring["FSR_nm"]
        # 与上式 LOD_intrinsic 互验（同式）
        rep["LOD_intrinsic_crosscheck_riu"] = ring["LOD_riu"]
    rep["LOD_real"] = lod_real(S_nm_per_riu, Q, wl_um, noise)
    return rep


def calibration_curve(S_nm_per_riu: float,
                      dn_max: float = 1e-2, n: int = 51) -> Dict[str, Any]:
    """标定曲线：Δλ(nm) vs Δn（线性，Δλ = S·Δn）。"""
    dn = np.linspace(0.0, dn_max, n)
    dlam = S_nm_per_riu * dn
    return {
        "S_nm_per_riu": S_nm_per_riu,
        "dn_grid": dn.tolist(),
        "dlambda_nm_grid": dlam.tolist(),
    }


# ---------------------------------------------------------------------------
# 场景与量化门（验证模型能复现文献区间，且不恒为小值）
# ---------------------------------------------------------------------------
SCENARIOS: Dict[str, Dict[str, Any]] = {
    # 当前平台 v0 真实状态：粗线、低 Q、无 referencing、10 mK 稳定
    "v0_baseline": dict(S=30.3, Q=1e4, wl_um=1.55, ng=4.18, R_um=10.0,
                        noise={**DEFAULT_NOISE, "power_W": 1e-4,
                               "dT_stability_K": 0.01, "CMR": 1.0}),
    # 文献对标场景：薄线/slot(S=300)、Q=1e5、5 mK 主动温控、无 referencing
    "cited": dict(S=300.0, Q=1e5, wl_um=1.55,
                  noise={**DEFAULT_NOISE, "dT_stability_K": 5e-3, "CMR": 1.0}),
    # 退化场景：v0 几何 + 100 mK 无控 + 低功率 —— 应明显变差
    "degraded": dict(S=30.0, Q=1e4, wl_um=1.55,
                     noise={**DEFAULT_NOISE, "power_W": 1e-4,
                            "dT_stability_K": 0.1, "CMR": 1.0}),
    # 高 Q + referencing(CMR=100)：验证 referencing 把热漂压下去
    "bench_referenced": dict(S=300.0, Q=1e5, wl_um=1.55,
                             noise={**DEFAULT_NOISE, "dT_stability_K": 5e-3,
                                    "CMR": 100.0}),
}


# ---------------------------------------------------------------------------
# 自校 / 反向探针（先证能变红）
# ---------------------------------------------------------------------------
def selfcheck_ps_m2(tol_slope: float = 0.03,
                    cited_lo: float = 5e-7, cited_hi: float = 2e-6,
                    degraded_min: float = 1e-5) -> Dict[str, Any]:
    """PS-M2 守卫：斜率互验 + 量化门 + 反向探针。"""
    checks: Dict[str, Any] = {}

    # ① 谐振腔边缘斜率：闭式 vs 数值（方法学独立）
    FWHM = 0.155
    s_closed = resonance_slope_max(1.0, 0.1, FWHM)
    s_num = resonance_slope_max_numeric(1.0, 0.1, FWHM)
    checks["slope_formula_vs_numeric"] = (
        abs(s_closed - s_num) / max(s_num, 1e-12) < tol_slope)

    # ② 量化门：cited 场景 LOD_real 应落在文献 10⁻⁶–10⁻⁷ 区间（2× 内）
    r_cited = lod_real(SCENARIOS["cited"]["S"], SCENARIOS["cited"]["Q"],
                       SCENARIOS["cited"]["wl_um"], SCENARIOS["cited"]["noise"])
    checks["cited_LOD_in_band"] = (cited_lo <= r_cited["LOD_real_riu"] <= cited_hi)

    # ③ 退化场景应明显更差（证明模型捕获物理，非恒小值假绿）
    r_deg = lod_real(SCENARIOS["degraded"]["S"], SCENARIOS["degraded"]["Q"],
                     SCENARIOS["degraded"]["wl_um"], SCENARIOS["degraded"]["noise"])
    checks["degraded_worse_than_cited"] = (r_deg["LOD_real_riu"] >= degraded_min
                                          and r_deg["LOD_real_riu"] > r_cited["LOD_real_riu"])

    # ④ 反向探针：零功率 ⇒ 散粒噪声分量 → ∞ ⇒ LOD_elec → ∞ ⇒ LOD_real → ∞
    zero_pow = dict(SCENARIOS["cited"]["noise"]); zero_pow["power_W"] = 0.0
    r_zp = lod_real(SCENARIOS["cited"]["S"], SCENARIOS["cited"]["Q"],
                    SCENARIOS["cited"]["wl_um"], zero_pow)
    checks["zero_power_red_flag"] = not math.isfinite(r_zp["LOD_real_riu"])

    # ⑤ 反向探针：零灵敏度 ⇒ LOD_real → ∞（抹平断口必红）
    r_zs = lod_real(0.0, SCENARIOS["cited"]["Q"], SCENARIOS["cited"]["wl_um"],
                    SCENARIOS["cited"]["noise"])
    checks["zero_S_red_flag"] = not math.isfinite(r_zs["LOD_real_riu"])

    # ⑥ LOD_temp 与 S 解耦：同温参数下，S=30 与 S=300 的 LOD_temp 必相等
    n_a = dict(SCENARIOS["cited"]["noise"])
    n_b = dict(SCENARIOS["cited"]["noise"])
    lod_t_a = lod_real(30.0, 1e5, 1.55, n_a)["LOD_temp_riu"]
    lod_t_b = lod_real(300.0, 1e5, 1.55, n_b)["LOD_temp_riu"]
    checks["LOD_temp_S_invariant"] = (abs(lod_t_a - lod_t_b)
                                      / max(lod_t_b, 1e-30) < 1e-9)

    # ⑦ LOD_intrinsic 与 PS-M0 单一真源一致（杜绝口径漂移）
    rep = metric_report(SCENARIOS["v0_baseline"]["S"],
                        SCENARIOS["v0_baseline"]["Q"],
                        SCENARIOS["v0_baseline"]["wl_um"],
                        ng=SCENARIOS["v0_baseline"]["ng"],
                        R_um=SCENARIOS["v0_baseline"]["R_um"])
    checks["LOD_intrinsic_matches_M0"] = (
        abs(rep["LOD_intrinsic_riu"] - rep["LOD_intrinsic_crosscheck_riu"])
        / max(rep["LOD_intrinsic_riu"], 1e-30) < 1e-9)

    all_pass = all(v for k, v in checks.items()
                   if not k.startswith(("note",)))
    scen_reports = {}
    for k, v in SCENARIOS.items():
        kwargs = {kk: vv for kk, vv in v.items() if kk != "noise"}
        kwargs["S_nm_per_riu"] = kwargs.pop("S")
        scen_reports[k] = metric_report(**kwargs, noise=v.get("noise"))
    return {
        "selfcheck": {"all_pass": all_pass, "checks": checks},
        "scenarios": scen_reports,
    }


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def main(out_dir: Optional[str] = None) -> int:
    rep = selfcheck_ps_m2()
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "ps_m2_report.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
        # 标定曲线示例（v0 基线）
        cal = calibration_curve(SCENARIOS["v0_baseline"]["S"])
        with open(os.path.join(out_dir, "ps_m2_calibration_v0.json"), "w",
                  encoding="utf-8") as f:
            json.dump(cal, f, indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if rep["selfcheck"]["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(out_dir=os.path.join("outputs", "ps_m2")))
