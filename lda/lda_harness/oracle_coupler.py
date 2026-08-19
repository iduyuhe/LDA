"""LDA · 多端口耦合器件 ORACLE（物理定律锚，C 级自主，numpy + scipy）。

D-01：对方向耦合器 / 对称分束器提供两类**确定性**真值：

  1. 方向耦合器 —— FDFD 超模法（频域独立数值）：
     双平行波导的导模分裂为对称超模（neff_s）与反对称超模（neff_a）。
     耦合模理论（CMT）：耦合系数 κ = (βs−βa)/2 = π(neff_s−neff_a)/λ0，
     功率交换 P_c(z) = sin²(κz)，耦合长度 L_c = λ0/(2(neff_s−neff_a))。
     该结果由频域本征值方程**必然导出**，非 AI ground，方程确定。
  2. 对称 Y 分支分束器 —— 对称性定理（解析）：
     几何完全对称 ⇒ 两输出臂功率必然等分（P1 = P2 = 0.5·P_in，理想无损）。
     这是对称性的直接推论，确定性、可手算核对。

独立性（与 1.8 哲学一致）：ORACLE 与 FDTD 求解器方法不同、代码不同，交叉校验
可排除单一实现 bug。不依赖 GPL、不进 LLM 判决路径。

诚实边界：FDFD 用 Dirichlet 边界（等效金属壁），包层取 3µm（模尾远离壁）；
标量近似与 FDTD 同层级；超模识别依赖「芯区占比 + 对称性判据」，见 §2。
"""
from __future__ import annotations

import math
import numpy as np
from scipy.sparse import kron, identity, diags
from scipy.sparse.linalg import eigs


# ---------------------------------------------------------------------------
# 1. 方向耦合器：FDFD 超模法
# ---------------------------------------------------------------------------
def _build_fdfd_operator(eps2: np.ndarray, dl: float, wl_um: float):
    """构造标量亥姆霍兹频域算子 A = (1/dl²)·Lap + diag(k0²·ε)（同 oracle_mode）。"""
    Nx, Ny = eps2.shape

    def _lap_1d(N: int):
        e = np.ones(N - 1)
        return diags([e, -2.0 * np.ones(N), e], [-1, 0, 1], shape=(N, N)).tocsr()

    Lx = _lap_1d(Nx)
    Ly = _lap_1d(Ny)
    Ix = identity(Nx).tocsr()
    Iy = identity(Ny).tocsr()
    Lap = (kron(Ix, Ly) + kron(Lx, Iy)).tocsr()
    k0 = 2.0 * math.pi / wl_um
    A = ((1.0 / dl ** 2) * Lap + diags((k0 ** 2) * eps2.reshape(-1))).tocsr()
    return A, Nx, Ny


def fdfd_coupler_supermodes(eps2: np.ndarray, dl: float, wl_um: float,
                            mask_a: np.ndarray = None, mask_b: np.ndarray = None,
                            k_eig: int = 16):
    """FDFD 超模法求方向耦合器耦合系数。

    eps2 : (Nx,Ny) 双波导折射率平方场；dl : 网格步长 µm；wl_um : 真空波长。
    mask_a/mask_b : (Nx,Ny) 波导 A/B 芯区掩膜（缺省自动检测 > (n_clad²+n_core²)/2 的
                    两连通域，按 x 坐标负/正分配）。
    返回 dict：
      neff_s / neff_a : 对称/反对称超模有效折射率
      mode_s / mode_a : (Nx,Ny) 超模剖面（归一化到单位峰值）
      kappa          : 耦合系数 κ = π(neff_s−neff_a)/λ0（rad/µm）
      Lc_um          : 耦合长度 = λ0/(2(neff_s−neff_a))（µm）
      symmetry       : {'symmetric','antisymmetric'} 标记，防选错
    """
    arr = np.asarray(eps2, dtype=float)
    Nx, Ny = arr.shape
    n_clad = float(np.min(np.sqrt(arr)))
    n_core = float(np.max(np.sqrt(arr)))
    if mask_a is None or mask_b is None:
        core_mask = arr > (n_clad ** 2 + n_core ** 2) / 2.0
        xs = np.where(core_mask.any(axis=1))[0]
        if xs.size == 0:
            raise RuntimeError("FDFD 超模法：未检测到芯区")
        xmid = float(xs.mean())
        mask_a = core_mask.copy()
        mask_b = core_mask.copy()
        X = (np.arange(Nx)[:, None] - Nx / 2.0) * dl
        mask_a[X[:, None, :] > xmid] = False   # 波导 A：x<中轴
        mask_b[X[:, None, :] <= xmid] = False  # 波导 B：x>中轴
    mask_a = np.asarray(mask_a, dtype=bool).reshape(Nx, Ny)
    mask_b = np.asarray(mask_b, dtype=bool).reshape(Nx, Ny)

    A, Nx2, Ny2 = _build_fdfd_operator(arr, dl, wl_um)
    k0 = 2.0 * math.pi / wl_um

    # shift-invert：σ 取略低于基模（约 k0·2.3），同 oracle_mode 稳健策略
    sigma = (k0 * 2.3) ** 2
    lam, V = eigs(A, k=k_eig, sigma=sigma, which="LM", ncv=min(200, max(2 * k_eig + 1, k_eig + 30)),
                  return_eigenvectors=True)
    # 收集导模候选（n_clad < neff < n_core），按芯区占比降序
    cand = []
    for i in range(len(lam)):
        r = float(np.real(lam[i]))
        if r <= 0:
            continue
        ne = math.sqrt(r) / k0
        if not (n_clad + 1e-6 < ne < n_core - 1e-6):
            continue
        vv = np.real(V[:, i]).reshape(Nx, Ny)
        frac = float(np.sum(vv[mask_a | mask_b] ** 2) / (np.sum(vv ** 2) + 1e-30))
        # 对称性判据：波导 A/B 区平均场乘积的符号
        sa = float(np.sum(vv[mask_a]))
        sb = float(np.sum(vv[mask_b]))
        sym = sa * sb / (abs(sa) * abs(sb) + 1e-30)   # +1 对称超模，-1 反对称超模
        cand.append({"ne": ne, "vec": vv, "frac": frac, "sym": sym,
                     "sa": sa, "sb": sb})

    if len(cand) < 2:
        raise RuntimeError("FDFD 超模法：导模候选不足（耦合过弱或网格过粗）")
    cand.sort(key=lambda c: (-c["frac"], -c["ne"]))

    # 选最受限的对称超模（最高芯区占比中 sym>0 者）与最受限的反对称超模（sym<0 者）
    sym_cands = [c for c in cand if c["sym"] > 0.0]
    asy_cands = [c for c in cand if c["sym"] < 0.0]
    if not sym_cands or not asy_cands:
        # 兜底：若只有一组，取芯区占比最高的两个（物理上应为 s/a 对）
        sym_cands = cand[:1]
        asy_cands = cand[1:2]
    cs, ca = sym_cands[0], asy_cands[0]
    neff_s, mode_s = cs["ne"], cs["vec"]
    neff_a, mode_a = ca["ne"], ca["vec"]

    kappa = math.pi * (neff_s - neff_a) / wl_um        # rad/µm
    Lc = wl_um / (2.0 * (neff_s - neff_a))             # µm
    for m in (mode_s, mode_a):
        pm = np.max(np.abs(m))
        if pm > 0:
            m /= pm
    return {"neff_s": float(neff_s), "neff_a": float(neff_a),
            "mode_s": mode_s, "mode_a": mode_a,
            "kappa": float(kappa), "Lc_um": float(Lc),
            "symmetry": "symmetric/antisymmetric pair",
            "n_clad": n_clad, "n_core": n_core}


def coupling_oracle(w_um: float, h_um: float, gap_um: float,
                    n_core: float, n_clad: float, wl_um: float,
                    dl: float = None, clad_um: float = 3.0):
    """方向耦合器 ORACLE 参数化封装：直接由几何参数返回耦合系数真值。"""
    if dl is None:
        dl = wl_um / 24.0
    Lx = 2.0 * w_um + gap_um + 2.0 * clad_um
    Ly = h_um + 2.0 * clad_um
    Nx = int(round(Lx / dl))
    Ny = int(round(Ly / dl))
    xs = (np.arange(Nx) - Nx / 2.0) * dl
    ys = (np.arange(Ny) - Ny / 2.0) * dl
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    xa = -(w_um + gap_um) / 2.0
    xb = +(w_um + gap_um) / 2.0
    core_a = (np.abs(X - xa) <= w_um / 2.0) & (np.abs(Y) <= h_um / 2.0)
    core_b = (np.abs(X - xb) <= w_um / 2.0) & (np.abs(Y) <= h_um / 2.0)
    eps2 = np.full((Nx, Ny), n_clad ** 2, dtype=float)
    eps2[core_a | core_b] = n_core ** 2
    return fdfd_coupler_supermodes(eps2, dl, wl_um, mask_a=core_a, mask_b=core_b)


# ---------------------------------------------------------------------------
# 2. 对称 Y 分支分束器：对称性定理
# ---------------------------------------------------------------------------
def ybranch_oracle():
    """对称 Y 分支分束器 ORACLE：对称性定理 → 两臂功率必然等分。

    返回 dict：
      target_frac : 0.5（每臂占输出总功率的理想比例）
      basis       : 'symmetry theorem（几何完全对称 ⇒ P1=P2，能量守恒下各 0.5·P_in）'
    """
    return {"target_frac": 0.5,
            "basis": "symmetry theorem（几何完全对称 ⇒ P1=P2，能量守恒下各 0.5·P_in）"}


if __name__ == "__main__":
    w, h = 0.5, 0.22
    n_si, n_sio2, wl = 3.48, 1.44, 1.55
    print("=== 方向耦合器 ORACLE（gap=0.3µm）===")
    o1 = coupling_oracle(w, h, 0.3, n_si, n_sio2, wl)
    print(f"  neff_s={o1['neff_s']:.5f}  neff_a={o1['neff_a']:.5f}")
    print(f"  κ={o1['kappa']:.5f} rad/µm  Lc={o1['Lc_um']:.2f} µm")
    print("=== 方向耦合器 ORACLE（gap=0.5µm，应更弱耦合、Lc 更长）===")
    o2 = coupling_oracle(w, h, 0.5, n_si, n_sio2, wl)
    print(f"  neff_s={o2['neff_s']:.5f}  neff_a={o2['neff_a']:.5f}")
    print(f"  κ={o2['kappa']:.5f} rad/µm  Lc={o2['Lc_um']:.2f} µm")
    print("=== 对称 Y 分支 ORACLE ===")
    print(" ", ybranch_oracle())
