"""验证 Clements 分解重构保真度是否达到机器精度（≈1.0）。"""
import sys, os
sys.path.insert(0, "D:/agent_LDA")
os.chdir("D:/agent_LDA")

import numpy as np
from lda_layout.mesh_pnr import clements_decompose, mesh_clements_fidelity
from lda_l2.mzi_mesh_matmul import dft_matrix

def rand_unitary(N, seed):
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal((N, N)) + 1j * rng.standard_normal((N, N))
    Q, R = np.linalg.qr(Z)
    d = np.diagonal(R)
    ph = d / np.abs(d)
    return Q * ph[None, :]

print("=== 单位矩阵（应=1.0）===")
for N in [4, 8, 16]:
    U = np.eye(N)
    ops, D = clements_decompose(U)
    fid = mesh_clements_fidelity(ops, D, U)
    print(f"  N={N}: n_mzi={len(ops):3d} fidelity={fid:.15f}")

print("=== DFT(4)（应≈1.0）===")
U = dft_matrix(4)
ops, D = clements_decompose(U)
fid = mesh_clements_fidelity(ops, D, U)
print(f"  n_mzi={len(ops):3d} fidelity={fid:.15f}")

print("=== 随机酉（均值应≈1.0）===")
for N in [4, 7, 16]:
    fids = []
    for seed in range(20):
        U = rand_unitary(N, seed)
        ops, D = clements_decompose(U)
        fids.append(mesh_clements_fidelity(ops, D, U))
    fids = np.array(fids)
    print(f"  N={N}: mean={fids.mean():.15f} min={fids.min():.15f} max={fids.max():.15f}")
