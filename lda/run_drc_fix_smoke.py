"""LDA · D-18 DRC 回读整改闭环 smoke（agent 自适应可制造性修复）。

验证 DrcFixAgent 闭环：
  1. 4 类违规初值（R 过小 / gap 过小 / width 过窄 / 分叉角过大）→ agent 自动
     整改 → 最终 DRC 全 PASS；
  2. 整改轨迹 violation 数逐轮下降（单调收敛）；
  3. 最终参数满足规则（留 margin）；
  4. 版图 SVG + 报告导出。

退出码 0=全绿；非 0=有失败。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_agent.drc_fix_loop import DrcFixAgent
from lda_l2.drc import drc_check_device


def check(cond: bool, msg: str) -> bool:
    if cond:
        print("OK  " + msg)
        return True
    print("FAIL " + msg)
    return False


def main() -> int:
    print("=== D-18 DRC 回读整改闭环 smoke ===")
    ok = True
    cases = [
        ("RingResonator", {"R": 2.0, "wg_width": 0.3}),
        ("Waveguide", {"width": 0.2}),
        ("DirectionalCoupler", {"gap": 0.1, "width": 0.5}),
        ("SymmetricYBranch", {"width": 0.5, "split_angle": 45.0}),
    ]

    results = {}
    for kind, bad in cases:
        r = DrcFixAgent().run(kind, bad)
        results[kind] = r
        ok &= check(r["accepted"],
                    f"{kind} 违规初值 {bad} → agent 整改 {r['iterations']} 轮可制造")
        # 最终参数满足规则
        final_ok = drc_check_device(kind, r["final_params"]).passed
        ok &= check(final_ok, f"    {kind} 最终参数 {r['final_params']} DRC PASS")
        # violation 数逐轮不增（单调收敛）
        nv = [s["n_violations"] for s in r["trace"]]
        ok &= check(nv == sorted(nv, reverse=True) and nv[-1] == 0,
                    f"    整改轨迹 violation 数单调降：{nv}")
        print(f"    verdict: {r['verdict']}")
        ok &= check("<svg" in r["layout_svg"], f"    {kind} 整改后版图 SVG 可渲染")

    # 报告导出
    rep_dir = os.path.join(_HERE, "reports")
    os.makedirs(rep_dir, exist_ok=True)
    path = os.path.join(rep_dir, "drc_fix_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({k: {"accepted": v["accepted"], "iterations": v["iterations"],
                       "final_params": v["final_params"], "trace": v["trace"]}
                   for k, v in results.items()}, f, ensure_ascii=False, indent=2)
    print(f"OK  导出整改报告 -> {path}")

    print("\n=== D-18 DRC 回读整改闭环 smoke: "
          + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
