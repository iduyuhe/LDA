#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E44 门禁：**电源网格全域 IR 求解** —— 真矩阵解替代「均匀抽流一阶」。

## 本门禁守什么
B3 的 `ir_drop_closed` 假设「单根轨 + 电流沿轨均匀抽走 + 只看末端」⇒ `V = I·R/2`。
真实电源网格是 **M3 横条 × M4 竖条 + 交叉 via** 的网，电流从少数凸点注入、分散到上千负载点，
走二维路径 —— 最坏压降点既不在末端，也不由 `R/2` 决定，只能解 `G·V = I`。

| # | 守护 | 金标 |
|---|---|---|
| A1 | **退化关系** | 网格退化成「单链 + 均匀抽流」时，全域解 ≡ B3 `ir_drop_ladder` = `R·I·(n+1)/(2n)`（n=1..64 逐点） |
| A2 | 闭式极限 | n=4000 ⇒ 收敛到 `ir_drop_closed` = `I·R/2`（相对差 <1e-3，理论 1/2n=1.25e-4） |
| A3 | 假设差异（精确） | 同一总电流压在**远端单点**上 ⇒ 压降 = **2×** 闭式（精确，非近似） |
| A4 | **双解法互证** | 自己组装的电导矩阵+Dirichlet ⇄ 仓内 E1 `mna.Circuit`，四组网格含多源，相对差 <1e-9 |
| A5 | 守恒律 | KCL 残差 <1e-9 · 源注入功率 ≡ 网格耗散+负载耗散（<1e-9） |
| B1 | 线性性 | 所有电阻 ×3 ⇒ 最坏压降 ×3（精确，rel <1e-9） |
| B2 | **Rayleigh 单调性** | via 电阻减半 ⇒ 最坏压降**严格降**；加第二个电源凸点 ⇒ 严格降 |
| B3 | EM 标度 | `J=I/(w·t)` 在段电流上算；线宽 ×2 ⇒ J 恰好 ×0.5 |
| B4 | 拓扑只报告 | uniform/point/rail 三口径压降**只打印**，不设带宽；仅断言「点负载 ≥ 均匀负载」 |
| C1 | 判别力 | 负电阻／负负载／节点越界／退化网格／**悬空网络** 五类输入必报错 |
| C2 | 确定性 | 两次求解逐位相同 |
| C3 | 规模与耗时 | 16×16（512 节点 / 736 支路）可解且 < 阈值 |

## 诚实口径
- 🔴 **只解静态 DC IR**：无 `di/dt` 动态压降、无 decap、无封装/板级阻抗。
- 🔴 单角 tt、负载为理想电流沉（真实单元低压下电流下降 ⇒ 本模型**偏保守**）。
- 🔴 规则网格：不支持非均匀 pitch、宽窄混排、阻挡/打孔、多源不等压。
- 🔴 **不许说「网格压降一定大于闭式」**：8×8 实测只有单轨闭式的 0.46×（`ny` 条横条并联）。
  比值是**拓扑相关**的，只报告不当判据。同理「加列数必降」也不成立（加列会拉宽网格）。
- 🔴 **净增 0 锚**（线性方程解 ⇒ 残差恒 0）⇒ 门禁形态（同 E39–E43）；不报 TOPS/fJ/能效。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dpgrid as PG          # noqa: E402
from lda_l2.ecore import dsignoff as SG        # noqa: E402
from lda_harness.smoke_kit import make_check   # noqa: E402

AN_ELAPSED_MAX_S = 60.0

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def _ladder_case(nseg, i_total):
    """单链：n 段、总电流均摊到每段末端节点。"""
    r_tot = SG.RSH["M3"] * 20.0 / 0.5
    g = PG.build_ladder(nseg, r_tot / nseg)
    loads = {k: i_total / nseg for k in range(1, nseg + 1)}
    return g, loads, r_tot


def main():
    t0 = time.time()
    print("=" * 78)
    print("E44 · 电源网格全域 IR 求解（真矩阵解：G·V = I）")
    print("=" * 78)

    rsh, l_um, w_um = SG.RSH["M3"], 20.0, 0.5
    i_tot = 1e-3

    # ── A1 退化：单链 ≡ B3 ir_drop_ladder ────────────────────────────
    rows = []
    for nseg in (1, 2, 4, 8, 16, 64):
        g, loads, _r = _ladder_case(nseg, i_tot)
        got = PG.solve_reduced(g, loads)["worst_drop_v"]
        ref = SG.ir_drop_ladder(i_tot, rsh, l_um, w_um, nseg)
        rows.append((nseg, got, ref, abs(got - ref) / ref))
    worst = max(r[3] for r in rows)
    check("A1 退化关系：单链全域解 ≡ B3 ir_drop_ladder = R·I·(n+1)/(2n)（n=1,2,4,8,16,64 逐点）",
          worst < 1e-9, "最差相对差 %.2e @n=%d · %s"
          % (worst, [r[0] for r in rows if r[3] == worst][0],
             " ".join("n%d:%.9f" % (a, b) for a, b, _c, _d in rows[:4])))

    # ── A2 闭式极限 ────────────────────────────────────────────────
    nbig = 4000
    g, loads, _r = _ladder_case(nbig, i_tot)
    big = PG.solve_reduced(g, loads)["worst_drop_v"]
    closed = SG.ir_drop_closed(i_tot, rsh, l_um, w_um)
    rel = abs(big - closed) / closed
    check("A2 闭式极限：n=4000 ⇒ 逼近 ir_drop_closed = I·R/2（理论 1/(2n)=1.25e-4，实测 <1e-3）",
          rel < 1e-3, "closed=%.9f mesh=%.9f rel=%.2e" % (closed, big, rel))

    # ── A3 点负载 = 2× 闭式（精确）───────────────────────────────────
    nseg = 20
    g, _loads, r_tot = _ladder_case(nseg, i_tot)
    point = PG.solve_reduced(g, {nseg: i_tot})["worst_drop_v"]
    closed20 = SG.ir_drop_closed(i_tot, rsh, l_um, w_um)
    ratio = point / closed20
    check("A3 假设差异（精确）：同一总电流压在远端单点 ⇒ 压降 = 2× 闭式 I·R/2",
          abs(ratio - 2.0) < 1e-9, "point=%.9f closed=%.9f ratio=%.12f"
          % (point, closed20, ratio))

    # ── A4 双解法互证（含多源）───────────────────────────────────────
    cases = []
    for (nx, ny) in ((4, 4), (8, 8), (12, 20)):
        gg = PG.build_grid(nx, ny)
        cases.append(("%dx%d" % (nx, ny), gg, PG.uniform_loads(gg, 2e-3)))
    g8 = PG.build_grid(8, 8)
    g8s = PG.add_source(g8, g8["idx"][("h", 7, 7)])
    cases.append(("8x8+2源", g8s, PG.uniform_loads(g8s, 2e-3)))
    diffs = []
    for label, gg, ld in cases:
        c = PG.compare_solvers(gg, ld)
        diffs.append((label, c["rel_diff"]))
    dmax = max(d for _l, d in diffs)
    check("A4 双解法互证：自组装电导矩阵+Dirichlet ⇄ 仓内 E1 MNA（四组含多源）相对差 <1e-9",
          dmax < 1e-9, " ".join("%s:%.1e" % (l, d) for l, d in diffs))

    # ── A5 守恒律（KCL + 能量）──────────────────────────────────────
    kcl, pb = [], []
    for _label, gg, ld in cases:
        r = PG.solve_reduced(gg, ld)
        kcl.append(r["kcl_residual"])
        pb.append(r["power_balance_rel"])
    check("A5 守恒律：KCL 残差 <1e-9 ∧ 源注入功率 ≡ 网格耗散 + 负载耗散（<1e-9）",
          max(kcl) < 1e-9 and max(pb) < 1e-9,
          "KCL 最差 %.2e · 能量最差 %.2e" % (max(kcl), max(pb)))

    # ── B1 线性性 ──────────────────────────────────────────────────
    ld8 = PG.uniform_loads(g8, 2e-3)
    base = PG.solve_reduced(g8, ld8)["worst_drop_v"]
    g3 = dict(g8)
    g3["edges"] = [(a, b, r * 3.0, k, l) for (a, b, r, k, l) in g8["edges"]]
    tri = PG.solve_reduced(g3, ld8)["worst_drop_v"]
    check("B1 线性性：所有电阻 ×3 ⇒ 最坏压降恰 ×3",
          abs(tri / base - 3.0) < 1e-9, "base=%.9f ×3=%.9f ratio=%.12f"
          % (base, tri, tri / base))

    # ── B2 Rayleigh 单调性 ─────────────────────────────────────────
    g_half = PG.build_grid(8, 8, via_r=PG.R_VIA_OHM / 2.0)
    d_via = PG.solve_reduced(g_half, ld8)["worst_drop_v"]
    d_src = PG.solve_reduced(g8s, PG.uniform_loads(g8s, 2e-3))["worst_drop_v"]
    check("B2 Rayleigh 单调性：via 电阻减半 ⇒ 最坏压降严格降 ∧ 加第二电源凸点 ⇒ 严格降",
          d_via < base and d_src < base,
          "base=%.6f mV · via/2=%.6f（↓%.2f%%）· 2源=%.6f（↓%.2f%%）"
          % (base * 1e3, d_via * 1e3, (base - d_via) / base * 100,
             d_src * 1e3, (base - d_src) / base * 100))

    # ── B3 EM：标度 ∧ 判定标志双向可翻 ──────────────────────────────
    res8 = PG.solve_reduced(g8, ld8)
    w1 = PG.em_segments(g8, res8, width_um=PG.PG_WIDTH_UM)
    w2 = PG.em_segments(g8, res8, width_um=PG.PG_WIDTH_UM * 2.0)
    em_ratio = (w2["j_a_m2"] / w1["j_a_m2"]) if w1["j_a_m2"] > 0 else 0.0
    # 同一几何把总电流降到 1/8 ⇒ J 也降到 1/8 ⇒ 判定必须从「超限」翻成「通过」
    lo = PG.solve_reduced(g8, PG.uniform_loads(g8, 2e-3 / 8.0))
    w_lo = PG.em_segments(g8, lo, width_um=PG.PG_WIDTH_UM)
    check("B3 EM：J=I/(w·t) 线宽 ×2 ⇒ J 恰 ×0.5 ∧ 判定标志双向可翻（超限↔通过）",
          abs(em_ratio - 0.5) < 1e-12 and (w1["ok"] is False) and (w_lo["ok"] is True),
          "J=%.3e A/m²（裕量 %.2f× · ok=%s · %s）⇒ 电流/8 后 ok=%s · J2/J1=%.12f"
          % (w1["j_a_m2"], w1["margin_x"], w1["ok"], w1["kind"], w_lo["ok"], em_ratio))
    if not w1["ok"]:
        print("     🔴 真实结论：本演示工况（8×8 / 总 2 mA / 0.5 µm）**违反 EM**"
              "（J=%.2e > J_MAX=%.1e，裕量 %.2f×）⇒ 需要加宽或加源 —— 这是全域解才看得见的事"
              % (w1["j_a_m2"], w1["j_max"], w1["margin_x"]))

    # ── B4 拓扑只报告（不设带宽）────────────────────────────────────
    rep = PG.topology_report(8, 8, 2e-3)
    print("  [拓扑报告·仅报告不作判据] 8×8：uniform=%.4f mV · point=%.4f mV · 单轨闭式=%.4f mV"
          % (rep["uniform_drop_v"] * 1e3, rep["point_drop_v"] * 1e3, rep["rail_closed_v"] * 1e3))
    print("    比值：point/uniform=%.2f · uniform/rail=%.2f · point/rail=%.2f"
          "（🔴 比值随拓扑变，不给带宽，也不说「网格一定更差」）"
          % (rep["point_over_uniform"], rep["uniform_over_rail"], rep["point_over_rail"]))
    check("B4 点负载 ≥ 均匀负载（唯一敢断言的方向）；三口径压降仅报告不设带宽",
          rep["point_over_uniform"] > 1.0,
          "point/uniform=%.4f" % rep["point_over_uniform"])

    # ── C1 判别力：五类非法输入必报错 ───────────────────────────────
    def _expect_error(fn, *a, **kw):
        try:
            fn(*a, **kw)
            return False
        except (ValueError, KeyError, IndexError):
            return True

    bad_neg_r = dict(g8)
    bad_neg_r["edges"] = [(a, b, -r, k, l) for (a, b, r, k, l) in g8["edges"]]
    victim = g8["idx"][("h", 7, 7)]
    bad_float = dict(g8)
    bad_float["edges"] = [e for e in g8["edges"] if victim not in (e[0], e[1])]
    probes = [
        ("负电阻", _expect_error(PG.solve_reduced, bad_neg_r, ld8)),
        ("负负载", _expect_error(PG.solve_reduced, g8, {0: -1e-3})),
        ("节点越界", _expect_error(PG.solve_reduced, g8, {10 ** 6: 1e-3})),
        ("退化网格", _expect_error(PG.build_grid, 1, 1)),
        ("悬空网络", _expect_error(PG.solve_reduced, bad_float, ld8)),
    ]
    missed = [k for k, ok in probes if not ok]
    check("C1 判别力：负电阻／负负载／节点越界／退化网格／悬空网络 五类必报错",
          not missed, "漏抓 %s" % (missed or "无（5/5 全抓）"))

    # ── C2 确定性 ──────────────────────────────────────────────────
    a1 = PG.solve_reduced(g8, ld8)["v"]
    a2 = PG.solve_reduced(g8, ld8)["v"]
    check("C2 确定性：同一输入两次求解逐位相同", bool((a1 == a2).all()),
          "max|Δ|=%.1e" % float(abs(a1 - a2).max()))

    # ── C3 规模与耗时 ──────────────────────────────────────────────
    gg = PG.build_grid(16, 16)
    r16 = PG.solve_reduced(gg, PG.uniform_loads(gg, 4e-3))
    dt = time.time() - t0
    check("C3 规模：16×16（%d 节点 / %d 支路）可解 · 全门禁耗时 %.2f s < %.0f s"
          % (r16["n_nodes"], r16["n_edges"], dt, AN_ELAPSED_MAX_S),
          r16["n_nodes"] == 512 and dt < AN_ELAPSED_MAX_S,
          "drop=%.4f mV · KCL=%.1e" % (r16["worst_drop_v"] * 1e3, r16["kcl_residual"]))

    print("  [诚实边界] %s" % "；".join(PG.DPGRID_DISCLOSURE["limits"][:3]))
    print("-" * 78)
    print("E44 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("E44 有红色：见上方 [FAIL] 行")
        return 1
    print("E44 全绿 · 电源网格全域 IR：两解法互证 · 单链退化 ≡ B3 阶梯解 · 点负载=2×闭式 · "
          "Rayleigh 单调 · 净增 0 锚（**只解静态 DC，见披露清单**）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
