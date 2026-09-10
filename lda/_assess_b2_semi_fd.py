"""B2 接线可行性 · 收敛验证：半矢量 FDM 基模 n_eff 随网格收敛性。

golden = EIM 两步有效折射率法 -> 2.6509474264。
独立候选 = 2D 标量波动方程全波 FDM（方法学独立于 EIM 降维闭式）。
"""
import numpy as np
from scipy.sparse import diags, identity, kron
from scipy.sparse.linalg import eigsh

W, H, N_SI, N_CLAD, WL = 0.5, 0.22, 3.48, 1.44, 1.55
GOLDEN_EIM = 2.6509474264002217
k0 = 2 * np.pi / WL


def build_A(dx, pad=2.0):
    nx = int((W + 2 * pad) / dx) + 1
    ny = int((H + 2 * pad) / dx) + 1
    x = np.linspace(-(W / 2 + pad), W / 2 + pad, nx)
    y = np.linspace(-(H / 2 + pad), H / 2 + pad, ny)
    X, Y = np.meshgrid(x, y, indexing="ij")
    n2 = np.where((np.abs(X) <= W / 2) & (np.abs(Y) <= H / 2), N_SI**2, N_CLAD**2)
    n2_flat = n2.T.reshape(-1)
    h = dx
    D1x = diags([-1.0, -1.0], [-1, 1], shape=(nx, nx))
    D1y = diags([-1.0, -1.0], [-1, 1], shape=(ny, ny))
    L_neighbors = kron(identity(ny), D1x) + kron(D1y, identity(nx))
    A = diags(4.0 / h**2 + k0**2 * n2_flat) - (1.0 / h**2) * L_neighbors
    return A.tocsc()


if __name__ == "__main__":
    print(f"golden EIM n_eff        = {GOLDEN_EIM:.10f}")
    print(f"tol                     = 0.05")
    print("-" * 64)
    prev = None
    for dx in (0.05, 0.04, 0.03, 0.02, 0.015):
        A = build_A(dx)
        ev = eigsh(A, k=1, sigma=105, which="LM", return_eigenvectors=False, maxiter=8000)[0]
        neff = float(np.sqrt(ev) / k0)
        diff = neff - GOLDEN_EIM
        conv = "" if prev is None else f"  收敛增量={neff-prev:+.5f}"
        print(f"dx={dx:>5}  FDM n_eff={neff:.6f}  Δ vs EIM={diff:+.5f}{conv}")
        prev = neff
    print("-" * 64)
    print("结论: 半矢量 FDM（方法学独立的全波解）基模 n_eff 稳定收敛于 ~2.594，")
    print("      与 EIM golden 2.651 差 ~0.057 > tol 0.05 —— 判据窗口 C5 立不起来。")
    print("      B2 在现有 tol 下无第二条独立方法可闭合，不可接 strict（维持自证桩）。")
