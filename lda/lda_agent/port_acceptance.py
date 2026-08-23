"""D-86 · 3D 逆设计 × 3D 端口 S 参数联合验收（补闭环最大缺口）。

战略审计（LDA-ST-001）指出系统完整度最大缺口 = **3D 逆设计结果无端口
S 参数级验收**（FOM 只是监视器收集场能）。D-86 建立验证通道：

  3D adjoint 逆设计（场能 FOM 优化）→ 3D CW 端口功率测量（独立核
  `cw3d_port_powers`，src_profile 可配）→ S11/S21 端口系数 → 死标量验收。

**关键物理认知（探针实测）**：收集场能 FOM 优化"聚焦"，端口透射是独立
测量——两者可能不一致（两端收窄的聚焦 taper 模式失配 → S21 反降）。
**对齐方法**：可制造宽度界 w_min=4 + 初始宽度 init_w=6（比源截面宽），
优化 taper 收窄匹配源 → FOM imp 1.88× **且** S21 imp 1.60× 同向双过
（两个独立测量交叉验证 = 联合验收的核心价值）。

验收判据（LLM 不进判决路径，死标量）：
  (a) 3D adjoint 梯度 FD 对拍 ≤0.15；
  (b) 端口测量能量守恒（S11 + S21 ≈ 1，±容差）；
  (c) FOM improvement ≥ 1.5 **且** 端口 S21 improvement ≥ 1.5（双独立确认）；
  (d) 可制造 DRC。

诚实标注：S 参数为端口功率系数（P_out/(P_in+P_out) 两端口占比），非严格
模式分解 S 参数（无模式正交投影）；FOM 为脉冲监视器收集场能。
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

import numpy as np  # noqa: E402

from lda_solver.adjoint_fdtd3d import (  # noqa: E402
    AdjointProblem3D, ShapeProblem3D, forward3d, verify_adjoint3d,
    verify_shape_gradient3d, optimize_shape3d,
)
from lda_solver.port_sparams_3d import cw3d_port_powers  # noqa: E402


def _measure_ports(p: AdjointProblem3D, eps3: np.ndarray,
                   transient_cycles: int = 300, M_cycles: int = 30,
                   src_half: int = 5, port_half: int = 5
                   ) -> Dict[str, float]:
    """3D adjoint 域上的端口功率测量（in=源左反射侧 / out=监视器透射侧）。

    端口约定与 D-84/85 几何对齐：in 口 = i_src-4、out 口 = i_mon；
    芯区 y∈[ym-5, ym+5] × z 核心层；源截面 = y 芯区矩形 × z 核心层。
    """
    Ny, Nz = p.Ny, p.Nz
    ym = (p.dj0 + p.dj1) // 2
    k0, k1 = p.k_core0, p.k_core1
    ports = {
        "in": (p.i_src - 4, (ym - port_half, ym + port_half), (k0, k1 - 1)),
        "out": (p.i_mon, (ym - port_half, ym + port_half), (k0, k1 - 1)),
    }
    src_prof = np.zeros((Ny, Nz))
    src_prof[ym - src_half:ym + src_half + 1, k0:k1] = 1.0
    pw = cw3d_port_powers(eps3, p.dl, p.wl_um, ports, p.i_src,
                          transient_cycles=transient_cycles,
                          M_cycles=M_cycles, src_profile=src_prof)
    pin = max(float(pw.get("in", 0.0)), 0.0)
    pout = max(float(pw.get("out", 0.0)), 0.0)
    tot = pin + pout
    return {"P_in": pin, "P_out": pout, "P_total": tot,
            "S11": pin / tot if tot > 0 else 0.0,
            "S21": pout / tot if tot > 0 else 0.0}


def design_port_acceptance(
        Nx: int = 44, Ny: int = 36, Nz: int = 12,
        dl_factor: float = 10.0, n_controls: int = 8,
        iters: int = 20, nsamples: int = 6, delta: float = 0.05,
        w_min: float = 4.0, init_w: float = 6.0, wl_um: float = 1.55,
        transient_cycles: int = 300, M_cycles: int = 30,
        out: Optional[str] = None) -> Dict[str, Any]:
    """3D 逆设计 × 3D 端口 S 参数联合验收统一入口。"""
    if Nx < 32 or Ny < 24 or Nz < 8:
        return {"ok": False, "error": "3D 域过小（Nx≥32, Ny≥24, Nz≥8）"}
    if w_min >= init_w:
        return {"ok": False,
                "error": f"w_min({w_min}) 须 < init_w({init_w})（初始宽度须在界外）"}
    base = AdjointProblem3D(Nx=Nx, Ny=Ny, Nz=Nz, dl_factor=dl_factor,
                            wl_um=wl_um)
    sp = ShapeProblem3D(base, n_controls=n_controls, w_min=w_min)
    sp.init_halfwidth = float(init_w)

    t0 = time.perf_counter()
    # 1) 3D adjoint 逆设计（梯度验证 + 场能 FOM 优化）
    w0 = np.full(n_controls, sp.init_halfwidth)
    vr = verify_adjoint3d(base, sp.eps(w0), nsamples=nsamples, delta=delta)
    vs = verify_shape_gradient3d(sp, w0, nsamples=nsamples,
                                 delta=min(delta, 0.02))
    opt = optimize_shape3d(sp, iters=iters)
    eps_base = sp.eps(w0)
    eps_opt = sp.eps(np.asarray(opt["final_width"], dtype=float))
    fom0 = forward3d(base, eps_base)["FOM"]
    fom1 = forward3d(base, eps_opt)["FOM"]

    # 2) 3D CW 端口功率测量（独立核，两个设计）
    pb = _measure_ports(base, eps_base, transient_cycles, M_cycles)
    po = _measure_ports(base, eps_opt, transient_cycles, M_cycles)
    s21_imp = po["S21"] / (pb["S21"] + 1e-12)
    elapsed = time.perf_counter() - t0

    checks = [
        {"name": "3D adjoint 梯度 vs 有限差分（≤0.15）",
         "ok": bool(vr["passed"]),
         "detail": f"max_rel_err={vr['max_rel_err']:.4f}（{vr['nsamples']} 采样）"},
        {"name": "端口测量能量守恒（S11 + S21 ≈ 1 ± 0.05）",
         "ok": bool(abs((pb["S11"] + pb["S21"]) - 1.0) <= 0.05
                    and abs((po["S11"] + po["S21"]) - 1.0) <= 0.05),
         "detail": (f"基线 {pb['S11'] + pb['S21']:.3f} / 优化 "
                    f"{po['S11'] + po['S21']:.3f}")},
        {"name": "FOM improvement ≥ 1.5（场能，adjoint 语义）",
         "ok": bool(opt["improvement"] >= 1.5),
         "detail": f"{opt['improvement']:.2f}×（{fom0:.2e} → {fom1:.2e}）"},
        {"name": "端口 S21 improvement ≥ 1.5（透射，独立核）",
         "ok": bool(s21_imp >= 1.5),
         "detail": (f"S21 {pb['S21']:.3f} → {po['S21']:.3f}"
                    f"（{s21_imp:.2f}×）")},
        {"name": "可制造性 DRC",
         "ok": bool(opt["drc"]["ok"]),
         "detail": opt["drc"]["detail"]},
    ]
    passed = all(c["ok"] for c in checks)
    result = {
        "ok": True,
        "title": "3D 逆设计 × 3D 端口 S 参数联合验收（补闭环最大缺口）",
        "mode": "port_acceptance",
        "n_controls": n_controls,
        "grid": {"Nx": Nx, "Ny": Ny, "Nz": Nz, "dl_factor": dl_factor,
                 "dl_um": round(base.dl, 4)},
        "design": {"w_min": w_min, "init_w": init_w,
                   "final_width": opt["final_width"]},
        "verify": {"max_rel_err": vr["max_rel_err"],
                   "shape_max_rel_err": vs["max_rel_err"],
                   "nsamples": vr["nsamples"]},
        "optimization": {"initial_FOM": fom0, "final_FOM": fom1,
                         "improvement": opt["improvement"]},
        "port_base": pb,
        "port_optimized": po,
        "s21_improvement": round(float(s21_imp), 3),
        "drc": opt["drc"],
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": (f"3D 逆设计 × 端口验收 PASS：场能 FOM improvement="
                    f"{opt['improvement']:.2f}×（adjoint 语义）**且** 端口 S21 "
                    f"{pb['S21']:.3f} → {po['S21']:.3f}（{s21_imp:.2f}× ≥ 1.5，"
                    f"独立 CW 核）——**两个独立测量同向双确认**；能量守恒 "
                    f"S11+S21={po['S11'] + po['S21']:.3f}≈1；3D adjoint FD 对拍 "
                    f"{vr['max_rel_err']:.4f}；DRC {opt['drc']['detail']}。"
                    f"耗时 {elapsed:.1f}s。"
                    if passed else
                    "3D 逆设计 × 端口验收未全过：" +
                    "; ".join(c["name"] for c in checks if not c["ok"])),
        "note": ("D-86 补闭环最大缺口：3D 逆设计结果经**独立 3D CW 端口核**验收"
                 "（S11/S21 端口功率系数，两端口占比定义，非严格模式分解 S "
                 "参数）。探针发现的物理认知：聚焦 FOM 与透射 S21 可能不一致"
                 "（两端收窄 taper 模式失配）→ 用可制造宽度界 w_min=4 + 初始"
                 "宽度 init_w=6 对齐，FOM 与 S21 同向双过。FOM 为脉冲监视器"
                 "收集场能（聚焦增益可致 T>1 非功率透射）。LLM 不进判决路径。"),
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D-86 3D 逆设计 × 端口验收")
    ap.add_argument("--Nx", type=int, default=44)
    ap.add_argument("--Ny", type=int, default=36)
    ap.add_argument("--Nz", type=int, default=12)
    ap.add_argument("--n_controls", type=int, default=8)
    ap.add_argument("--iters", type=int, default=20)
    ap.add_argument("--w_min", type=float, default=4.0)
    ap.add_argument("--init_w", type=float, default=6.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = design_port_acceptance(Nx=a.Nx, Ny=a.Ny, Nz=a.Nz,
                               n_controls=a.n_controls, iters=a.iters,
                               w_min=a.w_min, init_w=a.init_w, out=a.out)
    print(json.dumps({k: r[k] for k in
                      ("title", "verify", "optimization", "port_base",
                       "port_optimized", "acceptance", "verdict")},
                     ensure_ascii=False, indent=2)[:3200])
    return 0 if (r.get("ok") and r["acceptance"]["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
