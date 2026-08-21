"""D-47: 单发读出保真度预算（T1 限制 · SNR(t_m) 扫描 · 最优读出时间）。

在 D-43/D-46 色散读出架构上，从"读出可分辨（χ≥κ_r）"推进到
**读出保真度可预算**：给定 χ/κ_r/T1/读出光子数/放大器噪声，输出
单发读出 SNR、|0⟩/|1⟩ 保真度、最优读出时间与死标量验收判决。

物理模型（LLM 不进判决路径，Krantz 2019 / Gambetta 2008 综述工程标准）：
  · 色散位移（频率）：χ = g²/Δ（复用 D-43）
  · 相位积分（匹配滤波）单发读出 SNR（角频率约定，单调无振荡伪影）：
      SNR = 2·χ_rad·√( n̄·η·t_m / (κ_rad·(1+2N_amp)) )
    χ_rad = 2π·χ, κ_rad = 2π·κ_r
  · 误判概率：ε = ½·erfc(SNR/√2)（|0⟩/|1⟩ 高斯点重叠）
  · T1 弛豫污染：F1 = (1−ε)·(1 − t_m/T1)（一阶，t_m ≪ T1）
  · 保真度：F0 = 1−ε；F = (F0+F1)/2
  · 最优读出时间：t_m* = argmax F(t_m)（SNR 增 vs T1 污染增），
    扫描范围 [0.2/κ_r, min(1µs, T1/2)]
  · 非破坏性约束：平均读出光子数 n̄ ≤ 100（防激发 qubit）

验收（死标量比对）：
  SNR(t_m*) ≥ 2.0 · F(t_m*) ≥ 0.95 · t_m*/T1 ≤ 0.1（污染预算）
  · n̄ ≤ 100（非破坏） · χ ≥ κ_r（读出可分辨，复用） · Δ/g ≥ 5（色散区）

输出：D-44 统一设计包（kind=readout_fidelity）+ 预算表 + 扫描曲线 + 混合 IR。
"""

import argparse
import json
import math
import sys
from typing import Any, Dict, List, Optional, Tuple

from lda_ir import (  # type: ignore
    IRModel, ObjectiveSpec, Resonator, Transmon, Waveguide, validate,
)

# 物理默认（GHz / µs / 无量纲）
_DEF_F01 = 5.0
_DEF_DELTA = 1.0
_DEF_G = 0.10
_DEF_KAPPA_R = 0.005
_DEF_T1_US = 20.0          # 超导 qubit 典型 T1
_DEF_NBAR = 10.0           # 平均读出光子数（非破坏读出典型 <100）
_DEF_ETA = 0.5             # 读出效率（量子效率 × 引线损耗）
_DEF_N_AMP = 5.0           # 放大器噪声光子数（HEMT 典型 5-10）
_NBAR_MAX = 100.0
_F_MIN = 0.95
_SNR_MIN = 2.0


# ---------------------------------------------------------------------------
# 保真度模型
# ---------------------------------------------------------------------------
def readout_snr(chi_ghz: float, kappa_r_ghz: float, nbar: float, eta: float,
                N_amp: float, t_m_s: float) -> float:
    """单发读出 SNR（相位积分/匹配滤波，角频率约定）。

    SNR = 2·χ_rad·√(n̄·η·t_m/(κ_rad·(1+2N_amp)))
    """
    chi_rad = 2.0 * math.pi * chi_ghz * 1e9
    kap_rad = 2.0 * math.pi * kappa_r_ghz * 1e9
    return (2.0 * chi_rad *
            math.sqrt(nbar * eta * t_m_s / (kap_rad * (1.0 + 2.0 * N_amp))))


def readout_fidelity(chi_ghz: float, kappa_r_ghz: float, nbar: float,
                     eta: float, N_amp: float, t_m_s: float,
                     T1_s: float) -> Dict[str, float]:
    """给定读出时间 t_m 的保真度预算。"""
    snr = readout_snr(chi_ghz, kappa_r_ghz, nbar, eta, N_amp, t_m_s)
    eps = 0.5 * math.erfc(snr / math.sqrt(2.0))
    F0 = 1.0 - eps
    F1 = (1.0 - eps) * (1.0 - t_m_s / T1_s)
    return {"t_m_s": t_m_s, "snr": snr, "eps": eps, "F0": F0, "F1": F1,
            "F": (F0 + F1) / 2.0, "t1_pollution": t_m_s / T1_s}


def optimize_readout_time(chi_ghz: float, kappa_r_ghz: float, nbar: float,
                          eta: float, N_amp: float, T1_s: float,
                          n_scan: int = 401) -> Tuple[float, Dict[str, float]]:
    """扫描 t_m 最大化 F（SNR 增长 vs T1 污染增长）。

    扫描范围：[0.2/κ_r, min(1µs, T1/2)]，其中 0.2/κ_r 保证谐振器填充。
    """
    kap_rad = 2.0 * math.pi * kappa_r_ghz * 1e9
    t_min = 0.2 / kap_rad
    t_max = min(1e-6, T1_s / 2.0)
    if t_max <= t_min:
        t_max = t_min * 2.0
    best_t, best_f, best_b = t_min, -1.0, None
    for i in range(n_scan):
        tm = t_min + (t_max - t_min) * i / (n_scan - 1)
        b = readout_fidelity(chi_ghz, kappa_r_ghz, nbar, eta, N_amp, tm, T1_s)
        if b["F"] > best_f:
            best_t, best_f, best_b = tm, b["F"], b
    return best_t, best_b


def fidelity_sweep(chi_ghz: float, kappa_r_ghz: float, nbar: float, eta: float,
                   N_amp: float, T1_s: float, n_pts: int = 16) -> List[Dict[str, float]]:
    """预算表：t_m 采样点上的 SNR/保真度（供报告/曲线）。"""
    kap_rad = 2.0 * math.pi * kappa_r_ghz * 1e9
    t_min = 0.2 / kap_rad
    t_max = min(1e-6, T1_s / 2.0)
    out = []
    for i in range(n_pts):
        tm = t_min + (t_max - t_min) * i / (n_pts - 1)
        b = readout_fidelity(chi_ghz, kappa_r_ghz, nbar, eta, N_amp, tm, T1_s)
        out.append({k: round(v, 6) if isinstance(v, float) else v
                    for k, v in b.items()})
    return out


# ---------------------------------------------------------------------------
# 主闭环
# ---------------------------------------------------------------------------
def design_fidelity(f01: float = _DEF_F01, delta: float = _DEF_DELTA,
                    g: float = _DEF_G, kappa_r: float = _DEF_KAPPA_R,
                    T1_us: float = _DEF_T1_US, nbar: float = _DEF_NBAR,
                    eta: float = _DEF_ETA, N_amp: float = _DEF_N_AMP,
                    ) -> Dict[str, Any]:
    """单发读出保真度预算闭环。"""
    T1_s = T1_us * 1e-6
    chi = g * g / abs(delta)
    f_r = f01 + delta
    Q_ext = f_r / kappa_r

    # 1) 最优读出时间 + 保真度预算
    tm_star, b_star = optimize_readout_time(chi, kappa_r, nbar, eta, N_amp, T1_s)
    sweep = fidelity_sweep(chi, kappa_r, nbar, eta, N_amp, T1_s)

    # 2) 死标量验收
    checks = [
        {"name": "色散区有效（Δ/g ≥ 5）", "ok": bool(abs(delta) / g >= 5.0),
         "detail": f"Δ/g={abs(delta) / g:.1f}"},
        {"name": "读出可分辨（χ ≥ κ_r）", "ok": bool(chi >= kappa_r),
         "detail": f"χ={chi:.4f}GHz vs κ_r={kappa_r}GHz（χ/κ={chi / kappa_r:.1f}）"},
        {"name": f"单发 SNR ≥ {_SNR_MIN}", "ok": bool(b_star["snr"] >= _SNR_MIN),
         "detail": f"SNR(t_m*)={b_star['snr']:.2f}（t_m*={tm_star * 1e9:.0f}ns）"},
        {"name": f"读出保真度 F ≥ {_F_MIN}", "ok": bool(b_star["F"] >= _F_MIN),
         "detail": f"F={b_star['F']:.4f}（F0={b_star['F0']:.4f}·F1={b_star['F1']:.4f}）"},
        {"name": "|1⟩ 态保真度 F1 ≥ 0.95（T1 污染直接门槛）",
         "ok": bool(b_star["F1"] >= 0.95),
         "detail": f"F1={b_star['F1']:.4f}（t_m*/T1={tm_star / T1_s * 100:.2f}%）"},
        {"name": "读出时间污染预算（t_m*/T1 ≤ 0.1）",
         "ok": bool(tm_star / T1_s <= 0.1),
         "detail": f"t_m*/T1={tm_star / T1_s * 100:.2f}%"},
        {"name": f"非破坏性读出（n̄ ≤ {_NBAR_MAX:.0f}）",
         "ok": bool(nbar <= _NBAR_MAX),
         "detail": f"n̄={nbar} 光子（读出脉冲不激发 qubit）"},
    ]

    # 3) 混合 IR 网表（domain=hybrid，回溯设计意图）
    l_design = 1.0 / (4.0 * f_r * 1e9 * math.sqrt(0.4e-6 * 1.5e-10))
    model = IRModel(
        domain="hybrid", name="readout-fidelity-budget",
        components=[Transmon(id="q1", E_J=(f01 + 0.25) ** 2 / (8.0 * 0.25),
                             E_C=0.25),
                    Resonator(id="r1", Lp=0.4e-6, Cp=1.5e-10,
                              l=l_design,
                              l_bounds=(l_design * 0.5, l_design * 1.5)),
                    Waveguide(id="feedline", width=0.5)],
        objectives=[ObjectiveSpec(bid="B9", target=f01, tol=0.1,
                                  role="objective"),
                    ObjectiveSpec(bid="B12", target=round(f_r, 4), tol=0.02,
                                  role="objective")],
        notes=f"单发读出保真度预算：f01={f01}GHz, Δ={delta}GHz, g={g}GHz, "
              f"κ_r={kappa_r}GHz, T1={T1_us}µs, n̄={nbar}, η={eta}, "
              f"N_amp={N_amp} → t_m*={tm_star * 1e9:.0f}ns, F={b_star['F']:.4f}",
    )
    model.connect("qc", "q1.readout", "r1.in")
    model.connect("ro", "r1.out", "feedline.in")
    ir_errs = validate(model)
    checks.insert(0, {"name": "混合 IR 网表校验（hybrid）", "ok": not ir_errs,
                      "detail": f"{len(model.components)} 器件 + "
                                f"{len(model.nets)} 网表"
                                f"{'；' + '；'.join(ir_errs[:3]) if ir_errs else ' 通过'}"})

    accepted = all(c["ok"] for c in checks)
    verdict = (
        f"单发读出保真度预算 PASS：t_m*={tm_star * 1e9:.0f}ns → "
        f"SNR={b_star['snr']:.2f}（误判 {b_star['eps']:.2e}），F="
        f"{b_star['F']:.4f}（T1 污染 {tm_star / T1_s * 100:.2f}%），"
        f"χ/κ_r={chi / kappa_r:.1f}，n̄={nbar:.0f} 非破坏。"
        if accepted else
        "读出保真度预算未全过：" + "; ".join(
            c["name"] for c in checks if not c["ok"]))

    return {
        "ok": True,
        "title": "单发读出保真度预算（T1 限制 · SNR/保真度）",
        "f01_ghz": f01, "delta_ghz": delta, "g_ghz": g,
        "kappa_r_ghz": kappa_r, "chi_ghz": round(chi, 6),
        "T1_us": T1_us, "nbar": nbar, "eta": eta, "N_amp": N_amp,
        "t_m_star_ns": round(tm_star * 1e9, 1),
        "budget": {k: round(v, 6) if isinstance(v, float) else v
                   for k, v in b_star.items()},
        "sweep": sweep,
        "ir": {"schema_version": model.schema_version,
               "domain": model.domain, "n_components": len(model.components),
               "n_nets": len(model.nets), "validate_errors": ir_errs},
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": "SNR=相位积分（匹配滤波）模型：SNR=2·χ_rad·√(n̄·η·t_m/"
                "(κ_rad·(1+2N_amp)))，χ/κ_r 为角频率约定；误判 ε=½erfc(SNR/√2)；"
                "T1 污染 F1=(1−ε)(1−t_m/T1) 一阶；t_m* 在 [0.2/κ_r, "
                "min(1µs, T1/2)] 扫描最大化 F。n̄≤100 为非破坏读出经验上限。"
                "LLM 不进判决路径。",
    }


# ---------------------------------------------------------------------------
# D-44 统一设计包（注册 readout_fidelity kind）
# ---------------------------------------------------------------------------
def package_from_readout_fidelity(f01: float = _DEF_F01, **kw: Any) -> Dict[str, Any]:
    """把保真度预算包装为 D-44 统一 DesignPackage。"""
    from lda_design.design_package import SCHEMA_VERSION, _now_iso

    r = design_fidelity(f01=f01, **kw)
    acc = r["acceptance"]
    return {
        "package_id": f"readout-fidelity-f01{f01}-t1{r['T1_us']}",
        "schema_version": SCHEMA_VERSION,
        "kind": "readout_fidelity", "domain": "hybrid",
        "title": r["title"],
        "created_at": _now_iso(),
        "ir": {"schema_version": r["ir"]["schema_version"],
               "domain": r["ir"]["domain"],
               "n_components": r["ir"]["n_components"],
               "n_nets": r["ir"]["n_nets"],
               "validate_errors": r["ir"]["validate_errors"]},
        "design": {"targets": {"f01_ghz": f01, "delta_ghz": r["delta_ghz"],
                               "g_ghz": r["g_ghz"], "kappa_r_ghz": r["kappa_r_ghz"]},
                   "params": {"T1_us": r["T1_us"], "nbar": r["nbar"],
                              "eta": r["eta"], "N_amp": r["N_amp"],
                              "t_m_star_ns": r["t_m_star_ns"],
                              "budget": r["budget"]},
                   "inverse_design": {"formula": "χ=g²/Δ；SNR/保真度闭式预算"}},
        "verification": {"checks": acc["checks"], "passed": bool(acc["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"sweep": r["sweep"]},
        "honest_notes": r.get("note", ""),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="LDA 单发读出保真度预算")
    ap.add_argument("--f01", type=float, default=_DEF_F01)
    ap.add_argument("--delta", type=float, default=_DEF_DELTA)
    ap.add_argument("--g", type=float, default=_DEF_G)
    ap.add_argument("--kappa_r", type=float, default=_DEF_KAPPA_R)
    ap.add_argument("--t1_us", type=float, default=_DEF_T1_US)
    ap.add_argument("--nbar", type=float, default=_DEF_NBAR)
    ap.add_argument("--eta", type=float, default=_DEF_ETA)
    ap.add_argument("--n_amp", type=float, default=_DEF_N_AMP)
    args = ap.parse_args()
    r = design_fidelity(f01=args.f01, delta=args.delta, g=args.g,
                        kappa_r=args.kappa_r, T1_us=args.t1_us,
                        nbar=args.nbar, eta=args.eta, N_amp=args.n_amp)
    print(json.dumps({k: r[k] for k in
                      ("title", "chi_ghz", "t_m_star_ns", "budget", "sweep",
                       "ir", "acceptance", "verdict")},
                     ensure_ascii=False, indent=2))
    return 0 if r["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
