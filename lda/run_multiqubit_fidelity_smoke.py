"""D-51 smoke：N-qubit 复用读出逐 qubit 保真度（D-46 × D-47 集成）。

2 个物理合理配置必须 PASS + 3 个负例必须 FAIL（验收双向有效）：
  - 负例 A：q2 T1=0.3µs（坏 qubit）→ q2 F1<0.95 独立 FAIL
  - 负例 B：读出频率过近（5MHz≈κ_r）→ 复用 dip 融合 FAIL
  - 负例 C：q3 n̄=500（非破坏超限）→ 逐 qubit FAIL
"""

import sys

sys.path.insert(0, ".")
from lda_agent.multiqubit_fidelity import design_multiqubit_fidelity  # noqa: E402

CASES = [
    (dict(f01s=[4.8, 5.0, 5.2], T1_us_list=[20.0, 15.0, 25.0]),
     True, "3 qubit 逐 qubit 不同 T1（20/15/25µs）"),
    (dict(f01s=[5.0, 5.1, 5.2, 5.3], delta=1.0, g=0.10,
          T1_us_list=[30.0, 20.0, 25.0, 18.0]),
     True, "4 qubit 更宽间隔 + 不同 T1"),
    (dict(f01s=[4.8, 5.0, 5.2], T1_us_list=[20.0, 0.3, 25.0]),
     False, "负例A: q2 T1=0.3µs 保真度不足"),
    (dict(f01s=[5.0, 5.005]),
     False, "负例B: 读出频率过近(5MHz≈κ_r) dip 融合"),
    (dict(f01s=[4.8, 5.0, 5.2], nbar_list=[10.0, 10.0, 500.0]),
     False, "负例C: q3 n̄=500 非破坏超限"),
]


def main() -> int:
    ok = True
    print("=" * 76)
    print("D-51 N-qubit 复用读出逐 qubit 保真度（D-46×D-47 集成）smoke")
    print("=" * 76)
    for kw, expect, label in CASES:
        r = design_multiqubit_fidelity(**kw)
        acc = r["acceptance"]
        got = bool(acc["passed"])
        good = got == expect
        ok &= good
        fs = [q["budget"]["F"] for q in r["per_qubit"]]
        print(f"[{'OK  ' if good else 'FAIL'}] {label}")
        print(f"      F per qubit={[round(f, 4) for f in fs]} | "
              f"checks {sum(1 for c in acc['checks'] if c['ok'])}/"
              f"{len(acc['checks'])} | passed={got}（期望 {expect}）")
        if not good:
            for c in acc["checks"]:
                if not c["ok"]:
                    print("      ✗", c["name"], "|", c["detail"][:90])
    print("=" * 76)
    print("D-51 smoke:", "ALL GREEN" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
