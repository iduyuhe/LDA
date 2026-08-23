"""D-82 · 混合逆设计统一入口（形状主干 + 拓扑微调带）。

把 D-82 混合逆设计核（`lda_solver/hybrid_inverse.py`）包装为可复用的
设计→验收入口：混合优化 + **纯形状基线对比**（同迭代，验证拓扑自由度
增益）+ 死标量验收（FD 对拍 / improvement / 混合≥纯形状 / DRC）。
3D 形状为诚实边界（2D TEz 核限制，归后续）。
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

import numpy as np  # noqa: E402

from lda_solver.adjoint_fdtd import AdjointProblem, forward  # noqa: E402
from lda_solver.hybrid_inverse import (  # noqa: E402
    HybridProblem, verify_hybrid_gradient, optimize_hybrid,
)


def design_hybrid(
        Nx: int = 90, Ny: int = 70, dl_factor: float = 10.0,
        n_controls: int = 8, iters: int = 20, nsamples: int = 8,
        delta: float = 0.02, topo_wgt: float = 0.6,
        topo_band: str = "2.5,7.5", wl_um: float = 1.55,
        out: Optional[str] = None) -> Dict[str, Any]:
    """混合逆设计统一入口（含纯形状基线对比）。"""
    lo, hi = [float(x) for x in topo_band.split(",")]
    if lo >= hi:
        return {"ok": False, "error": f"拓扑带非法：{topo_band}（须 lo<hi）"}
    base = AdjointProblem(Nx=Nx, Ny=Ny, dl_factor=dl_factor, sponge=8,
                          wl_um=wl_um)
    hp = HybridProblem(base=base, n_controls=n_controls,
                       topo_band=(lo, hi))
    w0 = np.full(n_controls, hp.init_halfwidth)
    rho0 = np.zeros(hp.n_topo)

    t0 = time.perf_counter()
    vr = verify_hybrid_gradient(hp, w0, rho0, nsamples=nsamples, delta=delta)
    # 纯形状基线（拓扑冻结，同迭代）
    base_opt = optimize_hybrid(hp, iters=iters, topo_wgt=0.0)
    # 混合优化
    opt = optimize_hybrid(hp, iters=iters, topo_wgt=topo_wgt,
                          baseline=base_opt)
    elapsed = time.perf_counter() - t0

    checks = [
        {"name": "混合梯度 vs 有限差分（max_rel_err ≤ 0.15）",
         "ok": bool(vr["passed"]),
         "detail": f"max_rel_err={vr['max_rel_err']:.4f}（{vr['nsamples']} 采样）"},
        {"name": "FOM improvement ≥ 1.5",
         "ok": bool(opt["improvement"] >= 1.5),
         "detail": f"{opt['improvement']:.2f}×（{opt['initial_FOM']:.2e} → "
                   f"{opt['final_FOM']:.2e}）"},
        {"name": "混合 ≥ 纯形状（拓扑自由度增益）",
         "ok": bool(opt.get("gain_over_shape") is None
                    or opt["gain_over_shape"] >= 1.0),
         "detail": (f"混合 {opt['improvement']:.2f}× vs 纯形状 "
                    f"{opt.get('baseline_shape_improvement', 0):.2f}×"
                    + (f"（增益 {opt['gain_over_shape']}×）"
                       if opt.get("gain_over_shape") is not None else ""))},
        {"name": "可制造性 DRC（形状宽度 + 平滑）",
         "ok": bool(opt["drc"]["ok"]),
         "detail": opt["drc"]["detail"]},
    ]
    passed = all(c["ok"] for c in checks)
    result = {
        "ok": True,
        "title": "形状+拓扑混合逆设计（分层表达：形状主干 + 拓扑微调带）",
        "mode": "hybrid",
        "n_controls": n_controls,
        "n_topo_voxels": hp.n_topo,
        "topo_band": [lo, hi],
        "grid": {"Nx": Nx, "Ny": Ny, "dl_factor": dl_factor},
        "verify": {"max_rel_err": vr["max_rel_err"], "nsamples": vr["nsamples"]},
        "optimization": {"initial_FOM": opt["initial_FOM"],
                         "final_FOM": opt["final_FOM"],
                         "improvement": opt["improvement"],
                         "final_width": opt["final_width"],
                         "topo_fill_frac": opt["topo_fill_frac"],
                         "baseline_shape_improvement":
                             opt.get("baseline_shape_improvement"),
                         "gain_over_shape": opt.get("gain_over_shape"),
                         "elapsed_s": round(elapsed, 2)},
        "drc": opt["drc"],
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": (f"混合逆设计 PASS：FOM improvement={opt['improvement']:.2f}×"
                    f"（纯形状基线 {opt.get('baseline_shape_improvement', 0):.2f}×"
                    f"，混合增益 {opt.get('gain_over_shape', 1.0)}×）；宽度曲线 "
                    f"{opt['final_width']}；拓扑带参与度 "
                    f"{opt['topo_fill_frac']}；混合梯度对拍 "
                    f"{vr['max_rel_err']:.4f}；DRC "
                    f"{opt['drc']['detail']}。耗时 {elapsed:.1f}s。"
                    if passed else
                    "混合逆设计未全过：" +
                    "; ".join(c["name"] for c in checks if not c["ok"])),
        "note": ("D-82 分层表达：形状主干（宽度曲线，可制造内建 DRC）+ 拓扑"
                 "微调带（voxel 密度，紧贴形状边界）。诚实边界：3D 形状（宽"
                 "+高截面参数化）需 3D adjoint 核（2D TEz 限制，归后续）；"
                 "拓扑带为单环带；FOM 为收集场能（T>1 聚焦增益非功率透射）。"
                 "LLM 不进判决路径。"),
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D-82 混合逆设计")
    ap.add_argument("--n_controls", type=int, default=8)
    ap.add_argument("--iters", type=int, default=20)
    ap.add_argument("--topo_band", default="2.5,7.5")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = design_hybrid(n_controls=a.n_controls, iters=a.iters,
                      topo_band=a.topo_band, out=a.out)
    print(json.dumps({k: r[k] for k in
                      ("title", "verify", "optimization", "drc",
                       "acceptance", "verdict")},
                     ensure_ascii=False, indent=2)[:3000])
    return 0 if (r.get("ok") and r["acceptance"]["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
