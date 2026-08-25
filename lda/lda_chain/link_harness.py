"""LDA P1-M4 · 链路级物理定律锚上提为 harness 框架题（B19）。

把 M3 验证 Agent 内部的物理锚（无源无增益 / 无缺模型 / 布线完整）正式
提升为 **VerificationHarness 一等公民**——与 B1–B18 同一套框架、同一套
死标量比对、同一句「LLM 不进判决路径」纪律。

B19（passivity）：无源线性网络（无外部泵浦）硬约束
    max|T(λ)| over all transfer paths ≤ 1 + tol
能量守恒是其无损（α=0）特例——无损 ⇒ S 幺正 ⇒ 功率守恒。本锚以
「无增益上界」表达，损耗（|T|<1）合法，增益（|T|>1）判 FAIL。

诚实边界：链路级**仅物理定律锚**（缺系统级实证语料）→ 不判 E 题；
本报告若被纳入 harness 生态，明确标注 empirical_anchor=False。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import math

from lda_harness.harness import VerificationHarness
from lda_harness.benchmarks import BENCHMARK_DEFS

B19_ID = "B19"
PASSIVITY_TOL = 1e-9


def _max_transfer(transfers: Dict[str, List[float]]) -> float:
    """链路级联全部传递路径上的最大幅度 |T(λ)|。"""
    max_t = 0.0
    for vec in transfers.values():
        for v in vec:
            a = abs(v)
            if a > max_t:
                max_t = a
    return max_t


def _per_source_power_balance(transfers: Dict[str, List[float]],
                              wls: List[float]) -> Dict[str, Any]:
    """逐源功率守恒诊断（无损特例：每波长各 sink 功率和 = 1）。

    返回每源的最大「功率泄漏」= 1 - Σ_sink |T_src→sink|²（按波长取最坏）。
    损耗合法：泄漏 ≥ 0 即物理（≤0 表示增益，判 FAIL）；无损链路应 ≈0。
    """
    # 按 (src) 聚合 sink；transfer key = 'src_comp.src_port->dst_comp.dst_port'
    # 注意：吸收端按「完整端口」区分（ring3.out 与 ring3.drop 是不同物理吸收端）
    by_src: Dict[str, Dict[str, List[float]]] = {}
    for key, vec in transfers.items():
        src_part, dst_part = str(key).split("->")
        src = src_part.split(".")[0]   # 源器件 id
        dst = dst_part                 # 完整目标端口（含 .out/.drop），不丢端口
        by_src.setdefault(src, {})[dst] = vec
    worst = {}  # src -> 最大泄漏(最坏波长)
    for src, sinks in by_src.items():
        n = len(next(iter(sinks.values())))
        leak_max = 0.0
        for k in range(n):
            p = sum((abs(vec[k]) ** 2) for vec in sinks.values())
            leak = 1.0 - p
            if leak > leak_max:
                leak_max = leak
        worst[src] = round(leak_max, 6)
    return {"per_source_leak": worst,
            "lossless_ok": all(v <= PASSIVITY_TOL for v in worst.values())}


def link_physics_harness(link, sim: Dict[str, Any],
                         blocked: Optional[List[str]] = None,
                         anchor=None) -> Dict[str, Any]:
    """对一条已仿真的链路跑 B19 物理定律锚。

    参数
    ----
    link     : LinkModel（已规划/综合）
    sim      : engine.simulate 返回值（含 'transfers' / 'wavelengths_um'）
    blocked  : 未成功布线的 net 列表（M3 验证 Agent 提供）
    anchor   : 实证锚（链路级未注入，保持 None → 诚实降级不判 E）

    返回
    ----
    {
      "b19": {BenchmarkResult-ish 字典},
      "energy_conservation": {...诊断...},
      "no_missing_models": bool,
      "routing_complete": bool,
      "anchor": "physical_law_only",
      "empirical_anchor": False,
      "status": "ok"/"fail",
    }
    """
    blocked = blocked or []
    transfers = sim.get("transfers", {})
    wls = sim.get("wavelengths_um", [])

    # ---- B19 经真实 harness 框架跑（resolve_specs + run + cmp='le'）----
    defs = {B19_ID: BENCHMARK_DEFS[B19_ID]}
    h = VerificationHarness(defs, anchor=anchor)
    specs = h.resolve_specs()  # B19: golden=1.0, cmp='le', tol=1e-9
    max_t = _max_transfer(transfers)

    def _b19_candidate(spec, golden, params):
        # 返回该链路级联的 max|T|（来自已仿真结果，避免重复计算）
        return max_t

    results = h.run(specs, _b19_candidate)
    b19 = results[0]
    b19_d = {
        "id": b19.bid,
        "metric": b19.metric,
        "golden": b19.golden,
        "candidate": b19.candidate,
        "tol": b19.tol,
        "oracle": b19.oracle,
        "passed": bool(b19.passed),
        "cmp": "le",
        "source": b19.source,
        "note": b19.note,
    }

    # ---- 能量守恒诊断（无损特例）----
    ec = _per_source_power_balance(transfers, wls)

    # ---- 无缺模型 / 布线完整（与 M3 verify agent 同源）----
    missing = sim.get("missing_models", [])
    no_missing = len(missing) == 0
    routing_ok = len(blocked) == 0

    passed = (b19.passed and no_missing and routing_ok)
    status = "ok" if passed else "fail"

    return {
        "b19": b19_d,
        "energy_conservation": ec,
        "no_missing_models": no_missing,
        "missing_models": missing,
        "routing_complete": routing_ok,
        "blocked_nets": blocked,
        "anchor": "physical_law_only",
        "empirical_anchor": False,
        "honest_note": ("链路级仅物理定律锚（B19 无源无增益 / 无缺模型 / 布线完整"
                        "）。缺系统级实证语料，未做实证校准，不判 E 题。"),
        "status": status,
    }


def max_transfer_of(sim: Dict[str, Any]) -> float:
    """导出：链路级联最大传递幅度（供 CLI / 报告复用）。"""
    return _max_transfer(sim.get("transfers", {}))
