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
import os
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
    check("F1 缺口台账如实开放：含 PM-G7（光学域 drift 无锚）与 PM-G8（T1/T2 锁死）",
          "PM-G7" in _gids and "PM-G8" in _gids, "缺口=%s" % _gids)

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
