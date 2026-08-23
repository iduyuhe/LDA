"""D-84/D-85/D-87 · 3D adjoint 形状逆设计统一入口（破 3D 诚实边界）。

D-84 平板波导宽度曲线（`design_shape3d`）+ **D-85 截面形状**
（`design_section3d`：宽度 w(x) × 厚度 h(x) 双软边界联合）+ **D-87 谱形目标
× 3D**（`design_spectral3d`：截面 × 多波长加权联合）。死标量验收：
  (a) 3D adjoint 梯度 FD 对拍 ≤0.15；
  (b) 形状梯度链式 FD 对拍 ≤0.15（宽度/截面/多波长加权联合）；
  (c) FOM improvement ≥1.5 + DRC（多波长：加权 ≥1.5 且各波长 ≥1.2）。
诚实边界：小 3D 域（内存/算力限制）；FOM 为收集场能（T>1 聚焦增益非功率
透射）。
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
    ShapeProblem3DSection, verify_section_gradient, optimize_section3d,
    make_wl_problems3d, verify_section_gradient_multi,
    optimize_section3d_multi,
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


def design_section3d(
        Nx: int = 44, Ny: int = 36, Nz: int = 12,
        dl_factor: float = 10.0, n_controls: int = 8,
        iters: int = 18, nsamples: int = 6, delta: float = 0.05,
        wl_um: float = 1.55, out: Optional[str] = None) -> Dict[str, Any]:
    """D-85 3D 截面形状逆设计（宽度 w(x) × 厚度 h(x) 双软边界）。"""
    if Nx < 32 or Ny < 24 or Nz < 8:
        return {"ok": False, "error": "3D 域过小（Nx≥32, Ny≥24, Nz≥8）"}
    base = AdjointProblem3D(Nx=Nx, Ny=Ny, Nz=Nz, dl_factor=dl_factor,
                            wl_um=wl_um)
    sp = ShapeProblem3DSection(base, n_controls=n_controls)
    w0 = np.full(n_controls, sp.init_w)
    h0 = np.full(n_controls, sp.init_h)

    t0 = time.perf_counter()
    vr = verify_adjoint3d(base, sp.eps(w0, h0), nsamples=nsamples,
                          delta=delta)
    vs = verify_section_gradient(sp, w0, h0, nsamples=nsamples,
                                 delta=min(delta, 0.02))
    opt = optimize_section3d(sp, iters=iters)
    elapsed = time.perf_counter() - t0

    checks = [
        {"name": "3D adjoint 梯度 vs 有限差分（≤0.15）",
         "ok": bool(vr["passed"]),
         "detail": f"max_rel_err={vr['max_rel_err']:.4f}（{vr['nsamples']} 采样）"},
        {"name": "截面梯度（宽度+厚度）链式 vs 有限差分（≤0.15）",
         "ok": bool(vs["passed"]),
         "detail": f"max_rel_err={vs['max_rel_err']:.4f}（{vs['nsamples']} 采样）"},
        {"name": "FOM improvement ≥ 1.5（均匀截面 → 优化 w×h）",
         "ok": bool(opt["improvement"] >= 1.5),
         "detail": f"{opt['improvement']:.2f}×（{opt['initial_FOM']:.2e} → "
                   f"{opt['final_FOM']:.2e}）"},
        {"name": "可制造性 DRC（宽度 + 厚度双界 + 双平滑）",
         "ok": bool(opt["drc"]["ok"]),
         "detail": opt["drc"]["detail"]},
    ]
    passed = all(c["ok"] for c in checks)
    result = {
        "ok": True,
        "title": "3D 截面形状逆设计（宽度 × 厚度双软边界 · 3D adjoint 纵深）",
        "mode": "adjoint3d_section",
        "n_controls": n_controls,
        "grid": {"Nx": Nx, "Ny": Ny, "Nz": Nz, "dl_factor": dl_factor,
                 "dl_um": round(base.dl, 4), "dt": round(base.dt, 6)},
        "core_layer": {"z": [base.k_core0, base.k_core1]},
        "design_voxels": int(base.design_mask.sum()),
        "verify": {"max_rel_err": vr["max_rel_err"],
                   "section_max_rel_err": vs["max_rel_err"],
                   "nsamples": vr["nsamples"]},
        "optimization": {"initial_FOM": opt["initial_FOM"],
                         "final_FOM": opt["final_FOM"],
                         "improvement": opt["improvement"],
                         "final_width": opt["final_width"],
                         "final_height": opt["final_height"],
                         "elapsed_s": round(elapsed, 2)},
        "drc": opt["drc"],
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": (f"3D 截面形状逆设计 PASS：FOM improvement="
                    f"{opt['improvement']:.2f}×；3D adjoint FD 对拍 "
                    f"{vr['max_rel_err']:.4f}、截面梯度（w+h）链式 "
                    f"{vs['max_rel_err']:.4f}（≤0.15）；宽度 "
                    f"{opt['final_width']}、厚度 {opt['final_height']}；"
                    f"DRC {opt['drc']['detail']}。耗时 {elapsed:.1f}s。"
                    if passed else
                    "3D 截面形状逆设计未全过：" +
                    "; ".join(c["name"] for c in checks if not c["ok"])),
        "note": ("D-85 3D 截面形状：宽度 w(x) × 厚度 h(x) 双软边界联合优化"
                 "（z 底固定 0、顶 z_top=h(x)）；3D Yee 显式转置梯度链式。"
                 "诚实边界：小 3D 域；FOM 为收集场能（T>1 聚焦增益非功率"
                 "透射）。LLM 不进判决路径。"),
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def design_spectral3d(
        Nx: int = 44, Ny: int = 36, Nz: int = 12,
        dl_factor: float = 10.0, n_controls: int = 8,
        iters: int = 16, nsamples: int = 6, delta: float = 0.05,
        wavelengths_um: Optional[list] = None,
        weights: Optional[list] = None,
        out: Optional[str] = None) -> Dict[str, Any]:
    """D-87 谱形目标 × 3D：截面形状 × 多波长加权联合逆设计。

    每个波长构造独立 `ShapeProblem3DSection`（base deepcopy，**物理网格固定
    只变 omega/period_steps**——D-80 归一化网格陷阱免疫）。联合
    FOM = Σw_λ·FOM_λ；联合梯度分块归一化（w/h 各自尺度）；线搜索评估 =
    全波长加权 FOM（同投影一致）。验收：加权 improvement≥1.5、各波长≥1.2、
    多波长联合梯度 FD 对拍≤0.15、DRC 双界。
    """
    if Nx < 32 or Ny < 24 or Nz < 8:
        return {"ok": False, "error": "3D 域过小（Nx≥32, Ny≥24, Nz≥8）"}
    base = AdjointProblem3D(Nx=Nx, Ny=Ny, Nz=Nz, dl_factor=dl_factor)
    probs = make_wl_problems3d(base, wavelengths_um)
    nwl = len(probs)
    if weights is None:
        wt = np.ones(nwl) / nwl
    else:
        wt = np.asarray(weights, dtype=float)
        wt = wt / wt.sum()
    sps = [ShapeProblem3DSection(p, n_controls=n_controls) for p in probs]
    w0 = np.full(n_controls, sps[0].init_w)
    h0 = np.full(n_controls, sps[0].init_h)

    t0 = time.perf_counter()
    vr = verify_adjoint3d(base, sps[0].eps(w0, h0), nsamples=nsamples,
                          delta=delta)
    vm = verify_section_gradient_multi(sps, wt, w0, h0,
                                       nsamples=nsamples,
                                       delta=min(delta, 0.02))
    opt = optimize_section3d_multi(sps, weights=list(wt), iters=iters)
    elapsed = time.perf_counter() - t0

    checks = [
        {"name": "3D adjoint 梯度 vs 有限差分（≤0.15）",
         "ok": bool(vr["passed"]),
         "detail": f"max_rel_err={vr['max_rel_err']:.4f}（{vr['nsamples']} 采样）"},
        {"name": "多波长联合梯度（w+h×Nλ）链式 vs 有限差分（≤0.15）",
         "ok": bool(vm["passed"]),
         "detail": f"max_rel_err={vm['max_rel_err']:.4f}（{vm['nsamples']} 采样）"},
        {"name": "加权 improvement ≥ 1.5（均匀截面 → 优化 w×h 多波长）",
         "ok": bool(opt["weighted_improvement"] >= 1.5),
         "detail": f"{opt['weighted_improvement']:.2f}×（逐波长 "
                   f"{[round(p['improvement'], 2) for p in opt['per_wavelength']]}）"},
        {"name": "各波长 improvement ≥ 1.2（谱形目标=设计对目标带整体可用）",
         "ok": bool(all(p["improvement"] >= 1.2 for p in opt["per_wavelength"])),
         "detail": "; ".join(f"λ{p['wl_um']}:{p['improvement']:.2f}×"
                             for p in opt["per_wavelength"])},
        {"name": "可制造性 DRC（宽度 + 厚度双界 + 双平滑）",
         "ok": bool(opt["drc"]["ok"]),
         "detail": opt["drc"]["detail"]},
    ]
    passed = all(c["ok"] for c in checks)
    result = {
        "ok": True,
        "title": "谱形目标 × 3D 截面（多波长加权联合 · 参数化×目标矩阵 3D 打通）",
        "mode": "adjoint3d_spectral",
        "n_controls": n_controls,
        "n_wavelengths": nwl,
        "grid": {"Nx": Nx, "Ny": Ny, "Nz": Nz, "dl_factor": dl_factor,
                 "dl_um": round(base.dl, 4), "dt": round(base.dt, 6)},
        "core_layer": {"z": [base.k_core0, base.k_core1]},
        "design_voxels": int(base.design_mask.sum()),
        "verify": {"max_rel_err": vr["max_rel_err"],
                   "spectral_max_rel_err": vm["max_rel_err"],
                   "nsamples": vr["nsamples"]},
        "optimization": {
            "weighted_improvement": opt["weighted_improvement"],
            "per_wavelength": opt["per_wavelength"],
            "initial_FOM_total": opt["initial_FOM_total"],
            "final_FOM_total": opt["final_FOM_total"],
            "final_width": opt["final_width"],
            "final_height": opt["final_height"],
            "elapsed_s": round(elapsed, 2)},
        "drc": opt["drc"],
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": (f"谱形目标 × 3D 截面 PASS：加权 improvement="
                    f"{opt['weighted_improvement']:.2f}×（逐波长 "
                    f"{[round(p['improvement'], 2) for p in opt['per_wavelength']]}）；"
                    f"3D adjoint FD 对拍 {vr['max_rel_err']:.4f}、多波长联合梯度 "
                    f"{vm['max_rel_err']:.4f}（≤0.15）；宽度 "
                    f"{opt['final_width']}、厚度 {opt['final_height']}；"
                    f"DRC {opt['drc']['detail']}。耗时 {elapsed:.1f}s。"
                    if passed else
                    "谱形目标 × 3D 截面未全过：" +
                    "; ".join(c["name"] for c in checks if not c["ok"])),
        "note": ("D-87 谱形目标 × 3D 截面：宽度×厚度双软边界 × 多波长加权联合"
                 "（物理网格固定只变 omega——归一化网格陷阱免疫）；分块归一化"
                 "（w/h 各自尺度）。诚实边界：小 3D 域；FOM 为收集场能（T>1 "
                 "聚焦增益非功率透射）。LLM 不进判决路径。"),
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D-84/85/87 3D adjoint 形状逆设计")
    ap.add_argument("--mode", default="shape",
                    choices=["shape", "section", "spectral"])
    ap.add_argument("--Nx", type=int, default=44)
    ap.add_argument("--Ny", type=int, default=36)
    ap.add_argument("--Nz", type=int, default=12)
    ap.add_argument("--n_controls", type=int, default=8)
    ap.add_argument("--iters", type=int, default=18)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    kw = dict(Nx=a.Nx, Ny=a.Ny, Nz=a.Nz, n_controls=a.n_controls,
              iters=a.iters, out=a.out)
    if a.mode == "section":
        r = design_section3d(**kw)
    elif a.mode == "spectral":
        r = design_spectral3d(**kw)
    else:
        r = design_shape3d(**kw)
    print(json.dumps({k: r[k] for k in
                      ("title", "verify", "optimization", "drc",
                       "acceptance", "verdict")},
                     ensure_ascii=False, indent=2)[:3000])
    return 0 if (r.get("ok") and r["acceptance"]["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
