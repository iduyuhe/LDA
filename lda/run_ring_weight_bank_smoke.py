# -*- coding: utf-8 -*-
"""U4 常驻门禁：微环权重库（MRR 替 MZI 做幅度控制）· 设计层。

判据分组（A–K）
---------------
A 契约 / 预算 / 披露（含「假设值」必须被标为假设）
B 闭式核 `peak_drop_weight` / `kappa_for_peak_weight`（往返 + 单调 + 极限 + 独立重算）
C 域校验（κ ∉ [0,1] / w > a **必 raise**，绝不静默截断）+ 「合法必过」
D 与 D-37 资产交叉验证（采样谱峰 + Q 分解 **独立重算**）
E 选择性 / Q / FWHM（地板 + 反演 + 「冲突目标」不可兼得）
F 双旋钮位深（档位极差口径 vs 单点口径反面对照 + 越域点显式报出）
G 面积对比（物理参照达标 + 占位参照仅对照 + 独立重算）
H 权重库映射（默认已签发表 · 表外权重显式标注 **不静默外推** · gap→κ 往返回路）
I 与 U1 共享网格共网格（保真度保持 + 对角层 + 信道数不匹配必 raise）
J 诚实边界文本（关键数字与结论必须出现在披露里）
K 突变探针友好性（独立重算的容差必须**紧到能把伪造值判红**）

🔴 立场：本 smoke 断言的是**事实**，包括不利事实 ——
`F6` 断言失谐旋钮在 κ=0.147 处**不达标**（2.91 bit < 5）、`F3` 断言单点口径
**高估 1.52×**、`H5` 断言部分权重**不可达**。若有人把模块改成「总是达标 /
单点可信 / 权重任意可达」，这些判据立刻变红。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
from lda_l2.ring_weight_bank import (  # noqa: E402
    AREA_BUDGET_RATIO,
    CHANNEL_SPACING_NM_DEFAULT,
    DETUNING_RESOLUTION_PM_DEFAULT,
    GAP_RESOLUTION_NM_DEFAULT,
    KAPPA_TOL,
    MZI_DY_UM_DEFAULT,
    M_RING_DEFAULT,
    N_G_DEFAULT,
    PS_ARM_UM_DEFAULT,
    RING_WEIGHT_DISCLOSURE,
    TABLE_PROBE_GAP_UM,
    WEIGHT_BUDGET_BITS,
    WL_NM_DEFAULT,
    W_UM,
    RingWeightBankError,
    area_vs_eo_modulator,
    calibration_table_info,
    detuning_knob_bits,
    gap_bounds_for_backend,
    gap_for_kappa,
    gap_knob_bits,
    intrinsic_fwhm_floor_pm,
    kappa_at_gap,
    kappa_for_fwhm,
    kappa_for_peak_weight,
    max_weight_under_selectivity,
    peak_drop_weight,
    q_selectivity,
    roundtrip_amplitude,
    weight_bank_from_weights,
    weight_bank_on_shared_mesh,
    weight_reachable_interval,
)

PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True, detail_on="fail")

# ---------------------------------------------------------------------------
# 本轮实测常量（gap=0.30µm · λ=1.55µm · 与 D-37 / U3 同源）—— 用于「钉住」结论
# ---------------------------------------------------------------------------
R30 = 3.0207                 # wdm_ring_anchor(gap=0.30) 半径（µm）
A_CEIL = 0.991300            # 半程振幅 a（权重物理上限）
KAPPA_ANALYTIC_30 = 0.942375
KAPPA_FDTD_30 = 0.040522125
FWHM_FLOOR_PM = 143.6993
BITS_GAP_RANGE = 8.1328
BITS_GAP_POINT = 12.3236
RATIO_PI_ARM = 0.01217106
W_MAX_TABLE = 0.08036590
W_MIN_TABLE = 0.00024984

W_BANK = [0.02, 0.04, 0.06, 0.08]
WL_BANK = [1550.0, 1552.5, 1555.0, 1557.5]


def _rejects(fn, exc: type = Exception) -> bool:
    """fn() 必须抛 exc（且不是别的异常）⇒ True。"""
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def _ind_a(R_um: float, bl: float) -> float:
    """独立重算半程振幅（不复用模块函数）。"""
    return math.exp(-23.03 * bl * (2.0 * math.pi * R_um * 1e-6) / 2.0)


def _ind_w(kappa: float, R_um: float, bl: float) -> float:
    """独立重算谐振 drop 透射率 = a·κ⁴/(1 − a·t²)²（不复用模块函数）。"""
    a = _ind_a(R_um, bl)
    t2 = 1.0 - kappa * kappa
    return a * kappa ** 4 / (1.0 - a * t2) ** 2


def main():  # noqa: C901
    from lda_agent.ring_adddrop import (adddrop_spectrum,
                                        bending_loss_db_per_cm)
    from lda_layout.placement import device_bbox
    from lda_layout.wdm_mesh_pnr import wdm_ring_anchor

    R = wdm_ring_anchor(WL_NM_DEFAULT, n_g=N_G_DEFAULT, m=M_RING_DEFAULT,
                        gap=TABLE_PROBE_GAP_UM)["R_um"]
    BL = bending_loss_db_per_cm(R)
    A = roundtrip_amplitude(R, BL)

    # ======================================================= A 契约 / 预算 / 披露
    need = {"scope", "nonneg_weight_only", "absolute_weight_not_calibrated",
            "analytic_placeholder_out_of_domain", "single_point_derivative_lies",
            "thermal_drift_not_calibrated", "weight_bandwidth_is_resonance_fwhm",
            "no_fdtd_no_3d"}
    check("A1 披露项键齐全（8 项，防被悄悄删）",
          need.issubset(set(RING_WEIGHT_DISCLOSURE)),
          "missing=%s" % sorted(need - set(RING_WEIGHT_DISCLOSURE)))
    check("A2 披露项值均为非空字符串",
          all(isinstance(v, str) and v.strip() for v in RING_WEIGHT_DISCLOSURE.values()))
    check("A3 面积预算口径 == 10%（§4.2 U4）",
          abs(AREA_BUDGET_RATIO - 0.10) < 1e-12, "=%.4f" % AREA_BUDGET_RATIO)
    check("A4 权重位深预算口径 == 5.0 bit（§4.2 U4 · 设计预算）",
          abs(WEIGHT_BUDGET_BITS - 5.0) < 1e-12, "=%.3f" % WEIGHT_BUDGET_BITS)
    check("A5 面积参照 == 真实 π 相移臂 1000µm（与 mesh_drive_manifest 同源）",
          abs(PS_ARM_UM_DEFAULT - 1000.0) < 1e-12
          and abs(MZI_DY_UM_DEFAULT - 4.0) < 1e-12,
          "ps_arm=%.1f dy=%.1f" % (PS_ARM_UM_DEFAULT, MZI_DY_UM_DEFAULT))
    check("A6 信道间隔 == 2.5nm；半径锚 gap == 0.30µm（与 U1/D-57 同源）",
          abs(CHANNEL_SPACING_NM_DEFAULT - 2.5) < 1e-12
          and abs(TABLE_PROBE_GAP_UM - 0.30) < 1e-12
          and abs(R - R30) < 1e-3,
          "spacing=%.1f gap=%.2f R=%.4f" % (CHANNEL_SPACING_NM_DEFAULT,
                                           TABLE_PROBE_GAP_UM, R))
    # 🔴 两个「分辨率」是假设值 ⇒ 必须由返回字段显式自曝，不得冒充实测
    gk = gap_knob_bits(dgap_nm=GAP_RESOLUTION_NM_DEFAULT)
    dk = detuning_knob_bits(KAPPA_FDTD_30, dlam_pm=DETUNING_RESOLUTION_PM_DEFAULT)
    check("A7 分辨率参数以「假设值」自曝（非实测/非标定）",
          "假设值" in gk["assumed_not_measured"]
          and "假设值" in dk["assumed_not_measured"]
          and abs(gk["dgap_nm"] - GAP_RESOLUTION_NM_DEFAULT) < 1e-12
          and abs(dk["dlam_pm"] - DETUNING_RESOLUTION_PM_DEFAULT) < 1e-12)
    check("A8 κ 容差为小量且 > 0（不是判据放宽）",
          0.0 < KAPPA_TOL <= 1e-6, "=%.1e" % KAPPA_TOL)

    # ============================================================ B 闭式核
    worst_rt = 0.0
    for k in (0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 0.94, 1.0):
        worst_rt = max(worst_rt, abs(kappa_for_peak_weight(
            peak_drop_weight(k, R, BL), R, BL) - k))
    check("B1 闭式正反演往返 |Δκ| ≤ 1e-12（机器精度）",
          worst_rt <= 1e-12, "worst=%.3e" % worst_rt)
    check("B2 κ=0 ⇒ w=0（无耦合无 drop）",
          peak_drop_weight(0.0, R, BL) == 0.0)
    check("B3 κ=1 ⇒ w == a（临界耦合达物理上限）",
          abs(peak_drop_weight(1.0, R, BL) - A) < 1e-15,
          "w(1)=%.17g a=%.17g" % (peak_drop_weight(1.0, R, BL), A))
    check("B4 无损（α=0）⇒ a==1 且 w ≡ 1（与 κ 无关）",
          roundtrip_amplitude(R, 0.0) == 1.0
          and abs(peak_drop_weight(0.7, R, 0.0) - 1.0) < 1e-15)
    check("B5 有损 ⇒ w ∈ (0, a]，且 w 严格小于 a（除 κ=1）",
          all(0.0 < peak_drop_weight(k, R, BL) < A
              for k in (0.05, 0.2, 0.5, 0.9, 0.99)),
          "a=%.9f" % A)
    ks = [i / 200.0 for i in range(201)]
    wv = [peak_drop_weight(k, R, BL) for k in ks]
    check("B6 w 对 κ **严格单调递增**（201 点无平台）",
          all(wv[i] < wv[i + 1] for i in range(len(wv) - 1)))
    check("B7 独立重算 w == 模块自报（最坏 0 差，不读自报值）",
          max(abs(_ind_w(k, R, BL) - peak_drop_weight(k, R, BL))
              for k in ks) == 0.0)
    check("B8 独立重算 a == 模块自报（相对差 ≤ 1e-15）",
          abs(_ind_a(R, BL) - A) / A <= 1e-15, "a=%.17g" % A)

    # ============================================================ C 域校验
    check("C1 🔴 κ>1 ⇒ 必 raise（模型失效 ≠ 器件饱和，**不截断**）",
          _rejects(lambda: peak_drop_weight(1.5, R, BL), RingWeightBankError))
    check("C2 κ<0 ⇒ 必 raise",
          _rejects(lambda: peak_drop_weight(-0.1, R, BL), RingWeightBankError))
    check("C3 🔴 w > a ⇒ 必 raise（超环内损耗上限，不给边界值）",
          _rejects(lambda: kappa_for_peak_weight(1.0, R, BL), RingWeightBankError)
          and _rejects(lambda: kappa_for_peak_weight(A * 1.000001, R, BL),
                       RingWeightBankError))
    check("C4 w < 0 ⇒ 必 raise（非负权重语义）",
          _rejects(lambda: kappa_for_peak_weight(-1e-9, R, BL),
                   RingWeightBankError))
    check("C5 R ≤ 0 / α < 0 ⇒ 必 raise",
          _rejects(lambda: roundtrip_amplitude(0.0, BL), RingWeightBankError)
          and _rejects(lambda: roundtrip_amplitude(R, -1.0), RingWeightBankError))
    check("C6 q_selectivity(κ ∉ [0,1]) ⇒ 必 raise",
          _rejects(lambda: q_selectivity(1.2, R, N_G_DEFAULT, BL),
                   RingWeightBankError))
    check("C7 kappa_for_fwhm(fwhm ≤ 0) ⇒ 必 raise",
          _rejects(lambda: kappa_for_fwhm(0.0, R, N_G_DEFAULT, BL),
                   RingWeightBankError))
    check("C8 🔴 合法输入必过（不误伤边界值）",
          peak_drop_weight(0.0, R, BL) == 0.0
          and abs(peak_drop_weight(1.0, R, BL) - A) < 1e-15
          and kappa_for_peak_weight(0.0, R, BL) == 0.0
          and abs(kappa_for_peak_weight(A, R, BL) - 1.0) < 1e-15)
    check("C9 gap_for_kappa(κ=1, analytic) **不**被容差误判不可达（边界回归）",
          abs(kappa_at_gap(gap_for_kappa(1.0, backend="analytic"),
                           backend="analytic") - 1.0) <= KAPPA_TOL * 10)
    check("C10 但真越域不受容差护佑（fdtd-table 求 κ=0.9 必 raise）",
          _rejects(lambda: gap_for_kappa(0.9, backend="fdtd-table"),
                   RingWeightBankError))

    # ================================================ D 与 D-37 资产交叉验证
    w_closed = peak_drop_weight(0.147, R, BL)
    wls = [1.55 + i * 1e-6 for i in range(-200, 201)]
    spec_peak = max(adddrop_spectrum(wls, R, N_G_DEFAULT, 0.147, BL)["drop"])
    check("D1 闭式 w 与 D-37 采样谱峰一致（差 < 1e-6，交叉验证不重写公式）",
          abs(w_closed - spec_peak) < 1e-6,
          "closed=%.10f spec=%.10f d=%.2e" % (w_closed, spec_peak,
                                              abs(w_closed - spec_peak)))
    q = q_selectivity(0.147, R, N_G_DEFAULT, BL, WL_NM_DEFAULT)
    L_m = 2.0 * math.pi * R * 1e-6
    lam_m = WL_NM_DEFAULT * 1e-9
    ap = 23.03 * BL
    q_c_i = 2.0 * math.pi * N_G_DEFAULT * L_m / (lam_m * 0.147 ** 2)
    q_i_i = 2.0 * math.pi * N_G_DEFAULT / (lam_m * ap)
    q_l_i = 1.0 / (2.0 / q_c_i + 1.0 / q_i_i)
    check("D2 Q_c / Q_i / Q_L 独立重算 == 模块自报（相对差 ≤ 1e-12）",
          abs(q["Q_c"] - q_c_i) / q_c_i <= 1e-12
          and abs(q["Q_i"] - q_i_i) / q_i_i <= 1e-12
          and abs(q["Q_L"] - q_l_i) / q_l_i <= 1e-12,
          "Qc=%.4f Qi=%.4f QL=%.4f" % (q["Q_c"], q["Q_i"], q["Q_L"]))
    check("D3 analytic 取数（κ_c 占位）钉住 0.942375",
          abs(kappa_at_gap(TABLE_PROBE_GAP_UM, backend="analytic")
              - KAPPA_ANALYTIC_30) < 1e-6,
          "=%.6f" % kappa_at_gap(TABLE_PROBE_GAP_UM, backend="analytic"))
    check("D4 fdtd-table 取数钉住 0.040522125（U3 已签发表，不重算不插值误差）",
          abs(kappa_at_gap(TABLE_PROBE_GAP_UM, backend="fdtd-table")
              - KAPPA_FDTD_30) < 1e-8,
          "=%.9f" % kappa_at_gap(TABLE_PROBE_GAP_UM, backend="fdtd-table"))
    check("D5 🔴 analytic vs FDTD 的 w 差 ≈ 39.5×（= 16.0dB）—— 绝对定标未达标被钉住",
          abs((peak_drop_weight(KAPPA_ANALYTIC_30, R, BL)
               / peak_drop_weight(KAPPA_FDTD_30, R, BL)) / 39.5 - 1.0) < 0.02,
          "ratio=%.3f" % (peak_drop_weight(KAPPA_ANALYTIC_30, R, BL)
                          / peak_drop_weight(KAPPA_FDTD_30, R, BL)))

    # ============================================== E 选择性 / Q / FWHM 折中
    floor = intrinsic_fwhm_floor_pm(R, N_G_DEFAULT, BL, WL_NM_DEFAULT)
    check("E1 FWHM 硬地板 == 独立重算 1000·λ/Q_i（弯曲损耗决定，无耦合可突破）",
          abs(floor - FWHM_FLOOR_PM) < 1e-3
          and abs(floor - 1000.0 * WL_NM_DEFAULT / q_i_i) < 1e-6,
          "floor=%.4f pm (ind=%.4f)" % (floor, 1000.0 * WL_NM_DEFAULT / q_i_i))
    k200 = kappa_for_fwhm(200.0, R, N_G_DEFAULT, BL, WL_NM_DEFAULT)
    check("E2 FWHM 反演往返：κ(200pm) ⇒ FWHM 回到 200pm（相对 ≤ 1e-9）",
          abs(q_selectivity(k200, R, N_G_DEFAULT, BL, WL_NM_DEFAULT)["fwhm_pm"]
              / 200.0 - 1.0) <= 1e-9,
          "κ=%.6f fwhm=%.6f" % (k200, q_selectivity(k200, R, N_G_DEFAULT, BL,
                                                    WL_NM_DEFAULT)["fwhm_pm"]))
    infeas = max_weight_under_selectivity(R, N_G_DEFAULT, BL, fwhm_budget_ratio=0.05)
    check("E3 🔴 FWHM 预算 5%·2.5nm=125pm < 地板 143.7pm ⇒ feasible=False（不装作有解）",
          infeas["feasible"] is False and infeas["weight_max"] == 0.0
          and infeas["fwhm_budget_pm"] < infeas["fwhm_floor_pm"],
          "budget=%.2f floor=%.2f" % (infeas["fwhm_budget_pm"],
                                      infeas["fwhm_floor_pm"]))
    check("E4 kappa_for_fwhm(目标宽于地板) ⇒ 必 raise（物理不可达，非数值问题）",
          _rejects(lambda: kappa_for_fwhm(floor * 0.5, R, N_G_DEFAULT, BL,
                                          WL_NM_DEFAULT),
                   RingWeightBankError))
    mws = [max_weight_under_selectivity(R, N_G_DEFAULT, BL,
                                        fwhm_budget_ratio=r)["weight_max"]
           for r in (0.1, 0.2, 0.5)]
    check("E5 预算放宽 ⇒ 可达权重上限单调放宽（0.1→0.2→0.5）",
          mws[0] < mws[1] < mws[2],
          "w_max=%s" % ["%.6f" % x for x in mws])
    check("E6 🔴 「高权重」与「波长选择性」是**冲突目标**：预算 20% 时仅达 a 的 ~52%",
          abs(mws[1] / A - 0.5154) < 0.01,
          "frac_of_a=%.4f" % (mws[1] / A))

    # ==================================================== F 双旋钮位深
    gb = gap_knob_bits(alpha_bend_dBcm=BL)
    check("F1 gap 旋钮位深（**档位极差**口径）== 8.1328 bit ⇒ 达标（≥5）",
          abs(gb["bits_range"] - BITS_GAP_RANGE) < 1e-3 and gb["budget_met"] is True,
          "bits=%.4f" % gb["bits_range"])
    check("F2 单点口径 == 12.3236 bit（并列作反面对照）",
          abs(gb["bits_point"] - BITS_GAP_POINT) < 1e-3,
          "bits_point=%.4f" % gb["bits_point"])
    check("F3 🔴 单点口径系统性**高估** 1.52× ⇒ 一律用档位极差（钉住不利事实）",
          abs(gb["point_overestimates_x"] - 1.5153) < 1e-3
          and gb["point_overestimates_x"] > 1.4,
          "over=%.4f×" % gb["point_overestimates_x"])
    check("F4 档位极差最坏点在 gap=0.650µm（非设计点 0.30µm —— 故单点不可代表全域）",
          abs(gb["worst_gap_um"] - 0.650) < 1e-9
          and abs(gb["worst_gap_um"] - gb["design_gap_um"]) > 0.2,
          "worst_gap=%.4f design=%.2f" % (gb["worst_gap_um"], gb["design_gap_um"]))
    check("F5 🔴 扫描中的**越域点被显式报出**（不静默钳位）",
          gb["n_out_of_domain"] == 2
          and all(p["why"] for p in gb["out_of_domain_points"])
          and gb["n_sweep_points"] == len(gb["out_of_domain_points"]) + 69,
          "n_ood=%d n=%d" % (gb["n_out_of_domain"], gb["n_sweep_points"]))
    d_good = detuning_knob_bits(0.0405, R_um=R, alpha_bend_dBcm=BL)
    check("F6 失谐旋钮 κ=0.0405 ⇒ 5.7026 bit 达标（FWHM 170.67pm ≪ 2500pm）",
          abs(d_good["bits_range"] - 5.7026) < 1e-4
          and d_good["budget_met"] is True
          and abs(d_good["fwhm_pm"] - 170.675) < 5e-3,
          "bits=%.6f fwhm=%.6f" % (d_good["bits_range"], d_good["fwhm_pm"]))
    d_bad = detuning_knob_bits(0.147, R_um=R, alpha_bend_dBcm=BL)
    check("F7 🔴 κ=0.147 ⇒ 2.91 bit **不达标**（FWHM 499pm 过宽）—— 如实报出",
          abs(d_bad["bits_range"] - 2.91) < 5e-3 and d_bad["budget_met"] is False,
          "bits=%.4f" % d_bad["bits_range"])
    check("F8 失谐位深非单调于 κ（0.5 回升到 5.32 —— 与 FWHM 变宽 + 饱和区竞争）",
          detuning_knob_bits(0.5, R_um=R, alpha_bend_dBcm=BL)["bits_range"] > 5.0)

    # ========================================================= G 面积对比
    ar = area_vs_eo_modulator(R, gap_um=TABLE_PROBE_GAP_UM)
    check("G1 🔴 面积对真实 π 相移臂 == 1.2171% ≤ 10% ⇒ 达标",
          abs(ar["ratio_pi_arm"] - RATIO_PI_ARM) < 1e-8
          and ar["budget_met_pi_arm"] is True,
          "ratio=%.6f%%" % (100 * ar["ratio_pi_arm"]))
    check("G2 对局部胞元（Lu=20µm）为 60.86% —— 仅作对照，**不用于达标判定**",
          ar["ratio_unit_cell"] > AREA_BUDGET_RATIO
          and ar["budget_met_unit_cell"] is False,
          "ratio_uc=%.2f%%" % (100 * ar["ratio_unit_cell"]))
    rhw, rhh = device_bbox("RingAddDrop", {"R": R, "wg_width": W_UM,
                                            "gap": TABLE_PROBE_GAP_UM})
    ehw, ehh = device_bbox("MZI", {"Lu": PS_ARM_UM_DEFAULT, "dy": MZI_DY_UM_DEFAULT})
    ind_ratio = (4.0 * rhw * rhh) / (4.0 * ehw * ehh)
    check("G3 面积/比例 == 独立重算 device_bbox（参照源唯一，相对差 ≤ 1e-12）",
          abs(ar["ratio_pi_arm"] - ind_ratio) / ind_ratio <= 1e-12
          and abs(ar["ring_area_um2"] - 4.0 * rhw * rhh) < 1e-12,
          "ring=%.4f eo=%.1f" % (ar["ring_area_um2"], ar["eo_area_pi_arm_um2"]))
    check("G4 honest_note 明写判定口径（物理参照 vs 占位参照）",
          "ratio_pi_arm" in ar["honest_note"] and "对照" in ar["honest_note"])

    # ==================================================== H 权重库映射
    tinfo = calibration_table_info()
    bank = weight_bank_from_weights(W_BANK, wl_nm=WL_BANK)
    check("H1 🔴 默认 backend == fdtd-table（权重库不建立在已证差 39.5× 的占位上）",
          bank["backend"] == "fdtd-table"
          and tinfo["available"] is True
          and tinfo["gaps_um"] == [0.25, 0.3, 0.35, 0.4])
    check("H2 4 个目标权重全部落**已签发表内**（gap ∈ [0.25, 0.40]）",
          bank["all_reachable_in_table"] is True
          and bank["n_gap_outside_signed_table"] == 0
          and all(e["gap_in_signed_table"] for e in bank["entries"]),
          "n_out=%d" % bank["n_gap_outside_signed_table"])
    reach = bank["reachable_interval"]
    check("H3 可达权重区间 == [2.4984e-4, 8.0366e-2]（对应 gap [0.25,0.40]）",
          abs(reach["w_max"] - W_MAX_TABLE) < 1e-6
          and abs(reach["w_min"] - W_MIN_TABLE) < 1e-6
          and abs(reach["gap_lo_um"] - 0.25) < 1e-12
          and abs(reach["gap_hi_um"] - 0.40) < 1e-12,
          "w=[%.6g, %.6f]" % (reach["w_min"], reach["w_max"]))
    check("H4 反查 gap ⇒ κ(gap) 回到 entry['kappa']（往返 ≤ KAPPA_TOL，闭环自洽）",
          all(abs(kappa_at_gap(e["gap_um"], e["wl_nm"] * 1e-3, N_G_DEFAULT,
                               M_RING_DEFAULT, "fdtd-table") - e["kappa"]) <= KAPPA_TOL
              for e in bank["entries"]),
          "maxd=%.3e" % max(abs(kappa_at_gap(e["gap_um"], e["wl_nm"] * 1e-3,
                                             N_G_DEFAULT, M_RING_DEFAULT,
                                             "fdtd-table") - e["kappa"])
                            for e in bank["entries"]))
    out_bank = weight_bank_from_weights([0.005, 0.02, 0.5], wl_nm=1550.0)
    e_out = [e for e in out_bank["entries"] if e["gap_um"] is None]
    check("H5 🔴 表外权重**显式标注** gap=None + reason 非空（**不静默外推**）",
          len(e_out) == 1 and e_out[0]["w_target"] == 0.5
          and e_out[0]["unreachable_reason"]
          and e_out[0]["gap_in_signed_table"] is False
          and out_bank["all_reachable_in_table"] is False,
          "out=%d" % len(e_out))
    e_in = [e for e in out_bank["entries"] if e["gap_um"] is not None]
    check("H6 表内权重**不**被误标（reason is None 且 in_table True）",
          len(e_in) == 2 and all(e["unreachable_reason"] is None
                                 and e["gap_in_signed_table"] for e in e_in))
    check("H7 WDM 每信道环半径随中心波长微调（R 非恒定，与 U1 ring_anchors 同源）",
          max(e["R_um"] for e in bank["entries"])
          - min(e["R_um"] for e in bank["entries"]) > 1e-3,
          "R=[%.4f, %.4f]" % (min(e["R_um"] for e in bank["entries"]),
                              max(e["R_um"] for e in bank["entries"])))
    check("H8 honest_note 含可达区间与上限（dB）—— 不隐藏「表外不可达」",
          "可设计区间" in bank["honest_note"] and "dB" in bank["honest_note"]
          and "不静默外推" in bank["honest_note"])
    check("H9 空权重向量 / 波长长度不齐 ⇒ 必 raise",
          _rejects(lambda: weight_bank_from_weights([]), RingWeightBankError)
          and _rejects(lambda: weight_bank_from_weights([0.02, 0.04],
                                                        wl_nm=[1550.0]),
                       RingWeightBankError))

    # ==================================================== I 与 U1 共网格
    mesh = weight_bank_on_shared_mesh(W_BANK)
    check("I1 网格保真度**保持**（与 1.0 差 ≤ 1e-12，继承 U1 已证结论）",
          mesh["mesh_fidelity_preserved"]
          and abs(mesh["mesh_fidelity"] - 1.0) <= 1e-12
          and abs(mesh["mesh_layout_fidelity"] - 1.0) <= 1e-12,
          "fid=%.17g lay=%.17g" % (mesh["mesh_fidelity"],
                                   mesh["mesh_layout_fidelity"]))
    check("I2 权重层是对角幅度层（非对角元素恒 0 ⇒ 不破坏酉网格）",
          mesh["weight_layer_is_diagonal"] is True
          and mesh["weight_matrix_offdiag_max"] == 0.0)
    check("I3 全部信道满足 FWHM ≪ 信道间隔（选择性全通）",
          mesh["all_selectivity_ok"] is True
          and mesh["channel_spacing_nm"] == CHANNEL_SPACING_NM_DEFAULT)
    check("I4 权重数 ≠ 信道数 ⇒ 必 raise（WDM 须每信道一个环）",
          _rejects(lambda: weight_bank_on_shared_mesh([0.02]), RingWeightBankError))
    check("I5 共网格结构锚不被权重层改动（K=4 / N=16 / n_mzi=120 / DRC+LVS 维持）",
          mesh["K"] == 4 and mesh["N"] == 16 and mesh["n_mzi"] == 120
          and mesh["drc_pass"] is True and mesh["lvs_verdict"] == "ACCEPT",
          "K=%s N=%s n_mzi=%s" % (mesh["K"], mesh["N"], mesh["n_mzi"]))

    # ==================================================== J 诚实边界文本
    d = RING_WEIGHT_DISCLOSURE
    check("J1 🔴 披露「absolute_weight_not_calibrated」含 39.5× 与 16.0 dB",
          "39.5×" in d["absolute_weight_not_calibrated"]
          and "16.0 dB" in d["absolute_weight_not_calibrated"])
    check("J2 🔴 披露「analytic_placeholder_out_of_domain」含「违反能量守恒」与不截断承诺",
          "违反能量守恒" in d["analytic_placeholder_out_of_domain"]
          and "不静默截断" in d["analytic_placeholder_out_of_domain"])
    check("J3 🔴 披露「thermal_drift_not_calibrated」明写**不宣称已校准**（T1 铁律）",
          "不宣称已校准" in d["thermal_drift_not_calibrated"])
    check("J4 🔴 披露「no_fdtd_no_3d」明写不跑 FDTD / 不做 3D",
          "不跑 FDTD" in d["no_fdtd_no_3d"] and "3D" in d["no_fdtd_no_3d"])
    check("J5 🔴 披露「single_point_derivative_lies」含单点 12.32 vs 极差 8.13 实测对照",
          "12.32" in d["single_point_derivative_lies"]
          and "8.13" in d["single_point_derivative_lies"])
    check("J6 披露「weight_bandwidth_is_resonance_fwhm」点明权重带宽 = 谐振 FWHM",
          "FWHM" in d["weight_bandwidth_is_resonance_fwhm"]
          and "Q_i" in d["weight_bandwidth_is_resonance_fwhm"])
    check("J7 披露「nonneg_weight_only」点明只支撑非负权重网络",
          "非负" in d["nonneg_weight_only"]
          and "不建模" in d["nonneg_weight_only"])

    # ============================================ K 突变探针友好性（反向护栏）
    # 以下判据的意义：把「模块自报值」与「独立重算」的容差锁到**紧**，
    # 使任何伪造（哪怕改 1%）都会被立刻判红 —— 护栏必须证明自己会响。
    check("K1 独立重算 vs 模块 w 相对容差 ≤ 1e-12（改 1% 必红）",
          max(abs(_ind_w(k, R, BL) - peak_drop_weight(k, R, BL))
              / max(peak_drop_weight(k, R, BL), 1e-30) for k in ks) <= 1e-12)
    check("K2 位深断言容差 1e-3 bit（改 0.02% 即红）",
          abs(gb["bits_range"] - BITS_GAP_RANGE) < 1e-3)
    check("K3 面积比断言容差 1e-8（相对 8e-7 ⇒ 改 1e-6 即红）",
          abs(ar["ratio_pi_arm"] - RATIO_PI_ARM) < 1e-8)
    check("K4 「不达标」断言是**双向**的（F7 期望 False ⇒ 改成 True 必红）",
          d_bad["budget_met"] is False)
    check("K5 「表外不可达」断言是**双向**的（H5 期望有表外项 ⇒ 全可达必红）",
          out_bank["n_gap_outside_signed_table"] == 1
          and bank["n_gap_outside_signed_table"] == 0)

    total = PASS + FAIL
    print("-" * 74)
    print("ring_weight_bank smoke：%d PASS / %d FAIL / 共 %d 项" % (PASS, FAIL, total))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
