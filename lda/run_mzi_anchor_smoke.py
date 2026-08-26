"""MZI 引擎 × B20 物理定律锚 对照验证 smoke（D-112 后内核纵深）。

验证：
  1. harness 内置 B20（ReferenceCandidate 自洽）PASS —— MZI 成为可复核
     物理定律基准点（对照验证地基）。
  2. MZI 引擎闭环最优候选 FSR == B20 解析 golden（死标量比对一致）——

     这正落实杜先生「设计出的器件能和其他器件/基准对比，解决验证问题」的
     想法：MZI 引擎输出的 FSR 直接对物理定律锚 B20 复核，而非自证清白。

运行：python run_mzi_anchor_smoke.py
"""
from __future__ import annotations

import sys
import os
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


class MziAnchorSmoke(unittest.TestCase):

    def test_b20_harness_pass(self):
        from lda_harness.benchmarks import BENCHMARK_DEFS
        from lda_harness.harness import (
            VerificationHarness, ReferenceCandidate,
        )
        self.assertIn("B20", BENCHMARK_DEFS)
        h = VerificationHarness(BENCHMARK_DEFS)
        specs = h.resolve_specs()
        results = h.run(specs, ReferenceCandidate())
        b20 = [r for r in results if r.bid == "B20"]
        self.assertEqual(len(b20), 1)
        self.assertTrue(b20[0].passed, msg=b20[0].note)

    def test_mzi_engine_matches_b20(self):
        from lda_design.design_engine import DesignEngine
        from lda_harness.golden import b20_mzi_fsr
        eng = DesignEngine()
        res = eng.design("MziInterferometer", 20.0, top_k=3)
        self.assertTrue(res["ok"], msg=res.get("error"))
        self.assertGreater(res["passed"], 0, msg="MZI 无通过候选")
        best = res["best"]
        cand_fsr = best["metric"]
        golden_fsr = b20_mzi_fsr(deltaL_um=best["params"]["deltaL_um"])
        # 引擎输出 FSR（round 3 位展示）= 物理定律锚 B20 解析值（round 后），
        # 死标量比对，LLM 不进判决路径；round 误差上界 5e-4，delta 取 1e-2。
        self.assertAlmostEqual(cand_fsr, round(golden_fsr, 3), delta=1e-2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
