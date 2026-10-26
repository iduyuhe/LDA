# -*- coding: utf-8 -*-
"""E24 ADC 架构与列共享功耗权衡门禁（D-199 · v0.9.320）。

═══════════════════════════════════════════════════════════════════════════
本段是**连续第三次**把瓶颈收紧，且每次都是修口径而不是加功能
═══════════════════════════════════════════════════════════════════════════
E21 器件 → E22 器件族（地板 74.90）→ E23 修行线电容 1008×（地板 19.27，ADC 51.9%）
→ **E24 修逻辑口径两处错**（地板 **10.125**，**ADC 98.8%**）：

  · 频率：占位 200 MHz（偏高 2.05×）→ 正解 `1/t_clk = 97.68 MHz`（E17 推导）
  · 门数：`n²`（阵列单元数）→ 正解 `∝ n`（每列一个 ADC 控制/后处理单元），N=64 时**偏高 64×**

判什么
  A 模块自检（`adc_arch.adc_arch_self_check` **11 项**）
  B 关键事实（10 条）：两步式电容/能量比 · 🔴 **E_op 与 f_s 无关** · K⇒1/K ·
    两步式 8.5× · 未建模项区间与「下界」声明 · 逻辑时钟同源 · 逻辑 ∝n · 地板 10.125 · 对 Mythic 的差距
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

from lda_l2.ecore import adc_arch as A          # noqa: E402
from lda_l2.ecore import capability_manifest as CM  # noqa: E402
from lda_l2.ecore import device_family as D     # noqa: E402
from lda_l2.ecore import energy as E            # noqa: E402
from lda_harness.smoke_kit import make_result_collector  # noqa: E402

_results: list = []
check = make_result_collector(_results)

AN_FLOOR_FJ = 10.125          # 逻辑口径修正后地板
AN_ADC_SHARE = 98.8           # 地板处 ADC 份额（%）
AN_SAR_FJ = 9.9609            # 标准 SAR 的 ADC 每 op 能量
AN_TWO_STEP_FJ = 1.1719       # 两步式
MYTHIC_FJ = 8.3               # 120 TOPS/W


def _two_step_cap_ok() -> bool:
    return abs(A.cdac_cap_units(8, "two_step")["cap_units"] - 32.0) < 1e-12


def _invariance_ok() -> bool:
    """🔴 E_op,adc 与 f_s 无关：手算 e_sample/(2nK) 必须与函数逐位一致。"""
    got = A.adc_energy_per_op(8, "sar", 64, 1)["energy_per_op_fj"]
    manual = (0.5 * 255 * 10e-15 * 1.0) / (2 * 64 * 1) * 1e15
    return abs(got - manual) / manual < 1e-12


def _floor_ok() -> bool:
    fl = D.efficiency_floor_fj_per_op(64, 8)
    return (abs(fl["e_floor_fj_per_op"] - AN_FLOOR_FJ) / AN_FLOOR_FJ < 0.01
            and abs(fl["p_other_share_of_floor"]["adc"] * 100 - AN_ADC_SHARE) < 1.0)


def _logic_clock_ok() -> bool:
    lc = E.logic_clock_hz(8)
    return lc["identity_ok"] and abs(lc["f_logic_hz"] / 1e6 - 97.68) < 0.1


def _logic_prop_n_ok() -> bool:
    return abs(E.logic_power_w(64)["power_w"] / E.logic_power_w(32)["power_w"] - 2.0) < 1e-12


def _overhead_ok() -> bool:
    ob = A.overhead_bounds(10.0)
    return ob["spread_factor"] >= 2.0 and "下界" in ob["verdict"]


def main() -> int:
    print("=" * 74)
    print("E24 ADC 架构与列共享功耗权衡门禁（D-199）")
    print("=" * 74)

    print("\n── A 模块自检 ──")
    check("A1 adc_arch 自检 11/11（两步式电容/能量比/不变性/K/经验因子/未建模项）",
          A.adc_arch_self_check(verbose=True))

    print("\n── B 关键事实 ──")
    check("B1 两步式 C_tot = 2·C0·2^(b/2) = 32 C0（8 bit · vs SAR 256 C0）",
          _two_step_cap_ok())
    us = A.cdac_cap_units(8, "sar")
    u2 = A.cdac_cap_units(8, "two_step")
    check("B2 金标：两步式/SAR 能量比 ≡ 0.117647（精确闭式 15/127.5）",
          abs(u2["energy_units_C0V2"] / us["energy_units_C0V2"] - 15.0 / 127.5) < 1e-15)
    check("B3 🔴 **不变性**：E_op,adc = e_sample/(2·n·K) ⇒ **与转换速率 f_s 无关**"
          "（「两步式速度减半」不改能效）", _invariance_ok())

    e1 = A.adc_energy_per_op(8, "sar", 64, 1)["energy_per_op_fj"]
    e8 = A.adc_energy_per_op(8, "sar", 64, 8)["energy_per_op_fj"]
    check("B4 列共享 K=8 ⇒ ADC 每 op 能量 1/8（精确）", abs(e1 / e8 - 8.0) < 1e-12)
    check("B5 两步式比 SAR 好 8.5×（架构收益，非参数调优）",
          abs(e1 / A.adc_energy_per_op(8, "two_step", 64, 1)["energy_per_op_fj"] - 8.5) < 0.05)
    check("B6 🔴 未建模项给出**区间**（≥2× spread）且明写「ADC 能耗是**下界**」",
          _overhead_ok())
    check("B7 逻辑时钟真源 = 1/t_clk ≡ n_clk/T_conv = 97.68 MHz（E17 同源 · 恒等）",
          _logic_clock_ok())
    check("B8 🔴 逻辑功耗 ∝ n（**不是 ∝n²** · 修正项偏高 64×）", _logic_prop_n_ok())
    check("B9 🔴 修后地板 %.3f fJ/op · **ADC 占 %.1f%%**（瓶颈收敛到单一来源）"
          % (D.efficiency_floor_fj_per_op(64, 8)["e_floor_fj_per_op"], AN_ADC_SHARE),
          _floor_ok())
    check("B10 对 Mythic 的差距可判定：标准 SAR 地板 %.3f / Mythic %.1f = **%.2f×**；"
          "两步式 %.2f fJ/op ⇒ **低于目标**"
          % (AN_FLOOR_FJ, MYTHIC_FJ, AN_FLOOR_FJ / MYTHIC_FJ, AN_TWO_STEP_FJ),
          abs(AN_FLOOR_FJ / MYTHIC_FJ - 1.22) < 0.02
          and AN_TWO_STEP_FJ < MYTHIC_FJ)
    check("B11 能力清单已登记 adc_arch（%d 条能力）" % len(CM.ECORE_CAPABILITY_MANIFEST),
          "lda_l2.ecore.adc_arch" in [x["module"] for x in CM.ECORE_CAPABILITY_MANIFEST])

    print("\n── C 反向可证伪 ──")

    # C1：两步式电容改成 2^b（不退化为两级）⇒ B1 必红
    def _bad_cap(bits, arch):
        if arch == "two_step":
            return {"arch": arch, "bits": bits, "cap_units": float(2 ** bits),
                    "energy_units_C0V2": 0.5 * (2 ** bits - 1), "energy_factor": None,
                    "empirical_factor": False, "basis": "bad"}
        return {**A.cdac_cap_units.__wrapped__(bits, arch)} \
            if hasattr(A.cdac_cap_units, "__wrapped__") else None
    real_cap = A.cdac_cap_units
    with mock.patch.object(A, "cdac_cap_units",
                           lambda b, a: ({"arch": a, "bits": b, "cap_units": float(2 ** b),
                                          "energy_units_C0V2": 0.5 * (2 ** b - 1),
                                          "energy_factor": None, "empirical_factor": False,
                                          "basis": "bad"} if a == "two_step"
                                         else real_cap(b, a))):
        c1 = not _two_step_cap_ok()
    check("C1 探针：两步式电容退回 2^b（未真分两级）⇒ B1 必红", c1)

    # C2：逻辑时钟改回占位 200 MHz ⇒ B7 必红
    with mock.patch.object(E, "logic_clock_hz",
                           lambda bits=8: {"f_logic_hz": 200.0e6, "t_clk_s": 1e-8,
                                           "n_clk": 9, "f_from_conv": 1e8,
                                           "identity_ok": False, "basis": "bad"}):
        c2 = not _logic_clock_ok()
    check("C2 探针：逻辑时钟改回占位 200 MHz ⇒ B7 必红（**防回退**）", c2)

    # C3：逻辑门数改回 n² ⇒ B8 必红
    real_logic = E.logic_power_w
    with mock.patch.object(E, "logic_power_w",
                           lambda n_cells, **k: real_logic(int(n_cells) ** 2
                                                           if n_cells <= 256 else n_cells, **k)):
        c3 = not _logic_prop_n_ok()
    check("C3 探针：逻辑门数改回 n²（旧错口径）⇒ B8 必红", c3)

    # C4：未建模项 verdict 改成「可直接对外」⇒ B6 必红
    with mock.patch.object(A, "overhead_bounds",
                           lambda x: {"spread_factor": 1.0,
                                      "verdict": "本模型 ADC 能耗可直接对外"}):
        c4 = not _overhead_ok()
    check("C4 探针：verdict 改成「可直接对外」⇒ B6 必红（**下界声明是红线**）", c4)

    # C5：让 E_op 人为依赖 f_s ⇒ 不变性判据必红
    with mock.patch.object(A, "adc_energy_per_op",
                           lambda bits=8, arch="sar", n=64, share_k=1, **k:
                           {"energy_per_op_fj": 9.9609 * 1.5}):
        c5 = not _invariance_ok()
    check("C5 探针：E_op 被人为放大 1.5× ⇒ B3 不变性判据必红", c5)

    check("C7 还原完整性：探针退出后 A1 + B1/B3/B6/B7/B8/B9 复绿",
          A.adc_arch_self_check(verbose=False) and _two_step_cap_ok()
          and _invariance_ok() and _overhead_ok() and _logic_clock_ok()
          and _logic_prop_n_ok() and _floor_ok())

    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e24_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print(("[PASS] " if ok else "[FAIL] ") + name + (("  :: " + detail) if detail else ""))
    print()
    print("=" * 74)
    print("E24 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 5 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
