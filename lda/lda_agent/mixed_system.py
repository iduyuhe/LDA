"""D-52: 多环 WDM × 量子读出混合巨型系统（光子分波 + 量子读出同一网表）。

把 D-42（WDM 多环分波网络，1550nm 光频段）与 D-51（N-qubit 频率复用
读出，微波 GHz 段）放进**同一个 IR 网表、同一个设计包**：

  光子域：N 信道 WDM 分波器（复用 D-42：谐振对齐 R、级联传递、
          IL≤3dB / XT≥15dB / DRC / 单 FSR 防混叠）
  量子域：N qubit 频率复用读出（复用 D-51：信道错开≥3κ_r、dip 可分辨、
          逐 qubit 保真度 t_m*/SNR/F）
  桥接：  WDM 信道 i ↔ qubit i 读出 1:1 映射（光控量子芯片的接口规划）
  系统验收 = 光子子验收 + 量子子验收 + 全局（映射完整 + 混合 IR 全 valid）

物理模型（LLM 不进判决路径，全部复用已验证实现）：
  · WDM：add-drop 传递函数级联（D-37/D-42，SOI 220nm 解析模型）
  · 读出：χ=g²/Δ；SNR=2χ_rad√(n̄ηt_m/(κ_rad(1+2N_amp)))；F1=(1−ε)(1−t_m/T1)
          （D-47/D-51）
  · 诚实标注：光（1550nm）↔ 微波（GHz）两子系统物理独立，桥接为
    芯片级接口规划（光电转换不在本模型内），不假装统一物理模型。

输出：D-44 统一设计包（kind=mixed_system，spec/schema 8 kind）。
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from lda_ir import (  # type: ignore
    IRModel, ObjectiveSpec, Resonator, RingResonator, Transmon, Waveguide,
    validate,
)
from lda_agent.wdm_system import design_wdm  # type: ignore
from lda_agent.multiqubit_fidelity import design_multiqubit_fidelity  # type: ignore

# 默认参数（光子 WDM 3 信道 + 量子 3 qubit）
_DEF_CHANNELS_NM = [1550.0, 1553.0, 1556.0]
_DEF_F01S_GHZ = [4.8, 5.0, 5.2]
_DEF_GAP_UM = 0.3
_DEF_T1_US = [20.0, 15.0, 25.0]


# ---------------------------------------------------------------------------
# 主闭环
# ---------------------------------------------------------------------------
def design_mixed_system(
        wdm_channels_nm: Optional[List[float]] = None,
        qubit_f01s_ghz: Optional[List[float]] = None,
        wdm_gap_um: float = _DEF_GAP_UM,
        delta_ghz: float = 1.0, g_ghz: float = 0.10,
        T1_us_list: Optional[List[float]] = None,
        nbar_list: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """多环 WDM × 量子读出混合巨型系统设计闭环。"""
    if wdm_channels_nm is None:
        wdm_channels_nm = list(_DEF_CHANNELS_NM)
    if qubit_f01s_ghz is None:
        qubit_f01s_ghz = list(_DEF_F01S_GHZ)
    n_wdm = len(wdm_channels_nm)
    n_q = len(qubit_f01s_ghz)

    # 1) 光子子网络（复用 D-42）
    wdm = design_wdm(wdm_channels_nm, gap=wdm_gap_um)

    # 2) 量子子网络（复用 D-51）
    qu = design_multiqubit_fidelity(
        qubit_f01s_ghz, delta=delta_ghz, g=g_ghz,
        T1_us_list=T1_us_list, nbar_list=nbar_list)

    # 3) 全局验收
    checks: List[Dict[str, Any]] = []
    # 3a) 映射完整性（1:1 信道 ↔ qubit）
    mapping_ok = n_wdm == n_q
    mapping = ([{"channel_nm": ch, "qubit_f01_ghz": f01,
                 "readout_ghz": fr}
                for ch, f01, fr in zip(wdm_channels_nm, qubit_f01s_ghz,
                                       qu["readout_freqs_ghz"])]
               if mapping_ok else [])
    checks.append({
        "name": "WDM 信道 ↔ qubit 1:1 映射完整",
        "ok": bool(mapping_ok),
        "detail": f"{n_wdm} 信道 ↔ {n_q} qubit"
                  + ("" if mapping_ok else "（数目不匹配）")})
    # 3b) 光子子验收（D-42 摘要）
    wdm_acc = wdm["acceptance"]
    checks.append({
        "name": "光子子网络验收（WDM）",
        "ok": bool(wdm_acc["passed"]),
        "detail": (f"{sum(1 for c in wdm_acc['checks'] if c['ok'])}/"
                   f"{len(wdm_acc['checks'])} 项：IL≤"
                   f"{max(wdm['metrics']['il_drop_db']):.2f}dB XT≥"
                   f"{min(wdm['metrics']['xt_min_db']):.1f}dB")})
    # 3c) 量子子验收（D-51 摘要）
    qu_acc = qu["acceptance"]
    f_list = [q["budget"]["F"] for q in qu["per_qubit"]]
    checks.append({
        "name": "量子子网络验收（读出 + 保真度）",
        "ok": bool(qu_acc["passed"]),
        "detail": (f"{sum(1 for c in qu_acc['checks'] if c['ok'])}/"
                   f"{len(qu_acc['checks'])} 项：逐 qubit F∈"
                   f"[{min(f_list):.4f}, {max(f_list):.4f}]")})

    # 4) 混合 IR 网表（光子 WDM 环 + 量子 qubit/readout + 力线）
    comps: List[Any] = []
    objectives: List[Any] = []
    nets: List[Dict[str, Any]] = []
    # 光子域：N 个 WDM 环（D-42 IR 组件复刻）
    for i, (ch, R) in enumerate(zip(wdm_channels_nm, wdm["ring_radii_um"])):
        comps.append(RingResonator(id=f"w{i + 1}", R=round(float(R), 4),
                                   n_g=4.2))
        objectives.append(ObjectiveSpec(
            bid="B4", target=round(ch ** 2 / (4.2 * 2 * 3.14159 * float(R)), 3),
            tol=1e-3, role="objective"))
    for i in range(n_wdm - 1):
        nets.append({"id": f"wdm{i + 1}", "connects": [f"w{i + 1}.out",
                                                       f"w{i + 2}.in"]})
    # 量子域：N qubit + N readout + feedline（复用 D-51 组件）
    import math
    comps.append(Waveguide(id="feedline", width=0.5))
    for i, (f01, f_r, q) in enumerate(zip(qubit_f01s_ghz,
                                          qu["readout_freqs_ghz"],
                                          qu["per_qubit"])):
        l = 1.0 / (4.0 * f_r * 1e9 * math.sqrt(0.4e-6 * 1.5e-10))
        comps.append(Transmon(id=f"q{i + 1}",
                              E_J=(f01 + 0.25) ** 2 / (8.0 * 0.25), E_C=0.25))
        comps.append(Resonator(id=f"r{i + 1}", Lp=0.4e-6, Cp=1.5e-10, l=l,
                               l_bounds=(l * 0.5, l * 1.5)))
        objectives.append(ObjectiveSpec(bid="B12", target=round(f_r, 4),
                                        tol=0.02, role="objective"))
        nets.append({"id": f"q{i + 1}r{i + 1}",
                     "connects": [f"q{i + 1}.readout", f"r{i + 1}.in"]})
        nets.append({"id": f"r{i + 1}f", "connects": [f"r{i + 1}.out",
                                                      "feedline.in"]})
    model = IRModel(
        domain="hybrid", name="mixed-wdm-readout",
        components=comps, objectives=objectives,
        notes=f"多环 WDM × 量子读出混合系统：{n_wdm} 信道 WDM（1550nm "
              f"段，R={[round(float(r), 2) for r in wdm['ring_radii_um']]}µm）"
              f"× {n_q} qubit 读出（readout {qu['readout_freqs_ghz']}GHz），"
              f"信道 i ↔ qubit i 1:1 映射",
    )
    for nt in nets:
        model.connect(nt["id"], *nt["connects"])
    ir_errs = validate(model)
    checks.insert(0, {
        "name": "混合 IR 网表校验（光子 WDM + 量子读出同一网表）",
        "ok": not ir_errs,
        "detail": f"{len(model.components)} 器件 + {len(model.nets)} 网表"
                  f"{'；' + '；'.join(ir_errs[:3]) if ir_errs else ' 通过'}"})

    accepted = all(c["ok"] for c in checks)
    verdict = (
        f"混合巨型系统 PASS：{n_wdm} 信道 WDM（IL≤"
        f"{max(wdm['metrics']['il_drop_db']):.2f}dB, XT≥"
        f"{min(wdm['metrics']['xt_min_db']):.1f}dB）× {n_q} qubit 读出"
        f"（逐 qubit F∈[{min(f_list):.4f}, {max(f_list):.4f}]）同一网表，"
        f"信道↔qubit 1:1 映射完整。"
        if accepted else
        "混合系统未全过：" + "; ".join(
            c["name"] for c in checks if not c["ok"]))

    return {
        "ok": True,
        "title": f"{n_wdm}-信道 WDM × {n_q}-qubit 读出混合巨型系统",
        "n_wdm": n_wdm, "n_qubits": n_q,
        "wdm_channels_nm": wdm_channels_nm, "qubit_f01s_ghz": qubit_f01s_ghz,
        "mapping": mapping, "mapping_ok": mapping_ok,
        "photon": {"ring_radii_um": wdm["ring_radii_um"],
                   "metrics": wdm["metrics"],
                   "acceptance": wdm_acc},
        "quantum": {"readout_freqs_ghz": qu["readout_freqs_ghz"],
                    "per_qubit": qu["per_qubit"],
                    "spectrum": qu["spectrum"],
                    "dip_resolvability": qu["dip_resolvability"],
                    "acceptance": qu_acc},
        "ir": {"schema_version": model.schema_version,
               "domain": model.domain, "n_components": len(model.components),
               "n_nets": len(model.nets), "validate_errors": ir_errs},
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": "光子（1550nm WDM，D-42 解析模型）与微波（GHz 读出，D-47/"
                "D-51 模型）两子系统物理独立，桥接为芯片级接口规划（信道 i ↔ "
                "qubit i，光电转换不在本模型内）——不假装统一物理模型，各自"
                "物理定律锚验收。LLM 不进判决路径。",
    }


# ---------------------------------------------------------------------------
# D-44 统一设计包（注册 mixed_system kind）
# ---------------------------------------------------------------------------
def package_from_mixed_system(
        wdm_channels_nm: Optional[List[float]] = None,
        qubit_f01s_ghz: Optional[List[float]] = None, **kw: Any) -> Dict[str, Any]:
    """把混合系统设计包装为 D-44 统一 DesignPackage。"""
    from lda_design.design_package import SCHEMA_VERSION, _now_iso

    r = design_mixed_system(wdm_channels_nm=wdm_channels_nm,
                            qubit_f01s_ghz=qubit_f01s_ghz, **kw)
    acc = r["acceptance"]
    return {
        "package_id": (f"mixed-wdm{r['n_wdm']}-q{r['n_qubits']}"),
        "schema_version": SCHEMA_VERSION,
        "kind": "mixed_system", "domain": "hybrid",
        "title": r["title"],
        "created_at": _now_iso(),
        "ir": {"schema_version": r["ir"]["schema_version"],
               "domain": r["ir"]["domain"],
               "n_components": r["ir"]["n_components"],
               "n_nets": r["ir"]["n_nets"],
               "validate_errors": r["ir"]["validate_errors"]},
        "design": {"targets": {"wdm_channels_nm": r["wdm_channels_nm"],
                               "qubit_f01s_ghz": r["qubit_f01s_ghz"]},
                   "params": {"mapping": r["mapping"],
                              "photon": {"ring_radii_um": r["photon"]["ring_radii_um"]},
                              "quantum": {"readout_freqs_ghz":
                                          r["quantum"]["readout_freqs_ghz"],
                                          "per_qubit": r["quantum"]["per_qubit"]}},
                   "inverse_design": {"formula": "WDM R=m·λ/2πn_g（D-42）+ "
                                                 "E_J/l/Cc 闭式（D-41）"}},
        "verification": {"checks": acc["checks"], "passed": bool(acc["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"photon_metrics": r["photon"]["metrics"],
                      "quantum_spectrum": r["quantum"]["spectrum"],
                      "dip_resolvability": r["quantum"]["dip_resolvability"]},
        "honest_notes": r.get("note", ""),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="LDA 多环 WDM × 量子读出混合系统")
    ap.add_argument("--wdm_channels", default="1550,1553,1556",
                    help="WDM 信道波长(nm)，逗号分隔")
    ap.add_argument("--f01s", default="4.8,5.0,5.2",
                    help="qubit 频率(GHz)，逗号分隔")
    ap.add_argument("--gap", type=float, default=_DEF_GAP_UM)
    ap.add_argument("--t1_us", default=None, help="逐 qubit T1(µs)")
    args = ap.parse_args()
    ch = [float(x) for x in args.wdm_channels.split(",") if x.strip()]
    f01s = [float(x) for x in args.f01s.split(",") if x.strip()]
    t1 = ([float(x) for x in args.t1_us.split(",") if x.strip()]
          if args.t1_us else None)
    r = design_mixed_system(ch, f01s, wdm_gap_um=args.gap, T1_us_list=t1)
    print(json.dumps({k: r[k] for k in
                      ("title", "mapping", "photon", "quantum", "ir",
                       "acceptance", "verdict")},
                     ensure_ascii=False, indent=2, default=str))
    return 0 if r["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
