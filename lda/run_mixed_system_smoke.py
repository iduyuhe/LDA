"""D-52 smoke：多环 WDM × 量子读出混合巨型系统（D-42 × D-51）。

2 个物理合理配置必须 PASS + 3 个负例必须 FAIL（验收双向有效）：
  - 负例 A：光子 WDM 超规格（信道跨度 > FSR → 混叠 FAIL）
  - 负例 B：量子坏 qubit（q2 T1=0.3µs → 量子子网络 FAIL）
  - 负例 C：信道数 ≠ qubit 数（映射不完整 → 全局 FAIL）
"""

import sys

sys.path.insert(0, ".")
from lda_agent.mixed_system import design_mixed_system  # noqa: E402

CASES = [
    (dict(wdm_channels_nm=[1550.0, 1553.0, 1556.0],
          qubit_f01s_ghz=[4.8, 5.0, 5.2]),
     True, "3 信道 WDM × 3 qubit 读出"),
    (dict(wdm_channels_nm=[1548.0, 1550.0, 1552.0, 1554.0],
          qubit_f01s_ghz=[5.0, 5.1, 5.2, 5.3],
          T1_us_list=[30.0, 20.0, 25.0, 18.0]),
     True, "4 信道 WDM × 4 qubit（不同 T1）"),
    (dict(wdm_channels_nm=[1550.0, 1554.0, 1558.0, 1562.0, 1566.0],
          qubit_f01s_ghz=[4.8, 5.0, 5.2]),
     False, "负例A: 5 信道 WDM 跨度超 FSR 混叠"),
    (dict(wdm_channels_nm=[1550.0, 1553.0, 1556.0],
          qubit_f01s_ghz=[4.8, 5.0, 5.2],
          T1_us_list=[20.0, 0.3, 25.0]),
     False, "负例B: q2 T1=0.3µs 量子保真度不足"),
    (dict(wdm_channels_nm=[1550.0, 1553.0, 1556.0, 1559.0],
          qubit_f01s_ghz=[4.8, 5.0, 5.2]),
     False, "负例C: 4 信道 ↔ 3 qubit 映射不完整"),
]


def main() -> int:
    ok = True
    print("=" * 76)
    print("D-52 多环 WDM × 量子读出混合巨型系统 smoke")
    print("=" * 76)
    for kw, expect, label in CASES:
        r = design_mixed_system(**kw)
        acc = r["acceptance"]
        got = bool(acc["passed"])
        good = got == expect
        ok &= good
        print(f"[{'OK  ' if good else 'FAIL'}] {label}")
        print(f"      IR {r['ir']['n_components']}器件+{r['ir']['n_nets']}网表"
              f" | checks {sum(1 for c in acc['checks'] if c['ok'])}/"
              f"{len(acc['checks'])} | passed={got}（期望 {expect}）")
        if not good:
            for c in acc["checks"]:
                if not c["ok"]:
                    print("      ✗", c["name"], "|", c["detail"][:85])
    print("=" * 76)
    print("D-52 smoke:", "ALL GREEN" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
