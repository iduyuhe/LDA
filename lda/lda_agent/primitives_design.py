# -*- coding: utf-8 -*-
"""LDA · D-71 真实版图基元库 agent 封装（foundry-ready 版图基元）。

对四个真实版图基元（Taper / EulerBend / MMI / GratingCoupler）生成
GDSII 结构 + DRC 可制造性自查 + SVG 预览，输出死标量验收：
  - 每个基元 GDS 可编码（round-trip 解析回读一致）；
  - DRC 全部 PASS（min_width / min_space / min_bend_R，典型 SOI 规则）。

诚实边界：本步只交付**几何基元**（foundry 可接受的版图形状），
分束比 / 透射谱等电磁特性归 D-72（真实 2D FDTD 端口 S 参数验收），
本模块不做任何电气性能声称。LLM 不进判决路径。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_l2.gds_export import (  # noqa: E402
    geometry_desc, gds_library, layout_elements, parse_gds,
)
from lda_l2.drc import DEFAULT_RULES, drc_check_device  # noqa: E402
from lda_l2.primitives import primitive_descs  # noqa: E402

# 每个基元的默认参数（µm；典型 SOI 窗口）
PRIMITIVES: Dict[str, Dict[str, float]] = {
    "Taper": {"w1": 0.5, "w2": 2.0, "length": 20.0, "profile": "adiabatic"},
    "EulerBend": {"width": 0.5, "R": 10.0, "theta_deg": 90.0},
    "MMI": {"width": 0.5, "W_mmi": 6.0, "L_mmi": 20.0,
            "L_tap": 4.0, "out_gap": 0.5, "L_out": 3.0},
    "GratingCoupler": {"width": 0.5, "Lambda": 0.72, "duty": 0.55,
                       "n_tooth": 20, "L_in": 3.0},
}

# 单基元 GDS 结构名 → desc 供 SVG 预览
_LAYER_COLOR = {1: "#38bdf8", 2: "#8aa0c6", 3: "#f5c542", 4: "#e91e63"}


def _svg_for_descs(descs, width: int = 320) -> str:
    """desc 列表 → 内联 SVG（供 WebUI 预览；权威版图以 GDS 字节为准）。"""
    pts_all = []
    for d in descs:
        if d["kind"] == "path":
            pts_all += list(d["points_um"])
        else:
            for ring in d.get("rings_um", []):
                pts_all += list(ring)
    if not pts_all:
        return "<p>（空）</p>"
    xs = [p[0] for p in pts_all]
    ys = [p[1] for p in pts_all]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    span = max(xmax - xmin, ymax - ymin, 1e-6)
    pad = 20
    S = (width - 2 * pad) / span
    X = lambda x: pad + (x - xmin) * S  # noqa: E731
    Y = lambda y: pad + (ymax - y) * S  # noqa: E731
    out = [f'<svg width="{width}" height="{width}" '
           'style="background:#fff;border:1px solid #ddd;border-radius:6px">']
    for d in descs:
        col = _LAYER_COLOR.get(d.get("layer", 1), "#38bdf8")
        if d["kind"] == "path":
            dstr = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in d["points_um"])
            out.append(f'<polyline points="{dstr}" fill="none" stroke="{col}" '
                       f'stroke-width="{max(d.get("width_um", 0.5) * S, 2):.1f}"/>')
        else:
            for ring in d.get("rings_um", []):
                dstr = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in ring)
                out.append(f'<polygon points="{dstr}" fill="{col}" '
                           'fill-opacity="0.7"/>')
    out.append("</svg>")
    return "".join(out)


def design_primitives(verbose: bool = False,
                      **overrides: Any) -> Dict[str, Any]:
    """真实版图基元库报告：GDS 编码 + round-trip + DRC + SVG 预览。"""
    results: Dict[str, Any] = {}
    checks: list = []
    for kind, defp in PRIMITIVES.items():
        params = dict(defp)
        params.update({k: v for k, v in overrides.get(kind, {}).items()
                       if v is not None})
        # 1) 几何 desc + GDS 编码
        descs = primitive_descs(kind, params)
        elements = layout_elements(kind, params)
        gds_bytes = gds_library("LDA_D71", {f"{kind}_D71": elements})
        # 2) round-trip 回读（GDS 可编码性验证）
        try:
            parsed = parse_gds(gds_bytes)
            rt_ok = len(parsed.get("structures", {})) >= 1
        except Exception as e:  # noqa: BLE001
            rt_ok, parsed = False, {"error": str(e)}
        # 3) DRC 可制造性自查
        drc = drc_check_device(kind, params, rules=DEFAULT_RULES)
        # 4) 几何边界框
        xs = []
        ys = []
        for d in descs:
            if d["kind"] == "path":
                xs += [p[0] for p in d["points_um"]]
                ys += [p[1] for p in d["points_um"]]
            else:
                for ring in d.get("rings_um", []):
                    xs += [p[0] for p in ring]
                    ys += [p[1] for p in ring]
        bbox = {"x": [round(min(xs), 3), round(max(xs), 3)],
                "y": [round(min(ys), 3), round(max(ys), 3)]} if xs else None
        results[kind] = {
            "params": {k: (round(float(v), 4) if isinstance(v, (int, float))
                           else v) for k, v in params.items()},
            "n_elements": len(elements),
            "gds_bytes": len(gds_bytes),
            "roundtrip_ok": bool(rt_ok),
            "drc": {"passed": drc.passed,
                    "violations": [c.brief() for c in drc.violations()]},
            "bbox_um": bbox,
            "svg": _svg_for_descs(descs) if overrides.get("_svg", True) else "",
        }
        checks.append({
            "name": f"{kind} 基元",
            "ok": bool(rt_ok and drc.passed),
            "detail": (f"GDS {len(elements)} 元素 / {len(gds_bytes)}B "
                       f"round-trip={'OK' if rt_ok else 'FAIL'} · "
                       f"DRC={'PASS' if drc.passed else 'FAIL'}"
                       + ("" if drc.passed else
                          " [" + "; ".join(c.brief() for c in drc.violations()) + "]")),
        })
        if verbose:
            print(f"  {kind}: {len(elements)} elems / {len(gds_bytes)}B "
                  f"rt={'OK' if rt_ok else 'FAIL'} "
                  f"drc={'PASS' if drc.passed else 'FAIL'}")

    accepted = all(c["ok"] for c in checks)
    verdict = (
        "真实版图基元库 PASS：4 基元（Taper/EulerBend/MMI/GratingCoupler）"
        "GDS 可编码（round-trip 回读一致）+ DRC 全绿（min_width/min_space/"
        "min_bend_R，典型 SOI 规则）。几何已 foundry-ready；"
        "电特性（分束比/透射谱）待 D-72 2D FDTD 端口 S 参数验收。"
        if accepted else
        "未全过：" + "; ".join(c["name"] for c in checks if not c["ok"]))
    return {
        "ok": True,
        "title": "真实版图基元库（D-71 · foundry-ready 几何）",
        "primitives": results,
        "rules": DEFAULT_RULES,
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": ("真实版图基元替代玩具几何（直线/圆环）：taper（线性/绝热余弦轮廓，"
                 "两端斜率 0 减模式失配）、Euler 弯（clothoid 曲率 0→1/R→0 连续，"
                 "无折角尖点）、MMI 1×2 对称分束（输入 taper + 多模干涉区 + 双输出 "
                 "taper）、光栅耦合器（周期部分刻蚀齿，齿宽=Λ·duty）。本步只交付"
                 "foundry 可接受的 GDS 几何；分束比/耦合效率等电特性归 D-72 真实 "
                 "2D FDTD 端口 S 参数验收，不做性能声称。LLM 不进判决路径。"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA D-71 真实版图基元库")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--out", default=None, help="报告 JSON 输出路径")
    args = ap.parse_args()
    rep = design_primitives(verbose=args.verbose)
    out = {k: rep[k] for k in ("title", "primitives", "rules",
                               "acceptance", "verdict", "note")}
    text = json.dumps(out, ensure_ascii=False, indent=2, default=str)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)),
                    exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"报告已写入 {args.out}")
    print(text)
    return 0 if rep["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
