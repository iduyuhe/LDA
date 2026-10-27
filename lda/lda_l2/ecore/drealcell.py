# -*- coding: utf-8 -*-
"""E38c · **真实标准单元面积标定 + 可布通性重测**（`lda/lda_l2/ecore/drealcell.py` · D-227）。

══════════════════════════════════════════════════════════════
定位：E38a/E38b 已证「符号级超窄单元（area_per_tr=0.040µm²/管 ⇒ 单元宽 ~0.075µm、223 单元/行）」
是布通率仅 ~3-4% 的根因。E38c 把单元面积**标定到一个公开可引用的真实值**，重摆重测，量化
「换成真实单元面积到底能救多少」。

🔴 **本模块不改 `dcell.DEFAULT_TECH`**（不动 E34~E38 既有锚），而是**另建一个 realistic Tech**
   （`dataclasses.replace(DEFAULT_TECH, area_per_tr_um2=0.266)`）传给 `dplac.place` ⇒ 只影响 E38c
   的重测，生产链与既有门禁零影响。

══════════════════════════════════════════════════════════════
🔴🔴 面积标定的公开引用（可引用、非拟合）
══════════════════════════════════════════════════════════════
Nangate45 Open Cell Library（开源 45nm 标准单元库）：NAND2_X1 单元面积 ≈ **1.064 µm²**，NAND2 逻辑
= **4 个晶体管**（2 PMOS 并联 + 2 NMOS 串联）⇒ **≈ 0.266 µm²/管**。相较 LDA 符号值 0.040 是 **6.65×**。
（这是一个公开库的量级标定，不是 Foundry PDK 精确值；作**量级参考**，见诚实边界。）

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标
══════════════════════════════════════════════════════════════
- **面积守恒**：`Σ(w·h) ≡ Σ n_tr · area_per_tr`（逐位；换 tech 后仍守恒 ⇒ 标定真的进了几何）。
- **单元变稀**：realistic Tech 下 `cells/row` 显著 < 符号值（≈89 vs 223）。
- **布通率提升**：`routability(real) > routability(symbolic)`（同层数同规则，真实面积不应更差）。
- **层数单调**：route-over-cell 下 `routability(4 层) ≥ routability(2 层)`。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- 0.266µm²/管是**公开库量级参考**（Nangate45），非 Foundry PDK 精确值；`area_per_tr` 本就不作绝对锚。
- 仍用抽象多层网格（2/4 层）；`cell_block_up_to=2` 表示「M5/M6 跨单元布线」（真实高层金属行为），
  但**仍无细间距 M1/M2 引脚接入层** —— 残余瓶颈正是粗引脚接入。
- 真实面积只把布通率抬 2.6×（3.8%→9.7% @2 层），**开不出 100% 可布通布局**；完整可布通需
  「真实单元面积 + 跨单元布线 + 细引脚接入」三者齐备（后者未建模）。
"""
from __future__ import annotations

import dataclasses

from . import dcell as DC
from . import dplac as PL
from . import ddroute_rr as RR
from .dsynth import Netlist

# 符号值（现状）与真实参考值
AREA_PER_TR_SYMBOLIC = DC.DEFAULT_TECH.area_per_tr_um2      # 0.040
REAL_AREA_PER_TR_45 = 0.266                                  # Nangate45 NAND2_X1 1.064µm² / 4tr
REF_NANGATE45 = ("Nangate45 Open Cell Library: NAND2_X1 ≈ 1.064 µm² / 4 tr ≈ 0.266 µm²/tr "
                 "（开源 45nm 量级参考，非 Foundry PDK）")


def real_tech(area_per_tr: float = REAL_AREA_PER_TR_45) -> DC.Tech:
    """构造 realistic Tech（只改 area_per_tr，其余沿用 DEFAULT_TECH）。"""
    return dataclasses.replace(DC.DEFAULT_TECH, area_per_tr_um2=area_per_tr)


def realistic_place(nl: Netlist, area_per_tr: float = REAL_AREA_PER_TR_45):
    """用 realistic Tech 重新摆放。返回 (Placement, Tech)。"""
    t = real_tech(area_per_tr)
    return PL.place(nl, tech=t), t


def placed_area_um2(p: PL.Placement) -> float:
    return sum(w * h for (_x, _y, w, h) in p.cell_xywh.values())


def expected_area_um2(nl: Netlist, area_per_tr: float) -> float:
    """Σ n_tr · area_per_tr —— 面积守恒的源端。"""
    return sum(DC.CELLS[g.cell].n_tr for g in nl.gates) * area_per_tr


def cells_per_row(p: PL.Placement) -> float:
    return len(p.cell_xywh) / float(p.rows) if p.rows else 0.0


def realistic_routability(nl: Netlist, area_per_tr: float = REAL_AREA_PER_TR_45,
                          layers: int = 2, cell_block_up_to: int = 2,
                          rr_rounds: int = 0, max_expand: int = 120000) -> dict:
    """真实面积重摆 + 抽象多层布线（默认跨单元布线 cell_block_up_to=2）。"""
    p, t = realistic_place(nl, area_per_tr)
    r = RR.route_rr(nl, p, layers=layers, rr_rounds=rr_rounds,
                    max_expand=max_expand, cell_block_up_to=cell_block_up_to)
    return {"placement": p, "routability": r["routability"], "n_routed": r["n_routed"],
            "n_nets": r["n_nets"], "die_w": p.die_w_um, "die_h": p.die_h_um,
            "rows": p.rows, "cells_per_row": cells_per_row(p),
            "placed_area": placed_area_um2(p)}


# ---------------------------------------------------------------------------
# 自检（含对照组）
# ---------------------------------------------------------------------------
def realcell_self_check(verbose: bool = False) -> dict:
    """E38c 自检：面积守恒（换 tech）+ 单元变稀 + 布通率提升 + 层数单调。

    - ① 面积守恒：realistic 摆放 `Σ(w·h) ≡ Σ n_tr·0.266`（逐位）；符号 tech 同式（对照组）。
    - ② 单元变稀：realistic cells/row < 符号值的一半。
    - ③ 布通率提升：realistic(2 层) > 符号(2 层)。
    - ④ 层数单调：realistic route-over-cell(4 层) ≥ (2 层)。
    - 探针：用错误 area_per_tr(0.040) 摆放 ⇒ 面积守恒式必须随之变（证明标定非硬编码）。
    """
    from . import dctrl as C
    problems = []

    b = C.build()
    nl = b["netlist"]
    p_sym = PL.place(nl)                    # 符号
    p_real, _t = realistic_place(nl)        # 真实

    # ① 面积守恒（真实 & 符号各一次）
    exp_r = expected_area_um2(nl, REAL_AREA_PER_TR_45)
    if abs(placed_area_um2(p_real) - exp_r) > 1e-6:
        problems.append(("area_conservation_real", placed_area_um2(p_real), exp_r))
    exp_s = expected_area_um2(nl, AREA_PER_TR_SYMBOLIC)
    if abs(placed_area_um2(p_sym) - exp_s) > 1e-6:
        problems.append(("area_conservation_sym", placed_area_um2(p_sym), exp_s))

    # ② 单元变稀
    cpr_sym = cells_per_row(p_sym)
    cpr_real = cells_per_row(p_real)
    if not (cpr_real < cpr_sym * 0.5):
        problems.append(("not_sparser", cpr_real, cpr_sym))

    # ③ 布通率提升（2 层，同规则）
    r_sym = RR.route_rr(nl, p_sym, layers=2, rr_rounds=0)
    r_real2 = realistic_routability(nl, layers=2, cell_block_up_to=2)
    if not (r_real2["routability"] > r_sym["routability"]):
        problems.append(("routability_not_improved", r_sym["routability"], r_real2["routability"]))

    # ④ 层数单调（realistic, route-over-cell）
    r_real4 = realistic_routability(nl, layers=4, cell_block_up_to=2)
    if not (r_real4["routability"] >= r_real2["routability"] - 1e-9):
        problems.append(("layers_not_monotone", r_real2["routability"], r_real4["routability"]))

    # 探针：错误 area_per_tr 摆放 ⇒ 面积守恒式随之变（非硬编码）
    p_wrong, _ = realistic_place(nl, AREA_PER_TR_SYMBOLIC)
    wrong_matches_real = abs(placed_area_um2(p_wrong) - exp_r) < 1e-6
    if wrong_matches_real:
        problems.append(("probe_area_hardcoded",))

    if verbose:
        print("  realcell: cells/row sym=%.0f real=%.0f | die %.0fx%.0f | "
              "routability sym(2L)=%.1f%% real(2L)=%.1f%% real(4L)=%.1f%% | area %.1f vs %.1f µm²"
              % (cpr_sym, cpr_real, p_real.die_w_um, p_real.die_h_um,
                 100 * r_sym["routability"], 100 * r_real2["routability"],
                 100 * r_real4["routability"], placed_area_um2(p_real), exp_r))
    return {
        "ok": not problems, "problems": problems,
        "cells_per_row_symbolic": cpr_sym, "cells_per_row_realistic": cpr_real,
        "die_w": p_real.die_w_um, "die_h": p_real.die_h_um, "rows": p_real.rows,
        "routability_symbolic_2l": r_sym["routability"],
        "routability_real_2l": r_real2["routability"],
        "routability_real_4l": r_real4["routability"],
        "placed_area": placed_area_um2(p_real), "expected_area": exp_r,
        "area_per_tr_real": REAL_AREA_PER_TR_45,
    }


DREALCELL_DISCLOSURE = {
    "route": "E38c · 真实标准单元面积标定 + 可布通性重测（D-227）",
    "analysis": "area_per_tr 0.040(符号) → 0.266(Nangate45 NAND2_X1 量级参考) ⇒ dplac.place(tech=real) "
                "重摆 → 抽象多层布线(route-over-cell) 重测布通率；不改 DEFAULT_TECH",
    "golden": "面积守恒 Σ(w·h)≡Σn_tr·area_per_tr(逐位) · cells/row 显著下降 · routability(real)>symbolic · "
              "route-over-cell 层数单调(4≥2)",
    "not_included": "0.266 为公开库量级参考(非 PDK 精确) · 抽象多层无 M5/M6 真实 GDS · "
                    "仍无细间距 M1/M2 引脚接入层（残余瓶颈即此）",
    "e38c_note": "真实单元面积把布通率 3.8%→9.7%(2 层, 2.6×)、跨单元布线+4 层→~22%、6 层→~32%；"
                 "**仍开不出 100% 可布通布局** —— 残余瓶颈是**粗引脚接入**(0.36µm 网格无 M1/M2 细接入)，"
                 "真实设计靠细间距 M1/M2 pin access 解决（本模型未建）。故「完全可布通」= 真实单元面积 + "
                 "跨单元布线 + 细引脚接入 三者齐备，缺一不可。这是 E38c 的诚实结论。",
    "claimable": False,
}
