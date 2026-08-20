"""LDA · D-21 DRC 工艺规则从 PDK 注入 smoke（多晶圆厂可制造性差异）。

验证 DRC 规则按 foundry 取：
  1. 各 foundry 的 design_rules 提取正确（min_bend_R 不同：CUMEC 4 / NOEIC 5 / SITRI 6）；
  2. 同一设计（如 Ring R=4.5µm）在不同 foundry 可制造性不同——CUMEC 合规、
     NOEIC/SITRI 违规（工艺窗口驱动差异）；
  3. D-12 器件库默认参数在所选 foundry 规则下 DRC 全过；
  4. 多 foundry DRC 对比报告导出。

退出码 0=全绿；非 0=有失败。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.drc import drc_check_device, rules_from_pdk
from lda_l2.pdk import get_default_registry


def check(cond: bool, msg: str) -> bool:
    if cond:
        print("OK  " + msg)
        return True
    print("FAIL " + msg)
    return False


def main() -> int:
    print("=== D-21 DRC 工艺规则从 PDK 注入 smoke ===")
    ok = True
    reg = get_default_registry()
    photon = [k for k in reg.list_pdks() if "量子" not in k]

    # 1) 各 foundry 规则提取 + 差异
    rules = {}
    for k in photon:
        rules[k] = rules_from_pdk(reg.get(k))
    bends = {k: rules[k]["min_bend_R_um"] for k in photon}
    ok &= check(len(set(bends.values())) == 3,
                f"3 个光子 foundry 的 min_bend_R 各不相同（{bends}）")
    for k in photon:
        print(f"    {k.split('::')[0]:<8} 规则 {rules[k]}")

    # 2) 同一设计在不同 foundry 可制造性差异（Ring R=4.5µm）
    ring_design = {"R": 4.5, "wg_width": 0.5}
    verdicts = {}
    for k in photon:
        r = drc_check_device("RingResonator", ring_design, rules=rules[k])
        verdicts[k] = r.passed
        print(f"    Ring R=4.5µm @ {k.split('::')[0]}: "
              f"{'可制造 PASS' if r.passed else 'min_bend 违规 FAIL'}")
    ok &= check(verdicts[photon[1]] and not verdicts[photon[0]]
                and not verdicts[photon[2]],
                "同一设计跨厂差异：CUMEC(min_bend 4)可制造、"
                "NOEIC(5)/SITRI(6)违规")

    # 3) D-12 器件库默认参数在 CUMEC 规则下 DRC 全过
    from lda_l2.device_library import get_default_library
    lib = get_default_library()
    cumec_rules = rules[photon[1]]
    lib_ok = True
    for name in lib.list():
        dev = lib.get(name)
        params = {k: (lo + hi) / 2.0 for k, (lo, hi) in dev.params_schema.items()}
        try:
            r = drc_check_device(name, params, rules=cumec_rules)
        except ValueError:
            continue  # Bragg 一维堆叠
        lib_ok = lib_ok and r.passed
        print(f"    CUMEC 规则下 {name:<20} {'PASS' if r.passed else 'FAIL'}")
    ok &= check(lib_ok, "D-12 器件库默认参数在 CUMEC 规则下全过 DRC")

    # 4) 多 foundry DRC 对比报告导出
    rep_dir = os.path.join(_HERE, "reports")
    os.makedirs(rep_dir, exist_ok=True)
    report = {
        "ring_R4.5_verdict": {k: v for k, v in verdicts.items()},
        "foundry_rules": {k: v for k, v in rules.items()},
    }
    path = os.path.join(rep_dir, "drc_pdk_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"OK  导出多 foundry DRC 对比报告 -> {path}")

    print("\n=== D-21 DRC 工艺规则从 PDK 注入 smoke: "
          + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
