"""2D 全矢量本征模求解器（H-field staggered · PML）—— G12-H。

═══ 为什么有这个模块 ═══
`semivec_mode_solver` 是**半矢量**（约束 E_y≡0）⇒ 变分约束使 β² 系统性偏高：
SOI 高对比度（3.478/1.444）实测偏 **+0.0276**（2.5936 vs Lumerical FDE 2.566），
其 docstring 已写明「不得用于 SOI 高对比度波导的绝对 n_eff 判定」，
并把正解指向 **staggered / Yee 网格**。本模块即该正解。

═══ 方法（公开论文，非代码移植）═══
    A. B. Fallahkhair, K. S. Li and T. E. Murphy,
    "Vector Finite Difference Modesolver for Anisotropic Dielectric
     Waveguides", J. Lightwave Technol. 26(11), 1423-1431 (2008).
    doi:10.1109/JLT.2008.923643

  · 解横磁分量 h=[Hx;Hy]；H 在格点（vertex），E 在格心（cell）——staggered，
    与半矢量模块的 collocated 网格**不是同一离散**。
  · 用散度约束 ∇·(εH)=0 **代数消去 Hz** ⇒ 得 β² 本征问题 `A h = β² h`
    （无二次特征值 QEP、无奇异质量项）。
  · ε 分段均匀且界面与网格线重合 ⇒ H 连续、无 δ 函数。
  · PML = 复坐标拉伸（Chew & Weedon 1994，公开方法）：外层节点坐标加虚部。

  系数由论文方程在**各向同性极限下自行化简**（见 `coeffs()`），
  未 import / 未复制任何第三方实现。

═══ 实测凭据（2026-09-24）═══
  ① 与公开参考实现（modesolver，同一篇论文的独立实现）逐位一致：
     SOI 600×220 TE0 本项目 2.570410 vs 参考 2.570409755（Δ≈2e-7）；
     SiN 1.2×0.3 基模 1.597884 vs 1.597883911（Δ≈1e-7）。
     ⚠️ 参考实现仅作**外部 oracle 标量对照**（一次性脚本），**不进本模块**。
  ② SOI 600×220 TE0 = 2.570410（格点收敛 ≈2.5699）vs FDE 2.566
     ⇒ Δ ≈ +0.004（半矢量同题 2.5936 ⇒ +0.0276 ⇒ **误差降 7 倍**）。
  ③ A 级实证锚（实测事实，见 selfcheck ③）：SiN 1.2×0.3 TE 实测
     n_g = 1.9666（Coatings 10(4) 309 (2020)）—— 本模块 Δ=+1.4e-3（0.07%）。

🔴 **口径澄清（订正旧记录）**：旧记录写「SiN 1.2×0.3 目标 n_eff = 1.967」——
**那是 n_g（群折射率），不是 n_eff**。SiN 1.2×0.3 的真值：
    n_eff ≈ 1.598（本模块 1.597882 / 半矢量 1.600320 / 参考实现 1.597884），
    n_g   ≈ 1.9666（实测）—— 差 0.37 由「低限制 + 材料色散」共同贡献，属正常量级。
把 n_g 当 n_eff 用会误判为「求解器偏差 −0.37」。

═══ 🔴 诚实边界 ═══
  · `2.566` / `1.9666` 之外的**商业求解器数值属「仿真值」**，按本仓铁律
    **不作 golden**（`lda_harness/real_machine_oracle`：仿真/计算值 ⛔ 非事实）。
    因此本模块的 golden 只有三类**合法来源**：
      ① 闭式物理律（均匀介质 max β² = k0²n²）
      ② 闭式物理律（TE/TM 分裂符号、n_clad < n_eff < n_core）
      ③ **实测事实**（A 级可溯源，见 selfcheck ③）
    对 FDE/参考实现的吻合只称「**外部对标**」，不称 golden。
  · 网格对齐纪律：芯层尺寸须是 h_grid 的整数倍，否则楼梯误差主导
    （实测 h=0.015 时 0.22/0.015=14.67 非整数 ⇒ SOI 约 +0.07 的纯几何误差）。
    本模块内部**自动 snap** 几何到网格线（同 semivec 做法）。
  · 窗口：默认半窗 L = max(1.2, 2·max(w,h)) µm 已对 SOI/SiN 收敛
    （SOI：L=1.0/1.5/2.0 逐位相同；SiN：L=2.0 与 L=8.0 差 1.5e-5）。
    弱限制模（SiN 类）若须更紧的窗，请显式用 PML 并自行验证。
"""
from __future__ import annotations

import math
from typing import Dict, List, NamedTuple, Optional

import numpy as np
from scipy.sparse import bmat, coo_matrix, csr_matrix, kron, eye, diags
from scipy.sparse.linalg import eigsh, eigs

__all__ = [
    "H_GRID", "L_HALF_MIN", "HALF_WIN_MULT", "N_PML", "A_PML", "K_EIGS",
    "ModeResult",
    "build_grid", "eps_cells", "eps_rib", "coeffs", "build_operator",
    "core_vertex_mask", "solve_modes_eps",
    "solve_modes", "neff_strip", "neff_2d", "group_index",
    "selfcheck_uniform_limit", "selfcheck_sin_pristine_control",
    "selfcheck_low_contrast_vs_semivec", "selfcheck_highcontrast_regression",
    "selfcheck_grid_convergence", "selfcheck_strip_bounds",
    "selfcheck_arbitrary_lowcontrast_vs_semivec",
    "selfcheck_arbitrary_strip_degeneracy",
    "selfcheck_rib_slab_monotonic", "selfcheck_rib_slab_loadbearing",
    "selfcheck_rib_vs_semivec_nonzero", "selfcheck_rib_grid_convergence",
    "run_selfchecks",
    # G12-B：真 3D 空间全矢量本征模（collocated 3D 向量拉普拉斯 FDFD）
    "build_operator_3d", "cavity_k0_sq", "solve_modes_eps_3d", "neff_3d",
    "H_GRID_3D", "K_EIGS_3D",
    "selfcheck_cubic_cavity_golden", "selfcheck_3d_convergence",
    "selfcheck_3d_diel_lt_air", "selfcheck_3d_shape_sensitivity",
]


# ═══════════════════════════════════════════════════════════════════
# 生产档位（速度/精度权衡，实测标定）
# ═══════════════════════════════════════════════════════════════════
# h=0.010 同时对齐 0.22 / 0.30 / 0.60 / 1.20（全部为 0.01 的整数倍）；
# SOI 实测 h=0.02→2.6370 / 0.01→2.570410 / 0.005→2.569920 ⇒ 0.01 已收敛到 ~5e-4。
H_GRID = 0.010          # µm
L_HALF_MIN = 1.2        # µm 最小半窗（模场半径 ≪ 此值时才可再紧）
HALF_WIN_MULT = 2.0     # µm 半窗 = mult·max(w,h)
N_PML = 16              # PML 层数（可选，默认不启用）
A_PML = 0.7             # PML 强度（复坐标拉伸系数）
K_EIGS = 6              # ARPACK 请求本征对数
D_WL = 0.02             # µm 群折射率中心差分半步长


class ModeResult(NamedTuple):
    """单个本征模。field 为 (ny, nx) 顶点网格；TE-like ⇔ Hy 主导。"""
    neff: float
    conf_core: float
    peak_in_core: bool
    im_beta2: float
    frac_hy_core: float
    hx: np.ndarray
    hy: np.ndarray


# ═══════════════════════════════════════════════════════════════════
# 网格 + PML（复坐标拉伸，cubic m=3 剖面）
# ═══════════════════════════════════════════════════════════════════
def build_grid(Lhalf: float, h: float, n_pml: int = 0, A_pml: float = 0.0):
    """节点坐标（PML 时含虚部）→ x[0..n]。"""
    n_core = 2 * int(round(Lhalf / h))
    n = n_core + 2 * n_pml
    x = (np.arange(n + 1) - n / 2.0) * h
    if n_pml > 0 and A_pml > 0:
        f = 1.0 + 1j * A_pml
        x = x.astype(complex)
        kv = slice(n - n_pml, n + 1)                        # 高侧
        q1, q2 = x[n - n_pml].real, x[n].real
        x[kv] = x[kv].real + (f - 1.0) * (x[kv].real - q1) ** 4 / (q2 - q1) ** 3
        kv = slice(0, n_pml + 1)                            # 低侧
        q1, q2 = x[n_pml].real, x[0].real
        x[kv] = x[kv].real + (f - 1.0) * (x[kv].real - q1) ** 4 / (q2 - q1) ** 3
    return x


def eps_cells(w: float, h_core: float, n_core: float, n_clad: float,
              xc: np.ndarray, yc: np.ndarray) -> np.ndarray:
    """楼梯 ε（cell-centered）→ (ny_cells, nx_cells)。输入为折射率。"""
    X, Y = np.meshgrid(np.asarray(xc).real, np.asarray(yc).real, indexing="ij")
    eps = np.where((np.abs(X) <= w / 2.0) & (np.abs(Y) <= h_core / 2.0),
                   n_core ** 2, n_clad ** 2)
    return eps.T


def eps_rib(ridge_w: float, ridge_h: float, slab_t: float,
            n_core: float, n_clad: float,
            xc: np.ndarray, yc: np.ndarray) -> np.ndarray:
    """脊形（rib）波导 ε（cell-centered）→ (ny_cells, nx_cells)。输入为折射率。

    几何（与 `eps_cells` 完全同口径，仅换形状）：底部平板（slab）厚 `slab_t`
    **横向铺满整个窗口**，其上居中一脊（宽 `ridge_w`、高 `ridge_h`）。

    🔴 本函数是 G12-A「任意 2D 截面」能力的**几何样例**，不是新的物理模型：
    它只负责把「芯材料占据哪些 cell」表达出来，算子与选模一律走既有
    `build_operator` / `solve_modes_eps`。`slab_t=0` 时平板层消失 ⇒ 只剩一个
    居中矩形（宽 `ridge_w` × 高 `ridge_h`）；退化一致性另由
    `selfcheck_arbitrary_strip_degeneracy` 用 `eps_cells` 的居中矩形场直接核验
    （两者的居中实现不同：本函数按 cell 索引居中，`eps_cells` 按连续坐标判阈值）。

    🔴 **两个踩过的坑（实测，勿回退）**：
      ① **几何必须 snap 到网格**（与 `semivec.neff_strip` 同口径）。脊形对
         `slab_t` 的敏感度实测 **dn_eff/dt ≈ 6 /µm** —— 厚度差 0.01 µm 即
         0.06 的 n_eff 位移（≫ 物理容差 2e-3）。若按连续坐标取阈值，有效厚度
         会随 h 跳变 ⇒ 收敛序列「看似不收敛」。snap 后有效尺寸在 h=0.04/0.02/
         0.01 三档上**完全相同**，剩下的才是纯离散误差。
      ② **结构必须垂直居中**。早期版本把 slab 贴在窗口底边 ⇒ 结构紧贴
         Dirichlet 墙（离墙 ~0.1 µm）⇒ 模场被墙挤压、n_eff 随 h 跳 9.8e-2。
         现按 cell 索引居中，底边恒落在格线上。
    """
    xc_r = np.asarray(xc).real
    yc_r = np.asarray(yc).real
    hx = float(xc_r[1] - xc_r[0]) if xc_r.size >= 2 else 0.0
    hy = float(yc_r[1] - yc_r[0]) if yc_r.size >= 2 else 0.0
    h = 0.5 * (hx + hy)
    if h <= 0:
        raise ValueError("eps_rib: 无法从坐标推出网格步长")
    nx, ny = int(xc_r.size), int(yc_r.size)

    n_slab = max(int(round(slab_t / h)), 0)
    n_tot = max(int(round((slab_t + ridge_h) / h)), n_slab + 1)
    n_w = 2 * max(int(round(ridge_w / 2.0 / h)), 1)     # 偶格数 ⇒ 关于中轴对称
    i0 = ny // 2 - n_tot // 2                            # 垂直居中
    j0 = nx // 2 - n_w // 2
    if n_tot > ny or n_w > nx:
        raise ValueError("eps_rib: 结构尺寸超出窗口")

    eps = np.full((ny, nx), float(n_clad ** 2))
    eps[i0:i0 + n_slab, :] = float(n_core ** 2)          # 底部平板（横向铺满窗口）
    eps[i0:i0 + n_tot, j0:j0 + n_w] = float(n_core ** 2)  # 居中脊
    return eps


# ═══════════════════════════════════════════════════════════════════
# 算子装配（各向同性 Fallahkhair 离散，自行化简）
# ═══════════════════════════════════════════════════════════════════
def coeffs(eps: np.ndarray, dx: np.ndarray, dy: np.ndarray, k0: float) -> Dict[str, np.ndarray]:
    """全部 Fallahkhair 系数（各向同性化简）。P 点四格 ε = E1(NW) E2(SW) E3(SE) E4(NE)。"""
    ny_cells, nx_cells = eps.shape
    ny, nx = ny_cells + 1, nx_cells + 1

    epsp = np.pad(eps, 1, mode="edge")
    dxp = np.pad(np.asarray(dx), 1, mode="edge")
    dyp = np.pad(np.asarray(dy), 1, mode="edge")

    n = np.repeat(dyp[1:ny + 1], nx)
    s = np.repeat(dyp[0:ny], nx)
    e = np.tile(dxp[1:nx + 1], ny)
    w = np.tile(dxp[0:nx], ny)

    def rv(a, r0, r1, c0, c1):
        return np.asarray(a[r0:r1, c0:c1]).ravel(order="C")

    E1 = rv(epsp, 1, ny + 1, 0, nx)
    E2 = rv(epsp, 0, ny, 0, nx)
    E3 = rv(epsp, 0, ny, 1, nx + 1)
    E4 = rv(epsp, 1, ny + 1, 1, nx + 1)

    ns21 = n * E2 + s * E1
    ns34 = n * E3 + s * E4
    ew14 = e * E1 + w * E4
    ew23 = e * E2 + w * E3

    # ---- Axx ----
    axxn = (2 * e * E3 / ns34 + 2 * w * E2 / ns21) / (n * (e + w))
    axxs = (2 * e * E4 / ns34 + 2 * w * E1 / ns21) / (s * (e + w))
    axxe = 2.0 / (e * (e + w))
    axxw = 2.0 / (w * (e + w))
    axxp = (-(axxn + axxs + axxe + axxw)
            + k0 ** 2 * (n + s) * (E4 * E3 * e / ns34 + E1 * E2 * w / ns21) / (e + w))

    # ---- Ayy ----
    ayyn = 2.0 / (n * (n + s))
    ayys = 2.0 / (s * (n + s))
    ayye = (2 * n * E1 / ew14 + 2 * s * E2 / ew23) / (e * (n + s))
    ayyw = (2 * n * E4 / ew14 + 2 * s * E3 / ew23) / (w * (n + s))
    ayyp = (-(ayyn + ayys + ayye + ayyw)
            + k0 ** 2 * (e + w) * (E1 * E4 * n / ew14 + E2 * E3 * s / ew23) / (n + s))

    # ---- Axy ----
    d24_13 = E2 * E4 - E1 * E3
    axyn = (E3 / ns34 - E2 / ns21 + s * d24_13 / (ns21 * ns34)) / (e + w)
    axys = (E1 / ns21 - E4 / ns34 + n * d24_13 / (ns21 * ns34)) / (e + w)
    axye = -2.0 * ((E2 - E1) * w ** 2 / ns21 + (E3 - E4) * e * w / ns34) / (e * (e + w) ** 2)
    axyw = -2.0 * ((E4 - E3) * e ** 2 / ns34 + (E1 - E2) * w * e / ns21) / (w * (e + w) ** 2)
    axyp = -(axyn + axys + axye + axyw)

    # ---- Ayx ----
    ayxn = -2.0 * ((E2 - E3) * s ** 2 / ew23 + (E1 - E4) * n * s / ew14) / (n * (n + s) ** 2)
    ayxs = -2.0 * ((E4 - E1) * n ** 2 / ew14 + (E3 - E2) * s * n / ew23) / (s * (n + s) ** 2)
    ayxe = (E1 / ew14 - E2 / ew23 + w * d24_13 / (ew23 * ew14)) / (n + s)
    ayxw = (E3 / ew23 - E4 / ew14 + e * d24_13 / (ew23 * ew14)) / (n + s)
    ayxp = -(ayxn + ayxs + ayxe + ayxw)

    return dict(nx=nx, ny=ny,
                axxn=axxn, axxs=axxs, axxe=axxe, axxw=axxw, axxp=axxp,
                ayyn=ayyn, ayys=ayys, ayye=ayye, ayyw=ayyw, ayyp=ayyp,
                axyn=axyn, axys=axys, axye=axye, axyw=axyw, axyp=axyp,
                ayxn=ayxn, ayxs=ayxs, ayxe=ayxe, ayxw=ayxw, ayxp=ayxp)


def build_operator(eps: np.ndarray, dx: np.ndarray, dy: np.ndarray, k0: float):
    """返回 (A, nx, ny)：A h = β² h，h=[Hx;Hy]，N=nx·ny 顶点。"""
    c = coeffs(eps, dx, dy, k0)
    nx, ny = c["nx"], c["ny"]
    N = nx * ny

    jj = np.arange(N).reshape((ny, nx), order="C")
    jall = jj.ravel(order="C")
    js = jj[:-1, :].ravel(order="C"); jn = jj[1:, :].ravel(order="C")
    jw = jj[:, :-1].ravel(order="C"); je = jj[:, 1:].ravel(order="C")

    rows = np.concatenate([jall, jw, je, js, jn])
    cols = np.concatenate([jall, je, jw, jn, js])

    def blk(dp, de, dw, dn, ds):
        v = np.concatenate([dp[jall], de[jw], dw[je], dn[js], ds[jn]])
        return coo_matrix((v, (rows, cols)), shape=(N, N)).tocsr()

    A = bmat([[blk(c["axxp"], c["axxe"], c["axxw"], c["axxn"], c["axxs"]),
               blk(c["axyp"], c["axye"], c["axyw"], c["axyn"], c["axys"])],
              [blk(c["ayxp"], c["ayxe"], c["ayxw"], c["ayxn"], c["ayxs"]),
               blk(c["ayyp"], c["ayye"], c["ayyw"], c["ayyn"], c["ayys"])]],
             format="csr")
    A.eliminate_zeros()
    return A, nx, ny


# ═══════════════════════════════════════════════════════════════════
# 求解 + 选模
# ═══════════════════════════════════════════════════════════════════
def _half_win(w: float, h_core: float, L: Optional[float]) -> float:
    if L is not None:
        return float(L)
    return max(L_HALF_MIN, HALF_WIN_MULT * max(w, h_core))


def core_vertex_mask(eps: np.ndarray) -> np.ndarray:
    """由 cell 级 ε 场推「芯区顶点掩码」→ shape (ny_cells+1, nx_cells+1)。

    芯 cell = ε 实部高于 (min+max)/2；顶点归芯 ⟺ 其四邻 cell 中**任一**为芯
    （一格膨胀，保证居中矩形的边界顶点仍算芯内）。

    🔴 仅供**未显式给掩码**的任意截面调用；条形路径由 `solve_modes` 显式传入
    精确解析掩码，以保证既有判据**逐位不变**。
    """
    e = np.asarray(eps).real
    nyc, nxc = e.shape
    cell = e > 0.5 * (float(e.min()) + float(e.max()))
    p = np.pad(cell, 1, mode="constant", constant_values=False)
    return (p[0:nyc + 1, 0:nxc + 1] | p[0:nyc + 1, 1:nxc + 2]
            | p[1:nyc + 2, 0:nxc + 1] | p[1:nyc + 2, 1:nxc + 2])


def solve_modes_eps(eps: np.ndarray, xv: np.ndarray, yv: np.ndarray, k0: float,
                    k: int = K_EIGS, sigma: Optional[float] = None,
                    n_lo: Optional[float] = None, n_hi: Optional[float] = None,
                    core_vmask: Optional[np.ndarray] = None,
                    conf_min: float = 0.30) -> List[ModeResult]:
    """**任意 2D 截面**本征模 —— G12-A 的通用求解入口。

    几何只以 ε 场表达（shape `(ny_cells, nx_cells)`，值 = n²），算子与选模
    完全复用既有 `build_operator` ⇒ **本函数不引入任何新的物理模型**。

    - `n_lo` / `n_hi`：受限模折射率下/上界；缺省由 ε 场的 min/max 实部推出。
    - `core_vmask`：芯区顶点掩码；缺省由 `core_vertex_mask(eps)` 推出。
    """
    eps = np.asarray(eps)
    e = eps.real
    if n_lo is None:
        n_lo = math.sqrt(max(float(e.min()), 1e-12))
    if n_hi is None:
        n_hi = math.sqrt(max(float(e.max()), 1e-12))
    dx = np.diff(np.asarray(xv))
    dy = np.diff(np.asarray(yv))
    A, nx, ny = build_operator(eps, dx, dy, k0)
    N = nx * ny

    if sigma is None:
        sigma = (k0 * (n_lo + 0.85 * (n_hi - n_lo))) ** 2
    try:
        vals, vecs = eigs(A, k=k, sigma=sigma, which="LM")
    except Exception:                                    # noqa: BLE001
        return []
    if core_vmask is None:
        core_vmask = core_vertex_mask(eps)

    out: List[ModeResult] = []
    for m in range(vals.shape[0]):
        v = vals[m]
        if not np.isfinite(v.real) or v.real <= 0:
            continue
        neff = math.sqrt(v.real) / k0
        if not (n_lo + 1e-3 < neff < n_hi + 1e-4):
            continue
        hv = vecs[:, m]
        hx2 = np.abs(hv[:N]) ** 2
        hy2 = np.abs(hv[N:]) ** 2
        tot = float((hx2 + hy2).sum())
        if tot <= 0:
            continue
        hx2g = hx2.reshape((ny, nx), order="C")
        hy2g = hy2.reshape((ny, nx), order="C")
        e2 = hx2g + hy2g
        conf = float(e2[core_vmask].sum() / tot)
        imax = np.unravel_index(int(np.argmax(e2)), e2.shape)
        peak = bool(core_vmask[imax[0], imax[1]])
        hy_core = float(hy2g[core_vmask].sum() /
                        max(float((hy2g[core_vmask] + hx2g[core_vmask]).sum()), 1e-300))
        out.append(ModeResult(neff=neff, conf_core=conf, peak_in_core=peak,
                              im_beta2=float(v.imag), frac_hy_core=hy_core,
                              hx=hv[:N].reshape((ny, nx), order="C"),
                              hy=hv[N:].reshape((ny, nx), order="C")))
    # 只保留受限良好、峰在芯内的模；
    # 排序按 n_eff 降序（基模在前）——conf 排序会被 PML 伪模污染
    good = [r for r in out if r.conf_core > conf_min and r.peak_in_core]
    good.sort(key=lambda r: -r.neff)
    return good


def solve_modes(w: float, h_core: float, wl: float,
                n_core: float, n_clad: float,
                h_grid: float = H_GRID, L: Optional[float] = None,
                n_pml: int = 0, A_pml: float = 0.0,
                k: int = K_EIGS) -> List[ModeResult]:
    """解条形波导本征模，返回按 n_eff 降序（基模在前）的 ModeResult 列表。

    几何自动 snap 到网格线（半宽取整到 h_grid 整数倍）——避免楼梯误差主导。

    🔴 v0.9.136 起本函数改为**委托** `solve_modes_eps`，并显式传入精确矩形掩码
    ⇒ 求解与选模路径与重构前**逐位一致**（由既有 13 判据锁死）。
    """
    hw = max(int(round(w / 2.0 / h_grid)), 1) * h_grid
    hh = max(int(round(h_core / 2.0 / h_grid)), 1) * h_grid
    w, h_core = 2.0 * hw, 2.0 * hh

    k0 = 2.0 * math.pi / wl
    Lh = _half_win(w, h_core, L)
    xv = build_grid(Lh, h_grid, n_pml, A_pml)
    xc = 0.5 * (xv[:-1] + xv[1:])
    eps = eps_cells(w, h_core, n_core, n_clad, xc, xc)

    mx = (np.abs(xv.real) <= w / 2.0 + 1e-12)
    my = (np.abs(xv.real) <= h_core / 2.0 + 1e-12)
    core_vmask = my[:, None] & mx[None, :]
    sigma = (k0 * (n_clad + 0.85 * (n_core - n_clad))) ** 2
    return solve_modes_eps(eps, xv, xv, k0, k=k, sigma=sigma,
                           n_lo=n_clad, n_hi=n_core,
                           core_vmask=core_vmask, conf_min=0.30)


def neff_2d(eps: np.ndarray, h: float, wl: float, pol: str = "TE",
            k: int = K_EIGS, core_vmask: Optional[np.ndarray] = None,
            conf_min: float = 0.30) -> float:
    """**任意 2D 截面**（cell-centered ε = n²，shape `(ny_cells, nx_cells)`）
    指定偏振基模 n_eff —— G12-A 对外主入口。

    对标 `semivec_mode_solver.neff_2d(n2, h, k0, ...)`：**同一份场**（两者都是
    n²）可分别喂给半矢量与全矢量 ⇒ 构成本仓又一组**方法学独立互验**。

    🔴 本入口按「场已给定 + 网格均匀」构造节点坐标，**不启用 PML**；需要 PML 的
    任意截面请直接调 `solve_modes_eps`（自行给含复坐标拉伸的 xv/yv）。
    """
    eps = np.asarray(eps)
    nyc, nxc = eps.shape
    k0 = 2.0 * math.pi / wl
    xv = (np.arange(nxc + 1) - nxc / 2.0) * h
    yv = (np.arange(nyc + 1) - nyc / 2.0) * h
    rs = solve_modes_eps(eps, xv, yv, k0, k=k,
                         core_vmask=core_vmask, conf_min=conf_min)
    want_hy = (pol.upper() == "TE")
    for r in rs:                                    # 已按 n_eff 降序
        if (r.frac_hy_core > 0.5) == want_hy:
            return r.neff
    return float("nan")


def neff_strip(w: float, h_core: float, wl: float,
               n_core: float = 2.0, n_clad: float = 1.44,
               core_material: Optional[str] = None,
               clad_material: Optional[str] = None, wl_ref: float = 1.55,
               pol: str = "TE", **kw) -> float:
    """条形波导指定偏振基模 n_eff。

    pol="TE" ⇒ 准 TE（Hy 主导，E 主要横向）；pol="TM" ⇒ 准 TM（Hx 主导）。
    未找到合格模返回 nan。
    """
    nc = _n_disp(wl, n_core, wl_ref, core_material)
    ncl = _n_disp(wl, n_clad, wl_ref, clad_material)
    rs = solve_modes(w, h_core, wl, nc, ncl, **kw)
    want_hy = (pol.upper() == "TE")
    for r in rs:                                    # 已按 n_eff 降序
        if (r.frac_hy_core > 0.5) == want_hy:
            return r.neff
    return float("nan")


def group_index(w: float, h_core: float, wl: float,
                n_core: float = 2.0, n_clad: float = 1.44,
                core_material: Optional[str] = None,
                clad_material: Optional[str] = None, wl_ref: float = 1.55,
                d_wl: float = D_WL, pol: str = "TE", **kw) -> float:
    """n_g = n_eff − λ·dn_eff/dλ（λ 中心差分）。

    🔴 三个 λ 上**网格与窗口必须完全相同**，否则测到的是网格伪变化而非物理色散。
    """
    kw2 = dict(kw)
    nm = neff_strip(w, h_core, wl, n_core, n_clad, core_material, clad_material,
                    wl_ref, pol=pol, **kw2)
    nl = neff_strip(w, h_core, wl - d_wl, n_core, n_clad, core_material,
                    clad_material, wl_ref, pol=pol, **kw2)
    nh = neff_strip(w, h_core, wl + d_wl, n_core, n_clad, core_material,
                    clad_material, wl_ref, pol=pol, **kw2)
    return nm - wl * (nh - nl) / (2.0 * d_wl)


# ---------------------------------------------------------------------------
# 材料色散（复用同仓 Sellmeier，λ 单位 µm）
# ---------------------------------------------------------------------------
def _n_disp(wl: float, value_at_ref: float, wl_ref: float,
            material: Optional[str]) -> float:
    """有 material 时走 Sellmeier；否则按常数折射率（不随 λ 变）。"""
    if not material:
        return float(value_at_ref)
    try:
        from lda.lda_solver import semivec_mode_solver as _sv       # type: ignore
    except ImportError:                                            # pragma: no cover
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
        import semivec_mode_solver as _sv                          # type: ignore
    key = material.strip().lower().replace("₃", "3")
    fn = {"si": _sv.sellmeier_si, "sio2": _sv.sellmeier_sio2,
          "si3n4": _sv.sellmeier_si3n4}.get(key)
    if fn is None:
        return float(value_at_ref)
    return float(fn(wl) / fn(wl_ref) * value_at_ref)               # 保 n(wl_ref) 一致


# ---------------------------------------------------------------------------
# 自校锚
# ---------------------------------------------------------------------------
SOI_W, SOI_H, SOI_NC, SOI_NCL = 0.6, 0.22, 3.4777, 1.4441
SIN_W, SIN_H, SIN_NC, SIN_NCL = 1.2, 0.3, 1.9963, 1.4441
# G12-A 脊形（rib）样例几何：脊 0.48 宽 × 0.20 高，坐在厚 0.12 的平板上
# 🔴 三个尺寸在 h=0.04/0.02/0.01 上都是**整格**且总高/脊宽为**偶格** ⇒
#    三档网格上几何逐格相同，收敛序列测到的才是纯离散误差（见 eps_rib 注②）
RIB_W, RIB_H, RIB_T = 0.48, 0.20, 0.12
# 仿真值（参考实现 / FDE）——仅作「外部对标」，**不作 golden**
SOI_REF_NEFF = 2.570410
SIN_REF_NEFF = 1.597884
SIN_NG_MEASURED = 1.9666        # A 级实测事实（Coatings 10(4) 309 (2020)）


def selfcheck_uniform_limit(tol: float = 1e-8, h: float = 0.02,
                            Lhalf: float = 0.8) -> List[tuple]:
    """① 闭式物理律（**精确**）：均匀介质的最大本征值有闭式。

    均匀 ε 时 A = diag(Lx, Ly)⊗，各为「五点拉普拉斯 + k0²n²」；两端 ghost 取 0
    （硬 Dirichlet）⇒ 一维离散本征值 λ_m = (2−2cos(mπ/(M+1)))/h²，其中
    **M = 节点数 = 单元数+1**（易错：写成单元数会差 1，实测差 3.7e-1）。

        max β² = k0²n² − 2·λ_1 ,  λ_1 = (2 − 2cos(π/(M+1)))/h²

    实测（h=0.1,N=8）46.151502 vs 闭式 46.1510；h=0.02,N=80）26.735670 vs 26.7353。
    """
    rows = []
    k0 = 2.0 * math.pi / 1.55
    for n in (1.44, 2.0, 3.0):
        xv = build_grid(Lhalf, h, 0, 0.0)
        dx = np.diff(xv)
        n_cells = len(dx)
        eps = np.full((n_cells, n_cells), n ** 2)
        A, _nx, _ny = build_operator(eps, dx, dx, k0)
        b2 = float(eigsh(A, k=1, which="LA", return_eigenvectors=False)[0])
        m_nodes = n_cells + 1
        lam1 = (2.0 - 2.0 * math.cos(math.pi / (m_nodes + 1))) / h ** 2
        ex = (k0 * n) ** 2 - 2.0 * lam1
        rows.append((f"uniform[n={n}]", b2, ex, b2 - ex, tol, abs(b2 - ex) <= tol))
    return rows


def selfcheck_strip_bounds(w=SOI_W, h_core=SOI_H, n_core=SOI_NC, n_clad=SOI_NCL,
                           verbose: bool = False) -> List[tuple]:
    """② 闭式物理律：受限模必须 n_clad < n_eff < n_core，且准 TE ≥ 准 TM（双折射符号）。"""
    rows = []
    nc_te = neff_strip(w, h_core, 1.55, n_core, n_clad, pol="TE")
    nc_tm = neff_strip(w, h_core, 1.55, n_core, n_clad, pol="TM")
    if verbose:
        print(f"  [边界律] TE={nc_te:.6f} TM={nc_tm:.6f} "
              f"(clad={n_clad} core={n_core})")
    rows.append(("bound[n_clad<n_eff<n_core]",
                 nc_te, n_core, nc_te - n_core, 0.0,
                 bool(math.isfinite(nc_te) and n_clad < nc_te < n_core)))
    rows.append(("birefringence[TE>=TM]", nc_te, nc_tm, nc_te - nc_tm, 0.0,
                 bool(math.isfinite(nc_tm) and nc_te >= nc_tm)))
    return rows


def selfcheck_sin_pristine_control(tol: float = 3e-3, L: float = 2.4,
                                   verbose: bool = False) -> tuple:
    """③ A 级实证锚（唯一外部真值）：SiN 1.2×0.3 TE 实测 n_g = 1.9666。

    出处：Coatings (MDPI) 10(4) 309 (2020) Fig.5 —— FSR=1.9078 nm、R=100 µm、
    n=1.9963@1550nm、全 PECVD silica 包层；λ²/(FSR·L)=1.9666 自洽。
    返回 (ng_calc, 1.9666, Δ)。

    🔴 **诚实记录（不得含糊）**：本模块实测 n_g = 1.968004 ⇒ Δ=+1.4e-3（0.07%）；
    半矢量模块同题 Δ=+8.4e-5。差 17×，来源是
      · 对象不对齐：实测是 R=100 µm **环**，候选是**直波导**；
      · 离散差异：本模块 h=0.01 楼梯 H-field vs 半矢量 h=0.015 调和界面。
    ⇒ **低对比度的绝对 n_g 精度仍以半矢量为准**；本模块的价值在**高对比度**
    （SOI +0.0276 → +0.004）。此处容差 3e-3 是「跨对象量级一致」上界，不是精度声明。
    """
    ng = group_index(SIN_W, SIN_H, 1.55, n_core=SIN_NC, n_clad=SIN_NCL,
                     core_material="Si3N4", clad_material="SiO2", L=L)
    if verbose:
        print(f"  [实证对照] SiN 1.2x0.3 TE  n_g(算)={ng:.6f} "
              f"n_g(实测)={SIN_NG_MEASURED:.6f}  Δ={ng - SIN_NG_MEASURED:+.3e}"
              f" （半矢量同题 Δ=+8.4e-5）")
    return ng, SIN_NG_MEASURED, ng - SIN_NG_MEASURED


def selfcheck_low_contrast_vs_semivec(tol: float = 3e-3,
                                      verbose: bool = False) -> tuple:
    """④ 低对比度退化：全矢量 vs 半矢量（方法学独立，同仓自研）须一致。

    SiN（Δn=0.55）半矢量误差 ≲1e-3 ⇒ 两法必须吻合，否则全矢量有偏。
    """
    try:
        from lda.lda_solver import semivec_mode_solver as sv
    except ImportError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
        import semivec_mode_solver as sv                            # type: ignore
    fv = neff_strip(SIN_W, SIN_H, 1.55, SIN_NC, SIN_NCL, L=2.4)
    sv_ne = sv.neff_strip(SIN_W, SIN_H, 1.55, n_core=SIN_NC, n_clad=SIN_NCL,
                          h_grid=sv.H_GRID, L=sv.L_WIN)
    d = fv - sv_ne
    if verbose:
        print(f"  [低对比度退化] 全矢量={fv:.6f} 半矢量={sv_ne:.6f} Δ={d:+.3e}")
    return fv, sv_ne, d


def selfcheck_highcontrast_regression(tol: float = 2e-3,
                                      verbose: bool = False) -> tuple:
    """⑤ 高对比度**回归锁**（非 golden！）：SOI 600×220 TE0 须复现 2.570410。

    声明：2.570410 是**同一离散的参考实现值（仿真值）**，按本仓铁律不作 golden。
    本项是**回归锁**，防实现被改坏；绝对精度只以「外部对标」表述
    （对 Lumerical FDE 2.566 偏 +0.004，半矢量同题 +0.0276）。
    """
    ne = neff_strip(SOI_W, SOI_H, 1.55, SOI_NC, SOI_NCL, L=1.5)
    d = ne - SOI_REF_NEFF
    if verbose:
        print(f"  [高对比度回归锁] SOI 600x220 TE0 n={ne:.6f} "
              f"锁值={SOI_REF_NEFF:.6f} Δ={d:+.2e}（tol={tol:g}）")
    return ne, SOI_REF_NEFF, d


def selfcheck_grid_convergence(hs=(0.010, 0.005), tol: float = 2e-3,
                               L: float = 1.0, verbose: bool = False) -> List[tuple]:
    """⑥ 网格收敛：SOI n_eff 随 h 收缩趋稳（h=0.01→0.005 须 ≤ tol）。

    实测 2.570410 → 2.569920（Δ=4.9e-4）；L=1.0 已被证明与 L=2.0 逐位相同。
    """
    rows = []
    vals = {}
    for h in hs:
        vals[h] = neff_strip(SOI_W, SOI_H, 1.55, SOI_NC, SOI_NCL, h_grid=h, L=L)
    if verbose:
        print("  [网格收敛] " + " ".join(f"h={h}:{v:.6f}" for h, v in vals.items()))
    for i in range(len(hs) - 1):
        dh = abs(vals[hs[i]] - vals[hs[i + 1]])
        rows.append((f"convergence[h={hs[i]}→{hs[i+1]}]", vals[hs[i]],
                     vals[hs[i + 1]], dh, tol, bool(math.isfinite(dh) and dh <= tol)))
    return rows


# ═══════════════════════════════════════════════════════════════════
# G12-A：任意 2D 截面（rib / 多层 / 复杂形状）自检
# ═══════════════════════════════════════════════════════════════════
def _arb_grid(Lh: float, h: float):
    """任意截面的均匀网格 → (节点 xv, 格心 xc)；xc 同时用作 y 方向格心。"""
    n = 2 * int(round(Lh / h))
    xv = (np.arange(n + 1) - n / 2.0) * h
    return xv, 0.5 * (xv[:-1] + xv[1:])


def _semivec():
    try:
        from lda.lda_solver import semivec_mode_solver as sv
    except ImportError:
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
        import semivec_mode_solver as sv                            # type: ignore
    return sv


def selfcheck_arbitrary_strip_degeneracy(tol: float = 1e-9,
                                         verbose: bool = False) -> tuple:
    """⑦ **退化一致性锁**：居中矩形 ε 场经任意截面入口 `neff_2d` ⇒ 必须与
    既有条形封装 `neff_strip` 给出同一数字。

    这是「新入口没改坏既有路径」的机器锁：同一几何、同一网格、同一算子、同一
    σ，只换调用路径（便捷封装 vs 任意 ε 场）。tol=1e-9 远严于物理容差 2e-3，
    留 ~1e-3 量级给 ARPACK 迭代的随机起始向量残差。
    """
    h = H_GRID
    w, hc = SOI_W, SOI_H
    hw = max(int(round(w / 2.0 / h)), 1) * h
    hh = max(int(round(hc / 2.0 / h)), 1) * h
    w, hc = 2.0 * hw, 2.0 * hh
    Lh = _half_win(w, hc, None)
    xv, xc = _arb_grid(Lh, h)
    eps = eps_cells(w, hc, SOI_NC, SOI_NCL, xc, xc)
    mx = (np.abs(xv.real) <= w / 2.0 + 1e-12)
    my = (np.abs(xv.real) <= hc / 2.0 + 1e-12)
    vmask = my[:, None] & mx[None, :]

    a = neff_2d(eps, h, 1.55, pol="TE", core_vmask=vmask)
    b = neff_strip(SOI_W, SOI_H, 1.55, SOI_NC, SOI_NCL, h_grid=h, L=Lh)
    d = a - b
    if verbose:
        print(f"  [任意截面·退化一致] neff_2d={a:.9f} neff_strip={b:.9f} "
              f"Δ={d:+.2e}（tol={tol:g}）")
    return a, b, d


def selfcheck_arbitrary_lowcontrast_vs_semivec(h: float = 0.02, Lh: float = 2.4,
                                               tol: float = 3e-3,
                                               verbose: bool = False) -> tuple:
    """⑧ **任意截面 × 方法学独立互验**：把**同一份** SiN 矩形 n² 场分别喂给
    全矢量 `neff_2d` 与半矢量 `semivec_mode_solver.neff_2d`，低对比度（Δn=0.55）
    下两法必须吻合。

    ⇒ 这给 P3「横向交叉验证网」再添一格：器件=条形波导 × 物理量=n_eff，
      两法=**半矢量（约束 E_y≡0）↔ 全矢量（H-field staggered）**，方法学独立。
    """
    sv = _semivec()
    xc = _arb_grid(Lh, h)[1]
    n = xc.size
    n2 = sv.build_index_2d(n, n, h, SIN_W, SIN_H, SIN_NC, SIN_NCL)   # (nx, ny)
    fv = neff_2d(np.asarray(n2).T, h, 1.55, pol="TE")
    k0 = 2.0 * math.pi / 1.55
    sv_ne = sv.neff_2d(n2, h, k0, k=8, n_core=SIN_NC, n_clad=SIN_NCL)
    sv_ne = float(sv_ne[0]) if isinstance(sv_ne, (tuple, list)) else float(sv_ne)
    d = fv - sv_ne
    if verbose:
        print(f"  [任意截面·低对比度互验] 全矢量={fv:.6f} 半矢量={sv_ne:.6f} "
              f"Δ={d:+.3e}（h={h}, L={2*Lh}）")
    return fv, sv_ne, d


def selfcheck_rib_slab_monotonic(h: float = 0.02, Lh: float = 1.6,
                                 ts=(0.0, 0.04, 0.08, 0.12),
                                 verbose: bool = False) -> List[tuple]:
    """⑨ **物理必然性**：脊形波导的平板层厚度 t ↑ ⇒ 芯区高折射率材料**只增不减**
    ⇒ 基模 n_eff 必须**严格单调递增**。

    这是「任意截面几何真的被算子读进去了」的可证伪判据：若 `eps_rib` 的 slab
    分支没生效（例如写错成恒等于 ridge），n_eff 会与 t **无关** ⇒ 单调性立刻变红。
    """
    xc = _arb_grid(Lh, h)[1]
    vals = []
    for t in ts:
        eps = eps_rib(RIB_W, RIB_H, t, SOI_NC, SOI_NCL, xc, xc)
        vals.append(neff_2d(eps, h, 1.55, pol="TE"))
    if verbose:
        print("  [脊形·slab 单调] " + " ".join(f"t={t}:{v:.6f}" for t, v in zip(ts, vals)))
    rows = []
    for i in range(len(ts) - 1):
        dd = vals[i + 1] - vals[i]
        rows.append((f"rib_mono[t={ts[i]}→{ts[i+1]}]", vals[i], vals[i + 1], dd,
                     0.0, bool(math.isfinite(dd) and dd > 0.0)))
    return rows


def selfcheck_rib_slab_loadbearing(h: float = 0.02, Lh: float = 1.6,
                                   floor: float = 1e-3,
                                   verbose: bool = False) -> tuple:
    """⑨b **slab 分支承重**：完整脊形 vs 抹掉平板层（`slab_t=0`，只剩居中矩形）
    的 n_eff 必须显著不同。

    若有人把 `eps_rib` 改写成「只画脊」（slab 分支成装饰代码），本行会立刻变红
    —— 这正是 **⑰ 反向测试**要的那条eps，落进行集合 ⇒ 可被 `scripts/g12a_probe.py`
    直接打到。
    """
    xc = _arb_grid(Lh, h)[1]
    eps_full = eps_rib(RIB_W, RIB_H, RIB_T, SOI_NC, SOI_NCL, xc, xc)
    eps_noslab = eps_rib(RIB_W, RIB_H, 0.0, SOI_NC, SOI_NCL, xc, xc)
    v_full = neff_2d(eps_full, h, 1.55, pol="TE")
    v_no = neff_2d(eps_noslab, h, 1.55, pol="TE")
    d = abs(v_full - v_no)
    if verbose:
        print(f"  [脊形·slab 承重] 完整={v_full:.6f} 仅留脊={v_no:.6f} "
              f"|Δ|={d:.3e}（须 > {floor:g}）")
    return v_full, v_no, d


def selfcheck_rib_vs_semivec_nonzero(h: float = 0.02, Lh: float = 1.6,
                                     floor: float = 1e-4,
                                     verbose: bool = False) -> tuple:
    """⑩ **反自证桩**：高对比度 SOI 脊形波导上，全矢量与半矢量**必须不同**。

    若两法给出同一数字 ⇒ 说明任意截面入口退化成了半矢量（复制粘贴/误接线），
    判据必须变红。**「两法相同」在这里是缺陷信号，不是一致性证据。**
    """
    sv = _semivec()
    xc = _arb_grid(Lh, h)[1]
    eps = eps_rib(RIB_W, RIB_H, RIB_T, SOI_NC, SOI_NCL, xc, xc)
    fv = neff_2d(eps, h, 1.55, pol="TE")
    # 半矢量侧喂**同一份场**（半矢量只认场，不认形状名）⇒ 两法唯一差别是物理模型
    thr = 0.5 * (SOI_NC ** 2 + SOI_NCL ** 2)
    n2_rib = np.where(np.asarray(eps).T > thr, SOI_NC ** 2, SOI_NCL ** 2)
    k0 = 2.0 * math.pi / 1.55
    sv_ne = sv.neff_2d(n2_rib, h, k0, k=8, n_core=SOI_NC, n_clad=SOI_NCL)
    sv_ne = float(sv_ne[0]) if isinstance(sv_ne, (tuple, list)) else float(sv_ne)
    d = abs(fv - sv_ne)
    if verbose:
        print(f"  [脊形·反自证桩] 全矢量={fv:.6f} 半矢量={sv_ne:.6f} "
              f"|Δ|={d:.3e}（须 > {floor:g}）")
    return fv, sv_ne, d


def selfcheck_rib_grid_convergence(hs=(0.020, 0.010), tol: float = 2e-3,
                                   Lh: float = 1.6,
                                   verbose: bool = False) -> List[tuple]:
    """⑪ 脊形波导网格收敛（与条形同口径）：h 减半后 n_eff 变化 ≤ tol。"""
    rows, vals = [], {}
    for h in hs:
        xc = _arb_grid(Lh, h)[1]
        eps = eps_rib(RIB_W, RIB_H, RIB_T, SOI_NC, SOI_NCL, xc, xc)
        vals[h] = neff_2d(eps, h, 1.55, pol="TE")
    if verbose:
        print("  [脊形·网格收敛] " + " ".join(f"h={h}:{v:.6f}" for h, v in vals.items()))
    for i in range(len(hs) - 1):
        dh = abs(vals[hs[i]] - vals[hs[i + 1]])
        rows.append((f"rib_conv[h={hs[i]}→{hs[i+1]}]", vals[hs[i]],
                     vals[hs[i + 1]], dh, tol,
                     bool(math.isfinite(dh) and dh <= tol)))
    return rows


# ═══════════════════════════════════════════════════════════════════
# G12-B：真 3D 空间全矢量本征模（collocated 3D 向量拉普拉斯 FDFD）—— 2026-09-24
# ═══════════════════════════════════════════════════════════════════
#
# 求解对象：六面 PEC 金属腔（墙 E_tan=0）中的三维本征模。Helmholtz
#     ∇²E + k0² n² E = 0  ⇒  -∇²E = k0² n² E
# 用 collocated 有限差分（E 在每内部节点取值，墙 DOF 直接剔除 = 硬 Dirichlet）：
#     · 单分量 3D 拉普拉斯 = Lx⊗Iy⊗Iz + Ix⊗Ly⊗Iz + Ix⊗Iy⊗Lz
#       其中 Lx 是 1D **内部节点** Dirichlet 拉普拉斯（M=N-1，墙不计），
#       3 点格式，特征值 λ_m=(2/h²)(1-cos(mπ/N))→(mπ/L)²（O(h²)）。
#     · 三分量块对角 ⇒ 完整向量拉普拉斯。
#     · 质量矩阵 M：节点 ε = 周围 8 个 cell 的算术平均（collocated FDFD 节点平均）；
#       广义本征问题 KE E = k0² M E。
#
# 🔴 为什么是 collocated 向量拉普拉斯，而非 Yee 交错 curl-curl：
#   交错 curl-curl（K=C1ᵀ M_H C1）在此 PEC 方案下有 (N-2)³ 维离散梯度零空间
#   （伪 DC 模），且**最低物理本征值发散**（实测 8.0→6.03 随 N 不收敛到闭环金），
#   系统性错误。collocated 向量拉普拉斯正定、无伪零空间、h→0 收敛到闭环金，
#   收敛阶 rate=2.00 已由常驻门禁 `selfcheck_3d_convergence` 复现（smoke 判据 ⑲）。
#
# 🔴 诚实边界：本模块的 golden 只有**闭式物理律**（均匀立方腔
#   k0²(1,1,1)=3(π/L)²/n²、k0²(2,1,1)=2·k0²(1,1,1)）。任何商业/参考求解器的
#   数值属「仿真值」，按本仓铁律**不作 golden**（仅外部对标）。
H_GRID_3D = 0.02          # µm 3D 默认网格（与 2D 不同尺度，独立档位）
K_EIGS_3D = 8             # ARPACK 请求本征对数


def _laplacian_1d_dirichlet(N, h):
    """1D Dirichlet 拉普拉斯（内部节点版）。N 单元 ⇒ M=N-1 内部节点（墙剔除）。

    3 点格式（主 2/h²，次 -1/h²）；特征值 λ_m=(2/h²)(1-cos(mπ/N))→(mπ/L)²，O(h²)。
    """
    M = max(N - 1, 1)
    main = 2.0 / h ** 2 * np.ones(M)
    off = -1.0 / h ** 2 * np.ones(M - 1)
    return diags([off, main, off], [-1, 0, 1], shape=(M, M)).tocsr()


def build_operator_3d(eps3d, h):
    """collocated 3D 向量拉普拉斯 FDFD。eps3d: (Nx,Ny,Nz) 折射率平方（cell-centered）。

    返回 (KE, M, Nx, Ny, Nz)。广义本征问题 KE E = k0² M E，E 定义在
    (Nx-1)×(Ny-1)×(Nz-1) 内部节点，PEC 墙由剔除墙 DOF 实现（E_tan=0）。

    质量矩阵 M 为节点对角阵：每节点 ε = 周围 8 个 cell 的算术平均
    （collocated FDFD 节点平均）；均匀 ε 下自动退化为常数，与原型 v6 一致。
    """
    eps3d = np.asarray(eps3d, dtype=float)
    Nx, Ny, Nz = eps3d.shape
    Lx = _laplacian_1d_dirichlet(Nx, h)
    Ly = _laplacian_1d_dirichlet(Ny, h)
    Lz = _laplacian_1d_dirichlet(Nz, h)
    Ix = eye(Lx.shape[0]); Iy = eye(Ly.shape[0]); Iz = eye(Lz.shape[0])
    # 单分量 3D 拉普拉斯
    K1 = (kron(kron(Lx, Iy), Iz)
          + kron(kron(Ix, Ly), Iz)
          + kron(kron(Ix, Iy), Lz)).tocsr()
    # 三分量块对角
    KE = (kron(eye(3), K1)).tocsr()
    nn = (Nx - 1) * (Ny - 1) * (Nz - 1)
    # 节点 ε：周围 8 cell 平均（墙外一圈 pad 为 edge，不参与内部节点）
    e = eps3d.real
    pad = np.pad(e, 1, mode="edge")
    node_eps = (pad[1:Nx, 1:Ny, 1:Nz] + pad[2:Nx + 1, 1:Ny, 1:Nz]
                + pad[1:Nx, 2:Ny + 1, 1:Nz] + pad[2:Nx + 1, 2:Ny + 1, 1:Nz]
                + pad[1:Nx, 1:Ny, 2:Nz + 1] + pad[2:Nx + 1, 1:Ny, 2:Nz + 1]
                + pad[1:Nx, 2:Ny + 1, 2:Nz + 1] + pad[2:Nx + 1, 2:Ny + 1, 2:Nz + 1]) / 8.0
    Mvec = np.tile(node_eps.ravel(order="C"), 3)
    M = coo_matrix((Mvec, (np.arange(3 * nn), np.arange(3 * nn))),
                   shape=(3 * nn, 3 * nn)).tocsr()
    return KE, M, Nx, Ny, Nz


def cavity_k0_sq(eps3d, h, k: int = K_EIGS_3D):
    """立方/任意腔基模及若干低阶本征 k0²（升序）→ ndarray（length min(k, …)）。

    广义本征问题 KE E = k0² M E 经 M^{-1/2} 对称化：Astd = D KE D（D=diag(1/√M)），
    最小代数本征值 = 最小 k0²（物理基模）。轴对称立方腔 (1,1,1) 三重简并、
    下一簇 (2,1,1) 族 = 2× 基模（闭式），见 selfcheck。
    """
    KE, M, Nx, Ny, Nz = build_operator_3d(eps3d, h)
    md = np.asarray(M.diagonal()).ravel()
    md = np.where(md <= 0, 1.0, md)
    mh = 1.0 / np.sqrt(md)
    D = csr_matrix((mh, (np.arange(len(mh)), np.arange(len(mh)))),
                   shape=(len(mh), len(mh)))
    Astd = (D @ KE @ D).tocsr()
    Astd = 0.5 * (Astd + Astd.T)
    kk = min(k, Astd.shape[0] - 2)
    if kk < 1:
        kk = 1
    vals = eigsh(Astd, k=kk, which="SM", return_eigenvectors=False)
    return np.sort(np.real(vals))


# 与 G12-A `solve_modes_eps` 同风格命名（任意 3D 截面求解入口）
solve_modes_eps_3d = cavity_k0_sq


def neff_3d(eps3d, h, wl, k: int = K_EIGS_3D) -> float:
    """任意 3D 截面（cell-centered n²，(Nx,Ny,Nz)）**基模等效指标**。

    返回 `k0_res / k0_free`，即基模谐振波数相对真空波数的比值（<1 表示介质加载
    使腔谐振频率下降）。闭式对照请直接用 `cavity_k0_sq`（与波长无关）。

    🔴 与 G12-A `neff_2d` 同签名风格（场已给定 + 均匀网格），但不启用 PML。
    """
    k0_free = 2.0 * math.pi / wl
    k0sq = cavity_k0_sq(eps3d, h, k=k)
    if len(k0sq) == 0:
        return float("nan")
    return float(math.sqrt(max(float(k0sq[0]), 0.0)) / k0_free)


def selfcheck_cubic_cavity_golden(n: float = 2.0, L: float = 1.0, N: int = 32,
                                  tol: float = 1e-2,
                                  verbose: bool = False) -> List[tuple]:
    """① 闭式物理律（**强**）：均匀立方腔基模 k0²(1,1,1) = 3(π/L)²/n²。

    立方腔 (mx,my,mz) 模的 k0² = (1/n²)(π/L)²(mx²+my²+mz²)。基模 (1,1,1) 三重
    简并，下一簇 (2,1,1) 族 = 2× 基模。collocated 向量拉普拉斯 O(h²) 收敛，
    N=32 残差 ~6e-3 < tol 1e-2。返回 [(name, got, ex, d, tol, good), ...]。
    """
    h = L / N
    eps = np.full((N, N, N), n ** 2)
    k0sq = cavity_k0_sq(eps, h, k=6)
    gold111 = 3.0 * (math.pi / L) ** 2 / n ** 2
    rows = []
    got111 = float(k0sq[0])
    d111 = got111 - gold111
    rows.append(("cubic[k0²(1,1,1)]", got111, gold111, d111, tol,
                 bool(math.isfinite(d111) and abs(d111) <= tol)))
    # 下一簇 (2,1,1) = 2× 基模（跳过三重简并）
    above = k0sq[k0sq > gold111 * 1.3]
    got211 = float(above[0]) if above.size else float("nan")
    ratio = (got211 / gold111) if math.isfinite(got211) else float("nan")
    d211 = ratio - 2.0
    rows.append(("cubic[ratio 211/111]", ratio, 2.0, d211, tol,
                 bool(math.isfinite(d211) and abs(d211) <= tol)))
    if verbose:
        print(f"  [立方腔·闭式金] k0²(1,1,1)={got111:.6f} 金={gold111:.6f} "
              f"Δ={d111:+.2e}; 下一簇/基模={ratio:.4f} (金=2.0)")
    return rows


def selfcheck_3d_convergence(n: float = 2.0, L: float = 1.0,
                             Ns=(16, 32, 64), verbose: bool = False) -> List[tuple]:
    """② 网格收敛 O(h²)：k0²(1,1,1) 误差随 N 加倍按 ~1/4 收缩 ⇒ 收敛阶 ≈ 2.0。
    断言 1.8 ≤ rate ≤ 2.2（容许少量离散/ARPACK 扰动）。
    """
    gold = 3.0 * (math.pi / L) ** 2 / n ** 2
    rows = []
    errs: List[float] = []
    for N in Ns:
        h = L / N
        eps = np.full((N, N, N), n ** 2)
        e0 = cavity_k0_sq(eps, h, k=1)[0]
        errs.append(abs(e0 - gold))
    prev = None
    rates: List[float] = []
    for i, N in enumerate(Ns):
        if prev is not None:
            rate = math.log(prev / errs[i]) / math.log(2)
            rates.append(rate)
            rows.append((f"conv3d[h={Ns[i - 1]}→{Ns[i]}]", errs[i - 1], errs[i],
                         rate, 0.0,
                         bool(math.isfinite(rate) and 1.8 <= rate <= 2.2)))
        prev = errs[i]
    if verbose and rows:
        print("  [3D 收敛] " + " ".join(f"rate={r:.2f}" for r in rates))
    return rows


def selfcheck_3d_diel_lt_air(n: float = 2.0, L: float = 1.0, N: int = 8,
                             verbose: bool = False) -> tuple:
    """③ 物理必然性：介质加载腔基模谐振 k0² 必 < 同几何空腔（k0²∝1/n²）。
    反例：若算子把 ε 当成了 1/n² 倒数读，会得出 diel>air 的荒谬结论。
    """
    h = L / N
    eps_air = np.full((N, N, N), 1.0)
    eps_diel = np.full((N, N, N), n ** 2)
    k_air = cavity_k0_sq(eps_air, h, k=1)[0]
    k_diel = cavity_k0_sq(eps_diel, h, k=1)[0]
    d = k_air - k_diel  # 须 > 0（air 谐振频率更高）
    if verbose:
        print(f"  [3D 介质<空腔] air k0²={k_air:.4f} diel k0²={k_diel:.4f} "
              f"差={d:.4f} (>0 成立)")
    return k_air, k_diel, d


def selfcheck_3d_shape_sensitivity(n: float = 2.0, L: float = 1.0, N: int = 16,
                                   floor: float = 1e-2,
                                   verbose: bool = False) -> tuple:
    """④ 反向测试（几何真被读取）：把立方腔在 x 方向压扁（Lx→0.5L），
    基模 k0²(1,1,1) 必显著变化（> floor）。若算子把 z/y 维度错当成 1 维，
    或几何被忽略，扁化不会反映到本征值 ⇒ 判据变红（缺陷信号）。
    """
    h = L / N
    eps_cube = np.full((N, N, N), n ** 2)
    Nx = max(int(N / 2), 2)
    eps_flat = np.full((Nx, N, N), n ** 2)
    k_cube = cavity_k0_sq(eps_cube, h, k=1)[0]
    k_flat = cavity_k0_sq(eps_flat, h, k=1)[0]
    d = abs(k_cube - k_flat)
    if verbose:
        print(f"  [3D 形状敏感] 立方 k0²={k_cube:.4f} 扁化 k0²={k_flat:.4f} "
              f"|Δ|={d:.3e} (须>{floor:g})")
    return k_cube, k_flat, d


def run_selfchecks(verbose: bool = True):
    """跑全部自校锚 → (ok, rows)。CI 直接调用本函数。"""
    rows, ok = [], True

    for name, got, ex, d, tl, good in selfcheck_uniform_limit():
        ok &= good
        rows.append((name, got, ex, d, tl, good))

    for name, got, ex, d, tl, good in selfcheck_strip_bounds(verbose=verbose):
        ok &= good
        rows.append((name, got, ex, d, tl, good))

    ng, gold, d = selfcheck_sin_pristine_control(verbose=verbose)
    good = math.isfinite(d) and abs(d) <= 3e-3
    ok &= good
    rows.append(("empirical[SiN 1.2x0.3 TE n_g]", ng, gold, d, 3e-3, good))

    fv, sv_ne, d = selfcheck_low_contrast_vs_semivec(verbose=verbose)
    good = math.isfinite(d) and abs(d) <= 3e-3
    ok &= good
    rows.append(("lowcontrast[fullvec vs semivec SiN]", fv, sv_ne, d, 3e-3, good))

    ne, lock, d = selfcheck_highcontrast_regression(verbose=verbose)
    good = math.isfinite(d) and abs(d) <= 2e-3
    ok &= good
    rows.append(("regression[SOI 600x220 TE0]", ne, lock, d, 2e-3, good))

    for name, got, ex, d, tl, good in selfcheck_grid_convergence(verbose=verbose):
        ok &= good
        rows.append((name, got, ex, d, tl, good))

    # ---- G12-A：任意 2D 截面 ------------------------------------------------
    a, b, d = selfcheck_arbitrary_strip_degeneracy(verbose=verbose)
    good = math.isfinite(d) and abs(d) <= 1e-9
    ok &= good
    rows.append(("arb_degenerate[neff_2d==neff_strip]", a, b, d, 1e-9, good))

    fv2, sv2, d = selfcheck_arbitrary_lowcontrast_vs_semivec(verbose=verbose)
    good = math.isfinite(d) and abs(d) <= 3e-3
    ok &= good
    rows.append(("arb_lowcontrast[fullvec vs semivec SiN]", fv2, sv2, d, 3e-3, good))

    for name, got, ex, d, tl, good in selfcheck_rib_slab_monotonic(verbose=verbose):
        ok &= good
        rows.append((name, got, ex, d, tl, good))

    vf, vn, d = selfcheck_rib_slab_loadbearing(verbose=verbose)
    good = math.isfinite(d) and d > 1e-3
    ok &= good
    rows.append(("rib_slab_load[full vs ridge-only]", vf, vn, d, 1e-3, good))

    fv3, sv3, d3 = selfcheck_rib_vs_semivec_nonzero(verbose=verbose)
    good = math.isfinite(d3) and d3 > 1e-4
    ok &= good
    # 该行语义与其余行**相反**：got/ref 是两法各自的 n_eff，Δ=|两法之差|，
    # 判据是 **Δ > tol（必须不同）** 而非 ≤ tol —— 相同即缺陷信号。
    rows.append(("rib_antistake[fullvec!=semivec]", fv3, sv3, d3, 1e-4, good))

    for name, got, ex, d, tl, good in selfcheck_rib_grid_convergence(verbose=verbose):
        ok &= good
        rows.append((name, got, ex, d, tl, good))

    # ---- G12-B：真 3D 空间全矢量本征模 --------------------------------------
    for name, got, ex, d, tl, good in selfcheck_cubic_cavity_golden(verbose=verbose):
        ok &= good
        rows.append((name, got, ex, d, tl, good))

    for name, got, ex, d, tl, good in selfcheck_3d_convergence(verbose=verbose):
        ok &= good
        rows.append((name, got, ex, d, tl, good))

    ka, kd, d = selfcheck_3d_diel_lt_air(verbose=verbose)
    good = bool(math.isfinite(d) and d > 0.0)
    ok &= good
    rows.append(("diel_lt_air[k0²_diel<k0²_air]", ka, kd, d, 0.0, good))

    kc, kf, d = selfcheck_3d_shape_sensitivity(verbose=verbose)
    good = bool(math.isfinite(d) and d > 1e-2)
    ok &= good
    rows.append(("shape[flatten≠cube]", kc, kf, d, 1e-2, good))

    if verbose:
        print()
        for name, got, ex, d, tl, good in rows:
            print(f"  [{'PASS' if good else 'FAIL'}] {name}  got={got:.6f} "
                  f"ref={ex:.6f} Δ={d:+.2e} tol={tl:g}")
    return ok, rows


if __name__ == "__main__":
    import time
    print("=" * 78)
    print("G12-H 全矢量本征模求解器（H-field staggered + PML）自检")
    t0 = time.time()
    ok, rows = run_selfchecks(verbose=True)
    print(f"\n{'ALL PASS' if ok else 'HAS FAIL'}  "
          f"({sum(1 for r in rows if r[5])}/{len(rows)}, {time.time() - t0:.1f}s)")
