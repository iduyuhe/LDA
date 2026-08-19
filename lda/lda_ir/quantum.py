"""LDA L0 · 量子子集 Kinds（复用 core，与光子子集同一套 IR 地基）。

这是"统一光子 + 量子"差异化的具体落地——**同一套 IR 数据模型**（Component /
Param / ObjectiveSpec / 校验器 / 桥接层）同时表达光子器件与量子器件，agent
设计闭环与验证裁判对两者一视同仁。光子靠折射率/几何，量子靠约瑟夫森/充电能，
但"设计意图 → IR → 桥接 → 设计闭环 → 物理定律锚验证"的链路完全一致。

量子侧黄金参考为 ①类确定性物理锚（核心永不 import GPL/商业依赖）：
  - B9 transmon 跃迁频率 f01（Koch2007 解析色散近似）；
  - B10 单比特门保真度（退相干极限解析）。
真实 EPR 哈密顿量对角化（pyEPR/Ansys）属 A 级强依赖，按主权策略只作
外部 ORACLE（oracle_pyepr.py），核心不沾。

本模块零外部依赖，仅 import 标准库与本包 core。
"""
from __future__ import annotations

from typing import Tuple

from .core import Component, Port


def Transmon(id: str = "q1", E_J: float = 20.0, E_C: float = 0.30,
             EJ_bounds: Tuple[float, float] = (5.0, 40.0),
             EC_bounds: Tuple[float, float] = (0.1, 1.0)) -> Component:
    """超导 transmon 量子比特（驱动 B9 频率逆设计的主器件）。

    E_J = 约瑟夫森能（GHz），E_C = 充电能（GHz）。f01 = √(8·E_J·E_C) − E_C。
    默认两参数均可调（N 维逆设计）；若只想调 E_J 命中频率，可只给 EJ_bounds。
    """
    return Component(
        id=id,
        kind="Transmon",
        params={"E_J": E_J, "E_C": E_C},
        param_bounds={"E_J": tuple(EJ_bounds), "E_C": tuple(EC_bounds)},
        ports=[Port("control"), Port("readout")],
    )


def Resonator(id: str = "r1", f0: float = 5.0, Q: float = 1.0e4,
              f0_bounds: Tuple[float, float] = (4.0, 8.0)) -> Component:
    """读out/耦合谐振腔（频率 f0 GHz、品质因子 Q）。

    用于量子-光子混合系统（如玻色编码、readout 腔）。当前 IR 仅建模几何/
    频率参数；与光子谐振器不同，这里是微波谐振，不进入 B11 光学谱形链路。
    """
    return Component(
        id=id,
        kind="Resonator",
        params={"f0": f0, "Q": Q},
        param_bounds={"f0": tuple(f0_bounds)},
        ports=[Port("in"), Port("out")],
    )


def Coupler(id: str = "c1", g: float = 0.1,
            g_bounds: Tuple[float, float] = (0.0, 0.5)) -> Component:
    """可调耦合器（耦合强度 g GHz，连接两个 transmon 或 transmon-谐振腔）。

    用于可调耦合架构（避免固定耦合带来的频率拥挤 / 串扰）。g 可调区间由
    工艺窗口决定（可调耦合 junction 的磁通偏置范围）。
    """
    return Component(
        id=id,
        kind="Coupler",
        params={"g": g},
        param_bounds={"g": tuple(g_bounds)},
        ports=[Port("a"), Port("b", directed=True)],
    )
