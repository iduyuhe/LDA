"""LDA L2 · 开放 PDK / 器件本体 Registry（参考实现，机器优先）。

L2 是架构分层里"社区共建"的一层：晶圆厂 / 代工厂把工艺节点（process node）
与器件模板（device template）登记到 Registry，agent 设计闭环从中取"真实
工艺窗口"（可调参数 bounds、固定工艺参数、目标规格），使逆设计落在可制造
边界内——而不是在真空里优化几何。

设计纪律（《白皮书》主权策略 B 级 / 双引擎资源策略）：
  - PDK 数据可来自公开近似（本示例 NOEIC SOI 180nm 用公开文献近似参数）；
  - 真实 NDA-PDK（Synopsys/Cadence 商业套件）属 A 级，永不借、只对接自主内核；
  - Registry 本体是我们自主的"对接点"，分发主权化（社区共建 + 自主托管）。

许可证：Apache-2.0 兼容，零外部依赖，离线可跑、主权可控。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# --------------------------------------------------------------------------
# 器件模板：把"工艺节点能造什么 + 设计目标"结构化
# --------------------------------------------------------------------------
@dataclass
class DeviceTemplate:
    """一个器件模板：描述某工艺节点下可调/固定参数与设计规格目标。

    derive_problem() 会把它映射成 agent 设计闭环可消费的 DesignProblem。
    支持单参数（tunable/bounds）与 N 维逆设计（tunables + constraint_bids）。
    """

    name: str
    device_type: str
    bids: List[str]                 # 关联的标准题（求解器正确性 + 设计达标）
    objective_bid: str              # 设计目标所在题（agent 优化它）
    target_metric: str
    target: float
    target_tol: float
    fixed_params: Dict[str, float]  # 注入到所有关联题的固定工艺参数
    tunables: Optional[Dict[str, Tuple[float, float]]] = None  # N 维逆设计
    tunable: Optional[str] = None   # 单参数名（向后兼容）
    bounds: Optional[Tuple[float, float]] = None  # 单参数 bounds（向后兼容）
    decreasing: bool = True         # metric 是否随 tunable 增大而单调减小
    note: str = ""
    constraint_bids: List[str] = field(default_factory=list)   # 须 PASS 的约束题
    use_gradient: bool = False    # True=派生问题用有限差分梯度下降（数值伴随）
    objective: Optional[List[Dict]] = None  # 加权多目标 [{bid,weight,target,tol}]；
                                             # None = 单目标（由 objective_bid 等构造）

    def __post_init__(self):
        if self.tunables is None:
            if not self.tunable or self.bounds is None:
                raise ValueError("须提供 tunables(多参数) 或 (tunable, bounds)(单参数)")
            self.tunables = {self.tunable: tuple(self.bounds)}


# --------------------------------------------------------------------------
# 工艺设计套件（PDK）
# --------------------------------------------------------------------------
@dataclass
class PDK:
    """一个工艺设计套件（Process Design Kit）：某 foundry 的一段工艺节点。"""

    foundry: str
    node: str                       # 工艺节点名，如 "SOI 180nm"
    wavelength_band: str
    n_si: float
    n_clad: float
    process_notes: str = ""
    # 量子工艺窗口：transmon 的充电能默认/可调区间由代工结型决定，不同
    # foundry 不同（如 Al/AlOx 固定频率 vs 可调耦合结、氧化层厚度差异）。
    # 与光子 n_si 对称——它是量子域"可制造窗口"的注入点，使量子逆设计
    # 天然落在某厂的 E_C 工艺现实内，不同厂收敛到不同 E_J 落点。
    quantum_window: Optional[Dict[str, float]] = None
    templates: Dict[str, DeviceTemplate] = field(default_factory=dict)

    def add_template(self, template: DeviceTemplate) -> None:
        self.templates[template.name] = template

    def to_summary(self) -> dict:
        return {
            "foundry": self.foundry,
            "node": self.node,
            "wavelength_band": self.wavelength_band,
            "n_si": self.n_si,
            "n_clad": self.n_clad,
            "quantum_window": dict(self.quantum_window) if self.quantum_window else None,
            "process_notes": self.process_notes,
            "templates": [
                {
                    "name": t.name,
                    "device_type": t.device_type,
                    "bids": t.bids,
                    "objective_bid": t.objective_bid,
                    "target_metric": t.target_metric,
                    "target": t.target,
                    "target_tol": t.target_tol,
                    "tunable": t.tunable,
                    "bounds": list(t.bounds) if t.bounds is not None else None,
                    "tunables": {k: list(v) for k, v in t.tunables.items()},
                    "constraint_bids": list(t.constraint_bids),
                    "use_gradient": t.use_gradient,
                    "objective": list(t.objective) if t.objective else None,
                    "fixed_params": t.fixed_params,
                    "decreasing": t.decreasing,
                    "note": t.note,
                }
                for t in self.templates.values()
            ],
        }


# --------------------------------------------------------------------------
# 开放 Registry
# --------------------------------------------------------------------------
class PDKRegistry:
    """开放 PDK Registry：登记 / 查询 / 由模板派生 agent 设计问题。

    这是 L0(IR) → L2(PDK 工艺参数) → L1(协议) → L3(内核) → harness
    全链路里"工艺参数"的注入点。没有它，设计问题的 bounds 与默认参数就是
    真空硬编码；有了它，agent 逆设计天然落在工艺可制造窗口内。
    """

    def __init__(self):
        self._pdks: Dict[str, PDK] = {}

    def register(self, pdk: PDK) -> None:
        self._pdks[pdk.foundry + "::" + pdk.node] = pdk

    def list_pdks(self) -> List[str]:
        return list(self._pdks.keys())

    def get(self, key: str) -> PDK:
        if key not in self._pdks:
            raise KeyError(f"未登记的 PDK: {key}（已知：{self.list_pdks()}）")
        return self._pdks[key]

    def derive_problem(self, pdk_key: str, template_name: str,
                       solver: str = "truth"):
        """由 PDK 模板派生一个可喂给 DesignAgent 的 DesignProblem。

        延迟导入 lda_agent.design_loop，避免 lda_l2 与 lda_agent 形成
        强编译期耦合（二者在运行期才接成闭环）。
        """
        from lda_agent.design_loop import DesignProblem

        pdk = self.get(pdk_key)
        t = pdk.templates.get(template_name)
        if not t:
            raise KeyError(f"PDK {pdk_key} 无模板 {template_name}")
        return DesignProblem(
            name=f"{pdk.foundry}/{pdk.node} · {t.name}",
            bids=list(t.bids),
            objective_bid=t.objective_bid,
            target_metric=t.target_metric,
            target=t.target,
            target_tol=t.target_tol,
            tunables={k: tuple(v) for k, v in t.tunables.items()},
            base_params=dict(t.fixed_params),
            decreasing=t.decreasing,
            constraint_bids=list(t.constraint_bids),
            use_gradient=t.use_gradient,
            objective=list(t.objective) if t.objective else None,
            solver=solver,
        )

    def to_summary(self) -> dict:
        return {k: v.to_summary() for k, v in self._pdks.items()}


# --------------------------------------------------------------------------
# 全局默认 Registry（应用启动即加载示例 PDK，可被社区扩展）
# --------------------------------------------------------------------------
_DEFAULT_REGISTRY: Optional[PDKRegistry] = None


def get_default_registry() -> PDKRegistry:
    """返回（惰性构建并缓存）默认 Registry 实例。"""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        from .pdk_examples import build_example_registry
        _DEFAULT_REGISTRY = build_example_registry()
    return _DEFAULT_REGISTRY
