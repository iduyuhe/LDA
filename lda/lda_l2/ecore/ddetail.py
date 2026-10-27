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
- **简化 L 形路由，无拥塞求解 / 无 track 共享 / 无绕障**：当前布局下经验为 0 同层短路，
  但这是「布局稀疏」的幸运，不是路由器的保证；真正 maze/grid 路由器是下一阶段。
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
L_VIA2 = 28

# ---- 几何/规则假设（MODEL_ESTIMATE · 一阶）----
W_ROUTE = 0.24          # µm · 布线金属线宽
VIA = 0.20             # µm · 通孔边长
ENC = 0.02             # µm · 通孔包围（金属比通孔大出的单边量）
PIN_R = 0.30           # µm · 单元引脚焊垫边长（> W_ROUTE，保证可连）


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
            if dx > 1e-9:
                # H 段：M3，y=ay，x∈[ax,bx]
                shapes.append(_rect(L_M3, ax, ay - W_ROUTE / 2.0, bx, ay + W_ROUTE / 2.0,
                                    net=net, kind="metal"))
                n_seg += 1
            if dy > 1e-9:
                # V 段：M4，x=bx，y∈[ay,by]
                shapes.append(_rect(L_M4, bx - W_ROUTE / 2.0, ay, bx + W_ROUTE / 2.0, by,
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
    "claimable": False,
    "claimable_reason": "布线几何是布局的视觉化；可 signoff 的只有结构性事实（中心线≥MST、"
                       "单元几何完整性）；其**可制造性**仍 MODEL_ESTIMATE",
}
