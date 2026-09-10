"""真机 ORACLE 接入契约自洽 smoke（2026-09-11）。

零真实数据：仅验证 C1–C5 契约结构与 G1/C4/C5/G2 守卫**系统能力**已研发完整，
不接任何真实 foundry / 流片真值，不构成假绿。

验证项：
  1. 契约模块可导入、REAL_MACHINE_ANCHOR_BINDING 为空（锁死档现状）
  2. REAL_MACHINE_ORACLE.is_empty == True（零真值）
  3. 无 provenance 注册 → OracleGuardError（C5 守卫）
  4. T1-B 输出反向注册 → OracleGuardError（G1/C4 标定单向）
  5. assert_t1_kernel_sovereign() 对 DEVSIM（B 级）不抛（G2 主权钩子）
"""
import sys

sys.path.insert(0, "lda")

from lda_harness.real_machine_oracle import (
    REAL_MACHINE_ANCHOR_BINDING,
    REAL_MACHINE_ORACLE,
    OracleGuardError,
    RealMachineMeasurement,
    RealMachineProvenance,
    MeasurementQuantity,
    assert_t1_kernel_sovereign,
)


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

    if fails:
        print("FAIL")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS · 真机 ORACLE 契约骨架自洽（C1-C5 + G1/C4/C5/G2 守卫生效，零真实数据）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
