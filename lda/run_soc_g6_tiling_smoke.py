# -*- coding: utf-8 -*-
"""G6 杠杆② 多核 array tiling · CI 门禁（CI core 301→302）。

复用 S5-ext 单核主权 GDS（build_soc_gds）+ 叠加 M×M 阵列 tiling / 阵列 DRC /
层栈完整性 / 阵列级 MVM 保真 / 跨核光 IO 计数。判定真算，不报能效，不 import
A 级禁借求解器。
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict

_LDA_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_LDA_DIR)
for _p in (_LDA_DIR, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_l2 import soc_array_tiling as sat


def run_soc_g6_tiling_smoke(N: int = 8, M: int = 4, dac_bits: int = 16,
                            seed: int = 20261009) -> Dict[str, Any]:
    """G6 多核 array tiling 门禁：返回报告并断言 all_pass（失败即红）。"""
    rep = sat.soc_array_tiling_report(N=N, M=M, dac_bits=dac_bits, seed=seed)
    assert rep["all_pass"], "G6 tiling 未全 PASS（见报告字段）"
    return rep


if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=int(os.environ.get("LDA_G6_N", "8")))
    ap.add_argument("--M", type=int, default=int(os.environ.get("LDA_G6_M", "4")))
    a = ap.parse_args()
    rep = run_soc_g6_tiling_smoke(N=a.N, M=a.M)
    print(json.dumps({k: v for k, v in rep.items() if k != "honest_boundary"},
                     indent=2, default=str))
    print("honest_boundary:", rep["honest_boundary"])
    print("ALL_PASS =", rep["all_pass"])
    if not rep["all_pass"]:
        sys.exit(1)
