"""LDA · D-29 方向耦合器全场透射谱 smoke。

验证 fdtd2d_coupler（2D FDTD DC 功率交换 vs 波长）：
  1. 结构自检（始终）：场构造（双波导芯区几何）+ CMT 公式
  2. 谱形验收（numpy，快）：cross 功率单调递增（CMT tan²(κL) 趋势）+
    cross_frac 与超模法 κ(λ) CMT 预测平均偏差 ≤ 容差
  3. 报告落盘 reports/dc_transmission_report.json
"""
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "lda_solver"))

from lda_solver.fdtd2d_coupler import (  # noqa: E402
    build_dc_field, dc_transmission_spectrum, run_dc_transmission,
)


def check(cond: bool, msg: str, report: dict, key: str) -> bool:
    status = "OK  " if cond else "FAIL"
    print(f"[{status}] {msg}")
    report["checks"].append({"key": key, "ok": bool(cond), "msg": msg})
    return bool(cond)


def main() -> int:
    report: dict = {"d29": "DC transmission spectrum", "checks": []}
    ok = True

    # 1) 结构自检（始终，无数值）
    w, gap, nc, ncl = 0.5, 0.3, 3.48, 1.44
    dl = 1.55 / 20.0
    eps2, dl, Nx, Ny, yoff = build_dc_field(w, gap, nc, ncl, dl, Lx_um=26.0)
    core_cells = int(np.sum(eps2 > (ncl ** 2 + nc ** 2) / 2.0))
    ok &= check(core_cells > 0 and Nx > 100 and Ny > 20,
                f"DC 双波导场构造：Nx={Nx} Ny={Ny}，芯区 {core_cells} cells",
                report, "field")

    # 2) 谱形验收（numpy，7 波长 ≈1min）
    rep = run_dc_transmission(w_um=w, gap_um=gap, n_points=7, span_um=0.06)
    report["live"] = {
        "cross_frac_fdtd": rep["cross_frac_fdtd"],
        "kappa_fdtd": rep["kappa_fdtd"],
        "monotone_increasing": rep["monotone_increasing"],
        "kappa_monotone": rep["kappa_monotone"],
        "kappa_in_range": rep["kappa_in_range"],
    }
    ok &= check(rep["monotone_increasing"],
                f"cross 功率单调递增：{rep['cross_frac_fdtd']}"
                "（CMT 功率交换趋势，κ 随 λ 增）", report, "trend")
    ok &= check(rep["kappa_monotone"],
                f"反解 κ_fdtd 单调递增：{rep['kappa_fdtd']}"
                "（与 D-23 3D 超模法趋势一致）", report, "kappa_mono")
    ok &= check(rep["kappa_in_range"],
                f"κ_fdtd 物理量级 [{rep['kappa_min']},{rep['kappa_max']}] rad/µm",
                report, "kappa_range")
    ok &= check(rep["accepted"],
                f"DC 全场透射谱验收 PASS：{rep['verdict'][:80]}", report, "accept")

    out_path = os.path.join(_HERE, "reports", "dc_transmission_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告：{out_path}")
    print("D-29 DC 全场透射谱 smoke:", "ALL GREEN" if ok else "HAS FAILURE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
