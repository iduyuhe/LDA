"""D-46 smoke：N qubit 频率复用读出系统（光子-量子混合设计包）。

2 个物理合理配置必须 PASS + 2 个负例必须 FAIL（验收双向有效）：
  - 负例 A：相邻 qubit 频率过近 → readout 间隔 < 3×κ_r（串扰）→ FAIL
  - 负例 B：Δ/g=2（色散近似失效，JC 独立检测 χ rel 跳升）→ FAIL
"""

import sys

sys.path.insert(0, ".")
from lda_agent.multiqubit_readout import design_multiqubit_readout  # noqa: E402

CASES = [
    # (f01s, delta, g, kappa_ext, 期望)
    ([4.8, 5.0, 5.2], 1.0, 0.10, 0.005, True, "3 qubit 标准频率复用"),
    ([5.0, 5.1, 5.2, 5.3], 1.0, 0.10, 0.004, True, "4 qubit 更宽间隔"),
    # 注：Δ=1.5/g=0.08 时 χ=4.3MHz<κ_r=6MHz（读出不可分辨）——验收正确拒绝，故用 Δ=1.0/g=0.10
    ([5.0, 5.005], 1.0, 0.10, 0.005, False, "负例A: 读出频率过近(5MHz≈κ_r)串扰"),
    ([5.0], 0.2, 0.10, 0.005, False, "负例B: Δ/g=2 色散失效"),
]


def main() -> int:
    ok = True
    print("=" * 72)
    print("D-46 N-qubit 频率复用读出系统（光子-量子混合设计包）smoke")
    print("=" * 72)
    for f01s, delta, g, ke, expect, label in CASES:
        r = design_multiqubit_readout(f01s, delta=delta, g=g, kappa_ext=ke)
        acc = r["acceptance"]
        got = bool(acc["passed"])
        good = got == expect
        ok &= good
        fr = r["readout_freqs_ghz"]
        span = (fr[-1] - fr[0]) * 1000 if len(fr) > 1 else 0.0
        print(f"[{'OK  ' if good else 'FAIL'}] {label}")
        print(f"      f01={f01s} → readout {[round(x, 3) for x in fr]}GHz"
              f"（跨度 {span:.0f}MHz）| Δ/g={abs(delta) / g:.1f}"
              f" | checks {sum(1 for c in acc['checks'] if c['ok'])}/"
              f"{len(acc['checks'])} | passed={got}（期望 {expect}）")
        if not good:
            for c in acc["checks"]:
                if not c["ok"]:
                    print("      ✗", c["name"], "|", c["detail"][:100])
    print("=" * 72)
    print("D-46 smoke:", "ALL GREEN" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
