"""D-123 · 真实损耗预算（M5 延伸）——**把「每模光学深度」接进 dB 账**。

════════════════════════════════════════════════════════════════════════════
问题（承接 M5 的落点）
────────────────────────────────────────────────────────────────────────────
M5（D-122）坐实了「矩形 Clements 网格深度 = 紧界 N 可达」，把**层数**从三角
Reck 的 2N−3 减到 N。但层数只是**结构性**数字；光子真正吃掉的损耗，取决于它对
每一模而言**实际穿过多少片 2 模门（分束器）** —— 即**每模光学深度**。

🔴 **本模块的第一件事是把两个口径显式分开**（这是最容易混、也最容易出错的地方）：

  · **列口径**（D-120 `mesh_scaling_laws.n_stages = N−1`）：网格的**列数/阶段数**。
    对 `reck_decompose`（抽象 Givens，非相邻耦合，需波导交叉）而言，它**恰好等于**
    每模深度 N−1（本模块构造实测，见 `abstract_reck_optical_depth`）。
  · **每模口径**（本模块引入）：平台**邻耦合三角网格** `reck_triangular_mesh`
    （M1/M2 实测 0 交叉）的每模深度实测为 **2N−3**，**不是** N−1 ——
    因为同一「列」内的相邻对有**共享模**（是一条链，不是匹配）。

⇒ D-120 的 `loss_per_path = (N−1)·per_mzi` 是**列口径**；把它当成邻耦合三角网格的
  真实每模损耗会**低估约 2 倍**。本模块给出每模口径的正确账。

════════════════════════════════════════════════════════════════════════════
三条可机器判定的结论（实测见 `run_selfchecks`）
────────────────────────────────────────────────────────────────────────────
  ★ 结论 1（每模深度：三角 2N−3 / 矩形 N）
    · 三角 Reck（邻耦合，0 交叉）：每模深度 ∈ [1, 2N−3]  ⇒ 最坏模付 (2N−3)·per
    · 矩形 Clements（M5）：每模深度 ∈ [⌊N/2⌋, N]      ⇒ 最坏模付 N·per
    ⇒ **矩形化不只省层数，也把最坏模损耗减半**（N=216：1029.6 → 518.4 dB，省 511.2）。

  ★ 结论 2（M5 的收益在「真实 dB 账」上兑现）
    元件数**不变**（两种网格同为 N(N−1)/2，Clements 必要性定理）⇒ 收益纯在
    **每模光学深度** ⇒ 直接兑现为损耗。矩形化的损耗收益 = (N−3)·per_mzi。

  ★ 结论 3（时间复用：通用仍不省损，但**浅电路**才越墙 —— D-121 结论 2/3 在可达基线上重述）
    · 通用（按 M5 的**可达**调度 N，而非不可达的 N−1）：每模损耗 = N·per_step
      ⇒ 比矩形静态 N·per_mzi **多 N·DELAY = 0.2N dB**（环/开关/延迟）⇒ 通用不省损。
    · 但时间复用（矩形调度）**优于三角静态**（N·per_step < (2N−3)·per_mzi）——
      因为它继承了矩形化的深度收益。
    · **浅电路**（深度 D < N，放弃通用性）才真正越墙：N=216, D=32 ⇒ 83.2 dB
      （比矩形通用静态省 435.2 dB），但可及参数 ⌊N/2⌋·D = 3456 ≪ N(N−1)/2 = 23220
      ⇒ **维度计数判非通用**（与 D-121 的 Borealis 判死同法）。

════════════════════════════════════════════════════════════════════════════
🔴 诚实边界（必读）
  · 损耗为**设计预算口径**（`per_mzi` 复用 D-120 的 2.4 dB 同源常数；每步延迟/开关
    0.2 dB 复用 D-121），**非实测 PDK**（属 D5 外部依赖）。
  · 本账**不含波导交叉损耗**（`crossing_loss_included=False`）：三角网格已由 M2 主权
    P&R 实测 0 交叉；矩形网格的交叉数需 P&R 几何确定（属 P1-B）。本模块给出
    **交叉敏感性**（`crossing_breakeven_*`）：矩形要抹平 511.2 dB 的优势需 ≈1.0e4 个
    交叉/模（远超任何平面版图量级）⇒ 该缺口**不改变**任何结论。
  · 「每模深度」由**构造实测**（跑分解数门数）给出，并附闭式核对；非仿真、非拟合。

════════════════════════════════════════════════════════════════════════════
红线自检标注：
- C 级自主：纯 numpy + 平台模块（lda_l2 / lda_qeda / lda_layout 主权分解），零量子 SDK。
- LLM 不进判决路径：深度为 int、损耗为 float（10^(−dB/10) 闭式）、判决为 bool（死标量）。
- 数学锚（闭式，非拟合非仿真）：2N−3 · N−1 · ⌊N/2⌋ · N · 10^(−dB/10) · ⌈n_mzi/⌊N/2⌋⌉。
════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import math
from collections import OrderedDict

from lda_l2 import mzi_mesh_matmul as MMM
from lda_qeda import scale_bench as SBM
from lda_qeda import temporal_mesh as TMB

__all__ = [
    "PER_MZI_LOSS_DB",
    "DELAY_LOSS_DB",
    "PER_STEP_LOSS_DB",
    "CROSSING_LOSS_DB",
    "abstract_reck_optical_depth",
    "triangular_optical_depth",
    "rectangular_optical_depth",
    "optical_depth_profile",
    "column_basis_loss",
    "static_mesh_loss_budget",
    "temporal_universal_loss_budget",
    "temporal_shallow_loss_budget",
    "universality_loss_floor",
    "loss_account_table",
    "equal_loss_frontier",
    "crossing_breakeven",
    "loss_wall_n_per_mode",
    "loss_budget_verdict",
    "run_selfchecks",
    "RED_LINE_DISCLOSURE",
]

# ---------------------------------------------------------------------------
# 损耗常数（设计与 D-120 / D-121 同源，非实测 golden）
# ---------------------------------------------------------------------------
PER_MZI_LOSS_DB = float(SBM.PER_MZI_LOSS_DB)          # 2.4 dB = 2·DC + 2·PS + 波导段
DELAY_LOSS_DB = float(TMB.DELAY_LOSS_DB)              # 0.20 dB（每步环/延迟/开关）
PER_STEP_LOSS_DB = float(TMB.PER_ROUNDTRIP_LOSS_DB)   # 2.6 dB = 单片 MZI + 每步延迟
CROSSING_LOSS_DB = float(MMM.CROSSING_LOSS_DB)        # 0.05 dB（仅用于敏感性披露）


def _eta(loss_db: float) -> float:
    """透射率闭式：η = 10^(−dB/10)。"""
    return float(10.0 ** (-float(loss_db) / 10.0))


def _guard_n(n_modes) -> int:
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    return n


def _per_mode_counts(ops, n: int, pairs) -> list:
    """数每个模各穿过多少片门。`pairs` 从每片 op 抽出 (低模, 高模)。"""
    cnt = [0] * n
    for op in ops:
        i, j = pairs(op)
        cnt[int(i)] += 1
        cnt[int(j)] += 1
    return cnt


# ---------------------------------------------------------------------------
# 1) 三种网格的「每模光学深度」（构造实测 + 闭式核对）
# ---------------------------------------------------------------------------
def abstract_reck_optical_depth(n_modes: int) -> dict:
    """**抽象 Reck**（`reck_decompose`，非相邻耦合 Givens，需波导交叉）的每模深度。

    构造实测 = **N−1**（每个模被 R−1 次左清 + N−1−R 次右清，合计 N−1）。
    ⇒ 这正是 D-120 `mesh_scaling_laws.n_stages` 的口径来源：**列/阶段数 = N−1**。
    ⚠️ 它不是平台**邻耦合三角网格**的每模深度（后者 = 2N−3）。
    """
    n = _guard_n(n_modes)
    ops, _D = MMM.reck_decompose(MMM.dft_matrix(n))
    cnt = _per_mode_counts(ops, n, lambda op: (op[0], op[1]))
    return {
        "mesh": "abstract_reck_givens",
        "n_modes": n,
        "n_mzi": int(len(ops)),
        "per_mode_min": int(min(cnt)),
        "per_mode_max": int(max(cnt)),
        "per_mode_mean": float(sum(cnt)) / float(n),
        "closed_form_max": int(n - 1),
        "closed_form_ok": bool(max(cnt) == n - 1),
        "needs_crossings": True,
        "note": "D-120 的 N−1 属此口径（列/阶段 = 每模深度，但需交叉）。",
    }


def triangular_optical_depth(n_modes: int) -> dict:
    """平台**邻耦合三角网格**（`reck_triangular_mesh`，M1/M2 实测 0 交叉）的每模深度。

    构造实测：**max = 2N−3**（中间模最长）、min = 1（端模）。
    🔴 与「列数 N−1」**不是一回事** —— 同一列内相邻对共享模（是链，非匹配），
    故光子在一列里可能连穿多片 ⇒ 真实每模深度**约两倍**于列数。
    """
    n = _guard_n(n_modes)
    ops, _D = MMM.reck_triangular_mesh(MMM.dft_matrix(n))
    cnt = _per_mode_counts(ops, n, lambda op: (op[1], op[1] + 1))
    return {
        "mesh": "triangular_reck_adjacent",
        "n_modes": n,
        "n_mzi": int(len(ops)),
        "n_columns": int(n - 1),
        "per_mode_min": int(min(cnt)),
        "per_mode_max": int(max(cnt)),
        "per_mode_mean": float(sum(cnt)) / float(n),
        "closed_form_max": int(2 * n - 3),
        "closed_form_min": 1,
        "closed_form_ok": bool(max(cnt) == 2 * n - 3 and min(cnt) == 1),
        "needs_crossings": False,
        "note": "列数 = N−1（结构阶段数）；**每模深度 max = 2N−3**（本模块口径）。",
    }


def rectangular_optical_depth(n_modes: int) -> dict:
    """**矩形 Clements 网格**（M5 / D-122）的每模深度（构造实测）。

    门数 = N(N−1)/2（与三角同）；层数 = **N**；每模深度 ∈ [⌊N/2⌋, **N**]。
    """
    n = _guard_n(n_modes)
    from lda_qeda import rect_mesh as RMB
    layers, _D = RMB.rectangular_mesh_layers(MMM.dft_matrix(n))
    flat = [(j, j + 1) for L in layers for (j, _t, _p) in L]
    cnt = _per_mode_counts(flat, n, lambda ij: ij)
    return {
        "mesh": "rectangular_clements",
        "n_modes": n,
        "n_mzi": int(len(flat)),
        "n_layers": int(len(layers)),
        "per_mode_min": int(min(cnt)),
        "per_mode_max": int(max(cnt)),
        "per_mode_mean": float(sum(cnt)) / float(n),
        "closed_form_max": int(n),
        "closed_form_min": int(n // 2),
        "closed_form_ok": bool(max(cnt) == n and min(cnt) == n // 2),
        "layers_are_matchings": bool(all(RMB.layer_is_matching(L, n) for L in layers)),
        "needs_crossings": None,
        "note": "层/列数 = N = 紧界（D-122）；每模深度 max = N（本模块口径）。",
    }


def optical_depth_profile(n_modes: int, *, mesh: str = "rect") -> dict:
    """按网格类型取每模深度剖面（rect 默认 = M5 矩形）。"""
    m = str(mesh).lower()
    if m in ("rect", "rectangular", "clements"):
        return rectangular_optical_depth(n_modes)
    if m in ("tri", "triangular", "reck"):
        return triangular_optical_depth(n_modes)
    if m in ("abstract", "givens", "reck_decompose"):
        return abstract_reck_optical_depth(n_modes)
    raise ValueError(f"未知 mesh={mesh!r}")


# ---------------------------------------------------------------------------
# 2) 损耗预算：静态（每模口径） / 列口径 / 时间复用
# ---------------------------------------------------------------------------
def _loss_row(dep: dict, per_item_db: float) -> dict:
    d_max = int(dep["per_mode_max"])
    d_min = int(dep["per_mode_min"])
    d_mean = float(dep["per_mode_mean"])
    l_max = d_max * float(per_item_db)
    return {
        "depth_max": d_max,
        "depth_min": d_min,
        "depth_mean": d_mean,
        "loss_per_mode_max_db": float(l_max),
        "loss_per_mode_mean_db": float(d_mean * float(per_item_db)),
        "loss_per_mode_min_db": float(d_min * float(per_item_db)),
        "per_mode_eta_at_max_loss": _eta(l_max),
    }


def static_mesh_loss_budget(n_modes: int, *, mesh: str = "rect",
                            per_mzi_db: float | None = None) -> dict:
    """静态网格的**每模口径**损耗预算（本模块的核心账）。

        每模损耗 = 每模光学深度 × per_mzi   （最坏模 / 均值 / 最好模 三档）
    """
    n = _guard_n(n_modes)
    pm = PER_MZI_LOSS_DB if per_mzi_db is None else float(per_mzi_db)
    if pm < 0.0:
        raise ValueError("per_mzi_db ≥ 0")
    dep = optical_depth_profile(n, mesh=mesh)
    row = _loss_row(dep, pm)
    return {
        "kind": "static_mesh_per_mode",
        "basis": "per_mode_optical_depth",
        "mesh": dep["mesh"],
        "n_modes": n,
        "n_physical_mzi": int(dep["n_mzi"]),
        "per_mzi_loss_db": pm,
        "crossing_loss_included": False,
        "needs_crossings": dep.get("needs_crossings"),
        **row,
    }


def column_basis_loss(n_modes: int, *, per_mzi_db: float | None = None) -> dict:
    """D-120 的**列口径**损耗：`(N−1)·per_mzi`（结构性阶段数口径）。

    ⚠️ 这是「列数 = N−1」的账（对 `reck_decompose` 抽象网格成立）；
    对平台**邻耦合三角网格**的真实每模账应看 `triangular_optical_depth`（2N−3）。
    """
    n = _guard_n(n_modes)
    pm = PER_MZI_LOSS_DB if per_mzi_db is None else float(per_mzi_db)
    if pm < 0.0:
        raise ValueError("per_mzi_db ≥ 0")
    laws = SBM.mesh_scaling_laws(n)
    loss = float(laws["loss_per_path_db"])
    return {
        "kind": "static_mesh_column_basis",
        "basis": "column_stages (D-120)",
        "mesh": "abstract_reck_givens",
        "n_modes": n,
        "n_stages": int(laws["n_stages"]),
        "loss_per_mode_db": loss,
        "per_mode_eta": _eta(loss),
        "per_mzi_loss_db": pm,
        "note": "列口径 = N−1 ⇒ 对邻耦合三角网格（真每模 2N−3）会低估约 2 倍。",
    }


def temporal_universal_loss_budget(n_modes: int, *, schedule: str = "rect") -> dict:
    """**通用**时间复用表的每模损耗 = 深度 × 每步损耗。

    schedule：
      · "rect" ⇒ 深度 = **N**（M5 可达调度，D-122）
      · "reck" ⇒ 深度 = **2N−3**（D-121 浅调度，平台三角 op 集最优）
    """
    n = _guard_n(n_modes)
    s = str(schedule).lower()
    if s in ("rect", "rectangular", "clements"):
        depth = n
    elif s in ("reck", "tri", "triangular"):
        depth = 2 * n - 3
    else:
        raise ValueError(f"未知 schedule={schedule!r}")
    loss = depth * PER_STEP_LOSS_DB
    return {
        "kind": "time_multiplexed_universal",
        "n_modes": n,
        "schedule": s,
        "depth": int(depth),
        "n_physical_mzi": 1,
        "per_step_loss_db": PER_STEP_LOSS_DB,
        "loss_per_mode_db": float(loss),
        "per_mode_eta": _eta(loss),
    }


def temporal_shallow_loss_budget(n_modes: int, depth: int) -> dict:
    """**浅电路**（放弃通用性）时间复用表：深度 D ⇒ 损耗 D·per_step；参数 ≈ ⌊N/2⌋·D。

    🔴 **两个「通用」口径必须分开**（「下界 ≠ 可达」的又一实例）：
      · `parametric_universal`：参数计数口径 ⌊N/2⌋·D ≥ N(N−1)/2（**非紧** —— D-121 证
        明偶 N 下 D = N−1 不可达）；
      · `achievable_universal`：紧界口径 D ≥ **N**（D-121 的相邻耦合紧下界，D-122 由
        矩形网格构造性达到）。
    `universal` 取**二者同时成立**（保守、可构造）。⇒ D = N−1 时参数口径"够"但**不通用**。
    """
    n = _guard_n(n_modes)
    d = int(depth)
    if d < 1:
        raise ValueError("depth ≥ 1")
    loss = d * PER_STEP_LOSS_DB
    reach = (n // 2) * d
    need = n * (n - 1) // 2
    tight = int(TMB.tight_depth_lower_bound(n))
    return {
        "kind": "time_multiplexed_shallow",
        "n_modes": n,
        "depth": d,
        "n_physical_mzi": 1,
        "per_step_loss_db": PER_STEP_LOSS_DB,
        "loss_per_mode_db": float(loss),
        "per_mode_eta": _eta(loss),
        "reachable_params": int(reach),
        "gates_needed_universal": int(need),
        "param_fraction": float(reach) / float(need),
        "parametric_universal": bool(reach >= need),
        "achievable_universal": bool(d >= tight),
        "tight_universal_depth": int(tight),
        "universal": bool(reach >= need and d >= tight),
    }


# ---------------------------------------------------------------------------
# 3) 统一账表 / 下界 / 敏感性 / 判决
# ---------------------------------------------------------------------------
def universality_loss_floor(n_modes: int) -> dict:
    """**通用性**每模损耗下界：跨架构取最小（死标量比较）。

      · 矩形静态（M5）：N·per_mzi
      · 三角静态：       (2N−3)·per_mzi
      · 时间复用（矩形调度）：N·per_step
    ⇒ 最省 = 矩形静态 N·per_mzi（比时间复用少 N·DELAY；比三角静态少 (N−3)·per_mzi）。
    """
    n = _guard_n(n_modes)
    cands = OrderedDict()
    cands["rect_static"] = n * PER_MZI_LOSS_DB
    cands["triangular_static"] = (2 * n - 3) * PER_MZI_LOSS_DB
    cands["temporal_rect_schedule"] = n * PER_STEP_LOSS_DB
    cands["temporal_reck_schedule"] = (2 * n - 3) * PER_STEP_LOSS_DB
    best = min(cands, key=lambda k: cands[k])
    return {
        "n_modes": n,
        "candidates_db": {k: float(v) for k, v in cands.items()},
        "floor_db": float(cands[best]),
        "floor_kind": best,
        "floor_eta": _eta(cands[best]),
    }


def loss_account_table(n_modes: int) -> dict:
    """把四种实现的每模损耗并列成表（`loss_per_mode_max_db` 一律为**最坏模**）。"""
    n = _guard_n(n_modes)
    rect = static_mesh_loss_budget(n, mesh="rect")
    tri = static_mesh_loss_budget(n, mesh="tri")
    tmp_rect = temporal_universal_loss_budget(n, schedule="rect")
    tmp_reck = temporal_universal_loss_budget(n, schedule="reck")
    col = column_basis_loss(n)
    rows = [
        {"impl": "静态矩形 Clements（M5）", "physical_mzi": rect["n_physical_mzi"],
         "depth": rect["depth_max"], "loss_per_mode_db": rect["loss_per_mode_max_db"],
         "universal": True, "basis": "per_mode"},
        {"impl": "静态三角 Reck（邻耦合·0 交叉）", "physical_mzi": tri["n_physical_mzi"],
         "depth": tri["depth_max"], "loss_per_mode_db": tri["loss_per_mode_max_db"],
         "universal": True, "basis": "per_mode"},
        {"impl": "时间复用（矩形调度 N）", "physical_mzi": 1,
         "depth": tmp_rect["depth"], "loss_per_mode_db": tmp_rect["loss_per_mode_db"],
         "universal": True, "basis": "per_mode"},
        {"impl": "时间复用（Reck 调度 2N−3）", "physical_mzi": 1,
         "depth": tmp_reck["depth"], "loss_per_mode_db": tmp_reck["loss_per_mode_db"],
         "universal": True, "basis": "per_mode"},
        {"impl": "静态（D-120 列口径 N−1）", "physical_mzi": tri["n_physical_mzi"],
         "depth": col["n_stages"], "loss_per_mode_db": col["loss_per_mode_db"],
         "universal": True, "basis": "column_stages"},
    ]
    return {
        "n_modes": n,
        "per_mzi_loss_db": PER_MZI_LOSS_DB,
        "per_step_loss_db": PER_STEP_LOSS_DB,
        "rows": rows,
        "rect_vs_tri_saving_db": float(rect["loss_per_mode_max_db"]
                                       - tri["loss_per_mode_max_db"]),
        "rect_vs_temporal_saving_db": float(rect["loss_per_mode_max_db"]
                                            - tmp_rect["loss_per_mode_db"]),
    }


def equal_loss_frontier(n_modes: int) -> dict:
    """在**与矩形通用静态相同的损耗预算**下，时间复用浅电路能及多少参数。"""
    n = _guard_n(n_modes)
    budget = n * PER_MZI_LOSS_DB                     # = 矩形通用静态的最坏模损耗
    d_eq = int(budget // PER_STEP_LOSS_DB)           # 同预算下可用的步数（下取整）
    sh = temporal_shallow_loss_budget(n, max(1, d_eq))
    need = n * (n - 1) // 2
    return {
        "n_modes": n,
        "loss_budget_db": float(budget),
        "temporal_depth_at_equal_loss": int(max(1, d_eq)),
        "temporal_reachable_params": int(sh["reachable_params"]),
        "rect_static_params": int(need),
        "param_fraction_vs_rect": float(sh["reachable_params"]) / float(need),
        "temporal_universal_at_equal_loss": bool(sh["universal"]),
        "note": "同损耗下时间复用浅电路仍**不通用**（参数 < N(N−1)/2）——维度计数判死。",
    }


def crossing_breakeven(n_modes: int) -> dict:
    """**交叉敏感性**（诚实披露）：矩形相对三角省的 dB 需多少交叉/模才能抹平。"""
    n = _guard_n(n_modes)
    saving = (2 * n - 3 - n) * PER_MZI_LOSS_DB        # = (N−3)·per_mzi
    cnt = saving / CROSSING_LOSS_DB
    return {
        "n_modes": n,
        "crossing_loss_db": CROSSING_LOSS_DB,
        "rect_saving_vs_tri_db": float(saving),
        "breakeven_crossings_per_mode": float(cnt),
        "note": ("矩形要抹平其优势需 ≈此数目的交叉/模；远超任何平面版图量级 ⇒ "
                 "交叉缺口不改变结论（三角网格 M2 实测 0 交叉）。"),
    }


def loss_wall_n_per_mode(eta_threshold: float, *, mesh: str = "rect",
                         per_mzi_db: float | None = None, cap: int = 100000) -> int:
    """**每模口径**损耗墙：使「最坏模」每模透射率 η < 阈值 的最小 N（≥2）。

    与 D-120 `loss_wall_n`（列口径）区分：这里用**每模光学深度**（三角 2N−3 / 矩形 N）。
    整数逐步扫描（禁闭式浮点反解）。
    """
    if not (0.0 < float(eta_threshold) <= 1.0):
        raise ValueError("eta_threshold ∈ (0,1]")
    pm = PER_MZI_LOSS_DB if per_mzi_db is None else float(per_mzi_db)
    if pm <= 0.0:
        return 0
    limit_db = -10.0 * math.log10(float(eta_threshold))
    for n in range(2, int(cap) + 1):
        if optical_depth_profile(n, mesh=mesh)["per_mode_max"] * pm > limit_db:
            return int(n)
    return int(cap) + 1


def loss_budget_verdict(n_modes: int = 216) -> dict:
    """★ 判决：把 M5 的**每模深度 N** 接进真实 dB 账后的三条结论（死标量）。"""
    n = _guard_n(n_modes)
    rect = static_mesh_loss_budget(n, mesh="rect")
    tri = static_mesh_loss_budget(n, mesh="tri")
    tmp_rect = temporal_universal_loss_budget(n, schedule="rect")
    col = column_basis_loss(n)
    floor = universality_loss_floor(n)
    sh = temporal_shallow_loss_budget(n, 32)
    cb = crossing_breakeven(n)
    saved_m5 = float(tri["loss_per_mode_max_db"] - rect["loss_per_mode_max_db"])
    tm_penalty = float(tmp_rect["loss_per_mode_db"] - rect["loss_per_mode_max_db"])
    return {
        "n_modes": n,
        "rect_static_loss_db": rect["loss_per_mode_max_db"],
        "triangular_static_loss_db": tri["loss_per_mode_max_db"],
        "column_basis_loss_db": col["loss_per_mode_db"],
        "temporal_rect_schedule_loss_db": tmp_rect["loss_per_mode_db"],
        "m5_saving_vs_triangular_db": saved_m5,
        "temporal_penalty_vs_rect_static_db": tm_penalty,
        "temporal_beats_triangular_static": bool(
            tmp_rect["loss_per_mode_db"] < tri["loss_per_mode_max_db"]),
        "temporal_still_worse_than_rect_static": bool(
            tmp_rect["loss_per_mode_db"] > rect["loss_per_mode_max_db"]),
        "universality_floor_db": floor["floor_db"],
        "universality_floor_kind": floor["floor_kind"],
        "shallow_D32_loss_db": sh["loss_per_mode_db"],
        "shallow_D32_universal": sh["universal"],
        "breakeven_crossings_per_mode": cb["breakeven_crossings_per_mode"],
        "headline": (
            f"把 M5 的**每模深度 N** 接进真实 dB 账：三角静态最坏模 (2N−3)·per = "
            f"{tri['loss_per_mode_max_db']:.0f} dB → 矩形 {n}·per = "
            f"{rect['loss_per_mode_max_db']:.0f} dB（**省 {saved_m5:.0f} dB**）。"
            f"通用时间复用（矩形调度）{tmp_rect['loss_per_mode_db']:.0f} dB："
            f"**优于三角静态**（继承矩形化收益），仍**贵于矩形静态** "
            f"{tm_penalty:.0f} dB（= N·延迟）⇒ D-121「通用与省损不可兼得」在"
            f"**可达基线 N**（而非不可达的 N−1）上依然成立。只有**浅电路**越墙"
            f"（D=32 ⇒ {sh['loss_per_mode_db']:.0f} dB）但参数 {sh['reachable_params']} "
            f"≪ {sh['gates_needed_universal']} ⇒ 非通用。"),
    }


# ---------------------------------------------------------------------------
# 4) 自检锚
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    """D-123 自检：每模深度（构造 vs 闭式，三网格）/ 列口径与每模口径区分 /
    M5 收益兑现 / 元件数不变 / 时间复用通用与浅电路 / 精度下界 / 交叉敏感性 / 护栏 / 无 LLM。"""
    res = OrderedDict()

    # ① 抽象 Reck 每模深度 = N−1（列口径来源）
    ok1 = True
    for n_ in (4, 8, 16, 64):
        d = abstract_reck_optical_depth(n_)
        if not (d["per_mode_max"] == n_ - 1 and d["closed_form_ok"]):
            ok1 = False
    res["① 抽象 Reck（reck_decompose）每模深度 = N−1（构造实测）⇒ D-120 列口径有据"] = ok1

    # ② 三角（邻耦合）每模深度 = 2N−3 · min = 1 —— 与列数 N−1 不同
    ok2 = True
    detail2 = []
    for n_ in (4, 5, 8, 16, 32, 64):
        d = triangular_optical_depth(n_)
        detail2.append(f"N={n_}:col={d['n_columns']}→max={d['per_mode_max']}")
        if not (d["per_mode_max"] == 2 * n_ - 3 and d["per_mode_min"] == 1
                and d["n_columns"] == n_ - 1 and d["closed_form_ok"]):
            ok2 = False
    res["② ★口径★ 三角（邻耦合·0交叉）每模深度 max=2N−3 ≠ 列数 N−1（构造实测）"] = ok2

    # ③ 矩形（M5）每模深度 max = N · min = ⌊N/2⌋ · 每层真匹配
    ok3 = True
    detail3 = []
    for n_ in (4, 5, 8, 16, 32, 64):
        d = rectangular_optical_depth(n_)
        detail3.append(f"N={n_}:d={d['n_layers']} max={d['per_mode_max']}")
        if not (d["per_mode_max"] == n_ and d["per_mode_min"] == n_ // 2
                and d["n_layers"] == n_ and d["layers_are_matchings"] and d["closed_form_ok"]):
            ok3 = False
    res["③ ★M5★ 矩形每模深度 max=N · min=⌊N/2⌋ · 每层真匹配（构造实测）"] = ok3

    # ④ 元件数不变：两种网格同为 N(N−1)/2
    ok4 = True
    for n_ in (4, 16, 64, 216):
        if not (triangular_optical_depth(n_)["n_mzi"] == n_ * (n_ - 1) // 2
                and rectangular_optical_depth(n_)["n_mzi"] == n_ * (n_ - 1) // 2):
            ok4 = False
    res["④ 元件数不变：三角/矩形同为 N(N−1)/2（Clements 必要性定理）"] = ok4

    # ⑤ ★M5 接进 dB 账★ N=216：三角 1029.6 → 矩形 518.4（省 511.2）
    tri216 = static_mesh_loss_budget(216, mesh="tri")
    rect216 = static_mesh_loss_budget(216, mesh="rect")
    ok5 = (abs(tri216["loss_per_mode_max_db"] - 429 * PER_MZI_LOSS_DB) < 1e-9
           and abs(rect216["loss_per_mode_max_db"] - 216 * PER_MZI_LOSS_DB) < 1e-9
           and rect216["loss_per_mode_max_db"] < tri216["loss_per_mode_max_db"])
    res[f"⑤ ★M5 收益★ N=216：三角 {tri216['loss_per_mode_max_db']:.1f} dB → "
        f"矩形 {rect216['loss_per_mode_max_db']:.1f} dB（省 "
        f"{tri216['loss_per_mode_max_db']-rect216['loss_per_mode_max_db']:.1f} dB）"] = ok5

    # ⑥ 列口径（N−1）低估：它 ≈ 矩形口径、远小于三角每模口径
    col216 = column_basis_loss(216)
    ok6 = (abs(col216["n_stages"] - 215) < 1e-9
           and col216["loss_per_mode_db"] < tri216["loss_per_mode_max_db"] - 400.0)
    res[f"⑥ ★口径区分★ D-120 列口径 {col216['loss_per_mode_db']:.1f} dB 低估三角真账"
        f" {tri216['loss_per_mode_max_db']:.1f} dB（差 "
        f"{tri216['loss_per_mode_max_db']-col216['loss_per_mode_db']:.1f} dB）"] = ok6

    # ⑦ 时间复用通用（矩形调度）：优于三角静态、仍贵于矩形静态（= N·DELAY）
    tm216 = temporal_universal_loss_budget(216, schedule="rect")
    pen = tm216["loss_per_mode_db"] - rect216["loss_per_mode_max_db"]
    ok7 = (abs(pen - 216 * DELAY_LOSS_DB) < 1e-9
           and tm216["loss_per_mode_db"] < tri216["loss_per_mode_max_db"]
           and tm216["loss_per_mode_db"] > rect216["loss_per_mode_max_db"])
    res[f"⑦ 时间复用通用（矩形调度 N）{tm216['loss_per_mode_db']:.1f} dB："
        f"优于三角静态 · 贵于矩形静态 {pen:.1f} dB（= N·延迟）⇒ 通用不省损"] = ok7

    # ⑧ 浅电路 D=32：损耗大降但参数 ≪ 通用所需 ⇒ 非通用
    sh32 = temporal_shallow_loss_budget(216, 32)
    ok8 = (abs(sh32["loss_per_mode_db"] - 32 * PER_STEP_LOSS_DB) < 1e-9
           and sh32["loss_per_mode_db"] < rect216["loss_per_mode_max_db"] - 400.0
           and sh32["universal"] is False
           and sh32["reachable_params"] == 108 * 32)
    res[f"⑧ 浅电路 D=32：{sh32['loss_per_mode_db']:.1f} dB（越墙）但参数 "
        f"{sh32['reachable_params']} ≪ {sh32['gates_needed_universal']} ⇒ 非通用"] = ok8

    # ⑨ 通用性损耗下界 = 矩形静态 N·per_mzi（跨四实现取最小）
    fl = universality_loss_floor(216)
    ok9 = (fl["floor_kind"] == "rect_static"
           and abs(fl["floor_db"] - 216 * PER_MZI_LOSS_DB) < 1e-9)
    res[f"⑨ 通用性每模损耗下界 = {fl['floor_db']:.1f} dB（{fl['floor_kind']}）"] = ok9

    # ⑩ 交叉敏感性：抹平需 ≈1e4 交叉/模（远超版图量级）
    cb = crossing_breakeven(216)
    ok10 = cb["breakeven_crossings_per_mode"] > 9000.0
    res[f"⑩ 交叉敏感性：抹平矩形优势需 ≈{cb['breakeven_crossings_per_mode']:.0f} 交叉/模"
        f" ⇒ 交叉缺口不改结论"] = ok10

    # ⑪ 等损耗前沿：同预算下时间复用浅电路仍不通用
    eq = equal_loss_frontier(216)
    ok11 = (eq["temporal_universal_at_equal_loss"] is False
            and eq["param_fraction_vs_rect"] < 1.0)
    res[f"⑪ 等损耗前沿：同预算时间复用浅电路参数 = {eq['temporal_reachable_params']}"
        f" = {eq['param_fraction_vs_rect']*100:.0f}% 矩形通用 ⇒ 仍非通用"] = ok11

    # ⑫ 护栏
    guard = True
    for bad in ((lambda: triangular_optical_depth(1)),
                (lambda: rectangular_optical_depth(0)),
                (lambda: static_mesh_loss_budget(8, mesh="rect", per_mzi_db=-0.1)),
                (lambda: temporal_universal_loss_budget(8, schedule="nope")),
                (lambda: temporal_shallow_loss_budget(8, 0)),
                (lambda: optical_depth_profile(8, mesh="unknown")),
                (lambda: loss_wall_n_per_mode(1.5))):
        try:
            bad()
            guard = False
        except ValueError:
            pass
    res["⑫ 护栏：非法 N / 负 per_mzi / 未知 mesh / 未知调度 / depth<1 / 非法阈值 ⇒ ValueError"] = guard

    # ⑬ 判决无 LLM：深度/参数为 int、损耗为 float、判决为 bool（死标量）
    v = loss_budget_verdict(216)
    res["⑬ 判决无 LLM：深度/参数为 int · 损耗为 float · 判决位为 bool（死标量）"] = (
        isinstance(v["n_modes"], int)
        and isinstance(v["temporal_beats_triangular_static"], bool)
        and isinstance(v["rect_static_loss_db"], float))

    # ⑭ ★下界 ≠ 可达★ 浅电路 D = N−1：参数计数口径"够"但紧界未达 ⇒ **不通用**
    sh215 = temporal_shallow_loss_budget(216, 215)
    sh216 = temporal_shallow_loss_budget(216, 216)
    ok14 = (sh215["parametric_universal"] is True
            and sh215["achievable_universal"] is False
            and sh215["universal"] is False
            and sh215["reachable_params"] == sh215["gates_needed_universal"]
            and sh216["universal"] is True
            and sh215["tight_universal_depth"] == 216)
    res["⑭ ★下界≠可达★ 浅电路 D=N−1：参数口径够(23220)但紧界未达 ⇒ 不通用（D≥N 才通用）"] = ok14

    if verbose:
        for k, val in res.items():
            print(f"[{'PASS' if val else 'FAIL'}] {k}")
        print("② 明细：" + " · ".join(detail2))
        print("③ 明细：" + " · ".join(detail3))
    return bool(all(res.values()))


RED_LINE_DISCLOSURE = {
    "role": "D-123 = 真实损耗预算（M5 延伸）：把「每模光学深度」接进 dB 账，"
            "并显式区分「列口径 N−1」与「每模口径 2N−3 / N」。",
    "basis_separation": "列口径（D-120 n_stages=N−1，抽象 Reck / 需交叉）≠ 每模口径"
                        "（邻耦合三角 2N−3 · 矩形 N）；真实损耗必须用每模口径。",
    "golden": "只用闭式 / 构造实测：2N−3 · N−1 · ⌊N/2⌋ · N · 10^(−dB/10) · "
              "⌈n_mzi/⌊N/2⌋⌉；「每模深度」由跑分解数门数构造得到并附闭式核对。",
    "reuse_not_reinvent": "per_mzi=2.4 dB 复用 D-120（scale_bench）；每步延迟 0.2 dB 与"
                          "per_step=2.6 dB 复用 D-121（temporal_mesh）；矩形层复用 D-122"
                          "（rect_mesh → 主权 clements_rect_decompose）。",
    "sovereignty": "C 级自主（纯 numpy + 平台 lda_l2 / lda_qeda / lda_layout），零量子 SDK；"
                   "LLM 不进判决路径。",
    "honest_boundary": "① 损耗为**设计预算口径**（非实测 PDK，属 D5）；"
                       "② 不含波导交叉损耗（三角网格 M2 实测 0 交叉；矩形交叉数需 P&R 几何，"
                       "属 P1-B）—— 附交叉敏感性：抹平矩形优势需 ≈1e4 交叉/模，不改结论；"
                       "③ 「每模深度」为构造实测（非仿真、非拟合）；"
                       "④ 结论 3（通用与省损不可兼得）在**可达基线 N**（非不可达的 N−1）上成立。",
}

if __name__ == "__main__":
    ok = run_selfchecks(verbose=True)
    print(f"loss_budget 自检：{'全 PASS' if ok else '有 FAIL'}")
