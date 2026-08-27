"""LDA L2 · 版图几何级 RC 寄生估算（v0.8.31 · 主权零依赖）。

作用：对 **GDSII 版图多边形**（复用 lda_l2.gds_export.parse_gds_polygons
的 layer / kind / width / points_um）做**几何级**电阻(R)-电容(C)寄生估算——
把版图尺寸直接换算成每个器件的 R_par / C_par 量级。这是版图→寄生这一环的
**主权自研拼图**，使「设计 → 仿真 → 版图 → DRC/LVS → 工艺角 → 几何寄生」
在设计侧主权闭环内自洽。

主权纪律（与 lda_l2.gds_drc / lda_pdk.tapeout_pipeline 同源）：
  - 零依赖（仅标准库 + lda_l2.gds_export.parse_gds_polygons）；
  - 仅几何维度死标量估算，无工艺魔法数硬编码；
  - 诚实边界：几何级估算 **≠ foundry 工艺级寄生 deck**；真实金属/硅工艺
    方块电阻、介质厚度等参数发动期由真实 PDK 提供后替换（数据驱动）。

**诚实边界（必须守住）**：
  - 本模块给出的是**几何量级估算**（方块电阻 × 长/宽、平行板 × 面积），
    不求解真实截面电磁场（无 3D 场解 RC 提取）；
  - 串联/并联为**一阶近似**（R 沿 net 求和、C 对衬底并联求和），适合
    量级洞察与阈值守门，不替代签核级寄生网表；
  - 阈值（max_r_ohm / max_c_ff）为**主权几何护栏**，非 foundry 签核限值。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# ---- 主权默认 RC 表（公开文献典型量级，非真实 PDK；发动期替换）----
# sheet_ohm_per_sq : 方块电阻 Ω/□ ；cap_fF_per_um2 : 对衬底平行板电容 fF/µm²
DEFAULT_RC_SHEET: Dict[str, Dict[str, Any]] = {
    "metal":     {"layer": 11, "sheet_ohm_per_sq": 0.05, "cap_fF_per_um2": 0.02,
                  "note": "金属互连（Al/Cu 典型 R□）"},
    "poly":      {"layer": 31, "sheet_ohm_per_sq": 20.0, "cap_fF_per_um2": 0.05,
                  "note": "多晶硅（典型 R□）"},
    "active_si": {"layer": 1,  "sheet_ohm_per_sq": 80.0, "cap_fF_per_um2": 0.10,
                  "note": "有源硅（典型 R□，含衬底耦合）"},
    "silicide":  {"layer": 41, "sheet_ohm_per_sq": 5.0,  "cap_fF_per_um2": 0.03,
                  "note": "硅化物接触（低阻）"},
}
# 层号 → RC 键
LAYER_TO_RC: Dict[int, str] = {v["layer"]: k for k, v in DEFAULT_RC_SHEET.items()}

# 未知层（非导体建模层）：R 不建模（=0，标注未建模），C 用衬底默认电容
DEFAULT_SUBSTRATE_CAP_FF_PER_UM2 = 0.02

# 主权几何护栏（非 foundry 签核限值）
DEFAULT_RC_THRESHOLDS: Dict[str, float] = {
    "max_r_ohm": 1000.0,   # 信号走线电阻护栏 1kΩ
    "max_c_ff": 1000.0,    # 负载电容护栏 1pF
}


# --------------------------------------------------------------------------
# 几何小工具（局部实现，避免跨模块私有依赖）
# --------------------------------------------------------------------------
def _bbox(poly: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _poly_area(poly: List[Tuple[float, float]]) -> float:
    """鞋带公式多边形面积（µm²，取绝对值）。"""
    if len(poly) < 3:
        return 0.0
    s = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


def _path_length(poly: List[Tuple[float, float]]) -> float:
    if len(poly) < 2:
        return 0.0
    return sum(
        ((poly[i][0] - poly[i - 1][0]) ** 2 + (poly[i][1] - poly[i - 1][1]) ** 2) ** 0.5
        for i in range(1, len(poly))
    )


# --------------------------------------------------------------------------
# 核心估算
# --------------------------------------------------------------------------
def _element_rc(elem: Dict[str, Any], rc_sheet: Dict[str, Dict[str, Any]]
                ) -> Dict[str, Any]:
    """单元素的几何 RC 估算。"""
    layer = int(elem.get("layer", -1))
    kind = elem.get("kind")
    width = elem.get("width") or 0.0
    pts = elem.get("points_um") or []
    rc_key = LAYER_TO_RC.get(layer)
    meta = rc_sheet.get(rc_key, {}) if rc_key else {}

    # ---- 电阻 ----
    r_ohm = 0.0
    r_note = ""
    if rc_key and meta:
        rsq = float(meta["sheet_ohm_per_sq"])
        if kind == "path" and width > 0:
            length = _path_length(pts)
            r_ohm = rsq * (length / width)
        elif kind == "boundary" and len(pts) >= 2:
            x0, y0, x1, y1 = _bbox(pts)
            bw, bh = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
            # 方形板：R ≈ R□ × (宽/高)（两对边间电阻一阶近似）
            r_ohm = rsq * (bw / bh)
        else:
            r_note = "几何未建模(无宽/非标准形)"
    else:
        r_note = "未知层·R 未建模(非导体层)"

    # ---- 电容（对衬底平行板，全层适用）----
    if kind == "path" and width > 0:
        area = _path_length(pts) * width
    elif len(pts) >= 3:
        area = _poly_area(pts)
    else:
        area = 0.0
    cap_rate = float(meta.get("cap_fF_per_um2", DEFAULT_SUBSTRATE_CAP_FF_PER_UM2))
    c_ff = cap_rate * area
    if not rc_key:
        c_ff = DEFAULT_SUBSTRATE_CAP_FF_PER_UM2 * area

    return {
        "layer": layer,
        "kind": kind,
        "width_um": round(width, 4) if width else None,
        "area_um2": round(area, 4),
        "R_ohm": round(r_ohm, 6),
        "C_ff": round(c_ff, 6),
        "rc_key": rc_key,
        "note": r_note,
    }


def estimate_parasitics(structures: Dict[str, List[Dict]],
                        rc_sheet: Optional[Dict[str, Dict[str, Any]]] = None
                        ) -> Dict[str, Any]:
    """对 parse_gds_polygons 的 structures 字典做几何 RC 寄生估算。

    返回 {by_structure, totals, elements, rc_sheet_used, honest_note}。
    - elements：逐元素明细
    - by_structure：每结构 R_series(串联和) / C_total(并联和) / n_elements
    - totals：全版图 R_series_ohm / C_total_ff / 计数
    串联/并联为一阶近似（详见模块诚实边界）。
    """
    sheet = dict(DEFAULT_RC_SHEET)
    if rc_sheet:
        sheet.update(rc_sheet)

    elements: List[Dict[str, Any]] = []
    by_structure: Dict[str, Dict[str, Any]] = {}
    tot_r = 0.0
    tot_c = 0.0
    n_elems = 0

    for sname, elems in structures.items():
        s_r = 0.0
        s_c = 0.0
        s_n = 0
        for e in elems:
            n_elems += 1
            s_n += 1
            rc = _element_rc(e, sheet)
            elements.append({"structure": sname, **rc})
            s_r += rc["R_ohm"]
            s_c += rc["C_ff"]
            tot_r += rc["R_ohm"]
            tot_c += rc["C_ff"]
        by_structure[sname] = {
            "R_series_ohm": round(s_r, 6),
            "C_total_ff": round(s_c, 6),
            "n_elements": s_n,
        }

    return {
        "by_structure": by_structure,
        "totals": {
            "R_series_ohm": round(tot_r, 6),
            "C_total_ff": round(tot_c, 6),
            "n_elements": n_elems,
            "n_structures": len(by_structure),
        },
        "elements": elements,
        "rc_sheet_used": sheet,
        "honest_note": (
            "几何级 RC 估算（主权）：R=R□×长/宽、C=平行板×面积，串联/并联为一阶近似；"
            "非 foundry 工艺级寄生 deck，真实金属/硅工艺参数发动期由真实 PDK 替换。"
        ),
    }


def check_parasitic(report: Dict[str, Any],
                    thresholds: Optional[Dict[str, float]] = None
                    ) -> Dict[str, Any]:
    """对寄生估算做主权几何护栏死标量判定（不阻断签核，仅作洞察阈值）。"""
    th = dict(DEFAULT_RC_THRESHOLDS)
    if thresholds:
        th.update(thresholds)
    violations: List[str] = []
    tot = report["totals"]
    if tot["R_series_ohm"] > th["max_r_ohm"]:
        violations.append(
            f"全版图串联电阻 {tot['R_series_ohm']:.2f}Ω > 护栏 {th['max_r_ohm']}Ω")
    if tot["C_total_ff"] > th["max_c_ff"]:
        violations.append(
            f"全版图负载电容 {tot['C_total_ff']:.2f}fF > 护栏 {th['max_c_ff']}fF")
    # 逐结构明细越界提示（不重复计入 totals 违例）
    for sname, s in report["by_structure"].items():
        if s["R_series_ohm"] > th["max_r_ohm"]:
            violations.append(
                f"{sname}: R={s['R_series_ohm']:.2f}Ω > {th['max_r_ohm']}Ω")
        if s["C_total_ff"] > th["max_c_ff"]:
            violations.append(
                f"{sname}: C={s['C_total_ff']:.2f}fF > {th['max_c_ff']}fF")
    return {
        "all_pass": len(violations) == 0,
        "violations": violations,
        "thresholds": th,
    }


def parasitic_rc_markdown(report: Dict[str, Any],
                          check: Optional[Dict[str, Any]] = None) -> str:
    L = []
    L.append("### 版图几何级 RC 寄生估算（主权 · 非 foundry 工艺级）")
    L.append("")
    tot = report["totals"]
    status = "✅" if (check is None or check["all_pass"]) else "⚠️"
    L.append(f"- {status} 全版图估算：R_series ≈ {tot['R_series_ohm']:.3f}Ω · "
             f"C_total ≈ {tot['C_total_ff']:.3f}fF "
             f"（{tot['n_elements']} 元素 / {tot['n_structures']} 结构）")
    if report["by_structure"]:
        L.append("")
        L.append("| 结构 | 元素数 | R_series (Ω) | C_total (fF) |")
        L.append("|---|---|---|---|")
        for sname, s in report["by_structure"].items():
            L.append(f"| {sname} | {s['n_elements']} | "
                     f"{s['R_series_ohm']:.3f} | {s['C_total_ff']:.3f} |")
    if check and check["violations"]:
        L.append("")
        L.append(f"- ⚠️ 几何护栏触发 {len(check['violations'])} 项（主权阈值，非签核限值）：")
        for v in check["violations"][:12]:
            L.append(f"  - {v}")
    L.append("")
    L.append(f"*诚实边界：{report['honest_note']}*")
    return "\n".join(L)
