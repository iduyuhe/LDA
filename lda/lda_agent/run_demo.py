"""LDA · 端到端闭环 demo 运行器（确定性、批处理、无交互）。

演示目标：λ0=1.55µm、Si/SiO2 布拉格镜，目标 R ≥ 0.99（在中心波长）。
跑 DesignAgent 闭环，落盘 DesignOutcomeReport（JSON）+ 可读摘要。

用法：
  python run_demo.py            # 默认布拉格镜演示
  python run_demo.py --target 0.95   # 自定义阈值
"""
from __future__ import annotations

import os
import sys
import json
import time
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from design_loop import DesignAgent, json_report  # noqa: E402
from l1_protocol import dump_json  # noqa: E402


def build_intent(threshold: float, geo: str = "stack") -> dict:
    if geo == "waveguide_2d":
        # 真 2D 波导验收：以"FDTD 对 slab ORACLE 的 neff 一致性"为准（无 R 阈值）
        return {
            "geometry_type": "waveguide",
            "materials": {"sih": 3.48, "silo": 1.44},   # core / clad
            "target_wavelength_um": 1.55,
            "target_metric": "neff",
            "threshold": 1.0,                            # 占位（波导无 R 阈值）
            "tolerance_rel": 0.02,                       # |Δneff|/neff 公差
            "max_iterations": 4,
            "initial_periods": 1,
            "extra": {"width_um": 0.5, "core_ref": "sih", "clad_ref": "silo"},
        }
    return {
        "geometry_type": "bragg_mirror",
        "materials": {"air": 1.0, "sih": 3.48, "silo": 1.44},
        "target_wavelength_um": 1.55,
        "target_metric": "R",
        "threshold": threshold,
        "tolerance_rel": 0.02,
        "max_iterations": 12,
        "initial_periods": 1,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.99, help="目标反射率阈值 R")
    ap.add_argument("--backend", default="numpy", help="求解后端(numpy/numba_cpu/torch_cpu/torch_cuda)")
    ap.add_argument("--geo", default="stack",
                    choices=["stack", "voxel_field", "waveguide_2d"],
                    help="几何原语：stack(层状) | voxel_field(版图→体素) | waveguide_2d(真2D波导)")
    ap.add_argument("--out", default=os.path.join(_HERE, "design_outcome_report.json"),
                    help="报告输出路径")
    args = ap.parse_args()

    intent = build_intent(args.threshold, args.geo)
    intent["geo_kind"] = args.geo
    if args.geo == "waveguide_2d":
        # 波导求解用内置 dl=wl/32 + sponge=80（已验证收敛），不走 stack 的 dl_factor 体系
        intent.setdefault("extra", {})["backend"] = args.backend
    else:
        intent["extra"] = {"backend": args.backend, "dl_factor": 60.0, "sponge": 60, "ramp": 200}

    t0 = time.time()
    agent = DesignAgent(backend=args.backend, geo_kind=args.geo,
                        dl_factor=60.0, sponge=60, ramp=200)
    rep = agent.run(intent)
    wall = time.time() - t0

    # 落盘
    dump_json(rep.to_dict(), args.out)

    # 可读摘要
    is_wg = (args.geo == "waveguide_2d")
    print("=" * 64)
    print("LDA · agent-native 设计闭环 · 演示报告")
    print("=" * 64)
    if is_wg:
        print(f"目标        : 真2D 波导 λ0={intent['target_wavelength_um']}µm, "
              f"Si/SiO2, 芯宽 {intent['extra'].get('width_um', 0.5)}µm")
        print(f"后端        : {args.backend}（时域 2D-TE FDTD，对 slab 闭式 ORACLE）")
        geo_label = "真2D 波导(waveguide_2d)"
        m_label, o_label = "neff(FDTD)", "neff(slab ORACLE)"
        err_label = "|Δneff|/neff 验收"
    else:
        print(f"目标        : 布拉格镜 λ0={intent['target_wavelength_um']}µm, "
              f"Si/SiO2, 目标 R≥{intent['threshold']}")
        print(f"后端        : {args.backend}（已验证主权核，对 TMM 物理定律锚）")
        geo_label = ("机器优先版图→体素(voxel_field)" if args.geo == "voxel_field"
                     else "层状 stack")
        m_label, o_label = "R(FDTD)", "R(TMM)"
        err_label = "|ΔR| 验收(中心波长)"
    print(f"几何原语    : {geo_label}")
    print(f"迭代次数    : {rep.iterations}")
    print(f"是否达标    : {'是 ✅' if rep.accepted else '否 ❌'}")
    print(f"最终 {m_label}: {rep.final_metric:.4f}   {o_label}={rep.final_oracle_metric:.4f}")
    if is_wg:
        rel = (rep.final_metric_err / rep.final_oracle_metric
               if rep.final_oracle_metric else 0.0)
        print(f"{err_label} : {rel:.2%}  (公差 {intent['tolerance_rel']:.0%} 相对误差)")
    else:
        print(f"{err_label} : {rep.final_metric_err:.2e}  (公差 {intent['tolerance_rel']} 绝对误差)")
    print(f"全谱最大误差(诊断) : {rep.final_max_metric_err:.2e}")
    print(f"闭环墙钟    : {wall:.1f}s")
    print("-" * 64)
    print("迭代轨迹 (periods → metric_fdtd / metric_oracle / err / passed):")
    for row in rep.loop_trace:
        print(f"  it{row['iteration']:>2}  N={row['periods']:>2}  "
              f"M={row['R_fdtd']:.4f}/{row['R_tmm']:.4f}  "
              f"err={row['metric_err']}  {'PASS' if row['passed'] else '...'}")
    print("-" * 64)
    print(f"结论        : {rep.verdict}")
    print(f"报告已落盘  : {args.out}")
    print("=" * 64)


if __name__ == "__main__":
    main()
