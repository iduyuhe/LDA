"""3D FDTD 快速诊断：每个结构化用例取 1-2 个波长，验证 2x 过阻尼修复。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from lda.lda_solver.fdtd3d import solve_spectrum, run_greens_test
from lda.lda_solver.tmm import solve_spectrum as tmm_solve_spectrum


def check(name, layers, wls, tol):
    fd = solve_spectrum({"layers": layers, "wavelengths_um": wls})
    tt = tmm_solve_spectrum({"layers": layers, "wavelengths_um": wls})["transmission"]
    print(f"\n=== {name} ===")
    maxerr = 0.0
    for w, a, b in zip(wls, fd["transmission"], tt):
        print(f"  wl={w:.3f}  FDTD3D={a:.4f}  TMM={b:.4f}  d={abs(a-b):.4f}")
        maxerr = max(maxerr, abs(a - b))
    ok = maxerr < tol
    print(f"  max|dT|={maxerr:.4f} -> {'PASS' if ok else 'FAIL'} (tol={tol})")
    return ok


def main():
    allok = True
    allok &= check("B 单界面", [(float('inf'), 1.0), (float('inf'), 1.5)],
                   [1.3, 1.5], 0.04)
    allok &= check("C FP", [(float('inf'), 1.0), (2.0, 2.5), (float('inf'), 1.0)],
                   [1.0, 2.0], 0.08)
    allok &= check("D Bragg", ([(float('inf'), 1.44)] +
                   [(0.25, 3.48), (0.25, 1.44)] * 24 + [(float('inf'), 1.44)]),
                   [1.9, 2.46], 0.12)
    amps = run_greens_test(wl=2.0, n=1.0)
    vals = [v for _, v in amps]
    mean = sum(vals) / len(vals)
    mr = max(abs(v - mean) / mean for v in vals)
    print(f"\n=== E 球面波 ===")
    for r, v in amps:
        print(f"  r={r} |Ez|*r={v:.5f}")
    print(f"  max_rel={mr:.4f} -> {'PASS' if mr < 0.2 else 'FAIL'}")
    allok &= mr < 0.2
    print("\n>> 快速诊断:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
