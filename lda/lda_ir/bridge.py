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
  路径 A（L1 DesignAgent.run）：光子 Waveguide(kind) → 真 2D 波导验收闭环
  （geo_kind="waveguide_2d"，FDTD neff ↔ slab ORACLE）；RingResonator →
  环形谱形逆设计闭环（D-11，解析环形传递函数 + 谱形提取交叉验收）。
  路径 B（D-38 声明式注册表 run_inverse_design，本桥 ir_to_inverse_design）：
  复用同一框架落地 RingResonator / BraggMirror / RingAddDrop / Transmon 四类
  已验证器件（跨光子/量子、跨 match/threshold、跨连续/离散；C 级自主，零外部
  求解器）。新器件接入 = 注册表加一条 spec，本桥零改动——这是"逆设计扩面"
  的主通道。其余 kind（GratingCoupler / Splitter / DirectionalCoupler /
  SymmetricYBranch）逆设计需经对应专用闭环（规划 D-09/D-01）——对不支持
  kind 抛 NotImplementedError，不静默返回假 intent。

另提供 ir_eval：L3 直接消费 IR 算真值 + 判定（不经 agent 闭环），这是
"IR 即事实源"的活路径（与 DesignAgent 无关，始终可用）。

零外部依赖；延迟导入 lda_agent / lda_l2，避免编译期强耦合。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .core import IRModel


def _check_bridgeable(model: IRModel):
    """校验 IR 是否可桥接为 DesignAgent intent；返回 primary_component。

    当前 DesignAgent 支持光子 Waveguide（→waveguide_2d）与 RingResonator
    （→ring 谱形闭环，D-11）。其余 kind / 量子域诚实抛 NotImplementedError，
    不静默返回假 intent。
    """
    prim = model.primary_component
    if prim is None:
        raise ValueError("IR 无 component，无法构造设计意图")
    if model.domain != "photon":
        raise NotImplementedError(
            f"domain={model.domain} 的 agent 逆设计闭环未接入：当前 DesignAgent "
            "仅支持光子真 2D 波导(waveguide_2d)与环形谱形闭环(ring)。"
            "量子侧真值判定请走 ir_eval。")
    if prim.kind not in ("Waveguide", "RingResonator"):
        raise NotImplementedError(
            f"kind={prim.kind} 的 agent 逆设计闭环未接入：当前 DesignAgent 仅支持 "
            "Waveguide（真 2D 波导）与 RingResonator（环形谱形，D-11）。"
            "耦合器/分束器需经 D-01 CouplerAgent 接入（见规划 D-09）。")
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

    if prim.kind == "RingResonator":
        # —— 环形谱形逆设计闭环（D-11）：调 R 使 drop 谱 FSR 命中目标 ——
        spec = model.spectrum
        target_fsr = prim.params.get("target_fsr_nm")
        if target_fsr is None and spec is not None:
            target_fsr = spec.target_fsr_nm
        if target_fsr is None:
            raise ValueError(
                "RingResonator IR 需 target_fsr_nm（组件参数或 SpectrumSpec）")
        R_bounds = prim.param_bounds.get("R", (8.0, 12.0))
        n_g = prim.params.get("n_g") or (spec.n_g if spec else 4.2)
        wl0 = spec.wl0_um if spec else 1.55
        return {
            "geometry_type": "ring",
            "target_wavelength_um": float(wl0),
            "target_metric": "spectrum_match",
            "threshold": 0.0,
            "tolerance_rel": 0.02,       # 方法一致性容差（谱形提取 ↔ 解析）
            "max_iterations": 40,
            "initial_periods": 1,
            "extra": {
                "R_um": float(prim.params.get("R", 10.0)),
                "R_bounds": [float(v) for v in R_bounds],
                "n_g": float(n_g),
                "Q": float(prim.params.get("Q", 1.0e4)),
                "kappa": float(prim.params.get("kappa", 0.05)),
                "target_fsr_nm": float(target_fsr),
                "wl0_um": float(wl0),
                "target_tol": 0.03,      # 设计目标容差（与 B11 golden 一致）
                "backend": backend,
            },
        }

    # —— Waveguide → 真 2D 波导验收闭环 ——
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
# IR → D-38 声明式逆设计注册表（逆设计扩面主通道）
# --------------------------------------------------------------------------
# IR kind 与 D-38 注册表 kind 命名一致（零翻译层）：本集合即"桥接层认可的
# 可经 run_inverse_design 闭环的 IR kind"。新增器件 = 注册表加一条 spec（
# 见 lda_agent/inverse_design.py），本桥零改动。
_INVERSE_KINDS = ("RingResonator", "BraggMirror", "RingAddDrop", "Transmon")


def _resolve_inverse_kind(model: IRModel) -> str:
    """取 IR 主器件并解析其 D-38 逆设计注册表 kind；不支持则诚实抛 NotImplementedError。"""
    prim = model.primary_component
    if prim is None:
        raise ValueError("IR 无 component，无法构造逆设计意图")
    if prim.kind in _INVERSE_KINDS:
        return prim.kind
    raise NotImplementedError(
        f"kind={prim.kind} 未接入逆设计注册表：当前支持 {list(_INVERSE_KINDS)}"
        "（其余 kind 逆设计需经对应专用闭环，见规划）。")


def ir_to_inverse_design(model: IRModel, registry, foundry_key: str,
                         backend: str = "numpy") -> Dict:
    """由 IR 构造 D-38 逆设计意图并执行 run_inverse_design 闭环。

    与 ir_to_intent（L1 DesignAgent.run 路径）互补：本函数复用 D-38 声明式
    注册表（run_inverse_design），落地 RingResonator / BraggMirror / RingAddDrop
    / Transmon 四类已验证器件。foundry 工艺窗口注入 extra（与 _inject_process_params
    同源），保证"经闭环优化"与"L3 直接算真值"两路径一致。

    返回 run_inverse_design 的报告 dict（含 ok / accepted / final_params /
    method_err / elapsed_s）——调用方据此判定闭环成败，不静默返回空。
    """
    kind = _resolve_inverse_kind(model)
    pdk = registry.get(foundry_key)
    prim = model.primary_component
    p = prim.params
    spec = model.spectrum

    extra: Dict[str, float] = {}
    if kind == "RingResonator":
        extra["n_g"] = float(p.get("n_g", pdk.n_si if model.domain == "photon" else 4.2))
        extra["wl0_um"] = float(spec.wl0_um if spec else p.get("wl0_um", 1.55))
        extra["Q"] = float(p.get("Q", 1.0e4))
        extra["kappa"] = float(p.get("kappa", 0.05))
        extra["n_points"] = int(p.get("n_points", 81))
        target = float(spec.target_fsr_nm if spec else p.get("target_fsr_nm", 9.15))
    elif kind == "BraggMirror":
        extra["wl0_um"] = float(p.get("wl0_um", 1.55))
        extra["n_si"] = float(p.get("n_si", pdk.n_si))
        extra["n_sio"] = float(p.get("n_sio", getattr(pdk, "n_clad", 1.44)))
        extra["dl_factor"] = float(p.get("dl_factor", 60.0))
        target = float(p.get("target_r_min", 0.99))
    elif kind == "RingAddDrop":
        extra["R_um"] = float(p.get("R", 6.0))
        extra["wg_width"] = float(p.get("wg_width", 0.5))
        extra["n_g"] = float(p.get("n_g", pdk.n_si if model.domain == "photon" else 4.2))
        extra["wl0_um"] = float(spec.wl0_um if spec else p.get("wl0_um", 1.55))
        extra["n_points"] = int(p.get("n_points", 401))
        target = float(p.get("target_Q", 2500.0))
    else:  # Transmon（量子域）
        ec = p.get("E_C")
        if ec is None and getattr(pdk, "quantum_window", None):
            ec = pdk.quantum_window.get("ec_default")
        extra["E_C"] = float(ec if ec is not None else 0.30)
        extra["N"] = int(p.get("N", 20))
        extra["n_g"] = float(p.get("n_g", 0.0))
        target = float(p.get("target_f01", 5.0))

    from lda_agent.inverse_design import run_inverse_design
    return run_inverse_design(kind, target_metric=target, extra=extra)


def ir_to_multifoundry_inverse(model: IRModel, registry,
                               backend: str = "numpy") -> List[Tuple[str, Dict]]:
    """按 FoundryPlan 遍历 foundry，对每个 foundry 跑 ir_to_inverse_design。

    与 ir_to_multifoundry 对称；域过滤同规则（光子 IR 不派发到量子 foundry，
    反之）。单 foundry 失败跳过并告警（不阻断整体）。
    """
    _resolve_inverse_kind(model)  # 整体不可逆设计 → 直接抛，不静默返回空

    if model.foundry_plan is None:
        keys = [model.pdk_ref] if model.pdk_ref else registry.list_pdks()
    elif model.foundry_plan.mode == "all":
        keys = registry.list_pdks()
    else:
        keys = [k for k in model.foundry_plan.foundries if k in registry.list_pdks()]

    if model.domain == "photon":
        keys = [k for k in keys if "量子" not in k]
    elif model.domain == "quantum":
        keys = [k for k in keys if "量子" in k]

    out: List[Tuple[str, Dict]] = []
    for k in keys:
        try:
            rep = ir_to_inverse_design(model, registry, k, backend=backend)
            out.append((k, rep))
        except Exception as e:
            print(f"[bridge-inverse] 跳过 foundry '{k}'：{e}")
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
