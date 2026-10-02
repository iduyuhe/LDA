# -*- coding: utf-8 -*-
"""LDA 光联接模块征程 · M2（1.6T · 200G/lane · LPO 形态）门禁。

覆盖（C 系列 = 门禁本体；A 系列 = **外部标准规格锚**；P 系列 = 突变探针，**先证能变红**）：
  A1  200G/lane 符号率 106.25 GBd ∈ 公开窗口 [106.0, 106.5]
  A2  RS-only（KP4 单级）pre-FEC 2.4e-4 ∈ [2.0e-4, 2.8e-4]
  A3  级联 FEC（802.3dj）pre-FEC 4.8e-3 ∈ [4.5e-3, 5.2e-3]
  A4  LPO 内码增益 2.744 dB ∈ [2.4, 3.1] **且** ≡ 闭式 Q 差（同源自洽）
  A5  1.6T 聚合 ≡ 8×200G
  C6  形态 → FEC 模式映射（LPO 拿不到模块内码 ⇒ 只能 RS-only）
  C7  带宽：200G 档 EO f_3dB ≥ Nyquist；**legacy 档（M1 常量）必不足**（带宽墙真存在）
  C8  设计点结论 ≡ 声明式期望（逐点覆盖全部 SPEC_POINTS_M2 成员）
  C9  受限**分因**正确（色散受限 ≠ 带宽受限：关掉色散重算独立判定）
  C10 主设计点：LPO 可达且裕量 < retimed 裕量（LPO 真收紧）
  C11 接收噪声上界 > 设计假设（⇒ 噪声非瓶颈）· 且 ⟷ 独立手算闭式一致
  C12 驱动–TIA（200G 档）：t90 闭式 ⟷ RK4（rel<1e-3）· 上升 <0.5UI · TIA > Nyquist
  C13 波长栅 O-band + 环规划（梳齿规避）有解且 best 隔离 ≥ 15 dB
      + **C13c 搜索解 ⟷ 设计常量互锁**（防常量漂移；血案：`ring_m` 曾抄成 M1 的 C-band 解 129）
  C14 诚实护栏：能力宣称面无 TOPS/能效字样 · 披露键齐备
  C15 集成：G-OI2 builder 与 D4 交付域 `oi_transceiver` 接线在位（真 GDS 可出）
      + **C15c 跨模块互锁**：**版图 builder 的环解 ⟷ 链路预算的规划解**（防版图/预算静默脱钩）
  P1  抹掉 LPO 收紧（`mode_for_form_factor` 对 lpo 也返回级联）⇒ C6/C8 必红
  P2  把 M2 的调制器带宽换成 M1（100G）档常量 ⇒ C7「200G 够用」必红
  P3  把 M1 档常量的带宽抬高到 200G 档 ⇒ C7「带宽墙存在」必红
  P4  `_limiting_factor` 恒返回 bw_limited（丢掉「关色散重算」）⇒ C8/C9 必红
  P5  把级联 FEC 门限改回 2.4e-4（抹掉级联优势）⇒ A3 规格锚必红
  P6  把 200G/lane 符号率改成 53.125（当成 100G/lane 用）⇒ A1 规格锚必红
  P7  TIA 反馈电阻改成 1 Ω（噪声爆炸）⇒ C11「噪声非瓶颈」必红
  P8  `ring_m` 抄成 M1 的 C-band 解 129（**血案原值**）⇒ C13c 互锁必红
  P9  版图 builder `RX_RING_M` 退回 129 ⇒ C15c 跨模块互锁必红
  R   探针还原后基线门禁**必须重新全绿**（探针不得污染真判据）

运行：python run_oi_m2_smoke.py（cwd=lda/）
"""
from __future__ import annotations

import math
import os
import sys
import unittest.mock as mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')

from lda_l2 import oi_m1 as M1  # noqa: E402
from lda_l2 import oi_m2 as M   # noqa: E402

_BASE_PROC = dict(M.OI_M2_PROCESS)        # 探针还原对照快照（进程启动时的设计常数）
_BASE_LEGACY = dict(M.OI_M2_LEGACY_PROCESS)
_BASE_FEC = {k: dict(v) for k, v in M.FEC_MODE_PROFILES.items()}


def _restore() -> None:
    """把被探针改过的设计常数**逐字还原**（防探针污染真判据）。"""
    M.OI_M2_PROCESS.clear()
    M.OI_M2_PROCESS.update(_BASE_PROC)
    M.OI_M2_LEGACY_PROCESS.clear()
    M.OI_M2_LEGACY_PROCESS.update(_BASE_LEGACY)
    M.FEC_MODE_PROFILES.clear()
    M.FEC_MODE_PROFILES.update({k: dict(v) for k, v in _BASE_FEC.items()})


def _q_ber(snr_db: float) -> float:
    """闭式 Q 函数 BER（与平台同源口径）：BER = 0.375·erfc(Q/√2)，Q = 10^(SNR/20)。"""
    q = 10.0 ** (snr_db / 20.0)
    return 0.375 * math.erfc(q / math.sqrt(2.0))


def _baseline_checks(pts=None, pts_tag: str = "", light: bool = False):
    """基线判据（**同一份**供「首次运行」与「探针还原后重跑」共用）。

    `light=True` 时跳过重活（环规划搜索 / 真版图构建）——探针只需证明目标判据
    能变红，不必重跑全量（探针 5 次 × 全量 ≈ 数十秒纯浪费）。
    """
    out = []
    pts = M.m2_budget_all_points() if pts is None else pts
    tag = f"{pts_tag} " if pts_tag else ""

    # ── A 系列：外部标准规格锚（窗口判据；同源相等**不足**以守）────────────
    lo, hi = M._BAUD_ANCHOR_BAND_GBD
    out.append((f"{tag}A1 符号率 {M.PAM4_BAUD_200G_GBD} GBd ∈ [{lo},{hi}]（802.3dj 200G/lane）",
                lo <= M.PAM4_BAUD_200G_GBD <= hi))
    _id_of = {"rs_only": "A2", "concatenated": "A3"}
    for mode in ("rs_only", "concatenated"):
        a, b = M._FEC_BER_ANCHOR_BAND[mode]
        v = M.fec_pre_fec_ber(mode)
        out.append((f"{tag}{_id_of[mode]} {mode} pre-FEC {v:.2e} ∈ [{a:.1e},{b:.1e}]",
                    a <= v <= b))
    gain = M.lpo_inner_code_gain_db()
    g_lo, g_hi = M._LPO_INNER_GAIN_BAND_DB
    out.append((f"{tag}A4 LPO 内码增益 {gain:.3f} dB ∈ [{g_lo},{g_hi}]",
                g_lo <= gain <= g_hi))
    # A4 同源自洽（**必要但非充分**：单独用是假判据，必须与上面的窗口判据同时在场）
    q_gain = (M.required_snr_ideal_db("rs_only")
              - M.required_snr_ideal_db("concatenated"))
    out.append((f"{tag}A4 LPO 内码增益 ≡ 闭式 SNR(RS-only)−SNR(级联)（Δ<1e-12）",
                abs(gain - q_gain) < 1e-12))
    # A4 反向：内码增益必须与「两模式门限比」可解释（防两个错值互相抵消）
    ratio = M.fec_pre_fec_ber("concatenated") / M.fec_pre_fec_ber("rs_only")
    out.append((f"{tag}A4 级联/RS-only 门限比 {ratio:.2f}× ∈ [15,25]（20× 放宽 ⇒ ~2.7dB）",
                15.0 <= ratio <= 25.0))
    out.append((f"{tag}A5 聚合净速率 {M.aggregate_gbps():.0f} Gb/s == "
                f"{M.OI_M2_PROCESS['n_lanes']}×{M.NET_PER_LANE_GBPS:.0f}G",
                abs(M.aggregate_gbps()
                    - M.OI_M2_PROCESS["n_lanes"] * M.NET_PER_LANE_GBPS) < 1e-9
                and abs(M.aggregate_gbps() - 1600.0) < 1e-9))

    # ── C6：形态 → FEC 模式（LPO 拿不到模块内码）──────────────────────────
    out.append((f"{tag}C6 LPO ⇒ RS-only（needs_module_dsp=False）；retimed ⇒ 级联",
                M.mode_for_form_factor("lpo") == "rs_only"
                and M.mode_for_form_factor("retimed") == "concatenated"
                and M.FEC_MODE_PROFILES["rs_only"]["needs_module_dsp"] is False
                and M.FEC_MODE_PROFILES["concatenated"]["needs_module_dsp"] is True))

    # ── C7：带宽墙（吃狗粮核心）──────────────────────────────────────────
    hr_fast = M.bandwidth_headroom_ghz("fast")
    hr_legacy = M.bandwidth_headroom_ghz("legacy")
    out.append((f"{tag}C7a 200G 档 EO f_3dB {M.eo_f3db_ghz('fast'):.2f} GHz ≥ "
                f"Nyquist {M.NYQUIST_200G_GHZ:.3f}（余量 {hr_fast:+.2f}）", hr_fast > 0.0))
    out.append((f"{tag}C7b 吃狗粮：M1 档 EO f_3dB {M.eo_f3db_ghz('legacy'):.2f} GHz < "
                f"Nyquist（缺 {-hr_legacy:.2f} GHz ⇒ 带宽墙真存在）", hr_legacy < 0.0))

    # ── C8：设计点结论 ≡ 声明式期望 ──────────────────────────────────────
    for sp in M.SPEC_POINTS_M2:
        k = sp["key"]
        got = pts[k]["verdict_point"]
        out.append((f"{tag}C8 设计点 {k}: verdict {got} ≡ 声明 {sp['expect']}",
                    got == sp["expect"]))

    # ── C9：受限**分因**（色散受限 ≠ 带宽受限）──────────────────────────
    out.append((f"{tag}C9a C_2km 成因 {pts['C_2km']['limiting_cause']} ≡ disp_limited"
                f"（关掉色散后可达={pts['C_2km']['required_snr_nodisp_reachable']}）",
                pts["C_2km"]["limiting_cause"] == "disp_limited"
                and pts["C_2km"]["required_snr_nodisp_reachable"] is True))
    out.append((f"{tag}C9b O_2km_legacy 成因 {pts['O_2km_legacy']['limiting_cause']} "
                f"≡ bw_limited（关掉色散仍不可达）",
                pts["O_2km_legacy"]["limiting_cause"] == "bw_limited"
                and pts["O_2km_legacy"]["required_snr_nodisp_reachable"] is False))
    out.append((f"{tag}C9c 两成因**不同源**（0 色散下 C_2km 可达而 legacy 不可达）",
                pts["C_2km"]["required_snr_nodisp_reachable"]
                != pts["O_2km_legacy"]["required_snr_nodisp_reachable"]))

    # ── C10：主设计点 LPO 真收紧 ────────────────────────────────────────
    o2 = pts["O_2km"]
    rm = o2["retimed"]["margin_db"]
    lm = o2["lpo"]["margin_db"]
    pen = o2["lpo_penalty_db"]

    def _rs(v):
        return "不可达" if v is None else f"{v:+.2f}dB"

    out.append((f"{tag}C10a O_2km：retimed 可达（裕量 {_rs(rm)}）且 LPO 可达（裕量 {_rs(lm)}）",
                o2["retimed"]["required_snr_reachable"]
                and o2["lpo"]["required_snr_reachable"]))
    out.append((f"{tag}C10b O_2km：LPO 裕量 < retimed 裕量（{_rs(lm)} < {_rs(rm)}）",
                rm is not None and lm is not None and lm < rm))
    # C10c：LPO 代价 = 裕量缩水。**不**与「理想内码增益」严格相等——代价含 ISI 项
    # （RS-only 门限更紧，所需 SNR 更高 ⇒ 同一 ISI 的绝对影响不同）⇒ 只判
    # 「代价 > 0」+「与内码增益同量级」。严格恒等式由 C10d 守。
    out.append((f"{tag}C10c O_2km：LPO 代价 {'—' if pen is None else format(pen, '.3f')} dB "
                f"> 0 且 |代价 − 理想内码增益 {gain:.3f}| < 1.5 dB（ISI 口径差）",
                pen is not None and pen > 0.0 and abs(pen - gain) < 1.5))
    # C10d：三者口径**恒等式**（严格）：lpo_penalty ≡ 内码增益 + (ISI_LPO − ISI_retimed)。
    #   守的是「代价/增益/ISI 三处不各写一份」——任一处口径漂移即红。
    if rm is not None and lm is not None and pen is not None:
        isi_l = o2["lpo"]["isi_penalty_db"]
        isi_r = o2["retimed"]["isi_penalty_db"]
        _c10d = (isi_l is not None and isi_r is not None
                 and abs(pen - (gain + (isi_l - isi_r))) < 1e-9)
        _c10d_txt = (f"ISI(LPO)={isi_l:.4f} ISI(retimed)={isi_r:.4f}"
                     if _c10d else f"分解={pen} gain={gain}")
    else:
        _c10d, _c10d_txt = False, "存在不可达形态 ⇒ 恒等式无定义"
    out.append((f"{tag}C10d O_2km：LPO 代价 ≡ 内码增益 + (ISI_LPO − ISI_retimed)"
                f"（恒等式 Δ<1e-9 · {_c10d_txt}）", _c10d))

    # ── C11：接收噪声预算（噪声非瓶颈 + 独立手算一致）────────────────────
    nz = M.tia_noise_snr_db()
    out.append((f"{tag}C11a 噪声上界 {nz['snr_db']:.2f} dB > 设计假设 "
                f"{M.OI_M2_PROCESS['snr_db']:.1f} dB（⇒ 带宽/ISI 才是瓶颈）",
                nz["snr_db"] > M.OI_M2_PROCESS["snr_db"]))
    # 独立手算（不复用被测函数的任何中间量：从物理常数重算一遍）
    qe, kb, tk = 1.602176634e-19, 1.380649e-23, 300.0
    rf = M.OI_M2_PROCESS["r_f_ohm"]
    i_pp = 0.8 * (10.0 ** (-6.0 / 10.0)) * 1e-3
    i_avg = 0.5 * i_pp
    i_n = math.sqrt(4.0 * kb * tk / rf + 2.0 * qe * i_avg)
    bw = M.eo_f3db_ghz("fast") * 1e9
    snr_manual = 20.0 * math.log10(i_pp / (i_n * math.sqrt(bw)))
    out.append((f"{tag}C11b 噪声上界手算复现 {snr_manual:.3f} dB ≡ 平台 {nz['snr_db']:.3f} dB",
                abs(snr_manual - nz["snr_db"]) < 1e-9))

    # ── C12：驱动–TIA 协同（200G 档）────────────────────────────────────
    dt = M.driver_tia_200g()
    rel = (dt["t90_abs_diff_s"] / dt["t90_closed_form_s"]
           if dt["t90_abs_diff_s"] is not None else float("inf"))
    out.append((f"{tag}C12a 驱动 t90 闭式 ⟷ RK4（rel {rel:.2e} < 1e-3）", rel < 1e-3))
    out.append((f"{tag}C12b 驱动上升 {dt['rise_10_90_ui']:.3f} UI < 0.5 且 TIA "
                f"{dt['tia_over_nyquist']:.2f}×Nyquist",
                dt["driver_fast_enough"] and dt["tia_wide_enough"]))

    # ── C13：波长栅 / 环规划 ────────────────────────────────────────────
    ch = M.m2_channels()
    out.append((f"{tag}C13a M2 波长栅 O-band 起 {ch[0]:.1f}nm · {len(ch)} 通道 · "
                f"间距 {ch[1] - ch[0]:.1f}nm",
                abs(ch[0] - M.OI_M2_PROCESS["wl0_nm"]) < 1e-9
                and len(ch) == M.OI_M2_PROCESS["n_lanes"]))
    if not light:
        plan = M.plan_m2_rings()
        bp = plan["best"] or {}
        out.append((f"{tag}C13b 环规划（梳齿规避）{plan['n_solutions']} 解 · best m="
                    f"{bp.get('m')} minXT={bp.get('min_xt_db')}dB ≥ 15",
                    plan["n_solutions"] > 0 and float(bp.get("min_xt_db", 0.0)) >= 15.0))
        # C13c 🔴 同源互锁：搜索解 ⟷ 设计常量（M1 有同款判据 #9，M2 原缺 ⇒ v0.9.179 补）
        #  血案：`OI_M2_PROCESS["ring_m"]` 曾抄成 M1 的 C-band 解 129（注释却称「M2 波段搜索给出」），
        #  而 M2 O-band 搜索给 268 ⇒ 版图与预算不同参而**一切判据全绿**抓不到。
        out.append((f"{tag}C13c 搜索解 ⟷ 设计常量互锁（best m={bp.get('m')}/gap={bp.get('gap_um')} ⟷ "
                    f"常量 m={M.OI_M2_PROCESS['ring_m']}/gap={M.OI_M2_PROCESS['ring_gap_um']}）",
                    bool(bp) and int(bp.get("m")) == int(M.OI_M2_PROCESS["ring_m"])
                    and abs(float(bp.get("gap_um", -1.0))
                            - float(M.OI_M2_PROCESS["ring_gap_um"])) < 1e-9))
        # C15c 🔴 跨模块互锁：**版图 builder 的环解** ⟷ 链路预算的规划解
        #  （否则「签核的环」≠「预算的环」—— 版图与预算静默脱钩）
        from lda_layout import oi_transceiver_pnr as _TXm
        out.append((f"{tag}C15c 版图环解 ⟷ 预算规划解互锁（builder RX_RING_M={_TXm.RX_RING_M} "
                    f"≡ best m={bp.get('m')}）",
                    bool(bp) and int(_TXm.RX_RING_M) == int(bp.get("m"))))

    # ── C14：诚实护栏 ───────────────────────────────────────────────────
    need_keys = {"level", "not_redline", "form_lpo", "ber_layer", "snr_is_input",
                 "spec_anchor", "no_energy", "verdict", "params"}
    out.append((f"{tag}C14a 能力宣称面无 TOPS/能效字样", M.honest_boundary_ok()))
    out.append((f"{tag}C14b 披露键齐备（缺={sorted(need_keys - set(M.OI_M2_DISCLOSURE))}）",
                need_keys <= set(M.OI_M2_DISCLOSURE)))

    # ── C15：G-OI2 builder 与 D4 域接线在位 ──────────────────────────────
    if not light:
        from lda_layout.oi_transceiver_pnr import build_oi_transceiver_pnr
        from lda_l2 import d4_domains as dm
        bl = build_oi_transceiver_pnr(n_lanes=M.OI_M2_PROCESS["n_lanes"])
        out.append((f"{tag}C15a G-OI2 builder 出真 GDS（{bl['gds_elements']} 元素 · "
                    f"DRC={'PASS' if bl['drc_pass'] else 'FAIL'} · LVS={bl['lvs_verdict']}）",
                    len(bl["gds_bytes"]) > 0 and bl["drc_pass"]
                    and bl["lvs_verdict"] == "ACCEPT"))
        out.append((f"{tag}C15b D4 交付域 oi_transceiver 注册在位（{len(dm.D4_DOMAINS)} 域）",
                    "oi_transceiver" in dm.D4_DOMAINS
                    and "oi_transceiver" in dm.DOMAIN_PARAM_LIMITS
                    and "oi_transceiver" in dm.DOMAIN_LABELS))
    return out


def main() -> int:
    print("=" * 74)
    print("LDA 光联接模块征程 · M2（1.6T · 200G/lane · LPO）门禁")
    print("=" * 74)

    pts = M.m2_budget_all_points()
    print("── 基线判据 ──")
    for name, ok in _baseline_checks(pts):
        check(name, ok)

    # ── 摘要 ──────────────────────────────────────────────────────────
    print("-" * 74)
    print(f"  1.6T: {M.OI_M2_PROCESS['n_lanes']}×{M.NET_PER_LANE_GBPS:.0f}G = "
          f"{M.aggregate_gbps():.0f} Gb/s · baud {M.PAM4_BAUD_200G_GBD} GBd · "
          f"Nyquist {M.NYQUIST_200G_GHZ:.3f} GHz · "
          f"EO f_3dB {M.eo_f3db_ghz('fast'):.2f} GHz（余量 "
          f"{M.bandwidth_headroom_ghz('fast'):+.2f}）")
    print(f"  LPO 代价(FEC) = {M.lpo_inner_code_gain_db():.3f} dB · "
          f"接收噪声上界 {M.tia_noise_snr_db()['snr_db']:.2f} dB vs 设计假设 "
          f"{M.OI_M2_PROCESS['snr_db']:.1f} dB")
    for sp in M.SPEC_POINTS_M2:
        pt = pts[sp["key"]]
        rm = pt["retimed"]["margin_db"]
        lm = pt["lpo"]["margin_db"]
        r_txt = "不可达" if rm is None else f"{rm:+.2f}dB"
        l_txt = "不可达" if lm is None else f"{lm:+.2f}dB"
        print(f"  {sp['key']:13s} [{pt['verdict_point']:12s}] EO={pt['eo_f3db_ghz']:.2f}GHz "
              f"retimed={r_txt} LPO={l_txt}")

    # ── 突变探针（每个都必须让上面的判据变红）──────────────────────────
    print("-" * 74)
    print("── 突变探针（先证能变红）──")

    def _red(checks, needle: str) -> bool:
        """给定「判据名 → bool」表，返回含 needle 的项是否**变红**。"""
        hits = [(n, ok) for (n, ok) in checks if needle in n]
        return bool(hits) and any(not ok for _, ok in hits)

    # P1：抹掉 LPO 收紧
    with mock.patch.object(M, "mode_for_form_factor",
                           lambda form: "concatenated"):
        p1 = _baseline_checks(M.m2_budget_all_points())
    check("🔴 P1 探针: 抹掉 LPO 收紧（lpo 也拿级联）⇒ C6 必红", _red(p1, "C6 "))
    check("🔴 P1 探针: 同上一并让 C10b「LPO 裕量 < retimed 裕量」必红", _red(p1, "C10b"))
    _restore()

    # P2：M2 档带宽退回 M1（100G）常量
    M.OI_M2_PROCESS["f_mod_ghz"] = M.OI_M2_LEGACY_PROCESS["f_mod_ghz"]
    M.OI_M2_PROCESS["f_pd_ghz"] = M.OI_M2_LEGACY_PROCESS["f_pd_ghz"]
    M.OI_M2_PROCESS["f_tia_ghz"] = M.OI_M2_LEGACY_PROCESS["f_tia_ghz"]
    p2 = _baseline_checks(light=True)
    check("🔴 P2 探针: M2 带宽退回 M1 档 ⇒ C7a「200G 够用」必红", _red(p2, "C7a"))
    _restore()

    # P3：把 M1 档常量抬高到 200G 档 ⇒ 带宽墙消失
    M.OI_M2_LEGACY_PROCESS["f_mod_ghz"] = M.OI_M2_PROCESS["f_mod_ghz"]
    M.OI_M2_LEGACY_PROCESS["f_pd_ghz"] = M.OI_M2_PROCESS["f_pd_ghz"]
    M.OI_M2_LEGACY_PROCESS["f_tia_ghz"] = M.OI_M2_PROCESS["f_tia_ghz"]
    p3 = _baseline_checks(light=True)
    check("🔴 P3 探针: M1 档带宽抬到 200G 档 ⇒ C7b「带宽墙存在」必红", _red(p3, "C7b"))
    _restore()

    # P4：_limiting_factor 丢掉「关色散重算」⇒ 色散受限被误归因成带宽受限
    with mock.patch.object(M, "_limiting_factor",
                           lambda spec, mode="concatenated": {
                               "cause": "bw_limited",
                               "required_snr_nodisp_reachable": False,
                               "ber_at_snr_hi_nodisp": None}):
        p4 = _baseline_checks(M.m2_budget_all_points())
    check("🔴 P4 探针: 分因丢掉「关色散重算」⇒ C9a 必红", _red(p4, "C9a"))
    check("🔴 P4 探针: 同上一并让 C8 设计点结论必红", _red(p4, "C8 "))
    _restore()

    # P5：级联 FEC 门限改回 2.4e-4（抹掉级联优势）
    M.FEC_MODE_PROFILES["concatenated"]["pre_fec_ber"] = 2.4e-4
    p5 = _baseline_checks(light=True)
    check("🔴 P5 探针: 级联门限改回 2.4e-4 ⇒ A3 规格锚必红", _red(p5, "A3"))
    _restore()

    # P6：符号率当成 100G/lane 用（53.125 GBd）
    _baud_save = M.PAM4_BAUD_200G_GBD
    M.PAM4_BAUD_200G_GBD = 53.125
    p6 = _baseline_checks(light=True)
    check("🔴 P6 探针: 符号率改成 53.125 ⇒ A1 规格锚必红", _red(p6, "A1"))
    M.PAM4_BAUD_200G_GBD = _baud_save

    # P7：TIA 反馈电阻 1 Ω ⇒ 噪声爆炸
    M.OI_M2_PROCESS["r_f_ohm"] = 1.0
    p7 = _baseline_checks(light=True)
    check("🔴 P7 探针: TIA R_f=1Ω ⇒ C11a「噪声非瓶颈」必红", _red(p7, "C11a"))
    _restore()

    # P8：环区数常量漂移（抄成 M1 的 C-band 解）⇒ C13c「搜索解 ⟷ 常量」互锁必红
    #     （这是 v0.9.179 修复的那条血案原值，探针即复现血案现场）
    M.OI_M2_PROCESS["ring_m"] = 129
    p8 = _baseline_checks()
    check("🔴 P8 探针: ring_m 抄成 M1 的 129 ⇒ C13c 互锁必红", _red(p8, "C13c"))
    _restore()

    # P9：版图 builder 环解漂移 ⇒ C15c「版图环解 ⟷ 预算规划解」跨模块互锁必红
    from lda_layout import oi_transceiver_pnr as _TX
    _rxm_save = _TX.RX_RING_M
    _TX.RX_RING_M = 129
    p9 = _baseline_checks()
    check("🔴 P9 探针: builder RX_RING_M 退回 129 ⇒ C15c 跨模块互锁必红", _red(p9, "C15c"))
    _TX.RX_RING_M = _rxm_save

    # ── R：还原后基线必须重新全绿 ───────────────────────────────────────
    print("-" * 74)
    print("── 还原后基线复查（探针不得污染真判据）──")
    for name, ok in _baseline_checks(M.m2_budget_all_points(), pts_tag="R"):
        check(name, ok)

    n_pass = globals().get("PASS", 0)
    n_fail = globals().get("FAIL", 0)
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {n_fail} FAIL / 共 {n_pass + n_fail} 项")
    return 0 if (n_pass and not n_fail) else 1


if __name__ == "__main__":
    raise SystemExit(main())
