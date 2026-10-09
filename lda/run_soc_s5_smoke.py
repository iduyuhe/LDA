# -*- coding: utf-8 -*-
"""S5：主权 GDS 真实导出 + DRC/LVS 全流程签核（光子计算 SoC 征程）。

复用 S3/S4 全链路 C1–C9（集成度不回归），并新增 S5 专属主权 GDS 签核：
  · S5-G1 主权 mesh GDS 真实落盘（build_nxn_mzi_mesh 写 lda_{N}x{N}_mzi_mesh.gds）
  · S5-G2 文件往返无损：sha256(落盘) == sha256(内存 bytes)（文件 IO 无损坏）
  · S5-G3 落盘文件可解析 + 含 M3 奇圈破局层（LIB_LAYER_METAL3=9）
  · S5-G4 文件级几何 DRC 全流程（gds_drc.check_geometry，覆盖最小线宽/间距/面积）
  · S5-G5 整芯片 SoC GDS 真实写盘 + 含 M3 层 + mesh 子集（SI+M3）与主权 mesh GDS 一致

S5 把 S4 的「内存判据」升级为「可 tape-out 文件级签核」：主权 mesh 版图不仅
在内存通过 DRC/LVS（export_chip_gds 内部已做 roundtrip + 两闸），其落盘 GDSII
还要经文件往返无损 + 几何 DRC + 含 M3 层三重验证；整芯片 SoC GDS 须含 M3 层且
mesh 子集与主权 mesh GDS 逐层一致（装配不破坏主权版图）。

红线纪律：不报能效；判定必须真算；EIC/HEATER 为行为级几何占位（S3 声明），
其 netlist 级 LVS 留后续，S5 仅做几何存在性 + mesh 子集一致性。
"""
from __future__ import annotations

import os
import sys
import json
import hashlib
from typing import Any, Dict, Optional

import numpy as np

# 路径装配（让 examples / lda_l2 可导入）
_LDA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../lda
_ROOT = os.path.dirname(_LDA_DIR)                                       # .../D:/agent_LDA
for _p in (_LDA_DIR, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_l2 import gds_export as gx
from lda_l2.gds_drc import check_geometry
from lda_l2.soc_design_package import (
    _build_nxn_mesh, build_soc_gds,
    soc_end_to_end_mvm, soc_end_to_end_classifier,
)
from lda_l2.eic_functional import soc_eic_array
from lda_l2.soc_calibration import soc_calibration_verify
from lda_l2.four_layer_redline_gate import check_external_laser_bypassable


def _layer_poly_count(parsed: Dict, layers) -> int:
    """统计 parse_gds_polygons 结果中落在指定 GDS 层集合的元素数（S5-G5b 用）。"""
    cnt = 0
    for elems in parsed.get("structures", {}).values():
        for e in elems:
            if e.get("layer") in layers:
                cnt += 1
    return cnt


def run_soc_s5_smoke(N: int = 64, dac_bits: int = 16, seed: int = 20261009
                     ) -> Dict[str, Any]:
    """运行 S5 主权 GDS 签核，返回 C1–C9 + S5 专属签核报告。"""
    # ── 一次构建主权 mesh（落盘 + 返回原始 bytes + verdicts + geoms）
    core = _build_nxn_mesh(N, return_geoms=True)
    gds_path = core["gds_path"]
    gds_raw = core["gds_bytes_raw"]
    assert os.path.exists(gds_path), "S5-G1 FAIL: 主权 mesh GDS 未落盘: %s" % gds_path
    data = open(gds_path, "rb").read()

    # S5-G2 文件往返无损（sha256 比对内存 bytes）
    h_file = hashlib.sha256(data).hexdigest()
    h_mem = hashlib.sha256(gds_raw).hexdigest()
    assert h_file == h_mem, "S5-G2 FAIL: GDS 文件往返 sha256 不一致（文件 IO 损坏）"

    # S5-G3 落盘可解析 + 含 M3 奇圈破局层（仅当主权 mesh 确有 M3 几何时强制）
    parse = gx.parse_gds(data)
    top_layers: set = set()
    for s in parse["structures"].values():
        top_layers |= s["layers"]
    has_m3_geom = bool(core.get("n_m3_nets", 0) > 0)
    if has_m3_geom:
        assert gx.LIB_LAYER_METAL3 in top_layers, \
            "S5-G3 FAIL: 主权 mesh GDS 有 M3 几何却缺 M3 层（层集合=%s）" % sorted(top_layers)

    # S5-G4 文件级几何 DRC 全流程（最小线宽/间距/面积）
    parsed = gx.parse_gds_polygons(data)
    geom = check_geometry(parsed["structures"])
    assert geom["all_pass"], "S5-G4 FAIL: 主权 mesh GDS 几何 DRC 违规: %s" % geom["violations"][:5]

    # ── C1–C9（复用 core + 平台子函数，集成度不回归）
    expected_mzi = N * (N - 1) // 2
    c1 = {
        "n_mzi": core["n_mzi"], "expected_n_mzi": expected_mzi,
        "drc": core["drc_verdict"], "lvs": core["lvs_verdict"],
        "n_crossing_pairs": core.get("n_crossing_pairs"),
        "n_unresolved_crossings": core.get("n_unresolved_crossings"),
        "n_layer_repairs": core.get("n_layer_repairs"),
        "pass": bool(core["n_mzi"] == expected_mzi
                     and core["drc_verdict"] == "PASS"
                     and core["lvs_verdict"] in ("ACCEPT", "PASS")),
    }
    eic = soc_eic_array(N)
    c2 = {"n_drivers": eic["n_drivers"], "pass": bool(eic["n_drivers"] >= N)}
    c3 = {"n_tias": eic["n_tias"], "pass": bool(eic["n_tias"] >= N)}
    c4 = {"n_io_ports": len(core.get("io_ports", [])),
          "pass": bool(len(core.get("io_ports", [])) >= 2)}
    g5 = check_external_laser_bypassable()
    c5 = {"status": g5["status"], "pass": bool(g5["status"] == "BYPASSABLE")}
    cal = soc_calibration_verify(N, anchor=None)
    c6 = {"identifiable": cal["identifiable"], "rank": cal["rank"],
          "pass": bool(cal["identifiable"])}
    c9 = {"cal_state": cal["cal_state"], "can_claim_calibrated": cal["can_claim_calibrated"],
          "pass": bool(cal["cal_state"] == "BLOCKED_NO_ANCHOR"
                       and cal["can_claim_calibrated"] is False)}
    # C7 端到端（复用 S3/S4 同一函数，确保口径一致）
    mvm = soc_end_to_end_mvm(N, dac_bits=dac_bits, seed=seed)
    cls = soc_end_to_end_classifier(dac_bits=dac_bits, seed=seed)
    quant_tol = 10.0 * (2.0 * np.pi / float(2 ** dac_bits)) * float(N)
    c7 = {
        "mvm_rel_err": mvm["mvm_rel_err"], "quant_tol": float(quant_tol),
        "classifier_accuracy": cls["accuracy"],
        "pass": bool(mvm["mvm_rel_err"] < quant_tol
                     and cls["accuracy"] >= 1.0 - 1e-9),
    }

    # ── 整芯片 SoC GDS（复用 core，不重建 mesh）
    soc = build_soc_gds(N, core=core)
    soc_data = open(soc["gds_path"], "rb").read()
    soc_parse = gx.parse_gds(soc_data)
    soc_layers: set = set()
    for s in soc_parse["structures"].values():
        soc_layers |= s["layers"]
    if has_m3_geom:
        assert gx.LIB_LAYER_METAL3 in soc_layers, \
            "S5-G5a FAIL: 整芯片 SoC GDS 缺 M3 层（主权 mesh 有 M3 几何却未在整芯片落盘）"
    # S5-G5b mesh 子集（SI+M3）与主权 mesh GDS 逐层一致
    soc_parsed = gx.parse_gds_polygons(soc_data)
    mesh_poly = _layer_poly_count(parsed, {gx.LIB_LAYER_SI, gx.LIB_LAYER_METAL3})
    soc_mesh_poly = _layer_poly_count(soc_parsed, {gx.LIB_LAYER_SI, gx.LIB_LAYER_METAL3})
    c8 = {
        "n_layers": soc["n_layers"], "layers": soc["layers"],
        "soc_mesh_poly": soc_mesh_poly, "mesh_poly": mesh_poly,
        "pass": bool(soc["n_layers"] >= 3
                     and gx.LIB_LAYER_SI in soc["layers"]
                     and gx.LIB_LAYER_METAL in soc["layers"]
                     and soc_mesh_poly == mesh_poly),
    }

    crit = {"c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5,
            "c6": c6, "c7": c7, "c8": c8, "c9": c9}
    # S5 专属签核字段
    s5 = {
        "g1_file_exists": True,
        "g2_roundtrip_sha256": h_file == h_mem,
        "g3_has_m3": gx.LIB_LAYER_METAL3 in top_layers,
        "g4_geom_drc_pass": bool(geom["all_pass"]),
        "g5_soc_gds_exists": os.path.exists(soc["gds_path"]),
        "g5_soc_has_m3": gx.LIB_LAYER_METAL3 in soc_layers,
        "g5_mesh_subset_consistent": soc_mesh_poly == mesh_poly,
    }
    # S5 专属断言：G1/G2/G4/G5(存在+子集一致) 恒要求；G3/G5a 的 M3 层仅在
    # 主权 mesh 确有 M3 几何（N≥64 奇圈）时强制（小 N 无奇圈则仅记录）。
    s5_pass = (
        s5["g1_file_exists"] and s5["g2_roundtrip_sha256"]
        and s5["g4_geom_drc_pass"] and s5["g5_soc_gds_exists"]
        and s5["g5_mesh_subset_consistent"]
        and (not has_m3_geom or s5["g3_has_m3"])
        and (not has_m3_geom or s5["g5_soc_has_m3"])
    )
    all_pass = all(c["pass"] for c in crit.values()) and s5_pass
    return {
        "N": int(N), "dac_bits": int(dac_bits),
        "gds_path": gds_path, "gds_n_bytes": len(data),
        "criteria": crit, "s5_checks": s5,
        "all_pass": bool(all_pass),
        "mvm_rel_err": mvm["mvm_rel_err"], "quant_tol": float(quant_tol),
        "classifier_accuracy": cls["accuracy"],
        "gds_n_layers_soc": soc["n_layers"], "gds_layers_soc": soc["layers"],
        "soc_gds_path": soc["gds_path"],
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=int(os.environ.get("LDA_S4_N", "64")))
    a = ap.parse_args()
    rep = run_soc_s5_smoke(N=a.N)
    print(json.dumps({k: v for k, v in rep.items() if k != "criteria"},
                     indent=2, default=str))
    print("ALL_PASS =", rep["all_pass"])
    if not rep["all_pass"]:
        print("CRIT:", json.dumps(rep["criteria"], default=str))
        print("S5:", json.dumps(rep["s5_checks"], default=str))
        sys.exit(1)
