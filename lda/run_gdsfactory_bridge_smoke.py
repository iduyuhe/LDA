"""gdsfactory 兼容桥 + GDS 主权几何 DRC smoke（v0.8.30 · 入 CI core）。

验证：
  ① lda_l2.gds_export.parse_gds_polygons —— 主权最小解析器还原多边形几何；
  ② lda_l2.gds_drc.check_geometry —— 几何子集 DRC（最小线宽/间距/面积）死标量；
  ③ lda_l1.gdsfactory_bridge —— gdsfactory 可用时转 spec；不可用时优雅降级；
  ④ 回路：LDA 自造 GDS → parse → DRC 全绿 + 一条故意违规（线宽0.05<0.12）判 FAIL。

红线：全部几何死标量；不依赖 gdsfactory（可选，缺失时仅测主权解析+DRC 回路）。
主权纪律：本桥对接 B 级 gdsfactory，但 LDA 核心零硬依赖；几何 DRC 仅子集。
"""
from __future__ import annotations

import os
import sys
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


class GdsfactoryBridgeSmoke(unittest.TestCase):

    def test_parse_and_drc_pass(self):
        from lda_l2 import gds_export
        from lda_l2.gds_drc import check_geometry
        poly = [(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)]
        b = gds_export.gds_library("T", {
            "C": [gds_export.path(1, 0.5, [(0, 0), (20, 0)]),
                  gds_export.boundary(1, poly)],
        })
        parsed = gds_export.parse_gds_polygons(b)
        self.assertEqual(len(parsed["structures"]), 1)
        rep = check_geometry(parsed["structures"])
        self.assertTrue(rep["all_pass"], f"合法几何应过 DRC：{rep['violations']}")
        self.assertEqual(rep["n_elements"], 2)

    def test_drc_rejects_undersized(self):
        from lda_l2 import gds_export
        from lda_l2.gds_drc import check_geometry
        # PATH 宽 0.05µm < 最小 0.12 → 应判 FAIL
        b = gds_export.gds_library("T", {
            "C": [gds_export.path(1, 0.05, [(0, 0), (10, 0)])],
        })
        parsed = gds_export.parse_gds_polygons(b)
        rep = check_geometry(parsed["structures"])
        self.assertFalse(rep["all_pass"], "线宽 0.05µm < 0.12µm 必须判违规")
        self.assertTrue(any("线宽" in v for v in rep["violations"]))

    def test_gf_bridge_graceful(self):
        from lda_l1.gdsfactory_bridge import (
            gdsfactory_available, gf_component_to_spec,
        )
        # 无论 gdsfactory 是否安装，桥模块都能 import 且不崩
        avail = gdsfactory_available()
        # 未装时优雅返回 False；装了则 True（CI 本机通常未装，属 B 级可选）
        self.assertIsInstance(avail, bool)
        # 桥函数本身可调用（缺组件时返回合法 spec 结构）
        fake = type("C", (), {"name": "demo", "references": [], "ports": {}})()
        spec = gf_component_to_spec(fake, name="demo")
        self.assertIn("devices", spec)
        self.assertIn("io", spec)


if __name__ == "__main__":
    unittest.main(verbosity=2)
