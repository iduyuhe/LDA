# -*- coding: utf-8 -*-
"""P0.1 · WDM 网格 P&R 回归护栏（K 波长 × N×N 光子张量核）。

把 `lda_layout/wdm_mesh_pnr.py`（K 波长 × N×N Clements 网格 + 微环 add-drop
解/复用路由）接入 CI 核心门禁：任何主权链改动（placement.port_anchor /
lvs / drc / mesh_pnr 分解 / MMI 端口锚）一旦破坏下述任一条即 FAIL：

  - 每波长面保真度（分解级 + 版级）机器精度；
  - DRC PASS（逐 MZI 死标量）；
  - 单一 LinkModel 单次 LVS ACCEPT（0 违规，网络全匹配）；
  - 微环物理锚 R=m·λ/(2π·n_g) 与 FSR>信道间隔；
  - **反向护栏**（缺陷态必亮红）：断一条下路 net ⇒ LVS 拒绝；非酉 U ⇒ 分解护栏拒绝。

数据流全程几何独立：路由端点 → LVS 版图网表（几何恢复）比对原理图 netlist。

不依赖 torch/numba/cupy/meep/tidy3d；纯 numpy。按准入准则（<5s 且无重依赖）
无权豁免，必须进 CORE_SMOKES。
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))   # lda/
ROOT = os.path.dirname(HERE)                          # D:/agent_LDA
sys.path.insert(0, os.path.join(ROOT, "lda"))

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), return_ok=True, detail_on="fail")


def main() -> int:
    from lda_layout.wdm_mesh_pnr import (demo_wdm_mesh_pnr,
                                         wdm_mesh_reverse_guard)

    rep = demo_wdm_mesh_pnr(K=4, N=4)
    ok = True

    # ---- 结构 ----
    ok &= check("K=4 波长面", rep["K"] == 4, detail=str(rep["K"]))
    ok &= check("N=4 网格", rep["N"] == 4, detail=str(rep["N"]))
    ok &= check("每面 6 MZI / 合计 24（Clements 4×4）", rep["n_mzi_total"] == 24,
                detail=str(rep["n_mzi_total"]))

    # ---- 保真度（分解级 + 版级）机器精度 ----
    ok &= check("分解级保真度 ≈1.0", abs(rep["fidelity_min"] - 1.0) < 1e-9,
                detail=f"{rep['fidelity_min']:.15f}")
    ok &= check("版级保真度 ≈1.0", abs(rep["layout_fidelity_min"] - 1.0) < 1e-9,
                detail=f"{rep['layout_fidelity_min']:.15f}")
    for p in rep["per_wavelength"]:
        ok &= check(
            f"λ{p['wl_nm']:.1f}nm 面保真度（分解+版级）≈1.0",
            abs(p["fidelity"] - 1.0) < 1e-9
            and abs(p["layout_fidelity"] - 1.0) < 1e-9,
            detail=f"fid={p['fidelity']:.12f} lay={p['layout_fidelity']:.12f}")

    # ---- DRC ----
    ok &= check("DRC PASS（逐 MZI 死标量）", bool(rep["drc_pass"]))

    # ---- LVS（单一主权签核）----
    sch = rep["lvs_full"]["schematic"]
    m = rep["lvs_match"]
    ok &= check("LVS ACCEPT", rep["lvs_verdict"] == "ACCEPT",
                detail=f"{rep['lvs_verdict']} viol={rep['lvs_n_violations']}")
    ok &= check("LVS 0 违规", rep["lvs_n_violations"] == 0,
                detail=str(rep["lvs_n_violations"]))
    ok &= check("LVS 器件全匹配（n_devices_match == 原理图实例数）",
                m["n_devices_match"] == sch["n_instances"],
                detail=f"{m} sch_inst={sch['n_instances']}")
    ok &= check("LVS 网络全匹配（n_nets_match == n_nets_total）",
                m["n_nets_match"] == m["n_nets_total"], detail=str(m))

    # ---- 聚合带宽密度 ×K ----
    ok &= check("聚合带宽密度 ×K=4", rep["bandwidth_density_xK"] == 4,
                detail=str(rep["bandwidth_density_xK"]))

    # ---- 微环物理锚 ----
    a0 = rep["ring_anchors"][0]
    R_exp = 30 * (1550.0e-3) / (2.0 * math.pi * 2.45)
    ok &= check("微环半径物理锚 R=m·λ/(2π·n_g)",
                abs(a0["R_um"] - R_exp) < 1e-3,
                detail=f"R={a0['R_um']} exp={R_exp:.4f}")
    ok &= check("环 FSR > 信道间隔 25nm（不串扰）", a0["FSR_nm"] > 25.0,
                detail=f"FSR={a0['FSR_nm']}")

    # ---- GDS 非空 ----
    ok &= check("GDS 非空", rep["gds_elements"] > 0 and bool(rep["gds_bytes"]),
                detail=f"elems={rep['gds_elements']}")

    # ---- 反向护栏（护栏自证：缺陷必亮红）----
    g = wdm_mesh_reverse_guard(rep)
    ok &= check("反向 D1：断下路 net ⇒ LVS REJECT", g.get("D1_open_detected") is True,
                detail=str(g))
    ok &= check("反向 D2：非酉 U ⇒ 分解/保真护栏亮红",
                g.get("D2_nonunitary_rejected") is True, detail=str(g))

    return 0 if ok else 1


if __name__ == "__main__":
    rc = main()
    print(f"PASS={globals().get('PASS', 0)} FAIL={globals().get('FAIL', 0)}")
    sys.exit(rc)
