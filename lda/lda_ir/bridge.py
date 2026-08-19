"""LDA L0 → L2/L1/agent 桥接层。

把"机器优先的 IR"翻译为现有 agent 设计闭环可消费的 DesignProblem，并经 L1
KernelGateway 驱动 L3 内核真算——这正是《白皮书》人机协作哲学的落地：IR 是
人/agent 写出的"设计意图机器语言"，桥接层把它适配成"agent 操作接口"
（确定性、批处理、可验证、无交互）。

两个入口：
  - ir_to_design_problem(model, registry, foundry_key)
        ：单 foundry 逆设计。foundry 的工艺窗口（n_si 等）注入 base_params，
          IR 的 spectrum → B11 objective，objectives → 加权 objective，
          param_bounds → tunables。
  - ir_to_multifoundry(model, registry)
        ：按 FoundryPlan 遍历 foundry 生成多个 DesignProblem，天然表达
          "同一设计意图落在不同工艺窗口 → 不同收敛落点"（多晶圆厂共建闭环）。

零外部依赖；延迟导入 lda_agent / lda_l2，避免编译期强耦合。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .core import IRModel, SpectrumSpec


def _spectrum_to_objective(spec: SpectrumSpec) -> Dict:
    """目标谱形 → 单目标 objective（bid=B11, target=0, tol=0.03）。

    零耦合 harness：误差公式由 SpectrumSpec.metric 自身给出，与
    lda_harness.golden.b11_ring_spectrum_match 同式，bridge 只负责把
    spectrum 翻译成"让 B11 误差趋近 0"的目标。
    """
    return {"bid": "B11", "weight": 1.0, "target": 0.0, "tol": 0.03}


def ir_to_design_problem(model: IRModel, registry, foundry_key: str,
                         solver: str = "truth") -> "object":
    """由 IR + 指定 foundry 构造一个 DesignProblem（驱动单 foundry 逆设计）。

    registry 为 lda_l2.pdk.PDKRegistry 实例；foundry_key 形如 "NOEIC(演示近似)::SOI 180nm"。
    """
    from lda_agent.design_loop import DesignProblem

    pdk = registry.get(foundry_key)
    prim = model.primary_component
    if prim is None:
        raise ValueError("IR 无 component，无法构造设计问题")

    # 工艺窗口注入：仅光子域有意义——foundry 的 n_si 作为 n_g 近似（与现有
    # pdk_examples B11 模板一致）。折射率是工艺参数，由 foundry 决定，故光子域
    # 强制用 foundry.n_si（覆盖 IR 占位），与量子 E_C 工艺固定对称：设计者只
    # 调几何。量子域（transmon 频率由 E_J/E_C 决定）不注入 n_g。
    base_params: Dict[str, float] = dict(prim.params)
    if model.domain == "photon":
        base_params["n_g"] = pdk.n_si

    # 量子工艺窗口注入：transmon 的 E_C 是**工艺参数**（由代工结型/氧化层决定），
    # 设计者只调 E_J（结面积）命中频率——与光子"n_si 由工艺决定、调几何 R"完全
    # 对称。因此无论 IR 是否显式给 E_C，均用 foundry 的 ec_default 强制固定 E_C
    # 并移除其可调，使"同一 f01 目标在不同量子厂收敛到不同 E_J 落点"的因果链
    # 完全由工艺窗口驱动（多晶圆厂共建的干净演示）。
    ec = None
    if model.domain == "quantum" and pdk.quantum_window:
        ec = pdk.quantum_window.get("ec_default")
    if ec is not None:
        base_params["E_C"] = ec

    # 可调参数区间
    tunables: Dict[str, Tuple[float, float]] = {k: tuple(v) for k, v in prim.param_bounds.items()}
    if model.domain == "quantum" and ec is not None and "E_C" in tunables:
        # E_C 由工艺固定 → 移除可调（只调 E_J）
        del tunables["E_C"]

    # 构造 objective 列表：spectrum → B11；外加 IR.objectives
    objective: List[Dict] = []
    bids: List[str] = []
    constraint_bids: List[str] = []
    if model.spectrum is not None:
        objective.append(_spectrum_to_objective(model.spectrum))
        bids.append("B11")
    for o in model.objectives:
        objective.append({"bid": o.bid, "weight": o.weight,
                          "target": o.target, "tol": o.tol})
        bids.append(o.bid)
        if o.role == "constraint":
            constraint_bids.append(o.bid)

    # 几何相关硬约束（环形必须有 B4 弯曲半径约束，保证可制造）
    if "RingResonator" in prim.kind and "B4" not in constraint_bids:
        constraint_bids.append("B4")
        if "B4" not in bids:
            bids.append("B4")

    if not objective:
        raise ValueError("IR 未指定任何 objective（spectrum 或 objectives 至少其一）")

    primary_bid = objective[0]["bid"]
    # 主目标 target/tol（DesignProblem 单目标兼容字段）
    primary_target = objective[0]["target"]
    primary_tol = objective[0]["tol"]

    # 梯度下降：谱形逆设计用有限差分梯度（数值伴随）
    use_gradient = model.spectrum is not None

    return DesignProblem(
        name=f"{model.name or prim.kind} @ {pdk.foundry}/{pdk.node}",
        bids=bids,
        objective_bid=primary_bid,
        target_metric="spectrum_match" if model.spectrum else "custom",
        target=primary_target,
        target_tol=primary_tol,
        base_params=base_params,
        tunables=tunables,
        decreasing=False,
        constraint_bids=constraint_bids,
        use_gradient=use_gradient,
        objective=objective,
        solver=solver,
    )


def ir_to_multifoundry(model: IRModel, registry,
                       solver: str = "truth") -> List[Tuple[str, "object"]]:
    """按 FoundryPlan 遍历 foundry，返回 [(foundry_key, DesignProblem), ...]。

    mode="all" → 注册表全部 foundry；mode="list" → 仅指定 foundry。量子 foundry
    没有匹配光子器件的工艺窗口也能跑（桥接只用 n_si/工艺窗口，逆设计仍收敛到
    几何落点），但若某 foundry 链构造失败则跳过并告警（不阻断其他 foundry）。
    """
    if model.foundry_plan is None:
        # 默认：若 IR 指定 pdk_ref 则单 foundry，否则全部
        keys = [model.pdk_ref] if model.pdk_ref else registry.list_pdks()
    elif model.foundry_plan.mode == "all":
        keys = registry.list_pdks()
    else:
        keys = [k for k in model.foundry_plan.foundries if k in registry.list_pdks()]

    # domain 匹配：光子 IR 不派发到量子 foundry（避免误用工艺窗口）
    if model.domain == "photon":
        keys = [k for k in keys if "量子" not in k]
    elif model.domain == "quantum":
        keys = [k for k in keys if "量子" in k]

    out: List[Tuple[str, "object"]] = []
    for k in keys:
        try:
            prob = ir_to_design_problem(model, registry, k, solver=solver)
            out.append((k, prob))
        except Exception as e:  # 单 foundry 失败不阻断整体多 foundry 对比
            print(f"[bridge] 跳过 foundry '{k}'：{e}")
    return out


# --------------------------------------------------------------------------
# L3 求解器直接消费 IR：把 IR 意图（谱形 / objective）翻译为"黄金参考真值
# 计算 + pass/fail 判定"，不经过 DesignProblem 手写中转——让 IR 成为唯一
# 事实源（技术复利：上层每次计算都从 IR 派生，而非另写一份目标描述）。
# --------------------------------------------------------------------------
def _inject_process_params(model: IRModel, foundry_key: str, registry) -> Dict[str, float]:
    """构造 IR 的完整候选参数：组件初始参数 + foundry 工艺窗口注入。

    与 ir_to_design_problem 共享同一套注入规则（光子 n_si、量子 E_C 工艺固定），
    保证"经 agent 闭环优化"与"L3 直接算真值"两路径完全同源。
    """
    pdk = registry.get(foundry_key)
    prim = model.primary_component
    params: Dict[str, float] = dict(prim.params)
    if model.domain == "photon":
        params["n_g"] = pdk.n_si       # 折射率工艺固定（与闭环路径一致）
    if model.domain == "quantum" and pdk.quantum_window:
        ec = pdk.quantum_window.get("ec_default")
        if ec is not None:
            params["E_C"] = ec          # 充电能工艺固定
    return params


def _bid_params(model: IRModel, params: Dict[str, float], bid: str) -> Dict[str, float]:
    """把 IR 全量参数裁剪为该 bid 黄金参考接受的键（与 DesignAgent._evaluate 同逻辑）。"""
    from lda_harness.benchmarks import BENCHMARK_DEFS
    d = BENCHMARK_DEFS.get(bid, {})
    p = dict(d.get("default_params", {}))
    for k, v in params.items():
        if k in p:
            p[k] = v
    return p


def ir_eval(model: IRModel, params: Dict[str, float],
            foundry_key: str = "", registry=None) -> Dict:
    """L3 直接消费 IR：给定 IR + 候选参数 → 算出各目标/约束题的真值与判定。

    返回 {bid: {candidate, golden, passed, tol, source}} + 顶层 passed_all。
    foundry_key 非空时先经工艺窗口注入（与闭环路径同源）；为空则直接用 params。

    这是"IR 即事实源"的落地：内核不再硬编码目标，而是读 IR 的 spectrum /
    objectives 直接算出物理真值并判定——验证裁判与逆设计共用同一份 IR 意图。
    """
    from lda_harness.golden import golden_with_source
    from lda_harness.benchmarks import BENCHMARK_DEFS

    if foundry_key and registry is not None:
        base = _inject_process_params(model, foundry_key, registry)
    else:
        base = dict(params)
    params = {**base, **params}

    bids = []
    if model.spectrum is not None:
        bids.append("B11")
    bids += [o.bid for o in model.objectives]

    rows = {}
    passed_all = True
    for bid in bids:
        p = _bid_params(model, params, bid)
        try:
            value, source, note = golden_with_source(bid, p)
        except Exception as e:
            rows[bid] = {"candidate": None, "golden": None, "passed": False,
                         "tol": None, "source": "error", "note": str(e)}
            passed_all = False
            continue
        tol = BENCHMARK_DEFS.get(bid, {}).get("tol")
        target = None
        if bid == "B11":
            target = 0.0  # B11 误差目标趋近 0
        else:
            obj = next((o for o in model.objectives if o.bid == bid), None)
            target = obj.target if obj else None
        passed = (tol is not None and target is not None
                  and abs(value - target) <= tol)
        passed_all = passed_all and passed
        rows[bid] = {"candidate": value, "golden": value, "passed": passed,
                     "tol": tol, "target": target, "source": source, "note": note}
    return {"rows": rows, "passed_all": passed_all,
            "params": params, "foundry": foundry_key or None}
