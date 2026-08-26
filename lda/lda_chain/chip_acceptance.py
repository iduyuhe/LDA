"""LDA 芯片级设计验收标准（chip acceptance · P1-M4 补强，任务 254）。

把「芯片设计成功」从口头承诺变成**死标量可判定**：任何链路/芯片设计结果
（来自 orchestrator / lda_chain 引擎）必须同时通过以下非 AI ground 判定
（LLM 不进判决路径，PASS/FAIL 由确定性计算决定）：

  A. B19 无源无增益界   —— max|T(λ)| ≤ 1 + tol（物理合法性：无源网络不可能放大）
  B. 级联乘法性         —— T(drop_i) = T_drop(i)·Π_{j<i}[T_thru(j)·g_bus(j)]
                          （数值正确性：级联引擎算得对，死标量 rel ≤ tol）
  C. 能量守恒诊断       —— 无损特例逐源功率闭合（1 − Σ|T|² ≈ 0，损耗合法 ≥0）
  D. 完整性             —— 无缺模型（所有器件 kind 有响应）+ 布线完整（无 blocked net）

判定规则：
  - 全 A-D 通过 → accepted=True（芯片设计验收通过）
  - 任一失败 → accepted=False + 失败锚明细（可追溯修复）

诚实边界：
  - 芯片级当前仅物理定律锚（A-D 全部确定性数值/解析）；缺系统级实证语料，
    不判 E 题（empirical_anchor=False）——与 harness 的 E 题纪律一致。
  - 验收标准针对「仿真级芯片设计闭环」；流片级（DRC/LVS/工艺角/实测回流）
    属发动期 PDK 对接后扩展（见 chip_acceptance 版本演进）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from lda_chain.link_harness import link_physics_harness, link_cascade_check


def _bool2(v: Any, default: bool = False) -> bool:
    """安全布尔（None → default；避免 0.0 falsy 陷阱）。"""
    if v is None:
        return default
    return bool(v)


def accept_chip(ctx: Any, tol_cascade: float = 1e-6,
                tol_passivity: float = 1e-9) -> Dict[str, Any]:
    """芯片级设计验收入口：对 orchestrator 产出的 DesignContext 跑全锚判定。

    参数
    ----
    ctx : DesignContext（含 link/sim/verification/net_loss_db/blocked_nets）
    tol_cascade / tol_passivity : 死标量容差（默认与 harness 一致）

    返回
    ----
    {
      "accepted": bool, "grounds": {...A-D...}, "blockers": [失败锚],
      "anchor": "physical_law_only", "empirical_anchor": False,
      "honest_note": ..., "report": "one-line summary",
    }
    """
    link = getattr(ctx, "link", None)
    sim = getattr(ctx, "sim", None)
    if link is None or sim is None:
        return {"accepted": False, "grounds": {},
                "blockers": ["ctx.link 或 ctx.sim 缺失（编排未完成）"],
                "anchor": "physical_law_only", "empirical_anchor": False,
                "honest_note": "验收前置：编排须先产出 link+sim",
                "report": "REJECT: 编排未完成"}

    # A+C+D：B19 物理锚 harness（无源界 + 能量守恒 + 完整性）
    blocked = list(getattr(ctx, "blocked_nets", None) or [])
    hp = link_physics_harness(link, sim, blocked)
    b19 = hp.get("b19", {})
    ec = hp.get("energy_conservation", {})
    a_passed = _bool2(b19.get("passed"))
    # C 锚语义：损耗合法（泄漏≥0），增益非法（泄漏<0）。无损特例 lossless_ok=True
    # 是「理想诊断」，不是验收硬约束；有损耗链路的泄漏>0 属物理合法，不判 FAIL。
    leak_vals = list((ec.get("per_source_leak") or {}).values())
    c_passed = bool(leak_vals) and all(v >= -1e-9 for v in leak_vals)
    d_passed = _bool2(hp.get("no_missing_models")) and _bool2(hp.get("routing_complete"))

    # B：级联乘法性数值锚
    cc = link_cascade_check(link, sim, tol=tol_cascade,
                            net_loss_db=getattr(ctx, "net_loss_db", None))
    b_passed = _bool2(cc.get("passed"))
    b_rel = cc.get("max_rel")

    grounds = {
        "A_b19_passivity": {
            "passed": a_passed,
            "metric": "max|T(λ)|",
            "value": b19.get("candidate"),
            "golden": b19.get("golden"),
            "tol": tol_passivity,
            "cmp": "le",
            "oracle": "无源网络无增益上界（B19 物理定律锚）",
        },
        "B_cascade_multiplicativity": {
            "passed": b_passed,
            "metric": "max_rel vs 解析级联闭式",
            "value": b_rel,
            "tol": tol_cascade,
            "oracle": "T(drop_i)=T_drop(i)·Π_{j<i}[T_thru(j)·g_bus(j)]",
            "checked_pairs": cc.get("checked_pairs"),
        },
        "C_energy_conservation": {
            "passed": c_passed,
            "metric": "逐源最大功率泄漏（≥0 合法损耗；<0 增益非法）",
            "value": ec.get("per_source_leak"),
            "oracle": "能量守恒：泄漏 ≥ 0（损耗合法）；<0 表示增益判 FAIL；"
                      "无损特例 Σ|T|²=1",
            "lossless_diagnostic": ec.get("lossless_ok"),
        },
        "D_completeness": {
            "passed": d_passed,
            "metric": "无缺模型 + 布线完整",
            "value": {"missing": sim.get("missing_models", []),
                      "blocked": blocked},
            "oracle": "全器件 kind 有响应 + 全 net 布线成功",
        },
    }

    blockers = [k for k, g in grounds.items() if not g["passed"]]
    accepted = not blockers
    summary = ("ACCEPT" if accepted else "REJECT")
    report = (f"{summary} [{', '.join(g for g in grounds if grounds[g]['passed'])}"
              + (f" | BLOCKED: {', '.join(blockers)}" if blockers else "") + "]")
    return {
        "accepted": accepted,
        "grounds": grounds,
        "blockers": blockers,
        "anchor": "physical_law_only",
        "empirical_anchor": False,
        "honest_note": ("芯片级验收 = 物理定律锚（B19 无源界 + 级联乘法性 + 能量守恒"
                        " + 完整性），全部确定性死标量判定；LLM 不进判决路径。"
                        "缺系统级实证语料，不判 E 题。"),
        "report": report,
    }


def accept_from_dict(link, sim, net_loss_db: Optional[Dict[str, float]] = None,
                     blocked: Optional[List[str]] = None,
                     tol_cascade: float = 1e-6,
                     tol_passivity: float = 1e-9) -> Dict[str, Any]:
    """从（link, sim, ...）元组验收（不依赖 DesignContext 的轻量入口）。"""
    class _Ctx:  # 最小鸭子类型容器
        pass
    c = _Ctx()
    c.link = link
    c.sim = sim
    c.net_loss_db = net_loss_db or {}
    c.blocked_nets = blocked or []
    return accept_chip(c, tol_cascade=tol_cascade, tol_passivity=tol_passivity)
