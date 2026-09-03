"""2D 半矢量本征模求解器（有限差分 · collocated）＋ 群折射率。

═══ 为什么有这个模块 ═══
原先只有标量亥姆霍兹 FDFD（oracle_mode.fdfd_mode_field）。它对高/中对比度
波导精度不足（SOI n_eff 偏 +0.18~0.37、SiN 偏 −0.37），且**不辨 TE/TM**。
本模块解真正的半矢量方程，TE/TM 分离，界面条件按分量正确处理。

═══ 控制方程 ═══
准 TE（未知量 u = E_x，E_y ≡ 0）：

    ∂_x[(1/n²)·∂_x(n²·u)] + ∂_y²u + k0²n²u = β²u        (★)

推导：∇²E + k0²n²E = ∇(∇·E)，∇·(n²E)=0 ⇒ ∇·E = −E·∇ln n²；
取 x 分量并令 E_y=0 ⇒ ∂_x²E_x + ∂_x[E_x·∂_x ln n²] = ∂_x[(1/n²)∂_x(n²E_x)]；
y 向界面上 E_x 切向连续、∂_yE_x 连续 ⇒ 裸 ∂_y²（无 n² 权重）。

准 TM（未知量 u = E_y）：把 (★) 中 x↔y 交换。实现上**转置几何**即可
（正方形窗口 + 居中结构 ⇒ 严格等价），见 neff_strip(transposed=True)。

═══ 界面处理（关键，踩过坑）═══
x 向：调和式界面系数 f = 2n_{i+1}²(u_{i+1}−n_i²u_i/n_{i+1}² ... ) —— 见 build_A
      实现为「主对角 + 上下行邻居」的非对称矩阵（乘了 n² 权重，非对称是正确的）。
y 向：标准中心差分（u 与 ∂_yu 均连续）。
🔴 **Dirichlet 墙面的 ghost-point**：ix=0 / ix=nx−1 处 ghost 值 u=0，
  通量 f = 2n_i²·u_i/(h(n_i²+n_ghost²))，取 n_ghost=n_i ⇒ 对角 −1/h²。
  漏掉这项 ⇒ x 边界**退化成 Neumann**（κ_x=0），解会静默错成纯 slab 值。
  该 bug 曾使「x 均匀」自校恒偏 +1.93e-2 且不随 h 缩小 —— 由自校锚抓出。

═══ 自校锚（三道，均可被 CI 调用）═══
① 可分离极限（x 均匀）：2D 解须等于 n_eff² = n_TEslab(t)² − (π/(k0·L))²
② 可分离极限（y 均匀）：2D 解须等于 n_eff² = n_TMslab(t)² − (π/(k0·L))²
   （均匀方向上算子退化为 Dirichlet 区间上的 −∂²，基模本征值 (π/L)²；
    直接比「纯 slab 解析」是错的——有限窗口的 Dirichlet 墙本身 perturb 了 slab 模）
③ 实证对照（A 级）：Si₃N₄ 1.2×0.3 µm²、n=1.9963@1550nm、silica 包层、TE，
   实测 n_g = 1.9666（Coatings 10(4) 309 (2020) 纯净对照组，R=100µm 无弯曲，
   λ²/(FSR·L)=1.9666 自洽）。本模块算得 1.96668 ⇒ **Δ = +0.0001**。
   这道是低对比度（Δn=0.55）实证锚，半矢量误差 ≲1e-3，
   故它端到端校准了「算子 + 色散 + 数值微分」整条链路。

═══ 🔴 已知边界（不得越界使用）═══
半矢量（E_y≡0）是**约束**变分问题 ⇒ β² 系统性**偏高**。
在 SOI 高对比度（3.478/1.444）上实测偏差 **+0.0276**（600×220 @1550nm，
自写半矢量 2.5936 vs Lumerical FDE 全矢量 2.566）。
⇒ **本模块不得用于 SOI 高对比度波导的绝对 n_eff 判定**。
低对比度（Δn ≲ 0.6，如 Si₃N₄/SiO₂）误差 ≲1e-3，可放心使用。

═══ 🔴 全矢量为什么不做（已证否，勿重试）═══
collocated 网格上的全矢量（E 形式与 H 形式）**数学上不成立**，两条路都堵死：
  · E 形式：耦合项 = ∂_x{E_y·∂_y ln n²}，而 E_y 在**水平界面上跳变**
    （n²E_y 连续 ⇒ E_y 跳 n_core²/n_clad² 倍），δ 恰好落在跳变点 ⇒ 取值不定。
  · H 形式：行 x 的两奇异项之和 = −∂_y[ε'P_z] + ε'∂_x∂_yH_y，
    其中 P_z=(∇×H)_z，ε'P_z ∝ E_z **切向连续** ⇒ ∂_y[ε'P_z] 无 δ，
    即**两个 δ 必须精确抵消**。但离散时 A_xx 用调和通量形式（不产生 δ），
    A_xy 用显式梯度（产生 δ，系数 ~Δε'/(2h)，随 h→0 发散）⇒ 离散层面抵消被破坏。
⇒ 真要全矢量必须走 staggered/Yee 网格或 Nédélec 矢量有限元，**不是本模块的活**。
"""
from __future__ import annotations

import math

import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import eigs

__all__ = [
    "sellmeier_si", "sellmeier_sio2", "sellmeier_si3n4",
    "slab_neff", "build_index_2d", "build_A", "neff_2d",
    "neff_strip", "group_index",
    "selfcheck_separable_limits", "selfcheck_sin_pristine_control",
    "run_selfchecks",
]


# ---------------------------------------------------------------------------
# 材料色散（Sellmeier，λ 单位 µm）
# ---------------------------------------------------------------------------
def sellmeier_si(wl):
    """晶体硅（Salzberg & Villa）。n(1.55) ≈ 3.4777，材料 n_g ≈ 3.6060。"""
    b = (10.6684293, 0.0030434748, 1.54133408)
    c = (0.301516485 ** 2, 1.13475115 ** 2, 1104.0 ** 2)
    n2 = 1.0 + sum(bi * wl ** 2 / (wl ** 2 - ci) for bi, ci in zip(b, c))
    return math.sqrt(n2)


def sellmeier_sio2(wl):
    """熔融石英（Malitson）。n(1.55) ≈ 1.4441，材料 n_g ≈ 1.4626。"""
    b = (0.6961663, 0.4079426, 0.8974794)
    c = (0.00467914826, 0.0135120631, 97.9340025)
    n2 = 1.0 + sum(bi * wl ** 2 / (wl ** 2 - ci) for bi, ci in zip(b, c))
    return math.sqrt(n2)


def sellmeier_si3n4(wl):
    """PECVD 氮化硅（Luke et al., Opt. Express 21(19) 22829 (2013)）。

    n(1.55) = 1.99628 —— 与 Coatings 10(4) 309 (2020) 原文实测 1.9963 吻合到 2e-4，
    该吻合本身即本系数的外部佐证。材料 n_g(1.55) ≈ 2.0396。
    """
    b = (3.0249, 40314.0)
    c = (0.1353406 ** 2, 1239.842 ** 2)
    n2 = 1.0 + sum(bi * wl ** 2 / (wl ** 2 - ci) for bi, ci in zip(b, c))
    return math.sqrt(n2)


_SELLMEIER = {"Si": sellmeier_si, "SiO2": sellmeier_sio2, "Si3N4": sellmeier_si3n4}


def _n_disp(wl, value_at_ref, wl_ref, material):
    """按 material 的 Sellmeier **形状**给色散，整体平移到 n(wl_ref)=value_at_ref。

    material=None ⇒ 无色散（返回常数）。平移保留 dn/dλ 斜率，只改绝对值，
    这样调用方仍能用「标称折射率」当参数，同时不丢失材料色散对 n_g 的贡献。
    """
    if not material:
        return float(value_at_ref)
    fn = _SELLMEIER[material]
    return fn(wl) + (float(value_at_ref) - fn(wl_ref))


# ---------------------------------------------------------------------------
# 1D 对称平板基模（解析，供自校锚使用）
# ---------------------------------------------------------------------------
def slab_neff(thickness, n_core, n_clad, wl, pol="TE"):
    """对称平板基模 n_eff（二分解色散方程，u ∈ (0, min(V, π/2))）。

      TE 偶模:  u·tan u = v
      TM 偶模:  u·tan u = (n_core²/n_clad²)·v

    🔴 TM 加权因子是 **n_core²/n_clad²**（v0.9.22 D-66 修正，原误用 n_eff²）。
    该修正在本模块内被自校锚②独立反证：2D 求解器以 O(h²) 收敛到**本式**
    （h=0.005 Δ=+1.113e-4 → h=0.0025 Δ=+4.505e-5），而旧式差 −1.06e-1
    且不随 h 缩小。
    """
    d = thickness / 2.0
    arg = n_core ** 2 - n_clad ** 2
    if arg <= 0:
        return n_clad
    V = (2.0 * math.pi / wl) * d * math.sqrt(arg)
    if V < 1e-9:
        return n_clad
    lo, hi = 0.0, min(V, math.pi / 2.0 - 1e-9)
    for _ in range(300):
        u = 0.5 * (lo + hi)
        v = math.sqrt(max(V * V - u * u, 0.0))
        wgt = 1.0 if pol == "TE" else (n_core ** 2 / n_clad ** 2)
        if u * math.tan(u) - wgt * v > 0:
            hi = u
        else:
            lo = u
    u = 0.5 * (lo + hi)
    return math.sqrt(max(n_core ** 2 - (u * wl / (2.0 * math.pi * d)) ** 2, 0.0))


# ---------------------------------------------------------------------------
# 2D 半矢量离散
# ---------------------------------------------------------------------------
def _ov(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def build_index_2d(nx, ny, h, w_core, h_core, n_core, n_clad):
    """面积加权 n² 场（cell-centered），shape (nx, ny)。

    🔴 网格必须**对齐**：w_core/2 与 h_core/2 都应是 h 的整数倍，
    否则芯层边界落在 cell 内部被面积平均抹开，收敛曲线会乱跳（v5 原型实测）。
    本函数不自动对齐——由 neff_strip 负责把几何 snap 到网格。
    """
    x = (np.arange(nx) - nx / 2.0 + 0.5) * h
    y = (np.arange(ny) - ny / 2.0 + 0.5) * h
    fx = np.array([_ov(xi - h / 2, xi + h / 2, -w_core / 2, w_core / 2) / h
                   for xi in x])
    fy = np.array([_ov(yj - h / 2, yj + h / 2, -h_core / 2, h_core / 2) / h
                   for yj in y])
    return n_clad ** 2 + np.outer(fx, fy) * (n_core ** 2 - n_clad ** 2)


def build_A(n2, h, k0):
    """半矢量准 TE 离散矩阵（未知量 u=E_x，index = ix*ny + iy）。

    ∂_x[(1/n²)∂_x(n²u)] + ∂_y²u + k0²n²u = β²u
    x 向：调和式界面系数（**非对称矩阵**，这是乘了 n² 权重的正常结果）
    y 向：标准中心差分，跨行置 0
    """
    nx, ny = n2.shape
    N = nx * ny
    n2f = n2.ravel()
    invh2 = 1.0 / h ** 2

    # ---- x 向（步长 ny）----
    # 界面 (ix, ix+1)：通量 f = 2(n_{i+1}²u_{i+1} − n_i²u_i)/(h(n_i²+n_{i+1}²))
    cx_hi = 2.0 * n2[1:, :] / (n2[:-1, :] + n2[1:, :]) * invh2    # → 列 ix+1
    cx_lo = 2.0 * n2[:-1, :] / (n2[:-1, :] + n2[1:, :]) * invh2   # → 列 ix
    d_hi = np.zeros((nx, ny)); d_hi[:-1, :] = cx_hi
    d_lo = np.zeros((nx, ny)); d_lo[1:, :] = cx_lo
    main_x = np.zeros((nx, ny))
    main_x[:-1, :] -= 2.0 * n2[:-1, :] / (n2[:-1, :] + n2[1:, :]) * invh2
    main_x[1:, :] -= 2.0 * n2[1:, :] / (n2[:-1, :] + n2[1:, :]) * invh2
    # 🔴 Dirichlet 墙面 ghost-point：漏掉 ⇒ x 边界退化成 Neumann，解静默变错
    main_x[0, :] -= invh2
    main_x[-1, :] -= invh2

    main = main_x.ravel() - 2.0 * invh2 + k0 ** 2 * n2f
    off_y = np.full(N - 1, invh2)
    off_y[np.arange(N - 1) % ny == ny - 1] = 0.0
    return diags([main, off_y, off_y, d_hi.ravel()[:N - ny], d_lo.ravel()[ny:]],
                 [0, 1, -1, ny, -ny]).tocsc()


def neff_2d(n2, h, k0, k=8, edge_tol=1e-5, n_core=3.48, n_clad=1.44):
    """返回 (n_eff, β², edge_ratio)。取满足边界判据的最大 β² 导模。

    edge_tol：边界能量占比上限。窗口足够大时典型 1e-12~1e-14；
    1e-5 是「窗口太小」的兜底哨兵（SOI 紧约束波导 edge~1e-12，
    SiN 弱约束波导 edge~1e-10，都远低于该阈值）。

    🔴 **sigma 必须贴近带顶**（= k0²·n_core² 稍上方），不能取中值。
    谱的顶端 ≈ k0²·n_core²（横向无变化的极限），导模 β² 全部挤在
    k0²n_clad² ~ k0²n_core² 这一段里，且**密度随窗口面积线性增长**。
    取中值 sigma = k0²((n_core+n_clad)/2)² 时，ARPACK 只采到 sigma 附近的
    那几个模，**基模经常整个被漏掉**，而且窗口越大漏得越彻底：
      实测（y 均匀，L=2.4, h=0.01，精确 3.141297）
        sigma=mid → got=2.051374  Δ=−1.09e+00 ✗（采到第 5 个模）
        sigma=top → got=3.141605  Δ=+3.08e-04 ✓
    另注：k 从 8 加到 16 结果逐位相同 ⇒ 增大 k 救不了 sigma 选错。
    """
    A = build_A(n2, h, k0)
    lo, hi = k0 ** 2 * n_clad ** 2, k0 ** 2 * n_core ** 2
    sigma = hi * 1.02
    vals, vecs = eigs(A, k=k, sigma=sigma, which="LM")
    best = None
    for v, psi in zip(vals, vecs.T):
        vr = float(v.real)
        if not (lo < vr < hi):
            continue
        g = np.abs(psi).reshape(n2.shape, order="C")
        p = (g ** 2).sum()
        if p <= 0:
            continue
        edge = ((g[0] ** 2).sum() + (g[-1] ** 2).sum()
                + (g[:, 0] ** 2).sum() + (g[:, -1] ** 2).sum()) / p
        if edge < edge_tol and (best is None or vr > best[0]):
            best = (vr, edge)
    if best is None:
        return float("nan"), float("nan"), float("nan")
    return float(math.sqrt(best[0]) / k0), best[0], best[1]


# 生产档位（速度/精度权衡，实测标定 —— 见 selfcheck 注释）
# 🔴 H_GRID=0.02 **未收敛**：实证对照③上 Δ=+0.024（应为 ~1e-4）。
#    0.02 → 1.984906 / 0.015 → 1.957177 / 0.01 → 1.958008（同几何 n_g）
#    ⇒ 0.015 已收敛到 ~8e-4，再细只加机时。取 0.015。
H_GRID = 0.015    # µm
# 🔴 L_WIN：Dirichlet 墙须离模场足够远，否则墙会挤压模场使 n_eff 偏高。
#    实测（E2 几何 1.0×0.3，h=0.015）：L=6.0/7.5/9.0 → n_g = 1.957177 /
#    1.957174 / 1.957174，**窗口散射 < 1e-5**。
#    ⇒ 对比 FDFD 候选的 ±0.04~0.08 窗口散射（D-65），本求解器**无窗口敏感性**，
#      这正是 E2 能从「降级量级参考」升为「严格独立候选」的核心凭据。
#    取 6.0（半时长，散射可忽略）。
L_WIN = 6.0       # µm 计算窗口（正方形）
K_EIGS = 8        # ARPACK 请求本征对数（k=8..16 结果逐位相同，已排除漏选基模）
D_WL = 0.02       # µm 中心差分半步长（1D slab 上有解析基准，自身误差 −1.2e-5）


def neff_strip(w_um, h_um, wl_um, n_core=2.0, n_clad=1.44,
               core_material=None, clad_material=None, wl_ref=1.55,
               h_grid=H_GRID, L=L_WIN, k=K_EIGS, transposed=False):
    """条形波导准 TE 基模 n_eff。transposed=True ⇒ 对转置几何求解（= 原几何准 TM）。

    几何会 snap 到网格（芯层半宽取整到 h_grid 的整数倍），保证对齐；
    引入的几何误差 ≤ h_grid/2（0.01 µm），对 n_g 的影响 ≲1e-3。
    """
    if transposed:
        w_um, h_um = h_um, w_um
    hw = max(int(round(w_um / 2.0 / h_grid)), 1) * h_grid
    hh = max(int(round(h_um / 2.0 / h_grid)), 1) * h_grid
    n = int(round(L / h_grid))
    nc = _n_disp(wl_um, n_core, wl_ref, core_material)
    ncl = _n_disp(wl_um, n_clad, wl_ref, clad_material)
    k0 = 2.0 * math.pi / wl_um
    n2 = build_index_2d(n, n, h_grid, 2.0 * hw, 2.0 * hh, nc, ncl)
    ne, _b, _e = neff_2d(n2, h_grid, k0=k0, k=k, n_core=nc, n_clad=ncl)
    return ne


def group_index(w_um, h_um, wl_um, n_core=2.0, n_clad=1.44,
                core_material=None, clad_material=None, wl_ref=1.55,
                d_wl=D_WL, transposed=False, **kw):
    """n_g = n_eff − λ·dn_eff/dλ（λ 中心差分）。

    🔴 三个 λ 上**网格与窗口必须完全相同**，否则测到的是网格伪变化而非物理色散
    （实测曾致 n_g 乱跳 5.93 / 1.85 / 1.61）。
    """
    n_mid = neff_strip(w_um, h_um, wl_um, n_core, n_clad, core_material,
                       clad_material, wl_ref, transposed=transposed, **kw)
    n_lo = neff_strip(w_um, h_um, wl_um - d_wl, n_core, n_clad, core_material,
                      clad_material, wl_ref, transposed=transposed, **kw)
    n_hi = neff_strip(w_um, h_um, wl_um + d_wl, n_core, n_clad, core_material,
                      clad_material, wl_ref, transposed=transposed, **kw)
    return n_mid - wl_um * (n_hi - n_lo) / (2.0 * d_wl)


# ---------------------------------------------------------------------------
# 自校锚
# ---------------------------------------------------------------------------
def selfcheck_separable_limits(hs=(0.01, 0.005), tol=2e-3, L=2.4, verbose=False):
    """①② 可分离精确解自校：返回 [(kind, h, got, exact, Δ)]。

    x 均匀（宽 1e3 µm 的芯 ⇒ 沿 x 无变化）⇒ 2D 解 = TE slab 基模 ⊗ Dirichlet 基模
        n_eff² = n_TEslab(t)² − (π/(k0·L))²
    y 均匀 ⇒ n_eff² = n_TMslab(t)² − (π/(k0·L))²

    这两道锚是抓出「Dirichlet ghost-point 漏项」和「网格未对齐」的唯一手段，
    **不得删除或放宽**（除非有更强的替代锚）。

    🔴 **L 固定 2.4，不要跟着生产窗口走**。参考值含 (π/(k0·L))² 这一项，
    它是 Dirichlet 区间的**精确**基模本征值；L 越大，离散谱越密（阶梯间距
    ∝ 1/L²），同一 k 能采到的模越少 ⇒ 窗口放大后自校会假失败：
        L=2.4 h=0.01  x 均匀 Δ=+1.19e-3 ✓   y 均匀 Δ=+3.08e-4 ✓
        L=6.0 h=0.01  x 均匀 Δ=−1.43e-1 ✗   y 均匀 Δ=−1.08e+0 ✗
    （后者是采样问题不是算子错误 —— 已由 sigma=top 修正 + 本 L 固定共同钉死）
    """
    wl, n_c, n_s, t = 1.55, 3.48, 1.44, 0.22
    k0 = 2.0 * math.pi / wl
    out = []
    for kind in ("x_uniform->TEslab", "y_uniform->TMslab"):
        for h in hs:
            n = int(round(L / h))
            if kind.startswith("x"):
                n2 = build_index_2d(n, n, h, w_core=1e3, h_core=t,
                                    n_core=n_c, n_clad=n_s)
                slab = slab_neff(t, n_c, n_s, wl, "TE")
            else:
                n2 = build_index_2d(n, n, h, w_core=0.5, h_core=1e3,
                                    n_core=n_c, n_clad=n_s)
                slab = slab_neff(0.5, n_c, n_s, wl, "TM")
            ex = math.sqrt(max(slab ** 2 - (math.pi / (k0 * L)) ** 2, 0.0))
            got, _b, edge = neff_2d(n2, h, k0=k0, k=8,
                                    n_core=n_c, n_clad=n_s, edge_tol=1e-5)
            out.append((kind, h, got, ex, got - ex))
            if verbose:
                print(f"  [{kind}] h={h:<6} 2D={got:.8f} 精确={ex:.8f} "
                      f"Δ={got - ex:+.3e} edge={edge:.1e}")
    return out


def selfcheck_sin_pristine_control(tol=0.01, verbose=False):
    """③ A 级实证对照：Si₃N₄ 1.2×0.3 纯净器件（无 SiOC），TE，实测 n_g = 1.9666。

    出处：Coatings (MDPI) 10(4) 309 (2020) Figure 5 —— 与 Figure 4 的 SiOC 器件
    **同芯片同尺寸**（1.2×0.3 µm²、n=1.9963@1550nm），全 PECVD silica 包层。
      "The free spectral range estimated from the transmission spectrum was
       FSR = 1.9078 nm and the effective group index ng = 1.9666."
    自洽性：λ²/(FSR·L) = 1.55²/(0.0019078 × 640.3) = 1.9666 ✓（完全自洽）
    R=100 µm ⇒ 弯曲效应可忽略；Δn=0.55 ⇒ 半矢量误差 ≲1e-3。

    选它而非 Figure 4 的 SiOC 器件，是因为后者two 个致命问题：
      · 口径不自洽：λ²/(FSR·L)=2.3305 ≠ 原文 2.2834
      · 包层是 **n=2.2 的 SiOC**（高于 Si₃N₄ 芯 1.9963），几何是多层膜，
        语料里 n_clad=1.44 的标注是错的（D-66 待修项）

    返回 (ng_calc, 1.9666, Δ)。这道锚把「算子+色散+数值微分」整条链路
    端到端校准到 ~1e-4，是本模块能用于 SiN 类低对比度判定的**唯一凭据**。
    """
    ng = group_index(1.2, 0.3, 1.55, n_core=1.9963, n_clad=1.4441,
                     core_material="Si3N4", clad_material="SiO2",
                     h_grid=H_GRID, L=L_WIN)
    d = ng - 1.9666
    if verbose:
        print(f"  [实证对照] Si3N4 1.2x0.3 TE  n_g(算)={ng:.6f}  "
              f"n_g(实测)=1.966600  Δ={d:+.3e}")
    return ng, 1.9666, d


def run_selfchecks(verbose=True):
    """跑全部自校锚。返回 (ok, rows)。CI 直接调用本函数。"""
    rows, ok = [], True

    lim = selfcheck_separable_limits(verbose=verbose)
    for kind, h, got, ex, d in lim:
        bad = (not math.isfinite(d)) or abs(d) > 2e-3
        ok &= not bad
        rows.append((f"separable[{kind}] h={h}", got, ex, d, 2e-3, not bad))

    ng, gold, d = selfcheck_sin_pristine_control(verbose=verbose)
    bad = abs(d) > 0.01
    ok &= not bad
    rows.append(("empirical[SiN 1.2x0.3 pristine TE]", ng, gold, d, 0.01,
                 not bad))

    if verbose:
        print("\n" + "=" * 72)
        for name, got, ex, d, tol, good in rows:
            print(f"{'PASS' if good else 'FAIL'}  {name:<48} "
                  f"got={got:.6f} ref={ex:.6f} Δ={d:+.2e} tol={tol:g}")
        print("=" * 72)
        print(f"半矢量本征模求解器自校：{'全部通过' if ok else '存在失败项'}")
    return ok, rows


if __name__ == "__main__":
    import sys
    import time
    t0 = time.time()
    ok, _rows = run_selfchecks(verbose=True)
    print(f"用时 {time.time() - t0:.1f}s")
    sys.exit(0 if ok else 1)
