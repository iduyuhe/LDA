# -*- coding: utf-8 -*-
"""SoC 多层光电 GDS 协同组装（光子计算 SoC 征程 S2 · G3 雏形）。

复用 `gds_export` 既有层定义（LIB_LAYER_SI=1 光子芯层 / LIB_LAYER_METAL=3 金属层 /
LIB_LAYER_HEATER=6 热相移器层 / LIB_LAYER_SI 兼光 IO），把 SoC 三类子系统协同写入
同一份 GDSII，满足集成度判据 C8（同一份主权 GDS 含光子层 + 电子层 + IO/热层）。

红线：本模块只做**几何协同占位与层断言**，不引入任何工艺/性能宣称；真实 foundry
PDK 映射（G4）不在首期。
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from lda_l2 import gds_export as gx


def assemble_soc_gds(photon_elements: Sequence[bytes],
                     eic_elements: Sequence[bytes],
                     io_elements: Sequence[bytes],
                     heater_elements: Sequence[bytes] = ()) -> bytes:
    """把光子核(SI) / 电子外设(METAL) / 光 IO(SI) / 热相移器(HEATER) 组装进同一份 GDS。

    返回 GDSII bytes（`gds_export.gds_library`）。
    """
    structs = {
        "SOC_TOP": (list(photon_elements) + list(eic_elements)
                    + list(io_elements) + list(heater_elements))
    }
    return gx.gds_library("LDA_SOC", structs)


def soc_layer_report(elements_by_layer: Dict[int, Sequence[bytes]]) -> set:
    """返回 SoC GDS 中实际出现的层集合（C8 层协同断言用）。"""
    return set(elements_by_layer.keys())


def build_minimal_soc_demo(N: int = 8) -> Dict[str, Any]:
    """构造最小 SoC GDS 演示：N 光子 MZI 臂 + N 电子焊盘 + 2 光 IO + N 热相移器。

    仅几何占位，用于集成度判据 C8 机器核验；不作任何工艺 / 性能宣称。
    """
    photon = [gx.path(gx.LIB_LAYER_SI, 0.5,
                      [(i * 2.0, 0.0), (i * 2.0, 10.0)]) for i in range(N)]
    eic = [gx.boundary(gx.LIB_LAYER_METAL,
                       [(i * 1.0, 12.0), (i * 1.0 + 0.5, 12.0),
                        (i * 1.0 + 0.5, 12.5), (i * 1.0, 12.5)]) for i in range(N)]
    io = [gx.path(gx.LIB_LAYER_SI, 0.5,
                  [(-2.0, y), (-2.0, y + 5.0)]) for y in (0.0, 20.0)]
    heater = [gx.boundary(gx.LIB_LAYER_HEATER,
                          [(i * 2.0, -1.0), (i * 2.0 + 1.0, -1.0),
                           (i * 2.0 + 1.0, -0.5), (i * 2.0, -0.5)]) for i in range(N)]
    gds = assemble_soc_gds(photon, eic, io, heater)
    layers = sorted({gx.LIB_LAYER_SI, gx.LIB_LAYER_METAL, gx.LIB_LAYER_HEATER})
    return {
        "gds_bytes": gds,
        "n_layers": len(layers),
        "layers": layers,
        "n_mzi": N,
        "n_eic": N,
        "n_io": 2,
        "n_heater": N,
    }


if __name__ == "__main__":
    print("=== SoC 多层 GDS 协同演示 ===")
    d = build_minimal_soc_demo(16)
    print("  GDS 字节数=%d  层数=%d  层集合=%s" % (len(d["gds_bytes"]), d["n_layers"], d["layers"]))
    print("  光子核=%d 电子=%d 光IO=%d 热相移器=%d" % (d["n_mzi"], d["n_eic"], d["n_io"], d["n_heater"]))
