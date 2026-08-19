"""LDA · GPU 激活聚焦验证（快速版，避免重跑 CPU greens N=120）。
实跑于已装 CUDA 轮的 venv：torch 2.11.0+cu128 / RTX 5060 Ti。
只做三件必要证明：
  1) 4 例 TMM 物理定律锚 selfcheck on cuda (PASS?)
  2) cuda vs cpu fp64 跨设备 bit-equivalence（小网格 + greens N=60）
  3) greens N=120 on cuda 计时 + 相对基线加速比（不跑 cpu N=120）
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import torch
from lda.lda_solver.fdtd3d_torch import solve_spectrum_torch, run_greens_test_torch
from lda.lda_solver.tmm import solve_spectrum as tmm_solve
from activate_gpu_fdtd3d import _cases, _tmm_T, _max_rel

NUMBA_CPU_BASELINE_S = 20.08
TORCH_CPU_BASELINE_S = 102.86

def main():
    assert torch.cuda.is_available(), "CUDA 不可用"
    dev = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    print("=" * 60)
    print(f">> GPU: {dev}  (cc {cap[0]}.{cap[1]}) | torch {torch.__version__} | CUDA {torch.version.cuda}")
    print("=" * 60)

    print("\n[1] 物理定律锚 selfcheck (cuda) vs TMM ORACLE")
    ok_all = True
    for cname, layers, wls, tol in _cases():
        fd = solve_spectrum_torch({"layers": layers, "wavelengths_um": wls}, device="cuda")
        tt = _tmm_T(layers, wls)
        err = max(abs(a - b) for a, b in zip(fd["transmission"], tt))
        ok = err < tol
        ok_all = ok_all and ok
        print(f"  {cname:<42} max|ΔT|={err:.4f} -> {'PASS' if ok else 'FAIL'} (tol={tol})")

    print("\n[2] cuda vs cpu fp64 bit-equivalence")
    eq_ok = True
    for cname, layers, wls, _ in _cases():
        fc = solve_spectrum_torch({"layers": layers, "wavelengths_um": wls}, device="cpu")
        fd = solve_spectrum_torch({"layers": layers, "wavelengths_um": wls}, device="cuda")
        d = _max_rel(fc["transmission"], fd["transmission"])
        ok = d < 1e-9
        eq_ok = eq_ok and ok
        print(f"  {cname:<42} max_rel={d:.2e} -> {'PASS' if ok else 'FAIL'}")
    # greens N=60 互证
    g_cpu = [v for _, v in run_greens_test_torch(wl=2.0, n=1.0, N=60, device="cpu")]
    g_cuda = [v for _, v in run_greens_test_torch(wl=2.0, n=1.0, N=60, device="cuda")]
    gd = _max_rel(g_cpu, g_cuda)
    gok = gd < 1e-9
    eq_ok = eq_ok and gok
    print(f"  {'E. greens N=60':<42} max_rel={gd:.2e} -> {'PASS' if gok else 'FAIL'}")

    print("\n[3] greens N=120 (cuda) 计时")
    t0 = time.perf_counter()
    amps = run_greens_test_torch(wl=2.0, n=1.0, N=120, sponge=28, dl_factor=20.0, ramp=400, device="cuda")
    t_cuda = time.perf_counter() - t0
    vals = [round(v, 5) for _, v in amps]
    sp_n = NUMBA_CPU_BASELINE_S / t_cuda
    sp_t = TORCH_CPU_BASELINE_S / t_cuda
    print(f"  cuda: {t_cuda:8.2f}s |Ez|*r={vals}")
    print(f"  加速比 vs numba-cpu(20.08s)={sp_n:.2f}x | vs torch-cpu(102.86s)={sp_t:.2f}x")

    total = ok_all and eq_ok
    print("\n>> GPU 激活总判定:", "PASS" if total else "FAIL",
          f"(selfcheck={'PASS' if ok_all else 'FAIL'}, equiv={'PASS' if eq_ok else 'FAIL'})")

if __name__ == "__main__":
    main()
