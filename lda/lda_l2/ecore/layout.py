"""LDA ecore · 电子计算芯片版图与几何签核（E6 · D-156）。

**为什么需要它（E6 逼出的平台接缝）**：
E1–E5 把电子计算核做到了**电路级**（MOSFET + MNA + 交叉阵列 + 数据通路），
但 `lda_l2/ecore/` 里**一条版图链都没有** —— 平台的 GDS/DRC/LVS 全在**光子侧**
（`gds_export` / `chip_layout_export` / `drc` / `lvs` / `lvs_geom`），超导侧有
`lda_qeda/sc_layout.py`（几何→带 net 网表→LVS 签核）。电子侧**零**。
⇒ 严格讲：电子征程此前「设计出了电路，但签不出芯片」。本模块补齐这条链，
使电子计算芯片**第一次能出真 GDS**，走完「几何 → DRC → LVS → 签核」闭环。

**模型（1T 交叉点单元阵列）**：
  每个交叉点 = 一个 NMOS「1T」单元（有源区 DIFF_D/DIFF_S + 多晶硅栅 POLY +
  接触孔 CONT + M1 源极焊垫 + VIA1）。
  - **行线** M1 水平（`row{i}`）：经 CONT_D 接漏极（DIFF_D）；
  - **列线** M2 竖直（`col{j}`）：经 VIA1 ← M1 焊垫 ← CONT_S 接源极（DIFF_S）；
  - **权重栅** `wg_{i}_{j}`：POLY 栅本身（对外端口；栅驱动/编程路径属 E7+，本段不含）。

**单一真源**：层栈与规则 = `ecore/elayers.py`；几何编码/GDSII = `lda_l2/gds_export`。

**三类闭环判据（闭式 golden）**：
  1. **版图足迹** bbox = 节距闭式（`(m-1)·pitch_x + 2·half_x` 等）；
  2. **AREF 层次化** 展开后元素数 **≡ flat 元素数**（层次化不改变几何，沿用平台 P0-1 纪律）；
  3. **W/L 几何回提** ≡ 声明值（栅长 = 与有源区 y 重叠的 POLY 元素 x 跨度；宽 = 有源区 y 跨度）。

**几何 LVS（不重放设计意图）**：对**实际产出几何**做「同层 bbox 重叠 = 连通」并查集 +
「CONT/VIA1 是唯一合法跨层桥」跨层并查，得到连通分量；校验
① 每分量单一 net（否则 SHORT）② 每元素有 net ③ 桥须跨下层→上层（否则悬空桥）
④ 声明 net 全部实现 ⑤ 晶体管数 = n·m ⑥ W/L 一致 ⑦ 零悬空。

🔴 **诚实边界**：
  - 层号/层序/规则为**公开工艺近似的设计规则**（可覆盖 · **非实测 golden**）；
    Foundry PDK 层规属 D5 外部依赖，平台不沾。
  - 沟道区被 POLY 栅**断开**（DIFF_D / DIFF_S 分离）—— 这是教学级简化：
    真实 LVS 需**晶体管识别**把连续有源区按栅切成源/漏，本模块不做该识别。
  - 全部判据为 **bbox 级**几何近似（非多边形布尔运算）；bbox 相交**偏保守**
    （宁可多报，不放过）。
  - 纯标准库（零 numpy 也可）；**LLM 不进判决路径**；zero 商业 EDA 依赖。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from lda_l2 import gds_export as G
from lda_l2.ecore import elayers as EL

# 层名（gds_layer → 层名），单一真源 = elayers._LAYER_KIND
_NAME_OF_LAYER: Dict[int, str] = {v: k for k, v in {
    "DIFF": EL.L_DIFF, "POLY": EL.L_POLY, "CONT": EL.L_CONT,
    "M1": EL.L_M1, "VIA1": EL.L_VIA1, "M2": EL.L_M2, "PAD": EL.L_PAD,
}.items()}

EDRC_RULES = (
    "EDR-MIN-WIDTH",         # 每层最小线宽
    "EDR-MIN-SPACE",         # 同层最小间距
    "EDR-CONT-ENCLOSURE",    # 接触孔须被上下层各包围 ≥ enclosure
    "EDR-MIN-AREA",          # 每层最小面积
)

# 默认单元参数（µm）——公开工艺近似占位，非 PDK 标定
DEFAULT_CELL_PARAMS: Dict[str, float] = {
    "w_um": 1.20,        # 沟道宽 W（有源区 y 跨度）
    "l_um": 0.30,        # 栅长 L（POLY 在 x 的跨度）
    "sd_um": 0.45,       # 源/漏外延（有源区每侧伸出栅的长度）
    "cont_um": 0.20,     # 接触孔边长
    "poly_oh_um": 0.25,  # POLY 对 DIFF 的 y 外延（防边缘漏电）
    "dy_um": 0.35,       # 漏/源接触孔 y 偏置（漏 +dy，源 -dy）
    "pad_um": 0.40,      # M1 源极焊垫边长
    "via_um": 0.20,      # VIA1 边长
    "row_w_um": 0.40,    # M1 行线宽
    "col_w_um": 0.40,    # M2 列线宽
    "pitch_x_um": 2.40,  # 列节距
    "pitch_y_um": 2.40,  # 行节距
}

LAYOUT_DISCLOSURE = {
    "role": "E6 = 电子计算芯片版图与几何签核（DRC/LVS/GDS）· 让电子芯片能出真 GDS",
    "cell": "1T 交叉点单元（DIFF_D/DIFF_S + POLY 栅 + CONT×2 + M1 焊垫 + VIA1）",
    "channel": "沟道区被 POLY 断开（DIFF_D/DIFF_S 分离）—— 教学级简化；"
               "真实 LVS 需晶体管识别，本模块不做（见模块 docstring 诚实边界）",
    "rules": "ELEC_DESIGN_RULES 为公开工艺近似的**设计规则 · 可覆盖 · 非实测 golden**"
             "（Foundry PDK 属 D5 外部依赖）",
    "geom": "全部判据为 **bbox 级**几何近似（非多边形布尔），bbox 相交偏保守",
    "red_line": "纯标准库（零 numpy 也可）· LLM 不进判决路径 · 零商业 EDA 依赖",
}

# ---------------------------------------------------------------------------
# 几何工具
# ---------------------------------------------------------------------------
_Bbox = Tuple[float, float, float, float]


def _bbox(d: Dict) -> _Bbox:
    """元素 bbox (xmin,xmax,ymin,ymax)。

    🔴 path 的线宽只沿**法向**外扩：轴对齐折线仅扩一个方向（水平线只扩 y、
    竖直线只扩 x），否则 bbox 会凭空胖一圈（实测：4×4 阵列足迹被多算 0.4 µm）。
    非轴对齐折线保守地两向都扩。
    """
    if d["kind"] == "path":
        w = float(d.get("width_um", 0.0)) / 2.0
        xs = [p[0] for p in d["points_um"]]
        ys = [p[1] for p in d["points_um"]]
        if len(set(ys)) == 1:                       # 水平线：只扩 y
            return (min(xs), max(xs), min(ys) - w, max(ys) + w)
        if len(set(xs)) == 1:                       # 竖直线：只扩 x
            return (min(xs) - w, max(xs) + w, min(ys), max(ys))
        return (min(xs) - w, max(xs) + w, min(ys) - w, max(ys) + w)
    pts = [p for r in d["rings_um"] for p in r]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), max(xs), min(ys), max(ys))


def _overlap(a: _Bbox, b: _Bbox, tol: float = 1e-9) -> bool:
    return not (a[1] < b[0] - tol or a[0] > b[1] + tol
                or a[3] < b[2] - tol or a[2] > b[3] + tol)


def _gap(a: _Bbox, b: _Bbox) -> float:
    """两 bbox 的最短边距（Manhattan/Chebyshev 风格：x/y 分离量的较大者）。"""
    dx = max(a[0] - b[1], b[0] - a[1], 0.0)
    dy = max(a[2] - b[3], b[2] - a[3], 0.0)
    return math.hypot(dx, dy) if (dx > 0.0 and dy > 0.0) else max(dx, dy)


def _enclosure(inner: _Bbox, outer: _Bbox) -> float:
    """inner 被 outer 包围的最小边距（未包围则为负）。"""
    return min(inner[0] - outer[0], outer[1] - inner[1],
               inner[2] - outer[2], outer[3] - inner[3])


def _ring_square(cx: float, cy: float, side: float) -> List[List[Tuple[float, float]]]:
    h = side / 2.0
    return [[(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]]


def _b_square(layer: int, cx: float, cy: float, side: float, net: str) -> Dict:
    return {"kind": "boundary", "layer": layer, "net": net,
            "rings_um": _ring_square(cx, cy, side)}


def _b_rect(layer: int, x0: float, x1: float, y0: float, y1: float, net: str) -> Dict:
    return {"kind": "boundary", "layer": layer, "net": net,
            "rings_um": [[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]}


# ---------------------------------------------------------------------------
# 单元几何（本地坐标，原点 = 单元中心）
# ---------------------------------------------------------------------------
def crosspoint_cell(net_drain: str, net_source: str, net_gate: str,
                    params: Optional[Dict[str, float]] = None) -> List[Dict]:
    """单个 1T 交叉点单元几何（**本地**坐标，原点 = 单元中心）。

    返回 7 个元素：
      DIFF_D（漏，net_drain）· DIFF_S（源，net_source）· POLY 栅（net_gate）
      · CONT_D · CONT_S · M1 源极焊垫 · VIA1
    """
    p = dict(DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    w, l, sd = p["w_um"], p["l_um"], p["sd_um"]
    cont, oh, dy = p["cont_um"], p["poly_oh_um"], p["dy_um"]
    pad, via = p["pad_um"], p["via_um"]
    hg = l / 2.0
    cx_s = -(hg + sd / 2.0)        # 源接触孔 x
    cx_d = +(hg + sd / 2.0)        # 漏接触孔 x

    return [
        # 有源区（源/漏分离；沟道由 POLY 断开）
        _b_rect(EL.L_DIFF, cx_d - sd / 2.0, hg + sd, -w / 2.0, w / 2.0, net_drain),
        _b_rect(EL.L_DIFF, -(hg + sd), cx_s + sd / 2.0, -w / 2.0, w / 2.0, net_source),
        # 多晶硅栅（在 y 向对 DIFF 外延 = poly_oh）
        _b_rect(EL.L_POLY, -hg, hg, -(w / 2.0 + oh), (w / 2.0 + oh), net_gate),
        # 接触孔
        _b_square(EL.L_CONT, cx_d, +dy, cont, net_drain),
        _b_square(EL.L_CONT, cx_s, -dy, cont, net_source),
        # M1 源极焊垫（承载 CONT_S → VIA1 转接）
        _b_square(EL.L_M1, cx_s, -dy, pad, net_source),
        # VIA1（M1 → M2 跨层桥）
        _b_square(EL.L_VIA1, cx_s, -dy, via, net_source),
    ]


# ---------------------------------------------------------------------------
# 阵列 P&R（节距闭式 + 行线/列线）
# ---------------------------------------------------------------------------
def array_lines(n: int, m: int,
                params: Optional[Dict[str, float]] = None) -> List[Dict]:
    """阵列布线（绝对坐标）：行线 M1 水平 + 列线 M2 竖直 —— **布线几何的唯一定义处**。

    E6 `crossbar_array` 与 E9 `array_scale`（千级阵列，O(N) 不物化 N² 单元）**共用**本函数，
    杜绝第二份副本（平台 P0-0/P0-1 血案的通则）。
    """
    p = dict(DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    px, py = p["pitch_x_um"], p["pitch_y_um"]
    out: List[Dict] = []
    # 行线（M1 水平）——经每行全部单元的漏极接触孔
    x_lo = 0.0 - (p["l_um"] / 2.0 + p["sd_um"])
    x_hi = (m - 1) * px + (p["l_um"] / 2.0 + p["sd_um"])
    for i in range(n):
        y = i * py + p["dy_um"]
        out.append({"kind": "path", "layer": EL.L_M1, "net": f"row{i}",
                    "width_um": p["row_w_um"], "points_um": [(x_lo, y), (x_hi, y)]})
    # 列线（M2 竖直）——经每列全部单元的 VIA1
    cx_s = -(p["l_um"] / 2.0 + p["sd_um"] / 2.0)
    y_lo = 0.0 - (p["w_um"] / 2.0 + p["poly_oh_um"])
    y_hi = (n - 1) * py + (p["w_um"] / 2.0 + p["poly_oh_um"])
    for j in range(m):
        x = j * px + cx_s
        out.append({"kind": "path", "layer": EL.L_M2, "net": f"col{j}",
                    "width_um": p["col_w_um"], "points_um": [(x, y_lo), (x, y_hi)]})
    return out


def array_footprint(n: int, m: int,
                    params: Optional[Dict[str, float]] = None
                    ) -> Tuple[float, float]:
    """阵列版图足迹 (W, H) µm —— **闭式**（节距 + 单元半宽）。"""
    p = dict(DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    half_x = max(p["l_um"] / 2.0 + p["sd_um"],
                 (p["l_um"] / 2.0 + p["sd_um"] / 2.0) + p["col_w_um"] / 2.0)
    half_y = max(p["w_um"] / 2.0 + p["poly_oh_um"],
                 p["dy_um"] + p["row_w_um"] / 2.0,
                 p["dy_um"] + p["pad_um"] / 2.0)
    return ((m - 1) * p["pitch_x_um"] + 2.0 * half_x,
            (n - 1) * p["pitch_y_um"] + 2.0 * half_y)


def crossbar_array(n: int, m: int,
                   params: Optional[Dict[str, float]] = None) -> Dict:
    """n×m 1T 交叉阵列版图（绝对坐标）：单元阵列 + 行线(M1) + 列线(M2)。"""
    if n <= 0 or m <= 0:
        raise ValueError("n/m 必须为正")
    p = dict(DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    px, py = p["pitch_x_um"], p["pitch_y_um"]

    cells: List[Dict] = []          # 含 (i, j, 本地 descs)
    flat: List[Dict] = []
    for i in range(n):
        for j in range(m):
            ox, oy = j * px, i * py
            nd, ns, ng = f"row{i}", f"col{j}", f"wg_{i}_{j}"
            local = crosspoint_cell(nd, ns, ng, p)
            cells.append({"i": i, "j": j, "x0": ox, "y0": oy, "descs": local})
            for d in local:
                e = dict(d)
                if d["kind"] == "path":
                    e["points_um"] = [(x + ox, y + oy) for x, y in d["points_um"]]
                else:
                    e["rings_um"] = [[(x + ox, y + oy) for x, y in r]
                                     for r in d["rings_um"]]
                flat.append(e)

    # 行线 / 列线（唯一定义处 = array_lines，与 E9 千级阵列共用）
    flat.extend(array_lines(n, m, p))

    nets = sorted({d["net"] for d in flat})
    return {
        "n": n, "m": m, "params": p,
        "descs": flat,
        "cells": [{"i": c["i"], "j": c["j"], "x0": c["x0"], "y0": c["y0"]}
                  for c in cells],
        "cell_descs": crosspoint_cell("row0", "col0", "wg_0_0", p),
        "n_elements": len(flat),
        "nets": nets,
        "footprint_um": array_footprint(n, m, p),
        "n_cells": n * m,
    }


def expected_netlist(n: int, m: int,
                     params: Optional[Dict[str, float]] = None) -> Dict:
    """阵列的**期望网表**（供 LVS 校验）：端口集 / 单元数 / W·L 声明值。"""
    p = dict(DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    ports = {f"row{i}" for i in range(n)} | {f"col{j}" for j in range(m)}
    ports |= {f"wg_{i}_{j}" for i in range(n) for j in range(m)}
    return {"n_cells": n * m, "ports": ports,
            "W_um": float(p["w_um"]), "L_um": float(p["l_um"])}


# ---------------------------------------------------------------------------
# 几何回提：W / L
# ---------------------------------------------------------------------------
def extract_wl(descs: Sequence[Dict]) -> Dict[str, float]:
    """从**版图几何**回提晶体管尺寸（**逐单元**，取全体单元的一致值）。

    W = 单个有源区元素的 y 跨度；L = 与有源区在 y 上重叠的单个 POLY 栅元素的 x 跨度。
    全阵列取 min/max 并回报**一致性**（所有单元应完全相同 —— 阵列版图的整齐性判据）。

    方法学独立于正向几何生成（不同代码路径），但共享「DIFF 是沟道 / POLY 是栅」
    这一几何约定 ⇒ 属**代码路径级独立**，非物理方法级独立（同 `lvs_geom` 的诚实口径）。
    """
    diff = [d for d in descs if d["layer"] == EL.L_DIFF]
    poly = [d for d in descs if d["layer"] == EL.L_POLY]
    out = {"W_um": 0.0, "L_um": 0.0, "W_min_um": 0.0, "W_max_um": 0.0,
           "L_min_um": 0.0, "L_max_um": 0.0, "uniform": False,
           "n_diff": len(diff), "n_poly": len(poly), "n_gates": 0}
    if not diff or not poly:
        return out
    db = [_bbox(d) for d in diff]
    Ws = [b[3] - b[2] for b in db]
    dy0, dy1 = min(b[2] for b in db), max(b[3] for b in db)
    # 与有源区在 y 上重叠的 POLY 元素 = 栅条（不含远离沟道的延伸）
    gates = [d for d in poly if _bbox(d)[2] < dy1 - 1e-9 and _bbox(d)[3] > dy0 + 1e-9]
    gb = [_bbox(d) for d in gates]
    Ls = [b[1] - b[0] for b in gb]
    out.update({
        "W_um": min(Ws), "W_min_um": min(Ws), "W_max_um": max(Ws),
        "L_um": min(Ls) if Ls else 0.0,
        "L_min_um": min(Ls) if Ls else 0.0, "L_max_um": max(Ls) if Ls else 0.0,
        "uniform": (max(Ws) - min(Ws) < 1e-9
                    and (not Ls or max(Ls) - min(Ls) < 1e-9)),
        "n_gates": len(gates),
    })
    return out


# ---------------------------------------------------------------------------
# 几何 DRC
# ---------------------------------------------------------------------------
def run_edrc(descs: Sequence[Dict],
             limits: Optional[Dict[str, float]] = None) -> Dict:
    """电子几何 DRC：最小线宽 / 同层间距 / 接触孔包围 / 最小面积。

    返回 {verdict, violations, n_rules, limits, checked}。verdict ∈ {ACCEPT, REJECT}；
    violation = {rule, detail}（死标量，零模型调用）。
    """
    lim = dict(EL.ELEC_DESIGN_RULES)
    if limits:
        lim.update(limits)

    def min_w_of(layer: int) -> Optional[float]:
        return {EL.L_DIFF: lim["diff_min_width_um"],
                EL.L_POLY: lim["poly_min_width_um"],
                EL.L_CONT: lim["cont_size_um"],
                EL.L_M1: lim["m1_min_width_um"],
                EL.L_VIA1: lim["via1_size_um"],
                EL.L_M2: lim["m2_min_width_um"]}.get(layer)

    def min_s_of(layer: int) -> Optional[float]:
        return {EL.L_DIFF: lim["diff_min_space_um"],
                EL.L_POLY: lim["poly_min_space_um"],
                EL.L_CONT: lim["cont_min_space_um"],
                EL.L_M1: lim["m1_min_space_um"],
                EL.L_VIA1: lim["via1_size_um"],
                EL.L_M2: lim["m2_min_space_um"]}.get(layer)

    violations: List[Dict] = []
    checked = 0
    boxes = [(_bbox(d), d) for d in descs]

    # ① 最小线宽 + ④ 最小面积
    for bb, d in boxes:
        lname = _NAME_OF_LAYER.get(d["layer"], str(d["layer"]))
        wmin = min_w_of(d["layer"])
        if wmin is not None and d["kind"] == "boundary":
            thin = min(bb[1] - bb[0], bb[3] - bb[2])
            checked += 1
            if thin < wmin - 1e-9:
                violations.append({"rule": "EDR-MIN-WIDTH",
                                   "detail": f"{lname} 最薄边 {thin:.3f} < {wmin:.3f} µm"})
        if d["kind"] == "path":
            w = float(d.get("width_um", 0.0))
            if wmin is not None:
                checked += 1
                if w < wmin - 1e-9:
                    violations.append({"rule": "EDR-MIN-WIDTH",
                                       "detail": f"{lname} 线宽 {w:.3f} < {wmin:.3f} µm"})
        if d["layer"] == EL.L_DIFF:
            area = (bb[1] - bb[0]) * (bb[3] - bb[2])
            checked += 1
            if area < lim["diff_min_area_um2"] - 1e-9:
                violations.append({"rule": "EDR-MIN-AREA",
                                   "detail": f"DIFF 面积 {area:.3f} < "
                                             f"{lim['diff_min_area_um2']:.3f} µm²"})

    # ② 同层最小间距（只查同层、且**非同一 net** 的元素对）
    by_layer: Dict[int, List[Tuple[_Bbox, Dict]]] = {}
    for bb, d in boxes:
        by_layer.setdefault(d["layer"], []).append((bb, d))
    for layer, items in by_layer.items():
        sp = min_s_of(layer)
        if sp is None:
            continue
        for a in range(len(items)):
            for b in range(a + 1, len(items)):
                if items[a][1]["net"] == items[b][1]["net"]:
                    continue
                checked += 1
                g = _gap(items[a][0], items[b][0])
                if g < sp - 1e-9:
                    lname = _NAME_OF_LAYER.get(layer, str(layer))
                    violations.append({"rule": "EDR-MIN-SPACE",
                                       "detail": f"{lname} 间距 {g:.3f} < {sp:.3f} µm"
                                                 f"（{items[a][1]['net']} / {items[b][1]['net']}）"})

    # ③ 接触孔包围（CONT 须被其 via_map 允许的层各包围 ≥ enclosure）
    st = EL.get_estack()
    for bb, d in boxes:
        if _NAME_OF_LAYER.get(d["layer"]) not in st.bridge_layers():
            continue
        bridge = _NAME_OF_LAYER[d["layer"]]
        allowed = {n for pair in st.via_map.get(bridge, []) for n in pair}
        for ob, od in boxes:
            if od is d or not _overlap(bb, ob):
                continue
            oname = _NAME_OF_LAYER.get(od["layer"])
            if oname not in allowed:
                continue
            checked += 1
            enc = _enclosure(bb, ob)
            need = (lim["cont_enclosure_um"] if bridge == "CONT"
                    else lim["via1_enclosure_um"])
            if enc < need - 1e-9:
                violations.append({"rule": "EDR-CONT-ENCLOSURE",
                                   "detail": f"{bridge} 被 {oname} 包围 {enc:.3f} < "
                                             f"{need:.3f} µm"})

    verdict = "ACCEPT" if not violations else "REJECT"
    return {"verdict": verdict, "violations": violations,
            "n_rules": len(EDRC_RULES), "limits": lim, "checked": checked}


# ---------------------------------------------------------------------------
# 几何 LVS（连通分量 + 跨层桥 + 尺寸回提）
# ---------------------------------------------------------------------------
def elvs_signoff(descs: Sequence[Dict], expected: Dict) -> Dict:
    """几何 LVS：对**实际产出几何**做连通性提取与声明网表比对。

    判据（逐条 → issues）：
      ① 每元素有 net 标签 ② 同层 signal 层相交 ⇒ 短路 ③ 跨层桥**必须跨下层→上层**
      （CONT/VIA1 须同时接触其 via_map 允许层中的**下方**与**上方**层，否则悬空桥）
      ④ 声明端口全部实现 ⑤ 晶体管数 = 期望单元数 ⑥ W/L 几何回提 ≡ 声明 ⑦ 零悬空
    """
    issues: List[str] = []
    n_checks = 0
    st = EL.get_estack()
    els = list(descs)
    n = len(els)

    # ① 每元素有 net
    n_checks += 1
    if any(not e.get("net") for e in els):
        issues.append("ELVS-NO-NET: 存在无 net 标签的几何元素")

    boxes = [_bbox(e) for e in els]
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # ② 同层 signal 层相交 ⇒ 连通（同层 short）；异层不连通
    n_checks += 1
    for a in range(n):
        for b in range(a + 1, n):
            la = _NAME_OF_LAYER.get(els[a]["layer"])
            lb = _NAME_OF_LAYER.get(els[b]["layer"])
            if la != lb:
                continue
            if st.can_short(la, lb) and _overlap(boxes[a], boxes[b]):
                union(a, b)

    # ③ 跨层桥：CONT/VIA1 是唯一合法桥；必须同时接触「允许层的下方 + 上方」各≥1 层
    n_checks += 1
    for k in range(n):
        lk = _NAME_OF_LAYER.get(els[k]["layer"])
        if lk not in st.bridge_layers():
            continue
        allowed = {nm for pair in st.via_map.get(lk, []) for nm in pair}
        pos_b = st.pos_of(lk)
        touched: set = set()
        for t in range(n):
            if t == k or not _overlap(boxes[k], boxes[t]):
                continue
            lt = _NAME_OF_LAYER.get(els[t]["layer"])
            if lt in allowed:
                touched.add(lt)
                union(k, t)
        lower = {nm for nm in touched if st.pos_of(nm) < pos_b}
        upper = {nm for nm in touched if st.pos_of(nm) > pos_b}
        if not lower or not upper:
            issues.append(f"ELVS-DANGLING-BRIDGE: {lk}@{els[k].get('net')} 只接触"
                          f"{sorted(touched) or '空'}（须跨下层+上层各≥1，"
                          f"允许层 {sorted(allowed)}）")

    comps: Dict[int, List[int]] = {}
    for k in range(n):
        comps.setdefault(find(k), []).append(k)

    # ②b 每分量单一 net（否则短路）
    for root, members in comps.items():
        nets = {els[k].get("net") for k in members}
        if len(nets) > 1:
            issues.append(f"ELVS-SHORT: 同一连通分量合并了多个 net {sorted(nets)}")

    # ④ 声明端口全部实现 ⑦ 零悬空
    realized = {e.get("net") for e in els}
    ports = set(expected.get("ports", set()))
    n_checks += 1
    missing = ports - realized
    if missing:
        issues.append(f"ELVS-MISSING-NET: 声明端口未实现 {sorted(missing)[:6]}"
                      f"（共 {len(missing)}）")
    n_checks += 1
    floating = realized - ports
    if floating:
        issues.append(f"ELVS-FLOATING: 出现声明之外的 net {sorted(floating)[:6]}"
                      f"（共 {len(floating)}）")

    # ⑤ 晶体管数 = 期望单元数
    wl = extract_wl(els)
    n_checks += 1
    n_cells = int(expected.get("n_cells", 0))
    if wl.get("n_gates", 0) != n_cells:
        issues.append(f"ELVS-TRANSISTOR-COUNT: 栅区 {wl.get('n_gates', 0)}"
                      f" ≠ 期望单元 {n_cells}")

    # ⑥ W/L 几何回提 ≡ 声明
    n_checks += 1
    eW = float(expected.get("W_um", 0.0))
    eL = float(expected.get("L_um", 0.0))
    if abs(wl["W_um"] - eW) > 1e-6 or abs(wl["L_um"] - eL) > 1e-6:
        issues.append(f"ELVS-DEVICE-MISMATCH: 回提 W/L="
                      f"{wl['W_um']:.4f}/{wl['L_um']:.4f} ≠ 声明 {eW:.4f}/{eL:.4f}")

    verdict = "ACCEPT" if not issues else "REJECT"
    return {"verdict": verdict, "issues": issues, "n_checks": n_checks,
            "netlist": {"n_elements": n, "n_components": len(comps),
                        "n_nets_realized": len(realized),
                        "n_ports": len(ports),
                        "n_gates": wl.get("n_gates", 0),
                        "W_um": wl["W_um"], "L_um": wl["L_um"]}}


# ---------------------------------------------------------------------------
# GDS 出口（flat + AREF 层次化）
# ---------------------------------------------------------------------------
def _desc_to_gds(d: Dict) -> bytes:
    if d["kind"] == "path":
        return G.path(d["layer"], d["width_um"], d["points_um"])
    pts = [p for r in d["rings_um"] for p in r]
    return G.boundary(d["layer"], pts)


def to_gds(n: int, m: int, params: Optional[Dict[str, float]] = None,
           path: Optional[str] = None, hierarchical: bool = True) -> Dict:
    """阵列 → GDSII 字节。hierarchical=True 用 **cell + AREF** 压缩单元阵列。

    返回 {gds_bytes, flat_elements, n_expanded, n_elements_top, applied, ...}。
    AREF 只压缩**单元阵列**（行/列线跨单元，留在 top）；展开后元素数必须 **≡ flat**。
    """
    arr = crossbar_array(n, m, params)
    p = arr["params"]
    flat = arr["descs"]
    cell = arr["cell_descs"]
    n_cell_elems = len(cell)
    n_lines = n + m

    applied = False
    if hierarchical:
        px, py = p["pitch_x_um"], p["pitch_y_um"]
        top = [G.aref("XB_CELL", (0.0, 0.0), px, py, m, n, layer=EL.L_DIFF)]
        for d in flat:
            if d["kind"] == "path":
                top.append(_desc_to_gds(d))
        data = G.gds_library(
            "LDA_ECORE",
            {"XB_CELL": [_desc_to_gds(d) for d in cell], "TOP": top},
        )
        applied = True
        n_top = len(top)
    else:
        data = G.gds_library("LDA_ECORE",
                             {"XB": [_desc_to_gds(d) for d in flat]})
        n_top = len(flat)

    if path:
        G.write_gds(path, data)
    return {"gds_bytes": data, "flat_elements": len(flat),
            "n_expanded": len(flat), "n_elements_top": n_top,
            "n_cell_elements": n_cell_elems, "n_lines": n_lines,
            "applied": applied, "n_bytes": len(data)}


def gds_roundtrip_check(n: int, m: int,
                        params: Optional[Dict[str, float]] = None) -> Dict:
    """层次化 GDS 解析回读：展开后元素数 ≡ flat 元素数（平台 P0-1 纪律）。"""
    r = to_gds(n, m, params, hierarchical=True)
    parsed = G.parse_gds_polygons(r["gds_bytes"], expand_refs=True)
    top = parsed.get("top_structures", [])
    n_top = sum(len(parsed["structures"][s]) for s in top)
    return {"expanded_top_elements": n_top, "flat_elements": r["flat_elements"],
            "match": n_top == r["flat_elements"],
            "top_structures": top, "n_structures": len(parsed["structures"])}


# ---------------------------------------------------------------------------
# SVG 预览
# ---------------------------------------------------------------------------
def layout_svg(descs: Sequence[Dict], width: int = 520) -> str:
    """版图 SVG 预览（按层上色）。"""
    color = {EL.L_DIFF: "#16a34a", EL.L_POLY: "#dc2626", EL.L_CONT: "#111827",
             EL.L_M1: "#2563eb", EL.L_VIA1: "#9333ea", EL.L_M2: "#ea580c",
             EL.L_PAD: "#64748b"}
    xs, ys = [], []
    for d in descs:
        pts = d.get("points_um") or [p for r in d.get("rings_um", []) for p in r]
        xs += [p[0] for p in pts]
        ys += [p[1] for p in pts]
    if not xs:
        return "<p>（空版图）</p>"
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    span = max(xmax - xmin, ymax - ymin, 1e-6)
    pad = 20
    S = (width - 2 * pad) / span
    X = lambda x: pad + (x - xmin) * S
    Y = lambda y: pad + (ymax - y) * S
    out = [f'<svg width="{width}" height="{width}" '
           'style="background:#fff;border:1px solid #ddd;border-radius:6px">']
    for d in descs:
        col = color.get(d["layer"], "#888")
        if d["kind"] == "path":
            dd = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in d["points_um"])
            out.append(f'<polyline points="{dd}" fill="none" stroke="{col}" '
                       f'stroke-width="{max(d.get("width_um",0.2)*S,1.5):.1f}"/>')
        else:
            dd = " ".join(f"{X(x):.1f},{Y(y):.1f}" for r in d["rings_um"] for x, y in r)
            out.append(f'<polygon points="{dd}" fill="{col}" fill-opacity="0.75"/>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------
# 自检（常驻断言）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    msgs: List[Tuple[str, bool]] = []

    def chk(name: str, cond) -> bool:
        msgs.append((name, bool(cond)))
        return bool(cond)

    ok = True
    n, m = 4, 4

    # ① 合法阵列：DRC / LVS 双 ACCEPT
    arr = crossbar_array(n, m)
    drc = run_edrc(arr["descs"])
    ok &= chk("① 合法 4×4 阵列 DRC ACCEPT", drc["verdict"] == "ACCEPT")
    lvs = elvs_signoff(arr["descs"], expected_netlist(n, m))
    ok &= chk("② 合法 4×4 阵列 LVS ACCEPT", lvs["verdict"] == "ACCEPT")

    # ③ 足迹 = 节距闭式
    bb = [( _bbox(d)) for d in arr["descs"]]
    W = max(b[1] for b in bb) - min(b[0] for b in bb)
    H = max(b[3] for b in bb) - min(b[2] for b in bb)
    fW, fH = array_footprint(n, m)
    ok &= chk("③ 足迹 bbox = 闭式（节距）",
              abs(W - fW) < 1e-6 and abs(H - fH) < 1e-6)

    # ④ AREF 层次化：展开元素数 ≡ flat
    rt = gds_roundtrip_check(n, m)
    ok &= chk("④ AREF 展开元素数 ≡ flat 元素数", rt["match"])

    # ⑤ W/L 几何回提 ≡ 声明
    wl = extract_wl(arr["descs"])
    exp = expected_netlist(n, m)
    ok &= chk("⑤ W/L 几何回提 ≡ 声明（W=1.20 / L=0.30）",
              abs(wl["W_um"] - exp["W_um"]) < 1e-6
              and abs(wl["L_um"] - exp["L_um"]) < 1e-6)

    # ⑥ 违规可触发：接触孔缩到 0.05 ⇒ 包围/线宽 REJECT
    bad = crossbar_array(n, m, {"cont_um": 0.05, "pad_um": 0.40})
    vbad = run_edrc(bad["descs"])
    ok &= chk("⑥ 接触孔过小 ⇒ DRC REJECT",
              vbad["verdict"] == "REJECT"
              and any(v["rule"] in ("EDR-CONT-ENCLOSURE", "EDR-MIN-WIDTH")
                      for v in vbad["violations"]))

    # ⑦ 短路可触发：把源极焊垫拉到行线上（同层 M1 相交）⇒ LVS REJECT
    el = [dict(d) for d in crossbar_array(1, 1)["descs"]]
    for d in el:
        if d.get("net") == "col0" and d["layer"] == EL.L_M1:
            d["rings_um"] = _ring_square(0.375, 0.0, 0.40)   # 与 row0 行线相交
    vs = elvs_signoff(el, expected_netlist(1, 1))
    ok &= chk("⑦ M1 焊垫搭到行线 ⇒ LVS REJECT（SHORT）",
              vs["verdict"] == "REJECT"
              and any("SHORT" in i for i in vs["issues"]))

    # ⑧ W/L 失配可触发：声明 L 改 0.6 ⇒ LVS DEVICE-MISMATCH REJECT
    bad_exp = expected_netlist(n, m)
    bad_exp["L_um"] = 0.60
    vm = elvs_signoff(arr["descs"], bad_exp)
    ok &= chk("⑧ 声明 L 与几何不符 ⇒ LVS REJECT（DEVICE-MISMATCH）",
              vm["verdict"] == "REJECT"
              and any("DEVICE-MISMATCH" in i for i in vm["issues"]))

    # ⑨ 真出 GDS 且含电子层 20..25
    r = to_gds(n, m)
    parsed = G.parse_gds(r["gds_bytes"])
    layers = set()
    for stt in parsed.get("structures", {}).values():
        layers |= set(stt.get("layers", []))
    ok &= chk("⑨ GDS round-trip 含电子层 20..25",
              bool(r["gds_bytes"]) and {20, 21, 22, 23, 24, 25}.issubset(layers))

    if verbose:
        for nm, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {nm}")
    return bool(ok)
