"""宽度 / 通道的权衡：E49 说「扩规模必须等比加宽 die」，本模块把这句话**量化并修正**。

═══════════════════════════════════════════════════════════════════════════════
E49 留下的问题
───────────────────────────────────────────────────────────────────────────────
E49 的结论是「上限来自布线资源、扩规模必须等比加宽 die」。但那只测了 **cols 固定 8** 的一维。
本模块把 **cols（die 宽度）** 与 **CH（通道高度）** 当两个独立的资源杠杆做二维扫描，
回答：加宽 die 到底能换回多少布通率、代价多大、上限在哪。

═══════════════════════════════════════════════════════════════════════════════
三条实测结论（都会进判据）
───────────────────────────────────────────────────────────────────────────────
① **加宽 die 单独做是「负收益」**：CH=1.60（T=4）时，cols 8→32 布通率 **56.9% → 0.0%**
   **单调下降**。原因：cols 增大 ⇒ rows 减小 ⇒ **通道数减少**（每行上方一条通道），
   而通道轨道数 T 不变 ⇒ 每个通道要服务的网更多 ⇒ 通道容量律先崩。
   ⇒ E49 那句「必须等比加宽 die」**不完整**，必须补「**同时**加高通道」。

② **存在最优点，且布通率对 cols 非单调**：CH=3.40（T=9）时 256 单元
   cols 4/8/12/16/20/24/32 → **51/67/70/85/86/87/43 %**。
   越过最优点（cols=32）通道只剩 8 条、4 个通道超容量（覆盖 124 网）⇒ 崩到 43%。
   ⇒ 这是「两条方向相反的资源约束」的交叉点，不是调参手感。

③ **再加 jog_max 救不了剩下的失败**（证伪「候选列不够」）：
   把 `M2_JOG_MAX` 从 0.72 提到 2.16（每引脚候选列 **5 → 13**，2.6×），
   `no_column` 只从 34 降到 32。⇒ 根因**不是**候选列少，而是**每个网独占一条跨行 M4 竖线**
   （星形拓扑：每网一条 trunk，竖线从引脚跨到通道）—— 列再多也分不过来。
   ⇒ 真正的出路是**加一层垂直层（M5）**或在**行内做局部布线**，不是继续加宽。

═══════════════════════════════════════════════════════════════════════════════
面积代价（实测，256 单元）
───────────────────────────────────────────────────────────────────────────────
  默认（cols=8 / CH=1.60）：1161 µm² · 布通 56.9%
  最优点（cols=24 / CH=3.40）：1980 µm² · 布通 **87.3%**  ⇒ **面积 +71% 换 +30.4pp**
  「85% 档」（cols=16 / CH=2.80）：1650 µm² · 布通 84.6% ⇒ 面积 +42%
  ⇒ 边际收益在 cols≈24/CH≈3.4 就见顶；再往上必须换杠杆。
"""

from . import dctrl as CT
from . import ddrc_lvs as DL
from . import dpnr as PN

#: 默认列数扫描（die 宽度 = cols × pitch_x）。
COLS_GRID = (4, 8, 12, 16, 20, 24, 32)
#: 默认通道高度扫描（µm）⇒ T = floor((CH−W)/pitch)+1。
CH_GRID = (1.60, 2.20, 2.80, 3.40)
#: 默认规模（256 单元 = 256 个可建模门）。
CASE_CELLS = 256


def tracks_for(ch_um: float) -> int:
    """通道高 `ch_um` 能放几条 M3 轨道。

    🔴 **直接引用 `dpnr.tracks_in_channel`，不在这里重算** —— 同一个物理量写两份真源，
    改一处忘另一处就会报出与实际容量判定不一致的 T（本轮把它记进「同源=写成引用」）。
    """
    return PN.tracks_in_channel(ch_um)


def probe_config(nl, cells: int, cols: int, ch_um: float) -> dict:
    """跑一个 `(cols, ch_um)` 配置，返回布通率 / 失败构成 / 面积 / DRC。

    🔴 `ch_um` 只影响**布局与容量判定**（`place_real` 用模块常量 `CH_UM` 算行距与通道数），
    所以这里临时改全局再立刻恢复 —— 不留下跨调用状态。
    """
    old = PN.CH_UM
    try:
        PN.CH_UM = float(ch_um)
        pl = PN.place_real(nl, max_cells=cells, cols=cols, truncate_ok=True)
        rt = PN.route_block(nl, pl)
        vr = DL.run_drc(PN.all_routing(rt))["violations"]
    finally:
        PN.CH_UM = old

    n_int = len(rt["routed"]) + len(rt["unrouted"])
    n_col = int((pl["die_w_um"] - PN.W) // PN.PITCH) + 1
    ch_full = sum(1 for v in rt["ch_info"].values() if not v["routable"])
    nets_in_full = sum(v["n_nets"] for v in rt["ch_info"].values() if not v["routable"])
    return {
        "cells": int(cells), "cols": int(cols), "ch_um": float(ch_um),
        "rows": int(pl["rows"]), "t_tracks": tracks_for(ch_um), "n_col": n_col,
        "die_w_um": pl["die_w_um"], "die_h_um": pl["die_h_um"],
        "area_um2": pl["die_w_um"] * pl["die_h_um"],
        "n_net": len(rt["pins"]), "n_int": n_int,
        "n_routed": len(rt["routed"]), "n_unrouted": len(rt["unrouted"]),
        "route_rate": (len(rt["routed"]) / n_int) if n_int else 0.0,
        "n_fail_no_column": rt["n_col_fail_no_column"],
        "n_fail_too_far": rt["n_col_fail_too_far"],
        "n_channel_full": int(ch_full), "n_nets_in_full_channel": int(nets_in_full),
        "n_drc": len(vr),
    }


def width_sweep(nl=None, cells: int = CASE_CELLS,
                cols_grid=COLS_GRID, ch_grid=CH_GRID) -> dict:
    """二维扫 `(cols × CH)`，返回 `{"rows": [...], "cols_grid": ..., "ch_grid": ...}`。"""
    if nl is None:
        nl = CT.build()["netlist"]
    rows = [probe_config(nl, cells, c, ch) for ch in ch_grid for c in cols_grid]
    return {"rows": rows, "cols_grid": tuple(cols_grid), "ch_grid": tuple(ch_grid),
            "cells": int(cells)}


def slice_at(grid: dict, ch_um: float) -> list:
    """取某一通道高度下、沿 cols 的切片（按 cols 升序）。"""
    return sorted([r for r in grid["rows"] if abs(r["ch_um"] - ch_um) < 1e-9],
                  key=lambda r: r["cols"])


def best_of(rows: list) -> dict:
    """布通率最高的那一档（并列时取面积小的）。"""
    return min(rows, key=lambda r: (-r["route_rate"], r["area_um2"]))


def is_unimodal(seq: list, tol: float = 1e-9) -> bool:
    """序列是否「先升后降」（单峰）。用于判「存在最优点」。

    允许平台：严格上升段之后只允许不增。
    """
    if len(seq) < 3:
        return False
    i = 0
    while i + 1 < len(seq) and seq[i + 1] > seq[i] + tol:
        i += 1
    if i == 0:                       # 从第一步就下降 ⇒ 不是「先升」
        return False
    while i + 1 < len(seq) and seq[i + 1] <= seq[i] + tol:
        i += 1
    return i == len(seq) - 1


def monotonically_non_increasing(seq: list, tol: float = 1e-9) -> bool:
    return all(seq[i + 1] <= seq[i] + tol for i in range(len(seq) - 1))


def pareto(rows: list) -> list:
    """（面积, 布通率）Pareto 前沿：不被「面积更小且布通率更高」的档支配。"""
    out = []
    for r in sorted(rows, key=lambda x: (x["area_um2"], -x["route_rate"])):
        if not out or r["route_rate"] > out[-1]["route_rate"] + 1e-9:
            out.append(r)
    return out


def min_area_for(rows: list, target_rate: float) -> dict:
    """达到 `target_rate` 布通率的**最小面积**档；达不到返回 None。"""
    ok = [r for r in rows if r["route_rate"] >= target_rate - 1e-9]
    if not ok:
        return None
    return min(ok, key=lambda r: r["area_um2"])


def jog_probe(nl=None, cells: int = CASE_CELLS, cols: int = 24,
              ch_um: float = 3.40, jog_list=(0.72, 2.16)) -> dict:
    """**证伪「候选列不够」**：放大 `M2_JOG_MAX`（⇒ 每引脚候选列数）看 `no_column` 降多少。

    若候选列数真的是瓶颈，2.6× 的候选列应带来成比例的改善；实测只降 2 个网
    ⇒ 根因是「每网独占一条跨行 M4 竖线」，与候选列数无关。
    """
    if nl is None:
        nl = CT.build()["netlist"]
    old_ch, old_jog = PN.CH_UM, PN.M2_JOG_MAX
    out = []
    try:
        PN.CH_UM = float(ch_um)
        for jog in jog_list:
            PN.M2_JOG_MAX = float(jog)
            pl = PN.place_real(nl, max_cells=cells, cols=cols, truncate_ok=True)
            rt = PN.route_block(nl, pl)
            out.append({"jog_um": float(jog),
                        "n_cand": 2 * int(jog // PN.PITCH) + 1,
                        "n_no_column": rt["n_col_fail_no_column"],
                        "n_routed": len(rt["routed"])})
    finally:
        PN.CH_UM, PN.M2_JOG_MAX = old_ch, old_jog
    lo, hi = out[0], out[-1]
    return {"samples": out,
            "cand_ratio": hi["n_cand"] / lo["n_cand"],
            "gain_nets": hi["n_routed"] - lo["n_routed"],
            "nocol_drop": lo["n_no_column"] - hi["n_no_column"]}


DWIDTH_DISCLOSURE = {
    "what": "宽度/通道二维权衡：加宽 die 的收益、代价、最优点与上限归因",
    "claimable": False,
    "not_a_recipe": True,
    "limits": [
        "测的是**当前实现 + 当前几何**（INV+NAND2 / LDA-DEMO45 / 每网一条 M3 trunk 的星形拓扑），"
        "**不是通用布局布线结论**：换单元库、换拓扑（maze/steiner）、换层数都要重测",
        "「加宽 die 单独做是负收益」的前提是**通道数 == 行数**这条实现约定；"
        "真实设计里通道与行不一一对应，此结论不可直接外推",
        "最优点位置随规模漂移（64/128/256/512 单元实测 cols≈20/24/24/20），"
        "**不是一个常数**；本模块只断言「存在且在 [16, 24] 内」",
        "面积是**裸单元排布面积**（含单元间距与通道高），不含 IO/电源环/keep-out",
        "剩余失败（~13%）的真根因是「每网独占跨行 M4 竖线」，"
        "已验证**加大 jog_max 无用**；出路是加层（M5）或行内局部布线 —— 本仓都还没做",
        "不宣称可制造 / 可流片；规则集自建教科书尺度，非 foundry PDK",
        "净增 0 锚（计数与比值 ⇒ resid≡0）⇒ 门禁形态",
    ],
}
