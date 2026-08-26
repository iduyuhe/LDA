"""Fluxonium / 可调耦合器引擎 × B23/B24 物理定律锚 对照验证 smoke（内核纵深 D+E）。

验证：
  1. harness 内置 B23/B24（ReferenceCandidate 自洽）PASS。
  2. Fluxonium 引擎闭环最优候选：双基对拍一致（rel≤1%）且 f01 ≥ B23 LC 极限
     （单调物理边界）。
  3. TunableCoupler 引擎闭环最优候选 |g_eff| == B24 二阶微扰锚（死标量比对）。
"""
from __future__ import annotations

import sys
import os
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


class FluxoniumAnchorSmoke(unittest.TestCase):

    def test_b23_b24_harness_pass(self):
        from lda_harness.benchmarks import BENCHMARK_DEFS
        from lda_harness.harness import (
            VerificationHarness, ReferenceCandidate,
        )
        self.assertIn("B23", BENCHMARK_DEFS)
        self.assertIn("B24", BENCHMARK_DEFS)
        h = VerificationHarness(BENCHMARK_DEFS)
        specs = h.resolve_specs()
        results = h.run(specs, ReferenceCandidate())
        for bid in ("B23", "B24"):
            r = [x for x in results if x.bid == bid]
            self.assertEqual(len(r), 1)
            self.assertTrue(r[0].passed, msg=r[0].note)

    def test_fluxonium_engine_dual_basis(self):
        from lda_design.design_engine import DesignEngine
        from lda_harness.golden import b23_fluxonium_lc_limit
        eng = DesignEngine()
        res = eng.design("Fluxonium", 6.0, top_k=3)
        self.assertTrue(res["ok"], msg=res.get("error"))
        self.assertGreater(res["passed"], 0, msg="Fluxonium 无通过候选")
        best = res["best"]
        f01 = best["metric"]
        self.assertIsNotNone(f01, msg="未提取到 f01")
        dual = best["result"]["checks"]["dual_basis"]
        self.assertLessEqual(dual["rel"], 0.01, msg="双基对拍超 1%")
        # B23 LC 单调上界：f01(Ej>0) ≥ √(8EcEl)
        lc = b23_fluxonium_lc_limit(1.0, 1.0)
        self.assertGreaterEqual(f01, lc * 0.95,
                                msg="f01 低于 LC 极限边界（物理错误）")

    def test_tcoup_engine_matches_b24(self):
        from lda_design.design_engine import DesignEngine
        from lda_harness.golden import b24_tcoup_geff
        eng = DesignEngine()
        res = eng.design("TunableCoupler", 0.005, top_k=3)
        self.assertTrue(res["ok"], msg=res.get("error"))
        self.assertGreater(res["passed"], 0, msg="TunableCoupler 无通过候选")
        best = res["best"]
        cand = best["metric"]
        self.assertIsNotNone(cand, msg="未提取到 |g_eff|")
        golden = abs(b24_tcoup_geff(5.0, 7.5, best["params"]["g1_ghz"], 0.10))
        # 引擎输出 |g_eff|（三模对角化真跑）= B24 解析锚，死标量比对，
        # LLM 不进判决路径；delta 取验证容差上限 5%（passed 保证 ≤3%）。
        self.assertAlmostEqual(cand, golden, delta=0.05 * golden)


if __name__ == "__main__":
    unittest.main(verbosity=2)
