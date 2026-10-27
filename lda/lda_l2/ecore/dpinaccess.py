# -*- coding: utf-8 -*-
"""E38d · **细引脚接入逃逸 + 现实线距联调 + 容量结论**（`lda/lda_l2/ecore/dpinaccess.py` · D-228）。

══════════════════════════════════════════════════════════════
定位：E38c 把单元面积标定到真实（0.266µm²/tr），布通率 3.8%→9.7%（2 层），残余瓶颈判为
「粗引脚接入」。E38d 补齐两件真实设计的必备条件并**联调**：
1. **细引脚接入逃逸**：细层(M1/M2)可把单元引脚接到半径 r 内的粗网格点（`access_radius`）。
2. **现实线距**：0.36µm（W=0.24，约 250nm 级）→ 0.24µm（≈45nm 级），网格变密、容量变多。
三种真实条件（真实单元面积 + 细引脚接入 + 现实线距）+ 跨单元布线 + 多层，**联调**看布通率。

🔴🔴 本模块是**容量研究**：只报连通性布通率、不产 GDS；R.PITCH 临时改写（try/finally 还原）。

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标
══════════════════════════════════════════════════════════════
- **引脚接入单调**：同配置下 `routability(access_radius 大) ≥ routability(小)`。
- **层数单调**：跨单元布线 `routability(4 层) ≥ routability(2 层)`。
- **线距单调**：更细线距 `routability(0.24) ≥ routability(0.36)`（同配置）。
- **联调 ≥ 单要素**：三要素齐备的布通率 ≥ 仅真实单元面积。
- **诚实断言**：联调布通率仍 < 0.9（容量受限，非 100%）——把负结论钉成机核，防伪绿。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- 引脚接入逃逸**自身不计占用**（细层独立）⇒ 是**乐观上界**（真实细层也有拥塞）。
- 抽象多层（2/4 层），无 M5/M6 真实 GDS；线距是网格参数，非 Foundry track。
- **联调仍只 ~39%** ⇒ 瓶颈已从「引脚接入/线距」迁到**网络密度/布线容量**：1359 网 vs 46µm die，
  要真正可布通需**更大的 die（摊开 ×K，E37 的 ×N 面积）**。这是 E38d 的诚实结论。
"""
from __future__ import annotations

import contextlib

from . import dcell as DC
from . import dplac as PL
from . import ddroute_rr as RR
from .dsynth import Netlist

REAL_AREA_PER_TR = 0.266       # Nangate45 NAND2_X1 量级（同 E38c）
PITCH_SYMBOLIC = 0.36          # 现状线距
PITCH_REAL = 0.24              # 现实线距（≈45nm 级）


@contextlib.contextmanager
def _pitch(p):
    """临时把 ddroute_rr.PITCH 改成 p，退出时还原（try/finally）。"""
    old = RR.PITCH
    RR.PITCH = p
    try:
        yield
    finally:
        RR.PITCH = old


def pin_access_routability(nl: Netlist, area_per_tr: float = REAL_AREA_PER_TR,
                           pitch: float = PITCH_REAL, layers: int = 4,
                           access_radius: int = 4, cell_block_up_to: int = 2,
                           max_expand: int = 200000, rr_rounds: int = 0) -> dict:
    """真实单元面积 + 细引脚接入 + 现实线距 + 跨单元布线 的联调布通率。"""
    real = _real_tech(area_per_tr)
    p = PL.place(nl, tech=real)
    with _pitch(pitch):
        r = RR.route_rr(nl, p, layers=layers, rr_rounds=rr_rounds, max_expand=max_expand,
                        cell_block_up_to=cell_block_up_to, access_radius=access_radius)
    return {"routability": r["routability"], "n_routed": r["n_routed"], "n_nets": r["n_nets"],
            "die_w": p.die_w_um, "die_h": p.die_h_um, "pitch": pitch, "layers": layers,
            "access_radius": access_radius}


def _real_tech(area_per_tr):
    import dataclasses
    return dataclasses.replace(DC.DEFAULT_TECH, area_per_tr_um2=area_per_tr)


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def pinaccess_self_check(verbose: bool = False) -> dict:
    """E38d 自检：接入/层/线距三单调 + 联调≥单要素 + 诚实(仍<90%)。

    为控成本：单调性探针在**符号小网格**上做（快）；联调与「仅真实单元」在真实布局上做（慢）。
    """
    from . import dctrl as C
    problems = []

    b = C.build()
    nl = b["netlist"]
    p_sym = PL.place(nl)                    # 小网格，快

    # ① 引脚接入单调（符号 2 层，全层阻断）
    r0 = RR.route_rr(nl, p_sym, layers=2, rr_rounds=0, access_radius=0)
    r4 = RR.route_rr(nl, p_sym, layers=2, rr_rounds=0, access_radius=4)
    if not (r4["routability"] >= r0["routability"] - 1e-9):
        problems.append(("access_not_monotone", r0["routability"], r4["routability"]))

    # ② 层数单调（符号，跨单元布线 cell_block_up_to=2 + 接入 4）
    l2 = RR.route_rr(nl, p_sym, layers=2, rr_rounds=0, cell_block_up_to=2, access_radius=4)
    l4 = RR.route_rr(nl, p_sym, layers=4, rr_rounds=0, cell_block_up_to=2, access_radius=4)
    if not (l4["routability"] >= l2["routability"] - 1e-9):
        problems.append(("layers_not_monotone", l2["routability"], l4["routability"]))

    # ③ 线距单调（符号，2 层，接入 4）：0.24 细 ≥ 0.36 粗
    with _pitch(PITCH_REAL):
        pf = RR.route_rr(nl, p_sym, layers=2, rr_rounds=0, access_radius=4)
    if not (pf["routability"] >= r4["routability"] - 1e-9):
        problems.append(("pitch_not_monotone", r4["routability"], pf["routability"]))

    # ④ 联调 vs 仅真实单元（真实布局，慢）
    real = _real_tech(REAL_AREA_PER_TR)
    p_real = PL.place(nl, tech=real)
    only_cell = RR.route_rr(nl, p_real, layers=2, rr_rounds=0)             # 仅真实单元面积
    combined = pin_access_routability(nl)                                  # 三要素联调
    if not (combined["routability"] >= only_cell["routability"] - 1e-9):
        problems.append(("combined_below_single", only_cell["routability"], combined["routability"]))

    # ⑤ 诚实断言：联调仍 < 0.9（容量受限，非 100%）
    if not (combined["routability"] < 0.9):
        problems.append(("combined_unexpectedly_high", combined["routability"]))

    if verbose:
        print("  pinaccess: symbol r0=%.1f%% r4=%.1f%% | 2L=%.1f%% 4L=%.1f%% | pitch0.24=%.1f%% | "
              "realOnly(2L)=%.1f%% combined=%.1f%% (%.0f%%/%.0fx%.0f)"
              % (100 * r0["routability"], 100 * r4["routability"],
                 100 * l2["routability"], 100 * l4["routability"], 100 * pf["routability"],
                 100 * only_cell["routability"], 100 * combined["routability"],
                 100 * combined["routability"], combined["die_w"], combined["die_h"]))
    return {
        "ok": not problems, "problems": problems,
        "access_r0": r0["routability"], "access_r4": r4["routability"],
        "layers_2l": l2["routability"], "layers_4l": l4["routability"],
        "pitch_real": pf["routability"],
        "real_only_2l": only_cell["routability"],
        "combined": combined["routability"],
        "die_w": combined["die_w"], "die_h": combined["die_h"],
    }


DPINACCESS_DISCLOSURE = {
    "route": "E38d · 细引脚接入逃逸 + 现实线距联调 + 容量结论（D-228）",
    "analysis": "access_radius(细层逃逸到半径 r 内粗网格点) + 现实线距(0.24µm) + 真实单元面积(0.266) "
                "+ 跨单元布线 + 多层 联调；R.PITCH 临时改写 try/finally 还原",
    "golden": "引脚接入单调(r↑不劣) · 层数单调(4L≥2L) · 线距单调(细≥粗) · 联调≥仅真实单元 · 诚实(联调<90%)",
    "not_included": "引脚逃逸不计占用(乐观上界) · 抽象多层无真实 GDS · 线距是网格参数非 PDK track",
    "e38d_note": "三要素齐备联调布通率 ~38.7%（vs 仅真实单元 2 层 9.7%、符号 3.8%），**仍 <100%** —— "
                 "瓶颈已从「引脚接入/线距」迁到**网络密度/布线容量**（1359 网 vs 46µm die）。要真正可布通"
                 "需**更大的 die（摊开 ×K，E37 的 ×N 面积）**；真实三要素下所需 K 应远小于 E37 符号密度下的 ×14.6。",
    "claimable": False,
}
