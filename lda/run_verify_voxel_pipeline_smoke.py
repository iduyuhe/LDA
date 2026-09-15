# -*- coding: utf-8 -*-
"""P0-1 覆盖护栏：器件级几何（voxel_field）闭环验证脚本（`lda_agent/verify_voxel_pipeline.py`）最小门禁。

背景（见 `LDA_lda_agent_code_review_P0-1_2026-09-16.md` 覆盖维度）：
- `verify_voxel_pipeline.py` 验证「stack 原语闭环」与「voxel_field 机器优先版图→体素→FDTD」
  对同一设计意图给出一致的布拉格镜反射率 R（逐位一致），是器件级几何主权闭环证据；
  但**此前无 CI 护栏**。
- 本 smoke 在**单元层**对单阈值跑 stack 与 voxel_field 两条几何路径，断言：
  ① 两者均 accepted；② 两者最终 R 逐位一致（voxel 管线零引入误差）。
  进 CORE_SMOKES，与全库强护栏叙事一致。

🔴 维护约束：若 `run_geo` 返回结构（accepted/final_metric）变更，本 smoke 须同步；
本 smoke 自身必须在 CORE_SMOKES 内（自食其规则，`run_ci_coverage_gate_smoke` 守护）。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_agent.verify_voxel_pipeline import run_geo  # noqa: E402


def main():
    dl_factor, sponge, thr = 24.0, 32, 0.99
    rs, _ = run_geo("stack", thr, dl_factor, sponge)
    rv, _ = run_geo("voxel_field", thr, dl_factor, sponge)
    dR = abs(rs.final_metric - rv.final_metric)
    bit = dR < 1e-9

    checks = [
        {
            "name": "stack_accepted",
            "passed": bool(rs.accepted),
            "detail": f"stack R(FDTD)={rs.final_metric:.6f} accepted={rs.accepted}",
        },
        {
            "name": "voxel_field_accepted",
            "passed": bool(rv.accepted),
            "detail": f"voxel_field R(FDTD)={rv.final_metric:.6f} accepted={rv.accepted}",
        },
        {
            "name": "stack_vs_voxel_bit_equiv",
            "passed": bool(bit),
            "detail": f"|ΔR| stack-vs-voxel = {dR:.2e} < 1e-9 (voxel 零引入误差)",
        },
    ]
    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    return {
        "name": "verify_voxel_pipeline (stack vs voxel_field, single threshold)",
        "passed": passed,
        "total": total,
        "ok": passed == total,
        "checks": checks,
    }


if __name__ == "__main__":
    v = main()
    for c in v["checks"]:
        print(f"  {'✅' if c['passed'] else '❌'} {c['name']}: {c['detail']}")
    print(f"[verify_voxel_pipeline] {v['passed']}/{v['total']} PASS -> "
          f"{'OK' if v['ok'] else 'FAIL'}")
    sys.exit(0 if v["ok"] else 1)
