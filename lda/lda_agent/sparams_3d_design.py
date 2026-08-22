# -*- coding: utf-8 -*-
"""LDA · D-72 深化：3D 端口 S 参数验收 agent 封装（SOI 220nm · numba 核）。

对 MMI 1×2 对称分束器跑**全 3D FDTD 端口透反射谱**验收（复用已验证
numba 3D 核 _fdtd3d_core，零新依赖）：3D 波导截面匹配源注入 → 多端口
DFT 收集 → 输入功率归一 → S 参数谱 → 死标量验收（仿真有效 + 平衡度
≤0.15 + 透射 ≥0.05）+ 2D↔3D 连续性对拍诊断（3D 垂直模式约束使 S 参数
与 2D 系统性不同，差异是物理非 bug，不作判据）。
LLM 不进判决路径。
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

from lda_solver.port_sparams_3d import verify_s_params_3d  # noqa: E402

_DEF_MMI = {"width": 0.5, "W_mmi": 3.0, "L_mmi": 6.0, "L_tap": 3.0,
            "out_gap": 0.5, "L_out": 2.0, "wl0_um": 1.55, "n_wl": 3,
            "span_um": 0.04}


def design_sparams_3d(mmi: Dict[str, Any] | None = None,
                      verbose: bool = False, **kw: Any) -> Dict[str, Any]:
    """3D 端口 S 参数验收（MMI SOI 220nm）。kw 透传求解参数（smoke 提速）。"""
    params = dict(_DEF_MMI)
    if mmi:
        params.update({k: float(v) for k, v in mmi.items()
                       if v is not None})
    vr = verify_s_params_3d(params, **kw)

    pts = vr["spectrum"]["points"]
    checks = [
        {"name": "MMI 3D 端口 S 参数验收（SOI 220nm）",
         "ok": bool(vr["acceptance"]["passed"]),
         "detail": (f"{len(pts)} 波长 · 平衡度 max="
                    f"{max(p['balance'] for p in pts):.3f}（≤0.15）· "
                    f"T_total min={min(p['T_total'] for p in pts):.3f}（≥0.05）")},
        {"name": "2D↔3D 连续性对拍诊断（物理差异，非判据）",
         "ok": True,
         "detail": "; ".join(
             f"λ{d['wl_um']}: bal {d.get('bal_2d', '-')}→{d.get('bal_3d', '-')}"
             for d in vr["diagnostic_2d_vs_3d"][:3])},
    ]
    accepted = all(c["ok"] for c in checks)
    verdict = (
        f"MMI 3D 端口 S 参数验收 PASS：{len(pts)} 波长 S 参数谱（S11/S21/S31）"
        f"满足仿真有效 + 平衡度 + 透射判据；2D↔3D 对拍为诊断量（垂直模式"
        f"约束下的物理差异）。"
        if accepted else
        "未全过：" + "; ".join(c["name"] for c in checks if not c["ok"]))
    return {
        "ok": True,
        "title": "真实器件 3D 端口 S 参数验收（D-72 深化 · SOI 220nm）",
        "geometry": {"MMI_3D": {k: round(float(v), 4)
                                for k, v in params.items()
                                if k not in ("wl0_um", "n_wl", "span_um")},
                     "h_si_um": vr["spectrum"]["h_si_um"],
                     "dl_um": round(1.55 / vr["spectrum"]["dl_factor"], 5)},
        "spectrum": vr["spectrum"],
        "checks": vr["checks"],
        "diagnostic_2d_vs_3d": vr["diagnostic_2d_vs_3d"],
        "acceptance": {"sparams_3d": vr["acceptance"], "passed": accepted},
        "verdict": verdict,
        "note": ("MMI 1×2 对称分束器全 3D FDTD 端口透反射谱（SOI 220nm 波导层"
                 "+上下包层，复用已验证 numba 核 _fdtd3d_core）：3D 波导截面"
                 "匹配源注入（TE 主极化 Ez）→ 多端口 DFT 收集 → 输入功率归一"
                 "→ S 参数谱，能量守恒自动满足。死标量验收：仿真有效 + 平衡度"
                 "≤0.15 + 透射 ≥0.05（自成像对称 ORACLE）。2D↔3D 对拍为诊断量"
                 "（3D 垂直模式约束使 S 参数与 2D 系统性不同，物理差异非 bug）。"
                 "诚实边界：有限高度波导 3D 模场与 2D TEz 本质不同；分束比绝对值"
                 "依赖自成像长度精确设计，不声称与商业 EDA 数值库逐点一致。"
                 "LLM 不进判决路径。"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA D-72 3D 端口 S 参数验收")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--out", default=None, help="报告 JSON 输出路径")
    args = ap.parse_args()
    rep = design_sparams_3d(verbose=args.verbose)
    out = {k: rep[k] for k in ("title", "geometry", "spectrum", "checks",
                               "diagnostic_2d_vs_3d", "acceptance",
                               "verdict", "note")}
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
