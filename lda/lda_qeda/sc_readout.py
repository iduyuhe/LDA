"""D-136 · 超导征程 S4：读出/控制线路 + 串扰/损耗预算（吃狗粮）。

S1（D-133）单 transmon 单元签核；S2（D-134）耦合 transmon 对；S3（D-135）把平台推进到
**N 比特阵列 P&R + 超导规模 DRC/LVS + 逐边物理签核**。S4 在阵列之上补**外围互连与
系统级预算**：把芯片从「能排阵列」推进到「带读出/控制线路、可算串扰与损耗预算」。

三大新增能力（均纯几何 + 闭式物理，零量子 SDK）：
  • 读出线路：每 qubit 一条色散读出谐振腔（net="readout"，几何桥接 qubit↔其所在行
    馈线 net="feedline"），共享行馈线做频分复用读出。
  • 控制线路：每 qubit 一条控制桩（net="control"，垂直向下桥接 qubit，落入行间/地前
    沟道，留地间隙，不短接地、不误桥邻 qubit）。
  • 串扰预算（全 pair）：用几何电容 1/d³ 标度为非最近邻对估背景耦合 J_bg，再用二阶
    微扰 ZZ 率 ζ_zz = 2J²α/(Δ(Δ+α))（Blais 2004 色散，MHz）算全 pair 静态 ZZ 矩阵，
    报最大的「杂散 ZZ」（非耦合对）与最近邻 ZZ（信息）；控制线串扰用平行线段 fringe
    电容闭式估 X = C_x/C_q。
  • 损耗预算（per-qubit）：Barends/Marinis 参与比模型 1/T1 = Σ tanδ_i·p_i（几何定 p_i）
    + Purcell 限制 γ_P = κg²/Δ²（复用 D-88 闭式）+ 辐射项；报 T1_total 与 Purcell 保护。

诚实边界（与 S1–S3 一致，并显式标注 S4 新增）：
  • 读出谐振频率 f_r、馈线 κ、读出耦合 g、tanδ_i、参与比 p_i、控制线 ε_eff/t、C_q 均为
    **设计参数**，非实测 PDK（属 D5）。闭式**公式**为确定性物理定律（golden）；数值是
    设计预算口径。
  • 串扰/损耗为**几何 + 闭式估计**，非电磁场求解器全波仿真（属 D5 外部依赖）。
  • 控制桩为片上 stub，键合焊盘在片外（未建模）；几何上不短接地、不误桥邻 qubit。
  • 复用 S3 阵列 + S2 单元原语 + D-88 色散/Purcell 闭式，零重复造轮子。
红线：纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、DRC 限值为设计规则。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from lda_l2 import gds_export as G
# 复用 S3 阵列 P&R 与 S2 单元原语（保证与 S2/S3 同口径，零重复造轮子）
from lda_qeda import sc_array as SA
from lda_qeda.sc_coupler import (_bbox, _overlap)
from lda_solver import coupler_solver as CS

# 超导层（与 gds_export / sc_layout / sc_coupler / sc_array 同源）
FILM = G.LIB_LAYER_SC_FILM
JJ = G.LIB_LAYER_SC_JJ
GROUND = G.LIB_LAYER_SC_GROUND

# 单 transmon 单元几何尺寸（与 gds_export Transmon 默认一致，用于控制桩定位）
_T_MONO_PAD_W = 3.0
_T_MONO_PAD_H = 2.0
_T_MONO_ARM_LEN = 6.0

# S4 读出/控制 DRC 规则名（在 S3 五则基础上扩读出/控制几何规则）
READOUT_DRC_RULES = (
    "SCD-MIN-WIDTH",            # 导体最小线宽（含读出/馈线/控制）
    "SCD-MIN-JJ",               # 约瑟夫森结最小尺寸
    "SCD-MIN-GROUND-GAP",       # qubit 导体到地平面最小间隙（逐分量）
    "SCD-QUBIT-GROUND-SHORT",   # qubit 导体与地平面不得重叠（短接）
    "SCD-ARRAY-QUIBIT-SPACING", # 不同 qubit 分量导体不得互叠（强制 pitch）
    "SCD-READOUT-MIN-WIDTH",    # 读出谐振腔最小线宽
    "SCD-FEEDLINE-MIN-WIDTH",   # 馈线最小线宽
    "SCD-CONTROL-MIN-WIDTH",    # 控制桩最小线宽
    "SCD-READOUT-FEEDLINE-GAP", # 读出腔-馈线耦合间隙（≥ 下限，防短接）
    "SCD-CONTROL-GROUND-GAP",   # 控制桩-地间隙（≥ 下限，防短接）
)
DEFAULT_READOUT_LIMITS = {
    "min_width_um": 0.2,        # 设计规则（可覆盖 · 非实测 golden）
    "min_jj_um": 0.15,
    "min_ground_gap_um": 0.5,
    "min_spacing_um": 1e-6,
    "min_readout_width_um": 0.8,
    "min_feedline_width_um": 1.0,
    "min_control_width_um": 0.6,
    "min_readout_feedline_gap_um": 0.2,   # 耦合间隙下限（< 则短接）
    "readout_feedline_couple_um": 3.0,    # 读出-馈线耦合邻近容差（≤ 此距算桥接）
    "min_control_ground_gap_um": 1.5,     # 控制桩-地间隙下限
}

# 串扰/损耗预算验收阈值（设计参数）
ZZ_STRAY_LIMIT_MHZ = 1.0        # 杂散 ZZ（非耦合对）预算上限：高于此干扰闲置 spectator
                              # （典型固定频率 transmon 网格 spectator ZZ ~0.1–1 MHz，可经
                              # 动态解耦管理；最近邻 ZZ~1 MHz 为 CR 本征相互作用，不计入此限）
CONTROL_XTALK_LIMIT = 0.05      # 控制线串扰系数上限
T1_TARGET_US = 20.0             # per-qubit T1 目标（µs）

RED_LINE_DISCLOSURE = {
    "role": "D-136 = 超导征程 S4：在 S3 阵列上补读出/控制线路 + 串扰预算 + 损耗预算，"
            "把平台从「能排阵列」推进到「带互连与系统级预算」",
    "layers": "SC_FILM=10 / SC_JJ=11 / SC_GROUND=12（gds_export 定义，非 Foundry PDK）；"
              "读出/馈线/控制均布在 FILM 层，以 net 区分（与 S2/S3 同口径）",
    "limits": "min_width/min_jj/min_ground_gap/readout/control 限值为**设计规则 · 可覆盖 · "
              "非实测 golden**（Foundry PDK 属 D5 外部依赖，平台不沾）",
    "lvs": "几何 LVS 对**实际 produced 几何**做 bbox 重叠/邻近网表提取（不重放意图）；"
           "读出桥接 1 qubit_id + 邻近 1 行馈线；控制桥接恰好 1 qubit_id",
    "physics": "串扰：全 pair 二阶微扰 ZZ 率 ζ_zz=2J²α/(Δ(Δ+α))（Blais 2004 色散，golden）；"
               "非最近邻 J_bg 用几何 1/d³ 标度估（设计估计）。损耗：Barends 参与比 "
               "1/T1=Σtanδ_i·p_i + Purcell γ_P=κg²/Δ²（复用 D-88 闭式）。f_r/κ/g/tanδ/p_i 为"
               "设计参数（非 golden），公式为确定性物理定律",
    "red_line": "纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、"
                "读出/控制为几何 stub（键合焊盘片外未建模）",
}


# ---------------------------------------------------------------------------
# 阵列 + 读出/控制线路几何单元（P&R）
# ---------------------------------------------------------------------------
def readout_array_cell(params: Optional[Dict] = None) -> List[Dict]:
    """阵列（S3）+ 读出谐振腔 + 行馈线 + 控制桩 的几何元素（带 net 标签）。

    组成：
      • qubit/coupler/ground：复用 S3 array_cell，但**重建地平面**为带 routing 沟道
        （inner edge = 阵列 bbox + routing_margin）的外框，给读出/控制留布线空间。
      • 每 row 一条行馈线（net="feedline"，path），做该 row 频分复用读出。
      • 每 qubit 一条读出谐振腔（net="readout"，boundary，qubit_id）：上跨 qubit 顶 pad，
        下邻其 row 馈线（耦合间隙），几何桥接 qubit↔feedline。
      • 每 qubit 一条控制桩（net="control"，path，qubit_id）：垂直向下桥接 qubit，落入
        行间/地前沟道，留地间隙，不短接地、不误桥邻 qubit。
    """
    p = dict(params or {})
    rows = int(p.get("rows", 2))
    cols = int(p.get("cols", 2))
    pitch_x = float(p.get("pitch_x", 22.0))
    pitch_y = float(p.get("pitch_y", 14.0))
    rm = float(p.get("routing_margin", 8.0))        # routing 沟道半宽
    feedline_offset = float(p.get("feedline_offset", 4.0))
    readout_hw = float(p.get("readout_hw", 1.0))    # 读出腔半宽
    readout_hh = float(p.get("readout_hh", 1.5))    # 读出腔半高
    feedline_w = float(p.get("feedline_w", 2.0))
    control_w = float(p.get("control_w", 1.0))
    control_len = float(p.get("control_len", 4.0))
    mono_params = {k: v for k, v in p.items()
                   if k in ("pad_w", "pad_h", "gap_x", "jj_len", "jj_h",
                            "cpw_w", "arm_len")}
    ph = float(mono_params.get("pad_h", _T_MONO_PAD_H))

    x0 = -(cols - 1) * pitch_x / 2.0
    y0 = -(rows - 1) * pitch_y / 2.0

    base = SA.array_cell(p)
    qc = [d for d in base if d.get("net") != "ground"]   # 去掉 S3 地，自建带沟道地

    # 导体 bbox → 重建地平面（带 routing 沟道）
    cond_boxes = [_bbox(d) for d in qc]
    ax0 = min(b[0] for b in cond_boxes)
    ax1 = max(b[1] for b in cond_boxes)
    ay0 = min(b[2] for b in cond_boxes)
    ay1 = max(b[3] for b in cond_boxes)
    px0, px1 = ax0 - rm, ax1 + rm
    py0, py1 = ay0 - rm, ay1 + rm
    fo = 5.0
    ox0, ox1 = px0 - fo, px1 + fo
    oy0, oy1 = py0 - fo, py1 + fo
    ground = [
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(ox0, py1), (ox1, py1), (ox1, oy1), (ox0, oy1)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(ox0, oy0), (ox1, oy0), (ox1, py0), (ox0, py0)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(ox0, oy0), (px0, oy0), (px0, oy1), (ox0, oy1)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(px1, oy0), (ox1, oy0), (ox1, oy1), (px1, oy1)]]},
    ]
    elements: List[Dict] = list(qc) + ground

    # 每 row 一行馈线（频分复用读出总线）
    for r in range(rows):
        yf = y0 + r * pitch_y + ph + feedline_offset
        elements.append({"kind": "path", "layer": FILM, "net": "feedline",
                         "qubit_id": None, "width_um": feedline_w,
                         "points_um": [(ax0 - 4.0, yf), (ax1 + 4.0, yf)]})

    # 每 qubit 读出腔 + 控制桩
    for r in range(rows):
        cy = y0 + r * pitch_y
        for c in range(cols):
            cx = x0 + c * pitch_x
            qid = r * cols + c
            # 读出腔：上跨 qubit 顶 pad，下邻其 row 馈线（耦合间隙）
            ry = cy + ph + readout_hh - 0.5   # 中心：底缘 = cy+ph-0.5（与 pad 重叠 0.5）
            elements.append({"kind": "boundary", "layer": FILM, "net": "readout",
                             "qubit_id": qid,
                             "rings_um": [[(cx - readout_hw, ry - readout_hh),
                                            (cx + readout_hw, ry - readout_hh),
                                            (cx + readout_hw, ry + readout_hh),
                                            (cx - readout_hw, ry + readout_hh)]]})
            # 控制桩：垂直向下桥接 qubit，落入沟道，留地间隙
            elements.append({"kind": "path", "layer": FILM, "net": "control",
                             "qubit_id": qid, "width_um": control_w,
                             "points_um": [(cx, cy), (cx, cy - control_len)]})
    return elements


# ---------------------------------------------------------------------------
# GDS / SVG 出口
# ---------------------------------------------------------------------------
def readout_gds(params: Optional[Dict] = None, path: str = "sc_readout.gds") -> bytes:
    """真出 GDSII（零依赖自写编码器）。返回文件字节。"""
    descs = readout_array_cell(params)
    recs: List[bytes] = []
    for d in descs:
        if d["kind"] == "path":
            recs.append(G.path(d["layer"], d["width_um"], d["points_um"]))
        else:
            recs.append(G.boundary(d["layer"], G._flatten_rings(d.get("rings_um"))))
    data = G.gds_library("LDA-SC-READOUT", {"sc_readout": recs})
    G.write_gds(path, data)
    return data


def readout_svg_preview(params: Optional[Dict] = None, width: int = 620) -> str:
    """版图 SVG 预览（按 net 上色：qubit=蓝 / jj=红 / coupler=橙 / readout=绿 /
    control=紫 / feedline=青 / ground=灰）。"""
    descs = readout_array_cell(params)
    net_color = {"qubit": "#2563eb", "jj": "#e11d48", "coupler": "#f59e0b",
                 "readout": "#16a34a", "control": "#7c3aed",
                 "feedline": "#0891b2", "ground": "#94a3b8"}
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
            out.append(f'<polygon points="{dd}" fill="{col}" fill-opacity="0.7"/>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------
# 几何工具
# ---------------------------------------------------------------------------
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


def _gap(a: Tuple[float, float, float, float],
         b: Tuple[float, float, float, float]) -> float:
    """两 bbox 间隙（重叠 ⇒ 0）。"""
    dx = max(a[0] - b[1], b[0] - a[1], 0.0)
    dy = max(a[2] - b[3], b[2] - a[3], 0.0)
    return float((dx * dx + dy * dy) ** 0.5)


def _near(a: Tuple[float, float, float, float],
          b: Tuple[float, float, float, float], gap: float) -> bool:
    return _gap(a, b) <= gap + 1e-9


# ---------------------------------------------------------------------------
# S4 超导几何 DRC（S3 五则 + 读出/控制四则）
# ---------------------------------------------------------------------------
def run_readout_drc(elements: List[Dict],
                    limits: Optional[Dict] = None) -> Dict:
    """S4 超导几何 DRC：S3 五则（最小线宽/JJ/地间距/短接/阵列间距）+ S4 四则
    （读出腔宽/馈线宽/控制桩宽/读出-馈线间隙/控制-地间隙）。

    返回 {verdict, violations, n_rules, limits}。verdict ∈ {ACCEPT, REJECT}。
    """
    lim = dict(DEFAULT_READOUT_LIMITS)
    if limits:
        lim.update(limits)
    min_w = float(lim["min_width_um"])
    min_jj = float(lim["min_jj_um"])
    min_gap = float(lim["min_ground_gap_um"])
    min_rw = float(lim["min_readout_width_um"])
    min_fw = float(lim["min_feedline_width_um"])
    min_cw = float(lim["min_control_width_um"])
    min_rf = float(lim["min_readout_feedline_gap_um"])
    min_cg = float(lim["min_control_ground_gap_um"])
    violations: List[Dict] = []
    checked = 0

    ground_boxes = [_bbox(d) for d in elements if d.get("net") == "ground"]

    # S3 五则：最小线宽 / JJ / 地间距(逐分量) / 短接 / 阵列间距
    for comp in _qubit_groups(elements).values():
        qbb = _bbox_of_list(comp)
        for gb in ground_boxes:
            checked += 1
            if _overlap(qbb, gb):
                violations.append({"rule": "SCD-QUBIT-GROUND-SHORT",
                                    "detail": "qubit 导体与地平面几何重叠（短接）"})
                continue
            gap = _gap(qbb, gb)
            if gap < min_gap - 1e-9:
                violations.append({"rule": "SCD-MIN-GROUND-GAP",
                                    "detail": f"qubit→地间隙 {gap:.3f} µm < {min_gap:.3f} µm"})
    qgroups = _qubit_groups(elements)
    qids = list(qgroups)
    for i in range(len(qids)):
        for j in range(i + 1, len(qids)):
            checked += 1
            if _overlap(_bbox_of_list(qgroups[qids[i]]),
                        _bbox_of_list(qgroups[qids[j]])):
                violations.append({"rule": "SCD-ARRAY-QUIBIT-SPACING",
                                    "detail": f"qubit {qids[i]} 与 {qids[j]} 导体互叠"})

    # S4 四则
    for d in elements:
        layer = d["layer"]
        if d["kind"] == "path" and layer == FILM:
            checked += 1
            w = float(d.get("width_um", 0.0))
            net = d.get("net")
            if net == "feedline" and w < min_fw - 1e-12:
                violations.append({"rule": "SCD-FEEDLINE-MIN-WIDTH",
                                    "detail": f"馈线宽 {w:.3f} µm < {min_fw:.3f} µm"})
            elif net == "control" and w < min_cw - 1e-12:
                violations.append({"rule": "SCD-CONTROL-MIN-WIDTH",
                                    "detail": f"控制桩宽 {w:.3f} µm < {min_cw:.3f} µm"})
            elif net in ("qubit", "coupler") and w < min_w - 1e-12:
                violations.append({"rule": "SCD-MIN-WIDTH",
                                    "detail": f"导体宽 {w:.3f} µm < {min_w:.3f} µm"})
        elif d["kind"] == "boundary" and layer == FILM:
            checked += 1
            thin = min(_bbox(d)[1] - _bbox(d)[0], _bbox(d)[3] - _bbox(d)[2])
            net = d.get("net")
            if net == "readout" and thin < min_rw - 1e-12:
                violations.append({"rule": "SCD-READOUT-MIN-WIDTH",
                                    "detail": f"读出腔最薄边 {thin:.3f} µm < {min_rw:.3f} µm"})
            elif net in ("qubit", "coupler") and thin < min_w - 1e-12:
                violations.append({"rule": "SCD-MIN-WIDTH",
                                    "detail": f"岛屿/耦合器最薄边 {thin:.3f} µm < {min_w:.3f} µm"})
        elif d["kind"] == "boundary" and layer == JJ:
            checked += 1
            jd = min(_bbox(d)[1] - _bbox(d)[0], _bbox(d)[3] - _bbox(d)[2])
            if jd < min_jj - 1e-12:
                violations.append({"rule": "SCD-MIN-JJ",
                                    "detail": f"JJ 最薄边 {jd:.3f} µm < {min_jj:.3f} µm"})

    # 读出腔-馈线间隙 + 控制-地间隙（专项）
    readouts = [d for d in elements if d.get("net") == "readout"]
    feedlines = [_bbox(d) for d in elements if d.get("net") == "feedline"]
    controls = [d for d in elements if d.get("net") == "control"]
    for rd in readouts:
        checked += 1
        rbb = _bbox(rd)
        if any(_overlap(rbb, fb) for fb in feedlines):
            violations.append({"rule": "SCD-READOUT-FEEDLINE-GAP",
                                "detail": "读出腔与馈线几何重叠（短接，须留耦合间隙）"})
            continue
        gmin = min((_gap(rbb, fb) for fb in feedlines), default=1e9)
        if gmin < min_rf - 1e-9:
            violations.append({"rule": "SCD-READOUT-FEEDLINE-GAP",
                                "detail": f"读出腔-馈线间隙 {gmin:.3f} µm < {min_rf:.3f} µm"})
    for cd in controls:
        checked += 1
        cbb = _bbox(cd)
        if any(_overlap(cbb, gb) for gb in ground_boxes):
            violations.append({"rule": "SCD-CONTROL-GROUND-GAP",
                                "detail": "控制桩与地平面几何重叠（短接）"})
            continue
        gmin = min((_gap(cbb, gb) for gb in ground_boxes), default=1e9)
        if gmin < min_cg - 1e-9:
            violations.append({"rule": "SCD-CONTROL-GROUND-GAP",
                                "detail": f"控制桩-地间隙 {gmin:.3f} µm < {min_cg:.3f} µm"})

    verdict = "ACCEPT" if not violations else "REJECT"
    return {"verdict": verdict, "violations": violations,
            "n_rules": len(READOUT_DRC_RULES), "limits": lim, "checked": checked}


# ---------------------------------------------------------------------------
# S4 超导几何 LVS（S3 六则 + 读出/控制连通断言）
# ---------------------------------------------------------------------------
def readout_lvs_signoff(elements: List[Dict]) -> Dict:
    """S4 几何 LVS：对**实际 produced 几何**做 bbox 重叠/邻近网表提取。

    判据：① 每导体有 net ② 存在 N 个 qubit 网（每 qubit 有 JJ 桥接 + ≥2 臂）
    ③ 每行馈线为单一 net（segment 数 == rows，未断裂）④ 每读出桥接恰好 1 qubit_id +
    邻近恰好 1 行馈线 ⑤ 每控制桥接恰好 1 qubit_id ⑥ 耦合器桥接恰好 2 qubit_id
    ⑦ 耦合图连通 ⑧ 地单一分量无短接 ⑨ 读出/控制不与地短接。
    返回 {verdict, issues, netlist, n_checks}。
    """
    issues: List[str] = []
    n_checks = 0

    cond = [(d["layer"], d.get("net", ""), _bbox(d), d.get("qubit_id"))
            for d in elements if d["kind"] in ("path", "boundary")]
    n_checks += 1
    if any(not net for (_L, net, _bb, _q) in cond):
        issues.append("SCD-LVS-NO-NET: 存在无 net 标签的导体元素")

    qgroups = _qubit_groups(elements)
    jj_elems = [d for d in elements if d["layer"] == JJ]
    couplers = [(L, net, bb, q) for (L, net, bb, q) in cond if net == "coupler"]
    readouts = [(L, net, bb, q) for (L, net, bb, q) in cond if net == "readout"]
    controls = [(L, net, bb, q) for (L, net, bb, q) in cond if net == "control"]
    feedlines = [(L, net, bb, q) for (L, net, bb, q) in cond if net == "feedline"]
    ground = [(L, net, bb, q) for (L, net, bb, q) in cond if net == "ground"]

    # ② qubit 网计数（JJ 桥接 + ≥2 臂）
    n_checks += 1
    n_qubit_found = 0
    for qid, comp in qgroups.items():
        jj_touch = any(_overlap(_bbox(jj), _bbox_of_list(comp)) for jj in jj_elems)
        arms = [d for d in comp if d["kind"] == "path"]
        if not jj_touch:
            issues.append(f"SCD-LVS-QUBIT-NO-JJ: qubit {qid} 缺 JJ 桥接")
        if len(arms) < 2:
            issues.append(f"SCD-LVS-QUBIT-PORTS: qubit {qid} 端口臂 < 2")
        else:
            n_qubit_found += 1

    # ③ 馈线：每行一条（segment 数 == rows，未断裂）
    n_checks += 1
    n_feed_seg = len(feedlines)
    expected_rows = _infer_rows(elements)
    if n_feed_seg != expected_rows:
        issues.append(f"SCD-LVS-FEEDLINE-SPLIT: 馈线 segment 数 {n_feed_seg} "
                      f"≠ 预期行数 {expected_rows}（馈线断裂/多余）")

    # ④ 读出桥接 1 qubit_id + 邻近 1 行馈线（+ 每 qubit 须有读出）
    n_checks += 1
    couple_tol = float(DEFAULT_READOUT_LIMITS["readout_feedline_couple_um"])
    feedline_bboxes = [fb for (_L2, _n2, fb, _q2) in feedlines]
    readout_qids = set()
    for (_L, _n, rbb, qid) in readouts:
        readout_qids.add(qid)
        touched_q = [q for q, comp in qgroups.items()
                     if _overlap(rbb, _bbox_of_list(comp))]
        overlap_f = any(_overlap(rbb, fb) for fb in feedline_bboxes)
        near_f = [fb for fb in feedline_bboxes
                  if _near(rbb, fb, couple_tol)]
        if overlap_f:
            issues.append(f"SCD-LVS-READOUT-FEEDLINE-SHORT: 读出腔与馈线几何重叠"
                          f"（短接，qubit_id={qid}）")
        elif len(touched_q) != 1:
            issues.append(f"SCD-LVS-READOUT-BRIDGE-Q: 读出桥接 {len(touched_q)} 个 qubit"
                          f"（须恰好 1，qubit_id={qid}）")
        elif len(near_f) != 1:
            issues.append(f"SCD-LVS-READOUT-BRIDGE-F: 读出邻近 {len(near_f)} 条馈线"
                          f"（须恰好 1，qubit_id={qid}）")
    for qid in qgroups:
        if qid not in readout_qids:
            issues.append(f"SCD-LVS-QUBIT-NO-READOUT: qubit {qid} 缺读出谐振腔")

    # ⑤ 控制桥接恰好 1 qubit_id（+ 每 qubit 须有控制）
    n_checks += 1
    control_qids = set()
    for (_L, _n, cbb, qid) in controls:
        control_qids.add(qid)
        touched_q = [q for q, comp in qgroups.items()
                     if _overlap(cbb, _bbox_of_list(comp))]
        if len(touched_q) != 1:
            issues.append(f"SCD-LVS-CONTROL-BRIDGE-Q: 控制桥接 {len(touched_q)} 个 qubit"
                          f"（须恰好 1，qubit_id={qid}）")
    for qid in qgroups:
        if qid not in control_qids:
            issues.append(f"SCD-LVS-QUBIT-NO-CONTROL: qubit {qid} 缺控制桩")

    # ⑥ 耦合器桥接恰好 2 qubit_id
    n_checks += 1
    edges = []
    for (_L, _n, cbb, _q) in couplers:
        touched = [q for q, comp in qgroups.items()
                   if _overlap(cbb, _bbox_of_list(comp))]
        if len(touched) != 2:
            issues.append(f"SCD-LVS-COUPLER-BRIDGE-NE2: 耦合器桥接 {len(touched)} 个 qubit"
                          f"（须恰好 2）")
        else:
            edges.append(tuple(sorted(touched)))

    # ⑦ 耦合图连通
    n_checks += 1
    qid_list = sorted(qgroups.keys())
    n_qubit = len(qid_list)
    remap = {q: i for i, q in enumerate(qid_list)}
    parent = list(range(n_qubit))

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
    if n_qubit > 1:
        if not edges:
            issues.append("SCD-LVS-NO-COUPLER: 多 qubit 阵列缺耦合元件（未连通）")
        if len(comps_graph) > 1:
            issues.append(f"SCD-LVS-FLOATING-QUBIT: 耦合图分成 {len(comps_graph)} "
                          "个孤立分量")

    # ⑧ 地单一分量无短接
    n_checks += 1
    gcomps = SA._ground_components(elements)
    if len(gcomps) != 1:
        issues.append(f"SCD-LVS-GROUND-SPLIT: 地平面分成 {len(gcomps)} 个分量")
    qubit_boxes = [_bbox(d) for d in elements if d.get("net") == "qubit"]
    short = any(_overlap(qb, gb) for qb in qubit_boxes for (_L, _n, gb, _q) in ground)
    if short:
        issues.append("SCD-LVS-QUBIT-GROUND-SHORT: 导体与地平面重叠（短接）")

    # ⑨ 读出/控制不与地短接
    n_checks += 1
    ro_short = any(_overlap(rbb, gb) for (_L, _n, rbb, _q) in readouts
                   for (_L2, _n2, gb, _q2) in ground)
    ct_short = any(_overlap(cbb, gb) for (_L, _n, cbb, _q) in controls
                   for (_L2, _n2, gb, _q2) in ground)
    if ro_short:
        issues.append("SCD-LVS-READOUT-GROUND-SHORT: 读出腔与地短接")
    if ct_short:
        issues.append("SCD-LVS-CONTROL-GROUND-SHORT: 控制桩与地短接")

    verdict = "ACCEPT" if not issues else "REJECT"
    return {"verdict": verdict, "issues": issues,
            "netlist": {"qubit_nets": n_qubit_found,
                        "feedline_segments": n_feed_seg,
                        "readout": len(readouts),
                        "control": len(controls),
                        "coupler": len(couplers),
                        "ground_nets": len(gcomps),
                        "edges_bridged": len(edges)},
            "n_checks": n_checks}


def _infer_rows(elements: List[Dict]) -> int:
    """从 qubit group 的 y 坐标推断行数（供 LVS 馈线 segment 数比对）。"""
    qgroups = _qubit_groups(elements)
    ys = set()
    for comp in qgroups.values():
        bb = _bbox_of_list(comp)
        ys.add(round((bb[2] + bb[3]) / 2.0, 6))
    return len(ys)


# ---------------------------------------------------------------------------
# 串扰预算（全 pair ZZ + 控制线串扰）
# ---------------------------------------------------------------------------
def _array_topology(params: Optional[Dict] = None) -> Tuple[Dict[int, Tuple[float, float]],
                                                            List[Tuple[int, int]]]:
    """返回 (positions: qid→(cx,cy), edges: 最近邻拓扑边)。复用 S3 拓扑。"""
    p = dict(params or {})
    rows = int(p.get("rows", 2))
    cols = int(p.get("cols", 2))
    pitch_x = float(p.get("pitch_x", 22.0))
    pitch_y = float(p.get("pitch_y", 14.0))
    x0 = -(cols - 1) * pitch_x / 2.0
    y0 = -(rows - 1) * pitch_y / 2.0
    pos: Dict[int, Tuple[float, float]] = {}
    for r in range(rows):
        for c in range(cols):
            pos[r * cols + c] = (x0 + c * pitch_x, y0 + r * pitch_y)
    edges: List[Tuple[int, int]] = []
    for r in range(rows):
        for c in range(cols - 1):
            edges.append((r * cols + c, r * cols + c + 1))
    for r in range(rows - 1):
        for c in range(cols):
            edges.append((r * cols + c, (r + 1) * cols + c))
    return pos, edges


def crosstalk_budget(params: Optional[Dict] = None) -> Dict:
    """全 pair 串扰预算。

    方法（闭式 + 几何，方法学独立）：
      • 最近邻边 J：coupler_solver 严格对角化↔解析闭式（与 S3 同口径，确定性锚）。
      • 非最近邻背景 J_bg：几何电容 1/d³ 标度 J_bg(d)=J_nn·(pitch/d)³（设计估计）。
      • 全 pair 静态 ZZ 率：ζ_zz=2J²α/(Δ(Δ+α))（Blais 2004 二阶微扰，MHz），
        α=−E_C·1000，Δ=(f_j−f_i)·1000。
      • 控制线串扰：相邻控制桩平行段 fringe 电容 C_x=ε_eff·ε0·Lc·t/gap → X=C_x/C_q。
    返回：全 pair ζ_zz 矩阵、最近邻 ZZ、最大杂散 ZZ、控制串扰、验收 verdict。
    """
    p = dict(params or {})
    rows = int(p.get("rows", 2))
    cols = int(p.get("cols", 2))
    N = rows * cols
    ec = float(p.get("E_C", 0.25))
    ej_list = p.get("EJ_list") or [18.0 + 0.3 * i for i in range(N)]
    ej_list = [float(x) for x in ej_list]
    alpha_mhz = -ec * 1000.0

    pos, edges = _array_topology(p)
    pitch = float(p.get("pitch_x", 22.0))

    # 最近邻 J（确定性锚）
    j_nn = {}
    for (a, b) in edges:
        sol = CS.solve_coupler(ej_list[a], ec, ej_list[b], ec,
                               float(p.get("Cc", 0.007)), 1.0, 1.0)
        j_nn[(a, b)] = float(sol["J_num"])
    import statistics as _st
    j_nn_rep = float(_st.median(j_nn.values())) if j_nn else 0.012

    # 全 pair ζ_zz（规模优化：f01/位置/边集**预计算**，逐对只做算术 —— 行为等价）
    f01_mhz = [CS.koch_f01(ej, ec) * 1000.0 for ej in ej_list]
    xs = [pos[i][0] for i in range(N)]
    ys = [pos[i][1] for i in range(N)]
    es = set(tuple(sorted(e)) for e in edges)
    jnn_get = j_nn.get
    zz_matrix: List[Dict] = []
    stray_zz: List[float] = []
    nn_zz: List[float] = []
    pitch3 = pitch ** 3.0
    for i in range(N):
        xi = xs[i]
        yi = ys[i]
        fi_mhz = f01_mhz[i]
        for j in range(i + 1, N):
            dx = xi - xs[j]
            dy = yi - ys[j]
            d = math.sqrt(dx * dx + dy * dy)
            nearest = (i, j) in es
            if nearest:
                J = jnn_get((i, j), j_nn_rep)
            else:
                J = j_nn_rep * pitch3 / (d ** 3.0)     # 背景耦合 1/d³ 标度
            delta_mhz = f01_mhz[j] - fi_mhz
            J_mhz = J * 1000.0                        # J 转 MHz（与 α/Δ 同口径）
            denom = alpha_mhz * alpha_mhz - delta_mhz * delta_mhz
            if abs(denom) < 1e-12:
                zeta = 0.0
            else:
                zeta = 2.0 * J_mhz * J_mhz * alpha_mhz / denom    # MHz（ζ_zz=2J²α/(α²−Δ²)）
            zz_matrix.append({"pair": [i, j], "d_um": float(d), "J_ghz": J,
                              "delta_mhz": float(delta_mhz), "zz_mhz": float(zeta),
                              "nearest": nearest})
            if nearest:
                nn_zz.append(abs(zeta))
            else:
                stray_zz.append(abs(zeta))

    max_stray = float(max(stray_zz)) if stray_zz else 0.0
    max_nn = float(max(nn_zz)) if nn_zz else 0.0

    # 控制线串扰（相邻控制桩平行段）
    xtalk = _control_xtalk(params, pos)
    max_xt = float(max((x["X"] for x in xtalk), default=0.0))

    stray_ok = bool(max_stray <= ZZ_STRAY_LIMIT_MHZ)
    xt_ok = bool(max_xt <= CONTROL_XTALK_LIMIT)
    verdict = "ACCEPT" if (stray_ok and xt_ok) else "REJECT"
    return {
        "verdict": verdict,
        "n_qubits": N, "n_pairs": len(zz_matrix),
        "alpha_mhz": alpha_mhz,
        "j_nn_rep_ghz": j_nn_rep,
        "max_stray_zz_mhz": max_stray,
        "max_nearest_zz_mhz": max_nn,
        "zz_stray_limit_mhz": ZZ_STRAY_LIMIT_MHZ,
        "max_control_xtalk": max_xt,
        "control_xtalk_limit": CONTROL_XTALK_LIMIT,
        "pair_zz": zz_matrix,
        "control_xtalk": xtalk,
        "stray_zz_ok": stray_ok, "control_xtalk_ok": xt_ok,
        "note": ("全 pair 静态 ZZ 用二阶微扰 ζ_zz=2J²α/(Δ(Δ+α))（Blais 2004 色散，"
                 "golden 闭式）；非最近邻 J_bg 用几何 1/d³ 标度（设计估计）。控制串扰用"
                 "平行段 fringe 电容闭式 X=C_x/C_q（设计估计）。LLM 不进判决路径。"),
    }


def _control_xtalk(params: Optional[Dict],
                   pos: Dict[int, Tuple[float, float]]) -> List[Dict]:
    """相邻控制桩串扰：平行段 fringe 电容 C_x = ε_eff·ε0·Lc·t/gap → X=C_x/C_q。"""
    p = dict(params or {})
    rows = int(p.get("rows", 2))
    cols = int(p.get("cols", 2))
    control_len = float(p.get("control_len", 4.0))
    eps_eff = float(p.get("eps_eff", 6.0))
    t_film = float(p.get("t_film_um", 0.05))
    C_q = float(p.get("C_q_fF", 50.0))
    eps0 = 8.854e-12
    out: List[Dict] = []
    # 同行相邻列控制桩：x 间距 = pitch_x − (2·控制覆盖长度)
    pitch_x = float(p.get("pitch_x", 22.0))
    # 控制桩覆盖：从 qubit 中心向 -control_len 延伸（见 readout_array_cell）
    cover = control_len
    for r in range(rows):
        for c in range(cols - 1):
            gap = pitch_x - 2.0 * cover      # 两相邻桩平行线间距（几何）
            if gap <= 0:
                X = 1.0                      # 重叠 ⇒ 强串扰（判 REJECT）
            else:
                Lc = control_len
                C_x = eps_eff * eps0 * (Lc * 1e-6) * (t_film * 1e-6) / (gap * 1e-6)
                X = C_x / (C_q * 1e-15)
            out.append({"pair": [r * cols + c, r * cols + c + 1],
                        "gap_um": float(gap), "X": float(X)})
    return out


# ---------------------------------------------------------------------------
# 损耗预算（per-qubit：参与比 + Purcell + 辐射）
# ---------------------------------------------------------------------------
def loss_budget(params: Optional[Dict] = None) -> Dict:
    """per-qubit 损耗预算（Barends/Marinis 参与比 + Purcell，闭式 golden）。

    1/T1_internal = ω·Σ tanδ_i·p_i       （几何定参与比 p_i；ω=2π f_q）
    γ_Purcell = κ·g²/Δ²                   （D-88 闭式，g=读出耦合，Δ=f_r−f_q）
    1/T1_total = 1/T1_internal + 1/T1_purcell + 1/T1_radiative
    f_r/κ/g/tanδ_i/p_i 为设计参数（非 golden）；公式为确定性物理定律。
    验收：每 qubit T1_total ≥ T1_TARGET 且 T1_purcell ≥ T1_TARGET（Purcell 保护）。
    """
    p = dict(params or {})
    rows = int(p.get("rows", 2))
    cols = int(p.get("cols", 2))
    N = rows * cols
    ec = float(p.get("E_C", 0.25))
    ej_list = p.get("EJ_list") or [18.0 + 0.3 * i for i in range(N)]
    ej_list = [float(x) for x in ej_list]

    # 设计参数（材料 + 几何参与比 + 读出）—— 取良好 AlOx/硅基 transmon 量级
    f_r = float(p.get("f_r_ghz", 4.8))
    kappa = float(p.get("kappa_ghz", 0.003))
    g_rq = float(p.get("g_rq_ghz", 0.05))
    tan_d_s = float(p.get("tan_delta_surface", 1e-6))
    tan_d_sub = float(p.get("tan_delta_substrate", 3e-7))
    tan_d_rad = float(p.get("tan_delta_radiative", 5e-7))
    p_s = float(p.get("p_surface", 0.1))
    p_sub = float(p.get("p_substrate", 0.9))
    p_rad = float(p.get("p_radiative", 0.0))

    per_qubit: List[Dict] = []
    all_ok = True
    for q in range(N):
        f_q = float(CS.koch_f01(ej_list[q], ec))
        omega = 2.0 * math.pi * f_q * 1e9            # rad/s
        inv_t1_int = omega * (tan_d_s * p_s + tan_d_sub * p_sub)
        delta = f_r - f_q                              # 色散失谐（GHz）
        gamma_p = kappa * g_rq * g_rq / (delta * delta)   # GHz（Purcell 率 Γ_P=κ(g/Δ)²）
        inv_t1_purcell = gamma_p * 1e9                  # 1/s（Γ_P[Hz]=γ_P[GHz]·1e9）
        inv_t1_rad = omega * (tan_d_rad * p_rad) if p_rad > 0 else 0.0
        inv_total = inv_t1_int + inv_t1_purcell + inv_t1_rad
        t1_int_us = (1e6 / inv_t1_int) if inv_t1_int > 0 else float("inf")
        t1_purcell_us = (1e6 / inv_t1_purcell) if inv_t1_purcell > 0 else float("inf")
        t1_total_us = (1e6 / inv_total) if inv_total > 0 else float("inf")
        ok = bool(t1_total_us >= T1_TARGET_US and t1_purcell_us >= T1_TARGET_US)
        all_ok = all_ok and ok
        per_qubit.append({
            "qubit": q, "f01_ghz": f_q, "f_r_ghz": f_r,
            "delta_ghz": float(delta),
            "t1_internal_us": (None if t1_int_us == float("inf") else float(t1_int_us)),
            "t1_purcell_us": (None if t1_purcell_us == float("inf") else float(t1_purcell_us)),
            "t1_total_us": (None if t1_total_us == float("inf") else float(t1_total_us)),
            "ok": ok,
        })

    min_t1 = float(min((q["t1_total_us"] for q in per_qubit
                        if q["t1_total_us"] is not None), default=0.0))
    verdict = "ACCEPT" if all_ok else "REJECT"
    return {
        "verdict": verdict,
        "n_qubits": N,
        "t1_target_us": T1_TARGET_US,
        "kappa_ghz": kappa, "g_rq_ghz": g_rq, "f_r_ghz": f_r,
        "tan_delta_surface": tan_d_s, "tan_delta_substrate": tan_d_sub,
        "p_surface": p_s, "p_substrate": p_sub,
        "min_t1_total_us": min_t1,
        "per_qubit": per_qubit,
        "note": ("per-qubit 损耗 = Barends 参与比 1/T1=ω·Σtanδ_i·p_i + Purcell "
                 "γ_P=κg²/Δ²（D-88 闭式）。f_r/κ/g/tanδ_i/p_i 为设计参数（非 golden）；"
                 "公式为确定性物理定律。LLM 不进判决路径。"),
    }


# ---------------------------------------------------------------------------
# 综合物理签核（串扰 + 损耗）
# ---------------------------------------------------------------------------
def readout_physics(params: Optional[Dict] = None) -> Dict:
    """S4 物理签核 = 串扰预算 + 损耗预算 双 ACCEPT。"""
    xt = crosstalk_budget(params)
    lb = loss_budget(params)
    verdict = "ACCEPT" if (xt["verdict"] == "ACCEPT"
                           and lb["verdict"] == "ACCEPT") else "REJECT"
    return {
        "verdict": verdict,
        "crosstalk": xt,
        "loss": lb,
        "note": "S4 物理签核 = 串扰预算（全 pair ZZ + 控制串扰）+ 损耗预算（per-qubit "
                "参与比 + Purcell）双 ACCEPT。",
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

    cell = readout_array_cell({"rows": 2, "cols": 2})
    chk("① 合法 2×2 读出阵列 DRC ACCEPT", run_readout_drc(cell)["verdict"] == "ACCEPT")
    chk("② 合法 2×2 读出阵列 LVS ACCEPT（4 qubit·2 馈线·4 读出·4 控制·连通）",
        readout_lvs_signoff(cell)["verdict"] == "ACCEPT")

    # 读出腔太薄 ⇒ DRC REJECT
    thin = readout_array_cell({"rows": 1, "cols": 2, "readout_hw": 0.1})
    vtr = run_readout_drc(thin)
    chk("③ 读出腔太薄 ⇒ DRC REJECT（SCD-READOUT-MIN-WIDTH）",
        vtr["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-READOUT-MIN-WIDTH" for v in vtr["violations"]))

    # 读出腔与馈线短接（重叠） ⇒ DRC + LVS REJECT
    short = readout_array_cell({"rows": 1, "cols": 2, "readout_hh": 4.0})
    vsr = run_readout_drc(short)
    vsrl = readout_lvs_signoff(short)
    chk("④ 读出-馈线短接 ⇒ DRC REJECT（SCD-READOUT-FEEDLINE-GAP）",
        vsr["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-READOUT-FEEDLINE-GAP" for v in vsr["violations"]))
    chk("⑤ 读出-馈线短接 ⇒ LVS REJECT（READOUT-FEEDLINE-SHORT）",
        vsrl["verdict"] == "REJECT"
        and any("READOUT-FEEDLINE-SHORT" in i for i in vsrl["issues"]))

    # 控制桩与地短接 ⇒ DRC + LVS REJECT
    cshort = readout_array_cell({"rows": 1, "cols": 2, "control_len": 20.0})
    vcs = run_readout_drc(cshort)
    vcsl = readout_lvs_signoff(cshort)
    chk("⑥ 控制桩过长穿地 ⇒ DRC REJECT（SCD-CONTROL-GROUND-GAP）",
        vcs["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-CONTROL-GROUND-GAP" for v in vcs["violations"]))
    chk("⑦ 控制桩穿地 ⇒ LVS REJECT（CONTROL-GROUND-SHORT）",
        vcsl["verdict"] == "REJECT"
        and any("CONTROL-GROUND-SHORT" in i for i in vcsl["issues"]))

    # 缺读出（每 qubit 无 readout）⇒ LVS REJECT
    noread = [d for d in cell if d.get("net") != "readout"]
    vnr = readout_lvs_signoff(noread)
    chk("⑧ 缺读出 ⇒ LVS REJECT（QUBIT-NO-READOUT）",
        vnr["verdict"] == "REJECT"
        and any("QUBIT-NO-READOUT" in i for i in vnr["issues"]))

    # 馈线断裂（一分为二）⇒ LVS REJECT
    broken = list(cell)
    # 把第 0 条馈线切成两段（中间留 1µm 缝）
    feeds = [i for i, d in enumerate(broken) if d.get("net") == "feedline"]
    if feeds:
        fi = feeds[0]
        pts = broken[fi]["points_um"]
        (xa, ya), (xb, yb) = pts[0], pts[1]
        xm = (xa + xb) / 2.0
        broken[fi]["points_um"] = [(xa, ya), (xm - 0.5, yb)]
        broken.append({"kind": "path", "layer": FILM, "net": "feedline",
                        "qubit_id": None, "width_um": broken[fi]["width_um"],
                        "points_um": [(xm + 0.5, yb), (xb, yb)]})
    vfb = readout_lvs_signoff(broken)
    chk("⑨ 馈线断裂（一分为二）⇒ LVS REJECT（FEEDLINE-SPLIT）",
        vfb["verdict"] == "REJECT"
        and any("FEEDLINE-SPLIT" in i for i in vfb["issues"]))

    # 杂散 ZZ 过高（强耦合 Cc ⇒ 背景耦合 J_bg 大 ⇒ 对角对 ζ_zz 超限）⇒ 串扰 REJECT
    xt_bad = crosstalk_budget({"rows": 2, "cols": 2, "Cc": 0.1})
    chk("⑩ 强耦合 Cc ⇒ 杂散 ZZ 超限 ⇒ 串扰 REJECT",
        xt_bad["verdict"] == "REJECT"
        and xt_bad["max_stray_zz_mhz"] > ZZ_STRAY_LIMIT_MHZ)

    # 损耗不足（高 tanδ ⇒ T1 过低）⇒ 损耗 REJECT
    lb_bad = loss_budget({"rows": 2, "cols": 2,
                          "tan_delta_surface": 5e-4, "p_surface": 0.5})
    chk("⑪ 高 tanδ ⇒ T1 不足 ⇒ 损耗 REJECT",
        lb_bad["verdict"] == "REJECT"
        and lb_bad["min_t1_total_us"] < T1_TARGET_US)

    # 综合物理 ACCEPT（合法 2×2）
    phys = readout_physics({"rows": 2, "cols": 2})
    chk("⑫ 合法 2×2 物理 ACCEPT（串扰 + 损耗双 ACCEPT）",
        phys["verdict"] == "ACCEPT")

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok
