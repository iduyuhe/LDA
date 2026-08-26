"""CPW λ/4 读出谐振器引擎 × B22 物理定律锚 对照验证 smoke（内核纵深 C · QRES 1D TL-FDTD）。

验证：
  1. harness 内置 B22（ReferenceCandidate 自洽）PASS —— 读出谐振器成为可复核
     物理定律基准点（对照验证地基）。
  2. QRES 引擎闭环最优候选 f0 == B22 解析 golden（死标量比对一致）——
     设计出的读出谐振器基模频率直接对物理定律锚 B22 复核，而非自证清白。

运行：python run_qres_anchor_smoke.py
"""
from __future__ import annotations

import sys
import os
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


class QresAnchorSmoke(unittest.TestCase):

    def test_b22_harness_pass(self):
        from lda_harness.benchmarks import BENCHMARK_DEFS
        from lda_harness.harness import (
            VerificationHarness, ReferenceCandidate,
        )
        self.assertIn("B22", BENCHMARK_DEFS)
        h = VerificationHarness(BENCHMARK_DEFS)
        specs = h.resolve_specs()
        results = h.run(specs, ReferenceCandidate())
        b22 = [r for r in results if r.bid == "B22"]
        self.assertEqual(len(b22), 1)
        self.assertTrue(b22[0].passed, msg=b22[0].note)

    def test_qres_engine_matches_b22(self):
        from lda_design.design_engine import DesignEngine
        from lda_harness.golden import b22_qres_frequency
        eng = DesignEngine()
        res = eng.design("ReadoutResonator", 7.5, top_k=3)
        self.assertTrue(res["ok"], msg=res.get("error"))
        self.assertGreater(res["passed"], 0, msg="QRES 无通过候选")
        best = res["best"]
        cand = best["metric"]
        self.assertIsNotNone(cand, msg="未提取到 FDTD 基模频率 f0")
        golden = b22_qres_frequency(best["params"]["L_um"], 2.5)
        # 引擎输出 f0（1D TL-FDTD 真跑）= 物理定律锚 B22 解析值，死标量比对，
        # LLM 不进判决路径；delta 取验证容差上限 5%（passed 保证 ≤3%）。
        self.assertAlmostEqual(cand, golden, delta=0.05 * golden)


if __name__ == "__main__":
    unittest.main(verbosity=2)
