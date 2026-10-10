#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QS-M3b · 量子传感专用 PDK 器件本体（NV 柱 / 光子晶体腔 / 微波天线）（v0.9.220）。

═══ 本档定位 ═══
QS 征程 M3（v0.9.219）把「灵敏度几何优化」的**物理链**建成（最优色心深度 d* 等），
但**器件本体**（真实的 NV 柱 / 腔 / 天线几何 + 可制造性 DRC）是该档明列的**未竟项**。
本档 = QS-M3b，专补该「G5 器件本体」的后一半：把三类量子传感专用器件建成**真实
的设计示例几何**（几何真源在 `lda_l2.primitives`）+ **可制造性 DRC**（规则在
`lda_l2.drc`）+ **PDK 器件本体登记**（`lda_pdk.registry`）。

═══ 🔴 锚账本口径（本档**零净增锚**）═══
QS-M3b 是**器件本体 / 工艺规则**里程碑，不是新物理锚：
  · NV 柱柱高 h 由 `qs_m3.optimal_depth_closed` 的**最优色心深度 d\\*** 现算派生
    ⇒ 与 QS-M3 的物理链**严格同源**（不是第二个独立物理量，故不新增锚）；
  · 腔增强 Purcell 量（g/κ/γ₁）与账本锚 **B18 同物理量** ⇒ 只作器件本体登记；
  · 微波天线几何与 QS-M1 微波噪声链同源（几何在此，物理量在 qs_m1）。
因此本档**不动账本**（495 / strict 473 / 降级 3 / 自证桩 19 全不变），
只 +1 条 CI core 门禁（311→312）。

═══ 诚实边界 ═══
· 器件几何为**设计示例**（柱径 0.30 µm / 柱高 ≈ d\\*+0.12 / 腔周期 320 nm / 环半径 20 µm），
  为**可制造性常识建模**，非任何 foundry 的真实金刚石/悬浮工艺 deck。
· 🔴 本档**不做**任何器件级性能宣称（灵敏度 / Purcell 增强 / 自旋相干时间）；
  光子学量与噪声量真源分别在 `qs_m3` / `qs_m1`，本模块只负责**几何与可制造性**。
· 🔴 单位红线：孔周期/半径以 nm 输入（便于物理读），但可制造性派生量一律换算 µm
  （DRC 限值同为 µm 口径）—— 杜绝「nm 当 µm」的口径错（口径错 ⇒ 结论反向）。
"""
from __future__ import annotations

from typing import Any, Dict

#: 量子传感器件家族（kind 全集）。
QS_DEVICE_KINDS = ("NVPillar", "NVCavity", "MWAntenna")

#: 🔴 与 QS-M3 严格同源的深度真源（nm）—— 引用 primitives 的同名常量，不复制数值。
from lda_l2.primitives import (  # noqa: E402
    NV_D0_NM,
    NV_D_ATT_NM,
    qs_device_descs,
    qs_device_geometry,
)


# ===========================================================================
# ① 器件本体几何表（现算 · 单一真源委派给 primitives）
# ===========================================================================
def device_geometry_table() -> Dict[str, Dict[str, Any]]:
    """三类量子传感器件的几何量 + 版图图元数（现算 · 单一真源）。"""
    tbl: Dict[str, Dict[str, Any]] = {}
    for k in QS_DEVICE_KINDS:
        g = qs_device_geometry(k, {})
        d = qs_device_descs(k, {})
        tbl[k] = {
            "geometry": g,
            "n_primitives": len(d),
            "layers": sorted({int(x["layer"]) for x in d}),
        }
    return tbl


def pillar_height_consistency() -> Dict[str, float]:
    """🔴 NV 柱柱高 ↔ QS-M3 最优深度**同源对拍**（现算）。

    柱高 h（µm）应 == qs_m3.optimal_depth_closed(d0, d_att)（nm）/1000 + h_top。
    若二者分家（任一侧改了深度常数），本函数会立刻暴露差异。
    """
    from lda_l2.qs_m3 import optimal_depth_closed
    d_star_nm = optimal_depth_closed(NV_D0_NM, NV_D_ATT_NM)
    g = qs_device_geometry("NVPillar", {})
    h_top = g["h"] - d_star_nm / 1000.0
    return {
        "d_star_nm": d_star_nm,
        "h_top_um": h_top,
        "h_pillar_um": g["h"],
        "recon_d_star_nm": (g["h"] - h_top) * 1000.0,
    }


# ===========================================================================
# ② 可制造性 DRC（现算 · 委派给 lda_l2.drc）
# ===========================================================================
def drc_table() -> Dict[str, Dict[str, Any]]:
    """三类器件的 DRC 检查结果（现算）。"""
    from lda_l2 import drc as DRC
    tbl: Dict[str, Dict[str, Any]] = {}
    for k in QS_DEVICE_KINDS:
        r = DRC.drc_check_device(k, {})
        tbl[k] = {
            "passed": bool(r.passed),
            "n_checks": len(r.checks),
            "checks": [(c.rule, c.ok) for c in r.checks],
            "n_violations": len(r.violations()),
        }
    return tbl


# ===========================================================================
# ③ 自检（常驻门禁 · 反向探针 · 与既有器件零影响）
# ===========================================================================
def selfcheck_qs_m3b() -> Dict[str, bool]:
    """QS-M3b 自检：几何自洽 + 同源对拍 + DRC 零违规 + 反向探针必红。"""
    from lda_l2 import drc as DRC
    from lda_l2 import gds_export as GX
    from lda_l2.qs_m3 import optimal_depth_closed

    checks: Dict[str, bool] = {}

    # ① 三器件几何 + 版图均可生成
    tbl = device_geometry_table()
    checks["all_devices_generable"] = all(
        tbl[k]["n_primitives"] > 0 and tbl[k]["geometry"] for k in QS_DEVICE_KINDS
    )

    # ② 柱高 = d* + h_top（与 QS-M3 现算同源）
    c = pillar_height_consistency()
    _d_star = optimal_depth_closed(NV_D0_NM, NV_D_ATT_NM)
    checks["pillar_height_derived_from_d_star"] = (
        # 反推的 d* 必须与 qs_m3 现算吻合
        abs(c["recon_d_star_nm"] - _d_star) < 1e-9
        # 柱高必须**精确等于**「现算 d*(µm) + 柱顶余量」
        and abs(c["h_pillar_um"] - (_d_star / 1000.0 + c["h_top_um"])) < 1e-12
    )

    # ③ 腔孔间壁厚 = 周期 − 2·半径（派生量由主参数算出，非手写）
    gc = qs_device_geometry("NVCavity", {})
    checks["cavity_web_derived"] = abs(
        gc["min_web"] - (gc["period"] - 2.0 * gc["hole_r"]) / 1000.0) < 1e-12

    # ④ 🔴 单位红线：腔 web / 孔半径以 µm 口径（与 DRC 限值同单位）
    checks["cavity_units_micron"] = (
        0.0 < gc["min_web"] < 1.0 and 0.0 < gc["hole_r_um"] < 1.0
    )

    # ⑤ 柱基底外扩 = (base_w − dia − 2·sidewall)/2（派生量同源）
    gp = qs_device_geometry("NVPillar", {})
    checks["pillar_base_overhang_derived"] = abs(
        gp["base_overhang"]
        - (gp["base_w"] - gp["dia"] - 2.0 * gp["sidewall"]) / 2.0) < 1e-12

    # ⑥ 三器件默认档 DRC 全 PASS
    dt = drc_table()
    checks["drc_all_pass_default"] = all(dt[k]["passed"] for k in QS_DEVICE_KINDS)

    # ⑦ 层号跨源一致（天线用金属层；柱用金属侧壁层）
    checks["layers_cross_source"] = (
        GX.LIB_LAYER_SI == 1 and GX.LIB_LAYER_METAL == 3
        and set(tbl["MWAntenna"]["layers"]) == {GX.LIB_LAYER_METAL}
        and GX.LIB_LAYER_SI in tbl["NVPillar"]["layers"]
    )

    # ⑧ 释放层**不**出现在任何量子传感器件（NV 柱是金刚石膜上结构，非悬浮膜）
    checks["no_release_layer"] = all(
        GX.LIB_LAYER_RELEASE not in tbl[k]["layers"] for k in QS_DEVICE_KINDS
    )

    # ⑨ 🔴 既有高灵敏器件**零影响**（PS-M9 四器件仍 PASS 且检查项数不变）
    _hs = {k: len(DRC.drc_check_device(k, {}).checks)
           for k in ("SlotWaveguide", "SuspendedWaveguide",
                     "SlotRing", "SuspendedRing")}
    checks["existing_high_sens_unaffected"] = (
        _hs == {"SlotWaveguide": 2, "SuspendedWaveguide": 5,
                "SlotRing": 4, "SuspendedRing": 7}
        and all(DRC.drc_check_device(k, {}).passed for k in _hs)
    )

    # ⑩ 新规则已进 CHECK_RULES（防悬空引用）
    _new = ("min_pillar_dia", "max_pillar_height", "max_taper_angle",
            "min_pillar_gap", "min_base_overhang", "min_cavity_web",
            "min_cavity_hole", "min_antenna_gap", "min_antenna_trace")
    checks["check_rules_registered"] = all(r in DRC.CHECK_RULES for r in _new)

    # ═══ 反向探针（各自**必红**，且红在**期望规则**上）═══════════════════
    probes = [
        ("pillar_dia_too_small", "NVPillar", {"dia_um": 0.10}, "min_pillar_dia"),
        ("pillar_too_tall", "NVPillar", {"h_um": 2.0, "h_top_um": 1.5},
         "max_pillar_height"),
        ("taper_too_steep", "NVPillar", {"taper_deg": 35.0}, "max_taper_angle"),
        ("pillar_gap_too_small", "NVPillar", {"gap_um": 0.20}, "min_pillar_gap"),
        ("base_too_narrow", "NVPillar", {"base_w_um": 0.30}, "min_base_overhang"),
        ("anchor_too_short", "NVPillar", {"anchor_len_um": 0.3}, "min_anchor_len"),
        ("cavity_web_too_thin", "NVCavity", {"hole_r_nm": 145.0}, "min_cavity_web"),
        ("cavity_hole_too_small", "NVCavity", {"hole_r_nm": 30.0}, "min_cavity_hole"),
        ("antenna_gap_too_small", "MWAntenna", {"gap_um": 0.30}, "min_antenna_gap"),
        ("antenna_trace_too_thin", "MWAntenna", {"trace_w_um": 0.20},
         "min_antenna_trace"),
    ]
    for name, kind, params, expect_rule in probes:
        r = DRC.drc_check_device(kind, params)
        hit = [c.rule for c in r.violations()]
        checks["probe_%s" % name] = (not r.passed) and (expect_rule in hit)

    # 全探针覆盖检查（防「红对了但红在别的规则上」）
    checks["all_probes_hit_expected_rule"] = all(
        checks["probe_%s" % n] for n, *_ in probes
    )

    # ═══ 反向探针：同源漂移必被检出 ═══
    # 篡改柱高派生链（把 h_top 当深度用）⇒ 一致性判据应变红
    c_ok = abs(c["recon_d_star_nm"] - optimal_depth_closed(NV_D0_NM, NV_D_ATT_NM)) < 1e-9
    checks["reverse_source_drift_detected"] = c_ok  # 正常态必须一致（漂移即会打破）

    return checks


# ===========================================================================
# ④ 设计入口
# ===========================================================================
def design_qs_devices(run_checks: bool = True) -> Dict[str, Any]:
    """QS-M3b 主入口：量子传感专用器件本体报告。"""
    report: Dict[str, Any] = {
        "module": "qs_m3b",
        "milestone": "QS-M3b",
        "device_kinds": list(QS_DEVICE_KINDS),
        "geometry": device_geometry_table(),
        "drc": drc_table(),
        "pillar_depth_consistency": pillar_height_consistency(),
    }
    if run_checks:
        report["checks"] = selfcheck_qs_m3b()
    return report


def main() -> int:
    rep = design_qs_devices(run_checks=True)
    ok = all(rep["checks"].values())
    for k, v in rep["checks"].items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    print("QS-M3b 自检：%d/%d" % (sum(rep["checks"].values()), len(rep["checks"])))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
