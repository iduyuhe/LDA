# -*- coding: utf-8 -*-
"""LDA L2 · S5-ext 真实 PDK 对接机制（多 foundry 注册表 + 主权 GDS 符合性校验）。

S5-ext 的 G4 增量是把「单一 AIM 公开近似 spec」升级为**真实 PDK 对接机制**：
  - 一套结构化 `FoundryPDK` 契约 schema（层栈 + 器件原语目录 + 工艺窗口字典），
    逐条 provenance 强制披露（`NDA:` 真实签约 / `public:` 近似）；
  - 已知 foundry 的**公开**工艺参数注册表（AIM / Tower / GF / IMEC 的 MPW 公开
    文档值），明确标 `public:` 非 NDA 真值；
  - 主权 GDS 对所选 PDK 契约的符合性校验（层映射 + 逐层最小特征 + 工艺窗口
    + 器件原语目录），**含反向探针**证明 PDK 替换真生效；
  - foundry 授权方把签约 NDA 真值按同 schema 注入（JSON / dict）即零改动生效。

🔴 红线 / 诚实边界（与 foundry_pdk / soc_tapeout_signoff 同源）：
  - 本项目**无任何 foundry NDA 真值**；注册表数值为「公开 MPW 文档近似 + 逐条规格锚」，
    非真实 PDK deck。本符合性校验是 LDA **主权自洽**的「PDK 契约对齐」判定，
    **不构成**真实 foundry tape-out 授权（真实授权须由各 foundry 商务签约注入 NDA PDK）。
  - 加载器强制要求 pdk.provenance 与每条 layer/primitive 的 prov 以 `NDA:` 或
    `public:` 开头，否则拒绝加载——任何 PDK 的真伪由 provenance 显式声明，不静默冒充。
  - 不 import A 级禁借求解器（Meep/Tidy3D）；能效维度不在此模块宣称。
  - 主权 GDS 未对单元做「器件原语名」标注，故「器件原语符合性」层级为
    层 + 特征级（设计所用层/特征均落在 PDK 提供原语对应层与窗口内），
    未做 per-cell 原语名一一比对（该维度显式标「未覆盖」，不静默放过）。

许可证：MIT（与 LDA 一致）。
"""
from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lda_l2 import gds_export as gx, foundry_pdk


# --------------------------------------------------------------------------
# PDK 契约 schema（逐条 provenance 强制披露）
# --------------------------------------------------------------------------
@dataclass
class PDKLayer:
    """PDK 中的一层（主权层 → foundry 层 + 工艺窗口 + 用途）。"""

    sovereign_layer: int
    foundry_layer: int
    purpose: str
    min_width_um: float
    typ_width_um: float
    max_width_um: float
    prov: str               # 必须以 NDA: 或 public: 开头


@dataclass
class PDKDevicePrimitive:
    """PDK 器件原语（目录项；公开文档可含端口/footprint，缺失则诚实标 unknown）。"""

    name: str
    purpose: str
    ports: Optional[int] = None
    bbox_um: Optional[Tuple[float, float]] = None
    prov: str = "public:unknown"


@dataclass
class FoundryPDK:
    """一个 foundry 的 PDK 契约（层栈 + 器件原语目录 + 工艺窗口 + 诚实边界）。"""

    foundry: str
    node: str
    provenance: str
    layers: List[PDKLayer]
    primitives: List[PDKDevicePrimitive] = field(default_factory=list)
    spec_anchors: List[str] = field(default_factory=list)
    honest_boundary: str = ""


# --------------------------------------------------------------------------
# provenance 护栏
# --------------------------------------------------------------------------
def _prov_ok(p: str) -> bool:
    return isinstance(p, str) and (p.startswith("NDA:") or p.startswith("public:"))


# --------------------------------------------------------------------------
# 已知 foundry 注册表（公开 MPW 文档近似 · 非 NDA 真值）
# --------------------------------------------------------------------------
def _soi_layer_block(si_fw: float, si_tw: float, si_mw: float,
                     metal_min: float, heater_min: float,
                     foundry_si: int, foundry_metal: int, foundry_heater: int,
                     foundry_m3: int, src: str) -> Tuple[List[PDKLayer], List[PDKDevicePrimitive]]:
    """构造一个典型 SOI 光子 PDK 的层栈 + 器件原语（数值为公开近似）。"""
    layers = [
        PDKLayer(1, foundry_si, "Si 波导/器件层", si_fw, si_tw, 20.0,
                 f"public:{src} Si 波导最小线宽近似"),
        PDKLayer(3, foundry_metal, "Cu metal1 布线", metal_min, 1.0, 50.0,
                 f"public:{src} metal1 最小线宽近似"),
        PDKLayer(6, foundry_heater, "TiN 热相移层", heater_min, 1.0, 5.0,
                 f"public:{src} 热相移最小线宽近似"),
        PDKLayer(9, foundry_m3, "Cu metal3 / 通孔", metal_min, 1.0, 50.0,
                 f"public:{src} metal3 最小线宽近似"),
    ]
    primitives = [
        PDKDevicePrimitive("strip_waveguide", "单模 strip 波导", None, None,
                           f"public:{src} 原语目录"),
        PDKDevicePrimitive("grating_coupler", "光栅耦合器（光纤 IO）", 1, None,
                           f"public:{src} 原语目录"),
        PDKDevicePrimitive("mzi", "Mach-Zehnder 干涉单元", 2, None,
                           f"public:{src} 原语目录"),
        PDKDevicePrimitive("thermal_phase_shifter", "热光相移器", 2, None,
                           f"public:{src} 原语目录"),
        PDKDevicePrimitive("ge_photodetector", "Ge 光电探测器", 2, None,
                           f"public:{src} 原语目录"),
        PDKDevicePrimitive("metal_pad", "金属焊盘（EIC 键合）", None, None,
                           f"public:{src} 原语目录"),
    ]
    return layers, primitives


def build_aim_photonics_pdk() -> FoundryPDK:
    """AIM Photonics 公开近似 PDK（180nm SOI，base passive/active）。

    来源：AIM Photonics 公开 PDK 页面描述的层栈架构（1 Si + 2 SiN 波导、6 implant、
    Ge PD、2 Cu wiring、Al pad）——数值为公开近似量级，非 NDA deck。
    """
    layers, primitives = _soi_layer_block(
        0.12, 0.45, 20.0, 0.20, 0.50,
        foundry_si=1, foundry_metal=10, foundry_heater=11, foundry_m3=12,
        src="AIM Photonics PDK 公开页(aimphotonics.com/services)：180nm SOI, "
            "1 Si+2 SiN 波导, Ge PD, 2 Cu wiring")
    return FoundryPDK(
        foundry="AIM Photonics(公开近似)",
        node="SOI 180nm (passive/active)",
        provenance="public:AIM Photonics 公开 PDK 文档近似（非 NDA 真值）",
        layers=layers, primitives=primitives,
        spec_anchors=[
            "AIM Photonics PDK 页面：base passive/active = 1 Si + 2 SiN 波导、"
            "6 implant、Ge PD、2 Cu wiring、Al pad",
            "AIM Photonics Active/Passive PDK v8.0（公开页面声明）",
            "层映射数值 = 公开 SOI 180nm 近似量级，非 NDA deck",
        ],
        honest_boundary=(
            "🔴 本项目**无任何 foundry NDA 真值**；本 PDK 为公开近似 + 逐条规格锚，"
            "仅用于建立「主权 GDS → foundry PDK 契约对齐」链路。真实对接须与各 "
            "foundry 商务签约（AIM/Tower/GF/IMEC），由真实 PDK 注入后替换。"),
    )


def build_tower_semiconductor_pdk() -> FoundryPDK:
    """Tower Semiconductor 公开近似 PDK（PH18 / SINTEF SiPh，180nm SOI）。

    来源：Tower PH18（原 SINTEF）180nm SOI 光子平台公开描述（220nm Si、波导、Ge PD、
    2 Cu metal、TiN heater）——数值为公开近似量级，非 NDA deck。
    """
    layers, primitives = _soi_layer_block(
        0.15, 0.50, 20.0, 0.20, 0.50,
        foundry_si=1, foundry_metal=10, foundry_heater=11, foundry_m3=12,
        src="Tower PH18(原 SINTEF) SiPh 公开描述：180nm SOI, 220nm Si, Ge PD, "
            "2 Cu metal, TiN heater")
    return FoundryPDK(
        foundry="Tower Semiconductor(公开近似)",
        node="SOI 180nm (PH18 SiPh)",
        provenance="public:Tower PH18 公开平台文档近似（非 NDA 真值）",
        layers=layers, primitives=primitives,
        spec_anchors=[
            "Tower PH18 SiPh 平台公开描述：180nm SOI、220nm Si 波导、Ge PD、"
            "2 Cu metal level、TiN heater",
            "层映射数值 = 公开 PH18 近似量级，非 NDA deck",
        ],
        honest_boundary=(
            "🔴 本项目**无任何 foundry NDA 真值**；本 PDK 为公开近似 + 逐条规格锚，"
            "真实对接须 Tower 商务签约注入 NDA PDK 替换。"),
    )


def build_globalfoundries_pdk() -> FoundryPDK:
    """GlobalFoundries 公开近似 PDK（90WG / 45SPCLO SiPh，90nm SOI 光子）。

    来源：GF 90WG / 45SPCLO 硅光子平台公开描述（90nm SOI、波导、Ge PD）——数值为
    公开近似量级，非 NDA deck。
    """
    layers, primitives = _soi_layer_block(
        0.10, 0.40, 20.0, 0.18, 0.45,
        foundry_si=1, foundry_metal=10, foundry_heater=11, foundry_m3=12,
        src="GlobalFoundries 90WG/45SPCLO SiPh 公开描述：90nm SOI, 波导, Ge PD")
    return FoundryPDK(
        foundry="GlobalFoundries(公开近似)",
        node="SOI 90nm (90WG/45SPCLO SiPh)",
        provenance="public:GF 90WG/45SPCLO 公开平台文档近似（非 NDA 真值）",
        layers=layers, primitives=primitives,
        spec_anchors=[
            "GF 90WG / 45SPCLO 硅光子平台公开描述：90nm SOI、波导、Ge PD",
            "层映射数值 = 公开 90nm SiPh 近似量级，非 NDA deck",
        ],
        honest_boundary=(
            "🔴 本项目**无任何 foundry NDA 真值**；本 PDK 为公开近似 + 逐条规格锚，"
            "真实对接须 GF 商务签约注入 NDA PDK 替换。"),
    )


def build_imec_pdk() -> FoundryPDK:
    """imec 公开近似 PDK（ISIPP50G，220nm Si，50G 光子平台）。

    来源：imec ISIPP50G 公开描述（220nm Si 线波导、Ge PD、TiN heater、3 metal
    level）——数值为公开近似量级，非 NDA deck。
    """
    layers, primitives = _soi_layer_block(
        0.12, 0.45, 20.0, 0.20, 0.50,
        foundry_si=1, foundry_metal=10, foundry_heater=11, foundry_m3=12,
        src="imec ISIPP50G 公开描述：220nm Si 线波导, Ge PD, TiN heater, 3 metal")
    return FoundryPDK(
        foundry="imec(公开近似)",
        node="SOI 220nm (ISIPP50G)",
        provenance="public:imec ISIPP50G 公开平台文档近似（非 NDA 真值）",
        layers=layers, primitives=primitives,
        spec_anchors=[
            "imec ISIPP50G 平台公开描述：220nm Si 线波导、Ge PD、TiN heater、3 metal level",
            "层映射数值 = 公开 ISIPP50G 近似量级，非 NDA deck",
        ],
        honest_boundary=(
            "🔴 本项目**无任何 foundry NDA 真值**；本 PDK 为公开近似 + 逐条规格锚，"
            "真实对接须 imec 商务签约注入 NDA PDK 替换。"),
    )


# 已知 foundry 注册表
REGISTRY: Dict[str, Any] = {
    "AIM Photonics": build_aim_photonics_pdk,
    "Tower Semiconductor": build_tower_semiconductor_pdk,
    "GlobalFoundries": build_globalfoundries_pdk,
    "imec": build_imec_pdk,
}
DEFAULT_PDK_NAME = "AIM Photonics"


def get_pdk(name: Optional[str] = None) -> FoundryPDK:
    name = name or DEFAULT_PDK_NAME
    if name not in REGISTRY:
        raise KeyError(f"未知 foundry：{name}（已知：{sorted(REGISTRY)}）")
    return REGISTRY[name]()


def pdk_registry_names() -> List[str]:
    return sorted(REGISTRY)


# --------------------------------------------------------------------------
# PDK → FoundrySpec（复用 G4 层映射）
# --------------------------------------------------------------------------
def convert_pdk_to_spec(pdk: FoundryPDK) -> foundry_pdk.FoundrySpec:
    """由 PDK 层栈派生 G4 FoundrySpec（供 foundry_pdk.layer_map_report 复用）。"""
    fmap = {L.sovereign_layer: L.foundry_layer for L in pdk.layers}
    mw = min(L.min_width_um for L in pdk.layers)
    return foundry_pdk.FoundrySpec(
        foundry=pdk.foundry,
        node=pdk.node,
        foundry_layer_map=fmap,
        drc_rules={"min_width_um": mw, "min_spacing_um": mw, "min_area_um2": 0.04},
        spec_anchors=list(pdk.spec_anchors),
        honest_boundary=pdk.honest_boundary,
    )


# --------------------------------------------------------------------------
# 加载器（foundry 授权方注入 NDA PDK）
# --------------------------------------------------------------------------
def load_foundry_pdk(path_or_dict: Any) -> FoundryPDK:
    """加载一个 foundry PDK（JSON 文件路径或已解析 dict），并强制诚实披露。

    🔴 诚实护栏：pdk.provenance 与每条 layer.prov / primitive.prov 必须以 `NDA:`
    （真实签约 PDK）或 `public:`（近似）开头，否则拒绝加载——杜绝静默冒充 NDA。
    """
    raw = path_or_dict
    if isinstance(raw, str):
        if not os.path.exists(raw):
            raise FileNotFoundError(f"foundry PDK 文件未找到：{raw}")
        with open(raw, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    if not isinstance(raw, dict):
        raise TypeError("foundry PDK 必须是 dict 或 JSON 文件路径")

    provenance = raw.get("provenance", "")
    if not _prov_ok(provenance):
        raise ValueError(
            f"pdk.provenance 必须以 'NDA:'（真实签约 PDK）或 'public:'（近似）开头，"
            f"强制诚实披露；收到：{provenance!r}")

    layers_raw = raw.get("layers", [])
    if not layers_raw:
        raise ValueError("pdk.layers 为空：PDK 必须至少含 1 层")
    layers: List[PDKLayer] = []
    for lr in layers_raw:
        prov = lr.get("prov", "")
        if not _prov_ok(prov):
            raise ValueError(
                f"层 {lr.get('sovereign_layer')!r} 的 prov 必须以 'NDA:' 或 'public:' 开头；"
                f"收到：{prov!r}")
        layers.append(PDKLayer(
            sovereign_layer=int(lr["sovereign_layer"]),
            foundry_layer=int(lr["foundry_layer"]),
            purpose=str(lr["purpose"]),
            min_width_um=float(lr["min_width_um"]),
            typ_width_um=float(lr["typ_width_um"]),
            max_width_um=float(lr["max_width_um"]),
            prov=str(prov),
        ))
    prims_raw = raw.get("primitives", [])
    prims: List[PDKDevicePrimitive] = []
    for pr in prims_raw:
        prov = pr.get("prov", "public:unknown")
        if not _prov_ok(prov):
            raise ValueError(
                f"原语 {pr.get('name')!r} 的 prov 必须以 'NDA:' 或 'public:' 开头；"
                f"收到：{prov!r}")
        prims.append(PDKDevicePrimitive(
            name=str(pr["name"]),
            purpose=str(pr["purpose"]),
            ports=pr.get("ports"),
            bbox_um=tuple(pr["bbox_um"]) if pr.get("bbox_um") else None,
            prov=str(prov),
        ))
    return FoundryPDK(
        foundry=str(raw.get("foundry", "unnamed-pdk")),
        node=str(raw.get("node", "")),
        provenance=str(provenance),
        layers=layers, primitives=prims,
        spec_anchors=list(raw.get("spec_anchors", [])),
        honest_boundary=str(raw.get("honest_boundary", "")),
    )


# --------------------------------------------------------------------------
# 特征宽度提取 + 逐层符合性
# --------------------------------------------------------------------------
def _feature_width_um(e: Dict[str, Any]) -> Optional[float]:
    """取一个元素的「特征宽度」µm：PATH 用 width；BOUNDARY 用 bbox 短边。"""
    if e.get("kind") == "path" and e.get("width") is not None:
        return float(e["width"])
    pts = e.get("points_um") or []
    if len(pts) < 2:
        return 0.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    return min(w, h)


def pdk_conformance_report(gds_path: str, pdk: FoundryPDK) -> Dict[str, Any]:
    """主权 GDS → 所选 PDK 契约符合性校验（层映射 + 逐层最小特征 + 工艺窗口）。

    返回：
      - all_mapped: 主权层 ⊆ PDK 支持层
      - per_layer: 每层 min_feature_ok（最小特征 ≥ PDK min_width）+ 工艺窗口观测
      - primitive_catalog: PDK 器件原语目录（信息）+ 设计需求层齐备性
      - conformant: all_mapped 且所有 per_layer.min_feature_ok
      - honest_boundary: 随 PDK 来源改写
    """
    spec = convert_pdk_to_spec(pdk)
    lm = foundry_pdk.layer_map_report(gds_path, spec)

    data = open(gds_path, "rb").read()
    parsed = gx.parse_gds_polygons(data)
    # 仅取顶层结构（避免 cell 自身结构被重复计入；与 gds_drc 口径一致）
    referenced = {el.get("sname") for v in parsed["structures"].values()
                  for el in v if el.get("kind") in ("sref", "aref")}
    top_structures = [n for n in parsed["structures"] if n not in referenced] or \
        list(parsed["structures"].keys())
    top_elems = [e for s in top_structures for e in parsed["structures"][s]]

    layer_by_sov: Dict[int, List[float]] = {}
    for e in top_elems:
        fw = _feature_width_um(e)
        if fw is None:
            continue
        layer_by_sov.setdefault(e.get("layer"), []).append(fw)

    per_layer = []
    all_min_ok = True
    for L in pdk.layers:
        widths = layer_by_sov.get(L.sovereign_layer, [])
        if not widths:
            per_layer.append({
                "sovereign_layer": L.sovereign_layer,
                "foundry_layer": L.foundry_layer,
                "purpose": L.purpose,
                "n_elements": 0,
                "min_obs_um": None,
                "typ_obs_um": None,
                "max_obs_um": None,
                "min_width_um": L.min_width_um,
                "max_width_um": L.max_width_um,
                "min_feature_ok": True,
                "over_max_window": False,
                "detail": "该层无元素（规则不适用，判通过）",
            })
            continue
        mn, mx = min(widths), max(widths)
        typ = sum(widths) / len(widths)
        min_ok = mn >= L.min_width_um
        over_max = mx > L.max_width_um
        all_min_ok = all_min_ok and min_ok
        per_layer.append({
            "sovereign_layer": L.sovereign_layer,
            "foundry_layer": L.foundry_layer,
            "purpose": L.purpose,
            "n_elements": len(widths),
            "min_obs_um": round(mn, 4),
            "typ_obs_um": round(typ, 4),
            "max_obs_um": round(mx, 4),
            "min_width_um": L.min_width_um,
            "max_width_um": L.max_width_um,
            "min_feature_ok": bool(min_ok),
            "over_max_window": bool(over_max),
            "detail": (
                f"min_obs={mn:.4f}≥min={L.min_width_um}→{'OK' if min_ok else 'FAIL'};"
                + ("" if not over_max else
                   f" max_obs={mx:.4f}>max={L.max_width_um}（宽线/焊盘，按设计允许，仅信息）")),
        })

    # 器件原语目录：信息级（主权 GDS 未做 per-cell 原语名标注，显式标未覆盖）
    need_purposes = {"Si 波导/器件层", "Cu metal1 布线", "TiN 热相移层"}
    offered = {L.purpose for L in pdk.layers}
    primitive_ready = need_purposes.issubset(offered)
    conformant = bool(lm["all_mapped"] and all_min_ok and primitive_ready)

    return {
        "gds_path": gds_path,
        "foundry": pdk.foundry,
        "node": pdk.node,
        "pdk_provenance": pdk.provenance,
        "all_mapped": bool(lm["all_mapped"]),
        "unmapped_layers": lm["unmapped_layers"],
        "per_layer": per_layer,
        "n_layers_checked": len(per_layer),
        "primitive_catalog": [
            {"name": p.name, "purpose": p.purpose, "ports": p.ports,
             "bbox_um": p.bbox_um, "prov": p.prov}
            for p in pdk.primitives],
        "primitive_ready": bool(primitive_ready),
        "conformant": conformant,
        "honest_boundary": pdk.honest_boundary + (
            " 器件原语符合性为层 + 特征级（主权 GDS 未做 per-cell 原语名标注），"
            "per-cell 原语名比对显式标未覆盖。"),
    }


def pdk_conformance_markdown(rep: Dict[str, Any]) -> str:
    L = []
    L.append("### 主权 GDS → foundry PDK 契约符合性（S5-ext 真实 PDK 对接）")
    L.append("")
    L.append(f"- foundry：`{rep['foundry']}` · node：`{rep['node']}`")
    L.append(f"- GDS：`{rep['gds_path']}`")
    L.append(f"- PDK provenance：`{rep['pdk_provenance']}`")
    L.append(f"- 层映射全部可达：{rep['all_mapped']}（越界层：{rep['unmapped_layers']}）")
    L.append(f"- **conformant = {rep['conformant']}** · primitive_ready = {rep['primitive_ready']}")
    L.append("")
    L.append("| 主权层 | foundry层 | 用途 | 元素数 | min观测(µm) | typ观测 | max观测 | PDK min | PDK max | 最小特征 | 细节 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rep["per_layer"]:
        mn = "—" if r["min_obs_um"] is None else f"{r['min_obs_um']:.4f}"
        ty = "—" if r["typ_obs_um"] is None else f"{r['typ_obs_um']:.4f}"
        mx = "—" if r["max_obs_um"] is None else f"{r['max_obs_um']:.4f}"
        ok = "✅" if r["min_feature_ok"] else "❌"
        L.append(f"| {r['sovereign_layer']} | {r['foundry_layer']} | {r['purpose']} | "
                 f"{r['n_elements']} | {mn} | {ty} | {mx} | {r['min_width_um']} | "
                 f"{r['max_width_um']} | {ok} | {r['detail']} |")
    L.append("")
    L.append("*器件原语目录（PDK 提供）：*")
    for p in rep["primitive_catalog"]:
        L.append(f"- {p['name']}（{p['purpose']}）· ports={p['ports']} · prov={p['prov']}")
    L.append("")
    L.append(f"*诚实边界：{rep['honest_boundary']}*")
    return "\n".join(L)
