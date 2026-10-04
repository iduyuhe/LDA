# -*- coding: utf-8 -*-
"""PM-M3 货架脚本：光子存储**阵列版图**（真 GDS + SVG + 报告 JSON）· 自包含可复跑。

产出（落 `examples/photo_memory/`）：
  lda_pm_m3_report.json          案例卡数据源（只读消费 · 不含重算路径）
  lda_pm_m3_array_8x1.gds        8 单元串行总线阵列真 GDSII
  lda_pm_m3_array_8x1.svg        同源几何 SVG 预览（层色：Si 蓝 / GST 橙 / 加热器金）
  lda_pm_m3_array_4x8.gds        4 总线 × 8 单元阵列真 GDSII（规模压力档）

🔴 复跑纪律：本脚本是**唯一**的产物生成器；CI 不跑它（examples 不随包分发）⇒
   「入库快照 == 仓库当前状态」由 `lda/run_pm_m3_smoke.py` 的常驻判据守（比对
   报告里的 gds_sha256/计数与现场重算）。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if os.path.join(_ROOT, "lda") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "lda"))

from lda_l2 import chip_layout_export as CLE          # noqa: E402
from lda_l2 import pm_m3 as M3                        # noqa: E402

OUT = _HERE
LAYER_COLOR = {1: "#38bdf8", 5: "#f97316", 6: "#f5c542", 3: "#f5c542"}


def render_svg(geoms, title: str, path: str, width: int = 960) -> str:
    """同源几何元组 → SVG（不解析 GDS 字节；权威版图以 GDSII 为准）。"""
    xs = [p[0] for g in geoms for p in g[3]]
    ys = [p[1] for g in geoms for p in g[3]]
    if not xs:
        raise RuntimeError("空版图，无法渲染 SVG")
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    span = max(xmax - xmin, ymax - ymin, 1e-6)
    pad, top = 24, 40
    S = (width - 2 * pad) / span
    H = int((ymax - ymin) * S + 2 * pad + top)

    def X(x):
        return pad + (x - xmin) * S

    def Y(y):
        return top + pad + (ymax - y) * S

    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
           'width="%d" height="%d" style="background:#0b1020">' % (width, H, width, H),
           '<text x="%d" y="24" fill="#e2e8f0" font-size="13" '
           'font-family="monospace">%s</text>' % (pad, title)]
    for g in geoms:
        kind, layer, w, pts = g[0], int(g[1]), g[2], g[3]
        col = LAYER_COLOR.get(layer, "#94a3b8")
        d = " ".join("%.2f,%.2f" % (X(x), Y(y)) for x, y in pts)
        if kind == "P":
            out.append('<polyline points="%s" fill="none" stroke="%s" '
                       'stroke-width="%.2f"/>'
                       % (d, col, max(float(w or 0.5) * S, 1.0)))
        else:
            out.append('<polygon points="%s" fill="%s" fill-opacity="0.70"/>'
                       % (d, col))
    out.append("</svg>\n")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join(out))
    return path


def main() -> int:
    report: dict = {"generated_by": "examples/photo_memory/build_pm_m3.py"}

    # ── 主档：8 单元串行总线阵列
    arr8 = M3.build_array(8, n_buses=1)
    so8 = M3.layout_signoff(arr8)
    gds8 = so8["gds_bytes"]
    p_gds8 = os.path.join(OUT, "lda_pm_m3_array_8x1.gds")
    with open(p_gds8, "wb") as fh:
        fh.write(gds8)
    geoms8 = (CLE.device_geoms(arr8["link"], arr8["placement"], 0.5)
              + CLE.route_geoms(arr8["routes"], 0.5)
              + CLE.io_grating_geoms(arr8["link"], arr8["placement"], 0.5))
    render_svg(geoms8, "LDA PM-M3 · 8-cell PCM array (Si blue / GST orange / heater gold)",
               os.path.join(OUT, "lda_pm_m3_array_8x1.svg"))

    scan8 = M3.independent_gds_scan(gds8)
    exp8 = M3.expected_layer_counts(arr8)
    report["array_8x1"] = {
        "kind": "1 bus × 8 cells",
        "gds": {"path": "lda_pm_m3_array_8x1.gds", "bytes": len(gds8),
                "sha256": __import__("hashlib").sha256(gds8).hexdigest()},
        "svg": "lda_pm_m3_array_8x1.svg",
        "stats": so8["gds_stats"],
        "drc": {"all_pass": so8["drc_report"]["all_pass"],
                "n_checked": so8["drc_report"]["n_checked"],
                "n_pass": so8["drc_report"]["n_pass"]},
        "lvs": {"verdict": so8["lvs_report"]["verdict"],
                "n_violations": so8["lvs_report"]["n_violations"]},
        "io_ports": so8.get("io_ports", []),
        "independent_scan": scan8,
        "expected": exp8,
    }

    # ── 规模压力档：4 bus × 8 cells
    arr32 = M3.build_array(8, n_buses=4)
    so32 = M3.layout_signoff(arr32)
    p_gds32 = os.path.join(OUT, "lda_pm_m3_array_4x8.gds")
    with open(p_gds32, "wb") as fh:
        fh.write(so32["gds_bytes"])
    report["array_4x8"] = {
        "kind": "4 buses × 8 cells",
        "gds": {"path": "lda_pm_m3_array_4x8.gds", "bytes": len(so32["gds_bytes"]),
                "sha256": __import__("hashlib").sha256(so32["gds_bytes"]).hexdigest()},
        "stats": so32["gds_stats"],
        "drc_all_pass": bool(so32["drc_report"]["all_pass"]),
        "lvs_verdict": so32["lvs_report"]["verdict"],
        "lvs_n_violations": so32["lvs_report"]["n_violations"],
        "independent_scan": M3.independent_gds_scan(so32["gds_bytes"]),
    }

    # ── 全量数据（上游同源 / pitch / 预算 / 规模档 / 披露）
    full = M3.m3_report("GST")
    report.update({k: full[k] for k in
                   ("material", "device", "upstream", "pitch", "budget",
                    "scale_tiers", "disclosure", "signoff_checks")})
    report["milestone"] = full["milestone"]

    with open(os.path.join(OUT, "lda_pm_m3_report.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    ok = all(so8["checks"].values()) and all(so32["checks"].values())
    print("[PM-M3] 8x1: DRC=%s LVS=%s(%d) scan layers=%s"
          % (so8["drc_report"]["all_pass"], so8["lvs_report"]["verdict"],
             so8["lvs_report"]["n_violations"], scan8["layers"]))
    print("[PM-M3] 4x8: DRC=%s LVS=%s(%d)"
          % (so32["drc_report"]["all_pass"], so32["lvs_report"]["verdict"],
             so32["lvs_report"]["n_violations"]))
    print("[PM-M3] artifacts -> %s" % OUT)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
