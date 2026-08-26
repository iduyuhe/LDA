"""LDA P1-M3 · 验证 Agent（verify）。

链路级双 ground 的「第一道」——物理定律锚：
  - 无源线性网络 ⇒ 所有传递增益 |T(λ)| ≤ 1 + tol（不允许增益，损耗合法）
  - 无缺模型器件（所有实例均有 registry / 合成传递模型）
  - 无 blocked net（布线完整）

仿真由 lda_chain.engine.simulate 驱动（注入 net 损耗），与 M1/M2 同构。
诚实边界：链路级**无实证锚**（缺系统级语料），仅物理定律锚，报告标注
「无实证校准」——绝不编造 E 题（LLM 不进判决路径）。

产出：ctx.sim / ctx.verification。
"""
from __future__ import annotations

from typing import Any, Dict, List

import math

from .agents import AgentMsg, BaseAgent, DesignContext
from lda_chain import engine
from lda_chain.link_harness import link_physics_harness, link_cascade_check


PASSIVITY_TOL = 1e-9  # |T| 允许上限 = 1 + tol（数值浮点余量）


class VerificationAgent(BaseAgent):
    NAME = "verify"
    ACTIONS = ["verify"]

    def _run(self, msg: AgentMsg, ctx: DesignContext) -> Dict[str, Any]:
        if ctx.link is None:
            raise RuntimeError("链路规划未执行：ctx.link 为空")
        p = msg.payload
        wls = p.get("wavelengths_um") or _wls_from_link(ctx.link)
        sim = engine.simulate(ctx.link, wls, net_loss_db=ctx.net_loss_db or None)
        ctx.sim = sim

        checks = []

        # 1) 无源网络无增益（物理定律锚）
        max_gain = 0.0
        worst_key = ""
        for k, vec in sim["transfers"].items():
            peak = max((abs(v) for v in vec), default=0.0)
            if peak > max_gain:
                max_gain = peak
                worst_key = k
        no_gain = max_gain <= 1.0 + PASSIVITY_TOL
        checks.append({
            "name": "passivity_no_gain",
            "metric": "max|T(λ)| over all transfers",
            "value": round(max_gain, 6),
            "tol": 1.0 + PASSIVITY_TOL,
            "passed": bool(no_gain),
            "oracle": "无源线性网络：无外部泵浦 ⇒ |T|≤1",
            "worst": worst_key,
        })

        # 2) 无缺模型器件
        missing = sim.get("missing_models", [])
        checks.append({
            "name": "no_missing_models",
            "metric": "缺传递模型器件数",
            "value": len(missing),
            "tol": 0,
            "passed": len(missing) == 0,
            "oracle": "所有实例须有 registry/合成传递模型",
            "missing": missing,
        })

        # 3) 布线完整（无 blocked net）
        blocked = ctx.blocked_nets or []
        checks.append({
            "name": "routing_complete",
            "metric": "未布线（blocked）net 数",
            "value": len(blocked),
            "tol": 0,
            "passed": len(blocked) == 0,
            "oracle": "所有 net 须成功自动布线",
            "blocked": blocked,
        })

        # 4) 链路级系统指标（从 transfers 直算，规避 wdm_system 串扰索引 bug）
        sys_metrics = _system_metrics(sim["transfers"])

        # 5) 物理定律锚上提为 harness B19（P1-M4）：经真实 VerificationHarness 跑
        harness_res = link_physics_harness(ctx.link, sim, ctx.blocked_nets)
        # 5b) 级联乘法性死标量锚（芯片级验收数值锚，P1-M4 补强）：
        #     解析闭式 T(drop_i)=T_drop(i)·Π_{j<i}T_thru(j)·g_bus(j) vs 引擎
        #     transfers 逐波长比对（计入同源 net 段损耗）
        cascade = link_cascade_check(ctx.link, sim, net_loss_db=ctx.net_loss_db or None)

        passed = sum(1 for c in checks if c["passed"])
        status = ("ok" if (passed == len(checks) and harness_res["status"] == "ok"
                           and cascade["passed"]) else "fail")
        verification = {
            "status": status,
            "passed": passed,
            "total": len(checks),
            "checks": checks,
            "system_metrics": sys_metrics,
            # P1-M4：链路级物理定律锚上提为 harness B 类题（B19）
            "b19_harness": harness_res["b19"],
            "energy_conservation": harness_res["energy_conservation"],
            "no_missing_models": harness_res["no_missing_models"],
            "routing_complete": harness_res["routing_complete"],
            # P1-M4 补强：级联乘法性死标量锚（数值正确性，与 B19 物理合法性互补）
            "cascade_check": cascade,
            "anchor": "physical_law_only",
            "empirical_anchor": False,
            "honest_note": ("链路级物理定律锚（B19 无源无增益 / 无缺模型 / 布线完整"
                            "）+ 级联乘法性死标量锚。缺系统级实证语料，未做实证校准，"
                            "不判 E 题。"),
        }
        ctx.verification = verification
        ctx.append_step(self.NAME, msg.action,
                        f"链路验证：{passed}/{len(checks)} 物理锚 PASS"
                        + ("（含系统指标）" if sys_metrics else ""),
                        {"checks": checks, "system_metrics": sys_metrics})
        return verification


def _wls_from_link(link) -> List[float]:
    lp = link.link_params or {}
    wl0 = lp.get("wl0_um", 1.55)
    span = lp.get("span_um", 0.06)
    n = int(lp.get("n_samples", 61))
    return [wl0 - span / 2.0 + span * i / (n - 1) for i in range(n)]


def _system_metrics(transfers: Dict[str, List[float]]) -> Dict[str, Any]:
    """从级联传递谱直算系统指标（不依赖 wdm_system 的索引逻辑）。"""
    if not transfers:
        return {}
    out = {}
    for key, vec in transfers.items():
        peak = max((abs(v) for v in vec), default=0.0)
        # |T| 已是场幅，功率 = |T|^2；IL(dB) = -10 log10(power)
        power = peak ** 2
        il_db = -10.0 * math.log10(max(power, 1e-30))
        out[key] = {
            "peak_magnitude": round(peak, 6),
            "peak_power_db": round(il_db, 3),
            "n_wl": len(vec),
        }
    return out
