#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QS-M5（G7 标定/读出闭环）· 量子传感器 **闭环标定 + 动态范围** 门禁（v0.9.222）。

═══ 判什么（分节）═══
A 微波频率锁定（ODMR 线型**闭式 ⇄ 时域 FID 数值变换**一致 · 鉴别器在 f₀ 处 S=0 ·
  反号对称 · 闭环 gain=1 **一步**收敛 / gain=0.9 **几何**收敛更慢 · 收敛判据用
  **相对线宽**（非绝对 Hz，防误判） · 数值链**二分求根**锁定点 ↔ 反馈律不动点一致）·
B 磁场闭环（两点法 k̂=V_ref/B_ref **无噪声代数精确** · 全跨多点 LSQ 数值链一致 ·
  ε_k 定义自洽 · 读数相对误差 = ε_k · 有噪声 ⇒ 残差 > 0 **非代数恒等**）·
C 动态范围（噪声底 ∝ √(1/τ) · 线性段耗尽场 ∝ 线宽 · DR 定义 20log₁₀ 比值 100 ⇒ 40 dB ·
  DR 随线宽/积分时间**单调** · AC 灵敏度 ∝ √Δf · **闭式 ⇄ MC 带限噪声 rms** 一致）·
D 签核（三合一 ACCEPT）·
E 反向探针（探测偏置超 w/2 / 零参考场 / η≤0 / 零线宽 / 零带宽 / 错口径 / 非对称区间
  ⇒ 各自**必红**）·
F 自入 CI core（防静默漏接 · **G2 golden 分派必含三锚**（防漏登⇒假自证桩））·
G 模块自检直连（qs_m5.selfcheck_qs_m5 全项 PASS）。

═══ 🔴 锚账本口径（本档**净增 3 道锚** B482–B484）═══
QS-M5 交付**新物理量**（非既有锚的重复）：
  · **B482** 微波频锁鉴别器中心斜率（闭环标定专属：锁定回路增益，Hz⁻¹）；
  · **B483** 磁场标度因子自标定 k̂=V_ref/B_ref（闭环标定专属：V/T）；
  · **B484** AC 灵敏度带宽折算 η_AC=η√(2Δf)（动态范围/读出专属：T）。
🔴 **如实不登记**：动态范围 DR=20log₁₀(B_max/B_min)（**纯定义式** ⇒ 登记会构成
「定义充数」）· 频锁几何收敛（**控制律收敛性**）· 鉴别器对称性/DR 单调性/
读数误差=ε_k（**对称性/单调性/恒等**）· 线性段耗尽场（**定义标度**）——以上归本
smoke 覆盖，**不登记为 B 锚**（宁可少，不越级谎报）。
QS-M0/M1 的 η / QS-M4 的阵列物理均**不重复登记**。

═══ 诚实边界 ═══
· ODMR 线宽 w / 探测偏置 δ / 漂移量 / 读数噪声 / 参考场 B_ref / 积分时间 τ 均为
  **设计示例**，**非实测 PDK**。
· 🔴 本档**不做**器件级/系统级性能宣称；报告为**建模值**。
· 🔴 「NV 动态范围 ~54 dB」「芯片级 26 nT/√Hz」为**蓝图层引用的公开文献值**
  （Chinese Phys. B 2025 / MDPI Micromachines 2025），作**对标准星**；本档建模值
  与之**独立**，**不得**声称「实测达到 54 dB / 26 nT/√Hz」。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")


def main() -> int:
    from lda_l2 import qs_m5 as M

    f0 = M.zero_field_splitting_hz()
    w0 = 1.0e7
    d0 = w0 / 4.0

    # ══ A 微波频率锁定 ══════════════════════════════════════════════════
    check("A1 ODMR 线型在共振处凹陷最深（L(f₀)=1−C；C=1 ⇒ 0）",
          abs(M.odmr_lorentzian(f0, f0, w0, 1.0)) < 1e-12)

    check("A2 ODMR 半高：L(f₀±w/2)=1−C/2（半高宽 = w 定义自洽）",
          abs(M.odmr_lorentzian(f0 + w0 / 2.0, f0, w0, 1.0) - 0.5) < 1e-12)

    check("A3 🔴 ODMR 闭式线型 ↔ **时域 FID 数值变换**一致（绝对差 < 1e-6）",
          all(abs(M.odmr_lorentzian(f0 + dd, f0, w0, 1.0)
                  - M.odmr_lorentzian_numeric(f0 + dd, f0, w0, 1.0)) < 1e-6
              for dd in (0.0, 1e5, 1e6, 5e6, 1e7)),
          "失谐点 = (0, 0.1, 1, 5, 10) MHz")

    check("A4 鉴别器在共振处 S(f₀)=0（洛伦兹对称 ⇒ 零点 = f₀）",
          abs(M.lock_error_signal(f0, f0, w0, d0)) < 1e-12)

    _s_lo = M.lock_error_signal(f0 - 1.0e6, f0, w0, d0)
    _s_hi = M.lock_error_signal(f0 + 1.0e6, f0, w0, d0)
    check("A5 鉴别器**反号对称**（f₀ 两侧符号相反 ⇒ 可判方向）",
          _s_lo * _s_hi < 0.0,
          "S(−)=%.3e · S(+)=%.3e" % (_s_lo, _s_hi))

    _lk = M.frequency_lock(f0 + 2.0e5, f0, linewidth_hz=w0,
                           probe_offset_hz=d0, loop_gain=1.0)
    check("A6 闭环 gain=1 ⇒ **一步**收敛（残差 < 1 Hz）",
          abs(_lk["residual_hz"]) < 1.0 and _lk["n_iter"] <= 2,
          "残差 = %.3e Hz · 轮数 = %d" % (_lk["residual_hz"], _lk["n_iter"]))

    _lk9 = M.frequency_lock(f0 + 2.0e5, f0, linewidth_hz=w0,
                            probe_offset_hz=d0, loop_gain=0.9, n_iter=200,
                            tol_hz=1e-3)
    check("A7 闭环 gain=0.9 ⇒ **几何收敛**（残差 < 1e-2 Hz 且轮数多于 gain=1）",
          abs(_lk9["residual_hz"]) < 1e-2 and _lk9["n_iter"] > _lk["n_iter"],
          "残差 = %.3e Hz · 轮数 = %d" % (_lk9["residual_hz"], _lk9["n_iter"]))

    check("A8 🔴 收敛判据用**相对线宽**（残差/线宽 < 1e-6），非绝对 Hz",
          _lk["residual_rel_linewidth"] < 1e-6,
          "残差/线宽 = %.3e" % _lk["residual_rel_linewidth"])

    _bis = M.lock_by_bisection(f0, linewidth_hz=w0, probe_offset_hz=d0, n_iter=140)
    check("A9 🔴 数值链**二分求根**锁定点 ↔ 反馈律不动点一致（|残差| < 1e-6 Hz）",
          abs(_bis["residual_hz"]) < 1.0e-6,
          "二分残差 = %.3e Hz · 区间 = %.3e Hz"
          % (_bis["residual_hz"], _bis["bracket_hz"]))

    # ══ B 磁场闭环 ═══════════════════════════════════════════════════════
    check("B1 两点法标度估计 k̂=V_ref/B_ref **无噪声代数精确**（= 1e3 V/T）",
          abs(M.scale_factor_estimate(1.0e3 * 100.0e-6, 100.0e-6) - 1.0e3) < 1e-9)

    _k_lsq = M.scale_factor_estimate_numeric(1.0e3 * 100.0e-6, 100.0e-6,
                                             noise_rel=1.0e-4)
    check("B2 🔴 闭式两点法 ↔ **全跨多点 LSQ 斜率**一致（相对残差 < 1e-5）",
          abs(_k_lsq - 1.0e3) / 1.0e3 < 1.0e-5,
          "k̂_LSQ = %.8f V/T · rel = %.3e" % (_k_lsq, abs(_k_lsq - 1.0e3) / 1.0e3))

    check("B3 ε_k 定义自洽（ε=|k̂−k|/k；k̂=1.02 ⇒ 0.02）",
          abs(M.scale_mismatch(1.02, 1.0) - 0.02) < 1e-12)

    _m0 = M.field_loop_calibrate(noise_frac=0.0)
    check("B4 无噪声闭环 ⇒ 读数相对误差**恰 0**（两点法代数精确，如实标注）",
          abs(_m0["readout_rel_error"]) < 1e-12)

    _m1 = M.field_loop_calibrate(noise_frac=1.0e-4)
    check("B5 有噪声 ⇒ 残差 > 0（**非**代数恒等）",
          _m1["readout_rel_error"] > 0.0,
          "误差 = %.3e" % _m1["readout_rel_error"])

    check("B6 🔴 读数相对误差 = ε_k（链②结论；浮点换算舍入 < 1e-8）",
          abs(_m1["readout_rel_error"] - _m1["scale_mismatch"]) < 1e-8,
          "ε_k = %.3e" % _m1["scale_mismatch"])

    # ══ C 动态范围 ═══════════════════════════════════════════════════════
    check("C1 噪声底 B_min ∝ √(1/τ)（τ×100 ⇒ B_min ×0.1）",
          abs(M.noise_floor_field(1e-9, 1.0)
              / M.noise_floor_field(1e-9, 100.0) - 10.0) < 1e-9)

    check("C2 线性段耗尽场 B_max ∝ 线宽（w×2 ⇒ B_max ×2）",
          abs(M.linear_range_max_field(2.0e7)
              / M.linear_range_max_field(1.0e7) - 2.0) < 1e-12)

    check("C3 DR 定义：20·log₁₀（幅度比 100 ⇒ 40 dB）",
          abs(M.dynamic_range_db(1.0, 100.0) - 40.0) < 1e-12)

    _dr_a = M.evaluate_dynamic_range(linewidth_hz=1.0e7)["dynamic_range_db"]
    _dr_b = M.evaluate_dynamic_range(linewidth_hz=5.0e7)["dynamic_range_db"]
    check("C4 DR 随线宽**单调增**（宽线宽 ⇒ 动态范围大，与灵敏度权衡）",
          _dr_b > _dr_a, "DR(10MHz)=%.1f dB < DR(50MHz)=%.1f dB" % (_dr_a, _dr_b))

    _dr_c = M.evaluate_dynamic_range(integration_s=100.0)["dynamic_range_db"]
    check("C5 DR 随积分时间**单调增**（长积分 ⇒ 噪声底降 ⇒ DR 升）",
          _dr_c > _dr_a, "DR(τ=1)=%.1f dB < DR(τ=100)=%.1f dB" % (_dr_a, _dr_c))

    _ac_c = M.ac_sensitivity(1e-9, 1e3)
    _ac_n = M.ac_sensitivity_numeric(1e-9, 1e3)
    check("C6 🔴 AC 灵敏度闭式 √(2Δf) ↔ **MC 带限噪声 rms** 一致（相对残差 < 5e-3）",
          abs(_ac_c - _ac_n) / _ac_c < 5e-3,
          "闭式 = %.6e · MC = %.6e · rel = %.3e"
          % (_ac_c, _ac_n, abs(_ac_c - _ac_n) / _ac_c))

    check("C7 AC 灵敏度 ∝ √Δf（Δf×4 ⇒ η_AC ×2）",
          abs(M.ac_sensitivity(1e-9, 4000.0) / M.ac_sensitivity(1e-9, 1000.0)
              - 2.0) < 1e-9)

    # ══ D 签核 ═══════════════════════════════════════════════════════════
    check("D1 闭环标定签核三合一（频锁 + 磁场闭环 + 动态范围）ACCEPT",
          M.locked_sensor_physics()["verdict"] == "ACCEPT",
          "verdict = %s" % M.locked_sensor_physics()["verdict"])

    check("D2 四情景动态范围表可现算（baseline/narrowline/wideline/longint）",
          set(M.dynamic_range_table()) == {"baseline", "narrowline", "wideline", "longint"},
          "scenarios = %s" % sorted(M.dynamic_range_table()))

    # ══ E 反向探针（各自必红）═══════════════════════════════════════════
    check("E1 探测偏置超 w/2（δ=w）⇒ 频锁参数非法必抛错",
          M._raises(lambda: M.frequency_lock(f0, f0, linewidth_hz=w0,
                                             probe_offset_hz=w0)))

    check("E2 零参考场 ⇒ 标度估计必抛错",
          M._raises(lambda: M.scale_factor_estimate(1.0, 0.0)))

    check("E3 η ≤ 0 ⇒ 噪声底必抛错",
          M._raises(lambda: M.noise_floor_field(0.0, 1.0)))

    check("E4 零线宽 ⇒ 线性段上限必抛错",
          M._raises(lambda: M.linear_range_max_field(0.0)))

    check("E5 零带宽 ⇒ AC 灵敏度必抛错",
          M._raises(lambda: M.ac_sensitivity(1e-9, 0.0)))

    check("E6 错误口径 ⇒ 口径自检必抛错",
          M._raises(lambda: M.assert_caliber("wrong_caliber")))

    check("E7 非对称区间（同号端点）⇒ 二分求根必抛错（零点不在区间）",
          M._raises(lambda: M.lock_by_bisection(f0, linewidth_hz=w0,
                                                probe_offset_hz=d0,
                                                lo_hz=f0 + 1.0e6,
                                                hi_hz=f0 + 2.0e6)))

    # 漂移探针：线宽真源改了 ⇒ DR 必变（判据依赖现算值，非恒真）
    _dr_p = M.evaluate_dynamic_range(linewidth_hz=2.0e7)["dynamic_range_db"]
    check("E8 线宽真源漂移必被检出（DR 判据读现算值）",
          _dr_p > _dr_a,
          "DR(20MHz)=%.1f dB > DR(10MHz)=%.1f dB" % (_dr_p, _dr_a))

    # ══ F 自入 CI core ════════════════════════════════════════════════════
    with open(os.path.join(_HERE, "run_ci_regression.py"), encoding="utf-8") as f:
        _ci = f.read()
    check("F1 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_qs_m5_smoke.py" in _ci)

    # 🔴 F2：B482–B484 的 golden 必须在 _GOLDEN_DISPATCH 内有定义。
    # 根因（QS-M4 血案）：_GOLDEN_DISPATCH 是**手工维护的硬编码字典** ⇒ 漏登
    #  ⇒ 全量照妖镜报「无黄金参考定义」且锚被判**自证桩**。本判据把
    # 「账本成员必在 golden 分派内」钉成常驻门禁（最前置一道）。
    from lda_harness.golden import _GOLDEN_DISPATCH as _GD
    _missing = [b for b in ("B482", "B483", "B484") if b not in _GD]
    check("F2 🔴 B482–B484 golden 必在 _GOLDEN_DISPATCH 内有定义（防漏登⇒假自证桩）",
          not _missing, "缺失 = %s" % _missing)

    # 🔴 F3：三锚必在 BENCHMARK_ORDER（增锚必同登两处契约的另半）
    from lda_harness.benchmarks import BENCHMARK_ORDER as _BO
    _missing_bo = [b for b in ("B482", "B483", "B484") if b not in _BO]
    check("F3 🔴 B482–B484 必在 BENCHMARK_ORDER 内（增锚同登契约）",
          not _missing_bo, "缺失 = %s" % _missing_bo)

    # ══ G 模块自检直连 ════════════════════════════════════════════════════
    _sc = M.selfcheck_qs_m5()
    check("G1 qs_m5.selfcheck_qs_m5 全项 PASS（%d 项）" % len(_sc),
          all(_sc.values()),
          "FAIL = %s" % [k for k, v in _sc.items() if not v])

    print("")
    print("门禁 smoke：%d PASS / %d FAIL"
          % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
