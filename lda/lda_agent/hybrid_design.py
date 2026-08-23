"""D-82/D-83 · 混合逆设计统一入口（形状主干 + 拓扑微调带）。

D-82 单目标混合逆设计（`design_hybrid`）+ **D-83 多波长加权联合**
（`design_hybrid_multi`：混合参数化 × 多波长谱形目标，含纯形状多波长
基线对比 + Pareto 前端）——Track A 参数化×目标矩阵全打通。
死标量验收：FD 对拍 / improvement / 混合≥纯形状 / 各波长 ≥1.2 / DRC。
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
    optimize_hybrid_multi,
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


def _hybrid_for(base: AdjointProblem, wl_um: float, n_controls: int,
                topo_band: Tuple[float, float]) -> HybridProblem:
    """多波长 HybridProblem：复制 base 固定 dl 只变 omega（D-80 教训）。"""
    import copy
    b = copy.deepcopy(base)
    if abs(wl_um - b.wl_um) > 1e-9:
        b.wl_um = float(wl_um)
        b.omega = 2.0 * np.pi / float(wl_um)
        b.period_steps = int(round(2.0 * np.pi / (b.omega * b.dt)))
    return HybridProblem(base=b, n_controls=n_controls, topo_band=topo_band)


def _verify_hybrid_multi(hps, w_ctl, rho, weights, nsamples=8, delta=0.02):
    """多波长联合 FOM 的混合梯度 FD 对拍（形状控制点 + 拓扑体素）。

    rho 用 0.5 远离边界（D-82 教训：ρ=0 时 -δ clip 产生单边差分假象）。
    """
    nwl = len(hps)
    wt = np.asarray(weights, dtype=float) / np.asarray(weights).sum()
    K = hps[0].n_controls

    def F(w_, r_):
        return sum(wt[k] * forward(hps[k].base, hps[k].eps(w_, r_))["FOM"]
                   for k in range(nwl))

    fwd = [forward(hps[k].base, hps[k].eps(w_ctl, rho)) for k in range(nwl)]
    g_joint = np.concatenate([
        sum(wt[k] * hps[k].gradient(fwd[k], w_ctl, rho)[0] for k in range(nwl)),
        sum(wt[k] * hps[k].gradient(fwd[k], w_ctl, rho)[1] for k in range(nwl))])
    rng = np.random.default_rng(7)
    s_picks = sorted(rng.choice(K, size=min(nsamples // 2, K), replace=False))
    n_t = hps[0].n_topo
    t_pool = sorted(rng.choice(n_t, size=min(400, n_t), replace=False))
    t_picks = sorted(rng.choice(len(t_pool), size=min(nsamples // 2, len(t_pool)),
                                replace=False))
    rows = []
    for k in s_picks:
        wp = w_ctl.copy(); wp[k] += delta
        wm = w_ctl.copy(); wm[k] -= delta
        rows.append({"kind": "shape", "idx": int(k), "g_adj": float(g_joint[k]),
                     "g_fd": float((F(wp, rho) - F(wm, rho)) / (2 * delta))})
    for ti in t_picks:
        idx = int(t_pool[ti])
        rp = rho.copy(); rp[idx] += delta
        rm = rho.copy(); rm[idx] -= delta
        rows.append({"kind": "topo", "idx": idx,
                     "g_adj": float(g_joint[K + idx]),
                     "g_fd": float((F(w_ctl, rp) - F(w_ctl, rm)) / (2 * delta))})
    ga = np.array([r["g_adj"] for r in rows])
    gf = np.array([r["g_fd"] for r in rows])
    max_rel = float(np.abs(ga - gf).max() / (np.abs(gf).max() + 1e-12))
    return {"rows": rows, "max_rel_err": max_rel, "nsamples": len(rows),
            "passed": bool(max_rel <= 0.15)}


def design_hybrid_multi(
        wavelengths: Optional[str] = None,
        weights: Optional[str] = None,
        Nx: int = 90, Ny: int = 70, dl_factor: float = 10.0,
        n_controls: int = 8, iters: int = 18, nsamples: int = 8,
        delta: float = 0.02, topo_wgt: float = 0.6,
        topo_band: str = "2.5,7.5", wl_um: float = 1.55,
        pareto: bool = True, out: Optional[str] = None) -> Dict[str, Any]:
    """D-83 混合参数化 × 多波长加权联合统一入口（含纯形状基线 + Pareto）。

    参数化矩阵全打通：参数化 ∈ {拓扑, 形状, 混合} × 目标 ∈ {单场能,
    谱形目标, 多波长}——本入口 = 混合 × 多波长（Track A 纵深收官件）。
    死标量验收：FD 对拍 ≤0.15 + 加权 improvement ≥1.5 + 各波长 ≥1.2 +
    混合 ≥ 纯形状多波长基线（增益 ≥1.0）+ DRC。
    """
    lo, hi = [float(x) for x in topo_band.split(",")]
    if lo >= hi:
        return {"ok": False, "error": f"拓扑带非法：{topo_band}（须 lo<hi）"}
    wls = [float(x) for x in (wavelengths or "1.53,1.57").split(",")
           if x.strip()]
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

    base = AdjointProblem(Nx=Nx, Ny=Ny, dl_factor=dl_factor, sponge=8,
                          wl_um=wl_um)
    hps = [_hybrid_for(base, wl, n_controls, (lo, hi)) for wl in wls]
    K, n_t = hps[0].n_controls, hps[0].n_topo
    w0 = np.full(K, hps[0].init_halfwidth)
    rho0 = np.full(n_t, 0.5)   # 远离边界（FD 对拍用）

    t0 = time.perf_counter()
    vr = _verify_hybrid_multi(hps, w0, rho0, wt, nsamples=nsamples,
                              delta=delta)
    base_opt = optimize_hybrid_multi(hps, wt, iters=iters, topo_wgt=0.0)
    opt = optimize_hybrid_multi(hps, wt, iters=iters, topo_wgt=topo_wgt,
                                baseline=base_opt)
    elapsed = time.perf_counter() - t0

    # Pareto 前端（权重网格，混合参数化）
    pareto_points: List[Dict[str, Any]] = []
    if pareto and len(wls) == 2:
        for wa, wb in ((0.2, 0.8), (0.5, 0.5), (0.8, 0.2)):
            wg = np.asarray([wa, wb], dtype=float)
            wg = wg / wg.sum()
            po = optimize_hybrid_multi(hps, wg, iters=min(iters, 12),
                                       topo_wgt=topo_wgt)
            pareto_points.append({
                "weights": [float(wg[0]), float(wg[1])],
                "improvements": [round(p["improvement"], 3)
                                 for p in po["per_wavelength"]],
                "weighted_improvement": po["weighted_improvement"]})

    checks = [
        {"name": "混合×多波长联合梯度 vs 有限差分（≤0.15）",
         "ok": bool(vr["passed"]),
         "detail": f"max_rel_err={vr['max_rel_err']:.4f}（{vr['nsamples']} 采样）"},
        {"name": "加权 FOM improvement ≥ 1.5",
         "ok": bool(opt["weighted_improvement"] >= 1.5),
         "detail": (f"{opt['weighted_improvement']}×（初始 "
                    f"{opt['initial_FOM']:.2e} → {opt['final_FOM']:.2e}）")},
        {"name": "各波长 improvement ≥ 1.2",
         "ok": bool(all(p["improvement"] >= 1.2
                        for p in opt["per_wavelength"])),
         "detail": ", ".join(f"λ{p['wl_um']}:{p['improvement']:.2f}×"
                             for p in opt["per_wavelength"])},
        {"name": "混合 ≥ 纯形状多波长基线（拓扑增益）",
         "ok": bool(opt.get("gain_over_shape") is None
                    or opt["gain_over_shape"] >= 1.0),
         "detail": (f"混合 {opt['weighted_improvement']}× vs 纯形状 "
                    f"{opt.get('baseline_shape_improvement', 0)}×"
                    + (f"（增益 {opt['gain_over_shape']}×）"
                       if opt.get("gain_over_shape") is not None else ""))},
        {"name": "可制造性 DRC（形状宽度 + 平滑）",
         "ok": bool(opt["drc"]["ok"]),
         "detail": opt["drc"]["detail"]},
    ]
    passed = all(c["ok"] for c in checks)
    result = {
        "ok": True,
        "title": "混合参数化 × 多波长加权联合（Track A 纵深收官）",
        "mode": "hybrid_multi",
        "wavelengths": wls,
        "weights": [round(float(x), 4) for x in wt],
        "n_controls": n_controls,
        "n_topo_voxels": n_t,
        "topo_band": [lo, hi],
        "grid": {"Nx": Nx, "Ny": Ny, "dl_factor": dl_factor},
        "verify": {"max_rel_err": vr["max_rel_err"], "nsamples": vr["nsamples"]},
        "optimization": {"initial_FOM": opt["initial_FOM"],
                         "final_FOM": opt["final_FOM"],
                         "weighted_improvement":
                             opt["weighted_improvement"],
                         "per_wavelength": opt["per_wavelength"],
                         "final_width": opt["final_width"],
                         "topo_fill_frac": opt["topo_fill_frac"],
                         "topo_rho_max": opt["topo_rho_max"],
                         "baseline_shape_improvement":
                             opt.get("baseline_shape_improvement"),
                         "gain_over_shape": opt.get("gain_over_shape"),
                         "elapsed_s": round(elapsed, 2)},
        "pareto_points": pareto_points,
        "drc": opt["drc"],
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": (f"混合×多波长联合 PASS：加权 improvement="
                    f"{opt['weighted_improvement']}×（纯形状多波长基线 "
                    f"{opt.get('baseline_shape_improvement', 0)}×，混合增益 "
                    f"{opt.get('gain_over_shape', 1.0)}×）；逐波长 "
                    + "; ".join(f"λ{p['wl_um']}:{p['improvement']:.2f}×"
                                for p in opt["per_wavelength"])
                    + f"；混合梯度对拍 {vr['max_rel_err']:.4f}；DRC "
                    + opt["drc"]["detail"] + f"；Pareto 前端 "
                    f"{len(pareto_points)} 点。耗时 {elapsed:.1f}s。"
                    if passed else
                    "混合×多波长联合未全过：" +
                    "; ".join(c["name"] for c in checks if not c["ok"])),
        "note": ("D-83 参数化×目标矩阵全打通：参数化∈{拓扑,形状,混合} × "
                 "目标∈{单场能,谱形目标,多波长}。分块归一化保证拓扑带参与度"
                 "。诚实边界：3D 形状需 3D adjoint 核（归后续）；FOM 为收集"
                 "场能（T>1 聚焦增益非功率透射）；2D TEz。LLM 不进判决路径。"),
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D-82/D-83 混合逆设计")
    ap.add_argument("--mode", default="hybrid",
                    choices=["hybrid", "multi"])
    ap.add_argument("--n_controls", type=int, default=8)
    ap.add_argument("--iters", type=int, default=20)
    ap.add_argument("--topo_band", default="2.5,7.5")
    ap.add_argument("--wavelengths", default=None,
                    help="多波长模式：逗号分隔（如 1.53,1.57）")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    kw = dict(n_controls=a.n_controls, iters=a.iters,
              topo_band=a.topo_band, out=a.out)
    if a.mode == "multi":
        r = design_hybrid_multi(wavelengths=a.wavelengths, **kw)
    else:
        r = design_hybrid(**kw)
    print(json.dumps({k: r[k] for k in
                      ("title", "verify", "optimization", "drc",
                       "acceptance", "verdict")},
                     ensure_ascii=False, indent=2)[:3000])
    return 0 if (r.get("ok") and r["acceptance"]["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
