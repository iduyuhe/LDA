"""LDA · D-19 一键设计流水线（IR → 版图 → DRC → 整改 → 仿真 → 验收）。

把已交付的版图线串成**产品化设计交付流水线**：输入设计意图（器件 kind +
目标/参数），自动完成：

  1. 逆设计（可选）：环形 target_fsr → 半径 R（D-11 RingBandAgent）
  2. 版图生成：geometry_desc → GDSII + SVG（D-14）
  3. DRC 自查：可制造性规则检查（D-15）
  4. 自动整改：DRC violation → agent 调参直到可制造（D-18）
  5. 仿真验收：版图波导 FDTD neff → slab ORACLE（D-16）
  6. 设计包落盘：GDS + SVG + JSON 报告

CLI：
  python -m lda_agent.design_pipeline RingResonator --target_fsr 9.15 --out reports/ring
  python -m lda_agent.design_pipeline DirectionalCoupler --gap 0.1   # 演示自动整改

全链路死代码判定（物理锚验收 + DRC 规则），LLM 不进判决路径。
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_l2.drc import drc_check_device
from lda_l2.gds_export import (gds_library, geometry_desc, layout_elements,
                               svg_preview, write_gds)
from lda_l2.layout_sim import simulate_layout

_SUPPORTED = ("Waveguide", "RingResonator", "DirectionalCoupler",
              "SymmetricYBranch")


def _default_params(kind: str) -> Dict[str, float]:
    from lda_l2.device_library import get_default_library
    dev = get_default_library().get(kind)
    return {k: (lo + hi) / 2.0 for k, (lo, hi) in dev.params_schema.items()}


def _inverse_design(kind: str, target_fsr_nm: float) -> Dict[str, float]:
    """环形目标 FSR → 半径 R（D-11 RingBandAgent 逆设计）。"""
    from lda_agent.ring_loop import RingBandAgent
    intent = {
        "geometry_type": "ring",
        "target_wavelength_um": 1.55,
        "target_metric": "spectrum_match",
        "tolerance_rel": 0.02,
        "max_iterations": 40,
        "extra": {
            "R_um": 10.0, "R_bounds": [8.0, 12.0], "n_g": 4.2,
            "Q": 1.0e4, "kappa": 0.05, "target_fsr_nm": float(target_fsr_nm),
            "wl0_um": 1.55, "target_tol": 0.03, "backend": "numpy",
        },
    }
    rep = RingBandAgent().run(intent)
    if not rep["accepted"]:
        raise RuntimeError(f"环形逆设计未收敛：{rep['verdict']}")
    return {"R": rep["final_R_um"], "wg_width": 0.5}


def run_pipeline(kind: str = "RingResonator",
                 params: Optional[Dict[str, float]] = None,
                 target_fsr_nm: Optional[float] = None,
                 out_dir: Optional[str] = None, out_id: Optional[str] = None,
                 tol_rel: float = 0.02) -> Dict:
    """一键设计流水线：逆设计→版图→DRC→整改→仿真→验收→落盘。"""
    if kind not in _SUPPORTED:
        raise ValueError(f"流水线暂不支持 kind={kind}（支持：{_SUPPORTED}）")

    steps: List[str] = []

    # 1) 逆设计（环形 target_fsr → R）
    if kind == "RingResonator" and target_fsr_nm and not params:
        params = _inverse_design(kind, target_fsr_nm)
        steps.append(f"逆设计 target_fsr={target_fsr_nm}nm → R={params['R']:.4f}µm")
    if params is None:
        params = _default_params(kind)

    # 2) DRC 初始自查
    drc0 = drc_check_device(kind, params)

    # 3) 自动整改（初始违规时，D-18 DrcFixAgent）
    fix_report = None
    if not drc0.passed:
        from lda_agent.drc_fix_loop import DrcFixAgent
        fix_report = DrcFixAgent().run(kind, params)
        params = dict(fix_report["final_params"])
        steps.append(f"DRC 整改 {fix_report['iterations']} 轮（初始 {len(drc0.violations())} 项违规）")

    # 4) 版图生成（GDS + SVG）
    desc = geometry_desc(kind, params)
    gds_bytes = gds_library(f"LDA-{kind}", {kind: layout_elements(kind, params)})
    svg = svg_preview({kind: _svg_items(desc)})
    steps.append("版图生成（GDSII + SVG）")

    # 5) 仿真验收
    sim = simulate_layout(desc, 3.48, 1.44, 1.55, tol_rel)
    steps.append(f"FDTD 仿真 neff={sim['neff_fdtd']:.4f}（rel={sim['rel_err']:.3%}）")

    # 6) 报告打包 + 落盘
    drc_final = drc_check_device(kind, params)
    accepted = bool(drc_final.passed and sim["passed"])
    report = {
        "kind": kind,
        "final_params": params,
        "inverse_design": ({"target_fsr_nm": target_fsr_nm,
                            "R_um": params.get("R")}
                           if target_fsr_nm else None),
        "drc": drc_final.to_dict(),
        "drc_fix": fix_report["trace"] if fix_report else None,
        "sim": sim,
        "steps": steps,
        "accepted": accepted,
        "verdict": _verdict(kind, params, accepted, sim),
    }
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        oid = out_id or f"pipeline_{kind.lower()}"
        write_gds(os.path.join(out_dir, oid + ".gds"), gds_bytes)
        with open(os.path.join(out_dir, oid + "_report.json"), "w",
                  encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        with open(os.path.join(out_dir, oid + ".svg"), "w", encoding="utf-8") as f:
            f.write(svg)
        report["artifacts"] = {
            "gds": oid + ".gds", "report": oid + "_report.json", "svg": oid + ".svg",
        }
    return report


def _svg_items(desc) -> List:
    items = []
    for d in desc:
        layer = d.get("layer", 1)
        if d["kind"] == "boundary":
            rings = d.get("rings_um", [d.get("points_um", [])])
            pts = []
            for r in rings:
                pts.extend(r)
                pts.append(r[0])
            items.append(("boundary", {"points_um": pts, "layer": layer}))
        else:
            items.append((d["kind"], {"points_um": d.get("points_um", []),
                                      "width_um": d.get("width_um", 0.5),
                                      "layer": layer}))
    return items


def _verdict(kind, params, accepted, sim) -> str:
    if accepted:
        return (f"设计流水线全链路 PASS：{kind} 参数 {params}，"
                f"可制造（DRC 全过）+ 仿真验收 "
                f"neff={sim['neff_fdtd']:.4f}（rel={sim['rel_err']:.3%}）。"
                f"设计包已落盘（GDS + SVG + JSON 报告）。")
    return (f"流水线未全过：DRC={drc_check_device(kind, params).passed}，"
            f"仿真={sim['passed']}。请检查工艺规则 / 目标设置。")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="LDA 一键设计流水线（D-19）")
    ap.add_argument("kind", nargs="?", default="RingResonator",
                    choices=list(_SUPPORTED))
    ap.add_argument("--target_fsr", type=float, default=None,
                    help="环形目标 FSR(nm) → 自动逆设计 R")
    ap.add_argument("--gap", type=float, default=None)
    ap.add_argument("--width", type=float, default=None)
    ap.add_argument("--R", type=float, default=None)
    ap.add_argument("--out", default=None, help="输出目录（默认不落盘）")
    args = ap.parse_args()

    params = {}
    if args.gap is not None:
        params["gap"] = args.gap
    if args.width is not None:
        params["width"] = args.width
    if args.R is not None:
        params["R"] = args.R
    params = params or None

    rep = run_pipeline(args.kind, params=params,
                       target_fsr_nm=args.target_fsr, out_dir=args.out)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if rep["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
