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
    IndependentCandidateRouter,
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
        # P0-2（v0.9.15）：默认改走**独立候选路由**。
        #   IndependentCandidateRouter 按 spec_id 把已登记的锚题分发到
        #   BENCHMARK_CANDIDATES 中的独立求解器（严格数值法，与 golden 的
        #   解析闭式方法学不同源）；**未登记的锚题仍落回 ReferenceCandidate**
        #   （|diff|≡0，诚实保留自证桩，绝不假装已独立）。
        # 效果：报告的 summary.verified 首次 > 0（v0.9.14 及之前恒为 0），
        # 同时 self_consistent_stub_count 如实暴露剩余自证桩数量。
        candidate = IndependentCandidateRouter()
        _ind = candidate.describe()
        cand_name = ("IndependentCandidateRouter(独立候选 %d 道: %s)"
                     % (len(_ind), ",".join(_ind) or "无"))
        # 绝大多数锚题仍是自证桩 ⇒ 警告必须继续显示（不得因 verified>0 而撤下）
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
    # 独立候选判出的项数（P0-2）：verified 必须与之相等，
    # 且它们**必须全部 PASS**（独立候选若挂了，说明真求解器回归了）。
    n_independent = sum(1 for r in results if getattr(r, "independent", False))
    # 🔴 标签 ≠ 行为：只核对 independent 标签会被「标签为真、实现已回落 golden」
    # 骗过 —— v0.9.15 反向自检实测：把 router.__call__ 改成全回落，标签仍报
    # 4 道独立、verified=4，断言全绿 ⇒ **假绿**。故按值复核。
    #
    # ⚠️ 作用域：仅对 **IndependentCandidateRouter** 生效。该路由承诺的是
    # 「golden=解析闭式 ↔ candidate=严格数值」**方法学不同源** ⇒ |diff| 必须
    # 非零，为 0 只可能是静默回落。而 `--ai`（L3 AI 内核）语义相反：它验证的是
    # 「AI 写的内核对不对」，|diff|≡0 表示**内核把公式算对了**（B1/B4 即此情形），
    # 是合法 PASS 而非回落失败 —— 一刀切会把「算对了」误判成「假独立」。
    if isinstance(candidate, IndependentCandidateRouter):
        _fake_independent = [r.bid for r in results
                             if getattr(r, "independent", False)
                             and isinstance(r.candidate, (int, float))
                             and isinstance(r.golden, (int, float))
                             and abs(r.candidate - r.golden) < 1e-12]
        assert not _fake_independent, (
            f"标为独立候选却 candidate≡golden（假独立）：{sorted(_fake_independent)}"
            "——路由或候选实现可能已静默回落 golden，verified 会被虚报")
    if not args.ai and args.perturb <= 0:
        # 判决回路必须闭合（48/48），但**不得**被读成「48 项已验证」
        assert n_pass == len(results), (
            f"判决回路应全部 PASS，实际 {n_pass}/{len(results)}")
    assert rep.is_self_consistent(meta) is self_consistent, (
        "is_self_consistent(meta) 与本次候选语义不一致")

    if self_consistent:
        # D-64 诚实标注护栏：一旦有人改报告模板/改 meta 而弄丢警告，此处立刻红。
        assert "本报告不构成验证结论" in md, (
            "报告丢失 D-64 自证警告：外部读者会把「N/N 通过」误读为「N 项已验证」")
        assert "非验证结论" in md, "报告汇总行丢失「非验证结论」标注"
        _js = json.loads(js)
        assert _js["summary"]["self_consistent"] is True, "JSON summary.self_consistent 应为 True"
        # P0-2 混合态护栏（新增）：verified 必须**恰好**等于独立候选项数。
        # 双向护栏缺一不可：
        #   ① verified 不得多算 —— 防止自证桩被误计为「已验证」（假绿）
        #   ② verified 不得少算 —— 防止独立候选被悄悄降级回自证桩（倒退）
        _verified = _js["summary"]["verified"]
        _stub = _js["summary"]["self_consistent_stub_count"]
        assert _verified == n_independent, (
            f"verified({_verified}) 应恰为独立候选项数({n_independent})——"
            "多算=把自证桩当已验证，少算=独立候选被降级")
        assert _stub == len(results) - n_independent, (
            f"自证桩数({_stub}) 应为 {len(results) - n_independent}")
        assert _verified + _stub == len(results), (
            "verified + 自证桩 必须等于总项数（不得有第三态漏算）")
        if n_independent:
            assert "独立候选求解器" in md, (
                "混合态下报告必须说明「N 项独立 / M 项自证」，"
                "否则外部读者无法区分哪些真被验证")
        print(f"\n[D-64/P0-2] 混合态断言通过：独立候选 verified={_verified} · "
              f"自证桩 {_stub} · 判决回路 {n_pass}/{len(results)} 闭合")
    else:
        _js = json.loads(js)
        assert _js["summary"]["self_consistent"] is False, "独立候选下 self_consistent 应为 False"
        print(f"\n[D-64] 独立候选断言通过：verified={_js['summary']['verified']}/{len(results)}")


if __name__ == "__main__":
    main()
