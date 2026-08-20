"""D-31 环形逆设计 FDTD 双验证 smoke。

结构自检（CI 无 GPU 可跑，快）+ live 双验证（GPU：解析收敛 R 后调 D-27
环形 FDTD 核做最终 drop 谱验证，FSR(FDTD) ↔ 解析 FSR 对拍）。
无 GPU 时 live 诚实 SKIP 不算失败（与 D-27 同纪律）。

判据（死代码判定，LLM 不进判决路径）：
  1. 解析层：谱形误差 |FSR_c(R,n_g)−target|/target ≤ target_tol（设计目标命中）
  2. FDTD 层（D-31 新）：drop 谱谐振峰 ≥3 且 FSR(FDTD) 与解析 FSR(n_g=n_core)
     相对偏差 ≤ tol_rel（真实 FDTD 物理行为自洽，方法一致性）
  accepted = 两层皆过
"""
import json
import os
import sys

import numpy as np  # noqa: F401  (find_resonances/fsr_from_resonances 依赖)

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def check(cond, msg, report, key):
    ok = bool(cond)
    report["checks"][key] = {"ok": ok, "msg": msg}
    print(("OK  " if ok else "FAIL") + " " + msg)
    return ok


def main() -> int:
    report = {"checks": {}, "live": None}
    ok = True

    # 1) 模块可导入 + FDTD 验证函数可调用
    from lda_agent.ring_loop import RingBandAgent, verify_ring_fdtd
    ok &= check(callable(verify_ring_fdtd),
                "verify_ring_fdtd 可导入（D-31 FDTD 最终验证层）", report, "import")

    # 2) 解析层零回归：不开 fdtd_verify 时行为不变
    r0 = RingBandAgent().run({
        "geometry_type": "ring", "target_wavelength_um": 1.55,
        "target_metric": "spectrum_match", "tolerance_rel": 0.02,
        "max_iterations": 40,
        "extra": {"R_um": 10.0, "R_bounds": [8.0, 12.0], "n_g": 4.2,
                  "Q": 1.0e4, "kappa": 0.05, "target_fsr_nm": 9.15,
                  "wl0_um": 1.55, "target_tol": 0.03}})
    ok &= check(r0["accepted"] and abs(r0["final_R_um"] - 9.9498) < 1e-3
                and r0["fdtd_verify"] is None,
                f"解析层零回归：R={r0['final_R_um']:.4f}µm（=D-11 9.9498），"
                f"fdtd_verify=None（未启用）", report, "zero_regression")

    # 3) FDTD 层判据字段齐备（不真跑，纯结构）
    import inspect
    sig = inspect.signature(verify_ring_fdtd)
    for p in ("R_um", "n_core", "n_clad", "n_points", "tol_rel", "backend"):
        ok &= check(p in sig.parameters,
                    f"verify_ring_fdtd 参数 {p} 齐备", report, "sig_" + p)

    # 4) live 双验证（GPU；无 GPU 诚实 SKIP）
    #    注：本机 CUDA_VISIBLE_DEVICES="" 对 torch 无效（is_available 仍 True），
    #    本地验证 CI 无 GPU 路径用 LDA_SKIP_LIVE=1 强制跳过。
    if os.environ.get("LDA_SKIP_LIVE") == "1":
        cuda = False
    else:
        try:
            import torch
            cuda = torch.cuda.is_available()
        except Exception:
            cuda = False
    if cuda:
        intent = {
            "geometry_type": "ring", "target_wavelength_um": 1.55,
            "target_metric": "spectrum_match", "tolerance_rel": 0.02,
            "max_iterations": 40,
            "extra": {"R_um": 10.0, "R_bounds": [8.0, 12.0], "n_g": 4.2,
                      "Q": 1.0e4, "kappa": 0.05, "target_fsr_nm": 9.15,
                      "wl0_um": 1.55, "target_tol": 0.03,
                      "fdtd_verify": True, "fdtd_n_points": 21,
                      "fdtd_tol_rel": 0.30, "fdtd_backend": "auto"}}
        r = RingBandAgent().run(intent)
        fd = r["fdtd_verify"]
        report["live"] = {
            "final_R_um": r["final_R_um"], "accepted": r["accepted"],
            "fdtd": fd,
        }
        ok &= check(r["accepted"],
                    f"环形双验证 PASS（解析收敛 + FDTD 最终验证）：{r['verdict'][:110]}",
                    report, "live_accepted")
        if fd is not None:
            ok &= check(fd["accepted"] and len(fd["peaks_um"]) >= 3,
                        f"FDTD 层 drop 谱 {len(fd['peaks_um'])} 个谐振峰 + "
                        f"FSR(FDTD)={fd['fsr_fdtd_nm']:.2f}nm vs 解析 "
                        f"{fd['fsr_analytic_nm']:.2f}nm（rel="
                        f"{fd['fsr_rel_dev']:.2%} ≤ {fd['tol_rel']:.0%}）",
                        report, "live_fdtd")
    else:
        print("SKIP live 双验证（无 GPU；环形 FDTD 需 CUDA，见 fdtd2d_ring）")
        report["live"] = {"skipped": True, "reason": "no cuda"}

    report["all_green"] = ok
    os.makedirs(os.path.join(_HERE, "reports"), exist_ok=True)
    with open(os.path.join(_HERE, "reports", "ring_double_verify_smoke.json"),
              "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("ALL GREEN" if ok else "HAS FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
