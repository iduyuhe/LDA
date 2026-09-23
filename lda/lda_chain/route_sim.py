"""LDA L1 · 链路级布局+仿真整合（placement + routing + engine + GDS）。

P1-M2 入口。给定 LinkModel，输出：
  - placement（器件放置）
  - 每条内部 net 的自动布线 RouteResult（含损耗）
  - 注入 net 损耗后的链路级联仿真（engine.simulate）
  - 整芯片 GDSII 字节（器件几何 + 走线，round-trip 可解析）
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from lda_l2 import gds_export
from lda_chain import engine
from lda_layout.placement import device_bbox, place_row, port_abs
from lda_layout.router import RouteResult, route_net
from lda_layout.router_p1 import route_net_p1  # P1 重写：空间索引+局部窗口，与 route_net 逐位一致且更快


def route_and_simulate(link, wavelengths_um, wg_width=0.5, bend_radius=5.0,
                       corner="round", pitch_x=None, straight_loss_db_cm=2.5,
                       sources=None):
    """放置→自动布线（含损耗）→注入仿真→生成 GDS，一体输出 LayoutResult。"""
    placement = place_row(link, pitch_x=pitch_x)
    # 障碍 = 所有器件包围盒
    obstacles = []
    for c in link.ir.components:
        ox, oy, _ = placement[c.id]
        hw, hh = device_bbox(c.kind, dict(c.params))
        obstacles.append((ox, oy, hw, hh))

    routes: Dict[str, RouteResult] = {}
    net_loss_db: Dict[str, float] = {}
    for net in link.ir.nets:
        ports = [tuple(x.split(".", 1)) for x in net.connects if "." in x]
        if len(ports) == 2:
            (i0, p0), (i1, p1) = ports
            src = port_abs(i0, p0, placement, link)
            dst = port_abs(i1, p1, placement, link)
            # 障碍排除源与目标器件（其端口连接点本就在各自 bbox 内，合法）
            obs = [o for o in obstacles
                   if (abs(o[0] - placement[i0][0]) > 1e-6
                       or abs(o[1] - placement[i0][1]) > 1e-6)
                   and (abs(o[0] - placement[i1][0]) > 1e-6
                        or abs(o[1] - placement[i1][1]) > 1e-6)]
            rr = route_net_p1(net.id, src, dst, obstacles=obs,
                           wg_width=wg_width, bend_radius=bend_radius,
                           corner=corner, straight_loss_db_cm=straight_loss_db_cm)
            routes[net.id] = rr
            net_loss_db[net.id] = rr.total_loss_db
        # 多端口 net（>2）M2 不覆盖（诚实标注，跳过布线）

    sim = engine.simulate(link, wavelengths_um, net_loss_db=net_loss_db,
                          sources=sources)
    sim["net_loss_db"] = net_loss_db

    gds_bytes = _build_chip_gds(link, placement, routes, wg_width)
    parse = gds_export.parse_gds(gds_bytes)

    return {
        "placement": placement,
        "routes": routes,
        "net_loss_db": net_loss_db,
        "sim": sim,
        "gds_bytes": gds_bytes,
        "gds_parse": parse,
        "blocked_nets": [n for n, r in routes.items() if r.blocked],
        "note": ("P1-M2 链路级布局+仿真整合：放置→自动布线（含损耗）→注入仿真→"
                 "生成 GDS。" + (" 注意：存在未避障 net（blocked）。"
                 if any(r.blocked for r in routes.values()) else "")),
    }


def layout_only(link, wavelengths_um=None, wg_width=0.5, bend_radius=5.0,
                 corner="round", pitch_x=None, straight_loss_db_cm=2.5):
    """放置→自动布线（含损耗）→生成 GDS，不跑仿真（仿真由 VerificationAgent 独立驱动）。

    返回：placement / routes / net_loss_db / gds_bytes / gds_parse / blocked_nets。
    与 route_and_simulate 共用同一 GDS 构建逻辑，确保「版图」与「验证」职责分离。
    """
    placement = place_row(link, pitch_x=pitch_x)
    obstacles = []
    for c in link.ir.components:
        ox, oy, _ = placement[c.id]
        hw, hh = device_bbox(c.kind, dict(c.params))
        obstacles.append((ox, oy, hw, hh))

    routes: Dict[str, RouteResult] = {}
    net_loss_db: Dict[str, float] = {}
    for net in link.ir.nets:
        ports = [tuple(x.split(".", 1)) for x in net.connects if "." in x]
        if len(ports) == 2:
            (i0, p0), (i1, p1) = ports
            src = port_abs(i0, p0, placement, link)
            dst = port_abs(i1, p1, placement, link)
            obs = [o for o in obstacles
                   if (abs(o[0] - placement[i0][0]) > 1e-6
                       or abs(o[1] - placement[i0][1]) > 1e-6)
                   and (abs(o[0] - placement[i1][0]) > 1e-6
                        or abs(o[1] - placement[i1][1]) > 1e-6)]
            rr = route_net_p1(net.id, src, dst, obstacles=obs,
                           wg_width=wg_width, bend_radius=bend_radius,
                           corner=corner, straight_loss_db_cm=straight_loss_db_cm)
            routes[net.id] = rr
            net_loss_db[net.id] = rr.total_loss_db

    gds_bytes = _build_chip_gds(link, placement, routes, wg_width)
    parse = gds_export.parse_gds(gds_bytes)
    return {
        "placement": placement,
        "routes": routes,
        "net_loss_db": net_loss_db,
        "gds_bytes": gds_bytes,
        "gds_parse": parse,
        "blocked_nets": [n for n, r in routes.items() if r.blocked],
        "note": ("P1-M3 版图布局（不含仿真）：放置→自动布线（含损耗）→生成 GDS。"
                 + (" 注意：存在未避障 net（blocked）。"
                    if any(r.blocked for r in routes.values()) else "")),
    }


def _build_chip_gds(link, placement, routes, wg_width):
    """整芯片 GDSII（器件几何 + 走线，round-trip 可解析）。

    v0.9.128（P1-T1.2 连带修复 · **P0-0 同型缺陷根治**）
    -------------------------------------------------
    本函数原先**自持一份器件几何实现**（RingResonator / Waveguide /
    GratingCoupler 三个特例 + 一个通用分支）。那份抄件有两处缺陷：

      ① 通用分支**先索引** `d["points_um"]`、**后判** `d["kind"]` ⇒ 任何产出
         BOUNDARY 描述的器件（`SymmetricYBranch` 的 taper / `MMI` 的多模区 /
         `BraggMirror` 的光栅 / `Taper`）**KeyError 崩在布局期** —— 实测这四类
         全崩，即 `layout_only` 对它们长期不可用（其下游：`lda check` /
         `lda build` / `lda_l1.protocol` / `lda_agent.agent_layout`）。
      ② **即使**把取字段改对走 `rings_um` 分支，它也没有施加 `(ox, oy)` 偏移
         —— 与 `chip_layout_export._desc_geoms` 文档记载的 **P0-0 血案**
         （「path 分支施加了偏移而 boundary 分支没有」，曾让 CPO 250k 的
         174,080 个光栅齿全部错位）**错法完全一致**。

    这正是 P0-0 的原话教训：**同一段逻辑抄两遍、错得一样**。故本函数不再自持
    几何，改为**薄委托到唯一定义处** `chip_layout_export.device_geom_of`
    （其 docstring 已自任「器件几何的**唯一定义处**」），字节编码仍交
    `gds_export` ⇒ 布局快照的几何语义与 DRC/LVS **完全同源**。
    （`chip_layout_export` 不 import `lda_chain` ⇒ 无循环导入。）

    🔴 既有调用零影响（实测）：对原实现本就能跑的三类器件
    （Waveguide / RingResonator / GratingCoupler）GDS **逐字节一致**。
    """
    from lda_l2.chip_layout_export import device_geom_of
    elements = []
    for c in link.ir.components:
        for g in device_geom_of(c, placement, wg_width):
            if g[0] == "P":
                elements.append(gds_export.path(g[1], g[2], g[3]))
            else:
                elements.append(gds_export.boundary(g[1], g[3]))
    for net_id, rr in routes.items():
        elements.append(gds_export.path(gds_export.LIB_LAYER_SI, wg_width,
                                        rr.points_um))
    return gds_export.gds_library("LDA_CHIP", {"CHIP": elements})
