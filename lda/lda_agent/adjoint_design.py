"""LDA · D-69 伴随法梯度逆设计 agent 封装（adjoint FDTD 拓扑逆设计）。

把主权 2D adjoint FDTD 核（lda_solver/adjoint_fdtd.py）封装为 agent 可调用的
设计闭环：给定（默认或自定义）几何 → 均匀平板初值 → 双重验证 → 梯度拓扑
逆设计 → 死标量验收。铁律不变：LLM 不进判决路径，PASS 由死标量比对决定：
  (a) adjoint 灵敏度 vs 中心有限差分对拍 max_rel_err ≤ 0.15（M4 里程碑 1）；
  (b) 拓扑逆设计 improvement = final_FOM / initial_FOM ≥ 1.5（M4 里程碑 2）。

FOM 语义（诚实标注）：高斯脉冲源 + 监视器窄孔径收集场能
FOM = Σ_{n≥meas0} Σ_j Ez[i_mon,j]²。无源无耗散结构可因聚焦/相干增强使
T = FOM/E_in > 1（聚焦增益，非功率透射），报告时与"功率透射"区分。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_solver.adjoint_fdtd import (  # noqa: E402
    AdjointProblem, forward, compute_gradient,
    verify_adjoint, optimize_topology,
)

_DEF_ITERS = 50
_DEF_STEP = 0.5
_DEF_BETA = 14.0


def design_adjoint(problem: Optional[AdjointProblem] = None,
                   iters: int = _DEF_ITERS, step0: float = _DEF_STEP,
                   beta_max: float = _DEF_BETA,
                   nsamples: int = 8, delta: float = 0.05,
                   verbose: bool = False,
                   **geo: Any) -> Dict[str, Any]:
    """伴随法拓扑逆设计闭环：验证锚 → 梯度优化 → 死标量验收。

    geo 可覆盖 AdjointProblem 几何字段（Nx/Ny/dl_factor/sponge/y_mon0/...
    di0/di1/dj0/dj1 等）；不传则用默认聚焦器几何。
    """
    if problem is None:
        problem = AdjointProblem(**geo)
    else:
        # 显式 problem 时忽略 geo（避免歧义）
        geo = {}
    if problem.design_mask.sum() == 0:
        return {"ok": False,
                "error": "设计区为空（di0/di1 或 dj0/dj1 无效），无优化自由度",
                "geometry": {"design_i": [problem.di0, problem.di1],
                             "design_j": [problem.dj0, problem.dj1]}}
    eps0 = _uniform_slab(problem)

    # 1) 验证锚：adjoint 梯度 vs 中心有限差分（方向对拍）
    vr = verify_adjoint(problem, eps0, nsamples=nsamples, delta=delta)

    # 2) 拓扑逆设计：密度投影 + 回溯线搜索梯度上升
    opt = optimize_topology(problem, eps0, iters=iters, step0=step0,
                            beta_max=beta_max, verbose=verbose)

    # 3) 最终设计材料统计（二值化程度）
    final = opt["final_eps"]
    dm = problem.design_mask
    vals = final[dm]
    lo = vals < (problem.eps_min + 0.35 * (problem.eps_max - problem.eps_min))
    hi = vals > (problem.eps_min + 0.65 * (problem.eps_max - problem.eps_min))
    material = {
        "n_design_voxels": int(dm.sum()),
        "frac_low_eps": round(float(lo.mean()), 4),
        "frac_high_eps": round(float(hi.mean()), 4),
        "frac_intermediate": round(float((~(lo | hi)).mean()), 4),
    }

    # 4) 死标量验收
    checks = [
        {"name": "adjoint vs FD 梯度方向对拍",
         "ok": bool(vr["passed"]),
         "detail": (f"max_rel_err={vr['max_rel_err']:.4f} "
                    f"(≤0.15) K={vr['K_adj_over_fd']:.3f}")},
        {"name": "拓扑逆设计提升（M4）",
         "ok": bool(opt["passed"]),
         "detail": (f"improvement={opt['improvement']:.2f}× "
                    f"(≥1.5)：FOM {opt['initial_FOM']:.2f} → "
                    f"{opt['final_FOM']:.2f}")},
        {"name": "诚实标注：脉冲源场能目标语义",
         "ok": True,
         "detail": "FOM=监视器孔径收集场能（脉冲源，能量有界）；"
                   f"T={opt['final_T']:.3f} 为归一化收集场能，聚焦增益可>1，"
                   "非功率透射"},
    ]
    accepted = all(c["ok"] for c in checks)
    verdict = (
        f"伴随法拓扑逆设计 PASS：{material['n_design_voxels']} 体素设计区，"
        f"FOM {opt['initial_FOM']:.1f} → {opt['final_FOM']:.1f} "
        f"（{opt['improvement']:.2f}×），adjoint 对拍 "
        f"max_rel_err={vr['max_rel_err']:.4f}"
        if accepted else
        "未全过：" + "; ".join(c["name"] for c in checks if not c["ok"]))

    return {
        "ok": True,
        "title": "伴随法梯度拓扑逆设计（D-69 · adjoint FDTD）",
        "geometry": {
            "Nx": problem.Nx, "Ny": problem.Ny,
            "dl_um": round(problem.dl, 5), "sponge": problem.sponge,
            "i_src": problem.i_src,
            "y_src": [problem.y_src0, problem.y_src1],
            "i_mon": problem.i_mon,
            "aperture_y": [problem.y_mon0, problem.y_mon1],
            "design_i": [problem.di0, problem.di1],
            "design_j": [problem.dj0, problem.dj1],
            "eps_range": [problem.eps_min, problem.eps_max],
            "wl_um": problem.wl_um,
        },
        "verify": {
            "nsamples": vr["nsamples"], "delta": vr["delta"],
            "K_adj_over_fd": vr["K_adj_over_fd"],
            "max_rel_err": vr["max_rel_err"],
            "mean_rel_err": vr["mean_rel_err"],
            "passed": vr["passed"],
        },
        "optimization": {
            "iters": iters, "step0": step0, "beta_max": beta_max,
            "initial_FOM": opt["initial_FOM"],
            "final_FOM": opt["final_FOM"],
            "final_T": opt["final_T"],
            "improvement": opt["improvement"],
            "passed": opt["passed"],
            "history": opt["history"][-1] if opt["history"] else {},
            "history_tail": opt["history"][-10:] if opt["history"] else [],
        },
        "material": material,
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": ("主权 2D adjoint FDTD（TEz，Yee 网格 + 海绵 PML，高斯脉冲源）。"
                 "adjoint 为 FDTD 更新算子显式转置（数值 Mᵀ 对拍至 1e-15），"
                 "梯度经中心有限差分方向对拍验证。优化器 = 密度投影（beta "
                 "延拓 2→14 二值化）+ 回溯线搜索梯度上升（FOM 单调不降）。"
                 "FOM 为收集场能，聚焦增益可致 T>1，非功率透射。"
                 "LLM 不进判决路径。"),
    }


def _uniform_slab(problem: AdjointProblem) -> Any:
    eps0 = np.full((problem.Nx, problem.Ny), problem.eps_min)
    eps0[problem.design_mask] = (problem.eps_min + problem.eps_max) / 2.0
    return eps0


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA D-69 伴随法拓扑逆设计")
    ap.add_argument("--iters", type=int, default=_DEF_ITERS)
    ap.add_argument("--step", type=float, default=_DEF_STEP)
    ap.add_argument("--beta", type=float, default=_DEF_BETA)
    ap.add_argument("--nsamples", type=int, default=8)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--out", default=None, help="报告 JSON 输出路径")
    args = ap.parse_args()
    rep = design_adjoint(iters=args.iters, step0=args.step,
                         beta_max=args.beta, nsamples=args.nsamples,
                         verbose=args.verbose)
    out = {k: rep[k] for k in (
        "title", "geometry", "verify", "optimization", "material",
        "acceptance", "verdict", "note")}
    text = json.dumps(out, ensure_ascii=False, indent=2, default=str)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)),
                    exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"报告已写入 {args.out}")
    print(text)
    return 0 if rep["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
