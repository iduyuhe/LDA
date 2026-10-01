# -*- coding: utf-8 -*-
"""E19 列侧共享的动态代价门禁（D-194 · v0.9.169）。

═══════════════════════════════════════════════════════════════════════════
判什么（分节）
═══════════════════════════════════════════════════════════════════════════
A 模块自检（`col_share_dynamic.col_share_dynamic_self_check` **13 项**）
B 关键事实 name-first（14 条）：电荷注入 pedestal（确定性可校准）+ Pelgrom 随机残差 ·
  孔径抖动（σ_v=π·f·V_ref·σ_t · 越 kT/C/越 LSB 频率）· 多路开关 R_on 同器件 · plain 侵蚀恒定 ·
  🔴 **保吞吐共享 mux 侵蚀 ∝K（K*=160 处 ≈7%）** · 预算项格式+E15 合成律 · 跨模块交叉
  （E18 `cdac_settle_tau` / `thermal_noise_rms_v`）· 保护性约束（E18 数字逐位不变）· 诚实披露
C 反向可证伪：**6 条突变探针**（披露追加「已报 TOPS」/ 残差越 kT/C / 抖动公式坏 /
  多路开关 R_on 错 / keep 侵蚀不 ∝K / plain 侵蚀随 K 变）⇒ 均必红 + **还原重跑**
K 自入 CI core（防静默漏接 · 血案 #28）

═══════════════════════════════════════════════════════════════════════════
🔴 本门禁的核心价值
═══════════════════════════════════════════════════════════════════════════
1. **闭合 E18 G-S 自点名的缺口**：E18 静态面积/吞吐口径的**动态补齐** ——
   电荷注入 / 孔径抖动 / 多路开关建立时间。
2. 🔴 **诚实拒绝造腿**（B2/B3/B4）：在可达共享度内三项动态代价**都不是精度墙** ——
   电荷注入确定性 pedestal 可单点校准消除（真成本=校准负担）· 残差 ≪ kT/C/LSB；
   孔径抖动仅高带宽越 kT/C（~20 MHz）/ 越 LSB（~1.2 GHz）；多路开关建立在 plain 共享下可忽略。
3. 🔴 **唯一新的、非平凡的动态代价**（B7/B8）：保吞吐共享下多路开关建立侵蚀 **∝K**，
   **K*=160 处 ≈7% 每列周期** —— E18 静态模型此前漏计，**反相关于 E18 面积收益**（与抖动同族）。
4. 🔴 **保护性约束**（B12）：**只读消费** E14/E17/E18/E8/E15，**不改**任何既有默认值；
   `keep_throughput` 默认 **False** ⇒ E18 已发布数字（含 `converter_period_s(8)` 逐位）**不变**。
5. 🔴 **诚实**（B10/B11）：参数为**公开量级占位（非 PDK）** · **不做功耗估算**；
   **绝不报 TOPS / TOPS-W / fJ/op**（用**肯定性禁止短语**判定）。
"""
from __future__ import annotations

import math
import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import budget as B              # noqa: E402
from lda_l2.ecore import col_share as C            # noqa: E402
from lda_l2.ecore import col_share_dynamic as D    # noqa: E402
from lda_l2.ecore import converter as CV          # noqa: E402
from lda_l2.ecore import mismatch as MM           # noqa: E402
from lda_l2.ecore import timing as T              # noqa: E402

_results: list = []

# ── 实测锚（本机默认几何 ‖ 默认工艺 · 8 bit / N=64）─────────────────────
AN_T_CONV_8 = 9.213525600058347e-08      # 一次 SAR 转换周期（= E17 sar_stage_time(8) · 逐位）
AN_R_ON = 6.410256410256410             # 多路开关 R_on（= E18 CDAC 开关 W/L=500）


def check(name: str, cond: bool, detail: str = "") -> bool:
    _results.append((name, bool(cond), detail))
    return bool(cond)


# ── 复用的绿色判据（突变探针也调同一份 —— 保证「打的判据」就是「守的判据」）──
def _pedestal_ok() -> bool:
    """B1 · 电荷注入确定性 pedestal ≈ 119 mV（11.9%FS）· 可单点校准 · 残差 ~29 µV。"""
    ped = D.charge_injection_pedestal_v()
    res = D.charge_injection_residual_sigma_v()
    return (0.11 < ped["pedestal_v"] < 0.13 and ped["is_calibratable"] is True
            and 2.7e-5 < res["sigma_pedestal_v"] < 3.1e-5)


def _residual_ok() -> bool:
    """B2 · 电荷注入随机残差 ≪ kT/C（64 µV）与 LSB（3.9 mV）（不是墙）。"""
    res = D.charge_injection_residual_sigma_v()
    return res["below_ktc"] and res["below_lsb"]


def _jitter_ok() -> bool:
    """B3 · 孔径抖动 @ 100 MHz：σ_v ≈ 314 µV（0.0314%FS）< LSB（3906 µV）（条件性）。"""
    jit = D.aperture_jitter_sigma_v()
    return 3.0e-4 < jit["sigma_v"] < 3.3e-4 and jit["below_lsb"] is True


def _jitter_limits_ok() -> bool:
    """B4 · 抖动越界频率：f_ktc ≈ 20.5 MHz < f_lsb ≈ 1243 MHz（先越 kT/C 再越 LSB）。"""
    jl = D.jitter_bandwidth_limits(8)
    return (18.0e6 < jl["f_cross_ktc_hz"] < 23.0e6
            and 1.1e9 < jl["f_cross_lsb_hz"] < 1.4e9
            and 0 < jl["f_cross_ktc_hz"] < jl["f_cross_lsb_hz"])


def _mux_ron_ok() -> bool:
    """B5 · 多路开关 R_on ⟷ E18 CDAC 开关（同一器件 W/L=500 ⇒ 6.41 Ω）· t_mux ≪ T_conv。"""
    tm = D.mux_settling_tau(8)
    return (abs(tm["r_on_ohm"] - T.cdac_settle_tau(8)["r_on_ohm"]) < 1e-15
            and tm["same_device_as_e18"] is True
            and tm["t_settle_s"] < C.converter_period_s(8) / 1000.0)


def _plain_erosion_ok() -> bool:
    """B6 · plain 共享 mux 侵蚀恒定（∝ t_mux/T_conv，与 K 无关）。"""
    e1 = D.mux_settling_erosion(64, 1, 8, False)
    e4 = D.mux_settling_erosion(64, 4, 8, False)
    return (abs(e1["overhead_rel_pct"] - e4["overhead_rel_pct"]) < 1e-9
            and 0.03 < e1["overhead_rel_pct"] < 0.06)


def _keep_erosion_ok() -> bool:
    """B7 · 🔴 保吞吐共享 mux 侵蚀 ∝K：K=160 → ≈6.94%（K* 处 ~7%，E18 漏计的真实代价）。"""
    e1 = D.mux_settling_erosion(64, 1, 8, True)
    e160 = D.mux_settling_erosion(64, 160, 8, True)
    return (abs(e160["overhead_rel_pct"] / e1["overhead_rel_pct"] - 160.0) < 1e-9
            and 5.0 < e160["overhead_rel_pct"] < 9.0)


def _keep_vs_plain_ok() -> bool:
    """B8 · 保吞吐侵蚀(K=160) ≫ plain 侵蚀(K=160)（反相关于 E18 面积收益）。"""
    ek = D.mux_settling_erosion(64, 160, 8, True)["overhead_rel_pct"]
    ep = D.mux_settling_erosion(64, 160, 8, False)["overhead_rel_pct"]
    return ek > 100.0 * ep


def _budget_ok() -> bool:
    """B9 · 动态预算项格式合规（RANDOM·非负）且 E15 合成律可跑（worst ~0.0946% ⇒ ~10 位）。"""
    terms = D.dynamic_budget_terms(8, 8, 8)
    cmb = B.combine(terms)
    return (len(terms) == 2 and all(t["category"] in B.CATEGORIES and t["rel_pct"] >= 0
                                    for t in terms)
            and 0.05 < cmb["worst_pct"] < 0.15 and cmb["worst_bits"] > 7.0)


def _disclosure_ok() -> bool:
    """B10 · 🔴 诚实（肯定）：披露含「不报 TOPS」「确定性 pedestal 可校准」「非 PDK」「不做功耗估算」。"""
    blob = " ".join(str(v) for v in D.COL_SHARE_DYN_DISCLOSURE.values())
    return ("不报 TOPS" in blob and ("校准" in blob or "可单点失调" in blob)
            and "非 PDK" in blob and "不做功耗估算" in blob)


_FALSE_CLAIMS = ("已报 TOPS", "已报能效", "已流片", "已含功耗", "已签核",
                 "实测硅数据", "已含真实版图寄生")


def _no_false_claim_ok() -> bool:
    """B11 · 🔴 诚实（否定）：**未声称** TOPS / 能效 / 已流片 / 已含功耗。

    🔴 用「**肯定性禁止短语**」而非 `"TOPS" not in blob` ——
    披露里写的是「**绝不报** TOPS/TOPS-W/fJ/op」（正确的自我否定），
    否定词窗口会误判（E12/E13/E17/E18 血案同族）。
    """
    blob = " ".join(str(v) for v in D.COL_SHARE_DYN_DISCLOSURE.values())
    return all(k not in blob for k in _FALSE_CLAIMS)


def _protect_e18_ok() -> bool:
    """B12 · 🔴 保护性约束：E18 已发布数字逐位不变（converter_period_s(8) / col_throughput 公式）
    · CONV/TIMING/COL_SHARE_PROCESS 键值未改（本段**只读消费**）。"""
    t = C.converter_period_s(8)
    sps4 = C.col_throughput_sps(4, 8, keep_throughput=False)
    return (abs(t - AN_T_CONV_8) < 1e-21
            and abs(sps4 - 1.0 / (4.0 * t)) < 1e-30
            and CV.CONV_PROCESS["c_unit_f"] == 1.0e-12
            and CV.CONV_PROCESS["r_unit_ohm"] == 10.0e3
            and T.TIMING_PROCESS["bits"] == 8
            and C.COL_SHARE_PROCESS["switch_wl"] == 500.0)


def _cross_ok() -> bool:
    """B13 · 跨模块交叉：mux R_on ⟷ E18 `cdac_settle_tau` 同器件 · kT/C 地板 ⟷ E18 `thermal_noise_rms_v`。"""
    tm = D.mux_settling_tau(8)
    return (abs(tm["r_on_ohm"] - T.cdac_settle_tau(8)["r_on_ohm"]) < 1e-15
            and abs(C.thermal_noise_rms_v(1.0e-12) - math.sqrt(
                C.KB * 300.0 / 1.0e-12)) < 1e-24)


def _report_shape_ok() -> bool:
    """B14 · 汇总报告结构完整（电荷注入/孔径抖动/mux建立 三块 + 侵蚀表 ≥9 + 预算项 2）。"""
    r = D.dynamic_cost_report(64, 64, 8)
    return (isinstance(r, dict) and r["is_oracle"] is False
            and "charge_injection" in r and "aperture_jitter" in r and "mux_settling" in r
            and len(r["mux_settling"]["erosion_table"]) >= 9
            and len(r["budget_terms"]) == 2)


def main() -> int:
    # ══════════════════════ A 模块自检 ══════════════════════
    ok_a = D.col_share_dynamic_self_check(verbose=False)
    check("A1 模块自检 13/13 PASS（电荷注入 pedestal/残差 · 孔径抖动越界频率 · mux R_on 同器件 · "
          "plain 侵蚀恒定 · 保吞吐侵蚀 ∝K · 预算项格式 · 保护性约束 · 诚实披露 · 汇总报告）", ok_a,
          "pedestal≈119mV · 残差≈29µV · K*=160 侵蚀≈6.94%")

    # ══════════════════════ B 关键事实（name-first）══════════════════════
    _ped = D.charge_injection_pedestal_v()
    _res = D.charge_injection_residual_sigma_v()
    check("B1 电荷注入：确定性 pedestal = %.1f mV（%.1f%%FS）· **可单点失调校准消除** · "
          "Pelgrom 随机残差 %.2f µV ≪ pedestal"
          % (_ped["pedestal_v"] * 1e3, _ped["pedestal_rel_pct"],
             _res["sigma_pedestal_v"] * 1e6),
          _pedestal_ok(), "ped=%.4e V · 残差=%.3e V" % (_ped["pedestal_v"],
                                                       _res["sigma_pedestal_v"]))

    _res = D.charge_injection_residual_sigma_v()
    _lsb = D.COL_SHARE_DYN_PROCESS["ref_v"] / (1 << 8)
    check("B2 🔴 电荷注入随机残差 ≪ kT/C 与 LSB（%.2e V vs kT/C %.2e / LSB %.2e）⇒ **不是墙**"
          % (_res["sigma_pedestal_v"], C.thermal_noise_rms_v(_ped["sample_cap_f"]),
              _lsb),
          _residual_ok(), "vs_ktc=%.4f · vs_lsb=%.5f" % (_res["vs_ktc_ratio"], _res["vs_lsb_ratio"]))

    _jit = D.aperture_jitter_sigma_v()
    check("B3 孔径抖动 @ %.0f MHz：σ_v = %.1f µV（%.4f%%FS）< LSB=%.1f µV（**条件性，非墙**）"
          % (_jit["signal_freq_hz"] / 1e6, _jit["sigma_v"] * 1e6, _jit["sigma_rel_pct"],
             _jit["lsb_v"] * 1e6),
          _jitter_ok(), "σ_v=%.4e V" % _jit["sigma_v"])

    _jl = D.jitter_bandwidth_limits(8)
    check("B4 孔径抖动越界频率：f_ktc = %.1f MHz < f_lsb = %.0f MHz（先越 kT/C 再越 LSB）"
          % (_jl["f_cross_ktc_hz"] / 1e6, _jl["f_cross_lsb_hz"] / 1e6),
          _jitter_limits_ok(), "f_ktc=%.4e · f_lsb=%.4e Hz" % (_jl["f_cross_ktc_hz"],
                                                          _jl["f_cross_lsb_hz"]))

    _tm = D.mux_settling_tau(8)
    check("B5 多路开关 R_on = %.4f Ω（**同一器件 W/L=500**，⟷ E18 CDAC 开关）· "
          "t_mux = %.2f ps ≪ T_conv(1) = %.1f ns（×%.0f）" % (_tm["r_on_ohm"],
          _tm["t_settle_s"] * 1e12, C.converter_period_s(8) * 1e9,
          C.converter_period_s(8) / _tm["t_settle_s"]),
          _mux_ron_ok(), "τ_mux=%.3e s" % _tm["tau_s"])

    _e1 = D.mux_settling_erosion(64, 1, 8, False)
    check("B6 多路开关建立 plain 共享：侵蚀**恒定**（∝ t_mux/T_conv，与 K 无关）≈ %.4f%%（可忽略）"
          % _e1["overhead_rel_pct"],
          _plain_erosion_ok(), "恒定侵蚀=%.4f%%" % _e1["overhead_rel_pct"])

    _e160 = D.mux_settling_erosion(64, 160, 8, True)
    check("B7 🔴 **保吞吐共享 mux 侵蚀 ∝K**：K=160 → %.2f%%（≈K 倍 · **K*≈160 处 ~7%%**）"
          "—— E18 静态模型此前未计的真实动态代价" % _e160["overhead_rel_pct"],
          _keep_erosion_ok(), "K=160 侵蚀=%.3f%%" % _e160["overhead_rel_pct"])

    check("B8 保吞吐侵蚀(K=160, %.2f%%) ≫ plain 侵蚀(K=160)（反相关于 E18 面积收益）"
          % _e160["overhead_rel_pct"],
          _keep_vs_plain_ok(), "比值 ≫100×")

    _terms = D.dynamic_budget_terms(8, 8,8)
    _cmb = B.combine(_terms)
    check("B9 动态预算项格式合规（RANDOM·非负）且 E15 合成律可跑：worst = %.4f%% ⇒ %.3f 位"
          % (_cmb["worst_pct"], _cmb["worst_bits"]),
          _budget_ok(), "项=%d · worst_bits=%.4f" % (_cmb["n_terms"], _cmb["worst_bits"]))

    check("B10 🔴 诚实（肯定）：披露含「不报 TOPS」+「可校准」+「非 PDK」+「不做功耗估算」",
          _disclosure_ok(), "披露 %d 键全含要求项" % len(D.COL_SHARE_DYN_DISCLOSURE))

    check("B11 🔴 诚实（否定）：**未声称** TOPS / 能效 / 已流片 / 已含功耗（🔴 用**肯定性禁止短语**，"
          "不用 `\"TOPS\" not in blob` —— 否则误伤「**绝不报** TOPS」这句正确的自我否定）",
          _no_false_claim_ok(), "禁止短语 %d 条无一命中" % len(_FALSE_CLAIMS))

    check("B12 🔴 **保护性约束**：E18 已发布数字**逐位不变**（`converter_period_s(8)` = %.6e ns · "
          "`col_throughput_sps(4,keep=False)=1/(4·T_conv)`）· CONV/TIMING/COL_SHARE_PROCESS 键值未改"
          % (C.converter_period_s(8) * 1e9),
          _protect_e18_ok(), "本段只读消费 ⇒ 上游全不受影响")

    check("B13 跨模块交叉：mux R_on ⟷ E18 `cdac_settle_tau` 同器件（6.41 Ω）· kT/C 地板 ⟷ E18 "
          "`thermal_noise_rms_v`", _cross_ok(), "R_on=%.6f Ω" % D.mux_settling_tau(8)["r_on_ohm"])

    _rep = D.dynamic_cost_report(64, 64, 8)
    check("B14 汇总报告结构完整（电荷注入/孔径抖动/mux建立 三块 + 侵蚀表 %d 行 + 预算项 %d）"
          % (len(_rep["mux_settling"]["erosion_table"]), len(_rep["budget_terms"])),
          _report_shape_ok(), "结论键=%d" % len(_rep["conclusion"]))

    # ══════════════════════ C 反向可证伪（6 条突变探针）══════════════════════
    # C1 披露**追加**「已报 TOPS」（而非替换）⇒ **只有 B11 红**，B10 仍绿（探针特异性）
    _bad_disc = dict(D.COL_SHARE_DYN_DISCLOSURE)
    _bad_disc["no_power"] = _bad_disc["no_power"] + " 已报 TOPS：8.3 TOPS"
    with mock.patch.object(D, "COL_SHARE_DYN_DISCLOSURE", _bad_disc):
        c1_false = not _no_false_claim_ok()
        c1_still_true = _disclosure_ok()
    check("C1 反向：披露**追加**「已报 TOPS」（而非替换原文）⇒ B11 必红 · **且 B10 仍绿**"
          "（🔴 探针只对被测机制敏感）", c1_false and c1_still_true,
          "B11 变红 = %s · B10 仍绿 = %s" % (c1_false, c1_still_true))

    # C2 电荷注入随机残差越 kT/C（破坏校准剔除逻辑）⇒ B2 必红
    _ORIG_res = D.charge_injection_residual_sigma_v
    with mock.patch.object(D, "charge_injection_residual_sigma_v",
                           lambda override=None: dict(_ORIG_res(override),
                                                      sigma_pedestal_v=1.0e-3,
                                                      below_ktc=False, below_lsb=False)):
        c2 = not _residual_ok()
    check("C2 反向：电荷注入随机残差**越 kT/C**（σ=1 mV，破坏校准剔除逻辑）⇒ B2 必红"
          "（「残差必须 ≪ kT/C/LSB」必须能被判出来）", c2, "残差判据实测变红 = %s" % c2)

    # C3 孔径抖动公式坏（σ_v 放大 100×）⇒ B3 必红
    _ORIG_jit = D.aperture_jitter_sigma_v
    with mock.patch.object(D, "aperture_jitter_sigma_v",
                           lambda f=None, override=None: dict(_ORIG_jit(f, override),
                                                             sigma_v=3.0e-2,
                                                             sigma_rel_pct=3.0,
                                                             below_lsb=False)):
        c3 = not _jitter_ok()
    check("C3 反向：孔径抖动公式坏（σ_v 放大到 30 mV）⇒ B3 必红"
          "（「抖动须 < LSB」必须能被判出来）", c3, "抖动判据实测变红 = %s" % c3)

    # C4 多路开关 R_on 错（改成 1000 Ω，破坏同器件不变性）⇒ B5 必红
    _ORIG_mux = D.mux_settling_tau
    with mock.patch.object(D, "mux_settling_tau",
                           lambda bits=None, override=None: dict(_ORIG_mux(bits, override),
                                                                 r_on_ohm=1000.0,
                                                                 same_device_as_e18=False)):
        c4 = not _mux_ron_ok()
    check("C4 反向：多路开关 R_on 错（=1000 Ω，破坏「同器件 W/L=500」不变性）⇒ B5 必红"
          "（「R_on 须 = 6.41 Ω 同 E18」必须能被判出来）", c4, "mux 判据实测变红 = %s" % c4)

    # C5 保吞吐侵蚀不 ∝K（恒为 0.1%）⇒ B7 必红
    _ORIG_ero = D.mux_settling_erosion
    with mock.patch.object(D, "mux_settling_erosion",
                           lambda n, k=1, bits=None, keep=False, override=None: dict(
                               _ORIG_ero(n, k, bits, keep, override), overhead_rel_pct=0.1)):
        c5 = not _keep_erosion_ok()
    check("C5 反向：保吞吐侵蚀**不 ∝K**（恒为 0.1%%）⇒ B7 必红"
          "（「K*=160 处 ≈7%%」必须能被判出来）", c5, "侵蚀判据实测变红 = %s" % c5)

    # C6 plain 侵蚀随 K 变（打破「恒定」不变性）⇒ B6 必红
    def _ero_bad(n, k=1, bits=None, keep=False, override=None):
        r = _ORIG_ero(n, k, bits, keep, override)
        if not keep:
            r["overhead_rel_pct"] = 0.01 * float(max(1, int(k)))
        return r
    with mock.patch.object(D, "mux_settling_erosion", _ero_bad):
        c6 = not _plain_erosion_ok()
    check("C6 反向：plain 侵蚀**随 K 变**（打破「恒定」不变性）⇒ B6 必红"
          "（「plain 侵蚀须与 K 无关」必须能被判出来）", c6, "plain 判据实测变红 = %s" % c6)

    # 还原重跑（无残留漂移）
    check("C7 还原完整性：全部探针退出后，A1 自检 + B2/B3/B5/B6/B7/B11 复跑仍全绿",
          D.col_share_dynamic_self_check(verbose=False) and _residual_ok() and _jitter_ok()
          and _mux_ron_ok() and _plain_erosion_ok() and _keep_erosion_ok()
          and _no_false_claim_ok())

    # ── K 自入 CI core ────────────────────────────────────────────────
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e19_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        if not ok:
            print("FAIL | " + name + (("  :: " + detail) if detail else ""))
        elif detail:
            print("PASS | " + name + "  :: " + detail)
    print()
    print("=" * 74)
    print("E19 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 6 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
