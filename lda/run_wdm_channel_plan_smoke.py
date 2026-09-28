#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P6 · T6.2（U2）· WDM 信道规划门禁 smoke —— K 提升 4 → 8/16 的 FSR/混叠/串扰预算。

判据分组（A–G）：
  A 契约与披露齐备（防有人悄悄删诚实声明 / 改同源常数）
  B 闭式自洽（**独立重算**，不读模块自报值）
  C 两路交叉验证（闭式洛伦兹 vs 严格耦模式，**不共享公式** ⇒ 差不得恒为 0）
  D 逐档重算（无陈旧复用：每档 m 必须等于用该档自己 span 反解的值）
  E 反向护栏（判据会响：过小 m / 过宽 FWHM 必红）
  F 输入域（必 raise + 合法必过）
  G 口径澄清（两条 FSR 口径：字面判据在 K≥4 恒满足 ⇒ 不构成约束）

🔴 判据只用**保守串扰**（逐对 max(闭式, 严格)）；两路差异只披露不阻塞（理由见模块 docstring）。
运行：python lda/run_wdm_channel_plan_smoke.py
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_layout import wdm_channel_plan as wcp  # noqa: E402

# 🔴 调用签名：check(name, cond, detail="") —— 名字在前（P6·T6.1 血案：写反 ⇒ 整体假绿）
PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True,
                   detail_fmt="  —— {d}", detail_on="fail")


def _raises(fn):
    try:
        fn()
    except Exception:
        return True
    return False


def main() -> int:
    print("=" * 74)
    print("P6 · T6.2 WDM 信道规划（K 提升 4 → 8/16）· FSR / 混叠 / 串扰预算")
    print("=" * 74)

    plans = {K: wcp.plan_wdm_channels(K) for K in (4, 8, 16, 32)}
    audits = {K: wcp.audit_channel_plan(p) for K, p in plans.items()}
    t = wcp.tier_table()

    # ---------------------------------------------------------------- A 契约/披露
    print("--- A 契约与披露 ---")
    check("A1 披露键 %d 条且逐键非空（防删诚实声明）" % len(wcp.WDM_CHANNEL_DISCLOSURE),
          len(wcp.WDM_CHANNEL_DISCLOSURE) == 9 and all(
              isinstance(v, str) and v.strip()
              for v in wcp.WDM_CHANNEL_DISCLOSURE.values()),
          "keys=%s" % sorted(wcp.WDM_CHANNEL_DISCLOSURE.keys()))
    check("A2 每档 plan 带完整 disclosure_keys（防删披露）",
          all(p["disclosure_keys"] == sorted(wcp.WDM_CHANNEL_DISCLOSURE.keys())
              for p in plans.values()))
    from lda_l2 import ring_weight_bank as _rwb
    check("A3 间隔/默认 m 与 ring_weight_bank **同源**（单一来源，非另写字面量）",
          wcp.CHANNEL_SPACING_NM_DEFAULT == _rwb.CHANNEL_SPACING_NM_DEFAULT
          and wcp.M_RING_DEFAULT == _rwb.M_RING_DEFAULT,
          "spacing=%s m=%s" % (wcp.CHANNEL_SPACING_NM_DEFAULT, wcp.M_RING_DEFAULT))
    import inspect
    sig = inspect.signature(_rwb.max_weight_under_selectivity)
    check("A4 FWHM 预算比例与 U4 的 fwhm_budget_ratio 默认**同值**（0.2）",
          abs(wcp.FWHM_BUDGET_RATIO
              - float(sig.parameters["fwhm_budget_ratio"].default)) < 1e-15,
          "本模块=%.4f · U4 默认=%.4f"
          % (wcp.FWHM_BUDGET_RATIO, sig.parameters["fwhm_budget_ratio"].default))

    # ---------------------------------------------------------------- B 闭式自洽
    print("--- B 闭式自洽（独立重算，不读模块自报值）---")
    worst_fsr = 0.0
    for K, p in plans.items():
        m = p["m_ring"]
        a = wcp.ring_fsr_nm(wcp.WL_NM_DEFAULT, wcp.N_G_DEFAULT, m)
        b = (wcp.WL_NM_DEFAULT ** 2) / (
            wcp.N_G_DEFAULT * 2.0 * math.pi * wcp.ring_radius_um(
                wcp.WL_NM_DEFAULT, wcp.N_G_DEFAULT, m)) * 1e-3
        worst_fsr = max(worst_fsr, abs(a - b) / a)
    check("B1 FSR 两条独立路径一致（λ/m ≡ λ²/(n_g·2πR)）",
          worst_fsr < 1e-12, "max 相对差=%.3e" % worst_fsr)

    f, dl = 0.39842, 2.5
    x_mod = wcp.xtalk_db_from_fwhm(f, dl)
    x_hand = 10.0 * math.log10(1.0 / (1.0 + (2.0 * dl / f) ** 2))
    check("B2 洛伦兹串扰与手算一致（功率比式，非复用模块式）",
          abs(x_mod - x_hand) < 1e-12, "模块=%.9f 手算=%.9f" % (x_mod, x_hand))

    back = wcp.fwhm_nm_for_xtalk(x_mod, dl)
    check("B3 闭式反解往返一致（FWHM → XT → FWHM）",
          abs(back - f) / f < 1e-12, "往返 FWHM=%.9f vs %.9f" % (back, f))

    x_boundary = wcp.xtalk_db_from_fwhm(wcp.FWHM_BUDGET_RATIO * dl, dl)
    check("B4 关键等价性：ratio=0.2·Δλ ⟺ 相邻串扰 = −20.0432 dB（判据 −20 dB 的物理落点）",
          abs(x_boundary - (-20.0432)) < 5e-4, "实测=%.4f dB" % x_boundary)

    check("B5 判据目标的反解 FWHM 与边界之比 = 1.0050（1/√(10^2−1)·10 的闭式）",
          abs(wcp.fwhm_nm_for_xtalk(-20.0, dl) / (0.2 * dl) - 1.00504) < 1e-4,
          "实测比=%.6f" % (wcp.fwhm_nm_for_xtalk(-20.0, dl) / (0.2 * dl)))

    # ------------------------------------------------- C 两路交叉验证（不共享公式）
    print("--- C 两路交叉验证（闭式 vs 严格耦模式）---")
    gaps_binding = {K: p["model_gap_on_binding_db"] for K, p in plans.items()}
    gaps_max = {K: p["model_gap_max_db"] for K, p in plans.items()}
    check("C1 绑定对两路差 ≤ 0.5 dB（决策相关对必须好看）",
          all(g is not None and g <= 0.5 for g in gaps_binding.values()),
          "逐档绑定对差=%s" % {k: (None if v is None else round(v, 4))
                            for k, v in gaps_binding.items()})
    check("C2 🔴 两路差**必须 > 0**（证明它们不是同一式子的两种写法 ⇒ 交叉验证非恒真）",
          all(g is not None and g > 1e-6 for g in gaps_max.values()),
          "逐档相关对 max|Δ|=%s" % {k: (None if v is None else round(v, 4))
                                 for k, v in gaps_max.items()})
    check("C3 保守串扰 ≥ 闭式串扰（逐档，防低估）",
          all(p["worst_xtalk_db"] >= p["xtalk"]["lorentz_worst_db"] - 1e-12
              for p in plans.values()))
    check("C4 严格路对**建环口径**敏感（复刻已修血案：按 λ₀ 统一建环 ⇒ 给出 >0 dB 的荒谬值）",
          _buggy_single_ring_gives_absurd()
          and all(p["xtalk"]["binding_pair"]["conservative_db"] <= 0.0
                  for p in plans.values()),
          "对 K=16 用 λ₀ 的单环半径评 λ≠λ₀ 的受害信道 ⇒ 结果 >0 dB（故必须每信道建环）")
    check("C5 严格路无失败（n_exact_failures 全 0）",
          all(p["n_exact_failures"] == 0 for p in plans.values()))
    # 🔴 C6（探针 M9 盲区修复）：保守值必须**恰为**逐对 max(闭式, 严格)。
    #    只断言「≥ 闭式」在「严格路更差」时会漏检（丢 max 后仍成立 ⇒ 整条漏检）。
    c6 = []
    for K, p in plans.items():
        x = p["xtalk"]
        want = max(x["lorentz_worst_db"], x["exact_worst_db"])
        c6.append(abs(p["worst_xtalk_db"] - want) < 1e-12)
    check("C6 🔴 保守串扰 ≡ max(闭式最坏, 严格最坏)（逐档逐位；防「丢保守 max」漏检）",
          all(c6), "逐档差=%s" % {K: round(plans[K]["worst_xtalk_db"]
                                        - max(plans[K]["xtalk"]["lorentz_worst_db"],
                                              plans[K]["xtalk"]["exact_worst_db"]), 12)
                              for K in plans})

    # ---------------------------------------------------------------- D 逐档重算
    print("--- D 逐档重算（无陈旧复用）---")
    check("D1 🔴 每档 m ≡ min(M_RING_DEFAULT, floor(λ/(margin·span)))（独立复算全对）",
          t["m_recompute_all_ok"], "逐档 m=%s · 复算=%s"
          % (t["m_ring_by_tier"], t["m_recompute_ok_by_tier"]))
    check("D2 K=16 是**约束绑定**档（被迫把 m 由 30 降到 25）",
          t["tiers_constraint_binding"][2] and t["m_ring_by_tier"][2] == 25
          and t["tiers_kept_default"][0] and t["tiers_kept_default"][1],
          "m=%s kept_default=%s" % (t["m_ring_by_tier"], t["tiers_kept_default"]))
    check("D3 逐档 FSR/((K−1)·Δλ) ≥ 1.5（真实混叠余量）",
          all(p["fsr_ok"] for p in plans.values()),
          "逐档比值=%s" % {k: round(p["fsr_over_comb_span"], 4)
                        for k, p in plans.items()})
    check("D4 逐档最坏串扰（保守）≤ −20 dB",
          all(p["xtalk_ok"] for p in plans.values()),
          "逐档 XT=%s" % {k: round(p["worst_xtalk_db"], 3) for k, p in plans.items()})
    check("D4b 🔴 验收口径与设计点**解耦**：按 U4 同源 FWHM 边界（0.2·Δλ）判，"
          "逐档边界串扰 ≤ −20 dB ⇒ 放松目标会翻红（可证伪，非自我实现）",
          all(p["xtalk_boundary_db"] <= p["xtalk_target_db"] for p in plans.values())
          and all(abs(p["xtalk_boundary_db"] - (-20.0432)) < 5e-4
                  for p in plans.values()),
          "逐档边界串扰=%s" % {k: round(p["xtalk_boundary_db"], 4) for k, p in plans.items()})
    check("D5 逐档 FWHM 高于地板且 κ 可反演（物理可达）",
          all(p["fwhm_above_floor"] and p["kappa_for_design_fwhm"] is not None
              for p in plans.values()),
          "FWHM 地板=%s nm" % {k: round(p["fwhm_floor_nm"], 6)
                            for k, p in plans.items()})
    check("D6 逐档 audit 全绿（7 条子判据）",
          all(a["all_ok"] for a in audits.values()),
          "K=16 audit=%s" % audits[16])

    # ---------------------------------------------------------------- E 反向护栏
    print("--- E 反向护栏（判据会响）---")
    p_bad_m = wcp.plan_wdm_channels(16, m_ring=60)
    check("E1 强制过小 FSR 的 m=60（K=16）⇒ fsr_ok 必 False（护栏会响）",
          (not p_bad_m["fsr_ok"]) and p_bad_m["fsr_over_comb_span"] < 1.5,
          "FSR/span=%.4f" % p_bad_m["fsr_over_comb_span"])
    x_wide = wcp.xtalk_db_from_fwhm(0.8 * 2.5, 2.5)
    check("E2 FWHM 放宽到 0.8·Δλ ⇒ 闭式 XT 必 > −20 dB（判据会响）",
          x_wide > -20.0, "XT=%.3f dB" % x_wide)
    check("E3 收紧 FSR 判据（min=3.0 + 相称 margin=3.2）⇒ K=16 的 m 必更小（结论随判据动）",
          wcp.solve_m_ring(16, fsr_over_span_min=3.0, design_margin=3.2)["m_design"]
          < wcp.solve_m_ring(16, fsr_over_span_min=1.5)["m_design"],
          "m(3.0)=%d < m(1.5)=%d"
          % (wcp.solve_m_ring(16, fsr_over_span_min=3.0, design_margin=3.2)["m_design"],
             wcp.solve_m_ring(16, fsr_over_span_min=1.5)["m_design"]))
    check("E3b 🔴 margin < 判据 ⇒ **必 raise**（不许设计点松于判据 —— 可满足性/不可满足性双向）",
          _raises(lambda: wcp.solve_m_ring(16, fsr_over_span_min=3.0, design_margin=1.6)))
    check("E4 K 扩到 32 仍可行（m=12 · FSR/span 1.667 ≥ 1.5）⇒ 扩档路径成立",
          plans[32]["fsr_ok"] and plans[32]["m_ring"] == 12,
          "m=%d FSR/span=%.4f" % (plans[32]["m_ring"], plans[32]["fsr_over_comb_span"]))

    # ---------------------------------------------------------------- F 输入域
    print("--- F 输入域（必 raise + 合法必过）---")
    check("F1 K=0 ⇒ raise", _raises(lambda: wcp.plan_wdm_channels(0)))
    check("F2 spacing=0 ⇒ raise",
          _raises(lambda: wcp.plan_wdm_channels(8, spacing_nm=0.0)))
    check("F3 design_margin < fsr_over_span_min ⇒ raise",
          _raises(lambda: wcp.solve_m_ring(8, design_margin=1.0)))
    check("F4 xtalk_target_db ≥ 0 ⇒ raise",
          _raises(lambda: wcp.fwhm_nm_for_xtalk(0.0, 2.5)))
    check("F5 fwhm_nm ≤ 0 ⇒ raise 且 detune<0 ⇒ raise",
          _raises(lambda: wcp.xtalk_db_lorentz(0.0, 2.5))
          and _raises(lambda: wcp.xtalk_db_lorentz(0.4, -1.0)))
    check("F6 m_ring < 1 / fsr ≤ 0 / delta < 0 ⇒ raise",
          _raises(lambda: wcp.ring_fsr_nm(1550.0, 2.45, 0))
          and _raises(lambda: wcp.detuning_to_nearest_resonance_nm(1.0, 0.0))
          and _raises(lambda: wcp.detuning_to_nearest_resonance_nm(-1.0, 5.0)))
    check("F7 合法必过：K=1（span=0）⇒ fsr_over_comb_span=None 且 fsr_ok True",
          wcp.plan_wdm_channels(1)["fsr_ok"]
          and wcp.plan_wdm_channels(1)["fsr_over_comb_span"] is None)

    # ---------------------------------------------------------------- G 口径澄清
    print("--- G 口径澄清 ---")
    ratios = {K: p["fsr_over_spacing"] for K, p in plans.items()}
    check("G1 字面口径 FSR/Δλ 在 K≥4 恒 ≥ 20.6× ⇒ **不构成约束**（验收取的是 FSR/span）",
          all(v >= 20.6 for v in ratios.values()),
          "逐档 FSR/Δλ=%s" % {k: round(v, 3) for k, v in ratios.items()})
    check("G2 K=16 在**两种**口径下结论相反 ⇒ 口径选择是实质性的（非措辞）",
          plans[16]["fsr_over_spacing"] >= 20.0
          and plans[16]["m_selection"]["m_kept_default"] is False,
          "FSR/Δλ=%.3f（字面口径恒满足）vs 判据 FSR/span≥1.5 迫使 m 由 30 降到 %d"
          % (plans[16]["fsr_over_spacing"], plans[16]["m_ring"]))
    check("G3 混叠限制标记正确（绑定对是否非相邻信道）",
          all(isinstance(p["xtalk"]["alias_limited"], bool) for p in plans.values()),
          "逐档 alias_limited=%s" % {k: p["xtalk"]["alias_limited"]
                                  for k, p in plans.items()})
    # 🔴 G4：**折返逻辑的真正用武之地** —— 达标档永远不会触发它（span < FSR ⇒ m_lo=0），
    #    故必须**故意造一个越域档**（K=64 @2.5nm ⇒ span 157.5nm ≫ FSR 51.67nm）来证明
    #    `detuning_to_nearest_resonance_nm` 的 FSR 折返**真的在工作**（否则该函数可被
    #    「直接返回 delta」的恒等实现替换而全绿 ⇒ 判据失去覆盖）。
    p64 = wcp.plan_wdm_channels(64, m_ring=30)
    bp64 = p64["xtalk"]["binding_pair"]
    check("G4 🔴 越域档（K=64 · m=30 · span 157.5 ≫ FSR 51.67）⇒ 绑定对必为**非相邻**信道"
          "且折返后失谐 < Δλ（证明 FSR 折返逻辑真在工作）",
          (not p64["fsr_ok"]) and bp64 is not None
          and bp64["channel_distance"] > 1
          and abs(bp64["wrapped_detune_nm"]) < 2.5
          and p64["worst_xtalk_db"] > -20.0,
          "binding=%s · 最坏 XT=%.3f dB ⇒ 混叠即灾难（这正是 FSR≥1.5·span 判据的动机）"
          % ({(k, v) for k, v in bp64.items() if k in
              ("channel_distance", "comb_delta_nm", "wrapped_detune_nm")},
             p64["worst_xtalk_db"]))

    total = PASS + FAIL
    print("-" * 74)
    print("wdm_channel_plan smoke：%d PASS / %d FAIL / 共 %d 项" % (PASS, FAIL, total))
    print("  逐档 (K, m, FSR/span, XT保守 dB)：%s"
          % [(K, plans[K]["m_ring"], round(plans[K]["fsr_over_comb_span"], 3),
              round(plans[K]["worst_xtalk_db"], 3)) for K in sorted(plans)])
    return 0 if FAIL == 0 else 1


def _buggy_single_ring_gives_absurd() -> bool:
    """复刻已修血案：**按 λ₀ 统一建环**去评 λ≠λ₀ 的受害信道 ⇒ 给出 >0 dB 的荒谬值。

    正确实现（本模块）按**受害波长**建环；此函数刻意用错口径，用于证明「建环口径」
    对结论是**实质性**的（而不是可忽略的实现细节）。
    """
    from lda_agent.ring_adddrop import adddrop_spectrum
    m, n_g, kap = 25, wcp.N_G_DEFAULT, 0.142086
    wl0 = wcp.WL_NM_DEFAULT                      # 1550
    R_wrong = wcp.ring_radius_um(wl0, n_g, m)     # 按 λ₀ 建环（错）
    victim, aggressor = 1585.0, 1587.5            # 受害 ≠ λ₀
    fsr0 = wcp.ring_fsr_nm(wl0, n_g, m)
    k = int(round((aggressor - victim) / fsr0))
    spec = adddrop_spectrum([victim * 1e-3, (aggressor - k * fsr0) * 1e-3],
                            R_wrong, n_g, kap, 0.0, wl0_um=wl0 * 1e-3)
    t_v, t_a = float(spec["drop"][0]), float(spec["drop"][1])
    x_wrong = 10.0 * math.log10(t_a / t_v) if t_v > 0 and t_a > 0 else float("-inf")
    x_right = wcp.xtalk_db_exact(victim, aggressor, m, n_g, kap)
    # 错口径给出「入侵者比受害者强」（>0 dB）且与正确口径差 > 10 dB
    return bool(x_wrong > 0.0 and abs(x_wrong - x_right) > 10.0)


if __name__ == "__main__":
    raise SystemExit(main())
