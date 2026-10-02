"""LDA · 光子计算芯片 M2 验证 smoke（光计算征程 · 性能爬坡里程碑）。

验证目标（M2 把平台从「能算」推向「算得准」的四块新增能力）：
  ① 相位量化：相移器有限比特分辨率模型 → 网格传递矩阵保真度随比特退化；
  ② 相位标定闭环：Vπ·L 物理定律 + π/2 探针反估 Vπ → 回收 Vπ 增益误差；
  ③ 非线性激活：检测后（电子/光电域）relu/sigmoid/tanh，平台既往无激活模块；
  ④ 端到端计算精度锚：两层网络「光学 MVM→探测→激活」与 numpy 同构参考管线比对，
     报告 MAC 误差与分类精度；全精度逐位一致、量化/标定误差致退化、标定闭环回收。

纪律（与全仓血案一致）：
- name-first check(name, ok, detail)：名字在前，写反即假绿防治（血案 20）；
- 每条判据带**反向可证伪**（退化存在 / 回收存在 / 定义成立），真变更或 bug 会拉红；
- 不借 Meep/Tidy3D（A 级禁）；LLM 不进判决路径；
- 自身须 ∈ CORE_SMOKES（自食其规则，覆盖网关守护）。

实测 <1s（纯 numpy），进 CI core 无压力。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

CHECKS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")
    sys.stdout.flush()


def main() -> int:
    import inspect

    import numpy as np
    from lda_l2.photonic_compute import (
        verify_photonic_compute_m2,
        photonic_activation,
        mesh_transfer_with_model,
        VPI_L_VMM,
    )
    from lda_l2.mzi_mesh_matmul import voltage_from_phase, VPI_UNIT_ARM_MM

    r = verify_photonic_compute_m2()

    # ---- ① 相位量化：退化存在 + 高位宽逼近机器精度 ----
    q = {qd["n_bits"]: qd["fidelity"] for qd in r["quantization_sweep"]}
    fid_1 = q[1]
    fid_12 = q[12]
    # 反向：若量化是 no-op（bug），1bit 与 12bit 应相等 → 严格小于才证明模型非恒真
    check("M2a 量化：1-bit 保真 < 12-bit 保真（退化存在，非恒真）",
          fid_1 < fid_12, f"fid(1)={fid_1:.6f} < fid(12)={fid_12:.6f}")
    check("M2a 量化：12-bit 保真 ≥ 0.999（高位宽逼近机器精度）",
          fid_12 >= 0.999, f"fid(12)={fid_12:.9f}")
    # 统计性断言：更多比特 → 平均保真显著更高（期望意义；量化 no-op bug 会让
    # 各比特均值齐平 ⇒ 被下式拉红）。单矩阵逐点未必单调（量化栅格相对相位），故用均值。
    rng = np.random.default_rng(99)
    bits_list = (1, 2, 4, 8, 12)
    means = {}
    for nb in bits_list:
        fs = []
        for _ in range(30):
            Z = (rng.standard_normal((6, 6)) + 1j * rng.standard_normal((6, 6)))
            Uu, _ = np.linalg.qr(Z)
            _, _, _, ff = mesh_transfer_with_model(Uu, n_bits=nb)
            fs.append(ff)
        means[nb] = float(np.mean(fs))
    check("M2a 量化：平均保真随比特上升（30 随机酉均值，12-bit 比 1-bit 高 >0.1）",
          means[12] > means[1] + 0.1,
          " ".join(f"{k}:{means[k]:.4f}" for k in bits_list))

    # ---- ② 相位标定闭环：回收存在 + 优于未标定 ----
    cal = r["calibration"]
    # 反向：若标定被跳过/无效（bug），fid_cal 应 == fid_no_cal → 严格大于才证明闭环生效
    check("M2b 标定：闭环回收 Vπ 增益误差（fid_cal ≥ 0.999）",
          cal["fid_cal"] >= 0.999, f"fid_cal={cal['fid_cal']:.9f}")
    check("M2b 标定：标定后保真 > 未标定保真（闭环优于无）",
          cal["fid_cal"] > cal["fid_no_cal"],
          f"{cal['fid_cal']:.6f} > {cal['fid_no_cal']:.6f}")

    # ---- ③ 非线性激活：定义成立（若实现被误改会拉红）----
    check("M2c 激活：ReLU(-1)=0（负值截断）",
          abs(photonic_activation(-1.0, "relu") - 0.0) < 1e-12,
          f"={photonic_activation(-1.0,'relu'):.6f}")
    check("M2c 激活：ReLU(3)=3（正值直通）",
          abs(photonic_activation(3.0, "relu") - 3.0) < 1e-12,
          f"={photonic_activation(3.0,'relu'):.6f}")
    check("M2c 激活：Sigmoid(0)=0.5（中点）",
          abs(photonic_activation(0.0, "sigmoid") - 0.5) < 1e-12,
          f"={photonic_activation(0.0,'sigmoid'):.6f}")
    check("M2c 激活：Tanh(0)=0",
          abs(photonic_activation(0.0, "tanh")) < 1e-12,
          f"={photonic_activation(0.0,'tanh'):.6f}")

    # ---- ④ 端到端计算精度锚 ----
    full = r["e2e_full"]
    q2 = r["e2e_q2"]
    no_cal = r["e2e_vpi_no_cal"]
    cal_e = r["e2e_vpi_cal"]
    # 全精度光学实现须与 numpy 参考管线逐位一致（MAC 误差≈机器精度、分类 100%）
    check("M2d 端到端：全精度分类精度 = 100%（光学 == numpy 参考）",
          abs(full["accuracy"] - 1.0) < 1e-12, f"acc={full['accuracy']:.6f}")
    check("M2d 端到端：全精度最大 MAC 误差 < 1e-10（逐位一致）",
          full["max_mac_err"] < 1e-10, f"mac_err={full['max_mac_err']:.3e}")
    # 反向：2-bit 量化须致精度退化（若量化未生效会恒 100% → 假绿）
    check("M2d 端到端：2-bit 量化致精度退化（acc < 100%）",
          q2["accuracy"] < 1.0, f"acc={q2['accuracy']*100:.1f}%")
    # 反向：标定闭环须把 Vπ 误差场景精度回收（若标定无效会停在未标定水平）
    check("M2d 端到端：Vπ+5% 标定后精度 > 未标定精度",
          cal_e["accuracy"] > no_cal["accuracy"],
          f"{cal_e['accuracy']*100:.1f}% > {no_cal['accuracy']*100:.1f}%")

    # ---- ⑤ Vπ·L 单位口径守护（v0.9.183 补：清死 import 时改「接线」而非删除）----
    # 🔴 血案（c4965be）：Vπ·L 单位统一提交只改了 `mzi_mesh_matmul.voltage_from_phase`
    # 的形参名（vpi_l_v_cm → vpi_l_v_mm）与默认值（V·cm → V·mm），**漏改调用方**
    # `photonic_compute.py` ⇒ 该模块自 c4965be 起 `TypeError` 全程不可运行，而本 smoke
    # 当时只 `import VPI_L_V_CM` **从未使用**（死 import）⇒ 口径裂开无任何判据看守。
    # 故此处把死 import 变成真判据：单位口径 + 关键字契约（后者是该类断裂的通用防线）。
    _sig = inspect.signature(voltage_from_phase)
    check("M2e Vπ·L 关键字契约：voltage_from_phase 只收 vpi_l_v_mm（V·mm 单一真值口径）",
          "vpi_l_v_mm" in _sig.parameters and "vpi_l_v_cm" not in _sig.parameters,
          f"参数={list(_sig.parameters)}")
    check("M2e Vπ·L 真值源：VPI_L_VMM == 250.0（V·mm，≡ 25 V·cm 同一物理量）",
          abs(VPI_L_VMM - 250.0) < 1e-12, f"VPI_L_VMM={VPI_L_VMM}")
    # 物理量不变锚：φ=π 时驱动电压 = π·250/(π·10) = 25 V（L_mm=10 ⇒ 1 cm 臂）
    _v_pi = voltage_from_phase(math.pi, vpi_l_v_mm=VPI_L_VMM)
    check("M2e Vπ·L 物理量锚：φ=π @ 250 V·mm ⇒ 25.0 V（单位切换不改物理量）",
          abs(_v_pi - 25.0) < 1e-12, f"V(π)={_v_pi:.12g} V")
    # 反向：把 V·cm 口径的数值（25.0）当 V·mm 传 ⇒ 得 2.5 V（10× 静默错单位）。
    # 若有人把口径退回 V·cm 而不改单位，本判据在此处即红。
    _v_cm_misuse = voltage_from_phase(math.pi, vpi_l_v_mm=25.0)
    check("M2e Vπ·L 反向：V·cm 数值当 V·mm 传 ⇒ 10× 偏差（错单位必被本判据抓）",
          abs(_v_cm_misuse - 2.5) < 1e-12 and abs(_v_cm_misuse - _v_pi) > 1.0,
          f"V(π,V·cm误用)={_v_cm_misuse:.6g} V vs 正确 {_v_pi:.6g} V")
    # 🔴 回译恒等式（本判据直接看守「归一闪射」）：设备回译 φ=π·V/Vπ 中 Vπ = Vπ·L/L_arm。
    # 若消费方忘了除以臂长（c4965be 血案），该式会给出 φ/10 ⇒ 标定闭环失效 ⇒ 此判据红。
    _rt_bad = []
    for _phi in (0.3, 1.0, math.pi / 2.0, math.pi):
        _V = voltage_from_phase(_phi, vpi_l_v_mm=VPI_L_VMM)
        _phi_back = math.pi * _V / (VPI_L_VMM / VPI_UNIT_ARM_MM)
        if abs(_phi_back - _phi) > 1e-12:
            _rt_bad.append((_phi, _phi_back))
    check("M2e 回译恒等式：π·V(φ)/(Vπ·L/L_arm) == φ（臂长归一两侧同步，防 10× 闪射）",
          not _rt_bad, f"bad={_rt_bad[:2]} · L_arm={VPI_UNIT_ARM_MM}")

    # ---- 自食其规则：本 smoke 须 ∈ CORE_SMOKES（覆盖网关守护）----
    try:
        from run_ci_regression import CORE_SMOKES
        in_core = os.path.basename(__file__) in CORE_SMOKES
    except Exception as ex:  # noqa: BLE001
        in_core = False
        print(f"   （无法读取 CORE_SMOKES：{ex}）")
    check("L12 本 smoke 自身在 CORE_SMOKES 内（自食其规则）",
          in_core, f"{os.path.basename(__file__)} ∈ CORE_SMOKES={in_core}")

    rc = 0
    for name, ok, _ in CHECKS:
        if not ok:
            rc = 1
    print("-" * 70)
    npass = sum(1 for _, ok, _ in CHECKS if ok)
    print(f"M2 smoke 结果：{npass}/{len(CHECKS)} 通过  rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
