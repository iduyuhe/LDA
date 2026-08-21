"""D-51: N-qubit 复用读出逐 qubit 保真度预算（D-46 × D-47 集成）。

把 D-46（N-qubit 频率复用读出：信道错开 ≥3×κ_r、力线 dip 可分辨、
混合 IR 网表 3N+1）与 D-47（单发读出保真度：相位积分 SNR、T1 污染、
最优 t_m*、非破坏 n̄≤100）合并为**一个系统设计闭环**：

  N qubit 沿公共力线频率复用读出（D-46 复用）
  × 每 qubit 独立保真度预算（D-47 复用：逐 qubit T1 / n̄ 可不同）
  → 系统级验收 = 复用验收（全部信道错开 + dip 可分辨）
                + 逐 qubit 保真度验收（SNR/F/F1/t_m*/T1/n̄ 全过）
  → 混合 IR 网表（3N+1）+ D-44 统一设计包（kind=multiqubit_fidelity）

物理模型（LLM 不进判决路径，全部复用已验证实现）：
  · χ = g²/Δ；κ_r = κ_ext + κ_i（D-43/D-46）
  · SNR = 2·χ_rad·√(n̄·η·t_m/(κ_rad·(1+2N_amp)))（D-47，角频率约定）
  · F0 = 1−½erfc(SNR/√2)；F1 = (1−ε)(1−t_m/T1)；F = (F0+F1)/2（D-47）
  · t_m* = argmax F(t_m)，扫描 [0.2/κ_r, min(1µs, T1/2)]（D-47）
  · dip 可分辨：相邻读出频率中点透射 > 0.5（D-46）
"""

import argparse
import json
import math
import sys
from typing import Any, Dict, List, Optional

from lda_ir import (  # type: ignore
    IRModel, ObjectiveSpec, Resonator, Transmon, Waveguide, validate,
)
from lda_agent.multiqubit_readout import (  # type: ignore
    dip_resolvable, feedline_spectrum,
)
from lda_agent.readout_fidelity import (  # type: ignore
    optimize_readout_time, readout_fidelity,
)

# 物理默认（与 D-46/D-47 一致）
_DEF_DELTA = 1.0
_DEF_G = 0.10
_DEF_KAPPA_EXT = 0.005
_DEF_KAPPA_I = None            # 默认 κ_ext/2（接近临界）
_DEF_ETA = 0.5
_DEF_N_AMP = 5.0
_DEF_NBAR = 10.0
_DEF_T1_US_LIST = None         # 默认逐 qubit 均 20µs
_F_MIN = 0.95
_SNR_MIN = 2.0
_NBAR_MAX = 100.0


# ---------------------------------------------------------------------------
# 主闭环
# ---------------------------------------------------------------------------
def design_multiqubit_fidelity(
        f01s: List[float], delta: float = _DEF_DELTA, g: float = _DEF_G,
        kappa_ext: float = _DEF_KAPPA_EXT, kappa_i: Optional[float] = None,
        T1_us_list: Optional[List[float]] = None,
        nbar_list: Optional[List[float]] = None, eta: float = _DEF_ETA,
        N_amp: float = _DEF_N_AMP, Lp: float = 0.4e-6, Cp: float = 1.5e-10,
) -> Dict[str, Any]:
    """N-qubit 复用读出逐 qubit 保真度预算闭环。"""
    if kappa_i is None:
        kappa_i = kappa_ext / 2.0
    kappa_r = kappa_ext + kappa_i
    n = len(f01s)
    f01s = sorted(f01s)
    fr = [f + delta for f in f01s]
    chi = g * g / abs(delta)
    if T1_us_list is None:
        T1_us_list = [20.0] * n
    if nbar_list is None:
        nbar_list = [_DEF_NBAR] * n
    if len(T1_us_list) != n or len(nbar_list) != n:
        raise ValueError("T1_us_list / nbar_list 长度须与 f01s 一致")

    # 1) 逐 qubit 保真度预算（复用 D-47）
    per_qubit: List[Dict[str, Any]] = []
    for i, (f01, f_r, T1_us, nbar) in enumerate(
            zip(f01s, fr, T1_us_list, nbar_list)):
        T1_s = T1_us * 1e-6
        tm_star, b = optimize_readout_time(chi, kappa_r, nbar, eta, N_amp,
                                           T1_s)
        per_qubit.append({
            "qid": f"q{i + 1}", "f01_ghz": f01, "f_r_ghz": round(f_r, 4),
            "T1_us": T1_us, "nbar": nbar,
            "t_m_star_ns": round(tm_star * 1e9, 1),
            "budget": {k: round(v, 6) if isinstance(v, float) else v
                       for k, v in b.items()},
        })

    # 2) 频率复用（复用 D-46）
    resolv = dip_resolvable(fr, kappa_ext, kappa_i)
    spacing_ok = True
    for i in range(n - 1):
        if fr[i + 1] - fr[i] < 3.0 * kappa_r:
            spacing_ok = False

    # 3) 系统验收（复用 + 逐 qubit 保真度联合）
    checks: List[Dict[str, Any]] = [
        {"name": f"读出频率错开（间隔 ≥ 3×κ_r={kappa_r}GHz）",
         "ok": bool(spacing_ok),
         "detail": ("；".join(
             f"Δf{fr[i + 1]:.4f}−{fr[i]:.4f}={fr[i + 1] - fr[i]:.4f}GHz"
             for i in range(n - 1)) if n > 1 else "单 qubit")},
        {"name": "力线 dip 可分辨（相邻中点透射 > 0.5）",
         "ok": bool(all(r["resolvable"] for r in resolv)),
         "detail": "；".join(
             f"{r['f0_ghz']}↔{r['f1_ghz']}GHz 中点 T={r['mid_T']}"
             for r in resolv) if resolv else "单 dip"},
        {"name": "色散区有效（Δ/g ≥ 5）", "ok": bool(abs(delta) / g >= 5.0),
         "detail": f"Δ/g={abs(delta) / g:.1f}"},
        {"name": "读出可分辨（χ=g²/Δ ≥ κ_r）",
         "ok": bool(chi >= kappa_r),
         "detail": f"χ={chi:.4f}GHz vs κ_r={kappa_r}GHz（χ/κ={chi / kappa_r:.1f}）"},
    ]
    for i, q in enumerate(per_qubit):
        b = q["budget"]
        ok_i = (b["snr"] >= _SNR_MIN and b["F"] >= _F_MIN
                and b["F1"] >= _F_MIN and q["T1_us"] > 0
                and q["nbar"] <= _NBAR_MAX)
        checks.append({
            "name": f"q{i + 1} 单发保真度（SNR≥{_SNR_MIN}/F≥{_F_MIN}/"
                    f"F1≥{_F_MIN}/n̄≤{_NBAR_MAX:.0f}）",
            "ok": bool(ok_i),
            "detail": (f"t_m*={q['t_m_star_ns']}ns → SNR={b['snr']:.2f} "
                       f"F={b['F']:.4f}(F1={b['F1']:.4f}) T1={q['T1_us']}µs "
                       f"n̄={q['nbar']}")})

    # 4) 混合 IR 网表（3N+1，domain=hybrid）
    comps: List[Any] = [Waveguide(id="feedline", width=0.5)]
    objectives = [ObjectiveSpec(bid="B9", target=f01s[0], tol=0.1,
                                role="objective")]
    for i, (f01, f_r) in enumerate(zip(f01s, fr)):
        E_J = (f01 + 0.25) ** 2 / (8.0 * 0.25)
        l = 1.0 / (4.0 * f_r * 1e9 * math.sqrt(Lp * Cp))
        comps.append(Transmon(id=f"q{i + 1}", E_J=E_J, E_C=0.25))
        comps.append(Resonator(id=f"r{i + 1}", Lp=Lp, Cp=Cp, l=l,
                               l_bounds=(l * 0.5, l * 1.5)))
        objectives.append(ObjectiveSpec(bid="B12", target=round(f_r, 4),
                                        tol=0.02, role="objective"))
    model = IRModel(
        domain="hybrid", name="multiqubit-readout-fidelity",
        components=comps, objectives=objectives,
        notes=f"{n}-qubit 复用读出逐 qubit 保真度：f01={f01s} → readout "
              f"{fr}GHz（Δ={delta}, g={g}, κ_r={kappa_r}GHz），逐 qubit "
              f"T1={T1_us_list}µs / n̄={nbar_list}",
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
    span_mhz = (fr[-1] - fr[0]) * 1000 if n > 1 else 0.0
    fmin = min(q["budget"]["F"] for q in per_qubit)
    verdict = (
        f"{n}-qubit 复用读出逐 qubit 保真度 PASS：readout 沿力线错开 "
        f"（跨度 {span_mhz:.0f}MHz，dip 全可分辨）；逐 qubit F ∈ "
        f"[{fmin:.4f}, {max(q['budget']['F'] for q in per_qubit):.4f}] "
        f"（t_m*={[q['t_m_star_ns'] for q in per_qubit]}ns），"
        f"χ/κ_r={chi / kappa_r:.1f}。"
        if accepted else
        "多 qubit 保真度未全过：" + "; ".join(
            c["name"] for c in checks if not c["ok"]))

    return {
        "ok": True,
        "title": f"{n}-qubit 复用读出逐 qubit 保真度（D-46×D-47 集成）",
        "n_qubits": n, "f01s_ghz": f01s, "readout_freqs_ghz": fr,
        "delta_ghz": delta, "g_ghz": g,
        "kappa_r_ghz": kappa_r, "chi_ghz": round(chi, 6),
        "per_qubit": per_qubit,
        "spectrum": feedline_spectrum(fr, kappa_ext, kappa_i),
        "dip_resolvability": resolv,
        "ir": {"schema_version": model.schema_version,
               "domain": model.domain, "n_components": len(model.components),
               "n_nets": len(model.nets), "validate_errors": ir_errs},
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": "逐 qubit 保真度模型复用 D-47（相位积分 SNR + T1 污染 + "
                "t_m* 优化 + n̄≤100 非破坏）；频率复用复用 D-46（信道错开 "
                "≥3×κ_r + dip 可分辨）。逐 qubit T1/n̄ 可独立设置——坏 qubit "
                "独立 FAIL 不影响他者。LLM 不进判决路径。",
    }


# ---------------------------------------------------------------------------
# D-44 统一设计包（注册 multiqubit_fidelity kind）
# ---------------------------------------------------------------------------
def package_from_multiqubit_fidelity(
        f01s: Optional[List[float]] = None, **kw: Any) -> Dict[str, Any]:
    """把逐 qubit 保真度设计包装为 D-44 统一 DesignPackage。"""
    from lda_design.design_package import SCHEMA_VERSION, _now_iso

    if f01s is None:
        f01s = [4.8, 5.0, 5.2]
    r = design_multiqubit_fidelity(f01s, **kw)
    acc = r["acceptance"]
    return {
        "package_id": f"multiqubit-fidelity-{r['n_qubits']}q",
        "schema_version": SCHEMA_VERSION,
        "kind": "multiqubit_fidelity", "domain": "hybrid",
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
                              "chi_ghz": r["chi_ghz"],
                              "per_qubit": r["per_qubit"]},
                   "inverse_design": {"formula": "E_J/l/Cc 闭式反解 + "
                                                 "SNR/保真度闭式预算"}},
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
    ap = argparse.ArgumentParser(
        description="LDA N-qubit 复用读出逐 qubit 保真度预算")
    ap.add_argument("--f01s", default="4.8,5.0,5.2",
                    help="qubit 频率(GHz)，逗号分隔")
    ap.add_argument("--delta", type=float, default=_DEF_DELTA)
    ap.add_argument("--g", type=float, default=_DEF_G)
    ap.add_argument("--t1_us", default=None,
                    help="逐 qubit T1(µs)，逗号分隔；缺省全 20")
    ap.add_argument("--nbar", default=None,
                    help="逐 qubit 读出光子数，逗号分隔；缺省全 10")
    args = ap.parse_args()
    f01s = [float(x) for x in args.f01s.split(",") if x.strip()]
    t1_list = ([float(x) for x in args.t1_us.split(",") if x.strip()]
               if args.t1_us else None)
    nbar_list = ([float(x) for x in args.nbar.split(",") if x.strip()]
                 if args.nbar else None)
    r = design_multiqubit_fidelity(f01s, delta=args.delta, g=args.g,
                                   T1_us_list=t1_list, nbar_list=nbar_list)
    print(json.dumps({k: r[k] for k in
                      ("title", "per_qubit", "spectrum", "dip_resolvability",
                       "ir", "acceptance", "verdict")},
                     ensure_ascii=False, indent=2))
    return 0 if r["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
