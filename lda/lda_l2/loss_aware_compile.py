# -*- coding: utf-8 -*-
"""U7 · 损耗感知编译（Loss-aware compilation）—— 把 D1 的保守损耗方差口径
升级为**可机器化证明的精确核算**，并回答「编译层能否降低 IL_var」。

背景（D1 → U7）
--------------
`D1_bus_loss_budget_2026-09-22.md` 给出 grid2d 直总线的路径损耗预算，其路径
方差口径为**保守上界**：

    IL_full  = alpha_prop*L_bus + <deg>*1.3*alpha_tap
    IL_short = alpha_prop*col_pitch + 1*alpha_tap      # D1 §二 「最短路径」
    IL_var   = IL_full - IL_short

D1 §五.3 自陈「方差口径保守……真实 std 小于此」，但未量化。

本模块做什么
------------
1. **几何事实（严格）**：grid2d 每根 rail 是 `gc_in(k) -> MZI... -> ps_out(k)
   -> gc_out(k)` 的水平直链，光自 x=mesh_x0 单调行进到 x=x_max =>
   **任意 I/O 对的波导长度 L_path >= L_bus = x_max - mesh_x0 > col_pitch**
   => D1 的 `IL_short = alpha_prop*col_pitch + alpha_tap` **物理不可实现**。
2. **精确模型**：每穿过一个 MZI 额外走 `rail_pitch - gap` 的竖直绕行 =>
   IL_path(io) = alpha_prop*[L_bus + n_tap*(rail_pitch-gap)]/1e4 + n_tap*alpha_tap
   => **IL 完全由 n_tap 决定**；n_tap 的可达范围由格点 DP 给出。
3. **真实方差**：直总线下 L_bus 项对**所有端口相同** => 对 IL_var **零贡献**；
   per-port IL_var 完全由 `deg`（每 rail 挂的 MZI 数）展布决定。实测
   `deg` 多集 = {N/2, N/2, N, ..., N}，对 U 的转置 / 共轭 / 反序 / 端口置换
   （共 10 种合法变换）**完全不变** => **编译层对 IL_var 的真实自由度为 0**
   （结构性不变量，非实现缺陷）。

诚实边界：见 `LOSS_AWARE_DISCLOSURE`。本模块**不跑 FDTD / 不做 3D / 不改 PDK 真值**，
也不宣称「给出了比 D1 更优的布局」——它把**不可实现的保守下界**换成**可实现的
物理下界**，属口径精确化，同一布局的物理量本身未变。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
#: `build_mesh_pnr` 的输入侧留白（µm）—— 与 `mesh_pnr.build_mesh_pnr` 同源。
MESH_X0_UM = 10.0
#: 轨距（µm）—— 与 `build_mesh_pnr(rail_pitch=...)` 默认同源。
RAIL_PITCH_DEFAULT = 4.0
#: 耦合间隙（µm）—— 与 `build_mesh_pnr(gap=...)` 默认同源。
GAP_DEFAULT = 0.3
#: 传播损耗代表值（dB/cm）—— D1 场景 B。
ALPHA_PROP_DEFAULT = 2.0
#: 每抽头耦合器插入损耗代表值（dB）—— D1 场景 B。
ALPHA_TAP_DEFAULT = 0.05
#: D1 §五.3 的保守「轨切换余量」倍率（仅用于复现 D1 口径，非物理量）。
D1_TAP_SWITCH_MARGIN = 1.3
#: 逐列自适应列宽的 margin（µm）—— 与 `build_mesh_pnr(Lc_margin=...)` 同源。
LC_MARGIN_DEFAULT = 6.0
#: 列间距余量（µm）—— 与 `build_mesh_pnr(col_gap=...)` 同源。
COL_GAP_DEFAULT = 8.0

#: 判定「保守上界」的最小高估倍率（物理最小 IL / D1 IL_short）—— N>=4 实测 >= 2.33。
MIN_INFEASIBLE_RATIO = 2.0

#: 披露键（smoke 须断言全部存在）。
LOSS_AWARE_DISCLOSURE: Dict[str, str] = {
    "scope": (
        "只做 grid2d 直总线的**被动插入损耗核算**（传播 + 每抽头耦合器）；"
        "不含弯曲/模场失配/偏振/温度漂移/热串扰，不含调制器与探测端预算。"
    ),
    "parameterized_not_measured": (
        "alpha_prop / alpha_tap 取公开区间代表值（SOI 1-3 dB/cm · 方向耦合器 "
        "0.05-0.1 dB）⇒ 全部结论是**参数化估算（L3）**，真值须 foundry PDK 圆片表征回填。"
    ),
    "physical_lower_bound_not_layout_gain": (
        "🔴 本模块的核心交付是把 D1 的 `IL_short`（col_pitch + 1 tap）这一**不可实现的"
        "下界**替换为**可实现的物理下界**（L_bus + n_tap*(rail_pitch-gap)）⇒ IL_var 数值"
        "下降属**口径精确化**，**不是**找到了更优布局。同一布局的物理量本身未变。"
    ),
    "compile_degree_of_freedom_is_zero": (
        "🔴 实测 `deg` 多集 = {N/2, N/2, N, ..., N}，对 U 的转置/共轭/反序/端口置换"
        "（10 种合法变换）**完全不变** ⇒ 在 grid2d 架构下，**编译层（分解选择 / 列分配 / "
        "端口映射）对 IL_var 的真实自由度为 0**；进一步降低 IL_var 只能靠 PDK"
        "（alpha_tap ↓，如绝热 MMI）或幅度均衡（见 amplitude_equalization_manifest）。"
    ),
    "varcol_reduces_mean_not_var": (
        "逐列自适应列宽（变长列）可真实降低总宽 L_bus（实测 4.9%-6.4%）⇒ 降 IL_mean；"
        "但**对 per-port IL_var 零贡献**（所有端口共享同一 L_bus）。"
    ),
    "dp_is_geometric_not_photonic": (
        "格点 DP 给出的是 n_tap 的**几何可达范围**（`[min deg, max deg]`），"
        "不是给定 U 的实际光子路径（实际分光由 theta 决定，是叠加态）；"
        "DP 值用于界定方差上下界，**不用于宣称某条路径的实测损耗**。"
    ),
    "no_fdtd_no_3d": (
        "不跑 FDTD、不做 3D 电磁、不重新签核（几何不变 => DRC/LVS 结论继承既有结果）。"
    ),
    "d1_doc_vs_manifest_io_margin": (
        "🔴 既有口径漂移：D1 **文档** §二 的 n_tap ≈ <deg>*1.3（含轨切换余量），而既有 "
        "`mesh_pnr.amplitude_equalization_manifest` 的实现用 <deg>*1（漏 1.3）⇒ 两者的 "
        "IL_var_io 相差 <deg>*0.3*alpha_tap。本模块默认采 **D1 文档口径**（更保守），并以 "
        "`manifest_io_comparison` 把差异机器化记录，**未修改既有实现**。"
    ),
    "honest_verdict_on_target": (
        "🔴 内部总结 §4.2 U7 的验收判据「同 N 下 IL_var 下降 >= 20%（相对当前列分配）」"
        "**在编译层不可达**（自由度为零，见上）⇒ 本模块**不声称达标**，"
        "只交付「精确核算 + 结构性零自由度证明 + 保守上界证伪」。"
    ),
}


class LossAwareCompileError(Exception):
    """损耗感知编译的域/契约错误（一律 raise，绝不静默截断或外推）。"""


# ---------------------------------------------------------------------------
# 1) 几何抽取（复用 build_mesh_pnr 的结果，不重复布局逻辑）
# ---------------------------------------------------------------------------
def rail_geometry(build_result: Dict[str, Any]) -> Dict[str, Any]:
    """从 `build_mesh_pnr` 结果抽取损耗核算所需的几何量。

    返回：N / ops(4-tuple) / n_cols / col_pitch_um / x_max_um / L_bus_um /
          deg(逐 rail 抽头数) / deg_min / deg_max / deg_span /
          col_mzis(逐列 MZI 的 rail 索引集合) / percol_mzi_count
    """
    if "ops" not in build_result or "x_max_um" not in build_result:
        raise LossAwareCompileError("build_result 缺少 ops / x_max_um（须来自 build_mesh_pnr）")
    N = int(build_result["N"])
    if N < 2:
        raise LossAwareCompileError("N=%d 非法（须 >= 2）" % N)
    ops = sorted((int(j), float(th), float(ph), int(c)) for (j, th, ph, c) in build_result["ops"])
    x_max = float(build_result["x_max_um"])
    col_pitch = float(build_result["pitch_um"])
    if col_pitch <= 0.0:
        raise LossAwareCompileError("col_pitch=%.6f 非法（须 > 0）" % col_pitch)

    deg = [0] * N
    col_mzis: Dict[int, List[int]] = {}
    for (j, _th, _ph, c) in ops:
        if not (0 <= j < N - 1):
            raise LossAwareCompileError("MZI 下轨索引 j=%d 越界（N=%d）" % (j, N))
        deg[j] += 1
        deg[j + 1] += 1
        col_mzis.setdefault(c, []).append(j)

    n_cols = len(col_mzis)
    L_bus = x_max - MESH_X0_UM
    if L_bus <= 0.0:
        raise LossAwareCompileError("L_bus=%.6f 非法（须 > 0）" % L_bus)
    return {
        "N": N,
        "ops": ops,
        "n_cols": n_cols,
        "col_pitch_um": col_pitch,
        "x_max_um": x_max,
        "L_bus_um": L_bus,
        "L_bus_over_col_pitch": L_bus / col_pitch,
        "deg": deg,
        "deg_min": min(deg),
        "deg_max": max(deg),
        "deg_span": max(deg) - min(deg),
        "deg_mean": sum(deg) / float(N),
        "col_mzis": {c: sorted(v) for c, v in sorted(col_mzis.items())},
        "n_mzi": len(ops),
    }


def path_length_um(n_tap: float, L_bus_um: float, rail_pitch: float = RAIL_PITCH_DEFAULT,
                   gap: float = GAP_DEFAULT) -> float:
    """穿过 `n_tap` 个 MZI 的路径波导长度（µm）。

    直段 L_bus + 每个 MZI 的竖直绕行 (rail_pitch - gap)（见 `_mzi_arm_polyline`：
    pinch 幅度 rail_pitch/2 - gap/2，上下各一次 ⇒ 竖直路程 = rail_pitch - gap）。
    """
    if n_tap < 0:
        raise LossAwareCompileError("n_tap=%.6f 非法（须 >= 0）" % n_tap)
    d_vert = rail_pitch - gap
    if d_vert < 0:
        raise LossAwareCompileError("rail_pitch=%.6f < gap=%.6f ⇒ 几何非法" % (rail_pitch, gap))
    return L_bus_um + n_tap * d_vert


def il_db(n_tap: float, L_bus_um: float, alpha_prop: float, alpha_tap: float,
          rail_pitch: float = RAIL_PITCH_DEFAULT, gap: float = GAP_DEFAULT) -> float:
    """被动插入损耗（dB）：传播项（dB/cm × µm/1e4）+ 抽头项（dB × 个数）。"""
    if alpha_prop < 0 or alpha_tap < 0:
        raise LossAwareCompileError("alpha_prop/alpha_tap 非法（须 >= 0）")
    return alpha_prop * path_length_um(n_tap, L_bus_um, rail_pitch, gap) / 1e4 + n_tap * alpha_tap


# ---------------------------------------------------------------------------
# 2) 逐路径 n_tap 的几何可达范围（格点 DP）
# ---------------------------------------------------------------------------
def ntap_reachable_range(ops: Sequence[Tuple[int, float, float, int]], N: int) -> Dict[str, Any]:
    """光在 rail×column 格点上右行，穿过 MZI 记 1 个抽头；返回 (min, max) n_tap。

    状态 = 「处理完第 c 列后位于 rail k」。转移：
      - 列 c 无 MZI 挂 rail k ⇒ 只能留在 k，代价 0（波导直穿）；
      - 列 c 有 MZI 挂 rail k ⇒ 必穿过该 MZI（代价 1），且**可选**留在 k（直通臂）
        或换到该 MZI 的另一条 rail（耦合臂）。
    起始 = 任意 rail（代价 0），终止 = 任意 rail。

    🔴 这是**几何可达**范围，不是给定 U 的实际光子路径（见披露 `dp_is_geometric_not_photonic`）。
    """
    if N < 2:
        raise LossAwareCompileError("N=%d 非法（须 >= 2）" % N)
    cols: Dict[int, set] = {}
    for (j, _th, _ph, c) in ops:
        j = int(j)
        c = int(c)
        if not (0 <= j < N - 1):
            raise LossAwareCompileError("MZI 下轨索引 j=%d 越界（N=%d）" % (j, N))
        cols.setdefault(c, set()).add(j)
    if not cols:
        raise LossAwareCompileError("ops 为空 ⇒ 无 MZI，无法核算")

    INF = float("inf")
    mn: List[float] = [0.0] * N
    mx: List[float] = [0.0] * N
    for c in sorted(cols):
        js = cols[c]
        has = [False] * N
        for j in js:
            has[j] = True
            has[j + 1] = True
        nmn: List[float] = [INF] * N
        nmx: List[float] = [-INF] * N
        for k in range(N):
            if mn[k] == INF:
                continue
            cost = 1.0 if has[k] else 0.0
            if mn[k] + cost < nmn[k]:
                nmn[k] = mn[k] + cost
            if mx[k] + cost > nmx[k]:
                nmx[k] = mx[k] + cost
            if (k in js) and (k + 1 < N):                    # MZI (k,k+1) ⇒ 可上跳
                if mn[k] + 1.0 < nmn[k + 1]:
                    nmn[k + 1] = mn[k] + 1.0
                if mx[k] + 1.0 > nmx[k + 1]:
                    nmx[k + 1] = mx[k] + 1.0
            if ((k - 1) in js) and (k - 1 >= 0):             # MZI (k-1,k) ⇒ 可下跳
                if mn[k] + 1.0 < nmn[k - 1]:
                    nmn[k - 1] = mn[k] + 1.0
                if mx[k] + 1.0 > nmx[k - 1]:
                    nmx[k - 1] = mx[k] + 1.0
        mn, mx = nmn, nmx
    lo = int(min(mn))
    hi = int(max(mx))
    return {
        "n_tap_min": lo,
        "n_tap_max": hi,
        "n_tap_span": hi - lo,
        "n_cols": len(cols),
        "note": "几何可达范围；与 deg_min/deg_max 的一致性由调用方用 rail_geometry 交叉核对",
    }


# ---------------------------------------------------------------------------
# 3) D1 保守口径（复现）+ 精确核算
# ---------------------------------------------------------------------------
def d1_conservative_io(build_result: Dict[str, Any],
                       pdk: Optional[Dict[str, Any]] = None,
                       tap_switch_margin: float = D1_TAP_SWITCH_MARGIN) -> Dict[str, Any]:
    """复现 D1 §二 的保守 io-pair 方差口径（**不重新实现 D1 的模型**，只按 D1 公式复算）。

    IL_full  = alpha_prop*L_bus/1e4 + <deg>*margin*alpha_tap     # margin=1.3（D1 §二 「轨切换余量」）
    IL_short = alpha_prop*col_pitch/1e4 + 1*alpha_tap
    IL_var   = IL_full - IL_short

    🔴 `tap_switch_margin` 显式参数化：D1 **文档** §二 写明 n_tap ≈ <deg>*1.3（含轨切换余量），
    而既有 `mesh_pnr.amplitude_equalization_manifest` 的 `IL_var_io` 实现里**漏掉了该 1.3**
    （用 `<deg>*1`）⇒ 两者口径不同。本函数默认复现 **D1 文档**口径；调用方传
    `tap_switch_margin=1.0` 即可复现 manifest 实现口径（见 `manifest_io_comparison`）。
    """
    pdk = dict(pdk or {})
    alpha_prop = float(pdk.get("alpha_prop_db_cm", ALPHA_PROP_DEFAULT))
    alpha_tap = float(pdk.get("alpha_tap_db", ALPHA_TAP_DEFAULT))
    if tap_switch_margin <= 0.0:
        raise LossAwareCompileError("tap_switch_margin=%.6f 非法（须 > 0）" % tap_switch_margin)
    geo = rail_geometry(build_result)
    L_bus = geo["L_bus_um"]
    col_pitch = geo["col_pitch_um"]
    IL_full = alpha_prop * L_bus / 1e4 + geo["deg_mean"] * tap_switch_margin * alpha_tap
    IL_short = alpha_prop * col_pitch / 1e4 + 1.0 * alpha_tap
    if IL_full <= IL_short:
        raise LossAwareCompileError(
            "D1 口径下 IL_full(%.6f) <= IL_short(%.6f) ⇒ 参数域异常" % (IL_full, IL_short))
    return {
        "IL_full_db": IL_full,
        "IL_short_db": IL_short,
        "IL_var_io_db": IL_full - IL_short,
        "alpha_prop_db_cm": alpha_prop,
        "alpha_tap_db": alpha_tap,
        "deg_mean": geo["deg_mean"],
        "tap_switch_margin": tap_switch_margin,
    }


def manifest_io_comparison(build_result: Dict[str, Any],
                           pdk: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """对照 **D1 文档口径（含 1.3 余量）** 与 **既有 manifest 实现口径（不含 1.3）**。

    🔴 这是一处**既有口径漂移**的机器化记录：`mesh_pnr.amplitude_equalization_manifest`
    的 docstring 自称「D1 保守 io_pair」，但其 `IL_full` 用 `deg_mean*alpha_tap`（无 1.3）
    ⇒ 其 `IL_var_io` 比 D1 文档口径**低** deg_mean*0.3*alpha_tap。本模块不改动既有实现，
    只把差异量化并披露。
    """
    doc_io = d1_conservative_io(build_result, pdk, D1_TAP_SWITCH_MARGIN)
    impl_io = d1_conservative_io(build_result, pdk, 1.0)
    return {
        "d1_doc_var_io_db": doc_io["IL_var_io_db"],
        "manifest_impl_var_io_db": impl_io["IL_var_io_db"],
        "gap_db": doc_io["IL_var_io_db"] - impl_io["IL_var_io_db"],
        "doc_tap_switch_margin": D1_TAP_SWITCH_MARGIN,
        "impl_tap_switch_margin": 1.0,
        "note": (
            "D1 文档 §二 含轨切换余量 1.3；既有 manifest 实现未含 ⇒ 两者 var_io 相差 "
            "<deg>*0.3*alpha_tap。本模块默认采用 **D1 文档口径**（更保守）。"
        ),
    }


def il_per_port_direct_bus(build_result: Dict[str, Any],
                           pdk: Optional[Dict[str, Any]] = None,
                           rail_pitch: float = RAIL_PITCH_DEFAULT,
                           gap: float = GAP_DEFAULT) -> Dict[str, Any]:
    """直总线**精确**逐端口 IL（可实现的物理下界模型）。

    IL_k = alpha_prop*[L_bus + deg[k]*(rail_pitch-gap)]/1e4 + deg[k]*alpha_tap
    ⇒ IL_var_ports = (deg_max - deg_min) * dIL_per_tap，
      dIL_per_tap = alpha_prop*(rail_pitch-gap)/1e4 + alpha_tap
    """
    pdk = dict(pdk or {})
    alpha_prop = float(pdk.get("alpha_prop_db_cm", ALPHA_PROP_DEFAULT))
    alpha_tap = float(pdk.get("alpha_tap_db", ALPHA_TAP_DEFAULT))
    geo = rail_geometry(build_result)
    L_bus = geo["L_bus_um"]
    d_vert = rail_pitch - gap
    if d_vert < 0:
        raise LossAwareCompileError("rail_pitch=%.6f < gap=%.6f ⇒ 几何非法" % (rail_pitch, gap))
    dil = alpha_prop * d_vert / 1e4 + alpha_tap
    per_port = []
    ils = []
    for k, n in enumerate(geo["deg"]):
        Lp = path_length_um(n, L_bus, rail_pitch, gap)
        il = alpha_prop * Lp / 1e4 + n * alpha_tap
        ils.append(il)
        per_port.append({"port": k, "n_tap": n, "L_path_um": Lp, "IL_db": il,
                         "IL_linear": 10.0 ** (-il / 10.0)})
    var = max(ils) - min(ils)
    var_closed = geo["deg_span"] * dil
    if abs(var - var_closed) > 1e-9 * max(1.0, abs(var_closed)):
        raise LossAwareCompileError(
            "逐端口 IL 方差(%.12g) != 闭式 (deg_span*dIL_per_tap=%.12g) ⇒ 模型不自洽"
            % (var, var_closed))
    return {
        "IL_mean_db": sum(ils) / len(ils),
        "IL_var_ports_db": var,
        "IL_var_ports_closed_form_db": var_closed,
        "dIL_per_tap_db": dil,
        "L_bus_um": L_bus,
        "rail_pitch_um": rail_pitch,
        "gap_um": gap,
        "d_vert_um": d_vert,
        "deg_min": geo["deg_min"],
        "deg_max": geo["deg_max"],
        "deg_span": geo["deg_span"],
        "alpha_prop_db_cm": alpha_prop,
        "alpha_tap_db": alpha_tap,
        "per_port": per_port,
    }


# ---------------------------------------------------------------------------
# 4) 保守上界的机器化证伪
# ---------------------------------------------------------------------------
def refute_short_path_infeasible(build_result: Dict[str, Any],
                                 pdk: Optional[Dict[str, Any]] = None,
                                 rail_pitch: float = RAIL_PITCH_DEFAULT,
                                 gap: float = GAP_DEFAULT) -> Dict[str, Any]:
    """机器化证明 D1 的 `IL_short` 物理不可实现。

    论据（两条，均为严格不等式）：
      ① 几何：任意 I/O 对的 L_path >= L_bus > col_pitch（光必须横穿全宽且单调向右）；
      ② 抽头：任意路径至少穿过 `deg_min` 个 MZI（光至少在一条 rail 上走完其全部 MZI）。
    ⇒ 物理最小 IL = alpha_prop*(L_bus + deg_min*(rail_pitch-gap))/1e4 + deg_min*alpha_tap
    ⇒ 若 `物理最小 IL / D1 IL_short >= MIN_INFEASIBLE_RATIO`，则 D1 的 IL_short 不可达。
    """
    d1 = d1_conservative_io(build_result, pdk)
    exact = il_per_port_direct_bus(build_result, pdk, rail_pitch, gap)
    geo = rail_geometry(build_result)
    alpha_prop = d1["alpha_prop_db_cm"]
    alpha_tap = d1["alpha_tap_db"]

    il_short_d1 = d1["IL_short_db"]
    il_min_phys = alpha_prop * path_length_um(geo["deg_min"], geo["L_bus_um"],
                                              rail_pitch, gap) / 1e4 + geo["deg_min"] * alpha_tap
    ratio = il_min_phys / il_short_d1 if il_short_d1 > 0 else float("inf")
    L_ok = geo["L_bus_um"] > geo["col_pitch_um"]
    return {
        "IL_short_d1_db": il_short_d1,
        "IL_min_physical_db": il_min_phys,
        "infeasible_ratio": ratio,
        "short_path_infeasible": bool(ratio >= MIN_INFEASIBLE_RATIO),
        "L_bus_gt_col_pitch": bool(L_ok),
        "L_bus_um": geo["L_bus_um"],
        "col_pitch_um": geo["col_pitch_um"],
        "min_infeasible_ratio_required": MIN_INFEASIBLE_RATIO,
        "var_ratio_io_over_exact": d1["IL_var_io_db"] / exact["IL_var_ports_db"],
        "d1_var_io_db": d1["IL_var_io_db"],
        "exact_var_ports_db": exact["IL_var_ports_db"],
        "honest_note": (
            "D1 的 IL_short（col_pitch + 1 tap）在 grid2d 直总线中**不可实现**；"
            "infeasible_ratio 随 N 增长（实测 N=4/8/16 => 2.33/4.59/9.12）。"
        ),
    }


def conservative_overestimate(build_result: Dict[str, Any],
                              pdk: Optional[Dict[str, Any]] = None,
                              rail_pitch: float = RAIL_PITCH_DEFAULT,
                              gap: float = GAP_DEFAULT) -> Dict[str, Any]:
    """量化「D1 保守口径 / 精确物理口径」的高估倍率与下降率。"""
    d1 = d1_conservative_io(build_result, pdk)
    exact = il_per_port_direct_bus(build_result, pdk, rail_pitch, gap)
    var_io = d1["IL_var_io_db"]
    var_ex = exact["IL_var_ports_db"]
    if var_ex <= 0:
        raise LossAwareCompileError("精确 IL_var=%.6g <= 0 ⇒ 无法计算倍率" % var_ex)
    ratio = var_io / var_ex
    return {
        "d1_var_io_db": var_io,
        "exact_var_ports_db": var_ex,
        "overestimate_x": ratio,
        "reduction_ratio": 1.0 - var_ex / var_io,
        "overestimate_ge_20pct": bool((1.0 - var_ex / var_io) >= 0.20),
    }


# ---------------------------------------------------------------------------
# 5) 结构性不变量：deg 多集对合法变换不变
# ---------------------------------------------------------------------------
def _deg_multiset(ops: Sequence[Tuple[int, float, float, int]], N: int) -> Tuple[int, ...]:
    deg = [0] * N
    for row in ops:                     # bs_list 是 3-tuple (j, theta, phi)；ops 是 4-tuple
        j = int(row[0])
        if not (0 <= j < N - 1):
            raise LossAwareCompileError("MZI 下轨索引 j=%d 越界（N=%d）" % (j, N))
        deg[j] += 1
        deg[j + 1] += 1
    return tuple(sorted(deg))


def deg_multiset_invariance(U: Any, port_perm: Optional[Sequence[int]] = None) -> Dict[str, Any]:
    """实测 `deg` 多集在 10 种合法变换下是否不变。

    变体：U / U.T / U.conj() / U.conj().T / U[::-1,::-1] / U[::-1,:] / U[:,::-1]
          / P U P^T / P U / U P（P = 端口置换，缺省用反转置换，可由调用方给出）。
    """
    import numpy as np
    from lda_layout.mesh_pnr import clements_rect_decompose

    A = np.array(U, dtype=complex)
    N = A.shape[0]
    if port_perm is None:
        perm = list(range(N))[::-1]
    else:
        perm = list(port_perm)
        if sorted(perm) != list(range(N)):
            raise LossAwareCompileError("port_perm 非 0..N-1 的一个排列：%s" % (perm,))
    P = np.zeros((N, N), dtype=complex)
    for a, b in enumerate(perm):
        P[a, b] = 1.0

    variants = {
        "U": A,
        "U.T": A.T,
        "U.conj()": A.conj(),
        "U.conj().T": A.conj().T,
        "U[::-1,::-1]": A[::-1, ::-1],
        "U[::-1,:]": A[::-1, :],
        "U[:,::-1]": A[:, ::-1],
        "P U P^T": P @ A @ P.T,
        "P U": P @ A,
        "U P": A @ P,
    }
    rows: List[Dict[str, Any]] = []
    multisets = []
    for name, V in variants.items():
        ops, _D = clements_rect_decompose(V)
        ms = _deg_multiset(ops, N)
        multisets.append(ms)
        rows.append({"variant": name, "deg_multiset": list(ms),
                     "deg_min": ms[0], "deg_max": ms[-1], "span": ms[-1] - ms[0]})
    invariant = all(ms == multisets[0] for ms in multisets)
    return {
        "N": N,
        "n_variants": len(variants),
        "invariant": bool(invariant),
        "deg_multiset": list(multisets[0]),
        "deg_min": multisets[0][0],
        "deg_max": multisets[0][-1],
        "span": multisets[0][-1] - multisets[0][0],
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# 6) 逐列自适应列宽（变长列）—— 真实降 L_bus（但只降 IL_mean）
# ---------------------------------------------------------------------------
def percol_adaptive_width(build_result: Dict[str, Any],
                          lc_margin: float = LC_MARGIN_DEFAULT,
                          col_gap: float = COL_GAP_DEFAULT) -> Dict[str, Any]:
    """逐列自适应列宽：列宽 = 该列最长 MZI 的 Lu + col_gap（而非全局 Lu_max + col_gap）。

    真实降低总宽 => 降 L_bus => 降 IL_mean；**对 IL_var 零贡献**（见披露）。
    """
    from lda_layout.mesh_pnr import coupler_length_from_theta

    geo = rail_geometry(build_result)
    if "layout_mode" in build_result and build_result["layout_mode"] != "grid2d":
        raise LossAwareCompileError(
            "变长列仅对 grid2d 布局有意义（当前 layout_mode=%r）" % build_result["layout_mode"])
    per_col_lu: Dict[int, float] = {}
    for (j, th, _ph, c) in geo["ops"]:
        Lc = coupler_length_from_theta(2.0 * th)
        Lu = Lc + 2.0 * lc_margin
        if c not in per_col_lu or Lu > per_col_lu[c]:
            per_col_lu[c] = Lu
    n_cols = len(per_col_lu)
    width_fixed = n_cols * (geo["col_pitch_um"])          # 现状：全局 Lu_max + col_gap
    width_varcol = sum(per_col_lu[c] + col_gap for c in sorted(per_col_lu))
    if width_varcol <= 0:
        raise LossAwareCompileError("变长列总宽=%.6f 非法" % width_varcol)
    return {
        "n_cols": n_cols,
        "per_col_lu_um": {c: per_col_lu[c] for c in sorted(per_col_lu)},
        "lu_max_um": max(per_col_lu.values()),
        "width_fixed_um": width_fixed,
        "width_varcol_um": width_varcol,
        "ratio": width_varcol / width_fixed,
        "L_bus_reduction_ratio": 1.0 - width_varcol / width_fixed,
        "l_bus_saving_ge_4pct": bool((1.0 - width_varcol / width_fixed) >= 0.04),
        "affects_il_var": False,
        "honest_note": "变长列降 L_bus（⇒ IL_mean），但 per-port IL_var 不变（共享 L_bus 项抵消）。",
    }


# ---------------------------------------------------------------------------
# 7) 面积-损耗权衡曲线
# ---------------------------------------------------------------------------
def area_loss_tradeoff(build_result: Dict[str, Any],
                       pdk: Optional[Dict[str, Any]] = None,
                       rail_pitch: float = RAIL_PITCH_DEFAULT,
                       gap: float = GAP_DEFAULT,
                       lc_margin: float = LC_MARGIN_DEFAULT,
                       col_gap: float = COL_GAP_DEFAULT) -> Dict[str, Any]:
    """给出「总宽(footprint 一维) vs IL_mean / IL_var」的两个布局点与结论。

    点 A = 现状（统一 col_pitch）· 点 B = 逐列自适应列宽。
    🔴 结论：IL_var 两点**相同**（结构性），IL_mean 在 B 点更低 ⇒ 权衡只存在于 IL_mean。
    """
    pdk = dict(pdk or {})
    alpha_prop = float(pdk.get("alpha_prop_db_cm", ALPHA_PROP_DEFAULT))
    alpha_tap = float(pdk.get("alpha_tap_db", ALPHA_TAP_DEFAULT))
    geo = rail_geometry(build_result)
    vw = percol_adaptive_width(build_result, lc_margin, col_gap)
    N = geo["N"]
    pts = []
    for tag, width in (("A_uniform", vw["width_fixed_um"]), ("B_varcol", vw["width_varcol_um"])):
        L_bus = width                                     # 总宽即 x 方向跨度
        ils = [alpha_prop * path_length_um(n, L_bus, rail_pitch, gap) / 1e4 + n * alpha_tap
               for n in geo["deg"]]
        pts.append({
            "tag": tag,
            "x_span_um": width,
            "IL_mean_db": sum(ils) / len(ils),
            "IL_var_db": max(ils) - min(ils),
        })
    var_equal = abs(pts[0]["IL_var_db"] - pts[1]["IL_var_db"]) < 1e-12
    return {
        "N": N,
        "points": pts,
        "il_var_identical": bool(var_equal),
        "il_mean_delta_db": pts[1]["IL_mean_db"] - pts[0]["IL_mean_db"],
        "width_reduction_ratio": 1.0 - pts[1]["x_span_um"] / pts[0]["x_span_um"],
        "honest_note": (
            "面积-损耗权衡**不涉及 IL_var**（两点相同）；变长列只买 IL_mean 的下降。"
            "若目标是 IL_var，唯一杠杆是 PDK（alpha_tap↓）或幅度均衡。"
        ),
    }


# ---------------------------------------------------------------------------
# 8) 汇总报告
# ---------------------------------------------------------------------------
def loss_aware_compile_report(build_result: Dict[str, Any],
                              pdk: Optional[Dict[str, Any]] = None,
                              U: Any = None,
                              rail_pitch: float = RAIL_PITCH_DEFAULT,
                              gap: float = GAP_DEFAULT) -> Dict[str, Any]:
    """U7 汇总：几何 / DP 可达 / 精确核算 / 保守证伪 / 零自由度 / 权衡。"""
    geo = rail_geometry(build_result)
    dp = ntap_reachable_range(geo["ops"], geo["N"])
    d1 = d1_conservative_io(build_result, pdk)
    exact = il_per_port_direct_bus(build_result, pdk, rail_pitch, gap)
    ref = refute_short_path_infeasible(build_result, pdk, rail_pitch, gap)
    over = conservative_overestimate(build_result, pdk, rail_pitch, gap)
    man_cmp = manifest_io_comparison(build_result, pdk)
    trade = area_loss_tradeoff(build_result, pdk, rail_pitch, gap)
    dp_consistent = (dp["n_tap_min"] == geo["deg_min"]) and (dp["n_tap_max"] == geo["deg_max"])
    inv = deg_multiset_invariance(U) if U is not None else None
    return {
        "N": geo["N"],
        "geometry": {
            "n_cols": geo["n_cols"], "n_mzi": geo["n_mzi"],
            "col_pitch_um": geo["col_pitch_um"], "L_bus_um": geo["L_bus_um"],
            "L_bus_over_col_pitch": geo["L_bus_over_col_pitch"],
            "deg": geo["deg"], "deg_min": geo["deg_min"], "deg_max": geo["deg_max"],
            "deg_span": geo["deg_span"], "deg_mean": geo["deg_mean"],
        },
        "dp": dp,
        "dp_consistent_with_deg": bool(dp_consistent),
        "d1_conservative": d1,
        "exact": exact,
        "refutation": ref,
        "overestimate": over,
        "manifest_io_comparison": man_cmp,
        "deg_invariance": inv,
        "tradeoff": trade,
        "compile_dof": {
            "deg_multiset_invariant": (bool(inv["invariant"]) if inv is not None else None),
            "real_dof_for_il_var": 0,
            "reason": "deg 多集为分解结构不变量；L_bus 项对所有端口相同 ⇒ 对 IL_var 零贡献",
        },
        "disclosure": LOSS_AWARE_DISCLOSURE,
    }


# ---------------------------------------------------------------------------
# 自测（判据由 run_loss_aware_compile_smoke.py 常驻守护）
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np
    from lda_layout.mesh_pnr import build_mesh_pnr

    PDK = {"alpha_prop_db_cm": ALPHA_PROP_DEFAULT, "alpha_tap_db": ALPHA_TAP_DEFAULT}
    for N in (4, 8, 16):
        U = np.fft.fft(np.eye(N)).astype(complex) / math.sqrt(N)
        br = build_mesh_pnr(U, rail_pitch=RAIL_PITCH_DEFAULT, layout_mode="grid2d")
        rep = loss_aware_compile_report(br, PDK, U=U)
        print("--- N=%d ---" % N)
        print("  deg=%s span=%d  L_bus=%.2f col_pitch=%.2f ratio=%.2f"
              % (rep["geometry"]["deg"], rep["geometry"]["deg_span"],
                 rep["geometry"]["L_bus_um"], rep["geometry"]["col_pitch_um"],
                 rep["geometry"]["L_bus_over_col_pitch"]))
        print("  DP n_tap=[%d,%d] consistent=%s"
              % (rep["dp"]["n_tap_min"], rep["dp"]["n_tap_max"], rep["dp_consistent_with_deg"]))
        print("  D1 var_io=%.6f  exact var=%.6f  over=%.4fx  reduction=%.2f%%"
              % (rep["d1_conservative"]["IL_var_io_db"], rep["exact"]["IL_var_ports_db"],
                 rep["overestimate"]["overestimate_x"],
                 100.0 * rep["overestimate"]["reduction_ratio"]))
        print("  IL_short infeasible=%s ratio=%.3f  L_bus>col_pitch=%s"
              % (rep["refutation"]["short_path_infeasible"],
                 rep["refutation"]["infeasible_ratio"],
                 rep["refutation"]["L_bus_gt_col_pitch"]))
        print("  var_io: D1文档=%.6f  manifest实现=%.6f  gap=%.6f"
              % (rep["manifest_io_comparison"]["d1_doc_var_io_db"],
                 rep["manifest_io_comparison"]["manifest_impl_var_io_db"],
                 rep["manifest_io_comparison"]["gap_db"]))
        print("  deg invariant=%s (%d variants)"
              % (rep["deg_invariance"]["invariant"], rep["deg_invariance"]["n_variants"]))
        print("  varcol L_bus 降 %.2f%%  IL_var 相同=%s"
              % (100.0 * rep["tradeoff"]["width_reduction_ratio"],
                 rep["tradeoff"]["il_var_identical"]))
