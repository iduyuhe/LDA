#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QS-M6（G8 超导量子器件物理）· 量子传感器 **超导 SQUID 磁力计** 门禁（v0.9.223）。

═══ 判什么（分节）═══
A 约瑟夫森 RCSJ 结（直流约瑟夫森关系 I_s=I_c·sinδ 在 δ=π/2 达 I_c · Ambegaokar–
  Baratoff 闭式 I_c·R_n=πΔ/(2e) 线性于 Δ · 等离子频率 ω_p∝√I_c · McCumber
  β_c=ω_pRC 定义自洽 · **RCSJ 积分器**：偏置 < I_c ⇒ 相位**锁定**于 δ_eq=asin(I_b/I_c) /
  偏置 > I_c ⇒ **逃逸** · 0.99/1.01·I_c 两侧判据**翻转**）·
B SQUID 环路临界电流 I_c(Φ)（f=0 取 2I_c0 · f=0.5 取零 · 周期 1 · **闭式 ⇄ 相位扫描**
  一致（**非对齐** f=0.30）· 🔴 **对齐 f=0.25 ⇒ 代数恒等**（残差恒 0，须显式标注，
  不可作独立锚）· 转导闭式 ⇄ 数值中心差分一致 · 转导在 f=0 为零 · f=0.25 幅值
  =√2πI_c0/Φ0 · 有效面积 ∝ side² · B=Φ/A）·
C 磁通噪声 → 磁场灵敏度（Johnson S_I=4k_BT/R ∝ T、∝1/R · **闭式 S_Φ ⇄ MC 数值**一致
  · S_Φ∝T · S_Φ∝1/转导² · B_N∝√S_Φ · B_N∝1/A · fT 折换 · 综合链路报告值 == 现算）·
D 签核（design_qs_squid 三链串联全绿 + 情景表可现算）·
E 反向探针（零转导 ⇒ S_Φ 爆 · 错口径 ⇒ 抛 · 情景单调性方向反证 · **粗网格/粗步长
  ⇒ 闭式⇄数值残差显著放大**（证明是真数值残差非代数恒等））·
F 自入 CI core（防静默漏接 · **G2 golden 分派必含三锚**（防漏登⇒假自证桩）·
  三锚必在 BENCHMARK_ORDER）·
G 模块自检直连（qs_m6.selfcheck_qs_m6 全项 PASS）。

═══ 🔴 锚账本口径（本档**净增 3 道锚** B485–B487）═══
QS-M6 交付**新物理量**（非既有锚的重复）：
  · **B485** SQUID 环路临界电流磁通调制 I_c(Φ)（超导磁力计专属：A）；
  · **B486** 磁通-电压转导 ∂I_c/∂Φ（超导磁力计专属：A/Wb）；
  · **B487** 磁场灵敏度谱密度 B_N（超导磁力计专属：T/√Hz）。
🔴 **如实不登记**：RCSJ 锁定判据 δ_eq=asin(I_b/I_c)（**平衡态/定义**）· β_c 滞回判据
（**无量纲定义**）· I_c 在 f=0 极大 / f=0.5 为零（**对称性**）· A_eff=side² / B=Φ/A
（**纯几何定义**）· S_Φ∝T / B_N∝√S_Φ / B_N∝1/A（**标度律**）· 情景单调性（**单调性**）
——以上归本 smoke 覆盖，**不登记为 B 锚**（宁可少，不越级谎报）。
QS-M0–M5 的 NV 磁力计 / 标定物理均**不重复登记**（不同物理对象：电-磁通 vs 光-自旋-磁）。

═══ 诚实边界 ═══
· 结临界电流 I_c0 / 正常态电阻 R_n / 能隙 Δ / 温度 T / 环面积 A_eff / 电感均为
  **设计示例量级**（4 K 超导典型），**非实测 PDK**。
· 🔴 本档**不做**器件级/系统级性能宣称；报告为**建模值**（baseline B_N≈79.25 fT/√Hz）。
· 🔴 「SQUID 集成 1–5 fT/√Hz」为**蓝图层引用的公开文献值**（物理学报 2025,74,20250426），
  作**对标准星**；本档建模值与之**独立**，**不得**声称「实测达到 1–5 fT/√Hz」。
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
    from lda_l2 import qs_m6 as M

    ic0 = 2.0e-6

    # ══ A 约瑟夫森 RCSJ 结 ═══════════════════════════════════════════════
    check("A1 直流约瑟夫森关系在 δ=π/2 达 I_c（I_s=I_c·sinδ）",
          abs(M.josephson_current(1.0, 3.141592653589793 / 2.0) - 1.0) < 1e-15)

    check("A2 零相位 ⇒ 零电流（I_s(0)=0）",
          abs(M.josephson_current(1.0, 0.0)) < 1e-15)

    _ab1 = M.ambegaokar_baratoff_ic_rn(1.0e-3 * M.E_CHARGE)
    _ab2 = M.ambegaokar_baratoff_ic_rn(2.0e-3 * M.E_CHARGE)
    check("A3 Ambegaokar–Baratoff 闭式 I_c·R_n=πΔ/(2e) 线性于 Δ",
          abs(_ab2 - 2.0 * _ab1) < 1e-15 * max(abs(_ab2), 1.0))

    _w1 = M.plasma_frequency_rad_s(1.0e-6, 4.0e-13)
    _w2 = M.plasma_frequency_rad_s(4.0e-6, 4.0e-13)
    check("A4 等离子频率 ω_p=√(2eI_c/ħC) ∝ √I_c（I_c×4 ⇒ ω_p×2）",
          abs(_w2 - 2.0 * _w1) < 1e-9 * _w1)

    check("A5 McCumber β_c=ω_p·R·C 定义自洽",
          abs(M.mccumber_beta_c(1.0e-6, 4.0e-13, 20.0)
              - M.plasma_frequency_rad_s(1.0e-6, 4.0e-13) * 20.0 * 4.0e-13) < 1e-15)

    _dt = 1.0 / (40.0 * M.plasma_frequency_rad_s(2.0e-6, 4.0e-13))
    _st_lock = M.rcsj_integrate(0.1, 0.0, ic_a=2.0e-6, capacitance_f=4.0e-13,
                                resistance_ohm=20.0, i_bias_a=1.0e-6,
                                dt_s=_dt, n_steps=400000)
    check("A6 🔴 RCSJ 积分器：偏置 < I_c ⇒ 相位**锁定**（δ′→0）",
          abs(_st_lock["ddelta_rad_s"]) < 1e4,
          "δ′=%.3e rad/s · δ=%.4f rad" % (_st_lock["ddelta_rad_s"], _st_lock["delta_rad"]))

    _d_eq = 3.141592653589793 * 0 + __import__("math").asin(1.0e-6 / 2.0e-6)
    _resid = abs((_st_lock["delta_rad"] - _d_eq + 3.141592653589793)
                 % (2.0 * 3.141592653589793) - 3.141592653589793)
    check("A7 🔴 锁定末态相位 == 闭式平衡点 δ_eq=asin(I_b/I_c)（模 2π）",
          _resid < 1e-3, "残差 = %.3e rad" % _resid)

    _st_run = M.rcsj_integrate(0.1, 0.0, ic_a=2.0e-6, capacitance_f=4.0e-13,
                               resistance_ohm=20.0, i_bias_a=3.0e-6,
                               dt_s=_dt, n_steps=400000)
    check("A8 RCSJ：偏置 > I_c ⇒ 相位**逃逸**（δ′ 显著非零，washboard 倾斜）",
          abs(_st_run["ddelta_rad_s"]) > 1e6,
          "δ′=%.3e rad/s" % _st_run["ddelta_rad_s"])

    _st_lo = M.rcsj_integrate(0.1, 0.0, ic_a=2.0e-6, capacitance_f=4.0e-13,
                              resistance_ohm=20.0, i_bias_a=0.99 * 2.0e-6,
                              dt_s=_dt, n_steps=400000)
    _st_hi = M.rcsj_integrate(0.1, 0.0, ic_a=2.0e-6, capacitance_f=4.0e-13,
                              resistance_ohm=20.0, i_bias_a=1.01 * 2.0e-6,
                              dt_s=_dt, n_steps=400000)
    check("A9 🔴 I_c 两侧判据**翻转**（0.99I_c 锁定 / 1.01I_c 逃逸）",
          abs(_st_lo["ddelta_rad_s"]) < 1e4 and abs(_st_hi["ddelta_rad_s"]) > 1e6,
          "δ′(−)=%.2e · δ′(+)=%.2e" % (_st_lo["ddelta_rad_s"], _st_hi["ddelta_rad_s"]))

    # ══ B SQUID 环路临界电流 / 转导 ══════════════════════════════════════
    check("B1 I_c(Φ) 在 f=0 取 2·I_c0（两结同相）",
          abs(M.squid_critical_current(ic0, 0.0) - 2.0 * ic0) < 1e-18)

    check("B2 I_c(Φ) 在 f=0.5 取零（完全相消）",
          abs(M.squid_critical_current(ic0, 0.5)) < 1e-18)

    check("B3 I_c(Φ) 周期为 1（f=1 复位）",
          abs(M.squid_critical_current(ic0, 1.0)
              - M.squid_critical_current(ic0, 0.0)) < 1e-18)

    check("B4 🔴 闭式 ⇄ **相位空间扫描**一致（非对齐 f=0.30，rel < 1e-6）",
          abs(M.squid_critical_current(ic0, 0.30)
              - M.squid_critical_current_numeric(ic0, 0.30))
          <= 1e-6 * abs(M.squid_critical_current(ic0, 0.30)),
          "rel = %.3e" % (abs(M.squid_critical_current(ic0, 0.30)
                              - M.squid_critical_current_numeric(ic0, 0.30))
                          / abs(M.squid_critical_current(ic0, 0.30))))

    check("B5 🔴 对齐 f=0.25 ⇒ 闭式==数值**恰等**（代数恒等 · 不可作独立锚，如实标注）",
          abs(M.squid_critical_current(ic0, 0.25)
              - M.squid_critical_current_numeric(ic0, 0.25)) == 0.0)

    _t_closed = M.squid_transfer_function(ic0, 0.0, 0.30)
    _t_num = M.squid_transfer_function_numeric(ic0, 0.0, 0.30, dflux=1e-6)
    check("B6 🔴 转导闭式 ⇄ **数值中心差分**一致（rel < 1e-6）",
          abs(_t_closed - _t_num) <= 1e-6 * abs(_t_closed),
          "闭式 = %.6e · 数值 = %.6e · rel = %.3e"
          % (_t_closed, _t_num, abs(_t_closed - _t_num) / abs(_t_closed)))

    check("B7 转导在 f=0 处为零（cos 极大 ⇒ 斜率为零）",
          abs(M.squid_transfer_function(ic0, 0.0, 0.0)) < 1e-18)

    _t_q = M.squid_transfer_function(ic0, 0.0, 0.25)
    _expect_q = __import__("math").sqrt(2.0) * 3.141592653589793 * ic0 / M.FLUX_QUANTUM_WB
    check("B8 f=0.25 转导幅值 = √2·π·I_c0/Φ0（|sin(πf)|=√2/2 处）",
          abs(abs(_t_q) - _expect_q) < 1e-12 * _expect_q,
          "|转导| = %.6e · 期望 = %.6e" % (abs(_t_q), _expect_q))

    check("B9 有效拾取面积 A_eff=side²（×2 边长 ⇒ ×4 面积）",
          abs(M.effective_pickup_area_m2(2.0)
              - 4.0 * M.effective_pickup_area_m2(1.0)) < 1e-18)

    check("B10 磁通-磁场换算 B=Φ/A_eff",
          abs(M.flux_to_field_t(1e-12, 1e-8) - 1e-4) < 1e-18)

    # ══ C 磁通噪声 → 磁场灵敏度 ═══════════════════════════════════════════
    check("C1 Johnson 噪声 S_I=4k_BT/R ∝ T",
          abs(M.johnson_noise_current_psd(2.0, 10.0)
              - 2.0 * M.johnson_noise_current_psd(1.0, 10.0)) < 1e-30)

    check("C2 Johnson 噪声 ∝ 1/R（R×0.5 ⇒ S_I×2）",
          abs(M.johnson_noise_current_psd(4.2, 20.0)
              - 0.5 * M.johnson_noise_current_psd(4.2, 10.0)) < 1e-30)

    _t_abs = abs(M.squid_transfer_function(ic0, 0.0, 0.25))
    _s_closed = M.flux_noise_psd(4.2, 20.0, _t_abs)
    _s_num = M.flux_noise_psd_numeric(4.2, 20.0, ic0, 0.0, 0.25, n_mc=400000)
    check("C3 🔴 S_Φ 闭式 ⇄ **MC 数值**一致（固定 seed · rel < 2e-2）",
          abs(_s_closed - _s_num) <= 0.02 * _s_closed,
          "闭式 = %.6e · MC = %.6e · rel = %.3e"
          % (_s_closed, _s_num, abs(_s_closed - _s_num) / _s_closed))

    check("C4 S_Φ ∝ T（热噪声主导）",
          abs(M.flux_noise_psd(8.4, 20.0, _t_abs)
              - 2.0 * M.flux_noise_psd(4.2, 20.0, _t_abs)) < 1e-40)

    check("C5 S_Φ ∝ 1/转导²（转导×2 ⇒ S_Φ×1/4）",
          abs(M.flux_noise_psd(4.2, 20.0, 2.0 * _t_abs)
              - 0.25 * M.flux_noise_psd(4.2, 20.0, _t_abs)) < 1e-45)

    check("C6 B_N ∝ √S_Φ（S_Φ×4 ⇒ B_N×2）",
          abs(M.field_sensitivity_t_per_sqrt_hz(4.0 * _s_closed, 1e-8)
              - 2.0 * M.field_sensitivity_t_per_sqrt_hz(_s_closed, 1e-8)) < 1e-30)

    check("C7 B_N ∝ 1/A_eff（面积×2 ⇒ B_N×0.5）",
          abs(M.field_sensitivity_t_per_sqrt_hz(_s_closed, 2e-8)
              - 0.5 * M.field_sensitivity_t_per_sqrt_hz(_s_closed, 1e-8)) < 1e-30)

    check("C8 fT 折换正确（×1e15）",
          abs(M.field_sensitivity_fT_per_sqrt_hz(_s_closed, 1e-8)
              - 1e15 * M.field_sensitivity_t_per_sqrt_hz(_s_closed, 1e-8)) < 1e-15)

    _rep = M.squid_magnetometer_physics()
    check("C9 综合链路自洽：报告 B_N == 现算（判据读现算值）",
          abs(_rep["b_n_t_per_sqrt_hz"]
              - M.field_sensitivity_t_per_sqrt_hz(_rep["s_flux_wb2_per_hz"],
                                                  _rep["area_m2"])) < 1e-40)

    check("C10 综合链路：报告 I_c(Φ=0.25Φ0) == 现算",
          abs(_rep["ic_phi_a"] - M.squid_critical_current(ic0, 0.25)) < 1e-18)

    # ══ D 签核 ═══════════════════════════════════════════════════════════
    _design = M.design_qs_squid(run_checks=True)
    check("D1 三链串联签核：模块自检全项 PASS",
          bool(_design.get("selfcheck_pass")),
          "FAIL = %s" % [k for k, v in _design.get("selfcheck", {}).items() if not v])

    check("D2 五情景灵敏度表可现算（baseline/small_loop/large_loop/low_temp/high_ic）",
          set(M.sensitivity_table()) == {"baseline", "small_loop", "large_loop",
                                         "low_temp", "high_ic"},
          "scenarios = %s" % sorted(M.sensitivity_table()))

    # ══ E 反向探针（各自必红）═══════════════════════════════════════════
    check("E1 零转导 ⇒ S_Φ 必抛错（除零）",
          M._raises(lambda: M.flux_noise_psd(4.2, 20.0, 0.0)))

    check("E2 错误口径 ⇒ 口径自检必抛错",
          M._raises(lambda: M.assert_caliber("wrong_caliber")))

    check("E3 情景单调性方向反证：大环灵敏度**优于**小环（fT/√Hz 更小）",
          M.evaluate_scenario("large_loop")["b_n_fT_per_sqrt_hz"]
          < M.evaluate_scenario("small_loop")["b_n_fT_per_sqrt_hz"],
          "large=%.3f < small=%.3f"
          % (M.evaluate_scenario("large_loop")["b_n_fT_per_sqrt_hz"],
             M.evaluate_scenario("small_loop")["b_n_fT_per_sqrt_hz"]))

    check("E4 低温灵敏度**优于**常温（S_Φ∝T）",
          M.evaluate_scenario("low_temp")["b_n_fT_per_sqrt_hz"]
          < M.evaluate_scenario("baseline")["b_n_fT_per_sqrt_hz"])

    # 🔴 E5：粗网格 ⇒ 闭式⇄数值残差**显著放大**（证明是真数值残差，非代数恒等）
    _cf03 = M.squid_critical_current(ic0, 0.30)
    _fine = M.squid_critical_current_numeric(ic0, 0.30, n_grid=1 << 18)
    _coarse = M.squid_critical_current_numeric(ic0, 0.30, n_grid=64)
    check("E5 🔴 粗网格(n=64) ⇒ 残差 ≫ 细网格(2^18)（真离散化残差 · 非代数恒等）",
          abs(_cf03 - _coarse) > 1e3 * abs(_cf03 - _fine),
          "coarse rel = %.3e · fine rel = %.3e"
          % (abs(_cf03 - _coarse) / _cf03, abs(_cf03 - _fine) / _cf03))

    # 🔴 E6：粗步长 ⇒ 转导数值残差显著增大（证明是真有限差分残差）
    _tc = M.squid_transfer_function(ic0, 0.0, 0.30)
    _tf = M.squid_transfer_function_numeric(ic0, 0.0, 0.30, dflux=1e-6)
    _tk = M.squid_transfer_function_numeric(ic0, 0.0, 0.30, dflux=1e-2)
    check("E6 🔴 粗步长(ΔΦ=1e-2) ⇒ 转导残差 ≫ 细步长(1e-6)（真有限差分残差）",
          abs(_tc - _tk) > 1e3 * abs(_tc - _tf),
          "coarse rel = %.3e · fine rel = %.3e"
          % (abs(_tc - _tk) / abs(_tc), abs(_tc - _tf) / abs(_tc)))

    # ══ F 自入 CI core ════════════════════════════════════════════════════
    with open(os.path.join(_HERE, "run_ci_regression.py"), encoding="utf-8") as f:
        _ci = f.read()
    check("F1 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_qs_m6_smoke.py" in _ci)

    # 🔴 F2：B485–B487 的 golden 必须在 _GOLDEN_DISPATCH 内有定义。
    # 根因（QS-M4 血案）：_GOLDEN_DISPATCH 是**手工维护的硬编码字典** ⇒ 漏登
    #  ⇒ 全量照妖镜报「无黄金参考定义」且锚被判**自证桩**。本判据把
    # 「账本成员必在 golden 分派内」钉成常驻门禁（最前置一道）。
    from lda_harness.golden import _GOLDEN_DISPATCH as _GD
    _missing = [b for b in ("B485", "B486", "B487") if b not in _GD]
    check("F2 🔴 B485–B487 golden 必在 _GOLDEN_DISPATCH 内有定义（防漏登⇒假自证桩）",
          not _missing, "缺失 = %s" % _missing)

    # 🔴 F3：三锚必在 BENCHMARK_ORDER（增锚必同登契约的另半）
    from lda_harness.benchmarks import BENCHMARK_ORDER as _BO
    _missing_bo = [b for b in ("B485", "B486", "B487") if b not in _BO]
    check("F3 🔴 B485–B487 必在 BENCHMARK_ORDER 内（增锚同登契约）",
          not _missing_bo, "缺失 = %s" % _missing_bo)

    # ══ G 模块自检直连 ════════════════════════════════════════════════════
    _sc = M.selfcheck_qs_m6()
    check("G1 qs_m6.selfcheck_qs_m6 全项 PASS（%d 项）" % len(_sc),
          all(_sc.values()),
          "FAIL = %s" % [k for k, v in _sc.items() if not v])

    print("")
    print("门禁 smoke：%d PASS / %d FAIL"
          % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
