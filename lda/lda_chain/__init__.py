"""LDA P1-M1 · 通用链路框架（lda_chain）。

芯片级补强的共同地基：通用链路模型（LinkModel）+ 通用光子级联仿真引擎
（engine）+ 器件传递模型注册表（registry）+ 光子 MVP 骨架（photon_link）。

零依赖（标准库 + 现有 lda_ir / lda_agent 解析模型），C 级自写，主权可控。
"""
from __future__ import annotations

from .engine import simulate
from .link_model import LinkModel
from .photon_link import build_wdm_link, build_wdm_link_from_channels
from .registry import get_response, register_device_model
from .route_sim import route_and_simulate
from lda_layout.router import route_net, RouteResult
from lda_layout.placement import (place_row, port_anchor, device_bbox, port_abs)

__all__ = [
    "LinkModel", "simulate", "registry_get_response", "register_device_model",
    "build_wdm_link", "build_wdm_link_from_channels",
    "route_and_simulate", "route_net", "RouteResult",
    "place_row", "port_anchor", "device_bbox", "port_abs",
]

# 别名，避免与 registry 模块名冲突时的歧义导入
registry_get_response = get_response
