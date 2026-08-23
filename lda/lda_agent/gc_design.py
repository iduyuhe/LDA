"""D-78 光栅耦合器（GC）端口验收 agent 封装。

design_gc(mmi=None, **kw) → 报告：GC 2D FDTD 透射谱 + 光栅方程 ORACLE
验收（谷检出 / 谷位置对拍 / Λ 扫描趋势锚）。LLM 不进判决路径。
"""
import argparse
import json
import os
import sys
from typing import Any, Dict

_DEF_GC = {"width": 0.5, "Lambda": 0.68, "duty": 0.55, "n_tooth": 12,
           "L_in": 3.0, "L_out": 2.0, "wl0_um": 1.55, "n_wl": 9}


def design_gc(gc: Dict[str, Any] | None = None,
              verbose: bool = False, **kw: Any) -> Dict[str, Any]:
    """D-78 GC 端口验收闭环。kw 透传求解参数（smoke 提速）。"""
    from lda_solver.port_sparams_gc import verify_gc
    params = dict(_DEF_GC)
    if gc:
        params.update({k: float(v) for k, v in gc.items() if v is not None})
    vr = verify_gc(params, **kw)
    pts = vr["spectrum"]["points"]
    checks = [
        {"name": "GC 2D FDTD 端口验收（光栅方程 ORACLE）",
         "ok": bool(vr["acceptance"]["passed"]),
         "detail": (f"谷 depth={vr['dip']['depth']:.3f}（≥0.10）· 谷位置 "
                    f"{vr['dip']['wl_um']}µm vs 预测 {vr['lambda_rad_pred']}µm "
                    f"（rel={abs(vr['dip']['wl_um']-vr['lambda_rad_pred'])/vr['lambda_rad_pred']:.3f}"
                    f"≤0.15）· Λ 扫描斜率 {vr['slope']['slope_fit']} vs "
                    f"周期结构 neff {vr['slope']['slope_pred']} "
                    f"（rel={vr['slope']['slope_rel_err']:.3f}≤0.10）")},
        {"name": "凹槽微扰诊断（诚实标注，非判据）",
         "ok": True,
         "detail": (f"直波导 neff={vr['neff_measured']}、周期结构反解 "
                    f"neff_gc={vr['neff_gc_inferred']}、微扰比例 "
                    f"{vr['perturb_frac']:.3f}（凹槽使周期结构 n 低于直波导，"
                    f"Λ 无关恒定比例，物理预期）")},
    ]
    accepted = all(c["ok"] for c in checks)
    report = {
        "title": "光栅耦合器端口验收（D-78 · 光栅方程 ORACLE）",
        "geometry": {"GC": dict(params), "neff_measured": vr["neff_measured"],
                     "lambda_rad_pred": vr["lambda_rad_pred"],
                     "lambda_bragg_pred": vr["lambda_bragg_pred"]},
        "spectrum": vr["spectrum"],
        "dip": vr["dip"],
        "slope": vr["slope"],
        "checks": checks,
        "acceptance": {"passed": accepted,
                       "criteria": vr["acceptance"]["criteria"]},
        "verdict": vr["verdict"],
        "note": vr["note"],
    }
    if verbose:
        print(f"[GC] accepted={accepted} "
              f"dip={vr['dip']['wl_um']}µm depth={vr['dip']['depth']:.3f} "
              f"slope_rel={vr['slope']['slope_rel_err']:.3f}")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="D-78 GC 端口验收报告")
    ap.add_argument("--out", default="reports/gc_d78.json")
    ap.add_argument("--Lambda", type=float, default=None)
    ap.add_argument("--duty", type=float, default=None)
    ap.add_argument("--n_tooth", type=int, default=None)
    args = ap.parse_args()
    gc = {}
    if args.Lambda is not None:
        gc["Lambda"] = args.Lambda
    if args.duty is not None:
        gc["duty"] = args.duty
    if args.n_tooth is not None:
        gc["n_tooth"] = args.n_tooth
    rep = design_gc(gc or None, verbose=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, default=str)
    print(f"报告已写入 {args.out}（accepted={rep['acceptance']['passed']}）")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
