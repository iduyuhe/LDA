# -*- coding: utf-8 -*-
"""G6 收官：主权 GDS → foundry DRC 闭集 流片 signoff CI 门禁。

复用 S5 全链路（一次构建 mesh，拿 C1–C9 + S5 签核 + 主权 GDS），并叠加
foundry DRC 闭集 signoff 判据（G4 foundry_pdk + 显式闭集规则牌）。

红线：不报能效；判定真算；不 import A 级禁借求解器；foundry 规则为公开近似
（非 NDA 真值）→ signoff_ready 仅代表「主权自洽可制造性就绪」，不构成真实
foundry tape-out 授权（见 soc_tapeout_signoff.honest_boundary）。

默认 N=16 控 CI 预算；N=64/N=128 主权版图 signoff 已按需验证（13/13 通过，
<0.3s）。
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

from lda_l2 import soc_tapeout_signoff as ts
import run_soc_s5_smoke as s5mod


def run_soc_tapeout_signoff_smoke(N: int = 16, dac_bits: int = 16,
                                  seed: int = 20261009) -> Dict[str, Any]:
    """运行 foundry DRC 闭集 流片 signoff 签核，返回 S5 基线 + signoff 报告。"""
    # 复用 S5 全链路（一次构建 mesh，确认设计流水线仍全 PASS）
    s5 = s5mod.run_soc_s5_smoke(N=N, dac_bits=dac_bits, seed=seed)
    assert s5["all_pass"], "Tapeout 前置失败：S5 全链路未全 PASS（signoff 建于 S5 之上）"

    # 对**完整 SoC 主权 GDS（lda_soc_{N}x{N}.gds，含 SI/METAL/HEATER/M3 的
    # 可 tape-out 交付物）**跑 foundry DRC 闭集 signoff（N 触发 build_soc_gds）。
    signoff = ts.tapeout_signoff_report(N=N)
    all_pass = bool(s5["all_pass"] and signoff["signoff_ready"])
    return {
        "N": int(N),
        "s5_all_pass": s5["all_pass"],
        "gds_path": signoff["gds_path"],
        "signoff": signoff,
        "signoff_ready": signoff["signoff_ready"],
        "n_rules_pass": signoff["n_rules_pass"],
        "n_rules_total": signoff["n_rules_total"],
        "all_pass": all_pass,
        "mvm_rel_err": s5["mvm_rel_err"], "quant_tol": s5["quant_tol"],
        "classifier_accuracy": s5["classifier_accuracy"],
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=int(os.environ.get("LDA_TAPE_N", "16")))
    a = ap.parse_args()
    rep = run_soc_tapeout_signoff_smoke(N=a.N)
    print(json.dumps({k: v for k, v in rep.items() if k != "signoff"},
                     indent=2, default=str))
    print(ts.tapeout_signoff_markdown(rep["signoff"]))
    print("ALL_PASS =", rep["all_pass"])
    if not rep["all_pass"]:
        raise SystemExit(1)
