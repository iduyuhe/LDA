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

    **语义（v0.8.11 修正）**：engine.simulate 的 transfers 是**功率谱**
    （器件响应直接给功率，如 MZI cos²/sin²、ring thru/drop 功率谱、
    wg 透射 1），不是场幅度——能量守恒在功率域直接求和，
    **不得再平方**（旧版对功率再平方导致泄漏失真，如无损 MZI 网络
    报泄漏 0.5）。

    返回每源的最大「功率泄漏」= 1 - Σ_sink T_src→sink（按波长取最坏）。
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
            p = sum(vec[k] for vec in sinks.values())  # 功率域直接求和（transfers 已是功率）
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


def link_cascade_check(link, sim: Dict[str, Any],
                       tol: float = 1e-6,
                       net_loss_db: Optional[Dict[str, float]] = None
                       ) -> Dict[str, Any]:
    """链路级联乘法性死标量锚（芯片级验收数值锚）。

    对 WDM 前馈链（bus 串联 add-drop 环），信号流图级联有解析闭式：
        T(bus_in → ring_i.drop) = T_drop(ring_i) · Π_{j<i} T_thru(ring_j)
    用引擎同源 adddrop_spectrum 模型逐波长重建解析期望，与 engine.simulate
    的 transfers 逐波长死标量比对（rel ≤ tol PASS）。这验证「级联引擎算得
    对」（数值正确性），与 B19（无源界，物理合法性）互为补充。

    LLM 不进判决路径：期望与实测均为确定性计算，PASS/FAIL 由死标量 rel 决定。

    返回 {passed, checked_pairs, max_rel, detail[{src->sink, rel}], honest_note}
    """
    from lda_agent.ring_adddrop import (adddrop_spectrum,
                                        bending_loss_db_per_cm, gap_to_kappa)
    from lda_chain.registry import _ring_response  # noqa: F401（复用于期望重建）

    transfers = sim.get("transfers", {})
    wls = sim.get("wavelengths_um", [])
    if not wls:
        return {"passed": False, "max_rel": None, "detail": [],
                "honest_note": "无波长网格，无法做级联比对"}
    lp = getattr(link, "link_params", {}) or {}
    gap = lp.get("gap", 0.3)

    # 依拓扑顺序排列的环（bus 串行链：按 IR 添加序）
    rings = [c for c in link.ir.components if c.kind == "RingResonator"]
    if not rings:
        return {"passed": True, "checked_pairs": 0, "max_rel": 0.0,
                "detail": [], "honest_note": "无环形器件，级联锚不适用（trivially ok）"}

    # 解析期望：逐环算 drop/thru，级联累积。
    # 引擎视角：单个 bus 源（bus0.in）传播到各环 drop 端 → transfers key =
    # "bus0.in->ring_i.drop"。解析闭式 T(bus0.in→ring_i.drop) =
    # T_drop(ring_i)·Π_{j<i} T_thru(ring_j)，按 IR 添加序（bus 串行链）重建。
    # 注：component.params['R'] 单位 mm（与 registry._ring_response 同源）；gap 单位 um
    src_id = None
    for k in transfers:
        src_inst = str(k).split("->")[0].split(".")[0]
        if src_inst not in {c.id for c in rings}:
            src_id = src_inst
            break
    if src_id is None and transfers:
        src_id = str(next(iter(transfers))).split("->")[0].split(".")[0]
    src_id = src_id or "bus0"

    # net 段损耗（与引擎 simulate 同源：net_loss_db 逐 net dB）
    net_loss_db = net_loss_db or sim.get("net_loss_db") or {}
    def _net_gain(net_id: str) -> float:
        return 10.0 ** (-net_loss_db.get(net_id, 0.0) / 10.0)

    # bus 串行链：net 按连接序命名（bus0/bus1/...）；每段损耗乘入级联。
    # 逐环 drop 期望 = T_drop(ring_i)·Π_{j<i}[T_thru(ring_j)·g_bus_j]
    # 引擎视角 net 名 = f"bus{j}"（WDM bus 段），缺失则 g=1（理想互连，仍同模型）。
    cum_thru = [1.0] * len(wls)
    expected: Dict[str, List[float]] = {}
    ring_names = []
    for j, comp in enumerate(rings):
        R_mm = float(comp.params["R"])
        n_g = float(comp.params.get("n_g", 4.2))
        kappa = gap_to_kappa(gap)
        alpha_bend = bending_loss_db_per_cm(R_mm)
        sp = adddrop_spectrum(wls, R_mm, n_g, kappa, alpha_bend, 1.55)
        g_bus = _net_gain(f"bus{j}")
        drop = [cum_thru[i] * sp["drop"][i] for i in range(len(wls))]
        expected[f"{src_id}.in->{comp.id}.drop"] = drop
        # 下一段：thru(ring_j) 之后再乘 bus_j 段损耗
        cum_thru = [cum_thru[i] * sp["thru"][i] * g_bus
                    for i in range(len(wls))]
        ring_names.append(comp.id)

    # 与引擎 transfers 比对
    detail = []
    max_rel = 0.0
    checked = 0
    for key, exp in expected.items():
        act = transfers.get(key)
        if act is None:
            detail.append({"src->sink": key, "found": False, "rel": None})
            continue
        rel = 0.0
        for i in range(len(wls)):
            denom = abs(exp[i]) + 1e-12
            r = abs(act[i] - exp[i]) / denom
            if r > rel:
                rel = r
        checked += 1
        max_rel = max(max_rel, rel)
        detail.append({"src->sink": key, "found": True,
                       "rel": round(rel, 8)})
    passed = bool(checked > 0 and max_rel <= tol)
    return {
        "passed": passed,
        "checked_pairs": checked,
        "max_rel": round(max_rel, 8),
        "tol": tol,
        "rings": ring_names,
        "detail": detail,
        "honest_note": ("级联乘法性锚：解析闭式 T(drop_i)=T_drop(i)·Π_{j<i}T_thru(j) "
                        "vs 引擎 transfers 死标量比对；LLM 不进判决路径。"),
    }
