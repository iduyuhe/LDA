"""MZM 调制器 Vπ 锚 B28 对照验证 smoke（v0.9.1 · 钉子 D1b=A）。

验证：
  1. harness 内置 B28（ReferenceCandidate 自洽）PASS —— MZM 半波电压
     成为可复核物理定律基准点（MZI 无源 B20 + 有源 B28 双锚闭合）。
  2. B28 双算法互证：解析闭式 ↔ 沿程积分+二分 偏差 ≤ cross_tol
     （非 AI ground，硬判决）。
  3. 实证量级 sanity：LiNbO3 x-cut MZM Vπ≈3.8V ∈ [3,5]V 合理区间
     （诚实边界佐证，不进死标量判决）。

运行：python run_b28_modulator_vpi_smoke.py
"""
from __future__ import annotations

import sys
import os
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


class B28ModulatorVpiSmoke(unittest.TestCase):

    def test_b28_harness_pass(self):
        from lda_harness.benchmarks import BENCHMARK_DEFS
        from lda_harness.harness import (
            VerificationHarness, ReferenceCandidate,
        )
        self.assertIn("B28", BENCHMARK_DEFS)
        h = VerificationHarness(BENCHMARK_DEFS)
        specs = h.resolve_specs()
        results = h.run(specs, ReferenceCandidate())
        b28 = [r for r in results if r.bid == "B28"]
        self.assertEqual(len(b28), 1)
        self.assertTrue(b28[0].passed, msg=b28[0].note)

    def test_b28_cross_check_ok(self):
        from lda_harness.b28_modulator_vpi_anchor import b28_modulator_vpi_report
        rep = b28_modulator_vpi_report()
        self.assertTrue(rep["cross_check_ok"],
                        msg="解析闭式 ↔ 沿程积分+二分 互证失败: %s" % rep)
        self.assertTrue(rep["monotone_in_L"],
                        msg="Vπ 随调制臂长度应单调递减")

    def test_b28_empirical_sanity(self):
        from lda_harness.b28_modulator_vpi_anchor import b28_modulator_vpi_report
        rep = b28_modulator_vpi_report()
        es = rep["empirical_sanity"]
        self.assertTrue(es["in_range"],
                        msg="LiNbO3 x-cut MZM Vπ=%.3fV 应∈[3,5]V" % es["lnb03_xcut_Vpi_volts"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
