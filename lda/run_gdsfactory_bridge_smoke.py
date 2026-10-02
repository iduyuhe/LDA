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
        import importlib.util
        import sys
        import types

        from lda_l1.gdsfactory_bridge import (
            gdsfactory_available, gf_component_to_spec,
        )
        # 🔴 语义判据（v0.9.183 强化）：`gdsfactory_available()` 必须与**独立的可用性
        #    探测**（importlib.util.find_spec）一致 —— 不得恒真/恒假。
        #    旧判据只 `assertIsInstance(avail, bool)` ⇒ **恒真**，因此 1529c9f 把
        #    `import gdsfactory  # noqa: F401` 当 F401 删掉（函数退化为 `return True`）
        #    后本门禁仍全绿（血案：删 import ⇒ 改语义，只断言类型抓不到）。
        real = importlib.util.find_spec("gdsfactory") is not None
        self.assertEqual(gdsfactory_available(), real,
                         "gdsfactory_available() 必须等于真实可导入性（非恒真/恒假）")

        # 反向探针（双向，证明函数真的在探测）：
        #   ① 注入假 gdsfactory 模块 ⇒ 必须 True；② 拦截 import ⇒ 必须 False。
        saved = sys.modules.get("gdsfactory")
        try:
            sys.modules["gdsfactory"] = types.ModuleType("gdsfactory")
            self.assertTrue(gdsfactory_available(),
                            "注入可导入的 gdsfactory 后必须返回 True（防恒假）")
        finally:
            if saved is None:
                sys.modules.pop("gdsfactory", None)
            else:
                sys.modules["gdsfactory"] = saved

        class _Blocker:
            def find_spec(self, name, path=None, target=None):
                if name == "gdsfactory":
                    raise ImportError("blocked by smoke probe")
                return None

        blocker = _Blocker()
        sys.meta_path.insert(0, blocker)
        try:
            self.assertFalse(gdsfactory_available(),
                             "拦截 gdsfactory 导入后必须返回 False（防恒真）")
        finally:
            sys.meta_path.remove(blocker)
        self.assertEqual(gdsfactory_available(), real, "探针须无副作用（恢复原值）")
        # 桥函数本身可调用（缺组件时返回合法 spec 结构）
        fake = type("C", (), {"name": "demo", "references": [], "ports": {}})()
        spec = gf_component_to_spec(fake, name="demo")
        self.assertIn("devices", spec)
        self.assertIn("io", spec)


if __name__ == "__main__":
    # F-18（v0.9.113 · 波次 2 · 审计：「19 个 smoke 用 unittest、其余用自研
    # check() ⇒ 两套测试范式并存」）：本文件保留标准 unittest 写测试体，
    # 但**报告与退出契约统一走 smoke_kit** —— 逐条 `  [PASS] <name>`，
    # 失败/错误仍打标准 FAIL:/ERROR: 块（含 traceback，CI 判定「失败痕迹」可命中，
    # 不会被误判 SKIP），rc 与 `unittest.main(verbosity=2)` 逐位一致。
    from lda_harness.smoke_kit import run_unittest_suite

    raise SystemExit(run_unittest_suite(GdsfactoryBridgeSmoke))
