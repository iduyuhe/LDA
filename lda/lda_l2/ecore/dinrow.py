"""行内局部布线：**能不能让网在行内互联、不走跨行长竖线**（E51 · D-243）。

═══════════════════════════════════════════════════════════════════════════════
为什么瞄准这条路
───────────────────────────────────────────────────────────────────────────────
E50 结束时布通率卡在 **87.3%**，失败全是 `no_column`，而 E50 已机核排除「候选列不够」，
并指出真根因是**每个网独占一条跨行 M4 竖线**（星形拓扑：每网一条 M3 trunk，竖线从引脚跨到通道）。
本模块要验的就是这句话给出的出路：**让网在行内互联**。

动机是实测出来的：**60–80% 的内部网所有引脚都在同一行**（256 单元 cols=8 时 61%、cols=24 时 79%）
—— 这些网根本不需要跨行。

═══════════════════════════════════════════════════════════════════════════════
结论：这条路**走不通**，三个独立证据
───────────────────────────────────────────────────────────────────────────────
① **行内 M3 水平段必撞**：同一行所有引脚的 M3 pad 都在自己的 y 带上，任何横穿同行的水平段
   都会压到异网 pad。实测 256 单元 cols=24：布通率 **零改善**（233 网一个没多），
   而 DRC 从 **0 爆到 786 条**（cols=16 是 288、cols=8 是 70）。

② **行内 M2 也没空间**（闭式）：单元内 M1 引脚之间的最大空隙 —— INV **345nm**、NAND2 **410nm**，
   而一条 M2 走线需 `W + S_MIN = 340nm` ⇒ **最多 1 条轨道**，INV 余量只剩 **5nm**。
   一行有几十个网要横连 ⇒ 1 条轨道远远不够。

③ **列分配迭代零收益**：第一轮用「通道最高轨」估 M4 竖段的 y 区间（最坏情况），
   改用实际轨号后区间确实变短 —— 但布通率**一个网都没多**。
   ⇒ 冲突**不是**来自区间长度，而是「同一行的引脚 y 区间必然重叠」这条几何事实。

═══════════════════════════════════════════════════════════════════════════════
于是得到一条「渐近线」的量化解释
───────────────────────────────────────────────────────────────────────────────
加宽 die 同时带来两件事：列数 `ncol ≈ die_w/pitch` 增加，**而每行引脚数也同比增加**。实测：

| cols | ncol | 每行最大引脚数 | 供给/需求 | 布通率 |
|---|---|---|---|---|
| 4  | 16  | 12 | 1.33 | 51.3% |
| 8  | 32  | 24 | 1.33 | 66.7% |
| 16 | 64  | 46 | 1.39 | 84.6% |
| 24 | 96  | 67 | **1.43** | **87.3%** |
| 32 | 128 | 90 | 1.42 | 43.1%（通道崩） |

供给/需求比**恒定在 1.33–1.43**，所以「加宽」永远不能把 `no_column` 归零
（最优点仍剩 **34/267 = 12.7%**）。布通率就在 **87%** 处见顶。

**⇒ 唯一能突破的杠杆是「加一层垂直层（M5）」让列资源翻倍**：分子（列）可以靠新层翻倍，
而分母（每行引脚数）不变。这是本模块给出的、有实测支撑的下一步。
"""

import collections

from . import dcells as CL
from . import dctrl as CT
from . import ddrc_lvs as DL
from . import dpnr as PN

#: 探针用的规模（256 单元 = E50 的基线工况）。
CASE_CELLS = 256
#: 判「同行」的列数集合。
COLS_GRID = (8, 16, 24, 32)
#: 通道高度扫描（验证「加到某个高度后完全饱和」）。
CH_GRID = (3.40, 4.00, 4.60, 5.20, 6.00)
#: 列分配迭代次数（第一轮 vs 多轮）。
ITER_GRID = (1, 2, 3)


def _with_ch(ch_um, fn):
    """临时设 `PN.CH_UM` 跑一次 `fn()`，**无论如何都恢复**（不留跨调用状态）。"""
    old = PN.CH_UM
    try:
        PN.CH_UM = float(ch_um)
        return fn()
    finally:
        PN.CH_UM = old


def row_gaps(cell_name: str) -> dict:
    """某单元**行内可用 y 空隙**（nm）与「一条 M2 走线」的需求对比。

    空隙 = 相邻 M1 引脚 pad 之间、以及最低/最高 pad 与行边界之间的空白。
    M2 走线需求 = `W + S_MIN`（线宽 + 最小间距）。
    """
    c = CL.CELLS[cell_name]()
    ys = sorted((v.y0, v.y1) for v in c.pins.values())
    gaps, prev = [], 0
    for (y0, y1) in ys:
        if y0 > prev:
            gaps.append((prev, y0, y0 - prev))
        prev = max(prev, y1)
    if CL.H_ROW > prev:
        gaps.append((prev, CL.H_ROW, CL.H_ROW - prev))
    need_nm = (PN.W + DL.S_MIN) * 1000.0
    widest = max((g for (_a, _b, g) in gaps), default=0)
    return {"cell": cell_name, "h_row_nm": CL.H_ROW, "gaps_nm": gaps,
            "widest_nm": widest, "need_nm": need_nm,
            "n_tracks": int(widest // need_nm), "slack_nm": widest - need_nm}


def net_row_span(pl: dict, pins: dict) -> dict:
    """内部网的「引脚跨几行」分布（同 1 行 = 不需要跨行）。"""
    rp = pl["row_pitch_um"]
    hist = collections.Counter()
    for _net, pts in pins.items():
        if len(pts) < 2:
            continue
        hist[len({int(p[3] // rp) for p in pts})] += 1
    tot = sum(hist.values())
    return {"hist": dict(sorted(hist.items())), "n_int": tot,
            "same_row": hist.get(1, 0),
            "same_row_rate": (hist.get(1, 0) / tot) if tot else 0.0}


def in_row_probe(nl=None, cells: int = CASE_CELLS, cols: int = 24,
                 ch_um: float = 3.40) -> dict:
    """实测「开/关行内局部互联」的布通率与 DRC。

    `in_row=True` 时：同行网的所有引脚**共享一条 M4 列**（锚 = 最左引脚），
    其余引脚用 M3 水平段在自己的 y 上接过去。若几何允许，布通率应上升、DRC 应仍为 0。
    """
    if nl is None:
        nl = CT.build()["netlist"]

    def run(flag):
        def _f():
            pl = PN.place_real(nl, max_cells=cells, cols=cols, truncate_ok=True)
            rt = PN.route_block(nl, pl, in_row=flag)
            vr = DL.run_drc(PN.all_routing(rt))["violations"]
            n_int = len(rt["routed"]) + len(rt["unrouted"])
            return {"n_int": n_int, "n_routed": len(rt["routed"]),
                    "rate": (len(rt["routed"]) / n_int) if n_int else 0.0,
                    "n_drc": len(vr),
                    "drc_kinds": dict(collections.Counter(v[0] for v in vr)),
                    "n_in_row": rt["n_in_row"]}
        return _with_ch(ch_um, _f)

    off, on = run(False), run(True)
    return {"off": off, "on": on,
            "delta_routed": on["n_routed"] - off["n_routed"],
            "delta_drc": on["n_drc"] - off["n_drc"]}


def col_iter_probe(nl=None, cells: int = CASE_CELLS, cols: int = 24,
                   ch_um: float = 3.40, iters=ITER_GRID) -> list:
    """列分配迭代：用「实际轨号」替代「最高轨」重估 y 区间，能多布通几个网？"""
    if nl is None:
        nl = CT.build()["netlist"]
    out = []
    for it in iters:
        def _f():
            pl = PN.place_real(nl, max_cells=cells, cols=cols, truncate_ok=True)
            rt = PN.route_block(nl, pl, col_iters=it)
            return {"iters": int(it), "n_routed": len(rt["routed"]),
                    "n_no_column": rt["n_col_fail_no_column"],
                    "n_drc": len(DL.run_drc(PN.all_routing(rt))["violations"])}
        out.append(_with_ch(ch_um, _f))
    return out


def channel_saturation(nl=None, cells: int = CASE_CELLS, cols: int = 24,
                       ch_grid=CH_GRID) -> list:
    """通道高度继续加大：`T` 涨、布通率还涨吗？（验证「通道已不是瓶颈」）"""
    if nl is None:
        nl = CT.build()["netlist"]
    out = []
    for ch in ch_grid:
        def _f():
            pl = PN.place_real(nl, max_cells=cells, cols=cols, truncate_ok=True)
            rt = PN.route_block(nl, pl)
            n_int = len(rt["routed"]) + len(rt["unrouted"])
            ch_full = sum(1 for v in rt["ch_info"].values() if not v["routable"])
            return {"ch_um": float(ch), "t_tracks": pl["t_tracks"],
                    "n_routed": len(rt["routed"]),
                    "rate": (len(rt["routed"]) / n_int) if n_int else 0.0,
                    "n_channel_full": int(ch_full),
                    "n_drc": len(DL.run_drc(PN.all_routing(rt))["violations"])}
        out.append(_with_ch(ch, _f))
    return out


def supply_demand(nl=None, cells: int = CASE_CELLS, ch_um: float = 3.40,
                  cols_grid=COLS_GRID) -> list:
    """列**供给**（ncol）vs 同行引脚**需求**（每行最大引脚数）—— 比值是不是常数。"""
    if nl is None:
        nl = CT.build()["netlist"]
    out = []
    for cols in cols_grid:
        def _f():
            pl = PN.place_real(nl, max_cells=cells, cols=cols, truncate_ok=True)
            rt = PN.route_block(nl, pl)
            ncol = int((pl["die_w_um"] - PN.W) // PN.PITCH) + 1
            allp = [(x, y) for pts in rt["pins"].values() for (_i, _p, x, y) in pts]
            per = collections.Counter(int(y // pl["row_pitch_um"]) for (_x, y) in allp)
            mx = max(per.values()) if per else 0
            n_int = len(rt["routed"]) + len(rt["unrouted"])
            return {"cols": int(cols), "rows": int(pl["rows"]), "n_col": ncol,
                    "max_per_row": int(mx),
                    "ratio": (ncol / mx) if mx else 0.0,
                    "n_routed": len(rt["routed"]),
                    "rate": (len(rt["routed"]) / n_int) if n_int else 0.0,
                    "n_no_column": rt["n_col_fail_no_column"],
                    "n_channel_full": sum(1 for v in rt["ch_info"].values()
                                          if not v["routable"])}
        out.append(_with_ch(ch_um, _f))
    return out


DINROW_DISCLOSURE = {
    "what": "行内局部布线的可行性判定 + 「87% 渐近线」的量化归因",
    "claimable": False,
    "not_a_solution": True,
    "limits": [
        "这是**负结果**：行内局部布线在当前单元几何下不可行（M3 必撞、M2 只有 1 条轨道），"
        "**不是**说「行内布线在真实设计里也不行」—— 真实 std-cell 的 pin access 靠 M2 局部绕行，"
        "但那是**单元库自带**的（本仓 dcells 的 M2 只在 pin access 处有焊盘）",
        "渐近线 87% 依赖本实现的**星形拓扑**（每网一条 M3 trunk + 每引脚一条 M4 竖线）；"
        "换 Steiner/多干拓扑后这条线会变",
        "「供给/需求比恒定」是在**同一网表前 N 门**上测的，网序变化会让比值小幅漂移（实测 1.33–1.43）",
        "本模块只做**可行性判定与归因**，不提供行内布线实现（因为它被证伪了）",
        "不宣称可制造 / 可流片；规则集自建 LDA-DEMO45，非 foundry PDK",
        "净增 0 锚（计数与比值 ⇒ resid≡0）⇒ 门禁形态",
    ],
}
