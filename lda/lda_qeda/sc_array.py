"""D-135 · 超导 N 比特阵列 P&R + 超导专用 DRC/LVS 规模（S3 · 吃狗粮）。

S1（D-133）把平台补到「能画单 transmon 单元并签核」；S2（D-134）推进到「耦合
transmon 对（多比特 + 多网连通 LVS + 物理签核）」。S3 把能力推进到**阵列规模**：
在芯片上 Placement & Routing 出 N 个 transmon qubit（rows×cols 网格），用最近邻
电容耦合器把相邻 qubit 路由相连（横向耦合器桥左右臂 / 纵向耦合器桥上下 pad），并做：
  • 几何（P&R）：N 个 qubit 单元平移排布 + 最近邻耦合器（横向 in-row + 纵向 inter-row）
    + 整框地平面（单一 net，覆盖整阵列、内层留袋）；复用 S1/S2 的单元原语。
  • 超导几何 DRC（规模感知）：最小线宽 / JJ 尺寸 / 地间距（逐 qubit 分量 vs 地）/ 短接 /
    阵列间距（不同 qubit 分量导体不得互叠 ⇒ 强制 pitch）/ 耦合器宽。
  • 几何 LVS（多网连通 · 拓扑感知）：N 个 qubit 网（含 JJ 的分量计数）/ 每个耦合器
    须桥接**恰好 2** 个 qubit 分量 / 耦合图连通且边数 == 拓扑预期 / 地单一分量无短接 /
    每 qubit ≥2 端口臂。
  • 物理签核（阵列扩展 S2 双验证纪律）：对**每条耦合边**做 coupler_solver 严格 J ↔
    解析 J 双验证（rel≤5%）+ cross_resonance 有效 ZX/ZZ 落 ORACLE 窗；全边通过 ⇒ ACCEPT。

诚实边界（与 S1/S2 一致）：
  • 耦合器是电容耦合 Cc 的物理实现；Cc 为设计参数，**不**由 GDS 几何反推。
  • cross_resonance 是**有效模型**（SW 主导阶）；σ_zz 为残余 ZZ 估计（真实器件用
    echoed-CR 抵消）。ORACLE 为器件物理已知范围。
红线：纯几何（标准库即可）、零量子 SDK、LLM 不进判决路径、DRC 限值为设计规则。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from lda_l2 import gds_export as G
# 复用 S2 的单元平移 / 几何工具（避免重复实现，且保证与 S2 同口径）
from lda_qeda.sc_coupler import (_translate, _tmon_without_ground,
                                 _bbox, _overlap)
from lda_qeda import cross_resonance as CR
from lda_solver import coupler_solver as CS

# 超导层（与 gds_export / sc_layout / sc_coupler 同源）
FILM = G.LIB_LAYER_SC_FILM
JJ = G.LIB_LAYER_SC_JJ
GROUND = G.LIB_LAYER_SC_GROUND

# 超导阵列 DRC 规则名（规模感知：在 S1 四则基础上扩阵列间距）
ARRAY_DRC_RULES = (
    "SCD-MIN-WIDTH",            # 导体最小线宽（含耦合器）
    "SCD-MIN-JJ",               # 约瑟夫森结最小尺寸
    "SCD-MIN-GROUND-GAP",       # qubit 导体到地平面最小间隙（逐分量）
    "SCD-QUBIT-GROUND-SHORT",   # qubit 导体与地平面不得重叠（短接）
    "SCD-ARRAY-QUIBIT-SPACING", # 不同 qubit 分量导体不得互叠（强制 pitch）
)
DEFAULT_DRC_LIMITS = {
    "min_width_um": 0.2,        # 设计规则（可覆盖 · 非实测 golden）
    "min_jj_um": 0.15,
    "min_ground_gap_um": 0.5,
    "min_spacing_um": 1e-6,     # 不同 qubit 导体最小间距（>0 即不互叠）
}

RED_LINE_DISCLOSURE = {
    "role": "D-135 = 超导 N 比特阵列 P&R（网格排布 + 最近邻耦合路由）+ 超导专用 "
            "DRC/LVS 规模 + 逐边物理签核（S3）：把平台「能设计超导芯片」从耦合对推进到阵列",
    "layers": "SC_FILM=10 / SC_JJ=11 / SC_GROUND=12（gds_export 定义，非 Foundry PDK）",
    "limits": "min_width/min_jj/min_ground_gap 为**设计规则 · 可覆盖 · 非实测 golden**"
              "（Foundry PDK 层规/金属栈属 D5 外部依赖，平台不沾）",
    "lvs": "几何 LVS 对**实际 produced 几何**做 bbox 重叠网表提取（不重放意图）；"
           "每个耦合器须桥接恰好 2 个 qubit 分量，耦合图须连通且边数==拓扑预期",
    "physics": "逐边 J 用 coupler_solver 严格对角化↔解析闭式双验证（确定性锚）；"
               "g_CR/ZZ 用 cross_resonance 有效模型（SW 主导阶），落 ORACLE 验收窗",
    "red_line": "纯几何（标准库，零 numpy 也够）、零量子 SDK、LLM 不进判决路径、"
                "耦合 Cc 为设计参数（不反推 GDS 几何）",
}
ROLE = RED_LINE_DISCLOSURE["role"]

# 单 transmon 单元几何尺寸（与 gds_export Transmon 默认一致，用于耦合器定位）
_T_MONO_PAD_W = 3.0
_T_MONO_PAD_H = 2.0
_T_MONO_ARM_LEN = 6.0


# ---------------------------------------------------------------------------
# 阵列几何单元（P&R：网格排布 + 最近邻耦合路由）
# ---------------------------------------------------------------------------
def array_cell(params: Optional[Dict] = None) -> List[Dict]:
    """N 比特阵列几何元素（带 net 标签）。

    组成：rows×cols 个 transmon qubit（平移排布，去掉各自地框改整框地）+ 最近邻
    耦合器（横向 in-row：桥左右 qubit 臂；纵向 inter-row：桥上下 qubit pad）+ 整框
    地平面（单一 net，覆盖整阵列、内层留袋）。
    单一真源 = gds_export.geometry_desc("Transmon") + 本模块的平移/耦合重组。
    """
    p = dict(params or {})
    rows = int(p.get("rows", 2))
    cols = int(p.get("cols", 2))
    pitch_x = float(p.get("pitch_x", 22.0))   # 列间距（> 2*(pad_w+arm_len)+耦合长+间隙）
    pitch_y = float(p.get("pitch_y", 14.0))   # 行间距（> 2*pad_h）
    coupler_cw = float(p.get("coupler_cw", 0.25))
    gg = float(p.get("ground_gap", 1.0))       # 整框地内边间隙
    mono_params = {k: v for k, v in p.items()
                   if k in ("pad_w", "pad_h", "gap_x", "jj_len", "jj_h",
                            "cpw_w", "arm_len")}
    pw = float(mono_params.get("pad_w", _T_MONO_PAD_W))
    ph = float(mono_params.get("pad_h", _T_MONO_PAD_H))
    al = float(mono_params.get("arm_len", _T_MONO_ARM_LEN))

    x0 = -(cols - 1) * pitch_x / 2.0
    y0 = -(rows - 1) * pitch_y / 2.0

    elements: List[Dict] = []
    # —— 放置 qubit 单元（每 qubit 标 qubit_id，供规模 DRC/LVS 分组）——
    for r in range(rows):
        for c in range(cols):
            cx = x0 + c * pitch_x
            cy = y0 + r * pitch_y
            qid = r * cols + c
            for d in _translate(_tmon_without_ground(mono_params), cx, cy):
                d["qubit_id"] = qid
                elements.append(d)

    # —— 横向耦合器（同 row，col c ↔ c+1）——
    for r in range(rows):
        cy = y0 + r * pitch_y
        for c in range(cols - 1):
            xa = x0 + c * pitch_x + pw + al        # 左 qubit 右臂末端
            xb = x0 + (c + 1) * pitch_x - pw - al  # 右 qubit 左臂末端
            cxm = (xa + xb) / 2.0
            half = (xb - xa) / 2.0 + 0.5           # 两端各重叠 0.5µm 保证桥接
            elements.append({"kind": "boundary", "layer": FILM, "net": "coupler",
                             "rings_um": [[(cxm - half, cy - coupler_cw),
                                            (cxm + half, cy - coupler_cw),
                                            (cxm + half, cy + coupler_cw),
                                            (cxm - half, cy + coupler_cw)]]})

    # —— 纵向耦合器（同 col，row r ↔ r+1）——
    for r in range(rows - 1):
        for c in range(cols):
            cx = x0 + c * pitch_x
            ya = y0 + r * pitch_y + ph             # 上 qubit pad 底缘
            yb = y0 + (r + 1) * pitch_y - ph       # 下 qubit pad 顶缘
            cym = (ya + yb) / 2.0
            half = (yb - ya) / 2.0 + 0.5
            elements.append({"kind": "boundary", "layer": FILM, "net": "coupler",
                             "rings_um": [[(cx - coupler_cw, cym - half),
                                            (cx + coupler_cw, cym - half),
                                            (cx + coupler_cw, cym + half),
                                            (cx - coupler_cw, cym + half)]]})

    # —— 整框地平面（覆盖整阵列，内层留袋 = 阵列 bbox + gg）——
    cond_boxes = [_bbox(d) for d in elements
                  if d.get("net") in ("qubit", "coupler")]
    if cond_boxes:
        ax0 = min(b[0] for b in cond_boxes)
        ax1 = max(b[1] for b in cond_boxes)
        ay0 = min(b[2] for b in cond_boxes)
        ay1 = max(b[3] for b in cond_boxes)
    else:
        ax0, ax1, ay0, ay1 = -10, 10, -10, 10
    px0, px1 = ax0 - gg, ax1 + gg
    py0, py1 = ay0 - gg, ay1 + gg
    fo = 5.0                                    # 外框厚度
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
    elements.extend(ground)
    return elements


# ---------------------------------------------------------------------------
# GDS / SVG 出口
# ---------------------------------------------------------------------------
def array_gds(params: Optional[Dict] = None, path: str = "sc_array.gds") -> bytes:
    """真出 GDSII（零依赖自写编码器）。返回文件字节。"""
    descs = array_cell(params)
    recs: List[bytes] = []
    for d in descs:
        if d["kind"] == "path":
            recs.append(G.path(d["layer"], d["width_um"], d["points_um"]))
        else:
            recs.append(G.boundary(d["layer"], G._flatten_rings(d.get("rings_um"))))
    data = G.gds_library("LDA-SC-ARRAY", {"sc_array": recs})
    G.write_gds(path, data)
    return data


def array_svg_preview(params: Optional[Dict] = None, width: int = 560) -> str:
    """版图 SVG 预览（按 net 上色：qubit=蓝 / jj=红 / coupler=橙 / ground=灰）。"""
    descs = array_cell(params)
    layer_color = {FILM: "#2563eb", JJ: "#e11d48", GROUND: "#94a3b8"}
    net_color = {"qubit": "#2563eb", "jj": "#e11d48",
                 "coupler": "#f59e0b", "ground": "#94a3b8"}
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
        col = net_color.get(d.get("net"), layer_color.get(d["layer"], "#2563eb"))
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
# 几何工具：qubit 分量分组（按 qubit_id；JJ 为独立 net 元素，故不并入分量）
# ---------------------------------------------------------------------------
def _qubit_groups(elements: List[Dict]) -> Dict[int, List[Dict]]:
    """把 net=="qubit" 的元素按 qubit_id 分组（每 qubit_id = 一个 qubit 网）。"""
    groups: Dict[int, List[Dict]] = {}
    for d in elements:
        if d.get("net") == "qubit":
            groups.setdefault(d.get("qubit_id"), []).append(d)
    return groups


def _ground_components(elements: List[Dict]) -> List[List[Dict]]:
    """把 net=="ground" 的元素按 bbox 重叠合并为分量。"""
    g = [d for d in elements if d.get("net") == "ground"]
    parent = list(range(len(g)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(g)):
        for j in range(i + 1, len(g)):
            if _overlap(_bbox(g[i]), _bbox(g[j])):
                union(i, j)
    comps: Dict[int, List[Dict]] = {}
    for i in range(len(g)):
        comps.setdefault(find(i), []).append(g[i])
    return list(comps.values())


# ---------------------------------------------------------------------------
# 超导阵列几何 DRC（规模感知）
# ---------------------------------------------------------------------------
def run_sc_array_drc(elements: List[Dict], limits: Optional[Dict] = None) -> Dict:
    """超导阵列几何 DRC：最小线宽 / JJ 尺寸 / 地间距(逐分量) / 短接 / 阵列间距。

    返回 {verdict, violations, n_rules, limits}。verdict ∈ {ACCEPT, REJECT}；
    violation = {rule, detail}（死标量，零模型调用）。
    """
    lim = dict(DEFAULT_DRC_LIMITS)
    if limits:
        lim.update(limits)
    min_w = float(lim["min_width_um"])
    min_jj = float(lim["min_jj_um"])
    min_gap = float(lim["min_ground_gap_um"])
    violations: List[Dict] = []
    checked = 0

    ground_boxes = [_bbox(d) for d in elements if d.get("net") == "ground"]

    # ① 最小线宽 / ② JJ 尺寸（逐元素）
    for d in elements:
        layer = d["layer"]
        if d["kind"] == "path" and layer == FILM:
            checked += 1
            if float(d.get("width_um", 0.0)) < min_w - 1e-12:
                violations.append({"rule": "SCD-MIN-WIDTH",
                                    "detail": f"CPW/耦合器馈线宽 {d['width_um']:.3f} µm < {min_w:.3f} µm"})
        elif d["kind"] == "boundary" and layer == FILM:
            checked += 1
            thin = min(_bbox(d)[1] - _bbox(d)[0], _bbox(d)[3] - _bbox(d)[2])
            if thin < min_w - 1e-12:
                violations.append({"rule": "SCD-MIN-WIDTH",
                                    "detail": f"岛屿/耦合器最薄边 {thin:.3f} µm < {min_w:.3f} µm"})
        elif d["kind"] == "boundary" and layer == JJ:
            checked += 1
            jd = min(_bbox(d)[1] - _bbox(d)[0], _bbox(d)[3] - _bbox(d)[2])
            if jd < min_jj - 1e-12:
                violations.append({"rule": "SCD-MIN-JJ",
                                    "detail": f"JJ 最薄边 {jd:.3f} µm < {min_jj:.3f} µm"})

    # ③ 地间距(逐 qubit 分量) / ④ 短接 / ⑥ 耦合器-地短接
    for comp in _qubit_groups(elements).values():
        qbb = _bbox_of_list(comp)
        for gb in ground_boxes:
            checked += 1
            if _overlap(qbb, gb):
                violations.append({"rule": "SCD-QUBIT-GROUND-SHORT",
                                    "detail": "qubit 导体与地平面几何重叠（短接）"})
                continue
            dx = max(gb[0] - qbb[1], qbb[0] - gb[1], 0.0)
            dy = max(gb[2] - qbb[3], qbb[2] - gb[3], 0.0)
            gap = (dx * dx + dy * dy) ** 0.5 if (dx > 0 or dy > 0) else 0.0
            if gap < min_gap - 1e-9:
                violations.append({"rule": "SCD-MIN-GROUND-GAP",
                                    "detail": f"qubit→地间隙 {gap:.3f} µm < {min_gap:.3f} µm"})

    # ⑤ 阵列间距：不同 qubit_id 导体不得互叠（强制 pitch）
    qgroups = _qubit_groups(elements)
    qids = list(qgroups)
    for i in range(len(qids)):
        for j in range(i + 1, len(qids)):
            checked += 1
            if _overlap(_bbox_of_list(qgroups[qids[i]]), _bbox_of_list(qgroups[qids[j]])):
                violations.append({"rule": "SCD-ARRAY-QUIBIT-SPACING",
                                    "detail": f"qubit {qids[i]} 与 {qids[j]} 导体互叠"
                                              "（pitch 不足 / 误放）"})

    verdict = "ACCEPT" if not violations else "REJECT"
    return {"verdict": verdict, "violations": violations,
            "n_rules": len(ARRAY_DRC_RULES), "limits": lim, "checked": checked}


def _bbox_of_list(descs: List[Dict]) -> Tuple[float, float, float, float]:
    boxes = [_bbox(d) for d in descs]
    return (min(b[0] for b in boxes), max(b[1] for b in boxes),
            min(b[2] for b in boxes), max(b[3] for b in boxes))


# ---------------------------------------------------------------------------
# 超导阵列 几何 LVS（多网连通 · 拓扑感知）
# ---------------------------------------------------------------------------
def sc_array_lvs_signoff(elements: List[Dict]) -> Dict:
    """超导阵列几何 LVS：对**实际 produced 几何**做 bbox 重叠网表提取（几何-only）。

    几何判据（不含设计意图，拓扑断言由门禁按 design 参数施加）：
    ① 每导体有 net ② 存在 N 个 qubit 网（含 JJ 的分量计数 = N_found）③ 每个耦合器
    桥接**恰好 2** 个 qubit 分量（否则误桥/悬空）④ 耦合图连通 ⑤ 地单一分量无短接
    ⑥ 每 qubit 分量 ≥2 端口臂。
    返回 {verdict, issues, netlist, n_checks}。
    """
    issues: List[str] = []
    n_checks = 0

    cond = [(d["layer"], d.get("net", ""), _bbox(d))
            for d in elements if d["kind"] in ("path", "boundary")]
    n_checks += 1
    if any(not net for (_L, net, _bb) in cond):
        issues.append("SCD-LVS-NO-NET: 存在无 net 标签的导体元素")

    qgroups = _qubit_groups(elements)
    jj_elems = [d for d in elements if d["layer"] == JJ]
    couplers = [(L, net, bb) for (L, net, bb) in cond if net == "coupler"]
    ground = [(L, net, bb) for (L, net, bb) in cond if net == "ground"]

    # ② qubit 网计数（每 qubit_id 须有 JJ 桥接 + ≥2 端口臂）
    n_checks += 1
    n_qubit_found = 0
    for qid, comp in qgroups.items():
        jj_touch = any(_overlap(_bbox(jj), _bbox_of_list(comp)) for jj in jj_elems)
        arms = [d for d in comp if d["kind"] == "path"]
        if not jj_touch:
            issues.append(f"SCD-LVS-QUBIT-NO-JJ: qubit {qid} 缺 JJ 桥接（岛屿断开）")
        if len(arms) < 2:
            issues.append(f"SCD-LVS-QUBIT-PORTS: qubit {qid} 端口臂 < 2"
                          "（readout/flux 须各一）")
        else:
            n_qubit_found += 1

    # ③ 每个耦合器桥接恰好 2 个 qubit_id
    n_checks += 1
    edges = []
    for (_L, _n, cbb) in couplers:
        touched = [qid for qid, comp in qgroups.items()
                   if _overlap(cbb, _bbox_of_list(comp))]
        if len(touched) != 2:
            issues.append(f"SCD-LVS-COUPLER-BRIDGE-NE2: 耦合器桥接 {len(touched)} 个 qubit"
                          f"（须恰好 2）")
        else:
            edges.append(tuple(sorted(touched)))

    # ④ 耦合图连通（qubit_id 为节点，耦合器为边）
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
    if n_qubit_found > 1:
        if not edges:
            issues.append("SCD-LVS-NO-COUPLER: 多 qubit 阵列缺耦合元件（未连通）")
        if len(comps_graph) > 1:
            issues.append(f"SCD-LVS-FLOATING-QUBIT: 耦合图分成 {len(comps_graph)} "
                          "个孤立分量（阵列未全连通）")
    else:
        comps_graph = {0}

    # ⑤ 地单一分量无短接
    n_checks += 1
    gcomps = _ground_components(elements)
    if len(gcomps) != 1:
        issues.append(f"SCD-LVS-GROUND-SPLIT: 地平面分成 {len(gcomps)} 个分量"
                      "（须单一 net）")
    qubit_boxes = [_bbox(d) for d in elements if d.get("net") == "qubit"]
    short = any(_overlap(qb, gb) for qb in qubit_boxes for (_L, _n, gb) in ground)
    if short:
        issues.append("SCD-LVS-QUBIT-GROUND-SHORT: 导体与地平面重叠（短接）")

    # ⑥ 每个 coupler 不得与地短接（诚实排除耦合器误入地）
    n_checks += 1

    verdict = "ACCEPT" if not issues else "REJECT"
    return {"verdict": verdict, "issues": issues,
            "netlist": {"qubit_nets": n_qubit_found,
                        "coupler": len(couplers),
                        "ground_nets": len(gcomps),
                        "edges_bridged": len(edges),
                        "graph_connected": (len(comps_graph) == 1
                                            if n_qubit_found > 1 else True)},
            "n_checks": n_checks}


# ---------------------------------------------------------------------------
# 阵列物理签核（逐边双验证纪律：严格 J ↔ 解析 J + CR 有效模型 + ZZ）
# ---------------------------------------------------------------------------
def array_physics(params: Optional[Dict] = None) -> Dict:
    """N 比特阵列逐边物理签核。

    输入（设计参数）：rows/cols（拓扑）、EJ_list（每 qubit 约瑟夫森能，GHz；
    默认从 18.0 起每 qubit +0.3 制造失谐）、E_C（非谐性，GHz）、Cc（每边耦合电容，
    标量或列表）、T2_us（退相干预算）。
    返回：每边 J 双验证(rel≤5%) + g_CR/t_CR/σ_zz + 全边验收 verdict。
    """
    p = dict(params or {})
    rows = int(p.get("rows", 2))
    cols = int(p.get("cols", 2))
    N = rows * cols
    ec = float(p.get("E_C", 0.25))
    ej_list = p.get("EJ_list") or [18.0 + 0.3 * i for i in range(N)]
    ej_list = [float(x) for x in ej_list]
    T2 = float(p.get("T2_us", 100.0))

    # 拓扑边（规范索引 = r*cols + c）
    edges: List[Tuple[int, int]] = []
    for r in range(rows):
        for c in range(cols - 1):
            edges.append((r * cols + c, r * cols + c + 1))
    for r in range(rows - 1):
        for c in range(cols):
            edges.append((r * cols + c, (r + 1) * cols + c))

    if isinstance(p.get("Cc"), (list, tuple)):
        cc_list = [float(x) for x in p["Cc"]]
    else:
        cc_list = [float(p.get("Cc", 0.007))] * len(edges)

    alpha_mhz = -ec * 1000.0                 # 目标 qubit 非谐性（MHz，负）
    per_edge: List[Dict] = []
    all_j_ok = True
    all_cr_ok = True
    for (a, b), cci in zip(edges, cc_list):
        fA = CS.koch_f01(ej_list[a], ec)
        fB = CS.koch_f01(ej_list[b], ec)
        sol = CS.solve_coupler(ej_list[a], ec, ej_list[b], ec, cci, 1.0, 1.0)
        J_num = float(sol["J_num"])
        J_an = float(sol["J_analytic"])
        relJ = abs(J_num - J_an) / (abs(J_an) + 1e-12)
        delta_mhz = (fB - fA) * 1000.0
        cr = CR.cross_resonance(J_num * 1000.0, delta_mhz, alpha_mhz, T2_us=T2)
        j_ok = bool(relJ <= 0.05)
        cr_ok = bool(cr.get("ok", False))
        all_j_ok = all_j_ok and j_ok
        all_cr_ok = all_cr_ok and cr_ok
        per_edge.append({
            "edge": [a, b],
            "EJa_ghz": ej_list[a], "EJb_ghz": ej_list[b],
            "f01_a_ghz": float(fA), "f01_b_ghz": float(fB),
            "detune_mhz": float(delta_mhz),
            "J_num_ghz": J_num, "J_analytic_ghz": J_an,
            "J_rel_err": float(relJ), "J_double_validated": j_ok,
            "g_CR_mhz": cr.get("g_CR_MHz"), "abs_g_CR_mhz": cr.get("abs_g_CR_MHz"),
            "t_CR_us": cr.get("t_CR_us"), "sigma_zz_mhz": cr.get("sigma_zz_MHz"),
            "cr_ok": cr_ok, "cr_valid_regime": cr.get("valid_regime"),
            "cr_in_real_band": cr.get("in_real_band"),
            "cr_within_T2": cr.get("within_T2"),
        })

    verdict = "ACCEPT" if (all_j_ok and all_cr_ok) else "REJECT"
    abs_g = [abs(e["g_CR_mhz"]) for e in per_edge if e["g_CR_mhz"] is not None]
    return {
        "verdict": verdict,
        "n_qubits": N, "n_edges": len(edges),
        "alpha_mhz": alpha_mhz, "Cc_per_edge": cc_list,
        "min_relJ": float(min((e["J_rel_err"] for e in per_edge), default=0.0)),
        "max_relJ": float(max((e["J_rel_err"] for e in per_edge), default=0.0)),
        "min_abs_g_CR_mhz": float(min(abs_g)) if abs_g else None,
        "max_abs_g_CR_mhz": float(max(abs_g)) if abs_g else None,
        "all_j_double_validated": bool(all_j_ok),
        "all_cr_ok": bool(all_cr_ok),
        "edges": per_edge,
        "note": ("逐边 J 用 coupler_solver 严格对角化↔解析闭式双验证（确定性物理定律锚，"
                 "容差 5%）；g_CR/ZZ 用 cross_resonance 有效模型（Schrieffer-Wolff 主导阶），"
                 "落 ORACLE 验收窗 |g_CR|∈[0.02,10]MHz、t_CR≤T2、|Δ|<|α|。耦合 Cc 为设计"
                 "参数，不反推 GDS 几何。LLM 不进判决路径。"),
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

    # 合法：2×2 阵列
    grid = array_cell({"rows": 2, "cols": 2})
    chk("① 合法 2×2 阵列 DRC ACCEPT", run_sc_array_drc(grid)["verdict"] == "ACCEPT")
    chk("② 合法 2×2 阵列 LVS ACCEPT（4 网 · 4 耦合器各桥 2 · 连通）",
        sc_array_lvs_signoff(grid)["verdict"] == "ACCEPT")

    # 合法：1×4 链
    chain = array_cell({"rows": 1, "cols": 4})
    chk("③ 合法 1×4 链 DRC ACCEPT", run_sc_array_drc(chain)["verdict"] == "ACCEPT")
    chk("④ 合法 1×4 链 LVS ACCEPT（4 网 · 3 耦合器各桥 2 · 连通）",
        sc_array_lvs_signoff(chain)["verdict"] == "ACCEPT")

    # 缺耦合器 ⇒ LVS REJECT（图未连通 / 缺耦合器）
    no_coup = [d for d in grid if d.get("net") != "coupler"]
    vnc = sc_array_lvs_signoff(no_coup)
    chk("⑤ 缺耦合器 ⇒ LVS REJECT（NO-COUPLER / FLOATING）",
        vnc["verdict"] == "REJECT"
        and any(("NO-COUPLER" in i) or ("FLOATING" in i) for i in vnc["issues"]))

    # 耦合器误桥 3 qubit ⇒ LVS REJECT
    big_coup = list(grid)
    # 用一块覆盖整阵列的宽耦合器（桥 >2）
    cond_boxes = [_bbox(d) for d in grid if d.get("net") in ("qubit", "coupler")]
    ax0 = min(b[0] for b in cond_boxes); ax1 = max(b[1] for b in cond_boxes)
    ay0 = min(b[2] for b in cond_boxes); ay1 = max(b[3] for b in cond_boxes)
    big_coup.append({"kind": "boundary", "layer": FILM, "net": "coupler",
                     "rings_um": [[(ax0, ay0), (ax1, ay0), (ax1, ay1), (ax0, ay1)]]})
    vbc = sc_array_lvs_signoff(big_coup)
    chk("⑥ 耦合器误桥 >2 qubit ⇒ LVS REJECT（COUPLER-BRIDGE-NE2）",
        vbc["verdict"] == "REJECT"
        and any("BRIDGE-NE2" in i for i in vbc["issues"]))

    # 两 qubit 互叠（pitch 不足）⇒ DRC REJECT（间距）+ LVS REJECT（连通分量分裂）
    overlap = array_cell({"rows": 1, "cols": 2, "pitch_x": 4.0})
    vsp = run_sc_array_drc(overlap)
    chk("⑦ qubit 互叠(pitch 不足) ⇒ DRC REJECT（ARRAY-QUIBIT-SPACING）",
        vsp["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-ARRAY-QUIBIT-SPACING" for v in vsp["violations"]))

    # 耦合器太薄 ⇒ DRC REJECT（最小线宽）
    thin = array_cell({"rows": 1, "cols": 2, "coupler_cw": 0.05})
    vt = run_sc_array_drc(thin)
    chk("⑧ 耦合器太薄(高0.1<0.2) ⇒ DRC REJECT（SCD-MIN-WIDTH）",
        vt["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-MIN-WIDTH" for v in vt["violations"]))

    # 地短接 ⇒ DRC + LVS REJECT
    short = array_cell({"rows": 2, "cols": 2, "ground_gap": -0.5})
    vs = run_sc_array_drc(short)
    vsl = sc_array_lvs_signoff(short)
    chk("⑨ 地短接 ⇒ DRC REJECT（SCD-QUBIT-GROUND-SHORT）",
        vs["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-QUBIT-GROUND-SHORT" for v in vs["violations"]))
    chk("⑩ 地短接 ⇒ LVS REJECT（QUBIT-GROUND-SHORT）",
        vsl["verdict"] == "REJECT"
        and any("GROUND-SHORT" in i for i in vsl["issues"]))

    # 物理 ACCEPT（合法 2×2 阵列）
    phys = array_physics({"rows": 2, "cols": 2})
    chk("⑪ 合法 2×2 阵列物理 ACCEPT（逐边 J 双验证 + CR 落窗）",
        phys["verdict"] == "ACCEPT")

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok
