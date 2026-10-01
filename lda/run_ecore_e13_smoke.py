#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电子计算征程 E13 门禁 · 2D MOS 漂移扩散输运（I–V / 亚阈值摆幅）。

═══ 判什么（分节）═══
A 内核自检（mos_2d_transport **6/6**）·
B 关键判据（**G1–G6**，全部 name-first 断言）：
  G1 **SS ≥ 60 mV/dec 热极限**（物理定律锚 · 不等式）·
  G2 长沟道 SS ⟷ **教科书闭式** `(kT/q)ln10·(1+Cd/Cox)`（含体效应 · rel < 10%）·
  G3 栅长趋势（L↓ ⇒ SS↑ · 与 E12 的 roll-off 同向）·
  G4 电流守恒（源≡漏 · **带绝对下限**）·
  G5 输出特性单调（V_d↑ ⇒ I_d↑ 并趋饱和）·
  G6 V_th 双法交叉（恒流法 ⟷ E12 表面势法 · 同量级）·
C 反向可证伪（**5 条突变探针**：伪造 SS=6 ⇒ G1 必红 / 伪造 SS=200 ⇒ G2 必红 /
  破坏源端电流 ⇒ G4 必红 / **污染接触载流子 BC（假注入）⇒ 内核自检③ 必红** /
  栅长趋势反向 ⇒ G3 必红）+ 还原完整性 ·
D 零重计算/惰性导入（ecore 包在**无 scipy** 环境仍可 import）·
K 自入 CI core（防静默漏接 · 血案 28）。

🔴 本门禁的核心价值：**把「不产 I-V」这条登记了整整一段（E12 · G-K）的缺口真正关掉**，
并且关得**可证伪** —— SS 的物理下限（不等式）与教科书闭式（等式）**双锚**，
外加与 E12 静电结果的**独立交叉**（roll-off 方向 / V_th 双法）。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

VG_N = 13
LS_FOR_TREND = (1000.0, 250.0, 100.0)


def main() -> int:
    import numpy as np
    import unittest.mock as mock
    from lda_solver import mos_2d_transport as MT
    from lda_l2.ecore import device_transport as DT

    # ══════════════════════ A 内核自检 ══════════════════════
    ok_a = MT.run_selfchecks(verbose=False)
    check("A1 内核自检 mos_2d_transport 6/6（Si 掩码/接触只含 n⁺/平衡零电流/"
          "收敛+守恒/教科书闭式/V_d 单调）", ok_a)

    # ══════════════════════ B 关键判据 G1–G6 ══════════════════════
    vg = DT.default_vg_list(n=VG_N)
    curves = {}
    for L in LS_FOR_TREND:
        curves[L] = DT.transfer_curve(L, vg_list=vg)
    c100, c250, c1000 = curves[100.0], curves[250.0], curves[1000.0]

    # B1 转移特性自身健全（含负 V_g ⇒ 一定覆盖深亚阈值）
    check("B1 转移特性健全：含负 V_g 的点 · 全点收敛 · 电流跨 >4 个数量级",
          min(p["Vg"] for p in c100["points"]) < 0.0
          and c100["all_converged"]
          and (max(abs(p["I_d"]) for p in c100["points"])
               / max(min(abs(p["I_d"]) for p in c100["points"]), 1e-30)) > 1e4,
          "Vg∈[%.2f, %.2f] · %d/%d 收敛 · I 跨度 %.1e"
          % (min(p["Vg"] for p in c100["points"]),
             max(p["Vg"] for p in c100["points"]),
             c100["n_converged"], c100["n_points"],
             max(abs(p["I_d"]) for p in c100["points"])
             / max(min(abs(p["I_d"]) for p in c100["points"]), 1e-30)))

    # B2 🔴 G1：SS ≥ 热极限（物理定律锚 · 不等式）
    g1 = DT.ss_thermal_limit_report(curve=c100)
    check("B2 🔴 G1 **SS ≥ 60 mV/dec 热极限**（物理定律锚 · 数值解不得突破）",
          (not g1["violates_thermal_limit"]) and g1["SS_mv_dec"] > g1["thermal_limit_mv_dec"],
          "SS=%.2f ≥ 极限 %.2f mV/dec（SS@100nm）"
          % (g1["SS_mv_dec"], g1["thermal_limit_mv_dec"]))

    # B3 🔴 G2：长沟道 ⟷ 教科书闭式（含体效应）
    g2 = DT.cross_check_ss_closed_form(curve=c1000)
    check("B3 🔴 G2 长沟道 SS ⟷ **教科书闭式** (kT/q)ln10·(1+Cd/Cox)（rel < 10%）",
          g2["passes"],
          "2D=%.2f ⟷ 闭式=%.2f mV/dec（rel=%.2f%% · Cd/Cox=%.4f · 理想极限 %.2f）"
          % (g2["SS_2d_mv_dec"], g2["SS_closed_mv_dec"], g2["rel_err"] * 100,
             g2["Cd_over_Cox"], g2["SS_ideal_mv_dec"]))

    # B4 G3：栅长趋势（短沟道退化 · 与 E12 roll-off 同向）
    g3 = DT.ss_vs_length_report(curves=curves)
    ss_by_l = {p["Lg_nm"]: p["SS_mv_dec"] for p in g3["points"]}
    check("B4 G3 栅长趋势：L↓ ⇒ SS↑（短沟道静电控制退化 · 与 E12 roll-off/DIBL 同向）",
          g3["monotone_long_to_short"]
          and ss_by_l[65.0] > ss_by_l[100.0] > ss_by_l[250.0] > ss_by_l[1000.0],
          "65→%.0f · 100→%.1f · 250→%.1f · 1000→%.1f mV/dec（闭式平台 %.1f）"
          % (ss_by_l[65.0], ss_by_l[100.0], ss_by_l[250.0], ss_by_l[1000.0],
             g3["SS_closed_platform_mv_dec"]))

    # B5 G4：电流守恒（带绝对下限 —— 相对判据在分母趋零时失效）
    g4 = DT.current_conservation_report(c100)
    check("B5 G4 电流守恒 源≡漏（|I_d| ≥ 1e-3 A/m 的点 rel < 1e-3）",
          g4["passes"],
          "%d/%d 点 · worst=%.2e @Vg=%.2f" % (g4["n_checked"], g4["n_total"],
                                              g4["worst_rel"], g4["worst_Vg"]))

    # B6 G5：输出特性单调
    g5 = DT.id_vd_report(lg_nm=300.0)
    check("B6 G5 输出特性 I_d 随 V_d 单调增（低 V_d → 高 V_d 趋饱和）",
          g5["monotone"],
          " · ".join("Vd=%.2f→%.3e" % (p["V_d"], p["I_d_a_per_m"]) for p in g5["points"]))

    # B7 G6：V_th 双法交叉（恒流法 ⟷ E12 表面势法）
    g6 = DT.vth_cc_vs_surface_potential(curve=c100)
    check("B7 G6 V_th 双法同量级（E13 恒流法 ⟷ E12 表面势法 · 两法均 is_oracle=False）",
          g6["passes"],
          "CC=%.4f ⟷ ψ_s=%.4f V（差 %.1f mV · %.1f%%）"
          % (g6["V_th_cc_v"], g6["V_th_surface_potential_v"], g6["abs_diff_mv"],
             g6["rel_err"] * 100))

    # B8 能力闭合表（E12 的「不产 I-V」已被 E13 闭合）
    cap = DT.transport_capability_closure()
    check("B8 能力闭合表：闭合 4 项 · 仍不可用 4 项（含 T2 永久锁 + DD 框架边界）",
          len(cap["closed_by_e13"]) == 4 and len(cap["still_not_available"]) == 4
          and any("I–V" in c["item"] for c in cap["closed_by_e13"])
          and any("T2" in c["why"] for c in cap["still_not_available"]))

    # B9 披露：显式声明 DD 框架边界 + 迁移率常数 + 不报 TOPS
    hb = DT.DEVICE_TRANSPORT_DISCLOSURE["honest_boundary"]
    check("B9 🔴 披露显式声明「漂移扩散框架 ⇒ 不含量子修正/隧穿」+「迁移率常数 ⇒ I_on 不可当性能」+ 不报 TOPS",
          "漂移扩散" in hb and "迁移率" in hb and "TOPS" in hb and "I_on" in hb)

    # ══════════════════════ C 反向可证伪（突变探针）═══════════════════════
    # C1 伪造 SS = 6 mV/dec（低于热极限）⇒ G1 必红
    fake_fast = dict(c100, SS_mv_dec=6.0)
    ok_c1 = DT.ss_thermal_limit_report(curve=fake_fast)["violates_thermal_limit"]
    check("C1 反向：伪造 SS=6 mV/dec（突破热极限）⇒ G1 判定必红"
          "（**物理定律锚不可被数值解突破**）", ok_c1 is True)

    # C2 伪造 SS = 200（远离闭式）⇒ G2 必红
    fake_slow = dict(c1000, SS_mv_dec=200.0)
    ok_c2 = DT.cross_check_ss_closed_form(curve=fake_slow)["passes"]
    check("C2 反向：伪造 SS=200 mV/dec ⇒ G2 与教科书闭式对照必红", ok_c2 is False)

    # C3 🔴 真破坏：让源端 SG 电流偏移（非守恒截面）⇒ G4 必红
    real_tc = MT.terminal_current

    def bad_tc(flag, psi, carrier_si, mask, dev, side="drain"):
        v = real_tc(flag, psi, carrier_si, mask, dev, side=side)
        return v * 2.0 if side == "source" else v

    with mock.patch.object(MT, "terminal_current", bad_tc):
        c_bad = DT.transfer_curve(100.0, vg_list=DT.default_vg_list(n=5))
    ok_c3 = DT.current_conservation_report(c_bad)["passes"]
    check("C3 反向：破坏源端电流截面（源≠漏）⇒ G4 守恒判据必红", ok_c3 is False,
          "worst_rel=%.2e" % DT.current_conservation_report(c_bad)["worst_rel"])

    # C4 🔴 真破坏（本轮血案回归）：污染接触载流子 BC（假注入）⇒ 内核自检③ 必红
    real_cc = MT._contact_carriers

    def bad_cc(mask, psi, dev):
        n_arr, p_arr = real_cc(mask, psi, dev)
        return np.maximum(n_arr, dev["N_SD"] * 1e-3), p_arr

    with mock.patch.object(MT, "_contact_carriers", bad_cc):
        ok_c4 = MT.run_selfchecks(verbose=False)
    check("C4 反向：污染接触载流子 BC（假注入）⇒ 内核自检③「平衡零电流」必红"
          "（本轮真血案：源/漏整列钉 n⁺ 电位 = 短路源-体结）", ok_c4 is False)

    # C5 栅长趋势反向（伪造 L↓ ⇒ SS↓）⇒ G3 必红
    rev = {1000.0: dict(c1000, SS_mv_dec=200.0),
           250.0: dict(c250, SS_mv_dec=120.0),
           100.0: dict(c100, SS_mv_dec=70.0)}
    ok_c5 = DT.ss_vs_length_report(curves=rev)["monotone_long_to_short"]
    check("C5 反向：伪造栅长趋势反向（短沟道 SS 反而更小）⇒ G3 必红", ok_c5 is False)

    # 还原完整性：探针退出后 A1 复绿（无 patch 残留）
    check("C6 还原完整性：探针结束后内核自检复绿（无 mock 残留）",
          MT.run_selfchecks(verbose=False) is True)

    # ══════════════════════ D 惰性导入（无 scipy 环境可 import）═══════════════════════
    src = open(os.path.join(_ROOT, "lda", "lda_l2", "ecore", "device_transport.py"),
               encoding="utf-8").read()
    head = src.split("def _mt()")[0]
    check("D1 🔴 ecore 桥**惰性导入** scipy 依赖内核（模块级零 numpy/scipy ⇒ "
          "无 scipy 环境仍可 import 包）",
          all(k not in head for k in ("import numpy", "import scipy", "from numpy",
                                      "from scipy", "import lda_solver")))

    # ══════════════════════ K 自入 CI core ══════════════════════
    try:
        import run_ci_regression as R
        in_core = "run_ecore_e13_smoke.py" in R.CORE_SMOKES
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", in_core,
              "len=%d" % len(R.CORE_SMOKES))
    except Exception as e:  # pragma: no cover
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", False,
              "import 失败: %s" % e)

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
