"""LDA · D-41 量子 agent 逆设计最小闭环（目标 → IR → 数值验证 PASS）。

把 D-38（逆设计框架）+ D-39（量子严格求解器）+ D-40（统一 IR/PhysicsAnchor）
串成**量子 agent 逆设计闭环**：给定目标频率/耦合，自动完成
「IR 构造（D-40 PhysicsAnchor + objective）→ 校验 → 闭式物理反解 → D-39
严格数值双验证 → 报告」——与光子 D-37 产品链路同构，LLM 不进判决路径。

三个量子器件的逆设计均为**闭式物理定律反解**（比搜索更干净、确定性）：
  - Transmon  : target f01 → E_J = (f01+E_C)²/(8·E_C)（Koch 反解）
  - Resonator : target f0  → l = 1/(4·f0·√(L′·C′))（λ/4 反解）
  - Coupler   : target J   → Cc = J·C₁·C₂/(n01₁·n01₂)（耦合闭式反解）

验证（D-39 严格数值 vs 解析契约双验证）：
  - Transmon  : 严格对角化 f01 ↔ Koch（rel ≤ 3%）
  - Resonator : 离散 TL 严格本征值 f0 ↔ λ/4 闭式（rel ≤ 1%）
  - Coupler   : 441 维严格对角化 J ↔ 解析 J（rel ≤ 10%）

CLI：python lda_agent/quantum_design.py --kind Transmon --target 5.0
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_ir import (Coupler, IRModel, ObjectiveSpec, Resonator, Transmon,  # noqa: E402
                    validate)

_QUANTUM_KINDS = ("Transmon", "Resonator", "Coupler")


# ---------------------------------------------------------------------------
# 闭式物理反解（确定性物理定律）
# ---------------------------------------------------------------------------
def inverse_transmon(target_f01_ghz: float, E_C: float) -> float:
    """Koch 反解：E_J = (f01+E_C)²/(8·E_C)（GHz）。"""
    return (target_f01_ghz + E_C) ** 2 / (8.0 * E_C)


def inverse_resonator(target_f0_ghz: float, Lp: float, Cp: float) -> float:
    """λ/4 反解：l = 1/(4·f0·√(L′·C′))（m）。"""
    return 1.0 / (4.0 * target_f0_ghz * 1e9 * math.sqrt(Lp * Cp))


def inverse_coupler(target_J_ghz: float, E_J1: float, E_C1: float,
                    E_J2: float, E_C2: float, C1: float, C2: float) -> float:
    """耦合反解：Cc = J·C₁·C₂/(n01₁·n01₂)（n01=(E_J/2E_C)^{1/4}/2）。"""
    n01 = lambda ej, ec: (ej / (2.0 * ec)) ** 0.25 / 2.0  # noqa: E731
    return target_J_ghz * C1 * C2 / (n01(E_J1, E_C1) * n01(E_J2, E_C2))


# ---------------------------------------------------------------------------
# 严格数值双验证（D-39 求解器）
# ---------------------------------------------------------------------------
def _ensure_path() -> None:
    try:
        from lda_l2.device_library import _ensure_solver_on_path
        _ensure_solver_on_path()
    except Exception:
        pass


def verify_quantum(kind: str, params: Dict[str, float],
                   target: float) -> Dict[str, Any]:
    """D-39 严格数值 vs 解析契约双验证。返回 {passed, analytic, numerical, verdict}。"""
    _ensure_path()
    if kind == "Transmon":
        from lda_solver.transmon_solver import koch_f01, solve_transmon
        E_J, E_C = params["E_J"], params["E_C"]
        sol = solve_transmon(E_J, E_C)
        f01_an = koch_f01(E_J, E_C)
        rel = abs(sol["f01"] - f01_an) / f01_an
        tol = 0.03
        passed = bool(rel <= tol)
        return {
            "passed": passed, "target_ghz": target,
            "analytic": {"f01_koch_ghz": round(f01_an, 5)},
            "numerical": {"f01_diag_ghz": round(sol["f01"], 5),
                          "rel_err": round(rel, 6), "tol_rel": tol,
                          "levels_ghz": [round(x, 4) for x in sol["levels_ghz"]]},
            "verdict": (f"Transmon 双验证 PASS（严格对角化 f01={sol['f01']:.4f} ↔ "
                        f"Koch {f01_an:.4f} rel={rel:.2%}≤{tol:.0%}）"
                        if passed else
                        f"Transmon 双验证 FAIL（rel={rel:.2%}>{tol:.0%}）"),
        }
    if kind == "Resonator":
        from lda_solver.resonator_solver import (f_quarter_wave_closed_form,
                                                 solve_resonator)
        Lp, Cp, l = params["Lp"], params["Cp"], params["l"]
        f_an = f_quarter_wave_closed_form(Lp, Cp, l) / 1e9
        sol = solve_resonator(Lp=Lp, Cp=Cp, l=l, tol_rel=0.01)
        rel = sol["rel_err"]
        tol = 0.01
        passed = bool(rel <= tol)
        return {
            "passed": passed, "target_ghz": target,
            "analytic": {"f0_closed_ghz": round(f_an, 5)},
            "numerical": {"f0_num_ghz": sol["f0_num_ghz"],
                          "rel_err": rel, "tol_rel": tol, "N_used": sol["N_used"]},
            "verdict": (f"Resonator 双验证 PASS（离散 TL 严格 f0={sol['f0_num_ghz']} "
                        f"↔ 闭式 {f_an:.4f} rel={rel:.2%}≤{tol:.0%}）"
                        if passed else
                        f"Resonator 双验证 FAIL（rel={rel:.2%}>{tol:.0%}）"),
        }
    if kind == "Coupler":
        from lda_solver.coupler_solver import coupling_analytic, solve_coupler
        J_an = coupling_analytic(params["E_J1"], params["E_C1"], params["E_J2"],
                                 params["E_C2"], params["Cc"], params["C1"],
                                 params["C2"])
        sol = solve_coupler(params["E_J1"], params["E_C1"], params["E_J2"],
                            params["E_C2"], params["Cc"], params["C1"],
                            params["C2"])
        rel = abs(sol["J_num"] - J_an) / abs(J_an)
        tol = 0.10
        passed = bool(rel <= tol)
        return {
            "passed": passed, "target_ghz": target,
            "analytic": {"J_analytic_ghz": round(J_an, 5)},
            "numerical": {"J_num_ghz": round(sol["J_num"], 5),
                          "rel_err": round(rel, 6), "tol_rel": tol,
                          "levels_ghz": [round(x, 4) for x in sol["levels_ghz"]]},
            "verdict": (f"Coupler 双验证 PASS（441 维严格对角化 J={sol['J_num']:.4f} "
                        f"↔ 解析 {J_an:.4f} rel={rel:.2%}≤{tol:.0%}）"
                        if passed else
                        f"Coupler 双验证 FAIL（rel={rel:.2%}>{tol:.0%}）"),
        }
    raise ValueError(f"未知量子 kind：{kind}")


# ---------------------------------------------------------------------------
# IR 构造（D-40 统一 IR，带 PhysicsAnchor + objective）
# ---------------------------------------------------------------------------
def build_ir(kind: str, target: float, extra: Optional[Dict[str, float]] = None
             ) -> IRModel:
    ex = dict(extra or {})
    if kind == "Transmon":
        comp = Transmon(id="q1", E_C=float(ex.get("E_C", 0.30)))
        bid, tol = "B9", 0.1
    elif kind == "Resonator":
        comp = Resonator(id="r1", Lp=float(ex.get("Lp", 0.4e-6)),
                         Cp=float(ex.get("Cp", 1.5e-10)))
        bid, tol = "B12", 0.02
    elif kind == "Coupler":
        comp = Coupler(id="c1", E_J1=float(ex.get("E_J1", 20.0)),
                       E_C1=float(ex.get("E_C1", 0.25)),
                       E_J2=float(ex.get("E_J2", 20.0)),
                       E_C2=float(ex.get("E_C2", 0.25)),
                       C1=float(ex.get("C1", 1.0)), C2=float(ex.get("C2", 1.0)))
        bid, tol = "B13", 0.10
    else:
        raise ValueError(f"未知量子 kind：{kind}（可选 {_QUANTUM_KINDS}）")
    return IRModel(
        domain="quantum", name=f"{kind.lower()}-{bid}",
        components=[comp],
        objectives=[ObjectiveSpec(bid=bid, target=round(float(target), 6),
                                  tol=tol, role="objective")],
        notes=f"D-41 量子 agent 逆设计闭环：目标 {target}（{bid} 物理锚）",
    )


# ---------------------------------------------------------------------------
# 主闭环
# ---------------------------------------------------------------------------
def design_quantum(kind: str, target: float,
                   extra: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """量子 agent 逆设计最小闭环：IR → 校验 → 闭式反解 → 严格数值双验证。"""
    if kind not in _QUANTUM_KINDS:
        return {"ok": False, "error": f"未知量子 kind：{kind}"
                                     f"（可选 {_QUANTUM_KINDS}）"}
    ex = dict(extra or {})
    model = build_ir(kind, target, ex)
    errs = validate(model)
    if errs:
        return {"ok": False, "error": f"IR 校验失败：{errs}"}

    # 闭式反解
    if kind == "Transmon":
        E_C = float(ex.get("E_C", 0.30))
        params = {"E_J": round(inverse_transmon(target, E_C), 6), "E_C": E_C}
        inv = {"formula": "E_J=(f01+E_C)²/(8E_C)（Koch 反解）"}
    elif kind == "Resonator":
        Lp = float(ex.get("Lp", 0.4e-6)); Cp = float(ex.get("Cp", 1.5e-10))
        params = {"Lp": Lp, "Cp": Cp,
                  "l": round(inverse_resonator(target, Lp, Cp), 10)}
        inv = {"formula": "l=1/(4·f0·√(L′C′))（λ/4 反解）"}
    else:  # Coupler
        E_J1 = float(ex.get("E_J1", 20.0)); E_C1 = float(ex.get("E_C1", 0.25))
        E_J2 = float(ex.get("E_J2", 20.0)); E_C2 = float(ex.get("E_C2", 0.25))
        C1 = float(ex.get("C1", 1.0)); C2 = float(ex.get("C2", 1.0))
        params = {"E_J1": E_J1, "E_C1": E_C1, "E_J2": E_J2, "E_C2": E_C2,
                  "C1": C1, "C2": C2,
                  "Cc": round(inverse_coupler(target, E_J1, E_C1, E_J2, E_C2,
                                              C1, C2), 6)}
        inv = {"formula": "Cc=J·C₁C₂/(n01₁n01₂)（耦合闭式反解）"}

    # 严格数值双验证（D-39）
    verify = verify_quantum(kind, params, target)
    physics = model.components[0].physics
    return {
        "ok": True,
        "kind": kind,
        "target": target,
        "domain": "quantum",
        "ir": {
            "schema_version": model.schema_version,
            "physics_bid": physics.bid if physics else None,
            "physics_kind": physics.kind if physics else None,
            "validate_errors": errs,
        },
        "inverse_design": {"params": params, "formula": inv["formula"]},
        "verification": verify,
        "passed": bool(verify["passed"]),
        "verdict": (f"量子 agent 逆设计闭环 PASS：目标 {kind} "
                    f"{target}{'GHz' if kind != 'Resonator' else 'GHz'} → "
                    f"{inv['formula']} → {verify['verdict']}"
                    if verify["passed"] else
                    f"量子逆设计闭环未全过：{verify['verdict']}"),
    }


def design_from_ir(model: IRModel) -> Dict[str, Any]:
    """消费任意量子 IR（D-40）：按 physics 锚 + objective 自动逆设计。"""
    out = {"ok": True, "devices": {}}
    for comp in model.components:
        ph = comp.physics
        if ph is None or ph.bid not in ("B9", "B12", "B13"):
            continue
        obj = next((o for o in model.objectives if o.bid == ph.bid), None)
        if obj is None:
            continue
        kind = {"B9": "Transmon", "B12": "Resonator", "B13": "Coupler"}[ph.bid]
        extra = dict(ph.spec_params)
        # spec_params 里去掉反解目标参数（l/Cc/E_J 由目标反解，其余为输入）
        out["devices"][comp.id] = design_quantum(kind, obj.target, extra)
    if not out["devices"]:
        out["ok"] = False
        out["error"] = "IR 无带 B9/B12/B13 物理锚 + objective 的量子器件"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA D-41 量子 agent 逆设计闭环")
    ap.add_argument("--kind", default="Transmon", choices=list(_QUANTUM_KINDS))
    ap.add_argument("--target", type=float, default=5.0,
                    help="目标 f01/f0/J（GHz）")
    args = ap.parse_args()
    rep = design_quantum(args.kind, args.target)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
