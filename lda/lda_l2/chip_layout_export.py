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

# ── 几何中间表示（v0.9.33 P0-1）────────────────────────────────────────────
# 层次化导出需要「几何」而非「已编码的 GDS 字节」（字节无法再平移/归一化到
# cell 局部坐标）。故把几何生成与 GDS 编码拆成两层，flat 与层次化共用同一份
# 几何生成 —— 不允许出现第二份副本（P0-0 的根因就是同一段逻辑抄两遍）。
#
#   ("P", layer, width_um, points)   PATH     走线
#   ("B", layer, None,     points)   BOUNDARY 多边形
# points 为 ((x, y), ...) µm；坐标一律**绝对**（未归一化）。
Geom = Tuple


def _encode_geom(g: Geom) -> bytes:
    """几何元组 → GDS 元素字节（唯一的编码出口）。"""
    if g[0] == "P":
        return gds_export.path(g[1], g[2], list(g[3]))
    return gds_export.boundary(g[1], list(g[3]))


def _shift_geom(g: Geom, dx: float, dy: float) -> Geom:
    """几何平移。"""
    return (g[0], g[1], g[2],
            tuple((x + dx, y + dy) for x, y in g[3]))


def _rebase_geom(g: Geom, ox: float, oy: float) -> Geom:
    """绝对坐标 → 相对单元原点（cell 局部坐标）。

    round 到 1e-9 µm（= 1e-6 DBU）消除浮点末位噪声；真正的量化在编码时
    由 `_to_dbu` 完成。层次化会引入「减原点 + 加实例位置」的浮点往返，
    可能在 .5 DBU 边界产生 1 DBU（1 nm）舍入差 —— 版图精度下无意义，
    但护栏会显式统计而不过滤。
    """
    return (g[0], g[1], g[2],
            tuple((round(x - ox, 9), round(y - oy, 9)) for x, y in g[3]))


def _geom_key(g: Geom, q: int = 1000) -> Tuple:
    """DBU 量化后的比对键（等价性验证用，消除浮点末位噪声）。"""
    pts = tuple((int(round(x * q)), int(round(y * q))) for x, y in g[3])
    w = None if g[2] is None else int(round(g[2] * q))
    return (g[0], g[1], w, pts)


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
    """RouteResult / dict / 多层段列表 → 折线点（聚合全部段）。"""
    if isinstance(rr, (list, tuple)):          # v0.8.26 多层：段列表
        pts: List[Tuple[float, float]] = []
        for seg in rr:
            pts.extend(_route_points(seg))
        return pts
    if isinstance(rr, dict):
        return list(rr.get("points_um") or [])
    return list(getattr(rr, "points_um", []) or [])


def _is_multilayer_routes(routes) -> bool:
    """routes 是否多层（任一 net 值为段列表，v0.8.26 千器件跨行跳线）。"""
    for val in (routes or {}).values():
        if isinstance(val, (list, tuple)):
            return True
    return False


def _desc_geoms(desc: Dict, ox: float, oy: float) -> List[Geom]:
    """几何描述（geometry_desc / primitive_descs）→ 几何元组，统一施加原点偏移。

    v0.9.32 P0-0 修复：此前 path 分支施加了 (ox,oy) 而 boundary 分支没有，
    两处调用点（_device_elements / _io_grating_elements）各抄一遍、错得一样。
    primitive_descs('grating_coupler') 返回 1 path + 16 boundary（光栅齿），
    于是齿全部堆在局部原点，而真正的 IO 端口处没有任何齿结构——CPO 250k
    里 174,080 个齿（占元素 19.4%）全部错位，据此外协流片 IO 耦合器会失效。
    体积/元素数类断言因器件主体走 path 而不受影响，故缺陷长期潜伏。

    v0.9.33 P0-1：拆出「几何层」——返回 Geom 元组而非 GDS 字节，使层次化
    导出与 flat 导出**共用同一份几何生成**，杜绝第二份副本（P0-0 的根因
    正是同一段逻辑被抄两遍）。字节编码统一由 `_encode_geom` 负责。

    已知待办（本次不修，避免扩大回归面）：boundary 的 rings_um 支持多环
    （带孔多边形），当前展平为单环；GDS BOUNDARY 仅支持单环，正确做法是
    每环一个元素。当前全部基元数据均为单环，故展平不改变元素数。
    """
    if desc["kind"] == "path":
        pts = tuple((ox + px, oy + py) for px, py in desc.get("points_um", []))
        return [("P", desc["layer"], desc["width_um"], pts)]
    flat = tuple((ox + px, oy + py)
                 for ring in desc.get("rings_um", []) for px, py in ring)
    return [("B", desc["layer"], None, flat)]


def _desc_elements(desc: Dict, ox: float, oy: float) -> List[bytes]:
    """几何描述 → GDS 元素字节（薄委托 `_desc_geoms`，保持对外接口不变）。"""
    return [_encode_geom(g) for g in _desc_geoms(desc, ox, oy)]


def device_geom_of(c, placement, wg_width) -> List[Geom]:
    """单个器件的几何（绝对坐标 µm）—— 器件几何的**唯一定义处**。

    v0.9.33 P0-1：`device_geoms` 与层次化模块都薄委托到此，杜绝第二份副本
    （P0-0 的根因就是同一段逻辑抄两遍、错得一样）。
    """
    ox, oy = placement[c.id][0], placement[c.id][1]
    params = dict(c.params)
    lib = gds_export.LIB_LAYER_SI
    if c.kind in ("RingResonator", "RingAddDrop"):
        R = float(params.get("R", 10.0))
        wg_w = float(params.get("wg_width", wg_width))
        gap = float(params.get("gap", 0.3))
        half = R * 1.5
        off = R + wg_w / 2.0 + gap
        ring_pts = tuple((ox + R * math.cos(2.0 * math.pi * i / 64),
                          oy + R * math.sin(2.0 * math.pi * i / 64))
                         for i in range(64))
        return [("P", lib, wg_w, ring_pts),
                ("P", lib, wg_w,
                 ((ox - half, oy - off), (ox + half, oy - off))),
                ("P", lib, wg_w,
                 ((ox - half, oy + off), (ox + half, oy + off)))]
    if c.kind == "Waveguide":
        length = float(params.get("length", 10.0))
        return [("P", lib, wg_width, ((ox, oy), (ox + length, oy)))]
    if c.kind == "GratingCoupler":
        L = float(params.get("L", 10.0))
        return [("P", lib, wg_width, ((ox, oy), (ox, oy + L)))]
    out: List[Geom] = []
    for d in gds_export.geometry_desc(c.kind, params):
        out.extend(_desc_geoms(d, ox, oy))
    return out


def device_geoms(link, placement, wg_width) -> List[Geom]:
    """器件几何（绝对坐标 µm）。与 `device_elements` 同源，供层次化复用。"""
    out: List[Geom] = []
    for c in link.ir.components:
        out.extend(device_geom_of(c, placement, wg_width))
    return out


def device_elements(link, placement, wg_width) -> List[bytes]:
    """器件版图元素（薄委托 `device_geoms`）。"""
    return [_encode_geom(g) for g in device_geoms(link, placement, wg_width)]


def io_grating_geoms(link, placement, wg_width) -> List[Geom]:
    """IO 光栅耦合器几何：每个外部端口放真实光栅齿区几何（绝对坐标 µm）。"""
    out: List[Geom] = []
    for (inst, port) in io_ports_of(link):
        ox, oy = port_abs(inst, port, placement, link)
        descs = primitive_descs("grating_coupler",
                                {"width": wg_width, "n_tooth": 16})
        for d in descs:
            out.extend(_desc_geoms(d, ox, oy))
    return out


def io_grating_elements(link, placement, wg_width) -> List[bytes]:
    """IO 光栅元素（薄委托 `io_grating_geoms`）。"""
    return [_encode_geom(g) for g in io_grating_geoms(link, placement, wg_width)]


def route_geoms(routes, wg_width) -> List[Geom]:
    """布线几何（绝对坐标 µm）。

    ⚠️ 与 `export_chip_gds` 的既有行为保持**逐条一致**：每条 net 无条件产出
    一个 PATH，即使 `_route_points` 返回空（当前 WDM 案例有 2 条这样的空
    path）。过滤它们会改变元素数与字节数，破坏 bit-exact 基线。
    **已知待办**：空 PATH 在 GDS 里是无 XY 的畸形记录，应在确认下游无依赖
    后单独清理（本次不动，避免扩大回归面）。
    """
    lib = gds_export.LIB_LAYER_SI
    out: List[Geom] = []
    for _net_id, rr in (routes or {}).items():
        out.append(("P", lib, wg_width, tuple(_route_points(rr))))
    return out


# 向后兼容别名（旧私有名在外仓/脚本中可能被引用）
_device_elements = device_elements
_io_grating_elements = io_grating_elements


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
                    rules: Optional[Dict[str, float]] = None,
                    with_hierarchy: bool = True
                    ) -> Dict[str, Any]:
    """芯片级版图导出主入口：器件 + 布线 + IO 光栅 + 统计 + DRC + LVS。

    返回 {gds_bytes, gds_parse, gds_stats, drc_report, lvs_report, io_ports,
          hierarchy}。
    v0.8.24：新增 lvs_report（版图-原理图一致性签核，与 DRC 并列双闸）。
    v0.8.26：自动检测多层 routes（net_id → [RouteResult, ...] 段列表，
    千器件跨行跳线）——多层时 lvs_report 用 run_lvs_multilayer（层叠短路
    语义），GDS 段按段绘制。

    v0.9.33（P0-1）**层次化导出**：`with_hierarchy=True`（默认）时先尝试
    识别版图中的重复单元，成功则用 **cell + AREF** 输出（CPO 250k 实测
    897,600 元素 / 97.45 MB → **331 元素 / 36 KB**）。失败则**自动回退
    flat**，并在返回的 `hierarchy` 字典中写明原因 —— 绝不静默。

    ⚠️ 层次化只影响 `gds_bytes` / `n_elements` / `n_structures`；
    **DRC 与 LVS 判决完全不受影响**（它们基于 link/placement/routes 而非
    GDS 元素，且层次化展开与 flat 逐元素等价，见 `lda_l2.hierarchy`）。

    ⚠️ 下游读取层次化 GDS 时，`parse_gds_polygons` 默认**展开引用**
    （`expand_refs=True`），否则 DRC/RC 只会看到 1 条 AREF ⇒ 假绿。
    """
    multi = _is_multilayer_routes(routes)

    # ── 层次化尝试（失败即回退 flat，原因显式记录）
    hier_info: Dict[str, Any] = {"applied": False, "reason": "",
                                 "n_elements_flat": None,
                                 "n_instances": 0, "period": 0,
                                 "cell_elements": 0, "top_elements": 0}
    gds_bytes = None
    if with_hierarchy:
        try:
            from lda_l2.hierarchy import detect_hierarchy, encode_hierarchical
            plan = detect_hierarchy(link, placement, routes, wg_width,
                                    with_io_grating=with_io_grating)
        except Exception as exc:                      # 检测异常 ⇒ 回退，不传播
            plan = None
            hier_info["reason"] = f"detect_error: {type(exc).__name__}: {exc}"
        if plan is None:
            hier_info["reason"] = hier_info["reason"] or "no_repeating_cell"
        else:
            hier_info.update({
                "applied": True,
                "reason": "ok",
                "n_instances": plan.n_inst,
                "period": plan.period,
                "cell_elements": len(plan.cell_geoms),
                "top_elements": len(plan.top_geoms),
                "use_aref": plan.use_aref,
                "array": [plan.nx, plan.ny],
                "pitch_um": [round(plan.dx, 6), round(plan.dy, 6)],
            })
            gds_bytes = encode_hierarchical(plan)

    # ── flat 路径（层次化未启用 / 检测失败时的基线）
    elements = device_elements(link, placement, wg_width)
    for net_id, rr in (routes or {}).items():
        elements.append(gds_export.path(gds_export.LIB_LAYER_SI,
                                        wg_width, _route_points(rr)))
    if with_io_grating:
        elements.extend(io_grating_elements(link, placement, wg_width))
    hier_info["n_elements_flat"] = len(elements)
    if gds_bytes is None:
        gds_bytes = gds_export.gds_library("LDA_CHIP", {"CHIP": elements})

    parse = gds_export.parse_gds(gds_bytes)
    stats = chip_layout_stats(link, placement, routes)
    stats["n_elements"] = (hier_info["cell_elements"]
                           + hier_info.get("top_elements", 0)
                           + (1 if hier_info.get("use_aref")
                              else hier_info["n_instances"])
                           if hier_info["applied"] else len(elements))
    stats["n_structures"] = (parse.get("n_structures")
                             if isinstance(parse, dict) else None)
    stats["gds_bytes"] = len(gds_bytes)
    stats["multilayer"] = multi
    drc = chip_drc_report(link, placement, rules=rules)
    if multi:
        from lda_l2.layers import get_stack
        from lda_l2.lvs import run_lvs_multilayer
        lvs = run_lvs_multilayer(link, placement, routes, stack=get_stack("soi"))
    else:
        lvs = run_lvs(link, placement, routes)
    return {
        "gds_bytes": gds_bytes,
        "gds_parse": parse,
        "gds_stats": stats,
        "drc_report": drc,
        "lvs_report": lvs,
        "io_ports": [f"{i}.{p}" for i, p in io_ports_of(link)],
        "hierarchy": hier_info,
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
