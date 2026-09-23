# -*- coding: utf-8 -*-
"""U8 常驻门禁：非易失权重后端（PCM / Sb₂Se₃）· **条件式设计**。

判据分组（A–I）
---------------
A 契约 / 披露 / 文献锚（含「GST 不许发明数字」与 B29 漂移检测）
B 红线守卫（机器化：畸形必 raise + 空集必过 + 合法必过 + 可满足性）
C 器件级编程态模型（闭式往返 + 域校验 raise + 周期等价 + 独立重算）
D 位深（dB 域模型恒等式 + 线性 T 域口径对照 + 反问题边界三态）
E retention / endurance（**下界**语义 + 地平线外推无据 + 盈亏平衡）
F 设计接口（与 `mesh_drive_manifest` / U4 权重库的**同形性机器判据**）
G 静态功耗（B29 物理锚 + **内部口径 12.96× 不一致**被钉住 + break-even 闭式）
H 跨后端对照（与 U4 / U7 同源取数 + 「0.2 dB 巧合」被显式标注）+ 报告结构
I 独立重算容差（必须紧到能把伪造值判红）

🔴 立场：本 smoke 断言的是**事实**，包括不利事实 ——
`A8` 断言 GST 的关键锚**全是 None**（拒绝发明数字）、`G3` 断言内部功耗口径
**不一致（12.96×）**、`H3` 断言 PCM 位深**低于** U4 微环、`E4` 断言高写入频次
**超耐久**、`F11` 断言部分权重**不可达**。若有人把模块改成「随便给 GST 编个数字 /
功耗基线自洽 / PCM 分辨率更好 / 权重任意可达」，这些判据立刻变红。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import lda_l2.nonvolatile_weight_backend as nvm_mod  # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402
from lda_l2.nonvolatile_weight_backend import (  # noqa: E402
    ARM_REF_UM,
    C_MAX,
    C_MIN,
    DEFAULT_MATERIAL,
    LITERATURE_ANCHORS,
    MATERIALS,
    NVM_DISCLOSURE,
    P2_VOA_LEN_UM,
    P2_VOA_THERMAL_MW,
    PARITY_KEYS_VS_DRIVE_MANIFEST,
    PARITY_KEYS_VS_WEIGHT_BANK,
    PHASE_FULL_SWING_RAD,
    PROVENANCE_KINDS,
    THERMAL_PHASE_EFF_DEG_PER_MW,
    THERMAL_PHASE_PI_POWER_MW,
    WDM_N_MZI_REF,
    WDM_N_OUT_REF,
    WRITE_POWER_RATIO_DEFAULT,
    WRITE_TIME_S_DEFAULT,
    NonvolatileBackendError,
    NonvolatileRedlineError,
    backend_interface_parity,
    bits_for_phase_error,
    c_for_il_db,
    c_for_phase,
    c_for_transmittance,
    cross_backend_comparison,
    endurance_break_even_writes_per_day,
    endurance_budget,
    guard_all_anchors_are_not_measured,
    guard_no_foundry_process_truth,
    il_db,
    level_budget,
    nonvolatile_backend_report,
    nvm_drive_manifest,
    phase_error_max_rad,
    phase_rad,
    power_baseline_consistency,
    programming_window,
    quantize_phase,
    require_numeric_anchor,
    retention_budget,
    static_power_saving,
    transmittance,
    weight_bank_from_weights,
    wrap_phase,
    write_power_break_even,
)

PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True, detail_fmt="  —— {d}", detail_on="fail")

# ---------------------------------------------------------------------------
# 本轮实测常量（冻结，用于「钉住」结论；全部可由独立重算复核）
# ---------------------------------------------------------------------------
ETA_B29 = 38.88019612769657          # °/mW（B29 物理锚 @1mW 默认参数）
P_PI_MW = 4.6296062758741021         # = 180 / ETA_B29
DR_DB = 0.2                          # 幅度域动态范围 = 2 × 0.1 dB/π
T_AT_C1 = 0.954992586021436           # 10^(−0.2/10)
T_RANGE = 0.045007413978564004
MAX_SLOPE = 0.04605170185988092
MID_SLOPE = 0.045003437145835566
BITS_T_POINT = 6.966908200500037
BITS_T_RANGE = 7.00012748144891
POINT_OVER = 1.023292992280754
PHASE_ERR_7 = 0.024543692606170259   # π/128
U4_GAP_BITS_RANGE = 8.132814304977007
U4_POINT_OVER = 1.5152892045331718
U4_A = 0.9913004121028992
U4_ATT_DR = 0.03794713276958582
ATT_DR_RATIO = 5.2704904271528425
B29_PER_MM = 4.629606275874102
P2_PER_MM = 60.0
POWER_BASELINE_RATIO = 12.960065375898857
STATIC_120_16_MW = 629.62645351887784
STATIC_4_4_MW = 37.03685020699283
STATIC_16_16_MW = 148.14740082797127
BREAK_EVEN_WRITES_PER_DAY = 27397.260273972603      # 1e8 / (365×10)
ENDURANCE_MARGIN_1PD = 27397.260273972603
W99_C = 0.21824027
W99_IL = 0.04364805402450088
W97_IL = 0.1322826573375516
DISCLOSURE_KEYS = 13


def _rejects(fn, exc: type = Exception) -> bool:
    """fn() 必须抛 exc（且不是别的异常）⇒ True。"""
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


# ---- 独立重算助手（不复用模块函数，用于抓「模块改错但自洽」） ----
def _ind_il(c: float) -> float:
    """IL(c) = (2π·c/π)·0.1 = 0.2·c（从文献锚与全摆幅假设直接展开）。"""
    return (2.0 * math.pi * c / math.pi) * 0.1


def _ind_T(c: float) -> float:
    return 10.0 ** (-_ind_il(c) / 10.0)


def _ind_c_from_il(il: float) -> float:
    return il / 0.2


def _ind_c_from_T(t: float) -> float:
    return -10.0 * math.log10(t) / 0.2


def _ind_p_pi(eta: float) -> float:
    return 180.0 / eta


def _ind_static_mw(n_phase: int, eta: float) -> float:
    return n_phase * 180.0 / eta


def _ind_margin(ec: float, writes_per_day: float, horizon: float) -> float:
    return ec / (writes_per_day * 365.0 * horizon)


def main():  # noqa: C901
    from lda_harness.b29_thermal_phase_anchor import (   # 漂移检测
        b29_thermal_phase_efficiency,
    )

    # ======================================================= A 契约 / 披露 / 锚
    check("A1 披露项键齐全（%d 项，防被悄悄删）" % DISCLOSURE_KEYS,
          len(NVM_DISCLOSURE) == DISCLOSURE_KEYS,
          "len=%d" % len(NVM_DISCLOSURE))
    check("A2 披露项值均为非空字符串",
          all(isinstance(v, str) and v.strip() for v in NVM_DISCLOSURE.values()))
    check("A3 披露含「文献锚≠实测」「不做能力宣称」「红线」三条核心声明",
          all(k in NVM_DISCLOSURE for k in
              ("literature_anchor_not_measurement", "no_capability_claim",
               "no_foundry_process_truth")))
    check("A4 材料集合 == {Sb2Se3, GST, ModeConverter2026}；默认材料 == Sb2Se3",
          set(MATERIALS) == {"Sb2Se3", "GST", "ModeConverter2026"}
          and DEFAULT_MATERIAL == "Sb2Se3",
          "= %s / default=%s" % (sorted(MATERIALS), DEFAULT_MATERIAL))
    check("A5 🔴 全锚 is_measured_by_this_project is False（本项目无 PCM 实测）",
          all(a["is_measured_by_this_project"] is False for a in LITERATURE_ANCHORS.values()))
    check("A6 全锚 provenance ∈ PROVENANCE_KINDS（不含 measurement）",
          all(a["provenance"] in PROVENANCE_KINDS for a in LITERATURE_ANCHORS.values())
          and "measurement" not in PROVENANCE_KINDS)
    sb = LITERATURE_ANCHORS["Sb2Se3"]
    check("A7 Sb₂Se₃ 文献锚四项 == 7bit / 10yr / 1e8 / 0.1 dB/π",
          sb["levels_bits"] == 7.0 and sb["retention_years"] == 10.0
          and sb["endurance_cycles"] == 1.0e8 and sb["il_db_per_pi"] == 0.1,
          "%s/%s/%s/%s" % (sb["levels_bits"], sb["retention_years"],
                           sb["endurance_cycles"], sb["il_db_per_pi"]))
    check("A8 Sb₂Se₃ retention / endurance 均标为**下界**（非中心值）",
          sb["retention_is_lower_bound"] is True and sb["endurance_is_lower_bound"] is True)
    gst = LITERATURE_ANCHORS["GST"]
    check("A9 🔴 GST 的 levels_bits / retention / endurance / il_db_per_pi **全为 None**"
          "（文献未给数字 ⇒ 拒绝发明）",
          gst["levels_bits"] is None and gst["retention_years"] is None
          and gst["endurance_cycles"] is None and gst["il_db_per_pi"] is None,
          "bits=%r ret=%r end=%r il=%r" % (gst["levels_bits"], gst["retention_years"],
                                           gst["endurance_cycles"], gst["il_db_per_pi"]))
    check("A10 GST 唯一可用信息 = 定性约束 crossbar_limit == 3",
          gst["crossbar_limit"] == 3)
    check("A11 全摆幅设计预算 == 2π（**假设**常量，非文献值）",
          abs(PHASE_FULL_SWING_RAD - 2.0 * math.pi) < 1e-15
          and abs(C_MIN) < 1e-15 and abs(C_MAX - 1.0) < 1e-15)
    mc = LITERATURE_ANCHORS["ModeConverter2026"]
    check("A12 ModeConverter2026 只给位深（5bit），其余全 None（非权重元件）",
          mc["levels_bits"] == 5.0 and mc["il_db_per_pi"] is None
          and mc["retention_years"] is None)
    check("A13 参照规模 == U1 实测 K=4×N=16（120 MZI / 16 输出）",
          (WDM_N_MZI_REF, WDM_N_OUT_REF) == (120, 16))
    check("A14 🔴 B29 热光效率锚**实时重算**一致（35.88 漂移即红）",
          abs(b29_thermal_phase_efficiency() - ETA_B29) < 1e-12
          and abs(THERMAL_PHASE_EFF_DEG_PER_MW - ETA_B29) < 1e-12,
          "live=%.15f const=%.15f" % (b29_thermal_phase_efficiency(),
                                      THERMAL_PHASE_EFF_DEG_PER_MW))
    check("A15 P_π 常量 == 180/η（独立重算）",
          abs(THERMAL_PHASE_PI_POWER_MW - _ind_p_pi(ETA_B29)) < 1e-12,
          "=%.15f" % THERMAL_PHASE_PI_POWER_MW)

    # ======================================================= B 红线守卫
    check("B1 畸形载荷（键含 foundry）⇒ raise NonvolatileRedlineError",
          _rejects(lambda: guard_no_foundry_process_truth({"foundry_corner": 1}),
                   NonvolatileRedlineError))
    check("B2 畸形载荷（键含 tcad）⇒ raise",
          _rejects(lambda: guard_no_foundry_process_truth({"tcad_alpha": 1.0}),
                   NonvolatileRedlineError))
    check("B3 畸形载荷（中文键「工艺角」）⇒ raise",
          _rejects(lambda: guard_no_foundry_process_truth({"工艺角": "ss"}),
                   NonvolatileRedlineError))
    check("B4 空载荷 ⇒ 通过（空集反例：守卫不误伤）",
          not _rejects(lambda: guard_no_foundry_process_truth({}), Exception))
    check("B5 🔴 散文**值**含 foundry ⇒ **不**触发（钉住「只扫键名」是有意设计）",
          not _rejects(lambda: guard_no_foundry_process_truth(
              {"note": "不碰 foundry 工艺真值"}), Exception))
    check("B6 嵌套畸形（深层键含 foundry）⇒ raise",
          _rejects(lambda: guard_no_foundry_process_truth({"a": {"b": {"foundry_x": 1}}}),
                   NonvolatileRedlineError))
    check("B7 列表内元素键含 foundry ⇒ raise",
          _rejects(lambda: guard_no_foundry_process_truth({"rows": [{"foundry_y": 1}]}),
                   NonvolatileRedlineError))
    check("B8 🔴 声明键 False ⇒ 通过（守卫**可满足**，非按构造恒红）",
          not _rejects(lambda: guard_no_foundry_process_truth(
              {"foundry_process_truth_used": False}), Exception))
    check("B9 🔴 声明键 True ⇒ raise（声明「有工艺真值」本身违规）",
          _rejects(lambda: guard_no_foundry_process_truth(
              {"foundry_process_truth_used": True}), NonvolatileRedlineError))
    check("B10 深层声明键 True ⇒ raise（递归收集，非只看顶层）",
          _rejects(lambda: guard_no_foundry_process_truth(
              {"a": [{"foundry_process_truth_used": True}]}), NonvolatileRedlineError))
    bad_measured = {"X": {"provenance": "literature", "is_measured_by_this_project": True}}
    check("B11 🔴 锚标 is_measured=True ⇒ raise（T1：本项目无 PCM 实测）",
          _rejects(lambda: guard_all_anchors_are_not_measured(bad_measured),
                   NonvolatileRedlineError))
    bad_prov = {"X": {"provenance": "measurement", "is_measured_by_this_project": False}}
    check("B12 锚标 provenance='measurement' ⇒ raise",
          _rejects(lambda: guard_all_anchors_are_not_measured(bad_prov),
                   NonvolatileRedlineError))
    check("B13 合法锚（原样）⇒ 通过（「合法必过」）",
          not _rejects(lambda: guard_all_anchors_are_not_measured(), Exception))
    check("B14 require_numeric_anchor(GST,'il_db_per_pi') ⇒ raise（宁缺毋滥）",
          _rejects(lambda: require_numeric_anchor("GST", "il_db_per_pi"),
                   NonvolatileBackendError))
    check("B15 require_numeric_anchor(GST,'levels_bits') ⇒ raise",
          _rejects(lambda: require_numeric_anchor("GST", "levels_bits"),
                   NonvolatileBackendError))
    check("B16 require_numeric_anchor(不存在的字段) ⇒ raise",
          _rejects(lambda: require_numeric_anchor("Sb2Se3", "no_such_field"),
                   NonvolatileBackendError))
    check("B17 🔴 端到端：level_budget('GST') ⇒ raise（缺锚 ⇒ 拒绝数值预算）",
          _rejects(lambda: level_budget("GST"), NonvolatileBackendError))
    check("B18 🔴 端到端：endurance_break_even('GST') ⇒ raise",
          _rejects(lambda: endurance_break_even_writes_per_day("GST"),
                   NonvolatileBackendError))

    # ======================================================= C 编程态模型
    check("C1 phase_rad 线性：φ(0)=0 / φ(0.5)=π / φ(1)=2π",
          abs(phase_rad(0.0)) < 1e-15
          and abs(phase_rad(0.5) - math.pi) < 1e-14
          and abs(phase_rad(1.0) - 2.0 * math.pi) < 1e-14)
    check("C2 🔴 il_db(1.0) == 0.2 dB（= 2 × 0.1 dB/π 文献锚）",
          abs(il_db(1.0) - DR_DB) < 1e-15, "=%.17g" % il_db(1.0))
    check("C3 transmittance(1.0) == 10^(−0.2/10)（与独立重算逐位一致，容差 0）",
          transmittance(1.0) == T_AT_C1 and T_AT_C1 == _ind_T(1.0),
          "=%.17g" % transmittance(1.0))
    check("C4 il_db 对 c 严格单调递增（10 点扫描）",
          all(il_db(0.1 * i) < il_db(0.1 * (i + 1)) for i in range(10)))
    check("C5 transmittance 对 c 严格单调递减（10 点扫描）",
          all(transmittance(0.1 * i) > transmittance(0.1 * (i + 1)) for i in range(10)))
    check("C6 il_db 与独立重算逐位一致（@0/0.25/0.5/0.75/1，容差 0）",
          all(il_db(c) == _ind_il(c) for c in (0.0, 0.25, 0.5, 0.75, 1.0)),
          ";".join("%.17g" % il_db(c) for c in (0.0, 0.25, 0.5, 0.75, 1.0)))
    check("C7 c ∉ [0,1] ⇒ raise（1.0001 / −0.001 都不静默截断）",
          _rejects(lambda: il_db(1.0001), NonvolatileBackendError)
          and _rejects(lambda: phase_rad(-0.001), NonvolatileBackendError))
    check("C8 未知材料 ⇒ raise",
          _rejects(lambda: il_db(0.5, "Si3N4"), NonvolatileBackendError))
    check("C9 c→φ→c 往返机器精度（0.3 / 0.7）",
          abs(c_for_phase(phase_rad(0.3)) - 0.3) < 1e-15
          and abs(c_for_phase(phase_rad(0.7)) - 0.7) < 1e-15)
    check("C10 🔴 c=1.0 往返得 0.0（φ=2π ≡ 0 的**精确周期等价**，不是 bug）",
          c_for_phase(phase_rad(1.0)) == 0.0,
          "→ %.17g" % c_for_phase(phase_rad(1.0)))
    check("C11 c_for_phase(wrap=False) 越域 ⇒ raise；wrap=True ⇒ 折回",
          _rejects(lambda: c_for_phase(7.0, wrap=False), NonvolatileBackendError)
          and abs(c_for_phase(7.0, wrap=True) - (7.0 % (2.0 * math.pi)) / (2.0 * math.pi)) < 1e-15)
    check("C12 wrap_phase(−π/4) == 7π/4；wrap_phase(7π/2) == 3π/2",
          abs(wrap_phase(-math.pi / 4.0) - 7.0 * math.pi / 4.0) < 1e-14
          and abs(wrap_phase(7.0 * math.pi / 2.0) - 3.0 * math.pi / 2.0) < 1e-14)
    check("C13 非有限相位 ⇒ raise",
          _rejects(lambda: c_for_phase(float("nan")), NonvolatileBackendError)
          and _rejects(lambda: c_for_phase(float("inf")), NonvolatileBackendError))
    check("C14 c_for_il_db 越域（0.3 dB > 0.2 dB 上限）⇒ raise",
          _rejects(lambda: c_for_il_db(0.3), NonvolatileBackendError))
    check("C15 c→IL→c 往返机器精度（独立重算一致）",
          all(abs(c_for_il_db(il_db(c)) - c) < 1e-15 for c in (0.0, 0.3, 0.7, 1.0)))
    check("C16 c→T→c 往返机器精度（≤1.2e-15）",
          all(abs(c_for_transmittance(transmittance(c)) - c) < 1.5e-15
              for c in (0.0, 0.3, 0.7, 1.0)))
    check("C17 c_for_transmittance 域校验：T ≤ 0 / T > 1 ⇒ raise；T < T_min ⇒ raise",
          _rejects(lambda: c_for_transmittance(0.0), NonvolatileBackendError)
          and _rejects(lambda: c_for_transmittance(1.5), NonvolatileBackendError)
          and _rejects(lambda: c_for_transmittance(0.5), NonvolatileBackendError))
    check("C18 il_db / c_for_il_db 对 GST ⇒ raise（缺锚）",
          _rejects(lambda: il_db(0.5, "GST"), NonvolatileBackendError))
    win = programming_window()
    check("C19 🔴 幅度域动态范围只有 0.2 dB ⇒ PCM 是**相位**元件不是衰减元件",
          abs(win["attenuation_dynamic_range_db"] - DR_DB) < 1e-15
          and win["weight_nonnegative_only"] is True)
    check("C20 programming_window 幅度下限 == 独立重算 10^(−0.2/10)",
          abs(win["amplitude_range"][0] - _ind_T(1.0)) < 1e-16)
    check("C21 未知材料 ⇒ programming_window raise",
          _rejects(lambda: programming_window("GST"), NonvolatileBackendError))

    # ======================================================= D 位深
    lb = level_budget()
    check("D1 bits_source == 'literature'（未显式指定位深时取文献锚）",
          lb["bits_source"] == "literature" and lb["bits_literature"] == 7.0)
    check("D2 bits_used == 7.0 / levels == 128",
          lb["bits_used"] == 7.0 and lb["levels"] == 128.0)
    check("D3 Δc == 1/128 · Δφ == 2π/128 · ΔIL == 0.0015625（独立重算一致）",
          lb["dc"] == 0.0078125
          and abs(lb["phi_step_rad"] - 2.0 * math.pi / 128.0) < 1e-18
          and lb["il_step_db"] == 0.0015625
          and abs(lb["phi_step_rad"] - 2.0 * phase_error_max_rad(7)) < 1e-18,
          "dφ=%.17g ΔIL=%.17g" % (lb["phi_step_rad"], lb["il_step_db"]))
    check("D4 🔴 dB 域位深 == 所用位深（**线性模型的恒等式**，非测得）",
          abs(lb["bits_db"] - lb["bits_used"]) < 1e-12 and lb["bits_db_is_model_identity"] is True,
          "%.15f vs %.15f" % (lb["bits_db"], lb["bits_used"]))
    td = lb["t_domain"]
    check("D5 t_range == 独立重算 1 − 10^(−0.2/10)",
          abs(td["t_range"] - (1.0 - _ind_T(1.0))) < 1e-17, "%.17g" % td["t_range"])
    check("D6 max_slope == ln10/10·DR·T(0)（独立解析重算）",
          abs(td["max_slope_per_c"] - math.log(10.0) / 10.0 * DR_DB * 1.0) < 1e-17)
    check("D7 mid_slope == ln10/10·DR·T(0.5)（独立解析重算）",
          abs(td["mid_slope_per_c"]
              - math.log(10.0) / 10.0 * DR_DB * _ind_T(0.5)) < 1e-16)
    check("D8 单点口径高估 == T(0)/T(0.5) == 1.023292992280754",
          abs(td["point_overestimates_x"] - POINT_OVER) < 1e-14,
          "=%.17g" % td["point_overestimates_x"])
    check("D9 单点口径高估 == 1/独立重算 T(0.5)（方向性：单点 > 档位极差）",
          abs(td["point_overestimates_x"] - 1.0 / _ind_T(0.5)) < 1e-14
          and td["bits_t_point"] < td["bits_t_range"])
    check("D10 bits_t_point / bits_t_range 与冻结值一致",
          abs(td["bits_t_point"] - BITS_T_POINT) < 1e-12
          and abs(td["bits_t_range"] - BITS_T_RANGE) < 1e-12)
    check("D11 🔴 PCM 单点高估（偏离 1 仅 0.0233）**远小于** U4 微环（偏离 1 达 0.515×）"
          "（因 IL∝c 线性 ⇒ T 仅弱指数）",
          abs(td["point_overestimates_x"] - 1.0) < abs(U4_POINT_OVER - 1.0) / 10.0,
          "dev=%.6f vs U4 dev=%.6f"
          % (abs(td["point_overestimates_x"] - 1.0), abs(U4_POINT_OVER - 1.0)))
    lb8 = level_budget(bits=8)
    check("D12 bits=8 ⇒ bits_source == 'override' 且 levels == 256",
          lb8["bits_source"] == "override" and lb8["levels"] == 256.0)
    check("D13 bits ≤ 0 ⇒ raise",
          _rejects(lambda: level_budget(bits=0), NonvolatileBackendError))
    check("D14 phase_error_max_rad(7) == π/128 == 0.024543692606170259（= 1.40625°）",
          abs(phase_error_max_rad(7) - PHASE_ERR_7) < 1e-18
          and abs(math.degrees(phase_error_max_rad(7)) - 1.40625) < 1e-12)
    check("D15 phase_error_max_rad(bits ≤ 0) ⇒ raise",
          _rejects(lambda: phase_error_max_rad(0), NonvolatileBackendError))
    e7 = phase_error_max_rad(7)
    r_exact = bits_for_phase_error(e7)
    r_loose = bits_for_phase_error(e7 * (1.0 + 1e-9))
    r_strict = bits_for_phase_error(e7 * (1.0 - 1e-9))
    check("D16 🔴 反问题边界三态：恰等于 7-bit 半步 ⇒ 7 bit（仅吸收浮点噪声）",
          r_exact["bits_required"] == 7 and r_exact["levels_required"] == 128,
          "%d bit / %d lv" % (r_exact["bits_required"], r_exact["levels_required"]))
    check("D17 稍宽（+1e-9）⇒ 7 bit（不因舍入多要一位）",
          r_loose["bits_required"] == 7)
    check("D17b 🔴 反解**无**浮点容差死护栏（`PHASE_ERR_REL_TOL` 经探针证明无必要后已删）",
          not hasattr(nvm_mod, "PHASE_ERR_REL_TOL"),
          "still present" if hasattr(nvm_mod, "PHASE_ERR_REL_TOL") else "removed")
    check("D17c 边界输入的 `levels_raw` 在 IEEE 下是**精确整数** 128（无需容差的依据）",
          r_exact["levels_raw"] == 128.0, "=%.17g" % r_exact["levels_raw"])
    check("D18 🔴 严格优于（−1e-9）⇒ **8** bit（诚实：更严的需求必须更多位）",
          r_strict["bits_required"] == 8, "%d bit" % r_strict["bits_required"])
    check("D19 bits_for_phase_error 非法输入 ⇒ raise（err ≤ 0 / span ≤ 0）",
          _rejects(lambda: bits_for_phase_error(0.0), NonvolatileBackendError)
          and _rejects(lambda: bits_for_phase_error(0.01, 0.0), NonvolatileBackendError))

    # ======================================================= E retention / endurance
    check("E1 🔴 地平线语义：5/10 年 ⇒ 满足；10.0001/20 年 ⇒ **不满足**（下界不外推）",
          retention_budget(horizon_years=5.0)["meets_horizon"] is True
          and retention_budget(horizon_years=10.0)["meets_horizon"] is True
          and retention_budget(horizon_years=10.0001)["meets_horizon"] is False
          and retention_budget(horizon_years=20.0)["meets_horizon"] is False)
    check("E2 horizon ≤ 0 ⇒ raise",
          _rejects(lambda: retention_budget(horizon_years=0.0), NonvolatileBackendError))
    eb = endurance_budget(writes_per_day=1.0, horizon_years=10.0)
    check("E3 1 次/天 × 10 年 ⇒ 需 3650 次（独立重算一致）· 余量 ≈ 27397.26×",
          eb["writes_total_required"] == 3650.0
          and abs(eb["margin_x"] - ENDURANCE_MARGIN_1PD) < 1e-9
          and eb["meets_endurance"] is True)
    eb2 = endurance_budget(writes_per_day=1.0e5, horizon_years=10.0)
    check("E4 🔴 1e5 次/天 × 10 年 ⇒ 需 3.65e8 次 **超耐久**（不利结论如实报出）",
          eb2["writes_total_required"] == 3.65e8 and eb2["meets_endurance"] is False,
          "req=%.6g meets=%s" % (eb2["writes_total_required"], eb2["meets_endurance"]))
    check("E5 余量与独立重算一致（相对误差 < 1e-15）",
          abs(eb["margin_x"] / _ind_margin(1.0e8, 1.0, 10.0) - 1.0) < 1e-15)
    check("E6 writes_per_day < 0 / horizon ≤ 0 ⇒ raise",
          _rejects(lambda: endurance_budget(writes_per_day=-1.0), NonvolatileBackendError)
          and _rejects(lambda: endurance_budget(horizon_years=0.0), NonvolatileBackendError))
    be = endurance_break_even_writes_per_day(horizon_years=10.0)
    check("E7 盈亏平衡写入频次 == 1e8/(365×10) == 27397.260273972603",
          abs(be["writes_per_day_star"] - BREAK_EVEN_WRITES_PER_DAY) < 1e-9)
    check("E8 🔴 GST 无 endurance 锚 ⇒ meets=False 且 anchor_available=False",
          endurance_budget("GST")["meets_endurance"] is False
          and retention_budget("GST")["anchor_available"] is False)
    check("E9 披露含「下界」与「未做加速老化」",
          "下界" in NVM_DISCLOSURE["retention_endurance_are_lower_bounds"]
          and "加速老化" in NVM_DISCLOSURE["retention_endurance_are_lower_bounds"])

    # ======================================================= F 同形接口
    par = backend_interface_parity()
    check("F1 🔴 与 mesh_drive_manifest 的必需共有键全中（%s）"
          % ",".join(PARITY_KEYS_VS_DRIVE_MANIFEST),
          par["drive_manifest_required_ok"] is True
          and set(par["drive_manifest_required"]) == set(PARITY_KEYS_VS_DRIVE_MANIFEST))
    check("F2 drive_manifest 共有键 == {mzi,n_mzi,n_out,out}",
          set(par["drive_manifest_shared"]) == {"mzi", "n_mzi", "n_out", "out"},
          "= %s" % par["drive_manifest_shared"])
    check("F3 🔴 与 U4 权重库的必需共有键全中（%s）"
          % ",".join(PARITY_KEYS_VS_WEIGHT_BANK),
          par["weight_bank_required_ok"] is True)
    check("F4 差异键集合**非空且被解释**（同形≠同物理）",
          bool(par["drive_manifest_only_nvm"]) and bool(par["drive_manifest_only_dm"])
          and len(par["expected_semantic_diff"]) == 2)
    check("F5 差异说明含「非易失」与「材料维」两个语义点",
          "非易失" in par["expected_semantic_diff"]["drive"]
          and "材料维" in par["expected_semantic_diff"]["bank"])
    check("F6 同形性说明明写「不可互换」",
          "不可互换" in par["honest_note"])
    check("F7 nvm_drive_manifest 空清单 ⇒ raise",
          _rejects(lambda: nvm_drive_manifest([]), NonvolatileBackendError))
    check("F8 nvm_drive_manifest n_mzi 越界 ⇒ raise",
          _rejects(lambda: nvm_drive_manifest([0.1, 0.2], n_mzi=3),
                   NonvolatileBackendError))
    dm = nvm_drive_manifest([0.0, 0.5, 1.0, 3.0 * math.pi / 2.0], n_mzi=2)
    check("F9 🔴 「不报」功耗而非「报 0」：static_power_reported is False",
          dm["static_power_reported"] is False and dm["static_power_mw"] == 0.0)
    check("F10 manifest 分槽正确（n_mzi=2 ⇒ 2 个 mzi + 2 个 out）",
          dm["n_mzi"] == 2 and dm["n_out"] == 2 and len(dm["mzi"]) == 2
          and len(dm["out"]) == 2)
    check("F11 manifest 量化误差 ≤ N-bit 理论上限（含 2π 边界）",
          dm["max_err_rad"] <= phase_error_max_rad(7) + 1e-15,
          "max=%.15f cap=%.15f" % (dm["max_err_rad"], phase_error_max_rad(7)))
    check("F12 quantize_phase(2π) == quantize_phase(0)（周期等价）",
          quantize_phase(2.0 * math.pi, 7)["level_index"] == 0
          and abs(quantize_phase(2.0 * math.pi, 7)["err_rad"]) < 1e-15)
    q_top = quantize_phase(PHASE_FULL_SWING_RAD - 1e-15, 7)
    check("F12b 🔴 电平号恒在 [0, n_levels) 内（2π−ε 边界不得得 128 ⇒ 取模不可省）",
          q_top["level_index"] < q_top["n_levels"] and q_top["level_index"] >= 0
          and q_top["level_index"] == 0,
          "idx=%d / n=%d" % (q_top["level_index"], q_top["n_levels"]))
    check("F13 nvm_drive_manifest 位深 ≤ 0 ⇒ raise",
          _rejects(lambda: nvm_drive_manifest([0.1], bits=0), NonvolatileBackendError))
    bk = weight_bank_from_weights([1.0, 0.99, 0.97, 0.5])
    check("F14 🔴 幅度域极窄 ⇒ 目标权重 0.5 **不可达**且**显式标注**（不静默外推）",
          bk["entries"][3]["reachable"] is False
          and bk["entries"][3]["unreachable_reason"] is not None
          and bk["n_unreachable"] == 1)
    check("F15 w=1.0 ⇒ c=0 / level 0 / IL=0（端点精确）",
          bk["entries"][0]["c_required"] == 0.0
          and bk["entries"][0]["level_index"] == 0
          and bk["entries"][0]["il_db"] == 0.0)
    check("F16 w=0.99 ⇒ c/level/IL 与冻结值一致（c 走闭式反演）",
          abs(bk["entries"][1]["c_required"] - W99_C) < 1e-8
          and abs(bk["entries"][1]["il_db"] - W99_IL) < 1e-12)
    check("F17 w=0.99 的 c 与独立重算一致（相对误差 < 1e-9）",
          abs(bk["entries"][1]["c_required"] / _ind_c_from_T(0.99) - 1.0) < 1e-9)
    check("F18 w=0.97 ⇒ IL 与独立重算一致",
          abs(bk["entries"][2]["il_db"] - (-10.0 * math.log10(0.97))) < 1e-12
          and abs(bk["entries"][2]["il_db"] - W97_IL) < 1e-12)
    check("F19 权重库空向量 ⇒ raise；w > 1 ⇒ 不可达（**raise 与不可达语义分离**）",
          _rejects(lambda: weight_bank_from_weights([]), NonvolatileBackendError)
          and weight_bank_from_weights([1.5])["entries"][0]["reachable"] is False)
    check("F20 权重库 honest_note 明写「不静默外推」且含计数",
          "不静默外推" in bk["honest_note"] and "1/4" in bk["honest_note"])
    check("F21 波长序列长度不匹配 ⇒ raise",
          _rejects(lambda: weight_bank_from_weights([0.99, 0.99], wl_nm=[1550.0]),
                   NonvolatileBackendError))

    # ======================================================= G 静态功耗
    check("G1 P_π == 180/38.88019612769657 == 4.6296062758741021（独立重算）",
          abs(_ind_p_pi(ETA_B29) - P_PI_MW) < 1e-15)
    check("G2 🔴 B29 **实时重算**一致（上游漂移即红）",
          abs(180.0 / b29_thermal_phase_efficiency() - P_PI_MW) < 1e-12)
    pb = power_baseline_consistency()
    check("G3 🔴 内部口径**不一致**被钉住：B29 4.6296 mW/mm vs P2 60.0 mW/mm ⇒ 12.96×",
          abs(pb["ratio_p2_over_b29"] - POWER_BASELINE_RATIO) < 1e-9
          and pb["within_one_order_of_magnitude"] is False,
          "ratio=%.15f" % pb["ratio_p2_over_b29"])
    check("G4 P2 口径独立重算 == 15 mW / 0.25 mm == 60 mW/mm",
          abs(pb["p2_assumption_mw_per_mm"]
              - P2_VOA_THERMAL_MW / (P2_VOA_LEN_UM / 1000.0)) < 1e-12
          and pb["p2_assumption_mw_per_mm"] == P2_PER_MM)
    check("G5 B29 口径独立重算 == 4.6296 mW / 1.0 mm",
          abs(pb["b29_anchor_mw_per_mm"]
              - _ind_p_pi(ETA_B29) / (ARM_REF_UM / 1000.0)) < 1e-15)
    check("G6 基线披露含「不可引用」与「量级级不确定度」",
          "不可引用" in pb["note"] and "量级级" in pb["note"])
    sp = static_power_saving()
    check("G7 N=16 网格（120+16=136 相移器）⇒ 热调静态 629.62645351887784 mW",
          sp["n_phase_total"] == 136
          and abs(sp["thermal_static_power_mw"] - STATIC_120_16_MW) < 1e-9)
    check("G8 省量比 == 1.0（100% 静态功耗）且 PCM 静态 == 0",
          sp["saving_ratio"] == 1.0 and sp["nvm_static_power_mw"] == 0.0
          and abs(sp["saved_mw"] - sp["thermal_static_power_mw"]) < 1e-15)
    check("G9 🔴 绝对 mW **不可引用**（absolute_mw_quotable is False）",
          sp["absolute_mw_quotable"] is False)
    check("G10 小/中规模独立重算（4+4 与 16+16）",
          abs(static_power_saving(4, 4)["thermal_static_power_mw"] - STATIC_4_4_MW) < 1e-9
          and abs(static_power_saving(16, 16)["thermal_static_power_mw"] - STATIC_16_16_MW) < 1e-9
          and abs(static_power_saving(16, 16)["thermal_static_power_mw"]
                  - _ind_static_mw(32, ETA_B29)) < 1e-15)
    check("G11 n_mzi / n_out < 0 ⇒ raise",
          _rejects(lambda: static_power_saving(-1, 0), NonvolatileBackendError))
    check("G12 η ≤ 0 ⇒ raise",
          _rejects(lambda: static_power_saving(1, 1, eff_deg_per_mw=0.0),
                   NonvolatileBackendError))
    wb = write_power_break_even()
    check("G13 🔴 break-even 占空比 d* == 1/k == 0.1；重写周期 == k·t_write == 1e-5 s",
          abs(wb["duty_star"] - 1.0 / WRITE_POWER_RATIO_DEFAULT) < 1e-15
          and abs(wb["reprogram_interval_star_s"]
                  - WRITE_POWER_RATIO_DEFAULT * WRITE_TIME_S_DEFAULT) < 1e-21,
          "d*=%.17g T*=%.17g" % (wb["duty_star"], wb["reprogram_interval_star_s"]))
    check("G14 break-even 明写「都是**假设值**」与「条件式」",
          "假设值" in wb["note"] and "条件式" in wb["note"])
    check("G15 k ≤ 0 / t_write ≤ 0 ⇒ raise",
          _rejects(lambda: write_power_break_even(p_write_over_p_static=0.0),
                   NonvolatileBackendError)
          and _rejects(lambda: write_power_break_even(t_write_s=0.0),
                       NonvolatileBackendError))

    # ======================================================= H 跨后端对照 + 报告
    cb = cross_backend_comparison()
    check("H1 🔴 U4 档位极差位深**跨模块实时**一致（8.1328，上游漂移即红）",
          abs(cb["u4_gap_bits_range"] - U4_GAP_BITS_RANGE) < 1e-12,
          "=%.15f" % cb["u4_gap_bits_range"])
    check("H2 U4 单点高估 == 1.5152892045331718（U4 文档称 1.52×）",
          abs(cb["u4_point_overestimates_x"] - U4_POINT_OVER) < 1e-12)
    check("H3 🔴 PCM 文献位深 **低于** U4 微环（优势在功耗不在分辨率）",
          cb["u8_bits_db"] < cb["u4_gap_bits_range"] and cb["bits_ratio_u8_over_u4"] < 1.0,
          "%.6f < %.6f" % (cb["u8_bits_db"], cb["u4_gap_bits_range"]))
    check("H4 U4 权重上限 a == 0.9913004121028992 · 幅度动态范围 == 0.03794713276958582 dB",
          abs(cb["u4_weight_ceiling_a"] - U4_A) < 1e-15
          and abs(cb["u4_att_dynamic_range_db"] - U4_ATT_DR) < 1e-15)
    check("H5 🔴 幅度动态范围比 PCM/U4 == 5.2704904271528425（PCM 更大但**同类**缺陷）",
          abs(cb["att_dr_ratio_u8_over_u4"] - ATT_DR_RATIO) < 1e-12,
          "=%.15f" % cb["att_dr_ratio_u8_over_u4"])
    check("H6 🔴 「热光臂损耗 0.2 dB == PCM 全摆幅文献损耗 0.2 dB」是**圆整数字巧合**，已显式标注",
          abs(cb["thermal_arm_prop_loss_db"] - cb["pcm_full_swing_il_db"]) < 1e-15
          and "巧合" in cb["note"] and "不可当设计收益引用" in cb["note"])
    check("H7 U7 α_prop 跨模块一致 == 2.0 dB/cm；参照臂 1000µm",
          cb["alpha_prop_db_cm"] == 2.0 and cb["arm_ref_um"] == ARM_REF_UM)
    rep = nonvolatile_backend_report()
    need_top = {"mat", "anchor", "programming_window", "level_budget", "retention",
                "endurance", "static_power", "power_baseline", "write_break_even",
                "cross_backend", "guard_declaration", "disclosure", "prose"}
    check("H8 总报告顶层键齐全（%d 项）" % len(need_top),
          need_top.issubset(set(rep)),
          "missing=%s" % sorted(need_top - set(rep)))
    check("H9 🔴 报告 guard_declaration 两键均为 False（且守卫在必经路径上跑过）",
          rep["guard_declaration"].get("foundry_process_truth_used") is False
          and rep["guard_declaration"].get("anchors_measured_by_this_project") is False)
    check("H10 报告披露 == NVM_DISCLOSURE 全 %d 键" % DISCLOSURE_KEYS,
          set(rep["disclosure"]) == set(NVM_DISCLOSURE)
          and len(rep["disclosure"]) == DISCLOSURE_KEYS)
    check("H11 🔴 GST 无数值锚 ⇒ **总报告本就不可构造**（raise，而非「生成一份空报告」）",
          _rejects(lambda: nonvolatile_backend_report("GST"), NonvolatileBackendError)
          and rep["endurance_break_even"] is not None)
    check("H12 🔴 报告水平线取 20 年 ⇒ retention 如实报不满足（不利结论进入报告）",
          rep["retention"]["meets_horizon"] is False
          and nonvolatile_backend_report(horizon_years=5.0)["retention"]["meets_horizon"] is True)
    rep_payload = {k: v for k, v in rep.items() if k not in ("prose", "disclosure")}
    check("H13 报告 prose 含 foundry 字样、但守卫在**必经路径**上仍通过"
          "（钉住「只扫键名」是有意设计与可满足性）",
          "foundry" in rep["prose"]["redline"].lower()
          and not _rejects(lambda: guard_no_foundry_process_truth(rep_payload), Exception))
    check("H14 报告可 JSON 序列化（结构完整）",
          isinstance(__import__("json").dumps(rep, ensure_ascii=False, default=str), str))

    # ======================================================= I 独立重算容差
    check("I1 il_db 与独立重算**逐位一致**（容差 0 ⇒ 伪造值必红）",
          all(il_db(c) == _ind_il(c) for c in
              [i / 100.0 for i in range(0, 101, 7)]))
    check("I2 静态功耗与独立重算相对误差 < 1e-15",
          abs(static_power_saving(37, 11)["thermal_static_power_mw"]
              / _ind_static_mw(48, ETA_B29) - 1.0) < 1e-15)
    check("I3 独立重算的 T 与模块 T 相对误差 < 1e-16",
          all(abs(transmittance(c) / _ind_T(c) - 1.0) < 1e-16
              for c in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)))
    check("I4 🟡 探针自证：把「独立重算」故意写错 1e-3 ⇒ 判据会变红"
          "（证明容差紧到有判别力）",
          abs(_ind_il(0.5) * (1.0 + 1e-3) - il_db(0.5)) > 1e-9)

    print("-" * 70)
    print("U8 非易失权重后端（PCM/Sb₂Se₃）· 条件式设计：%d 判据 · %d FAIL"
          % (PASS + FAIL, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
