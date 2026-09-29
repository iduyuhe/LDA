"""D-145 · 超导征程 S5 第三波（完善）：**统一拓扑 DRC/LVS 框架**（方阵 + heavy-hex 共用）。

背景：S3（D-135）的**方阵** P&R 与 S5 P1（D-138）的 **heavy-hex** P&R 各自带一套
DRC/LVS，规则名与实现口径分叉（`SCD-ARRAY-QUIBIT-SPACING` vs `SCD-HEAVYHEX-*`）。
本模块把「拓扑」抽出来做成**一个抽象 + 一个引擎**：

  · **拓扑抽象**（纯数据）：`{positions, kind, couplers, adjacency, max_degree_limit, meta}`
    - `grid_topology(rows, cols)`      方阵：节点 = rows×cols qubit，耦合 = 最近邻（度 ≤ 4）
    - `heavy_hex_topology(rows, cols)` 蜂窝两子格 + 边中点，耦合 = 顶点—中点（度 ≤ 3）
  · **共用引擎**（方阵与 heavy-hex 走**同一份**代码）：
    - `topology_degree_stats` / `topology_cell`（P&R）
    - `run_topology_drc`（S1 四则 + `SCD-TOPO-NODE-SPACING` + `SCD-TOPO-MAX-DEGREE`）
    - `topology_lvs`（复用 S2 多网连通 + `SCD-LVS-TOPO-COUPLER-COUNT`）
    - `topology_physics`（逐耦合 J 双验证 + CR 落窗）
    - `topology_gds` / `topology_svg_preview`

关键设计：**最大度上限由拓扑自己声明**（grid=4 / heavy-hex=3）——引擎不写死「必须 ≤3」，
而是按 `topo["max_degree_limit"]` 判，从而同一份 DRC 能同时服务两种拓扑。

诚实边界（与 S1–S4 一致）：
  · 耦合器几何为**中心连线**旋转矩形（单元级示意；Cc 为设计参数，不由几何反推）。
  · 逐耦合 J 双验证只在相邻 qubit 近共振区可分辨（与 S2/G3 同口径）。
  · 本框架是 S3 方阵 / S5 P1 heavy-hex 的**拓扑与签核层**统一；S3 的 `array_cell`（带
    qubit_id 分组 + 阵列专用地框）与 S4 的读出/控制语义**保持不变**（非破坏性重构）。
红线：纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、限值为设计规则。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from lda_l2 import gds_export as G
from lda_qeda import sc_layout as SCD
from lda_qeda.sc_coupler import (_bbox, _overlap, _translate,
                                 _tmon_without_ground, sc_pair_lvs_signoff)
from lda_solver import coupler_solver as CS
from lda_qeda import cross_resonance as CR

FILM = G.LIB_LAYER_SC_FILM
JJ = G.LIB_LAYER_SC_JJ
GROUND = G.LIB_LAYER_SC_GROUND

DEFAULT_GRID_PITCH_X = 22.0
DEFAULT_GRID_PITCH_Y = 14.0
DEFAULT_HEX_UNIT = 56.0

GRID_MAX_DEGREE = 4          # 方阵内部节点度上界
HEAVYHEX_MAX_DEGREE = 3      # heavy-hex 定义式上界（无 4 邻居）

DEFAULT_TOPO_LIMITS = dict(SCD.DEFAULT_DRC_LIMITS)
DEFAULT_TOPO_LIMITS.update({
    "min_node_spacing_um": 0.5,    # 相邻节点 qubit 导体最小间隙
    "coupler_width_um": 0.5,
})
# 统一规则集：S1 四则（线宽/JJ/地间距/短接）+ 拓扑两则
TOPOLOGY_DRC_RULES = tuple(list(SCD.SCD_RULES) + [
    "SCD-TOPO-NODE-SPACING",   # 不同节点 qubit 导体不得互叠（方阵与 heavy-hex 共用）
    "SCD-TOPO-MAX-DEGREE",     # 拓扑最大度 ≤ 该拓扑声明的上限（grid 4 / hex 3）
])

RED_LINE_DISCLOSURE = {
    "role": "D-145 = 超导征程 S5 第三波（完善）：统一拓扑 DRC/LVS 框架 —— 方阵（S3/D-135）"
            "与 heavy-hex（S5 P1/D-138）走同一份拓扑抽象 + 同一份 DRC/LVS/物理引擎",
    "layers": "SC_FILM=10 / SC_JJ=11 / SC_GROUND=12（gds_export 定义，非 Foundry PDK）",
    "limits": "min_node_spacing / coupler_width 为**设计规则 · 可覆盖 · 非实测 golden**"
              "（Foundry PDK 属 D5 外部依赖）",
    "lvs": "复用 S2 多网连通 LVS（对**实际 produced 几何**做 bbox 网表提取）+ 耦合计数与拓扑一致",
    "physics": "逐耦合 J 用 coupler_solver 严格对角化↔解析闭式双验证 + cross_resonance 有效"
               "模型落 ORACLE 窗（与 S2/S3 同口径）",
    "topology": "拓扑抽象 = 节点位置/类型 + 耦合对 + 邻接 + **自声明最大度上限**；"
                "grid maxDeg=4 · heavy-hex maxDeg=3；引擎按声明判，不写死",
    "red_line": "纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、"
                "耦合器为中心连线矩形（单元级示意）",
}
ROLE = RED_LINE_DISCLOSURE["role"]


# ---------------------------------------------------------------------------
# 拓扑抽象（纯数据）
# ---------------------------------------------------------------------------
def _finalize(name: str, positions: Dict[int, Tuple[float, float]],
              kind: Dict[int, str], pairs: List[Tuple[int, int]],
              max_degree_limit: int, extra: Optional[Dict] = None) -> Dict:
    """由 (位置, 类型, 耦合对) 构造统一拓扑字典（邻接/度数/计数由引擎算）。"""
    adj: Dict[int, List[int]] = {n: [] for n in positions}
    seen = set()
    couplers: List[Tuple[int, int]] = []
    for (a, b) in pairs:
        key = (a, b) if a < b else (b, a)
        if key in seen:
            continue
        seen.add(key)
        couplers.append(key)
        adj[a].append(b)
        adj[b].append(a)
    topo = {"name": name, "positions": positions, "kind": kind,
            "couplers": couplers, "adjacency": adj,
            "max_degree_limit": int(max_degree_limit),
            "n_qubits": len(positions), "n_couplings": len(couplers)}
    if extra:
        topo.update(extra)
    return topo


def grid_topology(rows: int = 3, cols: int = 3,
                  pitch_x: float = DEFAULT_GRID_PITCH_X,
                  pitch_y: float = DEFAULT_GRID_PITCH_Y) -> Dict:
    """方阵拓扑：rows×cols qubit，耦合 = 最近邻（横向 in-row + 纵向 inter-row）。

    与 S3 `array_cell` 同一拓扑（节点数 rows·cols；耦合数 rows(cols−1)+cols(rows−1)）。
    度：内部 4 / 边 3 / 角 2 ⇒ max_degree_limit = 4。
    """
    rows, cols = int(rows), int(cols)
    x0 = -(cols - 1) * pitch_x / 2.0
    y0 = -(rows - 1) * pitch_y / 2.0
    positions: Dict[int, Tuple[float, float]] = {}
    kind: Dict[int, str] = {}
    for r in range(rows):
        for c in range(cols):
            nid = r * cols + c
            positions[nid] = (x0 + c * pitch_x, y0 + r * pitch_y)
            kind[nid] = "vertex"
    pairs: List[Tuple[int, int]] = []
    for r in range(rows):
        for c in range(cols - 1):
            pairs.append((r * cols + c, r * cols + c + 1))
    for r in range(rows - 1):
        for c in range(cols):
            pairs.append((r * cols + c, (r + 1) * cols + c))
    return _finalize("grid", positions, kind, pairs, GRID_MAX_DEGREE,
                     {"rows": rows, "cols": cols,
                      "pitch_x": float(pitch_x), "pitch_y": float(pitch_y),
                      "n_vertices": rows * cols, "n_edge_qubits": 0})


def heavy_hex_topology(rows: int = 3, cols: int = 3,
                       unit_um: float = DEFAULT_HEX_UNIT) -> Dict:
    """heavy-hex 拓扑：蜂窝两子格 A/B（各度 3）+ 每条边中点 qubit ⇒ 度 ≤ 3。

    A(i,j) = i·(3/2,√3/2)·U + j·(3/2,−√3/2)·U   B(i,j) = A(i,j) + (U, 0)
    A(i,j) 邻接 B(i,j) / B(i−1,j) / B(i,j−1)。每条蜂窝边插入中点 qubit（度 2）。
    与 S5 P1 `sc_topology.heavy_hex_graph` 同源（同一实现）。
    """
    rows, cols = int(rows), int(cols)
    sx, sy = 1.5 * unit_um, (math.sqrt(3.0) / 2.0) * unit_um

    def _A(i: int, j: int) -> Tuple[float, float]:
        return (sx * (i + j), sy * (i - j))

    xs = [sx * (i + j) for i in range(rows) for j in range(cols)]
    ys = [sy * (i - j) for i in range(rows) for j in range(cols)]
    xc, yc = 0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys))

    positions: Dict[int, Tuple[float, float]] = {}
    kind: Dict[int, str] = {}
    aid: Dict[Tuple[int, int], int] = {}
    bid: Dict[Tuple[int, int], int] = {}
    n = 0
    for i in range(rows):
        for j in range(cols):
            ax, ay = _A(i, j)
            aid[(i, j)] = n
            positions[n] = (ax - xc, ay - yc)
            kind[n] = "vertex"
            n += 1
    for i in range(rows):
        for j in range(cols):
            ax, ay = _A(i, j)
            bid[(i, j)] = n
            positions[n] = (ax + unit_um - xc, ay - yc)
            kind[n] = "vertex"
            n += 1
    n_v = n

    honey: List[Tuple[int, int]] = []
    seen = set()

    def _add(a: int, b: int):
        key = (min(a, b), max(a, b))
        if key not in seen:
            seen.add(key)
            honey.append(key)

    for i in range(rows):
        for j in range(cols):
            _add(aid[(i, j)], bid[(i, j)])
            if i - 1 >= 0:
                _add(aid[(i, j)], bid[(i - 1, j)])
            if j - 1 >= 0:
                _add(aid[(i, j)], bid[(i, j - 1)])

    # 每条蜂窝边插入中点 qubit；耦合拆成 (顶点—中点) 与 (中点—顶点)
    pairs: List[Tuple[int, int]] = []
    edges: List[Tuple[int, int, int]] = []
    for k, (a, b) in enumerate(honey):
        eid = n_v + k
        pa, pb = positions[a], positions[b]
        positions[eid] = ((pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0)
        kind[eid] = "edge"
        edges.append((eid, a, b))
        pairs.append((a, eid))
        pairs.append((eid, b))

    return _finalize("heavy-hex", positions, kind, pairs, HEAVYHEX_MAX_DEGREE,
                     {"rows": rows, "cols": cols, "unit_um": float(unit_um),
                      "edges": edges, "n_vertices": n_v, "n_edge_qubits": len(edges),
                      "n_edges": 2 * len(edges)})


def topology_degree_stats(topo: Dict) -> Dict:
    """度分布 + **是否满足该拓扑自声明的最大度上限**。"""
    adj = topo["adjacency"]
    deg = {n: len(v) for n, v in adj.items()}
    hist: Dict[int, int] = {}
    for d in deg.values():
        hist[d] = hist.get(d, 0) + 1
    lim = int(topo["max_degree_limit"])
    v_deg = [deg[n] for n in topo["kind"] if topo["kind"][n] == "vertex"]
    e_deg = [deg[n] for n in topo["kind"] if topo["kind"][n] == "edge"]
    return {"histogram": hist, "max_degree": max(deg.values()) if deg else 0,
            "max_degree_limit": lim,
            "within_limit": bool(all(d <= lim for d in deg.values())),
            "no_four_neighbor": bool(all(d <= HEAVYHEX_MAX_DEGREE for d in deg.values())),
            "vertex_deg_max": max(v_deg) if v_deg else 0,
            "edge_deg_max": max(e_deg) if e_deg else 0}


# ---------------------------------------------------------------------------
# P&R（方阵与 heavy-hex 共用）
# ---------------------------------------------------------------------------
def _bar_polygon(p1: Tuple[float, float], p2: Tuple[float, float],
                 w: float) -> Optional[List[Tuple[float, float]]]:
    """两点连线的旋转矩形四角（中心连线耦合器）。"""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return None
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    h = w / 2.0
    return [(p1[0] + nx * h, p1[1] + ny * h), (p2[0] + nx * h, p2[1] + ny * h),
            (p2[0] - nx * h, p2[1] - ny * h), (p1[0] - nx * h, p1[1] - ny * h)]


def topology_cell(topo: Dict, params: Optional[Dict] = None) -> List[Dict]:
    """统一 P&R：每个节点一只 transmon + 每个耦合对一根棒状耦合器 + 整框地。"""
    p = dict(params or {})
    cw = float(p.get("coupler_width", DEFAULT_TOPO_LIMITS["coupler_width_um"]))
    gg = float(p.get("ground_gap", 1.0))
    mono_params = {k: v for k, v in p.items()
                   if k in ("pad_w", "pad_h", "gap_x", "jj_len", "jj_h",
                            "cpw_w", "arm_len")}

    body: List[Dict] = []
    for nid, (x, y) in topo["positions"].items():
        body += _translate(_tmon_without_ground(mono_params), x, y)
    for (u, v) in topo["couplers"]:
        poly = _bar_polygon(topo["positions"][u], topo["positions"][v], cw)
        if poly:
            body.append({"kind": "boundary", "layer": FILM, "net": "coupler",
                         "rings_um": [poly]})

    boxes = [_bbox(d) for d in body]
    px = max(max(abs(b[0]), abs(b[1])) for b in boxes) + gg
    py = max(max(abs(b[2]), abs(b[3])) for b in boxes) + gg
    co = max(px, py) + 15.0
    ground = [
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(-co, py), (co, py), (co, co), (-co, co)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(-co, -py), (co, -py), (co, -co), (-co, -co)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(-co, -py), (-px, -py), (-px, py), (-co, py)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(px, -py), (co, -py), (co, py), (px, py)]]},
    ]
    return body + ground


def topology_gds(topo: Dict, params: Optional[Dict] = None,
                 path: str = "sc_topology.gds") -> bytes:
    """真出 GDSII（零依赖自写编码器）。返回文件字节。"""
    descs = topology_cell(topo, params)
    recs: List[bytes] = []
    for d in descs:
        if d["kind"] == "path":
            recs.append(G.path(d["layer"], d["width_um"], d["points_um"]))
        else:
            recs.append(G.boundary(d["layer"], G._flatten_rings(d.get("rings_um"))))
    data = G.gds_library("LDA-SC-TOPO", {topo["name"]: recs})
    G.write_gds(path, data)
    return data


def topology_svg_preview(topo: Dict, params: Optional[Dict] = None,
                         width: int = 620) -> str:
    """版图 SVG 预览（qubit=蓝 / jj=红 / coupler=橙 / ground=灰）。"""
    descs = topology_cell(topo, params)
    net_color = {"qubit": "#2563eb", "jj": "#e11d48", "coupler": "#f59e0b",
                 "ground": "#e2e8f0"}
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
    X = lambda x: pad + (x - xmin) * S        # noqa: E731
    Y = lambda y: pad + (ymax - y) * S        # noqa: E731
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
# DRC / LVS / 物理（方阵与 heavy-hex 共用同一份代码）
# ---------------------------------------------------------------------------
def run_topology_drc(elements: List[Dict], topo: Dict,
                     limits: Optional[Dict] = None) -> Dict:
    """统一拓扑 DRC = S1 四则 + SCD-TOPO-NODE-SPACING + SCD-TOPO-MAX-DEGREE。"""
    lim = dict(DEFAULT_TOPO_LIMITS)
    if limits:
        lim.update(limits)
    base = SCD.run_sc_drc(elements, lim)
    violations = list(base["violations"])

    # SCD-TOPO-NODE-SPACING：不同**节点**的 qubit 导体不得互叠（同节点内 pad/臂互叠是设计）
    node_boxes: Dict[int, List[Tuple[float, float, float, float]]] = {}
    for d in elements:
        if d.get("net") != "qubit":
            continue
        bb = _bbox(d)
        cx, cy = (bb[0] + bb[1]) / 2.0, (bb[2] + bb[3]) / 2.0
        nid = min(topo["positions"],
                  key=lambda n: (topo["positions"][n][0] - cx) ** 2
                  + (topo["positions"][n][1] - cy) ** 2)
        node_boxes.setdefault(nid, []).append(bb)
    group_bb = {nid: (min(b[0] for b in v), max(b[1] for b in v),
                      min(b[2] for b in v), max(b[3] for b in v))
                for nid, v in node_boxes.items()}
    keys = list(group_bb)
    overlaps = 0
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if _overlap(group_bb[keys[i]], group_bb[keys[j]]):
                overlaps += 1
    if overlaps:
        violations.append({"rule": "SCD-TOPO-NODE-SPACING",
                           "detail": f"{overlaps} 对节点 qubit 导体互叠（节点间距不足）"})

    # SCD-TOPO-MAX-DEGREE：最大度 ≤ 该拓扑自声明上限（grid 4 / heavy-hex 3）
    deg = topology_degree_stats(topo)
    if not deg["within_limit"]:
        violations.append({"rule": "SCD-TOPO-MAX-DEGREE",
                           "detail": f"最大度={deg['max_degree']}"
                                     f">{topo['max_degree_limit']}（{topo['name']}）"})

    verdict = "ACCEPT" if not violations else "REJECT"
    return {"verdict": verdict, "violations": violations,
            "n_rules": len(TOPOLOGY_DRC_RULES), "limits": lim,
            "topology": topo["name"], "max_degree": deg["max_degree"],
            "max_degree_limit": topo["max_degree_limit"], "qubit_overlaps": overlaps}


def topology_lvs(elements: List[Dict], topo: Dict) -> Dict:
    """统一拓扑 LVS = 复用 S2 多网连通 LVS + 耦合计数与拓扑一致。"""
    base = sc_pair_lvs_signoff(elements)
    issues = list(base["issues"])
    n_checks = base["n_checks"] + 1

    n_coupler = len([d for d in elements if d.get("net") == "coupler"])
    if n_coupler != topo["n_couplings"]:
        issues.append(f"SCD-LVS-TOPO-COUPLER-COUNT: 耦合器={n_coupler}"
                      f"≠拓扑耦合数={topo['n_couplings']}（{topo['name']}）")

    verdict = "ACCEPT" if not issues else "REJECT"
    return {"verdict": verdict, "issues": issues,
            "netlist": dict(base["netlist"], topology=topo["name"],
                            n_nodes=topo["n_qubits"], n_couplers=n_coupler),
            "n_checks": n_checks}


def topology_physics(topo: Dict, params: Optional[Dict] = None) -> Dict:
    """统一拓扑物理签核：逐耦合 J 双验证 + CR 有效模型落窗。"""
    p = dict(params or {})
    ec = float(p.get("E_C", 0.25))
    ej_c = float(p.get("E_J_vertex", 18.0))
    ej_e = float(p.get("E_J_edge", 19.3))
    cc = float(p.get("Cc", 0.007))
    max_couplers = int(p.get("max_physics_couplers", 64))

    delta = CS.koch_f01(ej_e, ec) - CS.koch_f01(ej_c, ec)
    alpha = -ec
    per: List[Dict] = []
    max_rel = 0.0
    for i, (_u, _v) in enumerate(topo["couplers"][:max_couplers]):
        sol = CS.solve_coupler(ej_c, ec, ej_e, ec, cc, 1.0, 1.0)
        j_num = float(sol["J_num"])
        j_an = float(sol["J_analytic"])
        rel = abs(j_num - j_an) / (abs(j_an) + 1e-15)
        max_rel = max(max_rel, rel)
        cr = CR.cross_resonance(j_num * 1000.0, delta * 1000.0, alpha * 1000.0)
        per.append({"coupler": i, "J_num_ghz": j_num, "J_rel_err": float(rel),
                    "g_CR_mhz": cr.get("g_CR_MHz"), "cr_ok": bool(cr.get("ok", False))})
    j_ok = bool(max_rel <= 0.05)
    cr_ok = bool(all(e["cr_ok"] for e in per)) if per else False
    verdict = "ACCEPT" if (j_ok and cr_ok) else "REJECT"
    return {"verdict": verdict, "topology": topo["name"], "n_couplers": len(per),
            "max_J_rel_err": float(max_rel), "J_double_validated": j_ok,
            "cr_all_ok": cr_ok, "detune_ghz": float(delta),
            "g_CR_mhz": per[0]["g_CR_mhz"] if per else None, "couplers": per,
            "note": "逐耦合 J 用 coupler_solver 严格↔解析双验证（容差 5%）+ CR 有效模型落窗"
                    "（与 S2/S3 同口径）。Cc/E_J 为设计参数，不由几何反推。LLM 不进判决路径。"}


# ---------------------------------------------------------------------------
# 自检（方阵 + heavy-hex 双拓扑）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    ok = True
    msgs: List[Tuple[str, bool]] = []

    def chk(name, cond, detail=None):
        nonlocal ok
        ok = ok and bool(cond)
        msgs.append((name, bool(cond)))

    g = grid_topology(3, 3)
    h = heavy_hex_topology(3, 3)
    dg, dh = topology_degree_stats(g), topology_degree_stats(h)

    chk("① 方阵 3×3：9 节点 · 12 耦合 · 度上限 4（内部 4/边 3/角 2）",
        g["n_qubits"] == 9 and g["n_couplings"] == 12
        and g["max_degree_limit"] == GRID_MAX_DEGREE and dg["max_degree"] == 4
        and dg["within_limit"], f"N={g['n_qubits']} E={g['n_couplings']} "
                               f"maxDeg={dg['max_degree']}")
    chk("② heavy-hex 3×3：18 顶点 + 21 边 qubit = 39 qubit · 42 耦合 · 度 ≤3",
        h["n_vertices"] == 18 and h["n_edge_qubits"] == 21 and h["n_qubits"] == 39
        and h["n_couplings"] == 42 and dh["max_degree"] <= HEAVYHEX_MAX_DEGREE
        and dh["no_four_neighbor"] and dh["vertex_deg_max"] == 3
        and dh["edge_deg_max"] == 2, f"N={h['n_qubits']} maxDeg={dh['max_degree']}")
    chk("③ 方阵与 heavy-hex **度上限由拓扑自声明**（4 vs 3）",
        g["max_degree_limit"] == 4 and h["max_degree_limit"] == 3)

    # 同一份 DRC/LVS/物理引擎跑两种拓扑
    cg, ch = topology_cell(g), topology_cell(h)
    chk("④ **统一 DRC** 对方阵与 heavy-hex 均 ACCEPT",
        run_topology_drc(cg, g)["verdict"] == "ACCEPT"
        and run_topology_drc(ch, h)["verdict"] == "ACCEPT")
    chk("⑤ **统一 LVS** 对方阵与 heavy-hex 均 ACCEPT",
        topology_lvs(cg, g)["verdict"] == "ACCEPT"
        and topology_lvs(ch, h)["verdict"] == "ACCEPT")
    chk("⑥ **统一物理**（逐耦合 J 双验证 + CR 落窗）对两者均 ACCEPT",
        topology_physics(g)["verdict"] == "ACCEPT"
        and topology_physics(h)["verdict"] == "ACCEPT")

    # 规则集稳定：S1 四则 + TOPO 两则
    chk("⑦ 统一规则集 = S1 四则 + TOPO 两则（6 条）· 名字稳定",
        len(TOPOLOGY_DRC_RULES) == 6
        and run_topology_drc(cg, g)["n_rules"] == 6
        and "SCD-TOPO-NODE-SPACING" in TOPOLOGY_DRC_RULES
        and "SCD-TOPO-MAX-DEGREE" in TOPOLOGY_DRC_RULES)

    # 节点太挤 ⇒ NODE-SPACING REJECT（两种拓扑）
    dense_g = grid_topology(3, 3, pitch_x=12.0, pitch_y=8.0)
    dense_h = heavy_hex_topology(3, 3, unit_um=16.0)
    vdg = run_topology_drc(topology_cell(dense_g), dense_g)
    vdh = run_topology_drc(topology_cell(dense_h), dense_h)
    chk("⑧ 节点太挤 ⇒ DRC REJECT（SCD-TOPO-NODE-SPACING）· 两拓扑皆然",
        vdg["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-TOPO-NODE-SPACING" for v in vdg["violations"])
        and vdh["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-TOPO-NODE-SPACING" for v in vdh["violations"]))

    # 度超上限 ⇒ MAX-DEGREE REJECT（人为把方阵某节点连到 5 个；hex 连到 4 个）
    bad_g = grid_topology(3, 3)
    bad_g["adjacency"][0] = [1, 2, 3, 4, 5]
    vbg = run_topology_drc(cg, bad_g)
    bad_h = heavy_hex_topology(3, 3)
    bad_h["adjacency"][0] = [1, 2, 3, 4]
    vbh = run_topology_drc(ch, bad_h)
    chk("⑨ 度超上限 ⇒ DRC REJECT（SCD-TOPO-MAX-DEGREE）· grid 5>4 与 hex 4>3",
        vbg["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-TOPO-MAX-DEGREE" for v in vbg["violations"])
        and vbh["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-TOPO-MAX-DEGREE" for v in vbh["violations"]))

    # 方阵实例与 S3 拓扑口径一致：耦合数 == rows(cols−1)+cols(rows−1)
    for (r, c) in ((2, 2), (3, 3), (7, 8)):
        gg = grid_topology(r, c)
        expected = r * (c - 1) + c * (r - 1)
        chk(f"⑩ 方阵实例与 S3 口径一致（{r}×{c}：耦合数 == rows(cols−1)+cols(rows−1)）",
            gg["n_qubits"] == r * c and gg["n_couplings"] == expected)

    # 缺耦合器 ⇒ LVS 计数 REJECT（两种拓扑）
    no_coup_g = [d for d in cg if d.get("net") != "coupler"]
    no_coup_h = [d for d in ch if d.get("net") != "coupler"]
    chk("⑪ 缺耦合器 ⇒ LVS REJECT（SCD-LVS-TOPO-COUPLER-COUNT / 连通）· 两拓扑皆然",
        topology_lvs(no_coup_g, g)["verdict"] == "REJECT"
        and topology_lvs(no_coup_h, h)["verdict"] == "REJECT")

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok
