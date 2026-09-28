# -*- coding: utf-8 -*-
"""P6 · T6.4 常驻门禁：EIC 行为级（per-MZI 驱动 + TIA 阵列）· L2 系统级。

判据分组（A–K）
---------------
A 契约 / 披露（7 键齐全 + 关键立场字面）
B 闭式正确性（**独立重算** v(t)=V_dd(1−e^{−t/τ})；t→0、t→∞ 两端极限）
C 候选与 golden 一致（默认档残差 < tol **且 > 1e-12** ⇒ 非恒等、非地板）
D **判据 D**（残差随离散步数 N 严格单调下降 + **实测**比值 ≈ 16⁴ = O(h⁴)）
E 电压→相位（Vπ 由 VπL 与臂长独立重算；VπL 口径与 `build_mesh_pnr` 同源）
F 相位量化（DAC 位深 ⇒ 步进闭式独立重算 + 单调性）
G TIA 单极点（f=0 ⇒ Z=R_f；f=f_3dB ⇒ |Z|=R_f/√2；带宽闭式）
H **零能效/功耗守卫**（必 raise ×3 + 合法必过 ×4 —— 铁律 8）
I 输入域（必 raise + 边界合法必过）
J 结论钉死（上升时延闭式落在窄带 + 与 RK4 一致；满摆幅相位闭式一致）
K 判据有效性自证（**注入假 RK4 ⇒ D 组必红**，证明判据非恒真）

🔴 立场：断言的是**事实** —— `A`/`H` 断言**零能效数字**；`D` 断言**收敛阶来自实测**；
`A` 断言「只到行为级、不碰晶体管级」。若有人补上 pJ/bit、或把 RK4 换成恒等实现，这些判据立刻变红。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
from lda_l2.eic_behavioral import (  # noqa: E402
    C_F_F_DEFAULT,
    DAC_BITS_DEFAULT,
    EIC_DISCLOSURE,
    R_F_OHM_DEFAULT,
    TAU_DRIVER_S_DEFAULT,
    V_DD_DEFAULT,
    VPI_L_V_MM_DEFAULT,
    EicBehavioralError,
    assert_no_energy_metrics,
    driver_step_closed_form,
    driver_step_rk4,
    eic_budget,
    mzi_phase_from_voltage,
    phase_resolution_rad,
    tia_bandwidth_hz,
    tia_transimpedance_ohm,
    vpi_from_vpi_l,
)

PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True, detail_fmt="  —— {d}", detail_on="fail")

T_EVAL = 4.0 * TAU_DRIVER_S_DEFAULT
NS_SCAN = (16, 64, 256, 1024)


def _raises(fn, exc=EicBehavioralError):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def main():  # noqa: C901
    print("=== P6 · T6.4 EIC 行为级门禁 ===")

    # ---------------------------------------------------------------- A 契约
    print("--- A 契约 / 披露 ---")
    check("A1 披露 7 键齐全（防有人悄悄删掉诚实声明）",
          len(EIC_DISCLOSURE) == 7, "%d 键" % len(EIC_DISCLOSURE))
    blob = " ".join(EIC_DISCLOSURE.values())
    check("A2 披露含「零能效数字」与「行为级」「不碰晶体管级」字面",
          "零能效数字" in blob and "行为级" in blob and "不碰晶体管级" in blob)
    check("A3 披露含「数值格式属性」字面（防把 O(h⁴) 当器件精度）",
          "数值格式" in blob)

    # ------------------------------------------------------------ B 闭式正确性
    print("--- B 闭式正确性（独立重算）---")
    for t, tau in ((0.0, TAU_DRIVER_S_DEFAULT), (1e-11, TAU_DRIVER_S_DEFAULT),
                   (4e-11, 5e-12)):
        want = V_DD_DEFAULT * (1.0 - math.exp(-t / tau))
        got = driver_step_closed_form(t, tau_s=tau)
        check("B 闭式 == V_dd(1−e^{−t/τ})（t=%.1e, τ=%.1e）" % (t, tau),
              abs(got - want) < 1e-15, "%.17g vs %.17g" % (got, want))
    check("B t=0 ⇒ v=0（零初值）", driver_step_closed_form(0.0) == 0.0)
    check("B t≫τ ⇒ v→V_dd（饱和）",
          abs(driver_step_closed_form(60.0 * TAU_DRIVER_S_DEFAULT) - V_DD_DEFAULT) < 1e-15)

    # ------------------------------------------------- C 候选与 golden 一致
    print("--- C 候选（RK4）与 golden（闭式）一致 ---")
    g = driver_step_closed_form(T_EVAL)
    resid = {}
    for n in NS_SCAN:
        resid[n] = abs(g - driver_step_rk4(T_EVAL, n_steps=n))
    check("C1 默认档残差 < tol(1e-7)", resid[256] < 1e-7, "|Δ|=%.3e" % resid[256])
    check("C2 🔴 默认档残差 > 1e-12（**非恒等、非浮点地板** ⇒ 避开 d_criterion ③ 红灯）",
          resid[256] > 1e-12, "|Δ|=%.3e" % resid[256])
    check("C3 候选 ≠ golden（方法不同源：解析求解 vs 数值积分）",
          resid[256] != 0.0)

    # ------------------------------------------------------------ D 判据 D
    print("--- D 判据 D（残差随 N 严格单调 + 实测收敛阶）---")
    seq = [resid[n] for n in NS_SCAN]
    check("D1 残差随 N **严格单调下降**",
          all(a > b for a, b in zip(seq, seq[1:])), str(["%.3e" % x for x in seq]))
    r1 = resid[16] / resid[64]      # 期望 ≈ 4⁴ = 256
    r2 = resid[64] / resid[256]     # 期望 ≈ 256
    check("D2 实测比值 ≈ 4⁴=256（O(h⁴)）：r1 ∈ [200, 400]", 200.0 < r1 < 400.0,
          "r1=%.1f" % r1)
    check("D3 实测比值 ≈ 4⁴=256（O(h⁴)）：r2 ∈ [200, 400]", 200.0 < r2 < 400.0,
          "r2=%.1f" % r2)
    check("D4 粗端残差浮出双精度地板（> 1e-13）", resid[16] > 1e-13,
          "%.3e" % resid[16])

    # -------------------------------------------------------- E 电压 → 相位
    print("--- E 电压 → 相位 ---")
    check("E1 Vπ = VπL / (arm/1000)（独立重算）",
          abs(vpi_from_vpi_l(7.5, 1000.0) - 7.5) < 1e-15,
          "%.17g" % vpi_from_vpi_l(7.5, 1000.0))
    check("E2 VπL 口径与 mesh_pnr 默认同源（7.5 V·mm）", VPI_L_V_MM_DEFAULT == 7.5)
    check("E3 φ(v) = π·v/Vπ（独立重算）",
          abs(mzi_phase_from_voltage(V_DD_DEFAULT) - math.pi * 2.0 / 7.5) < 1e-15,
          "%.17g" % mzi_phase_from_voltage(V_DD_DEFAULT))
    check("E4 φ 随 v 严格单调增",
          mzi_phase_from_voltage(0.5) < mzi_phase_from_voltage(1.5))

    # ------------------------------------------------------------ F 相位量化
    print("--- F 相位量化（DAC）---")
    want6 = abs(math.pi * (V_DD_DEFAULT / 64.0) / vpi_from_vpi_l())
    check("F1 步进 = π·(V_dd/2^bits)/Vπ（独立重算）",
          abs(phase_resolution_rad(6) - want6) < 1e-18, "%.17g" % phase_resolution_rad(6))
    check("F2 位深↑ ⇒ 步进严格减",
          phase_resolution_rad(6) > phase_resolution_rad(8) > phase_resolution_rad(10))

    # ---------------------------------------------------------------- G TIA
    print("--- G TIA（单极点）---")
    check("G1 f=0 ⇒ Z = R_f", abs(tia_transimpedance_ohm(0.0) - R_F_OHM_DEFAULT) < 1e-9,
          "%.6f" % tia_transimpedance_ohm(0.0).real)
    f3 = tia_bandwidth_hz()
    z3 = abs(tia_transimpedance_ohm(f3))
    check("G2 f=f_3dB ⇒ |Z| = R_f/√2",
          abs(z3 - R_F_OHM_DEFAULT / math.sqrt(2.0)) < 1e-6 * R_F_OHM_DEFAULT,
          "%.6f vs %.6f" % (z3, R_F_OHM_DEFAULT / math.sqrt(2.0)))
    check("G3 带宽闭式 = 1/(2π R_f C_f)",
          abs(f3 - 1.0 / (2.0 * math.pi * R_F_OHM_DEFAULT * C_F_F_DEFAULT)) < 1e-6)
    check("G4 |Z| 随 f 单调减（低通）",
          abs(tia_transimpedance_ohm(1e9)) > abs(tia_transimpedance_ohm(1e11)))

    # ------------------------------------------------- H 零能效/功耗守卫
    print("--- H 零能效/功耗守卫 ---")
    # 🔴 守卫是**单一真值来源**（复用 `optical_pareto.assert_no_energy_metrics`，见模块注释），
    #    故它抛的是 `OpticalParetoError` —— 这是**有意设计**（避免 U10 血案：同一准入条件两处各写一份
    #    ⇒ 突变探针抓不住）。此处按**真实异常类型**断言，不放宽判据。
    from lda_l2.optical_pareto import OpticalParetoError  # noqa: E402
    check("H1 键 pj_per_bit ⇒ 必 raise",
          _raises(lambda: assert_no_energy_metrics({"pj_per_bit": 3.0}), OpticalParetoError))
    check("H2 键 power_w ⇒ 必 raise",
          _raises(lambda: assert_no_energy_metrics({"driver": {"power_w": 0.1}}),
                  OpticalParetoError))
    check("H3 键 TOPS/W ⇒ 必 raise",
          _raises(lambda: assert_no_energy_metrics({"x": [{"TOPS/W": 1}]}), OpticalParetoError))
    check("H4 空载荷 ⇒ 必过", not _raises(lambda: assert_no_energy_metrics({})))
    check("H5 纯散文值含 pJ/bit ⇒ 必过（只扫键不扫值）",
          not _raises(lambda: assert_no_energy_metrics({"note": "不输出 pJ/bit（电域主导）"})))
    check("H6 合法键载荷 ⇒ 必过",
          not _raises(lambda: assert_no_energy_metrics(
              {"vpi_v": 7.5, "phase_full_swing_rad": 0.83, "tia_bandwidth_hz": 4e9})))
    check("H7 🔴 `eic_budget` 全表零能效/功耗键名（机器可查）",
          not _raises(lambda: assert_no_energy_metrics(eic_budget(64))))

    # -------------------------------------------------------------- I 输入域
    print("--- I 输入域 ---")
    check("I1 τ<=0 ⇒ 必 raise", _raises(lambda: driver_step_closed_form(1e-11, tau_s=0.0)))
    check("I2 t<0 ⇒ 必 raise", _raises(lambda: driver_step_rk4(-1.0)))
    check("I3 n_steps<1 ⇒ 必 raise", _raises(lambda: driver_step_rk4(1e-11, n_steps=0)))
    check("I4 dac_bits<1 ⇒ 必 raise", _raises(lambda: phase_resolution_rad(0)))
    check("I5 n_mzi<1 ⇒ 必 raise", _raises(lambda: eic_budget(0)))
    check("I6 rise_frac 越界 ⇒ 必 raise", _raises(lambda: eic_budget(8, rise_frac=1.5)))
    check("I7 边界合法 ⇒ 必过",
          not _raises(lambda: driver_step_rk4(1e-11, n_steps=1)))

    # ------------------------------------------------------------ J 结论钉死
    print("--- J 结论钉死 ---")
    b = eic_budget(64)
    t_cf = -TAU_DRIVER_S_DEFAULT * math.log(1.0 - 0.9)
    check("J1 上升时延（闭式）≡ −τ·ln(1−0.9)（独立重算）",
          abs(b["rise_time_closed_form_s"] - t_cf) < 1e-24,
          "%.6e vs %.6e" % (b["rise_time_closed_form_s"], t_cf))
    check("J2 数值求得的上升时延与闭式一致（相对差 < 1e-4）",
          abs(b["rise_time_rk4_s"] - t_cf) / t_cf < 1e-4,
          "rel=%.3e" % (abs(b["rise_time_rk4_s"] - t_cf) / t_cf))
    check("J3 满摆幅相位 ≡ π·V_dd/Vπ（独立重算）",
          abs(b["phase_full_swing_rad"]
              - math.pi * V_DD_DEFAULT / vpi_from_vpi_l()) < 1e-15)
    check("J4 预算表含披露键清单（防删披露）",
          len(b["disclosure_keys"]) == 7 and b["dac_bits"] == DAC_BITS_DEFAULT)

    # --------------------------------------------------- K 判据有效性自证
    print("--- K 判据有效性自证 ---")
    def fake_rk4(t_s, tau_s=TAU_DRIVER_S_DEFAULT, v_dd=V_DD_DEFAULT, n_steps=256):
        return driver_step_closed_form(t_s, tau_s, v_dd)      # 恒等伪实现
    seq_fake = [abs(driver_step_closed_form(T_EVAL)
                    - fake_rk4(T_EVAL, n_steps=n)) for n in NS_SCAN]
    check("K1 注入恒等伪 RK4 ⇒ 残差恒 0 ⇒ **C2（>1e-12）与 D1（严格单调）必红**",
          (not all(s > 1e-12 for s in seq_fake))
          and (not all(a > b for a, b in zip(seq_fake, seq_fake[1:]))),
          str(["%.3e" % s for s in seq_fake]))

    print("=" * 74)
    print("P6 · T6.4 EIC 行为级：%d PASS / %d FAIL" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
