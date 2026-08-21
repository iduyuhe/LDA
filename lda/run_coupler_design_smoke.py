"""D-55 smoke：方向耦合器设计闭环（2D FDTD 真实求解器验证）。

2 个物理合理配置必须 PASS + 3 个负例必须 FAIL（验收双向有效）：
  - 负例 A：gap=0.8µm（耦合太弱 → κ 太小 → L_target 超界 FAIL）
  - 负例 B：gap=0.05µm（耦合太强 → κ 超物理量级 FAIL）
  - 负例 C：target_cross=0.995（L 超界 FAIL）
"""

import sys

sys.path.insert(0, ".")
from lda_agent.directional_coupler import design_coupler  # noqa: E402

CASES = [
    (dict(target_cross=0.50, gap_um=0.3), True, "50:50 标准（gap=0.3µm）"),
    (dict(target_cross=0.30, gap_um=0.3), True, "30:70 变体（gap=0.3µm）"),
    (dict(target_cross=0.50, gap_um=0.8), False, "负例A: gap=0.8µm 耦合过弱"),
    (dict(target_cross=0.50, gap_um=0.05), False, "负例B: gap=0.05µm 耦合过强"),
    (dict(target_cross=0.50, gap_um=0.7), False, "负例C: gap=0.7µm L 超界"),
]


def main() -> int:
    ok = True
    print("=" * 76)
    print("D-55 方向耦合器设计闭环 smoke（2D FDTD 真实求解器）")
    print("=" * 76)
    for kw, expect, label in CASES:
        r = design_coupler(transient_cycles=400, **kw)
        if not r.get("ok"):
            print(f"[{'OK  ' if not expect else 'FAIL'}] {label} → {r.get('error')}")
            ok = ok and not expect
            continue
        acc = r["acceptance"]
        got = bool(acc["passed"])
        good = got == expect
        ok &= good
        cv = r.get("cross_val_fdtd")
        cv_s = f"实测 cross={cv:.3f}" if cv is not None else "（L 超界短路）"
        print(f"[{'OK  ' if good else 'FAIL'}] {label}")
        print(f"      κ={r['kappa_fdtd']:.5f} L={r['L_target_um']:.2f}µm "
              f"{cv_s} | checks {sum(1 for c in acc['checks'] if c['ok'])}/"
              f"{len(acc['checks'])} | passed={got}（期望 {expect}）")
        if not good:
            for c in acc["checks"]:
                if not c["ok"]:
                    print("      ✗", c["name"], "|", c["detail"][:90])
    print("=" * 76)
    print("D-55 smoke:", "ALL GREEN" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
