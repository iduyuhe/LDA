# -*- coding: utf-8 -*-
"""网格瓦片化（tiling）· P6 · T6.3（U9）· 瓦片档位化 + **逐档重跑 D1/D2/P3 三预算**。

背景：全仓此前只有 `examples/budget_p3_tile_loss.py`（一个 **N_TILE=16 硬编码**的示例脚本），
**没有 tiling 库模块**。U9 的验收是「扩档 + 每档天花板随档更新、旧档数字不得复用」——
所以本模块把「瓦片档」变成**参数**，并让每一档**用自己的几何**重跑三条预算：

  · **D1** 总线传播损耗（随 N 增长）：`L_bus` 由真实 grid2d 分解几何给出
    （`clements_rect_decompose` + `_rect_column_assignment` ⇒ 与 `build_mesh_pnr` 的
    `x_max_um` 同源，本模块用后者并在 smoke 里用前者**独立复算**）。
  · **D2** 热串扰保真预算：`sigma_budget = 0.14/N`（与 D2 文档同式）；热串扰相移
    `dphi = 3·X(d_min)·π` 由**局部**几何（`d_min = rail_pitch`）决定 ⇒ 与 N 无关，
    而预算随 N 收缩 ⇒ **档间判定会翻转**（这是「必须逐档重跑」的第二个理由）。
  · **P3** tiling 损耗协同 + 定天花板：`IL_total(T) = T·IL_bus_tile + (T−1)·IL_link + T·IL_par`，
    `IL_link` 取**该档自己的** x 跨度、`IL_par` 取**该档自己的** GDS 寄生提取结果。

🔴 三处实测发现（本模块立项的直接依据，均由本轮实跑得到）：
  1. **示例脚本的线性律有偏**：`examples/budget_p3_tile_loss.py` 用 `L_BUS_PER_N_UM = 35.6`
     线性外推。实测 grid2d 真值：N=4 `38.833`、N=8 `36.082`、N=16 `35.070`、N=32 `34.798`（µm/N）
     ⇒ **每 N 母线长不是常数**，且 35.6·16 = 569.6 vs 真值 561.123（**+1.51%**）、
     35.6·4 = 142.4 vs 155.333（**−8.33%**）。⇒ 换档必须重算，「旧档数字不得复用」有实测依据。
  2. **两布局模式口径不一致（示例脚本混用）**：P3 的**损耗模型**取 grid2d 几何（L_bus=561.123），
     而其**瓦片 GDS/寄生**用 `build_mesh_pnr` **默认 serpentine** 布局（x_max=3981.541µm）⇒
     互连长度被**低估 7.0957×**、寄生电容取自另一个几何（3193.92 vs 457.59 fF，**6.98×**）。
     实测比值随 N 增长：`1.3224× / 3.1733× / 7.0957× / 15.0497×`（N=4/8/16/32）。
     ⇒ 本模块**强制单模式**（默认 `grid2d`），并把两模式差作为披露量输出。
  3. **本征 Q_i 与 R 无关**（`ring_adddrop.q_decomposition`：`Q_i = 2π·n_g/(λ·α_p)`，**单位长度**量）
     ⇒ 「小环弯曲损耗大 ⇒ Q_i 更低」这一直觉在**该模型下不成立**（R 相关版本见
     `ring_adddrop.bending_loss_db_per_cm(R)`）；本模块不据此宣称任何 R 依赖。

🔴 诚实边界（`TILING_DISCLOSURE`，逐键由 smoke 断言存在）：
  · 损耗/寄生/热耦合系数均为**设计预算常数**（`C_SUB_LOSS_DB_PER_FF = 1e-4` 为透明折算系数），
    **非 foundry 签核值**；本模块**无实测锚**。
  · 「瓦片」= 独立的 N×N Clments 网格，块间以**互连波导**级联 ⇒ tiling 损耗**高于**单一融合
    总线（不重复计 D1 单总线，如实）；块分解的酉等价性属 U5 范围，本模块不重复论证。
  · 热串扰模型是 `X(d) = c0·(d0/d)` 经验比（锚定 SOI MZI mesh 文献），**非第一性原理**；
    只算**最近邻**（同列 D-D + 内部邻），不含全局热传导解。
  · 寄生衬底泄漏**代理系数**（dB/fF）是几何级透明折算，**不是**光-电协同真值。
  · **不宣称**任何能效/带宽/良率；天花板是**损耗预算意义**上的可达 N 上界。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

# ---------------------------------------------------------------------------
# 档位与预算常数（与 `examples/budget_p3_tile_loss.py` / `budget_thermal_d2.py` 对齐：
# 同名常数取同值；本模块把「档」参数化，不改既有示例脚本）
# ---------------------------------------------------------------------------
#: 瓦片档位（N_TILE）。4/8/16/32 均已实测可跑（全档 build+寄生 <0.1s）。
TILE_TIERS: Tuple[int, ...] = (4, 8, 16, 32)
#: 布局模式（**强制单模式** —— 双模式混用是已实测的口径缺陷，见模块 docstring 发现 2）
LAYOUT_MODE_DEFAULT: str = "grid2d"
#: 瓦片间级联的 T 扫描（与示例脚本一致）
T_TABLE: Tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 128)
#: 轨道切换余量（D1 文档口径 `n_tap ≈ ⟨deg⟩·1.3`；本模块显式列为参数并披露）
RAIL_SWITCH_MARGIN: float = 1.3
#: 寄生衬底泄漏代理系数（dB/fF，几何级透明折算，非签核值）
C_SUB_LOSS_DB_PER_FF: float = 1e-4
#: 系统级代价阈值（与示例脚本一致）
EQUALIZER_RANGE_DB: float = 30.0
RECEIVER_MARGIN_DB: float = 20.0
#: D2 保真预算系数（与 `budget_thermal_d2.py` 同式：sigma_budget = 0.14/N）
D2_FIDELITY_COEF: float = 0.14
#: D2 热串扰模型（与 `budget_thermal_d2.py` 同参数）
D2_D0_UM: float = 10.0
D2_P_EXP: float = 1.0
#: D2 保守倍数（最坏受害者受 2 个 D-D 邻 + 1 个内部邻）
D2_WORST_MULT: float = 3.0
#: 三场景（α_prop dB/cm, α_tap dB/tap）—— 与 D1/P3 同源
SCENARIOS: Dict[str, Tuple[float, float]] = {
    "A": (1.0, 0.020),
    "B": (2.0, 0.050),
    "C": (3.0, 0.100),
}
#: D2 隔离场景（c0 = 受害者相移/aggressor 摆幅比）—— 与 `budget_thermal_d2.py` 同源
ISO_CASES: Dict[str, float] = {
    "no_iso_typ": 0.020,
    "no_iso_best": 0.010,
    "deep_tr": 0.002,
    "deep_tr_air": 0.001,
}

TILING_DISCLOSURE: Dict[str, str] = {
    "consts_are_budget": "损耗/寄生/热耦合系数均为**设计预算常数**（`C_SUB_LOSS_DB_PER_FF=1e-4` 是透明折算系数），**非 foundry 签核值**；本模块**无实测锚**。",
    "tiling_costlier": "瓦片 = 独立 N×N 网格 + 块间互连波导级联 ⇒ tiling 损耗**高于**单一融合总线（不重复计 D1 单总线，如实）；块分解的酉等价性属 U5，本模块不重复论证。",
    "thermal_empirical": "D2 热串扰用 `X(d)=c0·(d0/d)` **经验比**（锚定 SOI MZI mesh 文献），非第一性原理；只算最近邻（2×D-D + 1×内部），不含全局热传导解。",
    "parasitic_proxy": "寄生衬底泄漏是**几何级透明代理折算**（dB/fF），**不是**光-电协同真值；C_total 由 `parasitic_rc.estimate_parasitics` 对真实 GDS 提取。",
    "single_layout_mode": "🔴 **强制单布局模式**（默认 grid2d）：损耗几何、GDS、寄生必须同一模式。示例脚本混用两模式（损耗取 grid2d、GDS 取 serpentine）⇒ 互连长度低估 7.10×（N=16 实测）。两模式差由 `layout_mode_gap()` 输出。",
    "per_tier_recompute": "每档必须**用该档自己的几何**重跑 D1/D2/P3：实测「每 N 母线长」随档变化（38.833/36.082/35.070/34.798 µm/N @ N=4/8/16/32）⇒ 线性外推有偏（N=16 +1.51%、N=4 −8.33%）。`assert_no_tier_reuse()` 机器守护。",
    "no_perf_claim": "**不宣称**能效/带宽/良率；天花板是**损耗预算意义**上的可达 N 上界（`IL_total ≤ 阈值`）。",
    "qi_model_note": "`ring_adddrop.q_decomposition` 的 Q_i 是**单位长度**量 ⇒ **与 R 无关**；「小环弯曲损耗大」在本模型下不成立，R 相关版本见 `bending_loss_db_per_cm(R)`。本模块不据此宣称 R 依赖。",
    "link_uses_own_span": "块间互连长度取**该档自己的** x 跨度（grid2d 的 `x_max_um`），不是固定常数。",
    "ceiling_nearly_tier_free": "🔴 **N 上的损耗天花板几乎与档无关**（实测 N_tile=4/8/16/32 的 rx 天花板均为 256）：因 `IL ∝ N`、各档「每 N 系数」仅差 ~10% ⇒ 各档在同一 N 附近一起撞阈值。**故本模块不宣称「天花板随档更新」**（那在 N 上不成立）；真正随档变且单调的是**每 N 损耗** `IL_total(N)/N`（固定 N=512 实测随档递增）与 **D2 判定翻转**（N_tile=4 过、≥8 不过）。仅供「T 的粒度」与「IL 分解」逐档更新。",
}


class MeshTilingError(Exception):
    """输入/不变量违规。"""


# ---------------------------------------------------------------------------
# 1) 瓦片几何（**真实** P&R + GDS + 寄生，单模式）
# ---------------------------------------------------------------------------
def tile_geometry(N_tile: int, layout_mode: str = LAYOUT_MODE_DEFAULT,
                  rail_pitch: float = 4.0, ps_arm_um: float = 1000.0,
                  vpi_l_v_mm: float = 7.5) -> Dict[str, Any]:
    """构建该档瓦片（真实主权 P&R + GDS + 寄生提取），返回几何与寄生。

    返回 `x_max_um`（= D1 口径的总线长 L_bus）、`footprint_um2`、`n_cols`、`n_mzi`、
    `C_total_ff`、`R_series_ohm`、`layout_fidelity`、`drc_pass`、`lvs_verdict`。
    🔴 **同一 `layout_mode` 同时决定损耗几何与 GDS/寄生** ⇒ 无混用。
    """
    from lda_l2 import parasitic_rc
    from lda_l2.gds_export import parse_gds_polygons
    from lda_l2.mzi_mesh_matmul import dft_matrix
    from lda_layout.mesh_pnr import build_mesh_pnr

    if N_tile < 2:
        raise MeshTilingError("N_tile=%r 非法（须 >=2）" % (N_tile,))
    if layout_mode not in ("grid2d", "serpentine"):
        raise MeshTilingError("layout_mode=%r 非法（须 grid2d / serpentine）" % (layout_mode,))
    rep = build_mesh_pnr(dft_matrix(int(N_tile)), rail_pitch=rail_pitch,
                         layout_mode=layout_mode, ps_arm_um=ps_arm_um,
                         vpi_l_v_mm=vpi_l_v_mm)
    prc = parasitic_rc.estimate_parasitics(parse_gds_polygons(rep["gds_bytes"])["structures"])
    # 🆕 D-126：逐 rail 抽头数（deg）的分布 —— 「每模口径」所需。
    #   此前本模块只假设 ⟨deg⟩ = N−1（列/均值口径）⇒ 用 it 估天花板会**低估最坏模**。
    #   grid2d 实测：deg_min = N/2、deg_max = N、⟨deg⟩ = N−1（Σdeg = N(N−1)）。
    deg = [0] * int(N_tile)
    for (j, _t, _p, _c) in rep["ops"]:
        j = int(j)
        deg[j] += 1
        deg[j + 1] += 1
    return {
        "N_tile": int(N_tile),
        "layout_mode": layout_mode,
        "L_bus_um": float(rep["x_max_um"]),
        "bus_len_per_n_um": float(rep["x_max_um"]) / float(N_tile),
        "footprint_um2": float(rep["footprint_um2"]),
        "n_cols": int(rep["n_cols"]),
        "n_mzi": int(rep["n_mzi"]),
        "deg_min": int(min(deg)),
        "deg_max": int(max(deg)),
        "deg_span": int(max(deg) - min(deg)),
        "deg_mean": float(sum(deg)) / float(N_tile),
        "C_total_ff": float(prc["totals"]["C_total_ff"]),
        "R_series_ohm": float(prc["totals"]["R_series_ohm"]),
        "n_elements": int(prc["totals"]["n_elements"]),
        "layout_fidelity": float(rep["layout_fidelity"]),
        "drc_pass": bool(rep["drc_pass"]),
        "lvs_verdict": str(rep["lvs_verdict"]),
    }


def layout_mode_gap(N_tile: int, **kw: Any) -> Dict[str, Any]:
    """两布局模式的口径差（**披露量**，非判据）：serpentine / grid2d 的比值。

    实测（N=4/8/16/32）：面积比 `1.3224 / 3.1733 / 7.0957 / 15.0497`、
    x_max 比 `1.3224 / 3.1733 / 7.0957 / 15.0497`、C_total 比 `1.3164 / 3.1321 / 6.9799 / 14.7845`。
    """
    g = tile_geometry(N_tile, layout_mode="grid2d", **kw)
    s = tile_geometry(N_tile, layout_mode="serpentine", **kw)
    return {
        "N_tile": int(N_tile),
        "grid2d": g, "serpentine": s,
        "area_ratio_s_over_g": float(s["footprint_um2"] / g["footprint_um2"]),
        "xmax_ratio_s_over_g": float(s["L_bus_um"] / g["L_bus_um"]),
        "ctotal_ratio_s_over_g": float(s["C_total_ff"] / g["C_total_ff"]),
    }


# ---------------------------------------------------------------------------
# 2) D1 总线传播损耗（该档自己的几何）
# ---------------------------------------------------------------------------
def d1_bus_budget(N_tile: int, scenario: str = "B",
                  layout_mode: str = LAYOUT_MODE_DEFAULT,
                  rail_switch_margin: float = RAIL_SWITCH_MARGIN,
                  **kw: Any) -> Dict[str, Any]:
    """D1：该档瓦片的总线传播损耗（dB）与路径间损耗方差。

    `IL_full = α_prop·L_bus/1e4 + (⟨deg⟩·margin)·α_tap`（全宽路径，含轨切换余量）
    `IL_short = α_prop·col_pitch/1e4 + 1·α_tap`（相邻 I/O 最短路径）
    `IL_var = IL_full − IL_short`（**相位校准无法补偿的幅度失衡**）
    🔴 `⟨deg⟩ = N−1`（结构不变量：Σdeg = 2·n_mzi = N(N−1)）；`col_pitch` 由该档几何给。
    """
    if scenario not in SCENARIOS:
        raise MeshTilingError("scenario=%r 非法（须 ∈ %s）" % (scenario, sorted(SCENARIOS)))
    a_prop, a_tap = SCENARIOS[scenario]
    geo = tile_geometry(N_tile, layout_mode=layout_mode, **kw)
    N = int(N_tile)
    avg_deg = float(N - 1)                      # 结构不变量
    col_pitch = float(geo["L_bus_um"]) / max(int(geo["n_cols"]), 1)
    L_cm = geo["L_bus_um"] / 1e4
    col_cm = col_pitch / 1e4
    il_mean = a_prop * L_cm + avg_deg * a_tap
    il_full = a_prop * L_cm + (avg_deg * rail_switch_margin) * a_tap
    il_short = a_prop * col_cm + 1.0 * a_tap
    # 🆕 D-126：把「每模口径」登记进来 —— 此前本通道只有 mean（列/均值口径）。
    #   每模最坏 ⟺ deg_max（光子走挂门最多的那条 rail）；最好 ⟺ deg_min。
    #   🔴 本模型（`a_prop·L_cm + deg·a_tap`）**不含**每抽头波导绕行项
    #   ⇒ 与 `loss_aware_compile` 的总线端口模型相差 `deg·α_prop·(rail_pitch−gap)/1e4`
    #   （两个模块各自的模型选择，均已在各自披露中声明）。
    from lda_l2 import il_basis as _ILB
    geo_deg_min = int(geo.get("deg_min", 0))
    geo_deg_max = int(geo.get("deg_max", 0))
    if geo_deg_min < 1 or geo_deg_max < geo_deg_min:
        raise MeshTilingError("tile_geometry 未给出合法 deg_min/deg_max（%r/%r）"
                              % (geo_deg_min, geo_deg_max))
    il_min = a_prop * L_cm + geo_deg_min * a_tap
    il_max = a_prop * L_cm + geo_deg_max * a_tap
    basis = _ILB.il_basis_from_stats(
        il_min, il_mean, il_max, channel="tiling", n_modes=N,
        per_element_db=a_tap, per_element_kind="per_tap_db",
        basis_note="瓦片总线 IL：IL_k = α_prop·L_bus/1e4 + deg[k]·α_tap（本通道模型，**不含**每抽头波导绕行）；"
                   "每模最坏 = deg_max（grid2d = N）、最好 = deg_min（= N/2）、均值 = ⟨deg⟩ = N−1。")
    return {
        "N_tile": N, "scenario": scenario, "a_prop_db_cm": a_prop, "a_tap_db": a_tap,
        "layout_mode": geo["layout_mode"],
        "L_bus_um": float(geo["L_bus_um"]),
        "bus_len_per_n_um": float(geo["bus_len_per_n_um"]),
        "col_pitch_um": float(col_pitch),
        "avg_deg": avg_deg,
        "rail_switch_margin": float(rail_switch_margin),
        "IL_mean_db": float(il_mean),
        "IL_min_db": float(il_min),
        "IL_max_db": float(il_max),
        "IL_full_db": float(il_full),
        "IL_short_db": float(il_short),
        "IL_var_db": float(il_full - il_short),
        "il_basis_per_mode": basis,
        "geometry": geo,
    }


# ---------------------------------------------------------------------------
# 3) D2 热串扰保真预算（该档自己的 N）
# ---------------------------------------------------------------------------
def d2_thermal_budget(N_tile: int, iso_case: str = "deep_tr_air",
                      rail_pitch: float = 4.0) -> Dict[str, Any]:
    """D2：热串扰相移 vs 保真预算（该档自己的 N）。

    `sigma_budget = 0.14/N`（N² 单元随机游走，总保真 >0.99）
    `dphi_single = c0·(d0/d_min_DD)·π`、`dphi_worst = D2_WORST_MULT × dphi_single`
    （`d_min_DD = rail_pitch` ⇒ **与 N 无关**的局部几何 ⇒ 预算收缩而误差不变 ⇒ 档间会翻转）
    """
    if iso_case not in ISO_CASES:
        raise MeshTilingError("iso_case=%r 非法（须 ∈ %s）" % (iso_case, sorted(ISO_CASES)))
    if rail_pitch <= 0:
        raise MeshTilingError("rail_pitch 须 > 0")
    c0 = ISO_CASES[iso_case]
    x = c0 * (D2_D0_UM / float(rail_pitch)) ** D2_P_EXP
    budget = D2_FIDELITY_COEF / float(N_tile)
    dphi_single = x * math.pi
    dphi_worst = D2_WORST_MULT * dphi_single
    return {
        "N_tile": int(N_tile), "iso_case": iso_case, "c0": c0,
        "rail_pitch_um": float(rail_pitch),
        "sigma_budget_rad": float(budget),
        "x_ratio": float(x),
        "dphi_single_rad": float(dphi_single),
        "dphi_worst_rad": float(dphi_worst),
        "pass_single": bool(dphi_single < budget),
        "pass_worst": bool(dphi_worst < budget),
    }


# ---------------------------------------------------------------------------
# 4) P3 tiling 损耗协同 + 定天花板（该档自己的 IL_bus / IL_link / IL_par）
# ---------------------------------------------------------------------------
def p3_tiling_ceiling(N_tile: int, scenario: str = "B",
                      t_table: Sequence[int] = T_TABLE,
                      layout_mode: str = LAYOUT_MODE_DEFAULT,
                      c_sub_loss_db_per_ff: float = C_SUB_LOSS_DB_PER_FF,
                      eq_range_db: float = EQUALIZER_RANGE_DB,
                      rx_margin_db: float = RECEIVER_MARGIN_DB,
                      **kw: Any) -> Dict[str, Any]:
    """P3：`IL_total(T) = T·IL_bus_tile + (T−1)·IL_link + T·IL_par` ⇒ 逐 T 扫描 ⇒ 天花板。

    🔴 `IL_link` 用**该档自己的** x 跨度（不做常数）、`IL_par` 用**该档自己的** GDS 寄生。
    天花板 = 满足 `IL_total ≤ 阈值` 的最大 `N = N_tile·T`。
    """
    d1 = d1_bus_budget(N_tile, scenario=scenario, layout_mode=layout_mode, **kw)
    geo = d1["geometry"]
    a_prop = d1["a_prop_db_cm"]
    il_bus_tile = d1["IL_mean_db"]                             # 每瓦片内部（mean 口径）
    il_link = a_prop * (geo["L_bus_um"] / 1e4)                 # 每边界互连（该档 x 跨度）
    il_par_tile = c_sub_loss_db_per_ff * geo["C_total_ff"]      # 每瓦片寄生代理
    # 🆕 D-126：每模最坏口径的 per-tile 总线 IL（= 挂门最多的 rail）。
    #   本通道原用 `IL_mean_db`（列/均值口径）估天花板 ⇒ **低估最坏模**。
    il_bus_worst = float(d1["IL_max_db"])
    rows = []
    last_eq = last_rx = 0
    last_eq_pm = last_rx_pm = 0
    for T in t_table:
        if T < 1:
            raise MeshTilingError("t_table 元素须 >=1，收到 %r" % (T,))
        N = int(N_tile) * int(T)
        il_bus = il_bus_tile * T
        il_lnk = il_link * (T - 1)
        il_par = il_par_tile * T
        il_tot = il_bus + il_lnk + il_par
        # 每模最坏口径（同一 T 结构，只把 per-tile bus 换成最坏模读数）
        il_bus_pm = il_bus_worst * T
        il_tot_pm = il_bus_pm + il_lnk + il_par
        fe = bool(il_tot <= eq_range_db)
        fr = bool(il_tot <= rx_margin_db)
        fe_pm = bool(il_tot_pm <= eq_range_db)
        fr_pm = bool(il_tot_pm <= rx_margin_db)
        rows.append({"T": int(T), "N": N, "IL_bus_db": float(il_bus),
                     "IL_link_db": float(il_lnk), "IL_par_db": float(il_par),
                     "IL_total_db": float(il_tot), "feas_eq": fe, "feas_rx": fr,
                     "IL_bus_per_mode_db": float(il_bus_pm),
                     "IL_total_per_mode_db": float(il_tot_pm),
                     "feas_per_mode_eq": fe_pm, "feas_per_mode_rx": fr_pm})
        if fe:
            last_eq = N
        if fr:
            last_rx = N
        if fe_pm:
            last_eq_pm = N
        if fr_pm:
            last_rx_pm = N
    return {
        "N_tile": int(N_tile), "scenario": scenario, "layout_mode": geo["layout_mode"],
        "IL_bus_per_tile_db": float(il_bus_tile),
        "IL_bus_worst_per_tile_db": il_bus_worst,
        "IL_link_per_boundary_db": float(il_link),
        "IL_par_per_tile_db": float(il_par_tile),
        "eq_range_db": float(eq_range_db), "rx_margin_db": float(rx_margin_db),
        "rows": rows,
        "ceiling_eq_N": int(last_eq),
        "ceiling_rx_N": int(last_rx),
        "ceiling_per_mode_eq_N": int(last_eq_pm),
        "ceiling_per_mode_rx_N": int(last_rx_pm),
        "basis_note": "`IL_total_db`/`ceiling_*` = **列/均值口径**（per-tile 用 ⟨deg⟩=N−1）；"
                      "`IL_total_per_mode_db`/`ceiling_per_mode_*` = **每模最坏口径**"
                      "（per-tile 用 deg_max）⇒ 后者**更严**（天花板 ≤ 前者）。两者不可互换。",
        "a_prop_db_cm": a_prop, "a_tap_db": d1["a_tap_db"],
        "L_bus_um": float(geo["L_bus_um"]),
        "C_total_ff": float(geo["C_total_ff"]),
    }


# ---------------------------------------------------------------------------
# 5) 逐档规划 + 「旧档数字不得复用」机器守护
# ---------------------------------------------------------------------------
def _per_tier_constants(b: Dict[str, Any], scenarios: Sequence[str]) -> Tuple[float, ...]:
    """一档的「必须随档重算」常数指纹（用于档间互异/陈旧复用检查）。

    指纹覆盖**全部场景**的 (µm/N, IL_mean, P3 三项) ⇒ 任一场景出现陈旧复用都会被抓。
    """
    fp: List[float] = []
    for s in scenarios:
        fp += [
            round(float(b["d1"][s]["bus_len_per_n_um"]), 9),
            round(float(b["d1"][s]["IL_mean_db"]), 9),
            round(float(b["p3"][s]["IL_bus_per_tile_db"]), 9),
            round(float(b["p3"][s]["IL_link_per_boundary_db"]), 9),
            round(float(b["p3"][s]["IL_par_per_tile_db"]), 9),
        ]
    return tuple(fp)


def assert_no_tier_reuse(plan: Dict[str, Any]) -> None:
    """🔴 机器守护「**旧档数字不得复用**」：逐档常量指纹必须两两互异。

    若某两档指纹逐位相同 ⇒ 要么该档确实与另一档几何等价（则两档本就该合并，
    须显式声明而非静默复用），要么实现里出现了「取别档结果」的陈旧复用 —— 两者都必须 raise。
    """
    scenarios = list(plan["scenarios"])
    seen: Dict[Tuple[float, ...], int] = {}
    for b in plan["tiers"]:
        fp = _per_tier_constants(b, scenarios)
        if fp in seen:
            raise MeshTilingError(
                "档间常量指纹重复：N_tile=%d 与 N_tile=%d 逐位相同 ⇒ 疑似陈旧复用"
                "（每 N 母线长/IL 分解/D1 几何/P3 项必须随档重算）"
                % (b["N_tile"], seen[fp]))
        seen[fp] = b["N_tile"]


def il_per_n_at(N_tile: int, N_target: int, scenario: str = "B",
                layout_mode: str = LAYOUT_MODE_DEFAULT,
                t_table: Sequence[int] = T_TABLE, **kw: Any) -> Dict[str, Any]:
    """在**固定总规模** `N_target` 下的「每 N 损耗」(dB/N) —— 这是**真正随档变**的量。

    🔴 为何要看它：N 上的**天花板**几乎与档无关（损耗 ∝ N ⇒ 各档在同一 N 附近一起撞阈值），
    故「每档天花板随档更新」在 N 上**不成立**（如实登记，见披露键 `ceiling_nearly_tier_free`）。
    随档变的是**每 N 损耗**：`IL_total(N)/N`。要求 `N_target % N_tile == 0`（否则该档无法
    精确到达该 N ⇒ 返回 `reachable=False`，**不插值、不外推**）。
    """
    if N_target <= 0 or int(N_target) % int(N_tile) != 0:
        return {"N_tile": int(N_tile), "N_target": int(N_target),
                "reachable": False,
                "reason": "N_target=%d 不能被 N_tile=%d 整除（N = N_tile·T）"
                          % (N_target, N_tile)}
    T = int(N_target) // int(N_tile)
    p3 = p3_tiling_ceiling(N_tile, scenario=scenario, t_table=(T,),
                           layout_mode=layout_mode, **kw)
    row = p3["rows"][0]
    return {
        "N_tile": int(N_tile), "N_target": int(N_target), "T": int(T),
        "reachable": True,
        "IL_total_db": float(row["IL_total_db"]),
        "IL_per_N_db": float(row["IL_total_db"]) / float(N_target),
        "IL_bus_per_N_db": float(row["IL_bus_db"]) / float(N_target),
        "IL_link_per_N_db": float(row["IL_link_db"]) / float(N_target),
        "IL_par_per_N_db": float(row["IL_par_db"]) / float(N_target),
    }


def plan_tiling(tiers: Sequence[int] = TILE_TIERS,
                scenarios: Sequence[str] = ("A", "B", "C"),
                iso_case: str = "deep_tr_air",
                layout_mode: str = LAYOUT_MODE_DEFAULT,
                t_table: Sequence[int] = T_TABLE,
                n_target_fixed: int = 512) -> Dict[str, Any]:
    """逐档重跑 D1/D2/P3 三预算 ⇒ 汇总天花板表 + 档间互异自证。

    🔴 额外给出**固定总规模** `n_target_fixed` 下的「每 N 损耗」（真正随档变的量）。
    """
    out_tiers = []
    for N_tile in tiers:
        d1 = {s: d1_bus_budget(N_tile, scenario=s, layout_mode=layout_mode)
              for s in scenarios}
        d2 = d2_thermal_budget(N_tile, iso_case=iso_case)
        p3 = {s: p3_tiling_ceiling(N_tile, scenario=s, t_table=t_table,
                                   layout_mode=layout_mode) for s in scenarios}
        out_tiers.append({
            "N_tile": int(N_tile),
            "geometry": d1[scenarios[0]]["geometry"],
            "d1": {s: {k: v for k, v in d1[s].items() if k != "geometry"}
                   for s in scenarios},
            "d2": d2,
            "p3": {s: {k: v for k, v in p3[s].items() if k != "rows"}
                   for s in scenarios},
            "p3_rows": {s: p3[s]["rows"] for s in scenarios},
            "il_per_n_at_fixed_N": il_per_n_at(N_tile, n_target_fixed,
                                               scenario=scenarios[0],
                                               layout_mode=layout_mode),
        })
    ilpn = [b["il_per_n_at_fixed_N"] for b in out_tiers]
    reachable = [x for x in ilpn if x["reachable"]]
    monotone = all(reachable[i]["IL_per_N_db"] < reachable[i + 1]["IL_per_N_db"]
                   for i in range(len(reachable) - 1))
    plan = {
        "layout_mode": layout_mode,
        "tiers": out_tiers,
        "n_tiers": len(out_tiers),
        "tier_list": [int(x) for x in tiers],
        "scenarios": list(scenarios),
        "iso_case": iso_case,
        "n_target_fixed": int(n_target_fixed),
        "bus_len_per_n_by_tier": [round(float(b["d1"][scenarios[0]]["bus_len_per_n_um"]), 6)
                                  for b in out_tiers],
        "ceiling_rx_by_tier": [{s: b["p3"][s]["ceiling_rx_N"] for s in scenarios}
                               for b in out_tiers],
        "ceiling_eq_by_tier": [{s: b["p3"][s]["ceiling_eq_N"] for s in scenarios}
                               for b in out_tiers],
        "d2_pass_worst_by_tier": {b["N_tile"]: b["d2"]["pass_worst"] for b in out_tiers},
        "il_per_n_at_fixed_N_by_tier": {b["N_tile"]: b["il_per_n_at_fixed_N"]
                                        for b in out_tiers},
        # 🔴 真正随档变、且**单调**的量（判据锚在此，而非在「天花板必随档变」上）
        "il_per_n_monotone_increasing": bool(monotone),
        "il_per_n_values": [x["IL_per_N_db"] for x in reachable],
        "disclosure_keys": sorted(TILING_DISCLOSURE.keys()),
    }
    assert_no_tier_reuse(plan)
    plan["tier_reuse_guard"] = "PASS（逐档常量指纹两两互异）"
    return plan


if __name__ == "__main__":  # 自测：打真实数字
    print("=== 网格瓦片化（tiling）自测 · 逐档 D1/D2/P3 ===")
    print("%6s %11s %12s %10s %11s %11s %11s %9s %9s"
          % ("N_tile", "L_bus(µm)", "µm/N", "C_tot(fF)", "IL_bus/tile",
             "IL_link/bd", "IL_par/tile", "ceil_rx", "ceil_eq"))
    p = plan_tiling()
    for b in p["tiers"]:
        g = b["geometry"]
        p3 = b["p3"]["B"]
        print("%6d %11.3f %12.6f %10.4f %11.6f %11.6f %11.6f %9d %9d"
              % (b["N_tile"], g["L_bus_um"], g["bus_len_per_n_um"], g["C_total_ff"],
                 p3["IL_bus_per_tile_db"], p3["IL_link_per_boundary_db"],
                 p3["IL_par_per_tile_db"], p3["ceiling_rx_N"], p3["ceiling_eq_N"]))
    print("\n逐档 µm/N = %s ⇒ 档间互异=%s"
          % (p["bus_len_per_n_by_tier"], len(set(p["bus_len_per_n_by_tier"]))
             == len(p["bus_len_per_n_by_tier"])))
    print("D2 最保守判定（deep_tr_air）逐档 = %s" % p["d2_pass_worst_by_tier"])
    print("固定 N=%d 的每 N 损耗逐档 = %s（单调递增=%s）"
          % (p["n_target_fixed"],
             [round(v, 6) for v in p["il_per_n_values"]],
             p["il_per_n_monotone_increasing"]))
    print("\n两模式口径差（披露量）:")
    for N in (4, 16):
        gap = layout_mode_gap(N)
        print("  N=%-4d 面积比=%.4f× x_max 比=%.4f× C_total 比=%.4f×"
              % (N, gap["area_ratio_s_over_g"], gap["xmax_ratio_s_over_g"],
                 gap["ctotal_ratio_s_over_g"]))
    print("\n天花板（场景 A/B/C · rx≤20dB）逐档：")
    for b in p["tiers"]:
        print("  N_tile=%-3d %s" % (b["N_tile"], {
            s: b["p3"][s]["ceiling_rx_N"] for s in p["scenarios"]}))
