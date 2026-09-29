"""超导征程 S5 全闭环**批量** demo（P0: D-137 路由 + D-142 频率 + D-143 规模；
P1: D-138 heavy-hex + D-139 可调耦合器 + D-140 读出 mux + D-141 控制多线 + D-144 阵列损耗；
第三波完善: D-145 统一拓扑 DRC/LVS 框架 · 吃狗粮）。

批量签核两类配置族：
  • **grid 族**（LDA 原生方阵）：每档跑 路由 DRC/LVS（G1）+ 频率规划（G6）+ 读出 mux 规划/DRC/LVS（G4）
    + 控制多线 DRC/LVS/串扰（G5）+ 阵列损耗（G8）；产出 .gds/.svg。
  • **heavy-hex 族**（对标 IBM）：每档跑 拓扑度统计 + DRC/LVS + 逐边物理（G2）；产出 .gds/.svg。
  • **单元**：可调耦合器（G3）DRC/LVS/物理；产出 .gds/.svg。
  • **统一拓扑框架族**（D-145）：方阵实例走与 heavy-hex **同一份** DRC/LVS/物理引擎（度上限
    自声明 4 vs 3）；产出 .gds/.svg。

汇总 lda_schip_s5.report.json。闭环判定 = 该档全部子签核 ACCEPT。
默认档位：grid="2x2,7x8,13x13" · hex="3x3,4x5"；可用环境变量覆盖：
  S5_TIERS="2x2,7x8,13x13,21x21" S5_HEX_TIERS="3x3,5x6" S5_TFG_TIERS="3x3,7x8" python lda_schip_s5.py
"""
from __future__ import annotations

import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.join(_HERE, "..") not in sys.path:
    sys.path.insert(0, os.path.join(_HERE, ".."))

from lda_qeda import sc_routing as SR                                 # noqa: E402
from lda_qeda import sc_freq_alloc as FA                              # noqa: E402
from lda_qeda import sc_readout_mux as MX                             # noqa: E402
from lda_qeda import sc_control as CT                                 # noqa: E402
from lda_qeda import sc_topology as TP                                # noqa: E402
from lda_qeda import sc_topology_core as TC                           # noqa: E402
from lda_qeda import sc_coupler as SC                                 # noqa: E402


def _parse_tiers(env: str):
    out = []
    for tok in env.split(","):
        tok = tok.strip().lower()
        if "x" in tok:
            r, c = tok.split("x")
            out.append((int(r), int(c)))
    return out


def _write(svg_path: str, svg: str, gds_path: str, gds: bytes):
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return len(gds)


def _grid_one(rows: int, cols: int) -> dict:
    params = {"rows": rows, "cols": cols}
    tag = f"{rows}x{cols}"
    elems = SR.routed_array_cell(params)
    gds_path = os.path.join(_HERE, f"lda_schip_s5_{tag}.gds")
    svg_path = os.path.join(_HERE, f"lda_schip_s5_{tag}.svg")
    gds_bytes = SR.routed_gds(params, gds_path)
    _write(svg_path, SR.routed_svg_preview(params, width=680), gds_path, gds_bytes)

    drc = SR.run_routing_drc(elems)
    lvs = SR.routed_array_lvs(elems)
    fpl = FA.plan(params)
    lb = SR.S4.array_loss_budget(params)
    cap = SR.routing_capacity(params)

    mux_cell = MX.mux_array_cell(params)
    mux_pl = MX.mux_plan(params)
    mdr = MX.run_mux_drc(mux_cell, mux_pl)
    mlv = MX.mux_lvs(mux_cell, mux_pl)
    mph = MX.mux_physics(params)

    ctrl = CT.control_array_cell(params)
    cdr = CT.run_control_drc(ctrl)
    clv = CT.control_lvs(ctrl)
    cxt = CT.line_xtalk_budget(params)

    closed = all(x["verdict"] == "ACCEPT" for x in (drc, lvs, fpl, lb, mdr, mlv, mph, cdr, clv, cxt))
    return {
        "family": "grid", "tier": tag, "rows": rows, "cols": cols,
        "n_qubits": rows * cols, "n_elements": len(elems),
        "gds_bytes": len(gds_bytes),
        "drc": {"verdict": drc["verdict"], "n_rules": drc["n_rules"]},
        "lvs": {"verdict": lvs["verdict"], "n_issues": len(lvs["issues"])},
        "freq": {"verdict": fpl["verdict"], "mode": fpl["mode"],
                 "max_stray_zz_mhz": fpl["max_stray_zz_mhz"]},
        "loss": {"verdict": lb["verdict"], "min_t1_total_us": lb["min_t1_total_us"],
                 "yield": lb["yield"], "pkg_mode_ok": lb["pkg_mode_ok"]},
        "mux": {"drc": mdr["verdict"], "lvs": mlv["verdict"], "phys": mph["verdict"],
                "tone_spacing_mhz": mph["plan"]["min_tone_spacing_mhz"]},
        "control": {"drc": cdr["verdict"], "lvs": clv["verdict"], "xtalk": cxt["verdict"],
                    "max_intra_X": cxt["max_intra_X"]},
        "routing_capacity": {"n_signals": cap["n_signals"],
                             "pitch_y_eff_um": cap["pitch_y_eff_um"]},
        "closed_loop": closed,
    }


def _hex_one(rows: int, cols: int) -> dict:
    params = {"rows": rows, "cols": cols}
    tag = f"hh{rows}x{cols}"
    g = TP.heavy_hex_graph(rows, cols)
    cell = TP.heavy_hex_cell(params)
    gds_path = os.path.join(_HERE, f"lda_schip_s5_{tag}.gds")
    svg_path = os.path.join(_HERE, f"lda_schip_s5_{tag}.svg")
    gds_bytes = TP.heavy_hex_gds(params, gds_path)
    _write(svg_path, TP.heavy_hex_svg_preview(params, width=680), gds_path, gds_bytes)

    deg = TP.heavy_hex_degree_stats(g)
    drc = TP.run_heavyhex_drc(cell, g)
    lvs = TP.heavyhex_lvs(cell, g)
    ph = TP.heavy_hex_physics(params)
    closed = all(x["verdict"] == "ACCEPT" for x in (drc, lvs, ph))
    return {
        "family": "heavy-hex", "tier": tag, "rows": rows, "cols": cols,
        "n_qubits": g["n_qubits"], "n_vertices": g["n_vertices"],
        "n_edge_qubits": g["n_edge_qubits"], "n_couplings": g["n_edges"],
        "max_degree": deg["max_degree"], "no_four_neighbor": deg["no_four_neighbor"],
        "n_elements": len(cell), "gds_bytes": len(gds_bytes),
        "drc": {"verdict": drc["verdict"], "n_rules": drc["n_rules"]},
        "lvs": {"verdict": lvs["verdict"], "n_issues": len(lvs["issues"])},
        "physics": {"verdict": ph["verdict"], "max_J_rel_err": ph["max_J_rel_err"]},
        "closed_loop": closed,
    }


def _topocore_one(rows: int, cols: int) -> dict:
    """统一拓扑框架（D-145）方阵实例：grid_topology → topology_cell → 统一 DRC/LVS/物理。"""
    tag = f"tfg{rows}x{cols}"
    topo = TC.grid_topology(rows, cols)
    cell = TC.topology_cell(topo)
    gds_path = os.path.join(_HERE, f"lda_schip_s5_{tag}.gds")
    svg_path = os.path.join(_HERE, f"lda_schip_s5_{tag}.svg")
    gds_bytes = TC.topology_gds(topo, {}, gds_path)
    _write(svg_path, TC.topology_svg_preview(topo, {}, width=680), gds_path, gds_bytes)
    deg = TC.topology_degree_stats(topo)
    drc = TC.run_topology_drc(cell, topo)
    lvs = TC.topology_lvs(cell, topo)
    ph = TC.topology_physics(topo)
    closed = all(x["verdict"] == "ACCEPT" for x in (drc, lvs, ph))
    return {"family": "topology-core", "tier": tag, "rows": rows, "cols": cols,
            "n_qubits": topo["n_qubits"], "n_couplings": topo["n_couplings"],
            "max_degree": deg["max_degree"],
            "max_degree_limit": topo["max_degree_limit"],
            "n_elements": len(cell), "gds_bytes": len(gds_bytes),
            "drc": {"verdict": drc["verdict"], "n_rules": drc["n_rules"]},
            "lvs": {"verdict": lvs["verdict"], "n_issues": len(lvs["issues"])},
            "physics": {"verdict": ph["verdict"], "max_J_rel_err": ph["max_J_rel_err"]},
            "closed_loop": closed}


def _tunable_one() -> dict:
    tc = SC.tunable_coupler_cell({})
    gds_path = os.path.join(_HERE, "lda_schip_s5_tunable.gds")
    svg_path = os.path.join(_HERE, "lda_schip_s5_tunable.svg")
    gds_bytes = SC.tunable_coupler_gds({}, gds_path)
    _write(svg_path, SC.tunable_coupler_svg_preview({}, width=520), gds_path, gds_bytes)
    drc = SC.run_tunable_drc(tc)
    lvs = SC.tunable_coupler_lvs(tc)
    ph = SC.tunable_coupler_physics({})
    closed = all(x["verdict"] == "ACCEPT" for x in (drc, lvs, ph))
    return {"family": "unit", "tier": "tunable-coupler", "n_elements": len(tc),
            "gds_bytes": len(gds_bytes),
            "drc": {"verdict": drc["verdict"], "n_rules": drc["n_rules"]},
            "lvs": {"verdict": lvs["verdict"], "n_issues": len(lvs["issues"])},
            "physics": {"verdict": ph["verdict"], "J_on_mhz": ph["J_on_mhz"],
                        "J_off_mhz": ph["J_off_mhz"], "off_ratio": ph["off_ratio"]},
            "closed_loop": closed}


def main() -> int:
    grid_tiers = _parse_tiers(os.environ.get("S5_TIERS", "2x2,7x8,13x13"))
    hex_tiers = _parse_tiers(os.environ.get("S5_HEX_TIERS", "3x3,4x5"))
    print("═" * 82)
    print("超导征程 S5 全闭环批量 demo（P0 D-137/142/143 + P1 D-138/139/140/141/144 + D-145 统一拓扑框架）")
    print("═" * 82)

    results = []
    all_closed = True

    print("── 单元：可调耦合器（G3 · D-139）──")
    t0 = time.time()
    ru = _tunable_one()
    all_closed = all_closed and ru["closed_loop"]
    results.append(ru)
    print(f"  {ru['tier']:<16} DRC={ru['drc']['verdict']} LVS={ru['lvs']['verdict']} "
          f"PHYS={ru['physics']['verdict']} · J_on={ru['physics']['J_on_mhz']:.3f}MHz "
          f"off_ratio={ru['physics']['off_ratio']:.1f} · 元素={ru['n_elements']} · "
          f"{time.time() - t0:.2f}s · {'✅' if ru['closed_loop'] else '❌'}")

    print("── grid 族（LDA 方阵）──")
    for (r, c) in grid_tiers:
        t0 = time.time()
        res = _grid_one(r, c)
        all_closed = all_closed and res["closed_loop"]
        results.append(res)
        print(f"  {res['tier']:>7} (N={res['n_qubits']:>4}) · "
              f"DRC={res['drc']['verdict']} LVS={res['lvs']['verdict']} "
              f"FREQ={res['freq']['verdict']}({res['freq']['mode']}) "
              f"LOSS={res['loss']['verdict']} MUX={res['mux']['phys']} "
              f"CTRL={res['control']['xtalk']} · 元素={res['n_elements']} · "
              f"{time.time() - t0:.2f}s · {'✅' if res['closed_loop'] else '❌'}")

    print("── heavy-hex 族（对标 IBM）──")
    for (r, c) in hex_tiers:
        t0 = time.time()
        res = _hex_one(r, c)
        all_closed = all_closed and res["closed_loop"]
        results.append(res)
        print(f"  {res['tier']:>7} (N={res['n_qubits']:>4}) · "
              f"顶点={res['n_vertices']} 边{res['n_edge_qubits']} · maxDeg={res['max_degree']} · "
              f"DRC={res['drc']['verdict']} LVS={res['lvs']['verdict']} "
              f"PHYS={res['physics']['verdict']} · 元素={res['n_elements']} · "
              f"{time.time() - t0:.2f}s · {'✅' if res['closed_loop'] else '❌'}")

    print("── 统一拓扑框架（D-145 · 方阵实例，与 heavy-hex 共用引擎）──")
    for (r, c) in _parse_tiers(os.environ.get("S5_TFG_TIERS", "3x3,7x8")):
        t0 = time.time()
        res = _topocore_one(r, c)
        all_closed = all_closed and res["closed_loop"]
        results.append(res)
        print(f"  {res['tier']:>7} (N={res['n_qubits']:>4}) · 耦合={res['n_couplings']} · "
              f"maxDeg={res['max_degree']}/{res['max_degree_limit']} · "
              f"DRC={res['drc']['verdict']} LVS={res['lvs']['verdict']} "
              f"PHYS={res['physics']['verdict']} · 元素={res['n_elements']} · "
              f"{time.time() - t0:.2f}s · {'✅' if res['closed_loop'] else '❌'}")

    report = {
        "module": "S5 全闭环批量签核（P0 D-137/142/143 + P1 D-138/139/140/141/144 + D-145 统一拓扑框架）",
        "configs": results,
        "all_closed_loop": all_closed,
        "red_line": {"routing": SR.RED_LINE_DISCLOSURE,
                     "freq_alloc": FA.RED_LINE_DISCLOSURE,
                     "mux": MX.RED_LINE_DISCLOSURE,
                     "control": CT.RED_LINE_DISCLOSURE,
                     "topology": TP.RED_LINE_DISCLOSURE,
                     "topology_core": TC.RED_LINE_DISCLOSURE},
    }
    rep_path = os.path.join(_HERE, "lda_schip_s5.report.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  汇总报告: {rep_path}")
    print(f"  批量闭环判定: {'✅ PASS' if all_closed else '❌ FAIL'}")
    return 0 if all_closed else 1


if __name__ == "__main__":
    sys.exit(main())
