"""规模上探：这套链路**能用到多大规模**，以及上限来自哪里。

═══════════════════════════════════════════════════════════════════════════════
为什么需要这个模块
───────────────────────────────────────────────────────────────────────────────
E45–E48 的所有结论都建立在**一个 12 单元的小块**上（「路由 DRC 34→0」「零 DRC」）。
那些结论对不对、能推广到多远，此前**没有任何证据**。本模块把规模当自变量：

  · 产出一条**规模阶梯**（12 … 1024 单元）的实测表：形状数、内部网数、布通率、
    各类失败原因、分段耗时、DRC 数；
  · 拟合 **DRC 耗时的复杂度指数**（`run_drc` 是逐对 O(M²)，M = 金属 shape 数）；
  · 按拟合律**外推**到更大规模，给一个可引用的数；
  · 把「上限来自什么」说清楚 —— 是算法、是资源、还是我自己实现的限定。

═══════════════════════════════════════════════════════════════════════════════
这里查出的两个真缺陷（都不是"算法不够聪明"）
───────────────────────────────────────────────────────────────────────────────
① **成片的 M3 长跳线短路（v0.9.352 修）**：列被推远超过 M2 逃逸上限后，旧代码退回
   **M3 横向长跳线**，而跳线只能画在**引脚 y** 上 —— 同一行所有引脚的 y 相同 ⇒ 多条
   跳线全叠在同一 y、同层不同网 ⇒ `min_spacing` 成片（64 单元 8 行实测 **41 条**）。
   12 单元的块里列不会被推远，所以 E45 的「零 DRC」在**规模上不成立**。
   修法：把逃逸上限当**硬约束**，超出就如实报 `too_far`/`no_column`，不画违例假装布通。

② **逐引脚逃逸额度必须按方向算（v0.9.352 修）**：逃逸条只朝**一个方向**扩张，向左逃
   只受左邻约束。初版用「两侧各摊一半」的单一额度，把「向左 0.5µm 完全合法」误判成
   「只能逃 0.01µm」⇒ 12 单元布通率从 10/10 掉到 9/10（判据 A 立刻抓到）。

═══════════════════════════════════════════════════════════════════════════════
上限在哪（实测，不是估计）
───────────────────────────────────────────────────────────────────────────────
· **时间**：DRC 占绝对主导（1024 单元时 96%）。拟合 `t_drc ∝ M^1.95` —— 与逐对
  比较的 O(M²) 一致。这是**纯 Python 单核**的数，不代表 C++ 实现。
· **资源**：固定 die 宽（8 列）时，**列失败率随规模单调上升**（12 单元 0% → 1024 单元
  82%）。原因是 M4 列数由 **die 宽度**决定、与行数无关；行数一多，列必然枯竭。
  ⇒ 「这套链路能用到多大规模」的真实答案是：**不是被算法卡住，是被布线资源卡住**；
  要扩规模必须**等比加宽 die**（与 E38 链「唯一杠杆是加面积」同向）。

🔴 **本模块不宣称任何规模上限是「算法极限」**：它测的是**当前实现 + 当前几何**。
"""

import math
import time

from . import dctrl as CT
from . import ddrc_lvs as DL
from . import dpnr as PN

#: 默认规模阶梯（单元数）。列数固定 8 ⇒ 行数随规模增加（这是「固定 die 宽」的工况）。
LADDER = (12, 32, 64, 128, 256, 512, 1024)
#: 默认列数（= die 宽度的一半多一点）。
COLS = 8


def _ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


def probe(nl, max_cells: int, cols: int = COLS, cell_gap: float = None) -> dict:
    """跑一档规模，返回**分段计时 + 结果统计**（不改任何全局状态）。"""
    t0 = time.perf_counter()
    pl = PN.place_real(nl, max_cells=max_cells, cols=cols, cell_gap=cell_gap,
                       truncate_ok=True)   # 规模阶梯：就是要截断
    t_place = _ms(t0)

    t0 = time.perf_counter()
    rt = PN.route_block(nl, pl)
    t_route = _ms(t0)

    sh = PN.all_routing(rt)
    metals = [s for s in sh if s.kind in ("metal", "pin")]
    t0 = time.perf_counter()
    vr = DL.run_drc(sh)["violations"]
    t_drc = _ms(t0)

    n_net = len(rt["pins"])
    n_routed = len(rt["routed"])
    n_chan_full = len(rt["ch_info"]) - sum(1 for v in rt["ch_info"].values() if v["routable"])
    return {
        "cells": int(max_cells), "cols": int(cols), "rows": int(pl["rows"]),
        "die_w_um": pl["die_w_um"], "die_h_um": pl["die_h_um"],
        "die_area_um2": pl["die_w_um"] * pl["die_h_um"],
        "n_shapes": len(sh), "n_metals": len(metals),
        "n_net": n_net, "n_routed": n_routed, "n_unrouted": len(rt["unrouted"]),
        "route_rate": (n_routed / n_net) if n_net else 0.0,
        "n_fail_too_far": rt["n_col_fail_too_far"],
        "n_fail_no_column": rt["n_col_fail_no_column"],
        "n_chan_full": int(n_chan_full),
        "n_drc": len(vr),
        "t_place_ms": t_place, "t_route_ms": t_route, "t_drc_ms": t_drc,
        "t_total_ms": t_place + t_route + t_drc,
    }


def size_ladder(nl=None, ladder=LADDER, cols: int = COLS) -> dict:
    """跑完整阶梯。返回 `{"rows": [...], "cols": cols}`（逐档一行，可直接打印成表）。"""
    if nl is None:
        nl = CT.build()["netlist"]
    rows = [probe(nl, n, cols=cols) for n in ladder]
    for r in rows:
        r["drc_share"] = (r["t_drc_ms"] / r["t_total_ms"]) if r["t_total_ms"] else 0.0
        r["fail_rate"] = ((r["n_fail_too_far"] + r["n_fail_no_column"]) / r["n_net"]
                          if r["n_net"] else 0.0)
        r["no_column_rate"] = (r["n_fail_no_column"] / r["n_net"]) if r["n_net"] else 0.0
    return {"rows": rows, "cols": int(cols), "ladder": tuple(ladder)}


def fit_exponent(xs: list, ys: list) -> dict:
    """对 `y = a·x^k` 做 log-log 最小二乘，返回 `k` 与拟合优度 R²。

    只用 `x>0 ∧ y>0` 的点（耗时为 0 的档不参与）。
    """
    pts = [(x, y) for (x, y) in zip(xs, ys) if x > 0 and y > 0]
    if len(pts) < 2:
        return {"k": float("nan"), "r2": 0.0, "n": len(pts)}
    lx = [math.log(x) for (x, _y) in pts]
    ly = [math.log(y) for (_x, y) in pts]
    n = len(lx)
    mx = sum(lx) / n
    my = sum(ly) / n
    sxx = sum((v - mx) ** 2 for v in lx)
    sxy = sum((a - mx) * (b - my) for (a, b) in zip(lx, ly))
    k = sxy / sxx if sxx else float("nan")
    b = my - k * mx
    ss_tot = sum((b0 - my) ** 2 for b0 in ly)
    ss_res = sum((ly[i] - (k * lx[i] + b)) ** 2 for i in range(n))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot else 1.0
    return {"k": k, "r2": r2, "n": n, "intercept": b}


def complexity(ladder_result: dict) -> dict:
    """阶梯的复杂度画像：DRC 耗时对金属数、总耗时对单元数。"""
    rows = ladder_result["rows"]
    drc = fit_exponent([r["n_metals"] for r in rows], [r["t_drc_ms"] for r in rows])
    tot = fit_exponent([r["cells"] for r in rows], [r["t_total_ms"] for r in rows])
    return {"drc_vs_metals": drc, "total_vs_cells": tot,
            "drc_share_max": max(r["drc_share"] for r in rows),
            "drc_share_min": min(r["drc_share"] for r in rows)}


def extrapolate(ladder_result: dict, target_cells: int) -> dict:
    """按**实测的 DRC 复杂度指数**外推目标规模的 DRC 耗时。**结果是一个上界，不是点估计。**

    🔴 为什么是上界（实测，不是保守取值）：金属数**并不与单元数成正比** —— 规模一放大，
    列资源枯竭、布通率下降 ⇒ 形状增长慢于单元数（实测 `metals/cells` 从 6.5 降到 3.3）。
    本函数按**末档比例线性放大**金属数，于是系统性高估 M，再经 `^k` 放大成时间高估。
    实测：用前 6 档外推 1024 单元，高估 **83%**（2.72 s vs 实测 1.48 s）。

    ⇒ 引用这个数时必须写「**上界**」，不能当点估计用；真实规模下的布通率会更低
    （那就不是"更快的同一件事"，而是"布得更少"）。**布通率不外推**：它由资源决定，不是幂律。
    """
    rows = ladder_result["rows"]
    last = rows[-1]
    cmp_ = complexity(ladder_result)
    k = cmp_["drc_vs_metals"]["k"]
    metals_per_cell = last["n_metals"] / last["cells"] if last["cells"] else 0.0
    m_target = metals_per_cell * target_cells
    t_last = last["t_drc_ms"]
    if not (t_last > 0 and last["n_metals"] > 0 and k == k):
        return {"target_cells": target_cells, "k": k, "t_drc_s": float("nan")}
    t = t_last * (m_target / last["n_metals"]) ** k
    return {"target_cells": int(target_cells), "metals_per_cell": metals_per_cell,
            "n_metals_est": m_target, "k": k, "t_drc_s": t / 1000.0,
            "based_on_cells": last["cells"], "based_on_t_drc_s": t_last / 1000.0}


def failure_breakdown(ladder_result: dict) -> list:
    """逐档的失败构成（用于判「列资源枯竭」是不是单调的）。"""
    out = []
    for r in ladder_result["rows"]:
        out.append({"cells": r["cells"], "n_net": r["n_net"],
                    "n_routed": r["n_routed"],
                    "no_column": r["n_fail_no_column"],
                    "too_far": r["n_fail_too_far"],
                    "chan_full": r["n_chan_full"],
                    "no_column_rate": r["no_column_rate"],
                    "route_rate": r["route_rate"]})
    return out


def monotonic(seq: list, tol: float = 1e-9) -> bool:
    """非严格单调不降（允许相等）。用于「列失败率随规模上升」这条判据。"""
    return all(seq[i] <= seq[i + 1] + tol for i in range(len(seq) - 1))


DSCALE_DISCLOSURE = {
    "what": "规模上探：阶梯实测（12…1024 单元）+ DRC 复杂度指数拟合 + 外推 + 失败构成",
    "claimable": False,
    "not_a_limit_claim": True,
    "limits": [
        "测的是**当前实现 + 当前几何**（8 列固定 / INV+NAND2 / LDA-DEMO45 规则集），"
        "**不是算法极限**：换 C++ 实现、换列数、换单元库都要重测",
        "复杂度指数来自**纯 Python 单核**实测；绝对耗时不可外推到真实 EDA 工具",
        "外推只对 **DRC 耗时**做幂律外推，且结果是**上界**（按末档 metals/cells 比例线性放大，"
        "而实测该比例随规模下降 ⇒ 系统性高估，前 6 档外推末档高估 83%）；"
        "**不外推布通率** —— 它由资源决定，不是幂律",
        "阶梯取网表**前 N 个门**，内部网数随门序变化（不严格等比），所以「布通率」"
        "本身不单调；单调的是**列失败率**（它直接反映「列数由 die 宽决定」这条机制）",
        "规模上限的根因是**布线资源**（列数 ∝ die 宽，与行数无关），不是算法缺陷；"
        "扩规模必须等比加宽 die（与 E38 链同向）",
        "不宣称可制造 / 可流片；规则集自建教科书尺度，非 foundry PDK",
        "净增 0 锚（计数与浮点幂律拟合 ⇒ resid≡0）⇒ 门禁形态",
    ],
}
