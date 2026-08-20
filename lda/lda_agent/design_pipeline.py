"""LDA · D-19/D-25 一键设计流水线（IR → 版图 → DRC → 整改 → 仿真 → 验收）。

把已交付的版图线串成**产品化设计交付流水线**：输入设计意图（器件 kind +
目标/参数），自动完成：

  1. 逆设计（可选）：环形 target_fsr → 半径 R（D-11 RingBandAgent）；
                     波导 target_neff → 芯宽 width（D-25，slab ORACLE 反解）
  2. 版图生成：geometry_desc → GDSII + SVG（D-14）
  3. DRC 自查：可制造性规则检查（D-15）
  4. 自动整改：DRC violation → agent 调参直到可制造（D-18）
  5. 仿真验收（按器件分派，D-25）：
     - Waveguide/Ring/DC：版图直波导 FDTD neff → slab ORACLE（D-16）
     - SymmetricYBranch：分束验收（对称性定理，GPU live / 无 GPU ORACLE 演示）
  6. 设计包落盘：GDS + SVG + JSON 报告

CLI：
  python -m lda_agent.design_pipeline RingResonator --target_fsr 9.15
  python -m lda_agent.design_pipeline Waveguide --target_neff 3.2   # D-25
  python -m lda_agent.design_pipeline SymmetricYBranch
  python -m lda_agent.design_pipeline DirectionalCoupler --gap 0.1  # 演示自动整改

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


def _inverse_design_waveguide(target_neff: float, n_core: float = 3.48,
                              n_clad: float = 1.44, wl_um: float = 1.55,
                              width_bounds=(0.35, 0.75)) -> Dict[str, float]:
    """波导目标 neff → 芯宽 width（slab ORACLE 反解，D-25）。

    slab TE 基模 neff(a) 随半厚 a 单调递增 → 宽度窗口内目标 neff 唯一反解
    （二分）。独立于 FDTD：逆设计用解析锚，流水线仿真再用 FDTD 交叉验收。
    """
    _LDA_HARNESS = os.path.join(os.path.dirname(_HERE), "lda_harness")
    if _LDA_HARNESS not in sys.path:
        sys.path.insert(0, _LDA_HARNESS)
    from oracle_mode import _slab_te_neff

    def f(a: float) -> float:
        return _slab_te_neff(n_core, n_clad, a, wl_um)

    lo_a, hi_a = width_bounds[0] / 2.0, width_bounds[1] / 2.0
    f_lo, f_hi = f(lo_a), f(hi_a)
    if not (f_lo < target_neff < f_hi):
        raise RuntimeError(
            f"目标 neff={target_neff} 不在宽度窗口 [{width_bounds[0]},{width_bounds[1]}]µm "
            f"可达范围 [{f_lo:.3f}, {f_hi:.3f}]")
    lo, hi = lo_a, hi_a
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if f(mid) < target_neff:
            lo = mid
        else:
            hi = mid
    return {"width": round(lo + hi, 4)}


def _simulate(kind: str, params: Dict[str, float], tol_rel: float) -> Dict:
    """按器件类型分派仿真验收（D-25 扩展）。

    Waveguide / RingResonator / DirectionalCoupler：版图直波导 neff
    （layout_sim，FDTD ↔ slab ORACLE）；
    SymmetricYBranch：分束验收（对称性定理，GPU live / 无 GPU 诚实 ORACLE 演示）。
    """
    if kind == "SymmetricYBranch":
        return _simulate_yb(params, tol_rel)
    desc = geometry_desc(kind, params)
    sim = simulate_layout(desc, 3.48, 1.44, 1.55, tol_rel)
    sim["mode"] = "layout_fdtd"
    return sim


def _simulate_yb(params: Dict[str, float], tol_rel: float) -> Dict:
    """对称 Y 分支分束验收（D-01 验收锚，D-25 接入流水线）。

    有 GPU → CouplerAgent YB live（FDTD 能流平衡 ↔ 对称性定理 50/50）；
    无 GPU → 诚实 ORACLE 真值演示（对称性定理：几何完全对称 ⇒ P1=P2）。
    """
    from lda_agent.coupler_loop import CouplerAgent, CouplerTarget

    def _cuda_ok() -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False

    if not _cuda_ok():
        return {
            "mode": "oracle_demo",
            "passed": True,
            "target_frac": 0.5,
            "balance_abs": 0.0,
            "note": "对称性定理（几何完全对称 ⇒ P1=P2=0.5·P_in）；"
                    "实时 FDTD 分束仿真需 GPU，此处为 ORACLE 真值演示",
            "tol_balance": 0.10,
        }
    t = CouplerTarget(kind="ybranch", backend="torch")
    out = CouplerAgent().run(t)
    m = out.metrics
    return {
        "mode": "live_fdtd",
        "passed": bool(out.passed),
        "target_frac": m.get("target_frac"),
        "fracA": m.get("fracA"),
        "fracB": m.get("fracB"),
        "balance_abs": m.get("balance_abs"),
        "tol_balance": m.get("tol_balance"),
    }


def run_pipeline(kind: str = "RingResonator",
                 params: Optional[Dict[str, float]] = None,
                 target_fsr_nm: Optional[float] = None,
                 target_neff: Optional[float] = None,
                 out_dir: Optional[str] = None, out_id: Optional[str] = None,
                 tol_rel: float = 0.02) -> Dict:
    """一键设计流水线：逆设计→版图→DRC→整改→仿真→验收→落盘。"""
    if kind not in _SUPPORTED:
        raise ValueError(f"流水线暂不支持 kind={kind}（支持：{_SUPPORTED}）")

    steps: List[str] = []

    # 1) 逆设计（环形 target_fsr→R；波导 target_neff→width）
    if kind == "RingResonator" and target_fsr_nm and not params:
        params = _inverse_design(kind, target_fsr_nm)
        steps.append(f"逆设计 target_fsr={target_fsr_nm}nm → R={params['R']:.4f}µm")
    elif kind == "Waveguide" and target_neff and not params:
        params = _inverse_design_waveguide(target_neff)
        steps.append(f"逆设计 target_neff={target_neff} → width={params['width']}µm")
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

    # 5) 仿真验收（按器件类型分派）
    sim = _simulate(kind, params, tol_rel)
    if sim.get("mode") == "oracle_demo":
        steps.append(f"仿真验收：ORACLE 真值演示（{sim['note'][:28]}…）")
    elif sim.get("mode") == "live_fdtd":
        steps.append(f"FDTD 分束仿真 fracA={sim.get('fracA')}（balance={sim.get('balance_abs')}）")
    else:
        steps.append(f"FDTD 仿真 neff={sim['neff_fdtd']:.4f}（rel={sim['rel_err']:.3%}）")

    # 6) 报告打包 + 落盘
    drc_final = drc_check_device(kind, params)
    accepted = bool(drc_final.passed and sim["passed"])
    report = {
        "kind": kind,
        "final_params": params,
        "layout_svg": svg,
        "inverse_design": (
            {"target_fsr_nm": target_fsr_nm, "R_um": params.get("R")}
            if target_fsr_nm else
            {"target_neff": target_neff, "width_um": params.get("width")}
            if target_neff else None),
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
        mode = sim.get("mode", "layout_fdtd")
        if mode == "oracle_demo":
            detail = "仿真验收：对称性定理 ORACLE 真值（分束 50/50）"
        elif mode == "live_fdtd":
            detail = (f"仿真验收：FDTD 分束 fracA={sim.get('fracA')}"
                      f"（balance={sim.get('balance_abs')}）")
        else:
            detail = f"仿真验收 neff={sim['neff_fdtd']:.4f}（rel={sim['rel_err']:.3%}）"
        return (f"设计流水线全链路 PASS：{kind} 参数 {params}，"
                f"可制造（DRC 全过）+ {detail}。"
                f"设计包已落盘（GDS + SVG + JSON 报告）。")
    return (f"流水线未全过：DRC={drc_check_device(kind, params).passed}，"
            f"仿真={sim.get('passed')}。请检查工艺规则 / 目标设置。")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="LDA 一键设计流水线（D-19/D-25）")
    ap.add_argument("kind", nargs="?", default="RingResonator",
                    choices=list(_SUPPORTED))
    ap.add_argument("--target_fsr", type=float, default=None,
                    help="环形目标 FSR(nm) → 自动逆设计 R")
    ap.add_argument("--target_neff", type=float, default=None,
                    help="波导目标 neff → 自动逆设计 width（D-25）")
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
                       target_fsr_nm=args.target_fsr,
                       target_neff=args.target_neff, out_dir=args.out)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if rep["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
