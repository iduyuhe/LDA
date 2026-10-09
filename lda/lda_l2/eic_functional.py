# -*- coding: utf-8 -*-
"""EIC 功能级模型（光子计算 SoC 征程 S2 · G2 补齐）· 理想 DAC/ADC + 标定 FSM 包装。

背景：`eic_behavioral.py` 只到「行为级」（一阶 RC 驱动 + 单极点 TIA）。本模块把 EIC
从行为级推进到「功能级」——在行为级之上叠加**理想数据转换器（DAC/ADC 量化器）**与
**标定有限状态机（FSM）**的功能结构，用于 SoC 整芯片协同设计的接口契约验证。

红线纪律（沿用 eic_behavioral + calibration_protocol）：
  · 仍不碰晶体管级（DAC/ADC 内部电路在红线外；本模块只建**理想量化器**接口）。
  · 零能效数字：复用 `eic_behavioral.assert_no_energy_metrics` 单一真值来源。
  · 标定：任何 calibrated 宣称必须绑定合格物理锚，否则 BLOCKED
    （`guard_calibration_requires_anchor`）。
  · 纯 numpy；LLM 不进判决路径；golden = 闭式物理律（理想量化器为确定性映射）。
"""
from __future__ import annotations

import numpy as np
from typing import Any, Dict, List, Optional

from lda_l2.eic_behavioral import (
    driver_step_rk4,
    tia_transimpedance_ohm,
    tia_bandwidth_hz,
    mzi_phase_from_voltage,
    eic_budget,
    TAU_DRIVER_S_DEFAULT,
    V_DD_DEFAULT,
    VPI_L_V_MM_DEFAULT,
    PS_ARM_UM_DEFAULT,
    R_F_OHM_DEFAULT,
    C_F_F_DEFAULT,
    DAC_BITS_DEFAULT,
    assert_no_energy_metrics,
)
from lda_l2.calibration_protocol import (
    CalibrationStateMachine,
    identifiability_report,
    project_calibration_state,
)


# ---------------------------------------------------------------------------
# 1) 理想数据转换器（功能级，非晶体管级）
# ---------------------------------------------------------------------------
def ideal_dac(code: int, dac_bits: int = DAC_BITS_DEFAULT,
              v_ref: float = V_DD_DEFAULT) -> float:
    """理想 DAC 量化器：码字 → 电压。v = code * v_ref / 2**dac_bits。"""
    if not (0 <= code < 2 ** dac_bits):
        raise ValueError("code %d 越界 [0, %d)" % (code, 2 ** dac_bits))
    return float(code) * v_ref / float(2 ** dac_bits)


def ideal_adc(voltage: float, adc_bits: int = 8,
              v_ref: float = V_DD_DEFAULT) -> int:
    """理想 ADC 流水线（功能级）：电压 → 码字（量化 + 饱和裁剪）。"""
    n = 2 ** adc_bits
    code = int(np.clip(round(voltage / v_ref * (n - 1)), 0, n - 1))
    return int(code)


# ---------------------------------------------------------------------------
# 2) per-MZI 功能级驱动 + TIA
# ---------------------------------------------------------------------------
class DriverFunctional:
    """per-MZI 驱动（功能级）：理想 DAC 码字 →（RC 驱动阶跃）→ 施加电压 → 相位。"""

    def __init__(self, dac_bits: int = DAC_BITS_DEFAULT,
                 v_ref: float = V_DD_DEFAULT,
                 tau_s: float = TAU_DRIVER_S_DEFAULT):
        self.dac_bits = dac_bits
        self.v_ref = v_ref
        self.tau_s = tau_s

    def apply(self, code: int, settle_frac: float = 8.0, n_steps: int = 64) -> float:
        v_dac = ideal_dac(code, self.dac_bits, self.v_ref)
        return driver_step_rk4(settle_frac * self.tau_s, tau_s=self.tau_s,
                               v_dd=v_dac, n_steps=n_steps)

    def phase_from_code(self, code: int) -> float:
        v = self.apply(code)
        return mzi_phase_from_voltage(v, VPI_L_V_MM_DEFAULT, PS_ARM_UM_DEFAULT)


class TiaFunctional:
    """per-MZI TIA（功能级）：光电流 → 输出电压（单极点跨阻）。"""

    def __init__(self, r_f_ohm: float = R_F_OHM_DEFAULT,
                 c_f_f: float = C_F_F_DEFAULT):
        self.r_f = r_f_ohm
        self.c_f = c_f_f

    def transfer(self, i_phot_ua: float, f_hz: float = 1e9) -> float:
        z = tia_transimpedance_ohm(f_hz, self.r_f, self.c_f)
        return float(i_phot_ua) * 1e-6 * z

    def bandwidth_hz(self) -> float:
        return tia_bandwidth_hz(self.r_f, self.c_f)


# ---------------------------------------------------------------------------
# 3) SoC 标定 FSM（功能级包装 CalibrationStateMachine）
# ---------------------------------------------------------------------------
def soc_calibration_fsm(N: int, mode: str = "complex",
                        anchor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """SoC 标定 FSM 驱动：复用 `calibration_protocol.project_calibration_state`。

    红线：无物理锚 ⇒ 终态 BLOCKED_NO_ANCHOR，can_claim_calibrated=False。
    返回状态机终态 + 可宣称判定 + 可辨识性（C6/C9 机器核验来源）。
    """
    rep = project_calibration_state(
        N, mode=mode, anchor=anchor,
        closed_loop_converged=True, drift_checked=True)
    return {
        "state": rep.get("state", "UNKNOWN"),
        "can_claim_calibrated": bool(rep.get("can_claim_calibrated", False)),
        "identifiable": bool(rep.get("identifiable", False)),
        "rank": int(rep.get("rank", 0)),
    }


# ---------------------------------------------------------------------------
# 4) SoC 电子外设阵列（用于 C2/C3 计数与预算）
# ---------------------------------------------------------------------------
def soc_eic_array(n_mzi: int, dac_bits: int = DAC_BITS_DEFAULT) -> Dict[str, Any]:
    """构造 N 个 per-MZI 驱动 + ADC + TIA 的功能级阵列（C2/C3 计数与预算）。"""
    drivers = [DriverFunctional(dac_bits=dac_bits) for _ in range(n_mzi)]
    tias = [TiaFunctional() for _ in range(n_mzi)]
    adcs = [ideal_adc for _ in range(n_mzi)]
    budget = eic_budget(
        n_mzi, tau_s=TAU_DRIVER_S_DEFAULT, v_dd=2.0 * V_DD_DEFAULT,
        dac_bits=dac_bits, vpi_l_v_mm=VPI_L_V_MM_DEFAULT,
        arm_um=PS_ARM_UM_DEFAULT, r_f_ohm=R_F_OHM_DEFAULT, c_f_f=C_F_F_DEFAULT)
    out: Dict[str, Any] = {
        "n_mzi": n_mzi,
        "n_drivers": len(drivers),
        "n_tias": len(tias),
        "n_adcs": len(adcs),
        "phase_resolution_rad": budget["phase_resolution_rad"],
        "tia_bandwidth_hz": budget["tia_bandwidth_hz"],
    }
    assert_no_energy_metrics(out)
    return out


if __name__ == "__main__":
    print("=== EIC 功能级自检 ===")
    for N in (8, 16, 64):
        arr = soc_eic_array(N)
        print("  N=%d  驱动=%d  TIA=%d  ADC=%d  相位分辨率=%.4f rad"
              % (N, arr["n_drivers"], arr["n_tias"], arr["n_adcs"],
                 arr["phase_resolution_rad"]))
    d = DriverFunctional()
    print("  ideal_dac(0)=%.4f  ideal_dac(1)=%.4f  单调=%s"
          % (ideal_dac(0), ideal_dac(1), ideal_dac(1) > ideal_dac(0)))
    cal = soc_calibration_fsm(16, anchor=None)
    print("  无锚标定终态=%s  可宣称=%s  可辨识=%s"
          % (cal["state"], cal["can_claim_calibrated"], cal["identifiable"]))
