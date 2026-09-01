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

  ⚠️ D-64（2026-09-01）判决路径独立性：因为 ReferenceCandidate 直接返回
  黄金值，|候选−黄金|≡0 ⇒ **恒 PASS、零验证价值**。本报告默认模式的「48/48
  通过」只证明**判决回路闭合**（黄金取值→比对→容差判定→报告），**不证明
  任何一项已被验证**。报告正文已加醒目警告并在 JSON 里给出
  `summary.self_consistent=true / summary.verified=0`；断言见本文件末尾
  （警告若被弄丢，CI 立刻红）。真验证须走独立候选：--ai（L3 AI 内核）、
  --perturb（故意注入偏差以演示 FAIL 检出），或 verification_adapters.py
  的独立频域候选（如 E2 的 FDFD n_g）。
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
        self_consistent = False
    elif args.perturb > 0:
        candidate = PerturbedCandidate(args.perturb)
        cand_name = "PerturbedCandidate(%.0f%%)" % (args.perturb * 100)
        self_consistent = False
    else:
        # 参考候选：候选值≡黄金值 ⇒ 恒 PASS。它只验证判决回路闭合，
        # 不验证任何求解器（D-64）。报告侧必须对此显式标注。
        candidate = ReferenceCandidate()
        cand_name = "ReferenceCandidate"
        self_consistent = True

    results = harness.run(specs, candidate)

    meta = {
        "L0_IR": args.l0 or "(内置默认 B1–B4,B8)",
        "candidate": cand_name,
        "oracle": "确定性物理定律锚（analytical/EIM/Airy/Rayleigh）",
        "self_consistent": self_consistent,
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

    # ---- 机器断言（本文件在 CI core 集内，退出码非 0 即 FAIL）----
    n_pass = sum(1 for r in results if r.passed)
    if not args.ai and args.perturb <= 0:
        # 自证闭环：判决回路必须闭合（48/48），但**不得**被读成「48 项已验证」
        assert n_pass == len(results), (
            f"自证闭环应全部 PASS，实际 {n_pass}/{len(results)}")
    assert rep.is_self_consistent(meta) is self_consistent, (
        "is_self_consistent(meta) 与本次候选语义不一致")

    if self_consistent:
        # D-64 诚实标注护栏：一旦有人改报告模板/改 meta 而弄丢警告，此处立刻红。
        assert "本报告不构成验证结论" in md, (
            "报告丢失 D-64 自证警告：外部读者会把「N/N 通过」误读为「N 项已验证」")
        assert "非验证结论" in md, "报告汇总行丢失「非验证结论」标注"
        _js = json.loads(js)
        assert _js["summary"]["self_consistent"] is True, "JSON summary.self_consistent 应为 True"
        assert _js["summary"]["verified"] == 0, (
            "自证闭环下 verified 必须为 0（passed 不代表已验证）")
        print("\n[D-64] 自证标注断言通过：报告含警告 / verified=0 / 判决回路 48/48 闭合")
    else:
        _js = json.loads(js)
        assert _js["summary"]["self_consistent"] is False, "独立候选下 self_consistent 应为 False"
        print(f"\n[D-64] 独立候选断言通过：verified={_js['summary']['verified']}/{len(results)}")


if __name__ == "__main__":
    main()
