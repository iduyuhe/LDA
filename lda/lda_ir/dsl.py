"""LDA L0 · IR 序列化（机器优先）+ 可读渲染。

机器优先原则（《白皮书》人机协作哲学）：
  - to_dict() / from_dict() ：纯 dict ↔ IRModel 双向 round-trip，零信息损失，
    可直接 json.dumps 后经 L1 MCP 传输、落库、做 diff。这是 agent 间 / agent
    与内核间的"机器语言"。
  - to_dsl()                ：单向人类可读渲染（缩进行式），仅用于调试展示 /
    人审 IR，不用于回灌（避免脆弱 parser 引入 bug）。

整个模块零外部依赖，只 import 标准库 json 与本包 core。
"""
from __future__ import annotations

import json
from typing import Any, Dict

from .core import (
    Component, FoundryPlan, IRModel, Net, ObjectiveSpec, Port, SpectrumSpec,
)


# --------------------------------------------------------------------------
# 机器优先：dict 序列化（round-trip）
# --------------------------------------------------------------------------
def _port_to_dict(p: Port) -> Dict[str, Any]:
    return {"name": p.name, "directed": p.directed}


def _port_from_dict(d: Dict[str, Any]) -> Port:
    return Port(name=d["name"], directed=d.get("directed", False))


def _net_to_dict(n: Net) -> Dict[str, Any]:
    return {"id": n.id, "connects": list(n.connects)}


def _net_from_dict(d: Dict[str, Any]) -> Net:
    return Net(id=d["id"], connects=list(d.get("connects", [])))


def _obj_to_dict(o: ObjectiveSpec) -> Dict[str, Any]:
    return {"bid": o.bid, "weight": o.weight, "target": o.target,
            "tol": o.tol, "role": o.role}


def _obj_from_dict(d: Dict[str, Any]) -> ObjectiveSpec:
    return ObjectiveSpec(bid=d["bid"], weight=d.get("weight", 1.0),
                         target=d.get("target", 0.0), tol=d.get("tol", 0.05),
                         role=d.get("role", "objective"))


def _spec_to_dict(s: SpectrumSpec) -> Dict[str, Any]:
    return {"kind": s.kind, "target_fsr_nm": s.target_fsr_nm,
            "wl0_um": s.wl0_um, "n_g": s.n_g, "primary_param": s.primary_param}


def _spec_from_dict(d: Dict[str, Any]) -> SpectrumSpec:
    return SpectrumSpec(kind=d.get("kind", "ring_fsr"),
                        target_fsr_nm=d.get("target_fsr_nm", 9.15),
                        wl0_um=d.get("wl0_um", 1.55),
                        n_g=d.get("n_g", 4.2),
                        primary_param=d.get("primary_param", "R"))


def _plan_to_dict(f: FoundryPlan) -> Dict[str, Any]:
    return {"mode": f.mode, "foundries": list(f.foundries)}


def _plan_from_dict(d: Dict[str, Any]) -> FoundryPlan:
    return FoundryPlan(mode=d.get("mode", "all"),
                       foundries=list(d.get("foundries", [])))


def _comp_to_dict(c: Component) -> Dict[str, Any]:
    d = {
        "id": c.id, "kind": c.kind,
        "params": dict(c.params),
        "param_bounds": {k: list(v) for k, v in c.param_bounds.items()},
        "ports": [_port_to_dict(p) for p in c.ports],
        "foundry_hints": list(c.foundry_hints),
    }
    # D-40 physics 一等字段（标准化定稿 D-76：物理锚必须经 round-trip 保留，
    # 否则 agent 间传递 IR 会丢"锚定的物理定律"，下游验证裁判失去判据）
    if c.physics is not None:
        d["physics"] = {
            "bid": c.physics.bid,
            "kind": c.physics.kind,
            "spec_params": dict(c.physics.spec_params),
            "anchor": c.physics.anchor,
        }
    return d


def _comp_from_dict(d: Dict[str, Any]) -> Component:
    comp = Component(
        id=d["id"], kind=d["kind"],
        params=dict(d.get("params", {})),
        param_bounds={k: tuple(v) for k, v in d.get("param_bounds", {}).items()},
        ports=[_port_from_dict(p) for p in d.get("ports", [])],
        foundry_hints=list(d.get("foundry_hints", [])),
    )
    ph = d.get("physics")
    if ph:
        from .core import PhysicsAnchor
        comp.physics = PhysicsAnchor(
            bid=ph["bid"], kind=ph.get("kind", ""),
            spec_params=dict(ph.get("spec_params", {})),
            anchor=ph.get("anchor", ""))
    return comp


def to_dict(m: IRModel) -> Dict[str, Any]:
    """IRModel → 纯 dict（机器优先，可 json.dumps）。"""
    return {
        "schema_version": m.schema_version,
        "domain": m.domain,
        "name": m.name,
        "components": [_comp_to_dict(c) for c in m.components],
        "nets": [_net_to_dict(n) for n in m.nets],
        "pdk_ref": m.pdk_ref,
        "foundry_plan": _plan_to_dict(m.foundry_plan) if m.foundry_plan else None,
        "objectives": [_obj_to_dict(o) for o in m.objectives],
        "spectrum": _spec_to_dict(m.spectrum) if m.spectrum else None,
        "notes": m.notes,
    }


def from_dict(d: Dict[str, Any]) -> IRModel:
    """纯 dict → IRModel（round-trip，零信息损失）。"""
    return IRModel(
        schema_version=d.get("schema_version", "0.1"),
        domain=d.get("domain", "photon"),
        name=d.get("name", ""),
        components=[_comp_from_dict(c) for c in d.get("components", [])],
        nets=[_net_from_dict(n) for n in d.get("nets", [])],
        pdk_ref=d.get("pdk_ref"),
        foundry_plan=_plan_from_dict(d["foundry_plan"]) if d.get("foundry_plan") else None,
        objectives=[_obj_from_dict(o) for o in d.get("objectives", [])],
        spectrum=_spec_from_dict(d["spectrum"]) if d.get("spectrum") else None,
        notes=d.get("notes", ""),
    )


def dumps(m: IRModel) -> str:
    """直接产出 JSON 字符串（agent 间传递的标准机器语言）。"""
    return json.dumps(to_dict(m), ensure_ascii=False, indent=2)


def loads(s: str) -> IRModel:
    return from_dict(json.loads(s))


# --------------------------------------------------------------------------
# 人类可读渲染（单向，仅调试/展示）
# --------------------------------------------------------------------------
def to_dsl(m: IRModel) -> str:
    """把 IR 渲染为缩进可读文本（便于人审，不回灌）。"""
    L: List[str] = []
    L.append(f'ir LDA-IR/{m.schema_version} {m.domain} "{m.name}"')
    if m.pdk_ref:
        L.append(f"pdk_ref {m.pdk_ref}")
    for c in m.components:
        L.append(f"component {c.id} {c.kind}")
        for k, v in c.params.items():
            b = c.param_bounds.get(k)
            if b is not None:
                L.append(f"  param {k}={v} bounds({b[0]},{b[1]})")
            else:
                L.append(f"  param {k}={v}")
        if c.ports:
            L.append("  port " + " ".join(p.name for p in c.ports))
        for fh in c.foundry_hints:
            L.append(f"  hint {fh}")
    for n in m.nets:
        L.append(f"net {n.id} " + " ".join(n.connects))
    for o in m.objectives:
        L.append(f"{o.role} {o.bid} weight={o.weight} target={o.target} tol={o.tol}")
    if m.spectrum:
        s = m.spectrum
        L.append(f"spectrum {s.kind} target_fsr_nm={s.target_fsr_nm} "
                 f"wl0_um={s.wl0_um} n_g={s.n_g} primary_param={s.primary_param}")
    if m.foundry_plan:
        fp = m.foundry_plan
        if fp.mode == "all":
            L.append("foundry_plan all")
        else:
            L.append("foundry_plan list " + " ".join(fp.foundries))
    if m.notes:
        L.append(f"# {m.notes}")
    return "\n".join(L)
