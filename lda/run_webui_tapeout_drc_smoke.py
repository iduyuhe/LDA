#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WebUI 流片签核 / 几何 DRC 端点接线 smoke · v0.9.62

验收：
  - /api/tapeout 与 /api/geometry_drc 两个 WebUI 端点确实调用到主权生产内核
    （lda_pdk.tapeout_pipeline.run_tapeout_pipeline / lda_l2.gds_drc.check_geometry），
    而非恒 True 假绿。
  - 正向：默认器件 → 返回结构化结果，且 GDS 真实生成并喂入 S3.5 寄生 / S3.6 几何 DRC。
  - 反向：极细波导（width=0.01µm < 0.12µm 规则）必须触发 DRC FAIL / 几何违规，
    证明端点接的是真实内核（会响），不是死标量或恒绿占位。
  - 诚实边界：不存在的器件 kind 必须进 skipped、不崩、不假绿。

运行：python lda/run_webui_tapeout_drc_smoke.py
"""
import sys
import os

LDA_ROOT = os.path.dirname(os.path.abspath(__file__))
if LDA_ROOT not in sys.path:
    sys.path.insert(0, LDA_ROOT)

from lda_webui import app  # 生产路径（非副本）；import 不触发 server 启动


def main() -> int:
    passed = failed = 0

    def check(name, cond, extra=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name} {extra}")

    print("=== WebUI 流片签核 / 几何 DRC 端点接线 smoke ===")

    # ---- 正向：流片签核（默认器件）----
    d = app.run_tapeout_check({"devices": {"RingAddDrop": {"R": 10.0, "gap": 0.3}}})
    check("tapeout 返回 verdict 字段", d.get("verdict") in ("ACCEPT", "REJECT"), d.get("verdict"))
    check("tapeout 真实生成版图 GDS（gds_generated）",
          d.get("gds_generated") is True, d.get("gds_generated"))
    geo = d.get("geometry_drc_result") or {}
    check("tapeout S3.6 几何 DRC 真实跑（n_elements>0）",
          isinstance(geo.get("n_elements"), int) and geo.get("n_elements") > 0, geo)
    para = d.get("parasitic_result") or {}
    # S3.5 寄生：提供 GDS 后必实跑（by_structure 非空 或 total_r 有值）
    check("tapeout S3.5 寄生估算实跑",
          para.get("passed") is not None and (para.get("total_r_ohm") is not None), para)

    # ---- 反向：流片签核（极细波导必须 FAIL）----
    d_bad = app.run_tapeout_check({"devices": {"Waveguide": {"width": 0.01}}})
    check("反向 tapeout drc_passed=False（真实内核会响）",
          d_bad.get("drc_passed") is False, d_bad.get("drc_passed"))
    check("反向 tapeout verdict=REJECT",
          d_bad.get("verdict") == "REJECT", d_bad.get("verdict"))
    geo_bad = d_bad.get("geometry_drc_result") or {}
    bad_viol = geo_bad.get("violations") or []
    check("反向 tapeout 几何 DRC 抓到线宽违规",
          any("线宽" in v for v in bad_viol), bad_viol[:1])

    # ---- 正向：几何 DRC 快查 ----
    g = app.run_geometry_drc({"devices": {"RingResonator": {"R": 10.0, "wg_width": 0.5}}})
    check("geometry_drc ok=True", g.get("ok") is True, g.get("error"))
    rep = g.get("report") or {}
    check("geometry_drc 报告含 all_pass", rep.get("all_pass") in (True, False), rep)
    check("geometry_drc 生成 markdown（非假绿占位）",
          isinstance(g.get("markdown"), str) and "几何 DRC" in g.get("markdown", ""), g.get("markdown"))

    # ---- 反向：几何 DRC（极细波导必须 FAIL）----
    g_bad = app.run_geometry_drc({"devices": {"Waveguide": {"width": 0.01}}})
    rep_bad = g_bad.get("report") or {}
    check("反向 geometry_drc all_pass=False（gds_drc 被调用）",
          rep_bad.get("all_pass") is False, rep_bad.get("all_pass"))
    check("反向 geometry_drc 抓到线宽违规",
          any("线宽" in v for v in rep_bad.get("violations", [])), rep_bad.get("violations"))

    # ---- 诚实边界：不存在的器件 kind 必须友好拒绝 / 不崩 ----
    d_un = app.run_tapeout_check({"devices": {"NoSuchDeviceXYZ": {"x": 1.0}}})
    check("不存在器件诚实拒绝（不崩、不假绿）",
          d_un.get("ok") is False
          and ("不支持" in (d_un.get("error") or "")
               or d_un.get("verdict") == "REJECT"), d_un)
    g_un = app.run_geometry_drc({"devices": {"NoSuchDeviceXYZ": {"x": 1.0}}})
    check("几何 DRC 对无几何器件返回 ok=False（诚实标注，非假绿）",
          g_un.get("ok") is False and bool(g_un.get("error")), g_un)

    print(f"\n结果：{passed} PASS / {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
