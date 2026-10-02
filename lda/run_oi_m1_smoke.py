# -*- coding: utf-8 -*-
"""LDA 光联接模块征程 · M1（800G）门禁 —— 闭式 golden + 突变探针 + 还原重跑。

覆盖（C 系列 = 门禁本体；P 系列 = 突变探针，**先证能变红**）：
  C1  一阶低通：|H(f_3dB)| = 1/√2（3 个不同 f₃ · 同类成员 ≥2）
  C2  级联 EO S21：解回代 |H(f_3dB)| = 1/√2（≤1e-6）· 单极点退化 ≡ fᵢ
  C3  RC 带宽闭式 ≡ 1/(2πRC)（与 `compact_model.derive_responses` 同式）
  C4  色散：D=0 ⇒ σ₁≡σ₀（精确）· σ₁ 随 L 严格单调增
  C5  设计点色散代价（**逐点按声明期望** · 覆盖全部 SPEC_POINTS 成员）
  C6  PAM4 平坦：BER_closed ≈ BER_mc · 三眼等间距 ≈2
  C7  「所需 SNR」：仿真二分 ⟷ 闭式解析 一致（Δ < 0.3 dB）
  C8  驱动–TIA 协同：t90 闭式 ⟷ RK4（rel<1e-3）· 上升 <0.5 UI · TIA > Nyquist
  C9  梳齿规避信道规划：搜索解 ⟷ 设计常量 一致 · 规划 minXT≥15dB · M0 默认必红 · 旧规则会拒
  C10 集成：800G 聚合 · B19 无源无增益 · 闭式≡级联 ≤0.05dB · 8 通道隔离 ≥15dB · 无缺失模型
  C11 设计点结论：C_2km 过 KP4 门限 · C_10km 不可达 · O 波段近零色散
  C12 诚实护栏：能力宣称面无 TOPS/能效 · 披露键齐备
  C13 公开规格锚：KP4 pre-FEC 门限 ≡ IEEE 802.3bs/df Clause 91 的 2.4e-4
      （曾被误写 2.4e-2，差 100× ⇒ 会把「所需 SNR」低估 ~5dB；此判据 + P6 防复发）
  P1  抹平 EO S21（flatten）⇒ C-带宽（ISI 抽头）门禁必红
  P2  去色散（patch `OI_M1_PROCESS.d_ps_nm_km=0`）⇒ C5 必红
  P3  倍增接收噪声（patch `OI_M1_PROCESS.snr_db=10`）⇒ C-BER 必红
  P4  打乱 PAM4 电平间距（patch `_PAM4_LEVELS`）⇒ C-眼门禁必红
  P5  撤掉 CORE 登记 ⇒ `run_ci_coverage_gate_smoke._classify()` 必报缺口
  P6  把 KP4 规格常量改回错值 2.4e-2 ⇒ C13 规格锚必红
  R   探针还原后基线门禁**必须重新全绿**（探针不得污染真判据）

运行：python run_oi_m1_smoke.py（cwd=lda/）
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')

from lda_l2 import oi_m1 as M  # noqa: E402

_LEVELS_REF = M._PAM4_LEVELS
_KP4_REF = M.TARGET_BER_KP4            # 公开规格锚快照（IEEE 802.3bs/df Clause 91）
_BASE = dict(M.OI_M1_PROCESS)          # 探针还原对照（进程启动时的设计常数快照）


# ─────────────────────────────────────────────────────────────────────────────
# 门禁条件（供基线断言与突变探针**共用**；探针须能让它们变红）
# ─────────────────────────────────────────────────────────────────────────────
def _gate_bw(sim) -> bool:
    """带宽受限 ⇒ 符号间隔冲激响应必有 ISI 抽头（|taps[1]| ≥ 0.01）。"""
    return abs(sim["isi_taps"][1]) >= 0.01


def _gate_eye_flat(sim) -> bool:
    """平坦信道三眼等间距（眼高 ≈ 2，电平间距定义显式）。"""
    return all(abs(e["eye_height"] - 2.0) < 0.1 for e in sim["eyes"])


def _gate_ber(sim, thr: float = None) -> bool:
    """设计点链路预算级 BER 门槛：默认取 **公开规格 KP4 门限**（单一真源，
    防「两处各写一份门限」的静默分歧 —— U10 血案同族）。"""
    if thr is None:
        thr = M.TARGET_BER_KP4
    return sim["ber_closed"] < thr


def _gate_disp(pen_db: float) -> bool:
    """C-band 2 km 闭式色散代价应「可见但预算内」：0.1 < pen ≤ 1.5 dB。"""
    return 0.1 < pen_db <= 1.5


def _c_band_pen_db(reach_km: float = 2.0) -> float:
    """用 `OI_M1_PROCESS` 的**当前**值（探针会改它）算 C-band 闭式色散代价。"""
    p = M.OI_M1_PROCESS
    t_sym = 1.0 / (p["baud_gbd"] * 1e9)
    s0 = p["tx_sigma_frac"] * t_sym
    b2 = M.beta2_s2_per_m(p["d_ps_nm_km"], p["wl_nm"])
    return M.dispersion_penalty_db(s0, b2, reach_km * 1e3, p["baud_gbd"])


def _design_sim():
    """按 `OI_M1_PROCESS` 当前值跑一次 C-band 主设计点（探针会改它）。"""
    return M.pam4_link_sim(seed=0)


def _run_baseline_gates(label: str) -> None:
    """基线门禁子集（探针还原后须重新全绿 —— ⑥ 复原判据）。"""
    check(f"{label}: C-带宽 ISI 抽头非零（|taps[1]|≥0.01）", _gate_bw(_design_sim()))
    check(f"{label}: 设计点 BER < KP4 门限 {M.TARGET_BER_KP4:.1e}", _gate_ber(_design_sim()))
    check(f"{label}: C_2km 闭式色散代价 ∈ (0.1,1.5]dB", _gate_disp(_c_band_pen_db()))
    flat = M.pam4_link_sim(flatten_channel=True, no_dispersion=True)
    check(f"{label}: 平坦信道三眼等间距 ≈2", _gate_eye_flat(flat))


# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 74)
    print("光联接模块 M1（800G）门禁 — 闭式 golden + 突变探针 + 还原")
    print("=" * 74)

    # ── C1 一阶低通闭式 ──
    for f3 in (1e9, 30e9, 90.9e9):
        check(f"C1 一阶低通 |H(f_3dB)|=1/√2（f₃={f3/1e9:.1f}GHz）",
              abs(M.first_order_mag(f3, f3) - 1 / math.sqrt(2)) < 1e-12)

    # ── C2 级联 EO S21 解回代 + 单极点退化 ──
    fm, fp, ft = 55e9, 60e9, 90.9457e9
    f3 = M.eo_s21_f3db_hz(fm, fp, ft)
    check(f"C2 级联 EO S21 解回代 |H(f_3dB)|=1/√2（f₃={f3/1e9:.3f}GHz）",
          abs(abs(M.eo_s21_complex(f3, fm, fp, ft)) - 1 / math.sqrt(2)) < 1e-6)
    check("C2 级联 EO S21 单极点退化 (f_3dB≡fᵢ)",
          abs(M.eo_s21_f3db_hz(45e9, 1e18, 1e18) - 45e9) / 45e9 < 1e-3)

    # ── C3 RC 带宽闭式（与 compact_model 同式）──
    mw = M.modulator_bandwidth_hz()
    r = M.OI_M1_PROCESS["r_electrode_ohm"]
    c = (M.OI_M1_PROCESS["c_junction_fF"] + M.OI_M1_PROCESS["c_electrode_fF"]) * 1e-15
    check("C3 调制器 RC 带宽 ≡ 1/(2πRC)（与 compact_model 同式）",
          abs(mw["f_rc_hz"] - 1.0 / (2 * math.pi * r * c)) / mw["f_rc_hz"] < 1e-12)

    # ── C4 色散闭式 ──
    p = M.OI_M1_PROCESS
    s0 = p["tx_sigma_frac"] / (p["baud_gbd"] * 1e9)
    b2 = M.beta2_s2_per_m(p["d_ps_nm_km"], p["wl_nm"])
    check("C4 D=0 ⇒ σ₁≡σ₀（精确）",
          abs(M.dispersion_broadening_s(s0, 0.0, 2e3) - s0) < 1e-30)
    sig = [M.dispersion_broadening_s(s0, b2, L) for L in (1e3, 5e3, 2e4)]
    check("C4 σ₁ 随 L 严格单调增（3 点）",
          sig[0] < sig[1] < sig[2])

    # ── C5 + C11 逐设计点（覆盖全部 SPEC_POINTS 成员，按 expect 声明断言）──
    pts = M.m1_budget_all_points(seed=0)
    keys = [s["key"] for s in M.SPEC_POINTS]
    check("C5 设计点覆盖：SPEC_POINTS 全部成员均已评估",
          set(keys) <= set(pts.keys()) and len(pts) == len(M.SPEC_POINTS))
    for sp in M.SPEC_POINTS:
        k, exp = sp["key"], sp["expect"]
        pc = pts[k]["per_channel"][0]
        pen = pc["disp_penalty_db"]
        if exp == "pass":
            ok = (pts[k]["worst_ber_closed"] < M.TARGET_BER_KP4 and pen <= 1.5)
            det = (f"BER={pts[k]['worst_ber_closed']:.2e} < KP4 "
                   f"{M.TARGET_BER_KP4:.1e} · 闭式色散代价={pen:.2f}dB")
        elif exp == "disp_limited":
            ok = (pc["required_snr_reachable"] is False
                  and pts[k]["worst_ber_closed"] > M.TARGET_BER_KP4 and pen > 6.0)
            det = (f"所需SNR={'不可达' if not pc['required_snr_reachable'] else '可达'} · "
                   f"BER={pts[k]['worst_ber_closed']:.2e} > KP4 · 闭式代价={pen:.2f}dB")
        else:
            ok, det = False, f"未知 expect={exp!r}（新增设计点须显式声明期望）"
        check(f"C5 设计点 {k}（{sp['role']}·expect={exp}）", ok, det)
    # O 波段退化：D=0 ⇒ 闭式代价 ≡ 0（同类成员 ≥2）
    oks = [s for s in M.SPEC_POINTS if s["band"] == "O"]
    check(f"C11 O 波段闭式色散代价 ≡0（{len(oks)} 点）",
          len(oks) >= 2
          and all(abs(pts[s["key"]]["per_channel"][0]["disp_penalty_db"]) < 1e-9
                  for s in oks))
    check("C11 O 波段 10km 与 2km BER 同（零色散 ⇒ 无距离劣化）",
          abs(pts["O_10km"]["worst_ber_closed"]
              - pts["O_2km"]["worst_ber_closed"]) < 1e-9)

    # ── C6 PAM4 平坦 golden ──
    g = M.pam4_link_sim(flatten_channel=True, no_dispersion=True, snr_db=20.0,
                        n_sym=8192, seed=1)
    rel = abs(g["ber_closed"] - g["ber_mc"]) / max(g["ber_closed"], 1e-12)
    check(f"C6 平坦 BER_closed ≈ BER_mc（rel {rel:.2%} <25%）", rel < 0.25)
    check("C6 平坦信道三眼等间距 ≈2", _gate_eye_flat(g))

    # ── C7 所需 SNR：仿真 ⟷ 闭式 ──
    req = M.required_snr_db(M.TARGET_BER_KP4, flatten_channel=True,
                            no_dispersion=True, seed=1)
    ideal = M.ideal_required_snr_db(M.TARGET_BER_KP4)
    check(f"C7 所需SNR 仿真⟷闭式（Δ={abs(req['snr_db']-ideal):.3f}dB <0.3）",
          abs(req["snr_db"] - ideal) < 0.3)

    # ── C8 驱动–TIA 协同 ──
    dt = M.driver_tia_cosim()
    check("C8 驱动 t90 闭式⟷RK4（rel<1e-3）",
          dt["t90_abs_diff_s"] is not None
          and dt["t90_abs_diff_s"] / dt["t90_closed_form_s"] < 1e-3)
    check(f"C8 驱动上升 {dt['rise_10_90_ui']:.2f}UI <0.5", dt["rise_10_90_ui"] < 0.5)
    check(f"C8 TIA {dt['f_tia_ghz']:.1f}GHz > Nyquist", dt["tia_over_nyquist"] > 1.0)

    # ── C9 梳齿规避信道规划 ──
    plan = M.plan_lwdm_channels()
    bp = plan["best"] or {}
    check(f"C9 规划搜索解 ⟷ 设计常量（m={bp.get('m')}/{M.OI_M1_PROCESS['ring_m']}）",
          bp.get("m") == M.OI_M1_PROCESS["ring_m"]
          and abs(bp.get("gap_um", -1) - M.OI_M1_PROCESS["ring_gap_um"]) < 1e-9)
    check(f"C9 规划解 minXT={bp.get('min_xt_db')}dB ≥15 且 maxIL="
          f"{bp.get('max_il_drop_db')}dB ≤3",
          bp.get("min_xt_db", 0) >= 15.0 and bp.get("max_il_drop_db", 9) <= 3.0)
    check("C9 「FSR > 跨度」旧规则会拒该 31.5nm 跨度（平台旧判据过保守）",
          bool(plan["fsr_rule_rejects_span"]) and plan["n_solutions"] > 0)

    # ── C10 集成 ──
    link = M.build_transceiver_m1()
    rep = M.transceiver_m1_budget(link, M.m1_channels(8))
    check("C10 装配合法 IR.validate==[]", link.validate() == [])
    check("C10 800G 聚合 = 8×100G", rep["aggregate_gbps"] == 800.0)
    check("C10 B19 无源无增益 |T|≤1", rep["b19_passivity"])
    check("C10 无缺失器件模型",
          all(not pc["missing_models"] for pc in rep["m0"]["per_channel"]))
    check("C10 闭式≡级联 ≤0.05dB（装配接线正确）",
          all(pc["il_ab_diff_db"] <= 0.05 for pc in rep["m0"]["per_channel"]))
    check(f"C10 8 通道隔离 ≥15dB（实际 {rep['worst_isolation_db']:.1f}dB）",
          rep["worst_isolation_db"] >= 15.0)

    # ── C12 诚实护栏（能力宣称面不得含 TOPS/能效）──
    check("C12 能力宣称面无 TOPS/能效字样", M.honest_boundary_ok())
    need = {"ber_layer", "snr_is_input", "no_energy", "verdict", "params"}
    check("C12 披露键齐备（ber_layer/snr_is_input/no_energy/…）",
          need <= set(M.OI_M1_DISCLOSURE.keys()))
    check("C12 NON_CLAIMED 非空且含 BER 分层声明",
          len(M.NON_CLAIMED) >= 4
          and any("BER" in s and "预算级" in s for s in M.NON_CLAIMED))

    # ── C13 公开规格锚：KP4 门限口径（外部**标准**=限值 ⇒ 可用作锚，非 LDA 成就/非仿真值）──
    #   IEEE 802.3bs / 802.3df Clause 91：KP4 = RS(544,514) over GF(2^10)，t=15 符号纠错
    #   ⇒ 公开一致的 pre-FEC BER 门限 ≈ 2.4e-4（Keysight 应用笔记 / Vitex 800G 验收指南 /
    #   Heather Technologies IEEE 802.3 FEC 对照表，三源独立一致）。
    #   🔴 2026-10-02 修正：曾被误写 2.4e-2（差 100×）⇒ 「所需 SNR」被低估 ~5dB。
    check(f"C13 公开规格锚：KP4 pre-FEC 门限 {M.TARGET_BER_KP4:.2e} ∈ [2.0e-4, 2.8e-4]"
          f"（IEEE 802.3bs/df Clause 91 RS(544,514)）",
          2.0e-4 <= M.TARGET_BER_KP4 <= 2.8e-4)
    _snr_ideal = M.ideal_required_snr_db()
    _lo, _hi = M._KP4_REQUIRED_SNR_BAND_DB
    check(f"C13 PAM4 KP4 所需 SNR 落在合理性窗口（{_snr_ideal:.2f}dB ∈ "
          f"[{_lo},{_hi}]dB；工业共识 ~26dB，**非 golden**，仅防量级漂移）",
          _lo <= _snr_ideal <= _hi)

    # ── 探针前置：基线门禁必须全绿（否则探针「变红」无意义）──
    print("-" * 74)
    _run_baseline_gates("基线")

    # ═══ P1 抹平 EO S21（flatten）⇒ C-带宽必红 ═══
    flat = M.pam4_link_sim(flatten_channel=True, no_dispersion=True)
    check("P1 探针须造分歧（抹平 EO S21 → ISI 门禁变红）",
          _gate_bw(_design_sim()) and not _gate_bw(flat),
          f"受限 |taps1|={abs(_design_sim()['isi_taps'][1]):.4f} · "
          f"抹平 |taps1|={abs(flat['isi_taps'][1]):.6f}")

    # ═══ P2 去色散（patch 被消费的 `OI_M1_PROCESS.d_ps_nm_km`）═══
    _saved = M.OI_M1_PROCESS["d_ps_nm_km"]
    try:
        check("P2 前置：C-band 2km 闭式色散代价门禁原为绿", _gate_disp(_c_band_pen_db()))
        M.OI_M1_PROCESS["d_ps_nm_km"] = 0.0
        pen0 = _c_band_pen_db()
        check("P2 探针须造分歧（D=0 → 色散代价门禁变红）",
              not _gate_disp(pen0), f"D=0 ⇒ 代价={pen0:.4f}dB")
    finally:
        M.OI_M1_PROCESS["d_ps_nm_km"] = _saved

    # ═══ P3 倍增接收噪声（patch `OI_M1_PROCESS.snr_db`）═══
    _saved = M.OI_M1_PROCESS["snr_db"]
    try:
        check("P3 前置：设计点 BER 门禁原为绿", _gate_ber(_design_sim()))
        M.OI_M1_PROCESS["snr_db"] = 10.0
        sim_bad = _design_sim()
        check("P3 探针须造分歧（SNR 28→10dB → BER 门禁变红）",
              not _gate_ber(sim_bad),
              f"SNR=10dB ⇒ BER={sim_bad['ber_closed']:.3e}")
    finally:
        M.OI_M1_PROCESS["snr_db"] = _saved

    # ═══ P4 打乱 PAM4 电平间距（patch `_PAM4_LEVELS`）═══
    try:
        _flat0 = M.pam4_link_sim(flatten_channel=True, no_dispersion=True)
        check("P4 前置：平坦三眼等间距门禁原为绿", _gate_eye_flat(_flat0))
        M._PAM4_LEVELS = (-3.0, -0.5, 0.5, 3.0)
        _flat1 = M.pam4_link_sim(flatten_channel=True, no_dispersion=True)
        check("P4 探针须造分歧（电平间距被打乱 → 眼高门禁变红）",
              not _gate_eye_flat(_flat1),
              f"眼高={[round(e['eye_height'],3) for e in _flat1['eyes']]}")
    finally:
        M._PAM4_LEVELS = _LEVELS_REF

    # ═══ P5 撤掉 CORE 登记 ⇒ 覆盖门禁必报缺口 ═══
    import run_ci_coverage_gate_smoke as G  # noqa: E402
    import run_ci_regression as R           # noqa: E402
    _saved_core = R.CORE_SMOKES
    try:
        check("P5 前置：M0/M1 smoke 已在 CORE_SMOKES 内",
              "run_oi_m0_smoke.py" in R.CORE_SMOKES
              and "run_oi_m1_smoke.py" in R.CORE_SMOKES)
        R.CORE_SMOKES = [f for f in R.CORE_SMOKES
                         if f not in ("run_oi_m0_smoke.py", "run_oi_m1_smoke.py")]
        orphans, _, _ = G._classify()
        hit = ("run_oi_m0_smoke.py" in orphans) and ("run_oi_m1_smoke.py" in orphans)
        check("P5 探针须造分歧（撤登记 → 覆盖门禁报未登记）", hit,
              f"报未登记 {len(orphans)} 项")
    finally:
        R.CORE_SMOKES = _saved_core

    # ═══ P6 patch 公开规格常量（2.4e-4 → 曾误用的 2.4e-2）⇒ C13 规格锚必红 ═══
    try:
        check("P6 前置：KP4 公开规格锚原为绿",
              2.0e-4 <= M.TARGET_BER_KP4 <= 2.8e-4)
        M.TARGET_BER_KP4 = 2.4e-2
        _bad = M.TARGET_BER_KP4
        check("P6 探针须造分歧（KP4=2.4e-2 → C13 规格锚变红）",
              not (2.0e-4 <= _bad <= 2.8e-4), f"KP4={_bad:.1e}")
    finally:
        M.TARGET_BER_KP4 = _KP4_REF

    # ═══ ⑥ 还原重跑：探针不得污染真判据 ═══
    # ⑥a 反向测试：还原判据**本身**必须会红（否则它是假判据）
    _s_snr = M.OI_M1_PROCESS["snr_db"]
    try:
        M.OI_M1_PROCESS["snr_db"] = 7.0
        check("R-探针 还原判据须会红（污染 snr_db → 判据为假）",
              not (M.OI_M1_PROCESS["snr_db"] == _BASE["snr_db"]
                   and M.OI_M1_PROCESS["d_ps_nm_km"] == _BASE["d_ps_nm_km"]))
    finally:
        M.OI_M1_PROCESS["snr_db"] = _s_snr
    check("R 探针还原：_PAM4_LEVELS / OI_M1_PROCESS / KP4 规格锚 已复原",
          M._PAM4_LEVELS == _LEVELS_REF
          and M.TARGET_BER_KP4 == _KP4_REF
          and M.OI_M1_PROCESS["d_ps_nm_km"] == _BASE["d_ps_nm_km"]
          and M.OI_M1_PROCESS["snr_db"] == _BASE["snr_db"]
          and "run_oi_m0_smoke.py" in R.CORE_SMOKES
          and "run_oi_m1_smoke.py" in R.CORE_SMOKES)
    print("-" * 74)
    _run_baseline_gates("还原后")

    # ── 摘要 ──
    print("-" * 74)
    print(f"  8×C-band 2km: f_3dB(EO)={rep['per_channel'][0]['f_3db_eo_ghz']:.2f}GHz "
          f"worstQ={rep['worst_q']:.2f} worstBER={rep['worst_ber_closed']:.2e} "
          f"隔离≥{rep['worst_isolation_db']:.1f}dB 聚合={rep['aggregate_gbps']:.0f}Gb/s")
    print(f"  信道规划 (梳齿规避): m={bp.get('m')} R={bp.get('R_um')}µm gap="
          f"{bp.get('gap_um')}µm · minFSR={bp.get('min_fsr_nm')}nm · "
          f"min梳齿偏移={bp.get('min_comb_detune_nm')}nm · minXT={bp.get('min_xt_db')}dB")
    for sp in M.SPEC_POINTS:
        pc = pts[sp["key"]]["per_channel"][0]
        rs = pc["required_snr_db"]
        print(f"  {sp['key']:7s} λ={sp['wl_nm']:.0f}nm L={sp['reach_km']}km [{sp['expect']}]: "
              f"Q={pts[sp['key']]['worst_q']:.2f} "
              f"BER={pts[sp['key']]['worst_ber_closed']:.2e} "
              f"代价(闭式)={pc['disp_penalty_db']:.2f}dB "
              f"所需SNR={('不可达' if not pc['required_snr_reachable'] else f'{rs:.2f}dB')}")

    n_pass = globals().get("PASS", 0)
    n_fail = globals().get("FAIL", 0)
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {n_fail} FAIL / 共 {n_pass + n_fail} 项")
    return 0 if (n_pass and not n_fail) else 1


if __name__ == "__main__":
    raise SystemExit(main())
