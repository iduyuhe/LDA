"""2D FDTD 调试：打印 C 用例真实跑 vs 参考跑的 |Ez| 沿 x 剖面，与 3D 对比。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from lda.lda_solver import fdtd2d

INF = float('inf')
layers_C = [(INF, 1.0), (2.0, 2.5), (INF, 1.0)]
ref_C = [(INF, 1.0), (2.0, 1.0), (INF, 1.0)]

wl = 2.0
amp_r, prof_r = fdtd2d._run_planewave(layers_C, wl, dl_factor=80, debug=True)
amp_f, prof_f = fdtd2d._run_planewave(ref_C, wl, dl_factor=80, debug=True)

print(f"[2D] amp_real={amp_r:.5f}  amp_ref={amp_f:.5f}  |ratio|^2={abs(amp_r/amp_f)**2:.4f}")
print("x : |Ez|_real (per 20 cells) [slab ~320-400, monitor 460]")
for x in range(0, len(prof_r), 20):
    print(f"  {x:4d}  {prof_r[x]:.4f}   ref={prof_f[x]:.4f}")
