"""真机 ORACLE 接入契约自洽 smoke（2026-09-11 建 · 2026-09-23 扩 ①②）。

零真实数据：仅验证 C1–C5 契约结构与 G1/C4/C5/G2 / W / ① 守卫**系统能力**已
研发完整，不接任何真实 foundry / 流片真值，不构成假绿。

验证项：
  1. 契约模块可导入、REAL_MACHINE_ANCHOR_BINDING 为空（锁死档现状）
  2. REAL_MACHINE_ORACLE.is_empty == True（零真值）
  3. 无 provenance 注册 → OracleGuardError（C5 守卫）
  4. T1-B 输出反向注册 → OracleGuardError（G1/C4 标定单向）
  5. assert_t1_kernel_sovereign() 对 DEVSIM（B 级）不抛（G2 主权钩子）
  ── 2026-09-23 新增（杜先生裁定 ①②，「逐步解锁」的四项决议）──
  6. ① 分类完备：ELIGIBLE ∩ INELIGIBLE == ∅ 且并集 == 全部 OracleKind
  7. ① 正向（**合法必过**）：三种实测 kind 守卫必过（证明非恒抛）
  8. ① 反向 A：商业求解器场级解 kind 注册 → 必 raise
  9. ① 反向 B：role="secondary_golden" → 必 raise（机制整体禁用）
 10. ② 反向 A：声称已标定但窗口表内无该锚 ⇒ 必 raise（未签字 = 未标定）
 11. ② 反向 B：已签字窗口下**超窗** ⇒ 必 raise
 12. ② 正向（**合法必过**）：已签字窗口下**窗内** ⇒ 注册成功且值可回读
 13. ② 诚实默认：honest_tier 空串（未声称标定）⇒ 放行
 14. ② 现状：SIGNED_CALIBRATION_WINDOWS 为空 · SECONDARY_GOLDEN_ALLOWED is False

注：② 的注入测试一律用**新 registry 实例**，不污染全局单例（保 is_empty 现状）。
"""
import os
import sys

# 项目引导：本文件位于 lda/，被测模块以顶层包名（lda_harness.*）导入 ⇒
# 把本文件所在目录（lda/）加入 sys.path，使其在「项目根 cwd」与「lda/ cwd」
# 两种调用方式下均可导入（与同族 smoke 一致；原用相对串 "lda" 仅在项目根 cwd 有效）。
_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_harness.real_machine_oracle import (  # noqa: E402
    CALIBRATED_TIER_PREFIX,
    GOLDEN_ELIGIBLE_KINDS,
    GOLDEN_INELIGIBLE_KINDS,
    REAL_MACHINE_ANCHOR_BINDING,
    REAL_MACHINE_ORACLE,
    SECONDARY_GOLDEN_ALLOWED,
    SIGNED_CALIBRATION_WINDOWS,
    CalibrationWindow,
    MeasurementQuantity,
    OracleGuardError,
    OracleKind,
    RealMachineMeasurement,
    RealMachineOracleRegistry,
    RealMachineProvenance,
    assert_t1_kernel_sovereign,
    guard_golden_eligibility,
)


def _expect_raise(fails, name, fn):
    """调用 fn，期望 OracleGuardError；未抛即记失败。"""
    try:
        fn()
    except OracleGuardError:
        return
    fails.append(name)


def main() -> int:
    fails = []

    # 1. 绑定表为空（锁死档现状）
    if REAL_MACHINE_ANCHOR_BINDING:
        fails.append("REAL_MACHINE_ANCHOR_BINDING 应空（T2 锁死，B 未启动）")

    # 2. 全局注册表零真值
    if not REAL_MACHINE_ORACLE.is_empty:
        fails.append("REAL_MACHINE_ORACLE 应 is_empty==True（零真实数据）")

    # 3. C5 守卫：无 provenance 拒入
    try:
        REAL_MACHINE_ORACLE.register(
            RealMachineMeasurement("B-4", MeasurementQuantity.DETECTOR_BANDWIDTH,
                                   value=25.0, unit="GHz"),
            RealMachineProvenance(ref=""),  # 空 provenance
        )
        fails.append("C5 守卫失效：空 provenance 竟被注册")
    except OracleGuardError:
        pass  # 期望

    # 4. G1/C4 守卫：T1-B 输出反向注册拒入
    try:
        REAL_MACHINE_ORACLE.register(
            RealMachineMeasurement("B-3", MeasurementQuantity.CARRIER_DENSITY,
                                   value=1e17, unit="cm^-3", provenance_ref="p1"),
            RealMachineProvenance(ref="p1", foundry="X"),
        )
        fails.append("G1/C4 守卫失效：T1-B 输出反向注册为 ORACLE")
    except OracleGuardError:
        pass  # 期望

    # 5. G2 主权钩子：DEVSIM 应登记为 B 级（非 A）
    try:
        assert_t1_kernel_sovereign()
    except OracleGuardError as e:
        fails.append(f"G2 钩子异常：{e}")

    # ------------------------------------------------------------------
    # ① 商业求解器不作（二级）golden
    # ------------------------------------------------------------------
    all_kinds = set(OracleKind)
    # 6. 分类完备：两集不相交且并集为全部 kind
    if GOLDEN_ELIGIBLE_KINDS & GOLDEN_INELIGIBLE_KINDS:
        fails.append("① 分类失效：ELIGIBLE 与 INELIGIBLE 有交集")
    if (GOLDEN_ELIGIBLE_KINDS | GOLDEN_INELIGIBLE_KINDS) != all_kinds:
        fails.append("① 分类不完备：有 kind 既不在 ELIGIBLE 也不在 INELIGIBLE")
    if OracleKind.COMMERCIAL_SOLVER_FIELD in GOLDEN_ELIGIBLE_KINDS:
        fails.append("① 分类失效：商业求解器场级解被列为可作 golden")

    # 7. 正向（合法必过）：三种实测 kind 必过
    for k in sorted(GOLDEN_ELIGIBLE_KINDS, key=lambda x: x.value):
        try:
            if not guard_golden_eligibility(k):
                fails.append(f"① 正向失败：{k.value} 守卫未返回 True")
        except OracleGuardError as e:
            fails.append(f"① 正向失败（实测 kind 竟被拦）：{k.value} - {e}")

    # 8. 反向 A：商业求解器场级解注册必 raise
    _expect_raise(
        fails, "① 反向 A 失效：商业求解器场级解竟被注册为 golden",
        lambda: RealMachineOracleRegistry().register(
            RealMachineMeasurement(
                "B-9", MeasurementQuantity.IV_CURVE, value=1e-3, unit="A",
                provenance_ref="p9", kind=OracleKind.COMMERCIAL_SOLVER_FIELD),
            RealMachineProvenance(ref="p9", foundry="Solver-Vendor"),
        ),
    )
    # 8b. 自研内核解同理必 raise
    _expect_raise(
        fails, "① 反向 A-2 失效：自研内核解竟被注册为 golden",
        lambda: RealMachineOracleRegistry().register(
            RealMachineMeasurement(
                "B-9", MeasurementQuantity.IV_CURVE, value=1e-3, unit="A",
                provenance_ref="p9", kind=OracleKind.SELF_KERNEL_SOLVED),
            RealMachineProvenance(ref="p9", foundry="LDA-T1"),
        ),
    )

    # 9. 反向 B：二级 golden 角色必 raise
    _expect_raise(
        fails, "① 反向 B 失效：secondary_golden 角色未被拦（机制未禁用）",
        lambda: guard_golden_eligibility(
            OracleKind.LITERATURE_MEASURED, role="secondary_golden"),
    )

    # ------------------------------------------------------------------
    # ② 外部 ORACLE 标定窗口（超窗必 raise）
    # ------------------------------------------------------------------
    anchor = "B-9"
    # 10. 反向 A：窗口表为准空 ⇒ 声称已标定必 raise（未签字）
    _expect_raise(
        fails, "② W1 失效：无已签字窗口竟接受「已标定」声明",
        lambda: RealMachineOracleRegistry().register(
            RealMachineMeasurement(
                anchor, MeasurementQuantity.IV_CURVE, value=25.0, unit="mA",
                provenance_ref="p9",
                honest_tier=f"{CALIBRATED_TIER_PREFIX}[window={anchor}]"),
            RealMachineProvenance(ref="p9", foundry="X"),
        ),
    )

    try:
        # 注入一个**已签字**窗口（signer 为人类责任方 · 非 AI）
        SIGNED_CALIBRATION_WINDOWS[anchor] = CalibrationWindow(
            anchor_id=anchor, quantity=MeasurementQuantity.IV_CURVE,
            lo=20.0, hi=30.0, signer="杜玉河", signed_date="2026-09-23",
            source_ref="external-oracle://DEVSIM@<provenance-ref>",
            note="smoke 注入窗口（仅测契约，非真实标定）",
        )
        w = SIGNED_CALIBRATION_WINDOWS[anchor]

        # 11. 反向 B：超窗必 raise
        _expect_raise(
            fails, "② W5 失效（**超窗**）：窗外的「已标定」声明竟被接受",
            lambda: RealMachineOracleRegistry().register(
                RealMachineMeasurement(
                    anchor, MeasurementQuantity.IV_CURVE, value=99.0, unit="mA",
                    provenance_ref="p9",
                    honest_tier=f"{CALIBRATED_TIER_PREFIX}[window={anchor}]"),
                RealMachineProvenance(ref="p9", foundry="X"),
            ),
        )

        # 12. 正向（合法必过）：窗内注册成功且值可回读
        reg = RealMachineOracleRegistry()
        try:
            reg.register(
                RealMachineMeasurement(
                    anchor, MeasurementQuantity.IV_CURVE, value=25.0, unit="mA",
                    provenance_ref="p9",
                    honest_tier=f"{CALIBRATED_TIER_PREFIX}[window={anchor}]"),
                RealMachineProvenance(ref="p9", foundry="X"),
            )
        except OracleGuardError as e:
            fails.append(f"② 正向失败（窗内竟被拦）：{e}")
        else:
            got = reg.get(anchor)
            if got is None or got.value != 25.0:
                fails.append("② 正向失败：窗内注册后值不可回读")
            if not reg.get(anchor).honest_tier.startswith(CALIBRATED_TIER_PREFIX):
                fails.append("② 正向失败：honest_tier 未随注册保留")

        # 12b. W2 量不一致必 raise
        _expect_raise(
            fails, "② W2 失效：标定窗口量与注册量不符未被拦",
            lambda: RealMachineOracleRegistry().register(
                RealMachineMeasurement(
                    anchor, MeasurementQuantity.CV_CURVE, value=25.0, unit="pF",
                    provenance_ref="p9",
                    honest_tier=f"{CALIBRATED_TIER_PREFIX}[window={anchor}]"),
                RealMachineProvenance(ref="p9", foundry="X"),
            ),
        )

        # 12c. W3 无人类签字人必 raise
        SIGNED_CALIBRATION_WINDOWS[anchor] = CalibrationWindow(
            anchor_id=anchor, quantity=MeasurementQuantity.IV_CURVE,
            lo=20.0, hi=30.0, signer="   ", signed_date="2026-09-23",
            source_ref="external-oracle://x",
        )
        _expect_raise(
            fails, "② W3 失效：无签字人的窗口仍被接受（AI 代签风险）",
            lambda: RealMachineOracleRegistry().register(
                RealMachineMeasurement(
                    anchor, MeasurementQuantity.IV_CURVE, value=25.0, unit="mA",
                    provenance_ref="p9",
                    honest_tier=f"{CALIBRATED_TIER_PREFIX}[window={anchor}]"),
                RealMachineProvenance(ref="p9", foundry="X"),
            ),
        )
        _ = w  # 注入对象已被 12c 覆盖，保留引用仅为可读性
    finally:
        # 恢复空表现状（本 smoke 不得改变锁死档事实）
        SIGNED_CALIBRATION_WINDOWS.clear()

    # 13. 诚实默认：未声称标定 ⇒ 放行（不因窗口表空而被误拦）
    try:
        RealMachineOracleRegistry().register(
            RealMachineMeasurement("B-10", MeasurementQuantity.IV_CURVE,
                                   value=1e-6, unit="A", provenance_ref="p10"),
            RealMachineProvenance(ref="p10", foundry="X"),
        )
    except OracleGuardError as e:
        fails.append(f"② 诚实默认失败：未声称标定却被拦 - {e}")

    # 14. 现状：窗口表空 · 二级 golden 禁用
    if SIGNED_CALIBRATION_WINDOWS:
        fails.append("② 现状失真：SIGNED_CALIBRATION_WINDOWS 应为空（④ 路径未启用）")
    if SECONDARY_GOLDEN_ALLOWED:
        fails.append("① 现状失真：SECONDARY_GOLDEN_ALLOWED 应为 False")

    if fails:
        print("FAIL")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS · 真机 ORACLE 契约骨架自洽"
          "（C1-C5 + G1/C4/C5/G2 + W1-W5 + ① 守卫生效，零真实数据）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
