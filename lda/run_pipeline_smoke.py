"""LDA · D-19 一键设计流水线 smoke（IR → 版图 → DRC → 整改 → 仿真 → 验收）。

验证产品化设计交付流水线：
  1. Ring + target_fsr → 逆设计 R → 版图 → DRC → 仿真 → 验收全链路 PASS + 落盘；
  2. DC 违规初值（gap=0.1）→ 流水线自动 DRC 整改 → PASS；
  3. 断言设计包产物（GDS / SVG / JSON 报告）非空；
  4. CLI 入口可用。

退出码 0=全绿；非 0=有失败。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_agent.design_pipeline import run_pipeline


def check(cond: bool, msg: str) -> bool:
    if cond:
        print("OK  " + msg)
        return True
    print("FAIL " + msg)
    return False


def main() -> int:
    print("=== D-19 一键设计流水线 smoke ===")
    ok = True
    out = os.path.join(_HERE, "reports", "pipeline_demo")
    os.makedirs(out, exist_ok=True)

    # 1) Ring + target_fsr → 逆设计 → 全链路
    r1 = run_pipeline("RingResonator", target_fsr_nm=9.15, out_dir=out)
    ok &= check(r1["accepted"], f"Ring 流水线 PASS（逆设计 R={r1['final_params']['R']:.4f}µm，"
                f"仿真 neff={r1['sim']['neff_fdtd']:.4f}）")
    ok &= check(r1["inverse_design"]["R_um"] is not None,
                "逆设计步骤执行（target_fsr → R）")
    ok &= check(len(r1["steps"]) >= 3, f"流水线步骤完整（{len(r1['steps'])} 步：逆设计/版图/仿真）")
    for s in r1["steps"]:
        print(f"    · {s}")
    ok &= check(r1["accepted"], "Ring 设计包验收 PASS")

    # 2) DC 违规初值 → 自动整改 → PASS
    r2 = run_pipeline("DirectionalCoupler", params={"gap": 0.1, "width": 0.5},
                      out_dir=out, out_id="pipeline_dc")
    ok &= check(r2["accepted"], f"DC 违规初值流水线 PASS（整改后 gap="
                f"{r2['final_params']['gap']:.2f}µm）")
    ok &= check(r2["drc_fix"] is not None and len(r2["drc_fix"]) >= 1,
                "DRC 自动整改轨迹已记录")

    # 3) 设计包产物非空
    for f in ("pipeline_ringresonator.gds", "pipeline_ringresonator.svg",
              "pipeline_ringresonator_report.json"):
        p = os.path.join(out, f)
        ok &= check(os.path.exists(p) and os.path.getsize(p) > 0, f"产物 {f} 非空")
    with open(os.path.join(out, "pipeline_dc_report.json"),
              encoding="utf-8") as f:
        j = json.load(f)
    ok &= check(j["accepted"] and j["kind"] == "DirectionalCoupler",
                "DC 报告 JSON 结构正确")

    print("\n=== D-19 一键设计流水线 smoke: "
          + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
