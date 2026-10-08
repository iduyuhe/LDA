# -*- coding: utf-8 -*-
"""B-38 数值核（Batch B-38 · 光子传感器新征程 PS-M8 · G2 几何半 + G4 传感窗口）。

═══ 物理族 ═══
PS-M8 = **几何灵敏度半**（G2 几何半）+ **Q 增强 LOD 缩放**（G2 几何半的探测极限推高），
并把 **G4 传感窗口层 / DRC 例外** 作为器件元数据 + 门禁收口（见 ps_m8.py / drc.py / registry.py）。

**B469 / B470 / B471**＝三种高灵敏几何（thin-wire / slot / suspended）的波导折射率灵敏度
``S = d n_eff / d n_a``，golden 与 candidate 用**同一套全矢量本征模求解器（FV，自研、
scipy 仅为标准数值库，非 GPL/Meep/Tidy3D）**两条**方法学独立**路径互验：

| 锚 | 几何 | golden（一阶本征值微扰闭式） | candidate（FV-FD 有限差分） |
|---|---|---|---|
| **B469** | thin-wire 窄条 | ``S = dγ/dn_a / (2 k0² n_eff)``，γ=(k0·n_eff)²；``dγ/dn_a=⟨w|δÂ|h⟩/⟨w|h⟩``（Rayleigh 商·**左本征矢** w） | perturb ``n_a`` ±δ → 重解 ``n_eff`` → 中心差商 |
| **B470** | slot 狭缝 | 同上 | 同上 |
| **B471** | suspended 悬浮 | 同上 | 同上 |

🔴 **golden 方法学（已定谳，取代旧 Γ_a 积分法）**：
    ``build_operator`` 返回的算子 **非对称**（‖A−Aᵀ‖/‖A‖≈18.6%，staggered 离散所致），
    故一阶本征值微扰 ``δγ = ⟨h|δA|h⟩/⟨h|h⟩`` **不可用右本征矢**（错得 S=0.815 vs 真值 0.495）；
    必须用**左本征矢** ``w``（Aᵀ 在 γ0 的右本征矢）⇒ ``δγ = ⟨w|δA|h⟩/⟨w|h⟩``。
    用左本征矢后 RQ 给出 ``dγ/dn_a=27.2544``，与 re-solve 实算 ``27.2560`` **机器精度一致**。
    δÂ 仅来自 analyte 区 ε 改变：``δε = 2·N_A·δ``（ε=n²）。
    golden 与 candidate 同为 FV 但**方法学独立**：golden = 线性化微扰（不重解），
    candidate = 重解后中心差商（brute perturbation）。同 B460 的 HF 律 vs FD 互验口径。

**B472**＝Q 增强 LOD 缩放闭式：谐振腔 Q 升高 → 线宽收窄 → 边缘斜率 ``∝ Q`` →
``LOD_elec ∝ 1/Q``，而 ``LOD_temp`` 与 Q **解耦**（同 PS-M2）⇒
``LOD_real(Q) = √((LOD_elec_ref·Q0/Q)² + LOD_temp_ref²)``（闭式）↔ 模型实算（方法学独立）。

🔴 **B472 测试区间纪律（诚实）**：默认噪声（5 mK / 无 referencing / CMR=1）下 ``LOD_temp≈9.3e-7``
**远大于** ``LOD_elec≈1.8e-10`` ⇒ ``LOD_real`` 被热漂地板主导、**与 Q 无关**（缩放退化、单调性失效）。
故 B472 必须在**电学受限（充分 referencing）区间**演示：``LOD_real≈LOD_elec∝1/Q`` 才可见。
锚默认噪声取 ``B472_NOISE``（CMR=1e4，≈80 dB 差分 referencing —— 平衡双通道可达），
热漂被压到 ``LOD_temp≈9.3e-11``，Q 缩放清晰可见且单调。物理要点：Q 增强 LOD **仅当**
热漂被 referencing 抑制时才成立（真实传感器多热漂受限），此洞察本身就是 B472 要交付的诚实结论。

🔴 同源体检（实 grep 全仓，排除噪声）：
    · `thin.wire|thinwire|窄条|几何灵敏度|geometry.*sensitivity` 在 BENCHMARK_DEFS 内 **0 命中**
      ⇒ **高灵敏几何族零锚占用（本族首锚）**。
    · `slot|狭缝|slot.*waveguide` 在 BENCHMARK_DEFS 内 **0 命中** ⇒ **slot 族零锚占用**。
    · `suspended|悬浮|Q.*增强|Q.*scaling|LOD.*Q` 在 BENCHMARK_DEFS 内 **0 命中**
      ⇒ **suspended / Q-scaling 族零锚占用**。
    · 与 PS-M0~M7（B459~B468）被测标量（谐振斜率 / 折射率导数 / 覆盖度 / 流量 / 毛细 /
      热阻 / 串扰 / 噪声底 / 对准）**完全不同** ⇒ **非重复计数**。

🔴 血案预防（沿用 B460 同族经验 + 本 session 实测）：
    1. **非对称算子必须用左本征矢**：右本征矢 RQ 系统性错（strip 0.815 vs 0.495）；左本征矢机器精度对齐。
    2. **FD 步长 δ 不可太小也不可太大**：δ 太小 ⇒ 中心差商陷双精度抵消（地板，随网格不降反升，判假独立，
       B-10 同族）；δ 太大 ⇒ O(δ²) 截断主导。取 δ=1e-4（实测两 regime 都干净）。
    3. **n_a 扰动只改 water（1.33）单元**：core（Si 3.4777）/ substrate（SiO2 1.444）保持不变；
       suspended 时去掉 substrate（原 SiO2 区改 water）⇒ 唯一大幅增强杠杆（2.4×）。
    4. **选模口径 golden≡candidate**：统一 ``conf_min=0.0 + frac_hy_core>0.5 + n_eff>N_SUB+0.01``；
       薄条/弱狭缝的受限导模 conf_core 会 <0.30（被旧阈值滤成 nan），必须降到 0.0 再判受限。
    5. **诚实梯度（实测）**：SOI 220nm 下 substrate 受限的薄条/狭缝灵敏度 ≈ strip 基线或略低
       （strip≈0.495 / thinwire(0.22)≈0.447 / slot≈0.434–0.446）；唯一戏剧杠杆是**去衬底**
       suspended→1.171（2.4×）。判据梯度断言 = 「suspended ≫ strip ≈ thinwire ≈ slot」，
       **不要求 slot>thinwire>strip**（该梯度在物理上错）。

🔴 scipy 隔离纪律：本模块**顶层只 import numpy/math**；FV 求解器与 `eigs`（scipy 依赖）在**函数体内惰性 import**，
确保 `benchmark_defs/part6.py` 顶层 `from ._batch_b38_numeric import golden_b469` 不触发 scipy，
避免 scipy 泄漏进 count_consistency / three_class 等**闭式解释器**门禁（与 B460 的 `_get_batch_b34()` 惰性加载同口径）。

诚实边界：
    · 几何/材料为**设计示例**（SOI 220nm @1550nm；water n_a=1.33 / SiO2 substrate 1.444 / Si core 3.4777）。
      slot 狭缝水介质、suspended 去衬底均为真实可制造传感几何。结论只可用于数值方法与量级，
      **不得作制造/性能宣称**。
    · golden 的一阶微扰是**闭式物理律**（Rayleigh 商微扰定理）；其被积量 ⟨w|δÂ|h⟩ 在离散算子上数值求和
      （被积函数无更简闭式）——与 B460（slab 闭式 Γ）同族但更一般；残差由 RQ 微扰 vs FD 重解双重独立路径互证。
    · 零商业依赖（numpy + scipy 标准数值库）。
"""
from __future__ import annotations

import functools
import math
from typing import Dict, Optional, Tuple

import numpy as np


# ===========================================================================
# 公共几何 / 材料（设计示例）
# ===========================================================================
N_CORE = 3.4777          # 晶体硅 @1550nm
N_SUB = 1.444            # 二氧化硅衬底（埋氧 / buried oxide）
N_A = 1.33               # 待测 analyte（水 @1550nm）
WL = 1.55                # µm
H_GRID_DEFAULT = 0.010    # µm（与 FV 求解器生产档对齐：0.22/0.45/0.06 均为 0.01 整数倍）
L_HALF_DEFAULT = 1.5     # µm 半窗（water/spin 低对比度，留足模场余量）

# 逐几何默认档（均为 h_grid=0.01 的整数倍尺寸，避免楼梯误差）
# thinwire 需 w≥0.22（0.12/0.16/0.18/0.20 全截止→nan）；slot 需 rail≥0.18 且 gap≤0.05
# （rail=0.18 gap=0.08/0.10→nan）。默认档经扫参确认可受限。
_DEFAULTS = {
    "strip":   dict(w_um=0.45, h_um=0.22, gap_um=0.0, w_rail_um=0.0,
                    substrate=True, Lhalf_um=L_HALF_DEFAULT),
    "thinwire": dict(w_um=0.22, h_um=0.22, gap_um=0.0, w_rail_um=0.0,
                     substrate=True, Lhalf_um=L_HALF_DEFAULT),
    "slot":    dict(w_um=0.0, h_um=0.22, gap_um=0.05, w_rail_um=0.22,
                    substrate=True, Lhalf_um=L_HALF_DEFAULT),
    "suspended": dict(w_um=0.45, h_um=0.22, gap_um=0.0, w_rail_um=0.0,
                      substrate=False, Lhalf_um=L_HALF_DEFAULT),
}


# ===========================================================================
# 几何 ε 场构建（cell-centered n²）+ analyte / core 单元掩码
# ===========================================================================
def _build_eps(kind: str, p: Dict[str, float],
               h_grid: float, Lhalf: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """构建任意 2D 截面的 ε 场（cell-centered n²）与坐标。

    坐标：x 横向（沿宽）、y 纵向（沿高）；窗口 [-Lhalf, Lhalf]²。
    几何（snap 到 h_grid 格线，避免楼梯误差）：
      · core（Si）= 居中矩形 |x|≤w/2, |y|≤h/2；slot 时 core = 两道 rail（|x|∈(gap/2, gap/2+w_rail)）；
      · substrate（SiO2）= y < -h/2（suspended 时取消，改 water）；
      · 其余 = analyte（water, n_a）。
    返回 (eps, xv_node, yv_node, is_a_cell, is_core_cell)：xv_node/yv_node 为**顶点网格**（供求解器）。
    """
    n = 2 * int(round(Lhalf / h_grid))
    x_node = (np.arange(n + 1) - n / 2.0) * h_grid
    y_node = x_node
    x_cell = 0.5 * (x_node[:-1] + x_node[1:])   # cell 中心（eps 用）
    y_cell = 0.5 * (y_node[:-1] + y_node[1:])
    Xc, Yc = np.meshgrid(np.asarray(x_cell).real, np.asarray(y_cell).real, indexing="ij")

    n_core = N_CORE
    n_sub = N_SUB
    n_a = N_A
    eps = np.full(Xc.shape, n_a ** 2, dtype=np.float64)

    if p.get("substrate", True):
        eps[Yc < (-p["h_um"] / 2.0 - 1e-12)] = n_sub ** 2

    # core（Si）—— snap 边界到格线
    hw = max(int(round(p["w_um"] / 2.0 / h_grid)), 1) * h_grid
    hh = max(int(round(p["h_um"] / 2.0 / h_grid)), 1) * h_grid
    w, h = 2.0 * hw, 2.0 * hh
    is_core = (np.abs(Xc) <= w / 2.0 + 1e-12) & (np.abs(Yc) <= h / 2.0 + 1e-12)

    if kind == "slot":
        gap = max(int(round(p["gap_um"] / h_grid)), 1) * h_grid
        wr = max(int(round(p["w_rail_um"] / 2.0 / h_grid)), 1) * h_grid
        gp = gap / 2.0
        rail = ((np.abs(Xc) > gp - 1e-12) & (np.abs(Xc) <= gp + wr + 1e-12))
        is_core = is_core | (rail & (np.abs(Yc) <= h / 2.0 + 1e-12))
    eps[is_core] = n_core ** 2

    is_a_cell = np.abs(eps - n_a ** 2) < 1e-6
    is_core_cell = np.abs(eps - n_core ** 2) < 1e-6
    return eps, x_node, y_node, is_a_cell, is_core_cell


def _vertex_mask_from_cells(is_cell: np.ndarray) -> np.ndarray:
    """cell 布尔掩码 → 顶点掩码（任一邻 cell 为真即真，一格膨胀，对齐 solver 的 core_vertex_mask）。

    返回形状 = (nyc+1, nxc+1)，与 ModeResult.hx/hy 的**顶点网格**同形（否则 Γ_a 积分广播错位）。
    """
    nyc, nxc = is_cell.shape
    pad = np.pad(is_cell, 1, mode="constant", constant_values=False)
    return (pad[0:nyc + 1, 0:nxc + 1]
            | pad[0:nyc + 1, 1:nxc + 2]
            | pad[1:nyc + 2, 0:nxc + 1]
            | pad[1:nyc + 2, 1:nxc + 2])


def _solve_te0(kind: str, p: Dict[str, float], h_grid: float = H_GRID_DEFAULT,
               k: int = 6) -> Optional[object]:
    """FV 求解 TE0 基模，返回 ModeResult（无受限导模 ⇒ None）。

    🔴 scipy（FV 求解器）**惰性 import**：仅在本函数被实际调用时加载，确保模块顶层 scipy-free。
    🔴 选模口径（golden≡candidate 一致）：``conf_min=0.0`` + TE 主导（frac_hy_core>0.5）
    + 受限（n_eff > N_SUB+0.01）。旧 conf_min=0.30 会把薄条/弱狭缝的受限导模滤成 nan。
    """
    from lda_solver.full_vector_mode_solver import solve_modes_eps  # 惰性：scipy 依赖

    eps, xv, yv, is_a_cell, is_core_cell = _build_eps(kind, p, h_grid, p["Lhalf_um"])
    core_vmask = _vertex_mask_from_cells(is_core_cell)
    k0 = 2.0 * math.pi / WL
    rs = solve_modes_eps(eps, xv, yv, k0, k=k, core_vmask=core_vmask, conf_min=0.0)
    return _pick_te0(rs)


def _pick_te0(rs) -> Optional[object]:
    """从 solve_modes_eps 候选中选 TE0 基模：最高 n_eff、TE 主导、受限。

    `rs` 已按 n_eff 降序；第一个满足 TE 主导 + 受限者即基模。
    """
    if not rs:
        return None
    for r in rs:
        if r.frac_hy_core > 0.5 and r.neff > N_SUB + 0.01:
            return r
    return None


# ===========================================================================
# B469 / B470 / B471 · 几何灵敏度：一阶本征值微扰 golden + FV-FD candidate
# ===========================================================================
def _geometry_sensitivity_golden_uncached(kind: str, p: Optional[Dict[str, float]] = None,
                                h_grid: float = H_GRID_DEFAULT,
                                delta: float = 1e-4) -> float:
    """golden：一阶本征值微扰（Rayleigh 商 + **左本征矢**）闭式求 ``S = dn_eff/dn_a``。

    算子 ``A h = γ h``，``γ = (k0·n_eff)²``，非对称（staggered ⇒ ‖A−Aᵀ‖/‖A‖≈18.6%）⇒
    一阶微扰必须用**左本征矢** ``w``（Aᵀ 在 γ0 的右本征矢）：

        ``dγ/dn_a = ⟨w | δA | h⟩ / ⟨w | h⟩``，其中 ``δA`` 仅来自 analyte 区 ``δε = 2·N_A·δ``

    再 ``S = dγ/dn_a / (2·k0²·n_eff)``。

    🔴 scipy（`eigs` / 求解器）**惰性 import**：golden 仅在 scipy 环境下实算；
    闭式门禁（count_consistency / three_class）只导入本模块顶层别名、不触发 scipy。
    n_a ≤ 0 / 无受限导模 ⇒ nan。
    """
    pp = dict(_DEFAULTS[kind]) if p is None else dict(p)
    from lda_solver.full_vector_mode_solver import solve_modes_eps, build_operator  # 惰性
    from scipy.sparse.linalg import eigs  # 惰性（scipy）

    eps, xv, yv, is_a_cell, is_core_cell = _build_eps(kind, pp, h_grid, pp["Lhalf_um"])
    core_vmask = _vertex_mask_from_cells(is_core_cell)
    k0 = 2.0 * math.pi / WL
    dx = np.diff(xv)
    dy = np.diff(yv)
    rs = solve_modes_eps(eps, xv, yv, k0, k=6, core_vmask=core_vmask, conf_min=0.0)
    best = _pick_te0(rs)
    if best is None:
        return float("nan")
    n_eff = float(best.neff)
    # 右本征矢 h（concat Hx, Hy，vertex 顺序 C）
    hv = np.concatenate([best.hx.ravel(order="C"), best.hy.ravel(order="C")])
    A0 = build_operator(eps, dx, dy, k0)[0]
    gamma0 = (k0 * n_eff) ** 2
    # 左本征矢 = Aᵀ 在 γ0 的右本征矢（A 非对称 ⇒ 必须用左本征矢，否则错 0.815 vs 0.495）
    wv = eigs(A0.T.tocsc(), k=1, sigma=gamma0, return_eigenvectors=True)[1][:, 0].real
    # 扰动 analyte 折射率 n_a → n_a + δ（ε += 2 N_A δ，忽略 O(δ²)）
    eps_p = eps.copy().astype(float)
    eps_p[is_a_cell] = eps_p[is_a_cell] + 2.0 * N_A * delta
    Ap = build_operator(eps_p, dx, dy, k0)[0]
    gamma_p = float(np.vdot(wv, Ap.dot(hv)).real) / float(np.vdot(wv, hv).real)
    dgamma_dna = (gamma_p - gamma0) / delta
    S = dgamma_dna / (2.0 * k0 * k0 * n_eff)
    return float(S)


# ===========================================================================
# 进程内记忆化层（v0.9.210 · 性能纪律 · **不改数值**）
# ===========================================================================
# 🔴 动机（实测血案）：`run_l1_agent_smoke` 在**同一进程内**对全 490 题做 4 次
#    `verify_design` ⇒ 同一 (kind, params, h_grid, delta) 的 golden 被**重算 4 遍**；
#    B469/B470/B471 的 golden 各含一次 FV 全矢量本征求解 + `eigs`（单次 6~7 s）⇒
#    该 smoke 从 ~20 s 涨到 ~135 s（账本本身 486 题只要 20.2 s，**4 道新锚占 19 s/遍**）。
#    `run_benchmark_falsifiability_smoke` 同理。
# 🔴 安全性论证：下列四个函数均为**纯函数** —— 无全局可变态、无 I/O、无随机源、
#    无 wall-clock 依赖（参数缺省来自模块级常量 `_DEFAULTS` / `H_GRID_DEFAULT`）。
#    ⇒ 记忆化**语义中性**：同入参必得同一浮点值，只省时间。
# 🔴 键归一：`p` / `noise` 为 dict（不可哈希）⇒ 归一为 sorted tuple；`None` 与空 dict
#    视作**同一态**（与各函数体 `dict(_DEFAULTS[kind]) if p is None` 的读取语义一致）。
#    参数被调用方在返回后原地改动不影响已缓存结果（键是快照）。


def _ckey(p):
    """params/noise dict ⇒ 可哈希快照键（None 与 {} 归一为 None）。"""
    if not p:
        return None
    return tuple(sorted((str(k), float(v)) for k, v in p.items()))


def _unkey(k):
    """快照键 ⇒ 新 dict（避免把内部快照暴露给被调用函数）。"""
    return None if k is None else dict(k)


@functools.lru_cache(maxsize=None)
def _geom_golden_c(kind, pkey, h_grid, delta):
    return _geometry_sensitivity_golden_uncached(kind, _unkey(pkey), h_grid, delta)


@functools.lru_cache(maxsize=None)
def _geom_fd_c(kind, pkey, delta, h_grid):
    return _geometry_sensitivity_fd_uncached(kind, _unkey(pkey), delta, h_grid)


@functools.lru_cache(maxsize=None)
def _lod_golden_c(Q, Q0, S, wl, nkey):
    return _q_scaling_lod_golden_uncached(Q, Q0, S, wl, _unkey(nkey))


@functools.lru_cache(maxsize=None)
def _lod_cand_c(Q, Q0, S, wl, nkey):
    return _q_scaling_lod_cand_uncached(Q, Q0, S, wl, _unkey(nkey))


def geometry_sensitivity_golden(kind: str, p: Optional[Dict[str, float]] = None,
                                h_grid: float = H_GRID_DEFAULT,
                                delta: float = 1e-4) -> float:
    """【记忆化入口】golden：一阶本征值微扰（Rayleigh 商 + 左本征矢）求 ``S=dn_eff/dn_a``。

    实现与口径见 `_geometry_sensitivity_golden_uncached`（含左本征矢必要性的血案说明）。
    本包装仅做**入参记忆化**（纯函数 ⇒ 数值逐位不变；首次调用耗时，重复调用 O(1)）。
    """
    return _geom_golden_c(kind, _ckey(p), float(h_grid), float(delta))


def geometry_sensitivity_fd(kind: str, p: Optional[Dict[str, float]] = None,
                            delta: float = 1e-4,
                            h_grid: float = H_GRID_DEFAULT) -> float:
    """【记忆化入口】候选：FV-FD 中心差商求 ``S=dn_eff/dn_a``。

    实现与口径见 `_geometry_sensitivity_fd_uncached`。本包装仅做入参记忆化。
    """
    return _geom_fd_c(kind, _ckey(p), float(delta), float(h_grid))


def q_scaling_lod_golden(Q: float, Q0: float, S_nm_per_riu: float, wl_um: float = 1.55,
                         noise: Optional[Dict[str, float]] = None) -> float:
    """【记忆化入口】golden：Q-scaling 闭式 ``LOD_real(Q)``。

    实现与推导见 `_q_scaling_lod_golden_uncached`。本包装仅做入参记忆化。
    """
    return _lod_golden_c(float(Q), float(Q0), float(S_nm_per_riu), float(wl_um),
                         _ckey(noise))


def q_scaling_lod_cand(Q: float, Q0: float, S_nm_per_riu: float, wl_um: float = 1.55,
                       noise: Optional[Dict[str, float]] = None) -> float:
    """【记忆化入口】候选：模型实算 ``LOD_real(Q)``。

    实现与口径见 `_q_scaling_lod_cand_uncached`。本包装仅做入参记忆化。
    """
    return _lod_cand_c(float(Q), float(Q0), float(S_nm_per_riu), float(wl_um),
                       _ckey(noise))


#: golden 入口别名（part6.py 顶层引用）
golden_b469 = lambda: geometry_sensitivity_golden("thinwire")     # noqa: E731
golden_b470 = lambda: geometry_sensitivity_golden("slot")         # noqa: E731
golden_b471 = lambda: geometry_sensitivity_golden("suspended")    # noqa: E731
# strip 基线（非锚，仅供梯度对照）
golden_strip_baseline = lambda: geometry_sensitivity_golden("strip")  # noqa: E731


def _geometry_sensitivity_fd_uncached(kind: str, p: Optional[Dict[str, float]] = None,
                           delta: float = 1e-4, h_grid: float = H_GRID_DEFAULT) -> float:
    """候选：FV-FD 有限差分 perturb ``n_a`` ±δ → 重解 ``n_eff`` → 中心差商。

    δ 默认 1e-4（避开双精度抵消地板，又不引入 O(δ²) 截断主导）。
    选模口径与 golden 严格一致（conf_min=0.0 + TE 主导 + 受限），否则两路径口径错位。
    无导模 / δ ≤ 0 ⇒ nan。
    """
    if delta <= 0:
        return float("nan")
    pp = dict(_DEFAULTS[kind]) if p is None else dict(p)
    from lda_solver.full_vector_mode_solver import solve_modes_eps  # 惰性
    eps0, xv, yv, is_a_cell, is_core_cell = _build_eps(kind, pp, h_grid, pp["Lhalf_um"])
    core_vmask = _vertex_mask_from_cells(is_core_cell)
    k0 = 2.0 * math.pi / WL

    def _neff_with_na(na_mod: float) -> float:
        eps = eps0.copy()
        eps[is_a_cell] = na_mod ** 2
        rs = solve_modes_eps(eps, xv, yv, k0, k=6, core_vmask=core_vmask, conf_min=0.0)
        r = _pick_te0(rs)
        return float(r.neff) if r is not None else float("nan")

    np_ = N_A + delta
    nm_ = N_A - delta
    n_eff_p = _neff_with_na(np_)
    n_eff_m = _neff_with_na(nm_)
    if not (math.isfinite(n_eff_p) and math.isfinite(n_eff_m)):
        return float("nan")
    return float((n_eff_p - n_eff_m) / (2.0 * delta))


#: 候选入口别名（候选注册装饰器引用）
cand_b469 = lambda: geometry_sensitivity_fd("thinwire")     # noqa: E731
cand_b470 = lambda: geometry_sensitivity_fd("slot")         # noqa: E731
cand_b471 = lambda: geometry_sensitivity_fd("suspended")    # noqa: E731


# ===========================================================================
# B472 · Q 增强 LOD 缩放闭式
# ===========================================================================
# 电学受限区间：差分 referencing CMR=1e4（≈80 dB，平衡双通道可读出）压低热漂，
# 使 LOD_temp≈9.3e-11 ≪ LOD_elec（Q 缩放可见且单调）。真实 5 mK 无 referencing
# 传感器热漂主导、Q 缩放退化（已诚实披露，不作锚测试区间）。
B472_NOISE: Dict[str, float] = {
    "power_W": 1e-3, "dt_s": 1e-3, "eta": 0.8, "NEP_W_per_sqrtHz": 1e-12,
    "RIN_per_Hz": 1e-14, "Idark_A": 1e-9, "R_AW": 1.0,
    "dn_dT": 1.86e-4, "dT_stability_K": 5e-3, "CMR": 1e4,
    "T_bg": 1.0, "T_min": 0.1,
}


def _q_scaling_lod_golden_uncached(Q: float, Q0: float, S_nm_per_riu: float, wl_um: float = 1.55,
                         noise: Optional[Dict[str, float]] = None) -> float:
    """golden：Q-scaling 闭式 ``LOD_real(Q) = √((LOD_elec_ref·Q0/Q)² + LOD_temp_ref²)``。

    由 PS-M2 模型导出：FWHM=λ/Q ⇒ 边缘斜率 ∝ Q ⇒ ``LOD_elec ∝ 1/Q``；而 ``LOD_temp``
    与 Q **解耦**（同 PS-M2，热漂由温控决定）。ref = Q0 处模型实算值。
    Q ≤ 0 / S ≤ 0 / Q0 ≤ 0 ⇒ nan。
    """
    if Q <= 0 or Q0 <= 0 or S_nm_per_riu <= 0:
        return float("nan")
    from lda_l2.ps_m2 import lod_real  # 惰性（ps_m2 纯 numpy，无 scipy）
    r0 = lod_real(S_nm_per_riu, Q0, wl_um, noise)
    lod_elec_ref = r0["LOD_elec_riu"]
    lod_temp_ref = r0["LOD_temp_riu"]
    if not (math.isfinite(lod_elec_ref) and math.isfinite(lod_temp_ref)):
        return float("nan")
    val = (lod_elec_ref * Q0 / Q) ** 2 + lod_temp_ref ** 2
    return float(math.sqrt(val)) if val >= 0 else float("nan")


def _q_scaling_lod_cand_uncached(Q: float, Q0: float, S_nm_per_riu: float, wl_um: float = 1.55,
                      noise: Optional[Dict[str, float]] = None) -> float:
    """候选：模型实算 ``LOD_real(Q)``（PS-M2 lod_real，逐分量合成）。

    与 golden 的 Q-scaling 闭式方法学独立：golden 走「斜率 ∝ Q 推导出的闭式」，
    candidate 走「模型逐分量合成」两条路径在 Q 维度互验。
    """
    if Q <= 0 or S_nm_per_riu <= 0:
        return float("nan")
    from lda_l2.ps_m2 import lod_real  # 惰性
    r = lod_real(S_nm_per_riu, Q, wl_um, noise)
    return float(r["LOD_real_riu"])


#: 别名（默认走电学受限区间 B472_NOISE，Q 缩放可见）
golden_b472 = lambda: q_scaling_lod_golden(1e5, 1e4, 300.0, noise=B472_NOISE)   # noqa: E731
cand_b472 = lambda: q_scaling_lod_cand(1e5, 1e4, 300.0, noise=B472_NOISE)       # noqa: E731


# ===========================================================================
# 判据 D / 反向探针 用默认档与 tol（待 Task #35 实测标定）
# ===========================================================================
_GRID_BY_BID = {
    "B469": [1e-5, 2e-5, 5e-5, 1e-4, 2e-4],   # FD 步长 δ（O(δ²) 截断，太细陷地板）
    "B470": [1e-5, 2e-5, 5e-5, 1e-4, 2e-4],
    "B471": [1e-5, 2e-5, 5e-5, 1e-4, 2e-4],
    "B472": [1e4, 2e4, 5e4, 1e5, 2e5],        # Q 扫描（缩放律精确，残差应恒 < tol）
}
_KW_BY_BID = {"B469": "delta", "B470": "delta", "B471": "delta", "B472": "Q"}
_TOL_BY_BID = {
    "B469": 5e-3,   # 无量纲灵敏度（待标定）
    "B470": 5e-3,
    "B471": 5e-3,
    "B472": 1e-9,   # RIU（缩放律精确，残差应为机器精度级）
}
_N_A = N_A


if __name__ == "__main__":
    print("=== B-38 PS-M8 几何半 + Q-scaling 自检 ===")
    try:
        # ---- B469/B470/B471：RQ golden vs FV-FD + 诚实梯度对照 ----
        print("\n--- 几何灵敏度（Rayleigh 商 golden vs FV-FD；诚实梯度：suspended ≫ strip ≈ thinwire ≈ slot）---")
        geos = [("strip", "基线 strip"), ("thinwire", "B469 thin-wire"),
                ("slot", "B470 slot"), ("suspended", "B471 suspended")]
        Sg, Sf = {}, {}
        for kind, label in geos:
            g = geometry_sensitivity_golden(kind)
            f = geometry_sensitivity_fd(kind)
            Sg[kind], Sf[kind] = g, f
            dd = abs(g - f)
            print("%-18s S_golden=%.6f  S_fd=%.6f  |Δ|=%.3e  %s"
                  % (label, g, f, dd, "OK" if dd < 1e-2 else "BAD"))
        # 诚实梯度：suspended 大幅增强（≫ strip）；薄条/狭缝 ≈ strip（不要求 > strip）
        ok_susp = Sg["suspended"] > Sg["strip"] * 1.5
        ok_flat = (abs(Sg["thinwire"] - Sg["strip"]) < 0.15
                   and abs(Sg["slot"] - Sg["strip"]) < 0.15)
        ok_grad = ok_susp and ok_flat
        print("梯度（suspended≫strip 且 thinwire/slot≈strip）:", "OK" if ok_grad else "BAD",
              "  strip=%.4f thinwire=%.4f slot=%.4f suspended=%.4f"
              % (Sg["strip"], Sg["thinwire"], Sg["slot"], Sg["suspended"]))

        # ---- B472：Q-scaling 闭式 vs 模型（电学受限区间 B472_NOISE）----
        print("\n--- B472 Q-scaling LOD（golden 闭式 vs 模型实算；电学受限区间）---")
        S, Q0 = 300.0, 1e4
        lod_seq = []
        for Q in (1e4, 5e4, 1e5, 2e5):
            gg = q_scaling_lod_golden(Q, Q0, S, noise=B472_NOISE)
            cc = q_scaling_lod_cand(Q, Q0, S, noise=B472_NOISE)
            lod_seq.append(cc)
            print("Q=%.0e  golden=%.6e  cand=%.6e  |Δ|=%.3e  %s"
                  % (Q, gg, cc, abs(gg - cc), "OK" if abs(gg - cc) < 1e-9 else "BAD"))
        # Q 增强单调性：Q↑ ⇒ LOD↓（电学受限下 Q 缩放可见）
        ok_mono = all(lod_seq[i + 1] < lod_seq[i] for i in range(len(lod_seq) - 1))
        print("Q 增强单调（Q↑⇒LOD↓）:", "OK" if ok_mono else "BAD",
              "  序列=%.3e→%.3e→%.3e→%.3e (Q:1e4→2e5)"
              % (lod_seq[0], lod_seq[1], lod_seq[2], lod_seq[3]))
        # 反向探针：热漂解耦（LOD_temp 不随 Q 变）——诚实披露 Q 缩放只在 referencing 下成立
        from lda_l2.ps_m2 import lod_real  # 惰性
        lt_q1 = lod_real(S, 1e4, 1.55, B472_NOISE)["LOD_temp_riu"]
        lt_q2 = lod_real(S, 2e5, 1.55, B472_NOISE)["LOD_temp_riu"]
        print("LOD_temp 与 Q 解耦（Q:1e4 vs 2e5 不变）:",
              "OK" if abs(lt_q1 - lt_q2) < 1e-15 else "BAD",
              "  LOD_temp=%.3e" % lt_q1)
    except Exception as exc:  # pragma: no cover
        print("自检需 scipy（FV 求解器）；在 scipy 环境下运行：", exc)
