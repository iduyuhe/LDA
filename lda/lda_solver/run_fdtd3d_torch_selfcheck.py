"""LDA · L3 自研 3D FDTD 核 · PyTorch 后端 · 物理定律锚交叉校验闭环。

与 run_fdtd3d_selfcheck.py 完全同构图、同 ORACLE（tmm.py 一维退化 + 点源
球面波 |Ez|·r）、同公差；仅把后端从纯 numpy（fdtd3d.py）换成 PyTorch 张量化
后端（fdtd3d_torch.py，device 自动选 cuda/cpu）。用于证明"GPU/CPU 张量后端
与 sovereign numpy 参考实现物理等价"。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from lda.lda_solver.fdtd3d_torch import (solve_spectrum_torch,
                                         run_greens_test_torch)
from lda.lda_solver.tmm import solve_spectrum as tmm_solve_spectrum
import torch


def _device():
    return 'cuda' if torch.cuda.is_available() else 'cpu'


def _tmm_T(layers, wls):
    out = tmm_solve_spectrum({"layers": layers, "wavelengths_um": wls})
    return list(out["transmission"])


def _report(name, layers, wls, tol, device):
    print(f"\n=== {name} ===")
    fd = solve_spectrum_torch({"layers": layers, "wavelengths_um": wls}, device=device)
    tf = fd["transmission"]
    tt = _tmm_T(layers, wls)
    print(f"  {'wl(um)':>8} {'FDTD_T':>10} {'TMM_T':>9} {'delta':>8}")
    for w, a, b in zip(wls, tf, tt):
        print(f"  {w:>8.3f} {a:>10.4f} {b:>9.4f} {abs(a-b):>8.4f}")
    max_err = max(abs(a - b) for a, b in zip(tf, tt))
    ok = max_err < tol
    print(f"  max|ΔT| = {max_err:.4f}  -> {'PASS' if ok else 'FAIL'} (tol={tol})")
    return ok


def _report_greens(name, tol, device):
    print(f"\n=== {name} ===")
    amps = run_greens_test_torch(wl=2.0, n=1.0, device=device)
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
    device = _device()
    print(f">> LDA 自研 3D FDTD · PyTorch 后端（device={device}）交叉校验")
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

    all_ok = True
    for name, layers, wls_c, tol in cases:
        ok = _report(name, layers, wls_c, tol, device)
        all_ok = all_ok and ok

    ok_g = _report_greens("E. 点源球面波 |Ez|·r 常数（真三维）", 0.20, device)
    all_ok = all_ok and ok_g

    print("\n" + "=" * 48)
    print(">> 总判定：", "PASS — 3D PyTorch 后端通过物理定律锚校验" if all_ok
          else "FAIL — 3D PyTorch 后端未通过校验，需排查")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
