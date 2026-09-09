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
    unittest.main(verbosity=2)
