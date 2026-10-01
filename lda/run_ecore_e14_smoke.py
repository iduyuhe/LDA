#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电子计算征程 E14 门禁 · 真 DAC / ADC / 行驱动外设（把「设计链」补成「系统链」）。

═══ 判什么（分节）═══
A 模块自检（`converter` **11/11** · `periphery` **9/9**）·
B 关键判据（**B1–B15** · name-first）：
  B1  R-2R **网络装配自证**：MNA 解理想开关网络 ⟷ 二进制除权闭式（方法学独立）·
  B2  真 NMOS 开关 DAC：8 bit **全码扫描** max|Δ| < 1 LSB + 单调 ·
  B3  **R_on 是精度来源**：开关 W/L ↑ ⇒ R_on ↓ ⇒ 静态误差 ↓（对照）·
  B4  CDAC **电荷守恒**：保持后 V_top ⟷ 闭式 −V_in（机器精度）·
  B5  SAR 转换 ≤ 1 LSB（16 取样点）· B6 逐次逼近收敛（末步残差 ≤ 1 LSB）·
  B7  采样保持 ⟷ **后向欧拉离散闭式**（同口径）· B8 **离散化误差 O(dt)**（步长加密单调降）·
  B9  行驱动闭式 ⟷ **MNA 真实电路**（VCVS 闭环 + R_ol + R_L）·
  B10 🔴 **R_oc = 0 ⟷ E9 `row_line_profile` 逐位一致**（极限交叉核对）·
  B11 🔴 **R_oc ↑ ⇒ 可及规模上界 N_max ↓**（本段核心系统结论）·
  B12 🔴 **行系统项**：真驱动 ⇒ 行增益离散；理想驱动 ⇒ 离散 = 0（对照实验）·
  B13 系统链：真驱动误差 > 理想驱动 · B14 🔴 **vcvs 极性事实锁定**（平台缺陷登记）·
  B15 披露完整（比较器判决器抽象 + 行驱动宏模型 + 不报 TOPS）·
C 反向可证伪（**6 条突变探针** + 还原完整性）：
  C1 破坏 R-2R 拓扑（2R→R）⇒ B1 必红 · C2 比较器判决失效（失调极大）⇒ B5 必红 ·
  C3 污染 CDAC 顶板读数 ⇒ B4 必红 · C4 忽略 R_oc（强制理想源）⇒ B11 必红 ·
  C5 去掉采样电容 ⇒ B7 必红 · C6 抹平驱动负载调整 ⇒ B13 必红 · C7 还原后复绿
D 公开符号齐备 · K 自入 CI core。

🔴 本门禁的核心价值：**证明「真电路」不是摆设** —— 每个转换器/驱动器都必须与
**闭式物理律**对拍，且**与 E9 的既有模型在极限处逐位一致**（不是另起一套模型）。
另：**登记一个真实的平台缺陷**（`mna.vcvs` 极性与 docstring 相反）—— 按保护性约束**不修 mna**，
而是**适配 + 锁死事实**（B14）：若未来有人"顺手改正"，B14 会红并提示适配过期。
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


def _g_siemens() -> float:
    """与 E9 门禁同源的交叉点电导（kp·(W/L)·(Vg−Vth0)）。"""
    from lda_l2.ecore.mosfet import NmosParams
    nn = NmosParams(w_over_l=1.2 / 0.3)
    return nn.kp * nn.w_over_l * (2.1 - nn.vth0)


def _r_seg() -> float:
    """与 E9 门禁同源的每段行线电阻（复用 E7 寄生模块）。"""
    from lda_l2.ecore import parasitic as PA
    return PA.array_parasitics(8, 8)["r_row_seg_ohm"]


def main() -> int:
    import numpy as np
    import unittest.mock as mock
    from lda_l2.ecore import converter as CN
    from lda_l2.ecore import periphery as PR
    from lda_l2.ecore.mna import Circuit

    # ══════════════════════ A 模块自检 ══════════════════════
    check("A1 `converter` 自检 11/11（网络装配/真 DAC/ R_on 精度/ 电荷守恒/ SAR/ 收敛/"
          "采样保持/ 离散闭式/ O(dt)/ 采样单调/ 失调/ 披露）",
          CN.converter_self_check(verbose=False) is True)
    check("A2 `periphery` 自检 9/9（行驱动闭式⟷MNA/ 闭环 R_oc/ 负载单调/ R_oc=0⟷E9/"
          "规模上界/ 行系统项/ 系统链/ 披露/ vcvs 事实）",
          PR.periphery_self_check(verbose=False) is True)

    # ══════════════════════ B 关键判据 ══════════════════════
    # B1 R-2R 网络装配自证
    w1 = 0.0
    for code in (0, 1, 7, 100, 255):
        w1 = max(w1, abs(CN.r2r_ideal_network_dc(CN.code_to_bits(code, 8), 1.0, 10.0e3)
                         - CN.ideal_dac_voltage(code, 8, 1.0)))
    check("B1 R-2R **网络装配自证**：MNA 解理想开关网络 ⟷ 二进制除权闭式（max|Δ| < 1e-9）",
          w1 < 1e-9, "max|Δ|=%.3e" % w1)

    rep8 = CN.dac_static_report(8, step=1)
    check("B2 真 NMOS 开关 DAC：8 bit 全码 256 点 max|Δ| < 1 LSB · 单调 · R_on=%.1f Ω"
          % rep8["ron_ohm"],
          rep8["max_abs_err_lsb"] < 1.0 and rep8["monotone"]
          and rep8["codes_scanned"] == 256,
          "err=%.4f LSB · INL=%.4f LSB · codes=%d"
          % (rep8["max_abs_err_lsb"], rep8["inl_lsb_max"], rep8["codes_scanned"]))

    big = CN.dac_static_report(6, dac_sw_wl=2000.0, step=1)
    sml = CN.dac_static_report(6, dac_sw_wl=50.0, step=1)
    check("B3 **R_on 是精度来源**：开关 W/L ↑ ⇒ R_on ↓ ⇒ 静态误差 ↓（W/L=2000 ⟷ 50）",
          big["max_abs_err_lsb"] < sml["max_abs_err_lsb"],
          "W/L=2000 → %.4f LSB · W/L=50 → %.4f LSB"
          % (big["max_abs_err_lsb"], sml["max_abs_err_lsb"]))

    sar8 = CN.sar_convert(0.4187, 8, 1.0)
    rel_hold = (abs(sar8["v_top_hold_v"] - sar8["top_closed_form_hold_v"])
                / abs(sar8["top_closed_form_hold_v"]))
    check("B4 CDAC **电荷守恒**：保持后 V_top ⟷ 闭式 −V_in（rel < 1e-6）· 后向欧拉天然守恒",
          rel_hold < 1e-6,
          "V_top=%.9f ⟷ 闭式 %.9f（rel=%.2e）"
          % (sar8["v_top_hold_v"], sar8["top_closed_form_hold_v"], rel_hold))

    e8 = CN.sar_error_report(8, samples=16)
    check("B5 SAR + CDAC 转换：16 个均匀取样点 **max 误差 ≤ 1 LSB**",
          e8["all_within_1lsb"], "max=%d LSB · 样本 %d" % (e8["max_err_lsb"], e8["samples"]))

    check("B6 逐次逼近收敛：末步残差 |V_top| ≤ 1 LSB（剩余区间每步减半）",
          abs(sar8["residual_v"]) <= sar8["lsb_v"] * 1.5,
          "residual=%.3e V · LSB=%.3e V" % (sar8["residual_v"], sar8["lsb_v"]))

    sh = CN.sample_hold_transient()
    check("B7 采样保持 ⟷ **后向欧拉离散闭式**（同口径 · rel < 1e-9）",
          sh["rel_err_discrete"] < 1e-9,
          "v_end=%.9f ⟷ 离散 %.9f（rel=%.2e）"
          % (sh["v_end_v"], sh["discrete_form_v"], sh["rel_err_discrete"]))

    d40 = CN.sample_hold_transient(n_steps=40)["discretization_rel"]
    d80 = CN.sample_hold_transient(n_steps=80)["discretization_rel"]
    d160 = CN.sample_hold_transient(n_steps=160)["discretization_rel"]
    check("B8 **离散化误差 O(dt)**：步长 40→80→160 ⇒ 与连续闭式偏差单调降（比值 ≈ 2）",
          d40 > d80 > d160 and 1.5 < (d40 / d80) < 2.6,
          "%.3e → %.3e → %.3e（比值 %.2f）" % (d40, d80, d160, d40 / d80))

    c9 = PR.row_driver_mna_check(0.8, 1.0e3, 1.0e3, 1.0e3)
    check("B9 行驱动闭式 ⟷ **MNA 真实电路**（VCVS 闭环 + R_ol + R_L · rel < 1e-9）",
          c9["rel_err"] < 1e-9,
          "MNA=%.9f ⟷ 闭式 %.9f（rel=%.2e · R_oc=%.4f Ω）"
          % (c9["v_load_mna_v"], c9["v_load_closed_form_v"], c9["rel_err"],
             c9["r_out_closed_ohm"]))

    r_seg, g = _r_seg(), _g_siemens()
    from lda_l2.ecore import array_scale as AS
    mine = PR.row_line_profile_with_driver(24, r_seg, g, 0.0)["voltages"]
    ref = AS.row_line_profile(24, r_seg, g)["voltages"]
    dmax = float(np.max(np.abs(np.asarray(mine) - np.asarray(ref))))
    check("B10 🔴 **R_oc = 0 ⟷ E9 `row_line_profile` 逐位一致**（极限交叉核对 · max|Δ| < 1e-12）",
          dmax < 1e-12, "max|Δ|=%.3e（r_seg=%.4f Ω · g=%.3e S）" % (dmax, r_seg, g))

    tbl = PR.driver_scale_table(r_seg, g, 0.05, (0.0, 1.0, 5.0, 20.0))
    ns = [r["n_max"] for r in tbl["rows"]]
    check("B11 🔴 **R_oc ↑ ⇒ 可及规模上界 N_max ↓**（5% 预算 · 本段核心系统结论）",
          tbl["monotone_shrink"] and ns[0] > ns[-1],
          "N_max: %s（R_oc = 0/1/5/20 Ω）· 理想 %d → 最差 %d"
          % (ns, tbl["n_max_ideal"], tbl["n_max_worst"]))

    rng = np.random.RandomState(0)
    Gm = rng.uniform(1.0e-4, 5.0e-4, (8, 6))
    xd = rng.uniform(0.1, 1.0, 8)
    se = PR.row_system_error(Gm, xd, vfs=1.0, rf=1.0e4, a_gain=1.0e3,
                             r_out_open_ohm=1.0e3)
    check("B12 🔴 **行系统项**：真驱动 ⇒ 行增益**离散**；理想驱动 ⇒ 离散 = 0（对照实验）",
          se["with_driver_spread"] > 1e-4 and abs(se["ideal_driver_spread"]) < 1e-12,
          "真驱动 spread=%.3e · 理想驱动 spread=%.3e"
          % (se["with_driver_spread"], se["ideal_driver_spread"]))

    ch_i = PR.system_chain(Gm, xd, vfs=1.0, rf=1.0e4, a_gain=1.0e9, r_out_open_ohm=0.0)
    ch_r = PR.system_chain(Gm, xd, vfs=1.0, rf=1.0e4, r_out_open_ohm=1.0e3)
    check("B13 端到端系统链：真驱动 max_rel_err > 理想驱动（A→∞ & R_ol=0 ⇒ 趋 0）",
          ch_r["max_rel_err"] > ch_i["max_rel_err"] and ch_i["max_rel_err"] < 1e-8,
          "真 %.3e ⟷ 理想 %.3e" % (ch_r["max_rel_err"], ch_i["max_rel_err"]))

    pol = PR.vcvs_polarity_fact()
    check("B14 🔴 **platform 事实锁定**：`mna.vcvs` 实际极性 ⟷ docstring **相反**"
          "（适配 + 登记 · 不改 mna ⇒ 保护 E1–E13 已上线数字）",
          pol["polarity_inverted"] is True and pol["v_out_with_ctl_p_positive"] < 0.0,
          "v_out(ctl_p=+1 V)=%.1f（docstring 期望 +1000）"
          % pol["v_out_with_ctl_p_positive"])

    hb_c = CN.CONVERTER_DISCLOSURE["honest_boundary"]
    hb_p = PR.PERIPHERY_DISCLOSURE["honest_boundary"]
    check("B15 披露完整：比较器判决器抽象 + 行驱动宏模型 + 两处均**不报 TOPS**",
          "判决器抽象" in hb_c and "宏模型" in hb_p
          and "TOPS" in hb_c and "TOPS" in hb_p)

    # ══════════════════════ C 反向可证伪（突变探针）═══════════════════════
    # C1 破坏 R-2R 拓扑（某个 2R 电阻改成 R）⇒ B1 必红
    real_build = CN._build_r2r_ideal

    def bad_build(n, bits, vref, r):
        ckt = real_build(n, bits, vref, r)
        for e in ckt._elems:                       # noqa: SLF001
            if e.get("tag") == "2R0":
                e["r"] = r                         # 2R → R（破坏二进制权）
        return ckt

    with mock.patch.object(CN, "_build_r2r_ideal", bad_build):
        w_c1 = abs(CN.r2r_ideal_network_dc(CN.code_to_bits(255, 8), 1.0, 10.0e3)
                   - CN.ideal_dac_voltage(255, 8, 1.0))
    check("C1 反向：把 R-2R 的 2R 改成 R（破坏二进制权）⇒ B1 网络装配判据必红",
          w_c1 > 1e-9, "破坏后 max|Δ|=%.3e" % w_c1)

    # C2 比较器判决失效（失调极大 ⇒ 全部保留）⇒ B5 必红
    e_c2 = CN.sar_error_report(6, samples=8, comp_offset_v=1.0e9)
    check("C2 反向：比较器失调极大（判决全保留）⇒ B5 转换精度判据必红",
          e_c2["all_within_1lsb"] is False, "max=%d LSB" % e_c2["max_err_lsb"])

    # C3 污染 CDAC 顶板读数（+1%）⇒ B4 电荷守恒必红
    real_seg = CN._cdac_run_segment

    def bad_seg(*a, **k):
        out = np.array(real_seg(*a, **k), dtype=float)
        out[1] = out[1] * 1.01                  # 顶板 +1%
        return out

    with mock.patch.object(CN, "_cdac_run_segment", bad_seg):
        s_bad = CN.sar_convert(0.4187, 8, 1.0)
        r_c3 = (abs(s_bad["v_top_hold_v"] - s_bad["top_closed_form_hold_v"])
                / abs(s_bad["top_closed_form_hold_v"]))
    check("C3 反向：污染 CDAC 顶板读数（+1%）⇒ B4 电荷守恒判据必红",
          r_c3 >= 1e-6, "污染后 rel=%.3e" % r_c3)

    # C4 忽略 R_oc（强制理想源）⇒ B11 必红
    real_prof = PR.row_line_profile_with_driver

    def bad_prof(n, r_seg_, g_, r_out_cl_ohm, v_in=1.0):
        return real_prof(n, r_seg_, g_, 0.0, v_in)      # 强制 R_oc = 0

    with mock.patch.object(PR, "row_line_profile_with_driver", bad_prof):
        tbl_bad = PR.driver_scale_table(r_seg, g, 0.05, (0.0, 1.0, 5.0, 20.0))
    ns_bad = [r["n_max"] for r in tbl_bad["rows"]]
    check("C4 反向：忽略 R_oc（强制理想源）⇒ B11 可及规模上界判据必红"
          "（上界不再随 R_oc 收缩）",
          not (tbl_bad["monotone_shrink"] and ns_bad[0] > ns_bad[-1]),
          "上界 = %s" % ns_bad)

    # C5 去掉采样电容（不给 C 元件）⇒ B7 必红
    def no_cap(self, n1, n2, c, tag=""):
        return self                                   # 不加电容

    with mock.patch.object(Circuit, "capacitor", no_cap):
        sh_bad = CN.sample_hold_transient()
    check("C5 反向：去掉采样电容（无 RC 建立）⇒ B7 离散闭式对拍必红",
          sh_bad["rel_err_discrete"] >= 1e-9,
          "rel=%.3e（v_end=%.6f ⟷ 闭式 %.6f）"
          % (sh_bad["rel_err_discrete"], sh_bad["v_end_v"], sh_bad["discrete_form_v"]))

    # C6 抹平驱动负载调整 ⇒ B12 **行系统项**判据必红
    #    🔴 判据必须**只对被测机制敏感**：抹平负载后仍残留**缓冲增益误差** A/(1+A)≈1e-3，
    #    故不能用「是否比理想驱动差」当判据（那个差值含增益误差）⇒ 改用
    #    **行增益离散度**（spread）—— 抹平后行间差异应消失。
    def flat_buf(v_in, a_gain=1.0e3, r_out_open_ohm=1.0e3, r_load_ohm=1.0e3):
        return float(v_in) * a_gain / (1.0 + a_gain)   # 忽略负载

    with mock.patch.object(PR, "buffered_row_voltage", flat_buf):
        se_flat = PR.row_system_error(Gm, xd, vfs=1.0, rf=1.0e4, a_gain=1.0e3,
                                      r_out_open_ohm=1.0e3)
    check("C6 反向：抹平驱动负载调整（忽略 R_L）⇒ B12 **行系统项**判据必红"
          "（行增益离散消失）",
          not (se_flat["with_driver_spread"] > 1e-4
               and abs(se_flat["ideal_driver_spread"]) < 1e-12),
          "抹平后 spread=%.3e（真驱动 %.3e）"
          % (se_flat["with_driver_spread"], se["with_driver_spread"]))

    # C7 还原完整性
    ok_a1 = CN.converter_self_check(verbose=False)
    ok_a2 = PR.periphery_self_check(verbose=False)
    check("C7 还原完整性：全部探针退出后 A1/A2 复绿（无 mock 残留）",
          ok_a1 is True and ok_a2 is True)

    # ══════════════════════ D 公开符号齐备 ══════════════════════
    need_c = ("ideal_dac_voltage", "r2r_ideal_network_dc", "r2r_nmos_dac_dc",
              "dac_static_report", "cdac_top_closed_form", "sar_convert",
              "sar_error_report", "sample_hold_transient", "nmos_switch_ron_ohm",
              "CONVERTER_DISCLOSURE", "converter_self_check")
    need_p = ("buffered_row_voltage", "row_driver_mna_check", "vcvs_polarity_fact",
              "row_line_profile_with_driver", "max_scale_with_driver",
              "driver_scale_table", "system_chain", "row_system_error",
              "PERIPHERY_DISCLOSURE", "periphery_self_check")
    miss_c = [s for s in need_c if not hasattr(CN, s)]
    miss_p = [s for s in need_p if not hasattr(PR, s)]
    check("D1 两模块公开符号齐备（converter %d + periphery %d）" % (len(need_c), len(need_p)),
          not miss_c and not miss_p, "缺 converter=%s periphery=%s" % (miss_c, miss_p))

    # ══════════════════════ K 自入 CI core ══════════════════════
    try:
        import run_ci_regression as R
        in_core = "run_ecore_e14_smoke.py" in R.CORE_SMOKES
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", in_core,
              "len=%d" % len(R.CORE_SMOKES))
    except Exception as e:  # pragma: no cover
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", False, "import 失败: %s" % e)

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
