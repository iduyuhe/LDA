# -*- coding: utf-8 -*-
"""LDA L2 · 主权 GDS → foundry DRC 闭集 / NDA deck 替换 流片 signoff（G6 收官增量）。

在 G4「foundry PDK 对接层」(foundry_pdk.py) 之上：
  - 默认：把 foundry DRC 视为**显式闭集**（有限、可枚举、逐项规格锚登记），
    输出 LDA 主权自洽的「可制造性就绪」判定。
  - 扩展：支持**真实 foundry NDA deck 替换闭集**——通过 `load_foundry_deck`
    加载 foundry 授权方按本 schema 注入的签约 deck（JSON），signoff 即真走该
    deck 的规则与逐项 provenance，而非默认值。

🔴 红线 / 诚实边界（与 foundry_pdk 同源，逐字强化）：
  - 本项目**无任何 foundry NDA 真值**；闭集规则数值为「公开近似 + 逐条规格锚」，
    非真实 PDK deck。本 signoff 是 LDA **主权自洽**的「可制造性就绪」判定，
    **不构成**真实 foundry tape-out 授权。
  - NDA deck 替换机制**只提供替换能力**，绝不伪造 NDA 数值：加载器强制要求
    deck 级与每条规则的 `provenance` 以 `NDA:`（真实签约 deck）或 `public:`
    （近似）开头，否则拒绝加载——任何 deck 的真伪由 provenance 显式声明，
    不静默冒充 NDA。
  - 闭集 = 本模块显式枚举的有限规则集合（见 build_closed_set_deck）；任何未列入
    闭集（或替换 deck 未覆盖）的 foundry 规则（密度 / 天线 / 阱邻近 / 金属填充 /
    封装余量等）均**显式标未覆盖**，不静默放过。
  - 不 import A 级禁借求解器（Meep/Tidy3D）；能效维度不在此模块宣称。
  - 真实流片须由各 foundry 商务签约，由授权方提供 deck 文件（设 `LDA_FOUNDRY_DECK`
    环境变量或显式传入 `deck=`），替换本闭集。

许可证：MIT（与 LDA 一致）。
"""
from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lda_l2 import gds_drc, gds_export as gx, foundry_pdk, soc_design_package as sdp


# 真实 foundry NDA deck 注入入口：foundry 授权方把签约 deck JSON 置于此路径并设该环境变量，
# tapeout_signoff_report(..., auto_env=True) 即自动加载并替换闭集。
ENV_DECK_VAR = "LDA_FOUNDRY_DECK"


@dataclass
class FoundryDRCRule:
    """闭集 / 替换 deck 中的一条 foundry DRC 规则（显式、可枚举、带规格锚）。

    与 gds_drc.check_geometry 的「开放几何窗口」不同，本类把每条规则**显式命名**
    登记进闭集，使「到底查了哪些 foundry 规则」对用户完全透明（非黑盒快查）。
    """

    rid: str                 # 规则 ID，如 FDRC-W-SI-MINWIDTH
    foundry_layer: int      # foundry 层号（映射后）；layer_allowed 用 -1 表示全层
    layer_name: str         # 层语义名（SI / METAL / HEATER / M3 / ALL）
    kind: str               # min_width | min_spacing | min_area | layer_allowed
    thr_um: float           # 阈值（µm）；layer_allowed 存「允许层数」仅作展示
    prov: str               # 规格锚来源 / 近似口径；必须以 NDA: 或 public: 开头


@dataclass
class FoundryDeck:
    """一个可替换闭集的 foundry DRC deck（闭集本身即一种 deck，NDA deck 是另一种）。

    provenance 与每条 rule.prov 强制诚实披露：'NDA:...' = 真实签约 deck；
    'public:...' = 近似（含闭集与模板）。加载器拒绝无此前缀的 deck。
    """

    name: str
    node: str
    provenance: str
    rules: List[FoundryDRCRule]
    spec_anchors: List[str] = field(default_factory=list)


def build_closed_set_deck(spec: foundry_pdk.FoundrySpec) -> List[FoundryDRCRule]:
    """由 foundry spec 派生显式闭集规则牌（每层 min_width/spacing/area + 层集允许）。

    阈值取 spec.drc_rules 同量级（公开 SOI 180nm 近似），逐层登记规格锚。
    """
    r = spec.drc_rules
    mw, ms, ma = r["min_width_um"], r["min_spacing_um"], r["min_area_um2"]
    # 主权层 → foundry 层（spec.foundry_layer_map）
    layer_pairs = [
        ("SI", spec.foundry_layer_map.get(1, 1)),
        ("METAL", spec.foundry_layer_map.get(3, 3)),
        ("HEATER", spec.foundry_layer_map.get(6, 6)),
        ("M3", spec.foundry_layer_map.get(9, 9)),
    ]
    deck: List[FoundryDRCRule] = []
    anchor0 = "; ".join(spec.spec_anchors[:1]) if spec.spec_anchors else "公开近似"
    for name, fl in layer_pairs:
        prov = (f"public:{spec.foundry} {spec.node} 公开近似最小几何窗口"
                f"（非 NDA 真值；来源：{anchor0}）")
        deck.append(FoundryDRCRule(f"FDRC-W-{name}-MINWIDTH", fl, name,
                                   "min_width", mw, prov))
        deck.append(FoundryDRCRule(f"FDRC-S-{name}-MINSPACE", fl, name,
                                   "min_spacing", ms, prov))
        deck.append(FoundryDRCRule(f"FDRC-A-{name}-MINAREA", fl, name,
                                   "min_area", ma, prov))
    # 层集允许（闭集核心：只允许 foundry 层号落在映射闭集内）
    allowed = sorted(set(spec.foundry_layer_map.values()))
    deck.append(FoundryDRCRule(
        "FDRC-LAYER-ALLOWED", -1, "ALL", "layer_allowed",
        float(len(allowed)),
        f"public:闭集允许层号 = {allowed}（主权→foundry 映射闭集；任何越界层显式判违规，不静默放过）"))
    return deck


def _prov_ok(p: str) -> bool:
    """provenance 必须以 NDA: 或 public: 开头，强制诚实披露。"""
    return isinstance(p, str) and (p.startswith("NDA:") or p.startswith("public:"))


def load_foundry_deck(path_or_dict: Any) -> FoundryDeck:
    """加载一个 foundry DRC deck（JSON 文件路径或已解析 dict），并强制诚实披露。

    🔴 诚实护栏：deck.provenance 与每条 rule.prov 必须以 `NDA:`（真实签约 deck）
    或 `public:`（近似）开头，否则拒绝加载——杜绝静默冒充 NDA 的假 deck。

    入参：
      - 字符串：视为 JSON 文件路径（必须存在）。
      - dict：已解析的 deck 结构（同 JSON schema）。
    返回：FoundryDeck（rules 为 FoundryDRCRule 列表）。
    """
    raw = path_or_dict
    if isinstance(raw, str):
        if not os.path.exists(raw):
            raise FileNotFoundError(f"foundry deck 文件未找到：{raw}")
        with open(raw, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    if not isinstance(raw, dict):
        raise TypeError("foundry deck 必须是 dict 或 JSON 文件路径")

    provenance = raw.get("provenance", "")
    if not _prov_ok(provenance):
        raise ValueError(
            f"deck.provenance 必须以 'NDA:'（真实签约 deck）或 'public:'（近似）开头，"
            f"强制诚实披露；收到：{provenance!r}")

    rules_raw = raw.get("rules", [])
    if not rules_raw:
        raise ValueError("deck.rules 为空：闭集/替换 deck 必须至少含 1 条规则")

    rules: List[FoundryDRCRule] = []
    for rr in rules_raw:
        prov = rr.get("prov", "")
        if not _prov_ok(prov):
            raise ValueError(
                f"规则 {rr.get('rid')!r} 的 prov 必须以 'NDA:' 或 'public:' 开头，"
                f"强制逐条诚实披露；收到：{prov!r}")
        rules.append(FoundryDRCRule(
            rid=str(rr["rid"]),
            foundry_layer=int(rr["foundry_layer"]),
            layer_name=str(rr["layer_name"]),
            kind=str(rr["kind"]),
            thr_um=float(rr["thr_um"]) if rr.get("thr_um") is not None else 0.0,
            prov=str(prov),
        ))
    return FoundryDeck(
        name=str(raw.get("name", "unnamed-deck")),
        node=str(raw.get("node", "")),
        provenance=str(provenance),
        rules=rules,
        spec_anchors=list(raw.get("spec_anchors", [])),
    )


def _run_one_rule(structures: Dict[str, List[Dict]], rule: FoundryDRCRule,
                  allowed_layers: List[int]) -> Dict[str, Any]:
    """对单条规则做判定，返回 {rid, kind, layer, thr_um, prov, pass, detail}。

    几何类规则：把 structures 过滤到该 foundry 层，调 gds_drc.check_geometry，
    仅启用对应 kind 的阈值（其余置 0 使该维度恒通过），取对应标志位。
    """
    if rule.kind == "layer_allowed":
        present = set()
        for elems in structures.values():
            for e in elems:
                present.add(e.get("layer"))
        bad = sorted(present - set(allowed_layers))
        return {
            "rid": rule.rid, "kind": rule.kind, "layer": "ALL",
            "thr_um": None, "prov": rule.prov, "pass": len(bad) == 0,
            "detail": (f"present_layers={sorted(present)}; allowed={allowed_layers}"
                       + ("" if not bad else f"; 越界层={bad}")),
        }
    # 几何规则：过滤到该 foundry 层
    sub = {s: [e for e in elems if e.get("layer") == rule.foundry_layer]
           for s, elems in structures.items()}
    sub = {s: v for s, v in sub.items() if v}
    if not sub:
        return {"rid": rule.rid, "kind": rule.kind, "layer": rule.foundry_layer,
                "thr_um": rule.thr_um, "prov": rule.prov, "pass": True,
                "detail": "该层无元素（规则不适用，判通过）"}
    rep = gds_drc.check_geometry(sub, rules={
        "min_width_um": rule.thr_um if rule.kind == "min_width" else 0.0,
        "min_spacing_um": rule.thr_um if rule.kind == "min_spacing" else 0.0,
        "min_area_um2": rule.thr_um if rule.kind == "min_area" else 0.0,
    })
    flag = {"min_width": rep["min_width_ok"], "min_spacing": rep["min_spacing_ok"],
            "min_area": rep["min_area_ok"]}[rule.kind]
    n_v = {"min_width": rep["n_width_violations"],
           "min_spacing": rep["n_spacing_violations"],
           "min_area": rep["n_area_violations"]}[rule.kind]
    return {"rid": rule.rid, "kind": rule.kind, "layer": rule.foundry_layer,
            "thr_um": rule.thr_um, "prov": rule.prov, "pass": bool(flag),
            "detail": f"n_violations={n_v}; n_elements={rep['n_elements']}"}


def tapeout_signoff_report(gds_path: Optional[str] = None,
                           N: Optional[int] = None,
                           spec: Optional[foundry_pdk.FoundrySpec] = None,
                           deck: Optional[FoundryDeck] = None,
                           auto_env: bool = False
                           ) -> Dict[str, Any]:
    """主权 GDS → foundry DRC 闭集 / NDA deck 替换 流片 signoff 主入口。

    决策顺序（deck 解析）：
      1. 显式 `deck=` → 直接用该 deck（真实 NDA deck 或近似 deck 均可）。
      2. 否则若 `auto_env=True` 且 `LDA_FOUNDRY_DECK` 指向存在文件 → 加载该 deck。
      3. 否则 → 用本模块显式枚举的闭集（公开近似，非 NDA）。

    gds_path 与 N 二选一：给 N 时若 gds_path 缺失则惰性 build_soc_gds(N) 生成。
    返回 per_rule 判定（含逐条 prov）+ signoff_ready + 层映射 + deck 来源 + 诚实边界。

    🔴 诚实边界：signoff_ready=True 仅代表「主权 GDS 满足所用 deck 的规则」；
    若来源为闭集/近似 deck 则**不构成**真实 foundry tape-out 授权；真实授权须
    由 foundry 签约 deck（provenance 以 NDA: 开头）注入替换。
    """
    spec = spec or foundry_pdk.build_aim_photonics_spec()
    if gds_path is None:
        if N is None:
            raise ValueError("gds_path 与 N 至少给一个")
        built = sdp.build_soc_gds(N)
        gds_path = built["gds_path"]

    # —— deck 解析（替换机制核心）——
    if deck is None and auto_env:
        envp = os.environ.get(ENV_DECK_VAR)
        if envp and os.path.exists(envp):
            deck = load_foundry_deck(envp)
    if deck is None:
        deck_rules = build_closed_set_deck(spec)
        deck_source = "closed-set-public-approx"
        deck_provenance = ("public:本模块显式枚举有限规则（公开近似+逐条规格锚），"
                           "非 NDA deck")
        deck_anchors = list(spec.spec_anchors)
    else:
        deck_rules = deck.rules
        deck_source = deck.name
        deck_provenance = deck.provenance
        deck_anchors = list(deck.spec_anchors)

    data = open(gds_path, "rb").read()
    parsed = gx.parse_gds_polygons(data)
    mapped = foundry_pdk.map_layers(parsed["structures"], spec)
    allowed = sorted(set(spec.foundry_layer_map.values()))
    per_rule = [_run_one_rule(mapped, r, allowed) for r in deck_rules]
    n_pass = sum(1 for r in per_rule if r["pass"])
    signoff_ready = (n_pass == len(per_rule))
    lm = foundry_pdk.layer_map_report(gds_path, spec)
    n_total_elems = sum(len(elems) for elems in parsed["structures"].values())
    return {
        "gds_path": gds_path,
        "foundry": spec.foundry,
        "node": spec.node,
        "deck_source": deck_source,
        "deck_provenance": deck_provenance,
        "closed_set_size": len(deck_rules),
        "per_rule": per_rule,
        "n_rules_pass": n_pass,
        "n_rules_total": len(deck_rules),
        "signoff_ready": signoff_ready,
        "layer_map": lm["layer_map"],
        "all_mapped": lm["all_mapped"],
        "n_structures": lm["n_structures"],
        "n_elements": n_total_elems,
        "spec_anchors": deck_anchors,
        "honest_boundary": (
            f"🔴 所用 deck 来源 = {deck_source}（provenance: {deck_provenance}）。"
            "若来源为闭集/近似 deck，本 signoff 仅代表「主权 GDS 满足该 deck 规则」，"
            "**不构成**真实 foundry tape-out 授权；未列入该 deck 的 foundry 规则"
            "（密度 / 天线 / 阱邻近 / 金属填充 / 封装余量等）一律显式标未覆盖。"
            "真实流片须由各 foundry 商务签约，提供 provenance 以 'NDA:' 开头的签约"
            "deck 替换本闭集。"
        ),
    }


def tapeout_signoff_markdown(rep: Dict[str, Any]) -> str:
    """把 signoff 报告渲染为 Markdown（含 deck 来源 / 逐条规则 + provenance + 诚实边界）。"""
    L = []
    L.append("### 主权 GDS → foundry DRC 流片 signoff（含 NDA deck 替换）")
    L.append("")
    L.append(f"- foundry：`{rep['foundry']}` · node：`{rep['node']}`")
    L.append(f"- GDS：`{rep['gds_path']}`")
    L.append(f"- **deck 来源**：`{rep['deck_source']}`")
    L.append(f"- deck provenance：`{rep['deck_provenance']}`")
    L.append(f"- 规则：**{rep['n_rules_pass']}/{rep['n_rules_total']}** 通过"
             f" · signoff_ready = **{rep['signoff_ready']}**")
    L.append(f"- 层映射全部可达：{rep['all_mapped']} · 结构数：{rep['n_structures']}"
             f" · 元素数：{rep['n_elements']}")
    L.append("")
    L.append("| 规则 ID | 层 | 类型 | 阈值(µm) | 来源 | 结果 | 细节 |")
    L.append("|---|---|---|---|---|---|---|")
    for r in rep["per_rule"]:
        thr = "—" if r["thr_um"] is None else f"{r['thr_um']:.3f}"
        res = "✅" if r["pass"] else "❌"
        L.append(f"| {r['rid']} | {r['layer']} | {r['kind']} | {thr} | {r['prov']} | {res} | {r['detail']} |")
    L.append("")
    L.append("*规格锚：*")
    for a in rep["spec_anchors"]:
        L.append(f"- {a}")
    L.append("")
    L.append(f"*诚实边界：{rep['honest_boundary']}*")
    return "\n".join(L)
