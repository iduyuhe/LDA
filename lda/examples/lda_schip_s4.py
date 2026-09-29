"""超导征程 S4 全闭环 demo（D-136 · 读出/控制线路 + 串扰/损耗预算 · 吃狗粮）。

产出：lda_schip_s4.gds（真 GDSII）/ .svg（版图预览）/ .report.json（物理 + DRC + LVS
签核报告）。闭环判定 = 几何 DRC + 几何 LVS + 物理（串扰+损耗）全 ACCEPT。

默认阵列：2×2（4 qubit · 4 读出 · 4 控制 · 2 行馈线 · 4 最近邻耦合）。可用环境变量覆盖
rows/cols：
  ROWS=3 COLS=3 python lda_schip_s4.py
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.join(_HERE, "..") not in sys.path:
    sys.path.insert(0, os.path.join(_HERE, ".."))

from lda_qeda import sc_readout as S4                                 # noqa: E402


def main() -> int:
    rows = int(os.environ.get("ROWS", "2"))
    cols = int(os.environ.get("COLS", "2"))
    params = {"rows": rows, "cols": cols}

    print(f"═══ 超导征程 S4 全闭环（D-136）· {rows}×{cols} 阵列 + 读出/控制 + 预算 ═══")

    # —— 几何 ——
    elems = S4.readout_array_cell(params)
    gds_path = os.path.join(_HERE, "lda_schip_s4.gds")
    svg_path = os.path.join(_HERE, "lda_schip_s4.svg")
    gds_bytes = S4.readout_gds(params, gds_path)
    svg = S4.readout_svg_preview(params, width=560)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)

    # —— 签核 ——
    drc = S4.run_readout_drc(elems)
    lvs = S4.readout_lvs_signoff(elems)
    phys = S4.readout_physics(params)

    closed = (drc["verdict"] == "ACCEPT"
              and lvs["verdict"] == "ACCEPT"
              and phys["verdict"] == "ACCEPT")

    xt = phys["crosstalk"]
    lb = phys["loss"]
    report = {
        "module": "D-136 · 超导征程 S4 读出/控制线路 + 串扰/损耗预算",
        "topology": {"rows": rows, "cols": cols, "n_qubits": rows * cols,
                     "n_edges_expected": rows * (cols - 1) + cols * (rows - 1)},
        "geometry": {"n_elements": len(elems),
                     "nets": lvs["netlist"]},
        "drc": {"verdict": drc["verdict"], "n_rules": drc["n_rules"],
                "violations": drc["violations"]},
        "lvs": {"verdict": lvs["verdict"], "netlist": lvs["netlist"],
                "issues": lvs["issues"]},
        "physics": {
            "verdict": phys["verdict"],
            "n_qubits": xt["n_qubits"], "n_pairs": xt["n_pairs"],
            "max_stray_zz_mhz": xt["max_stray_zz_mhz"],
            "zz_stray_limit_mhz": xt["zz_stray_limit_mhz"],
            "max_control_xtalk": xt["max_control_xtalk"],
            "control_xtalk_limit": xt["control_xtalk_limit"],
            "min_t1_total_us": lb["min_t1_total_us"],
            "t1_target_us": lb["t1_target_us"],
        },
        "closed_loop": closed,
        "red_line": S4.RED_LINE_DISCLOSURE,
    }
    rep_path = os.path.join(_HERE, "lda_schip_s4.report.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"  GDS : {gds_path} ({len(gds_bytes)} B)")
    print(f"  SVG : {svg_path}")
    print(f"  JSON: {rep_path}")
    print(f"  DRC : {drc['verdict']}  LVS : {lvs['verdict']}  "
          f"PHYS: {phys['verdict']}")
    print(f"  阵列: {rows}×{cols} = {rows*cols} qubit · "
          f"{report['topology']['n_edges_expected']} 耦合边")
    print(f"  串扰: max_stray_zz={xt['max_stray_zz_mhz']:.3f}MHz "
          f"(≤{xt['zz_stray_limit_mhz']}) · max_xt={xt['max_control_xtalk']:.4f} "
          f"(≤{xt['control_xtalk_limit']})")
    print(f"  损耗: min_t1_total={lb['min_t1_total_us']:.2f}µs "
          f"(≥{lb['t1_target_us']}µs)")
    print(f"  闭环判定: {'✅ PASS' if closed else '❌ FAIL'}")
    return 0 if closed else 1


if __name__ == "__main__":
    sys.exit(main())
