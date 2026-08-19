"""LDA · agent 自迭代设计闭环 · 命令行演示。

用法：
  python run_agent_loop.py                 # 默认：真求解器闭环（双判据全绿）
  python run_agent_loop.py --solver l3_ai  # AI 写内核闭环（演示法官抓残差）
  python run_agent_loop.py --out reports_agent

演示 agent-native 设计闭环：agent 提案 → L1 驱动内核 → 物理定律法官验证 →
诊断 → 再提案，直到设计目标收敛。是"AI for AI"可运行的最小实证。
"""
from __future__ import annotations

import argparse
import os

from lda_l1.protocol import KernelGateway
from lda_agent.design_loop import (
    DesignAgent, ring_fsr_problem, ring_fsr_with_waveguide_problem,
)


def main():
    ap = argparse.ArgumentParser(description="LDA agent 自迭代设计闭环")
    ap.add_argument("--solver", choices=["truth", "l3_ai"], default="truth",
                    help="内核来源：truth(解析物理定律) / l3_ai(AI 写内核离线近似)")
    ap.add_argument("--dual", action="store_true",
                    help="双规格场景：同时验 B4(FSR)+B2(波导 n_eff)；"
                         "用 l3_ai 时 B2 有缺陷→法官独立抓残差")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "reports_agent"),
                    help="报告输出目录")
    args = ap.parse_args()

    gw = KernelGateway(out_dir=args.out)
    agent = DesignAgent(gw, out_dir=args.out)

    if args.dual:
        problem = ring_fsr_with_waveguide_problem(target_fsr=9.15,
                                                  solver=args.solver)
    else:
        problem = ring_fsr_problem(target_fsr=9.15, solver=args.solver)
    result = agent.run(problem, max_iter=30)

    os.makedirs(args.out, exist_ok=True)
    rep_path = os.path.join(args.out, "agent_loop_report.md")
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write(agent.format_report(result))

    # 终端摘要
    print(f"[{problem.name} · solver={args.solver}]")
    print(f"  收敛={result.converged}  轮次={result.iterations}")
    print(f"  最终 R={result.final_param} µm → FSR={result.final_metric} nm "
          f"(目标 {result.target})")
    print(f"  内核验证={'PASS(全绿)' if result.final_passed_all else 'FAIL(法官抓残差)'}")
    print(f"  结论：{result.note}")
    print(f"  报告：{rep_path}")

    if args.solver == "truth":
        print("\n# 对照：切到 AI 写内核，看法官如何独立抓出残差——")
        print("  python run_agent_loop.py --solver l3_ai")


if __name__ == "__main__":
    main()
