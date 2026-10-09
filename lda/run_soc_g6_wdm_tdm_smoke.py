# -*- coding: utf-8 -*-
"""G6 杠杆①③：WDM 多 λ 复用 + 时间复用调度（在 S5-ext 全链路之上叠加）。

复用 S5 全链路 C1–C9 + S5-G1~G5（集成度不回归），并新增：
  · G6-WDM：主权 mesh 波长相关酉真算 —— W 信道每 λ MVM 保真 < 容差 + demux/mux GDS DRC
  · G6-TDM：K 帧时分复用 —— 每帧 MVM 保真 < 容差 + 重配置相位变更计数

红线：不报能效；判定真算；不 import A 级禁借求解器；foundry 规则为公开近似（沿用 S5-ext）。
"""
from __future__ import annotations

import os
import sys
import json
from typing import Any, Dict

_LDA_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_LDA_DIR)
for _p in (_LDA_DIR, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_l2 import soc_wdm as wdm
from lda_l2 import soc_tdm as tdm
import run_soc_s5_smoke as s5mod


def run_soc_g6_wdm_tdm_smoke(N: int = 8, W: int = 4, K: int = 4,
                              dac_bits: int = 16,
                              seed: int = 20261009) -> Dict[str, Any]:
    """运行 G6 杠杆①③ 签核，返回 S5 基线 + WDM + TDM 报告。"""
    # 复用 S5 全链路（一次构建 mesh，拿 C1–C9 + S5 签核 + GDS 路径）
    s5 = s5mod.run_soc_s5_smoke(N=N, dac_bits=dac_bits, seed=seed)
    assert s5["all_pass"], "G6 前置失败：S5 全链路未全 PASS（WDM/TDM 建于 S5 之上）"

    # G6 杠杆① WDM 多 λ 复用
    w = wdm.soc_wdm_report(N=N, W=W, seed=seed)
    # G6 杠杆③ 时间复用调度
    t = tdm.soc_tdm_report(N=N, K=K, dac_bits=dac_bits, seed=seed)

    g6_pass = bool(w["all_pass"] and t["all_pass"])
    all_pass = bool(s5["all_pass"] and g6_pass)
    return {
        "N": int(N), "W": int(W), "K": int(K),
        "s5_all_pass": s5["all_pass"],
        "wdm": w, "tdm": t,
        "wdm_pass": w["all_pass"], "tdm_pass": t["all_pass"],
        "g6_pass": g6_pass,
        "all_pass": all_pass,
        "gds_path": s5["gds_path"],
        "mvm_rel_err": s5["mvm_rel_err"], "quant_tol": s5["quant_tol"],
        "classifier_accuracy": s5["classifier_accuracy"],
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=int(os.environ.get("LDA_G6_N", "8")))
    ap.add_argument("--W", type=int, default=int(os.environ.get("LDA_G6W_W", "4")))
    ap.add_argument("--K", type=int, default=int(os.environ.get("LDA_G6T_K", "4")))
    a = ap.parse_args()
    rep = run_soc_g6_wdm_tdm_smoke(N=a.N, W=a.W, K=a.K)
    print(json.dumps({k: v for k, v in rep.items()
                      if k not in ("wdm", "tdm")}, indent=2, default=str))
    print("WDM: worst_mvm_err=%.3e  tol=%.2f  gds_drc=%s"
          % (rep["wdm"]["worst_mvm_rel_err"], rep["wdm"]["tol_mvm_rel"],
             rep["wdm"]["gds_drc_all_pass"]))
    print("TDM: worst_mvm_err=%.3e  tol=%.2f  reconfig_updates=%d"
          % (rep["tdm"]["worst_mvm_rel_err"], rep["tdm"]["tol_mvm_rel"],
             rep["tdm"]["reconfig_total_phase_updates"]))
    print("ALL_PASS =", rep["all_pass"])
    if not rep["all_pass"]:
        raise SystemExit(1)
