"""D-141 · 超导征程 S5 P1：控制多线几何（XY/Z/coupler-flux）+ 逐线串扰预算 + 签核。

S4（D-136）每 qubit 只有**一条**控制桩（几何 stub）。真实超导 qubit 的片上控制需要
**多线分工**：XY 微波驱动线 + Z 磁通偏置线 + 耦合器磁通线（可调耦合器的 flux）。
G5 把单桩升级为**三线分离**（同 qubit 三条平行走线、线型各异），并逐线给串扰预算。

能力（纯几何 + 闭式，零量子 SDK）：
  • control_array_cell(params)  → S4 阵列几何 + 每 qubit 三条控制线（xy/z/cflux，net=control
                                   + control_role 标签），几何上互不重叠且与地留隙
  • run_control_drc(els)        → S4 十则 + 三线二则（线间距 / 线宽，设计规则）
  • control_lvs(els, params)    → S4 九判据 + 「每 qubit 恰三线且角色互异」判据
  • line_xtalk_budget(params)   → 逐线串扰：平行段 fringe 电容 C_x=ε_eff·ε0·Lc·t/gap → X=C_x/C_q
                                  （复用 S4 闭式），分「同 qubit 内线对（xy↔z 等）」与
                                  「相邻 qubit 同角色线」两类，各有上限
  • control_physics(params)     → 逐线串扰预算 ACCEPT（含 XY↔Z 隔离）
  • run_selfchecks()

诚实边界（与 S1–S4 一致）：
  • ε_eff / t_film / C_q / 线宽为**设计参数**，非实测 PDK（属 D5）；闭式公式为确定性物理定律。
  • 串扰为**平行段 fringe 电容闭式估计**，非全波电磁仿真（属 D5）。
  • 三线为片上 stub，键合焊盘/穿片互连在片外（未建模）。
红线：纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、限值为设计规则。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from lda_l2 import gds_export as G
from lda_qeda import sc_readout as S4
from lda_qeda.sc_coupler import _bbox

FILM = G.LIB_LAYER_SC_FILM
JJ = G.LIB_LAYER_SC_JJ
GROUND = G.LIB_LAYER_SC_GROUND

CTRL_ROLES = ("xy", "z", "cflux")          # 微波驱动 / 磁通偏置 / 耦合器磁通
_CTRL_WIDTH = {"xy": 0.6, "z": 0.8, "cflux": 0.6}     # 各线型默认线宽（µm，设计参数）

DEFAULT_CTRL_LIMITS = dict(S4.DEFAULT_READOUT_LIMITS)
DEFAULT_CTRL_LIMITS.update({
    "ctrl_line_pitch_um": 1.2,        # 同 qubit 三线中心间距（设计规则 · 可覆盖）
    "min_ctrl_line_gap_um": 0.3,      # 三线间最小边到边间隙
    "min_ctrl_line_width_um": 0.3,    # 单线最小线宽
})
CTRL_DRC_RULES = tuple(list(S4.READOUT_DRC_RULES) + [
    "SCD-CTRL-LINE-SPACING",      # 同 qubit 三线边到边间隙 ≥ 下限
    "SCD-CTRL-LINE-MIN-WIDTH",    # 单条控制线最小线宽
])

CTRL_XTALK_LIMIT = 0.05           # 同角色线间串扰系数上限（复用 S4 口径）
CTRL_ISOLATION_LIMIT = 1e-3       # XY↔Z 隔离（交叉线型，要求更严）

RED_LINE_DISCLOSURE = {
    "role": "D-141 = 超导征程 S5 P1：控制多线几何（XY/Z/coupler-flux 三线分离）"
            "+ 逐线串扰预算 + 签核，把 S4 的单控制桩升级为真实多线控制",
    "layers": "SC_FILM=10 / SC_JJ=11 / SC_GROUND=12（gds_export 定义，非 Foundry PDK）；"
              "三条控制线均布 FILM 层，以 net=control + control_role 区分",
    "limits": "ctrl_line_pitch / min_ctrl_line_gap / min_ctrl_line_width 为**设计规则 · "
              "可覆盖 · 非实测 golden**（Foundry PDK 属 D5 外部依赖）",
    "lvs": "几何 LVS 复用 S4 九判据 + 「每 qubit 恰三条控制线且角色互异（xy/z/cflux）」，"
           "对**实际 produced 几何**做 bbox 重叠网表提取",
    "physics": "逐线串扰 = 平行段 fringe 电容闭式 C_x=ε_eff·ε0·Lc·t/gap → X=C_x/C_q"
               "（复用 S4 口径）；分同 qubit 内线对与相邻 qubit 同角色线两类，各有上限",
    "control": "XY=微波驱动、Z=磁通偏置、cflux=耦合器磁通；三线几何分离 + 逐线预算",
    "red_line": "纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、"
                "控制线为片上 stub（键合/穿片互连片外未建模）",
}
ROLE = RED_LINE_DISCLOSURE["role"]


# ---------------------------------------------------------------------------
# 几何单元（S4 阵列 + 每 qubit 三线分离）
# ---------------------------------------------------------------------------
def control_array_cell(params: Optional[Dict] = None) -> List[Dict]:
    """S4 阵列 + 每 qubit 三条控制线（xy/z/cflux）。

    单一真源 = S4.readout_array_cell；把其单条控制桩替换为三条平行 stub
    （中心偏移 −p/0/+p，线宽按角色），每条 net="control" + control_role 标签，
    仍垂直向下桥接本 qubit、落入沟道、留地间隙。
    """
    p = dict(params or {})
    pitch = float(p.get("ctrl_line_pitch", DEFAULT_CTRL_LIMITS["ctrl_line_pitch_um"]))
    control_len = float(p.get("control_len", 4.0))
    out: List[Dict] = []
    for d in S4.readout_array_cell(p):
        if d.get("net") == "control":
            qid = d.get("qubit_id")
            x0, y0 = d["points_um"][0]
            x1 = d["points_um"][1][0]
            for k, role in enumerate(CTRL_ROLES):
                off = (k - 1) * pitch
                out.append({"kind": "path", "layer": FILM, "net": "control",
                            "control_role": role, "qubit_id": qid,
                            "width_um": _CTRL_WIDTH[role],
                            "points_um": [(x0 + off, y0), (x1 + off, y0 - control_len)]})
        else:
            out.append(d)
    return out


def control_gds(params: Optional[Dict] = None, path: str = "sc_control.gds") -> bytes:
    """真出 GDSII（零依赖自写编码器）。返回文件字节。"""
    descs = control_array_cell(params)
    recs: List[bytes] = []
    for d in descs:
        if d["kind"] == "path":
            recs.append(G.path(d["layer"], d["width_um"], d["points_um"]))
        else:
            recs.append(G.boundary(d["layer"], G._flatten_rings(d.get("rings_um"))))
    data = G.gds_library("LDA-SC-CONTROL", {"sc_control": recs})
    G.write_gds(path, data)
    return data


def control_svg_preview(params: Optional[Dict] = None, width: int = 620) -> str:
    """版图 SVG 预览（三线按角色上色：xy=紫 / z=靛 / cflux=粉）。"""
    descs = control_array_cell(params)
    role_color = {"xy": "#7c3aed", "z": "#4338ca", "cflux": "#db2777"}
    net_color = {"qubit": "#2563eb", "jj": "#e11d48", "coupler": "#f59e0b",
                 "readout": "#16a34a", "feedline": "#0891b2", "ground": "#e2e8f0"}
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
        if d.get("control_role"):
            col = role_color[d["control_role"]]
        else:
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
# DRC（S4 十则 + 三线二则）
# ---------------------------------------------------------------------------
def run_control_drc(elements: List[Dict],
                    limits: Optional[Dict] = None) -> Dict:
    """多线控制几何 DRC = S4 十则 + SCD-CTRL-LINE-SPACING + SCD-CTRL-LINE-MIN-WIDTH。"""
    lim = dict(DEFAULT_CTRL_LIMITS)
    if limits:
        lim.update(limits)
    base = S4.run_readout_drc(elements, limits)
    violations = list(base["violations"])

    ctrls = [d for d in elements if d.get("net") == "control"]
    # 单线最小线宽
    for d in ctrls:
        w = float(d.get("width_um", 0.0))
        if w < lim["min_ctrl_line_width_um"] - 1e-12:
            violations.append({"rule": "SCD-CTRL-LINE-MIN-WIDTH",
                               "detail": f"控制线宽 {w:.3f}"
                                         f"<{lim['min_ctrl_line_width_um']}"})

    # 同 qubit 三线边到边间隙（同 qubit_id 的线对）
    by_q: Dict[int, List[Dict]] = {}
    for d in ctrls:
        by_q.setdefault(d.get("qubit_id"), []).append(d)
    min_gap = float("inf")
    for _q, group in by_q.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                bi, bj = _bbox(group[i]), _bbox(group[j])
                dx = max(bi[0] - bj[1], bj[0] - bi[1], 0.0)
                dy = max(bi[2] - bj[3], bj[2] - bi[3], 0.0)
                min_gap = min(min_gap, math.hypot(dx, dy))
    if ctrls and min_gap < lim["min_ctrl_line_gap_um"] - 1e-9:
        violations.append({"rule": "SCD-CTRL-LINE-SPACING",
                           "detail": f"同 qubit 三线最小间隙 {min_gap:.3f}"
                                     f"<{lim['min_ctrl_line_gap_um']}"})

    verdict = "ACCEPT" if not violations else "REJECT"
    return {"verdict": verdict, "violations": violations,
            "n_rules": len(CTRL_DRC_RULES), "limits": lim,
            "min_line_gap_um": (None if min_gap == float("inf") else float(min_gap))}


# ---------------------------------------------------------------------------
# LVS（S4 九判据 + 三线角色互异）
# ---------------------------------------------------------------------------
def control_lvs(elements: List[Dict]) -> Dict:
    """多线控制几何 LVS = S4 九判据 + 「每 qubit 恰三线且角色互异」。"""
    base = S4.readout_lvs_signoff(elements)
    issues = list(base["issues"])
    n_checks = base["n_checks"] + 1

    by_q: Dict[int, List[str]] = {}
    for d in elements:
        if d.get("net") == "control":
            by_q.setdefault(d.get("qubit_id"), []).append(d.get("control_role"))

    qgroups = S4._qubit_groups(elements)
    for qid in qgroups:
        roles = by_q.get(qid, [])
        if len(roles) != len(CTRL_ROLES):
            issues.append(f"SCD-LVS-CTRL-LINE-COUNT: qubit {qid} 控制线={len(roles)}"
                          f"≠{len(CTRL_ROLES)}")
        elif set(roles) != set(CTRL_ROLES):
            issues.append(f"SCD-LVS-CTRL-ROLE-DUP: qubit {qid} 三线角色非互异 "
                          f"({sorted(roles)})")

    verdict = "ACCEPT" if not issues else "REJECT"
    return {"verdict": verdict, "issues": issues,
            "netlist": dict(base["netlist"],
                            control_lines=sum(len(v) for v in by_q.values()),
                            roles_per_qubit=len(CTRL_ROLES)),
            "n_checks": n_checks}


# ---------------------------------------------------------------------------
# 逐线串扰预算（fringe 电容闭式）
# ---------------------------------------------------------------------------
def _fringe_x(gap_um: float, length_um: float, params: Dict) -> float:
    """平行段 fringe 电容闭式 → 串扰系数 X=C_x/C_q（gap ≤ 0 ⇒ 强串扰 1.0）。"""
    if gap_um <= 1e-9:
        return 1.0
    eps_eff = float(params.get("eps_eff", 6.0))
    t_film = float(params.get("t_film_um", 0.05))
    C_q = float(params.get("C_q_fF", 50.0))
    eps0 = 8.854e-12
    c_x = eps_eff * eps0 * (length_um * 1e-6) * (t_film * 1e-6) / (gap_um * 1e-6)
    return float(c_x / (C_q * 1e-15))


def line_xtalk_budget(params: Optional[Dict] = None) -> Dict:
    """逐线串扰预算（同 qubit 内线对 + 相邻 qubit 同角色线）。

    对每个 qubit：三线中心间距 p、线宽按角色 w_i ⇒ 边到边 gap_ij = p·|i−j| − (w_i+w_j)/2；
    X_ij = fringe 闭式。另算相邻列同角色线的 X（gap ≈ pitch_x − 2p − w）。
    验收：所有 X ≤ CTRL_XTALK_LIMIT，且 XY↔Z 对 X ≤ CTRL_ISOLATION_LIMIT。
    """
    p = dict(params or {})
    rows = int(p.get("rows", 2))
    cols = int(p.get("cols", 2))
    pitch = float(p.get("ctrl_line_pitch", DEFAULT_CTRL_LIMITS["ctrl_line_pitch_um"]))
    pitch_x = float(p.get("pitch_x", 22.0))
    length = float(p.get("control_len", 4.0))

    intra: List[Dict] = []
    for a in range(len(CTRL_ROLES)):
        for b in range(a + 1, len(CTRL_ROLES)):
            ra, rb = CTRL_ROLES[a], CTRL_ROLES[b]
            gap = pitch * (b - a) - (_CTRL_WIDTH[ra] + _CTRL_WIDTH[rb]) / 2.0
            x = _fringe_x(gap, length, p)
            intra.append({"line_pair": [ra, rb], "gap_um": float(gap), "X": x})
    inter: List[Dict] = []
    for role in CTRL_ROLES:
        gap = pitch_x - 2.0 * pitch - _CTRL_WIDTH[role]
        x = _fringe_x(gap, length, p)
        inter.append({"role": role, "gap_um": float(gap), "X": x})

    max_intra = max((e["X"] for e in intra), default=0.0)
    max_inter = max((e["X"] for e in inter), default=0.0)
    xy_z = next((e["X"] for e in intra
                 if set(e["line_pair"]) == {"xy", "z"}), 0.0)
    max_x = max(max_intra, max_inter)
    xt_ok = bool(max_x <= CTRL_XTALK_LIMIT)
    iso_ok = bool(xy_z <= CTRL_ISOLATION_LIMIT)
    verdict = "ACCEPT" if (xt_ok and iso_ok) else "REJECT"
    return {
        "verdict": verdict, "n_qubits": rows * cols,
        "ctrl_line_pitch_um": pitch, "ctrl_line_len_um": length,
        "max_intra_X": float(max_intra), "max_inter_X": float(max_inter),
        "xy_z_isolation_X": float(xy_z),
        "xtalk_limit": CTRL_XTALK_LIMIT, "isolation_limit": CTRL_ISOLATION_LIMIT,
        "intra_pairs": intra, "inter_lines": inter,
        "xtalk_ok": xt_ok, "isolation_ok": iso_ok,
        "note": ("逐线串扰 = 平行段 fringe 电容闭式 C_x=ε_eff·ε0·Lc·t/gap → X=C_x/C_q"
                 "（复用 S4 口径）；分同 qubit 内线对（含 XY↔Z 隔离）与相邻 qubit 同角色线。"
                 "ε_eff/t/C_q 为设计参数（非 golden）。LLM 不进判决路径。"),
    }


def control_physics(params: Optional[Dict] = None) -> Dict:
    """控制多线物理签核 = 逐线串扰预算 ACCEPT（含 XY↔Z 隔离）。"""
    xt = line_xtalk_budget(params)
    return {"verdict": xt["verdict"], "xtalk": xt,
            "note": "控制多线物理 = 逐线串扰预算（同 qubit 内线对 + 相邻 qubit 同角色线）。"}


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

    cell = control_array_cell({"rows": 2, "cols": 2})
    check = run_control_drc(cell)
    chk("① 合法 2×2 多线控制 DRC ACCEPT（S4 十则 + 三线二则）",
        check["verdict"] == "ACCEPT")
    chk("② 合法 2×2 多线控制 LVS ACCEPT（S4 九判据 + 三线角色互异）",
        control_lvs(cell)["verdict"] == "ACCEPT")

    n_ctrl = len([d for d in cell if d.get("net") == "control"])
    chk("③ 2×2 控制线数 = 4 qubit × 3 线 = 12",
        n_ctrl == 12
        and all(d.get("control_role") in CTRL_ROLES
                for d in cell if d.get("net") == "control"))

    # 三线太挤（pitch 太小）⇒ DRC REJECT
    tight = control_array_cell({"rows": 1, "cols": 2, "ctrl_line_pitch": 0.2})
    vt = run_control_drc(tight)
    chk("④ 三线太挤(pitch 0.2) ⇒ DRC REJECT（SCD-CTRL-LINE-SPACING）",
        vt["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-CTRL-LINE-SPACING" for v in vt["violations"]))

    # 线太细 ⇒ DRC REJECT
    thin = control_array_cell({"rows": 1, "cols": 2})
    for d in thin:
        if d.get("net") == "control":
            d["width_um"] = 0.05
    vw = run_control_drc(thin)
    chk("⑤ 控制线太细(0.05<0.3) ⇒ DRC REJECT（SCD-CTRL-LINE-MIN-WIDTH）",
        vw["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-CTRL-LINE-MIN-WIDTH" for v in vw["violations"]))

    # 少一线（角色缺） ⇒ LVS REJECT
    missing = [d for i, d in enumerate(cell)
               if not (d.get("net") == "control" and d.get("control_role") == "z")]
    vm = control_lvs(missing)
    chk("⑥ 缺 Z 线 ⇒ LVS REJECT（SCD-LVS-CTRL-LINE-COUNT）",
        vm["verdict"] == "REJECT" and any("CTRL-LINE-COUNT" in i for i in vm["issues"]))

    # 角色重复（两 xy 无 cflux） ⇒ LVS REJECT
    dup = []
    for d in cell:
        if d.get("net") == "control" and d.get("control_role") == "cflux":
            d2 = dict(d)
            d2["control_role"] = "xy"
            dup.append(d2)
        else:
            dup.append(d)
    vd = control_lvs(dup)
    chk("⑦ 角色重复(两 xy 无 cflux) ⇒ LVS REJECT（SCD-LVS-CTRL-ROLE-DUP）",
        vd["verdict"] == "REJECT" and any("CTRL-ROLE-DUP" in i for i in vd["issues"]))

    # 逐线串扰 ACCEPT（合法）
    xt = line_xtalk_budget({"rows": 2, "cols": 2})
    chk("⑧ 合法 2×2 逐线串扰 ACCEPT（含 XY↔Z 隔离）", xt["verdict"] == "ACCEPT")

    # 三线重叠（pitch 0.1） ⇒ 串扰 REJECT
    xt_bad = line_xtalk_budget({"rows": 2, "cols": 2, "ctrl_line_pitch": 0.1})
    chk("⑨ 三线重叠(pitch 0.1) ⇒ 串扰/隔离 REJECT",
        xt_bad["verdict"] == "REJECT"
        and (xt_bad["xy_z_isolation_X"] > CTRL_ISOLATION_LIMIT
             or xt_bad["max_intra_X"] > CTRL_XTALK_LIMIT))

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok
