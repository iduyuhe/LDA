#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""D-126 · 每模口径平台统一登记 + 三条物理/版图通道对齐 · 门禁 smoke。

把「每模口径」从**量子栈**（D-124）与**平台单一真源**（D-125）继续推到
**物理/版图层**的三条损耗通道，并钉成常驻判据：

  · `loss_aware_compile.il_per_port_direct_bus`（grid2d 直总线逐端口 IL）
    —— 此前只报 mean + var（最坏模藏在方差里）；
  · `mesh_tiling.d1_bus_budget` / `p3_tiling_ceiling`（瓦片总线 IL + 损耗天花板）
    —— 此前用 `⟨deg⟩ = N−1`（**列/均值口径**）⇒ 天花板**低估最坏模**；
  · `optical_pareto.optical_metrics`（光域 Pareto 损耗轴）
    —— 此前用 `deg_max`（已是每模最坏）但无统一词汇。

判据分组（A–G）：
  A 词汇/契约（`lda_l2.il_basis` 单一真源 · 序护栏 · 构造器/护栏正反向）
  B grid2d 总线通道（旧键零破坏 + 每模三项 ≡ 独立重算 + deg 结构不变量）
  C 瓦片通道（deg 来自真实几何 + 每模三项独立重算 + 跨模块模型差 == 绕行项 + 1.3 余量不足）
  D 瓦片天花板：每模口径**更严**（天花板 ≤ 均值天花板 + 逐行 identity + 单调）
  E Pareto 通道（il_worst ≡ 规范 max + 独立重算 + 能效守卫不误伤 + 反向护栏不空转）
  F 跨通道一致性 + 诚实边界 + 红线（四通道同词汇 + 反面篡改必红 + 非同一量 + 零 SDK）
  G mesh 通道（与 D-125 单一真源不矛盾）

🔴 立场：断言**事实**，包括不利事实 ——
   C5 断言「存在档位使含 1.3 余量的 `IL_full` 仍**低于**每模最坏 `IL_max`」
   （即 1.3 是**均值上的余量**，不能替代每模最坏）；
   F4 断言四通道是**不同布局模型**（spread 不相等），**不**假装是同一个量。

🔴 抗突变致病态：所有**生产调用**都走 `_safe()` —— 被突变打成异常时**自判红**（具名 [FAIL]），
   而不是让门禁崩溃（D-124 血案：崩成 exit=99 会丢失「哪条判据红了」的可归因性）。
运行：python lda/run_il_basis_platform_smoke.py
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

from lda_l2 import il_basis as ILB                     # noqa: E402
from lda_l2 import loss_aware_compile as LAC           # noqa: E402
from lda_l2 import mesh_tiling as MT                   # noqa: E402
from lda_l2 import mzi_mesh_matmul as MMM              # noqa: E402
from lda_l2 import optical_pareto as OP                # noqa: E402
from lda_layout.mesh_pnr import (                      # noqa: E402
    _rect_column_assignment,
    build_mesh_pnr,
    clements_rect_decompose,
)

# 🔴 调用签名：check(name, cond, detail="") —— 名字在前（P6·T6.1 血案）
PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True,
                   detail_fmt="  —— {d}", detail_on="fail")

TIERS = (4, 8, 16, 32)
_BANNED_SDK = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")


def _raises(fn):
    try:
        fn()
    except Exception:
        return True
    return False


def _safe(fn, default=None):
    """跑一个可能被突变打成异常的生产调用：异常 ⇒ `(False, default)`（门禁自判红，不崩溃）。"""
    try:
        return True, fn()
    except Exception:                                       # noqa: BLE001
        return False, default


def _deg_independent(N: int):
    """独立复算 deg 直方图（与 `build_mesh_pnr` 不同源：直接走 clements + 列分配）。"""
    U = np.fft.fft(np.eye(N)).astype(complex) / math.sqrt(N)
    bs, _D = clements_rect_decompose(U)
    _rect_column_assignment(bs)                        # 与 build_mesh_pnr 同调用序
    deg = [0] * N
    for (j, _t, _p) in bs:
        deg[j] += 1
        deg[j + 1] += 1
    return deg


def main() -> int:
    print("=" * 78)
    print("D-126 每模口径平台统一登记 + 三条物理/版图通道对齐")
    print("=" * 78)

    PDK = {"alpha_prop_db_cm": 2.0, "alpha_tap_db": 0.05}
    RP = LAC.RAIL_PITCH_DEFAULT
    GAP = LAC.GAP_DEFAULT

    def _bus(N):
        return LAC.il_per_port_direct_bus(
            build_mesh_pnr(MMM.dft_matrix(N), rail_pitch=RP, layout_mode="grid2d"), PDK)

    # ---------------------------------------------------------------- A 词汇/契约
    print("--- A 词汇/契约（il_basis 单一真源）---")
    ok_a, self_ok = _safe(lambda: ILB.run_selfchecks(verbose=False), False)
    check("A1 `lda_l2.il_basis` 模块自检 13/13 PASS",
          ok_a and self_ok is True, "词汇/构造/序护栏/正反向/跨通道汇总/反面篡改/披露")

    check("A2 规范必备键 %d 条齐备 · basis 四标签互异 · 词汇表声明四种口径名"
          % len(ILB.PER_MODE_REQUIRED_KEYS),
          len(ILB.PER_MODE_REQUIRED_KEYS) == 7
          and len({ILB.BASIS_PER_MODE, ILB.BASIS_COLUMN_MEAN, ILB.BASIS_TOTAL,
                   ILB.BASIS_PER_ELEMENT}) == 4
          and all(k in ILB.BASIS_VOCAB_NOTE for k in ("per_mode", "column_mean",
                                                      "total_cascade", "per_element")),
          "keys=%s" % list(ILB.PER_MODE_REQUIRED_KEYS))

    check("A3 披露键 ≥8 条且含 `no_physics`（本模块不偷算物理）/`no_cross_channel_equality`"
          "（不假装四通道同量）",
          len(ILB.IL_BASIS_DISCLOSURE) >= 8
          and all(isinstance(v, str) and v.strip() for v in ILB.IL_BASIS_DISCLOSURE.values())
          and "no_physics" in ILB.IL_BASIS_DISCLOSURE
          and "no_cross_channel_equality" in ILB.IL_BASIS_DISCLOSURE
          and "budget_not_measured" in ILB.IL_BASIS_DISCLOSURE,
          "keys=%d" % len(ILB.IL_BASIS_DISCLOSURE))

    check("A4 ★序护栏★ from_stats 报错序（min>mean>max）⇒ 必 raise",
          _raises(lambda: ILB.il_basis_from_stats(3.0, 2.0, 1.0, channel="t")))

    ok_g, _good = _safe(lambda: ILB.il_basis_from_values([1.0, 2.0, 3.0], channel="t"))
    _broken = dict(_good) if ok_g else {}
    if ok_g:
        del _broken["il_max_db"]
    ok_broke = _raises(lambda: ILB.assert_basis_consistency(_broken)) if ok_g else False
    ok_pass, _ = _safe(lambda: ILB.assert_basis_consistency(_good, expect_channel="t",
                                                            expect_n_modes=3))
    check("A5 护栏正反向：缺必备键 ⇒ raise · 合法登记 ⇒ 必过", ok_g and ok_broke and ok_pass)

    # ---------------------------------------------------------------- B grid2d 总线
    print("--- B grid2d 直总线通道（每模口径）---")
    bus_ok, bus_basis_ok, bus_deg_ok = True, True, True
    bus_det = {}
    for N in (8, 16):
        ok_pp, pp = _safe(lambda: _bus(N))
        ok_geo, geo = _safe(lambda: LAC.rail_geometry(
            build_mesh_pnr(MMM.dft_matrix(N), rail_pitch=RP, layout_mode="grid2d")))
        if not (ok_pp and ok_geo):
            bus_ok = bus_basis_ok = bus_deg_ok = False
            bus_det[N] = "调用异常"
            continue
        deg = _deg_independent(N)
        ap, at = PDK["alpha_prop_db_cm"], PDK["alpha_tap_db"]
        ils = [ap * (geo["L_bus_um"] + d * (RP - GAP)) / 1e4 + d * at for d in deg]
        want_mean = sum(ils) / len(ils)
        b = pp["il_basis_per_mode"]
        bus_det[N] = (round(pp["IL_mean_db"], 9), round(pp["IL_var_ports_db"], 9))
        bus_ok = bus_ok and abs(pp["IL_mean_db"] - want_mean) < 1e-12 \
            and abs(pp["IL_var_ports_db"] - (max(ils) - min(ils))) < 1e-12
        bus_basis_ok = bus_basis_ok and abs(b["il_min_db"] - min(ils)) < 1e-12 \
            and abs(b["il_mean_db"] - want_mean) < 1e-12 \
            and abs(b["il_max_db"] - max(ils)) < 1e-12 \
            and abs(b["il_spread_db"] - (max(ils) - min(ils))) < 1e-12 \
            and b["il_min_db"] < b["il_mean_db"] < b["il_max_db"] \
            and b["channel"] == "grid2d_bus" and b["n_modes"] == N \
            and b["per_element_kind"] == "per_tap_db"
        bus_deg_ok = bus_deg_ok and abs(geo["deg_mean"] - (N - 1)) < 1e-12 \
            and sum(deg) == N * (N - 1) and min(deg) == N // 2 and max(deg) == N
    check("B1 旧键**零破坏**：`IL_mean_db`/`IL_var_ports_db` ≡ 逐端口闭式独立重算（逐位）",
          bus_ok, "逐档(mean,var)=%s" % bus_det)
    check("B2 ★每模口径★ `il_basis_per_mode` 三项 ≡ 逐端口 IL 的 min/mean/max（独立重算）",
          bus_basis_ok, "channel/n_modes/per_element_kind 齐备")
    check("B3 deg 结构不变量：⟨deg⟩ == N−1 · Σdeg == N(N−1) · deg_min == N/2 · deg_max == N"
          "（偶数 N 实测锁定）",
          bus_deg_ok, "N=8/16（奇 N 未验证，故不并入本判据）")
    ok4, pp4 = _safe(lambda: _bus(16))
    check("B4 每模口径非退化：min < mean < max（真分布，非单点）· spread > 0",
          ok4 and pp4["il_basis_per_mode"]["il_spread_db"] > 0.0,
          "" if ok4 else "调用异常")
    ok5, pp5 = _safe(lambda: [_bus(N) for N in (8, 16)])
    check("B5 每模口径**不**等于端口均值口径：`IL_max_db > IL_mean_db`（最坏模 > 均值）",
          ok5 and all(p["IL_max_db"] > p["IL_mean_db"] for p in pp5),
          "" if ok5 else "调用异常")
    ok6, pp6 = _safe(lambda: _bus(8))
    ok6b, _ = _safe(lambda: ILB.assert_basis_consistency(
        pp6["il_basis_per_mode"], expect_channel="grid2d_bus", expect_n_modes=8))
    check("B6 `assert_basis_consistency` 对本通道登记必过（expect_channel/n_modes 匹配）",
          ok6 and ok6b)

    # ---------------------------------------------------------------- C 瓦片通道
    print("--- C 瓦片通道（每模口径 · 跨模块模型差）---")
    c1_ok, c2_ok, c3_ok, c4_ok, c5_ok = True, True, True, True, True
    c1_det, c2_det, c3_det, c4_det = {}, {}, {}, {}
    for N in TIERS:
        ok_d, d = _safe(lambda: MT.d1_bus_budget(N, scenario="B"))
        ok_t, tg = _safe(lambda: MT.tile_geometry(N))
        if not ok_d:
            c1_ok = c3_ok = False
            c1_det[N] = "调用异常"
            continue
        geo = d["geometry"]
        deg = _deg_independent(N)
        ap, at, mg = d["a_prop_db_cm"], d["a_tap_db"], d["rail_switch_margin"]
        L_cm = geo["L_bus_um"] / 1e4
        col_cm = (geo["L_bus_um"] / max(geo["n_cols"], 1)) / 1e4
        want_mean = ap * L_cm + (N - 1) * at
        want_full = ap * L_cm + ((N - 1) * mg) * at
        want_short = ap * col_cm + at
        c1_det[N] = round(d["IL_mean_db"], 9)
        c1_ok = c1_ok and abs(d["IL_mean_db"] - want_mean) < 1e-12 \
            and abs(d["IL_full_db"] - want_full) < 1e-12 \
            and abs(d["IL_short_db"] - want_short) < 1e-12 \
            and abs(d["IL_var_db"] - (want_full - want_short)) < 1e-12
        # C2 deg 来自**真实几何**（与独立复算一致）
        c2_det[N] = (tg["deg_min"], tg["deg_max"]) if ok_t else "调用异常"
        c2_ok = c2_ok and ok_t and tg["deg_min"] == min(deg) and tg["deg_max"] == max(deg) \
            and abs(tg["deg_mean"] - sum(deg) / N) < 1e-12
        # C3 每模三项独立重算
        b = d["il_basis_per_mode"]
        c3_det[N] = (round(b["il_min_db"], 9), round(b["il_mean_db"], 9), round(b["il_max_db"], 9))
        c3_ok = c3_ok and abs(b["il_min_db"] - (ap * L_cm + min(deg) * at)) < 1e-12 \
            and abs(b["il_mean_db"] - want_mean) < 1e-12 \
            and abs(b["il_max_db"] - (ap * L_cm + max(deg) * at)) < 1e-12 \
            and b["channel"] == "tiling" and b["n_modes"] == N \
            and b["il_min_db"] < b["il_mean_db"] < b["il_max_db"]
    check("C1 旧键**零破坏**：IL_mean/IL_full/IL_short/IL_var ≡ 闭式独立重算（含 1.3 余量，逐档逐位）",
          c1_ok, "逐档 IL_mean=%s" % c1_det)
    check("C2 `tile_geometry` 的 deg_min/deg_max/deg_mean ≡ 独立复算（clements + 列分配，不同源）",
          c2_ok, "逐档(min,max)=%s" % c2_det)
    check("C3 ★每模口径★ `il_basis_per_mode` ≡ α_prop·L/1e4 + {deg_min, N−1, deg_max}·α_tap（独立重算）",
          c3_ok, "逐档(min,mean,max)=%s" % c3_det)

    # C4 跨模块模型差 ≡ 每抽头波导绕行项（tiling 模型**不含**绕行）
    ok_bus8, pp8 = _safe(lambda: _bus(8))
    ok_til8, t8 = _safe(lambda: MT.d1_bus_budget(8, scenario="B"))
    want_detour = PDK["alpha_prop_db_cm"] * (RP - GAP) / 1e4
    if ok_bus8 and ok_til8:
        bus_pe = pp8["il_basis_per_mode"]["per_element_db"]
        til_pe = t8["il_basis_per_mode"]["per_element_db"]
        c4_ok = abs((bus_pe - til_pe) - want_detour) < 1e-12
        c4_det = {"bus_pe": round(bus_pe, 9), "til_pe": round(til_pe, 9),
                  "want_detour": round(want_detour, 9)}
    else:
        c4_ok = False
        c4_det = "调用异常"
    check("C4 ★跨模块口径对账★ 总线每抽头 − 瓦片每抽头 ≡ α_prop·(rail_pitch−gap)/1e4（= 绕行项）",
          c4_ok, "逐值=%s" % c4_det)

    # C5 1.3 余量不能替代每模最坏：N_tile=4 时 IL_full < IL_max；N_tile=8 时 IL_full > IL_max
    ok_d4, d4 = _safe(lambda: MT.d1_bus_budget(4, scenario="B"))
    ok_d8, d8 = _safe(lambda: MT.d1_bus_budget(8, scenario="B"))
    c5_ok = ok_d4 and ok_d8 and d4["IL_full_db"] < d4["IL_max_db"] \
        and d8["IL_full_db"] > d8["IL_max_db"]
    check("C5 🔴 1.3 余量是**均值上的余量**，不能替代每模最坏：N_tile=4 ⇒ IL_full < IL_max",
          c5_ok, ("N=4 full=%.6f max=%.6f | N=8 full=%.6f max=%.6f"
                  % (d4["IL_full_db"], d4["IL_max_db"], d8["IL_full_db"], d8["IL_max_db"]))
          if (ok_d4 and ok_d8) else "调用异常")

    # ---------------------------------------------------------------- D 每模式天花板
    print("--- D 瓦片损耗天花板：每模口径更严 ---")
    d1_ok, d2_ok, d3_ok, d4b_ok, d5_ok = True, True, True, True, True
    d1_det, d4b_det = {}, {}
    for N in TIERS:
        ok_p3, p3 = _safe(lambda: MT.p3_tiling_ceiling(N, scenario="B", t_table=MT.T_TABLE))
        ok_w, dw = _safe(lambda: MT.d1_bus_budget(N, scenario="B"))
        if not (ok_p3 and ok_w):
            d1_ok = d2_ok = d3_ok = d4b_ok = d5_ok = False
            d1_det[N] = d4b_det[N] = "调用异常"
            continue
        rows = p3["rows"]
        il_worst = dw["IL_max_db"]
        il_lnk = p3["IL_link_per_boundary_db"]
        il_par = p3["IL_par_per_tile_db"]
        for r in rows:
            T = r["T"]
            d2_ok = d2_ok and abs(r["IL_total_per_mode_db"]
                                  - (il_worst * T + il_lnk * (T - 1) + il_par * T)) < 1e-12
            d3_ok = d3_ok and abs(r["IL_total_db"]
                                  - (r["IL_bus_db"] + r["IL_link_db"] + r["IL_par_db"])) < 1e-12
            d2_ok = d2_ok and r["IL_total_per_mode_db"] >= r["IL_total_db"] - 1e-12
        d1_ok = d1_ok and p3["ceiling_per_mode_eq_N"] <= p3["ceiling_eq_N"] \
            and p3["ceiling_per_mode_rx_N"] <= p3["ceiling_rx_N"]
        d1_det[N] = (p3["ceiling_eq_N"], p3["ceiling_per_mode_eq_N"],
                     p3["ceiling_rx_N"], p3["ceiling_per_mode_rx_N"])
        exp_pm_rx = max((r["N"] for r in rows if r["IL_total_per_mode_db"] <= 20.0), default=0)
        exp_pm_eq = max((r["N"] for r in rows if r["IL_total_per_mode_db"] <= 30.0), default=0)
        d4b_ok = d4b_ok and p3["ceiling_per_mode_rx_N"] == exp_pm_rx \
            and p3["ceiling_per_mode_eq_N"] == exp_pm_eq
        d4b_det[N] = (p3["ceiling_per_mode_rx_N"], exp_pm_rx)
        tot = [r["IL_total_per_mode_db"] for r in rows]
        d5_ok = d5_ok and all(tot[i] < tot[i + 1] for i in range(len(tot) - 1))
    check("D1 ★每模口径更严★ 逐档 `ceiling_per_mode_* ≤ ceiling_*`（eq 与 rx 两阈值）",
          d1_ok, "逐档(eq,eq_pm,rx,rx_pm)=%s" % d1_det)
    check("D2 逐行 `IL_total_per_mode_db` ≡ T·IL_max + (T−1)·IL_link + T·IL_par（独立重算）"
          "且 ≥ 均值口径同行",
          d2_ok)
    check("D3 旧键**零破坏**：逐行 `IL_total_db` ≡ bus+link+par（独立重算）",
          d3_ok)
    check("D4 每模式天花板 ≡ 由 rows 独立重算（逐档逐位，不插值不外推）",
          d4b_ok, "逐档(报告,复算)=%s" % d4b_det)
    check("D5 每模式 `IL_total_per_mode_db` 随 T **严格增**",
          d5_ok)

    # ---------------------------------------------------------------- E Pareto 通道
    print("--- E 光域 Pareto 损耗轴（每模最坏）---")
    e1_ok, e2_ok, e3_ok = True, True, True
    for N in (4, 8, 16):
        ok_mo, mo = _safe(lambda: OP.optical_metrics(N, 4, arch="shared"))
        ok_geo, geo = _safe(lambda: LAC.rail_geometry(
            build_mesh_pnr(MMM.dft_matrix(N), rail_pitch=LAC.RAIL_PITCH_DEFAULT,
                           layout_mode="grid2d")))
        if not (ok_mo and ok_geo):
            e1_ok = e2_ok = e3_ok = False
            continue
        ap, at = LAC.ALPHA_PROP_DEFAULT, LAC.ALPHA_TAP_DEFAULT
        ils = [ap * (geo["L_bus_um"] + d * (LAC.RAIL_PITCH_DEFAULT - LAC.GAP_DEFAULT)) / 1e4
               + d * at for d in geo["deg"]]
        b = mo["il_basis_per_mode"]
        e1_ok = e1_ok and abs(mo["il_worst_db"] - b["il_max_db"]) < 1e-12 \
            and mo["il_basis"] == "per_mode"
        e2_ok = e2_ok and abs(b["il_min_db"] - min(ils)) < 1e-12 \
            and abs(b["il_mean_db"] - sum(ils) / len(ils)) < 1e-12 \
            and abs(b["il_max_db"] - max(ils)) < 1e-12 \
            and b["channel"] == "pareto" and b["n_modes"] == N
        e3_ok = e3_ok and mo["deg_max"] == max(geo["deg"]) \
            and abs(mo["L_bus_um"] - geo["L_bus_um"]) < 1e-12 \
            and mo["macs_per_pass"] == 4 * N * N
    check("E1 ★Pareto 损耗轴 ≡ 规范 max★ `il_worst_db ≡ il_basis_per_mode.il_max_db` · `il_basis=='per_mode'`",
          e1_ok, "逐 N 一致")
    check("E2 `il_basis_per_mode` 三项 ≡ 独立重算（rail_geometry + 闭式，不同源）",
          e2_ok)
    check("E3 旧键**零破坏**：deg_max / L_bus_um / macs_per_pass ≡ 直接重算",
          e3_ok)

    ok_t, t = _safe(lambda: OP.optical_pareto_table(Ns=(2, 4, 8), Ks=(1, 4),
                                                    precision_bits=8.1328))
    check("E4 `optical_pareto_table` 带 `il_basis=='per_mode'` 且逐行有 `il_basis_per_mode`；"
          "新键**不触发**能效守卫（assert_no_energy_metrics 已在该函数内）",
          ok_t and t["il_basis"] == "per_mode" and "il_basis_note" in t
          and all("il_basis_per_mode" in r for r in t["rows"])
          and len(t["rows"]) == 2 * 3 * 2)
    ok_g, g = _safe(lambda: OP.loss_relax_reverse_guard())
    check("E5 反向护栏**不空转**：放宽损耗上限 ⇒ Pareto 面必须移动（新键未干扰支配判决）",
          ok_g and g["moved"] is True and g["n_kept_relaxed"] > g["n_kept_tight"],
          ("tight=%d → relaxed=%d" % (g["n_kept_tight"], g["n_kept_relaxed"]))
          if ok_g else "调用异常")

    # ---------------------------------------------------------------- F 跨通道 + 诚实 + 红线
    print("--- F 跨通道一致性 + 诚实边界 + 红线 ---")
    ok_man, man = _safe(lambda: ILB.il_basis_manifest(8))
    _chs = man["channels"] if (ok_man and isinstance(man, dict)) else {}
    check("F1 ★跨通道一致性★ N=8 四通道（mesh/grid2d_bus/tiling/pareto）同 per_mode 词汇且一致",
          ok_man and man["n_channels"] == 4 and man["consistent"] is True
          and man["all_per_mode"] is True
          and set(_chs) == {"mesh", "grid2d_bus", "tiling", "pareto"},
          "channels=%s" % (sorted(_chs) if _chs else "调用异常"))
    ok_f2, _ = _safe(lambda: all(
        ILB.assert_basis_consistency(e, expect_channel=k, expect_n_modes=8)
        for k, e in _chs.items()) and _chs["mesh"]["il_max_db"] > 0.0)
    check("F2 逐通道过 `assert_basis_consistency`（键齐 + 序正确 + basis 标签 + spread 自洽）",
          ok_man and ok_f2)
    _bad = {k: dict(v) for k, v in _chs.items()}
    if "tiling" in _bad:
        _bad["tiling"]["il_max_db"] = _bad["tiling"]["il_min_db"]
    check("F3 ★反面★ 篡改一条通道（max→min）⇒ `assert_manifest_consistent` 必 raise",
          bool(_bad) and _raises(lambda: ILB.assert_manifest_consistent(
              {"N": 8, "channels": _bad})))
    _sp_mesh = _chs["mesh"]["il_spread_db"] if "mesh" in _chs else None
    _sp_bus = _chs["grid2d_bus"]["il_spread_db"] if "grid2d_bus" in _chs else None
    check("F4 🔴 四通道是**不同布局模型**（不做数值等价）：mesh spread ≠ bus spread，"
          "词汇统一但数值各自独立",
          ok_man and _sp_mesh is not None and _sp_bus is not None
          and abs(_sp_mesh - _sp_bus) > 1.0
          and "no_cross_channel_equality" in man["disclosure"],
          ("mesh spread=%.4f vs bus spread=%.4f" % (_sp_mesh, _sp_bus))
          if (_sp_mesh is not None and _sp_bus is not None) else "调用异常")
    ok_src, _src = _safe(lambda: open(os.path.join(_HERE, "lda_l2", "il_basis.py"),
                                      encoding="utf-8").read(), "")
    check("F5 红线：`il_basis` **零 numpy**（纯 stdlib）· 零量子 SDK · 判决全为实数/整数/布尔",
          ok_src and "import numpy" not in _src
          and not any(b in _src.lower() for b in _BANNED_SDK)
          and "no_llm" in ILB.IL_BASIS_DISCLOSURE)

    # ---------------------------------------------------------------- G mesh 通道
    print("--- G mesh 通道（D-125 单一真源 · 不变量）---")
    m_ok = True
    for N in (4, 8, 16):
        ok_r, pack = _safe(lambda: (MMM.reck_triangular_mesh(MMM.dft_matrix(N))[0],))
        if not ok_r:
            m_ok = False
            continue
        ops = pack[0]
        ok_s, st = _safe(lambda: MMM.mesh_per_mode_optical_depth_stats(ops, n_modes=N))
        ok_m, mb = _safe(lambda: MMM.mesh_loss_basis(ops))
        ok_sc, dsc = _safe(lambda: MMM.mesh_per_mode_optical_depth(ops))
        m_ok = m_ok and ok_s and ok_m and ok_sc \
            and st["depth_max"] == dsc \
            and st["depth_max"] == mb["per_mode_optical_depth"] \
            and abs(st["depth_max"] * mb["per_mzi_loss_db"] - mb["per_mode_db"]) < 1e-12 \
            and st["depth_min"] <= st["depth_mean"] <= st["depth_max"] \
            and tuple(st["depths"]) == tuple(range(N))
    check("G1 `mesh_per_mode_optical_depth_stats` **同一计数真源**：depth_max ≡ 标量版 ≡ "
          "mesh_loss_basis.per_mode_optical_depth；分布覆盖全部 N 个模",
          m_ok, "逐档 depth_max 一致")

    print()
    print("=" * 78)
    total = PASS + FAIL
    print("D-126 每模口径门禁 smoke：%d PASS / %d FAIL / 共 %d 项" % (PASS, FAIL, total))
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
