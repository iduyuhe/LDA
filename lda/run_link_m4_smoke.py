"""LDA P1-M4 验证 smoke · 链路双 ground 上提。

验证项：
  1. B19 已注册为 harness B 类题，且 cmp='le'（无源无增益不等式锚）
  2. harness 门禁为真：candidate>1 必 FAIL；≤1+tol 必 PASS（证明不是自洽空转）
  3. 链路级物理锚上提模块 link_physics_harness 经真实 VerificationHarness 跑出 B19 PASS
  4. orchestrator 四 Agent 端到端闭环：verification.status=ok、b19_harness.passed、GDS 产出
  5. WebUI 端点 run_link_design 返回 ok + gds_b64
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from lda_harness.harness import VerificationHarness
from lda_harness.benchmarks import BENCHMARK_DEFS
from lda_chain.link_harness import link_physics_harness
from lda_agent.orchestrator import Orchestrator
import lda_webui.app as _app  # 仅验证端点函数可调用


def main() -> int:
    checks = []

    # 1) B19 注册 + cmp='le'
    b19 = BENCHMARK_DEFS.get("B19")
    checks.append(("B19 已注册", b19 is not None))
    checks.append(("B19 cmp='le'（不等式锚）", b19 is not None and b19.get("cmp") == "le"))

    # 2) harness 门禁为真（直接构造 B19 题，喂不同 candidate）
    defs = {"B19": b19}
    h = VerificationHarness(defs)
    specs = h.resolve_specs()  # golden=1.0, cmp='le'

    def _cand_over(spec, golden, params):
        return 1.5  # 增益 ⇒ 应 FAIL

    def _cand_ok(spec, golden, params):
        return 0.93  # 无源 ⇒ 应 PASS

    r_over = h.run(specs, _cand_over)[0]
    r_ok = h.run(specs, _cand_ok)[0]
    checks.append(("harness 门禁：增益 candidate(1.5) FAIL", not r_over.passed))
    checks.append(("harness 门禁：无源 candidate(0.93) PASS", r_ok.passed))

    # 3) link_physics_harness 经真实 harness 跑 B19
    spec = {"type": "wdm", "channels_um": [1.53, 1.55, 1.57, 1.59],
            "R_um": 10.0, "gap_um": 0.3, "kappa": 0.05, "alpha_cm": 2.5}
    ctx = Orchestrator().run(spec, out_dir=tempfile.mkdtemp())
    sim = ctx.sim
    hr = link_physics_harness(ctx.link, sim, ctx.blocked_nets)
    checks.append(("link_physics_harness 返回 B19 dict", "b19" in hr and "candidate" in hr["b19"]))
    checks.append(("B19 candidate ≤ 1.0（无源）", hr["b19"]["candidate"] <= 1.0 + 1e-9))
    checks.append(("B19 passed（经真实 harness）", hr["b19"]["passed"] is True))
    checks.append(("能量守恒诊断存在", "energy_conservation" in hr
                   and "per_source_leak" in hr["energy_conservation"]))

    # 4) orchestrator 端到端闭环
    v = ctx.verification or {}
    checks.append(("orchestrator verification.status=ok", v.get("status") == "ok"))
    checks.append(("orchestrator b19_harness.passed", (v.get("b19_harness") or {}).get("passed") is True))
    checks.append(("四 Agent 全执行", [s["agent"] for s in ctx.steps]
                   == ["planner", "synthesis", "layout", "verify"]))
    checks.append(("GDS 产出（>0 字节）", len(ctx.gds_bytes or b"") > 0))
    checks.append(("诚实边界：仅物理锚/无实证", v.get("anchor") == "physical_law_only"
                   and v.get("empirical_anchor") is False))

    # 5) WebUI 端点
    d = _app.run_link_design({"channels": "1.53,1.55,1.57,1.59", "R": 10,
                               "gap": 0.3, "kappa": 0.05, "alpha": 2.5})
    checks.append(("WebUI /api/link_design ok", d.get("ok") is True))
    checks.append(("WebUI 返回 gds_b64", isinstance(d.get("gds_b64"), str)
                   and len(d.get("gds_b64", "")) > 0))

    passed = sum(1 for _, ok in checks if ok)
    print("=" * 60)
    print("P1-M4 链路双 ground 上提 验证")
    print("=" * 60)
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"合计：{passed}/{len(checks)} PASS")
    ok_all = passed == len(checks)
    print("RESULT:", "ALL PASS" if ok_all else "HAS FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
