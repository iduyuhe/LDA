# -*- coding: utf-8 -*-
"""E36 · **CIM 加速器 IP 硬宏 + GDS 合并 + detail route/真实单元几何 + IP 级 DRC/LVS**
（`lda/lda_l2/ecore/dmacro.py` · D-219 → D-220~D-223）。

══════════════════════════════════════════════════════════════
定位：把 E33 的**阵列 GDS** 与 E34 的**数字控制壳网表** + E35 的**布局/布线**，
打包成一个**真的硬宏（hard macro）** —— 有外框、有顶层引脚、有单一 GDS 文件。
E36 在 E35 基础上进一步：
  - D-220 **detail route**：把 MST 每网画成真实金属多边形（H=M3 / V=M4 / 弯角 VIA2）；
  - D-221 **真实单元几何**：数字单元从包围盒升级为有源区标记 + M1 引脚焊垫 + 通孔栈；
  - D-222/D-223 **IP 级 DRC/LVS**：对数字区路由几何做最小线宽/间距/通孔 + 连通性/短路。
══════════════════════════════════════════════════════════════
终点已定为 **CIM 加速器 IP**（不是能流片的完整 SoC）：本宏就是那个「IP」实体。
它把前四段（E33 阵列 + E34 数字 + E35 布局布线）**第一次合到一个几何与电气边界里**。

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标：合并后的 GDS **元素数 = 回读元素数**（零丢失）
══════════════════════════════════════════════════════════════
E33 的纪律「`flat_elements ≡ len(descs)`」在这里升级为「**喂给解析器的元素数 ≡ 发出的元素数**」。
任何「几何体被静默丢进 top 之外」（E31 的 via stack 假绿同型）都会被抓红。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- **数字单元内部的真实几何仍是符号级**（模型尺度单元宽≈0.08µm，放不下真实晶体管）；
  有源区/引脚/通孔栈是「占位标记」，不是 PDK 可制造单元
- **简化 L 形路由无 track 分配/无绕障** ⇒ baseline 存在大量同层重叠/短路（已知诚实事实，
  如实报告违例数，不因此判红；清零是下一阶段 maze/grid 路由器的事）
- **阵列与数字块之间没有任何 IO 环电气连接几何**（只是摆在一起）
- **顶层引脚是标记方块**，未画 pad 金属 / ESD / bump
- 合并用 flat（非 AREF）⇒ 文件偏大，但**可机核零丢失**（这正是要的）
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import dcell as DC
from . import dsta as ST
from . import dplac as PL
from . import droute as RT
from . import dextract as DX
from . import ddetail as DD
from . import ddrc_lvs as DL
from . import dctrl as C
from . import layout as LY
from .dsynth import Netlist
from lda_l2 import gds_export as G

# ---- IP 层分配（避开阵列 20–36 与标准层）----
LAYER_DIGITAL = 50          # 数字单元包围盒
LAYER_IP_BOUNDARY = 51      # IP 外框（标记）
LAYER_PIN = 52              # 顶层引脚（标记）
GAP_UM = 20.0               # 阵列块与数字块之间的间距
IO_RING_UM = PL.IO_RING_UM  # 复用布局的 IO ring 厚度


@dataclass
class Macro:
    gds_bytes: bytes
    n_emitted: int            # 发出的 GDS 元素数
    n_parsed: int             # 回读展开后的元素数
    boundary_um: tuple        # (x0, y0, x1, y1)  IP 外框
    core_um: tuple
    array_box_um: tuple
    digital_box_um: tuple
    n_pins: int
    n_digital_cells: int
    array_only_bytes: int     # 对照：仅阵列 GDS 字节数
    n_route_shapes: int       # detail route 金属/通孔形状数
    n_cell_shapes: int        # 真实单元几何形状数
    drc_violations: int       # IP 级 DRC 违例（仅数字区 P&R）
    lvs_problems: int         # IP 级 LVS 问题（仅数字区 P&R）


def _desc_bytes(d: dict) -> bytes:
    """阵列几何 desc → GDS 元素字节（与 `layout.to_gds` 同一编码器）。"""
    if d["kind"] == "path":
        return G.path(d["layer"], d["width_um"], d["points_um"])
    # boundary：rings_um 是「多个多边形」的列表；每个多边形单独发一条 BOUNDARY
    out = b""
    for poly in d["rings_um"]:
        out += G.boundary(d["layer"], poly)
    return out


def _box(layer: int, x0: float, y0: float, x1: float, y1: float) -> bytes:
    return G.boundary(layer, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _pin(layer: int, x: float, y: float, s: float = 1.5) -> bytes:
    return _box(layer, x - s / 2.0, y - s / 2.0, x + s / 2.0, y + s / 2.0)


def build_ip(nl: Netlist, tech=DC.DEFAULT_TECH) -> Macro:
    """合成 CIM 加速器 IP 硬宏（阵列 + 数字壳 + **E36 detail route 金属** + **E36 真实单元几何**
    + 外框 + 引脚 → 单一 GDS）。

    E36 新增（全部数字区局部坐标 + dig_off_x 偏移）：
      - `DD.detail_route` 把 MST 每网画成 H=M3 / V=M4 / 弯角 VIA2 真实金属多边形；
      - `DD.real_cell_geom` 每颗数字单元升级为 有源区标记(E_DIFF/20) + M1 引脚焊垫 + 通孔栈；
      - `DL.run_drc` / `DL.run_lvs` 对数字区**路由几何**做 IP 级可制造性/连通性 signoff。
    """
    # ① 阵列几何（复用 E33 签核栈：行线 M2 + via stack）
    arr = LY.crossbar_array(87, 87, None, row_layer="M2", via_stack=True)
    arr_descs = arr["descs"]
    aw, ah = LY.array_footprint(87, 87)
    # 对照：仅阵列的 GDS 字节（flat）
    arr_only = LY.to_gds(87, 87, None, hierarchical=False,
                         row_layer="M2", via_stack=True)["gds_bytes"]

    # ② 数字布局 + 布线（E35 布局/布线 + E34 网表）
    p = PL.place(nl, tech=tech)
    dig_off_x = aw + GAP_UM

    # E36 · detail route 金属/通孔（数字局部坐标）+ 真实单元几何
    dr = DD.detail_route(nl, p, tech=tech)
    cell_shapes = DD.real_cell_geom(p, tech=tech)

    top: list = []
    n_emit = 0

    # 阵列（直接放在原点）
    for d in arr_descs:
        top.append(_desc_bytes(d))
        n_emit += 1

    # 数字单元包围盒（保留为视觉区块标记，LAYER_DIGITAL=50；仍按布局坐标 + 偏移）
    for nm, (x0, y0, w, h) in p.cell_xywh.items():
        top.append(_box(LAYER_DIGITAL, dig_off_x + x0, y0,
                        dig_off_x + x0 + w, y0 + h))
        n_emit += 1

    # E36 · detail route 金属/通孔（M3/M4/VIA2）→ 真实多边形（偏移 dig_off_x）
    for s in dr.shapes:
        top.append(_box(s.layer, dig_off_x + s.x0, s.y0,
                        dig_off_x + s.x1, s.y1))
        n_emit += 1

    # E36 · 真实单元几何（DIFF/M1/VIA1/VIA2）→ 真实多边形（偏移 dig_off_x）
    for s in cell_shapes:
        top.append(_box(s.layer, dig_off_x + s.x0, s.y0,
                        dig_off_x + s.x1, s.y1))
        n_emit += 1

    # 数字块外框 + 阵列块外框
    top.append(_box(LAYER_IP_BOUNDARY, 0.0, 0.0, aw, ah))
    n_emit += 1
    top.append(_box(LAYER_IP_BOUNDARY, dig_off_x, 0.0,
                    dig_off_x + p.die_w_um, p.die_h_um))
    n_emit += 1

    # 顶层引脚（沿数字块左边界等距，标记方块）
    for (_port, _b, _net, x, y, _side) in p.pin_list:
        top.append(_pin(LAYER_PIN, dig_off_x + x, y))
        n_emit += 1

    # ③ IP 总外框（环绕 core 的 IO ring）
    core_w = dig_off_x + p.die_w_um
    core_h = max(ah, p.die_h_um)
    bx0, by0 = -IO_RING_UM, -IO_RING_UM
    bx1, by1 = core_w + IO_RING_UM, core_h + IO_RING_UM
    top.append(_box(LAYER_IP_BOUNDARY, bx0, by0, bx1, by1))
    n_emit += 1

    gds = G.gds_library("CIM_IP", {"TOP": top})

    # ④ 回读（展开引用 → 元素数）
    parsed = G.parse_gds_polygons(gds, expand_refs=True)
    top_names = parsed.get("top_structures", [])
    n_parsed = sum(len(parsed["structures"][s]) for s in top_names)

    # E36 · IP 级 DRC/LVS（对数字区**路由几何** signoff；baseline 违例数如实报告，不判红）
    drc = DL.run_drc(dr.shapes)
    lvs = DL.run_lvs(dr.shapes, dr.net_pins)

    return Macro(
        gds_bytes=gds, n_emitted=n_emit, n_parsed=n_parsed,
        boundary_um=(bx0, by0, bx1, by1),
        core_um=(0.0, 0.0, core_w, core_h),
        array_box_um=(0.0, 0.0, aw, ah),
        digital_box_um=(dig_off_x, 0.0, dig_off_x + p.die_w_um, p.die_h_um),
        n_pins=len(p.pin_list), n_digital_cells=len(p.cell_xywh),
        array_only_bytes=len(arr_only),
        n_route_shapes=len(dr.shapes),
        n_cell_shapes=len(cell_shapes),
        drc_violations=len(drc["violations"]),
        lvs_problems=len(lvs["problems"]),
    )


def closure() -> dict:
    """IP 级综合闭环：面积 / 时序 / GDS 一把抓。"""
    b = C.build()
    nl = b["netlist"]
    w = DX.wire_aware_sta(nl)
    macro = build_ip(nl)
    p = PL.place(nl)
    return {
        "fmax_ideal_mhz": w.fmax_ideal_mhz,
        "fmax_wire_mhz": w.fmax_wire_mhz,
        "ratio": w.ratio,
        "total_wire_um": w.total_wire_um,
        "total_C_fF": w.total_C_fF,
        "n_nets": w.n_nets,
        "die_digital_um": (p.die_w_um, p.die_h_um),
        "array_box_um": macro.array_box_um,
        "digital_box_um": macro.digital_box_um,
        "ip_boundary_um": macro.boundary_um,
        "ip_area_um2": (macro.boundary_um[2] - macro.boundary_um[0]) *
                        (macro.boundary_um[3] - macro.boundary_um[1]),
        "n_pins": macro.n_pins,
        "n_digital_cells": macro.n_digital_cells,
        "gds_bytes": len(macro.gds_bytes),
        "gds_emitted": macro.n_emitted,
        "gds_parsed": macro.n_parsed,
        "array_only_bytes": macro.array_only_bytes,
        "n_route_shapes": macro.n_route_shapes,
        "n_cell_shapes": macro.n_cell_shapes,
        "drc_violations": macro.drc_violations,
        "lvs_problems": macro.lvs_problems,
    }


def macro_self_check(verbose: bool = False) -> dict:
    from . import dctrl as C2
    problems = []
    b = C2.build()
    nl = b["netlist"]
    m = build_ip(nl)

    # ① 元素数守恒：发出 ≡ 回读（零丢失）
    if m.n_emitted != m.n_parsed:
        problems.append(("element_loss", m.n_emitted, m.n_parsed))

    # ② 合并后的 GDS 字节 > 仅阵列 GDS（确实多了数字 + 外框 + 引脚）
    if not (len(m.gds_bytes) > m.array_only_bytes):
        problems.append(("gds_not_larger", len(m.gds_bytes), m.array_only_bytes))

    # ③ 引脚数 == 布局引脚数
    arr_dim = LY.array_footprint(87, 87)
    dig_off_x = arr_dim[0] + GAP_UM
    p = PL.place(nl)
    if m.n_pins != len(p.pin_list):
        problems.append(("pin_count_mismatch", m.n_pins, len(p.pin_list)))

    # ④ IP 外框必须包围阵列块 + 数字块
    bx0, by0, bx1, by1 = m.boundary_um
    ax0, ay0, ax1, ay1 = m.array_box_um
    dx0, dy0, dx1, dy1 = m.digital_box_um
    if not (bx0 <= ax0 and by0 <= ay0 and bx1 >= ax1 and by1 >= ay1
            and bx0 <= dx0 and by0 <= dy0 and bx1 >= dx1 and by1 >= dy1):
        problems.append(("boundary_not_enclosing", m.boundary_um,
                         m.array_box_um, m.digital_box_um))

    # ⑤ 数字单元数 == 网表门数
    if m.n_digital_cells != len(nl.gates):
        problems.append(("cell_count", m.n_digital_cells, len(nl.gates)))

    # 🔴 对照组：构造一个**漏掉所有数字单元包围盒**的伪劣 GDS（模拟「几何体被静默丢进
    #    top 之外」—— 与 E31 via stack 假绿同型），再谎报 emit 为全量。
    #    判据 `emit ≠ parse` 必须抓红。
    arr2 = LY.crossbar_array(87, 87, None, row_layer="M2", via_stack=True)
    tb = []
    for d in arr2["descs"]:
        if d["kind"] == "path":
            tb.append(G.path(d["layer"], d["width_um"], d["points_um"]))
        else:
            for poly in d["rings_um"]:
                tb.append(G.boundary(d["layer"], poly))
    aw2, ah2 = LY.array_footprint(87, 87)
    tb.append(_box(LAYER_IP_BOUNDARY, 0.0, 0.0, aw2, ah2))   # 阵列块外框
    for (_pp, _bb, _nn, xx, yy, _sd) in p.pin_list:
        tb.append(_pin(LAYER_PIN, dig_off_x + xx, yy))
    gds_bad = G.gds_library("CIM_IP_BAD", {"TOP": tb})
    parsed_bad = G.parse_gds_polygons(gds_bad, expand_refs=True)
    n_parsed_bad = sum(len(parsed_bad["structures"][s])
                       for s in parsed_bad.get("top_structures", []))
    # 谎报 emit = 全量（声称含被删的数字盒）
    fake_emit = m.n_parsed
    if fake_emit == n_parsed_bad:
        problems.append(("control_emit_mismatch_not_red",))

    if verbose:
        c = closure()
        print("  macro: IP=%.0f x %.0f um  area=%.0f um2  pins=%d  cells=%d"
              % (c["ip_boundary_um"][2] - c["ip_boundary_um"][0],
                 c["ip_boundary_um"][3] - c["ip_boundary_um"][1], c["ip_area_um2"],
                 c["n_pins"], c["n_digital_cells"]))
        print("  macro: gds=%d B (emit=%d parse=%d)  array_only=%d B"
              % (c["gds_bytes"], c["gds_emitted"], c["gds_parsed"],
                 c["array_only_bytes"]))
        print("  macro: route_shapes=%d  cell_shapes=%d  drc=%d  lvs=%d"
              % (c["n_route_shapes"], c["n_cell_shapes"],
                 c["drc_violations"], c["lvs_problems"]))
    return {
        "ok": not problems, "problems": problems,
        "n_emitted": m.n_emitted, "n_parsed": m.n_parsed,
        "gds_bytes": len(m.gds_bytes), "n_pins": m.n_pins,
        "ip_area_um2": (m.boundary_um[2] - m.boundary_um[0]) *
                       (m.boundary_um[3] - m.boundary_um[1]),
        "ip_boundary_um": m.boundary_um,
        "n_route_shapes": m.n_route_shapes, "n_cell_shapes": m.n_cell_shapes,
        "drc_violations": m.drc_violations, "lvs_problems": m.lvs_problems,
    }


DMACRO_DISCLOSURE = {
    "route": "E36 · CIM 加速器 IP 的 P&R 深化 · 第 3 层（IP 硬宏 + GDS 合并 + detail route/真实单元几何 + IP DRC/LVS）",
    "analysis": "阵列 GDS（E33 栈）+ 数字单元包围盒 + **E36 detail route 金属(M3/M4/VIA2)** + "
                "**E36 真实单元几何(有源/M1/通孔栈)** + 外框 + 引脚 → 单一 GDS；"
                "复用 gds_export 编码器与 parse_gds_polygons 回读；对数字区路由几何跑 run_drc/run_lvs",
    "golden": "合并 GDS 元素数（emit）≡ 回读展开元素数（零丢失）· GDS 字节 > 仅阵列 · "
              "外框包围阵列+数字 · E36 路由/单元几何真发进 GDS（计入 emit/parse 守恒）",
    "not_included": "数字单元内部几何符号级(非 PDK) · 简化 L 路由无 track 分配(baseline 同层短路已知) · "
                    "无 IO 环电气连接几何 · 引脚是标记方块 · flat 非 AREF · "
                    "IP 级 DRC/LVS 规则值为假设(非 PDK) 仅验路由几何",
    "claimable": False,
    "claimable_reason": "GDS 几何是布局的视觉化；IP 面积/引脚数/路由形状数是结构性事实可 signoff，"
                       "但**可制造性**仍 MODEL_ESTIMATE（IP 级 DRC/LVS 规则非 Foundry PDK；"
                       "baseline 违例数是简化路由器的诚实结果，非签核绿）",
}
