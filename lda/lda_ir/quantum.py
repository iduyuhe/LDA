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

from typing import Dict, Optional, Tuple

from .core import Component, PhysicsAnchor, Port


def Transmon(id: str = "q1", E_J: float = 20.0, E_C: float = 0.30,
             target_f01: Optional[float] = None,
             EJ_bounds: Tuple[float, float] = (5.0, 40.0),
             EC_bounds: Tuple[float, float] = (0.1, 1.0)) -> Component:
    """超导 transmon 量子比特（驱动 B9 频率逆设计的主器件）。

    光子子集 v0.2 同步：量子子集从"预留"推进为"骨架字段定义"——
    本件已是完整骨架（E_J / E_C 字段 + f01 解析锚），新增 target_f01
    表达量子设计意图：
      - E_J / E_C    ：约瑟夫森能 / 充电能（GHz），f01 = √(8·E_J·E_C) − E_C；
      - target_f01   ：可选目标跃迁频率（GHz），对齐光子 SpectrumSpec 的
                       "目标谱形"语义——量子侧用"目标频率"表达设计意图。

    默认两参数均可调（N 维逆设计）；若只想调 E_J 命中频率，可只给 EJ_bounds。
    D-40：挂 PhysicsAnchor B9（Koch2007 确定性物理锚）。
    """
    params: Dict[str, float] = {"E_J": E_J, "E_C": E_C}
    if target_f01 is not None:
        params["target_f01"] = target_f01
    bounds: Dict[str, tuple] = {"E_J": tuple(EJ_bounds), "E_C": tuple(EC_bounds)}
    if target_f01 is not None:
        bounds["target_f01"] = (1.0, 15.0)
    return Component(
        id=id,
        kind="Transmon",
        params=params,
        param_bounds=bounds,
        ports=[Port("control"), Port("readout")],
        physics=PhysicsAnchor(
            bid="B9", kind="transmon-f01",
            spec_params={"E_J": E_J, "E_C": E_C},
            anchor="Koch2007 解析色散近似 f01=√(8·E_J·E_C)−E_C（GHz）"
                   "；严格侧=D-35 transmon 哈密顿量对角化"),
    )


def Resonator(id: str = "r1", Lp: float = 0.4e-6, Cp: float = 1.5e-10,
              l: float = 3000e-6, Q: float = 1.0e4,
              Lp_bounds: Tuple[float, float] = (0.3e-6, 0.6e-6),
              Cp_bounds: Tuple[float, float] = (1.0e-10, 2.5e-10),
              l_bounds: Tuple[float, float] = (2000e-6, 4000e-6)) -> Component:
    """读out/耦合谐振腔（λ/4 微波谐振，频率 f0、品质因子 Q）。

    D-40 深化：从"抽象 f0/Q"升级为**物理规范参数**（L′/C′/l，分布参数），
    f0 由物理定律 λ/4 闭式给出（f=1/(4l√(L′C′))），并挂 PhysicsAnchor B12
    （闭式 ↔ D-39 离散 TL 严格本征值）。与光子谐振器不同，这里是微波谐振，
    不进入 B11 光学谱形链路。
    """
    f0 = 1.0 / (4.0 * l * (Lp * Cp) ** 0.5) / 1e9  # GHz
    return Component(
        id=id,
        kind="Resonator",
        params={"Lp": Lp, "Cp": Cp, "l": l, "Q": Q, "f0_ghz": round(f0, 6)},
        param_bounds={"Lp": tuple(Lp_bounds), "Cp": tuple(Cp_bounds),
                      "l": tuple(l_bounds)},
        ports=[Port("in"), Port("out")],
        physics=PhysicsAnchor(
            bid="B12", kind="resonator-f0",
            spec_params={"Lp": Lp, "Cp": Cp, "l": l},
            anchor="λ/4 闭式 f0=1/(4l√(L′C′))（连续极限物理定律）"
                   "；严格侧=D-39 离散 TL 三对角特征值"),
    )


def Coupler(id: str = "c1", g: float = 0.1, E_J1: float = 20.0,
            E_C1: float = 0.25, E_J2: float = 20.0, E_C2: float = 0.25,
            Cc: float = 0.02, C1: float = 1.0, C2: float = 1.0,
            g_bounds: Tuple[float, float] = (0.0, 0.5)) -> Component:
    """可调耦合器（耦合强度 g GHz，连接两个 transmon 或 transmon-谐振腔）。

    D-40 深化：从"抽象 g"升级为**双 transmon 物理规范参数**（E_J1/E_C1/
    E_J2/E_C2/Cc/C1/C2），J 由解析闭式 J=Jc·n01₁·n01₂ 给出，并挂
    PhysicsAnchor B13（解析 J ↔ D-39 441 维严格对角化）。
    """
    Jc = Cc / (C1 * C2)
    n01 = lambda ej, ec: (ej / (2.0 * ec)) ** 0.25 / 2.0  # noqa: E731
    j_ghz = Jc * n01(E_J1, E_C1) * n01(E_J2, E_C2)
    return Component(
        id=id,
        kind="Coupler",
        params={"g": g, "E_J1": E_J1, "E_C1": E_C1, "E_J2": E_J2, "E_C2": E_C2,
                "Cc": Cc, "C1": C1, "C2": C2, "J_ghz": round(j_ghz, 6)},
        param_bounds={"g": tuple(g_bounds)},
        ports=[Port("a"), Port("b", directed=True)],
        physics=PhysicsAnchor(
            bid="B13", kind="coupler-J",
            spec_params={"E_J1": E_J1, "E_C1": E_C1, "E_J2": E_J2,
                         "E_C2": E_C2, "Cc": Cc, "C1": C1, "C2": C2},
            anchor="J=Jc·<0|n̂|1>₁·<0|n̂|1>₂，n01=(E_J/2E_C)^{1/4}/2（Koch 类）"
                   "；严格侧=D-39 双 qubit 441 维电荷 basis 对角化"),
    )
