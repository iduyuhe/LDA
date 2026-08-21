"""LDA · D-43 光子-量子混合链路：芯片级 dispersive readout（readout 波导 + Transmon）。

量子芯片标准读出架构：Transmon qubit（f01）↔ 电容耦合（g）↔ readout 谐振器
（f_r = f01+Δ，λ/4）↔ 读出力线（feedline，κ_r 读出线宽）。这是"跨光子+量子
统一"的**系统级**落地：同一 IR 网表连接微波光子器件（Waveguide 读出力线）与
量子器件（Transmon/Resonator），同一物理定律锚验证链路。

闭环（LLM 不进判决路径）：
  1. 系统设计（闭式物理反解）：
       - Transmon    : E_J = (f01+E_C)²/(8E_C)（D-41 反解）
       - Resonator   : l = 1/(4·f_r·√(L′C′))（λ/4 反解，f_r=f01+Δ 色散失谐）
       - 耦合        : Cc = 2·g/√(f_q·f_r)（标准电容耦合闭式，CΣ=Cr=1 归一）
       - Feedline    : Q_ext = f_r/κ_r（读出耦合 Q）
  2. 严格数值双验证：
       - Transmon  : 严格对角化 f01 ↔ Koch（D-39，rel≤3%）
       - Resonator : 离散 TL 严格本征值 f0 ↔ λ/4 闭式（D-39，rel≤1%）
       - 耦合系统   : **JC 哈密顿量精确对角化**（Fock 截断，严格数值）——
                     ① 共振真空拉比分裂 = 2g（自洽）② 色散位移 |χ_num| ≈ g²/Δ
                     （解析色散近似 ↔ 精确对角化，rel≤10%）
  3. 系统验收（死标量比对）：
       - 色散区有效  : Δ/g ≥ 5（弱耦合近似成立）
       - 读出可分辨  : χ = g²/Δ ≥ κ_r（色散位移 ≥ 读出线宽）
       - Q_ext 物理量级（1e2~1e5）；IR 混合网表校验通过
  4. 混合 IR（domain=hybrid）+ 报告。

CLI：python lda_agent/qubit_readout_chain.py --f01 5.0
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

import numpy as np  # noqa: E402

from lda_ir import IRModel, ObjectiveSpec, Resonator, Transmon, Waveguide, validate  # noqa: E402


# ---------------------------------------------------------------------------
# JC 严格对角化（耦合系统精确数值）
# ---------------------------------------------------------------------------
def jc_spectrum(f_q: float, f_r: float, g: float, M: int = 30) -> np.ndarray:
    """JC 哈密顿量精确对角化（GHz）：|g,n>,|e,n>，Fock 截断 M。

    H = (−f_q/2)|g><g| + (f_q/2)|e><e| + f_r·a†a + g(σ₋a† + σ₊a)
    耦合：|e,n> ↔ |g,n+1>，强度 g·√(n+1)（标准 JC）。
    """
    dim = 2 * (M + 1)
    H = np.zeros((dim, dim))
    for n in range(M + 1):
        H[2 * n, 2 * n] = -f_q / 2.0 + n * f_r
        H[2 * n + 1, 2 * n + 1] = +f_q / 2.0 + n * f_r
    for n in range(M):
        ei, gi = 2 * n + 1, 2 * (n + 1)
        H[ei, gi] = g * math.sqrt(n + 1.0)
        H[gi, ei] = g * math.sqrt(n + 1.0)
    return np.sort(np.linalg.eigh(H)[0])


def jc_dispersive_verify(f_q: float, f_r: float, g: float,
                         tol_rel: float = 0.10) -> Dict[str, Any]:
    """JC 精确对角化 ↔ 色散近似双验证。

    ① 共振真空拉比分裂：f_q=f_r 时 |e,0>/|g,1> 分裂 = 2g（自洽）
    ② 色散位移：χ_num = |(ω_r|e − ω_r|g)/2| vs χ_an = g²/Δ（|Δ|=|f_r−f_q|）
    """
    delta = abs(f_r - f_q)
    chi_an = g * g / max(delta, 1e-9)
    E = jc_spectrum(f_q, f_r, g)
    w_r_g = E[2] - E[0]
    w_r_e = E[3] - E[1]
    chi_num = abs((w_r_e - w_r_g) / 2.0)
    chi_rel = abs(chi_num - chi_an) / chi_an
    # 共振拉比分裂（在共振频率对处）
    E_res = jc_spectrum(f_r, f_r, g)
    rabi_split = E_res[2] - E_res[1]
    g_self = rabi_split / 2.0
    g_rel = abs(g_self - g) / g
    passed = bool(chi_rel <= tol_rel and g_rel <= 0.02)
    return {
        "passed": passed,
        "chi_num_ghz": round(chi_num, 6),
        "chi_analytic_ghz": round(chi_an, 6),
        "chi_rel_err": round(chi_rel, 6),
        "tol_rel": tol_rel,
        "rabi_split_ghz": round(rabi_split, 6),
        "g_from_split_ghz": round(g_self, 6),
        "g_rel_err": round(g_rel, 6),
    }


# ---------------------------------------------------------------------------
# 闭式反解（复用 D-41 公式）
# ---------------------------------------------------------------------------
def inverse_transmon(f01: float, E_C: float) -> float:
    return (f01 + E_C) ** 2 / (8.0 * E_C)


def inverse_resonator(f0: float, Lp: float, Cp: float) -> float:
    return 1.0 / (4.0 * f0 * 1e9 * math.sqrt(Lp * Cp))


def inverse_coupling(g: float, f_q: float, f_r: float) -> float:
    """标准电容耦合闭式：g = Cc·√(ωq·ωr)/(2·√(CΣ·Cr)) → Cc = 2g/√(fq·fr)
    （CΣ=Cr=1 归一；g/f 用 GHz）。"""
    return 2.0 * g / math.sqrt(f_q * f_r)


# ---------------------------------------------------------------------------
# 主闭环
# ---------------------------------------------------------------------------
def design_chain(f01: float = 5.0, E_C: float = 0.25, delta: float = 1.0,
                 g: float = 0.10, kappa_r: float = 0.005,
                 Lp: float = 0.4e-6, Cp: float = 1.5e-10,
                 C_sigma: float = 1.0, C_r: float = 1.0) -> Dict[str, Any]:
    """芯片级 dispersive readout 链路设计闭环。"""
    f_r = f01 + delta
    # 1) 系统设计（闭式反解）
    E_J = inverse_transmon(f01, E_C)
    l = inverse_resonator(f_r, Lp, Cp)
    Cc = inverse_coupling(g, f01, f_r) * math.sqrt(C_sigma * C_r)
    Q_ext = f_r / kappa_r
    params = {"E_J": round(E_J, 4), "E_C": E_C, "f_r_ghz": f_r,
              "Lp": Lp, "Cp": Cp, "l_m": round(l, 9),
              "Cc": round(Cc, 5), "Q_ext": round(Q_ext, 1)}

    # 2) 严格数值双验证
    _ensure_path()
    from lda_solver.coupler_solver import koch_f01  # noqa: E402
    from lda_solver.resonator_solver import f_quarter_wave_closed_form  # noqa: E402
    from lda_solver.transmon_solver import solve_transmon  # noqa: E402
    sol_q = solve_transmon(E_J, E_C)
    f01_an = koch_f01(E_J, E_C)
    rel_q = abs(sol_q["f01"] - f01_an) / f01_an
    f0_an = f_quarter_wave_closed_form(Lp, Cp, l) / 1e9
    from lda_solver.resonator_solver import solve_resonator  # noqa: E402
    sol_r = solve_resonator(Lp=Lp, Cp=Cp, l=l, tol_rel=0.01)
    rel_r = sol_r["rel_err"]
    jc = jc_dispersive_verify(f01, f_r, g)

    # 3) 系统验收（死标量比对）
    chi = g * g / abs(delta)
    checks = [
        {"name": "Transmon 双验证（对角化↔Koch）", "ok": bool(rel_q <= 0.03),
         "detail": f"f01={sol_q['f01']:.4f}↔{f01_an:.4f}GHz rel={rel_q:.2%}"},
        {"name": "Resonator 双验证（离散本征值↔λ/4 闭式）", "ok": bool(rel_r <= 0.01),
         "detail": f"f0={sol_r['f0_num_ghz']}↔{f0_an:.4f}GHz rel={rel_r:.2%}"},
        {"name": "JC 精确对角化自洽（共振分裂=2g + 色散 χ）",
         "ok": bool(jc["passed"]),
         "detail": (f"拉比分裂={jc['rabi_split_ghz']}≈2g · "
                    f"|χ_num|={jc['chi_num_ghz']} vs g²/Δ={jc['chi_analytic_ghz']} "
                    f"rel={jc['chi_rel_err']:.2%}")},
        {"name": "色散区有效（Δ/g ≥ 5）", "ok": bool(abs(delta) / g >= 5.0),
         "detail": f"Δ/g={abs(delta)/g:.1f}"},
        {"name": "读出可分辨（χ ≥ κ_r）", "ok": bool(chi >= kappa_r),
         "detail": f"χ={chi:.4f}GHz vs κ_r={kappa_r}GHz"},
        {"name": "读出 Q_ext 物理量级（1e2~1e5）", "ok": bool(1e2 <= Q_ext <= 1e5),
         "detail": f"Q_ext={Q_ext:.0f}（=f_r/κ_r）"},
    ]
    # 4) 混合 IR 网表（domain=hybrid：量子 + 微波光子读出力线）
    model = IRModel(
        domain="hybrid", name="qubit-readout-chain",
        components=[Transmon(id="q1", E_J=E_J, E_C=E_C),
                    Resonator(id="r1", Lp=Lp, Cp=Cp, l=l,
                              l_bounds=(l * 0.5, l * 1.5)),
                    Waveguide(id="feedline", width=0.5)],
        objectives=[ObjectiveSpec(bid="B9", target=f01, tol=0.1,
                                  role="objective"),
                    ObjectiveSpec(bid="B12", target=round(f_r, 4), tol=0.02,
                                  role="objective")],
        notes=f"芯片级 dispersive readout：qubit f01={f01}GHz ↔ readout "
              f"f_r={f_r}GHz（Δ={delta}GHz）↔ feedline（κ_r={kappa_r}GHz）",
    )
    model.connect("qc", "q1.readout", "r1.in")   # qubit ↔ readout 腔
    model.connect("ro", "r1.out", "feedline.in")  # readout → 读出力线
    ir_errs = validate(model)
    checks.insert(0, {"name": "混合 IR 网表校验（hybrid）", "ok": not ir_errs,
                      "detail": f"{len(model.components)} 器件 + "
                                f"{len(model.nets)} 网表"
                                f"{'；' + '；'.join(ir_errs[:3]) if ir_errs else ' 通过'}"})
    accepted = all(c["ok"] for c in checks)
    verdict = ("芯片级 dispersive readout 链路设计 PASS：qubit f01=%.3fGHz ↔ "
               "readout f_r=%.3fGHz（Δ=%.2fGHz，Δ/g=%.1f）↔ feedline Q_ext=%.0f，"
               "χ=%.2fMHz ≥ κ_r=%.1fMHz；三器件双验证 + JC 精确对角化自洽。"
               % (f01, f_r, delta, abs(delta) / g, Q_ext, chi * 1000, kappa_r * 1000)
               if accepted else
               "readout 链路未全过：" + "; ".join(
                   c["name"] for c in checks if not c["ok"]))
    return {
        "ok": True,
        "title": "光子-量子混合链路 · 芯片级 dispersive readout",
        "f01_ghz": f01, "f_r_ghz": f_r, "delta_ghz": delta, "g_ghz": g,
        "kappa_r_ghz": kappa_r,
        "params": params,
        "ir": {"schema_version": model.schema_version,
               "domain": model.domain, "n_components": len(model.components),
               "n_nets": len(model.nets), "validate_errors": ir_errs},
        "verification": {
            "transmon": {"f01_diag_ghz": round(sol_q["f01"], 5),
                         "f01_koch_ghz": round(f01_an, 5),
                         "rel_err": round(rel_q, 6)},
            "resonator": {"f0_num_ghz": sol_r["f0_num_ghz"],
                          "f0_closed_ghz": round(f0_an, 5),
                          "rel_err": rel_r},
            "jc": jc,
        },
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": "JC 精确对角化（Fock 截断 M=30）为耦合系统严格数值侧；χ=g²/Δ 为"
                "色散解析近似——两者交叉验证（rel≤10%）。耦合闭式取 CΣ=Cr=1 归一。"
                "LLM 不进判决路径。",
    }


def _ensure_path() -> None:
    try:
        from lda_l2.device_library import _ensure_solver_on_path
        _ensure_solver_on_path()
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA D-43 readout 链路设计")
    ap.add_argument("--f01", type=float, default=5.0)
    ap.add_argument("--delta", type=float, default=1.0)
    ap.add_argument("--g", type=float, default=0.10)
    ap.add_argument("--kappa_r", type=float, default=0.005)
    args = ap.parse_args()
    rep = design_chain(f01=args.f01, delta=args.delta, g=args.g,
                       kappa_r=args.kappa_r)
    print(json.dumps({k: rep[k] for k in
                      ("title", "f01_ghz", "f_r_ghz", "params", "verification",
                       "ir", "acceptance", "verdict")},
                     ensure_ascii=False, indent=2))
    return 0 if rep["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
