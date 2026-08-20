"""LDA L0 · 统一中间表示（IR）/ DSL —— 核心数据模型（光子子集草案）。

L0 是架构分层里最底层、最该"自己做好、不取巧"的地基（主权策略 C 级：
第一天自主）。它表达的是**设计意图的统一机器语言**，而不是给人看的 GUI
或给人逐步调参的 API（《白皮书》§11/§12 人机协作哲学：人定方向，agent
负责操作执行）。因此本模块刻意"机器优先"——

  - 一切结构均可序列化为纯 dict（JSON 友好，便于 agent 间传递、经 L1 MCP
    传输、落库 diff）；
  - 不绑定任何 EDA 商业格式（GDSII/OASIS 是 A 级，永不借）；
  - 零外部依赖（仅标准库），离线可跑、主权可控。

本草案聚焦**光子 + 量子统一子集**（`photon.py` / `quantum.py` 复用同一套
core），并顺带把两块"设计意图"显式表达出来（对应之前讨论的候选④）：
  - SpectrumSpec   ：目标谱形（如环形谐振器 FSR 目标），驱动 B11 谱形逆设计；
  - FoundryPlan    ：多晶圆厂落点意图（"all"= 跨已注册 foundry 各跑一遍），
                     驱动 L2 多晶圆厂共建闭环。
光子靠折射率/几何、量子靠约瑟夫森/充电能，但"设计意图→IR→桥接→设计闭环→
物理定律锚验证"链路完全一致——这正是"统一光子+量子"差异化定位的底座。

验证裁判（harness）与设计闭环（agent）都消费 IR 派生出的 DesignProblem，
IR 本身不直接算物理——它只描述"要造什么、约束是什么、目标谱长什么样、
想落在哪个/哪些 foundry"。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# --------------------------------------------------------------------------
# 端口 / 网表 / 几何参数
# --------------------------------------------------------------------------
@dataclass
class Port:
    """器件端口（用于网表连接与可制造性校验）。"""
    name: str
    directed: bool = False       # True=同向（in/out），False=双向（光无源通常双向）


@dataclass
class Net:
    """网表连接：把若干 component.port 连到一起（光学：波导连器件）。"""
    id: str
    connects: List[str] = field(default_factory=list)   # ["comp_id.port_name", ...]


# --------------------------------------------------------------------------
# 目标规格 / 目标谱形 / 多 foundry 落点（候选④ 显式表达）
# --------------------------------------------------------------------------
@dataclass
class ObjectiveSpec:
    """一个设计目标或硬约束，引用标准题 bid（harness 验证裁判的题号）。

    role="objective"  → agent 优化它使其命中 target±tol；
    role="constraint" → 必须 PASS（不优化，但不过则整体判 FAIL）。
    """
    bid: str                       # 如 "B11" / "B4" / "B2"
    weight: float = 1.0
    target: float = 0.0
    tol: float = 0.05
    role: str = "objective"        # "objective" | "constraint"


@dataclass
class SpectrumSpec:
    """目标谱形规格（驱动 B11 谱形逆设计）。

    当前支持两种 kind：
      - "ring_fsr"   ：环形谐振器自由光谱范围目标（nm），metric 用
                       FSR_c = wl0^2 / (n_g · 2π · R) · 1000，
                       误差 = |FSR_c − target_fsr_nm| / target_fsr_nm；
                       与 lda_harness.golden.b11_ring_spectrum_match 同公式，
                       IR 模块自包含、零耦合 harness。
      - "lorentz_comb"：（预留）逐波长洛伦兹梳目标，待扩展。

    metric(R, n_g) 供 bridge 直接构造 objective（bid="B11", target=0）。
    """
    kind: str = "ring_fsr"
    target_fsr_nm: float = 9.15
    wl0_um: float = 1.55
    n_g: float = 4.2
    primary_param: str = "R"       # 驱动谱形的主几何参数名（环形=半径 R）

    def metric(self, R: float, n_g: Optional[float] = None) -> float:
        """返回谱形归一化误差（0=完美匹配）。与 golden.b11 同式。"""
        ng = n_g if n_g is not None else self.n_g
        fsr_c = (self.wl0_um ** 2) / (ng * 2.0 * 3.141592653589793 * R) * 1000.0
        return abs(fsr_c - self.target_fsr_nm) / self.target_fsr_nm


@dataclass
class FoundryPlan:
    """多晶圆厂落点意图（驱动 L2 多晶圆厂共建闭环）。

    mode="all"  ：跨已注册的全部 foundry 各跑一遍逆设计；
    mode="list" ：仅在 foundries 指定的 foundry 列表上跑。
    """
    mode: str = "all"                          # "all" | "list"
    foundries: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# 器件实例 / 顶层模型
# --------------------------------------------------------------------------
@dataclass
class Component:
    """一个器件实例（IR 图里的节点）。

    kind 决定领域语义（光子：RingResonator / Waveguide / GratingCoupler /
    Splitter ...）；params 是几何/工艺参数；param_bounds 标记哪些参数可调
    及其工艺窗口；ports 用于网表连接；foundry_hints 给 agent 的软提示
    （最终落点由 FoundryPlan + L2 Registry 决定，不强制）。
    """
    id: str
    kind: str
    params: Dict[str, float] = field(default_factory=dict)
    param_bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    ports: List[Port] = field(default_factory=list)
    foundry_hints: List[str] = field(default_factory=list)


@dataclass
class IRModel:
    """L0 顶层统一中间表示。

    机器优先：全部可 to_dict()（→ JSON）→ from_dict() round-trip；to_dsl()
    仅作人类可读渲染（见 dsl.py）。描述"要造什么、约束、目标谱、想落哪个
    foundry"，不直接算物理。
    """
    schema_version: str = "0.2"
    domain: str = "photon"                      # "photon" | "quantum"
    name: str = ""
    components: List[Component] = field(default_factory=list)
    nets: List[Net] = field(default_factory=list)
    pdk_ref: Optional[str] = None               # 倾向 foundry::node；None=不限定
    foundry_plan: Optional[FoundryPlan] = None  # 多 foundry 落点意图
    objectives: List[ObjectiveSpec] = field(default_factory=list)
    spectrum: Optional[SpectrumSpec] = None     # 目标谱形（B11 逆设计）
    notes: str = ""

    # —— 便捷构造 ——
    def add(self, comp: Component) -> "IRModel":
        self.components.append(comp)
        return self

    def connect(self, net_id: str, *ports: str) -> "IRModel":
        self.nets.append(Net(id=net_id, connects=list(ports)))
        return self

    # —— 主器件（bridge 取它构造 DesignProblem）——
    @property
    def primary_component(self) -> Optional[Component]:
        if not self.components:
            return None
        # 优先取 kind 含 Resonator / Grating / Splitter / Waveguide /
        # Coupler / YBranch 的设计主体（v0.2 新增方向耦合器 / 对称 Y 分支）
        for k in ("Resonator", "Grating", "Splitter", "Waveguide",
                  "Coupler", "YBranch"):
            for c in self.components:
                if k in c.kind:
                    return c
        return self.components[0]
