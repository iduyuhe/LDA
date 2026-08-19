"""LDA 验证 harness · 命令行入口。

用法：
  python run_harness.py                  # 默认：内置 B1–B4,B8 + 参考求解器（演示 pass 闭环）
  python run_harness.py --l0 examples/l0_demo_ring.json   # 从 L0 IR 读取 benchmarks
  python run_harness.py --perturb 0.10   # 注入 10% 扰动，演示 fail 检测
  python run_harness.py --ai             # L3 AI 写内核候选（有 LLM 端点则调用，否则离线近似）
  python run_harness.py --out reports    # 报告输出目录

说明：
  参考求解器（ReferenceCandidate）返回黄金参考值本身——代表"一个正确的
  求解器"。真实场景中，candidate 应是 L3 的 AI 写内核输出；harness 只负责
  "候选 vs 黄金(物理定律) 比对 + 容差判定"，是人验收的质量门。
  `--ai` 接入 `L3AISolverCandidate`：优先调用 OpenAI 兼容 LLM 端点
  （env: LDA_LLM_BASE/LDA_LLM_KEY/LDA_LLM_MODEL）让 AI 现场求解，离线或
  无密钥时回退到本地带缺陷近似，演示"部分 PASS/部分 FAIL"的真实判别。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lda_harness.benchmarks import BENCHMARK_DEFS
from lda_harness.harness import (
    VerificationHarness, ReferenceCandidate, PerturbedCandidate,
)
from lda_harness.l3_ai_solver import L3AISolverCandidate
from lda_harness import report as rep


def main():
    ap = argparse.ArgumentParser(description="LDA 验证锚点 harness")
    ap.add_argument("--l0", default=None,
                    help="L0 IR JSON 路径（含 verification.benchmarks）")
    ap.add_argument("--perturb", type=float, default=0.0,
                    help="候选求解器相对扰动（演示 fail 检测）")
    ap.add_argument("--ai", action="store_true",
                    help="接入 L3 AI 写内核候选（LLM 端点优先，否则离线近似）")
    ap.add_argument("--out", default=os.path.join(HERE, "reports"),
                    help="报告输出目录")
    args = ap.parse_args()

    harness = VerificationHarness(BENCHMARK_DEFS)

    l0_ir = None
    if args.l0:
        with open(args.l0, "r", encoding="utf-8") as f:
            l0_ir = json.load(f)

    specs = harness.resolve_specs(l0_ir)

    if args.ai:
        candidate = L3AISolverCandidate()
        cand_name = ("L3AISolverCandidate(llm=%s)" % candidate.llm_enabled)
    elif args.perturb > 0:
        candidate = PerturbedCandidate(args.perturb)
        cand_name = "PerturbedCandidate(%.0f%%)" % (args.perturb * 100)
    else:
        candidate = ReferenceCandidate()
        cand_name = "ReferenceCandidate"

    results = harness.run(specs, candidate)

    meta = {
        "L0_IR": args.l0 or "(内置默认 B1–B4,B8)",
        "candidate": cand_name,
        "oracle": "确定性物理定律锚（analytical/EIM/Airy/Rayleigh）",
    }
    md = rep.format_markdown(results, meta)
    js = rep.format_json(results, meta)

    os.makedirs(args.out, exist_ok=True)
    md_path = os.path.join(args.out, "verification_report.md")
    js_path = os.path.join(args.out, "verification_report.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js)

    print(md)
    print(f"\n报告已写入：\n  {md_path}\n  {js_path}")


if __name__ == "__main__":
    main()
