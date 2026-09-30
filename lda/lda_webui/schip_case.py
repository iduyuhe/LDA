"""超导量子计算芯片案例卡（WebUI 只读端点数据源）· D-148。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
超导征程「吃狗粮」LDA-S1…S5（D-133…D-145）的**只读案例**：用 LDA 亲手设计一颗
transmon 超导量子计算芯片 —— 从单比特单元到 1024 比特阵列版图，走完
**P&R → 布线路由 → 几何 DRC/LVS → 频率避撞 → 串扰/损耗预算**全链路签核，
并出**真 GDSII**。

与 `/api/qchip_demo`（光量子 LOQC 案例卡 · D-131）**并列**：量子两条路线在 LDA
均有真 GDS 闭环。本卡回答的是**同一个平台问题**——「同一条链路，换一种物理
（微波/超导），是否还站得住？」

🔴 **零重计算**（与站内 cpo_array / design_* 等重算端点不同）：本模块**不跑 P&R、
不 import 求解器、不解析 GDS** —— 全部数字取自 ① 静态里程碑/结论（人工登记、
可回溯到门禁与 report）② **闭式**几何推算 ③ 对产出物只 `stat` 的元信息。
⇒ **无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**，与 `/api/qchip_demo`、
`/api/verification_ledger` 同属「公开只读验货」类。

🔴 **不伪装实测**：`verdict` 恒为 `DESIGN_SIGNOFF`（**非** ACCEPT/PASS），
返回体自带 `honest_note`。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

__all__ = [
    "CASE_ID", "SCHIP_HONEST_NOTE", "MILESTONES", "FINDINGS", "GAPS",
    "GRID_TIERS", "HEX_TIERS", "REFERENCE_TIERS",
    "capacity_closed_form", "case_card", "run_selfchecks",
]

# ═══════════════════════════ 常量（与平台模块同源）═══════════════════════════
CASE_ID = "LDA-S · 超导量子计算芯片（transmon / 微波 QEDA）"

#: 单 transmon 工作点（S1 · D-133 · `coupler_solver` 严格对角化 ↔ Koch 闭式双验证）
F01_GHZ = 4.887
ALPHA_GHZ = -0.356
#: 读出/损耗目标（S4 · D-136）· 设计规则口径
T1_TARGET_US = 20.0
#: 静态杂散 ZZ 上限（S4 · D-136）· MHz
ZZ_STRAY_LIMIT_MHZ = 1.0
#: 可调耦合器可关比下限（S5 P1 · G3 · D-139）
COUPLER_OFF_RATIO_MIN = 10.0
#: 阵列版图默认 pitch（µm）· `sc_array` 设计规则
PITCH_X_UM = 22.0
PITCH_Y_UM = 14.0
#: 旗舰规模（对标 IBM 千比特级声明）
FLAGSHIP_ROWS, FLAGSHIP_COLS = 32, 32

SCHIP_HONEST_NOTE = (
    "① 本案例是**设计期签核**（版图 + DRC/LVS + 频率/串扰/损耗预算 + 物理闭式双验证），"
    "**非流片后实测**——无低温实测 T1/T2、无实测保真度、无 foundry 回片；"
    "② DRC 限值为**设计规则**（源自 S1 单元原语的几何自洽与公开工艺常识），"
    "**非任何 foundry 的 PDK deck**（属 D5 外部依赖）；"
    "③ 物理量分两类：**闭式/严格对角化双验证**（Koch f01、耦合 J、SQUID E_J(Φ)、"
    "色散 χ）为方法学可复核；**损耗/串扰预算**（参与比、Purcell、ZZ 杂散）为"
    "**设计预算口径**，参数（tanδ、参与比、κ、g）为设计输入，非实测；"
    "④ 规模数字是**版图容量**（可排布并可签核的比特数），"
    "**不等于**已制备器件的比特数——与 IBM/Google 的「已交付芯片」不同台比较；"
    "⑤ **不含纠错码**（surface code / qLDPC）逻辑比特验证、不含量子线路级仿真、"
    "不含门保真实测、不含封装/低温布线实现 ⇒ 属**版本级（pre-QEC）物理层设计**能力；"
    "⑥ 零量子 SDK：全程不依赖 Qiskit / Cirq / PennyLane 等外部量子框架，"
    "物理内核为平台自研（numpy 闭式 + 严格对角化）。"
)

# ═══════════════════════ 五段征程（静态事实 · 可回溯门禁）═══════════════════
MILESTONES = [
    {"id": "S1", "code": "D-133", "title": "单 transmon 单元 · 全闭环",
     "gate": 21,
     "result": "真 GDS（层 10/11/12）+ 几何 DRC 4 规则 + LVS 5 判据；"
               "f01 严格对角化 4.887 GHz ↔ Koch 闭式 rel 0.42%；α = −0.356 GHz"},
    {"id": "S2", "code": "D-134", "title": "耦合 transmon 对 · 全闭环",
     "gate": 24,
     "result": "耦合对版图 + 复用 S1 签核 + 多网连通 LVS 6 判据；"
               "J 双验证 rel ≤ 5%；g_CR = 2.59 MHz · t_CR = 1.21 µs · σ_zz = 0.21 MHz"},
    {"id": "S3", "code": "D-135", "title": "N 比特阵列 P&R · 全闭环",
     "gate": 28,
     "result": "rows×cols 网格 P&R + 最近邻耦合（行内 + 行间）+ 规模 DRC 5 规则 + "
               "LVS 6 判据；3×3 = 9 qubit / 12 边 · 逐边 J 双验证 max rel 4.37%"},
    {"id": "S4", "code": "D-136", "title": "读出 / 控制线路 + 串扰 / 损耗预算",
     "gate": 31,
     "result": "读出谐振腔 + 馈线 + 控制桩 P&R；专用 DRC 10 规则 + LVS 9 判据；"
               "全 pair 杂散 ZZ ≤ 1.0 MHz；per-qubit T1（内部 + Purcell）≥ 20 µs"},
    {"id": "S5", "code": "D-137…D-145", "title": "规模压力 + 真实架构要素 + 统一拓扑框架",
     "gate": 96,
     "result": "G1 梳状单层布线路由（14 DRC / 11 LVS）· G6 频率避撞分配 · "
               "G7 规模压力（53/127/433/**1024**）· G3 可调耦合器（可关比 54.3）· "
               "G4 读出 FDM · G5 控制多线 · G8 阵列 + 封装损耗 · "
               "G2 heavy-hex（最大度 3 · 对标 IBM）· G9 批量签核 · D-145 统一拓扑框架"},
]

# ═══════════════════════ 关键结论（物理 + 方法学）═══════════════════════
FINDINGS = [
    {"title": "物理内核方法学独立（非自证）",
     "detail": "Koch 闭式 ↔ 严格对角化（`coupler_solver`）双路互验、SQUID 精确闭式 "
               "E_J(Φ)=√((E_J1+E_J2)²cos²πf+(E_J1−E_J2)²sin²πf)、Schrieffer-Wolff "
               "有效 ZX/ZZ。判决为**死标量比对**，LLM 不进判决路径。"},
    {"title": "规模自洽：版图比例随 N 自动重算",
     "detail": "行 pitch 由 `pitch_y_eff = max(pitch_y_user, (cols−1)·routing_pitch + "
               "drop + feed_zone + clearance)` 约束 ⇒ 大 N 时控制线不再误桥邻居，"
               "这是「9 qubit 能排、1024 qubit 排不动」这一常见断层的根因。"},
    {"title": "频率避撞：显式规避 ZZ 极点",
     "detail": "分配器带三类硬约束（近邻 |Δ| ≥ 10 MHz、最近邻 ≥ 40 MHz、"
               "|‖Δ‖ − |α|| ≥ 30 MHz 避 ZZ 极点），并用**向量化闭式** 与 S4 的"
               "逐对 ZZ 交叉复核（rel 12.7% ≤ 20% 容差）⇒ 大 N 可算（N=1024 用 0.17 s）。"},
    {"title": "拓扑可切换：重六边形与方阵共用一份 DRC/LVS",
     "detail": "D-145 把「拓扑」抽为数据（位置 + 邻接 + 耦合对 + **度上限自声明**），"
               "网格与 heavy-hex 走同一份引擎；最大度上限由拓扑自报（方阵 4 / "
               "heavy-hex 3）⇒ 一份规则服务两种架构。"},
    {"title": "规模不牺牲余量：N 增大时 T1 仍达标",
     "detail": "阵列聚合 + 封装参与比 + 封装腔模规避（f_box 须离工作带 ≥ 200 MHz）⇒ "
               "N = 4…1024 全部 yield = 1.0，最小 T1 41.2 µs（目标 20 µs）。"},
]

# ═══════════════════════ 诚实边界（未闭合项 · 逐条登记）═══════════════════════
GAPS = [
    {"id": "G-A", "title": "无流片 / 无低温实测",
     "detail": "全部为设计期签核；T1/T2、门保真度、读出保真度均未实测。"},
    {"id": "G-B", "title": "无 foundry PDK",
     "detail": "DRC 限值为自建设计规则，未对接任何工艺厂 deck（D5 外部依赖）。"},
    {"id": "G-C", "title": "无纠错码层",
     "detail": "surface code / qLDPC 逻辑比特、解码器与阈值分析不在本案例范围。"},
    {"id": "G-D", "title": "无量子线路级仿真与门标定",
     "detail": "不做脉冲级 Rabi/Ramsey 标定流程、不做线路编译与噪声仿真。"},
    {"id": "G-E", "title": "封装 / 低温布线未落地",
     "detail": "封装只做到「腔模规避 + 参与比预算」；倒装焊、TSV、低温衰减链未实现。"},
]

# ═══════════════════════ 规模档案（来自 examples 实测 report）═══════════════════
#: 网格族（方阵 · 最大度 4）· 实测快照（examples/lda_schip_s5.report.json）
GRID_TIERS = [
    {"tier": "2x2", "qubits": 4, "elements": 44},
    {"tier": "7x8", "qubits": 56, "elements": 563},
    {"tier": "13x13", "qubits": 169, "elements": 1694},
]
#: heavy-hex 族（最大度 3 · 对标 IBM）
HEX_TIERS = [
    {"tier": "3x3", "qubits": 39, "vertices": 18, "edge_qubits": 21,
     "couplings": 42, "max_degree": 3, "elements": 241},
    {"tier": "4x5", "qubits": 91, "vertices": 40, "edge_qubits": 51,
     "couplings": 102, "max_degree": 3, "elements": 561},
]
#: 规模压力档（路由 + 频率 + 损耗）· 实测快照
REFERENCE_TIERS = [
    {"n": 53, "rows": 7, "cols": 8},
    {"n": 127, "rows": 13, "cols": 10},
    {"n": 433, "rows": 21, "cols": 21},
    {"n": 1024, "rows": 32, "cols": 32},
]
#: 千比特级容量（实测：N=1024 · 32×32）· 元素数与 pitch 均为门禁实测值
FLAGSHIP_FACTS = {
    "qubits": FLAGSHIP_ROWS * FLAGSHIP_COLS,
    "rows": FLAGSHIP_ROWS, "cols": FLAGSHIP_COLS,
    "n_elements": 10244,
    "n_signals": 1056,
    "pitch_y_eff_um": 141.0,
    "freq_plan_seconds": 0.17,
    "max_stray_zz_mhz": 0.39,
    "t1_us_at_n441": 25.17,
    "t1_us_min_n_le_1024": 41.2,
}

_ARTIFACT_DIRS = ("examples", "lda/examples")


# ═══════════════════════════ 闭式（可反向测试）═══════════════════════════
def capacity_closed_form(rows: int, cols: int,
                         pitch_x_um: float = PITCH_X_UM,
                         pitch_y_um: float = PITCH_Y_UM) -> Dict[str, Any]:
    """阵列容量闭式：耦合数 / 交互半径 / 版图跨距（纯几何，与 `sc_array` 同口径）。

    - 耦合数 = rows(cols−1) + cols(rows−1)（网格 4 邻居；行内 + 行间）
    - 交互半径 = 1.5 · pitch_x（`sc_freq_alloc` 的约束施加范围）
    - 版图跨距 = (cols−1)·pitch_x × (rows−1)·pitch_y
    """
    rows, cols = int(rows), int(cols)
    if rows < 1 or cols < 1:
        raise ValueError("rows / cols 须 ≥ 1")
    qubits = rows * cols
    couplings = rows * (cols - 1) + cols * (rows - 1)
    return {
        "rows": rows, "cols": cols, "n_qubits": qubits,
        "n_couplings": couplings,
        "n_neighbors_max": 4 if (rows > 1 and cols > 1) else (
            3 if (rows > 1 or cols > 1) else 0),
        "interact_radius_um": round(1.5 * pitch_x_um, 3),
        "span_x_um": round((cols - 1) * pitch_x_um, 3),
        "span_y_um": round((rows - 1) * pitch_y_um, 3),
    }


def heavy_hex_closed_form(rows: int, cols: int) -> Dict[str, Any]:
    """heavy-hex 规模（**实测值**，取自 `sc_topology_core.heavy_hex_topology`）。

    构造 = 蜂窝两子格 A/B（各度 3）+ 每条原始边中点插一个 qubit ⇒ **最大度恒 3**
    （无 4 邻居，IBM heavy-hex 的定义式）。下表为已实测登记档位：

    | rows×cols | 顶点 | 边 qubit | 总 qubit | 耦合 |
    |---|---|---|---|---|
    | 3×3 | 18 | 21 | 39 | 42 |
    | 4×5 | 40 | 51 | 91 | 102 |
    """
    key = (int(rows), int(cols))
    table = {
        (3, 3): {"vertices": 18, "edge_qubits": 21, "couplings": 42},
        (4, 5): {"vertices": 40, "edge_qubits": 51, "couplings": 102},
    }
    base = table.get(key)
    if base is None:
        raise ValueError("本闭式仅覆盖已登记档位 (3,3) / (4,5)")
    return dict(base, rows=key[0], cols=key[1],
                n_qubits=base["vertices"] + base["edge_qubits"],
                max_degree=3)


def hilbert_space_log2(n_qubits: int) -> float:
    """Hilbert 空间维数（log2）＝ 比特数（超导：2 能级/比特）。"""
    n = int(n_qubits)
    if n < 1:
        raise ValueError("n_qubits 须 ≥ 1")
    return float(n)


# ═══════════════════════════ 产出物探测（只读元信息）═══════════════════════
def _artifact_manifest(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """探测 `examples/` 下超导芯片产出物**元信息**（文件名 + 字节数）。

    🔴 **聚合扫描**：源码仓里产出物分散在 `examples/` 与 `lda/examples/` 两处
    （S1 早期产物在顶层、S2+ 在包内）⇒ 逐个候选目录扫描后**按文件名去重合并**。

    🔴 只 `stat`，不读内容、不解析 GDS ⇒ 微秒级；目录都不存在的（如生产部署只装
    `lda/` 而 `examples/` 未随包分发）则优雅降级为 `available=False`。
    """
    root = repo_root
    if root is None:
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
    items: Dict[str, int] = {}
    hits: List[str] = []
    for d in _ARTIFACT_DIRS:
        p = os.path.join(root, d)
        if not os.path.isdir(p):
            continue
        hits.append(d)
        try:
            names = sorted(os.listdir(p))
        except OSError:
            continue
        for nm in names:
            if not nm.startswith("lda_schip") or nm.endswith(".py"):
                continue
            fp = os.path.join(p, nm)
            try:
                if os.path.isfile(fp):
                    items[nm] = int(os.path.getsize(fp))
            except OSError:
                continue
    if not hits:
        return {"available": False, "root_hint": _ARTIFACT_DIRS[0], "count": 0,
                "items": [],
                "note": "产出物目录不在本部署内（源码仓才含 examples/）"}
    lst = [{"name": k, "bytes": v} for k, v in sorted(items.items())]
    return {"available": True, "dirs_scanned": hits,
            "root_hint": hits[0], "count": len(lst), "items": lst,
            "note": "只读元信息（文件名 + 字节数，已跨目录去重）；"
                    "在线生成请走源码仓的 examples/lda_schip_s5.py"}


def _measured_report(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """读 `examples/lda_schip_s5.report.json`（若在）⇒ 用**真值**替代静态快照。

    读不到则返回 `{}`，由调用方回落静态表（优雅降级）。
    """
    root = repo_root
    if root is None:
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
    for d in _ARTIFACT_DIRS:
        fp = os.path.join(root, d, "lda_schip_s5.report.json")
        if os.path.isfile(fp):
            try:
                with open(fp, encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                return {}
    return {}


def _tiers_from_report(rep: Dict[str, Any]) -> Dict[str, Any]:
    """从实测 report 提取各族档位（缺项回落静态表）。"""
    grid, hexes = [], []
    for c in (rep.get("configs") or []):
        fam, tier = c.get("family"), c.get("tier")
        row = {"tier": tier, "qubits": c.get("n_qubits"),
               "elements": c.get("n_elements")}
        if fam == "grid" and c.get("n_qubits"):
            grid.append(row)
        elif fam == "heavy-hex" and c.get("n_qubits"):
            hexes.append(dict(row, vertices=c.get("n_vertices"),
                              edge_qubits=c.get("n_edge_qubits"),
                              couplings=c.get("n_couplings"),
                              max_degree=c.get("max_degree")))
    return {"grid": grid or GRID_TIERS, "hex": hexes or HEX_TIERS,
            "source": "examples/lda_schip_s5.report.json（实测）"
                      if (grid or hexes) else "内置快照（2026-09-29 实测）"}


# ═══════════════════════════════ 案例卡 ═══════════════════════════════
def case_card(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """组装超导芯片案例卡（只读 · 零重计算 · 免登录）。

    `verdict` 恒为 `DESIGN_SIGNOFF` —— **明标「设计期签核」而非实测**。
    """
    flag = capacity_closed_form(FLAGSHIP_ROWS, FLAGSHIP_COLS)
    rep = _measured_report(repo_root)
    tiers = _tiers_from_report(rep)
    gate_total = sum(m["gate"] for m in MILESTONES)
    return {
        "endpoint": "/api/schip_demo",
        "case_id": CASE_ID,
        "claim": "用 LDA 从零设计一颗超导 transmon 量子计算芯片：版图 + DRC/LVS + "
                 "频率避撞 + 串扰/损耗预算全链路签核，出真 GDSII",
        "verdict": "DESIGN_SIGNOFF",
        "verdict_label": "设计期签核（非流片实测）",
        "identity": {
            "physics": "超导 transmon（固定/可调频率）· 微波 QEDA",
            "device": "transmon 比特 + 可调耦合器（SQUID）+ 读出谐振腔/FDM 馈线 + "
                      "XY/Z/flux 控制线 + 阵列布线沟道",
            "unit": "transmon 单元 = 十字岛 + Josephson 结 + 孪生焊盘",
            "route_note": "量子两条路线之一（另一条为光量子 LOQC，见 /api/qchip_demo）；"
                          "两条均已走完 LDA 真 GDS 闭环",
            "gds_layers": {"FILM": 10, "JJ": 11, "GROUND": 12},
            "zero_quantum_sdk": True,
        },
        "span": {
            "milestones": len(MILESTONES),
            "gate_checks": gate_total,
            "modules": 10,
            "module_lines": 5633,
            "probe_mutations": 18,
        },
        "milestones": MILESTONES,
        "findings": FINDINGS,
        "gaps": GAPS,
        "gaps_total": len(GAPS),
        "flagship": {
            "kind": "grid（方阵 · 4 邻居）",
            "rows": flag["rows"], "cols": flag["cols"],
            "n_qubits": flag["n_qubits"],
            "n_couplings": flag["n_couplings"],
            "n_elements": FLAGSHIP_FACTS["n_elements"],
            "n_signals": FLAGSHIP_FACTS["n_signals"],
            "pitch_y_eff_um": FLAGSHIP_FACTS["pitch_y_eff_um"],
            "hilbert_log2_dim": hilbert_space_log2(flag["n_qubits"]),
            "freq_plan_seconds": FLAGSHIP_FACTS["freq_plan_seconds"],
            "max_stray_zz_mhz": FLAGSHIP_FACTS["max_stray_zz_mhz"],
            "zz_limit_mhz": ZZ_STRAY_LIMIT_MHZ,
            "t1_us_min": FLAGSHIP_FACTS["t1_us_min_n_le_1024"],
            "t1_target_us": T1_TARGET_US,
            "design_rules": {
                "drc_grid": 14, "lvs_grid": 11,
                "drc_heavy_hex": 6, "lvs_heavy_hex": 6,
            },
        },
        "scale_tiers": {
            "grid": tiers["grid"],
            "heavy_hex": tiers["hex"],
            "pressure": REFERENCE_TIERS,
            "source": tiers["source"],
            "note": "规模 = **版图容量**（可排布且可签核的比特数），非已制备器件数",
        },
        "physics": {
            "f01_ghz": F01_GHZ,
            "anharmonicity_ghz": ALPHA_GHZ,
            "f01_rel_err_vs_koch": 0.0042,
            "coupler_J_on_mhz": 0.400,
            "coupler_J_off_mhz": 0.0074,
            "coupler_off_ratio": 54.3,
            "coupler_J_rel_err": 0.046,
            "g_CR_mhz": 2.59, "t_CR_us": 1.21, "sigma_zz_mhz": 0.21,
            "t1_target_us": T1_TARGET_US,
            "zz_stray_limit_mhz": ZZ_STRAY_LIMIT_MHZ,
        },
        "topology_capacity": {
            "grid": capacity_closed_form(FLAGSHIP_ROWS, FLAGSHIP_COLS),
            "heavy_hex_3x3": heavy_hex_closed_form(3, 3),
            "heavy_hex_4x5": heavy_hex_closed_form(4, 5),
        },
        "artifacts": _artifact_manifest(repo_root),
        "ui": {
            "found_in_ui": True,
            "entry": "验证实力（accept）→「超导量子芯片案例」卡",
            "related_panels": [
                "㊿ QEDA 求解器级补强 · transmon-resonator 色散读出（三能级严格求解）",
                "51 QEDA 纵深三件套（多能级展开 · 驱动场 Rabi/AC Stark · 读出串扰 ZZ 耦合）",
            ],
            "scope_note": "UI 量子面板覆盖**器件物理仿真**；本卡覆盖**芯片级 P&R 与签核**，"
                          "二者互补。",
        },
        "positioning": _positioning(),
        "honest_note": SCHIP_HONEST_NOTE,
    }


def _positioning() -> Dict[str, Any]:
    """先进性定位（公开来源 · 只作背景，不与本案例同台比较）。"""
    return {
        "disclaimer": "下列为 2026 年公开报道的**产业界已交付芯片**数字，仅作背景坐标；"
                      "本案例为**设计期签核**，两者**不同台比较**。",
        "public_landscape": [
            {"who": "IBM", "item": "Heron r2/r3 156 qubit（固定频率 transmon + "
                                    "可调耦合器）；Condor 1,121 qubit（2023，缩放里程碑）；"
                                    "Nighthawk 120 qubit 方格 4-度连通"},
            {"who": "IBM", "item": "2026 Kookaburra 路线（qLDPC 量子存储 + 逻辑处理单元，"
                                   "目标 ≤360 qubit / 7,500 门）"},
            {"who": "Google", "item": "Willow 105 qubit · 2024-12 首次 below-threshold "
                                     "纠错（3×3→5×5→7×7 surface code 指数抑制）"},
            {"who": "中国", "item": "祖冲之 3.2 107 qubit（全微波控制，低于阈值纠错）；"
                                    "祖冲之 3.0 105 qubit / 182 耦合器"},
            {"who": "Fujitsu + RIKEN", "item": "256 qubit 超导（2025-04），目标 1,000 qubit"},
            {"who": "Rigetti / IQM", "item": "Ankaa-3 84 qubit · Cepheus-1 108 qubit；"
                                            "Radiance 150 qubit（二比特门保真 99.91%）"},
        ],
        "what_is_different": [
            {"axis": "交付物", "industry": "已制备芯片 + 云访问",
             "lda": "**设计期签核**：真 GDSII + DRC/LVS + 预算，可复现、可审计"},
            {"axis": "工具链来源", "industry": "各自闭源 CAD/PDK 栈 + Qiskit 等 SDK",
             "lda": "**开源（MIT）· Agent-native · 零量子 SDK**：物理内核自研，"
                    "判决不依赖外部量子框架"},
            {"axis": "判决路径", "industry": "通常为实验标定 + 数值仿真混合",
             "lda": "**LLM 不进判决路径**：判决为死标量比对；红线为物理定律锚"},
            {"axis": "拓扑", "industry": "heavy-hex（IBM Heron）→ Nighthawk 改方格 4-度",
             "lda": "**两种拓扑共用一份 DRC/LVS 引擎**（度上限自声明：方阵 4 / hex 3）"},
            {"axis": "规模口径", "industry": "已交付比特数（156 / 105 / 107）",
             "lda": "**版图容量**（1024 可排布且可签核）——口径不同，不可直接比数"},
        ],
        "honest_limits": [
            "无数值/保真度同台比较：LDA 不宣称在门保真度、相干时间或纠错阈值上优于任何厂商。",
            "不宣称「量子优势」：本案例不涉及任何计算优势主张。",
            "规模数字须按「版图容量」解读，误读成「已制备 1024 比特芯片」即为失真。",
        ],
    }


# ═══════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。闭式断言 + 红线断言（不 import 求解器）。"""
    res: Dict[str, bool] = {}
    msgs: List[str] = []

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)
        msgs.append(f"{'PASS' if cond else 'FAIL'} | {name}")

    # ① 容量闭式：32×32 ⇒ 1024 qubit / 1984 耦合
    f = capacity_closed_form(32, 32)
    chk("① 32×32 容量闭式：1024 qubit · 1984 耦合 · 4 邻居",
        f["n_qubits"] == 1024 and f["n_couplings"] == 1984 and f["n_neighbors_max"] == 4)

    # ② 耦合数闭式与逐点枚举一致（N=2..8 方阵）
    ok = True
    for k in range(2, 9):
        want = 2 * k * (k - 1)
        ok = ok and capacity_closed_form(k, k)["n_couplings"] == want
    chk("② 方阵耦合数 ≡ 2k(k−1)（k=2..8 逐点）", ok)

    # ③ 交互半径 = 1.5·pitch_x（频率避撞约束范围）
    chk("③ 交互半径 = 1.5 × pitch_x = 33.0 µm",
        abs(f["interact_radius_um"] - 33.0) < 1e-9)

    # ④ heavy-hex 实测：3×3 ⇒ 39 qubit / 42 耦合；4×5 ⇒ 91 qubit / 102 耦合
    h33 = heavy_hex_closed_form(3, 3)
    h45 = heavy_hex_closed_form(4, 5)
    chk("④ heavy-hex：3×3 ⇒ 39 qubit/42 耦合 · 4×5 ⇒ 91 qubit/102 耦合 · 度恒 3",
        h33["n_qubits"] == 39 and h33["couplings"] == 42
        and h45["n_qubits"] == 91 and h45["couplings"] == 102
        and h33["max_degree"] == 3 == h45["max_degree"])

    # ⑤ Hilbert 维数 = 比特数（超导 2 能级/比特）
    chk("⑤ Hilbert log2 维数 ≡ 比特数（1024 ⇒ 1024.0）",
        abs(hilbert_space_log2(1024) - 1024.0) < 1e-12)

    # ⑥ 案例卡组装：5 里程碑 · 5 结论 · 5 缺口 · 判据合计 200
    card = case_card(repo_root="__nonexistent_root__")
    chk("⑥ 案例卡组装：5 里程碑 / 5 结论 / 5 缺口 / 门禁判据合计 200",
        len(card["milestones"]) == 5 and len(card["findings"]) == 5
        and card["gaps_total"] == 5 and card["span"]["gate_checks"] == 200)

    # ⑦ 产出物优雅降级（root 不存在 ⇒ available False，不抛错）
    chk("⑦ 产出物探测优雅降级（root 不存在 ⇒ available=False）",
        card["artifacts"]["available"] is False)

    # ⑧ 🔴 不伪装实测：verdict 恒 DESIGN_SIGNOFF，且诚实边界齐全
    note = card["honest_note"]
    chk("⑧ 不伪装实测：verdict=DESIGN_SIGNOFF · 诚实边界含「非流片后实测」/「非 PDK」/"
        "「不含纠错码」",
        card["verdict"] == "DESIGN_SIGNOFF"
        and "非流片后实测" in note and "非任何 foundry 的 PDK deck" in note
        and "不含纠错码" in note)

    # ⑨ 🔴 先进性与产业界不同台比较（disclaimer + 诚实限制 全在）
    pos = card["positioning"]
    chk("⑨ 先进性定位：含不同台比较声明 + 3 条诚实限制",
        bool(pos["disclaimer"]) and len(pos["honest_limits"]) == 3
        and len(pos["public_landscape"]) >= 5)

    # ⑩ 🔴 规模口径必须写「版图容量」（防被误读为已制备芯片）
    chk("⑩ 规模口径明标「版图容量」（非已制备器件数）",
        "版图容量" in card["scale_tiers"]["note"])

    # ⑪ 零量子 SDK 声明（结构计数：本模块不 import 任何量子框架）
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    banned = ("qiskit", "cirq", "pennylane", "qutip", "braket", "projectq")
    hit = [b for b in banned if f"import {b}" in src.lower()]
    chk("⑪ 零量子 SDK：本模块无任何外部量子框架 import", not hit)

    # ⑫ 护栏：非法输入抛错（N < 1 / 未登记 hex 档位）
    guard = 0
    for bad in (lambda: capacity_closed_form(0, 4),
                lambda: heavy_hex_closed_form(9, 9),
                lambda: hilbert_space_log2(0)):
        try:
            bad()
        except ValueError:
            guard += 1
    chk("⑫ 护栏：非法 rows/cols · 未登记 hex 档位 · n_qubits<1 均抛 ValueError",
        guard == 3)

    ok_all = all(res.values())
    if verbose:
        for m in msgs:
            print("  " + m)
    return ok_all


if __name__ == "__main__":
    print("超导芯片案例卡自检：", "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
