"""B2 · 完整 detail route —— **真实单元引脚 + 轨道容量律 + DRC 零违规**（与 A2 多 track 协同）。

═══════════════════════════════════════════════════════════════════════════════
B2 与 E37 `ddetail.track_route` 的差别（为什么不是重复实现）
───────────────────────────────────────────────────────────────────────────────
E37 的 `track_route` 已经做了「H 段按区间着色分配到 M3 轨道」。它有两个**结构性简化**：

  ① **引脚取自单元中心**（`_net_pins` 用 `p.cell_xywh` 的中心）—— 真实单元的输入/输出
     引脚在**左边界**与内部竖 strap 上，不在几何中心；
  ② **容量不设上界**：`interval_color` 有几段就分几条轨道，从不过问
     「这个通道放不放得下」——于是「布不通」这件事在抽象里根本不可能发生
     （E38f/E38g 的整条负结果正是从「资源不设限/设限后崩塌」来的）。

B2 把这两点补上：

  · 引脚 = `dcells` 的**真实引脚矩形**（左边界 A/B、内部 Y strap），取边界接入点；
  · 容量 = `dmtrack.channel_density`（A2）给出的**所需轨道数 d**，左边界算法分配；
    通道只有 T 条轨道，**T < d ⇒ 该通道布不通**（不是"多画几条"）；
  · 布完直接跑 `ddrc_lvs.run_drc`（M3/M4 线宽间距 + VIA2 包围），要求**零违规**；
  · 同时给出 E37 式「中心点 + 同 y 集中走线」的**基线**做对照 —— 同一网表下基线必然违规。

═══════════════════════════════════════════════════════════════════════════════
诚实边界
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **两层通道模型**（M3 横 / M4 竖 / VIA2 弯角），不是通用迷宫/多层路由器；
   不做 rip-up，不优化线长，只做**容量可行 + DRC 干净**。
2. 🔴 **单元内 M1 引脚到 M3 的 via 串沿用 E37 约定**（`real_cell_geom` 的 M1→M2→M3 堆叠），
   本模块只负责 M3/M4 段；via 串联的失效面已在 E33 量化（via 串联 6）。
3. 🔴 网表/布局是小规模**演示用例**（4+4 单元），不是真实设计的布线结果；
   不宣称可布通率、不报面积/能效。
4. 🔴 `claimable=False`：几何/容量结论是整数与闭式，**净增 0 锚**（门禁形态，同 E39/E40）。
"""
from __future__ import annotations

from dataclasses import dataclass

from . import dcells as CL
from . import ddetail as DD
from . import dmtrack as MT
# ---- 与 ddetail 保持同一套金属/通孔口径 ----
W = DD.W_ROUTE                 # 0.24 µm 线宽
VIA = DD.VIA                   # 0.20 µm 通孔
ENC = DD.ENC                   # 0.02 µm 包围
PITCH = DD.TRACK_PITCH         # 0.36 µm 轨道间距（> W + S_MIN = 0.34）
LAND = VIA / 2.0 + ENC + 0.01  # landing pad 半宽

CELL_GAP = 0.60                # 单元之间的水平通道宽（µm）
ROW_CHANNEL = 2.00             # 行间水平通道高（µm）


@dataclass(frozen=True)
class Placed:
    """一个已放置单元：名字 + 左下角坐标（µm）。"""
    name: str
    x0: float
    y0: float

    @property
    def cell(self) -> CL.Cell:
        return CL.CELLS[self.name]()

    @property
    def w(self) -> float:
        return self.cell.w / 1000.0

    @property
    def h(self) -> float:
        return self.cell.h / 1000.0


def train_tracks(y0: float, height: float) -> int:
    """通道内可容纳的轨道数（扣除两边界半个线宽后按 pitch 排）。"""
    usable = height - W
    return max(0, int(usable / PITCH) + 1)


# ═══════════════════════════════════════════════════════════════════════════
# ① 布局与真实引脚
# ═══════════════════════════════════════════════════════════════════════════
def place_rows(bottom, top) -> dict:
    """两行布局：底行 y=0，行间通道 ROW_CHANNEL，顶行其上。单元间留 CELL_GAP。"""
    out, x = [], 0.0
    for nm in bottom:
        out.append(Placed(nm, x, 0.0))
        x += CL.CELLS[nm]().w / 1000.0 + CELL_GAP
    y_top = max(p.h for p in out) + ROW_CHANNEL
    x = 0.0
    for nm in top:
        out.append(Placed(nm, x, y_top))
        x += CL.CELLS[nm]().w / 1000.0 + CELL_GAP
    return {"cells": out,
            "row0_top": max(p.h for p in out if p.y0 == 0.0),
            "row1_y": y_top,
            "channel": (max(p.h for p in out if p.y0 == 0.0), y_top)}


def pin_point(p: Placed, net: str) -> tuple:
    """真实引脚的**接入点**（µm，绝对坐标）。

    · `A` / `B`：引脚矩形贴在左边界 ⇒ 接入点取左边界中点（走线从此向左/向上出）；
    · `Y`：内部竖 strap ⇒ 接入点取 strap 中心（M4 从上方接进来）；
    · `VDD` / `VSS`：电源轨，本模块不布（属电源网）。

    🔴 与 E37 的关键差别：这里**不是单元几何中心**。INV 的 A 在 x=x0（左边界），
       Y 在 x=x0+0.4425；两者相差 0.44µm —— 中心点路由会把这两者都当成 x0+0.31，
       于是线长与冲突位置都算错。
    """
    c = p.cell
    r = c.pins[net]
    if net in ("A", "B"):
        return (p.x0, p.y0 + (r.y0 + r.y1) / 2000.0)
    return (p.x0 + (r.x0 + r.x1) / 2000.0, p.y0 + (r.y0 + r.y1) / 2000.0)


def center_point(p: Placed, net: str) -> tuple:
    """E37 式基线的引脚口径：一律取**单元几何中心**（错误口径，仅用于对照）。"""
    return (p.x0 + p.w / 2.0, p.y0 + p.h / 2.0)


# ═══════════════════════════════════════════════════════════════════════════
# ② 演示网表
# ═══════════════════════════════════════════════════════════════════════════
def build_case() -> dict:
    """4+4 单元、4 条跨行网的演示用例。

    刻意把跨行连成**交叉**（Y0→A2 / Y1→A3 / Y2→A0 / Y3→A1）——这样四条网的
    x 区间高度重叠，行间通道的所需轨道数 d 会 >1，容量律才有对象。
    """
    lay = place_rows(["INV_X1"] * 4, ["INV_X1"] * 4)
    bot = [c for c in lay["cells"] if c.y0 == 0.0]
    top = [c for c in lay["cells"] if c.y0 > 0.0]
    pairs = [(bot[0], "Y", top[2], "A"),
             (bot[1], "Y", top[3], "A"),
             (bot[2], "Y", top[0], "A"),
             (bot[3], "Y", top[1], "A")]
    nets = []
    for k, (pa, na, pb, nb) in enumerate(pairs):
        nets.append({"name": "n%d" % k,
                     "a": pin_point(pa, na), "b": pin_point(pb, nb),
                     "a_c": center_point(pa, na), "b_c": center_point(pb, nb)})
    return {"layout": lay, "nets": nets,
            "channel": lay["channel"],
            "t_tracks": train_tracks(lay["channel"][0], ROW_CHANNEL)}


# ═══════════════════════════════════════════════════════════════════════════
# ③ 路由（轨道分配 + 容量判定）
# ═══════════════════════════════════════════════════════════════════════════
def _seg(layer: int, x0: float, y0: float, x1: float, y1: float, net: str, kind: str):
    return DD._rect(layer, x0, y0, x1, y1, net=net, kind=kind)


def _corner(shapes: list, x: float, y: float, net: str) -> None:
    """弯角：VIA2 + M3/M4 landing（保证两侧金属各自包围 ≥ ENC）。"""
    shapes.append(_seg(DD.L_VIA2, x - VIA / 2.0, y - VIA / 2.0,
                       x + VIA / 2.0, y + VIA / 2.0, net, "via"))
    shapes.append(_seg(DD.L_M3, x - LAND, y - W / 2.0, x + LAND, y + W / 2.0, net, "metal"))
    shapes.append(_seg(DD.L_M4, x - W / 2.0, y - LAND, x + W / 2.0, y + LAND, net, "metal"))


def route(case: dict, t_avail: int | None = None):
    """两层通道路由：M4 竖（引脚 → 行间通道）+ M3 横（通道内按轨道）。

    返回 {shapes, assignments, d, t_avail, routed, unrouted, wire_um}。
    """
    ch = case["channel"]
    y_lo, y_hi = ch
    t_avail = case["t_tracks"] if t_avail is None else t_avail
    nets = case["nets"]

    # ① 容量：行间通道的所需轨道数 d（A2 的通道密度，与 E39 同一实现）
    ivs = [(min(n["a"][0], n["b"][0]), max(n["a"][0], n["b"][0])) for n in nets]
    ivs_nm = [(int(round(a * 1000)), int(round(b * 1000))) for (a, b) in ivs]
    d = MT.channel_density(ivs_nm)
    need, assign = MT.left_edge_tracks(
        [(l, r, n["name"]) for n, (l, r) in zip(nets, ivs_nm)])

    shapes: list = []
    routed, unrouted = [], []
    wire = 0.0
    # 轨道 y：通道内自下而上按 pitch 排；超出 T 的分配到「越界轨道」并判布不通
    y_base = y_lo + W / 2.0 + 0.02
    for (k, tr, nm) in assign:
        net = next(n for n in nets if n["name"] == nm)
        if tr >= t_avail:
            unrouted.append((nm, tr, t_avail))
            continue
        yh = y_base + tr * PITCH
        ax, ay = net["a"]
        bx, by = net["b"]
        # M4 竖：引脚 A → 轨道
        shapes.append(_seg(DD.L_M4, ax - W / 2.0, min(ay, yh), ax + W / 2.0, max(ay, yh), nm, "metal"))
        # M4 竖：引脚 B → 轨道
        shapes.append(_seg(DD.L_M4, bx - W / 2.0, min(by, yh), bx + W / 2.0, max(by, yh), nm, "metal"))
        # M3 横：轨道上跨接两竖
        shapes.append(_seg(DD.L_M3, min(ax, bx) - W / 2.0, yh - W / 2.0,
                           max(ax, bx) + W / 2.0, yh + W / 2.0, nm, "metal"))
        _corner(shapes, ax, yh, nm)
        _corner(shapes, bx, yh, nm)
        routed.append(nm)
        wire += abs(ax - bx) + abs(ay - yh) + abs(by - yh)
    return {"shapes": shapes, "assignments": assign, "d": d, "t_avail": t_avail,
            "routed": routed, "unrouted": unrouted, "wire_um": wire, "need": need}


def route_center_baseline(case: dict):
    """E37 式基线：引脚取单元中心、H 段压在引脚 y 上（不做轨道分配）。

    这条基线正是 E36 报「baseline DRC=204,320」的成因：不同网的水平段落在同一 y
    ⇒ 同层异网重叠。此处用于**对照证明**「真实引脚 + 轨道分配」确实更好。
    """
    shapes: list = []
    for n in case["nets"]:
        ax, ay = n["a_c"]
        bx, by = n["b_c"]
        shapes.append(_seg(DD.L_M4, ax - W / 2.0, min(ay, by), ax + W / 2.0, max(ay, by),
                           n["name"], "metal"))
        shapes.append(_seg(DD.L_M3, min(ax, bx) - W / 2.0, ay - W / 2.0,
                           max(ax, bx) + W / 2.0, ay + W / 2.0, n["name"], "metal"))
        _corner(shapes, ax, ay, n["name"])
    return {"shapes": shapes}


# ═══════════════════════════════════════════════════════════════════════════
# ④ 连通性（按层感知：M3/M4 只在 VIA2 处相连）
# ═══════════════════════════════════════════════════════════════════════════
def net_components(shapes: list) -> dict:
    """每个网的**连通分量数**（M3/M4 仅经 VIA2 连接；同层相接即连）。"""
    out: dict = {}
    for net in {s.net for s in shapes if s.net}:
        ss = [s for s in shapes if s.net == net]
        n = len(ss)
        p = list(range(n))

        def find(i):
            while p[i] != i:
                p[i] = p[p[i]]
                i = p[i]
            return i

        def union(i, j):
            a, b = find(i), find(j)
            if a != b:
                p[a] = b

        for i in range(n):
            for j in range(i + 1, n):
                a, b = ss[i], ss[j]
                if a.kind == "via" or b.kind == "via":
                    if DD.rects_overlap(a, b, inflate=1e-9):
                        union(i, j)
                elif a.layer == b.layer and DD.rects_overlap(a, b, inflate=1e-9):
                    union(i, j)
        out[net] = len({find(i) for i in range(n)})
    return out


def dcroute_self_check() -> dict:
    """结构自检（不含 DRC —— DRC 由门禁调 `ddrc_lvs.run_drc`，同一套口径）。"""
    case = build_case()
    r = route(case)
    return {"d": r["d"], "t_avail": r["t_avail"], "need": r["need"],
            "routed": len(r["routed"]), "unrouted": r["unrouted"],
            "n_shapes": len(r["shapes"]), "wire_um": round(r["wire_um"], 3),
            "components": net_components(r["shapes"])}


B2_DISCLOSURE = {
    "what": "真实单元引脚 + 轨道容量律（T ≥ d）+ 两层通道路由 + DRC 零违规",
    "layers": "M3 横 / M4 竖 / VIA2 弯角（与 E37 同栈）",
    "not_general_router": True,
    "no_ripup": True,
    "pin_access_note": "单元内 M1→M3 的 via 串沿用 E37 real_cell_geom 约定（失效面见 E33）",
    "claimable": False,
}
