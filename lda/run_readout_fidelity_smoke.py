"""D-47 smoke：单发读出保真度预算（T1 限制 · SNR/保真度）。

2 个物理合理配置必须 PASS + 3 个负例必须 FAIL（验收双向有效）：
  - 负例 A：T1=300ns（坏 qubit）→ F < 0.95 FAIL
  - 负例 B：N_amp=100（高噪放大器）→ SNR 不足 FAIL
  - 负例 C：n̄=500（非破坏超限）→ FAIL
"""

import sys

sys.path.insert(0, ".")
from lda_agent.readout_fidelity import design_fidelity  # noqa: E402

CASES = [
    # (kw, 期望, label)
    (dict(f01=5.0, delta=1.0, g=0.10, kappa_r=0.005, T1_us=20.0),
     True, "标准配置（T1=20µs, n̄=10）"),
    (dict(f01=5.0, delta=1.0, g=0.10, kappa_r=0.003, T1_us=50.0,
          nbar=20, N_amp=3.0),
     True, "高 T1 + 高 n̄ + 低噪放大器"),
    (dict(f01=5.0, delta=1.0, g=0.10, kappa_r=0.005, T1_us=0.3),
     False, "负例A: T1=300ns 保真度不足"),
    (dict(f01=5.0, delta=2.5, g=0.10, kappa_r=0.005, T1_us=20.0),
     False, "负例B: χ=0.004<κ_r=0.005 读出不可分辨"),
    (dict(f01=5.0, delta=1.0, g=0.10, kappa_r=0.005, T1_us=20.0, nbar=500.0),
     False, "负例C: n̄=500 非破坏超限"),
]


def main() -> int:
    ok = True
    print("=" * 72)
    print("D-47 单发读出保真度预算 smoke")
    print("=" * 72)
    for kw, expect, label in CASES:
        r = design_fidelity(**kw)
        acc = r["acceptance"]
        got = bool(acc["passed"])
        good = got == expect
        ok &= good
        b = r["budget"]
        print(f"[{'OK  ' if good else 'FAIL'}] {label}")
        print(f"      t_m*={r['t_m_star_ns']:.0f}ns | SNR={b['snr']:.2f} | "
              f"F={b['F']:.4f}（F0={b['F0']:.4f}·F1={b['F1']:.4f}）| "
              f"污染 {b['t1_pollution'] * 100:.2f}% | "
              f"checks {sum(1 for c in acc['checks'] if c['ok'])}/"
              f"{len(acc['checks'])} | passed={got}（期望 {expect}）")
        if not good:
            for c in acc["checks"]:
                if not c["ok"]:
                    print("      ✗", c["name"], "|", c["detail"][:90])
    print("=" * 72)
    print("D-47 smoke:", "ALL GREEN" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
