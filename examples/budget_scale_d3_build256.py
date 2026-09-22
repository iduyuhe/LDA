# -*- coding: utf-8 -*-
"""D3 · 256 全量 grid2d build（快版分解 patch 后），生成 GDS + 驱动清单 + 指标。"""
import sys, os, math, time
sys.path.insert(0, r"D:/agent_LDA/lda")
sys.path.insert(0, r"D:/agent_LDA")
sys.path.insert(0, r"D:/agent_LDA/examples")
import numpy as np
from lda.lda_layout import mesh_pnr as mp

def _arctan(x1, x2):
    return math.atan2(abs(x1), abs(x2)) if x2 != 0 else math.pi / 2.0
def _angle(x1, x2):
    return cmath.phase(x1 / x2) if x2 != 0 else 0.0
import cmath
def clements_rect_decompose_fast(U, tol=1e-12):
    U = np.array(U, dtype=complex, copy=True)
    N = U.shape[0]
    bs_list = []; left_T = []
    for ii in range(N - 1):
        if ii % 2 == 0:
            for jj in range(ii + 1):
                m0 = ii - jj; m1 = ii - jj + 1
                a = U[N - 1 - jj, m0]; b = U[N - 1 - jj, m1]
                theta = _arctan(a, b); phi = _angle(a, b)
                c = math.cos(theta); s = math.sin(theta); e = cmath.exp(-1j * phi)
                col0 = U[:, m0].copy(); col1 = U[:, m1].copy()
                U[:, m0] = e * c * col0 - s * col1
                U[:, m1] = e * s * col0 + c * col1
                bs_list.append((m0, theta, phi))
        else:
            for jj in range(ii + 1):
                m0 = N + jj - ii - 2; m1 = N + jj - ii - 1
                a = U[m1, jj]; b = U[m0, jj]
                theta = _arctan(a, b); phi = _angle(-a, b)
                c = math.cos(theta); s = math.sin(theta); e = cmath.exp(1j * phi)
                row0 = U[m0, :].copy(); row1 = U[m1, :].copy()
                U[m0, :] = e * c * row0 - s * row1
                U[m1, :] = e * s * row0 + c * row1
                left_T.append((m0, theta, phi))
    for (m0b, th, ph) in reversed(left_T):
        m0 = m0b; m1 = m0b + 1
        c = math.cos(th); s = math.sin(th); e = cmath.exp(-1j * ph)
        row0 = U[m0, :].copy(); row1 = U[m1, :].copy()
        U[m0, :] = e * c * row0 + e * s * row1
        U[m1, :] = -s * row0 + c * row1
        theta = _arctan(U[m1, m0], U[m1, m1]); phi = _angle(U[m1, m0], U[m1, m1])
        c2 = math.cos(theta); s2 = math.sin(theta); e2 = cmath.exp(-1j * phi)
        col0 = U[:, m0].copy(); col1 = U[:, m1].copy()
        U[:, m0] = e2 * c2 * col0 - s2 * col1
        U[:, m1] = e2 * s2 * col0 + c2 * col1
        bs_list.append((m0b, theta, phi))
    phases = np.diag(U)
    D = np.diag([cmath.exp(1j * cmath.phase(p)) for p in phases]).astype(complex)
    return bs_list, D

def dft_matrix(N):
    n = np.arange(N); k = n.reshape(-1, 1)
    return np.exp(-2j * np.pi * k * n / N) / math.sqrt(N)

mp.clements_rect_decompose = clements_rect_decompose_fast
N = 256
U = dft_matrix(N)
t0 = time.time()
rep = mp.build_mesh_pnr(U, layout_mode="grid2d")
tbuild = time.time() - t0
gds = f"D:/agent_LDA/examples/mesh{N}x{N}_grid2d.gds"
csv = f"D:/agent_LDA/examples/mesh{N}x{N}_grid2d_drive_manifest.csv"
if os.path.exists(gds): os.remove(gds)
if os.path.exists(csv): os.remove(csv)
mp.write_mesh_gds(rep, gds)
dm = rep["drive_manifest"]
with open(csv, "w", encoding="utf-8") as f:
    f.write("type,rail_or_j,col,phi_rad,V\n")
    for d in dm["mzi"]:
        f.write(f"MZI,{d['j']},{d['col_c']},{d['phi_rad']:.6f},{d['V']:.4f}\n")
    for d in dm["out"]:
        f.write(f"OUT,{d['rail']},{d['rail']},{d['phi_rad']:.6f},{d['V']:.4f}\n")
fp_mm2 = rep["footprint_um2"] / 1e6
drc = "PASS" if rep["drc_pass"] else "FAIL"
lvs = f"{rep['lvs_verdict']}(n={rep['lvs_n_violations']})"
out = (f"N={N} tbuild={tbuild:.1f}s layout_fid={rep['layout_fidelity']:.6f} "
       f"DRC={drc} LVS={lvs} cols={rep['n_cols']} "
       f"footprint={fp_mm2:.3f}mm^2 x_max={rep['x_max_um']:.0f}um "
       f"Vmax={rep['v_max']:.2f}V gds={os.path.getsize(gds)//1024}KB "
       f"csv_rows={len(dm['mzi'])+len(dm['out'])}")
with open(r"D:/agent_LDA/examples/_d3_build256_out.txt", "w", encoding="utf-8") as f:
    f.write(out + "\n")
print(out)
