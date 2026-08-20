"""LDA · D-24 通用谱形逆设计框架 smoke。

验证统一 SpectrumInverseDesignAgent：
  1. ring 实例（match 模式 + 黄金分割）：R=9.9498µm（与 D-11 一致）
  2. 新实例即插即用（同一 ring 引擎、不同工艺 n_g → 不同收敛落点）：
     证明「提供 engine/metric/oracle 三函数即插即用」
  3. bragg 实例（threshold 模式 + 离散扫描）：N=6，R_min≥阈值且
     逐点 max|ΔR|≤tol（与 D-03 一致，FDTD 引擎）
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_agent.spectrum_loop import (  # noqa: E402
    SpectrumTarget, SpectrumInverseDesignAgent, metric_error,
    run_ring_spectrum, run_bragg_spectrum,
    ring_engine, ring_metric, ring_oracle,
)


def check(cond: bool, msg: str, report: dict, key: str) -> bool:
    status = "OK  " if cond else "FAIL"
    print(f"[{status}] {msg}")
    report["checks"].append({"key": key, "ok": bool(cond), "msg": msg})
    return bool(cond)


def main() -> int:
    report: dict = {"d24": "spectrum inverse-design framework", "checks": []}
    ok = True

    # 1) ring 实例（match 模式 + 黄金分割）：与 D-11 一致
    r = run_ring_spectrum({})
    ok &= check(r["accepted"], f"ring 实例 PASS：{r['verdict'][:80]}", report, "ring")
    ok &= check(abs(r["final_R_um"] - 9.9498) < 0.001,
                f"R={r['final_R_um']:.4f}µm（理论 9.9498，误差 {abs(r['final_R_um']-9.9498):.4f}µm）",
                report, "ring_R")
    ok &= check(r["final_spectrum_err"] <= 0.03 and r["final_fsr_method_err"] <= 0.02,
                f"谱形误差 {r['final_spectrum_err']:.2e} ≤ 0.03，方法一致性 "
                f"{r['final_fsr_method_err']:.2e} ≤ 0.02", report, "ring_dual")

    # 2) 新实例即插即用：同一 ring 引擎、不同工艺窗口（n_g=4.18，CUMEC）
    #    → 无需改框架，只换 engine_kw，收敛落点不同（跨工艺差异）
    r2 = run_ring_spectrum({"extra": {"n_g": 4.18}})
    ok &= check(r2["accepted"],
                f"即插即用实例（n_g=4.18）PASS：R={r2['final_R_um']:.4f}µm"
                f"（vs n_g=4.2 的 {r['final_R_um']:.4f}µm，工艺窗口驱动落点差异）",
                report, "plug_and_play")
    ok &= check(abs(r2["final_R_um"] - r["final_R_um"]) > 0.001,
                "不同工艺窗口收敛到不同 R（非走过场）", report, "ppl_diff")

    # 3) bragg 实例（threshold 模式 + 离散扫描）：D-03 一致
    rb = run_bragg_spectrum({})
    ok &= check(rb["accepted"],
                f"bragg 实例 PASS：{rb['verdict'][:80]}", report, "bragg")
    ok &= check(rb["final_periods"] >= 6 and rb["final_band_min_R_fdtd"] >= 0.99,
                f"N={rb['final_periods']}，R_min={rb['final_band_min_R_fdtd']:.5f}"
                f" ≥ 0.99", report, "bragg_R")
    ok &= check(rb["final_max_abs_err"] is not None
                and rb["final_max_abs_err"] <= 0.02,
                f"逐点 max|ΔR|={rb['final_max_abs_err']} ≤ 0.02（与 D-03 verify_band 同式）",
                report, "bragg_tol")

    # 4) 框架目标语义自检：match / threshold 的 metric_error 定义
    t_match = SpectrumTarget(name="t", param_name="x", bounds=(0, 1),
                             target_metric=1.0, mode="match")
    t_thr = SpectrumTarget(name="t", param_name="x", bounds=(0, 1),
                           target_metric=0.9, mode="threshold")
    ok &= check(abs(metric_error(0.5, t_match) - 0.5) < 1e-9,
                "match 模式：|m−t|/t", report, "mode_match")
    ok &= check(abs(metric_error(0.95, t_thr) - 0.0) < 1e-9
                and abs(metric_error(0.8, t_thr) - (0.9-0.8)/0.9) < 1e-9,
                "threshold 模式：达标 0 / 未达 (t−m)/t", report, "mode_threshold")

    out_path = os.path.join(_HERE, "reports", "spectrum_loop_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告：{out_path}")
    print("D-24 通用谱形逆设计框架 smoke:", "ALL GREEN" if ok else "HAS FAILURE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
