"""D-57 smoke：耦合器 × WDM 组合（FDTD 标定驱动 gap → WDM 系统验收）。

2 个物理合理配置必须 PASS + 3 个负例必须 FAIL（验收双向有效）：
  - 负例 A：gap_scan 全弱耦合区（0.35/0.4/0.45µm → k_ring 过小 IL FAIL）
  - 负例 B：gap_scan 越界（0.15µm < 标定文件范围 0.2 → 标定越界 FAIL）
  - 负例 C：5 信道跨度超 FSR（WDM 内部混叠 → 组合 FAIL）
"""

import sys

sys.path.insert(0, ".")
from lda_agent.wdm_coupler import design_wdm_with_coupler  # noqa: E402

CASES = [
    (dict(channels_nm=[1550.0, 1553.0, 1556.0],
          gap_scan=[0.25, 0.30, 0.35]),
     True, "3 信道标准（gap 扫描 0.25/0.3/0.35）"),
    (dict(channels_nm=[1548.0, 1550.0, 1552.0],
          gap_scan=[0.20, 0.25, 0.30]),
     True, "3 信道更密扫描（0.2/0.25/0.3）"),
    (dict(channels_nm=[1550.0, 1553.0, 1556.0],
          gap_scan=[0.35, 0.40, 0.45]),
     False, "负例A: gap 全弱耦合区（k_ring 过小）"),
    (dict(channels_nm=[1550.0, 1553.0, 1556.0],
          gap_scan=[0.15]),
     False, "负例B: gap 越界标定文件（0.15 < 0.2）"),
    (dict(channels_nm=[1550.0, 1554.0, 1558.0, 1562.0, 1566.0],
          gap_scan=[0.25]),
     False, "负例C: 5 信道跨度超 FSR（WDM 混叠）"),
]


def main() -> int:
    ok = True
    print("=" * 76)
    print("D-57 耦合器×WDM 组合 smoke（FDTD 标定驱动 gap）")
    print("=" * 76)
    for kw, expect, label in CASES:
        r = design_wdm_with_coupler(**kw)
        acc = r["acceptance"]
        got = bool(acc["passed"])
        good = got == expect
        ok &= good
        chosen = r["chosen_gap_um"]
        print(f"[{'OK  ' if good else 'FAIL'}] {label}")
        print(f"      R={r['R_typ_um']}µm | chosen gap={chosen} | "
              f"checks {sum(1 for c in acc['checks'] if c['ok'])}/"
              f"{len(acc['checks'])} | passed={got}（期望 {expect}）")
        if not good:
            for c in acc["checks"]:
                if not c["ok"]:
                    print("      ✗", c["name"], "|", c["detail"][:90])
    print("=" * 76)
    print("D-57 smoke:", "ALL GREEN" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
