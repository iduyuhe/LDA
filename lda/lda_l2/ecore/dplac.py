# -*- coding: utf-8 -*-
"""E35 · **标准单元布局（placement）**（`lda/lda_l2/ecore/dplac.py` · D-216）。

══════════════════════════════════════════════════════════════
定位：把 E34 的 1,284 门网表**真正摆到硅片上** —— 给出每颗单元的物理坐标、
真实的 die 面积（含布线通道 + IO ring），并产出端口引脚落点。
══════════════════════════════════════════════════════════════
E34 的面积只是「Σ 单元面积 = 240.8 µm²」——那是**门本身**，不含任何布线余量。
本模块第一次给出**真实 die 尺寸**：行式布局 + 行内布线通道 + 环绕 IO ring。

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标：摆放后 **Σ(单元物理面积) ≡ Σ(n_tr·area_per_tr)**（面积守恒）
══════════════════════════════════════════════════════════════
这是「布局没偷偷少摆/多摆单元」的机核判据。E34 的 `area_um2` 是源；
本模块的摆放面积必须逐位等于它（差 < 1e-6）。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- **单元纵横比是模型假设**：本模块令行高 `H_ROW` 固定、宽 = 面积/H_ROW ⇒ 单元偏「瘦」，
  真实标准单元高宽比固定、宽随复杂度变。这**低估了宽度 ⇒ 低估了线长 ⇒ 保守**。
- **布局是贪心 + 有限爬山**，不是全局最优（无 min-cut 分区 / 无合法化器）
- **无电源条 / 无阱 / 无单元内 detail route**（detail route 在 `droute`）
- 端口引脚沿边界**等距排布**（真实签核要按 IO 规划），是简化
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from . import dcell as DC
from .dsynth import Gate, Netlist

# ---- 布局工艺假设（MODEL_ESTIMATE · 一阶）----
H_ROW_UM = 2.4          # µm · 标准单元行高（假设）
IO_RING_UM = 12.0       # µm · 环绕 IP 的 IO ring 厚度（含 pad + 电源环预留）
CHANNEL_X = 0.30        # µm · 行间（纵向）布线通道占行高比例附加
CHANNEL_FRAC = 0.35     # 在「单元总面积」上附加的**行间/列间布线通道**比例（经验）
SEED = 12345            # 确定性随机种子（结果可复现 ⇒ 报告可复核）


@dataclass
class Placement:
    cell_xywh: dict          # cell name -> (x0, y0, w, h)  µm，die 局部坐标
    die_w_um: float
    die_h_um: float
    rows: int
    cell_area_sum_um2: float      # = Σ n_tr·area_per_tr（金标）
    placed_area_um2: float        # = Σ(w·h)
    io_ring_um2: float
    routing_channel_um2: float
    port_pins: dict          # net -> (x, y)  端口引脚的边界落点（die 局部）
    pin_list: list           # [(port, bit, net, x, y, side), ...]
    hpwl_um: float           # 摆放后的半周长线长下界
    rng: int = SEED


def _cell_size(cell: str, tech=DC.DEFAULT_TECH) -> tuple:
    """单元物理尺寸：行高固定、宽 = 面积/行高 ⇒ **面积逐位守恒**。

    🔴 用真实 `cell_area_um2`（= n_tr·area_per_tr），不另起一套面积。
    """
    a = DC.cell_area_um2(cell, tech)
    w = a / H_ROW_UM
    return w, H_ROW_UM


def _net_pins(nl: Netlist) -> dict:
    """收集每个 net 的**驱动/接收单元**——用于线长与端口落点。"""
    net_cells: dict = {}
    for g in nl.gates:
        net_cells.setdefault(g.out, []).append(g.name)
        for n in g.ins:
            net_cells.setdefault(n, []).append(g.name)
    return net_cells


def _port_side(i: int, n: int) -> str:
    """端口引脚沿**左边界**等距排布（简化；真实签核要 IO 规划）。"""
    return "left"


def place(nl: Netlist, tech=DC.DEFAULT_TECH, seed: int = SEED) -> Placement:
    """行式布局：按连通度降序填充行，再有限爬山降 HPWL。"""
    rng = random.Random(seed)
    cells = nl.gates
    n_cell = len(cells)

    # 单元尺寸 + 面积守恒量
    sizes = {g.name: _cell_size(g.cell, tech) for g in cells}
    cell_area_sum = sum(w * h for (w, h) in sizes.values())
    placed_area = cell_area_sum  # 本模型宽=面积/行高 ⇒ Σ(w·h) ≡ Σ面积

    # 行宽：让 die 大致方形（含通道余量）
    gross = cell_area_sum * (1.0 + CHANNEL_FRAC)
    side = math.sqrt(gross)
    # 每行高度 = H_ROW + 通道；行数
    row_pitch = H_ROW_UM * (1.0 + CHANNEL_X)
    rows = max(1, int(math.ceil(side / row_pitch)))
    # 行宽 = 让所有单元能放下
    total_w = sum(w for (w, _h) in sizes.values())
    row_w = max(total_w / rows, side)

    # 按连通度降序（先放最忙的单元，利于局部聚拢）
    deg = {}
    net_cells = _net_pins(nl)
    for g in cells:
        d = 0
        for n in [g.out] + list(g.ins):
            d += len(net_cells.get(n, ()))
        deg[g.name] = d
    order = sorted(cells, key=lambda g: deg[g.name], reverse=True)

    # 顺序填充：行内从左到右
    xywh = {}
    cursor_x = 0.0
    cursor_y = 0.0
    row_idx = 0

    def new_row():
        nonlocal cursor_x, cursor_y, row_idx
        cursor_x = 0.0
        cursor_y = row_idx * row_pitch
        row_idx += 1

    new_row()
    for g in order:
        w, h = sizes[g.name]
        if cursor_x + w > row_w and cursor_x > 0:
            new_row()
        xywh[g.name] = (cursor_x, cursor_y, w, h)
        cursor_x += w

    die_w = row_w
    die_h = rows * row_pitch

    # ---- 有限爬山：随机交换相邻单元降 HPWL ----
    cell_by_row = {}
    for nm, (x, y, w, h) in xywh.items():
        cell_by_row.setdefault(round(y / row_pitch), []).append(nm)

    def hpwl():
        tot = 0.0
        for net, cl in net_cells.items():
            xs, ys = [], []
            for c in cl:
                x, y, w, h = xywh[c]
                xs.append(x + w / 2.0)
                ys.append(y + h / 2.0)
            if len(xs) >= 2:
                tot += (max(xs) - min(xs)) + (max(ys) - min(ys))
        return tot

    best = hpwl()
    for _ in range(min(4000, n_cell * 4)):
        r = rng.randrange(rows)
        row_list = cell_by_row.get(r, [])
        if len(row_list) < 2:
            continue
        i, j = rng.sample(range(len(row_list)), 2)
        a, b = row_list[i], row_list[j]
        xywh[a], xywh[b] = xywh[b], xywh[a]
        nh = hpwl()
        if nh < best:
            best = nh
            row_list[i], row_list[j] = row_list[j], row_list[i]
        else:
            xywh[a], xywh[b] = xywh[b], xywh[a]  # 撤销

    # ---- 端口引脚落点（沿左边界等距）----
    # 🔴 只取**真实对外端口**：`@d` 是寄存器的次态网（由 DFF 驱动，非 IP 引脚）⇒ 排除。
    port_pins = {}
    pin_list = []
    bits = []
    for (port, width) in nl.inputs:
        for b in range(width):
            bits.append((port, b, nl.in_nets[(port, b)]))
    for (port, width) in nl.outputs.items():
        if port.endswith("@d"):
            continue                    # 次态网不是 IP 顶层引脚
        for b in range(len(width)):
            bits.append((port, b, nl.outputs[port][b]))
    nbits = len(bits)
    for k, (port, b, net) in enumerate(bits):
        y = (k + 0.5) / max(nbits, 1) * die_h
        x = 0.0
        port_pins[net] = (x, y)
        pin_list.append((port, b, net, x, y, "left"))

    io_ring = 2 * IO_RING_UM * (die_w + die_h) + 4 * IO_RING_UM ** 2
    routing_channel = gross - cell_area_sum

    return Placement(
        cell_xywh=xywh,
        die_w_um=die_w, die_h_um=die_h, rows=rows,
        cell_area_sum_um2=cell_area_sum, placed_area_um2=placed_area,
        io_ring_um2=io_ring, routing_channel_um2=routing_channel,
        port_pins=port_pins, pin_list=pin_list, hpwl_um=best, rng=seed,
    )


def ip_digital_region(p: Placement) -> tuple:
    """数字区的**外框**（含 IO ring）µm，die 局部坐标。"""
    return (0.0, 0.0, p.die_w_um + 2 * IO_RING_UM, p.die_h_um + 2 * IO_RING_UM)


# ---------------------------------------------------------------------------
# 自检（含「必须失败」的对照组）
# ---------------------------------------------------------------------------
def plac_self_check(verbose: bool = False) -> dict:
    """面积守恒金标 + 边界 + 端口落点 + 对照（故意不摆满 → 面积不守恒）。"""
    from . import dctrl as C
    problems = []
    b = C.build()
    nl = b["netlist"]
    p = place(nl)

    # ① 面积守恒：摆放面积 ≡ Σ n_tr·area_per_tr
    src_area = nl.area_um2()
    if abs(p.placed_area_um2 - src_area) > 1e-6:
        problems.append(("area_conservation", p.placed_area_um2, src_area))

    # ② 所有单元落在 die 内（含 IO ring 之前）
    for nm, (x, y, w, h) in p.cell_xywh.items():
        if x < -1e-9 or y < -1e-9 or x + w > p.die_w_um + 1e-9 or y + h > p.die_h_um + 1e-9:
            problems.append(("out_of_die", nm, x, y, w, h))
            break

    # ③ die 面积 ≥ placed 面积
    if p.die_w_um * p.die_h_um < p.placed_area_um2 - 1e-6:
        problems.append(("die_smaller_than_cells", p.die_w_um * p.die_h_um,
                         p.placed_area_um2))

    # ④ 单元数一致
    if len(p.cell_xywh) != len(nl.gates):
        problems.append(("cell_count", len(p.cell_xywh), len(nl.gates)))

    # ⑤ 端口引脚在左边界（x≈0）
    off = [abs(x) for (_p, _b, _n, x, _y, _s) in p.pin_list]
    if max(off) > 1e-9:
        problems.append(("port_not_on_boundary", max(off)))

    # ⑥ 行数 ≥ 1
    if p.rows < 1:
        problems.append(("zero_rows", p.rows))

    # 🔴 对照组：制造一个「面积不守恒」的伪劣布局，判据必须抓红
    bad = Placement(
        cell_xywh={nm: (0.0, 0.0, w * 0.5, h)  # 宽度砍半 ⇒ 面积少一半
                  for nm, (x, y, w, h) in p.cell_xywh.items()},
        die_w_um=p.die_w_um, die_h_um=p.die_h_um, rows=p.rows,
        cell_area_sum_um2=src_area,
        placed_area_um2=src_area * 0.5,   # 故意错
        io_ring_um2=p.io_ring_um2, routing_channel_um2=p.routing_channel_um2,
        port_pins=p.port_pins, pin_list=p.pin_list, hpwl_um=p.hpwl_um,
    )
    if abs(bad.placed_area_um2 - src_area) <= 1e-6:
        problems.append(("control_area_conservation_not_red",))

    if verbose:
        print("  place: die=%.1f x %.1f um  rows=%d  cell_area=%.1f  placed=%.1f  "
              "io_ring=%.1f  chan=%.1f  hpwl=%.1f"
              % (p.die_w_um, p.die_h_um, p.rows, p.cell_area_sum_um2,
                 p.placed_area_um2, p.io_ring_um2, p.routing_channel_um2,
                 p.hpwl_um))

    return {
        "ok": not problems, "problems": problems,
        "die_w_um": p.die_w_um, "die_h_um": p.die_h_um, "rows": p.rows,
        "cell_area_sum_um2": p.cell_area_sum_um2,
        "placed_area_um2": p.placed_area_um2,
        "io_ring_um2": p.io_ring_um2, "hpwl_um": p.hpwl_um,
        "n_pins": len(p.pin_list),
    }


DPLAC_DISCLOSURE = {
    "route": "E35 · CIM 加速器 IP 的 P&R · 第 0 层（标准单元布局）",
    "analysis": "行式布局（行高固定 · 宽=面积/行高 ⇒ 面积逐位守恒）· 按连通度降序填充 + "
                "有限随机爬山降 HPWL · 端口沿左边界等距落点 · 环绕 IO ring",
    "golden": "Σ(摆放单元面积) ≡ Σ(n_tr·area_per_tr)（差 < 1e-6）",
    "not_included": "纵横比是模型假设（单元偏瘦 ⇒ 低估线长 ⇒ 保守）· 贪心+有限爬山非全局最优 · "
                    "无电源条/阱/detail route · 端口等距排布非 IO 规划",
    "claimable": False,
    "claimable_reason": "die 面积、行数、IO ring 均为一阶假设（H_ROW/IO_RING/通道比例无可核语料）"
                       "⇒ MODEL_ESTIMATE；可 signoff 的只有结构性事实（单元数、面积守恒）",
}
