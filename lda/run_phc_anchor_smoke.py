"""光子晶体腔引擎 × B21 物理定律锚 对照验证 smoke（内核纵深 B · PhC 2D FDTD）。

验证：
  1. harness 内置 B21（ReferenceCandidate 自洽）PASS —— PhC 腔成为可复核
     物理定律基准点（对照验证地基）。
  2. PhC 引擎闭环最优候选 λ_res == B21 解析 golden（死标量比对一致）——
     设计出的光子晶体腔共振波长直接对物理定律锚 B21 复核，而非自证清白。

运行：python run_phc_anchor_smoke.py
"""
from __future__ import annotations

import sys
import os
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


class PhcAnchorSmoke(unittest.TestCase):

    def test_b21_harness_pass(self):
        from lda_harness.benchmarks import BENCHMARK_DEFS
        from lda_harness.harness import (
            VerificationHarness, ReferenceCandidate,
        )
        self.assertIn("B21", BENCHMARK_DEFS)
        h = VerificationHarness(BENCHMARK_DEFS)
        specs = h.resolve_specs()
        results = h.run(specs, ReferenceCandidate())
        b21 = [r for r in results if r.bid == "B21"]
        self.assertEqual(len(b21), 1)
        self.assertTrue(b21[0].passed, msg=b21[0].note)

    def test_phc_engine_matches_b21(self):
        from lda_design.design_engine import DesignEngine
        from lda_harness.golden import b21_phc_resonance
        eng = DesignEngine()
        res = eng.design("PhCCavity", 2200.0, top_k=3)
        self.assertTrue(res["ok"], msg=res.get("error"))
        self.assertGreater(res["passed"], 0, msg="PhC 无通过候选")
        best = res["best"]
        cand = best["metric"]
        self.assertIsNotNone(cand, msg="未提取到 FDTD 腔共振 λ_res")
        golden = b21_phc_resonance(best["params"]["L_cav_um"], 3.48, 1.44)
        # 引擎输出 λ_res（2D FDTD 真跑）= 物理定律锚 B21 解析值，死标量比对，
        # LLM 不进判决路径；delta 取验证容差上限 5%（passed 保证 ≤3%）。
        self.assertAlmostEqual(cand, golden, delta=0.05 * golden)


if __name__ == "__main__":
    unittest.main(verbosity=2)
