"""LDA 芯片级版图导出增强（v0.8.11d · 门3 前置：从原理图到可测芯片版图）。

在链路级 layout_only（放置+布线+GDS）之上增加"可测芯片"三要素：
  1. **IO 光栅耦合器接入**：链路所有外部端口（源/汇）自动放置光栅耦合器
     （grating_coupler_descs 真实齿区几何），使芯片版图可光纤耦合测试；
  2. **版图统计**：结构/元素数、芯片 bbox/面积、器件数、IO 端口数、层清单；
  3. **版图 DRC 可制造性报告**：对链路所有器件跑 drc_check_device（死标量），
     汇总芯片级可制造性（与门3 流片管道 S2 DRC 自查同源）。

设计纪律：不动 route_sim 核心（链路引擎职责单一），本模块为独立增强层；
全部几何复用 lda_l2 真实基元（零依赖、纯标准库）。

产出：chip_gds（增强版 GDSII）+ gds_stats + drc_report + markdown 版图报告。
"""
from __future__ import annotations

import math
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_l2 import gds_export
from lda_l2.drc import drc_check_device, drc_summary, rules_from_pdk
from lda_l2.lvs import run_lvs, lvs_markdown
from lda_l2.primitives import primitive_descs
from lda_layout.placement import port_abs, device_bbox


def io_ports_of(link) -> List[Tuple[str, str]]:
    """链路外部 IO 端口（源 + 汇），保序去重。"""
    topo = link.topology()
    ext = [(i, p) for (i, p, _) in topo["external"]]
    src_set = set(getattr(link, "sources", []) or [])
    seen = set()
    out = []
    for x in ext:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _route_points(rr) -> List[Tuple[float, float]]:
    """RouteResult 或 dict 摘要 → 折线点。"""
    if isinstance(rr, dict):
        return list(rr.get("points_um") or [])
    return list(getattr(rr, "points_um", []) or [])


def _device_elements(link, placement, wg_width) -> List[bytes]:
    """器件版图元素（复用 route_sim._build_chip_gds 的器件绘制逻辑）。"""
    elements = []
    lib = gds_export.LIB_LAYER_SI
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
    return elements


def _io_grating_elements(link, placement, wg_width) -> List[bytes]:
    """IO 光栅耦合器接入：每个外部端口放真实光栅齿区几何。"""
    elements = []
    for (inst, port) in io_ports_of(link):
        ox, oy = port_abs(inst, port, placement, link)
        descs = primitive_descs("grating_coupler",
                                {"width": wg_width, "n_tooth": 16})
        for d in descs:
            pts = [(ox + px, oy + py) for px, py in d.get("points_um", [])]
            if d["kind"] == "path":
                elements.append(gds_export.path(d["layer"], d["width_um"], pts))
            else:
                flat = [pp for ring in d.get("rings_um", []) for pp in ring]
                elements.append(gds_export.boundary(d["layer"], flat))
    return elements


def chip_layout_stats(link, placement, routes) -> Dict[str, Any]:
    """芯片版图统计（bbox/面积/器件/IO/层）。"""
    xs: List[float] = []
    ys: List[float] = []
    for c in link.ir.components:
        ox, oy, _ = placement[c.id]
        hw, hh = device_bbox(c.kind, dict(c.params))
        xs += [ox - hw, ox + hw]
        ys += [oy - hh, oy + hh]
    for rr in (routes or {}).values():
        for px, py in _route_points(rr):
            xs.append(px)
            ys.append(py)
    x0, x1 = (min(xs), max(xs)) if xs else (0.0, 0.0)
    y0, y1 = (min(ys), max(ys)) if ys else (0.0, 0.0)
    layers = {1}  # 默认硅层；按元素实际层补充由调用方传入
    return {
        "n_devices": len(link.ir.components),
        "n_io": len(io_ports_of(link)),
        "bbox_um": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
        "area_um2": round((x1 - x0) * (y1 - y0), 2),
        "width_um": round(x1 - x0, 2),
        "height_um": round(y1 - y0, 2),
        "n_nets": len(link.ir.nets),
    }


def _drc_params(kind: str, params: Dict[str, float]) -> Dict[str, float]:
    """链路参数 → DRC 检查参数（单位归一）。

    链路引擎约定：RingResonator 的 R 单位 **mm**（registry._ring_response 同源），
    而 DRC 规则（min_bend_R 等）单位 **µm** → 归一化 R_mm ×1000 = R_µm，
    避免把 0.0099 mm（=9.9 µm，合规）误判为 0.0099 µm 违规。
    """
    p = dict(params)
    if p.get("R") is not None:
        p["R"] = float(p["R"]) * 1000.0  # mm → µm
    return p


def chip_drc_report(link, placement, rules: Optional[Dict[str, float]] = None
                    ) -> Dict[str, Any]:
    """芯片级版图 DRC 可制造性自查（对链路所有器件，死标量）。"""
    results = {}
    for c in link.ir.components:
        try:
            r = drc_check_device(c.kind, _drc_params(c.kind, dict(c.params)),
                                 rules=rules)
            results[c.id] = {"passed": r.passed, "brief": r.brief()}
        except Exception as e:  # noqa: BLE001 —— 未知 kind 不阻断芯片级报告
            results[c.id] = {"passed": False, "brief": f"DRC 未覆盖：{str(e)[:40]}"}
    all_pass = all(v["passed"] for v in results.values())
    return {"all_pass": all_pass,
            "n_checked": len(results),
            "n_pass": sum(1 for v in results.values() if v["passed"]),
            "devices": results,
            "summary": drc_summary({c.id: drc_check_device(
                c.kind, _drc_params(c.kind, dict(c.params)), rules=rules)
                for c in link.ir.components})}


def export_chip_gds(link, placement, routes, wg_width: float = 0.5,
                    with_io_grating: bool = True,
                    rules: Optional[Dict[str, float]] = None
                    ) -> Dict[str, Any]:
    """芯片级版图导出主入口：器件 + 布线 + IO 光栅 + 统计 + DRC + LVS。

    返回 {gds_bytes, gds_parse, gds_stats, drc_report, lvs_report, io_ports}。
    v0.8.24：新增 lvs_report（版图-原理图一致性签核，与 DRC 并列双闸）。
    """
    elements = _device_elements(link, placement, wg_width)
    for net_id, rr in (routes or {}).items():
        elements.append(gds_export.path(gds_export.LIB_LAYER_SI,
                                        wg_width, _route_points(rr)))
    if with_io_grating:
        elements.extend(_io_grating_elements(link, placement, wg_width))

    gds_bytes = gds_export.gds_library("LDA_CHIP", {"CHIP": elements})
    parse = gds_export.parse_gds(gds_bytes)
    stats = chip_layout_stats(link, placement, routes)
    stats["n_elements"] = len(elements)
    stats["n_structures"] = (parse.get("n_structures")
                             if isinstance(parse, dict) else None)
    stats["gds_bytes"] = len(gds_bytes)
    drc = chip_drc_report(link, placement, rules=rules)
    lvs = run_lvs(link, placement, routes)
    return {
        "gds_bytes": gds_bytes,
        "gds_parse": parse,
        "gds_stats": stats,
        "drc_report": drc,
        "lvs_report": lvs,
        "io_ports": [f"{i}.{p}" for i, p in io_ports_of(link)],
    }


def layout_markdown(link, placement, routes, wg_width: float = 0.5,
                    rules: Optional[Dict[str, float]] = None) -> str:
    """芯片版图 markdown 报告（器件/布线/IO/统计/DRC/LVS）。"""
    r = export_chip_gds(link, placement, routes, wg_width=wg_width, rules=rules)
    st = r["gds_stats"]
    drc = r["drc_report"]
    lvs = r["lvs_report"]
    L = []
    L.append("# LDA 芯片版图导出报告（可测芯片版图）")
    L.append("")
    L.append(f"- 器件 {st['n_devices']} · net {st['n_nets']} · IO 端口 {st['n_io']}"
             f"（含光栅耦合器接入）")
    L.append(f"- 芯片 bbox：{st['bbox_um']} µm · 面积 {st['area_um2']} µm²")
    L.append(f"- GDS：{st['gds_bytes']} B · {st['n_structures']} 结构 · "
             f"{st['n_elements']} 元素")
    L.append(f"- DRC：{drc['n_pass']}/{drc['n_checked']} 器件通过"
             f"（{'✅ 可制造性自查通过' if drc['all_pass'] else '❌ 有违规，见明细'}）")
    L.append(f"- LVS：**{lvs['verdict']}**（{'✅ 版图-原理图一致'
             if lvs['verdict'] == 'ACCEPT' else '❌ 有失配，见明细'}）"
             f" · {lvs['match']['n_nets_match']}/{lvs['match']['n_nets_total']} 网一致"
             f" · 违规 {lvs['n_violations']} 项")
    L.append("")
    L.append("## 器件与 DRC 明细")
    L.append("")
    L.append("| 器件 | kind | DRC | 说明 |")
    L.append("|---|---|---|---|")
    for c in link.ir.components:
        d = drc["devices"].get(c.id, {})
        mark = "✅" if d.get("passed") else "❌"
        L.append(f"| {c.id} | {c.kind} | {mark} | {d.get('brief','')[:60]} |")
    L.append("")
    L.append("## IO 端口（光栅耦合器接入）")
    L.append("")
    for p in r["io_ports"]:
        L.append(f"- `{p}`")
    L.append("")
    L.append(lvs_markdown(lvs))
    L.append("")
    L.append("*本报告为芯片级版图（原理图→可测版图），非流片级；"
             "光栅耦合器为几何交付（耦合效率需 D-72 FDTD 验证）。*")
    return "\n".join(L)
