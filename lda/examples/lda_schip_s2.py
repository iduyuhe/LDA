"""LDA 吃狗粮 · 超导征程 S2：耦合 transmon 对 全闭环 demo（D-134）。

把「平台能设计超导多比特芯片」走完闭环：
  物理（coupler_solver 严格 J ↔ 解析 J 双验证 + cross_resonance 有效 ZX/ZZ）
  → 版图（两 transmon + 可调电容耦合器 + 整框地，零依赖 GDSII）
  → 几何 DRC/LVS 签核
  → 产物：lda_schip_s2.gds / .svg / .report.json

运行：python examples/lda_schip_s2.py（cwd=lda/）
"""
from __future__ import annotations

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in os.sys.path:
    os.sys.path.insert(0, _ROOT)

from lda_qeda import sc_coupler as S2

OUT_GDS = os.path.join(_HERE, "lda_schip_s2.gds")
OUT_SVG = os.path.join(_HERE, "lda_schip_s2.svg")
OUT_JSON = os.path.join(_HERE, "lda_schip_s2.report.json")

PARAMS = {
    "E_J1": 18.0, "E_C1": 0.25,
    "E_J2": 19.3, "E_C2": 0.25,
    "Cc": 0.007, "C1": 1.0, "C2": 1.0,
}


def main() -> int:
    print("=" * 78)
    print("LDA 超导征程 S2 · 耦合 transmon 对 全闭环 demo（D-134）")
    print("=" * 78)

    # ── 物理签核 ──
    phys = S2.coupled_pair_physics(PARAMS)
    print("── 物理签核（双验证：严格 J ↔ 解析 J · cross_resonance 有效 ZX/ZZ）──")
    print(f"  控制 qubit A  f01 = {phys['f01_A_ghz']:.4f} GHz")
    print(f"  目标 qubit B  f01 = {phys['f01_B_ghz']:.4f} GHz")
    print(f"  失谐 Δ          = {phys['detune_ghz'] * 1000:.1f} MHz  (|α|={abs(phys['alpha_B_ghz']) * 1000:.0f} MHz)")
    print(f"  耦合 J  严格     = {phys['J_num_ghz'] * 1000:.3f} MHz")
    print(f"  耦合 J  解析     = {phys['J_analytic_ghz'] * 1000:.3f} MHz  (rel={phys['J_rel_err']:.2%})")
    print(f"  有效 ZX  g_CR    = {phys['g_CR_mhz']:.3f} MHz")
    print(f"  门时间 t_CR      = {phys['t_CR_us']:.3f} µs")
    print(f"  残余 ZZ σ_zz     = {phys['sigma_zz_mhz']:.3f} MHz（echoed-CR 可抵消）")
    print(f"  物理 verdict     = {phys['verdict']}")

    # ── 版图 ──
    elems = S2.coupled_pair_cell({})
    data = S2.coupled_pair_gds({}, OUT_GDS)
    svg = S2.coupled_pair_svg_preview({})
    with open(OUT_SVG, "w", encoding="utf-8") as f:
        f.write(svg)
    print("── 版图（两 transmon + 可调电容耦合器 + 整框地）──")
    print(f"  GDS    → {OUT_GDS}  ({len(data)} bytes · {len(elems)} 元素)")
    print(f"  SVG    → {OUT_SVG}")

    # ── 几何签核 ──
    drc = S2.run_sc_pair_drc(elems)
    lvs = S2.sc_pair_lvs_signoff(elems)
    print("── 几何签核 ──")
    print(f"  DRC verdict = {drc['verdict']}  (rules={drc['n_rules']})")
    print(f"  LVS verdict = {lvs['verdict']}  (netlist={lvs['netlist']})")

    # ── 闭环判定 ──
    closed = (phys["verdict"] == "ACCEPT"
              and drc["verdict"] == "ACCEPT"
              and lvs["verdict"] == "ACCEPT")
    report = {
        "module": "D-134 · 超导耦合 transmon 对",
        "step": "S2",
        "params": PARAMS,
        "physics": phys,
        "layout": {
            "n_elements": len(elems),
            "gds_bytes": len(data),
            "drc": drc,
            "lvs": lvs,
        },
        "closed_loop": closed,
        "red_line": S2.RED_LINE_DISCLOSURE,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  report → {OUT_JSON}")
    print()
    print(f"全闭环判定：{'✅ PASS（物理+版图+签核 全 ACCEPT）' if closed else '❌ FAIL'}")
    return 0 if closed else 1


if __name__ == "__main__":
    os.sys.exit(main())
