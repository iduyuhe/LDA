"""D-84 · 3D adjoint 形状逆设计统一入口（破 3D 诚实边界第一步）。

把 3D adjoint 核（`lda_solver/adjoint_fdtd3d.py`：3D Yee 显式转置伴随 +
宽度曲线平板波导形状）包装为设计→验收入口。死标量验收：
  (a) 3D adjoint 梯度 FD 对拍 ≤0.15；
  (b) 3D 形状梯度链式 FD 对拍 ≤0.15；
  (c) FOM improvement ≥1.5 + DRC。
诚实边界：z 截面暂均匀（截面变化归 D-85+）；FOM 为收集场能（T>1 聚焦增益
非功率透射）；小 3D 域（内存/算力限制）。
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

from lda_solver.adjoint_fdtd3d import (  # noqa: E402
    AdjointProblem3D, ShapeProblem3D, verify_adjoint3d,
    verify_shape_gradient3d, optimize_shape3d,
)


def design_shape3d(
        Nx: int = 44, Ny: int = 36, Nz: int = 12,
        dl_factor: float = 10.0, n_controls: int = 8,
        iters: int = 20, nsamples: int = 6, delta: float = 0.05,
        wl_um: float = 1.55, out: Optional[str] = None) -> Dict[str, Any]:
    """3D adjoint 形状逆设计统一入口（平板波导宽度曲线）。"""
    if Nx < 32 or Ny < 24 or Nz < 8:
        return {"ok": False, "error": "3D 域过小（Nx≥32, Ny≥24, Nz≥8）"}
    base = AdjointProblem3D(Nx=Nx, Ny=Ny, Nz=Nz, dl_factor=dl_factor,
                            wl_um=wl_um)
    sp = ShapeProblem3D(base, n_controls=n_controls)
    w0 = np.full(n_controls, sp.init_halfwidth)

    t0 = time.perf_counter()
    vr = verify_adjoint3d(base, sp.eps(w0), nsamples=nsamples, delta=delta)
    # 形状梯度 FD 对拍须用小步长（FOM 对宽度二阶非线性，0.05 超阈——D-84 实测）
    vs = verify_shape_gradient3d(sp, w0, nsamples=nsamples,
                                 delta=min(delta, 0.02))
    opt = optimize_shape3d(sp, iters=iters)
    elapsed = time.perf_counter() - t0

    checks = [
        {"name": "3D adjoint 梯度 vs 有限差分（≤0.15）",
         "ok": bool(vr["passed"]),
         "detail": f"max_rel_err={vr['max_rel_err']:.4f}（{vr['nsamples']} 采样）"},
        {"name": "3D 形状梯度链式 vs 有限差分（≤0.15）",
         "ok": bool(vs["passed"]),
         "detail": f"max_rel_err={vs['max_rel_err']:.4f}（{vs['nsamples']} 采样）"},
        {"name": "FOM improvement ≥ 1.5（均匀宽 → 优化 taper）",
         "ok": bool(opt["improvement"] >= 1.5),
         "detail": f"{opt['improvement']:.2f}×（{opt['initial_FOM']:.2e} → "
                   f"{opt['final_FOM']:.2e}）"},
        {"name": "可制造性 DRC（形状宽度 + 平滑）",
         "ok": bool(opt["drc"]["ok"]),
         "detail": opt["drc"]["detail"]},
    ]
    passed = all(c["ok"] for c in checks)
    result = {
        "ok": True,
        "title": "3D adjoint 形状逆设计（3D Yee 显式转置伴随 · 破 3D 边界）",
        "mode": "adjoint3d_shape",
        "n_controls": n_controls,
        "grid": {"Nx": Nx, "Ny": Ny, "Nz": Nz, "dl_factor": dl_factor,
                 "dl_um": round(base.dl, 4), "dt": round(base.dt, 6)},
        "core_layer": {"z": [base.k_core0, base.k_core1]},
        "design_voxels": int(base.design_mask.sum()),
        "verify": {"max_rel_err": vr["max_rel_err"],
                   "shape_max_rel_err": vs["max_rel_err"],
                   "nsamples": vr["nsamples"]},
        "optimization": {"initial_FOM": opt["initial_FOM"],
                         "final_FOM": opt["final_FOM"],
                         "improvement": opt["improvement"],
                         "final_width": opt["final_width"],
                         "elapsed_s": round(elapsed, 2)},
        "drc": opt["drc"],
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": (f"3D adjoint 形状逆设计 PASS：FOM improvement="
                    f"{opt['improvement']:.2f}×（{opt['initial_FOM']:.2e} → "
                    f"{opt['final_FOM']:.2e}）；3D adjoint FD 对拍 "
                    f"{vr['max_rel_err']:.4f}、形状梯度链式 "
                    f"{vs['max_rel_err']:.4f}（≤0.15）；宽度 taper "
                    f"{opt['final_width']}；DRC {opt['drc']['detail']}。"
                    f"3D 域 {Nx}×{Ny}×{Nz}，设计体素 "
                    f"{int(base.design_mask.sum())}。耗时 {elapsed:.1f}s。"
                    if passed else
                    "3D adjoint 形状逆设计未全过：" +
                    "; ".join(c["name"] for c in checks if not c["ok"])),
        "note": ("D-84 破 3D 诚实边界第一步：3D Yee 交错网格（6 分量）更新算子"
                 "显式转置伴随（数值 Mᵀ 对拍 1e-15）+ 宽度曲线平板波导形状（z "
                 "截面暂均匀）。诚实边界：z 方向截面变化归 D-85+；FOM 为监视器"
                 "收集场能（T>1 聚焦增益非功率透射）；小 3D 域（内存/算力）。"
                 "LLM 不进判决路径。"),
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D-84 3D adjoint 形状逆设计")
    ap.add_argument("--Nx", type=int, default=48)
    ap.add_argument("--Ny", type=int, default=40)
    ap.add_argument("--Nz", type=int, default=12)
    ap.add_argument("--n_controls", type=int, default=8)
    ap.add_argument("--iters", type=int, default=16)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = design_shape3d(Nx=a.Nx, Ny=a.Ny, Nz=a.Nz,
                       n_controls=a.n_controls, iters=a.iters, out=a.out)
    print(json.dumps({k: r[k] for k in
                      ("title", "verify", "optimization", "drc",
                       "acceptance", "verdict")},
                     ensure_ascii=False, indent=2)[:3000])
    return 0 if (r.get("ok") and r["acceptance"]["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
