"""B5/B7 回退下限（rollback lower bound）反向护栏。

B5(Y 分支 50/50 分束插入损耗) 与 B7(波导交叉串扰) 是 ORACLE 依赖锚
（Meep/Tidy3D 真场级 → numpy 离线近似 → 设计守则锚下限）。本 smoke 守卫
「ORACLE 全不可用时回退到设计守则下限」这条**诚实降级下限**不被静默漂移：

  - 下限须**精确等于**设计守则锚 (B5=3.0 dB, B7=-40.0 dB)，不得回落 0/None/错误数；
  - 下限须**诚实标注** source="design-anchor"（不得伪装成 physical-law / 真场级）；
  - ORACLE 在场时须**正确绕开下限**（反向护栏：smoke 会响，证明测的是回退分支而非常量）；
  - 离线近似（CI 主路径）仍产出**几何相关真实值**（B5>3.0 单调、B7 有限负 dB）。

铁律：测生产代码（lda_harness.golden）非内嵌副本；反向测试会响；<5s 无重依赖 ⇒ 入 CORE 不得豁免。
"""
import math
import sys


def _check(name, cond, detail=""):
    status = "[PASS]" if cond else "[FAIL]"
    print(f"  {status} {name}" + (f"  ({detail})" if detail else ""))
    return cond


def main():
    try:
        from lda_harness import golden
        from lda_harness.oracle_field import resolve_field_oracle
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] import lda_harness.golden: {e}")
        return 1

    params_b5 = dict(w_core=0.5, h_core=0.22, n_si=3.48, n_clad=1.44,
                     wl=1.55, theta_deg=10.0)
    params_b7 = dict(w_core=0.5, h_core=0.22, n_si=3.48, n_clad=1.44,
                     wl=1.55, gap=0.2)

    ok = True
    orig = golden.resolve_field_oracle  # 保存，finally 恢复

    try:
        # --- [A] 离线主路径（CI 默认：无 Meep 子进程 → numpy 离线近似）---
        r5 = resolve_field_oracle("B5", params_b5)
        ok &= _check(
            "B5 离线近似路径可用 (numpy-overlap-offline)",
            r5 is not None and r5.get("source") == "numpy-overlap-offline"
            and isinstance(r5.get("value"), (int, float)),
            f"source={r5.get('source') if r5 else None} val={r5.get('value') if r5 else None}")
        if r5:
            # 几何相关：theta 增大 → 损耗单调增大（>3.0 理想下限）
            extra = 0.4 * (params_b5["theta_deg"] / 10.0) ** 2
            ok &= _check(
                "B5 离线值 = 3.0 + 0.4*(theta/10)^2 几何相关",
                abs(r5["value"] - (3.0 + extra)) < 1e-9,
                f"val={r5['value']:.4f} expect={3.0 + extra:.4f}")
        r7 = resolve_field_oracle("B7", params_b7)
        ok &= _check(
            "B7 离线近似路径可用 (numpy-fdtd-offline)",
            r7 is not None and r7.get("source") == "numpy-fdtd-offline"
            and isinstance(r7.get("value"), (int, float)),
            f"source={r7.get('source') if r7 else None} val={r7.get('value') if r7 else None}")
        if r7:
            # 串扰为负 dB 且有限（离线 FDTD 真场计算量级合理）
            ok &= _check(
                "B7 离线串扰为有限负 dB（合理量级）",
                math.isfinite(r7["value"]) and r7["value"] < 0,
                f"val={r7['value']:.3f} dB")

        # --- [B] 回退下限持有（全部 ORACLE 不可用 → resolve_field_oracle 返回 None）---
        golden.resolve_field_oracle = lambda bid, p: None
        v5 = golden.golden_value("B5", params_b5)
        ok &= _check(
            "B5 回退下限精确 = B5_DESIGN_ANCHOR (3.0 dB)",
            v5 == golden.B5_DESIGN_ANCHOR,
            f"val={v5} expect={golden.B5_DESIGN_ANCHOR}")
        v7 = golden.golden_value("B7", params_b7)
        ok &= _check(
            "B7 回退下限精确 = B7_DESIGN_ANCHOR (-40.0 dB)",
            v7 == golden.B7_DESIGN_ANCHOR,
            f"val={v7} expect={golden.B7_DESIGN_ANCHOR}")
        # 诚实标注：下限不得伪装成 physical-law / 真场级
        s5 = golden.golden_with_source("B5", params_b5)
        s7 = golden.golden_with_source("B7", params_b7)
        ok &= _check(
            "B5 回退须诚实标注 source=design-anchor",
            s5[1] == "design-anchor" and "ORACLE" in s5[2],
            f"source={s5[1]}")
        ok &= _check(
            "B7 回退须诚实标注 source=design-anchor",
            s7[1] == "design-anchor" and "ORACLE" in s7[2],
            f"source={s7[1]}")

        # --- [C] 反向护栏：下限不是「永远返回」的常量 —— ORACLE 在场须绕开下限 ---
        sentinel = {"value": 99.9, "source": "meep-fdtd", "note": "sentinel oracle"}
        golden.resolve_field_oracle = lambda bid, p: sentinel
        vs = golden.golden_value("B5", params_b5)
        ok &= _check(
            "反向护栏：ORACLE 在场时绕开下限 (B5=99.9)",
            vs == 99.9, f"val={vs}")
        ss = golden.golden_with_source("B5", params_b5)
        ok &= _check(
            "反向护栏：ORACLE 在场 source=meep-fdtd 非 design-anchor",
            ss[1] == "meep-fdtd", f"source={ss[1]}")
    finally:
        golden.resolve_field_oracle = orig  # 恢复生产代码原行为

    print("B5/B7 回退下限 smoke: " + ("ALL PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
