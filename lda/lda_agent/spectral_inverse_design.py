"""D-80 · 谱形目标逆设计（Track A 深化 · 目标从「收集场能」泛化到谱形/分束/模式）。

把 D-69/D-70 的伴随梯度拓扑逆设计从「单孔径收集场能最大化」泛化为三类
**谱形目标 FOM**（逼近商业 EDA adjoint 逆设计核心卖点）：

  ① split_ratio（分束比）: 双输出监视器，FOM=(E_A+ε)^a·(E_B+ε)^b，a:b=target_ratio
     —— 优化后 FDTD 实测分束比命中 target_ratio ± 0.10；
  ② mode_match（模式匹配）: 目标场分布投影，FOM=proj²/‖p‖²，优化聚焦到目标模场；
  ③ spectrum（谱形/多波长）: FOM=Σ w_λ·FOM_λ，多波长加权联合优化
     —— 谱形目标 = 设计对目标波长带整体可用（各波长均提升）。

统一闭环（LLM 不进判决路径，死标量验收）：
  (a) adjoint vs 中心有限差分方向对拍 max_rel_err ≤ 0.15（梯度正确性锚）；
  (b) 目标 FOM improvement ≥ 1.5；
  (c) split_ratio 追加：分束比 err ≤ 0.10。

诚实边界：FOM 为脉冲源监视器孔径收集场能（聚焦增益可致 T>1，非功率透射）；
窄带谱形目标（波长带内网格色散均匀）为物理可行窗口；2D TEz 近似。
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

from lda_solver.adjoint_fdtd import (  # noqa: E402
    AdjointProblem, verify_adjoint, optimize_topology, spectrum_optimize,
)


def design_spectral(
        target_type: str = "split_ratio",
        target_ratio: float = 0.5,
        wavelengths: Optional[str] = None,
        Nx: int = 90, Ny: int = 80, dl_factor: float = 12.0,
        iters: int = 25, nsamples: int = 6, delta: float = 0.03,
        step0: float = 0.5, beta_max: float = 10.0,
        wl_um: float = 1.55, sponge: int = 8,
        mode_profile_mode: str = "flat",
        out: Optional[str] = None) -> Dict[str, Any]:
    """D-80 谱形目标逆设计统一入口（返回死标量验收报告）。"""
    if target_type not in ("field_energy", "split_ratio", "mode_match",
                           "spectrum"):
        return {"ok": False, "error": f"未知 target_type={target_type}"
                                      f"（须 field_energy/split_ratio/"
                                      f"mode_match/spectrum）"}

    # 构造问题（split_ratio 双监视器默认几何）
    geo: Dict[str, Any] = dict(Nx=Nx, Ny=Ny, dl_factor=dl_factor,
                               sponge=sponge, wl_um=wl_um,
                               target_type=target_type)
    if target_type == "split_ratio":
        geo["target_ratio"] = float(target_ratio)
    problem = AdjointProblem(**geo)
    if problem.design_mask.sum() == 0:
        return {"ok": False, "error": "设计区为空"}
    if target_type == "mode_match":
        span = problem.y_mon1 - problem.y_mon0
        if mode_profile_mode == "flat":
            problem.mode_profile = np.ones(span)
        elif mode_profile_mode == "gauss":
            x = np.linspace(-1.0, 1.0, span)
            problem.mode_profile = np.exp(-x ** 2 / 0.2)
        else:
            return {"ok": False,
                    "error": f"未知 mode_profile_mode={mode_profile_mode}"}

    # 均匀平板初值
    eps0 = np.full((problem.Nx, problem.Ny), problem.eps_min)
    eps0[problem.design_mask] = (problem.eps_min + problem.eps_max) / 2.0

    t0 = time.perf_counter()
    # ① 梯度锚：FD 对拍
    vr = verify_adjoint(problem, eps0, nsamples=nsamples, delta=delta)

    # ② 优化
    if target_type == "spectrum":
        wls = [float(x) for x in
               (wavelengths or "1.53,1.55,1.57").split(",") if x.strip()]
        opt = spectrum_optimize(problem, eps0, wavelengths_um=wls,
                                iters=iters, step0=step0, beta_max=beta_max)
    else:
        opt = optimize_topology(problem, eps0, iters=iters, step0=step0,
                                beta_max=beta_max)
    elapsed = time.perf_counter() - t0

    # ③ 死标量验收
    ok_anchor = bool(vr["passed"])
    ok_gain = bool(opt["passed"])
    ratio_info: Dict[str, Any] = {}
    if target_type == "split_ratio":
        ratio_info = {"final_ratio": opt.get("final_ratio"),
                      "target_ratio": opt.get("target_ratio"),
                      "ratio_err": opt.get("ratio_err"),
                      "ratio_ok": bool(opt.get("ratio_err", 1.0) <= 0.10)}
    checks: List[Dict[str, Any]] = [
        {"name": "adjoint 梯度 vs 有限差分（max_rel_err ≤ 0.15）",
         "ok": ok_anchor,
         "detail": f"max_rel_err={vr['max_rel_err']:.4f}（{vr['nsamples']} 样本）"},
        {"name": f"目标 FOM improvement ≥ 1.5（{target_type}）",
         "ok": ok_gain,
         "detail": (f"improvement={opt['improvement']:.2f}×"
                    if target_type != "spectrum" else
                    f"加权 {opt['weighted_improvement']:.2f}×（各波长 "
                    + ", ".join(f"{w['wl_um']}:{w['improvement']:.2f}×"
                                for w in opt["per_wavelength"]) + "）")},
    ]
    if target_type == "split_ratio":
        checks.append({"name": "分束比命中 target ± 0.10",
                       "ok": bool(ratio_info["ratio_ok"]),
                       "detail": (f"FDTD 实测 {ratio_info['final_ratio']:.3f} vs "
                                  f"目标 {ratio_info['target_ratio']}（err="
                                  f"{ratio_info['ratio_err']:.3f}）")})
    passed = all(c["ok"] for c in checks)

    # ④ 结果汇总
    result = {
        "ok": True,
        "title": f"谱形目标逆设计（{target_type}）",
        "target_type": target_type,
        "target_ratio": target_ratio,
        "grid": {"Nx": Nx, "Ny": Ny, "dl_factor": dl_factor,
                 "design_voxels": int(problem.design_mask.sum())},
        "geometry": {"i_src": problem.i_src, "i_mon": problem.i_mon,
                     "mon_y": [problem.y_mon0, problem.y_mon1],
                     "mon2_y": ([problem.y2_mon0, problem.y2_mon1]
                                if target_type == "split_ratio" else None)},
        "verify": {"max_rel_err": vr["max_rel_err"],
                   "mean_rel_err": vr["mean_rel_err"],
                   "nsamples": vr["nsamples"]},
        "optimization": {
            "initial_FOM": (opt["initial_FOM"] if target_type != "spectrum"
                            else opt["initial_FOM_total"]),
            "final_FOM": (opt["final_FOM"] if target_type != "spectrum"
                          else opt["final_FOM_total"]),
            "improvement": (opt["improvement"] if target_type != "spectrum"
                            else opt["weighted_improvement"]),
            "iters": iters, "elapsed_s": round(elapsed, 2),
            **({"final_ratio": opt.get("final_ratio"),
                "target_ratio": opt.get("target_ratio"),
                "ratio_err": opt.get("ratio_err")}
               if target_type == "split_ratio" else {}),
            **({"per_wavelength": opt["per_wavelength"],
                "weighted_improvement": opt["weighted_improvement"]}
               if target_type == "spectrum" else {}),
        },
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": (f"谱形目标逆设计（{target_type}）PASS："
                    + ("分束比 " if target_type == "split_ratio" else "")
                    + f"FOM improvement={opt['improvement'] if target_type != 'spectrum' else opt['weighted_improvement']:.2f}×"
                    + (f"，实测分束比 {opt['final_ratio']:.3f}（target {target_ratio}）"
                       if target_type == "split_ratio" else "")
                    + f"；adjoint 对拍 {vr['max_rel_err']:.4f}；"
                    + f"耗时 {elapsed:.1f}s。"
                    if passed else
                    "谱形目标逆设计未全过：" +
                    "; ".join(c["name"] for c in checks if not c["ok"])),
        "note": ("D-80 目标泛化：field_energy（D-70 收集场能）/ split_ratio"
                 "（分束比）/ mode_match（模式匹配）/ spectrum（多波长谱形）。"
                 "诚实边界：FOM 为脉冲源监视器收集场能（T>1 聚焦增益，非功率"
                 "透射）；窄带谱形窗口物理可行（网格色散均匀）；2D TEz 近似。"
                 "LLM 不进判决路径。"),
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D-80 谱形目标逆设计")
    ap.add_argument("--target_type", default="split_ratio",
                    choices=["field_energy", "split_ratio", "mode_match",
                             "spectrum"])
    ap.add_argument("--target_ratio", type=float, default=0.5)
    ap.add_argument("--wavelengths", default=None, help="谱形目标波长(µm,逗号)")
    ap.add_argument("--Nx", type=int, default=90)
    ap.add_argument("--Ny", type=int, default=80)
    ap.add_argument("--iters", type=int, default=25)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = design_spectral(
        target_type=a.target_type, target_ratio=a.target_ratio,
        wavelengths=a.wavelengths, Nx=a.Nx, Ny=a.Ny, iters=a.iters,
        out=a.out)
    print(json.dumps({k: r[k] for k in
                      ("title", "verify", "optimization", "acceptance",
                       "verdict")}, ensure_ascii=False, indent=2))
    return 0 if (r.get("ok") and r["acceptance"]["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
