# -*- coding: utf-8 -*-
"""P0-1 覆盖护栏：κ_c(gap,λ) 全网格 PDK 标定脚本（`lda_agent/calibrate_kappa_grid.py`）最小门禁。

背景（见 `LDA_lda_agent_code_review_P0-1_2026-09-16.md` 覆盖维度）：
- `calibrate_kappa_grid.py` 用 2D FDTD 双点差分标定方向耦合器耦合系数 κ_c(gap,λ)，
  产出 PDK 网格（供 wdm_coupler 双线性插值）；但**此前无 CI 护栏**。
- 本 smoke 在**单元层**对单个 (gap,λ) 点跑 `kappa_fdtd`，断言：
  ① 返回有限 κ_c；② 0 < κ_c < 2 rad/µm（物理合理带）；
  ③ 交叉功率 frac 落在 (0,1)。轻量（单点 2 次 2D FDTD），进 CORE_SMOKES。

🔴 维护约束：若 `kappa_fdtd` 返回结构（κ/c1/c2/winding）变更，本 smoke 须同步；
本 smoke 自身必须在 CORE_SMOKES 内（自食其规则，`run_ci_coverage_gate_smoke` 守护）。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_agent.calibrate_kappa_grid import kappa_fdtd  # noqa: E402


def main():
    # 单点最小标定：gap=0.30µm, λ=1.55µm, dl_factor=20（与默认网格同细度）。
    k, c1, c2, winding = kappa_fdtd(0.30, 1.55, dl_factor=20)

    finite = all(math.isfinite(x) for x in (k, c1, c2))
    k_ok = 0.0 < k < 2.0                       # 方向耦合器 κ_c 物理合理带
    frac_ok = (0.0 < c1 < 1.0) and (0.0 < c2 < 1.0)  # 交叉功率占比 ∈ (0,1)

    checks = [
        {
            "name": "kappa_finite",
            "passed": bool(finite),
            "detail": f"κ_c={k:.5f} c1={c1:.3f} c2={c2:.3f} (all finite)",
        },
        {
            "name": "kappa_physically_banded",
            "passed": bool(k_ok),
            "detail": f"0 < κ_c({k:.5f}) < 2 rad/µm",
        },
        {
            "name": "cross_frac_in_01",
            "passed": bool(frac_ok),
            "detail": f"cross_frac c1={c1:.3f} c2={c2:.3f} ∈ (0,1)",
        },
    ]
    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    return {
        "name": "calibrate_kappa_grid (single gap×wl point)",
        "passed": passed,
        "total": total,
        "ok": passed == total,
        "checks": checks,
    }


if __name__ == "__main__":
    v = main()
    for c in v["checks"]:
        print(f"  {'✅' if c['passed'] else '❌'} {c['name']}: {c['detail']}")
    print(f"[calibrate_kappa_grid] {v['passed']}/{v['total']} PASS -> "
          f"{'OK' if v['ok'] else 'FAIL'}")
    sys.exit(0 if v["ok"] else 1)
