"""LDA L2 · 开放 PDK / 器件本体 Registry（机器优先，社区共建层）。"""
from .pdk import (
    PDK, DeviceTemplate, PDKRegistry, get_default_registry,
)
from .pdk_examples import build_example_registry

__all__ = [
    "PDK", "DeviceTemplate", "PDKRegistry",
    "get_default_registry", "build_example_registry",
]
