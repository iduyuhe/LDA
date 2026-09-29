"""D-138 · 超导征程 S5 P1：heavy-hex 拓扑（对标 IBM）—— 统一拓扑框架的 **heavy-hex 适配层**。

🔴 **D-145 起本模块是薄适配层**：真实实现在 `sc_topology_core`（统一拓扑 DRC/LVS 框架，
方阵与 heavy-hex 共用同一份引擎）。本模块只做三件事：
  ① 把 「heavy-hex 参数（rows/cols/unit）」→ `core.heavy_hex_topology(...)`；
  ② 保持 S5 P1 既有的公开 API 名（`heavy_hex_graph` / `heavy_hex_cell` / `run_heavyhex_drc`
     / `heavyhex_lvs` / `heavy_hex_physics` / `heavy_hex_degree_stats` / `heavy_hex_gds` /
     `heavy_hex_svg_preview`）不变 ⇒ 既有门禁/探针/demo 零改动；
  ③ 提供 heavy-hex 视角的自检（拓扑形状 + 统一引擎 ACCEPT + 各违规 REJECT）。

拓扑（与 LDA 原生方阵对照，见 `sc_topology_core`）：
  · heavy-hex = 蜂窝两子格 A/B（各度 3）+ 每条边中点 qubit（度 2）⇒ **最大度 3，无 4 邻居**。
  · 方阵 = rows×cols 网格 + 最近邻耦合 ⇒ 最大度 4。两者规则名/引擎**完全共用**
    （`SCD-TOPO-NODE-SPACING` / `SCD-TOPO-MAX-DEGREE`，度上限由拓扑自声明）。
红线：纯几何 + 平台 numpy 物理锚、零量子 SDK、LLM 不进判决路径、限值为设计规则。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from lda_qeda import sc_topology_core as TC

# 统一框架的重导出（沿用 P1 的公开名）
DEFAULT_HEX_UNIT_UM = TC.DEFAULT_HEX_UNIT
HEAVYHEX_MAX_DEGREE = TC.HEAVYHEX_MAX_DEGREE
HEAVYHEX_DRC_RULES = TC.TOPOLOGY_DRC_RULES
DEFAULT_HEAVY_LIMITS = TC.DEFAULT_TOPO_LIMITS

RED_LINE_DISCLOSURE = {
    "role": "D-138 = 超导征程 S5 P1：heavy-hex 拓扑生成器（对标 IBM）+ P&R + DRC/LVS 签核"
            "（**D-145 起与方阵共用 sc_topology_core 统一框架**）",
    "layers": "SC_FILM=10 / SC_JJ=11 / SC_GROUND=12（gds_export 定义，非 Foundry PDK）",
    "limits": "min_node_spacing / coupler_width 为**设计规则 · 可覆盖 · 非实测 golden**"
              "（Foundry PDK 属 D5 外部依赖）",
    "lvs": "复用 S2 多网连通 LVS（对**实际 produced 几何**做 bbox 网表提取）+ 耦合计数与拓扑一致",
    "physics": "逐耦合 J 用 coupler_solver 严格对角化↔解析闭式双验证 + cross_resonance 有效"
               "模型落 ORACLE 窗（与 S2/S3 同口径）",
    "topology": "heavy-hex = 蜂窝顶点（度 3）+ 边中点（度 2）；最大度 3，无 4 邻居；"
                "与方阵共用 `SCD-TOPO-*` 规则与同一份 DRC/LVS 引擎",
    "red_line": "纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、"
                "耦合器为中心连线矩形（单元级示意）",
}
ROLE = RED_LINE_DISCLOSURE["role"]


# ---------------------------------------------------------------------------
# 拓扑 / P&R / 出口（全部委托统一框架）
# ---------------------------------------------------------------------------
def heavy_hex_graph(rows: int = 3, cols: int = 3,
                    unit_um: float = DEFAULT_HEX_UNIT_UM) -> Dict:
    """heavy-hex 拓扑（委托 `core.heavy_hex_topology`）。"""
    return TC.heavy_hex_topology(rows, cols, unit_um)


def heavy_hex_degree_stats(graph: Dict) -> Dict:
    """度分布（委托统一框架；含 `max_degree_limit` / `within_limit`）。"""
    return TC.topology_degree_stats(graph)


def heavy_hex_cell(params: Optional[Dict] = None) -> List[Dict]:
    """heavy-hex P&R 版图（委托 `core.topology_cell`）。"""
    p = dict(params or {})
    graph = heavy_hex_graph(int(p.get("rows", 3)), int(p.get("cols", 3)),
                            float(p.get("hex_unit", DEFAULT_HEX_UNIT_UM)))
    return TC.topology_cell(graph, p)


def heavy_hex_gds(params: Optional[Dict] = None, path: str = "sc_heavyhex.gds") -> bytes:
    """真出 GDSII（委托统一框架）。"""
    p = dict(params or {})
    graph = heavy_hex_graph(int(p.get("rows", 3)), int(p.get("cols", 3)),
                            float(p.get("hex_unit", DEFAULT_HEX_UNIT_UM)))
    return TC.topology_gds(graph, p, path)


def heavy_hex_svg_preview(params: Optional[Dict] = None, width: int = 620) -> str:
    """版图 SVG 预览（委托统一框架）。"""
    p = dict(params or {})
    graph = heavy_hex_graph(int(p.get("rows", 3)), int(p.get("cols", 3)),
                            float(p.get("hex_unit", DEFAULT_HEX_UNIT_UM)))
    return TC.topology_svg_preview(graph, p, width)


# ---------------------------------------------------------------------------
# DRC / LVS / 物理（委托统一框架）
# ---------------------------------------------------------------------------
def run_heavyhex_drc(elements: List[Dict], graph: Optional[Dict] = None,
                     limits: Optional[Dict] = None) -> Dict:
    """heavy-hex DRC（= 统一框架 DRC：S1 四则 + SCD-TOPO-NODE-SPACING + SCD-TOPO-MAX-DEGREE）。"""
    g = graph if graph is not None else heavy_hex_graph()
    return TC.run_topology_drc(elements, g, limits)


def heavyhex_lvs(elements: List[Dict], graph: Optional[Dict] = None) -> Dict:
    """heavy-hex LVS（= 统一框架 LVS：S2 多网连通 + SCD-LVS-TOPO-COUPLER-COUNT）。"""
    g = graph if graph is not None else heavy_hex_graph()
    return TC.topology_lvs(elements, g)


def heavy_hex_physics(params: Optional[Dict] = None) -> Dict:
    """heavy-hex 逐耦合物理（= 统一框架物理：J 双验证 + CR 落窗）。"""
    p = dict(params or {})
    graph = heavy_hex_graph(int(p.get("rows", 3)), int(p.get("cols", 3)),
                            float(p.get("hex_unit", DEFAULT_HEX_UNIT_UM)))
    return TC.topology_physics(graph, p)


_bar_polygon = TC._bar_polygon       # 向后兼容重导出


# ---------------------------------------------------------------------------
# 自检（heavy-hex 视角：拓扑形状 + 统一引擎 ACCEPT + 各违规 REJECT）
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
        and g["n_couplings"] == 42)
    chk("② **最大度 ≤ 3（无 4 邻居，IBM heavy-hex 定义式）** · 顶点 3 / 边 2",
        deg["max_degree"] <= HEAVYHEX_MAX_DEGREE and deg["no_four_neighbor"]
        and deg["vertex_deg_max"] == 3 and deg["edge_deg_max"] == 2
        and deg["within_limit"])
    chk("③ 度上限由拓扑自声明 = 3（与方阵 4 对照）",
        g["max_degree_limit"] == HEAVYHEX_MAX_DEGREE)

    cell = heavy_hex_cell({"rows": 3, "cols": 3})
    chk("④ 合法 3×3 heavy-hex DRC ACCEPT（统一框架 S1 四则 + TOPO 两则）",
        run_heavyhex_drc(cell, g)["verdict"] == "ACCEPT")
    chk("⑤ 合法 3×3 heavy-hex LVS ACCEPT（S2 多网连通 + 计数一致）",
        heavyhex_lvs(cell, g)["verdict"] == "ACCEPT")

    dense = heavy_hex_cell({"rows": 3, "cols": 3, "hex_unit": 16.0})
    vd = run_heavyhex_drc(dense, g)
    chk("⑥ 节点太挤(unit 16) ⇒ DRC REJECT（SCD-TOPO-NODE-SPACING）",
        vd["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-TOPO-NODE-SPACING" for v in vd["violations"]))

    bad = heavy_hex_graph(3, 3)
    bad["adjacency"][0] = [1, 2, 3, 4]
    vb = run_heavyhex_drc(cell, bad)
    chk("⑦ 出现 4 邻居 ⇒ DRC REJECT（SCD-TOPO-MAX-DEGREE，4>3）",
        vb["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-TOPO-MAX-DEGREE" for v in vb["violations"]))

    no_coup = [d for d in cell if d.get("net") != "coupler"]
    vn = heavyhex_lvs(no_coup, g)
    chk("⑧ 缺耦合器 ⇒ LVS REJECT（SCD-LVS-TOPO-COUPLER-COUNT / 连通）",
        vn["verdict"] == "REJECT")

    chk("⑨ heavy-hex 密度：边 qubit / 顶点 ≈ 1.5（蜂窝特征）",
        abs(g["n_edge_qubits"] / g["n_vertices"] - 1.5) < 0.6)

    phys = heavy_hex_physics({"rows": 3, "cols": 3})
    chk("⑩ 逐耦合物理 ACCEPT（J 双验证 + CR 落窗）", phys["verdict"] == "ACCEPT")

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok
