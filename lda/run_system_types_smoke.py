"""Phase 1 系统类型 smoke（v0.8.33 · 提案编译器系统类型注册表）。

覆盖：
  ① SYSTEM_TYPES 注册表含 link / wdm_demux / quantum_fidelity 三类
  ② link 默认路径零回归（design_pipeline 不传 system_type 仍走 link 闭环）
  ③ wdm_demux 复用 design_wdm_advanced 已验证闭环（B4 锚：drop IL≤3 / XT≥15）
  ④ quantum_fidelity 复用 design_multiqubit_fidelity 已验证闭环（D-46×D-47）
  ⑤ 向后兼容：design_pipeline({...}) 无 system_type 参数 = link，n_accepted≥1
  ⑥ 🔴 红线：wdm/quantum 类型 honest_note 声明 LLM 不进判决路径

运行：python run_system_types_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.proposal_compiler import (
    design_pipeline, supported_system_types,
)

_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    print("Phase 1 系统类型 smoke（提案编译器 SYSTEM_TYPES 注册表）")

    # ① 注册表三类
    types = supported_system_types()
    check("SYSTEM_TYPES 含 link/wdm_demux/quantum_fidelity",
          types == ["link", "wdm_demux", "quantum_fidelity"],
          f"{types}")

    # ② link 默认路径（零回归）
    link = design_pipeline({"n_channels": 4, "channel_spacing_ghz": 100,
                            "link_budget_db": 3.0})
    check("link 默认路径：过锚提案≥1（零回归）",
          link["n_accepted"] >= 1 and link["feasible_domain"]["feasible"],
          f"过锚 {link['n_accepted']}")

    # ③ wdm_demux（复用 design_wdm_advanced）
    wdm = design_pipeline({"n_channels": 4, "spacing_nm": 2.5},
                          system_type="wdm_demux")
    wdm_acc = wdm["ranked"][0]["screening"]["accepted"]
    check("wdm_demux：B4 锚判决 ACCEPT（复用已验证闭环）",
          wdm["n_accepted"] == 1 and wdm_acc,
          wdm["ranked"][0]["screening_summary"])
    check("wdm_demux：honest_note 声明 LLM 不进判决",
          "不进判决路径" in wdm["honest_note"], "")

    # ④ quantum_fidelity（复用 design_multiqubit_fidelity）
    q = design_pipeline({"f01s": [4.8, 5.0, 5.2]},
                        system_type="quantum_fidelity")
    q_acc = q["ranked"][0]["screening"]["accepted"]
    check("quantum_fidelity：D-46×D-47 判决 ACCEPT（复用已验证闭环）",
          q["n_accepted"] == 1 and q_acc,
          q["ranked"][0]["screening_summary"])
    check("quantum_fidelity：honest_note 声明 LLM 不进判决",
          "不进判决路径" in q["honest_note"], "")

    # ⑤ 向后兼容：无 system_type = link
    legacy = design_pipeline({"n_channels": 4, "channel_spacing_ghz": 100})
    check("向后兼容：design_pipeline 无 system_type 仍走 link",
          legacy.get("system_type", "link") == "link"
          and legacy["n_accepted"] >= 1,
          f"过锚 {legacy['n_accepted']}")

    # ⑥ 未知类型报错（不静默退化）
    try:
        design_pipeline({}, system_type="nope")
        check("未知 system_type 抛错（不静默退化）", False, "未抛错")
    except ValueError:
        check("未知 system_type 抛错（不静默退化）", True, "")

    print(f"\n系统类型 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
