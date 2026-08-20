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
                  Q: float = 1.0e4, kappa: float = 0.05,
                  target_fsr_nm: Optional[float] = None,
                  R_bounds: tuple = (8.0, 12.0),
                  Q_bounds: tuple = (1.0e3, 1.0e5),
                  kappa_bounds: tuple = (0.0, 0.5)) -> Component:
    """add-drop 环形谐振器（驱动 B11 谱形逆设计的主器件）。

    光子子集 v0.2 补全字段（此前仅 R / n_g）：
      - R             ：环半径（µm），谱形驱动主几何参数；
      - n_g           ：群折射率，默认 None 由桥接层按 foundry 工艺折射率注入
                        （跨 foundry 落点差异来源）；显式给定则跨 foundry 固定；
      - Q             ：品质因子（无量纲），驱动线宽 / 消光；
      - kappa         ：波导-环耦合系数（无量纲），决定临界耦合与 drop 效率；
      - target_fsr_nm ：可选 FSR 目标（nm），与 SpectrumSpec 同语义、内聚到
                        组件，供 L3 直接消费（无需额外挂 SpectrumSpec）。

    向后兼容：旧调用 `RingResonator(R=10.0, R_bounds=(...))` 仍有效。
    """
    params: Dict[str, float] = {"R": R, "Q": Q, "kappa": kappa}
    if n_g is not None:
        params["n_g"] = n_g
    if target_fsr_nm is not None:
        params["target_fsr_nm"] = target_fsr_nm
    bounds: Dict[str, tuple] = {"R": tuple(R_bounds), "Q": tuple(Q_bounds),
                                "kappa": tuple(kappa_bounds)}
    if target_fsr_nm is not None:
        bounds["target_fsr_nm"] = (0.1, 100.0)
    return Component(
        id=id,
        kind="RingResonator",
        params=params,
        param_bounds=bounds,
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


def DirectionalCoupler(id: str = "dc", gap: float = 0.3, Lc: float = 10.0,
                       kappa_target: Optional[float] = None,
                       gap_bounds: tuple = (0.10, 0.60),
                       Lc_bounds: tuple = (1.0, 60.0)) -> Component:
    """方向耦合器（dirty 兄弟器件，D-01 验收锚的对口 IR 表达）。

    光子子集 v0.2 新增。字段对齐 D-01 已验证验收锚（gap=0.3/0.25µm → κ）：
      - gap           ：耦合间隙（µm），决定耦合强度 κ；
      - Lc            ：耦合长度（µm），决定交叉功率分配；
      - kappa_target  ：可选目标耦合系数 κ（1/µm），供 L3 直接消费——
                        与 oracle_coupler 的超模法 κ 同语义，使 IR 成为
                        "耦合器验收"的唯一事实源（技术复利）。

    四端口（双向）：in1/in2 为两输入波导，thru1/thru2 为直通/交叉输出。
    """
    params: Dict[str, float] = {"gap": gap, "Lc": Lc}
    if kappa_target is not None:
        params["kappa_target"] = kappa_target
    bounds: Dict[str, tuple] = {"gap": tuple(gap_bounds), "Lc": tuple(Lc_bounds)}
    if kappa_target is not None:
        bounds["kappa_target"] = (0.0, 0.5)
    return Component(
        id=id,
        kind="DirectionalCoupler",
        params=params,
        param_bounds=bounds,
        ports=[Port("in1"), Port("in2"), Port("thru1"), Port("thru2")],
    )


def SymmetricYBranch(id: str = "yb", width: float = 0.5, split_angle: float = 10.0,
                     arm_length: float = 5.0,
                     width_bounds: tuple = (0.30, 1.00),
                     angle_bounds: tuple = (1.0, 30.0),
                     arm_bounds: tuple = (1.0, 20.0)) -> Component:
    """对称 Y 分支分束器（D-01 验收锚的对口 IR 表达：50/50 平衡分束）。

    光子子集 v0.2 新增（与既有 MMI 式 Splitter 区分：本件为零附加长度、
    对称分叉的 Y 分支，D-01 用对称性定理验证 50/50）。字段：
      - width        ：波导宽度（µm）；
      - split_angle  ：分支角（度），决定模式演化与分束对称性；
      - arm_length   ：分支臂长（µm），供版图 / 截断用。

    三端口（双向）：in 为单输入，out1/out2 为对称两输出（目标 50/50）。
    """
    return Component(
        id=id,
        kind="SymmetricYBranch",
        params={"width": width, "split_angle": split_angle, "arm_length": arm_length},
        param_bounds={"width": tuple(width_bounds), "split_angle": tuple(angle_bounds),
                      "arm_length": tuple(arm_bounds)},
        ports=[Port("in"), Port("out1"), Port("out2")],
    )


# 领域词汇表（便于校验 / 渲染时识别已知 Kind）
KNOWN_KINDS: List[str] = [
    "RingResonator", "Waveguide", "GratingCoupler", "Splitter",
    "DirectionalCoupler", "SymmetricYBranch",
]
