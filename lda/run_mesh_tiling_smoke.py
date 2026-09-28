#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P6 · T6.3（U9）· 网格瓦片化（tiling）门禁 smoke —— 逐档重跑 D1/D2/P3 三预算。

判据分组（A–H）：
  A 契约与披露齐备 · 常数与既有示例脚本同源
  B 几何/寄生（真实构建 · 单模式）：保真度/DRC/LVS + **D1 路径独立复算 L_bus** + 结构不变量
  C 单布局模式强制（口径缺陷机器化：两模式差随档增长）
  D 逐档三预算（D1/D2/P3 闭式自洽 + P3 定天花板独立重算）
  E 🔴 无陈旧复用（档间常量指纹互异 + 固定 N 的每 N 损耗随档单调）
  F 口径澄清（如实登记「N 天花板几乎与档无关」，不假装随档更新）
  G 输入域（必 raise + 合法必过）
  H 结论钉死（场景序 + P1-B 安全区）

🔴 立场：本 smoke 断言的是**事实**，包括不利事实 —— F1 断言「N 天花板几乎与档无关」，
   而不是把它硬说成「随档更新」。真正随档变且单调的是每 N 损耗（E3）。
运行：python lda/run_mesh_tiling_smoke.py
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np  # noqa: E402

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2 import mesh_tiling as mt  # noqa: E402

# 🔴 调用签名：check(name, cond, detail="") —— 名字在前（P6·T6.1 血案）
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


def _d1_xmax_independent(N: int) -> float:
    """**D1 路径**独立复算 L_bus（与 `build_mesh_pnr` 不同源 ⇒ 真交叉核验）。

    复刻 `examples/budget_bus_loss_d1.py` 的几何式（参数与 D1 同值）。
    """
    from lda_layout.mesh_pnr import (_rect_column_assignment,
                                     clements_rect_decompose,
                                     coupler_length_from_theta)
    U = np.fft.fft(np.eye(N)).astype(complex) / math.sqrt(N)
    bs_list, _D = clements_rect_decompose(U)
    color = _rect_column_assignment(bs_list)
    c_max = max(color)
    lu_max = 0.0
    for (_j, theta, _phi) in bs_list:
        lu_max = max(lu_max, coupler_length_from_theta(2.0 * theta) + 2.0 * 6.0)
    col_pitch = lu_max + 8.0
    return 10.0 + (c_max + 1) * col_pitch + 6.0 + 18.0


def _deg_histogram_independent(N: int):
    """独立复算 deg 直方图（结构不变量 Σdeg = N(N−1) 的来源）。"""
    from lda_layout.mesh_pnr import clements_rect_decompose
    U = np.fft.fft(np.eye(N)).astype(complex) / math.sqrt(N)
    bs_list, _D = clements_rect_decompose(U)
    deg = [0] * N
    for (j, _t, _p) in bs_list:
        deg[j] += 1
        deg[j + 1] += 1
    return deg


def main() -> int:
    print("=" * 76)
    print("P6 · T6.3 网格瓦片化（tiling）· 逐档 D1/D2/P3 三预算")
    print("=" * 76)

    plan = mt.plan_tiling()
    tiers = {b["N_tile"]: b for b in plan["tiers"]}

    # ---------------------------------------------------------------- A 契约/披露
    print("--- A 契约与披露 ---")
    check("A1 披露键 %d 条且逐键非空（防删诚实声明）" % len(mt.TILING_DISCLOSURE),
          len(mt.TILING_DISCLOSURE) == 10
          and all(isinstance(v, str) and v.strip()
                  for v in mt.TILING_DISCLOSURE.values()),
          "keys=%s" % sorted(mt.TILING_DISCLOSURE.keys()))
    check("A2 plan 带完整 disclosure_keys（防删披露）",
          plan["disclosure_keys"] == sorted(mt.TILING_DISCLOSURE.keys()))
    check("A3 常数与既有示例脚本同源（D2 系数 0.14 · 阈值 30/20 · c0 表 · 场景表）",
          abs(mt.D2_FIDELITY_COEF - 0.14) < 1e-15
          and abs(mt.EQUALIZER_RANGE_DB - 30.0) < 1e-15
          and abs(mt.RECEIVER_MARGIN_DB - 20.0) < 1e-15
          and mt.SCENARIOS["A"] == (1.0, 0.020) and mt.SCENARIOS["C"] == (3.0, 0.100)
          and mt.ISO_CASES["deep_tr_air"] == 0.001
          and abs(mt.D2_WORST_MULT - 3.0) < 1e-15,
          "coef=%.2f eq=%.0f rx=%.0f" % (mt.D2_FIDELITY_COEF, mt.EQUALIZER_RANGE_DB,
                                         mt.RECEIVER_MARGIN_DB))
    check("A4 默认布局模式为 grid2d（单模式强制的前提）",
          mt.LAYOUT_MODE_DEFAULT == "grid2d" and plan["layout_mode"] == "grid2d")

    # ---------------------------------------------------------------- B 几何/寄生
    print("--- B 几何/寄生（真实构建 · D1 路径独立复算）---")
    ok_q = all(abs(tiers[N]["geometry"]["layout_fidelity"] - 1.0) < 1e-9
               and tiers[N]["geometry"]["drc_pass"] is True
               and tiers[N]["geometry"]["lvs_verdict"] == "ACCEPT"
               and tiers[N]["geometry"]["C_total_ff"] > 0
               for N in plan["tier_list"])
    check("B1 逐档 保真度=1.0 · DRC PASS · LVS ACCEPT · C_total>0",
          ok_q, "逐档=%s" % {N: (round(tiers[N]["geometry"]["layout_fidelity"], 12),
                              tiers[N]["geometry"]["drc_pass"],
                              tiers[N]["geometry"]["lvs_verdict"])
                          for N in plan["tier_list"]})
    # 🔴 判据用**相对**容差：两条路径是同一几何量的不同求和顺序 ⇒ 绝对差 ~1e-9 µm
    #    在 ~1000 µm 量级上是相对 1e-12（机器精度），绝对阈值会**假红**（U3 血训：
    #    判据阈值不得严于声明精度）。
    worst_rel = max(abs(tiers[N]["geometry"]["L_bus_um"] - _d1_xmax_independent(N))
                    / tiers[N]["geometry"]["L_bus_um"] for N in plan["tier_list"])
    check("B2 🔴 L_bus ≡ **D1 路径独立复算**（不同源：build_mesh_pnr vs clements/col_assignment）",
          worst_rel < 1e-9, "max 相对差=%.3e（绝对 ~1e-9 µm，属两条求和顺序的机器精度）"
          % worst_rel)
    check("B3 逐档 n_cols == N_tile（grid2d 结构不变量）",
          all(tiers[N]["geometry"]["n_cols"] == N for N in plan["tier_list"]),
          "逐档=%s" % {N: tiers[N]["geometry"]["n_cols"] for N in plan["tier_list"]})
    deg_ok, deg_detail = True, {}
    for N in plan["tier_list"]:
        deg = _deg_histogram_independent(N)
        avg = sum(deg) / N
        deg_detail[N] = (round(avg, 9), N - 1)
        deg_ok = deg_ok and abs(avg - (N - 1)) < 1e-12 and sum(deg) == N * (N - 1)
    check("B4 逐档 ⟨deg⟩ == N−1 且 Σdeg == N(N−1)（结构不变量，独立复算）",
          deg_ok, "逐档(avg, N−1)=%s" % deg_detail)
    lb = [tiers[N]["geometry"]["L_bus_um"] for N in plan["tier_list"]]
    pn = [tiers[N]["geometry"]["bus_len_per_n_um"] for N in plan["tier_list"]]
    check("B5 L_bus 随档**严格增**，而 µm/N 随档**严格减**（饱和趋势）",
          all(lb[i] < lb[i + 1] for i in range(len(lb) - 1))
          and all(pn[i] > pn[i + 1] for i in range(len(pn) - 1)),
          "L_bus=%s · µm/N=%s" % ([round(x, 3) for x in lb], [round(x, 4) for x in pn]))

    # ---------------------------------------------------------------- C 单模式强制
    print("--- C 单布局模式强制（口径缺陷机器化）---")
    check("C1 同档的 D1 几何与 GDS/寄生取自**同一** layout_mode",
          all(tiers[N]["d1"]["B"]["layout_mode"] == mt.LAYOUT_MODE_DEFAULT
              and tiers[N]["geometry"]["layout_mode"] == mt.LAYOUT_MODE_DEFAULT
              for N in plan["tier_list"]))
    gaps = {N: mt.layout_mode_gap(N) for N in plan["tier_list"]}
    ratios = [gaps[N]["xmax_ratio_s_over_g"] for N in plan["tier_list"]]
    check("C2 🔴 两模式口径差随档**增**（面积比 == x_max 比 ⇒ 同一几何）且 N=16 时 ≈7.0957×",
          all(ratios[i] < ratios[i + 1] for i in range(len(ratios) - 1))
          and all(abs(gaps[N]["area_ratio_s_over_g"]
                      - gaps[N]["xmax_ratio_s_over_g"]) < 1e-6
                  for N in plan["tier_list"])
          and abs(gaps[16]["xmax_ratio_s_over_g"] - 7.0957) < 5e-3,
          "x_max 比逐档=%s" % [round(x, 4) for x in ratios])
    check("C3 layout_mode 非法 ⇒ raise",
          _raises(lambda: mt.tile_geometry(8, layout_mode="bogus")))

    # ---------------------------------------------------------------- D 逐档三预算
    print("--- D 逐档三预算（D1/D2/P3 闭式自洽）---")
    d1_ok, d1_det = True, {}
    for N in plan["tier_list"]:
        d = tiers[N]["d1"]["B"]
        var = d["IL_full_db"] - d["IL_short_db"]
        # 🔴 独立重算：用报告的 L_bus/col_pitch/avg_deg + **模块常数**复算三项
        ap, at = mt.SCENARIOS["B"]
        mg = mt.RAIL_SWITCH_MARGIN
        want_mean = ap * (d["L_bus_um"] / 1e4) + d["avg_deg"] * at
        want_full = ap * (d["L_bus_um"] / 1e4) + (d["avg_deg"] * mg) * at
        want_short = ap * (d["col_pitch_um"] / 1e4) + 1.0 * at
        d1_det[N] = round(var, 9)
        d1_ok = d1_ok and abs(d["IL_var_db"] - var) < 1e-12 \
            and d["IL_full_db"] > d["IL_short_db"] > 0.0 \
            and abs(d["IL_mean_db"] - want_mean) < 1e-12 \
            and abs(d["IL_full_db"] - want_full) < 1e-12 \
            and abs(d["IL_short_db"] - want_short) < 1e-12
    check("D1 逐档 D1：三项 **独立重算**逐位一致（含轨切换余量常数）且 full > short > 0",
          d1_ok, "逐档 IL_var=%s" % d1_det)
    d2_ok, d2_det = True, {}
    for N in plan["tier_list"]:
        d = tiers[N]["d2"]
        d2_det[N] = round(d["sigma_budget_rad"], 9)
        d2_ok = d2_ok and abs(d["sigma_budget_rad"] - 0.14 / N) < 1e-15 \
            and abs(d["dphi_worst_rad"] - 3.0 * d["dphi_single_rad"]) < 1e-15
    check("D2 逐档 D2：sigma_budget ≡ 0.14/N 且 dphi_worst ≡ 3×dphi_single（逐位）",
          d2_ok, "逐档 budget=%s" % d2_det)
    flips = plan["d2_pass_worst_by_tier"]
    check("D3 🔴 D2 判定**档间翻转**（N=4 过、N≥8 不过）⇒ 三预算确需逐档重跑",
          flips.get(4) is True and flips.get(8) is False
          and flips.get(16) is False and flips.get(32) is False,
          "逐档 pass_worst=%s" % flips)
    p3_ok, p3_det = True, {}
    for N in plan["tier_list"]:
        p = tiers[N]["p3"]["B"]
        want_link = p["a_prop_db_cm"] * p["L_bus_um"] / 1e4
        p3_det[N] = round(p["IL_link_per_boundary_db"], 9)
        p3_ok = p3_ok and abs(p["IL_link_per_boundary_db"] - want_link) < 1e-12
    check("D4 逐档 P3：IL_link ≡ α_prop·（**该档自己的** L_bus）/1e4（非固定常数）",
          p3_ok, "逐档 IL_link/boundary=%s" % p3_det)
    mon_ok, mon_det = True, {}
    for N in plan["tier_list"]:
        rows = tiers[N]["p3_rows"]["B"]
        tot = [r["IL_total_db"] for r in rows]
        mon_det[N] = (round(tot[0], 6), round(tot[-1], 6))
        mon_ok = mon_ok and all(tot[i] < tot[i + 1] for i in range(len(tot) - 1)) \
            and all(abs(r["IL_total_db"] - (r["IL_bus_db"] + r["IL_link_db"]
                                            + r["IL_par_db"])) < 1e-12 for r in rows)
    check("D5 逐档 P3：IL_total 随 T **严格增** 且 ≡ bus+link+par（逐位）",
          mon_ok, "逐档(最小,最大)=%s" % mon_det)
    # 天花板独立重算（用该档自己的三常数）
    ceil_ok, ceil_det = True, {}
    for N in plan["tier_list"]:
        p = tiers[N]["p3"]["B"]
        rows = tiers[N]["p3_rows"]["B"]
        expect_rx = max((r["N"] for r in rows if r["IL_total_db"] <= 20.0), default=0)
        ceil_det[N] = (p["ceiling_rx_N"], expect_rx)
        ceil_ok = ceil_ok and p["ceiling_rx_N"] == expect_rx
    check("D6 天花板 ≡ 由**该档自己的**三常数独立重算（逐档逐位）",
          ceil_ok, "逐档(报告,复算)=%s" % ceil_det)
    par_ok, par_det = True, {}
    for N in plan["tier_list"]:
        p = tiers[N]["p3"]["B"]
        want = mt.C_SUB_LOSS_DB_PER_FF * tiers[N]["geometry"]["C_total_ff"]
        par_det[N] = (round(p["IL_par_per_tile_db"], 9), round(want, 9))
        par_ok = par_ok and abs(p["IL_par_per_tile_db"] - want) < 1e-12
    check("D7 逐档 IL_par/tile ≡ C_SUB_LOSS_DB_PER_FF × 该档 C_total_ff（独立重算）",
          par_ok, "逐档(报告,复算)=%s" % par_det)

    # ---------------------------------------------------------------- E 无陈旧复用
    print("--- E 无陈旧复用（U9 核心）---")
    check("E1 `assert_no_tier_reuse` 通过（逐档常量指纹两两互异，plan_tiling 内已调用）",
          plan.get("tier_reuse_guard") == "PASS（逐档常量指纹两两互异）")
    pnv = plan["bus_len_per_n_by_tier"]
    check("E2 逐档 µm/N 两两互异（=「旧档数字不得复用」的直接证据）",
          len(set(pnv)) == len(pnv), "逐档 µm/N=%s" % pnv)
    vals = plan["il_per_n_values"]
    check("E3 🔴 固定 N=%d 的每 N 损耗随档**严格单调递增**（真正随档变的量）"
          % plan["n_target_fixed"],
          plan["il_per_n_monotone_increasing"] and len(vals) == len(plan["tier_list"]),
          "逐档 dB/N=%s" % [round(v, 6) for v in vals])
    _fake = {"scenarios": ["B"], "tiers": [
        {"N_tile": 8, "d1": {"B": tiers[8]["d1"]["B"]},
         "p3": {"B": tiers[8]["p3"]["B"]}},
        {"N_tile": 16, "d1": {"B": tiers[8]["d1"]["B"]},
         "p3": {"B": tiers[8]["p3"]["B"]}},
    ]}
    check("E4 反向：人为让两档指纹逐位相同 ⇒ `assert_no_tier_reuse` **必 raise**",
          _raises(lambda: mt.assert_no_tier_reuse(_fake)))

    # ---------------------------------------------------------------- F 口径澄清
    print("--- F 口径澄清（如实登记不利事实）---")
    ceil_sets = {s: [tiers[N]["p3"][s]["ceiling_rx_N"] for N in plan["tier_list"]]
                 for s in plan["scenarios"]}
    check("F1 🔴 N 上的损耗天花板**几乎与档无关**（逐档 rx 天花板相同）⇒ 本模块**不宣称**"
          "「天花板随档更新」这一在 N 上不成立的说法",
          len(set(ceil_sets["B"])) == 1,
          "逐档 rx 天花板=%s（真正随档变的是每 N 损耗与 D2 翻转）" % ceil_sets)
    check("F2 与 F1 对照：D2 判定**是**档相关的（两件事不可混为一谈）",
          len(set(flips.values())) > 1,
          "逐档 D2 pass_worst=%s" % flips)

    # ---------------------------------------------------------------- G 输入域
    print("--- G 输入域（必 raise + 合法必过）---")
    check("G1 N_tile < 2 ⇒ raise", _raises(lambda: mt.tile_geometry(1)))
    check("G2 layout_mode 非法 ⇒ raise（已在 C3 覆盖，此处走 d1 路径）",
          _raises(lambda: mt.d1_bus_budget(8, layout_mode="bogus")))
    check("G3 scenario 非法 ⇒ raise", _raises(lambda: mt.d1_bus_budget(8, scenario="Z")))
    check("G4 iso_case 非法 ⇒ raise", _raises(lambda: mt.d2_thermal_budget(8, iso_case="x")))
    check("G5 t_table 含 T<1 ⇒ raise",
          _raises(lambda: mt.p3_tiling_ceiling(8, t_table=(0, 2))))
    check("G6 rail_pitch ≤ 0 ⇒ raise（D2）",
          _raises(lambda: mt.d2_thermal_budget(8, rail_pitch=0.0)))
    check("G7 合法必过：N_target 不可整除 ⇒ `reachable=False`（**不插值不外推**）",
          mt.il_per_n_at(16, 500)["reachable"] is False
          and mt.il_per_n_at(16, 512)["reachable"] is True)

    # ---------------------------------------------------------------- H 结论钉死
    print("--- H 结论钉死 ---")
    check("H1 逐档场景序 ceiling(A) ≥ ceiling(B) ≥ ceiling(C)（损耗越大天花板越低）",
          all(ceil_sets["A"][i] >= ceil_sets["B"][i] >= ceil_sets["C"][i]
              for i in range(len(plan["tier_list"]))))
    check("H2 场景 A 的 rx 天花板 ≥ 128（P1-B 安全区，与示例脚本同断言）",
          all(v >= 128 for v in ceil_sets["A"]), "逐档=%s" % ceil_sets["A"])

    total = PASS + FAIL
    print("-" * 76)
    print("mesh_tiling smoke：%d PASS / %d FAIL / 共 %d 项" % (PASS, FAIL, total))
    print("  逐档 N_tile/µm·N⁻¹/每N损耗(dB@512)/D2过：%s"
          % [(N, round(tiers[N]["geometry"]["bus_len_per_n_um"], 4),
              round(tiers[N]["il_per_n_at_fixed_N"]["IL_per_N_db"], 6),
              flips[N]) for N in plan["tier_list"]])
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
