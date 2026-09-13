"""P1-3 · 四层系统（S9）立项前红线闸门自检 smoke（CI core 173）。

断言：
  G1 主权：受检 L1/L2 引擎未借 Meep/Tidy3D（A 级禁）PASS。
  G2 LLM：受检引擎无 torch/transformers/openai 进判决路径 PASS。
  G3 每层锚（建议 A）：**四层**均挂 VMM 锚 ≥ self_certified ⇒ 全 ADMISSIBLE，整体 PASS；
     L1(B14 方法学独立) / L2(Reck 定理) 高于门槛；L3/L4 为 Tier-1 自证桩（诚实标注，
     **不得**冒充 strict，带升级路径与验证责任方）。
  G4 不虚报：demo 披露明确真实相干实测未含、不声称已实现相干光学计算机 PASS。
  G5 外置激光可绕：BYPASSABLE。
  引擎内核：MZI 网格重构目标酉（DFT-4）保真度 > 0.999、fro_err < 1e-9（机器精度）。
  反向可证伪：tier < self_certified（"none"）必须判 SUSPENDED（护栏真会响）。

纪律：纯 numpy 死标量，无 wall-clock；失败即非零退出（CI 门禁）。
运行：python -m lda.run_four_layer_redline_gate_smoke
"""
from __future__ import annotations

import sys
import os
import unittest

# 项目根引导：本文件位于 lda/，模块用绝对包路径 from lda.lda_l2... 导入，
# 故需把项目根（lda/ 的父目录）加入 sys.path，使其在 run_ci_regression.py
# 的 cwd=lda/ + 脚本路径式调用下也可导入（与 -m 调用等价）。
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class FourLayerRedLineGateSmoke(unittest.TestCase):

    def test_gate_hard_discipline(self):
        from lda.lda_l2.four_layer_redline_gate import run_four_layer_redline_gate
        rep = run_four_layer_redline_gate()
        g = rep.to_dict()
        # G1 / G2 / G4 硬纪律必须 PASS；G5 必须 BYPASSABLE
        self.assertEqual(g["gates"]["G1"]["status"], "PASS", msg=g["gates"]["G1"]["verdict"])
        self.assertEqual(g["gates"]["G2"]["status"], "PASS", msg=g["gates"]["G2"]["verdict"])
        self.assertEqual(g["gates"]["G4"]["status"], "PASS", msg=g["gates"]["G4"]["verdict"])
        self.assertEqual(g["gates"]["G5"]["status"], "BYPASSABLE", msg=g["gates"]["G5"]["verdict"])

    def test_all_four_layers_admissible_at_min_tier(self):
        """建议 A：四层均挂 VMM 锚 ≥ self_certified ⇒ 全 ADMISSIBLE、整体 PASS。"""
        from lda.lda_l2.four_layer_redline_gate import run_four_layer_redline_gate
        rep = run_four_layer_redline_gate()
        g = rep.to_dict()
        layers = g["gates"]["G3"]["layers"]
        self.assertEqual(set(layers.keys()),
                         {"L1_passive_frontend", "L2_compilation",
                          "L3_control_calibration", "L4_cosim"})
        for name, ly in layers.items():
            self.assertEqual(ly["status"], "ADMISSIBLE", msg=f"{name} 未达 self_certified 门槛")
        # 整体过闸
        self.assertEqual(rep.overall, "PASS", msg=f"红线闸门整体 = {rep.overall}")
        self.assertEqual(g["suspended_layers"], [], msg="不应有挂起层")
        self.assertEqual(g["gates"]["G3"]["status"], "PASS")
        # 层成熟度须落位
        self.assertEqual(layers["L3_control_calibration"]["maturity_tier"], "self_certified")
        self.assertEqual(layers["L4_cosim"]["maturity_tier"], "self_certified")

    def test_l3_l4_are_honest_tier1_stubs(self):
        """G4 纪律：L3/L4 只可标 Tier-1 自证桩，且带升级路径 + 验证责任方（不虚报）。"""
        from lda.lda_l2.four_layer_redline_gate import run_four_layer_redline_gate
        rep = run_four_layer_redline_gate()
        layers = rep.to_dict()["gates"]["G3"]["layers"]
        for name in ("L3_control_calibration", "L4_cosim"):
            a = layers[name]["anchor"]
            self.assertEqual(a["tier"], "self_certified", msg=f"{name} tier 谎报")
            self.assertEqual(a["provenance"], "self_authored_closed_form")
            self.assertTrue(a["upgrade_path"], msg=f"{name} 缺升级路径")
            self.assertTrue(a["who_verifies"], msg=f"{name} 缺验证责任方")
            # 自证桩须构造性自洽（反解残差 ≈ 0）+ 端点成立
            self.assertLess(a["residual"], 1e-9, msg=f"{name} 闭环残差非零（模型不自洽）")
            self.assertTrue(a["endpoints_ok"], msg=f"{name} 端点不成立")
        # 高于门槛的 L1/L2 不得被降级为自证桩
        self.assertIn(layers["L1_passive_frontend"]["maturity_tier"],
                      ("methodologically_independent", "strict_independent"))
        self.assertIn(layers["L2_compilation"]["maturity_tier"],
                      ("mathematical_theorem", "strict_independent"))

    def test_reverse_below_threshold_suspends(self):
        """反向可证伪：tier < self_certified 必判 SUSPENDED（护栏真会响）。"""
        from lda.lda_l2.four_layer_redline_gate import _classify_layer_status
        self.assertEqual(_classify_layer_status("none"), "SUSPENDED")
        self.assertEqual(_classify_layer_status("self_certified"), "ADMISSIBLE")
        self.assertEqual(_classify_layer_status("degraded_ordinal"), "ADMISSIBLE")
        self.assertEqual(_classify_layer_status("strict_independent"), "ADMISSIBLE")

    def test_mzi_engine_reconstruction_machine_precision(self):
        from lda.lda_l2.mzi_mesh_matmul import (
            run_mzi_mesh_matmul_demo, dft_matrix)
        rep = run_mzi_mesh_matmul_demo(dft_matrix(4))
        self.assertGreater(rep["fidelity"], 0.999, msg="MZI 重构保真度不足")
        self.assertLess(rep["recon_err_fro"], 1e-9, msg="MZI 重构非机器精度（虚报）")
        # 对外演示级联插损为有限实数（诚实预算，非幻数）
        self.assertGreaterEqual(rep["cascade_loss_db"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
