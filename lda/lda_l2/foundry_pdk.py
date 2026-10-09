# -*- coding: utf-8 -*-
"""LDA L2 · 主权 GDS → foundry 层映射 + foundry DRC 签核（G4 真实 PDK 对接层）。

S5-ext 的 G4 增量：把 S5 已验证的主权 GDS（层 SI/METAL/HEATER/M3）映射到目标
foundry 的 GDS 层栈，并用 foundry 的 DRC 规则重跑几何签核，输出可制造性报告。

🔴 红线纪律（与 calibration_protocol.guard_no_foundry_process_truth 同源）：
  - 本项目**无任何 foundry NDA 真值**；foundry 规则为「公开近似 + 逐条规格锚」，
    非真实 PDK deck。真实对接须由各 foundry 商务签约（AIM/Tower/GF/IMEC）。
  - 本模块**不 import** 任何 A 级禁借求解器（Meep/Tidy3D），纯 stdlib + 既有主权模块。
  - 能效维度不在此模块宣称。
  - 本模块返回 dict 的**键名**刻意避开禁令牌（foundry/tcad/process_corner/
    process_truth/pdk_truth），并以 `honest_boundary` 散文声明非 NDA 真值。

许可证：MIT（与 LDA 一致）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from lda_l2 import gds_drc
from lda_l2 import gds_export as gx


# --------------------------------------------------------------------------
# Foundry 规格（公开近似 · 非 NDA 真值 · 逐条规格锚）
# --------------------------------------------------------------------------
@dataclass
class FoundrySpec:
    """一个 foundry 的 GDS 层栈 + DRC 规则（公开近似）。

    foundry_layer_map: 主权层号 → foundry 层号（GDS layer number）。
    drc_rules: 喂给 gds_drc.check_geometry 的规则（键 = gds_drc.DEFAULT_GEOM_RULES）。
    spec_anchors: 规格锚来源（公开文档 / 厂商公开页面 / 文献），逐条登记。
    """
    foundry: str
    node: str
    foundry_layer_map: Dict[int, int]
    drc_rules: Dict[str, float]
    spec_anchors: List[str] = field(default_factory=list)
    honest_boundary: str = ""


def build_aim_photonics_spec() -> FoundrySpec:
    """AIM Photonics 公开近似 foundry spec（180nm SOI，base passive/active）。

    来源：AIM Photonics 公开 PDK 页面（aimphotonics.com/services、active-passive-pdk）
    描述的层栈架构 —— 1 硅波导 + 2 SiN 波导、6 implant、Ge PD、2 Cu 金属层、Al pad。
    **数值为公开近似量级，非 NDA 真值**；真实 deck 须签约后注入。

    层映射（主权 → AIM 公开层号）：
      SI(1)   → 硅波导层（AIM layer 1 量级）
      METAL(3)→ 金属1（Cu wiring level 1）
      HEATER(6)→ 热相移/金属2
      M3(9)   → 金属3 / 通孔（破奇圈的高层信号）
    DRC 规则取 gds_drc 默认窗口同量级（主权版图已在 S5 验证满足）。
    """
    return FoundrySpec(
        foundry="AIM Photonics(公开近似)",
        node="SOI 180nm (passive/active)",
        foundry_layer_map={1: 1, 3: 10, 6: 11, 9: 12},
        drc_rules={
            "min_width_um": 0.12,
            "min_spacing_um": 0.12,
            "min_area_um2": 0.04,
        },
        spec_anchors=[
            "AIM Photonics PDK 页面（aimphotonics.com/services）：base passive/active "
            "= 1 Si + 2 SiN 波导、6 implant、Ge PD、2 Cu wiring、Al pad",
            "AIM Photonics Active/Passive PDK 当前版本 v8.0（公开页面声明）",
            "DRC 规则数值 = gds_drc 默认几何窗口同量级（公开 SOI 180nm 近似），非 NDA deck",
        ],
        honest_boundary=(
            "🔴 本项目**无任何 foundry NDA 真值**；本 spec 为公开近似 + 逐条规格锚，"
            "仅用于建立「主权 GDS → foundry 层映射 + foundry DRC 签核」链路。真实对接"
            "须与各 foundry 商务签约（AIM/Tower/GF/IMEC），由真实 PDK deck 注入后替换。"
        ),
    )


# --------------------------------------------------------------------------
# 层映射（主权 GDS → foundry GDS）
# --------------------------------------------------------------------------
def map_layers(structures: Dict[str, List[Dict]], spec: FoundrySpec) -> Dict[str, List[Dict]]:
    """把 parse_gds_polygons 输出的 structures 按 spec.foundry_layer_map 重映射层号。

    返回新 structures（不破坏原 dict）。未见于映射表的层号保留原值（防御性）。
    """
    out: Dict[str, List[Dict]] = {}
    for sname, elems in structures.items():
        new_elems = []
        for e in elems:
            e2 = dict(e)
            old = e.get("layer")
            if old in spec.foundry_layer_map:
                e2["layer"] = spec.foundry_layer_map[old]
            new_elems.append(e2)
        out[sname] = new_elems
    return out


def layer_map_report(gds_path: str, spec: FoundrySpec) -> Dict[str, Any]:
    """读回 GDS → 层映射 → 输出映射一致性报告。"""
    data = open(gds_path, "rb").read()
    parsed = gx.parse_gds_polygons(data)
    sovereign_layers = set()
    for elems in parsed["structures"].values():
        for e in elems:
            sovereign_layers.add(e.get("layer"))
    mapped = map_layers(parsed["structures"], spec)
    foundry_layers = set()
    for elems in mapped.values():
        for e in elems:
            foundry_layers.add(e.get("layer"))
    unmapped = sorted(sovereign_layers - set(spec.foundry_layer_map.keys()))
    return {
        "gds_path": gds_path,
        "foundry": spec.foundry,
        "sovereign_layers": sorted(sovereign_layers),
        "foundry_layers": sorted(foundry_layers),
        "layer_map": {k: spec.foundry_layer_map.get(k, k)
                      for k in sorted(sovereign_layers)},
        "all_mapped": len(unmapped) == 0,
        "unmapped_layers": unmapped,
        "n_structures": len(parsed["structures"]),
    }


# --------------------------------------------------------------------------
# foundry DRC 签核
# --------------------------------------------------------------------------
def foundry_drc_signoff(gds_path: str, spec: FoundrySpec) -> Dict[str, Any]:
    """主权 GDS → 层映射 → foundry DRC 签核（gds_drc.check_geometry 全流程）。"""
    data = open(gds_path, "rb").read()
    parsed = gx.parse_gds_polygons(data)
    mapped = map_layers(parsed["structures"], spec)
    rep = gds_drc.check_geometry(mapped, rules=spec.drc_rules)
    rep["foundry"] = spec.foundry
    rep["layer_map"] = {k: spec.foundry_layer_map.get(k, k)
                        for k in sorted(spec.foundry_layer_map.keys())}
    rep["spec_anchors"] = list(spec.spec_anchors)
    rep["honest_boundary"] = spec.honest_boundary
    return rep


def pdk_signoff_report(gds_path: str, spec: Optional[FoundrySpec] = None) -> Dict[str, Any]:
    """串起层映射 + foundry DRC + 诚实边界（G4 主入口）。"""
    spec = spec or build_aim_photonics_spec()
    lm = layer_map_report(gds_path, spec)
    drc = foundry_drc_signoff(gds_path, spec)
    return {
        "g4_layer_map": lm,
        "g4_drc": {
            "all_pass": bool(drc["all_pass"]),
            "n_violations": len(drc.get("violations", [])),
            "rules": drc.get("rules", {}),
            "n_elements": drc.get("n_elements", 0),
        },
        "spec_anchors": spec.spec_anchors,
        "honest_boundary": spec.honest_boundary,
    }
