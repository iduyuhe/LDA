"""版图几何级 RC 寄生估算 smoke（v0.8.31 · 设计侧主权闭环收口）。

覆盖：
  1. 合法版图（金属走线 path + 器件多边形 boundary）→ R/C 数值合理（正、有限）
  2. 超长细走线 → 串联电阻越过主权几何护栏 → 判 FAIL（诚实阈值，非签核）
  3. 空结构 → 优雅不崩溃，totals 归零
  4. Markdown 报告含诚实边界标注

零依赖、纯 numpy 不存在（仅标准库），CI core 可跑。LLM 不进判决路径。
"""
from __future__ import annotations

import os
import sys
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


def _metal_path() -> Dict[str, list]:
    """一条 15µm 长、0.5µm 宽金属走线（层 11，合法量级）。"""
    return {
        "WG1": [{
            "layer": 11, "kind": "path", "width": 0.5,
            "points_um": [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)],
        }]
    }


def _device_boundary() -> Dict[str, list]:
    """一个有源硅器件多边形（层 1，4µm×4µm）。"""
    return {
        "DEV1": [{
            "layer": 1, "kind": "boundary", "width": None,
            "points_um": [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0),
                          (0.0, 4.0), (0.0, 0.0)],
        }]
    }


class ParasiticRCSmoke(unittest.TestCase):

    def test_estimate_legal_layout(self):
        from lda_l2.parasitic_rc import estimate_parasitics, check_parasitic
        structures = {}
        structures.update(_metal_path())
        structures.update(_device_boundary())
        rep = estimate_parasitics(structures)
        chk = check_parasitic(rep)
        self.assertGreater(rep["totals"]["R_series_ohm"], 0.0,
                           "合法金属走线应估算出正电阻")
        self.assertGreater(rep["totals"]["C_total_ff"], 0.0,
                           "器件应估算出正电容")
        self.assertTrue(chk["all_pass"],
                        f"合法版图不应触发护栏：{chk['violations']}")
        # 金属 15µm/0.5µm：R≈ R□(0.05)×(15/0.5)=1.5Ω，量级合理
        self.assertAlmostEqual(rep["by_structure"]["WG1"]["R_series_ohm"],
                               1.5, delta=0.5)

    def test_threshold_fail_long_thin(self):
        from lda_l2.parasitic_rc import estimate_parasitics, check_parasitic
        # 20000µm 长、0.05µm 宽金属走线 → R≈ 0.05×4e5 = 2e4Ω > 1000Ω 护栏
        structures = {
            "LONG": [{
                "layer": 11, "kind": "path", "width": 0.05,
                "points_um": [(0.0, 0.0), (20000.0, 0.0)],
            }]
        }
        rep = estimate_parasitics(structures)
        chk = check_parasitic(rep)
        self.assertFalse(chk["all_pass"], "超长细走线应触发电阻护栏")
        self.assertTrue(any("R=" in v or "串联电阻" in v for v in chk["violations"]),
                        f"应含电阻违例：{chk['violations']}")

    def test_empty_graceful(self):
        from lda_l2.parasitic_rc import estimate_parasitics, check_parasitic
        rep = estimate_parasitics({})
        chk = check_parasitic(rep)
        self.assertEqual(rep["totals"]["R_series_ohm"], 0.0)
        self.assertEqual(rep["totals"]["C_total_ff"], 0.0)
        self.assertEqual(rep["totals"]["n_elements"], 0)
        self.assertTrue(chk["all_pass"])

    def test_markdown_honest_boundary(self):
        from lda_l2.parasitic_rc import (
            estimate_parasitics, check_parasitic, parasitic_rc_markdown)
        structures = _metal_path()
        rep = estimate_parasitics(structures)
        md = parasitic_rc_markdown(rep, check_parasitic(rep))
        self.assertIn("几何级 RC 寄生估算", md)
        self.assertIn("非 foundry 工艺级", md)
        self.assertIn("诚实边界", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
