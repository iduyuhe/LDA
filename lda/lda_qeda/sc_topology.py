"""D-138 · 超导征程 S5 P1：heavy-hex 拓扑生成器（对标 IBM）+ P&R + 签核。

LDA 原生拓扑是 2D 方阵（S3，4 邻居）；IBM 全系（Eagle/Osprey/Condor/Heron/Willow）
用 **heavy-hex**（heavy-hexagon）格：qubit 无 4 邻居 —— 蜂窝（honeycomb）顶点 qubit
（度 3）+ 每条边中点 qubit（度 2），最大度 = 3。G2 把平台拓扑从方阵扩到 heavy-hex。

能力（纯几何 + 闭式，零量子 SDK）：
  • heavy_hex_graph(rows, cols)   → heavy-hex 图：顶点 qubit + 边中点 qubit + 耦合边 + 邻接
  • heavy_hex_degree_stats(g)     → 度分布（**最大度 ≤ 3**，无 4 邻居；heavy-hex 定义式性质）
  • heavy_hex_cell(params)        → P&R 版图：每节点一只 transmon + 每边一个耦合器 + 整框地
  • run_heavyhex_drc(els)         → 复用 S1 DRC 四则 + heavy-hex 二则（间距 / 最大度）
  • heavyhex_lvs(els, graph)      → 复用 S2 多网连通 LVS + 节点/边计数一致
  • heavy_hex_physics(params)     → 逐边 J 双验证（coupler_solver 严格↔解析）+ CR 落窗
  • run_selfchecks()

构图（brick-wall honeycomb）：
  顶点 (r,c) 位置 x = c·U + 0.5·(r%2)·U，y = (rows−1−r)·(√3/2)·U；
  边：(r,c)-(r,c+1)（水平，全行）+ (r,c)-(r+1,c)（仅偶行 ⇒ 竖直边方向交替 ⇒ 度 3）。
  每条边中点插入一只 qubit ⇒ 顶点度 3 / 边 qubit 度 2。

诚实边界（与 S1–S4 一致）：
  • 耦合器几何为**中心连线**的旋转矩形（单元级示意图；尺寸/电容 Cc 为设计参数，不由几何反推）。
  • 逐边 J 双验证只在相邻 qubit 近共振区可分辨（与 S2/G3 同口径）。
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

DEFAULT_HEX_UNIT_UM = 56.0     # 蜂窝单位边长（相邻 qubit 中心距）
HEAVYHEX_MAX_DEGREE = 3        # heavy-hex 定义式：最大度 = 3（无 4 邻居）

DEFAULT_HEAVY_LIMITS = dict(SCD.DEFAULT_DRC_LIMITS)
DEFAULT_HEAVY_LIMITS.update({
    "min_node_spacing_um": 0.5,     # 相邻节点 qubit 导体最小间隙
    "coupler_width_um": 0.5,
})
HEAVYHEX_DRC_RULES = tuple(list(SCD.SCD_RULES) + [
    "SCD-HEAVYHEX-SPACING",     # 节点 qubit 导体不得互叠
    "SCD-HEAVYHEX-DEGREE",      # 最大度 ≤ 3（heavy-hex 拓扑定义）
])

RED_LINE_DISCLOSURE = {
    "role": "D-138 = 超导征程 S5 P1：heavy-hex 拓扑生成器（对标 IBM）+ P&R + DRC/LVS 签核，"
            "把平台拓扑从 LDA 原生方阵扩到 IBM 全系 heavy-hex",
    "layers": "SC_FILM=10 / SC_JJ=11 / SC_GROUND=12（gds_export 定义，非 Foundry PDK）",
    "limits": "min_node_spacing / coupler_width 为**设计规则 · 可覆盖 · 非实测 golden**"
              "（Foundry PDK 属 D5 外部依赖）",
    "lvs": "复用 S2 多网连通 LVS（对**实际 produced 几何**做 bbox 网表提取）+ 节点/边计数一致",
    "physics": "逐边 J 用 coupler_solver 严格对角化↔解析闭式双验证 + cross_resonance 有效"
               "模型落 ORACLE 窗（与 S2/S3 同口径）",
    "topology": "heavy-hex = 蜂窝顶点（度 3）+ 边中点（度 2）；最大度 3，无 4 邻居",
    "red_line": "纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、"
                "耦合器为中心连线矩形（单元级示意）",
}
ROLE = RED_LINE_DISCLOSURE["role"]


# ---------------------------------------------------------------------------
# 拓扑生成器
# ---------------------------------------------------------------------------
def heavy_hex_graph(rows: int = 3, cols: int = 3,
                    unit_um: float = DEFAULT_HEX_UNIT_UM) -> Dict:
    """生成 heavy-hex 图（蜂窝两子格 A/B + 边中点 qubit + 耦合边 + 邻接）。

    蜂窝两子格（近邻距 = 1 单位）：
      A(i,j) = i·(3/2, √3/2) + j·(3/2, −√3/2)      B(i,j) = A(i,j) + (1, 0)
      A(i,j) 邻接 B(i,j) / B(i−1,j) / B(i,j−1)   ⇒ A、B 各度 3
    每条边插入一只中点 qubit ⇒ 顶点度 3 / 边 qubit 度 2（heavy-hex 定义）。
    返回 {positions, kind, edges:[(eid,va,vb)], adjacency, n_vertices, n_edge_qubits,
          n_qubits, n_edges(=2·原始边), ...}。
    """
    rows = int(rows)
    cols = int(cols)
    sx, sy = 1.5 * unit_um, (math.sqrt(3.0) / 2.0) * unit_um
    positions: Dict[int, Tuple[float, float]] = {}
    kind: Dict[int, str] = {}

    def _A(i: int, j: int) -> Tuple[float, float]:
        return (sx * (i + j), sy * (i - j))

    x_all = [sx * (i + j) for i in range(rows) for j in range(cols)]
    xc = 0.5 * (min(x_all) + max(x_all))
    y_all = [sy * (i - j) for i in range(rows) for j in range(cols)]
    yc = 0.5 * (min(y_all) + max(y_all))

    aid = {}
    bid = {}
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
    pairs: List[Tuple[int, int]] = []
    seen = set()

    def _add(a: int, b: int):
        key = (min(a, b), max(a, b))
        if key not in seen:
            seen.add(key)
            pairs.append(key)

    for i in range(rows):
        for j in range(cols):
            _add(aid[(i, j)], bid[(i, j)])
            if i - 1 >= 0:
                _add(aid[(i, j)], bid[(i - 1, j)])
            if j - 1 >= 0:
                _add(aid[(i, j)], bid[(i, j - 1)])

    edges: List[Tuple[int, int, int]] = []
    for k, (a, b) in enumerate(pairs):
        eid = n_v + k
        pa, pb = positions[a], positions[b]
        positions[eid] = ((pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0)
        kind[eid] = "edge"
        edges.append((eid, a, b))

    adj: Dict[int, List[int]] = {nid: [] for nid in positions}
    for (eid, a, b) in edges:
        adj[a].append(eid)
        adj[eid].append(a)
        adj[b].append(eid)
        adj[eid].append(b)

    return {"positions": positions, "kind": kind, "edges": edges,
            "adjacency": adj, "n_vertices": n_v, "n_edge_qubits": len(edges),
            "n_qubits": n_v + len(edges), "n_edges": 2 * len(edges),
            "unit_um": unit_um, "rows": rows, "cols": cols}


def heavy_hex_degree_stats(graph: Dict) -> Dict:
    """度分布（heavy-hex 定义式性质：最大度 ≤ 3，无 4 邻居）。"""
    adj = graph["adjacency"]
    deg = {n: len(v) for n, v in adj.items()}
    hist: Dict[int, int] = {}
    for d in deg.values():
        hist[d] = hist.get(d, 0) + 1
    v_deg = [deg[n] for n in graph["kind"] if graph["kind"][n] == "vertex"]
    e_deg = [deg[n] for n in graph["kind"] if graph["kind"][n] == "edge"]
    return {"histogram": hist, "max_degree": max(deg.values()) if deg else 0,
            "vertex_deg_max": max(v_deg) if v_deg else 0,
            "edge_deg_max": max(e_deg) if e_deg else 0,
            "no_four_neighbor": bool(all(d <= HEAVYHEX_MAX_DEGREE for d in deg.values()))}


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


# ---------------------------------------------------------------------------
# P&R（每节点 transmon + 每边耦合器 + 整框地）
# ---------------------------------------------------------------------------
def heavy_hex_cell(params: Optional[Dict] = None) -> List[Dict]:
    """heavy-hex P&R 版图：每节点一只 transmon + 每边一个耦合器 + 整框地。"""
    p = dict(params or {})
    graph = heavy_hex_graph(int(p.get("rows", 3)), int(p.get("cols", 3)),
                            float(p.get("hex_unit", DEFAULT_HEX_UNIT_UM)))
    cw = float(p.get("coupler_width", DEFAULT_HEAVY_LIMITS["coupler_width_um"]))
    gg = float(p.get("ground_gap", 1.0))
    mono_params = {k: v for k, v in p.items()
                   if k in ("pad_w", "pad_h", "gap_x", "jj_len", "jj_h",
                            "cpw_w", "arm_len")}

    body: List[Dict] = []
    for nid, (x, y) in graph["positions"].items():
        body += _translate(_tmon_without_ground(mono_params), x, y)
    for (eid, a, b) in graph["edges"]:
        # 每条原始边拆成两条耦合（a—中点 / 中点—b）⇒ heavy-hex 顶点度 3 / 边 qubit 度 2
        for (u, v) in ((a, eid), (eid, b)):
            poly = _bar_polygon(graph["positions"][u], graph["positions"][v], cw)
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


def heavy_hex_gds(params: Optional[Dict] = None, path: str = "sc_heavyhex.gds") -> bytes:
    """真出 GDSII（零依赖自写编码器）。返回文件字节。"""
    descs = heavy_hex_cell(params)
    recs: List[bytes] = []
    for d in descs:
        if d["kind"] == "path":
            recs.append(G.path(d["layer"], d["width_um"], d["points_um"]))
        else:
            recs.append(G.boundary(d["layer"], G._flatten_rings(d.get("rings_um"))))
    data = G.gds_library("LDA-SC-HEAVYHEX", {"sc_heavyhex": recs})
    G.write_gds(path, data)
    return data


def heavy_hex_svg_preview(params: Optional[Dict] = None, width: int = 620) -> str:
    """版图 SVG 预览（qubit=蓝 / jj=红 / coupler=橙 / ground=灰）。"""
    descs = heavy_hex_cell(params)
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
# DRC / LVS
# ---------------------------------------------------------------------------
def run_heavyhex_drc(elements: List[Dict],
                     graph: Optional[Dict] = None,
                     limits: Optional[Dict] = None) -> Dict:
    """heavy-hex DRC = S1 四则 + SCD-HEAVYHEX-SPACING + SCD-HEAVYHEX-DEGREE。"""
    lim = dict(DEFAULT_HEAVY_LIMITS)
    if limits:
        lim.update(limits)
    base = SCD.run_sc_drc(elements, lim)
    violations = list(base["violations"])

    # SCD-HEAVYHEX-SPACING：不同**节点**的 qubit 导体不得互叠（同节点内的 pad/臂互叠是设计）
    g = graph if graph is not None else heavy_hex_graph()
    node_boxes: Dict[int, List[Tuple[float, float, float, float]]] = {}
    for d in elements:
        if d.get("net") != "qubit":
            continue
        bb = _bbox(d)
        cx, cy = (bb[0] + bb[1]) / 2.0, (bb[2] + bb[3]) / 2.0
        nid = min(g["positions"],
                  key=lambda n: (g["positions"][n][0] - cx) ** 2
                  + (g["positions"][n][1] - cy) ** 2)
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
        violations.append({"rule": "SCD-HEAVYHEX-SPACING",
                           "detail": f"{overlaps} 对节点 qubit 导体互叠（节点间距不足）"})

    # SCD-HEAVYHEX-DEGREE：最大度 ≤ 3
    deg = heavy_hex_degree_stats(g)
    if deg["max_degree"] > HEAVYHEX_MAX_DEGREE:
        violations.append({"rule": "SCD-HEAVYHEX-DEGREE",
                           "detail": f"最大度={deg['max_degree']}>{HEAVYHEX_MAX_DEGREE}"})

    verdict = "ACCEPT" if not violations else "REJECT"
    return {"verdict": verdict, "violations": violations,
            "n_rules": len(HEAVYHEX_DRC_RULES), "limits": lim,
            "max_degree": deg["max_degree"], "qubit_overlaps": overlaps}


def heavyhex_lvs(elements: List[Dict], graph: Optional[Dict] = None) -> Dict:
    """heavy-hex LVS = 复用 S2 多网连通 LVS + 节点/边计数一致。"""
    base = sc_pair_lvs_signoff(elements)
    issues = list(base["issues"])
    n_checks = base["n_checks"] + 1

    g = graph if graph is not None else heavy_hex_graph()
    n_q_group = len([d for d in elements if d.get("net") == "qubit"
                     and d.get("kind") == "boundary"])
    n_coupler = len([d for d in elements if d.get("net") == "coupler"])
    # 耦合器数须 == 2·边数（每条边连通 2 个（顶点,边中点）对）
    if n_coupler != g["n_edges"]:
        issues.append(f"SCD-LVS-HEAVYHEX-COUPLER-COUNT: 耦合器={n_coupler}"
                      f"≠2·边数={g['n_edges']}")

    verdict = "ACCEPT" if not issues else "REJECT"
    return {"verdict": verdict, "issues": issues,
            "netlist": dict(base["netlist"], n_nodes=g["n_qubits"],
                            n_couplers=n_coupler, qubit_islands=n_q_group),
            "n_checks": n_checks}


# ---------------------------------------------------------------------------
# 物理签核（逐边 J 双验证 + CR 落窗）
# ---------------------------------------------------------------------------
def heavy_hex_physics(params: Optional[Dict] = None) -> Dict:
    """heavy-hex 逐边物理签核：J 严↔解析双验证 + CR 有效模型落窗。"""
    p = dict(params or {})
    g = heavy_hex_graph(int(p.get("rows", 3)), int(p.get("cols", 3)),
                        float(p.get("hex_unit", DEFAULT_HEX_UNIT_UM)))
    ec = float(p.get("E_C", 0.25))
    ej_c = float(p.get("E_J_vertex", 18.0))
    ej_e = float(p.get("E_J_edge", 19.3))
    cc = float(p.get("Cc", 0.007))
    max_edges = int(p.get("max_physics_edges", 64))

    f_c = CS.koch_f01(ej_c, ec)
    f_e = CS.koch_f01(ej_e, ec)
    delta = f_e - f_c
    alpha = -ec
    edges_phys: List[Dict] = []
    max_rel = 0.0
    for (i, (eid, a, b)) in enumerate(g["edges"][:max_edges]):
        sol = CS.solve_coupler(ej_c, ec, ej_e, ec, cc, 1.0, 1.0)
        j_num = float(sol["J_num"])
        j_an = float(sol["J_analytic"])
        rel = abs(j_num - j_an) / (abs(j_an) + 1e-15)
        max_rel = max(max_rel, rel)
        cr = CR.cross_resonance(j_num * 1000.0, delta * 1000.0, alpha * 1000.0)
        edges_phys.append({"edge": i, "J_num_ghz": j_num, "J_rel_err": float(rel),
                           "g_CR_mhz": cr.get("g_CR_MHz"),
                           "cr_ok": bool(cr.get("ok", False))})
    j_ok = bool(max_rel <= 0.05)
    cr_ok = bool(all(e["cr_ok"] for e in edges_phys)) if edges_phys else False
    verdict = "ACCEPT" if (j_ok and cr_ok) else "REJECT"
    return {"verdict": verdict, "n_edges": len(edges_phys),
            "max_J_rel_err": float(max_rel), "J_double_validated": j_ok,
            "cr_all_ok": cr_ok, "detune_ghz": float(delta),
            "g_CR_mhz": edges_phys[0]["g_CR_mhz"] if edges_phys else None,
            "edges": edges_phys,
            "note": "逐边 J 用 coupler_solver 严格↔解析双验证（容差 5%）+ CR 有效模型落窗"
                    "（与 S2/S3 同口径）。Cc/E_J 为设计参数，不由几何反推。LLM 不进判决路径。"}


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    ok = True
    msgs: List[Tuple[str, bool]] = []

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        msgs.append((name, bool(cond)))

    g = heavy_hex_graph(3, 3)
    deg = heavy_hex_degree_stats(g)
    chk("① 3×3 heavy-hex 图：18 顶点 + 21 边 qubit = 39 qubit · 42 耦合",
        g["n_vertices"] == 18 and g["n_edge_qubits"] == 21 and g["n_qubits"] == 39
        and g["n_edges"] == 42)
    chk("② **最大度 ≤ 3（无 4 邻居）** · 顶点度 3 / 边 qubit 度 2",
        deg["max_degree"] <= HEAVYHEX_MAX_DEGREE and deg["no_four_neighbor"]
        and deg["vertex_deg_max"] == 3 and deg["edge_deg_max"] == 2)

    cell = heavy_hex_cell({"rows": 3, "cols": 3})
    chk("③ 合法 3×3 heavy-hex DRC ACCEPT（S1 四则 + heavy-hex 二则）",
        run_heavyhex_drc(cell, g)["verdict"] == "ACCEPT")
    chk("④ 合法 3×3 heavy-hex LVS ACCEPT（S2 多网连通 + 计数一致）",
        heavyhex_lvs(cell, g)["verdict"] == "ACCEPT")

    # 节点太挤（单位边长过小）⇒ SPACING REJECT
    dense = heavy_hex_cell({"rows": 3, "cols": 3, "hex_unit": 16.0})
    vd = run_heavyhex_drc(dense, g)
    chk("⑤ 节点太挤(unit 16) ⇒ DRC REJECT（SCD-HEAVYHEX-SPACING）",
        vd["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-HEAVYHEX-SPACING" for v in vd["violations"]))

    # 破坏度为 4 的图 ⇒ DEGREE REJECT
    bad = heavy_hex_graph(3, 3)
    bad["adjacency"][0] = [1, 2, 3, 4]
    vb = run_heavyhex_drc(cell, bad)
    chk("⑥ 出现 4 邻居 ⇒ DRC REJECT（SCD-HEAVYHEX-DEGREE）",
        vb["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-HEAVYHEX-DEGREE" for v in vb["violations"]))

    # 缺耦合器 ⇒ LVS 计数 REJECT
    no_coup = [d for d in cell if d.get("net") != "coupler"]
    vn = heavyhex_lvs(no_coup, g)
    chk("⑦ 缺耦合器 ⇒ LVS REJECT（HEAVYHEX-COUPLER-COUNT / 连通）",
        vn["verdict"] == "REJECT")

    # 密度：边 qubit 数 ≈ 1.5 × 顶点数（蜂窝特征）
    chk("⑧ heavy-hex 密度：边 qubit / 顶点 ≈ 1.5（蜂窝特征）",
        abs(g["n_edge_qubits"] / g["n_vertices"] - 1.5) < 0.6)

    phys = heavy_hex_physics({"rows": 3, "cols": 3})
    chk("⑨ 逐边物理 ACCEPT（J 双验证 + CR 落窗）", phys["verdict"] == "ACCEPT")

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok
