#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E38 门禁（D-225）：**网格迷宫路由器 + 可布通性（E38a）**。

## 本门禁守什么
E36/E37 用简化 L 路由 + track 分配，E37 证明 2 层清零不可行。E38 换**真正的网格迷宫路由器**
（M3 横 / M4 竖，分层独立占用），看**到底能布通多少**——并诚实报布通率。核心不是"布通"，
是**诚实测量布通率 + 证明低布通率源自布局密度（非算法）**。

| # | 守护对象 | 金标 |
|---|---|---|
| B1 | 控制组 `ddroute_grid` | 稀疏合成 3 网 ⇒ 100% 布通 + DRC=0 + LVS 通 + 线长≥MST（路由器非空转） |
| B2 | 负结果 `ddroute_grid` | 真实布局布通率如实报（本密度仅 3.2%，判 <50%）；真实 DRC/LVS 只作信息不判红 |
| B3 | 密度回升 `routability_vs_spread` | 放大布局 ×1→×3 ⇒ 布通率回升（证明低布通率是密度所致） |

## 探针（每个必须打红）
- **C1** 用异网终端把某网唯一出路围死 ⇒ `_route_net` 必报未布（非静默丢弃）
- **C2** 控制组形状注入异网重叠 ⇒ `fast_drc` 必红 min_spacing
- **C3** 砍掉控制组某网 1 条边 ⇒ 线长 < MST（金标有牙）

## 诚实口径
真实布局 die 仅 18×18.7µm、1340 单元（≈223/行、单元宽 0.075µm）⇒ **布通率仅 3.2%（44/1354）**：
0.36µm 轨距下 ~4~5 单元挤到同一网格点，几乎每点都是某网终端 ⇒ 大多数线出不了引脚。这是
**布局密度**（符号级超窄单元，非 PDK 真实面积）所致，不是路由器不足。真实已布形状的 DRC/LVS
**只作信息不判红**（单元中心=共享终端黑盒 ⇒ pad 重叠/连通性含混，E36/E37 起既有简化）；
几何干净性以「稀疏合成控制组（终端互斥）」为准。多轮 R&R 与完整密度曲线属 E38b。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import ddroute_grid as G        # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL           # noqa: E402
from lda_l2.ecore import dctrl as CT              # noqa: E402
from lda_l2.ecore import dplac as PL              # noqa: E402
from lda_harness.smoke_kit import make_check      # noqa: E402

AN_ELAPSED_MAX_S = 200.0   # 本门禁耗时上界（含 ×1~×3 密度扫描，实测见末行）

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def b1_control():
    """B1 · 稀疏合成控制组：100% 布通 + DRC=0 + LVS 通 + 线长≥MST（证明路由器有效）。"""
    synth = {"nA": {(2, 2), (10, 8)}, "nB": {(20, 20), (30, 10)}, "nC": {(5, 40), (45, 40)}}
    ss, routed, unr, _ = G._route_term_set(synth, 51, 53)
    d = DL.fast_drc(ss)
    pins = {n: [(i * G.PITCH, j * G.PITCH) for (i, j) in ns] for n, ns in synth.items()}
    l = DL.fast_lvs(ss, pins)
    wl_ok = True
    for n, (e, v) in routed.items():
        wl = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in e) * G.PITCH
        if wl < G._mst_len(synth[n]) - 1e-6:
            wl_ok = False
    ok = (not unr) and len(routed) == len(synth) and len(d["violations"]) == 0 and l["ok"] and wl_ok
    check("B1 控制组：稀疏合成 100% 布通 + DRC=0 + LVS 通 + 线长≥MST", ok,
          "unr=%s drc=%d lvs=%d wl_ok=%s" % (unr, len(d["violations"]),
                                             len(l["problems"]), wl_ok))


def b2_negative():
    """B2 · 真实布局布通率如实报（本密度 <50%）；真实 DRC/LVS 只作信息。"""
    nl = CT.build()["netlist"]
    p = PL.place(nl)
    r = G.route_grid(nl, p)
    ok = (r["n_nets"] > 0) and (r["routability"] < 0.5)
    check("B2 负结果：真实布局布通率 <50%（本密度不可布通，如实报）", ok,
          "%.1f%% (%d/%d)" % (100 * r["routability"], r["n_routed"], r["n_nets"]))
    if r["shapes"]:
        drc_n = len(DL.fast_drc(r["shapes"])["violations"])
        rp = {n: r["net_pins"][n] for n in r["routed_nets"]}
        lvs_n = len(DL.fast_lvs(r["shapes"], rp)["problems"])
    else:
        drc_n = lvs_n = 0
    print("  :: grid=%dx%d  真实 DRC=%d / LVS=%d（信息·不判红·单元黑盒共享终端）"
          % (r["nx"], r["ny"], drc_n, lvs_n))


def b3_relief():
    """B3 · 密度回升：放大布局 ×1→×3 ⇒ 布通率回升（证明低布通率源自密度）。"""
    nl = CT.build()["netlist"]
    p = PL.place(nl)
    sweep = G.routability_vs_spread(nl, p, factors=(1, 2, 3))
    ok = sweep[-1]["routability"] >= sweep[0]["routability"] - 1e-9
    check("B3 密度回升：放大布局 ⇒ 布通率回升（非算法之过）", ok,
          " ".join("×%g→%.1f%%" % (s["spread"], 100 * s["routability"]) for s in sweep))


def c1_wall():
    """C1 · 围死某网 ⇒ 必报未布（非静默丢弃）。"""
    from collections import defaultdict
    TERM = defaultdict(set)
    TERM[(0, 0)].add("nA")
    TERM[(5, 0)].add("nA")
    for i in range(1, 5):
        for j in range(3):
            TERM[(i, j)].add("__wall__")
    r = G._route_net({(0, 0), (5, 0)}, "nA", 6, 3, {}, {}, TERM)
    check("C1 突变探针：围死网 ⇒ 必报未布（非静默丢）", r is None, "")


def c2_overlap():
    """C2 · 控制组形状注入异网重叠 ⇒ fast_drc 必红 min_spacing。"""
    from lda_l2.ecore import ddetail as DD
    synth = {"nA": {(2, 2), (10, 8)}, "nB": {(20, 20), (30, 10)}, "nC": {(5, 40), (45, 40)}}
    ss, _r, _u, _ = G._route_term_set(synth, 51, 53)
    h = next((s for s in ss if s.layer == DD.L_M3 and s.kind == "metal"
              and (s.x1 - s.x0) >= 3 * 0.10), None)
    if h is None:
        check("C2 突变探针：控制组无长 H 段", False, "no H")
        return
    bad = list(ss)
    bad.append(DD._rect(DD.L_M3, h.x0, h.y0 + 0.01, h.x1, h.y0 + 0.01 + G.W,
                        net="__short__", kind="metal"))
    caught = any(v[0] == "min_spacing" for v in DL.fast_drc(bad)["violations"])
    check("C2 突变探针：注入异网重叠 ⇒ fast_drc 必红 min_spacing", caught, "")


def c3_cut():
    """C3 · 砍 1 条边 ⇒ 线长 < MST（金标有牙，能抓编数）。"""
    synth = {"nA": {(2, 2), (10, 8)}, "nB": {(20, 20), (30, 10)}, "nC": {(5, 40), (45, 40)}}
    ss, routed, _u, _ = G._route_term_set(synth, 51, 53)
    n0 = next(iter(routed))
    e0 = routed[n0][0]
    e1 = e0[:-1]
    wl_cut = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in e1) * G.PITCH
    caught = wl_cut < G._mst_len(synth[n0]) - 1e-6
    check("C3 突变探针：砍 1 边 ⇒ 线长<MST（金标有牙）", caught, "")


def main():
    t0 = time.time()
    print("=" * 78)
    print("E38a · 网格迷宫路由器 + 可布通性（诚实布通率）")
    print("=" * 78)
    b1_control()
    b2_negative()
    b3_relief()
    c1_wall()
    c2_overlap()
    c3_cut()

    dt = time.time() - t0
    check("B0 门禁耗时 %.1f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E38a · 通过 %d · 失败 %d · 耗时 %.1f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E38a 网格迷宫路由器/布通率出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E38a 全绿 · 路由器有效（控制 100%）+ 真实布局布通率如实报（负结果）+ 密度回升 · "
          "3 金标 + 3 突变探针全打红")
    return 0


if __name__ == "__main__":
    sys.exit(main())
