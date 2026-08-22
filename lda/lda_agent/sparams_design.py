# -*- coding: utf-8 -*-
"""LDA · D-72 真实器件端口 S 参数验收 agent 封装（2D FDTD + ORACLE 对拍）。

对真实器件（MMI 1×2 对称分束器）跑**全 2D FDTD 端口透反射谱验收**：
  输入 CW 激励 → 输出/回波端口 DFT 收集 → 输入功率归一 → S 参数谱
  （|S11|² 回波 / |S21|² 上输出 / |S31|² 下输出，能量守恒自动满足）
  → 死标量验收（物理定律锚，LLM 不进判决路径）：
    (a) 仿真有效（注入能量被收集）；
    (b) 对称性：双输出平衡度 ≤ 0.15（1×2 对称 MMI + 对称激励 ⇒ 自成像
        对称的必然推论）；
    (c) 透射存在性：S21+S31 ≥ 0.05。
  并演示 **DRC 工艺规则从真实 PDK 注入**（NOEIC/CUMEC/SITRI SOI 180nm
  design_rules → rules_from_pdk → 基元 DRC 自查）。

诚实边界：S 参数为 2D TEz 近似（3D 端口验收为后续工作）；分束比绝对值
依赖自成像长度精确设计，本步不声称与商业 EDA 数值库逐点一致。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_solver.port_sparams import verify_s_params  # noqa: E402
from lda_l2.drc import rules_from_pdk, drc_check_device  # noqa: E402

_DEF_MMI = {"width": 0.5, "W_mmi": 4.0, "L_mmi": 12.0, "L_tap": 3.0,
            "out_gap": 0.5, "L_out": 2.0, "wl0_um": 1.55, "n_wl": 5,
            "span_um": 0.06}


def _pdk_drc_report(params: Dict[str, float]) -> Dict[str, Any]:
    """真实 PDK design_rules 注入 → MMI 基元 DRC 自查（D-21 rules_from_pdk）。"""
    from lda_l2.pdk_examples import build_example_registry
    reg = build_example_registry()
    out = {}
    for key in reg.list_pdks():
        if "SOI 180nm" not in key:
            continue
        pdk = reg.get(key)
        rules = rules_from_pdk(pdk)
        drc = drc_check_device("MMI", params, rules=rules)
        out[key] = {
            "rules": rules,
            "passed": drc.passed,
            "violations": [c.brief() for c in drc.violations()],
        }
    return out


def design_sparams(mmi: Dict[str, Any] | None = None,
                   verbose: bool = False, **kw: Any) -> Dict[str, Any]:
    """D-72 MMI 端口 S 参数验收 + PDK 规则注入 DRC。

    kw 可覆盖 verify_s_params 的求解参数（transient_cycles/dl_factor 等，
    smoke 提速用）。
    """
    params = dict(_DEF_MMI)
    if mmi:
        params.update({k: float(v) for k, v in mmi.items()
                       if v is not None and k != "profile"})
    vr = verify_s_params("MMI", params, **kw)
    pdk = _pdk_drc_report(params)

    checks = [
        {"name": "MMI 2D FDTD 端口 S 参数验收",
         "ok": bool(vr["acceptance"]["passed"]),
         "detail": (f"{len(vr['spectrum']['points'])} 波长 · 平衡度 "
                    f"max={max(p['balance'] for p in vr['spectrum']['points']):.3f}"
                    f"（≤0.15）· T_total min="
                    f"{min(p['T_total'] for p in vr['spectrum']['points']):.3f}"
                    f"（≥0.05）")},
        {"name": "DRC 工艺规则 PDK 注入（NOEIC/CUMEC/SITRI SOI 180nm）",
         "ok": all(v["passed"] for v in pdk.values()),
         "detail": "; ".join(f"{k.split('::')[0]}:{'PASS' if v['passed'] else 'FAIL'}"
                             for k, v in pdk.items())},
    ]
    accepted = all(c["ok"] for c in checks)
    verdict = (
        f"真实器件端口 S 参数验收 PASS：{len(vr['spectrum']['points'])} 波长 "
        f"S 参数谱（S11/S21/S31）满足对称性 + 透射判据；"
        f"3 个真实 SOI 180nm PDK 规则注入 DRC 全绿。"
        f"S 参数为 2D TEz 近似，3D 端口验收为后续工作。"
        if accepted else
        "未全过：" + "; ".join(c["name"] for c in checks if not c["ok"]))
    return {
        "ok": True,
        "title": "真实器件端口 S 参数验收（D-72 · MMI 2D FDTD + ORACLE 对拍）",
        "geometry": {"MMI": {k: round(float(v), 4) for k, v in params.items()
                             if k not in ("wl0_um", "n_wl", "span_um")}},
        "spectrum": vr["spectrum"],
        "checks": vr["checks"],
        "acceptance": {
            "sparams": vr["acceptance"],
            "pdk_drc": {k: {"passed": v["passed"],
                            "violations": v["violations"]}
                        for k, v in pdk.items()},
            "passed": accepted,
        },
        "verdict": verdict,
        "note": ("MMI 1×2 对称分束器全 2D FDTD 端口透反射谱：输入 CW 激励 → "
                 "输出/回波端口 DFT 收集 → 输入功率归一 → S 参数谱，能量守恒"
                 "自动满足。ORACLE=自成像对称性必然推论（对称设计+对称激励⇒"
                 "双输出平衡；无耗散⇒能量守恒），物理定律锚级，非拟合。"
                 "DRC 规则从真实 PDK.design_rules 注入（D-21 rules_from_pdk）。"
                 "诚实边界：2D TEz 近似；分束比绝对值依赖自成像长度精确设计，"
                 "不声称与商业 EDA 数值库逐点一致。LLM 不进判决路径。"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA D-72 端口 S 参数验收")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--out", default=None, help="报告 JSON 输出路径")
    args = ap.parse_args()
    rep = design_sparams(verbose=args.verbose)
    out = {k: rep[k] for k in ("title", "geometry", "spectrum", "checks",
                               "acceptance", "verdict", "note")}
    text = json.dumps(out, ensure_ascii=False, indent=2, default=str)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)),
                    exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"报告已写入 {args.out}")
    print(text)
    return 0 if rep["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
