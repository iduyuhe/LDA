"""B28 数值零点拟合候选护栏 smoke（v0.9.28 · T-2）。

守护五件事：
  ① 求解器自校：T(V) 谱的物理形状 —— T(0)=1、T 在 Vπ 处为 0（cos² 链自洽）
  ② harness 正向：B28 候选必须 PASS（残差 ≪ tol）
  ③ candidate 登记必须是 mzm_vpi_nullfit（防回退自证桩/回退沿程积分）
  ④ 🔴 判据 D 双对照（本锚最有价值的一组断言）：
       · nullfit 候选残差随 n_voltage 真实收敛（真数值离散化）
       · 沿程积分候选残差恒 ~4.4e-16（代数恒等 = 判据 D 反例，
         只许作报告侧交叉验证，不得作 harness 独立候选）
  ⑤ 反向：r_eff +10% ⇒ Vπ 变 ~9% ⇒ |cand−golden| ≫ tol 必 FAIL

运行：python run_b28_nullfit_smoke.py（~2s）
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


def main() -> int:
    print("=" * 72)
    print("B28 数值零点拟合候选护栏（mzm_vpi_nullfit）")
    print("=" * 72)

    from lda_solver.mzm_vpi_nullfit import (
        _transmission, mzm_vpi_nullfit, nullfit_convergence,
    )
    from lda_harness.b28_modulator_vpi_anchor import (
        mzm_vpi_analytic, mzm_vpi_integral,
    )
    from lda_harness.harness import candidate_discretization_responds
    from lda_harness.benchmarks import BENCHMARK_DEFS

    lam, n_eff, r_eff, gamma, L, d = 1.55, 2.2, 30.8e-12, 0.5, 10000.0, 8.0
    lm, Lm, dm = lam * 1e-6, L * 1e-6, d * 1e-6

    # ------------------------------------------------ ① 谱形状自校
    t0 = _transmission(0.0, lm, n_eff, r_eff, gamma, Lm, dm)
    vpi = mzm_vpi_analytic()
    tv = _transmission(vpi, lm, n_eff, r_eff, gamma, Lm, dm)
    check("T(0)=1（满传输起点）", abs(t0 - 1.0) < 1e-12, "T(0)=%.12f" % t0)
    check("T(Vπ)=0（闭式零点处传输归零，物理链自洽）", tv < 1e-12,
          "T(Vπ)=%.2e" % tv)

    # ------------------------------------------------ ② harness 正向
    from lda_harness.verification_adapters import build_harness_specs
    from lda_harness.verification_spec import run_verification
    specs, cand = build_harness_specs()
    sp = [s for s in specs if s.spec_id == "B28"][0]
    fn = cand["B28"]
    ov = sp.oracle_fn(sp.params)
    cv = fn(sp, ov)
    res = run_verification(sp, fn, oracle_value=ov)
    check("B28 正向 PASS", bool(res.passed),
          "cand=%.12f gold=%.12f 残差=%.2e tol=%s" % (cv, ov, abs(cv - ov), sp.tol))

    # ------------------------------------------------ ③ 登记防回退
    b28 = BENCHMARK_DEFS["B28"]
    check("candidate 登记 = mzm_vpi_nullfit",
          b28.get("candidate") == "mzm_vpi_nullfit",
          "实际=%s（防回退自证桩或沿程积分）" % b28.get("candidate"))

    # ------------------------------------------------ ④ 判据 D 双对照
    def nullfit_pair(n):
        return mzm_vpi_nullfit(n_voltage=n), mzm_vpi_analytic()

    ok_fit, ev_fit = candidate_discretization_responds(nullfit_pair, min_ratio=1.0)
    r_fit = ev_fit.get("residual", [])
    check("判据D：nullfit 残差随 n_voltage 收敛（真独立）", ok_fit,
          " ".join("%.1e" % r for r in r_fit))

    def integral_pair(n):
        return mzm_vpi_integral(n_segments=n), mzm_vpi_analytic()

    ok_int, ev_int = candidate_discretization_responds(integral_pair, min_ratio=1.0)
    check("判据D：沿程积分残差恒 ~4e-16（代数恒等，反例钉死）", not ok_int,
          " ".join("%.1e" % r for r in ev_int.get("residual", [])))

    conv = nullfit_convergence()
    errs = [row["abs_err"] for row in conv["rows"]]
    check("nullfit 收敛单调（充分加密后）",
          errs[-1] < errs[len(errs) // 2] < errs[0],
          "N=25→400 残差 %.1e → %.1e" % (errs[0], errs[-1]))

    # ------------------------------------------------ ⑤ 反向必被抓
    p2 = dict(sp.params)
    p2["r_eff"] = sp.params["r_eff"] * 1.1

    class _S:  # 最小 spec shim
        spec_id = "B28"
        params = p2

    cv2 = fn(_S(), ov)
    d2 = abs(cv2 - ov)
    check("反向 r_eff+10% 必 FAIL", d2 > float(sp.tol),
          "越界 %.4f ≫ tol %s" % (d2, sp.tol))

    print("=" * 72)
    if FAIL:
        print(f"B28 nullfit 冒烟：{PASS} PASS / {FAIL} FAIL —— 🔴 存在问题")
        return 1
    print(f"B28 nullfit 冒烟：{PASS} PASS / 0 FAIL —— 全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
