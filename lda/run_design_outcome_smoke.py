"""P2 旗舰端到端面板 · 设计闭环→统一设计包 · 门禁冒烟。

零外部依赖（仅标准库 unittest）。验证：
  1. engine_catalog / package_catalog 不依赖内核实例化即可返回（轻量元数据）。
  2. package_from_engine 对 Transmon / RingResonator 真跑闭环并包成统一设计包，
     verification.passed=True 且 validate_package 无错误（schema 合法）。
  3. ENGINE_KINDS 已被 validate_package 放行。

运行：python run_design_outcome_smoke.py
"""
from __future__ import annotations

import sys
import os
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


class DesignOutcomeSmoke(unittest.TestCase):

    def test_catalogs_no_kernel(self):
        from lda_design.design_package import (
            engine_catalog, package_catalog, ENGINE_KINDS,
        )
        eng = engine_catalog()
        self.assertEqual(len(eng), len(ENGINE_KINDS))
        for e in eng:
            self.assertIn("kind", e)
            self.assertIn("default_target", e)
        pkg = package_catalog()
        self.assertGreaterEqual(len(pkg), 11)
        for p in pkg:
            self.assertIn("kind", p)
            self.assertIn("defaults", p)

    def test_engine_transmon_package(self):
        from lda_design.design_package import (
            package_from_engine, validate_package, ENGINE_KINDS,
        )
        pkg = package_from_engine("engine_transmon", 5.0, top_k=3)
        self.assertTrue(pkg.get("ok"), msg=pkg.get("error"))
        self.assertIn(pkg["kind"], ENGINE_KINDS)
        self.assertEqual(pkg["domain"], "quantum")
        v = pkg["verification"]
        self.assertTrue(v["passed"], msg=v.get("verdict"))
        self.assertIn("checks", v)
        self.assertEqual(pkg["design"]["targets"]["target"], 5.0)
        self.assertEqual(validate_package(pkg), [])

    def test_engine_ringresonator_package(self):
        from lda_design.design_package import (
            package_from_engine, validate_package,
        )
        pkg = package_from_engine("engine_ringresonator", 9.0, top_k=3)
        self.assertTrue(pkg.get("ok"), msg=pkg.get("error"))
        self.assertEqual(pkg["domain"], "photon")
        v = pkg["verification"]
        # Ring 为解析锚：物理合理即算可用（诚实标注 FDTD 抽检需 GPU）
        self.assertTrue(v["passed"], msg=v.get("verdict"))
        self.assertEqual(validate_package(pkg), [])

    def test_engine_mzi_package(self):
        from lda_design.design_package import (
            package_from_engine, validate_package,
        )
        pkg = package_from_engine("engine_mzi", 20.0, top_k=3)
        self.assertTrue(pkg.get("ok"), msg=pkg.get("error"))
        self.assertEqual(pkg["domain"], "photon")
        self.assertEqual(pkg["kind"], "engine_mzi")
        v = pkg["verification"]
        # MZI 为解析干涉谱契约（analytic_only）：物理自洽即 PASS
        self.assertTrue(v["passed"], msg=v.get("verdict"))
        self.assertEqual(validate_package(pkg), [])
        # 校验最优候选 FSR 与物理定律锚 B20 一致（死标量比对）
        best = pkg["artifacts"]["engine_result"]["best"]
        best_fsr = best["metric"]
        from lda_harness.golden import b20_mzi_fsr
        golden_fsr = b20_mzi_fsr(deltaL_um=best["params"]["deltaL_um"])
        self.assertAlmostEqual(best_fsr, golden_fsr, delta=0.5)

    def test_engine_phc_package(self):
        from lda_design.design_package import (
            package_from_engine, validate_package,
        )
        pkg = package_from_engine("engine_phc", 2200.0, top_k=3)
        self.assertTrue(pkg.get("ok"), msg=pkg.get("error"))
        self.assertEqual(pkg["domain"], "photon")
        self.assertEqual(pkg["kind"], "engine_phc")
        v = pkg["verification"]
        # PhC 为真跑 2D FDTD：闭环 + 真实求解器双重验证通过即 PASS
        self.assertTrue(v["passed"], msg=v.get("verdict"))
        self.assertEqual(validate_package(pkg), [])
        # 校验最优候选 λ_res 与物理定律锚 B21 一致（死标量比对）
        best = pkg["artifacts"]["engine_result"]["best"]
        best_lam = best["metric"]
        from lda_harness.golden import b21_phc_resonance
        golden = b21_phc_resonance(best["params"]["L_cav_um"], 3.48, 1.44)
        self.assertIsNotNone(best_lam)
        self.assertAlmostEqual(best_lam, golden, delta=0.05 * golden)

    def test_package_all_11(self):
        from lda_design.design_package import (
            build_package, validate_package, PACKAGE_KINDS,
        )
        for k in PACKAGE_KINDS:
            with self.subTest(kind=k):
                pkg = build_package(k)
                self.assertTrue(pkg.get("ok"), msg=pkg.get("error"))
                self.assertEqual(validate_package(pkg), [])
                self.assertIn("verification", pkg)
                self.assertIn("passed", pkg["verification"])

    def test_unknown_kind(self):
        from lda_design.design_package import package_from_engine
        pkg = package_from_engine("engine_nonexistent", 1.0, top_k=1)
        self.assertFalse(pkg.get("ok"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
