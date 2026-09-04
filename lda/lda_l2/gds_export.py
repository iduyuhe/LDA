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


def aref(sname: str, origin_um: Sequence[float], dx_um: float, dy_um: float,
         nx: int, ny: int, layer: int = LIB_LAYER_SI) -> bytes:
    """AREF 阵列引用（二维等间距矩形阵列，无旋转/镜像）· v0.9.33 P0-1。

    一条 AREF 记录即可表达 nx×ny 个单元实例——这是层次化压缩的关键：
    CPO 250k 的 2,720 个相同通道由 **1 条 AREF** 表示（flat 需 897,600 个元素）。

    GDSII 标准 XY 为三点（DBU 整数）：
      P1 = 阵列原点 (ox, oy)
      P2 = (ox + dx·nx, oy)          —— 列方向总跨度
      P3 = (ox, oy + dy·ny)          —— 行方向总跨度
    单点间距由 (P2−P1)/nx、(P3−P1)/ny 推出，故 dx/dy 是**间距**而非总跨度。

    ⚠️ 与既有 `sref` 一致，本记录也写了 LAYER（0x0D）。严格 GDSII 中
    SREF/AREF 不含 LAYER，此处的 LAYER 是 LDA 内部约定（便于按层过滤），
    保持与 sref 的既有行为一致以免破坏已生成的版图。

    ⚠️ **解析器必须能展开引用**：`parse_gds_polygons(expand_refs=True)`
    会把 AREF 还原成 nx×ny 份实际几何。若不展开，层次化 GDS 喂给
    `gds_drc` / `parasitic_rc` 只会看到 1 个元素 ⇒ **DRC 假绿**。
    """
    ox, oy = float(origin_um[0]), float(origin_um[1])
    out = _rec(0x0B, 0, b"")                       # AREF
    out += _rec(0x12, 6, _ascii(sname))            # SNAME
    out += _rec(0x0D, 2, _int2(layer))             # LAYER（LDA 内部约定，见上）
    out += _rec(0x1A, 2, _int2(0))                 # STRANS（无变换）
    out += _rec(0x13, 2, _int2(int(nx)) + _int2(int(ny)))   # COLROW
    xy = [ox, oy, ox + dx_um * nx, oy, ox, oy + dy_um * ny]
    out += _rec(0x10, 3, _int4_list([_to_dbu(v) for v in xy]))
    out += _rec(0x11, 0, b"")                      # ENDEL
    return out


def gds_library(name: str, structures: Dict[str, List[bytes]]) -> bytes:
    """GDSII 库文件：库头 + 各结构（单元名 → 元素记录列表）。

    v0.8.46 · 性能：累计字节改「收 list 后 b''.join()」一次性拼接。
    原因：CPython 的 ``bytes += bytes`` **不做超额分配**，循环里逐段 ``+=``
    每次复制整段 growing buffer → 整体 O(n²)（gds_library 在 20k 器件已占
    全链 77% 墙钟，50k 56s、100k OOM）。list + join 为 O(n) 且**字节级一致**
    （拼接顺序与内容不变，输出 bit-exact 同旧实现）。
    """
    chunks: List[bytes] = []
    chunks.append(_rec(0x00, 2, _int2(600)))       # HEADER（版本 600）
    chunks.append(_rec(0x01, 0, b""))              # BGNLIB
    chunks.append(_rec(0x02, 6, _ascii(name)))     # LIBNAME
    chunks.append(_rec(0x03, 5, _real8(DBU) + _real8(1.0 / DBU)))  # UNITS
    for sname, elements in structures.items():
        chunks.append(_rec(0x05, 0, b""))          # BGNSTR
        chunks.append(_rec(0x06, 6, _ascii(sname)))  # STRNAME
        chunks.extend(elements)
        chunks.append(_rec(0x07, 0, b""))          # ENDSTR
    chunks.append(_rec(0x04, 0, b""))              # ENDLIB
    return b"".join(chunks)


# ---------------------------------------------------------------------------
# 器件几何 → 版图元素（IR Component / 器件库参数 → GDS）
# ---------------------------------------------------------------------------
def ring_polygon(R_um: float, n_sides: int = 64) -> List[Tuple[float, float]]:
    """圆多边形近似（顺时针，n_sides 段）。"""
    return [(R_um * math.cos(2.0 * math.pi * i / n_sides),
             R_um * math.sin(2.0 * math.pi * i / n_sides))
            for i in range(n_sides)]


def ring_centerline(R_um: float, n_pts: int = 64) -> List[Tuple[float, float]]:
    """环中心线离散点（D-79 真实波导环 PATH；首≠尾避免 GDS PATH 闭合歧义）。"""
    return [(R_um * math.cos(2.0 * math.pi * i / n_pts),
             R_um * math.sin(2.0 * math.pi * i / n_pts))
            for i in range(n_pts)]


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
        # D-79：实心环带 → 真实波导环（中心线 PATH + width，foundry 弯曲波导
        # 标准表达；实心 BOUNDARY 环带不可变宽度、DRC 无法检查环宽）。
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": wg_w,
                      "points_um": ring_centerline(R)})
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
        # D-79：实心环带 → 真实波导环（中心线 PATH + width）
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": wg_w,
                      "points_um": ring_centerline(R)})
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
        # D-79：双波导 PATH（真实波导表达；输入输出 taper 由流水线可选叠加）
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": core_w,
                      "points_um": [(0.0, off), (Lc, off)]})
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": core_w,
                      "points_um": [(0.0, -off), (Lc, -off)]})
    elif kind == "SymmetricYBranch":
        angle = math.radians(float(params.get("split_angle", 10.0)))
        arm = float(params.get("arm_length", 5.0))
        half = angle / 2.0
        # D-79：输入绝热 taper（D-71 基元）→ 分叉点 → 双 arm PATH
        from lda_l2.primitives import taper_polygon as _tp
        tap_len = min(arm * 0.25, 2.0)
        tap_w2 = core_w * 1.6                       # taper 末端渐宽容纳分叉
        descs.append({"kind": "boundary", "layer": LIB_LAYER_SI,
                      "rings_um": [_tp(core_w, tap_w2, tap_len,
                                       profile="adiabatic")]})
        x0 = tap_len
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": core_w,
                      "points_um": [(x0, 0.0),
                                    (x0 + arm * math.cos(half),
                                     arm * math.sin(half))]})
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": core_w,
                      "points_um": [(x0, 0.0),
                                    (x0 + arm * math.cos(half),
                                     -arm * math.sin(half))]})
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
        elif rectype in (0x08, 0x09, 0x0A, 0x0B):  # BOUNDARY/PATH/SREF/AREF
            if cur is not None:
                cur["elements"] += 1
        elif rectype == 0x0D:                     # LAYER
            if cur is not None and len(payload) >= 2:
                (layer,) = struct.unpack_from(">h", payload, 0)
                cur["layers"].add(layer)
        i += ln
    return {"libname": libname, "structures": structures,
            "n_structures": len(structures)}


def parse_gds_polygons(data: bytes,
                       expand_refs: bool = True) -> Dict:
    """解析 GDSII 字节 → 每结构多边形几何（主权最小解析器扩展 · v0.8.30）。

    与 parse_gds（只取摘要）互补：本函数还原每个元素的多边形顶点（µm）与层，
    供「几何 DRC 快查」（最小线宽/间距/面积）与 gdsfactory 兼容桥使用。

    记录类型：BOUNDARY(0x08) / PATH(0x09) 元素 + LAYER(0x0D) + WIDTH(0x0F,
    PATH 宽) + XY(0x10, INT4 顶点) + ENDEL(0x11) 闭合。坐标 DBU→µm（×1e-3）。
    仅覆盖本编码器写出的标准子集；遇未知记录安全跳过。

    v0.9.33 P0-1 层次化支持：
      - 识别 SREF(0x0A) / AREF(0x0B) + SNAME(0x12) + STRANS(0x1A) +
        COLROW(0x13)，解析为 kind='sref'/'aref' 的元素（带 `sname`/
        `colrow`/`points_um`）。
      - **`expand_refs=True`（默认）把引用还原成实际几何**：AREF 展开为
        nx×ny 份被引单元的多边形（按 P1/P2/P3 推单点间距），SREF 按原点平移；
        支持嵌套引用（带环检测，遇环返回空而不死循环）。
      - 🔴 **为何默认展开**：不展开的话层次化 GDS 在 `gds_drc` /
        `parasitic_rc` 眼里只有 1 条 AREF 记录 ⇒ 几何检查几乎全空 ⇒
        **DRC 假绿**。宁可解析慢，不可假绿。
      - 对**不含任何引用**的 GDS（当前全部既有版图即如此），展开逻辑空转，
        输出与旧版 **bit-exact 一致**（零回归）。
    """
    i, n = 0, len(data)
    libname = ""
    structures: Dict[str, List[Dict]] = {}
    cur: List[Dict] | None = None
    cur_layer = 0
    cur_kind = None          # 0x08 / 0x09 / 0x0A / 0x0B
    cur_width = None
    cur_pts: List[Tuple[int, int]] = []
    cur_sname = ""
    cur_colrow: Optional[Tuple[int, int]] = None
    out = {"libname": libname, "structures": structures}

    def _flush() -> None:
        nonlocal cur_kind, cur_layer, cur_width, cur_pts, cur_sname, cur_colrow
        if cur is not None and cur_kind is not None:
            if cur_kind in (0x08, 0x09) and cur_pts:
                cur.append({
                    "layer": cur_layer,
                    "kind": "boundary" if cur_kind == 0x08 else "path",
                    "width": cur_width,
                    "points_um": [(x * DBU, y * DBU) for x, y in cur_pts],
                })
            elif cur_kind in (0x0A, 0x0B) and cur_sname:
                el = {
                    "layer": cur_layer,
                    "kind": "sref" if cur_kind == 0x0A else "aref",
                    "width": None,
                    "sname": cur_sname,
                    "points_um": [(x * DBU, y * DBU) for x, y in cur_pts],
                }
                if cur_kind == 0x0B:
                    el["colrow"] = cur_colrow or (1, 1)
                cur.append(el)
        cur_kind = None
        cur_layer = 0
        cur_width = None
        cur_pts = []
        cur_sname = ""
        cur_colrow = None


    while i < n:
        if i + 4 > n:
            break
        (ln,) = struct.unpack_from(">H", data, i)
        if ln < 4:
            break
        rectype = data[i + 2]
        datatype = data[i + 3]
        payload = data[i + 4:i + ln]
        if rectype == 0x02:                       # LIBNAME
            libname = payload.decode("ascii", "ignore").rstrip("\x00")
        elif rectype == 0x06:                     # STRNAME（新结构开始，flush 旧）
            _flush()
            sname = payload.decode("ascii", "ignore").rstrip("\x00")
            cur = []
            structures[sname] = cur
        elif rectype in (0x08, 0x09, 0x0A, 0x0B):   # BOUNDARY/PATH/SREF/AREF
            _flush()
            cur_kind = rectype
            cur_layer = 0
            cur_width = None
            cur_pts = []
        elif rectype == 0x12:                     # SNAME（引用的单元名）
            cur_sname = payload.decode("ascii", "ignore").rstrip("\x00")
        elif rectype == 0x13:                     # COLROW（AREF 阵列行列数）
            if len(payload) >= 4:
                cx, cy = struct.unpack_from(">hh", payload, 0)
                cur_colrow = (int(cx), int(cy))
        elif rectype == 0x0D:                     # LAYER
            if len(payload) >= 2:
                (cur_layer,) = struct.unpack_from(">h", payload, 0)
        elif rectype == 0x0F:                     # WIDTH（PATH 宽）
            if len(payload) >= 4:
                (w,) = struct.unpack_from(">i", payload, 0)
                cur_width = w * DBU
        elif rectype == 0x10:                     # XY
            if len(payload) >= 8 and len(payload) % 8 == 0:
                vals = struct.unpack_from(">%di" % (len(payload) // 4), payload, 0)
                cur_pts = [(vals[j], vals[j + 1]) for j in range(0, len(vals), 2)]
        elif rectype == 0x11:                     # ENDEL（元素闭合）
            _flush()
        i += ln
    _flush()
    out["libname"] = libname

    # 顶层结构 = 未被任何其他结构引用的结构（展开**前**判定）。
    # 🔴 下游必须按 `top_structures` 取几何：展开后 cell 自身的结构仍保留
    #    自己的几何，若把所有结构求和会把 cell 那份**重复计入**
    #    （实测 CPO 小阵列：CHANNEL 202 + TOP 展开 1616 = 1818，而真实
    #    几何是 1616 —— 凭空多出 202）。flat 版图只有一个结构，不受影响。
    referenced = {el.get("sname")
                  for v in structures.values() for el in v
                  if el.get("kind") in ("sref", "aref")}
    top_structures = [n for n in structures if n not in referenced]

    if expand_refs:
        _expand_references(structures)
    out["expanded"] = bool(expand_refs)
    out["top_structures"] = top_structures
    return out


def _shift_element(el: Dict, dx: float, dy: float) -> Dict:
    """元素平移（引用展开用；只平移顶点，不改层/宽/类型）。"""
    out = dict(el)
    out["points_um"] = [(x + dx, y + dy) for x, y in el["points_um"]]
    return out


def _expand_references(structures: Dict[str, List[Dict]]) -> None:
    """就地展开全部结构的 SREF / AREF 引用（v0.9.33 P0-1）。

    AREF 的单点间距由三点推出：P1=原点、P2=(x1+dx·nx, y1)、P3=(x1, y1+dy·ny)
    ⇒ dx=(P2.x−P1.x)/nx、dy=(P3.y−P1.y)/ny（dx/dy 是**间距**非总跨度）。

    支持嵌套引用（cell 引用 cell）；带环检测（遇环该分支返回空，不死循环）。
    不含引用的结构原样保留 —— 保证 flat 版图输出 bit-exact 不变。
    """
    memo: Dict[str, List[Dict]] = {}

    def _resolve(name: str, stack: frozenset) -> List[Dict]:
        if name in memo:
            return memo[name]
        if name in stack:                      # 环：截断，不递归
            return []
        out: List[Dict] = []
        for el in structures.get(name, []):
            k = el.get("kind")
            if k == "sref":
                pts = el.get("points_um") or [(0.0, 0.0)]
                ox, oy = pts[0]
                out.extend(_shift_element(se, ox, oy)
                           for se in _resolve(el["sname"], stack | {name}))
            elif k == "aref":
                pts = el.get("points_um") or []
                if len(pts) < 3:
                    continue
                nx, ny = el.get("colrow", (1, 1))
                nx, ny = max(1, int(nx)), max(1, int(ny))
                p1, p2, p3 = pts[0], pts[1], pts[2]
                dx = (p2[0] - p1[0]) / nx
                dy = (p3[1] - p1[1]) / ny
                sub = _resolve(el["sname"], stack | {name})
                for b in range(ny):
                    for a in range(nx):
                        sx, sy = p1[0] + a * dx, p1[1] + b * dy
                        out.extend(_shift_element(se, sx, sy) for se in sub)
            else:
                out.append(el)
        if name not in stack:                  # 只缓存完整解（避免环污染）
            memo[name] = out
        return out

    for sname in list(structures.keys()):
        structures[sname] = _resolve(sname, frozenset())


def write_gds(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)
