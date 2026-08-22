"""LDA L2 · GDSII 版图出口（D-14：器件库/IR → 可制造版图）。

把已验证器件（D-12 器件库）+ L0 IR 布局导出为 **GDSII**（业界标准版图格式），
为阶段 3 真实版图生成铺路。自写**零依赖**最小 GDSII 编码器——不依赖
gdsfactory / gdspy / KLayout（B 级外部工具，按"量力借力不硬刚"纪律后续可 fork
增强，但核心出口主权自持）。

能力（最小可用子集，标准公开格式）：
  - GDSII 库文件编码：HEADER/BGNLIB/LIBNAME/UNITS/BGNSTR/STRNAME/ENDSTR/ENDLIB
  - 元素：BOUNDARY（多边形）、PATH（走线，带 WIDTH）、SREF（单元引用，可选）
  - IR → 版图：Waveguide / RingResonator / DirectionalCoupler / SymmetricYBranch
    的几何参数 → 层 + 多边形/PATH
  - SVG 预览（版图可视化，浏览器可看）+ 最小解析器（读回验证 round-trip）

坐标：数据库单位 DBU=1e-3 µm（=1 nm 精度），坐标 INT4（µm → DBU 取整）。
"""

from __future__ import annotations

import math
import struct
from typing import Dict, List, Optional, Sequence, Tuple

DBU = 1e-3                     # 数据库单位（µm）→ 1 DBU = 1 nm
LIB_LAYER_SI = 1               # 顶层硅（芯层）
LIB_LAYER_CLAD = 2             # 包层/BOX
LIB_LAYER_METAL = 3            # 金属层
LIB_LAYER_LABEL = 4


# ---------------------------------------------------------------------------
# GDSII 记录编码（标准公开格式）
# ---------------------------------------------------------------------------
def _rec(rectype: int, datatype: int, payload: bytes) -> bytes:
    n = 4 + len(payload)
    if n % 2:
        n += 1
    out = struct.pack(">H", n) + bytes([rectype, datatype]) + payload
    if len(payload) % 2:
        out += b"\x00"
    return out


def _int2(v: int) -> bytes:
    return struct.pack(">h", int(v))


def _int4_list(vs: Sequence[int]) -> bytes:
    return struct.pack(">%di" % len(vs), *[int(v) for v in vs])


def _int4(v: int) -> bytes:
    return struct.pack(">i", int(v))


def _real8(v: float) -> bytes:
    return struct.pack(">d", float(v))


def _ascii(s: str) -> bytes:
    b = s.encode("ascii", "ignore")
    if len(b) % 2:
        b += b"\x00"
    return b


def _to_dbu(v: float) -> int:
    return int(round(float(v) / DBU))


# ---------------------------------------------------------------------------
# GDSII 元素构造
# ---------------------------------------------------------------------------
def boundary(layer: int, points_um: Sequence[Sequence[float]]) -> bytes:
    """BOUNDARY 多边形（points 为 (x,y) µm 列表；自动闭合）。"""
    pts = [p for xy in points_um for p in xy]
    if (pts[0], pts[1]) != (pts[-2], pts[-1]):
        pts = pts + [pts[0], pts[1]]
    out = _rec(0x08, 0, b"")                       # BOUNDARY
    out += _rec(0x0D, 2, _int2(layer))             # LAYER
    out += _rec(0x0E, 2, _int2(0))                 # DATATYPE
    out += _rec(0x10, 3, _int4_list([_to_dbu(p) for p in pts]))  # XY (DBU)
    out += _rec(0x11, 0, b"")                      # ENDEL
    return out


def path(layer: int, width_um: float, points_um: Sequence[Sequence[float]]) -> bytes:
    """PATH 走线（宽度 width_um，路径点 µm）。"""
    pts = [p for xy in points_um for p in xy]
    out = _rec(0x09, 0, b"")                       # PATH
    out += _rec(0x0D, 2, _int2(layer))             # LAYER
    out += _rec(0x0F, 3, _int4(_to_dbu(width_um)))  # WIDTH (DBU)
    out += _rec(0x10, 3, _int4_list([_to_dbu(p) for p in pts]))  # XY (DBU)
    out += _rec(0x11, 0, b"")                      # ENDEL
    return out


def sref(sname: str, origin_um: Sequence[float], layer: int = LIB_LAYER_SI) -> bytes:
    """SREF 单元引用（原点 µm）。"""
    out = _rec(0x0A, 0, b"")                       # SREF
    out += _rec(0x12, 6, _ascii(sname))            # SNAME
    out += _rec(0x0D, 2, _int2(layer))             # LAYER
    out += _rec(0x10, 3, _int4_list([_to_dbu(origin_um[0]), _to_dbu(origin_um[1])]))
    out += _rec(0x11, 0, b"")                      # ENDEL
    return out


def gds_library(name: str, structures: Dict[str, List[bytes]]) -> bytes:
    """GDSII 库文件：库头 + 各结构（单元名 → 元素记录列表）。"""
    out = b""
    out += _rec(0x00, 2, _int2(600))               # HEADER（版本 600）
    out += _rec(0x01, 0, b"")                      # BGNLIB
    out += _rec(0x02, 6, _ascii(name))             # LIBNAME
    out += _rec(0x03, 5, _real8(DBU) + _real8(1.0 / DBU))  # UNITS
    for sname, elements in structures.items():
        out += _rec(0x05, 0, b"")                  # BGNSTR
        out += _rec(0x06, 6, _ascii(sname))        # STRNAME
        for el in elements:
            out += el
        out += _rec(0x07, 0, b"")                  # ENDSTR
    out += _rec(0x04, 0, b"")                      # ENDLIB
    return out


# ---------------------------------------------------------------------------
# 器件几何 → 版图元素（IR Component / 器件库参数 → GDS）
# ---------------------------------------------------------------------------
def ring_polygon(R_um: float, n_sides: int = 64) -> List[Tuple[float, float]]:
    """圆多边形近似（顺时针，n_sides 段）。"""
    return [(R_um * math.cos(2.0 * math.pi * i / n_sides),
             R_um * math.sin(2.0 * math.pi * i / n_sides))
            for i in range(n_sides)]


def ring_ring_polygon(R_um: float, width_um: float,
                      n_sides: int = 64) -> List[List[Tuple[float, float]]]:
    """环形（外环 + 内环，BOUNDARY 多环）。外环顺时针、内环逆时针挖洞。"""
    outer = ring_polygon(R_um + width_um / 2.0, n_sides)
    inner = ring_polygon(R_um - width_um / 2.0, n_sides)
    return [outer, list(reversed(inner))]


def _flatten_rings(rings: List[List[Tuple[float, float]]]) -> List[Tuple[float, float]]:
    """把多环 BOUNDARY 展平为 GDS XY（每环闭合）。"""
    pts: List[Tuple[float, float]] = []
    for r in rings:
        pts.extend(r)
        pts.append(r[0])          # 环闭合
    return pts


def geometry_desc(kind: str, params: Dict[str, float], **opt) -> List[Dict]:
    """器件 kind + 参数 → 几何元素描述（单一来源，GDS 编码 / SVG / DRC 复用）。

    每个 desc：{'kind': 'path'|'boundary', 'layer': int, ...}
      path     : + width_um + points_um（折线）
      boundary : + rings_um（多环多边形，每环闭合点列表）

    参数（µm）：Waveguide{width,length}；RingResonator{R,...} + wg_width；
    DirectionalCoupler{gap,Lc,width}；SymmetricYBranch{width,split_angle,arm_length}；
    RingAddDrop{R, wg_width, gap}（D-37 环形 add-drop：环 + through/drop 双 bus，
    端口：input→through（下 bus，y=-off）、add→drop（上 bus，y=+off），
    off = R + wg_width/2 + gap）。
    """
    core_w = float(params.get("width", 0.5))
    descs: List[Dict] = []

    if kind == "Waveguide":
        length = float(opt.get("length", params.get("length", 10.0)))
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": core_w,
                      "points_um": [(0.0, 0.0), (length, 0.0)]})
    elif kind == "RingResonator":
        R = float(params.get("R", 10.0))
        wg_w = float(opt.get("wg_width", params.get("wg_width", 0.5)))
        descs.append({"kind": "boundary", "layer": LIB_LAYER_SI,
                      "rings_um": ring_ring_polygon(R, wg_w)})
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": wg_w,
                      "points_um": [(-R * 1.4, -R - wg_w / 2.0),
                                    (R * 1.4, -R - wg_w / 2.0)]})
    elif kind == "RingAddDrop":
        # D-37：环形 add-drop（双 bus）。环居中，through bus 在下，drop bus 在上。
        R = float(params.get("R", 10.0))
        wg_w = float(opt.get("wg_width", params.get("wg_width", 0.5)))
        gap = float(params.get("gap", 0.3))
        half = float(opt.get("bus_half_length", R * 1.5))
        off = R + wg_w / 2.0 + gap
        descs.append({"kind": "boundary", "layer": LIB_LAYER_SI,
                      "rings_um": ring_ring_polygon(R, wg_w)})
        # through（下 bus）：input → through
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": wg_w,
                      "points_um": [(-half, -off), (half, -off)]})
        # drop（上 bus）：add → drop
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": wg_w,
                      "points_um": [(-half, off), (half, off)]})
    elif kind == "DirectionalCoupler":
        gap = float(params.get("gap", 0.3))
        Lc = float(params.get("Lc", 10.0))
        off = (gap + core_w) / 2.0
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": core_w,
                      "points_um": [(0.0, off), (Lc, off)]})
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": core_w,
                      "points_um": [(0.0, -off), (Lc, -off)]})
    elif kind == "SymmetricYBranch":
        angle = math.radians(float(params.get("split_angle", 10.0)))
        arm = float(params.get("arm_length", 5.0))
        half = angle / 2.0
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": core_w,
                      "points_um": [(0.0, 0.0),
                                    (arm * math.cos(half), arm * math.sin(half))]})
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": core_w,
                      "points_um": [(0.0, 0.0),
                                    (arm * math.cos(half), -arm * math.sin(half))]})
    # ---- D-71 真实版图基元（foundry-ready；几何交付，电特性归 D-72）----
    elif kind in ("Taper", "EulerBend", "MMI", "GratingCoupler"):
        from lda_l2.primitives import primitive_descs as _prim
        descs.extend(_prim(kind, params))
    else:
        raise ValueError(f"暂不支持导出 kind={kind}")
    return descs


def layout_elements(kind: str, params: Dict[str, float], **opt) -> List[bytes]:
    """IR 器件 kind + 参数 → GDSII 元素记录列表（由 geometry_desc 生成）。"""
    elements: List[bytes] = []
    for d in geometry_desc(kind, params, **opt):
        if d["kind"] == "path":
            elements.append(path(d["layer"], d["width_um"], d["points_um"]))
        else:
            elements.append(boundary(d["layer"],
                                     _flatten_rings(d.get("rings_um"))))
    return elements


def layout_from_ir(model, library=None) -> Dict[str, List[bytes]]:
    """L0 IR → GDS 结构字典。取 primary_component，参数来自 IR params。"""
    prim = model.primary_component
    if prim is None:
        raise ValueError("IR 无 component，无法导出版图")
    return {prim.id: layout_elements(prim.kind, dict(prim.params))}


def gds_bytes_for(model, lib_name: str = "LDA", library=None) -> bytes:
    """L0 IR → 完整 GDSII 文件字节。"""
    return gds_library(lib_name, layout_from_ir(model, library=library))


def layout_from_library(library=None) -> Dict[str, List[bytes]]:
    """D-12 已验证器件库 → GDS 结构（各器件取参数窗口默认值/中值）。

    串联 D-12（器件库）→ D-14（GDS 出口）：注册表里每个有几何表达的已验证
    器件都导出为一个 GDS 单元。一维堆叠器件（BraggMirror，无 2D 版图几何）
    跳过并提示。
    """
    if library is None:
        from lda_l2.device_library import get_default_library
        library = get_default_library()
    structs: Dict[str, List[bytes]] = {}
    skipped = []
    for name in library.list():
        dev = library.get(name)
        params = {k: (lo + hi) / 2.0 for k, (lo, hi) in dev.params_schema.items()}
        try:
            structs[name] = layout_elements(name, params)
        except ValueError:
            skipped.append(name)
    if skipped:
        print(f"[gds] 跳过无 2D 版图几何的器件（一维堆叠）：{skipped}")
    return structs


# ---------------------------------------------------------------------------
# SVG 版图预览（浏览器可看）
# ---------------------------------------------------------------------------
def _svg_elements(elements: List[bytes], layer_color: Dict[int, str],
                  bounds) -> str:
    # 简化：不解析 GDS 元素，直接基于几何参数重新渲染（供预览）
    raise NotImplementedError("SVG 预览由几何层渲染，见 svg_preview")


def svg_preview(structures: Dict[str, List[Tuple[str, dict]]], width=560) -> str:
    """由 (element_kind, params) 描述渲染 SVG（不解析 GDS 字节，直接几何）。

    element_kind ∈ {'path','boundary'}；params 含 layer/points_um/width_um。
    注：本函数用于快速预览；权威版图以 GDSII 字节为准。
    """
    layer_color = {1: "#38bdf8", 2: "#8aa0c6", 3: "#f5c542", 4: "#e91e63"}
    xs, ys = [], []
    for _sname, items in structures.items():
        for _ekind, p in items:
            pts = p["points_um"]
            xs += [pt[0] for pt in pts]
            ys += [pt[1] for pt in pts]
    if not xs:
        return "<p>（空版图）</p>"
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    span = max(xmax - xmin, ymax - ymin, 1e-6)
    pad = 30
    S = (width - 2 * pad) / span
    X = lambda x: pad + (x - xmin) * S
    Y = lambda y: pad + (ymax - y) * S
    out = [f'<svg width="{width}" height="{width * (span + 2 * pad) / (span + 2 * pad)}" '
           'style="background:#fff;border:1px solid #ddd;border-radius:6px">']
    for _sname, items in structures.items():
        for ekind, p in items:
            col = layer_color.get(p.get("layer", 1), "#38bdf8")
            pts = p["points_um"]
            if ekind == "path":
                d = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in pts)
                out.append(f'<polyline points="{d}" fill="none" '
                           f'stroke="{col}" stroke-width="{max(p.get("width_um",0.5)*S,2):.1f}"/>')
            else:
                d = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in pts)
                out.append(f'<polygon points="{d}" fill="{col}" fill-opacity="0.65"/>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------
# 最小 GDSII 解析器（读回验证 round-trip）
# ---------------------------------------------------------------------------
def parse_gds(data: bytes) -> Dict:
    """解析 GDSII 字节，返回摘要（库名/结构/元素计数/层集合）。

    仅覆盖本编码器用到的记录类型；用于验证导出版图可被标准工具读取。
    """
    i = 0
    libname = ""
    structures: Dict[str, dict] = {}
    cur = None
    n = len(data)
    while i < n:
        (ln,) = struct.unpack_from(">H", data, i)
        rectype, datatype = data[i + 2], data[i + 3]
        payload = data[i + 4:i + ln]
        if rectype == 0x02:                       # LIBNAME
            libname = payload.decode("ascii", "ignore").rstrip("\x00")
        elif rectype == 0x06:                     # STRNAME
            sname = payload.decode("ascii", "ignore").rstrip("\x00")
            cur = {"elements": 0, "layers": set()}
            structures[sname] = cur
        elif rectype in (0x08, 0x09, 0x0A):       # BOUNDARY/PATH/SREF
            if cur is not None:
                cur["elements"] += 1
        elif rectype == 0x0D:                     # LAYER
            if cur is not None and len(payload) >= 2:
                (layer,) = struct.unpack_from(">h", payload, 0)
                cur["layers"].add(layer)
        i += ln
    return {"libname": libname, "structures": structures,
            "n_structures": len(structures)}


def write_gds(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)
