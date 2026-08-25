"""P1-M3 smoke：Agent 元编排 + L1 原语扩展 端到端验证。

验证项：
  1) Orchestrator 四 Agent 端到端：planner→synthesis→layout→verify 全部执行，
     verification.status=ok，GDS 产出，net 损耗计入，无 blocked net。
  2) L1 KernelGateway 四个新原语：link_simulate / route / place / export_chip_gds
     均返回结构化 AgentResponse（status 合法、字段齐全）。
  3) 一致性：orchestrator 的 link_simulate 与 L1 link_simulate 原语调用同一引擎，
     传递谱峰值量级一致。
  4) 确定性：同一 spec 跑两次，verification 完全一致。
  5) 物理锚：passivity_no_gain 检查 PASS（无源网络 |T|≤1）。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_agent.orchestrator import Orchestrator
from lda_l1.protocol import KernelGateway, AgentRequest


SPEC = {
    "type": "wdm",
    "channels_um": [1.53, 1.55, 1.57, 1.59],
    "R_um": 10.0,
    "gap_um": 0.3,
    "kappa": 0.05,
    "alpha_cm": 2.5,
}


def _run_orchestrator(out_dir):
    return Orchestrator().run(
        dict(SPEC),
        layout_opts={"wg_width": 0.5, "bend_radius": 5.0},
        out_dir=out_dir,
    )


def main() -> int:
    checks = []
    tmp = tempfile.mkdtemp(prefix="lda_m3_")

    # --- 1) Orchestrator 端到端 ---
    ctx = _run_orchestrator(tmp)
    steps_agents = {s["agent"] for s in ctx.steps}
    checks.append(("四 Agent 全部执行",
                   steps_agents == {"planner", "synthesis", "layout", "verify"}))
    checks.append(("verification.status == ok",
                   ctx.verification.get("status") == "ok"))
    checks.append(("GDS 产出且非空", len(ctx.gds_bytes) > 0))
    checks.append(("net 损耗计入（>0）",
                   sum(ctx.net_loss_db.values()) > 0))
    checks.append(("无 blocked net", len(ctx.blocked_nets) == 0))
    checks.append(("物理锚 passivity_no_gain PASS",
                   any(c["name"] == "passivity_no_gain" and c["passed"]
                       for c in ctx.verification["checks"])))
    checks.append(("链路级诚实标注：无实证锚",
                   ctx.verification.get("empirical_anchor") is False))
    checks.append(("落盘产物存在",
                   os.path.exists(ctx.artifacts["gds"])
                   and os.path.exists(ctx.artifacts["report"])))

    # --- 2) L1 原语 ---
    gw = KernelGateway()
    # link_simulate
    r1 = gw.handle(AgentRequest("link_simulate", {"spec": SPEC}))
    checks.append(("L1 link_simulate ok", r1.status == "ok"
                   and len(r1.result.get("transfers", {})) > 0))
    # place
    r2 = gw.handle(AgentRequest("place", {"spec": SPEC}))
    checks.append(("L1 place ok", r2.status == "ok"
                   and r2.result.get("n_inst", 0) >= 4))  # 至少 4 个 ring 实例
    # export_chip_gds
    r3 = gw.handle(AgentRequest("export_chip_gds", {"spec": SPEC}))
    checks.append(("L1 export_chip_gds ok", r3.status in ("ok", "partial")
                   and r3.result.get("n_routed", 0) >= 1))
    # route（单 net：干净路由应成功；带障碍应返回结构化结果）
    r4 = gw.handle(AgentRequest("route", {
        "src": [0.0, 0.0], "dst": [20.0, 0.0],
        "obstacles": [], "wg_width": 0.5, "bend_radius": 5.0,
    }))
    checks.append(("L1 route 干净路由 ok", r4.status == "ok"
                   and "total_loss_db" in r4.result))
    r4b = gw.handle(AgentRequest("route", {
        "src": [0.0, 0.0], "dst": [20.0, 0.0],
        "obstacles": [[10.0, 0.0, 1.0, 1.0]],
        "wg_width": 0.5, "bend_radius": 5.0,
    }))
    checks.append(("L1 route 带障碍返回结构化结果",
                   r4b.status in ("ok", "fail")
                   and "total_loss_db" in r4b.result))

    # --- 3) 一致性：orchestrator 与 L1 link_simulate 同引擎同损耗同波长 ---
    # 用 orchestrator 的精确波长网格喂给 L1 原语，确保位级一致（不重复造波长网格）
    orch_transfers = ctx.sim.get("transfers", {})
    r1b = gw.handle(AgentRequest("link_simulate",
                                 {"spec": SPEC,
                                  "net_loss_db": ctx.net_loss_db,
                                  "wavelengths_um": ctx.sim["wavelengths_um"]}))
    l1_transfers = r1b.result["transfers"]
    common = set(orch_transfers) & set(l1_transfers)
    if common:
        # L1 原语为传输将传递谱四舍五入到 6 位小数；orchestrator 保留全精度。
        # 二者为同一物理量，比较时统一到 6 位小数精度（位级一致）。
        diff = max(abs(round(max(orch_transfers[k]), 6) - max(l1_transfers[k]))
                   for k in common)
        checks.append(("orchestrator 与 L1 link_simulate 一致（6dp 误差<1e-9）",
                       diff < 1e-9))
    else:
        checks.append(("orchestrator 与 L1 link_simulate 一致（6dp 误差<1e-9）", False))

    # --- 4) 确定性 ---
    ctx2 = _run_orchestrator(tempfile.mkdtemp(prefix="lda_m3_b_"))
    det = (json.dumps(ctx.verification, sort_keys=True)
           == json.dumps(ctx2.verification, sort_keys=True))
    checks.append(("确定性：两次 verification 一致", det))

    # --- 汇总 ---
    passed = sum(1 for _, ok in checks if ok)
    print("=" * 60)
    print("P1-M3 Agent 元编排 + L1 原语 验证")
    print("=" * 60)
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print("-" * 60)
    print(f"  合计 {passed}/{len(checks)}")
    print(f"  GDS 字节数: {len(ctx.gds_bytes)}")
    print(f"  net 总损耗: {sum(ctx.net_loss_db.values()):.4f} dB")
    print(f"  系统指标样例: {list(ctx.verification['system_metrics'].items())[:2]}")
    print("=" * 60)
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
