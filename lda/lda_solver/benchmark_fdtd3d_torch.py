"""LDA · L2-B 第二步 · 主权 3D FDTD 多后端正确性对照 + 性能基准。

后端（各自独立子进程，避免 numba 并行线程池与 torch 同进程冲突导致 segfault）：
  - numpy      (fdtd3d.py,        CPU 参考实现，逐字节基准)
  - numba-cpu  (fdtd3d_numba.py,  CPU 并行 JIT)
  - torch-cpu  (fdtd3d_torch.py,  device='cpu')
  - torch-cuda (fdtd3d_torch.py,  device='cuda'，若 GPU/轮子可用)

正确性：点源球面波 |Ez|·r 各后端与 numpy 互比，报告 max rel dev。
性能：球面波 greens 计时（N=120），报告相对 numpy 的加速比。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SYS_PY = sys.executable

# 每个后端在独立子进程中运行的 worker 代码（只 import 自己，互不污染）
WORKER = r'''
import sys, time, json
sys.path.insert(0, %r)
backend = sys.argv[1]; N = int(sys.argv[2])
wl, n, sponge, dl_factor, ramp = 2.0, 1.0, 28, 20.0, 400
t0 = time.perf_counter()
if backend == "numpy":
    import fdtd3d as M
    amps = M.run_greens_test(wl=wl, n=n, N=N, sponge=sponge, dl_factor=dl_factor, ramp=ramp)
elif backend == "numba-cpu":
    from fdtd3d_numba import run_greens_test_numba as f
    amps = f(wl=wl, n=n, N=N, sponge=sponge, dl_factor=dl_factor, ramp=ramp)
elif backend == "torch-cpu":
    import fdtd3d_torch as M
    amps = M.run_greens_test_torch(wl=wl, n=n, N=N, sponge=sponge, dl_factor=dl_factor, ramp=ramp, device="cpu")
elif backend == "torch-cuda":
    import fdtd3d_torch as M
    amps = M.run_greens_test_torch(wl=wl, n=n, N=N, sponge=sponge, dl_factor=dl_factor, ramp=ramp, device="cuda")
else:
    raise SystemExit("unknown backend " + backend)
dt = time.perf_counter() - t0
vals = [float(v) for _, v in amps]
print(json.dumps({"backend": backend, "time": dt, "vals": vals}))
''' % ROOT


def _run(backend, N):
    out = subprocess.run([SYS_PY, "-c", WORKER, backend, str(N)],
                         capture_output=True, text=True, cwd=HERE)
    if out.returncode != 0:
        return {"backend": backend, "error": out.stderr.strip().splitlines()[-1] if out.stderr else "?"}
    return json.loads(out.stdout.strip().splitlines()[-1])


def _max_rel(a, b):
    import numpy as np
    a = np.array(a, dtype=float); b = np.array(b, dtype=float)
    return float(np.max(np.abs(a - b) / (np.abs(b) + 1e-12)))


def main():
    N = 120
    print(">> L2-B 第二步基准 (N=%d greens)" % N)
    backends = ["numpy", "numba-cpu", "torch-cpu"]
    # torch-cuda 仅在可用时加入
    import torch as _t
    has_gpu = _t.cuda.is_available()
    if has_gpu:
        backends.append("torch-cuda")
        print("   CUDA available: %s" % _t.cuda.get_device_name(0))
    else:
        print("   CUDA unavailable (wheel blocked in this sandbox) — torch-cuda 跳过")

    results = {}
    for b in backends:
        r = _run(b, N)
        results[b] = r
        if "error" in r:
            print("   %-12s ERROR: %s" % (b, r["error"]))
        else:
            print("   %-12s %8.2fs  |Ez|*r=%s" % (b, r["time"], [round(v, 5) for v in r["vals"]]))

    ref = results["numpy"]["vals"]
    print("\n>> 正确性对照（各后端 vs numpy）：")
    for b in backends:
        if b == "numpy" or "error" in results[b]:
            continue
        d = _max_rel(results[b]["vals"], ref)
        print("   %-12s max_rel_dev_vs_numpy = %.2e" % (b, d))

    print("\n>> 性能（相对 numpy 加速比）：")
    t_ref = results["numpy"]["time"]
    for b in backends:
        if "error" in results[b]:
            continue
        sp = t_ref / results[b]["time"]
        print("   %-12s %.2fx" % (b, sp))
    print("\n>> 完成。")


if __name__ == "__main__":
    main()
