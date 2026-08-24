"""LDA · agent 自迭代设计闭环 · 命令行演示（D-106 修复：此前 import 断链不可运行）。

演示 agent-native 设计闭环：agent 提案 → L1 驱动内核（FDTD 真求解器）→
物理定律法官验证（TMM ORACLE 死标量）→ 诊断 → 再提案，直到设计目标收敛。
是"AI for AI"可运行的最小实证（白皮书 §12）。

用法：
  python run_agent_loop.py                 # 真求解器闭环（双判据全绿）
  python run_agent_loop.py --out reports_agent
  python run_agent_loop.py --json          # 输出 JSON 报告

注：--solver l3_ai 场景（AI 写内核被法官抓残差）由 run_l1_agent_smoke.py
（L3AISolverCandidate 18/21 法官抓 FAIL）与 run_agent.py 覆盖——本演示专注
truth 求解器的收敛闭环。
"""
from __future__ import annotations

import argparse
import json
import os

from lda_agent.design_loop import DesignAgent, json_report, main as design_main


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA agent 自迭代设计闭环")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "reports_agent"),
                    help="报告输出目录")
    ap.add_argument("--json", action="store_true", help="终端输出 JSON 报告")
    args = ap.parse_args()

    rep = design_main()
    d = rep.to_dict()

    os.makedirs(args.out, exist_ok=True)
    rep_path = os.path.join(args.out, "agent_loop_report.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    # 终端摘要
    print(f"[agent 自迭代设计闭环 · bragg_mirror]")
    print(f"  收敛={d.get('accepted')}  轮次={d.get('iterations')}")
    print(f"  最终 R={d.get('final_metric')} (ORACLE={d.get('final_oracle_metric')}) "
          f"误差={d.get('final_metric_err'):.4g}")
    print(f"  判据：{d.get('verdict', '')[:60]}...")
    print(f"  报告：{rep_path}")

    if args.json:
        print("\n" + json_report(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
