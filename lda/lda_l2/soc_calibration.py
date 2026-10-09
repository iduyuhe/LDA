# -*- coding: utf-8 -*-
"""SoC 标定对接（光子计算 SoC 征程 S2 · G5 冷态部分）。

把 `photonic_electronic_cosim.eo_calibration_loop`（读回闭环反估 Vπ）与
`calibration_protocol.CalibrationStateMachine`（流程状态机）对接，形成 SoC 冷态
标定验证链。证明：
  · C6：网格可辨识性验证（identifiability_report）通过 + 状态机实例存在；
  · C9：任何 calibrated 宣称必须绑定合格物理锚，无锚即 BLOCKED_NO_ANCHOR。

红线：本模块只做**设计层标定流程交付**，不宣称已物理校准（真实标定须 foundry
工艺角 / 实测锚，属 B 类外部）。无锚 ⇒ 终态 BLOCKED，can_claim=False。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from lda_l2.photonic_electronic_cosim import eo_calibration_loop
from lda_l2.calibration_protocol import (
    identifiability_report,
    project_calibration_state,
)


def soc_calibration_verify(N: int, mode: str = "complex",
                           anchor: Optional[Dict[str, Any]] = None,
                           dac_bits: int = 6, **loop_kw) -> Dict[str, Any]:
    """S2/G5 冷态标定验证。

    1) identifiability_report(N) 验证网格可辨识性（C6 来源）；
    2) eo_calibration_loop 反估真实 Vπ（读回闭环，设计层交付）；
    3) CalibrationStateMachine 走流程；无锚 ⇒ BLOCKED_NO_ANCHOR（C9 来源）。
    """
    ident = identifiability_report(N, mode=mode)
    loop = eo_calibration_loop(dac_bits=dac_bits, **loop_kw)
    cal = project_calibration_state(
        N, mode=mode, anchor=anchor,
        closed_loop_converged=True, drift_checked=True)
    return {
        "N": int(N),
        "identifiable": bool(ident["identifiable"]),
        "rank": int(ident["rank"]),
        "vpi_real": float(loop["vpi_real"]),
        "vpi_est": float(loop["vpi_est"]),
        "vpi_rel_err": float(loop["rel_err"]),
        "cal_state": cal.get("state", "UNKNOWN"),
        "can_claim_calibrated": bool(cal.get("can_claim_calibrated", False)),
    }


if __name__ == "__main__":
    print("=== SoC 冷态标定验证（无锚）===")
    r = soc_calibration_verify(16, anchor=None)
    print("  可辨识=%s 秩=%d Vπ真实=%.4f Vπ估计=%.4f 相对误差=%.3e"
          % (r["identifiable"], r["rank"], r["vpi_real"], r["vpi_est"], r["vpi_rel_err"]))
    print("  标定终态=%s 可宣称calibrated=%s" % (r["cal_state"], r["can_claim_calibrated"]))
