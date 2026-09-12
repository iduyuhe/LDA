# -*- coding: utf-8 -*-
"""
B32 EAM-QCSE 吸收边位移锚 CI 门禁 (T1-C W4, v0.9.69, A 档有源扩展 #3)

6 判据：
  ① golden(无穷深方势阱二阶微扰闭式) vs candidate(1D 薛定谔有限差分数值对角化)
     同号 + 同量级 (ratio 0.2-3.0) -- 方法学不同源, 判据 D 不撞。
  ② 反向: V_mod 增 -> |ΔE| 增 (monotone, 鉴别力)。
  ③ 红线: 高场 (扰动失效 / 电离上限) 必 raise。
  ④ honest_tier = "qcse-closed-form" (MQW 外延属 foundry T2, 文献消费非求解)。
  ⑤ 适用域 + 扰动失效检查 (L 1-50nm, |ΔE|<=0.3 E_conf, F<=1e6 V/cm)。
  ⑥ golden vs candidate dev<tol(0.3 相对) -- 方法一致性 (非精确恒等)。

红线守住: 纯能带/电磁闭式 + 数值带结构, 无载流子动力学/增益/TCAD/A 级。
"""
import sys
import math
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lda_harness.b32_qcse_anchor import (  # noqa: E402
    b32_qcse_report, b32_qcse_edge_shift_meV, B32_DOMAIN_LO, B32_DOMAIN_HI, B32_L_DEFAULT,
)


def _check(name, ok, detail=""):
    mark = "[PASS]" if ok else "[FAIL]"
    print(f"  {mark} {name} -- {detail}")
    return ok


def main():
    print("=" * 72)
    print("B32 EAM-QCSE absorption-edge shift (QCSE closed-form / numerical diagonalization)")
    print("=" * 72)
    all_ok = True

    V_test = 3.0  # reverse bias, V
    r = b32_qcse_report(V_test)

    # ① 同号 + 同量级 (判据 D 不撞)
    ratio = r["ratio_gold_over_num"]
    ok1 = r["same_sign"] and (0.2 <= ratio <= 3.0)
    all_ok &= _check("1 SB-closed-form vs numerical-diag same-sign same-magnitude (crit-D no-collision)",
                     ok1, f"ratio={ratio:.3f} (0.2-3.0, same sign; numeric is exact, closed-form is 2nd-order)")
    # ② 反向 monotone
    ok2 = r["monotone_F_up"]
    all_ok &= _check("2 Reverse: V up -> |dE| up (discrimination monotone)",
                     ok2, "monotone confirmed")

    # ③ 红线: 高场必 raise
    red_ok = False
    try:
        b32_qcse_edge_shift_meV(50.0)  # F = 1e8 V/m -> perturbation break
        red_ok = False
    except ValueError:
        red_ok = True
    ok3 = red_ok
    all_ok &= _check("3 Red-line: high-field (perturbation break / ionization) raise",
                     ok3, "ValueError raised")

    # ④ honest_tier
    ok4 = (r["honest_tier"] == "qcse-closed-form")
    all_ok &= _check("4 honest_tier = qcse-closed-form", ok4, r["honest_tier"])

    # ⑤ 适用域 + 扰动失效
    ok5 = r["perturbation_ok"] and (B32_DOMAIN_LO <= B32_L_DEFAULT <= B32_DOMAIN_HI)
    all_ok &= _check("5 Domain 1-50nm & perturbation-fail threshold",
                     ok5, f"pertOK={r['perturbation_ok']} Econf={r['E_conf_meV']:.2f} meV")

    # ⑥ golden vs candidate dev<tol (relative 0.3)
    dev = abs(r["dE_gold_meV"] - r["dE_num_meV"]) / abs(r["dE_num_meV"]) if r["dE_num_meV"] != 0 else float("inf")
    ok6 = dev < 0.3
    all_ok &= _check("6 golden(closed-form) vs candidate(numerical) dev<tol(0.3)",
                     ok6, f"dev={dev:.4f} (method-consistency tol, not exact identity)")

    print("-" * 72)
    print(f"B32 smoke: {'6 PASS / 0 FAIL' if all_ok else 'HAS FAIL'} -- "
          f"{'all green' if all_ok else 'review'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
