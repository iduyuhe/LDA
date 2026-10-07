"""PS-M6 · 规模与集成（吃狗粮 v6）。

═══ 策略（把单点传感器推向「芯片级 POC 诊断」：阵列 + 读出 + 封装 三件事同时成立）═══
PS-M0~M5 解决了「一个传感点怎么设计、怎么算指标、怎么开窗、怎么提灵敏、怎么功能化、
怎么在流体里工作」。但真实的 **POC 诊断芯片**不是单点：它是 **N 通道阵列** + **每通道
Ge PD + 跨阻放大器（TIA）读出** + **光纤阵列封装对准** 同时成立。PS-M6 抽取三道可判决的
**规模/集成支柱**（延续 PS-M2~M5 的「解析闭式 golden × 方法学独立数值候选」双轨纪律）：

  · B466 密集阵列**热串扰比** `ΔT(d)/ΔT(0)`：阵列密度（pitch）的物理上限；
  · B467 TIA **读出噪声底** `√(kT/C)`：读出链能分辨多小的信号（跨阻增益无关）；
  · B468 光纤-波导**对准耦合效率** `η(d)=e^{−d²/(2w²)}`：封装对准容差。

═══ 🔴 集成链（本档要回答的问题）═══
  阵列规模 → 理想均分损耗 `−10log10(N)` → 单通道光功率下降 → 读出噪声（**激光 RIN 主导**）
  → 波长分辨率 `δλ_min` → 折算 RIU 探测限 `LOD_readout = δλ_min / S`。
  ⇒ 与 PS-M4「读出非瓶颈」自洽：本档给出**读出/封装的定量上限**，并指出真正的集成瓶颈。

═══ 🔴 纪律 ═══
· 进报告数字一律**模块现算**（不转录草稿）；tol 与 anchor 判据**读自 `BENCHMARK_DEFS`**（不硬编码）；
· 每道守卫配反向探针（先证能变红）；复用 B-37 内核（`_batch_b37_numeric`）为三锚数学单一真源；
· 单点灵敏度 S 由 `lda_l2.ps_m3.real_waveguide_sensitivity`（对称平板闭式，廉价）**现算**注入
  —— 不调用 `ps_m0.bulk_sensitivity`（该 2D 模式求解实测 28.9s，CI 预算不允许），
  因此本档 S 是**平板设计示例值**，非 SOI 500×220 真实几何值（后者见 PS-M0）。
· 量纲 O(1) 化（判据 D 纪律）：串扰比/耦合效率无量纲、噪声 µV、波长 nm、LOD RIU。

═══ 诚实边界 ═══
· 几何/电路/封装参数均为**设计示例**（阵列 pitch 1 µm、热衰减长度 1 µm；C=100 fF、R_f=10 kΩ、
  I_dark=1 nA、BW=1 MHz、P0=1 mW、RIN=−140 dB/Hz；模场半径 5 µm）。结论只可用于数值方法与
  量级/预算，**不得作制造/性能宣称**。
· 热串扰为一维阻尼扩散「散热鳍」近似；读出为单极点白噪 + RIN + 暗电流散粒（忽略运放有限
  GBW、1/f 噪声、量化噪声）；对准为理想高斯模场重叠（忽略角度失配/端面反射）。
· 零商业依赖（纯 numpy + math）。
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Optional

from lda_harness._batch_b37_numeric import (  # noqa: E402
    align_overlap_golden,
    align_overlap_sampled,
    array_crosstalk_fd,
    array_crosstalk_golden,
    tia_noise_floor_golden_uV,
    tia_noise_floor_td_uV,
)
from lda_l2.ps_m2 import DEFAULT_NOISE, resonance_slope_max  # noqa: E402
from lda_l2.ps_m3 import real_waveguide_sensitivity  # noqa: E402


#: 物理常数
Q_E = 1.602176634e-19      # C
K_B = 1.380649e-23         # J/K

#: 三锚判据用的默认离散参数（与内核 _N_BY_BID 同口径）
_N_ANCHOR = {"B466": 6400, "B467": 32000, "B468": 1024}
_KW_ANCHOR = {"B466": "N", "B467": "n", "B468": "N"}
_GOLDEN = {"B466": array_crosstalk_golden, "B467": tia_noise_floor_golden_uV,
           "B468": align_overlap_golden}
_CAND = {"B466": array_crosstalk_fd, "B467": tia_noise_floor_td_uV,
         "B468": align_overlap_sampled}

# ---------------------------------------------------------------------------
# 默认设计示例参数
# ---------------------------------------------------------------------------
#: 阵列：热衰减长度 L=1 µm、条带热源半宽 a=0.5 µm、pitch=1 µm、8 通道、目标隔离 20 dB
DEFAULT_ARRAY: Dict[str, float] = {
    "L_th_um": 1.0, "a_um": 0.5, "pitch_um": 1.0, "n_ch": 8, "iso_db_target": 20.0,
}
#: 读出：C=100 fF、R_f=10 kΩ、T=300 K、I_dark=1 nA、BW=1 MHz、P0=1 mW、R_AW=0.8、Q=1e4
DEFAULT_READOUT: Dict[str, float] = {
    "C_fF": 100.0, "R_kOhm": 10.0, "T_K": 300.0,
    "Idark_A": 1e-9, "BW_hz": 1e6, "P0_W": 1e-3, "R_AW": 0.8,
    "Q": 1e4, "wl_um": 1.55, "RIN_per_Hz": 1e-14,
}
#: 封装：模场半径 5 µm、横向偏移 5 µm、均分/传播插损设计示例
DEFAULT_ALIGN: Dict[str, float] = {
    "w_um": 5.0, "d_um": 5.0, "prop_loss_db": 0.1, "cell_pitch_um": 60.0,
    "settle_factor": 5.0,
}


# ---------------------------------------------------------------------------
# 判据工具：tol 读自 BENCHMARK_DEFS（不硬编码）
# ---------------------------------------------------------------------------
def _tol_from_defs(bid: str) -> float:
    """从 `BENCHMARK_DEFS` 现读该锚 tol（防与账本漂移）。"""
    from lda_harness.benchmarks import BENCHMARK_DEFS
    return float(BENCHMARK_DEFS[bid]["tol"])


def anchor_verdict(bid: str) -> Dict[str, float]:
    """现算某锚的 golden / candidate / |Δ| / tol / 是否 PASS（走与 harness 同口径的调用）。"""
    from lda_harness.benchmarks import BENCHMARK_DEFS
    params = dict(BENCHMARK_DEFS[bid]["default_params"])
    tol = float(BENCHMARK_DEFS[bid]["tol"])
    g = float(_GOLDEN[bid](**params))
    c = float(_CAND[bid](**{**params, _KW_ANCHOR[bid]: _N_ANCHOR[bid]}))
    return {"golden": g, "candidate": c, "abs_res": abs(g - c), "tol": tol,
            "passed": abs(g - c) < tol}


def _verdict_with(bid: str, key: str, factor: float) -> bool:
    """反向探针（与 `run_benchmark_falsifiability_smoke` 同语义）：**冻结** golden 于原始
    参数，只把**候选侧**输入参数乘以 factor，判定是否仍 PASS（期望 False=被抓）。

    🔴 血案：若把 golden 也用扰动参数重算，则 golden 与候选**同步漂移**⇒ |Δ| 不变 ⇒ 探针
    恒绿（假绿）。必须冻结 golden。
    """
    from lda_harness.benchmarks import BENCHMARK_DEFS
    params = dict(BENCHMARK_DEFS[bid]["default_params"])
    tol = float(BENCHMARK_DEFS[bid]["tol"])
    g = float(_GOLDEN[bid](**params))                      # 冻结于原始参数
    pp = dict(params)
    pp[key] = pp[key] * factor
    c = float(_CAND[bid](**{**pp, _KW_ANCHOR[bid]: _N_ANCHOR[bid]}))
    return (math.isfinite(g) and math.isfinite(c) and abs(g - c) < tol)


# ---------------------------------------------------------------------------
# 支柱 ① 阵列规模（热串扰定 pitch / 通道密度）
# ---------------------------------------------------------------------------
def array_scale(p: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """密集传感阵列规模：热串扰比 + 达标最小 pitch + 通道密度 + 长臂孔径。"""
    pp = dict(DEFAULT_ARRAY) if p is None else dict(p)
    L = pp["L_th_um"]
    a = pp["a_um"]
    pitch = pp["pitch_um"]
    c = array_crosstalk_golden(L, pitch, a)
    c_db = 20.0 * math.log10(c) if c > 0.0 else float("-inf")
    iso = pp["iso_db_target"]
    c_max = 10.0 ** (-iso / 20.0)
    # 反算 pitch_min：c(p) = K·e^{−p/L} = c_max，K = sinh(a/L)/(1−e^{−a/L})
    K = (math.sinh(a / L) / (1.0 - math.exp(-a / L))) if (L > 0.0 and a > 0.0) else float("nan")
    pitch_min = (-L * math.log(c_max / K)) if (K > 0.0 and 0.0 < c_max < K) else float("nan")
    n_ch = int(pp["n_ch"])
    return {
        "L_th_um": L, "a_um": a, "pitch_um": pitch,
        "crosstalk_ratio": c, "crosstalk_db": c_db,
        "iso_db_target": iso,
        "crosstalk_at_iso_target": c_max,
        "pitch_min_um": pitch_min,
        "array_length_um": pitch * max(n_ch - 1, 0),
        "channel_density_per_mm": (1000.0 / pitch) if pitch > 0.0 else float("nan"),
        "n_ch": n_ch,
    }


# ---------------------------------------------------------------------------
# 支柱 ② 读出链（TIA 噪声底 → 输入参考电流噪声 → 波长分辨率）
# ---------------------------------------------------------------------------
def readout_chain(p: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """TIA 读出链：噪声底 / 输入参考电流噪声 / 带宽 / 波长分辨率 δλ_min。"""
    pp = dict(DEFAULT_READOUT) if p is None else dict(p)
    C = pp["C_fF"]
    R = pp["R_kOhm"]
    T = pp["T_K"]
    Rf = R * 1e3
    v_n_uV = tia_noise_floor_golden_uV(C, R, T)
    v_n = v_n_uV * 1e-6
    i_amp = v_n / Rf                                   # A：TIA 折算到输入的电流噪声
    i_dark = math.sqrt(2.0 * Q_E * pp["Idark_A"] * pp["BW_hz"])
    i_rin = pp["P0_W"] * pp["R_AW"] * math.sqrt(pp["RIN_per_Hz"] * pp["BW_hz"])
    i_tot = math.sqrt(i_amp ** 2 + i_dark ** 2 + i_rin ** 2)
    tau = Rf * C * 1e-15
    f3db = 1.0 / (2.0 * math.pi * tau)
    FWHM_nm = pp["wl_um"] * 1000.0 / pp["Q"]
    slope = resonance_slope_max(DEFAULT_NOISE["T_bg"], DEFAULT_NOISE["T_min"], FWHM_nm)
    dI_dlam = pp["P0_W"] * pp["R_AW"] * slope          # A/nm
    dlam_min_nm = (i_tot / dI_dlam) if dI_dlam > 0.0 else float("inf")
    # RIN-only 波长分辨率（用于功率无关性判据）：i_rin/(P0·R·slope) = √(RIN·BW)/slope
    dlam_rin_nm = (i_rin / dI_dlam) if dI_dlam > 0.0 else float("inf")
    return {
        "C_fF": C, "R_kOhm": R, "T_K": T,
        "v_n_uV": v_n_uV, "tau_s": tau, "f_3dB_Hz": f3db,
        "i_amp_A": i_amp, "i_dark_A": i_dark, "i_rin_A": i_rin, "i_tot_A": i_tot,
        "FWHM_nm": FWHM_nm, "slope_per_nm": slope, "dI_dlam_A_per_nm": dI_dlam,
        "delta_lambda_min_nm": dlam_min_nm,
        "delta_lambda_rin_nm": dlam_rin_nm,
        "dominant_noise": ("rin" if i_rin >= max(i_amp, i_dark)
                           else ("dark" if i_dark >= i_amp else "amp")),
    }


# ---------------------------------------------------------------------------
# 支柱 ③ 封装/对准（高斯模场重叠容差）
# ---------------------------------------------------------------------------
def alignment(p: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """光纤-波导横向对准：耦合效率 / 插损 / 1 dB 容差。"""
    pp = dict(DEFAULT_ALIGN) if p is None else dict(p)
    w = pp["w_um"]
    d = pp["d_um"]
    eta = align_overlap_golden(d, w)
    loss_db = (-10.0 * math.log10(eta)) if eta > 0.0 else float("inf")
    # η = 10^{−L/10} ⇒ d = w·√(2·(L/10)·ln10)
    d_1db = w * math.sqrt(2.0 * 0.1 * math.log(10.0))
    d_3db = w * math.sqrt(2.0 * 0.3 * math.log(10.0))
    return {
        "w_um": w, "d_um": d,
        "eta": eta, "insertion_loss_db": loss_db,
        "d_1db_um": d_1db, "d_3db_um": d_3db,
        "eta_at_1db": (10.0 ** -0.1),
    }


# ---------------------------------------------------------------------------
# 集成汇总（阵列 × 读出 × 封装 → POC 芯片级预算）
# ---------------------------------------------------------------------------
def integration_summary(p: Optional[Dict[str, float]] = None,
                        S_nm_per_riu: Optional[float] = None) -> Dict[str, Any]:
    """把三支柱合成 POC 芯片级预算：光学插损 / 帧率 / 面积 / 读出限制 LOD。

    `S_nm_per_riu` 缺省时由 `lda_l2.ps_m3.real_waveguide_sensitivity`（对称平板闭式，廉价）现算。
    """
    arr = array_scale(p)
    rod = readout_chain(p)
    ali = alignment(p)
    pp = dict(DEFAULT_ALIGN) if p is None else dict(p)
    if S_nm_per_riu is None:
        S_nm_per_riu = float(real_waveguide_sensitivity()["S_nm_per_riu"])
    n_ch = arr["n_ch"]
    split_loss_db = (-10.0 * math.log10(1.0 / n_ch)) if n_ch > 0 else float("inf")
    total_loss_db = split_loss_db + ali["insertion_loss_db"] + pp["prop_loss_db"]
    t_settle = pp["settle_factor"] * rod["tau_s"]
    frame_rate_hz = 1.0 / (n_ch * t_settle) if (n_ch > 0 and t_settle > 0.0) else float("inf")
    area_mm2 = (n_ch * arr["pitch_um"] * pp["cell_pitch_um"]) * 1e-6   # µm² → mm²
    lod_readout_riu = (rod["delta_lambda_min_nm"] / S_nm_per_riu) if S_nm_per_riu > 0.0 else float("inf")
    return {
        "n_ch": n_ch,
        "S_nm_per_riu": S_nm_per_riu,
        "channel_split_loss_db": split_loss_db,
        "alignment_loss_db": ali["insertion_loss_db"],
        "total_optical_loss_db": total_loss_db,
        "frame_rate_hz": frame_rate_hz,
        "t_settle_s": t_settle,
        "area_mm2": area_mm2,
        "delta_lambda_min_nm": rod["delta_lambda_min_nm"],
        "LOD_readout_riu": lod_readout_riu,
        "dominant_noise": rod["dominant_noise"],
        "array": arr, "readout": rod, "alignment": ali,
    }


# ---------------------------------------------------------------------------
# 自校 / 反向探针（先证能变红）
# ---------------------------------------------------------------------------
def selfcheck_ps_m6() -> Dict[str, Any]:
    """PS-M6 守卫：三锚对齐（tol 读自 BENCHMARK_DEFS）+ 阵列/读出/对准物理律 + 集成一致性
    + 反向探针（×1.1 必红）+ 非法参数红标。"""
    checks: Dict[str, Any] = {}

    # ---- ① 三锚对齐（走 harness 同口径）----
    for bid in ("B466", "B467", "B468"):
        v = anchor_verdict(bid)
        checks["%s_anchor_within_tol" % bid.lower()] = bool(v["passed"])
        checks["%s_tol_read_from_defs" % bid.lower()] = (
            abs(v["tol"] - _tol_from_defs(bid)) < 1e-18)

    # ---- ② 阵列：物理律 + 反算 + 单调 ----
    a0 = array_scale()
    checks["array_crosstalk_finite_positive"] = (
        math.isfinite(a0["crosstalk_ratio"]) and 0.0 < a0["crosstalk_ratio"] < 1.0)
    a_wide = array_scale({**DEFAULT_ARRAY, "pitch_um": 2.0})
    checks["array_crosstalk_decreases_with_pitch"] = (
        a_wide["crosstalk_ratio"] < a0["crosstalk_ratio"])
    # 反算 pitch_min 处串扰 == 隔离目标
    c_at_min = array_crosstalk_golden(a0["L_th_um"], a0["pitch_min_um"], a0["a_um"])
    rel_min = (abs(c_at_min - a0["crosstalk_at_iso_target"]) / a0["crosstalk_at_iso_target"])
    checks["array_pitch_min_meets_iso_target"] = bool(rel_min < 1e-12)
    a_iso40 = array_scale({**DEFAULT_ARRAY, "iso_db_target": 40.0})
    checks["array_pitch_min_grows_with_iso_target"] = (
        a_iso40["pitch_min_um"] > a0["pitch_min_um"])
    checks["array_density_consistent"] = (
        abs(a0["channel_density_per_mm"] - 1000.0 / a0["pitch_um"]) < 1e-12)

    # ---- ③ 读出：噪声底 / 带宽 / 量纲 ----
    r0 = readout_chain()
    checks["readout_noise_floor_finite_positive"] = (
        math.isfinite(r0["v_n_uV"]) and r0["v_n_uV"] > 0.0)
    r_R = readout_chain({**DEFAULT_READOUT, "R_kOhm": 20.0})
    checks["readout_noise_floor_R_independent"] = (
        abs(r_R["v_n_uV"] - r0["v_n_uV"]) / r0["v_n_uV"] < 1e-12)
    checks["readout_bandwidth_equals_inverse_tau"] = (
        abs(r0["f_3dB_Hz"] - 1.0 / (2.0 * math.pi * r0["tau_s"]))
        / r0["f_3dB_Hz"] < 1e-15)
    r_C = readout_chain({**DEFAULT_READOUT, "C_fF": 200.0})
    checks["readout_bandwidth_halves_with_doubled_C"] = (
        abs(r_C["f_3dB_Hz"] - 0.5 * r0["f_3dB_Hz"]) / r0["f_3dB_Hz"] < 1e-15)
    checks["readout_input_referred_current_consistent"] = (
        abs(r0["i_amp_A"] - (r0["v_n_uV"] * 1e-6) / (DEFAULT_READOUT["R_kOhm"] * 1e3))
        / r0["i_amp_A"] < 1e-12)
    # RIN-only 波长分辨率与光功率无关（i_rin ∝ P0、dI/dλ ∝ P0 ⇒ 相消）
    r_p2 = readout_chain({**DEFAULT_READOUT, "P0_W": 2e-3})
    checks["readout_rin_limited_dlam_power_invariant"] = (
        abs(r_p2["delta_lambda_rin_nm"] - r0["delta_lambda_rin_nm"])
        / r0["delta_lambda_rin_nm"] < 1e-12)

    # ---- ④ 对准：容差律 ----
    al0 = alignment()
    checks["align_eta_at_zero_is_one"] = (abs(align_overlap_golden(0.0, 5.0) - 1.0) < 1e-12)
    al_off = alignment({**DEFAULT_ALIGN, "d_um": 7.0})
    checks["align_eta_decreases_with_offset"] = (al_off["eta"] < al0["eta"])
    checks["align_1db_tolerance_recovers_10^-0.1"] = (
        abs(align_overlap_golden(al0["d_1db_um"], al0["w_um"]) - 10.0 ** -0.1) < 1e-9)
    checks["align_1db_formula_w_sqrt"] = (
        abs(al0["d_1db_um"] - al0["w_um"] * math.sqrt(2.0 * 0.1 * math.log(10.0))) < 1e-12)

    # ---- ⑤ 集成一致性 ----
    ints = integration_summary()
    checks["integration_total_loss_adds_up"] = (
        abs(ints["total_optical_loss_db"]
            - (ints["channel_split_loss_db"] + ints["alignment_loss_db"]
               + DEFAULT_ALIGN["prop_loss_db"])) < 1e-12)
    checks["integration_frame_rate_consistent"] = (
        abs(ints["frame_rate_hz"] - 1.0 / (ints["n_ch"] * ints["t_settle_s"]))
        / ints["frame_rate_hz"] < 1e-12)
    checks["integration_area_positive"] = (ints["area_mm2"] > 0.0)
    checks["integration_S_positive_finite"] = (
        math.isfinite(ints["S_nm_per_riu"]) and ints["S_nm_per_riu"] > 0.0)
    checks["integration_lod_readout_consistent"] = (
        abs(ints["LOD_readout_riu"]
            - ints["delta_lambda_min_nm"] / ints["S_nm_per_riu"]) / ints["LOD_readout_riu"] < 1e-12)

    # ---- ⑥ 反向探针（先证能变红）：×1.1 必 FAIL（冻结 golden，只扰候选侧）----
    checks["reverse_b466_perturb_d_flips_red"] = (
        not _verdict_with("B466", "d_um", 1.1))
    checks["reverse_b467_perturb_C_flips_red"] = (
        not _verdict_with("B467", "C_fF", 1.1))
    checks["reverse_b468_perturb_d_flips_red"] = (
        not _verdict_with("B468", "d_um", 1.1))

    # ---- ⑦ 非法参数红标 ----
    checks["red_flag_zero_params_nan"] = (
        not math.isfinite(array_crosstalk_golden(0.0, 1.0, 0.5))
        and not math.isfinite(tia_noise_floor_golden_uV(0.0))
        and not math.isfinite(align_overlap_golden(1.0, 0.0)))

    all_pass = all(bool(v) for v in checks.values())
    return {
        "selfcheck": {"all_pass": all_pass, "checks": checks,
                      "n_checks": len(checks)},
        "array": a0,
        "readout": r0,
        "alignment": al0,
        "integration": {k: v for k, v in ints.items()
                        if k not in ("array", "readout", "alignment")},
        "anchors": {bid: anchor_verdict(bid) for bid in ("B466", "B467", "B468")},
    }


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def main(out_dir: Optional[str] = None) -> int:
    rep = selfcheck_ps_m6()
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "ps_m6_report.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if rep["selfcheck"]["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(out_dir=os.path.join("outputs", "ps_m6")))
