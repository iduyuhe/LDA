"""PS-M4 · 生物/化学功能化与表面传感（吃狗粮 v4）。

═══ 策略（把 PS-M3 的 B460 体灵敏度延伸到真实生物传感读出机制）═══
PS-M3 用真实 SOI 平板波导把体灵敏度 `dneff/dn_clad = (n_clad/n_eff)·Γ_clad` 对齐立项（B460）。
真实生物/化学传感**不是**改整体包层折射率，而是：受体功能化在波导表面形成**薄吸附层**
（adlayer：厚度 ds、折射率 n_a），analyte 结合改变该层折射率，由倏逝场**表面灵敏度**检出。
PS-M4 把这条物理链补全并判决化：

  · 表面/吸附层灵敏度 `S_surface = d n_eff/d n_a = (n_a/n_eff)·Γ_adlayer`，
    Γ_adlayer = 吸附层 [a, a+ds] 内实际场 L² 份额 = Γ_clad·(1−e^(−2γ·ds))（γ=倏逝衰减常数）；
  · 倏逝穿透深度 `1/γ`、体/表灵敏度比 `1−exp(−2γ·ds)`（ds→∞ 退化为 B460 体灵敏度）；
  · 谐振波长位移 `Δλ = λ·Δn_eff/n_g`，其中 Δn_eff = S_surface·Δn_a；
  · 朗缪尔吸附：平衡覆盖度 `θ_eq=K_A·C/(1+K_A·C)` 与动力学 `θ(t)=θ_eq·(1−e^(−(k_on·C+k_off)·t))`
    （K_A=k_on/k_off）⇒ 时间分辨结合曲线 → 时间分辨 Δλ(t)；
  · de Feijter 质量标定 `Γ = (n_a−n_c)·ds/(dn/dc)`：把表面折射率变化换算成表面质量密度（µg/cm²），
    并给出时间分辨表面质量沉积 Γ(t)=Γ_sat·θ(t)。

═══ 🔴 物理要点 ═══
  · Γ_adlayer 必须用**实际场**的 L² 份额（与 B460 同口径）：Γ_adlayer = Γ_clad·(1−e^(−2γ·ds))；
    这正是 PS-M2 待办 B460 当初 44% 偏差的根因——Γ 口径错配。
  · 表面灵敏度 < 体灵敏度（有限 ds 只截获部分倏逝尾，Γ_adlayer<Γ_clad）；ds→∞ 两者退化一致
    （连续一致，非重复计数——与 B461 同源体检结论一致）。
  · Δλ 与 S_surface、Δn_a 成正比；Δn_a 又由覆盖度 θ 决定（线性有效介质近似，见诚实边界）。
  · 朗缪尔为理想单位点模型；B462 只证明「闭式 ⇄ RK4 积分」一致这一数学事实。

═══ 🔴 纪律 ═══
· 进报告数字一律**模块现算**（不转录草稿）；
· 判据读到的值 = 模块现算值；
· 每道守卫配反向探针（先证能变红）；
· 复用 PS-M2 `lod_real` 为噪声模型单一真源（杜绝口径漂移）；
· 复用 B-35 内核（`_batch_b35_numeric`）为表面灵敏度/朗缪尔数学单一真源。

═══ 诚实边界 ═══
· 几何/生物参数为**设计示例**（SOI 220nm 平板 / 水包层 @1550nm；adlayer 取蛋白层典型
  n_a≈1.45、ds≈50nm、K_A≈1e9 M⁻¹）。结论只可用于数值方法与量级，不得作制造/性能宣称。
· de Feijter 默认 `dn/dc≈0.182 cm³/g` 为**可见光波长**蛋白折射率增量；1550nm 处该值偏低一档，
  此处作一阶近似，真实标定须重测 1550nm 的 dn/dc。
· 线性覆盖模型 `Δn_a(θ)=Δn_sat·θ` 是一阶有效介质近似（低覆盖合理）；高覆盖需随 θ 重算 S_surface。
· S_surface 取 θ=0（无 analyte）几何增益作常增益，是表面位移量级估计的一阶近似。
· 平板波导是真实、可 fabrication 的平面波导传感器几何；本模块选平板是为让 HF golden 取**精确闭式 Γ**。
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Optional

import numpy as np

# 复用 PS-M2 噪声模型单一真源（LOD_real = √(LOD_elec² + LOD_temp²)）
from lda_l2.ps_m2 import DEFAULT_NOISE, lod_real  # noqa: E402
# 复用 PS-M3 体灵敏度物理链（B-34 批 · B460）做对照
from lda_harness._batch_b34_numeric import (  # noqa: E402
    slab_te0_neff,
    sensitivity_golden,
)
# 复用 PS-M4 数学核（B-35 批 · B461/B462）：表面灵敏度 + 朗缪尔
from lda_harness._batch_b35_numeric import (  # noqa: E402
    _slab_u_gamma,
    langmuir_rk4,
    langmuir_theta_eq,
    langmuir_theta_t,
    slab_gamma_adlayer_analytic,
    surface_sensitivity_fd,
    surface_sensitivity_golden,
)


# ---------------------------------------------------------------------------
# 默认真实几何（SOI 平板波导 / 水包层 @1550nm —— 设计示例）+ 默认吸附层
# ---------------------------------------------------------------------------
DEFAULT_GEO: Dict[str, float] = {
    "n_f": 3.4777,     # 晶体硅 @1550nm
    "n_c": 1.33,       # 水 / 待测物（平板波导传感窗）
    "n_a": 1.45,       # 蛋白吸附层典型折射率
    "d_um": 0.22,      # 平板厚度 220 nm
    "wl_um": 1.55,
}
#: 默认吸附层厚度（蛋白单层 ~ tens of nm）——设计示例
DEFAULT_DS_UM: float = 0.05  # 50 nm
#: de Feijter 默认折射率增量（蛋白，可见光波长值，1550nm 作一阶近似）
DEFAULT_DN_DC: float = 0.182  # cm³/g


# ---------------------------------------------------------------------------
# 真实表面灵敏度物理链（adlayer 场 L² 分数 / 倏逝深度 / 体-表比 / 谐振位移）
# ---------------------------------------------------------------------------
def real_surface_sensitivity(geo: Optional[Dict[str, float]] = None,
                             ds_um: float = DEFAULT_DS_UM) -> Dict[str, float]:
    """真实表面灵敏度物理链（HF golden 已 TMM-FD 验证，见 B461）+ 群折射率。

    返回：n_eff、γ(1/µm)、倏逝穿透深度 1/γ(µm)、Γ_clad、Γ_adlayer、体/表比
    `1−exp(−2γ·ds)`、S_surface(HF 闭式)、S_bulk(对照)、n_g(固定折射率 FD 下限)、
    S_nm_per_riu = λ·S_surface/n_g（adlayer 折射率变化 → 谐振位移）。
    """
    g = dict(DEFAULT_GEO) if geo is None else dict(geo)
    n_f, n_c, n_a, d, wl = g["n_f"], g["n_c"], g["n_a"], g["d_um"], g["wl_um"]
    neff = slab_te0_neff(n_f, n_c, d, wl)
    u, gamma = _slab_u_gamma(n_f, n_c, d, wl)
    decay_depth_um = (1.0 / gamma) if math.isfinite(gamma) and gamma > 0 else float("nan")
    g_clad = slab_gamma_adlayer_analytic(n_f, n_c, d, wl, ds_um=1e6)  # Γ_clad（ds→∞）
    g_ad = slab_gamma_adlayer_analytic(n_f, n_c, d, wl, ds_um)         # Γ_adlayer（有限 ds）
    bulk_surface_ratio = (1.0 - math.exp(-2.0 * gamma * ds_um)) if math.isfinite(gamma) else float("nan")
    s_surface = surface_sensitivity_golden(n_f, n_c, n_a, d, ds_um, wl)
    s_bulk = sensitivity_golden(n_f, n_c, d, wl)
    # 群折射率（固定折射率 FD 下限；真实 n_g 含材料色散会更高）
    dl = 1e-3
    neff_p = slab_te0_neff(n_f, n_c, d, wl + dl)
    neff_m = slab_te0_neff(n_f, n_c, d, wl - dl)
    dneff_dlam = (neff_p - neff_m) / (2.0 * dl)
    n_g = neff - wl * dneff_dlam
    S_nm_per_riu = (wl * 1000.0 / n_g) * s_surface if math.isfinite(n_g) else float("nan")
    return {
        "n_f": n_f, "n_c": n_c, "n_a": n_a, "d_um": d, "ds_um": ds_um, "wl_um": wl,
        "n_eff": neff, "gamma_inv_um": gamma, "decay_depth_um": decay_depth_um,
        "gamma_clad": g_clad, "gamma_adlayer": g_ad,
        "bulk_surface_ratio": bulk_surface_ratio,
        "S_surface": s_surface, "S_bulk": s_bulk,
        "S_align_residual": (abs(s_surface - surface_sensitivity_fd(n_f, n_c, n_a, d, ds_um, wl))
                             / s_surface) if s_surface > 0 else float("nan"),
        "n_g": n_g, "S_nm_per_riu": S_nm_per_riu,
    }


def resonance_shift(geo: Optional[Dict[str, float]] = None, ds_um: float = DEFAULT_DS_UM,
                    delta_n_a: float = 0.01) -> Dict[str, float]:
    """谐振波长位移：Δλ = λ·Δn_eff/n_g，其中 Δn_eff = S_surface·Δn_a。

    返回：S_surface、n_g、S_nm_per_riu、Δn_eff、Δλ_nm（adlayer 折射率变化 Δn_a 诱发的位移）。
    """
    s = real_surface_sensitivity(geo, ds_um)
    dneff = s["S_surface"] * delta_n_a
    dlam = (s["wl_um"] * 1000.0 / s["n_g"]) * dneff if math.isfinite(s["n_g"]) else float("nan")
    return {
        "S_surface": s["S_surface"], "n_g": s["n_g"],
        "S_nm_per_riu": s["S_nm_per_riu"],
        "delta_n_a": delta_n_a, "delta_neff": dneff, "delta_lambda_nm": dlam,
    }


# ---------------------------------------------------------------------------
# de Feijter 表面质量标定 + 朗缪尔链
# ---------------------------------------------------------------------------
def de_feijter_mass_density(n_a: float, n_c: float, ds_um: float,
                            dn_dc: float = DEFAULT_DN_DC) -> Dict[str, float]:
    """de Feijter 表面质量密度：Γ [g/cm²] = (n_a−n_c)·d[cm] / (dn/dc)[cm³/g]。

    d[cm] = ds_um·1e-4。返回 Γ_g_cm2 与 Γ_kg_m2（1 g/cm² = 10 kg/m²）。
    诚实边界：de Feijter 假设均匀单层、已知 dn/dc；默认 dn/dc 为可见光值（1550nm 偏低）。
    """
    d_cm = ds_um * 1e-4
    gamma_g_cm2 = (n_a - n_c) * d_cm / dn_dc if dn_dc > 0 else float("nan")
    gamma_kg_m2 = gamma_g_cm2 * 10.0 if math.isfinite(gamma_g_cm2) else float("nan")
    return {
        "dn_dc": dn_dc, "d_cm": d_cm,
        "gamma_g_cm2": gamma_g_cm2, "gamma_kg_m2": gamma_kg_m2,
    }


def langmuir_chain(k_on: float, k_off: float, C: float, t: float = 1e3,
                   geo: Optional[Dict[str, float]] = None, ds_um: float = DEFAULT_DS_UM,
                   dn_dc: float = DEFAULT_DN_DC) -> Dict[str, Any]:
    """朗缪尔链：平衡 θ_eq、动力学 θ(t)、对应表面质量 Γ(t)、时间分辨谐振位移 Δλ(t)。

    线性覆盖模型 Δn_a(θ) = Δn_sat·θ（Δn_sat = n_a−n_c）；Δλ(t) = λ·S_surface·Δn_a(t)/n_g。
    诚实边界：线性有效介质近似（低覆盖合理）；S_surface 取 θ=0 几何常增益。
    """
    theta_eq = langmuir_theta_eq(k_on, k_off, C)
    theta_t = langmuir_theta_t(k_on, k_off, C, t)
    g = dict(DEFAULT_GEO) if geo is None else dict(geo)
    n_a, n_c = g["n_a"], g["n_c"]
    dnsat = n_a - n_c
    s = real_surface_sensitivity(geo, ds_um)
    # 表面质量密度随时间：Γ(t) = Γ_sat·θ(t)
    gamma_sat = de_feijter_mass_density(n_a, n_c, ds_um, dn_dc)["gamma_kg_m2"]
    gamma_t = gamma_sat * theta_t
    # 时间分辨谐振位移：Δλ(t) = λ·S_surface·Δn_a(t)/n_g，Δn_a(t)=dnsat·θ(t)
    delta_n_a_t = dnsat * theta_t
    dlam_t = (s["wl_um"] * 1000.0 / s["n_g"]) * (s["S_surface"] * delta_n_a_t) \
        if math.isfinite(s["n_g"]) else float("nan")
    return {
        "theta_eq": theta_eq, "theta_t": theta_t, "t_s": t,
        "dnsat": dnsat, "gamma_sat_kg_m2": gamma_sat,
        "gamma_t_kg_m2": gamma_t, "delta_lambda_t_nm": dlam_t,
    }


# ---------------------------------------------------------------------------
# 表面传感 LOD（复用 PS-M2 噪声模型）：RIU → 表面质量密度
# ---------------------------------------------------------------------------
def surface_sensor_lod(geo: Optional[Dict[str, float]] = None, ds_um: float = DEFAULT_DS_UM,
                       noise: Optional[Dict[str, float]] = None, Q: float = 1.0e4,
                       dn_dc: float = DEFAULT_DN_DC) -> Dict[str, Any]:
    """表面传感 LOD：把真实表面灵敏度 S_nm_per_riu 代入 PS-M2 噪声模型得 LOD_real（RIU），
    再用 de Feijter 换算成表面质量探测极限 Γ_LOD = LOD_real_Δn_a·ds/(dn/dc)。

    返回：表面灵敏度物理链 + LOD_real（RIU，adlayer 折射率变化）明细 + Γ_LOD（kg/m²）。
    """
    sens = real_surface_sensitivity(geo, ds_um)
    if noise is None:
        noise = dict(DEFAULT_NOISE)
    lod = lod_real(sens["S_nm_per_riu"], Q, sens["wl_um"], noise)
    # de Feijter 反向：可探测 adlayer 折射率变化 = LOD_real_riu
    lod_dn_a = lod["LOD_real_riu"]
    gamma_lod_kg_m2 = (lod_dn_a * (ds_um * 1e-4) / dn_dc) * 10.0 \
        if dn_dc > 0 else float("nan")
    return {
        "sensitivity": sens, "Q": Q, "LOD_real": lod,
        "lod_delta_n_a_riu": lod_dn_a, "gamma_lod_kg_m2": gamma_lod_kg_m2,
    }


# ---------------------------------------------------------------------------
# 场景（复用量级 + 反向探针）
# ---------------------------------------------------------------------------
SCENARIOS: Dict[str, Dict[str, Any]] = {
    # 真实 SOI 平板 / 水包层 / 50nm 蛋白层，1 mK 主动温控、无 referencing
    "soi_slab_protein": dict(geo=DEFAULT_GEO, ds_um=DEFAULT_DS_UM, Q=1e4,
                             noise={**DEFAULT_NOISE, "dT_stability_K": 1e-3, "CMR": 1.0}),
    # 厚吸附层（500nm）→ 体/表比趋近 1（接近 B460 体灵敏度）—— 上限对照
    "soi_slab_thick": dict(geo=DEFAULT_GEO, ds_um=0.5, Q=1e4,
                           noise={**DEFAULT_NOISE, "dT_stability_K": 1e-3}),
    # referenced：CMR=100 验证热漂被压下去
    "bench_referenced": dict(geo=DEFAULT_GEO, ds_um=DEFAULT_DS_UM, Q=1e4,
                             noise={**DEFAULT_NOISE, "dT_stability_K": 1e-3, "CMR": 100.0}),
}


# ---------------------------------------------------------------------------
# 自校 / 反向探针（先证能变红）
# ---------------------------------------------------------------------------
def selfcheck_ps_m4(tol_surface_align: float = 2e-3,
                    S_surface_hi: float = 1.0,
                    LOD_hi: float = 1.0) -> Dict[str, Any]:
    """PS-M4 守卫：表面灵敏度对齐 + 物理合理 + 朗缪尔 + 反向探针。"""
    s = real_surface_sensitivity()
    checks: Dict[str, Any] = {}

    # ① 表面灵敏度数学链对齐（核心）：HF golden 与 TMM-FD 绝对 |Δ| < B461 tol（2e-3）
    #    （与设计薄层 ds 一致，直接镜像判据 D 的绝对残差语义）
    s_b461_g = surface_sensitivity_golden(DEFAULT_GEO["n_f"], DEFAULT_GEO["n_c"],
                                         DEFAULT_GEO["n_a"], DEFAULT_GEO["d_um"],
                                         DEFAULT_DS_UM, DEFAULT_GEO["wl_um"])
    s_b461_c = surface_sensitivity_fd(DEFAULT_GEO["n_f"], DEFAULT_GEO["n_c"],
                                     DEFAULT_GEO["n_a"], DEFAULT_GEO["d_um"],
                                     DEFAULT_DS_UM, DEFAULT_GEO["wl_um"])
    abs_res = abs(s_b461_g - s_b461_c)
    checks["surface_aligned_golden_vs_fd"] = (abs_res < tol_surface_align)

    # ② 物理量合理：0 < S_surface < 1（Γ∈(0,1) 且 n_a>n_eff 部分 ⇒ 通常 <1）
    checks["S_surface_in_range"] = (0.0 < s["S_surface"] <= S_surface_hi)

    # ③ Γ_adlayer ∈ (0, Γ_clad)（有限 ds 只截获部分倏逝尾）
    checks["gamma_adlayer_lt_clad"] = (0.0 < s["gamma_adlayer"] < s["gamma_clad"])

    # ④ 倏逝穿透深度有限且为正
    checks["decay_depth_positive"] = (math.isfinite(s["decay_depth_um"]) and s["decay_depth_um"] > 0.0)

    # ⑤ 体/表比 ∈ (0,1) 且随 ds 增大趋近 1
    checks["bulk_surface_ratio_in_range"] = (0.0 < s["bulk_surface_ratio"] < 1.0)

    # ⑥ 群折射率 > 有效折射率（正常色散）
    checks["ng_gt_neff"] = (s["n_g"] > s["n_eff"]) if math.isfinite(s["n_g"]) else False

    # ⑦ LOD_real 有限且为正（量级 < 1 RIU）
    lod = surface_sensor_lod()["LOD_real"]
    checks["LOD_finite_positive"] = (math.isfinite(lod["LOD_real_riu"])
                                     and 0 < lod["LOD_real_riu"] < LOD_hi)

    # ⑧ 反向探针：n_f ≤ n_c（无导模）⇒ S_surface 必为 nan ⇒ 守卫必捕获
    nan_geo = {**DEFAULT_GEO, "n_f": 1.30}
    s_nan = real_surface_sensitivity(nan_geo)
    checks["no_guided_mode_red_flag"] = (not math.isfinite(s_nan["S_surface"]))

    # ⑨ 连续一致：ds 远大于倏逝衰减深度（5µm ≫ 1/γ≈98nm）⇒ Γ_adlayer→Γ_clad
    #    （退化为 B460 体灵敏度），rel<1e-3
    s_thick = real_surface_sensitivity(DEFAULT_GEO, ds_um=5.0)
    rel = (abs(s_thick["gamma_adlayer"] - s["gamma_clad"]) / s["gamma_clad"]
           if s["gamma_clad"] > 0 else float("nan"))
    checks["thick_adlayer_degenerates_to_bulk"] = (rel < 1e-3)

    # ⑩ 朗缪尔平衡 θ_eq ∈ (0,1)（默认 K_A·C=1 ⇒ θ_eq=0.5）
    bio_def = dict(k_on=1e6, k_off=1e-3, C=1e-9)
    th_eq = langmuir_theta_eq(bio_def["k_on"], bio_def["k_off"], bio_def["C"])
    checks["langmuir_theta_eq_in_range"] = (0.0 < th_eq < 1.0)

    # ⑪ 朗缪尔动力学：θ(t) 单调上升且趋于 θ_eq（t 远大于时间常数时 rel<1e-6）
    th_t_big = langmuir_theta_t(bio_def["k_on"], bio_def["k_off"], bio_def["C"], 1e4)
    th_eq_big = langmuir_theta_eq(bio_def["k_on"], bio_def["k_off"], bio_def["C"])
    checks["langmuir_kinetics_to_equilibrium"] = (
        abs(th_t_big - th_eq_big) / th_eq_big < 1e-6 if th_eq_big > 0 else False)

    # ⑫ 朗缪尔闭环：闭式 θ(t) ⇄ RK4 积分（同 t=1e3s）|Δ|<1e-6
    th_closed = langmuir_theta_t(bio_def["k_on"], bio_def["k_off"], bio_def["C"], 1e3)
    th_rk4 = langmuir_rk4(bio_def["k_on"], bio_def["k_off"], bio_def["C"], 2000, 1e3)
    checks["langmuir_closed_form_eq_rk4"] = (abs(th_closed - th_rk4) < 1e-6)

    # ⑬ 反向探针：k_on=0 ⇒ θ_eq=0
    checks["langmuir_zero_affinity_red_flag"] = (langmuir_theta_eq(0.0, 1e-3, 1e-9) == 0.0)

    # ⑭ 朗缪尔链表面质量有限且为正（默认蛋白层）
    lc = langmuir_chain(bio_def["k_on"], bio_def["k_off"], bio_def["C"], 1e3)
    checks["langmuir_chain_mass_positive"] = (
        math.isfinite(lc["gamma_t_kg_m2"]) and lc["gamma_t_kg_m2"] > 0.0)

    all_pass = all(v for k, v in checks.items() if not k.startswith(("note",)))
    scen_reports = {}
    for k, v in SCENARIOS.items():
        scen_reports[k] = surface_sensor_lod(v["geo"], v.get("ds_um", DEFAULT_DS_UM),
                                             v.get("noise"), v["Q"])
    return {
        "selfcheck": {"all_pass": all_pass, "checks": checks},
        "baseline_surface_sensitivity": s,
        "baseline_lod": surface_sensor_lod(),
        "scenarios": scen_reports,
    }


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def main(out_dir: Optional[str] = None) -> int:
    rep = selfcheck_ps_m4()
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "ps_m4_report.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if rep["selfcheck"]["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(out_dir=os.path.join("outputs", "ps_m4")))
