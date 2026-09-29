"""超导 N 比特阵列 全闭环 demo（D-135 · S3 · 吃狗粮）。

产出：lda_schip_s3.gds（真 GDSII）/ .svg（版图预览）/ .report.json（物理 + DRC + LVS
签核报告）。闭环判定 = 物理 + 几何 DRC + 几何 LVS 全 ACCEPT。

默认阵列：2×2（4 qubit · 4 最近邻耦合器）。可用环境变量覆盖 rows/cols：
  ROWS=3 COLS=3 python lda_schip_s3.py
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.join(_HERE, "..") not in sys.path:
    sys.path.insert(0, os.path.join(_HERE, ".."))

from lda_qeda import sc_array as S3                                 # noqa: E402


def main() -> int:
    rows = int(os.environ.get("ROWS", "2"))
    cols = int(os.environ.get("COLS", "2"))
    params = {"rows": rows, "cols": cols}

    print(f"═══ 超导 N 比特阵列 全闭环（D-135 · S3）· {rows}×{cols} 阵列 ═══")

    # —— 几何 ——
    elems = S3.array_cell(params)
    gds_path = os.path.join(_HERE, "lda_schip_s3.gds")
    svg_path = os.path.join(_HERE, "lda_schip_s3.svg")
    gds_bytes = S3.array_gds(params, gds_path)
    svg = S3.array_svg_preview(params, width=560)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)

    # —— 签核 ——
    drc = S3.run_sc_array_drc(elems)
    lvs = S3.sc_array_lvs_signoff(elems)
    phys = S3.array_physics(params)

    closed = (drc["verdict"] == "ACCEPT"
              and lvs["verdict"] == "ACCEPT"
              and phys["verdict"] == "ACCEPT")

    report = {
        "module": "D-135 · 超导 N 比特阵列 P&R + 规模 DRC/LVS + 逐边物理（S3）",
        "topology": {"rows": rows, "cols": cols, "n_qubits": rows * cols,
                     "n_edges_expected": rows * (cols - 1) + cols * (rows - 1)},
        "geometry": {"n_elements": len(elems)},
        "drc": {"verdict": drc["verdict"], "n_rules": drc["n_rules"],
                "violations": drc["violations"]},
        "lvs": {"verdict": lvs["verdict"], "netlist": lvs["netlist"],
                "issues": lvs["issues"]},
        "physics": {"verdict": phys["verdict"], "n_qubits": phys["n_qubits"],
                    "n_edges": phys["n_edges"],
                    "min_relJ": phys["min_relJ"], "max_relJ": phys["max_relJ"],
                    "min_abs_g_CR_mhz": phys["min_abs_g_CR_mhz"],
                    "max_abs_g_CR_mhz": phys["max_abs_g_CR_mhz"],
                    "all_j_double_validated": phys["all_j_double_validated"],
                    "all_cr_ok": phys["all_cr_ok"]},
        "closed_loop": closed,
        "red_line": S3.RED_LINE_DISCLOSURE,
    }
    rep_path = os.path.join(_HERE, "lda_schip_s3.report.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"  GDS : {gds_path} ({len(gds_bytes)} B)")
    print(f"  SVG : {svg_path}")
    print(f"  JSON: {rep_path}")
    print(f"  DRC : {drc['verdict']}  LVS : {lvs['verdict']}  "
          f"PHYS: {phys['verdict']}")
    print(f"  阵列: {rows}×{cols} = {rows*cols} qubit · "
          f"{report['topology']['n_edges_expected']} 耦合边 · "
          f"逐边 maxRelJ={phys['max_relJ']:.2%} · "
          f"max|g_CR|={phys['max_abs_g_CR_mhz']:.3f} MHz")
    print(f"  闭环判定: {'✅ PASS' if closed else '❌ FAIL'}")
    return 0 if closed else 1


if __name__ == "__main__":
    sys.exit(main())
