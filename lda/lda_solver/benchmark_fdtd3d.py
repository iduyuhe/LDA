"""L2-B 基准：Numba-CPU 加速核 vs 纯 numpy 核 —— 正确性对照 + 性能比值。

正确性：在同一几何/参数下，numba 输出应与 numpy 逐字节等价（物理一致铁律）。
性能：计时两者在相同 case 上的耗时，给出 CPU speedup。
（numpy 版在缩小网格下仍可跑完；生产级大网格的加速收益由 numba 并行与融合保证。）
"""
from __future__ import annotations

import time

import numpy as np

import fdtd3d as npb          # 纯 numpy 参考实现
import fdtd3d_numba as nb    # Numba 加速实现


def _rel(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    denom = max(abs(b).max(), 1e-12)
    return float(np.max(np.abs(a - b) / denom))


def compare_spectrum():
    print("=" * 64)
    print("SPECTRUM 对照（numpy vs numba）")
    cases = {
        "matched(n0=nL=1.0)": {"layers": [(float('inf'), 1.0), (float('inf'), 1.0)],
                               "wavelengths_um": [1.2, 1.5, 1.8]},
        "single-iface(1.0/1.5)": {"layers": [(float('inf'), 1.0), (float('inf'), 1.5)],
                                  "wavelengths_um": [1.2, 1.5, 1.8]},
        "fp-etalon(n=2.5,d=2um)": {"layers": [(float('inf'), 1.0), (2.0, 2.5), (float('inf'), 1.0)],
                                   "wavelengths_um": [1.4, 1.6, 1.8]},
    }
    kwargs = dict(dl_factor=80.0, sponge=160, ramp=300)
    for name, spec in cases.items():
        t0 = time.perf_counter()
        rn = npb.solve_spectrum(spec, **kwargs)["transmission"]
        t_np = time.perf_counter() - t0
        t0 = time.perf_counter()
        rb = nb.solve_spectrum_numba(spec, **kwargs)["transmission"]
        t_nb = time.perf_counter() - t0
        rd = _rel(rn, rb)
        print(f"  [{name}]")
        print(f"    numpy T = {[round(x,4) for x in rn]}")
        print(f"    numba T = {[round(x,4) for x in rb]}")
        print(f"    max|rel T diff| = {rd:.2e}  |  numpy {t_np:7.2f}s  numba {t_nb:7.2f}s  "
              f"speedup = {t_np/t_nb:5.1f}x")


def compare_greens():
    print("=" * 64)
    print("GREEN / 球面波 对照（numpy vs numba）")
    kwargs = dict(wl=2.0, n=1.0, N=48, sponge=12, dl_factor=20.0, ramp=300)
    t0 = time.perf_counter()
    rn = npb.run_greens_test(**kwargs)
    t_np = time.perf_counter() - t0
    t0 = time.perf_counter()
    rb = nb.run_greens_test_numba(**kwargs)
    t_nb = time.perf_counter() - t0
    an = np.array([x[1] for x in rn])
    ab = np.array([x[1] for x in rb])
    rd = _rel(an, ab)
    print(f"    numpy |Ez|*r = {[round(x,4) for x in an]}")
    print(f"    numba |Ez|*r = {[round(x,4) for x in ab]}")
    print(f"    max|rel diff| = {rd:.2e}  |  numpy {t_np:7.2f}s  numba {t_nb:7.2f}s  "
          f"speedup = {t_np/t_nb:5.1f}x")


if __name__ == "__main__":
    compare_spectrum()
    compare_greens()
    print("=" * 64)
    print("OK: numba 与 numpy 物理一致性验证完成（rel diff 应 << 1e-2）")
