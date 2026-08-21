"""LDA · D-41 量子 agent 逆设计最小闭环 smoke。

验证「给定目标频率/耦合 → IR（D-40 物理锚）→ 闭式反解 → D-39 严格数值
双验证 PASS」端到端闭环，覆盖 Transmon / Resonator / Coupler + 多器件 IR
消费（design_from_ir）。LLM 不进判决路径。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_agent.quantum_design import (design_from_ir, design_quantum)  # noqa: E402
from lda_ir import (Coupler, IRModel, ObjectiveSpec, Resonator,  # noqa: E402
                    Transmon, validate)

CASES = [
    ("Transmon", 5.0, {}),
    ("Transmon", 6.5, {"E_C": 0.22}),
    ("Resonator", 10.7583, {}),
    ("Resonator", 8.0, {"Lp": 0.5e-6}),
    ("Coupler", 0.0316, {}),
    ("Coupler", 0.08, {"E_J1": 25.0, "E_C1": 0.22}),
]


def main() -> int:
    ok = True
    print("=" * 70)
    print("D-41 量子 agent 逆设计最小闭环（目标 → IR → 数值验证 PASS）")
    print("=" * 70)
    for kind, target, extra in CASES:
        r = design_quantum(kind, target, extra)
        p = r.get("inverse_design", {}).get("params", {})
        v = r.get("verification", {})
        ok &= bool(r.get("passed"))
        print(f"[{'OK  ' if r.get('passed') else 'FAIL'}] {kind} 目标 "
              f"{target}{'GHz'} → params={p} → 严格数值 rel="
              f"{(v.get('numerical') or {}).get('rel_err')}")
    # 多器件 IR 消费（design_from_ir）
    m = IRModel(
        domain="quantum", name="multi-q",
        components=[Transmon(id="q1", E_C=0.30), Resonator(id="r1"),
                    Coupler(id="c1")],
        objectives=[ObjectiveSpec(bid="B9", target=5.0, tol=0.1),
                    ObjectiveSpec(bid="B12", target=10.7583, tol=0.02),
                    ObjectiveSpec(bid="B13", target=0.0316, tol=0.10)],
    )
    errs = validate(m)
    ok &= not errs
    out = design_from_ir(m)
    ok &= bool(out["ok"])
    for cid, d in out.get("devices", {}).items():
        ok &= bool(d.get("passed"))
        print(f"[{'OK  ' if d.get('passed') else 'FAIL'}] IR 消费 {cid} "
              f"({d['kind']}) → params={d['inverse_design']['params']}")
    print("=" * 70)
    print("D-41 全绿:", ok)
    with open(os.path.join(_HERE, "reports", "quantum_design_d41.json"), "w",
              encoding="utf-8") as f:
        json.dump({"all_passed": ok,
                   "cases": [{c[0]: {"target": c[1],
                                     "passed": design_quantum(c[0], c[1], c[2])
                                     .get("passed")}} for c in CASES]},
                  f, ensure_ascii=False, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
