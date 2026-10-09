# -*- coding: utf-8 -*-
"""S4 规模爬升 smoke（光子计算 SoC 征程 · G6：N 16→32→64→128）· 复用 S3 的 C1–C9。

判据定义见 `docs/LDA_光子计算SOC征程_架构定义v1_2026-10-09.md` §6/§9。
本 smoke 机器核验『规模爬升后集成度不回归』：
  · 在目标规模 N（默认 64，即相对基线 16 做 4× 爬升）装配真实 N×N SoC 设计包；
  · 复用 S3 全链路 C1–C9（含 C1 主权 P&R + DRC/LVS 全绿、C7 端到端推理 vs 数字 golden、
    C9 无锚 BLOCKED 红线）；
  · 额外规模债照妖镜判据：n_unresolved_crossings == 0（所有交叉必须可异层化解，不得有
    2 层物理不可解残留）；n_mzi == N(N−1)/2（真算 MZI 数随规模单调增长）。

所有数字由真实模块现算（无占位造假）；红线纪律沿用底层（不报能效 / 不宣称已物理校准）。
返回 dict；任何 assert 失败即抛异常（CI 判 FAIL）。
"""
from __future__ import annotations

import os

from typing import Any, Dict

from lda_l2.soc_design_package import build_soc_design_package


def run_soc_s4_smoke(N: int = 64, dac_bits: int = 16,
                     seed: int = 20261009) -> Dict[str, Any]:
    rep = build_soc_design_package(N=N, dac_bits=dac_bits, seed=seed)
    crit = rep["criteria"]

    # ---- C1：主权光子核 + DRC/LVS（含规模债字段）----
    c1 = crit["c1"]
    assert c1["n_mzi"] == c1["expected_n_mzi"], \
        "C1 FAIL: MZI 数 %d ≠ 期望 %d（N=%d）" % (c1["n_mzi"], c1["expected_n_mzi"], N)
    assert c1["drc"] == "PASS", "C1 FAIL: DRC=%s（N=%d）" % (c1["drc"], N)
    assert c1["lvs"] in ("ACCEPT", "PASS"), "C1 FAIL: LVS=%s（N=%d）" % (c1["lvs"], N)
    # 规模债照妖镜：所有交叉必须可异层化解（不得有 2 层物理不可解残留）
    assert c1.get("n_unresolved_crossings") == 0, \
        "C1 FAIL: 规模债未还清，残留不可解交叉 %s（N=%d）" % (
            c1.get("n_unresolved_crossings"), N)
    assert c1.get("n_crossing_pairs") is not None and c1["n_crossing_pairs"] > 0, \
        "C1 FAIL: 交叉对数为 0（N=%d）" % N

    # ---- C2 / C3：电子外设（随 N 同步爬升）----
    assert crit["c2"]["pass"], "C2 FAIL: 驱动器数不足 N=%d" % N
    assert crit["c3"]["pass"], "C3 FAIL: TIA 数不足 N=%d" % N

    # ---- C4：光 IO ----
    c4 = crit["c4"]
    assert c4["n_io_ports"] >= 2, "C4 FAIL: IO 端口 %d < 2（N=%d）" % (c4["n_io_ports"], N)
    assert c4["n_gratings_class"] >= 2, "C4 FAIL: GratingCoupler 类数 %d < 2" % c4["n_gratings_class"]
    assert c4["cpo_valid"], "C4 FAIL: cpo_optical_io_metrics 无效"

    # ---- C5：封装光源 G5 网关 ----
    assert crit["c5"]["status"] == "BYPASSABLE", \
        "C5 FAIL: 封装光源状态 %s" % crit["c5"]["status"]

    # ---- C6：标定环可辨识 ----
    assert crit["c6"]["identifiable"] is True, "C6 FAIL: 网格不可辨识（N=%d）" % N

    # ---- C7：端到端推理 vs 数字 golden（规模下保真度不退化）----
    c7 = crit["c7"]
    assert c7["mvm_rel_err"] < c7["quant_tol"], \
        "C7 FAIL: MVM 相对误差 %.3e ≥ 量化容差 %.3e（N=%d）" % (
            c7["mvm_rel_err"], c7["quant_tol"], N)
    assert c7["classifier_accuracy"] >= 1.0 - 1e-9, \
        "C7 FAIL: 分类精度 %.6f < 1.0（N=%d）" % (c7["classifier_accuracy"], N)

    # ---- C8：同一份主权 GDS 多层协同 ----
    c8 = crit["c8"]
    assert c8["n_layers"] >= 3, "C8 FAIL: GDS 层数 %d < 3（N=%d）" % (c8["n_layers"], N)
    assert c8["pass"], "C8 FAIL: GDS 缺 SI/METAL 协同层"

    # ---- C9：标定红线（无锚不得宣称 calibrated）----
    c9 = crit["c9"]
    assert c9["cal_state"] == "BLOCKED_NO_ANCHOR", \
        "C9 FAIL: 无锚应 BLOCKED，收到 %s" % c9["cal_state"]
    assert c9["can_claim_calibrated"] is False, "C9 FAIL: 无锚不得宣称 calibrated"

    # ---- 总门 ----
    assert rep["all_pass"] is True, "S4 FAIL: 存在未通过判据 %s" % \
        [k for k, v in crit.items() if not v["pass"]]

    return {
        "N": N,
        "dac_bits": dac_bits,
        "n_mzi": c1["n_mzi"],
        "expected_n_mzi": c1["expected_n_mzi"],
        "drc": c1["drc"],
        "lvs": c1["lvs"],
        "n_crossing_pairs": c1["n_crossing_pairs"],
        "n_bridged_nets": c1["n_bridged_nets"],
        "n_layer_repairs": c1["n_layer_repairs"],
        "n_unresolved_crossings": c1["n_unresolved_crossings"],
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
    # 允许 CI 通过环境变量下调规模（默认 64 直接压测规模债修复；CI 超时风险时设 LDA_S4_N=32）
    _n = int(os.environ.get("LDA_S4_N", "64"))
    print(json.dumps(run_soc_s4_smoke(N=_n), indent=2, ensure_ascii=False))
