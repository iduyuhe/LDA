"""D-89 3D adjoint numba 性能基准：forward/梯度/优化链路加速比 + FOM 一致性。

运行：python run_perf_adjoint3d.py（需 numba 环境，如 envs/default；无 numba 时
报告 _NUMBA=False 并跳过加速比测量——回退本身就是验收项）。

输出：reports/perf_adjoint3d_d89.json
验收（死标量，LLM 不进判决）：
  (a) 大域（≥64）forward 加速比 ≥ 20×；
  (b) numba 与 numpy FOM 相对差 ≤ 1e-10（bit-level 一致性）；
  (c) 无 numba 环境优雅回退 numpy（_NUMBA=False 仍可用）。
"""
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_solver.adjoint_fdtd3d import (  # noqa: E402
    AdjointProblem3D, ShapeProblem3D, forward3d, compute_gradient3d,
    optimize_shape3d, _NUMBA,
)


def _timeit(fn, repeat=3):
    """计时：repeat 次取最小值（CPU turbo/缓存状态波动下最稳定）。"""
    best = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        r = fn()
        best = min(best, time.perf_counter() - t0)
    return best, r


def main() -> int:
    domains = [(44, 36, 12), (64, 52, 16), (80, 60, 20)]
    rows = []
    for (Nx, Ny, Nz) in domains:
        p = AdjointProblem3D(Nx=Nx, Ny=Ny, Nz=Nz)
        sp = ShapeProblem3D(p, n_controls=8)
        eps3 = sp.eps(np.full(8, sp.init_halfwidth))
        fwd_np = forward3d(p, eps3, backend="numpy")   # 预热 + 参考
        fwd_nb = forward3d(p, eps3, backend="numba")
        rel_fom = abs(fwd_nb["FOM"] - fwd_np["FOM"]) / fwd_np["FOM"]
        t_np_f, _ = _timeit(lambda: forward3d(p, eps3, backend="numpy"))
        t_nb_f, _ = _timeit(lambda: forward3d(p, eps3, backend="numba"))
        t_np_g, _ = _timeit(lambda: compute_gradient3d(p, fwd_np, backend="numpy"))
        t_nb_g, _ = _timeit(lambda: compute_gradient3d(p, fwd_np, backend="numba"))
        g_np = compute_gradient3d(p, fwd_np, backend="numpy")
        g_nb = compute_gradient3d(p, fwd_np, backend="numba")
        rel_g = np.abs(g_np - g_nb).max() / (np.abs(g_np).max() + 1e-12)
        rows.append({
            "domain": f"{Nx}x{Ny}x{Nz}",
            "fwd_numpy_s": round(t_np_f, 4), "fwd_numba_s": round(t_nb_f, 4),
            "fwd_speedup": round(t_np_f / t_nb_f, 1),
            "fom_rel": float(rel_fom),
            "grad_numpy_s": round(t_np_g, 4), "grad_numba_s": round(t_nb_g, 4),
            "grad_speedup": round(t_np_g / t_nb_g, 1),
            "grad_rel": float(rel_g),
        })
        print(f"{Nx}x{Ny}x{Nz}: FWD {rows[-1]['fwd_speedup']}x "
              f"({rows[-1]['fwd_numpy_s']}s->{rows[-1]['fwd_numba_s']}s) "
              f"FOM rel={rel_fom:.1e} | GRAD {rows[-1]['grad_speedup']}x "
              f"rel={rel_g:.1e}")

    # 优化链路加速比（64 域，iters=4——大域才是 numba 主战场）
    opt_row = None
    if _NUMBA:
        p = AdjointProblem3D(Nx=64, Ny=52, Nz=16)
        sp = ShapeProblem3D(p, n_controls=8)
        t_nb, opt_nb = _timeit(lambda: optimize_shape3d(sp, iters=4))
        p2 = AdjointProblem3D(Nx=64, Ny=52, Nz=16)
        sp2 = ShapeProblem3D(p2, n_controls=8)
        t_np, opt_np = _timeit(lambda: optimize_shape3d(sp2, iters=4,
                                                        backend="numpy"))
        opt_row = {
            "domain": "64x52x16", "iters": 4,
            "opt_numpy_s": round(t_np, 2), "opt_numba_s": round(t_nb, 2),
            "opt_speedup": round(t_np / t_nb, 1),
            "imp_numpy": round(float(opt_np["improvement"]), 3),
            "imp_numba": round(float(opt_nb["improvement"]), 3),
        }
        print(f"优化链路: {opt_row['opt_speedup']}x "
              f"({opt_row['opt_numpy_s']}s->{opt_row['opt_numba_s']}s) "
              f"imp {opt_row['imp_numpy']}=={opt_row['imp_numba']}")

    # 最大域（80x60x20）forward 加速比 ≥ 20× 验收（大域是 numba 主战场）
    max_domain = rows[-1]
    speedup_ok = bool(_NUMBA and max_domain["fwd_speedup"] >= 20.0)
    consistent = bool(all(r["fom_rel"] <= 1e-10 for r in rows))
    report = {
        "title": "D-89 3D adjoint numba 性能基准",
        "numba_available": bool(_NUMBA),
        "rows": rows,
        "optimization": opt_row,
        "acceptance": {
            "passed": bool(speedup_ok and consistent),
            "checks": {
                "max_domain_forward_speedup_ge_20x": speedup_ok,
                "fom_bit_consistency_le_1e-10": consistent,
            },
        },
        "verdict": ("最大域 forward ≥20× + FOM bit-level 一致" if
                    (speedup_ok and consistent) else "未达标"),
    }
    out = os.path.join(_HERE, "reports", "perf_adjoint3d_d89.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[written] {out}")
    print(f"PASS: {report['acceptance']['passed']}")
    return 0 if report["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
