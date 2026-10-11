#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QS-M7（G9 超导量子传感优化）· 量子传感器 **SQUID 性能冲刺（噪声优化）** 门禁（v0.9.224）。

═══ 判什么（分节）═══
A 磁通聚焦变压器有效面积（washer 电感 L≅1.25µ0d 定义自洽 · **闭式分压比 ⇄ 离散
  Neumann 互感重建**一致（rel<2e-2）· 🔴 **粗网格 ⇒ 残差显著放大**（证明是真数值
  残差非代数恒等）· γ_A ↑ ⇒ A_eff ↑（单调）· L_i=L_p ⇒ A_eff 最大（阻抗匹配最优）·
  A_eff > 裸环几何面积（变压器增益 > 1））·
B 亚微米结噪声（Johnson S_I=4k_BT/R ∝ T、∝1/R · **闭式 S_Φ,opt ⇄ MC 数值**一致 ·
  A-B 乘积 I_c·R_n=πΔ/(2e) 线性于 Δ · R_n 抬升饱和 g(ρ)→max_gain 边界自洽 ·
  ρ=1 ⇒ g=1 退化裸结）·
C 优化后磁场灵敏度（**闭式 B_N,opt ⇄ MC+数值互感**一致 · B_N,opt < 基线（优化增益 > 1）
  · 低温更优 · 综合链路报告值 == 现算 · 情景表可现算）·
D 签核（design_qs_noise_opt 三链串联全绿 + 情景表可现算）·
E 反向探针（零拾取面积 ⇒ A_eff 零 · 错口径 ⇒ 抛 · 情景单调性方向反证 · **粗网格
  ⇒ 闭式⇄数值残差显著放大**（证明是真数值残差非代数恒等））·
F 自入 CI core（防静默漏接 · **G2 golden 分派必含三锚**（防漏登⇒假自证桩）·
  三锚必在 BENCHMARK_ORDER）·
G 模块自检直连（qs_m7.selfcheck_qs_m7 全项 PASS）。

═══ 🔴 锚账本口径（本档**净增 3 道锚** B488–B490）═══
QS-M7 交付**新物理量**（非既有锚的重复）：
  · **B488** 磁通聚焦变压器有效面积 A_eff（优化专属：m²）；
  · **B489** 亚微米结噪声约束磁通噪声谱密度 S_Φ,opt（优化专属：Wb²/Hz）；
  · **B490** 优化后磁场灵敏度 B_N,opt（优化专属：T/√Hz）。
🔴 **如实不登记**：washer 电感 L≅1.25µ0d（**定义式**）· 阻抗匹配 L_i=L_p ⇒ A_eff 最大
（**最优性**）· γ↑⇒A_eff↑ / 低温更优 / 大拾取环更优（**单调性**）· R_n 抬升饱和
（**饱和极限**）· 优化增益 / SOTA 比（**派生标量**）——以上归本 smoke 覆盖，
**不登记为 B 锚**（宁可少，不越级谎报）。
🔴 **不含梯度计/CMRR 链**（QS-M4 B480 已占 ⇒ 避免撞车）。
QS-M0–M6 的 NV 磁力计 / 标定 / 裸 SQUID 环物理均**不重复登记**。

═══ 诚实边界 ═══
· 拾取环面积 / 自感 / 互感 / 结 R_n / 温 / 聚焦因子均为**设计示例量级**（4 K 超导典型），
  **非实测 PDK**。
· 🔴 本档**不做**器件级/系统级性能宣称；报告为**建模值**（B_N,opt≈1.73 fT/√Hz）。
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
    from lda_l2 import qs_m7 as M

    ic0 = 2.0e-6
    rn_opt = 142.5
    ap = (500.0e-6) ** 2
    m_h = 1.6e-9
    li = 2.0e-9
    lp = 2.0e-9

    # ══ A 磁通聚焦变压器有效面积 ═════════════════════════════════════════
    _L1 = M.washer_inductance_h(100.0e-6)
    _L2 = M.washer_inductance_h(200.0e-6)
    check("A1 washer 电感 L≅1.25·µ0·d 线性于孔径（d×2 ⇒ L×2）",
          abs(_L2 - 2.0 * _L1) < 1e-20 * max(abs(_L2), 1.0))

    _a_closed = M.transformer_effective_area_m2(ap, m_h, li, lp, 1.5)
    _a_num = M.transformer_effective_area_numeric(ap, m_h, li, lp, 1.5)
    check("A2 🔴 闭式分压比 ⇄ **离散 Neumann 互感重建**一致（rel < 2e-2）",
          abs(_a_closed - _a_num) <= 0.02 * _a_closed,
          "闭式 = %.6e · 数值 = %.6e · rel = %.3e"
          % (_a_closed, _a_num, abs(_a_closed - _a_num) / _a_closed))

    _a_coarse = M.transformer_effective_area_numeric(ap, m_h, li, lp, 1.5, n_seg=32)
    check("A3 🔴 粗网格(n_seg=32) ⇒ 闭式⇄数值残差显著放大（证明真数值残差非代数恒等）",
          abs(_a_coarse - _a_closed) > 5.0 * abs(_a_num - _a_closed),
          "粗 rel = %.3e · 细 rel = %.3e"
          % (abs(_a_coarse - _a_closed) / _a_closed,
             abs(_a_num - _a_closed) / _a_closed))

    _a_g1 = M.transformer_effective_area_m2(ap, m_h, li, lp, 1.0)
    _a_g2 = M.transformer_effective_area_m2(ap, m_h, li, lp, 2.0)
    check("A4 γ_A ↑ ⇒ A_eff ↑（几何聚焦单调）",
          _a_g1 < _a_closed < _a_g2)

    _a_match = M.transformer_effective_area_m2(ap, m_h, 2.0e-9, 2.0e-9, 1.5)
    _a_mismatch = M.transformer_effective_area_m2(ap, m_h, 20.0e-9, 2.0e-9, 1.5)
    check("A5 🔴 阻抗匹配 L_i=L_p ⇒ A_eff **最大**（失配则劣化）",
          _a_match > _a_mismatch,
          "匹配 = %.4e · 失配 = %.4e" % (_a_match, _a_mismatch))

    check("A6 变压器增益 > 1（A_eff > 裸环几何面积 100µm²）",
          _a_closed > (100.0e-6) ** 2)

    # ══ B 亚微米结噪声 ═══════════════════════════════════════════════════
    check("B1 Johnson 噪声 S_I=4k_BT/R ∝ T（T×2 ⇒ S_I×2）",
          abs(M.johnson_noise_current_psd(8.4, 20.0)
              - 2.0 * M.johnson_noise_current_psd(4.2, 20.0)) < 1e-30)

    check("B2 Johnson 噪声 ∝ 1/R（R×0.5 ⇒ S_I×2）",
          abs(M.johnson_noise_current_psd(4.2, 20.0)
              - 0.5 * M.johnson_noise_current_psd(4.2, 10.0)) < 1e-30)

    _ab1 = M.ambegaokar_baratoff_product_v(1.0e-3 * M.E_CHARGE)
    _ab2 = M.ambegaokar_baratoff_product_v(2.0e-3 * M.E_CHARGE)
    check("B3 A-B 乘积 I_c·R_n=πΔ/(2e) 线性于 Δ（Δ×2 ⇒ 乘积×2）",
          abs(_ab2 - 2.0 * _ab1) < 1e-15 * max(abs(_ab2), 1.0))

    _s_closed = M.submicron_junction_noise_psd(4.2, ic0, rn_opt, 0.30)
    _s_num = M.submicron_junction_noise_psd_numeric(4.2, ic0, rn_opt, 0.30)
    check("B4 🔴 闭式 S_Φ,opt ⇄ **MC 数值**一致（rel < 1e-2）",
          abs(_s_closed - _s_num) <= 0.01 * _s_closed,
          "闭式 = %.6e · MC = %.6e · rel = %.3e"
          % (_s_closed, _s_num, abs(_s_closed - _s_num) / _s_closed))

    check("B5 S_Φ,opt ∝ T（热噪声主导：T=8.4 ⇒ S_Φ×2）",
          abs(M.submicron_junction_noise_psd(8.4, ic0, rn_opt, 0.30)
              - 2.0 * M.submicron_junction_noise_psd(4.2, ic0, rn_opt, 0.30)) < 1e-46)

    check("B6 亚微米 R_n 抬升边界：ρ=1 ⇒ g=1（退化裸结）",
          abs(M.submicron_resistance_gain(1.0) - 1.0) < 1e-12)

    check("B7 🔴 R_n 抬升饱和（ρ→∞ ⇒ g→max_gain，非无限上升）",
          M.submicron_resistance_gain(1e9) < 8.0 + 1e-9
          and M.submicron_resistance_gain(4.0) > M.submicron_resistance_gain(2.0))

    # ══ C 优化后磁场灵敏度 ═══════════════════════════════════════════════
    _b_closed = M.optimized_field_sensitivity_t_per_sqrt_hz(
        4.2, ic0, rn_opt, ap, m_h, li, lp, 1.5, 0.30)
    _b_num = M.optimized_field_sensitivity_numeric(
        4.2, ic0, rn_opt, ap, m_h, li, lp, 1.5, 0.30)
    check("C1 🔴 闭式 B_N,opt ⇄ **MC + 数值互感**一致（rel < 2e-2）",
          abs(_b_closed - _b_num) <= 0.02 * _b_closed,
          "闭式 = %.6e · 数值 = %.6e · rel = %.3e"
          % (_b_closed, _b_num, abs(_b_closed - _b_num) / _b_closed))

    check("C2 🔴 优化后优于基线（B_N,opt < 79.25 fT/√Hz ⇒ 优化增益 > 1）",
          _b_closed < 79.25e-15,
          "B_N,opt = %.3f fT/√Hz" % (_b_closed * 1e15))

    _b_lo = M.optimized_field_sensitivity_t_per_sqrt_hz(
        1.5, ic0, rn_opt, ap, m_h, li, lp, 1.5, 0.30)
    check("C3 低温更优（T=1.5 K ⇒ B_N,opt < 4.2 K）",
          _b_lo < _b_closed)

    _phys = M.squid_noise_optimization_physics()
    check("C4 综合链路报告值 == 现算",
          abs(_phys["b_n_opt_t_per_sqrt_hz"] - _b_closed) < 1e-30)

    check("C5 情景表可现算（5 情景全非空）",
          len(M.optimization_table()) == 5
          and all(v["b_n_opt_fT_per_sqrt_hz"] > 0 for v in M.optimization_table().values()))

    # ══ D 签核 ═══════════════════════════════════════════════════════════
    _design = M.design_qs_noise_opt()
    check("D1 design_qs_noise_opt 三链串联全绿（verdict=ACCEPT）",
          _design["verdict"] == "ACCEPT"
          and all(_design["checks"].values()),
          "verdict = %s" % _design["verdict"])

    # ══ E 反向探针 ═══════════════════════════════════════════════════════
    check("E1 🔴 零拾取面积 ⇒ 抛（非法）",
          M._raises(lambda: M.transformer_effective_area_m2(0.0, m_h, li, lp)))

    check("E2 🔴 零互感 ⇒ 抛（非法）",
          M._raises(lambda: M.transformer_effective_area_m2(ap, 0.0, li, lp)))

    check("E3 🔴 错口径 ⇒ assert_caliber 抛",
          M._raises(lambda: M.assert_caliber("wrong_caliber")))

    check("E4 🔴 面积失配（L_i=10·L_p）⇒ A_eff 显著劣化（情景单调性方向反证）",
          M.evaluate_scenario("impedance_mismatch")["a_eff_m2"]
          < M.evaluate_scenario("baseline")["a_eff_m2"])

    _e5_coarse = M.transformer_effective_area_numeric(ap, m_h, li, lp, 1.5, n_seg=16)
    check("E5 🔴 极粗网格(n_seg=16) ⇒ 残差 ≫ 细网格（真数值残差）",
          abs(_e5_coarse - _a_closed) > 3.0 * abs(_a_num - _a_closed),
          "rel = %.3e" % (abs(_e5_coarse - _a_closed) / _a_closed))

    # ══ F 自入 CI core ═══════════════════════════════════════════════════
    with open(os.path.join(_HERE, "run_ci_regression.py"), encoding="utf-8") as f:
        _ci = f.read()
    check("F1 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_qs_m7_smoke.py" in _ci)

    from lda_harness.golden import _GOLDEN_DISPATCH as _GD
    _missing = [b for b in ("B488", "B489", "B490") if b not in _GD]
    check("F2 🔴 B488–B490 golden 必在 _GOLDEN_DISPATCH 内有定义（防漏登⇒假自证桩）",
          not _missing, "缺失 = %s" % _missing)

    from lda_harness.benchmarks import BENCHMARK_ORDER as _BO
    _missing_bo = [b for b in ("B488", "B489", "B490") if b not in _BO]
    check("F3 🔴 B488–B490 必在 BENCHMARK_ORDER 内（增锚同登契约）",
          not _missing_bo, "缺失 = %s" % _missing_bo)

    # ══ G 模块自检直连 ═══════════════════════════════════════════════════
    _sc = M.selfcheck_qs_m7()
    check("G1 qs_m7.selfcheck_qs_m7 全项 PASS（%d 项）" % len(_sc),
          all(_sc.values()),
          "FAIL = %s" % [k for k, v in _sc.items() if not v])

    print("")
    print("门禁 smoke：%d PASS / %d FAIL"
          % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
