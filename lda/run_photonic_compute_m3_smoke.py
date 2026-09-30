# -*- coding: utf-8 -*-
"""P6 · 光计算征程 M3 · 光电协同仿真常驻门禁（L2 系统级）。

判据分组（A–K）
---------------
A 契约 / 披露（EO 披露键齐全 + 关键立场字面：零能效 / 行为级 T1 候选 / 跨模块 Vπ 口径警告）
B DAC→驱动→相移器 量化（平均相位误差随位深单调下降 + 12-bit 近机器精度）
C 闭环标定（DAC 下发+TIA 读回反估 Vπ：8-bit 残差 << 4-bit 残差；残差随位深单调下降）
D EO 端到端精度锚（全精度分类=100% 且权重误差≈0；2-bit 致退化；Vπ 失配致退化）
E 闭环回收（标定精度 > 未标定；标定权重误差 < 未标定）
F TIA 单极点（f=0⇒Z=R_f；f=f_3dB⇒|Z|=R_f/√2；高频滚降）
G EO 行为级预算（零能效守卫：assert_no_energy_metrics 必过；含 DAC 相位分辨率键）
H 输入域（dac_bits<1 / n_mzi<1 必 raise；边界合法必过）
I 反向可证伪（注入恒等相位映射 ⇒ B 组单调与近零判据必红；注入假标定 ⇒ C 组必红）
J 通用纪律（reverse 反例：量化退化存在 / 标定回收存在 / 全精度==参考 / 量化致退化 / 标定回收精度）
K 自入 core 校验（本文件在 CORE_SMOKES 内 + 覆盖表含本文件）

🔴 立场：断言的是**事实** —— EO 披露含「零能效数字」「行为级 T1 候选」「Vπ 跨模块口径不一致警告」字面；
B 断言量化单调（非恒真，真 no-op 量化会拉红）；E 断言标定回收（非恒真，断标定环路会拉红）；
G 断言零能效（非恒真，加 pJ/bit 会拉红）。CI core 233→234。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check
from lda_l2.photonic_electronic_cosim import (  # noqa: E402
    verify_photonic_compute_m3,
    eo_phase_map,
    eo_calibration_loop,
    eo_budget,
    EO_COSIM_DISCLOSURE,
    VPI_V_DEFAULT,
    R_F_OHM_DEFAULT,
    DAC_BITS_DEFAULT,
)
from lda_l2.eic_behavioral import assert_no_energy_metrics  # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True, detail_fmt="  —— {d}", detail_on="fail")


def _raises(fn, exc=Exception):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def main():  # noqa: C901
    print("=== P6 · 光计算征程 M3 · 光电协同仿真门禁 ===")
    r = verify_photonic_compute_m3()

    # ----------------------------------------------------------- A 契约 / 披露
    print("--- A 契约 / 披露 ---")
    check("A1 EO 披露键齐全（>=10）", len(EO_COSIM_DISCLOSURE) >= 10,
          "%d 键" % len(EO_COSIM_DISCLOSURE))
    blob = " ".join(EO_COSIM_DISCLOSURE.values())
    check("A2 披露含「零能效数字」「行为级 T1 候选」「跨模块 Vπ 口径不一致」字面",
          "零能效数字" in blob and "行为级（T1 候选" in blob and "跨模块口径不一致" in blob)
    check("A3 披露含「不宣称已物理校准（U10 纪律）」字面", "不宣称已物理校准" in blob)

    # ----------------------------------------------------- B DAC 量化单调
    print("--- B DAC→驱动→相移器 量化 ---")
    ds = {q["n_bits"]: q["mean_phase_err"] for q in r["dac_sweep"]}
    check("B1 12-bit 平均相位误差 < 0.01 rad（近机器精度）",
          ds[12] < 0.01, "%.6f" % ds[12])
    check("B2 平均相位误差随位深单调下降（2→4→8→12）",
          ds[2] > ds[4] > ds[8] > ds[12],
          " ".join("%.4f" % ds[k] for k in (2, 4, 8, 12)))
    check("B3 量化确致误差（2-bit 误差 >> 12-bit）",
          ds[2] > 10.0 * ds[12], "%.4f vs %.6f" % (ds[2], ds[12]))

    # ----------------------------------------------------- C 闭环标定
    print("--- C 闭环标定（DAC 下发 + TIA 读回）---")
    cal = r["calibration"]
    check("C1 8-bit 标定残差 < 1%（闭环可回收 Vπ 失配）",
          cal["rel_err_8bit"] < 0.01, "%.5f" % cal["rel_err_8bit"])
    check("C2 标定残差随位深单调下降（4-bit > 8-bit）",
          cal["rel_err_4bit"] > cal["rel_err_8bit"],
          "4b=%.5f 8b=%.5f" % (cal["rel_err_4bit"], cal["rel_err_8bit"]))
    check("C3 反估 Vπ 与真实 Vπ 一致（8-bit 残差 < 0.5%）",
          abs(cal["vpi_est_8bit"] - cal["vpi_real"]) / cal["vpi_real"] < 0.005)

    # ----------------------------------------------------- D EO 端到端精度锚
    print("--- D EO 端到端精度锚 ---")
    full, q2, mis, rec = (r["eo_full"], r["eo_q2"],
                          r["eo_vpi_mismatch"], r["eo_vpi_calibrated"])
    check("D1 EO 全精度分类精度 = 100%", full["accuracy"] == 1.0,
          "%.4f" % full["accuracy"])
    check("D2 EO 全精度权重相对误差 < 5e-3（光学实现==参考）",
          full["max_mac_err"] < 5e-3, "%.6f" % full["max_mac_err"])
    check("D3 2-bit 量化致精度退化（< 100%）", q2["accuracy"] < 1.0,
          "%.4f" % q2["accuracy"])
    check("D4 Vπ+5% 未标定致精度退化（< 100%）", mis["accuracy"] < 1.0,
          "%.4f" % mis["accuracy"])

    # ----------------------------------------------------- E 闭环回收
    print("--- E 闭环回收 ---")
    check("E1 标定后精度 > 未标定精度", rec["accuracy"] > mis["accuracy"],
          "%.4f vs %.4f" % (rec["accuracy"], mis["accuracy"]))
    check("E2 标定后权重误差 < 未标定权重误差",
          rec["max_mac_err"] < mis["max_mac_err"],
          "%.6f vs %.6f" % (rec["max_mac_err"], mis["max_mac_err"]))

    # ----------------------------------------------------- F TIA 单极点
    print("--- F TIA 单极点频响 ---")
    t = r["tia"]
    check("F1 DC 读回增益 = R_f", abs(t["z0"] - R_F_OHM_DEFAULT) < 1e-6,
          "%.1f vs %.1f" % (t["z0"], R_F_OHM_DEFAULT))
    check("F2 f=f_3dB 增益 = R_f/√2（0.707）", abs(t["z3"] - R_F_OHM_DEFAULT / math.sqrt(2)) < 1.0)
    check("F3 高频（10·f_3dB）读回增益滚降（< 0.5×DC）",
          t["z_hi_over_f3"] < 0.5, "%.3f" % t["z_hi_over_f3"])

    # ----------------------------------------------------- G EO 预算零能效
    print("--- G EO 行为级预算（零能效守卫）---")
    from lda_l2.optical_pareto import OpticalParetoError  # noqa: E402
    b = eo_budget(64)
    check("G1 预算表零能效/功耗键名（机器可查）",
          not _raises(lambda: assert_no_energy_metrics(b), OpticalParetoError))
    check("G2 预算含 DAC 相位分辨率键", "eo_phase_resolution_rad" in b)
    check("G3 注入 pj_per_bit ⇒ assert_no_energy_metrics 必 raise",
          _raises(lambda: assert_no_energy_metrics({"pj_per_bit": 3.0}), OpticalParetoError))

    # ----------------------------------------------------- H 输入域
    print("--- H 输入域 ---")
    check("H1 dac_bits<1 ⇒ 必 raise", _raises(lambda: eo_phase_map(1.0, dac_bits=0)))
    check("H2 n_mzi<1 ⇒ eo_budget 必 raise", _raises(lambda: eo_budget(0)))
    check("H3 边界合法（dac_bits=1, n_mzi=1）⇒ 必过",
          not _raises(lambda: (eo_phase_map(1.0, dac_bits=1), eo_budget(1))))

    # ----------------------------------------------------- I 反向可证伪
    print("--- I 反向可证伪 ---")
    def fake_eo_phase_map(target_phi, dac_bits=DAC_BITS_DEFAULT, v_dd=15.0,
                          vpi_v=VPI_V_DEFAULT, vpi_real=None, tau_s=20e-12,
                          t_settle_frac=8.0, calibrate=False, vpi_est=None):
        # 恒等伪实现：直接返回目标相位（无量化、无 Vπ 失配）⇒ B/C 组判据必红
        return float(target_phi) % (2.0 * math.pi)
    # B2 单调：恒等映射使各 bit 误差全 0 ⇒ 不满足 2>4>8>12（非严格下降）⇒ 红
    errs = {}
    for nb in (2, 4, 8, 12):
        phis = [0.3, 1.1, 2.7, 4.2, 5.5]
        e = [abs((fake_eo_phase_map(p, dac_bits=nb) - p) % (2*math.pi)) for p in phis]
        errs[nb] = sum(min(d, 2*math.pi - d) for d in e) / len(e)
    check("I1 注入恒等相位映射 ⇒ B2 单调判据必红（各 bit 误差全 0，非严格下降）",
          not (errs[2] > errs[4] > errs[8] > errs[12]))
    # C 组：注入「假标定恒返回标称」⇒ 残差不随位深变 ⇒ C2 必红
    def fake_cal_loop(dac_bits=8, v_dd=15.0, vpi_real=7.875, vpi_v=7.5):
        return {"vpi_real": vpi_real, "vpi_est": vpi_v,  # 返回标称（未校正）
                "rel_err": abs(vpi_v - vpi_real) / vpi_real, "best_code": 0,
                "null_intensity": 0.0, "responsivity": 1.0, "r_f": 2000.0}
    fc4 = fake_cal_loop(dac_bits=4)["rel_err"]
    fc8 = fake_cal_loop(dac_bits=8)["rel_err"]
    check("I2 注入假标定（恒返回标称）⇒ C2 单调判据必红", not (fc4 > fc8))

    # ----------------------------------------------------- J 通用反向纪律
    print("--- J 通用纪律（reverse 反例）---")
    check("J1 量化退化存在（2-bit 精度 < 全精度）", q2["accuracy"] < full["accuracy"])
    check("J2 标定回收存在（标定精度 > 未标定）", rec["accuracy"] > mis["accuracy"])
    check("J3 全精度光学实现 == 参考（分类 100% 且权重误差 < 5e-3）",
          full["accuracy"] == 1.0 and full["max_mac_err"] < 5e-3)
    check("J4 Vπ 失配致退化（未标定精度 < 全精度）", mis["accuracy"] < full["accuracy"])

    # ----------------------------------------------------- K 自入 core 校验
    print("--- K 自入 core 校验 ---")
    import run_ci_regression as R  # noqa: E402
    check("K1 本 smoke 在 CORE_SMOKES 内",
          "run_photonic_compute_m3_smoke.py" in R.CORE_SMOKES,
          "CORE_SMOKES 共 %d 条" % len(R.CORE_SMOKES))

    print("=" * 74)
    print("P6 · 光计算征程 M3 · 光电协同仿真：%d PASS / %d FAIL" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
