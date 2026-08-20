"""LDA L0 → L2/L1/agent 桥接层。

把"机器优先的 IR"翻译为现有 agent 设计闭环可消费的 **intent dict**
（DesignAgent.run 接口）。注：webui 修复时移除了 DesignProblem 抽象层，
DesignAgent 现只消费 dict 意图，故本层输出 intent dict 而非 DesignProblem。

两个入口：
  - ir_to_intent(model, registry, foundry_key)
        ：单 foundry 意图。foundry 的工艺窗口（n_si 等）注入 materials，
          设计意图（目标谱形/objective）翻译为 DesignAgent 可跑的目标。
  - ir_to_multifoundry(model, registry)
        ：按 FoundryPlan 遍历 foundry 生成多个 intent，天然表达
          "同一设计意图落在不同工艺窗口 → 不同收敛落点"（多晶圆厂共建闭环）。

当前 DesignAgent 能力边界（诚实声明）：
  仅支持光子 Waveguide(kind) → 真 2D 波导验收闭环（geo_kind="waveguide_2d"，
  FDTD neff ↔ slab ORACLE）。环形谱形 / 耦合器 / 量子逆设计需经
  D-03 BandDesignAgent / D-01 CouplerAgent 专用闭环接入（规划 D-09）——
  对不支持 kind 抛 NotImplementedError，不静默返回假 intent。

另提供 ir_eval：L3 直接消费 IR 算真值 + 判定（不经 agent 闭环），这是
"IR 即事实源"的活路径（与 DesignAgent 无关，始终可用）。

零外部依赖；延迟导入 lda_agent / lda_l2，避免编译期强耦合。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .core import IRModel


def _check_bridgeable(model: IRModel):
    """校验 IR 是否可桥接为 DesignAgent intent；返回 primary_component。

    当前 DesignAgent 仅支持光子真 2D 波导（Waveguide → waveguide_2d）。
    其余 kind / 量子域诚实抛 NotImplementedError，不静默返回假 intent。
    """
    prim = model.primary_component
    if prim is None:
        raise ValueError("IR 无 component，无法构造设计意图")
    if model.domain != "photon":
        raise NotImplementedError(
            f"domain={model.domain} 的 agent 逆设计闭环未接入：当前 DesignAgent "
            "仅支持光子真 2D 波导(waveguide_2d)。量子侧真值判定请走 ir_eval。")
    if prim.kind != "Waveguide":
        raise NotImplementedError(
            f"kind={prim.kind} 的 agent 逆设计闭环未接入：当前 DesignAgent 仅支持 "
            "Waveguide（真 2D 波导）。RingResonator/耦合器/分束器谱形逆设计需经 "
            "D-03 BandDesignAgent / D-01 CouplerAgent 接入（见规划 D-09）。")
    return prim


def ir_to_intent(model: IRModel, registry, foundry_key: str,
                 backend: str = "numpy") -> Dict:
    """由 IR + 指定 foundry 构造一个 DesignAgent.run 可消费的 intent dict。

    registry 为 lda_l2.pdk.PDKRegistry 实例；foundry_key 形如
    "NOEIC(演示近似)::SOI 180nm"。foundry 的 n_si/n_clad 作为工艺窗口注入
    materials（与旧 DesignProblem 的 base_params 注入语义一致），设计变量
    width 经 extra 传入（waveguide_2d 的 DesignerAgent 读取）。
    """
    prim = _check_bridgeable(model)
    pdk = registry.get(foundry_key)

    wl0 = model.spectrum.wl0_um if model.spectrum else 1.55
    width = float(prim.params.get("width", 0.5))
    return {
        "geometry_type": "waveguide_2d",
        "materials": {"air": 1.0, "sih": pdk.n_si, "silo": pdk.n_clad},
        "target_wavelength_um": float(wl0),
        "target_metric": "neff",
        "threshold": 1.0,            # 波导验收以"与 slab ORACLE 一致"为准，无 R 阈值
        "tolerance_rel": 0.02,
        "max_iterations": 1,         # waveguide_2d 单次验证即判定（方法一致性）
        "initial_periods": 1,
        "extra": {
            "width_um": width,
            "core_ref": "sih",
            "clad_ref": "silo",
            "backend": backend,
        },
    }


def ir_to_multifoundry(model: IRModel, registry,
                       backend: str = "numpy") -> List[Tuple[str, Dict]]:
    """按 FoundryPlan 遍历 foundry，返回 [(foundry_key, intent), ...]。

    domain 过滤：光子 IR 不派发到量子 foundry（避免误用工艺窗口），量子 IR
    反之。kind 不支持时整体抛 NotImplementedError（非静默空列表）；单 foundry
    数据问题跳过并告警（不阻断其他 foundry）。
    """
    _check_bridgeable(model)  # 整体不可桥接 → 直接抛，不静默返回空

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

    out: List[Tuple[str, Dict]] = []
    for k in keys:
        try:
            intent = ir_to_intent(model, registry, k, backend=backend)
            out.append((k, intent))
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

    与 ir_to_intent 共享同一套注入规则（光子 n_si、量子 E_C 工艺固定），
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
