"""D-140 · 超导征程 S5 P1：读出频分复用（FDM mux）几何 + 频率规划/调度 + 签核。

S4（D-136）已给每 row 一条行馈线、每 qubit 一条读出腔（几何 stub）——即「共享馈线的
读出」的骨架。G4 把骨架补成**真实频分复用（FDM）**：一条馈线上挂多只读出腔，各腔须落在
**互不碰撞且与 qubit 工作点隔离**的频点上（读出音 f_r 落带、与 qubit f01 留保护带、
同馈线相邻音最小间隔），并按 λ/4 关系把「声」编码进几何（腔长/腔高随 f_r 单调）。

能力（纯几何 + 闭式，零量子 SDK）：
  • mux_plan(params)          → 频率规划：阶梯分配 N 个互异读出音 + 与 qubit 保护带校验
  • resonator_length_um(f)    → λ/4 腔长闭式 L = v_ph/(4f)（设计表示，几何按参考腔缩放）
  • mux_array_cell(params)    → S4 阵列几何 + 每读出腔「按音高编码腔高」（单一真源复用 S4）
  • run_mux_drc(els, plan)    → S4 十则 + FDM 三则（腔间距/音间隔/qubit 保护带，均设计规则）
  • mux_lvs(els, plan)        → S4 九判据 + 读出音唯一性（同端口不得重音）
  • mux_physics(params)       → 频率规划 + per-读出 Purcell 预算（复用 D-88 闭式）
  • run_selfchecks()

诚实边界（与 S1–S4 一致）：
  • f_r / κ / g / ε_eff 均为**设计参数**，非实测 PDK（属 D5）；闭式公式为确定性物理定律。
  • 腔长按 λ/4 表示，几何为**缩放表示**（片上单元级布局，非 mm 级真腔长 1:1）。
  • 复用 S4 阵列/读出几何 + S2 单元原语 + D-88 色散/Purcell 闭式，零重复造轮子。
红线：纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、限值为设计规则。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from lda_l2 import gds_export as G
from lda_qeda import sc_readout as S4
from lda_qeda.sc_coupler import _bbox
from lda_solver import coupler_solver as CS

FILM = G.LIB_LAYER_SC_FILM
JJ = G.LIB_LAYER_SC_JJ
GROUND = G.LIB_LAYER_SC_GROUND

C_UM_PER_S = 2.998e14          # 光速（µm/s）

# FDM 设计规则（可覆盖 · 非实测 golden）
DEFAULT_MUX_LIMITS = {
    "min_tone_spacing_mhz": 30.0,     # 同端口相邻读出音最小间隔
    "min_qubit_guard_mhz": 80.0,      # 读出音到 qubit f01 最小保护带
    "min_resonator_gap_um": 0.5,      # 同馈线相邻读出腔几何间隙
    "min_readout_h_um": 0.8,          # 读出腔编码后最小半高（防过薄）
}
MUX_DRC_RULES = tuple(list(S4.READOUT_DRC_RULES) + [
    "SCD-MUX-RESONATOR-GAP",   # 同馈线相邻读出腔几何间隙 ≥ 下限
    "SCD-MUX-TONE-SPACING",    # 同端口相邻读出音最小间隔（频域设计规则）
    "SCD-MUX-QUBIT-GUARD",     # 读出音到 qubit f01 保护带（频域设计规则）
])

DEFAULT_MUX_PLAN = {
    "f_min_ghz": 6.8, "f_max_ghz": 8.2,
    "eps_eff": 6.5,
    "f_ref_ghz": 6.5, "readout_h_ref_um": 1.5,   # 参考音 / 参考腔半高（λ/4 缩放基准）
    "kappa_ghz": 0.002, "g_rq_ghz": 0.05,        # 读出耦合（Purcell 预算用，设计参数）
}
READOUT_T1_TARGET_US = 20.0      # per-读出 Purcell 保护目标（与 S4 同口径）

RED_LINE_DISCLOSURE = {
    "role": "D-140 = 超导征程 S5 P1：读出频分复用（FDM mux）几何 + 频率规划/调度 + 签核，"
            "把 S4 的「共享馈线读出」补成「多腔共线、音互异且隔离」的真 FDM",
    "layers": "SC_FILM=10 / SC_JJ=11 / SC_GROUND=12（gds_export 定义，非 Foundry PDK）；"
              "读出腔/馈线布 FILM 层，以 net(readout/feedline) 区分",
    "limits": "min_tone_spacing / min_qubit_guard / min_resonator_gap 为**设计规则 · 可覆盖 · "
              "非实测 golden**（Foundry PDK 属 D5 外部依赖）",
    "lvs": "几何 LVS 复用 S4 九判据 + FDM 音唯一性（同端口不得重音）；对**实际 produced "
           "几何**做 bbox 重叠/邻近网表提取",
    "physics": "读出音规划为确定性阶梯分配（几何 ↔ λ/4 关系 L=v_ph/(4f)）；"
               "Purcell 复用 D-88 闭式 γ_P=κg²/Δ²。f_r/κ/g/ε_eff 为设计参数（非 golden）",
    "mux": "FDM = 一馈线多腔，音域互异且与 qubit 工作点隔离；共享端口时全阵音互异",
    "red_line": "纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、"
                "腔长为 λ/4 缩放表示（片内单元级，键合/封装片外未建模）",
}
ROLE = RED_LINE_DISCLOSURE["role"]


# ---------------------------------------------------------------------------
# λ/4 谐振腔闭式（几何 ↔ 频率）
# ---------------------------------------------------------------------------
def resonator_length_um(f_ghz: float, eps_eff: float = 6.5) -> float:
    """λ/4 谐振腔物理长度（µm）：L = v_ph/(4·f)，v_ph = c/√ε_eff。"""
    v_ph = C_UM_PER_S / math.sqrt(float(eps_eff))
    return float(v_ph / (4.0 * float(f_ghz) * 1e9))


def resonator_freq_ghz(length_um: float, eps_eff: float = 6.5) -> float:
    """λ/4 谐振腔频率（GHz）：f = v_ph/(4·L)。"""
    v_ph = C_UM_PER_S / math.sqrt(float(eps_eff))
    return float(v_ph / (4.0 * float(length_um) * 1e-6) / 1e9)


# ---------------------------------------------------------------------------
# FDM 频率规划（阶梯分配 + 隔离校验）
# ---------------------------------------------------------------------------
def _qubit_freqs_mhz(params: Dict) -> List[float]:
    """阵列 qubit 工作频率（MHz）。未给 EJ_list 时用**限带**默认（f01 ∈ [5.0,6.2] GHz）。"""
    rows = int(params.get("rows", 2))
    cols = int(params.get("cols", 2))
    n = rows * cols
    ec = float(params.get("E_C", 0.25))
    if params.get("EJ_list"):
        ej = [float(x) for x in params["EJ_list"]]
    else:
        ej = S4._band_limited_ej_list(n, ec)
    return [CS.koch_f01(float(x), ec) * 1000.0 for x in ej]


def mux_plan(params: Optional[Dict] = None) -> Dict:
    """FDM 读出音规划（**每馈线**阶梯分配 + 隔离校验）。

    LDA/S4 架构 = 每 row 一条馈线，读出音在**同馈线内**须互异（不同馈线可复用音）。
    分配：同馈线 cols 个音在 [f_min, f_max] 上等距阶梯；校验 ① 同馈线音间隔 ≥
    min_tone_spacing ② 每音到其 qubit f01 保护带 ≥ min_qubit_guard ③ 音落带内。
    shared_port=True 时退化为「全阵互异」（须更宽音域）。
    """
    p = dict(params or {})
    pl = dict(DEFAULT_MUX_PLAN)
    pl.update({k: v for k, v in p.items() if k in DEFAULT_MUX_PLAN})
    lim = dict(DEFAULT_MUX_LIMITS)
    lim.update({k: v for k, v in p.items() if k in DEFAULT_MUX_LIMITS})

    rows = int(p.get("rows", 2))
    cols = int(p.get("cols", 2))
    n = rows * cols
    f_min = float(pl["f_min_ghz"])
    f_max = float(pl["f_max_ghz"])
    eps = float(pl["eps_eff"])
    f_ref = float(pl["f_ref_ghz"])
    h_ref = float(pl["readout_h_ref_um"])
    shared = bool(p.get("shared_port", False))

    n_slot = n if shared else max(cols, 1)          # 每馈线音数（或全阵）
    step = (f_max - f_min) / (n_slot - 1) if n_slot > 1 else 0.0
    qf = _qubit_freqs_mhz(p)

    per_q: List[Dict] = []
    min_spacing = float("inf")
    min_guard = float("inf")
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            slot = i if shared else c
            tone = f_min + slot * step
            tone_mhz = tone * 1000.0
            guard = abs(tone_mhz - qf[i])
            min_guard = min(min_guard, guard)
            if slot > 0:
                min_spacing = min(min_spacing, step * 1000.0)
            length = resonator_length_um(tone, eps)
            h_i = max(h_ref * (f_ref / tone), lim["min_readout_h_um"])
            per_q.append({"qubit": i, "feedline": r, "tone_slot": slot,
                          "f_r_ghz": tone, "tone_mhz": tone_mhz,
                          "qubit_f01_mhz": qf[i], "guard_mhz": guard,
                          "length_um": length, "readout_half_h_um": h_i})

    if n_slot <= 1:
        min_spacing = float("inf")
    sp_ok = bool(min_spacing >= lim["min_tone_spacing_mhz"])
    guard_ok = bool(min_guard >= lim["min_qubit_guard_mhz"])
    band_ok = bool(f_min < f_max)
    verdict = "ACCEPT" if (sp_ok and guard_ok and band_ok) else "REJECT"

    return {
        "verdict": verdict, "n_readouts": n, "rows": rows, "cols": cols,
        "f_min_ghz": f_min, "f_max_ghz": f_max, "step_ghz": step,
        "shared_port": shared, "tones_per_feedline": n_slot,
        "eps_eff": eps, "f_ref_ghz": f_ref,
        "min_tone_spacing_mhz": (None if min_spacing == float("inf") else float(min_spacing)),
        "min_qubit_guard_mhz": (None if min_guard == float("inf") else float(min_guard)),
        "spacing_ok": sp_ok, "guard_ok": guard_ok, "band_ok": band_ok,
        "per_readout": per_q,
        "note": ("FDM 音规划 = 每馈线（row）内 cols 个音在 [f_min,f_max] 等距阶梯"
                 "（不同于馈线可复用音；shared_port 时全阵互异）；校验同馈线音间隔与"
                 "qubit f01 保护带。f_r/ε_eff 为设计参数（非 golden）；λ/4 关系为物理定律。"),
    }


def _tone_from_elements(elements: List[Dict]) -> Dict[int, float]:
    """从读出腔几何反推音点（腔半高 ↔ 音，λ/4 缩放编码；用于几何-频域一致性判据）。"""
    out: Dict[int, float] = {}
    for d in elements:
        if d.get("net") == "readout":
            bb = _bbox(d)
            h = (bb[3] - bb[2]) / 2.0
            out[d.get("qubit_id")] = h
    return out


# ---------------------------------------------------------------------------
# 几何单元（S4 阵列 + 读出腔「按音高编码腔高」）
# ---------------------------------------------------------------------------
def mux_array_cell(params: Optional[Dict] = None) -> List[Dict]:
    """FDM 阵列几何：S4 阵列/馈线/控制 + 每读出腔按音高编码腔高（λ/4 缩放表示）。

    单一真源 = S4.readout_array_cell；仅把每只读出腔的**上缘**按其音高上移/下移
    （保底缘不动 ⇒ 与馈线耦合间隙、与 qubit 的桥接均保持不变）。
    """
    p = dict(params or {})
    plan = mux_plan(p)
    h_by_q = {r["qubit"]: r["readout_half_h_um"] for r in plan["per_readout"]}
    base_hh = float(p.get("readout_hh", 1.5))
    out: List[Dict] = []
    for d in S4.readout_array_cell(p):
        if d.get("net") == "readout":
            qid = d.get("qubit_id")
            new_hh = h_by_q.get(qid, base_hh)
            bb = _bbox(d)
            x0, x1 = bb[0], bb[1]
            y_bot = bb[2]                       # 保底缘（与馈线耦合间隙不变）
            y_top = y_bot + 2.0 * new_hh
            d2 = dict(d)
            d2["rings_um"] = [[(x0, y_bot), (x1, y_bot), (x1, y_top), (x0, y_top)]]
            out.append(d2)
        else:
            out.append(d)
    return out


def mux_gds(params: Optional[Dict] = None, path: str = "sc_mux.gds") -> bytes:
    """真出 GDSII（零依赖自写编码器）。返回文件字节。"""
    descs = mux_array_cell(params)
    recs: List[bytes] = []
    for d in descs:
        if d["kind"] == "path":
            recs.append(G.path(d["layer"], d["width_um"], d["points_um"]))
        else:
            recs.append(G.boundary(d["layer"], G._flatten_rings(d.get("rings_um"))))
    data = G.gds_library("LDA-SC-MUX", {"sc_mux": recs})
    G.write_gds(path, data)
    return data


def mux_svg_preview(params: Optional[Dict] = None, width: int = 620) -> str:
    """版图 SVG 预览（FDM 读出腔按音高编码腔高）。"""
    descs = mux_array_cell(params)
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
# DRC（S4 十则 + FDM 三则）
# ---------------------------------------------------------------------------
def run_mux_drc(elements: List[Dict], plan: Optional[Dict] = None,
                limits: Optional[Dict] = None) -> Dict:
    """FDM 几何 DRC = S4 十则 + FDM 三则（腔间距 / 音间隔 / qubit 保护带）。"""
    lim = dict(DEFAULT_MUX_LIMITS)
    if limits:
        lim.update(limits)
    base = S4.run_readout_drc(elements, limits)
    violations = list(base["violations"])

    # SCD-MUX-RESONATOR-GAP：同馈线相邻读出腔几何间隙
    reads = [d for d in elements if d.get("net") == "readout"]
    min_gap = float("inf")
    for i in range(len(reads)):
        for j in range(i + 1, len(reads)):
            bi, bj = _bbox(reads[i]), _bbox(reads[j])
            dx = max(bi[0] - bj[1], bj[0] - bi[1], 0.0)
            dy = max(bi[2] - bj[3], bj[2] - bi[3], 0.0)
            min_gap = min(min_gap, math.hypot(dx, dy))
    if reads and min_gap < lim["min_resonator_gap_um"] - 1e-9:
        violations.append({"rule": "SCD-MUX-RESONATOR-GAP",
                           "detail": f"相邻读出腔间隙 {min_gap:.3f}"
                                     f"<{lim['min_resonator_gap_um']}"})

    pl = plan if plan is not None else mux_plan({})
    if not pl.get("spacing_ok", False):
        violations.append({"rule": "SCD-MUX-TONE-SPACING",
                           "detail": f"最小音间隔={pl['min_tone_spacing_mhz']}"
                                     f"<{lim['min_tone_spacing_mhz']}"})
    if not pl.get("guard_ok", False):
        violations.append({"rule": "SCD-MUX-QUBIT-GUARD",
                           "detail": f"最小 qubit 保护带={pl['min_qubit_guard_mhz']}"
                                     f"<{lim['min_qubit_guard_mhz']}"})

    verdict = "ACCEPT" if not violations else "REJECT"
    return {"verdict": verdict, "violations": violations,
            "n_rules": len(MUX_DRC_RULES), "limits": lim,
            "min_resonator_gap_um": (None if min_gap == float("inf") else float(min_gap)),
            "plan_verdict": pl["verdict"]}


# ---------------------------------------------------------------------------
# LVS（S4 九判据 + 音唯一性）
# ---------------------------------------------------------------------------
def mux_lvs(elements: List[Dict], plan: Optional[Dict] = None) -> Dict:
    """FDM 几何 LVS = S4 九判据 + 读出音唯一性（同端口不得重音）。"""
    base = S4.readout_lvs_signoff(elements)
    issues = list(base["issues"])
    n_checks = base["n_checks"] + 1

    pl = plan if plan is not None else mux_plan({})
    n_readouts = len([d for d in elements if d.get("net") == "readout"])
    by_feed: Dict[int, List[float]] = {}
    for r in pl["per_readout"]:
        by_feed.setdefault(r["feedline"], []).append(r["tone_mhz"])
    # 同馈线内音互异（不同馈线独立端口，可复用音）
    dup = any(len(v) != len({round(t, 6) for t in v}) for v in by_feed.values())
    if dup:
        issues.append("SCD-LVS-MUX-TONE-DUP: 同馈线内存在重复读出音（FDM 无法分辨）")
    if len(pl["per_readout"]) != n_readouts:
        issues.append(f"SCD-LVS-MUX-COUNT: 音数={len(pl['per_readout'])}≠读出腔数={n_readouts}")

    n_unique = sum(len({round(t, 6) for t in v}) for v in by_feed.values())
    verdict = "ACCEPT" if not issues else "REJECT"
    return {"verdict": verdict, "issues": issues,
            "netlist": dict(base["netlist"], tones=len(pl["per_readout"]),
                            unique_tones=n_unique, feedlines=len(by_feed)),
            "n_checks": n_checks}


# ---------------------------------------------------------------------------
# 物理签核（频率规划 + per-读出 Purcell）
# ---------------------------------------------------------------------------
def mux_physics(params: Optional[Dict] = None) -> Dict:
    """FDM 物理签核 = 频率规划 ACCEPT + per-读出 Purcell 保护 ACCEPT。

    Purcell（复用 D-88 闭式）：γ_P = κ·g²/Δ²，Δ = f_r − f_q；1/T1_P = γ_P。
    验收：每读出 T1_P ≥ 目标 且规划 ACCEPT。
    """
    p = dict(params or {})
    pl = mux_plan(p)
    kappa = float(p.get("kappa_ghz", DEFAULT_MUX_PLAN["kappa_ghz"]))
    g_rq = float(p.get("g_rq_ghz", DEFAULT_MUX_PLAN["g_rq_ghz"]))
    per: List[Dict] = []
    all_ok = True
    for r in pl["per_readout"]:
        delta_ghz = (r["f_r_ghz"] * 1000.0 - r["qubit_f01_mhz"]) / 1000.0
        gamma_p = kappa * g_rq * g_rq / (delta_ghz * delta_ghz) if abs(delta_ghz) > 1e-9 else 1e9
        t1p_us = 1e6 / (gamma_p * 1e9) if gamma_p > 0 else float("inf")
        ok = bool(t1p_us >= READOUT_T1_TARGET_US)
        all_ok = all_ok and ok
        per.append({"qubit": r["qubit"], "f_r_ghz": r["f_r_ghz"],
                    "delta_ghz": float(delta_ghz),
                    "t1_purcell_us": (None if t1p_us == float("inf") else float(t1p_us)),
                    "ok": ok})
    min_t1 = min((x["t1_purcell_us"] for x in per
                  if x["t1_purcell_us"] is not None), default=0.0)
    verdict = "ACCEPT" if (pl["verdict"] == "ACCEPT" and all_ok) else "REJECT"
    return {"verdict": verdict, "plan": pl,
            "kappa_ghz": kappa, "g_rq_ghz": g_rq,
            "t1_target_us": READOUT_T1_TARGET_US,
            "min_t1_purcell_us": float(min_t1),
            "purcell_ok": all_ok, "per_readout": per,
            "note": ("FDM 物理 = 频率规划（阶梯 + 隔离）+ per-读出 Purcell γ_P=κg²/Δ²"
                     "（D-88 闭式）。f_r/κ/g 为设计参数（非 golden）。LLM 不进判决路径。")}


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

    cell = mux_array_cell({"rows": 2, "cols": 2})
    check = run_mux_drc(cell)
    chk("① 合法 2×2 FDM 阵列 DRC ACCEPT（S4 十则 + FDM 三则）",
        check["verdict"] == "ACCEPT")
    chk("② 合法 2×2 FDM 阵列 LVS ACCEPT（S4 九判据 + 音唯一）",
        mux_lvs(cell)["verdict"] == "ACCEPT")

    plan = mux_plan({"rows": 2, "cols": 2})
    by_feed: Dict[int, List[float]] = {}
    for r in plan["per_readout"]:
        by_feed.setdefault(r["feedline"], []).append(r["tone_mhz"])
    chk("③ 音规划：每馈线音互异 + 最小间隔落带",
        all(len(v) == len({round(t, 6) for t in v}) for v in by_feed.values())
        and plan["min_tone_spacing_mhz"] >= DEFAULT_MUX_LIMITS["min_tone_spacing_mhz"]
        and plan["verdict"] == "ACCEPT")

    # 音太密（带太窄）⇒ REJECT
    dense = mux_plan({"rows": 2, "cols": 4, "f_min_ghz": 6.8, "f_max_ghz": 6.85})
    chk("④ 音域过窄（带 50MHz/4 音/馈线）⇒ 规划与 DRC REJECT（SCD-MUX-TONE-SPACING）",
        dense["verdict"] == "REJECT"
        and run_mux_drc(mux_array_cell({"rows": 2, "cols": 4}),
                        plan=dense)["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-MUX-TONE-SPACING"
                for v in run_mux_drc(mux_array_cell({"rows": 2, "cols": 4}),
                                     plan=dense)["violations"]))

    # 读出音贴 qubit f01 ⇒ REJECT（保护带不足）
    guard = mux_plan({"rows": 1, "cols": 1, "f_min_ghz": 5.05, "f_max_ghz": 5.05})
    chk("⑤ 读出音贴 qubit f01（保护带 50MHz<80）⇒ 规划 REJECT（SCD-MUX-QUBIT-GUARD）",
        guard["verdict"] == "REJECT"
        and not guard["guard_ok"])

    # 同馈线重音 ⇒ LVS REJECT
    dup_plan = dict(plan)
    pr = [dict(x) for x in plan["per_readout"]]
    pr[1] = dict(pr[1], tone_mhz=pr[0]["tone_mhz"])
    dup_plan["per_readout"] = pr
    chk("⑥ 同馈线重复读出音 ⇒ LVS REJECT（SCD-LVS-MUX-TONE-DUP）",
        mux_lvs(mux_array_cell({"rows": 2, "cols": 2}), plan=dup_plan)["verdict"] == "REJECT"
        and any("MUX-TONE-DUP" in i
                for i in mux_lvs(mux_array_cell({"rows": 2, "cols": 2}),
                                 plan=dup_plan)["issues"]))

    # λ/4 闭式：f 高 ⇒ L 短（单调）
    l_lo = resonator_length_um(6.0)
    l_hi = resonator_length_um(7.0)
    chk("⑦ λ/4 闭式：f↑⇒L↓ 单调 · L(6GHz)≈L(7GHz)·7/6",
        l_hi < l_lo and abs(l_lo / l_hi - 7.0 / 6.0) < 1e-6)

    # 几何 ↔ 频域一致：腔高编码随音单调（λ/4）
    h = {r["qubit"]: r["readout_half_h_um"] for r in plan["per_readout"]}
    chk("⑧ 腔高按音高编码：高音 ⇒ 腔更矮（λ/4 缩放表示一致）",
        h[0] > h[1] and abs(h[0] - DEFAULT_MUX_PLAN["readout_h_ref_um"]
                            * DEFAULT_MUX_PLAN["f_ref_ghz"]
                            / plan["per_readout"][0]["f_r_ghz"]) < 1e-9)

    phys = mux_physics({"rows": 2, "cols": 2})
    chk("⑨ 合法 2×2 FDM 物理 ACCEPT（规划 + Purcell 双 ACCEPT）",
        phys["verdict"] == "ACCEPT")

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok
