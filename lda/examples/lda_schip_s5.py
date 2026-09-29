"""超导征程 S5 全闭环**批量** demo（D-137 路由 + D-142 频率 + D-143 规模 · 吃狗粮）。

在多档规模上批量签核：每档产出 lda_schip_s5_<R>x<C>.gds / .svg，并汇总
lda_schip_s5.report.json。单档闭环判定 = 路由几何 DRC + 段感知 LVS + 频率规划（含杂散 ZZ）
+ 损耗预算 全 ACCEPT。

默认档位：2×2、7×8(56)、13×13(169)；可用环境变量覆盖：
  S5_TIERS="2x2,7x8,13x13,21x21" python lda_schip_s5.py
"""
from __future__ import annotations

import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.join(_HERE, "..") not in sys.path:
    sys.path.insert(0, os.path.join(_HERE, ".."))

from lda_qeda import sc_routing as SR                                 # noqa: E402
from lda_qeda import sc_freq_alloc as FA                              # noqa: E402


def _parse_tiers(env: str):
    out = []
    for tok in env.split(","):
        tok = tok.strip().lower()
        if "x" in tok:
            r, c = tok.split("x")
            out.append((int(r), int(c)))
    return out


def _one(rows: int, cols: int) -> dict:
    params = {"rows": rows, "cols": cols}
    tag = f"{rows}x{cols}"
    elems = SR.routed_array_cell(params)
    gds_path = os.path.join(_HERE, f"lda_schip_s5_{tag}.gds")
    svg_path = os.path.join(_HERE, f"lda_schip_s5_{tag}.svg")
    gds_bytes = SR.routed_gds(params, gds_path)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(SR.routed_svg_preview(params, width=680))

    drc = SR.run_routing_drc(elems)
    lvs = SR.routed_array_lvs(elems)
    fpl = FA.plan(params)
    lb = SR.S4.loss_budget(params)
    cap = SR.routing_capacity(params)

    closed = (drc["verdict"] == "ACCEPT" and lvs["verdict"] == "ACCEPT"
              and fpl["verdict"] == "ACCEPT" and lb["verdict"] == "ACCEPT")
    return {
        "tier": tag, "rows": rows, "cols": cols, "n_qubits": rows * cols,
        "n_elements": len(elems), "gds_bytes": len(gds_bytes),
        "drc": {"verdict": drc["verdict"], "n_rules": drc["n_rules"],
                "n_violations": len(drc["violations"])},
        "lvs": {"verdict": lvs["verdict"], "netlist": lvs["netlist"],
                "n_issues": len(lvs["issues"])},
        "freq": {"verdict": fpl["verdict"], "mode": fpl["mode"],
                 "n_distinct_freqs": fpl["n_distinct_freqs"],
                 "max_stray_zz_mhz": fpl["max_stray_zz_mhz"],
                 "zz_stray_limit_mhz": fpl["zz_stray_limit_mhz"],
                 "zz_path": fpl["zz_path"]},
        "loss": {"verdict": lb["verdict"], "min_t1_total_us": lb["min_t1_total_us"],
                 "t1_target_us": lb["t1_target_us"]},
        "routing_capacity": {"n_signals": cap["n_signals"],
                             "pitch_y_eff_um": cap["pitch_y_eff_um"],
                             "pitch_y_growth": cap["pitch_y_growth"]},
        "closed_loop": closed,
    }


def main() -> int:
    tiers = _parse_tiers(os.environ.get("S5_TIERS", "2x2,7x8,13x13"))
    print("═" * 78)
    print("超导征程 S5 全闭环批量 demo（D-137/D-142/D-143）")
    print("═" * 78)

    results = []
    all_closed = True
    for (r, c) in tiers:
        t0 = time.time()
        res = _one(r, c)
        dt = time.time() - t0
        all_closed = all_closed and res["closed_loop"]
        results.append(res)
        print(f"  {res['tier']:>7} (N={res['n_qubits']:>4}) · "
              f"DRC={res['drc']['verdict']} LVS={res['lvs']['verdict']} "
              f"FREQ={res['freq']['verdict']}({res['freq']['mode']}) "
              f"LOSS={res['loss']['verdict']} · "
              f"杂散ZZ={res['freq']['max_stray_zz_mhz']:.3f}≤"
              f"{res['freq']['zz_stray_limit_mhz']} · "
              f"minT1={res['loss']['min_t1_total_us']:.1f}µs · "
              f"元素={res['n_elements']} · {dt:.2f}s · "
              f"{'✅' if res['closed_loop'] else '❌'}")

    report = {
        "module": "D-137/D-142/D-143 · 超导征程 S5 大 N P&R + 路由 + 频率避撞 + 规模压力",
        "tiers": results,
        "all_closed_loop": all_closed,
        "red_line": {"routing": SR.RED_LINE_DISCLOSURE,
                     "freq_alloc": FA.RED_LINE_DISCLOSURE},
    }
    rep_path = os.path.join(_HERE, "lda_schip_s5.report.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  汇总报告: {rep_path}")
    print(f"  批量闭环判定: {'✅ PASS' if all_closed else '❌ FAIL'}")
    return 0 if all_closed else 1


if __name__ == "__main__":
    sys.exit(main())
