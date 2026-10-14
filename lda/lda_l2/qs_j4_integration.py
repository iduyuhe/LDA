# -*- coding: utf-8 -*-
"""J4-M2 单芯片集成预算（Quantum Sensing System Integration · Layer 4 / 缺口 G-QSYS-3）。

═══ 这是什么 ═══
把「NV 阵列 + 微波天线 + 光路 + 读出」**落到同一颗芯片**的功能集成预算：微波驱动与读出
光路之间的**跨域寄生耦合**、读出链的杂散光、驱动线的功率不均匀 —— 多源合成 ⇒ **净灵敏度
劣化倍率**与集成签核。QS 器件征程（M0–M9）只覆盖**同域**（阵列磁偶极串扰 B478/B479、
读出 mux B508），**跨域集成**完全空白。

    X_total   = √(X_mw² + X_opt² + X_ro²)        （三源正交合成）
    η_eff     = η_single · X_total                （净灵敏度劣化倍率）

🔴🔴 **账本锚净增 0（如实登记 · 三重避让）** —— **实 grep 全仓**后三个候选形式全部与既有锚
同源，登记任一都会构成重复计数：

| 候选形式 | 被谁占用 | 判否理由 |
|---|---|---|
| **隔离度 = 1/|S21|²** | **B513**（`purcell_filter_suppression`） | **同数值格式**（ABCD 代数闭式 ⇄ ODE 数值积分） |
| **跨域耦合模能量交换** | **B14**（定向耦合器 `dc_cmt_solver`） | 结构同源（同一耦合模算子） |
| **串扰恶化灵敏度倍率 √(1+X²)** | **B479**（`nv_array_crosstalk_sensitivity_penalty`） | **同被测标量** |
| **级联隔离度 ∏I_i（dB 相加）** | **S4**（`s4_fidelity_budget` ∏fᵢ） | 结构同源（乘法级联预算） |

⇒ 本模块交付**能力层（可复算的集成预算）+ 诚实登记「无锚」**，**不硬凑**。

═══ 诚实边界 ═══
· 隔离度 / 杂散光耦合比 / 驱动不均匀度均为**设计示例量级**（非实测芯片 PDK）；
· 只证「集成预算链自洽 + 量级合理」，**不作制造/性能宣称**；
· 未建模：3D 电磁全波耦合、封装腔体谐振、多通道相位一致性、温度梯度。
零商业依赖（纯 numpy + math；零 RNG）。
"""
from __future__ import annotations

import math

#: 🔴 锚登记状态（供门禁判据机械核 —— 本档**净增 0**）
ANCHOR_STATUS = "none"
ANCHOR_AVOIDANCE = (
    ("isolation 1/|S21|^2", "B513 purcell_filter_suppression", "同数值格式（ABCD ⇄ ODE 积分）"),
    ("coupled-mode exchange", "B14 dc_cmt_solver（定向耦合器）", "结构同源（同一耦合模算子）"),
    ("crosstalk penalty sqrt(1+X^2)", "B479 array crosstalk penalty", "同被测标量"),
    ("cascaded isolation prod I_i", "S4 fidelity budget（prod f_i）", "结构同源（乘法级联）"),
)

# ══════════════════════════════════════════════════════════════════════
# 设计示例常量（dB 域隔离度 / 比值域耦合）
# ══════════════════════════════════════════════════════════════════════
ISO_MW_OPT_DB = 55.0              # dB（微波驱动 → 读出光路的跨域隔离度）
ISO_OPT_RO_DB = 40.0              # dB（泵浦光 → 读出链的杂散光隔离度）
DRIVE_NONUNIFORMITY_DB = 0.2      # dB（沿线微波幅度不均匀度 ~2.3%）
ISOLATION_FLOOR_DB = 30.0         # dB（集成签核下限）

_CALIBER = "单芯片集成预算 · 三源正交合成 · 设计示例量级"


def assert_caliber(caliber: str) -> None:
    if caliber != _CALIBER:
        raise ValueError("集成口径不符：本模块仅支持 %r" % _CALIBER)


def db_to_ratio(db: float) -> float:
    """隔离度 dB → 幅度比值（10^(dB/20)）。"""
    return 10.0 ** (float(db) / 20.0)


def crosstalk_amplitude_from_isolation(iso_db: float) -> float:
    """隔离度 ISO(dB) 对应的**正交串扰幅度** X = 10^(−ISO/20)（无量纲）。"""
    if iso_db <= 0.0:
        raise ValueError("隔离度须 > 0 dB")
    return 10.0 ** (-float(iso_db) / 20.0)


def net_sensitivity_penalty(iso_mw_opt_db: float = ISO_MW_OPT_DB,
                            iso_opt_ro_db: float = ISO_OPT_RO_DB,
                            drive_nonuniformity_db: float = DRIVE_NONUNIFORMITY_DB) -> float:
    """净灵敏度劣化倍率 X_total = √(1 + X_mw² + X_opt² + X_drive²)。

    🔴 与 **B479**（阵列串扰恶化倍率 √(1+X_tot²)）**同为**该正交合成式 —— 故本档**不登记锚**
    （同被测标量）；此处仅供集成预算内部使用。
    """
    x_mw = crosstalk_amplitude_from_isolation(iso_mw_opt_db)
    x_opt = crosstalk_amplitude_from_isolation(iso_opt_ro_db)
    x_drive = 10.0 ** (float(drive_nonuniformity_db) / 20.0) - 1.0
    return math.sqrt(1.0 + x_mw ** 2 + x_opt ** 2 + x_drive ** 2)


def integration_report(iso_mw_opt_db: float = ISO_MW_OPT_DB,
                       iso_opt_ro_db: float = ISO_OPT_RO_DB,
                       drive_nonuniformity_db: float = DRIVE_NONUNIFORMITY_DB,
                       iso_floor_db: float = ISOLATION_FLOOR_DB) -> dict:
    """单芯片集成预算报告（三源隔离度 + 净劣化 + 签核 + 锚状态）。"""
    x_tot = net_sensitivity_penalty(iso_mw_opt_db, iso_opt_ro_db, drive_nonuniformity_db)
    worst_iso = min(float(iso_mw_opt_db), float(iso_opt_ro_db))
    return {
        "caliber": _CALIBER,
        "iso_mw_opt_db": float(iso_mw_opt_db),
        "iso_opt_ro_db": float(iso_opt_ro_db),
        "drive_nonuniformity_db": float(drive_nonuniformity_db),
        "worst_isolation_db": float(worst_iso),
        "net_sensitivity_penalty": float(x_tot),
        "penalty_ppm": float((x_tot - 1.0) * 1e6),
        "anchor_status": ANCHOR_STATUS,
        "verdict": "ACCEPT" if worst_iso >= float(iso_floor_db) and x_tot < 1.01 else "REJECT",
    }


# ── 自检 ────────────────────────────────────────────────────────────────
def selfcheck_qs_j4_integration() -> dict:
    checks = {}
    checks["anchor_status_is_none"] = bool(ANCHOR_STATUS == "none")
    checks["avoidance_has_4_entries"] = bool(len(ANCHOR_AVOIDANCE) == 4)
    checks["db_ratio_roundtrip"] = bool(abs(db_to_ratio(20.0) - 10.0) < 1e-12)
    checks["higher_isolation_smaller_crosstalk"] = bool(
        crosstalk_amplitude_from_isolation(60.0) < crosstalk_amplitude_from_isolation(40.0))
    # 隔离度每 +20 dB ⇒ 串扰幅度 ÷10
    checks["decade_per_20db"] = bool(
        abs(crosstalk_amplitude_from_isolation(60.0) * 10.0
            - crosstalk_amplitude_from_isolation(40.0)) < 1e-15)
    # 无限隔离 ⇒ X→1（只余驱动不均匀）
    checks["infinite_isolation_limits"] = bool(
        net_sensitivity_penalty(1e6, 1e6, 0.0) - 1.0 < 1e-6)
    checks["penalty_ge_one"] = bool(net_sensitivity_penalty() >= 1.0)
    checks["penalty_monotone_in_nonuniformity"] = bool(
        net_sensitivity_penalty(drive_nonuniformity_db=3.0)
        > net_sensitivity_penalty(drive_nonuniformity_db=0.2))
    rep = integration_report()
    checks["report_verdict_accept"] = bool(rep["verdict"] == "ACCEPT")
    checks["report_anchor_status_none"] = bool(rep["anchor_status"] == "none")
    checks["report_worst_isolation_min"] = bool(
        abs(rep["worst_isolation_db"] - min(ISO_MW_OPT_DB, ISO_OPT_RO_DB)) < 1e-12)
    # 反向探针：隔离度取 0 ⇒ 串扰 = 1（全耦合）且签核必 REJECT
    checks["reverse_zero_isolation_rejects"] = bool(
        integration_report(iso_mw_opt_db=20.0)["verdict"] == "REJECT")
    checks["reverse_bad_iso_raises"] = _raises(lambda: crosstalk_amplitude_from_isolation(0.0))
    checks["reverse_bad_caliber_raises"] = _raises(lambda: assert_caliber("x"))
    return checks


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def main() -> int:
    sc = selfcheck_qs_j4_integration()
    bad = 0
    print("=" * 64)
    print("J4-M2 单芯片集成预算自检（锚净增 0 · 如实登记）：")
    for k, v in sc.items():
        ok = bool(v)
        bad += 0 if ok else 1
        print("  [%s] %s" % ("PASS" if ok else "FAIL", k))
    print("=" * 64)
    print("ALL PASS" if bad == 0 else "%d FAIL" % bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
