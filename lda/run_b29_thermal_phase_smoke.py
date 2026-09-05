"""B29 热光相移 FDM 候选护栏 smoke（v0.9.39 · T-9 接线 #1）。

守护四件事：
  ① harness 正向：B29 候选必须 PASS（残差 ≪ tol）
  ② candidate 登记必须是 thermal_phase_fdm（防回退自证桩）
  ③ 🔴 判据 D：FDM 残差随 N 单调收敛（真数值离散化，非代数恒等）
  ④ 反向：dn_dt +10% ⇒ 相移变 ~10% ⇒ |cand−golden|≫tol 必 FAIL

运行：python run_b29_thermal_phase_smoke.py（~2s）
"""
from __future__ import annotations

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
    print("B29 热光相移 FDM 候选护栏（thermal_phase_fdm）")
    print("=" * 72)

    from lda_solver.thermal_phase_efficiency import (
        thermal_phase_efficiency_fdm, fdm_convergence,
    )
    from lda_harness.b29_thermal_phase_anchor import b29_thermal_phase_efficiency
    from lda_harness.benchmarks import BENCHMARK_DEFS
    from lda_harness.verification_adapters import build_harness_specs
    from lda_harness.verification_spec import run_verification

    # ------------------------------------------------ ② 登记防回退
    b29 = BENCHMARK_DEFS["B29"]
    check("candidate 登记 = thermal_phase_fdm",
          b29.get("candidate") == "thermal_phase_fdm",
          "实际=%s（防回退自证桩）" % b29.get("candidate"))

    # ------------------------------------------------ ① harness 正向
    specs, cand = build_harness_specs()
    sp = [s for s in specs if s.spec_id == "B29"][0]
    fn = cand["B29"]
    ov = sp.oracle_fn(sp.params)
    cv = fn(sp, ov)
    res = run_verification(sp, fn, oracle_value=ov)
    check("B29 正向 PASS", bool(res.passed),
          "cand=%.6f gold=%.6f 残差=%.2e tol=%s" % (cv, ov, abs(cv - ov), sp.tol))

    # ------------------------------------------------ ③ 判据 D 单调收敛
    conv = fdm_convergence()
    errs = [r["abs_err"] for r in conv["rows"]]
    check("判据D：FDM 残差随 N 单调收敛（真独立）",
          errs[-1] < errs[len(errs) // 2] < errs[0] and errs[-1] < 1e-2,
          " ".join("%.1e" % e for e in errs))
    check("判据D：基线残差 > 1e-12（非代数恒等反例）",
          abs(cv - ov) > 1e-12, "res=%.2e" % abs(cv - ov))

    # ------------------------------------------------ ④ 反向必被抓
    p2 = dict(sp.params)
    p2["dn_dt"] = sp.params["dn_dt"] * 1.1

    class _S:  # 最小 spec shim
        spec_id = "B29"
        params = p2

    cv2 = fn(_S(), ov)
    d2 = abs(cv2 - ov)
    check("反向 dn_dt+10% 必 FAIL", d2 > float(sp.tol),
          "越界 %.4f ≫ tol %s" % (d2, sp.tol))

    print("=" * 72)
    if FAIL:
        print(f"B29 FDM 冒烟：{PASS} PASS / {FAIL} FAIL —— 🔴 存在问题")
        return 1
    print(f"B29 FDM 冒烟：{PASS} PASS / 0 FAIL —— 全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
