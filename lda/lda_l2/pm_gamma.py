# -*- coding: utf-8 -*-
"""LDA 光子存储征程 · **Γ（模场-材料重叠因子）场求解标定** —— PM-G2 结算（v0.9.198）。

定位
----
M0 起 `Γ` 一直是**纯假设参数**（`pm_m0.GAMMA_DEFAULT = 0.05`）⇒ 缺口 **PM-G2**
（「模场重叠因子 Γ 的 FDTD 标定」）。单元绝对相移/长度结论对 Γ **线性敏感**
（`Γ 0.01→0.2 ⇒ L_π 29.8→1.5 µm`），所以不标定就没有绝对数。

本模块把 Γ 从「假设」升级为「**自研电磁场求解标定值 + 方法学区间**」。

🔴 口径声明（红线）
-------------------
- 这里得到的是**计算值**（`claim_kind = "simulation"`）⇒ **⛔ 永不作 golden**。
  它只作「设计取值依据 + 区间」，进不了任何 golden 判定路径。
- 全链**纯 numpy/scipy**（C 级自主）· 不 import Meep/Tidy3D/任何商业 EDA。
- Γ 的物理定义（与 PhotoniX 2022 器件口径同源）：
      Γ = ∫_PCM |E|² dA / ∫_all |E|² dA
  即「模场能量落在 PCM 区域的占比」。微扰关系 `Δn_eff = Γ·Δn_bulk` 是同一量的
  另一种测量（特征值差分），两者互为独立判据。

方法学（本模块的全部价值在于**三条独立路径互证**）
--------------------------------------------------
| 路径 | 工具 | 离散 | 数学量 |
|---|---|---|---|
| ① 场法 | `lda_solver.semivec_mode_solver.build_A`（半矢量 collocated） | 5 点 | ∫\\|E_x\\|² 面积分 |
| ② 微扰法 | 同一求解器，两次本征值 | 5 点 | Δn_eff/Δn_bulk |
| ③ 全矢量场法 | `lda_solver.full_vector_mode_solver`（staggered Yee，**独立离散**） | 交错 | ∫\\|H\\|² 面积分 |
| ④ 1D 平板 | 本模块自实现（**独立维度**，无限宽极限） | 3 对角 | ∫\\|E_y\\|² 线积分 |

①/② 共享同一求解器（同源），③/④ 是**真正独立**的代码路径 ⇒ ③ 与 ① 的一致性是
「换一套离散、值不变」的强证据（实测差 ~2%）。

公开文献口径对照（**只作对照，不作 golden**）
-------------------------------------------
PhotoniX 3:18 (2022) doi:10.1186/s43074-022-00070-4 的 Sb₂Se₃-on-SiN 器件给出
Δn_eff≈0.071 与 L_π=11 µm ⇒ 隐含模式重叠 `Γ_implied = Δn_eff/Δn_bulk ≈ 0.092`
（`Δn_bulk` 取 Delaney 2020 AFM doi:10.1002/adfm.202002447 的 0.77）。LDA 自研标定
与它**同量级**（不追求逐位一致 —— 几何/材料不同，只作交叉参照）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from lda_l2 import pm_matlib as ML

WL_NM_DEFAULT: float = 1550.0

#: 🔴 计算值性质标注（永不作 golden）—— 供下游与门禁机器读取。
GAMMA_CLAIM_KIND: str = "simulation"

#: LDA 基准几何（**设计参数**，非实测）：SiN 条波导 + Sb₂Se₃ 顶部覆盖层。
GAMMA_GEOMETRY: Dict[str, Any] = {
    "waveguide": "SiN strip（条波导）",
    "core_material": "SiN", "clad_material": "SiO2", "pcm_material": "Sb2Se3",
    "w_um": 1.0, "h_um": 0.4, "t_pcm_um": 0.04,
    "n_core": 2.00, "n_clad": 1.44,
    "provenance": "几何为**设计参数**（非实测/非文献器件复制）；n_core/n_clad 取 SiN/SiO2 @1550nm 常规值；"
                  "n_pcm 由 `pm_matlib.nk()` 现算（非晶态多源均值）。",
}

#: 网格档位（🔴 所有尺寸必须落在整数格点上 —— 否则薄层被面积平均抹开、收敛曲线乱跳）。
GRID_FAST: Dict[str, float] = {"h_um": 0.02, "L_um": 3.0}    # 门禁/状态判定档
GRID_FINE: Dict[str, float] = {"h_um": 0.01, "L_um": 4.0}    # 收敛证据档

#: 文献器件口径（对照，非判据）：PhotoniX 2022 器件隐含模式重叠。
LIT_IMPLIED_GAMMA: float = 0.0922
LIT_IMPLIED_SOURCE: str = ("PhotoniX 3:18 (2022) doi:10.1186/s43074-022-00070-4 "
                           "Δn_eff≈0.071 / Δn_bulk=0.77（Delaney 2020 AFM）")

GAMMA_DISCLOSURE: Dict[str, Any] = {
    "claim_kind": GAMMA_CLAIM_KIND,
    "never_golden": True,
    "no_meep_no_tidy3d": True,
    "no_fabricated_efficiency": True,
    "note": "Γ 为**自研场求解计算值** ⇒ 只作设计取值依据 + 区间；⛔ 不进 golden 判定路径。",
}


class PMGammaError(Exception):
    """Γ 标定错误。"""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise PMGammaError(msg)


# ---------------------------------------------------------------------------
# 1. 材料参数（**现算**，不写字面量）
# ---------------------------------------------------------------------------
def design_n_pcm(wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """PCM 覆盖层折射率：由 `pm_matlib.nk()` 现算（非晶态多源均值 + 区间）。"""
    r = ML.nk("Sb2Se3", "amorphous", wl_nm)
    ns = [p["n"] for p in r["per_source"]]
    return {"n_mean": float(sum(ns) / len(ns)), "n_min": r["n_min"], "n_max": r["n_max"],
            "n_sources": r["n_sources"], "wl_nm": float(wl_nm),
            "source": "pm_matlib.OPTICAL_ANCHORS['Sb2Se3'].amorphous（现算均值）"}


# ---------------------------------------------------------------------------
# 2. 几何 → 网格（对齐断言：丑失败优于假结果）
# ---------------------------------------------------------------------------
def _check_aligned(h_um: float, *sizes: float) -> None:
    for s in sizes:
        ratio = s / h_um
        _require(abs(ratio - round(ratio)) < 1e-9,
                 f"尺寸 {s} µm 不是网格 {h_um} µm 的整数倍（薄层会被面积平均抹开 ⇒ 结果不可信）")


def _build_index(w_um: float, h_um: float, t_pcm_um: float, n_core: float,
                 n_clad: float, n_pcm: float, has_pcm: bool,
                 w_pcm_um: Optional[float] = None, h_grid: float = 0.02,
                 L_win: float = 3.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """构造 n² 剖面（**cell-centered**，shape (nx=横向, ny=垂直)，与半矢量索引一致）。

    has_pcm=False ⇒ PCM 区域替换为包层（供微扰法做「无 PCM」参考解）。
    """
    if w_pcm_um is None:
        w_pcm_um = w_um
    nx = int(round(L_win / h_grid))
    ny = nx
    xc = (np.arange(nx) - nx / 2.0 + 0.5) * h_grid
    yc = (np.arange(ny) - ny / 2.0 + 0.5) * h_grid
    n2 = np.full((nx, ny), n_clad ** 2, dtype=float)
    core = np.ix_(np.abs(xc) <= w_um / 2.0 + 1e-12, np.abs(yc) <= h_um / 2.0 + 1e-12)
    n2[core] = n_core ** 2
    if has_pcm:
        pcm = np.ix_(np.abs(xc) <= w_pcm_um / 2.0 + 1e-12,
                     (yc > h_um / 2.0 - 1e-12) & (yc <= h_um / 2.0 + t_pcm_um + 1e-12))
        n2[pcm] = n_pcm ** 2
    return n2, xc, yc


def _pcm_mask(xc: np.ndarray, yc: np.ndarray, h_um: float, t_pcm_um: float,
              w_pcm_um: float) -> np.ndarray:
    return np.ix_(np.abs(xc) <= w_pcm_um / 2.0,
                  (yc > h_um / 2.0) & (yc <= h_um / 2.0 + t_pcm_um))


# ---------------------------------------------------------------------------
# 3. 求解器入口（局部 import：避免加载序耦合 + 让 pm_m0 只在使用时才付代价）
# ---------------------------------------------------------------------------
def _solve_semivec(n2: np.ndarray, h_grid: float, k0: float, k: int = 4) -> Tuple[float, np.ndarray]:
    """半矢量本征模 → (n_eff, |psi|² 网格 (nx, ny))。固定起始向量 ⇒ 确定性。"""
    from scipy.sparse.linalg import eigs

    from lda_solver.semivec_mode_solver import build_A
    A = build_A(n2, h_grid, k0)
    N = n2.size
    _require(N > k + 2, "网格过小")
    sigma = k0 ** 2 * float(n2.max()) * 1.02
    vals, vecs = eigs(A, k=k, sigma=sigma, which="LM", v0=np.ones(N))
    lo, hi = k0 ** 2 * float(n2.min()) * 0.9, k0 ** 2 * float(n2.max()) * 1.1
    best = None
    for v, psi in zip(vals, vecs.T):
        vr = float(v.real)
        if not (lo < vr < hi):
            continue
        if best is None or vr > best[0]:
            best = (vr, psi)
    _require(best is not None, "半矢量未找到受限模")
    psi2 = np.abs(best[1]) ** 2
    return math.sqrt(best[0]) / k0, psi2.reshape(n2.shape, order="C")


def _solve_fullvec(n2: np.ndarray, h_grid: float, k0: float, w_um: float,
                   h_um: float, k: int = 6) -> Tuple[float, np.ndarray]:
    """全矢量（staggered Yee，**独立离散**）→ (n_eff, |H|² 网格 (ny, nx))。

    ⚠ 顶点网格（形状比 cell 数大 1）· eps 约定 shape (ny, nx)（与半矢量转置）。
    """
    from lda_solver.full_vector_mode_solver import solve_modes_eps
    eps = n2.T.copy()                      # (ny, nx)
    nyc, nxc = eps.shape
    xv = (np.arange(nxc + 1) - nxc / 2.0) * h_grid          # 横向（宽度）
    yv = (np.arange(nyc + 1) - nyc / 2.0) * h_grid          # 垂直
    mx = np.abs(xv) <= w_um / 2.0 + 1e-12
    my = np.abs(yv) <= h_um / 2.0 + 1e-12
    core_vmask = my[:, None] & mx[None, :]                  # 🔴 必须显式传：PCM 的 n 比芯高
    n_hi = math.sqrt(float(eps.max()))
    rs = solve_modes_eps(eps, xv, yv, k0, k=k, n_lo=math.sqrt(float(eps.min())),
                         n_hi=n_hi, core_vmask=core_vmask, conf_min=0.2)
    _require(bool(rs), "全矢量未找到合格模")
    m = rs[0]
    return m.neff, (np.abs(m.hx) ** 2 + np.abs(m.hy) ** 2), (xv, yv)


def _solve_slab(n: np.ndarray, h_grid: float, k0: float) -> Tuple[float, np.ndarray]:
    """1D 垂直平板本征模（**独立维度**：无限宽极限）→ (n_eff, |E_y|²)。"""
    from scipy.sparse import diags
    from scipy.sparse.linalg import eigs
    nx = n.size
    invh2 = 1.0 / h_grid ** 2
    main = -2.0 * invh2 + k0 ** 2 * n ** 2
    off = np.full(nx - 1, invh2)
    A = diags([main, off, off], [0, 1, -1]).tocsc()
    sigma = k0 ** 2 * float(np.max(n ** 2)) * 1.02
    vals, vecs = eigs(A, k=4, sigma=sigma, which="LM", v0=np.ones(nx))
    lo, hi = k0 ** 2 * float(np.min(n ** 2)) * 0.9, k0 ** 2 * float(np.max(n ** 2)) * 1.1
    best = None
    for v, psi in zip(vals, vecs.T):
        vr = float(v.real)
        if not (lo < vr < hi):
            continue
        if best is None or vr > best[0]:
            best = (vr, psi)
    _require(best is not None, "1D 平板未找到受限模")
    return math.sqrt(best[0]) / k0, np.abs(best[1]) ** 2


# ---------------------------------------------------------------------------
# 4. 三条方法学路径
# ---------------------------------------------------------------------------
def gamma_semivec(wl_nm: float = WL_NM_DEFAULT, h_grid: float = 0.02,
                  L_win: float = 3.0, geom: Optional[Dict[str, Any]] = None,
                  n_pcm: Optional[float] = None) -> Dict[str, Any]:
    """路径 ①②：半矢量本征模 —— 场法 + 微扰法（同一求解器，两种数学量）。"""
    g = dict(GAMMA_GEOMETRY if geom is None else geom)
    if n_pcm is None:
        n_pcm = design_n_pcm(wl_nm)["n_mean"]
    k0 = 2.0 * math.pi / (wl_nm * 1e-3)
    _check_aligned(h_grid, g["w_um"], g["h_um"], g["t_pcm_um"], L_win)
    n2, xc, yc = _build_index(g["w_um"], g["h_um"], g["t_pcm_um"], g["n_core"],
                              g["n_clad"], n_pcm, True, h_grid=h_grid, L_win=L_win)
    n2ref, _, _ = _build_index(g["w_um"], g["h_um"], g["t_pcm_um"], g["n_core"],
                               g["n_clad"], n_pcm, False, h_grid=h_grid, L_win=L_win)
    neff, psi2 = _solve_semivec(n2, h_grid, k0)
    neff_ref, _ = _solve_semivec(n2ref, h_grid, k0)
    m = _pcm_mask(xc, yc, g["h_um"], g["t_pcm_um"], g["w_um"])
    g_field = float(psi2[m].sum() / psi2.sum())
    g_pert = (neff - neff_ref) / (n_pcm - g["n_clad"])
    edge = float((psi2[0].sum() + psi2[-1].sum() + psi2[:, 0].sum() + psi2[:, -1].sum())
                 / psi2.sum())
    return {"gamma_field": g_field, "gamma_perturbation": float(g_pert),
            "neff_with_pcm": float(neff), "neff_without_pcm": float(neff_ref),
            "n_pcm": float(n_pcm), "edge_fraction": edge,
            "h_um": float(h_grid), "L_um": float(L_win)}


def gamma_fullvec(wl_nm: float = WL_NM_DEFAULT, h_grid: float = 0.02,
                  L_win: float = 3.0, geom: Optional[Dict[str, Any]] = None,
                  n_pcm: Optional[float] = None) -> Dict[str, Any]:
    """路径 ③：**全矢量**（staggered Yee，独立离散）场法。"""
    g = dict(GAMMA_GEOMETRY if geom is None else geom)
    if n_pcm is None:
        n_pcm = design_n_pcm(wl_nm)["n_mean"]
    k0 = 2.0 * math.pi / (wl_nm * 1e-3)
    _check_aligned(h_grid, g["w_um"], g["h_um"], g["t_pcm_um"], L_win)
    n2, xc, yc = _build_index(g["w_um"], g["h_um"], g["t_pcm_um"], g["n_core"],
                              g["n_clad"], n_pcm, True, h_grid=h_grid, L_win=L_win)
    neff, h2, (xv, yv) = _solve_fullvec(n2, h_grid, k0, g["w_um"], g["h_um"])
    # 🔴 顶点网格上 PCM 区边界必须用**严格不等式**（芯顶面 y=h/2 那一行属**芯**，
    #    坐标恰为 h/2 ⇒ 不能带 1e-12 容差，否则会把强场的芯顶面算进 PCM ⇒ Γ 虚高）。
    pcm = ((yv > g["h_um"] / 2.0) &
           (yv <= g["h_um"] / 2.0 + g["t_pcm_um"]))[:, None] & \
          (np.abs(xv) <= g["w_um"] / 2.0)[None, :]
    g_field = float(h2[pcm].sum() / h2.sum())
    return {"gamma_field": g_field, "neff": float(neff), "n_pcm": float(n_pcm),
            "h_um": float(h_grid), "L_um": float(L_win)}


def gamma_slab(wl_nm: float = WL_NM_DEFAULT, h_grid: float = 0.02,
               L_win: float = 3.0, geom: Optional[Dict[str, Any]] = None,
               n_pcm: Optional[float] = None) -> Dict[str, Any]:
    """路径 ④：1D 垂直平板（**独立维度**，无限宽极限）场法。"""
    g = dict(GAMMA_GEOMETRY if geom is None else geom)
    if n_pcm is None:
        n_pcm = design_n_pcm(wl_nm)["n_mean"]
    k0 = 2.0 * math.pi / (wl_nm * 1e-3)
    _check_aligned(h_grid, g["h_um"], g["t_pcm_um"], L_win)
    nx = int(round(L_win / h_grid))
    x = (np.arange(nx) - nx / 2.0 + 0.5) * h_grid
    n = np.full(nx, g["n_clad"])
    n[np.abs(x) <= g["h_um"] / 2.0] = g["n_core"]
    n[(x > g["h_um"] / 2.0) & (x <= g["h_um"] / 2.0 + g["t_pcm_um"])] = n_pcm
    neff, u2 = _solve_slab(n, h_grid, k0)
    pcm = (x > g["h_um"] / 2.0) & (x <= g["h_um"] / 2.0 + g["t_pcm_um"])
    return {"gamma_field": float(u2[pcm].sum() / u2.sum()), "neff": float(neff),
            "n_pcm": float(n_pcm), "h_um": float(h_grid), "L_um": float(L_win)}


# ---------------------------------------------------------------------------
# 5. 汇总：主账 + 方法学区间 + 对照
# ---------------------------------------------------------------------------
def _band(ratio: float) -> str:
    """三带规则（与 M5/M6 同口径）。"""
    if ratio is None or ratio <= 0:
        return "undefined"
    r = ratio if ratio >= 1.0 else 1.0 / ratio
    if 0.5 <= r <= 2.0:
        return "same_order"
    if r <= 5.0:
        return "within_5x"
    return "outside_band"


_CACHE: Dict[Tuple[Any, ...], Dict[str, Any]] = {}


def gamma_multimethod(wl_nm: float = WL_NM_DEFAULT, grid: Optional[Dict[str, float]] = None,
                      geom: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """四路径全跑（带**进程内缓存** —— 同一参数只算一次，供 _ev_g2 反复调用不吃机时）。"""
    gd = dict(GRID_FAST if grid is None else grid)
    key = (round(float(wl_nm), 6), gd["h_um"], gd["L_um"], tuple(sorted((geom or GAMMA_GEOMETRY).items())))
    if key in _CACHE:
        return _CACHE[key]
    sv = gamma_semivec(wl_nm, gd["h_um"], gd["L_um"], geom)
    fv = gamma_fullvec(wl_nm, gd["h_um"], gd["L_um"], geom)
    sl = gamma_slab(wl_nm, gd["h_um"], gd["L_um"], geom)
    out = {"grid": gd, "semivec_field": sv["gamma_field"],
           "semivec_perturbation": sv["gamma_perturbation"],
           "fullvec_field": fv["gamma_field"], "slab_field": sl["gamma_field"],
           "neff_semivec_with_pcm": sv["neff_with_pcm"],
           "neff_semivec_without_pcm": sv["neff_without_pcm"],
           "neff_fullvec": fv["neff"], "neff_slab": sl["neff"],
           "edge_fraction": sv["edge_fraction"], "n_pcm": sv["n_pcm"]}
    _CACHE[key] = out
    return out


def gamma_calibration(wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """**Γ 标定主账**（快档）：主值 + 方法学区间 + 对照（假设 / 文献）。"""
    mm = gamma_multimethod(wl_nm)
    vals = [mm["semivec_field"], mm["semivec_perturbation"], mm["fullvec_field"], mm["slab_field"]]
    g_main = mm["semivec_field"]                       # 主账 = 场法（最直接的能量占比）
    g_ind = mm["fullvec_field"]                        # 独立离散对照
    n_pcm = mm["n_pcm"]
    from lda_l2 import pm_m0 as M0                     # 局部导入取**现役假设值**（对照用）
    hp = float(M0.GAMMA_DEFAULT)
    return {
        "geometry": dict(GAMMA_GEOMETRY), "wl_nm": float(wl_nm),
        "grid": dict(mm["grid"]), "n_pcm": n_pcm,
        "gamma_main": float(g_main),
        "gamma_independent_fullvec": float(g_ind),
        "gamma_perturbation": float(mm["semivec_perturbation"]),
        "gamma_slab": float(mm["slab_field"]),
        "gamma_min": float(min(vals)), "gamma_max": float(max(vals)),
        "two_method_rel_dev": abs(g_main - g_ind) / g_main,       # ①vs③ 独立离散一致性
        "field_pert_rel_dev": abs(g_main - mm["semivec_perturbation"]) / g_main,  # ①vs②
        "vs_assumption": {"assumption": hp, "ratio": g_main / hp,
                          "rel_dev": abs(g_main - hp) / hp, "band": _band(g_main / hp)},
        "vs_literature": {"lit_implied": LIT_IMPLIED_GAMMA, "source": LIT_IMPLIED_SOURCE,
                          "ratio": g_main / LIT_IMPLIED_GAMMA,
                          "band": _band(g_main / LIT_IMPLIED_GAMMA)},
        "claim_kind": GAMMA_CLAIM_KIND,
        "disclosure": dict(GAMMA_DISCLOSURE),
        "neff": {"semivec_with_pcm": mm["neff_semivec_with_pcm"],
                 "semivec_without_pcm": mm["neff_semivec_without_pcm"],
                 "fullvec": mm["neff_fullvec"], "slab": mm["neff_slab"]},
        "edge_fraction": mm["edge_fraction"],
    }


def gamma_convergence(wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """**收敛证据**（细档，一次性）：网格/窗口变化下主值漂移（供专用门禁）。"""
    a = gamma_multimethod(wl_nm)                        # 快档 h=0.02 / L=3
    b = gamma_multimethod(wl_nm, GRID_FINE)             # 细档 h=0.01 / L=4
    gm = a["semivec_field"]
    return {"coarse": {k: a[k] for k in ("semivec_field", "fullvec_field")},
            "fine": {k: b[k] for k in ("semivec_field", "fullvec_field")},
            "grid_rel_dev": abs(gm - b["semivec_field"]) / gm,
            "fullvec_rel_dev": abs(a["fullvec_field"] - b["fullvec_field"]) / a["fullvec_field"],
            "caches": len(_CACHE)}


def gamma_calibration_status(wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """**机器判定**：PM-G2 是否结算（全部读现算值，非字面量）。

    闭合口径 = 「Γ 为有限正数 <1 ∧ ①vs③ **独立离散**一致（rel<5%）∧ ①vs② 同量级
    （rel<20%）∧ 四条路径全部有限」。🔴 与「Γ 是否等于某个具体值」无关 ——
    计算值不作 golden。
    """
    cal = gamma_calibration(wl_nm)
    vals = [cal["gamma_main"], cal["gamma_independent_fullvec"],
            cal["gamma_perturbation"], cal["gamma_slab"]]
    finite = all(isinstance(v, float) and math.isfinite(v) and 0.0 < v < 1.0 for v in vals)
    ok = bool(finite and cal["two_method_rel_dev"] < 0.05 and cal["field_pert_rel_dev"] < 0.20)
    return {
        "calibrated": ok,
        "gap_pm_g2_open": not ok,
        "gamma_main": cal["gamma_main"],
        "gamma_independent_fullvec": cal["gamma_independent_fullvec"],
        "two_method_rel_dev": cal["two_method_rel_dev"],
        "field_pert_rel_dev": cal["field_pert_rel_dev"],
        "gamma_span": [cal["gamma_min"], cal["gamma_max"]],
        "vs_assumption_band": cal["vs_assumption"]["band"],
        "vs_literature_band": cal["vs_literature"]["band"],
        "claim_kind": GAMMA_CLAIM_KIND,
        "never_golden": True,
        "disclosed": "判定读四路径现算值（机器可查），不读任何声明的字面量。",
    }


def gamma_benchmark_rows(wl_nm: float = WL_NM_DEFAULT) -> List[Dict[str, Any]]:
    """**对拍表**：LDA 自研标定 vs ①M0 原假设 ②文献器件隐含（三带规则）。"""
    cal = gamma_calibration(wl_nm)
    rows = [
        {"metric": "gamma", "unit": "-",
         "lda_value": cal["gamma_main"], "lda_source": "pm_gamma.gamma_calibration（半矢量场法 · 现算）",
         "lit_value": cal["vs_assumption"]["assumption"], "lit_source": "pm_m0.GAMMA_DEFAULT（M0 原**假设**值）",
         "ratio": cal["vs_assumption"]["ratio"], "verdict": _band(cal["vs_assumption"]["ratio"]),
         "note": "🔴 原假设 Γ=%.3f 与自研标定值差 %.0f%% ⇒ **假设偏低**；方向要说清："
                 "`L ∝ 1/Γ` ⇒ 假设偏小让**报出的长度/面积偏大**（对面积保守），"
                 "但**可行窗同步缩小** ⇒ 按假设出的设计点在标定口径下**越窗**（不保守）"
                 "= 缺口 PM-G11。假设已可退役（但版图重标定是独立批次）。"
                 % (cal["vs_assumption"]["assumption"], 100 * cal["vs_assumption"]["rel_dev"])},
        {"metric": "gamma", "unit": "-",
         "lda_value": cal["gamma_main"], "lda_source": "pm_gamma.gamma_calibration（半矢量场法 · 现算）",
         "lit_value": LIT_IMPLIED_GAMMA, "lit_source": LIT_IMPLIED_SOURCE,
         "ratio": cal["vs_literature"]["ratio"], "verdict": _band(cal["vs_literature"]["ratio"]),
         "note": "文献器件（**不同几何/材料**）隐含模式重叠 —— 只作交叉参照（不构成同一器件的互验）。"},
        {"metric": "gamma_fullvec_vs_semivec", "unit": "-",
         "lda_value": cal["gamma_independent_fullvec"], "lda_source": "全矢量 staggered（独立离散）",
         "lit_value": cal["gamma_main"], "lit_source": "半矢量 collocated（主账）",
         "ratio": cal["gamma_independent_fullvec"] / cal["gamma_main"],
         "verdict": _band(cal["gamma_independent_fullvec"] / cal["gamma_main"]),
         "note": "🔴 **换一套离散、值不变** —— 这是「实现无关」的强证据（不是文献对照）。"},
    ]
    return rows


def gamma_impact_on_design(wl_nm: float = WL_NM_DEFAULT, mat: str = "GST",
                           n_levels: int = 16) -> Dict[str, Any]:
    """Γ 标定对**下游设计点**的影响（1/Γ 缩放律 · 机器可复核，不是口号）。

    原理：M1 振幅域的可行窗两端都 ∝ 1/Γ —— 每 µm 损耗 ∝ Γ 而 dB 预算固定 ⇒
    `L_swing = contrast_need_db / db_per_um`、`L_starve = il_starve_db / (…·Γ·k_a)` 均 ∝ 1/Γ；
    设计点 `L_mid = ½(L_swing + min(L_starve, 3·L_swing))` 亦 ∝ 1/Γ（离散公式只搬运，不改幂次）
    ⇒ **L_mid(Γ_cal) = L_mid(Γ_assumed) · Γ_assumed / Γ_cal**（精确等式，可核到机器精度）。

    🔴 本函数把「Γ 标定」与「全链版图数字」之间的断口**算出来并披露**：按**标定** Γ，原设计点
    （按假设 0.05 出图）会**越出可行窗上界**（读出会饿死）⇒ 现有 M0–M6 的**绝对**长度/版图数字
    须重标定（登记为缺口 **PM-G11**，两口径**并报**，不选择性披露）。

    ⚠️ 与「Γ-无关量」的分野：每 π 损耗 `IL_π`、M1 可行性判据 `r = k_a/(k_c−k_a)`、
    相位域 FOM `Δn/(8.6859k)` **不含 Γ**（Γ 与 L 同时约掉）⇒ 这些结论**不受本断口影响**
    （门禁 `run_pm_g2_smoke` C16 用**两档 Γ 现算互等**证明，非引述）。
    """
    from lda_l2 import pm_m0 as M0
    from lda_l2 import pm_m1 as M1
    g_assumed = float(M0.GAMMA_DEFAULT)
    g_cal = float(gamma_calibration_status(wl_nm)["gamma_main"])

    def _probe(g: float) -> Dict[str, Any]:
        rep = M1.m1_report(mat, n_levels, gamma=g, wl_nm=wl_nm)
        dd = rep.get("demo_design_point") or {}
        src = dd.get("source")
        rows = [x for x in rep["feasibility"]["per_source"] if x["source"] == src] or \
               [rep["feasibility"]["per_source"][0]]
        f = rows[0]
        return {"gamma": float(g), "source": src,
                "window_um": (list(f["window_um"]) if f["window_um"] else None),
                "l_swing_um": f["l_swing_um"], "l_starve_um": f["l_starve_um"],
                "l_mid_um": dd.get("l_mid_um"), "feasible": bool(f["feasible"])}

    a = _probe(g_assumed)
    b = _probe(g_cal)
    ratio = g_assumed / g_cal
    l_pred = (a["l_mid_um"] * ratio) if a["l_mid_um"] else None
    law_rel = (abs(l_pred - b["l_mid_um"]) / b["l_mid_um"]) if (l_pred and b["l_mid_um"]) else None
    win = b["window_um"]
    design_pt = a["l_mid_um"]                      # **现役**设计点（按假设 Γ 出图那一个）
    inside = bool(win and design_pt and win[0] <= design_pt <= win[1])
    outside_by = (design_pt - win[1]) if (win and design_pt and design_pt > win[1]) else 0.0
    return {
        "material": mat, "n_levels": int(n_levels), "wl_nm": float(wl_nm),
        "gamma_assumed": g_assumed, "gamma_calibrated": g_cal, "scale_ratio": ratio,
        "assumed": a, "calibrated": b,
        "l_mid_predicted_by_law_um": l_pred, "law_rel_dev": law_rel,
        "design_point_inside_calibrated_window": inside,
        "design_point_outside_by_um": outside_by,
        "design_point_outside_frac": (outside_by / win[1]) if (win and win[1]) else None,
        "reads_out": (not inside),
        "gap": "PM-G11",
        "disclosure": {
            "rule": "L ∝ 1/Γ（可行窗两端同阶）⇒ 绝对长度结论随 Γ 反比缩放",
            "headline": ("按标定 Γ=%.4f：可行窗 [%.3f, %.3f] µm，设计点应为 %.3f µm；"
                         "现值 %.3f µm（按假设 Γ=%.3f 出图）**越出窗上界 %.3f µm（+%.1f%%）**"
                         " ⇒ 读出饿死，须重标定（PM-G11）"
                         % (g_cal, win[0], win[1], b["l_mid_um"], design_pt, g_assumed,
                            win[1], 100.0 * (outside_by / win[1] if win and win[1] else 0.0))),
            "gamma_invariant": ["IL_π（每 π 损耗）", "M1 可行性判据 r=k_a/(k_c−k_a)",
                                "相位域 FOM=Δn/(8.6859k)"],
            "gamma_invariant_note": "Γ 与 L 同时约掉 ⇒ 上述结论**不受**本断口影响"
                                    "（门禁 C16 以两档 Γ 现算互等证明）。",
            "never_golden": True, "claim_kind": GAMMA_CLAIM_KIND,
        },
    }


def gamma_case_summary(wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """前端摘要（纯现算 · 无文件 IO）。"""
    cal = gamma_calibration(wl_nm)
    return {"geometry": cal["geometry"], "gamma_main": cal["gamma_main"],
            "gamma_span": [cal["gamma_min"], cal["gamma_max"]],
            "methods": {"semivec_field": cal["gamma_main"],
                        "semivec_perturbation": cal["gamma_perturbation"],
                        "fullvec_field": cal["gamma_independent_fullvec"],
                        "slab": cal["gamma_slab"]},
            "two_method_rel_dev": cal["two_method_rel_dev"],
            "vs_assumption": cal["vs_assumption"], "vs_literature": cal["vs_literature"],
            "benchmark_rows": gamma_benchmark_rows(wl_nm),
            "impact_on_design": gamma_impact_on_design(wl_nm),
            "calibration_status": gamma_calibration_status(wl_nm),
            "claim_kind": GAMMA_CLAIM_KIND, "disclosure": cal["disclosure"],
            "grid": cal["grid"]}


def _json_safe(obj: Any) -> Any:
    """JSON 出口安全（防非标准 token —— 消费者口径 = 浏览器 JSON.parse）。"""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, (np.floating,)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj
