"""P1-A 探测②：随机酉验证一般公式。

确认：adjoint MZI（G_k†）+ 反转 x 序 的网格前向传输 M_adj_rev，
乘输出对角相移 D 后 == U_target（保真度 1.0），对一般酉成立（D≠I）。
"""
import sys
import math
import numpy as np

sys.path.insert(0, "D:/agent_LDA/lda")
from lda_layout.mesh_pnr import clements_decompose, _mzi


def random_unitary(N, seed):
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((N, N)) + 1j * rng.standard_normal((N, N))
    Q, R = np.linalg.qr(X)
    d = np.diagonal(R)
    ph = d / np.abs(d)
    return Q * ph


def mesh_transfer_adj_rev(ops):
    N = max(max(op[0] + 2, op[3] + 1) for op in ops)
    seq = list(reversed(ops))           # 反转 x 序：op[-1] 最先作用
    U = np.eye(N, dtype=complex)
    for (j, theta, phi, c) in seq:
        G = _mzi(theta, phi).conj().T     # adjoint
        blk = np.eye(N, dtype=complex)
        blk[j, j] = G[0, 0]; blk[j, j + 1] = G[0, 1]
        blk[j + 1, j] = G[1, 0]; blk[j + 1, j + 1] = G[1, 1]
        U = blk @ U
    return U


def fidelity(A, B):
    N = A.shape[0]
    return 1.0 - np.linalg.norm(A - B) / (N * math.sqrt(2.0))


for N in (4, 5, 7, 8, 16):
    for seed in range(6):
        U = random_unitary(N, seed)
        ops, D = clements_decompose(U)
        Dmat = np.diag(np.diag(D))
        M = mesh_transfer_adj_rev(ops)
        f1 = fidelity(M @ Dmat, U)          # adjoint+rev，输出相移 D（右乘）
        f2 = fidelity(Dmat @ M, U)          # 输出相移在左乘
        fd = np.max(np.abs(np.diag(Dmat) - 1.0))
        if abs(f1 - 1.0) > 1e-9:
            print(f"  N={N} seed={seed} M@D fid={f1:.6f} D@M fid={f2:.6f} "
                  f"max|D-1|={fd:.4f}  <== MISMATCH")
    print(f"N={N}: 全部 6 例 M@D 保真度（max|D-1| 见上）")
print("DONE")
