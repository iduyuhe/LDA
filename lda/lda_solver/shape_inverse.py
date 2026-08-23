"""LDA · D-81 形状逆设计核（Track A 纵深：从 voxel 拓扑 → 连续几何形状）。

把 D-69/D-80 的 **voxel 拓扑逆设计**（逐体素密度二值化，可制造性靠后期
DRC 抽检）升级为 **形状逆设计**：几何由**连续宽度曲线 w(x)**（波导芯半宽
沿 x 的分布）参数化——K 个控制点 → 线性插值 → sigmoid 软边界介电分布。
形状导数经链式法则 dFOM/dw_k = Σ geps·dε/dw_k 得到，优化天然光滑、
控制点数量即特征尺寸（可制造性内建于参数化）。

与拓扑逆设计的本质差异（诚实标注）：
  - 拓扑：每个体素 0/1 自由度（~4k 体素），表达任意结构（分叉/谐振腔）；
  - 形状：K 个宽度控制点（~8-16），只表达**单芯宽度曲线**（taper/透镜/
    模式适配器）——不能表达分叉/多芯（Y 分束器归拓扑域）；
  - 形状的可制造性更好：边界连续、无孤立体素、宽度由上下界约束。

验收（LLM 不进判决路径，死标量）：
  (a) 形状梯度 vs 中心有限差分（控制点方向对拍）max_rel_err ≤ 0.15；
  (b) 目标 FOM improvement ≥ 1.5；
  (c) 可制造性 DRC：宽度 ∈ [w_min, w_max]（半宽界）、相邻控制点变化率
      受限于 slope_max（平滑约束）——不满足记 FAIL（设计不可制造）。
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

import numpy as np  # noqa: E402

from lda_solver.adjoint_fdtd import (  # noqa: E402
    AdjointProblem, forward, compute_gradient,
)


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


@dataclass
class ShapeProblem:
    """形状逆设计问题：控制点宽度曲线 + 软边界 + 基网格。

    复用 AdjointProblem 的 FDTD 域（源/监视器/海绵/设计区），形状芯居中于
    设计区中线（j_mid），每列半宽 w(x) 由 K 个控制点线性插值。
    """
    base: AdjointProblem
    n_controls: int = 8            # 控制点数量（特征尺寸自由度）
    w_min: float = 2.0             # 半宽下界（格，可制造）
    w_max: float = 10.0            # 半宽上界（格）
    slope_max: float = 1.5         # 相邻控制点最大变化（格/段，平滑约束）
    soft_t: float = 1.2            # 软边界厚度（格，sigmoid 宽度）
    init_halfwidth: float = 5.0    # 初始半宽（格）

    def __post_init__(self):
        p = self.base
        self.di0, self.di1 = p.di0, p.di1
        self.dj0, self.dj1 = p.dj0, p.dj1
        self.j_mid = (self.dj0 + self.dj1) // 2
        self.knots = np.linspace(self.di0, self.di1 - 1, self.n_controls)
        self.cols = np.arange(self.di0, self.di1)

    # ---- 可行性投影：宽度界 + 平滑约束（可制造性内建）----
    def project(self, w: np.ndarray) -> np.ndarray:
        """交替 clip 宽度界 + 贪心平滑相邻变化（正反两遍，迭代收敛）。"""
        w = np.asarray(w, dtype=float).copy()
        for _ in range(3):
            w = np.clip(w, self.w_min, self.w_max)
            if self.n_controls > 1:
                for i in range(1, self.n_controls):
                    if w[i] - w[i - 1] > self.slope_max:
                        w[i] = w[i - 1] + self.slope_max
                    elif w[i - 1] - w[i] > self.slope_max:
                        w[i] = w[i - 1] - self.slope_max
                for i in range(self.n_controls - 2, -1, -1):
                    if w[i] - w[i + 1] > self.slope_max:
                        w[i] = w[i + 1] + self.slope_max
                    elif w[i + 1] - w[i] > self.slope_max:
                        w[i] = w[i + 1] - self.slope_max
        return np.clip(w, self.w_min, self.w_max)

    # ---- 形状 → 介电 ----
    def width_at(self, w_ctl: np.ndarray) -> np.ndarray:
        """控制点 → 每列半宽（线性插值）。"""
        return np.interp(self.cols, self.knots, np.asarray(w_ctl, dtype=float))

    def eps(self, w_ctl: np.ndarray) -> np.ndarray:
        """控制点半宽 → 介电分布（sigmoid 软边界，可导）。"""
        p = self.base
        eps = np.full((p.Nx, p.Ny), p.eps_min)
        w_col = self.width_at(w_ctl)
        j = np.arange(self.dj0, self.dj1)
        t = self.soft_t
        for i, wc in zip(self.cols, w_col):
            d = wc - np.abs(j - self.j_mid)
            eps[i, j] = p.eps_min + (p.eps_max - p.eps_min) * _sigmoid(d / t)
        return eps

    # ---- 形状梯度（链式）----
    def gradient(self, fwd: dict, w_ctl: np.ndarray) -> np.ndarray:
        """dFOM/dw_k = Σ geps·dε/dw_k（控制点方向）。"""
        p = self.base
        geps = compute_gradient(p, fwd)
        K = self.n_controls
        j = np.arange(self.dj0, self.dj1)
        t = self.soft_t
        w_col = self.width_at(w_ctl)
        g = np.zeros(K)
        ks = self.knots
        for k in range(K):
            for i, wc in zip(self.cols, w_col):
                wgt = _interp_weight(i, ks, k, K)
                if wgt == 0.0:
                    continue
                d = wc - np.abs(j - self.j_mid)
                sd = _sigmoid(d / t)
                dsig_dw = (sd * (1.0 - sd)) / t
                g[k] += np.sum(geps[i, j] * (p.eps_max - p.eps_min)
                               * dsig_dw * wgt)
        return g


def _interp_weight(i: int, knots: np.ndarray, k: int, K: int) -> float:
    """列 i 对控制点 k 的线性插值权重。"""
    if K == 1:
        return 1.0
    x0, x1 = knots[0], knots[-1]
    if i <= x0:
        return 1.0 if k == 0 else 0.0
    if i >= x1:
        return 1.0 if k == K - 1 else 0.0
    seg = min(int((i - x0) / (x1 - x0) * (K - 1)), K - 2)
    frac = (i - knots[seg]) / (knots[seg + 1] - knots[seg])
    if k == seg:
        return 1.0 - frac
    if k == seg + 1:
        return frac
    return 0.0


# ---------------------------------------------------------------------------
# 验证：形状梯度 vs 控制点中心有限差分（方向对拍）
# ---------------------------------------------------------------------------
def verify_shape_gradient(sp: ShapeProblem, w_ctl: np.ndarray,
                          nsamples: int = 6, delta: float = 0.05,
                          seed: int = 12345) -> Dict[str, Any]:
    """对随机/均匀选取的控制点做中心差分，与形状梯度比方向误差。"""
    rng = np.random.default_rng(seed)
    K = sp.n_controls
    picks = sorted(rng.choice(K, size=min(nsamples, K), replace=False))
    fwd0 = forward(sp.base, sp.eps(w_ctl))
    gadj = sp.gradient(fwd0, w_ctl)
    rows = []
    for k in picks:
        wp = w_ctl.copy(); wp[k] += delta
        wm = w_ctl.copy(); wm[k] -= delta
        Fp = forward(sp.base, sp.eps(wp))["FOM"]
        Fm = forward(sp.base, sp.eps(wm))["FOM"]
        g_fd = (Fp - Fm) / (2.0 * delta)
        rows.append({"k": int(k), "g_adj": float(gadj[k]), "g_fd": float(g_fd)})
    # 归一化方向对拍（标定 K 于 |g_fd| 最大处）
    ref = max(rows, key=lambda r: abs(r["g_fd"]))
    Kcal = ref["g_adj"] / ref["g_fd"] if abs(ref["g_fd"]) > 1e-12 else 1.0
    errs = []
    for r in rows:
        pred = Kcal * r["g_fd"]
        errs.append(abs(r["g_adj"] - pred) / (abs(pred) + 1e-12))
    max_err = float(max(errs))
    return {"nsamples": len(rows), "delta": delta,
            "max_rel_err": max_err, "samples": rows,
            "passed": bool(max_err <= 0.15)}


# ---------------------------------------------------------------------------
# 可制造性 DRC（形状域）
# ---------------------------------------------------------------------------
def shape_drc(sp: ShapeProblem, w_ctl: np.ndarray) -> Dict[str, Any]:
    """形状可制造性检查：宽度界 + 平滑约束（相邻控制点变化率）。"""
    w = np.asarray(w_ctl, dtype=float)
    ok_w = bool(np.all(w >= sp.w_min) and np.all(w <= sp.w_max))
    if sp.n_controls > 1:
        slope = np.max(np.abs(np.diff(w)))
        ok_slope = bool(slope <= sp.slope_max)
    else:
        slope, ok_slope = 0.0, True
    ok = ok_w and ok_slope
    return {"ok": bool(ok), "w_min": sp.w_min, "w_max": sp.w_max,
            "width_range": [round(float(w.min()), 2), round(float(w.max()), 2)],
            "max_slope": round(float(slope), 3),
            "slope_max": sp.slope_max,
            "detail": (f"宽度∈[{w.min():.1f},{w.max():.1f}]（界 "
                       f"[{sp.w_min},{sp.w_max}]）；最大相邻变化 "
                       f"{slope:.2f}（≤{sp.slope_max}）")}


# ---------------------------------------------------------------------------
# 形状优化：控制点梯度上升 + 回溯线搜索（宽度界投影）
# ---------------------------------------------------------------------------
def optimize_shape(sp: ShapeProblem, iters: int = 30, step0: float = 0.4,
                   verbose: bool = False) -> Dict[str, Any]:
    """控制点梯度上升最大化监视器收集场能（宽度界投影 + 回溯线搜索）。

    返回 dict：history / final_width / improvement / passed / drc。
    """
    w = np.full(sp.n_controls, sp.init_halfwidth)
    fom0 = forward(sp.base, sp.eps(w))["FOM"]
    best_fom, best_w = fom0, w.copy()
    history = []
    for it in range(iters):
        fwd = forward(sp.base, sp.eps(w))
        g = sp.gradient(fwd, w)
        # 方向：最大分量归一化
        m = np.max(np.abs(g)) + 1e-12
        d = g / m
        alpha = step0
        f_eval = fwd["FOM"]
        f_try, accepted = f_eval, False
        while alpha > 2e-3:
            wt = sp.project(w + alpha * d)   # 可行性投影（宽度界 + 平滑）
            f_try = forward(sp.base, sp.eps(wt))["FOM"]
            if f_try > f_eval:
                accepted = True
                break
            alpha *= 0.5
        if accepted:
            w = sp.project(w + alpha * d)
            f_final = f_try
        else:
            f_final = f_eval
        if f_final > best_fom:
            best_fom, best_w = f_final, w.copy()
        history.append({"iter": it, "FOM": f_final, "T": fwd["T"],
                        "alpha": round(alpha, 4)})
        if verbose and (it % 5 == 0 or it == iters - 1):
            print(f"  it={it:3d} alpha={alpha:6.3f} FOM={f_final:.4e} "
                  f"T={fwd['T']:.4f}")

    fbf = forward(sp.base, sp.eps(best_w))
    improvement = fbf["FOM"] / (fom0 + 1e-12)
    drc = shape_drc(sp, best_w)
    return {
        "history": history,
        "final_width": [round(float(x), 3) for x in best_w],
        "final_T": fbf["T"],
        "final_FOM": fbf["FOM"],
        "initial_FOM": fom0,
        "improvement": float(improvement),
        "drc": drc,
        "passed": bool(improvement >= 1.5 and drc["ok"]),
        "note": ("形状逆设计：宽度曲线控制点（单芯 taper/模式适配），"
                 "可制造性内建（宽度界 + 平滑约束）；分叉/多芯归拓扑域。"),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="D-81 形状逆设计核")
    ap.add_argument("--n_controls", type=int, default=8)
    ap.add_argument("--iters", type=int, default=25)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    base = AdjointProblem(Nx=90, Ny=70, sponge=8, dl_factor=10)
    sp = ShapeProblem(base=base, n_controls=a.n_controls)
    w0 = np.full(a.n_controls, sp.init_halfwidth)
    vr = verify_shape_gradient(sp, w0, nsamples=6, delta=0.05)
    print(f"形状梯度 FD 对拍: max_rel_err={vr['max_rel_err']:.4f} "
          f"passed={vr['passed']}")
    opt = optimize_shape(sp, iters=a.iters, verbose=True)
    print(f"improvement={opt['improvement']:.2f}× passed={opt['passed']}")
    print(f"最终宽度曲线: {opt['final_width']}")
    print(f"DRC: {opt['drc']['detail']}")
    if a.out:
        rep = {"verify": vr, "opt": opt,
               "acceptance": {"passed": bool(vr["passed"] and opt["passed"])}}
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
