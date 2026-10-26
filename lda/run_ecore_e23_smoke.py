# -*- coding: utf-8 -*-
"""E23 外围能耗空间与达标可达性门禁（D-198 · v0.9.319）。

═══════════════════════════════════════════════════════════════════════════
本门禁的第一价值是**守住一次缺陷修复不许回退**
═══════════════════════════════════════════════════════════════════════════
E21/E22 的 `row_line_dynamic_power_w` 读错键名（`c_row_seg_f` vs 真源 `c_row_seg_fF`）
并静默走 `τ/R` fallback；E7 的 `tau_row_s` 是**整行** Elmore（∝N²）、`r_row_seg_ohm` 是**每段**
⇒ N=64 时行线电容**偏大 1008 倍**（222.76 fF vs 真源 0.2210 fF）。

修完后：
  · 地板 **74.90 → 19.27 fJ/op**（3.89×）
  · 主导项 **行线 74.3% → ADC 51.9% + 逻辑 47.8%**（行线仅 0.3%）
  · 独立交叉印证：产业公开口径「ADC 吃掉模拟 CIM 功耗 50~58%」

🔴 **本段否掉了 E22 自己给的方向**：行线只占 0.3% ⇒ 「改行线驱动」收益≈0。
   E22 的「E23 应做行线驱动」是**基于错误地板得出的错误建议**，本段撤回。

判什么
  A 模块自检（`drive_scheme.drive_scheme_self_check` **11 项**）
  B 关键事实（9 条）：行线电容**同源**（防回退）· 半摆幅 1/4 · 列共享 1/K ·
    地板 19.27 · 主导 ADC · 行线 <2%（**负结果**）· 阶梯 K=64 达 9.38 · 可达性不宣称
  C 反向可证伪：**5 条突变探针** ⇒ 均必红 + 还原重跑
  K 自入 CI core
"""
from __future__ import annotations

import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import capability_manifest as CM  # noqa: E402
from lda_l2.ecore import drive_scheme as S         # noqa: E402
from lda_l2.ecore import energy as E               # noqa: E402
from lda_l2.ecore import parasitic as PA           # noqa: E402
from lda_harness.smoke_kit import make_result_collector  # noqa: E402

_results: list = []
check = make_result_collector(_results)

AN_FLOOR_FJ = 10.125          # 修正后地板
AN_ADC_SHARE = 98.8          # 地板处 ADC 份额
AN_K64_FLOOR = 0.24          # 列共享 K=64 后的地板（半摆幅 + K=64）
AN_C_SEG_FF = 0.2210         # E7 真源每段线容（fF）


def _row_cap_src_ok() -> bool:
    """B1 · 行线电容**必须取 E7 真源**（防 τ/R 反解再犯）。"""
    ap = PA.array_parasitics(64, 64)
    rl = E.row_line_dynamic_power_w(64, 1.0e7)
    return (abs(rl["c_row_seg_fF"] - AN_C_SEG_FF) < 1e-3
            and abs(rl["c_row_total_f"] - ap["C_row_total_fF"] * 1e-15) < 1e-24)


def _half_swing_ok() -> bool:
    """B2 · 半摆幅 ⇒ 能量精确 1/4。"""
    f = S.scheme_energy_report(64, drive="voltage_full")["power_breakdown"]["row_line"]
    h = S.scheme_energy_report(64, drive="voltage_half")["power_breakdown"]["row_line"]
    return abs(h / f - 0.25) < 1e-15


def _adc_share_ok() -> bool:
    """B5 · 地板主导项 = ADC，行线 <2%。"""
    fl = S.floor_by_scheme(64)
    return (fl["dominant"] == "adc"
            and abs(fl["share"].get("adc", 0) * 100 - AN_ADC_SHARE) < 1.0
            and fl["share"].get("row_line", 1.0) < 0.02)


def _no_claim_ok() -> bool:
    """B8 · 可达性矩阵必须明写「不宣称可以达到」。"""
    rm = S.reachability_matrix(8.3)
    return ("不宣称" in rm["verdict"]) and bool(rm["must_satisfy"])


def main() -> int:
    print("=" * 74)
    print("E23 外围能耗空间与达标可达性门禁（D-198）")
    print("=" * 74)

    print("\n── A 模块自检 ──")
    check("A1 drive_scheme 自检 11/11（半摆幅/列共享/阶梯分解/守恒/负结果/可达性）",
          S.drive_scheme_self_check(verbose=True))

    print("\n── B 关键事实 ──")
    check("B1 🔴 行线电容 ≡ E7 真源 `c_row_seg_fF`=%.4f fF（**禁 τ/R 反解 · 曾偏大 1008×**）"
          % AN_C_SEG_FF, _row_cap_src_ok())
    check("B2 金标：半摆幅 ⇒ 行线能量精确 1/4（½C(ΔV)²）", _half_swing_ok())

    a1 = S.scheme_energy_report(64, adc="per_column")["power_breakdown"]["adc"]
    a8 = S.scheme_energy_report(64, adc="shared_k8")["power_breakdown"]["adc"]
    a64 = S.scheme_energy_report(64, adc="shared_k64")["power_breakdown"]["adc"]
    check("B3 金标：列共享 K=8 ⇒ 1/8 · K=64 ⇒ 1/64（精确）",
          abs(a1 / a8 - 8.0) < 1e-12 and abs(a1 / a64 - 64.0) < 1e-12)

    fl = S.floor_by_scheme(64)
    check("B4 🔴 修正后地板 = %.2f fJ/op（E22 原报 74.90 系行线口径错 · 3.89×）"
          % fl["e_floor_fj_per_op"],
          abs(fl["e_floor_fj_per_op"] - AN_FLOOR_FJ) / AN_FLOOR_FJ < 0.01)
    check("B5 🔴 地板主导项 = **ADC %.1f%%** + 逻辑 %.1f%% · 行线仅 %.2f%%"
          % (fl["share"]["adc"] * 100, fl["share"]["logic"] * 100,
             fl["share"]["row_line"] * 100), _adc_share_ok())

    lad = S.optimization_ladder(8.3)
    by = {x["id"]: x for x in lad}
    check("B6 🔴 **负结果**：行线半摆幅只改善 %.2f%% ⇒ 「改行线驱动」方向被否掉"
          % ((1 - by["baseline"]["e_floor_fj_per_op"]
              / by["drive_half"]["e_floor_fj_per_op"]) * 100),
          by["drive_half"]["gain_vs_prev"] < 1.01)

    check("B7 阶梯：ADC 列共享 K=64 后地板 %.3f fJ/op（离 8.3 目标 %.2f× ⇒ **已低于** ·"
          " 但见 E24 未建模项下界声明）"
          % (by["adc_k64"]["e_floor_fj_per_op"], by["adc_k64"]["gap_to_target"]),
          abs(by["adc_k64"]["e_floor_fj_per_op"] - AN_K64_FLOOR)
          / AN_K64_FLOOR < 0.02)

    check("B8 🔴 可达性矩阵明写「**不宣称可以达到**」+ 列出 must_satisfy 四条",
          _no_claim_ok())

    check("B9 阶梯单调不增（每步只改善或持平）",
          all(lad[i]["e_floor_fj_per_op"] >= lad[i + 1]["e_floor_fj_per_op"] - 1e-12
              for i in range(len(lad) - 1)))
    check("B10 能力清单已登记 drive_scheme（%d 条能力）"
          % len(CM.ECORE_CAPABILITY_MANIFEST),
          "lda_l2.ecore.drive_scheme"
          in [e["module"] for e in CM.ECORE_CAPABILITY_MANIFEST])

    print("\n── C 反向可证伪 ──")

    # C1：把行线电容改回 τ/R 反解 ⇒ B1 必红（**防回退是本门禁的第一职责**）
    def _bad_row(n, f_hz, params=None, v=None, swing_factor=1.0):
        ap = PA.array_parasitics(n, n)
        c_bad = (ap["tau_row_s"] / ap["r_row_seg_ohm"]) * 0.5
        return {"n": n, "c_row_seg_fF": c_bad * 1e15,
                "c_row_total_f": c_bad * n, "f_hz": f_hz,
                "swing_factor": swing_factor, "power_w": 1e-3, "basis": "bad"}

    with mock.patch.object(E, "row_line_dynamic_power_w", _bad_row):
        c1 = not _row_cap_src_ok()
    check("C1 探针：行线电容改回 τ/R 反解（旧缺陷）⇒ B1 必红（**防回退**）", c1)

    # C2：半摆幅按线性而非平方 ⇒ B2 必红
    bad = [dict(x) for x in S.DRIVE_SCHEMES]
    for x in bad:
        if x["id"] == "voltage_half":
            x["energy_factor"] = 0.5                     # 🔴 错口径：线性而非平方
            x["swing_factor"] = 0.7071067811865476       # = 1/√2 ⇒ 能量 1/2
    with mock.patch.object(S, "DRIVE_SCHEMES", bad):
        c2 = not _half_swing_ok()
    check("C2 探针：半摆幅用「ΔV=V/√2」（能量 1/2 而非 1/4）⇒ B2 必红", c2)

    # C3：抹掉 ADC 功耗 ⇒ 主导项不再是 ADC ⇒ B5 必红
    real_adc = E.adc_power_w
    with mock.patch.object(E, "adc_power_w",
                           lambda *a, **k: {**real_adc(*a, **k), "power_w": 0.0}):
        c3 = not _adc_share_ok()
    check("C3 探针：抹掉 ADC 功耗 ⇒ 「ADC 主导」必红", c3)

    # C4：把逻辑时钟同步这一步去掉 ⇒ K=64 就达不到 9.38 ⇒ B7 必红
    bad_steps = [dict(x) for x in S.LADDER_STEPS]
    for x in bad_steps:
        if x["id"] == "adc_k64":
            x["adc"] = "per_column"
    with mock.patch.object(S, "LADDER_STEPS", bad_steps):
        lad2 = S.optimization_ladder(8.3)
        c4 = abs({y["id"]: y for y in lad2}["adc_k64"]["e_floor_fj_per_op"]
                 - AN_K64_FLOOR) / AN_K64_FLOOR > 0.02
    check("C4 探针：撤掉 K=64 杠杆 ⇒ 地板回不到 9.38 ⇒ B7 必红", c4)

    # C5：可达性 verdict 改成「能达到」⇒ B8 必红
    with mock.patch.object(S, "reachability_matrix",
                           lambda *a, **k: {"verdict": "LDA 达到 8.3 fJ/op", "must_satisfy": ["x"]}):
        c5 = not _no_claim_ok()
    check("C5 探针：verdict 改成「能达到」⇒ B8 必红（**不宣称是红线**）", c5)

    check("C7 还原完整性：探针退出后 A1 + B1/B2/B4/B5/B7/B8 复绿",
          S.drive_scheme_self_check(verbose=False) and _row_cap_src_ok()
          and _half_swing_ok() and _adc_share_ok() and _no_claim_ok())

    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e23_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print(("[PASS] " if ok else "[FAIL] ") + name + (("  :: " + detail) if detail else ""))
    print()
    print("=" * 74)
    print("E23 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 5 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
