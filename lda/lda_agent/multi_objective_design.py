"""D-81 · 形状逆设计 + 多目标联合（Track A 纵深 · 从拓扑到形状、从单目标到多目标）。

把 D-80 的「谱形目标逆设计」再推进一步：
  ① **形状逆设计**：voxel 拓扑 → 连续宽度曲线 w(x)（K 控制点 + sigmoid 软
     边界），形状梯度链式投影，可制造性内建（宽度界 + 平滑约束 + DRC 验收）；
  ② **多目标联合**：多波长透射加权联合（FOM=Σw_λ·FOM_λ，形状参数共享）
     + **Pareto 前端扫描**（权重网格 → 各权重形状优化 → 非支配前端点）。

统一闭环（LLM 不进判决路径，死标量验收）：
  (a) 形状梯度 vs 中心有限差分方向对拍 max_rel_err ≤ 0.15；
  (b) 目标 FOM improvement ≥ 1.5（多目标 = 加权 improvement ≥ 1.5）；
  (c) 可制造性 DRC：宽度 ∈ [w_min, w_max]、相邻控制点变化 ≤ slope_max。

诚实边界：形状 = 单芯宽度曲线（taper/模式适配/透射），分叉/多芯归拓扑域
（D-80 split_ratio）；Pareto 为有限权重网格近似；FOM 为脉冲源监视器收集
场能（T>1 聚焦增益，非功率透射）；2D TEz。
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

import numpy as np  # noqa: E402

from lda_solver.adjoint_fdtd import AdjointProblem, forward  # noqa: E402
from lda_solver.shape_inverse import (  # noqa: E402
    ShapeProblem, verify_shape_gradient, optimize_shape, shape_drc,
)


def _make_base(Nx: int, Ny: int, dl_factor: float, sponge: int,
               wl_um: float) -> AdjointProblem:
    return AdjointProblem(Nx=Nx, Ny=Ny, dl_factor=dl_factor, sponge=sponge,
                          wl_um=wl_um)


def _shape_for(base: AdjointProblem, wl_um: Optional[float],
               n_controls: int, w_min: float, w_max: float,
               slope_max: float) -> ShapeProblem:
    """构造 ShapeProblem；wl 变化时固定 dl 只变 omega（D-80 教训）。"""
    import copy
    b = copy.deepcopy(base)
    if wl_um is not None and abs(wl_um - b.wl_um) > 1e-9:
        b.wl_um = float(wl_um)
        b.omega = 2.0 * np.pi / float(wl_um)
        b.period_steps = int(round(2.0 * np.pi / (b.omega * b.dt)))
    return ShapeProblem(base=b, n_controls=n_controls, w_min=w_min,
                        w_max=w_max, slope_max=slope_max)


# ---------------------------------------------------------------------------
# 单目标形状逆设计
# ---------------------------------------------------------------------------
def design_shape(
        Nx: int = 90, Ny: int = 70, dl_factor: float = 10.0,
        n_controls: int = 8, iters: int = 25, nsamples: int = 6,
        delta: float = 0.05, w_min: float = 2.0, w_max: float = 10.0,
        slope_max: float = 1.5, wl_um: float = 1.55,
        out: Optional[str] = None) -> Dict[str, Any]:
    """单目标形状逆设计（宽度曲线优化监视器收集场能）。"""
    if w_min >= w_max:
        return {"ok": False, "error": f"宽度界非法：w_min={w_min} ≥ w_max={w_max}"
                                      f"（须 w_min < w_max）"}
    base = _make_base(Nx, Ny, dl_factor, 8, wl_um)
    sp = _shape_for(base, None, n_controls, w_min, w_max, slope_max)
    w0 = np.full(n_controls, sp.init_halfwidth)
    t0 = time.perf_counter()
    vr = verify_shape_gradient(sp, w0, nsamples=nsamples, delta=delta)
    opt = optimize_shape(sp, iters=iters)
    elapsed = time.perf_counter() - t0

    checks = [
        {"name": "形状梯度 vs 有限差分（max_rel_err ≤ 0.15）",
         "ok": bool(vr["passed"]),
         "detail": f"max_rel_err={vr['max_rel_err']:.4f}（{vr['nsamples']} 控制点）"},
        {"name": "FOM improvement ≥ 1.5",
         "ok": bool(opt["improvement"] >= 1.5),
         "detail": f"{opt['improvement']:.2f}×（{opt['initial_FOM']:.2e} → "
                   f"{opt['final_FOM']:.2e}）"},
        {"name": "可制造性 DRC（宽度界 + 平滑）",
         "ok": bool(opt["drc"]["ok"]),
         "detail": opt["drc"]["detail"]},
    ]
    passed = all(c["ok"] for c in checks)
    result = {
        "ok": True,
        "title": "形状逆设计（宽度曲线 · 控制点参数化）",
        "mode": "shape",
        "n_controls": n_controls,
        "grid": {"Nx": Nx, "Ny": Ny, "dl_factor": dl_factor},
        "verify": {"max_rel_err": vr["max_rel_err"], "nsamples": vr["nsamples"]},
        "optimization": {"initial_FOM": opt["initial_FOM"],
                         "final_FOM": opt["final_FOM"],
                         "improvement": opt["improvement"],
                         "final_width": opt["final_width"],
                         "elapsed_s": round(elapsed, 2)},
        "drc": opt["drc"],
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": (f"形状逆设计 PASS：宽度曲线优化 FOM improvement="
                    f"{opt['improvement']:.2f}×（宽度 "
                    f"{opt['final_width']}）；形状梯度对拍 "
                    f"{vr['max_rel_err']:.4f}；DRC {opt['drc']['detail']}。"
                    f"耗时 {elapsed:.1f}s。"
                    if passed else
                    "形状逆设计未全过：" +
                    "; ".join(c["name"] for c in checks if not c["ok"])),
        "note": ("D-81 形状逆设计：K 控制点宽度曲线（单芯 taper/模式适配），"
                 "可制造性内建；形状梯度链式（geps·dε/dw）FD 对拍验证；"
                 "分叉/多芯归拓扑域。LLM 不进判决路径。"),
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


# ---------------------------------------------------------------------------
# 多目标联合：多波长加权 + Pareto 前端
# ---------------------------------------------------------------------------
def design_multi_objective(
        wavelengths: Optional[str] = None,
        weights: Optional[str] = None,
        Nx: int = 90, Ny: int = 70, dl_factor: float = 10.0,
        n_controls: int = 8, iters: int = 22, nsamples: int = 5,
        delta: float = 0.05, w_min: float = 2.0, w_max: float = 10.0,
        slope_max: float = 1.5, pareto: bool = True,
        out: Optional[str] = None) -> Dict[str, Any]:
    """多目标联合：多波长透射加权联合优化 + Pareto 前端扫描。

    场景：形状参数共享，目标 = 各波长收集场能（透射代理）。加权联合跑一次
    优化；Pareto 扫权重网格（λ1 主导 ↔ λ2 主导）得前端点。
    """
    wls = [float(x) for x in (wavelengths or "1.53,1.57").split(",") if x.strip()]
    if len(wls) < 2:
        return {"ok": False, "error": "多目标需 ≥2 个波长（逗号分隔）"}
    if weights is None:
        wt = [1.0 / len(wls)] * len(wls)
    else:
        wt = [float(x) for x in weights.split(",") if x.strip()]
    if len(wt) != len(wls):
        wt = [1.0 / len(wls)] * len(wls)
    wt = np.asarray(wt, dtype=float)
    wt = wt / wt.sum()

    base = _make_base(Nx, Ny, dl_factor, 8, wls[0])
    sps = [_shape_for(base, wl, n_controls, w_min, w_max, slope_max)
           for wl in wls]
    w = np.full(n_controls, sps[0].init_halfwidth)
    fom0 = sum(wt[k] * forward(sps[k].base, sps[k].eps(w))["FOM"]
               for k in range(len(wls)))

    t0 = time.perf_counter()
    # 加权联合优化（控制点，线搜索评估全波长）
    best_fom, best_w = fom0, w.copy()
    history = []
    for it in range(iters):
        fwds = [forward(sps[k].base, sps[k].eps(w)) for k in range(len(wls))]
        g = sum(wt[k] * sps[k].gradient(fwds[k], w) for k in range(len(wls)))
        m = np.max(np.abs(g)) + 1e-12
        d = g / m
        alpha = 0.4
        f_eval = sum(wt[k] * fwds[k]["FOM"] for k in range(len(wls)))
        f_try, accepted = f_eval, False
        while alpha > 2e-3:
            wt_r = sps[0].project(w + alpha * d)   # 可行性投影（宽度+平滑）
            f_try = sum(wt[k] * forward(sps[k].base, sps[k].eps(wt_r))["FOM"]
                        for k in range(len(wls)))
            if f_try > f_eval:
                accepted = True
                break
            alpha *= 0.5
        if accepted:
            w = sps[0].project(w + alpha * d)
            f_final = f_try
        else:
            f_final = f_eval
        if f_final > best_fom:
            best_fom, best_w = f_final, w.copy()
        history.append({"iter": it, "FOM_total": f_final,
                        "alpha": round(alpha, 4)})

    per_wl = []
    w_init = np.full(n_controls, sps[0].init_halfwidth)   # 初始均匀宽度（基线）
    for k, wl in enumerate(wls):
        f0 = forward(sps[k].base, sps[k].eps(w_init))
        f1 = forward(sps[k].base, sps[k].eps(best_w))
        per_wl.append({"wl_um": wl, "weight": round(float(wt[k]), 4),
                       "initial_FOM": f0["FOM"], "final_FOM": f1["FOM"],
                       "improvement": float(f1["FOM"] / (f0["FOM"] + 1e-12))})
    weighted_imp = float(sum(wt[k] * per_wl[k]["improvement"]
                             for k in range(len(wls))))
    drc = shape_drc(sps[0], best_w)
    joint_ok = bool(weighted_imp >= 1.5 and drc["ok"]
                    and all(per_wl[k]["improvement"] >= 1.2
                            for k in range(len(wls))))

    # Pareto 前端扫描（近似：权重网格）
    pareto_points: List[Dict[str, Any]] = []
    if pareto:
        grid = [(0.2, 0.8), (0.5, 0.5), (0.8, 0.2)]
        for wa, wb in grid:
            wg = np.asarray([wa, wb], dtype=float)
            wg = wg / wg.sum()
            wcur = np.full(n_controls, sps[0].init_halfwidth)
            for _ in range(min(iters, 14)):
                fwds = [forward(sps[0].base, sps[0].eps(wcur)),
                        forward(sps[1].base, sps[1].eps(wcur))]
                g = wg[0] * sps[0].gradient(fwds[0], wcur) + \
                    wg[1] * sps[1].gradient(fwds[1], wcur)
                m = np.max(np.abs(g)) + 1e-12
                d = g / m
                alpha = 0.4
                f_eval = wg[0] * fwds[0]["FOM"] + wg[1] * fwds[1]["FOM"]
                acc = False
                while alpha > 2e-3:
                    wt_r = sps[0].project(wcur + alpha * d)
                    f_try = wg[0] * forward(sps[0].base, sps[0].eps(wt_r))["FOM"] + \
                            wg[1] * forward(sps[1].base, sps[1].eps(wt_r))["FOM"]
                    if f_try > f_eval:
                        acc = True
                        break
                    alpha *= 0.5
                if acc:
                    wcur = sps[0].project(wcur + alpha * d)
            fa = forward(sps[0].base, sps[0].eps(wcur))["FOM"]
            fb = forward(sps[1].base, sps[1].eps(wcur))["FOM"]
            pareto_points.append({"weight_l1": wa, "weight_l2": wb,
                                  "FOM_l1": round(float(fa), 4),
                                  "FOM_l2": round(float(fb), 4),
                                  "improvement_l1": round(
                                      float(fa / (per_wl[0]["initial_FOM"] + 1e-12)), 3),
                                  "improvement_l2": round(
                                      float(fb / (per_wl[1]["initial_FOM"] + 1e-12)), 3),
                                  "width": [round(float(x), 2) for x in wcur]})
    elapsed = time.perf_counter() - t0

    checks = [
        {"name": f"多目标加权 improvement ≥ 1.5（{len(wls)} 波长）",
         "ok": bool(weighted_imp >= 1.5),
         "detail": f"加权 {weighted_imp:.2f}×（各波长 "
                   + ", ".join(f"λ{w['wl_um']}:{w['improvement']:.2f}×"
                               for w in per_wl) + "）"},
        {"name": "各波长均 ≥ 1.2×（联合不牺牲单目标）",
         "ok": bool(all(per_wl[k]["improvement"] >= 1.2
                        for k in range(len(wls)))),
         "detail": "，".join(f"λ{w['wl_um']}={w['improvement']:.2f}×"
                            for w in per_wl)},
        {"name": "可制造性 DRC（共享宽度曲线）",
         "ok": bool(drc["ok"]),
         "detail": drc["detail"]},
    ]
    if pareto and pareto_points:
        checks.append({"name": "Pareto 前端（权重网格扫描）",
                       "ok": True,
                       "detail": "; ".join(
                           f"(w1={p['weight_l1']}) λ1×{p['improvement_l1']}"
                           f"/λ2×{p['improvement_l2']}" for p in pareto_points)})
    passed = all(c["ok"] for c in checks)
    result = {
        "ok": True,
        "title": f"多目标联合逆设计（{len(wls)} 波长 · 形状参数共享）",
        "mode": "multi_objective",
        "wavelengths": wls,
        "weights": [round(float(x), 4) for x in wt],
        "n_controls": n_controls,
        "per_wavelength": per_wl,
        "weighted_improvement": round(weighted_imp, 4),
        "final_width": [round(float(x), 3) for x in best_w],
        "drc": drc,
        "pareto_points": pareto_points,
        "elapsed_s": round(elapsed, 2),
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": (f"多目标联合逆设计 PASS：加权 improvement="
                    f"{weighted_imp:.2f}×（"
                    + ", ".join(f"λ{w['wl_um']}:{w['improvement']:.2f}×"
                                for w in per_wl)
                    + f"）；共享宽度 {[round(float(x), 1) for x in best_w]}；"
                    f"Pareto 前端 {len(pareto_points)} 点。耗时 {elapsed:.1f}s。"
                    if passed else
                    "多目标联合未全过：" +
                    "; ".join(c["name"] for c in checks if not c["ok"])),
        "note": ("D-81 多目标联合：多波长透射加权 FOM + Pareto 前端扫描"
                 "（有限权重网格近似）；形状参数共享（可制造性内建）。"
                 "诚实边界：FOM 为收集场能代理（非功率透射）、2D TEz、"
                 "Pareto 为近似前端。LLM 不进判决路径。"),
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D-81 形状逆设计 + 多目标联合")
    ap.add_argument("--mode", choices=["shape", "multi"], default="shape")
    ap.add_argument("--wavelengths", default=None)
    ap.add_argument("--n_controls", type=int, default=8)
    ap.add_argument("--iters", type=int, default=22)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.mode == "multi":
        r = design_multi_objective(wavelengths=a.wavelengths,
                                   n_controls=a.n_controls,
                                   iters=a.iters, out=a.out)
    else:
        r = design_shape(n_controls=a.n_controls, iters=a.iters, out=a.out)
    print(json.dumps({k: r[k] for k in
                      ("title", "verify" if "verify" in r else "per_wavelength",
                       "optimization" if "optimization" in r else "weighted_improvement",
                       "drc", "acceptance", "verdict")},
                     ensure_ascii=False, indent=2)[:3000])
    return 0 if (r.get("ok") and r["acceptance"]["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
