"""LDA L0 · 光子子集器件 Kinds（工厂函数）。

把"常见光子器件"做成 IR Component 的便捷构造器，使 agent / 人都能用一行
代码表达一个设计主体。每个 Kind 自带默认端口与可调参数区间（工艺窗口由
L2 PDK 最终收紧，这里给一个宽松默认）。

这些 Kinds 是 L0 IR 的领域词汇表（vocabulary）起点；量子子集（Transmon /
Resonator / Coupler）后续在同目录 quantum.py 扩展，复用 core.py 的同一套
数据模型——这正是"统一 IR"的复利点：光子与量子共享 Port/Net/ObjectiveSpec。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .core import Component, Port


def RingResonator(id: str = "ring", R: float = 10.0, n_g: Optional[float] = None,
                  R_bounds: tuple = (8.0, 12.0)) -> Component:
    """环形谐振器（驱动 B11 谱形逆设计的主器件）。

    n_g 默认 None：不写死群折射率，由桥接层按目标 foundry 的工艺折射率
    （n_si 近似）注入——这正是"多晶圆厂落点差异"的来源（不同 foundry
    折射率不同 → 同一 FSR 目标收敛到不同几何）。如显式给定 n_g，则按设计
    意图固定（跨 foundry 不变）。
    """
    params: Dict[str, float] = {"R": R}
    if n_g is not None:
        params["n_g"] = n_g
    return Component(
        id=id,
        kind="RingResonator",
        params=params,
        param_bounds={"R": tuple(R_bounds)},
        ports=[Port("in"), Port("out"), Port("drop")],
    )


def Waveguide(id: str = "wg", width: float = 0.5, width_bounds: tuple = (0.35, 0.75)) -> Component:
    """直波导（几何相关场级 ORACLE 题 B1/B4 的主体）。"""
    return Component(
        id=id,
        kind="Waveguide",
        params={"width": width},
        param_bounds={"width": tuple(width_bounds)},
        ports=[Port("in"), Port("out")],
    )


def GratingCoupler(id: str = "gc", period: float = 0.63, duty: float = 0.5,
                   period_bounds: tuple = (0.55, 0.72)) -> Component:
    """光栅耦合器（B6 耦合效率题主体）。"""
    return Component(
        id=id,
        kind="GratingCoupler",
        params={"period": period, "duty": duty},
        param_bounds={"period": tuple(period_bounds)},
        ports=[Port("fib"), Port("wg")],
    )


def Splitter(id: str = "mmi", length: float = 5.0, width: float = 2.0,
             length_bounds: tuple = (3.0, 8.0)) -> Component:
    """MMI / 分束器（B7 分束比题主体）。"""
    return Component(
        id=id,
        kind="Splitter",
        params={"length": length, "width": width},
        param_bounds={"length": tuple(length_bounds)},
        ports=[Port("in"), Port("out1"), Port("out2")],
    )


# 领域词汇表（便于校验 / 渲染时识别已知 Kind）
KNOWN_KINDS: List[str] = ["RingResonator", "Waveguide", "GratingCoupler", "Splitter"]
