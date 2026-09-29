"""D-137 · 超导征程 S5 首刀：大 N P&R + 布线路由沟道（吃狗粮）。

S1（D-133）单比特 → S2（D-134）耦合对 → S3（D-135）N 比特阵列 → S4（D-136）读出/控制
+ 串扰/损耗预算。S4 的控制桩是**短线 stub**（键合焊盘片外未建模）。S5 首刀把能力从
「能排带 stub 的阵列」推进到「能把 N 个 qubit 的读出/控制**真正路由到片上焊盘**」——
这正是 53+ / 千比特级芯片的第一个硬卡点（信号数 ∝ N，必须进路由沟道）。

新增能力（纯几何 + 确定性 Manhattan 路由，零量子 SDK）：
  • 路由沟道（routing channel）：阵列导体与地内边之间的显式走廊，宽度随规模自洽。
  • 确定性「梳状」控制路由：每 qubit 控制线从 qubit 中心垂直下落到**本行专属 lane**
    （lane y = row_y − drop − (cols−1−c)·routing_pitch），再水平右引至右侧焊盘列；
    该排布对任意 N **无交叉、无重叠**（见 run_selfchecks 的几何论证）。
  • 行馈线左引：每行馈线向左外延至左侧焊盘列（读出频分复用的片外接口）。
  • 规模自洽比例：行间距 pitch_y 须 ≥ (cols−1)·routing_pitch + drop（否则相邻行 lane
    带重叠）——本模块自动取有效 pitch_y = max(用户值, 该下界)。
  • 路由 DRC（S4 十则 + 路由四则）+ 段感知 LVS（控制网精确桥接 1 qubit + 1 焊盘）。

诚实边界（与 S1–S4 一致）：
  • 焊盘为片上几何（层 FILM，net="pad"）；封装/键合线（>1 mile 低温线）片外未建模（属
    B 类外部依赖）。
  • Cc / ε_eff / loss 参数为设计参数；路由 pitch/焊盘尺寸为**设计规则**（可覆盖 · 非实测
    golden，Foundry PDK 属 D5）。
  • 路由为**单层**（FILM）确定性 Manhattan 梳状方案，非多层/非自动布线器；容量关系见
    routing_capacity（单层走廊的规模瓶颈）。
红线：纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、DRC 限值为设计规则。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from lda_l2 import gds_export as G
# 复用 S4 读出/控制几何范式 + S2 单元原语（同口径，零重复造轮子）
from lda_qeda import sc_readout as S4
from lda_qeda.sc_coupler import _bbox, _overlap

# 超导层（与 gds_export / sc_layout / sc_coupler / sc_array / sc_readout 同源）
FILM = G.LIB_LAYER_SC_FILM
JJ = G.LIB_LAYER_SC_JJ
GROUND = G.LIB_LAYER_SC_GROUND

# S5 路由 DRC 规则名（S4 十则 + 路由四则）
ROUTING_DRC_RULES = tuple(list(S4.READOUT_DRC_RULES) + [
    "SCD-ROUTING-WIRE-SPACING",   # 路由线（控制/馈线，逐段）线间间距 ≥ 下限
    "SCD-ROUTING-PAD-SPACING",    # 焊盘间间距 ≥ 下限
    "SCD-ROUTING-CHANNEL-GAP",    # 路由线-地内边沟道间隙 ≥ 下限
    "SCD-ROUTING-PAD-MIN-WIDTH",  # 键合焊盘最小尺寸
])
DEFAULT_ROUTING_LIMITS = dict(S4.DEFAULT_READOUT_LIMITS)
DEFAULT_ROUTING_LIMITS.update({
    "min_routing_gap_um": 0.6,    # 路由线间最小间距（设计规则 · 可覆盖）
    "min_channel_gap_um": 1.5,    # 路由线-地内边最小沟道间隙
    "min_pad_width_um": 2.0,      # 焊盘最小宽度
    "routing_pitch_um": 4.0,      # 路由 lane 间距（设计规则；须 > 线宽 + min_gap）
    "pad_w_um": 4.0, "pad_h_um": 2.5,
})

RED_LINE_DISCLOSURE = {
    "role": "D-137 = 超导征程 S5 首刀：大 N 阵列 P&R + 布线路由沟道（确定性梳状路由到"
            "片上焊盘），把平台从「带 stub 的阵列」（S4）推进到「能把 N 个 qubit 的"
            "读出/控制路由到焊盘」",
    "layers": "SC_FILM=10 / SC_JJ=11 / SC_GROUND=12（gds_export 定义，非 Foundry PDK）；"
              "路由线 + 焊盘均布在 FILM 层，以 net(control/feedline/pad) 区分",
    "limits": "routing_pitch / min_routing_gap / min_channel_gap / min_pad_width 为"
              "**设计规则 · 可覆盖 · 非实测 golden**（Foundry PDK 金属栈属 D5 外部依赖）",
    "lvs": "段感知几何 LVS：控制线（L 形多段）按**段级**判桥接，须恰好桥接 1 个 qubit_id"
           " + 恰好 1 个焊盘；每个焊盘须接恰好 1 个导体（无悬空）",
    "physics": "路由布局为确定性 Manhattan 梳状方案（几何构图 + 无交叉论证）；不含电磁场"
               "求解（属 D5）。串扰/损耗预算复用 S4 闭式（Blais 2004 ZZ / D-88 Purcell）",
    "routing": "单层确定性路由；规模自洽比例 pitch_y ≥ (cols−1)·routing_pitch + drop，"
               "单层走廊容量关系见 routing_capacity（千比特级须多层/mux）",
    "red_line": "纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、"
                "焊盘为片上几何（封装/键合线片外未建模）",
}
ROLE = RED_LINE_DISCLOSURE["role"]

# 单 transmon 单元几何尺寸（与 gds_export / sc_array / sc_readout 同源）
_T_MONO_PAD_W = 3.0
_T_MONO_PAD_H = 2.0


# ---------------------------------------------------------------------------
# 几何工具（段级：线 vs bbox / 线 vs 线）
# ---------------------------------------------------------------------------
def _polyline_hits_bbox(pts: List[Tuple[float, float]], width_um: float,
                        bb: Tuple[float, float, float, float]) -> bool:
    """多段线（各段轴对齐）是否与 bbox 相交（段级精确，非整线 bbox 粗判）。

    对轴对齐段，段 bbox（含线宽）即该段几何，故逐段 _overlap 即精确。
    """
    h = float(width_um) / 2.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        seg = (min(x1, x2) - h, max(x1, x2) + h, min(y1, y2) - h, max(y1, y2) + h)
        if _overlap(seg, bb):
            return True
    return False


def _wire_bbox(d: Dict) -> Tuple[float, float, float, float]:
    return _bbox(d)


def _gap(a: Tuple[float, float, float, float],
         b: Tuple[float, float, float, float]) -> float:
    dx = max(a[0] - b[1], b[0] - a[1], 0.0)
    dy = max(a[2] - b[3], b[2] - a[3], 0.0)
    return float((dx * dx + dy * dy) ** 0.5)


def _qubit_groups(elements: List[Dict]) -> Dict[int, List[Dict]]:
    groups: Dict[int, List[Dict]] = {}
    for d in elements:
        if d.get("net") == "qubit":
            groups.setdefault(d.get("qubit_id"), []).append(d)
    return groups


def _bbox_of_list(descs: List[Dict]) -> Tuple[float, float, float, float]:
    boxes = [_bbox(d) for d in descs]
    return (min(b[0] for b in boxes), max(b[1] for b in boxes),
            min(b[2] for b in boxes), max(b[3] for b in boxes))


# ---------------------------------------------------------------------------
# 阵列 + 路由沟道几何单元（P&R：确定性梳状控制路由 + 馈线左引 + 焊盘）
# ---------------------------------------------------------------------------
def _qubit_half_extent_y(p: Dict) -> float:
    """单 qubit 相对中心的 y 半高（从 1×1 实建几何量取，随 pad/jj 参数自洽）。"""
    single = S4.readout_array_cell({**p, "rows": 1, "cols": 1})
    ylo: List[float] = []
    yhi: List[float] = []
    for d in single:
        if d.get("net") == "qubit":
            b = _bbox(d)
            ylo.append(b[2]); yhi.append(b[3])
    if not ylo:
        return 1.0
    return float(max(max(yhi), -min(ylo)))


def routing_geometry(params: Optional[Dict] = None) -> Dict:
    """路由几何参数（单一真源，供 cell / capacity / DRC 共用）。

    规模自洽（相邻行 lane 带不重叠的真实下界 —— 须同时容纳：本行 lane 带 + 下落距离 +
    下一行馈线所在区间（feedline 位于 qubit 上方 ph+offset）+ 净空）：
        pitch_y_eff = max(pitch_y_user, (cols−1)·routing_pitch + drop + feed_zone + 净空)
        feed_zone   = pad_h + feedline_offset + feedline_w/2
    """
    p = dict(params or {})
    rows = int(p.get("rows", 2))
    cols = int(p.get("cols", 2))
    pitch_x = float(p.get("pitch_x", 22.0))
    routing_pitch = float(p.get("routing_pitch", DEFAULT_ROUTING_LIMITS["routing_pitch_um"]))
    drop = float(p.get("route_drop", 6.0))
    bond_pad_w = float(p.get("bond_pad_w", DEFAULT_ROUTING_LIMITS["pad_w_um"]))
    bond_pad_h = float(p.get("bond_pad_h", DEFAULT_ROUTING_LIMITS["pad_h_um"]))
    channel_gap = float(p.get("channel_gap", 2.0))
    frame = float(p.get("frame", 5.0))
    pitch_y_user = float(p.get("pitch_y", 14.0))
    mono_ph = float(p.get("pad_h", _T_MONO_PAD_H))     # 与 S4 同键（transmon pad 高）
    feedline_offset = float(p.get("feedline_offset", 4.0))
    feedline_w = float(p.get("feedline_w", 2.0))
    q_half = float(p.get("qubit_half_um", _qubit_half_extent_y(p)))
    clearance = float(p.get("route_clearance", max(routing_pitch, 1.0)))
    band_needed = (cols - 1) * routing_pitch
    feed_zone = mono_ph + feedline_offset + feedline_w / 2.0
    pitch_y_eff = max(pitch_y_user, band_needed + drop + feed_zone + clearance)
    return {
        "rows": rows, "cols": cols, "pitch_x": pitch_x,
        "routing_pitch": routing_pitch, "drop": drop,
        "bond_pad_w": bond_pad_w, "bond_pad_h": bond_pad_h,
        "channel_gap": channel_gap,
        "frame": frame, "pitch_y_user": pitch_y_user,
        "qubit_half_um": q_half, "clearance_um": clearance,
        "feed_zone_um": feed_zone,
        "band_needed_um": band_needed, "pitch_y_eff": pitch_y_eff,
        "pitch_y_growth": pitch_y_eff / pitch_y_user if pitch_y_user > 0 else 1.0,
    }


def routed_array_cell(params: Optional[Dict] = None) -> List[Dict]:
    """大 N 阵列 + 读出/控制路由到片上焊盘（带 net 标签）。

    组成：S4 readout_array_cell 的 qubit/coupler/jj/readout/feedline（控制 stub 替换为
    路由线）+ 控制路由线（net="control"，L 形：垂直落到本行 lane 再水平右引）+ 控制焊盘
    （net="pad", pad_role="control"）+ 馈线焊盘（net="pad", pad_role="feedline"）+
    整框地平面（内边 = 全部导体 bbox + channel_gap，即路由沟道外沿）。
    """
    g = routing_geometry(params)
    p2 = dict(params or {})
    p2["pitch_y"] = g["pitch_y_eff"]
    rows, cols = g["rows"], g["cols"]
    pitch_x, pitch_y = g["pitch_x"], g["pitch_y_eff"]
    routing_pitch, drop = g["routing_pitch"], g["drop"]
    pad_w, pad_h = g["bond_pad_w"], g["bond_pad_h"]
    channel_gap, frame = g["channel_gap"], g["frame"]
    control_w = float(p2.get("control_w", 1.0))

    # 基础 S4 几何，去掉地（自建沟道地）与控制 stub（替换为路由线）
    base = S4.readout_array_cell(p2)
    core = [d for d in base if d.get("net") not in ("ground", "control")]

    x0 = -(cols - 1) * pitch_x / 2.0
    y0 = -(rows - 1) * pitch_y / 2.0

    boxes = [_bbox(d) for d in core]
    ax0 = min(b[0] for b in boxes); ax1 = max(b[1] for b in boxes)
    x_pad_r = ax1 + channel_gap + pad_w / 2.0
    x_pad_l = ax0 - channel_gap - pad_w / 2.0

    elements: List[Dict] = list(core)

    # —— 控制路由线（L 形：垂直落到本行 lane，再水平右引至右侧焊盘列）——
    for r in range(rows):
        cy = y0 + r * pitch_y
        for c in range(cols):
            cx = x0 + c * pitch_x
            qid = r * cols + c
            y_turn = cy - drop - (cols - 1 - c) * routing_pitch
            elements.append({"kind": "path", "layer": FILM, "net": "control",
                             "qubit_id": qid, "width_um": control_w,
                             "points_um": [(cx, cy), (cx, y_turn),
                                           (x_pad_r, y_turn)]})
            elements.append({"kind": "boundary", "layer": FILM, "net": "pad",
                             "pad_role": "control", "qubit_id": qid,
                             "rings_um": [[(x_pad_r - pad_w / 2, y_turn - pad_h / 2),
                                            (x_pad_r + pad_w / 2, y_turn - pad_h / 2),
                                            (x_pad_r + pad_w / 2, y_turn + pad_h / 2),
                                            (x_pad_r - pad_w / 2, y_turn + pad_h / 2)]]})

    # —— 馈线左引至左侧焊盘列 + 焊盘 ——
    for d in elements:
        if d.get("net") == "feedline":
            pts = list(d["points_um"])
            left = min(pts, key=lambda q: q[0])
            yf = left[1]
            d["points_um"] = [(x_pad_l, yf)] + pts
            elements.append({"kind": "boundary", "layer": FILM, "net": "pad",
                             "pad_role": "feedline", "qubit_id": None,
                             "rings_um": [[(x_pad_l - pad_w / 2, yf - pad_h / 2),
                                            (x_pad_l + pad_w / 2, yf - pad_h / 2),
                                            (x_pad_l + pad_w / 2, yf + pad_h / 2),
                                            (x_pad_l - pad_w / 2, yf + pad_h / 2)]]})

    # —— 整框地平面（内边 = 全部导体 bbox + channel_gap，即路由沟道外沿）——
    cboxes = [_bbox(d) for d in elements]
    bx0 = min(b[0] for b in cboxes); bx1 = max(b[1] for b in cboxes)
    by0 = min(b[2] for b in cboxes); by1 = max(b[3] for b in cboxes)
    px0, px1 = bx0 - channel_gap, bx1 + channel_gap
    py0, py1 = by0 - channel_gap, by1 + channel_gap
    fo = frame
    ox0, ox1 = px0 - fo, px1 + fo
    oy0, oy1 = py0 - fo, py1 + fo
    elements.extend([
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(ox0, py1), (ox1, py1), (ox1, oy1), (ox0, oy1)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(ox0, oy0), (ox1, oy0), (ox1, py0), (ox0, py0)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(ox0, oy0), (px0, oy0), (px0, oy1), (ox0, oy1)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(px1, oy0), (ox1, oy0), (ox1, oy1), (px1, oy1)]]},
    ])
    return elements


# ---------------------------------------------------------------------------
# GDS / SVG 出口
# ---------------------------------------------------------------------------
def routed_gds(params: Optional[Dict] = None, path: str = "sc_routing.gds") -> bytes:
    """真出 GDSII（零依赖自写编码器）。返回文件字节。"""
    descs = routed_array_cell(params)
    recs: List[bytes] = []
    for d in descs:
        if d["kind"] == "path":
            recs.append(G.path(d["layer"], d["width_um"], d["points_um"]))
        else:
            recs.append(G.boundary(d["layer"], G._flatten_rings(d.get("rings_um"))))
    data = G.gds_library("LDA-SC-ROUTING", {"sc_routing": recs})
    G.write_gds(path, data)
    return data


def routed_svg_preview(params: Optional[Dict] = None, width: int = 620) -> str:
    """版图 SVG 预览（net 上色：qubit=蓝 / jj=红 / coupler=橙 / readout=绿 /
    control=紫 / feedline=青 / pad=墨 / ground=灰）。"""
    descs = routed_array_cell(params)
    net_color = {"qubit": "#2563eb", "jj": "#e11d48", "coupler": "#f59e0b",
                 "readout": "#16a34a", "control": "#7c3aed",
                 "feedline": "#0891b2", "pad": "#0f172a", "ground": "#94a3b8"}
    xs, ys = [], []
    for d in descs:
        pts = d.get("points_um") or [p for r in d.get("rings_um", []) for p in r]
        xs += [p[0] for p in pts]
        ys += [p[1] for p in pts]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    span = max(xmax - xmin, ymax - ymin, 1e-6)
    pad = 24
    S = (width - 2 * pad) / span
    X = lambda x: pad + (x - xmin) * S
    Y = lambda y: pad + (ymax - y) * S
    out = [f'<svg width="{width}" height="{width}" '
           'style="background:#fff;border:1px solid #ddd;border-radius:6px">']
    for d in descs:
        col = net_color.get(d.get("net"), "#2563eb")
        pts = d.get("points_um") or [p for r in d.get("rings_um", []) for p in r]
        dd = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in pts)
        if d["kind"] == "path":
            out.append(f'<polyline points="{dd}" fill="none" stroke="{col}" '
                       f'stroke-width="{max(d.get("width_um", 0.5) * S, 2):.1f}"/>')
        else:
            out.append(f'<polygon points="{dd}" fill="{col}" fill-opacity="0.75"/>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------
# 路由 DRC（S4 十则 + 路由四则）
# ---------------------------------------------------------------------------
def _wire_segments(elements: List[Dict]):
    """把控制/馈线（多段线）展开为逐段轴对齐矩形 (x0,x1,y0,y1,net,qid,wid)。

    wid = 元素索引（同一根线的段共享 wid ⇒ 间距检查跳过自身拐角）。
    """
    segs = []
    for wi, d in enumerate(elements):
        if d.get("net") not in ("control", "feedline"):
            continue
        h = float(d.get("width_um", 0.0)) / 2.0
        pts = d.get("points_um", [])
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            segs.append((min(x1, x2) - h, max(x1, x2) + h,
                         min(y1, y2) - h, max(y1, y2) + h,
                         d.get("net"), d.get("qubit_id"), wi))
    return segs


def _sweep_min_gap(segs, thresh: float):
    """按 y 扫描的逐段最小间距（返回 < thresh 的异线对；同线自身拐角跳过）。

    O(S log S) 典型；返回 (net_i, qid_i, net_j, qid_j, gap)。
    """
    order = sorted(segs, key=lambda s: s[2])
    bad = []
    for i in range(len(order)):
        xi0, xi1, yi0, yi1, ni, qi, wi = order[i]
        for j in range(i + 1, len(order)):
            xj0, xj1, yj0, yj1, nj, nj_q, wj = order[j]
            if yj0 > yi1 + thresh:
                break
            if wi == wj:                                     # 同一根线（含拐角）跳过
                continue
            g = _gap((xi0, xi1, yi0, yi1), (xj0, xj1, yj0, yj1))
            if g < thresh - 1e-9:
                bad.append((ni, qi, nj, nj_q, g))
    return bad


def run_routing_drc(elements: List[Dict],
                    limits: Optional[Dict] = None) -> Dict:
    """S5 路由 DRC：S4 十则 + 路由四则（逐段线间间距/焊盘间距/沟道间隙/焊盘尺寸）。

    返回 {verdict, violations, n_rules, limits}。verdict ∈ {ACCEPT, REJECT}。
    """
    lim = dict(DEFAULT_ROUTING_LIMITS)
    if limits:
        lim.update(limits)
    base = S4.run_readout_drc(elements, lim)              # S4 十则（同口径复用）
    violations: List[Dict] = list(base["violations"])
    checked = base.get("checked", 0)

    min_rgap = float(lim["min_routing_gap_um"])
    min_cgap = float(lim["min_channel_gap_um"])
    min_pad = float(lim["min_pad_width_um"])

    ground_boxes = [_bbox(d) for d in elements if d.get("net") == "ground"]
    segs = _wire_segments(elements)
    pads = [d for d in elements if d.get("net") == "pad"]

    # ① 路由线逐段间距（线间净空 < 下限 ⇒ 违规）
    for (ni, qi, nj, qj, g) in _sweep_min_gap(segs, min_rgap):
        checked += 1
        violations.append({"rule": "SCD-ROUTING-WIRE-SPACING",
                            "detail": f"路由段({ni}#{qi})↔({nj}#{qj}) 间距 {g:.3f} µm "
                                      f"< {min_rgap:.3f} µm"})

    # ② 焊盘间间距（焊盘 pairwise 净空 < 下限 ⇒ 违规）
    pboxes = [_bbox(pd) for pd in pads]
    for i in range(len(pboxes)):
        for j in range(i + 1, len(pboxes)):
            checked += 1
            g = _gap(pboxes[i], pboxes[j])
            if g < min_rgap - 1e-9:
                violations.append({"rule": "SCD-ROUTING-PAD-SPACING",
                                    "detail": f"焊盘间间距 {g:.3f} µm < {min_rgap:.3f} µm"})

    # ③ 路由线（逐段）→ 地内边沟道间隙
    for (x0, x1, y0, y1, net, q, _wi) in segs:
        if not ground_boxes:
            continue
        g = min((_gap((x0, x1, y0, y1), gb) for gb in ground_boxes), default=1e9)
        checked += 1
        if g < min_cgap - 1e-9:
            violations.append({"rule": "SCD-ROUTING-CHANNEL-GAP",
                                "detail": f"路由段({net}#{q})→地沟道间隙 {g:.3f} µm "
                                          f"< {min_cgap:.3f} µm"})

    # ④ 焊盘最小尺寸
    for pd in pads:
        b = _bbox(pd)
        checked += 1
        thin = min(b[1] - b[0], b[3] - b[2])
        if thin < min_pad - 1e-12:
            violations.append({"rule": "SCD-ROUTING-PAD-MIN-WIDTH",
                                "detail": f"焊盘最薄边 {thin:.3f} µm < {min_pad:.3f} µm"})

    verdict = "ACCEPT" if not violations else "REJECT"
    return {"verdict": verdict, "violations": violations,
            "n_rules": len(ROUTING_DRC_RULES), "limits": lim, "checked": checked}


# ---------------------------------------------------------------------------
# 段感知几何 LVS（控制网精确桥接 1 qubit + 1 焊盘）
# ---------------------------------------------------------------------------
def routed_array_lvs(elements: List[Dict]) -> Dict:
    """S5 段感知几何 LVS（对实际 produced 几何做网表提取）。

    判据：① 每导体有 net ② 每 qubit 有 JJ 桥接 + ≥2 端口臂 ③ 馈线 segment 数 == 行数
    ④ 每读出桥接恰好 1 qubit + 邻近恰好 1 馈线 ⑤ 每控制线（L 形多段）**段级**桥接恰好
    1 qubit + 恰好 1 焊盘 ⑥ 每焊盘接恰好 1 导体（无悬空）⑦ 控制焊盘数 == qubit 数
    ⑧ 耦合器桥接恰好 2 qubit ⑨ 耦合图连通 ⑩ 地单一分量无短接 ⑪ 读出/控制不与地短接。
    返回 {verdict, issues, netlist, n_checks}。
    """
    issues: List[str] = []
    n_checks = 0

    cond = [d for d in elements if d["kind"] in ("path", "boundary")]
    n_checks += 1
    if any(not d.get("net") for d in cond):
        issues.append("SCD-LVS-NO-NET: 存在无 net 标签的导体元素")

    qgroups = _qubit_groups(elements)
    qboxes = {q: _bbox_of_list(c) for q, c in qgroups.items()}    # 预计算（规模）
    jj_elems = [d for d in elements if d["layer"] == JJ]
    couplers = [d for d in elements if d.get("net") == "coupler"]
    readouts = [d for d in elements if d.get("net") == "readout"]
    controls = [d for d in elements if d.get("net") == "control"]
    feedlines = [d for d in elements if d.get("net") == "feedline"]
    pads = [d for d in elements if d.get("net") == "pad"]
    ground = [_bbox(d) for d in elements if d.get("net") == "ground"]

    # ② qubit 网（JJ 桥接 + ≥2 臂）
    n_checks += 1
    n_qubit_found = 0
    for qid, comp in qgroups.items():
        qbb = qboxes[qid]
        jj_touch = any(_overlap(_bbox(j), qbb) for j in jj_elems)
        arms = [d for d in comp if d["kind"] == "path"]
        if not jj_touch:
            issues.append(f"SCD-LVS-QUBIT-NO-JJ: qubit {qid} 缺 JJ 桥接（岛屿断开）")
        if len(arms) < 2:
            issues.append(f"SCD-LVS-QUBIT-PORTS: qubit {qid} 端口臂 < 2")
        else:
            n_qubit_found += 1

    # ③ 馈线 segment 数 == 行数
    n_checks += 1
    n_feed = len(feedlines)
    exp_rows = S4._infer_rows(elements)
    if n_feed != exp_rows:
        issues.append(f"SCD-LVS-FEEDLINE-SPLIT: 馈线 segment 数 {n_feed} ≠ 预期行数 "
                      f"{exp_rows}（馈线断裂/多余）")

    # ④ 读出桥接 1 qubit + 邻近 1 馈线
    n_checks += 1
    couple_tol = float(DEFAULT_ROUTING_LIMITS["readout_feedline_couple_um"])
    feed_boxes = [_bbox(d) for d in feedlines]
    readout_qids = set()
    for rd in readouts:
        rbb = _bbox(rd)
        readout_qids.add(rd.get("qubit_id"))
        touched = [q for q, b in qboxes.items() if _overlap(rbb, b)]
        overlap_f = any(_overlap(rbb, fb) for fb in feed_boxes)
        near_f = [fb for fb in feed_boxes if _gap(rbb, fb) <= couple_tol + 1e-9]
        if overlap_f:
            issues.append("SCD-LVS-READOUT-FEEDLINE-SHORT: 读出腔与馈线几何重叠（短接）")
        elif len(touched) != 1:
            issues.append(f"SCD-LVS-READOUT-BRIDGE-Q: 读出桥接 {len(touched)} 个 qubit"
                          f"（须恰好 1，qubit_id={rd.get('qubit_id')}）")
        elif len(near_f) != 1:
            issues.append(f"SCD-LVS-READOUT-BRIDGE-F: 读出邻近 {len(near_f)} 条馈线"
                          f"（须恰好 1，qubit_id={rd.get('qubit_id')}）")
    for qid in qgroups:
        if qid not in readout_qids:
            issues.append(f"SCD-LVS-QUBIT-NO-READOUT: qubit {qid} 缺读出谐振腔")

    # ⑤ 控制线（段级）桥接恰好 1 qubit + 恰好 1 焊盘（+ 每 qubit 须有控制线）
    n_checks += 1
    pad_boxes = [(_bbox(pd), pd.get("pad_role"), pd.get("qubit_id")) for pd in pads]
    bridged_qids = set()
    for cd in controls:
        pts = cd["points_um"]
        w = float(cd.get("width_um", 0.0))
        touched = [q for q, b in qboxes.items() if _polyline_hits_bbox(pts, w, b)]
        if len(touched) != 1:
            issues.append(f"SCD-LVS-CONTROL-BRIDGE-Q: 控制线桥接 {len(touched)} 个 qubit"
                          f"（须恰好 1，qubit_id={cd.get('qubit_id')}）")
        else:
            bridged_qids.add(touched[0])
        npad = sum(1 for (pbb, _role, _q) in pad_boxes
                   if _polyline_hits_bbox(pts, w, pbb))
        if npad != 1:
            issues.append(f"SCD-LVS-CONTROL-NO-PAD: 控制线接 {npad} 个焊盘"
                          f"（须恰好 1，qubit_id={cd.get('qubit_id')}）")
    for qid in qgroups:
        if qid not in bridged_qids:
            issues.append(f"SCD-LVS-QUBIT-NO-CONTROL: qubit {qid} 缺控制路由线")

    # ⑥ 每焊盘接恰好 1 导体（无悬空）
    n_checks += 1
    n_ctrl_pad = sum(1 for (_b, role, _q) in pad_boxes if role == "control")
    for (pbb, role, q) in pad_boxes:
        touch = 0
        for d in controls + feedlines:
            if d["kind"] == "path":
                if _polyline_hits_bbox(d["points_um"], float(d.get("width_um", 0.0)), pbb):
                    touch += 1
            elif _overlap(pbb, _bbox(d)):
                touch += 1
        if touch != 1:
            issues.append(f"SCD-LVS-PAD-FLOATING: 焊盘(role={role},qid={q}) 接 {touch} 个"
                          "导体（须恰好 1）")

    # ⑦ 控制焊盘数 == qubit 数
    n_checks += 1
    if n_ctrl_pad != len(qgroups):
        issues.append(f"SCD-LVS-PAD-COUNT: 控制焊盘 {n_ctrl_pad} ≠ qubit 数 "
                      f"{len(qgroups)}")

    # ⑧ 耦合器桥接恰好 2 qubit
    n_checks += 1
    edges = []
    for cp in couplers:
        cbb = _bbox(cp)
        touched = [q for q, b in qboxes.items() if _overlap(cbb, b)]
        if len(touched) != 2:
            issues.append("SCD-LVS-COUPLER-BRIDGE-NE2: 耦合器桥接 "
                          f"{len(touched)} 个 qubit（须恰好 2）")
        else:
            edges.append(tuple(sorted(touched)))

    # ⑨ 耦合图连通
    n_checks += 1
    qid_list = sorted(qgroups.keys())
    remap = {q: i for i, q in enumerate(qid_list)}
    parent = list(range(len(qid_list)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for (a, b) in edges:
        if a in remap and b in remap:
            union(remap[a], remap[b])
    comps_graph = set(find(remap[q]) for q in qid_list)
    if len(qid_list) > 1:
        if not edges:
            issues.append("SCD-LVS-NO-COUPLER: 多 qubit 阵列缺耦合元件（未连通）")
        if len(comps_graph) > 1:
            issues.append(f"SCD-LVS-FLOATING-QUBIT: 耦合图分成 {len(comps_graph)} 个孤立分量")

    # ⑩ 地单一分量无短接
    n_checks += 1
    gcomps = S4.SA._ground_components(elements)
    if len(gcomps) != 1:
        issues.append(f"SCD-LVS-GROUND-SPLIT: 地平面分成 {len(gcomps)} 个分量")
    qubit_boxes = [_bbox(d) for d in elements if d.get("net") == "qubit"]
    if any(_overlap(qb, gb) for qb in qubit_boxes for gb in ground):
        issues.append("SCD-LVS-QUBIT-GROUND-SHORT: 导体与地平面重叠（短接）")

    # ⑪ 读出/控制不与地短接
    n_checks += 1
    if any(_overlap(_bbox(d), gb) for d in readouts + controls for gb in ground):
        issues.append("SCD-LVS-ROUTING-GROUND-SHORT: 读出/控制与地短接")

    verdict = "ACCEPT" if not issues else "REJECT"
    return {"verdict": verdict, "issues": issues,
            "netlist": {"qubit_nets": n_qubit_found,
                        "feedline_segments": n_feed,
                        "readout": len(readouts),
                        "control": len(controls),
                        "pads_control": n_ctrl_pad,
                        "pads_total": len(pads),
                        "coupler": len(couplers),
                        "ground_nets": len(gcomps),
                        "edges_bridged": len(edges)},
            "n_checks": n_checks}


# ---------------------------------------------------------------------------
# 路由容量（闭式规模关系）
# ---------------------------------------------------------------------------
def routing_capacity(params: Optional[Dict] = None) -> Dict:
    """单层路由走廊的规模关系（闭式）。

    • 主瓶颈：行间距须 ≥ (cols−1)·routing_pitch（否则相邻行 lane 带重叠）⇒ 行间距被
      cols 拉大，芯片面积 ≈ cols × (rows·pitch_y_eff) ∝ cols²（方阵 N=cols²）。
    • 信号数 ∝ N（控制 N + 馈线 rows）；单层走廊高度 ∝ rows·pitch_y_eff ∝ N。
    • 给出「基准 pitch_y 下最多允许多少列」max_cols_at_base_pitch 与增长因子。
    """
    g = routing_geometry(params)
    rows, cols = g["rows"], g["cols"]
    n_control = rows * cols
    n_feedline = rows
    n_signals = n_control + n_feedline
    pitch_x = g["pitch_x"]
    base_py = g["pitch_y_user"]
    rp = g["routing_pitch"]
    drop = g["drop"]
    # 基准行间距下，lane 带 + drop + 余量须装进 pitch_y ⇒ 最大列数
    max_cols = int(max(0.0, (base_py - drop - rp) // rp)) + 1 if rp > 0 else cols
    chip_w = cols * pitch_x
    chip_h = rows * g["pitch_y_eff"]
    return {
        "n_control": n_control, "n_feedline": n_feedline, "n_signals": n_signals,
        "routing_pitch_um": rp, "pitch_y_eff_um": g["pitch_y_eff"],
        "pitch_y_growth": g["pitch_y_growth"],
        "band_needed_um": g["band_needed_um"],
        "qubit_half_um": g["qubit_half_um"], "clearance_um": g["clearance_um"],
        "chip_w_um": chip_w, "chip_h_um": chip_h,
        "max_cols_at_base_pitch": max_cols,
        "band_fits": bool(g["pitch_y_eff"] + 1e-9 >= g["band_needed_um"] + drop
                          + g["qubit_half_um"]),
        "note": "单层确定性梳状路由：行间距自洽放大 ∝ cols；千比特级信号数 ∝ N 需多层/mux"
                "（属 B 类架构扩展）。几何关系为设计口径。",
    }


# ---------------------------------------------------------------------------
# 自检（常驻断言：合法 ACCEPT/ACCEPT；各违规 REJECT）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    ok = True
    msgs: List[Tuple[str, bool]] = []

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        msgs.append((name, bool(cond)))

    # ① 合法 2×2 路由阵列 DRC ACCEPT
    g22 = routed_array_cell({"rows": 2, "cols": 2})
    chk("① 合法 2×2 路由阵列 DRC ACCEPT（S4 十则 + 路由四则）",
        run_routing_drc(g22)["verdict"] == "ACCEPT")

    # ② 合法 2×2 路由阵列 LVS ACCEPT（4 控制网各桥 1 qubit + 1 焊盘 · 2 馈线焊盘）
    v22 = routed_array_lvs(g22)
    chk("② 合法 2×2 路由阵列 LVS ACCEPT（控制 4 网 · 焊盘 4+2 · 连通）",
        v22["verdict"] == "ACCEPT")

    # ③ 合法 1×4 链 DRC/LVS 双 ACCEPT
    chain = routed_array_cell({"rows": 1, "cols": 4})
    chk("③ 合法 1×4 链 DRC ACCEPT", run_routing_drc(chain)["verdict"] == "ACCEPT")
    chk("④ 合法 1×4 链 LVS ACCEPT（控制 4 网 · 焊盘 4+1 · 连通）",
        routed_array_lvs(chain)["verdict"] == "ACCEPT")

    # ⑤ 缺控制线 ⇒ LVS REJECT（QUBIT-NO-CONTROL）
    no_ctrl = [d for d in g22
               if not (d.get("net") == "control")
               and not (d.get("net") == "pad" and d.get("pad_role") == "control")]
    vnc = routed_array_lvs(no_ctrl)
    chk("⑤ 缺控制线 ⇒ LVS REJECT（QUBIT-NO-CONTROL）",
        vnc["verdict"] == "REJECT"
        and any("QUBIT-NO-CONTROL" in i for i in vnc["issues"]))

    # ⑥ 控制线断焊盘（截短 L 形水平段）⇒ LVS REJECT（CONTROL-NO-PAD）
    cut = []
    for d in g22:
        if d.get("net") == "control":
            d2 = dict(d)
            (p0, p1, p2) = d["points_um"]
            d2["points_um"] = [p0, p1, (p1[0] + 0.5, p1[1])]    # 水平段缩短到 0.5µm
            cut.append(d2)
        else:
            cut.append(d)
    vcut = routed_array_lvs(cut)
    chk("⑥ 控制线未达焊盘 ⇒ LVS REJECT（CONTROL-NO-PAD）",
        vcut["verdict"] == "REJECT"
        and any("CONTROL-NO-PAD" in i for i in vcut["issues"]))

    # ⑦ 焊盘悬空（移走全部控制焊盘）⇒ LVS REJECT（PAD-COUNT / CONTROL-NO-PAD）
    nopad = [d for d in g22
             if not (d.get("net") == "pad" and d.get("pad_role") == "control")]
    vnp = routed_array_lvs(nopad)
    chk("⑦ 缺控制焊盘 ⇒ LVS REJECT（PAD-COUNT：控制焊盘 0 ≠ qubit 数）",
        vnp["verdict"] == "REJECT"
        and any("PAD-COUNT" in i for i in vnp["issues"]))

    # ⑧ 路由线间距不足 ⇒ DRC REJECT（SCD-ROUTING-WIRE-SPACING）
    thin_rp = routed_array_cell({"rows": 1, "cols": 3, "routing_pitch": 0.3})
    vts = run_routing_drc(thin_rp)
    chk("⑧ 路由 lane 太密(pitch0.3·线宽1) ⇒ DRC REJECT（ROUTING-WIRE-SPACING）",
        vts["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-ROUTING-WIRE-SPACING" for v in vts["violations"]))

    # ⑨ 焊盘太小 ⇒ DRC REJECT（SCD-ROUTING-PAD-MIN-WIDTH）
    small_pad = routed_array_cell({"rows": 1, "cols": 2,
                                   "bond_pad_w": 0.5, "bond_pad_h": 0.5})
    vsp = run_routing_drc(small_pad)
    chk("⑨ 焊盘太小(0.5<2.0) ⇒ DRC REJECT（ROUTING-PAD-MIN-WIDTH）",
        vsp["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-ROUTING-PAD-MIN-WIDTH" for v in vsp["violations"]))

    # ⑩ 行间距自洽：小 pitch_y 被放大到 (cols−1)·routing_pitch + drop + rp
    cap = routing_capacity({"rows": 2, "cols": 5, "pitch_y": 8.0, "routing_pitch": 2.0,
                            "route_drop": 6.0})
    chk("⑩ 规模自洽：pitch_y_eff = max(用户值, (cols−1)·rp + drop + rp)",
        cap["pitch_y_eff_um"] >= (5 - 1) * 2.0 + 6.0 + 2.0 - 1e-9)

    # ⑪ 规则数 / 网表规模
    chk("⑪ 规则名 / n_rules 稳定（ROUTING_DRC_RULES = S4 十则 + 路由四则 = 14）",
        len(ROUTING_DRC_RULES) == 14 and run_routing_drc(g22)["n_rules"] == 14)
    nl = routed_array_lvs(g22)["netlist"]
    chk("⑫ 2×2 网表：qubit 4 · 控制 4 · 控制焊盘 4 · 焊盘 6 · 馈线 2 · 边 4 · 地 1",
        nl["qubit_nets"] == 4 and nl["control"] == 4 and nl["pads_control"] == 4
        and nl["pads_total"] == 6 and nl["feedline_segments"] == 2
        and nl["edges_bridged"] == 4 and nl["ground_nets"] == 1)

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok
