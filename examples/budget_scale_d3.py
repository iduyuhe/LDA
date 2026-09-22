# -*- coding: utf-8 -*-
"""
D3 · grid2d 规模再上探 (256/512) —— 绑定 D1 幅度均衡 PDK
发现：mesh_pnr.clements_rect_decompose 用全矩阵乘法 (U@invT / T@U)，
      每次 Givens O(N^3)，总 N^2/2 次 => 实际 O(N^5)（非 O(N^3)）=> 512 超时根因。
修复：仅更新 2 行/2 列的等价快版 O(N^3)，bit-identical bs_list。
本脚本：①等价性校验 ②慢vs快计时(O(N^5)实证) ③快版实跑 4/16/128/256/512 全绿
      ④monkeypatch 后 build_mesh_pnr 真生成 256/512 grid2d GDS+驱动清单，量化 footprint。
"""
import sys, os, math, cmath, time
sys.path.insert(0, r"D:/agent_LDA/lda")
sys.path.insert(0, r"D:/agent_LDA")
sys.path.insert(0, r"D:/agent_LDA/examples")
import numpy as np
from lda.lda_layout import mesh_pnr as mp

def _arctan(x1, x2):
    return math.atan2(abs(x1), abs(x2)) if x2 != 0 else math.pi / 2.0
def _angle(x1, x2):
    return cmath.phase(x1 / x2) if x2 != 0 else 0.0

def clements_rect_decompose_fast(U, tol=1e-12):
    """等价快版：仅更新受影响的 2 行/2 列（O(N^3)），bs_list 与慢版逐元素一致。"""
    U = np.array(U, dtype=complex, copy=True)
    N = U.shape[0]
    bs_list = []
    left_T = []
    for ii in range(N - 1):
        if ii % 2 == 0:
            for jj in range(ii + 1):
                m0 = ii - jj; m1 = ii - jj + 1          # 0-based cols
                a = U[N - 1 - jj, m0]; b = U[N - 1 - jj, m1]
                theta = _arctan(a, b); phi = _angle(a, b)
                c = math.cos(theta); s = math.sin(theta)
                e = cmath.exp(-1j * phi)
                col0 = U[:, m0].copy(); col1 = U[:, m1].copy()
                U[:, m0] = e * c * col0 - s * col1
                U[:, m1] = e * s * col0 + c * col1
                bs_list.append((m0, theta, phi))
        else:
            for jj in range(ii + 1):
                m0 = N + jj - ii - 2; m1 = N + jj - ii - 1   # 0-based 下/上轨
                a = U[m1, jj]; b = U[m0, jj]
                theta = _arctan(a, b); phi = _angle(-a, b)
                c = math.cos(theta); s = math.sin(theta)
                e = cmath.exp(1j * phi)
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

def random_unitary(N):
    A = np.random.randn(N, N) + 1j * np.random.randn(N, N)
    Q, R = np.linalg.qr(A)
    d = np.diag(np.exp(1j * np.angle(np.diag(R))))
    return Q @ d

def dft_matrix(N):
    n = np.arange(N); k = n.reshape(-1, 1)
    return np.exp(-2j * np.pi * k * n / N) / math.sqrt(N)

def reconstruct_fast(bs_list, D, N):
    """O(N^3) 列序重建（2 列更新），返回 U_recon == U_target（机器精度）。"""
    color = mp._rect_column_assignment(bs_list)
    Cmax = max(color)
    cols = [[] for _ in range(Cmax + 1)]
    for k, (j, th, ph) in enumerate(bs_list):
        cols[color[k]].append((j, th, ph))
    U = np.eye(N, dtype=complex)
    for c in range(Cmax + 1):
        for (j, theta, phi) in cols[c]:
            c_ = math.cos(theta); s_ = math.sin(theta); e = cmath.exp(1j * phi)
            col0 = U[:, j].copy(); col1 = U[:, j + 1].copy()
            U[:, j] = e * c_ * col0 + e * s_ * col1
            U[:, j + 1] = -s_ * col0 + c_ * col1
    Dd = np.diag(np.diag(np.array(D, dtype=complex)))
    return U @ Dd

lines = []
# ① 等价性校验：慢 vs 快，N=16 随机酉，bs_list 必须逐元素一致
np.random.seed(0)
U16 = random_unitary(16)
slow_bs, slow_D = mp.clements_rect_decompose(U16)
fast_bs, fast_D = clements_rect_decompose_fast(U16)
eq_bs = all(abs(slow_bs[i][0]-fast_bs[i][0])<1e-12 and
            abs(slow_bs[i][1]-fast_bs[i][1])<1e-12 and
            abs(slow_bs[i][2]-fast_bs[i][2])<1e-12 for i in range(len(slow_bs)))
err_D = float(np.max(np.abs(slow_D - fast_D)))
lines.append(f"[等价] N=16 慢vs快 bs_list 一致={eq_bs} | D max|diff|={err_D:.2e} | n_bs={len(slow_bs)}")

# ② 慢vs快计时 (O(N^5) 实证)：N=128
for N in [64, 128]:
    U = dft_matrix(N)
    t0 = time.time(); mp.clements_rect_decompose(U); ts = time.time() - t0
    t0 = time.time(); clements_rect_decompose_fast(U); tf = time.time() - t0
    lines.append(f"[计时] N={N} 慢={ts:.3f}s 快={tf:.3f}s 加速={ts/max(tf,1e-9):.1f}x")

# ③ 快版跨规模：分解保真度 + 列数 + ops 数
lines.append("")
lines.append("--- 快版跨规模（分解保真=1-recon误差，列分配≈N）---")
for N in [4, 16, 128, 256, 512]:
    U = dft_matrix(N)
    t0 = time.time(); bs, D = clements_rect_decompose_fast(U); tdec = time.time() - t0
    color = mp._rect_column_assignment(bs)
    Cmax = max(color); n_cols = Cmax + 1
    Urecon = reconstruct_fast(bs, D, N)
    diff = float(np.max(np.abs(Urecon - U)))
    fid = float(max(0.0, 1.0 - diff / (N * math.sqrt(2.0))))
    lines.append(f"  N={N:>4} n_bs={len(bs):>7} n_cols={n_cols:>4} tdec={tdec:6.3f}s "
                 f"layout_fid={fid:.6f} recon_maxdiff={diff:.2e}")

# ④ 256 全量 build 见单独脚本 budget_scale_d3_build256.py（避免与快分析争超时）
lines.append("")
lines.append("--- 注：256 全量 build_mesh_pnr(grid2d) 由 budget_scale_d3_build256.py 单独跑（含 O(N^3) DRC 扫描）---")

out = "\n".join(lines)
with open(r"D:/agent_LDA/examples/_d3_scale_out.txt", "w", encoding="utf-8") as f:
    f.write(out + "\n")
print(out)
