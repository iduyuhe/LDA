"""LDA 超导征程 · LDA-S1：单 transmon 量子比特（先能设计出来 · 全闭环签核）。

============================================================================
定位（吃自己的狗粮 · 先内后外）
----------------------------------------------------------------------------
用 LDA 平台**亲手设计**第一款超导量子计算芯片的**最小单元**——一颗固定频率
transmon 量子比特，并走完闭环：
    · 物理：等效电路 → 哈密顿量 → 闭式 f01/α 签核（复用 D-35 transmon_solver，
      Koch 解析 ↔ 严格对角化双验证）
    · 版图：在 gds_export 注册 kind="Transmon"（D-133）→ 真出 GDSII + SVG 预览
    · 签核：几何 DRC（最小线宽/JJ/地间距）+ 几何 LVS（qubit↔JJ↔ground 连接性）
    · 报告：物理 + 版图 + 签核 落盘 JSON

这是「超导量子芯片征程」第一步（对标 LOQC 的 LDA-Q1）。它证明平台**能设计出**
一颗超导比特（此前超导栈只有仿真、无版图闭环），并把设计暴露的平台能力缺口
（版图原语/几何 DRC-LVS）回填为常驻能力。

红线：纯 numpy（仅物理侧）/ 纯几何（版图侧）、LLM 不进判决路径、限值为设计规则
（非实测 golden）。
============================================================================
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "lda"))

from lda_ir import Transmon as IRTransmon
from lda_solver.transmon_solver import koch_f01, solve_transmon
from lda_qeda.sc_layout import (transmon_cell, transmon_gds,
                                transmon_svg_preview, run_sc_drc,
                                sc_lvs_signoff, RED_LINE_DISCLOSURE)

OUT = HERE


def physics_signoff(E_J: float, E_C: float) -> dict:
    """等效电路 → 哈密顿量 → 闭式 f01/α 双验证（Koch 解析 ↔ 严格对角化）。"""
    sol = solve_transmon(E_J, E_C)
    f01_an = koch_f01(E_J, E_C)
    rel = abs(sol["f01"] - f01_an) / f01_an
    return {
        "E_J_ghz": E_J, "E_C_ghz": E_C,
        "f01_diag_ghz": round(sol["f01"], 5),
        "f01_koch_ghz": round(f01_an, 5),
        "alpha_ghz": round(sol["alpha"], 5),
        "rel_err": round(rel, 6), "tol_rel": 0.03,
        "passed": bool(rel <= 0.03),
        "verdict": (f"物理双验证 PASS（严格 f01={sol['f01']:.4f} ↔ Koch {f01_an:.4f} "
                    f"rel={rel:.2%}≤3%）") if rel <= 0.03 else "物理双验证 FAIL",
    }


def main() -> int:
    print("=" * 78)
    print("LDA-S1 · 单 transmon 量子比特（全闭环签核）")
    print("=" * 78)

    # ── 1. 物理签核 ──
    E_J, E_C = 11.3, 0.30          # 典型固定频率 transmon（f01 ≈ 4.9 GHz）
    phys = physics_signoff(E_J, E_C)
    print("── 物理：等效电路 → 哈密顿量 → f01/α ──")
    print(f"  E_J={E_J} GHz, E_C={E_C} GHz ⇒ f01={phys['f01_diag_ghz']} GHz, "
          f"α={phys['alpha_ghz']} GHz, rel={phys['rel_err']:.2%}")
    print(f"  {phys['verdict']}")

    ir = IRTransmon(E_J=E_J, E_C=E_C, target_f01=phys["f01_diag_ghz"])

    # ── 2. 版图 ──
    params: dict = {"pad_w": 3.0, "pad_h": 2.0, "gap_x": 0.2, "jj_len": 0.4,
                    "jj_h": 0.3, "cpw_w": 0.5, "arm_len": 6.0,
                    "ground_gap": 1.0, "chip_half": 15.0}
    gds_path = os.path.join(OUT, "lda_schip_s1.gds")
    svg_path = os.path.join(OUT, "lda_schip_s1.svg")
    transmon_gds(params, gds_path)
    svg = transmon_svg_preview(params, width=480)
    with open(svg_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    cell = transmon_cell(params)
    print("── 版图：GDS + SVG ──")
    print(f"  GDS 已写出：{gds_path}（{len(cell)} 个几何元素 · 层 10/11/12）")
    print(f"  SVG 预览：{svg_path}")

    # ── 3. 签核 ──
    drc = run_sc_drc(cell)
    lvs = sc_lvs_signoff(cell)
    print("── 签核：几何 DRC + 几何 LVS ──")
    print(f"  DRC verdict={drc['verdict']}（{drc['n_rules']} 规则 · "
          f"violations={len(drc['violations'])}）")
    for v in drc["violations"]:
        print(f"    [DRC] {v['rule']}: {v['detail']}")
    print(f"  LVS verdict={lvs['verdict']}（netlist={lvs['netlist']} · "
          f"issues={len(lvs['issues'])}）")
    for i in lvs["issues"]:
        print(f"    [LVS] {i}")

    overall = (phys["passed"] and drc["verdict"] == "ACCEPT"
               and lvs["verdict"] == "ACCEPT")
    print()
    print(f"★ LDA-S1 全闭环：{'PASS —— 平台能设计出一颗超导 transmon 并签核通过' if overall else 'FAIL'}")

    report = {
        "chip": "LDA-S1 单 transmon 量子比特",
        "role": RED_LINE_DISCLOSURE["role"],
        "physics": phys,
        "ir_anchor": {"bid": ir.physics.bid, "kind": ir.physics.kind},
        "layout": {"gds": os.path.basename(gds_path), "svg": os.path.basename(svg_path),
                   "n_elements": len(cell), "params": params},
        "signoff": {"drc": {"verdict": drc["verdict"], "n_rules": drc["n_rules"],
                            "violations": drc["violations"]},
                    "lvs": {"verdict": lvs["verdict"], "netlist": lvs["netlist"],
                            "issues": lvs["issues"]}},
        "overall": overall,
        "disclosure": RED_LINE_DISCLOSURE,
    }
    rep_path = os.path.join(OUT, "lda_schip_s1_report.json")
    with open(rep_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(f"  报告：{rep_path}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
