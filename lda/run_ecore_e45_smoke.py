#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E45 门禁（v0.9.349 收口）：**引脚可接入化 ⇒ 路由 DRC 归零**（14 条残差归零）。

## 本门禁守什么
E45 把 B 系列接进主链后，路由 DRC 34→14，并把 14 条残差**归因到单元引脚**：
`dcells` 的 M1 引脚只有 65nm 高、同单元内不同网的引脚 y 中心只差 0.0175–0.0375µm，
而 M3 接入焊盘高 0.242、互要 0.10 间距 ⇒ 两引脚接入点必须 ≥**0.342µm**。
v0.9.349 的任务是把「归因」变成「修掉」，并把修的过程做成可证伪的判据。

| # | 守护 | 金标 |
|---|---|---|
| A1 | 单元几何保真 | 重画引脚后 `dcells` 的 DRC/LVS **仍为 0**（平移不变） |
| A2 | 引脚自合法 | 每个信号 pad 两维 ≥`VIA+2·ENC=0.24` ∧ 同单元接入点两两 ≥pitch |
| A3 | 接入点零移动 | 接入点 == pad 中心（引脚自身就够落孔，不靠路由器补焊盘） |
| A4 | **判据有牙** | 两个反例探针（pad 缩到 0.20 / 挪进邻引脚 y 带）必须报**对应错误码** |
| B1 | DRC 归零 | 对 E36 式 L 路由基线（同网表同布局）**34 → 0** |
| B2 | 零残差 | 路由 DRC 与全量 DRC **都为 0**，且不含短路类 |
| B3 | 容量律有牙 | 每通道**实际用轨数 ≤ T** ∧ A2 密度 d ≤ 实际用轨数 ∧ 列失败 0 |
| B4 | 连通性 | 每个被布网**恰好 1 个连通分量** |
| C1 | 提取成网 | 被布网网络 `R>0 ∧ C>0` |
| C2 | 网格 IR/EM | PG 网格可解、KCL 闭合、EM 裕量如实报 |
| C3 | 确定性 | 两次路由几何逐位一致 |
| B0 | 耗时 | < 阈值 |

## 归零靠的**三件事**（不是一件，必须一起说）
1. **引脚重画**（`dcells`，本版）：信号引脚换成 **240×240 pad**，接入点落在
   120/480/840 nm 的**库级列网格**上 ⇒ 同单元两两 x 差恰一个 pitch；
2. **trunk 着色改用真实跨度**（`route_block`）：旧版按「引脚跨度」着色、trunk 却画到
   「引脚 ∪ 列」的跨度 ⇒ 列一被推远，同轨两网的 trunk 就叠死（E45 里那几条 trunk 短接）；
3. **通道数 == 行数 + 单元间距取轨道间距整数倍**（`place_real`，1.44 = 4×0.36）：
   每行上方都有自己的通道、接入点全域同相位 ⇒ **跳线长度归零**，列不再被挤走。

## 诚实口径（不许省）
- 🔴 **零 DRC 只对「这一个用例」成立**：12 单元 / 4 列 / 2 类单元（INV、NAND2）/
  自建规则集 LDA-DEMO45。换单元类型（DFF 仍未建模）、换列数、换通道高度**都要重测**，
  本门禁不宣称「全 IP 零 DRC」。
- 🔴 **不是通用路由器**：每网一条 M3 trunk 的星形拓扑，无 maze / rip-up / 协商，
  不做线长优化；只有一层垂直层（M4）可用，真实设计还有 M5+。
- 🔴 **规则集非 PDK**：W_MIN/S_MIN/ENC/VIA 都是教科书尺度假设 ⇒ 不得作制造/性能宣称。
- 🔴 引脚重画**没有增大单元面积**（INV 0.7688 / NAND2 1.4700 µm² 不变），代价落在
  **单元间距**（0.36→0.46µm）与**行数通道**（多一条通道）上 —— 这是真实成本，要报。
- 🔴 净增 0 锚（整数几何 + 组合分配 ⇒ resid≡0）⇒ 门禁形态。
"""

import copy
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dpnr as PN          # noqa: E402
from lda_l2.ecore import dcells as CL       # noqa: E402
from lda_l2.ecore import dctrl as CT         # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL      # noqa: E402
from lda_l2.ecore import dspef as SP         # noqa: E402
from lda_l2.ecore import dpgrid as PG        # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 120.0
AN_BASELINE_MIN = 30          # 基线 DRC 至少要这么多条（证明对比面对手是真的）

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)

#: 主用例：12 单元 / 4 列（3 行）
CASE_N = 12
CASE_COLS = 4


def _probe_cells(mutate: str) -> dict:
    """构造反例几何（判据的判别力探针）。`mutate` 指定扰动方式。"""
    cells = {n: f() for n, f in CL.CELLS.items()}
    inv = copy.copy(cells["INV_X1"])
    inv.pins = dict(inv.pins)
    r = inv.pins["Y"]
    if mutate == "shrink":
        # pad 高度压到 0.20 < VIA+2·ENC=0.24 ⇒ 孔放不下（只能靠外挂焊盘）
        inv.pins["Y"] = CL.R(CL.L_M1, r.x0, r.y0, r.x1, r.y0 + 200, net="Y")
    elif mutate == "crowd":
        # pad 挪进 A 的 y 带，且 x 也缩到一个 pitch 以内 ⇒ 两个 M3 焊盘必叠
        inv.pins["Y"] = CL.R(CL.L_M1, 300, 550, 540, 790, net="Y")
    else:
        raise ValueError(mutate)
    cells["INV_X1"] = inv
    return cells


def main():
    t0 = time.time()
    print("=" * 78)
    print("E45 · 引脚可接入化 ⇒ 路由 DRC 归零（14 条残差收口 · v0.9.349）")
    print("=" * 78)

    nl = CT.build()["netlist"]
    pl = PN.place_real(nl, max_cells=CASE_N, cols=CASE_COLS)

    # ── A1 单元几何保真（重画引脚后 DRC/LVS 仍 0）─────────────────────
    cl = PN.cell_drc_lvs(pl)
    bad = {k: v for k, v in cl.items() if v["drc"] or v["lvs"]}
    check("A1 单元几何保真：重画引脚后 dcells 的 DRC/LVS 仍全 0（平移不变）",
          not bad, "%s" % (cl if not bad else bad))

    # ── A2 引脚自合法（pad 尺寸 + 接入点间距）────────────────────────
    lg = PN.pin_legality()
    detail = " · ".join("%s min_pad=%.3f min_sep=%.3f"
                        % (k, v["min_pad_um"], v["min_sep_um"]) for k, v in lg["cells"].items())
    check("A2 引脚自合法：每个信号 pad 两维 ≥%.2fµm ∧ 同单元接入点两两 ≥%.2fµm"
          % (lg["need_pad_um"], lg["need_sep_um"]),
          lg["ok"], "%s · 违规 %d" % (detail, lg["n_violations"]))

    # ── A3 接入点零移动（引脚自身够落孔，不靠路由器补焊盘）───────────
    pts = [p for i in pl["insts"] for p in PN.pin_access_points(i)]
    moved = [p for p in pts if abs(p["moved_um"]) > 1e-9]
    check("A3 接入点零移动：接入点 == pad 中心（不靠路由器外挂 M1 焊盘擦屁股）",
          not moved and all(p["feasible"] for p in pts),
          "接入点 %d 个 · 被移动 %d · 不可行 %d"
          % (len(pts), len(moved), sum(1 for p in pts if not p["feasible"])))

    # ── A4 判据有牙（两个反例探针，必须报**对应**错误码）──────────────
    p1 = PN.pin_legality(_probe_cells("shrink"))
    p2 = PN.pin_legality(_probe_cells("crowd"))
    k1 = sorted({v[0] for c in p1["cells"].values() for v in c["violations"]})
    k2 = sorted({v[0] for c in p2["cells"].values() for v in c["violations"]})
    check("A4 判据有牙：pad 缩到 0.20µm 必报 pad_too_small ∧ 挪进邻引脚 y 带必报 pins_too_close",
          k1 == ["pad_too_small"] and k2 == ["pins_too_close"],
          "探针① %s · 探针② %s（干净几何 %s）"
          % (k1, k2, "无违规" if lg["ok"] else "有违规"))

    # ── B1 DRC 归零（对比 E36 式 L 路由基线）─────────────────────────
    base = PN.route_baseline(nl, pl)
    rt = PN.route_block(nl, pl)
    vb = len(DL.run_drc(base["shapes"])["violations"])
    vr = DL.run_drc(PN.routing_only(rt))["violations"]
    check("B1 DRC 归零：对 E36 式 L 路由基线（同网表同布局）路由 DRC 34 条级 → 0",
          vb >= AN_BASELINE_MIN and len(vr) == 0,
          "基线 %d → 新 %d · 布通 %d 网 · 未布 %d"
          % (vb, len(vr), len(rt["routed"]), rt["n_unrouted"]))

    # ── B2 零残差（路由 + 全量都不许有）────────────────────────────
    vall = DL.run_drc(PN.all_routing(rt))["violations"]
    kinds = sorted({v[0] for v in vr + vall})
    check("B2 零残差：路由 DRC 与全量 DRC 都为 0 ∧ 无短路类（short/min_width）",
          not vr and not vall and not kinds,
          "路由 %d 条 · 全量 %d 条 · 违规类 %s" % (len(vr), len(vall), kinds or "无"))

    # ── B3 容量律有牙（实际用轨数 ≤ T，且 d 是下界）──────────────────
    ch = rt["ch_info"]
    over = {c: v for c, v in ch.items() if v["tracks_used"] > v["t_avail"] or v["d"] > v["tracks_used"]}
    check("B3 容量律：每通道实际用轨数 ≤ T ∧ A2 密度 d ≤ 实际用轨数 ∧ 列失败 0",
          not over and not rt["col_fail"],
          "T=%d · 通道 %s · 越界 %d · 列失败 %s"
          % (rt["t_cap"], {c: (v["d"], v["tracks_used"], v["t_avail"]) for c, v in ch.items()},
             len(over), rt["col_fail"] or "无"))

    # ── B4 连通性 ───────────────────────────────────────────────
    comp = PN.net_components_rt(rt)
    badcomp = {k: v for k, v in comp.items() if v != 1}
    check("B4 连通性：每个被布网恰好 1 个连通分量（层感知：M3/M4 只经 VIA2 相连）",
          not badcomp and len(comp) == len(rt["routed"]),
          "网数 %d（布通 %d）· 断网 %s" % (len(comp), len(rt["routed"]), badcomp or "无"))

    # ── C1 提取成网 ─────────────────────────────────────────────
    nw = SP.extract_network([s for s in rt["shapes_route"] if s.net],
                            design="LDA_PNR_BLOCK", seg_um=0.5, with_coupling=False)
    ok_ext = 0
    for net in sorted(nw["nets"]):
        tot = SP.net_totals(nw["nets"][net])
        if tot["r_metal_ohm"] > 0 and tot["c_gnd_ff"] > 0:
            ok_ext += 1
    check("C1 提取成网：被布网网络 R>0 ∧ C>0（分布式 RC，不是两个标量）",
          ok_ext == len(nw["nets"]) and ok_ext > 0,
          "网络 %d 个 · 合规 %d" % (len(nw["nets"]), ok_ext))

    # ── C2 网格 IR/EM ───────────────────────────────────────────
    g = PG.build_grid(8, 8)
    ir = PG.solve_reduced(g, PG.uniform_loads(g, 2e-3))
    em = PG.em_segments(g, ir, width_um=PN.W)
    check("C2 网格 IR/EM：全域解可求解 ∧ KCL 闭合（<1e-9）∧ EM 裕量如实报",
          ir["kcl_residual"] < 1e-9 and ir["worst_drop_v"] > 0,
          "drop=%.4f mV · KCL=%.1e · J=%.2e A/m²（裕量 %.2f×，ok=%s）"
          % (ir["worst_drop_v"] * 1e3, ir["kcl_residual"], em["j_a_m2"], em["margin_x"], em["ok"]))

    # ── C3 确定性 ───────────────────────────────────────────────
    rt2 = PN.route_block(nl, pl)
    same = ([tuple((s.layer, s.x0, s.y0, s.x1, s.y1, s.net)) for s in rt["shapes"]] ==
            [tuple((s.layer, s.x0, s.y0, s.x1, s.y1, s.net)) for s in rt2["shapes"]])
    check("C3 确定性：两次路由的几何逐位一致", same,
          "shapes %d vs %d" % (len(rt["shapes"]), len(rt2["shapes"])))

    # ── B0 耗时 ────────────────────────────────────────────────
    dt = time.time() - t0
    check("B0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.9f" % dt)

    print("  [归零靠三件事] ① 引脚 240×240 pad 落在库级列网格(120/480/840nm)"
          " ② trunk 着色改用「引脚 ∪ 列」真实跨度（旧版按引脚跨度 ⇒ 同轨短接）"
          " ③ 通道数==行数 + 单元间距 1.44=4×0.36 ⇒ 跳线长度归零")
    print("  [成本] 单元面积不变（INV 0.769 / NAND2 1.470 µm²），但单元间距 0.36→0.46µm、"
          "每行多一条通道 ⇒ die %.2f×%.2f µm" % (pl["die_w_um"], pl["die_h_um"]))
    print("  [诚实边界] %s" % "；".join(PN.DPNR_DISCLOSURE["limits"][:3]))
    print("-" * 78)
    print("E45 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("E45 有红色：见上方 [FAIL] 行")
        return 1
    print("E45 全绿 · 引脚可接入化收口：路由 DRC **34 → 0** · 全量 DRC 0 · 布通 %d/%d · "
          "每网 1 分量 · 提取成网 · 网格 IR（**零 DRC 只对本用例成立，非全 IP**）"
          % (len(rt["routed"]), len(rt["routed"]) + rt["n_unrouted"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
