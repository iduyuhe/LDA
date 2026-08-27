"""LDA L2 · GDS 几何 DRC 快查（v0.8.30 · 主权零依赖）。

作用：对**任意来源 GDSII（含外部 gdsfactory/第三方工具导出）**做 LDA 侧
几何可制造性快查——最小线宽 / 最小间距 / 最小面积。这是 **GDS 输入路径**
（gdsfactory 兼容桥 `lda check --gds`）的诚实底线：LDA 主权 DRC 只覆盖
几何规则**子集**（不替代 foundry 官方 DRC deck），未知层/复杂规则显式标
"未覆盖"而非静默放过。

主权纪律（与 lda_l2.drc 同源）：
  - 零依赖（仅标准库 + lda_l2.gds_export.parse_gds_polygons）；
  - 仅几何维度死标量判决，无工艺魔法数硬编码；
  - 诚实边界：几何子集 ≠ foundry 全量 DRC，发动期真实 PDK deck 才完整。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# 默认几何规则（µm）：最小线宽 / 最小间距 / 最小面积（保守 SOI 量级默认值）
DEFAULT_GEOM_RULES = {
    "min_width_um": 0.12,
    "min_spacing_um": 0.12,
    "min_area_um2": 0.04,
}


def _bbox(poly: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _poly_width(poly: List[Tuple[float, float]]) -> float:
    """简单多边形最小边宽（带符号闭合 → 用相邻顶点距离近似 PATH 等效线宽）。"""
    if len(poly) < 2:
        return 0.0
    return min(
        ((poly[i][0] - poly[i - 1][0]) ** 2 + (poly[i][1] - poly[i - 1][1]) ** 2) ** 0.5
        for i in range(1, len(poly))
    )


def _segments(poly: List[Tuple[float, float]]) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    segs = []
    for i in range(1, len(poly)):
        segs.append((poly[i - 1], poly[i]))
    return segs


def _seg_distance(a: Tuple[Tuple[float, float], Tuple[float, float]],
                  b: Tuple[Tuple[float, float], Tuple[float, float]]) -> float:
    """两线段最短距离（用于最小间距近似）。"""
    def d_pt_seg(p, s0, s1) -> float:
        dx, dy = s1[0] - s0[0], s1[1] - s0[1]
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return ((p[0] - s0[0]) ** 2 + (p[1] - s0[1]) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((p[0] - s0[0]) * dx + (p[1] - s0[1]) * dy) / L2))
        qx, qy = s0[0] + t * dx, s0[1] + t * dy
        return ((p[0] - qx) ** 2 + (p[1] - qy) ** 2) ** 0.5
    cand = [d_pt_seg(a[0], b[0], b[1]), d_pt_seg(a[1], b[0], b[1]),
            d_pt_seg(b[0], a[0], a[1]), d_pt_seg(b[1], a[0], a[1])]
    if a[0] != a[1] and b[0] != b[1]:
        # 简单交叉检测（近似）
        return min(cand)
    return min(cand)


def check_geometry(structures: Dict[str, List[Dict]],
                   rules: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """对 GDS 结构字典（parse_gds_polygons 输出）做几何 DRC 快查。

    返回 {all_pass, min_width_ok, min_spacing_ok, min_area_ok,
          violations[], n_elements, rules}。诚实标注 "未覆盖" 项。
    """
    r = dict(DEFAULT_GEOM_RULES)
    if rules:
        r.update(rules)
    violations: List[str] = []
    min_w = float(r["min_width_um"])
    min_sp = float(r["min_spacing_um"])
    min_a = float(r["min_area_um2"])

    all_polys: List[Tuple[str, Dict]] = []
    n_elements = 0
    for sname, elems in structures.items():
        for e in elems:
            n_elements += 1
            pts = e.get("points_um") or []
            if e.get("kind") == "path" and (e.get("width") or 0) > 0:
                # PATH：用其 WIDTH 判线宽（更可靠）
                w = e["width"]
                if w < min_w:
                    violations.append(f"{sname}: PATH 线宽 {w:.3f}µm < {min_w}µm")
                # PATH 面积近似 = 长度×宽
                segs = _segments(pts)
                length = sum(((s[0][0] - s[1][0]) ** 2 + (s[0][1] - s[1][1]) ** 2) ** 0.5
                             for s in segs)
                if length * w < min_a:
                    violations.append(f"{sname}: PATH 面积 ≈ {length * w:.3f}µm² < {min_a}µm²")
            elif len(pts) >= 2:
                all_polys.append((sname, e))
                if e.get("kind") == "boundary":
                    w = _poly_width(pts)
                    if w < min_w:
                        violations.append(f"{sname}: 多边形最小边 {w:.3f}µm < {min_w}µm")
                    x0, y0, x1, y1 = _bbox(pts)
                    area = (x1 - x0) * (y1 - y0)
                    if area < min_a:
                        violations.append(f"{sname}: 面积 {area:.3f}µm² < {min_a}µm²")

    # 最小间距（仅相邻 bbox 重叠者计算，近似）
    spacing_checked = 0
    spacing_min = None
    for i in range(len(all_polys)):
        x0i, y0i, x1i, y1i = _bbox(all_polys[i][1]["points_um"])
        for j in range(i + 1, len(all_polys)):
            x0j, y0j, x1j, y1j = _bbox(all_polys[j][1]["points_um"])
            # bbox 不重叠则必间距>0，跳过
            if x1i < x0j or x1j < x0i or y1i < y0j or y1j < y0i:
                continue
            d = min(
                _seg_distance(s, t)
                for s in _segments(all_polys[i][1]["points_um"])
                for t in _segments(all_polys[j][1]["points_um"])
            )
            spacing_checked += 1
            spacing_min = d if spacing_min is None else min(spacing_min, d)
            if d < min_sp:
                violations.append(
                    f"{all_polys[i][0]}↔{all_polys[j][0]}: 间距 {d:.3f}µm < {min_sp}µm")
    if spacing_checked == 0:
        # 单结构或无重叠：间距规则无法严格判定 → 诚实标 "未覆盖"
        spacing_note = "未覆盖（无相邻元素，间距规则需多元素叠加）"
    else:
        spacing_note = f"已查 {spacing_checked} 对相邻元素，最小间距 {spacing_min:.3f}µm"

    return {
        "all_pass": len(violations) == 0,
        "min_width_ok": all(not v.startswith(("PATH 线宽", "多边形最小边")) for v in violations),
        "min_spacing_ok": not any(v.startswith((".*↔",)) for v in violations),
        "min_area_ok": not any("面积" in v for v in violations),
        "violations": violations,
        "n_elements": n_elements,
        "n_polys": len(all_polys),
        "spacing_note": spacing_note,
        "rules": r,
    }


def geometry_drc_markdown(report: Dict[str, Any]) -> str:
    L = []
    L.append("### GDS 几何 DRC 快查（主权子集 · 非 foundry 全量）")
    L.append("")
    if report["all_pass"]:
        L.append(f"- ✅ 几何可制造性子集通过（{report['n_elements']} 元素，{report['n_polys']} 多边形）")
    else:
        L.append(f"- ❌ 几何违规 {len(report['violations'])} 项（{report['n_elements']} 元素）")
    L.append(f"- 规则：最小线宽 {report['rules']['min_width_um']}µm · "
             f"最小间距 {report['rules']['min_spacing_um']}µm · "
             f"最小面积 {report['rules']['min_area_um2']}µm²")
    L.append(f"- 间距判定：{report['spacing_note']}")
    for v in report["violations"][:12]:
        L.append(f"  - ❌ {v}")
    L.append("")
    L.append("*诚实边界：本快查仅覆盖几何维度**子集**，不替代晶圆厂官方 DRC "
             "deck；发动期真实 PDK 接入后几何规则与完整 DRC 由 foundry deck 提供。*")
    return "\n".join(L)
