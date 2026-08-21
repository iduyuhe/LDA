"""D-59 smoke：波长相关标定库（κ_c(gap,λ) 二维 → WDM 每信道独立 k_ring）。

2 个物理合理配置必须 PASS + 3 个负例必须 FAIL（验收双向有效）：
  - 负例 A：gap 全弱耦合区 + 波长相关（k_ring 过小 IL FAIL）
  - 负例 B：5 信道跨度超 FSR + 波长相关（WDM 混叠 FAIL）
  - 负例 C：波长标定文件缺失（wl_calib 为空 → 波长标定无效 FAIL）
"""

import sys

sys.path.insert(0, ".")
from lda_agent.wdm_coupler import design_wdm_with_coupler  # noqa: E402

CASES = [
    (dict(channels_nm=[1550.0, 1553.0, 1556.0],
          gap_scan=[0.25, 0.30, 0.35], wavelength_calibrated=True),
     True, "3 信道波长相关（每信道独立 k_ring）"),
    (dict(channels_nm=[1548.0, 1550.0, 1552.0, 1554.0],
          gap_scan=[0.25, 0.30, 0.35], wavelength_calibrated=True),
     True, "4 信道波长相关（更宽跨度）"),
    (dict(channels_nm=[1550.0, 1553.0, 1556.0],
          gap_scan=[0.40, 0.45, 0.50], wavelength_calibrated=True),
     False, "负例A: gap 全弱耦合区 + 波长相关"),
    (dict(channels_nm=[1550.0, 1554.0, 1558.0, 1562.0, 1566.0],
          gap_scan=[0.25], wavelength_calibrated=True),
     False, "负例B: 5 信道跨度超 FSR + 波长相关"),
    (dict(channels_nm=[1550.0, 1553.0, 1556.0],
          gap_scan=[0.25], wavelength_calibrated=True, wl_calib={}),
     False, "负例C: 波长标定文件缺失"),
]


def main() -> int:
    ok = True
    print("=" * 76)
    print("D-59 波长相关标定库 smoke（κ_c(gap,λ) 二维 → WDM）")
    print("=" * 76)
    for kw, expect, label in CASES:
        r = design_wdm_with_coupler(**kw)
        acc = r["acceptance"]
        got = bool(acc["passed"])
        good = got == expect
        ok &= good
        pc = r.get("per_channel_kappa")
        pc_s = (("每信道 k_ring=" + str([p["k_ring"] for p in pc]))
                if pc else "（未启用/无效）")
        print(f"[{'OK  ' if good else 'FAIL'}] {label}")
        print(f"      {pc_s} | chosen={r['chosen_gap_um']} | "
              f"checks {sum(1 for c in acc['checks'] if c['ok'])}/"
              f"{len(acc['checks'])} | passed={got}（期望 {expect}）")
        if not good:
            for c in acc["checks"]:
                if not c["ok"]:
                    print("      ✗", c["name"], "|", c["detail"][:90])
    print("=" * 76)
    print("D-59 smoke:", "ALL GREEN" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
