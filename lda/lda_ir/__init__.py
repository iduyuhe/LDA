"""LDA L0 · 统一 IR/DSL 包入口（光子 + 量子统一子集）。

机器优先的设计意图中间表示。直接可序列化（to_dict/from_dict）、可校验
(validate)、可桥接到真实 agent 设计闭环（bridge），并携带目标谱形与多
晶圆厂落点意图（候选④）。光子与量子共用同一套 core/校验/桥接，仅 Kinds
与 domain 不同——这正是"统一光子+量子"差异化定位的底座。
"""
from __future__ import annotations

from .core import (
    Component, FoundryPlan, IRModel, Net, ObjectiveSpec, Port, SpectrumSpec,
)
from .photon import (DirectionalCoupler, GratingCoupler, RingResonator,
                     Splitter, SymmetricYBranch, Waveguide)
from .quantum import Coupler, Resonator, Transmon
from .dsl import dumps, from_dict, loads, to_dict, to_dsl
from .validate import validate

__all__ = [
    "IRModel", "Component", "Port", "Net", "ObjectiveSpec",
    "SpectrumSpec", "FoundryPlan",
    "RingResonator", "Waveguide", "GratingCoupler", "Splitter",
    "DirectionalCoupler", "SymmetricYBranch",
    "Transmon", "Resonator", "Coupler",
    "to_dict", "from_dict", "dumps", "loads", "to_dsl", "validate",
]
