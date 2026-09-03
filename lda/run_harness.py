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
        _tri = candidate.describe_trichotomy()
        from lda_harness.harness import (CANDIDATE_CLASS_STRICT,
                                         CANDIDATE_CLASS_DEGRADED)
        cand_name = ("IndependentCandidateRouter(独立候选 %d 道: %s；降级量级参考 %d 道: %s)"
                     % (len(_tri[CANDIDATE_CLASS_STRICT]),
                        ",".join(_tri[CANDIDATE_CLASS_STRICT]) or "无",
                        len(_tri[CANDIDATE_CLASS_DEGRADED]),
                        ",".join(_tri[CANDIDATE_CLASS_DEGRADED]) or "无"))
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
        from lda_harness.harness import CANDIDATE_CLASS_STUB
        # 按**三分类**双向复核（v0.9.16 · P0-3 加强）：
        #   ① 非自证桩（独立/降级）⇒ |diff| 必须非零（回落 golden 即穿帮）
        #   ② 自证桩 ⇒ |diff| 必须为零（若非零，说明分类表与实现脱节）
        # 只查 ① 不查 ②，就无法发现「某道被误标成自证桩、实际已接线」的漏算。
        #
        # 🔴🔴 v0.9.24 升级（由 B10 触发，**必须**）：
        #   ① 的判据从「|diff|≡0」升级为「**|diff|≡0 且 扰动无响应**」。
        #   B10 的候选是真的 4×4 Liouvillian 超算子 RK4 积分，但生产档位
        #   |L|·t≈2.5e-4 ⇒ 残差**恒为 1.11e-16、与步数无关** ⇒ 物理上不可标定，
        #   必然落进 1e-12。旧判据会把它误判成「假独立」（实测 AssertionError:
        #   `假独立=['B10']`）。自证桩的充要特征是「**跟着 golden 走**」
        #   （ReferenceCandidate 直接 return golden、**不看 params** ⇒ 扰动后
        #   纹丝不动），不是「残差小」。
        #   🔴 判据必须与 `run_benchmark_falsifiability_smoke` 路径①⑧ **同源**
        #   —— 两处若判据不同会当场打架（v0.9.24 实测：只升 smoke 没升 CLI ⇒
        #   smoke 8/8 全绿而本文件断言失败）。故统一调 `harness.candidate_responds`。
        from lda_harness.harness import _SpecShim, candidate_responds
        from lda_harness.verification_adapters import BENCHMARK_CANDIDATES
        _spec_by_id = {s.get("id"): s for s in specs}

        def _behaves_independently(r):
            """该锚的候选是否真在算（||diff|| 非零 **或** 对扰动有物理响应）。"""
            if not (isinstance(r.candidate, (int, float))
                    and isinstance(r.golden, (int, float))):
                return True   # 非标量结果（如 dict/复数）无法用残差判，放行
            if abs(r.candidate - r.golden) >= 1e-12:
                return True
            _sp = _spec_by_id.get(r.bid)
            _key = candidate.resolve_key(r.bid)
            _fn = BENCHMARK_CANDIDATES.get(_key) if _key else None
            if _sp is None or _fn is None:
                return False  # 拿不到 spec 或候选 ⇒ 无法自证，按假独立报
            return candidate_responds(
                _SpecShim(r.bid, dict(_sp.get("params") or {})), _fn, r.golden)

        _fake_independent = [r.bid for r in results
                             if getattr(r, "candidate_class", None)
                             not in (None, CANDIDATE_CLASS_STUB)
                             and not _behaves_independently(r)]
        assert not _fake_independent, (
            f"标为独立/降级候选却 candidate≡golden（假独立）：{sorted(_fake_independent)}"
            "——路由或候选实现可能已静默回落 golden，verified 会被虚报")
        _mislabeled_stub = [r.bid for r in results
                            if getattr(r, "candidate_class", None) == CANDIDATE_CLASS_STUB
                            and isinstance(r.candidate, (int, float))
                            and isinstance(r.golden, (int, float))
                            and abs(r.candidate - r.golden) >= 1e-12]
        assert not _mislabeled_stub, (
            f"标为自证桩却 |diff|≠0（分类表与实现脱节）：{sorted(_mislabeled_stub)}"
            "——该道实际已跑真求解器，却被算进自证桩，verified 会被少算")
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
        # 三分类（P0-3）：verified + 降级 + 自证桩 == 总项数，三者不得互相吞并
        _tri_sum = _js["summary"].get("candidate_class_totals") or {}
        _n_deg = _tri_sum.get("degraded_ordinal", 0)
        assert _verified == n_independent, (
            f"verified({_verified}) 应恰为独立候选项数({n_independent})——"
            "多算=把自证桩/降级锚当已验证，少算=独立候选被降级")
        assert _stub == len(results) - n_independent - _n_deg, (
            f"自证桩数({_stub}) 应为 {len(results) - n_independent - _n_deg}")
        assert _verified + _stub + _n_deg == len(results), (
            f"verified({_verified}) + 自证桩({_stub}) + 降级({_n_deg}) "
            f"必须等于总项数({len(results)})——三分类不得互相吞并或漏算")
        if n_independent:
            assert "独立候选求解器" in md, (
                "混合态下报告必须说明「N 项独立 / M 项自证」，"
                "否则外部读者无法区分哪些真被验证")
        print(f"\n[D-64/P0-2] 混合态断言通过：独立候选 verified={_verified} · "
              f"降级量级参考 {_n_deg} · 自证桩 {_stub} · "
              f"判决回路 {n_pass}/{len(results)} 闭合")
    else:
        _js = json.loads(js)
        assert _js["summary"]["self_consistent"] is False, "独立候选下 self_consistent 应为 False"
        print(f"\n[D-64] 独立候选断言通过：verified={_js['summary']['verified']}/{len(results)}")


if __name__ == "__main__":
    main()
