# -*- coding: utf-8 -*-
"""S3 集成度判据 smoke（光子计算 SoC 征程）· 覆盖 C1/C4/C5/C7/C8 + 复用 S2 的 C2/C3/C6/C9。

判据定义见 `docs/LDA_光子计算SOC征程_架构定义v1_2026-10-09.md` §6。
本 smoke 机器核验端到端 SoC 设计包装配 + 全部 C1–C9 集成度判据：
  · C1：N×N 主权 P&R 光子核（build_nxn_mzi_mesh）+ DRC/LVS 全绿（真算 MZI 数 = N(N−1)/2）；
  · C2：≥ N 个 per-MZI 驱动器（soc_eic_array）；
  · C3：≥ N 个 TIA；
  · C4：GratingCoupler ≥ 2 + cpo_optical_io_metrics 有效（真实模块 GratingCoupler / cpo_engines）；
  · C5：封装光源 G5 check_external_laser_bypassable() == BYPASSABLE；
  · C6：标定状态机 + 网格可辨识性（identifiability_report）通过；
  · C7：端到端光计算核推理 vs 数字 golden（numpy）落差 < 量化容差 + 分类精度 = 1.0；
  · C8：同一份主权 GDS（光子层 SI + 电子层 METAL + 热层 HEATER）协同 ≥3 层；
  · C9：无物理锚 ⇒ BLOCKED_NO_ANCHOR，can_claim_calibrated=False。

所有子系统均复用平台**真实模块**（无占位造假）；所有性能/精度数字由真实模块现算。
红线纪律（沿用底层）：不报能效；不宣称已物理校准；判据必须真算。
返回 dict；任何 assert 失败即抛异常（CI 判 FAIL）。
"""
from __future__ import annotations

from typing import Any, Dict

from lda_l2.soc_design_package import build_soc_design_package


def run_soc_s3_smoke(N: int = 16, dac_bits: int = 16,
                     seed: int = 20261009) -> Dict[str, Any]:
    rep = build_soc_design_package(N=N, dac_bits=dac_bits, seed=seed)
    crit = rep["criteria"]

    # ---- C1：主权光子核 + DRC/LVS ----
    c1 = crit["c1"]
    assert c1["n_mzi"] == c1["expected_n_mzi"], \
        "C1 FAIL: MZI 数 %d ≠ 期望 %d" % (c1["n_mzi"], c1["expected_n_mzi"])
    assert c1["drc"] == "PASS", "C1 FAIL: DRC=%s" % c1["drc"]
    assert c1["lvs"] in ("ACCEPT", "PASS"), "C1 FAIL: LVS=%s" % c1["lvs"]

    # ---- C2 / C3：电子外设 ----
    assert crit["c2"]["pass"], "C2 FAIL: 驱动器数不足 N=%d" % N
    assert crit["c3"]["pass"], "C3 FAIL: TIA 数不足 N=%d" % N

    # ---- C4：光 IO（真实 GratingCoupler + cpo 引擎）----
    c4 = crit["c4"]
    assert c4["n_io_ports"] >= 2, "C4 FAIL: IO 端口 %d < 2" % c4["n_io_ports"]
    assert c4["n_gratings_class"] >= 2, "C4 FAIL: GratingCoupler 类数 %d < 2" % c4["n_gratings_class"]
    assert c4["cpo_valid"], "C4 FAIL: cpo_optical_io_metrics 无效"

    # ---- C5：封装光源 G5 网关 ----
    assert crit["c5"]["status"] == "BYPASSABLE", \
        "C5 FAIL: 封装光源状态 %s" % crit["c5"]["status"]

    # ---- C6：标定环可辨识 ----
    assert crit["c6"]["identifiable"] is True, "C6 FAIL: 网格不可辨识（N=%d）" % N

    # ---- C7：端到端推理 vs 数字 golden ----
    c7 = crit["c7"]
    assert c7["mvm_rel_err"] < c7["quant_tol"], \
        "C7 FAIL: MVM 相对误差 %.3e ≥ 量化容差 %.3e" % (c7["mvm_rel_err"], c7["quant_tol"])
    assert c7["classifier_accuracy"] >= 1.0 - 1e-9, \
        "C7 FAIL: 分类精度 %.6f < 1.0" % c7["classifier_accuracy"]

    # ---- C8：同一份主权 GDS 多层协同 ----
    c8 = crit["c8"]
    assert c8["n_layers"] >= 3, "C8 FAIL: GDS 层数 %d < 3" % c8["n_layers"]
    assert c8["pass"], "C8 FAIL: GDS 缺 SI/METAL 协同层"

    # ---- C9：标定红线（无锚不得宣称 calibrated）----
    c9 = crit["c9"]
    assert c9["cal_state"] == "BLOCKED_NO_ANCHOR", \
        "C9 FAIL: 无锚应 BLOCKED，收到 %s" % c9["cal_state"]
    assert c9["can_claim_calibrated"] is False, "C9 FAIL: 无锚不得宣称 calibrated"

    # ---- 总门 ----
    assert rep["all_pass"] is True, "S3 FAIL: 存在未通过判据 %s" % \
        [k for k, v in crit.items() if not v["pass"]]

    return {
        "N": N,
        "dac_bits": dac_bits,
        "n_mzi": c1["n_mzi"],
        "drc": c1["drc"],
        "lvs": c1["lvs"],
        "n_io_ports": c4["n_io_ports"],
        "cpo_il_db": rep["subsystems"]["io"].get("per_channel_il_db"),
        "mvm_rel_err": c7["mvm_rel_err"],
        "quant_tol": c7["quant_tol"],
        "classifier_accuracy": c7["classifier_accuracy"],
        "gds_n_layers": c8["n_layers"],
        "gds_layers": c8["layers"],
        "cal_state_no_anchor": c9["cal_state"],
        "all_pass": True,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_soc_s3_smoke(), indent=2, ensure_ascii=False))
