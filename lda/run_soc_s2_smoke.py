# -*- coding: utf-8 -*-
"""S2 集成度判据 smoke（光子计算 SoC 征程）· 覆盖 C2/C3/C6/C8/C9 + G2/G3/G5 功能。

判据定义见 `docs/LDA_光子计算SOC征程_架构定义v1_2026-10-09.md` §6。
本 smoke 机器核验：
  · C2：设计含 ≥ N 个 per-MZI 驱动器；
  · C3：设计含 ≥ N 个 TIA；
  · G2：理想 DAC/ADC 量化确定性 + 功能级驱动链路可运行；
  · C6：标定状态机实例 + 网格可辨识性（identifiability_report）通过；
  · C8：同一份 GDS 含 ≥3 层（光子 SI + 电子 METAL + 热 HEATER）；
  · C9：无物理锚时标定终态 BLOCKED_NO_ANCHOR，can_claim_calibrated=False。

红线：不输出能效数字；不宣称已物理校准；所有判定为确定性机器断言。
返回 dict；任何 assert 失败即抛异常（CI 判 FAIL）。
"""
from __future__ import annotations

from typing import Any, Dict

from lda_l2.eic_functional import (
    soc_eic_array, ideal_dac, ideal_adc, DriverFunctional,
)
from lda_l2.soc_calibration import soc_calibration_verify
from lda_l2.soc_gds_assemble import build_minimal_soc_demo
from lda_l2 import gds_export as gx


def run_soc_s2_smoke(N: int = 16) -> Dict[str, Any]:
    # ---- C2 / C3 / G2：电子外设阵列 ----
    arr = soc_eic_array(N)
    assert arr["n_drivers"] >= N, "C2 FAIL: 驱动器数 %d < N=%d" % (arr["n_drivers"], N)
    assert arr["n_tias"] >= N, "C3 FAIL: TIA 数 %d < N=%d" % (arr["n_tias"], N)

    # ---- G2：理想 DAC/ADC 确定性 ----
    d = DriverFunctional()
    v0, v1 = ideal_dac(0), ideal_dac(1)
    assert v1 > v0, "G2 FAIL: 理想 DAC 单调性"
    code = ideal_adc(d.apply(ideal_dac(10, dac_bits=d.dac_bits)), adc_bits=8)
    assert 0 <= code < 256, "G2 FAIL: 理想 ADC 范围"

    # ---- C6 / C9：标定状态机（无锚 ⇒ BLOCKED，不可宣称 calibrated）----
    cal = soc_calibration_verify(N, anchor=None)
    assert cal["identifiable"] is True, "C6 FAIL: 网格不可辨识（N=%d）" % N
    assert cal["cal_state"] == "BLOCKED_NO_ANCHOR", \
        "C9 FAIL: 无锚应 BLOCKED，收到 %s" % cal["cal_state"]
    assert cal["can_claim_calibrated"] is False, \
        "C9 FAIL: 无锚不得宣称 calibrated"

    # ---- C8：多层光电 GDS 协同 ----
    demo = build_minimal_soc_demo(N)
    assert demo["n_layers"] >= 3, "C8 FAIL: 层协同数 %d < 3" % demo["n_layers"]
    assert gx.LIB_LAYER_SI in demo["layers"], "C8 FAIL: 缺光子层 SI"
    assert gx.LIB_LAYER_METAL in demo["layers"], "C8 FAIL: 缺电子层 METAL"
    assert gx.LIB_LAYER_HEATER in demo["layers"], "C8 FAIL: 缺热相移层 HEATER"

    return {
        "N": N,
        "n_drivers": arr["n_drivers"],
        "n_tias": arr["n_tias"],
        "dac_monotonic": v1 > v0,
        "identifiable": cal["identifiable"],
        "cal_state_no_anchor": cal["cal_state"],
        "can_claim_no_anchor": cal["can_claim_calibrated"],
        "vpi_rel_err": cal["vpi_rel_err"],
        "gds_n_layers": demo["n_layers"],
        "gds_layers": demo["layers"],
        "pass": True,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_soc_s2_smoke(), indent=2, ensure_ascii=False))
