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
from scipy.sparse import bmat, coo_matrix
from scipy.sparse.linalg import eigsh, eigs

__all__ = [
    "H_GRID", "L_HALF_MIN", "HALF_WIN_MULT", "N_PML", "A_PML", "K_EIGS",
    "ModeResult",
    "build_grid", "eps_cells", "coeffs", "build_operator",
    "solve_modes", "neff_strip", "group_index",
    "selfcheck_uniform_limit", "selfcheck_sin_pristine_control",
    "selfcheck_low_contrast_vs_semivec", "selfcheck_highcontrast_regression",
    "selfcheck_grid_convergence", "selfcheck_strip_bounds",
    "run_selfchecks",
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


def solve_modes(w: float, h_core: float, wl: float,
                n_core: float, n_clad: float,
                h_grid: float = H_GRID, L: Optional[float] = None,
                n_pml: int = 0, A_pml: float = 0.0,
                k: int = K_EIGS) -> List[ModeResult]:
    """解条形波导本征模，返回按 n_eff 降序（基模在前）的 ModeResult 列表。

    几何自动 snap 到网格线（半宽取整到 h_grid 整数倍）——避免楼梯误差主导。
    """
    hw = max(int(round(w / 2.0 / h_grid)), 1) * h_grid
    hh = max(int(round(h_core / 2.0 / h_grid)), 1) * h_grid
    w, h_core = 2.0 * hw, 2.0 * hh

    k0 = 2.0 * math.pi / wl
    Lh = _half_win(w, h_core, L)
    xv = build_grid(Lh, h_grid, n_pml, A_pml)
    dx = np.diff(xv)
    xc = 0.5 * (xv[:-1] + xv[1:])
    eps = eps_cells(w, h_core, n_core, n_clad, xc, xc)
    A, nx, ny = build_operator(eps, dx, dx, k0)
    N = nx * ny

    sigma = (k0 * (n_clad + 0.85 * (n_core - n_clad))) ** 2
    try:
        vals, vecs = eigs(A, k=k, sigma=sigma, which="LM")
    except Exception:                                    # noqa: BLE001
        return []

    mx = (np.abs(xv.real) <= w / 2.0 + 1e-12)
    my = (np.abs(xv.real) <= h_core / 2.0 + 1e-12)
    coremask = my[:, None] & mx[None, :]

    out: List[ModeResult] = []
    for m in range(vals.shape[0]):
        v = vals[m]
        if not np.isfinite(v.real) or v.real <= 0:
            continue
        neff = math.sqrt(v.real) / k0
        if not (n_clad + 1e-3 < neff < n_core + 1e-4):
            continue
        hv = vecs[:, m]
        hx2 = np.abs(hv[:N]) ** 2
        hy2 = np.abs(hv[N:]) ** 2
        tot = float((hx2 + hy2).sum())
        if tot <= 0:
            continue
        e2 = (hx2 + hy2).reshape((ny, nx), order="C")
        conf = float(e2[coremask].sum() / tot)
        imax = np.unravel_index(int(np.argmax(e2)), e2.shape)
        peak = bool(abs(xv.real[imax[0]]) <= h_core / 2.0 and
                    abs(xv.real[imax[1]]) <= w / 2.0)
        hy_core = float(hy2.reshape((ny, nx), order="C")[coremask].sum() /
                        max(float((hy2.reshape((ny, nx), order="C")[coremask] +
                                   hx2.reshape((ny, nx), order="C")[coremask]).sum()), 1e-300))
        out.append(ModeResult(neff=neff, conf_core=conf, peak_in_core=peak,
                              im_beta2=float(v.imag), frac_hy_core=hy_core,
                              hx=hv[:N].reshape((ny, nx), order="C"),
                              hy=hv[N:].reshape((ny, nx), order="C")))
    # 只保留受限良好、峰在芯内的模；
    # 排序按 n_eff 降序（基模在前）——conf 排序会被 PML 伪模污染
    good = [r for r in out if r.conf_core > 0.30 and r.peak_in_core]
    good.sort(key=lambda r: -r.neff)
    return good


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
