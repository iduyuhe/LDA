# -*- coding: utf-8 -*-
"""P0-1 覆盖护栏：真 2D 波导验收脚本（`lda_agent/verify_waveguide_2d.py`）dual-PASS 最小门禁。

背景（见 `LDA_lda_agent_code_review_P0-1_2026-09-16.md` 覆盖维度）：
- `verify_waveguide_2d.py` 是独立验收入口（时域 FDTD × 频域 slab ORACLE 双法互验，
  证明 agent 设计结果侧与物理定律锚对同一几何给出一致基模 neff），但**此前无 CI 护栏**。
- 本 smoke 在**单元层**对单个基准跑 `verify_one`，断言 dual-PASS（物理合法 + 方法一致）。
  轻量（单 2D FDTD + slab ORACLE），进 CORE_SMOKES，与全库强护栏叙事一致。

🔴 维护约束：若 `verify_one` 的判据（pass1/pass2/dual）语义变更，本 smoke 须同步；
本 smoke 自身必须在 CORE_SMOKES 内（自食其规则，`run_ci_coverage_gate_smoke` 守护）。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_agent.verify_waveguide_2d import verify_one, BENCHMARKS  # noqa: E402


def main():
    # 取首个基准（Si/SiO2 紧约束 0.5µm）做最小双法互验。
    args = BENCHMARKS[0]
    r = verify_one(*args)

    checks = [
        {
            "name": "pass1_physical_legal",
            "passed": bool(r["pass1"]),
            "detail": f"n_clad<neff_fdtd({r['ne_fdtd']:.5f})<n_core "
                      f"=> 时域解未发散/未退化",
        },
        {
            "name": "pass2_method_consistency",
            "passed": bool(r["pass2"]),
            "detail": f"|neff_fdtd-neff_oracle|/neff_oracle="
                      f"{r['rel_err']:.4%} <= {0.02:.0%}",
        },
        {
            "name": "dual_pass",
            "passed": bool(r["dual"]),
            "detail": f"dual={r['dual']} (PASS-1 ∧ PASS-2)",
        },
    ]
    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    return {
        "name": "verify_waveguide_2d dual-PASS (single benchmark)",
        "passed": passed,
        "total": total,
        "ok": passed == total,
        "checks": checks,
    }


if __name__ == "__main__":
    v = main()
    for c in v["checks"]:
        print(f"  {'✅' if c['passed'] else '❌'} {c['name']}: {c['detail']}")
    print(f"[verify_waveguide_2d] {v['passed']}/{v['total']} PASS -> "
          f"{'OK' if v['ok'] else 'FAIL'}")
    sys.exit(0 if v["ok"] else 1)
