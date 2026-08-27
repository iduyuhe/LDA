"""LDA L2 · 多层版图层栈定义（layer stack · v0.8.25 · 版图差距 #6）。

多层版图 = 信号层（金属/波导）+ 介质层（层间隔离）+ 通孔层（via 跨层电气连接）。
LVS 多层的核心语义：
  - **不同信号层垂直投影重叠 ≠ 短路**（介质隔离——只有经 via 才允许跨层电气连接）；
  - **同层路径相交 = 短路**；
  - **via 是唯一合法的跨层桥**（via 落在他 net 路径/端口上 = 短路）。

本模块定义层栈数据结构与默认栈（SOI 风格：M1 硅波导 / VIA12 通孔 / M2 金属
互连）。C 级自写零依赖；真实 PDK 层叠属发动期对接，此处为公开工艺近似。

层语义（简化物理模型）：
  - signal 层：承载布线的导电层（M1/M2…），彼此间被介质（SiO₂ 等）隔离；
  - via 层：连接相邻两个 signal 层的通孔（VIA12 连接 M1↔M2）；
  - dielectric 层：仅隔离（不参与 LVS 电气比对，用于层序校验）。

`stack.can_cross(l1, l2)`：l1/l2 两信号层是否可能短路（同层 True，异层 False）——
多层 LVS 短路判定的核心谓词。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Layer:
    """单个版图层。kind: signal（导电布线）/ via（通孔）/ dielectric（介质）。"""
    name: str
    kind: str                                    # "signal" | "via" | "dielectric"
    z_top_um: float = 0.0                        # 层顶 z（µm，工艺坐标）
    z_bot_um: float = 0.0                        # 层底 z


@dataclass
class LayerStack:
    """版图层栈：信号层 + via 层 + 层间连接映射。"""
    name: str
    layers: Dict[str, Layer] = field(default_factory=dict)
    via_map: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    # via 层名 -> (下层, 上层)：VIA12 -> ("M1", "M2")

    def signal_layers(self) -> List[str]:
        """信号层名列表（布线可用的导电层，按 z 升序）。"""
        sig = [n for n, l in self.layers.items() if l.kind == "signal"]
        return sorted(sig, key=lambda n: self.layers[n].z_top_um)

    def via_layers(self) -> List[str]:
        return [n for n, l in self.layers.items() if l.kind == "via"]

    def can_cross(self, l1: str, l2: str) -> bool:
        """两信号层是否可能短路：同层 True；异层经介质隔离 False（仅 via 可桥）。

        这是多层 LVS 短路判定的核心谓词——同层路径相交才判 short，
        跨层投影重叠（M1/M2 垂直重叠）不判 short（介质隔离，物理正确）。
        未知层名按同层保守处理（True，宁可多报不放过）。
        """
        if l1 not in self.layers or l2 not in self.layers:
            return l1 == l2  # 未知层：仅同名判短（保守）
        if l1 == l2:
            return self.layers[l1].kind == "signal"  # 信号层同层相交可短
        return False  # 异层介质隔离

    def via_connects(self, via_layer: str, l1: str, l2: str) -> bool:
        """via 层是否恰好连接 l1↔l2 两信号层。"""
        pair = self.via_map.get(via_layer)
        return pair is not None and set(pair) == {l1, l2}

    def to_summary(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "signal_layers": self.signal_layers(),
            "via_layers": self.via_layers(),
            "via_map": {k: list(v) for k, v in self.via_map.items()},
        }


# ---------------------------------------------------------------------------
# 默认栈：SOI 风格（M1 硅波导 / VIA12 / M2 金属互连）——公开工艺近似
# ---------------------------------------------------------------------------
DEFAULT_SOI_STACK = LayerStack(
    name="SOI-3L（公开近似）",
    layers={
        "M1": Layer("M1", "signal", z_top_um=0.22, z_bot_um=0.0),    # Si 波导层
        "VIA12": Layer("VIA12", "via", z_top_um=0.42, z_bot_um=0.22),  # W 通孔
        "M2": Layer("M2", "signal", z_top_um=0.62, z_bot_um=0.42),   # 金属互连层
    },
    via_map={"VIA12": ("M1", "M2")},
)

# 量子工艺栈（Al-AlOx：M1 超导布线 / VIA1 通孔 / M2 超导地平面）——预留
AL_STACK = LayerStack(
    name="Al-3L（公开近似）",
    layers={
        "M1": Layer("M1", "signal", z_top_um=0.10, z_bot_um=0.0),    # Al 信号层
        "VIA1": Layer("VIA1", "via", z_top_um=0.20, z_bot_um=0.10),
        "M2": Layer("M2", "signal", z_top_um=0.30, z_bot_um=0.20),   # Al 地平面
    },
    via_map={"VIA1": ("M1", "M2")},
)

STACK_REGISTRY: Dict[str, LayerStack] = {
    "soi": DEFAULT_SOI_STACK,
    "al": AL_STACK,
}


def get_stack(name: str = "soi") -> LayerStack:
    """取层栈（缺省 SOI）。"""
    return STACK_REGISTRY.get(name, DEFAULT_SOI_STACK)
