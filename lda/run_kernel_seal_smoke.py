"""器件库主流封口 6 类引擎 × B25-B27 锚 对照验证 smoke（v0.8.7）。

验证：
  1. harness 内置 B25/B26/B27（ReferenceCandidate 自洽）PASS。
  2. 6 个新引擎闭环最优候选均通过（光子 3 + 量子 3）。
  3. 死标量锚对照：可调 transmon f01==B25、读出配对 |χ|==B26、
     CZ 门 t_CZ==B27（引擎输出 vs 物理定律锚，LLM 不进判决路径）。
"""
from __future__ import annotations

import sys
import os
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


class KernelSealSmoke(unittest.TestCase):

    def test_b25_b27_harness_pass(self):
        from lda_harness.benchmarks import BENCHMARK_DEFS
        from lda_harness.harness import (
            VerificationHarness, ReferenceCandidate,
        )
        for bid in ("B25", "B26", "B27"):
            self.assertIn(bid, BENCHMARK_DEFS)
        h = VerificationHarness(BENCHMARK_DEFS)
        results = h.run(h.resolve_specs(), ReferenceCandidate())
        for bid in ("B25", "B26", "B27"):
            r = [x for x in results if x.bid == bid]
            self.assertEqual(len(r), 1)
            self.assertTrue(r[0].passed, msg=r[0].note)

    def _engine(self, kind, target):
        from lda_design.design_engine import DesignEngine
        res = DesignEngine().design(kind, target, top_k=3, verify_top_k=3)
        self.assertTrue(res["ok"], msg=res.get("error"))
        self.assertGreater(res["passed"], 0, msg=f"{kind} 无通过候选")
        return res["best"]

    def test_photon_three(self):
        # MMI：best L_mmi == B16 锚
        best = self._engine("Mmi1x2", 100.0)
        from lda_harness.golden import b16_mmi_length
        golden = b16_mmi_length(best["params"]["W_e_um"], 3.30, 1.55)
        self.assertAlmostEqual(best["metric"], golden, delta=0.05 * golden)
        # 光栅耦合器：best λ_B == Λ·n_eff
        best = self._engine("GratingCoupler2", 2.38)
        golden = best["params"]["period_um"] * 2.80
        self.assertAlmostEqual(best["metric"], golden, delta=0.05 * golden)
        # 方向耦合器：best L_3dB == B14 锚
        best = self._engine("DirectionalCoupler2", 20.0)
        from lda_harness.golden import b14_dc_coupling_length
        golden = b14_dc_coupling_length(best["params"]["n_e"], 3.36, 1.55)
        self.assertAlmostEqual(best["metric"], golden, delta=0.05 * golden)

    def test_tunable_transmon_matches_b25(self):
        best = self._engine("TunableTransmon", 6.0)
        from lda_harness.golden import b25_tunable_transmon_f01
        golden = b25_tunable_transmon_f01(
            best["params"]["phi_frac"], 20.0, 0.30)
        self.assertAlmostEqual(best["metric"], golden, delta=0.03 * golden)

    def test_readout_pair_matches_b26(self):
        best = self._engine("ReadoutPair", 0.002)
        from lda_harness.golden import b26_dispersive_shift
        golden = abs(b26_dispersive_shift(
            5.0, -0.30, best["params"]["f_r_ghz"], 0.10))
        self.assertAlmostEqual(best["metric"], golden, delta=0.05 * golden)

    def test_cz_gate_matches_b27(self):
        best = self._engine("CzGate", 700.0)
        from lda_harness.golden import b27_cz_gate_time
        golden = b27_cz_gate_time(
            5.0, -0.30, 6.0, best["params"]["g_ghz"])
        self.assertAlmostEqual(best["metric"], golden, delta=0.05 * golden)
        # 条件相位 π 精确性（相位检查在 verify 内部，这里复核引擎结果）
        pc = best["result"]["checks"]["phase_check"]
        self.assertTrue(pc["phase_ok"], msg="2|χ|·t != π")


if __name__ == "__main__":
    unittest.main(verbosity=2)
