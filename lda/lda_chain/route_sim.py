"""LDA L1 · 链路级布局+仿真整合（placement + routing + engine + GDS）。

P1-M2 入口。给定 LinkModel，输出：
  - placement（器件放置）
  - 每条内部 net 的自动布线 RouteResult（含损耗）
  - 注入 net 损耗后的链路级联仿真（engine.simulate）
  - 整芯片 GDSII 字节（器件几何 + 走线，round-trip 可解析）
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from lda_l2 import gds_export
from lda_chain import engine
from lda_layout.placement import device_bbox, place_row, port_abs
from lda_layout.router import RouteResult, route_net


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
            rr = route_net(net.id, src, dst, obstacles=obs,
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
            rr = route_net(net.id, src, dst, obstacles=obs,
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
    lib = gds_export.LIB_LAYER_SI
    elements = []
    for c in link.ir.components:
        ox, oy, _ = placement[c.id]
        params = dict(c.params)
        if c.kind in ("RingResonator", "RingAddDrop"):
            R = float(params.get("R", 10.0))
            wg_w = float(params.get("wg_width", wg_width))
            gap = float(params.get("gap", 0.3))
            half = R * 1.5
            off = R + wg_w / 2.0 + gap
            ring_pts = [(ox + R * math.cos(2.0 * math.pi * i / 64),
                         oy + R * math.sin(2.0 * math.pi * i / 64))
                        for i in range(64)]
            elements.append(gds_export.path(lib, wg_w, ring_pts))
            elements.append(gds_export.path(lib, wg_w,
                             [(ox - half, oy - off), (ox + half, oy - off)]))
            elements.append(gds_export.path(lib, wg_w,
                             [(ox - half, oy + off), (ox + half, oy + off)]))
        elif c.kind == "Waveguide":
            length = float(params.get("length", 10.0))
            elements.append(gds_export.path(lib, wg_width,
                             [(ox, oy), (ox + length, oy)]))
        elif c.kind == "GratingCoupler":
            L = float(params.get("L", 10.0))
            elements.append(gds_export.path(lib, wg_width,
                             [(ox, oy), (ox, oy + L)]))
        else:
            for d in gds_export.geometry_desc(c.kind, params):
                pts = [(ox + px, oy + py) for px, py in d["points_um"]]
                if d["kind"] == "path":
                    elements.append(gds_export.path(d["layer"], d["width_um"], pts))
                else:
                    flat = [pp for ring in d.get("rings_um", []) for pp in ring]
                    elements.append(gds_export.boundary(d["layer"], flat))
    for net_id, rr in routes.items():
        elements.append(gds_export.path(lib, wg_width, rr.points_um))
    return gds_export.gds_library("LDA_CHIP", {"CHIP": elements})
