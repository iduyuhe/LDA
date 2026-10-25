"""T1 紧凑模型 schema + 反向护栏（WBS-T1-1 / 反向护栏「参数扰动±20%响应必变」）。

验收（判据 D 思路，防常数假绿）：
  ① 默认 schema 派生出合理响应（带宽 >0、响应度 >0）
  ② 扰动 R_electrode ±20% → 3dB 带宽必须变化（RC 限制映射生效）
  ③ 扰动量子效率 ±20% → 响应度必须变化
  ④ 反常数假绿：每个参数各 ±20% 扰动，至少一个派生响应变化（非自证桩）
  ⑤ 接 B29/B30 锚定点不报错且来源标注（calibrate_from_anchors）
"""
import copy
import unittest

from lda_l2.compact_model import (
    CompactModelSpec, derive_responses, calibrate_from_anchors,
)
from lda_harness.b29_thermal_phase_anchor import b29_thermal_phase_report
from lda_harness.b30_readout_anchor import b30_readout_report


class TestCompactModel(unittest.TestCase):

    def test_default_derives_sane_responses(self):
        r = derive_responses(CompactModelSpec(name="test"))
        self.assertGreater(r["bw_3db_ghz"], 0.0)
        self.assertGreater(r["responsivity_AW"], 0.0)
        self.assertGreater(r["Vpi_at_length_V"], 0.0)

    # ── 🔴 v0.9.287 单位口径（V·cm → V·mm）──────────────────────────
    # 旧实现 `VpiL_Vcm / length_mm` 是「V·cm ÷ mm」，量纲不成立 ⇒ 整整小 10×，
    # 而当时门禁只断言 `Vpi_at_length_V > 0.0` ⇒ **有门禁提到 ≠ 门禁能证伪**。
    # 下面四条：一条**绝对量级锚点** + 一条单位不变量 + 一条跨模块互证 + 一条反向探针。
    def test_vpi_unit_anchor_10mm_equals_vpil_vcm(self):
        """单位锚点：10 mm = 1 cm ⇒ Vπ 数值上必须**恰好等于** VπL[V·cm]。

        🔴 必须是绝对量级判据：比值型不变量（Vπ × L = const）**对单位错无能为力**
        —— 旧式 `VπL/L` 也满足 Vπ×L = VπL，只是绝对值小 10×。
        """
        for vpil in (1.0, 2.0, 7.5):
            r = derive_responses(CompactModelSpec(VpiL_Vcm=vpil, length_mm=10.0))
            self.assertAlmostEqual(r["Vpi_at_length_V"], vpil, places=9)

    def test_vpi_length_invariant_in_v_mm(self):
        """Vπ × L[mm] == 10 × VπL[V·cm]（即 V·mm 口径下的 VπL 不变量）。"""
        vpil = 2.0
        for L in (0.5, 1.0, 4.0, 10.0):
            r = derive_responses(CompactModelSpec(VpiL_Vcm=vpil, length_mm=L))
            self.assertAlmostEqual(r["Vpi_at_length_V"] * L, 10.0 * vpil, places=9)

    def test_vpi_cross_module_agrees_with_eic_behavioral(self):
        """与 `eic_behavioral.vpi_from_vpi_l`（V·mm 口径）逐点一致 —— 两套单位处理互证。"""
        from lda_l2.eic_behavioral import vpi_from_vpi_l
        vpil_vcm = 2.0
        for L in (0.5, 1.0, 4.0):
            a = derive_responses(CompactModelSpec(VpiL_Vcm=vpil_vcm,
                                                  length_mm=L))["Vpi_at_length_V"]
            b = vpi_from_vpi_l(vpil_vcm * 10.0, L * 1000.0)
            self.assertAlmostEqual(a, b, places=9)

    def test_vpi_reverse_probe_old_bug_would_be_caught(self):
        """反向探针：旧式 `VπL/L`（漏 ×10）必须被上面三条抓住。"""
        vpil, L = 2.0, 10.0
        buggy = vpil / L                                   # 0.2 V（旧实现）
        good = derive_responses(CompactModelSpec(VpiL_Vcm=vpil,
                                                 length_mm=L))["Vpi_at_length_V"]
        self.assertAlmostEqual(good / buggy, 10.0, places=9)   # 正好差 10×
        with self.assertRaises(AssertionError):
            self.assertAlmostEqual(buggy, vpil, places=9)      # 旧值过不了单位锚点

    def test_perturb_relectrode_changes_bandwidth(self):
        base = CompactModelSpec()
        rb = derive_responses(base)["bw_3db_ghz"]
        hi = copy.copy(base); hi.R_electrode_ohm = base.R_electrode_ohm * 1.2
        lo = copy.copy(base); lo.R_electrode_ohm = base.R_electrode_ohm * 0.8
        rh = derive_responses(hi)["bw_3db_ghz"]
        rl = derive_responses(lo)["bw_3db_ghz"]
        self.assertNotAlmostEqual(rh, rb, places=6)
        self.assertNotAlmostEqual(rl, rb, places=6)
        self.assertLess(rh, rb)   # 电阻增大 → 带宽下降

    def test_perturb_quantum_eff_changes_responsivity(self):
        base = CompactModelSpec()
        rr = derive_responses(base)["responsivity_AW"]
        hi = copy.copy(base); hi.quantum_eff = min(0.99, base.quantum_eff * 1.2)
        lo = copy.copy(base); lo.quantum_eff = max(0.01, base.quantum_eff * 0.8)
        self.assertGreater(derive_responses(hi)["responsivity_AW"], rr)
        self.assertLess(derive_responses(lo)["responsivity_AW"], rr)

    def test_reverse_no_constant_model(self):
        # 每个参数 ±20% 扰动都必须使某个派生响应变化（杜绝常数假绿）
        base = CompactModelSpec()
        rb = derive_responses(base)
        fields = ["VpiL_Vcm", "length_mm", "R_electrode_ohm", "C_junction_fF",
                  "C_electrode_fF", "quantum_eff", "wavelength_nm", "dark_current_nA"]
        for f in fields:
            hi = copy.copy(base); lo = copy.copy(base)
            v = getattr(base, f)
            setattr(hi, f, v * 1.2)
            setattr(lo, f, v * 0.8)
            rh = derive_responses(hi); rl = derive_responses(lo)
            changed = any(rh[k] != rb[k] or rl[k] != rb[k] for k in rb)
            self.assertTrue(changed, f"参数 {f} 扰动后响应未变（疑似常数假绿）")

    def test_calibrate_from_anchors(self):
        spec = CompactModelSpec(name="cal")
        spec = calibrate_from_anchors(
            spec, b29_report=b29_thermal_phase_report(),
            b30_report=b30_readout_report())
        self.assertIsNotNone(spec.thermal_phase_deg_per_mW)
        self.assertIsNotNone(spec.readout_fidelity_F)
        self.assertEqual(spec.source["thermal_phase_deg_per_mW"], "B29-anchor")
        self.assertEqual(spec.source["readout_fidelity_F"], "B30-anchor")


if __name__ == "__main__":
    # F-18（v0.9.113 · 波次 2 · 审计：「19 个 smoke 用 unittest、其余用自研
    # check() ⇒ 两套测试范式并存」）：本文件保留标准 unittest 写测试体，
    # 但**报告与退出契约统一走 smoke_kit** —— 逐条 `  [PASS] <name>`，
    # 失败/错误仍打标准 FAIL:/ERROR: 块（含 traceback，CI 判定「失败痕迹」可命中，
    # 不会被误判 SKIP），rc 与 `unittest.main(verbosity=2)` 逐位一致。
    from lda_harness.smoke_kit import run_unittest_suite

    raise SystemExit(run_unittest_suite(TestCompactModel))
