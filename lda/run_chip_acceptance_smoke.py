"""LDA 芯片级设计验收标准 smoke（P1-M4 补强 · 任务 254）。

验证：
  1. orchestrator 端到端产出后 chip_acceptance.accepted=True（四锚 A-D 全 PASS）
  2. 门禁为真：人为破坏（注入增益 / 缺模型 / 布线失败）→ REJECT
  3. 死标量判定：LLM 不进判决路径（全部确定性计算）
  4. accept_from_dict 轻量入口可用
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def main() -> int:
    checks = []

    # 1) orchestrator 端到端 → 芯片级验收 accepted
    from lda_agent.orchestrator import Orchestrator
    from lda_chain.chip_acceptance import accept_chip, accept_from_dict

    spec = {"type": "wdm", "channels_um": [1.53, 1.55, 1.57, 1.59],
            "R_um": 10.0, "gap_um": 0.3, "kappa": 0.05, "alpha_cm": 2.5}
    ctx = Orchestrator().run(spec, out_dir=tempfile.mkdtemp())
    ca = getattr(ctx, "chip_acceptance", None) or {}
    checks.append(("chip_acceptance 存在（编排后自动汇总）", bool(ca)))
    checks.append(("accepted=True（四锚全 PASS）", ca.get("accepted") is True))
    checks.append(("四锚 A-D 全部 passed", all(
        g.get("passed") for g in (ca.get("grounds") or {}).values())))
    checks.append(("blockers 为空", not ca.get("blockers")))
    checks.append(("anchor=physical_law_only", ca.get("anchor") == "physical_law_only"))
    checks.append(("empirical_anchor=False（诚实边界）", ca.get("empirical_anchor") is False))
    checks.append(("report 含 ACCEPT", "ACCEPT" in (ca.get("report") or "")))
    checks.append(("verification.status 与验收一致（ok）",
                   (ctx.verification or {}).get("status") == "ok"))

    # 2) 门禁为真：注入增益 → REJECT（B19 应捕获）
    from lda_chain import engine as _eng
    sim_bad = dict(ctx.sim)
    bad_transfers = {k: [v * 1.5 for v in vec]
                     for k, vec in sim_bad.get("transfers", {}).items()}
    sim_bad["transfers"] = bad_transfers
    bad_ctx = type("_C", (), {})()
    bad_ctx.link = ctx.link
    bad_ctx.sim = sim_bad
    bad_ctx.net_loss_db = ctx.net_loss_db
    bad_ctx.blocked_nets = ctx.blocked_nets
    ca_bad = accept_chip(bad_ctx)
    checks.append(("门禁：注入增益(1.5×) → REJECT", ca_bad.get("accepted") is False))
    checks.append(("门禁：REJECT 指明 A_b19_passivity", "A_b19_passivity" in
                   (ca_bad.get("blockers") or [])))

    # 3) 门禁为真：缺模型 → REJECT（D 完整性捕获）
    sim_nomodel = dict(ctx.sim)
    sim_nomodel["missing_models"] = ["phantom_ring"]
    nc = type("_C", (), {})()
    nc.link = ctx.link
    nc.sim = sim_nomodel
    nc.net_loss_db = ctx.net_loss_db
    nc.blocked_nets = ctx.blocked_nets
    ca_nm = accept_chip(nc)
    checks.append(("门禁：缺模型 → REJECT", ca_nm.get("accepted") is False))
    checks.append(("门禁：REJECT 指明 D_completeness", "D_completeness" in
                   (ca_nm.get("blockers") or [])))

    # 4) accept_from_dict 轻量入口
    ca_light = accept_from_dict(ctx.link, ctx.sim,
                                net_loss_db=ctx.net_loss_db,
                                blocked=ctx.blocked_nets)
    checks.append(("accept_from_dict 可用且 accepted",
                   ca_light.get("accepted") is True))

    # 5) 确定性：两次运行验收一致（死标量，非 LLM）
    ctx2 = Orchestrator().run(spec, out_dir=tempfile.mkdtemp())
    ca2 = getattr(ctx2, "chip_acceptance", None) or {}
    checks.append(("确定性：两次验收报告一致",
                   (ca2.get("report") or "") == (ca.get("report") or "")))

    passed = sum(1 for _, ok in checks if ok)
    print("=" * 60)
    print("芯片级设计验收标准（四锚 A-D 死标量）")
    print("=" * 60)
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"合计：{passed}/{len(checks)} PASS")
    ok_all = passed == len(checks)
    print("RESULT:", "ALL PASS" if ok_all else "HAS FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
