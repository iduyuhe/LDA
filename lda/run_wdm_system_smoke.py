"""LDA · WDM 多环级联系统设计 smoke。

验证「IR 网表 → 信道逆设计 → 级联响应 → 系统验收」系统级闭环：
  1. 4 信道（2.5nm 间隔）→ 每环 R 谐振对齐 + IR 网表校验通过
  2. 级联指标：每信道 drop IL ≤ 3dB、邻信道串扰 XT ≥ 15dB、thru≈0
  3. 变体：3 信道 / 5 信道 / 不同 gap 均 PASS
  4. GDS 级联版图可解析（round-trip）
LLM 不进判决路径。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_agent.wdm_system import design_wdm  # noqa: E402

CASES = [                      # (channels, gap, expect)
    ([1550.0, 1552.5, 1555.0, 1557.5], 0.3, True),   # 4 信道 2.5nm 间隔：PASS
    ([1550.0, 1553.0, 1556.0], 0.3, True),           # 3 信道 3nm 间隔：PASS
    ([1550.0, 1553.0, 1556.0, 1559.0, 1562.0], 0.35,
     False),   # 5 信道跨度 12nm > FSR 9.1nm：必须 FAIL（混叠，验收双向有效）
]


def main() -> int:
    ok = True
    print("=" * 70)
    print("WDM 多环级联系统设计（IR 网表驱动 · 系统级纵深）")
    print("=" * 70)
    for channels, gap, expect in CASES:
        r = design_wdm(channels, gap=gap)
        acc = r.get("acceptance", {})
        m = r.get("metrics", {})
        got = bool(acc.get("passed"))
        good = (got == expect)
        ok &= good
        print(f"[{'OK  ' if good else 'FAIL'}] {len(channels)} 信道 gap={gap} "
              f"(期望 {'PASS' if expect else 'FAIL'}): "
              f"R={[round(x,3) for x in r['ring_radii_um']]}µm | "
              f"IL≤{max(m.get('il_drop_db',[0])):.2f}dB | XT≥"
              f"{min(m.get('xt_min_db',[0])):.1f}dB | IR "
              f"{r['ir']['n_components']}环+{r['ir']['n_nets']}网表 | "
              f"GDS {r['gds']['size_bytes']}B | 实际 {'PASS' if got else 'FAIL'}")
        for c in acc.get("checks", []):
            if not c["ok"]:
                print("    ✗", c["name"], "：", c["detail"])
    # 4 信道结果落盘证据
    r4 = design_wdm([1550.0, 1552.5, 1555.0, 1557.5], gap=0.3)
    with open(os.path.join(_HERE, "reports", "wdm_system.json"), "w",
              encoding="utf-8") as f:
        json.dump({"all_passed": ok,
                   "case_4ch": {k: r4[k] for k in
                                ("channels_nm", "ring_radii_um", "metrics",
                                 "acceptance", "verdict", "gds")}},
                  f, ensure_ascii=False, indent=2)
    print("=" * 70)
    print("WDM 系统 smoke 全绿:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
