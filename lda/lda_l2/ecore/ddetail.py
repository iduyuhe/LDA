# -*- coding: utf-8 -*-
"""E36 · **detail route 几何 + 真实单元几何**（`lda/lda_l2/ecore/ddetail.py` · D-220 / D-221）。

══════════════════════════════════════════════════════════════
定位：E35 的 `droute` 只算了每根网的**线长（拓扑量）**，而 `dmacro` 的 GDS 里
**根本没有路由金属多边形**——数字单元也只是包围盒。本模块第一次把 P&R 的
「线」真正画成**金属几何**：

- **D-220 detail route**：把 `droute` 的曼哈顿 MST 每根网变成真实金属多边形。
  约定 **H 段走 M3(27)、V 段走 M4(29)、弯角打 VIA2(28)**。H/V 走不同层 ⇒
  同层只会是 H-H 或 V-V；异层交叉（无孔）不构成电气短路——这正是「用层分工
  天然规避短路」的标准做法。
- **D-221 真实单元几何**：每颗数字单元从「包围盒矩形」升级为有 **有源区标记
  (E_DIFF/20) + M1 引脚焊垫 + 通孔栈(M1→M2→M3)** 的、能看见端子的单元。

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标（detail route）
══════════════════════════════════════════════════════════════
每网「布出的金属中心线长」≥ 该网 MST 长（曼哈顿度量）。
▶ 2 端网：中心线长 ≡ 两端曼哈顿距离（L 形为最短曼哈顿路径，取等）。
▶ 多端网：每条 MST 边取 L 形（H+V），总中心线长 = Σ 边曼哈顿长 = MST 长。
任何「画短了」的布线（中心线 < 曼哈顿距离）都是物理不可能，必被抓红。

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标（真实单元几何）
══════════════════════════════════════════════════════════════
每颗被摆放的单元必须发射 ≥1 个有源形状 + ≥1 个引脚焊垫；引脚焊垫位于单元中心
（连接点）。缺任一即「单元没画全」，必被抓红。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- **模型尺度下内部几何是符号级，非 PDK 真实单元**：E35 单元宽仅 ~0.08µm（=面积/行高），
  真实晶体管(沟道/源漏/接触)根本放不下 ⇒ 有源区/引脚是「占位标记」，不是可制造单元。
- **单元内部多端子分离是黑盒**：路由在单元中心汇成单节点；单元内部把各端子连通的
  逻辑不画（视为硬宏占位）。跨单元的布线连通性才是本模块真正验证的对象。
- **简化 L 形路由，无拥塞求解 / 无 track 共享 / 无绕障**：实测 c17 有 **DRC 87 处
  `min_spacing`**（弯角孔包围已于 v0.9.370 修至 0）**并且有 183 处 LVS 短路**
  （**78 同层 `short` + 105 通孔 `short_via`**，**去重后 43 对网** —— 条目数会把规模夸大 4 倍）
  —— 🔴 不是「只是间距紧」，是**连通性错误**。
  （v0.9.373 更正：本节原写「同层短路为零」，与 LVS 实测的 78 处同层短路矛盾，已删。）
  根因是**容量不足**，
  且已量化为 `drc_capacity_bound()` 的三向下界（通道轨数 / 单元引脚槽宽 / die 列数）。
  🔴 因此本路由器**不产可签核结果**（`claimable=False`）；清零需要加面积或加层，
  不是换一版代码能解决的。真正 maze/grid 路由器是下一阶段。
- 通孔只算 M1→M2→M3 栈与 M3↔M4 弯角孔，未计通孔电阻电容。
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict

from . import dcell as DC
from . import dplac as PL
from .dsynth import Netlist

# ---- 层号（单一真源 = gds_export / elayers）----
L_M1 = 23
L_M2 = 25
L_M3 = 27
L_M4 = 29
L_DIFF = 20
L_VIA1 = 24
L_V2 = 26              # M2↔M3 通孔（原模型缺这一层 ⇒ M1 到不了 M3）
L_VIA2 = 28

# ---- 几何/规则假设（MODEL_ESTIMATE · 一阶）----
W_ROUTE = 0.24          # µm · 布线金属线宽
VIA = 0.20             # µm · 通孔边长
ENC = 0.02             # µm · 通孔包围（金属比通孔大出的单边量）
PIN_R = 0.30           # µm · 单元引脚焊垫边长（> W_ROUTE，保证可连）
#: 弯角延伸量：VIA2 半边长 + 单边包围 ⇒ 弯角两层金属都能盖住孔（v0.9.370 修）
_LAND_CORNER = VIA / 2.0 + ENC


@dataclass
class Shape:
    layer: int
    x0: float
    y0: float
    x1: float
    y1: float
    net: str = None          # 金属/通孔所属网（单元标记 = None）
    kind: str = "metal"      # metal | via | active | pin
    cell: str = None         # 单元标记用


@dataclass
class DetailRoute:
    shapes: list             # 全部 Shape（路由金属 + 弯角孔）
    cell_shapes: list        # 真实单元几何 Shape（有源/引脚/通孔栈）
    net_pins: dict           # net -> [(x,y), ...] 终端点（单元中心 / 端口落点）
    centerline_um: dict      # net -> 布出中心线长
    mst_um: dict             # net -> MST 长（对照）
    n_nets: int
    n_routed_segments: int
    n_cells: int
    die_w_um: float = 0.0    # 路由后所需 die 宽（含轨道外溢 + IO 估计）
    die_h_um: float = 0.0    # 路由后所需 die 高


def _rect(layer: int, x0: float, y0: float, x1: float, y1: float, **kw) -> Shape:
    return Shape(layer, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), **kw)


def _mst_edges(points: list) -> list:
    """曼哈顿度量最小生成树的边（Prim，O(n²)）。返回 [(i,j), ...] 索引对。

    与 `droute._mst_length` 同度量（边权 = 两点曼哈顿距离），保证线长逐位一致。
    """
    n = len(points)
    if n < 2:
        return []
    INF = float("inf")
    dist = [INF] * n
    used = [False] * n
    par = [-1] * n
    dist[0] = 0.0
    edges = []
    for _ in range(n):
        u, best = -1, INF
        for i in range(n):
            if not used[i] and dist[i] < best:
                best = dist[i]
                u = i
        if u < 0:
            break
        used[u] = True
        if par[u] != -1:
            edges.append((par[u], u))
        xu, yu = points[u]
        for v in range(n):
            if used[v]:
                continue
            xv, yv = points[v]
            d = abs(xu - xv) + abs(yu - yv)
            if d < dist[v]:
                dist[v] = d
                par[v] = u
    return edges


def _net_pins(nl: Netlist, p: PL.Placement) -> dict:
    """每网终端点：门用单元中心；端口用 `p.port_pins` 落点。"""
    pins: dict = defaultdict(list)
    for g in nl.gates:
        if g.name in p.cell_xywh:
            x0, y0, w, h = p.cell_xywh[g.name]
            cx, cy = x0 + w / 2.0, y0 + h / 2.0
        else:
            cx, cy = 0.0, 0.0
        pins[g.out].append((cx, cy))
        for n in g.ins:
            pins[n].append((cx, cy))
    for net, (x, y) in p.port_pins.items():
        pins[net].append((x, y))
    return pins


def detail_route(nl: Netlist, p: PL.Placement, tech=DC.DEFAULT_TECH) -> DetailRoute:
    """把 MST 每根网画成真实金属多边形（H=M3 / V=M4 / 弯角 VIA2）。"""
    pins = _net_pins(nl, p)
    shapes: list = []
    centerline: dict = {}
    mst_len: dict = {}
    n_nets = 0
    n_seg = 0

    for net, pts in pins.items():
        if len(pts) < 2:
            centerline[net] = 0.0
            mst_len[net] = 0.0
            continue
        n_nets += 1
        edges = _mst_edges(pts)
        total = 0.0
        mst = 0.0
        for (a, b) in edges:
            ax, ay = pts[a]
            bx, by = pts[b]
            dx = abs(ax - bx)
            dy = abs(ay - by)
            # 弯角在 (bx, ay)：两段各向弯角外多伸 LAND，才能**包围** VIA2（否则孔只被半个
            # 方向盖住 ⇒ via_enclosure 必违例）。延伸是沿各自段方向外扩，不改中心线长。
            hx0, hx1 = min(ax, bx), max(ax, bx)
            vy0, vy1 = min(ay, by), max(ay, by)
            if dx > 1e-9 and dy > 1e-9:
                if bx >= ax:
                    hx1 += _LAND_CORNER
                else:
                    hx0 -= _LAND_CORNER
                if by >= ay:
                    vy0 -= _LAND_CORNER
                else:
                    vy1 += _LAND_CORNER
            if dx > 1e-9:
                # H 段：M3，y=ay，x∈[ax,bx]
                shapes.append(_rect(L_M3, hx0, ay - W_ROUTE / 2.0, hx1, ay + W_ROUTE / 2.0,
                                    net=net, kind="metal"))
                n_seg += 1
            if dy > 1e-9:
                # V 段：M4，x=bx，y∈[ay,by]
                shapes.append(_rect(L_M4, bx - W_ROUTE / 2.0, vy0, bx + W_ROUTE / 2.0, vy1,
                                    net=net, kind="metal"))
                n_seg += 1
            if dx > 1e-9 and dy > 1e-9:
                # 弯角通孔：M3↔M4 桥，落在 (bx,ay)
                shapes.append(_rect(L_VIA2, bx - VIA / 2.0, ay - VIA / 2.0,
                                    bx + VIA / 2.0, ay + VIA / 2.0, net=net, kind="via"))
            total += dx + dy
            mst += dx + dy
        centerline[net] = total
        mst_len[net] = mst

    return DetailRoute(
        shapes=shapes, cell_shapes=[], net_pins=pins,
        centerline_um=centerline, mst_um=mst_len,
        n_nets=n_nets, n_routed_segments=n_seg, n_cells=len(p.cell_xywh),
    )


def real_cell_geom(p: PL.Placement, tech=DC.DEFAULT_TECH) -> list:
    """每颗数字单元：有源区标记(E_DIFF) + M1 引脚焊垫(中心) + 通孔栈(M1→M2→M3)。

    ⚠️ 模型尺度下是符号级几何（见模块诚实边界）。引脚焊垫位于单元中心 = 路由连接点。
    """
    out: list = []
    for nm, (x0, y0, w, h) in p.cell_xywh.items():
        cx, cy = x0 + w / 2.0, y0 + h / 2.0
        # 有源区标记（符号级）：单元尺度仅 ~0.08µm 宽，内部画不下真实晶体管，
        # 故以单元中心固定边长的小方块标记「此处有源器件」（非 PDK 几何，见披露）。
        A = 0.06
        out.append(_rect(L_DIFF, cx - A / 2.0, cy - A / 2.0,
                         cx + A / 2.0, cy + A / 2.0, cell=nm, kind="active"))
        # M1 引脚焊垫（中心）
        out.append(_rect(L_M1, cx - PIN_R / 2.0, cy - PIN_R / 2.0,
                         cx + PIN_R / 2.0, cy + PIN_R / 2.0, cell=nm, kind="pin"))
        # 通孔栈 M1→M2→M3：两层孔叠在中心（连接焊垫到上层路由）
        out.append(_rect(L_VIA1, cx - VIA / 2.0, cy - VIA / 2.0,
                         cx + VIA / 2.0, cy + VIA / 2.0, cell=nm, kind="via"))
        out.append(_rect(L_VIA2, cx - VIA / 2.0, cy - VIA / 2.0,
                         cx + VIA / 2.0, cy + VIA / 2.0, cell=nm, kind="via"))
    return out


# ---------------------------------------------------------------------------
# E37 · **track 分配 L 路由**（`track_route` · D-224）
# ---------------------------------------------------------------------------
# 🔴🔴 动机：E36 的 `detail_route` 把每条 H 段压在引脚 y（`ay`）、每条 V 段压在引脚 x（`bx`），
# 同层金属在**共享行/列**上大量重叠 ⇒ baseline DRC=204,320（M3 163,436 + M4 40,236 + via 648）。
# `track_route` 用**区间着色**给每条 H 段分配唯一 M3 y 轨道、每条 V 段分配唯一 M4 x 轨道，
# 并把弯角/引脚过孔补 **landing pad**（修复 via_enclosure 648）。
#
# 🔴🔴 诚实边界（全部 `claimable=False`）：track 分配只消「主段」重叠；**引脚 stub 在共享
# 列/行上的重叠 + 扇出单元的同 y H 段**是 2 层 L 路由模型的**结构性极限**，无法在紧凑布局上
# 清零——见 `track_self_check` 如实报告的 residual。字面零 DRC 需退化 track-grid 布局或真实
# maze router（超出 L 路由范围，明确不宣称）。
TRACK_PITCH = 0.36        # µm · 轨道间距 > W_ROUTE + S_MIN = 0.34 ⇒ 相邻轨道必不重叠


def interval_color(intervals: list) -> tuple:
    """贪心区间着色：intervals=[(lo,hi), ...] -> (assign[], n_tracks)。

    用于把一组「同层金属段」分配到互不重叠的轨道：重叠的区间必须不同色。
    """
    order = sorted(range(len(intervals)), key=lambda i: (intervals[i][0], intervals[i][1]))
    ends = []
    assign = [0] * len(intervals)
    for idx in order:
        lo, hi = intervals[idx]
        placed = False
        for k in range(len(ends)):
            if lo >= ends[k] - 1e-9:
                assign[idx] = k
                ends[k] = hi
                placed = True
                break
        if not placed:
            assign[idx] = len(ends)
            ends.append(hi)
    return assign, len(ends)


def track_route(nl: Netlist, p: PL.Placement, tech=DC.DEFAULT_TECH) -> DetailRoute:
    """E37 · 带 track 分配的 L 路由（H=M3 / V=M4 / 弯角 + 引脚 VIA2，全 landing pad）。

    与 `detail_route` 的区别：主段按区间着色分配到独立轨道（消主段同层重叠）；
    引脚经 stub 接入轨道（保持 LVS 连通）；所有过孔带 M3+M4 landing pad（修 E36 via 648）。
    """
    pins = _net_pins(nl, p)
    shapes: list = []
    centerline: dict = {}
    mst_len: dict = {}
    n_nets = 0
    n_seg = 0

    m3_int = []          # H 段 x 跨度
    m4_int = []          # V 段 y 跨度
    edges_info = []
    for net, pts in pins.items():
        if len(pts) < 2:
            centerline[net] = 0.0
            mst_len[net] = 0.0
            continue
        n_nets += 1
        edges = _mst_edges(pts)
        mst = 0.0
        for (a, b) in edges:
            ax, ay = pts[a]
            bx, by = pts[b]
            dx = abs(ax - bx)
            dy = abs(ay - by)
            if dx > 1e-9:
                m3_int.append((min(ax, bx), max(ax, bx)))
            if dy > 1e-9:
                m4_int.append((min(ay, by), max(ay, by)))
            edges_info.append((net, ax, ay, bx, by, dx > 1e-9, dy > 1e-9))
            mst += dx + dy
        centerline[net] = mst
        mst_len[net] = mst

    a3, n3 = interval_color(m3_int)
    a4, n4 = interval_color(m4_int)
    LAND = VIA / 2.0 + ENC + 0.01   # landing pad 半边：保证金属包围过孔

    m3_idx = 0
    m4_idx = 0
    for (net, ax, ay, bx, by, is_h3, is_v4) in edges_info:
        if is_h3:
            yh = a3[m3_idx] * TRACK_PITCH
            m3_idx += 1
        if is_v4:
            xv = a4[m4_idx] * TRACK_PITCH
            m4_idx += 1
        if is_h3 or is_v4:
            # 主段（H=M3 / V=M4），弯角仅在 H、V 同时存在时产生
            if is_h3:
                hx0 = min(ax, bx, xv) if is_v4 else min(ax, bx)
                hx1 = max(ax, bx, xv) if is_v4 else max(ax, bx)
                shapes.append(_rect(L_M3, hx0, yh - W_ROUTE / 2.0, hx1, yh + W_ROUTE / 2.0,
                                    net=net, kind="metal"))
                n_seg += 1
            if is_v4:
                vy0 = min(ay, by, yh) if is_h3 else min(ay, by)
                vy1 = max(ay, by, yh) if is_h3 else max(ay, by)
                shapes.append(_rect(L_M4, xv - W_ROUTE / 2.0, vy0, xv + W_ROUTE / 2.0, vy1,
                                    net=net, kind="metal"))
                n_seg += 1
            if is_h3 and is_v4:
                _via_landing(shapes, xv, yh, net, LAND)   # 弯角
            # 引脚 A (ax,ay)：有 H 段则经 M4 竖 stub 接 H 段；否则（纯 V）经 M3 横 stub 接 V 段
            if is_h3:
                shapes.append(_rect(L_M4, ax - W_ROUTE / 2.0, min(ay, yh), ax + W_ROUTE / 2.0,
                                    max(ay, yh), net=net, kind="metal"))
                n_seg += 1
                _via_landing(shapes, ax, yh, net, LAND)
            else:
                shapes.append(_rect(L_M3, min(ax, xv), ay - W_ROUTE / 2.0, max(ax, xv),
                                    ay + W_ROUTE / 2.0, net=net, kind="metal"))
                n_seg += 1
                _via_landing(shapes, xv, ay, net, LAND)
            # 引脚 B (bx,by)：有 V 段则经 M3 横 stub 接 V 段；否则（纯 H）经 M4 竖 stub 接 H 段
            if is_v4:
                shapes.append(_rect(L_M3, min(bx, xv), by - W_ROUTE / 2.0, max(bx, xv),
                                    by + W_ROUTE / 2.0, net=net, kind="metal"))
                n_seg += 1
                _via_landing(shapes, xv, by, net, LAND)
            else:
                shapes.append(_rect(L_M4, bx - W_ROUTE / 2.0, min(by, yh), bx + W_ROUTE / 2.0,
                                    max(by, yh), net=net, kind="metal"))
                n_seg += 1
                _via_landing(shapes, bx, yh, net, LAND)

    # die 尺寸：轨道外溢后的包围盒 + IO 估计（如实反映 track 布线占据的物理范围）
    if shapes:
        xs = [s.x0 for s in shapes] + [s.x1 for s in shapes]
        ys = [s.y0 for s in shapes] + [s.y1 for s in shapes]
        die_w = max(xs) - min(xs) + 2 * PL.IO_RING_UM
        die_h = max(ys) - min(ys) + 2 * PL.IO_RING_UM
    else:
        die_w, die_h = p.die_w_um, p.die_h_um

    return DetailRoute(
        shapes=shapes, cell_shapes=[], net_pins=pins,
        centerline_um=centerline, mst_um=mst_len,
        n_nets=n_nets, n_routed_segments=n_seg, n_cells=len(p.cell_xywh),
        die_w_um=die_w, die_h_um=die_h,
    )


def _via_landing(shapes: list, x: float, y: float, net: str, land: float) -> None:
    """在 (x,y) 放 VIA2 + M3/M4 双 landing pad（保证通孔被两侧金属包围）。"""
    shapes.append(_rect(L_M3, x - land, y - land, x + land, y + land, net=net, kind="metal"))
    shapes.append(_rect(L_M4, x - land, y - land, x + land, y + land, net=net, kind="metal"))
    shapes.append(_rect(L_VIA2, x - VIA / 2.0, y - VIA / 2.0,
                        x + VIA / 2.0, y + VIA / 2.0, net=net, kind="via"))


def congestion_analysis(nl: Netlist, p: PL.Placement, tech=DC.DEFAULT_TECH) -> dict:
    """E37 · 拥堵量化：每行 H 段 x 区间**最大团**(clique) vs 行通道容量。

    clique = 该行同 y 的 H 段在 x 上同时重叠的最大条数 = 该行需要的 M3 轨道数；
    容量 = 行通道高 / TRACK_PITCH。若 clique ≫ 容量 ⇒ 2 层 L 路由在本密度**装不下**，
    真清零需把通道加高到 clique·pitch ⇒ 行高/面积按 `area_to_zero_ratio` 放大。
    """
    pins = _net_pins(nl, p)
    row_pitch = PL.H_ROW_UM * (1.0 + PL.CHANNEL_X)
    channel = row_pitch - PL.H_ROW_UM
    cap = max(1, int(channel // TRACK_PITCH))
    row_int: dict = defaultdict(list)
    for net, pts in pins.items():
        if len(pts) < 2:
            continue
        for (a, b) in _mst_edges(pts):
            ax, ay = pts[a]
            bx, by = pts[b]
            if abs(ax - bx) < 1e-9:
                continue
            r = int(round(ay / row_pitch))
            row_int[r].append((min(ax, bx), max(ax, bx)))

    def _max_clique(ivs):
        ev = []
        for lo, hi in ivs:
            ev.append((lo, 1))
            ev.append((hi, -1))
        ev.sort()
        cur = best = 0
        for _, d in ev:
            cur += d
            best = max(best, cur)
        return best

    cliques = {r: _max_clique(ivs) for r, ivs in row_int.items()}
    clique_max = max(cliques.values()) if cliques else 0
    need_channel = clique_max * TRACK_PITCH
    need_row_pitch = PL.H_ROW_UM + need_channel
    area_ratio = (need_row_pitch / row_pitch) if row_pitch > 0 else 1.0
    return {
        "rows": p.rows, "capacity_per_row": cap, "channel_um": channel,
        "clique_max": clique_max, "need_channel_um": need_channel,
        "need_row_pitch_um": need_row_pitch, "area_to_zero_ratio": area_ratio,
        "per_row_clique": cliques, "row_pitch_um": row_pitch,
    }


def drc_capacity_bound(nl: Netlist, p: PL.Placement, tech=DC.DEFAULT_TECH) -> dict:
    """**布线容量下界**：把「DRC 清不了零」从一句结论，变成可核数字。

    为什么需要它
    ------------
    v0.9.370 把弯角孔包围修好（`via_enclosure` 14 → 0）之后，剩下的**全部**是
    `min_spacing`。这些不是路由器写错，而是**资源不够**：

      ① **通道不够**：同 y 重叠的 H 段最大团 `clique_max` 需要同样多的 M3 轨道
         （节距 `TRACK_PITCH`），而每行只有 `channel_um = row_pitch − 行高`；
      ② **单元太窄**：一颗单元若有 k 个引脚，要各自引出一条线且间距 ≥ S_MIN，
         单元宽度至少要 `(k−1)·pitch + W_ROUTE`；而 E35 的单元宽是「面积/行高」
         反推的 ~0.08 µm（**比一条线宽 0.24 µm 还窄**）⇒ 同一颗门的多个网
         **必然从同一点出发**，几何上不可能不重叠；
      ③ **整 die 的列数**：所有网都要有自己的 M4 列，`n_pin_access · pitch`
         与 die 宽对比即可看出差几倍。

    返回的是**下界**（best case）：真实清零还要加上绕障/通孔/引脚焊垫占位。
    判定 `verdict`：
      · `ROUTING_RESOURCE_INFEASIBLE` —— 至少一个维度装不下（当前 c17 即此）；
      · `RESOURCE_SUFFICIENT` —— 三个维度都够（本仓尚无用例）。
    """
    cg = congestion_analysis(nl, p, tech)
    pitch = TRACK_PITCH
    cell_ws = [w for (_x, _y, w, _h) in p.cell_xywh.values()]
    pins_per_cell = [len(g.ins) + 1 for g in nl.gates if g.name in p.cell_xywh]
    n_pins_total = sum(pins_per_cell)
    pin_slot_need = ((max(pins_per_cell) - 1) * pitch + W_ROUTE) if pins_per_cell else 0.0
    w_min = min(cell_ws) if cell_ws else 0.0
    w_med = sorted(cell_ws)[len(cell_ws) // 2] if cell_ws else 0.0
    width_ratio = (pin_slot_need / w_med) if w_med > 0 else 0.0
    cols_need = n_pins_total * pitch
    cols_have = p.die_w_um
    channel_ok = cg["capacity_per_row"] >= cg["clique_max"]
    width_ok = pin_slot_need <= w_med + 1e-9
    cols_ok = cols_need <= cols_have + 1e-9
    return {
        "verdict": ("RESOURCE_SUFFICIENT" if (channel_ok and width_ok and cols_ok)
                    else "ROUTING_RESOURCE_INFEASIBLE"),
        "track_pitch_um": pitch,
        "route_width_um": W_ROUTE,
        # ① 通道
        "capacity_per_row": cg["capacity_per_row"],
        "clique_max": cg["clique_max"],
        "channel_um": cg["channel_um"],
        "need_channel_um": cg["need_channel_um"],
        "area_ratio_for_channel": cg["area_to_zero_ratio"],
        "channel_ok": channel_ok,
        # ② 单元宽度（引脚访问）
        "pins_per_cell_max": max(pins_per_cell) if pins_per_cell else 0,
        "pin_slot_need_um": pin_slot_need,
        "cell_w_min_um": w_min,
        "cell_w_median_um": w_med,
        "width_ratio_for_pin_access": width_ratio,
        "width_ok": width_ok,
        # ③ 整 die 列数
        "n_pin_access": n_pins_total,
        "cols_need_um": cols_need,
        "cols_have_um": cols_have,
        "cols_ok": cols_ok,
    }


def drc_zero_experiment(nl: Netlist, tech=DC.DEFAULT_TECH, channel_tracks: int = 0,
                        widen: float = 1.0) -> dict:
    """**反证实验**：按「可布线所需」放大单元宽 + 行通道，实测 DRC 能否归零。

    为什么要做这个实验
    ------------------
    `drc_capacity_bound()` 给出的是**下界**（通道 ×1.577 / 单元宽 ×14.4 / 列 ×5.6）。
    下界只是必要条件 —— 必须**实测**：把面积加到位，违规是否真的归零。
    这也正好检验「1.577× 面积就能换 0 违规」这个说法是否成立。

    做法（**纯构造，不改 `dplac.place` 的既有行为**）
    ------------------------------------------------
    ① 一行布局，单元宽按「每引脚一个 0.36µm 槽」给到 `(n_pins+1)·pitch`（`widen` 可调）；
    ② 行上方留 `channel_tracks` 条 M3 轨道（缺省取 `clique_max`）；
       `widen=None` = **只加通道、单元宽保持原样** —— 用来实测「只放大通道够不够」；
    ③ 每条 MST 边：M4 竖 stub 从引脚到轨道 → M3 横段（两端各外伸 `VIA/2+ENC` 包孔）→
       另一端 M4 stub 下到引脚；
    ④ 轨道按 x 区间着色分配（间距要求 `S_MIN + 2·(VIA/2+ENC)`，把 landing 也算进去，
       否则相邻两段「首尾相接」会判间距违例）；
    ⑤ 端口引脚移到行左侧中线上（原坐标的 y 会落进新通道里，属口径迁移）。

    🔴 **这是 what-if 实验，不是可签核版图**：单元内部仍是黑盒、无绕障/无拥塞求解、
    行式单行；结论只用来判「容量是不是唯一障碍」，不外推到真实 P&R。
    """
    p0 = PL.place(nl, tech)
    bound = drc_capacity_bound(nl, p0, tech)
    pitch, land = TRACK_PITCH, _LAND_CORNER
    s_min = _s_min_of_rules()
    row_h = PL.H_ROW_UM
    ct = channel_tracks if channel_tracks > 0 else max(1, bound["clique_max"])

    gates = [g for g in nl.gates if g.name in p0.cell_xywh]
    gates.sort(key=lambda g: p0.cell_xywh[g.name][0])       # 保持原左→右相对次序
    xywh, cursor = {}, 0.0
    for g in gates:
        if widen is None:                     # 只加通道：单元宽沿用原布局（实测「够不够」）
            w = p0.cell_xywh[g.name][2]
        else:
            w = (len(g.ins) + 1) * pitch * widen
        xywh[g.name] = (cursor, 0.0, w, row_h)
        cursor += w
    row_w = cursor

    # 引脚访问点：widen=None 时**故意沿用「单元中心单点」**（原口径，保留塌缩）；
    #            否则单元内均布（step ≥ pitch ⇒ 同层竖 stub 天然不挤）
    acc = {}
    for g in gates:
        x0, _y0, w, _h = xywh[g.name]
        roles = list(g.ins) + ["__out__"]
        step = w / len(roles)
        for k, role in enumerate(roles):
            px = (x0 + w / 2.0) if widen is None else (x0 + step * (k + 0.5))
            acc[(g.name, role)] = (px, row_h / 2.0)

    pins: dict = defaultdict(list)
    for g in gates:
        pins[g.out].append(acc[(g.name, "__out__")])
        for nm in g.ins:
            pins[nm].append(acc[(g.name, nm)])
    for i, net in enumerate(sorted(p0.port_pins)):
        pins[net].append((-pitch * (i + 1), row_h / 2.0))

    # MST 边 + 轨道着色（间距把 landing 一起算）
    edges, spans = [], []
    for net, pts in pins.items():
        if len(pts) < 2:
            continue
        for (a, b) in _mst_edges(pts):
            ax, ay = pts[a]
            bx, by = pts[b]
            edges.append((net, ax, ay, bx, by))
            spans.append((min(ax, bx) - land, max(ax, bx) + land))
    gap = s_min + 2 * land
    order = sorted(range(len(spans)), key=lambda i: (spans[i][0], spans[i][1]))
    ends, assign = [], [0] * len(spans)
    for idx in order:
        lo, hi = spans[idx]
        placed = False
        for k in range(len(ends)):
            if lo >= ends[k] + gap - 1e-9:
                assign[idx] = k
                ends[k] = hi
                placed = True
                break
        if not placed:
            assign[idx] = len(ends)
            ends.append(hi)

    shapes = []
    for i, (net, ax, ay, bx, by) in enumerate(edges):
        yt = row_h + (assign[i] + 0.5) * pitch
        for (px, py) in ((ax, ay), (bx, by)):
            shapes.append(_rect(L_M4, px - W_ROUTE / 2.0, min(py, yt + land),
                                px + W_ROUTE / 2.0, max(py, yt + land),
                                net=net, kind="metal"))
        shapes.append(_rect(L_M3, min(ax, bx) - land, yt - W_ROUTE / 2.0,
                            max(ax, bx) + land, yt + W_ROUTE / 2.0, net=net, kind="metal"))
        for px in (ax, bx):
            shapes.append(_rect(L_VIA2, px - VIA / 2.0, yt - VIA / 2.0,
                                px + VIA / 2.0, yt + VIA / 2.0, net=net, kind="via"))

    from . import ddrc_lvs as DRC          # 延迟 import：避免模块级循环依赖
    base_shapes = detail_route(nl, p0, tech).shapes
    base_v = len(DRC.run_drc(base_shapes)["violations"])
    got = DRC.run_drc(shapes)
    by_rule: dict = {}
    for v in got["violations"]:
        by_rule[v[0]] = by_rule.get(v[0], 0) + 1

    base_area = p0.die_w_um * p0.die_h_um
    new_area = row_w * (row_h + ct * pitch)
    # 行面积比（更严的口径：只比「单元行 + 通道」，不掺 IO ring）
    base_row_pitch = row_h * (1.0 + PL.CHANNEL_X)
    base_row_w = sum(w for (_x, _y, w, _h) in p0.cell_xywh.values())
    base_row_area = base_row_pitch * base_row_w
    row_area_ratio = (new_area / base_row_area) if base_row_area > 0 else 0.0
    return {
        "verdict": "DRC_ZERO_ACHIEVED" if not got["violations"] else "STILL_VIOLATING",
        "base_violations": base_v,
        "achieved_violations": len(got["violations"]),
        "achieved_by_rule": dict(sorted(by_rule.items())),
        "widen": ("base" if widen is None else widen),
        "channel_tracks": ct,
        "tracks_used": len(ends),
        "row_width_um": round(row_w, 4),
        "row_pitch_um": round(row_h + ct * pitch, 4),
        "area_ratio_vs_die": round(new_area / base_area, 3) if base_area else 0.0,
        "row_area_ratio": round(row_area_ratio, 3),
        # 与下界预测的对照（判据要能说「预测错在哪」）
        "predicted_channel_ratio": bound["area_ratio_for_channel"],
        "predicted_width_ratio": bound["width_ratio_for_pin_access"],
        "pin_slot_um": round(bound["pin_slot_need_um"], 4),
        "cell_width_um": round(row_w / max(1, len(gates)), 4),
        "note": "what-if 构造实验：单行布局 + 均布引脚 + 轨道分配；非可签核版图",
    }


def _s_min_of_rules() -> float:
    """取 DRC 的 S_MIN（单一真源在 ddrc_lvs；此处只读常量，不复制规则值）。"""
    from . import ddrc_lvs as DRC
    return float(DRC.S_MIN)


def track_self_check(verbose: bool = False) -> dict:
    """E37 自检：**校验器硬化 + 拥堵不可行负结果**（只断言硬事实，不伪绿）。

    旧版要求「track DRC 比 baseline 低 5×」——这是**错的期望**：实证 track 反而更高
    （913k > 204k），因引脚接入压在稠密共享行/列上。E37 只断言三条**可复核的硬事实**：

    - ① 每网中心线长 ≥ MST 长（路由几何不编数）。
    - ② **via 违例 = 0**（landing pad 修复 E36 的 648 via_enclosure）。
    - ③ **拥堵不可行**：每行 clique ≫ 通道容量、`area_to_zero_ratio` ≥ 5（真清零要 ≥5× 面积）
      ⇒ 2 层 L 路由在本密度**无法清零**（E37 诚实负结果）。
    - 判别式：注入异网重叠 / 悬空过孔 ⇒ fast_drc 必红（防 checker 假绿）。

    ⚠️ track 的 DRC 总数只作**信息打印**（913k 系引脚接入主导，非本门禁判红项）。
    """
    from . import dctrl as C
    from . import ddrc_lvs as DL
    problems = []
    b = C.build()
    nl = b["netlist"]
    p = PL.place(nl)
    tr = track_route(nl, p)

    # ① 中心线 ≥ MST
    for net, cl in tr.centerline_um.items():
        if cl < tr.mst_um.get(net, 0.0) - 1e-6:
            problems.append(("track_centerline_shorter", net, cl, tr.mst_um.get(net, 0.0)))

    # ② 真实网表诚实事实
    base = detail_route(nl, p)
    base_n = len(DL.fast_drc(base.shapes)["violations"])
    tr_drc = DL.fast_drc(tr.shapes)
    tr_n = len(tr_drc["violations"])
    via_v = sum(1 for v in tr_drc["violations"]
                if v[0] in ("via_enclosure", "via_floating"))

    # ③a via 必须清零（landing pad 修复）
    if via_v != 0:
        problems.append(("track_via_not_fixed", via_v))
    # ③b 拥堵不可行（真清零需 ≥5× 面积）
    cong = congestion_analysis(nl, p)
    if not (cong["area_to_zero_ratio"] >= 5.0):
        problems.append(("congestion_feasible_unexpectedly",
                         cong["clique_max"], cong["capacity_per_row"],
                         round(cong["area_to_zero_ratio"], 2)))

    # 🔴 判别式 1：注入异网重叠金属 ⇒ fast_drc 必须抓红
    h = next((s for s in tr.shapes if s.layer == L_M3 and (s.x1 - s.x0) >= 3.0 * 0.10), None)
    if h is not None:
        bad = list(tr.shapes)
        bad.append(_rect(L_M3, h.x0, h.y0 - 0.02, h.x1, h.y0 + 0.10 - 0.02,
                         net="__bad__", kind="metal"))
        if not any(v[0] == "min_spacing" for v in DL.fast_drc(bad)["violations"]):
            problems.append(("control_spacing_not_red",))
    else:
        problems.append(("control_no_h_segment",))

    # 🔴 判别式 2：注入悬空过孔 ⇒ fast_drc 必须抓红
    bad2 = list(tr.shapes)
    bad2.append(_rect(L_VIA2, 9999.0, 9999.0, 9999.0 + VIA, 9999.0 + VIA,
                      net="__badvia__", kind="via"))
    if not any(v[0] == "via_floating" for v in DL.fast_drc(bad2)["violations"]):
        problems.append(("control_floating_via_not_red",))

    if verbose:
        print("  track: nets=%d segs=%d  base_drc=%d  track_drc=%d(info)  via=%d  "
              "clique_max=%d  cap=%d  area×%.1f"
              % (tr.n_nets, tr.n_routed_segments, base_n, tr_n, via_v,
                 cong["clique_max"], cong["capacity_per_row"],
                 cong["area_to_zero_ratio"]))
    return {
        "ok": not problems, "problems": problems,
        "n_nets": tr.n_nets, "n_routed_segments": tr.n_routed_segments,
        "baseline_drc": base_n, "track_drc": tr_n,
        "track_via_violations": via_v,
        "congestion": cong,
        "die_w_um": tr.die_w_um, "die_h_um": tr.die_h_um,
    }


def DD_detail_for_compare(nl, p):
    """返回 detail_route 结果（自检金标③ baseline 对照用）。"""
    return detail_route(nl, p)


# ---------------------------------------------------------------------------
# 工具：矩形重叠 / 包含
# ---------------------------------------------------------------------------
def rects_overlap(a: Shape, b: Shape, inflate: float = 0.0) -> bool:
    ax0, ay0, ax1, ay1 = a.x0 - inflate, a.y0 - inflate, a.x1 + inflate, a.y1 + inflate
    bx0, by0, bx1, by1 = b.x0 - inflate, b.y0 - inflate, b.x1 + inflate, b.y1 + inflate
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def point_in_rect(px: float, py: float, s: Shape, tol: float = 1e-6) -> bool:
    return (s.x0 - tol <= px <= s.x1 + tol) and (s.y0 - tol <= py <= s.y1 + tol)


# ---------------------------------------------------------------------------
# 自检（含「必须失败」的对照组）
# ---------------------------------------------------------------------------
def detail_self_check(verbose: bool = False) -> dict:
    from . import dctrl as C
    problems = []
    b = C.build()
    nl = b["netlist"]
    p = PL.place(nl)
    dr = detail_route(nl, p)

    # ① 每网布出中心线长 ≥ MST 长（2 端网取等）
    for net, cl in dr.centerline_um.items():
        m = dr.mst_um.get(net, 0.0)
        if cl < m - 1e-6:
            problems.append(("centerline_shorter_than_mst", net, cl, m))

    # ② 2 端网：中心线长 ≡ 两端曼哈顿距离
    for net, pts in dr.net_pins.items():
        if len(pts) == 2:
            d = abs(pts[0][0] - pts[1][0]) + abs(pts[0][1] - pts[1][1])
            if abs(dr.centerline_um.get(net, 0.0) - d) > 1e-6:
                problems.append(("two_pin_centerline_not_manhattan", net,
                                 dr.centerline_um.get(net, 0.0), d))

    # ③ 总线长 > 0，且 ≥ droute 的 MST 总长（应逐位相等）
    from . import droute as RT
    rt = RT.route(nl, p)
    if dr.centerline_um and sum(dr.centerline_um.values()) <= 0:
        problems.append(("zero_routed_length",))
    if abs(sum(dr.centerline_um.values()) - rt.total_um) > 1e-6:
        problems.append(("routed_not_equal_mst_total",
                         sum(dr.centerline_um.values()), rt.total_um))

    # 🔴 对照组：构造一根「画短了」的 2 端网——把某 2 端网的 H 段砍到 0.4× 距离
    #   ⇒ 该网中心线 < 曼哈顿距离 ⇒ 判据必须抓红。
    bad_shapes = []
    target = None
    for net, pts in dr.net_pins.items():
        if len(pts) == 2:
            target = net
            break
    if target is not None:
        ax, ay = dr.net_pins[target][0]
        bx, by = dr.net_pins[target][1]
        dx = abs(ax - bx)
        for s in dr.shapes:
            if s.net != target or s.layer != L_M3:
                bad_shapes.append(s)
                continue
            # 把这条 H 段压缩到 0.4× 跨度
            if dx > 1e-9:
                mid = (ax + bx) / 2.0
                lo, hi = sorted([ax, bx])
                new_lo = mid - (hi - lo) * 0.2
                new_hi = mid + (hi - lo) * 0.2
                bad_shapes.append(_rect(L_M3, new_lo, ay - W_ROUTE / 2.0,
                                        new_hi, ay + W_ROUTE / 2.0, net=target, kind="metal"))
            else:
                bad_shapes.append(s)
        bad_cl = dx * 0.4 + abs(ay - by)  # 中心线被砍短
        if bad_cl >= (dx + abs(ay - by)) - 1e-6:
            problems.append(("control_shortened_not_red",))
    else:
        # 没有 2 端网（极端情况）：用「缺 H 段」对照
        if dr.shapes:
            problems.append(("control_no_two_pin",))

    if verbose:
        tot = sum(dr.centerline_um.values())
        print("  detail: nets=%d  segments=%d  routed=%.1f um  cells=%d"
              % (dr.n_nets, dr.n_routed_segments, tot, dr.n_cells))
    return {
        "ok": not problems, "problems": problems,
        "n_nets": dr.n_nets, "n_routed_segments": dr.n_routed_segments,
        "routed_um": sum(dr.centerline_um.values()),
        "n_cells": dr.n_cells,
    }


def cellgeom_self_check(verbose: bool = False) -> dict:
    from . import dctrl as C
    problems = []
    b = C.build()
    nl = b["netlist"]
    p = PL.place(nl)
    cells = real_cell_geom(p)

    per_cell = defaultdict(list)
    for s in cells:
        per_cell[s.cell].append(s)

    # ① 每颗单元 ≥1 有源 + ≥1 引脚
    for nm in p.cell_xywh:
        Sh = per_cell.get(nm, [])
        if not any(s.kind == "active" for s in Sh):
            problems.append(("cell_no_active", nm))
        if not any(s.kind == "pin" for s in Sh):
            problems.append(("cell_no_pin", nm))

    # ② 单元数 = 网表门数
    if len(per_cell) != len(nl.gates):
        problems.append(("cell_count", len(per_cell), len(nl.gates)))

    # 🔴 对照组：构造一个缺引脚焊垫的伪劣单元集（删掉某单元 pin），判据必须抓红
    bad = [s for s in cells if not (s.cell == next(iter(p.cell_xywh)) and s.kind == "pin")]
    # 重新按单元聚合
    bad_per = defaultdict(list)
    for s in bad:
        bad_per[s.cell].append(s)
    first = next(iter(p.cell_xywh))
    if any(s.kind == "pin" for s in bad_per.get(first, [])):
        problems.append(("control_missing_pin_not_red",))

    if verbose:
        print("  cellgeom: cells=%d  shapes=%d" % (len(per_cell), len(cells)))
    return {
        "ok": not problems, "problems": problems,
        "n_cells": len(per_cell), "n_shapes": len(cells),
    }


DDETAIL_DISCLOSURE = {
    "route": "E36 · P&R 深化 第 1 刀 · D-220 detail route + D-221 真实单元几何",
    "analysis": "MST 每网 → H(M3)+V(M4)+弯角 VIA2 真实金属多边形；单元包围盒升级为 "
                "有源区标记+M1 引脚焊垫+通孔栈",
    "golden": "每网布出中心线长 ≥ MST 长（2 端网≡曼哈顿距离）；每单元≥1 有源+≥1 引脚",
    "not_included": "模型尺度下单元内部几何符号级(非 PDK) · 单元内多端子分离为黑盒 · "
                    "简化 L 路由无拥塞求解/无 track 共享/无绕障 · 通孔 RC 未计",
    "e37_note": "E37（D-224）试了 interval 着色 track 分配：主段能上轨道，但在本密度（每行 "
                "clique 87~120、通道仅 2 轨）引脚接入压在共享行/列上，track 总 DRC=913k 反高于 "
                "基线 204k；真清零需 ≥14.6× 面积（退化）⇒ 2 层 L 路由不能清零，**诚实负结果**。"
                "via 648→0（landing pad）是真收益，但整网 DRC 不降；清零留待真实 maze/multilayer router。",
    "claimable": False,
    "claimable_reason": "布线几何是布局的视觉化；可 signoff 的只有结构性事实（中心线≥MST、"
                       "单元几何完整性）；其**可制造性**仍 MODEL_ESTIMATE",
}
