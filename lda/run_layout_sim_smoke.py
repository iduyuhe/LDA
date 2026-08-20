"""LDA · D-16 版图 → 仿真闭环 smoke（GDS 几何 → FDTD → 物理锚验收）。

验证「版图 → 仿真 → 验收」闭环：
  1. D-14 版图描述（geometry_desc）提取波导宽度 → FDTD neff → slab ORACLE
     验收 PASS（相对误差 ≤ tol）；
  2. 多种版图（Waveguide / Ring bus / IR 端到端）；
  3. eps 场正确性（芯 n_core² / 包层 n_clad²）；
  4. 报告导出。

退出码 0=全绿；非 0=有失败。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.gds_export import geometry_desc
from lda_l2.layout_sim import (find_waveguide_width, simulate_layout,
                               simulate_layout_from_ir, build_eps_from_layout)
from lda_ir import IRModel, Waveguide, RingResonator


def check(cond: bool, msg: str) -> bool:
    if cond:
        print("OK  " + msg)
        return True
    print("FAIL " + msg)
    return False


def main() -> int:
    print("=== D-16 版图 → 仿真闭环 smoke ===")
    ok = True
    N_SI, N_SIO2, WL = 3.48, 1.44, 1.55

    # 1) Waveguide 版图 → 仿真 → ORACLE 验收
    wg_desc = geometry_desc("Waveguide", {"width": 0.5})
    w = find_waveguide_width(wg_desc)
    ok &= check(w == 0.5, "版图描述提取波导宽度 width=0.5µm")
    r1 = simulate_layout(wg_desc, N_SI, N_SIO2, WL)
    ok &= check(r1["passed"], f"Waveguide 版图仿真 PASS（neff={r1['neff_fdtd']:.4f} "
                f"vs ORACLE {r1['neff_oracle']:.4f}，rel={r1['rel_err']:.3%}≤2%）")

    # 2) RingResonator 版图（bus PATH）→ 仿真
    ring_desc = geometry_desc("RingResonator", {"R": 10.0, "wg_width": 0.5})
    r2 = simulate_layout(ring_desc, N_SI, N_SIO2, WL)
    ok &= check(r2["passed"], f"Ring bus 版图仿真 PASS（width={r2['width_um']}µm，"
                f"neff={r2['neff_fdtd']:.4f}）")

    # 3) IR 端到端：IR → 版图几何 → FDTD → ORACLE
    m = IRModel(domain="photon", name="wg-loop",
                components=[Waveguide(id="wg", width=0.5)])
    r3 = simulate_layout_from_ir(m, N_SI, N_SIO2, WL)
    ok &= check(r3["passed"] and r3["ir_kind"] == "Waveguide",
                f"IR 端到端仿真 PASS（{r3['ir_kind']}@{r3['ir_id']}，"
                f"neff={r3['neff_fdtd']:.4f}）")

    # 4) eps 场正确性（芯区 n_core²，包层 n_clad²）
    eps2 = build_eps_from_layout(0.5, N_SI, N_SIO2, WL)
    core_mask = eps2 > (N_SI ** 2 + N_SIO2 ** 2) / 2.0
    ok &= check(float(eps2[core_mask].max()) == float(N_SI ** 2)
                and float(eps2[~core_mask].min()) == float(N_SIO2 ** 2),
                "eps 场芯区=n_core² 包层=n_clad² 正确")
    print(f"    eps 场 shape={eps2.shape} 芯占比={core_mask.mean():.1%}")

    # 5) 报告导出
    rep_dir = os.path.join(_HERE, "reports")
    os.makedirs(rep_dir, exist_ok=True)
    report = {
        "waveguide_layout": r1,
        "ring_bus_layout": r2,
        "ir_end_to_end": r3,
    }
    path = os.path.join(rep_dir, "layout_sim_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"OK  导出仿真报告 -> {path}")

    print("\n=== D-16 版图 → 仿真闭环 smoke: "
          + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
