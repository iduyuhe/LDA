# -*- coding: utf-8 -*-
"""LDA 光子存储征程 · PM-M4 外设与系统层门禁（判据 + 突变探针）。

判据（全部**重算**，不读字面量）：
  A1 模块自检：`pm_m4.run_selfchecks()` 18/18（同源调用，非转录）
  B1 读出链跨源一致：`|Z|` ≡ `eic_behavioral.tia_transimpedance_ohm` ∧ `f_3db` ≡
     `tia_bandwidth_hz` ∧ R_f 带宽上界 ≡ 二者反函数（三处同源，防静默失配）
  B2 PD 电流恒等式（重算）：`I_pd ≡ R_pd·p_in·T`
  B3 噪声恒等式（重算）：`σ_I² ≡ i_shot² + i_thermal²`
  B4 判决链恒等式（重算）：`SNR ≡ ΔV/(2σ_V)` ∧ `BER ≡ 0.5·erfc(SNR/√2)`（取最坏相邻对）
  B5 🔴 灵敏度**逆解自洽**：`p_min` 处 BER ≤ 目标 ∧ `p_min/2` 处 BER > 目标（真最小）
  C1 加热器电阻同源上层几何：`R ≡ R_sheet·(L_h/w_h)` ∧ `L_h ≡ pm_m3.cell_length_um`
  C2 写驱动恒等式（重算）：`E ≡ P·t` ∧ `P ≡ V²/R`
  C3 脉宽动态范围 ≡ `pm_m1.pulse_ladder` 的 `t_ratio_to_first`（同源重算）
  C4 🔴 系统预算：`ε_tot² ≡ Σ ε_i²` ∧ 瓶颈 == `argmax(ε)`（算出来的）
  C5 🔴 drift 段 ε ≡ `ν_T_ub·ln(t/t₀)`（**主账算自光学域上界锚**，PM-G7 结算）∧ 随保持时间单调升
  C6 🔴 最大保持时间逆解自洽：`t_max` 处 ≤ 目标 ∧ `2·t_max` 处 > 目标
  D1 2.5D 独立解码：层 65 == 2×通道数 ∧ 层 64/66 存在 ∧ DRC PASS ∧ LVS ACCEPT
  D2 PIC die bbox ≡ `pm_m3` 签核 bbox（同源）∧ 通道数 ≡ 器件数 − 2×总线
  D3 🔴 密度瓶颈判据（算出来的）：EIC pitch ↕ PIC pitch ⇒ `density_bottleneck` 翻转
  D4 2.5D GDS 字节 ≠ PIC 阵列 GDS 字节（真装配，非原样复用）
  E1 披露守卫：`disclosure` 全真 ∧ 真实输出**肯定式面**禁词零命中
  F1 缺口台账如实开放：含 `PM-G7`（光学域 drift 无锚）与 `PM-G8`（T1/T2 锁死）
  T1–T9 外设参数**物理核验与作用域**（v0.9.311 · `PM-G9a` 闭合依据）：响应度硬上限
     `R ≤ λ/1239.84`（η≤1）∧ 真实链路 `SNR(2R,P/2) ≡ SNR(R,P)` ∧ `P_min·R ≡ u*` ∧
     **`worst_pair` 是退化标签**（15 对同 SNR，min() 按浮点噪声挑）∧ 方阻作用域
     `P∝1/R_sheet`(电压驱动) ⇄ `V∝√R_sheet`(恒功率) ∧ 3.3 V 直驱过驱 ≥5×
  G1 🔴 内置快照 schema **逐块 == 仓库报告 JSON**（防「每加一批锚就多一份静默失真」）

突变探针（每条**先证能变红**，还原后复绿）：
  P1 读出速率提高 100× ⇒ R_f 带宽上界降 100×（证明上界由公式算出，非硬编码）
  P2 PD 响应度减半 ⇒ 各级 `I_pd` 逐位减半（证明 I_pd 走公式）
  P3 驱动位深 8→4 ⇒ `ε_write` 变 64×（证明写段误差是算出来的）
  P4 4 单元 vs 8 单元 ⇒ 层 65 解码数不同（证明期望非恒真）
  P5 EIC pitch 压到 0.8 µm ⇒ 通道条宽 < min_width ⇒ DRC 必红（判据可被证伪）
"""
from __future__ import annotations

import json
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')

from lda_l2 import eic_behavioral as EIC  # noqa: E402
from lda_l2 import pm_m1 as M1            # noqa: E402
from lda_l2 import pm_m2 as M2            # noqa: E402
from lda_l2 import pm_m3 as M3            # noqa: E402
from lda_l2 import pm_m4 as M4            # noqa: E402

_BANNED_POSITIVE = ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "fJ·op", "pJ/bit")
_NEG_TOKENS = ("不报", "不得报", "禁止", "禁用", "never", "not reported",
               "no efficiency", "不承诺", "不声称", "非", "无")


def _positive_surface(text: str) -> str:
    """只取**肯定式面**：剔除含否定标记的从句（否定式免责句不该让判据恒红）。"""
    parts = []
    for clause in text.replace("；", "。").replace(";", "。").split("。"):
        if any(tok in clause for tok in _NEG_TOKENS):
            continue
        parts.append(clause)
    return "。".join(parts)


def main() -> int:
    print("=" * 74)
    print("LDA 光子存储征程 · PM-M4 外设与系统门禁（读出链 + 写驱动 + 系统预算 + 2.5D）")
    print("=" * 74)

    # ── A1 模块自检（同源调用）────────────────────────────────────────────
    check("A1 `pm_m4.run_selfchecks()` 18/18（同源调用，非转录）",
          M4.run_selfchecks() is True)

    rep = M4.m4_report("GST")
    ro = M4.readout_chain("GST")

    # ── B1 读出链跨源一致（TIA 三处同源）──────────────────────────────────
    z_ref = abs(EIC.tia_transimpedance_ohm(ro["f_read_hz"], ro["r_f_ohm"], ro["c_f_f"]))
    bw_ref = EIC.tia_bandwidth_hz(ro["r_f_ohm"], ro["c_f_f"])
    check("B1 读出链跨源一致：|Z| ≡ eic_behavioral ∧ f_3db ≡ tia_bandwidth_hz ∧ R_f 上界 ≡ 反函数",
          abs(ro["z_mag_ohm"] - z_ref) < 1e-9
          and abs(ro["f_3db_hz"] - bw_ref) < 1e-6 * bw_ref
          and abs(EIC.tia_bandwidth_hz(ro["r_f_max_ohm"], ro["c_f_f"]) - ro["f_read_hz"]) < 1e-6,
          "|Z|=%.6g f_3db=%.6g" % (ro["z_mag_ohm"], ro["f_3db_hz"]))

    # ── B2 PD 电流恒等式（重算）──────────────────────────────────────────
    j = 5
    lvj = M4.level_transmittance("GST")["levels"][j]
    _ipd_exp = ro["resp_a_per_w"] * ro["p_in_w"] * lvj["T"]
    check("B2 PD 电流恒等式：I_pd ≡ R_pd·p_in·T（重算，取第 6 级 · 相对 1e-12）",
          abs(ro["levels"][j]["i_pd_a"] - _ipd_exp) <= 1e-12 * _ipd_exp,
          "I_pd=%.6g" % ro["levels"][j]["i_pd_a"])

    # ── B3 噪声恒等式（重算）────────────────────────────────────────────
    r0 = ro["levels"][0]
    _i2 = r0["i_shot_a"] ** 2 + r0["i_thermal_a"] ** 2
    check("B3 噪声恒等式：σ_I² ≡ i_shot² + i_thermal²（重算，相对 1e-12）",
          abs(r0["sigma_i_a"] ** 2 - _i2) <= 1e-12 * _i2)

    # ── B4 判决链恒等式（重算）──────────────────────────────────────────
    wp = ro["worst_pair"]
    _dv = ro["levels"][wp[1]]["v_out_v"] - ro["levels"][wp[0]]["v_out_v"]
    _snr = _dv / (2.0 * ro["levels"][0]["sigma_v_v"])
    check("B4 判决链恒等式：SNR ≡ ΔV/(2σ_V) ∧ BER ≡ 0.5·erfc(SNR/√2)（重算，最坏对）",
          abs(_snr - ro["worst_snr"]) < 1e-9 * max(ro["worst_snr"], 1.0)
          and abs(M4._erfc_ber(_snr) - ro["worst_ber"]) < 1e-18,
          "SNR=%.6g BER=%.3g" % (ro["worst_snr"], ro["worst_ber"]))

    # ── B5 灵敏度逆解自洽（真最小）───────────────────────────────────────
    sens = M4.readout_sensitivity("GST")
    _ber_half = M4.readout_chain("GST", p_in_w=sens["p_min_w"] / 2.0)["worst_ber"]
    check("B5 灵敏度逆解自洽：p_min 处 ≤ 目标 ∧ p_min/2 处 > 目标（真最小值）",
          sens["reachable"] and sens["ber_at"] <= sens["target_ber"]
          and _ber_half > sens["target_ber"],
          "p_min=%.4g W (%.2f dBm) margin=%.1f×"
          % (sens["p_min_w"], sens.get("p_min_dbm", float("nan")), sens.get("margin_x", 0.0)))

    # ── C1 加热器电阻同源上层几何 ────────────────────────────────────────
    hr = M4.heater_resistance("GST")
    _l_cell = float(M3.cell_length_um()["l_um"])
    check("C1 加热器电阻同源：R ≡ R_sheet·(L_h/w_h) ∧ L_h ≡ pm_m3 单元光程长",
          abs(hr["r_lo_ohm"] - hr["sheet_rho_lo_ohm_sq"] * hr["n_squares"]) < 1e-12
          and abs(hr["l_h_um"] - _l_cell) < 1e-12,
          "R=[%.2f, %.2f] Ω" % (hr["r_lo_ohm"], hr["r_hi_ohm"]))

    # ── C2 写驱动恒等式（重算）──────────────────────────────────────────
    wd = M4.write_driver("GST")
    check("C2 写驱动恒等式：E ≡ P·t ∧ P ≡ V²/R（重算）",
          abs(wd["e_lo_j"] - wd["p_lo_w"] * wd["t_pulse_s"]) <= 1e-12 * wd["e_lo_j"]
          and abs(wd["p_lo_w"] - wd["v_drv"] ** 2 / wd["r_hi_ohm"]) <= 1e-12 * wd["p_lo_w"],
          "P=[%.4g, %.4g] W E=[%.4g, %.4g] J"
          % (wd["p_lo_w"], wd["p_hi_w"], wd["e_lo_j"], wd["e_hi_j"]))

    # ── C3 脉宽动态范围同源 M1 ──────────────────────────────────────────
    _srcs = M1.kinetic_sources("GST")
    _lad = M1.pulse_ladder(tuple(0.1 + 0.8 * k / 15 for k in range(16)),
                           800.0, float(_srcs[0]["ea_ev"]), 2.0)
    check("C3 脉宽动态范围 ≡ pm_m1.pulse_ladder 的 t_ratio_to_first（同源重算）",
          abs(wd["pulse_ladder_ratio"] - float(_lad[-1]["t_ratio_to_first"])) < 1e-12,
          "ratio=%.4f" % wd["pulse_ladder_ratio"])

    # ── C4 系统预算合成恒等式 + 瓶颈 argmax ──────────────────────────────
    sb = rep["system_budget"]
    _s2 = sum(v * v for v in sb["eps"].values())
    check("C4 系统预算：ε_tot² ≡ Σ ε_i²（相对 1e-12）∧ 瓶颈 == argmax(ε)",
          abs(sb["eps_total"] ** 2 - _s2) <= 1e-12 * _s2
          and sb["bottleneck"] == max(sb["eps"], key=lambda k: sb["eps"][k]),
          "ε_tot=%.6g bottleneck=%s" % (sb["eps_total"], sb["bottleneck"]))

    # ── C5 drift 段算自光学域上界锚（主账 · PM-G7 结算）+ 保持时间单调 ────
    nuo = M2.nu_optical_bound("GST")
    _b1h = M4.system_link_budget("GST", t_hold_s=1.0)
    _b3600 = M4.system_link_budget("GST", t_hold_s=3600.0)
    check("C5 drift 段 ε ≡ ν_T_ub·ln(t/t₀)（**主账算自光学域上界锚**）∧ 随 t 单调升",
          abs(_b3600["eps"]["drift"] - float(nuo["nu_ub_max"]) * __import__("math").log(3600.0)) < 1e-12
          and _b3600["eps"]["drift"] > _b1h["eps"]["drift"],
          "ν_T_ub=%.4g ε_drift(1h)=%.6g" % (float(nuo["nu_ub_max"]), _b3600["eps"]["drift"]))

    # ── C6 最大保持时间逆解自洽 ─────────────────────────────────────────
    tm = sb["max_t_hold_s_for_target"]
    _ber_tm = M4.system_link_budget("GST", t_hold_s=tm)["ber_total"]
    _ber_2 = M4.system_link_budget("GST", t_hold_s=2.0 * tm)["ber_total"]
    check("C6 最大保持时间逆解自洽：t_max 处 ≤ 目标 ∧ 2·t_max 处 > 目标",
          tm > 0.0 and _ber_tm <= sb["ber_target"] and _ber_2 > sb["ber_target"],
          "t_max=%.4g s (%s)" % (tm, sb["max_t_hold_human"]))

    # ── D1 2.5D 独立解码 + DRC/LVS ──────────────────────────────────────
    a = M4.system_2p5d("GST", n_cells=8, n_buses=1)
    _L65 = int(M4._L_M1)
    _lay = a["independent_scan"]["layers"]
    check("D1 2.5D 独立解码：层 65 == 2×通道数 ∧ 层 64/66 存在 ∧ DRC PASS ∧ LVS ACCEPT",
          int(_lay.get(_L65, 0)) == 2 * a["n_channels"]
          and int(_lay.get(int(M4._L_INTERPOSER), 0)) >= 2
          and int(_lay.get(int(M4._L_ASIC), 0)) >= 1
          and a["drc"]["all_pass"] and a["lvs"]["verdict"] == "ACCEPT",
          "n_ch=%d layers=%s" % (a["n_channels"], dict(_lay)))

    # ── D2 PIC die bbox 同源 + 通道数恒等式 ─────────────────────────────
    _so = M3.layout_signoff(M3.build_array(8, n_buses=1))
    _bb = _so["gds_stats"]["bbox_um"]
    check("D2 PIC die bbox ≡ pm_m3 签核 bbox ∧ 通道数 ≡ 器件数 − 2×总线",
          abs(a["pic_die_um"][0] - (float(_bb[2]) - float(_bb[0]))) < 1e-9
          and abs(a["pic_die_um"][1] - (float(_bb[3]) - float(_bb[1]))) < 1e-9
          and a["n_channels"] == int(_so["gds_stats"]["n_devices"]) - 2,
          "pic=%s" % (a["pic_die_um"],))

    # ── D3 密度瓶颈判据（算出来的）──────────────────────────────────────
    a_narrow = M4.system_2p5d("GST", n_cells=8, n_buses=1, eic_pitch_um=5.0)
    _pic_pitch = float(M3.cell_pitch_um("GST")["pitch_um"])
    check("D3 密度瓶颈判据：EIC pitch ↕ PIC pitch ⇒ density_bottleneck 翻转（PIC pitch 同源 M3）",
          abs(a["pic_pitch_um"] - _pic_pitch) < 1e-12
          and a["density_bottleneck"] == ("eic" if a["eic_pitch_um"] > _pic_pitch else "pic")
          and a_narrow["density_bottleneck"] == "pic",
          "pic=%.4f eic=%.1f → %s" % (a["pic_pitch_um"], a["eic_pitch_um"], a["density_bottleneck"]))

    # ── D4 2.5D GDS ≠ PIC 阵列 GDS（真装配）────────────────────────────
    check("D4 2.5D GDS 字节 ≠ PIC 阵列 GDS 字节（真装配，非原样复用）",
          a["gds_bytes_len"] != len(_so["gds_bytes"]),
          "2p5d=%d B vs pic=%d B" % (a["gds_bytes_len"], len(_so["gds_bytes"])))

    # ── E1 披露守卫 ─────────────────────────────────────────────────────
    # 🔴 PM-G7 结算后 disclosure 含**故意的 False**（drift 段不再是跨域代理）⇒
    #    「全真」改为「既定披露键全真 ∧ drift 三键口径正确」（False 也是有效披露态）。
    disc = rep["disclosure"]
    surf = _positive_surface(json.dumps(disc, ensure_ascii=False))
    hits = [t for t in _BANNED_POSITIVE if t in surf]
    _must_true = {k: v for k, v in disc.items() if k not in (
        "drift_segment_is_cross_domain_proxy",)}
    check("E1 披露守卫：既定披露键全真 ∧ drift 三键口径正确（False 也是有效披露态）"
          "∧ 肯定式面禁词零命中",
          all(bool(v) for v in _must_true.values() if isinstance(v, bool))
          and disc["drift_segment_is_cross_domain_proxy"] is False
          and disc["drift_segment_main_account_is_measured_optical_upper_bound"] is True
          and disc["retention_claims_depend_on_detection_floor_assumption"] is True
          and not hits,
          "禁词命中=%s" % hits)

    # ── F1 缺口台账如实开放 ─────────────────────────────────────────────
    from lda_webui import pm_case as PC
    _gids = [g["id"] for g in PC.GAPS]
    _g8 = next(g for g in PC.GAPS if g["id"] == "PM-G8")
    check("F1 缺口台账如实：PM-G7 仍开放（光学域 drift）∧ PM-G8 已闭合（v0.9.293 电-热联仿）∧ PM-G8b 边界声明",
          "PM-G7" in _gids and "PM-G8" in _gids and "PM-G8b" in _gids
          and _g8["status"].startswith("已闭合")
          and next(g for g in PC.GAPS if g["id"] == "PM-G8b")["status"].startswith("边界声明"),
          "缺口=%s" % _gids)

    check("F1b 缺口台账含 v0.9.311 拆分结果 G9a/G9b（且旧 PM-G9 号已退役）",
          "PM-G9a" in _gids and "PM-G9b" in _gids and "PM-G9" not in _gids,
          "缺口=%s" % _gids)

    # ── H 加热器电-热-光链路（v0.9.293 · PM-G8 闭合依据）────────────────
    # 🔴 改前：热阻是**与几何无关的手填常数** `R_TH_K_PER_MW = 1.0`（只注「文献量级」），
    #    而同一台机器上「热阻」本可由几何算出 ⇒ **两口径相差 12.51× 且从无人核**。
    from lda_l2 import pm_thermal as PT
    from lda_design import active_models as AM

    _sc = PT.selfcheck_pm_thermal()
    check("H1 pm_thermal 自检全过（稳态守恒 / 双能量路径 / 阶跃 τ 点 / 线性 / 层和 / 非法几何）",
          not [k for k, v in _sc.items() if not v],
          "fail=%s" % [k for k, v in _sc.items() if not v])

    _rep = PT.heater_link_report()
    _lk = _rep["link"]
    check("H2 卡内披露数值 ≡ 模块现算（逐项，正则取断言值 · 防「文案与代码各说各话」）",
          abs(float(re.search(r"R_th \*\*([\d.]+) K/mW", _g8["status"]).group(1))
              - round(_lk["R_th_K_per_mW"], 2)) <= 5e-3
          and abs(float(re.search(r"T1=τ=([\d.]+) µs", _g8["status"]).group(1))
                  - round(_lk["tau_us"], 2)) <= 5e-3
          and abs(float(re.search(r"P_π \*\*([\d.]+) mW", _g8["status"]).group(1))
                  - round(_lk["P_pi_mw"], 3)) <= 5e-4,
          "R_th=%.4f τ=%.4f P_pi=%.4f" % (_lk["R_th_K_per_mW"], _lk["tau_us"], _lk["P_pi_mw"]))

    check("H3 对照支路① 稳态能量守恒：P ≡ ΔT/R_th（回代，绝对 1e-15）",
          _rep["check_steady_state"]["abs_diff"] <= 1e-15,
          "P=%.9f P_back=%.9f" % (_rep["check_steady_state"]["P_mw"],
                                  _rep["check_steady_state"]["P_back_mw"]))
    check("H4 对照支路② 两条能量路径相等：C_th·ΔT_π ≡ P_π·τ（相对 1e-12 · 因 τ=R·C）",
          _rep["check_energy_rel"] <= 1e-12, "rel=%.3e" % _rep["check_energy_rel"])
    check("H5 对照支路③ 阶跃 τ 点 == 1−e⁻¹ = 0.6321205588285577（与参数无关的闭式已知答案）",
          abs(_rep["check_step_at_tau"] - (1.0 - math.exp(-1.0))) <= 1e-15,
          "%.16f" % _rep["check_step_at_tau"])
    check("H6 自洽：ΔT=R_th·P ⇒ **功率比 × 热阻比 ≡ 1**（验证两侧用同一个 R_th；本身抓不住 R 写错）",
          abs(_lk["P_pi_ratio_vs_const"] * _lk["R_th_ratio_vs_const"] - 1.0) <= 1e-12,
          "P比=%.6f R比=%.6f" % (_lk["P_pi_ratio_vs_const"], _lk["R_th_ratio_vs_const"]))
    # 🔴 H6b **绝对量级锚点**（v0.9.287 教训：比值判据对单位错/量级错完全无能为力
    #    —— 上面 H6 的乘积与 R_th 取值无关，R 错 100 倍它照样绿）
    check("H6b 🔴 绝对量级锚点（文献区间，**比值判据的盲区由本条兜住**）："
          "R_th ∈ [5,50] K/mW ∧ τ ∈ [1,100] µs ∧ P_π ∈ [0.5,50] mW",
          5.0 <= _lk["R_th_K_per_mW"] <= 50.0
          and 1.0 <= _lk["tau_us"] <= 100.0
          and 0.5 <= _lk["P_pi_mw"] <= 50.0,
          "R=%.3f τ=%.2f P=%.3f" % (_lk["R_th_K_per_mW"], _lk["tau_us"], _lk["P_pi_mw"]))
    check("H7 🔴 **未擅自改对外数字**：现役 `R_TH_K_PER_MW` 仍为 1.0 且 `phase_shift_rad` 默认仍用它（1D 值只并列披露）",
          float(AM.R_TH_K_PER_MW) == 1.0
          and abs(AM.phase_shift_rad(1.0, 100.0) - (2 * math.pi / AM.WL_UM * AM.DN_DT_SI_PER_K * 1.0 * 100.0)) <= 1e-15
          and abs(_lk["R_th_K_per_mW"] - AM.R_TH_K_PER_MW) > 1.0,
          "1D=%.4f 常数=%.1f" % (_lk["R_th_K_per_mW"], AM.R_TH_K_PER_MW))
    # H8 反向探针（每条先证能变红）：① 卡上 R_th 文案 ×2 ⇒ H2 红；② R_th ×0.01（单位错模拟）⇒ H6b 红；
    #    ③ τ 文案 ×2 ⇒ H2 红；④ 层热阻少算一层 ⇒ H6b 的绝对值必变
    _h2_red = abs(_lk["R_th_K_per_mW"] * 2.0 - round(_lk["R_th_K_per_mW"], 2)) > 5e-3
    _h6b_red = not (5.0 <= _lk["R_th_K_per_mW"] * 0.01 <= 50.0)
    _h2_red_tau = abs(_lk["tau_us"] * 2.0 - round(_lk["tau_us"], 2)) > 5e-3
    _drop_box = PT.thermal_time_constant({"t_box_um": 0.01})["tau_us"]
    _h6b_red2 = abs(_drop_box - _lk["tau_us"]) > 1.0
    check("H8 反向探针：卡上 R_th×2 ⇒ H2 红 ∧ R_th×0.01（单位错）⇒ H6b 红 ∧ τ×2 ⇒ H2 红 ∧ 抽掉 BOX 层 ⇒ τ 必变",
          _h2_red and _h6b_red and _h2_red_tau and _h6b_red2,
          "h2=%s h6b=%s h2tau=%s box=%s" % (_h2_red, _h6b_red, _h2_red_tau, _h6b_red2))

    # ── G1 内置快照 schema == 仓库报告 JSON ─────────────────────────────
    snap = PC.STATIC_SNAPSHOT["m4"]
    rep_fp = os.path.join(_ROOT, "examples", "photo_memory", "lda_pm_m4_report.json")
    schema_bad = []
    if not os.path.exists(rep_fp):
        schema_bad.append("(报告缺失: %s)" % rep_fp)
    else:
        with open(rep_fp, encoding="utf-8") as fh:
            repj = json.load(fh)

        def _dig(o, keys):
            for k in keys:
                o = o[k]
            return o
        for keys, label in (
            (("readout",), "读出链"),
            (("write_driver",), "写驱动"),
            (("system_budget",), "系统预算"),
            (("assembly_2p5d",), "2.5D 装配"),
            (("rf_tradeoff",), "R_f 权衡"),
            (("upstream",), "上游"),
            (("upstream", "levels"), "上游电平"),
        ):
            ka, kb = set(_dig(snap, keys).keys()), set(_dig(repj, keys).keys())
            if ka != kb:
                schema_bad.append("%s(%s): 快照缺%s 报告多%s"
                                  % (label, ".".join(keys), sorted(ka - kb), sorted(kb - ka)))
    check("G1 🔴 内置快照 schema **逐块 == 仓库报告 JSON**（防「每加一批锚就多一份静默失真」）",
          not schema_bad, "失配：%s" % schema_bad[:3])

    # ═══════════════ 突变探针（先证能变红）═══════════════
    # P1 读出速率 ×100 ⇒ 上界 ÷100
    _ro_fast = M4.readout_chain("GST", f_read_hz=ro["f_read_hz"] * 100.0)
    check("P1 探针：读出速率 ×100 ⇒ R_f 带宽上界 ÷100（证明上界由公式算出，非硬编码）",
          abs(_ro_fast["r_f_max_ohm"] - ro["r_f_max_ohm"] / 100.0) < 1e-9 * ro["r_f_max_ohm"],
          "up=%.6g" % _ro_fast["r_f_max_ohm"])

    # P2 响应度减半 ⇒ I_pd 逐位减半
    _ro_half = M4.readout_chain("GST", resp_a_per_w=ro["resp_a_per_w"] / 2.0)
    check("P2 探针：PD 响应度减半 ⇒ 各级 I_pd 逐位减半（证明 I_pd 走公式）",
          abs(_ro_half["levels"][j]["i_pd_a"] - ro["levels"][j]["i_pd_a"] / 2.0)
          < 1e-30 + 1e-12 * ro["levels"][j]["i_pd_a"])

    # P3 驱动位深 8→4 ⇒ ε_write 变 64×
    _wd4 = M4.write_driver("GST", driver_bits=4)
    _ratio = _wd4["eps_write"] / wd["eps_write"]
    check("P3 探针：驱动位深 8→4 ⇒ ε_write 变 ~64×（证明写段误差是算出来的）",
          abs(_ratio - (2 ** 8 - 1) / (2 ** 4 - 1)) < 1e-9,
          "ε4/ε8=%.4f" % _ratio)

    # P4 4 单元 vs 8 单元 ⇒ 层 65 解码数不同
    _a4 = M4.system_2p5d("GST", n_cells=4, n_buses=1)
    check("P4 探针：4 单元 vs 8 单元 ⇒ 层 65 解码数不同（期望非恒真）",
          int(_a4["independent_scan"]["layers"].get(_L65, 0))
          != int(_lay.get(_L65, 0)),
          "4→%s 8→%s" % (_a4["independent_scan"]["layers"].get(_L65),
                         _lay.get(_L65)))

    # P5 EIC pitch 压到 0.8 µm（放宽 min_pad）⇒ 通道条宽 < min_width ⇒ DRC 必红
    _tight = M4.system_2p5d("GST", n_cells=8, n_buses=1, eic_pitch_um=0.8,
                            rules={"min_width_um": 0.5, "min_space_um": 0.5, "min_pad_um": 0.5})
    check("P5 探针：EIC pitch=0.8 µm ⇒ 通道条宽 < min_width ⇒ DRC 必红（判据可被证伪）",
          _tight["drc"]["channel_width_ok"] is False and _tight["drc"]["all_pass"] is False,
          "ch_w=%.3f" % (0.8 * 0.5))

    # ── T 外设参数的物理核验与作用域（v0.9.311 · PM-G9a 闭合依据）──────────
    # 缺口原文：「PD 响应度 / 加热器方阻取公开工程典型区间（非实测、非逐条 DOI）…
    # ⇒ 外设结论只给区间 + 恒等式 + 单调性，**无绝对真值**」。
    # 本节不改任何区间（改区间才是编数据），只把「无绝对真值」这句话**按条拆开**：
    # 哪些结论其实**是绝对的**、哪些只是区间、以及方阻的不确定度**从哪个口子**进去。
    from lda_l2 import pm_peripheral_scope as PSC

    _p, _t, _ = PSC.run_selfchecks(verbose=False)
    check("T1 `pm_peripheral_scope` 自检全过（%d 项：恒等式 / 上限 / 反比律 / 作用域 / 反向）"
          % _t, _p == _t, "PASS=%d/%d" % (_p, _t))

    # T2 🔴 物理上限（门禁**自己算**，不读模块自检结论）：R ≤ λ/1239.84（η≤1）
    _rmax = 1550.0 / 1239.841984
    _ap = PSC.anchor_physics_check()
    check("T2 🔴 响应度硬上限 R_max(1550) = %.6f A/W（≈教科书 1.25，相对差 %.1e）∧ "
          "锚区间隐含 η ∈ [%.3f, %.3f] ⊂ (0,1] ∧ 距上限余量 %.1f%%"
          % (_rmax, abs(_rmax / 1.25 - 1.0), _ap["eta_lo"], _ap["eta_hi"],
             100.0 * _ap["headroom_to_physics"]),
          abs(_rmax / 1.25 - 1.0) < 0.01 and _ap["eta_in_unit_interval"]
          and not _ap["upper_bound_violated"] and _ap["headroom_to_physics"] > 0.2,
          "η=[%.4f, %.4f]" % (_ap["eta_lo"], _ap["eta_hi"]))

    # T3 反向探针：声称 R=1.3 A/W @1550 ⇒ η>1 ⇒ **可证不可能**（判据非恒真）
    check("T3 反向探针：R=1.3 A/W @1550 ⇒ η = %.3f > 1 ⇒ 违反 η≤1 ⇒ 该声明可证不可能"
          % PSC.qe_from_responsivity(1.3, 1550.0),
          PSC.qe_from_responsivity(1.3, 1550.0) > 1.0)

    # T4 🔴 真实链路：SNR 只依赖 `R·P`（若某处单独用了 R 或 P，本条立红）
    _inv = PSC.snr_invariance()
    check("T4 🔴 真实读出链 SNR(2R, P/2) ≡ SNR(R, P)（相对差 %.1e ≤ 1e-12）"
          % _inv["rel_diff"], _inv["rel_diff"] < 1e-12,
          "SNR=%.4f ⇄ %.4f" % (_inv["snr_a"], _inv["snr_b"]))

    # T5 🔴 反比律：`P_min(R)·R ≡ u*`（真实链路二分逆解，两档；容差 = 二分相对分辨率量级）
    _law = PSC.p_min_law(r_values=(0.8, 1.0), iters=52)
    check("T5 🔴 P_min(R)·R ≡ u*：R=0.8 与 R=1.0 两档乘积相对离散 %.2e ≤ 1e-9 ⇒ "
          "**灵敏度精确反比于响应度**" % _law["product_spread_rel"],
          _law["product_spread_rel"] < 1e-9,
          "P_min: " + " ".join("%.4e" % r["p_min_w"] for r in _law["rows"]))

    # T6 🔴 本版最意外的发现：`worst_pair` 是**退化标签**（15 对同 SNR，min() 按浮点噪声挑）
    _wpi = PSC.worst_pair_invariance()
    check("T6 🔴 全部 %d 个判决对 SNR 相同（相对离散 %.1e）⇒ `worst_pair` 由 min() 在并列值里"
          "挑 ⇒ 三档 R 给出 %s ⇒ **该标签不可引用为结论**"
          % (_wpi["n_pairs"], _wpi["max_pair_spread"], _wpi["distinct_worst_pairs"]),
          _wpi["all_pairs_equal"] and _wpi["worst_pair_is_degenerate"],
          "spread=%s" % [("%.1e" % x["pair_snr_spread"]) for x in _wpi["rows"]])

    # T7 🔴 方阻的作用域：电压驱动 P ∝ 1/R_sheet（跨度 == 方阻跨度）↔ 恒功率驱动
    #    V ∝ √R_sheet（跨度 == √5）而功耗绝对值；方阻上界反解回代 == V_max
    _hd = PSC.heater_drive_scope()
    _span = _hd["sheet_hi"] / _hd["sheet_lo"]
    _rsmax = PSC.rsheet_max_for_power_drive(_hd["v_drv"], _hd["p_req_w"], _hd["n_squares"])
    _back = math.sqrt(_hd["p_req_w"] * _rsmax * _hd["n_squares"])
    check("T7 方阻作用域：电压驱动功耗跨度 %.4f× == 方阻跨度 %.4f×（P∝1/R_sheet）↔ "
          "恒功率驱动电压跨度 %.4f× == √%.0f ∧ 功耗绝对值；R_sheet,max=%.1f Ω/sq 回代 V=%.12f"
          % (_hd["voltage_drive"]["p_span"], _span, _hd["power_drive"]["v_span"],
             _span, _rsmax, _back),
          abs(_hd["voltage_drive"]["p_span"] - _span) < 1e-12
          and abs(_hd["power_drive"]["v_span"] - math.sqrt(_span)) < 1e-12
          and abs(_back - _hd["v_drv"]) < 1e-12,
          "P_π=%.4f mW · R=%.1f…%.1f Ω" % (_hd["p_req_w"] * 1e3,
                                           _hd["r_lo_ohm"], _hd["r_hi_ohm"]))

    # T8 🔴 可判定的设计结论：现役 3.3 V **电压直驱**对 P_π 过驱 ≥5× 且跨 5×
    #    ⇒ 「3.3 V 直驱」不可用于写相变（必须限流/调占空比/闭环调功），这不是区间问题
    _od = _hd["voltage_drive"]["overdrive_vs_req"]
    check("T8 🔴 现役 3.3 V 电压直驱对 P_π(%.4f mW) 过驱 %.2f–%.2f× ⇒ 直驱不可用"
          "（须限流/占空比/闭环调功）" % (_hd["p_req_w"] * 1e3, _od[0], _od[1]),
          _od[0] >= 5.0 and abs(_od[1] / _od[0] - _span) < 1e-12)

    # T10 🔴 汇总表的**分档**必须与三节结论一致（防「表里写绝对、正文算出来是区间」）
    _ss = PSC.scope_summary()
    check("T10 作用域汇总自洽：硬上限 %.4f A/W ∧ η=[%.4f,%.4f] ∧ 真实链路只依赖 R·P=%s ∧ "
          "15 对同 SNR=%s ∧ 电压驱动功耗跨 %.3f× / 恒功率电压跨 %.4f× ∧ 绝对结论 %d 条"
          % (_ss["responsivity_hard_bound_a_per_w"], _ss["anchor_eta_lo"],
             _ss["anchor_eta_hi"], _ss["snr_depends_only_on_r_times_p"],
             _ss["all_pairs_snr_equal"], _ss["heater_power_span_voltage_drive"],
             _ss["heater_voltage_span_power_drive"], len(_ss["absolute_conclusions"])),
          _ss["snr_depends_only_on_r_times_p"] and _ss["all_pairs_snr_equal"]
          and _ss["worst_pair_is_degenerate"]
          and abs(_ss["heater_power_span_voltage_drive"] - _span) < 1e-12
          and abs(_ss["heater_voltage_span_power_drive"] - math.sqrt(_span)) < 1e-12
          and _ss["anchor_eta_lo"] > 0.5 and _ss["anchor_eta_hi"] <= 1.0
          and len(_ss["absolute_conclusions"]) >= 4
          and len(_ss["range_only_conclusions"]) >= 2,
          "absolute=%d range_only=%d" % (len(_ss["absolute_conclusions"]),
                                         len(_ss["range_only_conclusions"])))

    # T11 🔴 卡上 `R_h` 区间 ≡ 模块现算（v0.9.311 抓到的一处 18 版陈旧数）
    #   原卡写「183.6–917.9 Ω」= v0.9.200 重标定**之前**的几何（L=11.015 µm, n_sq=18.36）算的；
    #   现役 L=6.556 µm ⇒ n_sq=10.93 ⇒ 109.3–546.3 Ω。同一比例 1.679 = 11.015/6.556。
    #   本判据用**正则从卡里取数**再与现算逐位对拍 —— 与 H2 的「卡内披露 ≡ 模块现算」同一手法。
    _hr = M4.heater_resistance()
    _m4res = next(m["result"] for m in PC.MILESTONES if m["id"] == "M4")
    _mm = re.search(r"`R_h`\s*\**\s*([\d.]+)\s*[–\-]\s*([\d.]+)\s*Ω", _m4res)
    _card_lo, _card_hi = (float(_mm.group(1)), float(_mm.group(2))) if _mm else (-1.0, -1.0)
    check("T11 🔴 卡上 `R_h` 区间 %.1f–%.1f Ω ≡ 模块现算 %.1f–%.1f Ω（n_sq=%.4f；"
          "原卡 183.6–917.9 是 v0.9.200 重标定前几何）"
          % (_card_lo, _card_hi, _hr["r_lo_ohm"], _hr["r_hi_ohm"], _hr["n_squares"]),
          _mm is not None and abs(_card_lo - _hr["r_lo_ohm"]) < 0.05
          and abs(_card_hi - _hr["r_hi_ohm"]) < 0.05)

    # T9 反向探针：把反比律误写成 `P_min ∝ 1/R²` ⇒ T5 必红（证明 T5 不是恒真）
    _w = [r["product_r_p"] / r["r_a_per_w"] for r in _law["rows"]]
    _spread_wrong = max(_w) / min(_w) - 1.0
    check("T9 反向探针：误写 P_min ∝ 1/R² ⇒ 守恒量离散度 %.3f ≫ 1e-9 ⇒ T5 必红"
          % _spread_wrong, _spread_wrong > 1e-2)

    # ── U 卡片自检接线 + PM-G9 拆分的口径守卫（v0.9.311）──────────────────
    # 🔴 **为什么要有 U1**：`pm_case.run_selfchecks()` 此前**没有任何门禁调用**
    #    （`run_pchip_case_smoke` import 的是 `pchip_case`，不是 `pm_case`）⇒ 它的 ⑥
    #    写死 `gaps_total == 7` 而 GAPS 早已长到 8，**静默红了 18 版**。
    #    「护栏子集的补集是自由的」这条纪律的反面：**不在任何子集里的自检 = 没人跑的自检**。
    _pc_ok = PC.run_selfchecks(verbose=False)
    check("U1 🔴 `pm_case.run_selfchecks()` 全过（此前**无任何门禁调用** ⇒ ⑥ 的陈旧字面量 "
          "静默红了 18 版）", bool(_pc_ok))

    # U2 PM-G9 拆分如实：G9a 已闭合（带机读证据）+ G9b 边界声明，且**同号不同物不混**
    _g9a = next((g for g in PC.GAPS if g["id"] == "PM-G9a"), None)
    _g9b = next((g for g in PC.GAPS if g["id"] == "PM-G9b"), None)
    _g9old = [g for g in PC.GAPS if g["id"] == "PM-G9"]
    check("U2 🔴 PM-G9 拆成 G9a（已闭合，证据指名模块 `pm_peripheral_scope`）/ "
          "G9b（边界声明）∧ 旧 `PM-G9` 号**不再存在**（防同一号两个含义）",
          _g9a is not None and _g9b is not None and not _g9old
          and _g9a["status"].startswith("已闭合")
          and "pm_peripheral_scope" in _g9a["status"]
          and _g9b["status"].startswith("边界声明"),
          "G9a=%s G9b=%s 旧号=%d" % (
              (_g9a or {}).get("status", "")[:14], (_g9b or {}).get("status", "")[:14],
              len(_g9old)))

    # ── S1 自入 CI core ─────────────────────────────────────────────────
    cut = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(cut, encoding="utf-8").read() if os.path.exists(cut) else ""
    check("S1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_pm_m4_smoke.py" in ck)

    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
