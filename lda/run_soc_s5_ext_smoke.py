# -*- coding: utf-8 -*-
"""S5-ext：在 S5（主权 GDS 签核）之上叠加 G1 单片激光 + G4 foundry PDK 对接。

复用 S5 全链路 C1–C9 + S5-G1~G5（集成度不回归），并新增：
  · G4 真实 foundry PDK 对接：主权 GDS → foundry 层映射 + foundry DRC 签核
    （AIM Photonics 公开近似 spec，逐条规格锚；非 NDA 真值）
  · G1 单片集成激光：与外置激光（G5 BYPASSABLE）对比，证明可单片集成
    （谐振命中 C 波段 + 阈值增益 < 可用增益 + 耦合损耗 < 预算）

红线：不报能效；判定真算；foundry 规则为公开近似（非 NDA 真值）；
不 import A 级禁借求解器。
"""
from __future__ import annotations

import os
import sys
import json
from typing import Any, Dict

_LDA_DIR = os.path.dirname(os.path.abspath(__file__))              # .../lda
_ROOT = os.path.dirname(_LDA_DIR)                                  # .../D:/agent_LDA
for _p in (_LDA_DIR, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_l2 import foundry_pdk as fpk
from lda_l2 import monolithic_laser as ml
import run_soc_s5_smoke as s5mod


def run_soc_s5_ext_smoke(N: int = 64, dac_bits: int = 16, seed: int = 20261009
                         ) -> Dict[str, Any]:
    # 复用 S5 全链路（一次构建 mesh，拿 C1–C9 + S5 签核 + GDS 路径）
    s5 = s5mod.run_soc_s5_smoke(N=N, dac_bits=dac_bits, seed=seed)
    gds_path = s5["gds_path"]
    assert s5["all_pass"], "S5-ext 前置失败：S5 全链路未全 PASS（G1/G4 建于 S5 之上）"

    # ── G4 真实 foundry PDK 对接（AIM Photonics 公开近似）
    spec = fpk.build_aim_photonics_spec()
    lm = fpk.layer_map_report(gds_path, spec)
    drc = fpk.foundry_drc_signoff(gds_path, spec)
    g4 = {
        "foundry": spec.foundry,
        "all_mapped": bool(lm["all_mapped"]),
        "sovereign_layers": lm["sovereign_layers"],
        "foundry_layers": lm["foundry_layers"],
        "layer_map": lm["layer_map"],
        "drc_all_pass": bool(drc["all_pass"]),
        "drc_n_violations": len(drc.get("violations", [])),
        "drc_rules": drc.get("rules", {}),
        "spec_anchors": spec.spec_anchors,
        "honest_boundary": spec.honest_boundary,
    }
    g4_pass = bool(g4["all_mapped"] and g4["drc_all_pass"])

    # ── G1 单片集成激光（对照外置激光 G5）
    g1 = ml.monolithic_laser_integration_report()
    g1_pass = bool(g1["g1_in_c_band"] and g1["g1_lasable"] and g1["g1_coupling_ok"])

    all_pass = bool(s5["all_pass"] and g4_pass and g1_pass)
    return {
        "N": int(N),
        "s5_all_pass": s5["all_pass"],
        "g4_foundry_pdk": g4,
        "g1_monolithic_laser": g1,
        "g4_pass": g4_pass,
        "g1_pass": g1_pass,
        "all_pass": all_pass,
        "gds_path": gds_path,
        "mvm_rel_err": s5["mvm_rel_err"],
        "quant_tol": s5["quant_tol"],
        "classifier_accuracy": s5["classifier_accuracy"],
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=int(os.environ.get("LDA_S4_N", "64")))
    a = ap.parse_args()
    rep = run_soc_s5_ext_smoke(N=a.N)
    print(json.dumps({k: v for k, v in rep.items()
                      if k not in ("g4_foundry_pdk", "g1_monolithic_laser")},
                     indent=2, default=str))
    print("G4 spec_anchors:", json.dumps(rep["g4_foundry_pdk"]["spec_anchors"],
                                          default=str, ensure_ascii=False))
    print("G4 honest_boundary:", rep["g4_foundry_pdk"]["honest_boundary"])
    print("G1 report:", json.dumps(rep["g1_monolithic_laser"],
                                    default=str, ensure_ascii=False))
    print("ALL_PASS =", rep["all_pass"])
    if not rep["all_pass"]:
        sys.exit(1)
