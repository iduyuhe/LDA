"""LDA · D-15 版图 DRC 自查 smoke（可制造性规则检查）。

验证版图/器件 DRC 自查：
  1. 合规器件（默认参数）DRC → PASS；
  2. 违规器件（R 过小 / gap 过小 / width 过窄 / 分叉角过大）→ 逐条检出 violation；
  3. D-12 已验证器件库全量 DRC → 默认（窗口）参数全 PASS；
  4. 输出 DRC 报告 JSON。

退出码 0=全绿；非 0=有失败。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.drc import (DEFAULT_RULES, drc_check_device, drc_from_library,
                        drc_summary)


def check(cond: bool, msg: str) -> bool:
    if cond:
        print("OK  " + msg)
        return True
    print("FAIL " + msg)
    return False


def main() -> int:
    print("=== D-15 版图 DRC 自查 smoke ===")
    ok = True

    # 1) 合规器件（默认参数）→ PASS
    cases = [
        ("Waveguide", {"width": 0.5}),
        ("RingResonator", {"R": 10.0, "wg_width": 0.5}),
        ("DirectionalCoupler", {"gap": 0.3, "width": 0.5}),
        ("SymmetricYBranch", {"width": 0.5, "split_angle": 10.0}),
    ]
    for kind, params in cases:
        r = drc_check_device(kind, params)
        ok &= check(r.passed, f"合规 {kind} DRC PASS")
        print(f"    {r.brief()}")
        for c in r.checks:
            print(f"      {c.brief()}")

    # 2) 违规器件 → 逐条检出
    bad_cases = [
        ("Waveguide", {"width": 0.2}, "min_width", "width 0.2 < 0.35"),
        ("RingResonator", {"R": 1.0}, "min_bend_R", "R 1.0 < 5.0"),
        ("DirectionalCoupler", {"gap": 0.1}, "min_space", "gap 0.1 < 0.2"),
        ("SymmetricYBranch", {"split_angle": 45.0}, "max_split",
         "split_angle 45 > 30"),
    ]
    for kind, params, rule, why in bad_cases:
        r = drc_check_device(kind, params)
        ok &= check(not r.passed, f"违规 {kind} DRC 检出 FAIL（{why}）")
        violated = {c.rule for c in r.violations()}
        ok &= check(rule in violated, f"    {kind} 违规规则={rule} 被检出")
        for c in r.violations():
            print(f"      {c.brief()}")

    # 3) D-12 器件库全量 DRC（默认窗口参数）→ 全 PASS
    lib_results = drc_from_library()
    ok &= check(all(r.passed for r in lib_results.values()),
                "D-12 器件库默认参数全过 DRC")
    print("    " + drc_summary(lib_results).replace("\n", "\n    "))

    # 4) 输出 DRC 报告 JSON
    rep_dir = os.path.join(_HERE, "reports")
    os.makedirs(rep_dir, exist_ok=True)
    report = {
        "rules": DEFAULT_RULES,
        "library": {k: v.to_dict() for k, v in lib_results.items()},
        "compliance_cases": [
            {"kind": k, "params": p, "passed": drc_check_device(k, p).passed}
            for k, p in cases
        ],
    }
    path = os.path.join(rep_dir, "drc_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"OK  导出 DRC 报告 -> {path}")

    print("\n=== D-15 版图 DRC 自查 smoke: "
          + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
