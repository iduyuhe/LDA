"""LDA · D-44 统一设计包规范（design outcome 的统一交付格式）。

把 D-37（环形 add-drop）/ D-41（量子逆设计）/ D-42（WDM 系统）/
D-43（readout 混合链路）四类设计结果统一成**同一份 DesignPackage**——
无论设计什么，交付物格式一致、可机器校验、可汇总对比：

  DesignPackage = {
    package_id, schema_version, kind, domain, title, created_at,
    ir        : 设计意图（D-40 IR：schema 版本 / 器件数 / 网表 / 校验）
    design    : targets（目标）+ params（设计参数）+ inverse_design（反解）
    verification : checks[]（死标量比对明细）+ passed + verdict
    artifacts : layout_svg / spectrum / gds / report（按 kind 可缺省）
    honest_notes : 模型/数据来源诚实标注
  }

设计包规范要点：
  - verification.passed 是唯一验收门（LLM 不进判决路径）；
  - ir 字段保证"每个包都回溯到设计意图 IR"；
  - honest_notes 强制记录模型假设与数据来源（诚实优先）。

CLI：python -m lda_design.design_package --all（构建全部 4 类包到 reports/packages/）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)   # lda/
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

SCHEMA_VERSION = "0.1"
PACKAGE_KINDS = ("add_drop", "quantum", "wdm", "readout_chain", "multiqubit",
                 "readout_fidelity")


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 4 类打包器（各包装一个已交付设计闭环的产物为统一 schema）
# ---------------------------------------------------------------------------
def package_from_add_drop(target_fsr: float = 17.5, gap: float = 0.3,
                          **kw) -> Dict[str, Any]:
    """D-37 环形 add-drop 产品链路 → 统一设计包。"""
    from lda_agent.ring_adddrop import build_package
    r = build_package(target_fsr_nm=target_fsr, params={"gap": gap})
    acc = r["acceptance"]
    return {
        "package_id": f"add-drop-fsr{target_fsr}",
        "schema_version": SCHEMA_VERSION,
        "kind": "add_drop", "domain": "photon",
        "title": "环形 add-drop 可制造设计包",
        "created_at": _now_iso(),
        "ir": {"schema_version": "0.3", "domain": "photon",
               "n_components": 1, "n_nets": 0,
               "validate_errors": []},
        "design": {"targets": {"fsr_nm": target_fsr},
                   "params": r["params"],
                   "inverse_design": r.get("inverse_design")},
        "verification": {"checks": acc["checks"], "passed": bool(acc["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"layout_svg": r.get("layout_svg"),
                      "spectrum": r.get("spectrum"),
                      "gds": r.get("gds"),
                      "budgets": {"coupling": r.get("coupling_budget"),
                                  "q": r.get("q_budget"),
                                  "loss": r.get("loss_budget")}},
        "honest_notes": r.get("note", ""),
    }


def package_from_quantum(kind: str = "Transmon", target: float = 5.0,
                         **kw) -> Dict[str, Any]:
    """D-41 量子 agent 逆设计闭环 → 统一设计包。"""
    from lda_agent.quantum_design import design_quantum
    r = design_quantum(kind, target, kw.get("extra"))
    v = r["verification"]
    return {
        "package_id": f"quantum-{kind.lower()}-{target}",
        "schema_version": SCHEMA_VERSION,
        "kind": "quantum", "domain": "quantum",
        "title": f"量子逆设计包（{kind}）",
        "created_at": _now_iso(),
        "ir": {"schema_version": (r.get("ir") or {}).get("schema_version", "0.3"),
               "domain": "quantum", "n_components": 1, "n_nets": 0,
               "validate_errors": (r.get("ir") or {}).get("validate_errors", [])},
        "design": {"targets": {kind.lower(): target},
                   "params": r["inverse_design"]["params"],
                   "inverse_design": {"formula": r["inverse_design"]["formula"]}},
        "verification": {"checks": [{"name": "严格数值双验证",
                                     "ok": bool(r["passed"]),
                                     "detail": v["verdict"]}],
                         "passed": bool(r["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"numerical": v.get("numerical"),
                      "analytic": v.get("analytic")},
        "honest_notes": "量子闭式反解 + D-39 严格数值双验证（LLM 不进判决）。",
    }


def package_from_wdm(channels: Optional[List[float]] = None, gap: float = 0.3,
                     **kw) -> Dict[str, Any]:
    """D-42 WDM 多环级联系统设计 → 统一设计包。"""
    from lda_agent.wdm_system import design_wdm
    channels = channels or [1550.0, 1552.5, 1555.0, 1557.5]
    r = design_wdm(channels, gap=gap)
    acc = r["acceptance"]
    return {
        "package_id": f"wdm-{len(channels)}ch",
        "schema_version": SCHEMA_VERSION,
        "kind": "wdm", "domain": "photon",
        "title": r["title"],
        "created_at": _now_iso(),
        "ir": {"schema_version": r["ir"]["schema_version"], "domain": "photon",
               "n_components": r["ir"]["n_components"],
               "n_nets": r["ir"]["n_nets"],
               "validate_errors": r["ir"]["validate_errors"]},
        "design": {"targets": {"channels_nm": r["channels_nm"]},
                   "params": {"ring_radii_um": r["ring_radii_um"],
                              "gap_um": r["gap_um"], "wg_width_um": r["wg_width_um"]},
                   "inverse_design": r.get("inverse_design"),
                   "metrics": r.get("metrics")},
        "verification": {"checks": acc["checks"], "passed": bool(acc["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"layout_svg": r.get("layout_svg"),
                      "spectrum": r.get("spectrum"),
                      "gds": r.get("gds")},
        "honest_notes": r.get("note", ""),
    }


def package_from_readout(f01: float = 5.0, delta: float = 1.0, g: float = 0.10,
                         kappa_r: float = 0.005, **kw) -> Dict[str, Any]:
    """D-43 光子-量子混合链路（dispersive readout）→ 统一设计包。"""
    from lda_agent.qubit_readout_chain import design_chain
    r = design_chain(f01=f01, delta=delta, g=g, kappa_r=kappa_r)
    acc = r["acceptance"]
    return {
        "package_id": f"readout-f01{f01}-d{delta}",
        "schema_version": SCHEMA_VERSION,
        "kind": "readout_chain", "domain": "hybrid",
        "title": r["title"],
        "created_at": _now_iso(),
        "ir": {"schema_version": r["ir"]["schema_version"],
               "domain": r["ir"]["domain"],
               "n_components": r["ir"]["n_components"],
               "n_nets": r["ir"]["n_nets"],
               "validate_errors": r["ir"]["validate_errors"]},
        "design": {"targets": {"f01_ghz": f01, "f_r_ghz": r["f_r_ghz"],
                               "g_ghz": g, "kappa_r_ghz": kappa_r},
                   "params": r["params"],
                   "inverse_design": {"formula": "E_J/l/Cc/Q_ext 闭式反解"}},
        "verification": {"checks": acc["checks"], "passed": bool(acc["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"verification_detail": r["verification"]},
        "honest_notes": r.get("note", ""),
    }


def package_from_multiqubit(f01s: Optional[List[float]] = None, **kw) -> Dict[str, Any]:
    """D-46 N-qubit 频率复用读出（光子-量子混合系统）→ 统一设计包。"""
    from lda_agent.multiqubit_readout import package_from_multiqubit as _p
    return _p(f01s=f01s, **kw)


def package_from_readout_fidelity(f01: float = 5.0, **kw) -> Dict[str, Any]:
    """D-47 单发读出保真度预算 → 统一设计包。"""
    from lda_agent.readout_fidelity import package_from_readout_fidelity as _p
    return _p(f01=f01, **kw)


_BUILDERS = {
    "add_drop": package_from_add_drop,
    "quantum": package_from_quantum,
    "wdm": package_from_wdm,
    "readout_chain": package_from_readout,
    "multiqubit": package_from_multiqubit,
    "readout_fidelity": package_from_readout_fidelity,
}

_DEFAULTS = {
    "add_drop": {"target_fsr": 17.5, "gap": 0.3},
    "quantum": {"kind": "Transmon", "target": 5.0},
    "wdm": {"channels": [1550.0, 1552.5, 1555.0, 1557.5], "gap": 0.3},
    "readout_chain": {"f01": 5.0, "delta": 1.0, "g": 0.10, "kappa_r": 0.005},
    "multiqubit": {"f01s": [4.8, 5.0, 5.2]},
    "readout_fidelity": {"f01": 5.0},
}


def build_package(kind: str, params: Optional[Dict[str, Any]] = None,
                  **kw) -> Dict[str, Any]:
    """统一派发：kind + 参数 → 统一 DesignPackage。

    params 为 dict（含子 kind 等键，不与包 kind 冲突）；kw 为显式键值。
    """
    if kind not in _BUILDERS:
        return {"ok": False, "error": f"未知设计包 kind={kind}（可选 {list(_BUILDERS)}）"}
    p = dict(_DEFAULTS.get(kind, {}))
    if params:
        p.update({k: v for k, v in params.items() if v is not None})
    p.update({k: v for k, v in kw.items() if v is not None})
    try:
        pkg = _BUILDERS[kind](**p)
        pkg["ok"] = True
        return pkg
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120], "kind": kind}


# ---------------------------------------------------------------------------
# 设计包 schema 校验（机器可校验的统一格式）
# ---------------------------------------------------------------------------
_REQUIRED = ("package_id", "schema_version", "kind", "domain", "title",
             "created_at", "design", "verification", "honest_notes")


def validate_package(pkg: Dict[str, Any]) -> List[str]:
    """校验 DesignPackage 是否符合统一规范。返回错误列表（空=合法）。"""
    errs: List[str] = []
    for f in _REQUIRED:
        if f not in pkg:
            errs.append(f"缺必填字段 '{f}'")
    if pkg.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"schema_version 应为 {SCHEMA_VERSION}，got {pkg.get('schema_version')}")
    if pkg.get("kind") not in PACKAGE_KINDS:
        errs.append(f"kind 未知：'{pkg.get('kind')}'")
    if pkg.get("domain") not in ("photon", "quantum", "hybrid"):
        errs.append(f"domain 未知：'{pkg.get('domain')}'")
    v = pkg.get("verification") or {}
    if "passed" not in v:
        errs.append("verification 缺 'passed' 验收门")
    if not pkg.get("honest_notes"):
        errs.append("honest_notes 为空（诚实标注必填）")
    return errs


def summarize(pkg: Dict[str, Any]) -> str:
    """人类可读摘要（供汇总/面板展示）。"""
    v = pkg.get("verification", {})
    d = pkg.get("design", {})
    return (f"[{'PASS' if v.get('passed') else 'FAIL'}] {pkg.get('kind')} · "
            f"{pkg.get('title')} · domain={pkg.get('domain')} · "
            f"目标 {d.get('targets')} · 参数 {d.get('params')} · "
            f"{str(v.get('verdict'))[:80]}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_all(out_dir: Optional[str] = None) -> Dict[str, Any]:
    """构建全部 4 类设计包并落盘 reports/packages/。"""
    out = {"schema_version": SCHEMA_VERSION, "packages": {}}
    for kind in PACKAGE_KINDS:
        pkg = build_package(kind)
        errs = validate_package(pkg)
        out["packages"][kind] = {
            "package_id": pkg.get("package_id"),
            "passed": pkg.get("verification", {}).get("passed"),
            "schema_ok": not errs,
            "schema_errors": errs,
        }
    out["all_schema_ok"] = all(
        v["schema_ok"] for v in out["packages"].values())
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        for kind in PACKAGE_KINDS:
            pkg = build_package(kind)
            with open(os.path.join(out_dir, f"{kind}.json"), "w",
                      encoding="utf-8") as f:
                json.dump(pkg, f, ensure_ascii=False, indent=2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA D-44 统一设计包")
    ap.add_argument("--all", action="store_true", help="构建全部 4 类包")
    ap.add_argument("--kind", default=None, choices=list(PACKAGE_KINDS))
    args = ap.parse_args()
    if args.kind:
        pkg = build_package(args.kind)
        print(json.dumps({k: pkg[k] for k in
                          ("package_id", "kind", "domain", "design",
                           "verification", "honest_notes")},
                         ensure_ascii=False, indent=2))
        return 0 if pkg.get("verification", {}).get("passed") else 1
    out = build_all(os.path.join(_LDA, "reports", "packages"))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["all_schema_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
