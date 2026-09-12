"""B31 Si 载流子色散相移锚 · CI 门禁 smoke（T1-C W3 · v0.9.69）。

守护六件事（评审 §1 终审裁决的物理约束）：
  ① 方法学独立交叉验证：Soref-Bennett 电子项 vs Drude 电子项 同号同量级
     （ratio 0.2-3.0；故意非恒等 → 判据 D 不撞，捕捉同一等离子体色散物理）
  ② 反向：V_R 升高 -> ΔN_eff 增大 -> |Δn| 增大 -> |Δφ| 单调增大（判别力）
  ③ 红线守卫：ΔN_eff 超 10^18 cm^-3 耗尽近似失效区必 raise（不越界宣称）
  ④ honest_tier = depletion-approx（耗尽近似闭式，零漂移-扩散）
  ⑤ 适用域：Soref-Bennett 10^17-10^20 cm^-3 + 耗尽失效阈内
  ⑥ golden(SB) vs candidate(Drude) 在 default_params 偏差 < tol(1.5，量级一致容差)

运行：python run_b31_soref_bennett_smoke.py（~1s）
"""
from __future__ import annotations

import sys
from pathlib import Path

# 强制 stdout/stderr 为 UTF-8，避免 Windows GBK 控制台编码含非 ASCII 字符时报错
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

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
    print(f"  [{tag}] {name}" + (f" -- {detail}" if detail else ""))


def main() -> int:
    print("=" * 72)
    print("B31 Si carrier-dispersion phase-shift (Soref-Bennett / Drude)")
    print("=" * 72)

    from lda_harness.b31_soref_bennett_anchor import (
        b31_soref_bennett_dn,
        b31_drude_dn,
        b31_depletion_dN_eff,
        b31_soref_bennett_phase_shift,
        b31_drude_phase_shift,
        b31_phase_shift_report,
    )

    V_bi, N0, lam, L, n_eff = 0.85, 2e17, 1.55, 1000.0, 2.4

    # --------------------------------- ① 方法学独立交叉验证（同号同量级）
    dN = 2e17  # SB 适用域内
    dn_sb = b31_soref_bennett_dn(dN, 0.0)       # 纯电子 SB 项
    dn_dr = b31_drude_dn(dN, n_eff)             # Drude 纯电子项
    ratio = abs(dn_dr) / abs(dn_sb)
    check("① SB-electron vs Drude-electron same-sign same-magnitude (crit-D no-collision)",
          0.2 <= ratio <= 3.0 and dn_sb * dn_dr > 0,
          f"ratio={ratio:.3f} (0.2-3.0, same sign; Drude lacks many-body correction)")

    # --------------------------------- ② 反向 V_R up -> |dphi| 单调增大
    Vs = [0.0, 1.0, 3.0, 5.0]
    phis = [b31_soref_bennett_phase_shift(V, V_bi, N0, 0.0, lam, L, n_eff)
            for V in Vs]
    mono = all(phis[i] < phis[i + 1] for i in range(len(phis) - 1))
    check("② Reverse: V_R up -> |dphi| up (discrimination monotone)", mono,
          " ".join("%.4f" % p for p in phis))

    # --------------------------------- ③ 红线：耗尽近似失效阈值必 raise
    guard_ok = False
    try:
        b31_soref_bennett_phase_shift(50.0, V_bi, N0, 0.0, lam, L, n_eff)
    except ValueError:
        guard_ok = True
    check("③ Red-line: dN_eff>1e18 cm^-3 depletion-fail raise", guard_ok,
          "" if guard_ok else "V_R=50 did not raise (should)")

    # --------------------------------- ④ honest_tier = depletion-approx
    rep = b31_phase_shift_report(V_R=3.0)
    check("④ honest_tier = depletion-approx", rep["honest_tier"] == "depletion-approx",
          rep["honest_tier"])

    # --------------------------------- ⑤ 适用域 + 耗尽失效阈
    check("⑤ Domain 1e17-1e20 & depletion-fail threshold", rep["domain_ok"] and rep["depletion_ok"],
          f"domain_ok={rep['domain_ok']} depletion_ok={rep['depletion_ok']} "
          f"dN_max={rep['dN_eff_max_cm3']:.3e}")

    # --------------------------------- ⑥ golden vs candidate 偏差 < tol(1.5)
    g = b31_soref_bennett_phase_shift(3.0, V_bi, N0, 0.0, lam, L, n_eff)
    c = b31_drude_phase_shift(3.0, V_bi, N0, lam, L, n_eff)
    dev = abs(c - g) / abs(g) if g != 0 else float("inf")
    check("⑥ golden(SB) vs candidate(Drude) dev<tol(1.5)", dev < 1.5,
          f"dev={dev:.3f} (magnitude-consistency tol, not exact identity)")

    print("=" * 72)
    if FAIL:
        print(f"B31 smoke: {PASS} PASS / {FAIL} FAIL -- PROBLEM")
        return 1
    print(f"B31 smoke: {PASS} PASS / 0 FAIL -- all green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
