"""LDA · 器件级几何（voxel_field）闭环验证。

验证目标（诚实、可复现）：
  1. stack 几何原语闭环：布拉格镜 R≥threshold，对 TMM 物理定律锚 PASS。
  2. voxel_field 几何原语闭环：同一设计意图经"机器优先版图→体素→FDTD"，
     对 TMM 物理定律锚同样 PASS。
  3. 两者最终反射率 R 逐位一致（voxel 管线零引入误差）。
  4. 直接比对 solve_spectrum 与 solve_spectrum_field_stack 的 T 谱 → 逐位一致。

用法：python verify_voxel_pipeline.py
"""
from __future__ import annotations

import os
import sys
import time

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_agent.design_loop import DesignAgent  # noqa: E402
from lda_agent.l1_protocol import load_solver, dump_json  # noqa: E402


def run_geo(geo: str, threshold: float, dl_factor: float, sponge: int):
    agent = DesignAgent(backend="numpy", dl_factor=dl_factor, sponge=sponge,
                        ramp=200, geo_kind=geo)
    intent = {
        "geometry_type": "bragg_mirror",
        "materials": {"air": 1.0, "sih": 3.48, "silo": 1.44},
        "target_wavelength_um": 1.55,
        "target_metric": "R",
        "threshold": threshold,
        "tolerance_rel": 0.02,
        "max_iterations": 12,
        "initial_periods": 1,
    }
    t0 = time.time()
    rep = agent.run(intent)
    return rep, time.time() - t0


def main():
    dl_factor, sponge = 24.0, 32
    print("=" * 68)
    print("LDA · voxel_field 器件级几何闭环验证（numpy 后端，当前沙箱可复现）")
    print("=" * 68)

    summary = {}
    for thr in (0.95, 0.99):
        rs, ts = run_geo("stack", thr, dl_factor, sponge)
        rv, tv = run_geo("voxel_field", thr, dl_factor, sponge)
        dR = abs(rs.final_metric - rv.final_metric)
        bit = dR < 1e-9
        print(f"\n[threshold={thr}]")
        print(f"  stack      : accepted={rs.accepted}  R(FDTD)={rs.final_metric:.5f}  "
              f"|ΔR|_TMM={rs.final_metric_err:.2e}  wall={ts:.1f}s")
        print(f"  voxel_field: accepted={rv.accepted}  R(FDTD)={rv.final_metric:.5f}  "
              f"|ΔR|_TMM={rv.final_metric_err:.2e}  wall={tv:.1f}s")
        print(f"  |ΔR| stack-vs-voxel = {dR:.2e}  -> {'BIT-EQUIV ✅' if bit else 'DIFF ❌'}")
        summary[f"thr_{thr}"] = {
            "stack_accepted": rs.accepted, "stack_R": rs.final_metric,
            "stack_err": rs.final_metric_err,
            "voxel_accepted": rv.accepted, "voxel_R": rv.final_metric,
            "voxel_err": rv.final_metric_err,
            "dR_stack_voxel": dR, "bit_equiv": bit,
        }

    # 直接比对两求解入口的 T 谱（用布拉格 D 题：λ0=2.46, Si/SiO2 24 单元）
    print("\n[直接谱比对] 布拉格 D 题（λ0=2.46µm, 24 单元, dl_factor=24, sponge=32）")
    lam = 2.46
    hi, lo = 3.48, 1.44
    qh, ql = lam / (4 * hi), lam / (4 * lo)
    layers = [(float("inf"), 1.0)]
    for _ in range(24):
        layers.append((qh, hi))
        layers.append((ql, lo))
    layers.append((float("inf"), 1.0))
    wls = [1.9, 2.2, 2.46, 2.7, 3.0]
    fdtd3d, _ = load_solver("numpy")
    a = fdtd3d.solve_spectrum({"layers": layers, "wavelengths_um": wls},
                              dl_factor=dl_factor, sponge=sponge)
    b = fdtd3d.solve_spectrum_field_stack(layers, wls, dl_factor=dl_factor, sponge=sponge)
    rel = max(abs(x - y) / max(y, 1e-9)
              for x, y in zip(a["transmission"], b["transmission"]))
    print(f"  solve_spectrum T      : {[round(x,5) for x in a['transmission']]}")
    print(f"  solve_spectrum_field  : {[round(x,5) for x in b['transmission']]}")
    print(f"  max rel diff          : {rel:.2e}  -> {'BIT-EQUIV ✅' if rel < 1e-12 else 'DIFF ❌'}")
    summary["direct_spectrum"] = {
        "stack_T": a["transmission"], "voxel_T": b["transmission"],
        "max_rel_diff": rel, "bit_equiv": rel < 1e-12,
    }

    ok = (summary["thr_0.95"]["stack_accepted"] and summary["thr_0.95"]["voxel_accepted"]
          and summary["thr_0.99"]["stack_accepted"] and summary["thr_0.99"]["voxel_accepted"]
          and summary["thr_0.95"]["bit_equiv"] and summary["thr_0.99"]["bit_equiv"]
          and summary["direct_spectrum"]["bit_equiv"])
    print("\n" + "=" * 68)
    print(f"总判定 : {'ALL PASS ✅' if ok else 'FAIL ❌'}")
    print("=" * 68)

    out = os.path.join(_HERE, "verify_voxel_pipeline_report.json")
    dump_json(summary, out)
    print(f"报告已落盘: {out}")


if __name__ == "__main__":
    main()
