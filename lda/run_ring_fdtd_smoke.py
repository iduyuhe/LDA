"""LDA · D-27 环形 FDTD 仿真核 smoke。

验证 fdtd2d_ring（2D add-drop 环形，CW 稳态透射谱）：
  1. 结构自检（始终）：场构造（环形+双 bus 芯区几何正确）+ 解析 FSR 公式
  2. 谱形验收（需 torch CUDA，本地跑）：drop 谱 ≥3 谐振峰 + FSR(FDTD) 与
     解析偏差 ≤ 容差；无 GPU 诚实 SKIP（CW 稳态 numpy 逐波长太慢）
  3. 报告落盘 reports/ring_fdtd_report.json
"""
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "lda_solver"))

from lda_solver.fdtd2d_ring import (  # noqa: E402
    build_add_drop_ring_field, find_resonances, fsr_from_resonances,
    ring_fsr_analytic_nm, run_ring_fdtd,
)


def check(cond: bool, msg: str, report: dict, key: str) -> bool:
    status = "OK  " if cond else "FAIL"
    print(f"[{status}] {msg}")
    report["checks"].append({"key": key, "ok": bool(cond), "msg": msg})
    return bool(cond)


def main() -> int:
    report: dict = {"d27": "ring FDTD kernel", "checks": []}
    ok = True

    try:
        import torch
        cuda = torch.cuda.is_available()
    except Exception:
        cuda = False
    print(f"torch.cuda.is_available() = {cuda}")

    # 1) 结构自检（始终，无数值）
    R, w, gap, nc, ncl = 6.0, 0.5, 0.3, 3.48, 1.44
    dl = 1.55 / 20.0
    eps2, dl, N, ybus = build_add_drop_ring_field(R, w, gap, nc, ncl, dl)
    ring_cells = int(np.sum(eps2 > (ncl ** 2 + nc ** 2) / 2.0))
    ok &= check(ring_cells > 0 and N > 100,
                f"环形+双 bus 场构造：N={N}，芯区 {ring_cells} cells", report, "field")
    fsr_an = ring_fsr_analytic_nm(R, nc, 1.55)
    ok &= check(15.0 < fsr_an < 25.0,
                f"解析 FSR(R=6,n_core=3.48)={fsr_an:.2f}nm（物理量级）", report, "fsr_an")

    # 2) 谱形验收（GPU live）
    if not cuda:
        print("[SKIP] 环形 FDTD 谱形验收需 torch CUDA（CW 稳态逐波长 numpy 太慢）"
              "→ 诚实 SKIP；本地 GPU 机跑全谱形")
        report["live"] = {"skipped": True, "reason": "no CUDA"}
    else:
        rep = run_ring_fdtd(R_um=R, n_points=21, transient_cycles=2500,
                            M_cycles=80, tol_rel=0.30)
        report["live"] = {
            "peaks_um": rep["peaks_um"],
            "fsr_fdtd_nm": rep["fsr_fdtd_nm"],
            "fsr_analytic_nm": rep["fsr_analytic_nm"],
            "fsr_rel_dev": rep["fsr_rel_dev"],
        }
        ok &= check(rep["accepted"], f"环形 FDTD 谱形验收 PASS：{rep['verdict'][:90]}",
                    report, "live_spectrum")
        ok &= check(len(rep["peaks_um"]) >= 3,
                    f"drop 谱 {len(rep['peaks_um'])} 个谐振峰"
                    f"（{[round(p,4) for p in rep['peaks_um']]}）",
                    report, "peaks")
        ok &= check(rep["fsr_rel_dev"] <= 0.30,
                    f"FSR(FDTD)={rep['fsr_fdtd_nm']:.2f}nm vs 解析 "
                    f"{rep['fsr_analytic_nm']:.2f}nm（rel={rep['fsr_rel_dev']:.2%} ≤ 30%）",
                    report, "fsr")

    out_path = os.path.join(_HERE, "reports", "ring_fdtd_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告：{out_path}")
    print("D-27 环形 FDTD 仿真核 smoke:", "ALL GREEN" if ok else "HAS FAILURE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
