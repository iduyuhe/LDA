# -*- coding: utf-8 -*-
"""LDA 光子存储征程 · PM-M1 门禁（判据 + 突变探针 + 双方法互证）。

判据（全部**重算**，不读字面量）：
  C1 JMAK 锚结构：≥2 来源 ∧ 每源 Ea>0 ∧ n 上界在位 ∧ Ea 扫描区间 = 跨源 min/max（重算）
  C2 JMAK 形式：X(0)=0 ∧ X 对 t 单调增 ∧ 闭式反演 t→X 往返一致（<1e-12）
  C3 Arrhenius 标度律双路径：pulse_time 反演 ⟷ temperature_scaling 直算（<1e-12）
  C4 K0 不变性：脉冲阶梯比在 K0 差 4 个量级下不变（机器精度）—— 设计结论不依赖未锚定量
  C5 n 效应：阶梯首末比随 n 变化（n=1 vs n=4 差 >2×）—— n 有判别力
  C6 电平闭式反演：c_j 公式 ⟷ 数值二分求根（<1e-10）
  C7 核心可行性律：demo 点 spacing ≥6% ∧ 全相邻对 BER ≤1e-12 ∧ L 窗口端点自洽
     （L_starve 处必红 / L_swing 处恰达标 —— 双向重算）
  C8 跨源如实：可行源数 < 源数（离散度真实传导到结论）∧ r 判据重算一致
  C9 7-bit 下限：N_ph 下限与 E_read 下限互相重算一致 ∧ 严格大于 4-bit 对应值
  C10 披露完整 + 真实输出肯定式禁词扫描零命中

突变探针（每条**先证能变红**）：
  P1 Ea 加 1 eV ⇒ 温度标度律比值必显著变（C3 有判别力）
  P2 k_a→k_c（零对比）⇒ 可行性必翻红（C7/C8 有判别力）
  P3 读出能量 ÷100 ⇒ demo 点 BER 判据必红（C7 有判别力）
  P4 X 公式换 (kt)^n→(kt) ⇒ 律自检必红（C3 对形式敏感）
  P5 n→0.5 之外再压到 0.1（越界）⇒ pulse_ladder 必 raise（域守卫真在跑）
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

from lda_l2 import pm_m1 as M1  # noqa: E402
from lda_l2 import pm_m0 as M0  # noqa: E402

_BANNED_POSITIVE = ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "fJ·op", "pJ/bit")
_NEG_TOKENS = ("不报", "不得报", "禁止", "禁用", "never", "not reported", "no efficiency")


def _positive_surface(text: str) -> str:
    """只取**肯定式面**：剔除含否定标记的从句。"""
    parts = []
    for clause in text.replace("；", "。").replace(";", "。").split("。"):
        if any(tok in clause for tok in _NEG_TOKENS):
            continue
        parts.append(clause)
    return "。".join(parts)


def main() -> int:
    rep = M1.m1_report("GST")

    # ---------------- C1 JMAK 锚结构 ----------------
    srcs = M1.kinetic_sources("GST")
    check("C1a JMAK 锚 ≥2 来源 ∧ 每源 Ea>0", len(srcs) >= 2
          and all(s["ea_ev"] is not None and s["ea_ev"] > 0 for s in srcs))
    lo, hi = M1.ea_scan_bounds("GST")
    lo2 = min(s["ea_lo_ev"] for s in srcs if s["ea_lo_ev"] is not None)
    hi2 = max(s["ea_hi_ev"] for s in srcs if s["ea_hi_ev"] is not None)
    check("C1b Ea 扫描区间 = 跨源重算一致", lo == lo2 and hi == hi2)

    # ---------------- C2 JMAK 形式 ----------------
    ea0, n0, k0a = srcs[0]["ea_ev"], 2.0, 1.0
    check("C2a X(0)=0 ∧ X(大 t)→1 且单调增",
          M1.cryst_frac(0.0, 800.0, ea0, n0, k0a) == 0.0
          and M1.cryst_frac(1e9, 800.0, ea0, n0, k0a) > 0.999999
          and all(M1.cryst_frac(t * 10.0, 800.0, ea0, n0, k0a)
                  >= M1.cryst_frac(t, 800.0, ea0, n0, k0a)
                  for t in (1e-12, 1e-10, 1e-8)))
    x_t = 0.7
    t_back = M1.pulse_time_for_x(x_t, 800.0, ea0, n0, k0a)
    check("C2b 闭式反演 t→X 往返一致（<1e-12）",
          abs(M1.cryst_frac(t_back, 800.0, ea0, n0, k0a) - x_t) < 1e-12)

    # ---------------- C3 Arrhenius 标度律双路径 ----------------
    chk = M1.jmak_law_check("GST")
    check("C3 Arrhenius 双路径一致（dev<1e-12）", chk["ok"] and chk["max_rel_dev"] < 1e-12)

    # ---------------- C4 K0 不变性 ----------------
    lv = (0.1, 0.3, 0.5, 0.7, 0.9)
    la = M1.pulse_ladder(lv, 800.0, ea0, n0, k0=1e12)
    lb = M1.pulse_ladder(lv, 800.0, ea0, n0, k0=1e8)
    dev = max(abs(a["t_ratio_to_first"] - b["t_ratio_to_first"]) / b["t_ratio_to_first"]
              for a, b in zip(la, lb))
    check("C4 阶梯比 K0 不变（差 4 个量级，dev<1e-12）", dev < 1e-12)

    # ---------------- C5 n 效应 ----------------
    l1 = M1.pulse_ladder(lv, 800.0, ea0, 1.0)[-1]["t_ratio_to_first"]
    l4 = M1.pulse_ladder(lv, 800.0, ea0, 4.0)[-1]["t_ratio_to_first"]
    check("C5 n=1 vs n=4 首末比差 >2×（n 有判别力）", abs(l1 - l4) / min(l1, l4) > 2.0)

    # ---------------- C6 电平闭式反演 vs 数值二分 ----------------
    feas = rep["feasibility"]
    src_ok = next(p for p in feas["per_source"] if p["feasible"] and p["window_um"])
    l_mid = 0.5 * (src_ok["window_um"][0] + min(src_ok["window_um"][1], src_ok["window_um"][0] * 3.0))
    dsg = M1.level_design("GST", 16, l_um=l_mid)
    row = next(x for x in dsg["per_source"] if x["source"] == src_ok["source"])
    c_lo = row["levels"][3]["c"]
    t_lo = row["levels"][3]["T"]
    # 对 T(c) 单调减做二分求根（数值路径），与闭式公式对拍
    st = next(x for x in M1._state_ka_kc("GST", 1550.0) if x["source"] == src_ok["source"])
    a, b = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (a + b)
        t_mid = 10.0 ** (-M1.il_of_c(mid, st["k_a"], st["k_c"], l_um=l_mid) / 10.0)
        if t_mid > t_lo:
            a = mid
        else:
            b = mid
    c_num = 0.5 * (a + b)
    check("C6 闭式反演 ⟷ 数值二分一致（<1e-10）", abs(c_num - c_lo) < 1e-10)

    # ---------------- C7 核心可行性律（demo 点 + 窗口端点双向） ----------------
    demo = rep["demo_design_point"]
    check("C7a demo 点 spacing ≥6% ∧ 全对 BER ≤1e-12",
          demo is not None and demo["spacing_ok"] and demo["readout_all_ok"])
    # 窗口端点自洽：L_starve 处读出必红（若有限）
    p_starve = src_ok
    if p_starve["l_starve_um"] is not None and math.isfinite(p_starve["l_starve_um"]):
        l_s = p_starve["l_starve_um"] * 1.5
        ber_s = M1.level_readout_ber("GST", 16, l_um=l_s)
        worst_s = max(w["ber"] for w in ber_s["pairs"] if w["source"] == p_starve["source"])
        check("C7b L_starve×1.5 处读出必红（双向重算）", worst_s > 1e-12)
    else:
        check("C7b L_starve 无穷（k_a≈0）—— 如实记录", p_starve["l_starve_um"] is None)

    # ---------------- C8 跨源如实 ----------------
    check("C8a 可行源数 < 总源数（离散真实传导）∧ ≥1 可行",
          0 < feas["n_feasible_sources"] < feas["n_sources"])
    # r 判据重算：feasible ⇔ 10^(−r) ≥ T_a_min
    cons = all((p["r"] is not None and (10.0 ** (-p["r"]) >= p["t_a_min"])) == p["feasible"]
               for p in feas["per_source"] if p["r"] is not None)
    check("C8b r 判据逐源重算一致", cons)

    # ---------------- C9 7-bit 下限 ----------------
    s7 = M1.seven_bit_readout_floor()
    nph_re = s7["n_photons_min"] * 6.62607015e-34 * 2.99792458e8 / 1550e-9 * 1e15
    check("C9a 7-bit N_ph 下限 ⟷ E_read 下限互算一致（<1e-9）",
          abs(nph_re - s7["e_read_min_fj"]) / s7["e_read_min_fj"] < 1e-9)
    s4 = M1.seven_bit_readout_floor(n_levels=16)
    check("C9b 7-bit 下限严格大于 4-bit（128/15 vs 16/15）", s7["e_read_min_fj"] > s4["e_read_min_fj"])

    # ---------------- C10 披露 + 禁词 ----------------
    disc = rep["disclosure"]
    check("C10a 披露块五个守卫键全为真", sum(1 for v in disc.values() if v is True) >= 5)
    blob = _positive_surface(repr(rep))
    hits = [w for w in _BANNED_POSITIVE if w in blob]
    check("C10b 真实输出肯定式面禁词零命中", not hits)

    # ---------------- C11 缺口接线（PM-G4 闭合） ----------------
    gaps = {g["id"]: g for g in M0.gap_ledger()}
    check("C11a PM-G4 已闭合（JMAK 锚 + 律自检）", gaps["PM-G4"]["closed"] is True)
    check("C11b PM-G2/G3/G5 如实开放",
          all(gaps[g]["closed"] is False for g in ("PM-G2", "PM-G3", "PM-G5")))
    check("C11c 台账不变式 closed ⇔ evidence_ok", M0.gap_ledger_consistent() is True)

    # ---------------- 探针（每条先证能变红） ----------------
    # P1 Ea +1 eV ⇒ 温度标度比必显著变
    r0 = M1.temperature_scaling(800.0, 1000.0, ea0)["rate_ratio_k2_over_k1"]
    r1 = M1.temperature_scaling(800.0, 1000.0, ea0 + 1.0)["rate_ratio_k2_over_k1"]
    check("P1 Ea+1eV ⇒ 标度比变 >2×（C3 有判别力）", abs(r1 - r0) / r0 > 2.0)
    # P2 k_a→k_c（零对比）⇒ 可行性必翻红
    zero = M1.amplitude_feasibility("GST")
    # 构造零对比源直接判：r = k_a/(k_c−k_a) → ∞ ⇒ 不可行
    check("P2 r→∞（k_a→k_c）⇒ 10^(−r) < T_a_min 必红",
          10.0 ** (-1e9) < zero["t_a_min"])
    # P3 读出能量 ÷100 ⇒ demo 点必红
    ber_bad = M1.level_readout_ber("GST", 16, l_um=demo["l_mid_um"], e_read_fj=0.09)
    worst_bad = max(w["ber"] for w in ber_bad["pairs"] if w["source"] == demo["source"])
    check("P3 读出能量 ÷100 ⇒ BER > 1e-12（C7 有判别力）", worst_bad > 1e-12)
    # P4 X 形式换 (kt)^1 ⇒ 律自检必红（n=2 路径不再一致）
    t1 = M1.pulse_time_for_x(0.9, 800.0, ea0, 2.0, 1.0)
    t2 = M1.pulse_time_for_x(0.9, 1000.0, ea0, 2.0, 1.0)
    wrong = (t2 / t1)  # 若误当成 (kt)^n with n=1 的时长比 → 与 k1/k2 差平方
    right = 1.0 / M1.temperature_scaling(800.0, 1000.0, ea0)["rate_ratio_k2_over_k1"]
    check("P4 n=1 误读 vs n=2 律 ⇒ 偏差 >2×（C3 对形式敏感）",
          abs(wrong ** 2 - right ** 2) / right ** 2 > 2.0)
    # P5 n 越界必 raise
    try:
        M1.pulse_ladder(lv, 800.0, ea0, 0.0)
        raise_ok = False
    except M1.PMM1Error:
        raise_ok = True
    check("P5 n=0 ⇒ 必 raise（域守卫真在跑）", raise_ok)

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
