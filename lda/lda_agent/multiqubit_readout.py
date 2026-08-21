"""D-46: N qubit 频率复用读出系统（光子-量子混合设计包）。

把 D-43（单 qubit dispersive readout）+ D-42（级联/信道错开）组合成
**多 qubit 频率复用读出**：N 个 Transmon qubit，各自电容耦合到专属 readout
谐振器（f_r_i = f01_i + Δ），谐振器沿公共读出力线（feedline）错开读出频率
（间隔 ≥ 3×线宽防串扰）——WDM 的量子版，量子芯片标准多 qubit 读出版图。

物理模型（LLM 不进判决路径）：
  · 每 qubit：闭式反解 E_J=(f+E_C)²/8E_C、l=1/(4f_r√(L′C′))、Cc=2g/√(f_q·f_r)、
    Q_ext=f_r/κ_r（复用 D-41/D-43）
  · 逐 qubit：D-39 严格数值双验证（Transmon 对角化↔Koch、Resonator 离散
    本征值↔λ/4 闭式）+ JC 精确对角化 ↔ 色散 χ=g²/Δ（复用 D-43）
  · 频率复用：力线透射 = N 个 hanger 型 dip 级联
    |S21|² = Π_i (Δ²+((κᵢ−κₑ)/2)²)/(Δ²+((κᵢ+κₑ)/2)²)（Goppl 2008 标准形式）
  · 可分辨判据：相邻 dip 中点透射 T_mid > 0.5（物理：两 dip 未融合）
  · 防串扰判据：相邻读出频率间隔 ≥ 3×κ_r（κ_r = κ_ext + κ_i）

输出：D-44 统一设计包（schema 校验通过）+ 力线透射谱 + 混合 IR 网表。
"""

import argparse
import json
import math
import sys
from typing import Any, Dict, List, Optional

import numpy as np

from lda_ir import (  # type: ignore
    IRModel, ObjectiveSpec, Resonator, Transmon, Waveguide, validate,
)
from lda_agent.qubit_readout_chain import (  # type: ignore
    inverse_coupling, inverse_resonator, inverse_transmon,
    jc_dispersive_verify,
)

# 默认物理参数（GHz / H / F / m，文献典型超导量子芯片）
_DEF_E_C = 0.25
_DEF_LP = 0.4e-6
_DEF_CP = 1.5e-10
_DEF_DELTA = 1.0
_DEF_G = 0.10
_DEF_KAPPA_EXT = 0.005      # 读出谐振器→力线耦合率 5MHz
_DEF_KAPPA_I = 0.0025       # 内耗 2.5MHz（κ_r = κ_ext + κ_i = 7.5MHz）
_MIN_SPACING_FACTOR = 3.0   # 相邻读出频率间隔 ≥ 3×κ_r


# ---------------------------------------------------------------------------
# 力线透射模型
# ---------------------------------------------------------------------------
def notch_transmission(f: float, f_r: float, kappa_ext: float,
                       kappa_i: float) -> float:
    """hanger 型读出透射 |S21|²（单 dip，Goppl 2008 标准形式）。"""
    d = f - f_r
    return ((d * d + ((kappa_i - kappa_ext) / 2.0) ** 2) /
            (d * d + ((kappa_i + kappa_ext) / 2.0) ** 2))


def feedline_spectrum(fr_ghz: List[float], kappa_ext: float, kappa_i: float,
                      span_ghz: float = 0.7, n_points: int = 2401) -> Dict[str, Any]:
    """公共读出力线级联透射谱（N 个 hanger dip 乘积）。

    返回 {"frequencies_ghz": [...], "transmission": [...]}。
    采样窗口自动覆盖所有 dip 并留边距。
    """
    lo = min(fr_ghz) - span_ghz / 2.0
    hi = max(fr_ghz) + span_ghz / 2.0
    grid = np.linspace(lo, hi, n_points)
    T = np.ones_like(grid)
    for f_r in fr_ghz:
        T = T * notch_transmission(grid, f_r, kappa_ext, kappa_i)
    return {"frequencies_ghz": [round(float(x), 6) for x in grid],
            "transmission": [round(float(x), 6) for x in T]}


def dip_resolvable(fr_ghz: List[float], kappa_ext: float, kappa_i: float,
                   grid_n: int = 4001) -> List[Dict[str, Any]]:
    """逐对相邻 dip 可分辨性检查：中点透射 > 0.5（未融合）。

    返回每对相邻 dip 的 {f0, f1, mid_f, mid_T, resolvable}。
    """
    out: List[Dict[str, Any]] = []
    for i in range(len(fr_ghz) - 1):
        f0, f1 = fr_ghz[i], fr_ghz[i + 1]
        mid_f = (f0 + f1) / 2.0
        # 中点处只看这两个 dip 的贡献（其余 dip 相距更远，贡献≈1）
        t_mid = (notch_transmission(mid_f, f0, kappa_ext, kappa_i) *
                 notch_transmission(mid_f, f1, kappa_ext, kappa_i))
        out.append({"f0_ghz": f0, "f1_ghz": f1,
                    "mid_f_ghz": round(mid_f, 6),
                    "mid_T": round(float(t_mid), 5),
                    "resolvable": bool(t_mid > 0.5)})
    return out


# ---------------------------------------------------------------------------
# 主闭环
# ---------------------------------------------------------------------------
def design_multiqubit_readout(
        f01s: List[float], E_C: float = _DEF_E_C, delta: float = _DEF_DELTA,
        g: float = _DEF_G, kappa_ext: float = _DEF_KAPPA_EXT,
        kappa_i: Optional[float] = None, Lp: float = _DEF_LP,
        Cp: float = _DEF_CP, min_spacing_factor: float = _MIN_SPACING_FACTOR,
) -> Dict[str, Any]:
    """N qubit 频率复用读出系统设计闭环。"""
    if kappa_i is None:
        kappa_i = kappa_ext / 2.0
    kappa_r = kappa_ext + kappa_i
    n = len(f01s)
    f01s = sorted(f01s)          # 按频率升序设计（力线从左到右错开）
    fr = [f + delta for f in f01s]
    chi = g * g / abs(delta)

    # 1) 每 qubit 闭式反解（复用 D-41/D-43）
    qubits: List[Dict[str, Any]] = []
    for i, f01 in enumerate(f01s):
        f_r = fr[i]
        E_J = inverse_transmon(f01, E_C)
        l = inverse_resonator(f_r, Lp, Cp)
        Cc = inverse_coupling(g, f01, f_r)
        Q_ext = f_r / kappa_r
        qubits.append({
            "qid": f"q{i + 1}", "f01_ghz": f01, "f_r_ghz": round(f_r, 4),
            "E_J": round(E_J, 4), "E_C": E_C, "l_m": round(l, 9),
            "Cc": round(Cc, 5), "Q_ext": round(Q_ext, 1),
            "kappa_ext_ghz": kappa_ext, "kappa_i_ghz": kappa_i,
        })

    # 2) 逐 qubit 严格数值双验证 + JC
    _ensure_path()
    from lda_solver.coupler_solver import koch_f01  # noqa: E402
    from lda_solver.resonator_solver import (  # noqa: E402
        f_quarter_wave_closed_form, solve_resonator,
    )
    from lda_solver.transmon_solver import solve_transmon  # noqa: E402

    checks: List[Dict[str, Any]] = []
    for i, q in enumerate(qubits):
        sol_q = solve_transmon(q["E_J"], E_C)
        f01_an = koch_f01(q["E_J"], E_C)
        rel_q = abs(sol_q["f01"] - f01_an) / f01_an
        f0_an = f_quarter_wave_closed_form(Lp, Cp, q["l_m"]) / 1e9
        sol_r = solve_resonator(Lp=Lp, Cp=Cp, l=q["l_m"], tol_rel=0.01)
        rel_r = sol_r["rel_err"]
        jc = jc_dispersive_verify(f01s[i], fr[i], g)
        q["verification"] = {
            "transmon": {"f01_diag_ghz": round(sol_q["f01"], 5),
                         "f01_koch_ghz": round(f01_an, 5),
                         "rel_err": round(rel_q, 6)},
            "resonator": {"f0_num_ghz": sol_r["f0_num_ghz"],
                          "f0_closed_ghz": round(f0_an, 5),
                          "rel_err": rel_r},
            "jc": jc,
        }
        checks.append({
            "name": f"q{i + 1} Transmon 双验证（对角化↔Koch）",
            "ok": bool(rel_q <= 0.03),
            "detail": f"f01={sol_q['f01']:.4f}↔{f01_an:.4f}GHz rel={rel_q:.2%}"})
        checks.append({
            "name": f"q{i + 1} Resonator 双验证（离散本征值↔λ/4 闭式）",
            "ok": bool(rel_r <= 0.01),
            "detail": f"f0={sol_r['f0_num_ghz']}↔{f0_an:.4f}GHz rel={rel_r:.2%}"})
        checks.append({
            "name": f"q{i + 1} JC 精确对角化自洽（分裂=2g + 色散 χ）",
            "ok": bool(jc["passed"]),
            "detail": (f"拉比分裂={jc['rabi_split_ghz']}≈2g · "
                       f"|χ_num|={jc['chi_num_ghz']} vs g²/Δ="
                       f"{jc['chi_analytic_ghz']} rel={jc['chi_rel_err']:.2%}")})

    # 3) 系统验收（死标量比对）
    spacing_ok = True
    for i in range(n - 1):
        gap = fr[i + 1] - fr[i]
        if gap < min_spacing_factor * kappa_r:
            spacing_ok = False
    checks.append({
        "name": f"读出频率错开（间隔 ≥ {min_spacing_factor:.0f}×κ_r）",
        "ok": bool(spacing_ok),
        "detail": ("；".join(
            f"Δf{fr[i + 1]:.4f}−{fr[i]:.4f}={fr[i + 1] - fr[i]:.4f}GHz"
            f"（κ_r={kappa_r}GHz）" for i in range(n - 1))
            if n > 1 else "单 qubit 无需错开")})
    resolv = dip_resolvable(fr, kappa_ext, kappa_i)
    checks.append({
        "name": "力线 dip 可分辨（相邻中点透射 > 0.5）",
        "ok": bool(all(r["resolvable"] for r in resolv)),
        "detail": "；".join(
            f"{r['f0_ghz']}↔{r['f1_ghz']}GHz 中点 T={r['mid_T']}"
            for r in resolv) if resolv else "单 dip"})
    checks.append({
        "name": "色散区有效（Δ/g ≥ 5，逐 qubit）",
        "ok": bool(abs(delta) / g >= 5.0),
        "detail": f"Δ/g={abs(delta) / g:.1f}"})
    checks.append({
        "name": "读出可分辨（χ=g²/Δ ≥ κ_r，逐 qubit）",
        "ok": bool(chi >= kappa_r),
        "detail": f"χ={chi:.4f}GHz vs κ_r={kappa_r}GHz（χ/κ={chi / kappa_r:.1f}）"})

    # 4) 混合 IR 网表（domain=hybrid：N qubit + N readout + 1 feedline）
    comps: List[Any] = [Waveguide(id="feedline", width=0.5)]
    objectives = [ObjectiveSpec(bid="B9", target=f01s[0], tol=0.1,
                                role="objective")]
    for i, q in enumerate(qubits):
        comps.append(Transmon(id=f"q{i + 1}", E_J=q["E_J"], E_C=E_C))
        comps.append(Resonator(id=f"r{i + 1}", Lp=Lp, Cp=Cp, l=q["l_m"],
                               l_bounds=(q["l_m"] * 0.5, q["l_m"] * 1.5)))
        objectives.append(ObjectiveSpec(bid="B12", target=round(fr[i], 4),
                                        tol=0.02, role="objective"))
    model = IRModel(
        domain="hybrid", name="multiqubit-readout",
        components=comps, objectives=objectives,
        notes=f"{n}-qubit 频率复用读出：f01={f01s} → readout f_r={fr} "
              f"（Δ={delta}GHz, g={g}GHz, κ_r={kappa_r}GHz）沿公共 feedline 错开",
    )
    for i in range(n):
        model.connect(f"q{i + 1}r{i + 1}", f"q{i + 1}.readout", f"r{i + 1}.in")
        model.connect(f"r{i + 1}f", f"r{i + 1}.out", "feedline.in")
    ir_errs = validate(model)
    checks.insert(0, {
        "name": "混合 IR 网表校验（hybrid · 3N+1 器件）",
        "ok": not ir_errs,
        "detail": f"{len(model.components)} 器件 + {len(model.nets)} 网表"
                  f"{'；' + '；'.join(ir_errs[:3]) if ir_errs else ' 通过'}"})

    accepted = all(c["ok"] for c in checks)
    span = fr[-1] - fr[0] if n > 1 else 0.0
    verdict = (
        f"{n}-qubit 频率复用读出 PASS：f01={f01s}GHz → readout "
        f"{[round(x, 3) for x in fr]}GHz 沿 feedline 错开（跨度 "
        f"{span * 1000:.0f}MHz），Δ/g={abs(delta) / g:.1f}，"
        f"χ/κ_r={chi / kappa_r:.1f}，dip 全部可分辨；逐 qubit 双验证 + JC 自洽。"
        if accepted else
        "多 qubit 读出未全过：" + "; ".join(
            c["name"] for c in checks if not c["ok"]))

    return {
        "ok": True,
        "title": f"{n}-qubit 频率复用读出（光子-量子混合系统）",
        "n_qubits": n, "f01s_ghz": f01s, "readout_freqs_ghz": fr,
        "delta_ghz": delta, "g_ghz": g,
        "kappa_r_ghz": kappa_r, "kappa_ext_ghz": kappa_ext,
        "kappa_i_ghz": kappa_i, "chi_ghz": round(chi, 6),
        "qubits": qubits,
        "spectrum": feedline_spectrum(fr, kappa_ext, kappa_i),
        "dip_resolvability": resolv,
        "ir": {"schema_version": model.schema_version,
               "domain": model.domain, "n_components": len(model.components),
               "n_nets": len(model.nets), "validate_errors": ir_errs},
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": "力线透射 = N 个 hanger 型 dip 级联（Goppl 2008 标准形式，"
                "临界耦合 T→0）；可分辨判据=相邻 dip 中点透射>0.5（未融合）；"
                "防串扰判据=读出频率间隔≥3×κ_r。κ_i 默认 κ_ext/2（接近临界，"
                "dip 深度~89%）。JC 精确对角化逐 qubit 交叉验证色散 χ。"
                "LLM 不进判决路径。",
    }


# ---------------------------------------------------------------------------
# D-44 统一设计包（注册 multiqubit kind）
# ---------------------------------------------------------------------------
def package_from_multiqubit(f01s: Optional[List[float]] = None,
                            **kw: Any) -> Dict[str, Any]:
    """把多 qubit 读出设计包装为 D-44 统一 DesignPackage。"""
    from lda_design.design_package import SCHEMA_VERSION, _now_iso

    if f01s is None:
        f01s = [4.8, 5.0, 5.2]
    r = design_multiqubit_readout(f01s, **kw)
    acc = r["acceptance"]
    return {
        "package_id": f"multiqubit-{r['n_qubits']}q",
        "schema_version": SCHEMA_VERSION,
        "kind": "multiqubit", "domain": "hybrid",
        "title": r["title"],
        "created_at": _now_iso(),
        "ir": {"schema_version": r["ir"]["schema_version"],
               "domain": r["ir"]["domain"],
               "n_components": r["ir"]["n_components"],
               "n_nets": r["ir"]["n_nets"],
               "validate_errors": r["ir"]["validate_errors"]},
        "design": {"targets": {"f01s_ghz": r["f01s_ghz"],
                               "delta_ghz": r["delta_ghz"],
                               "g_ghz": r["g_ghz"]},
                   "params": {"readout_freqs_ghz": r["readout_freqs_ghz"],
                              "kappa_r_ghz": r["kappa_r_ghz"],
                              "kappa_ext_ghz": r["kappa_ext_ghz"],
                              "kappa_i_ghz": r["kappa_i_ghz"],
                              "chi_ghz": r["chi_ghz"],
                              "qubits": r["qubits"]},
                   "inverse_design": {"formula": "E_J/l/Cc/Q_ext 闭式反解"
                                                 "（每 qubit，复用 D-41）"}},
        "verification": {"checks": acc["checks"], "passed": bool(acc["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"spectrum": r["spectrum"],
                      "dip_resolvability": r["dip_resolvability"]},
        "honest_notes": r.get("note", ""),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="LDA N-qubit 频率复用读出系统设计")
    ap.add_argument("--f01s", default="4.8,5.0,5.2",
                    help="qubit 频率(GHz)，逗号分隔")
    ap.add_argument("--delta", type=float, default=_DEF_DELTA)
    ap.add_argument("--g", type=float, default=_DEF_G)
    ap.add_argument("--kappa_ext", type=float, default=_DEF_KAPPA_EXT)
    ap.add_argument("--kappa_i", type=float, default=None)
    args = ap.parse_args()
    f01s = [float(x) for x in args.f01s.split(",") if x.strip()]
    r = design_multiqubit_readout(
        f01s, delta=args.delta, g=args.g, kappa_ext=args.kappa_ext,
        kappa_i=args.kappa_i)
    print(json.dumps({k: r[k] for k in
                      ("title", "f01s_ghz", "readout_freqs_ghz", "qubits",
                       "spectrum", "dip_resolvability", "ir", "acceptance",
                       "verdict")}, ensure_ascii=False, indent=2))
    return 0 if r["acceptance"]["passed"] else 1


def _ensure_path() -> None:
    try:
        from lda_l2.device_library import _ensure_solver_on_path
        _ensure_solver_on_path()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
