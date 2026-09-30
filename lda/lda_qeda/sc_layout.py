"""D-133 · 超导 transmon 单元版图 + 几何 DRC/LVS 签核（S1 · 吃狗粮）。

把 LDA 从「只能仿真 transmon」（D-35 transmon_solver / D-41 quantum_design 逆设计）
推进到「能画出超导单元版图并走完 DRC/LVS 签核」——这是 LOQC 征程（D-113..D-132）
已证的光子 GDS 闭环在**超导**侧的对应物。光子闭环走通了；超导先前只有理论锚/
仿真、无版图/DRC/LVS，本模块补齐版图原语 + 几何签核，让平台「先能设计出来」。

🔴 **订正（2026-09-30）**：「超导无版图/DRC/LVS」为**本模块建成前**的历史状态；
超导征程 LDA-S1…S5（D-133…D-145）现已走完真 GDS + DRC/LVS + 频率避撞 +
串扰/损耗预算全闭环（最大 1024 qubit / 32×32 / 10244 元件；heavy-hex 91 qubit）。
对照见 `LDA_超导量子计算芯片设计与成果总结_2026-09-30.md`。

能力（单一真源复用 gds_export.geometry_desc 的 Transmon kind）：
  - transmon_cell(params)        → geometry_desc 列表（带 net 语义标签）
  - transmon_gds(params, path)   → 真出 GDSII（零依赖自写编码器）
  - transmon_svg_preview(params) → 版图 SVG 预览（浏览器可看）
  - run_sc_drc(elements, limits) → 超导几何 DRC（最小线宽/间隙/JJ 尺寸/地间距/短接）
  - sc_lvs_signoff(elements)     → 几何 LVS（qubit↔JJ↔ground 连接性 + 端口附着 + 零悬空）
  - run_selfchecks()             → 合法 ACCEPT/ACCEPT；四类违规各 REJECT

几何 LVS 做法（诚实）：不重放设计意图，而是对**实际 produced 几何**做 bbox 重叠
提取网表——JJ 须同时覆盖两岛屿（桥接）、每根 qubit 导体须在同一连通分量、
地与 qubit 不得重叠（间隙被几何尊重）、无孤立导体。

红线：纯几何（标准库即可，零 numpy 也够）、LLM 不进判决路径；限值为**设计规则**
（可覆盖 · 非实测 golden · Foundry PDK 属 D5 外部依赖）。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from lda_l2 import gds_export as G

# 超导层（与 gds_export 同源）
FILM = G.LIB_LAYER_SC_FILM
JJ = G.LIB_LAYER_SC_JJ
GROUND = G.LIB_LAYER_SC_GROUND
LIB_LAYER_SC_FILM = G.LIB_LAYER_SC_FILM
LIB_LAYER_SC_JJ = G.LIB_LAYER_SC_JJ
LIB_LAYER_SC_GROUND = G.LIB_LAYER_SC_GROUND

SCD_RULES = (
    "SCD-MIN-WIDTH",          # 导体最小线宽
    "SCD-MIN-JJ",             # 约瑟夫森结最小尺寸
    "SCD-MIN-GROUND-GAP",     # qubit 导体到地平面最小间隙
    "SCD-QUBIT-GROUND-SHORT", # qubit 导体与地平面不得重叠（短接）
)
DEFAULT_DRC_LIMITS = {
    "min_width_um": 0.2,       # 设计规则（可覆盖 · 非实测 golden）
    "min_jj_um": 0.15,
    "min_ground_gap_um": 0.5,
}

RED_LINE_DISCLOSURE = {
    "role": "D-133 = 超导 transmon 单元版图 + 几何 DRC/LVS 签核（S1）："
            "补齐平台「能设计超导芯片」的版图/签收闭环（光子侧已由 D-113..D-132 证）",
    "layers": "SC_FILM=10 / SC_JJ=11 / SC_GROUND=12（gds_export 定义，非 Foundry PDK）",
    "limits": "min_width/min_jj/min_ground_gap 为**设计规则 · 可覆盖 · 非实测 golden**"
              "（Foundry PDK 层规/金属栈属 D5 外部依赖，平台不沾）",
    "lvs": "几何 LVS 对**实际 produced 几何**做 bbox 重叠网表提取（不重放意图）",
    "red_line": "纯几何（标准库，零 numpy 即可）、LLM 不进判决路径、零量子 SDK",
}
ROLE = RED_LINE_DISCLOSURE["role"]


# ---------------------------------------------------------------------------
# 几何工具（bbox / 重叠 / 元素提取）
# ---------------------------------------------------------------------------
def _bbox(d: Dict) -> Tuple[float, float, float, float]:
    """元素 bbox (xmin, xmax, ymin, ymax)。path 含 width；boundary 取 rings。"""
    if d["kind"] == "path":
        w = float(d.get("width_um", 0.0)) / 2.0
        xs = [p[0] for p in d["points_um"]]
        ys = [p[1] for p in d["points_um"]]
        return (min(xs) - w, max(xs) + w, min(ys) - w, max(ys) + w)
    pts = [p for r in d["rings_um"] for p in r]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), max(xs), min(ys), max(ys))


def _overlap(a: Tuple[float, float, float, float],
             b: Tuple[float, float, float, float], tol: float = 1e-9) -> bool:
    xmin_a, xmax_a, ymin_a, ymax_a = a
    xmin_b, xmax_b, ymin_b, ymax_b = b
    return not (xmax_a < xmin_b - tol or xmin_a > xmax_b + tol
                or ymax_a < ymin_b - tol or ymin_a > ymax_b + tol)


def _ring_pts(d: Dict) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    for r in d.get("rings_um", []):
        pts.extend(r)
    return pts


def transmon_cell(params: Optional[Dict] = None) -> List[Dict]:
    """Transmon 单元几何元素（带 net 标签），单一真源 = gds_export.geometry_desc。"""
    return G.geometry_desc("Transmon", params or {})


# ---------------------------------------------------------------------------
# GDS / SVG 出口
# ---------------------------------------------------------------------------
def transmon_gds(params: Optional[Dict] = None, path: str = "transmon.gds") -> bytes:
    """真出 GDSII（零依赖自写编码器）。返回文件字节。"""
    elems = G.layout_elements("Transmon", params or {})
    data = G.gds_library("LDA-SC", {"transmon": elems})
    G.write_gds(path, data)
    return data


def transmon_svg_preview(params: Optional[Dict] = None, width: int = 480) -> str:
    """版图 SVG 预览（按 net 上色：qubit=蓝 / jj=红 / ground=灰）。"""
    descs = transmon_cell(params)
    layer_color = {FILM: "#2563eb", JJ: "#e11d48", GROUND: "#94a3b8"}
    xs, ys = [], []
    for d in descs:
        pts = d.get("points_um") or _ring_pts(d)
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
        col = layer_color.get(d["layer"], "#2563eb")
        pts = d.get("points_um") or _ring_pts(d)
        dd = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in pts)
        if d["kind"] == "path":
            out.append(f'<polyline points="{dd}" fill="none" stroke="{col}" '
                       f'stroke-width="{max(d.get("width_um", 0.5) * S, 2):.1f}"/>')
        else:
            out.append(f'<polygon points="{dd}" fill="{col}" fill-opacity="0.7"/>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------
# 超导几何 DRC
# ---------------------------------------------------------------------------
def run_sc_drc(elements: List[Dict], limits: Optional[Dict] = None) -> Dict:
    """超导几何 DRC：最小线宽 / JJ 尺寸 / 地间距 / 短接。

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

    qubit_boxes: List[Tuple] = []
    ground_boxes: List[Tuple] = []
    for d in elements:
        layer = d["layer"]
        bb = _bbox(d)
        if d["kind"] == "path" and layer == FILM:
            checked += 1
            if float(d.get("width_um", 0.0)) < min_w - 1e-12:
                violations.append({"rule": "SCD-MIN-WIDTH",
                                    "detail": f"CPW 馈线宽 {d['width_um']:.3f} µm < {min_w:.3f} µm"})
        elif d["kind"] == "boundary" and layer == FILM:
            checked += 1
            thin = min(bb[1] - bb[0], bb[3] - bb[2])
            if thin < min_w - 1e-12:
                violations.append({"rule": "SCD-MIN-WIDTH",
                                    "detail": f"岛屿最薄边 {thin:.3f} µm < {min_w:.3f} µm"})
            qubit_boxes.append(bb)
        elif d["kind"] == "boundary" and layer == JJ:
            checked += 1
            jd = min(bb[1] - bb[0], bb[3] - bb[2])
            if jd < min_jj - 1e-12:
                violations.append({"rule": "SCD-MIN-JJ",
                                    "detail": f"JJ 最薄边 {jd:.3f} µm < {min_jj:.3f} µm"})
        elif d["kind"] == "boundary" and layer == GROUND:
            ground_boxes.append(bb)

    if qubit_boxes and ground_boxes:
        qx0 = min(b[0] for b in qubit_boxes)
        qx1 = max(b[1] for b in qubit_boxes)
        qy0 = min(b[2] for b in qubit_boxes)
        qy1 = max(b[3] for b in qubit_boxes)
        qbb = (qx0, qx1, qy0, qy1)
        for gb in ground_boxes:
            checked += 1
            if _overlap(qbb, gb):
                violations.append({"rule": "SCD-QUBIT-GROUND-SHORT",
                                    "detail": "qubit 导体与地平面几何重叠（短接）"})
                continue
            dx = max(gb[0] - qx1, qx0 - gb[1], 0.0)
            dy = max(gb[2] - qy1, qy0 - gb[3], 0.0)
            gap = math.hypot(dx, dy) if (dx > 0 or dy > 0) else 0.0
            if gap < min_gap - 1e-9:
                violations.append({"rule": "SCD-MIN-GROUND-GAP",
                                    "detail": f"qubit→地间隙 {gap:.3f} µm < {min_gap:.3f} µm"})

    verdict = "ACCEPT" if not violations else "REJECT"
    return {"verdict": verdict, "violations": violations,
            "n_rules": len(SCD_RULES), "limits": lim, "checked": checked}


# ---------------------------------------------------------------------------
# 超导几何 LVS（网表提取 + 连接性）
# ---------------------------------------------------------------------------
def sc_lvs_signoff(elements: List[Dict]) -> Dict:
    """几何 LVS：对**实际 produced 几何**做 bbox 重叠网表提取。

    判据：① 每导体有 net（零悬空标签）② 存在 JJ ③ JJ 须桥接 ≥2 个 qubit 导体
    （岛屿不断开）④ qubit 导体全在同一连通分量（重叠或 JJ 桥接）⑤ 地与 qubit
    不重叠（短接）⑥ ≥2 根 qubit 端口臂（readout + flux）。
    返回 {verdict, issues, netlist, n_checks}。
    """
    issues: List[str] = []
    n_checks = 0

    cond = [(d["layer"], d.get("net", ""), _bbox(d))
            for d in elements if d["kind"] in ("path", "boundary")]
    n_checks += 1
    if any(not net for (_L, net, _bb) in cond):
        issues.append("SCD-LVS-NO-NET: 存在无 net 标签的导体元素")

    qubit = [(L, net, bb) for (L, net, bb) in cond if net == "qubit"]
    jj = [(L, net, bb) for (L, net, bb) in cond if net == "jj"]
    ground = [(L, net, bb) for (L, net, bb) in cond if net == "ground"]

    n_checks += 1
    if not jj:
        issues.append("SCD-LVS-NO-JJ: 无约瑟夫森结元素")
    else:
        jj_ok = False
        for (_L, _n, jbb) in jj:
            touched = [bb for (L, net, bb) in qubit if _overlap(jbb, bb)]
            if len(touched) >= 2:
                jj_ok = True
                break
        if not jj_ok:
            issues.append("SCD-LVS-JJ-NOT-BRIDGING: JJ 未同时桥接 ≥2 个 qubit 导体（岛屿断开）")

    n_checks += 1
    parent = list(range(len(qubit)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(qubit)):
        for j in range(i + 1, len(qubit)):
            if _overlap(qubit[i][2], qubit[j][2]):
                union(i, j)
    for (_L, _n, jbb) in jj:
        idxs = [k for k, (L, net, bb) in enumerate(qubit) if _overlap(jbb, bb)]
        for k in range(1, len(idxs)):
            union(idxs[0], idxs[k])
    comps = set(find(i) for i in range(len(qubit)))
    if qubit and len(comps) > 1:
        issues.append(f"SCD-LVS-FLOATING-QUBIT: qubit 导体分成 {len(comps)} 个孤立分量（含悬空岛）")

    n_checks += 1
    short = any(_overlap(qbb, gbb) for (_Lq, _nq, qbb) in qubit
                for (_Lg, _ng, gbb) in ground)
    if short:
        issues.append("SCD-LVS-QUBIT-GROUND-SHORT: qubit 导体与地平面重叠（短接）")

    n_checks += 1
    arms = [d for d in elements if d.get("net") == "qubit" and d["kind"] == "path"]
    if len(arms) < 2:
        issues.append("SCD-LVS-PORTS: qubit 端口臂 < 2（readout/flux 须各一）")

    verdict = "ACCEPT" if not issues else "REJECT"
    return {"verdict": verdict, "issues": issues,
            "netlist": {"qubit": len(qubit), "jj": len(jj), "ground": len(ground),
                        "qubit_components": len(comps) if qubit else 0},
            "n_checks": n_checks}


# ---------------------------------------------------------------------------
# 自检（常驻断言：合法 ACCEPT/ACCEPT；四类违规各 REJECT）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    ok = True
    msgs: List[Tuple[str, bool]] = []

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        msgs.append((name, bool(cond)))

    base: Dict = {}
    el = transmon_cell(base)
    chk("① 合法单元 DRC ACCEPT", run_sc_drc(el)["verdict"] == "ACCEPT")
    chk("② 合法单元 LVS ACCEPT", sc_lvs_signoff(el)["verdict"] == "ACCEPT")

    el3 = transmon_cell({"cpw_w": 0.1})
    chk("③ CPW 太细 ⇒ DRC REJECT", run_sc_drc(el3)["verdict"] == "REJECT")

    el4 = transmon_cell({"jj_len": 0.1})
    chk("④ JJ 不桥接 ⇒ LVS REJECT", sc_lvs_signoff(el4)["verdict"] == "REJECT")

    el5 = transmon_cell(base) + [{"kind": "boundary", "layer": FILM, "net": "qubit",
                                   "rings_um": [[(40, 40), (42, 40), (42, 42), (40, 42)]]}]
    chk("⑤ 悬空导体 ⇒ LVS REJECT", sc_lvs_signoff(el5)["verdict"] == "REJECT")

    el6 = transmon_cell({"ground_gap": -0.5})
    chk("⑥ 地短接 ⇒ DRC REJECT", run_sc_drc(el6)["verdict"] == "REJECT")
    chk("⑦ 地短接 ⇒ LVS REJECT", sc_lvs_signoff(el6)["verdict"] == "REJECT")

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok
