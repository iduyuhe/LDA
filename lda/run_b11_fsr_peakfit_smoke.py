"""B11 环形谐振器 drop 端口谱形匹配 · 独立候选（ring_fsr_peakfit_b11）护栏 smoke。

守护四件事（v0.9.68 · P1①）：
  ① harness 正向：B11 候选必须 PASS（残差 ≪ tol=0.03）
  ② candidate 登记必须是 ring_fsr_peakfit_b11（防回退自证桩）
  ③ 🔴 判据 D：数值峰周期拟合 FSR 残差对离散化参数有响应且恒 >> 1e-12
     （真数值法，非代数恒等假独立）；默认网格下残差 < tol
  ④ 反向：n_g +10% ⇒ FSR 变 ~9% ⇒ |cand−golden|≫tol 必 FAIL（候选真响应参数）

运行：python run_b11_fsr_peakfit_smoke.py（~3s）
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{tag}] {name}" + (f" —— {detail}" if detail else ""))


def _drop_response(lam, wl0, ng, R, kappa=0.3, a_rt=0.99):
    import numpy as np
    L = 2.0 * math.pi * R
    t_rt = math.sqrt(max(0.0, 1.0 - kappa ** 2))
    phi = 2.0 * math.pi * ng * L / lam
    return (kappa ** 4 * a_rt) / (1.0 + (a_rt * t_rt) ** 2
                                  - 2.0 * a_rt * t_rt * np.cos(phi))


def main() -> int:
    print("=" * 72)
    print("B11 环形谐振器谱形匹配 · 独立候选护栏（ring_fsr_peakfit_b11）")
    print("=" * 72)

    from lda_harness.benchmarks import BENCHMARK_DEFS
    from lda_harness.verification_adapters import (
        build_harness_specs, _fit_fsr_peak_periodicity,
    )
    from lda_harness.verification_spec import run_verification

    # ------------------------------------------------ ② 登记防回退
    b11 = BENCHMARK_DEFS["B11"]
    check("candidate 登记 = ring_fsr_peakfit_b11",
          b11.get("candidate") == "ring_fsr_peakfit_b11",
          "实际=%s（防回退自证桩）" % b11.get("candidate"))

    # ------------------------------------------------ ① harness 正向
    specs, cand = build_harness_specs()
    sp = [s for s in specs if s.spec_id == "B11"][0]
    fn = cand["B11"]
    ov = sp.oracle_fn(sp.params)
    cv = fn(sp, ov)
    res = run_verification(sp, fn, oracle_value=ov)
    check("B11 正向 PASS", bool(res.passed),
          "cand=%.6f gold=%.6f 残差=%.2e tol=%s" % (cv, ov, abs(cv - ov), sp.tol))

    # ------------------------------------------------ ③ 判据 D 数值独立性
    # 复算 drop 传递函数，扫不同网格密度看 FSR 数值估计是否「对离散化有响应」
    # 且恒 >> 1e-12（证明是 genuine 数值法，非 candidate≡golden 代数恒等假独立）。
    # ⚠️ 本候选误差由抛物线定峰 + 1/λ 等距 polyfit 主导，不随网格单调收敛
    #   （中网格有时比细网格更准），故判据 D 不要求单调，只要求：
    #     (a) 基线残差恒 >> 1e-12（非机器精度恒等）
    #     (b) 跨网格残差跨度 > 2×（证明答案真由数值离散化决定，非返回常量）
    #     (c) 默认网格下残差 < tol（数值法落在容差内）
    p = sp.params
    wl0 = float(p.get("wavelength", 1.55))
    ng = float(p["n_g"])
    R = float(p["R"])
    # 闭式 FSR（nm）= λ0²/(n_g·2πR)·1000
    fsr_closed = (wl0 ** 2) / (ng * 2.0 * math.pi * R) * 1000.0

    grids = [5001, 20001, 50001]
    errs = []
    for n_grid in grids:
        fsr_num = _fit_fsr_peak_periodicity(
            lambda lam: _drop_response(lam, wl0, ng, R), wl0, n_grid=n_grid)
        errs.append(abs(fsr_num - fsr_closed))
    check("判据D：各网格残差均 > 1e-12（非代数恒等假独立）",
          all(e > 1e-12 for e in errs), " ".join("%.2e" % e for e in errs))
    check("判据D：跨网格残差跨度 > 2×（真数值法对离散化有响应）",
          max(errs) / min(errs) > 2.0, "span=%.1f" % (max(errs) / min(errs)))
    check("判据D：基线残差 > 1e-12（非代数恒等假独立）",
          abs(cv - ov) > 1e-12, "res=%.2e" % abs(cv - ov))
    check("判据D：基线残差 < tol（数值法在容差内）",
          abs(cv - ov) < float(sp.tol), "res=%.2e tol=%s" % (abs(cv - ov), sp.tol))

    # ------------------------------------------------ ④ 反向必被抓
    p2 = dict(sp.params)
    p2["n_g"] = sp.params["n_g"] * 1.1

    class _S:  # 最小 spec shim
        spec_id = "B11"
        params = p2

    cv2 = fn(_S(), ov)            # 新候选 vs 旧 golden（ov 已定）
    d2 = abs(cv2 - ov)
    check("反向 n_g+10% 必 FAIL", d2 > float(sp.tol),
          "越界 %.4f ≫ tol %s" % (d2, sp.tol))

    print("=" * 72)
    if FAIL:
        print(f"B11 谱拟合冒烟：{PASS} PASS / {FAIL} FAIL —— 🔴 存在问题")
        return 1
    print(f"B11 谱拟合冒烟：{PASS} PASS / 0 FAIL —— 全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
