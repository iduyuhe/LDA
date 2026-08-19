"""LDA · L2-B Numba-CPU 加速核 · 与 run_fdtd3d_selfcheck.py 同 ORACLE/同公差 的 5/5 校验。

仅把后端从纯 numpy（fdtd3d.solve_spectrum / run_greens_test）替换为 Numba 加速核
（fdtd3d_numba.solve_spectrum_numba / run_greens_test_numba）；ORACLE（tmm.py 一维
退化 + 点源球面波 |Ez|·r）与公差完全一致 —— 用于验证"物理一致性 + 性能升维"双赢。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from lda.lda_solver.fdtd3d_numba import solve_spectrum_numba, run_greens_test_numba
from lda.lda_solver.tmm import solve_spectrum as tmm_solve_spectrum


def _tmm_T(layers, wls):
    out = tmm_solve_spectrum({"layers": layers, "wavelengths_um": wls})
    return list(out["transmission"])


def _report(name, layers, wls, tol):
    print(f"\n=== {name} ===")
    fd = solve_spectrum_numba({"layers": layers, "wavelengths_um": wls})
    tf = fd["transmission"]
    tt = _tmm_T(layers, wls)
    print(f"  {'wl(um)':>8} {'FDTD3D_T':>10} {'TMM_T':>9} {'delta':>8}")
    for w, a, b in zip(wls, tf, tt):
        print(f"  {w:>8.3f} {a:>10.4f} {b:>9.4f} {abs(a-b):>8.4f}")
    max_err = max(abs(a - b) for a, b in zip(tf, tt))
    ok = max_err < tol
    print(f"  max|ΔT| = {max_err:.4f}  -> {'PASS' if ok else 'FAIL'} (tol={tol})")
    return ok


def _report_greens(name, tol):
    print(f"\n=== {name} ===")
    amps = run_greens_test_numba(wl=2.0, n=1.0)
    print(f"  {'r':>5} {'|Ez|*r':>12}")
    vals = []
    for r, v in amps:
        print(f"  {r:>5} {v:>12.5f}")
        vals.append(v)
    mean = sum(vals) / len(vals)
    rel = [abs(v - mean) / mean for v in vals]
    max_rel = max(rel)
    ok = max_rel < tol
    print(f"  mean={mean:.5f}  max_rel_dev={max_rel:.4f}  "
          f"-> {'PASS' if ok else 'FAIL'} (tol={tol})")
    return ok


def main():
    print(">> LDA 自研 3D FDTD · Numba-CPU 加速核 · 物理定律锚交叉校验")
    print(">> ORACLE = TMM 多层膜解析解（一维退化极限）+ 点源球面波（真三维）")

    cases = []
    wls = [1.3, 1.4, 1.5, 1.6]
    layers_match = [(float('inf'), 1.44), (float('inf'), 1.44)]
    cases.append(("A. 匹配介质 (T≡1.0)", layers_match, wls, 0.02))

    layers_iface = [(float('inf'), 1.0), (float('inf'), 1.5)]
    cases.append(("B. 单界面 空气→玻璃 (T≡0.96)", layers_iface, wls, 0.04))

    layers_fp = [(float('inf'), 1.0), (2.0, 2.5), (float('inf'), 1.0)]
    wls_fp = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2]
    cases.append(("C. FP 标准具 n=2.5 d=2.0um (条纹)", layers_fp, wls_fp, 0.08))

    n_h, n_l, period = 3.48, 1.44, 0.50
    lam_b = 2 * ((n_h + n_l) / 2) * period
    layers_bg = ([(float('inf'), 1.44)] +
                 [(0.25, n_h), (0.25, n_l)] * 24 +
                 [(float('inf'), 1.44)])
    wls_bg = [1.9, 2.2, 2.46, 2.7, 3.0]
    cases.append((f"D. 布拉格光栅 (中心≈{lam_b:.2f}um 禁带)", layers_bg, wls_bg, 0.12))

    import time
    t0 = time.perf_counter()
    all_ok = True
    for name, layers, wls_c, tol in cases:
        ok = _report(name, layers, wls_c, tol)
        all_ok = all_ok and ok

    ok_g = _report_greens("E. 点源球面波 |Ez|·r 常数（真三维）", 0.20)
    all_ok = all_ok and ok_g
    elapsed = time.perf_counter() - t0

    print("\n" + "=" * 48)
    print(f">> 总耗时：{elapsed/60:.1f} min（Numba-CPU 加速核）")
    print(">> 总判定：", "PASS — 3D 自研核 + Numba 加速通过物理定律锚校验" if all_ok
          else "FAIL — 未通过校验，需排查")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
